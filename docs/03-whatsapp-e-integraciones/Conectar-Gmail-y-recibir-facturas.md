# Conectar Gmail y recibir facturas por correo

*28 de septiembre de 2026. Guía para dejar en marcha las dos funciones de correo del
autónomo. Todo el código está hecho y probado; lo que falta son cuentas y variables
que solo puede poner el founder. Detalle técnico en
[`areas/05-correo`](../areas/05-correo.md).*

Son dos cosas independientes. Se pueden activar por separado y en cualquier orden:

| | Qué consigue el autónomo | Qué hay que preparar |
|---|---|---|
| **A · Enviar desde su Gmail** | Sus facturas salen desde su dirección y le quedan en Enviados | Un cliente OAuth en Google Cloud y dos variables |
| **B · Recibir facturas solas** | Las facturas de sus proveedores entran solas en Documentos | Un buzón en Hostinger con catch-all y dos variables |

Antes de empezar, comprueba que en Railway (proyecto `autonoms`, servicio `web`)
existe `NOESIS_SECRET` y **que no lo vas a cambiar nunca**: con él se cifran las
conexiones de Gmail, y si cambia, todos los autónomos tendrán que reconectar.

---

## A · Enviar desde el Gmail del autónomo

### A1. Google Cloud: la pantalla de permisos (15 min)

En <https://console.cloud.google.com>, usa el mismo proyecto del acceso con Google
del panel (el de `GOOGLE_OAUTH_CLIENT_ID`) o crea uno llamado «Bynoesis».

1. **Activar la API:** «APIs y servicios» → «Biblioteca» → busca **Gmail API** →
   **Habilitar**.
2. **Google Auth Platform → Marca (Branding):**
   - Nombre de la aplicación: `Bynoesis`
   - Correo de asistencia: el tuyo
   - Página principal: `https://bynoesis.com`
   - Política de privacidad: `https://bynoesis.com/privacidad`
   - Condiciones del servicio: `https://bynoesis.com/terminos`
   - Dominio autorizado: `bynoesis.com` (ya está verificado en Search Console)
3. **Acceso a datos (Data access) → Añadir o quitar permisos.** Marca exactamente estos
   tres y ninguno más:
   - `openid`
   - `.../auth/userinfo.email`
   - `.../auth/gmail.send`

   Si añades cualquier permiso de **leer** correo (`gmail.readonly`,
   `mail.google.com`…), Google lo trata como «restringido» y exige una auditoría de
   seguridad anual de pago. Bynoesis no lo necesita.
4. **Público (Audience):** tipo **Externo**. Mientras esté en **Pruebas**:
   - solo pueden conectar las cuentas que añadas en «Usuarios de prueba» (hasta 100):
     añade tu Gmail y el de cada piloto;
   - **la conexión caduca a los 7 días** y hay que reconectar. Es una regla de Google.

### A2. Google Cloud: el cliente OAuth (5 min)

**Google Auth Platform → Clientes.** Si ya existe el cliente web del acceso con Google,
edítalo; si no, **Crear cliente → Aplicación web**. En «URI de redirección
autorizados» tiene que estar, escrita exactamente así:

```text
https://bynoesis.com/integraciones/google/callback
```

Si es el mismo cliente del acceso al panel, deja también la que ya tenía
(`https://bynoesis.com/auth/google/callback`). Copia el **ID de cliente** (termina en
`.apps.googleusercontent.com`) y el **secreto de cliente**.

### A3. Railway: dos variables (2 min)

En Railway → `autonoms` → `web` → **Variables**, añade:

| Variable | Valor |
|---|---|
| `GOOGLE_CLIENT_ID` | El ID de cliente de A2 |
| `GOOGLE_CLIENT_SECRET` | El secreto de cliente de A2 |

Pégalos directamente en Railway, nunca en un chat ni en el repositorio. Railway
redespliega solo. `GOOGLE_REDIRECT_URI` no hace falta: se calcula a partir de
`NOESIS_BASE_URL`.

Al desplegar, ocurren dos cosas: aparece la tarjeta «Conectar mi Gmail» en Ajustes,
y la política de privacidad añade el apartado «Si conectas tu Gmail» que Google
exige.

### A4. Comprobar sin tocar nada (1 min)

En una terminal del servicio `web` de Railway (`railway ssh`):

```bash
noesis-integrations-check --network
```

La línea `gmail` debe decir **«Credenciales coherentes y Google accesible»**. Si dice
otra cosa, el propio mensaje indica qué corregir (ver la tabla del final).

### A5. Prueba real (5 min)

1. Entra en Bynoesis con tu cuenta → **Ajustes** → **Conectar mi Gmail**.
2. En la pantalla de Google, **deja marcada la casilla «Enviar correo electrónico en tu
   nombre»**. Google deja desmarcarla; si lo haces, Bynoesis te avisará al volver.
3. Al volver, Ajustes debe decir «Gmail conectado: tu@gmail.com».
4. Emite una factura de prueba a un cliente cuyo correo sea **otra** cuenta tuya y
   pulsa **Enviar por correo**.
5. Comprueba: llega a la otra cuenta **desde tu Gmail**, con el nombre del negocio y
   el PDF adjunto, y aparece en la carpeta **Enviados** de tu Gmail.

Solo salen desde el Gmail del autónomo los correos **a sus clientes** (facturas y
mensajes que redacta Bynoesis para ellos). Los avisos de Bynoesis al propio autónomo,
como recuperar la contraseña, siguen saliendo de Bynoesis.

### A6. Salir del modo pruebas (cuando haya pilotos)

Para quitar el límite de 100 cuentas y la caducidad de 7 días: **Google Auth Platform →
Público → Publicar aplicación**. Como `gmail.send` es un permiso «sensible», Google lo
revisa (normalmente días). Te pedirá:

- **Vídeo** (YouTube, puede ser «no listado»): la pantalla de Ajustes, pulsar
  «Conectar mi Gmail», la pantalla de Google con los permisos y el envío de una factura
  que aparece en Enviados.
- **Justificación**, que puedes pegar tal cual:

  > Bynoesis is a business management app for self-employed professionals in Spain.
  > We request gmail.send only so that each user can send their own invoices and
  > messages to their own customers from their own Gmail address, so replies reach
  > them and a copy stays in their Sent folder. We never read, store or access the
  > user's mailbox. The openid and email scopes are used only to show which account is
  > connected.

- Que la política de privacidad explique el uso de los datos de Google. Ya lo hace
  cuando las variables de A3 están puestas.

Antes de enviar la revisión, que el abogado lea el apartado «Si conectas tu Gmail» de
`/privacidad`.

---

## B · Recibir facturas por correo automáticamente

Cada negocio tiene una dirección privada del tipo `docs.<código>@bynoesis.com`, visible
en **Documentos**. Lo que llegue ahí entra como documento pendiente de revisar.

### B1. Hostinger: el buzón y el catch-all (10 min)

1. hPanel → **Correos** → `bynoesis.com` → **Crear cuenta de correo**:
   `entrada@bynoesis.com`, con una contraseña larga que no uses en ningún otro sitio.
2. En la configuración del dominio de correo busca **Catch-all** (a veces está dentro
   de «Reenvíos») y dirígelo a `entrada@bynoesis.com`. Así, cualquier dirección
   `docs.…@bynoesis.com` acaba en ese buzón. Las direcciones que ya existen, como
   `info@`, siguen funcionando igual.

### B2. Railway: dos variables, todavía apagado (2 min)

| Variable | Valor |
|---|---|
| `NOESIS_INBOUND_EMAIL_USER` | `entrada@bynoesis.com` |
| `NOESIS_INBOUND_EMAIL_PASSWORD` | La contraseña de B1 |

No pongas todavía `NOESIS_INBOUND_EMAIL_ENABLED`. El servidor IMAP
(`imap.hostinger.com`, puerto 993) ya viene configurado por defecto.

Luego, en la terminal de `web`: `noesis-integrations-check --network`. La línea
`correo_entrante` debe decir **«Buzón accesible; la recepción sigue apagada»**.

### B3. Prueba segura antes de encender (15 min)

1. Crea la dirección de un negocio de prueba (usa el ID de tu propia cuenta), en la
   terminal de `web`:
   ```bash
   noesis-inbound-email-check --business-id <ID> --create-route
   ```
   Apunta la dirección `docs.…@bynoesis.com` que devuelve.
2. Desde tu Gmail **personal**, empieza el reenvío como lo haría un autónomo (ver B5):
   ⚙️ → **Ver todos los ajustes** → **Reenvío y correo POP/IMAP** → **Añadir una
   dirección de reenvío** → la dirección del paso 1. Gmail manda un código a esa
   dirección.
3. Como la recepción aún está apagada, ese correo se queda en el buzón. Entra en el
   webmail de `entrada@bynoesis.com`, ábrelo, cópiate el **código** para confirmar el
   reenvío en Gmail y **descarga el mensaje como `.eml`**.
4. En Gmail, crea un filtro que reenvíe los correos con adjunto a esa dirección y
   mándate uno con un PDF. En el webmail, descarga también ese reenvío como `.eml`.
5. En tu Mac, dentro de la carpeta del proyecto, analiza los dos archivos. No se toca
   ninguna base de datos ni se envía nada:
   ```bash
   .venv/bin/python -m noesis.documents.inbound_email --inspect confirmacion.eml
   .venv/bin/python -m noesis.documents.inbound_email --inspect reenvio.eml
   ```
   - La confirmación debe decir `"gmail_forwarding": true` y, en `google_signature`,
     `pass` o `sin dato` (con `fail` no se enviaría al autónomo).
   - El reenvío debe decir **«Correcto: entraría en el negocio con 1 documento(s)»**.
     **Esta es la prueba clave:** demuestra que Hostinger conserva la dirección de
     destino cuando el correo llega reenviado.

Si el reenvío dice «no conserva el destinatario», no enciendas la recepción y
pásame ese `.eml`.

### B4. Encender (1 min)

Añade en Railway `NOESIS_INBOUND_EMAIL_ENABLED` = `true`. Desde ese momento, el reloj
lee el buzón cada 60 segundos y cada negocio ve su dirección en Documentos.

### B5. Instrucciones para el autónomo

**Gmail** (lo recomendable):

1. En Bynoesis, **Documentos** → copia tu dirección privada.
2. En Gmail: ⚙️ → **Ver todos los ajustes** → **Reenvío y correo POP/IMAP** →
   **Añadir una dirección de reenvío** → pega la dirección.
3. Te llegará un correo de Bynoesis con un enlace de Google: ábrelo para confirmar.
4. En Gmail, crea un **filtro** (lupa → «Mostrar opciones de búsqueda»). Por ejemplo,
   *Tiene archivo adjunto* + *Contiene las palabras* `factura` → **Crear filtro** →
   **Reenviar a** tu dirección de Bynoesis. No reenvíes todo el correo: solo lo que
   sea factura.

**Outlook / Hotmail:** Configuración → Correo → **Reglas** → Nueva regla → condición
«Tiene datos adjuntos» → acción **Reenviar a** tu dirección de Bynoesis. No usa código.
En Microsoft 365 de empresa, el reenvío fuera suele estar bloqueado: tiene que
permitirlo quien administre su correo.

**Cualquier otro correo:** reenviar a mano cada factura a su dirección privada siempre
funciona.

Lo que llega entra en **Documentos** como pendiente. Nada se contabiliza hasta que el
autónomo lo confirma.

---

## Si algo falla

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Google dice `redirect_uri_mismatch` | La dirección de A2 no es exactamente la de la guía | Cópiala otra vez, con `https` y sin barra final |
| Google dice «Acceso bloqueado» | Tu cuenta no está en Usuarios de prueba | Añádela en A1.4 |
| Al volver: «sin el permiso de enviar correo» | Se desmarcó la casilla en Google | Reconectar dejándola marcada |
| Ajustes dice que la cuenta está desconectada | El autónomo retiró el permiso, cambió la contraseña de Google o pasaron 7 días en modo pruebas | Reconectar. Mientras tanto, sus facturas salen desde Bynoesis |
| La factura salió desde Bynoesis y no desde su Gmail | Gmail no conectado o retirado | Normal: es el respaldo. Revisar Ajustes |
| `noesis-integrations-check` dice «dirección de vuelta no coincide» | `NOESIS_BASE_URL` y la URI de Google difieren | Deben ser el mismo dominio |
| No llega el correo con el código de Gmail | Recepción apagada, o la firma de Google falló | Analizar el `.eml` con `--inspect` (B3.5) |
| Reenvíos: `route_missing` o «no conserva el destinatario» | Hostinger no conserva el destinatario | Parar y revisar el `.eml` (B3.5) |
| En Documentos aparece un logo como documento | Imagen incrustada grande (más de 30 KB) | Descartarla; si se repite con un proveedor, avisar |

## Correo de Bynoesis (Brevo): un detalle pendiente

El dominio ya tiene el DKIM de Brevo. Al SPF le falta Brevo. Cambia el registro TXT
que empieza por `v=spf1` (no crees otro) para que quede:

```text
v=spf1 include:_spf.mail.hostinger.com include:spf.brevo.com ~all
```

Después, envíate un correo de prueba a un Gmail y en «Mostrar original» comprueba que
pone `DKIM: 'PASS' con el dominio bynoesis.com`.
