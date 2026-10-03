"""Persistencia de diagnóstico sobre sesión prestada; no conexión propia."""

from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID, uuid5

from noesis.financial_operations.contracts import ConflictError, positive_id, uuid_text
from .canonical import canonical_bytes
from .classifier import DiagnosticContext, fact_slots, item_uuid, revision
from .contracts import (
    Assessment, ExistingCoverage, HistoricalIdentity, IncidenceCode, RevisionIdentity, Severity, SourceReference,
)
from .readers import RawSource
from .sources import SOURCES


def canonical(value):
    return canonical_bytes(value).decode('utf-8')


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def sort_key(source):
    # BIGINT positivos rellenados: orden textual indexado = orden PK numérico.
    return canonical(tuple(f'{key:020d}' if type(key) is int else key for key in source.key))


def field_expr(dialect, field):
    if field not in {f for s in SOURCES.values() for f in s.fields}:
        raise ValueError('Campo fuera del catálogo cerrado.')
    return (f"raw_canonical::jsonb#>>'{{value,fields,{field}}}'" if dialect == 'postgres' else
            f"CAST(json_extract(raw_canonical,'$.value.fields.{field}') AS TEXT)")


class HistoryRepository:
    def __init__(self, session, business_id, manifest_uuid):
        self.session = session
        self.business_id = positive_id(business_id)
        self.manifest_uuid = uuid_text(manifest_uuid)

    @property
    def scope(self):
        return self.business_id, self.manifest_uuid

    def load(self):
        return self.session.execute('SELECT * FROM financial_history_manifests WHERE business_id=? AND manifest_uuid=?', self.scope).fetchone()

    def create(self, principal, repository_version, environment_identity, observed_at):
        scope = canonical({'sources': sorted(SOURCES), 'scope_version': 1, 'mode': 'diagnostic'})
        self.session.execute("""INSERT INTO financial_history_manifests
            (business_id,manifest_uuid,schema_version,repository_version,reader_version,classifier_version,canonical_version,
             scope_version,scope_canonical,environment_identity,created_by,validated_permission,started_at,status)
            VALUES (?,?,70,?,1,1,1,1,?,?,?,'historical.record',?,'scanning')
            ON CONFLICT(business_id,manifest_uuid) DO NOTHING""",
            (*self.scope, repository_version, scope, environment_identity, principal.user_id, observed_at))
        manifest = self.load()
        if (manifest['created_by'] != principal.user_id or manifest['scope_canonical'] != scope
                or manifest['repository_version'] != repository_version or manifest['environment_identity'] != environment_identity):
            raise ConflictError('Retry con distinto operador/código/scope/copia. Crear nuevo manifest.')
        return manifest

    def insert_sources(self, sources):
        drift = False
        ids = [item_uuid(source,slot) for source in sources for slot,_ in fact_slots(source)]
        existing = self.session.execute('SELECT item_uuid,raw_hash FROM financial_history_items WHERE business_id=? AND manifest_uuid=? '
            + 'AND item_uuid IN (' + ','.join('?' for _ in ids) + ')', (*self.scope,*ids)).fetchall() if ids else ()
        previous = {str(row['item_uuid']):row['raw_hash'] for row in existing}
        for source in sources:
            for slot, event in fact_slots(source):
                uid = item_uuid(source, slot)
                if uid in previous:
                    drift |= previous[uid] != source.content_hash
                    continue
                self.session.execute("""INSERT INTO financial_history_items
                    (business_id,manifest_uuid,item_uuid,source_type,source_id,source_key,source_sort_key,revision_canonical,fact_slot,
                     proposed_event_type,raw_canonical,raw_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (*self.scope, uid, source.source_kind, source.source_id, canonical(source.key),sort_key(source),revision(source).canonical_bytes().decode(),
                     slot, None if event is None else event.value, source.canonical_bytes().decode(), source.content_hash))
        return drift

    def page(self, kind, slot, *, after='', page_size=64):
        return self.session.execute('SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND '
            'source_type=? AND fact_slot=? AND source_key>? ORDER BY source_key LIMIT ?',
            (*self.scope, kind, slot, after, page_size)).fetchall()

    def raw(self, row):
        source = RawSource.from_canonical(row['raw_canonical'])
        if source.business_id != self.business_id or source.content_hash != row['raw_hash']:
            raise ValueError('Raw/hash/tenant incoherentes; no reparar.')
        return source

    def find(self, kind, field, values):
        values = tuple(sorted({str(v) for v in values if v is not None}))
        if not values:
            return ()
        if len(values) > 256:
            raise ValueError('Lookup requiere lotes de máximo256 claves.')
        # Solo la primera representación raw de una source: bancos pueden tener dos slots.
        rows = self.session.execute(f"SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND source_type=? "
            f"AND {field_expr(self.session.dialect, field)} IN ({','.join('?' for _ in values)}) "
            "AND fact_slot<>'match' ORDER BY source_key LIMIT 257", (*self.scope, kind, *values)).fetchall()
        if len(rows) > 256:
            self.context_overflow = True
            rows = rows[:256]
        return rows

    def context(self, page):
        self.context_overflow = False
        sources = { (s.source_kind, canonical(s.key)): s for s in (self.raw(row) for row in page) }
        parents = {}
        coverages = {}
        def add(kind, field, values):
            found = self.find(kind, field, values)
            for row in found:
                source = self.raw(row)
                sources[(source.source_kind, canonical(source.key))] = source
                if row['assessment_canonical']:
                    parents[f"{kind}:{source.source_id}:{row['fact_slot']}"] = Assessment(**json.loads(row['assessment_canonical'])['value'])
                if row['existing_coverage_canonical']:
                    value = json.loads(row['existing_coverage_canonical'])['value']
                    ident = value['identity']
                    value['identity'] = HistoricalIdentity(SourceReference(**ident['source']),RevisionIdentity(**ident['revision']),
                        ident['event_type'],ident['fact_slot'],ident['derivation_version'])
                    coverages[f"{kind}:{source.source_id}:{row['fact_slot']}"] = ExistingCoverage(**value)
            return tuple(self.raw(row) for row in found)
        active = tuple(sources.values())
        invoices = {s.fields.get('invoice_id') for s in active} | {s.fields.get('rectifies_invoice_id') for s in active}
        invoices |= {int(s.source_id) for s in active if s.source_kind == 'invoice'}
        banks = {int(s.source_id) for s in active if s.source_kind == 'bank_transaction'}
        links = add('bank_payment_link', 'bank_transaction_id', banks)
        payments = add('invoice_payment', 'id', {s.fields['payment_id'] for s in links})
        invoices |= {s.fields['invoice_id'] for s in payments}
        add('invoice', 'id', invoices)
        add('invoice_payment', 'invoice_id', invoices)
        for kind in ('invoice_line', 'invoice_record', 'invoice_coverage', 'recurring_run', 'verifactu_transport', 'cancellation_transport'):
            add(kind, 'invoice_id', invoices)
        add('invoice_record', 'id', {s.fields.get('original_record_id') for s in active})
        add('document_profile', 'id', {s.fields.get('document_profile_id') for s in sources.values()})
        add('invoice_series', 'id', {s.fields.get('series_id') for s in sources.values()})
        for key, coverage in (('invoice_payment','payment_coverage'),('bank_transaction','bank_import_coverage'),
                              ('bank_transaction','bank_match_coverage'),('received_invoice','supplier_coverage'),('expense','expense_coverage')):
            column = {'invoice_payment':'payment_id','bank_transaction':'bank_transaction_id'}.get(key, 'source_id')
            add(coverage, column, {int(s.source_id) for s in sources.values() if s.source_kind == key})
        for kind, column in (('invoice','invoice_id'), ('received_invoice','received_invoice_id'), ('expense','expense_id')):
            docs = add('document', column, {int(s.source_id) for s in sources.values() if s.source_kind == kind})
            add('document_classification', 'document_id', {int(d.source_id) for d in docs})
        add('supplier', 'id', {s.fields.get('supplier_id') for s in sources.values()})
        # Dedupe por kind/id: links y coberturas compuestas pueden tener múltiples revisiones.
        events = add('economic_event', 'source_id', {int(s.source_id) for s in sources.values() if s.source_kind in (
            'invoice','invoice_payment','bank_transaction','received_invoice','expense','invoice_cancellation_record')})
        event_links = add('economic_event_link', 'event_uuid', {e.fields['event_uuid'] for e in events})
        add('economic_event', 'event_uuid', {e.fields['target_event_uuid'] for e in event_links})
        # Dependencia import del mismo banco requiere su assessment original.
        for row in self.find('bank_transaction', 'id', banks):
            if row['assessment_canonical']:
                parents[f"bank_transaction:{row['source_id']}:import"] = Assessment(**json.loads(row['assessment_canonical'])['value'])
        return DiagnosticContext(tuple(sources.values()), parents, not self.context_overflow, coverages)

    def record_result(self, row, result):
        candidate = result.candidate
        self.session.execute("""UPDATE financial_history_items SET assessment_canonical=?,classification=?,disposition=?,severity=?,
            rule_id=?,rule_version=?,candidate_canonical=?,candidate_hash=?,dependency_canonical=?,unresolved_dependency_canonical=?,existing_coverage_canonical=?,terminal_result=?
            WHERE business_id=? AND manifest_uuid=? AND item_uuid=? AND terminal_result IS NULL""", (
            result.assessment.canonical_bytes().decode(), result.assessment.classification.value, result.assessment.disposition.value,
            result.assessment.severity.value, result.assessment.rule_id.value, result.assessment.rule_version,
            None if candidate is None else candidate.canonical_bytes().decode(), None if candidate is None else candidate.content_hash,
            canonical(result.dependencies),canonical(result.unresolved_dependencies), None if result.existing_coverage is None else result.existing_coverage.canonical_bytes().decode(),
            result.terminal_result, *self.scope, str(row['item_uuid'])))
        for code in result.incidences:
            self.incidence(str(row['item_uuid']), code, row['raw_hash'], result.assessment.severity)

    def incidence(self, uid, code, evidence_hash, severity=Severity.BLOCKING):
        incidence_uuid = str(uuid5(UUID(uid), IncidenceCode(code).value))
        self.session.execute("""INSERT INTO financial_history_incidences
            (business_id,manifest_uuid,item_uuid,incidence_uuid,code,severity,evidence_hash,rule_version,status,created_at)
            VALUES (?,?,?,?,?,?,?,1,'open',?) ON CONFLICT(business_id,manifest_uuid,item_uuid,code) DO NOTHING""",
            (*self.scope, uid, incidence_uuid, IncidenceCode(code).value, Severity(severity).value, evidence_hash, stamp()))

    def ordered_sources(self, kind, after=None, page_size=64):
        sql = 'SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND source_type=? AND fact_slot<>\'match\''
        params = [*self.scope, kind]
        if after is not None:
            sql += ' AND source_sort_key>?'
            params.append(after)
        sql += ' ORDER BY source_sort_key LIMIT ?'
        params.append(page_size)
        return self.session.execute(sql, tuple(params)).fetchall()

    def source_set_hash(self):
        digest = hashlib.sha256(canonical({'scope_version':1,'reader_version':1}).encode())
        for kind in sorted(SOURCES):
            after = None
            while rows := self.ordered_sources(kind, after):
                for row in rows:
                    source = self.raw(row)
                    hash_source(digest, source)
                    after = row['source_sort_key']
        return digest.hexdigest()

    def finish(self, comparison_hash):
        if self.session.execute('SELECT 1 FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND terminal_result IS NULL LIMIT 1', self.scope).fetchone():
            raise ValueError('No congelar plan incompleto.')
        source_hash = self.source_set_hash()
        if comparison_hash != source_hash:
            row = self.session.execute('SELECT item_uuid,raw_hash FROM financial_history_items WHERE business_id=? AND manifest_uuid=? ORDER BY source_type,source_key,fact_slot LIMIT 1', self.scope).fetchone()
            if row:
                self.incidence(str(row['item_uuid']), IncidenceCode.SOURCE_DRIFT, row['raw_hash'])
        manifest = self.load()
        plan = hashlib.sha256(canonical({'scope':json.loads(manifest['scope_canonical']), 'classifier_version':1,'canonical_version':1}).encode())
        summary = {'classification':dict.fromkeys(('A','B','C','D'),0),
                   'disposition':dict.fromkeys(('candidate','covered_existing','out_of_scope','excluded','pending_incidence'),0),
                   'terminal_result':{}, 'candidates':{}, 'sources':dict.fromkeys(SOURCES,0),
                   'incidences':{}, 'dependencies':0, 'broken_dependencies':0, 'items':0,
                   'mode':'diagnostic', 'eligible_for_import':False, 'certifiable':False}
        after = '00000000-0000-0000-0000-000000000000'
        while rows := self.session.execute('SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? '
            'AND item_uuid>? ORDER BY item_uuid LIMIT 64', (*self.scope, after)).fetchall():
            incidence_rows = self.session.execute('SELECT item_uuid,code,severity,evidence_hash,rule_version FROM financial_history_incidences '
                'WHERE business_id=? AND manifest_uuid=? AND item_uuid IN (' + ','.join('?' for _ in rows) + ') ORDER BY item_uuid,code',
                (*self.scope,*(str(row['item_uuid']) for row in rows))).fetchall()
            grouped = {}
            for incidence in incidence_rows:
                grouped.setdefault(str(incidence['item_uuid']), []).append({k:incidence[k] for k in ('code','severity','evidence_hash','rule_version')})
            for row in rows:
                after = str(row['item_uuid'])
                incs = grouped.get(after,[])
                plan.update(canonical({key: row[key] for key in ('item_uuid','revision_canonical','raw_hash','assessment_canonical',
                    'disposition','candidate_hash','dependency_canonical','unresolved_dependency_canonical','existing_coverage_canonical','terminal_result')} | {'incidences':incs}).encode())
                summary['items'] += 1
                for axis in ('classification','disposition','terminal_result'):
                    summary[axis][row[axis]] = summary[axis].get(row[axis],0) + 1
                if row['candidate_hash']:
                    candidate = json.loads(row['candidate_canonical'])['value']['event_payload']
                    key = candidate['event_type'] + '/v' + str(candidate['payload_version'])
                    summary['candidates'][key] = summary['candidates'].get(key,0) + 1
                if row['fact_slot'] != 'match':
                    summary['sources'][row['source_type']] = summary['sources'].get(row['source_type'],0) + 1
                dependencies = json.loads(row['dependency_canonical'])
                summary['dependencies'] += len(dependencies)
                summary['broken_dependencies'] += sum(d['parent_assessment'] is None or d['parent_assessment']['classification'] != 'A'
                    or d['parent_assessment']['severity'] == 'blocking' for d in dependencies)
                unresolved = json.loads(row['unresolved_dependency_canonical'])
                summary['dependencies'] += len(unresolved)
                summary['broken_dependencies'] += len(unresolved)
                for inc in incs:
                    summary['incidences'][inc['code']] = summary['incidences'].get(inc['code'],0) + 1
        summary['raw_money_problems'] = {code:summary['incidences'].get(code,0) for code in (
            'MONEY_BINARY_UNCORROBORATED','MONEY_SUBCENT','REQUIRED_VALUE_UNKNOWN')}
        summary['fiscal_discrepancies'] = summary['incidences'].get('FISCAL_AMOUNT_MISMATCH',0)
        blocking_incidence = self.session.execute("SELECT 1 FROM financial_history_incidences WHERE business_id=? AND manifest_uuid=? AND severity='blocking' LIMIT 1",self.scope).fetchone()
        blocked = (comparison_hash != source_hash or blocking_incidence or summary['terminal_result'].get('blocked',0)
                   or summary['terminal_result'].get('not_durably_supported',0) or summary['broken_dependencies'])
        now = stamp()
        self.session.execute("UPDATE financial_history_manifests SET status='frozen',result=?,source_set_hash=?,comparison_source_set_hash=?,"
            "plan_hash=?,summary_canonical=?,completed_at=?,frozen_at=? WHERE business_id=? AND manifest_uuid=? AND status='planning'",
            ('BLOCKED' if blocked else 'READY_FOR_REVIEW', source_hash, comparison_hash, plan.hexdigest(), canonical(summary), now, now, *self.scope))
        return self.load()


def hash_source(digest, source):
    digest.update(canonical({'source_type':source.source_kind,'key':source.key,'revision':revision(source),
                             'raw_hash':source.content_hash}).encode())
