Las Fases 0–1.8H y 1.9A–1.9C quedan aceptadas.

Ejecuta exclusivamente:

# FASE 1.9D — IMPORTER HISTÓRICO DURABLE

NO avances a 1.9E.

Esta fase introduce por primera vez incorporación histórica real al Economic Event Layer.

Solo puede operar sobre:

- epoch vigente y `fenced`;
- manifest 1.9C congelado;
- manifest `certifiable=true`;
- `boundary_current=true`;
- source scope/version compatible;
- candidato histórico ya congelado en el manifest.

NO consultar producción.

NO ejecutar backfill real.

Validación exclusivamente con fixtures/bases descartables SQLite y PostgreSQL.

Los cinco flags siguen OFF.

---

# 1. PRINCIPIO CENTRAL

El importer histórico:

**registra evidencia histórica.**

NO reproduce el hecho original.

Por tanto nunca llama:

- InvoiceCapture;
- PaymentCapture;
- BankCapture;
- SupplierInvoiceCapture;
- ExpenseCapture;
- financial writers;
- emisión;
- cobro;
- conciliación live;
- APIs fiscales;
- AEAT;
- Meta;
- OCR;
- IA.

Cadena conceptual:

certifiable manifest
→ frozen candidate
→ Historical Import Context
→ operación histórica no ejecutable
→ historical_unknown
→ Economic Event origin=historical
→ durable import result
→ commit.

No efecto legacy.

---

# 2. AUDITAR ESTADO REAL ANTES DE IMPLEMENTAR

Lee:

- AGENTS
- ADR-014, ADR-015, ADR-016
- FINANCIAL-HISTORY-v1
- FINANCIAL-HISTORY-INVENTORY-v1
- FINANCIAL-HISTORY-CUTOFF-v1
- cierres 1.9A/B/C
- migrations 63–71
- Financial Operations
- Economic Events schema/service/repository
- contratos históricos
- classifier/planning
- manifest/items
- fence/cutoff
- SQL guards de migration 71.

No asumas que el diseño inicial coincide exactamente con el runtime actual.

---

# 3. NO `bypass_fence=True`

Regla absoluta:

NO introducir parámetros genéricos como:

- `bypass_fence`
- `ignore_fence`
- `force`
- `admin_override`

que puedan reutilizar Capture, writers o llamadas live.

El permiso para escribir historia debe provenir de una **capacidad/import context tipado y acotado a un item concreto de un manifest concreto**.

Debe quedar ligado como mínimo a:

business
+
epoch
+
manifest
+
item
+
candidate hash
+
historical identity
+
operador actual.

No puede construirse desde input del LLM/canal.

---

# 4. MIGRACIÓN 72

Determina la siguiente migration real; previsiblemente 72.

Debe añadir únicamente infraestructura imprescindible para incorporación histórica.

Preferencia arquitectónica:

### `financial_history_import_batches`

o equivalente mínimo:

- business_id
- batch_uuid
- manifest_uuid
- epoch_uuid/generation
- importer_version
- created_by
- created_at
- status
- source_set_hash
- plan_hash

Un batch debe referenciar exactamente un manifest certificable.

### `financial_history_import_items`

o equivalente:

- business_id
- batch_uuid
- manifest_uuid
- item_uuid
- candidate_hash
- historical identity/hash
- operation_uuid
- authorization_uuid
- event_uuid
- event_type
- state/result
- recorded_by
- imported_at

Esta tabla puede actuar como:

**import intent + durable import result**

si se diseña de forma segura.

No es obligatorio usar exactamente estos nombres.

Pero NO mutar silenciosamente los items congelados de 1.9B/C para convertirlos en resultados de importación.

---

# 5. NO REINTERPRETAR MANIFEST

Un manifest congelado permanece inmutable.

No cambiar:

- classification;
- assessment;
- raw;
- candidate;
- dependencies;
- incidences;
- hashes;
- plan.

1.9D puede decidir si un candidato ya congelado tiene soporte durable en la versión actual del importer.

Eso debe quedar en la capa de importación, no reescribiendo el inventario.

---

# 6. `eligible_for_import=false`

No reutilices el booleano de 1.9C de forma engañosa.

Preferencia:

mantener los manifests de C con:

`eligible_for_import=false`

y representar la autorización técnica de incorporación mediante el batch/import plan de D.

Así preservamos:

certifiable inventory
≠
historical import execution.

Si consideras imprescindible cambiar esta semántica, debes justificarlo y probar migración/compatibilidad explícitamente.

No lo cambies por comodidad.

---

# 7. HISTORICAL IMPORT CONTEXT

Crear un contrato interno congelado.

Conceptualmente:

`HistoricalImportContext`

con:

- business_id
- epoch_uuid
- generation
- manifest_uuid
- batch_uuid
- item_uuid
- candidate_hash
- historical_identity
- event_uuid esperado
- operation_uuid esperado
- recorded_by
- importer_version.

Debe validarse contra DB dentro de la misma transacción.

No confiar únicamente en un objeto Python construido previamente.

---

# 8. VALIDACIÓN OBLIGATORIA EN CADA ITEM

Antes de cualquier write durable:

1. permiso/sesión actuales válidos;
2. cinco flags OFF;
3. business gate;
4. epoch sigue `fenced`;
5. control apunta a ese epoch/generation;
6. manifest sigue frozen/certifiable/boundary_current;
7. hashes del manifest coinciden;
8. item pertenece a ese manifest/business;
9. raw hash coincide;
10. candidate hash coincide;
11. candidate canonical reconstruye correctamente;
12. assessment/disposition permitidos;
13. no blocking incidence aplicable;
14. dependencias resueltas;
15. source actual sigue coincidiendo con evidencia congelada requerida.

Cualquier discrepancia:

→ no evento;
→ no operación parcial;
→ conflicto/incidencia de importación;
→ mantener fence.

---

# 9. NO RECLASIFICAR

El importer NO ejecuta nuevamente clasificación para obtener un resultado más favorable.

Carga:

- raw congelado;
- assessment congelado;
- candidate congelado.

Puede comprobar su integridad.

No puede convertir:

C → A
D → B
B → A.

Nueva evidencia o nuevas reglas requieren un nuevo manifest/corte según contratos.

---

# 10. QUÉ ITEMS PUEDEN IMPORTARSE

Solo candidatos explícitos y materialmente soportados.

Como mínimo:

- `classification` A o B cuando el contrato permita B;
- disposition `candidate`;
- candidate presente;
- identidad coherente;
- sin dependencia bloqueante;
- sin conflicto existing event.

C/D nunca.

OUT_OF_SCOPE nunca.

EXCLUDED nunca.

COVERED_EXISTING no crea evento nuevo.

---

# 11. `not_durably_supported`

1.9B dejó candidatos contractuales que entonces no tenían soporte durable.

1.9D puede desbloquear exclusivamente aquellos cuyo único impedimento era soporte de persistencia y cuyo contrato ya fue aprobado en 1.9A.

Inicialmente:

- `supplier_invoice.confirmed` historical v2
- `expense.confirmed` historical v2
- `bank_transaction.imported` historical v2

No uses esta regla para desbloquear cualquier `not_durably_supported`.

Debe existir whitelist/version matrix cerrada.

---

# 12. FACTURA HISTÓRICA SIGUE CONSERVADORA

NO desbloquear por defecto invoice historical v2.

1.9A/B dejaron esta familia bloqueada hasta disponer de un contrato explícito suficiente sobre:

- raw lines;
- totals;
- provenance;
- fiscal record;
- perfiles migrados.

Aunque 1.9B ya lea esa evidencia, no inventes ahora un contrato simplemente para aumentar cobertura.

Si al inspeccionar el código real puede demostrarse que el contrato aprobado ya es suficiente, documenta el razonamiento antes de modificarlo.

Por defecto:

**invoice historical v2 permanece bloqueada.**

---

# 13. VERSION MATRIX DURABLE

Actualmente los payloads históricos especiales v2 viven fuera del durable EconomicEvent.

Añade soporte durable exclusivamente para las versiones autorizadas.

La matriz debe distinguir explícitamente:

### Live

- versiones live actuales exactamente como antes;
- invoice issue/rectify v2 existentes intactos.

### Historical

- v1 existentes cuando sean contractualmente válidos;
- supplier_invoice.confirmed v2 historical;
- expense.confirmed v2 historical;
- bank_transaction.imported v2 historical.

No abrir:

“payload_version = 2 para cualquier tipo”.

SQL + aplicación deben concordar.

Golden tests de bytes/hash existentes obligatorios.

---

# 14. ORIGIN HISTORICAL

Todo evento producido por D:

`origin = historical`

Debe incluir:

- historical batch/import UUID;
- provenance versionada;
- frozen observed/economic dates;
- date provenance correcta;
- recorded_at = momento de incorporación;
- no actor original inventado.

Nunca `origin=live`.

---

# 15. HISTORICAL BATCH

El `historical_batch_uuid` debe tener referencia durable al batch/import context real.

Cadena demostrable:

Economic Event
→ import batch
→ certifiable manifest
→ epoch
→ T0.

No utilizar una UUID sin tabla/contrato que pruebe qué representa.

---

# 16. FINANCIAL OPERATION HISTÓRICA

Cada nuevo Economic Event histórico debe tener una operación histórica durable, salvo que el estado real del código demuestre una razón excepcional mejor.

Preferencia:

**operation_uuid obligatorio para todo evento nuevo de 1.9D.**

La operación:

- namespace historical;
- identidad derivada de HistoricalIdentity;
- request exacto/versionado;
- created_by = operador registrador según contrato existente;
- nunca representa actor original.

No usar una operation live existente salvo COVERED_EXISTING.

---

# 17. HISTORICAL_UNKNOWN

Crear exactamente una authorization durable:

- kind = historical_unknown
- actor_user_id = NULL
- actor_session_version = NULL
- recorded_by = operador actual
- permission = historical.record
- channel/namespace historical.

La operación permanece:

`PREPARED`

y nunca pasa por:

APPROVED
COMMITTED.

El resultado de importación vive en `financial_history_import_items`, no en `financial_operations.result`.

---

# 18. ENDURECIMIENTO SQL DE OPERACIONES HISTÓRICAS

Ahora que 1.9D creará registros históricos reales, los guards solo de aplicación de 1.9A dejan de ser suficientes como defensa estructural.

Añade constraints/triggers mínimos para impedir que una operación durable histórica pueda:

- cambiar namespace a ordinary;
- recibir HUMAN;
- recibir MANDATE;
- pasar a APPROVED;
- pasar a COMMITTED;
- recibir actor/session originales inventados.

No rompas operaciones live.

Probar SQLite/PostgreSQL.

---

# 19. RECORDER HISTÓRICO ESPECÍFICO

NO utilices `FinancialOperations.execute`.

Puede reutilizar:

- contratos;
- repositorio;
- canonicalización;
- identity;
- authorization storage.

Pero debe existir una frontera específica de registro histórico dentro de la transacción del importer.

No abrir otra conexión.

No commit propio.

---

# 20. EXCEPCIÓN AL FENCE — ESTRICTAMENTE ITEM-SCOPED

El importer necesita escribir:

- historical operation;
- historical authorization;
- Economic Event;
- links;
- event sequence;
- import result

mientras el fence continúa activo.

La excepción debe reconocer únicamente escrituras que estén vinculadas a un **import intent durable válido**.

Diseña el mecanismo exacto.

Una opción válida es que `financial_history_import_items` actúe como intent en estado transaccional:

`recording`

con:

- event_uuid esperado;
- operation_uuid esperado;
- candidate hash;
- manifest/item;
- epoch actual.

Los SQL guards pueden permitir exclusivamente escrituras que correspondan a ese intent.

No hace falta usar exactamente esta solución si existe otra más limpia.

Pero no acepto una excepción global por business.

---

# 21. SQL GUARDS DEL FENCE

Migration 71 protege también:

- economic_events;
- economic_event_links;
- economic_event_sequences.

1.9D NO debe desactivar esos triggers.

Modifícalos/adáptalos para permitir únicamente el camino histórico autorizado.

Ejemplo conceptual:

live write
→ fence activo
→ reject.

historical write SIN valid import intent
→ reject.

historical write CON import intent exacto
→ allow.

Debe ser demostrable en SQL directo.

---

# 22. LINKS PREINSERTADOS

Economic Event actual inserta relaciones antes del evento, con FK diferida.

Tenlo en cuenta.

La excepción SQL para `economic_event_links` no puede depender únicamente de consultar una fila de Economic Event que todavía no existe.

El import intent debe permitir validar:

`event_uuid`

antes de insertar links.

No debilites el sellado de relaciones.

---

# 23. EVENT SEQUENCE

La secuencia de negocio debe continuar única y monotónica entre:

live existentes
+
historical incorporados.

No crear segunda secuencia histórica.

El importer adquiere business gate.

Retry:

no vuelve a consumir secuencia si el evento ya existe.

Rollback:

incremento revierte transaccionalmente.

---

# 24. DETERMINISTIC EVENT UUID

El event UUID histórico debe derivarse de identidad histórica versionada, no del reloj/importer.

Mismo hecho:

→ mismo event UUID.

Candidate content incompatible con esa identidad:

→ conflicto.

No crear otra UUID para “hacerlo entrar”.

---

# 25. OPERATION UUID

Igualmente estable.

Mismo HistoricalIdentity:

→ misma EntryIdentity
→ misma operation_uuid.

Operador/manifest/retry no cambian identidad económica.

El batch/manifest sí quedan registrados como procedencia de la incorporación.

---

# 26. RETRY MISMO BATCH

Si se pierde respuesta después del commit:

retry debe recuperar:

- misma operation;
- misma authorization;
- mismo event;
- mismo import result.

Cero duplicados.

No llamar writers.

---

# 27. NUEVO MANIFEST ENCUENTRA EVENTO EXISTENTE

Caso importante:

un evento histórico fue incorporado correctamente por manifest/batch anterior.

Posteriormente otro cut/manifiesto encuentra el mismo hecho.

Debe:

1. encontrar el Economic Event por identidad;
2. verificar contenido;
3. verificar source/revision/type/relations;
4. referenciarlo como existing historical evidence.

NO hacer `append` con otro historical_batch_uuid.

El batch original del evento no se reescribe.

Si el contenido difiere:

`EXISTING_EVENT_CONFLICT`.

---

# 28. DEPENDENCIAS

Resolver exclusivamente por identidad.

### invoice → payment

Payment necesita invoice event exacto.

### invoice → rectification

Original exacto.

### bank imported + payment → match

Ambos exactos.

### invoice → fiscal cancellation

Invoice exacto.

### supplier confirmed → corrected/voided

Antecedente exacto.

### expense confirmed → voided

Antecedente exacto.

No usar:

- amount;
- fecha;
- cliente;
- proximidad.

---

# 29. PARENT COVERED_EXISTING

Un antecedente puede estar:

- live existente verificado;
- historical importado previamente.

Ambos pueden satisfacer una dependencia si el contrato lo permite.

Debe verificarse su Economic Event durable.

No basta con una fila coverage sin revisar el evento.

---

# 30. PADRE B

Mantener la decisión conservadora de 1.9A:

un padre clasificado B no satisface automáticamente una dependencia que requiere un hecho verificado.

No relajar para aumentar cobertura.

Si un tipo concreto permite relación con observed state, debe estar explícitamente aprobado en contrato, no inferido aquí.

---

# 31. SOURCE READER HISTÓRICO

No usar `revision_reader` que simplemente devuelva el número esperado.

Debe demostrar:

- source business;
- source id;
- revisión;
- raw hash;
- evidence relevante

contra el item congelado.

Con fence activo debería coincidir.

Si no coincide:

→ invariant breach / SOURCE_DRIFT;
→ rollback;
→ bloquear import;
→ mantener fence.

Considera invalidar el epoch de forma explícita tras detectar una ruptura real del cut.

Nunca corregir source.

---

# 32. NO REGENERAR FISCAL

Para invoice/fiscal cancellation:

NO:

- recalcular hash fiscal;
- regenerar QR;
- regenerar XML como original;
- crear nuevo invoice_record;
- enviar AEAT;
- modificar outbox.

Solo leer/verificar referencias ya congeladas.

---

# 33. IMPORT RESULT ATÓMICO

En una misma transacción por item:

business gate
→ validate epoch/manifest/item
→ import intent
→ historical operation
→ historical authorization
→ links/event
→ durable import result
→ commit.

Si falla cualquier paso:

ROLLBACK completo.

No operation huérfana.
No authorization huérfana.
No event huérfano.
No import result sin event.

---

# 34. GRANULARIDAD

Predeterminado:

una transacción por candidato.

Agrupar solo cuando exista una necesidad de atomicidad semántica demostrada.

No importar todo el manifest en una transacción gigante.

---

# 35. ORDEN TOPOLÓGICO

Importer debe poder avanzar por candidatos cuyas dependencias están satisfechas.

No O(N²).

Usar índices/plan congelado.

Un hijo no se intenta antes que su padre.

Dependencia bloqueada:

item permanece no importado.

No fabricar padre.

---

# 36. IMPORT BATCH RESULT

El batch debe poder expresar como mínimo:

- running/prepared según diseño;
- completed;
- blocked/partial si procede.

Pero NO afirmar:

- reconciliation PASS;
- activation ready.

Eso pertenece a 1.9E/1.10.

Import completo de todos los candidatos seguros ≠ cobertura financiera completa.

---

# 37. MANIFEST BLOCKED

Un manifest puede ser materialmente certifiable pero tener resultado BLOCKED por fuentes ambiguas.

No confundas esas dos dimensiones.

Puede ser razonable importar candidatos independientes seguros si el contrato permite partial import.

Si lo haces:

- documenta explícitamente;
- batch queda partial/BLOCKED;
- 1.9E debe explicar todo lo restante.

No importes un item bloqueado.

---

# 38. COVERAGE LIVE 65–67

NO insertar filas en las coberturas live existentes fingiendo:

- aprobación humana;
- operation_state committed live.

No debilitarlas.

La cobertura histórica debe derivarse de:

import result
→ Economic Event

y permanecer semánticamente distinta.

1.10 resolverá continuidad de productores live desde antecedentes históricos.

---

# 39. HISTORICAL COVERAGE

Preferencia:

el import result/item durable es la cobertura histórica.

No crear otra tabla duplicada salvo necesidad demostrada.

Debe poder resolver:

HistoricalIdentity
→ event_uuid

de manera indexada y tenant-safe.

---

# 40. NO CONTINUIDAD LIVE TODAVÍA

Después de importar un invoice histórico, NO modifiques todavía PaymentCapture/InvoiceCapture/etc. para utilizarlo automáticamente como antecedente live.

Eso pertenece a transición/activación 1.10 según diseño aprobado.

1.9D solo registra historia.

---

# 41. FENCE PERMANECE ACTIVO

Importar NO:

- release epoch;
- invalidate automáticamente por éxito;
- activar flags.

Después de completar D:

el fence continúa activo.

El negocio sigue protegido.

---

# 42. INVALIDATE / RELEASE DURANTE IMPORT

Si epoch deja de estar fenced/current antes del item:

→ no iniciar.

Si una transición intenta competir con un item import:

business gate serializa.

Después de release/invalidate:

→ nuevos items no importan.

No dejar una transacción iniciada con frontera revocada.

---

# 43. CRASH

Probar:

- crash antes import intent;
- después intent;
- después operation;
- después authorization;
- después links;
- después event;
- después import result antes respuesta.

Todos los pasos precommit desaparecen.

Postcommit retry recupera resultado.

Fence continúa.

---

# 44. CONCURRENCIA

PostgreSQL real con procesos:

- dos importers mismo item;
- mismo item diferente retry;
- dos items del mismo business;
- importer + release;
- importer + invalidate;
- importer + live writer;
- importer + SQL directo live;
- importers de businesses distintos.

Resultado:

- máximo un event por HistoricalIdentity;
- cero write live;
- sin deadlocks por inversión de locks.

---

# 45. MULTIEMPRESA

Todo incluye business_id.

No resolver target/event/dependency únicamente por UUID global sin tenant check.

Pruebas con IDs/source IDs coincidentes entre businesses.

---

# 46. PRIVACIDAD

Economic Event histórico solo contiene contrato económico aprobado.

No copiar al evento:

- raw DB dump;
- bits binarios completos salvo que el payload aprobado lo necesite;
- PDF;
- XML entero;
- OCR;
- conversación;
- notes libres.

Raw evidence permanece en inventory histórico bajo su política específica.

---

# 47. NO PRODUCCIÓN

No ejecutar sobre Railway/productivo.

No importar copia real.

No usar datos de clientes.

Solo fixtures sintéticos y bases descartables.

La restauración real sigue siendo 1.9F.

---

# 48. TESTS — HISTORICAL OPERATION

SQLite y PostgreSQL:

- namespace historical;
- historical_unknown;
- actor NULL;
- session NULL;
- recorded_by actual;
- PREPARED;
- execute rechazado;
- HUMAN rechazado;
- MANDATE rechazado;
- SQL APPROVED rechazado;
- SQL COMMITTED rechazado;
- namespace mutation rechazado.

---

# 49. TESTS — DURABLE V2

Para los tres tipos autorizados:

- supplier invoice confirmed observed state;
- expense confirmed observed state;
- bank imported observed state;
- fecha conocida;
- fecha unknown;
- evidence basis;
- evidence hash;
- null vs zero;
- Decimal exacto.

Comprobar:

- historical → permitido;
- live → rechazado;
- version matrix exacta;
- v1 golden intacto;
- invoice live v2 intacto.

---

# 50. TESTS — FENCE EXCEPTION

SQL directo:

- live Economic Event bajo fence → rechazado;
- historical sin import intent → rechazado;
- historical con manifest incorrecto → rechazado;
- historical con item incorrecto → rechazado;
- candidate hash incorrecto → rechazado;
- import intent válido → permitido exclusivamente para sus UUIDs.

Intentar reutilizar un import intent para otro event:

→ rechazado.

---

# 51. TESTS — DEPENDENCIAS

- parent live existing válido;
- parent historical importado;
- missing;
- B;
- C;
- D;
- cross-business;
- relation incorrecta;
- historical parent con contenido conflictivo.

Nunca heurística amount/date.

---

# 52. TESTS — IDEMPOTENCIA

- retry mismo item;
- timeout postcommit;
- segundo proceso;
- nuevo batch encuentra event existente;
- same identity/different content;
- same event_uuid/different candidate;
- same candidate/different operator.

Operador no cambia identidad del hecho.

---

# 53. TESTS — ZERO SIDE EFFECTS

Antes/después del import histórico comparar:

- invoices;
- lines;
- payments;
- bank;
- received;
- expenses;
- docs;
- invoice records;
- fiscal outboxes;
- cancellation records/outboxes;
- coverage live;
- recurrentes;
- flags.

Solo pueden aparecer:

- historical operation/auth;
- Economic Event/link/sequence;
- import tables/audit.

No efectos legacy.

---

# 54. TESTS — HISTORICAL EVENT HASH

Retry reproduce el Economic Event original.

No recalcular candidate desde reloj.

`observed_at` procede del frozen candidate/evidence.

`recorded_at` puede ser incorporación real y queda durable en el primer commit.

Nuevo retry no lo cambia.

---

# 55. MIGRACIONES

Probar ambos motores:

- clean → 72
- 71 → 72
- vacío 72 → 71 → 72 cuando sea seguro
- con import intent/result/event histórico: downgrade destructivo bloqueado
- events previos live intactos
- hashes previos intactos.

No tocar migration 71 retroactivamente.

---

# 56. REGRESIONES

Reejecutar todas las matrices Core relevantes:

- Financial Operations
- Economic Persistence
- Borrowed Writers
- Invoice
- Payment/Bank
- Purchasing
- Channels
- History A/B/C
- races.

Fence sin import continúa idéntico.

Business sin epoch continúa normal.

---

# 57. AUTOAUDITORÍA

Responder explícitamente:

1. ¿Existe un bypass genérico del fence?
2. ¿Puede Capture utilizar la excepción histórica?
3. ¿Puede un EE live utilizarla?
4. ¿Puede SQL historical sin item válido utilizarla?
5. ¿Puede importar manifest diagnóstico B?
6. ¿Puede importar epoch released/invalidated?
7. ¿Puede importar candidate C/D?
8. ¿Se reclasifica durante import?
9. ¿Se modifica raw evidence?
10. ¿Historical operation puede ejecutarse?
11. ¿Puede recibir HUMAN/MANDATE?
12. ¿Se insertan coverages live 65–67?
13. ¿Se reenvía/recalcula fiscal?
14. ¿Retry duplica sequence/event?
15. ¿Nuevo manifest reescribe historical_batch del evento previo?
16. ¿Un padre B satisface dependencia?
17. ¿Se toca source legacy?
18. ¿Fence se libera tras éxito/crash?
19. ¿Se consultó producción?
20. ¿Se inició 1.9E?

---

# CIERRE

Devuélveme:

1. arquitectura importer;
2. archivos;
3. migration;
4. schema import batch/items;
5. import context;
6. mecanismo exacto de excepción del fence;
7. SQL guards;
8. historical operations;
9. durable version matrix;
10. payloads v2;
11. identidad operation/event;
12. idempotencia;
13. historical batch;
14. source verification;
15. dependencies;
16. coverage existente;
17. import results;
18. partial/block semantics;
19. crash/retry;
20. concurrencia;
21. zero-side-effects;
22. SQLite;
23. PostgreSQL;
24. migraciones;
25. suite/gates;
26. riesgos;
27. PASS/FAIL individual;
28. autoauditoría.

No declares 1.9D terminada si para importar historia debes desactivar el fence, si existe un bypass reutilizable por writes live o si una operación historical_unknown puede convertirse en una operación financiera ejecutable.

**No avances a Fase 1.9E.**