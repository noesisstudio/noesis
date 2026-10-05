"""Contrato E común sobre fixtures reales y descartables, sin productor externo."""

import json
from contextlib import contextmanager
from uuid import uuid4
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.financial_history.reconciliation import HistoryReconciliation
from noesis.financial_history.reconciliation_contracts import FindingCode, ReconciliationFinding
from noesis.financial_operations.contracts import AccessDenied, ConflictError, StateError
from tests.financial_history_import_contract import HistoryImportContract


class HistoryReconciliationContract:
    seed = HistoryImportContract.seed
    draft = HistoryImportContract.draft
    issued = HistoryImportContract.issued
    movement = HistoryImportContract.movement
    approved = HistoryImportContract.approved
    empty_database = HistoryImportContract.empty_database
    exact_storage = HistoryImportContract.exact_storage
    sources = HistoryImportContract.sources
    frozen = HistoryImportContract.frozen
    payment_source = HistoryImportContract.payment_source
    setup_import = HistoryImportContract.setup_import

    def setup_reconciliation(self):
        self.setup_import()
        self.reconciler = HistoryReconciliation(self.bid,page_size=8)

    def scenario(self):
        self.sources(expense_unknown=True)
        self.frozen()
        self.importer.run(self.principal,self.batch_uuid)

    def reconcile(self, uid=None):
        return self.reconciler.reconcile(self.principal,self.epoch_uuid,str(self.manifest["manifest_uuid"]),self.batch_uuid,uid or uuid4())

    def snapshot(self):
        from noesis.financial_history.reconciliation_verifier import storage_hash
        with db.get_conn() as conn:
            if conn.dialect == "postgres":
                names = [r["table_name"] for r in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE'").fetchall()]
            else:
                names = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
            result = {}
            for table in names:
                if table.startswith("financial_history_reconciliation"):
                    continue
                result[table] = sorted(storage_hash(r) for r in conn.execute_exact("SELECT * FROM "+table).fetchall())
        result["flags"] = tuple(getattr(config,f) for f in ("FINANCIAL_CORE_ENABLED","LEDGER_REPORTING_ENABLED","OPEN_ITEMS_ENABLED","NEW_TAX_ENGINE_ENABLED","NEW_BANK_RECONCILIATION_ENABLED"))
        return result

    def findings(self, result):
        after, codes = "", set()
        while True:
            page = self.reconciler.read(self.principal,result["reconciliation_uuid"],after=after)
            codes.update(f["code"] for f in page["findings"])
            if page["next_cursor"] is None:
                return codes
            after = page["next_cursor"]

    def test_complete_observed_v2_pass_exact_hash_retry_no_side_effects(self):
        self.scenario()
        before = self.snapshot()
        uid = uuid4()
        result = self.reconcile(uid)
        self.assertEqual(result["result"],"PASS",self.findings(result))
        self.assertEqual(result["source_recheck_hash"],result["source_set_hash"])
        self.assertEqual(self.reconcile(uid),result)
        another = self.reconcile()
        self.assertEqual(another["result_hash"],result["result_hash"])
        self.assertEqual(before,self.snapshot())

    def test_catalog_closed_invalid_versions_refs_and_hashes(self):
        self.assertEqual(len(FindingCode),17)
        for kwargs in ({"code":"generic"},{"code":FindingCode.EVENT_MISSING,"finding_version":True},
                       {"code":FindingCode.SOURCE_DRIFT,"expected_hash":"x"},
                       {"code":FindingCode.SOURCE_DRIFT,"actual_ref":"datos personales libres"}):
            with self.assertRaises((ValueError,TypeError)):
                ReconciliationFinding(**kwargs)

    def test_prepared_batch_rejected_no_durable_run(self):
        self.sources()
        self.frozen()
        before = self.snapshot()
        with self.assertRaisesRegex(StateError,"BATCH_NOT_TERMINAL"):
            self.reconcile()
        self.assertEqual(before,self.snapshot())

    def test_crash_all_checkpoints_rollback_and_commit_response_loss(self):
        self.scenario()
        before = self.snapshot()
        for target in ("before_create","created","manifest_page","event_page","import_page","source_page","before_freeze","frozen"):
            uid = uuid4()
            def crash(step):
                if step == target:
                    raise RuntimeError("crash fixture")
            with patch.object(self.reconciler,"_checkpoint",side_effect=crash):
                with self.assertRaises(RuntimeError):
                    self.reconcile(uid)
            with db.get_conn() as conn:
                self.assertIsNone(conn.execute("SELECT 1 FROM financial_history_reconciliations WHERE business_id=? AND reconciliation_uuid=?",(self.bid,str(uid))).fetchone())
            self.assertEqual(self.reconcile(uid)["result"],"PASS")
            self.assertEqual(before,self.snapshot())
        uid = uuid4()
        with patch.object(self.reconciler,"_checkpoint",side_effect=lambda step: (_ for _ in ()).throw(RuntimeError("response")) if step=="committed" else None):
            with self.assertRaises(RuntimeError):
                self.reconcile(uid)
        self.assertEqual(self.reconcile(uid)["result"],"PASS")
        self.assertEqual(before,self.snapshot())

    def test_frozen_sql_immutable_retention_and_downgrade_blocked(self):
        self.scenario()
        result = self.reconcile()
        for sql in ("UPDATE financial_history_reconciliations SET result='BLOCKED'", "DELETE FROM financial_history_reconciliations"):
            with self.assertRaises(Exception):
                with db.get_conn() as conn:
                    conn.execute(sql+" WHERE business_id=? AND reconciliation_uuid=?",(self.bid,result["reconciliation_uuid"]))
        with self.assertRaisesRegex(ValueError,"reconciliación"):
            migrations.downgrade(72)

    def test_empty_migration_cycle_preserves_existing_d_bytes(self):
        for initial in (0,72):
            with self.subTest(initial=initial),self.empty_database(initial):
                self.assertEqual(migrations.upgrade(73),73)
                self.setup_reconciliation()
                self.scenario()
                before = self.snapshot()
                before.pop("schema_migrations", None)
                self.assertEqual(migrations.downgrade(72),72)
                self.assertEqual(migrations.upgrade(73),73)
                after = self.snapshot()
                after.pop("schema_migrations", None)  # Nuevo applied_at de 73, no dato financiero.
                self.assertEqual(before,after)

    def test_new_uuid_wrong_version_and_wrong_context_rejected(self):
        self.scenario()
        uid = uuid4()
        self.reconcile(uid)
        for key in ("epoch_uuid","manifest_uuid","batch_uuid"):
            kwargs = dict(epoch_uuid=self.epoch_uuid,manifest_uuid=str(self.manifest["manifest_uuid"]),batch_uuid=self.batch_uuid,reconciliation_uuid=uid)
            kwargs[key] = uuid4()
            with self.assertRaises((AccessDenied,StateError,ConflictError,ValueError)):
                self.reconciler.reconcile(self.principal,**kwargs)
        with self.assertRaises(ValueError):
            self.reconciler.reconcile(self.principal,self.epoch_uuid,self.manifest["manifest_uuid"],self.batch_uuid,uid,reconciliation_version=2)

    @contextmanager
    def corruption(self, *tables):
        """Solo BD sintética: suspende/restaura guards para demostrar diagnóstico.

        Las restricciones de CHECK restauradas NOT VALID en PG admiten evidencia
        dañada preexistente; se siguen aplicando a nuevas escrituras del fixture.
        Ninguna función/migración productiva cambia.
        """
        with db.get_conn() as conn:
            pg = conn.dialect == "postgres"
            definitions = []
            if pg:
                for table in tables:
                    conn.execute("ALTER TABLE "+table+" DISABLE TRIGGER ALL")
                    for r in conn.execute("SELECT conname,pg_get_constraintdef(oid) AS ddl FROM pg_constraint WHERE conrelid=?::regclass AND contype='c'",(table,)).fetchall():
                        definitions.append((table,r["conname"],r["ddl"]))
                        conn.execute('ALTER TABLE '+table+' DROP CONSTRAINT "'+r["conname"]+'"')
            else:
                conn.execute("PRAGMA foreign_keys=OFF")
                conn.execute("PRAGMA ignore_check_constraints=ON")
                for table in tables:
                    for r in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?",(table,)).fetchall():
                        definitions.append((r["name"],r["sql"]))
                        conn.execute('DROP TRIGGER "'+r["name"]+'"')
            try:
                yield conn
            finally:
                if pg:
                    for table,name,ddl in definitions:
                        conn.execute('ALTER TABLE '+table+' ADD CONSTRAINT "'+name+'" '+ddl.removesuffix(" NOT VALID")+" NOT VALID")
                    for table in tables:
                        conn.execute("ALTER TABLE "+table+" ENABLE TRIGGER ALL")
                else:
                    for _,ddl in definitions:
                        conn.execute(ddl)
                    conn.execute("PRAGMA ignore_check_constraints=OFF")

    def assert_blocked_unchanged(self, expected, uid=None):
        before = self.snapshot()
        result = self.reconcile(uid)
        self.assertEqual(result["result"],"BLOCKED")
        self.assertIn(expected,self.findings(result))
        self.assertEqual(before,self.snapshot())
        self.assertEqual(result,self.reconcile(result["reconciliation_uuid"]))
        return result

    def test_corruption_matrix_all_discrepancies_no_repair(self):
        mutations = (
            ("expenses","UPDATE expenses SET amount='13.11' WHERE business_id=?","SOURCE_DRIFT"),
            ("financial_history_items","UPDATE financial_history_items SET raw_hash=? WHERE business_id=?","MANIFEST_INCONSISTENT"),
            ("financial_history_import_items","DELETE FROM financial_history_import_items WHERE business_id=?","IMPORT_ITEM_MISSING"),
            ("financial_history_import_items","UPDATE financial_history_import_items SET result_canonical='{}' WHERE business_id=?","IMPORT_RESULT_CONFLICT"),
            ("economic_events","DELETE FROM economic_events WHERE business_id=?","EVENT_MISSING"),
            ("economic_events","UPDATE economic_events SET content_hash=? WHERE business_id=?","EVENT_CONTENT_CONFLICT"),
            ("financial_operations","UPDATE financial_operations SET state='committed' WHERE business_id=?","OPERATION_CONFLICT"),
            ("financial_operations","UPDATE financial_operations SET entry_namespace='web_api' WHERE business_id=?","OPERATION_CONFLICT"),
            ("financial_authorizations","UPDATE financial_authorizations SET kind='human_confirmation' WHERE business_id=?","AUTHORIZATION_CONFLICT"),
            ("financial_authorizations","UPDATE financial_authorizations SET actor_user_id=recorded_by,actor_session_version=0 WHERE business_id=?","AUTHORIZATION_CONFLICT"),
            ("financial_authorizations","UPDATE financial_authorizations SET approved_request_hash=? WHERE business_id=?","AUTHORIZATION_CONFLICT"),
            ("economic_event_sequences","UPDATE economic_event_sequences SET last_sequence=999 WHERE business_id=?","SEQUENCE_CONFLICT"),
            ("economic_events","UPDATE economic_events SET business_sequence=business_sequence+10 WHERE business_id=?","SEQUENCE_CONFLICT"),
            ("economic_events","UPDATE economic_events SET historical_batch_uuid=? WHERE business_id=?","EVENT_CONTENT_CONFLICT"),
            ("financial_history_import_batches","UPDATE financial_history_import_batches SET state='blocked' WHERE business_id=?","BLOCKING_HISTORY_REMAINS"),
        )
        for table,sql,code in mutations:
            with self.subTest(table=table,sql=sql):
                self.setup_reconciliation()
                self.scenario()
                extra = (str(uuid4()),) if "historical_batch_uuid=?" in sql else ("b"*64,) if sql.count("?")==2 else ()
                with self.corruption(table) as conn:
                    conn.execute(sql,(*extra,self.bid))
                self.assert_blocked_unchanged(code)

    def test_physical_source_insert_delete_and_frozen_retry_drift(self):
        for action in ("insert","delete"):
            with self.subTest(action=action):
                self.setup_reconciliation()
                self.scenario()
                original = self.reconcile()
                with self.corruption("expenses") as conn:
                    if action == "insert":
                        conn.execute("INSERT INTO expenses (business_id,concept,amount,created_at) VALUES (?,'nuevo','1.00','2026-09-01')",(self.bid,))
                    else:
                        conn.execute("DELETE FROM expenses WHERE business_id=?",(self.bid,))
                with self.assertRaises(ConflictError):
                    self.reconcile(original["reconciliation_uuid"])
                self.assertEqual(self.reconciler.read(self.principal,original["reconciliation_uuid"])["result"],original)
                self.assert_blocked_unchanged("SOURCE_DRIFT")

    def test_partial_with_unexplained_item_never_pass(self):
        self.sources()
        rows = self.frozen()
        self.importer.record_item(self.principal,self.batch_uuid,rows[0]["item_uuid"])
        with self.corruption("financial_history_import_batches") as conn:
            conn.execute("UPDATE financial_history_import_batches SET state='partial' WHERE business_id=? AND batch_uuid=?",(self.bid,self.batch_uuid))
        self.assert_blocked_unchanged("IMPORT_ITEM_MISSING")
    def test_binary_source_never_pass(self):
        db.add_expense("Ambiguo","12.10",business_id=self.bid)
        self.frozen()
        self.importer.run(self.principal,self.batch_uuid)
        self.assert_blocked_unchanged("BLOCKING_HISTORY_REMAINS")

    def test_existing_same_manifest_and_later_inventory_preserve_original_batch(self):
        self.scenario()
        original_batch = self.batch_uuid
        before = self.snapshot()
        self.batch_uuid = str(uuid4())
        self.importer.prepare(self.principal,self.manifest["manifest_uuid"],self.batch_uuid)
        self.importer.run(self.principal,self.batch_uuid)
        self.assertEqual(self.reconcile()["result"],"PASS")
        self.manifest = self.importer.inventory(self.principal,self.epoch_uuid,uuid4(),repository_version="fixture",environment_identity="synthetic")
        self.batch_uuid = str(uuid4())
        self.importer.prepare(self.principal,self.manifest["manifest_uuid"],self.batch_uuid)
        self.importer.run(self.principal,self.batch_uuid)
        result = self.reconcile()
        self.assertEqual(result["result"],"PASS",self.findings(result))
        after = self.snapshot()
        for table in ("economic_events","economic_event_links","financial_operations","financial_authorizations"):
            self.assertEqual(before[table],after[table])
        with db.get_conn() as conn:
            self.assertEqual({str(r["historical_batch_uuid"]) for r in conn.execute("SELECT historical_batch_uuid FROM economic_events WHERE business_id=?",(self.bid,)).fetchall()},{original_batch})

    def test_payment_parent_live_v2_fiscal_no_regeneration(self):
        db.update_verifactu_mode(self.bid,True)
        self.payment_source()
        self.frozen()
        self.importer.run(self.principal,self.batch_uuid)
        with patch("noesis.verifactu.invoice_record_hash",side_effect=AssertionError("No recalcular")),patch("noesis.verifactu.cancellation_record_hash",side_effect=AssertionError("No recalcular")):
            result = self.reconcile()
        self.assertEqual(result["result"],"PASS",self.findings(result))

    def test_bank_match_live_evidence_only_not_second_cash(self):
        from noesis.invoice_capture.service import InvoiceCapture
        from noesis.bank_capture.service import BankCapture
        from noesis.economic_events.contracts import CATALOG, EventType, FutureImpact
        invoice = InvoiceCapture(self.bid)
        op = self.approved(invoice,invoice.review(self.principal,self.draft()["id"]))
        iid = invoice.execute(self.principal,op.operation_uuid).result["invoice_id"]
        bank = BankCapture(self.bid)
        op = self.approved(bank,bank.review_import(self.principal,amount="10.00",account_scope="fixture",
            batch_uuid=uuid4(),row_key="one",statement_hash="a"*64,booked_on="2026-09-01"))
        tid = bank.execute(self.principal,op.operation_uuid).result["bank_transaction_id"]
        db.suggest_bank_transaction(tid,self.bid,iid)
        op = self.approved(bank,bank.review_match(self.principal,tid))
        bank.execute(self.principal,op.operation_uuid)
        self.frozen()
        self.importer.run(self.principal,self.batch_uuid)
        result = self.reconcile()
        self.assertEqual(result["result"],"PASS",self.findings(result))
        with db.get_conn() as conn:
            rows = conn.execute_exact("SELECT event_type,amount FROM economic_events WHERE business_id=?",(self.bid,)).fetchall()
        self.assertEqual(sum(r["event_type"]=="customer_payment.received" for r in rows),1)
        self.assertIsNotNone(next(r["amount"] for r in rows if r["event_type"]=="bank_transaction.matched"))
        self.assertEqual(CATALOG[EventType.BANK_TRANSACTION_MATCHED].future_impacts,(FutureImpact.EVIDENCE,))

    def test_parent_b_cannot_satisfy_verified_dependency(self):
        self.payment_source()
        self.frozen()
        self.importer.run(self.principal,self.batch_uuid)
        with self.corruption("financial_history_items") as conn:
            conn.execute("UPDATE financial_history_items SET classification='B' WHERE business_id=? AND manifest_uuid=? AND source_type='invoice'",(self.bid,str(self.manifest["manifest_uuid"])))
        self.assert_blocked_unchanged("DEPENDENCY_CONFLICT")

    def test_sql_duplicate_identity_detected_despite_normal_unique_guard(self):
        with self.empty_database(73):
            self.setup_reconciliation()
            self.sources()
            with db.get_conn() as conn:
                conn.execute("INSERT INTO expenses (business_id,concept,amount,created_at) VALUES (?,'Otro','1.00','2026-09-01')",(self.bid,))
            self.frozen()
            self.importer.run(self.principal,self.batch_uuid)
            with self.corruption("economic_events") as conn:
                if conn.dialect == "postgres":
                    rows = conn.execute("SELECT conname,pg_get_constraintdef(oid) AS ddl FROM pg_constraint WHERE conrelid='economic_events'::regclass AND contype='u'").fetchall()
                    name = next(r["conname"] for r in rows if r["ddl"]=="UNIQUE (business_id, source_type, source_id, source_revision, event_type)")
                    conn.execute('ALTER TABLE economic_events DROP CONSTRAINT "'+name+'"')
                else:
                    # Tabla QA reconstruida preservando filas y resto de constraints.
                    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name='economic_events'").fetchone()["sql"]
                    fragment = "UNIQUE(business_id,source_type,source_id,source_revision,event_type),"
                    self.assertIn(fragment,ddl)
                    conn.execute("CREATE TEMP TABLE duplicate_fixture AS SELECT * FROM economic_events")
                    conn.execute("DROP TABLE economic_events")
                    conn.execute(ddl.replace(fragment,""))
                    conn.execute("INSERT INTO economic_events SELECT * FROM duplicate_fixture")
                rows = conn.execute("SELECT event_uuid,source_id,source_revision FROM economic_events WHERE business_id=? AND source_type='expense' ORDER BY source_id",(self.bid,)).fetchall()
                conn.execute("UPDATE economic_events SET source_id=?,source_revision=?,expense_id=? WHERE business_id=? AND event_uuid=?",(rows[0]["source_id"],rows[0]["source_revision"],rows[0]["source_id"],self.bid,str(rows[1]["event_uuid"])))
            self.assert_blocked_unchanged("EVENT_CONTENT_CONFLICT")

    def test_terminal_batch_cannot_open_new_import_intent(self):
        self.sources()
        rows = self.frozen()
        self.importer.record_item(self.principal,self.batch_uuid,rows[0]["item_uuid"])
        with self.corruption("financial_history_import_batches") as conn:
            conn.execute("UPDATE financial_history_import_batches SET state='partial' WHERE business_id=? AND batch_uuid=?",(self.bid,self.batch_uuid))
        before = self.snapshot()
        with self.assertRaises(Exception):
            self.importer.record_item(self.principal,self.batch_uuid,rows[1]["item_uuid"])
        self.assertEqual(before,self.snapshot())

    def test_frozen_findings_append_update_delete_all_forbidden(self):
        self.scenario()
        with self.corruption("economic_event_sequences") as conn:
            conn.execute("UPDATE economic_event_sequences SET last_sequence=99 WHERE business_id=?",(self.bid,))
        result = self.reconcile()
        for sql in ("UPDATE financial_history_reconciliation_findings SET actual_ref='changed' WHERE business_id=?",
                    "DELETE FROM financial_history_reconciliation_findings WHERE business_id=?",
                    "INSERT INTO financial_history_reconciliation_findings SELECT business_id,reconciliation_uuid,?,manifest_uuid,item_uuid,code,severity,finding_version,expected_hash,actual_hash,expected_ref,actual_ref,evidence_canonical,?,created_at FROM financial_history_reconciliation_findings WHERE business_id=? LIMIT 1"):
            args = (str(uuid4()),"b"*64,self.bid) if sql.startswith("INSERT") else (self.bid,)
            with self.assertRaises(Exception),db.get_conn() as conn:
                conn.execute(sql,args)
        self.assertEqual(self.reconciler.read(self.principal,result["reconciliation_uuid"])["result"],result)

    def test_relations_missing_extra_wrong_parent_and_live_coverage_corruption(self):
        for action in ("missing","extra","wrong","coverage"):
            with self.subTest(action=action):
                self.setup_reconciliation()
                self.payment_source()
                self.frozen()
                self.importer.run(self.principal,self.batch_uuid)
                with self.corruption("economic_event_links","invoice_economic_coverage") as conn:
                    if action == "missing":
                        conn.execute("DELETE FROM economic_event_links WHERE business_id=?",(self.bid,))
                    elif action == "extra":
                        conn.execute("INSERT INTO economic_event_links (business_id,event_uuid,target_event_uuid,relation_type,recorded_at) SELECT business_id,event_uuid,target_event_uuid,'evidence_for',recorded_at FROM economic_event_links WHERE business_id=?",(self.bid,))
                    elif action == "wrong":
                        conn.execute("UPDATE economic_event_links SET target_event_uuid=event_uuid WHERE business_id=?",(self.bid,))
                    else:
                        conn.execute("UPDATE invoice_economic_coverage SET operation_state='prepared' WHERE business_id=?",(self.bid,))
                self.assert_blocked_unchanged("LIVE_COVERAGE_CONTAMINATION" if action=="coverage" else "DEPENDENCY_CONFLICT")

    def test_fiscal_reference_change_detected_without_new_hash(self):
        db.update_verifactu_mode(self.bid,True)
        self.payment_source()
        self.frozen()
        self.importer.run(self.principal,self.batch_uuid)
        with self.corruption("invoice_records") as conn:
            conn.execute("UPDATE invoice_records SET record_hash=? WHERE business_id=?",("b"*64,self.bid))
        with patch("noesis.verifactu.invoice_record_hash",side_effect=AssertionError("No recalcular")):
            self.assert_blocked_unchanged("FISCAL_REFERENCE_CONFLICT")

    def test_frozen_known_invalid_fiscal_reference_never_pass(self):
        db.update_verifactu_mode(self.bid,True)
        self.payment_source()
        with self.corruption("invoice_records") as conn:
            conn.execute("UPDATE invoice_records SET record_hash=? WHERE business_id=?",("b"*64,self.bid))
        self.frozen()
        self.importer.run(self.principal,self.batch_uuid)
        with patch("noesis.verifactu.invoice_record_hash",side_effect=AssertionError("No recalcular")):
            self.assert_blocked_unchanged("FISCAL_REFERENCE_CONFLICT")

    def test_prior_batch_terminal_alias_corruption_global_detection(self):
        self.scenario()
        original_batch = self.batch_uuid
        self.batch_uuid = str(uuid4())
        self.importer.prepare(self.principal,self.manifest["manifest_uuid"],self.batch_uuid)
        self.importer.run(self.principal,self.batch_uuid)
        with self.corruption("financial_history_import_items") as conn:
            conn.execute("UPDATE financial_history_import_items SET completion_key='skipped' WHERE business_id=? AND batch_uuid=?",(self.bid,original_batch))
        self.assert_blocked_unchanged("IMPORT_RESULT_CONFLICT")

    def test_money_unknown_null_not_zero_and_dates_preserved(self):
        self.scenario()
        with db.get_conn() as conn:
            rows = conn.execute_exact("SELECT * FROM economic_events WHERE business_id=?",(self.bid,)).fetchall()
        for row in rows:
            payload = json.loads(row["payload_canonical"])
            self.assertEqual(payload["evidence_basis"],"observed_state")
            if row["event_type"] == "expense.confirmed":
                self.assertIsNone(payload["vat_amount"])
                self.assertIsNone(payload["spent_on"])
                self.assertIsNone(row["occurred_at"])
            elif row["event_type"] == "supplier_invoice.confirmed":
                for field in ("base","vat_amount","irpf_amount","issued_on"):
                    self.assertIsNone(payload[field])
        self.assertEqual(self.reconcile()["result"],"PASS")

    def test_tenant_session_flags_and_revoked_epoch_fail_closed(self):
        from noesis.financial_operations.contracts import Principal
        from noesis.financial_history.cutoff import EpochUnavailable
        self.scenario()
        result = self.reconcile()
        other = db.create_business("Otra",uuid4().hex+"@example.test")
        user = db.create_user(uuid4().hex+"@example.test","fixture",other["id"])
        with self.assertRaises(AccessDenied):
            self.reconciler.read(Principal(user["id"],0),result["reconciliation_uuid"])
        with self.assertRaises(AccessDenied):
            self.reconciler.reconcile(Principal(self.principal.user_id,99),self.epoch_uuid,self.manifest["manifest_uuid"],self.batch_uuid,uuid4())
        with patch.object(config,"FINANCIAL_CORE_ENABLED",True),self.assertRaises(AccessDenied):
            self.reconcile()
        self.importer.invalidate(self.principal,self.epoch_uuid,reason="fixture_revoke")
        with self.assertRaises(EpochUnavailable):
            self.reconcile()
        self.assertEqual(self.reconciler.read(self.principal,result["reconciliation_uuid"])["result"],result)

    def test_findings_and_result_corruption_never_returns_pass(self):
        self.scenario()
        with self.corruption("economic_event_sequences") as conn:
            conn.execute("UPDATE economic_event_sequences SET last_sequence=99 WHERE business_id=?",(self.bid,))
        result = self.reconcile()
        with self.corruption("financial_history_reconciliation_findings") as conn:
            conn.execute("UPDATE financial_history_reconciliation_findings SET actual_ref='changed' WHERE business_id=?",(self.bid,))
        with self.assertRaises(ConflictError):
            self.reconciler.read(self.principal,result["reconciliation_uuid"])

    def test_large_fixture_pagination_query_growth_no_n_plus_one(self):
        import time
        import tracemalloc
        self.sources()
        with db.get_conn() as conn:
            for index in range(128):
                conn.execute("INSERT INTO expenses (business_id,concept,amount,created_at,spent_on) VALUES (?,'Fixture','1.00','2026-09-01','2026-09-01')",(self.bid,))
        self.frozen()
        self.importer.run(self.principal,self.batch_uuid)
        before = self.snapshot()
        tracemalloc.start()
        started = time.monotonic()
        total_queries = 0
        original_execute = db.Connection.execute_exact
        def counted(connection,sql,params=()):
            nonlocal total_queries
            total_queries += 1
            return original_execute(connection,sql,params)
        with patch.object(db.Connection,"execute_exact",counted):
            result = self.reconcile()
        elapsed = time.monotonic()-started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(result["result"],"PASS",self.findings(result))
        self.assertLess(self.reconciler._last_queries, 350)
        self.assertLess(total_queries,600)
        self.assertLess(peak,20*1024*1024)
        self.assertEqual(before,self.snapshot())
        print(f"E_PERF sources=131 page=8 verifier_queries={self.reconciler._last_queries} total_queries={total_queries} seconds={elapsed:.3f} peak_bytes={peak}")
