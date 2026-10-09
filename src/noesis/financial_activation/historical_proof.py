"""Equivalencia histórica limitada al handoff certificado, nunca a source drift."""

import json

from noesis.financial_operations.contracts import StateError
from noesis.financial_history.reconciliation_verifier import storage_hash
from .contracts import canonical, digest


def historical_cut_hash(session, business_id, cut):
    if cut['boundary_current']:
        return storage_hash(cut)
    epoch = session.execute('SELECT * FROM financial_history_epochs WHERE business_id=? AND epoch_uuid=?',
                            (business_id, str(cut['epoch_uuid']))).fetchone()
    if not epoch or epoch['state'] != 'handed_off' or epoch['fence_enabled'] or not epoch.get('handoff_uuid') or not cut['certifiable']:
        raise StateError('Certificado histórico no tiene handoff íntegro.')
    row = session.execute('''SELECT t.* FROM financial_activation_transitions t
        JOIN financial_activation_generations g ON g.business_id=t.business_id AND g.receipt_uuid=t.receipt_uuid
        JOIN financial_activation_control a ON a.business_id=t.business_id
        WHERE t.business_id=? AND t.receipt_uuid=? AND t.stage='enabled' AND g.activation_generation=1
        AND g.origin='handoff' AND a.ever_enabled=TRUE AND a.activation_generation>=1''',
        (business_id, str(epoch['handoff_uuid']))).fetchone()
    if not row:
        raise StateError('Recibo de handoff ausente.')
    body = json.loads(row['receipt_canonical'])
    if digest(body) != row['content_hash'] or canonical(body) != row['receipt_canonical']:
        raise StateError('Recibo de handoff incoherente.')
    history = body['evidence']['history']
    original = dict(cut, boundary_current=True if session.dialect == 'postgres' else 1)
    fingerprint = storage_hash(original)
    if (history['cut_storage_hash'] != fingerprint or history['epoch_uuid'] != str(cut['epoch_uuid'])
            or history['manifest_uuid'] != str(cut['manifest_uuid']) or history['generation'] != cut['generation']
            or history['source_set_hash'] != cut['source_set_hash'] or history['plan_hash'] != cut['plan_hash']):
        raise StateError('Handoff no conserva la identidad/hashes del cut original.')
    return fingerprint
