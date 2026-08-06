"""Leer el texto y el importe de una foto (OCR) — opcional y degradable.

Patrón adaptador, igual que la transcripción de voz: si la librería de OCR no está
instalada, `extract` devuelve None y la app sigue funcionando (el documento se
guarda igual, solo que sin lectura automática).

Para activarlo: pip install -e ".[ocr]" (y el binario `tesseract`).
En Mac:  brew install tesseract tesseract-lang
En Debian/Railway:  apt-get install tesseract-ocr tesseract-ocr-spa
"""

from __future__ import annotations

import io
import logging
import re

log = logging.getLogger("noesis.ocr")


def available() -> bool:
    """True si se puede hacer OCR en local (pytesseract + binario tesseract)."""
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001
        return False


def _read_image(image) -> str | None:
    try:
        import pytesseract
        return pytesseract.image_to_string(
            image, lang="spa+eng", timeout=8,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("OCR falló: %s", e)
        return None


def _read_text(data: bytes) -> str | None:
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            return _read_image(image)
    except Exception as e:  # noqa: BLE001
        log.warning("La imagen no se pudo preparar para OCR: %s", e)
        return None


def _detect_amount(text: str) -> float | None:
    """Heurística para el importe total de un ticket/factura.

    1) Si hay una línea con 'total', coge el mayor importe de esa línea.
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

    best_total = None
    for line in text.splitlines():
        if "total" in line.lower():
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
    return {"text": text.strip(), "amount": detect_amount(text)}


def extract_image(image) -> dict | None:
    """Lee una imagen PIL ya validada/rasterizada sin volverla a codificar."""
    if not available():
        return None
    text = _read_image(image)
    if text is None:
        return None
    return {"text": text.strip(), "amount": detect_amount(text)}
