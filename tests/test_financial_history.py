"""Solo contratos y fixtures sintéticos; nunca inventario/importación de legacy."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Context, Decimal, localcontext
import hashlib
import json
from pathlib import Path
import struct
import unittest
from uuid import UUID

from noesis.economic_events.contracts import (
    CATALOG, EconomicEvent, EventType, RelationType, SourceType, canonical_payload, payload_hash,
)
from noesis.financial_history.canonical import canonical_bytes, freeze
from noesis.financial_history.contracts import (
    Assessment, Classification, DatePrecision, DecisionKind, Disposition, EvidenceReference,
    EvidenceSource, ExistingCoverage, HistoricalAuditContext, HistoricalCandidate, HistoricalDates,
    HistoricalDecision, HistoricalDependency, HistoricalEvidence, HistoricalIdentity, HistoricalIncidence,
    IncidenceCode, LegacyDateKind, ReasonCode, RevisionIdentity, RevisionKind, RuleId, Severity, SourceReference,
)
from noesis.financial_history.money_evidence import (
    CorroborationStatus, MoneyProvenance, MoneyReason, RawMonetaryEvidence, StorageEngine, StorageType,
)
from noesis.financial_history.payloads import EventOrigin, EventPayload, EvidenceBasis, HISTORICAL_V2
from noesis.financial_operations.contracts import (
    AuthorizationKind, ConflictError, EntryIdentity, EntryNamespace, OperationState, StateError,
)
from noesis.financial_operations.historical import HistoricalAuthorization
from tests.test_economic_events import NOW, PAYLOADS


H = "a" * 64
OTHER_H = "b" * 64


def raw_exact(value="10.00", *, engine=StorageEngine.POSTGRES):
    exact = Decimal(value)
    with localcontext(Context(prec=1200)):
        reason = MoneyReason.EXACT_VALUE if exact == exact.quantize(Decimal("0.01")) else MoneyReason.SUBCENT
    return RawMonetaryEvidence(engine, StorageType.NUMERIC if engine == StorageEngine.POSTGRES else StorageType.TEXT,
        value, exact, None, None, value, None, None, MoneyProvenance.EXACT,
        CorroborationStatus.EXACT, None, (), reason)


def raw_unknown():
    return RawMonetaryEvidence(StorageEngine.SQLITE, StorageType.NULL, None, None, None, None,
        None, None, None, MoneyProvenance.UNKNOWN, CorroborationStatus.UNKNOWN, None, (), MoneyReason.UNKNOWN)


def raw_binary(value=12.340000000000002, *, engine=StorageEngine.SQLITE, candidate=None):
    finite = value == value and value not in (float("inf"), float("-inf"))
    raw = Decimal.from_float(value) if finite else None
    with localcontext(Context(prec=1200)):
        delta = None if candidate is None else raw - Decimal(candidate)
    return RawMonetaryEvidence(engine, StorageType.REAL if engine == StorageEngine.SQLITE else StorageType.DOUBLE,
        repr(value), None, struct.pack("!d", value).hex(), raw, None, candidate, delta,
        MoneyProvenance.LEGACY_BINARY, CorroborationStatus.UNCORROBORATED, None, (),
        MoneyReason.BINARY_UNCORROBORATED if finite else MoneyReason.NON_FINITE)


def identity(kind=EventType.EXPENSE_CONFIRMED, *, bid=1, source_id=1, revision=1, slot="primary"):
    return HistoricalIdentity(SourceReference(bid, CATALOG[kind].source_type, source_id),
        RevisionIdentity(RevisionKind.OBSERVED_REVISION, revision, None), kind, slot)


def dates(day=None):
    return HistoricalDates(LegacyDateKind.UNKNOWN if day is None else LegacyDateKind.CIVIL_DATE,
        day, day, day, None, NOW, None)


def assessment(category=Classification.VERIFIED_HISTORY, *, evidence_hash=H,
               disposition=Disposition.CANDIDATE, severity=Severity.INFO):
    rules = dict(zip(Classification, RuleId, strict=True))
    reason = ReasonCode.VERIFIED_FACT if category == Classification.VERIFIED_HISTORY else ReasonCode.OBSERVED_STATE
    code = None
    if category in (Classification.AMBIGUOUS, Classification.NOT_AUTOMATICALLY_TRANSFORMABLE):
        disposition = Disposition.PENDING_INCIDENCE
        reason, code = ReasonCode.INCIDENCE, IncidenceCode.REQUIRED_VALUE_UNKNOWN
    if disposition == Disposition.COVERED_EXISTING:
        reason = ReasonCode.COVERED_EXISTING
    return Assessment(category, disposition, severity, rules[category], 1, reason, (evidence_hash,), code)


def candidate(kind=EventType.EXPENSE_CONFIRMED, *, basis=EvidenceBasis.VERIFIED_FACT,
              revision=1, dependencies=None, raw=None):
    ident = identity(kind, revision=revision)
    values = dict(PAYLOADS[kind])
    day = values[CATALOG[kind].economic_date_field]
    temporal = dates(day)
    if kind in HISTORICAL_V2:
        values["confirmed_on" if kind != EventType.BANK_TRANSACTION_IMPORTED else "imported_on"] = None
        values.update(evidence_basis=basis.value, evidence_hash=H)
        version = 2
    else:
        version = 1
    initial = EventPayload(kind, version, EventOrigin.HISTORICAL, values, "EUR")
    money = {}
    def add(mapping, prefix=""):
        for key, val in mapping.items():
            if key in ("before", "after"):
                add(val, key + ".")
            elif key in ("amount", "total", "base", "vat_amount", "irpf_amount", "original_total"):
                money[prefix + key] = raw_unknown() if val is None else raw_exact(format(val, "f"))
    add(initial.payload)
    if raw is not None:
        money["total"] = raw
    evidence = HistoricalEvidence(ident.source, ident.revision, basis, NOW, temporal, money, ())
    if version == 2:
        values["evidence_hash"] = evidence.content_hash
    payload = EventPayload(kind, version, EventOrigin.HISTORICAL, values, "EUR")
    category = Classification.VERIFIED_HISTORY if basis == EvidenceBasis.VERIFIED_FACT else Classification.OBSERVED_STATE
    classified = assessment(category, evidence_hash=evidence.content_hash)
    if dependencies is None:
        dependencies = []
        for rule in CATALOG[kind].relations:
            parent_kind = rule.targets[0]
            source_id = 1
            parent_revision = 1
            if rule.kind == RelationType.RECTIFIES:
                source_id = 2
            if rule.kind == RelationType.MATCHES:
                source_id = values["invoice_payment_id"]
            dependencies.append(HistoricalDependency(rule.kind, identity(parent_kind, source_id=source_id,
                revision=parent_revision), assessment()))
    return HistoricalCandidate(ident, payload, evidence, temporal, classified, dependencies, None)


class FinancialHistoryContractsTest(unittest.TestCase):
    def test_closed_classifications_and_independent_axes(self):
        for category in Classification:
            item = assessment(category)
            self.assertIs(item.classification, category)
            self.assertEqual(item.rule_version, 1)
            warning = replace(item, severity=Severity.WARNING)
            self.assertIs(warning.classification, category)
        item = assessment(Classification.OBSERVED_STATE)
        excluded = replace(item, disposition=Disposition.EXCLUDED, reason=ReasonCode.EXCLUDED,
                           severity=Severity.BLOCKING)
        self.assertIs(excluded.classification, Classification.OBSERVED_STATE)
        self.assertIs(excluded.severity, Severity.BLOCKING)

    def test_unknown_rules_versions_and_confused_axes_rejected(self):
        item = assessment()
        for changes in ({"rule_id": "llm.classify"}, {"rule_version": 2}, {"rule_version": True},
                        {"classification": "covered_existing"}, {"disposition": "A"},
                        {"severity": "B"}, {"classification": Classification.OBSERVED_STATE},
                        {"reason": "texto libre"}, {"evidence_hashes": ()}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(item, **changes)

    def test_c_d_are_never_importable_classifications(self):
        for category in (Classification.AMBIGUOUS, Classification.NOT_AUTOMATICALLY_TRANSFORMABLE):
            item = assessment(category)
            with self.assertRaises(ValueError):
                replace(item, disposition=Disposition.CANDIDATE)
            c = candidate()
            blocked = replace(c, assessment=replace(item, evidence_hashes=(c.evidence.content_hash,)))
            self.assertFalse(blocked.importable)

    def test_all_eleven_identities_and_business_source_event_slot(self):
        for kind in EventType:
            self.assertEqual(identity(kind).entry_identity.namespace, EntryNamespace.HISTORICAL)
            self.assertEqual(identity(kind).event_uuid, identity(kind).event_uuid)
        item = identity(EventType.BANK_TRANSACTION_IMPORTED)
        variants = (identity(EventType.BANK_TRANSACTION_IMPORTED, bid=2),
                    identity(EventType.BANK_TRANSACTION_IMPORTED, source_id=2),
                    identity(EventType.BANK_TRANSACTION_MATCHED),
                    identity(EventType.BANK_TRANSACTION_IMPORTED, slot="import"),
                    identity(EventType.BANK_TRANSACTION_IMPORTED, revision=2))
        self.assertEqual(len({item.content_hash, *(v.content_hash for v in variants)}), 6)

    def test_identity_rejects_manifest_operator_retry_and_unknown_revision(self):
        item = identity()
        for name in ("manifest_uuid", "operator", "retry", "imported_at"):
            with self.assertRaises(TypeError):
                replace(item, **{name: "variable"})
        for changes in ({"value": None}, {"value": True}, {"value": 0}, {"kind": "invented_history"}):
            with self.assertRaises((TypeError, ValueError)):
                replace(item.revision, **changes)
        with self.assertRaises(ValueError):
            replace(item, event_type="quote.accepted")
        with self.assertRaises(ValueError):
            replace(item, derivation_version=2)

    def test_identity_evidence_conflict_and_legacy_factory_unchanged(self):
        item = identity()
        item.assert_same_evidence(H, H)
        with self.assertRaises(ConflictError):
            item.assert_same_evidence(H, OTHER_H)
        expected = hashlib.sha256(json.dumps(["expense", 1, 1], ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(EntryIdentity.historical("expense", 1, 1).key, expected)
        self.assertNotEqual(item.entry_identity, EntryIdentity.historical("expense", 1, 1))

    def test_immutable_fingerprint_identity_uses_full_hash(self):
        revision = RevisionIdentity(RevisionKind.IMMUTABLE_FINGERPRINT, 1, H)
        item = replace(identity(), revision=revision)
        self.assertNotEqual(item.content_hash, replace(item, revision=replace(revision, fingerprint=OTHER_H)).content_hash)
        with self.assertRaises(ValueError):
            replace(revision, fingerprint=None)

    def test_numeric_text_exact_and_zero_unknown(self):
        for engine in StorageEngine:
            raw = raw_exact("0.00", engine=engine)
            self.assertTrue(raw.validates_declared_amount("0.00"))
            self.assertFalse(raw.validates_declared_amount(None))
        missing = raw_unknown()
        self.assertTrue(missing.validates_declared_amount(None))
        self.assertFalse(missing.validates_declared_amount("0.00"))
        with self.assertRaises(ValueError):
            replace(missing, candidate_cent_value="0.00", delta="0")

    def test_real_double_residue_remains_uncorroborated(self):
        for engine in StorageEngine:
            raw = raw_binary(engine=engine, candidate="12.34")
            self.assertEqual(raw.candidate_cent_value, Decimal("12.34"))
            self.assertNotEqual(raw.delta, Decimal(0))
            self.assertIsNone(raw.exact_decimal)
            self.assertFalse(raw.validates_declared_amount("12.34"))
            parsed = json.loads(raw.canonical_bytes())["value"]
            self.assertIsInstance(parsed["binary_decimal"], str)
            with self.assertRaises(ValueError):
                replace(raw, exact_decimal="12.34")

    def test_subcent_no_implicit_rounding(self):
        raw = raw_exact("1.001")
        self.assertIs(raw.reason, MoneyReason.SUBCENT)
        self.assertFalse(raw.validates_declared_amount("1.00"))
        binary = replace(raw_binary(1.001), reason=MoneyReason.SUBCENT)
        self.assertFalse(binary.validates_declared_amount("1.00"))
        with self.assertRaises(ValueError):
            raw.validates_declared_amount("1.001")

    def test_binary_bits_text_decimal_and_delta_are_checked(self):
        raw = raw_binary(candidate="12.34")
        for changes in ({"binary_decimal": "12.34"}, {"raw_representation": "12.34"},
                        {"delta": "0"}, {"candidate_cent_value": "12.35"},
                        {"binary_representation": "bad"}, {"display_representation": "conversación"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(raw, **changes)

    def test_corroboration_is_explicit_and_referenced(self):
        raw = replace(raw_binary(10.0), corroboration=CorroborationStatus.CORROBORATED,
                      corroborated_decimal="10.00", corroborating_hashes=(H,), reason=MoneyReason.BINARY_CORROBORATED)
        self.assertTrue(raw.validates_declared_amount("10.00"))
        with self.assertRaises(ValueError):
            replace(raw, corroborating_hashes=())
        with self.assertRaises(ValueError):
            candidate(raw=raw)
        with self.assertRaises(ValueError):
            replace(raw, corroborated_decimal="11.00")
        c = candidate()
        evidence = replace(c.evidence, money=dict(c.evidence.money, total=raw),
                           references=(EvidenceReference(1, EvidenceSource.DOCUMENT, 1, H),))
        payload = replace(c.event_payload, payload=dict(c.event_payload.payload, evidence_hash=evidence.content_hash))
        corroborated = replace(c, evidence=evidence, event_payload=payload,
                               assessment=assessment(evidence_hash=evidence.content_hash))
        self.assertTrue(corroborated.importable)

    def test_nan_infinity_only_raw_incidence(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            item = raw_binary(value)
            self.assertIs(item.reason, MoneyReason.NON_FINITE)
            self.assertFalse(item.validates_declared_amount("0.00"))
            with self.assertRaises(ValueError):
                replace(item, candidate_cent_value="0.00", delta="0")
        for value in ("NaN", "Infinity", Decimal("NaN")):
            with self.assertRaises(ValueError):
                replace(raw_exact(), exact_decimal=value)

    def test_float_never_accepted_as_exact_or_candidate_money(self):
        raw = raw_exact()
        for field in ("exact_decimal", "candidate_cent_value", "delta", "corroborated_decimal"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(raw, **{field: 10.0})
        with self.assertRaises(TypeError):
            raw.validates_declared_amount(10.0)

    def test_hostile_decimal_context_does_not_change_raw_diagnostics(self):
        raw = raw_binary(candidate="12.34")
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(raw, raw_binary(candidate="12.34"))
            self.assertEqual(raw_exact("1.001").reason, MoneyReason.SUBCENT)

    def test_dates_unknown_day_naive_aware_and_observation(self):
        unknown = dates()
        self.assertIsNone(unknown.economic_date)
        self.assertIs(unknown.precision, DatePrecision.UNKNOWN)
        day = dates("2026-09-01")
        self.assertIs(day.precision, DatePrecision.DAY)
        self.assertNotEqual(day.economic_date, day.observed_at.date())
        naive = HistoricalDates(LegacyDateKind.NAIVE_TIMESTAMP, "2026-09-01T12:00:00", "2026-09-01",
            "2026-09-01", None, NOW, None)
        self.assertIsNone(naive.occurred_at)
        aware = HistoricalDates(LegacyDateKind.AWARE_TIMESTAMP, "2026-09-01T12:00:00+02:00", "2026-09-01",
            "2026-09-01", datetime(2026, 9, 1, 10, tzinfo=timezone.utc), NOW, None)
        self.assertIs(aware.precision, DatePrecision.INSTANT)
        self.assertNotEqual(aware.occurred_at, aware.observed_at)
        self.assertNotEqual(replace(aware, recorded_at=NOW+timedelta(days=1)).recorded_at, aware.occurred_at)

    def test_dates_do_not_assign_zone_or_today(self):
        for changes in ({"economic_date": date.today()}, {"civil_date": date.today()},
                        {"occurred_at": NOW}, {"observed_at": datetime(2026, 10, 2)}):
            with self.assertRaises(ValueError):
                replace(dates(), **changes)
        naive = HistoricalDates("naive_timestamp", "2026-09-01T12:00:00", "2026-09-01", None, None, NOW, None)
        with self.assertRaises(ValueError):
            replace(naive, occurred_at=NOW)

    def test_historical_v2_three_types_basis_and_known_unknown_dates(self):
        self.assertEqual(len(HISTORICAL_V2), 3)
        for kind in HISTORICAL_V2:
            for basis in EvidenceBasis:
                for original in (None, "2026-09-01"):
                    values = dict(PAYLOADS[kind], evidence_basis=basis.value, evidence_hash=H)
                    values["imported_on" if kind == EventType.BANK_TRANSACTION_IMPORTED else "confirmed_on"] = original
                    result = EventPayload(kind, 2, "historical", values, "EUR")
                    self.assertIs(result.evidence_basis, basis)
                    self.assertIsNone(result.economic_date)

    def test_historical_v2_null_money_preserves_unknown(self):
        c = candidate(EventType.SUPPLIER_INVOICE_CONFIRMED, basis=EvidenceBasis.OBSERVED_STATE)
        self.assertIsNone(c.event_payload.payload["vat_amount"])
        self.assertIsNone(c.event_payload.payload["base"])
        self.assertIsNone(c.event_payload.payload["irpf_amount"])
        self.assertTrue(c.importable)
        zero = dict(c.event_payload.payload, vat_amount="0.00")
        payload = replace(c.event_payload, payload=zero)
        self.assertNotEqual(payload.content_hash, c.event_payload.content_hash)

    def test_v2_live_unknown_type_version_basis_hash_extra_rejected(self):
        payload = candidate().event_payload
        for changes in ({"origin": "live"}, {"event_type": "quote.accepted"}, {"event_type": "job.completed"},
                        {"event_type": "supplier_payment.made"}, {"payload_version": 3}, {"payload_version": True},
                        {"currency": "USD"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(payload, **changes)
        for changes in ({"evidence_basis": "paid"}, {"evidence_hash": "bad"}, {"evidence_hash": "A"*64},
                        {"conversation": "texto"}, {"total": 10.0}, {"total": "10.001"}):
            with self.assertRaises((TypeError, ValueError)):
                replace(payload, payload=dict(payload.payload, **changes))
        for key in ("evidence_hash", "evidence_basis", "confirmed_on"):
            values = dict(payload.payload)
            del values[key]
            with self.assertRaises(ValueError):
                replace(payload, payload=values)

    def test_special_v2_is_memory_only_core_event_still_rejects_it(self):
        p = candidate().event_payload
        with self.assertRaises(ValueError):
            EconomicEvent(UUID(int=1), 1, p.event_type, SourceType.EXPENSE, 1, 1, None, NOW,
                          p.payload, payload_version=2)
        self.assertNotIsInstance(p, EconomicEvent)

    def test_v1_golden_hashes_all_types(self):
        expected = (
            "06afcef838e7045ad1ee2045376274557859f9e4eaf5df20b91817ea178a2496",  # pragma: allowlist secret; SHA256 público de fixture v1
            "381ed27d82bf2226c8a6b54c1c4bdac85c11d59805f81ee6a475669ca70cff70",  # pragma: allowlist secret; SHA256 público de fixture v1
            "993a1a3719a0c13c914c8c203f3d4ef76c286be81e88800b78b4cefa362a813a",  # pragma: allowlist secret; SHA256 público de fixture v1
            "13a09341ce5442ac574ca97dbda0162c7c7ff058c18dccc592c21d67f4d6f305",  # pragma: allowlist secret; SHA256 público de fixture v1
            "461eb6517c64bda662e3a2c9368dd0b29616468df51c54180713f47828370bcf",  # pragma: allowlist secret; SHA256 público de fixture v1
            "496de1dcf77efb7230f5488b4b04a777f0c399a065355e76f44e04224e3c252a",  # pragma: allowlist secret; SHA256 público de fixture v1
            "52465798af2433a4165051d88382c3cc957dc6c53746ee839c78f14caf9a44cc",  # pragma: allowlist secret; SHA256 público de fixture v1
            "16f452a5f31d52a58ecc82e2129f3ac223cf68652f2b216c261ab45ef918846f",  # pragma: allowlist secret; SHA256 público de fixture v1
            "a662f633742c18d025f5f70b7df455bbfe5ee2b23eaa74e71f7d437f60087394",  # pragma: allowlist secret; SHA256 público de fixture v1
            "73e4d4eeeca6c94e0aefb15be4aeae2efa130f75d0f1e09296854284f2092daa",  # pragma: allowlist secret; SHA256 público de fixture v1
            "b452aa814c93eb5b637fd959b729f07570acf27ff7468850fe03f57e9396cbd5",  # pragma: allowlist secret; SHA256 público de fixture v1
        )
        for (kind, value), golden in zip(PAYLOADS.items(), expected, strict=True):
            result = EventPayload(kind, 1, "live", value, "EUR")
            self.assertEqual(payload_hash(kind, value), golden)
            self.assertEqual(canonical_payload(kind, value), canonical_payload(kind, result.payload))

    def test_candidates_all_types_and_dependencies(self):
        for kind in EventType:
            revision = 2 if kind in (EventType.SUPPLIER_INVOICE_CORRECTED, EventType.SUPPLIER_INVOICE_VOIDED,
                                    EventType.EXPENSE_VOIDED) else 1
            item = candidate(kind, revision=revision)
            self.assertTrue(item.importable, kind)
            self.assertIsNone(item.dates.recorded_at)
            self.assertEqual(item.content_hash, item.content_hash)

    def test_invoice_v2_candidate_cannot_bypass_raw_line_evidence(self):
        from unittest.mock import patch
        c = candidate(EventType.INVOICE_ISSUED)
        # El wrapper conserva el validador v2 existente; la barrera del candidato
        # debe fallar antes de aceptar solo los importes de cabecera como prueba.
        with patch("noesis.financial_history.payloads.validate_payload", return_value=c.event_payload.payload):
            payload = replace(c.event_payload, payload_version=2)
        with self.assertRaisesRegex(ValueError, "raw por línea"):
            replace(c, event_payload=payload)

    def test_candidate_B_cannot_be_verified_or_use_v1(self):
        c = candidate(basis=EvidenceBasis.OBSERVED_STATE)
        with self.assertRaises(ValueError):
            replace(c, assessment=assessment(evidence_hash=c.evidence.content_hash))
        with self.assertRaises(ValueError):
            replace(c, event_payload=EventPayload(EventType.EXPENSE_CONFIRMED, 1, "historical",
                                                PAYLOADS[EventType.EXPENSE_CONFIRMED], "EUR"))
        with self.assertRaises(ValueError):
            replace(c, event_payload=replace(c.event_payload,
                payload=dict(c.event_payload.payload, evidence_basis="verified_fact")))

    def test_candidate_unverified_money_is_rejected_for_A_and_B(self):
        for basis in EvidenceBasis:
            for raw in (raw_binary(10.0, candidate="10.00"), raw_exact("10.001"), raw_unknown()):
                with self.subTest(basis=basis, raw=raw), self.assertRaises(ValueError):
                    candidate(basis=basis, raw=raw)

    def test_candidate_evidence_dates_and_coverage_must_match(self):
        c = candidate()
        for changes in ({"dates": replace(c.dates, recorded_at=NOW)},
                        {"evidence": replace(c.evidence, observed_at=NOW+timedelta(seconds=1),
                            dates=replace(c.dates, observed_at=NOW+timedelta(seconds=1)))},
                        {"event_payload": replace(c.event_payload, payload=dict(c.event_payload.payload, evidence_hash=H))},
                        {"assessment": assessment(evidence_hash=H)}):
            with self.assertRaises(ValueError):
                replace(c, **changes)
        coverage = ExistingCoverage(c.identity, UUID(int=5), H, "live")
        with self.assertRaises(ValueError):
            replace(c, existing_coverage=coverage)
        covered = replace(c, existing_coverage=coverage,
                          assessment=assessment(evidence_hash=c.evidence.content_hash, disposition=Disposition.COVERED_EXISTING))
        self.assertFalse(covered.importable)

    def test_dependencies_missing_C_D_and_conservative_B_block_child(self):
        c = candidate(EventType.CUSTOMER_PAYMENT_RECEIVED)
        for parent in (None, *(assessment(cat) for cat in (Classification.AMBIGUOUS,
                       Classification.NOT_AUTOMATICALLY_TRANSFORMABLE, Classification.OBSERVED_STATE))):
            blocked = replace(c, dependencies=(replace(c.dependencies[0], parent_assessment=parent),))
            self.assertFalse(blocked.importable)

    def test_dependencies_cross_business_self_unknown_extra_rejected(self):
        c = candidate(EventType.BANK_TRANSACTION_MATCHED)
        dep = c.dependencies[0]
        for target in (replace(dep.target, source=replace(dep.target.source, business_id=2)), c.identity):
            with self.assertRaises(ValueError):
                replace(c, dependencies=(replace(dep, target=target), *c.dependencies[1:]))
        with self.assertRaises(ValueError):
            replace(c, dependencies=())
        with self.assertRaises(ValueError):
            replace(c, dependencies=(*c.dependencies, dep))
        with self.assertRaises(TypeError):
            HistoricalDependency(RelationType.MATCHES, "same amount/date", assessment())

    def test_dependency_order_is_canonical(self):
        c = candidate(EventType.BANK_TRANSACTION_MATCHED)
        self.assertEqual(c.canonical_bytes(), replace(c, dependencies=tuple(reversed(c.dependencies))).canonical_bytes())

    def test_correction_revision_and_rectification_source_are_not_invented(self):
        c = candidate(EventType.SUPPLIER_INVOICE_CORRECTED, revision=2)
        dep = c.dependencies[0]
        with self.assertRaises(ValueError):
            replace(c, dependencies=(replace(dep, target=replace(dep.target, revision=c.identity.revision)),))
        rect = candidate(EventType.INVOICE_RECTIFIED)
        with self.assertRaises(ValueError):
            replace(rect, dependencies=(replace(rect.dependencies[0], target=identity(EventType.INVOICE_ISSUED)),))

    def test_canonical_reorder_null_decimal_date_enum_unicode_lists_maps(self):
        a = {"unicode": "á €", "decimal": Decimal("1.20"), "unknown": None, "date": date(2026, 9, 1),
             "enum": Classification.OBSERVED_STATE, "list": [None, {"y": "2", "x": "1"}]}
        b = dict(reversed(list(a.items())))
        b["list"] = [None, {"x": "1", "y": "2"}]
        self.assertEqual(canonical_bytes(a), canonical_bytes(b))
        self.assertIn('"decimal":"1.20"', canonical_bytes(a).decode())
        self.assertNotEqual(canonical_bytes(a), canonical_bytes(dict(a, unknown="0.00")))
        self.assertNotEqual(canonical_bytes([1, 2]), canonical_bytes([2, 1]))
        self.assertNotEqual(canonical_bytes("é"), canonical_bytes("e\u0301"))
        with self.assertRaises(TypeError):
            canonical_bytes({"money": [0.1]})
        for value in (Decimal("NaN"), Decimal("Infinity"), datetime(2026, 10, 2), "\ud800"):
            with self.assertRaises((ValueError, UnicodeEncodeError)):
                canonical_bytes(value)

    def test_immutable_copy_and_relevant_change_hash(self):
        source = {"values": [{"value": "1"}]}
        copied = freeze(source)
        source["values"][0]["value"] = "2"
        self.assertEqual(copied["values"][0]["value"], "1")
        c = candidate()
        with self.assertRaises(FrozenInstanceError):
            c.identity = identity()
        with self.assertRaises(TypeError):
            c.evidence.money["total"] = raw_exact("20")
        self.assertNotEqual(c.content_hash, replace(c, assessment=replace(c.assessment, severity=Severity.WARNING)).content_hash)

    def test_closed_incidence_catalog_and_decision_requires_evidence(self):
        self.assertEqual(len(IncidenceCode), 14)
        inc = HistoricalIncidence(identity().source, H, IncidenceCode.REQUIRED_VALUE_UNKNOWN,
                                  assessment(Classification.AMBIGUOUS))
        decision = HistoricalDecision(inc, DecisionKind.KEEP_BLOCKED, 3, NOW, (), None)
        self.assertIs(decision.incidence.assessment.severity, Severity.INFO)
        for kind in (DecisionKind.ADD_EVIDENCE, DecisionKind.SELECT_SUPPORTED_INTERPRETATION):
            with self.assertRaises(ValueError):
                replace(decision, kind=kind)
        ref = EvidenceReference(1, EvidenceSource.DOCUMENT, 1, OTHER_H)
        supported = replace(decision, kind=DecisionKind.SELECT_SUPPORTED_INTERPRETATION,
                            evidence=(ref,), interpretation_hash=OTHER_H)
        self.assertEqual(supported.recorded_by, 3)
        excluded = replace(decision, kind=DecisionKind.EXCLUDE)
        self.assertIs(excluded.incidence.assessment.classification, Classification.AMBIGUOUS)
        self.assertIs(excluded.incidence.assessment.disposition, Disposition.PENDING_INCIDENCE)

    def test_privacy_no_blobs_conversations_free_notes(self):
        c = candidate()
        for key in ("pdf", "xml", "image", "conversation", "note"):
            with self.assertRaises(ValueError):
                replace(c.evidence, money={key: raw_exact()})
            with self.assertRaises(TypeError):
                replace(c.evidence, **{key: "contenido"})
        for content in (b"PDF", {"conversation": "full"}, "archivo completo"):
            with self.assertRaises(TypeError):
                replace(c.evidence, references=(content,))
        with self.assertRaises(ValueError):
            EvidenceReference(1, "conversation", 1, H)

    def test_internal_audit_context_no_permission_grant_or_creator_impersonation(self):
        ctx = HistoricalAuditContext(1, 3, UUID(int=10), UUID(int=11), H, "historical.audit")
        self.assertTrue(ctx.matches(identity(), H))
        self.assertFalse(ctx.matches(identity(bid=2), H))
        self.assertFalse(ctx.matches(identity(), OTHER_H))
        with self.assertRaises(ValueError):
            replace(ctx, permission="financial.execute")
        with self.assertRaises(TypeError):
            replace(ctx, original_actor=3)

    def test_authorization_kind_namespace_and_state_closed(self):
        auth = HistoricalAuthorization(3, None, None, "historical", "historical_unknown",
                                       "historical.record", "prepared")
        for changes in ({"actor_user_id": 3}, {"actor_session_version": 0}, {"recorded_by": None},
                        {"namespace": EntryNamespace.WEB_API}, {"kind": AuthorizationKind.HUMAN},
                        {"kind": AuthorizationKind.MANDATE}, {"permission": "financial.authorize"},
                        {"state": OperationState.APPROVED}, {"state": OperationState.COMMITTED}):
            with self.assertRaises((ValueError, StateError)):
                replace(auth, **changes)

    def test_module_has_no_data_or_execution_dependencies(self):
        root = Path(__file__).parents[1] / "src/noesis/financial_history"
        pure_modules = {"__init__", "canonical", "contracts", "money_evidence", "payloads"}
        self.assertTrue(pure_modules <= {p.stem for p in root.glob("*.py")})
        import ast
        for path in root.glob("*.py"):
            if path.stem not in pure_modules:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn(node.module, ("noesis.db", "noesis.financial_writers", "noesis.invoice_capture",
                        "noesis.payment_capture", "noesis.purchasing_capture", "noesis.financial_operations.service"))

    def test_five_flags_and_schema_unchanged(self):
        from noesis import config, migrations
        for name in ("FINANCIAL_CORE_ENABLED", "LEDGER_REPORTING_ENABLED", "OPEN_ITEMS_ENABLED",
                     "NEW_TAX_ENGINE_ENABLED", "NEW_BANK_RECONCILIATION_ENABLED"):
            self.assertFalse(getattr(config, name))
        self.assertEqual(migrations.LATEST_VERSION, 75)


if __name__ == "__main__":
    unittest.main()
