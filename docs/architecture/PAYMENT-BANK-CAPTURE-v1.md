# Contrato interno — PaymentCapture / BankCapture v1

Alcance: exclusivamente 1.6. [Orden humana](FASE-1.6-orden.md),
[ADR-010](ADR-010-payment-bank-capture.md), [cierre](FASE-1.6-cierre.md).
Payloads aprobados v1 intactos; no ampliación del catálogo ni consumidores.

## Autoridad y API

`Principal(user_id, session_version)` procede del servidor autenticado.
`EntryIdentity` procede de una petición real; sus factories no autentican.
review no autoriza. prepare conserva el request exacto. authorize recibe
channel/hash/revisión expresamente aprobados y crea el recibo durable de 1.2.
execute recibe UUID de esa operación y comprueba permiso/sesión/suscripción,
creador, autorización, contenido y contexto actual bajo locks. No contexto IA.

```python
service = PaymentCapture(business_id)
request = service.review(principal, invoice_id, amount=Decimal("10.00"),
                         method="transferencia", paid_at="2026-10-01T09:12:34")
# O mode="full" / "remaining", sin amount: congela saldo al revisar.
operation = service.prepare(principal, entry_identity_from_server, request)
# Solo tras confirmación humana real:
service.authorize(principal, operation.operation_uuid, channel=entry_identity_from_server.namespace,
                  approved_hash=request.request_hash, approved_revision=request.expected_revision)
result = service.execute(principal, operation.operation_uuid)
```

No endpoint nuevo. Cobros web (`invoicing.py`), tools/chat/WhatsApp y banco web
(`finance.py`) conservan sus llamadas legacy. La demo también. Sus puentes
completos esperan 1.8. No existe proveedor bancario/pagos autenticado actual
al que añadir un puente seguro: los dos servicios son la frontera interna.
El adaptador de emisión de 1.5 sigue vigente. No crear permisos/actores ficticios.
Los cinco flags financieros siguen OFF. `capture_requested` o Core ON sin
contexto rechazan, tanto en fachadas db como import_csv. Sin fallback silencioso.

## Cobro y saldo

PaymentCapture.review admite `partial` con amount positivo explícito y
`full`/`remaining` sin amount. EUR y Decimal/string decimal, máximo 10.000.000,
sin float, booleanos, no finitos ni fracciones de céntimo. Método opcional texto
libre como legacy (50 caracteres), nota opcional (500). paid_at local ISO válido,
resuelto durante review si no se aporta. El origen TIMESTAMP sin zona no representa
un instante UTC: se rechaza entrada con zona, se publica día real, sin inventarla.

Exige factura emitida capturada (issued/rectified v2), misma empresa, creador y
fingerprint de emisión concordante. No backfill de facturas legacy. El contexto
lee filas de pagos bajo el lock de factura, suma Decimal y coteja saldo al céntimo.
No SUM binario. Revisión de emisión y UUID/fingerprint de factura congelados.

Parcial: importe fijo; otros parciales no lo invalidan mientras el origen sea
el mismo y el saldo actual alcance. Permite dos operaciones legítimas iguales.
Full/remaining: además fingerprint de todas las filas de pago, estado, paid_at y
saldo. Cualquier cobro intermedio exige nueva revisión; importe debe ser todo
el pendiente aprobado. Ejecuta `add_invoice_payment` con ese importe, nunca
`mark_invoice_paid` recalculando «lo que quede».

Un productor compartido `append_payment` sirve tanto al cobro manual como al match.
Solo construye v1 desde el snapshot del invoice_payment recién creado por el
writer: invoice_id, amount, paid_at → received_on, método real y revisión/huella.
Importe real debe coincidir con request aprobado; procedencia binaria explícita.

## Importación y CSV

`BankCapture.review_import`: batch_uuid no nulo, row_key estable (1–128),
account_scope opaco (1–128, sin credenciales), SHA-256 del extracto,
booked_on ISO, amount firmado no nulo, descripción/contraparte/referencia acotadas.
`effective_on` es la fecha de contabilización bancaria, no el día de importar.
`imported_on` procede de created_at real. value_on es null porque el writer no conserva la fecha valor; no atribuirla a booked_on.
El importe negativo solo produce evidencia; no pago a proveedor/gasto/AP.

`review_csv(principal, content, batch_uuid=..., account_scope=..., distinct_reasons=...)`
reutiliza el parser existente en modo exacto y devuelve pares identidad/request.
Fila = ordinal de fila no vacía, SHA del archivo vincula su contenido. No muta,
no ejecuta sugerencias ni autoriza automáticamente. Cada fila aprobada se ejecuta
con `BankCapture.execute`. Composable por operación/fila, no promesa de atomicidad
de todo el CSV: una fila inválida/ambigua se revisa explícitamente.

Identidad de operación IMPORT = batch/fila; batch es único por negocio y se
vincula durablemente a cuenta/extracto. Hash legacy de inserción nuevo = SHA de
cuenta/batch/fila, nunca identidad universal por contenido. UNIQUE de cobertura
por negocio/batch/fila y por movimiento/operación/evento.

Dos filas iguales del mismo batch: dos IDs. Otra cuenta: identidad independiente.
Contenido igual entre batches de la misma cuenta: posible duplicidad; no se
descarta ni se declara duplicado demostrado. review exige `distinct_reason`
humano para aprobarlo como movimiento distinto y congela IDs candidatos en
el request autorizado. Si candidatos cambian antes de efecto → stale.
Si era duplicado real, no ejecutar: la decisión de reutilizar/unificar movimientos
no está implementada ni se simula. Un proveedor futuro puede aportar identidad
universal validada sin convertir esta fase en Banking 2.0.

Revisión repetida de una fila ya capturada recupera su request original por
identidad durable y creador; fechas/candidatos posteriores no crean otro request.
Contenido/cuenta/extracto/resolución diferentes → ConflictError. execute committed
recupera resultado, incluso tras timeout o un día después, sin writer/append.

## Match y semántica de caja

review_match exige movimiento positivo sugerido, evento imported válido del mismo
movimiento, factura capturada y saldo suficiente. Congela revisión monotónica de
banco, huella, factura/huella/evento e importación. Cambios de revisión → stale.
Movimiento legacy sin imported falla cerrado. Confirmado por otra operación →
conflicto; nunca buscar pago por importe/fecha ni inferir replay.

execute: operación/autorización → gate negocio → bank lock → invoice lock →
reservas → writer confirm existente (pago, estado invoice, legacy invoice_event,
estado banco, vínculo) → productor común payment → match → resultado → commit.
La tabla `bank_payment_links` conserva exactamente un pago por movimiento y
un movimiento por pago, con FKs reales por negocio y concordancia invoice/importe.
No se modifica ni elimina. También se escribe en futuras confirmaciones legacy;
las anteriores quedan sin vínculo, sin backfill. Respuestas legacy preservadas.

| Hecho | Slot | Relaciones obligatorias | Impacto futuro |
|---|---|---|---|
| customer_payment.received | payment | settles → issued/rectified real | GL / AR / Treasury / Evidence |
| bank_transaction.imported | import | ninguna | Treasury / Evidence, sin GL automático |
| bank_transaction.matched | match | matches → payment de la misma operación; evidence_for → imported del mismo origen | Evidence exclusivamente |

Match produce **dos eventos y un solo pago**. Un consumidor de caja/AR/GL solo
considerará payment como cobro; ni match ni import constituyen otra entrada.
No existe todavía ese consumidor. UUID determinista por UUID operación/slot;
constraints de 1.3 conservan op/slot/origen/revisión. Imported inmutable en
revisión inicial; match es revisión posterior, no reescribe la importación.

## Cobertura, esquema y atomicidad

Migración 66: bank_payment_links, payment_economic_coverage,
bank_import_coverage, bank_match_coverage, índices/FKs/guards. Ningún nuevo
ledger o saldo/moneda, framework genérico, efectos GL/Tax/AR/AP ni históricos.

Reservas específicas antes de writer; IDs recién generados se adjuntan una sola
vez. Durante TX pueden ser null; **no puede persistir una reserva incompleta**:
FK diferida exige operación committed, cuyo guard requiere IDs y eventos/links,
source revision, importes, resultado/hash/UUID/EUR y cardinalidad exacta (1/1/2).
FK diferida exige evento del mismo origen/operación/tipo. FK inmediata de settles
exige cobertura real de factura; match exige imported y cobertura del payment
de su misma operación. Capturar un error no permite commit de la reserva.
Un ejecutor que omita reserva tampoco puede commit esos comandos.

Pagos capturados y coberturas completas son inmutables. Datos originales del
movimiento capturado no se pueden reinterpretar. Estado/link de confirmado
protegidos. Un movimiento con imported capturado no puede confirmar por el
writer legacy sin reserva de match aprobada: falla y revierte el cobro.

Mismo commit: pagos, estado factura, legacy invoice_event, banco/link, EE/links,
secuencia y resultado. Ningún commit interno, pool/ORM nuevo, red/AEAT/IA.
Observaciones value_ledger son postcommit best effort; no autoridad del Core.

Orígenes REAL/DOUBLE siguen con procedencia `legacy_binary_storage`; snapshot
declara huella completa en cobertura y provenance. Entradas/cálculos nuevos son
Decimal; EE PostgreSQL NUMERIC, SQLite TEXT y JSON string. El cursor exacto del
writer adapta solo fechas a formato legacy, sin normalizar Decimal a float al leer.
La adaptación binaria de escritura sigue localizada y explícita como en 1.4.

Downgrade con coberturas/vínculos bloqueado. Baja con evidencia bloqueada antes
de borrar; tablas vacías en inventario. Retención/exportación/cierre con conservación
esperan 1.10 antes de activar canales/cuentas. Rollback operativo: flags OFF,
revertir código compatible conservando esquema/evidencia; no purgar historial.
