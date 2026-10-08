# Financial Pilot Verification v1

G-VERIFY es una capa separada de G-PREP. `assess()` sigue documental/anti-READY.
No autoriza acceso real, selección de negocio, aprobación legal, activación,
integración main, despliegue o G-LIVE/H.

## Frontera de acceso y confianza

PilotVerifiers recibe FinancialSession/principal/contexto privados y una TX
consistente del llamador. SQLite exige TX exterior; PostgreSQL REPEATABLE READ
o SERIALIZABLE. No abre ni confirma conexiones. Sólo SELECT; G reutiliza A con
locking=False, sin FOR SHARE; el default A/D/F mantiene locking=True. El gate
también funciona en PostgreSQL READ ONLY. No se ejecutan providers, exports,
restores o lecturas de dumps.
Los hashes de almacenamiento legacy son identidad opaca, no certeza monetaria.
Decimal/NUMERIC y JSON decimal string permanecen en los contratos A–F.

VerificationContext v1: business_id positivo, Profile A exacto, evaluation_uuid,
code_sha Git completo, financial_chain_sha e integration_base_sha esperados,
Cohort REAL/SYNTHETIC. Cohort viene del bootstrap confiable
del entorno; nunca debe aceptarse como elección de un endpoint/chat. Closure y
dependencias se derivan de C, sin elegir, reducir o ampliar el perfil.

TrustStore está vacío por defecto. Sólo un bootstrap privado autorizado puede
instalar SourceAuthority por verifier/cohort. No usar SECRET_KEY ni la clave SQL
del runtime como fallback. No hay emisión real, configuración real de claves,
colectores externos ni API de ingestión en esta fase. HMAC autentica origen;
un documento, hash o claim firmado por una clave desconocida sigue bloqueado.
El colector futuro responde por observaciones/identidad humana específicas;
el algoritmo local además contrasta las fuentes BD y metadatos relacionados.

## Sobre cerrado de origen v1

Campos exactos: version, verifier, evidence_type, cohort, business_id,
profile_hash, context_hash, receipt_uuid, issued_at, expires_at, authority,
actor {user_id,session_version}, metadata. Signature HMAC-SHA256 va separada.
Canonical JSON ordenado, sin float, extras, URLs, paths ni credenciales.
Version=1; UUIDs opacos; hash64; instantes aware; TTL específico y ahora dentro
del intervalo. Origen/rol/tipo exactos por catálogo. Actor actual del tenant.
El gate cruza su actor con OPERATORS, y las personas que ejecutan runbooks con
el rol exacto. Son IDs privados; el informe público conserva hashes, no PII.

SYSTEM_DERIVED usa hechos BD y no admite sobres de claims. PROVIDER verifica
únicamente F existente en environment production y nivel
production_config_verified: local/sandbox nunca habilitan producción. La marca
synthetic impide acreditar REAL aunque IS_PRODUCTION=false en el ordenador.
LEGAL_REVIEW_DERIVED exige policy E approved_for_operation, approval humano
exacto, actor/session/version/hash/timestamp y recibo profesional autenticado.
El verifier no aprueba policy ni produce esa revisión.

## Metadatos específicos

- PILOT_BUSINESS: selección humana UUID/business/criterion=EMPTY; A sources
  completo más Operations/Auth/EE/provider attempts/results/cancelaciones/cierre
  y ambigüedad histórica. No basta invoice_count=0. Drafts y documentos
  explicables no económicos pueden existir; recibidas/gastos persistidos son
  económicos. El scope A incluye cobros, banco, rectificativas y fiscalidad.
- PILOT_PROFILE: selection UUID/Profile/hash/closure/dependencies exactos C.
- BACKUP: UUID/fecha/hash/encryption AT_REST_VERIFIED/access probe UUID/custodio/
  storage PRIVATE_IMMUTABLE u OFFLINE/location aislada/scope business_and_system/
  business exacto/system UUID. Antigüedad máxima 24h. No contenido ni path/DB URL.
- RESTORE: drill UUID/backup exacto/environment UUID/OUTBOUND_DENIED/schema79/
  PASS/hashes expected=actual y registro E=replay/completed_at/operator/custodian.
  Tener backup no sustituye un drill. El gate cruza la misma copia en backup,
  restore, custodia y monitoring.
- DEPLOYMENT: inventario UUID/SHA/schema79/lista exhaustiva esperada/réplicas
  con UUID/role/SHA/schema/flags exactos OFF/RESTRICTED_RUNTIME. Roles web,
  financial_worker y scheduler obligatorios; sin réplicas antiguas u omitidas.
- RUNTIME_KEY: probe UUID/fingerprint/matriz cerrada de accessible/inaccessible
  para web, worker, scheduler, db_runtime y execution_verifier. La clave SQL
  verifier no es accesible por runtime. La matriz debe coincidir con deployment.
- OPERATORS: assignment UUID y seis roles cerrados de G-PREP; primario y
  suplente distintos, usuarios activos/session actuales del tenant.
- BACKUP_CUSTODIAN: assignment UUID/custodio/copia exactos.
- PAUSE/UNKNOWN RUNBOOK: ensayo UUID/scenario cerrado/operador/fecha/PASS/
  failures=[]/version1/hash aceptado. Markdown o reference no sirven. Pausa
  ensaya HOLD email/Meta y drain AEAT committed; UNKNOWN ensaya los tres providers
  sin retry automático. Antigüedad máxima 24h.
- MONITORING: probe de acceso/operator/nueve secciones cerradas y backup.
  Reutiliza read model F; pending/UNKNOWN/privacy inválida bloquean, sin alertas.
- MAIN_INTEGRATION: current_main/base/chain/integration/ancestor SHAs, CI UUID/
  COMPLETE_A_G/SUCCESS/SHA exacto/0FAIL/0ERROR y review UUID ACCEPTED, procedentes
  de colector CI/revisión confiable. No consulta ni integra main aquí.
  Base y chain deben ser las esperadas del contexto; integration_sha/CI_sha
  deben coincidir con code_sha de todas las réplicas, no sólo con un ancestor.
- RESUME_CONTINUITY: ensayo UUID/schema79/operator/fecha/A/handoff/pause/recovery
  hashes/G→G+1 y siete casos cerrados PASS: caducidad positiva, drift, provider
  stale, privacy inválida, UNKNOWN, cambio de perfil, grant antiguo bloqueados.
- PRODUCTION_ACTIVATION: REAL siempre bloqueado por el guard D vigente;
  SYNTHETIC sólo demuestra que ese guard se conserva. No quitarlo con un claim.

READINESS reutiliza verify_readiness A: FULL vigente/perfil/capability proofs/
configuración/fuentes/tenant/hash, sin editar A. HISTORY reutiliza history/B;
observed_state no se promueve, unsupported/pendientes bloquean. PRIVACY/EXPORT
reutilizan E exacto y no crean manifests. Se excluye banco no validado.

## Resultado y revalidación

VerifiedEvidence opaco sólo sale de verifiers; sello privado de instancia,
contenido canónico/SHA256/source receipt hash/context y vigencia ≤300s. Un
constructor/JSON/verified=true no fabrica autoridad. Recheck vuelve a ejecutar
el algoritmo y autenticar fuente. El resultado GateResult también es inmutable
y sellado. Cambiar evidence/blocker/perfil/business/hash/result lo invalida.
No se editan informes antiguos. La instancia conserva su snapshot prestado;
para verificar actualidad tras terminar la TX se deben emitir pruebas nuevas
en un snapshot actual. No persistencia G ni serialización pública del sello.

PilotGate exige los 20 verificadores, sin duplicados, contexto/tenant/cohorte
exactos, evidencia vigente y relaciones coherentes. Decisión PILOT_READY o
PILOT_BLOCKED con failures cerrados. Synthetic READY se etiqueta
SYNTHETIC_STRUCTURAL, real_evidence_verified=false. Toda decisión mantiene
activation_authorized=false. En esta entrega REAL continúa bloqueado y no hay
real-world readiness ni piloto seleccionado.

Catálogo ejecutable y versionado: verification_contracts.CATALOG. Cada Spec
incluye evidence_type, business_scope, authority, source, algorithm, TTL,
canonical_proof, failure_reasons, real_access_required y human_confirmation_required.

[ADR025](ADR-025-pilot-verification-recovery-continuity.md),
[recovery](FINANCIAL-RECOVERY-READINESS-v1.md), [cierre](FASE-1.10G-verify-cierre.md).

## Catálogo v1 completo

Scope de todos: business/profile/closure exactos. Proof: canonical JSON v1 bound a contexto/origen; failures cerrados MISSING/INVALID/STALE/SCOPE/AUTHORITY/CONTEXT/SYNTHETIC/BLOCKED/PRODUCTION.

| Verifier | Tipo | Autoridad | Origen/algoritmo | TTL s | Acceso real | Humano |
|---|---|---|---|---:|---|---|
| LEGAL_POLICY | LEGAL_REVIEW_DERIVED | privacy_legal_owner | E_policy_and_professional_receipt: exact_approved_policy_human_receipt | 86400 | True | True |
| PILOT_BUSINESS | HUMAN_ATTESTED | business_holder | A_F_scoped_sources_and_holder: exhaustive_empty_and_explicit_selection | 300 | True | True |
| PILOT_PROFILE | HUMAN_ATTESTED | business_holder | A_profile_C_registry_and_holder: exact_profile_and_transitive_closure | 300 | True | True |
| READINESS | SYSTEM_DERIVED | primary_operator | A_verify_readiness: reuse_full_every_use | 300 | True | False |
| HISTORY | SYSTEM_DERIVED | primary_operator | history_certificate_and_B: reuse_history_and_B_no_promotion | 300 | True | False |
| PRIVACY | SYSTEM_DERIVED | privacy_legal_owner | E_readiness: current_policy_and_open_account | 300 | True | False |
| EXPORT | SYSTEM_DERIVED | primary_operator | E_manifest: current_complete_tenant_snapshot | 300 | True | False |
| PROVIDER_ATTESTATION | EXTERNAL_PROVIDER_DERIVED | engineering_owner | F_attestations: production_environment_level_ttl_fingerprints | 300 | True | False |
| BACKUP | BACKUP_DRILL_DERIVED | backup_custodian | authorized_backup_collector: encrypted_custodied_access_checked_scoped_metadata | 86400 | True | True |
| RESTORE | BACKUP_DRILL_DERIVED | backup_custodian | isolated_restore_drill_collector: exact_backup_schema_integrity_and_E_replay | 86400 | True | True |
| DEPLOYMENT_COMPATIBILITY | DEPLOYMENT_DERIVED | engineering_owner | deployment_inventory_collector: all_replicas_workers_scheduler_code_schema_roles_flags | 300 | True | True |
| RUNTIME_KEY | DEPLOYMENT_DERIVED | engineering_owner | role_access_probe_collector: required_and_forbidden_key_access_matrix | 300 | True | True |
| OPERATORS | HUMAN_ATTESTED | business_holder | holder_role_assignment_receipt: closed_roles_current_ids_sessions | 86400 | True | True |
| BACKUP_CUSTODIAN | HUMAN_ATTESTED | business_holder | holder_custody_receipt: exact_backup_custodian_assignment | 86400 | True | True |
| PAUSE_RUNBOOK | HUMAN_ATTESTED | primary_operator | pause_rehearsal_receipt: actual_pause_hold_drain_rehearsal | 86400 | True | True |
| UNKNOWN_RUNBOOK | HUMAN_ATTESTED | secondary_on_call | unknown_rehearsal_receipt: all_providers_unknown_no_retry_rehearsal | 86400 | True | True |
| MONITORING | HUMAN_ATTESTED | primary_operator | F_read_model_and_operator_receipt: all_required_sections_access_and_backup_freshness | 300 | True | True |
| MAIN_INTEGRATION | DEPLOYMENT_DERIVED | engineering_owner | CI_and_review_collector: current_main_ancestry_chain_full_clean_CI_review | 300 | True | True |
| PRODUCTION_ACTIVATION | SYSTEM_DERIVED | engineering_owner | D_production_guard: real_remains_blocked_synthetic_contract_only | 300 | False | False |
| RESUME_CONTINUITY | HUMAN_ATTESTED | engineering_owner | D79_continuity_rehearsal_receipt: expired_A_G_plus_one_and_negative_cases | 86400 | False | True |
