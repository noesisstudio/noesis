"""Catálogo y resultados cerrados de reconciliación; ninguna autoridad financiera."""

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import re

from .canonical import sha256, version_one
from .repository import canonical


class FindingCode(StrEnum):
    SOURCE_DRIFT = "SOURCE_DRIFT"
    MANIFEST_INCONSISTENT = "MANIFEST_INCONSISTENT"
    BATCH_NOT_TERMINAL = "BATCH_NOT_TERMINAL"
    IMPORT_ITEM_MISSING = "IMPORT_ITEM_MISSING"
    IMPORT_ITEM_UNEXPECTED = "IMPORT_ITEM_UNEXPECTED"
    IMPORT_RESULT_CONFLICT = "IMPORT_RESULT_CONFLICT"
    EVENT_MISSING = "EVENT_MISSING"
    EVENT_CONTENT_CONFLICT = "EVENT_CONTENT_CONFLICT"
    OPERATION_CONFLICT = "OPERATION_CONFLICT"
    AUTHORIZATION_CONFLICT = "AUTHORIZATION_CONFLICT"
    DEPENDENCY_CONFLICT = "DEPENDENCY_CONFLICT"
    EXISTING_COVERAGE_CONFLICT = "EXISTING_COVERAGE_CONFLICT"
    UNEXPECTED_HISTORICAL_EVENT = "UNEXPECTED_HISTORICAL_EVENT"
    LIVE_COVERAGE_CONTAMINATION = "LIVE_COVERAGE_CONTAMINATION"
    SEQUENCE_CONFLICT = "SEQUENCE_CONFLICT"
    FISCAL_REFERENCE_CONFLICT = "FISCAL_REFERENCE_CONFLICT"
    BLOCKING_HISTORY_REMAINS = "BLOCKING_HISTORY_REMAINS"


class ReconciliationResult(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def reference(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,160}", value):
        raise ValueError("Referencia mínima estructural requerida, sin texto libre.")
    return value


@dataclass(frozen=True, slots=True)
class ReconciliationFinding:
    code: FindingCode
    item_uuid: str | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None
    expected_ref: str | None = None
    actual_ref: str | None = None
    finding_version: int = 1

    def __post_init__(self):
        from noesis.financial_operations.contracts import uuid_text

        version_one(self.finding_version)
        object.__setattr__(self, "code", FindingCode(self.code))
        if self.item_uuid is not None:
            object.__setattr__(self, "item_uuid", uuid_text(self.item_uuid))
        for name in ("expected_hash", "actual_hash"):
            if getattr(self, name) is not None:
                sha256(getattr(self, name))
        for name in ("expected_ref", "actual_ref"):
            reference(getattr(self, name))

    def value(self):
        return dict(finding_version=1, code=self.code.value, severity="blocking",
                    item_uuid=self.item_uuid, expected_hash=self.expected_hash,
                    actual_hash=self.actual_hash, expected_ref=self.expected_ref,
                    actual_ref=self.actual_ref)

    @property
    def content_hash(self):
        return digest(self.value())


HASH_FIELDS = ("source_set_hash", "plan_hash", "import_set_hash", "event_set_hash",
               "source_recheck_hash", "findings_hash")


def result_value(row):
    version_one(row["reconciliation_version"])
    for field in HASH_FIELDS:
        sha256(row[field])
    return dict(reconciliation_version=1, business_id=row["business_id"],
                epoch_uuid=str(row["epoch_uuid"]), generation=row["generation"],
                manifest_uuid=str(row["manifest_uuid"]), batch_uuid=str(row["batch_uuid"]),
                **{field:row[field] for field in HASH_FIELDS},
                result=ReconciliationResult(row["result"]).value)
