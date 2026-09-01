"""Autenticación: hash de contraseñas (PBKDF2, solo stdlib) y sesión actual.

No usamos librerías externas para el hash: PBKDF2-HMAC-SHA256 con sal aleatoria y
600.000 iteraciones es seguro y viene en la librería estándar de Python. Esto
encaja con el objetivo de mantener Noesis con el mínimo de dependencias.
"""

from __future__ import annotations

import binascii
import hashlib
import hmac
import os
import re
import time
from datetime import datetime, timedelta

from .. import db

_ITERS = 600_000

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(email: str) -> bool:
    """Validación básica de formato de email (sin dependencias externas)."""
    return bool(_EMAIL_RE.match((email or "").strip()))


def hash_token(token: str) -> str:
    """Huella del token de un solo uso. En base solo se guarda esta huella."""
    return hashlib.sha256(token.encode()).hexdigest()


# -------- Límite compartido y pseudonimizado por IP/identidad/acción --------------
_WINDOW = 300        # 5 minutos
_MAX_ATTEMPTS = 8    # intentos permitidos por ventana


def client_ip(request) -> str:
    """IP real del cliente, a prueba de falsificación de X-Forwarded-For.

    Detrás de un proxy de confianza, la IP fiable es la que AÑADE el proxy más
    cercano, que va a la DERECHA de la cadena. Leerla desde la izquierda sería un
    coladero: cualquiera puede mandar "X-Forwarded-For: lo-que-quiera" y rotar la
    clave del rate limit. Saltamos `PROXY_HOPS` posiciones desde la derecha.
    """
    from .. import config
    if config.TRUST_PROXY_HEADERS:
        fwd = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        if parts:
            idx = len(parts) - config.PROXY_HOPS
            return parts[max(0, idx)]
    return request.client.host if request.client else "?"


def _attempt_key(key: str) -> str:
    """No guarda IP ni email reversibles aunque se filtre la tabla auxiliar."""
    from .. import config
    return hmac.new(
        config.SECRET_KEY.encode(), key.encode(), hashlib.sha256
    ).hexdigest()


def is_rate_limited(key: str) -> bool:
    """Comprueba el límite sin contabilizar peticiones que finalmente sean válidas."""
    since = (datetime.now() - timedelta(seconds=_WINDOW)).isoformat(timespec="seconds")
    return db.auth_attempt_count(_attempt_key(key), since) >= _MAX_ATTEMPTS


def record_failed_attempt(key: str) -> None:
    now = datetime.now()
    db.record_auth_attempt(
        _attempt_key(key),
        now.isoformat(timespec="microseconds"),
        keep_since=(now - timedelta(seconds=_WINDOW)).isoformat(timespec="seconds"),
    )


def clear_attempts(key: str) -> None:
    db.clear_auth_attempts(_attempt_key(key))


def too_many_attempts(key: str) -> bool:
    """Compatibilidad: registra el intento y devuelve si se ha superado el límite."""
    limited = is_rate_limited(key)
    if not limited:
        record_failed_attempt(key)
    return limited


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERS)
    return f"pbkdf2${_ITERS}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iters, salt_hex, dk_hex = stored.split("$")
        salt = binascii.unhexlify(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
        return hmac.compare_digest(binascii.hexlify(dk).decode(), dk_hex)
    except Exception:  # noqa: BLE001
        return False


def current_user(request) -> dict | None:
    """Devuelve el usuario de la sesión actual, o None si no hay sesión válida."""
    uid = request.session.get("uid")
    user = db.get_user(uid) if uid else None
    if not user:
        return None
    if request.session.get("sv", 0) != user.get("session_version", 0):
        return None
    # Una suspension corta las sesiones abiertas aqui mismo, no cuando caduque
    # la cookie. `set_user_access` sube ademas `session_version`, asi que esto
    # es el segundo cierre y no el unico.
    if not db.user_can_sign_in(user):
        request.session.clear()
        return None
    from .. import config
    now = int(time.time())
    last_seen = int(request.session.get("seen") or now)
    is_admin = bool(user.get("is_admin")) or config.is_admin_email(
        user.get("email")
    )
    idle_minutes = (
        config.ADMIN_SESSION_IDLE_MINUTES if is_admin else config.SESSION_IDLE_MINUTES
    )
    if now - last_seen > idle_minutes * 60:
        request.session.clear()
        return None
    # Evita reescribir la cookie en cada recurso, pero mantiene una ventana móvil.
    if now - last_seen >= 300 or "seen" not in request.session:
        request.session["seen"] = now
    return user
