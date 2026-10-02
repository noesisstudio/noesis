# Orden autorizada del titular — 1.6

Transcripción de la petición explícita recibida el 2-oct-2026. Es alcance de ejecución; las referencias del Master Plan son diseño.

Las Fases 1.1–1.5 quedan aceptadas.

Ejecuta exclusivamente:

**FASE 1.6 — Cobros de clientes, importación bancaria y conciliación como productores de Economic Events**

NO avances a 1.7.

Lee obligatoriamente el estado actual real del repositorio, todos los ADR/contratos de Fase 1 y especialmente:

- `ECONOMIC-EVENTS-v1.md`
- `FINANCIAL-OPERATIONS-v1.md`
- `BORROWED-WRITERS-v1.md`
- `INVOICE-CAPTURE-v1.md`
- cierres 1.1–1.5
- código actual de payments, banking, financial_writers, economic_events y financial_operations

---

# OBJETIVO

Conectar exclusivamente estos productores reales:

1. `customer_payment.received`
2. `bank_transaction.imported`
3. `bank_transaction.matched`

Mantener una diferencia semántica fundamental:

**customer_payment.received = hecho económico de caja/cobro**

**bank_transaction.imported = evidencia bancaria**

**bank_transaction.matched = evidencia de conciliación**

`bank_transaction.matched` NO debe representar una segunda entrada de caja.

---

# 1. CUSTOMER PAYMENT CAPTURE

Construye un servicio canónico interno para cobros equivalente conceptualmente a `InvoiceCapture`.

Debe componer:

Financial Operation
→ autorización durable
→ borrowed writer de payments
→ `customer_payment.received`
→ resultado durable
→ mismo commit.

No dupliques el writer existente.

Debe soportar al menos:

- cobro parcial explícito;
- cobro completo/restante;
- cobro originado por conciliación bancaria.

Todos deben converger en el mismo productor del hecho `customer_payment.received`.

---

# 2. RELACIÓN CON FACTURA

Todo `customer_payment.received` capturado debe tener relación obligatoria:

`settles`
→ evento primario de la factura correspondiente.

Debe apuntar a:

- `invoice.issued`
o
- `invoice.rectified`

según corresponda.

Si la factura no dispone de Economic Event capturado válido:

**fallar cerrado.**

No reconstruir historia implícitamente.

La recuperación de facturas legacy corresponde a 1.9.

---

# 3. IMPORTE DEL COBRO

El importe debe proceder de la fila `invoice_payment` realmente creada dentro de la transacción.

No construir el evento desde un float de respuesta pública.

Usar:

- Decimal;
- snapshot del writer;
- source fingerprint;
- paid_at real;
- método real;
- invoice_id real.

El payload aprobado v1 de `customer_payment.received` debe mantenerse salvo necesidad demostrable de nueva versión.

No ampliar versión por comodidad.

---

# 4. COBRO PARCIAL

Flujo:

review
→ request exacto
→ authorize
→ execute
→ payment row
→ Economic Event
→ resultado
→ commit.

Un cobro parcial aprobado por 100 € debe representar exactamente 100 €.

Si entre review y execute cambia el estado de forma que el cobro ya no sea válido:

→ stale/conflict
→ no efecto.

No sobrecobrar.

---

# 5. COBRO COMPLETO / REMAINING

`mark paid` no debe aprobar simplemente “lo que quede cuando ejecutes” sin congelar contexto.

Durante review:

- calcular pendiente real;
- congelar amount aprobado;
- congelar fingerprint/revisión del contexto de liquidación.

Si antes de execute entra otro cobro:

el contexto debe quedar stale y requerir nueva revisión.

Nunca aprobar 500 € pendientes y acabar cobrando 300 € porque cambió el saldo entre ambos momentos.

El Economic Event refleja el importe realmente aprobado y creado.

---

# 6. IDEMPOTENCIA DE COBRO

Misma operación/request:

→ mismo resultado
→ mismo invoice_payment
→ mismo Economic Event.

No insertar segundo cobro.

Request diferente con misma identidad:

→ conflicto.

Dos cobros legítimos del mismo importe:

→ operaciones distintas
→ ambos permitidos si no exceden saldo.

Probar concurrencia PostgreSQL real.

---

# 7. BANK TRANSACTION IMPORTED

Una importación bancaria real debe poder producir:

`bank_transaction.imported`

Este evento es **Evidence / Treasury**, no GL automático.

Debe permitir movimientos:

- positivos;
- negativos.

Un movimiento negativo NO crea supplier payment.

No inferir una obligación ni gasto.

---

# 8. IDENTIDAD DE IMPORTACIÓN BANCARIA

El fingerprint actual por contenido NO basta para demostrar identidad bancaria universal.

Diseña una identidad durable mínima que diferencie:

- reintento de la misma importación;
- misma fila del mismo extracto;
- posible duplicado entre extractos;
- dos movimientos legítimos idénticos.

Necesitamos como mínimo concepto equivalente a:

- import/batch identity;
- row identity;
- account scope del extracto.

No hace falta construir Banking 2.0.

Pero no descartes una fila legítima solo porque:

importe + fecha + concepto

coinciden.

Si el proveedor/banco no aporta identificador universal suficiente:

marcar ambigüedad / requerir resolución,
no afirmar duplicado demostrado.

---

# 9. BANK MATCH

La confirmación bancaria actual crea un cobro.

El nuevo flujo capturado debe ejecutar en UNA transacción:

Financial Operation
→ bank transaction lock
→ invoice lock
→ invoice payment
→ `customer_payment.received`
→ vínculo durable bank → payment
→ `bank_transaction.matched`
→ resultado durable
→ commit.

Debe producir exactamente **dos Economic Events** dentro de la misma operación:

### Slot 1
`customer_payment.received`

representa el cobro real.

### Slot 2
`bank_transaction.matched`

representa la conciliación/evidencia.

Nunca dos efectos de caja.

---

# 10. RELACIONES DEL MATCH

Según el contrato aprobado:

`bank_transaction.matched`

debe tener:

`matches`
→ `customer_payment.received`

y

`evidence_for`
→ `bank_transaction.imported`

Exactamente esas relaciones cuando correspondan.

Por tanto, para una conciliación capturada:

- el movimiento debe disponer de evento `bank_transaction.imported`;
- el cobro debe haberse creado en esa misma operación;
- el match debe enlazar ambos.

Si el movimiento es legacy y no tiene evento de importación:

**fallar cerrado para captura nueva.**

No inventar histórico en ese momento.

---

# 11. CONFIRMED_PAYMENT_ID DURABLE

Actualmente el writer conoce el `payment_id` creado, pero el movimiento no lo conserva durablemente.

Añade el enlace mínimo correcto, por ejemplo:

`bank_transactions.confirmed_payment_id`

o una tabla específica si resulta arquitectónicamente mejor.

Debe tener:

- business_id;
- FK real al invoice_payment;
- concordancia tenant;
- inmutabilidad una vez confirmado;
- exactamente un pago por match actual.

No usar coincidencia posterior por:

importe + fecha.

Después de commit debemos poder demostrar:

movimiento bancario X
→ payment Y.

---

# 12. REPLAY DEL MATCH

Misma operación de conciliación repetida:

→ recuperar mismo resultado;
→ mismo payment_id;
→ mismos dos eventos.

NO:

- crear otro payment;
- volver a confirmar movimiento;
- crear otro match;
- crear otro evento de caja.

Si el movimiento ya está confirmado por otra operación:

→ conflicto explícito o recuperación demostrable según identidad real.

Nunca inferir por proximidad.

---

# 13. ATOMICIDAD

Para cobro manual:

payment
+
invoice status
+
legacy invoice_event
+
Economic Event
+
resultado durable

mismo commit.

Para match bancario:

bank movement
+
payment
+
invoice state
+
durable payment link
+
payment Economic Event
+
match Economic Event
+
resultado

mismo commit.

Fallo en cualquier punto:

ROLLBACK COMPLETO.

---

# 14. COBERTURA DURABLE

Diseña cobertura equivalente a la de factura cuando sea necesaria para demostrar:

invoice_payment
↔ customer_payment.received

y

bank_transaction revision/match
↔ eventos correspondientes.

Evita relaciones circulares frágiles.

Debe garantizar a nivel estructural que un efecto capturado no pueda commit sin su evento obligatorio.

No conviertas esta fase en un framework genérico de coberturas.

---

# 15. BANK IMPORT VS MATCH

Una misma `bank_transaction` puede tener:

revisión inicial
→ `bank_transaction.imported`

y después revisión confirmada
→ `bank_transaction.matched`.

Eso está permitido y debe conservar historia.

No modificar el evento imported.

El match es otro hecho sobre revisión posterior del mismo origen.

Mantener `_financial_revision` y stale detection de Fase 1.4.

---

# 16. CANALES

Como en 1.5:

NO inventar identidad/autorización para web/chat/WhatsApp.

Conectar:

- servicio interno autenticado;
- adaptador explícito si existe frontera correcta.

Los canales completos esperan Fase 1.8.

Legacy puede seguir funcionando con flags apagados.

Si se solicita captura:

NO fallback silencioso.

---

# 17. IMPORT CSV

Revisa `banking.import_csv()`.

No hagas una reescritura bancaria completa.

Pero deja un camino composable para que una importación capturada:

- tenga identidad de batch;
- identidad de fila;
- account scope;
- cree movimiento;
- cree `bank_transaction.imported`;
- sea idempotente.

Un retry del mismo batch/fila:

→ mismo movimiento/evento.

Dos filas legítimas idénticas:

→ dos identidades diferentes.

---

# 18. NO IMPLEMENTAR SUPPLIER PAYMENTS

Aunque haya movimientos negativos:

NO crear:

`supplier_payment.made`

NO marcar una recibida pagada por inferencia.

NO crear AP settlement.

Eso pertenece a fases posteriores.

---

# 19. MIGRACIÓN

Añade únicamente lo necesario para:

- payment coverage;
- bank event coverage;
- durable bank→payment link;
- import identity/batch/row/account scope;
- guards/inmutabilidad.

No crear:

- Open Items;
- GL;
- Journal Entries;
- Tax Ledger;
- Bank Ledger completo;
- supplier payments;
- nueva tesorería;
- históricos;
- activación por cuenta.

---

# 20. TESTS — COBROS

Probar:

- 10 € parcial;
- varios parciales;
- pago completo;
- remaining;
- método/fecha;
- exceso;
- cero/negativo;
- fracción inválida;
- float rechazado en camino exacto.

Idempotencia:

- doble clic;
- timeout después commit;
- dos procesos misma operación;
- dos operaciones legítimas iguales.

Concurrencia:

- dos parciales simultáneos;
- parcial + full;
- dos full;
- nunca sobrecobro.

Comprobar:

exactamente un evento por payment.

---

# 21. TESTS — BANCO IMPORT

- positivo;
- negativo;
- cero si actualmente no está permitido, rechazo explícito;
- misma importación repetida;
- misma fila repetida;
- dos filas idénticas legítimas;
- dos cuentas/extractos distintos;
- fingerprint ambiguo;
- rollback.

Cada movimiento capturado:

exactamente un `bank_transaction.imported`.

---

# 22. TESTS — BANK MATCH

Caso normal:

movimiento positivo
→ factura capturada
→ match
→ payment
→ payment event
→ match event.

Comprobar:

- mismo commit;
- confirmed_payment_id;
- relación settles;
- relation matches;
- relation evidence_for;
- invoice status correcto.

Replay:

cero efectos nuevos.

Concurrencia:

dos procesos intentan confirmar el mismo movimiento.

Solo uno gana.

---

# 23. FALLOS INYECTADOS

Para match, fallar después de:

1. lock movimiento;
2. creación payment;
3. actualización invoice;
4. actualización bank transaction;
5. confirmed_payment_id;
6. payment Economic Event;
7. match Economic Event;
8. resultado durable.

Todo debe revertir.

Para import:

fallar tras insertar movimiento y antes de evento.

No puede quedar movimiento capturado sin evento.

---

# 24. DOBLE RECONOCIMIENTO

Añade tests semánticos/documentación explícita:

`customer_payment.received`
= futuro consumidor de caja/AR/GL.

`bank_transaction.matched`
= Evidence-only.

Un futuro consumidor financiero NO deberá sumar ambos como dos entradas.

No implementes todavía ese consumidor, pero deja el contrato inequívoco.

---

# 25. AUTOAUDITORÍA

Responder antes de cerrar:

1. ¿Puede existir payment capturado sin evento?
2. ¿Puede existir payment event sin payment?
3. ¿Puede un cobro liquidar factura sin evento de factura?
4. ¿Puede un retry duplicar cobro?
5. ¿Puede un full payment cambiar de importe entre aprobación y execute?
6. ¿Puede un match generar doble caja?
7. ¿Puede un match existir sin payment event?
8. ¿Puede un match existir sin imported event?
9. ¿Puede un movimiento apuntar a un payment de otro negocio?
10. ¿Puede una reimportación eliminar una fila legítima idéntica?
11. ¿Se infiere supplier payment de un movimiento negativo?
12. ¿Hay float presentado como exacto?
13. ¿Algún canal inventa autorización?
14. ¿Se ha adelantado Banking 2.0/Open Items/GL?

---

# CIERRE

Devuélveme:

- arquitectura de PaymentCapture/BankCapture;
- eventos producidos;
- slots;
- relaciones;
- cobertura;
- migración;
- identidad de importación;
- durable bank→payment;
- idempotencia;
- exactitud;
- concurrencia;
- rollback;
- pruebas SQLite;
- pruebas PostgreSQL;
- riesgos;
- canales pendientes;
- PASS/FAIL.

No declares 1.6 terminada si un movimiento conciliado puede producir doble efecto de caja o si un payment capturado puede commit sin su Economic Event.

**No avances a 1.7.**