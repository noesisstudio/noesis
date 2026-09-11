"""Genera el modelo economico de Bynoesis en xlsx.

Todas las cifras proceden de docs/06-negocio-y-finanzas/Unit-economics-y-cerebro-interno.md y de
analysis/build_unit_economics.mjs (fechadas 15/07/2026). Lo que no consta en el
repositorio se deja como celda PENDIENTE: no se inventa ningun dato.
"""
import os
import sys

try:
    from openpyxl import Workbook
except ModuleNotFoundError:
    raise SystemExit(
        'Falta openpyxl. Instalalo con: pip install -e ".[analysis]"'
    )
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from openpyxl.worksheet.datavalidation import DataValidation

# --- Paleta de marca (docs/design/STYLE_TOKENS.json) -----------------------
FOREST = "FF14463B"
TEAL = "FF2E8B74"
CREAM = "FFF4F1EA"
SAND = "FFE7E0D1"
INK = "FF15211C"
MUTED = "FF5D6B66"
WHITE = "FFFFFFFF"
INPUT = "FF0000CC"      # azul = celda editable, convencion de modelos financieros
CALC = "FF15211C"       # negro = formula
WARN = "FFB7831F"
STOP = "FFC0533F"
OKC = "FF1F8A6D"

HAIR = Side(style="thin", color="FFDDD8CC")
BOX = Border(left=HAIR, right=HAIR, top=HAIR, bottom=HAIR)

EUR = '#,##0.00\\ "\u20ac"'
EUR0 = '#,##0\\ "\u20ac"'
PCT = '0.0%'
PCT0 = '0%'
NUM = '#,##0.00'

wb = Workbook()


def sheet(name):
    ws = wb.create_sheet(name)
    ws.sheet_properties.tabColor = FOREST
    return ws


def title(ws, text, sub=None, span=8):
    ws["A1"] = text
    ws["A1"].font = Font(name="Aptos Display", size=17, bold=True, color=FOREST)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    ws.row_dimensions[1].height = 26
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(name="Aptos", size=9.5, italic=True, color=MUTED)
        ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
        ws.row_dimensions[2].height = 30


def section(ws, row, text, span=8):
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(name="Aptos", size=10, bold=True, color=WHITE)
    c.fill = PatternFill("solid", fgColor=TEAL)
    for i in range(2, span + 1):
        ws.cell(row=row, column=i).fill = PatternFill("solid", fgColor=TEAL)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)


def header(ws, row, values, start=1):
    for i, v in enumerate(values):
        c = ws.cell(row=row, column=start + i, value=v)
        c.font = Font(name="Aptos", size=9.5, bold=True, color=FOREST)
        c.fill = PatternFill("solid", fgColor=SAND)
        c.border = BOX
        c.alignment = Alignment(wrap_text=True, vertical="center")


def widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


def body(ws, rng, size=10):
    for row in ws[rng]:
        for c in row:
            if c.font is None or not c.font.bold:
                c.font = Font(name="Aptos", size=size, color=INK)


# ==========================================================================
# 1. RESUMEN
# ==========================================================================
ws = wb.active
ws.title = "Resumen"
ws.sheet_properties.tabColor = FOREST
title(ws, "Bynoesis \u2014 Modelo economico",
      "Modelo vivo: las celdas azules son entradas editables y el resto son formulas. "
      "Las cifras proceden del analisis interno fechado el 15/07/2026 con fuentes citadas en la hoja Fuentes. "
      "Lo que el repositorio no acredita esta en la hoja Datos_Pendientes y NO se ha estimado.")
widths(ws, {"A": 38, "B": 16, "C": 16, "D": 16, "E": 15, "F": 40})

section(ws, 4, "Catalogo adoptado", 6)
header(ws, 5, ["Concepto", "Autonomo", "Negocio", "Premium", "Unidad", "Nota"])
rows = [
    ("Precio mensual", "='Supuestos'!B7", "='Supuestos'!C7", "='Supuestos'!D7", "\u20ac/mes + IVA", "Catalogo adoptado tras el analisis"),
    ("Precio anual", 319, 539, 1089, "\u20ac/ano + IVA", "Cobra 11 meses, da acceso 12"),
    ("Mix de clientes supuesto", "='Supuestos'!B8", "='Supuestos'!C8", "='Supuestos'!D8", "%", "Hipotesis de escala, a recalibrar"),
]
for i, (lab, a, b, c, u, n) in enumerate(rows):
    r = 6 + i
    ws.cell(row=r, column=1, value=lab)
    for j, v in enumerate((a, b, c)):
        cell = ws.cell(row=r, column=2 + j, value=v)
        cell.number_format = PCT if i == 2 else EUR
        cell.font = Font(name="Aptos", size=10, color=CALC if isinstance(v, str) else INPUT)
    ws.cell(row=r, column=5, value=u)
    ws.cell(row=r, column=6, value=n)

section(ws, 10, "Resultado por plan (modelo Bynoesis)", 6)
header(ws, 11, ["Metrica", "Autonomo", "Negocio", "Premium", "Unidad", "Nota"])
res = [
    ("COGS software", "='Unit_Economics'!E13", "='Unit_Economics'!F13", "='Unit_Economics'!G13", "\u20ac/mes", "Stripe, WhatsApp, IA, voz, almacenamiento"),
    ("Margen bruto", "='Unit_Economics'!E14", "='Unit_Economics'!F14", "='Unit_Economics'!G14", "%", "Sobre precio neto"),
    ("Contribucion", "='Unit_Economics'!E18", "='Unit_Economics'!F18", "='Unit_Economics'!G18", "\u20ac/mes", "Ya descuenta soporte, onboarding y fijo"),
    ("Margen de contribucion", "='Unit_Economics'!E19", "='Unit_Economics'!F19", "='Unit_Economics'!G19", "%", "Sin CAC"),
]
for i, (lab, a, b, c, u, n) in enumerate(res):
    r = 12 + i
    ws.cell(row=r, column=1, value=lab)
    for j, v in enumerate((a, b, c)):
        cell = ws.cell(row=r, column=2 + j, value=v)
        cell.number_format = PCT if "%" in u else EUR
    ws.cell(row=r, column=5, value=u)
    ws.cell(row=r, column=6, value=n)

section(ws, 17, "Punto de equilibrio", 6)
header(ws, 18, ["Metrica", "Valor", "", "", "Unidad", "Nota"])
be = [
    ("Contribucion media ponderada", "=Unit_Economics!E18*Supuestos!B8+Unit_Economics!F18*Supuestos!C8+Unit_Economics!G18*Supuestos!D8", EUR, "\u20ac/cuenta/mes", "Segun el mix de la hoja Supuestos"),
    ("Opex fijo mensual", "=Supuestos!B41", EUR, "\u20ac/mes", "HIPOTESIS: 3.500 \u20ac. Sustituir por el gasto real"),
    ("Cuentas para equilibrio", "=IF(B19>0,ROUNDUP(B20/B19,0),\"\")", '#,##0', "cuentas", "Con el opex real este numero cambia"),
    ("Ingreso mensual en equilibrio", "=IF(B21<>\"\",B21*(Supuestos!B7*Supuestos!B8+Supuestos!C7*Supuestos!C8+Supuestos!D7*Supuestos!D8),\"\")", EUR0, "\u20ac/mes", "Sin IVA"),
]
for i, (lab, f, fmt, u, n) in enumerate(be):
    r = 19 + i
    ws.cell(row=r, column=1, value=lab)
    c = ws.cell(row=r, column=2, value=f)
    c.number_format = fmt
    c.font = Font(name="Aptos", size=10, bold=True, color=FOREST)
    ws.cell(row=r, column=5, value=u)
    ws.cell(row=r, column=6, value=n)

ws["A24"] = "Aviso"
ws["A24"].font = Font(name="Aptos", size=10, bold=True, color=STOP)
ws["A25"] = ("Ninguna cifra de este libro es un resultado observado. Son supuestos de planificacion "
             "fechados que el piloto debe recalibrar. El opex fijo, los sueldos, el reparto societario y "
             "el CAC no constan en el repositorio: estan en Datos_Pendientes sin rellenar.")
ws["A25"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A25"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A25:F27")
body(ws, "A4:F27")

# ==========================================================================
# 1b. CALCULADORA POR NUMERO DE CLIENTES
# ==========================================================================
ws = sheet("Calculadora")
ws.sheet_properties.tabColor = TEAL
title(ws, "Calculadora: escribe cuantos clientes tienes",
      "Cambia solo las tres celdas naranjas de abajo y todo el libro responde: ingresos, cada linea de coste, "
      "resultado mensual y cuanto falta para el equilibrio. Es la hoja para jugar; el resto explica de donde "
      "sale cada cifra.", 6)
widths(ws, {"A": 34, "B": 16, "C": 16, "D": 16, "E": 16, "F": 34})

UE = "Unit_Economics"

# --- 1. Clientes ---
section(ws, 4, "1 · Cuantos clientes de cada plan", 6)
header(ws, 5, ["Plan", "Clientes", "Precio", "Ingreso mensual", "Ingreso anual", "Nota"])
for i, (name, ucol, scol) in enumerate([("Autonomo", "E", "B"), ("Negocio", "F", "C"), ("Premium", "G", "D")]):
    r = 6 + i
    ws.cell(row=r, column=1, value=name).font = Font(name="Aptos", size=10, bold=True, color=INK)
    ci = ws.cell(row=r, column=2, value=0)
    ci.number_format = '#,##0'
    ci.font = Font(name="Aptos", size=13, bold=True, color=INPUT)
    ci.fill = PatternFill("solid", fgColor="FFFDF3E7")
    ci.border = BOX
    ci.alignment = Alignment(horizontal="center")
    c2 = ws.cell(row=r, column=3, value=f"=Supuestos!{scol}7")
    c3 = ws.cell(row=r, column=4, value=f"=B{r}*C{r}")
    c4 = ws.cell(row=r, column=5, value=f"=D{r}*12")
    for c in (c2, c3, c4):
        c.number_format = EUR0
        c.border = BOX
ws.row_dimensions[6].height = 22
ws.row_dimensions[7].height = 22
ws.row_dimensions[8].height = 22
ws.cell(row=9, column=1, value="TOTAL").font = Font(name="Aptos", size=10, bold=True, color=FOREST)
for col, letter in ((2, "B"), (4, "D"), (5, "E")):
    c = ws.cell(row=9, column=col, value=f"=SUM({letter}6:{letter}8)")
    c.number_format = '#,##0' if col == 2 else EUR0
    c.font = Font(name="Aptos", size=11, bold=True, color=FOREST)
    c.fill = PatternFill("solid", fgColor=CREAM)
    c.border = BOX
ws.cell(row=9, column=6, value="Ingreso sin IVA").font = Font(name="Aptos", size=9.5, color=MUTED)

# --- 2. COGS ---
section(ws, 11, "2 · Costes variables: lo que cuesta servirlos", 6)
header(ws, 12, ["Concepto", "Autonomo", "Negocio", "Premium", "Total", "€ por cliente"])
cogs_rows = [
    ("Comisiones de Stripe", 6), ("WhatsApp (plantillas)", 7), ("IA avanzada", 8),
    ("Transcripcion de voz", 9), ("Extraccion de documentos", 10),
    ("Almacenamiento", 11), ("Voz telefonica (Premium)", 12),
]
for i, (lab, ue_row) in enumerate(cogs_rows):
    r = 13 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    for j, (ucol, bcol) in enumerate([("E", "B"), ("F", "B"), ("G", "B")]):
        c = ws.cell(row=r, column=2 + j, value=f"=$B${6 + j}*'{UE}'!{ucol}{ue_row}")
        c.number_format = EUR
        c.border = BOX
    ct = ws.cell(row=r, column=5, value=f"=SUM(B{r}:D{r})")
    ct.number_format = EUR
    ct.border = BOX
    cu = ws.cell(row=r, column=6, value=f"=IFERROR(E{r}/$B$9,\"\")")
    cu.number_format = EUR
    cu.border = BOX
r = 20
ws.cell(row=r, column=1, value="TOTAL COSTES VARIABLES").font = Font(name="Aptos", size=10, bold=True, color=FOREST)
for j in range(4):
    col = get_column_letter(2 + j)
    c = ws.cell(row=r, column=2 + j, value=f"=SUM({col}13:{col}19)")
    c.number_format = EUR
    c.font = Font(name="Aptos", size=10, bold=True, color=FOREST)
    c.fill = PatternFill("solid", fgColor=CREAM)
    c.border = BOX
c = ws.cell(row=r, column=6, value="=IFERROR(E20/$B$9,\"\")")
c.number_format = EUR
c.font = Font(name="Aptos", size=10, bold=True, color=FOREST)
c.fill = PatternFill("solid", fgColor=CREAM)
c.border = BOX

# --- 3. Servicio ---
section(ws, 22, "3 · Coste de atender a esos clientes", 6)
header(ws, 23, ["Concepto", "Autonomo", "Negocio", "Premium", "Total", "€ por cliente"])
for i, (lab, ue_row) in enumerate([("Soporte humano", 15), ("Onboarding amortizado", 16)]):
    r = 24 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    for j, ucol in enumerate(["E", "F", "G"]):
        c = ws.cell(row=r, column=2 + j, value=f"=$B${6 + j}*'{UE}'!{ucol}{ue_row}")
        c.number_format = EUR
        c.border = BOX
    ct = ws.cell(row=r, column=5, value=f"=SUM(B{r}:D{r})")
    ct.number_format = EUR
    ct.border = BOX
    cu = ws.cell(row=r, column=6, value=f"=IFERROR(E{r}/$B$9,\"\")")
    cu.number_format = EUR
    cu.border = BOX
r = 26
ws.cell(row=r, column=1, value="TOTAL SERVICIO").font = Font(name="Aptos", size=10, bold=True, color=FOREST)
for j in range(4):
    col = get_column_letter(2 + j)
    c = ws.cell(row=r, column=2 + j, value=f"=SUM({col}24:{col}25)")
    c.number_format = EUR
    c.font = Font(name="Aptos", size=10, bold=True, color=FOREST)
    c.fill = PatternFill("solid", fgColor=CREAM)
    c.border = BOX

# --- 4. Fijos ---
section(ws, 28, "4 · Costes fijos: no dependen de cuantos clientes tengas", 6)
header(ws, 29, ["Concepto", "Importe mensual", "", "", "Anual", "Nota"])
fixed_rows = [
    ("Plataforma (app, correo, copias)", "=Supuestos!B40", "Escala poco con el numero de cuentas"),
    ("Opex fijo (founder, legal, herramientas)", "=Supuestos!B41", "SUPUESTO de 3.500 €. Sustituir por el real de Datos_Pendientes"),
    ("Publicidad", "=IFERROR(Ads_Captacion!B6,0)", "Lo que escribas en la hoja Ads_Captacion"),
]
for i, (lab, f, nota) in enumerate(fixed_rows):
    r = 30 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    c = ws.cell(row=r, column=2, value=f)
    c.number_format = EUR0
    c.border = BOX
    ca = ws.cell(row=r, column=5, value=f"=B{r}*12")
    ca.number_format = EUR0
    ca.border = BOX
    ws.cell(row=r, column=6, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6).alignment = Alignment(wrap_text=True, vertical="top")
r = 33
ws.cell(row=r, column=1, value="TOTAL FIJOS").font = Font(name="Aptos", size=10, bold=True, color=FOREST)
for col, letter in ((2, "B"), (5, "E")):
    c = ws.cell(row=r, column=col, value=f"=SUM({letter}30:{letter}32)")
    c.number_format = EUR0
    c.font = Font(name="Aptos", size=10, bold=True, color=FOREST)
    c.fill = PatternFill("solid", fgColor=CREAM)
    c.border = BOX

# --- 5. Resultado ---
section(ws, 35, "5 · Resultado", 6)
header(ws, 36, ["Metrica", "Mensual", "", "", "Anual", "Nota"])
result_rows = [
    ("Ingreso", "=D9", "Sin IVA"),
    ("(-) Costes variables", "=-E20", "Escalan con cada cliente nuevo"),
    ("MARGEN BRUTO", "=B37+B38", "Lo que queda para pagar estructura"),
    ("(-) Coste de servicio", "=-E26", "Soporte y onboarding"),
    ("(-) Costes fijos", "=-B33", "Plataforma, opex y publicidad"),
    ("RESULTADO DEL MES", "=B39+B40+B41", "Lo que gana o pierde la empresa cada mes"),
]
for i, (lab, f, nota) in enumerate(result_rows):
    r = 37 + i
    # Ojo: una etiqueta que empiece por "=" la interpreta Excel como formula
    # y muestra #NAME?. Los totales se marcan por nombre, no por prefijo.
    is_total = lab in ("MARGEN BRUTO", "RESULTADO DEL MES")
    ws.cell(row=r, column=1, value=lab).font = Font(
        name="Aptos", size=10, bold=is_total, color=FOREST if is_total else INK)
    c = ws.cell(row=r, column=2, value=f)
    c.number_format = EUR0
    c.border = BOX
    c.font = Font(name="Aptos", size=13 if lab == "RESULTADO DEL MES" else 10,
                  bold=is_total, color=FOREST if is_total else CALC)
    if is_total:
        c.fill = PatternFill("solid", fgColor=CREAM)
    ca = ws.cell(row=r, column=5, value=f"=B{r}*12")
    ca.number_format = EUR0
    ca.border = BOX
    ca.font = Font(name="Aptos", size=10, bold=is_total, color=FOREST if is_total else CALC)
    ws.cell(row=r, column=6, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)
ws.row_dimensions[42].height = 24
ws.conditional_formatting.add(
    "B42:E42", CellIsRule(operator="lessThan", formula=["0"], font=Font(color=STOP, bold=True, size=13)))
ws.conditional_formatting.add(
    "B42:E42", CellIsRule(operator="greaterThanOrEqual", formula=["0"], font=Font(color=OKC, bold=True, size=13)))

c = ws.cell(row=43, column=1, value="Margen sobre ingreso")
c.font = Font(name="Aptos", size=10, color=INK)
c = ws.cell(row=43, column=2, value="=IFERROR(B42/B37,\"\")")
c.number_format = PCT
c.font = Font(name="Aptos", size=10, bold=True, color=FOREST)
c.border = BOX

# --- 6. Distancia al equilibrio ---
section(ws, 45, "6 · Cuanto falta para el equilibrio", 6)
header(ws, 46, ["Metrica", "Valor", "", "", "Unidad", "Nota"])
be_rows = [
    ("Contribucion media por cliente",
     "=IFERROR((B6*('Unit_Economics'!E5-'Unit_Economics'!E13-'Unit_Economics'!E15-'Unit_Economics'!E16)"
     "+B7*('Unit_Economics'!F5-'Unit_Economics'!F13-'Unit_Economics'!F15-'Unit_Economics'!F16)"
     "+B8*('Unit_Economics'!G5-'Unit_Economics'!G13-'Unit_Economics'!G15-'Unit_Economics'!G16))/B9,\"\")",
     EUR, "€/mes", "Con la mezcla exacta de clientes que has escrito"),
    ("Clientes actuales", "=B9", '#,##0', "clientes", "La suma de las tres celdas naranjas"),
    ("Clientes para equilibrio", "=IFERROR(ROUNDUP($B$33/$B$47,0),\"\")", '#,##0', "clientes",
     "Manteniendo esa misma mezcla de planes"),
    ("Faltan", "=IFERROR(MAX(0,B49-B48),\"\")", '#,##0', "clientes", "Cero significa que ya estas por encima"),
    ("Sobran", "=IFERROR(MAX(0,B48-B49),\"\")", '#,##0', "clientes", "Clientes por encima del equilibrio"),
    ("Veredicto",
     '=IF(B48=0,"Escribe cuantos clientes tienes arriba",'
     'IF(B42>=0,"Por encima del equilibrio: la empresa gana dinero",'
     '"Por debajo del equilibrio: cada mes se consume caja"))',
     None, "", "Se recalcula solo"),
]
for i, (lab, f, fmt, u, nota) in enumerate(be_rows):
    r = 47 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    c = ws.cell(row=r, column=2, value=f)
    if fmt:
        c.number_format = fmt
    strong = lab in ("Clientes para equilibrio", "Faltan", "Veredicto")
    c.font = Font(name="Aptos", size=12 if strong else 10, bold=strong,
                  color=FOREST if strong else CALC)
    if strong:
        c.fill = PatternFill("solid", fgColor=CREAM)
    c.border = BOX
    ws.cell(row=r, column=5, value=u).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6).alignment = Alignment(wrap_text=True, vertical="top")

ws["A54"] = ("Prueba a escribir 66, 42 y 12: es el reparto del equilibrio con el mix previsto. Despues cambia una "
             "sola cifra y mira que pasa con el resultado. Diez clientes Premium mas mueven mucho mas la aguja "
             "que diez Autonomos, y esa es toda la conversacion comercial resumida en una celda.")
ws["A54"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A54"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A54:F56")
ws.freeze_panes = "A5"

# ==========================================================================
# 2. SUPUESTOS
# ==========================================================================
ws = sheet("Supuestos")
title(ws, "Supuestos", "Celdas azules = entradas editables. Cambiar aqui recalcula todo el libro. "
                       "Cada driver lleva fecha y fuente; los marcados como Supuesto no estan verificados.", 6)
widths(ws, {"A": 34, "B": 15, "C": 15, "D": 15, "E": 18, "F": 42})

section(ws, 4, "Supuestos por plan", 6)
header(ws, 5, ["Driver", "Autonomo", "Negocio", "Premium", "Unidad", "Fuente / criterio"])
plan_inputs = [
    ("Precio actual", 29, 39, 79, "\u20ac/mes + IVA", "Catalogo anterior", EUR),
    ("Precio adoptado", 29, 49, 99, "\u20ac/mes + IVA", "Recomendacion de unit economics", EUR),
    ("Mix de clientes", 0.55, 0.35, 0.10, "%", "Supuesto de escala", PCT),
    ("Creditos avanzados incluidos", 75, 300, 1500, "acciones/mes", "Catalogo actual", '#,##0'),
    ("Uso esperado del limite", 0.35, 0.40, 0.25, "%", "Supuesto conservador", PCT),
    ("Resolucion por cerebro interno", 0.60, 0.60, 0.60, "%", "Objetivo tras piloto", PCT),
    ("WhatsApp utility enviados", 30, 80, 200, "mensajes/mes", "Supuesto operativo", '#,##0'),
    ("WhatsApp service recibidos", 100, 300, 1000, "mensajes/mes", "Gratis hoy; sensibilidad futura", '#,##0'),
    ("Audio transcrito", 15, 60, 200, "min/mes", "Supuesto operativo", '#,##0'),
    ("Documentos procesados", 15, 50, 200, "docs/mes", "Supuesto operativo", '#,##0'),
    ("Documentos que escalan fuera", 0.20, 0.20, 0.20, "%", "OCR local primero", PCT),
    ("Almacenamiento", 0.25, 1, 3, "GB/cuenta", "Supuesto operativo", NUM),
    ("Voz telefonica incluida", 0, 0, 100, "min/mes", "Promesa Premium actual", '#,##0'),
    ("Soporte humano", 12, 20, 45, "min/cuenta/mes", "Supuesto de servicio", '#,##0'),
    ("Onboarding inicial", 30, 60, 120, "min/cuenta", "Amortizado en 12 meses", '#,##0'),
]
for i, (lab, a, b, c, u, src, fmt) in enumerate(plan_inputs):
    r = 6 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    for j, v in enumerate((a, b, c)):
        cell = ws.cell(row=r, column=2 + j, value=v)
        cell.number_format = fmt
        cell.font = Font(name="Aptos", size=10, color=INPUT)
        cell.border = BOX
    ws.cell(row=r, column=5, value=u).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6, value=src).font = Font(name="Aptos", size=9.5, color=MUTED)

section(ws, 23, "Supuestos globales", 6)
header(ws, 24, ["Driver", "Valor", "Unidad", "Fecha", "Fuente", "Nota"])
global_inputs = [
    ("EUR por USD", 1 / 1.1405, "EUR/USD", "14/07/2026", "ECB", "1 EUR = 1,1405 USD", '0.0000'),
    ("Stripe Payments", 0.015, "% ingreso", "15/07/2026", "Stripe", "Tarjeta EEE estandar", '0.00%'),
    ("Stripe Billing", 0.007, "% ingreso", "15/07/2026", "Stripe", "Pago por uso", '0.00%'),
    ("Stripe fijo", 0.25, "\u20ac/transaccion", "15/07/2026", "Stripe", "Una renovacion mensual", EUR),
    ("WhatsApp utility Espana", 0.0166, "\u20ac/mensaje", "15/07/2026", "Meta / rate card", "Mensaje entregado", '0.0000'),
    ("WhatsApp service futuro", 0.0166, "\u20ac/mensaje", "15/07/2026", "Sensibilidad", "Actualmente 0 \u20ac", '0.0000'),
    ("Haiku 4.5 por interaccion", 0.014, "USD/interaccion", "15/07/2026", "Anthropic", "8k input + 1,2k output", '0.0000'),
    ("Qwen3 32B por interaccion", 0.003028, "USD/interaccion", "15/07/2026", "Groq", "Mismo supuesto de tokens", '0.000000'),
    ("Peso Qwen en fallback", 0.80, "%", "15/07/2026", "Arquitectura hibrida", "Resto Haiku", PCT0),
    ("Whisper Turbo", 0.04, "USD/hora", "15/07/2026", "Groq", "Solo transcripcion", '0.000'),
    ("Extraccion externa documento", 0.012, "\u20ac/documento", "15/07/2026", "Supuesto", "Validar con corpus real", '0.000'),
    ("Object storage", 0.015, "USD/GB-mes", "15/07/2026", "Railway", "Sin egress", '0.000'),
    ("Voz agente", 0.11, "USD/min", "15/07/2026", "Retell", "Ejemplo de calculadora", '0.00'),
    ("Numero telefonico voz", 2, "USD/mes", "15/07/2026", "Retell", "Solo plan Premium", '0.00'),
    ("Coste hora soporte", 25, "\u20ac/hora", "15/07/2026", "Supuesto", "Coste empresa cargado", EUR),
    ("Plataforma fija", 65, "\u20ac/mes", "15/07/2026", "Supuesto", "App, email y backups minimos", EUR),
    ("Opex fijo para break-even", 3500, "\u20ac/mes", "15/07/2026", "SUPUESTO", "Founder, legal, herramientas, reserva. Sustituir por el real", EUR0),
    ("CAC inicial", 150, "\u20ac/cliente", "15/07/2026", "SUPUESTO", "Validar durante piloto", EUR0),
    ("IVA Espana", 0.21, "%", "15/07/2026", "AEAT", "El precio se comunica + IVA", PCT0),
    ("Cuentas para repartir fijo", 100, "cuentas", "15/07/2026", "Escenario base", "Solo unit economics por plan", '#,##0'),
]
for i, (lab, val, u, fecha, src, nota, fmt) in enumerate(global_inputs):
    r = 25 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    c = ws.cell(row=r, column=2, value=val)
    c.number_format = fmt
    c.font = Font(name="Aptos", size=10, color=INPUT)
    c.border = BOX
    ws.cell(row=r, column=3, value=u).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=4, value=fecha).font = Font(name="Aptos", size=9.5, color=MUTED)
    col5 = ws.cell(row=r, column=5, value=src)
    col5.font = Font(name="Aptos", size=9.5, bold=(src == "SUPUESTO"),
                     color=WARN if src == "SUPUESTO" else MUTED)
    ws.cell(row=r, column=6, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)
ws.freeze_panes = "A6"

# ==========================================================================
# 3. UNIT ECONOMICS
# ==========================================================================
ws = sheet("Unit_Economics")
title(ws, "Unit economics por plan",
      "Escenario base hibrido: cerebro interno resuelve el 60%; del resto, 80% Qwen y 20% Haiku. "
      "Columnas B-D = catalogo anterior (29/39/79). Columnas E-G = catalogo adoptado (29/49/99).")
widths(ws, {"A": 34, "B": 14, "C": 14, "D": 14, "E": 14, "F": 14, "G": 14, "H": 12})
header(ws, 4, ["Metrica", "Autonomo ant.", "Negocio ant.", "Premium ant.",
               "Autonomo adop.", "Negocio adop.", "Premium adop.", "Unidad"])

metrics = [
    ("Precio neto", EUR), ("Stripe", EUR), ("WhatsApp utility", EUR), ("IA avanzada", EUR),
    ("Transcripcion", EUR), ("Extraccion externa", EUR), ("Almacenamiento", EUR),
    ("Voz Premium", EUR), ("COGS software", EUR), ("Margen bruto software", PCT),
    ("Soporte humano", EUR), ("Onboarding amortizado", EUR), ("Fijo asignado", EUR),
    ("Contribucion", EUR), ("Margen de contribucion", PCT),
    ("Ingreso si el precio incluyera IVA", EUR), ("Contribucion si incluyera IVA", EUR),
    ("IA: 100% de creditos con Haiku", EUR), ("Margen bruto en peor caso IA", PCT),
]
units = ["\u20ac/mes"] * 9 + ["%"] + ["\u20ac/mes"] * 4 + ["%"] + ["\u20ac/mes"] * 3 + ["%"]
for i, (lab, fmt) in enumerate(metrics):
    r = 5 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    ws.cell(row=r, column=8, value=units[i]).font = Font(name="Aptos", size=9.5, color=MUTED)

S = "Supuestos"
cols = ["B", "C", "D", "E", "F", "G"]
for j, col in enumerate(cols):
    plan = j % 3
    ac = ["B", "C", "D"][plan]
    price_row = 6 if j < 3 else 7
    F = {
        5: f"='{S}'!{ac}${price_row}",
        6: f"={col}5*('{S}'!$B$26+'{S}'!$B$27)+'{S}'!$B$28",
        7: f"='{S}'!{ac}$12*'{S}'!$B$29",
        8: f"='{S}'!{ac}$9*'{S}'!{ac}$10*(1-'{S}'!{ac}$11)*('{S}'!$B$33*'{S}'!$B$32+(1-'{S}'!$B$33)*'{S}'!$B$31)*'{S}'!$B$25",
        9: f"='{S}'!{ac}$14/60*'{S}'!$B$34*'{S}'!$B$25",
        10: f"='{S}'!{ac}$15*'{S}'!{ac}$16*'{S}'!$B$35",
        11: f"='{S}'!{ac}$17*'{S}'!$B$36*'{S}'!$B$25",
        12: f"=IF('{S}'!{ac}$18>0,'{S}'!{ac}$18*'{S}'!$B$37*'{S}'!$B$25+'{S}'!$B$38*'{S}'!$B$25,0)",
        13: f"=SUM({col}6:{col}12)",
        14: f"=({col}5-{col}13)/{col}5",
        15: f"='{S}'!{ac}$19/60*'{S}'!$B$39",
        16: f"='{S}'!{ac}$20/60*'{S}'!$B$39/12",
        17: f"='{S}'!$B$40/'{S}'!$B$44",
        18: f"={col}5-{col}13-{col}15-{col}16-{col}17",
        19: f"={col}18/{col}5",
        20: f"={col}5/(1+'{S}'!$B$43)",
        21: f"={col}20-{col}13-{col}15-{col}16-{col}17",
        22: f"='{S}'!{ac}$9*'{S}'!$B$31*'{S}'!$B$25",
        23: f"=({col}5-({col}13-{col}8+{col}22))/{col}5",
    }
    for r, f in F.items():
        c = ws.cell(row=r, column=2 + j, value=f)
        c.number_format = metrics[r - 5][1]
        bold = r in (13, 14, 18, 19)
        c.font = Font(name="Aptos", size=10, bold=bold, color=FOREST if bold else CALC)
        c.border = BOX
        if r in (13, 18):
            c.fill = PatternFill("solid", fgColor=CREAM)
ws.freeze_panes = "B5"

# ==========================================================================
# 4. HIPOTESIS EXTERNA
# ==========================================================================
ws = sheet("Hipotesis_Externa")
title(ws, "Hipotesis de coste del documento externo",
      "Reproduccion literal de la tabla recibida. Su propio encabezado la titula 'Calculo (Hipotesis)': "
      "no lleva fuente ni fecha, y aplica el mismo coste a todos los planes independientemente del uso.", 6)
widths(ws, {"A": 32, "B": 34, "C": 16, "D": 16, "E": 14, "F": 40})

section(ws, 4, "Tabla recibida", 6)
header(ws, 5, ["Concepto de gasto", "Calculo (hipotesis)", "Coste mensual/usuario", "", "", "Contraste con el modelo Bynoesis"])
ext = [
    ("API de Meta (WhatsApp)", "150 mensajes enviados x 0,0166 \u20ac", "=150*Supuestos!B29", "El modelo Bynoesis usa 30/80/200 mensajes segun plan, no 150 fijos"),
    ("Inteligencia Artificial (LLM)", "150 procesamientos x ~0,02 \u20ac", 3.00, "El modelo Bynoesis estima 0,05/0,22/0,69 \u20ac: el cerebro interno resuelve el 60%"),
    ("Servidor y base de datos", "Prorrateo basico por usuario", 1.00, "El modelo Bynoesis reparte 65 \u20ac de plataforma entre las cuentas activas"),
]
for i, (a, b, c, nota) in enumerate(ext):
    r = 6 + i
    ws.cell(row=r, column=1, value=a).font = Font(name="Aptos", size=10, bold=True, color=INK)
    ws.cell(row=r, column=2, value=b).font = Font(name="Aptos", size=10, color=MUTED)
    cell = ws.cell(row=r, column=3, value=c)
    cell.number_format = EUR
    cell.font = Font(name="Aptos", size=10, color=INPUT if not isinstance(c, str) else CALC)
    cell.border = BOX
    ws.cell(row=r, column=6, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6).alignment = Alignment(wrap_text=True, vertical="top")

ws.cell(row=9, column=1, value="COSTE TOTAL VARIABLE").font = Font(name="Aptos", size=10, bold=True, color=FOREST)
ws.cell(row=9, column=2, value="Mensual por usuario").font = Font(name="Aptos", size=10, bold=True, color=FOREST)
t = ws.cell(row=9, column=3, value="=SUM(C6:C8)")
t.number_format = EUR
t.font = Font(name="Aptos", size=11, bold=True, color=FOREST)
t.fill = PatternFill("solid", fgColor=CREAM)
t.border = BOX

section(ws, 11, "Margen resultante con esta hipotesis", 6)
header(ws, 12, ["Plan", "Precio adoptado", "Coste variable", "Contribucion bruta", "Margen", "Nota"])
for i, (name, pc) in enumerate([("Autonomo", "B7"), ("Negocio", "C7"), ("Premium", "D7")]):
    r = 13 + i
    ws.cell(row=r, column=1, value=name).font = Font(name="Aptos", size=10, color=INK)
    c1 = ws.cell(row=r, column=2, value=f"=Supuestos!{pc}")
    c2 = ws.cell(row=r, column=3, value="=$C$9")
    c3 = ws.cell(row=r, column=4, value=f"=B{r}-C{r}")
    c4 = ws.cell(row=r, column=5, value=f"=D{r}/B{r}")
    for c in (c1, c2, c3):
        c.number_format = EUR
        c.border = BOX
    c4.number_format = PCT
    c4.border = BOX
    c4.font = Font(name="Aptos", size=10, bold=True, color=FOREST)
    ws.cell(row=r, column=6, value="No descuenta soporte, onboarding ni fijo: no es comparable con la contribucion de Unit_Economics").font = Font(name="Aptos", size=9, color=MUTED)

# ==========================================================================
# 5. COMPARADOR
# ==========================================================================
ws = sheet("Comparador")
title(ws, "Comparador de escenarios de coste",
      "Que pasa con el margen si el coste real por usuario resulta ser el del documento externo "
      "en lugar del estimado internamente. Solo compara COGS variable, para que la base sea la misma.", 7)
widths(ws, {"A": 30, "B": 15, "C": 15, "D": 15, "E": 15, "F": 15, "G": 15})

section(ws, 4, "COGS software por plan", 7)
header(ws, 5, ["Escenario", "Autonomo", "Negocio", "Premium", "", "", ""])
ws.cell(row=6, column=1, value="Modelo Bynoesis (con fuentes)").font = Font(name="Aptos", size=10, color=INK)
ws.cell(row=7, column=1, value="Hipotesis externa").font = Font(name="Aptos", size=10, color=INK)
ws.cell(row=8, column=1, value="Diferencia").font = Font(name="Aptos", size=10, bold=True, color=STOP)
ws.cell(row=9, column=1, value="Multiplicador").font = Font(name="Aptos", size=10, bold=True, color=STOP)
for j, col in enumerate(["B", "C", "D"]):
    src = ["E", "F", "G"][j]
    a = ws.cell(row=6, column=2 + j, value=f"=Unit_Economics!{src}13")
    b = ws.cell(row=7, column=2 + j, value="=Hipotesis_Externa!$C$9")
    d = ws.cell(row=8, column=2 + j, value=f"={col}7-{col}6")
    m = ws.cell(row=9, column=2 + j, value=f"=IF({col}6>0,{col}7/{col}6,\"\")")
    for c in (a, b, d):
        c.number_format = EUR
        c.border = BOX
    m.number_format = '0.0"x"'
    m.border = BOX
    m.font = Font(name="Aptos", size=10, bold=True, color=STOP)

section(ws, 11, "Margen bruto comparado", 7)
header(ws, 12, ["Escenario", "Autonomo", "Negocio", "Premium", "", "", ""])
ws.cell(row=13, column=1, value="Modelo Bynoesis").font = Font(name="Aptos", size=10, color=INK)
ws.cell(row=14, column=1, value="Hipotesis externa").font = Font(name="Aptos", size=10, color=INK)
ws.cell(row=15, column=1, value="Puntos perdidos").font = Font(name="Aptos", size=10, bold=True, color=STOP)
for j, col in enumerate(["B", "C", "D"]):
    src = ["E", "F", "G"][j]
    pcol = ["B", "C", "D"][j]
    a = ws.cell(row=13, column=2 + j, value=f"=Unit_Economics!{src}14")
    b = ws.cell(row=14, column=2 + j, value=f"=(Supuestos!{pcol}7-Hipotesis_Externa!$C$9)/Supuestos!{pcol}7")
    d = ws.cell(row=15, column=2 + j, value=f"={col}13-{col}14")
    for c in (a, b, d):
        c.number_format = PCT
        c.border = BOX
    d.font = Font(name="Aptos", size=10, bold=True, color=STOP)

ws["A17"] = "Como leerlo"
ws["A17"].font = Font(name="Aptos", size=10, bold=True, color=FOREST)
ws["A18"] = ("La hipotesis externa aplica un coste plano por usuario, asi que penaliza mucho al plan barato y "
             "apenas al caro, mientras que el modelo Bynoesis escala el coste con el uso incluido en cada plan. "
             "Si el piloto midiera un consumo parecido al de la hipotesis, el plan Autonomo seria el primero en "
             "sufrir. Es el escenario que conviene vigilar durante los primeros 30 dias.")
ws["A18"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A18"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A18:G21")

# ==========================================================================
# 6. ANUAL VS MENSUAL
# ==========================================================================
ws = sheet("Anual_vs_Mensual")
title(ws, "Tarifa anual frente a mensual",
      "El anual cobra 11 meses y da acceso 12: un descuento real del 8,3%. Se eligio este nivel, y no dos meses "
      "gratis, para proteger el margen de Premium mientras el piloto no ha medido voz y soporte reales.", 7)
widths(ws, {"A": 26, "B": 16, "C": 16, "D": 16, "E": 16, "F": 18, "G": 18})
header(ws, 4, ["Plan", "Mensual", "Cobro anual", "Equivalente/mes", "Ahorro/ano", "Contribucion mensual", "Margen contribucion"])
annual = [("Autonomo", "B7", 319, 18.69), ("Negocio", "C7", 539, 31.12), ("Premium", "D7", 1089, 49.12)]
for i, (name, pc, cobro, contrib) in enumerate(annual):
    r = 5 + i
    ws.cell(row=r, column=1, value=name).font = Font(name="Aptos", size=10, color=INK)
    c1 = ws.cell(row=r, column=2, value=f"=Supuestos!{pc}")
    c2 = ws.cell(row=r, column=3, value=cobro)
    c3 = ws.cell(row=r, column=4, value=f"=C{r}/12")
    c4 = ws.cell(row=r, column=5, value=f"=B{r}*12-C{r}")
    c5 = ws.cell(row=r, column=6, value=contrib)
    c6 = ws.cell(row=r, column=7, value=f"=F{r}/D{r}")
    for c in (c1, c2, c3, c4, c5):
        c.number_format = EUR
        c.border = BOX
    c2.font = Font(name="Aptos", size=10, color=INPUT)
    c5.font = Font(name="Aptos", size=10, color=INPUT)
    c6.number_format = PCT
    c6.border = BOX
    c6.font = Font(name="Aptos", size=10, bold=True, color=FOREST)

ws["A9"] = ("La contribucion anual es una estimacion del analisis del 15/07/2026 con el mismo uso, soporte y "
            "onboarding del escenario base y una sola comision Stripe prorrateada. El anual mejora caja y reduce "
            "comisiones, pero obliga a reservar capacidad de servicio durante doce meses.")
ws["A9"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A9"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A9:G11")

# ==========================================================================
# 7. ESCALA Y BREAK-EVEN
# ==========================================================================
ws = sheet("Escala_Breakeven")
title(ws, "Escala y punto de equilibrio",
      "Ingreso y resultado segun numero de cuentas, con el mix y el opex de la hoja Supuestos. "
      "El opex de 3.500 \u20ac es una hipotesis de planificacion, NO el gasto contable actual.", 6)
widths(ws, {"A": 14, "B": 20, "C": 20, "D": 20, "E": 20, "F": 22})
header(ws, 4, ["Cuentas", "Ingreso mensual", "Contribucion total", "Opex fijo", "Resultado", "Margen sobre ingreso"])
for i, n in enumerate([10, 25, 50, 100, 120, 150, 200, 300, 500, 750, 1000]):
    r = 5 + i
    c0 = ws.cell(row=r, column=1, value=n)
    c0.font = Font(name="Aptos", size=10, color=INPUT)
    c1 = ws.cell(row=r, column=2, value=f"=A{r}*(Supuestos!$B$7*Supuestos!$B$8+Supuestos!$C$7*Supuestos!$C$8+Supuestos!$D$7*Supuestos!$D$8)")
    c2 = ws.cell(row=r, column=3, value=f"=A{r}*(Unit_Economics!$E$18*Supuestos!$B$8+Unit_Economics!$F$18*Supuestos!$C$8+Unit_Economics!$G$18*Supuestos!$D$8)")
    c3 = ws.cell(row=r, column=4, value="=Supuestos!$B$41")
    c4 = ws.cell(row=r, column=5, value=f"=C{r}-D{r}")
    c5 = ws.cell(row=r, column=6, value=f"=IF(B{r}>0,E{r}/B{r},\"\")")
    for c in (c1, c2, c3, c4):
        c.number_format = EUR0
        c.border = BOX
    c5.number_format = PCT
    c5.border = BOX
    c4.font = Font(name="Aptos", size=10, bold=True, color=CALC)

ws.conditional_formatting  # marcador: el color se aplica abajo
ws.conditional_formatting.add(
    "E5:E15",
    CellIsRule(operator="lessThan", formula=["0"], font=Font(color=STOP, bold=True)))
ws.conditional_formatting.add(
    "E5:E15",
    CellIsRule(operator="greaterThanOrEqual", formula=["0"], font=Font(color=OKC, bold=True)))

ws["A17"] = "Punto de equilibrio exacto"
ws["A17"].font = Font(name="Aptos", size=10, bold=True, color=FOREST)
ws["A18"] = "Cuentas necesarias"
be_cell = ws["B18"]
be_cell.value = "=ROUNDUP(Supuestos!B41/(Unit_Economics!E18*Supuestos!B8+Unit_Economics!F18*Supuestos!C8+Unit_Economics!G18*Supuestos!D8),0)"
be_cell.number_format = '#,##0'
be_cell.font = Font(name="Aptos", size=12, bold=True, color=FOREST)
be_cell.fill = PatternFill("solid", fgColor=CREAM)
be_cell.border = BOX
ws["C18"] = "Con el catalogo adoptado y el mix 55/35/10. El analisis del 15/07/2026 lo situo en unas 120 cuentas."
ws["C18"].font = Font(name="Aptos", size=9.5, color=MUTED)

# --- Composicion del equilibrio por plan ---
section(ws, 20, "Cuantos clientes de cada plan hacen falta", 6)
header(ws, 21, ["Plan", "Mix", "Clientes", "Precio", "Ingreso mensual", "Contribucion mensual"])
plan_ref = [("Autonomo", "B", "E"), ("Negocio", "C", "F"), ("Premium", "D", "G")]
for i, (name, scol, ucol) in enumerate(plan_ref):
    r = 22 + i
    ws.cell(row=r, column=1, value=name).font = Font(name="Aptos", size=10, color=INK)
    c1 = ws.cell(row=r, column=2, value=f"=Supuestos!{scol}8")
    c2 = ws.cell(row=r, column=3, value=f"=ROUND($B$18*B{r},0)")
    c3 = ws.cell(row=r, column=4, value=f"=Supuestos!{scol}7")
    c4 = ws.cell(row=r, column=5, value=f"=C{r}*D{r}")
    c5 = ws.cell(row=r, column=6, value=f"=C{r}*Unit_Economics!{ucol}18")
    c1.number_format = PCT
    c2.number_format = '#,##0'
    c2.font = Font(name="Aptos", size=11, bold=True, color=FOREST)
    c2.fill = PatternFill("solid", fgColor=CREAM)
    for c in (c3, c4, c5):
        c.number_format = EUR0
    for c in (c1, c2, c3, c4, c5):
        c.border = BOX

r = 25
ws.cell(row=r, column=1, value="TOTAL").font = Font(name="Aptos", size=10, bold=True, color=FOREST)
for col, fmt in (("B", PCT), ("C", '#,##0'), ("E", EUR0), ("F", EUR0)):
    c = ws.cell(row=r, column={"B": 2, "C": 3, "E": 5, "F": 6}[col],
                value=f"=SUM({col}22:{col}24)")
    c.number_format = fmt
    c.font = Font(name="Aptos", size=10, bold=True, color=FOREST)
    c.fill = PatternFill("solid", fgColor=CREAM)
    c.border = BOX
ws.cell(row=r, column=4, value="").border = BOX

section(ws, 27, "Y si toda la cartera fuera de un solo plan", 6)
header(ws, 28, ["Plan", "Contribucion/cliente", "Clientes necesarios", "Ingreso mensual", "", ""])
for i, (name, scol, ucol) in enumerate(plan_ref):
    r = 29 + i
    ws.cell(row=r, column=1, value=name).font = Font(name="Aptos", size=10, color=INK)
    c1 = ws.cell(row=r, column=2, value=f"=Unit_Economics!{ucol}18")
    c2 = ws.cell(row=r, column=3, value=f"=IFERROR(ROUNDUP(Supuestos!$B$41/B{r},0),\"\")")
    c3 = ws.cell(row=r, column=4, value=f"=IFERROR(C{r}*Supuestos!{scol}7,\"\")")
    c1.number_format = EUR
    c2.number_format = '#,##0'
    c2.font = Font(name="Aptos", size=11, bold=True, color=FOREST)
    c3.number_format = EUR0
    for c in (c1, c2, c3):
        c.border = BOX

ws["A33"] = ("Leer las dos tablas juntas: la primera reparte el equilibrio segun el mix que esperas; la segunda "
             "dice cuantos clientes harian falta si solo vendieras un plan. La distancia entre ambas cifras es "
             "el valor real de vender el plan caro, y es el argumento para decidir a quien dedicar el esfuerzo "
             "comercial.")
ws["A33"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A33"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A33:F35")

# ==========================================================================
# 7b. ADS Y CAPTACION
# ==========================================================================
ws = sheet("Ads_Captacion")
ws.sheet_properties.tabColor = "FFB7831F"
title(ws, "Publicidad y coste de captacion",
      "Gasto variable: la publicidad no escala con los clientes que ya tienes, sino con los que quieres captar. "
      "Las celdas naranjas estan VACIAS a proposito: ninguna cifra de embudo consta en el repositorio. "
      "En cuanto escribas presupuesto y conversiones, el resto se calcula solo.", 6)
widths(ws, {"A": 36, "B": 16, "C": 16, "D": 18, "E": 14, "F": 44})

section(ws, 4, "Entradas de campana", 6)
header(ws, 5, ["Driver", "Valor", "", "Unidad", "", "Nota"])
ads_inputs = [
    ("Presupuesto mensual de ads", None, "€/mes", "El gasto variable principal. Sin el, el resto no calcula", EUR),
    ("Coste por clic", None, "€/clic", "Meta Ads y Google Ads dan medias distintas: usa la tuya", EUR),
    ("Conversion clic -> lead", None, "%", "Visitas que dejan datos en Solicitar acceso", PCT),
    ("Conversion lead -> prueba", None, "%", "Leads que activan la prueba de 14 dias", PCT),
    ("Conversion prueba -> pago", None, "%", "El dato que mas mueve el CAC", PCT),
    ("Churn mensual", None, "%", "Bajas sobre cartera. Necesario para el LTV", PCT),
    ("Altas que vienen de ads", None, "%", "El resto llega por boca a boca y no cuesta ads", PCT),
]
for i, (lab, val, u, nota, fmt) in enumerate(ads_inputs):
    r = 6 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    c = ws.cell(row=r, column=2, value=val)
    c.number_format = fmt
    c.font = Font(name="Aptos", size=10, bold=True, color=INPUT)
    c.fill = PatternFill("solid", fgColor="FFFDF3E7")
    c.border = BOX
    ws.cell(row=r, column=4, value=u).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6).alignment = Alignment(wrap_text=True, vertical="top")

section(ws, 14, "Embudo resultante", 6)
header(ws, 15, ["Metrica", "Valor", "", "Unidad", "", "Formula"])
funnel = [
    ("Clics al mes", "=IFERROR(B6/B7,\"\")", '#,##0', "clics", "Presupuesto / coste por clic"),
    ("Leads al mes", "=IFERROR(B16*B8,\"\")", '#,##0', "leads", "Clics x conversion a lead"),
    ("Pruebas iniciadas", "=IFERROR(B17*B9,\"\")", '#,##0', "pruebas", "Leads x conversion a prueba"),
    ("Clientes nuevos de ads", "=IFERROR(B18*B10,\"\")", '#,##0.0', "clientes/mes", "Pruebas x conversion a pago"),
    ("Altas totales estimadas", "=IFERROR(IF(B12>0,B19/B12,B19),\"\")", '#,##0.0', "clientes/mes", "Incluye las que no vienen de ads"),
    ("CAC real", "=IFERROR(B6/B19,\"\")", EUR, "€/cliente", "Presupuesto / clientes captados por ads"),
    ("CAC supuesto en el modelo", "=Supuestos!B42", EUR, "€/cliente", "150 € sin validar, para contraste"),
    ("Desviacion frente al supuesto", "=IFERROR(B21-B22,\"\")", EUR, "€/cliente", "Positivo = captar sale mas caro de lo previsto"),
]
for i, (lab, f, fmt, u, nota) in enumerate(funnel):
    r = 16 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    c = ws.cell(row=r, column=2, value=f)
    c.number_format = fmt
    bold = lab in ("CAC real", "Clientes nuevos de ads")
    c.font = Font(name="Aptos", size=11 if bold else 10, bold=bold, color=FOREST if bold else CALC)
    if bold:
        c.fill = PatternFill("solid", fgColor=CREAM)
    c.border = BOX
    ws.cell(row=r, column=4, value=u).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)

section(ws, 25, "Salud de la captacion", 6)
header(ws, 26, ["Metrica", "Valor", "", "Unidad", "", "Referencia habitual"])
health = [
    ("Contribucion media ponderada", "=Unit_Economics!E18*Supuestos!B8+Unit_Economics!F18*Supuestos!C8+Unit_Economics!G18*Supuestos!D8", EUR, "€/mes", "La que ya calcula el modelo"),
    ("Meses para recuperar el CAC", "=IFERROR(B27>0,\"\")", '#,##0.0', "meses", "Por debajo de 12 se considera sano"),
    ("Vida media del cliente", "=IFERROR(1/B11,\"\")", '#,##0.0', "meses", "1 / churn mensual"),
    ("LTV (contribucion x vida)", "=IFERROR(B27*B29,\"\")", EUR, "€", "Sin descuento financiero"),
    ("LTV / CAC", "=IFERROR(B30/B21,\"\")", '0.0"x"', "veces", "Referencia SaaS: 3x o mas"),
    ("Veredicto", "=IF(B31=\"\",\"Faltan datos\",IF(AND(B31>=3,B28<=12),\"Sano\",IF(B31>=1,\"Ajustado: revisar precio o embudo\",\"Insostenible: cada cliente pierde dinero\")))", None, "", "Se calcula solo al rellenar las entradas"),
]
for i, (lab, f, fmt, u, nota) in enumerate(health):
    r = 27 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    c = ws.cell(row=r, column=2, value=f)
    if fmt:
        c.number_format = fmt
    bold = lab in ("LTV / CAC", "Veredicto")
    c.font = Font(name="Aptos", size=11 if bold else 10, bold=bold, color=FOREST if bold else CALC)
    if bold:
        c.fill = PatternFill("solid", fgColor=CREAM)
    c.border = BOX
    ws.cell(row=r, column=4, value=u).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)
ws["B28"] = "=IFERROR(B21/B27,\"\")"
ws["B28"].number_format = '#,##0.0'
ws["B28"].border = BOX

section(ws, 34, "Impacto de los ads en el punto de equilibrio", 6)
header(ws, 35, ["Metrica", "Sin ads", "Con ads", "Unidad", "", "Nota"])
impact = [
    ("Coste fijo mensual", "=Supuestos!B41", "=Supuestos!B41+IFERROR(B6,0)", EUR0, "El presupuesto de ads se suma al opex mientras dure la campana"),
    ("Clientes para equilibrio", "=IFERROR(ROUNDUP(B36/$B$27,0),\"\")", "=IFERROR(ROUNDUP(C36/$B$27,0),\"\")", '#,##0', "Con la contribucion media ponderada"),
    ("Clientes adicionales que exige el ads", "", "=IFERROR(C37-B37,\"\")", '#,##0', "Los que la campana debe traer solo para pagarse"),
    ("Meses para conseguirlos", "", "=IFERROR(C38/B19,\"\")", '#,##0.0', "Al ritmo de captacion calculado arriba"),
]
for i, (lab, a, b, fmt, nota) in enumerate(impact):
    r = 36 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    for j, v in enumerate((a, b)):
        c = ws.cell(row=r, column=2 + j, value=v if v != "" else None)
        c.number_format = fmt
        bold = i >= 2 and j == 1
        c.font = Font(name="Aptos", size=10, bold=bold, color=WARN if bold else CALC)
        c.border = BOX
    ws.cell(row=r, column=4, value="").font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6).alignment = Alignment(wrap_text=True, vertical="top")

ws["A41"] = "Por que los ads van en su propia hoja"
ws["A41"].font = Font(name="Aptos", size=10, bold=True, color=FOREST)
ws["A42"] = ("El resto del libro mide lo que cuesta SERVIR a un cliente que ya tienes. La publicidad mide lo que "
             "cuesta CONSEGUIRLO, y se comporta al reves: si cortas la campana manana, el gasto desaparece pero "
             "los clientes captados siguen pagando. Por eso no se mezcla con el COGS ni con el margen de "
             "contribucion: se trata como una inversion con un plazo de recuperacion, que es la fila "
             "'Meses para recuperar el CAC'. Si ese plazo supera la vida media del cliente, la campana destruye "
             "valor aunque el margen por cuenta sea excelente.")
ws["A42"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A42"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A42:F45")

# ==========================================================================
# 7c. ESCENARIOS
# ==========================================================================
ws = sheet("Escenarios")
title(ws, "Escenarios de planificacion",
      "Tres futuros con los mismos costes unitarios y distinta velocidad comercial. "
      "El selector de la celda B5 alimenta la hoja PyG_Proyeccion. Las celdas naranjas "
      "estan vacias: la velocidad comercial es una decision del founder, no un dato del repositorio.", 6)
widths(ws, {"A": 34, "B": 18, "C": 18, "D": 18, "E": 14, "F": 40})

ws["A5"] = "Escenario activo"
ws["A5"].font = Font(name="Aptos", size=10, bold=True, color=FOREST)
sel = ws["B5"]
sel.value = "Base"
sel.font = Font(name="Aptos", size=11, bold=True, color=INPUT)
sel.fill = PatternFill("solid", fgColor=CREAM)
sel.border = BOX
dv = DataValidation(type="list", formula1='"Pesimista,Base,Optimista"', allow_blank=False)
ws.add_data_validation(dv)
dv.add(sel)
ws["C5"] = "Elige de la lista desplegable"
ws["C5"].font = Font(name="Aptos", size=9.5, italic=True, color=MUTED)

section(ws, 7, "Palancas por escenario", 6)
header(ws, 8, ["Palanca", "Pesimista", "Base", "Optimista", "Unidad", "Nota"])
scen = [
    ("Altas netas mes 1", None, 4, None, "clientes", "Base = el piloto de 3-5 comprometido en Tareas-vivas"),
    ("Crecimiento mensual de altas", None, None, None, "%", "PENDIENTE: depende del presupuesto de ads y del boca a boca"),
    ("Churn mensual", None, None, None, "%", "PENDIENTE: solo se sabra tras dos cierres del piloto"),
    ("Mix Autonomo", None, 0.55, None, "%", "Base = mix del analisis"),
    ("Mix Negocio", None, 0.35, None, "%", "Base = mix del analisis"),
    ("Mix Premium", None, 0.10, None, "%", "Base = mix del analisis"),
    ("Opex fijo mensual", None, 3500, None, "€/mes", "SUPUESTO hasta rellenar Datos_Pendientes"),
    ("Presupuesto de ads", None, None, None, "€/mes", "PENDIENTE: enlaza con la hoja Ads_Captacion"),
]
fmts = ['#,##0', PCT, PCT, PCT, PCT, PCT, EUR0, EUR0]
for i, (lab, p, b, o, u, nota) in enumerate(scen):
    r = 9 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    for j, v in enumerate((p, b, o)):
        c = ws.cell(row=r, column=2 + j, value=v)
        c.number_format = fmts[i]
        c.font = Font(name="Aptos", size=10, color=INPUT)
        c.fill = PatternFill("solid", fgColor=CREAM if v is not None else "FFFDF3E7")
        c.border = BOX
    ws.cell(row=r, column=5, value=u).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6).alignment = Alignment(wrap_text=True, vertical="top")

section(ws, 19, "Valores activos (los que usa la proyeccion)", 6)
header(ws, 20, ["Palanca", "Valor activo", "", "Unidad", "", ""])
for i, (lab, _, _, _, u, _) in enumerate(scen):
    r = 21 + i
    src = 9 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    c = ws.cell(row=r, column=2,
                value=f'=IF($B$5="Pesimista",B{src},IF($B$5="Optimista",D{src},C{src}))')
    c.number_format = fmts[i]
    c.font = Font(name="Aptos", size=10, bold=True, color=FOREST)
    c.border = BOX
    ws.cell(row=r, column=4, value=u).font = Font(name="Aptos", size=9.5, color=MUTED)

# ==========================================================================
# 7d. PROYECCION 24 MESES
# ==========================================================================
ws = sheet("PyG_Proyeccion")
title(ws, "Proyeccion a 24 meses",
      "Cuenta de resultados mensual y caja acumulada, gobernada por el escenario activo de la hoja Escenarios. "
      "Mientras el crecimiento y el churn esten vacios, la cartera se queda plana: es lo honesto, no un fallo.", 13)
widths(ws, {"A": 8, "B": 13, "C": 10, "D": 10, "E": 13, "F": 14, "G": 13, "H": 13,
            "I": 12, "J": 11, "K": 13, "L": 14, "M": 15})
header(ws, 4, ["Mes", "Cartera inicio", "Altas", "Bajas", "Cartera fin", "MRR",
               "COGS", "Margen bruto", "Opex fijo", "Ads", "Resultado", "Caja acumulada", "ARR"])

ws["A5"] = 0
ws["A5"].font = Font(name="Aptos", size=10, color=INK)
ws["B5"] = 0
ws["B5"].font = Font(name="Aptos", size=10, bold=True, color=INPUT)
ws["B5"].fill = PatternFill("solid", fgColor="FFFDF3E7")
ws["B5"].border = BOX
ws["C5"] = 0
ws["D5"] = 0
ws["E5"] = "=B5+C5-D5"
ws["L5"] = "=Datos_Pendientes!B15"

E = "Escenarios"
U = "Unit_Economics"
for m in range(1, 25):
    r = 5 + m
    p = r - 1
    ws.cell(row=r, column=1, value=m).font = Font(name="Aptos", size=10, color=INK)
    F = {
        2: f"=E{p}",
        3: f"=IFERROR(ROUND('{E}'!$B$21*(1+'{E}'!$B$22)^{m - 1},1),0)",
        4: f"=IFERROR(ROUND(B{r}*'{E}'!$B$23,1),0)",
        5: f"=B{r}+C{r}-D{r}",
        6: f"=E{r}*(Supuestos!$B$7*'{E}'!$B$24+Supuestos!$C$7*'{E}'!$B$25+Supuestos!$D$7*'{E}'!$B$26)",
        7: f"=E{r}*('{U}'!$E$13*'{E}'!$B$24+'{U}'!$F$13*'{E}'!$B$25+'{U}'!$G$13*'{E}'!$B$26)",
        8: f"=F{r}-G{r}",
        9: f"='{E}'!$B$27",
        10: f"=IFERROR('{E}'!$B$28,0)",
        11: f"=H{r}-I{r}-J{r}",
        12: f"=L{p}+K{r}",
        13: f"=F{r}*12",
    }
    for col, f in F.items():
        c = ws.cell(row=r, column=col, value=f)
        if col in (2, 3, 4, 5):
            c.number_format = '#,##0.0'
        elif col == 13:
            c.number_format = EUR0
        else:
            c.number_format = EUR0
        c.border = BOX
        if col in (11, 12):
            c.font = Font(name="Aptos", size=10, bold=True, color=CALC)

ws.conditional_formatting.add(
    "K6:L29", CellIsRule(operator="lessThan", formula=["0"], font=Font(color=STOP, bold=True)))
ws.conditional_formatting.add(
    "K6:L29", CellIsRule(operator="greaterThanOrEqual", formula=["0"], font=Font(color=OKC, bold=True)))
ws.freeze_panes = "B5"

ws["A31"] = "Indicadores derivados"
ws["A31"].font = Font(name="Aptos", size=10, bold=True, color=FOREST)
derived = [
    ("Mes en que el resultado se vuelve positivo", '=IFERROR(INDEX($A$6:$A$29,MATCH(TRUE,INDEX($K$6:$K$29>=0,0),0)),"No llega en 24 meses")'),
    ("Caja minima alcanzada", "=MIN(L6:L29)"),
    ("Mes de caja minima", '=IFERROR(INDEX($A$6:$A$29,MATCH(MIN($L$6:$L$29),$L$6:$L$29,0)),"")'),
    ("Cartera al mes 24", "=E29"),
    ("ARR al mes 24", "=M29"),
]
for i, (lab, f) in enumerate(derived):
    r = 32 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    c = ws.cell(row=r, column=3, value=f)
    c.number_format = EUR0 if "Caja" in lab or "ARR" in lab else '#,##0'
    c.font = Font(name="Aptos", size=11, bold=True, color=FOREST)
    c.fill = PatternFill("solid", fgColor=CREAM)
    c.border = BOX
ws.merge_cells("A31:B31")

ws["A38"] = ("La caja minima es la cifra que decide si el proyecto sobrevive: es el dinero que hay que tener "
             "disponible antes de empezar. Si supera el capital aportado, el plan no es financiable tal cual y "
             "hay que recortar opex, subir precio o retrasar la contratacion.")
ws["A38"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A38"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A38:M40")

# ==========================================================================
# 7e. SENSIBILIDAD
# ==========================================================================
ws = sheet("Sensibilidad")
title(ws, "Sensibilidad del punto de equilibrio",
      "Cuantas cuentas hacen falta segun el opex real y la contribucion media. Sirve para responder "
      "'si me equivoco en el gasto fijo, cuanto me duele'. La fila y la columna gris son entradas.", 8)
widths(ws, {"A": 26, "B": 13, "C": 13, "D": 13, "E": 13, "F": 13, "G": 13, "H": 13})

section(ws, 4, "Cuentas necesarias para equilibrio", 8)
ws["A5"] = "Opex \\ Contribucion"
ws["A5"].font = Font(name="Aptos", size=9.5, bold=True, color=FOREST)
ws["A5"].fill = PatternFill("solid", fgColor=SAND)
ws["A5"].border = BOX
contribs = [20, 25, 29.36, 35, 40, 45, 50]
for j, cv in enumerate(contribs):
    c = ws.cell(row=5, column=2 + j, value=cv)
    c.number_format = EUR
    c.font = Font(name="Aptos", size=9.5, bold=True, color=INPUT)
    c.fill = PatternFill("solid", fgColor=SAND)
    c.border = BOX
opexes = [1500, 2000, 2500, 3000, 3500, 4000, 5000, 6000, 8000]
for i, ov in enumerate(opexes):
    r = 6 + i
    c0 = ws.cell(row=r, column=1, value=ov)
    c0.number_format = EUR0
    c0.font = Font(name="Aptos", size=9.5, bold=True, color=INPUT)
    c0.fill = PatternFill("solid", fgColor=SAND)
    c0.border = BOX
    for j in range(len(contribs)):
        col = get_column_letter(2 + j)
        c = ws.cell(row=r, column=2 + j, value=f"=IFERROR(ROUNDUP($A{r}/{col}$5,0),\"\")")
        c.number_format = '#,##0'
        c.border = BOX
ws.conditional_formatting.add("B6:H14", ColorScaleRule(
    start_type='min', start_color='FFDDEFE7',
    end_type='max', end_color='FFF7E8E3'))

ws["A16"] = ("La columna de 29,36 € es la contribucion media ponderada que calcula el modelo con el mix "
             "55/35/10. Leer la fila del opex real: cada 500 € de gasto fijo de mas son unas 17 cuentas "
             "adicionales que hay que vender solo para empatar.")
ws["A16"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A16"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A16:H18")

# ==========================================================================
# 7f. CAPACIDAD DE SOPORTE
# ==========================================================================
ws = sheet("Capacidad_Soporte")
title(ws, "Capacidad de soporte y cuando contratar",
      "El soporte es el coste que primero rompe el margen al crecer. Traduce cuentas en horas de persona "
      "y avisa del punto en el que una sola persona ya no llega.", 7)
widths(ws, {"A": 30, "B": 14, "C": 14, "D": 14, "E": 16, "F": 18, "G": 34})

section(ws, 4, "Parametros", 7)
params = [
    ("Horas utiles por persona y mes", 130, '#,##0', "Jornada completa descontando festivos y tareas internas"),
    ("Minutos de soporte Autonomo", "=Supuestos!B19", '#,##0', "De la hoja Supuestos"),
    ("Minutos de soporte Negocio", "=Supuestos!C19", '#,##0', "De la hoja Supuestos"),
    ("Minutos de soporte Premium", "=Supuestos!D19", '#,##0', "De la hoja Supuestos"),
]
for i, (lab, v, fmt, nota) in enumerate(params):
    r = 5 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    c = ws.cell(row=r, column=2, value=v)
    c.number_format = fmt
    c.font = Font(name="Aptos", size=10, color=INPUT if not isinstance(v, str) else CALC)
    c.border = BOX
    ws.cell(row=r, column=7, value=nota).font = Font(name="Aptos", size=9.5, color=MUTED)

section(ws, 10, "Carga segun tamano de cartera", 7)
header(ws, 11, ["Cuentas", "Minutos/mes", "Horas/mes", "Personas necesarias", "Coste soporte", "% sobre MRR", "Situacion"])
for i, n in enumerate([25, 50, 100, 120, 200, 300, 500, 750, 1000]):
    r = 12 + i
    c0 = ws.cell(row=r, column=1, value=n)
    c0.font = Font(name="Aptos", size=10, color=INPUT)
    c1 = ws.cell(row=r, column=2, value=f"=A{r}*($B$6*Supuestos!$B$8+$B$7*Supuestos!$C$8+$B$8*Supuestos!$D$8)")
    c2 = ws.cell(row=r, column=3, value=f"=B{r}/60")
    c3 = ws.cell(row=r, column=4, value=f"=C{r}/$B$5")
    c4 = ws.cell(row=r, column=5, value=f"=C{r}*Supuestos!$B$39")
    c5 = ws.cell(row=r, column=6, value=f"=IFERROR(E{r}/(A{r}*(Supuestos!$B$7*Supuestos!$B$8+Supuestos!$C$7*Supuestos!$C$8+Supuestos!$D$7*Supuestos!$D$8)),\"\")")
    c6 = ws.cell(row=r, column=7, value=f'=IF(D{r}<=0.5,"Lo lleva el founder",IF(D{r}<=1,"Ocupa a una persona entera",IF(D{r}<=2,"Hace falta una segunda persona","Equipo de soporte formal")))')
    c1.number_format = '#,##0'
    c2.number_format = '#,##0'
    c3.number_format = '0.00'
    c4.number_format = EUR0
    c5.number_format = PCT
    c3.font = Font(name="Aptos", size=10, bold=True, color=FOREST)
    for c in (c0, c1, c2, c3, c4, c5, c6):
        c.border = BOX
    c6.font = Font(name="Aptos", size=9.5, color=MUTED)

ws["A22"] = ("El salto de 'lo lleva el founder' a 'una persona entera' es el momento mas peligroso: el coste "
             "aparece de golpe y el ingreso crece poco a poco. Conviene tenerlo cubierto en caja antes de "
             "llegar, no cuando ya ha llegado.")
ws["A22"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A22"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A22:G24")

# ==========================================================================
# 7g. KPIs DEL PILOTO
# ==========================================================================
ws = sheet("KPIs_Piloto")
ws.sheet_properties.tabColor = TEAL
title(ws, "KPIs que debe responder el piloto",
      "Los que ya estan comprometidos en Tareas-vivas y en Unit-economics. La columna Observado se rellena "
      "durante los dos cierres semanales del piloto con 3-5 autonomos.", 6)
widths(ws, {"A": 40, "B": 16, "C": 16, "D": 14, "E": 20, "F": 40})
header(ws, 4, ["Indicador", "Objetivo", "Observado", "Unidad", "Fuente del dato", "Por que importa"])
kpis = [
    ("Resolucion por cerebro interno", 0.60, None, "%", "Logs de IA por negocio", "Si baja del 40% el coste de IA se dispara", PCT),
    ("Activacion: alta hasta primer cobro", None, None, "dias", "Eventos de producto", "Mide si el producto engancha antes de que caduque la prueba"),
    ("Trabajos cerrados sin facturar", None, None, "n/mes", "Panel de trabajos", "Es el dinero que Bynoesis rescata: el argumento de venta"),
    ("Cobros recuperados", None, None, "€/mes", "Recordatorios y portal", "Convierte la suscripcion en inversion con retorno"),
    ("Tiempo ahorrado declarado", None, None, "h/semana", "Entrevista de cierre", "El testimonio que sostiene el precio"),
    ("Minutos de soporte por cuenta", 12, None, "min/mes", "Registro de soporte", "Autonomo: el supuesto es 12 min. Es la partida que rompe el margen"),
    ("Minutos de voz consumidos (Premium)", 100, None, "min/mes", "Adaptador de voz", "Si nadie los usa, sacarlos del plan y venderlos como add-on"),
    ("Correcciones sobre lo que propone Bynoesis", None, None, "%", "Eventos de correccion", "Mide la confianza real en el asistente"),
    ("Coste por cuenta observado", 1.48, None, "€/mes", "Costes por negocio", "Contrasta con el COGS estimado del modelo"),
    ("Retencion a 60 dias", None, None, "%", "Suscripciones", "Sin esto no hay LTV defendible"),
    ("CAC por canal", None, None, "€", "Ads_Captacion", "El supuesto de 150 € esta sin validar"),
]
for i, k in enumerate(kpis):
    lab, obj, obs, u, src, why = k[0], k[1], k[2], k[3], k[4], k[5]
    fmt = k[6] if len(k) > 6 else None
    r = 5 + i
    ws.cell(row=r, column=1, value=lab).font = Font(name="Aptos", size=10, color=INK)
    c1 = ws.cell(row=r, column=2, value=obj)
    if fmt:
        c1.number_format = fmt
    c1.font = Font(name="Aptos", size=10, color=CALC)
    c1.border = BOX
    c2 = ws.cell(row=r, column=3, value=obs)
    c2.fill = PatternFill("solid", fgColor="FFFDF3E7")
    c2.font = Font(name="Aptos", size=10, color=INPUT)
    c2.border = BOX
    ws.cell(row=r, column=4, value=u).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=5, value=src).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6, value=why).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=6).alignment = Alignment(wrap_text=True, vertical="top")
ws.freeze_panes = "A5"

# ==========================================================================
# 8. OPCIONES DE IA
# ==========================================================================
ws = sheet("Opciones_IA")
title(ws, "Coste de IA por opcion",
      "Con 8.000 tokens de entrada y 1.200 de salida por interaccion avanzada. Sirve para decidir cuando "
      "compensa alojar un modelo propio en lugar de pagar por uso.", 6)
widths(ws, {"A": 34, "B": 22, "C": 16, "D": 16, "E": 16, "F": 34})
header(ws, 4, ["Opcion", "Coste/interaccion", "75/mes", "300/mes", "1.500/mes", "Nota"])
ai_rows = [
    ("Cerebro determinista Bynoesis", 0, 0, 0, 0, "Codigo propio: sin coste por token"),
    ("Cloudflare Qwen3 30B A3B", 0.0007, 0.05, 0.21, 1.07, "Proveedor compatible barato"),
    ("Groq Qwen3 32B", 0.0027, 0.20, 0.80, 3.98, "Latencia baja"),
    ("Anthropic Haiku 4.5", 0.0123, 0.92, 3.68, 18.41, "Respaldo de calidad"),
]
for i, (a, b, c, d, e, n) in enumerate(ai_rows):
    r = 5 + i
    ws.cell(row=r, column=1, value=a).font = Font(name="Aptos", size=10, color=INK)
    for j, v in enumerate((b, c, d, e)):
        cell = ws.cell(row=r, column=2 + j, value=v)
        cell.number_format = '0.0000' if j == 0 else EUR
        cell.border = BOX
        cell.font = Font(name="Aptos", size=10, color=INPUT)
    ws.cell(row=r, column=6, value=n).font = Font(name="Aptos", size=9.5, color=MUTED)

section(ws, 10, "Cuando compensa alojar un modelo propio", 6)
host = [
    ("GPU 16 GB a 0,58 USD/h, 730 h/mes", "423,40 USD (~371 \u20ac al cambio usado)"),
    ("Cruce frente a Haiku 4.5", "~30.243 interacciones/mes"),
    ("Cruce frente a Groq Qwen3", "~139.828 interacciones/mes"),
    ("Conclusion", "Por debajo de ese volumen, cerebro interno + pago por uso es mas barato y exige menos operacion"),
]
for i, (a, b) in enumerate(host):
    r = 11 + i
    ws.cell(row=r, column=1, value=a).font = Font(name="Aptos", size=10, color=INK)
    c = ws.cell(row=r, column=2, value=b)
    c.font = Font(name="Aptos", size=10, bold=(i == 3), color=FOREST if i == 3 else INK)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)

ws["A16"] = ("No existe un servidor publico gratuito adecuado como nucleo de produccion: los tiers gratis pueden "
             "cambiar, limitar concurrencia, cortar solicitudes y tratar datos fuera de Bynoesis. El modelo open "
             "source evita licencia por token, pero no elimina computo, seguridad ni mantenimiento.")
ws["A16"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A16"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A16:F18")

# ==========================================================================
# 9. DATOS PENDIENTES
# ==========================================================================
ws = sheet("Datos_Pendientes")
ws.sheet_properties.tabColor = "FFC0533F"
title(ws, "Datos que faltan \u2014 rellenar antes de usar este modelo",
      "Estas cifras NO constan en el repositorio y NO se han estimado. Mientras esten vacias, el modelo "
      "es un escenario de planificacion y no un reflejo de la empresa. Rellenar la columna Valor real.", 5)
widths(ws, {"A": 38, "B": 18, "C": 18, "D": 20, "E": 46})
header(ws, 4, ["Concepto", "Valor real", "Unidad", "Quien lo tiene", "Por que hace falta"])
pend = [
    ("Forma juridica y NIF", "", "texto", "Founder", "Determina IRPF/IS, cuota de autonomos y la verificacion de Meta"),
    ("Reparto societario entre socios", "", "%", "Founder y socio", "Sin el no se puede repartir resultado ni valorar"),
    ("Sueldo o retirada mensual founder", "", "\u20ac/mes", "Founder", "Es la mayor partida del opex real; ahora es hipotesis"),
    ("Sueldo o retirada mensual socio", "", "\u20ac/mes", "Socio", "Idem"),
    ("Cuota de autonomos por socio", "", "\u20ac/mes", "Gestoria", "Coste fijo mensual ineludible"),
    ("Gestoria / asesoria", "", "\u20ac/mes", "Gestoria", "Fijo recurrente"),
    ("Factura real de Railway", "", "\u20ac/mes", "Founder", "Sustituye el prorrateo de plataforma de 65 \u20ac"),
    ("Dominio y correo", "", "\u20ac/ano", "Founder", "Fijo menor pero real"),
    ("Herramientas y suscripciones", "", "\u20ac/mes", "Founder", "IDE, diseno, analitica, almacenamiento"),
    ("Seguro de responsabilidad civil", "", "\u20ac/ano", "Founder", "Habitual antes de operar con datos de terceros"),
    ("Capital aportado a fecha de hoy", "", "\u20ac", "Founder y socio", "El vault cita ~4.000 \u20ac iniciales; confirmar"),
    ("Ingresos facturados hasta hoy", "", "\u20ac", "Founder", "Si es 0, el modelo es prospectivo y debe decirlo"),
    ("Clientes de pago actuales", "", "n", "Founder", "Base para cualquier proyeccion"),
    ("CAC observado por canal", "", "\u20ac/cliente", "Piloto", "El 150 \u20ac del modelo es un supuesto sin validar"),
    ("Churn mensual observado", "", "%", "Piloto", "Sin el no hay LTV defendible"),
    ("Presupuesto de marketing", "", "\u20ac/mes", "Founder", "Entra en el opex y condiciona el crecimiento"),
]
for i, (a, b, c, d, e) in enumerate(pend):
    r = 5 + i
    ws.cell(row=r, column=1, value=a).font = Font(name="Aptos", size=10, color=INK)
    cell = ws.cell(row=r, column=2, value=b)
    cell.fill = PatternFill("solid", fgColor="FFFDF3E7")
    cell.border = BOX
    cell.font = Font(name="Aptos", size=10, color=INPUT)
    ws.cell(row=r, column=3, value=c).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=4, value=d).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=5, value=e).font = Font(name="Aptos", size=9.5, color=MUTED)
    ws.cell(row=r, column=5).alignment = Alignment(wrap_text=True, vertical="top")
ws.freeze_panes = "A5"

# ==========================================================================
# 10. FUENTES
# ==========================================================================
ws = sheet("Fuentes")
title(ws, "Fuentes y cautelas",
      "Tarifas consultadas el 15/07/2026. Pueden haber cambiado: verificar antes de tomar una decision "
      "de precio o de proveedor.", 4)
widths(ws, {"A": 30, "B": 30, "C": 58, "D": 16})
header(ws, 4, ["Driver", "Proveedor", "URL", "Consultado"])
sources = [
    ("Comisiones de pago", "Stripe Espana", "https://stripe.com/es/pricing", "15/07/2026"),
    ("Coste de modelo de respaldo", "Anthropic Haiku", "https://www.anthropic.com/claude/haiku", "15/07/2026"),
    ("Plataforma y almacenamiento", "Railway", "https://docs.railway.com/pricing", "15/07/2026"),
    ("Correo transaccional", "Resend", "https://resend.com/docs/knowledge-base/what-is-resend-pricing", "15/07/2026"),
    ("Mensajeria utility", "WhatsApp Business", "https://whatsappbusiness.com/products/platform-pricing/", "15/07/2026"),
    ("Tipo de cambio", "ECB", "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html", "14/07/2026"),
    ("Voz telefonica", "Retell", "https://www.retellai.com/pricing", "15/07/2026"),
    ("Transcripcion", "Groq Speech-to-Text", "https://console.groq.com/docs/speech-to-text", "15/07/2026"),
    ("GPU serverless", "Runpod", "https://www.runpod.io/product/serverless", "15/07/2026"),
    ("Modelo abierto", "Qwen3", "https://github.com/QwenLM/Qwen3", "15/07/2026"),
]
for i, (a, b, c, d) in enumerate(sources):
    r = 5 + i
    ws.cell(row=r, column=1, value=a).font = Font(name="Aptos", size=10, color=INK)
    ws.cell(row=r, column=2, value=b).font = Font(name="Aptos", size=10, color=INK)
    cell = ws.cell(row=r, column=3, value=c)
    cell.font = Font(name="Aptos", size=9, color="FF008000", underline="single")
    cell.hyperlink = c
    ws.cell(row=r, column=4, value=d).font = Font(name="Aptos", size=9.5, color=MUTED)

ws["A17"] = "Cautelas"
ws["A17"].font = Font(name="Aptos", size=10, bold=True, color=STOP)
ws["A18"] = ("La tarifa utility de WhatsApp en Espana usa ademas una rate card publicada por un tercero, porque la "
             "tabla oficial dinamica no expuso el valor durante la consulta. Las tarifas pueden cambiar y no siempre "
             "incluyen impuestos. El coste de la hoja Hipotesis_Externa no tiene fuente ni fecha conocidas.")
ws["A18"].alignment = Alignment(wrap_text=True, vertical="top")
ws["A18"].font = Font(name="Aptos", size=9.5, color=MUTED)
ws.merge_cells("A18:D21")

# --- Guardar ---------------------------------------------------------------
DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "06-negocio-y-finanzas", "Bynoesis-Modelo-Economico.xlsx",
)
out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
for s in wb.worksheets:
    s.sheet_view.showGridLines = False
try:
    wb.save(out)
except PermissionError:
    raise SystemExit(
        f"No se puede escribir en {out}: cierra el archivo en Excel y vuelve a ejecutarlo."
    )
print("OK ->", out)
print("hojas:", [s.title for s in wb.worksheets])
