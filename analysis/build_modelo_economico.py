"""Genera el modelo economico de Bynoesis en xlsx.

Este es el libro **base**: el unico de los tres que calcula el coste de servir una
cuenta desde sus drivers —creditos de IA, mensajes, minutos, documentos, GB— en vez
de copiar un total ya cocinado. Los libros v2 y v3 anadieron capas que faltaban;
esta revision las trae aqui sin perder ese desglose.

Que corrige respecto a la version de agosto:

1. **El opex ya no es una constante.** Los 3.500 EUR eran una caja negra, y
   sustituirlos por 500 EUR describia un negocio donde nadie cobra. Ahora la
   estructura esta desglosada partida a partida y hay **tres equilibrios**: cubrir
   la estructura, cubrir estructura mas cuota de autonomos, y pagarte una retirada.
   Solo el tercero significa algo.
2. **El soporte no se cuenta dos veces.** Cobrarlo a 25 EUR/hora *y ademas* pagarle
   una retirada al founder contaba su tiempo dos veces. Hay dos contribuciones y el
   libro dice cual usar: **en caja** mientras atiendes tu (tu tiempo es capacidad,
   no gasto) y **cargada** cuando ese soporte lo paga alguien.
3. **La gente se va.** Cohortes por edad, con bajas mas altas los tres primeros
   meses. La proyeccion anterior tenia la casilla de bajas vacia y calculaba cero
   bajas durante dos anos.
4. **El tiempo del founder es el limite, no el mercado.** Las altas salen de las
   horas que quedan tras atender a la cartera, asi que la rampa se frena sola.
5. **El primer mes no se cobra entero:** catorce dias de prueba y un porcentaje de
   recibos que no se cobran.
6. **Los minutos de soporte se ponderan por la mezcla.** El libro v3 uso los 12
   minutos del plan Autonomo para toda la cartera; con la mezcla 55/35/10 son 18,1,
   y eso cambia el techo de cuentas que una persona puede atender.

Cifras ancla: analisis del 15/07/2026 (`Unit-economics-y-cerebro-interno.md`), canal
y comisiones del 16/09/2026 (`Canal-comercial-y-comisiones.md`) y el libro que el
founder edito el 17/09/2026 (plataforma 7 EUR). Lo que no esta medido va marcado
como supuesto y se lista en `Datos_Pendientes`.

Los valores por defecto viven en el diccionario `D`: la hoja `Supuestos` y la
comprobacion que el script imprime al terminar leen de ahi, asi que no pueden
separarse.

Uso: py analysis/build_modelo_economico.py [salida.xlsx]
"""
from __future__ import annotations

import math
import os
import sys

try:
    from openpyxl import Workbook
except ModuleNotFoundError:
    raise SystemExit('Falta openpyxl. Instalalo con: pip install -e ".[analysis]"')
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# --- Paleta de marca (docs/design/STYLE_TOKENS.json) -----------------------
FOREST, TEAL, CREAM, SAND = "FF14463B", "FF2E8B74", "FFF4F1EA", "FFE7E0D1"
INK, MUTED, WHITE = "FF15211C", "FF5D6B66", "FFFFFFFF"
INPUT = "FF0000CC"      # azul = celda editable, convencion de modelos financieros
CALC = "FF15211C"       # negro = formula
WARN, STOP, OKC = "FFB7831F", "FFC0533F", "FF1F8A6D"
NARANJA = "FFFDF3E7"    # fondo de las celdas que se rellenan a mano

HAIR = Side(style="thin", color="FFDDD8CC")
BOX = Border(left=HAIR, right=HAIR, top=HAIR, bottom=HAIR)

EUR = '#,##0.00\\ "€"'
EUR0 = '#,##0\\ "€"'
PCT, PCT0, NUM, DEC = '0.0%', '0%', '#,##0', '#,##0.0'
FUENTE = "Aptos"


def _es(n):
    """Formatea un numero con el separador de miles espanol."""
    return f"{n:,.0f}".replace(",", ".")


# ==========================================================================
# VALORES POR DEFECTO — unica fuente de verdad del libro y de la comprobacion
# ==========================================================================
D = {
    # Por plan: (Autonomo, Negocio, Premium)
    "precio_ant": (29, 39, 79),
    "precio": (29, 49, 99),
    "mix": (0.55, 0.35, 0.10),
    "creditos": (75, 300, 1500),
    "uso": (0.35, 0.40, 0.25),
    "interno": (0.60, 0.60, 0.60),
    "wa_util": (30, 80, 200),
    "wa_serv": (100, 300, 1000),
    "audio": (15, 60, 200),
    "docs": (15, 50, 200),
    "docs_fuera": (0.20, 0.20, 0.20),
    "almacen": (0.25, 1, 3),
    "voz": (0, 0, 100),
    "soporte": (12, 20, 45),
    "onboarding": (30, 60, 120),
    "anual": (319, 539, 1089),
    # Tarifas de proveedores
    "eurusd": 1 / 1.1405,
    "stripe_pay": 0.015, "stripe_bill": 0.007, "stripe_fijo": 0.25,
    "wa_precio": 0.0166, "wa_serv_precio": 0.0166,
    "haiku": 0.014, "qwen": 0.003028, "peso_qwen": 0.80,
    "whisper": 0.04, "extraccion": 0.012, "storage": 0.015,
    "voz_min": 0.11, "voz_num": 2,
    # Comportamiento del cliente
    "churn_nuevo": 0.08, "churn_maduro": 0.04, "dias_prueba": 14,
    "impagos": 0.03, "pct_anual": 0.20, "mult_nueva": 2.5,
    # Tiempo del founder
    "horas_mes": 60, "horas_alta": 3.0, "objetivo": 5, "crecimiento": 0.05,
    "hora_soporte": 25, "horas_persona": 130, "media_jornada": 900,
    # Estructura
    "plataforma": 7, "herramientas": 40, "gestoria": 60, "seguro": 30, "ads": 0,
    "cuota_autonomos": 300, "retirada": 1200, "caja_inicial": 4000,
    # Captacion y canal
    "cac": 150, "implantacion": 99, "pct_implantacion": 0.0,
    "com_alta": 1, "com_recurrente": 0.10, "com_meses": 12,
    "pct_canal": 0.0, "coste_comercial": 2400,
    # Fiscal
    "iva": 0.21, "cuentas_fijo": 100,
}

ORDEN = ["Resumen", "Calculadora", "Supuestos", "Unit_Economics", "Escala_Breakeven",
         "Vida_y_LTV", "Horas_del_founder", "Rampa_36m", "Escenarios", "Sensibilidad",
         "Canal_Comision", "Ads_Captacion", "Anual_vs_Mensual", "Comparador",
         "Hipotesis_Externa", "Opciones_IA", "KPIs_Piloto", "Datos_Pendientes",
         "Fuentes"]

wb = Workbook()
wb.active.title = ORDEN[0]
for _n in ORDEN[1:]:
    wb.create_sheet(_n)


# ==========================================================================
# AYUDAS DE FORMATO
# ==========================================================================
def hoja(nombre, color=TEAL):
    ws = wb[nombre]
    ws.sheet_properties.tabColor = color
    ws.sheet_view.showGridLines = False
    return ws


def title(ws, text, sub=None, span=8):
    ws["A1"] = text
    ws["A1"].font = Font(name="Aptos Display", size=17, bold=True, color=FOREST)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    ws.row_dimensions[1].height = 26
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(name=FUENTE, size=9.5, italic=True, color=MUTED)
        ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
        ws.row_dimensions[2].height = 46


def section(ws, row, text, span=8):
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(name=FUENTE, size=10, bold=True, color=WHITE)
    for i in range(1, span + 1):
        ws.cell(row=row, column=i).fill = PatternFill("solid", fgColor=TEAL)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)


def header(ws, row, values, start=1):
    for i, v in enumerate(values):
        c = ws.cell(row=row, column=start + i, value=v)
        c.font = Font(name=FUENTE, size=9.5, bold=True, color=FOREST)
        c.fill = PatternFill("solid", fgColor=SAND)
        c.border = BOX
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[row].height = 28


def widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


def nota(ws, row, texto_, span=8, alto=3, color=MUTED):
    c = ws.cell(row=row, column=1, value=texto_)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    c.font = Font(name=FUENTE, size=9.5, color=color)
    ws.merge_cells(start_row=row, start_column=1, end_row=row + alto - 1, end_column=span)
    return row + alto + 1


def rotulo(ws, row, texto_, color=FOREST, size=10):
    ws.cell(row=row, column=1, value=texto_).font = Font(
        name=FUENTE, size=size, bold=True, color=color)


def dato(ws, row, col, valor, fmt=None, *, editable=False, fuerte=False,
         naranja=False, size=None):
    c = ws.cell(row=row, column=col, value=valor)
    if fmt:
        c.number_format = fmt
    c.border = BOX
    c.font = Font(name=FUENTE, size=size or (12 if fuerte else 10), bold=fuerte,
                  color=INPUT if editable else (FOREST if fuerte else CALC))
    if naranja:
        c.fill = PatternFill("solid", fgColor=NARANJA)
    elif fuerte:
        c.fill = PatternFill("solid", fgColor=CREAM)
    return c


def txt(ws, row, col, valor, size=9.5, color=MUTED, wrap=False, bold=False):
    c = ws.cell(row=row, column=col, value=valor)
    c.font = Font(name=FUENTE, size=size, bold=bold, color=color)
    if wrap:
        c.alignment = Alignment(wrap_text=True, vertical="top")
    return c


# ==========================================================================
# 3. SUPUESTOS  (se escribe primero: todo lo demas apunta aqui)
# ==========================================================================
S = "Supuestos"
ref = {}        # clave -> "Supuestos!$B$41"
plan_row = {}   # clave -> numero de fila; columnas B/C/D = Autonomo/Negocio/Premium


def construir_supuestos():
    ws = hoja(S, FOREST)
    title(ws, "Supuestos",
          "Celdas azules = entradas editables; cambiarlas recalcula todo el libro. Cada "
          "driver lleva fecha y origen. SUPUESTO en ambar significa que la cifra no esta "
          "medida: es una decision de planificacion, no un dato de la empresa. Con cero "
          "clientes de pago, casi todo lo de abajo es una hipotesis.", 6)
    widths(ws, {"A": 42, "B": 15, "C": 15, "D": 15, "E": 17, "F": 58})

    fila = 4
    section(ws, fila, "1 · Por plan — que incluye y cuanto se usa", 6)
    fila += 1
    header(ws, fila, ["Driver", "Autonomo", "Negocio", "Premium", "Unidad",
                      "Fuente / criterio"])
    fila += 1
    planes = [
        ("precio_ant", "Precio anterior", "€/mes + IVA",
         "Catalogo de antes del analisis. Solo sirve para comparar", EUR),
        ("precio", "Precio adoptado", "€/mes + IVA",
         "DATO: decision del 15/07/2026; coincide con el catalogo del codigo", EUR),
        ("mix", "Mezcla de clientes", "%",
         "SUPUESTO: nadie ha comprado todavia. Debe sumar 100 %", PCT),
        ("creditos", "Creditos avanzados incluidos", "acciones/mes", "Catalogo actual", NUM),
        ("uso", "Uso esperado del limite", "%", "SUPUESTO conservador", PCT),
        ("interno", "Resuelve el cerebro interno", "%",
         "Objetivo tras el piloto. Si baja del 40 %, el coste de IA se dispara", PCT),
        ("wa_util", "WhatsApp utility enviados", "mensajes/mes", "SUPUESTO operativo", NUM),
        ("wa_serv", "WhatsApp service recibidos", "mensajes/mes",
         "Gratis hoy; queda para la sensibilidad futura", NUM),
        ("audio", "Audio transcrito", "min/mes", "SUPUESTO operativo", NUM),
        ("docs", "Documentos procesados", "docs/mes", "SUPUESTO operativo", NUM),
        ("docs_fuera", "Documentos que escalan fuera", "%", "OCR local primero", PCT),
        ("almacen", "Almacenamiento", "GB/cuenta", "SUPUESTO operativo", '#,##0.00'),
        ("voz", "Voz telefonica incluida", "min/mes",
         "Promesa Premium actual. El piloto dira si se usa", NUM),
        ("soporte", "Soporte de una cuenta asentada", "min/cuenta/mes",
         "SUPUESTO de servicio. Es la partida que rompe el margen", NUM),
        ("onboarding", "Onboarding inicial", "min/cuenta", "Amortizado en 12 meses", NUM),
    ]
    for clave, lab, u, src, fmt in planes:
        plan_row[clave] = fila
        txt(ws, fila, 1, lab, size=10, color=INK)
        for j, v in enumerate(D[clave]):
            dato(ws, fila, 2 + j, v, fmt, editable=True)
        txt(ws, fila, 5, u)
        txt(ws, fila, 6, src, color=WARN if src.startswith("SUPUESTO") else MUTED, wrap=True)
        fila += 1

    mixr = plan_row["mix"]
    aviso = ws.cell(row=fila, column=1, value=(
        f'=IF(ABS(B{mixr}+C{mixr}+D{mixr}-1)>0.0001,'
        f'"AVISO: la mezcla de planes no suma 100 %","Mezcla correcta: suma 100 %")'))
    aviso.font = Font(name=FUENTE, size=10, bold=True, color=WARN)
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=6)
    fila += 2

    bloques = [
        ("2 · Tarifas de proveedores — lo que cobran por usarlos", [
            ("eurusd", "EUR por USD", "EUR/USD", "14/07/2026", "ECB",
             "1 EUR = 1,1405 USD", '0.0000'),
            ("stripe_pay", "Stripe Payments", "% del ingreso", "15/07/2026", "Stripe",
             "Tarjeta EEE estandar", '0.00%'),
            ("stripe_bill", "Stripe Billing", "% del ingreso", "15/07/2026", "Stripe",
             "Facturacion por uso", '0.00%'),
            ("stripe_fijo", "Stripe fijo", "€/transaccion", "15/07/2026", "Stripe",
             "Una renovacion al mes", EUR),
            ("wa_precio", "WhatsApp utility Espana", "€/mensaje", "15/07/2026",
             "Meta / rate card", "Mensaje entregado", '0.0000'),
            ("wa_serv_precio", "WhatsApp service futuro", "€/mensaje", "15/07/2026",
             "Sensibilidad", "Hoy cuesta 0 €", '0.0000'),
            ("haiku", "Haiku 4.5 por interaccion", "USD/interaccion", "15/07/2026",
             "Anthropic", "8k de entrada y 1,2k de salida", '0.0000'),
            ("qwen", "Qwen3 32B por interaccion", "USD/interaccion", "15/07/2026", "Groq",
             "Mismo supuesto de tokens", '0.000000'),
            ("peso_qwen", "Peso de Qwen en el respaldo", "%", "15/07/2026",
             "Arquitectura hibrida", "El resto va a Haiku", PCT0),
            ("whisper", "Whisper Turbo", "USD/hora", "15/07/2026", "Groq",
             "Solo transcripcion", '0.000'),
            ("extraccion", "Extraccion externa de documento", "€/documento",
             "15/07/2026", "SUPUESTO", "Validar con un corpus real", '0.000'),
            ("storage", "Object storage", "USD/GB-mes", "15/07/2026", "Railway",
             "Sin egress", '0.000'),
            ("voz_min", "Voz de agente", "USD/min", "15/07/2026", "Retell",
             "Ejemplo de su calculadora", '0.00'),
            ("voz_num", "Numero telefonico de voz", "USD/mes", "15/07/2026", "Retell",
             "Solo plan Premium", '0.00'),
        ]),
        ("3 · Como se comporta un cliente — nada de esto esta medido", [
            ("churn_nuevo", "Bajas los tres primeros meses", "%/mes", "17/09/2026",
             "SUPUESTO", "Una cartera nueva pierde mas al principio: quien no llega a usarlo "
             "se va pronto", PCT),
            ("churn_maduro", "Bajas a partir del cuarto mes", "%/mes", "17/09/2026",
             "SUPUESTO", "Quien pasa de los tres meses suele quedarse", PCT),
            ("dias_prueba", "Dias de prueba gratis", "dias", "15/07/2026", "Producto",
             "El primer mes de cada alta no se cobra entero", NUM),
            ("impagos", "Recibos que no se cobran", "%", "17/09/2026", "SUPUESTO",
             "Tarjetas caducadas y devoluciones. Se sabra con la primera remesa de Stripe",
             PCT),
            ("pct_anual", "Contratan plan anual", "%", "17/09/2026", "SUPUESTO",
             "El anual adelanta once meses de caja y ahorra comisiones", PCT0),
            ("mult_nueva", "Soporte de una cuenta nueva", "x la asentada", "17/09/2026",
             "SUPUESTO", "Los tres primeros meses preguntan mucho mas: 2,5 veces los minutos",
             '0.0"x"'),
        ]),
        ("4 · Tu tiempo — el limite de verdad en un negocio de una persona", [
            ("horas_mes", "Horas al mes para vender y atender", "h/mes", "17/09/2026",
             "SUPUESTO", "Las que quedan despues de construir producto. Es la palanca que "
             "decide todo lo demas", NUM),
            ("horas_alta", "Horas por alta (venta y puesta en marcha)", "h/alta",
             "17/09/2026", "SUPUESTO", "Demo, alta, primera factura y acompanamiento. El "
             "analisis cifra solo el onboarding en 30-120 min", DEC),
            ("objetivo", "Altas que te gustaria hacer al mes", "altas/mes", "17/09/2026",
             "DECISION", "Tu objetivo comercial. El modelo solo lo cumple si te quedan horas",
             NUM),
            ("crecimiento", "Crecimiento mensual de ese objetivo", "%/mes", "17/09/2026",
             "SUPUESTO", "Boca a boca y prescriptores. Sin ads, es lento", PCT),
            ("hora_soporte", "Coste de una hora de soporte pagada", "€/hora",
             "15/07/2026", "SUPUESTO", "Coste de empresa cargado. Solo aplica cuando el "
             "soporte NO lo haces tu", EUR),
            ("horas_persona", "Horas utiles de una persona a jornada completa", "h/mes",
             "15/07/2026", "SUPUESTO", "Jornada descontando festivos y tareas internas", NUM),
            ("media_jornada", "Coste cargado de media jornada de soporte", "€/mes",
             "17/09/2026", "SUPUESTO", "Sueldo mas seguridad social", EUR0),
        ]),
        ("5 · Estructura de costes fijos — lo que sale de tu bolsillo cada mes", [
            ("plataforma", "Plataforma (Railway, dominio, correo)", "€/mes",
             "17/09/2026", "Founder", "Cifra que escribio el founder en su copia del libro. "
             "PENDIENTE: la factura real", EUR0),
            ("herramientas", "Herramientas y suscripciones", "€/mes", "17/09/2026",
             "SUPUESTO", "IDE, diseno, analitica, almacenamiento", EUR0),
            ("gestoria", "Gestoria", "€/mes", "17/09/2026", "SUPUESTO",
             "PENDIENTE: presupuesto real", EUR0),
            ("seguro", "Seguro y otros fijos", "€/mes", "17/09/2026", "SUPUESTO",
             "Responsabilidad civil. PENDIENTE", EUR0),
            ("ads", "Presupuesto de captacion", "€/mes", "17/09/2026", "DECISION",
             "A cero, captas solo con tu tiempo. Enlaza con la hoja Ads_Captacion", EUR0),
        ]),
    ]
    for titulo_bloque, drivers in bloques:
        section(ws, fila, titulo_bloque, 6)
        fila += 1
        header(ws, fila, ["Driver", "Valor", "Unidad", "Fecha", "Origen", "Nota"])
        fila += 1
        for clave, lab, u, fecha, src, n, fmt in drivers:
            ref[clave] = f"{S}!$B${fila}"
            txt(ws, fila, 1, lab, size=10, color=INK)
            dato(ws, fila, 2, D[clave], fmt, editable=True)
            txt(ws, fila, 3, u)
            txt(ws, fila, 4, fecha)
            duro = src in ("SUPUESTO", "DECISION", "PENDIENTE")
            txt(ws, fila, 5, src, color=WARN if duro else MUTED, bold=duro)
            txt(ws, fila, 6, n, wrap=True)
            fila += 1
        fila += 1

    est_ini = int(ref["plataforma"].rsplit("$", 1)[-1])
    est_fin = int(ref["ads"].rsplit("$", 1)[-1])

    section(ws, fila, "6 · Lo que hay que cubrir cada mes — los tres niveles", 6)
    fila += 1
    header(ws, fila, ["Nivel", "Valor", "Unidad", "Fecha", "Origen", "Que significa"])
    fila += 1
    ref["estructura"] = f"{S}!$B${fila}"
    txt(ws, fila, 1, "Estructura (sin cuota ni retirada)", size=10, color=INK, bold=True)
    dato(ws, fila, 2, f"=SUM(B{est_ini}:B{est_fin})", EUR0, fuerte=True)
    txt(ws, fila, 3, "€/mes")
    txt(ws, fila, 6, "El minimo que pagas aunque no cobres nada", wrap=True)
    fila += 1
    for clave, lab, fecha, src, n in [
        ("cuota_autonomos", "Cuota de autonomos", "17/09/2026", "PENDIENTE",
         "Depende de tarifa plana y de la forma juridica, sin decidir"),
        ("retirada", "Lo que quieres cobrar tu al mes", "17/09/2026", "DECISION",
         "La cifra que convierte esto en un trabajo y no en un hobby"),
    ]:
        ref[clave] = f"{S}!$B${fila}"
        txt(ws, fila, 1, lab, size=10, color=INK)
        dato(ws, fila, 2, D[clave], EUR0, editable=True)
        txt(ws, fila, 3, "€/mes")
        txt(ws, fila, 4, fecha)
        txt(ws, fila, 5, src, color=WARN, bold=True)
        txt(ws, fila, 6, n, wrap=True)
        fila += 1
    ref["salida_total"] = f"{S}!$B${fila}"
    txt(ws, fila, 1, "Salida total de caja al mes", size=10, color=INK, bold=True)
    dato(ws, fila, 2, f"={ref['estructura']}+{ref['cuota_autonomos']}+{ref['retirada']}",
         EUR0, fuerte=True)
    txt(ws, fila, 3, "€/mes")
    txt(ws, fila, 6, "Estructura, cuota y tu retirada. Sustituye al opex de 3.500 € del "
                     "libro de agosto, que era una caja negra sin desglosar", wrap=True)
    fila += 1
    ref["caja_inicial"] = f"{S}!$B${fila}"
    txt(ws, fila, 1, "Caja inicial", size=10, color=INK)
    dato(ws, fila, 2, D["caja_inicial"], EUR0, editable=True)
    txt(ws, fila, 3, "€")
    txt(ws, fila, 4, "17/09/2026")
    txt(ws, fila, 5, "PENDIENTE", color=WARN, bold=True)
    txt(ws, fila, 6, "El vault cita ~4.000 € iniciales. Confirmar", wrap=True)
    fila += 2

    section(ws, fila, "7 · Captacion y canal — propuesta del 16/09/2026, sin aprobar", 6)
    fila += 1
    header(ws, fila, ["Driver", "Valor", "Unidad", "Fecha", "Origen", "Nota"])
    fila += 1
    for clave, lab, u, src, n, fmt in [
        ("cac", "Coste de captar un cliente (CAC)", "€/cliente", "SUPUESTO",
         "Sin campanas medidas. Validar durante el piloto", EUR0),
        ("implantacion", "Cuota de implantacion", "€/alta", "PROPUESTA",
         "Perdonada en contratacion anual. Nada aprobado todavia", EUR0),
        ("pct_implantacion", "Altas que la pagan", "%", "DECISION",
         "A 0 % el libro se comporta como si la cuota no existiera: es el valor honesto "
         "mientras no este aprobada", PCT0),
        ("com_alta", "Comision al alta", "mensualidades", "PROPUESTA",
         "Estructura D: una mensualidad al firmar", DEC),
        ("com_recurrente", "Comision recurrente", "% de la cuota", "PROPUESTA",
         "Estructura D: 10 % durante doce meses", PCT0),
        ("com_meses", "Meses de comision recurrente", "meses", "PROPUESTA",
         "Si la cuenta se va antes del cuarto mes, la mensualidad se descuenta", NUM),
        ("pct_canal", "Altas que entran por canal", "%", "DECISION",
         "A 0 % vendes tu. Ningun comercial antes del piloto", PCT0),
        ("coste_comercial", "Coste cargado de un comercial", "€/mes", "SUPUESTO",
         "Sueldo, seguridad social y estructura", EUR0),
    ]:
        ref[clave] = f"{S}!$B${fila}"
        txt(ws, fila, 1, lab, size=10, color=INK)
        dato(ws, fila, 2, D[clave], fmt, editable=True)
        txt(ws, fila, 3, u)
        txt(ws, fila, 4, "16/09/2026")
        txt(ws, fila, 5, src, color=WARN, bold=True)
        txt(ws, fila, 6, n, wrap=True)
        fila += 1
    fila += 1

    section(ws, fila, "8 · Fiscal y reparto", 6)
    fila += 1
    header(ws, fila, ["Driver", "Valor", "Unidad", "Fecha", "Origen", "Nota"])
    fila += 1
    for clave, lab, u, fecha, src, n, fmt in [
        ("iva", "IVA Espana", "%", "15/07/2026", "AEAT",
         "El precio se comunica + IVA. No entra en el resultado: se repercute y se ingresa",
         PCT0),
        ("cuentas_fijo", "Cuentas para repartir la plataforma", "cuentas", "15/07/2026",
         "Escenario", "Solo sirve para ver el fijo por cuenta en Unit_Economics; el "
         "equilibrio usa la estructura entera, no este reparto", NUM),
    ]:
        ref[clave] = f"{S}!$B${fila}"
        txt(ws, fila, 1, lab, size=10, color=INK)
        dato(ws, fila, 2, D[clave], fmt, editable=True)
        txt(ws, fila, 3, u)
        txt(ws, fila, 4, fecha)
        txt(ws, fila, 5, src)
        txt(ws, fila, 6, n, wrap=True)
        fila += 1

    nota(ws, fila + 1,
         "Este libro no incluye IVA: se repercute y se ingresa, asi que no es ni ingreso ni "
         "gasto, solo un desfase de caja que la gestoria ordena por trimestres. Tampoco "
         "incluye IRPF ni impuesto de sociedades: con resultado negativo no hay base, y "
         "cuando la haya la cifra depende de la forma juridica, que sigue sin decidir.",
         span=6, color=WARN)
    ws.freeze_panes = "A6"


construir_supuestos()

P = ["B", "C", "D"]
UE = "Unit_Economics"
UE_PRECIO, UE_COGS, UE_MB = 5, 13, 14
UE_SOPORTE, UE_ONB, UE_FIJO = 15, 16, 17
UE_CARGADA, UE_MCARGADA = 18, 19
UE_COBRADO, UE_CAJA, UE_MCAJA = 20, 21, 22
UE_MIN, UE_VIDA, UE_LTV = 27, 28, 29
UE_ARPU, UE_COGSM, UE_SERVM, UE_CAJAM, UE_CARGM, UE_MINM = 32, 33, 34, 35, 36, 37


# ==========================================================================
# 4. UNIT ECONOMICS
# ==========================================================================
def construir_unit_economics():
    ws = hoja(UE)
    title(ws, "Unit economics por plan",
          "Escenario hibrido: el cerebro interno resuelve el 60 %; del resto, 80 % Qwen y "
          "20 % Haiku. Columnas B-D = catalogo anterior (29/39/79); columnas E-G = catalogo "
          "adoptado (29/49/99). Esta hoja es lo que este libro tiene y los otros dos no: el "
          "coste sale de los drivers uno a uno, no de un total copiado.")
    widths(ws, {"A": 40, "B": 13, "C": 13, "D": 13, "E": 13, "F": 13, "G": 13, "H": 12})
    header(ws, 4, ["Metrica", "Autonomo ant.", "Negocio ant.", "Premium ant.",
                   "Autonomo adop.", "Negocio adop.", "Premium adop.", "Unidad"])

    metrics = {
        UE_PRECIO: ("Precio de catalogo", EUR, "€/mes"),
        6: ("Stripe", EUR, "€/mes"),
        7: ("WhatsApp utility", EUR, "€/mes"),
        8: ("IA avanzada", EUR, "€/mes"),
        9: ("Transcripcion", EUR, "€/mes"),
        10: ("Extraccion externa", EUR, "€/mes"),
        11: ("Almacenamiento", EUR, "€/mes"),
        12: ("Voz Premium", EUR, "€/mes"),
        UE_COGS: ("COGS software", EUR, "€/mes"),
        UE_MB: ("Margen bruto software", PCT, "%"),
        UE_SOPORTE: ("Soporte humano, SI lo paga alguien", EUR, "€/mes"),
        UE_ONB: ("Onboarding amortizado, SI lo paga alguien", EUR, "€/mes"),
        UE_FIJO: ("Plataforma asignada por cuenta", EUR, "€/mes"),
        UE_CARGADA: ("CONTRIBUCION CARGADA (soporte pagado)", EUR, "€/mes"),
        UE_MCARGADA: ("Margen de contribucion cargada", PCT, "%"),
        UE_COBRADO: ("Precio realmente cobrado (tras impagos)", EUR, "€/mes"),
        UE_CAJA: ("CONTRIBUCION EN CAJA (atiendes tu)", EUR, "€/mes"),
        UE_MCAJA: ("Margen de contribucion en caja", PCT, "%"),
        23: ("Ingreso si el precio incluyera IVA", EUR, "€/mes"),
        24: ("Contribucion en caja si incluyera IVA", EUR, "€/mes"),
        25: ("IA en el peor caso: 100 % Haiku", EUR, "€/mes"),
        26: ("Margen bruto en el peor caso de IA", PCT, "%"),
        UE_MIN: ("Minutos de soporte al mes", NUM, "min/mes"),
        UE_VIDA: ("Vida media del cliente", DEC, "meses"),
        UE_LTV: ("LTV sobre contribucion en caja", EUR, "€"),
    }
    for r, (lab, fmt, u) in metrics.items():
        c = txt(ws, r, 1, lab, size=10, color=INK)
        if r in (UE_COGS, UE_CARGADA, UE_CAJA):
            c.font = Font(name=FUENTE, size=10, bold=True, color=FOREST)
        txt(ws, r, 8, u)

    pr = plan_row
    for j in range(6):
        col = get_column_letter(2 + j)
        ac = P[j % 3]
        precio_row = pr["precio_ant"] if j < 3 else pr["precio"]
        F = {
            UE_PRECIO: f"='{S}'!{ac}${precio_row}",
            6: (f"={col}{UE_PRECIO}*({ref['stripe_pay']}+{ref['stripe_bill']})"
                f"+{ref['stripe_fijo']}"),
            7: f"='{S}'!{ac}${pr['wa_util']}*{ref['wa_precio']}",
            8: (f"='{S}'!{ac}${pr['creditos']}*'{S}'!{ac}${pr['uso']}"
                f"*(1-'{S}'!{ac}${pr['interno']})"
                f"*({ref['peso_qwen']}*{ref['qwen']}+(1-{ref['peso_qwen']})*{ref['haiku']})"
                f"*{ref['eurusd']}"),
            9: f"='{S}'!{ac}${pr['audio']}/60*{ref['whisper']}*{ref['eurusd']}",
            10: f"='{S}'!{ac}${pr['docs']}*'{S}'!{ac}${pr['docs_fuera']}*{ref['extraccion']}",
            11: f"='{S}'!{ac}${pr['almacen']}*{ref['storage']}*{ref['eurusd']}",
            12: (f"=IF('{S}'!{ac}${pr['voz']}>0,'{S}'!{ac}${pr['voz']}*{ref['voz_min']}"
                 f"*{ref['eurusd']}+{ref['voz_num']}*{ref['eurusd']},0)"),
            UE_COGS: f"=SUM({col}6:{col}12)",
            UE_MB: f"=({col}{UE_PRECIO}-{col}{UE_COGS})/{col}{UE_PRECIO}",
            UE_SOPORTE: f"='{S}'!{ac}${pr['soporte']}/60*{ref['hora_soporte']}",
            UE_ONB: f"='{S}'!{ac}${pr['onboarding']}/60*{ref['hora_soporte']}/12",
            UE_FIJO: f"={ref['plataforma']}/{ref['cuentas_fijo']}",
            UE_CARGADA: f"={col}{UE_COBRADO}-{col}{UE_COGS}-{col}{UE_SOPORTE}-{col}{UE_ONB}",
            UE_MCARGADA: f"={col}{UE_CARGADA}/{col}{UE_PRECIO}",
            UE_COBRADO: f"={col}{UE_PRECIO}*(1-{ref['impagos']})",
            UE_CAJA: f"={col}{UE_COBRADO}-{col}{UE_COGS}",
            UE_MCAJA: f"={col}{UE_CAJA}/{col}{UE_PRECIO}",
            23: f"={col}{UE_PRECIO}/(1+{ref['iva']})",
            24: f"={col}23*(1-{ref['impagos']})-{col}{UE_COGS}",
            25: f"='{S}'!{ac}${pr['creditos']}*{ref['haiku']}*{ref['eurusd']}",
            26: f"=({col}{UE_PRECIO}-({col}{UE_COGS}-{col}8+{col}25))/{col}{UE_PRECIO}",
            UE_MIN: f"='{S}'!{ac}${pr['soporte']}",
            UE_VIDA: (f"=1+(1-{ref['churn_nuevo']})+(1-{ref['churn_nuevo']})^2"
                      f"+(1-{ref['churn_nuevo']})^3/{ref['churn_maduro']}"),
            UE_LTV: f"={col}{UE_CAJA}*{col}{UE_VIDA}",
        }
        for r, f in F.items():
            fuerte = r in (UE_COGS, UE_CARGADA, UE_CAJA)
            c = dato(ws, r, 2 + j, f, metrics[r][1], fuerte=fuerte)
            if fuerte:
                c.font = Font(name=FUENTE, size=10, bold=True, color=FOREST)
            if r in (UE_MB, UE_MCARGADA, UE_MCAJA):
                c.font = Font(name=FUENTE, size=10, bold=True, color=FOREST)

    section(ws, UE_ARPU - 1, "Media ponderada con la mezcla actual (catalogo adoptado)", 8)
    mixr = pr["mix"]
    medias = [
        (UE_ARPU, "Cuota media (ARPU)", UE_PRECIO, EUR,
         "Precio de cada plan por su peso en la mezcla"),
        (UE_COGSM, "COGS medio por cuenta", UE_COGS, EUR,
         "Lo que cuesta en dinero servir una cuenta media"),
        (UE_SERVM, "Soporte y onboarding medios", None, EUR,
         "Solo es gasto si ese soporte lo paga alguien que no eres tu"),
        (UE_CAJAM, "CONTRIBUCION MEDIA EN CAJA", UE_CAJA, EUR,
         "La que manda mientras atiendes tu: tu tiempo entra como capacidad, no como gasto"),
        (UE_CARGM, "CONTRIBUCION MEDIA CARGADA", UE_CARGADA, EUR,
         "La que manda en cuanto el soporte lo paga alguien"),
        (UE_MINM, "Minutos de soporte por cuenta", UE_MIN, DEC,
         "Ponderados por la mezcla. El libro v3 uso los 12 min del plan Autonomo para toda "
         "la cartera; con 35 % de Negocio y 10 % de Premium salen mas"),
    ]
    for r, lab, origen, fmt, explic in medias:
        txt(ws, r, 1, lab, size=10, color=INK, bold=r in (UE_CAJAM, UE_CARGM))
        if origen is None:
            f = (f"=SUMPRODUCT(E{UE_SOPORTE}:G{UE_SOPORTE},'{S}'!B{mixr}:D{mixr})"
                 f"+SUMPRODUCT(E{UE_ONB}:G{UE_ONB},'{S}'!B{mixr}:D{mixr})")
        else:
            f = f"=SUMPRODUCT(E{origen}:G{origen},'{S}'!B{mixr}:D{mixr})"
        dato(ws, r, 2, f, fmt, fuerte=r in (UE_CAJAM, UE_CARGM))
        txt(ws, r, 3, explic, wrap=True)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=8)

    nota(ws, UE_MINM + 2,
         "Las dos contribuciones no son dos opiniones: son dos negocios distintos. Mientras "
         "el founder atiende, su tiempo no sale de la caja y la buena es la contribucion EN "
         "CAJA; lo que limita entonces no es el margen sino las horas, y eso lo mide la hoja "
         "Horas_del_founder. En cuanto ese soporte lo paga alguien, la buena es la CARGADA. "
         "El libro de agosto usaba la cargada y ademas metia una retirada del founder en el "
         "opex: contaba su tiempo dos veces y por eso el equilibrio salia optimista.")
    ws.freeze_panes = "B5"


construir_unit_economics()

M_ARPU = f"'{UE}'!$B${UE_ARPU}"
M_COGS = f"'{UE}'!$B${UE_COGSM}"
M_SERV = f"'{UE}'!$B${UE_SERVM}"
M_CAJA = f"'{UE}'!$B${UE_CAJAM}"
M_CARG = f"'{UE}'!$B${UE_CARGM}"
M_MIN = f"'{UE}'!$B${UE_MINM}"
M_VIDA = f"'{UE}'!$E${UE_VIDA}"

HF = "Horas_del_founder"
HF_TECHO, HF_PRACTICO = 9, 10
RAMPA = "Rampa_36m"
R_MES, R_CAJAMIN, R_CUENTAS, R_AHOGO = 6, 7, 8, 9
R_INI = 12
R_FIN = R_INI + 35
BE = "Escala_Breakeven"
BE_RETIRADA = 8


# ==========================================================================
# 5. ESCALA Y BREAK-EVEN
# ==========================================================================
def construir_breakeven():
    ws = hoja(BE)
    title(ws, "Los tres equilibrios",
          "El libro de agosto daba una sola cifra —120 cuentas con 3.500 € de opex— y al "
          "cambiar el opex a 500 € daba 17, que describe un negocio donde nadie cobra. No "
          "hay un equilibrio: hay tres, y solo el tercero significa que esto te da de comer.")
    widths(ws, {"A": 46, "B": 15, "C": 17, "D": 14, "E": 16, "F": 46})

    section(ws, 4, "Los tres niveles", 6)
    header(ws, 5, ["Nivel", "Coste mensual", "Contribucion usada", "Cuentas necesarias",
                   "Ingreso cobrado en ese punto", "Que significa"])
    niveles = [
        ("Cubrir solo la estructura", ref["estructura"], M_CAJA,
         "Servidores, herramientas, gestoria y seguro. No cobras nada."),
        ("Cubrir estructura y cuota de autonomos", f"{ref['estructura']}+{ref['cuota_autonomos']}",
         M_CAJA, "El minimo para no poner dinero de tu bolsillo cada mes. Sigues sin cobrar."),
        ("EL EQUILIBRIO DE VERDAD: ademas te pagas la retirada", ref["salida_total"], M_CAJA,
         "Cuando esto deja de ser un hobby. Es la cifra que hay que mirar."),
        ("El mismo, pero con el soporte pagado a otra persona", ref["salida_total"], M_CARG,
         "Cuando ya no atiendes tu. La contribucion baja y el equilibrio sube."),
    ]
    for i, (lab, coste, base, explic) in enumerate(niveles):
        r = 6 + i
        fuerte = i == 2
        txt(ws, r, 1, lab, size=10, color=FOREST if fuerte else INK, bold=fuerte)
        dato(ws, r, 2, f"={coste}", EUR0)
        dato(ws, r, 3, f"={base}", EUR)
        dato(ws, r, 4, f'=IF(C{r}<=0,"-",ROUNDUP(B{r}/C{r},0))', NUM, fuerte=fuerte)
        dato(ws, r, 5, f'=IF(C{r}<=0,"-",D{r}*{M_ARPU}*(1-{ref["impagos"]}))', EUR0)
        txt(ws, r, 6, explic, wrap=True)
    assert 6 + 2 == BE_RETIRADA, "la fila del equilibrio de verdad se ha movido"

    section(ws, 11, "¿Cabe ese equilibrio en tus horas?", 6)
    header(ws, 12, ["Metrica", "Valor", "", "Unidad", "", "Lectura"])
    horas_check = [
        ("Cuentas del equilibrio de verdad", f"=D{BE_RETIRADA}", NUM, "cuentas",
         "De la tabla de arriba"),
        ("Horas de soporte que exigen al mes", f"=B13*{M_MIN}/60", DEC, "h/mes",
         "Con los minutos medios ponderados por la mezcla"),
        ("Horas que te quedan para vender", f"={ref['horas_mes']}-B14", DEC, "h/mes",
         "Lo que sobra despues de atender a esa cartera"),
        ("Altas que puedes cerrar con ese resto", f"=ROUNDDOWN(MAX(0,B15)/{ref['horas_alta']},0)",
         NUM, "altas/mes", "A las horas por alta del panel de supuestos"),
        ("Veredicto", '=IF(B15<=0,"NO: esa cartera te ocupa el mes entero y no podrias ni '
                      'venderla",IF(B15<'
                      f'{ref["horas_mes"]}*0.3,"JUSTO: llegarias, pero sin margen para vender",'
                      '"SI: cabe en tus horas con sitio para seguir vendiendo"))', None, "",
         "Compara el equilibrio con tu capacidad real"),
    ]
    for i, (lab, f, fmt, u, lec) in enumerate(horas_check):
        r = 13 + i
        fuerte = lab == "Veredicto"
        txt(ws, r, 1, lab, size=10, color=INK)
        c = dato(ws, r, 2, f, fmt, fuerte=fuerte)
        if fuerte:
            c.font = Font(name=FUENTE, size=11, bold=True, color=FOREST)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        txt(ws, r, 4, u)
        txt(ws, r, 6, lec, wrap=True)
    ws.conditional_formatting.add("B17", FormulaRule(
        formula=['ISNUMBER(SEARCH("NO:",$B$17))'],
        font=Font(name=FUENTE, size=11, bold=True, color=STOP)))

    section(ws, 19, "Escala: que pasa segun el tamano de la cartera", 8)
    header(ws, 20, ["Cuentas", "Ingreso cobrado", "Contribucion en caja", "Salida de caja",
                    "Resultado", "Margen", "Horas de soporte", "Situacion"])
    filas_escala = [10, 25, 44, 50, 75, 100, 150, 200, 300, 500, 1000]
    for i, n in enumerate(filas_escala):
        r = 21 + i
        dato(ws, r, 1, n, NUM, editable=True)
        dato(ws, r, 2, f"=A{r}*{M_ARPU}*(1-{ref['impagos']})", EUR0)
        dato(ws, r, 3, f"=A{r}*{M_CAJA}", EUR0)
        dato(ws, r, 4, f"={ref['salida_total']}", EUR0)
        dato(ws, r, 5, f"=C{r}-D{r}", EUR0)
        dato(ws, r, 6, f'=IF(B{r}>0,E{r}/B{r},"")', PCT)
        dato(ws, r, 7, f"=A{r}*{M_MIN}/60", DEC)
        c = dato(ws, r, 8, f'=IF(G{r}>{ref["horas_mes"]},"Imposible tu solo: el soporte pasa '
                           f'de tus horas",IF(G{r}>{ref["horas_mes"]}*0.7,"Al limite: el '
                           f'soporte se come el mes",IF(G{r}>{ref["horas_mes"]}*0.4,"Creces '
                           f'despacio","Tienes margen para vender")))')
        c.font = Font(name=FUENTE, size=9.5, color=MUTED)
    ws.conditional_formatting.add(f"E21:E{20 + len(filas_escala)}", CellIsRule(
        operator="lessThan", formula=["0"], font=Font(color=STOP, bold=True)))
    ws.conditional_formatting.add(f"E21:E{20 + len(filas_escala)}", CellIsRule(
        operator="greaterThanOrEqual", formula=["0"], font=Font(color=OKC, bold=True)))

    base = 21 + len(filas_escala) + 1
    section(ws, base, "Cuantos clientes de cada plan hacen falta en el equilibrio", 6)
    header(ws, base + 1, ["Plan", "Mezcla", "Clientes", "Precio", "Ingreso mensual",
                          "Contribucion en caja"])
    for i, (nombre, scol, ucol) in enumerate([("Autonomo", "B", "E"), ("Negocio", "C", "F"),
                                              ("Premium", "D", "G")]):
        r = base + 2 + i
        txt(ws, r, 1, nombre, size=10, color=INK)
        dato(ws, r, 2, f"='{S}'!{scol}{plan_row['mix']}", PCT)
        dato(ws, r, 3, f"=ROUND($D${BE_RETIRADA}*B{r},0)", NUM, fuerte=True)
        dato(ws, r, 4, f"='{S}'!{scol}{plan_row['precio']}", EUR0)
        dato(ws, r, 5, f"=C{r}*D{r}", EUR0)
        dato(ws, r, 6, f"=C{r}*'{UE}'!{ucol}{UE_CAJA}", EUR0)
    rt = base + 5
    txt(ws, rt, 1, "TOTAL", size=10, color=FOREST, bold=True)
    for col, fmt in (("B", PCT), ("C", NUM), ("E", EUR0), ("F", EUR0)):
        idx = {"B": 2, "C": 3, "E": 5, "F": 6}[col]
        dato(ws, rt, idx, f"=SUM({col}{base + 2}:{col}{base + 4})", fmt, fuerte=True)

    b2 = rt + 2
    section(ws, b2, "Y si toda la cartera fuera de un solo plan", 6)
    header(ws, b2 + 1, ["Plan", "Contribucion en caja", "Clientes para el equilibrio",
                        "Ingreso mensual", "", ""])
    for i, (nombre, scol, ucol) in enumerate([("Autonomo", "B", "E"), ("Negocio", "C", "F"),
                                              ("Premium", "D", "G")]):
        r = b2 + 2 + i
        txt(ws, r, 1, nombre, size=10, color=INK)
        dato(ws, r, 2, f"='{UE}'!{ucol}{UE_CAJA}", EUR)
        dato(ws, r, 3, f'=IFERROR(ROUNDUP({ref["salida_total"]}/B{r},0),"")', NUM, fuerte=True)
        dato(ws, r, 4, f'=IFERROR(C{r}*\'{S}\'!{scol}{plan_row["precio"]},"")', EUR0)

    nota(ws, b2 + 6,
         "Leer las tres tablas juntas. La primera dice cuanto hay que cubrir y con que "
         "contribucion; la segunda, cuantos clientes de cada plan lo componen; la tercera, "
         "cuantos harian falta vendiendo un solo plan. La distancia entre ellas es el valor "
         "real de vender el plan caro, y es toda la conversacion comercial en una cifra. Lo "
         "que ninguna dice es cuantos meses cuesta llegar: eso esta en Rampa_36m.", span=6)


construir_breakeven()


# ==========================================================================
# 6. VIDA Y LTV
# ==========================================================================
def construir_vida():
    ws = hoja("Vida_y_LTV")
    title(ws, "Cuanto dura un cliente y cuanto deja",
          "Sin bajas no hay vida media, y sin vida media no hay LTV: el libro de agosto "
          "describia un cliente que se queda para siempre. Aqui la vida se calcula con dos "
          "tramos —los tres primeros meses se va mas gente— en vez de con un churn plano, "
          "que es como se comporta de verdad una cartera nueva.", 7)
    widths(ws, {"A": 22, "B": 16, "C": 16, "D": 16, "E": 14, "F": 16, "G": 44})

    section(ws, 4, "Con los supuestos del panel", 7)
    header(ws, 5, ["Metrica", "Valor", "Unidad", "", "", "", "Como se calcula"])
    vivos = [
        ("Bajas los tres primeros meses", f"={ref['churn_nuevo']}", PCT, "%/mes"),
        ("Bajas despues", f"={ref['churn_maduro']}", PCT, "%/mes"),
        ("Vida media resultante", f"={M_VIDA}", DEC, "meses"),
        ("LTV en caja", f"={M_CAJA}*{M_VIDA}", EUR, "€"),
        ("LTV cargada", f"={M_CARG}*{M_VIDA}", EUR, "€"),
        ("LTV / CAC (en caja)", f'=IF({ref["cac"]}<=0,"-",B9/{ref["cac"]})', '0.0"x"', "veces"),
        ("Meses para recuperar el CAC", f'=IF({M_CAJA}<=0,"-",{ref["cac"]}/{M_CAJA})', DEC,
         "meses"),
    ]
    explicaciones = [
        "Del panel de supuestos.",
        "Del panel de supuestos.",
        "Suma de la supervivencia mes a mes: 1 + 0,92 + 0,92² + 0,92³/0,04. Con un "
        "churn plano del 4 % saldrian 25 meses; con dos tramos, menos.",
        "Contribucion en caja por la vida media. No es facturacion: es lo que deja.",
        "La misma cuenta con el soporte pagado a otra persona.",
        "Referencia habitual en SaaS: 3x o mas.",
        "Payback. Por encima de 12 meses la caja sufre aunque el LTV sea bueno.",
    ]
    for i, (lab, f, fmt, u) in enumerate(vivos):
        r = 6 + i
        fuerte = lab in ("Vida media resultante", "LTV en caja", "LTV / CAC (en caja)")
        txt(ws, r, 1, lab, size=10, color=INK)
        dato(ws, r, 2, f, fmt, fuerte=fuerte)
        txt(ws, r, 3, u)
        txt(ws, r, 7, explicaciones[i], wrap=True)
    ws.conditional_formatting.add("B11", CellIsRule(
        operator="lessThan", formula=["3"], font=Font(bold=True, color=STOP)))
    ws.conditional_formatting.add("B11", CellIsRule(
        operator="greaterThanOrEqual", formula=["3"], font=Font(bold=True, color=OKC)))

    section(ws, 14, "Y si las bajas fueran otras", 7)
    header(ws, 15, ["Bajas despues del 3er mes", "Vida media", "LTV en caja", "LTV cargada",
                    "LTV / CAC", "Recupera el CAC en", "Lectura"])
    tasas = [0.02, 0.03, 0.04, 0.05, 0.08, 0.10]
    for i, tasa in enumerate(tasas):
        r = 16 + i
        marca = abs(tasa - D["churn_maduro"]) < 1e-9
        dato(ws, r, 1, tasa, PCT, editable=True)
        dato(ws, r, 2, f"=1+(1-{ref['churn_nuevo']})+(1-{ref['churn_nuevo']})^2"
                       f"+(1-{ref['churn_nuevo']})^3/A{r}", DEC)
        dato(ws, r, 3, f"={M_CAJA}*B{r}", EUR)
        dato(ws, r, 4, f"={M_CARG}*B{r}", EUR)
        dato(ws, r, 5, f'=IF({ref["cac"]}<=0,"-",C{r}/{ref["cac"]})', '0.0"x"')
        dato(ws, r, 6, f'=IF({M_CAJA}<=0,"-",{ref["cac"]}/{M_CAJA})', DEC)
        c = dato(ws, r, 7, f'=IF(E{r}="","",IF(E{r}>=3,"Sostenible",IF(E{r}>=1,"Justo: el '
                           f'cliente apenas paga su captacion","Cada alta destruye valor")))')
        c.font = Font(name=FUENTE, size=9.5, bold=marca, color=FOREST if marca else MUTED)
        if marca:
            for col in range(1, 8):
                ws.cell(row=r, column=col).fill = PatternFill("solid", fgColor=CREAM)
    ws.conditional_formatting.add(f"E16:E{15 + len(tasas)}", CellIsRule(
        operator="lessThan", formula=["3"], font=Font(color=STOP)))

    nota(ws, 16 + len(tasas) + 1,
         "Ninguna fila de esta hoja es un dato: no hay todavia clientes de pago que permitan "
         "medir las bajas. El CAC de 150 € aguanta bien salvo con bajas altas, pero tanto "
         "el CAC como las bajas son supuestos. Y ojo con el LTV: describe el valor de un "
         "cliente a lo largo de dos anos, no dinero disponible este mes. La pregunta que "
         "limita de verdad es la caja, y esa la contesta Rampa_36m.", span=7)


construir_vida()


# ==========================================================================
# 7. HORAS DEL FOUNDER
# ==========================================================================
def construir_horas():
    ws = hoja(HF)
    title(ws, "Tu tiempo puesto en numeros",
          "En un negocio de una persona el limite no es el mercado: son las horas. Cada cuenta "
          "nueva consume tiempo de venta y puesta en marcha una vez, y tiempo de soporte todos "
          "los meses. Cuando el soporte se come las horas, no quedan para vender y la cartera "
          "deja de crecer sola — sin que el mercado tenga nada que ver.", 6)
    widths(ws, {"A": 42, "B": 14, "C": 14, "D": 16, "E": 16, "F": 50})

    header(ws, 4, ["Concepto", "Valor", "", "", "", "Nota"])
    base_rows = [
        ("Horas al mes para vender y atender", f"={ref['horas_mes']}", DEC,
         "Del panel de supuestos."),
        ("Soporte de una cuenta asentada", f"={M_MIN}/60", '#,##0.00',
         "Los minutos medios ponderados por la mezcla, pasados a horas."),
        ("Soporte de una cuenta nueva", f"={M_MIN}*{ref['mult_nueva']}/60", '#,##0.00',
         "Los tres primeros meses preguntan mas."),
        ("Horas por alta", f"={ref['horas_alta']}", DEC, "Venta y puesta en marcha."),
        ("Cuentas que llenan tus horas solo con soporte", "=ROUNDDOWN(B5/B6,0)", NUM,
         "El techo absoluto: a partir de aqui no te queda ni una hora para vender."),
        ("Techo practico (soporte al 70 % de tus horas)", "=ROUNDDOWN(B5*0.7/B6,0)", NUM,
         "El punto en el que conviene decidir: o baja el soporte por cuenta, o entra alguien."),
    ]
    for i, (lab, f, fmt, n) in enumerate(base_rows):
        r = 5 + i
        fuerte = r in (HF_TECHO, HF_PRACTICO)
        txt(ws, r, 1, lab, size=10, color=INK, bold=fuerte)
        dato(ws, r, 2, f, fmt, fuerte=fuerte)
        txt(ws, r, 6, n, wrap=True)
    assert 5 + 4 == HF_TECHO and 5 + 5 == HF_PRACTICO, "las filas del techo se han movido"

    section(ws, 12, "Carga segun el tamano de la cartera", 6)
    header(ws, 13, ["Cuentas atendidas", "Horas de soporte", "% de tus horas",
                    "Horas libres para vender", "Altas que puedes cerrar", "Situacion"])
    tramos = [10, 25, 44, 75, 100, 150, 200, 300]
    for i, n in enumerate(tramos):
        r = 14 + i
        dato(ws, r, 1, n, NUM, editable=True)
        dato(ws, r, 2, f"=A{r}*$B$6", DEC)
        dato(ws, r, 3, f'=IF($B$5=0,0,B{r}/$B$5)', PCT)
        dato(ws, r, 4, f"=MAX(0,$B$5-B{r})", DEC)
        dato(ws, r, 5, f'=IF($B$8<=0,0,ROUNDDOWN(D{r}/$B$8,0))', NUM)
        c = dato(ws, r, 6, f'=IF(C{r}>=1,"Ya no puedes vender: solo atiendes",'
                           f'IF(C{r}>=0.7,"Al limite: el soporte se come el mes",'
                           f'IF(C{r}>=0.4,"Creces despacio","Tienes margen para vender")))')
        c.font = Font(name=FUENTE, size=9.5, color=MUTED)
    ws.conditional_formatting.add(f"C14:C{13 + len(tramos)}", CellIsRule(
        operator="greaterThanOrEqual", formula=["0.7"], font=Font(bold=True, color=STOP)))
    ws.conditional_formatting.add(f"C14:C{13 + len(tramos)}", CellIsRule(
        operator="lessThan", formula=["0.4"], font=Font(color=OKC)))

    r0 = 14 + len(tramos) + 1
    r0 = nota(ws, r0,
              "Contratar no resuelve el problema por si solo: una persona de soporte cuesta "
              "desde el primer dia y la cartera crece de una en una. Por eso el margen tiene "
              "que venir de que el soporte por cuenta baje —cerebro local, "
              "autoexplicacion, menos dudas— y no de meter mas gente. Bajar el soporte de "
              "18 a 12 minutos regala mas cuentas que cualquier campana.", span=6)

    section(ws, r0, "Si hay que contratar", 6)
    header(ws, r0 + 1, ["Concepto", "Valor", "", "", "", "Nota"])
    contratar = [
        ("Coste cargado de media jornada", f"={ref['media_jornada']}", EUR0,
         "Media jornada con seguridad social."),
        ("Cuentas extra que hacen falta para pagarla",
         f'=IF({M_CARG}<=0,"-",ROUNDUP({ref["media_jornada"]}/{M_CARG},0))', NUM,
         "Sobre las que ya tengas. La persona no trae clientes: libera horas."),
        ("Horas que aporta media jornada", f"={ref['horas_persona']}/2", DEC,
         "Sobre las horas utiles de una jornada completa del panel."),
        ("Cuentas que esas horas permiten atender", "=ROUNDDOWN(B{0}/$B$6,0)", NUM,
         "Capacidad que compras con ese sueldo."),
    ]
    for i, (lab, f, fmt, n) in enumerate(contratar):
        r = r0 + 2 + i
        if "{0}" in f:
            f = f.format(r - 1)
        fuerte = i == 1
        txt(ws, r, 1, lab, size=10, color=INK)
        dato(ws, r, 2, f, fmt, fuerte=fuerte)
        txt(ws, r, 6, n, wrap=True)

    nota(ws, r0 + 7,
         "Esa cifra es la trampa del crecimiento: el coste entra de golpe y las altas llegan "
         "una a una. Antes de contratar conviene que la cartera pueda pagarlo ya, no que vaya "
         "a poder. Y fijarse en el cambio de contribucion: en cuanto el soporte se paga, la "
         "que manda es la CARGADA y el equilibrio sube de golpe.", span=6, color=WARN)


construir_horas()


# ==========================================================================
# 8. RAMPA 36 MESES
# ==========================================================================
def construir_rampa():
    ws = hoja(RAMPA)
    title(ws, "36 meses: cuatro cohortes y tus horas",
          "Cada mes entran las altas que permiten tus horas libres, no las que te gustaria. "
          "Las cuentas se siguen por edad porque las nuevas se van mas y preguntan mas. La "
          "proyeccion de agosto suponia altas constantes y cero bajas durante dos anos; esta "
          "se frena sola cuando el soporte te ocupa el mes.", 16)
    widths(ws, {"A": 6, "B": 9, "C": 8, "D": 8, "E": 8, "F": 8, "G": 10, "H": 9, "I": 11,
                "J": 12, "K": 12, "L": 12, "M": 12, "N": 12, "O": 13, "P": 13})

    rotulo(ws, 5, "Resumen", size=12)
    resumen = [
        (R_MES, "Mes en que dejas de perder dinero",
         f'=IFERROR(INDEX($A${R_INI}:$A${R_FIN},MATCH(TRUE,INDEX($O${R_INI}:$O${R_FIN}>0,0),0)),'
         f'"no llega en 36 meses")', NUM),
        (R_CAJAMIN, "Caja minima por el camino", f"=MIN($P${R_INI}:$P${R_FIN})", EUR0),
        (R_CUENTAS, "Cuentas al mes 36", f"=$H${R_FIN}", NUM),
        (R_AHOGO, "Mes en que el soporte pasa del 70 % de tus horas",
         f'=IFERROR(INDEX($A${R_INI}:$A${R_FIN},MATCH(TRUE,INDEX($I${R_INI}:$I${R_FIN}>=$F$6*0.7,0),0)),'
         f'"no llega en 36 meses")', NUM),
    ]
    for r, lab, f, fmt in resumen:
        txt(ws, r, 1, lab, size=10, color=INK, bold=True)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        dato(ws, r, 4, f, fmt, fuerte=True)

    # Espejos locales: el formato condicional no puede mirar a otra hoja.
    espejos = [(6, "Horas disponibles", f"={ref['horas_mes']}", DEC),
               (7, "Min. soporte asentada", f"={M_MIN}", DEC),
               (8, "Min. soporte nueva", f"={M_MIN}*{ref['mult_nueva']}", DEC),
               (9, "Horas por alta", f"={ref['horas_alta']}", DEC)]
    for r, lab, f, fmt in espejos:
        txt(ws, r, 5, lab, size=9, color=MUTED)
        c = ws.cell(row=r, column=6, value=f)
        c.number_format = fmt
        c.font = Font(name=FUENTE, size=9, color=MUTED)

    header(ws, 11, ["Mes", "Altas objetivo", "Altas reales", "Mes 1", "Mes 2", "Mes 3",
                    "Asentadas", "Cuentas", "Horas usadas", "Facturado", "Cobrado",
                    "Implantacion", "Comision canal", "Contribucion", "Resultado", "Caja"])
    for mes in range(1, 37):
        f = R_INI + mes - 1
        ant = f - 1
        soporte_previo = ("0" if mes == 1 else
                          f"((D{ant}+E{ant}+F{ant})*$F$8+G{ant}*$F$7)/60")
        recientes = f"SUM(C{max(R_INI, f - 11)}:C{f})"
        celdas = {
            1: (mes, NUM),
            2: (f"=ROUND({ref['objetivo']}*(1+{ref['crecimiento']})^(A{f}-1),0)", NUM),
            3: (f"=MAX(0,MIN(B{f},ROUNDDOWN(MAX(0,$F$6-{soporte_previo})/$F$9,0)))", NUM),
            4: (f"=C{f}", DEC),
            5: ("=0" if mes == 1 else f"=D{ant}*(1-{ref['churn_nuevo']})", DEC),
            6: ("=0" if mes == 1 else f"=E{ant}*(1-{ref['churn_nuevo']})", DEC),
            7: ("=0" if mes == 1 else f"=(G{ant}+F{ant})*(1-{ref['churn_maduro']})", DEC),
            8: (f"=D{f}+E{f}+F{f}+G{f}", DEC),
            9: (f"=C{f}*$F$9+((D{f}+E{f}+F{f})*$F$8+G{f}*$F$7)/60", DEC),
            10: (f"=H{f}*{M_ARPU}-C{f}*{M_ARPU}*{ref['dias_prueba']}/30", EUR0),
            11: (f"=J{f}*(1-{ref['impagos']})", EUR0),
            12: (f"=C{f}*{ref['implantacion']}*{ref['pct_implantacion']}", EUR0),
            13: (f"=-{ref['pct_canal']}*(C{f}*{ref['com_alta']}*{M_ARPU}"
                 f"+{ref['com_recurrente']}*{M_ARPU}*MIN(H{f},{recientes}))", EUR0),
            14: (f"=K{f}+L{f}+M{f}-H{f}*{M_COGS}", EUR0),
            15: (f"=N{f}-{ref['salida_total']}", EUR0),
            16: (f"={ref['caja_inicial']}+O{f}" if mes == 1 else f"=P{ant}+O{f}", EUR0),
        }
        for col, (valor, fmt) in celdas.items():
            c = dato(ws, f, col, valor, fmt)
            if col in (15, 16):
                c.font = Font(name=FUENTE, size=10, bold=True, color=CALC)
            if mes % 12 == 0:
                c.fill = PatternFill("solid", fgColor=CREAM)

    ws.conditional_formatting.add(f"O{R_INI}:P{R_FIN}", CellIsRule(
        operator="lessThan", formula=["0"], font=Font(color=STOP, bold=True)))
    ws.conditional_formatting.add(f"O{R_INI}:P{R_FIN}", CellIsRule(
        operator="greaterThanOrEqual", formula=["0"], font=Font(color=OKC, bold=True)))
    ws.conditional_formatting.add(f"I{R_INI}:I{R_FIN}", CellIsRule(
        operator="greaterThan", formula=["$F$6"], font=Font(color=STOP, bold=True)))
    ws.conditional_formatting.add(f"C{R_INI}:C{R_FIN}", CellIsRule(
        operator="lessThan", formula=[f"B{R_INI}"], font=Font(color=WARN, bold=True)))
    ws.freeze_panes = f"B{R_INI}"

    nota(ws, R_FIN + 2,
         "«Altas reales» en ambar significa que ese mes no cerraste las que querias porque no "
         "te dieron las horas: es el freno del modelo, y es el hallazgo. «Horas usadas» en "
         "rojo significa que ese mes no te dio la vida. «Mes 1/2/3» son las cuentas por edad y "
         "«Asentadas» las que pasaron de tres meses. La caja minima es la cifra que decide si "
         "el proyecto sobrevive: ya incluye la caja inicial. Si resulta negativa, su valor "
         "absoluto es la financiacion adicional necesaria y hay que recortar la "
         "retirada, subir precio o bajar el soporte por cuenta.", span=16)


construir_rampa()


# ==========================================================================
# COMPROBACION EN PYTHON (misma aritmetica que las formulas)
# ==========================================================================
def _cogs_plan(i):
    return (D["precio"][i] * (D["stripe_pay"] + D["stripe_bill"]) + D["stripe_fijo"]
            + D["wa_util"][i] * D["wa_precio"]
            + D["creditos"][i] * D["uso"][i] * (1 - D["interno"][i])
            * (D["peso_qwen"] * D["qwen"] + (1 - D["peso_qwen"]) * D["haiku"]) * D["eurusd"]
            + D["audio"][i] / 60 * D["whisper"] * D["eurusd"]
            + D["docs"][i] * D["docs_fuera"][i] * D["extraccion"]
            + D["almacen"][i] * D["storage"] * D["eurusd"]
            + ((D["voz"][i] * D["voz_min"] + D["voz_num"]) * D["eurusd"]
               if D["voz"][i] > 0 else 0.0))


def _medias():
    mix = D["mix"]
    cogs = [_cogs_plan(i) for i in range(3)]
    arpu = sum(D["precio"][i] * mix[i] for i in range(3))
    cogsm = sum(cogs[i] * mix[i] for i in range(3))
    serv = sum((D["soporte"][i] / 60 * D["hora_soporte"]
                + D["onboarding"][i] / 60 * D["hora_soporte"] / 12) * mix[i] for i in range(3))
    minutos = sum(D["soporte"][i] * mix[i] for i in range(3))
    caja = arpu * (1 - D["impagos"]) - cogsm
    cargada = caja - serv
    return cogs, arpu, cogsm, serv, minutos, caja, cargada


def _rampa(**kw):
    g = dict(D)
    g.update(kw)
    _, arpu, cogsm, _, minutos, _, _ = _medias()
    mix_min = minutos
    min_nueva = mix_min * g["mult_nueva"]
    salida = (g["plataforma"] + g["herramientas"] + g["gestoria"] + g["seguro"] + g["ads"]
              + g["cuota_autonomos"] + g["retirada"])
    c = d = e = f = 0.0
    caja = g["caja_inicial"]
    primero = None
    minima = None
    ahogo = None
    for mes in range(1, 37):
        sop_prev = ((c + d + e) * min_nueva + f * mix_min) / 60 if mes > 1 else 0.0
        libres = max(0.0, g["horas_mes"] - sop_prev)
        objetivo = round(g["objetivo"] * (1 + g["crecimiento"]) ** (mes - 1))
        altas = max(0, min(objetivo, math.floor(libres / g["horas_alta"])))
        c, d, e, f = (altas,
                      c * (1 - g["churn_nuevo"]) if mes > 1 else 0.0,
                      d * (1 - g["churn_nuevo"]) if mes > 1 else 0.0,
                      (f + e) * (1 - g["churn_maduro"]) if mes > 1 else 0.0)
        cuentas = c + d + e + f
        horas = altas * g["horas_alta"] + ((c + d + e) * min_nueva + f * mix_min) / 60
        facturado = cuentas * arpu - altas * arpu * g["dias_prueba"] / 30
        cobrado = facturado * (1 - g["impagos"]) + altas * g["implantacion"] * g["pct_implantacion"]
        resultado = cobrado - cuentas * cogsm - salida
        caja += resultado
        if primero is None and resultado > 0:
            primero = mes
        if ahogo is None and horas >= g["horas_mes"] * 0.7:
            ahogo = mes
        minima = caja if minima is None else min(minima, caja)
    return {"mes": primero, "caja_min": minima, "cuentas": cuentas, "ahogo": ahogo,
            "salida": salida}


ESCENARIOS = {
    "Prudente": dict(objetivo=3, crecimiento=0.02, churn_nuevo=0.12, churn_maduro=0.06,
                     horas_mes=40, mult_nueva=3.75, retirada=1500),
    "Base": {},
    "Optimista": dict(objetivo=8, crecimiento=0.10, churn_nuevo=0.05, churn_maduro=0.02,
                      horas_mes=90, mult_nueva=1.67, retirada=1200),
}
SIM = {nombre: _rampa(**kw) for nombre, kw in ESCENARIOS.items()}
_COGS, _ARPU, _COGSM, _SERV, _MIN, _CAJA, _CARG = _medias()
_ESTRUCTURA = D["plataforma"] + D["herramientas"] + D["gestoria"] + D["seguro"] + D["ads"]
_SALIDA = _ESTRUCTURA + D["cuota_autonomos"] + D["retirada"]
_VIDA = (1 + (1 - D["churn_nuevo"]) + (1 - D["churn_nuevo"]) ** 2
         + (1 - D["churn_nuevo"]) ** 3 / D["churn_maduro"])


# ==========================================================================
# 9. ESCENARIOS
# ==========================================================================
def construir_escenarios():
    ws = hoja("Escenarios")
    title(ws, "Tres futuros, y cual de ellos aguanta",
          "Mismos costes por cuenta, distinta velocidad y distinta suerte con las bajas. Para "
          "usar uno, copia sus valores a la hoja Supuestos: el libro entero se recalcula. No "
          "hay selector automatico a proposito, para que quede por escrito que escenario "
          "estas mirando. El libro de agosto tenia estas casillas vacias y por eso su "
          "proyeccion se quedaba plana.", 6)
    widths(ws, {"A": 42, "B": 15, "C": 15, "D": 15, "E": 10, "F": 50})

    section(ws, 4, "Palancas por escenario", 6)
    header(ws, 5, ["Palanca", "Prudente", "Base", "Optimista", "", "Por que ese valor"])
    palancas = [
        ("Altas objetivo al mes", 3, D["objetivo"], 8, NUM,
         "El piloto comprometido son 3-5 negocios. Ocho al mes exige prescriptores en marcha."),
        ("Crecimiento mensual del objetivo", 0.02, D["crecimiento"], 0.10, PCT,
         "Sin presupuesto de ads, el crecimiento es boca a boca."),
        ("Bajas los tres primeros meses", 0.12, D["churn_nuevo"], 0.05, PCT,
         "Cuanto peor sea el arranque, mas gente se va pronto."),
        ("Bajas despues", 0.06, D["churn_maduro"], 0.02, PCT,
         "Un producto que ya esta en la rutina del negocio retiene."),
        ("Horas al mes para vender y atender", 40, D["horas_mes"], 90, NUM,
         "Depende de cuanto producto tengas que seguir construyendo tu."),
        ("Soporte de una cuenta nueva (x la asentada)", 3.75, D["mult_nueva"], 1.67, '0.00"x"',
         "Baja si el producto se explica solo. Es la palanca que mas cuentas regala."),
        ("Retirada mensual del founder", 1500, D["retirada"], 1200, EUR0,
         "Lo prudente no es cobrar menos: es necesitar mas caja por el camino."),
    ]
    for i, (lab, pr_, ba, op, fmt, n) in enumerate(palancas):
        r = 6 + i
        txt(ws, r, 1, lab, size=10, color=INK)
        for j, v in enumerate((pr_, ba, op)):
            dato(ws, r, 2 + j, v, fmt, editable=True,
                 naranja=(j == 1))
        txt(ws, r, 6, n, wrap=True)

    section(ws, 14, "Que sale de cada uno (calculado por el generador, no formula viva)", 6)
    header(ws, 15, ["Resultado", "Prudente", "Base", "Optimista", "", "Lectura"])
    resultados = [
        ("Mes en que dejas de perder dinero", "mes", NUM,
         "Con tu retirada ya dentro del calculo."),
        ("Caja minima por el camino", "caja_min", EUR0,
         "El dinero que hay que poder aguantar. Comparar con la caja inicial."),
        ("Cuentas al mes 36", "cuentas", NUM,
         "Hasta donde llega la rampa con esas horas."),
        ("Mes en que el soporte pasa del 70 % de tus horas", "ahogo", NUM,
         "El punto en que hay que decidir: bajar soporte por cuenta o contratar."),
    ]
    for i, (lab, clave, fmt, lec) in enumerate(resultados):
        r = 16 + i
        txt(ws, r, 1, lab, size=10, color=INK)
        for j, nombre in enumerate(("Prudente", "Base", "Optimista")):
            v = SIM[nombre][clave]
            dato(ws, r, 2 + j, v if v is not None else "no llega", fmt,
                 fuerte=(nombre == "Base"))
        txt(ws, r, 6, lec, wrap=True)

    fila = nota(ws, 21,
                f"El escenario prudente no es pesimismo: es el que hay que poder aguantar. Con "
                f"esos supuestos la caja minima baja a "
                f"{_es(SIM['Prudente']['caja_min'])} €, despues de incluir los "
                f"{_es(D['caja_inicial'])} € de caja inicial: el plan "
                f"prudente no es financiable tal cual. Si solo sobrevives en el optimista, el "
                f"plan no es un plan.", span=6, color=WARN)

    section(ws, fila, "Lo que decide cada escenario", 6)
    fila += 1
    for pregunta, respuesta in [
        ("Si las bajas son del 12 % al principio",
         "La cartera se vacia casi tan rapido como entra: cada alta te cuesta tres horas y "
         "dura poco mas de ocho meses."),
        ("Si solo tienes 40 horas al mes",
         "El soporte alcanza tus horas mucho antes y el crecimiento se para sin que el mercado "
         "tenga nada que ver."),
        ("Si el soporte de una cuenta nueva baja a 1,67x",
         "Es la palanca que mas cuentas regala sin vender ni una mas. Ahi es donde paga el "
         "cerebro local y la autoexplicacion del producto."),
        ("Si subes tu retirada de 1.200 a 1.500 €",
         "El equilibrio sube unas ocho cuentas y la caja minima empeora: no es solo cobrar "
         "menos, es necesitar mas dinero antes de llegar."),
    ]:
        txt(ws, fila, 1, pregunta, size=10, color=INK, bold=True)
        txt(ws, fila, 2, respuesta, wrap=True)
        ws.merge_cells(start_row=fila, start_column=2, end_row=fila, end_column=6)
        ws.row_dimensions[fila].height = 30
        fila += 1


construir_escenarios()


# ==========================================================================
# 10. SENSIBILIDAD
# ==========================================================================
def construir_sensibilidad():
    ws = hoja("Sensibilidad")
    title(ws, "Sensibilidad del equilibrio",
          "Cuantas cuentas hacen falta segun lo que tengas que cubrir cada mes y la "
          "contribucion que consigas. Responde a «si me equivoco en el gasto fijo o en el "
          "coste de servir, cuanto me duele». La fila y la columna en gris son entradas.", 8)
    widths(ws, {"A": 30, "B": 13, "C": 13, "D": 13, "E": 13, "F": 13, "G": 13, "H": 13})

    section(ws, 4, "Cuentas necesarias para el equilibrio", 8)
    c = ws["A5"]
    c.value = "Salida de caja \\ Contribucion"
    c.font = Font(name=FUENTE, size=9.5, bold=True, color=FOREST)
    c.fill = PatternFill("solid", fgColor=SAND)
    c.border = BOX
    contribs = [20, 25, round(_CARG, 2), 32, round(_CAJA, 2), 43, 50]
    for j, cv in enumerate(contribs):
        cell = dato(ws, 5, 2 + j, cv, EUR, editable=True)
        cell.fill = PatternFill("solid", fgColor=SAND)
    salidas = [round(_ESTRUCTURA), round(_ESTRUCTURA + D["cuota_autonomos"]), 1000,
               round(_SALIDA), 2000, 2500, 3500, 5000]
    for i, ov in enumerate(salidas):
        r = 6 + i
        cell = dato(ws, r, 1, ov, EUR0, editable=True)
        cell.fill = PatternFill("solid", fgColor=SAND)
        for j in range(len(contribs)):
            col = get_column_letter(2 + j)
            dato(ws, r, 2 + j, f'=IFERROR(ROUNDUP($A{r}/{col}$5,0),"")', NUM)
    ws.conditional_formatting.add(f"B6:H{5 + len(salidas)}", ColorScaleRule(
        start_type='min', start_color='FFDDEFE7', end_type='max', end_color='FFF7E8E3'))

    fila = 6 + len(salidas) + 1
    nota(ws, fila,
         f"Las dos columnas que importan son {_CARG:.2f} € (contribucion cargada: el "
         f"soporte lo paga alguien) y {_CAJA:.2f} € (contribucion en caja: atiendes tu). "
         f"Las tres filas que importan son {_es(_ESTRUCTURA)} € de estructura, "
         f"{_es(_ESTRUCTURA + D['cuota_autonomos'])} € con la cuota de autonomos y "
         f"{_es(_SALIDA)} € con tu retirada dentro. Cada 500 € de salida de caja "
         f"adicional son unas {math.ceil(500 / _CAJA)} cuentas mas que hay que vender solo "
         f"para empatar, y cada euro de contribucion perdido pesa mas cuanto mas arriba estes.",
         span=8)


construir_sensibilidad()


# ==========================================================================
# 11. CANAL Y COMISIONES
# ==========================================================================
def construir_canal():
    ws = hoja("Canal_Comision")
    title(ws, "Que cuesta cada forma de pagar al canal",
          "Las cinco estructuras evaluadas el 16/09/2026, recalculadas con los supuestos de "
          "este libro. «Se lleva» es la parte de la contribucion de toda la vida del cliente "
          "que acaba en el comercial: es la cifra que decide si el canal escala. Nada de esto "
          "esta aprobado.", 7)
    widths(ws, {"A": 36, "B": 15, "C": 14, "D": 14, "E": 18, "F": 18, "G": 46})

    section(ws, 4, "Las cinco estructuras", 7)
    header(ws, 5, ["Estructura", "Pago al alta", "% recurrente", "Meses de recurrente",
                   "Coste total por cliente", "Se lleva (% de la contribucion de la vida)",
                   "Recupera en"])
    estructuras = [
        ("A · una mensualidad al alta", f"={M_ARPU}", 0.0, 0),
        ("B · dos mensualidades al alta", f"={M_ARPU}*2", 0.0, 0),
        ("C · 20 % recurrente de por vida", 0, 0.20, 999),
        ("D · 1 mes + 10 % durante 12 meses", f"={M_ARPU}", 0.10, 12),
        ("E · 2 meses + 5 % durante 12 meses", f"={M_ARPU}*2", 0.05, 12),
    ]
    fila_d = 9
    for i, (nombre, alta, recurrente, meses) in enumerate(estructuras):
        r = 6 + i
        marca = nombre.startswith("D")
        txt(ws, r, 1, nombre, size=10, color=FOREST if marca else INK, bold=marca)
        dato(ws, r, 2, alta, EUR)
        dato(ws, r, 3, recurrente, PCT0, editable=True)
        dato(ws, r, 4, meses, NUM, editable=True)
        dato(ws, r, 5, f"=B{r}+C{r}*{M_ARPU}*MIN(D{r},{M_VIDA})", EUR, fuerte=marca)
        dato(ws, r, 6, f'=IF({M_CAJA}*{M_VIDA}=0,0,E{r}/({M_CAJA}*{M_VIDA}))', PCT)
        dato(ws, r, 7, f'=IF({M_CAJA}<=0,"-",TEXT(E{r}/{M_CAJA},"0.0")&" meses")')
        if marca:
            assert r == fila_d, "la estructura D se ha movido de fila"
    ws.conditional_formatting.add("F6:F10", CellIsRule(
        operator="greaterThan", formula=["0.2"], font=Font(bold=True, color=STOP)))

    fila = nota(ws, 12,
                "La C es la mas cara por cliente y la mas atractiva para el comercial; la A es "
                "la mas barata y la que peor alinea, porque cobra igual si el cliente dura un "
                "mes que si dura tres anos. La D paga pronto, mantiene el coste de canal "
                "contenido y premia la permanencia: es la propuesta del 16/09/2026.", span=7)

    section(ws, fila, "Por que un comercial a sueldo no sale", 7)
    fila += 1
    header(ws, fila, ["Concepto", "Valor", "", "", "", "", "Lectura"])
    fila += 1
    txt(ws, fila, 1, "Coste cargado de un comercial", size=10, color=INK)
    dato(ws, fila, 2, f"={ref['coste_comercial']}", EUR0)
    txt(ws, fila, 7, "Sueldo, seguridad social y estructura.", wrap=True)
    fila += 1
    txt(ws, fila, 1, "Comision recurrente que cobraria", size=10, color=INK)
    dato(ws, fila, 2, 0.20, PCT0, editable=True)
    txt(ws, fila, 7, "Sobre la cuota, no sobre la contribucion.", wrap=True)
    pct_fila = fila
    fila += 1
    txt(ws, fila, 1, "Cuentas activas suyas para cubrirse", size=10, color=INK, bold=True)
    dato(ws, fila, 2, f'=IF({M_ARPU}*B{pct_fila}<=0,"-",'
                      f'ROUNDUP({ref["coste_comercial"]}/({M_ARPU}*B{pct_fila}),0))',
         NUM, fuerte=True)
    dato(ws, fila, 7, f'="A "&{ref["objetivo"]}&" altas al mes tardaria "'
                      f'&TEXT(B{fila}/MAX({ref["objetivo"]},1),"0.0")&" meses en llegar."')
    fila += 2
    fila = nota(ws, fila,
                "La conclusion no es «vende mas»: con esta cuota media, el canal tiene que ser "
                "comision pura, a tiempo parcial o por prescriptor. Una nomina exige una "
                "cartera propia que tarda anos en construirse. Y hay dos cosas que resolver "
                "antes de firmar con nadie: si el acuerdo funciona como contrato de agencia "
                "(Ley 12/1992) puede haber indemnizacion por clientela, y hoy no existe en el "
                "codigo ningun campo de referido para atribuir un alta a un comercial.",
                span=7, color=WARN)

    section(ws, fila, "La cuota de implantacion y la caja del alta", 7)
    fila += 1
    header(ws, fila, ["Concepto", "Sin cuota", "Con la cuota", "", "", "", "Nota"])
    fila += 1
    base = fila
    lineas = [
        ("Primera cuota del cliente", f"={M_ARPU}*(1-{ref['dias_prueba']}/30)",
         f"={M_ARPU}*(1-{ref['dias_prueba']}/30)",
         "La mensualidad del mes de la firma, ya descontados los dias de prueba."),
        ("Cuota de implantacion cobrada", 0, f"={ref['implantacion']}*{ref['pct_implantacion']}",
         "A 0 % de altas que la pagan, esta columna sale igual que la otra: es el valor "
         "honesto mientras no este aprobada."),
        ("Comision pagada al firmar (estructura D)", f"=-{M_ARPU}*{ref['pct_canal']}",
         f"=-{M_ARPU}*{ref['pct_canal']}",
         "A 0 % de altas por canal no hay comision: vendes tu."),
    ]
    for lab, a, b, n in lineas:
        txt(ws, fila, 1, lab, size=10, color=INK)
        dato(ws, fila, 2, a, EUR)
        dato(ws, fila, 3, b, EUR)
        txt(ws, fila, 7, n, wrap=True)
        fila += 1
    txt(ws, fila, 1, "Caja neta el mes de la firma", size=10, color=INK, bold=True)
    dato(ws, fila, 2, f"=SUM(B{base}:B{fila - 1})", EUR, fuerte=True)
    dato(ws, fila, 3, f"=SUM(C{base}:C{fila - 1})", EUR, fuerte=True)
    txt(ws, fila, 7, "Positivo significa que captar no consume caja ese mes.", wrap=True)
    neta = fila
    fila += 1
    txt(ws, fila, 1, "Coste de tu tiempo en esa alta", size=10, color=INK)
    dato(ws, fila, 2, f"={ref['horas_alta']}", DEC)
    dato(ws, fila, 3, f"={ref['horas_alta']}", DEC)
    txt(ws, fila, 7, "Horas, no euros: mientras vendas tu, el alta se paga con tiempo. Esa es "
                     "la parte que la cuota de implantacion pone en precio en vez de "
                     "esconderla en el margen.", wrap=True)
    for columna in ("B", "C"):
        ws.conditional_formatting.add(f"{columna}{neta}", CellIsRule(
            operator="lessThan", formula=["0"], font=Font(bold=True, color=STOP)))
        ws.conditional_formatting.add(f"{columna}{neta}", CellIsRule(
            operator="greaterThanOrEqual", formula=["0"], font=Font(bold=True, color=OKC)))


construir_canal()


# ==========================================================================
# 12. ADS Y CAPTACION
# ==========================================================================
def construir_ads():
    ws = hoja("Ads_Captacion", WARN)
    title(ws, "Publicidad y coste de captacion",
          "La publicidad no escala con los clientes que ya tienes, sino con los que quieres "
          "captar. Las celdas naranjas estan VACIAS a proposito: ninguna cifra de embudo "
          "consta en el repositorio. En cuanto escribas presupuesto y conversiones, el resto "
          "se calcula solo.", 6)
    widths(ws, {"A": 38, "B": 16, "C": 14, "D": 16, "E": 12, "F": 48})

    section(ws, 4, "Entradas de campana", 6)
    header(ws, 5, ["Driver", "Valor", "", "Unidad", "", "Nota"])
    entradas = [
        ("Presupuesto mensual de ads", "€/mes", EUR,
         "El gasto variable principal. Sin el, el resto no calcula"),
        ("Coste por clic", "€/clic", EUR,
         "Meta Ads y Google Ads dan medias distintas: usa la tuya"),
        ("Conversion clic -> lead", "%", PCT, "Visitas que dejan datos en Solicitar acceso"),
        ("Conversion lead -> prueba", "%", PCT, "Leads que activan la prueba de 14 dias"),
        ("Conversion prueba -> pago", "%", PCT, "El dato que mas mueve el CAC"),
        ("Altas que vienen de ads", "%", PCT, "El resto llega por boca a boca y no cuesta ads"),
    ]
    for i, (lab, u, fmt, n) in enumerate(entradas):
        r = 6 + i
        txt(ws, r, 1, lab, size=10, color=INK)
        dato(ws, r, 2, None, fmt, editable=True, naranja=True)
        txt(ws, r, 4, u)
        txt(ws, r, 6, n, wrap=True)

    section(ws, 13, "Embudo resultante", 6)
    header(ws, 14, ["Metrica", "Valor", "", "Unidad", "", "Formula"])
    embudo = [
        ("Clics al mes", '=IFERROR(B6/B7,"")', NUM, "clics", "Presupuesto / coste por clic"),
        ("Leads al mes", '=IFERROR(B15*B8,"")', NUM, "leads", "Clics x conversion a lead"),
        ("Pruebas iniciadas", '=IFERROR(B16*B9,"")', NUM, "pruebas", "Leads x conversion"),
        ("Clientes nuevos de ads", '=IFERROR(B17*B10,"")', DEC, "clientes/mes",
         "Pruebas x conversion a pago"),
        ("Altas totales estimadas", '=IFERROR(IF(B11>0,B18/B11,B18),"")', DEC, "clientes/mes",
         "Incluye las que no vienen de ads"),
        ("Horas que exigen esas altas", f'=IFERROR(B19*{ref["horas_alta"]},"")', DEC, "h/mes",
         "Los ads no te ahorran el tiempo de cerrar y poner en marcha"),
        ("CAC real", '=IFERROR(B6/B18,"")', EUR, "€/cliente",
         "Presupuesto / clientes captados por ads"),
        ("CAC supuesto en el modelo", f"={ref['cac']}", EUR, "€/cliente",
         "150 € sin validar, para contrastar"),
        ("Desviacion frente al supuesto", '=IFERROR(B21-B22,"")', EUR, "€/cliente",
         "Positivo = captar sale mas caro de lo previsto"),
    ]
    for i, (lab, f, fmt, u, n) in enumerate(embudo):
        r = 15 + i
        fuerte = lab in ("CAC real", "Clientes nuevos de ads")
        txt(ws, r, 1, lab, size=10, color=INK)
        dato(ws, r, 2, f, fmt, fuerte=fuerte, size=11 if fuerte else 10)
        txt(ws, r, 4, u)
        txt(ws, r, 6, n, wrap=True)

    section(ws, 25, "Salud de la captacion", 6)
    header(ws, 26, ["Metrica", "Valor", "", "Unidad", "", "Referencia habitual"])
    salud = [
        ("Contribucion media en caja", f"={M_CAJA}", EUR, "€/mes",
         "La que calcula Unit_Economics"),
        ("Meses para recuperar el CAC", f'=IFERROR(B21/{M_CAJA},"")', DEC, "meses",
         "Por debajo de 12 se considera sano"),
        ("Vida media del cliente", f"={M_VIDA}", DEC, "meses",
         "De Unit_Economics, con bajas en dos tramos"),
        ("LTV (contribucion x vida)", f"={M_CAJA}*{M_VIDA}", EUR, "€",
         "Sin descuento financiero"),
        ("LTV / CAC", '=IFERROR(B30/B21,"")', '0.0"x"', "veces", "Referencia SaaS: 3x o mas"),
        ("Veredicto", '=IF(B31="","Faltan datos",IF(AND(B31>=3,B28<=12),"Sano",'
                      'IF(B31>=1,"Ajustado: revisar precio o embudo",'
                      '"Insostenible: cada cliente pierde dinero")))', None, "",
         "Se calcula solo al rellenar las entradas"),
    ]
    for i, (lab, f, fmt, u, n) in enumerate(salud):
        r = 27 + i
        fuerte = lab in ("LTV / CAC", "Veredicto")
        txt(ws, r, 1, lab, size=10, color=INK)
        dato(ws, r, 2, f, fmt, fuerte=fuerte, size=11 if fuerte else 10)
        txt(ws, r, 4, u)
        txt(ws, r, 6, n, wrap=True)

    section(ws, 34, "Impacto de los ads en el equilibrio", 6)
    header(ws, 35, ["Metrica", "Sin ads", "Con ads", "Unidad", "", "Nota"])
    impacto = [
        ("Salida de caja mensual", f"={ref['salida_total']}",
         f'={ref["salida_total"]}+IFERROR(B6,0)', EUR0,
         "El presupuesto de ads se suma mientras dure la campana"),
        ("Clientes para el equilibrio", f'=IFERROR(ROUNDUP(B36/{M_CAJA},0),"")',
         f'=IFERROR(ROUNDUP(C36/{M_CAJA},0),"")', NUM, "Con la contribucion en caja"),
        ("Clientes adicionales que exige el ads", None, '=IFERROR(C37-B37,"")', NUM,
         "Los que la campana debe traer solo para pagarse"),
        ("Meses para conseguirlos", None, '=IFERROR(C38/B18,"")', DEC,
         "Al ritmo de captacion calculado arriba"),
    ]
    for i, (lab, a, b, fmt, n) in enumerate(impacto):
        r = 36 + i
        txt(ws, r, 1, lab, size=10, color=INK)
        dato(ws, r, 2, a, fmt)
        c = dato(ws, r, 3, b, fmt)
        if i >= 2:
            c.font = Font(name=FUENTE, size=10, bold=True, color=WARN)
        txt(ws, r, 6, n, wrap=True)

    nota(ws, 41,
         "El resto del libro mide lo que cuesta SERVIR a un cliente que ya tienes. La "
         "publicidad mide lo que cuesta CONSEGUIRLO, y se comporta al reves: si cortas la "
         "campana manana, el gasto desaparece pero los clientes captados siguen pagando. Por "
         "eso no se mezcla con el COGS ni con el margen de contribucion. Y hay una trampa "
         "propia de este negocio: los ads traen leads, no horas. Si el embudo entrega mas "
         "altas de las que caben en tus horas, el dinero de la campana se tira: mirar la fila "
         "«Horas que exigen esas altas» contra la hoja Horas_del_founder.", span=6)


construir_ads()


# ==========================================================================
# 13. ANUAL VS MENSUAL
# ==========================================================================
def construir_anual():
    ws = hoja("Anual_vs_Mensual")
    title(ws, "Tarifa anual frente a mensual",
          "El anual cobra once meses y da acceso doce: un descuento real del 8,3 %. Se eligio "
          "ese nivel, y no dos meses gratis, para proteger el margen de Premium mientras el "
          "piloto no ha medido voz y soporte reales. Aqui la contribucion ya no es una cifra "
          "copiada: se calcula con los mismos drivers que el mensual.", 8)
    widths(ws, {"A": 20, "B": 14, "C": 14, "D": 16, "E": 14, "F": 18, "G": 18, "H": 34})
    header(ws, 4, ["Plan", "Mensual", "Cobro anual", "Equivalente/mes", "Ahorro/ano",
                   "Contribucion en caja/mes", "Margen", "Diferencia con el mensual"])
    for i, (nombre, col) in enumerate([("Autonomo", "E"), ("Negocio", "F"), ("Premium", "G")]):
        r = 5 + i
        pcol = P[i]
        txt(ws, r, 1, nombre, size=10, color=INK)
        dato(ws, r, 2, f"='{S}'!{pcol}{plan_row['precio']}", EUR)
        dato(ws, r, 3, D["anual"][i], EUR0, editable=True)
        dato(ws, r, 4, f"=C{r}/12", EUR)
        dato(ws, r, 5, f"=B{r}*12-C{r}", EUR)
        # Mismo COGS, pero una sola comision Stripe al ano en vez de doce.
        dato(ws, r, 6, f"=D{r}*(1-{ref['impagos']})-('{UE}'!{col}{UE_COGS}-'{UE}'!{col}6)"
                       f"-(C{r}*({ref['stripe_pay']}+{ref['stripe_bill']})"
                       f"+{ref['stripe_fijo']})/12", EUR, fuerte=True)
        dato(ws, r, 7, f"=F{r}/D{r}", PCT)
        dato(ws, r, 8, f"=F{r}-'{UE}'!{col}{UE_CAJA}", EUR)

    section(ws, 9, "Que aporta el anual al conjunto", 8)
    header(ws, 10, ["Metrica", "Valor", "", "", "", "", "", "Lectura"])
    conj = [
        ("Altas que contratan anual", f"={ref['pct_anual']}", PCT0,
         "Del panel de supuestos."),
        ("Caja adelantada por cada alta anual",
         f"=SUMPRODUCT(C5:C7,'{S}'!B{plan_row['mix']}:D{plan_row['mix']})-{M_ARPU}", EUR0,
         "Once meses cobrados de golpe menos la mensualidad que habrias cobrado igual."),
        ("Caja adelantada al ritmo de altas del panel",
         f"=B12*{ref['objetivo']}*{ref['pct_anual']}", EUR0,
         "Lo que el anual mete en caja cada mes solo por adelantar cobros."),
    ]
    for i, (lab, f, fmt, lec) in enumerate(conj):
        r = 11 + i
        txt(ws, r, 1, lab, size=10, color=INK)
        dato(ws, r, 2, f, fmt, fuerte=i > 0)
        txt(ws, r, 8, lec, wrap=True)

    nota(ws, 15,
         "El anual mejora caja y ahorra once comisiones fijas de Stripe al ano, pero obliga a "
         "reservar capacidad de servicio durante doce meses y a devolver si el cliente se va. "
         "Su contribucion real depende del uso de voz y soporte que el piloto todavia no ha "
         "medido. La hoja Rampa_36m no lo aprovecha a proposito: contar hoy con ese adelanto "
         "seria financiarse con dinero que aun no se ha ganado.", span=8)


construir_anual()


# ==========================================================================
# 14-15. COMPARADOR E HIPOTESIS EXTERNA
# ==========================================================================
def construir_hipotesis_externa():
    ws = hoja("Hipotesis_Externa")
    title(ws, "Hipotesis de coste del documento externo",
          "Reproduccion literal de la tabla recibida. Su propio encabezado la titula «Calculo "
          "(Hipotesis)»: no lleva fuente ni fecha, y aplica el mismo coste a todos los planes "
          "independientemente del uso.", 6)
    widths(ws, {"A": 30, "B": 32, "C": 16, "D": 12, "E": 12, "F": 46})

    section(ws, 4, "Tabla recibida", 6)
    header(ws, 5, ["Concepto de gasto", "Calculo (hipotesis)", "Coste mensual/usuario", "", "",
                   "Contraste con este modelo"])
    ext = [
        ("API de Meta (WhatsApp)", "150 mensajes enviados x 0,0166 €",
         f"=150*{ref['wa_precio']}",
         "Aqui son 30/80/200 mensajes segun plan, no 150 fijos"),
        ("Inteligencia Artificial (LLM)", "150 procesamientos x ~0,02 €", 3.00,
         "Aqui la IA sale a 0,05/0,22/0,69 €: el cerebro interno resuelve el 60 %"),
        ("Servidor y base de datos", "Prorrateo basico por usuario", 1.00,
         "Aqui la plataforma son 7 € al mes repartidos entre las cuentas activas"),
    ]
    for i, (a, b, c, n) in enumerate(ext):
        r = 6 + i
        txt(ws, r, 1, a, size=10, color=INK, bold=True)
        txt(ws, r, 2, b, size=10)
        dato(ws, r, 3, c, EUR, editable=not isinstance(c, str))
        txt(ws, r, 6, n, wrap=True)
    txt(ws, 9, 1, "COSTE TOTAL VARIABLE", size=10, color=FOREST, bold=True)
    txt(ws, 9, 2, "Mensual por usuario", size=10, color=FOREST, bold=True)
    dato(ws, 9, 3, "=SUM(C6:C8)", EUR, fuerte=True)

    section(ws, 11, "Margen resultante con esa hipotesis", 6)
    header(ws, 12, ["Plan", "Precio adoptado", "Coste variable", "Contribucion bruta", "Margen",
                    "Nota"])
    for i, nombre in enumerate(["Autonomo", "Negocio", "Premium"]):
        r = 13 + i
        txt(ws, r, 1, nombre, size=10, color=INK)
        dato(ws, r, 2, f"='{S}'!{P[i]}{plan_row['precio']}", EUR)
        dato(ws, r, 3, "=$C$9", EUR)
        dato(ws, r, 4, f"=B{r}-C{r}", EUR)
        dato(ws, r, 5, f"=D{r}/B{r}", PCT)
        txt(ws, r, 6, "No descuenta soporte ni onboarding: no es comparable con la "
                      "contribucion de Unit_Economics", wrap=True)


def construir_comparador():
    ws = hoja("Comparador")
    title(ws, "Comparador de escenarios de coste",
          "Que pasa con el margen si el coste real por usuario resulta ser el del documento "
          "externo en lugar del estimado internamente. Solo compara COGS variable, para que la "
          "base sea la misma.", 7)
    widths(ws, {"A": 32, "B": 15, "C": 15, "D": 15, "E": 13, "F": 13, "G": 13})

    section(ws, 4, "COGS software por plan", 7)
    header(ws, 5, ["Escenario", "Autonomo", "Negocio", "Premium", "", "", ""])
    for i, lab in enumerate(["Modelo Bynoesis (con fuentes)", "Hipotesis externa", "Diferencia",
                             "Multiplicador"]):
        txt(ws, 6 + i, 1, lab, size=10, color=STOP if i >= 2 else INK, bold=i >= 2)
    for j, col in enumerate(["B", "C", "D"]):
        src = ["E", "F", "G"][j]
        dato(ws, 6, 2 + j, f"='{UE}'!{src}{UE_COGS}", EUR)
        dato(ws, 7, 2 + j, "=Hipotesis_Externa!$C$9", EUR)
        dato(ws, 8, 2 + j, f"={col}7-{col}6", EUR)
        c = dato(ws, 9, 2 + j, f'=IF({col}6>0,{col}7/{col}6,"")', '0.0"x"')
        c.font = Font(name=FUENTE, size=10, bold=True, color=STOP)

    section(ws, 11, "Margen bruto comparado", 7)
    header(ws, 12, ["Escenario", "Autonomo", "Negocio", "Premium", "", "", ""])
    for i, lab in enumerate(["Modelo Bynoesis", "Hipotesis externa", "Puntos perdidos"]):
        txt(ws, 13 + i, 1, lab, size=10, color=STOP if i == 2 else INK, bold=i == 2)
    for j, col in enumerate(["B", "C", "D"]):
        src = ["E", "F", "G"][j]
        dato(ws, 13, 2 + j, f"='{UE}'!{src}{UE_MB}", PCT)
        dato(ws, 14, 2 + j, f"=('{S}'!{P[j]}{plan_row['precio']}-Hipotesis_Externa!$C$9)"
                            f"/'{S}'!{P[j]}{plan_row['precio']}", PCT)
        c = dato(ws, 15, 2 + j, f"={col}13-{col}14", PCT)
        c.font = Font(name=FUENTE, size=10, bold=True, color=STOP)

    nota(ws, 17,
         "La hipotesis externa aplica un coste plano por usuario, asi que penaliza mucho al "
         "plan barato y apenas al caro, mientras que este modelo escala el coste con el uso "
         "incluido en cada plan. Si el piloto midiera un consumo parecido al de la hipotesis, "
         "el plan Autonomo seria el primero en sufrir. Es el escenario que conviene vigilar "
         "durante los primeros 30 dias.", span=7)


construir_hipotesis_externa()
construir_comparador()


# ==========================================================================
# 16. OPCIONES DE IA
# ==========================================================================
def construir_ia():
    ws = hoja("Opciones_IA")
    title(ws, "Coste de IA por opcion",
          "Con 8.000 tokens de entrada y 1.200 de salida por interaccion avanzada. Sirve para "
          "decidir cuando compensa alojar un modelo propio en lugar de pagar por uso.", 6)
    widths(ws, {"A": 34, "B": 20, "C": 14, "D": 14, "E": 14, "F": 40})
    header(ws, 4, ["Opcion", "Coste/interaccion", "75/mes", "300/mes", "1.500/mes", "Nota"])
    for i, (a, b, c, d, e, n) in enumerate([
        ("Cerebro determinista Bynoesis", 0, 0, 0, 0, "Codigo propio: sin coste por token"),
        ("Cloudflare Qwen3 30B A3B", 0.0007, 0.05, 0.21, 1.07, "Proveedor compatible barato"),
        ("Groq Qwen3 32B", 0.0027, 0.20, 0.80, 3.98, "Latencia baja"),
        ("Anthropic Haiku 4.5", 0.0123, 0.92, 3.68, 18.41, "Respaldo de calidad"),
    ]):
        r = 5 + i
        txt(ws, r, 1, a, size=10, color=INK)
        for j, v in enumerate((b, c, d, e)):
            dato(ws, r, 2 + j, v, '0.0000' if j == 0 else EUR, editable=True)
        txt(ws, r, 6, n, wrap=True)

    section(ws, 10, "Cuando compensa alojar un modelo propio", 6)
    for i, (a, b) in enumerate([
        ("GPU 16 GB a 0,58 USD/h, 730 h/mes", "423,40 USD (~371 € al cambio usado)"),
        ("Cruce frente a Haiku 4.5", "~30.243 interacciones/mes"),
        ("Cruce frente a Groq Qwen3", "~139.828 interacciones/mes"),
        ("Conclusion", "Por debajo de ese volumen, cerebro interno mas pago por uso es mas "
                       "barato y exige menos operacion"),
    ]):
        r = 11 + i
        txt(ws, r, 1, a, size=10, color=INK)
        txt(ws, r, 2, b, size=10, color=FOREST if i == 3 else INK, bold=i == 3)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)

    nota(ws, 16,
         "No existe un servidor publico gratuito adecuado como nucleo de produccion: los tiers "
         "gratis pueden cambiar, limitar concurrencia, cortar solicitudes y tratar datos fuera "
         "de Bynoesis. El modelo open source evita licencia por token, pero no elimina "
         "computo, seguridad ni mantenimiento. Y en este negocio la IA no es la partida que "
         "duele: el soporte cuesta mas de tres veces lo que los servidores.", span=6)


construir_ia()


# ==========================================================================
# 17. KPIs DEL PILOTO
# ==========================================================================
def construir_kpis():
    ws = hoja("KPIs_Piloto", TEAL)
    title(ws, "KPIs que debe responder el piloto",
          "Tres cifras convierten este libro en un modelo y no en un escenario: bajas reales, "
          "minutos de soporte por cuenta y horas que cuesta cerrar una venta. Con esas tres "
          "medidas, las demas dejan de importar tanto. La columna Observado se rellena durante "
          "los cierres semanales del piloto con 3-5 autonomos.", 7)
    widths(ws, {"A": 40, "B": 14, "C": 14, "D": 12, "E": 20, "F": 12, "G": 44})
    header(ws, 4, ["Indicador", "Objetivo", "Observado", "Unidad", "Fuente del dato",
                   "Prioridad", "Por que importa"])
    kpis = [
        ("Bajas a 30, 60 y 90 dias", 0.08, "%/mes", "Suscripciones", "1",
         "Es la cifra que mas mueve el modelo y no hay ninguna medida", PCT),
        ("Minutos de soporte por cuenta nueva", 45, "min/mes", "Registro de soporte", "1",
         "El supuesto es 2,5 veces los 18,1 min de una cuenta asentada", NUM),
        ("Horas que cuesta cerrar un alta", 3, "h/alta", "Agenda del founder", "1",
         "Decide cuantas altas caben al mes: es el freno de la rampa", DEC),
        ("Minutos de soporte por cuenta asentada", 18, "min/mes", "Registro de soporte", "2",
         "Ponderado por la mezcla. Bajarlo a 12 regala unas 100 cuentas de techo", NUM),
        ("Resolucion por cerebro interno", 0.60, "%", "Logs de IA por negocio", "2",
         "Si baja del 40 %, el coste de IA se dispara", PCT),
        ("Recibos que no se cobran", 0.03, "%", "Remesas de Stripe", "2",
         "Primera remesa real: entra directo en la contribucion", PCT),
        ("Coste por cuenta observado", 1.48, "€/mes", "Costes por negocio", "2",
         "Contrasta con el COGS estimado del modelo para el plan Autonomo", EUR),
        ("Activacion: alta hasta primer cobro", None, "dias", "Eventos de producto", "3",
         "Mide si el producto engancha antes de que caduque la prueba de 14 dias", NUM),
        ("Trabajos cerrados sin facturar", None, "n/mes", "Panel de trabajos", "3",
         "Es el dinero que Bynoesis rescata: el argumento de venta", NUM),
        ("Cobros recuperados", None, "€/mes", "Recordatorios y portal", "3",
         "Convierte la suscripcion en inversion con retorno", EUR0),
        ("Tiempo ahorrado declarado", None, "h/semana", "Entrevista de cierre", "3",
         "El testimonio que sostiene el precio", DEC),
        ("Minutos de voz consumidos (Premium)", 100, "min/mes", "Adaptador de voz", "3",
         "Si nadie los usa, sacarlos del plan y venderlos como add-on", NUM),
        ("CAC por canal", None, "€", "Ads_Captacion", "3",
         "El supuesto de 150 € esta sin validar", EUR0),
        ("Mezcla real de planes", None, "%", "Suscripciones", "3",
         "El 55/35/10 es un reparto asumido: nadie ha comprado todavia", PCT),
    ]
    for i, (lab, obj, u, src, prio, why, fmt) in enumerate(kpis):
        r = 5 + i
        txt(ws, r, 1, lab, size=10, color=INK, bold=prio == "1")
        dato(ws, r, 2, obj, fmt)
        dato(ws, r, 3, None, fmt, editable=True, naranja=True)
        txt(ws, r, 4, u)
        txt(ws, r, 5, src)
        c = dato(ws, r, 6, prio, NUM)
        c.font = Font(name=FUENTE, size=10, bold=True,
                      color=STOP if prio == "1" else (WARN if prio == "2" else MUTED))
        txt(ws, r, 7, why, wrap=True)
    ws.freeze_panes = "A5"


construir_kpis()


# ==========================================================================
# 18. DATOS PENDIENTES
# ==========================================================================
def construir_pendientes():
    ws = hoja("Datos_Pendientes", STOP)
    title(ws, "Que cifra es un dato y cual es una suposicion",
          "Con cero clientes de pago, casi todo este libro es una hipotesis. Separarlo es lo "
          "unico que impide confundir un escenario con una prevision. En rojo, lo que no esta "
          "medido y mas mueve el resultado; en ambar, lo que falta por confirmar con una "
          "factura o una decision.", 5)
    widths(ws, {"A": 42, "B": 20, "C": 14, "D": 20, "E": 60})
    header(ws, 4, ["Cifra", "Valor en el libro", "Estado", "Quien lo tiene",
                   "Origen o por que falta"])
    entradas = [
        ("Precios 29 / 49 / 99", "Adoptado", "DATO", "Founder",
         "Decision del 15/07/2026; coincide con el catalogo del codigo."),
        ("Coste de software por cuenta", "1,48 / 3,04 / 18,47", "CALCULADO", "Este libro",
         "Driver a driver sobre tarifas publicadas de Stripe, Meta, Anthropic, Groq y Railway "
         "(15/07/2026). Es lo unico de aqui que se puede auditar linea a linea."),
        ("Clientes de pago hoy", "0", "DATO", "Founder",
         "Por eso este libro es prospectivo y lo dice en la primera hoja."),
        ("Bajas mensuales", "8 % y 4 %", "SIN MEDIR", "Piloto",
         "No hay clientes de pago. Es la cifra que mas mueve el modelo: al 12 % / 6 % el "
         "equilibrio se va del mes 10 al 32."),
        ("Minutos de soporte por cuenta", "18,1 ponderados", "SIN MEDIR", "Piloto",
         "Los 12 min del plan Autonomo salen del analisis; los 20 y 45 de Negocio y Premium "
         "son supuestos, y el 2,5x de una cuenta nueva tambien."),
        ("Horas por alta", "3", "SIN MEDIR", "Founder",
         "El analisis cifra solo el onboarding en 30-120 min; el tiempo de vender no esta "
         "medido y es lo que frena la rampa."),
        ("Horas disponibles al mes", "60", "SIN MEDIR", "Founder",
         "Depende de cuanto producto sigas construyendo tu."),
        ("Mezcla 55 / 35 / 10", "Supuesto", "SIN MEDIR", "Piloto",
         "Nadie ha comprado todavia: el reparto real puede ser cualquiera, y mueve a la vez "
         "el ingreso y los minutos de soporte."),
        ("Recibos no cobrados", "3 %", "SIN MEDIR", "Piloto",
         "Se sabra con la primera remesa real de Stripe."),
        ("CAC observado por canal", "150 €", "SIN MEDIR", "Piloto",
         "Sin campanas medidas. El embudo de Ads_Captacion esta vacio a proposito."),
        ("Plataforma", "7 €/mes", "PENDIENTE", "Founder",
         "Cifra que escribio el founder el 17/09/2026. Falta la factura real de Railway."),
        ("Herramientas y suscripciones", "40 €/mes", "PENDIENTE", "Founder",
         "IDE, diseno, analitica, almacenamiento."),
        ("Gestoria", "60 €/mes", "PENDIENTE", "Gestoria", "Falta presupuesto real."),
        ("Seguro de responsabilidad civil", "30 €/mes", "PENDIENTE", "Founder",
         "Habitual antes de operar con datos de terceros."),
        ("Cuota de autonomos", "300 €/mes", "PENDIENTE", "Gestoria",
         "Depende de tarifa plana y de la forma juridica, sin decidir."),
        ("Forma juridica y NIF", "", "PENDIENTE", "Founder",
         "Determina IRPF/IS, cuota de autonomos y la verificacion de Meta."),
        ("Reparto societario entre socios", "", "PENDIENTE", "Founder y socio",
         "Sin el no se puede repartir resultado ni valorar."),
        ("Retirada del founder", "1.200 €/mes", "DECISION", "Founder",
         "No es un dato ni un supuesto: es lo que decidas cobrar. Mueve el equilibrio de 12 a "
         "44 cuentas por si sola."),
        ("Caja inicial", "4.000 €", "PENDIENTE", "Founder y socio",
         "El vault cita esa cifra inicial; falta confirmarla. La rampa base llega a bajar a "
         "-3.390 €, asi que el margen es estrecho."),
        ("Cuota de implantacion 99 €", "Propuesta, al 0 %", "SIN APROBAR", "Founder",
         "Canal-comercial-y-comisiones.md (16/09/2026). El founder reserva descuento, "
         "porcentaje, duracion y devoluciones."),
        ("Estructuras de comision A-E", "Propuesta D", "SIN APROBAR", "Founder",
         "Misma fuente. Y hoy no existe en el codigo ningun campo de referido para atribuir "
         "un alta a un comercial."),
        ("Ingresos facturados hasta hoy", "", "PENDIENTE", "Founder",
         "Si es 0, el modelo es prospectivo y debe decirlo."),
    ]
    colores = {"SIN MEDIR": STOP, "PENDIENTE": WARN, "SIN APROBAR": WARN, "DECISION": WARN}
    for i, (cifra, valor, estado, quien, origen) in enumerate(entradas):
        r = 5 + i
        color = colores.get(estado, INK)
        txt(ws, r, 1, cifra, size=10, color=color, bold=estado == "SIN MEDIR")
        dato(ws, r, 2, valor if valor else None, None, editable=not valor,
             naranja=not valor)
        txt(ws, r, 3, estado, color=color, bold=True)
        txt(ws, r, 4, quien)
        txt(ws, r, 5, origen, wrap=True)
        ws.row_dimensions[r].height = 30
    ws.freeze_panes = "A5"

    nota(ws, 5 + len(entradas) + 1,
         "Lo que convierte esto en un modelo y no en un escenario: tres a cinco clientes de "
         "pago y treinta dias midiendo bajas, minutos de soporte por cuenta y horas por alta. "
         "Hasta entonces, cualquier cifra de este libro sirve para decidir que medir, no para "
         "prometer nada a nadie.", span=5, color=WARN)


construir_pendientes()


# ==========================================================================
# 19. FUENTES
# ==========================================================================
def construir_fuentes():
    ws = hoja("Fuentes")
    title(ws, "Fuentes y cautelas",
          "Tarifas consultadas el 15/07/2026 salvo indicacion. Pueden haber cambiado: "
          "verificar antes de tomar una decision de precio o de proveedor.", 4)
    widths(ws, {"A": 34, "B": 28, "C": 62, "D": 16})
    header(ws, 4, ["Driver", "Proveedor o documento", "URL o ruta", "Consultado"])
    sources = [
        ("Comisiones de pago", "Stripe Espana", "https://stripe.com/es/pricing", "15/07/2026"),
        ("Coste del modelo de respaldo", "Anthropic Haiku",
         "https://www.anthropic.com/claude/haiku", "15/07/2026"),
        ("Plataforma y almacenamiento", "Railway", "https://docs.railway.com/pricing",
         "15/07/2026"),
        ("Correo transaccional", "Resend",
         "https://resend.com/docs/knowledge-base/what-is-resend-pricing", "15/07/2026"),
        ("Mensajeria utility", "WhatsApp Business",
         "https://whatsappbusiness.com/products/platform-pricing/", "15/07/2026"),
        ("Tipo de cambio", "ECB",
         "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html",
         "14/07/2026"),
        ("Voz telefonica", "Retell", "https://www.retellai.com/pricing", "15/07/2026"),
        ("Transcripcion", "Groq Speech-to-Text",
         "https://console.groq.com/docs/speech-to-text", "15/07/2026"),
        ("GPU serverless", "Runpod", "https://www.runpod.io/product/serverless", "15/07/2026"),
        ("Modelo abierto", "Qwen3", "https://github.com/QwenLM/Qwen3", "15/07/2026"),
        ("Unit economics y precio", "Analisis interno",
         "docs/06-negocio-y-finanzas/Unit-economics-y-cerebro-interno.md", "15/07/2026"),
        ("Canal, comisiones e implantacion", "Analisis interno",
         "docs/06-negocio-y-finanzas/Canal-comercial-y-comisiones.md", "16/09/2026"),
        ("Plataforma 7 € y opex editado", "Libro editado por el founder",
         "docs/01-producto/Noesis-Modelo-Economico.xlsx", "17/09/2026"),
        ("Cohortes, horas y tres equilibrios", "Modelo v3",
         "analysis/build_modelo_economico_v3.py", "17/09/2026"),
        ("Bajas, LTV y canal por formula", "Modelo v2",
         "analysis/build_modelo_economico_v2.py", "17/09/2026"),
    ]
    for i, (a, b, c, d) in enumerate(sources):
        r = 5 + i
        txt(ws, r, 1, a, size=10, color=INK)
        txt(ws, r, 2, b, size=10, color=INK)
        cell = ws.cell(row=r, column=3, value=c)
        cell.font = Font(name=FUENTE, size=9, color="FF008000",
                         underline="single" if c.startswith("http") else None)
        if c.startswith("http"):
            cell.hyperlink = c
        txt(ws, r, 4, d)

    fila = 5 + len(sources) + 1
    rotulo(ws, fila, "Cautelas", STOP)
    nota(ws, fila + 1,
         "La tarifa utility de WhatsApp en Espana usa ademas una rate card publicada por un "
         "tercero, porque la tabla oficial dinamica no expuso el valor durante la consulta. "
         "Las tarifas pueden cambiar y no siempre incluyen impuestos. El coste de la hoja "
         "Hipotesis_Externa no tiene fuente ni fecha conocidas. Y ninguna cifra de "
         "comportamiento de cliente —bajas, soporte, horas, mezcla— tiene fuente "
         "externa posible: solo la da el piloto.", span=4)


construir_fuentes()


def construir_calculadora():
    ws = hoja("Calculadora", TEAL)
    title(ws, "Calculadora: escribe cuantos clientes tienes",
          "Cambia solo las tres celdas naranjas y el resto responde: ingresos, cada linea de "
          "coste, las horas que se te van en atenderlos, el resultado del mes y cuanto falta "
          "para el equilibrio. Es la hoja para jugar; las demas explican de donde sale cada "
          "cifra.", 6)
    widths(ws, {"A": 40, "B": 15, "C": 15, "D": 15, "E": 15, "F": 42})

    section(ws, 4, "1 · Cuantos clientes de cada plan", 6)
    header(ws, 5, ["Plan", "Clientes", "Precio", "Facturado al mes", "Cobrado al mes", "Nota"])
    for i, nombre in enumerate(["Autonomo", "Negocio", "Premium"]):
        r = 6 + i
        txt(ws, r, 1, nombre, size=10, color=INK, bold=True)
        c = dato(ws, r, 2, 0, NUM, editable=True, naranja=True, size=13)
        c.alignment = Alignment(horizontal="center")
        dato(ws, r, 3, f"='{S}'!{P[i]}{plan_row['precio']}", EUR0)
        dato(ws, r, 4, f"=B{r}*C{r}", EUR0)
        dato(ws, r, 5, f"=D{r}*(1-{ref['impagos']})", EUR0)
        ws.row_dimensions[r].height = 22
    txt(ws, 9, 1, "TOTAL", size=10, color=FOREST, bold=True)
    for col, idx, fmt in (("B", 2, NUM), ("D", 4, EUR0), ("E", 5, EUR0)):
        dato(ws, 9, idx, f"=SUM({col}6:{col}8)", fmt, fuerte=True)
    txt(ws, 9, 6, "Sin IVA. Cobrado ya descuenta los recibos que no se cobran")

    section(ws, 11, "2 · Lo que cuesta servirlos, en dinero", 6)
    header(ws, 12, ["Concepto", "Autonomo", "Negocio", "Premium", "Total",
                    "€ por cliente"])
    for i, (lab, ue_row) in enumerate([
            ("Comisiones de Stripe", 6), ("WhatsApp (plantillas)", 7), ("IA avanzada", 8),
            ("Transcripcion de voz", 9), ("Extraccion de documentos", 10),
            ("Almacenamiento", 11), ("Voz telefonica (Premium)", 12)]):
        r = 13 + i
        txt(ws, r, 1, lab, size=10, color=INK)
        for j, col in enumerate(["E", "F", "G"]):
            dato(ws, r, 2 + j, f"=$B${6 + j}*'{UE}'!{col}{ue_row}", EUR)
        dato(ws, r, 5, f"=SUM(B{r}:D{r})", EUR)
        dato(ws, r, 6, f'=IFERROR(E{r}/$B$9,"")', EUR)
    txt(ws, 20, 1, "TOTAL COSTES VARIABLES", size=10, color=FOREST, bold=True)
    for j in range(4):
        col = get_column_letter(2 + j)
        dato(ws, 20, 2 + j, f"=SUM({col}13:{col}19)", EUR, fuerte=True)
    dato(ws, 20, 6, '=IFERROR(E20/$B$9,"")', EUR, fuerte=True)

    section(ws, 22, "3 · Lo que cuesta atenderlos, en tu tiempo", 6)
    header(ws, 23, ["Concepto", "Autonomo", "Negocio", "Premium", "Total", "Lectura"])
    txt(ws, 24, 1, "Horas de soporte al mes", size=10, color=INK)
    for j in range(3):
        dato(ws, 24, 2 + j, f"=$B${6 + j}*'{S}'!{P[j]}{plan_row['soporte']}/60", DEC)
    dato(ws, 24, 5, "=SUM(B24:D24)", DEC, fuerte=True)
    txt(ws, 24, 6, "Solo soporte: no incluye el tiempo de vender ni de poner en marcha",
        wrap=True)
    tiempo = [
        ("Porcentaje de tus horas", f'=IFERROR(E24/{ref["horas_mes"]},"")', PCT,
         "Por encima del 70 % no queda mes para vender"),
        ("Horas que te quedan para vender", f'=MAX(0,{ref["horas_mes"]}-E24)', DEC,
         "Lo que sobra despues de atender a esa cartera"),
        ("Altas que puedes cerrar con ese resto",
         f'=ROUNDDOWN(E26/{ref["horas_alta"]},0)', NUM,
         "A las horas por alta del panel de supuestos"),
        ("Si ese soporte lo pagaras a otra persona", f'=E24*{ref["hora_soporte"]}', EUR0,
         "No sale de caja mientras lo hagas tu, pero es lo que costaria delegarlo"),
    ]
    for i, (lab, f, fmt, lec) in enumerate(tiempo):
        r = 25 + i
        txt(ws, r, 1, lab, size=10, color=INK)
        dato(ws, r, 5, f, fmt, fuerte=(i == 0))
        txt(ws, r, 6, lec, wrap=True)
    ws.conditional_formatting.add("E25", CellIsRule(
        operator="greaterThanOrEqual", formula=["0.7"], font=Font(bold=True, color=STOP)))

    section(ws, 30, "4 · Lo que sale de caja, tengas los clientes que tengas", 6)
    header(ws, 31, ["Concepto", "Mensual", "", "", "Anual", "Nota"])
    fijos = [
        ("Estructura (plataforma, herramientas, gestoria, seguro, publicidad)",
         f"={ref['estructura']}", "Del bloque 5 de la hoja Supuestos"),
        ("Cuota de autonomos", f"={ref['cuota_autonomos']}", "PENDIENTE de la gestoria"),
        ("Lo que quieres cobrar tu", f"={ref['retirada']}",
         "Es una decision, no un dato. Sin esta linea el equilibrio no significa nada"),
    ]
    for i, (lab, f, n) in enumerate(fijos):
        r = 32 + i
        txt(ws, r, 1, lab, size=10, color=INK, wrap=True)
        dato(ws, r, 2, f, EUR0)
        dato(ws, r, 5, f"=B{r}*12", EUR0)
        txt(ws, r, 6, n, wrap=True)
    txt(ws, 35, 1, "TOTAL SALIDA DE CAJA", size=10, color=FOREST, bold=True)
    dato(ws, 35, 2, "=SUM(B32:B34)", EUR0, fuerte=True)
    dato(ws, 35, 5, "=B35*12", EUR0, fuerte=True)

    section(ws, 37, "5 · Resultado del mes", 6)
    header(ws, 38, ["Metrica", "Mensual", "", "", "Anual", "Nota"])
    resultado = [
        ("Ingreso cobrado", "=E9", "Facturado menos los recibos que no se cobran"),
        ("(-) Costes variables", "=-E20", "Escalan con cada cliente nuevo"),
        ("MARGEN BRUTO", "=B39+B40", "Lo que queda para pagar la estructura y pagarte a ti"),
        ("(-) Salida de caja", "=-B35", "Estructura, cuota y tu retirada"),
        ("RESULTADO DEL MES", "=B41+B42", "Lo que gana o pierde la empresa cada mes"),
    ]
    for i, (lab, f, n) in enumerate(resultado):
        r = 39 + i
        total = lab in ("MARGEN BRUTO", "RESULTADO DEL MES")
        txt(ws, r, 1, lab, size=10, color=FOREST if total else INK, bold=total)
        dato(ws, r, 2, f, EUR0, fuerte=total,
             size=14 if lab == "RESULTADO DEL MES" else None)
        dato(ws, r, 5, f"=B{r}*12", EUR0, fuerte=total)
        txt(ws, r, 6, n, wrap=True)
    ws.row_dimensions[43].height = 24
    for rango in ("B43", "E43"):
        ws.conditional_formatting.add(rango, CellIsRule(
            operator="lessThan", formula=["0"], font=Font(bold=True, size=14, color=STOP)))
        ws.conditional_formatting.add(rango, CellIsRule(
            operator="greaterThanOrEqual", formula=["0"],
            font=Font(bold=True, size=14, color=OKC)))
    txt(ws, 44, 1, "Margen sobre ingreso", size=10, color=INK)
    dato(ws, 44, 2, '=IFERROR(B43/B39,"")', PCT)

    section(ws, 46, "6 · Cuanto falta para el equilibrio", 6)
    header(ws, 47, ["Metrica", "Valor", "", "", "Unidad", "Nota"])
    equilibrio = [
        ("Contribucion media de TU mezcla", '=IFERROR((E9-E20)/B9,"")', EUR, "€/mes",
         "Con la mezcla exacta de clientes que has escrito arriba"),
        ("Clientes actuales", "=B9", NUM, "clientes", "La suma de las tres celdas naranjas"),
        ("Clientes para el equilibrio", '=IFERROR(ROUNDUP($B$35/$B$48,0),"")', NUM,
         "clientes", "Manteniendo esa misma mezcla de planes"),
        ("Faltan", '=IFERROR(MAX(0,B50-B49),"")', NUM, "clientes",
         "Cero significa que ya estas por encima"),
        ("Horas que exigiria esa cartera", f'=IFERROR(B50*{M_MIN}/60,"")', DEC, "h/mes",
         "Contra tus horas disponibles. Si se pasa, el equilibrio no cabe en tu tiempo"),
        ("Veredicto",
         '=IF(B49=0,"Escribe cuantos clientes tienes arriba",'
         f'IF(E24>{ref["horas_mes"]},"No te dan las horas: esa cartera te ocupa mas tiempo '
         f'del que tienes",IF(B43>=0,"Por encima del equilibrio: la empresa gana dinero y te '
         f'paga","Por debajo del equilibrio: cada mes se consume caja")))', None, "",
         "Se recalcula solo"),
    ]
    for i, (lab, f, fmt, u, n) in enumerate(equilibrio):
        r = 48 + i
        fuerte = lab in ("Clientes para el equilibrio", "Faltan", "Veredicto")
        c = dato(ws, r, 2, f, fmt, fuerte=fuerte)
        txt(ws, r, 1, lab, size=10, color=INK)
        if lab == "Veredicto":
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
            c.font = Font(name=FUENTE, size=11, bold=True, color=FOREST)
        txt(ws, r, 5, u)
        txt(ws, r, 6, n, wrap=True)

    nota(ws, 55,
         "Prueba a escribir 24, 15 y 5: es el reparto del equilibrio con la mezcla prevista, "
         "el que ademas te paga la retirada. Despues cambia una sola cifra y mira que pasa. "
         "Diez clientes Premium mueven mucho mas la aguja que diez Autonomos, y esa es toda la "
         "conversacion comercial resumida en una celda. Pero mira tambien el bloque 3: el plan "
         "caro consume casi cuatro veces mas soporte, asi que la aguja del dinero y la del "
         "tiempo no se mueven a la vez.", span=6)
    ws.freeze_panes = "A6"


construir_calculadora()


# ==========================================================================
# 1. RESUMEN  (se escribe al final: solo referencia a las demas)
# ==========================================================================
def construir_resumen():
    ws = hoja("Resumen", FOREST)
    title(ws, "Bynoesis — Modelo economico",
          "Modelo vivo: las celdas azules de la hoja Supuestos son entradas y el resto son "
          "formulas. No pregunta «cuanto ganaria con 500 clientes»: pregunta cuantos puedes "
          "atender tu solo, cuando dejas de perder dinero y cuanta caja hace falta hasta "
          "entonces. Con cero clientes de pago hoy, todo esto es un escenario; la hoja "
          "Datos_Pendientes dice que cifra es un dato y cual no.", 6)
    widths(ws, {"A": 44, "B": 15, "C": 15, "D": 15, "E": 14, "F": 48})

    section(ws, 4, "Catalogo adoptado", 6)
    header(ws, 5, ["Concepto", "Autonomo", "Negocio", "Premium", "Unidad", "Nota"])
    for i, (lab, plano, fmt, u, n) in enumerate([
        ("Precio mensual", plan_row["precio"], EUR, "€/mes + IVA",
         "Decision del 15/07/2026"),
        ("Mezcla de clientes supuesta", plan_row["mix"], PCT, "%",
         "SUPUESTO: nadie ha comprado todavia"),
    ]):
        r = 6 + i
        txt(ws, r, 1, lab, size=10, color=INK)
        for j in range(3):
            dato(ws, r, 2 + j, f"='{S}'!{P[j]}{plano}", fmt)
        txt(ws, r, 5, u)
        txt(ws, r, 6, n, wrap=True)
    r = 8
    txt(ws, r, 1, "Precio anual (cobra 11, da 12)", size=10, color=INK)
    for j in range(3):
        dato(ws, r, 2 + j, f"=Anual_vs_Mensual!C{5 + j}", EUR0)
    txt(ws, r, 5, "€/ano + IVA")
    txt(ws, r, 6, "Descuento real del 8,3 %", wrap=True)

    section(ws, 10, "Lo que deja cada cuenta", 6)
    header(ws, 11, ["Metrica", "Autonomo", "Negocio", "Premium", "Media", "Nota"])
    for i, (lab, ue_row, fmt, n) in enumerate([
        ("COGS software", UE_COGS, EUR, "Stripe, WhatsApp, IA, voz, almacenamiento"),
        ("Margen bruto", UE_MB, PCT, "Sobre el precio de catalogo"),
        ("Contribucion EN CAJA", UE_CAJA, EUR,
         "Mientras atiendes tu. Es la que manda hoy"),
        ("Contribucion CARGADA", UE_CARGADA, EUR,
         "Cuando el soporte lo paga alguien. Descuenta soporte y onboarding a 25 €/h"),
    ]):
        r = 12 + i
        fuerte = ue_row == UE_CAJA
        txt(ws, r, 1, lab, size=10, color=FOREST if fuerte else INK, bold=fuerte)
        for j, col in enumerate(["E", "F", "G"]):
            dato(ws, r, 2 + j, f"='{UE}'!{col}{ue_row}", fmt)
        media = {UE_COGS: M_COGS, UE_CAJA: M_CAJA, UE_CARGADA: M_CARG}.get(ue_row)
        if media:
            dato(ws, r, 5, f"={media}", fmt, fuerte=fuerte)
        else:
            dato(ws, r, 5, f"=({M_ARPU}-{M_COGS})/{M_ARPU}", fmt)
        txt(ws, r, 6, n, wrap=True)

    section(ws, 17, "Los tres equilibrios — la pregunta de verdad", 6)
    header(ws, 18, ["Nivel", "Cuentas", "Cuesta al mes", "", "Unidad", "Nota"])
    for i, (lab, be_row, n) in enumerate([
        ("Cubrir solo la estructura", 6, "Sin cobrar nada tu"),
        ("Cubrir estructura y cuota de autonomos", 7, "Dejas de poner dinero de tu bolsillo"),
        ("EQUILIBRIO DE VERDAD: ademas te pagas la retirada", BE_RETIRADA,
         "La cifra que hay que mirar"),
        ("El mismo, con el soporte pagado a otra persona", 9,
         "La contribucion baja y el equilibrio sube"),
    ]):
        r = 19 + i
        fuerte = be_row == BE_RETIRADA
        txt(ws, r, 1, lab, size=10, color=FOREST if fuerte else INK, bold=fuerte)
        dato(ws, r, 2, f"='{BE}'!D{be_row}", NUM, fuerte=fuerte)
        dato(ws, r, 3, f"='{BE}'!B{be_row}", EUR0)
        txt(ws, r, 5, "cuentas")
        txt(ws, r, 6, n, wrap=True)

    section(ws, 24, "Tiempo y caja — lo que decide si el plan es posible", 6)
    header(ws, 25, ["Pregunta", "Respuesta", "", "", "Unidad", "Como se calcula"])
    preguntas = [
        ("Cuentas que puedes atender tu solo", f"='{HF}'!$B${HF_TECHO}", NUM, "cuentas",
         "Donde el soporte se come todas tus horas y no queda ninguna para vender"),
        ("Techo practico (soporte al 70 % de tus horas)", f"='{HF}'!$B${HF_PRACTICO}", NUM,
         "cuentas", "El punto en que hay que decidir: bajar soporte por cuenta o contratar"),
        ("¿Cabe el equilibrio en tus horas?", f"='{BE}'!$B$17", None, "",
         "Compara el equilibrio de verdad con tu capacidad"),
        ("Mes en que dejas de perder dinero", f"='{RAMPA}'!$D${R_MES}", NUM, "mes",
         "Primer mes con resultado positivo, con tu retirada dentro"),
        ("Caja minima por el camino", f"='{RAMPA}'!$D${R_CAJAMIN}", EUR0, "€",
         "El punto mas bajo: el dinero que hay que poder aguantar"),
        ("Caja inicial disponible", f"={ref['caja_inicial']}", EUR0, "€",
         "PENDIENTE de confirmar. Si la caja minima la supera, el plan no es financiable"),
        ("Cuentas al mes 36", f"='{RAMPA}'!$D${R_CUENTAS}", NUM, "cuentas",
         "Hasta donde llega la rampa con tus horas"),
        ("Vida media del cliente", f"={M_VIDA}", DEC, "meses",
         "Con bajas del 8 % los tres primeros meses y del 4 % despues"),
        ("LTV / CAC", f'=IF({ref["cac"]}<=0,"-",{M_CAJA}*{M_VIDA}/{ref["cac"]})', '0.0"x"',
         "veces", "Referencia SaaS: 3x o mas. El CAC de 150 € esta sin validar"),
    ]
    for i, (lab, f, fmt, u, n) in enumerate(preguntas):
        r = 26 + i
        fuerte = lab.startswith(("Mes en que", "Caja minima", "¿Cabe"))
        txt(ws, r, 1, lab, size=10, color=INK, bold=fuerte)
        c = dato(ws, r, 2, f, fmt, fuerte=fuerte)
        if fmt is None:
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
            c.font = Font(name=FUENTE, size=10, bold=True, color=FOREST)
        txt(ws, r, 5, u)
        txt(ws, r, 6, n, wrap=True)
    ws.conditional_formatting.add("B28", FormulaRule(
        formula=['ISNUMBER(SEARCH("NO:",$B$28))'],
        font=Font(bold=True, color=STOP)))

    rotulo(ws, 36, "Aviso", STOP)
    nota(ws, 37,
         "Ninguna cifra de este libro es un resultado observado: no hay clientes de pago. Son "
         "supuestos de planificacion fechados que el piloto debe recalibrar. Lo unico auditable "
         "linea a linea es el COGS por plan, que sale de tarifas publicadas. Todo lo demas "
         "—bajas, minutos de soporte, horas por alta, mezcla de planes, CAC— es una "
         "hipotesis, y las tres primeras son las que mas mueven el resultado. Este libro sirve "
         "para decidir que medir en el piloto, no para prometer nada a nadie.",
         span=6, alto=4, color=MUTED)


construir_resumen()


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
print("hojas:", ", ".join(s.title for s in wb.worksheets))
print()
print("COMPROBACION (misma aritmetica que las formulas del libro)")
print("-" * 72)
for i, nombre in enumerate(("Autonomo", "Negocio", "Premium")):
    print(f"  {nombre:9s} precio {D['precio'][i]:3d} EUR   COGS {_COGS[i]:6.2f} EUR   "
          f"margen bruto {(D['precio'][i] - _COGS[i]) / D['precio'][i]:6.2%}")
print(f"  ARPU {_ARPU:.2f} EUR | COGS medio {_COGSM:.2f} EUR | "
      f"soporte+onboarding medio {_SERV:.2f} EUR | soporte {_MIN:.1f} min/cuenta")
print(f"  Contribucion EN CAJA {_CAJA:.2f} EUR   |   CARGADA {_CARG:.2f} EUR")
print(f"  Vida media {_VIDA:.1f} meses | LTV en caja {_CAJA * _VIDA:,.0f} EUR | "
      f"LTV/CAC {_CAJA * _VIDA / D['cac']:.1f}x")
print(f"  Equilibrios: estructura {math.ceil(_ESTRUCTURA / _CAJA)} | "
      f"+cuota {math.ceil((_ESTRUCTURA + D['cuota_autonomos']) / _CAJA)} | "
      f"+retirada {math.ceil(_SALIDA / _CAJA)} | "
      f"+retirada con soporte pagado {math.ceil(_SALIDA / _CARG)} cuentas")
print(f"  Techo de soporte en solitario: {math.floor(D['horas_mes'] / (_MIN / 60))} cuentas "
      f"(practico al 70 %: {math.floor(D['horas_mes'] * 0.7 / (_MIN / 60))})")
for nombre in ("Prudente", "Base", "Optimista"):
    s = SIM[nombre]
    print(f"  {nombre:10s} equilibrio mes {str(s['mes']):>3s} | "
          f"caja minima {s['caja_min']:9,.0f} EUR | cuentas m36 {s['cuentas']:5.0f} | "
          f"soporte al 70 % en el mes {str(s['ahogo']):>3s}")
