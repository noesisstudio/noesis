"""Núcleo compartido de la automatización de Facebook de Noesis.

Aquí vive todo lo que comparten el publicador (`publicar.py`) y la revisión del
domingo (`revision.py`): el calendario editorial, el cálculo de qué toca cada día,
las credenciales y las llamadas a la Graph API de Meta.

Solo biblioteca estándar, como el resto del proyecto. No importa nada de
`src/noesis/`: esto promociona Noesis, no forma parte del producto que se vende.
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
RAIZ_REPO = RAIZ.parents[1]
RUTA_CALENDARIO = RAIZ / "calendario.json"

VERSION_GRAPH_POR_DEFECTO = "v23.0"
INTENTOS_MAXIMOS = 3
ESPERA_BASE_SEGUNDOS = 4
TIEMPO_LIMITE_SEGUNDOS = 25
AGENTE = "noesis-marketing/1.0"

# Huso del negocio: la cadencia se cuenta en días de Madrid, no en UTC, para que
# un workflow que corre de madrugada no adelante ni retrase una publicación.
HUSO = "Europe/Madrid"

# Los enlaces solo pueden apuntar al sitio propio. Evita que un error de copiado
# publique tráfico hacia un dominio que no controlamos.
DOMINIO_PERMITIDO = "https://bynoesis.com"

# Facebook corta el texto visible mucho antes, pero un post largo se lee mal en
# móvil. Es un límite editorial, no técnico.
LARGO_MAXIMO_TEXTO = 1200


class ErrorConfiguracion(RuntimeError):
    """Falta algo para poder hablar con Meta."""


class ErrorCalendario(RuntimeError):
    """El calendario editorial no es válido."""


class ErrorGraph(RuntimeError):
    """Meta ha respondido con un error."""


# --- Calendario editorial -------------------------------------------------


@dataclass(frozen=True)
class Publicacion:
    identificador: str
    pilar: str
    titulo: str
    texto: str
    enlace: str = ""

    @property
    def primera_linea(self) -> str:
        return self.texto.strip().splitlines()[0]


@dataclass(frozen=True)
class Calendario:
    cadencia_dias: int
    ancla: date
    publicaciones: tuple[Publicacion, ...]

    def __len__(self) -> int:
        return len(self.publicaciones)


def cargar_calendario(ruta: Path = RUTA_CALENDARIO) -> Calendario:
    """Lee y valida el calendario. Falla pronto y con el motivo concreto."""

    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErrorCalendario(f"no se puede leer {ruta}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ErrorCalendario(f"{ruta.name} no es JSON válido: {exc}") from exc

    try:
        cadencia = int(datos["cadencia_dias"])
        ancla = date.fromisoformat(str(datos["ancla"]))
        crudas = list(datos["publicaciones"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ErrorCalendario(
            "el calendario necesita 'cadencia_dias', 'ancla' (YYYY-MM-DD) y "
            f"'publicaciones': {exc}"
        ) from exc

    if cadencia < 1:
        raise ErrorCalendario("'cadencia_dias' debe ser al menos 1.")
    if not crudas:
        raise ErrorCalendario("el calendario está vacío: no hay nada que publicar.")

    problemas: list[str] = []
    vistos: set[str] = set()
    publicaciones: list[Publicacion] = []
    for posicion, cruda in enumerate(crudas, start=1):
        identificador = str(cruda.get("id", "")).strip()
        etiqueta = identificador or f"posición {posicion}"
        texto = str(cruda.get("texto", "")).strip()
        enlace = str(cruda.get("enlace", "")).strip()
        if not identificador:
            problemas.append(f"{etiqueta}: falta 'id'.")
        elif identificador in vistos:
            problemas.append(f"{etiqueta}: 'id' repetido.")
        vistos.add(identificador)
        if not str(cruda.get("titulo", "")).strip():
            problemas.append(f"{etiqueta}: falta 'titulo'.")
        if not str(cruda.get("pilar", "")).strip():
            problemas.append(f"{etiqueta}: falta 'pilar'.")
        if not texto:
            problemas.append(f"{etiqueta}: falta 'texto'.")
        elif len(texto) > LARGO_MAXIMO_TEXTO:
            problemas.append(
                f"{etiqueta}: el texto tiene {len(texto)} caracteres y el máximo "
                f"editorial es {LARGO_MAXIMO_TEXTO}."
            )
        if enlace and not enlace.startswith(DOMINIO_PERMITIDO):
            problemas.append(f"{etiqueta}: el enlace debe empezar por {DOMINIO_PERMITIDO}.")
        publicaciones.append(
            Publicacion(
                identificador=identificador,
                pilar=str(cruda.get("pilar", "")).strip(),
                titulo=str(cruda.get("titulo", "")).strip(),
                texto=texto,
                enlace=enlace,
            )
        )

    if problemas:
        raise ErrorCalendario("calendario inválido:\n- " + "\n- ".join(problemas))

    return Calendario(cadencia_dias=cadencia, ancla=ancla, publicaciones=tuple(publicaciones))


# --- Qué toca publicar y cuándo -------------------------------------------


def hoy() -> date:
    """Fecha de hoy en el huso del negocio."""

    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(HUSO)).date()
    except Exception:  # pragma: no cover - runner sin base de husos
        return datetime.now(timezone.utc).date()


def indice_turno(dia: date, calendario: Calendario) -> int | None:
    """Número de turno de ese día, o None si ese día no toca publicar."""

    diferencia = (dia - calendario.ancla).days
    if diferencia < 0 or diferencia % calendario.cadencia_dias:
        return None
    return diferencia // calendario.cadencia_dias


def publicacion_de(dia: date, calendario: Calendario) -> tuple[Publicacion, int] | None:
    """Publicación que corresponde a ese día y vuelta del calendario (0 = primera)."""

    turno = indice_turno(dia, calendario)
    if turno is None:
        return None
    total = len(calendario.publicaciones)
    return calendario.publicaciones[turno % total], turno // total


def turno_anterior(dia: date, calendario: Calendario) -> date | None:
    """Último día de publicación en o antes de `dia`."""

    diferencia = (dia - calendario.ancla).days
    if diferencia < 0:
        return None
    return dia - timedelta(days=diferencia % calendario.cadencia_dias)


def turnos_entre(inicio: date, fin: date, calendario: Calendario) -> list[tuple[date, Publicacion, int]]:
    """Todos los turnos del intervalo, extremos incluidos."""

    agenda: list[tuple[date, Publicacion, int]] = []
    dia = inicio
    while dia <= fin:
        prevista = publicacion_de(dia, calendario)
        if prevista is not None:
            agenda.append((dia, prevista[0], prevista[1]))
        dia += timedelta(days=1)
    return agenda


def proximos_turnos(desde: date, cantidad: int, calendario: Calendario) -> list[tuple[date, Publicacion, int]]:
    """Los siguientes `cantidad` turnos a partir de `desde`, incluido."""

    diferencia = (desde - calendario.ancla).days
    if diferencia <= 0:
        primer_dia = calendario.ancla
    else:
        resto = diferencia % calendario.cadencia_dias
        primer_dia = desde if not resto else desde + timedelta(days=calendario.cadencia_dias - resto)
    agenda: list[tuple[date, Publicacion, int]] = []
    for salto in range(cantidad):
        dia = primer_dia + timedelta(days=salto * calendario.cadencia_dias)
        prevista = publicacion_de(dia, calendario)
        if prevista is not None:
            agenda.append((dia, prevista[0], prevista[1]))
    return agenda


def restantes_sin_repetir(dia: date, calendario: Calendario) -> int:
    """Publicaciones nuevas que quedan antes de que el calendario dé la vuelta."""

    turno = indice_turno(dia, calendario)
    if turno is None:
        siguiente = proximos_turnos(dia, 1, calendario)
        if not siguiente:
            return len(calendario.publicaciones)
        turno = indice_turno(siguiente[0][0], calendario) or 0
    total = len(calendario.publicaciones)
    return total - (turno % total)


# --- Credenciales ----------------------------------------------------------


@dataclass(frozen=True)
class Credenciales:
    pagina: str
    acceso: str
    version: str
    app_id: str = ""
    app_secreto: str = ""

    @property
    def puede_revisar_token(self) -> bool:
        return bool(self.app_id and self.app_secreto)


def cargar_env_local(ruta: Path | None = None) -> None:
    """Completa el entorno con el `.env` del repositorio si existe.

    Sirve para probar desde este ordenador. En GitHub Actions no hay `.env` y las
    variables llegan como secretos, así que esta función no hace nada.
    """

    destino = ruta or (RAIZ_REPO / ".env")
    if not destino.exists():
        return
    try:
        contenido = destino.read_text(encoding="utf-8")
    except OSError:
        return
    for linea in contenido.splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        clave, _, valor = limpia.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def credenciales_faltantes() -> list[str]:
    """Variables imprescindibles que no están puestas."""

    return [
        nombre
        for nombre in ("FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_TOKEN")
        if not os.environ.get(nombre, "").strip()
    ]


def leer_credenciales() -> Credenciales:
    cargar_env_local()
    faltan = credenciales_faltantes()
    if faltan:
        raise ErrorConfiguracion(
            "faltan variables para publicar en Facebook: "
            + ", ".join(faltan)
            + ". Están explicadas en facebook/README.md."
        )
    return Credenciales(
        pagina=os.environ["FACEBOOK_PAGE_ID"].strip(),
        acceso=os.environ["FACEBOOK_PAGE_TOKEN"].strip(),
        version=os.environ.get("META_GRAPH_VERSION", "").strip() or VERSION_GRAPH_POR_DEFECTO,
        app_id=os.environ.get("FACEBOOK_APP_ID", "").strip(),
        app_secreto=os.environ.get("FACEBOOK_APP_SECRET", "").strip(),
    )


# --- Graph API -------------------------------------------------------------


def _mensaje_de_error(cuerpo: bytes) -> str:
    try:
        datos = json.loads(cuerpo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return cuerpo[:300].decode("utf-8", "replace")
    error = datos.get("error") if isinstance(datos, dict) else None
    if not isinstance(error, dict):
        return str(datos)[:300]
    partes = [str(error.get("message", "error sin mensaje"))]
    for clave in ("type", "code", "error_subcode"):
        if error.get(clave) not in (None, ""):
            partes.append(f"{clave}={error[clave]}")
    return " · ".join(partes)


def _llamar(url: str, datos: dict[str, str] | None, espera: float, intentos: int) -> dict:
    """Llamada a la Graph API con reintentos ante fallos temporales.

    Quien publica pide `intentos=1` a propósito: si una escritura se corta después
    de que Meta la haya aceptado, reintentar publicaría dos veces lo mismo. Es
    preferible fallar y que la ejecución del día siguiente lo recupere después de
    mirar qué hay de verdad en la página.
    """

    cuerpo = urllib.parse.urlencode(datos).encode("utf-8") if datos is not None else None
    ultimo: Exception | None = None
    for intento in range(1, max(1, intentos) + 1):
        peticion = urllib.request.Request(
            url,
            data=cuerpo,
            method="POST" if cuerpo is not None else "GET",
            headers={"User-Agent": AGENTE},
        )
        try:
            with urllib.request.urlopen(peticion, timeout=TIEMPO_LIMITE_SEGUNDOS) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detalle = _mensaje_de_error(exc.read())
            # 4xx que no sea exceso de ritmo es culpa nuestra: reintentar no arregla
            # un token caducado ni un permiso que falta.
            if exc.code < 500 and exc.code != 429:
                raise ErrorGraph(f"Meta ha rechazado la llamada ({exc.code}): {detalle}") from exc
            ultimo = ErrorGraph(f"Meta ha fallado ({exc.code}): {detalle}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            ultimo = ErrorGraph(f"no se ha podido hablar con Meta: {exc}")
        if intento < intentos:
            time.sleep(espera * intento)
    raise ultimo or ErrorGraph("no se ha podido hablar con Meta.")


def graph_get(
    credenciales: Credenciales,
    ruta: str,
    parametros: dict[str, str] | None = None,
    espera: float = ESPERA_BASE_SEGUNDOS,
    intentos: int = INTENTOS_MAXIMOS,
) -> dict:
    consulta = dict(parametros or {})
    consulta.setdefault("access_token", credenciales.acceso)
    url = (
        f"https://graph.facebook.com/{credenciales.version}/{ruta.lstrip('/')}"
        f"?{urllib.parse.urlencode(consulta)}"
    )
    return _llamar(url, None, espera, intentos)


def graph_post(
    credenciales: Credenciales,
    ruta: str,
    datos: dict[str, str],
    espera: float = ESPERA_BASE_SEGUNDOS,
    intentos: int = 1,
) -> dict:
    cuerpo = dict(datos)
    cuerpo.setdefault("access_token", credenciales.acceso)
    url = f"https://graph.facebook.com/{credenciales.version}/{ruta.lstrip('/')}"
    return _llamar(url, cuerpo, espera, intentos)


# --- Estado real de la página ---------------------------------------------


@dataclass(frozen=True)
class PublicacionPagina:
    identificador: str
    mensaje: str
    creada: datetime
    enlace: str


def _fecha_meta(valor: str) -> datetime:
    # Meta devuelve "2026-09-08T07:10:03+0000".
    try:
        return datetime.strptime(valor, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return datetime.fromisoformat(valor)


def publicaciones_recientes(credenciales: Credenciales, limite: int = 25) -> list[PublicacionPagina]:
    """Lo que hay de verdad en la página, no lo que creemos haber publicado."""

    respuesta = graph_get(
        credenciales,
        f"{credenciales.pagina}/feed",
        {"fields": "id,message,created_time,permalink_url", "limit": str(limite)},
    )
    publicadas: list[PublicacionPagina] = []
    for elemento in respuesta.get("data", []):
        if not isinstance(elemento, dict):
            continue
        try:
            creada = _fecha_meta(str(elemento.get("created_time", "")))
        except ValueError:
            continue
        publicadas.append(
            PublicacionPagina(
                identificador=str(elemento.get("id", "")),
                mensaje=str(elemento.get("message", "")),
                creada=creada,
                enlace=str(elemento.get("permalink_url", "")),
            )
        )
    return publicadas


def firma(texto: str) -> str:
    """Huella estable de un texto para reconocerlo ya publicado.

    Ignora acentos, mayúsculas y espacios porque Facebook puede devolver el mensaje
    con saltos de línea normalizados.
    """

    plano = unicodedata.normalize("NFKD", texto)
    plano = "".join(letra for letra in plano if not unicodedata.combining(letra))
    return " ".join(plano.lower().split())[:90]


def ya_publicada(publicacion: Publicacion, publicadas: list[PublicacionPagina]) -> PublicacionPagina | None:
    objetivo = firma(publicacion.texto)
    for candidata in publicadas:
        if candidata.mensaje and firma(candidata.mensaje) == objetivo:
            return candidata
    return None


def resumen_github(lineas: list[str]) -> None:
    """Deja el resumen visible en la pestaña de la ejecución de GitHub Actions."""

    destino = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not destino:
        return
    try:
        with open(destino, "a", encoding="utf-8") as fichero:
            fichero.write("\n".join(lineas) + "\n")
    except OSError:
        pass


# --- Salud de la conexión --------------------------------------------------


@dataclass(frozen=True)
class Diagnostico:
    nombre_pagina: str
    usuario: str
    lee_publicaciones: bool
    caduca: datetime | None
    permisos: tuple[str, ...]
    avisos: tuple[str, ...]

    @property
    def dias_de_token(self) -> int | None:
        if self.caduca is None:
            return None
        return (self.caduca - datetime.now(timezone.utc)).days


# Con menos margen que esto conviene renovar el token antes de que pare la
# automatización sin avisar.
DIAS_AVISO_TOKEN = 21


def diagnostico_conexion(credenciales: Credenciales) -> Diagnostico:
    """Comprueba que la página responde, que se puede leer y que el token aguanta."""

    avisos: list[str] = []
    nombre = ""
    usuario = ""
    try:
        pagina = graph_get(credenciales, credenciales.pagina, {"fields": "name,username"})
        nombre = str(pagina.get("name", ""))
        usuario = str(pagina.get("username", ""))
    except ErrorGraph as exc:
        avisos.append(f"La página no responde con este token: {exc}")

    lee = True
    try:
        publicaciones_recientes(credenciales, limite=1)
    except ErrorGraph as exc:
        lee = False
        avisos.append(
            "No se pueden leer las publicaciones de la página, así que no hay "
            f"protección contra duplicados: {exc}"
        )

    caduca: datetime | None = None
    permisos: tuple[str, ...] = ()
    if credenciales.puede_revisar_token:
        try:
            respuesta = graph_get(
                credenciales,
                "debug_token",
                {
                    "input_token": credenciales.acceso,
                    "access_token": f"{credenciales.app_id}|{credenciales.app_secreto}",
                },
            )
            datos = respuesta.get("data", {}) if isinstance(respuesta, dict) else {}
            permisos = tuple(str(p) for p in datos.get("scopes", []))
            if not datos.get("is_valid", True):
                avisos.append("Meta marca el token como no válido: hay que renovarlo.")
            marca = int(datos.get("expires_at", 0) or 0)
            if marca:
                caduca = datetime.fromtimestamp(marca, tz=timezone.utc)
                restantes = (caduca - datetime.now(timezone.utc)).days
                if restantes <= DIAS_AVISO_TOKEN:
                    avisos.append(
                        f"El token caduca en {restantes} día(s) "
                        f"({caduca.date().isoformat()}): renuévalo esta semana."
                    )
            if permisos and "pages_manage_posts" not in permisos:
                avisos.append(
                    "Al token le falta el permiso pages_manage_posts: no podrá publicar."
                )
        except ErrorGraph as exc:
            avisos.append(f"No se ha podido comprobar la caducidad del token: {exc}")
    else:
        avisos.append(
            "Sin FACEBOOK_APP_ID y FACEBOOK_APP_SECRET no se puede avisar de la "
            "caducidad del token antes de que pare la automatización."
        )

    return Diagnostico(
        nombre_pagina=nombre,
        usuario=usuario,
        lee_publicaciones=lee,
        caduca=caduca,
        permisos=permisos,
        avisos=tuple(avisos),
    )
