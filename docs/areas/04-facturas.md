# 04 · Facturas: del borrador al cobro

> Financial Core: leer [guía 08](08-financial-core.md) y [ADR](../architecture/README.md).
> Nuevos dominios en repositorios especializados con transacción compartida;
> Decimal/NUMERIC y aprobación validada en servidor. La IA carece de autoridad
> financiera directa. Solo fundamentos: no cambia la operativa de esta guía.

> Léela antes de tocar facturas, presupuestos, cobros, series, recurrentes,
> rectificativas, PDF, impuestos o Veri*Factu. Es la zona más sensible del producto:
> un error aquí es un problema fiscal del cliente. Figura 4 del
> [mapa visual](../02-tecnico/Mapa-Bynoesis.html).

## Qué hace

Una factura nace como **borrador**, que se puede cambiar o borrar. Al **emitirla**, en
una sola transacción recibe su número correlativo, congela líneas, datos fiscales y
diseño, y, si el negocio tiene Veri*Factu activo, añade un registro encadenado. Desde
ese momento es inmutable: corregirla es emitir otra (rectificativa). Los cobros se
apuntan en un libro aparte y el estado «pagada» se calcula a partir de él.

## Esquema

```text
Chat/WhatsApp · Pantalla Facturas · Trabajo o proyecto · Recurrente (cada hora, :02)
                                   │
                                   ▼
                 Borrador (db.add_invoice / update_invoice_draft)
                   │   └─ ¿faltan datos? invoice_pending_fields → se pregunta
                   ▼
            Confirmación del titular (SÍ/NO; en WhatsApp, dos veces)
                   ▼
   db.issue_invoice ── BEGIN IMMEDIATE / FOR UPDATE ────────────────────────┐
     número por negocio + serie + año · líneas y datos fiscales congelados  │
     total = base + IVA − IRPF · registro Veri*Factu si verifactu_enabled   │
                   │                                                        ▼
                   ▼                                      cola Veri*Factu → AEAT
     PDF (web/invoice_pdf.build_invoice_pdf)               (apagado sin certificado)
                   │
     entrega: tools.prepare_invoice_delivery → WhatsApp · correo · portal /p/
                   │
     después: cobros (add_invoice_payment) · recordatorio 09:00 ·
              rectificativa R1–R5 · anulación Veri*Factu · paquete de gestoría
```

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `db.py` | `add_invoice`, `update_invoice_draft`, `invoice_pending_fields`, `_invoice_totals`, `issue_invoice`, `add_invoice_payment`, `delete_invoice` (solo borradores), `create_invoice_cancellation_record`, `add_invoice_series`, `tax_quarter` |
| `web/routers/invoicing.py` | API: facturas, series, recurrentes, rectificar, anular Veri*Factu, PDF, pagos, enviar/entregar, presupuestos, gastos, impuestos |
| `tools.py` | Herramientas del cerebro: crear factura, emitir, `prepare_invoice_delivery()` (comprueba que el canal puede enviar antes de encolar) |
| `web/invoice_pdf.py` | PDF de factura, presupuesto y vista previa de marca |
| `verifactu.py` | Huella SHA-256 encadenada, QR y XML de alta y anulación según la AEAT |
| `verifactu_client.py` | Remisión SOAP con certificado (mTLS); sin `VERIFACTU_CERT_PATH` no hace llamadas |
| `adapters/invoicing.py` | Frontera del motor propio. No se delega la facturación en terceros |
| `fiscal_validation.py` | NIF/NIE/CIF y problemas de un borrador |
| `trades.py` | Catálogos por oficio y aviso del 40 % de material en el IVA reducido |
| `web/scheduler.py` | `process_recurring_invoices`, `send_payment_reminders`, `process_verifactu_outbox` |

## Reglas que no se rompen

1. **Una factura emitida no se borra, no se renumera y no se edita.** La base de datos
   lo impide también. Corregir = rectificativa (R1–R5) que conserva la original.
2. **La emisión es atómica e idempotente.** Número, congelado y registro Veri*Factu en
   la misma transacción, con bloqueo de la factura.
3. **La numeración es correlativa por negocio, serie y año.** El titular puede declarar
   el siguiente número de una serie al venir de otro programa, pero **solo hacia
   delante** y queda registrado.
4. **Total = base + IVA − IRPF.** IVA 21, 10, 4 y 0 % (el 0 % es tipo cero, no
   exención); IRPF solo 0, 7 o 15 %. El IVA va por línea y todo redondea con
   `ROUND_HALF_UP` a céntimos. Ver [`Fiscalidad`](../05-legal-y-rgpd/Fiscalidad.md).
5. **Los cobros viven en `invoice_payments`.** «Pagada» y «pendiente» se derivan; un
   cobro bloquea la factura para que dos cobros a la vez no superen el total.
6. **Una factura a medias no se emite.** `issue_invoice` dice qué falta en vez de fallar.
7. **Veri*Factu es append-only.** Una anulación crea otro registro enlazado; nunca se
   corrige la historia.
8. **No se dice «en camino» si no hay forma de enviar.** `prepare_invoice_delivery`
   comprueba el canal y, si no puede, ofrece descargar el PDF.
9. **El IVA reducido y la factura simplificada se avisan, no se imponen.** El producto
   advierte (40 % de material, límite de 400 € de la simplificada) y nunca cambia un
   tipo ni bloquea la emisión por su cuenta.
10. **Las recurrentes crean borradores.** Emitir sola requiere autorización explícita
    del titular.

## Estado real (28-sep-2026)

- Funcionan: borradores, emisión, series, recurrentes, PDF con plantilla, cobros,
  rectificativas, presupuestos por el portal, impuestos del trimestre (303 y 130),
  entrega por WhatsApp y portal.
- Entrega por correo: la salida por Brevo está configurada en Railway, sin validar en
  real. El envío desde el Gmail del autónomo está hecho y pendiente de publicar.
- **Veri*Factu y la remisión a la AEAT están construidos y apagados**: faltan la S.L.,
  el NIF de productor, el certificado y la prueba en el entorno de la AEAT.

## Pruebas que lo cubren

`test_backend` (emisión, inmutabilidad, cobros concurrentes, Veri*Factu),
`test_invoicing_adapter`, `test_invoice_conversation`, `test_local_invoice`,
`test_entrega_factura`, `test_correo_propio`, `test_received_invoices`,
`test_trade_templates`, `test_rollback_pending`, `test_cost_totals`,
`test_xlsx_reports`. En PostgreSQL: `tests/postgres_smoke.py` (CI).

## Al revisar código de esta zona

- [ ] ¿Algo puede modificar o borrar una factura emitida, sus líneas o su registro?
- [ ] ¿Los importes usan `Decimal` con `ROUND_HALF_UP`, IVA por línea, como
      `_invoice_totals`? Nunca `float` para calcular.
- [ ] ¿Un cambio en la numeración mantiene la correlación y solo avanza?
- [ ] ¿La emisión sigue dentro de una transacción con bloqueo en los dos motores?
- [ ] ¿Se sigue pidiendo confirmación antes de emitir, cobrar o enviar?
- [ ] ¿Cambia algo de Veri*Factu? Contrastar con `Fiscalidad.md` y la especificación
      de la AEAT; no tocar sin criterio de asesoría.
- [ ] ¿El texto para el autónomo explica qué falta sin jerga fiscal innecesaria?

## Dudas frecuentes

- **¿Por qué no se puede borrar una factura?** Por ley: una emitida se conserva y se
  corrige con otra. Solo los borradores se borran.
- **¿Las facturas recibidas son de esta zona?** Se registran desde Documentos
  (lectura, borrador y confirmación) y cuentan en los impuestos del trimestre. Su
  entrada se describe en [05 · Correo](05-correo.md) y en
  [`Arquitectura`](../Arquitectura.md).

## Más detalle

[`Fiscalidad`](../05-legal-y-rgpd/Fiscalidad.md) ·
[`Verifactu-textos-archivados`](../05-legal-y-rgpd/Verifactu-textos-archivados.md) ·
[`Arquitectura`](../Arquitectura.md#garantías-del-backend)
