"""Regresión de la capa observacional de valor, WUB y confianza."""

from __future__ import annotations

import gc
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, migrations, value_ledger
from noesis.web import auth


class ValueLedgerTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_db = config.DB_PATH
        self.old_url = config.DATABASE_URL
        self.old_enabled = config.VALUE_LEDGER_ENABLED
        self.old_admin_enabled = config.VALUE_LEDGER_ADMIN_ENABLED
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "value-ledger.db"
        config.VALUE_LEDGER_ENABLED = True
        config.VALUE_LEDGER_ADMIN_ENABLED = False
        db.init_db()
        self.business = db.create_business("Negocio A", "a@example.com")
        self.other = db.create_business("Negocio B", "b@example.com")

    def tearDown(self):
        config.DB_PATH = self.old_db
        config.DATABASE_URL = self.old_url
        config.VALUE_LEDGER_ENABLED = self.old_enabled
        config.VALUE_LEDGER_ADMIN_ENABLED = self.old_admin_enabled
        # Windows puede tardar unos milisegundos en liberar el último handle WAL
        # tras una prueba de downgrade. Reintentamos de forma acotada; una fuga
        # persistente sigue haciendo fallar la prueba.
        for attempt in range(5):
            try:
                self.tempdir.cleanup()
                break
            except PermissionError:
                if attempt == 4:
                    raise
                gc.collect()
                time.sleep(0.05 * (attempt + 1))

    def _action(self, family, entity_id, *, business_id=None, at=None, key=None):
        return value_ledger.record_useful_action(
            business_id or self.business["id"],
            family,
            entity_type="test",
            entity_id=entity_id,
            idempotency_key=key,
            completed_at=at,
        )

    def _eligible(self, business_id, created_at="2026-01-01T09:00:00"):
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE businesses SET onboarding_done=TRUE, "
                "onboarding_profile_completed=TRUE, "
                "onboarding_preferences_completed=TRUE, "
                "subscription_status='active', created_at=? WHERE id=?",
                (created_at, business_id),
            )

    def test_taxonomy_is_central_versioned_and_binary_for_wub(self):
        self.assertEqual(value_ledger.TAXONOMY_VERSION, 1)
        self.assertFalse(value_ledger.ACTION_TAXONOMY["quote_prepared"].counts_for_wub)
        self.assertTrue(value_ledger.ACTION_TAXONOMY["quote_sent"].counts_for_wub)
        self.assertEqual(
            value_ledger.ACTION_TAXONOMY["invoice_issued"].process,
            "invoicing",
        )

    def test_action_is_idempotent_and_tenant_scoped(self):
        first = self._action("job_created", 10, key="same-key")
        repeated = self._action("job_created", 10, key="same-key")
        other = self._action(
            "job_created", 10, key="same-key", business_id=self.other["id"]
        )

        self.assertEqual(first["id"], repeated["id"])
        self.assertNotEqual(first["id"], other["id"])
        self.assertEqual(len(value_ledger.list_useful_actions(self.business["id"])), 1)
        self.assertEqual(len(value_ledger.list_useful_actions(self.other["id"])), 1)

    def test_origin_channel_and_completion_are_independent(self):
        with value_ledger.observation_context(
            channel="whatsapp",
            trigger_source="noesis_proposed",
            completion_mode="user_confirmed",
        ):
            action = self._action("payment_reminder_sent", 20)

        self.assertEqual(action["channel"], "whatsapp")
        self.assertEqual(action["trigger_source"], "noesis_proposed")
        self.assertEqual(action["completion_mode"], "user_confirmed")

    def test_wub_requires_three_core_actions_and_two_processes(self):
        start = datetime(2026, 8, 24, tzinfo=timezone.utc)
        self._action("job_created", 1, at=start + timedelta(hours=1))
        self._action("job_completed", 1, at=start + timedelta(hours=2))
        self._action("quote_prepared", 2, at=start + timedelta(hours=3))
        before = value_ledger.wub_snapshot(
            self.business["id"], start=start, end=start + timedelta(days=7)
        )
        self.assertFalse(before["is_wub"])
        self.assertEqual(before["core_actions"], 2)

        invoice = self._action("invoice_issued", 3, at=start + timedelta(hours=4))
        after = value_ledger.wub_snapshot(
            self.business["id"], start=start, end=start + timedelta(days=7)
        )
        self.assertTrue(after["is_wub"])
        self.assertEqual(after["process_count"], 2)

        value_ledger.transition_useful_action(
            self.business["id"], invoice["id"], "reverted", reason_code="test"
        )
        reverted = value_ledger.wub_snapshot(
            self.business["id"], start=start, end=start + timedelta(days=7)
        )
        self.assertFalse(reverted["is_wub"])

    def test_official_week_is_closed_monday_to_monday_in_business_timezone(self):
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE businesses SET timezone='Europe/Madrid' WHERE id=?",
                (self.business["id"],),
            )
        # 23:30 UTC del domingo ya es lunes en Madrid y queda fuera de la
        # semana cerrada que termina en ese lunes local.
        for index, family in enumerate(
            ("job_created", "job_completed", "invoice_issued"), start=1
        ):
            self._action(
                family,
                100 + index,
                at=datetime(2026, 8, 30, 23, 30, tzinfo=timezone.utc),
                key=f"boundary:{index}",
            )
        snapshot = value_ledger.official_wub(
            self.business["id"],
            as_of=datetime(2026, 8, 31, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(snapshot["core_actions"], 0)

    def test_consistency_counts_last_four_closed_weeks_and_streak(self):
        as_of = datetime(2026, 8, 31, 10, tzinfo=timezone.utc)
        for weeks_back in (0, 1):
            start, _end = value_ledger._closed_week_bounds(
                as_of - timedelta(days=7 * weeks_back), "Europe/Madrid"
            )
            for index, family in enumerate(
                ("job_created", "job_completed", "invoice_issued"), start=1
            ):
                self._action(
                    family,
                    f"{weeks_back}-{index}",
                    at=start + timedelta(hours=index),
                    key=f"week:{weeks_back}:{index}",
                )
        result = value_ledger.wub_consistency(
            self.business["id"], as_of=as_of, weeks=4
        )
        self.assertEqual(result["label"], "2/4")
        self.assertEqual(result["consecutive_wub_weeks"], 2)

    def test_weekly_rate_excludes_demo_onboarding_and_new_accounts(self):
        self._eligible(self.business["id"])
        self._eligible(self.other["id"])
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE businesses SET is_demo=TRUE WHERE id=?", (self.other["id"],)
            )
        start = datetime(2026, 8, 24, tzinfo=timezone.utc)
        for index, family in enumerate(
            ("job_created", "job_completed", "invoice_issued"), start=1
        ):
            self._action(family, index, at=start + timedelta(hours=index))
        result = value_ledger.weekly_wub_rate(
            as_of=datetime(2026, 8, 31, 12, tzinfo=timezone.utc)
        )
        self.assertEqual(result["eligible_businesses"], 1)
        self.assertEqual(result["wub_rate"], 100.0)
        self.assertEqual(result["excluded"]["demo"], 1)

    def test_wub_query_uses_the_business_and_time_index(self):
        with db.get_conn() as conn:
            plan = conn.execute(
                "EXPLAIN QUERY PLAN SELECT id FROM useful_actions "
                "WHERE business_id=? AND counts_for_wub=TRUE "
                "AND status IN ('completed','corrected') "
                "AND completed_at>=? AND completed_at<?",
                (self.business["id"], "2026-08-01", "2026-09-01"),
            ).fetchall()
        detail = " ".join(str(row["detail"]) for row in plan)
        self.assertIn("idx_useful_actions_wub", detail)

    def test_outcomes_support_many_to_many_and_reject_cross_tenant_links(self):
        one = self._action("job_completed", 1)
        two = self._action("invoice_issued", 2)
        outcome = value_ledger.record_useful_outcome(
            self.business["id"],
            "job_invoiced",
            attribution_type="direct",
            attribution_method="test_v1",
            entity_type="job_invoice",
            entity_id="1:2",
            idempotency_key="outcome:1",
            useful_action_ids=[one["id"], two["id"]],
        )
        repeated = value_ledger.record_useful_outcome(
            self.business["id"],
            "job_invoiced",
            attribution_type="direct",
            attribution_method="test_v1",
            entity_type="job_invoice",
            entity_id="1:2",
            idempotency_key="outcome:1",
            useful_action_ids=[one["id"], two["id"]],
        )
        self.assertEqual(outcome["id"], repeated["id"])
        with db.get_conn() as conn:
            links = conn.execute(
                "SELECT COUNT(*) AS n FROM useful_action_outcomes "
                "WHERE business_id=? AND useful_outcome_id=?",
                (self.business["id"], outcome["id"]),
            ).fetchone()["n"]
        self.assertEqual(links, 2)
        with self.assertRaises(ValueError):
            value_ledger.record_useful_outcome(
                self.other["id"],
                "job_invoiced",
                attribution_type="direct",
                attribution_method="test_v1",
                entity_type="job_invoice",
                entity_id="cross",
                idempotency_key="cross",
                useful_action_ids=[one["id"]],
            )

    def test_payment_money_is_deduplicated_and_never_claimed_without_evidence(self):
        observed = value_ledger.observe_payment_received(
            self.business["id"], invoice_id=4, payment_id=8, amount="25.00"
        )
        repeated = value_ledger.observe_payment_received(
            self.business["id"], invoice_id=4, payment_id=8, amount="25.00"
        )
        self.assertEqual(observed["id"], repeated["id"])
        self.assertEqual(observed["attribution_type"], "observed")
        self.assertEqual(float(observed["amount"]), 25.0)

    def test_trust_metrics_group_proposal_and_decision_by_correlation(self):
        fields = {
            "process_key": "collections",
            "action_family": "payment_reminder_sent",
            "correlation_key": "proposal:1",
            "trigger_source": "noesis_proposed",
        }
        db.record_assistant_action(
            self.business["id"], "payment_reminders", "Propuesta",
            status="proposed", **fields,
        )
        db.record_assistant_action(
            self.business["id"], "payment_reminders", "Aceptada",
            status="executed", **fields,
        )
        row = value_ledger.trust_metrics(self.business["id"])["rows"][0]
        self.assertEqual(row["offered"], 1)
        self.assertEqual(row["accepted"], 1)
        self.assertEqual(row["acceptance_rate"], 100.0)

    def test_feature_flag_and_fail_open_never_block_the_core_flow(self):
        client = db.add_client("Cliente", business_id=self.business["id"])
        config.VALUE_LEDGER_ENABLED = False
        job = db.add_job(client["id"], "Reparación", business_id=self.business["id"])
        self.assertIsNotNone(job)
        self.assertEqual(value_ledger.list_useful_actions(self.business["id"]), [])

        config.VALUE_LEDGER_ENABLED = True
        with patch.object(
            value_ledger, "record_useful_action", side_effect=RuntimeError("métrica")
        ):
            second = db.add_job(
                client["id"], "Segunda reparación", business_id=self.business["id"]
            )
        self.assertIsNotNone(second)
        self.assertIsNotNone(db.get_job(second["id"], self.business["id"]))

    def test_mature_business_flows_are_observed_after_success(self):
        db.update_fiscal(
            self.business["id"],
            nif="A12345678",
            address="Calle Principal 1",
        )
        client = db.add_client(
            "Cliente Fiscal",
            nif="B12345678",
            address="Calle Cliente 2",
            business_id=self.business["id"],
        )
        job = db.add_job(
            client["id"],
            "Texto operativo que no debe copiarse al ledger",
            price_estimate=100,
            business_id=self.business["id"],
        )
        completion = db.complete_job(job["id"], business_id=self.business["id"])
        invoice = db.issue_invoice(completion["invoice_id"], self.business["id"])
        payment = db.add_invoice_payment(
            invoice["id"], invoice["total"], business_id=self.business["id"]
        )

        families = {
            item["action_family"]
            for item in value_ledger.list_useful_actions(self.business["id"])
        }
        outcomes = value_ledger.list_useful_outcomes(self.business["id"])
        self.assertTrue({"job_created", "job_completed", "invoice_issued"} <= families)
        self.assertTrue(
            {"job_invoiced", "payment_received"}
            <= {item["outcome_family"] for item in outcomes}
        )
        self.assertEqual(
            next(item for item in outcomes if item["outcome_family"] == "payment_received")
            ["entity_id"],
            str(payment["id"]),
        )
        serialized = " ".join(
            str(item.get("metadata_json") or "")
            for item in value_ledger.list_useful_actions(self.business["id"])
        )
        self.assertNotIn("Texto operativo", serialized)

        quote = db.add_quote(
            client["id"], "Presupuesto", 50, business_id=self.business["id"]
        )
        db.mark_quote_sent(quote["id"], self.business["id"])
        db.accept_quote(quote["id"], self.business["id"])
        outcomes = value_ledger.list_useful_outcomes(self.business["id"])
        self.assertIn("quote_accepted", {item["outcome_family"] for item in outcomes})

    def test_outcome_read_or_write_failure_never_blocks_a_payment(self):
        db.update_fiscal(
            self.business["id"], nif="A12345678", address="Calle Principal 1"
        )
        client = db.add_client(
            "Cliente Fiscal", nif="B12345678", address="Calle Cliente 2",
            business_id=self.business["id"],
        )
        invoice = db.add_invoice(
            client["id"], "Servicio", 100, business_id=self.business["id"]
        )
        invoice = db.issue_invoice(invoice["id"], self.business["id"])
        with patch.object(
            value_ledger,
            "list_useful_actions",
            side_effect=RuntimeError("lectura de métrica"),
        ):
            payment = db.add_invoice_payment(
                invoice["id"], 50, business_id=self.business["id"]
            )
        self.assertEqual(payment["amount"], 50)
        self.assertEqual(db.invoice_paid_amount(invoice["id"], self.business["id"]), 50)

    def test_admin_audit_is_disabled_by_default_and_requires_admin(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        password = "password-segura-123"
        admin = db.create_user(
            "admin-value@example.com",
            auth.hash_password(password),
            self.business["id"],
        )
        normal = db.create_user(
            "normal-value@example.com",
            auth.hash_password(password),
            self.other["id"],
        )
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET is_admin=TRUE WHERE id=?", (admin["id"],))

        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                client.post(
                    "/login", data={"email": normal["email"], "password": password}
                )
                self.assertEqual(client.get("/admin/value-ledger").status_code, 403)
            with TestClient(server.app) as client:
                client.post(
                    "/login", data={"email": admin["email"], "password": password}
                )
                self.assertEqual(client.get("/admin/value-ledger").status_code, 404)
                config.VALUE_LEDGER_ADMIN_ENABLED = True
                response = client.get(
                    f"/admin/value-ledger?business_id={self.business['id']}"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["business_id"], self.business["id"])

    def test_migration_has_safe_rollback_and_can_be_reapplied(self):
        self.assertEqual(migrations.current_version(), 53)
        self._action("job_created", 1)
        self.assertEqual(migrations.downgrade(52), 52)
        with db.get_conn() as conn:
            table = conn.execute(
                "SELECT 1 AS found FROM sqlite_master "
                "WHERE type='table' AND name='useful_actions'"
            ).fetchone()
        self.assertIsNone(table)
        self.assertEqual(migrations.upgrade(53), 53)
        self.assertEqual(value_ledger.list_useful_actions(self.business["id"]), [])

    def test_rgpd_export_and_account_deletion_include_the_value_ledger(self):
        action = self._action("job_created", 1)
        value_ledger.record_useful_outcome(
            self.business["id"],
            "job_invoiced",
            attribution_type="assisted",
            attribution_method="test_v1",
            entity_type="job_invoice",
            entity_id="1:2",
            idempotency_key="rgpd:outcome",
            useful_action_ids=[action["id"]],
        )
        exported = db.export_business_data(self.business["id"])
        self.assertEqual(len(exported["useful_actions"]), 1)
        self.assertEqual(len(exported["useful_outcomes"]), 1)
        self.assertEqual(len(exported["useful_action_outcomes"]), 1)

        self.assertTrue(db.delete_business_cascade(self.business["id"]))
        with db.get_conn() as conn:
            for table in (
                "useful_actions", "useful_action_events", "useful_outcomes",
                "useful_action_outcomes",
            ):
                self.assertEqual(
                    conn.execute(
                        f"SELECT COUNT(*) AS n FROM {table} WHERE business_id=?",
                        (self.business["id"],),
                    ).fetchone()["n"],
                    0,
                )


if __name__ == "__main__":
    unittest.main()
