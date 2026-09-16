"""Extracción local, acotada y defensiva de texto en PDF digital."""

from __future__ import annotations

from io import BytesIO

MAX_PAGES = 12
MAX_TEXT_CHARS = 24_000
MAX_STREAM_BYTES = 8 * 1024 * 1024


def extract_pages(data: bytes) -> list[str] | None:
    """Texto embebido por página, sin ejecutar contenido ni intentar OCR de imágenes.

    Conserva la posición de cada página (vacía si no tiene texto) para poder separar
    un PDF con varias facturas sin confundir qué página es cuál.
    """
    try:
        from pypdf import PdfReader, filters

        # Un PDF pequeño puede declarar streams comprimidos enormes. Rebajamos los
        # límites globales seguros de pypdf antes de abrir contenido no confiable.
        for name in (
            "ZLIB_MAX_OUTPUT_LENGTH", "LZW_MAX_OUTPUT_LENGTH",
            "RUN_LENGTH_MAX_OUTPUT_LENGTH", "MAX_DECLARED_STREAM_LENGTH",
        ):
            if hasattr(filters, name):
                setattr(filters, name, min(
                    int(getattr(filters, name)), MAX_STREAM_BYTES
                ))
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            return None
        pages: list[str] = []
        remaining = MAX_TEXT_CHARS
        for index, page in enumerate(reader.pages):
            if index >= MAX_PAGES or remaining <= 0:
                break
            text = (page.extract_text() or "").strip()[:remaining]
            pages.append(text)
            remaining -= len(text)
        return pages if any(pages) else None
    except Exception:  # PDF inválido, cifrado o no extraíble: revisión manual.
        return None


def extract(data: bytes) -> str | None:
    """Lee texto embebido sin ejecutar contenido ni intentar OCR de imágenes."""
    pages = extract_pages(data)
    if not pages:
        return None
    result = "\n".join(page for page in pages if page).strip()
    return result or None
