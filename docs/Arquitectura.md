# Arquitectura

Objetivo: máximo posible **interno/cerrado**, mínimo de APIs externas (coste y
privacidad). Ver [[Investigación]] y [[Decisiones]].

## Diagrama mental
```
WhatsApp / Web / App  ─►  Cerebro  ─►  Herramientas  ─►  Base de datos
                            │
                  (local: nlu.py, gratis)
                  (IA privada: OpenAI-compatible)
                  (IA externa autorizada y limitada)
                            │
                            └─►  Facturación nativa Veri*Factu
```

## Piezas (código en `src/noesis/`)
- `web/server.py` — ensamblador FastAPI. Las páginas y APIs viven en routers por dominio.
- `web/routers/projects.py` — proyectos, miembros, horas y costes; todas las rutas
  quedan protegidas por sesión y `business_id`.
- `web/templates/landing.html` — página pública de producto en `/` con CTA a login/registro.
- `web/static/app.css` — sistema de diseño propio (sin Tailwind ni CDNs).
- `web/static/noesis-product-preview.png` — captura real del panel usada como visual de producto.
- `web/static/vendor/chart.umd.min.js` — Chart.js servido en local.
- `nlu.py` — **cerebro local** por reglas (sin coste/API).
- `web/chat.py` — orquesta reglas → IA privada → IA externa autorizada. Si un nivel
  falla o agota créditos, conserva el acompañamiento local.
- `agent.py` + `tools.py` — agentes privado/externo y acciones multi-negocio. El
  modelo nunca decide por sí solo los permisos ni el aislamiento.
- `adapters/ai.py` — contrato HTTP OpenAI-compatible para Ollama, llama.cpp, vLLM
  u otro servicio privado, sin SDK ni dependencia nueva. Ver [[IA-local]].
- `db.py` — frontera única de datos: Postgres con `DATABASE_URL`, pool de conexiones
  acotado por proceso y SQLite local como fallback.
- `banking.py` — importa extractos CSV en local, deduplica y propone coincidencias;
  el titular confirma antes de crear un cobro en el ledger.
- `migrations.py` — esquema versionado con subida/bajada; Railway lo aplica en
  pre-deploy.
- `web/whatsapp.py` — entrada idempotente y cola durable de salida. Persiste antes
  de enviar, reintenta con backoff y aplica estados `sent/delivered/read` de Meta.
- `adapters/email.py` + `email_outbox` — el correo se persiste antes de salir por API
  HTTPS o SMTP y el scheduler lo entrega con idempotencia, bloqueo entre réplicas y
  backoff.
- `web/routers/finance.py` — publica un feed ICS secreto y revocable para la agenda;
  no requiere OAuth ni una API de calendario para la suscripción de solo lectura.
- `web/scheduler.py` — genera los proactivos con plantillas aprobadas y ejecuta el
  worker de la cola cada 15 segundos. Los recordatorios de cobro respetan el
  opt-out y la cadencia de cada negocio, usan el restante y deduplican por
  factura/escalón antes de enlazar al portal privado.
- `db.py` también persiste eventos de producto y calcula el recorrido de activación
  por negocio sin depender de una plataforma analítica externa.
- `adapters/invoicing.py` — frontera del motor propio. La emisión interna registra
  Veri*Factu en la misma transacción y no delega facturas en terceros. Ver
  [[Fiscalidad]].
- `invoice_series`, `invoice_lines` y `recurring_invoices` — series configurables,
  conceptos estructurados y programación idempotente de borradores recurrentes. La
  emisión automática requiere autorización explícita del titular.
- `invoice_cancellation_records` y `verifactu_cancellation_outbox` — anulaciones
  fiscales append-only enlazadas al alta original. Conservan la factura emitida y
  usan la misma cadena cronológica de huellas y una cola durable independiente.
- `adapters/extraction.py` — visión Claude opcional para sugerir un borrador de
  gasto desde una foto; sin clave devuelve `None` y mantiene el flujo manual.
- `verifactu.py` — formato técnico AEAT: cadena de huella, SHA-256, URL/QR y XML.
- `web/auth.py` — login (PBKDF2, sesiones firmadas). Aislamiento por dueño.
- `web/server.py` — `TrustedHostMiddleware` admite el origen canónico, su único alias
  público y los hosts internos exactos. En producción el alias recibe 308 hacia
  `BASE_URL` conservando ruta/query; no se redirigen healthchecks ni hosts privados.
- `documents/validation.py` — valida el contenido real de imágenes y PDF antes de
  OCR o almacenamiento; limita píxeles/páginas y bloquea acciones PDF activas.
- `documents/malware.py` — transmite el archivo validado a un ClamAV privado por
  `INSTREAM`; si el despliegue exige el escáner, una caída falla cerrada antes de
  escribir en almacenamiento.
- `documents/service.py` + `documents/repo.py` — calculan SHA-256 tras validar y
  escanear, y la migración 38 impone una huella única por negocio. La búsqueda de
  históricos se limita al mismo `business_id` y tamaño para evitar comparación o
  filtración entre clientes; una colisión concurrente elimina el fichero sobrante.
- `security_center.py` + `security_events` — parte CISO de solo lectura sobre una
  bitácora append-only y encadenada, sin contenido operativo ni datos de contacto.
- `tests/test_backend.py` — regresiones de aislamiento, facturación, webhooks,
  fiscalidad, NLU y revocación de sesiones.

## Garantías del backend
- El aislamiento se valida en la ruta y de nuevo en `db.py`; una mutación nunca
  devuelve una entidad de otro `business_id`.
- Proyectos, miembros y costes usan FKs compuestas por negocio. El margen se deriva
  de presupuesto menos entradas reales; las horas son entradas con cantidad y coste.
- `business_id` es obligatorio en todo acceso operativo. Las FKs compuestas
  `(business_id, id)` impiden enlazar un trabajo, factura, presupuesto o documento
  con entidades de otra empresa.
- Un contenido documental idéntico no se almacena dos veces dentro del mismo
  negocio. La restricción vive también en PostgreSQL, no solo en la interfaz, y no
  existe deduplicación global que permita inferir archivos de otra empresa.
- La emisión de factura es atómica e idempotente. La secuencia se persiste por
  negocio/serie/año y los datos fiscales y líneas quedan congelados en la factura.
  General, rectificativas y tickets usan series separadas sin renumerar históricos.
- Los cobros viven en `invoice_payments`: el estado y el importe restante se
  derivan del ledger. Cada alta bloquea la factura (`BEGIN IMMEDIATE` en SQLite,
  `FOR UPDATE` en Postgres) para impedir que dos cobros superen el total.
- Una foto de ticket crea primero un documento y un borrador. Solo la confirmación
  explícita crea el gasto y enlaza `documents.expense_id` dentro de la transacción.
- En modo Veri*Factu, la misma transacción añade un registro de alta append-only,
  encadenado por NIF emisor. Las rectificaciones crean una nueva factura R1-R5 y
  conservan el original.
- Una anulación Veri*Factu no borra ni cambia la factura: crea un registro de
  anulación inmutable, enlazado al alta aceptada, y lo remite desde su propia outbox.
- Facturas emitidas no se borran ni se renumeran. Los borrados RGPD conservan los
  documentos sujetos a obligación fiscal.
- Los webhooks de WhatsApp y Stripe verifican firma y deduplican IDs. La migración
  16 distingue eventos en proceso, completados y fallidos: un error devuelve 5xx y
  permite reintentar; solo un evento completado se descarta como duplicado.
- Las sesiones se revocan al cambiar contraseña; la gestoría usa una tabla de tokens
  separada porque su identidad puede abarcar varios negocios. Sus enlaces son
  hasheados, caducables y de un solo uso, y recuperar la clave conserva el MFA. Las
  cuentas sin suscripción activa
  solo conservan acceso a pago, exportación y baja.
- En producción las sesiones usan cookie `__Host-`, caducan por inactividad y el
  administrador exige Google OAuth; si faltan sus credenciales el panel queda
  bloqueado, pero las rutas de clientes y salud siguen disponibles.
  Login y recuperación
  tienen límites persistentes por origen y cuenta sin guardar esos valores en claro.
- El servidor restringe hosts, no expone OpenAPI en producción, emite cabeceras de
  aislamiento y registra request IDs, ruta, estado y duración sin query strings ni
  contenido personal. En Railway admite además su hostname exacto de healthcheck
  (`healthcheck.railway.app`) solo cuando detecta ese entorno; nunca abre un wildcard.
- El scheduler registra cada ejecución para evitar duplicados entre réplicas. La
  outbox de WhatsApp usa claves idempotentes y `FOR UPDATE SKIP LOCKED` en Postgres
  para que varias réplicas no envíen la misma fila.
- La outbox de correo aplica la misma frontera durable. Los fallos agotados y los
  servicios sin configurar se muestran solo en administración, nunca como un centro
  de estado técnico para el cliente.
- `/health` comprueba que el proceso responde e identifica el release desplegado;
  `/ready` devuelve esa misma huella y la versión de esquema realmente aplicada.
- `noesis-production-check` consume ambas rutas desde fuera y las cruza con el estado
  versionado del repositorio. También recorre el sitemap y valida la superficie
  pública y sus protecciones sin autenticar ni tocar datos. GitHub lo programa cada
  seis horas; una caída queda registrada como workflow fallido, aunque una operación
  masiva debe añadir alerta 24/7 y guardia externa independiente de GitHub/Railway.
- Los backups incluyen una copia verificada de la base de datos y un ZIP separado,
  también verificado por hashes, con los archivos de `DOCS_PATH`. Un simulacro
  semanal independiente repite la restauración en un fichero/esquema descartable y
  deja evidencia inmutable; nunca restaura encima de producción.
- La copia externa exige HTTPS en producción y solicita cifrado en reposo al servicio
  S3-compatible. Su disponibilidad solo se considera validada tras una restauración.
- Los eventos de producto se almacenan siempre con `business_id`. La activación se
  deriva de datos operativos reales, no de clics o páginas visitadas.

## Flujo SaaS de alta
```
Prueba o contratación → cuenta → negocio → operativa → WhatsApp
                                                    │
                       prueba ───────────────────────┴─► panel
                       contratación ──────────────────► checkout → panel
```

El alta recoge sector, tamaño del equipo, provincia, objetivo principal y elección
explícita de IA. Después configura datos fiscales, IVA/IRPF, plantilla y vencimiento
de factura, cobro, recordatorios, informes y gestoría. Son valores operativos que
usa el producto. Quien prueba entra sin tarjeta; quien contrata revisa al final el
plan mensual/anual antes del checkout. Google solo se ofrece si existen cliente y
secreto válidos.

Detalle y pendientes: [[Backend_Hardening]].

## Identidades y canales de WhatsApp

```text
Titular ───────┐
Trabajador ────┴─> número central Noesis
                    ├─ identidad por teléfono vinculado
                    ├─ órdenes/parte/fichaje
                    └─ aportación pendiente -> revisión titular -> efecto

Cliente final ───> número comercial del negocio
                    ├─ WABA + phone_number_id -> business_id
                    ├─ remitente -> contacto/cliente/lead dentro del negocio
                    ├─ conversación + inbox + documento
                    └─ acuse/escala/respuesta por la misma conexión
```

El destinatario se valida antes del remitente. No existe fallback desde un número
empresarial desconocido al canal central, porque responder con la identidad errónea
sería una filtración. Todas las relaciones nuevas repiten `business_id` y usan claves
foráneas compuestas o validación equivalente. La outbox guarda `connection_id`; por
eso un reintento conserva el número emisor correcto. Un coste de campo es una
aportación, no un asiento: solo la aceptación transaccional crea una línea de material
y la operación es idempotente. El teléfono central tiene una sola identidad efectiva:
titular o trabajador. Se rechaza una segunda vinculación y una ambigüedad histórica
bloquea la orden completa, sin escoger un negocio por aproximación.

## Principios
- Datos en infraestructura propia/gestionada; solo el proveedor externo autorizado
  recibe el contexto que el nivel local no resuelve.
- Dependencias mínimas (hash con stdlib, no librerías pesadas).
- Adaptadores: cambiar de proveedor = cambiar 1 archivo.

Qué falta técnicamente: ver [[Tareas-vivas]]. Para conectar servicios externos,
consultar [[Conectar-APIs]]. El modelo de amenazas y la operación segura viven en
[[Seguridad-operativa]].
