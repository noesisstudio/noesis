"""Segundo factor TOTP y códigos de recuperación para cuentas profesionales.

El secreto TOTP se deriva de la clave maestra y la identidad estable de la cuenta:
no se guarda una semilla reversible adicional en la base. Los códigos de emergencia
son aleatorios de 80 bits y solo se conservan como SHA-256 para poder consumirlos
una vez.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
import urllib.parse

from .. import config

_STEP_SECONDS = 30
_DIGITS = 6


def secret_for(account: dict) -> str:
    identity = f"gestoria-mfa:v1:{account['id']}:{account['email']}".encode()
    digest = hmac.new(config.SECRET_KEY.encode(), identity, hashlib.sha256).digest()
    return base64.b32encode(digest).decode().rstrip("=")


def _secret_bytes(secret: str) -> bytes:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret + padding, casefold=True)


def code_for_counter(secret: str, counter: int) -> str:
    digest = hmac.new(
        _secret_bytes(secret), struct.pack(">Q", counter), hashlib.sha1
    ).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** _DIGITS)).zfill(_DIGITS)


def matching_counter(account: dict, code: str, *, at: int | None = None) -> int | None:
    clean = "".join(char for char in str(code or "") if char.isdigit())
    if len(clean) != _DIGITS:
        return None
    current = int(time.time() if at is None else at) // _STEP_SECONDS
    secret = secret_for(account)
    for counter in (current - 1, current, current + 1):
        if hmac.compare_digest(code_for_counter(secret, counter), clean):
            return counter
    return None


def provisioning_uri(account: dict) -> str:
    label = urllib.parse.quote(f"Bynoesis:{account['email']}", safe="")
    query = urllib.parse.urlencode({
        "secret": secret_for(account),
        "issuer": "Bynoesis",
        "algorithm": "SHA1",
        "digits": str(_DIGITS),
        "period": str(_STEP_SECONDS),
    })
    return f"otpauth://totp/{label}?{query}"


def qr_data_uri(account: dict) -> str:
    """Devuelve SVG autocontenido; si QR no carga, la clave manual sigue visible."""
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage

        image = qrcode.make(provisioning_uri(account), image_factory=SvgPathImage)
        output = io.BytesIO()
        image.save(output)
        encoded = base64.b64encode(output.getvalue()).decode()
        return f"data:image/svg+xml;base64,{encoded}"
    except Exception:  # noqa: BLE001
        return ""


def generate_recovery_codes(count: int = 8) -> list[str]:
    codes: list[str] = []
    for _ in range(count):
        raw = base64.b32encode(secrets.token_bytes(10)).decode().rstrip("=")
        codes.append("-".join(raw[index:index + 4] for index in range(0, 16, 4)))
    return codes


def normalize_recovery_code(code: str) -> str:
    return "".join(char for char in str(code or "").upper() if char.isalnum())


def recovery_hash(code: str) -> str:
    return hashlib.sha256(normalize_recovery_code(code).encode()).hexdigest()
