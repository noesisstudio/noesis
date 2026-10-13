"""Entender una pestaña de la hoja de Google: columnas, filas y estado escrito a mano.

Es lógica pura, sin base de datos ni red: recibe el texto CSV y devuelve filas
limpias. Lo que se hace con ellas está en `sincronizar.py`.

La regla que explica el resto: **la hoja manda en los datos de contacto y el CRM
en el estado, el historial y la baja.** Aquí solo se decide qué dice cada fila.
"""
from __future__ import annotations

import csv
import io
import re

from .. import sales
from . import zonas
from .zonas import sin_tildes

# Cómo se llama cada columna en la hoja «Leads» y en cualquier otra parecida.
# Las claves van sin tildes y en minúsculas; el valor es el campo de la ficha.
_COLUMNAS_HOJA = {
    "empresa": "nombre", "nombre": "nombre", "name": "nombre",
    "gestoria": "nombre", "despacho": "nombre", "razon social": "nombre",
    "titular": "nombre",
    "direccion": "direccion", "adreca": "direccion", "address": "direccion",
    "domicilio": "direccion",
    "poblacion": "poblacion", "ciudad": "poblacion", "municipio": "poblacion",
    "localidad": "poblacion",
    "provincia": "provincia",
    "telefono": "telefono", "tel": "telefono", "movil": "telefono",
    "phone": "telefono",
    "email": "email", "correo": "email", "e-mail": "email", "mail": "email",
    "email ia": "email", "correo electronico": "email",
    "web": "web", "pagina web": "web", "website": "web", "url": "web",
    "sitio web": "web",
    "estado": "hoja_estado", "status": "hoja_estado",
    "verificacion correo": "correo_verificacion",
    "verificacion": "correo_verificacion",
    "verificacion email": "correo_verificacion",
    "enviado": "hoja_enviado", "contactado": "hoja_enviado",
    "fecha envio": "hoja_enviado", "fecha contacto": "hoja_enviado",
    "oficio": "oficio", "actividad": "oficio", "sector": "oficio",
}
# Lo que el founder escribe en la columna ESTADO o ENVIADO de la hoja y a qué
# peldaño equivale. Se mira por orden: lo más avanzado primero.
_PISTAS_ESTADO = (
    ("descartado", ("no contactar", "no escribir", "descart", "no interes",
                    "no le interesa", "rechaz", "baja ", "de baja")),
    ("piloto", ("piloto", "probando", "en prueba")),
    ("cita", ("reunion", "cita", "videollamada", "demo ")),
    ("hablado", ("respond", "contest", "hablad", "resposta")),
    ("contactado", ("enviad", "contactad", "escrito ", "escrita", "enviat")),
)


def estado_desde_hoja(*textos) -> str | None:
    """Traduce lo escrito a mano en la hoja a un peldaño del embudo, o nada.

    «WEB ACTIVA» describe la web, no la conversación: no mueve a nadie.
    """
    plano = " ".join(sin_tildes(t or "") for t in textos).strip() + " "
    if not plano.strip() or plano.strip() in ("no", "-", "pendiente"):
        return None
    for estado, pistas in _PISTAS_ESTADO:
        # Al principio de palabra: «solicitar» no es una cita ni «trabaja» una baja.
        if any(re.search(r"\b" + re.escape(pista), plano) for pista in pistas):
            return estado
    return None


def _enviado(valor) -> bool:
    plano = sin_tildes(valor or "").strip()
    return bool(plano) and plano not in ("no", "-", "pendiente", "0", "false")


def clave_de_hoja(fila: dict) -> str:
    """Con qué se reconoce la misma fila en la siguiente lectura."""
    if fila.get("email"):
        return "e:" + fila["email"]
    if fila.get("telefono"):
        return "t:" + fila["telefono"]
    return "n:" + sin_tildes(fila.get("nombre") or "") + "|" + sin_tildes(
        fila.get("provincia") or "")


def parse_hoja(texto: str) -> dict:
    """Lee el CSV de una pestaña de Google Sheets y devuelve filas limpias.

    Devuelve `{"filas", "columnas", "ignoradas", "sin_datos"}`. No adivina: si la
    pestaña no tiene una columna de nombre y otra de correo o teléfono, es que
    se ha conectado la pestaña equivocada, y eso se dice en vez de importarla.
    """
    lector = list(csv.reader(io.StringIO((texto or "").lstrip("﻿"))))
    cabecera_en = None
    for indice, cruda in enumerate(lector[:6]):
        campos = {_COLUMNAS_HOJA.get(sin_tildes(c).strip()) for c in cruda}
        if "nombre" in campos and campos & {"email", "telefono"}:
            cabecera_en = indice
            break
    if cabecera_en is None:
        raise ValueError(
            "No encuentro una columna de nombre (EMPRESA) y otra de correo o "
            "teléfono en las primeras filas. ¿Es la pestaña correcta?")
    cabecera = [sin_tildes(c).strip() for c in lector[cabecera_en]]
    destinos = [_COLUMNAS_HOJA.get(c) for c in cabecera]
    filas, sin_datos, vistas = [], 0, set()
    for numero, cruda in enumerate(lector[cabecera_en + 1:], start=cabecera_en + 2):
        fila: dict = {}
        for destino, valor in zip(destinos, cruda):
            valor = " ".join((valor or "").split())
            if not destino or not valor or destino in fila:
                continue
            fila[destino] = valor
        correo = sales._RE_EMAIL.search(fila.get("email") or "")
        fila["email"] = correo.group(0).lower().rstrip(".") if correo else None
        fila["telefono"] = sales.normalizar_telefono(fila.get("telefono"))
        if not fila.get("nombre"):
            if not fila["email"]:
                sin_datos += 1 if any(c.strip() for c in cruda) else 0
                continue
            fila["nombre"] = fila["email"].split("@")[1]
        cp = zonas.RE_CP.search(fila.get("direccion") or "")
        if cp and not fila.get("poblacion") and cp.group(2):
            fila["poblacion"] = cp.group(2).strip(" .-")[:120] or None
        provincia = zonas.normalizar_provincia(fila.get("provincia"))
        if not provincia and cp:
            provincia = zonas.CP_PROVINCIA.get(cp.group(1)[:2])
        limpia = {
            "fila": numero,
            "nombre": fila["nombre"][:200],
            "direccion": (fila.get("direccion") or "")[:200] or None,
            "poblacion": (fila.get("poblacion") or "")[:120] or None,
            "provincia": provincia,
            "telefono": fila["telefono"],
            "email": fila["email"],
            "web": (fila.get("web") or "")[:200] or None,
            "oficio": sales.adivina_oficio(fila.get("oficio") or ""),
            "hoja_estado": (fila.get("hoja_estado") or "")[:120] or None,
            "correo_verificacion": (fila.get("correo_verificacion") or "")[:120]
                                   or None,
        }
        pista = estado_desde_hoja(fila.get("hoja_estado"),
                                  fila.get("hoja_enviado"))
        if not pista and _enviado(fila.get("hoja_enviado")):
            pista = "contactado"
        limpia["estado_pista"] = pista
        limpia["clave"] = clave_de_hoja(limpia)
        # La misma gestoría dos veces en la hoja entra una: la primera.
        if limpia["clave"] in vistas:
            continue
        vistas.add(limpia["clave"])
        filas.append(limpia)
    return {
        "filas": filas,
        "columnas": [lector[cabecera_en][i].strip()
                     for i, d in enumerate(destinos) if d],
        "ignoradas": [lector[cabecera_en][i].strip()
                      for i, d in enumerate(destinos)
                      if not d and lector[cabecera_en][i].strip()],
        "sin_datos": sin_datos,
    }


# Campos que son de la hoja: una lectura nueva los pone al día. Todo lo demás
# (estado, siguiente paso, nota, baja, historial) es del CRM y no se toca.
CAMPOS_DE_HOJA = ("nombre", "direccion", "poblacion", "provincia", "telefono",
                  "email", "web", "hoja_estado", "correo_verificacion")


def avanza(actual: str, pista: str | None) -> bool:
    """¿Lo que dice la hoja va más lejos que lo que sabe el CRM?

    Solo hacia delante y solo en fichas abiertas: la hoja nunca devuelve a nadie
    a un peldaño anterior ni reabre a quien se cerró aquí.
    """
    if not pista or pista not in sales.ESTADOS or actual not in sales.ESTADOS:
        return False
    if not sales.ESTADOS[actual]["abierto"]:
        return False
    if pista == "descartado":
        return True
    return sales.ORDEN_ESTADOS.index(pista) > sales.ORDEN_ESTADOS.index(actual)
