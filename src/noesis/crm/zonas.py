"""Provincias, lengua y correo comprobado: lo que la hoja escribe de mil maneras.

No depende de `sales.py` a propósito: `sales.enriquecer` usa esto para decidir en
qué lengua va el guion, y un módulo que se importan el uno al otro no arranca.
"""
from __future__ import annotations

import re
import unicodedata


def sin_tildes(texto) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn").lower()


# El código postal dice la provincia aunque la hoja no la traiga.
CP_PROVINCIA = {
    "01": "Álava", "02": "Albacete", "03": "Alicante", "04": "Almería",
    "05": "Ávila", "06": "Badajoz", "07": "Illes Balears", "08": "Barcelona",
    "09": "Burgos", "10": "Cáceres", "11": "Cádiz", "12": "Castellón",
    "13": "Ciudad Real", "14": "Córdoba", "15": "A Coruña", "16": "Cuenca",
    "17": "Girona", "18": "Granada", "19": "Guadalajara", "20": "Gipuzkoa",
    "21": "Huelva", "22": "Huesca", "23": "Jaén", "24": "León", "25": "Lleida",
    "26": "La Rioja", "27": "Lugo", "28": "Madrid", "29": "Málaga",
    "30": "Murcia", "31": "Navarra", "32": "Ourense", "33": "Asturias",
    "34": "Palencia", "35": "Las Palmas", "36": "Pontevedra", "37": "Salamanca",
    "38": "Santa Cruz de Tenerife", "39": "Cantabria", "40": "Segovia",
    "41": "Sevilla", "42": "Soria", "43": "Tarragona", "44": "Teruel",
    "45": "Toledo", "46": "Valencia", "47": "Valladolid", "48": "Bizkaia",
    "49": "Zamora", "50": "Zaragoza", "51": "Ceuta", "52": "Melilla",
}
# Cómo se escribe la misma provincia en una hoja hecha a mano.
_ALIAS_PROVINCIA = {
    "lerida": "Lleida", "gerona": "Girona", "la coruna": "A Coruña",
    "coruna": "A Coruña", "orense": "Ourense", "vizcaya": "Bizkaia",
    "guipuzcoa": "Gipuzkoa", "alava": "Álava", "araba": "Álava",
    "baleares": "Illes Balears", "islas baleares": "Illes Balears",
    "mallorca": "Illes Balears", "castello": "Castellón",
    "alacant": "Alicante", "tenerife": "Santa Cruz de Tenerife",
    "rioja": "La Rioja",
}
_PROVINCIAS = {sin_tildes(v): v for v in CP_PROVINCIA.values()}
# Catalán a Cataluña, castellano al resto: es la regla de la campaña.
_PROVINCIAS_CATALAN = {"lleida", "girona", "tarragona", "barcelona"}
RE_CP = re.compile(r"\b(\d{5})\b[\s,]*([^,;()\d]{2,60})?")


def normalizar_provincia(texto) -> str | None:
    """«LLEIDA», «Lérida» y «lleida » son la misma barra del gráfico."""
    limpio = " ".join(str(texto or "").split())
    if not limpio:
        return None
    plano = sin_tildes(limpio)
    if plano in _ALIAS_PROVINCIA:
        return _ALIAS_PROVINCIA[plano]
    if plano in _PROVINCIAS:
        return _PROVINCIAS[plano]
    return limpio.title()[:60] if limpio.isupper() or limpio.islower() else limpio[:60]


def lengua_de(provincia) -> str:
    return "ca" if sin_tildes(provincia or "") in _PROVINCIAS_CATALAN else "es"


def correo_verificado(texto) -> bool:
    """Lee la columna «VERIFICACION CORREO» de la hoja sin exigir una palabra fija."""
    plano = sin_tildes(texto or "")
    if not plano or re.search(r"\bno\b|falla|rebota|invalid|dudos", plano):
        return False
    return bool(re.search(r"exist|verific|valid|\bok\b|correct|comprob", plano))
