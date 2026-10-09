"""Continuidad live v1 sobre sesión prestada. Sólo SELECT, sin renovar A ni red."""

from datetime import datetime
from noesis.core.persistence import schema_version
from noesis.financial_operations.contracts import ConflictError, StateError
from .contracts import Profile, canonical, digest, instant
from .evaluator import FinancialReadinessEvaluator
from .historical_proof import historical_cut_hash


FIELDS = frozenset(('version', 'business_id', 'evaluation_uuid', 'evaluation_hash',
    'original_handoff_hash', 'previous_generation', 'generation_receipt_hash',
    'pause_receipt_uuid', 'pause_receipt_hash', 'profile_hash', 'capabilities',
    'grant_hash', 'configuration_hash', 'snapshot_hash', 'history_hash',
    'privacy_hash', 'source_hash', 'actor_user_id', 'actor_session_version', 'code_version'))


def validate_proof(value):
    """Validación estructural; decodificar no acredita una prueba de continuidad."""
    from noesis.financial_operations.contracts import positive_id, uuid_text
    from noesis.financial_providers.contracts import hash_text
    if type(value) is not dict or set(value) != FIELDS or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('RecoveryReadiness v1 cerrado requerido.')
    for name in ('business_id', 'previous_generation', 'actor_user_id'):
        positive_id(value[name])
    if type(value['actor_session_version']) is not int or value['actor_session_version'] < 0:
        raise ValueError('Sesión actual entera requerida.')
    for name in ('evaluation_uuid', 'pause_receipt_uuid'):
        if uuid_text(value[name]) != value[name]:
            raise ValueError('UUID canónico requerido.')
    for name in FIELDS:
        if name.endswith('_hash'):
            hash_text(value[name])
    from .contracts import Capability
    if type(value['capabilities']) is not list or value['capabilities'] != sorted(set(value['capabilities'])):
        raise ValueError('Closure canónica requerida.')
    for c in value['capabilities']:
        Capability(c)
    if type(value['code_version']) is not str or not value['code_version']:
        raise ValueError('Código requerido.')
    canonical(value)  # Rechaza números binarios y estructuras no JSON.
    return value


def verify_continuity(session, business_id, principal, api, control, original, proofs,
                      pause, generation_receipt, snapshot):
    """Revalidar las fuentes AHORA; el TTL de A sólo queda como provenance.

    La caducidad de providers/privacy/preflight sigue siendo obligatoria en F.
    Este verificador no emite una evaluación inicial ni altera estado alguno.
    """
    if schema_version(session.borrowed_connection) != 79:
        raise StateError('RecoveryReadiness exige schema79.')
    ev = FinancialReadinessEvaluator(session, business_id)
    business = ev._permission(principal, activation_verification=True)
    if (not control['ever_enabled'] or control['state'] != 'paused'
            or control['activation_generation'] < 1):
        raise StateError('Continuidad exclusiva de generación live pausada.')
    row = ev.repo.load(original['evaluation_uuid'])
    if not row:
        raise StateError('Provenance A ausente.')
    evaluation = ev.repo.result(row)
    if (evaluation['content_hash'] != original['evaluation_content_hash']
            or evaluation['outcome'] != 'fully_eligible' or evaluation['reasons']
            or evaluation['profile'] != original['profile']
            or evaluation['context']['code_version'] != api.code_version):
        raise ConflictError('Provenance A/perfil/código incoherentes.')
    first, _, handoff = api.generation(session, 1)
    if (first['evaluation_uuid'] != original['evaluation_uuid']
            or first['evaluation_content_hash'] != evaluation['content_hash']
            or first['profile'] != original['profile']
            or first['capabilities'] != original['capabilities']
            or first['capability_grant_hash'] != original['capability_grant_hash']
            or first['history'] != original['history']):
        raise ConflictError('Cadena de handoff/grants original cambió.')
    profile = Profile(tuple(original['profile']['capabilities']), original['profile']['profile_version'])
    closure, edges = profile.closure(fiscal_cancel_required=bool(business['verifactu_enabled']))
    if ([c.value for c in closure] != original['capabilities']
            or digest(proofs) != original['capability_grant_hash']
            or control['current_profile'] != canonical(profile.value())
            or str(control['current_evaluation_uuid']) != original['evaluation_uuid']
            or edges != evaluation['context']['dependencies']):
        raise ConflictError('Closure/grants de continuidad cambió.')
    h = original['history']
    # A verifica un corte fenced inicial. Tras handoff ese arco ya no existe:
    # contrastar el certificado congelado y las pruebas B actuales sin reimportar.
    from noesis.financial_history.reconciliation_repository import ReconciliationRepository
    from noesis.financial_history.reconciliation_verifier import ReconciliationVerifier
    rec = ReconciliationRepository(session, business_id, h['reconciliation_uuid']).result()
    if (rec['result'] != 'PASS' or rec['result_hash'] != h['result_hash']
            or h['rechecked_hash'] != h['result_hash'] or rec['generation'] != h['generation']
            or rec['plan_hash'] != h['plan_hash']):
        raise StateError('Certificado de reconciliación incoherente.')
    raw = session.borrowed_connection.execute_exact
    batch = raw('SELECT * FROM financial_history_import_batches WHERE business_id=? AND batch_uuid=?',
                (business_id, h['batch_uuid'])).fetchone()
    base = raw('SELECT * FROM financial_history_manifests WHERE business_id=? AND manifest_uuid=?',
               (business_id, h['manifest_uuid'])).fetchone()
    verifier = ReconciliationVerifier(session, business_id, batch, base, None, lambda _: None, 64)
    verifier.manifest_index()
    if verifier.findings or session.execute("SELECT 1 FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND (classification IN ('C','D') OR disposition='pending_incidence' OR unresolved_dependency_canonical<>'[]') LIMIT 1", (business_id, h['manifest_uuid'])).fetchone():
        raise StateError('Historia congelada pendiente/corrupta.')
    from noesis.financial_antecedents.proofs import ProofChecker
    checker = ProofChecker(session, business_id)
    event_proofs, covered_sources, prior = [], set(), 0
    from noesis.financial_activation.capabilities import capability_for_command
    for row in raw('SELECT * FROM economic_events WHERE business_id=? ORDER BY business_sequence', (business_id,)).fetchall():
        checked = checker.check(row)
        prior += 1
        if row['business_sequence'] != prior:
            raise ConflictError('Secuencia económica incoherente.')
        stored = checked['stored']
        covered_sources.add((stored.event.source_type.value, str(stored.event.source_id)))
        if stored.origin == 'live':
            op = session.execute('SELECT * FROM financial_operations WHERE business_id=? AND operation_uuid=?',
                                 (business_id, stored.operation_uuid)).fetchone()
            generation = op['activation_generation']
            if generation is not None:
                cap = capability_for_command(op['command_type']).value
                if (not 1 <= generation <= control['activation_generation'] or cap not in original['capabilities']
                        or op['activation_capability'] != cap):
                    raise ConflictError('Efecto financiero fuera de generación/closure original.')
                origin, _, _ = api.generation(session, generation)
                if origin['profile'] != original['profile'] or origin['capability_grant_hash'] != original['capability_grant_hash']:
                    raise ConflictError('Efecto financiero sin grants continuos.')
            elif not session.execute("SELECT 1 FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND source_type='economic_event' AND source_id=?", (business_id, h['manifest_uuid'], str(row['event_uuid']))).fetchone():
                raise ConflictError('EE live sin binding D ni provenance anterior al handoff.')
        event_proofs.append(dict(hash=checked['hash'], quality=checked['quality']))
    last = session.execute('SELECT last_sequence FROM economic_event_sequences WHERE business_id=?', (business_id,)).fetchone()
    if (last['last_sequence'] if last else 0) != prior:
        raise ConflictError('Testigo de secuencia económica incoherente.')
    from noesis.financial_history.readers import RawReader
    from noesis.financial_history.sources import PRIMARY
    reader = RawReader(session, business_id, page_size=64, cut_scope=True)
    for kind in sorted(PRIMARY):
        after = None
        while page := reader.page(kind, after):
            for source in page:
                if kind == 'invoice' and source.fields['status'] == 'borrador':
                    continue
                frozen = verifier.sources.get((kind, canonical(source.key)))
                if (frozen is None or frozen['hash'] != source.content_hash) and (kind, source.source_id) not in covered_sources:
                    raise ConflictError('Fuente financiera nueva/cambiada sin prueba B/EE.')
            after = page[-1].key
    current = dict(certificate_hash=rec['result_hash'], source_set_hash=batch['source_set_hash'],
                   plan_hash=batch['plan_hash'], event_proofs=sorted(event_proofs, key=canonical))
    from noesis.financial_history.reconciliation_verifier import storage_hash
    for table, key, uid, label in (
        ('financial_history_cut_manifests', 'manifest_uuid', h['manifest_uuid'], 'cut'),
        ('financial_history_manifests', 'manifest_uuid', h['manifest_uuid'], 'manifest'),
        ('financial_history_import_batches', 'batch_uuid', h['batch_uuid'], 'batch'),
        ('financial_history_reconciliations', 'reconciliation_uuid', h['reconciliation_uuid'], 'reconciliation'),
    ):
        source = raw('SELECT * FROM ' + table + ' WHERE business_id=? AND ' + key + '=?', (business_id, uid)).fetchone()
        hashed = historical_cut_hash(session, business_id, source) if label == 'cut' and source else storage_hash(source) if source else None
        if not source or hashed != h[label + '_storage_hash']:
            raise ConflictError('Testigo histórico cambió.')
    epoch = raw('SELECT * FROM financial_history_epochs WHERE business_id=? AND epoch_uuid=?',
                            (business_id, h['epoch_uuid'])).fetchone()
    if (not epoch or epoch['state'] != 'handed_off' or epoch['fence_enabled']
            or str(epoch['handoff_uuid']) != handoff['receipt_uuid']
            or digest(epoch['source_scope_canonical']) != h['source_scope_hash']
            or epoch['fence_version'] != h['fence_version']
            or epoch['generation'] != h['generation']
            or instant(epoch['t0'] if isinstance(epoch['t0'], datetime) else datetime.fromisoformat(epoch['t0'])) != h['t0']):
        raise StateError('Handoff/fence histórico cambió.')
    fence = session.execute('SELECT * FROM financial_history_control WHERE business_id=?', (business_id,)).fetchone()
    if not fence or fence['fence_enabled'] or str(fence['epoch_uuid']) != h['epoch_uuid']:
        raise StateError('Control histórico cambió.')
    from noesis.financial_privacy.repository import assert_open
    from noesis.financial_privacy.retention import readiness_evidence
    assert_open(session, business_id)
    privacy = readiness_evidence(session, business_id)
    if not privacy['privacy_ready'] or not privacy['export_ready']:
        raise StateError('PRIVACY_NOT_READY/EXPORT_NOT_READY en continuidad.')
    sources = ev._sources()
    if {'pending_live_operation', 'uncertain_dispatch'} & set(sources['economic_kinds']):
        raise StateError('Incertidumbre financiera bloquea continuidad.')
    from noesis.financial_providers.schema import ATTEMPTS, RESULTS
    if session.execute(f"SELECT 1 FROM {ATTEMPTS} a LEFT JOIN {RESULTS} r ON r.business_id=a.business_id AND r.attempt_uuid=a.evidence_uuid WHERE a.business_id=? AND (r.evidence_uuid IS NULL OR r.result='UNKNOWN_EXTERNAL_RESULT') LIMIT 1", (business_id,)).fetchone():
        raise StateError('UNKNOWN_EXTERNAL_RESULT bloquea continuidad.')
    value = dict(version=1, business_id=business_id, evaluation_uuid=original['evaluation_uuid'],
        evaluation_hash=evaluation['content_hash'], original_handoff_hash=digest(handoff),
        previous_generation=control['activation_generation'], generation_receipt_hash=digest(generation_receipt),
        pause_receipt_uuid=pause['receipt_uuid'], pause_receipt_hash=digest(pause),
        profile_hash=profile.content_hash, capabilities=original['capabilities'], grant_hash=digest(proofs),
        configuration_hash=snapshot['configuration_hash'], snapshot_hash=digest(snapshot),
        history_hash=digest(current), privacy_hash=digest(privacy), source_hash=digest(sources),
        actor_user_id=principal.user_id, actor_session_version=principal.session_version, code_version=api.code_version)
    return validate_proof(value)
