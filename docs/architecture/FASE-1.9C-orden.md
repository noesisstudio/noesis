Las Fases 0–1.8H, 1.9A y 1.9B quedan aceptadas.

Ejecuta exclusivamente:

# FASE 1.9C — EPOCH, CORTE T0 Y FENCE TRANSACCIONAL

NO avances a 1.9D.

Esta fase debe crear una frontera demostrable entre:

**estado legacy histórico observado**

y

**escrituras financieras posteriores**.

Todavía NO debe:

- importar Economic Events históricos;
- crear Financial Operations históricas para backfill;
- ejecutar `EconomicEvents.append(origin="historical")`;
- activar cuentas;
- convertir manifests diagnósticos de 1.9B en manifests certificables por simple UPDATE;
- implementar reconciliación final;
- ejecutar backfill.

Los cinco flags Financial Core continúan OFF.

---

# OBJETIVO

Al finalizar 1.9C debe existir una forma segura y comprobable de:

1. abrir un `epoch` histórico para un business;
2. adquirir una exclusión breve y consistente;
3. establecer T0;
4. instalar un fence durable;
5. impedir que escrituras financieras legacy relevantes atraviesen ese fence;
6. permitir lecturas/inventario por páginas sin mantener una transacción gigante;
7. detectar cualquier writer/ruta que intente escapar del protocolo;
8. abortar/inutilizar el corte de forma explícita;
9. producir un manifest asociado a ese epoch que pueda ser considerado **certifiable inventory**, pero todavía NO importable;
10. conservar cinco flags OFF.

No implementar el importer.

---

# 1. AUDITORÍA PREVIA OBLIGATORIA DE WRITERS

Antes de cambiar schema/código, inventaría TODOS los caminos que pueden modificar una fuente o evidencia que participa en 1.9.

Incluye como mínimo:

### Invoice
- invoices
- invoice_lines
- document profiles vinculados a invoice
- emisión
- drafts
- rectificativas
- cambios de status por cobro
- recordatorios si afectan hashes de inventario

### Fiscal
- invoice_records
- invoice_events cuando se usan como evidencia
- VERI*FACTU outbox
- invoice_cancellation_records
- cancellation outbox

### Payments
- invoice_payments
- invoice status derivado

### Bank
- bank_transactions
- bank_payment_links

### Purchasing
- received_invoices
- expenses
- suppliers si sus datos forman parte de evidencia interpretativa
- logical void

### Documents
- documents
- document classifications
- enlaces source↔document

### Recurring
- recurring_invoice_runs
- recurring_invoices cuando afectan procedencia

### Financial Core existente
- Economic Events
- links
- coverage tables 65–67

Para cada mutación documenta:

- API/writer;
- tabla;
- business scope;
- lock actual;
- si usa business gate;
- si puede producirse por SQL directo soportado;
- si debe quedar bloqueada durante fence;
- si puede seguir permitida porque no afecta el corte.

No escribas guards hasta terminar este mapa.

---

# 2. QUÉ ES T0

T0 NO es:

- `MAX(id)`;
- una fecha de creación;
- `created_at <= now`;
- el inicio de un scan largo;
- el momento en que se ejecutó 1.9B.

T0 es el instante durable en el que, bajo exclusión transaccional del business:

1. todas las escrituras financieras anteriores han terminado;
2. se registra un epoch;
3. se activa el fence;
4. cualquier nueva mutación protegida debe respetar ese fence.

Debe quedar timestamp con zona y generación monotónica por business.

T0 no convierte datos dudosos en correctos.

Solo fija el conjunto temporal observable.

---

# 3. MIGRACIÓN 71

Determina la siguiente migration real; previsiblemente 71.

Debe añadir exclusivamente infraestructura de epoch/fence/certificación.

Conceptualmente:

## `financial_history_epochs`

Como mínimo:

- business_id
- epoch_uuid
- generation
- state
- opened_by
- opened_at
- t0
- fence_enabled
- fence_version
- invalidated_at
- invalidated_by
- invalidation_reason
- released_at cuando proceda
- source_scope_version
- created_from_repository_version
- timestamps de auditoría

Estados cerrados y pequeños, por ejemplo:

- preparing
- fenced
- invalidated
- released

Adapta nombres a la arquitectura real.

No crear estados vagos tipo processing/active sin semántica exacta.

## Relación manifest ↔ epoch

NO conviertas manifests diagnósticos existentes de 1.9B en certificados.

Un manifest de corte certificable debe:

- referenciar epoch;
- tener un modo distinto e inmutable;
- conservar invariantes de 1.9B;
- nunca ser `eligible_for_import=true` todavía.

Puede requerir una nueva fila manifest o extensión controlada del schema existente.

Preferencia:

**nuevo manifest certifiable derivado por nueva ejecución de inventory bajo fence**, no promoción de uno diagnóstico antiguo.

---

# 4. UN SOLO EPOCH ACTIVO POR BUSINESS

A nivel DB debe ser imposible que el mismo business tenga dos fences históricos activos.

PostgreSQL:

constraint/index/lock equivalente seguro.

SQLite:

invariante equivalente.

Dos procesos intentando abrir epoch simultáneamente:

solo uno gana.

El perdedor:

→ conflicto explícito.

No “reutilizar” epoch automáticamente salvo retry con identidad exacta.

---

# 5. BUSINESS GATE

Usar la misma exclusión por business ya establecida en 1.8H.

Orden canónico:

business gate
→ epoch/fence control
→ operation/source locks.

Nunca:

source/operation
→ business gate.

Opening del epoch debe:

1. autenticar operador;
2. adquirir business gate;
3. bloquear/controlar fila de epoch;
4. validar que no existe otro epoch activo;
5. registrar T0/fence;
6. commit rápido.

No mantener esa transacción durante el scan histórico.

---

# 6. FENCE DURABLE

Una vez commit del fence:

toda mutación financiera relevante del business debe comprobarlo dentro de SU PROPIA transacción.

No basta con:

```text
SELECT fence_enabled
```

sin lock/serialización.

La comprobación debe formar parte del mismo protocolo de business gate/control row.

No permitir ventana:

check=false
→ otro proceso activa fence
→ writer continúa y commit.

El orden compartido debe impedirla.

---

# 7. SEMÁNTICA DEL FENCE

Mientras un epoch está `fenced`:

las mutaciones legacy que puedan cambiar el conjunto histórico/evidencia deben fallar cerrado.

Error específico y reconocible, no error SQL genérico cuando pueda evitarse.

Conceptualmente:

`HistoricalFenceActive`.

No hagas fallback.

No ejecutes mutación después.

---

# 8. QUÉ DEBE BLOQUEARSE

Como mínimo cualquier operación que pueda alterar:

- identidad de source;
- estado económico;
- amount;
- fechas económicas;
- relación parent;
- lines;
- payment rows;
- bank rows;
- matches;
- received invoice;
- expense;
- documento/evidencia usada en manifest;
- registros fiscales;
- cancellation records;
- cobertura Financial Core.

Pero NO bloquees indiscriminadamente todo el SaaS.

Acciones claramente no relacionadas con evidencia histórica pueden continuar si demuestras que no alteran el source set/hash.

Ejemplos posibles:

- login;
- lecturas;
- preferencias UI;
- mensajes no financieros.

Documenta la frontera.

---

# 9. WRITERS CAPTURE YA EXISTENTES

Aunque los cinco flags estén OFF, los Capture services existen.

Durante fence:

NO deben crear nuevos efectos financieros en ese business.

Es decir:

- InvoiceCapture
- PaymentCapture
- BankCapture
- SupplierInvoiceCapture
- ExpenseCapture

también deben respetar el fence.

No basta con bloquear solo legacy.

De lo contrario podríamos tener:

T0
→ fence
→ evento live nuevo
→ inventario mezcla frontera.

---

# 10. ECONOMIC EVENTS EXISTENTES

`EconomicEvents.append(origin="live")` debe respetar el mismo fence mientras 1.9C está activo para ese business, salvo que el diseño demuestre un camino futuro de handoff explícito que todavía NO existe.

En esta fase:

fence activo
→ no nuevo live economic fact.

No permitir bypass llamando directamente `EconomicEvents.append`.

---

# 11. TRANSPORTES Y ESTADOS ASÍNCRONOS

Cuidado con VERI*FACTU outboxes.

Distinguir:

**crear/cambiar evidencia económica/fiscal**
de
**actualizar estado de transporte externo ya existente**.

No quiero que el fence deje necesariamente al worker fiscal incapaz de registrar una respuesta AEAT previamente enviada si esa actualización NO cambia la verdad económica/fiscal que se inventaría.

Audita cada campo.

Puede permitirse transportar/registrar resultado externo postcommit si no cambia:

- invoice;
- invoice_record;
- fiscal hash;
- source set requerido para clasificación.

Pero si esos estados forman parte del manifest/certificación:

deben estabilizarse o representarse correctamente.

Documenta la decisión exacta.

NO hacer llamadas AEAT dentro del proceso de epoch.

---

# 12. DOCUMENTOS

Mismo análisis.

Un documento usado como evidencia histórica no puede cambiar durante un cut certificable.

Debes bloquear:

- reemplazo;
- relink;
- revisión;
- clasificación relevante

si forma parte del source set del manifest.

Pero no necesitas congelar un documento completamente ajeno al scope financiero histórico.

Tenant/scope obligatorio.

---

# 13. SCOPE DEL FENCE

Define un `source_scope_version`.

Inicialmente puede ser fijo v1 y cubrir exactamente el catálogo de fuentes auditado.

No permitir que el cliente elija tablas arbitrarias.

El fence debe saber qué writers/tables protege.

Si en el futuro cambia el catálogo:

nuevo scope version.

Un epoch v1 no se reinterpreta con reglas v2.

---

# 14. MANIFEST CERTIFICABLE

1.9B creó manifests diagnostic.

1.9C debe permitir un nuevo modo conceptualmente:

`certifiable_inventory`

o equivalente.

Invariantes:

- vinculado a un epoch `fenced`;
- creado después de T0;
- scope/version coincide;
- environment identity explícita;
- source set leído mientras fence continúa activo;
- segunda lectura/hash coherente;
- drift = BLOCKED;
- `certifiable=true` solo cuando se cumplen invariantes;
- `eligible_for_import=false` todavía.

IMPORTANTE:

certifiable ≠ importable.

1.9D decidirá incorporación.

---

# 15. NO PROMOCIÓN DE MANIFEST 1.9B

Debe ser imposible:

```sql
UPDATE financial_history_manifests
SET certifiable=true
WHERE ...
```

sobre un diagnostic.

No migration automática que convierta antiguos manifests.

Un diagnóstico anterior puede utilizarse como comparación humana, pero el corte certificado necesita scan nuevo asociado al epoch.

Añade tests SQL.

---

# 16. INVENTORY BAJO FENCE

Reutiliza readers/classifier/planning 1.9B.

No dupliques scanner.

Debe existir un modo explícito de ejecutar inventory contra un epoch.

Diferencias frente diagnostic:

- exige epoch válido;
- exige fence activo;
- snapshot/manifest asociado a T0;
- verifica control row entre páginas;
- si fence se invalida/desactiva → abortar;
- resultado potencialmente certifiable.

No cambiar reglas A/B/C/D.

---

# 17. NO MANTENER LOCK DURANTE TODO EL SCAN

No mantener business advisory lock durante minutos.

El patrón debe ser:

### Apertura

TX corta:
gate
→ fence ON
→ T0
→ commit.

### Scan

TXs cortas/paginadas:
validar fence/epoch
→ SELECT raw
→ persist inventory
→ commit.

### Freeze

TX corta:
gate
→ comprobar fence aún vigente
→ segunda comprobación de conjunto/hash
→ freeze manifest certifiable
→ commit.

Mientras tanto writers están bloqueados por el fence durable, no por una transacción larga.

---

# 18. INVALIDACIÓN

Necesitamos poder invalidar un epoch.

Casos:

- timeout operativo;
- administrador decide abortar;
- error del inventory;
- scope mismatch;
- guard descubierto incompleto;
- corrupción/drift inesperado.

Invalidar:

- es append/audit-safe;
- registra actor/reason/time;
- hace que manifest NO pueda certificarse;
- no borra inventory;
- no abre automáticamente los writers si semánticamente sigue siendo inseguro.

Define claramente diferencia:

`invalidated`
vs
`released`.

---

# 19. RELEASE

No liberes automáticamente fence porque terminó el scan.

Esto es crítico.

Si se libera:

legacy puede volver a escribir
→ el cut deja de ser frontera vigente para un futuro import.

Según el diseño de Astra:

un manifest puede seguir siendo evidencia del estado observado,
pero deja de ser elegible como frontera actual.

Por tanto:

`release fence`

debe:

- registrar durablemente hora/actor;
- invalidar `boundary_current`;
- impedir usar ese epoch en 1.9D salvo nuevo cut;
- NO borrar manifest.

No implementar activación.

---

# 20. CRASH

Escenarios:

### Crash después de fence commit antes de scan

El fence debe seguir activo.

Retry debe recuperar el epoch existente.

NO crear otro.

### Crash durante scan

Fence sigue activo.

Retry continúa manifest/crea nueva ejecución según identidad definida, pero no pierde T0.

### Crash después de manifest frozen

Fence sigue activo hasta acción explícita futura.

Nada se libera por finally/cleanup implícito.

---

# 21. TTL / WATCHDOG

No implementes un cron sofisticado.

Pero define y prueba cómo detectar un fence demasiado antiguo.

Un fence expirado NO se libera automáticamente.

Debe quedar:

`attention_required`

o señal equivalente para intervención.

Seguridad antes que disponibilidad.

No permitir que un timeout vuelva a habilitar writers silenciosamente.

---

# 22. SQL DIRECTO

Éste es un criterio importante.

Los guards de aplicación no bastan si existe SQL directo soportado/admin que pueda mutar tablas relevantes.

Para tablas clave, evalúa triggers/guards SQL que consulten el fence.

No añadas trigger a absolutamente todas las tablas sin análisis.

Prioriza fuentes financieras donde el bypass rompería T0.

Los triggers deben:

- scope por business;
- funcionar PG/SQLite;
- no bloquear migrations/instalación;
- permitir las operaciones explícitamente no económicas documentadas cuando sea seguro.

Documenta cualquier tabla que permanezca protegida solo por protocolo de aplicación y por qué.

---

# 23. DELETE BUSINESS

Un business con epoch/fence/manifests no puede borrarse destruyendo evidencia.

Integrar con guards existentes de conservación.

No resolver política RGPD final.

No implementar purge.

Simplemente fallar cerrado.

---

# 24. CONCURRENCIA — TEST CENTRAL

PostgreSQL real, procesos/conexiones separadas.

Debes probar determinísticamente:

### Writer empieza primero

T1:
business gate
→ writer

T2:
intenta abrir epoch

Resultado:

epoch espera; T0 solo se registra DESPUÉS de commit/rollback del writer.

### Epoch empieza primero

T1:
gate
→ activa fence
→ commit.

T2:
writer entra
→ detecta fence
→ falla ANTES de mutar.

### Dos epochs

Solo uno activo.

### Epoch + InvoiceCapture
bloqueado.

### Epoch + PaymentCapture
bloqueado.

### Epoch + BankCapture
bloqueado.

### Epoch + PurchasingCapture
bloqueado.

### Epoch + writer legacy
bloqueado.

### Epoch + EconomicEvents.append live directo
bloqueado.

No usar sleeps como única sincronización.

Barreras/locks reales.

---

# 25. SQLITE

BEGIN IMMEDIATE y protocolo equivalente.

No afirmar que tiene la misma granularidad que PostgreSQL, pero sí mismos invariantes observables.

Fence commit debe impedir futura mutación financiera.

---

# 26. SIDE EFFECTS DEL OPEN EPOCH

Abrir un epoch SOLO puede modificar:

- tablas nuevas de epoch/control;
- metadata necesaria del manifest/cut.

NO:

- invoices;
- payments;
- bank;
- expenses;
- received;
- EE;
- Operations;
- authorizations;
- fiscal.

Comparar snapshots before/after.

---

# 27. SIDE EFFECTS DE WRITER BLOQUEADO

Intentar writer bajo fence:

→ ninguna fila financiera cambia.

Ni siquiera:

- sequence;
- invoice number;
- status;
- outbox;
- FinancialOperation committed;
- Economic Event sequence.

El error debe ocurrir suficientemente temprano.

---

# 28. EXISTING OPERATIONS PREPARED/APPROVED

Caso delicado:

una FinancialOperation puede estar PREPARED o APPROVED antes de T0.

Después se activa fence.

No debe poder ejecutar durante fence.

Authorization histórica/live permanece como evidencia pero ejecución bloqueada.

No cancelarla automáticamente.

Tras liberar/invalidate en el futuro deberá volver a pasar las reglas que correspondan; no diseñar eso ahora.

Test obligatorio.

---

# 29. RECURRENTES

Un recurring draft/occurrence preparado antes de T0:

NO se emite durante fence.

Scheduler puede leer, pero no generar una mutación financiera que cambie el cut.

Decide si creación de nuevos borradores recurrentes afecta source set.

Si invoices drafts forman parte del inventario/out_of_scope, crear un draft cambia membership y por tanto debe quedar bloqueado durante fence certifiable.

Sé conservador.

---

# 30. IMPORT CSV / DOCUMENT REVIEW

Igualmente:

no permitir que, durante fence, un CSV cree nuevos bank_transactions ni una revisión documental confirme received/expense.

Procesamiento externo previo sin escritura económica puede continuar si no altera evidence scope.

---

# 31. FLAGS

Cinco flags siguen OFF.

Fence NO es activación.

No activar Financial Core para conseguir el corte.

No cambiar comportamiento normal de businesses sin fence.

Regression obligatoria:

business A fenced
business B normal

B sigue operando.

---

# 32. MULTIEMPRESA

Fence estrictamente tenant-scoped.

Un business bloqueado NO afecta:

- otro business;
- sus locks;
- sus writers;
- su scheduler.

Tests con IDs coincidentes.

---

# 33. AUTORIDAD

Abrir/invalidate/release epoch requiere operador actual autenticado y permiso:

`historical.record`

o capacidad interna equivalente definida.

No `financial.authorize`.

No human financial authorization.

No inventar actor histórico.

Registrar `opened_by`, `invalidated_by`, `released_by`.

---

# 34. NO IMPORTER

Aunque exista manifest certifiable:

NO crear todavía:

- FinancialOperation histórica por item;
- HistoricalAuthorization durable para import;
- EconomicEvent histórico;
- historical coverage.

1.9C acaba antes.

---

# 35. NO PAYLOAD V2 DURABLE

No ampliar todavía EconomicEvent storage para los tres v2 históricos especiales.

Pertenece a 1.9D cuando el importer esté listo.

No aprovechar migration 71 para meterlo “de paso”.

---

# 36. MIGRACIÓN / DOWNGRADE

Probar:

SQLite:
- clean→71
- 70→71
- vacío71→70→71
- con epoch/evidence downgrade bloqueado.

PostgreSQL equivalente.

No alterar migration 70.

No resolver el bug preexistente de downgrade PG29 salvo que impida directamente estos tests.

Documentarlo aparte.

---

# 37. PRUEBAS DE HASH

Con fence activo y sin writers:

dos scans equivalentes:

→ mismo source_set_hash/plan semántico si reglas iguales.

Intento de writer rechazado:

→ hash sigue igual.

Business distinto mutado:

→ hash del fenced business no cambia.

---

# 38. TESTS DE RELEASE

Tras release:

- epoch conserva historia;
- manifest conserva historia;
- certifiable/boundary-current semantics cambian correctamente;
- no se borra nada.

Si un writer posterior modifica source:

el antiguo manifest no puede presentarse como frontera vigente.

No necesitas ejecutar 1.9D para demostrarlo.

---

# 39. TESTS DE INVALIDATE

Invalidate antes de freeze:

→ manifest BLOCKED/no certifiable.

Invalidate después de freeze:

→ manifest conserva inventory pero pierde elegibilidad como boundary current.

No reescribir hashes.

---

# 40. OBSERVABILIDAD

Añadir logging/audit mínimo:

- epoch opened
- T0
- fence enabled
- manifest frozen
- invalidated
- released
- blocked writer attempt

sin copiar payload financiero sensible completo.

No crear nuevo sistema de observabilidad.

---

# 41. PERFORMANCE

Medir únicamente overhead razonable del check de fence.

No optimices prematuramente.

Un business sin active epoch debe pagar coste mínimo y indexado.

No hacer scan de history tables en cada writer.

Debe existir lookup/control eficiente por business.

---

# 42. SEGURIDAD

Auditar:

- IDOR epoch;
- cross-tenant;
- forged epoch_uuid;
- release por otro user;
- stale session;
- SQL direct bypass;
- race open/release;
- permission revocation.

No almacenar credenciales/environment URLs en epoch.

---

# 43. DOCUMENTACIÓN

Crear:

- ADR específico de cut/fence;
- contrato `FINANCIAL-HISTORY-CUTOFF-v1.md` o equivalente;
- mapa de writers auditados;
- cierre 1.9C.

Documentar claramente:

**diagnostic manifest 1.9B**
≠
**certifiable inventory 1.9C**
≠
**importable history 1.9D**

Y:

**certifiable**
≠
**activation ready**.

---

# 44. AUTOAUDITORÍA

Responder:

1. ¿T0 usa MAX(id)?
2. ¿Se mantiene una TX durante todo el scan?
3. ¿Puede un writer que empezó antes de T0 commit después y quedar fuera?
4. ¿Puede un writer empezar después de T0 y mutar?
5. ¿Puede Capture saltarse fence?
6. ¿Puede EE live directo saltarse fence?
7. ¿Puede SQL directo relevante saltarse fence?
8. ¿Puede otro business quedar bloqueado?
9. ¿Dos epochs activos simultáneos?
10. ¿Crash libera fence?
11. ¿TTL libera fence?
12. ¿Diagnostic manifest puede promocionarse por UPDATE?
13. ¿Certifiable implica importable?
14. ¿Release conserva falsamente boundary_current?
15. ¿Prepared/Approved previo puede ejecutar?
16. ¿Se creó EE histórico?
17. ¿Se implementó durable v2 histórico?
18. ¿Se inició 1.9D?

---

# CIERRE

Devuélveme:

1. mapa completo de writers;
2. archivos;
3. migration;
4. schema epoch/control;
5. estados;
6. protocolo exacto de T0;
7. fence enforcement;
8. application guards;
9. SQL guards;
10. tratamiento Capture;
11. EconomicEvents;
12. fiscal/async;
13. documents/recurring;
14. manifests certifiable;
15. crash/retry;
16. invalidate/release;
17. permisos;
18. SQLite;
19. PostgreSQL;
20. carreras;
21. side-effect proof;
22. performance;
23. migration cycles;
24. suite/gates;
25. riesgos;
26. PASS/FAIL individual;
27. autoauditoría.

No declares 1.9C cerrada si existe cualquier camino soportado que pueda modificar una fuente/evidencia del corte después de T0 sin invalidar o bloquear el epoch.

**No avances a Fase 1.9D.**