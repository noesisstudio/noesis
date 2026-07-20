# Conexión de servicios externos

> Guía operativa única para conectar producción. Describe lo que acepta el código
> actual; no convierte una integración en «publicada» hasta completar su prueba real.
> Los secretos se guardan en Railway o en el gestor del proveedor, nunca en Git.
> Estado general: [[Estado-actual-main]]. Orden vivo: [[Tareas-vivas]].

## Resumen ejecutivo

| Servicio | Estado del código | Acción externa | Prioridad | ¿Activar ya? |
|---|---|---|---|---|
| PostgreSQL / Railway | Construido y usado | Desplegar `main`, migrar y verificar | P0 | Sí |
| SMTP | Outbox durable construida | Crear credenciales y autenticar dominio | P0 | Sí |
| Google OAuth | Alta y acceso construidos | Crear cliente web OAuth | P0 | Sí |
| Stripe Billing | Checkout, portal y webhook construidos | Crear 6 precios y webhook | P0 | Solo test hasta cerrar el IVA |
| Meta WhatsApp Cloud API | Entrada, salida, firma y reintentos construidos | Verificar empresa/número y plantillas | P0 | Sí, primero con número de prueba |
| IA avanzada | Enrutamiento y consentimiento construidos | Elegir al menos un proveedor | P0 | Sí, con límites de gasto |
| Groq Whisper | Adaptador de audio construido | Crear una API key | P0/P1 | Sí si no se sirve Whisper local |
| Copia S3-compatible | Subida firmada construida | Crear bucket y credenciales | P0 | Sí |
| AEAT Veri*Factu | SOAP/mTLS y cola construidos | Certificado, NIF y entorno de pruebas | P0 | Solo `pruebas` hasta auditoría |

No hay que contratar todas las IAs. Para el piloto basta con conservar el cerebro
local y conectar **un** respaldo avanzado fiable. Groq Whisper es otra integración:
transcribe audio y no sustituye al modelo que razona o redacta.

## 0. Base de producción

Antes de cualquier proveedor:

```dotenv
NOESIS_ENV=production
NOESIS_HTTPS=true
NOESIS_BASE_URL=https://app.bynoesis.com
NOESIS_SECRET=<cadena larga y aleatoria>
NOESIS_ADMIN_EMAIL=<correo del founder>
DATABASE_URL=${{Postgres.DATABASE_URL}}
NOESIS_DOCS_PATH=/data/uploads
NOESIS_BACKUP_DIR=/data/backups
NOESIS_SEED_DEMO=false
NOESIS_RESET_DB=false
```

Railway inyecta `PORT`, `RAILWAY_ENVIRONMENT` y `RAILWAY_PUBLIC_DOMAIN`. Tras el
despliegue hay que aplicar la versión de esquema indicada en
[`project-state.json`](project-state.json), comprobar `GET /health`, `GET /ready`
y ejecutar `noesis-doctor --strict`. Nunca activar `NOESIS_RESET_DB` con datos.

## 1. Correo por SMTP

### Qué crear

Una cuenta transaccional en un proveedor con SMTP (por ejemplo, Postmark, Brevo,
Mailgun, Amazon SES o el SMTP corporativo) y un remitente del dominio de Noesis.
El código actual habla SMTP; una clave para la API REST del proveedor no sirve.

```dotenv
SMTP_HOST=<host SMTP>
SMTP_PORT=587
SMTP_USER=<usuario SMTP>
SMTP_PASS=<contraseña SMTP>
SMTP_FROM=Noesis <no-reply@bynoesis.com>
```

El adaptador usa STARTTLS. En DNS hay que publicar SPF y DKIM según el proveedor y
añadir DMARC antes de escalar envíos.

### Prueba de aceptación

- Recuperación de contraseña.
- Invitación de gestoría y envío confirmado de factura/documentación.
- Reintento de un fallo temporal desde la outbox sin duplicar el mensaje.
- Recepción en Gmail y Outlook sin caer en spam; revisar SPF, DKIM y DMARC.

## 2. Acceso con Google

### Qué crear

En Google Cloud, crear un cliente **OAuth 2.0 de aplicación web**, configurar la
pantalla de consentimiento y registrar exactamente:

- Origen autorizado: `https://app.bynoesis.com`
- URI de redirección: `https://app.bynoesis.com/auth/google/callback`
- Scopes usados por Noesis: `openid email profile`

```dotenv
GOOGLE_OAUTH_CLIENT_ID=<client id>
GOOGLE_OAUTH_CLIENT_SECRET=<client secret>
```

Google exige que la URI coincida exactamente, incluido protocolo y barra final.
Noesis oculta el botón si falta una de las dos variables.

### Prueba de aceptación

- Alta nueva por Google desde prueba mensual.
- Alta nueva por Google desde contratación anual y vuelta correcta al onboarding.
- Acceso a una cuenta ya existente con el mismo correo verificado.
- Cancelación del consentimiento y `state` inválido sin iniciar sesión.

Referencia: [OpenID Connect de Google](https://developers.google.com/identity/openid-connect/openid-connect).

## 3. Stripe Billing — suscripción de Noesis

Stripe aquí cobra **la suscripción SaaS de Noesis**. No cobra las facturas que el
autónomo emite a sus clientes y no es todavía un «cobro por enlace».

### Bloqueo previo: IVA

El catálogo se comunica como **29 / 49 / 99 EUR + IVA**, pero el Checkout actual
solo envía el `price_id`: no activa `automatic_tax` ni añade una tasa fiscal. Por
eso, antes de usar claves `live` hay que elegir y probar una solución coherente:

1. recomendada: añadir Stripe Tax al Checkout, recopilar la dirección necesaria y
   validar factura/IVA intracomunitario; o
2. crear precios con IVA incluido y cambiar todo el copy comercial que dice `+ IVA`.

Hasta resolverlo, Stripe se conecta y prueba **en modo test**, no se cobra a un
cliente real. Stripe documenta que Checkout solo calcula impuestos automáticamente
cuando se habilita `automatic_tax`.

### Qué crear

Tres productos y dos precios recurrentes EUR por producto:

| Plan | Mensual sin IVA | Anual sin IVA |
|---|---:|---:|
| Autónomo | 29 EUR | 319 EUR |
| Negocio | 49 EUR | 539 EUR |
| Sin Límites | 99 EUR | 1.089 EUR |

```dotenv
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_AUTONOMO=price_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_PREMIUM=price_...
STRIPE_PRICE_AUTONOMO_ANNUAL=price_...
STRIPE_PRICE_PRO_ANNUAL=price_...
STRIPE_PRICE_PREMIUM_ANNUAL=price_...
```

Crear el webhook `https://app.bynoesis.com/webhook/stripe` con:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

Activar también el Customer Portal en Stripe. No reutilizar secretos de test en
live ni confundir la clave secreta con la publicable.

### Prueba de aceptación

- Checkout mensual y anual de los tres planes.
- Importe, moneda, IVA y factura correctos.
- Alta activa solo después del evento firmado.
- Renovación, impago, reactivación, cancelación y portal de cliente.
- Reenvío del mismo evento sin duplicar efectos.

Referencias: [SaaS con Stripe](https://docs.stripe.com/saas),
[webhooks de suscripciones](https://docs.stripe.com/billing/subscriptions/webhooks).

## 4. Meta WhatsApp Cloud API

### Qué crear

En Meta Business / Meta for Developers:

1. verificar la empresa y crear una app con WhatsApp;
2. añadir o portar el número único de Noesis;
3. generar un token permanente con los permisos necesarios;
4. configurar el webhook y suscribir el campo `messages`;
5. aprobar las plantillas proactivas en español.

Callback: `https://app.bynoesis.com/webhook/whatsapp`  
Verify token: el mismo valor aleatorio que `WHATSAPP_VERIFY_TOKEN`.

```dotenv
NOESIS_WHATSAPP_NUMBER=34XXXXXXXXX
WHATSAPP_TOKEN=<token permanente>
WHATSAPP_PHONE_ID=<phone number id>
WHATSAPP_VERIFY_TOKEN=<secreto aleatorio propio>
WHATSAPP_APP_SECRET=<app secret de Meta>
META_GRAPH_VERSION=<versión soportada que se haya validado>
```

Plantillas que deben coincidir exactamente con las aprobadas:

```dotenv
WHATSAPP_TEMPLATE_LANGUAGE=es
WHATSAPP_TEMPLATE_DAILY_SUMMARY=noesis_resumen_diario
WHATSAPP_TEMPLATE_WEEKLY_SUMMARY=noesis_resumen_semanal
WHATSAPP_TEMPLATE_PAYMENT_ALERT=noesis_aviso_cobros
WHATSAPP_TEMPLATE_PAYMENT_REMINDER=noesis_recordatorio_cobro
WHATSAPP_TEMPLATE_INVOICE=noesis_factura_lista
WHATSAPP_TEMPLATE_QUOTE_FOLLOWUP=noesis_seguimiento_presupuesto
WHATSAPP_TEMPLATE_APPOINTMENT_REMINDER=noesis_recordatorio_cita
WHATSAPP_TEMPLATE_DAILY_CLOSING=noesis_cierre_dia
WHATSAPP_TEMPLATE_TAX_NOTICE=noesis_aviso_fiscal
```

La firma `X-Hub-Signature-256` es obligatoria en producción. El texto libre solo
se usa dentro de la ventana de atención; fuera de ella se usan plantillas.

### Prueba de aceptación

- Verificación GET del webhook y rechazo de firma falsa.
- Vinculación del titular y de un trabajador con código de un solo uso.
- Texto, audio, imagen de ticket, PDF/factura recibida y ticket de venta F2.
- Confirmación antes de crear gasto, emitir o enviar algo irreversible.
- Emisión confirmada, PDF generado y entrega por email o plantilla
  `noesis_factura_lista` con enlace privado sin duplicar la factura.
- Estados `sent`, `delivered`, `read` y fallo; reintento sin duplicados.
- Factura lista, recordatorio de cobro, presupuesto, cita, cierre diario y aviso fiscal.
- Cuenta caducada en modo consulta: no ejecuta acciones ni automatizaciones.

Referencia: [colección oficial de Meta para WhatsApp Business Platform](https://www.postman.com/meta/whatsapp-business-platform/overview).

## 5. IA avanzada: elegir una ruta, no todas

El orden real es: reglas locales → compositor interno → servicio privado compatible
→ proveedor externo compatible → Anthropic. Cada negocio debe consentir la salida
externa de datos. Las transferencias, emisiones, mensajes sensibles y decisiones
fiscales siguen necesitando confirmación del titular aunque responda una IA.

### Opción A — Anthropic como respaldo inicial

```dotenv
ANTHROPIC_API_KEY=<secreto>
NOESIS_MODEL=<modelo principal validado>
NOESIS_MODEL_INPUT_USD_PER_MTOK=<tarifa vigente>
NOESIS_MODEL_OUTPUT_USD_PER_MTOK=<tarifa vigente>
NOESIS_FALLBACK_MODEL=<modelo económico validado>
NOESIS_FALLBACK_INPUT_USD_PER_MTOK=<tarifa vigente>
NOESIS_FALLBACK_OUTPUT_USD_PER_MTOK=<tarifa vigente>
NOESIS_MAX_DAILY_EXTRACTIONS=30
```

No copiar tarifas antiguas sin verificarlas. Configurar presupuesto y alertas en el
proveedor. Referencia: [autenticación de Claude API](https://platform.claude.com/docs/en/manage-claude/authentication).

### Opción B — proveedor externo OpenAI-compatible

```dotenv
NOESIS_COMPAT_AI_BASE_URL=https://<proveedor>/v1
NOESIS_COMPAT_AI_MODEL=<id exacto>
NOESIS_COMPAT_AI_API_KEY=<secreto>
NOESIS_COMPAT_AI_PROVIDER=<slug>
NOESIS_COMPAT_AI_LEGAL_NAME=<razón social>
NOESIS_COMPAT_AI_REGION=<región y salvaguarda de transferencia>
NOESIS_COMPAT_AI_INPUT_USD_PER_MTOK=<tarifa vigente>
NOESIS_COMPAT_AI_OUTPUT_USD_PER_MTOK=<tarifa vigente>
```

La URL externa debe ser HTTPS. Antes de usarla hay que revisar contrato de
tratamiento, región, retención de prompts y si el modelo soporta correctamente las
herramientas de Noesis.

### Opción C — servicio privado compatible

```dotenv
NOESIS_LOCAL_AI_BASE_URL=http://<servicio-interno>:<puerto>/v1
NOESIS_LOCAL_AI_MODEL=<modelo servido>
NOESIS_LOCAL_AI_API_KEY=<secreto interno si aplica>
NOESIS_LOCAL_AI_TIMEOUT_SECONDS=45
```

Puede ser Ollama, llama.cpp o vLLM. No debe apuntar a `localhost` si el modelo vive
en otro servicio de Railway: hay que usar su red privada. La carpeta `deploy/local-ai/`
es una base de despliegue, no una prueba de capacidad. Validar calidad, herramientas,
latencia, concurrencia, RAM y caídas con el corpus real ES/CA.

### Prueba de aceptación común

- Preguntas reales de agenda, dinero, documentos, clientes y proyectos.
- Herramientas correctas y aislamiento entre dos negocios.
- Respuestas en ES/CA según preferencia.
- Caída del proveedor: continúa el cerebro local y no se pierde la conversación.
- Coste y tokens visibles por negocio; límite diario y mensual efectivo.

## 6. Audio: Groq Whisper o transcripción local

Si Railway no tiene memoria suficiente para `faster-whisper`, conectar Groq:

```dotenv
GROQ_API_KEY=<secreto>
GROQ_WHISPER_MODEL=whisper-large-v3-turbo
```

Probar audio corto/largo, catalán/castellano, silencio, formato no admitido y límite
de tamaño. Si se usa local, instalar el extra `audio`, persistir el modelo en
`NOESIS_WHISPER_DIR` y no hace falta una API. Referencia:
[Speech to Text de Groq](https://console.groq.com/docs/speech-to-text).

## 7. Backups externos S3-compatible

Crear un bucket privado con usuario limitado a ese bucket y, si el proveedor lo
permite, versionado, cifrado y política de retención.

```dotenv
NOESIS_BACKUP_S3_ENDPOINT=https://<endpoint>
NOESIS_BACKUP_S3_BUCKET=<bucket>
NOESIS_BACKUP_S3_ACCESS_KEY=<access key>
NOESIS_BACKUP_S3_SECRET_KEY=<secret key>
NOESIS_BACKUP_S3_REGION=<región>
NOESIS_BACKUP_S3_PREFIX=noesis
```

Una subida correcta no basta: restaurar base y documentos en un entorno aislado,
comprobar hashes y registrar RPO/RTO y tiempo real de recuperación.

## 8. AEAT Veri*Factu

No usa una API key. Usa SOAP con autenticación mTLS mediante certificado y clave PEM.
Primero se valida contra el portal de pruebas de la AEAT y con asesoría fiscal.

```dotenv
NOESIS_VERIFACTU_PRODUCER_NAME=Noesis
NOESIS_VERIFACTU_PRODUCER_NIF=<NIF real del productor>
NOESIS_VERIFACTU_SYSTEM_NAME=Noesis
NOESIS_VERIFACTU_SYSTEM_ID=NO
NOESIS_VERIFACTU_SYSTEM_VERSION=<versión publicada>
VERIFACTU_CERT_PATH=/data/secrets/verifactu-cert.pem
VERIFACTU_KEY_PATH=/data/secrets/verifactu-key.pem
VERIFACTU_KEY_PASSWORD=<solo si la clave PEM está cifrada>
VERIFACTU_CERT_TYPE=persona
VERIFACTU_AEAT_ENV=pruebas
NOESIS_VERIFACTU_MAX_RESPONSE_BYTES=2097152
```

Los PEM deben montarse como archivos privados persistentes; no se pegan en Git ni
en un campo que el código espera que sea una ruta. Usar `VERIFACTU_CERT_TYPE=sello`
solo con un certificado de sello: Noesis seleccionará los endpoints oficiales
`prewww10/www10`; `persona` usa `prewww1/www1`. La autorización del certificado para
remitir por cada obligado tributario debe verificarse con asesoría.

Antes del primer envío comprobar que la migración 33 está aplicada y que no hay
duplicados históricos. Probar aceptación, rechazo,
aceptación con errores, reintento, CSV y conservación append-only. Solo pasar a
`produccion` después de validación técnica, fiscal y del certificado.

La prueba debe incluir también: timeout después de una aceptación y reenvío
duplicado, SOAP Fault, respuesta sobredimensionada, cadena alterada, reloj del
servidor, anulación, subsanación y restauración desde copia. Una suscripción SaaS
cancelada no puede detener una remisión fiscal ya encolada.

Referencia: [esquemas y WSDL oficiales de la AEAT](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/informacion-tecnica/esquemas.html).

## 9. Servicios que no forman parte de la arquitectura

Noesis **no se conecta a Holded ni delega la facturación**. Numeración, emisión, PDF,
registro Veri*Factu, cola y remisión AEAT son desarrollo propio. Holded puede seguir
apareciendo en documentos de mercado como competidor o referencia visual, nunca como
proveedor técnico ni variable de producción.

Tampoco existe todavía un adaptador conectable para:

- Sincronización bidireccional con Google/Apple/Outlook: hoy hay ICS privado de solo
  lectura, que no requiere API.
- Banca PSD2: hoy hay importación y conciliación CSV con confirmación del titular.
- Cobro por enlace de las facturas del autónomo: Stripe actual solo factura Noesis.
- Recepcionista telefónico: es diseño P2, no integración disponible.
- Telegram y conectores directos con gestorías: no son necesarios para el piloto.

No crear credenciales ni pagar proveedores para estos puntos hasta que exista una
tarea aprobada, adaptador, pruebas y política de permisos.

## 10. Orden recomendado de conexión

1. Desplegar `main`, migrar, `/ready` y `noesis-doctor --strict`.
2. SMTP y Google OAuth: rápidos, visibles y de bajo riesgo operativo.
3. Stripe en test; cerrar IVA; repetir todos los ciclos antes de pasar a live.
4. Meta con número de prueba, después número real y plantillas aprobadas.
5. Un respaldo de IA con presupuesto; Groq Whisper solo si hace falta para audio.
6. Backup S3 y restauración real.
7. AEAT en `pruebas`; producción únicamente tras auditoría.

Una integración se marca conectada solo con evidencia de la prueba, no porque sus
variables existan. El resultado se registra en [[Registro-QA]] y el estado verificable
en [`project-state.json`](project-state.json).
