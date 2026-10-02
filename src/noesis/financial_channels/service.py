"""Propuestas exactas y recibos de canal, sin autoridad ni dispatch para la IA."""

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from noesis import db
from noesis.core.locks import lock_business
from noesis.bank_capture.service import BankCapture
from noesis.financial_operations.contracts import (
    AccessDenied,
    CommandType,
    ConflictError,
    EntryIdentity,
    EntryNamespace,
    Operation,
    OperationState,
    Principal,
    StateError,
    canonical_json,
    digest,
    positive_id,
    strict_json,
    uuid_text,
)
from noesis.financial_operations.service import FinancialOperations, _now
from noesis.invoice_capture.service import InvoiceCapture
from noesis.payment_capture.service import PaymentCapture
from noesis.purchasing_capture import ExpenseCapture, SupplierInvoiceCapture

current = ContextVar("authenticated_financial_channel", default=None)


def exact_revision(value):
    """Transporte sin pérdida para revisiones que exceden enteros exactos de JS."""
    if value is None:
        return None
    if isinstance(value, str):
        if not re.fullmatch(r"[1-9][0-9]{0,18}", value):
            raise ValueError("Revisión decimal canónica requerida.")
        value = int(value)
    return positive_id(value)


@dataclass(frozen=True, slots=True)
class ChannelContext:
    business_id: int
    principal: Principal
    identity: EntryIdentity
    actor: str
    # Solo en memoria: sirve a interpretación local, nunca se copia a operaciones.
    message: str = ""
    transport_identity: EntryIdentity | None = None
    confirmation_target: tuple | None = None
    reply_to: str = ""

    def __post_init__(self):
        positive_id(self.business_id)
        if not isinstance(self.principal, Principal) or not isinstance(
            self.identity, EntryIdentity
        ):
            raise AccessDenied("Contexto de servidor autenticado requerido.")
        if not isinstance(self.actor, str) or not self.actor:
            raise AccessDenied("Actor de canal requerido.")
        if self.confirmation_target is not None:
            if (
                not isinstance(self.confirmation_target, tuple)
                or len(self.confirmation_target) != 3
            ):
                raise ValueError("Referencia de propuesta exacta requerida.")
            op, hash_value, revision = self.confirmation_target
            uuid_text(op)
            if (
                not isinstance(hash_value, str)
                or len(hash_value) != 64
                or set(hash_value) - set("0123456789abcdef")
            ):
                raise ValueError("Huella de propuesta inválida.")
            object.__setattr__(
                self, "confirmation_target", (uuid_text(op), hash_value, exact_revision(revision))
            )

    @property
    def receipt_hash(self):
        return (
            digest(canonical_json([self.message, self.confirmation_target, self.reply_to]))
            if (self.message or self.confirmation_target is not None or self.reply_to)
            else None
        )

    @property
    def actor_key(self):
        return digest(
            canonical_json([self.principal.user_id, self.principal.session_version, self.actor])
        )

    @classmethod
    def web(cls, business_id, principal, request_uuid, *, chat=False, message=""):
        identity = (
            EntryIdentity.chat(request_uuid, 1) if chat else EntryIdentity.web_api(request_uuid)
        )
        return cls(
            business_id,
            principal,
            identity,
            f"web:{principal.user_id}:{principal.session_version}",
            message,
        )

    @classmethod
    def whatsapp(cls, business_id, principal, message_id, recipient, phone, *, message=""):
        return cls(
            business_id,
            principal,
            EntryIdentity.whatsapp_scoped("meta", recipient, business_id, message_id),
            f"wa:{phone}",
            message,
        )


def checkpoint(stage):
    """Frontera local de fallos, sin I/O ni extensiones financieras."""


def capture_for(business_id, command):
    command = CommandType(command)
    if command in {CommandType.INVOICE_ISSUE, CommandType.INVOICE_RECTIFY}:
        return InvoiceCapture(business_id)
    if command == CommandType.CUSTOMER_PAYMENT_RECORD:
        return PaymentCapture(business_id)
    if command in {CommandType.BANK_TRANSACTION_IMPORT, CommandType.BANK_TRANSACTION_MATCH}:
        return BankCapture(business_id)
    if command in {
        CommandType.SUPPLIER_INVOICE_CONFIRM,
        CommandType.SUPPLIER_INVOICE_CORRECT,
        CommandType.SUPPLIER_INVOICE_VOID,
    }:
        return SupplierInvoiceCapture(business_id)
    if command in {CommandType.EXPENSE_CONFIRM, CommandType.EXPENSE_VOID}:
        return ExpenseCapture(business_id)
    raise StateError("Acción todavía no conectada al Financial Core.")


def review_intent(capture, principal, intent):
    if set(intent) != {"command", "target_id", "fields"} or not isinstance(intent["fields"], dict):
        raise ValueError("Acción cerrada con command/target_id/fields requerida.")
    # Valida también claves reservadas anidadas y rechaza float antes de review.
    canonical_json(intent)
    command, target, fields = CommandType(intent["command"]), intent["target_id"], intent["fields"]
    if command in {CommandType.INVOICE_ISSUE, CommandType.INVOICE_RECTIFY}:
        request = capture.review(principal, target, **fields)
        if request.command_type != command:
            raise StateError("Acción de emisión distinta de la solicitada.")
        return request
    if command == CommandType.CUSTOMER_PAYMENT_RECORD:
        return capture.review(principal, target, **fields)
    if command == CommandType.BANK_TRANSACTION_IMPORT:
        if target is not None:
            raise ValueError("Importación nueva sin target.")
        return capture.review_import(principal, **fields)
    if command == CommandType.BANK_TRANSACTION_MATCH:
        if fields:
            raise ValueError("Match revisa la sugerencia real, sin campos adicionales.")
        return capture.review_match(principal, target)
    if command in {CommandType.SUPPLIER_INVOICE_CONFIRM, CommandType.EXPENSE_CONFIRM}:
        if target is not None:
            raise ValueError("Alta nueva sin target.")
        return capture.review_confirm(principal, **fields)
    if command == CommandType.SUPPLIER_INVOICE_CORRECT:
        return capture.review_correct(principal, target, **fields)
    return capture.review_void(principal, target, **fields)


def preview(request):
    """Solo datos congelados; sin UUID/hash/eventos/asientos en el texto humano."""
    command, p = request.command_type, request.parameters
    labels = {
        CommandType.INVOICE_ISSUE: "Emitir factura",
        CommandType.INVOICE_RECTIFY: "Emitir rectificativa",
        CommandType.CUSTOMER_PAYMENT_RECORD: "Registrar cobro",
        CommandType.SUPPLIER_INVOICE_CONFIRM: "Registrar factura recibida",
        CommandType.SUPPLIER_INVOICE_CORRECT: "Corregir factura recibida",
        CommandType.SUPPLIER_INVOICE_VOID: "Retirar factura recibida",
        CommandType.EXPENSE_CONFIRM: "Registrar gasto",
        CommandType.EXPENSE_VOID: "Retirar gasto",
        CommandType.BANK_TRANSACTION_IMPORT: "Importar movimiento bancario",
        CommandType.BANK_TRANSACTION_MATCH: "Confirmar cobro de este movimiento",
    }
    lines = [labels[command]]
    if command in {CommandType.INVOICE_ISSUE, CommandType.INVOICE_RECTIFY}:
        approved = p["approved_document"]
        lines += [f"Cliente: {approved['client']['name']}", f"Factura: #{request.target_id}"]
        invoice = approved["invoice"]
        if invoice.get("operation_date"):
            lines.append(f"Fecha de operación: {invoice['operation_date']}")
        for key, label in (("vat_amount", "IVA"), ("irpf_amount", "IRPF")):
            if invoice.get(key) is not None:
                lines.append(f"{label}: {invoice[key]} €")
    elif command == CommandType.CUSTOMER_PAYMENT_RECORD:
        lines += [f"Factura: #{request.target_id}", f"Método: {p['method'] or 'sin indicar'}"]
    elif command == CommandType.BANK_TRANSACTION_IMPORT:
        movement = p["movement"]
        lines += [
            f"Movimiento: {movement['description'] or 'sin descripción'}",
            f"Cuenta: {p['account_scope']}",
        ]
    elif command == CommandType.BANK_TRANSACTION_MATCH:
        lines += [f"Movimiento: #{request.target_id}", f"Factura: #{p['invoice_id']}"]
    else:
        fields = p["fields"] or p["before"]
        if fields.get("concept"):
            lines.append(f"Concepto: {fields['concept']}")
        supplier = fields.get("supplier_name") or fields.get("supplier_id")
        if supplier:
            lines.append(f"Proveedor: {supplier}")
        for key, label in (
            ("issued_on", "Fecha del proveedor"),
            ("spent_on", "Fecha del gasto"),
            ("vat_amount", "IVA"),
            ("irpf_amount", "IRPF"),
        ):
            if fields.get(key) is not None:
                lines.append(f"{label}: {fields[key]}")
        if request.target_id:
            lines.append(f"Registro: #{request.target_id}")
    lines += [f"Importe: {request.amount:.2f} €", f"Fecha de la acción: {request.effective_on}"]
    if request.reason:
        lines.append(f"Motivo: {request.reason}")
    return "\n".join(lines)


class FinancialChannels:
    def __init__(self, context):
        if not isinstance(context, ChannelContext):
            raise AccessDenied("Falta identidad autenticada de canal; no fallback.")
        self.context = context
        self.business_id = context.business_id
        self.operations = FinancialOperations(self.business_id)

    def _link(self, session, operation_uuid):
        row = session.execute(
            "SELECT * FROM financial_channel_proposals WHERE business_id=? AND operation_uuid=?",
            (self.business_id, uuid_text(operation_uuid)),
        ).fetchone()
        if not row:
            raise AccessDenied("Propuesta financiera no disponible en este canal.")
        allowed = {self.context.identity.namespace.value}
        if self.context.identity.namespace in {EntryNamespace.CHAT, EntryNamespace.WHATSAPP}:
            allowed.add("document_review")
        if self.context.identity.namespace == EntryNamespace.WEB_API:
            allowed.update({"document_review", "recurring", "import"})
        if row["actor_key"] != self.context.actor_key or row["channel"] not in allowed:
            raise AccessDenied("Propuesta de otra conversación, usuario o sesión.")
        return row

    def _guard(self, session, operation, stage):
        # Mismo orden del writer: negocio antes de bloquear la plantilla.
        lock_business(session, self.business_id)
        if stage == "lock":
            return
        row = self._link(session, operation.operation_uuid)
        if row["request_hash"] != operation.request.request_hash:
            raise StateError("Propuesta y request no coinciden.")
        if stage == "execute" and operation.state in {
            OperationState.APPROVED,
            OperationState.COMMITTED,
        }:
            receipt = session.execute(
                "SELECT 1 FROM financial_channel_receipts WHERE business_id=? AND operation_uuid=? "
                "AND authorization_uuid=? AND request_hash=? AND decision='yes'",
                (
                    self.business_id,
                    operation.operation_uuid,
                    operation.authorization_uuid,
                    operation.request.request_hash,
                ),
            ).fetchone()
            if not receipt:
                raise AccessDenied("Falta recibo durable de confirmación del canal.")
        if operation.state != OperationState.COMMITTED:
            if (
                row["actor_session_version"] != self.context.principal.session_version
                or row["expires_at"] <= _now()
            ):
                raise StateError("La propuesta ha caducado; revisa otra vez.")
            if row["recurring_context"] is not None:
                from .recurring import validate_occurrence

                validate_occurrence(
                    session, self.business_id, strict_json(row["recurring_context"])
                )

    def _receipt(self, session, identity=None):
        identity = identity or self.context.identity
        return session.execute(
            "SELECT * FROM financial_channel_receipts WHERE business_id=? AND channel=? AND receipt_key=?",
            (self.business_id, identity.namespace.value, identity.key),
        ).fetchone()

    def _review_ack(self, session, operation):
        """Ligar también un UUID que recupera una propuesta preexistente."""
        origin = self.context.transport_identity or self.context.identity
        existing = self._receipt(session, origin)
        message_hash = self.context.receipt_hash
        if existing:
            if (
                str(existing["operation_uuid"]) != operation.operation_uuid
                or existing["decision"] != "review"
                or existing["request_hash"] != operation.request.request_hash
                or existing["message_hash"] != message_hash
            ):
                raise ConflictError("Este recibo de revisión ya tiene otro contenido o finalidad.")
            return
        session.execute(
            "INSERT INTO financial_channel_receipts "
            "(business_id,channel,receipt_key,operation_uuid,request_hash,decision,authorization_uuid,recorded_at,message_hash) "
            "VALUES (?,?,?,?,?,'review',NULL,?,?)",
            (
                self.business_id,
                origin.namespace.value,
                origin.key,
                operation.operation_uuid,
                operation.request.request_hash,
                _now(),
                message_hash,
            ),
        )

    def replay(self):
        """Primero el recibo de confirmación, antes de consultar otro pending."""
        with self.operations._transaction(self.context.principal, write=False) as (session, repo):
            receipt = self._receipt(session)
            if receipt:
                if receipt["message_hash"] != self.context.receipt_hash:
                    raise ConflictError("Mismo mensaje de confirmación con contenido distinto.")
                operation = Operation.from_row(
                    repo.load(receipt["operation_uuid"], self.context.principal.user_id)
                )
                link = self._link(session, operation.operation_uuid)
                decision = receipt["decision"]
                if decision == "review":
                    return self._response(operation, link)
            else:
                row = session.execute(
                    "SELECT p.operation_uuid FROM financial_channel_proposals p JOIN financial_operations o "
                    "ON o.business_id=p.business_id AND o.operation_uuid=p.operation_uuid WHERE p.business_id=? "
                    "AND ((o.entry_namespace=? AND o.entry_key=?) OR (p.origin_channel=? AND p.origin_key=?))",
                    (
                        self.business_id,
                        self.context.identity.namespace.value,
                        self.context.identity.key,
                        self.context.identity.namespace.value,
                        self.context.identity.key,
                    ),
                ).fetchone()
                if not row:
                    return None
                operation = Operation.from_row(
                    repo.load(row["operation_uuid"], self.context.principal.user_id)
                )
                link = self._link(session, operation.operation_uuid)
                if link["origin_message_hash"] != self.context.receipt_hash:
                    raise ConflictError("Mismo recibo de mensaje con contenido distinto.")
                return self._response(operation, link)
        if decision == "no":
            return {
                "reply": "Descartado. No he cambiado ningún registro.",
                "action_result": "discarded",
                "source": "local",
            }
        return self.execute(operation.operation_uuid)

    def propose(
        self,
        intent,
        *,
        pending_actor=None,
        expected_pending_id=None,
        recurring_context=None,
        replaces=None,
    ):
        canonical = canonical_json(intent)
        identity = self.context.identity
        origin = self.context.transport_identity or identity
        command = CommandType(intent["command"])
        capture = capture_for(self.business_id, command)
        with self.operations._transaction(self.context.principal) as (session, repo):
            receipt = self._receipt(session, origin)
            if receipt:
                row = repo.load(receipt["operation_uuid"], self.context.principal.user_id)
                operation = Operation.from_row(row)
                link = self._link(session, operation.operation_uuid)
                if (
                    receipt["decision"] != "review"
                    or row["entry_namespace"] != identity.namespace.value
                    or row["entry_key"] != identity.key
                    or link["intent_canonical"] != canonical
                ):
                    raise ConflictError("Mismo UUID de acción con identidad o contenido diferente.")
                self._review_ack(session, operation)
                return self._response(operation, link)
            row = session.execute(
                "SELECT operation_uuid FROM financial_operations WHERE business_id=? AND entry_namespace=? "
                "AND entry_key=?",
                (self.business_id, identity.namespace.value, identity.key),
            ).fetchone()
            if row:
                operation = Operation.from_row(
                    repo.load(row["operation_uuid"], self.context.principal.user_id)
                )
                link = self._link(session, operation.operation_uuid)
                if link["intent_canonical"] != canonical:
                    raise ConflictError("Mismo recibo de acción con contenido diferente.")
                self._review_ack(session, operation)
                return self._response(operation, link)
        request = review_intent(capture, self.context.principal, intent)
        if command == CommandType.BANK_TRANSACTION_IMPORT:
            if identity != EntryIdentity.imported(
                request.parameters["batch"], request.parameters["row"]
            ):
                raise StateError(
                    "Importar requiere identidad estable batch/fila, no upload genérico."
                )
        text = preview(request)
        expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(
            timespec="microseconds"
        )

        def record(session, operation):
            session.execute(
                "INSERT INTO financial_channel_proposals "
                "(business_id,operation_uuid,request_hash,actor_session_version,channel,actor_key,intent_canonical,intent_hash,"
                "preview,expires_at,created_at,recurring_context,origin_message_hash,origin_channel,origin_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(business_id,operation_uuid) DO NOTHING",
                (
                    self.business_id,
                    operation.operation_uuid,
                    request.request_hash,
                    self.context.principal.session_version,
                    identity.namespace.value,
                    self.context.actor_key,
                    canonical,
                    digest(canonical),
                    text,
                    expires,
                    _now(),
                    canonical_json(recurring_context) if recurring_context is not None else None,
                    self.context.receipt_hash,
                    origin.namespace.value,
                    origin.key,
                ),
            )
            link = self._link(session, operation.operation_uuid)
            if link["intent_canonical"] != canonical:
                raise ConflictError("Propuesta concurrente con contenido distinto.")
            self._review_ack(session, operation)
            if replaces is not None:
                from noesis.financial_operations.repository import OperationsRepository

                repo = OperationsRepository(session, self.business_id)
                old = repo.load(replaces, self.context.principal.user_id)
                self._link(session, replaces)
                if old["state"] != OperationState.PREPARED.value:
                    raise StateError("No corregir contenido ya autorizado.")
                repo.transition(old, OperationState.CANCELLED, _now())
            if pending_actor is not None:
                self._pending(session, operation, pending_actor, expected_pending_id)
            checkpoint("prepared")

        try:
            operation = capture.prepare(
                self.context.principal, identity, request, preparation_recorder=record
            )
        except ConflictError:
            # Dos reviews simultáneos pueden resolver una fecha default distinta.
            # Solo recuperar si los inputs originales coinciden con la intención durable.
            return self.propose_existing(canonical)
        checkpoint("proposal_committed")
        return self.response(operation)

    def propose_existing(self, canonical):
        with self.operations._transaction(self.context.principal) as (session, repo):
            row = session.execute(
                "SELECT operation_uuid FROM financial_operations WHERE business_id=? AND entry_namespace=? "
                "AND entry_key=?",
                (
                    self.business_id,
                    self.context.identity.namespace.value,
                    self.context.identity.key,
                ),
            ).fetchone()
            if not row:
                raise ConflictError("Conflicto de preparación.")
            operation = Operation.from_row(
                repo.load(row["operation_uuid"], self.context.principal.user_id)
            )
            link = self._link(session, operation.operation_uuid)
            if link["intent_canonical"] != canonical:
                raise ConflictError("Intención diferente bajo el mismo recibo.")
            self._review_ack(session, operation)
            return self._response(operation, link)

    def _pending(self, session, operation, actor, expected_id):
        if actor != self.context.actor:
            raise AccessDenied("Pending de otra conversación.")
        if expected_id is not None:
            changed = session.execute(
                "DELETE FROM whatsapp_pending_actions WHERE business_id=? AND phone=? AND id=? "
                "AND expires_at>=? RETURNING id",
                (self.business_id, actor, expected_id, db._now()),
            ).fetchone()
            if not changed:
                raise StateError("La propuesta cambió; no sustituirla silenciosamente.")
        else:
            previous = session.execute(
                "SELECT payload FROM whatsapp_pending_actions WHERE business_id=? AND phone=?",
                (self.business_id, actor),
            ).fetchone()
            if previous:
                raise StateError("Hay otra propuesta; descártala o corrígela antes de continuar.")
        link = self._link(session, operation.operation_uuid)
        body = canonical_json(
            {
                "operation_uuid_ref": operation.operation_uuid,
                "request_hash": operation.request.request_hash,
                "revision": operation.request.expected_revision,
                "preview": link["preview"],
            }
        )
        session.execute(
            "INSERT INTO whatsapp_pending_actions (business_id,phone,kind,payload,expires_at,created_at) "
            "VALUES (?,?,'financial_capture',?,?,?)",
            (
                self.business_id,
                actor,
                body,
                (datetime.now() + timedelta(minutes=30)).isoformat(timespec="seconds"),
                db._now(),
            ),
        )

    def _consume(self, session, operation, pending_actor, pending_id):
        if pending_actor is None:
            return
        row = session.execute(
            "SELECT payload FROM whatsapp_pending_actions WHERE business_id=? AND phone=? AND id=?",
            (self.business_id, pending_actor, pending_id),
        ).fetchone()
        if (
            not row
            or strict_json(row["payload"]).get("operation_uuid_ref") != operation.operation_uuid
        ):
            if self._receipt(session) is not None:
                return
            raise StateError("El SÍ no corresponde a la propuesta actual.")
        session.execute(
            "DELETE FROM whatsapp_pending_actions WHERE business_id=? AND phone=? AND id=?",
            (self.business_id, pending_actor, pending_id),
        )
        checkpoint("pending_consumed")

    def cancel_pending(self):
        """Una orden nueva cancela durablemente PREPARED antes de quitar pending."""
        with self.operations._transaction(self.context.principal) as (session, repo):
            lock_business(session, self.business_id)
            row = session.execute(
                "SELECT * FROM whatsapp_pending_actions WHERE business_id=? AND phone=?"
                + (" FOR UPDATE" if session.dialect == "postgres" else ""),
                (self.business_id, self.context.actor),
            ).fetchone()
            if not row or row["kind"] != "financial_capture":
                return False
            payload = strict_json(row["payload"])
            saved = repo.load(payload["operation_uuid_ref"], self.context.principal.user_id)
            self._link(session, saved["operation_uuid"])
            if saved["state"] != OperationState.PREPARED.value:
                raise StateError("Esta acción ya está autorizada; recupera su resultado.")
            repo.transition(saved, OperationState.CANCELLED, _now())
            session.execute(
                "DELETE FROM whatsapp_pending_actions WHERE business_id=? AND phone=? AND id=?",
                (self.business_id, self.context.actor, row["id"]),
            )
            return True

    def confirm(
        self,
        operation_uuid,
        *,
        approved_hash,
        approved_revision,
        decision="yes",
        pending_actor=None,
        pending_id=None,
    ):
        if decision not in {"yes", "no"}:
            raise ValueError("Confirmación humana explícita requerida.")
        approved_revision = exact_revision(approved_revision)
        operation = self.operations.recover(self.context.principal, operation_uuid)
        capture = capture_for(self.business_id, operation.request.command_type)
        capture.operations._channel_guard = self._guard
        if (
            approved_hash != operation.request.request_hash
            or approved_revision != operation.request.expected_revision
        ):
            raise StateError("Confirmación de otra versión o contenido.")
        with self.operations._transaction(self.context.principal, write=False) as (session, _):
            self._guard(session, operation, "authorize")
            receipt = self._receipt(session)
            if receipt and (
                str(receipt["operation_uuid"]) != operation.operation_uuid
                or receipt["decision"] != decision
            ):
                raise ConflictError("Este mensaje ya confirmó otra propuesta o decisión.")
            if receipt and receipt["message_hash"] != self.context.receipt_hash:
                raise ConflictError("Contenido distinto bajo la misma confirmación.")

        def record(session, approved):
            existing = self._receipt(session)
            if existing:
                if (
                    str(existing["operation_uuid"]) != approved.operation_uuid
                    or existing["decision"] != decision
                    or existing["request_hash"] != approved.request.request_hash
                    or existing["message_hash"] != self.context.receipt_hash
                ):
                    raise ConflictError("Confirmación ligada a otra propuesta o contenido.")
                return
            # Comprobar pending ANTES del INSERT del recibo: no sustituye versión.
            self._consume(session, approved, pending_actor, pending_id)
            session.execute(
                "INSERT INTO financial_channel_receipts "
                "(business_id,channel,receipt_key,operation_uuid,request_hash,decision,authorization_uuid,recorded_at,message_hash) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    self.business_id,
                    self.context.identity.namespace.value,
                    self.context.identity.key,
                    approved.operation_uuid,
                    approved.request.request_hash,
                    decision,
                    approved.authorization_uuid if decision == "yes" else None,
                    _now(),
                    self.context.receipt_hash,
                ),
            )
            checkpoint("authorization_recorded")

        if decision == "no":
            # Terminal y recibo/consumo también deben compartir transacción.
            with self.operations._transaction(self.context.principal) as (session, repo):
                self._guard(session, None, "lock")
                row = repo.load(operation_uuid, self.context.principal.user_id)
                actual = Operation.from_row(row)
                self._guard(session, actual, "authorize")
                if actual.state not in {OperationState.PREPARED, OperationState.REJECTED}:
                    raise StateError("No se puede descartar una acción ya autorizada/terminada.")
                if actual.state == OperationState.PREPARED:
                    repo.transition(row, OperationState.REJECTED, _now())
                record(session, actual)
            return {
                "reply": "Descartado. No he cambiado ningún registro.",
                "action_result": "discarded",
                "source": "local",
            }
        capture.authorize(
            self.context.principal,
            operation_uuid,
            channel=self.context.identity.namespace,
            approved_hash=approved_hash,
            approved_revision=approved_revision,
            approval_recorder=record,
        )
        checkpoint("authorization_committed")
        return self.execute(operation_uuid)

    def execute(self, operation_uuid):
        operation = self.operations.recover(self.context.principal, operation_uuid)
        capture = capture_for(self.business_id, operation.request.command_type)
        capture.operations._channel_guard = self._guard
        done = capture.execute(self.context.principal, operation_uuid)
        checkpoint("effect_committed")
        return self.response(done)

    def response(self, operation):
        with self.operations._transaction(self.context.principal, write=False) as (session, _):
            link = self._link(session, operation.operation_uuid)
        return self._response(operation, link)

    def _response(self, operation, link):
        completed = operation.state == OperationState.COMMITTED
        response = {
            "operation_uuid": operation.operation_uuid,
            "request_hash": operation.request.request_hash,
            "revision": str(operation.request.expected_revision)
            if operation.request.expected_revision is not None
            else None,
            "source": "local",
            "confirmation_required": operation.state == OperationState.PREPARED,
            "command": operation.request.command_type.value,
            "reply": ("Hecho.\n" if completed else "") + link["preview"],
        }
        if operation.state in {OperationState.REJECTED, OperationState.CANCELLED}:
            response["reply"] = "Propuesta descartada. No he cambiado ningún registro."
            response["action_result"] = "discarded"
        elif not completed:
            response["reply"] += (
                "\n\nResponde citando esta propuesta con SÍ para confirmar o NO para descartar."
                if self.context.actor.startswith("wa:")
                else "\n\nResponde SÍ para confirmar esta propuesta o NO para descartarla."
            )
        else:
            response["action_result"] = "completed"
            response["result"] = dict(operation.result)
            if operation.request.parameters.get("document_id") is not None:
                response["document_id"] = operation.request.parameters["document_id"]
            if operation.request.command_type in {
                CommandType.INVOICE_ISSUE,
                CommandType.INVOICE_RECTIFY,
            }:
                response["invoice_ids"] = [operation.result["invoice_id"]]
        return response
