# Fase 1.4: mapa previo de escritores

Auditoría previa al cambio de código, 2026-10-02, main 6b4c144.
Las funciones están en `src/noesis/db.py` salvo indicación. `get_conn()` abre,
confirma al salir normalmente, revierte ante excepción y cierra. En PostgreSQL
BEGIN IMMEDIATE se traduce a SELECT 1; las escrituras pertenecen a su transacción.

| Camino / entradas alternativas | Propietario previo / BEGIN | Locks previos | Tablas y efectos | I/O fuera del escritor |
|---|---|---|---|---|
| `issue_invoice`: F1/F2/R1–R5; adaptador interno, tools, router invoicing, demo, recurrentes | get_conn; BEGIN IMMEDIATE; consultas get_invoice antes, durante replay y después en otras conexiones | invoice FOR UPDATE; serie FOR UPDATE y secuencia UPSERT; falta lock común entre series | invoices, document_sequences, invoice_document_profiles; registro y auditoría/outbox debajo | value_ledger tras commit; ningún envío AEAT |
| `_create_invoice_record` desde emisión | conexión prestada, sin BEGIN/commit | hereda invoice/serie; lectura de cadena sin lock común | invoice_records, invoice_events, verifactu_outbox; huella y QR locales, desglose congelado | XML/envío posterior en worker fiscal; ningún I/O aquí |
| `add_invoice` / `create_rectifying_invoice` / borradores | get_conn BEGIN; get_client/get_invoice externos y lectura final externa | original FOR UPDATE en rectificativa; serie por defecto | invoices e invoice_lines; solo borrador | no proveedor; aceptar presupuesto crea borrador operativo, nunca hecho económico |
| `update_invoice_draft`, `update_rectifying_invoice_draft`, `create_partial_invoice` / `complete_invoice_fields`, aceptar presupuesto | get_conn, BEGIN donde hay sustitución de líneas; lecturas previas | invoice/original según función | invoices/invoice_lines; no emisión | canales actuales conservados; históricos importados no se emiten ni entran en cadena |
| `add_invoice_payment` / `mark_invoice_paid`: parcial, completo, manual; tools/router/demo | get_conn BEGIN; mark lee resultado tras commit | invoice FOR UPDATE; SUM legacy de pagos | invoice_payments vía `_insert_invoice_payment`, invoices status, invoice_events | value_ledger posterior; helper de inserción ya prestado |
| `confirm_bank_transaction`: router finance | get_conn BEGIN; lectura final externa | bank FOR UPDATE → invoice FOR UPDATE | invoice_payments, invoices, invoice_events, bank_transactions; descarta payment_id | sin banco externo ni value_ledger de cobro; replay devuelve fila bancaria cruda |
| `add_received_invoice`: router documents, demo, documents.service, revisión PDF/WhatsApp | get_conn; BEGIN si documento; consulta proveedor dentro | documento FOR UPDATE si vínculo | received_invoices y documents | sin I/O externo |
| `update_received_invoice` / `set_received_invoice_status` / `delete_received_invoice` | get_conn; lectura previa y final externas en edición; sin BEGIN explícito | edición sin lock de lectura, susceptible a sobrescribir cambios | received_invoices, documents al borrar; baja física | pagada no constituye supplier_payment; sin I/O |
| documents.service `record_received_invoice` / `confirm_received_invoice` | resolver proveedor, recibida, revisión y clasificación en conexiones independientes | documento bloqueado solo por add_received | suppliers, received_invoices, documents, document_classifications | clasificación observa value_ledger tras commit; lectura/OCR previos no forman parte de confirmación |
| `add_expense`: tools, WhatsApp, router invoicing, service ticket, demo | get_conn; BEGIN con documento; get_project previo externo | documento FOR UPDATE | expenses y documents | sin I/O |
| `delete_expense` | get_conn sin BEGIN explícito | ninguno explícito | desvincula documents y borra expenses físicamente | sin I/O |
| documents.service `convert_ticket_to_expense` | lee documento; crea gasto; revisa y clasifica en varias conexiones | vínculo documental en add_expense | expenses/documents/document_classifications | OCR histórico float; value_ledger clasificación posterior |
| banking.import_csv → `add_bank_transaction`; suggest_pending → `suggest_bank_transaction` | una conexión por fila; suggest lee invoice antes y resultado después | import UNIQUE business/hash; sugerencia sin FOR UPDATE | bank_transactions; importación no produce cobros | CSV local; parser Decimal se convierte a float antes de DB; matching heurístico no autoriza |
| `ignore_bank_transaction` | get_conn, lectura final externa | UPDATE condicional status<>confirmed | bank_transactions | sin I/O |
| `create_invoice_cancellation_record`: router invoicing | get_conn BEGIN | sin lock invoice/cadena común | invoice_cancellation_records, verifactu_cancellation_outbox, invoice_events | SHA local; envío AEAT posterior |
| `process_due_recurring_invoices`: scheduler | lectura, reserva run, add_invoice, issue_invoice, finalización, error: varias transacciones | run UNIQUE; locks de emisión en su transacción independiente | recurring_invoice_runs, recurring_invoices y motor normal de factura | suscripción local; observaciones de emisión posteriores; riesgo de huérfano entre commits |

La búsqueda de INSERT/UPDATE/DELETE de estas tablas en todo `src/noesis` confirma
que las mutaciones financieras de producto anteriores convergen en db/service.
Demo contiene ajustes de estado de recibidas; migraciones contienen semillas y
backfills históricos. No son productores. La revisión debe cubrir también SQL
directo para revisionado, no solo los métodos públicos.

## Fronteras decididas antes de editar

Extraer un núcleo por dominio, reutilizado por la API pública y la API prestada.
El propietario exterior inicia y termina la transacción. Capturar resultado y
filas congeladas dentro de ella; mover únicamente las observaciones de producto
fuera del núcleo. Componer confirmaciones documentales y un vencimiento recurrente
con ese mismo núcleo. No ejecutar OCR, IA, disco, correo ni AEAT desde un writer.

SQLite REAL y PostgreSQL DOUBLE PRECISION son almacenamiento monetario legacy.
Decimal(str(float histórico)) se identifica como procedencia binaria, sin afirmar
recuperación de precisión. Capturar entradas Decimal antes de normalización;
preservar explícitamente los redondeos públicos históricos de recibidas.

Revisionar fuentes mutables con contadores de BD y proteger fuentes congeladas
con una huella de sus campos económicos. Un snapshot de baja se captura antes
de DELETE; 1.7 debe resolver conservación de origen antes de conectar voids.

Serialización transaccional por negocio en PostgreSQL antes de recursos de
dominio, y lock común de cadena por negocio/NIF antes de leerla. La secuencia EE
de 1.3 debe participar en esa misma exclusión para evitar inversión contador/origen.
Sin nueva tabla de locks, enlaces bancarios ni productores. El payment_id creado
se conserva en el resultado interno; su enlace durable corresponde a 1.6.

## Vías de mantenimiento comprobadas, sin productor

- `create_partial_invoice` y `complete_invoice_fields`: chat/local planner; solo
  borradores. get_client/get_invoice previos y lectura final son conexiones
  propias; completar puede usar update_invoice_draft y después limpiar pending
  en otra transacción. No se llaman desde el núcleo prestado de emisión.
- `link_partial_invoices_to_client`: enlace de borrador operativo. `accept_quote`
  (tools, router invoicing, portal) crea borrador en su conexión, no emite ni
  reconoce obligación; no se convierte en Economic Event.
- `delete_invoice` solo borra borradores. Baja/cascada de cliente/negocio respeta
  guards de factura emitida y conservación de evidencia financiera 1.2/1.3.
- record/outbox: `_create_invoice_record` es prestado. Los métodos de cola,
  claim/respuesta/reintento (`enqueue_missing_verifactu_records`, claim/finish y análogos de
  anulación) poseen sus conexiones y actualizan estado de transporte, no crean
  una emisión económica alternativa. Worker envía AEAT fuera de estos writers.
- `mark_reminder_sent` actualiza metadatos de recordatorio, excluidos de la
  huella económica. Ajustes de demo, FK/cleanup de vínculos y SQL de migraciones
  quedan cubiertos por contador conservador cuando cambian fuente mutable.
- No hay productor de factura histórica importada en main actual; la etiqueta
  importada es una exclusión explícita en issue_invoice. No construir uno aquí.

Estos caminos operativos/mantenimiento no se presentan como writers financieros
prestados preparados: mantienen la operativa vigente y no son ejecutores futuros
1.5–1.7. Las veinte fronteras preparadas se detallan en el contrato y cierre.
