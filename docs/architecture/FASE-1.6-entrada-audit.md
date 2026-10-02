# Auditoría de entradas — exclusivamente 1.6

Base main `56717d4`, esquema 65, árbol limpio y pull ff-only. Diagnóstico y
decisiones registrados en [ADR-010](ADR-010-payment-bank-capture.md) antes de editar
runtime. [Orden explícita](FASE-1.6-orden.md) amplía el plan de referencia de 1.6
a importación bancaria real; no autoriza 1.7.

| Entrada auditada | Actual | Decisión |
|---|---|---|
| invoicing.api_add_invoice_payment | db.add_invoice_payment | Legacy, puente durable pendiente 1.8 |
| invoicing.mark paid | db.mark_invoice_paid | Legacy; captura interna congela saldo revisado |
| tools._marcar_cobrada / chat / WhatsApp | db.mark_invoice_paid | No fabricar Principal/recibo desde pending ni IA |
| demo | db.add_invoice_payment / mark_invoice_paid | Legacy compatible |
| finance import | banking.import_csv → db.add_bank_transaction | Legacy; camino capturado CSV separado y composable |
| finance confirm | db.confirm_bank_transaction | Legacy; captura explícita requiere operación; origen captured protegido |
| payments borrowed writer | pago + status + legacy event | Reutilizar sin nuevo motor; source snapshot y payment_id reales |
| bank borrowed writer | confirmación crea pago pero no retiene ID | Añadir tabla link mínima, sin columna visible en respuesta ni backfill |
| proveedor de pago/banco | no frontera autenticada existente | Solo servicios internos ahora; no adaptador/channels ficticios |

El hash CSV de contenido/ocurrencia existente solo deduplica legacy: no demuestra
identidad universal entre extractos. Cuenta/batch/fila y resolución explícita
permiten conservar dos movimientos legítimos idénticos.

La revisión de emisión de 1.4 no incluye cobros posteriores: parciales necesitan
validar capacidad actual; full requiere fingerprint adicional de liquidación.
Ninguno puede originar su importe desde la respuesta pública float. v1 de los
tres hechos ya contiene campos suficientes; no requiere nueva versión.

Autoridad y TX de Operations 1.2; EE 1.3 y locks/revisiones 1.4; settles a factura
capturada 1.5. Capturas reservan cobertura antes del writer y exigen el evento
al commit. Banco confirmado enlaza su payment concreto, no coincidencia posterior.
Sin GL, Tax, OpenItems, AP settlement, activación ni identidad de canales.
