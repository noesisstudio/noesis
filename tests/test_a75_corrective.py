"""Regresiones del correctivo A75; fixtures y metadatos, sin datos reales."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db
from noesis.financial_history.readers import RawReader
from scripts.check_secrets import scan
from scripts.run_postgres_backup_lab import run_stage
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
        before = json.loads(subprocess.check_output(['git', 'show', 'b3a93361975693a157cf3874346dcfa456ce7162:.secrets.baseline']))  # pragma: allowlist secret; public corrective parent
        after = json.loads(Path('.secrets.baseline').read_text(encoding='utf-8'))
        self.assertEqual({k:v for k,v in before.items() if k!='results'},
                         {k:v for k,v in after.items() if k!='results'})
        filename = 'docs/project-state.json'
        for name in set(before['results'])|set(after['results']):
            old, new = before['results'].get(name, []), after['results'].get(name, [])
            self.assertEqual(old, new[:-1] if name==filename else new)
        added = after['results'][filename][-1]
        fingerprint = json.loads(Path(filename).read_text(encoding='utf-8'))['schema_lineage_a75_candidate']['failed_candidate_sha']
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

    def test_utf8_json_detected_with_utf8_mode_enabled_or_disabled(self):
        baseline = json.loads(Path('.secrets.baseline').read_text(encoding='utf-8'))
        scanner = Path('scripts/check_secrets.py').resolve()
        unknown = hashlib.sha256(uuid4().bytes).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(['git', 'init', '-q', str(root)], check=True, capture_output=True)
            (root/'.secrets.baseline').write_text(json.dumps(baseline), encoding='utf-8')
            (root/'unicode.json').write_text(json.dumps({'text':'revisión é € \u008d', 'api_secret':unknown}, ensure_ascii=False), encoding='utf-8')
            subprocess.run(['git', '-C', str(root), 'add', 'unicode.json'], check=True, capture_output=True)
            outputs = []
            for mode in ('0', '1'):
                env = {**os.environ, 'PYTHONUTF8':mode}
                result = subprocess.run([sys.executable, '-X', 'utf8='+mode, str(scanner)],
                                        cwd=root, env=env, capture_output=True)
                self.assertEqual(result.returncode, 1, result.stderr.decode('utf-8', errors='replace'))
                self.assertIn(b'Hex High Entropy String', result.stdout)
                self.assertNotIn(unknown.encode(), result.stdout + result.stderr)
                outputs.append(result.stdout)
            self.assertEqual(outputs[0], outputs[1])


class CorrectiveHarnessTests(unittest.TestCase):
    def test_each_smoke_stage_prepares_and_validates_canonical75_independently(self):
        for name in ('HTTP + backup + restore', 'privacy + rollback'):
            with self.subTest(stage=name):
                ok = subprocess.CompletedProcess([], 0, b'', b'')
                with patch('scripts.run_postgres_backup_lab.invoke', return_value=ok) as invoke:
                    result, precondition = run_stage(name, ['stage-contract'], {})
                commands = [call.args[0] for call in invoke.call_args_list]
                expected = [['-m', 'noesis.migrations', 'upgrade'],
                            ['-m', 'tests.postgres_canonical75_precondition']]
                if name == 'privacy + rollback':
                    expected.append(['tests/postgres_smoke.py'])
                self.assertEqual(commands, [*expected, ['stage-contract']])
                self.assertEqual((result.returncode, precondition), (0, 0))

    def test_failed_upgrade_or_identity_check_never_launches_smoke_or_contract(self):
        for name in ('HTTP + backup + restore', 'privacy + rollback'):
            for failed_step in (0, 1):
                with self.subTest(stage=name, failed_step=failed_step):
                    results = [subprocess.CompletedProcess([], 0, b'', b'')]*failed_step
                    results.append(subprocess.CompletedProcess([], 7, b'', b''))
                    with patch('scripts.run_postgres_backup_lab.invoke', side_effect=results) as invoke:
                        result, precondition = run_stage(name, ['must-not-run'], {})
                    self.assertEqual(invoke.call_count, failed_step + 1)
                    self.assertEqual((result.returncode, precondition), (7, 7))
