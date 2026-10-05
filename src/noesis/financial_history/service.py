"""Dry-run explícito interno: solo persiste diagnóstico; ningún canal conectado."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import AccessDenied, Principal, positive_id, uuid_text
from .canonical import instant, sha256
from .classifier import DiagnosticContext, classify
from .contracts import DecisionKind, EvidenceReference, ReasonCode
from .readers import RawReader
from .repository import HistoryRepository, canonical, hash_source, stamp
from .review import ReviewRecord
from .sources import PRIMARY, SOURCES


FLAGS = ('FINANCIAL_CORE_ENABLED','LEDGER_REPORTING_ENABLED','OPEN_ITEMS_ENABLED',
         'NEW_TAX_ENGINE_ENABLED','NEW_BANK_RECONCILIATION_ENABLED')


class HistoryDiagnostics:
    """Una UUID explícita identifica el run, nunca el reloj ni una autorización."""

    def __init__(self, business_id, *, page_size=64):
        self.business_id = positive_id(business_id)
        if type(page_size) is not int or not 1 <= page_size <= 64:
            raise ValueError('Página diagnóstica de1 a64 requerida.')
        self.page_size = page_size

    def _permission(self, session, principal):
        if not isinstance(principal, Principal):
            raise AccessDenied('Operador autenticado requerido para historical.record.')
        user = session.execute('SELECT id,is_active,session_version FROM users WHERE business_id=? AND id=?',
                               (self.business_id, principal.user_id)).fetchone()
        if not user or not user['is_active'] or user['session_version'] != principal.session_version:
            raise AccessDenied('Permiso historical.record denegado.')
        business = session.execute('SELECT subscription_status,trial_ends_at,is_demo FROM businesses WHERE id=?',
                                   (self.business_id,)).fetchone()
        if business and hasattr(business['trial_ends_at'],'isoformat'):
            business['trial_ends_at'] = business['trial_ends_at'].isoformat()
        if not business or not db.subscription_allows_access(business):
            raise AccessDenied('El negocio en modo consulta no puede registrar nuevos diagnósticos.')
        # Permiso interno de registrar diagnóstico: no financial.authorize ni receipt.
        if any(getattr(config, flag) for flag in FLAGS):
            raise AccessDenied('La unidad1.9B requiere los cinco flags apagados.')

    @contextmanager
    def _session(self, principal):
        with db.get_conn() as connection:
            session = FinancialSession(connection)
            self._permission(session, principal)
            yield session

    def run(self, principal, manifest_uuid, *, repository_version, environment_identity=None):
        """Retry recupera el mismo plan congelado; otra UUID solicita otro diagnóstico.

        TXs cortas por página. Sin gate/fence de negocio ni locks de sources.
        Lecturas débiles y comparación de conjuntos, nunca T0 certificable.
        """
        manifest_uuid = uuid_text(manifest_uuid)
        if not isinstance(repository_version, str) or not 1 <= len(repository_version) <= 128:
            raise ValueError('Versión del código explícita requerida.')
        if environment_identity is not None and (not isinstance(environment_identity, str) or len(environment_identity) > 128):
            raise ValueError('Identidad de copia acotada requerida, sin credenciales/URLs.')
        with self._session(principal) as session:
            manifest = self._create(session, principal, manifest_uuid, repository_version, environment_identity)
        if manifest['status'] == 'frozen':
            return manifest
        observed_at = instant(datetime.fromisoformat(str(manifest['started_at'])))
        retry_drift = False
        if manifest['status'] == 'scanning':
            for kind in sorted(SOURCES):
                after = None
                while True:
                    with self._session(principal) as session:
                        sources = self._reader(session).page(kind, after)
                        if not sources:
                            break
                        retry_drift |= HistoryRepository(session, self.business_id, manifest_uuid).insert_sources(sources)
                        after = sources[-1].key
            with self._session(principal) as session:
                session.execute("UPDATE financial_history_manifests SET status='planning' WHERE business_id=? AND manifest_uuid=? AND status='scanning'",
                                (self.business_id, manifest_uuid))
        order = [('invoice','issuance'),('invoice','rectification'),('invoice_payment','payment'),
                 ('bank_transaction','import'),('bank_transaction','match'),('received_invoice','observed'),
                 ('expense','observed'),('invoice_cancellation_record','cancellation')]
        order += [(kind,'evidence') for kind in sorted(SOURCES) if kind not in PRIMARY]
        for kind, slot in order:
            after = ''
            while True:
                with self._session(principal) as session:
                    repo = HistoryRepository(session, self.business_id, manifest_uuid)
                    rows = repo.page(kind, slot, after=after, page_size=self.page_size)
                    if not rows:
                        break
                    pending = tuple(row for row in rows if row['terminal_result'] is None)
                    if pending:
                        self._plan(repo, pending, kind, slot, observed_at)
                    after = rows[-1]['source_key']
        # Segundo recorrido paginado por conexión/lectura. Compara membership y raw.
        comparison = hashlib.sha256(canonical({'scope_version':1,'reader_version':1}).encode())
        for kind in sorted(SOURCES):
            after = None
            while True:
                with self._session(principal) as session:
                    sources = self._reader(session).page(kind, after)
                if not sources:
                    break
                for source in sources:
                    hash_source(comparison, source)
                after = sources[-1].key
        return self._complete(principal, manifest_uuid, comparison.hexdigest(), retry_drift)

    def _complete(self, principal, manifest_uuid, comparison_hash, retry_drift):
        with self._session(principal) as session:
            repo = HistoryRepository(session, self.business_id, manifest_uuid)
            if retry_drift:
                from .contracts import IncidenceCode
                row = session.execute('SELECT item_uuid,raw_hash FROM financial_history_items WHERE business_id=? AND manifest_uuid=? ORDER BY item_uuid LIMIT 1', repo.scope).fetchone()
                if row:
                    repo.incidence(str(row['item_uuid']), IncidenceCode.SOURCE_DRIFT, row['raw_hash'])
            return self._finish(session, repo, comparison_hash, principal)

    def _create(self, session, principal, manifest_uuid, repository_version, environment_identity):
        if migrations.current_version_connection(session.borrowed_connection) not in (70, 71, 72, 73):
            raise ValueError('Esquema70/71 requerido para diagnóstico1.9B.')
        return HistoryRepository(session, self.business_id, manifest_uuid).create(
            principal, repository_version, environment_identity, stamp())

    def _reader(self, session):
        return RawReader(session, self.business_id, page_size=self.page_size)

    def _finish(self, session, repo, comparison_hash, principal):
        return repo.finish(comparison_hash)

    def _plan(self, repo, rows, kind, slot, observed_at):
        context = repo.context(rows) if kind in PRIMARY else DiagnosticContext()
        if not context.complete and len(rows)>1:
            middle = len(rows)//2
            self._plan(repo,rows[:middle],kind,slot,observed_at)
            self._plan(repo,rows[middle:],kind,slot,observed_at)
            return
        from noesis.economic_events.contracts import EventType
        for row in rows:
            event_type = None if row['proposed_event_type'] is None else EventType(row['proposed_event_type'])
            result = classify(repo.raw(row),slot,event_type,context,observed_at)
            repo.record_result(row,result)

    def review(self, principal, manifest_uuid, incidence_uuid, *, decision_uuid, decision_type,
               evidence=(), reason_code=ReasonCode.INCIDENCE, interpretation_hash=None, previous_decision_uuid=None):
        """Registro de revisión append-only. Nunca resuelve/reclasifica el plan."""
        uid, incidence_uuid, decision_uuid = map(uuid_text, (manifest_uuid, incidence_uuid, decision_uuid))
        kind = DecisionKind(decision_type)
        reason = ReasonCode(reason_code)
        previous = None if previous_decision_uuid is None else uuid_text(previous_decision_uuid)
        with self._session(principal) as session:
            repo = HistoryRepository(session, self.business_id, uid)
            manifest = repo.load()
            if not manifest or manifest['status'] != 'frozen':
                raise AccessDenied('Manifest congelado del negocio requerido.')
            row = session.execute('SELECT * FROM financial_history_incidences WHERE business_id=? AND manifest_uuid=? AND incidence_uuid=?',
                                  (*repo.scope, incidence_uuid)).fetchone()
            if not row:
                raise AccessDenied('Incidencia del negocio requerida.')
            item = session.execute('SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND item_uuid=?',
                                   (*repo.scope, str(row['item_uuid']))).fetchone()
            repo.raw(item)
            self._evidence(session, tuple(evidence))
            decision = ReviewRecord(self.business_id,uid,str(row['item_uuid']),incidence_uuid,decision_uuid,
                principal.user_id,'historical.record',kind,tuple(evidence),reason,interpretation_hash,previous,datetime.now(timezone.utc))
            if previous and not session.execute('SELECT 1 FROM financial_history_decisions WHERE business_id=? AND manifest_uuid=? '
                'AND item_uuid=? AND incidence_uuid=? AND decision_uuid=?', (*repo.scope,str(row['item_uuid']),incidence_uuid,previous)).fetchone():
                raise AccessDenied('Decisión anterior incompatible.')
            existing = session.execute('SELECT * FROM financial_history_decisions WHERE business_id=? AND manifest_uuid=? AND decision_uuid=?',
                                       (*repo.scope,decision_uuid)).fetchone()
            values = dict(item_uuid=str(row['item_uuid']), incidence_uuid=incidence_uuid, recorded_by=principal.user_id,
                validated_permission='historical.record', decision_type=kind.value, evidence_canonical=canonical(decision.evidence),
                reason_code=reason.value, interpretation_hash=interpretation_hash, previous_decision_uuid=previous)
            if existing:
                if any(str(existing[k]) != str(v) for k,v in values.items()):
                    from noesis.financial_operations.contracts import ConflictError
                    raise ConflictError('Retry de decisión con otro contenido.')
                return existing
            fields = tuple(values)
            return session.execute('INSERT INTO financial_history_decisions (business_id,manifest_uuid,decision_uuid,'
                + ','.join(fields) + ',decided_at) VALUES (' + ','.join('?' for _ in range(len(fields)+4)) + ') RETURNING *',
                (*repo.scope,decision_uuid,*values.values(),stamp())).fetchone()

    def _evidence(self, session, references):
        # Ninguna referencia declarada puede aportar identidad ajena.
        mapping = {'document':('documents','id','content_sha256'), 'invoice_record':('invoice_records','id','record_hash'),
                   'invoice_cancellation_record':('invoice_cancellation_records','id','record_hash'),
                   'economic_event':('economic_events','event_uuid','content_hash')}
        for reference in references:
            if not isinstance(reference, EvidenceReference) or reference.business_id != self.business_id:
                raise AccessDenied('Referencia de otro negocio o no tipada.')
            if reference.kind.value not in mapping:
                alternate = {'document_profile':'document_profile','bank_payment_link':'bank_payment_link',
                             'recurring_invoice_run':'recurring_run'}
                source_kind = alternate[reference.kind.value]
                page = RawReader(session,self.business_id,page_size=1).page(source_kind,(reference.reference_id-1,))
                if not page or page[0].source_id!=str(reference.reference_id):
                    raise AccessDenied('Referencia durable ajena o ausente.')
                observed_hash = page[0].fields['profile_snapshot_hash'] if source_kind=='document_profile' else page[0].content_hash
                if observed_hash!=reference.evidence_hash:
                    raise AccessDenied('Hash de evidencia incompatible.')
                continue
            table, key, hash_column = mapping[reference.kind.value]
            found = session.execute(f'SELECT {hash_column} FROM {table} WHERE business_id=? AND {key}=?',
                                    (self.business_id,str(reference.reference_id) if table == 'economic_events' else reference.reference_id)).fetchone()
            if not found or found[hash_column] != sha256(reference.evidence_hash):
                raise AccessDenied('Hash/referencia durable incompatible.')
