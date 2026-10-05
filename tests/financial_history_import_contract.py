"""Fixtures reales sintéticos para1.9D, sin convertir dinero productivo."""

from datetime import datetime, timezone
import json
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db, migrations
from noesis.financial_history.importer import HistoryImporter
from noesis.financial_operations.contracts import Principal
from tests.financial_history_cutoff_contract import HistoryCutoffContract


class HistoryImportContract:
    seed = HistoryCutoffContract.seed
    draft = HistoryCutoffContract.draft
    issued = HistoryCutoffContract.issued
    movement = HistoryCutoffContract.movement
    approved = HistoryCutoffContract.approved
    empty_database = HistoryCutoffContract.empty_database

    def setup_import(self):
        self.seed()
        self.user = db.create_user(uuid4().hex + "@example.test", "fixture", self.bid)
        self.principal = Principal(self.user["id"], 0)
        self.importer = HistoryImporter(self.bid, page_size=8)
        self.epoch_uuid = str(uuid4())

    def exact_storage(self):
        # Esquema de fixture descartable, NO migración de fuentes legacy del producto.
        types = {
            "expenses": ("amount", "vat_rate"),
            "received_invoices": ("base", "vat_amount", "irpf_amount", "total", "vat_rate"),
            "bank_transactions": ("amount",),
            "invoice_payments": ("amount",),
        }
        with db.get_conn() as conn:
            if conn.dialect == "postgres":
                for table, columns in types.items():
                    for column in columns:
                        conn.execute(
                            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE NUMERIC USING {column}::numeric"
                        )
            else:
                conn.execute("PRAGMA writable_schema=ON")
                for table, columns in types.items():
                    ddl = conn.execute(
                        "SELECT sql FROM sqlite_master WHERE name=?", (table,)
                    ).fetchone()["sql"]
                    import re

                    for column in columns:
                        ddl = re.sub(r"\b" + column + r"\s+REAL\b", column + " TEXT", ddl)
                    conn.execute("UPDATE sqlite_master SET sql=? WHERE name=?", (ddl, table))
                version = conn.execute("PRAGMA schema_version").fetchone()["schema_version"]
                conn.execute(f"PRAGMA schema_version={version + 1}")
                conn.execute("PRAGMA writable_schema=OFF")

    def sources(self, *, expense_unknown=False, expense_vat=None, received_issued=None):
        self.exact_storage()
        with db.get_conn() as conn:
            expense = conn.execute(
                "INSERT INTO expenses (business_id,concept,amount,spent_on,category,created_at,_captured_vat_amount) VALUES (?,'Material','12.10',?,'material',?,?) RETURNING id",
                (
                    self.bid,
                    None if expense_unknown else "2026-09-01",
                    datetime(2026, 9, 1, tzinfo=timezone.utc).isoformat(),
                    expense_vat,
                ),
            ).fetchone()["id"]
            received = conn.execute(
                "INSERT INTO received_invoices (business_id,number,total,base,vat_amount,irpf_amount,status,created_at,issued_on) VALUES (?,'REC1','121.00',NULL,NULL,NULL,'pendiente',?,?) RETURNING id",
                (self.bid, datetime(2026, 9, 1, tzinfo=timezone.utc).isoformat(), received_issued),
            ).fetchone()["id"]
            bank = conn.execute(
                "INSERT INTO bank_transactions (business_id,import_hash,booked_on,amount,currency,status,created_at) VALUES (?,?,'2026-09-01','15.25','EUR','imported',?) RETURNING id",
                (self.bid, "a" * 64, datetime(2026, 9, 1, tzinfo=timezone.utc).isoformat()),
            ).fetchone()["id"]
        return expense, received, bank

    def frozen(self):
        self.importer.open(
            self.principal,
            self.epoch_uuid,
            repository_version="fixture",
            environment_identity="synthetic",
        )
        self.manifest = self.importer.inventory(
            self.principal,
            self.epoch_uuid,
            uuid4(),
            repository_version="fixture",
            environment_identity="synthetic",
        )
        self.batch_uuid = str(uuid4())
        self.importer.prepare(self.principal, self.manifest["manifest_uuid"], self.batch_uuid)
        with db.get_conn() as conn:
            return conn.execute(
                "SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND candidate_hash IS NOT NULL ORDER BY source_type",
                (self.bid, str(self.manifest["manifest_uuid"])),
            ).fetchall()

    def test_three_observed_v2_real_source_no_legacy_side_effects_retry(self):
        self.sources()
        rows = self.frozen()
        self.assertEqual(len(rows), 3)
        before = self.legacy_snapshot()
        first = [
            self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
            for row in rows
        ]
        self.assertEqual([r["state"] for r in first], ["recorded"] * 3)
        self.assertEqual(before, self.legacy_snapshot())
        again = [
            self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
            for row in rows
        ]
        self.assertEqual(first, again)
        self.assertTrue(self.importer.read(self.principal, self.epoch_uuid)["fence_enabled"])
        with db.get_conn() as conn:
            ops = conn.execute(
                "SELECT * FROM financial_operations WHERE business_id=?", (self.bid,)
            ).fetchall()
            auths = conn.execute(
                "SELECT * FROM financial_authorizations WHERE business_id=?", (self.bid,)
            ).fetchall()
            events = conn.execute_exact(
                "SELECT * FROM economic_events WHERE business_id=? ORDER BY business_sequence",
                (self.bid,),
            ).fetchall()
        self.assertEqual(len(ops), 3)
        self.assertEqual(len(auths), 3)
        self.assertEqual([e["business_sequence"] for e in events], [1, 2, 3])
        for op, auth in zip(ops, auths, strict=True):
            self.assertEqual(op["state"], "prepared")
            self.assertEqual(op["entry_namespace"], "historical")
            self.assertIsNone(op["result_canonical"])
            self.assertEqual(auth["kind"], "historical_unknown")
            self.assertIsNone(auth["actor_user_id"])
            self.assertIsNone(auth["actor_session_version"])
            self.assertEqual(auth["recorded_by"], self.principal.user_id)
        for e in events:
            self.assertEqual(e["origin"], "historical")
            self.assertEqual(e["payload_version"], 2)
            self.assertEqual(str(e["historical_batch_uuid"]), self.batch_uuid)
            self.assertEqual(json.loads(e["payload_canonical"])["evidence_basis"], "observed_state")

    def legacy_snapshot(self):
        from noesis.financial_history.sources import SOURCES
        from noesis.financial_history.service import FLAGS

        tables = {s.table for s in SOURCES.values()} - {"economic_events", "economic_event_links"}
        tables |= {
            "document_sequences",
            "financial_channel_proposals",
            "financial_channel_receipts",
            "recurring_invoices",
        }
        with db.get_conn() as conn:
            result = {}
            for table in sorted(tables):
                column = "id" if table == "businesses" else "business_id"
                result[table] = repr(
                    [
                        dict(r)
                        for r in conn.execute_exact(
                            f"SELECT * FROM {table} WHERE {column}=? ORDER BY 1,2", (self.bid,)
                        ).fetchall()
                    ]
                )
        result["flags"] = tuple(getattr(config, f) for f in FLAGS)
        return result

    def test_crash_all_precommit_checkpoints_rollback_and_response_loss(self):
        self.sources()
        row = self.frozen()[0]
        for stage in (
            "before_intent",
            "intent",
            "operation",
            "authorization",
            "links",
            "event",
            "result",
        ):
            with self.subTest(stage=stage):

                def crash(step):
                    if step == stage:
                        raise KeyboardInterrupt("fixture crash")

                with (
                    patch.object(self.importer, "_checkpoint", side_effect=crash),
                    self.assertRaises(KeyboardInterrupt),
                ):
                    self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
                with db.get_conn() as conn:
                    for table in (
                        "financial_operations",
                        "financial_authorizations",
                        "economic_events",
                        "financial_history_import_items",
                    ):
                        self.assertFalse(
                            conn.execute(
                                f"SELECT 1 FROM {table} WHERE business_id=?", (self.bid,)
                            ).fetchone()
                        )
                    seq = conn.execute(
                        "SELECT last_sequence FROM economic_event_sequences WHERE business_id=?",
                        (self.bid,),
                    ).fetchone()
                    self.assertFalse(seq)
                self.assertTrue(
                    self.importer.read(self.principal, self.epoch_uuid)["fence_enabled"]
                )
        with (
            patch.object(
                self.importer,
                "_checkpoint",
                side_effect=lambda step: (
                    (_ for _ in ()).throw(TimeoutError()) if step == "committed" else None
                ),
            ),
            self.assertRaises(TimeoutError),
        ):
            self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
        self.assertEqual(
            self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])["state"],
            "recorded",
        )

    def test_empty_migration_cycle_and_retention(self):
        for initial in (0, 71):
            with self.empty_database(initial):
                self.assertEqual(migrations.upgrade(72), 72)
                self.assertEqual(migrations.downgrade(71), 71)
                self.assertEqual(migrations.upgrade(72), 72)
        self.sources()
        row = self.frozen()[0]
        self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
        with self.assertRaisesRegex(ValueError, "histórica"):
            migrations.downgrade(71)

    def test_sql_historical_operation_cannot_promote_or_receive_human_mandate(self):
        from noesis.financial_operations.service import FinancialOperations
        from noesis.financial_operations.contracts import StateError

        self.sources()
        result = self.importer.record_item(
            self.principal,
            self.batch_uuid if hasattr(self, "batch_uuid") else self.frozen_batch(),
            self.first_item(),
        )
        op, auth = result["operation_uuid"], result["authorization_uuid"]
        for fragment in (
            "state='approved'",
            "state='committed'",
            "state='cancelled'",
            "entry_namespace='web_api'",
        ):
            with (
                self.subTest(fragment=fragment),
                self.assertRaises(Exception),
                db.get_conn() as conn,
            ):
                conn.execute(
                    f"UPDATE financial_operations SET {fragment} WHERE business_id=? AND operation_uuid=?",
                    (self.bid, op),
                )
        for kind, permission in (
            ("human_confirmation", "financial.authorize"),
            ("mandate", "financial.mandate"),
        ):
            with self.subTest(kind=kind), self.assertRaises(Exception), db.get_conn() as conn:
                conn.execute(
                    """INSERT INTO financial_authorizations (business_id,authorization_uuid,operation_uuid,kind,
                    actor_user_id,recorded_by,actor_session_version,validated_permission,approved_request_hash,approved_revision,channel,authorized_at)
                    SELECT business_id,?,operation_uuid,?,?,recorded_by,0,?,approved_request_hash,approved_revision,'web_api',authorized_at
                    FROM financial_authorizations WHERE business_id=? AND authorization_uuid=?""",
                    (str(uuid4()), kind, self.principal.user_id, permission, self.bid, auth),
                )
        with self.assertRaises(StateError):
            FinancialOperations(self.bid).execute(
                self.principal, op, lambda *_: self.fail("No ejecutar")
            )

    def frozen_batch(self):
        self.frozen()
        return self.batch_uuid

    def first_item(self):
        with db.get_conn() as conn:
            return str(
                conn.execute(
                    "SELECT item_uuid FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND candidate_hash IS NOT NULL ORDER BY source_type LIMIT 1",
                    (self.bid, str(self.manifest["manifest_uuid"])),
                ).fetchone()["item_uuid"]
            )

    def test_new_operator_retry_and_new_manifest_preserve_original_batch_hash_dates(self):
        self.sources()
        rows = self.frozen()
        first = self.importer.record_item(self.principal, self.batch_uuid, rows[0]["item_uuid"])
        other = db.create_user(uuid4().hex + "@example.test", "fixture", self.bid)
        principal = Principal(other["id"], 0)
        self.assertEqual(
            first, self.importer.record_item(principal, self.batch_uuid, rows[0]["item_uuid"])
        )
        old_batch = self.batch_uuid
        manifest2 = self.importer.inventory(
            self.principal,
            self.epoch_uuid,
            uuid4(),
            repository_version="fixture",
            environment_identity="synthetic",
        )
        batch2 = str(uuid4())
        self.importer.prepare(principal, manifest2["manifest_uuid"], batch2)
        second = self.importer.record_item(principal, batch2, rows[0]["item_uuid"])
        self.assertEqual(second["state"], "covered_existing")
        self.assertEqual(first["event_uuid"], second["event_uuid"])
        self.assertEqual(first["record_hash"], second["record_hash"])
        with db.get_conn() as conn:
            event = conn.execute(
                "SELECT historical_batch_uuid FROM economic_events WHERE business_id=? AND event_uuid=?",
                (self.bid, first["event_uuid"]),
            ).fetchone()
            self.assertEqual(str(event["historical_batch_uuid"]), old_batch)
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM economic_events WHERE business_id=?", (self.bid,)
            ).fetchone()["n"]
            self.assertEqual(count, 1)

    def test_same_candidate_new_batch_references_existing_without_reappend(self):
        self.sources()
        rows = self.frozen()
        result = self.importer.record_item(self.principal, self.batch_uuid, rows[0]["item_uuid"])
        batch2 = str(uuid4())
        self.importer.prepare(self.principal, self.manifest["manifest_uuid"], batch2)
        existing = self.importer.record_item(self.principal, batch2, rows[0]["item_uuid"])
        self.assertEqual(existing["state"], "existing")
        self.assertEqual(result["event_uuid"], existing["event_uuid"])
        self.assertEqual(result["record_hash"], existing["record_hash"])

    def test_sql_intent_scope_mismatches_and_unfinished_commit_rejected(self):
        from noesis.financial_history.import_repository import ImportRepository

        self.sources()
        row = self.frozen()[0]
        saved = {}

        def stop(step):
            if step == "intent":
                saved.update(
                    dict(
                        ImportRepository(session, self.bid, self.batch_uuid).item(
                            str(row["item_uuid"])
                        )
                    )
                )
                raise KeyboardInterrupt()

        with (
            self.assertRaises(KeyboardInterrupt),
            self.importer._session(self.principal) as session,
            patch.object(self.importer, "_checkpoint", side_effect=stop),
        ):
            self.importer._record_item(
                session, self.principal, self.batch_uuid, str(row["item_uuid"])
            )
        for fields in (
            {"manifest_uuid": str(uuid4())},
            {"item_uuid": str(uuid4())},
            {"candidate_hash": "b" * 64},
            {"raw_hash": "b" * 64},
            {
                "expected_event_canonical": saved["expected_event_canonical"].replace(
                    "15.25", "16.25"
                )
            },
            {"expected_event_uuid": str(uuid4())},
            {"session_version": 999},
        ):
            with (
                self.subTest(fields=fields),
                self.assertRaises(Exception),
                self.importer._session(self.principal) as session,
            ):
                session.execute(
                    "UPDATE financial_history_import_batches SET state='running' WHERE business_id=? AND batch_uuid=?",
                    (self.bid, self.batch_uuid),
                )
                values = saved | fields
                columns = tuple(values)
                session.execute(
                    "INSERT INTO financial_history_import_items ("
                    + ",".join(columns)
                    + ") VALUES ("
                    + ",".join("?" for _ in columns)
                    + ")",
                    tuple(values.values()),
                )
        # El intent válido tampoco se puede confirmar incompleto (FK propia diferida).
        with self.assertRaises(Exception), self.importer._session(self.principal) as session:
            session.execute(
                "UPDATE financial_history_import_batches SET state='running' WHERE business_id=? AND batch_uuid=?",
                (self.bid, self.batch_uuid),
            )
            session.execute(
                "INSERT INTO financial_history_import_items ("
                + ",".join(saved)
                + ") VALUES ("
                + ",".join("?" for _ in saved)
                + ")",
                tuple(saved.values()),
            )
        with db.get_conn() as conn:
            self.assertFalse(
                conn.execute(
                    "SELECT 1 FROM financial_history_import_items WHERE business_id=?", (self.bid,)
                ).fetchone()
            )
        self.assertEqual(
            self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])["state"],
            "recorded",
        )

    def test_epoch_released_invalidated_and_diagnostic_never_import(self):
        from noesis.financial_history.cutoff import EpochUnavailable
        from noesis.financial_history.service import HistoryDiagnostics
        from noesis.financial_operations.contracts import AccessDenied

        self.sources()
        diagnostic = HistoryDiagnostics(self.bid).run(
            self.principal, uuid4(), repository_version="fixture", environment_identity="synthetic"
        )
        with self.assertRaises(AccessDenied):
            self.importer.prepare(self.principal, diagnostic["manifest_uuid"], uuid4())
        row = self.frozen()[0]
        self.importer.invalidate(self.principal, self.epoch_uuid, reason="fixture_invalidated")
        with self.assertRaises(EpochUnavailable):
            self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
        self.importer.release(self.principal, self.epoch_uuid, reason="fixture_released")
        with self.assertRaises(EpochUnavailable):
            self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])

    def test_flags_session_subscription_and_cross_tenant_block(self):
        from noesis.financial_history.service import FLAGS
        from noesis.financial_operations.contracts import AccessDenied

        self.sources()
        row = self.frozen()[0]
        for flag in FLAGS:
            with patch.object(config, flag, True), self.assertRaises(AccessDenied):
                self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
        other = db.create_business("Otro", "other@example.test")
        principal = Principal(
            db.create_user(uuid4().hex + "@example.test", "fixture", other["id"])["id"], 0
        )
        with self.assertRaises(AccessDenied):
            self.importer.record_item(principal, self.batch_uuid, row["item_uuid"])
        with self.assertRaises(AccessDenied):
            self.importer.record_item(
                Principal(self.principal.user_id, 99), self.batch_uuid, row["item_uuid"]
            )
        self.assertEqual(
            self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])["state"],
            "recorded",
        )

    def test_partial_safe_independent_candidates_keep_fence(self):
        self.sources()
        result = self.importer.run(self.principal, self.frozen_batch())
        self.assertEqual(result["state"], "partial")
        self.assertEqual(sum(r["state"] == "recorded" for r in result["results"]), 3)
        self.assertTrue(self.importer.read(self.principal, self.epoch_uuid)["fence_enabled"])

    def test_binary_ambiguous_sources_never_promoted(self):
        db.add_expense("Material", "12.10", business_id=self.bid)
        self.frozen()
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT item_uuid FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND source_type='expense'",
                (self.bid, str(self.manifest["manifest_uuid"])),
            ).fetchone()
        result = self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
        self.assertEqual(result["state"], "blocked")
        with db.get_conn() as conn:
            self.assertFalse(
                conn.execute(
                    "SELECT 1 FROM economic_events WHERE business_id=?", (self.bid,)
                ).fetchone()
            )

    def payment_source(self):
        from noesis.invoice_capture.service import InvoiceCapture

        invoice = InvoiceCapture(self.bid)
        op = self.approved(invoice, invoice.review(self.principal, self.draft()["id"]))
        original = invoice.execute(self.principal, op.operation_uuid)
        iid = original.result["invoice_id"]
        self.exact_storage()
        with db.get_conn() as conn:
            return conn.execute(
                "INSERT INTO invoice_payments (business_id,invoice_id,amount,method,paid_at,created_at) VALUES (?,?,'10.00','efectivo','2026-09-01','2026-09-01T00:00:00') RETURNING id",
                (self.bid, iid),
            ).fetchone()["id"]

    def test_payment_v1_exact_live_parent_verified_and_topological(self):
        self.payment_source()
        rows = self.frozen()
        row = next(r for r in rows if r["source_type"] == "invoice_payment")
        before = self.legacy_snapshot()
        result = self.importer.run(self.principal, self.batch_uuid)
        payment = next(r for r in result["results"] if r["item_uuid"] == str(row["item_uuid"]))
        self.assertEqual(payment["state"], "recorded")
        self.assertEqual(before, self.legacy_snapshot())
        with db.get_conn() as conn:
            event = conn.execute_exact(
                "SELECT * FROM economic_events WHERE business_id=? AND event_uuid=?",
                (self.bid, payment["event_uuid"]),
            ).fetchone()
            self.assertEqual(event["payload_version"], 1)
            self.assertEqual(event["origin"], "historical")
            links = conn.execute(
                "SELECT * FROM economic_event_links WHERE business_id=? AND event_uuid=?",
                (self.bid, payment["event_uuid"]),
            ).fetchall()
            self.assertEqual(len(links), 1)
            self.assertEqual(links[0]["relation_type"], "settles")
        # Un corte posterior reconoce también v1 histórico sin fabricar coverage live.
        manifest2 = self.importer.inventory(
            self.principal,
            self.epoch_uuid,
            uuid4(),
            repository_version="fixture",
            environment_identity="synthetic",
        )
        batch2 = str(uuid4())
        self.importer.prepare(self.principal, manifest2["manifest_uuid"], batch2)
        existing = self.importer.record_item(self.principal, batch2, row["item_uuid"])
        self.assertEqual(existing["state"], "covered_existing")
        self.assertEqual(existing["event_uuid"], payment["event_uuid"])
        self.assertEqual(existing["record_hash"], payment["record_hash"])

    def test_sql_only_exact_expected_event_allowed_and_no_intent_live_historical_rejected(self):
        self.sources()
        row = self.frozen()[0]

        def check(step):
            if step == "links":
                from noesis.financial_history.import_repository import ImportRepository

                x = ImportRepository(session, self.bid, self.batch_uuid).item(str(row["item_uuid"]))
                # Intent ligado a un evento; otro UUID no puede consumirlo.
                with self.assertRaises(Exception):
                    session.execute("SAVEPOINT invalid_uuid")
                    session.execute(
                        "INSERT INTO economic_event_links (business_id,event_uuid,target_event_uuid,relation_type,recorded_at) VALUES (?,?,?,'matches',?)",
                        (self.bid, str(uuid4()), str(uuid4()), x["created_at"]),
                    )
                session.execute("ROLLBACK TO SAVEPOINT invalid_uuid")
                session.execute("RELEASE SAVEPOINT invalid_uuid")

        with (
            self.importer._session(self.principal) as session,
            patch.object(self.importer, "_checkpoint", side_effect=check),
        ):
            result = self.importer._record_item(
                session, self.principal, self.batch_uuid, str(row["item_uuid"])
            )
        with db.get_conn() as conn:
            event = dict(
                conn.execute_exact(
                    "SELECT * FROM economic_events WHERE business_id=? AND event_uuid=?",
                    (self.bid, result["event_uuid"]),
                ).fetchone()
            )
        for origin in ("historical", "live"):
            values = event | {"event_uuid": str(uuid4()), "origin": origin}
            values.pop("id")
            with self.subTest(origin=origin), self.assertRaises(Exception), db.get_conn() as conn:
                conn.execute(
                    "INSERT INTO economic_events ("
                    + ",".join(values)
                    + ") VALUES ("
                    + ",".join("?" for _ in values)
                    + ")",
                    tuple(values.values()),
                )

    def test_real_source_drift_invalidates_after_rollback_keeps_fence_and_frozen_bytes(self):
        self.sources()
        rows = self.frozen()
        row = next(r for r in rows if r["source_type"] == "expense")
        # Corrupción por propietario DDL en fixture: la API normal continúa bloqueada.
        with db.get_conn() as conn:
            name = "aaa_history_fence_expenses_update"
            if conn.dialect == "sqlite":
                ddl = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE name=?", (name,)
                ).fetchone()["sql"]
                conn.execute("DROP TRIGGER " + name)
            else:
                ddl = conn.execute(
                    "SELECT pg_get_triggerdef(oid) AS ddl FROM pg_trigger WHERE tgname=? AND tgrelid='expenses'::regclass",
                    (name,),
                ).fetchone()["ddl"]
                conn.execute("DROP TRIGGER " + name + " ON expenses")
            conn.execute(
                "UPDATE expenses SET amount='13.10' WHERE business_id=? AND id=?",
                (self.bid, int(row["source_id"])),
            )
            conn.execute(ddl)
        before = self.legacy_snapshot()
        result = self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["reason"], "SOURCE_DRIFT")
        self.assertEqual(before, self.legacy_snapshot())
        epoch = self.importer.read(self.principal, self.epoch_uuid)
        self.assertEqual(epoch["state"], "invalidated")
        self.assertTrue(epoch["fence_enabled"])
        with db.get_conn() as conn:
            current = conn.execute(
                "SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND item_uuid=?",
                (self.bid, str(self.manifest["manifest_uuid"]), str(row["item_uuid"])),
            ).fetchone()
            self.assertEqual(row["raw_hash"], current["raw_hash"])
            self.assertEqual(row["candidate_hash"], current["candidate_hash"])
            self.assertFalse(
                conn.execute(
                    "SELECT 1 FROM financial_operations WHERE business_id=? AND entry_namespace='historical'",
                    (self.bid,),
                ).fetchone()
            )

    def test_closed_durable_matrix_known_unknown_dates_null_vs_zero_and_no_float(self):
        from dataclasses import replace
        from noesis.economic_events.contracts import EconomicEvent
        from noesis.economic_events.persistence import StoredEvent

        self.sources(expense_unknown=True, expense_vat="0.00")
        rows = self.frozen()
        for row in rows:
            result = self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
            with db.get_conn() as conn:
                stored = StoredEvent.from_row(
                    conn.execute_exact(
                        "SELECT * FROM economic_events WHERE business_id=? AND event_uuid=?",
                        (self.bid, result["event_uuid"]),
                    ).fetchone()
                )
            event = stored.event
            params = {
                f: getattr(event, f)
                for f in (
                    "event_id",
                    "business_id",
                    "event_type",
                    "source_type",
                    "source_id",
                    "source_revision",
                    "occurred_at",
                    "observed_at",
                    "payload",
                    "payload_version",
                    "currency",
                    "relations",
                )
            }
            with self.assertRaises(ValueError):
                EconomicEvent(**params)
            with self.assertRaises((ValueError, TypeError)):
                replace(
                    event,
                    payload=dict(event.payload)
                    | {
                        "amount" if event.source_type.value == "bank_transaction" else "total": 12.1
                    },
                )
            if row["source_type"] == "expense":
                self.assertIsNone(event.economic_date)
                self.assertEqual(str(event.payload["vat_amount"]), "0.00")
            elif row["source_type"] == "received_invoice":
                self.assertIsNone(event.economic_date)
                self.assertIsNone(event.payload["vat_amount"])
            else:
                self.assertEqual(event.economic_date.isoformat(), "2026-09-01")

    def test_conflicting_durable_content_blocks_retry_preserves_original_result(self):
        self.sources()
        row = self.frozen()[0]
        first = self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
        with db.get_conn() as conn:
            # Simular corrupción por DDL privilegiado exclusivamente en este fixture.
            if conn.dialect == "postgres":
                guards = conn.execute(
                    "SELECT tgname AS name,pg_get_triggerdef(oid) AS sql FROM pg_trigger WHERE tgrelid='economic_events'::regclass AND (tgtype & 16)>0 AND NOT tgisinternal"
                ).fetchall()
            else:
                guards = conn.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='economic_events' AND upper(sql) LIKE '%BEFORE UPDATE%'"
                ).fetchall()
            for guard in guards:
                conn.execute(
                    "DROP TRIGGER "
                    + guard["name"]
                    + (" ON economic_events" if conn.dialect == "postgres" else "")
                )
            conn.execute(
                "UPDATE economic_events SET record_hash=? WHERE business_id=? AND event_uuid=?",
                ("b" * 64, self.bid, first["event_uuid"]),
            )
            for guard in guards:
                conn.execute(guard["sql"])
        retry = self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
        self.assertEqual(retry["state"], "blocked")
        self.assertEqual(retry["reason"], "EXISTING_EVENT_CONFLICT")
        audit = self.importer.read_batch(self.principal, self.batch_uuid)
        self.assertEqual(audit["blocking_code"], "EXISTING_EVENT_CONFLICT")
        self.assertEqual(audit["results"], [first])
        self.assertTrue(self.importer.read(self.principal, self.epoch_uuid)["fence_enabled"])

    def test_historical_parent_real_event_and_unverified_missing_cross_business_block(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from noesis.financial_history.contracts import (
            Assessment,
            Classification,
            Disposition,
            HistoricalDependency,
            IncidenceCode,
            RuleId,
            ReasonCode,
            Severity,
        )
        from noesis.financial_history.import_contracts import candidate as decode_candidate
        from noesis.financial_history.importer import ImportBlocked

        self.payment_source()
        row = next(r for r in self.frozen() if r["source_type"] == "invoice_payment")
        result = self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
        with self.importer._session(self.principal) as session:
            base = session.execute(
                "SELECT started_at FROM financial_history_manifests WHERE business_id=? AND manifest_uuid=?",
                (self.bid, str(self.manifest["manifest_uuid"])),
            ).fetchone()
            parent = decode_candidate(row["candidate_canonical"], base["started_at"])
            dependency = HistoricalDependency("matches", parent.identity, parent.assessment)
            # Resolver el componente exacto payment del futuro match; no crear hijo.
            child = SimpleNamespace(dependencies=(dependency,), dates=parent.dates)
            relations = self.importer._dependencies(
                session, str(self.manifest["manifest_uuid"]), child
            )
            self.assertEqual(str(relations[0].target_event_id), result["event_uuid"])
            for category, rule, reason in (
                (Classification.OBSERVED_STATE, RuleId.OBSERVED, ReasonCode.OBSERVED_STATE),
            ):
                bad = replace(
                    parent.assessment, classification=category, rule_id=rule, reason=reason
                )
                with self.assertRaises(ImportBlocked):
                    self.importer._dependencies(
                        session,
                        str(self.manifest["manifest_uuid"]),
                        SimpleNamespace(
                            dependencies=(replace(dependency, parent_assessment=bad),),
                            dates=parent.dates,
                        ),
                    )
            for target in (
                replace(parent.identity, source=replace(parent.identity.source, source_id=999999)),
                replace(
                    parent.identity,
                    source=replace(parent.identity.source, business_id=self.bid + 999999),
                ),
            ):
                with self.assertRaises(ImportBlocked):
                    self.importer._dependencies(
                        session,
                        str(self.manifest["manifest_uuid"]),
                        SimpleNamespace(
                            dependencies=(replace(dependency, target=target),), dates=parent.dates
                        ),
                    )
            for category, rule in (
                (Classification.AMBIGUOUS, RuleId.AMBIGUOUS),
                (Classification.NOT_AUTOMATICALLY_TRANSFORMABLE, RuleId.NOT_TRANSFORMABLE),
            ):
                bad = Assessment(
                    category,
                    Disposition.PENDING_INCIDENCE,
                    Severity.BLOCKING,
                    rule,
                    1,
                    ReasonCode.INCIDENCE,
                    parent.assessment.evidence_hashes,
                    IncidenceCode.SOURCE_HISTORY_LOST,
                )
                with self.assertRaises(ImportBlocked):
                    self.importer._dependencies(
                        session,
                        str(self.manifest["manifest_uuid"]),
                        SimpleNamespace(
                            dependencies=(replace(dependency, parent_assessment=bad),),
                            dates=parent.dates,
                        ),
                    )
            # El contrato del hijo rechaza una relación fuera de su catálogo.
            with self.assertRaises(ValueError):
                replace(parent, dependencies=(dependency,))
            # Corrupción DDL del antecedente histórico: ni proof ni UUID bastan.
            conn = session.borrowed_connection
            if conn.dialect == "postgres":
                guards = conn.execute(
                    "SELECT tgname AS name,pg_get_triggerdef(oid) AS sql FROM pg_trigger WHERE tgrelid='economic_events'::regclass AND (tgtype & 16)>0 AND NOT tgisinternal"
                ).fetchall()
            else:
                guards = conn.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='economic_events' AND upper(sql) LIKE '%BEFORE UPDATE%'"
                ).fetchall()
            conn.execute("SAVEPOINT parent_corruption")
            try:
                for guard in guards:
                    conn.execute(
                        "DROP TRIGGER "
                        + guard["name"]
                        + (" ON economic_events" if conn.dialect == "postgres" else "")
                    )
                conn.execute(
                    "UPDATE economic_events SET record_hash=? WHERE business_id=? AND event_uuid=?",
                    ("b" * 64, self.bid, result["event_uuid"]),
                )
                with self.assertRaises(ImportBlocked):
                    self.importer._dependencies(session, str(self.manifest["manifest_uuid"]), child)
            finally:
                conn.execute("ROLLBACK TO SAVEPOINT parent_corruption")
                conn.execute("RELEASE SAVEPOINT parent_corruption")

    def test_supplier_known_economic_date_not_invented_confirmation_date(self):
        from noesis.economic_events.persistence import StoredEvent

        self.sources(received_issued="2026-09-01")
        row = next(r for r in self.frozen() if r["source_type"] == "received_invoice")
        result = self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])
        with db.get_conn() as conn:
            event = StoredEvent.from_row(
                conn.execute_exact(
                    "SELECT * FROM economic_events WHERE business_id=? AND event_uuid=?",
                    (self.bid, result["event_uuid"]),
                ).fetchone()
            ).event
        self.assertEqual(event.economic_date.isoformat(), "2026-09-01")
        self.assertIsNone(event.payload["confirmed_on"])
        self.assertEqual(event.payload["evidence_basis"], "observed_state")

    def test_migration_71_72_preserves_existing_live_bytes_hashes_links_and_sequences(self):
        from noesis.purchasing_capture import ExpenseCapture
        from noesis.economic_events.persistence import StoredEvent

        with self.empty_database(71):
            self.setup_import()
            self.payment_source()
            capture = ExpenseCapture(self.bid)
            confirmed = capture.execute(
                self.principal,
                self.approved(
                    capture,
                    capture.review_confirm(self.principal, amount="12.10", concept="Material"),
                ).operation_uuid,
            )
            capture.execute(
                self.principal,
                self.approved(
                    capture,
                    capture.review_void(
                        self.principal, confirmed.result["source_id"], reason="Duplicado"
                    ),
                ).operation_uuid,
            )

            def snapshot():
                with db.get_conn() as conn:
                    return {
                        table: [
                            dict(r)
                            for r in conn.execute_exact(
                                f"SELECT * FROM {table} WHERE business_id=? ORDER BY 1,2",
                                (self.bid,),
                            ).fetchall()
                        ]
                        for table in (
                            "economic_events",
                            "economic_event_links",
                            "economic_event_sequences",
                        )
                    }

            original = snapshot()
            payload_hashes = [
                StoredEvent.from_row(r).event.payload_hash for r in original["economic_events"]
            ]
            event_bytes = [
                StoredEvent.from_row(r).event.canonical_bytes() for r in original["economic_events"]
            ]
            self.assertEqual({r["payload_version"] for r in original["economic_events"]}, {1, 2})
            self.assertEqual(len(original["economic_event_links"]), 1)
            # Fallo posterior al CHECK: ni DDL parcial ni datos perdidos.
            with patch(
                "noesis.financial_history.import_schema.guard",
                side_effect=RuntimeError("migration fixture"),
            ):
                with self.assertRaises(RuntimeError):
                    migrations.upgrade(72)
            self.assertEqual(migrations.current_version(), 71)
            self.assertEqual(snapshot(), original)
            for version in (72, 71, 72):
                action = migrations.upgrade if version == 72 else migrations.downgrade
                self.assertEqual(action(version), version)
                self.assertEqual(snapshot(), original)
                for row, payload_hash, event_canonical in zip(
                    snapshot()["economic_events"], payload_hashes, event_bytes, strict=True
                ):
                    stored = StoredEvent.from_row(row)
                    self.assertEqual(stored.event.content_hash, row["content_hash"])
                    self.assertEqual(stored.event.payload_hash, payload_hash)
                    self.assertEqual(stored.event.canonical_bytes(), event_canonical)
