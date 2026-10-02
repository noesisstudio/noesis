# Arquitectura

## 2026-10-02 — Fase 1.8, canales financieros

```text
Canal autenticado + recibo durable
  → financial_channels (interpretación cerrada, tarjeta exacta)
    → Capture.review / prepare (request + enlace + acuse review)
    → humano confirma op/hash/revisión
    → Capture.authorize (auth + recibo yes + pending CAS en commit)
    → Capture.execute (writer + cobertura + EE + result en commit)
  → respuesta HTTP / outbox Meta / PDF después del efecto
```

Monolito modular: repositorios financieros especializados y la infraestructura
existente de conexiones/transacciones; FinancialSession/execute_exact mantiene
Decimal/NUMERIC (SQLite TEXT canónico), sin normalización financiera a float.
Orden compartido de locks: negocio antes de operación y origen/pending/recurrencia.
La IA no selecciona ejecutores ni acredita aprobación.

Solo integración de canales con los Capture existentes, sin 1.9 ni activación.
`financial_channels/` enlaza propuestas y recibos mínimos con operaciones y
aprobaciones; no añade un motor financiero ni un event log operativo. Web exige
sesión/CSRF y UUID; chat turno/slot; WhatsApp provider/receptor/negocio/wamid;
documentos review UUID/documento/item/revisión; recurrentes schedule/vencimiento.
Autorización + recibo + consumo de pending atómicos; efecto posterior reintentable
con la misma operación. Scheduler genera borradores y exige confirmación humana;
no mandato abierto. Migración 68, enlaces inmutables y huella mínima de plantilla.
Cinco flags siguen OFF, guards capturados conservados y opt-in sin fallback.
Cierre técnico: **31 PASS / 0 FAIL**. Nuevas SQLite41/PG41, PostgreSQL total234,
general1617 (1298.519 s), Node9 y gates locales PASS. Último transporte de
revisión revalidado en ambos motores/HTTP/Node; alcance exacto en el [cierre](architecture/FASE-1.8-cierre.md).
Incluye autoauditorías, límites externos y diagnóstico/rollback.
Pendientes externos: CI remoto/despliegue y Meta real no certificados aquí;
activación y otra fase solo con nueva orden. CSV antiguo sin cuenta/batch y audio sin UUID quedan bloqueados
para mutaciones capturadas. Históricos, retención/export financiero y rollout
siguen en fases posteriores expresamente autorizadas.


## Orden vigente — exclusivamente Fase1.7

1.1–1.6 aceptadas. SupplierInvoiceCapture/ExpenseCapture conectan solo
supplier_invoice.confirmed/corrected/voided y expense.confirmed/voided v1.
Writers compartidos, autorización durable, cobertura inmutable por revisión,
continuidad antes/después, logical void y guards SQL. Documento/clasificación/
source/EE/resultado comparten commit. Flags OFF; no1.8, históricos ni activación.
Pagada es etiqueta operativa, no supplier payment/AP settlement. No GL/Tax/
OpenItems/reporting nuevo. Legacy no capturado conserva comportamiento.
[Orden](architecture/FASE-1.7-orden.md), [ADR-011](architecture/ADR-011-purchasing-capture.md),
[API](architecture/PURCHASING-CAPTURE-v1.md), [cierre](architecture/FASE-1.7-cierre.md).
Las secciones inferiores describen entregas históricas; no son la orden vigente.

## Financial Core — orden vigente 1.6

Monolito modular, repositorios/domain services con FinancialSession y db.get_conn
compartidos. PaymentCapture/BankCapture componen Operations y writers 1.4; no nueva
lógica financiera grande en db.py. Decimal/NUMERIC/TEXT y JSON string. IA propone,
no autoriza. Capturas incluyen cobertura específica, evento(s), vínculo y resultado
en el mismo commit. Match es evidencia, nunca segundo cobro. Cuenta/batch/fila
identifican importaciones sin prometer identidad universal por contenido.
[ADR-010](architecture/ADR-010-payment-bank-capture.md),
[contrato](architecture/PAYMENT-BANK-CAPTURE-v1.md). Flags OFF; no1.7 ni canales.

## Orden vigente — exclusivamente 1.5

Fases 1.1–1.4 aceptadas; solo emisión capturada F1/F2 y rectificativas R1–R5.
Servicio `invoice_capture/`: operaciones/aprobación durable + writer1.4 + evento
v2 + resultado en un commit. Migración65: cobertura inmutable con FKs diferidas;
v1/legacy/fiscalidad conservados. Flags apagados; otros productores y1.6 no autorizados.
[ADR-009](architecture/ADR-009-invoice-capture.md), [API](architecture/INVOICE-CAPTURE-v1.md),
[entradas auditadas](architecture/FASE-1.5-entrada-audit.md). Los alcances inferiores son históricos.

## Escritores prestados — Fase 1.4

`financial_writers/{invoices,payments,purchasing,bank,documents,recurring}` extrae
el núcleo de mutación existente. Fachada db/service posee conexión/BEGIN/commit;
writer recibe Connection/FinancialSession, devuelve WriterResult inmutable y
snapshots leídos dentro de esa transacción. Infraestructura/pool compartidos.
Mig.64: tres revisiones monotónicas, sin migrar REAL/DOUBLE monetario legacy.
Lock por negocio y cadena común fiscal; huellas/XML/QR conservados. No productores
ni flags. [ADR-008](architecture/ADR-008-borrowed-writers.md),
[API](architecture/BORROWED-WRITERS-v1.md). Solo 1.4 autorizada; no avanzar a 1.5.
Las secciones inferiores describen entregas anteriores.

## Economic Events — persistencia 1.3, sin productores

Migración 63: economic_events, economic_event_links y contador mínimo por negocio.
Contrato puro de 1.1 intacto; repositorio sobre FinancialSession prestada; servicio
append/read con permisos/autorización de 1.2, fuentes reales tipadas, revisión
confiable y SAVEPOINT. Commit exterior del llamador. NUMERIC exacto PostgreSQL /
TEXT canónico SQLite; hash del sobre y hash adicional de metadatos. Triggers
append-only, FKs compuestas, slots/uniques y contador serializado. Links sellados
en la incorporación; correction/void son eventos nuevos. Downgrade/baja bloqueados
con evidencia durable. [ADR-007](architecture/ADR-007-economic-persistence.md),
[API y schema](architecture/ECONOMIC-PERSISTENCE-v1.md).
Sin productores, accounting_date, posting, GL, Open Items, Tax Ledger, reporting,
AEAT o flags activados. 1.4 no autorizada. Las secciones inferiores son históricas.

## Operaciones financieras — solo infraestructura 1.2

`financial_operations/` añade contratos, repositorio y servicio sobre db.get_conn
+ FinancialSession, sin otro pool. Reserva unique por negocio/namespace/key,
aprobación mínima durable y resultado con el mismo commit que el ejecutor futuro.
PostgreSQL usa locks de fila; SQLite BEGIN IMMEDIATE. No hay estado executing
persistido ni commit de resultado separado. Reintento tras commit recupera el
resultado, previa revalidación de acceso. [ADR-006](architecture/ADR-006-financial-operations.md)
y [contrato](architecture/FINANCIAL-OPERATIONS-v1.md). Migración 62: solo dos tablas.
La baja legacy no borra evidencia durable: funciona con tablas vacías y rechaza
explícitamente si contienen registros. Retención/cierre quedan pendientes antes de productores.
1.2 no integra productores ni persiste eventos; 1.3 añade solo la capa descrita arriba.

## Financial Core: fundamentos incorporados

[Gobernanza y ADR](architecture/README.md), [guía 08](areas/08-financial-core.md).
Bynoesis es un monolito modular. Los servicios financieros futuros orquestarán
repositorios especializados sobre la misma conexión y transacción existentes:
`db.get_conn() -> FinancialSession -> repositorio(business_id)`.
El servicio posee commit/rollback; los repositorios no abren conexiones paralelas.
`Connection.execute_exact` conserva valores nativos y el camino legacy conserva
su normalización. No se traslada ni amplía lógica financiera grande en `db.py`.

`core/money.py` establece Decimal, EUR y cierre explícito HALF_UP. PostgreSQL
NUMERIC y SQLite TEXT canónico preservan importes; rechazar floats, incluidos JSON.
La IA solo propone y los servicios validados tienen autoridad de ejecución.
Domain/Operational Events y Economic Events son conceptos diferentes: aceptar
un presupuesto o completar un trabajo no produce automáticamente un hecho
financiero. Una regla de negocio posterior deberá justificarlo con evidencia.

Fase 0 incorpora contratos y cinco flags reservados apagados. `accounting/` solo
reserva el paquete. Fase 1.1 añade `economic_events/contracts.py`: once tipos,
payloads/sobre inmutables, canonicalización y hashes, exclusivamente en memoria.
[Contrato v1](architecture/ECONOMIC-EVENTS-v1.md). Sin persistencia ni productores;
no hay General Ledger, migraciones, asientos, nuevas rutas, reporting ni cambios
funcionales VERI*FACTU. El estado vigente se describe en la sección superior.

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
- `web/static/bynoesis-social-card.png` — tarjeta de 1200x630 para la vista previa
  del enlace (Open Graph). Hecha a propósito, sin capturas del panel: la anterior
  enseñaba el nombre de una cuenta y el de un cliente al compartir el enlace.
  Se regenera con `scripts/build_social_card.py`.
- `web/static/vendor/chart.umd.min.js` — Chart.js servido en local.
- `nlu.py` — **cerebro local** por reglas (sin coste/API).
- `web/chat.py` — orquesta reglas → IA privada → IA externa autorizada. Si un nivel
  falla o agota créditos, conserva el acompañamiento local.
- `agent.py` + `tools.py` — agentes privado/externo y acciones multi-negocio. El
  modelo nunca decide por sí solo los permisos ni el aislamiento.
- `adapters/ai.py` — contrato HTTP OpenAI-compatible para Ollama, llama.cpp, vLLM
  u otro servicio privado, sin SDK ni dependencia nueva. Ver [[IA-local]].
- `db.py` — infraestructura compartida de conexiones/transacciones y acceso legacy: Postgres con `DATABASE_URL`, pool de conexiones
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
- `documents/inbound_email.py` + migración 52 — entrada IMAP desde un único
  catch-all. Una dirección opaca resuelve exactamente un `business_id`; mensajes
  sin ruta, con dos rutas o con ruta revocada no entran. Solo se guardan huella,
  estado y contadores, y los adjuntos recorren el servicio documental existente.
  Un cliente extraído se relaciona por NIF/nombre exacto o queda pendiente de una
  confirmación editable; el correo jamás autoriza un asiento ni un alta silenciosa.
- `security_center.py` + `security_events` — parte CISO de solo lectura sobre una
  bitácora append-only y encadenada, sin contenido operativo ni datos de contacto.
- `tests/test_backend.py` — regresiones de aislamiento, facturación, webhooks,
  fiscalidad, NLU y revocación de sesiones.

## Garantías del backend
- El aislamiento se valida en la ruta y de nuevo en el repositorio de dominio o `db.py` legacy; una mutación nunca
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
- Un correo entrante se reclama por `business_id + SHA-256` para que dos réplicas o
  dos reenvíos no dupliquen archivos. El scheduler solo marca como leído un resultado
  definitivo; los fallos transitorios permanecen disponibles para reintento.
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
Trabajador ────┴─> número central Bynoesis
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
