Las Fases 0–1.8H y 1.9A–1.9D quedan aceptadas.

Ejecuta exclusivamente:

# FASE 1.9E — RECONCILIACIÓN HISTÓRICA DURABLE

NO avances a 1.9F.

La Fase 1.9D ya puede incorporar Economic Events históricos durables de forma acotada.

La Fase 1.9E debe demostrar que:

**lo inventariado + lo importado + lo ya cubierto + lo excluido/bloqueado explican de forma consistente el estado histórico del business.**

Esta fase NO repara.

Esta fase NO importa nuevos Economic Events.

Esta fase NO reclasifica.

Esta fase NO libera el fence.

Esta fase NO activa ninguna cuenta.

Cinco flags Financial Core siguen OFF.

Producción y copias reales siguen fuera de alcance.

---

# 1. PRINCIPIO CENTRAL

La reconciliación debe ser:

read-only respecto a:

- sources legacy;
- Economic Events;
- Financial Operations;
- Financial Authorizations;
- import batches/items;
- coverages live;
- fiscal;
- documentos;
- recurrentes.

Solo puede persistir:

- reconciliation run;
- findings/resultados propios de reconciliación;
- audit mínimo propio si es necesario.

Nunca corregir automáticamente una discrepancia.

---

# 2. QUÉ DEBE DEMOSTRAR

No quiero una reconciliación basada en:

`COUNT(sources) == COUNT(events)`.

Debe demostrar por identidad:

source congelado
↔ manifest item
↔ assessment/disposition
↔ import result o existing coverage
↔ Financial Operation histórica cuando proceda
↔ historical_unknown
↔ Economic Event
↔ relaciones/dependencias
↔ hashes
↔ source actual bajo fence.

Cada fila/hecho inventariado debe quedar explicado.

---

# 3. PRECONDICIONES

Para iniciar reconciliación:

- schema esperado;
- operador actual autenticado;
- `historical.record`;
- cinco flags OFF;
- epoch sigue `fenced`;
- control apunta a ese epoch/generation;
- `boundary_current=true`;
- manifest C está frozen;
- `certifiable=true`;
- manifest continúa `eligible_for_import=false`;
- source_set_hash y comparison hash iguales;
- plan_hash coherente;
- import batch existe;
- batch está en estado terminal.

Estados terminales admitidos para auditar:

- completed
- partial
- blocked

No reconciliar un batch:

- prepared
- running.

Un batch partial/blocked podrá reconciliarse, pero el resultado global deberá ser BLOCKED cuando corresponda.

---

# 4. MIGRACIÓN 73

Determina la siguiente migration real; previsiblemente 73.

Añade únicamente persistencia necesaria para reconciliación.

Diseño mínimo preferido:

## `financial_history_reconciliations`

Campos conceptuales:

- business_id
- reconciliation_uuid
- epoch_uuid
- generation
- manifest_uuid
- batch_uuid
- reconciliation_version
- created_by
- started_at
- completed_at
- state
- result
- source_set_hash
- plan_hash
- import_set_hash
- event_set_hash
- source_recheck_hash
- findings_hash
- result_hash

Estados pequeños:

- running
- frozen

Resultado:

- PASS
- BLOCKED

No crear:

- activation state;
- validating state;
- enabled;
- accounting close;
- GL/Open Items/Tax.

## `financial_history_reconciliation_findings`

Solo discrepancias.

Como mínimo:

- business
- reconciliation
- item_uuid nullable únicamente para findings globales
- code
- severity
- expected_hash/ref
- actual_hash/ref
- evidence canonical mínima
- created_at

Append-only.

No duplicar una fila de reconciliación por cada item correcto si import_items + manifest ya contienen esa información.

---

# 5. INMUTABILIDAD

Una reconciliation frozen:

NO puede modificarse.

Findings:

NO UPDATE.
NO DELETE.

Retry de la misma reconciliation UUID:

→ devuelve resultado original si contexto/hash coincide.

Misma UUID con:

- otro batch;
- otro manifest;
- otro epoch;
- otra versión

→ conflicto.

---

# 6. CATÁLOGO CERRADO DE FINDINGS

Define catálogo pequeño y tipado.

Debe cubrir como mínimo conceptos equivalentes a:

- SOURCE_DRIFT
- MANIFEST_INCONSISTENT
- BATCH_NOT_TERMINAL
- IMPORT_ITEM_MISSING
- IMPORT_ITEM_UNEXPECTED
- IMPORT_RESULT_CONFLICT
- EVENT_MISSING
- EVENT_CONTENT_CONFLICT
- OPERATION_CONFLICT
- AUTHORIZATION_CONFLICT
- DEPENDENCY_CONFLICT
- EXISTING_COVERAGE_CONFLICT
- UNEXPECTED_HISTORICAL_EVENT
- LIVE_COVERAGE_CONTAMINATION
- SEQUENCE_CONFLICT
- FISCAL_REFERENCE_CONFLICT
- BLOCKING_HISTORY_REMAINS

No crear un sistema genérico de incidencias.

Usar nombres finales coherentes con contratos existentes.

---

# 7. RESULTADO PASS

PASS debe ser estricto.

Como mínimo requiere:

- boundary vigente;
- source set todavía idéntico;
- todos los items del manifest explicados;
- cero import item incoherente;
- cero Economic Event huérfano/incompatible;
- cero Operation/Auth histórica incoherente;
- dependencias válidas;
- cero evento duplicado por HistoricalIdentity;
- secuencia coherente;
- cero conflicto fiscal;
- cero contaminación de coverage live;
- cero finding blocking;
- cero incidencia histórica blocking pendiente;
- batch compatible con cobertura completa exigida.

PASS NO significa:

- activar;
- cumplimiento contable;
- cumplimiento fiscal completo;
- readiness GL;
- readiness Open Items;
- readiness Tax Ledger.

---

# 8. RESULTADO BLOCKED

Debe ser BLOCKED si existe cualquier evidencia no explicada o inconsistente.

Ejemplos:

manifest contiene C/D blocking;
batch partial/blocked por candidato necesario;
source cambió;
evento desapareció;
hash difiere;
operation/auth incorrecta;
dependency no coincide;
evento inesperado;
historical identity duplicada;
fiscal reference incompatible.

No reparar.

---

# 9. OUT_OF_SCOPE Y EXCLUDED

No todo item tiene que producir evento.

Un item:

`out_of_scope`

puede quedar correctamente reconciliado si:

- el manifest lo congeló así;
- no existe import result/event económico inesperado para él.

Un item:

`excluded`

solo puede considerarse explicado si:

- exclusión está congelada/justificada según contrato;
- no existe evento creado pese a estar excluido;
- no tiene una dependencia requerida por otro item importado.

No transformar exclusión en PASS financiero por sí sola.

---

# 10. COVERED_EXISTING

Para todo `covered_existing`:

revalidar:

- Economic Event existe;
- business;
- source;
- revision;
- event type;
- content hash;
- origin;
- relations;
- coverage frozen.

No basta con que la coverage row exista.

Si event contradice manifest:

BLOCKED.

---

# 11. IMPORT ITEMS

Cada item candidato debe tener exactamente una explicación terminal apropiada:

- recorded
- existing
- covered_existing
- blocked
- skipped

según su assessment/disposition.

No puede haber:

- item candidate importable sin import result;
- dos resultados efectivos para misma identidad;
- recording huérfano;
- result que apunte a otro manifest/source.

---

# 12. HISTORICAL OPERATIONS

Por cada evento histórico creado por D:

verificar:

FinancialOperation:

- business correcto;
- namespace historical;
- state PREPARED;
- request exacto;
- created_by registrador;
- result_canonical NULL;
- committed_at NULL.

Authorization:

- exactamente una historical_unknown;
- actor NULL;
- session original NULL;
- recorded_by correcto;
- permission historical.record;
- channel historical;
- request hash/revision coherentes.

Cualquier HUMAN/MANDATE/APPROVED/COMMITTED:

BLOCKED.

---

# 13. ECONOMIC EVENT

Para cada event histórico:

verificar durable decode completo.

Comprobar:

- origin historical;
- batch original;
- event UUID;
- HistoricalIdentity;
- content hash;
- record hash;
- payload version;
- source type/id/revision;
- amount;
- currency;
- dates;
- provenance;
- business sequence;
- operation UUID;
- authorization UUID;
- links.

No reconstruir un evento para “arreglar” diferencias.

---

# 14. HISTORICAL BATCH NO SE REESCRIBE

Un evento puede haber sido incorporado por un batch anterior y posteriormente aparecer como `existing`.

Reconciliation debe aceptar esto únicamente si:

- el evento original tiene import proof durable;
- historical_batch_uuid sigue siendo el original;
- nuevo batch referencia existing correctamente;
- hashes coinciden.

Nunca esperar que historical_batch_uuid sea el batch actualmente reconciliado cuando el item es `existing`.

---

# 15. IDENTIDAD

Construir índice lógico:

HistoricalIdentity
→ máximo un Economic Event válido.

Buscar duplicados aunque:

- tengan distinto batch;
- distinto operador;
- distinto recorded_at.

Un mismo hecho no puede existir dos veces.

No identificar hechos por:

- amount;
- fecha;
- número visual.

---

# 16. DEPENDENCIAS

Reconstruir el grafo desde candidatos congelados y comprobar contra links durables.

Ejemplos:

invoice
→ payment

invoice original
→ rectification

bank import + payment
→ bank match

invoice
→ fiscal cancellation

supplier confirmed
→ correction/void

expense confirmed
→ void.

Cada link durable debe:

- existir cuando se esperaba;
- apuntar al event exacto;
- tener relation type correcto;
- pertenecer al mismo business.

Links adicionales no declarados:

BLOCKED.

---

# 17. PADRES LIVE

Una dependencia puede estar satisfecha por un Economic Event live preexistente.

Debe verificarse:

- event durable;
- source/revision;
- hash;
- coverage;
- semántica.

No exigir historical operation en ese caso.

Pero tampoco aceptar una coverage live corrupta solo porque existe.

---

# 18. SOURCES BAJO FENCE

Releer fuentes con RawReader de scope C.

El fence continúa activo, por tanto deben seguir coincidiendo con el manifest.

Calcular `source_recheck_hash`.

Debe coincidir con el source set certificado.

Cualquier:

- alta;
- baja;
- cambio;
- raw hash diferente;
- revision distinta

→ SOURCE_DRIFT
→ BLOCKED.

No invalidar/corregir automáticamente el source.

---

# 19. SOURCE SET COMPLETO

No comprobar únicamente sources que produjeron evento.

Reconciliar el conjunto completo congelado:

- evidence sources;
- documentos;
- perfiles;
- registros fiscales;
- transports excluidos según scope;
- recurring evidence;
- coverage existente.

La semántica de exclusiones de scope C debe permanecer idéntica.

---

# 20. DINERO

Para cada evento:

comparar:

raw evidence congelada
→ candidate frozen
→ Economic Event durable

sin pasar por float normalizado.

Para v2 histórico:

- Decimal;
- null vs zero;
- evidence basis;
- evidence hash.

No declarar discrepancy basándose únicamente en representación de display si la evidencia binaria congelada es la misma.

---

# 21. FACTURAS HISTÓRICAS V2

Siguen bloqueadas.

Reconciliation NO es el lugar para desbloquearlas.

Si existe inesperadamente una invoice historical v2:

BLOCKED salvo que ya estuviera explícitamente permitida por la matriz durable vigente, que actualmente NO debe ser así.

Golden live invoice v2 sigue intacto.

---

# 22. FISCAL

Para invoices y cancellations:

verificar exclusivamente evidencia ya congelada/durable.

No:

- recalcular hash VERI*FACTU como nueva verdad;
- regenerar QR;
- regenerar XML;
- reenviar AEAT;
- cambiar outbox.

Puede verificar que:

IDs/hashes/referencias congeladas
==
IDs/hashes/referencias actuales.

Diferencia:

FISCAL_REFERENCE_CONFLICT
→ BLOCKED.

---

# 23. BANK MATCH NO DUPLICA CAJA

Auditar semánticamente:

`customer_payment.received`

es hecho de caja.

`bank_transaction.matched`

es Evidence-only.

La reconciliación debe detectar cualquier conjunto histórico donde el match se esté interpretando como segundo cobro.

No crear posting ni sumar cash para reporting.

Comprobar relaciones:

matches
+
evidence_for.

---

# 24. COVERAGES LIVE 65–67

Snapshot antes/después.

1.9E no modifica ninguna.

Además verifica que ningún import histórico haya insertado filas fingiendo:

operation_state committed live
o
human authorization.

Si ocurre:

BLOCKED.

---

# 25. EVENT SEQUENCE

Validar por business:

- business_sequence único;
- positivo;
- monotónico;
- `economic_event_sequences.last_sequence` coherente con último event durable.

No confundir BIGSERIAL físico con business_sequence.

Huecos físicos de PK:

permitidos.

Incoherencia en business sequence:

BLOCKED.

No renumerar.

---

# 26. ORPHANS

Buscar explícitamente:

historical operation sin import proof;
historical_unknown sin operation histórica correcta;
historical event sin import proof;
import recorded sin event;
event con batch inexistente;
link sin event válido;
batch sin manifest/epoch;
result terminal incoherente.

Aunque FKs deberían impedir gran parte:

reconciliation debe verificar invariantes semánticos.

---

# 27. EVENTOS INESPERADOS

Buscar Economic Events históricos del business que:

- no estén explicados por coverage histórica/import proof;
- no sean eventos históricos preexistentes explícitamente reconocidos por contrato.

No ignorarlos.

`UNEXPECTED_HISTORICAL_EVENT`
→ BLOCKED.

No borrar.

---

# 28. VARIOS BATCHES

El business puede acumular varios batches históricos legítimos en distintos cuts.

Reconciliation actual está ligada a:

epoch
+
manifest
+
batch.

Pero debe comprobar que eventos anteriores utilizados como dependencies/existing:

- son válidos;
- no colisionan por identidad;
- conservan su batch original.

No exigir que toda historia del business pertenezca a un solo batch.

---

# 29. HASH DE IMPORT

Construir `import_set_hash` determinista con:

- item UUID;
- identity hash;
- candidate hash;
- terminal state;
- event UUID;
- content hash;
- record hash;
- operation UUID;
- authorization UUID.

Orden estable.

No timestamps no semánticos salvo que formen parte del record durable que se está verificando.

---

# 30. HASH DE EVENTS

Construir `event_set_hash` sobre eventos relevantes reconciliados.

Debe incluir semántica durable suficiente para detectar:

- evento cambiado;
- link cambiado;
- batch cambiado;
- op/auth cambiada.

No duplicar payload raw completo en reconciliation tables.

---

# 31. FINDINGS HASH

Ordenar findings determinísticamente.

Mismo estado:

→ mismo findings_hash.

No usar UUID aleatorio del finding dentro de su hash semántico si impediría reproducibilidad.

---

# 32. RESULT HASH

El `result_hash` debe comprometer como mínimo:

- reconciliation version;
- business;
- epoch/generation;
- manifest;
- batch;
- source_set_hash;
- plan_hash;
- import_set_hash;
- event_set_hash;
- source_recheck_hash;
- findings_hash;
- result PASS/BLOCKED.

Retry exacto:

→ mismo result_hash.

---

# 33. NO RECONCILIAR DURANTE IMPORT

Batch debe ser terminal.

Si aparece `recording`:

→ no empezar / BLOCKED técnico.

No competir con HistoryImporter para “esperar”.

No usar sleeps.

---

# 34. PAGINACIÓN

Datasets potencialmente grandes:

- manifest items paginados;
- import items paginados;
- EE por índices;
- sources por RawReader.

No cargar payload/raw completo de todo el business en memoria.

Grafo puede conservar identidades/edges O(N+E) como D, pero no documentos/blobs.

---

# 35. CONCURRENCIA

Fence sigue activo, pero probar PostgreSQL real:

- dos reconciliations misma UUID;
- dos UUIDs mismo batch;
- reconciliation + release;
- reconciliation + invalidate;
- reconciliation + intento live writer;
- reconciliation + importer sobre batch terminal rechazado/no posible;
- otro business continúa.

Define política para múltiples reconciliations del mismo batch.

Preferencia:

permitir runs históricos inmutables pero solo una ejecución `running` por business/batch.

No introducir deadlocks.

---

# 36. RELEASE/INVALIDATE

Al iniciar y antes de freeze:

epoch debe seguir current/fenced.

Si se libera o invalida durante reconciliation:

→ reconciliation no puede terminar PASS.

Resultado:

BLOCKED/aborted según contrato.

NO reactivar fence.

NO invalidar automáticamente epoch salvo corrupción/drift si el diseño lo justifica expresamente.

---

# 37. CRASH

Probar:

- antes de create run;
- durante source scan;
- durante import verification;
- durante event verification;
- antes de findings freeze;
- después del commit antes de respuesta.

Retry:

→ reanuda o recupera resultado exacto.

No modifica import ni sources.

---

# 38. SIDE EFFECT PROOF

Snapshot antes/después de reconciliation:

- legacy sources;
- fiscal;
- documents;
- recurrentes;
- Financial Operations;
- Authorizations;
- Economic Events;
- links;
- event sequence;
- live coverages;
- history manifests/items/incidences/decisions;
- import batches/items;
- epoch/control;
- flags.

Solo pueden cambiar:

`financial_history_reconciliations`
y
`financial_history_reconciliation_findings`
y audit propio mínimo si se aprueba.

---

# 39. PERMISOS

Crear reconciliation:

- operador autenticado;
- sesión vigente;
- business correcto;
- historical.record;
- opened_by/current policy compatible con Cutoff/Importer.

No usar:

financial.authorize.

No crear authorization.

Lectura posterior puede diseñarse con permiso histórico/audit actual, pero no relajar cross-tenant.

---

# 40. MULTIEMPRESA

Todos los joins tenant-scoped.

Tests con:

- mismos source IDs;
- mismos item UUIDs cuando sea posible;
- mismo batch UUID intentando otra empresa;
- event UUID ajeno.

Todo cross-business rechazado.

---

# 41. RESULTADO NO ES ACTIVACIÓN

No añadir:

- eligible_for_activation;
- account_enabled;
- capture_enabled;
- validating;
- Financial Core flag.

Si necesitas una salida para 1.10, usa únicamente algo descriptivo como:

`reconciliation_result = PASS`

sin efecto operativo.

1.10 decidirá la elegibilidad.

---

# 42. NO RELEASE FENCE

PASS no libera fence.

BLOCKED no libera fence.

Crash no libera fence.

1.9E termina con el business todavía fenced.

---

# 43. NO 1.9F

No:

- conectar producción;
- restaurar copia de producción;
- descargar backups;
- ejecutar sobre Railway;
- usar datos de clientes.

Fixtures y DB descartable únicamente.

La prueba contra restauración real pertenece a 1.9F y requerirá orden humana separada.

---

# 44. MIGRACIONES

SQLite:

- clean→73;
- 72→73;
- vacío73→72→73;
- con reconciliation durable downgrade bloqueado.

PostgreSQL equivalente.

Datos históricos/live previos deben conservar:

- bytes;
- hashes;
- events;
- links;
- operations;
- authorizations;
- import results.

No modificar migrations 63–72 retroactivamente.

---

# 45. TESTS HAPPY PATH

Construye escenario sintético completo razonable:

cut
→ manifest certifiable
→ import batch
→ historical events
→ reconcile.

Debe terminar PASS solo cuando todo cuadre.

Comprobar hashes/result reproducibles.

---

# 46. TESTS BLOCKED

Como mínimo:

- source drift;
- manifest hash conflict;
- missing import item;
- import result conflict;
- missing event;
- tampered content;
- wrong operation;
- wrong authorization;
- historical op COMMITTED;
- wrong dependency;
- missing relation;
- extra relation;
- unexpected historical event;
- live coverage contamination;
- sequence mismatch;
- fiscal reference conflict;
- blocking incidence;
- batch partial;
- batch blocked.

No reparar ninguno.

---

# 47. TESTS SEMÁNTICOS

Payment + bank match:

→ reconciliación reconoce un hecho de caja y evidencia match, no dos cash events.

Supplier/expense observed B:

→ conservar evidence basis observed_state.

Unknown:

→ sigue unknown.

No zero inventado.

Factura historical v2:

→ continúa no permitida.

---

# 48. TESTS EXISTING

Nuevo batch que referencia evento histórico previo:

→ PASS si proof original y nuevo result existing son correctos.

Cambiar historical_batch del evento:

→ BLOCKED.

Covered existing live:

→ PASS si coverage/event exactos.

---

# 49. SQL CORRUPTION TESTS

Con fixtures controlados o mecanismos QA:

- historical HUMAN;
- event sin proof;
- import recorded sin event;
- duplicate identity;
- wrong relation;
- wrong business sequence.

Reconciler debe detectarlo aunque en operación normal los guards lo impidan.

No debilitar guards productivos para montar test.

---

# 50. PERFORMANCE

Fixture grande razonable.

Verificar:

- O(N+E) o cercano;
- paginación;
- índices usados razonablemente;
- sin N+1 grave por evento cuando puede agruparse.

No establecer SLO productivo.

---

# 51. DOCUMENTACIÓN

Crear:

- contrato `FINANCIAL-HISTORY-RECONCILIATION-v1.md`
- ADR correspondiente;
- cierre 1.9E.

Actualizar FASE-1.9-plan sin marcar:

- 1.9F iniciada;
- production tested;
- activation ready.

Debe quedar explícito:

inventory certifiable
≠
import completed
≠
reconciliation PASS
≠
production rehearsal
≠
activation.

---

# 52. AUTOAUDITORÍA

Responder explícitamente:

1. ¿Reconciliation puede crear Economic Events?
2. ¿Puede modificar import results?
3. ¿Puede reclasificar A/B/C/D?
4. ¿Puede modificar sources?
5. ¿Puede recalcular fiscal como verdad nueva?
6. ¿Counts sustituyen identidad?
7. ¿Puede item candidate carecer de explicación terminal y obtener PASS?
8. ¿Puede historical event huérfano obtener PASS?
9. ¿Puede operation historical COMMITTED obtener PASS?
10. ¿Puede historical_unknown tener actor/session?
11. ¿Puede duplicated identity obtener PASS?
12. ¿Puede parent B satisfacer verified dependency?
13. ¿Puede bank match contarse como segundo cash?
14. ¿Puede live coverage contaminada pasar?
15. ¿Puede source drift pasar?
16. ¿PASS libera fence?
17. ¿PASS activa flags?
18. ¿Se consultó producción?
19. ¿Se inició 1.9F?
20. ¿Todo cambio fuera de reconciliation tables permanece cero?

---

# CIERRE

Devuélveme:

- arquitectura;
- archivos;
- migration;
- schema;
- catálogo findings;
- lifecycle;
- precondiciones;
- reconciliation algorithm;
- source verification;
- item accounting;
- import result verification;
- operations/auth verification;
- Economic Event verification;
- dependency graph;
- existing coverage;
- fiscal verification;
- money;
- sequence;
- hashes;
- concurrency;
- crash/retry;
- multiempresa;
- side-effect proof;
- SQLite;
- PostgreSQL;
- migration cycles;
- performance;
- suite/gates;
- riesgos;
- PASS/FAIL individual;
- autoauditoría.

No declares 1.9E cerrada si un resultado PASS puede coexistir con una fuente no explicada, un Economic Event histórico no acreditado, una Operation/Auth histórica incoherente o una dependencia rota.

**No avances a Fase 1.9F.**