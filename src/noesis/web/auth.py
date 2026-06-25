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

from .. import db

_ITERS = 200_000


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
    return db.get_user(uid) if uid else None
