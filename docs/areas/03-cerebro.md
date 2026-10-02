# 03 · Cerebro: el chat y WhatsApp

## Confirmación documental componible (1.4)

`documents.service` conserva APIs/canales; sus confirmaciones delegan en writers
prestados. Proveedor, recibida/gasto, vínculo y revisión/clasificación comparten
transacción; observaciones de producto después del commit. OCR/IA/archivo quedan
fuera del writer. `repo._*_with_conn` comparte consultas/mutación existentes.
No conectar FinancialOperations ni Economic Events al chat/WhatsApp aquí.

## Puerta financiera futura tras 1.2

`action_review.respond()` conserva su funcionamiento: elimina pending antes de
llamar run_tool fuera de la transacción. Esa fila temporal no es autorización
financiera durable. No se conecta FinancialOperations a este camino en 1.2.
Antes de su futura integración, leer [protocolo](../architecture/FINANCIAL-OPERATIONS-v1.md):
identidad estable de canal autenticado, request fijo, recibo durable de aprobación
antes de consumir pending y ejecución con la misma conexión prestada.
No interpretar de nuevo un sí ni aceptar claves/actores de argumentos IA.
Los tests prueban que un recibo independiente sobrevive al borrar una propuesta;
no afirman que los canales legacy ya utilicen esa garantía.

> Financial Core: leer [guía 08](08-financial-core.md) y [ADR](../architecture/README.md).
> Nuevos dominios en repositorios especializados con transacción compartida;
> Decimal/NUMERIC y aprobación validada en servidor. La IA carece de autoridad
> financiera directa. Solo fundamentos: no cambia la operativa de esta guía.

> Léela antes de tocar `web/chat.py`, `nlu.py`, `agent.py`, `tools.py`,
> `action_review.py`, `internal_brain.py`, `learning.py`, `local_invoice.py`,
> `web/whatsapp*.py` o la voz. Figura 3 del [mapa visual](../02-tecnico/Mapa-Bynoesis.html).

## Qué hace

Recibe un mensaje (chat web o WhatsApp, en texto, voz o archivo), averigua quién
escribe y lo intenta resolver subiendo por una escalera: primero reglas locales, que
no cuestan nada ni sacan datos del servidor, y solo si no bastan, una IA. Lo que se
entiende se convierte en una **herramienta**. Si la herramienta mueve dinero o envía
algo, no se ejecuta: se devuelve una **propuesta** y se espera el «sí» del titular.

## Esquema

```text
WhatsApp: /webhook/whatsapp ── firma de Meta ── sin duplicados ── whatsapp.handle_inbound
Web:      POST /api/{id}/chat ───────────────────────────────────────────────┐
  nota de voz → adapters/transcription.py (Groq o Whisper privado) → texto ┤
  foto o PDF  → whatsapp_documents.ingest → documento en revisión ─────────┼─► propuesta
                                                                            ▼
chat.handle() → _handle_turn()
   1. guarda el mensaje y decide el actor («wa:<tel>» o «web:<id>»)
   2. ¿es un «sí/no» a una propuesta pendiente? → action_review.respond()
   3. _handle(): escalera
        a. local_invoice.parse()         planificador local de facturas (interruptor)
        b. nlu.safety_refusal()          lo que nunca se hace
        c. internal_brain.prepare_response()  borradores de mensajes con datos reales
        d. nlu.parse() → run_tool()      reglas locales
        e. IA privada (adapters/ai.local_chat)          si está configurada
        f. IA externa compatible → Claude (agent.py)    solo con permiso y crédito
        g. respuesta honesta de que no se ha entendido
   4. tools.run_tool(): plan contratado → action_review.propose() → ejecuta
   5. respuesta: cola de WhatsApp o JSON a la web
```

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `web/chat.py` | `handle()` es la entrada única de web y WhatsApp; `_handle()` es la escalera; `handle_read_only()` sirve las demos y el WhatsApp de las cuentas en modo consulta (con `activation_url`) |
| `nlu.py` | Reglas locales: `parse()`, `parse_date()`, importes, IVA/IRPF, nombres; `format_reply()` redacta el resultado |
| `tools.py` | `TOOLS` (lo que el cerebro puede hacer), `run_tool()`, permisos por plan (`_TOOL_ENTITLEMENTS`) y recibos de ejecución |
| `action_review.py` | `propose()` convierte una acción sensible en propuesta; `respond()` atiende el «sí/no» |
| `internal_brain.py` | Redacta avisos de cobro, presupuesto, cita o gestoría con datos de la base; `deliver_confirmed()` solo tras confirmar |
| `agent.py` + `adapters/ai.py` | Agentes de IA (privada, compatible, Anthropic) con las mismas herramientas |
| `local_invoice.py`, `conversation_plan.py`, `intent_safety.py`, `fiscal_validation.py` | Facturas por lenguaje natural sin IA, huella del borrador, riesgo en órdenes de dinero, NIF |
| `learning.py` | Aprendizaje supervisado por negocio (apagado por defecto) |
| `web/whatsapp.py` | Entrada (`handle_inbound`), identidad por teléfono y por número receptor, cola de salida (`queue_text`, `queue_template`, `process_outbox`), firma (`verify_signature`) |
| `web/whatsapp_documents.py` | Fotos y PDF por WhatsApp: `ingest()` y correcciones en el chat (`handle_reply()`) |
| `whatsapp_templates.py` | Las nueve plantillas de Meta declaradas en código |
| `adapters/transcription.py`, `private_voice.py` | Voz a texto: Groq o Whisper privado |
| `documents/service.py` | Entrada única de documentos (web, WhatsApp y correo): valida, guarda, deduplica por negocio y clasifica |
| `documents/local_reader.py`, `documents/ocr.py`, `documents/reading.py`, `adapters/extraction.py` | Lectura: texto del PDF, OCR local con Tesseract y, si el negocio lo permite, extracción con IA |
| `documents/review.py`, `documents/pdf_batch.py` | Revisión y confirmación del borrador; PDF con varias facturas por rangos de páginas |

## Reglas que no se rompen

1. **La IA nunca decide permisos ni a qué negocio pertenece algo.** `run_tool()`
   recibe el `business_id` del servidor, no del modelo.
2. **Acción sensible = propuesta.** Emitir, cobrar, borrar o enviar pasa por
   `action_review.propose()`. Una orden nueva descarta la propuesta anterior; una
   **pregunta** no la descarta, para no perder una factura a medias por consultar algo.
3. **La IA no puede decir que hizo algo que no hizo.** Si la respuesta de una IA dice
   «factura creada» sin recibo de ejecución en ese turno, `_handle_turn()` la
   sustituye por un mensaje honesto. Lo mismo si imita una tarjeta de revisión
   («Responde SÍ…») sin propuesta guardada detrás (30-sep).
4. **Si una IA falla después de ejecutar una herramienta, no se reintenta con otra**
   (`PartialAgentExecutionError`): se pide revisar la actividad, para no duplicar.
5. **IA externa solo con permiso del negocio** (`db.integration_enabled(…,
   "ai_external")`) **y crédito reservado** (`db.claim_ai_credit`). Lo local no gasta.
6. **WhatsApp:** primero se valida el número que recibe y después quien escribe. Un
   número desconocido nunca recibe respuesta en nombre de otro negocio. Un teléfono
   tiene una sola identidad: titular o trabajador.
7. **Los mensajes proactivos solo con plantilla aprobada por Meta.** El texto libre
   solo dentro de la ventana de 24 horas.
8. **Emitir por WhatsApp pide una segunda confirmación**, porque una nota de voz se
   puede oír mal.
9. **Un documento nunca entra solo en las cuentas.** Primero es un borrador; solo la
   confirmación crea el gasto o registra la factura recibida, en la misma transacción.
10. **Herramientas solo locales** (1-oct): `aceptar_presupuesto`,
    `rechazar_presupuesto`, `cancelar_cita` y `mover_cita` están en `_DISPATCH` pero
    no en `TOOLS`, así que ninguna IA puede llamarlas. Solo las propone `nlu.parse()`,
    siempre con tarjeta de SÍ; con la revisión apagada, `chat.py` remite a la web.
    Cancelar una cita la marca `cancelado` (no la borra): `jobs_for_date` y la agenda
    por chat la ocultan, la web la tacha y el `.ics` la publica como CANCELLED.

## Estado real (28-sep-2026)

- Interruptores (`config.py`): `NOESIS_ASSISTANT_REVIEW_ENABLED` (propuestas y «sí/no»)
  y `NOESIS_LOCAL_PLANNER_ENABLED` están definidos en producción;
  `NOESIS_ASSISTANT_LEARNING_ENABLED`, `NOESIS_CONVERSATION_ISOLATION_ENABLED` y
  `NOESIS_WHATSAPP_INBOX_ENABLED` están **apagados** (por defecto `False`).
- En Railway existen `ANTHROPIC_API_KEY` y `GROQ_API_KEY`; falta validar en real el
  respaldo de IA y una nota de voz por WhatsApp. El modelo de respaldo es
  `NOESIS_FALLBACK_MODEL` (por defecto `claude-sonnet-5`).
- WhatsApp central funciona con el límite de una cuenta sin verificar; el número de
  cada negocio espera la verificación de Meta.

## Pruebas que lo cubren

Órdenes y lenguaje: `test_ordenes_del_dia`, `test_intent_safety`,
`test_conversation_safety`, `test_orden_a_medias`, `test_compound_corrections`,
`test_correcciones`, `test_nombre_dictado`, `test_client_name_rules`,
`test_alta_de_ficha`, `test_agenda_orders`, `test_client_signup_orders`.
Facturas por chat: `test_invoice_conversation`, `test_local_invoice`.
Cerebro y memoria: `test_internal_brain`, `test_learning`, `test_ai_model_config`.
Documentos: `test_document_reading`, `test_pdf_batch`, `test_received_invoices`.
WhatsApp y voz: `test_whatsapp_multichannel`, `test_whatsapp_documents`,
`test_whatsapp_inbox`, `test_conversation_isolation`, `test_voice_feedback`,
`test_private_voice`, `test_charla_whatsapp` (conversación real: faltas de móvil,
notas de voz como las escribe Whisper, clientes, agenda y mensajes sin texto).

## Al revisar código de esta zona

- [ ] ¿Una herramienta nueva que escribe está cubierta por `action_review` si toca
      dinero, fiscalidad, envíos o borrados?
- [ ] ¿Tiene permiso por plan en `_TOOL_ENTITLEMENTS` si es de plan Negocio?
- [ ] ¿Una regla nueva de `nlu.py` se ha medido con el corpus de
      `test_ordenes_del_dia` antes y después? «Medir primero, luego tocar».
- [ ] ¿Funciona en castellano **y** catalán, con importes y horas dichos en letra?
- [ ] ¿Un cambio en la escalera mantiene que lo local va antes que la IA?
- [ ] ¿Algún mensaje de error enseña nombres internos o variables de entorno a un
      autónomo? No debe.
- [ ] ¿Algo nuevo de WhatsApp proactivo usa una plantilla declarada en
      `whatsapp_templates.py`?

## Dudas frecuentes

- **¿Por qué una orden cae en «coach» en vez de ejecutarse?** Normalmente `nlu.parse()`
  no la reconoce y no hay IA disponible o permitida para ese negocio. Mira el orden
  de la escalera y el `source` de la respuesta (`local` o `ia`).
- **¿Dónde se guarda la conversación?** `db.add_assistant_message`, con el canal y la
  página. La memoria del negocio es visible y borrable desde Ajustes.

## Más detalle

[`WhatsApp-Cerebro`](../03-whatsapp-e-integraciones/WhatsApp-Cerebro.md) ·
[`IA-local`](../02-tecnico/IA-local.md) ·
[`Fiabilidad-conversacional-y-Whisper`](../02-tecnico/Fiabilidad-conversacional-y-Whisper.md) ·
[`Agente-operativo-fiable`](../02-tecnico/Agente-operativo-fiable.md)
