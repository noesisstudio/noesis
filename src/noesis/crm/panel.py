"""Los números de la página: gráficos, tablero, lista filtrada y siguiente tanda.

Todo se calcula aquí, en el servidor, y la página solo lo pinta: así el gráfico,
su tabla y las pruebas dicen exactamente lo mismo. Recibe fichas (dicts) y no
toca la base de datos.
"""
from __future__ import annotations

from datetime import date, timedelta

from .. import sales
from . import zonas
from .zonas import sin_tildes

# Hasta dónde llegó cada uno, aunque después se durmiera o se descartara. Se
# agrupa en cinco peldaños porque nueve barras no se leen de un vistazo.
PELDANOS = (
    ("lista", "En la lista", 0),
    ("contactado", "Contactados", 1),
    ("respuesta", "Han respondido", 2),
    ("piloto", "En piloto", 4),
    ("cliente", "Clientes", 6),
)
_CERRADOS = ("dormido", "descartado")
SEMANAS_PANEL = 12
PROVINCIAS_PANEL = 9
_MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct",
          "nov", "dic")


def _alcance(prospect: dict, toques: list[dict]) -> int:
    """El peldaño más alto que ha pisado, mirando también su historial."""
    indices = [0]
    estado = prospect.get("estado")
    if estado in sales.ORDEN_ESTADOS and estado not in _CERRADOS:
        indices.append(sales.ORDEN_ESTADOS.index(estado))
    for toque in toques:
        despues = toque.get("estado_despues")
        if despues in sales.ORDEN_ESTADOS and despues not in _CERRADOS:
            indices.append(sales.ORDEN_ESTADOS.index(despues))
    if toques:
        indices.append(1)
    return max(indices)


def _pct(parte: int, total: int) -> int:
    return round(parte * 100 / total) if total else 0


def _fecha(valor) -> date | None:
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def panel(prospects: list[dict], toques: list[dict],
          hoy: date | None = None) -> dict:
    """Los números de los gráficos, ya calculados: la página solo los pinta.

    Se calcula aquí para que el gráfico, su tabla y las pruebas digan lo mismo.
    Los que pidieron la baja no cuentan en ningún gráfico.
    """
    hoy = hoy or date.today()
    vivos = [p for p in prospects if not p.get("baja")]
    ids = {p["id"] for p in vivos}
    por_ficha: dict[int, list[dict]] = {}
    for toque in toques:
        if toque.get("prospect_id") in ids:
            por_ficha.setdefault(toque["prospect_id"], []).append(toque)
    alcance = {p["id"]: _alcance(p, por_ficha.get(p["id"], [])) for p in vivos}

    total = len(vivos)
    embudo, anterior = [], None
    for clave, etiqueta, minimo in PELDANOS:
        hay = sum(1 for valor in alcance.values() if valor >= minimo)
        embudo.append({
            "clave": clave, "etiqueta": etiqueta, "hay": hay,
            "ancho": _pct(hay, total),
            "del_total": _pct(hay, total),
            "del_anterior": _pct(hay, anterior) if anterior else None,
        })
        anterior = hay
    contactados = embudo[1]["hay"]
    respondieron = embudo[2]["hay"]
    hoy_iso = hoy.isoformat()
    vencidos = sum(
        1 for p in vivos
        if p.get("siguiente_el") and str(p["siguiente_el"]) <= hoy_iso
        and sales.ESTADOS.get(p.get("estado") or "lista", sales.ESTADOS["lista"])["abierto"])

    # --- Por provincia: dónde está la lista y cuánto se ha avanzado en cada una
    zonas: dict[str, dict] = {}
    for p in vivos:
        nombre = p.get("provincia") or "Sin provincia"
        zona = zonas.setdefault(nombre, {
            "nombre": nombre, "total": 0, "sin": 0, "contactados": 0,
            "respuesta": 0, "cerrados": 0})
        zona["total"] += 1
        if p.get("estado") in _CERRADOS:
            zona["cerrados"] += 1
        elif alcance[p["id"]] >= 2:
            zona["respuesta"] += 1
        elif alcance[p["id"]] >= 1:
            zona["contactados"] += 1
        else:
            zona["sin"] += 1
    ordenadas = sorted(zonas.values(), key=lambda z: (-z["total"], z["nombre"]))
    provincias = ordenadas[:PROVINCIAS_PANEL]
    if len(ordenadas) > PROVINCIAS_PANEL:
        resto = {"nombre": f"Otras {len(ordenadas) - PROVINCIAS_PANEL}",
                 "total": 0, "sin": 0, "contactados": 0, "respuesta": 0,
                 "cerrados": 0}
        for zona in ordenadas[PROVINCIAS_PANEL:]:
            for campo in ("total", "sin", "contactados", "respuesta", "cerrados"):
                resto[campo] += zona[campo]
        provincias.append(resto)
    tope = max((z["total"] for z in provincias), default=0)
    for zona in provincias:
        zona["ancho"] = _pct(zona["total"], tope)
        zona["tramos"] = [
            {"clave": campo, "etiqueta": etiqueta, "hay": zona[campo],
             "ancho": round(zona[campo] * 100 / zona["total"], 2)
             if zona["total"] else 0}
            for campo, etiqueta in TRAMOS_ZONA if zona[campo]]

    # --- Actividad: contactos anotados por semana, de lunes a domingo
    lunes = hoy - timedelta(days=hoy.weekday())
    inicios = [lunes - timedelta(weeks=n) for n in range(SEMANAS_PANEL - 1, -1, -1)]
    cuenta = {inicio: 0 for inicio in inicios}
    for lista in por_ficha.values():
        for toque in lista:
            cuando = _fecha(toque.get("fecha"))
            if not cuando:
                continue
            inicio = cuando - timedelta(days=cuando.weekday())
            if inicio in cuenta:
                cuenta[inicio] += 1
    tope_semana = max(cuenta.values(), default=0)
    semanas = [{
        "inicio": inicio.isoformat(),
        "etiqueta": f"{inicio.day} {_MESES[inicio.month - 1]}",
        "hay": cuenta[inicio],
        "alto": _pct(cuenta[inicio], tope_semana),
        "actual": inicio == lunes,
    } for inicio in inicios]

    return {
        "total": total,
        "cifras": [
            {"clave": "lista", "etiqueta": "En la lista", "valor": total,
             "nota": (f"{embudo[0]['hay'] - contactados} sin contactar"
                      if total else "Aún no hay nadie")},
            {"clave": "contactado", "etiqueta": "Contactados",
             "valor": contactados,
             "nota": (f"{_pct(contactados, total)} % de la lista"
                      if total else "—")},
            {"clave": "respuesta", "etiqueta": "Han respondido",
             "valor": respondieron,
             "nota": (f"{_pct(respondieron, contactados)} % de los contactados"
                      if contactados else "Aún no has contactado a nadie")},
            {"clave": "hoy", "etiqueta": "Te esperan hoy", "valor": vencidos,
             "nota": "seguimientos con fecha de hoy o anterior"},
        ],
        "embudo": embudo,
        "cerrados": {
            "dormido": sum(1 for p in vivos if p.get("estado") == "dormido"),
            "descartado": sum(1 for p in vivos
                              if p.get("estado") == "descartado"),
            "bajas": len(prospects) - total,
        },
        "provincias": provincias,
        "con_provincia": any(p.get("provincia") for p in vivos),
        "semanas": semanas,
        "contactos_semanas": sum(cuenta.values()),
        "contactos_semana_actual": cuenta[lunes],
    }


# Los cuatro tramos de la barra de cada provincia, en el orden en que se pintan.
TRAMOS_ZONA = (
    ("respuesta", "Han respondido"),
    ("contactados", "Contactados, sin respuesta"),
    ("sin", "Sin contactar"),
    ("cerrados", "Dormidos o descartados"),
)


# ---------------------------------------------------------- El tablero ------
TARJETAS_POR_COLUMNA = 6


def tablero(prospects: list[dict]) -> list[dict]:
    """Una columna por estado, con lo más urgente arriba.

    Recibe fichas ya enriquecidas. Cada columna enseña unas pocas tarjetas y
    dice cuántas hay: mil gestorías sin escribir no caben en una columna, y
    enseñarlas todas escondería las seis que sí están en marcha.
    """
    columnas = []
    for clave, meta in sales.ESTADOS.items():
        fichas = [p for p in prospects
                  if not p.get("baja") and (p.get("estado") or "lista") == clave]
        fichas.sort(key=lambda p: (not p.get("vencido"),
                                   str(p.get("siguiente_el") or "9999"),
                                   (p.get("nombre") or "").lower()))
        columnas.append({
            "clave": clave, "etiqueta": meta["etiqueta"],
            "significa": meta["significa"], "abierto": meta["abierto"],
            "hay": len(fichas),
            "tarjetas": fichas[:TARJETAS_POR_COLUMNA],
            "mas": max(0, len(fichas) - TARJETAS_POR_COLUMNA),
        })
    return columnas


# ------------------------------------------------------- Filtro y tanda -----
POR_PAGINA = 50


def filtrar(prospects: list[dict], *, tipo: str = "", estado: str = "",
            provincia: str = "", busca: str = "") -> list[dict]:
    """La lista que se ve: por tipo, estado, provincia y lo que se escriba."""
    aguja = sin_tildes(busca).strip()
    salida = []
    for p in prospects:
        if tipo and (p.get("tipo") or "autonomo") != tipo:
            continue
        if estado and (p.get("estado") or "lista") != estado:
            continue
        if provincia and (p.get("provincia") or "Sin provincia") != provincia:
            continue
        if aguja and aguja not in sin_tildes(" ".join(
                str(p.get(c) or "") for c in (
                    "nombre", "email", "telefono", "poblacion", "provincia",
                    "web", "presentado_por"))):
            continue
        salida.append(p)
    return salida


def paginar(filas: list, pagina: int, por_pagina: int = POR_PAGINA) -> dict:
    paginas = max(1, -(-len(filas) // por_pagina))
    pagina = min(max(1, pagina), paginas)
    desde = (pagina - 1) * por_pagina
    return {"filas": filas[desde:desde + por_pagina], "pagina": pagina,
            "paginas": paginas, "total": len(filas),
            "desde": desde + 1 if filas else 0,
            "hasta": min(desde + por_pagina, len(filas))}


def zonas_pendientes(prospects: list[dict]) -> list[dict]:
    """Provincias con gente sin escribir, de más a menos."""
    cuenta: dict[str, int] = {}
    for p in prospects:
        if (not p.get("baja") and (p.get("estado") or "lista") == "lista"
                and p.get("email")):
            zona = p.get("provincia") or "Sin provincia"
            cuenta[zona] = cuenta.get(zona, 0) + 1
    return [{"nombre": zona, "hay": hay} for zona, hay in
            sorted(cuenta.items(), key=lambda par: (-par[1], par[0]))]


def tanda(prospects: list[dict], zona: str = "",
          cuantos: int = sales.LOTE_DIARIO) -> list[dict]:
    """Los siguientes a los que escribir: sin contactar, con correo, de una zona.

    Primero los que tienen el correo comprobado: un correo que rebota no solo
    se pierde, también resta reputación al dominio desde el que se envía.
    """
    candidatos = [
        p for p in prospects
        if not p.get("baja") and (p.get("estado") or "lista") == "lista"
        and p.get("email")
        and (not zona or (p.get("provincia") or "Sin provincia") == zona)]
    candidatos.sort(key=lambda p: (not zonas.correo_verificado(
        p.get("correo_verificacion")), (p.get("nombre") or "").lower()))
    return candidatos[:cuantos]
