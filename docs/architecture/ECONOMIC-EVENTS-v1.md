# Economic Events: contrato v1

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

Contrato entregado en **1.1**, sin alterar su canonicalización en 1.3. Implementación pura en
`src/noesis/economic_events/contracts.py`; sin acceso a datos ni productores.
Catálogo cerrado de once hechos. No hay un sistema genérico de Domain Events.
`quote.accepted`, `job.completed` y `supplier_payment.made` se rechazan.
La capa durable de 1.3 se especifica en [persistencia v1](ECONOMIC-PERSISTENCE-v1.md);
no añade tipos ni conecta productores. 1.4 no autorizada.

## Sobre y autoridad

`EconomicEvent` es una dataclass congelada; su constructor valida también cuando
se llama directamente. Los payloads se copian y congelan recursivamente. Campos:

| Campo | Contrato |
|---|---|
| `event_id` | UUID no nulo aportado por el llamador; sin generación automática |
| `business_id` | BIGINT entero positivo obligatorio, sin bool ni coerción |
| `event_type` | `EventType`, exactamente un miembro del catálogo |
| `source_type` | `SourceType`, compatible con el tipo de hecho |
| `source_id`, `source_revision` | BIGINT enteros positivos obligatorios |
| `occurred_at` | datetime con zona o null explícito si se desconoce el instante |
| `observed_at` | datetime con zona obligatorio; momento de observación, no fecha económica |
| `payload_version` | entero 1; rechazar bool, float y versiones desconocidas |
| `currency` | EUR exclusivamente; default explícito EUR |
| `payload` | mapping cerrado, validado y congelado; detalles abajo |
| `relations` | tupla congelada de relaciones tipadas; default vacía cuando se permite |

`amount` y `economic_date` son propiedades derivadas del payload. No se aceptan
copias independientes que puedan contradecirlo. Las fechas económicas se indican
en el catálogo; no son fechas de contabilización ni asignan período fiscal.
Una fecha desconocida permanece null, sin sustituirla por la de confirmación.
Los timestamps se normalizan a UTC; las fechas civiles usan YYYY-MM-DD.

Validar este sobre **no prueba que el origen exista**, que sea de ese negocio,
que el snapshot coincida con su registro, ni que el humano lo haya autorizado.
Las referencias de relaciones declaran su `business_id` y se rechazan si difiere;
su existencia y pertenencia real exigirán repositorio y claves compuestas futuras.
No se admite `approved_by_ai` ni un estado `posted`. No hay permisos, ejecución,
aprobaciones, identidad de comando ni evidencia de aprobación implementados aquí.
La capa futura deberá añadir la operación y autorización estable sin atribuir
autoridad financiera a la IA; un hash no es una firma ni una aprobación.

## Campos y snapshots

En las tablas: `M` = importe final Decimal/string decimal; `D` = fecha civil ISO;
`T` = string no vacío de hasta 2048 caracteres; `ID` = BIGINT positivo.
`?` indica que el valor puede ser null, independientemente de su obligatoriedad.
Todos los payloads usan **versión 1**. Los campos opcionales ausentes se normalizan
a null. Campos adicionales se rechazan también dentro de snapshots.

| Snapshot | Obligatorios | Opcionales |
|---|---|---|
| Factura emitida (`I`) | `invoice_number:T`, `invoice_kind:T`, `issued_on:D`, `base:M`, `vat_amount:M`, `irpf_amount:M`, `total:M` | `operation_on:D?`, `due_on:D?` |
| Recibida (`S`) | `total:M`, `issued_on:D?` | `invoice_number:T?`, `due_on:D?`, `base:M?`, `vat_amount:M?`, `irpf_amount:M?` |
| Gasto (`E`) | `total:M`, `spent_on:D?`, `description:T` | `vat_amount:M?` |

`I`: F1/F2 para emisión; R1–R5 para rectificación por diferencias. Siempre
`total = base + vat_amount - irpf_amount`, comprobado con Decimal en contexto propio.
Una factura ordinaria permite cero pero no valores negativos; una rectificativa
permite importes firmados y exige `rectification_method:T` con valor `I`.
No se calculan tipos fiscales ni se recalcula el legacy.
La rectificación por sustitución no está soportada por este v1.

`S`: importes declarados no negativos; si se conocen los tres componentes,
comprobar su suma, sin inventar componentes desconocidos. No se deduce IVA
soportado de un total ni se concluye deducibilidad o pago de un estado documental.
`E`: total positivo; IVA declarado, si existe, entre cero y total. No implica pago.

## Catálogo final

Los impactos son posibilidades para reglas futuras, **no instrucciones de posting**.
GL = General Ledger; Tax = Tax Ledger; AR/AP = obligaciones de cliente/proveedor;
Treasury = tesorería; Evidence = evidencia. No hay consumidores de esos metadatos.

| Evento (v1) | Obligatorios | Opcionales | Source type | Amount y fecha económica | Relaciones obligatorias | Impacto futuro |
|---|---|---|---|---|---|---|
| `invoice.issued` | Campos obligatorios I | Opcionales I | `invoice` | `total` exigible >= 0; `issued_on` | Ninguna | GL / Tax / AR / Evidence |
| `invoice.rectified` | Campos obligatorios I + `reason:T`, `rectification_method:T` = `I` | Opcionales I | `invoice` | `total` diferencia firmada; `issued_on` | `rectifies` factura emitida o rectificada | GL / Tax / AR / Evidence |
| `customer_payment.received` | `invoice_id:ID`, `amount:M`, `received_on:D` | `method:T?` | `invoice_payment` | `amount` positivo realmente recibido, parcial/completo; `received_on` | `settles` factura emitida o rectificada | GL / AR / Treasury / Evidence |
| `supplier_invoice.confirmed` | Obligatorios S + `confirmed_on:D` | Opcionales S | `received_invoice` | `total` confirmado >= 0; `issued_on` o null | Ninguna | GL / Tax / AP / Evidence |
| `supplier_invoice.corrected` | `before:S`, `after:S`, `corrected_on:D`, `reason:T` | Opcionales dentro de S | `received_invoice` | `after.total` sustitutivo, no delta; `corrected_on` | `corrects` recibida confirmada o corregida | GL / Tax / AP / Evidence |
| `supplier_invoice.voided` | `before:S`, `voided_on:D`, `reason:T` | Opcionales dentro de S | `received_invoice` | `before.total` contextual >= 0; `voided_on` | `voids` recibida confirmada o corregida | GL / Tax / AP / Evidence |
| `expense.confirmed` | Obligatorios E + `confirmed_on:D` | Opcionales E | `expense` | `total` positivo; `spent_on` o null | Ninguna | GL / Tax / Evidence |
| `expense.voided` | `before:E`, `voided_on:D`, `reason:T` | Opcionales dentro de E | `expense` | `before.total` contextual positivo; `voided_on` | `voids` gasto confirmado | GL / Tax / Evidence |
| `bank_transaction.imported` | `amount:M`, `booked_on:D?`, `imported_on:D` | `value_on:D?`, `bank_reference:T?` | `bank_transaction` | Movimiento firmado no nulo, entrada + / salida -; `booked_on` o null | Ninguna | Treasury / Evidence; sin GL automático |
| `bank_transaction.matched` | `amount:M`, `invoice_payment_id:ID`, `matched_on:D` | Ninguno | `bank_transaction` | Importe positivo conciliado, sin segunda caja; `matched_on` | `matches` cobro + `evidence_for` movimiento importado | Solo Evidence |
| `invoice.fiscal_cancellation_registered` | `invoice_id:ID`, `invoice_number:T`, `original_total:M`, `registered_on:D`, `reason:T` | Ninguno | `invoice_cancellation_record` | **null**; `original_total` contexto firmado; `registered_on` | `evidence_for` factura emitida o rectificada | Solo Evidence |

Cada relación exige `kind`, `target_event_id` UUID no nulo, `target_event_type`
del catálogo y `business_id`. Exactamente una de cada clase indicada, sin clases
adicionales, duplicados, autorrelaciones ni referencias declaradas a otra empresa.
La anulación fiscal registrada no afirma aceptación AEAT, extinción de deuda,
reembolso o reversión contable. La importación bancaria no prueba un cobro nuevo.
La retirada de gasto/recibida preserva un snapshot anterior contextual; no genera
un importe negativo ejecutable. Una rectificativa tendrá un solo hecho primario,
no una emisión ordinaria adicional. Esas reglas no conectan productores en 1.1.

## Dinero y canonicalización

- Decimal de extremo a extremo. Entrada monetaria solo Decimal o string decimal;
  no float, bool, entero JSON, exponentes textuales, coma, NaN ni infinito.
- Límites y contexto monetario de `core/money.py`; hechos finales exactos a 0.01.
  Fracción de céntimo no nula se rechaza; `1.2000` se normaliza a `1.20`.
  Cero firmado se representa `0.00`. No se redondea un snapshot de forma implícita.
- `canonical_payload`: valida, copia y devuelve bytes JSON UTF-8, claves ordenadas,
  separadores compactos, sin escape ASCII obligatorio ni NaN. Importes como strings
  con dos decimales. Conserva texto Unicode/espacios originales; rechaza sustitutos
  Unicode aislados. No aplica normalización NFC ni pretende implementar RFC 8785.
- `payload_hash`: SHA-256 de `{canonical_version:1, event_type, payload_version,
  currency, payload}` en esa representación. Mismo contenido semántico normalizado
  da mismo hash independientemente del orden de campos, Decimal/string u opcionales
  ausentes/null. Cambio de tipo, importe, fecha o texto produce contenido diferente.
- `canonical_bytes` del sobre añade identidad, negocio, origen/revisión, timestamps,
  relaciones ordenadas por tipo/UUID y amount derivado. `content_hash` cubre todo.
  Mismo payload en dos operaciones legítimas conserva `payload_hash`, pero cambia
  `content_hash` si cambia la identidad. Ninguno deduplica ni ejecuta una operación.

Una futura entrada JSON deberá rechazar claves duplicadas antes de construir el
mapping: este contrato recibe mappings de Python y no ofrece un decoder de JSON.
Extender catálogo o versión requiere especificación, pruebas y autorización de
alcance; nunca un fallback que acepte cualquier nombre o `dict` sin esquema.
