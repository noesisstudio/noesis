"""Invariantes idénticas en dos motores, exclusivamente sobre fixtures nuevas."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
from unittest.mock import patch
from uuid import uuid4

from tests.history_legacy_schema import legacy_history71

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.economic_events.contracts import (
    CATALOG,
    EconomicEvent,
    EventRelation,
    EventType,
    RelationType,
)
from noesis.economic_events.repository import EventsRepository
from noesis.economic_events.service import EconomicEvents, COMMANDS
from noesis.financial_operations.contracts import (
    AccessDenied,
    ConflictError,
    EntryIdentity,
    FinancialRequest,
    Principal,
    StateError,
)
from noesis.financial_operations.service import FinancialOperations
from tests.test_economic_events import NOW, PAYLOADS

SYNTHETIC_ISSUER_NIF = "A12345678"  # pragma: allowlist secret
SYNTHETIC_PRODUCER_NIF = "B87654321"  # pragma: allowlist secret


class EconomicPersistenceContract:
    def test_empty_migration_roundtrip_preserves_legacy_sources(self):
        # Cada motor conserva las fuentes sintéticas existentes sin backfill.
        if config.DATABASE_URL:
            # La clase PG comparte esquema; probar la bajada vacía en otro, sin
            # retirar los eventos de pruebas anteriores.
            from urllib.parse import quote

            schema = "phase13_migration_" + uuid4().hex
            with db.get_conn() as conn:
                conn.execute(f"CREATE SCHEMA {schema}")
            url = self.original_url + "?options=" + quote("-csearch_path=" + schema)
            db.close_pool()
            try:
                with patch.object(config, "DATABASE_URL", url):
                    migrations.upgrade(62)
                    self.seed()
                    migrations.upgrade()
                    self._empty_migration_roundtrip()
                    db.close_pool()
            finally:
                with db.get_conn() as conn:
                    conn.execute(f"DROP SCHEMA {schema} CASCADE")
                db.close_pool()
        else:
            self._empty_migration_roundtrip()

    def _empty_migration_roundtrip(self):
        self.assertEqual(migrations.downgrade(62), 62)
        self.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)
        with db.get_conn() as conn:
            for kind, table in (("invoice", "invoices"), ("expense", "expenses")):
                self.assertIsNotNone(
                    conn.execute(
                        f"SELECT id FROM {table} WHERE business_id=? AND id=?",
                        (self.bid, self.sources[kind]),
                    ).fetchone()
                )
            self.assertIsNone(conn.execute("SELECT 1 FROM economic_events LIMIT 1").fetchone())

    def seed(self):
        self.business = db.create_business("Eventos sintéticos", uuid4().hex + "@example.test")
        self.other = db.create_business("Otra empresa", uuid4().hex + "@example.test")
        self.user = db.create_user(
            uuid4().hex + "@example.test", "hash de fixture", self.business["id"]
        )
        self.other_user = db.create_user(
            uuid4().hex + "@example.test", "hash de fixture", self.other["id"]
        )
        self.principal = Principal(self.user["id"], 0)
        self.bid = self.business["id"]
        client = db.add_client(
            "Cliente sintético", nif="B12345674", address="Calle Fixture 1", business_id=self.bid
        )  # pragma: allowlist secret
        invoice = db.add_invoice(client["id"], "Fixture", 100, business_id=self.bid)
        self.sources = {"invoice": invoice["id"]}
        with db.get_conn() as conn:
            for kind, table, columns, args in (
                (
                    "invoice_payment",
                    "invoice_payments",
                    "business_id,invoice_id,amount,paid_at,created_at",
                    (self.bid, invoice["id"], 10, NOW.isoformat(), NOW.isoformat()),
                ),
                (
                    "received_invoice",
                    "received_invoices",
                    "business_id,total,created_at",
                    (self.bid, 121, NOW.isoformat()),
                ),
                (
                    "expense",
                    "expenses",
                    "business_id,concept,amount,created_at",
                    (self.bid, "Fixture", 10, NOW.isoformat()),
                ),
                (
                    "bank_transaction",
                    "bank_transactions",
                    "business_id,import_hash,booked_on,amount,created_at",
                    (self.bid, uuid4().hex, "2026-10-02", 10, NOW.isoformat()),
                ),
            ):
                self.sources[kind] = conn.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ("
                    + ",".join("?" for _ in args)
                    + ") RETURNING id",
                    args,
                ).fetchone()["id"]

    @contextmanager
    def transaction(self):
        with db.get_conn() as conn:
            if conn.dialect == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
            session = FinancialSession(conn)
            yield EconomicEvents(session, self.bid), session

    def make_event(
        self, kind=EventType.EXPENSE_CONFIRMED, *, revision=1, relations=(), payload=None, **changes
    ):
        spec = CATALOG[kind]
        raw = dict(PAYLOADS[kind]) if payload is None else dict(payload)
        if "invoice_id" in raw:
            raw["invoice_id"] = self.sources["invoice"]
        if "invoice_payment_id" in raw:
            raw["invoice_payment_id"] = self.sources["invoice_payment"]
        return EconomicEvent(
            **dict(
                dict(
                    event_id=uuid4(),
                    business_id=self.bid,
                    event_type=kind,
                    source_type=spec.source_type,
                    source_id=self.sources[spec.source_type.value],
                    source_revision=revision,
                    occurred_at=None,
                    observed_at=NOW,
                    payload=raw,
                    relations=relations,
                ),
                **changes,
            )
        )

    def operation(self, event, *, approved=True, historical=False):
        command = next(k for k, v in COMMANDS.items() if event.event_type.value in v)
        service = FinancialOperations(self.bid)
        request = FinancialRequest(
            command, event.source_id, event.amount, date(2026, 10, 2), None, "Fixture", {}
        )
        identity = (EntryIdentity.historical(event.source_type.value, event.source_id, event.source_revision)
                    if historical else EntryIdentity.web_api(uuid4()))
        op = service.prepare(self.principal, identity, request)
        if approved:
            op = service.authorize(
                self.principal,
                op.operation_uuid,
                channel="web_api",
                approved_hash=request.request_hash,
                approved_revision=None,
            )
        return op

    def append(self, event=None, *, operation=None, **kwargs):
        event = event or self.make_event()
        op = operation or self.operation(event)
        with self.transaction() as (service, _):
            return service.append(
                self.principal,
                event,
                operation_uuid=op.operation_uuid,
                event_slot="primary",
                revision_reader=lambda *_: event.source_revision,
                **kwargs,
            )

    def relation(self, kind, target):
        return EventRelation(kind, target.event.event_id, target.event.event_type, self.bid)

    def rows(self):
        with db.get_conn() as conn:
            return tuple(
                conn.execute(
                    f"SELECT COUNT(*) AS n FROM {t} WHERE business_id=?", (self.bid,)
                ).fetchone()["n"]
                for t in ("economic_events", "economic_event_links", "economic_event_sequences")
            )

    def test_insert_read_exact_and_unknown_dates(self):
        item = self.make_event(
            payload=dict(
                PAYLOADS[EventType.EXPENSE_CONFIRMED], total=Decimal("9999999999999999.99")
            )
        )
        stored = self.append(item)
        with self.transaction() as (service, session):
            read = service.read(self.principal, item.event_id)
            native = session.execute(
                "SELECT amount FROM economic_events WHERE business_id=? AND event_uuid=?",
                (self.bid, str(item.event_id)),
            ).fetchone()["amount"]
        self.assertEqual(read, stored)
        self.assertEqual(read.event.amount, Decimal("9999999999999999.99"))
        self.assertIsInstance(native, Decimal if session.dialect == "postgres" else str)
        self.assertIsNone(read.event.economic_date)
        self.assertEqual(read.date_precision, "unknown")
        self.assertIsInstance(json.loads(read.event.canonical_bytes())["amount"], str)

    def test_all_eleven_types_and_relations_persist(self):
        invoice = self.append(self.make_event(EventType.INVOICE_ISSUED))
        supplier = self.append(self.make_event(EventType.SUPPLIER_INVOICE_CONFIRMED))
        expense = self.append()
        bank = self.append(self.make_event(EventType.BANK_TRANSACTION_IMPORTED))
        rectified = self.append(
            self.make_event(
                EventType.INVOICE_RECTIFIED,
                revision=2,
                relations=(self.relation(RelationType.RECTIFIES, invoice),),
            )
        )
        payment = self.append(
            self.make_event(
                EventType.CUSTOMER_PAYMENT_RECEIVED,
                relations=(self.relation(RelationType.SETTLES, invoice),),
            )
        )
        corrected = self.append(
            self.make_event(
                EventType.SUPPLIER_INVOICE_CORRECTED,
                revision=2,
                relations=(self.relation(RelationType.CORRECTS, supplier),),
            )
        )
        self.append(
            self.make_event(
                EventType.SUPPLIER_INVOICE_VOIDED,
                revision=3,
                relations=(self.relation(RelationType.VOIDS, corrected),),
            )
        )
        self.append(
            self.make_event(
                EventType.EXPENSE_VOIDED,
                revision=2,
                relations=(self.relation(RelationType.VOIDS, expense),),
            )
        )
        self.append(
            self.make_event(
                EventType.BANK_TRANSACTION_MATCHED,
                revision=2,
                relations=(
                    self.relation(RelationType.MATCHES, payment),
                    self.relation(RelationType.EVIDENCE_FOR, bank),
                ),
            )
        )
        # Registro fiscal local artificial; ninguna llamada AEAT ni datos históricos reales.
        from noesis import config

        db.update_fiscal(self.bid, nif=SYNTHETIC_ISSUER_NIF, address="Calle Fixture 1")
        with patch.object(config, "VERIFACTU_PRODUCER_NIF", SYNTHETIC_PRODUCER_NIF):
            db.update_verifactu_mode(self.bid, True)
            db.issue_invoice(self.sources["invoice"], self.bid)
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE verifactu_outbox SET status='aceptado' WHERE business_id=?", (self.bid,)
                )
            cancelled = db.create_invoice_cancellation_record(
                self.sources["invoice"], self.bid, reason="Registro artificial de prueba"
            )
        self.sources["invoice_cancellation_record"] = cancelled["id"]
        evidence = self.append(
            self.make_event(
                EventType.INVOICE_FISCAL_CANCELLATION_REGISTERED,
                relations=(self.relation(RelationType.EVIDENCE_FOR, invoice),),
            )
        )
        self.assertIsNone(evidence.event.amount)
        self.assertEqual(self.rows(), (11, 8, 1))
        self.assertLess(invoice.business_sequence, rectified.business_sequence)

    def test_dates_timestamps_precision_and_civil_date(self):
        for occurred, spent, precision in (
            (NOW, "2026-10-02", "instant"),
            (None, "2026-10-02", "day"),
            (None, None, "unknown"),
        ):
            event = self.make_event(
                revision=1 if precision == "instant" else 2 if precision == "day" else 3,
                occurred_at=occurred,
                payload=dict(PAYLOADS[EventType.EXPENSE_CONFIRMED], spent_on=spent),
            )
            stored = self.append(event)
            self.assertEqual(stored.date_precision, precision)
            self.assertEqual(stored.event.occurred_at, occurred)
            self.assertEqual(
                stored.event.economic_date, None if spent is None else date(2026, 10, 2)
            )
            self.assertTrue(stored.recorded_at.endswith("+00:00"))

    def test_same_uuid_operation_slot_and_source_revision_replay_or_conflict(self):
        event = self.make_event()
        op = self.operation(event)
        original = self.append(event, operation=op)
        self.assertEqual(self.append(event, operation=op), original)
        for changed in (
            replace(event, payload=dict(event.payload, total="11")),
            replace(event, event_id=uuid4()),
        ):
            with self.assertRaises(ConflictError):
                self.append(changed, operation=op)
        with self.assertRaises(ConflictError):
            self.append(event, operation=self.operation(event))
        self.assertEqual(self.rows(), (1, 0, 1))
        second = self.append(self.make_event(revision=2))
        self.assertEqual(second.business_sequence, 2)

    def test_slot_distinct_allows_two_events_in_one_operation(self):
        inv = self.append(self.make_event(EventType.INVOICE_ISSUED))
        bank = self.append(self.make_event(EventType.BANK_TRANSACTION_IMPORTED))
        pay = self.make_event(
            EventType.CUSTOMER_PAYMENT_RECEIVED,
            relations=(self.relation(RelationType.SETTLES, inv),),
        )
        match = self.make_event(
            EventType.BANK_TRANSACTION_MATCHED,
            revision=2,
            relations=(
                EventRelation(RelationType.MATCHES, pay.event_id, pay.event_type, self.bid),
                self.relation(RelationType.EVIDENCE_FOR, bank),
            ),
        )
        op = self.operation(match)
        with self.transaction() as (service, _):
            p = service.append(
                self.principal,
                pay,
                operation_uuid=op.operation_uuid,
                event_slot="payment",
                revision_reader=lambda *_: 1,
            )
            m = service.append(
                self.principal,
                match,
                operation_uuid=op.operation_uuid,
                event_slot="match",
                revision_reader=lambda *_: 2,
            )
        self.assertEqual(m.business_sequence, p.business_sequence + 1)

    def test_unknown_type_version_invalid_payload_and_hash(self):
        for change in (
            {"event_type": "job.completed"},
            {"event_type": "quote.accepted"},
            {"payload_version": 2},
            {"payload": {}},
            {"payload": dict(PAYLOADS[EventType.EXPENSE_CONFIRMED], total=0.1)},
        ):
            with self.assertRaises((ValueError, TypeError)):
                self.make_event(**change)
        with self.assertRaises(ValueError):
            self.append(expected_hash="0" * 64)
        self.assertEqual(self.rows(), (0, 0, 0))

    def test_database_updates_and_delete_are_always_rejected(self):
        event = self.make_event()
        stored = self.append(event)
        for column, value in (
            ("payload_canonical", "{}"),
            ("amount", "11.00"),
            ("source_id", 999),
            ("event_uuid", str(uuid4())),
            ("economic_date", "2020-01-01"),
            ("source_type", "invoice"),
            ("content_hash", "a" * 64),
        ):
            with self.subTest(column=column), self.assertRaises(db.DatabaseError):
                with db.get_conn() as conn:
                    conn.execute(
                        f"UPDATE economic_events SET {column}=? WHERE business_id=? AND event_uuid=?",
                        (value, self.bid, str(event.event_id)),
                    )
        with self.assertRaises(db.DatabaseError):
            with db.get_conn() as conn:
                conn.execute("DELETE FROM economic_events WHERE business_id=?", (self.bid,))
        with self.transaction() as (service, _):
            self.assertEqual(service.read(self.principal, event.event_id), stored)

    def test_links_duplicate_self_and_immutable_rejected(self):
        original = self.append(self.make_event(EventType.SUPPLIER_INVOICE_CONFIRMED))
        event = self.make_event(
            EventType.SUPPLIER_INVOICE_CORRECTED,
            revision=2,
            relations=(self.relation(RelationType.CORRECTS, original),),
        )
        self.append(event)
        relation = event.relations[0]
        with self.assertRaises(db.DatabaseError):
            with self.transaction() as (service, _):
                service.repo.insert_link(event.event_id, relation, NOW.isoformat())
        with self.assertRaises(db.DatabaseError):
            with self.transaction() as (service, _):
                service.repo.insert_link(
                    event.event_id,
                    replace(relation, target_event_id=event.event_id),
                    NOW.isoformat(),
                )
        for statement in (
            "UPDATE economic_event_links SET relation_type='voids' WHERE business_id=?",
            "DELETE FROM economic_event_links WHERE business_id=?",
        ):
            with self.assertRaises(db.DatabaseError):
                with db.get_conn() as conn:
                    conn.execute(statement, (self.bid,))

    def test_corrective_cycle_is_rejected_by_database(self):
        original = self.append(self.make_event(EventType.SUPPLIER_INVOICE_CONFIRMED))
        first = self.append(
            self.make_event(
                EventType.SUPPLIER_INVOICE_CORRECTED,
                revision=2,
                relations=(self.relation(RelationType.CORRECTS, original),),
            )
        )
        second = self.append(
            self.make_event(
                EventType.SUPPLIER_INVOICE_CORRECTED,
                revision=3,
                relations=(self.relation(RelationType.CORRECTS, first),),
            )
        )
        cycle = EventRelation(
            RelationType.CORRECTS, second.event.event_id, second.event.event_type, self.bid
        )
        with self.assertRaises(db.DatabaseError):
            with self.transaction() as (service, _):
                service.repo.insert_link(first.event.event_id, cycle, NOW.isoformat())

    def test_cross_business_source_operation_authorization_and_event(self):
        event = self.make_event()
        op = self.operation(event)
        other_principal = Principal(self.other_user["id"], 0)
        other_service = FinancialOperations(self.other["id"])
        request = op.request
        foreign = other_service.prepare(other_principal, EntryIdentity.web_api(uuid4()), request)
        foreign = other_service.authorize(
            other_principal,
            foreign.operation_uuid,
            channel="web_api",
            approved_hash=request.request_hash,
            approved_revision=None,
        )
        with self.assertRaises(AccessDenied):
            self.append(event, operation=foreign)
        with self.assertRaises(ValueError):
            self.append(replace(event, source_id=999999))
        with self.transaction() as (service, _):
            with self.assertRaises(AccessDenied):
                service.read(other_principal, event.event_id)
        self.append(event, operation=op)
        with self.assertRaises(db.DatabaseError):
            with self.transaction() as (service, session):
                values = dict(service.repo.load(event.event_id))
                values.pop("id")
                values.update(
                    event_uuid=str(uuid4()),
                    business_sequence=2,
                    operation_uuid=foreign.operation_uuid,
                    authorization_uuid=foreign.authorization_uuid,
                    source_revision=2,
                    idempotency_key="a" * 64,
                    event_slot="other",
                )
                session.execute(
                    "UPDATE economic_event_sequences SET last_sequence=2 WHERE business_id=?",
                    (self.bid,),
                )
                session.execute(
                    "INSERT INTO economic_events ("
                    + ",".join(values)
                    + ") VALUES ("
                    + ",".join("?" for _ in values)
                    + ")",
                    tuple(values.values()),
                )

    def test_live_requires_approval_and_current_permissions(self):
        event = self.make_event()
        op = self.operation(event, approved=False)
        with self.assertRaises(AccessDenied):
            self.append(event, operation=op)
        with self.transaction() as (service, _):
            with self.assertRaises(AccessDenied):
                service.append(
                    self.principal,
                    event,
                    operation_uuid=None,
                    event_slot="primary",
                    revision_reader=lambda *_: 1,
                )
        stored = self.append(event)
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET session_version=1 WHERE id=?", (self.user["id"],))
        with self.transaction() as (service, _):
            with self.assertRaises(AccessDenied):
                service.read(self.principal, stored.event.event_id)

    @legacy_history71
    def test_historical_metadata_without_fake_approval_or_backfill(self):
        event = self.make_event()
        with self.transaction() as (service, _):
            stored = service.append(
                self.principal,
                event,
                operation_uuid=None,
                event_slot="historical",
                origin="historical",
                historical_batch_uuid=str(uuid4()),
                provenance="fixture.explicit",
                revision_reader=lambda *_: 1,
            )
        self.assertIsNone(stored.authorization_uuid)
        self.assertEqual(stored.origin, "historical")
        with self.assertRaises(ValueError):
            with self.transaction() as (service, _):
                service.append(
                    self.principal,
                    self.make_event(revision=2),
                    operation_uuid=None,
                    event_slot="historical",
                    origin="historical",
                    revision_reader=lambda *_: 2,
                )

    def test_revision_reader_is_required_and_stale_revision_rejected(self):
        event = self.make_event()
        op = self.operation(event)
        for reader in (None, lambda *_: 2, lambda *_: True):
            with self.assertRaises((TypeError, StateError)):
                with self.transaction() as (service, _):
                    service.append(
                        self.principal,
                        event,
                        operation_uuid=op.operation_uuid,
                        event_slot="primary",
                        revision_reader=reader,
                    )
        self.assertEqual(self.rows(), (0, 0, 0))

    def test_rollback_after_sequence_event_and_link_even_if_caught(self):
        original = self.append(self.make_event(EventType.SUPPLIER_INVOICE_CONFIRMED))
        event = self.make_event(
            EventType.SUPPLIER_INVOICE_CORRECTED,
            revision=2,
            relations=(self.relation(RelationType.CORRECTS, original),),
        )
        op = self.operation(event)
        before = self.rows()
        for method in ("next_sequence", "insert_link", "insert"):
            actual = getattr(EventsRepository, method)

            def failing(repo, *args, **kwargs):
                actual(repo, *args, **kwargs)
                raise RuntimeError("Fallo después de " + method)

            with patch.object(EventsRepository, method, failing):
                with self.transaction() as (service, _):
                    with self.assertRaises(RuntimeError):
                        service.append(
                            self.principal,
                            event,
                            operation_uuid=op.operation_uuid,
                            event_slot="primary",
                            revision_reader=lambda *_: 2,
                        )
            self.assertEqual(self.rows(), before)
        final = self.append(event, operation=op)
        self.assertEqual(final.business_sequence, original.business_sequence + 1)

    def test_no_cascade_from_source_and_downgrade_preserves_evidence(self):
        event = self.make_event()
        self.append(event)
        with self.assertRaises(db.DatabaseError):
            with db.get_conn() as conn:
                conn.execute(
                    "DELETE FROM expenses WHERE business_id=? AND id=?", (self.bid, event.source_id)
                )
        version_before = migrations.current_version()
        with self.assertRaises(ValueError):
            migrations.downgrade(62)
        self.assertEqual(migrations.current_version(), version_before)
        with self.assertRaises(ValueError):
            db.delete_business_cascade(self.bid)
        self.assertEqual(self.rows(), (1, 0, 1))

    def test_read_revalidates_hash_without_repair(self):
        event = self.make_event()
        self.append(event)
        with self.transaction() as (service, _):
            row = service.repo.load(event.event_id)
            for column, value in (
                ("content_hash", "0" * 64),
                ("payload_canonical", "{}"),
                ("record_hash", "0" * 64),
                ("amount", "11.00"),
            ):
                with self.subTest(column=column), self.assertRaises(ValueError):
                    service._decode(dict(row, **{column: value}))

    def test_monotonic_sequence_and_independent_business_counter(self):
        first = self.append()
        second = self.append(self.make_event(revision=2))
        other = self.foreign_event()
        self.assertEqual(
            (first.business_sequence, second.business_sequence, other.business_sequence), (1, 2, 1)
        )

    def test_database_rejects_mismatched_amount_source_type_and_missing_links(self):
        event = self.make_event()
        stored = self.append(event)
        for changes in (
            {"amount": "11.00"},
            {"source_type": "invoice"},
            {"authorization_uuid": str(uuid4())},
            {"payload_version": 2},
        ):
            with self.subTest(changes=changes), self.assertRaises(db.DatabaseError):
                with self.transaction() as (service, session):
                    self.raw_clone(session, service.repo.load(event.event_id), **changes)
        self.assertEqual(stored.business_sequence, 1)

    @legacy_history71
    def foreign_event(self):
        with db.get_conn() as conn:
            source_id = conn.execute(
                "INSERT INTO expenses (business_id,concept,amount,created_at) VALUES (?,'Fixture',10,?) RETURNING id",
                (self.other["id"], NOW.isoformat()),
            ).fetchone()["id"]
        event = replace(self.make_event(), business_id=self.other["id"], source_id=source_id)
        with db.get_conn() as conn:
            if conn.dialect == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
            service = EconomicEvents(FinancialSession(conn), self.other["id"])
            return service.append(
                Principal(self.other_user["id"], 0),
                event,
                operation_uuid=None,
                event_slot="historical",
                origin="historical",
                historical_batch_uuid=str(uuid4()),
                revision_reader=lambda *_: 1,
            )

    def raw_clone(self, session, base, **changes):
        # Primero formar una fila válida distinta, para que cada fallo aísle su propia invariante.
        row = dict(base)
        row.pop("id")
        from noesis.economic_events.persistence import StoredEvent

        event = replace(StoredEvent.from_row(base).event, event_id=uuid4(), source_revision=2)
        row.update(
            event_uuid=str(event.event_id),
            source_revision=2,
            canonical_event=event.canonical_bytes().decode(),
            content_hash=event.content_hash,
            event_slot="other",
            business_sequence=2,
            idempotency_key=uuid4().hex * 2,
        )
        row.update(changes)
        session.execute(
            "UPDATE economic_event_sequences SET last_sequence=2 WHERE business_id=?", (self.bid,)
        )
        session.execute(
            "INSERT INTO economic_events ("
            + ",".join(row)
            + ") VALUES ("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )

    def test_real_foreign_source_authorization_and_link_are_rejected(self):
        foreign = self.foreign_event()
        with self.assertRaises(ValueError):
            self.append(replace(self.make_event(), source_id=foreign.event.source_id))
        relation = EventRelation(
            RelationType.VOIDS, foreign.event.event_id, foreign.event.event_type, self.bid
        )
        with self.assertRaises(AccessDenied):
            self.append(
                self.make_event(EventType.EXPENSE_VOIDED, revision=2, relations=(relation,))
            )
        with self.assertRaises(db.DatabaseError):
            with self.transaction() as (service, _):
                service.repo.insert_link(uuid4(), relation, NOW.isoformat())
        local = self.append()
        foreign_user = Principal(self.other_user["id"], 0)
        request = FinancialRequest(
            "expense.confirm", foreign.event.source_id, "10", date(2026, 10, 2), None, "Fixture", {}
        )
        operations = FinancialOperations(self.other["id"])
        op = operations.prepare(foreign_user, EntryIdentity.web_api(uuid4()), request)
        op = operations.authorize(
            foreign_user,
            op.operation_uuid,
            channel="web_api",
            approved_hash=request.request_hash,
            approved_revision=None,
        )
        with self.assertRaises(db.DatabaseError):
            with self.transaction() as (service, session):
                self.raw_clone(
                    session,
                    service.repo.load(local.event.event_id),
                    authorization_uuid=op.authorization_uuid,
                )

    def test_missing_or_incompatible_links_cannot_be_durable(self):
        original = self.append(self.make_event(EventType.SUPPLIER_INVOICE_CONFIRMED))
        corrected = self.append(
            self.make_event(
                EventType.SUPPLIER_INVOICE_CORRECTED,
                revision=2,
                relations=(self.relation(RelationType.CORRECTS, original),),
            )
        )
        with self.assertRaises(db.DatabaseError):
            with self.transaction() as (service, session):
                row = dict(service.repo.load(corrected.event.event_id))
                row.pop("id")
                event = replace(corrected.event, event_id=uuid4(), source_revision=3)
                row.update(
                    event_uuid=str(event.event_id),
                    source_revision=3,
                    canonical_event=event.canonical_bytes().decode(),
                    content_hash=event.content_hash,
                    event_slot="missing",
                    business_sequence=3,
                    idempotency_key=uuid4().hex * 2,
                )
                session.execute(
                    "UPDATE economic_event_sequences SET last_sequence=3 WHERE business_id=?",
                    (self.bid,),
                )
                session.execute(
                    "INSERT INTO economic_events ("
                    + ",".join(row)
                    + ") VALUES ("
                    + ",".join("?" for _ in row)
                    + ")",
                    tuple(row.values()),
                )
        with self.assertRaises(db.DatabaseError):
            with self.transaction() as (service, _):
                service.repo.insert_link(
                    original.event.event_id,
                    EventRelation(
                        RelationType.MATCHES,
                        corrected.event.event_id,
                        corrected.event.event_type,
                        self.bid,
                    ),
                    NOW.isoformat(),
                )
        self.assertEqual(self.rows(), (2, 1, 1))

    @legacy_history71
    def test_historical_unknown_receipt_is_preserved_without_human_actor(self):
        event = self.make_event()
        op = self.operation(event, approved=False, historical=True)
        op = FinancialOperations(self.bid).authorize(
            self.principal,
            op.operation_uuid,
            channel="historical",
            approved_hash=op.request.request_hash,
            approved_revision=None,
            kind="historical_unknown",
        )
        with self.transaction() as (service, session):
            stored = service.append(
                self.principal,
                event,
                operation_uuid=op.operation_uuid,
                event_slot="historical",
                origin="historical",
                historical_batch_uuid=str(uuid4()),
                revision_reader=lambda *_: 1,
            )
            auth = session.execute(
                "SELECT actor_user_id FROM financial_authorizations WHERE business_id=? AND authorization_uuid=?",
                (self.bid, stored.authorization_uuid),
            ).fetchone()
        self.assertIsNone(auth["actor_user_id"])
        self.assertEqual(op.state.value, "prepared")

    @legacy_history71
    def test_historical_namespace_cannot_supply_live_event_authority(self):
        event = self.make_event()
        op = self.operation(event, approved=False, historical=True)
        auth = str(uuid4())
        with db.get_conn() as conn:
            conn.execute("INSERT INTO financial_authorizations "
                "(business_id,authorization_uuid,operation_uuid,kind,actor_user_id,recorded_by,actor_session_version,"
                "validated_permission,approved_request_hash,channel,authorized_at) "
                "VALUES (?,?,?,'human_confirmation',?,?,0,'financial.authorize',?,'web_api',?)",
                (self.bid, auth, op.operation_uuid, self.principal.user_id, self.principal.user_id,
                 op.request.request_hash, NOW.isoformat()))
            conn.execute("UPDATE financial_operations SET state='approved',authorization_uuid=? "
                         "WHERE business_id=? AND operation_uuid=?", (auth, self.bid, op.operation_uuid))
        before = self.rows()
        with self.assertRaises(StateError):
            self.append(event, operation=op)
        self.assertEqual(before, self.rows())

    def test_source_payload_parent_ids_are_checked(self):
        original = self.append(self.make_event(EventType.INVOICE_ISSUED))
        event = self.make_event(
            EventType.CUSTOMER_PAYMENT_RECEIVED,
            relations=(self.relation(RelationType.SETTLES, original),),
        )
        bad = replace(event, payload=dict(event.payload, invoice_id=999999))
        with self.assertRaises(ValueError):
            self.append(bad)
        self.assertEqual(self.rows(), (1, 0, 1))

    def test_database_counter_and_business_sequences_are_protected(self):
        self.append()
        for sql in (
            "DELETE FROM economic_event_sequences WHERE business_id=?",
            "UPDATE economic_event_sequences SET last_sequence=0 WHERE business_id=?",
        ):
            with self.assertRaises(db.DatabaseError):
                with db.get_conn() as conn:
                    conn.execute(sql, (self.bid,))
