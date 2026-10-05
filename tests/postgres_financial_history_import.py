"""Importer1.9D contra PostgreSQL local descartable /noesis_ci."""

import unittest
import json
import os
from pathlib import Path
import subprocess
import sys

from tests.financial_history_import_contract import HistoryImportContract
from tests import postgres_financial_operations as operations_pg
from tests import postgres_financial_history_cutoff as cutoff_pg
from noesis import config, db


class HistoryImportPostgres(HistoryImportContract, unittest.TestCase):
    setUpClass = classmethod(operations_pg.FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(operations_pg.FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.setup_import()

    _waiting = cutoff_pg.HistoryCutoffPostgres._waiting

    def child(self, mode, **extra):
        args = dict(
            mode=mode,
            business_id=self.bid,
            user_id=self.principal.user_id,
            batch_uuid=self.batch_uuid,
            epoch_uuid=self.epoch_uuid,
            **extra,
        )
        environment = dict(
            os.environ,
            DATABASE_URL=config.DATABASE_URL,
            NOESIS_DATABASE_URL=config.DATABASE_URL,
            NOESIS_FINANCIAL_CORE_ENABLED="false",
            NOESIS_VERIFACTU_CERT_PATH="",
            NOESIS_VERIFACTU_KEY_PATH="",
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "tests.financial_history_import_worker", json.dumps(args)],
            cwd=Path(__file__).parents[1],
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.clean_child, process)
        self.assertEqual(json.loads(process.stdout.readline()), "READY")
        process.stdin.write("go\n")
        process.stdin.flush()
        self.assertEqual(json.loads(process.stdout.readline()), "STARTING")
        return process

    @staticmethod
    def clean_child(process):
        if process.poll() is None:
            process.kill()
        process.communicate()

    def result(self, process):
        output, error = process.communicate(timeout=30)
        self.assertEqual(process.returncode, 0, error)
        return json.loads(output.strip().splitlines()[-1])

    def unlock(self, process):
        process.stdin.write("commit\n")
        process.stdin.flush()

    def test_process_same_item_same_and_different_retry_no_duplicate(self):
        self.sources()
        rows = self.frozen()
        uid = str(rows[0]["item_uuid"])
        first = self.child("import", item_uuid=uid, hold=True)
        self.assertEqual(json.loads(first.stdout.readline()), "LOCKED")
        second = self.child("import", item_uuid=uid)
        self._waiting(1, "advisory")
        self.unlock(first)
        one, two = self.result(first), self.result(second)
        self.assertEqual(one, two)
        with db.get_conn() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM economic_events WHERE business_id=?", (self.bid,)
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT last_sequence FROM economic_event_sequences WHERE business_id=?",
                    (self.bid,),
                ).fetchone()["last_sequence"],
                1,
            )

    def test_process_two_items_same_business_monotonic_sequence(self):
        self.sources()
        rows = self.frozen()
        first = self.child("import", item_uuid=str(rows[0]["item_uuid"]), hold=True)
        self.assertEqual(json.loads(first.stdout.readline()), "LOCKED")
        second = self.child("import", item_uuid=str(rows[1]["item_uuid"]))
        self._waiting(1, "advisory")
        self.unlock(first)
        self.assertEqual(self.result(first)["state"], "recorded")
        self.assertEqual(self.result(second)["state"], "recorded")
        with db.get_conn() as conn:
            self.assertEqual(
                [
                    r["business_sequence"]
                    for r in conn.execute(
                        "SELECT business_sequence FROM economic_events WHERE business_id=? ORDER BY business_sequence",
                        (self.bid,),
                    ).fetchall()
                ],
                [1, 2],
            )

    def test_process_import_vs_release_and_invalidate_serialized(self):
        from noesis.financial_history.cutoff import EpochUnavailable

        for mode in ("release", "invalidate"):
            if hasattr(self, "manifest"):
                self.setup_import()
            self.sources()
            rows = self.frozen()
            first = self.child("import", item_uuid=str(rows[0]["item_uuid"]), hold=True)
            self.assertEqual(json.loads(first.stdout.readline()), "LOCKED")
            transition = self.child(mode)
            self._waiting(1, "advisory")
            self.unlock(first)
            self.assertEqual(self.result(first)["state"], "recorded")
            self.assertEqual(
                self.result(transition)["state"], "released" if mode == "release" else "invalidated"
            )
            with self.assertRaises(EpochUnavailable):
                self.importer.record_item(self.principal, self.batch_uuid, rows[1]["item_uuid"])

    def test_process_import_vs_live_writer_and_direct_sql_no_live_write(self):
        self.sources()
        row = self.frozen()[0]
        before = self.legacy_snapshot()
        first = self.child("import", item_uuid=str(row["item_uuid"]), hold=True)
        self.assertEqual(json.loads(first.stdout.readline()), "LOCKED")
        sql = self.child("sql")
        self.assertEqual(self.result(sql)["error"], "HistoricalWriterBusy")
        live = self.child("live")
        self._waiting(1, "advisory")
        self.unlock(first)
        self.assertEqual(self.result(first)["state"], "recorded")
        self.assertEqual(self.result(live)["error"], "HistoricalFenceActive")
        self.assertEqual(before, self.legacy_snapshot())

    def test_process_real_crash_rolls_back_then_retry(self):
        self.sources()
        row = self.frozen()[0]
        child = self.child("import", item_uuid=str(row["item_uuid"]), hold=True, stage="result")
        self.assertEqual(json.loads(child.stdout.readline()), "LOCKED")
        child.stdin.write("crash\n")
        child.stdin.flush()
        _, error = child.communicate(timeout=30)
        self.assertEqual(child.returncode, 73, error)
        with db.get_conn() as conn:
            for table in (
                "financial_history_import_items",
                "financial_operations",
                "financial_authorizations",
                "economic_events",
            ):
                self.assertFalse(
                    conn.execute(
                        f"SELECT 1 FROM {table} WHERE business_id=?", (self.bid,)
                    ).fetchone()
                )
        self.assertTrue(self.importer.read(self.principal, self.epoch_uuid)["fence_enabled"])
        self.assertEqual(
            self.importer.record_item(self.principal, self.batch_uuid, row["item_uuid"])["state"],
            "recorded",
        )

    def test_process_different_businesses_do_not_share_gate(self):
        self.sources()
        rows = self.frozen()
        original = (
            self.bid,
            self.principal,
            self.importer,
            self.manifest,
            self.epoch_uuid,
            self.batch_uuid,
        )
        self.setup_import()
        self.sources()
        other_rows = self.frozen()
        other = (
            self.bid,
            self.principal,
            self.importer,
            self.manifest,
            self.epoch_uuid,
            self.batch_uuid,
        )
        self.bid, self.principal, self.importer, self.manifest, self.epoch_uuid, self.batch_uuid = (
            original
        )
        first = self.child("import", item_uuid=str(rows[0]["item_uuid"]), hold=True)
        self.assertEqual(json.loads(first.stdout.readline()), "LOCKED")
        self.bid, self.principal, self.importer, self.manifest, self.epoch_uuid, self.batch_uuid = (
            other
        )
        second = self.child("import", item_uuid=str(other_rows[0]["item_uuid"]))
        self.assertEqual(self.result(second)["state"], "recorded")
        self.unlock(first)
        self.assertEqual(self.result(first)["state"], "recorded")


if __name__ == "__main__":
    unittest.main()
