# API canónica de emisión capturada — 1.5

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

```python
capture = InvoiceCapture(business_id)  # negocio de sesión, nunca argumento IA
request = capture.review(principal, invoice_id, payment_term_days=None)
op = capture.prepare(principal, entry_identity, request)
# Solo tras mostrar el contenido y recibir su confirmación humana explícita.
op = capture.authorize(principal, op.operation_uuid, channel=entry_identity.namespace,
    approved_hash=request.request_hash, approved_revision=request.expected_revision)
done = capture.execute(principal, op.operation_uuid)
```

review resuelve datos/defaults reales una vez. Mostrar request para revisión humana;
no llamar authorize automáticamente desde modelo/canal. EntryIdentity debe venir
de recibo estable autenticado y conservarse en retry. Misma entrada/request devuelve
operación; distinto request conflicto. operation_uuid generado por repositorio.
Los canales actuales no producen este contexto todavía: no exponer ejemplo como
tool/endpoint sin el puente autorizado de 1.8. Adaptador issue_captured delega solo
cuando el servidor ya dispone del contexto. Legacy flags False permanece igual.

FinancialOperations.execute posee get_conn/commit y recibe validador de contrato
estático previo al replay; revisión actual completa solo antes de primer efecto.
Callback comparte FinancialSession, reserva cobertura, llama writer normal,
construye payload v2 desde snapshot, valida céntimos, append y retorna resultado.
Result v1: invoice_id, number, event_uuid, event_type, content_hash,
source_fingerprint, amount stringDecimal, currency EUR, captured=True.
Ninguna lectura posterior reconstruye el hecho. Telemetría posterior best-effort.

[ADR completo](ADR-009-invoice-capture.md), [mapa entradas](FASE-1.5-entrada-audit.md).

## Payload v2

Campos v1 intactos y obligatorios conforme ECONOMIC-EVENTS-v1. Campo nuevo requerido
`evidence`: invoice_id/client_id positivos, series{id,code,document_type},
issuer/recipient{name,nif,address}, lines cerradas (id/position/description/kind,
quantity/unit_price/discount_rate/vat_rate/base/vat_amount/total), irpf_rate,
document_profile{id,version,content_hash}, fiscal_record nullable,
source_fingerprint SHA256 y money_provenance=legacy_binary_storage.
Valores nulables son explícitos. Ningún campo extra, float, moneda ajena o tipo
operativo. v2 no disponible para los otros nueve tipos. Líneas 1–256, IDs/posiciones
únicos; quantity>0, descuento0–100, IVA21/10/4/0, IRPF0/7/15.
Bases/cuotas de líneas suman a header; total=base+IVA−IRPF; registro fiscal cuadra.
El documento real siempre prevalece: discrepancia revierte, nunca corregir silencio.
Perfil conserva huella completa sin copiar logo/base64 al request de 64 KiB.

Rectificativa exige original capturado v2 de esa misma factura y rectifies,
conserva el original. Solo por diferencias I; R5 solo F2, demás R solo F1.
Fallo cerrado para originales legacy hasta recuperación histórica 1.9.
Fecha conocida civil congelada, occurred_at=None: timestamp legacy sin zona no
se presenta como instante UTC conocido. observed_at servidorUTC de incorporación.
