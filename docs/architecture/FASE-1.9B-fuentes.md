# Mapa previo de evidencia — 1.9B

Inspección del main real, schema69, 3-oct-2026. Solo datos sintéticos durante
esta entrega. La orden humana vigente es [1.9B](FASE-1.9B-orden.md).

| Tabla real | Clave tenant + paginación | Evidencia mínima | Papel |
|---|---|---|---|
| businesses (scope_anchor) | id del negocio explícito | únicamente id | ancla diagnóstica para incidencias de conjunto vacío; no hecho económico |
| invoices | business_id,id | number,type,status,rectifies_invoice_id,fechas,series_id,document_profile_id,currency; base/vat/irpf/total y tipos crudos | emisión/rectificación; draft fuera de alcance |
| invoice_lines | business_id,id | invoice_id,position,kind; quantity/unit_price/discount_rate/vat_rate/base/vat_amount/total crudos | líneas; descripción solo hash |
| invoice_series | business_id,id | code,document_type,created_at | procedencia; asignación retrospectiva no prueba serie original |
| document_profiles | business_id,id | version,created_at,template/color; hashes de contenido de marca | perfil congelado; sin imágenes/footer completos |
| invoice_records | business_id,id | invoice_id,number/type,fechas,record_hash,previous_hash,parent,breakdown_json mínimo; vat_total/invoice_total crudos | fiscal; no remisión |
| invoice_events | business_id,id | invoice_id,record_id,event_type,created_at | auxiliar; no productor |
| verifactu_outbox | business_id,id | invoice_id,record_id,status,fechas | solo transporte; sin respuestas/XML |
| invoice_payments | business_id,id | invoice_id,method,paid_at,created_at; amount crudo | cobro real; registro_anterior sintético |
| bank_transactions | business_id,id | import_hash,booked_on,currency,status,suggested_invoice_id,confirmed_at,created_at,_financial_revision; amount crudo | import y posible match separados |
| bank_payment_links | business_id,bank_transaction_id | payment_id | vínculo real; sugerencia no equivale a match |
| received_invoices | business_id,id | supplier_id,number,fechas,status,revision,voided_at; base/vat/irpf/total/vat_rate crudos | estado observado; pagada no es pago |
| suppliers | business_id,id | hash de NIF/nombre,created_at | referencia mínima; sin contactos/notas |
| expenses | business_id,id | spent_on,category,revision,voided_at; amount/vat_rate/_captured_vat_amount crudos | estado observado; IVA desconocido conservado |
| documents | business_id,id | invoice_id/expense_id/received_invoice_id,kind,doc_status,content_sha256,reviewed_at | referencia; sin archivo/OCR/notas |
| document_classifications | business_id,id | document_id,detected_kind,confirmed_kind,method,confirmed_at | clasificación; no autoridad financiera |
| invoice_cancellation_records | business_id,id | invoice_id,original_record_id,number,issue_date,generated_at,record_hash,previous_hash,reason | evidencia fiscal; sin nueva anulación |
| verifactu_cancellation_outbox | business_id,id | invoice_id,record_id,status,fechas | transporte auxiliar |
| recurring_invoice_runs | business_id,id | recurring_id,invoice_id,scheduled_for,status,financial_template_hash | procedencia; no mandato |
| recurring_invoices | business_id,id | client_id,cadence,status,next_run_on,series_id,created_at,updated_at,hash de lines_json | auxiliar; auto_issue no autoriza |
| economic_events | business_id,id | sobre/payload existentes,UUID/source/revision/tipo,hashes y metadatos de registro | verificación de cobertura, lectura exclusivamente |
| economic_event_links | business_id,event_uuid,relation_type,target_event_uuid | relaciones explícitas | coherencia de cobertura |
| invoice_economic_coverage | business_id,invoice_id | event_uuid,type,operation_uuid,state | cobertura emisión |
| payment_economic_coverage | business_id,operation_uuid | invoice_id,event/payment IDs,source_fingerprint,state | cobertura cobro |
| bank_import_coverage | business_id,operation_uuid | source/revision/event,account_scope,batch_uuid,row_key,statement_hash,content/source fingerprints,state | única identidad durable de import disponible |
| bank_match_coverage | business_id,bank_transaction_id | payment/import/event IDs,source_revision,state | cobertura match |
| supplier_invoice_economic_coverage / expense_economic_coverage | business_id,source_id,source_revision | event/type,antes/después,source_fingerprint,antecedent_uuid,state | continuidad por revisión |

Los nombres supplier_invoices, invoice_document_profiles y bank_*_economic_coverage
no existen en este esquema. No se inventan tablas, cuenta, batch ni fila bancaria.

## Migraciones y límites probatorios

11 creó pagos `registro_anterior` desde status cobrada: no acredita cobro original.
33 asignó series e insertó líneas donde faltaban: no dejó marcador por fila.
42/48 asignaron perfiles iniciales a emitidas: version1 no demuestra diseño original.
64 inicializó revisiones a1: no acredita alta ni cadena anterior. 65–67 conservan
coberturas live; permiten verificar hechos existentes, nunca recrear historia borrada.
Un patrón compatible con migración solo permite advertir/UNKNOWN, no afirmar
procedencia sintética sin marcador. La revisión actual no reconstruye anteriores.

REAL/DOUBLE se extrae desde execute_exact de la conexión prestada, con typeof/
pg_typeof, texto SQL, bits y Decimal.from_float exclusivamente diagnóstico. TEXT/
NUMERIC conserva exactitud. Nunca usar normalización legacy ni snapshot financiero
como única evidencia. El redondeo diagnóstico no valida dinero ni crea candidatos.
Un registro fiscal binario tampoco corrobora un decimal original por sí solo.

Los lectores usan catálogo cerrado de columnas, keyset y business_id obligatorio.
Todos los auxiliares forman parte del conjunto de evidencia y su hash; cambios de
pertenencia, referencias o contenido invalidan la comparación diagnóstica. No hay
T0, epoch, fence, locks de fuentes ni certificado de ausencia de concurrencia.

## Concreción de proyecciones al implementar

Los 28 kinds del catálogo incluyen el ancla y las coberturas separadas de recibidas
y gastos. `document_profiles` añade `profile_snapshot_hash`: la huella se calcula
sobre el snapshot existente en memoria, pero no se persisten imágenes/footer.
`invoice_records` y cancelaciones añaden `fiscal_hash_valid` mediante contraste
de la huella existente; no generan registros ni documentos fiscales. Los EE y
before/after de cobertura conservan proyecciones mínimas tipadas y hashes del
contenido almacenado, sin copiar payloads con notas/PII completos. Los nombres de
campo físicos y derivados definitivos están cerrados por `sources.py`/`readers.py`.
