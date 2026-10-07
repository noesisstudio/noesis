"""Límites operativos v1; no son SLO ni una política de conservación legal."""

import time
from noesis.core.locks import lock_key
from noesis.financial_operations.contracts import StateError
from .contracts import OperationalPolicy


def acquire_gate(session, business_id):
    """El mismo gate compartido, con espera F acotada; nunca otro namespace."""
    limit = OperationalPolicy().gate_wait_goal_ms / 1000
    start = time.monotonic()
    if session.dialect == 'sqlite':
        session.execute('PRAGMA busy_timeout=1000')
        session.execute('BEGIN IMMEDIATE')
        return
    key = lock_key('financial-writer', business_id)
    while not session.execute('SELECT pg_try_advisory_xact_lock(?) AS acquired', (key,)).fetchone()['acquired']:
        if time.monotonic() - start >= limit:
            raise StateError('GATE_WAIT_REVIEW_REQUIRED')
        time.sleep(0.01)


def handoff_timing(elapsed_ms):
    policy = OperationalPolicy()
    if elapsed_ms >= policy.handoff_review_ms:
        return 'MANUAL_REVIEW_REQUIRED'
    return 'HANDOFF_WARNING' if elapsed_ms >= policy.handoff_warning_ms else 'WITHIN_OPERATIONAL_POLICY'
