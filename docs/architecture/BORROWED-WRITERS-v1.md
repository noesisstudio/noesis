# API interna de escritores prestados v1

## Adenda vigente 1.8H

[ADR-013](ADR-013-financial-hardening.md) corrige los defects auditados sin
ampliar funcionalidades: business gate precede operation/source incluso en
prepare/reprepare y lecturas FOR UPDATE; DELETE permitido devuelve OLD en PG,
con reparación de instalaciones existentes; el bridge resuelve procedencia
recurrente con sesión prestada para todos los canales y una identidad económica.
Consulta COMMITTED exige creador/negocio/sesión actual, no sv histórico;
PREPARED/APPROVED y aprobación/ejecución conservan la autoridad original.
Sin reescritura de evidencia. Flags OFF; no 1.9. Las descripciones inferiores
con orden anterior de locks se conservan como contexto histórico, supersedido
por esta adenda y su [validación](FASE-1.8H-cierre.md).

## Conexión vigente de Fase 1.8

Los contratos de esta entrega permanecen vigentes. Los cinco Capture se invocan
ahora desde bridges autenticados, detrás del gate apagado del Core. La autoridad
sigue en FinancialOperations; la IA prepara, nunca aprueba. No cambian catálogo,
payloads, fiscalidad ni writers. [ADR-012](ADR-012-financial-channels.md) y
[contrato de canales](FINANCIAL-CHANNELS-v1.md). Los límites de no conexión en el
cierre original describen aquella entrega histórica, no esta fase autorizada.


Nota vigente1.7: cinco productores de recibidas/gastos v1 con cobertura por
revisión, continuidad, void lógico y guards. Catálogo/canonicalización intactos.
[ADR-011](ADR-011-purchasing-capture.md), [API](PURCHASING-CAPTURE-v1.md).
Flags OFF, no1.8. Las notas inferiores reflejan entregas anteriores.

Nota vigente 1.6: se añaden PaymentCapture/BankCapture sobre el writer existente,
con autorización durable, cobertura específica y resultado en un commit.
customer_payment.received v1 = cobro real; bank_transaction.imported v1 = evidencia;
bank_transaction.matched v1 = Evidence-only, nunca segunda caja. No cambia
canonicalización ni catálogo. [ADR-010](ADR-010-payment-bank-capture.md) y
[API](PAYMENT-BANK-CAPTURE-v1.md). Cursor exacto del writer conserva Decimal;
link bank→payment durable. Canales1.8 pendientes, flags OFF; no avanzar1.7.
Las notas inferiores describen el alcance histórico de cada entrega.

Nota de continuidad 1.5: primer productor real de emisión/rectificativa autorizado.
v1 conserva bytes/hash. Solo estos dos hechos incorporan payloadv2 y cobertura65.
Leer [ADR-009](ADR-009-invoice-capture.md) y [API](INVOICE-CAPTURE-v1.md).
El resto de límites de las entregas anteriores se interpreta históricamente.

Leer [ADR-008](ADR-008-borrowed-writers.md) y [mapa previo](FASE-1.4-writers-audit.md).
No conectar estos writers a Economic Events sin autorización de otra unidad.

```python
with db.get_conn() as conn:
    conn.execute("BEGIN IMMEDIATE")
    result = payments.add_invoice_payment(
        FinancialSession(conn), invoice_id, Decimal("10.00"),
        business_id=business_id, expected_revision=invoice_revision,
    )
    # Solo tests de 1.4 añaden una escritura sintética aquí.
    # En una unidad futura autorizada: evento y resultado durable en esta conexión.
# El propietario exterior puede ejecutar observe(result) después del commit.
```

Con operaciones de 1.2 usar su `execute(principal, operation_uuid, executor,
revision_reader=...)`: valida request/aprobación/revisión y toma lock de operación
antes del writer. El ejecutor recibe FinancialSession y request aprobado; devuelve
mapping canónico para el resultado durable. No abrir get_conn dentro del ejecutor.
El reader de 1.2 recibe (session, request); adaptar explícitamente el reader de
origen de 1.4, que recibe (session, SourceType, source_id), sin inferir tipo de IA.

Una excepción debe propagarse fuera del contexto propietario para rollback.
Capturarla y continuar hasta commit es decisión del propietario y puede confirmar
efectos: el writer no crea savepoints ni revierte la transacción de quien llama.
No llamar directamente `_mutate_*`: son el núcleo local, no el punto con locks,
validación de revisión y snapshot. La API pública del paquete exige transacción
activa en ambos motores. No usar autocommit/REPEATABLE READ.

| Módulo | Fronteras |
|---|---|
| invoices | add_invoice, create_rectifying_invoice, issue_invoice, create_invoice_cancellation_record |
| payments | add_invoice_payment, mark_invoice_paid; mismo `_insert_invoice_payment` para banco |
| purchasing | add/update/set_status/delete received_invoice; add/delete expense |
| bank | add/suggest/confirm/ignore bank_transaction |
| documents | record_received_invoice, confirm_received_invoice, convert_ticket_to_expense |
| recurring | generate_cycle(recurring_id, business_id, scheduled_for): identidad estable del vencimiento, motor normal |

Todos devuelven `WriterResult` congelado: legacy inmutable, snapshots, exact_inputs,
input_provenance, prepared_values, payment_id y observaciones diferidas.
`legacy_value()` recrea dict/list/float público. No devolver ese mapping a un
contrato del Financial Core: usar amounts Decimal y campos del snapshot con
procedencia explícita, proyectados por el productor futuro autorizado.

`SourceSnapshot`: business_id, source_type, source_id, revision, fingerprint,
amounts, data, money_provenance y deleted. Invoice incluye líneas, registro fiscal
y perfil congelado; gasto/recibida incluyen documento y clasificación; cobro/banco
incluyen snapshot del pago creado y padre. Capturados en la misma transacción.
No hay evento, autorización nueva ni posting implícitos en estos objetos.

legacy=True se reserva para la fachada compatible: admite los valores float
existentes y redondeos históricos. La API exacta por defecto rechaza float,
moneda desconocida y Decimal inválido o importe positivo que cierre a cero. `prepared_values` permite inspeccionar los
Decimal antes de la adaptación localizada a REAL/DOUBLE; `amounts` describe el
efecto almacenado con etiqueta binaria. No cambiar esa procedencia por «exacto».

Flags permanecen apagados. Banco no guarda enlace durable de pago todavía; una
confirmación repetida no puede recuperarlo. Una baja física tiene snapshot previo
pero no origen válido para incorporar un evento posterior al DELETE. Pendientes
respectivamente de 1.6 y 1.7, sin implementación en esta unidad.
