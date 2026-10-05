"""Contrato E y carreras de procesos PostgreSQL16 descartable."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

from noesis import config, db
from tests.financial_history_reconciliation_contract import HistoryReconciliationContract
from tests import postgres_financial_history_import as import_pg
from tests import postgres_financial_operations as operations_pg


class HistoryReconciliationPostgres(HistoryReconciliationContract,unittest.TestCase):
    setUpClass = classmethod(operations_pg.FinancialOperationsPostgres.setUpClass.__func__)
    tearDownClass = classmethod(operations_pg.FinancialOperationsPostgres.tearDownClass.__func__)
    _waiting = import_pg.HistoryImportPostgres._waiting
    clean_child = staticmethod(import_pg.HistoryImportPostgres.clean_child)
    result = import_pg.HistoryImportPostgres.result
    unlock = import_pg.HistoryImportPostgres.unlock

    def setUp(self):
        self.setup_reconciliation()

    def child(self,mode,**extra):
        args = dict(mode=mode,business_id=self.bid,user_id=self.principal.user_id,
                    batch_uuid=self.batch_uuid,epoch_uuid=self.epoch_uuid,manifest_uuid=str(self.manifest["manifest_uuid"]),
                    reconciliation_uuid=str(uuid4()))
        args.update(extra)
        environment = dict(os.environ,DATABASE_URL=config.DATABASE_URL,NOESIS_DATABASE_URL=config.DATABASE_URL,
                           NOESIS_FINANCIAL_CORE_ENABLED="false",NOESIS_VERIFACTU_CERT_PATH="",NOESIS_VERIFACTU_KEY_PATH="")
        process = subprocess.Popen([sys.executable,"-m","tests.financial_history_reconciliation_worker",json.dumps(args)],
            cwd=Path(__file__).parents[1],env=environment,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.clean_child,process)
        self.assertEqual(json.loads(process.stdout.readline()),"READY")
        process.stdin.write("go\n")
        process.stdin.flush()
        self.assertEqual(json.loads(process.stdout.readline()),"STARTING")
        return process

    def test_process_same_uuid_and_two_uuids_same_batch(self):
        self.scenario()
        for same in (True,False):
            uid = str(uuid4())
            first = self.child("reconcile",hold=True,reconciliation_uuid=uid)
            self.assertEqual(json.loads(first.stdout.readline()),"LOCKED")
            second = self.child("reconcile",reconciliation_uuid=uid if same else str(uuid4()))
            self._waiting(1,"advisory")
            self.unlock(first)
            one,two = self.result(first),self.result(second)
            self.assertEqual(one["result"],"PASS")
            self.assertEqual(one["result_hash"],two["result_hash"])
            self.assertEqual(one["reconciliation_uuid"]==two["reconciliation_uuid"],same)

    def test_process_release_and_invalidate_serialize_without_deadlock(self):
        for mode in ("release","invalidate"):
            self.setup_reconciliation()
            self.scenario()
            first = self.child("reconcile",hold=True)
            self.assertEqual(json.loads(first.stdout.readline()),"LOCKED")
            transition = self.child(mode)
            self._waiting(1,"advisory")
            self.unlock(first)
            self.assertEqual(self.result(first)["result"],"PASS")
            self.assertEqual(self.result(transition)["state"],"released" if mode=="release" else "invalidated")
            self.assertEqual(self.result(self.child("reconcile"))["error"],"EpochUnavailable")

    def test_process_live_writer_and_terminal_import_rejected(self):
        self.scenario()
        before = self.snapshot()
        first = self.child("reconcile",hold=True)
        self.assertEqual(json.loads(first.stdout.readline()),"LOCKED")
        live = self.child("live")
        with db.get_conn() as conn:
            item_uuid = str(conn.execute("SELECT item_uuid FROM financial_history_import_items WHERE business_id=? AND batch_uuid=? AND state='recorded' LIMIT 1",(self.bid,self.batch_uuid)).fetchone()["item_uuid"])
        imported = self.child("import",item_uuid=item_uuid)
        self._waiting(2,"advisory")
        self.unlock(first)
        self.assertEqual(self.result(first)["result"],"PASS")
        self.assertEqual(self.result(live)["error"],"HistoricalFenceActive")
        self.assertEqual(self.result(imported)["state"],"recorded")
        self.assertEqual(before,self.snapshot())
        # Otro batch prepared demuestra que E no se inicia durante un import.
        self.batch_uuid = str(uuid4())
        self.importer.prepare(self.principal,self.manifest["manifest_uuid"],self.batch_uuid)
        self.assertEqual(self.result(self.child("reconcile"))["error"],"StateError")

    def test_process_crash_rolls_back_only_e_then_retry(self):
        self.scenario()
        before = self.snapshot()
        uid = str(uuid4())
        first = self.child("reconcile",hold=True,reconciliation_uuid=uid)
        self.assertEqual(json.loads(first.stdout.readline()),"LOCKED")
        first.stdin.write("crash\n")
        first.stdin.flush()
        _,error = first.communicate(timeout=30)
        self.assertEqual(first.returncode,73,error)
        with db.get_conn() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM financial_history_reconciliations WHERE business_id=?",(self.bid,)).fetchone())
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.reconcile(uid)["result"],"PASS")

    def test_process_other_business_progresses_while_first_held(self):
        self.scenario()
        original = (self.bid,self.principal,self.importer,self.reconciler,self.manifest,self.epoch_uuid,self.batch_uuid)
        self.setup_reconciliation()
        self.scenario()
        other = (self.bid,self.principal,self.importer,self.reconciler,self.manifest,self.epoch_uuid,self.batch_uuid)
        self.bid,self.principal,self.importer,self.reconciler,self.manifest,self.epoch_uuid,self.batch_uuid = original
        first = self.child("reconcile",hold=True)
        self.assertEqual(json.loads(first.stdout.readline()),"LOCKED")
        self.bid,self.principal,self.importer,self.reconciler,self.manifest,self.epoch_uuid,self.batch_uuid = other
        second = self.child("reconcile")
        self.assertEqual(self.result(second)["result"],"PASS")
        self.unlock(first)
        self.assertEqual(self.result(first)["result"],"PASS")


if __name__ == "__main__":
    unittest.main()
