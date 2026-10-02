# ADR-012 — Identidad, propuesta y aprobación de canales financieros

Estado: adoptado dentro de Fase 1.8; no autoriza activación ni Fase 1.9.

## Problema

Los endpoints y herramientas legacy no conservan un recibo de intención estable.
ActionReview y WhatsApp podían consumir pending antes de ejecutar; un webhook o
respuesta perdida podía reinterpretarse. `auto_issue` es configuración operativa,
no un mandato de FinancialOperations que cubra requests futuros exactos.

## Decisión

`financial_channels/` es un adaptador de canal cerrado hacia InvoiceCapture,
PaymentCapture, BankCapture, SupplierInvoiceCapture y ExpenseCapture. La autoridad
permanece en operaciones/autorizaciones existentes, sin nuevo workflow engine.
Los canales producen Principal/EntryIdentity desde autenticación y recibos reales;
ningún argumento de tool elige identidad, aprobación ni ejecutor.

Preparación del Capture y enlace de propuesta comparten transacción. Una callback
privada de servidor se ejecuta después de insertar/ligar la autorización y antes
del commit: verifica la versión actual, consume pending y guarda el recibo. Si
falla cualquiera, rollback conserva pending y no deja autorización. Execute usa
otra transacción del Capture, revalidando fuente, sesión y contexto. Un fallo
posterior recupera el mismo UUID/resultado; entrega externa ocurre después.

Corrección cancela la propuesta PREPARED y prepara otro request/identidad en la
misma transacción que sustituye el pending; ninguna aprobación cambia contenido.
Una propuesta APPROVED no puede corregirse. El hash congela contenido, nunca se
usa como sustituto de la identidad de intención.

## Persistencia mínima

Migración 68: `financial_channel_proposals` y `financial_channel_receipts`, FKs
compuestas por negocio/op/request y op/autorización/hash, inmutabilidad SQL.
Se justifican porque pending puede borrarse y webhook solo conserva estado de
transporte; ninguno permite reconstruir qué propuesta confirmó aquel mensaje.
Un recibo `review` reconoce únicamente la preparación/recuperación del request;
liga también UUIDs web a operaciones recurrentes preexistentes y nunca autoriza.
Confirmación usa otro recibo `yes`/`no`; reutilizar UUID para otra finalidad falla.
Chat liga SÍ/NO/corrección a la tarjeta que mostró cada pestaña (op/hash/revisión).
WhatsApp exige citar el mensaje financiero del outbox propio por Meta ID, negocio
y teléfono. Una referencia distinta no consume pending. Otro SÍ citado recupera
el mismo resultado sin consumir otra propuesta. El recibo hash-ea texto/referencia/
cita, sin guardar conversación. Locks: negocio → operación → origen/pending.
Una orden nueva cancela PREPARED durablemente antes de quitar su pending.
La revisión de origen viaja como string decimal/null, para no perder enteros de
más de 53 bits en JavaScript; se valida como entero antes de comparar/autorizar.
El contrato interno de FinancialRequest y su hash no cambia.
No se copian conversaciones: hash del actor/mensaje, identidad opaca del recibo,
request/intent exacto, síntesis mostrada, versión de sesión y timestamps.
`recurring_invoice_runs.financial_template_hash` conserva el contexto de la
configuración antes de avanzar el vencimiento, incluso si el proceso cae.
Downgrade con enlaces no vacíos se rechaza; rollback de código conserva evidencia.

## Recurrentes y entradas insuficientes

No existe un mandato adecuado de futuras emisiones. Con Core activo el writer
recurrente impone borrador aunque `auto_issue` sea true. El run único genera una
sola factura y conserva huella; el bridge prepara por schedule/fecha y el humano
autoriza esa emisión exacta. Cambio/pausa bloquea antes de autorizar/ejecutar.
No se renueva una propuesta caducada ni se reinterpreta un run antiguo sin huella.
Una plantilla `ended`, incluso tras generar su último vencimiento, queda bloqueada
por exigir `active`; no se infiere mandato ni se reabre automáticamente.

CSV antiguo sin cuenta/batch, audio sin UUID, lotes documentales y productores
sin contexto autenticado quedan bloqueados en Core. La API CSV prepara filas;
cada confirmación queda ligada a su request. No se introduce mandato, aprobación
de lote, backfill, GL, Tax, Open Items, reporting ni nuevos eventos.

## Consecuencias

Flags OFF conserva legacy no capturado; una captura explícita falla cerrado.
Los guards de fuentes capturadas siguen vigentes incluso OFF. Autorización por
creador/sesión limita delegación; no se amplía RBAC. Caducidad y drift requieren
revisión humana, con bloqueos conservadores en recurrencias/documentos. La
evidencia financiera se conserva; exportación/retención completa espera su fase.

[Orden humana](FASE-1.8-orden.md), [inventario previo](FASE-1.8-entrada-audit.md),
[API](FINANCIAL-CHANNELS-v1.md), [cierre](FASE-1.8-cierre.md).
