"""Comprueba contra Meta que el canal de WhatsApp puede funcionar.

Solo hace lecturas: no envia ningun mensaje ni cambia nada en Meta. Contesta a
las cuatro preguntas que bloquean una prueba real con el numero:

1. El token, si esta vivo, hasta cuando y con que permisos.
2. El numero, si responde y en que estado de calidad esta.
3. La suscripcion, si Meta llama a nuestra URL y con el campo `messages`.
4. Las plantillas, si las nueve que usa el codigo estan de alta y aprobadas.
5. El webhook desplegado, si devuelve el challenge con el verify token vigente.
6. La firma, si el servidor valida `X-Hub-Signature-256` con el secreto vigente.

Uso:

    python scripts/check_whatsapp.py
    python scripts/check_whatsapp.py --url https://bynoesis.com

Lee las credenciales del entorno; si hay un `.env` en la raiz, lo carga antes.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

OK, AVISO, FALLO = "[OK]", "[AVISO]", "[FALLO]"
_fallos = 0


def _cargar_env() -> None:
    """Carga el .env de la raiz sin depender de python-dotenv."""
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip())


def _decir(nivel: str, texto: str, pista: str = "") -> None:
    global _fallos
    if nivel == FALLO:
        _fallos += 1
    print(f"{nivel} {texto}")
    if pista:
        print(f"  -> {pista}")


def _graph(camino: str, token: str, version: str, **params) -> dict:
    """GET a la Graph API. Devuelve el JSON, con el error de Meta si lo hay."""
    url = f"https://graph.facebook.com/{version}/{camino}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    peticion = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            return json.loads(respuesta.read())
    except urllib.error.HTTPError as error:
        try:
            return json.loads(error.read())
        except Exception:
            return {"error": {"message": f"HTTP {error.code}"}}
    except Exception as error:  # red caida, DNS, timeout
        return {"error": {"message": str(error)}}


def _error(datos: dict) -> str:
    return str(datos.get("error", {}).get("message", "")) if "error" in datos else ""


# ------------------------------------------------------------------ token --- #
def revisar_token(token: str, version: str) -> str:
    """Comprueba el token y devuelve el id de la app a la que pertenece."""
    datos = _graph("debug_token", token, version, input_token=token)
    fallo = _error(datos)
    if fallo:
        _decir(
            FALLO,
            f"El token no vale: {fallo}",
            "Genera uno permanente con un usuario del sistema en Configuracion del negocio.",
        )
        return ""
    info = datos.get("data", {})
    if not info.get("is_valid"):
        _decir(FALLO, "Meta marca el token como no valido.")
        return ""
    caduca = info.get("expires_at", 0)
    permisos = set(info.get("scopes", []))
    if caduca == 0:
        _decir(OK, "Token valido y sin fecha de caducidad.")
    else:
        cuando = datetime.fromtimestamp(caduca, timezone.utc)
        dias = (cuando - datetime.now(timezone.utc)).days
        nivel = OK if dias > 30 else AVISO
        _decir(
            nivel,
            f"Token valido, caduca el {cuando:%Y-%m-%d} (quedan {dias} dias).",
            "" if dias > 30 else "Cambialo por un token de usuario del sistema sin caducidad.",
        )
    for permiso in ("whatsapp_business_messaging", "whatsapp_business_management"):
        if permiso in permisos:
            _decir(OK, f"Permiso concedido: {permiso}.")
        else:
            _decir(FALLO, f"Falta el permiso {permiso}.", "Anadelo al generar el token.")
    return str(info.get("app_id", ""))


# ------------------------------------------------------------ suscripcion --- #
def revisar_suscripcion(app_id: str, app_secret: str, version: str, base: str) -> None:
    """Comprueba que Meta tiene registrado nuestro webhook y el campo messages."""
    if not app_id or not app_secret:
        _decir(AVISO, "Sin app_id o app_secret: no se puede leer la suscripcion del webhook.")
        return
    # El token de app se forma con id|secreto; solo sirve para leer la configuracion.
    datos = _graph(f"{app_id}/subscriptions", f"{app_id}|{app_secret}", version)
    fallo = _error(datos)
    if fallo:
        _decir(FALLO, f"No se puede leer la suscripcion del webhook: {fallo}")
        return
    esperado = base.rstrip("/") + "/webhook/whatsapp"
    for entrada in datos.get("data", []):
        if entrada.get("object") != "whatsapp_business_account":
            continue
        url = entrada.get("callback_url", "")
        campos = {campo.get("name") for campo in entrada.get("fields", [])}
        if url != esperado:
            _decir(FALLO, f"Meta llama a {url}, no a {esperado}.")
        elif not entrada.get("active"):
            _decir(FALLO, "La suscripcion existe pero esta inactiva.")
        else:
            _decir(OK, f"Meta tiene registrado {url} y esta activa.")
        if "messages" in campos:
            _decir(OK, "Campo 'messages' suscrito: los mensajes entrantes llegaran.")
        else:
            _decir(FALLO, "Falta suscribir el campo 'messages'.", "Hazlo en Webhooks > Administrar.")
        versiones = {campo.get("version") for campo in entrada.get("fields", [])}
        if versiones and version not in versiones:
            _decir(
                AVISO,
                f"Meta sirve los campos en {sorted(versiones)} y el codigo pide {version}.",
                "Revisa META_GRAPH_VERSION antes de que Meta retire la version.",
            )
        return
    _decir(
        FALLO,
        "La app no tiene ningun webhook de whatsapp_business_account registrado.",
        "Configuralo en Casos de uso > Paso 2 > Webhooks.",
    )


# ----------------------------------------------------------------- numero --- #
def revisar_numero(token: str, version: str, phone_id: str) -> None:
    campos = (
        "display_phone_number,verified_name,quality_rating,"
        "code_verification_status,account_mode"
    )
    datos = _graph(phone_id, token, version, fields=campos)
    fallo = _error(datos)
    if fallo:
        _decir(FALLO, f"No se puede leer el numero {phone_id}: {fallo}")
        return
    numero = datos.get("display_phone_number", "?")
    nombre = datos.get("verified_name", "sin nombre")
    calidad = datos.get("quality_rating", "?")
    verificacion = datos.get("code_verification_status", "?")
    _decir(
        OK,
        f"Numero {numero} ({nombre}), calidad {calidad}, verificacion {verificacion}.",
    )
    if datos.get("account_mode") == "SANDBOX":
        _decir(AVISO, "El numero esta en modo sandbox: solo escribe a destinatarios de prueba.")


# ------------------------------------------------------------- plantillas --- #
def revisar_plantillas(token: str, version: str, waba_id: str) -> None:
    from noesis import whatsapp_templates

    if not waba_id:
        _decir(
            AVISO,
            "Sin id de cuenta de WhatsApp: no se pueden comprobar las plantillas.",
            "Pasa --waba con el id que aparece en WhatsApp Manager.",
        )
        return
    datos = _graph(
        f"{waba_id}/message_templates",
        token,
        version,
        fields="name,status,language",
        limit=100,
    )
    fallo = _error(datos)
    if fallo:
        _decir(FALLO, f"No se pueden listar las plantillas: {fallo}")
        return
    idioma = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "es")
    en_meta = {
        (item["name"], item.get("language", "")): item.get("status", "?")
        for item in datos.get("data", [])
    }
    for spec in whatsapp_templates.SPECS:
        estado = en_meta.get((spec.name, idioma))
        if estado is None:
            _decir(
                FALLO,
                f"Falta en Meta la plantilla {spec.name} ({idioma}).",
                "Creala con el cuerpo de: python -m noesis.whatsapp_templates",
            )
        elif estado == "APPROVED":
            _decir(OK, f"Plantilla {spec.name}: aprobada.")
        else:
            _decir(AVISO, f"Plantilla {spec.name}: {estado}.")


# ---------------------------------------------------------------- webhook --- #
def _challenge(url: str, verify_token: str, reto: str) -> tuple[int, str]:
    """Pide el challenge al webhook. Devuelve (codigo HTTP, cuerpo)."""
    consulta = urllib.parse.urlencode(
        {"hub.mode": "subscribe", "hub.verify_token": verify_token, "hub.challenge": reto}
    )
    try:
        with urllib.request.urlopen(f"{url}?{consulta}", timeout=30) as respuesta:
            return respuesta.status, respuesta.read().decode("utf-8", "replace").strip()
    except urllib.error.HTTPError as error:
        return error.code, ""


def revisar_webhook(base: str, verify_token: str) -> None:
    if not verify_token:
        _decir(FALLO, "WHATSAPP_VERIFY_TOKEN esta vacio.")
        return
    reto = "noesis-comprobacion"
    url = base.rstrip("/") + "/webhook/whatsapp"
    try:
        codigo, cuerpo = _challenge(url, verify_token, reto)
    except Exception as error:
        _decir(FALLO, f"No se llega a {url}: {error}")
        return
    if codigo != 200:
        _decir(
            FALLO,
            f"El webhook {url} contesta HTTP {codigo}.",
            "El verify token del servidor no coincide con el local. Igualalos en Railway.",
        )
    elif cuerpo == reto:
        _decir(OK, f"El webhook {url} devuelve el challenge: Meta podra suscribirlo.")
    else:
        _decir(FALLO, f"El webhook contesta 200 pero devuelve {cuerpo!r} en vez del challenge.")
    # Un token falso tiene que rechazarse, aunque el servidor este bien configurado.
    try:
        codigo_falso, _ = _challenge(url, "token-falso", reto)
    except Exception as error:
        _decir(AVISO, f"No se pudo probar el verify token falso: {error}")
        return
    if codigo_falso == 403:
        _decir(OK, "Un verify token falso se rechaza con 403.")
    elif codigo_falso == 200:
        _decir(
            FALLO,
            "El webhook acepta un verify token falso.",
            "Revisa WHATSAPP_VERIFY_TOKEN en el servidor: parece vacio.",
        )
    else:
        _decir(AVISO, f"Un verify token falso devuelve HTTP {codigo_falso}, se esperaba 403.")


def revisar_firma(base: str, app_secret: str) -> None:
    """Comprueba que el servidor valida X-Hub-Signature-256 con el secreto vigente.

    Manda un sobre de webhook sin eventos: pasa por la verificacion de firma y no
    crea ningun dato. Es la unica forma de saber que el secreto desplegado coincide
    con el de Meta sin esperar a un mensaje real.
    """
    if not app_secret:
        _decir(FALLO, "WHATSAPP_APP_SECRET esta vacio: no se puede firmar nada.")
        return
    url = base.rstrip("/") + "/webhook/whatsapp"
    cuerpo = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
    firma = hmac.new(app_secret.encode(), cuerpo, hashlib.sha256).hexdigest()

    def _post(cabecera: str) -> int:
        peticion = urllib.request.Request(
            url,
            data=cuerpo,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": cabecera},
        )
        try:
            with urllib.request.urlopen(peticion, timeout=30) as respuesta:
                return respuesta.status
        except urllib.error.HTTPError as error:
            return error.code

    try:
        bueno = _post(f"sha256={firma}")
        malo = _post("sha256=" + "0" * 64)
    except Exception as error:
        _decir(AVISO, f"No se pudo probar la firma: {error}")
        return
    if bueno == 200:
        _decir(OK, "El servidor acepta un webhook firmado: el app secret desplegado es correcto.")
    else:
        _decir(
            FALLO,
            f"Un webhook bien firmado devuelve HTTP {bueno}.",
            "WHATSAPP_APP_SECRET del servidor no coincide con el de Meta. Igualalo en Railway.",
        )
    if malo == 401:
        _decir(OK, "Una firma falsa se rechaza con 401.")
    else:
        _decir(FALLO, f"Una firma falsa devuelve HTTP {malo}, se esperaba 401.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comprobador del canal de WhatsApp.")
    parser.add_argument(
        "--url",
        default=os.getenv("NOESIS_BASE_URL", "https://bynoesis.com"),
        help="Base del despliegue cuyo webhook se comprueba.",
    )
    parser.add_argument("--waba", default="", help="Id de la cuenta de WhatsApp Business.")
    parser.add_argument(
        "--sin-red", action="store_true", help="Solo comprueba el webhook, no llama a Meta."
    )
    args = parser.parse_args(argv)

    _cargar_env()
    token = os.getenv("WHATSAPP_TOKEN", "")
    phone_id = os.getenv("WHATSAPP_PHONE_ID", "")
    version = os.getenv("META_GRAPH_VERSION", "v23.0")

    print(f"Noesis - canal de WhatsApp (Graph {version})")
    if not args.sin_red:
        if not token:
            _decir(FALLO, "WHATSAPP_TOKEN esta vacio.")
        else:
            app_id = revisar_token(token, version)
            if phone_id:
                revisar_numero(token, version, phone_id)
            else:
                _decir(FALLO, "WHATSAPP_PHONE_ID esta vacio.")
            revisar_suscripcion(app_id, os.getenv("WHATSAPP_APP_SECRET", ""), version, args.url)
            revisar_plantillas(token, version, args.waba or os.getenv("WHATSAPP_WABA_ID", ""))
    revisar_webhook(args.url, os.getenv("WHATSAPP_VERIFY_TOKEN", ""))
    revisar_firma(args.url, os.getenv("WHATSAPP_APP_SECRET", ""))

    print(f"\nFallos que bloquean la prueba: {_fallos}")
    return 1 if _fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
