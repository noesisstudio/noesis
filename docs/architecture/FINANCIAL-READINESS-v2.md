# Readiness A75 — nuevo sobre v2, sin activación

[Contrato histórico v1](FINANCIAL-READINESS-v1.md), [paridad](FASE-1.10A75-parity.md),
[foundation](SCHEMA-LINEAGE-FOUNDATION-A75-v1.md), [orden](FASE-1.10A75-orden.md).

Misma API interna FinancialReadinessEvaluator con FinancialSession/business_id,
actor/session/permission exactos. Evaluar no autoriza, activa ni ejecuta. Sin
routing público, providers, captura, EE/Operations, GL/Tax/OpenItems ni B–G.

Profile1, Policy1 (max64/TTL300), canonical JSON1, quince capabilities, cierre
transitivo, outcome FULL/PARTIAL/BLOCKED, reasons/expiry/reconciliation/evidencia
fiscal not_applicable y guards de conservación mantienen semántica histórica.
Context nuevo: context_version2, schema_version física75 y SchemaBinding1 actual.
Sobre evaluation_version2; proofs proof_version2 con mismo binding. Todos los
hashes nuevos cubren esos valores. No reinterpretar schema_version74 histórico,
ni elevar v1 a v2 por sustitución. Reader histórico puro conserva raw/hash original.

Binding se comprueba antes de permissions/gate y otra vez en uso/repositorio,
en la TX prestada con registry SHARE primero. Fuentes/configuración/history
se revalidan; drift/integridad/lineage incompatible no persisten una evaluación.
SQL exige registry1..75 exacto y binding de contexto actual; CHECK de fila permite
75..80 para contrato de diseño, pero ninguna futura fila/contexto76 se acepta hoy.
A75 no instala E/F: PRIVACY_NOT_READY/EXPORT_NOT_READY/provider missing conservados.
Nunca hacer stubs de PASS ni legal approval automático.

Migration75 crea sólo financial_activation_control, financial_readiness_evaluations,
financial_readiness_capabilities y guards/índices. Sin registros de enable, grants,
operations/events ni handoff. Estado lógico sin fila=off/gen0/ever_enabledfalse;
control durable nuevo también off/0/false. Solo off/validating permitido.
FKs/keys compuestas tenant/actor; resultados/capabilities finalizados inmutables,
delete/baja/downgrade con evidencia rechazan. Downgrade técnico vacío75→74 probado,
no rollback de producción.
