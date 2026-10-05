"""Corte interno autenticado: epoch durable, sin importación ni activación."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import logging
import re
from uuid import uuid4

from noesis import db, migrations
from noesis.core.locks import lock_business
from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import AccessDenied, ConflictError, StateError, uuid_text
from .cut_scope import SCOPE
from .fence import installed
from .repository import canonical, stamp
from .service import HistoryDiagnostics

log = logging.getLogger(__name__)


class EpochUnavailable(StateError):
    """El corte dejó de ser vigente. Conservar inventario y abortar certificación."""


def label(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', value):
        raise ValueError('Identificador explícito sin URL, credencial ni contenido libre requerido.')
    return value


class HistoryCutoff(HistoryDiagnostics):
    @contextmanager
    def _session(self, principal):
        with db.get_conn() as conn:
            if conn.dialect == 'sqlite':
                conn.execute('BEGIN IMMEDIATE')
            session = FinancialSession(conn)
            # Preflight sin locks: un writer con gate puede actualizar el negocio.
            self._permission(session, principal)
            if not installed(session):
                raise ValueError('Esquema71 requerido para corte histórico.')
            lock_business(session, self.business_id)
            # Revalidar sesión/suscripción con locks DESPUÉS del gate.
            suffix = ' FOR SHARE' if conn.dialect == 'postgres' else ''
            session.execute('SELECT id FROM users WHERE business_id=? AND id=?'+suffix,
                            (self.business_id, getattr(principal, 'user_id', None))).fetchone()
            session.execute('SELECT id FROM businesses WHERE id=?'+suffix, (self.business_id,)).fetchone()
            self._permission(session, principal)
            yield session

    def _row(self, session, epoch_uuid, principal, *, active=False):
        row = session.execute('SELECT * FROM financial_history_epochs WHERE business_id=? AND epoch_uuid=?',
                              (self.business_id, uuid_text(epoch_uuid))).fetchone()
        if not row or row['opened_by'] != principal.user_id:
            raise AccessDenied('Epoch propio del operador y negocio requerido.')
        if active:
            control = session.execute('SELECT * FROM financial_history_control WHERE business_id=?', (self.business_id,)).fetchone()
            if (row['state'] != 'fenced' or not row['fence_enabled'] or not control or not control['fence_enabled']
                    or str(control['epoch_uuid']) != str(row['epoch_uuid']) or control['generation'] != row['generation']
                    or row['source_scope_canonical'] != canonical(SCOPE) or row['source_scope_version'] != 1):
                raise EpochUnavailable('Epoch invalidado/liberado o scope/control incompatible; no certificar.')
        return row

    def _audit(self, session, epoch_uuid, principal, action, reason, now=None):
        session.execute('INSERT INTO financial_history_epoch_audit (business_id,epoch_uuid,audit_uuid,action,recorded_by,recorded_at,reason) VALUES (?,?,?,?,?,?,?)',
                        (self.business_id, str(epoch_uuid), str(uuid4()), action, principal.user_id, now or stamp(), reason))
        log.info('historical %s business=%s epoch=%s', action, self.business_id, epoch_uuid)

    def open(self, principal, epoch_uuid, *, repository_version, environment_identity):
        epoch_uuid = uuid_text(epoch_uuid)
        version, environment = label(repository_version), label(environment_identity)
        with self._session(principal) as session:
            existing = session.execute('SELECT * FROM financial_history_epochs WHERE business_id=? AND epoch_uuid=?',
                                       (self.business_id, epoch_uuid)).fetchone()
            if existing:
                if (existing['opened_by'] != principal.user_id or existing['created_from_repository_version'] != version
                        or existing['environment_identity'] != environment or existing['source_scope_canonical'] != canonical(SCOPE)):
                    raise ConflictError('Retry de epoch con otra identidad/operador/scope/código/entorno.')
                return existing  # No nuevo T0, tampoco revive released/invalidated.
            lock = ' FOR UPDATE' if session.dialect == 'postgres' else ''
            control = session.execute('SELECT * FROM financial_history_control WHERE business_id=?'+lock, (self.business_id,)).fetchone()
            if control and control['fence_enabled']:
                raise ConflictError('Existe otro epoch activo del negocio.')
            generation = 1 if not control else control['generation'] + 1
            # Clock tomado DESPUÉS de permisos/gate/control, jamás transaction_timestamp/MAX(id).
            now = stamp()
            session.execute("""INSERT INTO financial_history_epochs
                (business_id,epoch_uuid,generation,state,opened_by,opened_at,t0,fence_enabled,fence_version,source_scope_version,
                 source_scope_canonical,created_from_repository_version,environment_identity,updated_at)
                VALUES (?,?,?,'fenced',?,?,?,TRUE,1,1,?,?,?,?)""",
                (self.business_id, epoch_uuid, generation, principal.user_id, now, now, canonical(SCOPE), version, environment, now))
            session.execute('INSERT INTO financial_history_control (business_id,epoch_uuid,generation,fence_enabled,fence_version,updated_at) '
                'VALUES (?,?,?,TRUE,1,?) ON CONFLICT(business_id) DO UPDATE SET epoch_uuid=excluded.epoch_uuid,generation=excluded.generation,fence_enabled=TRUE,updated_at=excluded.updated_at',
                (self.business_id, epoch_uuid, generation, now))
            self._audit(session, epoch_uuid, principal, 'opened', 'fence_enabled', now)
            log.info('historical T0 business=%s generation=%s t0=%s fence=enabled', self.business_id, generation, now)
            return self._row(session, epoch_uuid, principal)

    def read(self, principal, epoch_uuid, *, attention_after=timedelta(minutes=30)):
        if not isinstance(attention_after, timedelta) or attention_after <= timedelta(0):
            raise ValueError('TTL de atención positivo requerido.')
        with self._session(principal) as session:
            row = dict(self._row(session, epoch_uuid, principal))
            opened = datetime.fromisoformat(str(row['opened_at']))
            row['attention_required'] = bool(row['fence_enabled'] and datetime.now(timezone.utc)-opened > attention_after)
            control = session.execute('SELECT * FROM financial_history_control WHERE business_id=?', (self.business_id,)).fetchone()
            row['boundary_current'] = bool(row['state'] == 'fenced' and row['fence_enabled'] and control
                and control['fence_enabled'] and str(control['epoch_uuid']) == str(row['epoch_uuid'])
                and control['generation'] == row['generation'])
            return row

    def _end(self, principal, epoch_uuid, reason, *, release):
        epoch_uuid, reason = uuid_text(epoch_uuid), label(reason)
        with self._session(principal) as session:
            row = self._row(session, epoch_uuid, principal)
            state = 'released' if release else 'invalidated'
            if row['state'] == state:
                if row['release_reason' if release else 'invalidation_reason'] != reason:
                    raise ConflictError('Retry de transición con otro motivo.')
                return row
            if row['state'] == 'released':
                raise EpochUnavailable('Un epoch liberado no se reactiva ni invalida retrospectivamente.')
            now = stamp()
            if release:
                session.execute("UPDATE financial_history_epochs SET state='released',fence_enabled=FALSE,released_at=?,released_by=?,release_reason=?,updated_at=? WHERE business_id=? AND epoch_uuid=?",
                                (now, principal.user_id, reason, now, self.business_id, epoch_uuid))
            else:
                session.execute("UPDATE financial_history_epochs SET state='invalidated',invalidated_at=?,invalidated_by=?,invalidation_reason=?,updated_at=? WHERE business_id=? AND epoch_uuid=?",
                                (now, principal.user_id, reason, now, self.business_id, epoch_uuid))
            # El trigger71 revoca boundary/certificado y sincroniza control en esta TX.
            self._audit(session, epoch_uuid, principal, state, reason, now)
            return self._row(session, epoch_uuid, principal)

    def invalidate(self, principal, epoch_uuid, *, reason):
        return self._end(principal, epoch_uuid, reason, release=False)

    def release(self, principal, epoch_uuid, *, reason):
        return self._end(principal, epoch_uuid, reason, release=True)

    def inventory(self, principal, epoch_uuid, manifest_uuid, *, repository_version, environment_identity):
        scanner = _CutInventory(self.business_id, epoch_uuid, page_size=self.page_size)
        try:
            scanner.run(principal, manifest_uuid, repository_version=label(repository_version),
                        environment_identity=label(environment_identity))
        except (EpochUnavailable, AccessDenied, ConflictError):
            raise  # Explicit invalidation/release conserva los parciales y marca BLOCKED.
        except Exception:
            # Crash (BaseException/process kill) NO libera/invalida automáticamente.
            if scanner.started:
                self.invalidate(principal, epoch_uuid, reason='inventory_error')
            raise
        with self._session(principal) as session:
            return session.execute('SELECT * FROM financial_history_cut_manifests WHERE business_id=? AND manifest_uuid=?',
                                   (self.business_id, uuid_text(manifest_uuid))).fetchone()


class _CutInventory(HistoryDiagnostics):
    def __init__(self, business_id, epoch_uuid, **kwargs):
        super().__init__(business_id, **kwargs)
        self.epoch_uuid = uuid_text(epoch_uuid)
        self.cutoff = HistoryCutoff(business_id)
        self.started = False

    @contextmanager
    def _session(self, principal):
        with self.cutoff._session(principal) as session:
            self.cutoff._row(session, self.epoch_uuid, principal, active=True)
            yield session

    def _reader(self, session):
        from .readers import RawReader
        return RawReader(session, self.business_id, page_size=self.page_size, cut_scope=True)

    def _create(self, session, principal, manifest_uuid, repository_version, environment_identity):
        from .repository import HistoryRepository
        if migrations.current_version_connection(session.borrowed_connection) not in (71, 72):
            raise ValueError('Schema71 requerido para certifiable_inventory.')
        epoch = self.cutoff._row(session, self.epoch_uuid, principal, active=True)
        if epoch['environment_identity'] != environment_identity:
            raise ConflictError('Entorno explícito distinto al epoch.')
        repo = HistoryRepository(session, self.business_id, manifest_uuid)
        existing = repo.load()
        cut = session.execute('SELECT * FROM financial_history_cut_manifests WHERE business_id=? AND manifest_uuid=?', repo.scope).fetchone()
        if existing and (not cut or str(cut['epoch_uuid']) != self.epoch_uuid):
            raise ConflictError('No promover diagnóstico ni reutilizar manifest de otro corte.')
        now = stamp() if not existing else existing['started_at']
        manifest = repo.create(principal, repository_version, environment_identity, now)
        if not cut:
            session.execute("""INSERT INTO financial_history_cut_manifests
                (business_id,manifest_uuid,epoch_uuid,generation,mode,source_scope_version,source_scope_canonical,
                 environment_identity,t0,started_at,status,certifiable,eligible_for_import,boundary_current)
                VALUES (?,?,?,?,'certifiable_inventory',1,?,?,?,?,'scanning',FALSE,FALSE,TRUE)""",
                (*repo.scope, self.epoch_uuid, epoch['generation'], canonical(SCOPE), environment_identity, epoch['t0'], now))
        self.started = True
        return manifest

    def _complete(self, principal, manifest_uuid, comparison_hash, retry_drift):
        from .repository import HistoryRepository
        from .contracts import IncidenceCode
        # Cada SELECT paginado valida epoch/control con TX propia. No gate del scan.
        class Pages:
            def execute(inner, sql, params=()):
                with self._session(principal) as page_session:
                    cursor = page_session.execute(sql, params)
                    rows = cursor.fetchall() if sql.lstrip().upper().startswith("SELECT") else []
                class Detached:
                    def fetchall(self):
                        return rows
                    def fetchone(self):
                        return rows[0] if rows else None
                return Detached()
        computed = HistoryRepository(Pages(), self.business_id, manifest_uuid)
        if retry_drift:
            row = computed.session.execute('SELECT item_uuid,raw_hash FROM financial_history_items WHERE business_id=? AND manifest_uuid=? ORDER BY item_uuid LIMIT 1', computed.scope).fetchone()
            if row:
                computed.incidence(str(row['item_uuid']), IncidenceCode.SOURCE_DRIFT, row['raw_hash'])
        values = computed.build_finish(comparison_hash)
        with self._session(principal) as session:
            repo = HistoryRepository(session, self.business_id, manifest_uuid)
            existing = session.execute('SELECT * FROM financial_history_cut_manifests WHERE business_id=? AND manifest_uuid=?', repo.scope).fetchone()
            if existing['status'] == 'frozen':
                return repo.load()
            manifest = repo.freeze(values)
            no_drift = not session.execute("SELECT 1 FROM financial_history_incidences WHERE business_id=? AND manifest_uuid=? AND code='SOURCE_DRIFT' LIMIT 1", repo.scope).fetchone()
            consistent = no_drift and manifest['source_set_hash'] == comparison_hash
            session.execute("UPDATE financial_history_cut_manifests SET status='frozen',result=?,certifiable=?,source_set_hash=?,comparison_source_set_hash=?,plan_hash=?,completed_at=? WHERE business_id=? AND manifest_uuid=? AND status='scanning'",
                (manifest['result'], consistent, manifest['source_set_hash'], comparison_hash, manifest['plan_hash'], stamp(), *repo.scope))
            self.cutoff._audit(session, self.epoch_uuid, principal, 'manifest_frozen', 'consistent' if consistent else 'source_drift')
        if not consistent:
            self.cutoff.invalidate(principal, self.epoch_uuid, reason='source_drift')
        return manifest
