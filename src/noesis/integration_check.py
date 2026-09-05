"""Comprobaciones externas de solo lectura para preparar el piloto.

El doctor verifica presencia y coherencia local. Este comando da el siguiente paso:
consulta, sin crear cargos ni enviar mensajes, los catálogos de Stripe, Brevo y
Groq. Google solo permite verificar el proveedor y la forma de la configuración;
la credencial OAuth necesita siempre una prueba humana de inicio de sesión.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from . import config
from .documents import ocr, pdf_ocr


@dataclass(frozen=True)
class IntegrationCheck:
    area: str
    status: str
    summary: str
    action: str = ""


def _json_get(url: str, headers: dict[str, str] | None = None) -> dict:
    request = Request(
        url,
        headers={"accept": "application/json", **(headers or {})},
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"HTTP {response.status}")
            return json.loads(response.read(2_000_000).decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("sin conexión con el proveedor") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("respuesta no válida del proveedor") from exc


def _sender_email() -> str:
    raw = (config.SMTP_FROM or "").strip()
    match = re.search(r"<([^>]+)>", raw)
    return (match.group(1) if match else raw).strip().lower()


def _check_ocr() -> IntegrationCheck:
    languages = set(ocr.installed_languages())
    missing = sorted(set(ocr.PREFERRED_LANGUAGES) - languages)
    image_ok = ocr.available()
    pdf_ok = pdf_ocr.available()
    if image_ok and pdf_ok and not missing:
        return IntegrationCheck(
            "ocr", "ok", "Foto y PDF escaneado disponibles en cat/spa/eng.",
            "Ejecuta el corpus de aceptación con documentos reales anonimizados.",
        )
    reasons = []
    if not image_ok:
        reasons.append("Tesseract/Pillow no operativo")
    if not pdf_ok:
        reasons.append("OCR de PDF no operativo")
    if missing:
        reasons.append("idiomas ausentes: " + ", ".join(missing))
    return IntegrationCheck(
        "ocr", "blocker", "; ".join(reasons) + ".",
        "Instala el runtime declarado en railpack.json y vuelve a comprobar.",
    )


def _check_google(*, network: bool) -> IntegrationCheck:
    if not config.GOOGLE_OAUTH_CLIENT_ID and not config.GOOGLE_OAUTH_CLIENT_SECRET:
        return IntegrationCheck(
            "google", "skipped", "Google OAuth todavía no está configurado.",
            "Añade las dos variables y registra el callback exacto.",
        )
    if not config.google_oauth_available():
        return IntegrationCheck(
            "google", "blocker", "Google OAuth está configurado a medias.",
            "Completa Client ID y Client secret en el mismo entorno.",
        )
    if not config.GOOGLE_OAUTH_CLIENT_ID.endswith(".apps.googleusercontent.com"):
        return IntegrationCheck(
            "google", "blocker", "El Client ID no tiene el formato de Google.",
            "Copia el identificador de un cliente OAuth de aplicación web.",
        )
    if not network:
        return IntegrationCheck(
            "google", "warning", "Configuración local coherente; red no comprobada.",
            "Ejecuta con --network y después prueba alta y acceso en el navegador.",
        )
    try:
        discovery = _json_get(
            "https://accounts.google.com/.well-known/openid-configuration"
        )
    except RuntimeError as exc:
        return IntegrationCheck(
            "google", "blocker", f"Google OpenID no respondió ({exc}).",
            "Revisa DNS/salida HTTPS del despliegue.",
        )
    required = ("authorization_endpoint", "token_endpoint", "jwks_uri")
    if not all(discovery.get(key) for key in required):
        return IntegrationCheck(
            "google", "blocker", "La configuración OpenID recibida está incompleta.",
            "No abras el acceso con Google hasta repetir la prueba.",
        )
    return IntegrationCheck(
        "google", "warning",
        "Proveedor OpenID accesible y credenciales con formato coherente.",
        "Pendiente la prueba humana: alta nueva, cuenta existente, cancelación y state inválido.",
    )


def _check_brevo(*, network: bool) -> IntegrationCheck:
    if not config.BREVO_API_KEY:
        return IntegrationCheck(
            "correo", "skipped", "Brevo todavía no está configurado.",
            "Verifica el dominio y añade BREVO_API_KEY y SMTP_FROM.",
        )
    sender = _sender_email()
    if not sender or "@" not in sender:
        return IntegrationCheck(
            "correo", "blocker", "SMTP_FROM no contiene un remitente válido.",
            "Usa Bynoesis <no-reply@bynoesis.com>.",
        )
    if not network:
        return IntegrationCheck(
            "correo", "warning", "Brevo configurado; clave y remitente no comprobados.",
            "Ejecuta con --network.",
        )
    headers = {"api-key": config.BREVO_API_KEY}
    try:
        _json_get("https://api.brevo.com/v3/account", headers)
        senders = _json_get("https://api.brevo.com/v3/senders", headers)
    except RuntimeError as exc:
        return IntegrationCheck(
            "correo", "blocker", f"Brevo rechazó la comprobación ({exc}).",
            "Regenera la API key o revisa la salida HTTPS.",
        )
    active = {
        str(item.get("email") or "").strip().lower()
        for item in senders.get("senders", [])
        if item.get("active")
    }
    if sender not in active:
        return IntegrationCheck(
            "correo", "blocker", "La API key funciona, pero el remitente no está activo.",
            f"Verifica {sender} y autentica bynoesis.com en Brevo.",
        )
    return IntegrationCheck(
        "correo", "ok", "API de Brevo y remitente activo comprobados.",
        "Envía recuperación, invitación de gestoría y factura a Gmail y Outlook.",
    )


_STRIPE_PRICES = (
    ("Autónomo mensual", "STRIPE_PRICE_AUTONOMO", 2_900, "month"),
    ("Negocio mensual", "STRIPE_PRICE_PRO", 4_900, "month"),
    ("Premium mensual", "STRIPE_PRICE_PREMIUM", 9_900, "month"),
    ("Autónomo anual", "STRIPE_PRICE_AUTONOMO_ANNUAL", 31_900, "year"),
    ("Negocio anual", "STRIPE_PRICE_PRO_ANNUAL", 53_900, "year"),
    ("Premium anual", "STRIPE_PRICE_PREMIUM_ANNUAL", 108_900, "year"),
)


def _check_stripe(*, network: bool) -> IntegrationCheck:
    secret = config.STRIPE_SECRET_KEY.strip()
    webhook = config.STRIPE_WEBHOOK_SECRET.strip()
    prices = [(label, name, getattr(config, name).strip(), amount, interval)
              for label, name, amount, interval in _STRIPE_PRICES]
    present = [bool(secret), bool(webhook), *(bool(item[2]) for item in prices)]
    if not any(present):
        return IntegrationCheck(
            "stripe", "skipped", "Stripe todavía no está configurado.",
            "Añade la clave, el webhook y los seis price_id del mismo entorno.",
        )
    if not all(present):
        missing = []
        if not secret:
            missing.append("STRIPE_SECRET_KEY")
        if not webhook:
            missing.append("STRIPE_WEBHOOK_SECRET")
        missing.extend(name for _label, name, value, _amount, _interval in prices if not value)
        return IntegrationCheck(
            "stripe", "blocker", "Configuración incompleta: " + ", ".join(missing) + ".",
            "Completa todas las variables con valores del mismo modo test/live.",
        )
    if not secret.startswith(("sk_test_", "sk_live_")):
        return IntegrationCheck(
            "stripe", "blocker", "STRIPE_SECRET_KEY no tiene formato sk_test_/sk_live_.",
            "Usa la clave secreta, nunca la publicable pk_ ni un secreto de webhook.",
        )
    if len({item[2] for item in prices}) != len(prices):
        return IntegrationCheck(
            "stripe", "blocker", "Hay price_id duplicados entre planes o períodos.",
            "Copia de nuevo los seis identificadores del catálogo.",
        )
    if not webhook.startswith("whsec_"):
        return IntegrationCheck(
            "stripe", "blocker", "El secreto de webhook no tiene formato whsec_.",
            "Usa el secreto de firma del destino, no la clave secreta de Stripe.",
        )
    if not network:
        return IntegrationCheck(
            "stripe", "warning", "Variables completas; catálogo remoto no comprobado.",
            "Ejecuta con --network antes de otro Checkout.",
        )
    errors = []
    expected_live = secret.startswith("sk_live_")
    headers = {"Authorization": f"Bearer {secret}"}
    for label, _name, price_id, amount, interval in prices:
        try:
            price = _json_get(
                "https://api.stripe.com/v1/prices/" + quote(price_id, safe=""),
                headers,
            )
        except RuntimeError as exc:
            errors.append(f"{label}: {exc}")
            continue
        recurring = price.get("recurring") or {}
        if not price.get("active"):
            errors.append(f"{label}: inactivo")
        if price.get("currency") != "eur" or price.get("unit_amount") != amount:
            errors.append(f"{label}: importe o moneda incorrectos")
        if recurring.get("interval") != interval or recurring.get("interval_count") != 1:
            errors.append(f"{label}: periodicidad incorrecta")
        if price.get("tax_behavior") != "exclusive":
            errors.append(f"{label}: tax_behavior debe ser exclusive")
        if bool(price.get("livemode")) != expected_live:
            errors.append(f"{label}: pertenece a otro entorno")
    if errors:
        return IntegrationCheck(
            "stripe", "blocker", " | ".join(errors[:8]),
            "Corrige el catálogo; Bynoesis comunica precios sin IVA.",
        )
    return IntegrationCheck(
        "stripe", "ok", "Seis precios activos, EUR, recurrentes y con IVA exclusivo.",
        "Completa Checkout, portal, impago, reactivación y webhooks firmados.",
    )


def _check_groq(*, network: bool) -> IntegrationCheck:
    if not config.GROQ_API_KEY:
        return IntegrationCheck(
            "voz", "skipped", "Groq no está configurado; puede usarse Whisper privado.",
            "Añade GROQ_API_KEY solo si el servidor no soporta faster-whisper.",
        )
    if not network:
        return IntegrationCheck(
            "voz", "warning", "Groq configurado; clave y modelo no comprobados.",
            "Ejecuta con --network.",
        )
    try:
        payload = _json_get(
            "https://api.groq.com/openai/v1/models",
            {"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        )
    except RuntimeError as exc:
        return IntegrationCheck(
            "voz", "blocker", f"Groq rechazó la comprobación ({exc}).",
            "Regenera la clave o revisa la salida HTTPS.",
        )
    models = {str(item.get("id") or "") for item in payload.get("data", [])}
    if config.GROQ_WHISPER_MODEL not in models:
        return IntegrationCheck(
            "voz", "blocker", "La clave funciona, pero el modelo Whisper no está activo.",
            "Actualiza GROQ_WHISPER_MODEL con un modelo de transcripción disponible.",
        )
    return IntegrationCheck(
        "voz", "ok", "Clave Groq y modelo Whisper comprobados.",
        "Prueba audio ca/es/en, silencio, duración larga y formato no admitido.",
    )


def _check_backups() -> IntegrationCheck:
    values = (
        config.BACKUP_S3_ENDPOINT, config.BACKUP_S3_BUCKET,
        config.BACKUP_S3_ACCESS_KEY, config.BACKUP_S3_SECRET_KEY,
    )
    if not any(values):
        return IntegrationCheck(
            "copias", "skipped", "Copia externa S3 todavía no configurada.",
            "Crea bucket privado, usuario limitado, versionado y retención.",
        )
    if not all(values):
        return IntegrationCheck(
            "copias", "blocker", "La configuración S3 está incompleta.",
            "Completa endpoint, bucket, access key y secret key.",
        )
    if not all((
        config.BACKUP_S3_REGION,
        config.BACKUP_S3_PROVIDER_NAME,
        config.BACKUP_S3_DATA_REGION,
    )):
        return IntegrationCheck(
            "copias", "blocker",
            "Falta identificar la región de firma, el proveedor o la residencia de datos.",
            "Configura NOESIS_BACKUP_S3_REGION, _PROVIDER_NAME y _DATA_REGION.",
        )
    endpoint = urlsplit(config.BACKUP_S3_ENDPOINT)
    if endpoint.scheme != "https" or not endpoint.hostname:
        return IntegrationCheck(
            "copias", "blocker", "El endpoint S3 no es una URL HTTPS válida.",
            "Usa el endpoint S3 regional, no la URL pública del panel.",
        )
    return IntegrationCheck(
        "copias", "warning",
        f"S3 configurado en {config.BACKUP_S3_PROVIDER_NAME} "
        f"({config.BACKUP_S3_DATA_REGION}); restauración no demostrada.",
        "Ejecuta un backup y después noesis-restore-check en un entorno aislado.",
    )


def collect_checks(*, network: bool = False) -> dict:
    checks = [
        _check_ocr(),
        _check_brevo(network=network),
        _check_google(network=network),
        _check_stripe(network=network),
        _check_groq(network=network),
        _check_backups(),
    ]
    counts = {
        status: sum(item.status == status for item in checks)
        for status in ("ok", "warning", "blocker", "skipped")
    }
    return {
        "safe_read_only": True,
        "network_checked": network,
        "ready": counts["blocker"] == 0 and counts["warning"] == 0,
        "counts": counts,
        "checks": [asdict(item) for item in checks],
    }


def _print_human(report: dict) -> None:
    labels = {"ok": "OK", "warning": "PENDIENTE", "blocker": "BLOQUEO", "skipped": "SIN CONFIGURAR"}
    print("Bynoesis · comprobación de integraciones (solo lectura)")
    for item in report["checks"]:
        print(f"[{labels[item['status']]}] {item['area']}: {item['summary']}")
        if item["action"]:
            print(f"  → {item['action']}")
    counts = report["counts"]
    print(
        f"Resultado: {counts['ok']} OK, {counts['warning']} pendientes, "
        f"{counts['blocker']} bloqueos y {counts['skipped']} sin configurar."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Comprueba integraciones sin enviar mensajes ni crear cargos."
    )
    parser.add_argument(
        "--network", action="store_true",
        help="Consulta por GET los proveedores configurados.",
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument(
        "--strict", action="store_true",
        help="Devuelve error si queda cualquier pendiente o servicio sin configurar.",
    )
    args = parser.parse_args(argv)
    report = collect_checks(network=args.network)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    if report["counts"]["blocker"]:
        return 2
    if args.strict and (report["counts"]["warning"] or report["counts"]["skipped"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
