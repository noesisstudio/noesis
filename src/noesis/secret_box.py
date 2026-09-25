"""Caja fuerte para los secretos de terceros que guarda Bynoesis.

Conectar el Gmail de un autónomo significa guardar una llave que permite enviar
correo **en su nombre**. En claro, cualquiera con acceso a la base de datos —una
copia de seguridad mal guardada, el panel del servidor— podría escribir haciéndose
pasar por todos los clientes a la vez, con facturas dentro. Aquí se cifran antes
de tocar el disco.

La clave se deriva de `NOESIS_SECRET`, que ya protege las sesiones: así no hay un
secreto más que custodiar, y quien tenga la base de datos sin tener esa variable
no puede leer nada. El precio es explícito y hay que saberlo: **si se cambia
`NOESIS_SECRET`, los secretos guardados dejan de poder leerse** y cada autónomo
tendrá que volver a conectar su cuenta. No se pierde dinero ni documentos, solo
las conexiones.
"""
from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from . import config

log = logging.getLogger(__name__)

# Marca de versión: si algún día cambia la forma de cifrar, un secreto viejo se
# reconoce por su prefijo y se puede migrar en vez de romperse en silencio.
_PREFIJO = "v1:"


def _clave() -> bytes:
    """Clave de cifrado derivada del secreto de la aplicación."""
    material = hashlib.sha256(
        b"noesis-secret-box-v1|" + config.SECRET_KEY.encode("utf-8")
    ).digest()
    return base64.urlsafe_b64encode(material)


def disponible() -> bool:
    """¿Hay un secreto de aplicación digno de cifrar con él?

    Con el secreto de desarrollo por defecto no se guarda nada: sería cifrar con
    una llave que está escrita en el código y publicada en el repositorio.
    """
    return bool(config.SECRET_KEY) and (
        config.SECRET_KEY != "dev-secret-cambiar-en-produccion"  # pragma: allowlist secret
    )


def guardar(valor: str) -> str:
    """Cifra un secreto para poder escribirlo en la base de datos."""
    if not valor:
        return ""
    if not disponible():
        raise ValueError(
            "No hay un NOESIS_SECRET propio en este servidor, así que no puedo "
            "guardar credenciales cifradas. Configúralo antes de conectar cuentas."
        )
    return _PREFIJO + Fernet(_clave()).encrypt(valor.encode("utf-8")).decode("ascii")


def leer(guardado: str | None) -> str | None:
    """Descifra un secreto. Devuelve `None` si ya no se puede leer.

    No se relanza el error: un secreto ilegible —porque cambió `NOESIS_SECRET`, o
    porque el dato está corrupto— significa «esta conexión ya no vale», y quien
    llama debe pedir que se vuelva a conectar la cuenta, no reventar.
    """
    texto = str(guardado or "")
    if not texto:
        return None
    if not texto.startswith(_PREFIJO):
        log.warning("Secreto guardado con un formato desconocido; se ignora.")
        return None
    try:
        return Fernet(_clave()).decrypt(texto[len(_PREFIJO):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        log.warning("Un secreto guardado ya no se puede descifrar; hay que "
                    "volver a conectar esa cuenta.")
        return None
