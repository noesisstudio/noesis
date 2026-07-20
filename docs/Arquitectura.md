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
- `db.py` — frontera única de datos: Postgres con `DATABASE_URL` y SQLite local como
  fallback.
- `banking.py` — importa extractos CSV en local, deduplica y propone coincidencias;
  el titular confirma antes de crear un cobro en el ledger.
- `migrations.py` — esquema versionado con subida/bajada; Railway lo aplica en
  pre-deploy.
- `web/whatsapp.py` — entrada idempotente y cola durable de salida. Persiste antes
  de enviar, reintenta con backoff y aplica estados `sent/delivered/read` de Meta.
- `adapters/email.py` + `email_outbox` — el correo se persiste antes de SMTP y el
  scheduler lo entrega con idempotencia, bloqueo entre réplicas y backoff.
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
- Las sesiones se revocan al cambiar contraseña; las cuentas sin suscripción activa
  solo conservan acceso a pago, exportación y baja.
- El scheduler registra cada ejecución para evitar duplicados entre réplicas. La
  outbox de WhatsApp usa claves idempotentes y `FOR UPDATE SKIP LOCKED` en Postgres
  para que varias réplicas no envíen la misma fila.
- La outbox de correo aplica la misma frontera durable. Los fallos agotados y los
  servicios sin configurar se muestran solo en administración, nunca como un centro
  de estado técnico para el cliente.
- `/health` comprueba que el proceso responde y `/ready` que la versión de esquema
  esperada está aplicada y la base de datos disponible.
- Los backups incluyen una copia verificada de la base de datos y un ZIP separado,
  también verificado por hashes, con los archivos de `DOCS_PATH`.
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

## Principios
- Datos en infraestructura propia/gestionada; solo el proveedor externo autorizado
  recibe el contexto que el nivel local no resuelve.
- Dependencias mínimas (hash con stdlib, no librerías pesadas).
- Adaptadores: cambiar de proveedor = cambiar 1 archivo.

Qué falta técnicamente: ver [[Tareas-vivas]]. Para conectar servicios externos,
consultar [[Conectar-APIs]].
