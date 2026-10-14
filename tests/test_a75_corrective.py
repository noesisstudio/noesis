"""Regresiones del correctivo A75; fixtures y metadatos, sin datos reales."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db
from noesis.financial_history.readers import RawReader
from scripts.check_secrets import scan
from tests import test_public_marketing as marketing
from tests import test_seo as seo
from tests import test_financial_history_inventory as inventory


class CorrectiveFixtureTests(unittest.TestCase):
    def test_public_marketing_failed_enter_releases_patches_and_directory(self):
        before = (config.DB_PATH, config.DATABASE_URL, config.SEED_DEMO, config.RESET_DB,
                  marketing.server.start_scheduler)
        case = marketing.PublicMarketingTests('test_all_ctas_respect_closed_signup')
        try:
            with patch.object(marketing.TestClient, '__enter__', side_effect=RuntimeError('synthetic enter failure')):
                with self.assertRaisesRegex(RuntimeError, 'synthetic enter failure'):
                    case.setUp()
        finally:
            case.doCleanups()
        self.assertFalse(Path(case.temp.name).exists())
        self.assertEqual(before, (config.DB_PATH, config.DATABASE_URL, config.SEED_DEMO,
                                 config.RESET_DB, marketing.server.start_scheduler))

    def test_seo_failed_preparation_releases_patches_and_directory(self):
        before = (config.DB_PATH, config.DATABASE_URL, config.SEED_DEMO, config.RESET_DB)
        created = []
        def failure():
            created.append(config.DB_PATH.parent)
            raise RuntimeError('synthetic preparation failure')
        case = seo.SeoTestCase('test_robots_keeps_private_areas_out_of_search_engines')
        try:
            with patch.object(db, 'init_db', failure), self.assertRaisesRegex(RuntimeError, 'preparation failure'):
                case.setUp()
        finally:
            case.doCleanups()
        self.assertTrue(created)
        self.assertFalse(created[0].exists())
        self.assertEqual(before, (config.DB_PATH, config.DATABASE_URL, config.SEED_DEMO, config.RESET_DB))

    def test_repeated_commits_cannot_freeze_ready_on_unstable_sqlite_pages(self):
        case = inventory.HistoryInventorySQLite('test_drift_between_scan_and_freeze')
        case.setUp()
        self.addCleanup(case.doCleanups)
        draft = case.draft()
        original, writes = RawReader.page, []
        def page(reader, kind, after=None):
            if kind == 'invoice' and len(writes) < 2:
                with db.get_conn() as conn:
                    planning = conn.execute("SELECT 1 FROM financial_history_manifests WHERE business_id=? AND status='planning'", (case.bid,)).fetchone()
                if planning:
                    with db.get_conn() as conn:
                        conn.execute('UPDATE invoices SET concept=? WHERE business_id=? AND id=?',
                                     ('Commit '+str(len(writes)), case.bid, draft['id']))
                    writes.append(True)
            return original(reader, kind, after)
        with patch.object(RawReader, 'page', page):
            manifest = case.run_history()
        self.assertEqual(len(writes), 2)
        self.assertEqual(manifest['result'], 'BLOCKED')
        self.assertIn('SOURCE_DRIFT', case.codes(manifest))


class CorrectiveSecretTests(unittest.TestCase):
    def test_exact_single_public_exception_without_detector_or_filter_changes(self):
        before = json.loads(subprocess.check_output(['git', 'show', 'f5150b27076ab5725bae436fba781095a0a9c0ee:.secrets.baseline']))  # pragma: allowlist secret; public failed candidate
        after = json.loads(Path('.secrets.baseline').read_text(encoding='utf-8'))
        self.assertEqual({k:v for k,v in before.items() if k!='results'},
                         {k:v for k,v in after.items() if k!='results'})
        filename = 'docs/project-state.json'
        for name in set(before['results'])|set(after['results']):
            old, new = before['results'].get(name, []), after['results'].get(name, [])
            self.assertEqual(old, new[:-1] if name==filename else new)
        added = after['results'][filename][-1]
        fingerprint = json.loads(Path(filename).read_text(encoding='utf-8'))['schema_lineage_a75_candidate']['canonical75_fingerprint']
        self.assertEqual(added['filename'], filename)
        self.assertEqual(added['type'], 'Hex High Entropy String')
        self.assertEqual(added['hashed_secret'], hashlib.sha1(fingerprint.encode()).hexdigest())
        self.assertTrue(added['is_verified'])
        self.assertFalse(added['is_secret'])

    def test_new_temporary_hash_secret_still_detected(self):
        baseline = json.loads(Path('.secrets.baseline').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)/'negative-secret.json'
            unknown = hashlib.sha256(uuid4().bytes).hexdigest()
            target.write_text(json.dumps({'api_secret':unknown}), encoding='utf-8')
            findings = list(scan([str(target)], baseline))
            self.assertTrue(any(secret.secret_hash==hashlib.sha1(unknown.encode()).hexdigest()
                                for _,secret in findings))
