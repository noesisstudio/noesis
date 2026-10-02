"""Contratos + concurrencia de conexiones/procesos + crash real en PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.parse import quote, urlsplit
from uuid import uuid4

from noesis import config, db, migrations
from tests.financial_operations_contract import OperationsContract


class FinancialOperationsPostgres(OperationsContract, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = urlsplit(config.DATABASE_URL)
        if url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.path != "/noesis_ci" or config.IS_PRODUCTION:
            raise RuntimeError("Solo PostgreSQL local descartable /noesis_ci.")
        cls.original_url = config.DATABASE_URL
        cls.schema = "phase12_" + uuid4().hex
        with db.get_conn() as conn:
            conn.execute(f"CREATE SCHEMA {cls.schema}")
        separator = "&" if "?" in cls.original_url else "?"
        cls.scoped_url = cls.original_url + separator + "options=" + quote("-csearch_path=" + cls.schema)
        cls.settings = patch.object(config, "DATABASE_URL", cls.scoped_url)
        cls.settings.start()
        migrations.upgrade()

    @classmethod
    def tearDownClass(cls):
        db.close_pool()
        cls.settings.stop()
        with db.get_conn() as conn:
            conn.execute(f"DROP SCHEMA {cls.schema} CASCADE")
        db.close_pool()

    def setUp(self):
        self.seed()

    def workers(self, arguments):
        environment = dict(os.environ, NOESIS_DATABASE_URL=self.scoped_url, DATABASE_URL=self.scoped_url)
        children = [subprocess.Popen([sys.executable, "-m", "tests.financial_operations_worker", json.dumps(arg)],
            cwd=Path(__file__).parents[1], env=environment, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for arg in arguments]
        try:
            for child in children:
                self.assertEqual(child.stdout.readline().strip(), "READY")
            # Ambos procesos ya están listos; la carrera usa conexiones independientes.
            for child in children:
                child.stdin.write("go\n")
                child.stdin.flush()
            results = []
            for child in children:
                output, error = child.communicate(timeout=30)
                results.append((child.returncode, None if not output.strip() else json.loads(output.strip()), error))
            return results
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    def worker_args(self, mode, **kwargs):
        return dict(mode=mode, business_id=self.business["id"], user_id=self.user["id"], **kwargs)

    def test_two_connections_execute_once(self):
        op = self.approved()
        ready = threading.Barrier(2)
        def worker():
            ready.wait(timeout=10)
            return self.service.execute(self.principal, op.operation_uuid, self.effect)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: worker(), range(2)))
        self.assertEqual(results[0].result, results[1].result)
        self.assertEqual(self.count_effects(), 1)

    def test_two_processes_reserve_same_content_or_conflict_atomically(self):
        for conflict in (False, True):
            entry_uuid = str(uuid4())
            first = self.worker_args("prepare", entry_uuid=entry_uuid, request=self.request.canonical())
            second = dict(first, request=replace(self.request, amount="11").canonical()) if conflict else dict(first)
            results = self.workers([first, second])
            for code, _, error in results:
                self.assertEqual(code, 0, error)
            data = [item[1] for item in results]
            if conflict:
                self.assertEqual(sum(bool(item.get("conflict")) for item in data), 1)
            else:
                self.assertEqual(data[0]["operation_uuid"], data[1]["operation_uuid"])
            with db.get_conn() as conn:
                count = conn.execute("SELECT COUNT(*) AS n FROM financial_operations WHERE business_id=?",
                                     (self.business["id"],)).fetchone()["n"]
            self.assertEqual(count, 2 if conflict else 1)

    def test_two_processes_execute_once(self):
        op = self.approved()
        args = self.worker_args("execute", operation_uuid=op.operation_uuid)
        results = self.workers([args, args])
        for code, _, error in results:
            self.assertEqual(code, 0, error)
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(self.count_effects(), 1)

    def test_process_crash_rolls_back_effect_and_never_marks_committed(self):
        op = self.approved()
        result = self.workers([self.worker_args("crash", operation_uuid=op.operation_uuid)])[0]
        self.assertEqual(result[0], 17)
        self.assertEqual(self.count_effects(), 0)
        self.assertEqual(self.service.recover(self.principal, op.operation_uuid).state.value, "approved")
        retry = self.service.execute(self.principal, op.operation_uuid, self.effect)
        self.assertEqual(retry.state.value, "committed")
        self.assertEqual(self.count_effects(), 1)


if __name__ == "__main__":
    unittest.main()
