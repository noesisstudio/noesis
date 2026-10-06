"""Control plane interno D; transacciones únicas, autoridad humana y cero providers."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from noesis import config, db, migrations
from noesis.core.locks import lock_business
from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import AccessDenied, ConflictError, StateError, uuid_text
from noesis.financial_operations.repository import OperationsRepository
from noesis.financial_operations.contracts import OperationState
from noesis.financial_history.reconciliation_verifier import storage_hash
from .activation_contracts import ActivationRequest, ActivationPermission, ActivationAction, PauseReason
from .contracts import canonical, digest, instant, tenant
from .evaluator import FinancialReadinessEvaluator
from .execution_context import execution_context
from .readiness_verifier import verify_readiness
from .handoff_schema import REQUESTS, AUTHORIZATIONS, TRANSITIONS, GENERATIONS, GRANTS
from .configuration_snapshot import configuration_hash


def clock():
    return datetime.now(timezone.utc)


class FinancialActivation:
    """Sin rutas, tools, IA ni authority heredada de Operations.

    El llamador interno solo presenta una solicitud derivada por servidor y su
    confirmación humana exacta. Cada entrada revalida cuenta, tenant y sesión.
    """

    def __init__(self, business_id, *, code_version):
        self.bid = tenant(business_id)
        if not isinstance(code_version, str) or not 1 <= len(code_version) <= 128:
            raise ValueError("Identidad de código requerida.")
        self.code_version = code_version

    @contextmanager
    def transaction(self, principal, permission):
        if config.IS_PRODUCTION:
            raise StateError('D local no autoriza activación de producción.')
        if permission != ActivationPermission.MANAGE:
            raise AccessDenied("financial.activation.manage requerido.")
        with db.get_conn() as conn:
            s = FinancialSession(conn)
            if s.dialect == 'sqlite':
                s.execute('BEGIN IMMEDIATE')
            lock_business(s, self.bid)
            FinancialReadinessEvaluator(s, self.bid)._permission(
                principal, locking=True, activation_verification=True)
            if migrations.current_version_connection(conn) != 77:
                raise StateError('Schema77 requerido.')
            yield s

    def control(self, s):
        row = s.execute('SELECT * FROM financial_activation_control WHERE business_id=?', (self.bid,)).fetchone()
        if not row:
            raise StateError('Evaluación final de A requerida.')
        return row

    def request(self, s, uid, principal):
        row = s.execute(f'SELECT * FROM {REQUESTS} WHERE business_id=? AND request_uuid=?', (self.bid, uuid_text(uid))).fetchone()
        if not row or row['actor_user_id'] != principal.user_id or row['actor_session_version'] != principal.session_version:
            raise AccessDenied('Solicitud no disponible para esta sesión.')
        req = ActivationRequest.decode(row['request_canonical'])
        if req.content_hash != row['request_hash'] or req.body['code_version'] != self.code_version:
            raise ConflictError('Identidad/hash de solicitud cambió.')
        return req

    def context(self, req, stage):
        b = req.body
        return dict(kind='control', business_id=self.bid, request_uuid=b['request_uuid'],
                    request_hash=req.content_hash, generation=b['activation_generation'], stage=stage)

    def snapshot(self, s, principal):
        """Huella de recuperación; solo hashes, sin copiar datos personales.

        Excluir transporte de outbox (lo cierra F) y lifecycle D. Fuentes finales,
        operaciones, autorizaciones, EE y configuración quedan íntegramente cubiertos.
        """
        evaluator = FinancialReadinessEvaluator(s, self.bid)
        evaluator._permission(principal, locking=True, activation_verification=True)
        from noesis.financial_history.cut_scope import guarded_columns
        tables = sorted(set(guarded_columns()) | {'financial_operations', 'financial_authorizations'})
        values = {}
        for table in tables:
            if table in ('verifactu_outbox', 'verifactu_cancellation_outbox'):
                excluded = {'status', 'sent_at', 'completed_at', 'updated_at', 'attempts'}
            else:
                excluded = set()
            values[table] = sorted(storage_hash({k: v for k, v in dict(row).items() if k not in excluded})
                                   for row in s.borrowed_connection.execute_exact(
                                       'SELECT * FROM ' + table + ' WHERE business_id=?', (self.bid,)).fetchall())
        return dict(version=1, configuration_hash=configuration_hash(s, self.bid),
                    financial_hash=digest(values), table_hashes={k: digest(v) for k, v in values.items()})

    def generation(self, s, number):
        row = s.execute(f'SELECT * FROM {GENERATIONS} WHERE business_id=? AND activation_generation=?', (self.bid, number)).fetchone()
        if not row:
            raise StateError('Generación durable ausente.')
        receipt = self.receipt(s, row['receipt_uuid'])
        request = s.execute(f'SELECT * FROM {REQUESTS} WHERE business_id=? AND request_uuid=?',
                            (self.bid, str(row['request_uuid']))).fetchone()
        grants = s.execute(f'SELECT * FROM {GRANTS} WHERE business_id=? AND activation_generation=? ORDER BY capability',
                           (self.bid, number)).fetchall()
        req = ActivationRequest.decode(request['request_canonical'])
        proofs = []
        for g in grants:
            import json
            proof = json.loads(g['proof_canonical'])
            if (digest(proof) != g['proof_hash'] or proof['result'] != 'eligible'
                    or g['grant_hash'] != row['grant_hash'] or g['profile_hash'] != row['profile_hash']
                    or str(g['receipt_uuid']) != str(row['receipt_uuid'])):
                raise ConflictError('Grant durable incoherente.')
            proofs.append(proof)
        if (req.content_hash != request['request_hash'] or digest(proofs) != row['grant_hash']
                or [p['capability'] for p in proofs] != req.body['capabilities']
                or receipt['activation_generation'] != number or receipt['final_state'] != 'enabled'):
            raise ConflictError('Conjunto exacto de grants incoherente.')
        return req.body, proofs, receipt

    def receipt(self, s, uid):
        import json
        row = s.execute(f'SELECT * FROM {TRANSITIONS} WHERE business_id=? AND receipt_uuid=?', (self.bid, str(uid))).fetchone()
        if not row:
            raise StateError('Recibo ausente.')
        body = json.loads(row['receipt_canonical'])
        if canonical(body) != row['receipt_canonical'] or digest(body) != row['content_hash']:
            raise ConflictError('Recibo corrupto.')
        return body

    def recovery(self, s, principal, control):
        original, proofs, generation_receipt = self.generation(s, control['activation_generation'])
        pause = self.receipt(s, control['current_transition_uuid'])
        if pause['final_state'] != 'paused' or pause['activation_generation'] != control['activation_generation']:
            raise StateError('Pausa durable exacta requerida.')
        current = self.snapshot(s, principal)
        if current['configuration_hash'] != original['configuration_hash']:
            raise ConflictError('Configuración difiere de la evaluación que concedió los grants.')
        kinds = FinancialReadinessEvaluator(s, self.bid)._sources()['economic_kinds']
        if 'uncertain_dispatch' in kinds or 'pending_live_operation' in kinds:
            raise StateError('Operación/dispatch no terminal bloquea recuperación.')
        if current != pause['evidence']['snapshot']:
            raise ConflictError('Drift tras pausa; recuperación D denegada.')
        return original, proofs, dict(version=1, pause_receipt_uuid=pause['receipt_uuid'],
                                     pause_receipt_hash=digest(pause), generation_receipt_hash=digest(generation_receipt),
                                     snapshot=current)

    def prepare(self, principal, request_uuid, action, *, evaluation_uuid=None, pause_reason=None,
                permission=ActivationPermission.MANAGE):
        action, uid = ActivationAction(action), uuid_text(request_uuid)
        with self.transaction(principal, permission) as s:
            previous = s.execute(f'SELECT request_uuid FROM {REQUESTS} WHERE business_id=? AND request_uuid=?', (self.bid, uid)).fetchone()
            if previous:
                req = self.request(s, uid, principal)
                if req.body['action'] != action.value or (evaluation_uuid is not None and req.body['evaluation_uuid'] != uuid_text(evaluation_uuid)) or req.body['pause_reason'] != pause_reason:
                    raise ConflictError('Reutilización de identidad con distinto contenido.')
                return req
            control = self.control(s)
            recovery = None
            if action in (ActivationAction.ENABLE, ActivationAction.ABORT):
                states = ('off', 'validating', 'ready') if action == ActivationAction.ENABLE else ('validating', 'ready')
                if control['ever_enabled'] or control['state'] not in states:
                    raise StateError('Transición inicial denegada.')
                evidence = verify_readiness(s, self.bid, principal, evaluation_uuid or str(control['current_evaluation_uuid']))
                if evidence['evaluation']['context']['code_version'] != self.code_version:
                    raise ConflictError('Evaluación corresponde a otro código.')
                origin = dict(evaluation_uuid=evidence['evaluation']['evaluation_uuid'],
                              evaluation_content_hash=evidence['evaluation']['content_hash'],
                              profile=evidence['profile'], profile_hash=digest(evidence['profile']),
                              capabilities=evidence['capabilities'], capability_grant_hash=evidence['grant_hash'],
                              history=evidence['history'], external_evidence_hash=evidence['external_hash'])
            else:
                expected = 'enabled' if action == ActivationAction.PAUSE else 'paused'
                if not control['ever_enabled'] or control['state'] != expected:
                    raise StateError('Transición de generación live denegada.')
                if action == ActivationAction.RESUME:
                    original, _, recovery = self.recovery(s, principal, control)
                else:
                    PauseReason(pause_reason)
                    original, _, _ = self.generation(s, control['activation_generation'])
                origin = {k: original[k] for k in ('evaluation_uuid', 'evaluation_content_hash', 'profile', 'profile_hash',
                                                   'capabilities', 'capability_grant_hash', 'history', 'external_evidence_hash')}
            now = clock()
            number = control['activation_generation'] + int(action in (ActivationAction.ENABLE, ActivationAction.RESUME))
            body = dict(request_version=1, business_id=self.bid, request_uuid=uid, action=action.value,
                        expected_state=control['state'], expected_control_revision=control['control_revision'],
                        activation_generation=number, previous_generation=control['activation_generation'],
                        **origin, configuration_hash=configuration_hash(s, self.bid), code_version=self.code_version, schema_version=77,
                        actor_user_id=principal.user_id, actor_session_version=principal.session_version,
                        permission=ActivationPermission.MANAGE.value, created_at=instant(now),
                        expires_at=instant(now + timedelta(minutes=5)), pause_reason=pause_reason, recovery_proof=recovery)
            req = ActivationRequest(body)
            with execution_context(s, self.context(req, 'prepare')):
                s.execute(f'''INSERT INTO {REQUESTS}
                    (business_id,request_uuid,request_version,action,expected_state,expected_control_revision,proposed_generation,
                     evaluation_uuid,evaluation_hash,profile_canonical,profile_hash,capabilities_canonical,grant_hash,
                     actor_user_id,actor_session_version,permission,created_at,expires_at,request_canonical,request_hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (self.bid, uid, 1, action.value, body['expected_state'], body['expected_control_revision'], number,
                     body['evaluation_uuid'], body['evaluation_content_hash'], canonical(body['profile']), body['profile_hash'],
                     canonical(body['capabilities']), body['capability_grant_hash'], principal.user_id, principal.session_version,
                     body['permission'], body['created_at'], body['expires_at'], req.canonical(), req.content_hash))
            return req

    def authorize(self, principal, request_uuid, *, approved_hash, kind='human_confirmation',
                  permission=ActivationPermission.MANAGE):
        if kind != 'human_confirmation':
            raise AccessDenied('Confirmación humana de activación requerida.')
        with self.transaction(principal, permission) as s:
            req = self.request(s, request_uuid, principal)
            if approved_hash != req.content_hash:
                raise ConflictError('Hash aprobado distinto de la solicitud exacta.')
            old = s.execute(f'SELECT authorization_uuid FROM {AUTHORIZATIONS} WHERE business_id=? AND request_uuid=?',
                            (self.bid, req.body['request_uuid'])).fetchone()
            if old:
                return str(old['authorization_uuid'])
            self.validity(req)
            if self.control(s)['control_revision'] != req.body['expected_control_revision']:
                raise ConflictError('Revisión de control cambió antes de confirmar.')
            uid = str(uuid4())
            with execution_context(s, self.context(req, 'authorize')):
                s.execute(f'''INSERT INTO {AUTHORIZATIONS}
                    (business_id,authorization_uuid,request_uuid,approved_hash,actor_user_id,actor_session_version,kind,permission,authorized_at)
                    VALUES (?,?,?,?,?,?,'human_confirmation',?,?)''',
                    (self.bid, uid, req.body['request_uuid'], approved_hash, principal.user_id, principal.session_version,
                     ActivationPermission.MANAGE.value, instant(clock())))
            return uid

    def validity(self, req):
        if clock() >= datetime.fromisoformat(req.body['expires_at']):
            raise StateError('Solicitud de activación caducada.')

    def checkpoint(self, name):
        """Puntos de inyección de fallo en tests; ningún callback externo configurable."""

    def advance(self, principal, request_uuid, stage, *, permission=ActivationPermission.MANAGE):
        with self.transaction(principal, permission) as s:
            req = self.request(s, request_uuid, principal)
            old = s.execute(f'SELECT receipt_uuid FROM {TRANSITIONS} WHERE business_id=? AND request_uuid=? AND stage=?',
                            (self.bid, req.body['request_uuid'], stage)).fetchone()
            if old:
                return self.receipt(s, old['receipt_uuid'])
            self.validity(req)
            auth = s.execute(f'SELECT * FROM {AUTHORIZATIONS} WHERE business_id=? AND request_uuid=?',
                             (self.bid, req.body['request_uuid'])).fetchone()
            if not auth or auth['approved_hash'] != req.content_hash:
                raise AccessDenied('Confirmación humana durable exacta requerida.')
            b, control = req.body, self.control(s)
            if b['action'] != 'pause' and configuration_hash(s, self.bid) != b['configuration_hash']:
                raise ConflictError('Configuración congelada de activación cambió.')
            action = b['action']
            allowed = dict(enable=('validating', 'ready', 'enabled'), abort=('off',), pause=('paused',), resume=('enabled',))
            if stage not in allowed[action]:
                raise StateError('Stage/action incompatibles.')
            if action == 'resume':
                if control['state'] != 'paused' or control['control_revision'] != b['expected_control_revision']:
                    raise ConflictError('Pausa cambió.')
                _, proofs, proof = self.recovery(s, principal, control)
                if proof != b['recovery_proof']:
                    raise ConflictError('Prueba de recuperación cambió.')
                for target in ('validating', 'ready', 'enabled'):
                    control = self.control(s)
                    receipt = self.transition(s, req, auth, control, target, dict(recovery=proof), proofs)
            elif action == 'pause':
                if control['state'] != 'enabled' or control['control_revision'] != b['expected_control_revision']:
                    raise ConflictError('Generación/control cambió.')
                _, proofs, _ = self.generation(s, control['activation_generation'])
                cancelled, revoked = [], []
                repo = OperationsRepository(s, self.bid)
                for row in s.execute("SELECT * FROM financial_operations WHERE business_id=? AND entry_namespace<>'historical' AND state IN ('prepared','approved')", (self.bid,)).fetchall():
                    self.checkpoint('before_pause_cancel')
                    repo.transition(row, OperationState.CANCELLED, instant(clock()))
                    cancelled.append(str(row['operation_uuid']))
                    self.checkpoint('after_pause_cancel')
                for row in s.execute("SELECT * FROM financial_authorizations WHERE business_id=? AND kind='mandate' AND operation_uuid IS NULL AND revoked_at IS NULL", (self.bid,)).fetchall():
                    self.checkpoint('before_pause_revoke')
                    repo.revoke_mandate(row, instant(clock()))
                    revoked.append(str(row['authorization_uuid']))
                    self.checkpoint('after_pause_revoke')
                self.checkpoint('pause_terminalization')
                evidence = dict(cancelled=sorted(cancelled), revoked=sorted(revoked), snapshot=self.snapshot(s, principal))
                receipt = self.transition(s, req, auth, control, 'paused', evidence, proofs)
            else:
                predecessor = dict(validating=('off',), ready=('validating',), enabled=('ready',), off=('validating', 'ready'))[stage]
                if control['state'] not in predecessor or control['ever_enabled']:
                    raise StateError('Arco de activación inicial denegado.')
                evidence = verify_readiness(s, self.bid, principal, b['evaluation_uuid'])
                if (evidence['external_hash'] != b['external_evidence_hash'] or evidence['grant_hash'] != b['capability_grant_hash']
                        or evidence['profile'] != b['profile'] or evidence['history'] != b['history']
                        or evidence['evaluation']['content_hash'] != b['evaluation_content_hash']
                        or evidence['evaluation']['context']['code_version'] != self.code_version):
                    raise ConflictError('Snapshot exacto de activación cambió.')
                earlier = s.execute(f'SELECT COUNT(*) AS n FROM {TRANSITIONS} WHERE business_id=? AND request_uuid=?',
                                    (self.bid, b['request_uuid'])).fetchone()['n']
                if control['control_revision'] != b['expected_control_revision'] + earlier:
                    raise ConflictError('Revisión de control cambió fuera de la solicitud.')
                self.checkpoint('readiness_verified')
                receipt = self.transition(s, req, auth, control, stage,
                                          dict(history=evidence['history'], external_hash=evidence['external_hash']), evidence['grants'])
            self.checkpoint('before_commit')
        self.checkpoint('after_commit')
        return receipt

    def transition(self, s, req, auth, control, stage, evidence, proofs):
        b, uid, now = req.body, str(uuid4()), instant(clock())
        generation = b['activation_generation'] if stage == 'enabled' else control['activation_generation']
        receipt = dict(receipt_version=1, business_id=self.bid, receipt_uuid=uid, request_uuid=b['request_uuid'],
                       request_hash=req.content_hash, authorization_uuid=str(auth['authorization_uuid']),
                       previous_state=control['state'], final_state=stage, previous_revision=control['control_revision'],
                       final_revision=control['control_revision'] + 1, activation_generation=generation,
                       recorded_at=now, evidence=evidence)
        with execution_context(s, self.context(req, stage)):
            s.execute(f'''INSERT INTO {TRANSITIONS}
                (business_id,receipt_uuid,request_uuid,authorization_uuid,stage,previous_state,final_state,
                 previous_revision,final_revision,activation_generation,recorded_at,receipt_canonical,content_hash)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (self.bid, uid, b['request_uuid'], str(auth['authorization_uuid']), stage, control['state'], stage,
                 control['control_revision'], receipt['final_revision'], generation, now, canonical(receipt), digest(receipt)))
            self.checkpoint('receipt_written')
            if stage == 'enabled':
                s.execute(f'''INSERT INTO {GENERATIONS} (business_id,activation_generation,previous_generation,origin,receipt_uuid,
                    request_uuid,evaluation_uuid,profile_hash,grant_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (self.bid, generation, generation-1, 'handoff' if generation == 1 else 'recovery', uid,
                     b['request_uuid'], b['evaluation_uuid'], b['profile_hash'], b['capability_grant_hash'], now))
                self.checkpoint('generation_written')
                for proof in proofs:
                    s.execute(f'''INSERT INTO {GRANTS} (business_id,activation_generation,capability,evaluation_uuid,
                        profile_hash,closure_canonical,proof_canonical,proof_hash,grant_hash,receipt_uuid)
                        VALUES (?,?,?,?,?,?,?,?,?,?)''',
                        (self.bid, generation, proof['capability'], b['evaluation_uuid'], b['profile_hash'],
                         canonical(b['capabilities']), canonical(proof), digest(proof), b['capability_grant_hash'], uid))
                self.checkpoint('grants_written')
                if generation == 1:
                    h = b['history']
                    count = s.execute("UPDATE financial_history_epochs SET state='handed_off',fence_enabled=FALSE,handoff_uuid=?,updated_at=? WHERE business_id=? AND epoch_uuid=? AND state='fenced' AND fence_enabled=TRUE",
                                      (uid, now, self.bid, h['epoch_uuid'])).rowcount
                    if count != 1:
                        raise ConflictError('Epoch/fence inicial cambió.')
                    self.checkpoint('epoch_handed_off')
                    fence = s.execute('SELECT fence_enabled FROM financial_history_control WHERE business_id=?', (self.bid,)).fetchone()
                    if not fence or fence['fence_enabled']:
                        raise StateError('Fence no coordinado con handoff.')
                    self.checkpoint('fence_removed')
                    cut = s.execute('SELECT certifiable,boundary_current FROM financial_history_cut_manifests WHERE business_id=? AND manifest_uuid=?',
                                    (self.bid, h['manifest_uuid'])).fetchone()
                    if not cut or not cut['certifiable'] or cut['boundary_current']:
                        raise StateError('Certificado histórico no conservado.')
                    self.checkpoint('certificate_verified')
            self.checkpoint('before_control')
            s.execute('''UPDATE financial_activation_control SET state=?,control_revision=?,activation_generation=?,ever_enabled=?,
                      current_profile=?,current_evaluation_uuid=?,current_transition_uuid=?,updated_at=? WHERE business_id=?''',
                      (stage, receipt['final_revision'], generation, bool(control['ever_enabled']) or stage == 'enabled',
                       canonical(b['profile']), b['evaluation_uuid'], uid, now, self.bid))
            self.checkpoint('control_written')
        return receipt
