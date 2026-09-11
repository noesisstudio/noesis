# Fase 2 — De producto a negocio

Construido sobre la base multi-tenant. Todo respeta el aislamiento por `business_id`
y degrada con elegancia cuando falta una clave externa (mismo patrón que WhatsApp/Whisper).

## Qué se ha añadido

| Función | Dónde | Estado |
|---|---|---|
| **Presupuestos** (oferta → aceptar → factura) | `Presupuestos`, chat/WhatsApp | ✅ activo |
| **Recordatorios de cobro** automáticos | scheduler 09:00 → WhatsApp | ✅ (envía al activar WhatsApp) |
| **Impuestos trimestrales** (IVA 303 + IRPF 130) | `Impuestos` | ✅ activo |
| **Exportar** facturas/costes (CSV) y cuenta entera (JSON) | `Ajustes` | ✅ activo |
| **Copias de seguridad** diarias de la BD | scheduler 03:30, volumen | ✅ activo |
| **Recuperar contraseña** por email | `/recuperar` | ✅ (email real al poner SMTP) |
| **Panel de administración** (fundador) | `/admin` | ✅ (acceso por `NOESIS_ADMIN_EMAIL`) |
| **RGPD**: exportar/olvidar por cliente y baja de cuenta | `Clientes`, `Ajustes` | ✅ activo |
| **Suscripción de pago** (Stripe) | `Suscripción` | ⏳ se activa con claves Stripe |

## Lo que necesita configuración del fundador

- **Stripe** (cobrar de verdad): `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
  `STRIPE_PRICE_AUTONOMO`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_PREMIUM` y sus tres
  equivalentes `_ANNUAL`.
  Webhook → `POST /webhook/stripe`. Guía paso a paso: `docs/02-tecnico/Despliegue.md`,
  sección "Activar Stripe". Sin esto, el alta entra en prueba y el cobro se
  gestiona a mano.
- **Email** (reset de contraseña): `SMTP_HOST/PORT/USER/PASS/FROM`. Sin esto, el
  enlace de reset se registra en el log (sirve para probar).
- **Admin**: `NOESIS_ADMIN_EMAIL` con tu email para entrar en `/admin`.
- **WhatsApp**: número de Meta + tokens (desbloquea recordatorios y avisos por WhatsApp).
- **`NOESIS_BASE_URL`**: la URL pública real (enlaces de email y vueltas de pago).

## Notas de diseño

- Modelos 303/130 son **cifras de apoyo** para el gestor, no presentación oficial.
- Stripe y email se hablan por HTTPS/SMTP con la **stdlib** (sin dependencias nuevas).
- Las facturas siguen teniendo serie correlativa por negocio; los presupuestos usan
  serie propia `P{año}/{NNNN}`.
- El "olvido" elimina agenda, borradores y datos operativos, pero conserva la
  instantánea fiscal de facturas emitidas. La baja automática se bloquea si existen
  facturas sujetas a conservación y debe tramitarse como baja con retención fiscal.
- WhatsApp exige `WHATSAPP_APP_SECRET` en producción y deduplica cada `message.id`.
- La facturación es nativa de Bynoesis: ningún SaaS externo recibe las facturas ni
  controla su numeración o registro Veri*Factu.
