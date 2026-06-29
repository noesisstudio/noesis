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
- `db.py` — SQLite (multi-tenant). Futuro: Postgres/Supabase.
- `adapters/invoicing.py` — facturación: mock hoy → Holded mañana. Ver [[Fiscalidad]].
- `web/auth.py` — login (PBKDF2, sesiones firmadas). Aislamiento por dueño.
- `tests/test_backend.py` — regresiones de aislamiento, facturación, webhooks,
  fiscalidad, NLU y revocación de sesiones.

## Garantías del backend
- El aislamiento se valida en la ruta y de nuevo en `db.py`; una mutación nunca
  devuelve una entidad de otro `business_id`.
- La emisión de factura es atómica e idempotente. La secuencia se persiste por
  negocio/año y los datos fiscales quedan congelados en la factura.
- Facturas emitidas no se borran ni se renumeran. Los borrados RGPD conservan los
  documentos sujetos a obligación fiscal.
- Los webhooks de WhatsApp y Stripe verifican firma y deduplican IDs.
- Las sesiones se revocan al cambiar contraseña; las cuentas sin suscripción activa
  solo conservan acceso a pago, exportación y baja.
- El scheduler registra cada ejecución para evitar duplicados entre réplicas.

Detalle y pendientes: [[Backend_Hardening]].

## Principios
- Datos en local; solo el LLM (si se activa) sale fuera.
- Dependencias mínimas (hash con stdlib, no librerías pesadas).
- Adaptadores: cambiar de proveedor = cambiar 1 archivo.

Qué falta técnicamente: ver [[Roadmap]].
