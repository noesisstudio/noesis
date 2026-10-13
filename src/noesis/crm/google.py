"""Leer una pestaña de una hoja de cálculo de Google por su enlace.

La lista de captación vive en una hoja de Google que el founder ya usa. Para que
el CRM la lea no hace falta una cuenta de servicio ni pasar la revisión de Google
de un permiso sensible: basta con que la hoja esté compartida como «cualquier
persona con el enlace puede ver» (o publicada en la web) y Google la entrega en
CSV por una dirección fija.

Lo que hay que saber para operarlo:

* **Solo se lee.** Aquí no hay nada que escriba en la hoja. El camino de vuelta
  es al revés: la hoja lee el estado del CRM con `IMPORTDATA` (ver
  `sincronizar.py`). Así un fallo nuestro no puede pisar una celda suya.
* **Se pide la pestaña por su número (`gid`), no por su nombre.** La otra
  dirección de Google (`gviz`) acepta el nombre, pero devuelve la primera pestaña
  sin avisar si el nombre no existe y pierde celdas en columnas con números y
  texto mezclados, como los teléfonos. El `gid` va en el enlace que se copia con
  la pestaña abierta.
* **Una hoja sin compartir no da error: da la página de inicio de sesión.** Por
  eso se comprueba a dónde ha llevado la redirección y qué tipo de contenido ha
  llegado, y se explica en vez de intentar leer HTML como si fuera la lista.
* **Solo se sigue a Google.** La dirección la escribe una persona en un
  formulario: se acepta únicamente `docs.google.com` y las redirecciones a
  dominios de Google, para que esto no sirva de puente hacia otra máquina.

Es el adaptador de la integración (regla 7 de `AGENTS.md`): el resto de la carpeta
no sabe que detrás hay Google, solo que `descargar` devuelve un CSV. Si un día se
lee con una cuenta de servicio, cambia este archivo y nada más.
"""
from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

ANFITRION = "docs.google.com"
_ANFITRIONES_REDIRECCION = (".google.com", ".googleusercontent.com")
MAX_BYTES = 8 * 1024 * 1024
ESPERA_SEGUNDOS = 25
_RE_DOCUMENTO = re.compile(r"^/spreadsheets/d/([A-Za-z0-9_-]{20,})(?:/|$)")
_RE_PUBLICADO = re.compile(r"^/spreadsheets/d/e/([A-Za-z0-9_-]{20,})(?:/|$)")
_RE_GID = re.compile(r"(?:^|[?&#])gid=(\d+)")


class EnlaceNoValido(ValueError):
    """Lo pegado no es el enlace de una hoja de cálculo de Google."""


class HojaNoCompartida(RuntimeError):
    """Google pide iniciar sesión: la hoja no está compartida por enlace."""


class HojaNoDisponible(RuntimeError):
    """Google no ha entregado la hoja (borrada, caída o demasiado grande)."""


def analizar_enlace(url: str) -> dict:
    """Saca del enlace qué hoja es y qué pestaña. No hace ninguna petición."""
    partes = urllib.parse.urlsplit((url or "").strip())
    if partes.scheme != "https" or (partes.hostname or "").lower() != ANFITRION:
        raise EnlaceNoValido(
            "Pega el enlace de la hoja tal como sale en el navegador: empieza por "
            "https://docs.google.com/spreadsheets/…")
    gid = _RE_GID.search("?" + partes.query) or _RE_GID.search("#" + partes.fragment)
    publicado = _RE_PUBLICADO.match(partes.path)
    if publicado:
        return {"forma": "publicado", "id": publicado.group(1),
                "gid": gid.group(1) if gid else None}
    documento = _RE_DOCUMENTO.match(partes.path)
    if not documento:
        raise EnlaceNoValido(
            "Ese enlace es de Google, pero no de una hoja de cálculo.")
    return {"forma": "documento", "id": documento.group(1),
            "gid": gid.group(1) if gid else "0"}


def url_csv(url: str) -> str:
    """La dirección fija por la que Google entrega esa pestaña en CSV."""
    enlace = analizar_enlace(url)
    if enlace["forma"] == "publicado":
        consulta = {"output": "csv"}
        if enlace["gid"]:
            consulta.update({"gid": enlace["gid"], "single": "true"})
        return (f"https://{ANFITRION}/spreadsheets/d/e/{enlace['id']}/pub?"
                + urllib.parse.urlencode(consulta))
    return (f"https://{ANFITRION}/spreadsheets/d/{enlace['id']}/export?"
            + urllib.parse.urlencode({"format": "csv", "gid": enlace["gid"]}))


def url_canonica(url: str) -> str:
    """El enlace para abrir la hoja, sin parámetros de sesión ni de usuario."""
    enlace = analizar_enlace(url)
    if enlace["forma"] == "publicado":
        return (f"https://{ANFITRION}/spreadsheets/d/e/{enlace['id']}/pubhtml"
                + (f"?gid={enlace['gid']}&single=true" if enlace["gid"] else ""))
    return (f"https://{ANFITRION}/spreadsheets/d/{enlace['id']}/edit"
            f"#gid={enlace['gid']}")


def _de_google(url: str) -> bool:
    partes = urllib.parse.urlsplit(url)
    anfitrion = (partes.hostname or "").lower()
    return partes.scheme == "https" and (
        anfitrion == ANFITRION or anfitrion.endswith(_ANFITRIONES_REDIRECCION))


class _SoloGoogle(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _de_google(newurl):
            raise HojaNoDisponible("Google ha redirigido fuera de sus dominios.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _contexto_tls() -> ssl.SSLContext:
    """Verificación de certificados normal, con las raíces de `certifi` si están.

    En el servidor sobran: el sistema ya trae las suyas. En un Mac con el Python
    de python.org no las trae, y sin esto la lectura fallaría solo en local.
    """
    contexto = ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        return contexto
    contexto.load_verify_locations(certifi.where())
    return contexto


def descargar(url: str) -> str:
    """Trae la pestaña como texto CSV. Lanza una excepción con el motivo si no."""
    peticion = urllib.request.Request(  # noqa: S310 - anfitrión fijado en url_csv
        url_csv(url), headers={"User-Agent": "Bynoesis-CRM/1.0"})
    abridor = urllib.request.build_opener(
        _SoloGoogle, urllib.request.HTTPSHandler(context=_contexto_tls()))
    try:
        with abridor.open(peticion, timeout=ESPERA_SEGUNDOS) as respuesta:
            final = urllib.parse.urlsplit(respuesta.geturl()).hostname or ""
            tipo = (respuesta.headers.get("Content-Type") or "").lower()
            cuerpo = respuesta.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise HojaNoCompartida(_COMO_COMPARTIR) from exc
        if exc.code in (404, 410):
            raise HojaNoDisponible(
                "Google dice que esa hoja o esa pestaña ya no existe.") from exc
        raise HojaNoDisponible(
            f"Google ha contestado con un error ({exc.code}). Prueba en un "
            "rato.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HojaNoDisponible(
            "No he podido hablar con Google. Prueba en un rato.") from exc
    if final.startswith("accounts.") or "text/html" in tipo:
        raise HojaNoCompartida(_COMO_COMPARTIR)
    if len(cuerpo) > MAX_BYTES:
        raise HojaNoDisponible(
            "La pestaña pesa más de 8 MB. Deja en ella solo la lista.")
    return cuerpo.decode("utf-8-sig", errors="replace")


_COMO_COMPARTIR = (
    "Google pide iniciar sesión para ver esa hoja. Ábrela, pulsa «Compartir» y "
    "en «Acceso general» elige «Cualquier persona con el enlace» como lector.")
