"""Sobre durable: mantiene intacto el contrato puro v1 y verifica la lectura."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json

from .contracts import EconomicEvent, EventRelation
from noesis.financial_operations.contracts import strict_json, uuid_text


def instant(value):
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Instante con zona requerido.")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def record_hash(
    event,
    *,
    operation_uuid,
    event_slot,
    authorization_uuid,
    origin,
    historical_batch_uuid,
    provenance,
    date_precision,
    date_provenance,
    idempotency_key,
    business_sequence,
    recorded_at,
):
    metadata = dict(
        content_hash=event.content_hash,
        operation_uuid=operation_uuid,
        event_slot=event_slot,
        authorization_uuid=authorization_uuid,
        origin=origin,
        historical_batch_uuid=historical_batch_uuid,
        provenance=provenance,
        date_precision=date_precision,
        date_provenance=date_provenance,
        idempotency_key=idempotency_key,
        business_sequence=business_sequence,
        recorded_at=instant(recorded_at),
        persistence_version=1,
    )
    return hashlib.sha256(
        json.dumps(
            metadata, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class StoredEvent:
    id: int
    business_sequence: int
    event: EconomicEvent
    operation_uuid: str | None
    event_slot: str
    authorization_uuid: str | None
    origin: str
    historical_batch_uuid: str | None
    provenance: str
    date_precision: str
    date_provenance: str
    idempotency_key: str
    recorded_at: str
    record_hash: str

    @classmethod
    def from_row(cls, row):
        raw = strict_json(row["canonical_event"])
        if raw.pop("canonical_version", None) != 1:
            raise ValueError("Versión canónica desconocida.")
        raw.pop("amount")
        raw["occurred_at"] = (
            None if raw["occurred_at"] is None else datetime.fromisoformat(raw["occurred_at"])
        )
        raw["observed_at"] = datetime.fromisoformat(raw["observed_at"])
        raw["relations"] = tuple(EventRelation(**rel) for rel in raw["relations"])
        event_class = EconomicEvent
        if row['origin'] == 'historical':
            from noesis.financial_history.durable import HistoricalEconomicEvent
            event_class = HistoricalEconomicEvent
        event = event_class(**raw)
        if (
            event.canonical_bytes().decode("utf-8") != row["canonical_event"]
            or event.content_hash != row["content_hash"]
            or event.payload_bytes().decode("utf-8")
            != row["payload_canonical"]
        ):
            raise ValueError("Payload/sobre/hash incoherentes; no reparar automáticamente.")
        native_date = row["economic_date"]
        if isinstance(native_date, str):
            native_date = date.fromisoformat(native_date)
        native_amount = row["amount"]
        if native_amount is not None:
            from noesis.core.money import parse_money

            native_amount = parse_money(native_amount)
        expected = dict(
            business_id=event.business_id,
            event_uuid=str(event.event_id),
            event_type=event.event_type.value,
            source_type=event.source_type.value,
            source_id=event.source_id,
            source_revision=event.source_revision,
            payload_version=event.payload_version,
            currency=event.currency.value,
        )
        if (
            any(str(row[k]) != str(v) for k, v in expected.items())
            or native_amount != event.amount
            or native_date != event.economic_date
            or instant(row["observed_at"]) != instant(event.observed_at)
            or (None if row["occurred_at"] is None else instant(row["occurred_at"]))
            != (None if event.occurred_at is None else instant(event.occurred_at))
        ):
            raise ValueError("Columnas estructurales incoherentes con el sobre.")
        values = {
            key: row[key]
            for key in (
                "event_slot",
                "origin",
                "provenance",
                "date_precision",
                "date_provenance",
                "idempotency_key",
                "business_sequence",
                "recorded_at",
            )
        }
        for key in ("operation_uuid", "authorization_uuid", "historical_batch_uuid"):
            values[key] = None if row[key] is None else uuid_text(row[key])
        values["recorded_at"] = instant(values["recorded_at"])
        if record_hash(event, **values) != row["record_hash"]:
            raise ValueError("Huella del registro durable incoherente.")
        return cls(id=row["id"], event=event, record_hash=row["record_hash"], **values)
