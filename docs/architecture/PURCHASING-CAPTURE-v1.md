# Captura interna de recibidas y gastos v1 — exclusivamente Fase1.7

[Orden humana](FASE-1.7-orden.md), [auditoría previa](FASE-1.7-entrada-audit.md),
[ADR-011](ADR-011-purchasing-capture.md). No1.8 ni activación. Catálogo/payloads
[v1](ECONOMIC-EVENTS-v1.md) y canonicalización intactos.

## Arquitectura y autoridad

`purchasing_capture/` contiene SupplierInvoiceCapture y ExpenseCapture. La pequeña
base interna comparte composición de los dos dominios; no es un dispatcher/bus,
motor contable o framework de soft delete. Infraestructura/pool/conexiones1.2
intactos. Reutiliza purchasing y documents1.4, sin duplicar reglas de mutación.

Principal procede de sesión real de servidor; EntryIdentity identifica intención
durable de canal autenticado. Las factories no autentican. Ningún router, IA,
WhatsApp, OCR, subida, extracción, correo o clasificación provisional llama estos
servicios. Los bridges1.8 pendientes deberán conservar esos datos hasta retry.

Flujo: review → prepare → authorize → execute. Review no crea evidencia económica
ni aprobación. Authorize conserva hash/revisión/actor/sesión/canal1.2. Execute:
permiso/operación/aprobación → gate por negocio → source/documento bloqueados →
continuidad y revisión → reserva si correct/void → writer → snapshot real →
cobertura nueva → EE/relación → resultado1.2 → COMMIT. Creación reserva cobertura
después del INSERT, antes de append; origen nuevo solo observable al mismo commit.
Observaciones de producto después del commit, best-effort. Cero I/O externo dentro.

```python
capture = SupplierInvoiceCapture(business_id)
request = capture.review_confirm(principal, total=Decimal('121.00'),
                                 document_id=document_id, supplier_name='Proveedor')
operation = capture.prepare(principal, EntryIdentity.web_api(request_uuid), request)
capture.authorize(principal, operation.operation_uuid, channel='web_api',
                  approved_hash=request.request_hash,
                  approved_revision=request.expected_revision)
result = capture.execute(principal, operation.operation_uuid)
```

| Servicio | Review | Efecto aprobado |
|---|---|---|
| SupplierInvoiceCapture | review_confirm(total, document_id?, campos) | Alta manual, record sin archivo o confirm documental |
| SupplierInvoiceCapture | review_correct(source_id, reason, cambios) | UPDATE sobre última proyección cubierta, una revisión nueva |
| SupplierInvoiceCapture | review_void(source_id, reason) | Retirada lógica, una revisión nueva |
| ExpenseCapture | review_confirm(amount, concept, document_id?, campos) | Alta manual o ticket con importe explícito aprobado |
| ExpenseCapture | review_void(source_id, reason) | Retirada lógica, una revisión nueva |

Sin método expense.corrected. No hay escritor legacy de corrección de gasto:
una futura corrección deberá void del origen anterior + confirm de otro origen,
dos hechos, sin modificar el gasto histórico. No construir endpoint/flujo ahora.

## Request cerrado

Comandos1.2 existentes supplier_invoice.confirm/correct/void y expense.confirm/void.
EUR, versión1. Target/revisión null para alta; ID/revisión actual para correct/void.
Amount explícito = total confirmado/after.total/before.total respectivamente;
effective_on = día civil fijado por review para confirmar/corregir/retirar. El paso
de medianoche exige revisar de nuevo, sin cambiar request aprobado. Motivo
obligatorio/acotado para correct/void; no valor por defecto ni autorización IA.

Parameters tiene exactamente fields/document_id/document_fingerprint/before/
antecedent/source_fingerprint. Confirm congela todos los campos, documento y
clasificaciones existentes si hay archivo. Correct congela cambios completos,
before real, huella y evento anterior; void congela before y motivo. Inputs extra
rechazados. Igual identidad y distinto contenido: ConflictError. Distintas
identidades admiten documentos legítimos iguales. Replay committed devuelve el
resultado original aun si después hubo correct/void; no consulta revisión actual
para repetir efectos. Aplica contrato estático y permisos vigentes antes de recover.

Recibida: supplier_id o supplier_name/nif explícitos, number/concept,
issued_on/due_on, base/vat_rate/vat_amount/irpf_amount/total/category/note.
Gasto: concept/amount/vat_rate/vat_amount/category/spent_on/project_id.
Monetarios solo Decimal/string final en céntimos; sin float ni redondeo implícito.
Desconocidos explícitos null. ID de documento, proveedor/proyecto y permiso se
comprueban contra filas del mismo negocio. PDF batch no es confirmable.

## Payload final y fechas

Todos usan versión1 y slot estable `purchasing`; UUIDv5(operation_uuid,slot).

| Hecho | Snapshot/payload | Relaciones / amount |
|---|---|---|
| supplier_invoice.confirmed | total, issued_on?, invoice_number?, due_on?, base?, vat_amount?, irpf_amount?, confirmed_on | Sin relación; total |
| supplier_invoice.corrected | before y after del mismo snapshot, corrected_on, reason | corrects último confirmed/corrected; after.total sustitutivo |
| supplier_invoice.voided | before, voided_on, reason | voids último confirmed/corrected; before.total contextual |
| expense.confirmed | total, spent_on?, description, vat_amount?, confirmed_on | Sin relación; total registrado |
| expense.voided | before del snapshot anterior, voided_on, reason | voids confirmed; before.total contextual |

El contrato1.1 describe obligatorios/opcionales y validaciones de suma; no ampliar
campos ni inferir proveedor dentro del v1 cerrado. ID de proveedor/concepto/
categoría/tasa y demás campos relevantes están en la proyección cubierta durable.
Datos de ficha de proveedor no constituyen un freeze fiscal nuevo.

Fechas de emisión/gasto no se sustituyen por confirmación. confirmed/corrected/
voided_on y observed_at son distintos. occurred_at=None para instante original
desconocido; observed_at UTC aware. Void registra timestamp local del servidor y
motivo reales, sin atribuir zona a timestamps legacy. PG spent_on histórico usa
TIMESTAMP: solo fecha civil a medianoche sin zona se proyecta a día; otro valor
ambiguo falla cerrado. Sin accounting_date/períodos/cierre.

## Cobertura, continuidad e integridad

Migración67 crea `supplier_invoice_economic_coverage` y `expense_economic_coverage`:
PK(negocio,source_id,source_revision), operación/evento únicos, tipo, before/after
canónicos, source_fingerprint y antecedent_uuid. Proyección económica contiene
todos los campos de origen relevantes y marcas void. Preserva cuotas desconocidas.
Antes/después no son sumas SQL ni respuestas públicas. Proveedor se conserva por ID.

Nueva reserva transitoria admite after/fingerprint null solamente mientras la TX
está abierta. Adjunción una vez; después UPDATE/DELETE se rechazan. FK diferida a
EE(negocio,UUID,source,revision,tipo,op) y operación committed impide commit de una
reserva parcial. Guard del resultado exige fila/revisión actuales, payload,
importe/fecha/motivo/relación exactos, resultado y exactamente un evento. No se
puede eludir con ejecutor1.2 que omita productor ni con error de append capturado.

Correct/void reserva antes de mutación, con old_revision+1. Guarda before igual a
after de última cobertura, por revisión (no UUID ni fecha). Guards comprueban que
proyección actual coincide con esa cobertura y antecedente del mismo source.
Servicio también verifica huella completa y expected_revision bajo lock. Legacy
drift falla cerrado, queda para diagnóstico/backfill; no reconstrucción silenciosa.

Fuente cubierta no admite UPDATE económico sin reserva aprobada y nuevo evento
inmutable. Campos protegidos recibida: supplier_id/number/concept/issued_on/due_on/
base/vat_rate/vat_amount/irpf_amount/total/category, identidad/alta y void.
Gasto: concept/amount/vat_rate/cuota explícita/category/spent_on/project_id,
identidad/alta y void. DELETE físico siempre rechazado. Guard temporal solo permite
la revisión siguiente; no múltiples mutaciones con una reserva. Fuentes retiradas
no se reactivan ni modifican por legacy. Void solo se ejecuta con reserva válida.

Recibida activa permite status pendiente/pagada y note puramente operativos;
trigger revisiona esos cambios. Revisión stale se rechaza; nueva revisión puede
enlazar último evento de revisión inferior con igual proyección económica. Huecos
por cambios operativos legítimos no reconstruyen historia financiera.
`pagada` no acredita importe/fecha/cuenta/medio/transferencia: ningún pago ni
supplier_payment.made, settlement/AP, remesa o conciliación de proveedor.

## Conservación y lectores

Solo ambos orígenes añaden voided_at/void_reason. Origen, documentos/vínculos y
clasificación confirmada se conservan; guards rechazan unlink/DELETE de documento
capturado y cambio/borrado de clasificación confirmada. No framework general.

| Lectores | Tratamiento |
|---|---|
| db.get/list_received_invoice, list_expenses, expenses_between | Retirados excluidos |
| cash_forecast, _project_select, get_project | Costes/filas de gasto excluidos |
| profit_and_loss, month_billing, expenses_by_category | Excluidos antes de cálculos actuales |
| gestoria_received_in/expenses_in, paquetes, CSV/XLSX, tax_quarter, summary, chat | Heredan filtros de lectores comunes |
| export_business_data operativa/RGPD legacy | Filas operativas excluidas; export completo de evidencia pendiente1.10 |
| repo documental/archivo | Original visible y vínculo conservado, sin sumarlo como coste activo |
| SourceSnapshot, lectura exacta, EE/cobertura y conteos internos de diagnóstico | Evidencia conservada, sin filtro indiscriminado |

La baja destructiva incluye nuevas coberturas en inventario y se bloquea con
evidencia antes de purgar. Retención/exportación/cierre con conservación del núcleo
son gates1.10, no resueltos por esta entrega. Ninguna cuenta/canal activados.

## Exactitud, rollback y límites

Total/componentes históricos siguen REAL/DOUBLE. Snapshot se lee con execute_exact
prestado y conversión explícita desde almacenamiento binario; si tiene subcéntimos
no se ajustan silenciosamente. Payload/proyección deben coincidir con fila escrita
y campos aprobados. Money_provenance/EE provenance declara legacy_binary_storage;
Decimal(str(float)) no recupera precisión histórica. No normalización pública a
float en dominio nuevo. Nueva `_captured_vat_amount` opcional de gasto es NUMERIC
exacto PG/TEXT decimal SQLite, oculta en respuestas legacy y sin cálculo inferido.
No reemplaza tasas ni cambia reporting/fiscalidad legacy.

Contexto Decimal local de precisión50. Desconocido no es cero. No inferir
IVA=total-base, deducibilidad, pago, AP o tax period. Void no es refund/abono/
extinción AP ni asiento inverso. Ningún posting/GL/OpenItems/Tax/reporting nuevo.

Flags OFF; capture_requested y flagCore en fachadas sin contexto fallan cerrados,
sin fallback. No capturados conservan API/cálculos/redondeos/borrado legacy.
Rollback exterior conserva aprobación para retry y revierte fuente/revisión,
proveedor, links/clasificación, cobertura, eventos/relación/contador y resultado.
Bajada67→66 solo sin cobertura/void/cuota explícita; conserva dinero antiguo y
restaura triggers de revisión64. Con evidencia revertir código conservando67,
sin purga ni reset de revisiones. Old code sobre esquema nuevo se valida aparte.

Canales1.8, históricos1.9, activación/retención1.10 esperan otra orden explícita.
No cambios funcionales en VERI*FACTU ni proveedores externos en esta fase.
