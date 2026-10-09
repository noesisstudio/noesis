"""Anulación fiscal local atómica: evidencia, nunca reversión económica."""

from datetime import date, datetime, timezone
from uuid import UUID, uuid5

from noesis import config, db
from noesis.core.locks import lock_fiscal_chain
from noesis.core.money import parse_money
from noesis.economic_events.contracts import (
    EconomicEvent, EventRelation, EventType, RelationType, SourceType,
)
from noesis.economic_events.service import EconomicEvents
from noesis.financial_antecedents.contracts import Purpose, digest
from noesis.financial_antecedents.resolver import AntecedentResolver
from noesis.financial_history.reconciliation_verifier import storage_hash
from noesis.financial_operations.contracts import (
    AuthorizationKind, CommandType, EntryIdentity, FinancialRequest,
    OperationState, StateError, canonical_json, uuid_text,
)
from noesis.financial_operations.service import FinancialOperations, _now
from noesis.financial_writers import invoices
from noesis.financial_writers.boundary import revision_reader
from noesis.invoice_capture.service import PRODUCER_CONFIG

EVENT_SLOT = "primary"
EVENT_NAME = "invoice.fiscal_cancellation.primary.v1"
PARAMETERS = frozenset({
    "antecedent_resolution_uuid", "resolution_content_hash", "resolution_context_hash",
    "invoice_event_uuid", "invoice_event_content_hash", "invoice_event_record_hash",
    "fiscal_record_id", "fiscal_record_hash", "fiscal_context_hash", "configuration_hash",
})


def reason_text(value):
    if type(value) is not str or value != value.strip() or not 5 <= len(value) <= 1000:
        raise ValueError("Motivo explícito de 5 a 1.000 caracteres sin espacios exteriores.")
    return value


class FiscalCancellationCapture:
    """API interna revisar → preparar → confirmar humanamente → ejecutar."""

    def __init__(self, business_id):
        self.operations = FinancialOperations(business_id)
        self.business_id = self.operations.business_id

    def _context(self, session, principal, resolution):
        resolver = AntecedentResolver(session, self.business_id)
        saved = resolver.verify_resolution(principal, resolution)
        proof = saved["result"]
        if (proof["outcome"] != "resolved" or proof["quality"] != "verified_fact"
                or proof["origin"] != "live"
                or proof["request"]["purpose"] != Purpose.FISCAL_CANCEL.value
                or proof["request"]["antecedent"]["source_type"] != "invoice"
                or proof["proof"]["fiscal_evidence"]["state"] != "known"):
            raise StateError("Antecedente fiscal live verificado y resolved requerido.")
        invoice_id = proof["request"]["antecedent"]["source_id"]
        conn = session.borrowed_connection
        share = " FOR SHARE" if session.dialect == "postgres" else ""
        record = conn.execute_exact(
            "SELECT * FROM invoice_records WHERE business_id=? AND invoice_id=?" + share,
            (self.business_id, invoice_id),
        ).fetchone()
        outbox = conn.execute_exact(
            "SELECT * FROM verifactu_outbox WHERE business_id=? AND invoice_id=?" + share,
            (self.business_id, invoice_id),
        ).fetchone()
        business = conn.execute_exact(
            "SELECT nif,verifactu_enabled FROM businesses WHERE id=?" + share,
            (self.business_id,),
        ).fetchone()
        if (not record or not outbox or outbox["record_id"] != record["id"]
                or outbox["status"] not in ("aceptado", "aceptado_con_errores")
                or not business["verifactu_enabled"]):
            raise StateError("Alta fiscal válida y aceptada localmente requerida.")
        if session.execute(
            "SELECT 1 FROM invoice_cancellation_records WHERE business_id=? AND invoice_id=?",
            (self.business_id, invoice_id),
        ).fetchone():
            raise StateError("Existe una anulación previa; no adoptarla como otra operación live.")
        original = EconomicEvents(session, self.business_id).read(principal, proof["event_uuid"])
        event = original.event
        if (original.origin != "live" or event.payload_version != 2
                or event.source_id != invoice_id or event.source_type != SourceType.INVOICE
                or event.event_type not in (EventType.INVOICE_ISSUED, EventType.INVOICE_RECTIFIED)
                or event.amount is None or event.currency.value != "EUR"
                or proof["amount"] != format(event.amount, ".2f")
                or event.payload["evidence"]["fiscal_record"]["id"] != record["id"]
                or event.payload["evidence"]["fiscal_record"]["record_hash"] != record["record_hash"]):
            raise StateError("Evento original exacto y evidencia fiscal incoherentes.")
        # Se usa el verificador y lock existentes, nunca un algoritmo fiscal nuevo.
        lock_fiscal_chain(session, self.business_id, record["issuer_nif"])
        chain = db._fiscal_record_rows(conn, self.business_id, record["issuer_nif"])
        if not db._verify_invoice_record_rows(chain)["valid"]:
            raise StateError("Cadena fiscal inválida.")
        parameters = dict(
            antecedent_resolution_uuid=saved["resolution_uuid"],
            resolution_content_hash=saved["content_hash"],
            resolution_context_hash=proof["context_hash"],
            invoice_event_uuid=str(event.event_id),
            invoice_event_content_hash=event.content_hash,
            invoice_event_record_hash=original.record_hash,
            fiscal_record_id=record["id"], fiscal_record_hash=record["record_hash"],
            fiscal_context_hash=digest({"record": storage_hash(record),
                                       "outbox": storage_hash(outbox),
                                       "chain": [storage_hash(row) for row in chain]}),
            configuration_hash=digest({
                "producer": {k: getattr(config, k) for k in PRODUCER_CONFIG},
                "max_attempts": config.VERIFACTU_MAX_ATTEMPTS,
                "business": dict(business),
            }),
        )
        return saved, original, parameters

    def review(self, principal, resolution, *, reason):
        reason = reason_text(reason)
        with self.operations._transaction(principal) as (session, _):
            saved, original, parameters = self._context(session, principal, resolution)
            return FinancialRequest(
                CommandType.INVOICE_FISCAL_CANCEL, original.event.source_id, None,
                date.today(), saved["result"]["request"]["antecedent"]["revision"],
                reason, parameters,
            )

    def _contract(self, session, request):
        if (not isinstance(request, FinancialRequest)
                or request.command_type != CommandType.INVOICE_FISCAL_CANCEL
                or request.amount is not None or request.currency.value != "EUR"
                or request.target_id is None or request.expected_revision is None
                or request.effective_on is None or set(request.parameters) != PARAMETERS):
            raise StateError("Request fiscal cerrado y no monetario requerido.")
        reason_text(request.reason)
        for field in ("antecedent_resolution_uuid", "invoice_event_uuid"):
            if uuid_text(request.parameters[field]) != request.parameters[field]:
                raise StateError("Identidad canónica requerida.")
        for field in PARAMETERS - {"antecedent_resolution_uuid", "invoice_event_uuid", "fiscal_record_id"}:
            value = request.parameters[field]
            alphabet = "0123456789ABCDEFabcdef" if field == "fiscal_record_hash" else "0123456789abcdef"
            if type(value) is not str or len(value) != 64 or any(c not in alphabet for c in value):
                raise StateError("Hash fiscal exacto requerido.")
        from noesis.financial_operations.contracts import positive_id
        positive_id(request.parameters["fiscal_record_id"])

    def _validate(self, session, request, principal):
        self._contract(session, request)
        saved = AntecedentResolver(session, self.business_id).read(
            principal, request.parameters["antecedent_resolution_uuid"]
        )
        verified, original, parameters = self._context(session, principal, saved)
        if (request.target_id != original.event.source_id
                or request.effective_on != date.today().isoformat()
                or request.expected_revision != verified["result"]["request"]["antecedent"]["revision"]
                or canonical_json(parameters) != canonical_json(request.parameters)):
            raise StateError("Factura, resolución, evidencia fiscal o configuración cambiaron.")
        return request.expected_revision

    def prepare(self, principal, identity, request):
        if not isinstance(identity, EntryIdentity):
            raise TypeError("EntryIdentity de servidor requerida.")
        with self.operations._transaction(principal) as (session, repo):
            self._contract(session, request)
            operation = repo.prepare(principal, identity, request, _now())
            if operation.state == OperationState.PREPARED:
                self._validate(session, request, principal)
            return operation

    def authorize(self, principal, operation_uuid, *, channel, approved_hash, approved_revision,
                  kind=AuthorizationKind.HUMAN, mandate_uuid=None):
        if AuthorizationKind(kind) != AuthorizationKind.HUMAN or mandate_uuid is not None:
            raise StateError("C exige exclusivamente human_confirmation.")

        def confirmed(session, operation):
            authority = session.execute(
                "SELECT kind,approved_request_hash,approved_revision,actor_user_id,actor_session_version "
                "FROM financial_authorizations WHERE business_id=? AND authorization_uuid=?",
                (self.business_id, operation.authorization_uuid),
            ).fetchone()
            if (not authority or authority["kind"] != AuthorizationKind.HUMAN.value
                    or authority["approved_request_hash"] != operation.request.request_hash
                    or authority["approved_revision"] != operation.request.expected_revision
                    or authority["actor_user_id"] != principal.user_id):
                raise StateError("La autorización durable exacta debe ser humana.")
            if operation.state != OperationState.COMMITTED:
                if authority["actor_session_version"] != principal.session_version:
                    raise StateError("Confirmación humana de otra sesión.")
                self._validate(session, operation.request, principal)

        return self.operations.authorize(
            principal, operation_uuid, channel=channel, approved_hash=approved_hash,
            approved_revision=approved_revision, kind=AuthorizationKind.HUMAN,
            revision_reader=lambda s, r: self._validate(s, r, principal),
            request_validator=self._contract,
            approval_recorder=confirmed,
        )

    def execute(self, principal, operation_uuid):
        operation_uuid = uuid_text(operation_uuid)

        def contract(session, request):
            self._contract(session, request)
            row = session.execute(
                "SELECT a.kind FROM financial_operations o JOIN financial_authorizations a "
                "ON a.business_id=o.business_id AND a.authorization_uuid=o.authorization_uuid "
                "WHERE o.business_id=? AND o.operation_uuid=?", (self.business_id, operation_uuid),
            ).fetchone()
            if row and row["kind"] != AuthorizationKind.HUMAN.value:
                raise StateError("C no admite mandatos ni autoridad histórica.")

        def effect(session, request):
            # Se revalida de nuevo dentro de la TX exterior antes del writer.
            self._validate(session, request, principal)
            original = EconomicEvents(session, self.business_id).read(
                principal, request.parameters["invoice_event_uuid"]
            )
            writer = invoices.create_invoice_cancellation_record(
                session, request.target_id, self.business_id, reason=request.reason,
                expected_revision=request.expected_revision,
            )
            source = writer.snapshots[0]
            if source.source_type != "invoice_cancellation_record":
                raise StateError("Snapshot fiscal real requerido.")
            event_id = uuid5(UUID(operation_uuid), EVENT_NAME)
            registered_on = str(source.data["generated_at"])[:10]
            if registered_on != request.effective_on:
                raise StateError("Fecha fiscal distinta de la aprobada.")
            # Total exclusivamente del evento v2 verificado, jamás del total legacy.
            original_total = parse_money(original.event.amount)
            values = dict(
                business_id=self.business_id, invoice_id=request.target_id,
                cancellation_record_id=source.source_id,
                antecedent_resolution_uuid=request.parameters["antecedent_resolution_uuid"],
                original_invoice_event_uuid=str(original.event.event_id),
                original_event_type=original.event.event_type.value,
                event_uuid=str(event_id), operation_uuid=operation_uuid,
                event_type=EventType.INVOICE_FISCAL_CANCELLATION_REGISTERED.value,
                source_revision=source.revision, source_fingerprint=source.fingerprint,
                resolution_content_hash=request.parameters["resolution_content_hash"],
                resolution_context_hash=request.parameters["resolution_context_hash"],
            )
            session.execute(
                "INSERT INTO invoice_fiscal_cancellation_coverage (" + ",".join(values)
                + ") VALUES (" + ",".join("?" for _ in values) + ")", tuple(values.values()),
            )
            event = EconomicEvent(
                event_id, self.business_id, EventType.INVOICE_FISCAL_CANCELLATION_REGISTERED,
                SourceType.INVOICE_CANCELLATION_RECORD, source.source_id, source.revision,
                datetime.fromisoformat(str(source.data["generated_at"])), datetime.now(timezone.utc),
                {"invoice_id": request.target_id, "invoice_number": source.data["invoice_number"],
                 "original_total": original_total, "registered_on": registered_on, "reason": request.reason},
                relations=(EventRelation(RelationType.EVIDENCE_FOR, original.event.event_id,
                                         original.event.event_type, self.business_id),),
            )
            stored = EconomicEvents(session, self.business_id).append(
                principal, event, operation_uuid=operation_uuid, event_slot=EVENT_SLOT,
                revision_reader=revision_reader(self.business_id),
                provenance="fiscal_cancellation_capture.v1:" + source.fingerprint,
                date_provenance="fiscal_record.generated_at",
            )
            return dict(
                invoice_id=request.target_id, cancellation_record_id=source.source_id,
                antecedent_resolution_uuid=request.parameters["antecedent_resolution_uuid"],
                original_invoice_event_uuid=str(original.event.event_id),
                event_uuid=str(event_id), event_type=event.event_type.value,
                content_hash=stored.event.content_hash, source_revision=source.revision,
                source_fingerprint=source.fingerprint, original_total=format(original_total, ".2f"),
                amount=None, currency="EUR", captured=True,
            )

        return self.operations.execute(
            principal, operation_uuid, effect,
            revision_reader=lambda s, r: self._validate(s, r, principal), request_validator=contract,
        )
