"""Epoch/T0/fence real; PostgreSQL16 localhost descartable /noesis_ci."""

import unittest
from contextlib import contextmanager
from datetime import datetime
import json
import threading
import time
from uuid import uuid4

from noesis import db
from noesis.core.locks import lock_business, lock_key
from noesis.financial_operations.contracts import AccessDenied
from noesis.schema_lineage import require_runtime, SchemaLineageError

from tests.financial_history_cutoff_contract import HistoryCutoffContract
from tests.financial_history_cutoff_races import CutoffProcessRaces
from tests.postgres_financial_operations import FinancialOperationsPostgres


class HistoryCutoffPostgres(HistoryCutoffContract, CutoffProcessRaces, unittest.TestCase):
    setUpClass = classmethod(FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(FinancialOperationsPostgres.tearDownClass.__func__)

    def setUp(self):
        self.setup_cut()

    def _waiting(self, expected, kind, key=None):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with db.get_conn() as observer:
                if kind == "advisory":
                    key = (lock_key("financial-writer", self.bid) if key is None else key) & (
                        (1 << 64) - 1
                    )
                    count = observer.execute(
                        "SELECT COUNT(*) AS n FROM pg_locks WHERE locktype=? AND NOT granted AND classid::bigint=? AND objid::bigint=?",
                        (kind, key >> 32, key & 0xFFFFFFFF),
                    ).fetchone()["n"]
                else:
                    count = observer.execute(
                        "SELECT COUNT(*) AS n FROM pg_locks WHERE locktype=? AND NOT granted",
                        (kind,),
                    ).fetchone()["n"]
            if count >= expected:
                return
            threading.Event().wait(0.01)
        self.fail("No se observó contención real del lock esperado.")

    def test_open_release_process_race_only_one_boundary_current(self):
        self.open()
        with db.get_conn() as conn:
            lock_business(conn, self.bid)
            releaser = self.child("release", epoch_uuid=self.epoch_uuid)
            self.assertEqual(json.loads(releaser.stdout.readline()), "RELEASING")
            self._waiting(1, "advisory")
            opener = self.child("open", epoch_uuid=str(uuid4()))
            self.assertEqual(json.loads(opener.stdout.readline()), "OPENING")
            self._waiting(2, "advisory")
        released, new = self.result(releaser), self.result(opener)
        self.assertEqual(released["result"], "released")
        self.assertEqual(new["result"], "opened")
        self.assertEqual(new["generation"], 2)
        with db.get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM financial_history_epochs WHERE business_id=? AND state<>'released'",
                (self.bid,),
            ).fetchone()["n"]
        self.assertEqual(count, 1)

    def test_permission_revocation_serializes_with_session_check(self):
        with self.cut._session(self.principal):
            child = self.child("revoke")
            self.assertEqual(json.loads(child.stdout.readline()), "REVOKING")
            self._waiting(1, "transactionid")
        self.assertEqual(self.result(child)["result"], "revoked")
        with self.assertRaises(AccessDenied):
            self.open()
        with db.get_conn() as conn:
            self.assertFalse(
                conn.execute(
                    "SELECT 1 FROM financial_history_epochs WHERE business_id=?", (self.bid,)
                ).fetchone()
            )

    def test_waiting_services_do_not_lock_business_before_gate(self):
        # El dueño del gate debe poder actualizar negocio/revocar antes del waiter.
        for mode in ("open", "operations", "ee_gate"):
            with self.subTest(mode=mode):
                with db.get_conn() as conn:
                    lock_business(conn, self.bid)
                    child = self.child(mode, epoch_uuid=self.epoch_uuid, operation_uuid=str(uuid4()))
                    if mode == "open":
                        self.assertEqual(json.loads(child.stdout.readline()), "OPENING")
                    self._waiting(1, "advisory")
                    conn.execute("SET LOCAL lock_timeout='1s'")
                    conn.execute("UPDATE businesses SET name='Fixture gate' WHERE id=?", (self.bid,))
                    conn.execute("UPDATE users SET session_version=session_version+1 WHERE business_id=? AND id=?",
                                 (self.bid, self.user["id"]))
                self.assertEqual(self.result(child)["error"], "AccessDenied")
                with db.get_conn() as conn:
                    conn.execute("UPDATE users SET session_version=0 WHERE business_id=? AND id=?",
                                 (self.bid, self.user["id"]))

    def test_sql_statement_snapshot_before_open_observes_fence_after_commit(self):
        # La expresión VOLATILE se evalúa dentro del INSERT antes del guard C.
        # No cambia ningún objeto owned; query_start y lock observan la barrera.
        key = lock_key("cutoff-test-pause", uuid4())
        with self._pause_function(key):
            with db.get_conn() as pause:
                pause.execute("SELECT pg_advisory_xact_lock(?)", (key,))
                writer = self.child("sql_paused")
                self._waiting(1, "advisory", key)
                with db.get_conn() as observer:
                    require_runtime(observer)
                    statement = observer.execute(
                        "SELECT query_start FROM pg_stat_activity WHERE query LIKE ? "
                        "AND query LIKE ? AND wait_event_type='Lock'",
                        ("INSERT INTO expenses%", "%qa_cut_pause()%"),
                    ).fetchone()
                    self.assertIsNotNone(statement)
                epoch = self.open()
                self.assertLess(datetime.fromisoformat(str(statement['query_start'])),
                                datetime.fromisoformat(str(epoch['t0']).replace('Z', '+00:00')))
            result = self.result(writer)
            self.assertEqual(result["error"], "HistoricalFenceActive")
            with db.get_conn() as conn:
                self.assertFalse(conn.execute(
                    "SELECT 1 FROM expenses WHERE business_id=? AND concept='SQL fixture'",
                    (self.bid,),
                ).fetchone())

    @contextmanager
    def _pause_function(self, key):
        with db.get_conn() as conn:
            conn.execute(
                f"CREATE FUNCTION qa_cut_pause() RETURNS text VOLATILE LANGUAGE plpgsql AS $$ "
                f"BEGIN PERFORM pg_advisory_xact_lock({key}); RETURN 'SQL fixture'; END $$"
            )
        try:
            yield
        finally:
            with db.get_conn() as conn:
                conn.execute("DROP FUNCTION qa_cut_pause()")

    def test_pause_function_cleanup_even_when_assertion_fails(self):
        with self.assertRaisesRegex(AssertionError, 'synthetic assertion'):
            with self._pause_function(lock_key('cleanup', uuid4())):
                self.fail('synthetic assertion')
        with db.get_conn() as conn:
            require_runtime(conn)
            self.assertIsNone(conn.execute("SELECT to_regprocedure('qa_cut_pause()') AS f").fetchone()['f'])

    def test_extra_trigger_on_owned_expenses_rejected_and_cleaned(self):
        with db.get_conn() as conn:
            conn.execute("CREATE FUNCTION qa_owned_probe() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$")
        try:
            with db.get_conn() as conn:
                conn.execute("CREATE TRIGGER qa_owned_probe BEFORE INSERT ON expenses FOR EACH ROW EXECUTE FUNCTION qa_owned_probe()")
            with db.get_conn() as conn, self.assertRaisesRegex(SchemaLineageError, 'SCHEMA_OBJECT_MISMATCH'):
                require_runtime(conn)
        finally:
            with db.get_conn() as conn:
                conn.execute("DROP TRIGGER IF EXISTS qa_owned_probe ON expenses")
                conn.execute("DROP FUNCTION qa_owned_probe()")
        with db.get_conn() as conn:
            self.assertEqual(require_runtime(conn).schema_version, 75)


if __name__ == "__main__":
    unittest.main()
