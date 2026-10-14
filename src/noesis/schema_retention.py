"""Perfiles de retención cerrados; exclusivamente migrador técnico aislado."""

import os
from pathlib import Path
import socket
import tempfile


RETENTION_VERSIONS = (53, 54, 55, 58)


def retention_objects(version):
    from .schema_objects import expected_objects
    if version not in RETENTION_VERSIONS:
        return None
    # Estas migrations históricas ya conservan columnas/recibos al bajar.
    # El delta60 entero es cerrado; no se infieren dependencias de la DB actual.
    retained = dict(expected_objects('postgres', version))
    retained['column:invoices:pending_fields'] = expected_objects('postgres', 58)['column:invoices:pending_fields']
    retained['column:assistant_messages:actor'] = expected_objects('postgres', 59)['column:assistant_messages:actor']
    stage60 = expected_objects('postgres', 60)
    stage59 = expected_objects('postgres', 59)
    retained.update({key: value for key, value in stage60.items() if key not in stage59})
    return retained


def isolated_migration_owner(conn):
    from . import config
    if (conn.dialect != 'postgres' or getattr(conn, '_schema_lock_mode', None) != 'exclusive'
            or config.IS_PRODUCTION or os.name != 'posix' or os.geteuid() == 0
            or {name for _, name in socket.if_nameindex()} != {'lo'}
            or not Path('/proc/net/route').is_file()):
        return False
    # Prueba del cluster local desechable, no una URL/flag que afirme aislamiento.
    row = conn.execute_exact("SELECT current_setting('data_directory') AS directory, "
                             "current_setting('listen_addresses') AS listeners, "
                             "inet_server_addr()::text AS address").fetchone()
    directory = Path(row['directory']).resolve()
    if (row['listeners'] not in ('', '127.0.0.1') or row['address'] not in (None, '127.0.0.1')
            or directory.name != 'data' or not directory.parent.name.startswith('nv2-')
            or directory.parent.parent != Path(tempfile.gettempdir()).resolve()):
        return False
    try:
        stat = directory.parent.stat()
    except OSError:
        return False
    return stat.st_uid == os.geteuid() and stat.st_mode & 0o777 == 0o700
