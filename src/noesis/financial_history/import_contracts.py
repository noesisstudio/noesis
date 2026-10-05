"""Decodificación estricta del candidato congelado, sin reclasificar."""

from datetime import datetime
import json

from .contracts import (
    Assessment,
    EvidenceReference,
    ExistingCoverage,
    HistoricalDates,
    HistoricalDependency,
    HistoricalIdentity,
    RevisionIdentity,
    SourceReference,
)
from .money_evidence import RawMonetaryEvidence
from .payloads import EventPayload
from .planning import DiagnosticCandidate, InventoryEvidence


def identity(value):
    return HistoricalIdentity(
        SourceReference(**value["source"]),
        RevisionIdentity(**value["revision"]),
        value["event_type"],
        value["fact_slot"],
        value["derivation_version"],
    )


def coverage(text):
    value = json.loads(text)["value"]
    value["identity"] = identity(value["identity"])
    return ExistingCoverage(**value)


def candidate(text, observed_at):
    body = json.loads(text)
    if body["contract"] != "DiagnosticCandidate" or body["canonical_version"] != 1:
        raise ValueError("Contrato congelado desconocido.")
    v = body["value"]
    if v["eligible_for_import"] is not False or v["certifiable"] is not False:
        raise ValueError("No promover el candidato diagnóstico.")
    observed_at = datetime.fromisoformat(str(observed_at))
    dates = dict(v["dates"])
    if dates["occurred_at"] is not None:
        dates["occurred_at"] = datetime.fromisoformat(dates["occurred_at"])
    dates = HistoricalDates(**dates, observed_at=observed_at, recorded_at=None)
    e = v["evidence"]
    if e["contract"] != "InventoryEvidence" or e["canonical_version"] != 1:
        raise ValueError("Evidencia congelada desconocida.")
    ev = e["value"]
    evidence = InventoryEvidence(
        SourceReference(**ev["source"]),
        RevisionIdentity(**ev["revision"]),
        ev["basis"],
        observed_at,
        dates,
        {k: RawMonetaryEvidence(**raw) for k, raw in ev["money"].items()},
        tuple(EvidenceReference(**r) for r in ev["references"]),
    )
    deps = tuple(
        HistoricalDependency(
            d["relation"],
            identity(d["target"]),
            None if d["parent_assessment"] is None else Assessment(**d["parent_assessment"]),
        )
        for d in v["dependencies"]
    )
    covered = v["existing_coverage"]
    if covered is not None:
        covered = ExistingCoverage(
            identity(covered["identity"]),
            covered["event_uuid"],
            covered["event_content_hash"],
            covered["origin"],
        )
    result = DiagnosticCandidate(
        identity(v["identity"]),
        EventPayload(**v["event_payload"]),
        evidence,
        dates,
        Assessment(**v["assessment"]),
        deps,
        covered,
    )
    if result.canonical_bytes().decode() != text:
        raise ValueError("Candidato congelado no canónico.")
    return result
