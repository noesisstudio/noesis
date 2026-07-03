# Arquitectura

Objetivo: máximo posible **interno/cerrado**, mínimo de APIs externas (coste y
privacidad). Ver [[Investigación]] y [[Decisiones]].

## Diagrama mental
```
WhatsApp / Web / App  ─►  Cerebro  ─►  Herramientas  ─►  Base de datos
                            │
                  (local: nlu.py, gratis)
                  (IA opcional: Claude, solo lo complejo)
                            │
                            └─►  Facturación (mock → Holded API)
```

## Piezas (código en `src/noesis/`)
- `web/server.py` — FastAPI: páginas, API JSON, login, onboarding, webhook.
- `web/templates/landing.html` — página pública de producto en `/` con CTA a login/registro.
- `web/static/app.css` — sistema de diseño propio (sin Tailwind ni CDNs).
- `web/static/noesis-product-preview.png` — captura real del panel usada como visual de producto.
- `web/static/vendor/chart.umd.min.js` — Chart.js servido en local.
- `nlu.py` — **cerebro local** por reglas (sin coste/API).
- `web/chat.py` — orquesta: local primero, IA (Claude) de respaldo.
- `agent.py` + `tools.py` — agente IA y acciones (multi-negocio).
- `db.py` — frontera única de datos: Postgres con `DATABASE_URL` y SQLite local como
  fallback.
- `migrations.py` — esquema versionado con subida/bajada; Railway lo aplica en
  pre-deploy.
- `web/whatsapp.py` — entrada idempotente y cola durable de salida. Persiste antes
  de enviar, reintenta con backoff y aplica estados `sent/delivered/read` de Meta.
- `web/scheduler.py` — genera los proactivos con plantillas aprobadas y ejecuta el
  worker de la cola cada 15 segundos.
- `db.py` también persiste eventos de producto y calcula el recorrido de activación
  por negocio sin depender de una plataforma analítica externa.
- `adapters/invoicing.py` — selecciona emisión interna o Holded. Cuando un negocio
  activa el modo nativo, la emisión interna registra Veri*Factu en la misma
  transacción y no delega en terceros. Ver [[Fiscalidad]].
- `verifactu.py` — formato técnico AEAT: cadena de huella, SHA-256, URL/QR y XML.
- `web/auth.py` — login (PBKDF2, sesiones firmadas). Aislamiento por dueño.
- `tests/test_backend.py` — regresiones de aislamiento, facturación, webhooks,
  fiscalidad, NLU y revocación de sesiones.

## Garantías del backend
- El aislamiento se valida en la ruta y de nuevo en `db.py`; una mutación nunca
  devuelve una entidad de otro `business_id`.
- `business_id` es obligatorio en todo acceso operativo. Las FKs compuestas
  `(business_id, id)` impiden enlazar un trabajo, factura, presupuesto o documento
  con entidades de otra empresa.
- La emisión de factura es atómica e idempotente. La secuencia se persiste por
  negocio/año y los datos fiscales quedan congelados en la factura.
- Los cobros viven en `invoice_payments`: el estado y el importe restante se
  derivan del ledger. Cada alta bloquea la factura (`BEGIN IMMEDIATE` en SQLite,
  `FOR UPDATE` en Postgres) para impedir que dos cobros superen el total.
- En modo Veri*Factu, la misma transacción añade un registro de alta append-only,
  encadenado por NIF emisor. Las rectificaciones crean una nueva factura R1-R5 y
  conservan el original.
- Facturas emitidas no se borran ni se renumeran. Los borrados RGPD conservan los
  documentos sujetos a obligación fiscal.
- Los webhooks de WhatsApp y Stripe verifican firma y deduplican IDs. Los eventos
  de estado de WhatsApp reutilizan `webhook_events`, por lo que una entrega repetida
  no vuelve a producir efectos.
- Las sesiones se revocan al cambiar contraseña; las cuentas sin suscripción activa
  solo conservan acceso a pago, exportación y baja.
- El scheduler registra cada ejecución para evitar duplicados entre réplicas. La
  outbox de WhatsApp usa claves idempotentes y `FOR UPDATE SKIP LOCKED` en Postgres
  para que varias réplicas no envíen la misma fila.
- `/health` comprueba que el proceso responde y `/ready` que la versión de esquema
  esperada está aplicada y la base de datos disponible.
- Los eventos de producto se almacenan siempre con `business_id`. La activación se
  deriva de datos operativos reales, no de clics o páginas visitadas.

## Flujo SaaS de alta
```
Cuenta → perfil operativo → WhatsApp → panel
                              │
                              └─► recorrido: cliente → trabajo → factura → cobro
```

El alta recoge sector, tamaño del equipo, provincia y objetivo principal. Estos
campos permiten segmentar activación, retención y conversión sin mezclar negocios ni
exponer información personal en herramientas de terceros.

Detalle y pendientes: [[Backend_Hardening]].

## Principios
- Datos en infraestructura propia/gestionada; solo el LLM (si se activa) sale fuera.
- Dependencias mínimas (hash con stdlib, no librerías pesadas).
- Adaptadores: cambiar de proveedor = cambiar 1 archivo.

Qué falta técnicamente: ver [[Roadmap]].
