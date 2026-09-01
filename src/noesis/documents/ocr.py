"""Leer el texto y el importe de una foto (OCR) — opcional y degradable.

Patrón adaptador, igual que la transcripción de voz: si la librería de OCR no está
instalada, `extract` devuelve None y la app sigue funcionando (el documento se
guarda igual, solo que sin lectura automática).

La dependencia Python forma parte del producto; también hace falta el binario
`tesseract` y sus paquetes de idiomas en el servidor.
En Mac:  brew install tesseract tesseract-lang
En Debian/Railway: instala tesseract-ocr y los paquetes cat/spa/eng.
"""

from __future__ import annotations

import io
import logging
import re

log = logging.getLogger("noesis.ocr")
PREFERRED_LANGUAGES = ("cat", "spa", "eng")


def installed_languages() -> tuple[str, ...]:
    """Idiomas disponibles, en orden estable y sin asumir la imagen del servidor."""
    try:
        import pytesseract
        found = set(pytesseract.get_languages(config=""))
    except Exception:  # noqa: BLE001
        return ()
    preferred = tuple(language for language in PREFERRED_LANGUAGES if language in found)
    if preferred:
        return preferred
    return tuple(sorted(found - {"osd"}))


def available() -> bool:
    """True si se puede hacer OCR en local (pytesseract + binario tesseract)."""
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
        return bool(installed_languages())
    except Exception:  # noqa: BLE001
        return False


def _read_image(image) -> str | None:
    try:
        import pytesseract
        languages = installed_languages()
        if not languages:
            return None
        return pytesseract.image_to_string(
            image, lang="+".join(languages), timeout=12,
            config="--oem 1 --psm 3",
        )
    except Exception as e:  # noqa: BLE001
        log.warning("OCR falló: %s", e)
        return None


def _read_text(data: bytes) -> str | None:
    try:
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            prepared = ImageOps.exif_transpose(image)
            prepared = ImageOps.autocontrast(ImageOps.grayscale(prepared))
            if prepared.width < 1_400:
                scale = min(2.0, 1_400 / max(prepared.width, 1))
                prepared = prepared.resize(
                    (int(prepared.width * scale), int(prepared.height * scale))
                )
            return _read_image(prepared)
    except Exception as e:  # noqa: BLE001
        log.warning("La imagen no se pudo preparar para OCR: %s", e)
        return None


def _detect_amount(text: str) -> float | None:
    """Heurística para el importe total de un ticket/factura.

    1) Prioriza líneas equivalentes a «total a pagar» en catalán, castellano e inglés.
    2) Si no, coge el mayor importe del documento (suele ser el total).
    Formatos europeos: 1.234,56 y americanos: 1,234.56.
    """
    if not text:
        return None
    amount_re = re.compile(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+[.,]\d{2}")

    def to_float(s: str) -> float | None:
        s = s.strip()
        # Normaliza: el último separador es el decimal.
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    total_markers = (
        "total a pagar", "import total", "importe total", "total factura",
        "grand total", "amount due", "total due", "payment due", "a pagar",
        "total",
    )
    best_total = None
    for line in text.splitlines():
        normalized = " ".join(line.lower().split())
        if any(marker in normalized for marker in total_markers) and not re.search(
            r"\b(subtotal|base imponible|base imposable|taxable amount)\b", normalized
        ):
            vals = [to_float(m) for m in amount_re.findall(line)]
            vals = [v for v in vals if v is not None]
            if vals:
                best_total = max(best_total or 0, max(vals))
    if best_total:
        return round(best_total, 2)

    vals = [to_float(m) for m in amount_re.findall(text)]
    vals = [v for v in vals if v is not None]
    return round(max(vals), 2) if vals else None


def detect_amount(text: str | None) -> float | None:
    """Expone la misma heurística para texto PDF extraído localmente."""
    return _detect_amount(text or "")


def extract(data: bytes) -> dict | None:
    """Devuelve {text, amount} de una imagen, o None si el OCR no está disponible."""
    if not available():
        return None
    text = _read_text(data)
    if text is None:
        return None
    return {
        "text": text.strip(), "amount": detect_amount(text),
        "languages": list(installed_languages()),
    }


def extract_image(image) -> dict | None:
    """Lee una imagen PIL ya validada/rasterizada sin volverla a codificar."""
    if not available():
        return None
    text = _read_image(image)
    if text is None:
        return None
    return {
        "text": text.strip(), "amount": detect_amount(text),
        "languages": list(installed_languages()),
    }
