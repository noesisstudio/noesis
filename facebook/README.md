# Automatización de Facebook

Publica en la página de Facebook de Noesis **una pieza cada 3 días**, sin que
nadie tenga que entrar a hacerlo. Tú solo lees el informe que llega **cada
domingo** y compruebas que no hay avisos.

- Contenido: `calendario.json` (48 piezas, unos 5 meses sin repetir nada).
- Publicador: `publicar.py`, lo lanza el workflow «Facebook · publicar» cada día.
- Informe: `revision.py`, lo lanza el workflow «Facebook · revisión del domingo».
- Conexión inicial: `conectar.py`, se ejecuta una vez desde tu ordenador.

No guarda estado en el repositorio: antes de publicar mira lo que hay de verdad en
la página. Por eso no hay commits automáticos y no se dispara ningún despliegue.

## Qué tienes que hacer tú

| Cuándo | Qué | Cuánto |
| --- | --- | --- |
| Una vez | Conectar la página (los pasos de abajo) | ~15 min |
| Cada domingo | Leer la incidencia «Revisión Facebook» y comprobar que dice «todo correcto» | ~2 min |
| Cuando quieras | Cambiar textos futuros en `calendario.json` | opcional |
| Cada varios meses | Ampliar el calendario cuando el informe avise | ~1 h |

## Conectar la página

> Si es la primera vez, sigue la guía explicada de
> [`Conectar-Facebook.html`](Conectar-Facebook.html) (o su fuente [`.md`](Conectar-Facebook.md)): cuenta por qué
> hay dos tokens y qué se ve en cada pantalla. Lo de aquí abajo es el resumen.


Hazlo una sola vez. Necesitas ser administrador de la página de Facebook de
Noesis (configuración de la página en `branding/redes-sociales/facebook/`).

1. Entra en <https://developers.facebook.com/apps> y crea una app de tipo
   **Empresa** (o reutiliza la que ya uses con Meta). Apunta el **identificador de
   la app** y, en «Configuración → Básica», la **clave secreta de la app**.
2. Abre el **Explorador de la API Graph**
   (<https://developers.facebook.com/tools/explorer/>), elige tu app y pide un
   token de usuario con estos tres permisos:
   - `pages_show_list`
   - `pages_manage_posts`
   - `pages_read_engagement`
3. Copia ese token corto (caduca en una o dos horas, da igual) y ejecuta desde la
   raíz del proyecto:

   ```powershell
   .venv\Scripts\python.exe facebook\conectar.py
   ```

   En macOS o Linux: `.venv/bin/python facebook/conectar.py`. Pregunta los tres
   valores por teclado y los dos secretos no se ven al escribirlos, para que no
   queden en el historial de la terminal. También acepta `--app-id`,
   `--app-secret` y `--token-corto`, o las variables de entorno equivalentes
   (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_TOKEN_CORTO`).

   Te devuelve, para cada página que administras, el `FACEBOOK_PAGE_ID` y el
   `FACEBOOK_PAGE_TOKEN` definitivo. El token de página obtenido así **no caduca**
   mientras no cambies la contraseña de Facebook ni revoques los permisos.

4. En GitHub: **Settings → Secrets and variables → Actions → New repository
   secret**. Crea estos secretos con los valores que te ha dado el script:

   | Secreto | Obligatorio | Para qué |
   | --- | --- | --- |
   | `FACEBOOK_PAGE_ID` | sí | identificador de la página |
   | `FACEBOOK_PAGE_TOKEN` | sí | token de publicación |
   | `FACEBOOK_APP_ID` | recomendado | avisar de la caducidad del token |
   | `FACEBOOK_APP_SECRET` | recomendado | avisar de la caducidad del token |

   No pegues nunca estos valores en un fichero del repositorio.

5. Comprueba que la conexión funciona: **Actions → «Facebook · publicar» → Run
   workflow**, con `simulacro` marcado. Verás el texto que saldría, sin publicarlo.
6. Si quieres estrenar la página hoy mismo, lanza el mismo workflow con `forzar`
   marcado y `simulacro` desmarcado.

Mientras falten los secretos, la automatización **no falla**: se queda en pausa y
la revisión del domingo te lo recuerda.

## Comprobarlo desde tu ordenador

```bash
python facebook/publicar.py --simulacro          # qué tocaría hoy
python facebook/publicar.py --simulacro --fecha 2026-10-01
python facebook/publicar.py --verificar          # ¿responde la página?
python facebook/revision.py                      # el informe del domingo
```

Con `--simulacro` nunca se publica nada.

En Windows, `python` se sustituye por `.venv\Scripts\python.exe` y las
barras por `\`.

## El domingo

Cada domingo por la mañana se abre una incidencia en el repositorio con la
etiqueta `facebook`. Trae:

1. Lo que tenía que salir esa semana y si está de verdad en la página (✅ / ❌).
2. Otras publicaciones que hayáis hecho a mano.
3. Las 4 siguientes piezas, con su fecha, para que puedas vetarlas o cambiarlas.
4. La salud de la conexión: página, permisos y días que le quedan al token.
5. Cuántas piezas nuevas quedan antes de que el calendario empiece a repetirse.

Si el título dice **«todo correcto»**, no tienes que hacer nada. Si dice
**«N aviso(s)»**, arriba del todo está la lista de qué mirar.

## Cambiar el contenido

Todo el contenido vive en `calendario.json`. Cada pieza tiene:

```json
{
  "id": "F49",
  "pilar": "educacion",
  "titulo": "Nombre interno, no se publica",
  "texto": "Primera línea corta, que es el gancho.\n\nEl resto del mensaje.",
  "enlace": "https://bynoesis.com/solicitar-acceso"
}
```

Reglas que las pruebas verifican solas (`tests/test_marketing_facebook.py`):

- `id` único; `pilar`, `titulo` y `texto` obligatorios.
- La primera línea, máximo 130 caracteres: es lo que se lee sin desplegar el post.
- El texto, máximo 1200 caracteres.
- `enlace` opcional, y solo a `https://bynoesis.com`.
- Sin promesas prohibidas por el manual de marca (`100%`, «revoluciona»,
  «garantiza», «sin errores», «inteligencia artificial», «para siempre»).

Además, por criterio editorial: sin clientes ni cifras inventadas, sin prometer
presentación fiscal ni sustituir a la gestoría, y sin precios (los precios están
en la web y ahí no se desincronizan).

Se publican **en orden**. Si añades piezas al final, entran cuando les toque; si
editas una que aún no ha salido, sale la versión nueva. Basta con el commit: no
hay que desplegar nada.

## Renovar el token

Si el informe avisa de que el token caduca, o Meta empieza a rechazar las
llamadas, repite los pasos 2 y 3 de «Conectar la página» y actualiza el secreto
`FACEBOOK_PAGE_TOKEN`. No hace falta tocar el código.

## Cómo funciona por dentro

- El workflow corre **todos los días** a las 06:40 UTC, pero solo publica si el
  día cae en la cadencia: cada 3 días desde el `ancla` del calendario.
- Antes de publicar lee las últimas publicaciones de la página. Si el texto ya
  está ahí, no lo repite. Así una ejecución manual o repetida no duplica nada.
- Si un día que tocaba falló (corte de GitHub, token caído) y la página lleva
  callada desde entonces, la ejecución del día siguiente lo recupera. Si en ese
  hueco publicasteis algo a mano, no lo recupera: mejor saltarse una pieza que
  publicar dos seguidas.
- Cuando la cola se acaba, vuelve a empezar. El informe del domingo avisa varias
  semanas antes para que dé tiempo a escribir piezas nuevas.
- Solo usa biblioteca estándar de Python: el workflow no instala dependencias.

## Cuando algo falla

| Lo que dice Meta | Qué pasa | Qué hacer |
| --- | --- | --- |
| `code=190` | el token ya no vale | renovar `FACEBOOK_PAGE_TOKEN` |
| `code=200` | faltan permisos | rehacer el token con `pages_manage_posts` |
| `code=368` | Meta ha bloqueado temporalmente la página | no reintentar; revisar avisos en la página |
| `code=4` o `17` | demasiadas llamadas | se reintenta solo; si insiste, esperar unas horas |

Otros dos detalles que conviene saber:

- GitHub desactiva los workflows programados si el repositorio pasa 60 días sin
  actividad. Con desarrollo normal no ocurre; si ocurriera, se reactivan desde
  Actions con un clic.
- Meta prohíbe automatizar respuestas que parezcan atención humana. Esto solo
  publica contenido propio: los comentarios y mensajes se contestan a mano.
