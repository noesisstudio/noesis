"""Composición real de todos los escritores, compartida por SQLite/PostgreSQL."""

from datetime import date
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.documents import repo
from noesis.economic_events.contracts import SourceType
from noesis.financial_writers import bank, documents, invoices, payments, purchasing, recurring
from noesis.financial_writers.boundary import revision_reader, snapshot


class BorrowedWritersContract:
    def seed(self):
        self.settings = patch.multiple(
            config,
            VERIFACTU_PRODUCER_NIF="B87654321",  # pragma: allowlist secret
            VERIFACTU_CERT_PATH="",
            VERIFACTU_KEY_PATH="",
            VERIFACTU_AEAT_ENV="",
        )
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.business = db.create_business("Frontera", "writer@example.com")
        self.bid = self.business["id"]
        db.update_fiscal(self.bid, nif="A12345678", address="Calle 1")  # pragma: allowlist secret
        db.set_trial(self.bid, days=14)
        self.client = db.add_client(
            "Cliente", business_id=self.bid, nif="B12345674", address="Calle 2"
        )  # pragma: allowlist secret
        with db.get_conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS phase14_marker (business_id BIGINT NOT NULL,label TEXT NOT NULL)"
            )

    def draft(self, **kwargs):
        return db.add_invoice(self.client["id"], "Servicio", "100", business_id=self.bid, **kwargs)

    def issued(self):
        return db.issue_invoice(self.draft()["id"], self.bid)

    def document(self):
        doc = repo.add(
            self.bid,
            filename="ticket.jpg",
            stored_name="ticket.jpg",
            mime="image/jpeg",
            size=1,
            doc_status="pendiente_revisar",
        )
        repo.record_classification(
            doc["id"], self.bid, detected_kind="ticket", confidence=None, method="heuristica"
        )
        return doc["id"]

    def movement(self, invoice_id=None):
        import hashlib
        from uuid import uuid4

        value = db.add_bank_transaction(
            self.bid,
            import_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
            booked_on=date.today().isoformat(),
            amount="10",
        )
        if invoice_id:
            db.suggest_bank_transaction(
                value["id"], self.bid, invoice_id, score=100, reason="Prueba"
            )
        return value["id"]

    def schedule(self, auto_issue=True):
        return db.add_recurring_invoice(
            self.bid,
            self.client["id"],
            name="Cuota",
            cadence="monthly",
            next_run_on=date.today().isoformat(),
            auto_issue=auto_issue,
            lines=[{"description": "Cuota", "quantity": 1, "unit_price": 10, "vat_rate": 21}],
        )

    def state(self):
        tables = (
            "invoices",
            "invoice_lines",
            "invoice_payments",
            "received_invoices",
            "expenses",
            "bank_transactions",
            "invoice_records",
            "invoice_events",
            "verifactu_outbox",
            "invoice_cancellation_records",
            "verifactu_cancellation_outbox",
            "document_profiles",
            "document_sequences",
            "invoice_series",
            "documents",
            "document_classifications",
            "suppliers",
            "recurring_invoices",
            "recurring_invoice_runs",
            "phase14_marker",
        )
        with db.get_conn() as conn:
            return {
                table: [
                    dict(r)
                    for r in conn.execute_exact(
                        f"SELECT * FROM {table} WHERE business_id=? ORDER BY 1,2", (self.bid,)
                    ).fetchall()
                ]
                for table in tables
            }

    def case(self, name):
        if name == "draft":
            return lambda c: invoices.add_invoice(
                c, self.client["id"], "Nuevo", Decimal("2.675"), business_id=self.bid
            )
        if name == "issue":
            iid = self.draft()["id"]
            return lambda c: invoices.issue_invoice(c, iid, self.bid)
        if name == "rectify":
            iid = self.issued()["id"]
            return lambda c: invoices.create_rectifying_invoice(
                c, iid, self.bid, concept="Rectificar", base="-10", reason="Error material"
            )
        if name in {"payment", "paid", "bank_match"}:
            iid = self.issued()["id"]
            if name == "payment":
                return lambda c: payments.add_invoice_payment(
                    c, iid, Decimal("10.005"), business_id=self.bid
                )
            if name == "paid":
                return lambda c: payments.mark_invoice_paid(c, iid, self.bid)
            tid = self.movement(iid)
            return lambda c: bank.confirm_bank_transaction(c, tid, self.bid)
        if name in {"received_update", "received_status", "received_delete"}:
            rid = db.add_received_invoice("100", business_id=self.bid)["id"]
            if name == "received_update":
                return lambda c: purchasing.update_received_invoice(
                    c, rid, business_id=self.bid, total="101", base="90"
                )
            if name == "received_status":
                return lambda c: purchasing.set_received_invoice_status(
                    c, rid, "pagada", business_id=self.bid
                )
            return lambda c: purchasing.delete_received_invoice(c, rid, self.bid)
        if name == "received":
            return lambda c: purchasing.add_received_invoice(
                c, "121", base="100", vat_amount="21", business_id=self.bid
            )
        if name == "expense":
            return lambda c: purchasing.add_expense(
                c, "Compra", Decimal("2.675"), business_id=self.bid
            )
        if name == "expense_delete":
            eid = db.add_expense("Compra", "50", business_id=self.bid)["id"]
            return lambda c: purchasing.delete_expense(c, eid, self.bid)
        if name == "bank_import":
            return lambda c: bank.add_bank_transaction(
                c, self.bid, import_hash="b" * 64, booked_on=date.today().isoformat(), amount="10"
            )
        if name in {"bank_suggest", "bank_ignore"}:
            tid = self.movement()
            if name == "bank_ignore":
                return lambda c: bank.ignore_bank_transaction(c, tid, self.bid)
            iid = self.issued()["id"]
            return lambda c: bank.suggest_bank_transaction(
                c, tid, self.bid, iid, score=100, reason="Prueba"
            )
        if name in {"document_received", "document_expense"}:
            did = self.document()
            if name == "document_received":
                return lambda c: documents.confirm_received_invoice(
                    c, self.bid, did, total="100", supplier_name="Proveedor nuevo"
                )
            return lambda c: documents.convert_ticket_to_expense(
                c, self.bid, did, amount=Decimal("2.675")
            )
        if name == "record_received":
            return lambda c: documents.record_received_invoice(
                c, self.bid, total="100", supplier_name="Proveedor otro"
            )
        if name == "recurring":
            schedule = self.schedule()
            return lambda c: recurring.generate_cycle(
                c, schedule["id"], self.bid, schedule["next_run_on"]
            )
        if name == "cancellation":
            db.update_verifactu_mode(self.bid, True)
            iid = self.issued()["id"]
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE verifactu_outbox SET status='aceptado' WHERE business_id=? AND invoice_id=?",
                    (self.bid, iid),
                )
            return lambda c: invoices.create_invoice_cancellation_record(
                c, iid, self.bid, reason="Error confirmado"
            )
        raise AssertionError(name)

    def test_every_writer_outer_rollback_and_commit_with_marker(self):
        names = (
            "draft",
            "issue",
            "rectify",
            "payment",
            "paid",
            "received",
            "received_update",
            "received_status",
            "received_delete",
            "expense",
            "expense_delete",
            "bank_import",
            "bank_suggest",
            "bank_ignore",
            "bank_match",
            "document_received",
            "document_expense",
            "record_received",
            "recurring",
            "cancellation",
        )
        for name in names:
            with self.subTest(writer=name):
                action = self.case(name)
                before = self.state()
                with self.assertRaisesRegex(RuntimeError, "exterior"):
                    with db.get_conn() as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        with patch.object(
                            db, "get_conn", side_effect=AssertionError("Segunda conexión")
                        ):
                            result = action(FinancialSession(conn))
                            self.assertTrue(result.snapshots)
                            conn.execute(
                                "INSERT INTO phase14_marker VALUES (?,?)", (self.bid, name)
                            )
                            raise RuntimeError("Fallo exterior después del éxito")
                self.assertEqual(before, self.state())
                with db.get_conn() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    result = action(conn)
                    conn.execute("INSERT INTO phase14_marker VALUES (?,?)", (self.bid, name))
                self.assertNotEqual(before, self.state())
                self.assertTrue(all(s.business_id == self.bid for s in result.snapshots))
                if name == "bank_match":
                    self.assertIsNotNone(result.payment_id)
                    self.assertTrue(
                        any(s.source_type == "invoice_payment" for s in result.snapshots)
                    )

    def test_exact_inputs_rounding_and_immutable_actual_snapshot(self):
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            result = purchasing.add_expense(conn, "Compra", Decimal("2.675"), business_id=self.bid)
            s = result.snapshots[0]
            self.assertEqual(result.exact_inputs["amount"], Decimal("2.675"))
            self.assertEqual(s.amounts["amount"], Decimal("2.68"))
            self.assertEqual(result.legacy_value()["amount"], 2.68)
            self.assertEqual(s.money_provenance, "legacy_binary_storage")
            self.assertTrue(
                any(v == Decimal("2.68") for _, values in result.prepared_values for _, v in values)
            )
            with self.assertRaises(TypeError):
                s.amounts["amount"] = Decimal("0")
        legacy = db.add_received_invoice("10", base="2.675", business_id=self.bid)
        self.assertEqual(legacy["base"], 2.67)  # Conserva round(float) histórico.
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            exact = purchasing.add_received_invoice(conn, "10", base="2.675", business_id=self.bid)
            self.assertEqual(exact.snapshots[0].amounts["base"], Decimal("2.68"))
        self.assertNotIn("_financial_revision", db.get_received_invoice(legacy["id"], self.bid))

    def test_decimal_context_does_not_reduce_writer_precision(self):
        from decimal import localcontext

        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            with localcontext() as ctx:
                ctx.prec = 2
                result = purchasing.add_expense(
                    conn, "Compra", Decimal("9999999.995"), business_id=self.bid
                )
            self.assertEqual(result.snapshots[0].amounts["amount"], Decimal("10000000.00"))

    def test_no_outer_transaction_and_invalid_money_rejected(self):
        with db.get_conn() as conn:
            if conn.dialect == "sqlite":
                with self.assertRaises(ValueError):
                    purchasing.add_expense(conn, "Compra", "10", business_id=self.bid)
        for amount in (
            1.5,
            True,
            Decimal("0.004"),
            Decimal("NaN"),
            Decimal("Infinity"),
            "-1",
            "0",
            "1,50",
            "10000001",
        ):
            with (
                self.subTest(amount=amount),
                self.assertRaises((TypeError, ValueError, ArithmeticError)),
            ):
                with db.get_conn() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    purchasing.add_expense(conn, "Compra", amount, business_id=self.bid)
        self.assertEqual(db.add_expense("Legacy", "0.004", business_id=self.bid)["amount"],0)

    def test_six_revision_readers_stale_and_mutable_raw_sql(self):
        iid = self.issued()["id"]
        pid = db.add_invoice_payment(iid, "10", business_id=self.bid)["id"]
        rid = db.add_received_invoice("10", business_id=self.bid)["id"]
        eid = db.add_expense("Compra", "10", business_id=self.bid)["id"]
        tid = self.movement()
        cancel = self.case("cancellation")
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cid = cancel(conn).legacy["id"]
            read = revision_reader(self.bid)
            for kind, sid in (
                (SourceType.INVOICE, iid),
                (SourceType.INVOICE_PAYMENT, pid),
                (SourceType.RECEIVED_INVOICE, rid),
                (SourceType.EXPENSE, eid),
                (SourceType.BANK_TRANSACTION, tid),
                (SourceType.INVOICE_CANCELLATION_RECORD, cid),
            ):
                captured = snapshot(conn, self.bid, kind, sid)
                self.assertEqual(read(FinancialSession(conn), kind, sid), captured.revision)
                self.assertGreater(captured.revision, 0)
            first = snapshot(conn, self.bid, "received_invoice", rid)
            conn.execute(
                "UPDATE received_invoices SET total=11 WHERE business_id=? AND id=?",
                (self.bid, rid),
            )
            self.assertEqual(
                read(FinancialSession(conn), SourceType.RECEIVED_INVOICE, rid), first.revision + 1
            )
            with self.assertRaises(ValueError):
                purchasing.update_received_invoice(
                    conn, rid, business_id=self.bid, total="12", expected_revision=first.revision
                )
            conn.execute(
                "UPDATE expenses SET amount=12 WHERE business_id=? AND id=?", (self.bid, eid)
            )
            self.assertEqual(read(FinancialSession(conn), SourceType.EXPENSE, eid), 2)
            conn.execute(
                "UPDATE bank_transactions SET description='Cambio' WHERE business_id=? AND id=?",
                (self.bid, tid),
            )
            self.assertEqual(read(FinancialSession(conn), SourceType.BANK_TRANSACTION, tid), 2)

    def test_revision_of_issue_ignores_collection_but_draft_change_invalidates(self):
        iid = self.draft()["id"]
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            old = snapshot(conn, self.bid, "invoice", iid)
        db.update_invoice_draft(
            iid,
            self.bid,
            client_id=self.client["id"],
            lines=[{"description": "Otro", "unit_price": "101"}],
        )
        with self.assertRaises(ValueError):
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                invoices.issue_invoice(conn, iid, self.bid, expected_revision=old.revision)
        db.issue_invoice(iid, self.bid)
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            issued = snapshot(conn, self.bid, "invoice", iid)
        db.add_invoice_payment(iid, "10", business_id=self.bid)
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self.assertEqual(snapshot(conn, self.bid, "invoice", iid).revision, issued.revision)

    def test_f1_f2_r1_to_r5_vat_irpf_snapshot_and_fiscal_failure(self):
        db.update_verifactu_mode(self.bid, True)
        for typ in ("F1", "F2", "R1", "R2", "R3", "R4", "R5"):
            with self.subTest(invoice_type=typ):
                origin = self.draft(invoice_type="F2" if typ in {"F2", "R5"} else "F1")
                db.issue_invoice(origin["id"], self.bid)
                if typ.startswith("R"):
                    candidate = db.create_rectifying_invoice(
                        origin["id"],
                        self.bid,
                        concept="Rectifica",
                        base="-10",
                        invoice_type=typ,
                        reason="Error de precio",
                    )
                else:
                    candidate = self.draft(
                        invoice_type=typ,
                        irpf_rate=15,
                        lines=[
                            {
                                "description": str(rate),
                                "quantity": 1,
                                "unit_price": "10.05",
                                "vat_rate": rate,
                            }
                            for rate in (21, 10, 4, 0)
                        ],
                    )
                before = self.state()
                with self.assertRaises(RuntimeError):
                    with db.get_conn() as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        result = invoices.issue_invoice(conn, candidate["id"], self.bid)
                        self.assertIsNotNone(result.snapshots[0].data["fiscal_record"])
                        self.assertEqual(
                            result.snapshots[0].amounts["total"],
                            Decimal(str(result.legacy_value()["total"])),
                        )
                        raise RuntimeError("Después del registro fiscal")
                self.assertEqual(before, self.state())
                saved = db.issue_invoice(candidate["id"], self.bid)
                self.assertEqual(saved["invoice_type"], typ)

    def test_migration64_down_up_preserves_business_money(self):
        with self.source_revision_migration_scope():
            rid = db.add_received_invoice("2.68", business_id=self.bid)["id"]
            # Retirar primero migraciones dependientes; no saltar guards nuevos.
            migrations.downgrade(63)
            with db.get_conn() as conn:
                self.assertEqual(conn.execute('SELECT total FROM received_invoices WHERE business_id=? AND id=?',
                                             (self.bid, rid)).fetchone()['total'],2.68)
            migrations.upgrade()
            with db.get_conn() as conn:
                self.assertEqual(snapshot(conn,self.bid,'received_invoice',rid).revision,1)

    @contextmanager
    def source_revision_migration_scope(self):
        if not config.DATABASE_URL:
            yield
            return
        from urllib.parse import quote
        from uuid import uuid4
        schema = 'writers_migration_' + uuid4().hex
        with db.get_conn() as conn:
            conn.execute(f'CREATE SCHEMA {schema}')
        db.close_pool()
        try:
            with patch.object(config,'DATABASE_URL',self.original_url+'?options='+quote('-csearch_path='+schema)):
                migrations.upgrade()
                self.seed()
                yield
                db.close_pool()
        finally:
            with db.get_conn() as conn:
                conn.execute(f'DROP SCHEMA {schema} CASCADE')
            db.close_pool()

    def test_no_events_or_flags_changed(self):
        with db.get_conn() as conn:
            for table in (
                "economic_events",
                "economic_event_links",
                "financial_operations",
                "financial_authorizations",
            ):
                self.assertEqual(
                    conn.execute(
                        f"SELECT COUNT(*) AS n FROM {table} WHERE business_id=?", (self.bid,)
                    ).fetchone()["n"],
                    0,
                )
        self.assertFalse(config.FINANCIAL_CORE_ENABLED)

    def test_unknown_currency_and_nonmonotonic_revisions_rejected(self):
        with self.assertRaises(ValueError):
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                bank.add_bank_transaction(
                    conn,
                    self.bid,
                    import_hash="e" * 64,
                    booked_on=date.today().isoformat(),
                    amount="10",
                    currency="USD",
                )
        eid = db.add_expense("Compra", "10", business_id=self.bid)["id"]
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE expenses SET _financial_revision=0 WHERE business_id=? AND id=?",
                    (self.bid, eid),
                )
        with self.assertRaises(db.IntegrityError):
            with db.get_conn() as conn:
                conn.execute(
                    "INSERT INTO expenses (business_id,concept,amount,created_at,_financial_revision) VALUES (?,'Inventada',10,?,20)",
                    (self.bid, db._now()),
                )

    def test_financial_operation_can_own_writer_result_and_rollback(self):
        from uuid import uuid4
        from noesis.financial_operations.contracts import (
            CommandType,
            EntryIdentity,
            EntryNamespace,
            FinancialRequest,
            Principal,
        )
        from noesis.financial_operations.service import FinancialOperations

        user = db.create_user("owner-" + uuid4().hex + "@example.test", "hash de prueba", self.bid)
        principal = Principal(user["id"], 0)
        service = FinancialOperations(self.bid)
        request = FinancialRequest(
            # Operación sintética de infraestructura; expense.confirm exige productor1.7.
            CommandType.INVOICE_FISCAL_CANCEL,
            None,
            Decimal("10"),
            date.today(),
            None,
            "Compra",
            {"category": "material"},
        )
        op = service.prepare(principal, EntryIdentity.web_api(uuid4()), request)
        service.authorize(
            principal,
            op.operation_uuid,
            channel=EntryNamespace.WEB_API,
            approved_hash=request.request_hash,
            approved_revision=None,
        )
        before = self.state()

        def effect(session, approved):
            result = purchasing.add_expense(
                session, approved.reason, approved.amount, business_id=self.bid
            )
            session.execute("INSERT INTO phase14_marker VALUES (?,?)", (self.bid, "operation"))
            return {
                "expense_id": result.snapshots[0].source_id,
                "amount": result.snapshots[0].amounts["amount"],
            }

        def failure(session, approved):
            effect(session, approved)
            raise RuntimeError("Fallo exterior")

        with self.assertRaises(RuntimeError):
            service.execute(principal, op.operation_uuid, failure)
        self.assertEqual(before, self.state())
        committed = service.execute(principal, op.operation_uuid, effect)
        self.assertEqual(committed.result["amount"], "10.00")
        self.assertEqual(
            service.execute(principal, op.operation_uuid, failure).result, committed.result
        )
