"""Diagnóstico seguro y sin secretos antes de un piloto o despliegue.

Uso::

    noesis-doctor
    noesis-doctor --json --strict
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

from . import config, migrations
from .adapters import ai as ai_adapter


@dataclass(frozen=True)
class ReadinessCheck:
    area: str
    status: str
    summary: str
    action: str = ""


def _env_ready(names: tuple[str, ...]) -> tuple[list[str], list[str]]:
    present = [name for name in names if os.getenv(name, "").strip()]
    missing = [name for name in names if name not in present]
    return present, missing


def collect_readiness(*, check_database: bool = True) -> dict:
    """Devuelve una foto operativa; nunca incluye valores de credenciales."""
    checks: list[ReadinessCheck] = []

    secret_ok = (
        config.SECRET_KEY != "dev-secret-cambiar-en-produccion"
        and len(config.SECRET_KEY) >= 32
    )
    if config.IS_PRODUCTION and not secret_ok:
        checks.append(ReadinessCheck(
            "seguridad", "blocker", "La clave de sesión no es segura.",
            "Configura NOESIS_SECRET aleatoria con al menos 32 caracteres.",
        ))
    else:
        checks.append(ReadinessCheck(
            "seguridad", "ok" if secret_ok else "warning",
            "Clave de sesión preparada." if secret_ok else
            "La clave de sesión solo es apta para desarrollo local.",
            "Usa una clave aleatoria antes de exponer la app." if not secret_ok else "",
        ))

    https_ok = config.BASE_URL.startswith("https://")
    checks.append(ReadinessCheck(
        "seguridad",
        "ok" if https_ok else ("blocker" if config.IS_PRODUCTION else "warning"),
        "URL pública con HTTPS." if https_ok else "La URL base no usa HTTPS.",
        "Configura NOESIS_BASE_URL con el dominio HTTPS real." if not https_ok else "",
    ))

    if check_database:
        try:
            current = migrations.current_version()
            latest = migrations.LATEST_VERSION
            checks.append(ReadinessCheck(
                "base de datos", "ok" if current == latest else "blocker",
                f"Esquema en migración {current}/{latest}.",
                "Ejecuta python -m noesis.migrations upgrade."
                if current != latest else "",
            ))
        except Exception as exc:  # noqa: BLE001 - el doctor debe seguir informando
            checks.append(ReadinessCheck(
                "base de datos", "blocker",
                f"No se pudo comprobar el esquema ({type(exc).__name__}).",
                "Revisa DATABASE_URL y la conectividad antes del piloto.",
            ))

    checks.append(ReadinessCheck(
        "base de datos",
        "ok" if config.DATABASE_URL else "warning",
        "PostgreSQL configurado." if config.DATABASE_URL else
        "Se usa SQLite; válido en local, frágil para un SaaS desplegado.",
        "Conecta PostgreSQL en producción." if not config.DATABASE_URL else "",
    ))

    backup_names = (
        "NOESIS_BACKUP_S3_ENDPOINT", "NOESIS_BACKUP_S3_BUCKET",
        "NOESIS_BACKUP_S3_ACCESS_KEY", "NOESIS_BACKUP_S3_SECRET_KEY",
    )
    backup_present, backup_missing = _env_ready(backup_names)
    backup_ok = not backup_missing
    backup_partial = bool(backup_present) and bool(backup_missing)
    checks.append(ReadinessCheck(
        "copias",
        "ok" if backup_ok else ("blocker" if backup_partial else "warning"),
        "Copia externa S3 configurada." if backup_ok else
        ("La copia externa está configurada a medias." if backup_partial else
         "No hay copia externa configurada."),
        "Completa y prueba una restauración desde S3." if not backup_ok else
        "Ejecuta una restauración real antes del piloto.",
    ))

    whatsapp_names = (
        "NOESIS_WHATSAPP_NUMBER", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID",
        "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET",
    )
    wa_present, wa_missing = _env_ready(whatsapp_names)
    wa_ok = not wa_missing
    wa_partial = bool(wa_present) and bool(wa_missing)
    checks.append(ReadinessCheck(
        "whatsapp",
        "ok" if wa_ok else ("blocker" if wa_partial else "warning"),
        "Meta Cloud API configurada." if wa_ok else
        ("WhatsApp está configurado a medias." if wa_partial else
         "WhatsApp real aún no está configurado."),
        "Completa las credenciales y valida texto, audio, imagen, PDF y plantillas."
        if not wa_ok else "Ejecuta el smoke con el número real.",
    ))

    smtp_names = ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "SMTP_FROM")
    smtp_present, smtp_missing = _env_ready(smtp_names)
    smtp_ok = not smtp_missing
    checks.append(ReadinessCheck(
        "correo", "ok" if smtp_ok else "warning",
        "Correo saliente configurado." if smtp_ok else
        "El correo real no está completo.",
        "Completa SMTP y prueba recuperación, factura y gestoría."
        if not smtp_ok else "",
    ))

    google_names = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET")
    google_present, google_missing = _env_ready(google_names)
    google_ok = not google_missing
    google_partial = bool(google_present) and bool(google_missing)
    google_blocked = config.ADMIN_REQUIRE_GOOGLE_OAUTH and not google_ok
    checks.append(ReadinessCheck(
        "google",
        "ok" if google_ok else (
            "blocker" if google_partial or google_blocked else "warning"
        ),
        "Alta y acceso con Google configurados." if google_ok else
        ("Google OAuth está configurado a medias." if google_partial else
         "El acceso con Google aún no está configurado."),
        (
            "Crea el cliente OAuth web, registra el callback exacto y completa "
            "GOOGLE_OAUTH_CLIENT_ID y GOOGLE_OAUTH_CLIENT_SECRET."
        ) if not google_ok else "Prueba un alta nueva y un acceso existente.",
    ))

    stripe_names = (
        "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_AUTONOMO",
        "STRIPE_PRICE_PRO", "STRIPE_PRICE_PREMIUM",
        "STRIPE_PRICE_AUTONOMO_ANNUAL", "STRIPE_PRICE_PRO_ANNUAL",
        "STRIPE_PRICE_PREMIUM_ANNUAL",
    )
    stripe_present, stripe_missing = _env_ready(stripe_names)
    stripe_ok = not stripe_missing
    stripe_partial = bool(stripe_present) and bool(stripe_missing)
    checks.append(ReadinessCheck(
        "stripe", "ok" if stripe_ok else ("blocker" if stripe_partial else "warning"),
        "Cobro de suscripción configurado." if stripe_ok else
        ("Stripe está configurado a medias." if stripe_partial else
         "Stripe real aún no está configurado."),
        "Completa webhook y precios; prueba alta, renovación, fallo y cancelación."
        if not stripe_ok else "",
    ))

    aeat_names = (
        "NOESIS_VERIFACTU_PRODUCER_NIF", "VERIFACTU_CERT_PATH",
        "VERIFACTU_KEY_PATH", "VERIFACTU_AEAT_ENV",
    )
    aeat_present, aeat_missing = _env_ready(aeat_names)
    aeat_ok = not aeat_missing
    aeat_partial = bool(aeat_present) and bool(aeat_missing)
    cert_files_ok = aeat_ok and all(
        Path(os.getenv(name, "")).is_file()
        for name in ("VERIFACTU_CERT_PATH", "VERIFACTU_KEY_PATH")
    )
    checks.append(ReadinessCheck(
        "verifactu",
        "ok" if cert_files_ok else ("blocker" if aeat_partial or aeat_ok else "warning"),
        "Certificado y entorno AEAT preparados." if cert_files_ok else
        ("La remisión AEAT está incompleta o los PEM no existen." if aeat_present else
         "La remisión AEAT real aún no está configurada."),
        "Completa productor, PEM y entorno de pruebas; valida con la gestoría."
        if not cert_files_ok else "",
    ))

    local_ai = ai_adapter.local_available()
    compatible_ai = ai_adapter.external_available()
    anthropic_ai = bool(config.ANTHROPIC_API_KEY)
    providers = [
        name for name, enabled in (
            ("privada", local_ai),
            (config.COMPAT_AI_PROVIDER or "compatible", compatible_ai),
            ("anthropic", anthropic_ai),
        ) if enabled
    ]
    checks.append(ReadinessCheck(
        "ia", "ok" if providers else "warning",
        "Proveedores disponibles: " + ", ".join(providers) + "."
        if providers else "Solo está disponible el cerebro determinista local.",
        "Configura al menos un proveedor avanzado y conserva un fallback."
        if not providers else "Evalúa herramientas, castellano/catalán, coste y latencia.",
    ))
    if compatible_ai:
        price_ready = (
            config.COMPAT_AI_INPUT_USD_PER_MTOK > 0
            and config.COMPAT_AI_OUTPUT_USD_PER_MTOK > 0
        )
        checks.append(ReadinessCheck(
            "ia", "ok" if price_ready else "warning",
            "Tarifa del proveedor compatible registrada." if price_ready else
            "El proveedor compatible no tiene tarifa registrada.",
            "Configura los dos precios por millón de tokens para medir margen."
            if not price_ready else "",
        ))
    elif config.COMPAT_AI_BASE_URL or config.COMPAT_AI_MODEL or config.COMPAT_AI_API_KEY:
        checks.append(ReadinessCheck(
            "ia", "blocker",
            "El proveedor compatible está configurado a medias o no está declarado legalmente.",
            "Completa endpoint HTTPS, modelo, clave, NOESIS_COMPAT_AI_LEGAL_NAME y NOESIS_COMPAT_AI_REGION.",
        ))

    checks.append(ReadinessCheck(
        "operaciones", "ok" if config.ADMIN_EMAIL else "warning",
        "Responsable del panel interno configurado." if config.ADMIN_EMAIL else
        "No hay email administrador configurado.",
        "Configura NOESIS_ADMIN_EMAIL." if not config.ADMIN_EMAIL else "",
    ))

    antivirus_ok = bool(config.CLAMAV_HOST and config.CLAMAV_REQUIRED)
    checks.append(ReadinessCheck(
        "seguridad documental",
        "ok" if antivirus_ok else ("blocker" if config.CLAMAV_REQUIRED else "warning"),
        "Antivirus privado con fallo cerrado." if antivirus_ok else
        ("El antivirus es obligatorio pero no tiene host." if config.CLAMAV_REQUIRED else
         "El antivirus privado no esta en modo obligatorio."),
        "Configura ClamAV y NOESIS_CLAMAV_REQUIRED=true antes de escalar documentos."
        if not antivirus_ok else "",
    ))

    serialized = [asdict(check) for check in checks]
    counts = {
        status: sum(check.status == status for check in checks)
        for status in ("ok", "warning", "blocker")
    }
    return {
        "ready": counts["blocker"] == 0,
        "counts": counts,
        "checks": serialized,
    }


def _print_human(report: dict) -> None:
    labels = {"ok": "OK", "warning": "AVISO", "blocker": "BLOQUEO"}
    print("Noesis · preparación del piloto")
    for check in report["checks"]:
        print(f"[{labels[check['status']]}] {check['area']}: {check['summary']}")
        if check["action"]:
            print(f"  → {check['action']}")
    counts = report["counts"]
    print(
        f"Resultado: {counts['ok']} OK, {counts['warning']} avisos, "
        f"{counts['blocker']} bloqueos."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Comprueba configuración del piloto sin mostrar secretos."
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument(
        "--strict", action="store_true",
        help="Devuelve error también cuando quedan avisos.",
    )
    parser.add_argument(
        "--no-database", action="store_true",
        help="No abre la base de datos (útil al preparar variables).",
    )
    args = parser.parse_args(argv)
    report = collect_readiness(check_database=not args.no_database)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    if report["counts"]["blocker"]:
        return 2
    if args.strict and report["counts"]["warning"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
