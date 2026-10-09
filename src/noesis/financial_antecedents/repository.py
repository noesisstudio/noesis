"""Persistencia append-only B sobre la transacción prestada del llamador."""

from datetime import datetime, timezone

from noesis.financial_operations.contracts import AccessDenied, ConflictError, strict_json
from noesis.economic_events.persistence import instant
from .contracts import Permission, Reason, canonical, digest, validate_result
from .schema import TABLE


class AntecedentRepository:
    def __init__(self, session, business_id):
        self.s, self.bid = session, business_id

    def load(self, uid):
        return self.s.execute(
            f"SELECT * FROM {TABLE} WHERE business_id=? AND resolution_uuid=?", (self.bid, uid)
        ).fetchone()

    def read(self, principal, uid):
        row = self.load(uid)
        if (
            not row
            or row["created_by"] != principal.user_id
            or row["session_version"] != principal.session_version
        ):
            raise AccessDenied("Acceso a antecedente denegado.")
        result = validate_result(strict_json(row["result_canonical"]))
        request = result["request"]["antecedent"]
        columns = dict(
            business_id=result["business_id"],
            resolution_version=1,
            purpose=result["request"]["purpose"],
            source_type=request["source_type"],
            source_id=request["source_id"],
            source_revision=request["revision"],
            outcome=result["outcome"],
            **{k: result[k] for k in ("origin", "quality", "source_hash", "context_hash")},
            event_uuid=result["event_uuid"],
            operation_uuid=result["operation_uuid"],
            authorization_uuid=result["authorization_uuid"],
            batch_uuid=result["batch_uuid"],
            item_uuid=result["item_uuid"],
            reconciliation_uuid=result["reconciliation_uuid"],
            event_content_hash=result["event_content_hash"],
            event_record_hash=result["event_record_hash"],
            known_unknown_canonical=canonical(result["proof"]),
            content_hash=digest(result),
            revalidation="every_use",
            validated_permission=Permission.RESOLVE.value,
        )
        if any(
            (None if row[k] is None else str(row[k])) != (None if v is None else str(v))
            for k, v in columns.items()
        ):
            raise ConflictError("Resolución durable incoherente.")
        return dict(
            resolution_uuid=str(row["resolution_uuid"]),
            created_at=instant(row["created_at"]),
            result=result,
            content_hash=row["content_hash"],
            revalidation="every_use",
        )

    def store(self, principal, uid, result):
        validate_result(result)
        existing = self.load(uid)
        if existing:
            original = self.read(principal, uid)
            if original["result"]["context_hash"] != result["context_hash"] or canonical(
                original["result"]
            ) != canonical(result):
                raise ConflictError(Reason.SOURCE_CHANGED.value)
            return original
        ref = result["request"]["antecedent"]
        manifest = None
        if result["item_uuid"]:
            manifest = self.s.execute(
                "SELECT manifest_uuid FROM financial_history_import_items WHERE business_id=? AND batch_uuid=? AND item_uuid=?",
                (self.bid, result["batch_uuid"], result["item_uuid"]),
            ).fetchone()["manifest_uuid"]
        values = dict(
            business_id=self.bid,
            resolution_uuid=uid,
            resolution_version=1,
            purpose=result["request"]["purpose"],
            source_type=ref["source_type"],
            source_id=ref["source_id"],
            source_revision=ref["revision"],
            **{
                k: result[k]
                for k in (
                    "outcome",
                    "origin",
                    "quality",
                    "event_uuid",
                    "operation_uuid",
                    "authorization_uuid",
                    "batch_uuid",
                    "item_uuid",
                    "reconciliation_uuid",
                    "source_hash",
                    "event_content_hash",
                    "event_record_hash",
                    "context_hash",
                )
            },
            manifest_uuid=None if manifest is None else str(manifest),
            created_by=principal.user_id,
            session_version=principal.session_version,
            validated_permission=Permission.RESOLVE.value,
            known_unknown_canonical=canonical(result["proof"]),
            result_canonical=canonical(result),
            content_hash=digest(result),
            revalidation="every_use",
            created_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        )
        source_column = {"cancellation_record": "invoice_cancellation_record_id"}.get(
            ref["source_type"], ref["source_type"] + "_id"
        )
        values[source_column] = ref["source_id"]
        self.s.execute(
            f"INSERT INTO {TABLE} ("
            + ",".join(values)
            + ") VALUES ("
            + ",".join("?" for _ in values)
            + ")",
            tuple(values.values()),
        )
        return self.read(principal, uid)
