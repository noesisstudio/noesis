"""Scope C v1 cerrado; no altera el reader/scope diagnóstico B."""

from types import MappingProxyType
from .sources import SOURCES

TRANSPORT_KINDS = frozenset(('verifactu_transport', 'cancellation_transport'))
TRANSPORT_EVENTS = ('remision', 'aceptacion', 'rechazo')
TRANSPORT_FIELDS = ('status', 'sent_at', 'completed_at', 'updated_at')
SOURCE_SCOPE_VERSION = 1
FENCE_VERSION = 1
SCOPE = MappingProxyType({
    'name': 'financial_history_cut_v1', 'version': 1,
    'sources': tuple(sorted(SOURCES)),
    'transport_excluded_fields': TRANSPORT_FIELDS,
    'invoice_event_excluded_types': TRANSPORT_EVENTS,
    'documents': 'all_membership_and_financial_evidence',
})


def guarded_columns():
    result = {}
    for kind, spec in SOURCES.items():
        if kind == 'scope_anchor':
            continue
        columns = set(spec.keys + spec.fields + spec.money + spec.hashed + spec.json_fields) | {'business_id'}
        if kind in TRANSPORT_KINDS:
            columns -= set(TRANSPORT_FIELDS)
        if kind == 'document':
            columns |= {'stored_name', 'filename', 'mime', 'size'}
        # Schema64 bump: cualquier cambio de estas columnas altera revisión hashed.
        if kind == 'bank_transaction':
            columns |= {'match_score', 'match_reason'}
        if kind == 'received_invoice':
            columns |= {'note', 'void_reason'}
        if kind == 'expense':
            columns |= {'void_reason'}
        result[spec.table] = tuple(sorted(columns))
    result['document_sequences'] = ('business_id', 'kind', 'year', 'last_number')
    result['economic_event_sequences'] = ('business_id', 'last_sequence')
    return result
