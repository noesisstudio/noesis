"""Los dos documentos de dos paginas: lo esencial del modelo, nada mas.

Los libros de `analysis/` tienen diecinueve hojas y estan bien para trabajar, pero
no para ensenarselos a nadie. Esto es lo contrario: dos paginas con lo que decide,
generadas con los datos reales del panel en el momento de descargarlas.

La regla de cortar es simple: entra lo que cambia una decision. Los tres
equilibrios, lo que deja cada plan, si cabe en las horas del founder, cuanta caja
hace falta por el camino y en que se diferencia lo real de lo supuesto. Todo lo
demas se queda en el panel, que es donde se puede mirar con calma.
"""

from __future__ import annotations

from datetime import date

from . import officedocs as O


def _eur(value, dec: int = 2) -> str:
    if value is None:
        return "—"
    texto = f"{value:,.{dec}f}".replace(",", " ").replace(".", ",")
    return f"{texto} €"


def _pct(value) -> str:
    return "—" if value is None else f"{value * 100:.1f} %".replace(".", ",")


def _num(value) -> str:
    return "—" if value is None else f"{value:,.0f}".replace(",", ".")


def _parte(rep: dict) -> str:
    """La frase que resume el modelo entero, con los numeros ya dentro."""
    eq = next((n for n in rep["equilibrios"] if n["clave"]), None)
    cuentas = eq["cuentas"] if eq else None
    rampa = rep["rampa"]
    a = rep["assumptions"]
    minima = rampa["caja_minima"] or 0
    falta = abs(minima) if minima < 0 else 0
    cuando = (f"Se llega en el mes {rampa['mes_positivo']}"
              if rampa["mes_positivo"] else
              "Con estos supuestos no se llega dentro de 36 meses")
    caja = (f"la caja baja hasta {_eur(minima, 0)}"
            + (f": faltan {_eur(falta, 0)} adicionales a la caja inicial; el plan no "
               "es financiable" if falta > 0
               else ": la caja inicial cubre esta proyeccion de 36 meses"))
    equilibrio = (f"{_num(cuentas)} cuentas cubren la estructura, la cuota de autonomos y "
                  f"una retirada de {_eur(a['retirada'], 0)} al mes. "
                  if cuentas is not None else
                  "No existe equilibrio con una contribucion por cuenta nula o negativa. ")
    return f"{equilibrio}{cuando}, y por el camino {caja}."


def _tabla_equilibrios(rep: dict) -> list[list]:
    filas = [["Nivel", "Cuesta al mes", "Contribucion", "Cuentas"]]
    for n in rep["equilibrios"]:
        filas.append([n["nivel"], _eur(n["coste"], 0), _eur(n["contribucion"]),
                      _num(n["cuentas"])])
    return filas


def _tabla_planes(rep: dict) -> list[list]:
    filas = [["Plan", "Precio", "Coste", "Contrib. en caja", "Contrib. cargada",
              "Soporte"]]
    for p in rep["planes"]:
        filas.append([p["plan"], _eur(p["precio"], 0), _eur(p["cogs"]),
                      _eur(p["contribucion_caja"]), _eur(p["contribucion_cargada"]),
                      f"{p['soporte_min']:.0f} min"])
    med = rep["medias"]
    filas.append(["Media ponderada", _eur(med["arpu"]), _eur(med["cogs"]),
                  _eur(med["contribucion_caja"]), _eur(med["contribucion_cargada"]),
                  f"{med['soporte_min']:.1f} min"])
    return filas


def _tabla_real(rep: dict) -> list[list]:
    filas = [["Metrica", "Real hoy", "Supuesto", "Desviacion"]]
    for f in rep["observado"]["filas"]:
        real = f["real"]
        valor = (_num(real) if f["unidad"] == "cuentas" else _eur(real)) if real is not None else "—"
        sup = (_num(f["supuesto"]) if f["unidad"] == "cuentas" else _eur(f["supuesto"])) \
            if f["supuesto"] else "—"
        filas.append([f["etiqueta"], valor, sup,
                      _pct(f["desvio"]) if f["desvio"] is not None else "—"])
    return filas


def summary_docx(rep: dict, timeline: dict | None = None) -> bytes:
    """Word de dos paginas. Pagina 1: el negocio. Pagina 2: el tiempo y la caja."""
    a = rep["assumptions"]
    cap, cabe, rampa = rep["capacidad"], rep["cabe_en_horas"], rep["rampa"]
    obs = rep["observado"]
    hoy = date.today().strftime("%d/%m/%Y")

    veredicto = {
        "si": "Cabe en tus horas, con sitio para seguir vendiendo.",
        "justo": "Cabe, pero justo: casi no queda mes para vender.",
        "no": "No cabe: esa cartera te ocuparia el mes entero.",
        "sin_equilibrio": "No hay equilibrio: la contribucion por cuenta no es positiva.",
    }[cabe["estado"]]

    bloques: list[tuple] = [
        ("p", "Bynoesis · lo esencial del modelo economico", "Titulo"),
        ("p", f"Generado el {hoy} con los datos del panel. "
              + obs["aviso"], "Subtitulo"),
        ("p", "EL PARTE", "Etiqueta"),
        ("p", _parte(rep), "Normal"),
        ("p", "Los tres equilibrios", "Seccion"),
        ("p", "No hay un equilibrio: hay una escalera. Solo el tercero significa que "
              "esto da de comer.", "Nota"),
        ("tabla", _tabla_equilibrios(rep), [40, 20, 20, 20],
         ["left", "right", "right", "right"]),
        ("p", "Lo que deja cada plan", "Seccion"),
        ("p", "Hay dos contribuciones y no son dos opiniones: son dos negocios. En caja "
              "manda mientras atiende el founder, porque su tiempo es capacidad y no "
              "gasto. Cargada manda en cuanto ese soporte lo paga otra persona.", "Nota"),
        ("tabla", _tabla_planes(rep), [22, 14, 14, 18, 18, 14],
         ["left", "right", "right", "right", "right", "right"]),
        ("salto",),
        ("p", "El tiempo, que es el limite de verdad", "Seccion"),
        ("tabla", [
            ["Concepto", "Valor"],
            ["Horas al mes para vender y atender", f"{a['horas_mes']:.0f} h"],
            ["Soporte por cuenta asentada", f"{cap['soporte_min']:.1f} min"],
            ["Cuentas que se pueden atender en solitario", _num(cap["techo"])],
            ["Techo practico (soporte al 70 % de las horas)", _num(cap["practico"])],
            ["Horas que exige el equilibrio", f"{cabe['horas']:.1f} h"
             if cabe["cuentas"] is not None else "No existe equilibrio"],
            ["Veredicto", veredicto],
        ], [58, 42], ["left", "right"]),
        ("p", "La caja por el camino", "Seccion"),
        ("tabla", [
            ["Concepto", "Valor"],
            ["Mes en que deja de perder dinero",
             _num(rampa["mes_positivo"]) if rampa["mes_positivo"] else "no llega en 36"],
            ["Caja minima", _eur(rampa["caja_minima"], 0)],
            ["Caja inicial disponible", _eur(a["caja_inicial"], 0)],
            ["Mes en que el soporte pasa del 70 % de las horas",
             _num(rampa["mes_ahogo"]) if rampa["mes_ahogo"] else "no llega en 36"],
            ["Cuentas al mes 36", _num(rampa["cuentas_final"])],
            ["Vida media del cliente", f"{rep['vida_media']:.1f} meses"],
            ["LTV sobre contribucion en caja", _eur(rep["ltv_caja"], 0)],
            ["LTV / CAC", f"{rep['ltv_cac']:.1f}x" if rep["ltv_cac"] else "—"],
        ], [58, 42], ["left", "right"]),
        ("p", "Lo real frente a lo supuesto", "Seccion"),
        ("tabla", _tabla_real(rep), [40, 20, 20, 20],
         ["left", "right", "right", "right"]),
    ]

    if timeline and timeline.get("hay_cuentas"):
        ultimo = timeline["ultimo"]
        bloques.append(("p", f"Ultimo mes cerrado ({ultimo['mes']}): "
                             f"{_num(ultimo['cuentas'])} cuentas, "
                             f"{_num(ultimo['de_pago'])} de pago, "
                             f"{_num(ultimo['conexiones'])} conexiones y "
                             f"{_eur(ultimo['mrr'], 0)} de ingreso comprometido.", "Nota"))

    bloques.append(
        ("p", "Ninguna cifra de comportamiento de cliente esta medida: bajas, minutos "
              "de soporte por cuenta, horas por alta y mezcla de planes son supuestos "
              "de planificacion. Lo unico auditable linea a linea es el coste de "
              "servir una cuenta, que sale de tarifas publicadas del 15/07/2026. Este "
              "documento sirve para decidir que medir, no para prometer nada.", "Nota"))
    return O.build_docx(bloques)


def summary_xlsx(rep: dict, timeline: dict | None = None) -> bytes:
    """Excel de dos hojas con las mismas cifras, ya con formato de numero."""
    a = rep["assumptions"]
    cap, cabe, rampa = rep["capacidad"], rep["cabe_en_horas"], rep["rampa"]
    med = rep["medias"]
    T, C, X, E, P, N, S = (O.S_TITULO, O.S_CABECERA, O.S_TEXTO, O.S_EUR,
                           O.S_PCT, O.S_NUM, O.S_SECCION)
    EF, NOTA = O.S_EUR_FUERTE, O.S_NOTA

    esencial: list[list] = [
        [("Bynoesis · lo esencial del modelo economico", T)],
        [(f"Generado el {date.today().strftime('%d/%m/%Y')}. " + rep["observado"]["aviso"],
          NOTA)],
        [],
        [("Los tres equilibrios", S)],
        [("Nivel", C), ("Cuesta al mes", C), ("Contribucion", C), ("Cuentas", C)],
    ]
    for n in rep["equilibrios"]:
        estilo = EF if n["clave"] else E
        esencial.append([(n["nivel"], X), (n["coste"], estilo),
                         (n["contribucion"], E), (n["cuentas"], N)])
    esencial += [
        [],
        [("Lo que deja cada plan", S)],
        [("Plan", C), ("Precio", C), ("Coste", C), ("Contrib. en caja", C),
         ("Contrib. cargada", C), ("Margen bruto", C), ("Soporte (min)", C)],
    ]
    for p in rep["planes"]:
        esencial.append([(p["plan"], X), (p["precio"], E), (p["cogs"], E),
                         (p["contribucion_caja"], E), (p["contribucion_cargada"], E),
                         (p["margen_bruto"], P), (p["soporte_min"], N)])
    esencial.append([("Media ponderada", X), (med["arpu"], EF), (med["cogs"], E),
                     (med["contribucion_caja"], EF), (med["contribucion_cargada"], E),
                     ((med["arpu"] - med["cogs"]) / med["arpu"] if med["arpu"] else 0, P),
                     (round(med["soporte_min"], 1), N)])
    esencial += [
        [],
        [("El tiempo y la caja", S)],
        [("Concepto", C), ("Valor", C)],
        [("Horas al mes para vender y atender", X), (a["horas_mes"], N)],
        [("Soporte por cuenta asentada (min)", X), (round(cap["soporte_min"], 1), N)],
        [("Cuentas que se pueden atender en solitario", X), (cap["techo"], N)],
        [("Techo practico (70 % de las horas)", X), (cap["practico"], N)],
        [("Horas que exige el equilibrio", X),
         (round(cabe["horas"], 1) if cabe["cuentas"] is not None else "Sin equilibrio", N)],
        [("Mes en que deja de perder dinero", X),
         (rampa["mes_positivo"] if rampa["mes_positivo"] else "no llega en 36", N)],
        [("Caja minima", X), (rampa["caja_minima"], EF)],
        [("Caja inicial disponible", X), (a["caja_inicial"], E)],
        [("Cuentas al mes 36", X), (round(rampa["cuentas_final"]), N)],
        [("Vida media (meses)", X), (round(rep["vida_media"], 1), N)],
        [("LTV sobre contribucion en caja", X), (rep["ltv_caja"], E)],
        [("LTV / CAC", X), (round(rep["ltv_cac"], 1) if rep["ltv_cac"] else None, N)],
    ]

    datos: list[list] = [
        [("Lo real frente a lo supuesto", T)],
        [(rep["observado"]["aviso"], NOTA)],
        [],
        [("Metrica", C), ("Real hoy", C), ("Supuesto", C), ("Desviacion", C)],
    ]
    for f in rep["observado"]["filas"]:
        estilo = N if f["unidad"] == "cuentas" else E
        datos.append([(f["etiqueta"], X), (f["real"], estilo),
                      (f["supuesto"], estilo), (f["desvio"], P)])
    datos += [
        [],
        [("Supuestos que mas mueven el resultado", S)],
        [("Driver", C), ("Valor", C), ("Estado", C)],
        [("Bajas los tres primeros meses", X), (a["churn_nuevo"], P), ("sin medir", X)],
        [("Bajas a partir del cuarto mes", X), (a["churn_maduro"], P), ("sin medir", X)],
        [("Minutos de soporte por cuenta", X), (round(med["soporte_min"], 1), N),
         ("sin medir", X)],
        [("Horas por alta", X), (a["horas_alta"], N), ("sin medir", X)],
        [("Horas al mes del founder", X), (a["horas_mes"], N), ("sin medir", X)],
        [("Mezcla de planes (Autonomo)", X), (a["mix"][0], P), ("sin medir", X)],
        [("Recibos que no se cobran", X), (a["impagos"], P), ("sin medir", X)],
        [("Retirada mensual", X), (a["retirada"], E), ("decision", X)],
        [("Cuota de autonomos", X), (a["cuota_autonomos"], E), ("pendiente", X)],
        [("CAC", X), (a["cac"], E), ("sin medir", X)],
    ]

    if timeline and timeline.get("filas"):
        datos += [[], [("Evolucion mes a mes", S)],
                  [("Mes", C), ("Altas", C), ("Cuentas", C), ("De pago", C),
                   ("Conexiones", C), ("Ingreso", C), ("Coste real", C)]]
        for f in timeline["filas"]:
            datos.append([(f["mes"], X), (f["altas"], N), (f["cuentas"], N),
                          (f["de_pago"], N), (f["conexiones"], N),
                          (f["mrr"], E), (f["coste"], E)])
        datos.append([(timeline["nota"], NOTA)])

    return O.build_xlsx([
        {"nombre": "Lo esencial", "anchos": [42, 16, 16, 18, 18, 14, 14],
         "filas": esencial},
        {"nombre": "Datos y supuestos", "anchos": [38, 16, 16, 16, 14, 14, 14],
         "filas": datos},
    ])
