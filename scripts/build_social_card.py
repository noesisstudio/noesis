"""Genera la tarjeta que se ve al compartir bynoesis.com (Open Graph, 1200x630).

Se ejecuta a mano cuando cambie la marca o el reclamo; el PNG vive en el repo:

    python scripts/build_social_card.py

**Nunca una captura del panel.** La anterior lo era y enseñaba el nombre de una
cuenta y el de un cliente cada vez que alguien compartía el enlace, además de
salir recortada por la mitad: 1265x900 no es la proporción que usan Facebook,
LinkedIn ni WhatsApp.

Tipografías: las de la cadena que declara la marca en `app.css` («Iowan Old
Style» como alternativa de Fraunces, y Avenir Next por Inter). Vienen con macOS,
así que esto se regenera en un Mac; el PNG resultante no depende de ellas.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

VERDE = (20, 70, 59)          # #14463b  brand
VERDE_2 = (46, 139, 116)      # #2e8b74  brand_2
CREMA = (244, 241, 232)       # #f4f1e8
CREMA_SUAVE = (196, 214, 205)

W, H = 1200, 630
ESCALA = 3                    # se dibuja grande y se reduce: bordes limpios
lienzo = Image.new("RGB", (W * ESCALA, H * ESCALA), VERDE)
d = ImageDraw.Draw(lienzo, "RGBA")

def fuente(ruta, tam, idx=0):
    return ImageFont.truetype(ruta, tam * ESCALA, index=idx)

SERIF = "/System/Library/Fonts/Supplemental/Iowan Old Style.ttc"
SANS = "/System/Library/Fonts/Avenir Next.ttc"

def estrella(cx, cy, r, color, factor=1.0):
    """La marca de Bynoesis: la estrella de ocho puntas de noesis-mark.svg."""
    puntos = [(32, 3), (38, 26), (61, 32), (38, 38), (32, 61), (26, 38), (3, 32), (26, 26)]
    return [(cx + (x - 32) / 29 * r * factor, cy + (y - 32) / 29 * r * factor)
            for x, y in puntos]

# Estrella grande, muy tenue, sangrando por la derecha. Sin datos, sin pantallas.
d.polygon(estrella(1075 * ESCALA, 315 * ESCALA, 300 * ESCALA, None), fill=(46, 139, 116, 46))
d.polygon(estrella(1075 * ESCALA, 315 * ESCALA, 168 * ESCALA, None), fill=(46, 139, 116, 64))

# Banda cálida inferior: el crema de la marca, para que no sea un bloque verde.
d.rectangle([0, (H - 10) * ESCALA, W * ESCALA, H * ESCALA], fill=VERDE_2)

M = 84 * ESCALA   # margen

# --- Marca ---------------------------------------------------------------
d.polygon(estrella(M + 21 * ESCALA, 92 * ESCALA, 21 * ESCALA, None), fill=VERDE_2 + (255,))
d.polygon(estrella(M + 21 * ESCALA, 92 * ESCALA, 11 * ESCALA, None), fill=CREMA + (255,))
f_marca = fuente(SANS, 30, idx=2)
d.text((M + 54 * ESCALA, 92 * ESCALA), "Bynoesis", font=f_marca, fill=CREMA, anchor="lm")

# --- Titular -------------------------------------------------------------
f_titular = fuente(SERIF, 76, idx=1)   # Bold
d.text((M, 222 * ESCALA), "Tu negocio,", font=f_titular, fill=CREMA, anchor="ls")
d.text((M, 310 * ESCALA), "por WhatsApp.", font=f_titular, fill=CREMA, anchor="ls")

# --- Bajada --------------------------------------------------------------
f_bajada = fuente(SANS, 29, idx=7)   # Regular: se lee mejor en miniatura
d.text((M, 378 * ESCALA), "Facturas, cobros y agenda para autónomos",
       font=f_bajada, fill=CREMA_SUAVE, anchor="ls")
d.text((M, 422 * ESCALA), "y pequeños negocios de servicios.",
       font=f_bajada, fill=CREMA_SUAVE, anchor="ls")

# --- Pie -----------------------------------------------------------------
f_pie = fuente(SANS, 26, idx=2)
d.text((M, 528 * ESCALA), "bynoesis.com", font=f_pie, fill=(122, 184, 163), anchor="ls")

SALIDA = Path(__file__).resolve().parents[1] / "src/noesis/web/static/bynoesis-social-card.png"
lienzo.resize((W, H), Image.LANCZOS).save(SALIDA, optimize=True)
print(f"escrita: {SALIDA}")
