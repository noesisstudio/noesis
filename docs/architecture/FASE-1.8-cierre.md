# Cierre de Fase 1.8 — canales financieros

2026-10-02. Base main 63a065a, esquema 67; entrega esquema 68.
**Cierre técnico: 31 PASS / 0 FAIL**. Alcance exclusivo de la [orden humana](FASE-1.8-orden.md).
Cinco flags OFF; sin activar cuentas reales, sin 1.9 ni 1.10.

## Mapa antes/después, bridges e identidad

[Inventario antes de código](FASE-1.8-entrada-audit.md): actor, negocio, sesión,
pending, confirmación, retry y restricciones para cada entrada.

| Canal | Antes | Después con Core ON | EntryIdentity |
|---|---|---|---|
| Web emitir/rectificar | Endpoint/tool legacy | InvoiceCapture, prepare/confirm; borrador no emite | UUID acción y otro UUID confirmación |
| Cobro total/parcial | Endpoint muta saldo/pago | PaymentCapture congela importe/fecha/método | web_api UUID |
| Banco match | Confirma sugerencia legacy | BankCapture revisa movimiento/factura y exige aprobar | web_api UUID |
| Banco CSV | Multipart importa lote | API prepara filas; confirmación individual | batch UUID + row key, cuenta/extracto |
| Recibida/corrección/retirada | db/document service | SupplierInvoiceCapture confirm/correct/void | web_api UUID o reviewed_document |
| Gasto/retirada/documento | Tool/db/docservice | ExpenseCapture confirm/void | web_api UUID o reviewed_document |
| Chat/tools | Pending y dispatch legacy | Tool solo prepara; ActionReview autoriza durablemente | message UUID + slot 1, actor web:uid:sv |
| WhatsApp titular | Wamid sin vínculo financiero exacto | Capture tras citar tarjeta exacta y confirmar | meta + recipient + business + wamid + slot/version |
| OCR/revisión documental | SÍ/TODAS podía registrar | Primer SÍ prepara tarjeta Capture; siguiente SÍ citado autoriza | review UUID + document ID + item + revisión; origen enlazado |
| Recurrente | auto_issue podía emitir | Borrador/run/propuesta, humano confirma ocurrencia | schedule + scheduled_for, por business |
| Adaptadores/fachadas alternativos | Legacy/guards 1.4–1.7 | Sin identidad/Principal/request/aprobación: bloqueados | Contexto de servidor obligatorio |

Flags OFF conserva legacy no capturado; captura explícita nunca cae a legacy.
Fuentes capturadas conservan guards incluso OFF. Solo diez comandos/productores
existentes; catálogo intacto. Fiscal cancellation, supplier payment y Domain Events
no se conectan. Ningún nuevo motor financiero, asiento, TaxLine u OpenItem.

## ActionReview, versiones y autorización

1. Autenticación resuelve Principal, business/sesión/actor; transporte/cliente
   autenticado aporta recibo estable. El LLM solo propone campos, no autoridad/IDs.
2. Capture.review produce FinancialRequest exacto. Operación, preview congelado,
   enlace y acuse `review` comparten preparación/commit. Acuse no autoriza.
3. Preview muestra acción/cliente/proveedor/concepto/importe/impuestos/fecha y
   factura/movimiento pertinentes, sin hashes ni jerga contable para el autónomo.
4. Web confirma op/hash/revisión y decisión con otro UUID. Chat envía la tarjeta
   vista en su pestaña; WhatsApp cita mensaje financiero propio del outbox Meta.
   SÍ aislado/otra tarjeta no confirma pending. NO rechaza sin efecto.
5. Capture.authorize inserta Financial Authorization humana ANTES de callback
   privada: CAS del pending, consumo y recibo `yes` dentro del mismo commit.
   Falla persistencia → rollback, sin auth y con pending recuperable.
6. Capture.execute revalida creador/tenant/sesión/permiso/request/caducidad/fuente/
   recurrencia; writer + cobertura + EE + resultado comparten commit posterior.
7. Meta/PDF/HTTP después del commit. Retry recupera op/result sin interpretar ni
   duplicar. GET es lectura. Otro SÍ citado no consume una propuesta posterior.

Corrección PREPARED → nueva intención/request/hash/aprobación, anterior CANCELLED y
pending sustituido atómicamente. APPROVED no se edita. Otros cambios se revisan en
borrador/formulario/OCR, nunca silenciosamente. Orden nueva cancela PREPARED antes
del DELETE. Locks compartidos: negocio antes de operación/origen/recurrencia/pending.

## Recurrentes y mandatos

No existe mandato adecuado de futuras emisiones y no se inventa. auto_issue es
configuración: Core fuerza borrador, run único y huella antes de avanzar next_run.
Bridge prepara por vencimiento; humano confirma exactamente esa emisión. Crash
recupera runs completos aunque next_run avance. Dos workers no duplican factura.
Cambio/pausa/fecha/importe/sesión/caducidad bloquea antes de auth y execute.
Se exige `active`: última ocurrencia que deja plantilla `ended` también bloqueada.
Runs legacy sin huella, delegación y renovación con drift requieren diseño explícito.

## Migración, privacidad y archivos

Migración 68: `financial_channel_proposals` (op/request, canal/actor hash/sesión,
intención exacta, preview, TTL, origen opaco/contexto recurrente mínimo);
`financial_channel_receipts` (acción/mensaje opaco, op/hash, review/yes/no,
auth si yes, timestamp/hash texto-referencia-cita); huella de plantilla en runs.
FKs compuestas negocio/op/hash y op/auth/hash; triggers inmutables SQLite/PG.
Pending temporal y webhook claim no permiten reconstruir el request aprobado:
los enlaces son imprescindibles. No se copian conversaciones ni OCR completo a
Operations/Authorizations. Baja/downgrade no borra evidencia financiera.

Creados: `financial_channels/` (service/schema/tools/recurring/whatsapp), router
`web/routers/financial_actions.py`, tests SQLite/PG/worker/Node, ADR-012/orden/
inventario/contrato/cierre. Modificados: hooks privados Capture/Operations,
EntryIdentity, migraciones, recurrent writer, fachadas db, tools/ActionReview/chat/
WhatsApp/document review, middleware/router registro/UI/formularios y CI.
No se añade lógica financiera grande a db.py. AGENTS, guías 01/02/03/04/06/07/08,
arquitectura, estado JSON, mapa, decisiones, bitácora/QA/pendientes y contratos
anteriores apuntan a la gobernanza vigente; las órdenes anteriores son históricas.

Decisiones en [ADR-012](ADR-012-financial-channels.md) y
[API/contrato](FINANCIAL-CHANNELS-v1.md). Diferencias frente a legacy: aprobación
humana por vencimiento, CSV por fila y WhatsApp con cita exacta; entradas
insuficientes bloqueadas. Límites permitidos por la orden, sin ampliar alcance.

## Pruebas y gates

La suite general completa precede el último ajuste de transporte de revisión a string/null. Después se repitieron todos los 41 casos del bridge en SQLite/PG, HTTP real de emisión y los 9 checks Node; no cambió el contrato interno ni motores. PostgreSQL local QA restaurado a su estado inicial detenido tras sus pruebas.

| Comprobación | Resultado |
|---|---|
| SQLite `python -m unittest tests.test_financial_channels` | PASS 41/41, 46.288 s, última revalidación con revisión wire |
| PG `... tests.postgres_financial_channels.FinancialChannelsPostgres` | PASS 41/41, 17.300 s, última revalidación con revisión wire |
| PG regresiones Operations/Persistence/Writers/Invoice/PaymentBank/Purchasing | PASS 187/187, 81.712 s |
| PG precisión/contrato monetario `python -m tests.postgres_financial_core` | PASS 6/6, 0.120 s; total PG 234 |
| General `python -m unittest discover -s tests -p test_*.py` | PASS 1617/1617, 1298.519 s |
| Node marketing/calendario/economía/financial_channels | PASS 9/9; revisión mayor que 2^53 preservada |
| Ruff src/tests y Bandit high/high | PASS |
| pip-audit / uv lock --check | PASS; sin vulnerabilidades/cambio de lock; paquete local omitido por PyPI |
| Secretos/verdad documental/enlaces/diff | PASS; 66 enlaces añadidos válidos |
| PG 32→68 con datos y 36 rutas sin 5xx | PASS |
| PG 68→55→54→53→54→55→68; privacidad/conversación/backups | PASS |
| Código base 53 sobre PG68: cliente/factura/emisión/cobro/export | PASS |
| SQLite 0→68→0→68; /health /ready / /login | PASS, HTTP 200 |
| Facturas/costes/cobros/documentos/asistente OFF y ON | PASS, 10 páginas autenticadas 200 y gate renderizado |

Procesos externos sincronizados por READY/stdin, sin memoria compartida: confirmación
y ocurrencia concurrentes; crash antes/tras prepare, tras auth, dentro de writer y
tras commit antes de respuesta, incluyendo identidades WhatsApp entre intérpretes.
También se fuerza una carrera de mismo recibo/distinto contenido: un éxito y un
conflicto, una sola aprobación/efecto. Fixtures en BD/schemas descartables; Principal real,
configuración fiscal explícita. HTTP/middleware y webhook handlers reales; interpretación
y entrega Meta sustituidas. No se prueba proveedor/cuenta real ni se activa el Core.

Generales preliminares: una pasó con 1608 tests; otra dio cinco fallos de workers al
cambiar interfaz de fixtures mientras corría. Se fijó configuración del worker y
se repitió con runtime congelado. Una ejecución intermedia se detuvo para añadir
la comprobación de contenido dentro del commit y su prueba de carrera. Esas
ejecuciones no se usan como evidencia final. Tras la general se cerró la frontera
JSON de revisión a string/null: JavaScript no conserva enteros superiores a 2^53.
Se revalidó el bridge completo SQLite/PG, emisión HTTP real con revisión string y
Node. No se presenta la general como ejecutada después de ese último ajuste acotado.

## PASS/FAIL individual

| Nº | Criterio de la orden | Estado/evidencia |
|---|---|---|
| 1 | Cadena canónica/IA sin autoridad | PASS: finite Capture dispatch, tool solo propone |
| 2 | Auditoría previa | PASS: inventario sobre main limpio |
| 3 | Identidad por canal | PASS: factories/recibos durables |
| 4 | Auth antes de consumir pending | PASS: mismo commit, rollback probado |
| 5 | Corrección/aprobación nueva | PASS: nuevo hash/UUID, anterior CANCELLED |
| 6 | Síntesis humana/exacta | PASS: preview congelado sin hashes humanos |
| 7 | YES/NO/doble YES | PASS: referencia exacta, rechazo/replay, otro pending intacto |
| 8 | Expiración/stale | PASS: Capture + canal + recurrencia antes de auth/execute |
| 9 | Webhook duplicado | PASS: handler y evidencia durable; un efecto |
| 10 | Confirmación repetida | PASS: mismo wamid y otro SÍ citado recuperan resultado |
| 11 | Tools sin writer | PASS: whitelist/ContextVar/args cerrados |
| 12 | Web autenticada/CSRF/UUID | PASS: middleware/dos pasos/GET lectura |
| 13 | Documentos sin autoexecute | PASS: ID/huella/clasificación, revisión y segundo SÍ |
| 14 | CSV sin aprobación implícita | PASS: prepare por fila, upload no autoriza |
| 15 | Identidad recurrente | PASS: schedule/date/run único |
| 16 | Configuración ≠ autoridad | PASS: auto_issue solo borrador |
| 17 | Mandato acotado o humano | PASS: ningún mandato nuevo, humano por ocurrencia |
| 18 | Worker/retry/crash | PASS: procesos reales y factura única |
| 19 | Respuesta tras commit | PASS: result antes de entrega |
| 20 | Fallo de canal | PASS: Meta caído/timeout sin duplicar |
| 21 | Flags/opt-in sin fallback | PASS: cinco OFF, captura falla cerrado |
| 22 | Legacy/guards | PASS: regresiones y código base en esquema 68 |
| 23 | Privacidad mínima | PASS: hashes/metadatos, no conversación completa |
| 24 | Migración mínima | PASS: enlaces necesarios, FKs/guards/downgrade |
| 25 | Tests WhatsApp | PASS: sí/no/corrección/duplicate/stale/actor/sesión/retry |
| 26 | Tests web | PASS: doble submit/UUID conflicto/timeout/CSRF/sesión/tenant |
| 27 | Tests chat/tools | PASS: dinero/identidad modelo rechazados, tarjeta exacta |
| 28 | Tests documentos | PASS: OCR/revisión/corrección/EE único/stale/lote bloqueado |
| 29 | Tests recurrentes | PASS: workers/crash/cambio/pausa/importe-fecha/autoridad |
| 30 | Catálogo intacto | PASS: sin nuevos tipos, fiscal cancellation desconectada |
| 31 | Autoauditoría/cierre | PASS: 14 respuestas + Master Plan §44, suite y gates verdes |

## Autoauditoría de 1.8: 14 respuestas

| Nº / pregunta | Respuesta y control |
|---|---|
| 1 IA ejecuta writer | NO: herramienta/contexto/campos cerrados |
| 2 IA inventa operation_uuid | NO: factory/operación de servidor |
| 3 SÍ aprueba otra propuesta | NO: referencia op/hash/revisión, cita propia, pending CAS |
| 4 Consumo antes de auth | NO: auth precede callback; error revierte y conserva pending |
| 5 Doble webhook duplica | NO: identidad/recibo/op/result durables |
| 6 Timeout tras commit duplica | NO: resultado existente, executor no se repite |
| 7 Canal cambia request aprobado | NO: hash inmutable/nueva aprobación |
| 8 Sesión revocada ejecuta | NO: Principal/sv/permiso/creador/actor |
| 9 OCR se aprueba solo | NO: prepara; preview + humano separado |
| 10 Recurrente sin autoridad emite | NO: borrador incluso auto_issue |
| 11 Dos workers crean dos facturas | NO: run UNIQUE y lock negocio |
| 12 Conversaciones completas | NO: hash/metadatos mínimos |
| 13 Fallback silencioso | NO: Core/opt-in falla cerrado |
| 14 Adelanto históricos/activación/GL/Tax/OpenItems | NO: catálogo/motores intactos y flags OFF |

## Master Plan §44 después

1. EE: diez productores aceptados de 1.5–1.7, catálogo intacto.
2. Asientos: ninguno. 3. Cuentas: ninguna. 4. TaxLines: ninguna.
5. OpenItems/settlements: ninguno nuevo; sin AP nuevo.
6. Dimensiones: business/origen/documento/actor/canal/vencimiento existentes.
7. Permisos: sesión vigente, tenant/creador y aprobación humana exacta; IA/configuración no autoriza.
8. Reversibilidad: PREPARED cancelable/NO; efectos según void/rectificación Capture, evidencia retenida.
9. Idempotencia: identidad/recibos/op/result durables, procesos/retries comprobados.
10. Período cerrado: sin motor de períodos/posting; límites previos conservados, no garantía contable futura.
11. Auditoría: op/request/preview/recibo/auth/revisión/hash/timestamps/cobertura/EE, no archivo completo de chat.
12. Prueba: SQLite/PG, HTTP/CSRF/sesión, webhooks/procesos/crash y gates anteriores.

## Riesgos, bloqueos y rollback

Bloqueados con Core: audio sin identidad de upload/turno; CSV multipart sin cuenta/
batch; PDF batch/TODAS; WhatsApp trabajador/cliente sin titular; tools/adaptadores
sin contexto; runs legacy sin huella; delegación/renovación caducada/drift/plantilla
ended. Ningún mandato para emitir automáticamente. CSV nuevo dispone de API por
fila, sin workflow/UI genérica de lotes. WhatsApp exige citar la tarjeta: si falta
su referencia Meta en outbox, falla cerrado.

Legacy/OCR puede proceder de dinero binario: se muestra y confirma bajo contrato
decimal; no se certifica recuperación de precisión perdida. Exportación/retención
financiera completa espera fase autorizada posterior. Meta/AEAT reales, despliegue
y cuentas reales no están certificados por estas pruebas locales.

Diagnóstico: recibo/op/hash/auth/state/fuente; recuperar con GET o mismo recibo.
No ejecutar manualmente writers ni fabricar nueva identidad. Rollback de código
conserva esquema aditivo/evidencia; downgrade68 se rechaza si hay enlaces. Sin
datos, ciclos downgrade/upgrade probados. Flags OFF; no force-push/borrado de datos.

**Fase 1.9 no iniciada. Activación no autorizada.**
