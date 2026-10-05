# Cierre de Fase1.9E — Reconciliación histórica durable

5-oct-2026. Estado: implementación, matrices locales y CI final PASS.
Cierre técnico1.9E: 52 criterios PASS, cero FAIL. Sin1.9F, producción ni activación.
[Orden](FASE-1.9E-orden.md), [contrato](FINANCIAL-HISTORY-RECONCILIATION-v1.md),
[ADR018](ADR-018-financial-history-reconciliation.md).

## 1. Arquitectura

Servicio interno especializado y repositorio E sobre conexión/TX/gate compartidos.
Composición con C/D para precondiciones de lectura; no hereda sus APIs de escritura.
Verificador SELECT, sin productor/bridge/canal/provider. Únicas escrituras E en run
y findings propios. Monolito modular, IA sin autoridad, Decimal extremo a extremo.

## 2. Archivos

Nuevos `src/noesis/financial_history/reconciliation{,_contracts,_repository,
_schema,_verifier}.py`; contrato de pruebas común, suite SQLite, suite/worker PG;
orden íntegra, ADR018, contrato v1 y este informe. Modificados migrations.py, guards
de versiones B/C/D y lista estructural de retención de db.py; test LATEST_VERSION;
CI PG y timeout general. Gobernanza: AGENTS, project-state, Inicio, Estado, Tareas,
Registro-cambios/QA, Mapa, Arquitectura, Decisiones, README/plan y guías01/04/06/07/08
y técnica. Ningún cambio funcional en productores financieros, fiscal ni UI.

## 3. Migration

73, dos tablas y sus guards/índices; downgrade con evidencia prohibido.
Migraciones63–72 intactas. Guard nuevo sobre batch terminal evita nuevos intents
sin prohibir recuperar resultados D existentes. Compatibilidad B/C/D73 explícita.

## 4. Schema

Run running/frozen, PASS/BLOCKED, contexto tenant/epoch/generation/manifest/batch,
operador actual/sesión, fechas y seis hashes+result. Finding append-only con catálogo
cerrado, item nullable global, expected/actual hash/ref y evidencia mínima sin PII.
FK compuestas, running único por business/batch y lectura paginada/integridad.

## 5. Catálogo findings

Los17 códigos de la orden, sin añadidos, todos blocking. Enum/canonical/version/ref
cerrados; BATCH_NOT_TERMINAL normalmente rechaza antes de insertar run. Detalle en
el contrato v1. Ninguna fila de éxito por item.

## 6. Lifecycle

Running→frozen atómico en una TX. Frozen/identidad inmutables SQL. Findings sin
UPDATE/DELETE/append posterior. Múltiples runs frozen del mismo batch permitidos.
Lectura verifica resultado y findings; ninguna reparación.

## 7. Precondiciones

Schema73, sesión/tenant/suscripción/historical.record, flags OFF, epoch/control y
generation activos, scope C actual, hashes/comparison/plan coherentes, C frozen
certifiable sin eligible_for_import. Batch completed/partial/blocked y sin recording.
Prepared/running rechaza sin run; opened_by conserva política C/D. Revalida al sellar.

## 8. Reconciliation algorithm

Plan/raw congelados → EE completos y proofs agrupados → todos los resultados D →
fuentes reales scopeC → coberturas → grafo → huérfanos → hashes → frozen. Identidad
y evidencia, jamás counts como sustituto. Una discrepancia implica BLOCKED.

## 9. Source verification

RawReader paginado completo, incluyendo documentos/perfiles/fiscal/recurrentes y
EE/links/coverage. Reproduce conjunto C separando SOLO adiciones D acreditadas y
explicadas en manifest actual. El delta permanece en event_set_hash; cualquier
otra alta/baja/cambio bloquea. No excluye categorías nuevas del scope.

## 10. Item accounting

Candidate/covered_existing exige resultado terminal apropiado. C/D, incidencias,
dependencias pendientes y faltantes bloquean. Out_of_scope/excluded congelados
pueden no tener evento; skipped debe ser coherente y sin evento inesperado. Un
padre excluido/B no satisface dependencia. No reclasifica.

## 11. Import result verification

Estado/completion_key/completed/canonical/manifest/raw/candidato/identidad/event/
hash/op/auth exactos. Recorded/original y existing/covered distinguidos. Batch
blocked bloquea; partial con candidato pendiente bloquea. Partial heredado SOLO
por antiguos v2 no durables puede PASS una vez todos estén incorporados y no quede
impedimento. Es interpretación explícita de «cuando corresponda», sin reescribir D.

## 12. Operations/auth verification

Operación histórica PREPARED/namespace historical/request exacto/registrador/
resultado NULL/committed_at NULL. Una unknown exacta sin actor/session/mandato/
expires/revoked, canal historical y permiso historical.record. Human/mandate/
approved/committed incompatibles. Búsqueda global de operaciones/auth huérfanas.

## 13. Economic Event verification

StoredEvent durable completo, canonical/content/record hash, columnas monetarias,
source/type/revision, fechas/provenance/UUID/batch/slot/idempotency/sequence y proof
original único. Sin proof bloquea; contenido alterado nunca se reconstruye para reparar.
Matriz cerrada: tres v2 históricos especiales, no invoice histórico v2.

## 14. Dependency graph

Links exactos congelados, business/target/type/revisión, padres A verdaderos y
evidencia acreditada. Live padre requiere coverage y autoridad COMMITTED válida;
histórico proof original válido. Missing/extra/wrong/ciclo/huérfano bloquean, Kahn
O(N+E). B no satisface verified, aunque una declaración del hijo lo sugiera.

## 15. Existing coverage

Nuevo batch mismo manifest: existing. Nuevo inventario: covered_existing, preserva
batch/hash/observación/operation/auth originales. Covered live exige source,
revisión/origin/hash/links y cobertura exactos; no operación histórica ficticia.

## 16. Fiscal verification

Solo referencias congeladas y fuente actual; flag de validación C conservado.
Mocks que fallan si se llama a hashes fiscales durante E. Alterar referencia
produce FISCAL_REFERENCE_CONFLICT. Ningún XML/QR/outbox/provider/AEAT ni verdad fiscal nueva.

## 17. Money

Decimal/NUMERIC/string decimal. Raw monetario→evidencia congelada→payload→EE exactos,
sin redondear a céntimos para ocultar discrepancias. Binary legacy diagnosticado,
no convertido a Money autorizado. B observed_state conservado, unknown/NULL≠zero;
fechas desconocidas conservadas. El importe del match es evidencia y no segunda caja.

## 18. Sequence

Business sequence positiva/consecutiva/única y contador last coherente. Paginación
compuesta (sequence,id) evita saltar duplicados dañados. PK físico con huecos
permitido. No renumera ni actualiza contador.

## 19. Hashes

Seis hashes y result_hash: contexto/version/PASS/BLOCKED. Import por item UUID;
events por secuencia con registro/op/auth/proof/links y huérfanos globales. Findings
ordenados por hash semántico, sin UUID/reloj E. Mismo estado/new UUID E mismo hash;
cambio relevante conflicto/BLOCKED. No duplica payloads raw en tablas E.

## 20. Concurrency

PG procesos independientes: same UUID, two UUID same batch, release, invalidate,
live writer y retry D serializados, prepared batch rechazado, negocio distinto
progresa, crash real. Locks comunes, sin deadlock. Fixtures preparados antes de
retener gate: ALTER TABLE de QA es global y no prueba independencia de negocio.
SQLite conserva writer global de su motor.

## 21. Crash/retry

Ocho checkpoints antes/durante/freeze con rollback, postcommit respuesta perdida
recupera resultado exacto. Crash de proceso PG sin evidencia E parcial. Fence sigue.
Retry verifica contexto y estado actual; drift exige nuevo run y conserva antiguo
read. No modificar import/sources para recuperar.

## 22. Multiempresa

Todas las consultas/joins/FK tenant-scoped. Sesión ajena/caducada y batch/UUID ajenos
rechazados. Gate separado por negocio en PG. No lector global accesible a IA.

## 23. Side-effect proof

Snapshot de TODAS las tablas antes/después, además de flags. Solo se excluyen las
dos tablas E; ningún legacy/fiscal/doc/recurrente/operation/auth/EE/link/sequence/
coverage/B/C/D/control cambia en PASS, BLOCKED, crash o retry. En ciclo de migration
se excluye únicamente applied_at del registro73, conservando toda evidencia financiera.

## 24. SQLite

Matriz E final registrada en QA; incluye corrupción SQL controlada con guards
suspendidos/restaurados SOLO en fixture, no cambios productivos. Snapshot antes/
después y pruebas financieras A–D pasan. Ver evidencia final añadida al cerrar.

## 25. PostgreSQL

PG16 local /noesis_ci con schemas descartables. Matriz E final y procesos pasan;
sin producción. CHECK temporalmente retirado/restaurado NOT VALID en corrupción
QA para retener filas dañadas y probar diagnóstico. Producto conserva guards.

## 26. Migration cycles

Clean→73 y72→73; fixtures con evidencia D/live mantienen bytes/hashes/proofs en
vacío E73→72→73. E durable bloquea downgrade; matrices en ambos motores. CI también
comprueba ciclo completo y código base de schema53 contra actual.

## 27. Performance

131 fuentes monetarias, page8, 267 consultas de verificador y394 consultas totales
incluyendo precondiciones/repositorios/readers/freeze. Aproximadamente1MiB de pico
tracemalloc y menos10s local en ejecuciones medidas. Payload por página, lookups
agrupados y metadatos/edges O(N+E). No SLO de producción ni prueba de volumen real.

## 28. Suite/gates

Ruff, Bandit high, secretos, verdad del proyecto, Node9 y auditoría de dependencias.
Regresiones A–D142 (dos skips existentes). Matrices E SQLite/PG, ciclos, HTTP/servidor
sintético y suite completa/CI final PASS; evidencia verificable en la adenda siguiente.
El timeout general se amplía a35min para permitir suite completa más pruebas E y
ciclos; no se filtra ni reduce QA. Primeros fallos y correcciones se conservan en QA.

### Evidencia final verificable

[CI final: SUCCESS](https://github.com/noesisstudio/noesis/actions/runs/37315021181), código `c6594fc` después del último cambio funcional.
Suite general: **1800 tests**, 1413.197s, `OK (skipped=2)`; cero fallos y errores.
Los dos skips son existentes. Ciclo SQLite completo **73→0→73 PASS**.
Job PostgreSQL: **394 tests PASS** (185.759s sumados entre matrices), incluidos
31 de E (69.677s), procesos reales, migración histórica, 36 rutas de humo,
código anterior schema53 sobre73 y privacidad/rollback/backups sintéticos.
Ruff, Bandit high, secretos, verdad documental, Node9 y auditoría de dependencias PASS.
Matrices E locales en código final: SQLite26 (160.369s), PG31 (105.650s).
Regresiones A–D142 (271.077s, dos skips), autoridad/persistencia SQLite61
(57.267s) y persistencia PG28 (18.770s) PASS. HTTP local /health,/ready,/,/login200.

Performance local final: 131 fuentes, page8, 267 consultas del verificador;
393 consultas totales SQLite, 394 PostgreSQL. SQLite9.578s/909457 bytes de pico;
PG8.093s/967265 bytes. EXPLAIN usa índices de sequence, import items y findings.
Medición sintética, sin SLO ni volumen productivo. Servidor y cluster PG propios
apagados; backups sintéticos retirados del checkout. Ninguna producción consultada.

El primer job PostgreSQL falló por el helper QA legacy_history71 que restauraba72
fijo en un schema73. Corregido conservando su versión original; no se debilitó
ningún guard ni cambió runtime en esa corrección. Los runs anteriores no acreditan
el código final. La adenda de cierre posterior solo modifica documentación:
código, tests, workflow y dependencias siguen idénticos a `c6594fc`.
Cinco flags OFF, fence intacto, cero writes de E fuera de sus dos tablas.
PASS de reconciliación no equivale a rehearsal real, readiness ni activación.

## 29. Riesgos y diferencias

TX larga retiene gate; SQLite writer global. Solo fixtures sintéticos; volumen,
copy real, producción y readiness de activación NO acreditados. Hashes no son firma
ni protección contra falsificación coordinada por administrador de BD. Dos decisiones
explícitas respecto a lectura literal: proyección de delta EE/link D y partial por
v2 antiguo plenamente explicado. Necesarias por los contratos aceptados B/C/D,
documentadas antes de implementar en ADR018. Ningún alcance adicional.

## 30. PASS/FAIL individual

| Nº | Criterio de la orden | Resultado | Evidencia |
|---|---|---|---|
|1|PRINCIPIO CENTRAL|PASS|Servicio solo audita, writes propios|
|2|QUÉ DEBE DEMOSTRAR|PASS|Identidades/proofs/source set, no counts|
|3|PRECONDICIONES|PASS|Preflight sesión/flags/epoch/C/batch|
|4|MIGRACIÓN 73|PASS|Schema73 dos tablas y FK|
|5|INMUTABILIDAD|PASS|Guards run/findings y retry|
|6|CATÁLOGO CERRADO DE FINDINGS|PASS|17 códigos cerrados|
|7|RESULTADO PASS|PASS|PASS estricto sin discrepancias|
|8|RESULTADO BLOCKED|PASS|BLOCKED por evidencia inválida|
|9|OUT_OF_SCOPE Y EXCLUDED|PASS|Fuera de ámbito/excluido sin EE|
|10|COVERED_EXISTING|PASS|Coverage exacta live/historical|
|11|IMPORT ITEMS|PASS|Resultados terminales/canonical|
|12|HISTORICAL OPERATIONS|PASS|PREPARED y unknown exactos|
|13|ECONOMIC EVENT|PASS|StoredEvent decode completo|
|14|HISTORICAL BATCH NO SE REESCRIBE|PASS|Batch original preservado|
|15|IDENTIDAD|PASS|Índice lógico y duplicados SQL QA|
|16|DEPENDENCIAS|PASS|Grafo/links exactos y ciclos|
|17|PADRES LIVE|PASS|Padre live con cobertura real|
|18|SOURCES BAJO FENCE|PASS|Relectura bajo mismo gate/fence|
|19|SOURCE SET COMPLETO|PASS|Scope C completo sin exclusiones nuevas|
|20|DINERO|PASS|Raw/evidencia/Decimal/NULL/unknown|
|21|FACTURAS HISTÓRICAS V2|PASS|Matriz durable no invoice histórico v2|
|22|FISCAL|PASS|Referencias fiscales sin recalcular|
|23|BANK MATCH NO DUPLICA CAJA|PASS|Match Evidence-only, un payment|
|24|COVERAGES LIVE 65–67|PASS|Live coverages exactas e intactas|
|25|EVENT SEQUENCE|PASS|Sequence distinta de PK físico|
|26|ORPHANS|PASS|Huérfanos y alias de batches anteriores|
|27|EVENTOS INESPERADOS|PASS|Histórico sin proof bloquea|
|28|VARIOS BATCHES|PASS|Runs múltiples/batch original|
|29|HASH DE IMPORT|PASS|Hash import ordenado por item|
|30|HASH DE EVENTS|PASS|Hash evento/links/op/auth/proofs|
|31|FINDINGS HASH|PASS|Findings semánticos ordenados|
|32|RESULT HASH|PASS|Contexto y seis hashes/result|
|33|NO RECONCILIAR DURANTE IMPORT|PASS|Prepared/running rechaza sin run|
|34|PAGINACIÓN|PASS|Payloads paginados y metadatos O(N+E)|
|35|CONCURRENCIA|PASS|Procesos PG/gate por negocio|
|36|RELEASE/INVALIDATE|PASS|Release/invalidate serializados|
|37|CRASH|PASS|Ocho checkpoints y crash PG|
|38|SIDE EFFECT PROOF|PASS|Snapshot todas las tablas salvo E|
|39|PERMISOS|PASS|Historical.record/session actuales|
|40|MULTIEMPRESA|PASS|Tenant en consultas/FK/gate|
|41|RESULTADO NO ES ACTIVACIÓN|PASS|PASS no acredita activación|
|42|NO RELEASE FENCE|PASS|Fence permanece sin escrituras E|
|43|NO 1.9F|PASS|Solo fixtures; nunca producción/restore|
|44|MIGRACIONES|PASS|Clean/72/73 ciclos/retención|
|45|TESTS HAPPY PATH|PASS|Happy path completo y hash reproducible|
|46|TESTS BLOCKED|PASS|Matriz corrupción BLOCKED sin repair|
|47|TESTS SEMÁNTICOS|PASS|B/unknown/caja/fecha preservados|
|48|TESTS EXISTING|PASS|Existing y covered live/historical|
|49|SQL CORRUPTION TESTS|PASS|SQL corrupción QA sin debilitar producto|
|50|PERFORMANCE|PASS|131 fuentes, page8, agrupación, pico/queries|
|51|DOCUMENTACIÓN|PASS|Contrato/ADR/informe/gobernanza|
|52|AUTOAUDITORÍA|PASS|20 respuestas explícitas y CI final PASS|

## 31. Autoauditoría

| Nº | Pregunta | Respuesta explícita |
|---|---|---|
|1|¿Puede crear EE?|NO, solo SELECT y persistencia E propia.|
|2|¿Puede modificar import results?|NO; snapshots D idénticos.|
|3|¿Puede reclasificar A/B/C/D?|NO; solo contrasta plan congelado.|
|4|¿Puede modificar fuentes?|NO; lecturas RawReader.|
|5|¿Puede recalcular fiscal como nueva verdad?|NO; mocks prohíben hashes fiscales en E.|
|6|¿Counts sustituyen identidad?|NO; índice source/type/revision/fact y proofs.|
|7|¿Candidate sin explicación terminal PASS?|NO; IMPORT_ITEM_MISSING/BLOCKED.|
|8|¿Histórico huérfano PASS?|NO; UNEXPECTED_HISTORICAL_EVENT.|
|9|¿Historical COMMITTED PASS?|NO; OPERATION_CONFLICT.|
|10|¿Unknown con actor/session?|NO; AUTHORIZATION_CONFLICT.|
|11|¿Identidad duplicada PASS?|NO; EVENT_CONTENT_CONFLICT, SQL QA.|
|12|¿Padre B satisface verified?|NO; DEPENDENCY_CONFLICT, prueba real.|
|13|¿Bank match segunda caja?|NO; impacto exclusivo Evidence y un payment en fixture.|
|14|¿Coverage live contaminada pasa?|NO; LIVE_COVERAGE_CONTAMINATION.|
|15|¿Source drift pasa?|NO; SOURCE_DRIFT para cambios/altas/bajas.|
|16|¿PASS libera fence?|NO; E no escribe epoch/control.|
|17|¿PASS activa flags?|NO; cinco OFF y snapshot idéntico.|
|18|¿Se consultó producción?|NO; solo SQLite/PG locales sintéticos y CI.|
|19|¿Se inició1.9F?|NO; no restore real/Railway/backup real/clientes.|
|20|¿Cambios fuera de tablas E cero?|SÍ durante E, demostrado en PASS/BLOCKED/crash/retry.|

## Lista exacta de archivos de esta entrega

- [.github/workflows/ci.yml](../../.github/workflows/ci.yml)
- [AGENTS.md](../../AGENTS.md)
- [docs/02-tecnico/Guia-tecnica-ingeniero.md](../../docs/02-tecnico/Guia-tecnica-ingeniero.md)
- [docs/Arquitectura.md](../../docs/Arquitectura.md)
- [docs/Decisiones.md](../../docs/Decisiones.md)
- [docs/Estado-actual-main.md](../../docs/Estado-actual-main.md)
- [docs/Inicio.md](../../docs/Inicio.md)
- [docs/Mapa-codigo.md](../../docs/Mapa-codigo.md)
- [docs/Registro-QA.md](../../docs/Registro-QA.md)
- [docs/Registro-cambios.md](../../docs/Registro-cambios.md)
- [docs/Tareas-vivas.md](../../docs/Tareas-vivas.md)
- [docs/architecture/ADR-018-financial-history-reconciliation.md](../../docs/architecture/ADR-018-financial-history-reconciliation.md)
- [docs/architecture/FASE-1.9-plan.md](../../docs/architecture/FASE-1.9-plan.md)
- [docs/architecture/FASE-1.9E-cierre.md](../../docs/architecture/FASE-1.9E-cierre.md)
- [docs/architecture/FASE-1.9E-orden.md](../../docs/architecture/FASE-1.9E-orden.md)
- [docs/architecture/FINANCIAL-HISTORY-RECONCILIATION-v1.md](../../docs/architecture/FINANCIAL-HISTORY-RECONCILIATION-v1.md)
- [docs/architecture/README.md](../../docs/architecture/README.md)
- [docs/areas/01-vision-general.md](../../docs/areas/01-vision-general.md)
- [docs/areas/04-facturas.md](../../docs/areas/04-facturas.md)
- [docs/areas/06-rgpd-y-seguridad.md](../../docs/areas/06-rgpd-y-seguridad.md)
- [docs/areas/07-lo-automatico.md](../../docs/areas/07-lo-automatico.md)
- [docs/areas/08-financial-core.md](../../docs/areas/08-financial-core.md)
- [docs/project-state.json](../../docs/project-state.json)
- [src/noesis/db.py](../../src/noesis/db.py)
- [src/noesis/financial_history/cutoff.py](../../src/noesis/financial_history/cutoff.py)
- [src/noesis/financial_history/importer.py](../../src/noesis/financial_history/importer.py)
- [src/noesis/financial_history/reconciliation.py](../../src/noesis/financial_history/reconciliation.py)
- [src/noesis/financial_history/reconciliation_contracts.py](../../src/noesis/financial_history/reconciliation_contracts.py)
- [src/noesis/financial_history/reconciliation_repository.py](../../src/noesis/financial_history/reconciliation_repository.py)
- [src/noesis/financial_history/reconciliation_schema.py](../../src/noesis/financial_history/reconciliation_schema.py)
- [src/noesis/financial_history/reconciliation_verifier.py](../../src/noesis/financial_history/reconciliation_verifier.py)
- [src/noesis/financial_history/service.py](../../src/noesis/financial_history/service.py)
- [src/noesis/migrations.py](../../src/noesis/migrations.py)
- [tests/financial_history_reconciliation_contract.py](../../tests/financial_history_reconciliation_contract.py)
- [tests/financial_history_reconciliation_worker.py](../../tests/financial_history_reconciliation_worker.py)
- [tests/history_legacy_schema.py](../../tests/history_legacy_schema.py)
- [tests/postgres_financial_history_reconciliation.py](../../tests/postgres_financial_history_reconciliation.py)
- [tests/test_financial_history.py](../../tests/test_financial_history.py)
- [tests/test_financial_history_reconciliation.py](../../tests/test_financial_history_reconciliation.py)
