"""Validación defensiva de documentos no confiables antes de procesarlos.

El nombre, el MIME declarado y el canal de entrada son datos controlados por quien
sube el archivo. Esta capa comprueba los bytes reales y limita estructuras que
pueden agotar memoria o activar comportamiento dentro de un visor PDF.
"""

from __future__ import annotations

import io
import re
import warnings

from PIL import Image, UnidentifiedImageError

from .. import config


class UnsafeDocument(ValueError):
    """Archivo incompatible, malformado o peligroso para procesar."""


_IMAGE_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}
_PDF_ACTIVE_MARKERS = (
    b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/XFA",
)
_PDF_PAGE_RE = re.compile(rb"/Type\s*/Page(?!s)\b")


def _validate_pdf(data: bytes) -> None:
    if not data.startswith(b"%PDF-"):
        raise UnsafeDocument("El contenido no corresponde a un PDF válido.")
    if any(marker in data for marker in _PDF_ACTIVE_MARKERS):
        raise UnsafeDocument("El PDF contiene funciones activas que Noesis no admite.")
    pages = len(_PDF_PAGE_RE.findall(data))
    if pages > config.MAX_PDF_PAGES:
        raise UnsafeDocument(
            f"El PDF supera el límite de {config.MAX_PDF_PAGES} páginas."
        )


def _validate_image(ext: str, data: bytes) -> None:
    expected = _IMAGE_FORMATS[ext]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != expected:
                    raise UnsafeDocument(
                        "La extensión no coincide con el contenido de la imagen."
                    )
                width, height = image.size
                if width <= 0 or height <= 0:
                    raise UnsafeDocument("La imagen no tiene dimensiones válidas.")
                if width * height > config.MAX_IMAGE_PIXELS:
                    raise UnsafeDocument(
                        "La imagen tiene demasiados píxeles para procesarla con seguridad."
                    )
                image.verify()
    except UnsafeDocument:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise UnsafeDocument("La imagen es demasiado grande para procesarla.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise UnsafeDocument("La imagen está dañada o no es del formato indicado.") from exc


def _validate_heic(data: bytes) -> None:
    # ISO-BMFF: tamaño de caja + `ftyp` + marca principal. No se confía en MIME.
    if len(data) < 16 or data[4:8] != b"ftyp":
        raise UnsafeDocument("El contenido no corresponde a una imagen HEIC válida.")
    brands = {data[8:12]}
    brands.update(data[pos:pos + 4] for pos in range(16, min(len(data), 64), 4))
    if not brands.intersection({b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis"}):
        raise UnsafeDocument("El contenido no corresponde a una imagen HEIC válida.")


def validate(filename: str, data: bytes) -> None:
    """Valida firma, coherencia y límites antes de OCR o persistencia."""
    from . import storage

    ext = storage.ext_of(filename)
    if ext == ".pdf":
        _validate_pdf(data)
    elif ext in _IMAGE_FORMATS:
        _validate_image(ext, data)
    elif ext == ".heic":
        _validate_heic(data)
    else:
        raise UnsafeDocument("El formato del archivo no está permitido.")
