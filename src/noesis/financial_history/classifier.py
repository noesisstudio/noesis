"""Reglas puras versionadas: raw tipado → plan diagnóstico, sin BD ni efectos."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Context, Decimal, localcontext
import hashlib
import struct

from noesis.core.money import Currency, MAX_AMOUNT, parse_money
from noesis.economic_events.contracts import CATALOG, EventType as ET, RelationType as RT, SourceType
from .canonical import CanonicalContract, canonical_bytes, freeze
from .contracts import (
    Assessment, Classification as CL, Disposition as DP, ExistingCoverage, HistoricalDates,
    HistoricalDependency, HistoricalIdentity, IncidenceCode as IC, LegacyDateKind,
    ReasonCode as RC, RevisionIdentity, RevisionKind, RuleId, Severity as SV, SourceReference,
)
from .money_evidence import CorroborationStatus as CS, MoneyReason as MR, StorageType
from .payloads import EventOrigin, EventPayload, EvidenceBasis, HISTORICAL_V2
from .planning import DiagnosticCandidate, InventoryEvidence
from .readers import RawSource
from .sources import PRIMARY


@dataclass(frozen=True, slots=True)
class DiagnosticContext:
    sources: tuple[RawSource, ...] = ()
    parents: Mapping = None
    complete: bool = True
    coverages: Mapping = None

    def __post_init__(self):
        if any(not isinstance(s, RawSource) for s in self.sources):
            raise TypeError('Contexto raw tipado requerido.')
        object.__setattr__(self, 'sources', tuple(self.sources))
        object.__setattr__(self, 'parents', freeze(self.parents or {}))
        object.__setattr__(self, 'coverages', freeze(self.coverages or {}))

    def find(self, kind, field, value):
        return tuple(s for s in self.sources if s.source_kind == kind and s.fields.get(field) == value)


@dataclass(frozen=True, slots=True)
class UnresolvedDependency(CanonicalContract):
    business_id: int
    relation: RT
    source_type: SourceType
    source_id: int | None
    reason: str = 'parent_or_revision_not_observed'

    def __post_init__(self):
        from noesis.financial_operations.contracts import positive_id
        positive_id(self.business_id)
        object.__setattr__(self,'relation',RT(self.relation))
        object.__setattr__(self,'source_type',SourceType(self.source_type))
        if self.source_id is not None:
            positive_id(self.source_id)
        if self.reason!='parent_or_revision_not_observed':
            raise ValueError('Razón de dependencia desconocida.')


@dataclass(frozen=True, slots=True)
class ClassificationResult(CanonicalContract):
    assessment: Assessment
    candidate: DiagnosticCandidate | None
    dependencies: tuple[HistoricalDependency, ...]
    incidences: tuple[IC, ...]
    existing_coverage: ExistingCoverage | None
    terminal_result: str
    unresolved_dependencies: tuple[UnresolvedDependency, ...] = ()


def fact_slots(source):
    kind = source.source_kind
    if kind == 'invoice':
        return (('rectification' if str(source.fields['invoice_type']).startswith('R') else 'issuance',
                 ET.INVOICE_RECTIFIED if str(source.fields['invoice_type']).startswith('R') else ET.INVOICE_ISSUED),)
    if kind == 'bank_transaction':
        result = [('import', ET.BANK_TRANSACTION_IMPORTED)]
        if source.fields['status'] == 'confirmed' or source.fields['suggested_invoice_id'] is not None:
            result.append(('match', ET.BANK_TRANSACTION_MATCHED))
        return tuple(result)
    mapping = {'invoice_payment': ('payment', ET.CUSTOMER_PAYMENT_RECEIVED),
               'received_invoice': ('observed', ET.SUPPLIER_INVOICE_CONFIRMED),
               'expense': ('observed', ET.EXPENSE_CONFIRMED),
               'invoice_cancellation_record': ('cancellation', ET.INVOICE_FISCAL_CANCELLATION_REGISTERED)}
    if kind in mapping:
        slot, event = mapping[kind]
        if source.fields.get('voided_at'):
            event = ET.SUPPLIER_INVOICE_VOIDED if kind == 'received_invoice' else ET.EXPENSE_VOIDED
        return ((slot, event),)
    return (('evidence', None),)


def revision(source):
    observed = source.fields.get('_financial_revision')
    if observed is not None:
        return RevisionIdentity(RevisionKind.OBSERVED_REVISION, observed, None)
    return RevisionIdentity(RevisionKind.IMMUTABLE_FINGERPRINT, int(source.content_hash[:15], 16) + 1, source.content_hash)


def identity(source, slot, event):
    return HistoricalIdentity(SourceReference(source.business_id, SourceType(source.source_kind), int(source.source_id)),
                              revision(source), event, slot)


def assess(raw_hash, category=CL.OBSERVED_STATE, disposition=DP.OUT_OF_SCOPE, code=None, severity=SV.INFO):
    reason = RC.INCIDENCE if disposition == DP.PENDING_INCIDENCE else RC(disposition.value) if disposition != DP.CANDIDATE else (
        RC.VERIFIED_FACT if category == CL.VERIFIED_HISTORY else RC.OBSERVED_STATE)
    return Assessment(category, disposition, severity, dict(zip(CL, RuleId, strict=True))[category],
                      1, reason, (raw_hash,), code)


def civil_dates(raw, observed_at):
    if raw is None or raw == '':
        return HistoricalDates(LegacyDateKind.UNKNOWN, None, None, None, None, observed_at, None)
    if len(raw) == 10:
        day = date.fromisoformat(raw)
        return HistoricalDates(LegacyDateKind.CIVIL_DATE, raw, day, day, None, observed_at, None)
    parsed = datetime.fromisoformat(raw)
    aware = parsed.tzinfo is not None and parsed.utcoffset() is not None
    return HistoricalDates(LegacyDateKind.AWARE_TIMESTAMP if aware else LegacyDateKind.NAIVE_TIMESTAMP,
                           raw, parsed.date(), parsed.date(), parsed if aware else None, observed_at, None)


def declared(observation, *, nullable=False):
    raw = observation.evidence
    if raw is None or raw.reason == MR.NON_FINITE:
        raise ValueError('Importe inválido/desconocido.')
    if raw.storage_type == StorageType.NULL:
        if nullable:
            return None
        raise ValueError('Importe obligatorio desconocido.')
    value = raw.exact_decimal if raw.corroboration == CS.EXACT else raw.corroborated_decimal
    if value is None:
        raise ValueError('Binario sin corroborar no declara Money.')
    final = parse_money(value)
    if not raw.validates_declared_amount(final):
        raise ValueError('Importe subcéntimo no contractual.')
    return final


def diagnostic_number(observation):
    raw = observation.evidence
    return None if raw is None else raw.exact_decimal if raw.exact_decimal is not None else raw.binary_decimal


def agrees(observation, text):
    """Compara contra decimal durable ya declarado; nunca deriva Money del binario."""
    raw = observation.evidence
    if text is None:
        return raw is not None and raw.storage_type == StorageType.NULL
    try:
        number = parse_money(text)
    except (ValueError, TypeError):
        return False
    if raw is None or raw.reason == MR.NON_FINITE:
        return False
    if raw.storage_type in (StorageType.REAL, StorageType.DOUBLE):
        return raw.binary_representation == struct.pack('!d', float(number)).hex() or (
            number.is_zero() and raw.binary_decimal == 0)
    return raw.exact_decimal == number


def _coverage(source, event_type, context):
    kind, fields = source.source_kind, source.fields
    coverage_kind, key = {
        'invoice': ('invoice_coverage', 'invoice_id'), 'invoice_payment': ('payment_coverage', 'payment_id'),
        'bank_transaction': ('bank_match_coverage' if event_type == ET.BANK_TRANSACTION_MATCHED else 'bank_import_coverage', 'bank_transaction_id'),
        'received_invoice': ('supplier_coverage', 'source_id'), 'expense': ('expense_coverage', 'source_id'),
        'invoice_cancellation_record': (None, None),
    }[kind]
    coverages = context.find(coverage_kind, key, int(source.source_id)) if coverage_kind else ()
    events = context.find('economic_event', 'source_id', int(source.source_id))
    events = tuple(e for e in events if e.fields['source_type'] == kind and e.fields['event_type'] == event_type.value)
    if kind in ('received_invoice', 'expense'):
        coverages = tuple(c for c in coverages if c.fields['source_revision'] == fields['_financial_revision'])
        events = tuple(e for e in context.find('economic_event', 'source_id', int(source.source_id))
            if e.fields['source_type'] == kind and e.fields['source_revision'] == fields['_financial_revision'])
        if any(not e.fields['canonical_event'].get('validated') for e in events):
            return None, True
        if events:
            event_type = ET(events[0].fields['event_type'])
    if not coverages and not events:
        return None, False
    if not coverages and len(events)==1 and events[0].fields['origin']=='historical' and event_type in HISTORICAL_V2:
        # Otra ejecución encuentra evidencia registrada por D. No promover B a A;
        # el importer comprobará además su intent/result/operación reales.
        e = events[0]
        try:
            ident = identity(source, fact_slots(source)[0][0], event_type)
            planned = _candidate(source,ident,event_type,context,datetime.fromisoformat(e.fields['observed_at']),())
            payload_digest = hashlib.sha256(canonical_bytes(planned.event_payload.payload)).hexdigest()
            valid = (e.fields['canonical_event'].get('validated') and e.fields['payload_version']==2
                     and e.fields['source_revision']==ident.revision.value and e.fields['event_uuid']==str(ident.event_uuid)
                     and e.fields['provenance']=='historical_import_v1' and e.fields['currency']=='EUR'
                     and e.fields['payload_canonical']['storage_hash']==payload_digest
                     and not context.find('economic_event_link','event_uuid',e.fields['event_uuid']))
            return (e,False) if valid else (None,True)
        except (ValueError,TypeError,KeyError,ArithmeticError):
            return None,True
    historical_v1 = False
    if not coverages and len(events)==1 and events[0].fields['origin']=='historical':
        # Solo evidencia D determinista. Los contrastes de payload/links/targets
        # siguientes siguen siendo obligatorios; D verifica además op/auth/result.
        f = events[0].fields
        ident = identity(source,fact_slots(source)[0][0],event_type)
        historical_v1 = (f['payload_version']==1 and f['provenance']=='historical_import_v1'
                         and f['source_revision']==ident.revision.value and f['event_uuid']==str(ident.event_uuid))
    if len(events) != 1 or (coverage_kind and len(coverages) != 1 and not historical_v1):
        return None, True
    e = events[0]
    f, payload = e.fields, e.fields['payload_canonical']
    if not f['canonical_event'].get('validated') or f['currency'] != 'EUR' or e.business_id != source.business_id:
        return None, True
    if coverages:
        c = coverages[0].fields
        if (c['event_uuid'] != f['event_uuid'] or c['event_type'] != f['event_type']
                or c['operation_state'] != 'committed' or c['operation_uuid'] != f['operation_uuid']):
            return None, True
        if kind == 'bank_transaction' and c['source_revision'] != f['source_revision']:
            return None, True
        if kind in ('invoice', 'invoice_payment'):
            fingerprint = payload.get('evidence', {}).get('source_fingerprint') if kind == 'invoice' else c['source_fingerprint']
            if not fingerprint or int(fingerprint[:15], 16) + 1 != f['source_revision']:
                return None, True
        if kind in ('received_invoice', 'expense'):
            snapshot = c['before_state'] if event_type in (ET.SUPPLIER_INVOICE_VOIDED, ET.EXPENSE_VOIDED) else c['after_state']
            if not isinstance(snapshot, Mapping):
                return None, True
            # El snapshot durable no concede autoridad, pero permite contraste monetario.
            for path, observation in source.money.items():
                if path != 'vat_rate' and not agrees(observation, snapshot.get(path)):
                    return None, True
    if event_type in (ET.SUPPLIER_INVOICE_CORRECTED,):
        payload = payload['after']
    elif event_type in (ET.SUPPLIER_INVOICE_VOIDED, ET.EXPENSE_VOIDED):
        payload = payload['before']
    money_map = {'expense': {'amount': 'total', '_captured_vat_amount': 'vat_amount'},
                 'invoice_cancellation_record': {}}.get(kind)
    if money_map is None:
        money_map = {p: p for p in source.money if p in ('base','vat_amount','irpf_amount','total','amount')}
    if any(not agrees(source.money[path], payload.get(target)) for path, target in money_map.items()):
        return None, True
    if kind == 'invoice':
        if payload.get('invoice_number') != fields['number'] or payload.get('invoice_kind') != fields['invoice_type']:
            return None, True
        if payload.get('issued_on') != str(fields['issued_at'])[:10]:
            return None, True
        evidence = payload.get('evidence')
        if evidence is not None:
            if evidence['invoice_id'] != int(source.source_id) or evidence['client_id'] != fields['client_id']:
                return None, True
            for party in ('issuer','recipient'):
                for key,value in evidence[party].items():
                    observed = fields.get(party+'_'+key)
                    # Legacy vacío de recipient se serializó como NULL al emitir.
                    if value != observed and not (party == 'recipient' and value is None
                            and observed == hashlib.sha256(b'').hexdigest()):
                        return None, True
            lines = context.find('invoice_line','invoice_id',int(source.source_id))
            actual_lines = {int(line.source_id):line for line in lines}
            if set(actual_lines) != {line['id'] for line in evidence['lines']}:
                return None, True
            for line in evidence['lines']:
                actual = actual_lines[line['id']]
                if (line['position'] != actual.fields['position'] or line['kind'] != actual.fields['kind']
                        or line['description_hash'] != actual.fields['description_hash']
                        or any(not agrees(actual.money[field],line[field]) for field in actual.money)):
                    return None, True
            profiles = context.find('document_profile','id',fields['document_profile_id'])
            if (len(profiles)!=1 or evidence['document_profile']['id']!=fields['document_profile_id']
                    or evidence['document_profile']['version']!=profiles[0].fields['version']
                    or evidence['document_profile']['content_hash']!=profiles[0].fields['profile_snapshot_hash']):
                return None, True
            series = context.find('invoice_series','id',fields['series_id'])
            if len(series)!=1 or any(evidence['series'][key]!=series[0].fields[key] for key in ('id','code','document_type')):
                return None, True
            if not agrees(source.money['irpf_rate'],evidence['irpf_rate']):
                return None, True
            records = context.find('invoice_record','invoice_id',int(source.source_id))
            fiscal = evidence['fiscal_record']
            if fiscal is None and records or fiscal is not None and (len(records)!=1 or records[0].fields['record_hash']!=fiscal['record_hash']
                    or records[0].fields['previous_hash']!=fiscal['previous_hash'] or not agrees(records[0].money['invoice_total'],fiscal['invoice_total'])
                    or not agrees(records[0].money['vat_total'],fiscal['vat_total'])):
                return None, True
    if kind == 'invoice_payment':
        if payload.get('invoice_id') != fields['invoice_id'] or payload.get('method') != fields['method'] or payload.get('received_on') != str(fields['paid_at'])[:10]:
            return None, True
    if kind == 'bank_transaction':
        if event_type == ET.BANK_TRANSACTION_IMPORTED and payload.get('booked_on') != fields['booked_on']:
            return None, True
        if event_type == ET.BANK_TRANSACTION_MATCHED:
            link = context.find('bank_payment_link', 'bank_transaction_id', int(source.source_id))
            if len(link) != 1 or link[0].fields['payment_id'] != payload.get('invoice_payment_id') or fields['status'] != 'confirmed':
                return None, True
    actual_links = context.find('economic_event_link', 'event_uuid', f['event_uuid'])
    rels = {(r.fields['relation_type'], r.fields['target_event_uuid']) for r in actual_links}
    declared_links = {(r['kind'], r['target_event_id']) for r in f['canonical_event']['relations']}
    if rels != declared_links or {r[0] for r in rels} != {r.kind.value for r in CATALOG[event_type].relations}:
        return None, True
    for relation, target in rels:
        target_event = context.find('economic_event', 'event_uuid', target)
        if len(target_event) != 1 or not target_event[0].fields['canonical_event'].get('validated'):
            return None, True
        rule = next(r for r in CATALOG[event_type].relations if r.kind.value == relation)
        if ET(target_event[0].fields['event_type']) not in rule.targets:
            return None, True
        target_fields = target_event[0].fields
        expected_id = None
        if relation==RT.RECTIFIES.value:
            expected_id = fields['rectifies_invoice_id']
        elif relation==RT.SETTLES.value or relation==RT.EVIDENCE_FOR.value and kind=='invoice_cancellation_record':
            expected_id = fields['invoice_id']
        elif relation==RT.MATCHES.value:
            expected_id = payload['invoice_payment_id']
        elif relation==RT.EVIDENCE_FOR.value and kind=='bank_transaction':
            expected_id = int(source.source_id)
        elif relation in (RT.CORRECTS.value,RT.VOIDS.value):
            expected_id = int(source.source_id)
            if (target_fields['source_type']!=kind or target_fields['source_revision']>=f['source_revision']
                    or not coverages or coverages[0].fields['antecedent_uuid']!=target):
                return None,True
            previous = context.find(coverage_kind,'source_id',expected_id)
            previous = tuple(c for c in previous if c.fields['source_revision']==target_fields['source_revision'])
            current_before = coverages[0].fields['before_state']
            if (len(previous)!=1 or current_before is None or previous[0].fields['after_state'] is None
                    or current_before['storage_hash']!=previous[0].fields['after_state']['storage_hash']):
                return None,True
        if expected_id is not None and target_fields['source_id']!=expected_id:
            return None,True
    return e, False


def _required_money(source, event):
    if source.source_kind == 'invoice':
        return ('base','vat_amount','irpf_amount','total')
    if source.source_kind == 'received_invoice':
        return ('base','vat_amount','irpf_amount','total')
    if source.source_kind in ('invoice_payment', 'bank_transaction', 'expense'):
        return ('amount',) if source.source_kind != 'expense' else ('amount', '_captured_vat_amount')
    return ()


def _money_problems(source, event):
    result = []
    nullable = {'base','vat_amount','irpf_amount','_captured_vat_amount'} if source.source_kind in ('received_invoice','expense') else set()
    for field in _required_money(source, event):
        observation = source.money[field]
        try:
            declared(observation, nullable=field in nullable)
        except (ValueError, TypeError, ArithmeticError):
            raw = observation.evidence
            code = IC.MONEY_SUBCENT if raw is not None and raw.reason == MR.SUBCENT else (
                IC.MONEY_BINARY_UNCORROBORATED if raw is not None and raw.storage_type in (StorageType.REAL, StorageType.DOUBLE)
                and raw.reason != MR.NON_FINITE else IC.REQUIRED_VALUE_UNKNOWN)
            number = diagnostic_number(observation)
            if number is not None and abs(number)>MAX_AMOUNT:
                code = IC.REQUIRED_VALUE_UNKNOWN
            result.append(code)
    return result


def classify(source, slot, event_type, context, observed_at):
    if not isinstance(source, RawSource) or not isinstance(context, DiagnosticContext):
        raise TypeError('Raw y contexto tipados requeridos.')
    if any(s.business_id != source.business_id for s in context.sources):
        raise ValueError('Contexto de otro negocio.')
    h, f, kind = source.content_hash, source.fields, source.source_kind
    if not context.complete:
        code = IC.SOURCE_HISTORY_LOST
        return ClassificationResult(assess(h, CL.AMBIGUOUS, DP.PENDING_INCIDENCE, code, SV.BLOCKING),
                                    None, (), (code,), None, 'blocked')
    if kind not in PRIMARY:
        codes = ()
        if kind == 'economic_event' and not f['canonical_event'].get('validated'):
            codes = (IC.EXISTING_EVENT_CONFLICT,)
        if kind in ('invoice_record','invoice_cancellation_record') and not f.get('fiscal_hash_valid'):
            codes = (IC.REQUIRED_VALUE_UNKNOWN,)
        if codes:
            return ClassificationResult(assess(h, CL.AMBIGUOUS, DP.PENDING_INCIDENCE, codes[0], SV.BLOCKING), None, (), codes, None, 'blocked')
        return ClassificationResult(assess(h), None, (), (), None, 'out_of_scope')
    if (slot, event_type) not in fact_slots(source):
        raise ValueError('Hecho no pertenece al catálogo de esta fuente.')
    ident = identity(source, slot, event_type)
    if kind == 'invoice' and f['status'] == 'borrador':
        return ClassificationResult(assess(h), None, (), (), None, 'out_of_scope')
    covered, conflict = _coverage(source, event_type, context)
    if covered:
        from dataclasses import replace
        historical = covered.fields['origin']=='historical'
        actual_identity = (ident if historical else replace(ident, event_type=ET(covered.fields['event_type']),
            revision=RevisionIdentity(RevisionKind.DURABLE_REVISION,covered.fields['source_revision'],None)))
        coverage = ExistingCoverage(actual_identity, covered.fields['event_uuid'], covered.fields['content_hash'], covered.fields['origin'])
        return ClassificationResult(assess(h, CL.OBSERVED_STATE if historical else CL.VERIFIED_HISTORY, DP.COVERED_EXISTING), None, (), (), coverage, 'covered_existing')
    codes = [IC.EXISTING_EVENT_CONFLICT] if conflict else _money_problems(source, event_type)
    warnings = []
    deps = []
    unresolved = []
    parent_specs = []
    if kind == 'invoice':
        records = context.find('invoice_record', 'invoice_id', int(source.source_id))
        lines = context.find('invoice_line', 'invoice_id', int(source.source_id))
        profiles = context.find('document_profile', 'id', f['document_profile_id'])
        if not records or not lines:
            codes.append(IC.SOURCE_HISTORY_LOST)
        if not profiles or profiles[0].fields['version'] == 1:
            codes.append(IC.MIGRATED_DOCUMENT_PROFILE)
        # Sin marcador, una única línea compatible con migración sigue UNKNOWN.
        if len(lines) == 1:
            codes.append(IC.SOURCE_HISTORY_LOST)
        for record in records:
            for a, b in (('vat_amount','vat_total'),('total','invoice_total')):
                left, right = diagnostic_number(source.money[a]), diagnostic_number(record.money[b])
                if left is not None and right is not None and left != right:
                    codes.append(IC.FISCAL_AMOUNT_MISMATCH)
        numbers = {key:diagnostic_number(source.money[key]) for key in ('base','vat_amount','irpf_amount','total')}
        if all(value is not None for value in numbers.values()):
            with localcontext(Context(prec=1200)):
                if abs(numbers['base']+numbers['vat_amount']-numbers['irpf_amount']-numbers['total']) > Decimal('0.000000001'):
                    codes.append(IC.FISCAL_AMOUNT_MISMATCH)
        if f['status'] == 'cobrada' and not context.find('invoice_payment', 'invoice_id', int(source.source_id)):
            codes.append(IC.PAID_WITHOUT_PAYMENT)
        if event_type == ET.INVOICE_RECTIFIED:
            parent_specs.append((RT.RECTIFIES, 'invoice', f['rectifies_invoice_id'], 'issuance'))
    elif kind == 'invoice_payment':
        if f['method'] == 'registro_anterior':
            codes.append(IC.SYNTHETIC_LEGACY_PAYMENT)
        siblings = context.find('invoice_payment', 'invoice_id', f['invoice_id'])
        parents = context.find('invoice', 'id', f['invoice_id'])
        if parents:
            values = [diagnostic_number(s.money['amount']) for s in siblings]
            total = diagnostic_number(parents[0].money['total'])
            if total is not None and values and all(v is not None for v in values):
                with localcontext(Context(prec=1200)):
                    # Contraste diagnóstico con margen de ULP, nunca reconocimiento.
                    if sum(values, Decimal(0)) - total > Decimal('0.000000001'):
                        codes.append(IC.PAYMENT_OVER_TOTAL)
        if len([s for s in siblings if s.fields['method'] == f['method'] and s.fields['paid_at'] == f['paid_at']
                and s.money['amount'].content_hash == source.money['amount'].content_hash]) > 1:
            codes.append(IC.POSSIBLE_DUPLICATE_PAYMENT)
        parent_specs.append((RT.SETTLES, 'invoice', f['invoice_id'], 'issuance'))
    elif kind == 'bank_transaction':
        if f['currency'] != 'EUR' or not f['import_hash'] or len(f['import_hash']) != 64:
            codes.append(IC.REQUIRED_VALUE_UNKNOWN)
        if event_type == ET.BANK_TRANSACTION_MATCHED:
            links = context.find('bank_payment_link', 'bank_transaction_id', int(source.source_id))
            payment_id = links[0].fields['payment_id'] if len(links) == 1 else None
            payment = context.find('invoice_payment', 'id', payment_id)
            if (f['status'] != 'confirmed' or len(payment) != 1 or not f['confirmed_at']
                    or payment[0].fields['invoice_id'] != f['suggested_invoice_id']):
                codes.append(IC.BANK_LINK_AMBIGUOUS)
            if payment and diagnostic_number(payment[0].money['amount']) != diagnostic_number(source.money['amount']):
                codes.append(IC.BANK_LINK_AMBIGUOUS)
            parent_specs += [(RT.MATCHES, 'invoice_payment', payment_id, 'payment'),
                             (RT.EVIDENCE_FOR, 'bank_transaction', int(source.source_id), 'import')]
    elif kind in ('received_invoice', 'expense'):
        if f.get('voided_at'):
            codes.append(IC.SOURCE_HISTORY_LOST)
        if f['_financial_revision'] > 1:
            # Solo estado observado; no generar secuencia de correcciones ausente.
            warnings.append(IC.SOURCE_HISTORY_LOST)
        if kind == 'received_invoice' and f['status'] not in ('pendiente','pagada'):
            codes.append(IC.REQUIRED_VALUE_UNKNOWN)
    elif kind == 'invoice_cancellation_record':
        original = context.find('invoice_record', 'id', f['original_record_id'])
        if (len(original) != 1 or original[0].fields['invoice_id'] != f['invoice_id'] or not f['reason']
                or not f['record_hash'] or len(f['record_hash']) != 64 or not f['fiscal_hash_valid']
                or not original[0].fields['fiscal_hash_valid'] or original[0].fields['invoice_number']!=f['invoice_number']
                or original[0].fields['issuer_nif_hash']!=f['issuer_nif_hash']):
            codes.append(IC.REQUIRED_VALUE_UNKNOWN)
        invoices = context.find('invoice','id',f['invoice_id'])
        if invoices:
            try:
                declared(invoices[0].money['total'])
            except (TypeError,ValueError,ArithmeticError):
                raw_total = invoices[0].money['total'].evidence
                codes.append(IC.MONEY_SUBCENT if raw_total is not None and raw_total.reason==MR.SUBCENT else IC.MONEY_BINARY_UNCORROBORATED)
        parent_specs.append((RT.EVIDENCE_FOR, 'invoice', f['invoice_id'], 'issuance'))
    for relation, parent_kind, parent_id, parent_slot in parent_specs:
        parents = context.find(parent_kind, 'id', parent_id)
        if not parents:
            codes.append(IC.RECTIFICATION_PARENT_MISSING if relation == RT.RECTIFIES else IC.REQUIRED_VALUE_UNKNOWN)
            unresolved.append(UnresolvedDependency(source.business_id,relation,SourceType(parent_kind),parent_id))
            continue
        parent = parents[0]
        if parent_kind == 'invoice':
            parent_slot, parent_event = fact_slots(parent)[0]
        else:
            parent_event = ET.CUSTOMER_PAYMENT_RECEIVED if parent_kind == 'invoice_payment' else ET.BANK_TRANSACTION_IMPORTED
        target = identity(parent, parent_slot, parent_event)
        coverage = context.coverages.get(f'{parent_kind}:{parent_id}:{parent_slot}')
        if coverage is not None:
            target = coverage.identity
        parent_assessment = context.parents.get(f'{parent_kind}:{parent_id}:{parent_slot}')
        deps.append(HistoricalDependency(relation, target, parent_assessment))
    codes = tuple(sorted(set(codes), key=lambda c: c.value))
    if codes:
        category = CL.NOT_AUTOMATICALLY_TRANSFORMABLE if IC.SYNTHETIC_LEGACY_PAYMENT in codes else CL.AMBIGUOUS
        return ClassificationResult(assess(h, category, DP.PENDING_INCIDENCE, codes[0], SV.BLOCKING),
                                    None, tuple(deps), codes, None, 'blocked',tuple(unresolved))
    if kind == 'invoice':
        # No relajar bloqueo de factura histórica v2 establecido en1.9A.
        return ClassificationResult(assess(h, CL.VERIFIED_HISTORY, DP.CANDIDATE, severity=SV.BLOCKING),
                                    None, tuple(deps), (), None, 'not_durably_supported')
    try:
        candidate = _candidate(source, ident, event_type, context, observed_at, tuple(deps))
    except (ValueError, TypeError, ArithmeticError):
        code = IC.REQUIRED_VALUE_UNKNOWN
        return ClassificationResult(assess(h, CL.AMBIGUOUS, DP.PENDING_INCIDENCE, code, SV.BLOCKING),
                                    None, tuple(deps), (code,), None, 'blocked')
    terminal = 'not_durably_supported' if event_type in HISTORICAL_V2 else (
        'planned_diagnostic' if all(d.satisfied for d in deps) else 'blocked')
    return ClassificationResult(candidate.assessment, candidate, tuple(deps), tuple(warnings), None, terminal)


def _candidate(source, ident, event, context, observed_at, deps):
    f, kind = source.fields, source.source_kind
    money = {}
    if kind == 'received_invoice':
        payload = {k: declared(source.money[k], nullable=k != 'total') for k in ('total','base','vat_amount','irpf_amount')}
        payload.update(issued_on=f['issued_on'], invoice_number=f['number'], due_on=f['due_on'], confirmed_on=None)
        money = {k: source.money[k].evidence for k in ('total','base','vat_amount','irpf_amount')}
        legacy_date = f['issued_on']
    elif kind == 'expense':
        payload = {'total': declared(source.money['amount']), 'spent_on': None if f['spent_on'] is None else f['spent_on'][:10],
                   'description': f['concept'], 'vat_amount': declared(source.money['_captured_vat_amount'], nullable=True), 'confirmed_on': None}
        money = {'total': source.money['amount'].evidence, 'vat_amount': source.money['_captured_vat_amount'].evidence}
        legacy_date = f['spent_on']
    elif kind == 'bank_transaction':
        payload = {'amount': declared(source.money['amount'])}
        money = {'amount': source.money['amount'].evidence}
        if event == ET.BANK_TRANSACTION_IMPORTED:
            payload.update(booked_on=f['booked_on'], imported_on=None, bank_reference=None)
            legacy_date = f['booked_on']
        else:
            link = context.find('bank_payment_link', 'bank_transaction_id', int(source.source_id))[0]
            payload.update(invoice_payment_id=link.fields['payment_id'], matched_on=f['confirmed_at'][:10])
            legacy_date = f['confirmed_at']
    elif kind == 'invoice_payment':
        payload = {'amount': declared(source.money['amount']), 'invoice_id': f['invoice_id'],
                   'method': f['method'], 'received_on': f['paid_at'][:10]}
        money = {'amount': source.money['amount'].evidence}
        legacy_date = f['paid_at']
    else:
        invoice = context.find('invoice', 'id', f['invoice_id'])[0]
        payload = {'invoice_id': f['invoice_id'], 'invoice_number': f['invoice_number'],
                   'original_total': declared(invoice.money['total']), 'registered_on': f['generated_at'][:10], 'reason': f['reason']}
        money = {'original_total': invoice.money['total'].evidence}
        legacy_date = f['generated_at']
    dates = civil_dates(legacy_date, observed_at)
    basis = EvidenceBasis.OBSERVED_STATE if event in HISTORICAL_V2 else EvidenceBasis.VERIFIED_FACT
    evidence = InventoryEvidence(ident.source, ident.revision, basis, observed_at, dates, money, ())
    category = CL.OBSERVED_STATE if basis == EvidenceBasis.OBSERVED_STATE else CL.VERIFIED_HISTORY
    assessment = assess(evidence.content_hash, category, DP.CANDIDATE,
                        severity=SV.BLOCKING if event in HISTORICAL_V2 or any(not d.satisfied for d in deps) else SV.INFO)
    if event in HISTORICAL_V2:
        payload.update(evidence_basis=basis.value, evidence_hash=evidence.content_hash)
    return DiagnosticCandidate(ident, EventPayload(event, 2 if event in HISTORICAL_V2 else 1,
        EventOrigin.HISTORICAL, payload, Currency.EUR), evidence, dates, assessment, deps, None)


def item_uuid(source, slot):
    from uuid import UUID, uuid5
    # La evidencia no cambia la identidad de item; incompatible en retry → drift.
    key = canonical_bytes({'business_id': source.business_id, 'kind': source.source_kind,
                           'key': source.key, 'slot': slot, 'reader_version': 1})
    return str(uuid5(UUID('ecbcbeb6-d8b7-54ab-8901-dce2e1a36454'), hashlib.sha256(key).hexdigest()))
