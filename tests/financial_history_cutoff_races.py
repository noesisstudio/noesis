"""Mismas barreras de procesos SQLite/PG; locks observados en PG real."""

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from uuid import uuid4

from noesis import config, db
from noesis.core.locks import lock_business
from noesis.financial_history.fence import HistoricalWriterBusy


class CutoffProcessRaces:
    def child(self, mode, **extra):
        environment = dict(
            os.environ,
            DATABASE_URL=config.DATABASE_URL,
            NOESIS_DB_PATH=str(config.DB_PATH),
            NOESIS_FINANCIAL_CORE_ENABLED="false",
            NOESIS_VERIFACTU_CERT_PATH="",
            NOESIS_VERIFACTU_KEY_PATH="",
        )
        args = dict(mode=mode, business_id=self.bid, user_id=self.user["id"], **extra)
        process = subprocess.Popen(
            [sys.executable, "-m", "tests.financial_history_cutoff_worker", json.dumps(args)],
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

    def test_process_writer_before_t0_commit_and_rollback(self):
        for rollback in (False, True):
            with self.subTest(rollback=rollback):
                writer = self.child("hold")
                self.assertEqual(json.loads(writer.stdout.readline()), "LOCKED")
                epoch_uuid = str(uuid4())
                opener = self.child("open", epoch_uuid=epoch_uuid)
                self.assertEqual(json.loads(opener.stdout.readline()), "OPENING")
                if config.DATABASE_URL:
                    deadline = time.monotonic() + 10
                    waited = False
                    while time.monotonic() < deadline:
                        with db.get_conn() as conn:
                            waited = bool(
                                conn.execute(
                                    "SELECT 1 FROM pg_locks WHERE locktype='advisory' AND NOT granted"
                                ).fetchone()
                            )
                        if waited:
                            break
                        threading.Event().wait(0.01)
                    self.assertTrue(waited, "Se requiere evidencia del wait advisory real.")
                self.assertIsNone(opener.poll())
                writer.stdin.write(("rollback" if rollback else "commit") + "\n")
                writer.stdin.flush()
                completed = self.result(writer)
                epoch = self.result(opener)
                self.assertEqual(epoch["result"], "opened")
                self.assertGreaterEqual(
                    datetime.fromisoformat(epoch["t0"]),
                    datetime.fromisoformat(completed["before_commit"]),
                )
                with db.get_conn() as conn:
                    count = conn.execute(
                        "SELECT COUNT(*) AS n FROM expenses WHERE business_id=? AND concept='fixture process'",
                        (self.bid,),
                    ).fetchone()["n"]
                self.assertEqual(count, 1)  # Primera iteración commit; segunda rollback.
                self.cut.release(self.principal, epoch_uuid, reason="test_end")

    def test_two_processes_open_one_winner_no_implicit_retry_epoch(self):
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            lock_business(conn, self.bid)
            children = [self.child("open", epoch_uuid=str(uuid4())) for _ in range(2)]
            for child in children:
                self.assertEqual(json.loads(child.stdout.readline()), "OPENING")
                self.assertIsNone(child.poll())
            if config.DATABASE_URL:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    with db.get_conn() as observer:
                        waiting = observer.execute(
                            "SELECT COUNT(*) AS n FROM pg_locks WHERE locktype='advisory' AND NOT granted"
                        ).fetchone()["n"]
                    if waiting == 2:
                        break
                    threading.Event().wait(0.01)
                self.assertEqual(waiting, 2)
        results = [self.result(child) for child in children]
        self.assertEqual(sum(r.get("result") == "opened" for r in results), 1)
        self.assertEqual(sum(r.get("error") == "ConflictError" for r in results), 1)

    def test_process_epoch_first_legacy_direct_sql_and_ee(self):
        _, original = self.prepared_captures()
        before = self.unchanged()
        self.open()
        for mode, args in [
            ("legacy", {}),
            ("sql", {}),
            ("ee", {"event_uuid": original.result["event_uuid"]}),
        ]:
            with self.subTest(mode=mode):
                self.assertEqual(
                    self.result(self.child(mode, **args)).get("error"), "HistoricalFenceActive"
                )
                self.assertEqual(self.unchanged(), before)

    def test_process_epoch_first_all_five_capture_services(self):
        operations, _ = self.prepared_captures()
        before = self.unchanged()
        self.open()
        for capture, operation in operations:
            with self.subTest(capture=type(capture).__name__):
                result = self.result(
                    self.child(
                        "capture",
                        capture=type(capture).__name__,
                        operation_uuid=str(operation.operation_uuid),
                    )
                )
                self.assertEqual(result.get("error"), "HistoricalFenceActive")
                self.assertEqual(self.unchanged(), before)

    def test_pg_direct_sql_busy_fails_closed_no_gate_inversion(self):
        if not config.DATABASE_URL:
            self.skipTest("PG gate try-lock; SQLite BEGIN IMMEDIATE probado en carrera común.")
        writer = self.child("hold")
        self.assertEqual(json.loads(writer.stdout.readline()), "LOCKED")
        # SQL directo no espera gate después de row lock: conflicto retry explícito.
        with self.assertRaises(HistoricalWriterBusy), db.get_conn() as conn:
            conn.execute(
                "INSERT INTO expenses (business_id,concept,amount,spent_on,created_at) VALUES (?,'other',1,'2026-10-04','2026-10-04')",
                (self.bid,),
            )
        writer.stdin.write("rollback\n")
        writer.stdin.flush()
        self.result(writer)

    def test_pg_repeatable_snapshot_direct_sql_rejected(self):
        if not config.DATABASE_URL:
            self.skipTest("Aislamiento PostgreSQL.")
        with self.assertRaises(HistoricalWriterBusy), db.get_conn() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            conn.execute(
                "INSERT INTO expenses (business_id,concept,amount,spent_on,created_at) VALUES (?,'other',1,'2026-10-04','2026-10-04')",
                (self.bid,),
            )
