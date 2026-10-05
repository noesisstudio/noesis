"""Registro de incorporación sobre FinancialSession prestada, sin commit propio."""

from uuid import UUID, uuid5

from noesis.financial_operations.contracts import CommandType, FinancialRequest
from .repository import canonical, stamp

COMMANDS = dict(
    zip(
        (
            "invoice.issued",
            "invoice.rectified",
            "customer_payment.received",
            "supplier_invoice.confirmed",
            "supplier_invoice.corrected",
            "supplier_invoice.voided",
            "expense.confirmed",
            "expense.voided",
            "bank_transaction.imported",
            "bank_transaction.matched",
            "invoice.fiscal_cancellation_registered",
        ),
        CommandType,
        strict=True,
    )
)


class ImportRepository:
    def __init__(self, session, business_id, batch_uuid):
        self.session, self.business_id, self.batch_uuid = session, business_id, batch_uuid

    def item(self, item_uuid):
        return self.session.execute(
            "SELECT * FROM financial_history_import_items WHERE business_id=? AND batch_uuid=? AND item_uuid=?",
            (self.business_id, self.batch_uuid, item_uuid),
        ).fetchone()

    def insert(self, values):
        values = dict(business_id=self.business_id, batch_uuid=self.batch_uuid, **values)
        fields = tuple(values)
        self.session.execute(
            "INSERT INTO financial_history_import_items ("
            + ",".join(fields)
            + ") VALUES ("
            + ",".join("?" for _ in fields)
            + ")",
            tuple(values.values()),
        )

    def request(self, candidate):
        ident = candidate.identity
        return FinancialRequest(
            COMMANDS[ident.event_type.value],
            ident.source.source_id,
            candidate.amount,
            candidate.dates.economic_date,
            ident.revision.value,
            None,
            {
                "historical_recording_version": 1,
                "identity_hash": ident.content_hash,
                "candidate_hash": candidate.content_hash,
                "event_type": ident.event_type.value,
                "payload_version": candidate.event_payload.payload_version,
            },
        )

    def intent(self, context, candidate, event, raw_hash, sequence):
        request = self.request(candidate)
        auth = str(uuid5(UUID(context.operation_uuid), "historical-authorization-v1"))
        self.insert(
            dict(
                manifest_uuid=context.manifest_uuid,
                item_uuid=context.item_uuid,
                candidate_hash=context.candidate_hash,
                raw_hash=raw_hash,
                identity_hash=context.identity_hash,
                identity_canonical=candidate.identity.canonical_bytes().decode(),
                expected_event_uuid=context.event_uuid,
                expected_operation_uuid=context.operation_uuid,
                expected_authorization_uuid=auth,
                expected_event_canonical=event.canonical_bytes().decode(),
                expected_request_canonical=request.canonical(),
                expected_sequence=sequence,
                recorded_by=context.recorded_by,
                session_version=context.session_version,
                state="recording",
                completion_key="recorded",
                created_at=stamp(),
            )
        )
        return request, auth

    def record_operation(self, context, request, auth):
        # La autoridad se vuelve a contrastar en BD con el intent y sus UUID exactos.
        self.validate_context(context)
        now = stamp()
        self.session.execute(
            """INSERT INTO financial_operations (business_id,operation_uuid,entry_namespace,entry_key,
            created_by,command_type,command_version,request_canonical,request_hash,expected_revision,state,created_at,updated_at)
            VALUES (?,?,'historical',?,?,?,1,?,?,?,'prepared',?,?)""",
            (
                self.business_id,
                context.operation_uuid,
                context.identity_hash,
                context.recorded_by,
                request.command_type.value,
                request.canonical(),
                request.request_hash,
                request.expected_revision,
                now,
                now,
            ),
        )

    def record_authorization(self, context, request, auth):
        self.validate_context(context)
        now = stamp()
        self.session.execute(
            """INSERT INTO financial_authorizations (business_id,authorization_uuid,operation_uuid,kind,
            actor_user_id,actor_session_version,recorded_by,validated_permission,approved_request_hash,approved_revision,channel,authorized_at)
            VALUES (?,?,?,'historical_unknown',NULL,NULL,?,'historical.record',?,?,'historical',?)""",
            (
                self.business_id,
                auth,
                context.operation_uuid,
                context.recorded_by,
                request.request_hash,
                request.expected_revision,
                now,
            ),
        )
        self.session.execute(
            "UPDATE financial_operations SET authorization_uuid=?,updated_at=? WHERE business_id=? AND operation_uuid=?",
            (auth, now, self.business_id, context.operation_uuid),
        )

    def validate_context(self, context):
        from .durable import HistoricalImportContext
        from noesis.financial_operations.contracts import StateError

        if not isinstance(context, HistoricalImportContext):
            raise TypeError("Contexto histórico tipado requerido.")
        row = self.item(context.item_uuid)
        batch = self.session.execute(
            "SELECT * FROM financial_history_import_batches WHERE business_id=? AND batch_uuid=?",
            (self.business_id, self.batch_uuid),
        ).fetchone()
        if (
            context.business_id != self.business_id
            or context.batch_uuid != self.batch_uuid
            or not row
            or not batch
            or row["state"] != "recording"
            or str(row["manifest_uuid"]) != context.manifest_uuid
            or row["candidate_hash"] != context.candidate_hash
            or row["identity_hash"] != context.identity_hash
            or row["recorded_by"] != context.recorded_by
            or row["session_version"] != context.session_version
            or str(row["expected_event_uuid"]) != context.event_uuid
            or str(row["expected_operation_uuid"]) != context.operation_uuid
            or str(batch["epoch_uuid"]) != context.epoch_uuid
            or batch["generation"] != context.generation
            or batch["importer_version"] != context.importer_version
        ):
            raise StateError("Contexto no coincide con el intent durable de esta TX.")

    def finish(self, context, stored):
        result = result_values(context.item_uuid, "recorded", stored)
        self.session.execute(
            """UPDATE financial_history_import_items SET state='recorded',event_uuid=?,operation_uuid=?,
            authorization_uuid=?,content_hash=?,record_hash=?,result_canonical=?,completed_at=?
            WHERE business_id=? AND batch_uuid=? AND item_uuid=? AND state='recording'""",
            (
                str(stored.event.event_id),
                stored.operation_uuid,
                stored.authorization_uuid,
                stored.event.content_hash,
                stored.record_hash,
                canonical(result),
                stamp(),
                self.business_id,
                self.batch_uuid,
                context.item_uuid,
            ),
        )
        return result


def result_values(item_uuid, state, stored=None, reason=None):
    return dict(
        result_version=1,
        item_uuid=item_uuid,
        state=state,
        reason=reason,
        event_uuid=None if stored is None else str(stored.event.event_id),
        operation_uuid=None if stored is None else stored.operation_uuid,
        authorization_uuid=None if stored is None else stored.authorization_uuid,
        content_hash=None if stored is None else stored.event.content_hash,
        record_hash=None if stored is None else stored.record_hash,
    )
