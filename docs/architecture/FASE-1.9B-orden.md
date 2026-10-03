Las Fases 0–1.8H y 1.9A quedan aceptadas.

Ejecuta exclusivamente:

# FASE 1.9B — INVENTARIO HISTÓRICO PERSISTENTE Y DRY-RUN DIAGNÓSTICO

NO avances a 1.9C.

Esta fase puede:

- leer fuentes legacy;
- conservar evidencia cruda;
- crear manifests diagnósticos;
- crear items;
- clasificar A/B/C/D;
- registrar incidencias;
- registrar decisiones de revisión;
- construir candidatos históricos en memoria;
- resolver dependencias de forma diagnóstica;
- producir un dry-run durable y reproducible.

Esta fase NO puede:

- persistir Economic Events históricos;
- crear Financial Operations históricas;
- ejecutar `EconomicEvents.append`;
- ejecutar Capture;
- ejecutar writers;
- crear epoch certificable;
- activar fence;
- hacer backfill;
- reconciliar como PASS de activación;
- activar cuentas.

Los cinco flags Financial Core permanecen OFF.

---

# 1. BASE

Trabaja sobre el `main` real posterior al cierre de 1.9A.

Lee obligatoriamente:

- `AGENTS.md`
- `ADR-014-financial-history-contracts.md`
- `FINANCIAL-HISTORY-v1.md`
- `FASE-1.9-plan.md`
- cierre 1.9A
- diseño original completo 1.9
- migrations históricas relevantes
- esquema actual 69
- contratos de Economic Events
- Financial Operations
- coberturas 65–67
- source revisions de 64
- código legacy de invoices/payments/bank/purchasing/documents/recurring

Antes de programar, construye un mapa exacto de las tablas/campos que se utilizarán como evidencia.

---

# 2. OBJETIVO PRINCIPAL

Al terminar 1.9B debe ser posible ejecutar:

```text
business
   ↓
historical diagnostic scan
   ↓
manifest
   ↓
raw source items
   ↓
A / B / C / D
   ↓
dependencies
   ↓
incidences
   ↓
candidate plan
   ↓
READY_FOR_REVIEW o BLOCKED
```

sin ningún efecto financiero.

---

# 3. MANIFEST DE ESTA FASE: DIAGNÓSTICO, NO CERTIFICABLE

Éste es un punto crítico.

1.9C implementará corte/epoch/fence.

Por tanto todo manifest creado en 1.9B debe quedar inequívocamente marcado como:

**diagnostic / non-certifiable**

Nunca debe poder ser utilizado por el futuro importer.

No utilices nombres que puedan hacer parecer que el corte está certificado.

Debe existir un invariant estructural equivalente a:

```text
manifest_mode = diagnostic
eligible_for_import = false
```

No basta con documentación.

Un manifest 1.9B NO demuestra T0.

---

# 4. MIGRACIÓN 70

Crea la siguiente migración disponible sobre el `main` real si continúa siendo 70.

Esta migración debe incluir únicamente persistencia necesaria para 1.9B.

Conceptualmente:

### `financial_history_manifests`

Información mínima:

- business_id
- manifest_uuid
- mode = diagnostic
- schema_version observado
- repository/code version
- reader_version
- classifier/rule version
- canonicalization version
- scope version
- environment/copy identity cuando exista
- created_by
- started_at
- completed_at
- status
- source_set_hash
- plan_hash
- counts/result summary
- frozen_at

### `financial_history_items`

Por unidad de evidencia/hecho candidato:

- business_id
- manifest_uuid
- item_uuid
- source_type
- source_id
- revision identity
- fact slot
- proposed event type cuando exista
- raw evidence canonical
- raw evidence hash
- assessment
- disposition
- severity
- rule id/version
- candidate canonical cuando exista
- candidate hash
- dependency canonical
- existing coverage reference
- terminal inventory result

### `financial_history_incidences`

- business
- manifest
- item
- incidence code
- severity
- evidence hash
- status
- created_at

### `financial_history_decisions`

Append-only:

- business
- manifest
- incidence/item
- actor
- decision type
- evidence references
- reason code
- previous decision cuando corresponda
- decided_at

Adapta nombres si el schema real aconseja otra forma.

NO crear aún:

- `financial_history_epochs`
- fence/control table
- reconciliations finales
- historical Economic Event coverage
- durable historical payload support.

Eso pertenece a unidades posteriores.

---

# 5. INMUTABILIDAD

Una vez un manifest llega a `frozen`:

NO se modifica:

- scope;
- raw evidence;
- source hashes;
- classification original;
- candidate plan;
- dependencies;
- source_set_hash;
- plan_hash.

Una decisión manual futura se añade como nueva fila.

No reescribe evidencia.

No borrar manifest/items/incidences/decisions con evidencia.

Diseña equivalencia SQLite/PostgreSQL mediante constraints/triggers donde sea necesario.

---

# 6. LECTORES RAW

Implementa `financial_history/readers` o estructura equivalente.

Los lectores:

- reciben `FinancialSession` o conexión prestada;
- son read-only;
- no hacen commit;
- no llaman Capture;
- no llaman writers;
- no llaman EconomicEvents.append;
- no llaman proveedores externos;
- no llaman IA;
- no abren conexiones adicionales.

Deben poder leer únicamente un business.

Nunca query global sin filtro tenant.

---

# 7. FUENTES QUE DEBEN INVENTARIARSE

Como mínimo:

### Facturación

- invoices
- invoice_lines
- invoice document/fiscal profile realmente relevante
- invoice_records
- invoice_events legacy solo como evidencia auxiliar cuando corresponda
- verifactu outbox únicamente como evidencia de transporte, nunca de hecho económico

### Rectificativas

- relationship original/rectificative

### Cobros

- invoice_payments

### Banco

- bank_transactions
- bank_payment_links
- import-related legacy identity existente

### Compras

- received_invoices
- suppliers donde sean necesarios para interpretar source
- documents relacionados
- document classification mínima

### Gastos

- expenses
- documents relacionados

### Fiscal cancellation

- invoice_cancellation_records
- cancellation outbox solo como evidencia auxiliar

### Recurring

- recurring_invoice_runs
- recurring schedule únicamente como evidencia auxiliar.

### Existing Financial Core

- Economic Events existentes
- links
- invoice coverage
- payment coverage
- bank coverage
- purchasing coverage

para detectar:

`COVERED_EXISTING`

y NO duplicarlos.

---

# 8. UNA FILA NO EQUIVALE NECESARIAMENTE A UN ITEM

El item representa una unidad de evidencia/hecho candidato.

Ejemplos:

un `bank_transaction` puede producir:

- item `bank_transaction.imported`
- y eventualmente item `bank_transaction.matched`

Una invoice rectificativa:

- item de su emisión/rectificación

Una source auxiliar:

- puede existir como item/evidence sin candidato Economic Event.

No fuerces un evento por cada fila.

---

# 9. PAGINACIÓN

Los lectores deben trabajar por páginas.

No cargar todo el negocio en memoria.

Usar claves estables únicamente para paginar.

ID/PK puede ordenar lectura, pero:

**NO define T0.**

Evita `OFFSET` creciente si genera comportamiento O(N²) en datasets grandes.

Prefiere keyset pagination cuando corresponda.

---

# 10. EVIDENCIA MONETARIA CRUDA

Éste es uno de los criterios principales de 1.9B.

No uses `boundary.snapshot()` como única fuente monetaria histórica.

Debe capturarse la representación REAL de almacenamiento.

## SQLite REAL

Conservar como mínimo:

- `typeof(column)`
- valor observado
- bits IEEE-754 del valor si aplica
- representación decimal exacta del binario
- representación textual disponible
- candidate cent value diagnóstico
- delta
- provenance.

## PostgreSQL DOUBLE PRECISION

Conservar equivalentemente:

- tipo
- texto que devuelve PostgreSQL
- representación binaria/bytes de float8 de forma estable
- valor decimal exacto de esos bits
- candidate cent value
- delta.

Para NUMERIC:

→ Decimal exacto.

Para TEXT monetario exacto:

→ string exacto validado.

Nunca pasar por:

```text
float → str → Money
```

como afirmación de precisión original.

---

# 11. REGLA DE DINERO

Un importe contractual requerido para candidato A/B únicamente puede utilizarse si cumple las reglas 1.9A:

- exact evidence;
o
- binary evidence corroborated por otra evidencia decimal durable suficiente.

`candidate_cent_value` por sí solo:

NO basta.

Ejemplo:

`12.340000000000002`

puede producir:

candidate = `12.34`

pero:

classification/importability no pasa a segura solo por estar cerca del céntimo.

Si falta corroboración:

incidencia `MONEY_BINARY_UNCORROBORATED`.

Subcéntimo material:

`MONEY_SUBCENT`.

---

# 12. VALORES MIGRADOS RETROSPECTIVAMENTE

Inspecciona migrations reales y detecta valores que pueden haber sido creados/rellenados retrospectivamente.

Especial atención:

- `invoice_payments` con método `registro_anterior`;
- invoice_lines sintetizadas desde total;
- series asignadas retrospectivamente;
- document/fiscal profile añadido posteriormente;
- `_financial_revision` inicial de 64.

El reader debe conservar provenance suficiente para que el clasificador sepa:

`original_source`
vs
`migration_derived`
vs
`unknown`.

Si una migración no dejó marcador suficiente para distinguir un valor original de uno reconstruido:

NO inventes la distinción.

Registrar:

`SOURCE_HISTORY_LOST`

u otra incidencia aprobada que corresponda.

---

# 13. EXISTING COVERAGE

Antes de generar candidato:

buscar cobertura Financial Core existente.

Si existe:

1. verificar business;
2. source;
3. revision;
4. event type;
5. event hash;
6. relationships relevantes.

Si es coherente:

`Disposition.COVERED_EXISTING`.

NO candidato nuevo.

Si existe cobertura pero contradice source/evidencia:

`EXISTING_EVENT_CONFLICT`
+
BLOCKED.

Nunca reparar automáticamente.

---

# 14. FACTURAS

Construye reglas deterministas.

### Borrador

→ `OUT_OF_SCOPE`.

No D.

### Factura capturada ya existente

→ `COVERED_EXISTING` tras verificar.

### Invoice legacy potencialmente emitida

Inventariar:

- business
- id
- status
- number
- series
- type
- invoice_type
- dates
- customer
- lines
- bases
- VAT
- IRPF
- total
- currency
- rectification relation
- fiscal/document profile evidence
- invoice record
- hash/previous hash/QR references disponibles.

NO regenerar nada.

La clasificación debe ser conservadora.

Si existe contradicción fiscal/económica:

C
+
`FISCAL_AMOUNT_MISMATCH`.

---

# 15. FACTURA V2 HISTÓRICA

La decisión de 1.9A continúa:

**no permitir todavía candidato histórico invoice payload v2 importable**

hasta disponer de contrato de raw evidence suficiente para:

- líneas;
- totals;
- fiscal record;
- provenance.

En 1.9B sí puedes inventariar/calcular diagnóstico de esos campos.

Pero su disposition debe permanecer bloqueada/no importable conforme al contrato existente.

No relajes esta decisión para aumentar A/B.

---

# 16. RECTIFICATIVAS

Identificar R1–R5.

Debe resolverse original por relación explícita.

No usar:

- customer;
- importe;
- fecha;
- número cercano

para inferir original.

Original ausente/no acreditado:

`RECTIFICATION_PARENT_MISSING`
→ C/D según regla.

No convertir rectificativa a invoice.issued.

---

# 17. PAGOS

Inventariar cada fila real de `invoice_payments`.

Comprobar:

- business;
- invoice;
- amount;
- paid_at;
- method;
- accumulated amount;
- invoice total;
- existing coverage.

Regla especialmente importante:

`method = registro_anterior`

NO es A automáticamente.

Debe producir como mínimo:

`SYNTHETIC_LEGACY_PAYMENT`

salvo evidencia corroborante suficiente identificada por una regla explícita.

No considerar:

`invoice.status = cobrada`

como cobro si no existe evidencia admitida.

`cobrada` sin payment:

`PAID_WITHOUT_PAYMENT`.

Sobrecobro:

`PAYMENT_OVER_TOTAL`.

Posibles duplicados:

`POSSIBLE_DUPLICATE_PAYMENT`.

No modificar ninguno.

---

# 18. BANCO

Para `bank_transaction.imported` inventariar:

- business;
- transaction ID;
- amount/currency;
- booked_on;
- description/reference;
- import hash;
- account scope si existe;
- batch/row identity si existe;
- created timestamp;
- financial revision;
- existing coverage.

No inventar retrospectivamente:

- account_scope;
- statement_hash;
- batch;
- row key.

Si solo se conoce movimiento observado pero no identidad bancaria completa:

B puede ser válido únicamente si el contrato histórico v2 admite exactamente esa limitación.

Si ni siquiera se acredita suficientemente el movimiento:

C.

---

# 19. MATCH BANCARIO

Para match:

la existencia histórica de:

`suggested_invoice_id`

NO demuestra conciliación.

Un match candidato exige evidencia inequívoca de:

bank transaction
↔
invoice payment.

`bank_payment_links` válido:

evidencia fuerte.

Sin vínculo durable inequívoco:

`BANK_LINK_AMBIGUOUS`.

No relacionar por importe/fecha.

---

# 20. FACTURAS RECIBIDAS

Para legacy generalmente esperamos:

B — observed state.

Pero no lo hardcodees sin validar.

Inventariar:

- supplier
- invoice number
- issued_on
- due_on
- total
- base
- VAT
- IRPF
- status
- document references
- revision
- raw money
- coverage.

`pagada` continúa siendo estado operativo.

No crea supplier payment.

Revisión 3 NO implica que podamos reconstruir:

confirmed → corrected → corrected.

Sin snapshots anteriores:

no crear correcciones históricas.

---

# 21. GASTOS

Misma filosofía:

estado actual puede ser B si consistente y monetariamente acreditado.

Inventariar:

- concept
- amount
- VAT fields conocidos
- spent_on
- created metadata
- project/document refs
- revision
- coverage.

No inferir IVA.

No reconstruir gastos físicamente borrados sin evidencia durable.

---

# 22. FISCAL CANCELLATION

Inventariar todos los `invoice_cancellation_records`.

No conectar productor runtime.

No crear Economic Event.

Resolver dependencia explícita a invoice.

Comprobar:

- record
- business
- invoice
- original invoice record
- reason
- timestamps
- fiscal hashes/chaining disponible
- outbox únicamente como evidencia auxiliar.

Nunca interpretarlo como:

- invoice void económico;
- devolución;
- deuda cancelada.

---

# 23. DOCUMENTOS Y OCR

Documentos son evidencia auxiliar.

NO productores automáticos.

No copiar:

- PDF bytes;
- imágenes;
- XML completo;
- conversación;
- OCR íntegro

al manifest.

Guardar solamente los campos permitidos por FINANCIAL-HISTORY-v1:

- IDs
- hashes
- revisiones
- campos mínimos necesarios
- provenance.

OCR/classification no transforma C/D en A automáticamente.

---

# 24. RECURRENTES

Inventariar únicamente si ayuda a explicar procedencia de una invoice.

Un schedule/run legacy:

NO acredita mandato original.

Run sin fingerprint:

no reconstruir autoridad.

No producir nuevo tipo Economic Event.

---

# 25. CLASIFICADOR

Implementar reglas puras/versionadas.

Input:

raw evidence tipada.

Output:

- Assessment;
- disposition;
- candidate opcional;
- incidences;
- dependencies.

No DB dentro del clasificador.

No LLM.

No llamadas externas.

Mismos inputs/version:

→ mismo resultado.

---

# 26. CANDIDATE PLAN

Para candidatos válidos construye únicamente representación `HistoricalCandidate`.

NO:

- `EconomicEvent`;
- `FinancialOperation`;
- insert durable EE.

Debe poder mostrar qué se PREVERÍA incorporar en una fase posterior:

- historical identity
- event type
- payload version
- payload
- evidence basis
- evidence hash
- amount
- dates
- dependencies
- candidate hash.

Para tipos cuyo contrato durable aún no existe:

el plan puede mostrar candidato contractual pero marcar:

`not_durably_supported`

o disposición equivalente bloqueante.

No falsear readiness.

---

# 27. DEPENDENCIAS

Resolver usando HistoricalIdentity/existing coverage.

Orden conceptual:

invoice
→ rectification/payment/fiscal cancellation

bank import + payment
→ match

supplier confirmed
→ correction
→ void

expense confirmed
→ void.

Padre C/D:

hijo no candidate-importable.

Padre B:

conservadoramente bloqueado según contrato 1.9A salvo regla explícita futura.

No inferencia por amount/date.

---

# 28. INCIDENCIAS DURABLES

Persistir los 14 códigos cerrados de 1.9A.

No añadir nuevos códigos sin necesidad demostrada.

Cada incidencia debe conservar:

- business
- manifest
- item
- code
- severity
- evidence hash
- rule version
- status.

No almacenar texto libre como semántica principal.

---

# 29. DECISIONES MANUALES

Implementar únicamente registro append-only de decisión.

Decisiones permitidas según contrato:

- añadir evidencia;
- aceptar interpretación respaldada;
- excluir justificadamente;
- mantener bloqueo.

Una decisión:

NO puede cambiar raw evidence.

NO puede inventar actor original.

NO puede convertir automáticamente un candidato C/D en A sin nueva evidencia compatible.

Debe registrar:

- actor actual;
- timestamp;
- evidence refs;
- decision type;
- reason;
- previous decision cuando aplique.

---

# 30. DRY-RUN

Crear servicio explícito de dry-run diagnóstico.

Entrada:

business_id
+
scope/version
+
operator autenticado.

Salida:

manifest durable.

Debe poder entregar:

- fuentes inspeccionadas;
- counts;
- A/B/C/D;
- covered_existing;
- out_of_scope;
- excluded;
- pending incidences;
- candidates por event type/version;
- dependencies;
- broken dependencies;
- raw money problems;
- fiscal discrepancies;
- plan hash;
- source set hash.

Resultado final:

`READY_FOR_REVIEW`
o
`BLOCKED`

Pero nunca:

`READY_FOR_IMPORT`.

1.9B no puede certificar importabilidad porque todavía no existe T0/fence.

---

# 31. SIDE EFFECT GUARD

Añade tests estructurales/AST o equivalentes que garanticen que `financial_history` 1.9B:

NO importa ni llama:

- Capture services;
- financial_writers;
- `EconomicEvents.append`;
- `FinancialOperations.execute`;
- AEAT;
- Meta;
- OCR/LLM provider.

Si necesita utilizar tipos/contracts, permitido.

Persistencia propia del manifest sí.

---

# 32. DRIFT

Como todavía NO hay fence:

un dry-run diagnóstico puede detectar que una fuente cambió entre lectura y freeze.

Si detecta cambio:

`SOURCE_DRIFT`
+
manifest BLOCKED.

Aunque no detecte drift:

el manifest sigue siendo **non-certifiable**.

No afirmar corte estable.

Esto debe quedar estructuralmente representado.

---

# 33. HASH DEL CONJUNTO

`source_set_hash` debe depender de:

- pertenencia del conjunto;
- source identity;
- revision identity;
- raw evidence hash.

Alta, baja o modificación cambia hash.

Ordenar determinísticamente antes de hash.

No usar `MAX(id)`.

---

# 34. PLAN HASH

`plan_hash` debe incluir como mínimo:

- manifest scope/version;
- classifier version;
- item identities;
- assessments;
- candidate hashes;
- dependencies;
- incidences/dispositions.

Una decisión posterior NO reescribe el plan inicial.

Si requiere un plan revisado:

nueva versión/snapshot/manifest según diseño documentado.

No mutación silenciosa.

---

# 35. IDEMPOTENCIA DEL DRY-RUN

Retry de la misma ejecución lógica debe poder recuperarse sin duplicar items.

La identidad del manifest no debe derivarse exclusivamente del reloj.

Define claramente diferencia entre:

- retry del mismo manifest
- nuevo diagnóstico intencional.

Mismos source/raw + misma regla:

→ mismos item identities/candidate hashes.

---

# 36. MULTIEMPRESA

Todos los nuevos objetos:

- manifest
- item
- incidence
- decision

incluyen business_id.

FKs/queries siempre tenant-scoped.

Pruebas con IDs coincidentes entre businesses.

No permitir evidence ref cruzada.

---

# 37. PERMISOS

Crear dry-run requiere permiso específico apropiado, preferentemente:

`historical.record`

o una capacidad interna equivalente existente.

No utilizar `financial.authorize`.

No crear autorización histórica.

No atribuir el inventario al owner original.

Registrar únicamente operador actual.

---

# 38. NO HISTORICAL FINANCIAL OPERATION

Reiteración:

1.9B NO crea:

- EntryIdentity durable en financial_operations;
- financial_authorizations;
- FinancialOperation;
- Economic Event.

Solo utiliza contratos históricos puros para PLANIFICAR.

Esto simplifica rollback y evita confundir diagnóstico con backfill.

---

# 39. MIGRACIONES

Pruebas obligatorias:

SQLite:

- clean install → 70
- 69→70
- downgrade vacío cuando sea seguro
- evidencia existente bloquea downgrade destructivo
- reupgrade

PostgreSQL equivalente.

No perder nada de 62–69.

No tocar Economic Events.

---

# 40. TESTS DE INVENTARIO

Crear fixtures sintéticos que representen casos reales de migration history.

Como mínimo:

### Invoice

- legacy verificable;
- profile potencialmente migrado;
- línea sintética cuando pueda identificarse;
- record fiscal ausente;
- mismatch fiscal;
- rectificativa sin padre.

### Payment

- real;
- `registro_anterior`;
- cobrada sin payment;
- overpayment;
- duplicate possible.

### Bank

- movimiento con identidad suficiente;
- observed-only;
- ambiguous identity;
- valid link;
- suggestion without link.

### Purchasing

- received consistent observed state;
- revision >1 sin historia;
- unknown VAT;
- expense observed;
- subcent.

### Fiscal cancellation

- coherent;
- parent missing.

### Existing Core

- covered existing;
- conflicting existing.

---

# 41. TESTS DE RAW MONEY

Ambos motores donde aplique:

- exact TEXT;
- exact NUMERIC;
- REAL;
- DOUBLE;
- binary residue;
- 0.1;
- 2.675;
- subcent real;
- -0.0 si aparece;
- NULL;
- zero;
- NaN;
- Infinity;
- amount enorme/rango.

No convertir estos tests en assertions basadas solo en `round()`.

---

# 42. TESTS DE MANIFEST

- manifest diagnostic;
- immutable frozen;
- source set hash estable;
- membership changes hash;
- content changes hash;
- plan hash estable;
- retry;
- second intentional run;
- incidences append;
- decisions append;
- cross-business rejected;
- delete/update frozen rejected.

---

# 43. TESTS SIDE EFFECTS

Después de dry-run comparar antes/después:

- invoices;
- lines;
- payments;
- bank;
- received;
- expenses;
- invoice records;
- outboxes;
- Economic Events;
- Financial Operations;
- authorizations;
- flags.

Solo pueden cambiar las tablas `financial_history_*` autorizadas de 1.9B.

---

# 44. PERFORMANCE

Añadir fixture grande razonable.

Comprobar:

- paginación;
- consultas acotadas;
- memoria acotada;
- ausencia de consulta N+1 por cada source cuando pueda agruparse.

No imponer benchmark artificial de producción.

Pero documentar query shape.

---

# 45. NO PRODUCCIÓN

No conectar a producción.

No ejecutar dry-run sobre Railway/productivo.

No copiar base real.

Esta subfase se valida exclusivamente con:

- fixtures sintéticos;
- bases descartables;
- SQLite;
- PostgreSQL de tests.

El ensayo sobre restauración real pertenece a 1.9F.

---

# 46. NO 1.9C

No implementar:

- epoch durable certificado;
- T0 certificable;
- fence;
- write blocking;
- transición validating;
- live boundary.

Un manifest 1.9B debe seguir diciendo claramente:

**diagnostic only**.

---

# 47. NO 1.9D+

No implementar:

- durable historical payload v2;
- importer;
- historical append;
- historical coverage;
- reconciliation final;
- activation.

---

# AUTOAUDITORÍA

Antes de cerrar responde explícitamente:

1. ¿Puede dry-run escribir Economic Events?
2. ¿Puede crear Financial Operations?
3. ¿Puede tocar una source legacy?
4. ¿Puede un manifest diagnostic presentarse como certificable?
5. ¿Se usa MAX(id) como cutoff?
6. ¿El raw money cuantiza antes de conservar evidencia?
7. ¿Un `registro_anterior` se acepta como cobro A por sí solo?
8. ¿Status cobrada inventa payment?
9. ¿Suggested invoice inventa bank match?
10. ¿Revision 64 inventa historial previo?
11. ¿Document/OCR se convierten en productores?
12. ¿Existing coverage se duplica?
13. ¿C/D producen candidatos importables?
14. ¿B se presenta como verified fact?
15. ¿Una decisión manual reescribe evidencia?
16. ¿Hay queries cross-business?
17. ¿Se ejecutó contra producción?
18. ¿Se inició 1.9C?

---

# CIERRE

Devuélveme:

1. archivos;
2. migración;
3. schema;
4. lifecycle de manifest;
5. readers;
6. raw money extraction;
7. provenance de migraciones legacy;
8. reglas de clasificación;
9. tratamiento por cada source;
10. existing coverage;
11. candidate planning;
12. dependencies;
13. incidences;
14. decisions;
15. dry-run;
16. hashes;
17. idempotencia;
18. tests SQLite;
19. tests PostgreSQL;
20. performance;
21. side-effect proof;
22. suite general/gates;
23. riesgos;
24. PASS/FAIL individual;
25. autoauditoría.

No declares 1.9B cerrada si el dry-run puede producir un efecto financiero o si un manifest diagnóstico puede confundirse con un corte histórico certificado.

**No avances a Fase 1.9C.**