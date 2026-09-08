# Conectar Facebook (publicación automática)

Guía para dejar la página de Facebook publicando sola. Se hace **una sola vez**,
desde este ordenador, y tarda unos 15 minutos. Después no hay que volver a entrar:
la página publica una pieza cada 3 días y cada domingo llega un informe.

- Manual técnico de la automatización: [`README.md`](README.md).
- Aquí se explica **el porqué de cada paso**, que es lo que suele faltar.
- Misma guía en formato de lectura: [`Conectar-Facebook.html`](Conectar-Facebook.html).

## Antes de empezar

Necesitas tres cosas:

1. Ser **administrador** de la página de Facebook de Bynoesis.
2. Tener acceso al repositorio en GitHub para crear secretos (Settings → Secrets).
3. Este proyecto descargado en el ordenador.

## ¿Hace falta cuenta de Meta Developers?

Sí: no hay forma de publicar por API sin una app de Meta. Pero no es una cuenta
nueva ni un trámite. Se entra en <https://developers.facebook.com> **con tu cuenta
de Facebook de siempre**; la primera vez aceptas las condiciones de desarrollador y
ya está. Es gratis.

Y probablemente ya la tienes: la guía de WhatsApp del proyecto
([`docs/Conectar-APIs.md`](../docs/Conectar-APIs.md)) ya hace crear una app de Meta
para copiar su clave secreta a `WHATSAPP_APP_SECRET`. **Si ese paso está hecho,
reutiliza esa misma app** y sáltate el paso 1.

Lo que **no** hace falta, que es lo que suele echar para atrás:

| | ¿Hace falta? | Por qué |
|---|---|---|
| Revisión de la aplicación (*App Review*) | **No** | Publicas en tu propia página, siendo administrador de la app. La app se queda en modo desarrollo |
| Verificación del negocio | **No** | Solo se exige para permisos avanzados sobre datos de terceros |
| Publicar la app | **No** | En modo desarrollo funciona |
| Pagar algo | **No** | Es gratis |

La única condición es que tu cuenta sea administradora **de la app y de la
página**. Como creas tú las dos, se cumple sola. Publicar en páginas de otras
personas —clientes, por ejemplo— sí exigiría la revisión de Meta, pero eso no es
lo que hace esta automatización.

**Si prefieres no tocar nada de esto:** Meta Business Suite permite programar
publicaciones a mano, sin app ni token. Pierdes el informe del domingo, la
recuperación automática cuando una publicación falla, y hay que meter las 48
piezas a mano y reprogramar cada pocos meses.

## Por qué hay dos tokens (esta es la parte que confunde)

Meta no te da directamente una llave permanente. El camino es este:

```text
1. App de Meta          →  identifica al programa que publica (no publica nada por sí sola)
2. Token corto          →  permiso temporal tuyo, caduca en 1-2 horas
3. Token de página      →  la llave definitiva; se obtiene a partir del corto
4. Secreto en GitHub    →  donde vive esa llave para que el robot la use
```

El **token corto** es de usar y tirar: solo sirve para que `conectar.py` pida a
Meta el bueno. Que caduque en dos horas da igual, porque el que se guarda es el de
página, y ese **no caduca** mientras no cambies la contraseña de Facebook ni
revoques los permisos de la app.

Por eso hay un script intermedio: convierte una llave temporal en una permanente y
te dice cuál es. No se puede saltar ese paso.

---

## Paso 1 · Crear la app en Meta (5 min)

1. Entra en <https://developers.facebook.com/apps> con la cuenta de Facebook que
   administra la página.
2. **Crear app**. Si ya tienes una app de Meta por WhatsApp, reutilízala y salta al
   paso 2: no hace falta una segunda.
3. Ponle un nombre reconocible («Bynoesis publicación»).
4. Meta pregunta ahora por **casos de uso**, y esta pantalla despista: ninguno de
   los seis «Destacados» es el nuestro. Filtra por **«Otros»** y, al final de la
   lista, bajo «¿Buscas otra cosa?», marca **«Otro»** — el que avisa de que la app
   «se creará en la experiencia antigua». Luego, cuando pida el tipo de
   aplicación, elige **Empresa** (*Business*).
5. Al crearla aparece **«Productos disponibles»** (Messenger, Instagram, WhatsApp,
   API de marketing…). **No configures ninguno**: parece que hay que elegir algo y
   no hace falta nada. Los permisos de página se conceden en el paso 2, no aquí.
6. Comprueba arriba que pone **Tipo de aplicación: Empresa** y **Modo de la
   aplicación: En desarrollo**. Deja el modo en desarrollo; pasarlo a producción es
   lo que dispararía la revisión de Meta.
7. Ve a **Configuración de la aplicación → Básica** y apunta dos valores:
   - **Identificador de la app** (un número largo; ya se ve en la barra superior).
   - **Clave secreta de la app** — hay que pulsar «Mostrar».

Guárdalos en un sitio temporal. La clave secreta es un secreto de verdad: no la
pegues en ningún archivo del proyecto, ni en un chat, ni en un documento.

### Por qué «Otro» y no los casos de uso que Meta ofrece

Un caso de uso es un paquete de permisos preparado. Nosotros no necesitamos
ninguno: solo publicamos en nuestra propia página con tres permisos que nos damos
a nosotros mismos desde el Explorador de la API Graph (paso 2), con la app en modo
desarrollo. «Otro» deja la app limpia y esos permisos disponibles sin revisión.

| Caso de uso que ofrece Meta | Por qué no |
|---|---|
| API de marketing / anuncios con el Administrador | Son para **pagar** publicidad. Aquí se publica contenido orgánico |
| API de Threads | Otra red |
| Juego instantáneo | Otro producto |
| Inicio de sesión con Facebook | Sirve para que **un cliente** entre en Bynoesis con su cuenta de Facebook. No es esto |
| Conectar con clientes por WhatsApp | Interesa, pero es **otro trámite**: exige porfolio empresarial y va por [`docs/Conectar-APIs.md`](../docs/Conectar-APIs.md) |

**Cuidado con «Crea una aplicación sin un caso de uso»**, que está en esa misma
lista y suena a lo mismo. Da un identificador pelado, sin permisos ni productos, y
en la experiencia nueva ya no se pueden añadir después los de páginas: el
Explorador de la API Graph no ofrecerá `pages_manage_posts` y el paso 2 se queda
bloqueado.

«Otro» aparece marcado como *going away soon*. No afecta: Meta retira la forma de
**crear** apps así, no las ya creadas ni sus tokens. El día que desaparezca se crea
una nueva por el camino que haya entonces.

Si prefieres no depender de una opción a extinguir, la alternativa duradera es el
filtro **«Administración de contenido»**: ahí vive el caso de uso de gestionar
publicaciones de página y también sirve. Con «Otro» se llega seguro; con aquel,
antes.

## Paso 2 · Sacar el token corto (3 min)

1. Abre el **Explorador de la API Graph**:
   <https://developers.facebook.com/tools/explorer/>
2. Arriba a la derecha, en «Aplicación de Meta», **elige la app del paso 1**. Este
   desplegable se pasa por alto con facilidad, y si te dejas otra app, el token no
   servirá.
3. En «Permisos», añade estos tres:
   - `pages_show_list` — ver qué páginas administras
   - `pages_manage_posts` — publicar
   - `pages_read_engagement` — leer lo ya publicado (para no duplicar)
4. Pulsa **Generar token de acceso** y acepta el diálogo de Facebook.
5. Copia la cadena larga que aparece en el cuadro «Token de acceso».

> Meta cambia el nombre de estos botones cada pocos meses. Si no ves exactamente
> estas palabras, busca el desplegable de la app, la lista de permisos y el botón
> de generar: la secuencia es siempre la misma.

Tienes una o dos horas para el paso 3. Si te caduca, repite este paso: no se
rompe nada.

## Paso 3 · Convertirlo en la llave definitiva (2 min)

Desde la carpeta del proyecto, en la terminal:

En Windows (PowerShell):

```powershell
.venv\Scripts\python.exe facebook\conectar.py
```

En macOS o Linux:

```bash
.venv/bin/python facebook/conectar.py
```

> `python` a secas no existe dentro del proyecto: hay que usar el del entorno
> virtual, como arriba. Y ejecútalo con la ruta al archivo (no con `python -m`), o
> no encontrará sus propios módulos.

El script pregunta los tres valores por teclado. Los dos secretos **no se ven al
escribirlos**, que es justo lo que se busca: escritos en la línea de comandos
quedarían guardados en el historial de la terminal. Pega la clave secreta y el
token aunque la pantalla no muestre nada, y pulsa Enter.

Si prefieres automatizarlo, también acepta `--app-id`, `--app-secret` y
`--token-corto`, o las variables de entorno `FACEBOOK_APP_ID`,
`FACEBOOK_APP_SECRET` y `FACEBOOK_TOKEN_CORTO`.

Verás algo así:

```text
Páginas encontradas:

- Bynoesis
  FACEBOOK_PAGE_ID    = 1234567890
  FACEBOOK_PAGE_TOKEN = EAAG...(muy largo)
  Caduca              = no caduca mientras no cambies la contraseña ni revoques permisos
  Permisos            = pages_show_list, pages_manage_posts, pages_read_engagement
```

Si en «Caduca» aparece una fecha en vez de «no caduca», algo salió mal en el paso
2: repítelo asegurándote de elegir la app correcta.

## Paso 4 · Guardar la llave en GitHub (3 min)

En el repositorio: **Settings → Secrets and variables → Actions → New repository
secret**. Crea uno por fila:

| Nombre del secreto | Valor | ¿Obligatorio? |
|---|---|---|
| `FACEBOOK_PAGE_ID` | el `FACEBOOK_PAGE_ID` que imprimió el script | Sí |
| `FACEBOOK_PAGE_TOKEN` | el `FACEBOOK_PAGE_TOKEN` | Sí |
| `FACEBOOK_APP_ID` | el identificador de la app | Recomendado |
| `FACEBOOK_APP_SECRET` | la clave secreta de la app | Recomendado |

Los dos últimos no hacen falta para publicar: sirven para que el informe del
domingo pueda avisarte **antes** de que el token deje de funcionar. Sin ellos, el
primer aviso llegaría el día que ya no publique.

El nombre debe coincidir exactamente, en mayúsculas. Un secreto mal escrito no da
error: simplemente llega vacío y la automatización se queda en pausa.

## Paso 5 · Probar sin publicar (2 min)

En GitHub: **Actions → «Facebook · publicar» → Run workflow**, marcando
**`simulacro`**. Verás el texto que saldría hoy, sin publicar nada.

Desde tu ordenador es lo mismo:

```powershell
.venv\Scripts\python.exe facebook\publicar.py --simulacro   # qué tocaría hoy
.venv\Scripts\python.exe facebook\publicar.py --verificar   # ¿responde la página?
.venv\Scripts\python.exe facebook\revision.py               # el informe del domingo
```

Con `--simulacro` **nunca** se publica.

## Paso 6 · Estrenarla (opcional)

Si quieres que salga la primera pieza hoy mismo sin esperar a que toque:
**Actions → «Facebook · publicar» → Run workflow**, con **`forzar`** marcado y
`simulacro` **desmarcado**.

---

## Qué pasa a partir de ahora

| Cuándo | Qué ocurre | Qué haces tú |
|---|---|---|
| Cada día, 06:40 UTC | El robot mira si hoy toca por calendario | Nada |
| Cada 3 días | Publica una pieza | Nada |
| Domingos, 07:30 UTC | Se abre una incidencia «Revisión Facebook» | Leerla, ~2 min |
| Cada varios meses | El informe avisa de que el calendario se acaba | Ampliar `calendario.json` |

Los textos futuros están en `facebook/calendario.json`: puedes cambiar
cualquiera antes de que le toque salir.

## Cuando algo falle

| Síntoma | Qué significa | Qué hacer |
|---|---|---|
| Error **190** | El token murió: cambiaste la contraseña de Facebook o revocaste permisos | Repetir los pasos 2 a 4 |
| Error **200** | Al token le faltan permisos | Repetir el paso 2 con los tres permisos |
| Error **368** | Meta ha bloqueado temporalmente la página | Esperar; no reintentar en bucle |
| «Este usuario no administra ninguna página» | El token corto salió sin `pages_show_list`, o no eres administrador | Revisar permisos y tu rol en la página |
| No publica y no hay error | Faltan los secretos, o hoy no toca por calendario | Mirar la incidencia del domingo |

La automatización **nunca falla ruidosamente por falta de secretos**: se queda en
pausa y te lo recuerda el domingo. Eso es intencionado, para que un token caducado
no llene el repositorio de correos de error.

## Seguridad

- El `FACEBOOK_PAGE_TOKEN` permite publicar en la página en tu nombre. Trátalo
  como una contraseña: solo en los secretos de GitHub.
- No lo pegues en ningún archivo del proyecto, ni en una captura, ni en una
  conversación con una IA. Si aparece en algún sitio, revócalo en
  **developers.facebook.com → tu app → Configuración → Básica** y repite la guía.
- La automatización solo tiene permiso para publicar y leer la página. No accede a
  mensajes, anuncios ni a datos de tus clientes.
