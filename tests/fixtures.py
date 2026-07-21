"""Fixtures binarias reales para no debilitar validaciones de seguridad."""

from io import BytesIO

from PIL import Image


def _tiny_image(image_format: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(output, format=image_format)
    return output.getvalue()


TINY_JPEG = _tiny_image("JPEG")
TINY_PNG = _tiny_image("PNG")
