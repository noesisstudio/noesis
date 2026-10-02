# Fase 1.8 — inventario previo de entradas

Base main 63a065a, esquema 67, árbol limpio y pull ff-only. La orden humana acepta
1.1–1.7 y autoriza solo 1.8; no 1.9 ni activación. Código leído antes de editar.

| Entrada actual | Identidad/actor/sesión | Propuesta y confirmación / pending | Retry/riesgo | Destino capturado |
|---|---|---|---|---|
| Web invoices/send | Sesión uid/sv, negocio; sin UUID de acción | Botón → run_tool/enviar_factura | Doble submit sin intención durable | InvoiceCapture, dos pasos con UUID estable |
| Web rectify / rectification | Sesión; origen del negocio | Crea/edita borrador R; emisión separada | No es emisión ni EE; preservar borrador | InvoiceCapture al emitir R, no al editar |
| Web invoices/pay y payments | Sesión; sin UUID | Endpoint marca saldo o registra importe | Saldo recalculado, duplicación de parcial | PaymentCapture con saldo/importe congelados |
| Web bank confirm | Sesión; transaction_id | Click → confirm_bank_transaction | Sin aprobación exacta durable | BankCapture.review_match; legacy import bloqueado hasta captura |
| Web bank-import | Sesión + archivo; sin cuenta/batch durable | Upload → import_csv masivo | Upload no demuestra aprobación de filas | Preparar requests por fila y confirmar cada uno; cuenta/batch explícitos |
| Web received invoices, PATCH y DELETE | Sesión; documento/proveedor/origen | Formulario/acción → db/docservice | Dinero binario JSON, DELETE/corrección | SupplierInvoiceCapture confirm/correct/void; motivo explícito |
| Web expense, DELETE y document/to-expense | Sesión; documento/origen | Formulario/ticket → db/docservice | OCR fallback, dinero float | ExpenseCapture confirm/void; campos explícitos revisados |
| Chat web texto | actor web:uid:sv; historial opcional best-effort | action_review reviewed_tool, whatsapp_pending_actions | Turno sin UUID; pending eliminado antes de ejecutar | UUID de mensaje autenticado + slot/version; aprobación antes de consumo |
| Chat web audio | Sesión, archivo sin recibo estable de turno | Transcripción antes de chat | No UUID durable en API actual | Exigir recibo UUID del upload; sin él bloquear captura |
| WhatsApp central titular | Firma/routing/transporte, wamid; teléfono de negocio | reviewed_tool y pendientes emitir/gasto/recibida/doc_review | Webhook claim durable; varios pendientes; retry tras respuesta | Provider/receptor/negocio/wamid + slot; titular real, versión de sesión congelada |
| WhatsApp trabajador/receptor cliente | Worker/contacto, no Principal financiero | Fichajes/consulta/recepción | No autoridad financiera de titular | Bloqueado para mutaciones financieras |
| Tools/agent/local NLU | business servidor, pero no sesión ni recibo en argumentos | action_review.propose o dispatch directo sin contexto | IA podría fabricar argumentos/IDs; llamada fuera de canal | Preparar solo con contexto de servidor; sin contexto fallar cerrado |
| Revisión documental WhatsApp | doc_review, item/index, OCR y correcciones | SÍ o TODAS; payload temporal mutable | No Financial Authorization; batch implícito | Versión concreta con request exacto; OCR solo prepara, TODAS bloqueado para captura |
| Recurrentes scheduler | recurring_id + scheduled_for, runs UNIQUE | auto_issue boolean en configuración | No mandato exacto de 1.2; worker puede emitir legacy | Solo borrador por ocurrencia + confirmación humana; no mandato inventado |
| Adaptador invoicing y db/docservices internos | Contexto capturado explícito o legacy | Fachadas y writers 1.4 | No actor/identidad en llamadas alternativas | Mantener fail-closed con Core ON/capture_requested y guards existentes |
| Cancel-verifactu y supplier status pagada | Sesión + confirmación fiscal / estado operativo | Flujos distintos | No productor autorizado fiscal_cancel ni supplier_payment | Sin conectar; pagada operativa; fiscal cancel capturado bloqueado |

## Decisión previa de bridge

Las operaciones y autorizaciones ya representan request, autoridad y resultado.
Pending es temporal: reemplazo/TTL/borrado destruyen enlace e identidad de un SÍ.
Webhook claim tampoco enlaza la confirmación al request tras pérdida de respuesta.
Se necesitan solo metadatos durables de propuesta/canal y recibo de confirmación:
no duplicar estado financiero, conversación, eventos ni motor de workflow.
Preparación + metadatos compartirán transacción; autorización + recibo + consumo
exacto de pending también. Execute usa exclusivamente Capture. Contexto server-side
no serializable como argumentos del modelo. Hash de contenido detecta conflicto,
no sustituye identidad de intención.

## Master Plan §44 antes de código

1. Solo los diez productores autorizados de 1.5–1.7; catálogo intacto.
2. Ningún asiento. 3. Ninguna cuenta. 4. Ninguna TaxLine.
5. Ningún OpenItem/settlement nuevo. 6. Negocio/origen/documento/canal existentes.
7. Sesión/titular real, permiso y aprobación exacta 1.2; IA sin autoridad.
8. Preparación cancelable; efectos/reversión según Capture, historia retenida.
9. UUID/recibo real + slot, operación y resultado durables; no texto como identidad.
10. Sin motor de períodos/posting ni afirmación de funcionamiento contable en cierre.
11. Enlace mínimo de canal/propuesta/aprobación, hashes/revisión/instantes y resultado.
12. SQLite/PG, HTTP/CSRF/sesión, webhooks, pending/correcciones, procesos, crash y regresiones.
