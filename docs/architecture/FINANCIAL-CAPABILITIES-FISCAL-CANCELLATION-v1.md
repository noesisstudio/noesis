# Fase 1.10C — capacidades y anulación fiscal local v1

Fecha: 2026-10-06. [Orden](FASE-1.10C-orden.md),
[ADR021](ADR-021-capabilities-fiscal-cancellation.md), [cierre](FASE-1.10C-cierre.md).
API interna de servidor; no routing público, activación, handoff ni dispatch.

## Registry único y consumo futuro

`financial_activation.capabilities` reutiliza el Enum `Capability`, `DEPENDENCIES`
y cierre de `Profile` de A. Registry/spec v1 inmutables: capability, dependencias,
comando, productor, disponibilidad de implementación y requisitos adicionales.
No hay otro Enum conceptual. Las quince capacidades son las once financieras de
la tabla y `channel.web_financial`, `channel.whatsapp_financial`,
`provider.aeat_dispatch`, `provider.email_delivery`.

`implemented=True` significa código local disponible: Capture para comandos,
bridges/adaptadores existentes para canales/proveedores. No acredita preflight,
privacidad, exportación, continuidad, autoridad ni activación por generación.
Los cuatro canales/proveedores no tienen un productor de hechos económicos propio;
su campo command/producer es None y requieren preflight y activation_generation.
Las once financieras requieren human_confirmation, privacy, export, continuity
y activation_generation. La anulación añade durable_verified_fiscal_antecedent y
accepted_original_fiscal_record. Ningún requisito declara completada una fase futura.

| CommandType → Capability exacta | Productor local |
|---|---|
| invoice.issue | invoice_capture.InvoiceCapture |
| invoice.rectify | invoice_capture.InvoiceCapture |
| customer_payment.record | payment_capture.PaymentCapture |
| supplier_invoice.confirm | purchasing_capture.SupplierInvoiceCapture |
| supplier_invoice.correct | purchasing_capture.SupplierInvoiceCapture |
| supplier_invoice.void | purchasing_capture.SupplierInvoiceCapture |
| expense.confirm | purchasing_capture.ExpenseCapture |
| expense.void | purchasing_capture.ExpenseCapture |
| bank_transaction.import | bank_capture.BankCapture |
| bank_transaction.match | bank_capture.BankCapture |
| invoice.fiscal_cancel | fiscal_cancellation_capture.FiscalCancellationCapture |

`capability_for_command` rechaza comandos desconocidos; la construcción del mapping
falla si un nuevo CommandType no tiene Capability. `specification` solo admite v1
entera. `dependencies_for` usa el cierre A, incluido invoice.issue → fiscal_cancel/
aeat cuando el contexto fiscal lo exige. `require_command_capability` es únicamente
un predicado puro para D: consumidor y todo su cierre deben ser eligible exactos.
blocked, not_requested, not_applicable o ausencia no conceden una capacidad.
No recibe ni emite recibos de activación; D deberá revalidar grants por tenant,
generación y contexto. Ningún consumidor actual invoca esta policy.

Readiness mantiene hashes/formato/policy v1 y las evaluaciones ya persistidas.
La disponibilidad local de fiscal_cancel quita solamente su bloqueo por productor
ausente; todos los bloqueos por privacidad/export/continuidad/provider siguen
vigentes, así como las dependencias de emisión. No convierte un perfil financiero
en FULL. Una evaluación anterior conserva su cuerpo original (incluido el blocker
de implementación de entonces); un UUID nuevo refleja disponibilidad C. No se
reescribe ni se promociona esa prueba antigua. Las matrices explícitas A/B/history
añaden 76, sin comparaciones `>=`.

## Productor y request cerrado

`FiscalCancellationCapture(business_id)` expone review → prepare → authorize →
execute, usando FinancialOperations, FinancialSession prestada y una sola TX
exterior. Business gate antes de filas/cadena; no conexión ni commit propios.
review recibe Principal, resolución B durable exacta y reason. `verify_resolution`
se ejecuta sobre la misma sesión en review, prepare PREPARED, authorize y nueva
ejecución. B debe ser resolved, fiscal_cancel_invoice, verified_fact y live;
identidad original invoice.issued/rectified v2 exacta, registro/cadena íntegros,
outbox de alta aceptado/aceptado_con_errores y business Veri*Factu habilitado.
Historical, observed_state, mandate, stale, alta pendiente/rechazada o anulación
previa no son aptos. Se reutiliza el verificador fiscal existente.

FinancialRequest: command=invoice.fiscal_cancel; target_id=invoice exacta;
amount=None; currency=EUR; effective_on=día de review/registro; expected_revision=
revisión invoice aprobada en B; reason obligatorio, 5–1000 caracteres sin espacios
exteriores. Parameters contiene EXACTAMENTE:

- antecedent_resolution_uuid, resolution_content_hash, resolution_context_hash;
- invoice_event_uuid, invoice_event_content_hash, invoice_event_record_hash;
- fiscal_record_id, fiscal_record_hash, fiscal_context_hash, configuration_hash.

UUID canónico, hashes hexadecimales de 64 caracteres (hash fiscal conserva el
formato existente en mayúsculas), ID positivo. No payloads duplicados ni importe
libre. fiscal_context_hash vincula fila fiscal/outbox y cadena ordenada; config
vincula configuración de productor, intentos máximos, NIF/modo del negocio.
No persiste valores secretos. Cambio de fuente, outbox, cadena o configuración
obliga a nueva revisión/aprobación. Operación pendiente de otro día se revisa de
nuevo. EntryIdentity es la existente, nunca inferida de texto/importe.

authorize exige human_confirmation durable (también al repetir una operación ya
APPROVED), request_hash/revisión/actor exactos y sesión vigente;
no concede autoridad desde evidencia o IA. Mandatos se rechazan incluso si una
authorization durable existe: B no amplía su proof de mandatos en esta fase.

## Ejecución y evidencia atómicas

Operations valida request/auth y gate; C revalida B y el contexto antes del writer
existente `financial_writers.invoices.create_invoice_cancellation_record`, sin
cambiar cálculos, huella fiscal, XML, QR, numeración, cadena o algoritmos legacy.
Se utiliza su SourceSnapshot real de invoice_cancellation_record (revisión y
fingerprint, nunca 1 inventado). UUIDv5(operation_uuid,
`invoice.fiscal_cancellation.primary.v1`), event_slot=primary.

Una sola TX incorpora cancellation record, outbox pendiente/intentos0, invoice_events
operacional del writer, coverage C, EE/links/sequence y resultado COMMITTED.
Evento existente invoice.fiscal_cancellation_registered v1, EUR, amount=None,
fuente cancellation_record; payload cerrado invoice_id/invoice_number/original_total/
registered_on/reason. original_total procede exclusivamente del amount Decimal
del EE original verificado, JSON string decimal de dos cifras; no total legacy
float ni SUM aproximada. Fecha del registro real, evidence_for exactamente al
invoice.issued/rectified original. original_total no es reversión económica.

Resultado cerrado de 13 campos: invoice_id, cancellation_record_id,
antecedent_resolution_uuid, original_invoice_event_uuid, event_uuid, event_type,
content_hash, source_revision, source_fingerprint, original_total, amount=None,
currency=EUR, captured=True. No afecta saldo, deuda, cobros, banco, recibidas,
gastos, historia, B, readiness/control, flags, GL, reporting o fiscal dispatch.

Misma EntryIdentity/request → misma operación; mismo execute COMMITTED → resultado
original sin nuevo writer, incluso tras pérdida de respuesta. La recuperación no
revalida ausencia de anulación: recupera un efecto ya confirmado, no ejecuta otro.
Otra operación sobre factura ya anulada y una anulación legacy se bloquean;
ninguna adopción ni EE retrospectivo. Authorize ya APPROVED vuelve a comprobar
contexto; retry COMMITTED sigue conservando el resultado original.

## Cobertura y guards de migration76

`invoice_fiscal_cancellation_coverage` es inmutable y tenant-scoped. PK negocio/
invoice; únicos negocio/cancellation_record, operación, evento. Refs compound a
invoice/registro, resolución B con outcome/purpose/quality/origin/event exactos,
original EE tipo/invoice, y FKs diferidas a EE nuevo registro/revisión/tipo/operación
y operación COMMITTED. Campos proof adicionales: resolución hashes y fingerprint
del snapshot; no copia la resolución completa. Índices nuevos, nada retroactivo.

INSERT coverage exige operación APPROVED cancel/live, autoridad humana exacta,
creador/sesión/permisos B/auth, request target/revisión/reason/refs/hashes correctos,
outbox pendiente0 y alta aceptada, sin registro alternativo. INSERT EE live exige
coverage/op/source/revisión/slot/provenance, amount NULL/EUR/v1, payload de cinco
campos con original_total string exacto y link evidence_for original. COMMIT exige
coverage+EE y los trece campos exactos de result, amount literal null, total string
y captured boolean true. UPDATE/DELETE coverage abortan. Guards previos intactos.
La revalidación criptográfica de fuente/cadena/config es del servicio sobre la TX;
los guards SQL añaden protección estructural, no acreditación de un administrador
con poder para desactivar triggers o manipular todas las pruebas.

Downgrade76→75 solo sin evidencia C. Coverage, EE live de anulación o una operación
cancel COMMITTED bloquean pérdida. Sin backfill ni eliminación de outbox. Matrices
compatibles explícitas: readiness74/75/76, antecedents75/76, inventory70–76,
cutoff71–76, import72–76, reconciliation73–76 (tuplas enumeradas en código).

## Límites conservados

Factura histórica v2 unsupported y calidad observed_state siguen bloqueadas.
B bloquea rectificativas negativas para este propósito por PAYMENT_HISTORY_INCOMPLETE;
C conserva ese rechazo sin ampliar B. Rectificativa positiva verificada sí se prueba.
Business fiscal habilitado y día/config/cadena exactos son requisitos conservadores.
No se acredita AEAT real ni negocio activado: status aceptado es fixture sintético
local, nunca nueva attestation o llamada externa. Cinco flags OFF, D no iniciada.
