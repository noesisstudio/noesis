"""Genera la version 2 del modelo economico de Bynoesis en xlsx.

Que cambia respecto al modelo de agosto (que se conserva intacto):

1. Una sola hoja de mandos. Todo lo editable vive en `Panel`; el resto son
   formulas que apuntan alli. Cambiar la mezcla de planes o las bajas mueve el
   modelo entero, incluida la curva de caja.
2. Incorpora las cuatro capas que faltaban y que documenta
   `Canal-comercial-y-comisiones.md` (16/09/2026): bajas y vida del cliente,
   coste de adquisicion, canal comercial con sus cinco estructuras de comision,
   y caja mes a mes hasta el break-even.
3. Las cifras ancla del 15/07/2026 no se tocan: precio, COGS y contribucion por
   plan entran como dato verificado y todo lo demas se deriva de ellas. Lo que
   no esta medido se marca como supuesto, no como hecho.

Fuentes: docs/06-negocio-y-finanzas/Unit-economics-y-cerebro-interno.md y
docs/06-negocio-y-finanzas/Canal-comercial-y-comisiones.md.

Uso: py analysis/build_modelo_economico_v2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
except ModuleNotFoundError:  # pragma: no cover - herramienta de analisis
    raise SystemExit(
        'Falta openpyxl. Instalalo con: pip install -e ".[analysis]"'
    )

# --- Marca (docs/design/STYLE_TOKENS.json) ---------------------------------
FOREST = "FF14463B"
TEAL = "FF2E8B74"
CREAM = "FFF4F1EA"
SAND = "FFE7E0D1"
INK = "FF15211C"
MUTED = "FF5D6B66"
WHITE = "FFFFFFFF"
INPUT = "FF0000CC"   # azul: celda editable, convencion de modelos financieros
WARN = "FFB7831F"
STOP = "FFC0533F"
OKC = "FF1F8A6D"

HAIR = Side(style="thin", color="FFDDD8CC")
BOX = Border(left=HAIR, right=HAIR, top=HAIR, bottom=HAIR)

EUR = '#,##0.00\\ "€"'
EUR0 = '#,##0\\ "€"'
PCT = '0.0%'
PCT0 = '0%'
NUM = '#,##0'
DEC = '#,##0.0'

FUENTE = "Aptos"

# --- Cifras ancla, verificadas en el analisis del 15/07/2026 ---------------
# No se descomponen mas: el documento publica precio, COGS de software y
# contribucion; el bloque intermedio se calcula por diferencia dentro del libro
# para no inventar un desglose que nadie ha medido.
PLANES = [
    # nombre, precio, cogs_software, contribucion, anual
    ("Autonomo", 29, 1.48, 20.83, 319),
    ("Negocio", 49, 3.04, 34.89, 539),
    ("Premium", 99, 18.47, 56.96, 1089),
]
MEZCLA = [0.55, 0.35, 0.10]

UE_FILA_MEDIA = 12        # fila de la media ponderada en Unit_Economics
CANAL_FILA_D = 9          # estructura D, la propuesta, en Canal_Comision
CAJA_FILA_BREAKEVEN = 6   # «mes en que el resultado se vuelve positivo»
CAJA_FILA_MINIMA = 7      # «caja minima»
CAJA_TABLA_INICIO = 12    # primera fila de los 36 meses

DESTINO = (Path(__file__).resolve().parents[1] / "docs" /
           "06-negocio-y-finanzas" / "Bynoesis-Modelo-Economico-v2.xlsx")


def _titulo(ws, texto: str, subtitulo: str = "") -> int:
    ws["A1"] = texto
    ws["A1"].font = Font(name=FUENTE, size=16, bold=True, color=FOREST)
    fila = 2
    if subtitulo:
        ws["A2"] = subtitulo
        ws["A2"].font = Font(name=FUENTE, size=10, color=MUTED)
        ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=2, start_column=1, end_row=3, end_column=8)
        ws.row_dimensions[2].height = 30
        fila = 4
    return fila + 1


def _cabecera(ws, fila: int, titulos: list[str]) -> None:
    for columna, texto in enumerate(titulos, start=1):
        celda = ws.cell(row=fila, column=columna, value=texto)
        celda.font = Font(name=FUENTE, size=10, bold=True, color=WHITE)
        celda.fill = PatternFill("solid", fgColor=FOREST)
        celda.border = BOX
        celda.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.row_dimensions[fila].height = 28


def _fila(ws, fila: int, valores: list, formatos: list[str | None],
          *, editable: bool = False, negrita: bool = False) -> None:
    for columna, valor in enumerate(valores, start=1):
        celda = ws.cell(row=fila, column=columna, value=valor)
        celda.border = BOX
        formato = formatos[columna - 1] if columna - 1 < len(formatos) else None
        if formato:
            celda.number_format = formato
        color = INPUT if (editable and columna == 2) else INK
        celda.font = Font(name=FUENTE, size=10, bold=negrita, color=color)


def _nota(ws, fila: int, texto: str) -> None:
    celda = ws.cell(row=fila, column=1, value=texto)
    celda.font = Font(name=FUENTE, size=9, color=MUTED)
    celda.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila + 1,
                   end_column=8)
    ws.row_dimensions[fila].height = 26


def _anchos(ws, anchos: dict[str, int]) -> None:
    for columna, ancho in anchos.items():
        ws.column_dimensions[columna].width = ancho


def _hoja(wb, nombre: str):
    ws = wb.create_sheet(nombre)
    ws.sheet_properties.tabColor = TEAL
    ws.sheet_view.showGridLines = False
    return ws


# ---------------------------------------------------------------- PANEL ---
def panel(wb) -> None:
    ws = wb.active
    ws.title = "Panel"
    ws.sheet_properties.tabColor = FOREST
    ws.sheet_view.showGridLines = False
    _anchos(ws, {"A": 42, "B": 16, "C": 14, "D": 14, "E": 14, "F": 52})

    fila = _titulo(
        ws, "Bynoesis · modelo economico v2",
        "Lo azul se edita; lo negro es formula. Cambia un supuesto aqui y se "
        "mueve todo el libro, incluida la curva de caja. Las cifras por plan "
        "vienen del analisis del 15/07/2026; las bajas, el CAC y el canal son "
        "supuestos sin medir y estan marcados como tales.",
    )

    ws.cell(row=fila, column=1, value="Supuestos que decides tu").font = Font(
        name=FUENTE, size=12, bold=True, color=FOREST)
    fila += 1
    _cabecera(ws, fila, ["Supuesto", "Valor", "", "", "", "De donde sale"])
    fila += 1

    inicio_supuestos = fila
    supuestos = [
        ("Mezcla de planes · Autonomo", MEZCLA[0], PCT0,
         "Reparto de cuentas supuesto en el analisis del 15/07/2026."),
        ("Mezcla de planes · Negocio", MEZCLA[1], PCT0,
         "Las tres deben sumar 100 %."),
        ("Mezcla de planes · Premium", MEZCLA[2], PCT0,
         "Premium al 10 % es prudente: es el plan de menor margen."),
        ("Bajas al mes (churn)", 0.04, PCT,
         "SUPUESTO SIN MEDIR. No hay clientes de pago que permitan medirlo."),
        ("Coste de captar un cliente (CAC)", 150, EUR,
         "SUPUESTO SIN MEDIR. Figuraba en el modelo editable anterior."),
        ("Gasto fijo mensual (opex)", 3500, EUR0,
         "Constante del analisis del 15/07/2026."),
        ("Altas al mes", 10, NUM,
         "Ritmo de captacion que quieres simular."),
        ("Cuota de implantacion", 99, EUR0,
         "Propuesta del 16/09/2026; se perdona en contratacion anual."),
        ("Cuota de implantacion: % que la paga", 1.0, PCT0,
         "Con 0 % el modelo se comporta como si no existiera."),
        ("Caja inicial", 0, EUR0,
         "Dinero disponible al empezar la simulacion."),
    ]
    for etiqueta, valor, formato, origen in supuestos:
        _fila(ws, fila, [etiqueta, valor, None, None, None, origen],
              [None, formato, None, None, None, None], editable=True)
        fila += 1

    ws[f"B{inicio_supuestos}"].comment = None
    mezcla_a = f"$B${inicio_supuestos}"
    mezcla_n = f"$B${inicio_supuestos + 1}"
    mezcla_p = f"$B${inicio_supuestos + 2}"
    churn = f"$B${inicio_supuestos + 3}"
    cac = f"$B${inicio_supuestos + 4}"
    opex = f"$B${inicio_supuestos + 5}"
    altas = f"$B${inicio_supuestos + 6}"
    implantacion = f"$B${inicio_supuestos + 7}"
    pct_implantacion = f"$B${inicio_supuestos + 8}"
    caja_inicial = f"$B${inicio_supuestos + 9}"

    fila += 1
    aviso = ws.cell(
        row=fila, column=1,
        value="=IF(ABS(" + mezcla_a + "+" + mezcla_n + "+" + mezcla_p +
              "-1)>0.0001,\"AVISO: la mezcla de planes no suma 100 %\","
              "\"Mezcla correcta: suma 100 %\")")
    aviso.font = Font(name=FUENTE, size=10, bold=True, color=WARN)
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=6)
    fila += 2

    ws.cell(row=fila, column=1, value="Lo que sale de ahi").font = Font(
        name=FUENTE, size=12, bold=True, color=FOREST)
    fila += 1
    _cabecera(ws, fila, ["Resultado", "Valor", "", "", "", "Como se calcula"])
    fila += 1

    inicio_kpis = fila
    kpis = [
        ("Cuota media por cuenta (ARPU)",
         f"=Unit_Economics!$B${UE_FILA_MEDIA}", EUR,
         "Precio de cada plan por su peso en la mezcla."),
        ("Contribucion media por cuenta",
         f"=Unit_Economics!$D${UE_FILA_MEDIA}", EUR,
         "Lo que deja cada cuenta al mes despues de servirla."),
        ("Margen de contribucion",
         f"=IF(Panel!$B${inicio_kpis}=0,0,Panel!$B${inicio_kpis + 1}/"
         f"Panel!$B${inicio_kpis})", PCT,
         "Contribucion sobre cuota media."),
        ("Cuentas para cubrir el gasto fijo",
         f"=IF(Panel!$B${inicio_kpis + 1}<=0,\"-\","
         f"ROUNDUP({opex}/Panel!$B${inicio_kpis + 1},0))", NUM,
         "Break-even: gasto fijo entre contribucion media."),
        ("Vida media del cliente",
         f"=IF({churn}<=0,\"sin bajas\",1/{churn})", DEC,
         "Meses. Es 1 dividido entre las bajas mensuales."),
        ("Valor de un cliente (LTV)",
         f"=IF({churn}<=0,\"-\",Panel!$B${inicio_kpis + 1}/{churn})", EUR,
         "Contribucion por vida media. No es facturacion: es lo que deja."),
        ("LTV dividido entre CAC",
         f"=IF(OR({cac}<=0,{churn}<=0),\"-\","
         f"Panel!$B${inicio_kpis + 5}/{cac})", DEC,
         "Por debajo de 3 el negocio compra clientes demasiado caros."),
        ("Meses para recuperar el CAC",
         f"=IF(Panel!$B${inicio_kpis + 1}<=0,\"-\","
         f"{cac}/Panel!$B${inicio_kpis + 1})", DEC,
         "Payback. Por encima de 12 la caja sufre aunque el LTV sea bueno."),
        ("Mes en que la caja deja de bajar",
         f"=Caja_36m!$B${CAJA_FILA_BREAKEVEN}", NUM,
         "Primer mes con resultado mensual positivo, segun Caja_36m."),
        ("Caja minima que hace falta",
         f"=Caja_36m!$B${CAJA_FILA_MINIMA}", EUR0,
         "El punto mas bajo de la curva: el dinero que hay que poder aguantar."),
    ]
    for etiqueta, formula, formato, explicacion in kpis:
        _fila(ws, fila, [etiqueta, formula, None, None, None, explicacion],
              [None, formato, None, None, None, None], negrita=True)
        fila += 1

    ws.conditional_formatting.add(
        f"B{inicio_kpis + 6}",
        CellIsRule(operator="lessThan", formula=["3"],
                   font=Font(name=FUENTE, size=10, bold=True, color=STOP)))
    ws.conditional_formatting.add(
        f"B{inicio_kpis + 6}",
        CellIsRule(operator="greaterThanOrEqual", formula=["3"],
                   font=Font(name=FUENTE, size=10, bold=True, color=OKC)))

    fila += 1
    _nota(ws, fila,
          "Ninguna fila de bajas, CAC o comision es un dato observado: no hay "
          "todavia clientes de pago que permitan medirlos. El modelo sirve para "
          "ver que pasa si, no para afirmar que pasara. Primero tres a cinco "
          "clientes de pago y treinta dias de medicion.")

    return {
        "mezcla": (mezcla_a, mezcla_n, mezcla_p), "churn": churn, "cac": cac,
        "opex": opex, "altas": altas, "implantacion": implantacion,
        "pct_implantacion": pct_implantacion, "caja_inicial": caja_inicial,
        "arpu": f"Panel!$B${inicio_kpis}",
        "contribucion": f"Panel!$B${inicio_kpis + 1}",
        "vida": f"Panel!$B${inicio_kpis + 4}",
        "ltv": f"Panel!$B${inicio_kpis + 5}",
    }


# ------------------------------------------------------- UNIT ECONOMICS ---
def unit_economics(wb, ref: dict) -> None:
    ws = _hoja(wb, "Unit_Economics")
    _anchos(ws, {"A": 26, "B": 14, "C": 16, "D": 16, "E": 14, "F": 14,
                 "G": 40})

    fila = _titulo(
        ws, "Economia por plan",
        "Precio, coste de software y contribucion son cifras verificadas del "
        "15/07/2026. El bloque intermedio —soporte, onboarding, fijo por cuenta "
        "y comisiones— se calcula por diferencia: el analisis publica el total, "
        "no su desglose, y aqui no se inventa uno.",
    )

    _cabecera(ws, fila, [
        "Plan", "Precio", "Coste de software", "Contribucion",
        "Margen bruto", "Margen contribucion",
        "Soporte, onboarding y comisiones (por diferencia)"])
    fila += 1
    primera = fila
    for nombre, precio, cogs, contribucion, _anual in PLANES:
        _fila(ws, fila, [
            nombre, precio, cogs, contribucion,
            f"=IF(B{fila}=0,0,(B{fila}-C{fila})/B{fila})",
            f"=IF(B{fila}=0,0,D{fila}/B{fila})",
            f"=B{fila}-C{fila}-D{fila}",
        ], [None, EUR, EUR, EUR, PCT, PCT, EUR])
        fila += 1
    ultima = fila - 1

    fila += 1
    ws.cell(row=fila, column=1, value="Mezcla y medias").font = Font(
        name=FUENTE, size=12, bold=True, color=FOREST)
    fila += 1
    _cabecera(ws, fila, ["Concepto", "Cuota media", "Coste medio",
                         "Contribucion media", "", "", "Peso de cada plan"])
    fila += 1
    mezcla_a, mezcla_n, mezcla_p = ref["mezcla"]
    pesos = f"Panel!{mezcla_a},Panel!{mezcla_n},Panel!{mezcla_p}"
    assert fila == UE_FILA_MEDIA, (
        f"la media ponderada cae en {fila} y el Panel espera {UE_FILA_MEDIA}")
    _fila(ws, fila, [
        "Media ponderada",
        f"=B{primera}*Panel!{mezcla_a}+B{primera + 1}*Panel!{mezcla_n}"
        f"+B{ultima}*Panel!{mezcla_p}",
        f"=C{primera}*Panel!{mezcla_a}+C{primera + 1}*Panel!{mezcla_n}"
        f"+C{ultima}*Panel!{mezcla_p}",
        f"=D{primera}*Panel!{mezcla_a}+D{primera + 1}*Panel!{mezcla_n}"
        f"+D{ultima}*Panel!{mezcla_p}",
        None, None,
        f"=TEXT(Panel!{mezcla_a},\"0%\")&\" / \"&TEXT(Panel!{mezcla_n},\"0%\")"
        f"&\" / \"&TEXT(Panel!{mezcla_p},\"0%\")",
    ], [None, EUR, EUR, EUR, None, None, None], negrita=True)
    assert pesos  # referencia documentada arriba
    fila += 2

    _cabecera(ws, fila, ["Plan", "Cobro anual", "Equivalente al mes",
                         "Ahorro para el cliente", "", "", "Nota"])
    fila += 1
    for nombre, precio, _cogs, _contribucion, anual in PLANES:
        _fila(ws, fila, [
            nombre, anual, f"=B{fila}/12", f"={precio}*12-B{fila}", None, None,
            "Cobra once meses y da doce. Mejora caja y reduce comisiones.",
        ], [None, EUR0, EUR, EUR0, None, None, None])
        fila += 1

    fila += 1
    _nota(ws, fila,
          "El anual obliga a reservar capacidad de servicio durante doce meses, "
          "asi que su contribucion real depende del uso de voz y soporte que el "
          "piloto todavia no ha medido.")


# --------------------------------------------------------- VIDA Y LTV ----
def vida_y_ltv(wb, ref: dict) -> None:
    ws = _hoja(wb, "Vida_y_LTV")
    _anchos(ws, {"A": 18, "B": 18, "C": 18, "D": 18, "E": 18, "F": 40})

    fila = _titulo(
        ws, "Cuanto dura un cliente y cuanto deja",
        "Sin bajas no hay vida media y sin vida media no hay LTV: el modelo "
        "anterior describia un cliente que se queda para siempre. La fila "
        "resaltada es la que has puesto en el Panel.",
    )

    _cabecera(ws, fila, ["Bajas al mes", "Vida media (meses)",
                         "LTV (contribucion)", "LTV / CAC",
                         "Meses para recuperar el CAC", "Lectura"])
    fila += 1
    contribucion = ref["contribucion"]
    cac = ref["cac"]
    for tasa in (0.02, 0.03, 0.04, 0.05, 0.08, 0.10):
        _fila(ws, fila, [
            tasa,
            f"=1/A{fila}",
            f"={contribucion}/A{fila}",
            f"=IF(Panel!{cac}<=0,\"-\",C{fila}/Panel!{cac})",
            f"=IF({contribucion}<=0,\"-\",Panel!{cac}/{contribucion})",
            f"=IF(D{fila}=\"-\",\"\",IF(D{fila}>=3,\"Sostenible\","
            f"IF(D{fila}>=1,\"Justo: el cliente apenas paga su captacion\","
            f"\"Cada alta destruye valor\")))",
        ], [PCT, DEC, EUR, DEC, DEC, None],
            negrita=abs(tasa - 0.04) < 1e-9)
        fila += 1

    ws.conditional_formatting.add(
        f"D{fila - 6}:D{fila - 1}",
        CellIsRule(operator="lessThan", formula=["3"],
                   font=Font(name=FUENTE, size=10, color=STOP)))

    fila += 1
    _nota(ws, fila,
          "Ninguna de estas filas es un dato. El CAC de 150 EUR aguanta bien "
          "salvo con bajas altas, pero tanto el CAC como las bajas son "
          "supuestos hasta que haya clientes de pago que permitan medirlos.")


# -------------------------------------------------------------- CANAL ----
def canal(wb, ref: dict) -> None:
    ws = _hoja(wb, "Canal_Comision")
    _anchos(ws, {"A": 34, "B": 16, "C": 16, "D": 18, "E": 20, "F": 20,
                 "G": 46})

    fila = _titulo(
        ws, "Que cuesta cada forma de pagar al canal",
        "Las cinco estructuras evaluadas el 16/09/2026, recalculadas aqui con "
        "los supuestos del Panel. «Se lleva» es la parte de la contribucion "
        "total del cliente que acaba en el comercial: es la cifra que decide "
        "si el canal escala.",
    )

    contribucion = ref["contribucion"]
    arpu = ref["arpu"]
    vida = ref["vida"]
    altas = ref["altas"]

    _cabecera(ws, fila, [
        "Estructura", "Pago al alta", "% recurrente", "Meses de recurrente",
        "Coste total por cliente", "Se lleva (% contribucion)",
        "Recupera en (meses) · Gana a las altas del Panel en el mes 12"])
    fila += 1
    primera = fila
    estructuras = [
        ("A · una mensualidad al alta", f"={arpu}", 0.0, 0),
        ("B · dos mensualidades al alta", f"={arpu}*2", 0.0, 0),
        ("C · 20 % recurrente de por vida", 0, 0.20, 999),
        ("D · 1 mes + 10 % durante 12 meses", f"={arpu}", 0.10, 12),
        ("E · 2 meses + 5 % durante 12 meses", f"={arpu}*2", 0.05, 12),
    ]
    for nombre, alta, recurrente, meses in estructuras:
        # Coste total = pago al alta + % del ARPU durante los meses que dure la
        # comision, sin pasar de la vida media del cliente.
        coste = (f"=B{fila}+C{fila}*{arpu}*MIN(D{fila},{vida})")
        _fila(ws, fila, [
            nombre, alta, recurrente, meses, coste,
            f"=IF({contribucion}*{vida}=0,0,E{fila}/({contribucion}*{vida}))",
            f"=IF({contribucion}<=0,\"-\",TEXT(E{fila}/{contribucion},\"0.0\")"
            f"&\" meses · \"&TEXT(({contribucion}*12-E{fila})*Panel!{altas},"
            f"\"#,##0 €\"))",
        ], [None, EUR, PCT0, NUM, EUR, PCT, None],
            negrita=nombre.startswith("D"))
        if nombre.startswith("D"):
            assert fila == CANAL_FILA_D, (
                f"la estructura D cae en {fila} y se espera {CANAL_FILA_D}")
        fila += 1

    ws.conditional_formatting.add(
        f"F{primera}:F{fila - 1}",
        CellIsRule(operator="greaterThan", formula=["0.2"],
                   font=Font(name=FUENTE, size=10, bold=True, color=STOP)))

    fila += 1
    _nota(ws, fila,
          "La C es la mas cara por cliente y la mas atractiva para el "
          "comercial; la A es la mas barata y la que peor alinea, porque cobra "
          "igual si el cliente dura un mes que si dura tres anos. La D paga "
          "pronto, mantiene el coste de canal contenido y premia la "
          "permanencia: es la propuesta.")
    fila += 3

    ws.cell(row=fila, column=1,
            value="Por que un comercial a sueldo no sale").font = Font(
        name=FUENTE, size=12, bold=True, color=FOREST)
    fila += 1
    _cabecera(ws, fila, ["Concepto", "Valor", "", "", "", "", "Lectura"])
    fila += 1
    _fila(ws, fila, ["Coste cargado de un comercial", 2400, None, None, None,
                     None, "Sueldo, seguridad social y estructura."],
          [None, EUR0], editable=True)
    sueldo = f"$B${fila}"
    fila += 1
    _fila(ws, fila, ["Comision recurrente que cobraria", 0.20, None, None,
                     None, None, "Sobre la cuota, no sobre la contribucion."],
          [None, PCT0], editable=True)
    pct = f"$B${fila}"
    fila += 1
    _fila(ws, fila, [
        "Cuentas activas suyas para cubrirse",
        f"=IF({arpu}*{pct}<=0,\"-\",ROUNDUP({sueldo}/({arpu}*{pct}),0))",
        None, None, None, None,
        f"=\"A las altas del Panel, tardaria \"&"
        f"TEXT(B{fila}/MAX(Panel!{altas},1),\"0.0\")&\" meses en llegar.\"",
    ], [None, NUM], negrita=True)
    fila += 2
    _nota(ws, fila,
          "La conclusion no es «vende mas»: con esta cuota media, el canal "
          "tiene que ser comision pura, a tiempo parcial o por prescriptor. Una "
          "nomina exige una cartera propia que tarda anos en construirse.")


# ------------------------------------------------------- IMPLANTACION ----
def implantacion(wb, ref: dict) -> None:
    ws = _hoja(wb, "Implantacion")
    _anchos(ws, {"A": 40, "B": 18, "C": 18, "D": 18, "E": 18, "F": 44})

    fila = _titulo(
        ws, "La cuota de implantacion y la caja del alta",
        "Una cuota al alta convierte la captacion en caja neutra o positiva. "
        "Con cero clientes y sin inversor, esa es la diferencia entre poder "
        "pagar a diez comerciales y no poder pagar a uno.",
    )

    cuota = ref["implantacion"]
    porcentaje = ref["pct_implantacion"]
    arpu = ref["arpu"]
    altas = ref["altas"]

    _cabecera(ws, fila, ["Concepto", "Sin cuota", "Con la cuota del Panel",
                         "", "", "Nota"])
    fila += 1
    base = fila
    _fila(ws, fila, [
        "Primera cuota del cliente", f"={arpu}", f"={arpu}", None, None,
        "La mensualidad del mes en que firma.",
    ], [None, EUR, EUR])
    fila += 1
    _fila(ws, fila, [
        "Cuota de implantacion cobrada", 0,
        f"=Panel!{cuota}*Panel!{porcentaje}", None, None,
        "Se perdona en contratacion anual, de ahi el porcentaje del Panel.",
    ], [None, EUR, EUR])
    fila += 1
    _fila(ws, fila, [
        "Comision pagada al firmar (estructura D)",
        f"=-{arpu}", f"=-{arpu}", None, None,
        "La estructura D paga una mensualidad al alta.",
    ], [None, EUR, EUR])
    fila += 1
    _fila(ws, fila, [
        "Caja neta el mes de la firma",
        f"=SUM(B{base}:B{fila - 1})", f"=SUM(C{base}:C{fila - 1})", None, None,
        "Positivo significa que captar no consume caja ese mes.",
    ], [None, EUR, EUR], negrita=True)
    neta = fila
    fila += 1
    _fila(ws, fila, [
        "A las altas del Panel, al mes",
        f"=B{neta}*Panel!{altas}", f"=C{neta}*Panel!{altas}", None, None,
        "Lo que entra o sale de caja cada mes solo por captar.",
    ], [None, EUR0, EUR0], negrita=True)
    fila += 2
    _fila(ws, fila, [
        "Compromiso pendiente por ese cliente (10 % x 12 meses)",
        f"=-0.1*{arpu}*12", f"=-0.1*{arpu}*12", None, None,
        "No sale de caja al firmar, pero esta comprometido.",
    ], [None, EUR, EUR])
    fila += 1
    _fila(ws, fila, [
        "Coste total del canal por cliente",
        f"=Canal_Comision!$E${CANAL_FILA_D}",
        f"=Canal_Comision!$E${CANAL_FILA_D}", None, None,
        "Alta mas recurrente, tal como lo calcula la hoja Canal_Comision.",
    ], [None, EUR, EUR])
    fila += 1

    for columna in ("B", "C"):
        ws.conditional_formatting.add(
            f"{columna}{neta}:{columna}{fila - 1}",
            CellIsRule(operator="lessThan", formula=["0"],
                       font=Font(name=FUENTE, size=10, bold=True, color=STOP)))
        ws.conditional_formatting.add(
            f"{columna}{neta}:{columna}{fila - 1}",
            CellIsRule(operator="greaterThanOrEqual", formula=["0"],
                       font=Font(name=FUENTE, size=10, bold=True, color=OKC)))

    fila += 1
    _nota(ws, fila,
          "El analisis del 16/09/2026 cifraba en «unos 53 EUR» la caja neta de la "
          "firma comparando la cuota con la comision de alta (99 - 43). Aqui se "
          "desglosa el calculo completo, incluida la primera mensualidad y el "
          "compromiso recurrente, para que se vea de donde sale cada euro. "
          "Es coherente con lo que el modelo ya reconoce: el onboarding consume "
          "entre 30 y 120 minutos de founder que hoy se regalan. La cuota pone "
          "precio a ese trabajo en vez de esconderlo en el margen.")


# ---------------------------------------------------------- CAJA 36 M ----
def caja(wb, ref: dict) -> None:
    ws = _hoja(wb, "Caja_36m")
    _anchos(ws, {"A": 10, "B": 16, "C": 14, "D": 16, "E": 16, "F": 16,
                 "G": 16, "H": 16, "I": 18})

    fila = _titulo(
        ws, "Caja mes a mes, 36 meses",
        "El break-even en numero de cuentas no dice cuantos meses cuesta llegar "
        "ni cuanto dinero hay que poner por el camino, que es la pregunta que "
        "de verdad limita. Cada mes entran las altas del Panel y se van las "
        "bajas; la comision es la estructura D.",
    )

    altas = ref["altas"]
    churn = ref["churn"]
    opex = ref["opex"]
    contribucion = ref["contribucion"]
    arpu = ref["arpu"]
    cuota = ref["implantacion"]
    porcentaje = ref["pct_implantacion"]
    caja_inicial = ref["caja_inicial"]

    resumen = fila
    ws.cell(row=resumen, column=1, value="Resumen").font = Font(
        name=FUENTE, size=12, bold=True, color=FOREST)
    fila += 1
    # Las tres celdas que lee el Panel.
    tabla_inicio = CAJA_TABLA_INICIO
    tabla_fin = tabla_inicio + 35
    _fila(ws, fila, [
        "Mes en que el resultado mensual se vuelve positivo",
        f"=IFERROR(INDEX($A${tabla_inicio}:$A${tabla_fin},"
        f"MATCH(TRUE,INDEX($H${tabla_inicio}:$H${tabla_fin}>0,0),0)),"
        f"\"no llega en 36 meses\")",
    ], [None, NUM], negrita=True)
    fila += 1
    _fila(ws, fila, [
        "Caja minima (el punto mas bajo de la curva)",
        f"=MIN($I${tabla_inicio}:$I${tabla_fin})",
    ], [None, EUR0], negrita=True)
    fila += 1
    _fila(ws, fila, [
        "Cuentas activas al mes 36", f"=$C${tabla_fin}",
    ], [None, NUM], negrita=True)
    fila += 1
    _fila(ws, fila, [
        "Caja acumulada al mes 36", f"=$I${tabla_fin}",
    ], [None, EUR0], negrita=True)
    fila += 2

    _cabecera(ws, fila, [
        "Mes", "Altas", "Cuentas activas", "Ingreso (MRR)",
        "Contribucion", "Comision del canal", "Implantacion cobrada",
        "Resultado del mes", "Caja acumulada"])
    fila += 1
    assert fila == tabla_inicio, (
        f"la tabla empieza en {fila} y el Panel espera {tabla_inicio}")

    for mes in range(1, 37):
        f = fila
        anterior = f - 1
        activas = (f"=B{f}" if mes == 1 else
                   f"=C{anterior}*(1-Panel!{churn})+B{f}")
        _fila(ws, f, [
            mes,
            f"=Panel!{altas}",
            activas,
            f"=C{f}*{arpu}",
            f"=C{f}*{contribucion}",
            # Estructura D: una mensualidad al alta y 10 % de las cuentas
            # captadas en los ultimos doce meses.
            f"=-(B{f}*{arpu}+0.1*{arpu}*MIN(C{f},SUM(B{max(fila, f - 11)}:B{f})))",
            f"=B{f}*Panel!{cuota}*Panel!{porcentaje}",
            f"=E{f}+F{f}+G{f}-Panel!{opex}",
            (f"=Panel!{caja_inicial}+H{f}" if mes == 1
             else f"=I{anterior}+H{f}"),
        ], [NUM, NUM, DEC, EUR0, EUR0, EUR0, EUR0, EUR0, EUR0])
        fila += 1

    ws.conditional_formatting.add(
        f"H{tabla_inicio}:I{tabla_fin}",
        CellIsRule(operator="lessThan", formula=["0"],
                   font=Font(name=FUENTE, size=10, color=STOP)))
    ws.conditional_formatting.add(
        f"H{tabla_inicio}:I{tabla_fin}",
        CellIsRule(operator="greaterThanOrEqual", formula=["0"],
                   font=Font(name=FUENTE, size=10, color=OKC)))

    fila += 1
    _nota(ws, fila,
          "La curva supone que las altas del Panel se mantienen constantes y "
          "que las bajas se aplican a la cartera existente antes de sumar las "
          "nuevas. No incluye IVA, impuestos ni inversiones: mide si el negocio "
          "se paga a si mismo.")


# ------------------------------------------------------------ FUENTES ----
def fuentes(wb) -> None:
    ws = _hoja(wb, "Fuentes_y_pendientes")
    _anchos(ws, {"A": 38, "B": 16, "C": 22, "D": 66})

    fila = _titulo(
        ws, "De donde sale cada numero y que falta por medir",
        "Un modelo economico sin trazabilidad es una opinion con decimales. "
        "Aqui esta el origen de cada cifra y, sobre todo, lo que todavia no es "
        "un dato.",
    )

    _cabecera(ws, fila, ["Cifra", "Valor", "Estado", "Origen"])
    fila += 1
    origenes = [
        ("Precios 29 / 49 / 99 EUR", "Adoptado", "Decidido",
         "Decisiones: «Precio adoptado, prueba completa y despues modo "
         "consulta» (15/07/2026). Coincide con el catalogo del codigo."),
        ("Coste de software por plan", "1,48 / 3,04 / 18,47", "Calculado",
         "Unit-economics-y-cerebro-interno.md (15/07/2026): Stripe, WhatsApp, "
         "IA, transcripcion, extraccion, almacenamiento y voz."),
        ("Contribucion por plan", "20,83 / 34,89 / 56,96", "Calculado",
         "Mismo analisis. Ya descuenta soporte, onboarding y fijo por cuenta."),
        ("Mezcla 55 / 35 / 10", "Supuesto", "SIN MEDIR",
         "Reparto de planes asumido. Cambiara con el piloto."),
        ("Bajas mensuales", "4 %", "SIN MEDIR",
         "No hay clientes de pago. Cualquier LTV calculado sobre esto es una "
         "hipotesis, no una promesa."),
        ("CAC 150 EUR", "Supuesto", "SIN MEDIR",
         "Figuraba en el modelo editable anterior; no hay campanas medidas."),
        ("Opex 3.500 EUR", "Constante", "Supuesto",
         "Analisis del 15/07/2026. Asume que vende el founder."),
        ("Estructuras de comision", "A a E", "Propuesta",
         "Canal-comercial-y-comisiones.md (16/09/2026). Nada aprobado: el "
         "founder reserva descuento, porcentaje, duracion y devoluciones."),
        ("Cuota de implantacion 99 EUR", "Propuesta", "Sin aprobar",
         "Misma fuente. Perdonada en contratacion anual."),
        ("Coste cargado de comercial", "2.400 EUR", "Supuesto",
         "Sueldo mas seguridad social y estructura."),
    ]
    for cifra, valor, estado, origen in origenes:
        _fila(ws, fila, [cifra, valor, estado, origen], [None, None, None, None])
        ws.cell(row=fila, column=4).alignment = Alignment(wrap_text=True,
                                                          vertical="top")
        if estado == "SIN MEDIR":
            for columna in range(1, 5):
                ws.cell(row=fila, column=columna).font = Font(
                    name=FUENTE, size=10, color=STOP)
        ws.row_dimensions[fila].height = 30
        fila += 1

    fila += 1
    _nota(ws, fila,
          "Antes de firmar con nadie: tres a cinco clientes de pago y treinta "
          "dias midiendo bajas, soporte por cuenta y coste real de captacion. "
          "Con eso, este libro deja de ser un escenario y pasa a ser un modelo.")


def main() -> int:
    wb = Workbook()
    ref = panel(wb)
    unit_economics(wb, ref)
    vida_y_ltv(wb, ref)
    canal(wb, ref)
    implantacion(wb, ref)
    caja(wb, ref)
    fuentes(wb)
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    wb.save(DESTINO)
    print(f"Escrito: {DESTINO}")
    print("Hojas:", ", ".join(hoja.title for hoja in wb.worksheets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
