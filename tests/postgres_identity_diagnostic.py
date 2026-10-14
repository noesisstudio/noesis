"""Instrumentación sintética: metadatos DDL privados, sólo hashes en stdout."""
import hashlib
import json
import os
from pathlib import Path

from noesis.schema_lineage import canonical
from noesis.schema_objects import expected_objects, physical_objects


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def persist(label, receipt):
    directory = os.environ.get('NOESIS_SCHEMA_DIAGNOSTIC_DIR')
    if directory:
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = root / (label + '.json')
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if os.name == 'posix':
            path.chmod(0o600)


def object_diff(conn, label, *, version=75):
    namespace = conn.execute_exact('SELECT current_schema() AS namespace').fetchone()['namespace']
    actual = physical_objects(conn, namespace)
    expected = expected_objects('postgres', version)
    differences = []
    for key in sorted(set(actual) | set(expected)):
        if actual.get(key) == expected.get(key):
            continue
        differences.append({
            'object_key': key,
            'classification': 'missing' if key not in actual else 'extra' if key not in expected else 'changed',
            'actual_hash': digest(actual[key]) if key in actual else None,
            'expected_hash': digest(expected[key]) if key in expected else None,
        })
    receipt = {'label': label, 'actual_profile_hash': digest(actual),
               'expected_profile_hash': digest(expected), 'differences': differences}
    persist(label, receipt)
    print('PG_OBJECT_DIFF ' + json.dumps(receipt, sort_keys=True), flush=True)
    return receipt


def amount_check(conn, label):
    namespace = conn.execute_exact('SELECT current_schema() AS namespace').fetchone()['namespace']
    row = conn.execute_exact(
        'SELECT co.conname,co.contype,co.condeferrable,co.condeferred,co.convalidated,co.connoinherit,'
        'pg_get_constraintdef(co.oid,false) AS constraintdef,'
        'pg_get_expr(co.conbin,co.conrelid,false) AS expression '
        'FROM pg_constraint co JOIN pg_class c ON c.oid=co.conrelid '
        'JOIN pg_namespace n ON n.oid=c.relnamespace '
        'WHERE n.nspname=? AND c.relname=? AND co.conname=?',
        (namespace, 'economic_events', 'economic_events_amount_check'),
    ).fetchone()
    if row is None:
        raise AssertionError('AMOUNT_CHECK_MISSING_IN_SYNTHETIC_DIAGNOSTIC')
    descriptor = dict(row)
    column = dict(conn.execute_exact(
        'SELECT format_type(a.atttypid,a.atttypmod) AS column_type,a.atttypmod,'
        'i.numeric_precision,i.numeric_scale FROM pg_attribute a '
        'JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace '
        'JOIN information_schema.columns i ON i.table_schema=n.nspname '
        'AND i.table_name=c.relname AND i.column_name=a.attname '
        'WHERE n.nspname=? AND c.relname=? AND a.attname=?',
        (namespace, 'economic_events', 'amount'),
    ).fetchone())
    server = dict(conn.execute_exact(
        "SELECT current_setting('server_version') AS version,"
        "current_setting('server_version_num') AS version_num"
    ).fetchone())
    receipt = {'descriptor': descriptor, 'field_hashes': {k: digest(v) for k, v in descriptor.items()},
               'column': column, 'server': server}
    persist(label, receipt)
    print('PG_AMOUNT_CHECK ' + json.dumps({'label': label, 'field_hashes': receipt['field_hashes'],
                                         'column': column, 'server': server}, sort_keys=True), flush=True)
    return receipt
