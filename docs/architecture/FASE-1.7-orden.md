Las Fases 1.1–1.6 quedan aceptadas.

Ejecuta exclusivamente:

**FASE 1.7 — Facturas recibidas y gastos como productores de Economic Events**

NO avances a 1.8.

Antes de modificar código, lee el estado actual real del repositorio y todos los ADR/contratos relevantes de Fase 1, especialmente:

- `ECONOMIC-EVENTS-v1.md`
- `ECONOMIC-PERSISTENCE-v1.md`
- `FINANCIAL-OPERATIONS-v1.md`
- `BORROWED-WRITERS-v1.md`
- ADR-008
- cierres 1.4–1.6
- código actual de `financial_writers/purchasing.py`
- `financial_writers/documents.py`
- `documents/service.py`
- recibidas/gastos en `db.py`
- revisiones `_financial_revision`

## OBJETIVO

Conectar exclusivamente estos productores:

### Facturas recibidas

- `supplier_invoice.confirmed`
- `supplier_invoice.corrected`
- `supplier_invoice.voided`

### Gastos

- `expense.confirmed`
- `expense.voided`

No crear nuevos tipos de Economic Event.

No implementar supplier payments.

---

# 1. SERVICIOS CANÓNICOS

Construye servicios internos acotados, equivalentes conceptualmente a InvoiceCapture/PaymentCapture.

Por ejemplo:

- SupplierInvoiceCapture
- ExpenseCapture

Los nombres finales pueden adaptarse.

Deben componer:

Financial Operation
→ autorización durable
→ writer prestado
→ Economic Event
→ resultado durable
→ mismo commit.

No dupliques las reglas existentes de recibidas/gastos.

---

# 2. CONFIRMACIÓN DE FACTURA RECIBIDA

Una factura de proveedor confirmada debe producir exactamente:

`supplier_invoice.confirmed`

El hecho debe nacer únicamente cuando la factura ha sido **realmente confirmada**.

NO producir Economic Event por:

- OCR;
- extracción;
- clasificación provisional;
- subida de PDF;
- sugerencia de proveedor;
- documento pendiente de revisión.

Confirmación humana/directa explícita sí puede producirlo cuando exista identidad y autorización durable.

---

# 3. PAYLOAD DE FACTURA RECIBIDA

Mantén payload v1 salvo necesidad técnica demostrable.

Debe derivarse del snapshot realmente escrito.

Incluir según contrato:

- supplier/proveedor cuando proceda;
- número de factura si existe;
- issued_on si se conoce;
- due_on si se conoce;
- total;
- base si se conoce;
- IVA si se conoce;
- IRPF si se conoce;
- confirmed_on;
- referencias/evidencia permitidas por v1.

Regla crítica:

**desconocido ≠ cero.**

No inferir:

IVA = total - base

si la información no se conoce de forma fiable.

No inferir deducibilidad fiscal.

No inferir pago.

---

# 4. supplier_invoice.corrected

Una corrección de una recibida ya capturada produce:

`supplier_invoice.corrected`

Debe contener:

- `before`
- `after`
- `corrected_on`
- motivo

y relación:

`corrects`
→ último Economic Event económico válido de esa recibida.

El evento anterior permanece inmutable.

## Regla crítica de continuidad

Antes de corregir:

la proyección económica ACTUAL del source debe coincidir con el último estado económico cubierto.

Si la fila fue modificada por una ruta legacy después del último Economic Event y sus campos económicos ya no coinciden:

**fallar cerrado.**

No crear un `corrected` fingiendo que conocemos un `before` que nunca fue registrado.

Eso debe quedar para diagnóstico/backfill, no repararse silenciosamente.

---

# 5. REVISIONES

Usa `_financial_revision` de Fase 1.4.

La corrección debe:

1. revisar revision actual;
2. congelar before;
3. comprobar expected_revision;
4. ejecutar writer;
5. obtener revisión nueva;
6. congelar after;
7. generar Economic Event sobre la nueva revisión;
8. commit conjunto.

Una revisión stale:

→ rechazar.

No sobreescribir silenciosamente.

---

# 6. BAJA DE FACTURA RECIBIDA

Actualmente existe borrado físico.

Una factura recibida que ya forma parte del Financial Core:

**NO puede borrarse físicamente.**

Necesitamos conservar el origen porque:

- Economic Events tiene FK;
- existe evidencia económica;
- futuras contabilidad/fiscalidad necesitan trazabilidad.

Implementa una retirada lógica mínima.

Puede ser:

- `voided_at`;
- `void_reason`;
- estado interno equivalente;

según encaje con el schema.

No conviertas esto en un sistema genérico de soft delete.

---

# 7. supplier_invoice.voided

La retirada produce:

`supplier_invoice.voided`

Payload:

- snapshot `before`;
- `voided_on`;
- motivo.

Relación:

`voids`
→ último `supplier_invoice.confirmed` o `supplier_invoice.corrected`.

La fila origen se conserva.

NO significa:

- pago;
- devolución bancaria;
- abono del proveedor;
- extinción de AP;
- asiento inverso todavía.

Es únicamente el hecho económico de retirada/cancelación del registro recibido.

---

# 8. COMPORTAMIENTO LEGACY TRAS VOID

Los lectores actuales deben conservar el comportamiento visible esperado:

si antes DELETE hacía que una recibida desapareciera de:

- listas;
- gestoría;
- cálculos actuales;
- exportaciones operativas;
- consultas del usuario,

la fila lógicamente retirada debe dejar de aparecer allí donde corresponda.

Pero:

**la evidencia financiera no se destruye.**

Revisa explícitamente todos los lectores afectados.

No ocultes indiscriminadamente evidencia en herramientas internas/auditoría.

---

# 9. STATUS `pagada`

No interpretes:

`received_invoice.status = pagada`

como:

`supplier_payment.made`.

No existe evidencia suficiente de:

- importe liquidado;
- fecha;
- cuenta;
- medio;
- transferencia.

Por tanto:

NO crear supplier payment.
NO crear settlement.
NO generar Economic Event de pago.

Documenta esta diferencia.

---

# 10. EXPENSE CONFIRMED

Una alta de gasto capturada produce:

`expense.confirmed`

Debe representar el gasto realmente registrado, no OCR/sugerencia.

Payload según v1:

- total;
- spent_on si existe;
- description;
- vat_amount si se conoce;
- confirmed_on.

No inferir IVA si no existe información explícita.

No implica pago a proveedor/AP.

---

# 11. EXPENSE VOIDED

Un gasto capturado ya confirmado no puede desaparecer físicamente.

La retirada produce:

`expense.voided`

con:

- `before`;
- `voided_on`;
- motivo.

Relación:

`voids`
→ `expense.confirmed`.

El origen debe conservarse.

Lectores legacy deben tratarlo como retirado para preservar UX/comportamiento funcional.

---

# 12. CORRECCIÓN DE GASTOS

El catálogo actual NO contiene `expense.corrected`.

No inventes ese evento.

Si existe una necesidad real de corregir un gasto:

la semántica aprobada es:

1. retirar gasto anterior;
2. crear un nuevo gasto;
3. producir `expense.voided`;
4. producir `expense.confirmed` para el nuevo origen.

Pero NO crees un nuevo endpoint/flujo de usuario si actualmente no existe una operación de corrección.

Si implementarlo no es necesario para cubrir escritores existentes, documenta esta semántica para el futuro y mantén la fase acotada.

---

# 13. COBERTURA DURABLE

Diseña cobertura mínima para recibidas y gastos.

A diferencia de invoice coverage, el mismo source puede producir varios eventos a lo largo del tiempo.

La cobertura debe identificar como mínimo:

- business;
- source;
- source revision;
- operation;
- event UUID;
- event type.

Debe permitir:

```text
received_invoice #12 rev1
→ confirmed

received_invoice #12 rev2
→ corrected

received_invoice #12 rev3
→ voided
```

sin sobrescribir coberturas anteriores.

Y:

```text
expense #8 rev1
→ confirmed

expense #8 rev2
→ voided
```

La cobertura debe ser inmutable.

---

# 14. ÚLTIMO ESTADO ECONÓMICO

Crea una forma fiable de localizar el último Economic Event económico válido de cada source.

No lo infieras por:

`MAX(event_uuid)`
ni por fecha de aplicación.

Usar:

- revisión;
- business_sequence;
- cobertura;
- relación explícita;

según sea más correcto.

Una corrección/void debe enlazar exactamente con el antecedente correspondiente.

---

# 15. MODIFICACIONES LEGACY NO CAPTURADAS

Una vez un source está capturado:

una ruta legacy NO debe poder modificar campos económicos importantes saltándose el productor.

Debe:

- pasar por capture;
o
- fallar cerrado.

No hace falta integrar todavía todos los canales 1.8.

Pero estructuralmente no permitas:

capturado
→ legacy UPDATE económico
→ sin Economic Event.

Para modificaciones puramente operativas/no económicas, documenta claramente cuáles pueden seguir ocurriendo y cómo afectan `_financial_revision`.

---

# 16. DOCUMENTOS

Revisa los flujos:

- `record_received_invoice`
- `confirm_received_invoice`
- ticket → expense
- revisión/clasificación documental.

Objetivo:

documento
+ source confirmado
+ clasificación necesaria
+ Economic Event
+ resultado

deben poder compartir transacción cuando se use el camino capturado.

No ejecutar dentro de esa transacción:

- OCR;
- IA;
- correo;
- disco remoto;
- proveedores externos.

Esos pasos ocurren antes/después según corresponda.

---

# 17. DINERO

Mantener:

- Decimal en dominio nuevo;
- EUR;
- JSON monetario string;
- procedencia legacy binaria explícita.

No migrar REAL/DOUBLE todavía.

Antes de persistir evento:

snapshot/payload deben cuadrar con la fila realmente guardada.

No presentar como exacto un float histórico convertido posteriormente.

No corregir céntimos silenciosamente.

---

# 18. FECHAS

Distingue:

- issued_on de proveedor;
- spent_on;
- confirmed_on;
- corrected_on;
- voided_on;
- observed_at.

No inventes zonas horarias para fechas legacy.

No crear todavía accounting_date.

---

# 19. IDEMPOTENCIA

Mismo operation/request:

→ mismo source/result/event.

No volver a:

- crear recibida;
- corregirla;
- retirarla;
- crear gasto;
- retirarlo;
- generar otro evento.

Misma identidad + contenido diferente:

→ conflicto.

Dos documentos legítimos iguales:

→ operaciones/identidades distintas permitidas.

---

# 20. ATOMICIDAD

### Confirmación recibida

source
+
document links/classification cuando aplique
+
coverage
+
Economic Event
+
resultado

mismo commit.

### Corrección

before
+
UPDATE
+
new revision
+
Economic Event corrected
+
relation corrects
+
resultado

mismo commit.

### Void

source preservado
+
marca lógica
+
new revision
+
Economic Event voided
+
relation voids
+
resultado

mismo commit.

### Gasto

misma filosofía.

Fallo en cualquier punto:

ROLLBACK COMPLETO.

---

# 21. FALLBACK

Flags globales siguen apagados.

Legacy puede seguir funcionando para sources no capturados mientras corresponda.

Pero:

si se solicita captura:

**NO fallback silencioso.**

Y si un source ya está capturado:

no permitir mutación económica legacy sin evento.

---

# 22. NO SUPPLIER PAYMENTS

Reiteración explícita:

NO implementar:

- `supplier_payment.made`;
- AP settlement;
- conciliación de pagos proveedor;
- remesas;
- transferencias;
- Open Items AP.

Aunque la recibida diga `pagada`.

---

# 23. NO TAX ENGINE

Los eventos pueden contener IVA/IRPF conocido.

Eso NO significa:

- IVA deducible;
- gasto fiscalmente deducible;
- período tributario;
- modelo 303;
- asiento contable.

No implementar Tax Ledger.

---

# 24. MIGRACIÓN

Añade únicamente lo necesario para:

- cobertura por revisión;
- conservación lógica del origen;
- guards;
- razones/fechas de void si hacen falta;
- integridad e inmutabilidad.

No añadir:

- GL;
- Open Items;
- supplier payments;
- Tax Ledger;
- reporting nuevo;
- histórico/backfill;
- activación por cuenta.

---

# 25. TESTS — FACTURAS RECIBIDAS

Confirm:

- manual;
- documental;
- datos completos;
- datos parciales;
- base/IVA conocidos;
- base/IVA desconocidos;
- IRPF;
- fechas opcionales.

Corrección:

- importe;
- fecha;
- proveedor/datos relevantes;
- stale revision;
- dos correcciones sucesivas;
- correcciones concurrentes.

Void:

- confirm → void;
- correct → void;
- razón obligatoria;
- source conservado;
- lectores legacy lo ocultan.

---

# 26. TESTS — GASTOS

- confirm;
- documento/ticket cuando aplique;
- IVA conocido/desconocido;
- fecha;
- descripción;
- void;
- retry;
- stale;
- concurrencia.

Comprobar que no existe `expense.corrected`.

---

# 27. TESTS — HISTORIA

Comprobar explícitamente:

supplier invoice:

```text
confirmed
→ corrected
→ corrected
→ voided
```

Los cuatro Economic Events permanecen.

Relations:

```text
corrected2 corrects corrected1
corrected1 corrects confirmed
voided voids corrected2
```

Nada se modifica.

Expense:

```text
confirmed
→ voided
```

ambos permanecen.

---

# 28. TESTS — LEGACY BYPASS

Intentar SQL/API legacy económico sobre source capturado:

→ rechazado o redirigido al servicio autorizado.

Intentar DELETE físico:

→ rechazado.

Source no capturado con flags OFF:

→ comportamiento legacy documentado/preservado.

---

# 29. TESTS — MULTIEMPRESA

Cruzar:

- source;
- documento;
- proveedor;
- operación;
- autorización;
- cobertura;
- evento antecedente.

Todo rechazado.

---

# 30. FALLOS INYECTADOS

Para correction/void:

fallar después de:

1. lock;
2. captura before;
3. mutación;
4. revisión;
5. coverage;
6. Economic Event;
7. link;
8. resultado durable.

Nada parcial debe sobrevivir.

---

# 31. AUTOAUDITORÍA

Antes de cerrar responde:

1. ¿Puede una recibida capturada cambiar económicamente sin evento?
2. ¿Puede borrarse físicamente una recibida capturada?
3. ¿Puede borrarse físicamente un gasto capturado?
4. ¿Puede un corrected perder su before real?
5. ¿Puede un corrected enlazar con un antecedente incorrecto?
6. ¿Puede un void implicar supplier payment?
7. ¿Puede status pagada generar un pago falso?
8. ¿Puede IVA desconocido convertirse en cero?
9. ¿Puede un gasto inventar `expense.corrected`?
10. ¿Puede un retry duplicar source/event?
11. ¿Puede una ruta documental confirmar source y evento en commits distintos?
12. ¿Puede un source de otra empresa enlazarse?
13. ¿Algún float legacy se presenta como exactitud recuperada?
14. ¿Se adelantó AP/Open Items/Tax/GL?

---

# CIERRE

Devuélveme:

- arquitectura SupplierInvoiceCapture/ExpenseCapture;
- productores conectados;
- cobertura por revisiones;
- estrategia de logical void;
- lectores legacy afectados;
- comportamiento de status `pagada`;
- documentos/transacción;
- payloads;
- exactitud;
- idempotencia;
- concurrencia;
- rollback;
- migración;
- tests SQLite;
- tests PostgreSQL;
- riesgos;
- canales pendientes;
- PASS/FAIL individual.

No declares 1.7 terminada si un source capturado puede ser modificado o eliminado económicamente sin dejar un Economic Event nuevo e inmutable.

**No avances a 1.8.**