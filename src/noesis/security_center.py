"""Responsable CISO interno, determinista y de solo lectura.

Convierte controles verificables en un parte corto para el fundador. No usa IA,
no inspecciona contenido de clientes y no ejecuta acciones correctivas.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from . import config, db


def _age_hours(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(
            0.0,
            (datetime.now() - datetime.fromisoformat(str(value)[:19])).total_seconds()
            / 3600,
        )
    except ValueError:
        return None


def build_security_report() -> dict:
    """Devuelve estado, evidencias y siguientes pasos sin exponer datos personales."""
    findings: list[dict] = []

    def add(level: str, control: str, evidence: str, action: str = "") -> None:
        findings.append({
            "level": level,
            "control": control,
            "evidence": evidence,
            "action": action,
        })

    integrity = db.security_event_integrity()
    add(
        "ok" if integrity["ok"] else "critical",
        "Bitacora de seguridad",
        (
            f"Cadena integra con {integrity['events']} evento(s)."
            if integrity["ok"] else
            f"La cadena se rompe en el evento {integrity['broken_at']}."
        ),
        "Preserva la base y abre un incidente antes de modificar nada."
        if not integrity["ok"] else "",
    )

    if config.IS_PRODUCTION:
        oauth_ok = config.ADMIN_REQUIRE_GOOGLE_OAUTH and config.google_oauth_available()
        add(
            "ok" if oauth_ok else "critical",
            "Acceso del fundador",
            "Google OAuth es obligatorio y esta configurado."
            if oauth_ok else "El acceso fuerte del administrador no esta completo.",
            "Configura Google OAuth y manten NOESIS_ADMIN_REQUIRE_GOOGLE_OAUTH=true."
            if not oauth_ok else "",
        )
    else:
        add(
            "info", "Acceso del fundador",
            "Entorno local: la obligacion OAuth se comprueba al arrancar produccion.",
        )

    backup = db.latest_backup_run()
    backup_age = _age_hours((backup or {}).get("created_at"))
    if not backup:
        add(
            "critical", "Copias recuperables", "No hay copias registradas.",
            "Ejecuta una copia verificada y configura almacenamiento externo.",
        )
    elif backup.get("status") != "ok":
        add(
            "critical", "Copias recuperables", "La ultima copia fallo.",
            "Conserva la ultima copia buena y resuelve el fallo antes de operar.",
        )
    elif backup_age is None or backup_age > 48:
        add(
            "warning", "Copias recuperables",
            "La ultima copia buena supera las 48 horas o no tiene fecha valida.",
            "Comprueba el scheduler y ejecuta noesis-restore-check.",
        )
    else:
        add(
            "ok", "Copias recuperables",
            f"Ultima copia verificada hace {round(backup_age, 1)} hora(s).",
        )

    latest_events = db.list_security_events(100)
    restores = db.list_security_events(1, event_types=(
        "backup.restore_drill_passed", "backup.restore_drill_failed",
    ))
    restore_event = restores[0] if restores else None
    if not restore_event:
        add(
            "warning", "Simulacro de restauracion",
            "Aun no hay un simulacro independiente registrado.",
            "Ejecuta noesis-restore-check o espera al simulacro semanal.",
        )
    elif restore_event["event_type"].endswith("failed"):
        add(
            "critical", "Simulacro de restauracion",
            "El ultimo simulacro independiente fallo.",
            "Trata la copia como no recuperable hasta repetirlo con exito.",
        )
    elif (_age_hours(restore_event["created_at"]) is None
          or _age_hours(restore_event["created_at"]) > 192):
        add(
            "warning", "Simulacro de restauracion",
            "El último simulacro tiene más de ocho días o una fecha inválida.",
            "Repite noesis-restore-check en un entorno aislado.",
        )
    else:
        add(
            "ok", "Simulacro de restauracion",
            f"Ultimo simulacro correcto: {str(restore_event['created_at'])[:19]}.",
        )

    s3_values = (
        config.BACKUP_S3_ENDPOINT,
        config.BACKUP_S3_BUCKET,
        config.BACKUP_S3_ACCESS_KEY,
        config.BACKUP_S3_SECRET_KEY,
    )
    s3_context = (
        config.BACKUP_S3_REGION,
        config.BACKUP_S3_PROVIDER_NAME,
        config.BACKUP_S3_DATA_REGION,
    )
    if all(s3_values) and all(s3_context):
        from .web.backups import offsite_destination_id

        attempts = db.list_security_events(1, event_types=(
            "backup.offsite_started", "backup.offsite_passed", "backup.offsite_failed",
        ))
        attempt = attempts[0] if attempts else None
        current = bool(attempt and attempt["metadata"].get("destination_id")
                       == offsite_destination_id())
        age = _age_hours(attempt["created_at"]) if attempt else None
        passed = bool(current and attempt["event_type"] == "backup.offsite_passed"
                      and age is not None and age <= 48)
        failed = bool(current and attempt["event_type"] == "backup.offsite_failed")
        add(
            "ok" if passed else "critical" if failed else "warning",
            "Copia fuera del servidor",
            "El destino aceptó base y documentos en las últimas 48 horas. "
            "Falta demostrar recuperación desde una descarga externa."
            if passed else "La última subida externa falló. La copia local no la sustituye."
            if failed else "Destino configurado, sin un envío completo reciente demostrado.",
            "Descarga y restaura el juego en infraestructura independiente."
            if passed else "Revisa el destino y ejecuta una copia; verifica ambos archivos.",
        )
    elif any(s3_values):
        add(
            "critical", "Copia fuera del servidor",
            "La configuracion S3 esta incompleta.",
            "Completa credenciales, región, proveedor y residencia o retíralos.",
        )
    else:
        add(
            "warning", "Copia fuera del servidor", "No hay destino externo configurado.",
            "Conecta un bucket privado antes de incorporar datos reales.",
        )

    if config.CLAMAV_HOST and config.CLAMAV_REQUIRED:
        add(
            "ok", "Antivirus documental",
            "ClamAV privado esta configurado en modo de fallo cerrado.",
        )
    elif config.CLAMAV_HOST:
        add(
            "warning", "Antivirus documental",
            "ClamAV esta conectado, pero una caida no bloquea la subida.",
            "Activa NOESIS_CLAMAV_REQUIRED=true en produccion.",
        )
    else:
        add(
            "warning", "Antivirus documental",
            "Actuan firma, paginas y pixeles; falta el escaner de malware.",
            "Despliega ClamAV privado y activa el fallo cerrado.",
        )

    add(
        "ok" if config.DATABASE_URL else "warning",
        "Base de datos",
        "PostgreSQL esta configurado." if config.DATABASE_URL else
        "SQLite solo es adecuado para desarrollo local.",
        "Usa PostgreSQL en el piloto." if not config.DATABASE_URL else "",
    )
    add(
        "ok" if config.BASE_URL.startswith("https://") else "warning",
        "Transporte",
        "La URL base usa HTTPS." if config.BASE_URL.startswith("https://") else
        "La URL base no usa HTTPS.",
        "Configura el dominio HTTPS real." if not config.BASE_URL.startswith("https://") else "",
    )

    auth_pressure = db.auth_attempt_summary(24)
    attempts = auth_pressure["attempts"]
    add(
        "warning" if attempts >= 32 else "ok",
        "Presion de acceso",
        (
            f"{attempts} intento(s) fallido(s) sobre "
            f"{auth_pressure['pseudonymous_keys']} clave(s) seudonimas en 24 h."
        ),
        "Revisa el proveedor de red y los request IDs si el volumen sigue creciendo."
        if attempts >= 32 else "",
    )

    counts = db.security_event_counts()
    recent_critical = int(counts["24h"].get("critical", 0))
    if recent_critical:
        add(
            "critical", "Incidentes recientes",
            f"Hay {recent_critical} evento(s) critico(s) en las ultimas 24 horas.",
            "Revisa la evidencia y cierra cada causa; no borres la bitacora.",
        )

    penalties = {"critical": 1.5, "warning": 0.5, "ok": 0.0, "info": 0.0}
    score = max(0.0, 10.0 - sum(penalties[item["level"]] for item in findings))
    critical = sum(item["level"] == "critical" for item in findings)
    warnings = sum(item["level"] == "warning" for item in findings)
    status = "rojo" if critical else "ambar" if warnings else "verde"
    headline = (
        f"{critical} control(es) critico(s): no abras el piloto hasta resolverlos."
        if critical else
        f"Base controlada; quedan {warnings} refuerzo(s) operativo(s)."
        if warnings else
        "Controles internos preparados; manten la revision externa antes de escalar."
    )
    return {
        "status": status,
        "score": round(score, 1),
        "headline": headline,
        "findings": findings,
        "counts": counts,
        "recent_events": latest_events[:12],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "review_after": (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
    }
