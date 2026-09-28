"""Enviar correo desde el Gmail del propio autónomo, con su permiso.

El autónomo pulsa «Conectar mi Gmail», acepta en la pantalla de Google y a partir
de ahí sus facturas salen **desde su dirección** y le aparecen en su carpeta de
Enviados. Google no entrega su contraseña: entrega un permiso acotado
(`gmail.send`) que solo sirve para enviar, nunca para leer, y que él puede retirar
cuando quiera desde su cuenta.

Se habla con la API por HTTP con la biblioteca estándar, como el resto de
integraciones del proyecto: no hace falta el SDK de Google para tres llamadas.

Lo que hay que saber para operarlo:

* Mientras la aplicación esté en modo «pruebas» en Google Cloud, **el permiso
  caduca a los siete días** y el autónomo tendrá que reconectar. Es una regla de
  Google, no un fallo. Para clientes reales hay que publicar la pantalla de
  consentimiento y pasar su revisión.
* El `refresh_token` solo llega la **primera** vez que alguien autoriza. Por eso
  se pide `prompt=consent` y `access_type=offline`: sin ellos, reconectar
  devolvería una conexión que deja de funcionar en una hora.
* Si el autónomo retira el acceso, Google responde `invalid_grant`. Eso no es un
  error pasajero: la conexión está muerta y hay que decírselo, no reintentar.
* Un 401 al enviar NO significa lo mismo: suele ser un permiso de una hora que ha
  caducado antes de tiempo. Se renueva y se reintenta una vez.
* La pantalla de Google deja desmarcar cada permiso. Si el autónomo quita el de
  enviar, se le dice al conectar, no en el primer envío fallido.
* Solo salen por aquí los correos a **sus clientes** (`TIPOS_PROPIOS`). Los avisos de
  Bynoesis al propio autónomo, como recuperar la contraseña, siguen saliendo de
  Bynoesis: mandárselos desde su propio Gmail a sí mismo no tendría sentido.
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr

from .. import config, db

log = logging.getLogger(__name__)

AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
ENVIAR = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
# Qué dirección se ha conectado. `gmail.send` no deja leer ni el perfil de Gmail
# (users.getProfile exige un permiso de lectura), así que se pregunta a OpenID.
USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"
# El único permiso sobre el correo. Pedir además leerlo lo convertiría en un
# permiso «restringido», que exige auditoría de seguridad y meses de revisión.
SCOPE = "https://www.googleapis.com/auth/gmail.send"
# `openid` y `email` solo sirven para saber la dirección conectada; son permisos
# básicos que no añaden revisión de Google.
SCOPES = ("openid", "email", SCOPE)
# Correos que salen desde el Gmail del autónomo: los dirigidos a sus clientes.
TIPOS_PROPIOS = frozenset({"invoice", "client_message"})
_MARGEN = timedelta(minutes=5)


class CuentaRevocada(RuntimeError):
    """El autónomo retiró el acceso: no tiene sentido reintentar."""


class PermisoIncompleto(RuntimeError):
    """Se autorizó la cuenta, pero sin marcar el permiso de enviar correo."""


class _TokenRechazado(RuntimeError):
    """Google no aceptó el permiso de una hora: se renueva y se reintenta una vez."""


def configurado() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)


def url_de_autorizacion(business_id: int, estado: str) -> str:
    """Enlace al que se manda al autónomo para que autorice."""
    if not configurado():
        raise ValueError(
            "Conectar Gmail no está disponible: faltan GOOGLE_CLIENT_ID y "
            "GOOGLE_CLIENT_SECRET en el servidor.")
    parametros = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        # Sin estos dos no llega `refresh_token` y la conexión moriría en una hora.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": estado,
    }
    return f"{AUTORIZAR}?{urllib.parse.urlencode(parametros)}"


def _peticion(url: str, *, datos: dict | None = None,
              cabeceras: dict | None = None, cuerpo: bytes | None = None) -> dict:
    """Una llamada a Google, con los fallos traducidos a lo que hay que hacer.

    * `invalid_grant` al renovar → la conexión está muerta (`CuentaRevocada`).
    * 403 por falta de permiso → también: sin él no se podrá enviar nunca.
    * 401 → permiso de una hora rechazado (`_TokenRechazado`): se renueva.
    * Cualquier otra cosa, incluida la red, es pasajera y se reintenta después.

    La respuesta en bruto de Google va al log, nunca al mensaje: puede acabar en
    una pantalla o en `/admin` y no le dice nada útil a un autónomo.
    """
    if datos is not None:
        cuerpo = urllib.parse.urlencode(datos).encode()
        cabeceras = {**(cabeceras or {}),
                     "Content-Type": "application/x-www-form-urlencoded"}
    peticion = urllib.request.Request(url, data=cuerpo,
                                      headers=cabeceras or {})
    try:
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            return json.loads(respuesta.read(1_000_000) or b"{}")
    except urllib.error.HTTPError as exc:
        detalle = exc.read(2000).decode(errors="replace")
        log.warning("Google respondió %s en %s: %s", exc.code,
                    urllib.parse.urlsplit(url).path, detalle[:300])
        if "invalid_grant" in detalle:
            raise CuentaRevocada(
                "Google ya no acepta esta conexión. Lo normal es que se haya "
                "retirado el acceso desde la cuenta de Google, o que haya "
                "caducado por estar la aplicación en modo de pruebas."
            ) from exc
        if exc.code == 403 and ("insufficient" in detalle.lower()
                                or "ACCESS_TOKEN_SCOPE" in detalle):
            raise CuentaRevocada(
                "La cuenta de Google no tiene el permiso de enviar correo. "
                "Vuelve a conectarla y deja marcada la casilla de enviar."
            ) from exc
        if exc.code == 401:
            raise _TokenRechazado("Google no aceptó el permiso temporal.") from exc
        raise RuntimeError(
            f"Google no ha podido atenderlo ahora (código {exc.code}). "
            "Se reintentará solo.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            "No se ha podido hablar con Google (red). Se reintentará solo."
        ) from exc


def canjear_codigo(code: str) -> dict:
    """Cambia el código de la vuelta de Google por los tokens."""
    recibido = _peticion(TOKEN, datos={
        "code": code,
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    if not recibido.get("refresh_token"):
        # Sin él la conexión duraría una hora. Mejor decirlo ahora que dejar que
        # falle el primer envío de dentro de un rato.
        raise RuntimeError(
            "Google no ha devuelto un permiso duradero. Entra en tu cuenta de "
            "Google, quita el acceso de Bynoesis y vuelve a conectarla.")
    concedidos = set(str(recibido.get("scope") or "").split())
    if SCOPE not in concedidos:
        # La pantalla de Google deja desmarcar cada permiso. Guardarlo así daría
        # una conexión «buena» que fallaría en cada envío.
        raise PermisoIncompleto(
            "Google ha conectado la cuenta, pero sin el permiso de enviar correo. "
            "Vuelve a conectarla y deja marcada la casilla «Enviar correo "
            "electrónico en tu nombre».")
    return recibido


def correo_de_la_cuenta(access_token: str) -> str:
    """Qué dirección ha conectado, para enseñarla en Ajustes y firmar el remitente.

    Si Google no la confirma se devuelve vacío: Gmail envía igualmente desde la
    cuenta autorizada, solo que no se podrá mostrar cuál es.
    """
    try:
        perfil = _peticion(USERINFO,
                           cabeceras={"Authorization": f"Bearer {access_token}"})
    except (RuntimeError, CuentaRevocada):
        return ""
    correo = str(perfil.get("email") or "").strip().lower()
    if perfil.get("email_verified") not in {True, "true"} or "@" not in correo:
        return ""
    return correo


def _access_token_vigente(business_id: int, *, forzar: bool = False) -> tuple[str, str]:
    """Devuelve `(access_token, correo)`, renovándolo si hace falta o si se fuerza."""
    cuenta = db.get_oauth_credentials(business_id, "google")
    if not cuenta or cuenta.get("status") != "active":
        raise CuentaRevocada("No hay ninguna cuenta de Google conectada.")
    if not cuenta.get("refresh_token"):
        raise CuentaRevocada(
            "La conexión guardada ya no se puede leer. Vuelve a conectar la "
            "cuenta de Google desde Ajustes.")
    caduca = str(cuenta.get("expires_at") or "")
    if not forzar and cuenta.get("access_token") and caduca:
        try:
            if datetime.fromisoformat(caduca) - _MARGEN > datetime.now():
                return cuenta["access_token"], cuenta.get("account_email") or ""
        except ValueError:
            pass
    nuevo = _peticion(TOKEN, datos={
        "refresh_token": cuenta["refresh_token"],
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "grant_type": "refresh_token",
    })
    access = str(nuevo.get("access_token") or "")
    if not access:
        raise CuentaRevocada("Google no ha renovado el permiso de esta cuenta.")
    vence = (datetime.now() + timedelta(seconds=int(nuevo.get("expires_in", 3600)))
             ).isoformat(timespec="seconds")
    db.save_oauth_credentials(business_id, "google", access_token=access,
                              expires_at=vence)
    return access, cuenta.get("account_email") or ""


def disponible(business_id: int) -> bool:
    """¿Puede este negocio enviar desde su propio Gmail ahora mismo?"""
    if not configurado():
        return False
    cuenta = db.get_oauth_credentials(business_id, "google")
    return bool(cuenta and cuenta.get("status") == "active"
                and cuenta.get("refresh_token"))


def enviar(business_id: int, destino: str, asunto: str, cuerpo: str,
           adjuntos: list[tuple[str, bytes, str, str]] | None = None) -> bool:
    """Envía desde el Gmail conectado. El correo queda en SU carpeta de Enviados.

    Una cuenta revocada se anota como tal y no se reintenta: reintentar algo que
    el usuario ha retirado a propósito solo consume intentos y esconde el motivo.
    """
    try:
        access, remitente = _access_token_vigente(business_id)
        crudo = _mensaje_crudo(business_id, remitente, destino, asunto, cuerpo, adjuntos)
        try:
            respuesta = _enviar_crudo(access, crudo)
        except _TokenRechazado:
            # Permiso de una hora rechazado antes de tiempo: se pide otro y se
            # reintenta una sola vez. Si el nuevo también falla, no es pasajero.
            access, _ = _access_token_vigente(business_id, forzar=True)
            try:
                respuesta = _enviar_crudo(access, crudo)
            except _TokenRechazado as exc:
                raise CuentaRevocada(
                    "Google rechaza el permiso incluso recién renovado. Vuelve a "
                    "conectar la cuenta de Google desde Ajustes.") from exc
    except CuentaRevocada as exc:
        db.mark_oauth_credentials(business_id, "google", status="revoked",
                                  error=str(exc))
        raise
    return bool(respuesta.get("id"))


def _mensaje_crudo(business_id: int, remitente: str, destino: str, asunto: str,
                   cuerpo: str, adjuntos) -> str:
    mensaje = EmailMessage()
    mensaje["To"] = destino
    mensaje["Subject"] = asunto
    if remitente:
        # El cliente ve el nombre del negocio, no solo una dirección de Gmail.
        nombre = str((db.get_business(business_id) or {}).get("name") or "").strip()
        mensaje["From"] = formataddr((nombre, remitente)) if nombre else remitente
    mensaje.set_content(cuerpo)
    for nombre_adjunto, datos, tipo, subtipo in adjuntos or []:
        mensaje.add_attachment(datos, maintype=tipo, subtype=subtipo,
                               filename=nombre_adjunto)
    return base64.urlsafe_b64encode(mensaje.as_bytes()).decode("ascii")


def _enviar_crudo(access: str, crudo: str) -> dict:
    return _peticion(
        ENVIAR,
        cuerpo=json.dumps({"raw": crudo}).encode(),
        cabeceras={"Authorization": f"Bearer {access}",
                   "Content-Type": "application/json"})
