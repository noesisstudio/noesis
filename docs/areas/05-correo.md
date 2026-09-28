# 05 · Correo: lo que sale y lo que entra

> Léela antes de tocar `adapters/email.py`, `adapters/google_mail.py`,
> `secret_box.py`, `documents/inbound_email.py`, la cola de correo del reloj o
> cualquier sitio que llame a `queue_email`. Figura 5 del
> [mapa visual](../02-tecnico/Mapa-Bynoesis.html).

## Qué hace

**Sale:** ningún correo se envía mientras alguien espera en una página. Se guarda en
la cola (`email_outbox`) y el reloj lo manda cada 15 segundos por la primera vía
lista: el Gmail del propio autónomo (si lo conectó y es un correo de su negocio),
Brevo por API o SMTP. Si falla, reintenta cada vez más tarde.

**Entra:** cada negocio tiene una dirección privada `docs.<32 hex>@bynoesis.com`. Un
buzón único de Hostinger recoge todo (catch-all), el reloj lo lee por IMAP cada
60 segundos, la dirección decide el negocio y cada adjunto entra como documento
pendiente de revisión. El correo nunca crea un gasto ni un cliente por sí solo.

## Esquema

```text
SALE
formulario de acceso · invitación y clave · factura con PDF · paquete de gestoría ·
avisos de privacidad · mensajes del cerebro
        │ adapters/email.queue_email()  (con idempotency_key)
        ▼
email_outbox ──► scheduler.process_email_outbox (cada 15 s)
                   1. google_mail.disponible(negocio)? → google_mail.enviar()
                   2. BREVO_API_KEY? → API HTTPS de Brevo
                   3. SMTP_* → SMTP (Railway bloquea sus puertos: solo respaldo)
                   falla → reintento 30 s … 1 h; agotado → visible en /admin

ENTRA (apagado por defecto)
proveedor o filtro de Gmail → docs.<token>@bynoesis.com → catch-all Hostinger
  → scheduler.process_inbound_email (cada 60 s) → inbound_email.process_raw_message
      una sola ruta válida → negocio · huella SHA-256 → sin duplicados
      adjuntos → documents.service.upload → borrador que el titular confirma
      sin adjuntos: confirmación de reenvío de Gmail firmada por Google → al titular
```

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `adapters/email.py` | `queue_email()` guarda en la cola; `send_email()` elige Brevo o SMTP; plantillas de factura y recordatorio |
| `web/scheduler.py` | `process_email_outbox()`: elige vía, reintenta con backoff (`EMAIL_RETRY_BASE_SECONDS`, `EMAIL_RETRY_MAX_SECONDS`) |
| `adapters/google_mail.py` | Gmail del autónomo: `url_de_autorizacion`, `canjear_codigo`, `disponible`, `enviar`. Un solo permiso: `gmail.send` |
| `secret_box.py` | Cifra los tokens de Google con una clave derivada de `NOESIS_SECRET` |
| `web/routers/account.py` | `/b/{id}/integraciones/google/conectar`, `/integraciones/google/callback`, `…/desconectar` |
| `documents/inbound_email.py` | Entrada: rutas opacas, `process_raw_message()`, `poll_mailbox()`, confirmación de reenvío de Gmail; CLI `noesis-inbound-email-check` |
| `templates/documentos.html` | Muestra la dirección privada y cómo hacerlo automático con un filtro |
| `scripts/check_email.py`, `scripts/check_email_dns.py` | Qué vía está configurada, quién firma y prueba real; DNS (SPF, DKIM, DMARC) |

## Reglas que no se rompen

1. **Nunca enviar en la petición.** Siempre `queue_email()`; el reloj es el único que
   envía. Así una caída del proveedor no deja al usuario ante una página en blanco.
2. **Idempotencia.** Cada envío lleva `idempotency_key`; repetir la acción no duplica
   el correo.
3. **Gmail: un solo permiso, `gmail.send`.** Pedir lectura lo convierte en permiso
   «restringido» de Google, con auditoría de seguridad anual. Para recibir se usa el
   reenvío, no la lectura del buzón.
4. **Tokens cifrados.** Los de Google no tocan la base en claro. Si cambia
   `NOESIS_SECRET`, las conexiones dejan de leerse y cada autónomo reconecta.
5. **Una cuenta revocada no se reintenta.** `invalid_grant` la marca muerta, se avisa
   en Ajustes y el correo sale por Bynoesis.
6. **Entrada: la dirección decide, nada más.** Ni remitente, ni asunto, ni cuerpo
   deciden el negocio o crean datos. Dos rutas en un mismo correo = se rechaza.
7. **No se guarda el mensaje**: solo huella, estado y recuentos.
8. **Un enlace solo se reenvía si Google lo firmó.** La confirmación de reenvío exige
   `dkim=pass` de google.com en `Authentication-Results`, y solo se aceptan enlaces
   de `mail.google.com` o `mail-settings.google.com`.
9. **Mensajes para el autónomo sin jerga.** Nunca nombrar variables de entorno ni
   proveedores internos en un WhatsApp o un correo al cliente.

## Estado real (28-sep-2026)

- **DNS de bynoesis.com:** MX en Hostinger; DKIM de Brevo publicado y dominio
  verificado; DMARC `p=none` con informes a Brevo; al SPF le falta
  `include:spf.brevo.com` (el DKIM ya hace pasar DMARC).
- **Railway:** existen `BREVO_API_KEY`, `SMTP_FROM` y `SMTP_*`. Falta un envío real
  comprobando en Gmail que DKIM dice `bynoesis.com`.
- **Gmail del autónomo:** código hecho y probado, pendiente de publicar. Faltan en
  Railway `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` (cliente OAuth con
  `gmail.send` y vuelta a `https://bynoesis.com/integraciones/google/callback`).
  Sin ellas, la opción no aparece. En modo pruebas de Google, caduca a los 7 días.
- **Entrada:** apagada. Faltan el buzón catch-all en Hostinger y las variables
  `NOESIS_INBOUND_EMAIL_*`.

## Pruebas que lo cubren

`test_email_api`, `test_email_dns`, `test_entrega_factura`, `test_correo_propio`,
`test_inbound_email`, `test_password_recovery`, `test_access_requests`.

## Al revisar código de esta zona

- [ ] ¿Algún envío nuevo llama a `send_email()` directamente en vez de `queue_email()`?
- [ ] ¿Lleva `idempotency_key` y `business_id` cuando pertenece a un negocio?
- [ ] ¿Se pide algún permiso de Google distinto de `gmail.send`?
- [ ] ¿Algún token o secreto se guarda sin `secret_box`, o sale en un log?
- [ ] En la entrada: ¿algo usa el remitente, el asunto o el cuerpo para decidir el
      negocio o crear datos?
- [ ] ¿Un fallo transitorio deja el mensaje sin leer para reintentarlo, y uno
      definitivo lo marca como leído?

## Dudas frecuentes

- **¿Por qué no leer directamente el Gmail del autónomo?** Permiso restringido de
  Google: auditoría anual de pago y más riesgo. El filtro de reenvío consigue lo
  mismo y el autónomo elige qué nos llega.
- **¿Outlook?** Recibir: sí, con una regla de reenvío (Microsoft 365 de empresa suele
  bloquear el reenvío externo por defecto). Enviar desde su dirección: no está hecho;
  sale desde Bynoesis.
- **¿Yahoo?** También manda una verificación sin adjuntos al activar el reenvío, y hoy
  se descartaría. Solo la de Gmail está contemplada.

## Más detalle

[`Correo-que-no-cae-en-spam`](../03-whatsapp-e-integraciones/Correo-que-no-cae-en-spam.md) ·
[`Conectar-Correo.pdf`](../03-whatsapp-e-integraciones/Conectar-Correo.pdf) ·
[`Conectar-APIs`](../03-whatsapp-e-integraciones/Conectar-APIs.md)
