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
     `STRIPE_PRICE_AUTONOMO` y `STRIPE_PRICE_PRO`.
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

## Seguridad ya implementada
- Aislamiento por `business_id` en BD, rutas `/b/` y `/api/`, y onboarding.
- Contraseñas con PBKDF2 (stdlib). Sesiones firmadas con `NOESIS_SECRET`.
- Cada autónomo es un negocio independiente: sus datos no se cruzan con los demás.
