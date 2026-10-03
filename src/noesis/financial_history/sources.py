"""Catálogo de evidencia cerrado, contrastado con schema69; no productores."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class SourceSpec:
    table: str
    keys: tuple[str, ...]
    fields: tuple[str, ...]
    money: tuple[str, ...] = ()
    hashed: tuple[str, ...] = ()
    json_fields: tuple[str, ...] = ()


def spec(table, fields, money='', *, keys='id', hashed='', json_fields=''):
    return SourceSpec(table, tuple(keys.split()), tuple(fields.split()), tuple(money.split()),
                      tuple(hashed.split()), tuple(json_fields.split()))


SOURCES = MappingProxyType({
    'scope_anchor': spec('businesses', 'id'),
    'invoice': spec('invoices', 'id client_id number invoice_type rectifies_invoice_id rectification_type status '
        'issued_at operation_date due_date paid_at created_at series_id document_profile_id currency source',
        'base vat_amount irpf_amount total vat_rate irpf_rate',
        hashed='concept issuer_name issuer_nif issuer_address recipient_name recipient_nif recipient_address'),
    'invoice_line': spec('invoice_lines', 'id invoice_id position kind created_at',
        'quantity unit_price discount_rate vat_rate base vat_amount total', hashed='description'),
    'invoice_series': spec('invoice_series', 'id code document_type created_at'),
    'document_profile': spec('document_profiles', 'id version invoice_template brand_color logo_mime footer_image_mime '
        'footer_image_width footer_image_alignment footer_image_scope created_at',
        hashed='logo_data document_footer footer_image_data'),
    'invoice_record': spec('invoice_records', 'id invoice_id record_type record_version invoice_type rectification_type '
        'invoice_number issue_date operation_date generated_at previous_record_id previous_hash record_hash hash_algorithm '
        'hash_type hash_spec_version rectified_invoice_number rectified_issue_date created_at', 'vat_total invoice_total',
        hashed='issuer_nif rectified_issuer_nif qr_url', json_fields='breakdown_json'),
    'invoice_event': spec('invoice_events', 'id invoice_id record_id event_type created_at'),
    'verifactu_transport': spec('verifactu_outbox', 'id invoice_id record_id status sent_at completed_at created_at updated_at'),
    'invoice_payment': spec('invoice_payments', 'id invoice_id method paid_at created_at', 'amount'),
    'bank_transaction': spec('bank_transactions', 'id import_hash booked_on currency status suggested_invoice_id '
        'confirmed_at created_at _financial_revision', 'amount', hashed='description counterparty reference'),
    'bank_payment_link': spec('bank_payment_links', 'bank_transaction_id payment_id', keys='bank_transaction_id'),
    'received_invoice': spec('received_invoices', 'id supplier_id number issued_on due_on status category created_at '
        '_financial_revision voided_at', 'base vat_amount irpf_amount total vat_rate', hashed='concept'),
    'supplier': spec('suppliers', 'id created_at', hashed='name nif'),
    'expense': spec('expenses', 'id concept spent_on category created_at project_id _financial_revision voided_at',
        'amount vat_rate _captured_vat_amount', hashed='concept'),
    'document': spec('documents', 'id invoice_id expense_id received_invoice_id kind doc_status content_sha256 '
        'reviewed_at created_at'),
    'document_classification': spec('document_classifications', 'id document_id detected_kind confirmed_kind method '
        'confirmed_at created_at'),
    'invoice_cancellation_record': spec('invoice_cancellation_records', 'id invoice_id original_record_id invoice_number '
        'issue_date reason generated_at previous_record_type previous_record_id previous_hash record_hash hash_algorithm '
        'hash_type hash_spec_version created_at', hashed='issuer_nif'),
    'cancellation_transport': spec('verifactu_cancellation_outbox', 'id invoice_id record_id status sent_at '
        'completed_at created_at updated_at'),
    'recurring_run': spec('recurring_invoice_runs', 'id recurring_id scheduled_for invoice_id status created_at '
        'completed_at financial_template_hash'),
    'recurring_schedule': spec('recurring_invoices', 'id client_id cadence interval_count next_run_on ends_on auto_issue '
        'status invoice_type series_id created_at updated_at', hashed='lines_json'),
    'economic_event': spec('economic_events', 'id event_uuid business_sequence event_type payload_version operation_uuid '
        'event_slot idempotency_key source_type source_id source_revision invoice_id invoice_payment_id received_invoice_id '
        'expense_id bank_transaction_id invoice_cancellation_record_id occurred_at observed_at economic_date date_precision '
        'date_provenance currency authorization_uuid origin historical_batch_uuid provenance canonical_version content_hash '
        'record_hash recorded_at', 'amount', json_fields='payload_canonical canonical_event'),
    'economic_event_link': spec('economic_event_links', 'event_uuid target_event_uuid relation_type recorded_at',
        keys='event_uuid relation_type target_event_uuid'),
    'invoice_coverage': spec('invoice_economic_coverage', 'invoice_id event_uuid event_type operation_uuid operation_state', keys='invoice_id'),
    'payment_coverage': spec('payment_economic_coverage', 'operation_uuid invoice_id invoice_event_uuid payment_id '
        'source_fingerprint event_uuid event_type operation_state', keys='operation_uuid'),
    'bank_import_coverage': spec('bank_import_coverage', 'operation_uuid bank_transaction_id source_revision source_fingerprint '
        'event_uuid event_type batch_uuid row_key account_scope statement_hash content_fingerprint operation_state', keys='operation_uuid'),
    'bank_match_coverage': spec('bank_match_coverage', 'bank_transaction_id operation_uuid payment_id source_revision '
        'imported_event_uuid payment_event_uuid event_uuid event_type operation_state', keys='bank_transaction_id'),
    'supplier_coverage': spec('supplier_invoice_economic_coverage', 'source_id source_revision operation_uuid event_uuid '
        'event_type source_fingerprint antecedent_uuid operation_state', keys='source_id source_revision', json_fields='before_state after_state'),
    'expense_coverage': spec('expense_economic_coverage', 'source_id source_revision operation_uuid event_uuid '
        'event_type source_fingerprint antecedent_uuid operation_state', keys='source_id source_revision', json_fields='before_state after_state'),
})
PRIMARY = frozenset(('invoice', 'invoice_payment', 'bank_transaction', 'received_invoice', 'expense', 'invoice_cancellation_record'))
READER_VERSION = CLASSIFIER_VERSION = SCOPE_VERSION = 1
