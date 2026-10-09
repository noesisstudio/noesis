# RecoveryReadiness v1 — continuidad live schema79

Resume conserva A original como provenance: FULL original, hashes/perfil/grants
y certificado exactos, sin editar TTL ni crear un nuevo FULL artificial. La
primera activación sigue exigiendo A FULL vigente. Este contrato sólo vale para
ever_enabled=true, PAUSED, generación≥1, mismo negocio/perfil/closure/grants.

Campos exactos v1: business_id, evaluation_uuid/evaluation_hash,
original_handoff_hash, previous_generation, generation_receipt_hash,
pause_receipt_uuid/pause_receipt_hash, profile_hash/capabilities/grant_hash,
configuration_hash/snapshot_hash/history_hash/privacy_hash/source_hash,
actor_user_id/actor_session_version/code_version y version. Hash64/UUID
canónicos, enteros estrictos, caps ordenadas, sin float ni extras. Decode sólo
valida estructura; no acredita continuidad.

El verifier recibe FinancialSession prestada dentro del gate/TX D/F. Sólo
SELECT. Revalida:

1. Operador/sesión/cuenta/subscription actuales, estado PAUSED y G actual.
2. A durable íntegra y original handoff G1; cada generation/request/receipt/grant
   se valida con los verificadores D existentes. Closure C y dependencias
   iguales, configuración inicial igual al snapshot actual.
3. Pausa durable exacta y snapshot actual igual al de pausa. Fuentes finales,
   Operations/Auth/EE y configuración comprometidos por hashes existentes D.
4. Reconciliación histórica congelada PASS y findings íntegros; manifest/source
   set/plan/items/candidatos/incidencias congelados por verifier history. Cut,
   manifest/batch/reconciliation storage hashes originales; epoch handed_off,
   fence OFF/T0/scope/generation/handoff íntegros y control history consistente.
   La equivalencia cut tras handoff reutiliza historical_cut_hash. No se llama
   al arco fenced inicial, ni a importer/run/reconciliation writes.
5. Pruebas B de cada EE actual y sus dependencias/coverage/autoridad. Se conserva
   quality observada; nunca se transforma observed_state en verified_fact.
6. E actual approved/privacy/export/open; ninguna closing/closed. F externo
   pendiente o UNKNOWN bloquea. El preflight F exige además cada attestation
   production actual con huellas/environment/código/TTL y configuración exactos.

Drift/corruption/unknown/providers stale/privacy inválida/perfil diferente
mantienen PAUSED; no repair, fallback legacy, history import ni fence nuevo.
El TTL de A original deja de bloquear sólo este arco, una vez verificados los
testigos actuales. F preflight conserva TTL 5min y revalida every_use.

Persistencia: campo aditivo recovery_readiness en context de NUEVOS preflights
resume F79. RUNS canónico y binding D→F existentes lo guardan inmutable; nuevos
receipts D resume comprometen recovery_readiness_hash. Durante la misma TX,
D pasa validating→ready→enabled y crea G+1 con autoridad humana durable exacta.
G anterior no revive: Operations/Auth/mandates/bindings conservan guards de G.

No migration80. Requests originales mantienen contrato/hash; receipts de pausa
y handoff anteriores no se reescriben. Decodificación de F context antiguo sigue
compatible, pero no se usa para autorizar NUEVOS resumes79 sin proof actual.
Schema77/78 permanece igual; guard producción D intacto, cinco flags reales OFF.

Validación: SQLite y PostgreSQL descartables, A FULL→enable→A expirada→pause→
evidence actual→resume G+1; negativos de drift/stale/privacy/UNKNOWN/profile y
actor stale, conservación A/recibos/history, every_use y no DML del verifier.
No se ejecuta sobre producción, QA real o backups reales.

[ADR025](ADR-025-pilot-verification-recovery-continuity.md),
[pilot verification](FINANCIAL-PILOT-VERIFICATION-v1.md), [cierre](FASE-1.10G-verify-cierre.md).
