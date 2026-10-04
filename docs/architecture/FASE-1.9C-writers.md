# Auditoría previa de writers — Fase 1.9C

Realizada sobre main b31e165, 4-oct-2026, **antes de implementar guards o schema71**.
Orden: [1.9C](FASE-1.9C-orden.md). Catálogo de lectura: [fuentes B](FASE-1.9B-fuentes.md).
Inspección AST de todos los execute/execute_exact en src, contraste rg de SQL dinámico,
servicios prestados, fachadas, cascadas, filesystem, scheduler y Capture. Líneas son
las del estado auditado; los nombres de función son la pista estable.

## Conclusión y protocolo previsto

28 kinds B y dos contadores auxiliares deben conservar pertenencia/evidencia.
No se deja una tabla del scope solo con protección de aplicación. SQL INSERT/DELETE
y UPDATE de columnas económicas/evidencia tendrá guard por tenant. También cambio
de business_id/PK. SQL directo PostgreSQL tomará gate con try-lock transaccional
antes de consultar control: conflicto explícito si otro gate está ocupado, para
evitar invertir row-lock→gate y deadlock con writers normales. Application writers
toman gate bloqueante antes de fuentes. SQLite serializa con BEGIN IMMEDIATE.
READ COMMITTED es el protocolo PG; mutación directa con snapshot de aislamiento
superior se rechaza, evitando leer un control anterior a T0. DDL privilegiado,
desactivar triggers o escribir el volumen fuera de APIs no son SQL soportado.

## Scope de corte cerrado v1 (distinto del scope diagnóstico B)

Todas las columnas declaradas en sources.py quedan estables salvo transporte:
verifactu_outbox/cancellation_outbox conservan id/business/invoice_id/record_id/created_at;
status/sent_at/completed_at/updated_at se neutralizan solo en reader modo corte.
invoice_events excluye remision/aceptacion/rechazo; se bloquean nuevos intentos de
remisión, se permite INSERT de auditoría aceptación/rechazo de respuesta ya enviada.
No se reinterpreta ni cambia ningún manifest B. Campos de respuesta/CSV/error/next
attempt/lock fuera del hash C se permiten; attempts incrementado/nuevo sent_at y
claim se bloquean. Dispatch AEAT tendrá gate prestado alrededor de la llamada del
worker: apertura espera llamada ya empezada; llamada posterior falla antes de red.
Sin generar/reenviar fiscalidad. Ningún test llama AEAT.

Invoice.last_reminder_at/reminders_sent no está en hash; recordatorios permitidos.
Supplier email/phone/note, documentos OCR/notas/contexto ajeno y preferencias UI
no alteran proyección: permitidos. Documents INSERT/DELETE/clasificación/relink/
review/content hash y stored_name/filename/mime/size quedan protegidos. Todos los
documentos pertenecen al scope conservador B: alta nueva también cambia membership.
Archivo nuevo huérfano por preprocessing no entra en inventory; nunca reemplazar
bytes de archivo existente. Storage.delete/purge requiere gate con TX durante unlink;
se corrige cascada cliente que actualmente elimina bytes antes de fallo SQL.
Contador document_sequences protege solo invoice/invoice_series:*, quote continúa.
economic_event_sequences protegido íntegro. Business anchor protege baja/cambio id,
no flags/preferencias de negocio (abrir epoch no modifica businesses).

## Entradas/caminos transversales

- web/routers/invoicing, adapters/invoicing, tools/chat/WhatsApp, revisión: fachadas
  db o FinancialChannels→Operations→Capture→boundary.run. No fallback con fence.
- InvoiceCapture, PaymentCapture, BankCapture import/match y Supplier/ExpenseCapture:
  Operations write guard ANTES de operation/coverage, incluso flags OFF. PREPARED/
  APPROVED previos se conservan, execute falla sin transición ni autorización nueva.
- EE.append directo: guard gate ANTES de savepoint/operación/contador. SQL EE/links/
  covers65–67 tiene guard propio, no vía namespace ni flag.
- documentos service.confirm→writers; repo.add/review/classify/delete/purge directo
  también SQL guard. pdf_batch crea documents/classifications. Byte delete usa gate.
- recurrencia legacy/Capture: leer agendas permitido; generar_cycle bloqueado antes
  run/draft/advance; catch no debe insertar run error por rechazo de fence. Otro
  negocio continúa. add/set_status de schedule protegidos.
- aceptación quote crea draft: necesita guard previo a estado quote, sigue siendo
  operacional y NO EE. job.completed sin creación invoice no es fuente económica.
- set_series_next_number / perfiles on-demand / backfill cola / helpers privados:
  guards SQL + entry guards antes de auxiliares. No cambiar instaladores/migrations.
- demo/synthetic SQL: mismas restricciones tenant; ningún permiso especial.
- delete_client_cascade actualmente multiTX+unlink previo: proteger ventana completa
  con gate exterior y guard antes de primer side effect; no retirar conservación.
- delete_business_cascade guard evidencia se amplía a epoch/control/cut/audit.

## DML auditado por función

| Writer / ubicación inicial | Tablas | Tenant | Gate actual | Política prevista |
|---|---|---|---|---|
| `src/noesis/bank_capture/service.py:180` · `_import` | bank_import_coverage | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/bank_capture/service.py:193` · `_import` | bank_import_coverage | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/bank_capture/service.py:209` · `_match` | bank_match_coverage | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/bank_capture/service.py:218` · `_match` | bank_match_coverage | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:10237` · `set_trial` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:10251` · `set_subscription` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:10362` · `apply_stripe_subscription_event` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:10402` · `reconcile_stripe_subscription` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:10415` · `mark_business_as_demo` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:11381` · `update_whatsapp_reports` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:13409` · `admin_update_safe_business_configuration` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:13544` · `admin_update_document_metadata` | documents | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:13979` · `delete_client_cascade` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:14126` · `delete_business_cascade` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:1673` · `update_payment_reminder_settings` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:1719` · `update_fiscal` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:1738` · `update_business_profile` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:1791` · `update_onboarding_preferences` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:1819` · `complete_onboarding_step` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:2975` · `update_panel_layout` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:3008` · `_ensure_current_document_profile` | document_profiles | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:3133` · `update_branding` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:3250` · `create_account` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:3595` · `propose_document_client` | documents | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:3734` · `confirm_document_client_candidate` | documents | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:5245` · `update_clockin_policy` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:534` · `create_business` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:5405` · `update_verifactu_mode` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:5443` · `_ensure_default_invoice_series` | invoice_series | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:5505` · `add_invoice_series` | invoice_series | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:5725` · `update_rectifying_invoice_draft` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:5737` · `update_rectifying_invoice_draft` | invoice_lines | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:5743` · `update_rectifying_invoice_draft` | invoice_lines | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:587` · `rotate_calendar_token` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:5899` · `create_partial_invoice` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:5951` · `complete_invoice_fields` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:5959` · `complete_invoice_fields` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6072` · `update_invoice_draft` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6086` · `update_invoice_draft` | invoice_lines | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6092` · `update_invoice_draft` | invoice_lines | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:615` · `_backfill_phone_norms` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:6230` · `add_recurring_invoice` | recurring_invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6286` · `set_recurring_invoice_status` | recurring_invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6318` · `process_due_recurring_invoices` | recurring_invoice_runs | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6338` · `_next_document_number` | document_sequences | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6371` · `_next_invoice_series_number` | document_sequences | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6433` · `set_series_next_number` | document_sequences | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6474` · `_record_invoice_event` | invoice_events | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6689` · `_create_invoice_record` | invoice_records | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6734` · `_create_invoice_record` | verifactu_outbox | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6814` · `_insert_invoice_payment` | invoice_payments | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6834` · `_set_invoice_payment_state` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6840` · `_set_invoice_payment_state` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:6907` · `delete_invoice` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:7051` · `enqueue_missing_verifactu_records` | verifactu_outbox | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:7087` · `claim_next_verifactu_submission` | verifactu_outbox | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:7128` · `mark_verifactu_retry` | verifactu_outbox | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | permitido solo transporte/recordatorio excluido; SQL directo guardado |
| `src/noesis/db.py:7161` · `mark_verifactu_result` | verifactu_outbox | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | permitido solo transporte/recordatorio excluido; SQL directo guardado |
| `src/noesis/db.py:7201` · `postpone_verifactu_submissions` | verifactu_outbox | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | permitido solo transporte/recordatorio excluido; SQL directo guardado |
| `src/noesis/db.py:7225` · `claim_next_verifactu_cancellation_submission` | verifactu_cancellation_outbox | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:7270` · `mark_verifactu_cancellation_retry` | verifactu_cancellation_outbox | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | permitido solo transporte/recordatorio excluido; SQL directo guardado |
| `src/noesis/db.py:7305` · `mark_verifactu_cancellation_result` | verifactu_cancellation_outbox | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | permitido solo transporte/recordatorio excluido; SQL directo guardado |
| `src/noesis/db.py:7340` · `postpone_verifactu_cancellations` | verifactu_cancellation_outbox | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | permitido solo transporte/recordatorio excluido; SQL directo guardado |
| `src/noesis/db.py:755` · `set_whatsapp_status` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:759` · `set_whatsapp_status` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:769` · `disconnect_whatsapp` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:799` · `start_onboarding` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:862` · `finish_onboarding` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:9047` · `update_language` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:9058` · `update_explanation_level` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:908` · `update_payment_details` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:935` · `update_gestoria_settings` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:966` · `get_or_create_gestoria_token` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:9687` · `accept_quote` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:9699` · `accept_quote` | invoice_lines | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/db.py:975` · `revoke_gestoria_token` | businesses | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | solo id/baja protegido; preferencias/sesión permitidas; SQL directo guardado |
| `src/noesis/db.py:9883` · `mark_reminder_sent` | invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | permitido solo transporte/recordatorio excluido; SQL directo guardado |
| `src/noesis/demo.py:214` · `recibida` | received_invoices | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/documents/repo.py:115` · `set_content_hash` | documents | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/documents/repo.py:173` · `set_context` | documents | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/documents/repo.py:193` · `record_classification` | document_classifications | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/documents/repo.py:273` · `register_pdf_batch` | document_classifications | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/documents/repo.py:347` · `delete` | documents | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/documents/repo.py:369` · `purge_for_client` | documents | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/documents/repo.py:377` · `purge_for_business` | documents | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/documents/repo.py:418` · `_set_review_with_conn` | documents | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/documents/repo.py:445` · `_confirm_classification_with_conn` | document_classifications | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/documents/repo.py:65` · `add` | documents | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/economic_events/repository.py:13` · `lock_business` | economic_event_sequences | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/economic_events/repository.py:24` · `next_sequence` | economic_event_sequences | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/economic_events/repository.py:58` · `insert_link` | economic_event_links | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/economic_events/repository.py:94` · `insert` | economic_events | business_id/id; auxiliares por fila tenant | sin gate previo garantizado | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/bank.py:167` · `_mutate_confirm_bank_transaction` | bank_transactions | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/bank.py:171` · `_mutate_confirm_bank_transaction` | bank_payment_links | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/bank.py:192` · `_mutate_ignore_bank_transaction` | bank_transactions | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/bank.py:45` · `_mutate_add_bank_transaction` | bank_transactions | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/bank.py:91` · `_mutate_suggest_bank_transaction` | bank_transactions | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/invoices.py:110` · `_mutate_add_invoice` | invoice_lines | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/invoices.py:233` · `_mutate_create_rectifying_invoice` | invoices | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/invoices.py:256` · `_mutate_create_rectifying_invoice` | invoice_lines | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/invoices.py:392` · `_mutate_issue_invoice` | invoices | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/invoices.py:422` · `_mutate_issue_invoice` | invoices | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/invoices.py:551` · `_mutate_create_invoice_cancellation_record` | invoice_cancellation_records | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/invoices.py:585` · `_mutate_create_invoice_cancellation_record` | verifactu_cancellation_outbox | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/invoices.py:86` · `_mutate_add_invoice` | invoices | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/purchasing.py:104` · `_mutate_add_received_invoice` | documents | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/purchasing.py:191` · `_mutate_update_received_invoice` | received_invoices | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/purchasing.py:231` · `_mutate_set_received_invoice_status` | received_invoices | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/purchasing.py:254` · `_mutate_delete_received_invoice` | documents | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/purchasing.py:258` · `_mutate_delete_received_invoice` | received_invoices | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/purchasing.py:350` · `_mutate_add_expense` | expenses | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/purchasing.py:355` · `_mutate_add_expense` | documents | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/purchasing.py:384` · `_mutate_delete_expense` | documents | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/purchasing.py:388` · `_mutate_delete_expense` | expenses | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/purchasing.py:83` · `_mutate_add_received_invoice` | received_invoices | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/readers.py:100` · `add_supplier` | suppliers | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/recurring.py:30` · `_mutate_cycle` | recurring_invoice_runs | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/recurring.py:38` · `_mutate_cycle` | recurring_invoice_runs | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/recurring.py:70` · `_mutate_cycle` | recurring_invoice_runs | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/recurring.py:79` · `_mutate_cycle` | recurring_invoice_runs | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/financial_writers/recurring.py:81` · `_mutate_cycle` | recurring_invoices | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/invoice_capture/service.py:170` · `effect` | invoice_economic_coverage | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/payment_capture/service.py:74` · `reserve_payment` | payment_economic_coverage | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
| `src/noesis/payment_capture/service.py:92` · `append_payment` | payment_economic_coverage | business_id/id; auxiliares por fila tenant | boundary.run / Operations.execute | bloqueado si cambia fuente; metadatos ajenos permitidos; SQL directo guardado |
## SQL dinámico y auxiliares revisados manualmente

| Writer | Tablas | Gate actual | Protección prevista |
|---|---|---|---|
| PurchasingCapture._reserve/effect | supplier_invoice_economic_coverage, expense_economic_coverage, received_invoices/expenses logical void | Operations/gate | write guard antes reserva + SQL |
| EventsRepository.insert / lock_business / next_sequence | economic_events/economic_event_sequences | EE.append gate | guard antes contador + SQL |
| db._next_document_number/_next_invoice_number/set_series_next_number | document_sequences | no gate común garantizado en setter | guard temprano + SQL específico kind |
| db.update_branding/_ensure_current_document_profile | businesses,document_profiles | no gate común garantizado | profile SQL; branding que crea profile guard temprano |
| db.complete_invoice_fields/update_*draft | invoices/lines dinámicos | BEGIN IMMEDIATE, sin gate PG común | gate/guard antes SELECT fuente + SQL |
| db.delete_client_cascade/delete_business_cascade | bucles DELETE, documents/profiles/suppliers/invoices/recurring/EE/covers | multiTX cliente / conservación negocio | gate exterior archivo cliente; conservación epoch + SQL |
| repo._set_review_with_conn | documents campos dinámicos | writer documental o fachada | guard SQL de columnas del scope |
| schema64 revision triggers, schema65–67 reservation guards | bank/received/expense revision/covers | TX prestada | nuevos guards no desactivan anteriores; rollback completo |
| migrations/deployment | DDL/control de esquema | maintenance exclusivo sin epoch | schema71 instala última; downgrade con evidencia falla; no parche70/29 |

No quedan fuentes/evidencias del catálogo con SQL directo soportado sin guard.
El mapa debe revalidarse contra tests de cada tabla y mutaciones de claves tenant.
No acredita la implementación ni sustituye el cierre de pruebas.

## Revalidación posterior a implementación

Schema64 inspeccionado: note/void_reason de received, void_reason de expense y
match_score/match_reason de bank también alteran revisión hashed; quedan bloqueados.
PG protege tres acciones en29 tablas reales, más anchor business identity/delete.
Prueba con filas reales de todas las tablas, incluidos EE/links/covers65–67/
records/cancel/outboxes/run/schedule/profile: INSERT, cambio tenant y DELETE
rechazados por HistoricalFenceActive, sin cambio de fuentes. El mapa previo no
se reemplaza por este contraste. Namespace operacional quote sigue fuera de EE.

## Revalidación de orden de permisos

Preflight sin FOR SHARE; gate primero; revalidación bloqueada de usuario/negocio
después. Cutoff, FinancialOperations y append directo siguen este orden. Prueba
PG con processes/pg_locks: el dueño del gate actualiza negocio y revoca usuario
mientras los tres servicios esperan; ninguno conserva lock anterior al gate,
y todos rechazan sesión revocada tras adquirirlo. Revalidación protegida también
serializa revocación posterior. No sustituirla por un check anterior al gate.
