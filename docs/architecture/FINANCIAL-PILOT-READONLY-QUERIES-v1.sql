-- PLAN NO EJECUTADO. Requiere autorización real separada, schema79 y tenant humano.
-- psql recibe business_id por variable validada como entero positivo, sin interpolar SQL.
-- No credentials/connection strings aquí. No ejecutar contra QA/backups por defecto.
-- Primero ejecutar Q_SCHEMA separada; STOP si esquema/identidad no son los autorizados.
-- name: Q_SCHEMA
SELECT COALESCE(MAX(version),0) AS schema_version FROM schema_migrations;

-- Resto de fragmentos sólo dentro de BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
-- SET LOCAL statement_timeout='5s'; SET LOCAL lock_timeout='1s'; cerrar con ROLLBACK.
-- Runtime SQL no valida SHA/flags/replicas ni estabilidad de claves por sí solo.
-- name: Q_RUNTIME_ROLE
SELECT current_database() AS database_identity, current_schema() AS schema_identity,
       session_user AS runtime_role, rol.superuser, rol.createrole, rol.bypassrls
FROM (SELECT rolsuper AS superuser, rolcreaterole AS createrole, rolbypassrls AS bypassrls
      FROM pg_roles WHERE rolname=session_user) AS rol;

-- name: Q_KEY_ACCESS
SELECT has_table_privilege(session_user,'financial_execution_verifier_key','SELECT')
       AS runtime_can_read_verifier;

-- name: Q_BUSINESS
SELECT id AS business_id, verifactu_enabled
FROM businesses WHERE id=:'business_id'::bigint;

-- name: Q_EMPTY
SELECT 'invoices_non_draft' AS kind, COUNT(*) AS n FROM invoices
 WHERE business_id=:'business_id'::bigint AND (status IS NULL OR status<>'borrador')
UNION ALL SELECT 'payments',COUNT(*) FROM invoice_payments WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'received_invoices_conservative',COUNT(*) FROM received_invoices WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'expenses_conservative',COUNT(*) FROM expenses WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'bank_transactions',COUNT(*) FROM bank_transactions WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'economic_events',COUNT(*) FROM economic_events WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'fiscal_records',COUNT(*) FROM invoice_records WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'fiscal_cancellation',COUNT(*) FROM invoice_cancellation_records WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'fiscal_outbox',COUNT(*) FROM verifactu_outbox WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'fiscal_cancellation_outbox',COUNT(*) FROM verifactu_cancellation_outbox WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'live_pending_operations',COUNT(*) FROM financial_operations
 WHERE business_id=:'business_id'::bigint AND entry_namespace<>'historical' AND state IN ('prepared','approved');

-- name: Q_PROVIDER_UNCERTAINTY
SELECT a.evidence_uuid AS attempt_uuid,a.binding_uuid,a.provider,a.activation_generation,
       CASE WHEN s.evidence_uuid IS NOT NULL THEN 1 ELSE 0 END AS started,
       r.result AS terminal_result
FROM financial_provider_dispatch_attempts a
LEFT JOIN financial_provider_dispatch_starts s ON s.business_id=a.business_id AND s.attempt_uuid=a.evidence_uuid
LEFT JOIN financial_provider_dispatch_results r ON r.business_id=a.business_id AND r.attempt_uuid=a.evidence_uuid
WHERE a.business_id=:'business_id'::bigint
  AND (r.evidence_uuid IS NULL OR r.result='UNKNOWN_EXTERNAL_RESULT')
ORDER BY a.evidence_uuid;

-- name: Q_CONTROL
SELECT state,activation_generation,ever_enabled,control_revision,current_transition_uuid
FROM financial_activation_control WHERE business_id=:'business_id'::bigint;

-- name: Q_READINESS
SELECT evaluation_uuid,profile_hash,result,content_hash,context_hash,created_at,expires_at
FROM financial_readiness_evaluations WHERE business_id=:'business_id'::bigint AND state='final'
ORDER BY created_at DESC,evaluation_uuid DESC;

-- name: Q_HISTORY
SELECT epoch_uuid,fence_enabled FROM financial_history_control WHERE business_id=:'business_id'::bigint;

-- name: Q_RECONCILIATION
SELECT reconciliation_uuid,batch_uuid,manifest_uuid,state,result,result_hash
FROM financial_history_reconciliations WHERE business_id=:'business_id'::bigint
ORDER BY started_at DESC,reconciliation_uuid DESC;

-- name: Q_POLICY
SELECT evidence_uuid,status,content_hash,created_at FROM financial_retention_policies
WHERE business_id=:'business_id'::bigint ORDER BY created_at DESC,evidence_uuid DESC;

-- name: Q_EXPORT
SELECT evidence_uuid,content_hash,created_at FROM financial_export_manifests
WHERE business_id=:'business_id'::bigint ORDER BY created_at DESC,evidence_uuid DESC;

-- name: Q_CLOSURE
SELECT 'authorized_closure' AS kind,COUNT(*) AS n FROM financial_closure_authorizations WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'closure_receipt',COUNT(*) FROM financial_closure_receipts WHERE business_id=:'business_id'::bigint
UNION ALL SELECT 'restored_closed_account',COUNT(*) FROM financial_restore_suppressions
 WHERE business_id=:'business_id'::bigint AND scope='account_local_access';

-- name: Q_ATTESTATIONS
SELECT evidence_uuid,provider,implementation,capability,environment,level,result,
       expires_at,content_hash FROM financial_provider_attestations
WHERE business_id=:'business_id'::bigint ORDER BY created_at DESC,evidence_uuid DESC;

-- name: Q_PREFLIGHT
SELECT evidence_uuid,result,expires_at,content_hash FROM financial_provider_preflight_runs
WHERE business_id=:'business_id'::bigint ORDER BY created_at DESC,evidence_uuid DESC;

-- name: Q_GRANTS
SELECT activation_generation,capability,profile_hash,grant_hash,receipt_uuid
FROM financial_activation_grants WHERE business_id=:'business_id'::bigint
ORDER BY activation_generation,capability;

-- name: Q_OUTBOX_COUNTS
SELECT 'email' AS kind,status,COUNT(*) AS n,MIN(created_at) AS oldest FROM email_outbox
WHERE business_id=:'business_id'::bigint GROUP BY status
UNION ALL SELECT 'meta',status,COUNT(*),MIN(created_at) FROM whatsapp_outbox
WHERE business_id=:'business_id'::bigint GROUP BY status;

-- Nunca SELECT * de usuarios, credentials, inbox, body_canonical, fiscal XML o PII.
-- Hashes de filas privadas: sólo en reader exacto confiable/HMAC, sin copiar contenidos.
-- Las referencias SQL no prueban canonical/hash/procedencia: ejecutar verifiers A/B/E/F
-- existentes en futuro acceso autorizado. No llamar evaluate/check/export/prepare/advance.
