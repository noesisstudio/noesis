"""SELECTs tenant-scoped, keyset; conexión prestada sin commit ni efectos."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from uuid import UUID

from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import positive_id
from noesis.economic_events.persistence import StoredEvent
from .canonical import CanonicalContract, freeze
from .raw import MoneyObservation, observe_money
from .money_evidence import RawMonetaryEvidence
from .sources import SOURCES


def minimal(value):
    if isinstance(value, (datetime, date, UUID)):
        return value.isoformat() if not isinstance(value, UUID) else str(value)
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, float):
        raise TypeError('Un campo binario necesita extractor raw explícito.')
    return value


@dataclass(frozen=True, slots=True)
class RawSource(CanonicalContract):
    business_id: int
    source_kind: str
    key: tuple
    fields: Mapping
    money: Mapping[str, MoneyObservation]
    reader_version: int = 1
    provenance: Mapping | None = None

    def __post_init__(self):
        positive_id(self.business_id)
        spec = SOURCES[self.source_kind]
        if len(self.key) != len(spec.keys) or self.reader_version != 1:
            raise ValueError('Clave/versión de reader incompatible.')
        allowed = set(spec.fields) | set(spec.json_fields) | {f + '_hash' for f in spec.hashed}
        if self.source_kind == 'document_profile':
            allowed.add('profile_snapshot_hash')
        if self.source_kind in ('invoice_record','invoice_cancellation_record'):
            allowed.add('fiscal_hash_valid')
        if set(self.fields) != allowed or set(self.money) != set(spec.money):
            raise ValueError('Snapshot cerrado incompatible con source.')
        if any(not isinstance(v, MoneyObservation) for v in self.money.values()):
            raise TypeError('Raw money tipado requerido.')
        object.__setattr__(self, 'fields', freeze(self.fields))
        object.__setattr__(self, 'money', freeze(self.money))
        object.__setattr__(self, 'key', tuple(self.key))
        provenance = {'source_origin': 'original_source' if self.source_kind == 'economic_event' else 'unknown'}
        if self.source_kind == 'invoice_payment' and self.fields['method'] == 'registro_anterior':
            provenance = {'source_origin':'migration_derived', 'migration_marker':'registro_anterior', 'migration_version':11}
        if self.source_kind in ('invoice_line','invoice_series','document_profile'):
            provenance['migration_marker'] = 'no_discriminating_marker'
        if '_financial_revision' in self.fields:
            provenance['revision_origin'] = 'observed_only_since_migration64'
        if self.provenance is not None and dict(self.provenance) != provenance:
            raise ValueError('Procedencia no demostrada por los marcadores disponibles.')
        object.__setattr__(self, 'provenance', freeze(provenance))
        self.canonical_bytes()

    @property
    def source_id(self):
        return str(self.key[0])

    @classmethod
    def from_canonical(cls, text):
        body = json.loads(text)
        if body.get('canonical_version') != 1 or body.get('contract') != 'RawSource':
            raise ValueError('Contrato raw desconocido.')
        value = body['value']
        money = {}
        for key, observation in value['money'].items():
            evidence = observation['evidence']
            observation['evidence'] = None if evidence is None else RawMonetaryEvidence(**evidence)
            money[key] = MoneyObservation(**observation)
        return cls(value['business_id'], value['source_kind'], tuple(value['key']), value['fields'], money,
                   value['reader_version'], value.get('provenance'))


class RawReader:
    def __init__(self, connection, business_id, *, page_size=64, cut_scope=False):
        self.connection = connection.borrowed_connection if isinstance(connection, FinancialSession) else connection
        self.business_id = positive_id(business_id)
        if type(page_size) is not int or not 1 <= page_size <= 256:
            raise ValueError('Página de 1 a256 filas requerida.')
        self.page_size = page_size
        self.query_count = 0
        self.cut_scope = cut_scope

    def page(self, source_kind, after=None):
        return self._rows(source_kind, after=after)

    def read_key(self, source_kind, key):
        """Lectura indexada de la fuente real; no devuelve una revisión declarada."""
        if source_kind in ('invoice_record', 'invoice_cancellation_record'):
            raise ValueError('El importer fiscal verifica referencias sin recalcular huellas.')
        rows = self._rows(source_kind, exact_key=tuple(key))
        return rows[0] if len(rows) == 1 else None

    def read_fiscal_reference(self, frozen):
        """Contrasta referencia congelada; no regenera ni recalcula huella fiscal."""
        if frozen.source_kind not in ('invoice_record', 'invoice_cancellation_record'):
            raise ValueError('Referencia fiscal cerrada requerida.')
        rows = self._rows(frozen.source_kind, exact_key=frozen.key,
                          frozen_fiscal_valid=frozen.fields['fiscal_hash_valid'])
        return rows[0] if len(rows) == 1 else None

    def _rows(self, source_kind, after=None, exact_key=None, frozen_fiscal_valid=None):
        spec = SOURCES[source_kind]
        columns = ['id AS business_id' if source_kind == 'scope_anchor' else 'business_id', *spec.fields, *spec.hashed, *spec.json_fields]
        for field in spec.money:
            columns += [field]
            if self.connection.dialect == 'postgres':
                columns += [f'pg_typeof({field})::text AS {field}_storage', f'{field}::text AS {field}_text']
                # Los campos exactos son NUMERIC; los legacy son float8.
                if field not in ('amount', '_captured_vat_amount') or source_kind not in ('economic_event', 'expense'):
                    columns += [f'encode(float8send({field}),\'hex\') AS {field}_bits']
                elif source_kind == 'expense' and field != '_captured_vat_amount':
                    columns += [f'encode(float8send({field}),\'hex\') AS {field}_bits']
            else:
                columns += [f'typeof({field}) AS {field}_storage', f'CAST({field} AS TEXT) AS {field}_text']
        tenant_column = 'id' if source_kind == 'scope_anchor' else 'business_id'
        sql = f'SELECT {",".join(columns)} FROM {spec.table} WHERE {tenant_column}=?'
        params = [self.business_id]
        if self.cut_scope and source_kind == 'invoice_event':
            sql += " AND event_type NOT IN ('remision','aceptacion','rechazo')"
        if after is not None:
            if len(after) != len(spec.keys):
                raise ValueError('Cursor incompatible.')
            sql += f' AND ({",".join(spec.keys)})>({",".join("?" for _ in spec.keys)})'
            params += list(after)
        if exact_key is not None:
            if len(exact_key) != len(spec.keys):
                raise ValueError('Clave exacta incompatible.')
            sql += ' AND ' + ' AND '.join(f'{field}=?' for field in spec.keys)
            params += list(exact_key)
        sql += f' ORDER BY {",".join(spec.keys)} LIMIT ?'
        params.append(self.page_size)
        self.query_count += 1
        rows = self.connection.execute_exact(sql, tuple(params)).fetchall()
        if frozen_fiscal_valid is None:
            return tuple(self._source(source_kind, row) for row in rows)
        return tuple(self._source(source_kind, row, frozen_fiscal_valid=frozen_fiscal_valid) for row in rows)

    def _source(self, source_kind, row, *, frozen_fiscal_valid=None):
        spec = SOURCES[source_kind]
        fields = {key: minimal(row[key]) for key in spec.fields}
        if self.cut_scope:
            from .cut_scope import TRANSPORT_FIELDS, TRANSPORT_KINDS
            if source_kind in TRANSPORT_KINDS:
                fields.update(dict.fromkeys(TRANSPORT_FIELDS))
        if source_kind == 'document_profile':
            # Contraste del snapshot de perfil existente sin persistir sus blobs.
            profile = {key:minimal(row[key]) for key in ('business_id',*spec.fields,*spec.hashed)}
            fields['profile_snapshot_hash'] = hashlib.sha256(json.dumps(profile,sort_keys=True,
                ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        for key in spec.hashed:
            fields[key + '_hash'] = None if row[key] is None else hashlib.sha256(str(row[key]).encode('utf-8')).hexdigest()
        for key in spec.json_fields:
            fields[key] = None if row[key] is None else _read_json(row[key])
            # parse_float preserva la representación decimal SERIALIZADA;
            # no acredita que el writer legacy tuviera precisión original.
            fields[key] = _json_minimal(fields[key])
            if source_kind in ('supplier_coverage', 'expense_coverage') and fields[key] is not None:
                fields[key] = _private_projection(fields[key])
        if source_kind == 'economic_event':
            valid = True
            try:
                # Solo verifica un registro YA existente. No construye hechos nuevos.
                StoredEvent.from_row(row)
            except (ValueError, TypeError, KeyError, ArithmeticError):
                valid = False
            fields['canonical_event'] = {'validated': valid,
                'storage_hash': hashlib.sha256(row['canonical_event'].encode()).hexdigest(),
                'relations': fields['canonical_event'].get('relations', []) if valid else []}
            fields['payload_canonical'] = _private_projection(fields['payload_canonical']) if valid else {
                'invalid_payload_hash': hashlib.sha256(row['payload_canonical'].encode()).hexdigest()}
        money = {}
        for key in spec.money:
            storage = row[key + '_storage']
            if storage == 'double precision':
                storage = 'double_precision'
            money[key] = observe_money(self.connection.dialect, row[key], storage,
                                       row[key + '_text'], row.get(key + '_bits'))
        if source_kind in ('invoice_record','invoice_cancellation_record') and frozen_fiscal_valid is not None:
            fields['fiscal_hash_valid'] = frozen_fiscal_valid
        elif source_kind in ('invoice_record','invoice_cancellation_record'):
            # Verifica huella YA almacenada, después de preservar raw. No genera
            # registros/XML/QR, ni convierte binarios legacy en dinero acreditado.
            from noesis.verifactu import cancellation_record_hash, invoice_record_hash
            values = {key:minimal(row[key]) for key in ('issuer_nif','invoice_number','issue_date','previous_hash','generated_at')}
            try:
                if source_kind=='invoice_record':
                    calculated = invoice_record_hash(algorithm=row['hash_algorithm'],**values,
                        invoice_type=row['invoice_type'],vat_total=row['vat_total'],invoice_total=row['invoice_total'])
                else:
                    calculated = cancellation_record_hash(algorithm=row['hash_algorithm'],**values)
                fields['fiscal_hash_valid'] = calculated==row['record_hash']
            except (TypeError,ValueError,ArithmeticError):
                fields['fiscal_hash_valid'] = False
        return RawSource(self.business_id, source_kind, tuple(minimal(row[key]) for key in spec.keys), fields, money)


def _json_minimal(value):
    if isinstance(value, dict):
        return {k: _json_minimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_minimal(v) for v in value]
    return minimal(value)


def _read_json(text):
    try:
        return json.loads(text, parse_float=Decimal, parse_constant=lambda v: v)
    except (ValueError, TypeError):
        return {'invalid_json_hash': hashlib.sha256(str(text).encode()).hexdigest()}


def _private_projection(value):
    """Hash del contenido completo; proyección sin notas, direcciones ni blobs."""
    from .canonical import canonical_bytes
    digest = hashlib.sha256(canonical_bytes(value)).hexdigest()
    try:
        return _project_mapping(value, digest)
    except (KeyError, TypeError, AttributeError):
        # Corrupción de forma es evidencia, no permiso de copiar contenido libre.
        return {'storage_hash': digest, 'invalid_projection': True}


def _project_mapping(value, digest):
    if not isinstance(value, Mapping):
        return {'storage_hash': digest, 'invalid_projection': True}
    safe = {'total','base','vat_amount','irpf_amount','amount','_captured_vat_amount','spent_on','issued_on','due_on',
            'confirmed_on','voided_on','corrected_on','received_on','booked_on','imported_on','matched_on','registered_on',
            'invoice_id','invoice_payment_id','invoice_number','invoice_kind','method','source_fingerprint',
            'invoice_number','number','supplier_id','project_id','voided_at','category','vat_rate'}
    projection = {k: v for k, v in value.items() if k in safe}
    if any(isinstance(v, (Mapping, list, tuple)) for v in projection.values()):
        return {'storage_hash': digest, 'invalid_projection': True}
    for key in ('before', 'after'):
        if key in value:
            projection[key] = _private_projection(value[key])
    if 'evidence' in value:
        evidence = value['evidence']
        projection['evidence'] = {k: evidence.get(k) for k in ('invoice_id', 'client_id', 'source_fingerprint', 'money_provenance',
                                                             'irpf_rate','series','document_profile')}
        for party in ('issuer','recipient'):
            projection['evidence'][party] = {key+'_hash':None if text is None else hashlib.sha256(str(text).encode()).hexdigest()
                for key,text in evidence[party].items()}
        projection['evidence']['lines'] = [{k:v for k,v in line.items() if k!='description'} | {
            'description_hash':hashlib.sha256(line['description'].encode()).hexdigest()} for line in evidence['lines']]
        fiscal = evidence['fiscal_record']
        projection['evidence']['fiscal_record'] = None if fiscal is None else {k:fiscal[k] for k in (
            'id','record_hash','previous_hash','generated_at','vat_total','invoice_total')}
    projection['storage_hash'] = digest
    for key in ('description', 'concept', 'reason', 'void_reason'):
        if key in value:
            projection[key + '_hash'] = None if value[key] is None else hashlib.sha256(str(value[key]).encode()).hexdigest()
    return projection
