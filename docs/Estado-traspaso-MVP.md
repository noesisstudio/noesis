# Estado, traspaso y camino al MVP

> Documento vivo para **continuar el trabajo desde cualquier agente** (Claude o Codex)
> sin perder el hilo. Si lo retomas: lee esto entero, luego `AGENTS.md`.
> Última actualización: **2026-07-01**.

---

## 1. Dónde estamos (resumen en 30 segundos)

Noesis es un **copiloto de negocio por WhatsApp para autónomos de servicios**. Está
**desplegado y vivo 24/7** en Railway (`web-production-2d617.up.railway.app`). La rama
`main` (= `claude/portal-cliente`) tiene integrado el trabajo de los dos agentes.

**Hecho y en producción:**
- Núcleo: agenda, clientes, presupuestos, facturas (con IVA/IRPF + PDF), cobros,
  gastos, impuestos (303/130), análisis financiero. Multi-negocio aislado por
  `business_id`. Login propio (PBKDF2 + sesiones firmadas).
- **Cuña diferencial:** portal del cliente sin contraseña (`/p/{token}`: aprobar
  presupuestos, ver/descargar facturas) + envío del enlace por WhatsApp (wa.me).
- **Copiloto proactivo:** detecta trabajos hechos sin facturar, da un plan diario
  priorizado con el "porqué", y registra el ciclo del consejo
  (recomendado→aceptado→completado, "ledger").
- **Diseño fintech** en las 12 pantallas (paleta fría + verde de marca, KPIs,
  mini-barras, banda destacada).
- **Personalización:** 3 plantillas de factura (clásica/minimal/editorial) + logo o
  monograma automático, reflejado en PDF y portal.
- **Fundaciones SaaS:** `/health` y `/ready`, modelo de activación (6 pasos
  cliente→cobro), analítica interna `product_events`, onboarding de 3 pasos, embudo
  en el panel de fundador.
- **De Codex en `main`:** Holded real (adapter), plantillas de WhatsApp, emails,
  recordatorios, NLU flexible, módulo `documents/` ("papeles": recibos/tickets + OCR
  opcional) y datos fiscales del cliente.
- **Equipo y fichaje (migración 5 en `main`):** trabajadores aislados por negocio,
  asignación desde Agenda, planning por WhatsApp, acceso personal `/t/{token}`, PIN
  opcional y fichaje con GPS puntual opcional.
- **Fichaje justificable (en `codex/fichaje-legal`, pendiente de revisión):**
  migración 6 con sellos SHA-256 encadenados y protección *append-only*; correcciones
  y anulaciones auditadas; pausas; historial de 30 días para el trabajador; informes
  CSV/PDF con verificación de integridad; política de empresa e información RGPD con
  acuse. Compatible con SQLite/Postgres.
- **Veri*Factu fase 1 (en `codex/verifactu-fase1`, apilada sobre fichaje-legal):**
  migración 7; registro de alta append-only, huella SHA-256 AEAT encadenada por
  emisor, QR tributario, rectificativas R1-R5, eventos y exportación XML validada
  contra el XSD oficial. No transmite a AEAT ni usa certificado.

**Pruebas:** 68/68 en `tests/test_backend.py` (SQLite local, rama
`codex/verifactu-fase1`).

---

## 2. Mapa rápido del código

| Archivo | Qué es |
|---|---|
| `src/noesis/db.py` | Único punto de contacto con SQLite/Postgres. Selecciona Postgres con `DATABASE_URL`. |
| `src/noesis/migrations.py` | Esquema versionado, incluidas FKs multiempresa, `documents` y migración 6 de fichaje inalterable. |
| `src/noesis/agent.py` | **El cerebro IA**: bucle de tool-use con Claude. Sistema acotado al negocio. Solo se activa con `ANTHROPIC_API_KEY`. |
| `src/noesis/nlu.py` | Cerebro local por reglas (gratis, sin API): resuelve los comandos frecuentes. |
| `src/noesis/web/chat.py` | Orquestador híbrido: intenta NLU local → si no, agente IA. Aquí vive el copiloto (plan diario, sin-facturar, ledger). |
| `src/noesis/tools.py` | Acciones que el agente sabe ejecutar (agendar, facturar, cobrar, consultar…). |
| `src/noesis/web/whatsapp.py` | Webhook de mensajes/estados + outbox durable, reintentos y vinculación por código. |
| `src/noesis/web/server.py` | App FastAPI: ~70 rutas (páginas, API, onboarding, webhooks). |
| `src/noesis/web/templates/equipo.html` | Gestión del equipo, estado diario, GPS y enlaces personales. |
| `src/noesis/web/templates/fichaje.html` | Portal móvil por token para fichar, consultar el historial y leer la información RGPD. |
| `src/noesis/web/invoice_pdf.py` | PDF de factura con marca (plantillas + logo/monograma). |
| `src/noesis/web/work_reports.py` | Informes CSV/PDF verificables de registro de jornada. |
| `src/noesis/verifactu.py` | Huella, QR y XML según especificaciones técnicas AEAT. |
| `src/noesis/documents/` | Módulo de "papeles" (Codex): subir/guardar/leer documentos. |
| `src/noesis/adapters/` | `invoicing.py` (mock→Holded), `email.py` (SMTP), `transcription.py` (Whisper local). |
| `config.py` | Lee todas las variables de entorno (`.env`). |

---

## 3. Cómo continuar (protocolo multi-agente)

- **Una rama por agente** (`claude/*`, `codex/*`). Fusionar a `main` revisando el diff.
- **REGLA DE ORO que casi se salta el 2026-06-30:** no editar los mismos archivos a
  la vez, y **verificar siempre `git branch --show-current` antes de operar git** (una
  vez quedó `main` checked-out en la copia local y provocó confusión). Avisa de qué
  archivos vas a tocar.
- Railway **auto-despliega en cada push a `main`**. `/health` y `/ready` sirven de
  señal de "deploy vivo".
- Reparto histórico: Claude = backend/seguridad/fiscalidad/integraciones/diseño;
  Codex = frontend/UI/contenido + Holded/documentos. (Hoy ya se solapa; coordinad.)

---

## 4. Qué hay que CONFIGURAR para conectarlo todo

Copia `.env.example` a `.env` (y en Railway, ponlo como variables de entorno). Claves:

| Variable | Para qué | ¿Bloqueante? |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Enciende el cerebro IA** (sin ella solo va el NLU local por reglas). | Sí, para "que entienda cualquier frase". |
| `NOESIS_WHATSAPP_NUMBER`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` | WhatsApp Cloud API real (recibir/enviar). | Sí, para el canal WhatsApp. |
| `NOESIS_WHISPER_MODEL`, `NOESIS_WHISPER_DIR` + `pip install -e ".[audio]"` | Transcribir notas de voz en local. | No (degrada a "mándame texto"). |
| `STRIPE_*` | Cobro de la suscripción. | No (alta entra en prueba manual). |
| `HOLDED_API_KEY` | Facturación homologada Verifactu. | No (mock hasta que haya cliente que facture oficialmente). |
| `SMTP_*` | Emails (reset de contraseña, avisos). | No (si falta, va al log). |
| `NOESIS_SECRET`, `NOESIS_BASE_URL` | Seguridad y enlaces. | Sí en producción (ya puestas). |

### Conectar WhatsApp de verdad (resumen)
1. Meta for Developers → app + producto **WhatsApp** → número verificado (el ÚNICO de
   Noesis; el autónomo se identifica por su teléfono).
2. Coge `WHATSAPP_TOKEN` (permanente), `WHATSAPP_PHONE_ID`, define `WHATSAPP_VERIFY_TOKEN`
   y `WHATSAPP_APP_SECRET` (App Secret).
3. Webhook → `https://<tu-dominio>/webhook/whatsapp` (GET verifica, POST enruta). El
   código ya está listo en `whatsapp.py`.
4. El pipeline de **audio ya está cableado**: entra nota de voz → `_audio_to_text`
   (Whisper) → `chat.handle` → NLU/agente → ejecuta la acción.
5. Antes de activar proactivos, crea y aprueba en Meta las cuatro plantillas cuyo
   nombre se configura con `WHATSAPP_TEMPLATE_*`. Resúmenes y avisos programados no
   usan texto libre.

---

## 5. ANÁLISIS: qué falta para tener un MVP y empezar con clientes

El producto está **muy completo de funciones**. Lo que falta para pasar de "demo
impresionante" a "piloto con clientes reales" es sobre todo **conectar y endurecer**, no
construir más features.

### P0 — Bloqueante para el primer piloto (días)
1. **Encender el cerebro:** poner `ANTHROPIC_API_KEY` en Railway. Sin ella el chat solo
   entiende comandos fijos; con ella entiende cualquier frase (acotado al negocio).
2. **WhatsApp real:** número verificado en Meta + las 5 variables. Es EL canal y EL
   diferencial; hoy funciona simulado.
3. **Dominio:** conectar `bynoesis.com` (hoy se sirve por la URL de Railway). Da
   confianza para vender.
4. **Probar el ciclo de punta a punta con 1 negocio real:** alta → perfil → cliente →
   presupuesto → enviar al cliente por WhatsApp → aprobación en el portal → factura →
   cobro. Cazar fricciones reales.

### P1 — Para fiarse con varios clientes (1–3 semanas)
5. **Postgres**: implementación terminada en `codex/postgres`, pendiente de revisión
   y activación en Railway. No se ha tocado la SQLite ni la BD de producción.
6. **WhatsApp fiable:** implementado en `codex/whatsapp-fiable`, pendiente de
   revisión y de aprobar/configurar las plantillas reales en Meta. Incluye cola
   durable, backoff, estados `sent/delivered/read` e idempotencia de webhooks.
7. **Veri*Factu fase 2:** certificado digital, remisión automática y tratamiento
   de respuestas/reintentos de la AEAT antes de usar el modo en producción.
8. **Emails transaccionales** (SMTP real) y **copias de seguridad verificadas** (probar
   una restauración, no solo que se hagan).

### P2 — Crecimiento (después de validar)
9. CI en GitHub + más tests (Stripe, suscripciones, WhatsApp, aislamiento HTTP).
10. Monitorización/alertas, cohortes de activación/retención, app móvil nativa,
    automatizaciones de ciclo de vida (avisar si una cuenta no crea cliente/no factura).

### Deuda técnica concreta (de la lista de Codex)
- [x] `/health` y `/ready` — **hecho**.
- [x] `@app.on_event` → `lifespan` — **hecho**.
- [x] Código Postgres + quitar `DEFAULT_BUSINESS_ID=1` (pendiente activar en Railway).
- [ ] Partir las ~70 rutas de `server.py` en módulos por dominio.
- [x] Migraciones versionadas con upgrade/downgrade.
- [ ] CI + restaurar backups + e2e Postgres.

---

## 6. TAREAS PARA CODEX (backend) — lista accionable
> El fundador continuará con Codex para llevar la empresa al máximo. Estas son las
> tareas de backend, en orden de prioridad, con criterio de "hecho". Coordínate:
> avisa de qué archivos tocas y verifica `git branch --show-current` antes de operar.

1. **Activar Postgres en Railway tras revisar `codex/postgres`.**
   - Código listo: `psycopg`, SQLite fallback, migraciones 1→2, FKs compuestas,
     `business_id` obligatorio y tests de lectura/escritura cruzada.
   - Pendiente operativo: backup manual del volumen, provisionar Postgres limpio,
     enlazar `DATABASE_URL`, fusionar el PR y validar `/health` + `/ready`.

2. **Migraciones versionadas** (Alembic o equivalente) en vez de los `ALTER` en
   `_MIGRATIONS`. Hecho cuando: el esquema se versiona y se puede subir/bajar.

3. **WhatsApp fiable (producción, no piloto).**
   - Implementado en `codex/whatsapp-fiable`, basado en `codex/postgres`; pendiente
     de PR/revisión y configuración de las plantillas en Meta.
   - Cola durable de salida + reintentos con backoff + registro del estado de entrega
     (sent/delivered/read) usando los webhooks de estado de Meta.
   - Plantillas aprobadas por Meta para los mensajes proactivos (resúmenes, avisos de
     cobro) — fuera de la ventana de 24 h solo se puede con plantilla.
   - Hecho cuando: un mensaje que falla se reintenta y queda trazado; los proactivos
     usan plantilla aprobada.

4. **Partir `server.py`** (~70 rutas) en routers por dominio (auth, negocio, api,
   onboarding, webhooks, documentos). Hecho cuando: cada dominio en su módulo y los
   tests siguen verdes.

5. **CI en GitHub Actions**: lint + `python -m unittest` en cada push/PR, y bloquear
   merge a `main` si fallan. Hecho cuando: el badge está verde y un PR rojo no mergea.

6. **Endurecer fiscalidad/Verifactu**: cuando haya un cliente que facture oficialmente,
   activar Holded real (`HOLDED_API_KEY`) y validar numeración/series y Verifactu.

7. **Backups verificados + monitorización**: probar de verdad una restauración del
   backup; añadir alertas básicas (errores 5xx, caída de `/ready`).

Notas: el coste de IA ya está minimizado (cerebro local gratis + respaldo en Haiku vía
`NOESIS_FALLBACK_MODEL`). El audio (Whisper) es local y sin coste por uso.

## 7. Próximos pasos del fundador (no técnicos)
1. Poner `ANTHROPIC_API_KEY` y las variables de WhatsApp en Railway.
2. Verificar el número de WhatsApp en Meta y conectar `bynoesis.com`.
3. Probar el ciclo completo con un negocio real y anotar fricciones.
4. Dar de alta 3-5 autónomos del mismo perfil para el piloto.

Ver también: `docs/Roadmap.md`, `docs/Arquitectura.md`, `docs/Producto.md`.
