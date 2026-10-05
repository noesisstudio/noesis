# Cierre de Fase 1.9D — importer histórico durable

2026-10-05. **Implementación validada y cerrada: 57 PASS, 0 FAIL.** Solo 1.9D;
cinco flags OFF. Sin producción, copia/backfill real, reconciliación o activación.
**1.9E no autorizada ni iniciada.** [Orden íntegra](FASE-1.9D-orden.md),
[ADR-017 y auditoría previa](ADR-017-financial-history-import.md),
[contrato heredable](FINANCIAL-HISTORY-IMPORT-v1.md).

## 1. Arquitectura

HistoryImporter es una frontera interna del monolito modular sobre get_conn,
FinancialSession y business gate compartidos con HistoryCutoff. Registra evidencia
congelada, sin ejecutar el hecho original. No endpoint/tool/CLI/scheduler/productor.
Una TX por candidato: gate → revalidación → intent → operación/autorización →
links/evento → resultado → commit. Solo repositorios prestados, sin conexión/commit propios.

## 2. Archivos

Cinco módulos nuevos: durable, import_contracts, import_repository, import_schema e
importer. Decoder/repository de EE seleccionan el contrato histórico separado;
readers añade lookup tenant+PK real; classifier reconoce evidencia D en nuevos
inventarios; cutoff/service admiten esquema compatible posterior; migrations registra 72.
Pruebas comunes/SQLite/PostgreSQL y workers de procesos; CI añade la batería D.
Documentación obligatoria actualizada; listado completo al final.
db.py añade solo los dos nombres D a la guardia de retención de bajas; no nueva
lógica financiera grande. Sin cambios a config, canales, Capture, productores
o fiscalidad funcional.

## 3. Migración

72 añade dos tablas, índices y guards; 63–71 no se modifican retroactivamente.
PostgreSQL ALTER CHECK; SQLite cambia solo definición de CHECK/trigger dentro de
la TX, recarga schema_version y ejecuta integrity_check/foreign_key_check.
No reconstruye tablas referenciadas ni desactiva FKs. Procedimiento de metadatos
según [SQLite ALTER TABLE §8](https://www.sqlite.org/lang_altertable.html).
La prueba con datos live detectó y permitió corregir el problema de la reconstrucción.

## 4. Schema batches/items

| Tabla | Datos y restricciones |
|---|---|
| financial_history_import_batches | PK business/batch; manifest, epoch/generation, importer_version=1, source_set_hash/plan_hash, created_by/at, updated_at, state, blocking_code/item |
| financial_history_import_items | PK business/batch/item; manifest, raw/candidate/identity hashes, identidad canónica, event/op/auth UUID esperados, event/request canónicos, secuencia esperada, recorder/session, state/completion_key, UUID/hashes resultantes, resultado/motivo y fechas |

FKs tenant a C, epoch, item, operador y event/op/auth. Un recording por negocio
mediante índice parcial. FK propia diferida al mismo PK+completion_key obliga a
concluir recording→recorded antes del commit. No intent confirmado inconcluso ni
resultado recorded sin evento. Identidad y resultados terminales inmutables;
DELETE bloqueado. Índices identity/event/operation y fuentes congeladas.

## 5. Contexto

HistoricalImportContext frozen contiene business, epoch/generation, manifest/batch/item,
candidate/identity hashes, registrador/sesión actuales, UUIDs event/op esperados y
versión. Identidad completa en intent; recorder compara objeto/filas en la misma TX.
No input de canal/LLM ni autoridad del actor original.

## 6. Excepción exacta del fence

Intent recording para un único candidato de un batch running. SQL comprueba C
frozen/certifiable/current, epoch/control/generation/scope/hashes/versiones, sesión,
identidad/payload/request y dependencias. Solo UUIDs exactos, relaciones declaradas
y siguiente secuencia. No bypass genérico, bandera de conexión o excepción global.

## 7. SQL guards

Se adaptan únicamente INSERT EE/link/sequence y UPDATE sequence de 71. El resto
continúa. PG mantiene try-gate común READ COMMITTED; user/business FOR SHARE después
del gate. UPDATE comprueba tenants OLD/NEW. Links preinsertados se validan contra
intent; guards63 conservan tipo/target/conjunto sellado y FKs. Dependencias SQL
exigen padre congelado A y su evento/proof/coverage exactos. EE historical nuevo
sin intent se rechaza aun sin fence; puerta live assert_writable permanece.

## 8. Operaciones históricas

Cada nuevo EE tiene op historical, request exacto y creator registrador actual.
Una historical_unknown: actor/session NULL, recorded_by actual, historical.record,
channel historical. Op D PREPARED permanente, result/committed_at NULL. SQL bloquea
HUMAN/MANDATE, ordinary, APPROVED/COMMITTED y cancelación de registros D.
FinancialOperations.execute no se utiliza y rechaza historia. Registros contractuales
previos sin intent conservan cancel/reject no ejecutables.

## 9. Matriz durable

| Origin | Versiones |
|---|---|
| live | v1 de once tipos; v2 invoice.issued/invoice.rectified existentes |
| historical | v1 válido; v2 solo supplier_invoice.confirmed, expense.confirmed, bank_transaction.imported |

HistoricalEconomicEvent separado valida wrapper A. EconomicEvent live conserva
contrato y canonical_version=1; StoredEvent selecciona por origin durable.
Factura historical v2 sigue bloqueada. Bytes/hashes anteriores intactos.

Autoauditoría final cerró también el objeto durable: el wrapper de A permitía
validar una factura v2 en memoria, aunque SQL e importer ya la bloqueaban.
HistoricalEconomicEvent ahora exige la misma whitelist. Golden con factura live
v2 real verifica rechazo histórico y bytes/hashes live intactos. Revalidación:
PostgreSQL80 PASS (83.365 s), SQLite86 PASS (84.708 s).

## 10. Payloads v2

Conservan schema cerrado A; evidence_basis y evidence_hash obligatorios.
Supplier total y componentes/issued_on/invoice_number/due_on según catálogo; expense total,
description/spent_on/vat_amount; bank amount con signo no cero, booked_on/reference.
confirmed_on/imported_on obligatorios pero anulables. amount=total positivo en
supplier/expense. EUR/Decimal, JSON string decimal; float/subcéntimos/invalid rechazados.
NULL distinto de cero; fecha económica conocida no inventa fecha de confirmación.
Sin raw dump/PDF/XML/OCR/conversaciones/notas libres en EE.

## 11. Identidad operation/event

HistoricalIdentity v1 y EntryIdentity intactas. Event UUIDv5 deriva de identidad;
operation UUIDv5 usa namespace da4dd08e-997b-59d3-a9bc-848f9360d0a7 + identity hash;
authorization UUIDv5 de operación. Ni operador/manifest/batch/retry/reloj altera hecho.
Request v1 guarda recording version, identity/candidate hashes, tipo/versión,
amount/EUR/date/revisión. Conflicto no recibe otra UUID.

## 12. Idempotencia

Mismo batch/item verifica source/event y devuelve resultado original. Otro batch
referencia existing sin append/secuencia. Postcommit timeout y proceso competidor
recuperan op/auth/EE/result originales. Conflicto bloquea explícitamente; si hay
resultado sellado se conserva y batch expone blocking_code/item.

## 13. Historical batch

EE→resultado/batch real→C→epoch/generation→T0. Otro manifest conserva batch,
observed_at/recorded_at/hash originales. No batch retroactivo inventado para datos pre72.

## 14. Source verification

RawReader.read_key usa business+PK y execute_exact. Compara raw canonical/hash/revisión,
importes y campos necesarios contra congelado. No revision_reader constante ni
clasificación al importar. Referencias fiscales leídas contra raw existente sin
recalcular hash/QR/XML. SOURCE_DRIFT revierte y registra bloqueo; invalidación
explícita del dueño después del rollback conserva fence. Nunca corrige fuente.

## 15. Dependencias

Identidad exacta, padre A no bloqueante, fuente/revisión/tipo y EE durable/links/proof
verificados. Live covered_existing o historical previo pueden satisfacer contrato.
B/C/D/missing/cruzado/relación incorrecta/contenido conflictivo bloquean.
Sin heurística amount/date/client. Grafo Kahn O(N+E), índices y lectura paginada;
una TX por item; no carga raw/payloads de todo el manifest en memoria.

## 16. Coverage existente

Import result→EE es cobertura histórica indexada y tenant-safe. No inserta/debilita
coverage live65–67. Nuevos inventarios reconocen tres v2 coherentes conservando B
como B; también v1 D determinista con contraste source/payload/links/targets.
D valida op/auth/proof; no basta UUID/coverage. No continuidad automática live.

## 17. Import results

recording exclusivamente transaccional; recorded/existing/covered_existing/blocked/skipped
terminales. result_version=1: item/state/reason y UUIDs/hashes event/op/auth cuando procede.
read_batch pagina64 bajo permisos actuales, incluso tras revocación, sin nuevo registro.

## 18. Partial/block

Batch prepared/running/completed/blocked/partial. C certifiable con result BLOCKED
admite candidatos seguros independientes: partial si hubo evidencia, blocked si no.
completed termina plan sin bloqueos, sin afirmar cobertura total/reconciliation/activation.
C/D/OUT_OF_SCOPE/EXCLUDED/incidencia blocking no producen EE; eligible_for_import=false intacto.

## 19. Crash/retry

Siete checkpoints precommit: before_intent, intent, operation, authorization, links,
event, result; rollback completo incluida secuencia. os._exit PostgreSQL real antes
commit sin huérfanos. Respuesta perdida postcommit recupera resultado. Fence activo.

## 20. Concurrencia

Seis pruebas PG con procesos/barreras y espera pg_locks: mismo item/retry, dos items,
release/invalidate, writer live/SQL directo, muerte real, progreso de otro negocio.
Máximo un evento por identidad y contador común monotónico; cero live y sin inversión
locks. BIGSERIAL físico puede tener huecos; secuencia económica revierte.

## 21. Zero effects

Snapshots invoices/lines/payments/bank/received/expenses/docs/records/outboxes fiscales,
cancellation records/outboxes, coverage live, recurrentes/secuencias documentales/flags
iguales antes/después/retry. Solo nuevos op/auth historical, EE/link/sequence e import.
Sin GL/Open Items/Tax/posting/reporting o cambio funcional VERI*FACTU.

## 22. SQLite

Fixtures descartables; 19 pruebas comunes D. DDL de fixture monetaria TEXT exclusivamente
para evidencia exacta, nunca migración productiva. REAL ambiguo permanece bloqueado.
Guards/crashes/retry/fechas/precisión/deps/conflictos y datos live previos verificados.

## 23. PostgreSQL

PG16 local localhost/noesis_ci, schemas UUID sintéticos, NUMERIC y procesos reales.
Matriz final 363 PASS (239.055 s), D25=19 comunes+6 procesos. La instancia local
interrumpida entre sesiones se reinició; ejecuciones no concluidas no se cuentan PASS.
Sin base remota/copia/clientes/proveedor real.

## 24. Migraciones

Ambos motores: clean/71→72, vacío72→71→72; evidencia impide downgrade destructivo.
Live v1/v2 bytes/hashes/filas/links/secuencia iguales tras 71→72→71→72. Fallo posterior
al CHECK revierte esquema/datos. SQLite 72→0→72 solo sin evidencia; PG fixture32→72.

## 25. Suite/gates

Comandos reproducibles sobre bases temporales sintéticas; PostgreSQL requiere
localhost/noesis_ci y schema aislado, nunca una copia ni una URL productiva:

```text
uv run python -m unittest tests.test_financial_history_import
uv run python -m unittest tests.postgres_financial_history_import.HistoryImportPostgres
uv run python -m unittest discover -s tests -p "test_*.py"
uv run ruff check src tests
uv run bandit -r src/noesis -q -lll -iii
uv run python scripts/check_project_truth.py
uv run python scripts/check_secrets.py
uv run pip-audit
uv lock --check
node --test tests/public_marketing.test.cjs tests/public_calendar.test.cjs tests/admin_economia.test.cjs tests/financial_channels.test.cjs
```

La [CI](../../.github/workflows/ci.yml) conserva los comandos de las once matrices
PostgreSQL y humos. Total de matriz: Core6, Operations37, EE28, Borrowed18,
Invoice27, Payment/Bank41, Purchasing44, Channels50, HistoryB37, HistoryC50,
HistoryD25 = 363. HistoryA puro se ejecuta en la suite general y matriz SQLite.
El número de tests ejecutados incluye los skips cuando se indican; no equivalen
a un PASS individual del escenario omitido.

CI final [37300038706](https://github.com/noesisstudio/noesis/actions/runs/37300038706)
SUCCESS sobre942a113: suite general 1774 tests en1215.844 s, dos skips previstos;
PostgreSQL363 PASS (151.231 s sumados, D25 con seis carreras de procesos). Ambos jobs, gates,
migraciones y humos PASS. **57 criterios PASS, 0 FAIL**. Esta adenda solo modifica
documentación; código, tests, workflow y dependencias coinciden con la CI validada. Sin
producción consultada ni1.9E.

SQLite179 PASS en306.716 s,
dos skips previstos de carreras C; D19. PG363 PASS en239.055 s; D25 con seis procesos.
PG32→72, 36 rutas, código anterior53 sobre72, privacidad/rollback PASS. SQLite72→0→72
y health/ready/home/login HTTP200 local con scheduler mock. Ruff src/tests,
Bandit high/high, secretos staged, project truth, Node9, uv lock, pip-audit y125
links locales nuevos/modificados PASS. No dependencias nuevas; paquete local
noesis no se audita en PyPI. Ruff fuera de targets CI encontró avisos preexistentes
en branding/notebook; no se modifican. Golden tests y datos live forman parte
real de matrices, no una declaración. Ejecuciones interrumpidas no se cuentan PASS.


CI inicial620f5fe detectó fallo exclusivamente en fixture SOURCE_DRIFT: pg_trigger
se buscaba por nombre global y podía restaurar el trigger de otro esquema. Corrección:
tgrelid='expenses'::regclass limita al target actual. No cambio runtime. Revalidación
D25 con esquema señuelo/trigger homónimo PASS; CI final completa PASS.


Suite local1774 (2159.129 s) detectó cuatro incidencias: catálogo de retención no
incluía las dos tablas D; simulador DDL sin pg_get_functiondef y literal SQLSTATE.
Corregidos: dos nombres en la guardia de baja db.py (sin nueva lógica financiera),
simulador con definición real generada por65 y formato SQLSTATE uniforme.
Siete tests platform/baja PASS; D SQLite/PG y CI completa final revalidados PASS.

Última revalidación local tras cerrar el objeto durable: PostgreSQL80 PASS
(83.365 s), SQLite86 PASS (84.708 s). Secrets de todos los archivos versionados
PASS; 680 enlaces locales de documentos modificados comprobados. La instancia
PG QA propia fue apagada; logs/fixtures conservados en TEMP.

## 26. Decisiones, diferencias y riesgos

Dentro del diseño aprobado: intent/result combinado con FK propia diferida, recorder
específico, D permanentemente PREPARED, contrato histórico separado, partial seguro,
reconocimiento de evidencia D en inventarios posteriores. No cambios semánticos B/C.
observed_at rehidratado de started_at congelado, excluido del hash semántico B/C.
EvidenceReference no vacías que el scanner actual no construye se rechazan, sin fingir
verificación. Otros not_durably_supported y factura v2 siguen bloqueados.

SQL complejo exige matriz dual. SQLite writer global; PG writer busy requiere rollback/retry.
Propietario DDL que retire guards queda fuera de APIs autorizadas; corrupción se detecta
como drift/conflicto, sin reparación. Rollback code-first con flags OFF conservando
esquema/evidencia; downgrade destructivo72 con datos bloqueado. Restauración real espera
1.9F; reconciliación necesita autorización separada 1.9E. Sin activación/certificación productiva.

## 27. PASS/FAIL individual

Numeración corresponde a la orden íntegra. 57 PASS, 0 FAIL, con QA final y autoauditoría.

| Nº | Criterio | Estado | Evidencia |
|---:|---|---|---|
| 1 | Registro sin reproducir acciones | PASS | importer/snapshots |
| 2 | Auditoría previa runtime | PASS | ADR-017 |
| 3 | Sin bypass genérico | PASS | contexto/SQL/Capture intacto |
| 4 | Migración mínima72 | PASS | dos tablas/índices/guards |
| 5 | Manifest congelado inmutable | PASS | snapshots/hash |
| 6 | eligible_for_import=false intacto | PASS | boundary SQL/C |
| 7 | Contexto frozen contra DB/TX | PASS | durable/recorder |
| 8 | Revalidación por item | PASS | boundary/source/deps/session |
| 9 | Sin reclasificación al importar | PASS | decoder sin classify |
| 10 | Solo candidatos soportados | PASS | whitelist/disposition |
| 11 | not_durably_supported cerrado | PASS | tres v2 autorizados |
| 12 | Factura histórica v2 bloqueada | PASS | SQL/app/A |
| 13 | Matriz exacta y golden | PASS | CHECK/decoder/migration golden |
| 14 | Origin/fechas/provenance honestos | PASS | known/unknown/NULL |
| 15 | Batch real demostrable | PASS | FK C/epoch/T0 |
| 16 | Operación histórica obligatoria | PASS | recorder/result guard |
| 17 | Unknown única y PREPARED | PASS | SQL ambos motores |
| 18 | SQL impide promoción/actors | PASS | operation/auth guards |
| 19 | Recorder prestado sin execute | PASS | ImportRepository |
| 20 | Excepción por item exacto | PASS | valid_intent/FK |
| 21 | Fence SQL conservado | PASS | live/no intent/mismatch reject |
| 22 | Links preinsertados sellados | PASS | intent/guards63 |
| 23 | Secuencia común/retry/rollback | PASS | procesos/contador |
| 24 | Event UUID determinista | PASS | HistoricalIdentity v1 |
| 25 | Operation UUID estable | PASS | uuid5(identity hash) |
| 26 | Retry op/auth/EE/result original | PASS | checkpoints/procesos |
| 27 | Otro manifest conserva evento/batch | PASS | v1/v2 existing |
| 28 | Dependencias identidad exacta | PASS | SQL/app/catálogo |
| 29 | Parent covered_existing verificado | PASS | source/EE/proof/links |
| 30 | Padre B no satisface verified | PASS | A/B/C/D/missing |
| 31 | Reader real/SOURCE_DRIFT | PASS | PK/raw/hash/invalidate |
| 32 | Sin regeneración fiscal | PASS | referencias/snapshot |
| 33 | Atomicidad intent/op/auth/EE/result | PASS | FK/crash |
| 34 | TX por candidato | PASS | record_item/run |
| 35 | Topología O(N+E) | PASS | Kahn/páginas/índices |
| 36 | Batch sin reconciliación/activación | PASS | estados/version |
| 37 | Partial seguro de C BLOCKED | PASS | partial test |
| 38 | Coverage live65–67 intacta | PASS | snapshots/regresiones |
| 39 | Coverage histórica indexada | PASS | identity/event indexes |
| 40 | Sin continuidad live | PASS | Capture intacto |
| 41 | Fence sigue tras import | PASS | éxito/crash/retry |
| 42 | Release/invalidate serializados | PASS | PG procesos/gate |
| 43 | Crash pre/postcommit | PASS | siete checkpoints/os._exit |
| 44 | Concurrencia PG real | PASS | seis procesos/matriz |
| 45 | Multiempresa | PASS | PK/FK/lookup/tests |
| 46 | Privacidad payload cerrado | PASS | A/EE/no raw copy |
| 47 | Sin producción/copia real | PASS | local/noesis_ci/fixtures |
| 48 | Tests historical operations | PASS | SQL/operations matrix |
| 49 | Tests v2/matriz/golden | PASS | common/live golden |
| 50 | Tests SQL exception | PASS | mismatch/UUID/no intent |
| 51 | Tests deps/conflictos | PASS | A-B-C-D/relation/corruption |
| 52 | Tests idempotencia | PASS | operador/batch/cut/retry |
| 53 | Tests zero effects | PASS | snapshots sources/flags |
| 54 | Hash/fechas originales en retry | PASS | same/new operator/manifest |
| 55 | Migraciones duales/datos previos | PASS | common/golden |
| 56 | Todas regresiones y gates | PASS | CI completa942a113; general1774/PG363/gates/migraciones |
| 57 | Autoauditoría | PASS | 20 respuestas abajo |

## 28. Autoauditoría

| Nº | Pregunta de la orden | Respuesta y fundamento |
|---:|---|---|
| 1 | ¿Bypass genérico? | No. Intent exacto, no flag global. |
| 2 | ¿Capture usa excepción? | No. assert_writable permanece. |
| 3 | ¿EE live usa excepción? | No. SQL exige origin historical exacto. |
| 4 | ¿SQL historical sin item válido? | No. Intent/manifest/item vigente obligatorio. |
| 5 | ¿Importa diagnóstico B? | No. Sobre C certificable requerido. |
| 6 | ¿Importa released/invalidated? | No. Boundary/gate revalidado cada TX. |
| 7 | ¿Importa C/D? | No. Solo A/B explícito soportado. |
| 8 | ¿Reclasifica durante import? | No. Rehidrata/verifica congelado. |
| 9 | ¿Modifica raw? | No. Hash/snapshot original conservado. |
| 10 | ¿Operación histórica ejecutable? | No. PREPARED; SQL/servicio impiden promoción. |
| 11 | ¿HUMAN/MANDATE? | No. Guards y unknown única. |
| 12 | ¿Inserta coverage live65–67? | No. Resultado histórico separado. |
| 13 | ¿Reenvía/recalcula fiscal? | No. Verifica solo referencias congeladas. |
| 14 | ¿Retry duplica sequence/event? | No. Recupera original validado. |
| 15 | ¿Nuevo manifest reescribe batch? | No. Existing conserva metadata/hash. |
| 16 | ¿Padre B satisface dependencia? | No. Assessment A verificado obligatorio. |
| 17 | ¿Toca source legacy? | No. Sources solo SELECT; DDL monetaria solo fixture. |
| 18 | ¿Fence liberado por éxito/crash? | No. Release explícito separado. |
| 19 | ¿Producción consultada? | No. Solo fixtures y PG localhost/noesis_ci. |
| 20 | ¿Inició1.9E? | No. Sin reconciliación/activación/backfill real. |

## Listado completo de archivos

- Modificado: [.github/workflows/ci.yml](../../.github/workflows/ci.yml)
- Modificado: [AGENTS.md](../../AGENTS.md)
- Modificado: [docs/02-tecnico/Guia-tecnica-ingeniero.md](../../docs/02-tecnico/Guia-tecnica-ingeniero.md)
- Modificado: [docs/Arquitectura.md](../../docs/Arquitectura.md)
- Modificado: [docs/Decisiones.md](../../docs/Decisiones.md)
- Modificado: [docs/Estado-actual-main.md](../../docs/Estado-actual-main.md)
- Modificado: [docs/Inicio.md](../../docs/Inicio.md)
- Modificado: [docs/Mapa-codigo.md](../../docs/Mapa-codigo.md)
- Modificado: [docs/Registro-QA.md](../../docs/Registro-QA.md)
- Modificado: [docs/Registro-cambios.md](../../docs/Registro-cambios.md)
- Modificado: [docs/Tareas-vivas.md](../../docs/Tareas-vivas.md)
- Modificado: [docs/architecture/FASE-1.9-plan.md](../../docs/architecture/FASE-1.9-plan.md)
- Modificado: [docs/architecture/README.md](../../docs/architecture/README.md)
- Modificado: [docs/areas/01-vision-general.md](../../docs/areas/01-vision-general.md)
- Modificado: [docs/areas/03-cerebro.md](../../docs/areas/03-cerebro.md)
- Modificado: [docs/areas/04-facturas.md](../../docs/areas/04-facturas.md)
- Modificado: [docs/areas/06-rgpd-y-seguridad.md](../../docs/areas/06-rgpd-y-seguridad.md)
- Modificado: [docs/areas/07-lo-automatico.md](../../docs/areas/07-lo-automatico.md)
- Modificado: [docs/areas/08-financial-core.md](../../docs/areas/08-financial-core.md)
- Modificado: [docs/project-state.json](../../docs/project-state.json)
- Modificado: [src/noesis/economic_events/contracts.py](../../src/noesis/economic_events/contracts.py)
- Modificado: [src/noesis/economic_events/persistence.py](../../src/noesis/economic_events/persistence.py)
- Modificado: [src/noesis/economic_events/repository.py](../../src/noesis/economic_events/repository.py)
- Modificado: [src/noesis/financial_history/classifier.py](../../src/noesis/financial_history/classifier.py)
- Modificado: [src/noesis/financial_history/cutoff.py](../../src/noesis/financial_history/cutoff.py)
- Modificado: [src/noesis/financial_history/readers.py](../../src/noesis/financial_history/readers.py)
- Modificado: [src/noesis/financial_history/service.py](../../src/noesis/financial_history/service.py)
- Modificado: [src/noesis/migrations.py](../../src/noesis/migrations.py)
- Modificado: [tests/economic_persistence_contract.py](../../tests/economic_persistence_contract.py)
- Modificado: [tests/financial_history_cutoff_contract.py](../../tests/financial_history_cutoff_contract.py)
- Modificado: [tests/financial_operations_contract.py](../../tests/financial_operations_contract.py)
- Modificado: [tests/test_financial_history.py](../../tests/test_financial_history.py)
- Creado: [docs/architecture/ADR-017-financial-history-import.md](../../docs/architecture/ADR-017-financial-history-import.md)
- Creado: [docs/architecture/FASE-1.9D-cierre.md](../../docs/architecture/FASE-1.9D-cierre.md)
- Creado: [docs/architecture/FASE-1.9D-orden.md](../../docs/architecture/FASE-1.9D-orden.md)
- Creado: [docs/architecture/FINANCIAL-HISTORY-IMPORT-v1.md](../../docs/architecture/FINANCIAL-HISTORY-IMPORT-v1.md)
- Creado: [src/noesis/financial_history/durable.py](../../src/noesis/financial_history/durable.py)
- Creado: [src/noesis/financial_history/import_contracts.py](../../src/noesis/financial_history/import_contracts.py)
- Creado: [src/noesis/financial_history/import_repository.py](../../src/noesis/financial_history/import_repository.py)
- Creado: [src/noesis/financial_history/import_schema.py](../../src/noesis/financial_history/import_schema.py)
- Creado: [src/noesis/financial_history/importer.py](../../src/noesis/financial_history/importer.py)
- Creado: [tests/financial_history_import_contract.py](../../tests/financial_history_import_contract.py)
- Creado: [tests/financial_history_import_worker.py](../../tests/financial_history_import_worker.py)
- Creado: [tests/history_legacy_schema.py](../../tests/history_legacy_schema.py)
- Creado: [tests/postgres_financial_history_import.py](../../tests/postgres_financial_history_import.py)
- Creado: [tests/test_financial_history_import.py](../../tests/test_financial_history_import.py)

- Modificado: [src/noesis/db.py](../../src/noesis/db.py) — catálogo de retención.
- Modificado: [tests/test_platform.py](../../tests/test_platform.py) — introspección DDL simulada.
