"""Autenticación: hash de contraseñas (PBKDF2, solo stdlib) y sesión actual.

No usamos librerías externas para el hash: PBKDF2-HMAC-SHA256 con sal aleatoria y
200.000 iteraciones es seguro y viene en la librería estándar de Python. Esto
encaja con el objetivo de mantener Noesis con el mínimo de dependencias.
"""

from __future__ import annotations

import binascii
import hashlib
import hmac
import os
import re
import time

from .. import db

_ITERS = 600_000

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(email: str) -> bool:
    """Validación básica de formato de email (sin dependencias externas)."""
    return bool(_EMAIL_RE.match((email or "").strip()))


# -------- Límite de intentos (anti fuerza bruta), en memoria por IP+acción --------
_ATTEMPTS: dict[str, list[float]] = {}
_WINDOW = 300        # 5 minutos
_MAX_ATTEMPTS = 8    # intentos permitidos por ventana
_MAX_KEYS = 10_000


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


def _prune_attempts(now: float) -> None:
    stale = [
        key for key, hits in _ATTEMPTS.items()
        if not hits or now - hits[-1] >= _WINDOW
    ]
    for key in stale:
        _ATTEMPTS.pop(key, None)
    if len(_ATTEMPTS) > _MAX_KEYS:
        oldest = sorted(_ATTEMPTS, key=lambda key: _ATTEMPTS[key][-1])
        for key in oldest[:len(_ATTEMPTS) - _MAX_KEYS]:
            _ATTEMPTS.pop(key, None)


def is_rate_limited(key: str) -> bool:
    """Comprueba el límite sin contabilizar peticiones que finalmente sean válidas."""
    now = time.time()
    _prune_attempts(now)
    hits = [t for t in _ATTEMPTS.get(key, []) if now - t < _WINDOW]
    _ATTEMPTS[key] = hits
    return len(hits) >= _MAX_ATTEMPTS


def record_failed_attempt(key: str) -> None:
    now = time.time()
    _prune_attempts(now)
    hits = [t for t in _ATTEMPTS.get(key, []) if now - t < _WINDOW]
    hits.append(now)
    _ATTEMPTS[key] = hits[-_MAX_ATTEMPTS:]


def clear_attempts(key: str) -> None:
    _ATTEMPTS.pop(key, None)


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
    return user
