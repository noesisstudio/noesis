"""Regresiones portables de los guards; no sustituyen PostgreSQL sintético real."""

from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from noesis import config, schema_retention as retention


class _PathProbe:
    """Paths reales del fixture; sólo metadata POSIX y /proc simulados en Windows."""

    def __init__(self, value, fixture):
        self.path, self.fixture = Path(value), fixture

    @property
    def name(self):
        return self.path.name

    @property
    def parent(self):
        return _PathProbe(self.path.parent, self.fixture)

    def resolve(self):
        return _PathProbe(self.path.resolve(), self.fixture)

    def __eq__(self, other):
        return isinstance(other, _PathProbe) and self.path == other.path

    def is_file(self):
        return self.fixture.route_present if self.path == Path('/proc/net/route') else self.path.is_file()

    def stat(self):
        if self.fixture.stat_error:
            raise OSError('Metadata sintética no disponible')
        return SimpleNamespace(st_uid=self.fixture.owner_uid, st_mode=self.fixture.mode)


class IsolatedRetentionOwner(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nv2-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / 'data'
        self.directory.mkdir()
        self.route_present, self.stat_error = True, False
        self.owner_uid, self.mode = 1001, 0o40700
        self.os = SimpleNamespace(name='posix', geteuid=lambda: 1001)
        self.row = {'directory': str(self.directory), 'listeners': '127.0.0.1', 'address': '127.0.0.1'}
        self.conn = SimpleNamespace(dialect='postgres', _schema_lock_mode='exclusive',
                                    execute_exact=Mock(return_value=Mock(fetchone=lambda: self.row)))
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(config, 'IS_PRODUCTION', False))
        stack.enter_context(patch.object(retention, 'os', self.os))
        stack.enter_context(patch.object(retention, 'Path', side_effect=lambda value: _PathProbe(value, self)))
        self.network = stack.enter_context(patch.object(retention.socket, 'if_nameindex', return_value=[(1, 'lo')]))

    def test_legitimate_loopback_and_unix_socket_with_host_query(self):
        for address in ('127.0.0.1', None):
            with self.subTest(address=address):
                self.row['address'] = address
                self.assertTrue(retention.isolated_migration_owner(self.conn))
                query = self.conn.execute_exact.call_args.args[0]
                self.assertIn('host(inet_server_addr()) AS address', query)
                self.assertNotIn('inet_server_addr()::text', query)

    def test_any_other_address_or_listener_remains_rejected(self):
        for address in ('127.0.0.1/32', '127.0.0.2', '::1', 'localhost', '192.0.2.1', '0.0.0.0', ''):
            with self.subTest(address=address):
                self.row['address'] = address
                self.assertFalse(retention.isolated_migration_owner(self.conn))
        self.row['address'] = '127.0.0.1'
        for listener in ('*', '0.0.0.0', '::1', '127.0.0.1,192.0.2.1'):
            self.row['listeners'] = listener
            self.assertFalse(retention.isolated_migration_owner(self.conn))

    def test_network_and_route_proofs_cannot_be_claimed(self):
        for interfaces in ([], [(1, 'eth0')], [(1, 'lo'), (2, 'eth0')]):
            self.network.return_value = interfaces
            self.assertFalse(retention.isolated_migration_owner(self.conn))
        self.network.return_value = [(1, 'lo')]
        self.route_present = False
        self.assertFalse(retention.isolated_migration_owner(self.conn))
        self.conn.execute_exact.assert_not_called()

    def test_production_root_platform_and_locking_still_block_before_query(self):
        with patch.object(config, 'IS_PRODUCTION', True):
            self.assertFalse(retention.isolated_migration_owner(self.conn))
        self.os.geteuid = lambda: 0
        self.assertFalse(retention.isolated_migration_owner(self.conn))
        self.os.geteuid = lambda: 1001
        self.os.name = 'nt'
        self.assertFalse(retention.isolated_migration_owner(self.conn))
        self.os.name = 'posix'
        for lock in ('share', None):
            self.conn._schema_lock_mode = lock
            self.assertFalse(retention.isolated_migration_owner(self.conn))
        self.conn._schema_lock_mode = 'exclusive'
        self.conn.dialect = 'sqlite'
        self.assertFalse(retention.isolated_migration_owner(self.conn))
        self.conn.execute_exact.assert_not_called()

    def test_directory_is_exact_local_disposable_data_directory(self):
        for directory in (self.directory.parent / 'wrong',
                          self.directory.parent.parent / 'unowned' / 'data',
                          self.directory / 'nv2-nested' / 'data'):
            self.row['directory'] = str(directory)
            self.assertFalse(retention.isolated_migration_owner(self.conn))

    def test_uid_permissions_and_missing_metadata_are_not_relaxed(self):
        self.owner_uid = 1002
        self.assertFalse(retention.isolated_migration_owner(self.conn))
        self.owner_uid = 1001
        for mode in (0o40755, 0o40701, 0o40600):
            self.mode = mode
            self.assertFalse(retention.isolated_migration_owner(self.conn))
        self.mode = 0o40700
        self.stat_error = True
        self.assertFalse(retention.isolated_migration_owner(self.conn))

    def test_stage17_module_resolves_and_preserves_twenty_stage_runner(self):
        from scripts.run_postgres_backup_lab import CASES
        from tests.postgres_release_smoke import object_diff
        from tests.postgres_identity_diagnostic import object_diff as diagnostic
        self.assertEqual(len(CASES), 20)
        self.assertEqual(dict(CASES)['privacy + rollback'], ['-m', 'tests.postgres_release_smoke'])
        self.assertIs(object_diff, diagnostic)
