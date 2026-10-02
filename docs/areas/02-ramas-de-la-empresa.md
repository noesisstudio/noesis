# 02 · Ramas de la empresa

## Financial Core — canales capturados

Con el Core activo, los canales financieros pasan por `financial_channels/` y
Capture: identidad de servidor, propuesta congelada, autorización durable antes
de consumir el pending y ejecución idempotente. La IA no autoriza ni recibe
writers/identidades. Con flags OFF permanece legacy no capturado; opt-in explícito
nunca hace fallback. Fuente capturada conserva guards. Recurrentes preparan
borradores sin emitir; CSV se confirma por fila. Documento/OCR no es autoridad.
[Contrato y límites](../architecture/FINANCIAL-CHANNELS-v1.md),
[ADR-012](../architecture/ADR-012-financial-channels.md). Ningún flag activado.


> Léela antes de tocar una pantalla, un portal, `/admin`, la web pública o los
> flujos de alta. Figura 2 del [mapa visual](../02-tecnico/Mapa-Bynoesis.html).

## Qué hace

La empresa tiene cinco ramas. Cada una tiene su propia puerta en el código y su
propio tipo de identidad, y no se mezclan: la sesión del autónomo, la de la
gestoría y la del founder son distintas, y los clientes finales y los trabajadores
entran por enlaces privados sin cuenta.

## Esquema

```text
Bynoesis
├─ Producto ─────────── Autónomo: /b/{id}/… y WhatsApp
│                       Su equipo: /t/{token} y WhatsApp central
│                       Sus clientes: /p/{token}
│                       Su gestoría: /gestoria (cuenta profesional) y /g/{token}
├─ Captación ────────── Web pública, /solicitar-acceso, Cal.com, Facebook
├─ Dirección interna ── /admin: cuentas, CRM, economía, seguridad, soporte, copias
├─ Legal y fiscal ───── Textos legales, Veri*Factu, Stripe (apagados sin S.L.)
└─ Ingeniería ───────── Railway, CI de GitHub, comprobación de producción cada 6 h
```

## Archivos clave

| Rama | Archivos |
|---|---|
| **Autónomo** (panel) | `web/routers/pages.py` sirve `/b/{id}/{apartado}` con una plantilla por pantalla en `web/templates/`; las APIs están en `routers/clients.py`, `invoicing.py`, `finance.py`, `projects.py`, `team.py`, `documents.py`, `assistant.py`, `whatsapp_business.py`. Alta, sesión, Ajustes y suscripción: `routers/account.py` |
| **Equipo** | `routers/portal.py` (`/t/{token}`), `routers/team.py`, `web/work_reports.py`, `clockin_integrity.py` |
| **Clientes finales** | `routers/portal.py` (`/p/{token}`): aceptar presupuestos, descargar facturas |
| **Gestoría** | `routers/gestoria_portal.py` (`/gestoria`: acceso, MFA, recuperación, cartera), `routers/gestoria.py` (lo que el autónomo comparte), `web/gestoria.py` (paquetes), `gestoria_workspace.py`, enlace `/g/{token}` en `portal.py` |
| **Captación** | `routers/pages.py` (web pública, `sitemap.xml`, `robots.txt`, `llms.txt`), `web/public_marketing.py`, `templates/site_*.html` y `landing.html`, formulario en `routers/account.py` (`/solicitar-acceso`), `facebook/` (automatización aparte, no se despliega) |
| **Dirección interna** | `routers/admin.py` (`/admin`, `/admin/cuentas`, `/admin/crm`, `/admin/economia`, `/admin/costes`, `/admin/backups`, `/admin/privacidad`, `/admin/solicitudes`), `sales.py`, `economics.py`, `economics_docs.py`, `security_center.py`, `value_ledger.py` |
| **Legal y fiscal** | Plantillas `privacidad`, `terminos`, `aviso-legal`, `cookies`, `encargado-tratamiento`, `cumplimiento`; `verifactu.py`, `verifactu_client.py`; `adapters/billing.py` y `/webhook/stripe` en `routers/webhooks.py` |
| **Ingeniería** | `.github/workflows/ci.yml`, `production-smoke.yml`, `production_check.py`, `readiness.py` (`noesis-doctor`), `integration_check.py`, `scripts/check_project_truth.py`, `scripts/check_secrets.py` |

## Reglas que no se rompen

1. **Las identidades no se mezclan.** Una gestoría nunca obtiene acceso a un negocio
   por sí misma: hace falta invitación explícita del autónomo. El founder no opera
   negocios ajenos; el soporte usa permisos con caducidad que concede el titular.
2. **`/admin` exige Google** en producción (`NOESIS_ADMIN_REQUIRE_GOOGLE_OAUTH`); sin
   credenciales queda cerrado, pero el resto de la app sigue funcionando.
3. **El plan se comprueba en servidor** (`adapters/billing.py`, `has_entitlement`),
   igual en web, API, WhatsApp, portales y reloj.
4. **Los enlaces privados son secretos.** No se registran ni se reenvían en soporte, y
   sus respuestas llevan `no-store`.
5. **Web pública:** un solo `h1` por página, título y descripción únicos, y solo las
   rutas de `INDEXABLE_PATHS` (`routers/pages.py`) se indexan; el resto recibe
   `noindex`. Nada de CDNs en tiempo de ejecución.
6. **El alta pública está cerrada** hasta tener identidad legal: `/onboarding` lleva a
   `/solicitar-acceso` y el founder aprueba cada solicitud.
7. **Diseño y textos:** antes de tocar una pantalla, lee
   [`docs/design/`](../design/). Bynoesis da el parte del día; no es un dashboard.

## Estado real (28-sep-2026)

- Funcionan: panel, portales `/p`, `/t`, `/g`, portal de gestorías con MFA, web
  pública (14 páginas indexables), solicitud de acceso,
  `/admin` con CRM y economía, CI y comprobación externa cada 6 h.
- Apagado o bloqueado: alta pública, Stripe, Veri*Factu y número de WhatsApp de cada
  negocio (identidad legal y verificación de Meta); Facebook sin conectar la página.

## Pruebas que lo cubren

`test_public_marketing`, `test_seo`, `test_page_views`, `test_access_requests`,
`test_gestoria_mfa`, `test_gestoria_password_recovery`, `test_field_workflow`,
`test_admin_workspace`, `test_admin_usage`, `test_economia_panel`,
`test_crm_captacion`, `test_showcase_and_pdf_ocr`, `test_facebook`, y las pruebas de
JavaScript `tests/*.test.cjs` (`node --test`).

## Al revisar código de esta zona

- [ ] ¿La ruta nueva pasa por la guardia correcta (`/b/` y `/api/` con sesión y
      `business_id`; portales con token; `/admin` con administrador)?
- [ ] ¿Una pantalla nueva respeta el modo consulta y el plan?
- [ ] ¿La página pública nueva está en `INDEXABLE_PATHS` si debe indexarse, y fuera si
      no (confirmaciones de formularios, `/bienvenida`)?
- [ ] ¿La CSP de `web/server.py` necesita un origen nuevo? Solo por página y con
      permiso explícito (como Cal.com en `/contacto`).
- [ ] ¿Los textos siguen `docs/design/UX_COPY.md`, sin jerga interna?

## Dudas frecuentes

- **¿El CRM del founder y el del autónomo son el mismo?** No: `/admin/crm` es el embudo
  de la empresa (`sales.py`, sin `business_id`); `/b/{id}/crm` es el del autónomo.
- **¿Hay demo pública?** Sí, con `NOESIS_SEED_DEMO`: cuentas reales de solo lectura
  (`demo.py`, [`Demo-comercial`](../01-producto/Demo-comercial.md)).

## Más detalle

[`Como-funciona-la-empresa`](../06-negocio-y-finanzas/Como-funciona-la-empresa.md) ·
[`Producto`](../01-producto/Producto.md) ·
[`Permisos-y-acceso.pdf`](../04-seguridad-y-datos/Permisos-y-acceso.pdf) ·
[`Gestoria-y-App`](../01-producto/Gestoria-y-App.md)
