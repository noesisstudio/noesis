"""SQL de eventos sobre FinancialSession prestada; sin permisos ni transacciones propias."""

from .contracts import canonical_payload
from .persistence import StoredEvent, instant, record_hash
from .schema import SOURCES


class EventsRepository:
    def __init__(self, session, business_id):
        self.session, self.business_id = session, business_id

    def lock_business(self):
        self.session.execute(
            "INSERT INTO economic_event_sequences (business_id,last_sequence) VALUES (?,0) ON CONFLICT(business_id) DO NOTHING",
            (self.business_id,),
        )
        lock = " FOR UPDATE" if self.session.dialect == "postgres" else ""
        self.session.execute(
            "SELECT last_sequence FROM economic_event_sequences WHERE business_id=?" + lock,
            (self.business_id,),
        ).fetchone()

    def next_sequence(self):
        return self.session.execute(
            "UPDATE economic_event_sequences SET last_sequence=last_sequence+1 WHERE business_id=? RETURNING last_sequence",
            (self.business_id,),
        ).fetchone()["last_sequence"]

    def find(self, event, operation_uuid, event_slot, key):
        return self.session.execute(
            "SELECT * FROM economic_events WHERE business_id=? AND (event_uuid=? OR idempotency_key=? OR (operation_uuid=? AND event_slot=?) OR (source_type=? AND source_id=? AND source_revision=? AND event_type=?))",
            (
                self.business_id,
                str(event.event_id),
                key,
                operation_uuid,
                event_slot,
                event.source_type.value,
                event.source_id,
                event.source_revision,
                event.event_type.value,
            ),
        ).fetchall()

    def load(self, event_uuid):
        return self.session.execute(
            "SELECT * FROM economic_events WHERE business_id=? AND event_uuid=?",
            (self.business_id, str(event_uuid)),
        ).fetchone()

    def links(self, event_uuid):
        return self.session.execute(
            "SELECT relation_type,target_event_uuid FROM economic_event_links WHERE business_id=? AND event_uuid=? ORDER BY relation_type",
            (self.business_id, str(event_uuid)),
        ).fetchall()

    def insert_link(self, event_uuid, relation, now):
        self.session.execute(
            "INSERT INTO economic_event_links (business_id,event_uuid,target_event_uuid,relation_type,recorded_at) VALUES (?,?,?,?,?)",
            (
                self.business_id,
                str(event_uuid),
                str(relation.target_event_id),
                relation.kind.value,
                now,
            ),
        )

    def insert(self, event, metadata):
        values = dict(
            business_id=self.business_id,
            event_uuid=str(event.event_id),
            event_type=event.event_type.value,
            payload_version=event.payload_version,
            source_type=event.source_type.value,
            source_id=event.source_id,
            source_revision=event.source_revision,
            occurred_at=None if event.occurred_at is None else instant(event.occurred_at),
            observed_at=instant(event.observed_at),
            economic_date=None if event.economic_date is None else event.economic_date.isoformat(),
            currency=event.currency.value,
            amount=event.amount,
            canonical_version=1,
            payload_canonical=canonical_payload(
                event.event_type, event.payload, event.payload_version
            ).decode("utf-8"),
            canonical_event=event.canonical_bytes().decode("utf-8"),
            content_hash=event.content_hash,
            **metadata,
        )
        values[SOURCES[event.source_type.value][1]] = event.source_id
        values["record_hash"] = record_hash(event, **metadata)
        columns = tuple(values)
        row = self.session.execute(
            "INSERT INTO economic_events ("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join("?" for _ in columns)
            + ") RETURNING *",
            tuple(values.values()),
        ).fetchone()
        return StoredEvent.from_row(row)
