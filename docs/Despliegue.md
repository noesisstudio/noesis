# Despliegue 24/7

Objetivo: tener **bynoesis.com** online, con HTTPS, para enseñarlo a autónomos e
inversores. Ver fases en [[Roadmap]].

## Recomendación: Railway

Por qué Railway sobre Render para empezar: arranque más simple desde el repo de
GitHub, **volumen persistente** barato (clave para que no se borren los datos) y
escala bien al principio. Coste estimado: ~5 €/mes.

### Pasos (los hace el founder; el código ya está preparado)
1. Crear cuenta en [railway.app](https://railway.app) con el GitHub de Noesis.
2. **New Project → Deploy from GitHub repo** → elegir `noesisstudio/noesis`.
3. Railway detecta `railway.json`: ejecuta las migraciones en pre-deploy, arranca
   Uvicorn y usa `/ready` como healthcheck.
4. **Variables de entorno** (Settings → Variables):
   - `NOESIS_SECRET` → una cadena larga y aleatoria (firma las sesiones; **obligatoria**).
   - `NOESIS_BASE_URL` → `https://bynoesis.com` cuando el dominio propio esté
     conectado. Mientras tanto se usa automáticamente `RAILWAY_PUBLIC_DOMAIN`.
   - `HOST` → `0.0.0.0`
   - `DATABASE_URL` → referencia `${{Postgres.DATABASE_URL}}` del servicio Postgres.
   - `NOESIS_DOCS_PATH` → `/data/uploads` (los documentos/papeles subidos van también
     al volumen; si no, se borrarían en cada despliegue).
   - `ANTHROPIC_API_KEY` → opcional (solo si se quiere IA en el chat; sin ella va el
     cerebro local gratis).
   - Al activar WhatsApp: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`,
     `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` y `NOESIS_WHATSAPP_NUMBER`.
   - Al activar Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
     `STRIPE_PRICE_AUTONOMO`, `STRIPE_PRICE_PRO` y `STRIPE_PRICE_PREMIUM`
     (guía paso a paso en la sección "Activar Stripe" de abajo).
   - Email (SMTP): `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`.
   - Facturación legal: `HOLDED_API_KEY` (cuando se active Verifactu vía Holded).
   - `PORT` lo inyecta Railway automáticamente.
5. **Volumen persistente**: se mantiene montado en `/data` para documentos, modelos
   y la copia histórica de SQLite. La base operativa vive en Postgres.
6. **Dominio**: Settings → Networking → Custom Domain → `bynoesis.com`, y apuntar el
   DNS según indique Railway. HTTPS es automático.

## Activación de Postgres (solo tras aprobar el PR)
1. En el servicio web, pestaña **Backups**, crea y bloquea un backup manual del
   volumen que contiene `/data/noesis.db`. No cambies aún ninguna variable.
2. Añade un servicio PostgreSQL gestionado al mismo proyecto y entorno. Debe empezar
   limpio: esta migración no importa datos reales automáticamente.
3. En el servicio web, define `DATABASE_URL=${{Postgres.DATABASE_URL}}`. Conserva el
   volumen y `NOESIS_DB_PATH=/data/noesis.db` hasta verificar la transición.
4. Fusiona el PR. El `preDeployCommand` ejecuta
   `python -m noesis.migrations upgrade`; si falla, Railway no inicia el despliegue.
5. Comprueba `/health`, `/ready`, alta/login y aislamiento con dos negocios. Solo
   después retira la variable SQLite que ya no haga falta.

Para desarrollo y tests, si `DATABASE_URL` está vacía se usa SQLite. Sus migraciones
se aplican con `python -m noesis.migrations upgrade`; se pueden revertir con
`python -m noesis.migrations downgrade <versión>`.

## Checklist antes de exponer
- [ ] `NOESIS_SECRET` puesta y aleatoria (nunca la de por defecto).
- [ ] `NOESIS_BASE_URL` usa el dominio HTTPS definitivo.
- [ ] Backup manual bloqueado del volumen SQLite anterior.
- [ ] Postgres limpio enlazado mediante `DATABASE_URL`.
- [ ] Migración pre-deploy en versión actual y `/ready` en 200.
- [ ] Volumen mantenido para `NOESIS_DOCS_PATH` y otros ficheros.
- [ ] `NOESIS_BACKUP_DIR` apunta al volumen persistente.
- [ ] Si WhatsApp está activo, `WHATSAPP_APP_SECRET` está configurado.
- [ ] Si Stripe está activo, `STRIPE_WEBHOOK_SECRET` está configurado.
- [ ] Probar alta de un autónomo nuevo y confirmar que NO ve datos de otro.
- [ ] Página de privacidad/términos (RGPD) antes de meter datos reales de clientes.
- [ ] Quitar/!proteger el negocio y usuario demo si se considera necesario.

## Activar Stripe (cobro real, ~20 minutos)
El código ya está listo: checkout, portal de cliente y webhook firmado e idempotente.
Solo falta la configuración en stripe.com:

1. **Cuenta**: dashboard.stripe.com → activar la cuenta (datos fiscales de la empresa
   e IBAN donde recibir los pagos).
2. **Productos**: Catálogo → añadir 3 productos con precio recurrente mensual en EUR:
   Autónomo 29 €, Negocio 39 €, Sin Límites 79 €. Copiar los `price_...` de cada uno.
3. **Variables en Railway** (servicio web → Variables):
   - `STRIPE_SECRET_KEY` → clave secreta de producción (`sk_live_...`).
   - `STRIPE_PRICE_AUTONOMO`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_PREMIUM` → los `price_...`.
4. **Webhook**: Desarrolladores → Webhooks → añadir endpoint
   `https://bynoesis.com/webhook/stripe` con los eventos `checkout.session.completed`,
   `customer.subscription.created`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `invoice.paid` e `invoice.payment_failed`.
   Copiar el "signing secret" (`whsec_...`) a `STRIPE_WEBHOOK_SECRET`.
5. **Portal de cliente**: Configuración → Billing → Customer portal → activar
   (permite al cliente cambiar de plan, tarjeta y cancelar solo).
6. **Prueba**: antes de las claves live, repetir 2-4 en modo test (`sk_test_...`),
   pagar con la tarjeta `4242 4242 4242 4242` y comprobar que la cuenta pasa a
   "Suscripción activa" en `/b/{id}/suscripcion` y que el MRR aparece en `/admin`.

Sin estas variables, el alta sigue funcionando en modo manual (el interés queda
registrado como evento `checkout_started` y se activa el plan a mano).

## Seguridad ya implementada
- Aislamiento por `business_id` en BD, rutas `/b/` y `/api/`, y onboarding.
- Contraseñas con PBKDF2 (stdlib). Sesiones firmadas con `NOESIS_SECRET`.
- Cada autónomo es un negocio independiente: sus datos no se cruzan con los demás.
