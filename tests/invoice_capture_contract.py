"""Productor real y contrato compartido SQLite/PostgreSQL de 1.5."""

from dataclasses import replace
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.economic_events.service import EconomicEvents
from noesis.economic_events.repository import EventsRepository
from noesis.financial_operations.contracts import (
    AccessDenied, ConflictError, EntryIdentity, EntryNamespace, OperationState, Principal, StateError,
)
from noesis.financial_operations.repository import OperationsRepository
from noesis.financial_writers import invoices
from noesis.financial_writers.boundary import WriterConnection, snapshot
from noesis.invoice_capture.service import InvoiceCapture
from tests.borrowed_writers_contract import BorrowedWritersContract


class InvoiceCaptureContract:
    seed = BorrowedWritersContract.seed
    draft = BorrowedWritersContract.draft

    def setup_capture(self):
        self.seed()
        self.user = db.create_user(uuid4().hex + "@example.test", "hash fixture", self.bid)
        self.principal = Principal(self.user["id"], 0)
        self.capture = InvoiceCapture(self.bid)
        db.update_verifactu_mode(self.bid, True)

    def approve(self, invoice_id, *, identity=None):
        request = self.capture.review(self.principal, invoice_id)
        op = self.capture.prepare(self.principal, identity or EntryIdentity.web_api(uuid4()), request)
        return self.capture.authorize(self.principal, op.operation_uuid, channel=EntryNamespace.WEB_API,
            approved_hash=request.request_hash, approved_revision=request.expected_revision)

    def captured(self, **kwargs):
        iid = self.draft(**kwargs)["id"]
        operation = self.approve(iid)
        return self.capture.execute(self.principal, operation.operation_uuid)

    def counts(self):
        with db.get_conn() as conn:
            return {table: conn.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE business_id=?", (self.bid,)).fetchone()["n"] for table in
                    ("invoice_records", "invoice_events", "verifactu_outbox", "economic_events", "invoice_economic_coverage")}

    def state(self):
        base = BorrowedWritersContract.state(self)
        with db.get_conn() as conn:
            for table in ("economic_events", "economic_event_links", "economic_event_sequences", "invoice_economic_coverage", "financial_operations", "financial_authorizations"):
                base[table] = [dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE business_id=?", (self.bid,)).fetchall()]
        return base

    def event(self, operation):
        with db.get_conn() as conn:
            return EconomicEvents(FinancialSession(conn), self.bid).read(self.principal, operation.result["event_uuid"])

    def test_f1_f2_lines_taxes_dates_frozen_decimal(self):
        for kind in ("F1", "F2"):
            with self.subTest(kind=kind):
                op = self.captured(invoice_type=kind, operation_date=date.today().isoformat(), irpf_rate=15,
                    lines=[{"description": str(rate), "quantity": "1", "unit_price": "10.05", "vat_rate": rate} for rate in (21, 10, 4, 0)])
                event = self.event(op).event
                self.assertEqual(event.event_type.value, "invoice.issued")
                self.assertEqual(event.payload_version, 2)
                self.assertEqual(event.payload["total"], Decimal("37.69"))
                self.assertEqual(event.payload["operation_on"], date.today().isoformat())
                self.assertEqual(len(event.payload["evidence"]["lines"]), 4)
                self.assertEqual(event.payload["evidence"]["money_provenance"], "legacy_binary_storage")
                self.assertIsNotNone(event.payload["evidence"]["fiscal_record"])
                with self.assertRaises(TypeError):
                    event.payload["evidence"]["lines"][0]["base"] = Decimal("9")
        self.assertEqual(self.counts()["economic_events"], 2)

    def test_captured_evidence_blocks_destructive_account_deletion(self):
        self.captured()
        before = self.state()
        with self.assertRaisesRegex(ValueError, "conserv"):
            db.delete_business_cascade(self.bid)
        self.assertEqual(self.state(), before)
        self.assertIsNotNone(db.get_business(self.bid))

    def test_r1_to_r5_one_primary_original_unchanged(self):
        original = self.captured()
        ticket = self.captured(invoice_type="F2")
        before = db.get_invoice(original.result["invoice_id"], self.bid)
        for kind in ("R1", "R2", "R3", "R4", "R5"):
            parent = ticket if kind == "R5" else original
            draft = db.create_rectifying_invoice(parent.result["invoice_id"], self.bid, concept="Rectificar",
                base="-2.675", invoice_type=kind, reason="Precio incorrecto")
            op = self.approve(draft["id"])
            done = self.capture.execute(self.principal, op.operation_uuid)
            event = self.event(done).event
            self.assertEqual(event.event_type.value, "invoice.rectified")
            self.assertEqual(str(event.relations[0].target_event_id), parent.result["event_uuid"])
            self.assertEqual(event.payload["total"], Decimal("-3.24"))
            self.assertNotEqual(done.result["number"], parent.result["number"])
        self.assertEqual(db.get_invoice(original.result["invoice_id"], self.bid), before)
        with db.get_conn() as conn:
            rows = conn.execute("SELECT event_type,COUNT(*) AS n FROM economic_events WHERE business_id=? GROUP BY event_type", (self.bid,)).fetchall()
        self.assertEqual({r["event_type"]: r["n"] for r in rows}, {"invoice.issued": 2, "invoice.rectified": 5})

    def test_uncaptured_original_fails_closed_no_backfill(self):
        original = db.issue_invoice(self.draft()["id"], self.bid)
        rect = db.create_rectifying_invoice(original["id"], self.bid, concept="Rectificar", base="-1", reason="Error fiscal")
        before = self.state()
        with self.assertRaises(StateError):
            self.capture.review(self.principal, rect["id"])
        self.assertEqual(self.state(), before)

    def test_restrictions_rectifying_unchanged(self):
        full, ticket = self.captured(), self.captured(invoice_type="F2")
        for original, typ in ((full, "R5"), (ticket, "R1")):
            with self.assertRaises(ValueError):
                db.create_rectifying_invoice(original.result["invoice_id"], self.bid, concept="Error", base="-1", invoice_type=typ, reason="Prueba")
        with self.assertRaises(ValueError):
            db.create_rectifying_invoice(full.result["invoice_id"], self.bid, concept="Error", base="-1", rectification_type="S", reason="Prueba")

    def test_replay_timeout_same_entry_uuid_conflicting_content(self):
        iid = self.draft()["id"]
        identity = EntryIdentity.web_api(uuid4())
        approved = self.approve(iid, identity=identity)
        result = self.capture.execute(self.principal, approved.operation_uuid)
        state = self.state()
        for _ in range(3):
            self.assertEqual(self.capture.execute(self.principal, approved.operation_uuid), result)
            self.assertEqual(self.capture.prepare(self.principal, identity, approved.request), result)
        self.assertEqual(self.state(), state)
        with self.assertRaises(ConflictError):
            self.capture.prepare(self.principal, identity, replace(approved.request, amount="120.00"))
        self.assertEqual(self.counts()["economic_events"], 1)

    def test_two_operations_same_invoice_second_stale_no_double_effect(self):
        iid = self.draft()["id"]
        a, b = self.approve(iid), self.approve(iid)
        self.capture.execute(self.principal, a.operation_uuid)
        with self.assertRaises(StateError):
            self.capture.execute(self.principal, b.operation_uuid)
        self.assertEqual(self.counts()["economic_events"], 1)

    def test_nine_failures_full_rollback_retry_same_number(self):
        original_execute = WriterConnection.execute
        real_issue, real_append, real_insert = invoices.issue_invoice, EconomicEvents.append, EventsRepository.insert
        real_transition, real_number = OperationsRepository.transition, db._next_invoice_series_number
        def after(fn):
            def fail(*args, **kwargs):
                fn(*args, **kwargs)
                raise RuntimeError("Fallo inyectado")
            return fail
        def sql_failure(fragment):
            def run(proxy, sql, params=()):
                value = original_execute(proxy, sql, params)
                if fragment in sql:
                    raise RuntimeError("Fallo SQL inyectado")
                return value
            return run
        def result_failure(repo, row, state, *args, **kwargs):
            value = real_transition(repo, row, state, *args, **kwargs)
            if state == OperationState.COMMITTED:
                raise RuntimeError("Resultado durable fallido")
            return value
        failures = [patch.object(invoices, "issue_invoice", after(real_issue)),
                    patch.object(db, "_next_invoice_series_number", after(real_number)),
                    patch.object(WriterConnection, "execute", sql_failure("UPDATE invoices SET status='enviada'")),
                    patch.object(WriterConnection, "execute", sql_failure("INSERT INTO invoice_records")),
                    patch.object(WriterConnection, "execute", sql_failure("INSERT INTO verifactu_outbox")),
                    patch.object(EconomicEvents, "append", side_effect=RuntimeError("Antes del evento")),
                    patch.object(EventsRepository, "insert", after(real_insert)),
                    patch.object(EconomicEvents, "append", after(real_append)),
                    patch.object(OperationsRepository, "transition", result_failure)]
        for index, failure in enumerate(failures):
            with self.subTest(point=index):
                op = self.approve(self.draft()["id"])
                before = self.state()
                with failure, self.assertRaises(RuntimeError):
                    self.capture.execute(self.principal, op.operation_uuid)
                self.assertEqual(self.state(), before)
                done = self.capture.execute(self.principal, op.operation_uuid)
                self.assertTrue(done.result["captured"])
        self.assertEqual(self.counts()["economic_events"], 9)

    def test_stale_line_client_date_amount_fiscal_profile_series(self):
        mutations = [
            ("UPDATE invoice_lines SET description='Cambio' WHERE business_id=? AND invoice_id=?", "invoice"),
            ("UPDATE clients SET address='Otra calle' WHERE business_id=? AND id=?", "client"),
            ("UPDATE invoices SET operation_date='2026-01-01' WHERE business_id=? AND id=?", "invoice"),
            ("UPDATE invoices SET total=122 WHERE business_id=? AND id=?", "invoice"),
            ("UPDATE businesses SET address='Domicilio cambiado' WHERE id=?", "business"),
            ("UPDATE businesses SET document_footer='Texto cambiado' WHERE id=?", "business"),
            ("UPDATE invoice_series SET padding=5 WHERE business_id=? AND id=?", "series"),
        ]
        for sql, target in mutations:
            with self.subTest(target=target, sql=sql):
                draft = self.draft()
                op = self.approve(draft["id"])
                with db.get_conn() as conn:
                    params = (self.bid,) if target == "business" else (self.bid, self.client["id"] if target == "client" else draft["series_id"] if target == "series" else draft["id"])
                    conn.execute(sql, params)
                before = self.state()
                with self.assertRaises(StateError):
                    self.capture.execute(self.principal, op.operation_uuid)
                self.assertEqual(self.state(), before)

    def test_no_authorization_telemetry_failure_and_capture_no_fallback(self):
        iid = self.draft()["id"]
        request = self.capture.review(self.principal, iid)
        op = self.capture.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
        with self.assertRaises(StateError):
            self.capture.execute(self.principal, op.operation_uuid)
        with self.assertRaises(StateError):
            db.issue_invoice(iid, self.bid, capture_requested=True)
        op = self.capture.authorize(self.principal, op.operation_uuid, channel="web_api", approved_hash=request.request_hash, approved_revision=request.expected_revision)
        with patch("noesis.invoice_capture.service.observe", side_effect=RuntimeError("Telemetría")):
            done = self.capture.execute(self.principal, op.operation_uuid)
        self.assertEqual(done.state, OperationState.COMMITTED)

    def test_cross_business_invoice_operation_authorization_event_original(self):
        other = db.create_business("Otra", uuid4().hex + "@example.test")
        user = db.create_user(uuid4().hex + "@example.test", "hash", other["id"])
        outsider = Principal(user["id"], 0)
        original = self.captured()
        with self.assertRaises(AccessDenied):
            self.capture.operations.recover(outsider, original.operation_uuid)
        with self.assertRaises(StateError):
            InvoiceCapture(other["id"]).review(outsider, original.result["invoice_id"])
        op = self.approve(self.draft()["id"])
        with self.assertRaises(AccessDenied):
            InvoiceCapture(other["id"]).execute(outsider, op.operation_uuid)
        with self.assertRaises(AccessDenied):
            with db.get_conn() as conn:
                EconomicEvents(FinancialSession(conn), other["id"]).read(outsider, original.result["event_uuid"])

    def test_coverage_without_event_cannot_commit_even_if_error_caught(self):
        op = self.approve(self.draft()["id"])
        before = self.state()
        with self.assertRaises(Exception):
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("INSERT INTO invoice_economic_coverage (business_id,invoice_id,event_uuid,event_type,operation_uuid) VALUES (?,?,?,'invoice.issued',?)",
                    (self.bid, op.request.target_id, str(uuid4()), op.operation_uuid))
                invoices.issue_invoice(conn, op.request.target_id, self.bid)
                # El llamador podría tragarse un error: las FKs diferidas bloquean commit.
        self.assertEqual(self.state(), before)

    def test_captured_coverage_immutable_and_downgrade_protected(self):
        self.captured()
        for statement in ("DELETE FROM invoice_economic_coverage WHERE business_id=?", "UPDATE invoice_economic_coverage SET event_type='invoice.rectified' WHERE business_id=?"):
            with self.assertRaises(Exception):
                with db.get_conn() as conn:
                    conn.execute(statement, (self.bid,))
        with self.assertRaises(ValueError):
            migrations.downgrade(64)
        self.assertEqual(migrations.current_version(), 65)

    def test_migration_empty_cycle_preserves_legacy(self):
        with self.migration_scope():
            draft = self.draft()
            migrations.downgrade(64)
            self.assertEqual(db.get_invoice(draft["id"], self.bid), draft)
            migrations.upgrade()
            self.assertEqual(db.get_invoice(draft["id"], self.bid), draft)

    @contextmanager
    def migration_scope(self):
        if not config.DATABASE_URL:
            yield
            return
        from urllib.parse import quote
        schema = "phase15_migration_" + uuid4().hex
        with db.get_conn() as conn:
            conn.execute(f"CREATE SCHEMA {schema}")
        url = self.original_url + "?options=" + quote("-csearch_path=" + schema)
        db.close_pool()
        try:
            with patch.object(config, "DATABASE_URL", url):
                migrations.upgrade()
                self.setup_capture()
                yield
                db.close_pool()
        finally:
            with db.get_conn() as conn:
                conn.execute(f"DROP SCHEMA {schema} CASCADE")
            db.close_pool()

    def test_migration_preserves_v1_bytes_links_hashes_with_evidence(self):
        from noesis.economic_events.contracts import EconomicEvent, EventRelation, EventType, RelationType, SourceType
        from noesis.financial_operations.contracts import FinancialRequest
        from noesis.financial_operations.service import FinancialOperations
        from datetime import datetime, timezone
        with self.migration_scope():
            migrations.downgrade(64)
            source = db.add_expense("Fixture v1", "10", business_id=self.bid)
            events = []
            for revision, typ in ((1, "expense.confirmed"), (2, "expense.voided")):
                payload = {"total": "10.00", "spent_on": "2026-10-02", "description": "Fixture"}
                payload = dict(payload, confirmed_on="2026-10-02") if revision == 1 else {"before": payload, "voided_on": "2026-10-02", "reason": "Fixture retirada"}
                service = FinancialOperations(self.bid)
                req = FinancialRequest("expense.confirm" if revision == 1 else "expense.void", source["id"], "10.00", "2026-10-02", None, None, {})
                op = service.prepare(self.principal, EntryIdentity.web_api(uuid4()), req)
                op = service.authorize(self.principal, op.operation_uuid, channel="web_api", approved_hash=req.request_hash, approved_revision=None)
                relations = () if revision == 1 else (EventRelation(RelationType.VOIDS, events[0].event.event_id, EventType.EXPENSE_CONFIRMED, self.bid),)
                event = EconomicEvent(uuid4(), self.bid, typ, SourceType.EXPENSE, source["id"], revision, None, datetime.now(timezone.utc), payload, relations=relations)
                with db.get_conn() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    events.append(EconomicEvents(FinancialSession(conn), self.bid).append(self.principal, event, operation_uuid=op.operation_uuid, event_slot="primary", revision_reader=lambda *_: revision))
            with db.get_conn() as conn:
                before = [dict(row) for row in conn.execute_exact("SELECT * FROM economic_events ORDER BY id").fetchall()]
                links = [dict(row) for row in conn.execute_exact("SELECT * FROM economic_event_links").fetchall()]
            for target in (65, 64, 65):
                migrations.upgrade() if target == 65 else migrations.downgrade(64)
                with db.get_conn() as conn:
                    self.assertEqual([dict(row) for row in conn.execute_exact("SELECT * FROM economic_events ORDER BY id").fetchall()], before)
                    self.assertEqual([dict(row) for row in conn.execute_exact("SELECT * FROM economic_event_links").fetchall()], links)

    def test_v2_without_coverage_and_cross_tenant_authorization_rejected(self):
        from noesis.financial_operations.contracts import FinancialRequest
        from noesis.financial_operations.service import FinancialOperations
        captured = self.captured()
        original = self.event(captured).event
        legacy = db.issue_invoice(self.draft()["id"], self.bid)
        service = FinancialOperations(self.bid)
        request = FinancialRequest("invoice.issue", legacy["id"], "121.00", date.today(), None, None, {})
        op = service.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
        op = service.authorize(self.principal, op.operation_uuid, channel="web_api", approved_hash=request.request_hash, approved_revision=None)
        event = replace(original, event_id=uuid4(), source_id=legacy["id"])
        before = self.state()
        with self.assertRaises(Exception):
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                EconomicEvents(FinancialSession(conn), self.bid).append(self.principal, event,
                    operation_uuid=op.operation_uuid, event_slot="primary", revision_reader=lambda *_: event.source_revision)
        self.assertEqual(self.state(), before)
        draft = self.draft()
        with self.assertRaises(Exception):
            with db.get_conn() as conn:
                conn.execute("INSERT INTO invoice_economic_coverage (business_id,invoice_id,event_uuid,event_type,operation_uuid) VALUES (?,?,?,'invoice.issued',?)", (self.bid, draft["id"], str(uuid4()), op.operation_uuid))

    def test_payload_v2_closed_float_currency_version_invalid(self):
        op = self.captured()
        event = self.event(op).event
        for values in ({"currency": "USD"}, {"payload_version": 3}, {"payload": dict(event.payload, extra="no")}, {"payload": dict(event.payload, total=121.0)}):
            with self.subTest(values=values), self.assertRaises((TypeError, ValueError)):
                replace(event, **values)
        evidence = dict(event.payload["evidence"])
        lines = [dict(line) for line in evidence["lines"]]
        lines[0]["unit_price"] = 100.0
        with self.assertRaises(TypeError):
            replace(event, payload=dict(event.payload, evidence=dict(evidence, lines=lines)))

    def test_non_verifactu_one_event_and_no_fiscal_outbox(self):
        db.update_verifactu_mode(self.bid, False)
        op = self.captured()
        self.assertIsNone(self.event(op).event.payload["evidence"]["fiscal_record"])
        self.assertEqual(self.counts(), {"invoice_records": 0, "invoice_events": 1, "verifactu_outbox": 0, "economic_events": 1, "invoice_economic_coverage": 1})

    def test_other_command_replay_rejected_and_wrong_result_rolls_back(self):
        from noesis.financial_operations.contracts import FinancialRequest
        from noesis.financial_operations.service import FinancialOperations
        service = FinancialOperations(self.bid)
        request = FinancialRequest("expense.confirm", None, "10.00", date.today(), None, None, {})
        op = service.prepare(self.principal, EntryIdentity.web_api(uuid4()), request)
        service.authorize(self.principal, op.operation_uuid, channel="web_api", approved_hash=request.request_hash, approved_revision=None)
        service.execute(self.principal, op.operation_uuid, lambda *_: {"fixture": True})
        with self.assertRaises(StateError):
            self.capture.execute(self.principal, op.operation_uuid)
        op = self.approve(self.draft()["id"])
        before = self.state()
        real = OperationsRepository.transition
        def bad_result(repo, row, state, now, **kwargs):
            if state == OperationState.COMMITTED:
                kwargs["result"] = kwargs["result"].replace('"captured":true,', '')
                from noesis.financial_operations.contracts import digest
                kwargs["result_hash"] = digest(kwargs["result"])
            return real(repo, row, state, now, **kwargs)
        with patch.object(OperationsRepository, "transition", bad_result), self.assertRaises(Exception):
            self.capture.execute(self.principal, op.operation_uuid)
        self.assertEqual(self.state(), before)

    def test_financial_operation_cannot_bypass_canonical_capture(self):
        op = self.approve(self.draft()["id"])
        before = self.state()
        attempted_result = []
        def bypass(session, request):
            result = invoices.issue_invoice(session, request.target_id, self.bid)
            attempted_result.append(True)
            return {"invoice_id": result.snapshots[0].source_id}
        with self.assertRaises(Exception):
            self.capture.operations.execute(self.principal, op.operation_uuid, bypass, revision_reader=self.capture._validate)
        self.assertEqual(attempted_result, [True])
        self.assertEqual(self.state(), before)

    def test_decimal_context_cannot_change_confirmation(self):
        from decimal import localcontext, ROUND_DOWN
        iid = self.draft(irpf_rate=15)["id"]
        with localcontext() as context:
            context.prec = 2
            context.rounding = ROUND_DOWN
            op = self.approve(iid)
            done = self.capture.execute(self.principal, op.operation_uuid)
        self.assertEqual(done.result["amount"], "106.00")

    def test_coverage_cannot_confirm_v1_event_for_unissued_invoice(self):
        template = self.event(self.captured()).event
        op = self.approve(self.draft()["id"])
        before = self.state()
        attempted_result = []

        def bypass(session, request):
            source = snapshot(session.borrowed_connection, self.bid, "invoice", request.target_id)
            payload = {k: v for k, v in template.payload.items() if k != "evidence"}
            event = replace(template, event_id=uuid4(), source_id=request.target_id,
                            source_revision=source.revision, payload_version=1, payload=payload)
            session.execute("INSERT INTO invoice_economic_coverage (business_id,invoice_id,event_uuid,event_type,operation_uuid) VALUES (?,?,?,'invoice.issued',?)",
                            (self.bid, request.target_id, str(event.event_id), str(op.operation_uuid)))
            EconomicEvents(session, self.bid).append(self.principal, event,
                operation_uuid=op.operation_uuid, event_slot="primary", revision_reader=lambda *_: source.revision)
            attempted_result.append(True)
            return {"invoice_id": request.target_id, "event_uuid": str(event.event_id),
                    "event_type": "invoice.issued", "content_hash": event.content_hash,
                    "amount": payload["total"], "number": payload["invoice_number"], "currency": "EUR", "captured": True}

        with self.assertRaises(Exception) as failure:
            self.capture.operations.execute(self.principal, op.operation_uuid, bypass, revision_reader=self.capture._validate)
        self.assertEqual(attempted_result, [True], str(failure.exception))
        self.assertEqual(self.state(), before)

    def test_cent_mismatch_and_no_secondary_connection(self):
        op = self.approve(self.draft()["id"])
        real = invoices.issue_invoice
        def corrupt(*args, **kwargs):
            value = real(*args, **kwargs)
            source = value.snapshots[0]
            return replace(value, snapshots=(replace(source, amounts=dict(source.amounts, total=Decimal("999.00"))),))
        before = self.state()
        with patch.object(invoices, "issue_invoice", corrupt), self.assertRaises(StateError):
            self.capture.execute(self.principal, op.operation_uuid)
        self.assertEqual(self.state(), before)
        def borrowed(*args, **kwargs):
            with patch.object(db, "get_conn", side_effect=AssertionError("Segunda conexión")):
                return real(*args, **kwargs)
        real_append = EconomicEvents.append
        def borrowed_append(*args, **kwargs):
            with patch.object(db, "get_conn", side_effect=AssertionError("Segunda conexión en evento")):
                return real_append(*args, **kwargs)
        from noesis.adapters.invoicing import InternalInvoicingProvider
        with patch.object(invoices, "issue_invoice", borrowed), patch.object(EconomicEvents, "append", borrowed_append):
            InternalInvoicingProvider().issue_captured(self.bid, self.principal, op.operation_uuid)
