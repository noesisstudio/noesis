# WhatsApp como centro de operaciones — diseño para ejecutar

> **Qué es este documento**: el diseño completo, pensado y decidido, para convertir
> WhatsApp en el verdadero centro de Noesis. Escrito el 2026-07-03 a petición del
> founder ("el punto más diferencial es el WhatsApp, no las facturas").
>
> ✅ **CONSTRUIDO el mismo día** (migración 14): W0 (router de mèdia +
> confirmaciones SÍ/NO), W1 (cierre del día, aviso fiscal trimestral, config en
> Ajustes), W2 (foto de ticket → borrador de gasto por WhatsApp) y W4 (voz con
> fallback Groq → whisper local; falta solo GROQ_API_KEY, clic del founder).
> **Pendiente: W3** (PDF → gasto de proveedor / factura histórica con
> `source='importada'`) y, como siempre, **encender Meta** para el e2e real.

---

## 0. Marco estratégico (por qué esto y no más funciones de panel)

La tesis del founder es correcta y este documento la asume como norte:

- **La factura es el gancho, no el foso.** Veri*Factu obliga a cambiar de software:
  eso trae clientes. Pero facturar lo hará cualquier competidor.
- **El foso es que el autónomo no tenga que abrir NADA.** Todo su negocio entra y
  sale por el mismo chat donde ya vive: manda un audio y queda facturado; manda la
  foto del ticket y queda contabilizado; le llega el parte del día sin pedirlo.
  Eso no lo tiene Forjia (solo factura por WhatsApp), no lo tiene Holded (vive en
  el escritorio) y es carísimo de copiar bien.
- **Regla de oro del canal**: cada mensaje proactivo debe caber en una pantalla de
  móvil y terminar en UNA acción clara. WhatsApp no es un dashboard: es un
  copiloto que habla corto y hace.

## 1. Inventario honesto: qué existe ya (verificado en el código)

| Pieza | Estado | Dónde |
|---|---|---|
| Cola durable de envío + plantillas Meta + idempotencia | ✅ hecho | `web/whatsapp.py` (`whatsapp_outbox`, `queue_template`, backoff, estados) |
| Webhook entrante verificado (firma) + identificación por teléfono | ✅ hecho | `whatsapp.py` (`handle_inbound`, `db.get_business_by_phone`) |
| Descarga de mèdia de Meta (genérica, cualquier media_id) | ✅ hecho | `whatsapp._download_media` |
| Audio → texto (faster-whisper LOCAL, dep opcional `[audio]`) | ⚠️ cableado pero NO instalado en producción (RAM) | `adapters/transcription.py`, `whatsapp._audio_to_text` |
| Resumen diario y semanal programados con plantilla | ✅ funciones hechas | `web/scheduler.py` (`send_daily_summaries`, `send_weekly_summaries`) |
| Recordatorios de cobro al cliente (restante, escalones, idempotente) | ✅ en PR #15 | `scheduler.send_payment_reminders` |
| Extracción de ticket por visión (Haiku, validada, anti-inyección) | ✅ hecho (T2) | `adapters/extraction.py` |
| Módulo documentos (subida acotada, uuid, por negocio, vínculo a gasto) | ✅ hecho | `documents/` + migración 12 |
| **Webhook: imágenes y PDFs entrantes** | ❌ NO: `_extract_messages` solo lee `text` y `audio` | `whatsapp.py:145` |
| **Máquina de confirmación en el chat** (borrador → SÍ/NO) | ❌ NO existe | — |
| **Informe de cierre del día** (lo hecho, lo cobrado, lo pendiente) | ❌ NO existe (solo el brief de la mañana) | — |
| **Config de informes por negocio** (horas, on/off, qué bloques) | ❌ NO existe | — |
| **Ingesta de PDF** (gasto de proveedor / factura histórica) | ❌ NO existe | — |

**Conclusión**: el 60 % de la fontanería está. Lo que falta es (a) el router de
mèdia entrante, (b) el patrón borrador→confirmación, y (c) los informes de cierre
y su configuración. Nada requiere rediseñar lo existente.

## 2. Principios de diseño (no negociables)

1. **Nunca ejecutar dinero desde una interpretación.** Audio, foto o PDF generan
   siempre un **borrador** que se responde en el chat y se confirma con un SÍ.
   Texto tecleado explícito ("factura a Carlos 180") puede ejecutar directo como
   hoy, pero cualquier cosa que venga de transcripción/visión, confirmación.
2. **Local primero, IA después**: pypdf/NLU/reglas gratis; Haiku solo cuando hay
   imagen o PDF escaneado (céntimos); nunca un modelo caro en el camino rutinario.
3. **El contenido de un documento son DATOS, no instrucciones** (ya implementado
   en extraction.py; mantener en toda extracción nueva).
4. **Todo aislado por negocio** — el teléfono identifica (`get_business_by_phone`);
   un teléfono no vinculado NO puede meter datos (pero recibe invitación: bucle viral).
5. **Meta cobra por conversación iniciada por la empresa** (plantillas). Los
   informes se agrupan (1 plantilla/día máximo por tipo) y se aprovecha que la
   respuesta del usuario abre 24 h de mensajes libres gratis. Verificar tarifas
   vigentes al encender Meta (~3-6 céntimos por conversación de utilidad en España).

## 3. Fase W0 — El cimiento: router de mèdia + confirmación (HACER PRIMERO)

Sin esto no hay nada de lo demás. **Testeable al 100 % con mocks, sin Meta.**

### 3a. Ampliar `_extract_messages` (whatsapp.py)
Hoy solo extrae `text` y `audio.id`. Añadir:
```python
"image_id":    (message.get("image", {}) or {}).get("id"),
"image_mime":  (message.get("image", {}) or {}).get("mime_type"),
"document_id": (message.get("document", {}) or {}).get("id"),
"document_mime": ..., "document_filename": ...,
"caption":     el caption de imagen/documento si viene,
```
`_download_media` ya sirve tal cual (es genérica). Poner tope de descarga con
`config.MAX_UPLOAD_MB` (mismo patrón `read(max+1)` de siempre).

### 3b. Tabla de acciones pendientes (migración 14, `confirmaciones_whatsapp`)
```
whatsapp_pending_actions (
  id, business_id (FK), phone TEXT NOT NULL,
  kind TEXT NOT NULL,          -- 'gasto' | 'factura' | 'factura_historica' | ...
  payload TEXT NOT NULL,       -- JSON con el borrador validado
  document_id (FK compuesta a documents, nullable),
  expires_at, created_at
)
```
Reglas: **una pendiente por teléfono** (la nueva reemplaza a la anterior), TTL 30
minutos, siempre filtrada por `business_id`. En `handle_inbound`, ANTES de pasar
el texto a `chat.handle`: si hay pendiente viva y el texto ∈ {sí, si, ok, vale,
confirmo} → ejecutar y borrar; si ∈ {no, cancela, anula} → descartar y borrar.
Cualquier otro texto: se responde el flujo normal y la pendiente sigue viva hasta
su TTL (no molestar re-preguntando).

### 3c. Router en `handle_inbound`
```
texto   → (como hoy) códigos de vinculación / fichaje / confirmaciones / chat.handle
audio   → transcribir → si NLU detecta acción de dinero → BORRADOR; si consulta → directo
imagen  → descargar → extraction.extract_expense → guardar en documents/ →
          crear pendiente 'gasto' → responder resumen + "¿Lo apunto? SÍ/NO"
document(pdf) → Fase W3 (mientras tanto: "Lo he guardado en tus papeles" + documents/)
```
Respuesta tipo para imagen:
> 📄 He leído el ticket: **Ferretería Soler — 43,20 €** (IVA 21 %, 02/07).
> ¿Lo apunto como gasto? Responde **SÍ** o **NO**.

**Tests W0**: pendiente caduca; SÍ ejecuta una sola vez (carrera doble webhook =
`claim_webhook_event` ya existe); NO descarta; teléfono de otro negocio no ve ni
ejecuta pendientes ajenas; imagen > tope → mensaje de error amable sin crash;
teléfono no vinculado → invitación, nunca ingesta.

## 4. Fase W1 — Informes que llegan solos (lo que pidió el founder)

Reutiliza `scheduler.py` + plantillas. Lo nuevo es el **cierre del día** y la
**configuración**.

### 4a. Configuración por negocio (misma migración 14)
Columna `businesses.whatsapp_reports` TEXT (JSON), patrón idéntico a
`panel_layout` (tolerante a corrupto, claves desconocidas fuera):
```json
{"brief_manana": true, "hora_manana": 8,
 "cierre_tarde": true, "hora_tarde": 19,
 "resumen_semanal": true, "aviso_fiscal": true}
```
Tarjeta en Ajustes (como la de recordatorios del PR #15) + API. El scheduler pasa
de "hora fija global" a leer la preferencia (jobs cada hora que filtran negocios
por su hora elegida — mismo coste, sin APScheduler dinámico).

### 4b. Los cuatro informes (contenido decidido)
1. **Brief de la mañana** (ya existe `send_daily_summaries`; afinar contenido):
   citas de hoy (hora·cliente·zona), cobros a perseguir, sin-facturar. Fuente:
   `chat.daily_plan` (ya registra en el ledger del copiloto).
2. **Cierre del día** (NUEVO, `send_daily_closings`): qué se terminó hoy, qué se
   facturó (nº + importe), **qué se cobró hoy** (suma de `invoice_payments` con
   `paid_at` = hoy — el ledger de T1 lo da gratis), gastos apuntados, y UNA
   siguiente acción ("Mañana lo primero: reclamar a Marta, 420 €"). Es el informe
   de trabajo diario que pidió el founder: la sensación de "todo bajo control".
3. **Semanal** (ya existe; enriquecer): ingresos/costes/beneficio de la semana vs
   anterior (`month_billing` + rango), mora, y **IVA acumulado del trimestre**
   (`tax_quarter` ya lo calcula): "Llevas 1.240 € de IVA a apartar este trimestre".
4. **Aviso fiscal trimestral** (NUEVO, 4 envíos/año, día 1 de abr/jul/oct/ene):
   modelo 303/130 estimado con cifras y fecha límite. Coste Meta: irrelevante.

Cada informe = una plantilla Meta aprobada (añadir a `.env.example` con sus
parámetros exactos, como hizo el PR #15 con la de recordatorios). Idempotencia por
`claim_scheduled_run` + `idempotency_key` por negocio+día (patrón ya existente).

## 5. Fase W2 — Foto del ticket por WhatsApp (barato: reutiliza T2)

Ya diseñado en W0/3c: es SOLO cablear el router a `extraction.extract_expense`
(hecho, validado, anti-inyección) + pendiente 'gasto' + `db.add_expense(...,
document_id=...)` (hecho en migración 12, con anti-doble-vínculo). Al confirmar,
responder con el gasto creado y el total de gastos del mes. **Esfuerzo mínimo,
efecto WOW máximo — es la primera demo que enseñar a un piloto.**

## 6. Fase W3 — PDFs por WhatsApp: gastos de proveedor e histórico

Dos casos distintos con el mismo canal de entrada:

### 6a. Factura de proveedor en PDF → gasto
- **Local primero**: extraer la capa de texto con **pypdf** (dep pura-Python,
  ligera — justificada frente a la regla de mínimas deps; ya la usamos en tooling).
  Si hay texto → mandar SOLO el texto a Haiku (más barato y robusto que visión).
  Si no hay capa de texto (escaneado) → bloque documento/visión de Claude.
- Nueva función en `extraction.py`: `extract_document(data, mime, filename)` que
  devuelve `{tipo: 'gasto'|'factura_emitida'|'otro', campos..., confianza}`. El
  **clasificador decide**: si el NIF del emisor coincide con el del negocio, es una
  factura EMITIDA por él (caso 6b); si no, es un gasto (caso 6a).
- Flujo: PDF → clasificar+extraer → pendiente ('gasto' o 'factura_historica') →
  confirmación en el chat → crear + vincular documento.

### 6b. Facturas antiguas → histórico (el arma de onboarding)
El problema nº 1 de activación es la cuenta vacía. Esto lo mata: *"Reenvíame por
WhatsApp tus últimas facturas y te monto el histórico del año"*. Al confirmar,
se crean como ingresos históricos y el Análisis/Tesorería cobran vida el día 1.

**⚠️ Restricción Veri*Factu (crítica, no negociable)**: una factura importada NO
puede entrar en la cadena de `invoice_records` (rompería la huella encadenada y
sería falsear registros). Diseño: columna `invoices.source` ('noesis' default |
'importada') en la migración de esta fase. Las importadas: cuentan en analítica,
ingresos e IVA soportado histórico; **jamás** se re-emiten (`issue_invoice` las
rechaza), jamás generan registro Veri*Factu, y el PDF original queda en
`documents/` como justificante. Numeración: conservar la del PDF original en un
campo aparte (`external_number`), no consumir la secuencia de Noesis.

## 7. Fase W4 — Audio bien resuelto (decisión de coste para el founder)

El pipeline existe; el bloqueo es DÓNDE transcribir. Tres opciones, una decisión:

| Opción | Coste | Pros/Contras |
|---|---|---|
| faster-whisper local (lo cableado) | 0 €/uso; +RAM Railway (~7-10 €/mes de plan) | Privado, sin límites; añade ~1 GB RAM y arranque más lento |
| **API Whisper (Groq)** ← recomendada para empezar | ~0,002 €/min (casi gratis) | Cero RAM, latencia excelente; sale fuera (mismo caso que Claude: aceptable, ya sale lo complejo) |
| No transcribir | 0 € | "Mándame texto" — mata la promesa del canal |

**Recomendación**: adaptador con fallback en cadena — Groq si hay `GROQ_API_KEY`,
si no whisper local si está instalado, si no mensaje amable. `transcription.py` ya
es un adaptador: añadirle el backend Groq son ~40 líneas. Cuando haya volumen real,
reevaluar pasar a local por margen. La decisión de dar de alta Groq es 1 clic del
founder (como Meta y Stripe).

Y la regla de W0 aplica SIEMPRE: audio con acción de dinero → borrador+SÍ.

## 8. Seguridad del canal (ampliación de la auditoría existente)

- Solo se ingiere mèdia de **teléfonos vinculados**; no vinculado → invitación.
- Tope de tamaño por descarga (`MAX_UPLOAD_MB`, `read(max+1)`), allowlist de mime
  (jpg/png/webp para imagen; application/pdf para documento). HEIC: convertir o
  rechazar con mensaje claro (decidir en implementación; rechazar es aceptable).
- **Presupuesto de IA por negocio/día** (p. ej. 30 extracciones): contador en
  `product_events`; al superarlo, responder "mándamelo mañana o súbelo por la web".
  Protege el margen frente a un teléfono en bucle o abuso.
- El texto/imagen del documento nunca se trata como instrucciones (ya en el system
  prompt de extraction.py; replicar en `extract_document`).
- Registrar cada extracción en `product_events` (`media_ingested`, con tipo y
  resultado) → mide uso real del canal y coste.

## 9. Orden de ejecución y reparto

| # | Fase | Tamaño | Carril | Depende de |
|---|---|---|---|---|
| 1 | **W0** router mèdia + confirmaciones (migración 14 con la config de W1 incluida) | M | Codex o Fable (backend) | nada — mocks |
| 2 | **W2** foto ticket → gasto por WhatsApp | S | mismo PR o siguiente | W0 |
| 3 | **W1** cierre del día + config informes + aviso fiscal | M | backend + 1 pasada de Claude en Ajustes | migración 14 |
| 4 | **W3** PDF (factura recibida ya clasificable y confirmable; histórico emitido aún pendiente de flujo auditado con `source='importada'`) | L | Codex/Fable, revisión estricta (Veri*Factu) | W0 |
| 5 | **W4** audio Groq fallback | S | cualquiera | clic founder (GROQ_API_KEY) |
| — | Encender Meta (verificación empresa, token, webhook, aprobar plantillas) | clics | **FOUNDER** | bloquea el e2e real de TODO |

Todo lo anterior se construye y testea con mocks sin Meta. Pero **sin Meta nada
llega a un teléfono real**: sigue siendo el paso 0 del founder y el cuello de
botella de la validación. Las plantillas nuevas (cierre del día, aviso fiscal)
hay que enviarlas a aprobación de Meta al encender — tardan horas/días: hacerlo
el mismo día que se verifique la empresa.

## 10. Cómo se ve el día perfecto (el norte, para no perderlo)

> **8:00** — "Buenos días 👋 Hoy: 9:30 Marta (Badalona, caldera), 12:00 Luis
> (Gràcia). Te deben 1.840 € — a Ríos SL le reclamo hoy el 2º aviso yo. Nada sin
> facturar. 💪"
>
> **13:40** — 📷 *foto de un ticket* → "Ferretería Soler, 43,20 €, IVA 21 %.
> ¿Lo apunto? **SÍ** → Apuntado ✅ Llevas 312 € de gastos este mes."
>
> **17:15** — 🎤 *"factura a Marta la reparación de hoy, trescientos veinte más
> IVA"* → "Factura para **Marta Vidal**: 320 € + IVA = 387,20 €. ¿La emito?
> **SÍ** → Emitida la F-2026-041 con Veri*Factu ✅ ¿Se la envío con el enlace
> de pago?"
>
> **19:30** — "Cierre del día: 2 trabajos hechos, 1 factura emitida (387,20 €),
> cobrados 250 € de Luis. Mañana lo primero: presupuesto de la comunidad de
> Sants, caduca el viernes."

Eso no es una app de facturas. Eso es un empleado. Ahí está el valor del catálogo
29/49/99 € + IVA.
