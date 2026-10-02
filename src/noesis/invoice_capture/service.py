"""Un único productor de emisión sobre el motor prestado existente."""

from datetime import datetime, timezone
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
import hashlib
import json
from functools import wraps
from uuid import UUID, uuid5

from noesis import config, db
from noesis.core.locks import lock_business
from noesis.economic_events.contracts import EconomicEvent, EventRelation, EventType, RelationType, SourceType
from noesis.economic_events.service import EconomicEvents
from noesis.financial_operations.contracts import (
    CommandType, ConflictError, EntryIdentity, OperationState, StateError, canonical_json,
)
from noesis.financial_operations.service import FinancialOperations, _now
from noesis.financial_operations.contracts import FinancialRequest
from noesis.financial_writers import invoices
from noesis.financial_writers.boundary import _json, freeze, observe, revision_reader, snapshot

PRODUCER_CONFIG = (
    "VERIFACTU_PRODUCER_NAME", "VERIFACTU_PRODUCER_NIF", "VERIFACTU_SYSTEM_NAME",
    "VERIFACTU_SYSTEM_ID", "VERIFACTU_SYSTEM_VERSION", "VERIFACTU_INSTALLATION_PREFIX",
    "VERIFACTU_RECORD_VERSION", "VERIFACTU_HASH_ALGORITHM", "VERIFACTU_HASH_TYPE",
    "VERIFACTU_HASH_SPEC_VERSION",
)


def _decimal_context(method):
    @wraps(method)
    def call(*args, **kwargs):
        with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
            return method(*args, **kwargs)
    return call


def fingerprint(value):
    text = json.dumps(_json(freeze(value)), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _cents(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class InvoiceCapture:
    """API de servidor: revisar → preparar → autorizar → ejecutar; sin endpoint IA."""

    def __init__(self, business_id):
        self.operations = FinancialOperations(business_id)
        self.business_id = self.operations.business_id

    def _context(self, session, invoice_id, term):
        conn = session.borrowed_connection
        lock_business(session, self.business_id)
        source = snapshot(conn, self.business_id, "invoice", invoice_id)
        if not source or source.data["status"] != "borrador" or source.data["number"]:
            raise StateError("La captura requiere un borrador; no reconstruir históricos.")
        if source.data.get("currency") != "EUR" or source.data.get("source") == "importada":
            raise StateError("Origen no admitido para emisión capturada.")
        share = " FOR SHARE" if session.dialect == "postgres" else ""
        client = conn.execute_exact("SELECT * FROM clients WHERE business_id=? AND id=?" + share,
                                    (self.business_id, source.data["client_id"])).fetchone()
        business = conn.execute_exact("SELECT * FROM businesses WHERE id=?" + share,
                                      (self.business_id,)).fetchone()
        series = conn.execute_exact("SELECT * FROM invoice_series WHERE business_id=? AND id=?" + share,
                                    (self.business_id, source.data["series_id"])).fetchone()
        if not client or not business or not series or not series["active"]:
            raise StateError("Datos fiscales/serie incompletos.")
        if term is None:
            configured = business.get("default_payment_term_days")
            term = int(15 if configured is None else configured)
        if type(term) is not int or not 0 <= term <= 365:
            raise ValueError("Plazo explícito entero entre 0 y 365 requerido.")
        from noesis.migrations import _IMMUTABLE_INVOICE_FIELDS
        from noesis.db import _DOCUMENT_PROFILE_FIELDS
        context = {
            "invoice": {k: source.data.get(k) for k in _IMMUTABLE_INVOICE_FIELDS},
            "lines": [{k: v for k, v in line.items() if k != "business_id"} for line in source.data["lines"]],
            "client": {k: client.get(k) for k in ("id", "name", "nif", "address")},
            "issuer": {k: business.get(k) for k in ("name", "nif", "address", "verifactu_enabled", "default_payment_term_days")},
            "profile_hash": fingerprint({k: business.get(k) for k in _DOCUMENT_PROFILE_FIELDS}),
            "series": {k: series.get(k) for k in ("id", "code", "document_type", "active", "prefix_template", "padding")},
            "producer": {k: getattr(config, k) for k in PRODUCER_CONFIG},
            "term": term,
        }
        return source, freeze(context), term

    @_decimal_context
    def review(self, principal, invoice_id, *, payment_term_days=None):
        with self.operations._transaction(principal) as (session, _):
            source, context, term = self._context(session, invoice_id, payment_term_days)
            kind = source.data["invoice_type"]
            command = CommandType.INVOICE_RECTIFY if kind.startswith("R") else CommandType.INVOICE_ISSUE
            original = self._original(session, principal, source) if kind.startswith("R") else None
            return FinancialRequest(command, invoice_id, source.amounts["total"], db.date.today().isoformat(),
                source.revision, source.data.get("rectification_reason"), {
                    "approval_fingerprint": fingerprint(context), "approved_document": _json(context),
                    "payment_term_days": term, "original_event": str(original.event.event_id) if original else None,
                    "original_fingerprint": original.event.payload["evidence"]["source_fingerprint"] if original else None,
                })

    def _contract(self, session, request):
        if request.command_type not in (CommandType.INVOICE_ISSUE, CommandType.INVOICE_RECTIFY):
            raise StateError("Comando incompatible con emisión capturada.")
        required = {"approval_fingerprint", "approved_document", "payment_term_days", "original_event", "original_fingerprint"}
        if set(request.parameters) != required or request.target_id is None or request.expected_revision is None:
            raise StateError("Request de emisión completo requerido.")

    @_decimal_context
    def _validate(self, session, request):
        self._contract(session, request)
        source, context, _ = self._context(session, request.target_id, request.parameters["payment_term_days"])
        command = CommandType.INVOICE_RECTIFY if source.data["invoice_type"].startswith("R") else CommandType.INVOICE_ISSUE
        if (request.command_type != command or request.amount != source.amounts["total"]
                or request.effective_on != db.date.today().isoformat()
                or request.reason != source.data.get("rectification_reason")
                or request.parameters["approval_fingerprint"] != fingerprint(context)
                or canonical_json(request.parameters["approved_document"]) != canonical_json(_json(context))):
            raise StateError("La factura, el cliente o los datos fiscales cambiaron desde la revisión.")
        if command == CommandType.INVOICE_ISSUE and (request.parameters["original_event"] is not None or request.parameters["original_fingerprint"] is not None):
            raise StateError("Una emisión ordinaria no rectifica otro evento.")
        return source.revision

    def prepare(self, principal, identity, request, *, preparation_recorder=None):
        if not isinstance(identity, EntryIdentity) or not isinstance(request, FinancialRequest):
            raise TypeError("Identidad autenticada y request de revisión requeridos.")
        with self.operations._transaction(principal) as (session, repo):
            self._contract(session, request)
            operation = repo.prepare(principal, identity, request, _now())
            if operation.state == OperationState.PREPARED:
                self.operations._revision(session, request, self._validate)
            if preparation_recorder is not None:
                preparation_recorder(session, operation)
            return operation

    def authorize(self, principal, operation_uuid, **approval):
        return self.operations.authorize(principal, operation_uuid, revision_reader=self._validate, **approval)

    def _original(self, session, principal, source):
        original_id = source.data.get("rectifies_invoice_id")
        row = session.execute("SELECT event_uuid FROM invoice_economic_coverage WHERE business_id=? AND invoice_id=?",
                              (self.business_id, original_id)).fetchone()
        if not row:
            raise StateError("El original carece de evento capturado válido; no crear historia implícita.")
        stored = EconomicEvents(session, self.business_id).read(principal, row["event_uuid"])
        original = snapshot(session.borrowed_connection, self.business_id, "invoice", original_id)
        if (not original or original.data["status"] not in {"enviada", "parcial", "cobrada"}
                or stored.event.source_id != original_id
                or stored.event.event_type not in (EventType.INVOICE_ISSUED, EventType.INVOICE_RECTIFIED)
                or stored.event.payload_version != 2
                or stored.event.payload["evidence"]["source_fingerprint"] != original.fingerprint):
            raise StateError("Evidencia del original incoherente.")
        return stored

    @_decimal_context
    def execute(self, principal, operation_uuid):
        observations = []

        def effect(session, request):
            # Operations ya bloqueó autorización, operación y validó la revisión completa.
            source = snapshot(session.borrowed_connection, self.business_id, "invoice", request.target_id)
            original = self._original(session, principal, source) if request.command_type == CommandType.INVOICE_RECTIFY else None
            if original and (str(original.event.event_id) != request.parameters["original_event"]
                             or original.event.payload["evidence"]["source_fingerprint"] != request.parameters["original_fingerprint"]):
                raise ConflictError("El original aprobado no coincide.")
            typ = EventType.INVOICE_RECTIFIED if original else EventType.INVOICE_ISSUED
            event_id = uuid5(UUID(str(operation_uuid)), "invoice.primary.v2")
            session.execute("INSERT INTO invoice_economic_coverage (business_id,invoice_id,event_uuid,event_type,operation_uuid) VALUES (?,?,?,?,?)",
                            (self.business_id, request.target_id, str(event_id), typ.value, str(operation_uuid)))
            writer = invoices.issue_invoice(session, request.target_id, self.business_id,
                request.parameters["payment_term_days"], expected_revision=request.expected_revision)
            captured = writer.snapshots[0]
            payload = self._payload(session, writer)
            if payload["issued_on"] != request.effective_on:
                raise StateError("La fecha de emisión difiere de la aprobada.")
            relations = (EventRelation(RelationType.RECTIFIES, original.event.event_id,
                                       original.event.event_type, self.business_id),) if original else ()
            event = EconomicEvent(event_id, self.business_id, typ, SourceType.INVOICE,
                captured.source_id, captured.revision, None, datetime.now(timezone.utc), payload,
                payload_version=2, relations=relations)
            stored = EconomicEvents(session, self.business_id).append(principal, event,
                operation_uuid=operation_uuid, event_slot="primary", revision_reader=revision_reader(self.business_id),
                provenance="invoice_capture.v2:legacy_binary_storage", date_provenance="frozen_invoice")
            observations.append(writer)
            return {"invoice_id": captured.source_id, "number": payload["invoice_number"],
                    "event_uuid": str(stored.event.event_id), "event_type": typ.value,
                    "content_hash": stored.event.content_hash, "source_fingerprint": captured.fingerprint,
                    "amount": payload["total"], "currency": "EUR", "captured": True}

        result = self.operations.execute(principal, operation_uuid, effect, revision_reader=self._validate,
                                         request_validator=self._contract)
        for writer in observations:
            try:
                observe(writer)
            except Exception:
                # Telemetría posterior al commit, sin invalidar ni repetir el efecto.
                import logging
                logging.getLogger(__name__).exception("Observación de emisión no disponible tras commit")
        return result

    def _payload(self, session, writer):
        with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
            source = writer.snapshots[0]
            row = source.data
            totals = db._invoice_totals(row["lines"], row["irpf_rate"], _exact=True)
            for key in ("base", "vat_amount", "irpf_amount", "total"):
                if _cents(totals[key]) != source.amounts[key]:
                    raise StateError("Diferencia de céntimos entre evento y documento; revertir.")
            if not writer.exact_inputs or writer.input_provenance != "exact_input":
                raise StateError("Frontera exacta del writer requerida.")
            # prepared_values conserva cálculos adaptados si el motor escribe importes.
            # Emisión congela el borrador existente; su procedencia sigue siendo binaria.
            for _, prepared in writer.prepared_values:
                if any(not value.is_finite() for _, value in prepared):
                    raise StateError("Preparación monetaria no finita.")
            series = session.execute("SELECT id,code,document_type FROM invoice_series WHERE business_id=? AND id=?",
                                     (self.business_id, row["series_id"])).fetchone()
            profile, fiscal = row["document_profile"], row["fiscal_record"]
            from noesis.economic_events.invoice_payload import FISCAL, LINE
            evidence = {
                "invoice_id": source.source_id, "client_id": row["client_id"], "series": series,
                "issuer": {k: row["issuer_" + k] for k in ("name", "nif", "address")},
                "recipient": {k: row["recipient_" + k] or None for k in ("name", "nif", "address")},
                "lines": [{k: line[k] for k in {f.name for f in LINE} | {"quantity", "unit_price", "discount_rate", "vat_rate"}} for line in row["lines"]],
                "irpf_rate": row["irpf_rate"],
                "document_profile": {"id": profile["id"], "version": profile["version"], "content_hash": fingerprint(profile)},
                "fiscal_record": {f.name: _cents(fiscal[f.name]) if f.kind == "money" else fiscal[f.name] for f in FISCAL} if fiscal else None,
                "source_fingerprint": source.fingerprint, "money_provenance": source.money_provenance,
            }
            payload = {"invoice_number": row["number"], "invoice_kind": row["invoice_type"],
                "issued_on": str(row["issued_at"])[:10], "operation_on": str(row["operation_date"])[:10] if row["operation_date"] else None,
                "due_on": str(row["due_date"])[:10], **dict(source.amounts), "evidence": evidence}
            if row["invoice_type"].startswith("R"):
                payload.update(reason=row["rectification_reason"], rectification_method=row["rectification_type"])
            return payload
