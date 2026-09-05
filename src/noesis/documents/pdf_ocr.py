"""OCR local y defensivo para PDF escaneado o fotografiado.

PDFium solo rasteriza. La lectura se delega al mismo adaptador Tesseract usado por
las fotos, de modo que ningún documento abandona la infraestructura de Bynoesis.
"""

from __future__ import annotations

import logging
import math
from io import BytesIO

from . import ocr

log = logging.getLogger("noesis.pdf_ocr")

MAX_OCR_PAGES = 4
MAX_PIXELS_PER_PAGE = 5_000_000
MAX_TEXT_CHARS = 24_000
TARGET_SCALE = 2.0  # 144 dpi: suficiente para facturas y tickets habituales.


def available() -> bool:
    """El flujo necesita tanto PDFium como un Tesseract operativo."""
    if not ocr.available():
        return False
    try:
        import pypdfium2  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _safe_scale(page) -> float:
    width, height = page.get_size()
    width, height = float(width), float(height)
    if (
        not math.isfinite(width) or not math.isfinite(height)
        or width <= 0 or height <= 0
    ):
        raise ValueError("Dimensiones de página no válidas.")
    area = width * height
    scale = min(TARGET_SCALE, math.sqrt(MAX_PIXELS_PER_PAGE / area))
    # Un lienzo absurdo exigiría una escala que PDFium no puede rasterizar de forma
    # útil. Se rechaza antes de reservar memoria en vez de corregirlo después.
    if scale < 0.02:
        raise ValueError("Página demasiado grande para OCR seguro.")
    return scale


def extract(data: bytes) -> str | None:
    """Rasteriza como máximo cuatro páginas y devuelve su texto OCR acotado."""
    if not available():
        return None
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(BytesIO(data))
        chunks: list[str] = []
        remaining = MAX_TEXT_CHARS
        try:
            for index in range(min(len(document), MAX_OCR_PAGES)):
                page = document[index]
                bitmap = None
                image = None
                try:
                    bitmap = page.render(
                        scale=_safe_scale(page), grayscale=True,
                        draw_annots=False,
                    )
                    image = bitmap.to_pil()
                    if image.width * image.height > MAX_PIXELS_PER_PAGE:
                        image.thumbnail((2236, 2236))
                    result = ocr.extract_image(image)
                    text = str((result or {}).get("text") or "").strip()
                    if text:
                        chunks.append(text[:remaining])
                        remaining -= len(chunks[-1])
                    if remaining <= 0:
                        break
                finally:
                    if image is not None:
                        image.close()
                    if bitmap is not None:
                        bitmap.close()
                    page.close()
        finally:
            document.close()
        text = "\n".join(chunks).strip()
        return text or None
    except Exception as exc:  # PDF inválido/cifrado o fallo acotado: revisión.
        log.warning("OCR de PDF falló: %s", exc)
        return None
