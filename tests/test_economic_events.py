"""Contratos económicos sin conexiones, productores ni efectos financieros."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, Inexact, localcontext
import json
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import UUID

from noesis.economic_events.contracts import (
    CATALOG, EconomicEvent, EventRelation, EventType, FutureImpact, RelationType,
    SourceType, canonical_payload, payload_hash, validate_payload,
)


INVOICE = {"invoice_number": "2026/1", "invoice_kind": "F1", "issued_on": "2026-10-02",
           "base": "100.00", "vat_amount": "21.00", "irpf_amount": "15.00", "total": "106.00"}
SUPPLIER = {"total": "121.00", "issued_on": None}
EXPENSE = {"total": "10.00", "spent_on": None, "description": "Material"}
PAYLOADS = {
    EventType.INVOICE_ISSUED: INVOICE,
    EventType.INVOICE_RECTIFIED: dict(INVOICE, invoice_kind="R1", reason="Diferencias", rectification_method="I",
                                     base="-100", vat_amount="-21", irpf_amount="-15", total="-106"),
    EventType.CUSTOMER_PAYMENT_RECEIVED: {"invoice_id": 1, "amount": "10", "received_on": "2026-10-02"},
    EventType.SUPPLIER_INVOICE_CONFIRMED: dict(SUPPLIER, confirmed_on="2026-10-02"),
    EventType.SUPPLIER_INVOICE_CORRECTED: {"before": SUPPLIER, "after": dict(SUPPLIER, total="150"),
                                        "corrected_on": "2026-10-02", "reason": "Total corregido"},
    EventType.SUPPLIER_INVOICE_VOIDED: {"before": SUPPLIER, "voided_on": "2026-10-02", "reason": "Duplicado"},
    EventType.EXPENSE_CONFIRMED: dict(EXPENSE, confirmed_on="2026-10-02"),
    EventType.EXPENSE_VOIDED: {"before": EXPENSE, "voided_on": "2026-10-02", "reason": "Duplicado"},
    EventType.BANK_TRANSACTION_IMPORTED: {"amount": "-10", "booked_on": None, "imported_on": "2026-10-02"},
    EventType.BANK_TRANSACTION_MATCHED: {"amount": "10", "invoice_payment_id": 1, "matched_on": "2026-10-02"},
    EventType.INVOICE_FISCAL_CANCELLATION_REGISTERED: {
        "invoice_id": 1, "invoice_number": "2026/1", "original_total": "106",
        "registered_on": "2026-10-02", "reason": "Registro de anulación fiscal"},
}
NOW = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)


def event(kind=EventType.INVOICE_ISSUED, **changes):
    spec = CATALOG[kind]
    relations = tuple(EventRelation(rule.kind, UUID(int=index + 2), rule.targets[0], 1)
                      for index, rule in enumerate(spec.relations))
    args = dict(event_id=UUID(int=1), business_id=1, event_type=kind, source_type=spec.source_type,
                source_id=1, source_revision=1, occurred_at=NOW, observed_at=NOW,
                payload=PAYLOADS[kind], relations=relations)
    return EconomicEvent(**dict(args, **changes))


class EconomicEventsTest(unittest.TestCase):
    def test_catalog_is_exact_and_immutable(self):
        expected = {
            "invoice.issued", "invoice.rectified", "customer_payment.received",
            "supplier_invoice.confirmed", "supplier_invoice.corrected", "supplier_invoice.voided",
            "expense.confirmed", "expense.voided", "bank_transaction.imported",
            "bank_transaction.matched", "invoice.fiscal_cancellation_registered",
        }
        self.assertEqual({item.value for item in CATALOG}, expected)
        self.assertEqual(set(CATALOG), set(EventType))
        with self.assertRaises(TypeError):
            CATALOG[EventType.INVOICE_ISSUED] = None

    def test_all_types_valid_and_serializable_as_decimal_strings(self):
        for kind, spec in CATALOG.items():
            with self.subTest(kind=kind):
                item = event(kind)
                self.assertEqual(item.payload_version, 1)
                self.assertIs(item.source_type, spec.source_type)
                parsed = json.loads(item.canonical_bytes())
                self.assertIsInstance(parsed["amount"], str if item.amount is not None else type(None))
                self.assertEqual(len(item.payload_hash), 64)
                self.assertEqual(len(item.content_hash), 64)

    def test_unknown_and_operational_types_rejected(self):
        for kind in ("quote.accepted", "job.completed", "supplier_payment.made", "invoice.draft",
                     "invoice.paid", "unknown", "", None):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_payload(kind, INVOICE)

    def test_unknown_versions_rejected(self):
        for version in (0, 2, -1, "1", True, None, 1.0):
            with self.subTest(version=version), self.assertRaises(ValueError):
                event(payload_version=version)

    def test_missing_required_and_extra_fields_for_every_type(self):
        for kind, spec in CATALOG.items():
            for field in spec.fields:
                if not field.optional:
                    raw = dict(PAYLOADS[kind])
                    del raw[field.name]
                    with self.subTest(kind=kind, missing=field.name), self.assertRaises(ValueError):
                        validate_payload(kind, raw)
            for extra in ("approved_by_ai", "posting", "currency", "anything"):
                with self.subTest(kind=kind, extra=extra), self.assertRaises(ValueError):
                    validate_payload(kind, dict(PAYLOADS[kind], **{extra: True}))

    def test_closed_nested_snapshots(self):
        for kind, key in ((EventType.SUPPLIER_INVOICE_CORRECTED, "after"),
                          (EventType.SUPPLIER_INVOICE_VOIDED, "before"),
                          (EventType.EXPENSE_VOIDED, "before")):
            raw = dict(PAYLOADS[kind])
            raw[key] = dict(raw[key], paid=True)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_payload(kind, raw)

    def test_invalid_money_and_float_rejected_everywhere(self):
        invalid = (0.1, True, 10, None, "NaN", Decimal("NaN"), Decimal("Infinity"),
                   "1e2", "1,20", " 1", "10000000000000000", "0.001", "-0.005",
                   Decimal("1E-100000"), b"1", {})
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises((TypeError, ValueError)):
                validate_payload(EventType.EXPENSE_CONFIRMED,
                                 dict(PAYLOADS[EventType.EXPENSE_CONFIRMED], total=raw))
        for kind, spec in CATALOG.items():
            for field in spec.fields:
                if field.kind == "money":
                    with self.subTest(kind=kind, field=field.name), self.assertRaises(TypeError):
                        validate_payload(kind, dict(PAYLOADS[kind], **{field.name: 0.1}))
        raw = dict(PAYLOADS[EventType.SUPPLIER_INVOICE_CORRECTED], after=dict(SUPPLIER, total=0.1))
        with self.assertRaises(TypeError):
            validate_payload(EventType.SUPPLIER_INVOICE_CORRECTED, raw)

    def test_decimal_exactness_without_global_context_or_silent_rounding(self):
        raw = dict(PAYLOADS[EventType.EXPENSE_CONFIRMED], total=Decimal("9999999999999999.99"))
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            item = event(EventType.EXPENSE_CONFIRMED, payload=raw)
            self.assertEqual(item.amount, Decimal("9999999999999999.99"))
            self.assertEqual(json.loads(item.canonical_bytes())["amount"], "9999999999999999.99")
        self.assertEqual(canonical_payload(EventType.EXPENSE_CONFIRMED, dict(raw, total="10.0000")),
                         canonical_payload(EventType.EXPENSE_CONFIRMED, dict(raw, total=Decimal("10"))))

    def test_currency_and_source_mismatch(self):
        for currency in ("USD", "eur", "XXX", None, ""):
            with self.subTest(currency=currency), self.assertRaises(ValueError):
                event(currency=currency)
            with self.assertRaises(ValueError):
                payload_hash(EventType.INVOICE_ISSUED, INVOICE, currency=currency)
        with self.assertRaises(ValueError):
            event(source_type=SourceType.EXPENSE)

    def test_invalid_identifiers(self):
        for field in ("business_id", "source_id", "source_revision"):
            for value in (None, True, "1", 1.0, 0, -1, 2**63):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    event(**{field: value})
        for value in ("bad", UUID(int=0), 123, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                event(event_id=value)

    def test_amount_signs_and_breakdown(self):
        for kind in (EventType.CUSTOMER_PAYMENT_RECEIVED, EventType.BANK_TRANSACTION_MATCHED):
            for value in ("0", "-1"):
                with self.subTest(kind=kind, value=value), self.assertRaises(ValueError):
                    validate_payload(kind, dict(PAYLOADS[kind], amount=value))
        with self.assertRaises(ValueError):
            validate_payload(EventType.BANK_TRANSACTION_IMPORTED,
                             dict(PAYLOADS[EventType.BANK_TRANSACTION_IMPORTED], amount="-0"))
        for raw in (dict(INVOICE, total="107"), dict(INVOICE, invoice_kind="R1"),
                    dict(INVOICE, base="-100", vat_amount="-21", irpf_amount="-15", total="-106")):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_payload(EventType.INVOICE_ISSUED, raw)
        raw = dict(PAYLOADS[EventType.SUPPLIER_INVOICE_CONFIRMED], base="100", vat_amount="21", irpf_amount="0")
        self.assertEqual(validate_payload(EventType.SUPPLIER_INVOICE_CONFIRMED, raw)["total"], Decimal("121"))
        for raw in (dict(raw, total="122"), dict(raw, vat_amount="-1")):
            with self.assertRaises(ValueError):
                validate_payload(EventType.SUPPLIER_INVOICE_CONFIRMED, raw)
        for value in ("0", "-1"):
            with self.assertRaises(ValueError):
                validate_payload(EventType.EXPENSE_CONFIRMED, dict(PAYLOADS[EventType.EXPENSE_CONFIRMED], total=value))
        for value in ("-1", "11"):
            with self.assertRaises(ValueError):
                validate_payload(EventType.EXPENSE_CONFIRMED, dict(PAYLOADS[EventType.EXPENSE_CONFIRMED], vat_amount=value))

    def test_dates_unknowns_and_utc_instants(self):
        item = event(EventType.EXPENSE_CONFIRMED, occurred_at=None)
        self.assertIsNone(item.economic_date)
        self.assertIsNone(item.occurred_at)
        for value in ("2026-02-30", "20261002", "2026-1-2", NOW, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                event(payload=dict(INVOICE, issued_on=value))
        self.assertEqual(event(payload=dict(INVOICE, issued_on=date(2026, 10, 2))).economic_date,
                         date(2026, 10, 2))
        for value in (NOW.replace(tzinfo=None), "2026-10-02", None):
            with self.assertRaises(ValueError):
                event(observed_at=value)
        equivalent = NOW.astimezone(timezone(timedelta(hours=2)))
        self.assertEqual(event(occurred_at=equivalent, observed_at=equivalent).canonical_bytes(),
                         event().canonical_bytes())

    def test_required_relations_for_all_linked_types(self):
        for kind, spec in CATALOG.items():
            if spec.relations:
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    event(kind, relations=())
                relation = event(kind).relations[0]
                for change in ({"business_id": 2}, {"target_event_id": UUID(int=1)},
                               {"target_event_type": EventType.EXPENSE_VOIDED}):
                    relations = list(event(kind).relations)
                    relations[0] = replace(relation, **change)
                    with self.subTest(kind=kind, change=change), self.assertRaises(ValueError):
                        event(kind, relations=relations)
                with self.assertRaises(ValueError):
                    event(kind, relations=event(kind).relations * 2)
        with self.assertRaises(ValueError):
            event(relations=(EventRelation(RelationType.CORRECTS, UUID(int=2), EventType.INVOICE_ISSUED, 1),))

    def test_effect_semantics_do_not_duplicate_money(self):
        self.assertEqual(event(EventType.SUPPLIER_INVOICE_CORRECTED).amount, Decimal("150"))
        self.assertEqual(event(EventType.SUPPLIER_INVOICE_VOIDED).amount, Decimal("121"))
        self.assertEqual(event(EventType.INVOICE_RECTIFIED).amount, Decimal("-106"))
        self.assertIsNone(event(EventType.INVOICE_FISCAL_CANCELLATION_REGISTERED).amount)
        for kind in (EventType.BANK_TRANSACTION_MATCHED, EventType.INVOICE_FISCAL_CANCELLATION_REGISTERED):
            self.assertEqual(CATALOG[kind].future_impacts, (FutureImpact.EVIDENCE,))
        self.assertNotIn(FutureImpact.GL, CATALOG[EventType.BANK_TRANSACTION_IMPORTED].future_impacts)

    def test_canonical_order_precision_optionals_and_hash(self):
        reversed_payload = dict(reversed(list(INVOICE.items())))
        self.assertEqual(canonical_payload(EventType.INVOICE_ISSUED, INVOICE),
                         canonical_payload(EventType.INVOICE_ISSUED, reversed_payload))
        self.assertEqual(payload_hash(EventType.INVOICE_ISSUED, INVOICE),
                         payload_hash(EventType.INVOICE_ISSUED, reversed_payload))
        self.assertEqual(event().content_hash, event(payload=reversed_payload).content_hash)
        self.assertEqual(event().payload_hash, event(payload=dict(INVOICE, due_on=None)).payload_hash)
        self.assertNotEqual(event().payload_hash, event(payload=dict(INVOICE, invoice_number="2026/2")).payload_hash)
        self.assertNotEqual(event().payload_hash,
                            event(payload=dict(INVOICE, base="110", total="116")).payload_hash)
        self.assertNotEqual(event().payload_hash,
                            event(payload=dict(INVOICE, issued_on="2026-10-03")).payload_hash)
        self.assertEqual(event().payload_hash, event(event_id=UUID(int=100)).payload_hash)
        self.assertNotEqual(event().content_hash, event(event_id=UUID(int=100)).content_hash)
        changed = dict(INVOICE, invoice_kind="R1", reason="Corrección", rectification_method="I")
        self.assertNotEqual(event().payload_hash, event(EventType.INVOICE_RECTIFIED, payload=changed).payload_hash)
        self.assertEqual(event(EventType.BANK_TRANSACTION_MATCHED).canonical_bytes(),
                         event(EventType.BANK_TRANSACTION_MATCHED,
                               relations=tuple(reversed(event(EventType.BANK_TRANSACTION_MATCHED).relations))).canonical_bytes())

    def test_canonical_golden_vector_and_typed_hash(self):
        kind = EventType.EXPENSE_CONFIRMED
        expected = (b'{"confirmed_on":"2026-10-02","description":"Material",'
                    b'"spent_on":null,"total":"10.00","vat_amount":null}')
        self.assertEqual(canonical_payload(kind, PAYLOADS[kind]), expected)
        typed = (b'{"canonical_version":1,"currency":"EUR","event_type":"expense.confirmed",'
                 b'"payload":' + expected + b',"payload_version":1}')
        self.assertEqual(payload_hash(kind, PAYLOADS[kind]), hashlib.sha256(typed).hexdigest())

    def test_all_field_order_permutations_have_identical_content(self):
        import itertools
        raw = PAYLOADS[EventType.BANK_TRANSACTION_IMPORTED]
        expected = canonical_payload(EventType.BANK_TRANSACTION_IMPORTED, raw)
        for order in itertools.permutations(raw):
            self.assertEqual(canonical_payload(EventType.BANK_TRANSACTION_IMPORTED,
                                              {key: raw[key] for key in order}), expected)

    def test_mapping_and_null_validation(self):
        for raw in (None, [], "{}", {1: "x"}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_payload(EventType.INVOICE_ISSUED, raw)
        with self.assertRaises(ValueError):
            event(source_type="quote")
        with self.assertRaises(ValueError):
            event(EventType.INVOICE_RECTIFIED, payload=dict(PAYLOADS[EventType.INVOICE_RECTIFIED], reason=None))
        with self.assertRaises(ValueError):
            event(EventType.INVOICE_RECTIFIED,
                  payload=dict(PAYLOADS[EventType.INVOICE_RECTIFIED], rectification_method="S"))
        for raw in ([], "received", None):
            with self.assertRaises(ValueError):
                event(EventType.CUSTOMER_PAYMENT_RECEIVED, relations=(raw,))

    def test_snapshots_and_envelope_are_immutable_after_input_mutation(self):
        before, after = dict(SUPPLIER), dict(SUPPLIER, total="150")
        raw = dict(PAYLOADS[EventType.SUPPLIER_INVOICE_CORRECTED], before=before, after=after)
        item = event(EventType.SUPPLIER_INVOICE_CORRECTED, payload=raw)
        canonical = item.canonical_bytes()
        after["total"] = "999"
        raw["reason"] = "Otro"
        self.assertEqual(item.canonical_bytes(), canonical)
        with self.assertRaises(TypeError):
            item.payload["after"]["total"] = Decimal("999")
        with self.assertRaises(FrozenInstanceError):
            item.business_id = 2

    def test_text_and_json_are_bounded_and_utf8(self):
        for value in ("", "  ", "x" * 2049, 1, "\ud800"):
            with self.subTest(value=repr(value)), self.assertRaises((ValueError, UnicodeError)):
                event(payload=dict(INVOICE, invoice_number=value))
        self.assertIn("Número".encode(), event(payload=dict(INVOICE, invoice_number="Número")).canonical_bytes())

    def test_no_database_or_producer_dependencies_and_no_effect(self):
        from noesis import db
        with patch.object(db, "get_conn", side_effect=AssertionError("Sin acceso a datos")):
            for kind in CATALOG:
                event(kind).canonical_bytes()
        source = (Path(__file__).parents[1] / "src/noesis/economic_events/contracts.py").read_text(encoding="utf-8")
        self.assertNotIn("from noesis import db", source)
        self.assertNotIn("FinancialSession", source)


if __name__ == "__main__":
    unittest.main()
