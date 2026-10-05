"""Contrato durable histórico separado; no amplía EconomicEvent live."""

from dataclasses import dataclass
from uuid import UUID, uuid5

from noesis.economic_events.contracts import EconomicEvent, _canonical
from .payloads import EventOrigin, EventPayload


class HistoricalEconomicEvent(EconomicEvent):
    __slots__ = ()

    def _validated_payload(self):
        return EventPayload(
            self.event_type,
            self.payload_version,
            EventOrigin.HISTORICAL,
            self.payload,
            self.currency,
        ).payload

    @property
    def payload_hash(self):
        import hashlib

        return hashlib.sha256(
            _canonical(
                {
                    "canonical_version": 1,
                    "event_type": self.event_type.value,
                    "payload_version": self.payload_version,
                    "currency": self.currency.value,
                    "payload": self._validated_payload(),
                }
            )
        ).hexdigest()


def operation_uuid(identity):
    return str(uuid5(UUID("da4dd08e-997b-59d3-a9bc-848f9360d0a7"), identity.content_hash))


@dataclass(frozen=True, slots=True)
class HistoricalImportContext:
    business_id: int
    epoch_uuid: str
    generation: int
    manifest_uuid: str
    batch_uuid: str
    item_uuid: str
    candidate_hash: str
    identity_hash: str
    recorded_by: int
    session_version: int
    event_uuid: str
    operation_uuid: str
    importer_version: int = 1

    def __post_init__(self):
        from noesis.financial_operations.contracts import positive_id, uuid_text
        from .canonical import sha256, version_one

        for name in ("business_id", "generation", "recorded_by"):
            positive_id(getattr(self, name))
        for name in (
            "epoch_uuid",
            "manifest_uuid",
            "batch_uuid",
            "item_uuid",
            "event_uuid",
            "operation_uuid",
        ):
            object.__setattr__(self, name, uuid_text(getattr(self, name)))
        for name in ("candidate_hash", "identity_hash"):
            sha256(getattr(self, name))
        if type(self.session_version) is not int or self.session_version < 0:
            raise ValueError("Sesión actual requerida.")
        version_one(self.importer_version)
