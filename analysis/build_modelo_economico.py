"""Genera el modelo economico de Noesis en xlsx.

Todas las cifras proceden de docs/Unit-economics-y-cerebro-interno.md y de
analysis/build_unit_economics.mjs (fechadas 15/07/2026). Lo que no consta en el
repositorio se deja como celda PENDIENTE: no se inventa ningun dato.
"""
import sys
sys.path.insert(0, r"C:\Users\xavie\AppData\Local\Temp\claude\c--Users-xavie-Documents-GitHub-noesis\c99a232e-eeaa-4dd9-8f3d-e85b1e5a327f\scratchpad\pylibs")

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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
title(ws, "Noesis \u2014 Modelo economico",
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

section(ws, 10, "Resultado por plan (modelo Noesis)", 6)
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
header(ws, 5, ["Concepto de gasto", "Calculo (hipotesis)", "Coste mensual/usuario", "", "", "Contraste con el modelo Noesis"])
ext = [
    ("API de Meta (WhatsApp)", "150 mensajes enviados x 0,0166 \u20ac", "=150*Supuestos!B29", "El modelo Noesis usa 30/80/200 mensajes segun plan, no 150 fijos"),
    ("Inteligencia Artificial (LLM)", "150 procesamientos x ~0,02 \u20ac", 3.00, "El modelo Noesis estima 0,05/0,22/0,69 \u20ac: el cerebro interno resuelve el 60%"),
    ("Servidor y base de datos", "Prorrateo basico por usuario", 1.00, "El modelo Noesis reparte 65 \u20ac de plataforma entre las cuentas activas"),
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
ws.cell(row=6, column=1, value="Modelo Noesis (con fuentes)").font = Font(name="Aptos", size=10, color=INK)
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
ws.cell(row=13, column=1, value="Modelo Noesis").font = Font(name="Aptos", size=10, color=INK)
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
             "apenas al caro, mientras que el modelo Noesis escala el coste con el uso incluido en cada plan. "
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
from openpyxl.formatting.rule import CellIsRule
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
    ("Cerebro determinista Noesis", 0, 0, 0, 0, "Codigo propio: sin coste por token"),
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
             "cambiar, limitar concurrencia, cortar solicitudes y tratar datos fuera de Noesis. El modelo open "
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
out = r"c:\Users\xavie\Documents\GitHub\noesis\docs\Noesis-Modelo-Economico.xlsx"
for s in wb.worksheets:
    s.sheet_view.showGridLines = False
wb.save(out)
print("OK ->", out)
print("hojas:", [s.title for s in wb.worksheets])
