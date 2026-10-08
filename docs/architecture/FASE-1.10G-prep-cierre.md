# Fase 1.10G-PREP — expediente local

**PILOT_BLOCKED — EXTERNAL PREREQUISITES PENDING**
A–F CODE-VERIFIED PASS. G-LIVE NO AUTORIZADO. H NO INICIADA.

## Identidad y alcance

Rama local codex/phase-1-10g-prep. Padre/base exactos:
`981ffc2f26e645aa98792d9968f7d85c1246d688`. Commit de entrega: consultar HEAD.
No parte de main; sin rebase/merge/integración/push/deploy.
main declarado por orden `08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d`, único cambio
eliminar sigue.md sobre `acff183319f476a5f0b25a820751dca4523fd8fd`. No se consultó
remoto/producción para esta preparación. Integración futura desde main actual,
CI fresca completa e inspección obligatorias antes de deploy/pilot.

## Entrega y decisión

[Orden íntegra](FASE-1.10G-prep-orden.md), [contrato cerrado](FINANCIAL-PILOT-READINESS-v1.md),
[expediente JSON](FASE-1.10G-prep-report.json), [checklist](FINANCIAL-PILOT-CHECKLIST-v1.md),
[runbook](FINANCIAL-PILOT-RUNBOOK-v1.md), [SQL preparado](FINANCIAL-PILOT-READONLY-QUERIES-v1.sql),
[checks providers diseñados](FINANCIAL-PILOT-PROVIDER-CHECKS-v1.md).

PilotReadinessReport v1 puro/documental, sin nuevo esquema/estado/provider layer.
No migration80 ni cambios a migrations/db.py/A–F/adapters/config/workflows.
Reutiliza Profile A/spec C/OperationalPolicy F. Instantes explícitos/canonical/
SHA256/reasons/roles cerrados; sin floats, texto libre de autoridad, PII/secretos.
TTL/context drift sólo evalúan vigencia documental; nunca autoridad de activación.
Expediente actual business/profile NULL: no se ha seleccionado cuenta real.
SHA dentro del contexto es la base de software A–F, no SHA runtime productivo.
Informe generado con hora UTC y expiry300s; después conserva evidencia documental
bloqueada, no se anuncia como vigente. Ninguna referencia retira blockers.
READY reservado pero no habilitado: requiere futura evidencia real verificada
tras autorización separada. No existe ingestión de approvals/real facts JSON que
pueda falsear un resultado listo. No se afirma REAL-WORLD READY.

Perfil mínimo recomendado: request expense.confirm + expense.void; closure
channel.web_financial, expense.confirm, expense.void; providers ninguno; no bank.
Web solo sin comandos no cumple D. Facturación VF exige emisión/rectificación/
cancelación/AEAT. WhatsApp/email requieren Meta/email. Legalmente todos bloqueados
hoy por policy real provisional y prerequisitos no verificados. No se cambió
modo VF ni se redujo un perfil recibido para ocultar historia.

E REAL sigue PROVISIONAL / PENDIENTE DE APROBACIÓN PROFESIONAL y
PRIVACY_NOT_READY permanece. No persona, cuenta o approval inventadas.
D sigue rechazando producción; recovery D79 cuando A original caduca exige
solución autorizada antes de pilot. Ambos blockers explícitos, sin bypass.

## Tabla exacta de acciones reales pendientes

Esta tabla inventaría todos los reason codes posibles, no afirma que todos
se hayan observado en una cuenta. Missing y no verificado se conservan; unknown
no se transforma en fracaso de una cuenta ni en éxito. Los owners son roles sin
asignar. Requires human incluye aprobación de alcance/aceptación; no IA decide.

| BLOCKER | OWNER | EVIDENCE NEEDED | ACTION | CAN CODEX DO IT? | REQUIRES HUMAN? | REQUIRES REAL ACCESS? | RISK |
|---|---|---|---|---|---|---|---|
| ACCOUNT_CLOSED | privacy_legal_owner (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Conservar cierre E; no reabrir ni activar desde G-PREP. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| ACCOUNT_CLOSING | privacy_legal_owner (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Mantener bloqueo E; no iniciar piloto sobre cuenta en cierre. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| BACKUP_CUSTODIAN_NOT_ASSIGNED | business_holder (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Asignar responsable humano de custodia y restauración. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| BACKUP_NOT_VERIFIED | backup_custodian (sin asignar) | Hash/fecha/ubicación/cifrado/ACL/custodia reales | Verificar copia reciente, hash, custodia y cifrado at-rest bajo permiso separado. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| BANK_NOT_ALLOWED | business_holder (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Excluir banco del diseño piloto sólo por elección explícita; no habilitar capability no validada. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| DEPLOYMENT_COMPATIBILITY_UNKNOWN | engineering_owner (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Verificar SHA/schema79/roles/replicas/workers/scheduler compatibles sin réplicas antiguas. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| EXPORT_NOT_READY | primary_operator (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Verificar export E completo y vigente; G-PREP no crea un manifest. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| FISCAL_CONTEXT_UNVERIFIED | privacy_legal_owner (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Verificar modo fiscal del negocio; condición desconocida nunca omite AEAT de invoice.issue. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| HISTORY_BLOCKED | primary_operator (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Verificar corte/import/reconciliación/antecedentes existentes sin omitir fuentes. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| LEGAL_POLICY_UNAPPROVED | privacy_legal_owner (sin asignar) | Revisión profesional + referencia/confirmación exacta E | Obtener revisión profesional y confirmación humana exacta de policy E. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| MAIN_INTEGRATION_PENDING | engineering_owner (sin asignar) | Rama integración desde main + CI final limpia/inspección | Integrar A–G en rama futura desde main actual y ejecutar CI completa antes de deploy. | Sí, en alcance técnico futuro autorizado | Sí | No para diseñar; sí para aceptación productiva | Medio: compatibilidad/integridad |
| MONITORING_NOT_READY | primary_operator (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Verificar acceso al read model F y evidencia de freshness de backup. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| OPERATOR_NOT_ASSIGNED | business_holder (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Asignar operador primario, suplente y privacy/legal owner por decisión humana. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| PAUSE_RUNBOOK_UNVERIFIED | primary_operator (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Ensayar runbook D/F en sintético y validar su ejecutabilidad real por operador. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| PILOT_BUSINESS_NOT_SELECTED | business_holder (sin asignar) | Elección humana + inventario completo del business | Seleccionar explícitamente un único negocio tras checklist EMPTY autorizada. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| PILOT_PROFILE_NOT_SELECTED | business_holder (sin asignar) | Perfil/hash/closure exactos confirmados | Confirmar el perfil exacto y su closure C; no reducirlo para ocultar historia. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| PRIVACY_NOT_READY | privacy_legal_owner (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Verificar readiness E real; provisional sigue bloqueando. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| PRODUCTION_ACTIVATION_NOT_AUTHORIZED | engineering_owner (sin asignar) | Revisión D productivo + autorización humana posterior | Revisar guard de producción D con autorización futura explícita; no desactivarlo aquí. | Sí, en alcance técnico futuro autorizado | Sí | No para diseñar; sí para aceptación productiva | Medio: compatibilidad/integridad |
| PROVIDER_ATTESTATION_MISSING | primary_operator (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Obtener attestations productivas reales del closure exacto tras permiso específico. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| PROVIDER_ATTESTATION_STALE | primary_operator (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Emitir nueva attestation autorizada y revalidar huellas/expiry sin refresh. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| PROVIDER_ENVIRONMENT_MISMATCH | primary_operator (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Verificar entorno productivo exacto; local/sandbox no sustituyen producción. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| READINESS_NOT_FULL | primary_operator (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Obtener A FULL vigente del negocio/perfil exactos y comprobar su contexto. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| READINESS_STALE | primary_operator (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Reevaluar A con fuentes actuales; nunca editar ni promover la evaluación antigua. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| REAL_EVIDENCE_NOT_VERIFIED | primary_operator (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Verificar evidencia real autorizada; hashes/documentación/fixtures no acreditan readiness. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| RESTORE_NOT_VERIFIED | backup_custodian (sin asignar) | Drill aislado actual/schema79/FKs/replay E/hashes | Verificar restore aislado actual con replay E antes de servir; existencia no basta. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| RESUME_READINESS_CONTINUITY_UNVERIFIED | engineering_owner (sin asignar) | Contrato y ensayo recuperación A caducada sin reset | Resolver antes del piloto la recuperación D79 cuando A original haya caducado. | Sí, en alcance técnico futuro autorizado | Sí | No para diseñar; sí para aceptación productiva | Medio: compatibilidad/integridad |
| RUNTIME_KEY_NOT_VERIFIED | engineering_owner (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Verificar runtime/verifier y estabilidad de HMAC sin mostrar ni copiar claves. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| SAFE_CHECK_UNIMPLEMENTED | engineering_owner (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Validar e implementar aparte un check inocuo; no usar delivery como prueba. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| UNKNOWN_RESULT_RUNBOOK_UNVERIFIED | secondary_on_call (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Ensayar UNKNOWN por provider y aprobar revisión externa sin retry automático. | Sólo preparar; ejecución futura con permiso | Sí | Sí | Alto: legal/datos/efectos |
| UNSUPPORTED_HISTORY | engineering_owner (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Resolver contrato histórico no soportado con nueva autorización; conservar unknown. | Sí, en alcance técnico futuro autorizado | Sí | No para diseñar; sí para aceptación productiva | Medio: compatibilidad/integridad |
| VOLUME_OUTSIDE_POLICY | engineering_owner (sin asignar) | Recibo/hash/código/tenant/expiry y revisión humana de evidencia específica | Mantener cohorte dentro de policy F64; un warning no elimina blockers. | Sí, en alcance técnico futuro autorizado | Sí | No para diseñar; sí para aceptación productiva | Medio: compatibilidad/integridad |

## Operación/observación futura y seguridad

Primera operación propuesta: gasto auténtico necesario y pequeño, documento real,
confirmación humana exacta, recibo/cobertura/EE/Operation verificables. Void sólo
por necesidad de corrección real y conserva prueba; no dinero/caja fake ni borrado.
Sin operación necesaria, no ejecutar ninguna. T0/+15m/+1h/+2h/+24h/+72h:
2h atención activa +72h observación como propuesta, no SLO ni automatización.
Cada efecto futuro revalida evidence TTL5min; un preflight no cubre toda la ventana.

Hard stops, rol primario/suplente/legal/custodio, pausa D/F, UNKNOWN separado
AEAT/Meta/email, monitoring F más custodia backup, restore E y runtime están
paso a paso en el runbook/checklist. No CLI pública productiva ficticia; las APIs
internas de D/F están señaladas como futuras y bloqueadas, no se ejecutan.
Providers siguen SAFE_CHECK_UNIMPLEMENTED; diseñar GET no demuestra autenticación,
sender, delivery o fiscal chain, ni production_observed. SMTP TLS no acredita
credential; Gmail profile puede requerir scope no existente: no ampliarlo aquí.

## Pruebas y gates

Una selección completa fresca final de **98 PASS /0 skips /0 FAIL /0 ERROR en 225.323 s**:
34 PilotReadinessReport/CLI/catálogos/aislamiento/no-effects; Core16, EconomicEvents21,
Readiness27. No agregación de retests. La general G-PREP no se ha ejecutado de nuevo:
código puro opt-in sin routing/adapters/DB; verificación proporcional y base F completa
claramente separadas. No matriz nueva PG: no repositorio/SQL/migración ejecutable.
15 fragmentos SQL preparados validados por EXPLAIN/query_only en schema79 sintético;
dos de catálogo PG no ejecutados, no se finge validación en SQLite.
Ruff global/Bandit global y paquete final/dependency audit/documentation truth/enlaces
PASS; credential scan final completo PASS sobre todos los archivos versionados. Excepción exacta, sólo tres
SHA no secretos del report: público F y dos hashes computados de declaraciones,
ningún dato real, detector/filtro ni excepción anterior relajados.

Fallos intermedios encontrados/corregidos: nombres invoice_records/invoice_payments
y started_at del esquema real para SQL preparado; sin modificar esquema/old code.
Helper de comparación normalizaba CRLF de tres imágenes binarias; se corrigió la
comparación raw y confirmó bytes idénticos, ninguna imagen modificada.
F base ya tiene CI remota completa run37743993745 PASS sobre F exacto:
2074 total/2072 PASS/2 skips/0 FAIL/ERROR, 2353.757s; PG687, JS9.
No se presenta esa ejecución como suite general nueva de G-PREP.

Prueba de ausencia de efectos: snapshot **valores** de todas las tablas de DB
SQLite nueva descartable, cinco flags exactos antes/después; get_conn/prepare D/
check F/socket.connect prohibidos durante report/proposals. AST del paquete
excluye DB/adapters/dispatch/handoff/network imports. Código anterior byte a byte.
SQL de lectura preparado contrastado por EXPLAIN QUERY PLAN en schema79 sintético
query_only; dos consultas de catálogo PG requieren futura validación autorizada,
no se anuncian como PostgreSQL probado. No SQL real ni conexión nueva de dominio.

## Riesgos/limitaciones

- Report es diagnóstico de preparación, no un verificador de evidencia externa real
  ni permiso; retirar blockers exigirá implementación/autorización futura, no flags.
- Sin elección de negocio/perfil, roles, aprobación profesional, backup/restore/
  runtime actuales, no puede existir PILOT_READY. Cuenta vacía no se asume.
- Checks inocuos son diseño; AEAT y SMTP carecen de check productivo suficiente.
- Guard D producción/recovery A caducada pendientes, no se promete pause/resume real.
- Counts SQL son diagnóstico parcial, requieren catálogo A completo/FKs/related/hash.
- Migrations/General Ledger/Tax/Open Items/reporting nuevo/G-LIVE/H no tocados.

## Autoauditoría de la orden (ámbito real/G-PREP)

1. ¿Activó un negocio real? **NO**.
2. ¿Consultó producción? **NO**.
3. ¿Consultó Noesis19FQA? **NO**.
4. ¿Leyó un backup real? **NO**.
5. ¿Hizo provider I/O real? **NO**.
6. ¿Creó real production attestations? **NO**.
7. ¿Aprobó policy E? **NO**.
8. ¿Cambió PRIVACY_NOT_READY real? **NO**.
9. ¿Cambió los cinco flags? **NO**.
10. ¿Hizo handoff? **NO**.
11. ¿Creó generation/grants? **NO**.
12. ¿Creó Financial Operation real? **NO**.
13. ¿Creó EE real? **NO**.
14. ¿Creó actividad económica falsa real? **NO**.
15. ¿Seleccionó negocio piloto sin humano? **NO**.
16. ¿Ocultó blocker reduciendo perfil? **NO**.
17. ¿Consideró sandbox/local suficiente para producción? **NO**.
18. ¿Consideró backup existente como restore verificado? **NO**.
19. ¿Consideró rehearsal sintético como pilot? **NO**.
20. ¿Rebaseó A–F sobre nuevo main? **NO**.
21. ¿Mezcló main en G-PREP? **NO**.
22. ¿Desplegó? **NO**.
23. ¿Autorizó G-LIVE? **NO**.
24. ¿Inició H? **NO**.

Sólo fixtures sintéticos aislados de tests. Documentación pública consultada para
diseño de GET no equivale a provider I/O de cuenta real ni evidencia productiva.

## Inventario de entrega

- [.secrets.baseline](../../.secrets.baseline)
- [AGENTS.md](../../AGENTS.md)
- [docs/Arquitectura.md](../../docs/Arquitectura.md)
- [docs/Decisiones.md](../../docs/Decisiones.md)
- [docs/Estado-actual-main.md](../../docs/Estado-actual-main.md)
- [docs/Mapa-codigo.md](../../docs/Mapa-codigo.md)
- [docs/Registro-QA.md](../../docs/Registro-QA.md)
- [docs/Registro-cambios.md](../../docs/Registro-cambios.md)
- [docs/Tareas-vivas.md](../../docs/Tareas-vivas.md)
- [docs/architecture/FASE-1.10-plan.md](../../docs/architecture/FASE-1.10-plan.md)
- [docs/architecture/FASE-1.10G-prep-cierre.md](../../docs/architecture/FASE-1.10G-prep-cierre.md)
- [docs/architecture/FASE-1.10G-prep-orden.md](../../docs/architecture/FASE-1.10G-prep-orden.md)
- [docs/architecture/FASE-1.10G-prep-report.json](../../docs/architecture/FASE-1.10G-prep-report.json)
- [docs/architecture/FINANCIAL-PILOT-CHECKLIST-v1.md](../../docs/architecture/FINANCIAL-PILOT-CHECKLIST-v1.md)
- [docs/architecture/FINANCIAL-PILOT-PROVIDER-CHECKS-v1.md](../../docs/architecture/FINANCIAL-PILOT-PROVIDER-CHECKS-v1.md)
- [docs/architecture/FINANCIAL-PILOT-READINESS-v1.md](../../docs/architecture/FINANCIAL-PILOT-READINESS-v1.md)
- [docs/architecture/FINANCIAL-PILOT-READONLY-QUERIES-v1.sql](../../docs/architecture/FINANCIAL-PILOT-READONLY-QUERIES-v1.sql)
- [docs/architecture/FINANCIAL-PILOT-RUNBOOK-v1.md](../../docs/architecture/FINANCIAL-PILOT-RUNBOOK-v1.md)
- [docs/architecture/README.md](../../docs/architecture/README.md)
- [docs/areas/06-rgpd-y-seguridad.md](../../docs/areas/06-rgpd-y-seguridad.md)
- [docs/areas/07-lo-automatico.md](../../docs/areas/07-lo-automatico.md)
- [docs/areas/08-financial-core.md](../../docs/areas/08-financial-core.md)
- [docs/project-state.json](../../docs/project-state.json)
- [src/noesis/financial_pilot/__init__.py](../../src/noesis/financial_pilot/__init__.py)
- [src/noesis/financial_pilot/__main__.py](../../src/noesis/financial_pilot/__main__.py)
- [src/noesis/financial_pilot/contracts.py](../../src/noesis/financial_pilot/contracts.py)
- [src/noesis/financial_pilot/report.py](../../src/noesis/financial_pilot/report.py)
- [tests/test_financial_pilot.py](../../tests/test_financial_pilot.py)

No datos, secretos, dumps, bases, uploads ni artefactos de QA real en este inventario.

## Criterios de cierre G-PREP

| Criterio | Resultado |
|---|---|
| Rama local desde F exacto, sin main/rebase/integración/push | PASS |
| Contrato report cerrado/determinista/tenant/expiry y anti-fake READY | PASS |
| Perfil financiero mínimo derivado C y comparación fiscal/canales | PASS |
| Policy provisional + PRIVACY_NOT_READY conservados | PASS |
| Checks inocuos diseñados sin ejecución/attestation | PASS |
| EMPTY/queries/backup/restore/runtime/operator checklists | PASS, verificación real pendiente |
| Pause/UNKNOWN/monitoring/hard-stops/primera operación/observación | PASS documental, aceptación operativa real pendiente |
| Tabla exacta de blockers/owners/evidencia/acciones/riesgos | PASS |
| Pruebas nuevas/regresiones/gates/AST/enlaces | PASS, sin nueva matriz PG ni suite general G-PREP |
| Ausencia de efectos Core/red/flags y no migration | PASS |
| Gobernanza/orden/estado/QA/mapa/decisiones/bitácora | PASS |
| Autoauditoría 24 respuestas peligrosas NO | PASS |
| Readiness del piloto real | PILOT_BLOCKED — EXTERNAL PREREQUISITES PENDING |

No push tras commit local. G-LIVE no autorizado; H no iniciada.
