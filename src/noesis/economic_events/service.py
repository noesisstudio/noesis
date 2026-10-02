"""Incorporación de hechos: sin productores, cálculos, IA ni commit propio."""

from datetime import datetime, timezone
import hashlib
import json
import re

from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import (
    AccessDenied,
    ConflictError,
    OperationState,
    StateError,
    positive_id,
    uuid_text,
)
from noesis.financial_operations.repository import OperationsRepository
from noesis.financial_operations.service import FinancialOperations
from .contracts import EconomicEvent, RelationType
from .persistence import StoredEvent
from .repository import EventsRepository
from .schema import SOURCES

COMMANDS = {
    "invoice.issue": {"invoice.issued"},
    "invoice.rectify": {"invoice.rectified"},
    "customer_payment.record": {"customer_payment.received"},
    "supplier_invoice.confirm": {"supplier_invoice.confirmed"},
    "supplier_invoice.correct": {"supplier_invoice.corrected"},
    "supplier_invoice.void": {"supplier_invoice.voided"},
    "expense.confirm": {"expense.confirmed"},
    "expense.void": {"expense.voided"},
    "bank_transaction.import": {"bank_transaction.imported"},
    "bank_transaction.match": {"bank_transaction.matched", "customer_payment.received"},
    "invoice.fiscal_cancel": {"invoice.fiscal_cancellation_registered"},
}


class EconomicEvents:
    def __init__(self, session, business_id):
        if not isinstance(session, FinancialSession):
            raise TypeError("FinancialSession prestada requerida.")
        self.session, self.business_id = session, positive_id(business_id)
        self.repo = EventsRepository(session, self.business_id)
        self.permissions = FinancialOperations(self.business_id)

    def _operation(self, principal, uuid, origin):
        repository = OperationsRepository(self.session, self.business_id)
        row = repository.load(uuid, principal.user_id)
        auth = (
            repository.authorization(row["authorization_uuid"])
            if row["authorization_uuid"] is not None
            else None
        )
        if not auth:
            raise AccessDenied("Autorización durable requerida.")
        if origin == "live":
            if (
                row["state"] not in (OperationState.APPROVED.value, OperationState.COMMITTED.value)
                or auth["kind"] not in ("human_confirmation", "mandate")
                or auth["actor_user_id"] != principal.user_id
                or auth["actor_session_version"] != principal.session_version
            ):
                raise AccessDenied("Operación live no autorizada.")
            if auth["mandate_uuid"] is not None:
                from noesis.financial_operations.contracts import FinancialRequest

                self.permissions._mandate(
                    self.session,
                    repository,
                    auth["mandate_uuid"],
                    principal,
                    FinancialRequest.from_canonical(row["request_canonical"]),
                )
        elif auth["kind"] != "historical_unknown" or auth["recorded_by"] != principal.user_id:
            raise AccessDenied("Histórico requiere procedencia sin aprobación humana inventada.")
        return row, uuid_text(auth["authorization_uuid"])

    def read(self, principal, event_uuid):
        self.permissions._permission(self.session, principal, write=False)
        row = self.repo.load(uuid_text(event_uuid))
        if not row:
            raise AccessDenied("Evento no disponible.")
        if row["operation_uuid"] is not None:
            owner = self.session.execute(
                "SELECT created_by FROM financial_operations WHERE business_id=? AND operation_uuid=?",
                (self.business_id, row["operation_uuid"]),
            ).fetchone()
            if not owner or owner["created_by"] != principal.user_id:
                raise AccessDenied("Evento no disponible.")
        return self._decode(row)

    def _decode(self, row):
        stored = StoredEvent.from_row(row)
        actual = {
            (r["relation_type"], str(r["target_event_uuid"]))
            for r in self.repo.links(stored.event.event_id)
        }
        expected = {(r.kind.value, str(r.target_event_id)) for r in stored.event.relations}
        if actual != expected:
            raise ValueError("Links persistidos incoherentes; no reparar.")
        return stored

    def append(self, principal, event, **kwargs):
        # SAVEPOINT nunca debe ser la transacción exterior de SQLite (RELEASE la confirmaría).
        if self.session.dialect == "sqlite" and not self.session._connection.raw.in_transaction:
            raise StateError("El llamador debe abrir la transacción SQLite antes de incorporar.")
        self.permissions._permission(self.session, principal, write=True)
        self.session.execute("SAVEPOINT economic_append")
        try:
            result = self._append(principal, event, **kwargs)
        except BaseException:
            self.session.execute("ROLLBACK TO SAVEPOINT economic_append")
            self.session.execute("RELEASE SAVEPOINT economic_append")
            raise
        self.session.execute("RELEASE SAVEPOINT economic_append")
        return result

    def _append(
        self,
        principal,
        event,
        *,
        operation_uuid,
        event_slot,
        origin="live",
        historical_batch_uuid=None,
        provenance="server",
        date_provenance="source",
        revision_reader,
        expected_hash=None,
    ):
        self.permissions._permission(self.session, principal, write=True)
        if not isinstance(event, EconomicEvent) or event.business_id != self.business_id:
            raise ValueError("Contrato tipado del mismo negocio requerido.")
        if not isinstance(event_slot, str) or not re.fullmatch(
            r"[a-z][a-z0-9_.-]{0,63}", event_slot
        ):
            raise ValueError("Slot estable requerido.")
        for value in (provenance, date_provenance):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError("Procedencia explícita requerida.")
        if origin not in ("live", "historical"):
            raise ValueError("Origen cerrado requerido.")
        if origin == "historical":
            historical_batch_uuid = uuid_text(historical_batch_uuid)
        elif historical_batch_uuid is not None:
            raise ValueError("Batch solo histórico.")
        if expected_hash is not None and expected_hash != event.content_hash:
            raise ValueError("Hash del sobre no coincide.")
        operation_uuid = None if operation_uuid is None else uuid_text(operation_uuid)
        authorization_uuid = None
        if operation_uuid is not None:
            operation, authorization_uuid = self._operation(principal, operation_uuid, origin)
            if event.event_type.value not in COMMANDS[operation["command_type"]]:
                raise StateError("Comando incompatible con el evento.")
        elif origin == "live":
            raise AccessDenied("Live requiere operación y autorización.")
        key = hashlib.sha256(
            json.dumps(
                [operation_uuid, event_slot]
                if operation_uuid is not None
                else [
                    event.source_type.value,
                    event.source_id,
                    event.source_revision,
                    event.event_type.value,
                    event_slot,
                ],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        precision = (
            "instant"
            if event.occurred_at is not None
            else "day"
            if event.economic_date is not None
            else "unknown"
        )
        metadata = dict(
            operation_uuid=operation_uuid,
            event_slot=event_slot,
            authorization_uuid=authorization_uuid,
            origin=origin,
            historical_batch_uuid=historical_batch_uuid,
            provenance=provenance,
            date_precision=precision,
            date_provenance=date_provenance,
            idempotency_key=key,
        )
        from noesis.core.locks import lock_business
        lock_business(self.session, self.business_id)
        self.repo.lock_business()
        existing = self.repo.find(event, operation_uuid, event_slot, key)
        if existing:
            if len(existing) != 1:
                raise ConflictError("Identidades de evento incompatibles.")
            stored = self.read(principal, existing[0]["event_uuid"])
            if stored.event.content_hash != event.content_hash or any(
                getattr(stored, k) != v for k, v in metadata.items()
            ):
                raise ConflictError("Identidad/revisión ya incorporada con otro contenido.")
            return stored
        table, _ = SOURCES[event.source_type.value]
        lock = " FOR SHARE" if self.session.dialect == "postgres" else ""
        source = self.session.execute(
            f"SELECT id FROM {table} WHERE business_id=? AND id=?" + lock,
            (self.business_id, event.source_id),
        ).fetchone()
        if not source:
            raise ValueError("Origen ausente o de otra empresa.")
        if not callable(revision_reader):
            raise TypeError("Lector confiable de revisión requerido.")
        revision = revision_reader(self.session, event.source_type, event.source_id)
        if type(revision) is not int or revision != event.source_revision:
            raise StateError("Revisión de origen antigua/desconocida.")
        for relation in event.relations:
            target = self.read(principal, relation.target_event_id).event
            if target.event_type != relation.target_event_type:
                raise ValueError("Tipo real del target incompatible.")
            if relation.kind in (RelationType.CORRECTS, RelationType.VOIDS) and (
                target.source_type != event.source_type
                or target.source_id != event.source_id
                or target.source_revision >= event.source_revision
            ):
                raise ValueError("Corrección/retirada requiere mismo origen y revisión posterior.")
        self._references(event)
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        metadata.update(business_sequence=self.repo.next_sequence(), recorded_at=now)
        for relation in event.relations:
            self.repo.insert_link(event.event_id, relation, now)
        return self.repo.insert(event, metadata)

    def _references(self, event):
        # Solo IDs: no leer/normalizar importes legacy ni recalcular snapshots.
        if event.source_type.value in ("invoice_payment", "invoice_cancellation_record"):
            table, _ = SOURCES[event.source_type.value]
            row = self.session.execute(
                f"SELECT invoice_id FROM {table} WHERE business_id=? AND id=?",
                (self.business_id, event.source_id),
            ).fetchone()
            if row["invoice_id"] != event.payload["invoice_id"]:
                raise ValueError("Invoice ID no concuerda con el origen.")
            targets = [
                r
                for r in event.relations
                if r.target_event_type.value in ("invoice.issued", "invoice.rectified")
            ]
            if any(
                self.repo.load(r.target_event_id)["source_id"] != row["invoice_id"] for r in targets
            ):
                raise ValueError("Relación a otra factura.")
        if event.event_type.value == "bank_transaction.matched":
            row = self.session.execute(
                "SELECT id FROM invoice_payments WHERE business_id=? AND id=?",
                (self.business_id, event.payload["invoice_payment_id"]),
            ).fetchone()
            if not row:
                raise ValueError("Cobro de otra empresa o inexistente.")
            for relation in event.relations:
                target = self.repo.load(relation.target_event_id)
                expected = (
                    event.payload["invoice_payment_id"]
                    if relation.kind == RelationType.MATCHES
                    else event.source_id
                )
                if target["source_id"] != expected:
                    raise ValueError("Conciliación enlaza otro origen.")
