# Fase 1.10F — CODE-VERIFIED PASS TÉCNICO local

**1.10F CODE-VERIFIED PASS TÉCNICO — REAL PROVIDER ATTESTATIONS PENDING FOR PILOT**

Entrega exclusivamente local en `codex/phase-1-10f`. Padre exacto autorizado:
`e02492283b6cfc07d90740fb099463be64329807`. El commit de entrega se consulta en HEAD;
el informe forma parte de él. No push/PR/merge/deploy ni G–H.

[Orden íntegra](FASE-1.10F-orden.md), [ADR024](ADR-024-providers-integrated-preflight.md),
[contrato](FINANCIAL-PROVIDERS-PREFLIGHT-v1.md),
[límites](FINANCIAL-OPERATIONAL-LIMITS-v1.md), [runbook](FINANCIAL-PROVIDERS-runbook.md).

## Contratos, catálogo y arquitectura

Monolito modular: financial_providers contiene contratos, configuración, attestations,
repositorio, schema, preflight, dispatch, transporte, observabilidad y límites. Conexión,
pool/gate/transacciones existentes; FinancialSession exacta y Decimal/NUMERIC.
La fachada db.py incorpora shims de encolado y el guard de conservación de ocho tablas F, sin nuevo núcleo financiero.
La IA no recibe autoridad ni interfaces para aprobar/activar/verificar providers.

| Provider | Implementaciones | Capability de la spec C única |
|---|---|---|
| AEAT_VERIFACTU | aeat_soap | provider.aeat_dispatch |
| META_WHATSAPP | meta_graph | channel.whatsapp_financial |
| EMAIL_DELIVERY | brevo / smtp / gmail | provider.email_delivery |
| Sin provider | — | channel.web_financial |

Desconocidos bloqueados. Banking continúa BANK_CAPABILITY_UNVALIDATED.
ProviderAttestation v1 cerrado: tenant/UUID/provider/implementation/capability/environment,
level, checker/código/schema79, actor/sesión, fechas/expiry, configuration_fingerprint,
credential_fingerprint, PASS/BLOCKED/reasons y evidencia cerrada, source_attempt_uuid sólo
observed. JSON canónico/SHA-256, ningún float, secretos/PII/respuesta libre/path.
Cuatro semánticas: local_verified, sandbox_verified, production_config_verified,
production_observed; no escalera numérica. Observed requiere resultado real durable.
Huella HMAC privada derivada del secreto estable; certificado público SHA-256.
Rotación/drift/expiry invalida uso sin editar evidencia anterior.

## Preflight, D y readiness

FinancialIntegratedPreflight congela A FULL UUID/hash/profile/closure/dependencies,
history/source/configuración, volumen, E policy/export UUID/hash, attestations exactas,
incertidumbre/pendientes, actor/sesión/código/schema, G/control y límites/expiry.
Sólo escribe recibo F; replay exacto por UUID o conflicto por contexto distinto.
Every_use antes de preparar/avanzar D; schema79 enable/resume exige binding separado
al recibo PASS. D mantiene request v1/schema77, guard de producción y confirmación
humana durable exacta. Matrices anteriores se ejecutan explícitamente en 77/78.
A verifica pruebas existentes por SELECT; ninguna evaluación previa se reescribe.
Metadata schema exacta usa conexión prestada, sin normalización legacy a float.

## Dispatch, pausa, cierre y observabilidad

Binding outbox→source/operation→G→capability/provider explícito, no asunto/cuerpo/
importe/teléfono. Fiscal usa coverage y record_id exactos. Creación/binding es atómica.
Legacy financiero sin binding no se adopta: factura/cobro/financial-review Meta,
invoice email y fiscal se retienen post-handoff. Genéricos no financieros conservados.
PDF/upload directo bloqueado post-handoff mientras carezca de intento durable.

TX1 claim/attempt + start durable y revalidación, I/O fuera de TX/gate, TX2 resultado
y outbox atómicos. Un intento, una llamada; SUCCESS/FAILED_TERMINAL/UNKNOWN/ABORTED.
Timeout o respuesta perdida nunca acredita rechazo/aceptación. Duplicado AEAT depende
del parser del registro concreto. Email/Meta UNKNOWN no auto-reintentan.
AEAT pausado sólo DRAIN_COMMITTED de obligación exacta; Meta/email HOLD_DISPATCH.
Cierre E domina nuevos claims/drain. Resultado ya iniciado se conserva incluso tras
invalidación de sesión. Observed/telemetría posterior no puede repetir el side effect.
Clientes actuales AEAT/Meta/email/Gmail reutilizados; ningún cliente nuevo de delivery.

Read model SELECT por tenant: estado/G/grants, attestations/expiry, preflight, intentos/
UNKNOWN/errores, colas/edades, history/fence, E, receipts y motivos cerrados. Sin PII,
alertas remotas ni writes de autoridad. Fechas legacy naive no permiten inventar edad.
Observaciones opcionales append-only: sólo UUID/hash/motivo cerrado.

M79 agrega ocho tablas propias y guards connection/TX/tenant/inmutabilidad. Runtime
PostgreSQL restringido, sin clave HMAC del verifier. Downgrade sólo cuando F vacía.
Restore79 real de datos **sintéticos** conserva UNKNOWN, attempts y evidencia económica,
sin replay. FKs activas; se validan ciclos diferidos antes de reactivar triggers USER.

## Rehearsal, concurrencia, crashes y ausencia de efectos

Rehearsal F usa cut/inventory certificado/import terminal/reconciliación PASS reales
del software y A FULL calculada por su evaluator, sin fabricar FULL. Cohorte vacía
económicamente con identidad fiscal; B no tiene antecedente aplicable. Policy E
aprobada sólo en fixture aislado, export, providers simulados, F, D, ExpenseCapture
humano real, fake dispatch/result durable, export, pause/recovery/resume G2/export.
Replay de G1 devuelve resultado sin segundo envío. Integración E complementaria con
histórico expense exacto e inspección B conservada, D/export/cierre/restore sintéticos.
Ninguno demuestra AEAT/Meta/email ni policy legal real.

Procesos PostgreSQL reales: mismo/distinto binding, mismo preflight UUID, seis crashes
con os._exit; threads y progreso de otro tenant durante I/O simulado. Límites gate
acotados por negocio. Ventanas: antes claim, tras claim, antes I/O, tras I/O,
durante TX2 y tras commit. Start sin resultado nunca produce una segunda llamada.
Recuperación UNKNOWN exige detener/verificar antes el worker original.
Snapshots prueban que resultado/transporte no añade EE/Operations ni modifica grants,
generaciones, history, policy E o cinco flags. Certificados/credenciales sólo marcadores
sintéticos; bytes privados y Gmail decryptados no aparecen en export/evidence.

## Pruebas frescas del código final

Python 3.12.3; SQLite 3.45.1; PostgreSQL nativo 16.15 en cluster nuevo loopback descartable.
Sin datos reales. Outbound Python externo bloqueado; PostgreSQL libpq sólo localhost/noesis_ci.
Suite general de una sola ejecución final: **2074 total; 2072 PASS;
2 skips; 0 FAIL; 0 ERROR; 1751.766 s**. Matriz F SQLite 63 PASS,
incluida íntegra en esa ejecución. Ejecución fresca paralela por archivos en cuatro procesos aislados; el multiset de casos recogidos coincide exactamente con la discovery completa y el número ejecutado es idéntico. No se suman ejecuciones diagnósticas anteriores o interrumpidas.

Skips generales previstos, cubiertos por PostgreSQL:

- `test_pg_direct_sql_busy_fails_closed_no_gate_inversion (test_financial_history_cutoff.HistoryCutoffSQLite.test_pg_direct_sql_busy_fails_closed_no_gate_inversion)`: PG gate try-lock; SQLite BEGIN IMMEDIATE probado en carrera común.
- `test_pg_repeatable_snapshot_direct_sql_rejected (test_financial_history_cutoff.HistoryCutoffSQLite.test_pg_repeatable_snapshot_direct_sql_rejected)`: Aislamiento PostgreSQL.

| Matriz PostgreSQL | Casos | Resultado | Duración s |
|---|---:|---|---:|
| Core | 6 | PASS | 0.121 |
| Operations | 37 | PASS | 9.412 |
| Economic Events | 28 | PASS | 21.862 |
| Borrowed writers | 18 | PASS | 13.26 |
| Invoice | 27 | PASS | 32.356 |
| Payment Bank | 41 | PASS | 42.796 |
| Purchasing | 44 | PASS | 31.299 |
| Channels | 50 | PASS | 28.166 |
| History Inventory | 37 | PASS | 30.743 |
| History Cutoff | 50 | PASS | 41.878 |
| History Import | 25 | PASS | 41.789 |
| History Reconciliation | 31 | PASS | 148.317 |
| A | 29 | PASS | 21.13 |
| B | 52 | PASS | 30.941 |
| C | 46 | PASS | 59.403 |
| D | 35 | PASS | 65.065 |
| E | 62 | PASS | 38.437 |
| F | 69 | PASS | 146.727 |

Total matrices PostgreSQL: **687 PASS**, 0 FAIL/ERROR. JavaScript: 9 PASS, 0 skips/fail.
36 rutas HTTP PostgreSQL, backup/restore sintético, 32→79, código53 sobre79,
rollback79→55→54→53→54→55→79, privacidad/account deletion y transporte: PASS.
Integraciones E history SQLite/PostgreSQL: PASS. Migration SQLite 0→79→0→79: PASS.
Ruff, Bandit, credential scan (incluye archivos nuevos), dependency audit, verdad
documental y enlaces locales: PASS. AST 178 funciones y 78 entradas antiguas intactos.
Workflow añade matriz F PostgreSQL; no se ejecutó CI remota ni se publicó código.
Artefactos locales de validación: `C:\Users\mikic\AppData\Local\Temp\noesis-f-validation-4cc53c436e434ea389de1ffd976c2579` (sólo resultados sintéticos; fuera de Git). Suite final válida: `general-final-fresh-complete/general.json` y `general-complete-final.log`; copia resumida en `general.json`. Los logs `general-final.log`, `fresh-general/` y `general-final-fresh-parallel/` son diagnósticos anteriores y no cuentan para el cierre.

## Mediciones del código final

| Motor | Caso | Tiempo s | Pico Python bytes | Resultado |
|---|---|---:|---:|---|
| sqlite | preflight_empty | 0.188 | 230065 | PASS |
| sqlite | operational_snapshot_1 | 0.094 | 114503 | lectura |
| sqlite | preflight_64_history_items | 0.641 | 858440 | BLOCKED |
| sqlite | operational_snapshot_64 | 0.125 | 828987 | lectura |
| sqlite | preflight_three_providers | 0.36 | 463993 | PASS |
| sqlite | operational_snapshot_501_attempts | 0.047 | 74722 | lectura |
| sqlite | preflight_501_attempts_resume | 0.672 | 909948 | PASS |
| postgres | preflight_empty | 0.234 | 358650 | PASS |
| postgres | operational_snapshot_1 | 0.047 | 91290 | lectura |
| postgres | preflight_64_history_items | 0.469 | 838400 | BLOCKED |
| postgres | operational_snapshot_64 | 0.078 | 827973 | lectura |
| postgres | preflight_three_providers | 0.281 | 594861 | PASS |
| postgres | operational_snapshot_501_attempts | 0.016 | 87708 | lectura |
| postgres | preflight_501_attempts_resume | 0.656 | 901642 | PASS |

Cada motor prepara 501 attempts reales del software con transportes simulados.
Memoria medida con tracemalloc, no RSS ni SLO; preparar fixture no es latencia de preflight.
Vacío incluye un item de identidad fiscal; 64 items = esa identidad +63 gastos legacy.
Ese caso bloquea por evidencia legacy insuficiente: medirlo no promueve su certeza.

## Límites, riesgos y diferencias necesarias

Política operativa v1 cerrada:64 history items, gate1s, warning handoff2s, revisión5s,
readiness/preflight/attestation5min, corte warning5min/intervención15min. Nunca TTL
libera fence; nunca warning deshace commit. SQLite serializa writes por archivo.
Export/read model materializados: paginación interna, sin garantía de memoria constante.
No exactly-once externo. UNKNOWN requiere revisión concreta, no retry/reset por IA.
G antigua no se adopta tras resume. A caducada bloquea resume79; F no implementa reset
unilateral de A/control plane: resolverlo requiere diseño/autorización antes del piloto.

Cambios necesarios respecto al esquema78: export conserva D completo pero su prueba
económica de readiness79 excluye lifecycle D para evitar auto-invalidación circular;
F congela policy/export por UUID/hash. Snapshot D79 excluye metadata puramente de
transporte fiscal, sin excluir fuentes/valores/hashes financieros. Request/hashes previos
intactos. Fixtures D77/E78 fijan su versión; F79 cubre integración vigente.
Restore admite ciclos FK verificables, sin suspender FKs ni reescribir migraciones. La suite general detectó una omisión de F en el registro de baja: se añadió el bloqueo explícito de las ocho tablas F y una prueba de attestation aislada conservada, sin permitir borrado de evidencia. También se actualizó la expectativa global de versión del test history exactamente de 78 a la migración autorizada 79, manteniendo los cinco flags OFF y todos los hashes/AST anteriores. Se amplió el recorder DDL para devolver la definición E real consultada por M79; sus tres comprobaciones de FKs, placeholders y SQLSTATE permanecen íntegras y pasan.
Clasificación legacy usa sólo metadatos declarados de productores; no heuristic matching.

## REAL-WORLD BLOCKERS BEFORE G

Todos pendientes; F no los resuelve con fixtures:

1. Policy E REAL **PROVISIONAL / PENDIENTE DE APROBACIÓN PROFESIONAL**; PRIVACY_NOT_READY
   sigue bloqueando readiness real. Ningún approved_for_operation sintético es config real.
2. Negocio piloto y perfil/closure exactos, volumen y antecedentes/historia concretos.
3. Providers exactos del closure; checks readonly inocuos aún SAFE_CHECK_UNIMPLEMENTED.
4. Attestations productivas reales vigentes, sin transformar mocks en evidencia externa.
5. Backup/restaurabilidad reales autorizados y custodia/actualidad de supresiones.
6. Runtime/schema79/deployment compatibility, estabilidad de clave y procedure de renovación A.
7. Operador responsable/suplente/on-call; autoridad humana durably vinculada.
8. Monitorización operativa, expiración y alertas/procedimiento local de atención.
9. Pausa, drain permitido y recovery/resume, incluidas expiración A y generaciones antiguas.
10. Procedimiento para UNKNOWN concreto, worker detenido, evidencia externa y revisión humana.

## Autoauditoría explícita de treinta preguntas

| # | Pregunta de la orden | Respuesta | Evidencia / alcance |
|---:|---|---|---|
| 1 | ¿Puede F activar producción? | NO | D conserva el guard IS_PRODUCTION; ninguna activación real. |
| 2 | ¿Puede F quitar el guard production de D? | NO | No modifica ese guard ni ofrece bypass. |
| 3 | ¿Puede F cambiar los cinco flags? | NO | No asigna ni cambia defaults/variables reales; patches exclusivos de fixtures. |
| 4 | ¿Puede F aprobar la policy legal E? | NO | No; REAL sigue provisional y sólo fixtures aislados simulan aprobación. |
| 5 | ¿Puede local_verified habilitar producción? | NO | Nivel insuficiente en entorno productivo. |
| 6 | ¿Puede sandbox_verified habilitar producción? | NO | Entorno/nivel exactos; sandbox nunca acredita producción. |
| 7 | ¿Puede una attestation de otro business usarse? | NO | SELECT y FKs compuestos por tenant; pruebas cross-tenant. |
| 8 | ¿Puede una attestation de otro provider usarse? | NO | Spec C exacta y validación capability/provider. |
| 9 | ¿Puede una attestation expirada usarse? | NO | Expiry every_use bloquea claim/start/handoff. |
| 10 | ¿Puede config drift mantener una attestation válida? | NO | Recalcular HMAC; sender, Graph/config/conexión/certificado se revalidan. |
| 11 | ¿Puede credential rotation mantener una attestation válida? | NO | Fingerprint privada distinta; requiere nueva UUID. |
| 12 | ¿Puede readiness llamar un provider? | NO | Sólo SELECT de pruebas; socket bloqueado en fixtures. |
| 13 | ¿Puede handoff llamar un provider? | NO | Verificación de recibos/F binding y autoridad humana exacta; cero red. |
| 14 | ¿Puede preflight automático hacer provider I/O? | NO | No automático; network OFF; check externo actual bloqueado incluso con permiso. |
| 15 | ¿Puede un token/private key aparecer en evidence? | NO | Sólo HMAC/certificado público SHA; marcadores Meta/AEAT/SMTP/Gmail excluidos. |
| 16 | ¿Puede F exportar la fingerprint key? | NO | No pertenece al catálogo/export/logs/docs ni se persiste como evidencia F. |
| 17 | ¿Puede un SQL directo crear production_observed válido? | NO | Runtime sin clave, contexto HMAC connection/TX y guard de resultado real. |
| 18 | ¿Puede production_observed crearse sin provider result? | NO | Sólo SUCCEEDED real durable, start y attestation original no sintética. |
| 19 | ¿Puede provider result crear un EE económico nuevo? | NO | Sólo resultado/outbox/F; snapshots económicos sin cambios. |
| 20 | ¿Puede email/Meta unknown auto-reintentarse? | NO | Resultado UNKNOWN terminal en F; worker/replay nunca repiten llamada. |
| 21 | ¿Puede AEAT timeout fingirse como rechazo/éxito? | NO | Timeout/malformed/excepción quedan UNKNOWN; parser específico conserva aceptación/rechazo. |
| 22 | ¿Puede pause iniciar una nueva comunicación financiera? | NO | Email/Meta HOLD; AEAT sólo obligación committed exacta DRAIN_COMMITTED. |
| 23 | ¿Puede closure E iniciar/drain provider nuevo? | NO | Assert_open/auth/suppressions dominan claim/start y worker. |
| 24 | ¿Puede una generación vieja autorizar dispatch nuevo? | NO | Grant/control/binding exactos; no adoptar G antigua tras resume. |
| 25 | ¿Puede un outbox financiero sin binding fuerte despacharse post-handoff? | NO | Fiscal/email invoice/Meta financiero explícito retenidos; ningún fallback/adopción. |
| 26 | ¿Puede una comunicación no financiera romperse por F? | NO | Email y WhatsApp genéricos mantienen selección legacy, demostrados y regresionados. |
| 27 | ¿Puede provider network ejecutarse dentro de una TX DB? | NO | Dispatch libera gate/TX antes de cliente; progresión de otro tenant probada. |
| 28 | ¿Puede un crash tras provider side effect provocar retry ciego? | NO | Start durable; recuperación explícita UNKNOWN, una única llamada por attempt. |
| 29 | ¿Puede el rehearsal sintético declararse prueba real? | NO | Sólo software/control-flow; ninguna attestation real/piloto acreditados. |
| 30 | ¿Se inició 1.10G? | NO | No G–H, piloto, push, merge ni deploy. |

## Criterios finales F

| Criterio | Resultado |
|---|---|
| Catálogo cerrado y capability→provider exacto | PASS |
| Attestations durables/inmutables; niveles separados | PASS |
| Secretos excluidos; huellas privadas; drift/expiry | PASS |
| Preflight integrado durable y D79 exige binding exacto | PASS |
| Readiness/handoff sin provider I/O | PASS |
| Dispatch financiero post-handoff sin fallback legacy | PASS |
| Pausa/cierre fail closed; UNKNOWN sin retry inseguro | PASS |
| Clientes existentes reutilizados | PASS |
| Observabilidad sin PII/autoridad; límites codificados | PASS |
| Rehearsal completo sintético; concurrencia/crashes/restore | PASS |
| SQLite/PostgreSQL/regresiones/suite/gates frescos | PASS |
| Estado real bloqueado honestamente y blockers antes de G | PASS |
| Providers reales comprobados / autorización piloto | PENDING — fuera de F |
| No push/merge/deploy/producción/QA/backups reales/provider I/O/G | PASS |

No filesystem cleanup real, revocación remota, restore real ni destrucción de QA.
Main local permanece en e95c19beea7a9cda291f045459b06eb639e171e5 y la referencia local
origin/main en acff183319f476a5f0b25a820751dca4523fd8fd; no consultas remotas ni pushes.
Rollback: pausa/conservar/diagnosticar/revalidar. Downgrade79 sólo sin evidencia F;
no eliminar pruebas para hacerlo posible. Producción mantiene guard D y flags OFF.

## Archivos creados/modificados

- `.github/workflows/ci.yml`
- `AGENTS.md`
- `docs/03-whatsapp-e-integraciones/Conectar-APIs.md`
- `docs/Arquitectura.md`
- `docs/Decisiones.md`
- `docs/Estado-actual-main.md`
- `docs/Mapa-codigo.md`
- `docs/Registro-QA.md`
- `docs/Registro-cambios.md`
- `docs/Tareas-vivas.md`
- `docs/architecture/ADR-024-providers-integrated-preflight.md`
- `docs/architecture/FASE-1.10-plan.md`
- `docs/architecture/FASE-1.10F-cierre.md`
- `docs/architecture/FASE-1.10F-orden.md`
- `docs/architecture/FINANCIAL-OPERATIONAL-LIMITS-v1.md`
- `docs/architecture/FINANCIAL-PROVIDERS-PREFLIGHT-v1.md`
- `docs/architecture/FINANCIAL-PROVIDERS-runbook.md`
- `docs/architecture/README.md`
- `docs/areas/01-vision-general.md`
- `docs/areas/03-cerebro.md`
- `docs/areas/04-facturas.md`
- `docs/areas/05-correo.md`
- `docs/areas/06-rgpd-y-seguridad.md`
- `docs/areas/07-lo-automatico.md`
- `docs/areas/08-financial-core.md`
- `docs/project-state.json`
- `src/noesis/core/persistence.py`
- `src/noesis/db.py`
- `src/noesis/financial_activation/capabilities.py`
- `src/noesis/financial_activation/contracts.py`
- `src/noesis/financial_activation/evaluator.py`
- `src/noesis/financial_activation/handoff.py`
- `src/noesis/financial_activation/readiness_verifier.py`
- `src/noesis/financial_antecedents/contracts.py`
- `src/noesis/financial_history/fence.py`
- `src/noesis/financial_history/schema_compatibility.py`
- `src/noesis/financial_operations/service.py`
- `src/noesis/financial_privacy/contracts.py`
- `src/noesis/financial_privacy/dispatch.py`
- `src/noesis/financial_privacy/export.py`
- `src/noesis/financial_privacy/repository.py`
- `src/noesis/financial_privacy/retention.py`
- `src/noesis/financial_providers/__init__.py`
- `src/noesis/financial_providers/attestations.py`
- `src/noesis/financial_providers/configuration.py`
- `src/noesis/financial_providers/contracts.py`
- `src/noesis/financial_providers/dispatch.py`
- `src/noesis/financial_providers/limits.py`
- `src/noesis/financial_providers/observability.py`
- `src/noesis/financial_providers/preflight.py`
- `src/noesis/financial_providers/repository.py`
- `src/noesis/financial_providers/schema.py`
- `src/noesis/financial_providers/transports.py`
- `src/noesis/financial_providers/validation.py`
- `src/noesis/migrations.py`
- `src/noesis/tools.py`
- `src/noesis/web/backups.py`
- `src/noesis/web/scheduler.py`
- `src/noesis/web/whatsapp.py`
- `tests/financial_providers_benchmark.py`
- `tests/financial_providers_worker.py`
- `tests/postgres_financial_privacy.py`
- `tests/postgres_financial_providers.py`
- `tests/test_financial_activation_handoff.py`
- `tests/test_financial_history.py`
- `tests/test_financial_privacy.py`
- `tests/test_financial_providers.py`
- `tests/test_platform.py`
