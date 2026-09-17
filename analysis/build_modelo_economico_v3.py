"""Modelo economico v3: el negocio como es, no como gusta verlo.

Los modelos anteriores calculan bien lo que cuesta servir una cuenta. Este parte
de ahi y corrige lo que los hacia irreales:

1. **El founder cuesta dinero.** Un equilibrio de 17 cuentas con 500 EUR de opex
   describe un negocio donde nadie cobra. Aqui la retirada del founder y su cuota
   de autonomos son palancas visibles, y hay tres equilibrios distintos: cubrir la
   estructura, cubrir la estructura mas la cuota, y pagar un sueldo.
2. **El tiempo del founder es el limite, no el mercado.** Las altas no son una
   constante: salen de las horas que quedan despues de atender a la cartera. Cuando
   el soporte se come las horas, el crecimiento se para solo. Esa es la curva real
   de un negocio de una persona.
3. **El soporte del founder no es caja.** Cobrarlo a 25 EUR/hora *y ademas* pagarle
   un sueldo cuenta su tiempo dos veces. Aqui el soporte consume horas —capacidad—
   y solo se vuelve dinero cuando hay que contratar.
4. **La gente se va.** Con bajas mas altas los primeros meses, que es como se
   comporta de verdad una cartera nueva, y no cero como en la proyeccion anterior.
5. **El primer mes no se cobra entero**: hay catorce dias de prueba, y una parte de
   los recibos no se cobra a la primera.

Las cifras de coste por cuenta vienen del analisis del 15/07/2026 y del libro que
el founder edito el 17/09/2026 (opex 500 EUR, plataforma 7 EUR). Lo que sigue sin
medirse esta marcado como supuesto en la ultima hoja.

Uso: py analysis/build_modelo_economico_v3.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule, FormulaRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
except ModuleNotFoundError:  # pragma: no cover - herramienta de analisis
    raise SystemExit('Falta openpyxl. Instalalo con: pip install -e ".[analysis]"')

FOREST, TEAL, INK, MUTED, WHITE = ("FF14463B", "FF2E8B74", "FF15211C",
                                   "FF5D6B66", "FFFFFFFF")
INPUT, WARN, STOP, OKC = "FF0000CC", "FFB7831F", "FFC0533F", "FF1F8A6D"
BANDA = "FFF4F1EA"
HAIR = Side(style="thin", color="FFDDD8CC")
BOX = Border(left=HAIR, right=HAIR, top=HAIR, bottom=HAIR)
EUR = '#,##0.00\\ "€"'
EUR0 = '#,##0\\ "€"'
PCT, PCT0, NUM, DEC = '0.0%', '0%', '#,##0', '#,##0.0'
FUENTE = "Aptos"

# Coste de software por cuenta y mes, del analisis del 15/07/2026.
PLANES = [("Autonomo", 29, 1.48, 319), ("Negocio", 49, 3.04, 539),
          ("Premium", 99, 18.47, 1089)]

# Filas fijas que unas hojas referencian en otras. Con aserciones al escribir.
PANEL_PRECIOS = 8          # primera fila del bloque de planes
PANEL_CLIENTE = 15         # primera palanca de comportamiento del cliente
PANEL_TIEMPO = 23          # primera palanca de tiempo del founder
PANEL_COSTES = 32          # primera partida de estructura
PANEL_RESULTADOS = 45      # primera fila de resultados
RAMPA_INICIO = 10           # primera fila de los 36 meses

DESTINO = (Path(__file__).resolve().parents[1] / "docs" /
           "06-negocio-y-finanzas" / "Bynoesis-Modelo-Economico-v3.xlsx")


def _titulo(ws, texto, subtitulo=""):
    ws["A1"] = texto
    ws["A1"].font = Font(name=FUENTE, size=16, bold=True, color=FOREST)
    if not subtitulo:
        return 3
    ws["A2"] = subtitulo
    ws["A2"].font = Font(name=FUENTE, size=10, color=MUTED)
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=2, start_column=1, end_row=4, end_column=9)
    ws.row_dimensions[2].height = 42
    return 6


def _seccion(ws, fila, texto):
    celda = ws.cell(row=fila, column=1, value=texto)
    celda.font = Font(name=FUENTE, size=12, bold=True, color=FOREST)
    return fila + 1


def _cabecera(ws, fila, titulos):
    for columna, texto in enumerate(titulos, start=1):
        celda = ws.cell(row=fila, column=columna, value=texto)
        celda.font = Font(name=FUENTE, size=10, bold=True, color=WHITE)
        celda.fill = PatternFill("solid", fgColor=FOREST)
        celda.border = BOX
        celda.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.row_dimensions[fila].height = 30


def _fila(ws, fila, valores, formatos, *, editable=False, negrita=False,
          banda=False):
    for columna, valor in enumerate(valores, start=1):
        celda = ws.cell(row=fila, column=columna, value=valor)
        celda.border = BOX
        if columna - 1 < len(formatos) and formatos[columna - 1]:
            celda.number_format = formatos[columna - 1]
        celda.font = Font(name=FUENTE, size=10, bold=negrita,
                          color=INPUT if (editable and columna == 2) else INK)
        if banda:
            celda.fill = PatternFill("solid", fgColor=BANDA)


def _nota(ws, fila, texto, *, color=MUTED):
    celda = ws.cell(row=fila, column=1, value=texto)
    celda.font = Font(name=FUENTE, size=9, color=color)
    celda.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila + 1, end_column=9)
    ws.row_dimensions[fila].height = 28
    return fila + 3


def _anchos(ws, anchos):
    for columna, ancho in anchos.items():
        ws.column_dimensions[columna].width = ancho


def _hoja(wb, nombre):
    ws = wb.create_sheet(nombre)
    ws.sheet_properties.tabColor = TEAL
    ws.sheet_view.showGridLines = False
    return ws


# ---------------------------------------------------------------- PANEL ---
def panel(wb):
    ws = wb.active
    ws.title = "Panel"
    ws.sheet_properties.tabColor = FOREST
    ws.sheet_view.showGridLines = False
    _anchos(ws, {"A": 44, "B": 15, "C": 13, "D": 13, "E": 11, "F": 56})

    fila = _titulo(
        ws, "Bynoesis · modelo economico v3 (realista)",
        "Azul = lo editas tu. Negro = formula. Este libro no pregunta «cuanto "
        "ganaria con 500 clientes»: pregunta «cuantos puedo atender yo solo, "
        "cuando dejo de perder dinero y cuanta caja necesito hasta entonces». "
        "Con cero clientes de pago hoy, todo lo de aqui es un escenario; la "
        "ultima hoja dice que cifra es un dato y cual no.",
    )

    fila = _seccion(ws, fila, "1 · Precios y mezcla")
    _cabecera(ws, fila, ["Plan", "Precio", "Coste software", "Mezcla", "",
                         "De donde sale"])
    fila += 1
    assert fila == PANEL_PRECIOS, f"precios en {fila}, se espera {PANEL_PRECIOS}"
    for (nombre, precio, cogs, _anual), peso in zip(PLANES, (0.55, 0.35, 0.10)):
        _fila(ws, fila, [
            nombre, precio, cogs, peso, None,
            "Precio adoptado el 15/07/2026. El coste es Stripe, WhatsApp, IA, "
            "voz y almacenamiento.",
        ], [None, EUR0, EUR, PCT0], editable=True)
        fila += 1
    _fila(ws, fila, [
        "Media ponderada",
        f"=SUMPRODUCT(B{PANEL_PRECIOS}:B{fila - 1},D{PANEL_PRECIOS}:D{fila - 1})",
        f"=SUMPRODUCT(C{PANEL_PRECIOS}:C{fila - 1},D{PANEL_PRECIOS}:D{fila - 1})",
        f"=SUM(D{PANEL_PRECIOS}:D{fila - 1})", None,
        "La mezcla debe sumar 100 %.",
    ], [None, EUR, EUR, PCT0], negrita=True)
    arpu, cogs_medio = f"$B${fila}", f"$C${fila}"
    fila += 2

    fila = _seccion(ws, fila, "2 · Como se comporta un cliente")
    _cabecera(ws, fila, ["Palanca", "Valor", "", "", "", "Por que importa"])
    fila += 1
    assert fila == PANEL_CLIENTE, f"cliente en {fila}, se espera {PANEL_CLIENTE}"
    for etiqueta, valor, formato, nota in [
        ("Bajas los tres primeros meses", 0.08, PCT,
         "SUPUESTO. Una cartera nueva pierde mas al principio: el que no llega a "
         "usarlo se va pronto. El modelo anterior suponia cero bajas."),
        ("Bajas a partir del cuarto mes", 0.04, PCT,
         "SUPUESTO. Quien pasa de los tres meses suele quedarse."),
        ("Dias de prueba gratis", 14, NUM,
         "El primer mes de cada alta no se cobra entero."),
        ("Recibos que no se cobran", 0.03, PCT,
         "SUPUESTO. Tarjetas caducadas y devoluciones."),
        ("Contratan plan anual", 0.20, PCT0,
         "SUPUESTO. El anual adelanta once meses de caja."),
    ]:
        _fila(ws, fila, [etiqueta, valor, None, None, None, nota],
              [None, formato], editable=True)
        fila += 1
    churn_nuevo, churn_maduro = f"$B${PANEL_CLIENTE}", f"$B${PANEL_CLIENTE + 1}"
    dias_prueba, impagos = f"$B${PANEL_CLIENTE + 2}", f"$B${PANEL_CLIENTE + 3}"
    anual = f"$B${PANEL_CLIENTE + 4}"
    fila += 1

    fila = _seccion(ws, fila, "3 · Tu tiempo, que es el limite de verdad")
    _cabecera(ws, fila, ["Palanca", "Valor", "", "", "", "Por que importa"])
    fila += 1
    assert fila == PANEL_TIEMPO, f"tiempo en {fila}, se espera {PANEL_TIEMPO}"
    for etiqueta, valor, formato, nota in [
        ("Horas al mes para vender y atender", 60, NUM,
         "Las que te quedan despues de construir producto. Es la palanca que "
         "decide todo lo demas."),
        ("Horas por alta (venta y puesta en marcha)", 3.0, DEC,
         "Demo, alta, primera factura y acompanamiento. El analisis cifra el "
         "onboarding en 30-120 minutos; vender ocupa mas que eso."),
        ("Minutos de soporte, cuenta nueva", 30, NUM,
         "Los tres primeros meses preguntan mucho mas."),
        ("Minutos de soporte, cuenta asentada", 12, NUM,
         "Del analisis del 15/07/2026 para el plan Autonomo."),
        ("Altas que te gustaria hacer al mes", 5, NUM,
         "Tu objetivo comercial. El modelo solo lo cumple si te quedan horas."),
        ("Crecimiento mensual de ese objetivo", 0.05, PCT,
         "Boca a boca y prescriptores. Sin ads, es lento."),
    ]:
        _fila(ws, fila, [etiqueta, valor, None, None, None, nota],
              [None, formato], editable=True)
        fila += 1
    horas, horas_alta = f"$B${PANEL_TIEMPO}", f"$B${PANEL_TIEMPO + 1}"
    min_nueva, min_madura = f"$B${PANEL_TIEMPO + 2}", f"$B${PANEL_TIEMPO + 3}"
    objetivo, crecimiento = f"$B${PANEL_TIEMPO + 4}", f"$B${PANEL_TIEMPO + 5}"
    fila += 1

    fila = _seccion(ws, fila, "4 · Lo que sale de tu bolsillo cada mes")
    _cabecera(ws, fila, ["Partida", "Valor", "", "", "", "Nota"])
    fila += 1
    assert fila == PANEL_COSTES, f"costes en {fila}, se espera {PANEL_COSTES}"
    for etiqueta, valor, nota in [
        ("Servidores y dominio", 30, "Railway, dominio y correo. PENDIENTE: la factura real."),
        ("Herramientas y suscripciones", 40, "IDE, diseno, analitica, almacenamiento."),
        ("Gestoria", 60, "PENDIENTE: presupuesto real."),
        ("Seguro y otros fijos", 30, "Responsabilidad civil. PENDIENTE."),
        ("Presupuesto de captacion", 0, "Ads. A cero, captas solo con tu tiempo."),
        ("Cuota de autonomos", 300, "PENDIENTE: depende de tarifa plana y forma juridica."),
        ("Lo que quieres cobrar tu al mes", 1200, "La cifra que convierte esto en un trabajo y no en un hobby."),
    ]:
        _fila(ws, fila, [etiqueta, valor, None, None, None, nota],
              [None, EUR0], editable=True)
        fila += 1
    estructura = f"SUM($B${PANEL_COSTES}:$B${PANEL_COSTES + 4})"
    cuota = f"$B${PANEL_COSTES + 5}"
    retirada = f"$B${PANEL_COSTES + 6}"
    _fila(ws, fila, [
        "Estructura (sin cuota ni retirada)", f"={estructura}", None, None, None,
        "Es el minimo que hay que pagar aunque no cobres nada.",
    ], [None, EUR0], negrita=True)
    fila += 1
    _fila(ws, fila, [
        "Salida total de caja al mes",
        f"={estructura}+{cuota}+{retirada}", None, None, None,
        "Estructura, cuota y tu retirada.",
    ], [None, EUR0], negrita=True)
    salida_total = f"$B${fila}"
    fila += 1
    _fila(ws, fila, ["Caja inicial", 4000, None, None, None,
                     "El vault cita ~4.000 EUR iniciales. PENDIENTE confirmar."],
          [None, EUR0], editable=True)
    caja_inicial = f"$B${fila}"
    fila += 2

    fila = _seccion(ws, fila, "5 · Lo que contesta el modelo")
    _cabecera(ws, fila, ["Pregunta", "Respuesta", "", "", "", "Como se calcula"])
    fila += 1
    assert fila == PANEL_RESULTADOS, (
        f"resultados en {fila}, se espera {PANEL_RESULTADOS}")
    resultados = [
        ("Contribucion por cuenta y mes",
         f"=({arpu}*(1-{impagos}))-{cogs_medio}", EUR,
         "Lo que deja una cuenta despues de lo que cuesta servirla en dinero. "
         "Tu tiempo no entra aqui: entra como limite de capacidad."),
        ("Cuentas para cubrir solo la estructura",
         f"=IF($B${PANEL_RESULTADOS}<=0,\"-\",ROUNDUP({estructura}/"
         f"$B${PANEL_RESULTADOS},0))", NUM,
         "Servidores, herramientas, gestoria y seguro."),
        ("Cuentas para cubrir estructura y cuota",
         f"=IF($B${PANEL_RESULTADOS}<=0,\"-\",ROUNDUP(({estructura}+{cuota})/"
         f"$B${PANEL_RESULTADOS},0))", NUM,
         "El minimo para no poner dinero cada mes."),
        ("Cuentas para pagarte lo que quieres",
         f"=IF($B${PANEL_RESULTADOS}<=0,\"-\",ROUNDUP({salida_total}/"
         f"$B${PANEL_RESULTADOS},0))", NUM,
         "El equilibrio de verdad: cuando esto te da de comer."),
        ("Cuentas que puedes atender tu solo",
         "=Horas_del_founder!$B$9", NUM,
         "Donde el soporte se come todas tus horas y no queda ninguna para "
         "vender. A partir de ahi, o contratas o dejas de crecer."),
        ("¿Te da el tiempo para llegar al equilibrio?",
         f"=IF(N($B${PANEL_RESULTADOS + 3})=0,\"-\","
         f"IF($B${PANEL_RESULTADOS + 4}>=$B${PANEL_RESULTADOS + 3},"
         f"\"Si: cabe en tus horas\","
         f"\"NO: harian falta mas horas o alguien mas\"))", None,
         "Compara el equilibrio con tu capacidad. Es la pregunta que decide si "
         "el plan es posible."),
        ("Mes en que dejas de perder dinero",
         "=Rampa_36m!$B$6", NUM,
         "Primer mes con resultado positivo, ya con tu retirada dentro."),
        ("Caja minima por el camino",
         "=Rampa_36m!$B$7", EUR0,
         "El punto mas bajo: el dinero que tienes que poder aguantar."),
        ("Cuentas al mes 36",
         "=Rampa_36m!$B$8", NUM,
         "Hasta donde llega la rampa con tus horas."),
    ]
    for etiqueta, formula, formato, explicacion in resultados:
        _fila(ws, fila, [etiqueta, formula, None, None, None, explicacion],
              [None, formato], negrita=True)
        fila += 1

    celda_veredicto = f"$B${PANEL_RESULTADOS + 5}"
    ws.conditional_formatting.add(
        f"B{PANEL_RESULTADOS + 5}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("NO",{celda_veredicto}))'],
                    font=Font(name=FUENTE, size=10, bold=True, color=STOP)))
    ws.conditional_formatting.add(
        f"B{PANEL_RESULTADOS + 5}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("Si:",{celda_veredicto}))'],
                    font=Font(name=FUENTE, size=10, bold=True, color=OKC)))

    fila += 1
    _nota(ws, fila,
          "Este libro no incluye IVA: se repercute y se ingresa, asi que no es "
          "ni ingreso ni gasto, solo un desfase de caja que la gestoria ordena "
          "por trimestres. Tampoco incluye IRPF ni impuesto de sociedades: con "
          "resultado negativo no hay base, y cuando la haya la cifra depende de "
          "la forma juridica, que esta sin decidir.", color=WARN)

    return {
        "arpu": f"Panel!{arpu}", "cogs": f"Panel!{cogs_medio}",
        "churn_nuevo": f"Panel!{churn_nuevo}",
        "churn_maduro": f"Panel!{churn_maduro}",
        "dias_prueba": f"Panel!{dias_prueba}", "impagos": f"Panel!{impagos}",
        "anual": f"Panel!{anual}", "horas": f"Panel!{horas}",
        "horas_alta": f"Panel!{horas_alta}", "min_nueva": f"Panel!{min_nueva}",
        "min_madura": f"Panel!{min_madura}", "objetivo": f"Panel!{objetivo}",
        "crecimiento": f"Panel!{crecimiento}",
        "estructura": f"Panel!{estructura}".replace("SUM($B$", "SUM(Panel!$B$"),
        "cuota": f"Panel!{cuota}", "retirada": f"Panel!{retirada}",
        "salida_total": f"Panel!{salida_total}",
        "caja_inicial": f"Panel!{caja_inicial}",
        "contribucion": f"Panel!$B${PANEL_RESULTADOS}",
    }


# ------------------------------------------------- HORAS DEL FOUNDER ------
def horas_del_founder(wb, ref):
    ws = _hoja(wb, "Horas_del_founder")
    _anchos(ws, {"A": 34, "B": 14, "C": 14, "D": 14, "E": 14, "F": 48})

    fila = _titulo(
        ws, "Tu tiempo puesto en numeros",
        "En un negocio de una persona, el limite no es el mercado: son las horas. "
        "Cada cuenta nueva consume tiempo de venta y puesta en marcha una vez, y "
        "tiempo de soporte todos los meses. Cuando el soporte se come las horas, "
        "no quedan para vender y la cartera deja de crecer sola.",
    )

    _cabecera(ws, fila, ["Concepto", "Valor", "", "", "", "Nota"])
    fila += 1
    _fila(ws, fila, ["Horas al mes para vender y atender",
                     f"={ref['horas']}", None, None, None,
                     "Del Panel."], [None, DEC])
    fila += 1
    _fila(ws, fila, ["Soporte de una cuenta asentada (horas/mes)",
                     f"={ref['min_madura']}/60", None, None, None,
                     "Los minutos del Panel pasados a horas."], [None, DEC])
    fila += 1
    _fila(ws, fila, ["Cuentas que llenan tus horas solo con soporte",
                     f"=IF(B{fila - 1}<=0,\"sin limite\","
                     f"ROUNDDOWN(B{fila - 2}/B{fila - 1},0))", None, None, None,
                     "A partir de aqui no te queda ni una hora para vender."],
          [None, NUM], negrita=True)
    assert fila == 9, f"la fila del techo es {fila} y el Panel espera 9"
    fila += 2

    _cabecera(ws, fila, ["Cuentas atendidas", "Horas de soporte",
                         "% de tus horas", "Horas libres para vender",
                         "Altas que puedes cerrar", "Situacion"])
    fila += 1
    primera = fila
    for cuentas in (10, 25, 50, 75, 100, 150, 200, 300):
        _fila(ws, fila, [
            cuentas,
            f"=A{fila}*{ref['min_madura']}/60",
            f"=IF({ref['horas']}=0,0,B{fila}/{ref['horas']})",
            f"=MAX(0,{ref['horas']}-B{fila})",
            f"=IF({ref['horas_alta']}<=0,0,ROUNDDOWN(D{fila}/"
            f"{ref['horas_alta']},0))",
            f"=IF(C{fila}>=1,\"Ya no puedes vender: solo atiendes\","
            f"IF(C{fila}>=0.7,\"Al limite: el soporte se come el mes\","
            f"IF(C{fila}>=0.4,\"Creces despacio\",\"Tienes margen para vender\")))",
        ], [NUM, DEC, PCT, DEC, NUM, None], banda=(cuentas in (50, 150)))
        fila += 1

    ws.conditional_formatting.add(
        f"C{primera}:C{fila - 1}",
        CellIsRule(operator="greaterThanOrEqual", formula=["0.7"],
                   font=Font(name=FUENTE, size=10, bold=True, color=STOP)))
    ws.conditional_formatting.add(
        f"C{primera}:C{fila - 1}",
        CellIsRule(operator="lessThan", formula=["0.4"],
                   font=Font(name=FUENTE, size=10, color=OKC)))

    fila += 1
    fila = _nota(ws, fila,
                 "Contratar no resuelve el problema por si solo: una persona de "
                 "soporte cuesta desde el primer dia y la cartera crece despacio. "
                 "Por eso el margen del producto tiene que venir de que el soporte "
                 "por cuenta baje —cerebro local, autoexplicacion, menos dudas—, "
                 "no de meter mas gente.")

    _cabecera(ws, fila, ["Si contratas a media jornada", "Valor", "", "", "",
                         "Nota"])
    fila += 1
    _fila(ws, fila, ["Coste cargado al mes", 900, None, None, None,
                     "Media jornada con seguridad social. Editable."],
          [None, EUR0], editable=True)
    coste_persona = f"$B${fila}"
    fila += 1
    _fila(ws, fila, [
        "Cuentas extra necesarias para pagarla",
        f"=IF({ref['contribucion']}<=0,\"-\","
        f"ROUNDUP({coste_persona}/{ref['contribucion']},0))",
        None, None, None,
        "Sobre las que ya tengas: la persona no trae clientes, libera horas.",
    ], [None, NUM], negrita=True)
    fila += 2
    _nota(ws, fila,
          "Esa cifra es la trampa del crecimiento: el coste entra de golpe y las "
          "altas llegan una a una. Antes de contratar conviene que la cartera "
          "pueda pagarlo ya, no que vaya a poder.")


# ------------------------------------------------------------- RAMPA -----
def rampa(wb, ref):
    ws = _hoja(wb, "Rampa_36m")
    _anchos(ws, {"A": 7, "B": 11, "C": 11, "D": 11, "E": 11, "F": 12, "G": 12,
                 "H": 13, "I": 13, "J": 13, "K": 13, "L": 14, "M": 14})

    fila = _titulo(
        ws, "36 meses reales: cuatro cohortes y tus horas",
        "Cada mes entran las altas que te permiten tus horas libres, no las que "
        "te gustaria. Las cuentas se siguen por edad porque las nuevas se van mas "
        "y preguntan mas. La proyeccion anterior suponia altas constantes y cero "
        "bajas; esta se frena sola cuando el soporte te ocupa el mes.",
    )

    # Resumen que lee el Panel.
    _fila(ws, fila, [
        "Mes en que dejas de perder dinero",
        f"=IFERROR(INDEX($A${RAMPA_INICIO}:$A${RAMPA_INICIO + 35},"
        f"MATCH(TRUE,INDEX($L${RAMPA_INICIO}:$L${RAMPA_INICIO + 35}>0,0),0)),"
        f"\"no llega en 36 meses\")",
    ], [None, NUM], negrita=True)
    assert fila == 6, f"el resumen empieza en {fila} y el Panel espera 6"
    fila += 1
    _fila(ws, fila, ["Caja minima por el camino",
                     f"=MIN($M${RAMPA_INICIO}:$M${RAMPA_INICIO + 35})"],
          [None, EUR0], negrita=True)
    fila += 1
    _fila(ws, fila, ["Cuentas al mes 36", f"=$H${RAMPA_INICIO + 35}"],
          [None, NUM], negrita=True)
    # Espejo local de las horas disponibles: el formato condicional de la
    # columna de horas no puede mirar a otra hoja sin que Excel se queje.
    ws.cell(row=fila, column=4, value="Horas disponibles").font = Font(
        name=FUENTE, size=9, color=MUTED)
    celda_horas = ws.cell(row=fila, column=5, value=f"={ref['horas']}")
    celda_horas.number_format = DEC
    celda_horas.font = Font(name=FUENTE, size=9, color=MUTED)
    fila += 1

    _cabecera(ws, fila, [
        "Mes", "Altas", "Mes 1", "Mes 2", "Mes 3", "Asentadas", "Cuentas",
        "Horas usadas", "Facturado", "Cobrado", "Contribucion",
        "Resultado", "Caja"])
    fila += 1
    assert fila == RAMPA_INICIO, f"la rampa empieza en {fila}"

    for mes in range(1, 37):
        f, ant = fila, fila - 1
        # Altas: el objetivo crece, pero solo se cumplen las que caben en las
        # horas que quedan tras atender a la cartera del mes anterior.
        soporte_previo = (
            "0" if mes == 1 else
            f"((C{ant}+D{ant}+E{ant})*{ref['min_nueva']}+F{ant}*"
            f"{ref['min_madura']})/60")
        altas = (f"=MAX(0,MIN(ROUND({ref['objetivo']}*"
                 f"(1+{ref['crecimiento']})^(A{f}-1),0),"
                 f"ROUNDDOWN(MAX(0,{ref['horas']}-{soporte_previo})/"
                 f"{ref['horas_alta']},0)))")
        _fila(ws, f, [
            mes,
            altas,
            f"=B{f}",
            "=0" if mes == 1 else f"=C{ant}*(1-{ref['churn_nuevo']})",
            "=0" if mes == 1 else f"=D{ant}*(1-{ref['churn_nuevo']})",
            "=0" if mes == 1 else
            f"=(F{ant}+E{ant})*(1-{ref['churn_maduro']})",
            f"=C{f}+D{f}+E{f}+F{f}",
            f"=B{f}*{ref['horas_alta']}+((C{f}+D{f}+E{f})*{ref['min_nueva']}"
            f"+F{f}*{ref['min_madura']})/60",
            # El alta no paga los dias de prueba de su primer mes.
            f"=G{f}*{ref['arpu']}-B{f}*{ref['arpu']}*{ref['dias_prueba']}/30",
            f"=I{f}*(1-{ref['impagos']})",
            f"=J{f}-G{f}*{ref['cogs']}",
            f"=K{f}-{ref['salida_total']}",
            f"={ref['caja_inicial']}+L{f}" if mes == 1 else f"=M{ant}+L{f}",
        ], [NUM, NUM, DEC, DEC, DEC, DEC, DEC, DEC, EUR0, EUR0, EUR0, EUR0,
            EUR0], banda=(mes % 12 == 0))
        fila += 1

    ws.conditional_formatting.add(
        f"L{RAMPA_INICIO}:M{RAMPA_INICIO + 35}",
        CellIsRule(operator="lessThan", formula=["0"],
                   font=Font(name=FUENTE, size=10, color=STOP)))
    ws.conditional_formatting.add(
        f"L{RAMPA_INICIO}:M{RAMPA_INICIO + 35}",
        CellIsRule(operator="greaterThanOrEqual", formula=["0"],
                   font=Font(name=FUENTE, size=10, color=OKC)))
    ws.conditional_formatting.add(
        f"H{RAMPA_INICIO}:H{RAMPA_INICIO + 35}",
        CellIsRule(operator="greaterThan", formula=["$E$8"],
                   font=Font(name=FUENTE, size=10, bold=True, color=STOP)))

    fila += 1
    _nota(ws, fila,
          "«Horas usadas» en rojo significa que ese mes no te dio la vida: o "
          "recortas altas, o alguien mas atiende. «Mes 1/2/3» son las cuentas "
          "por edad; «Asentadas», las que pasaron de tres meses. El salto de la "
          "caja en el mes del equilibrio no es magia: es que la cartera ya paga "
          "tu retirada.")


# -------------------------------------------------------- ESCENARIOS -----
def escenarios(wb, ref):
    ws = _hoja(wb, "Escenarios")
    _anchos(ws, {"A": 40, "B": 16, "C": 16, "D": 16, "E": 10, "F": 46})

    fila = _titulo(
        ws, "Tres futuros, y cual de ellos aguanta",
        "Mismos costes por cuenta, distinta velocidad y distinta suerte con las "
        "bajas. Para usar uno, copia sus valores al Panel: el libro entero se "
        "recalcula. No hay selector automatico a proposito, para que quede por "
        "escrito que escenario estas mirando.",
    )

    _cabecera(ws, fila, ["Palanca", "Prudente", "Base", "Optimista", "",
                         "Por que ese valor"])
    fila += 1
    palancas = [
        ("Altas objetivo al mes", 3, 5, 8, NUM,
         "El piloto comprometido son 3-5 negocios. Ocho al mes exige "
         "prescriptores funcionando."),
        ("Crecimiento mensual del objetivo", 0.02, 0.05, 0.10, PCT,
         "Sin presupuesto de ads, el crecimiento es boca a boca."),
        ("Bajas los tres primeros meses", 0.12, 0.08, 0.05, PCT,
         "Cuanto peor sea el arranque, mas se va la gente pronto."),
        ("Bajas despues", 0.06, 0.04, 0.02, PCT,
         "Un producto que ya esta en la rutina del negocio retiene."),
        ("Horas al mes para vender y atender", 40, 60, 90, NUM,
         "Depende de cuanto producto tengas que seguir construyendo."),
        ("Minutos de soporte, cuenta nueva", 45, 30, 20, NUM,
         "Baja si el producto se explica solo."),
        ("Retirada mensual del founder", 1500, 1200, 1200, EUR0,
         "Lo prudente no es cobrar menos: es necesitar mas caja."),
    ]
    for etiqueta, prudente, base, optimista, formato, nota in palancas:
        _fila(ws, fila, [etiqueta, prudente, base, optimista, None, nota],
              [None, formato, formato, formato])
        fila += 1

    fila += 1
    fila = _nota(ws, fila,
                 "El escenario prudente no es pesimismo: es el que hay que poder "
                 "aguantar. Si solo sobrevives en el optimista, el plan no es un "
                 "plan.")

    _cabecera(ws, fila, ["Lo que decide cada escenario", "", "", "", "", ""])
    fila += 1
    for pregunta, respuesta in [
        ("Si las bajas son del 12 % al principio",
         "La cartera se vacia casi tan rapido como entra: cada alta cuesta tres "
         "horas tuyas y dura poco mas de ocho meses."),
        ("Si solo tienes 40 horas al mes",
         "El soporte alcanza tus horas mucho antes y el crecimiento se para sin "
         "que el mercado tenga nada que ver."),
        ("Si el soporte baja de 30 a 20 minutos",
         "Es la palanca que mas cuentas te regala sin vender ni una mas. Ahi es "
         "donde paga el cerebro local."),
    ]:
        _fila(ws, fila, [pregunta, respuesta], [None, None])
        ws.merge_cells(start_row=fila, start_column=2, end_row=fila, end_column=6)
        ws.cell(row=fila, column=2).alignment = Alignment(wrap_text=True,
                                                          vertical="top")
        ws.row_dimensions[fila].height = 30
        fila += 1


# ---------------------------------------------------------- FUENTES ------
def fuentes(wb):
    ws = _hoja(wb, "Que_es_dato_y_que_no")
    _anchos(ws, {"A": 40, "B": 18, "C": 16, "D": 66})

    fila = _titulo(
        ws, "Que cifra es un dato y cual es una suposicion",
        "Con cero clientes de pago, casi todo este libro es una hipotesis. "
        "Separarlo es lo unico que impide confundir un escenario con una "
        "prevision. En rojo, lo que no esta medido y mas mueve el resultado.",
    )

    _cabecera(ws, fila, ["Cifra", "Valor", "Estado", "Origen o por que falta"])
    fila += 1
    entradas = [
        ("Precios 29 / 49 / 99", "Adoptado", "DATO",
         "Decision del 15/07/2026, y coincide con el catalogo del codigo."),
        ("Coste de software por cuenta", "1,48 / 3,04 / 18,47", "CALCULADO",
         "Analisis del 15/07/2026 sobre tarifas publicadas de Stripe, Meta, "
         "Anthropic, Groq y Railway."),
        ("Plataforma fija por cuenta", "0,07 EUR", "CALCULADO",
         "7 EUR/mes repartidos entre 100 cuentas, segun el libro editado el "
         "17/09/2026."),
        ("Mezcla 55 / 35 / 10", "Supuesto", "SIN MEDIR",
         "Nadie ha comprado todavia: el reparto real puede ser cualquiera."),
        ("Bajas mensuales", "8 % y 4 %", "SIN MEDIR",
         "No hay clientes de pago. Es la cifra que mas mueve el modelo."),
        ("Horas disponibles al mes", "60", "SIN MEDIR",
         "Depende de cuanto producto sigas construyendo tu."),
        ("Horas por alta", "3", "SIN MEDIR",
         "El analisis cifra el onboarding en 30-120 minutos; vender no esta "
         "medido."),
        ("Minutos de soporte", "30 y 12", "SIN MEDIR",
         "Los 12 minutos salen del analisis; los 30 de cuenta nueva son una "
         "suposicion."),
        ("Recibos no cobrados", "3 %", "SIN MEDIR",
         "Se sabra con la primera remesa real de Stripe."),
        ("Estructura mensual", "160 EUR", "PENDIENTE",
         "Servidores, herramientas, gestoria y seguro: faltan las facturas "
         "reales, como recoge la hoja de datos pendientes del libro anterior."),
        ("Cuota de autonomos", "300 EUR", "PENDIENTE",
         "Depende de tarifa plana y de la forma juridica, sin decidir."),
        ("Retirada del founder", "1.200 EUR", "DECISION",
         "No es un dato ni un supuesto: es lo que decidas cobrar."),
        ("Caja inicial", "4.000 EUR", "PENDIENTE",
         "El vault cita esa cifra inicial; falta confirmarla."),
        ("Clientes de pago hoy", "0", "DATO",
         "Por eso este libro es prospectivo y lo dice en la primera hoja."),
    ]
    for cifra, valor, estado, origen in entradas:
        _fila(ws, fila, [cifra, valor, estado, origen], [None, None, None, None])
        ws.cell(row=fila, column=4).alignment = Alignment(wrap_text=True,
                                                          vertical="top")
        if estado in ("SIN MEDIR", "PENDIENTE"):
            for columna in range(1, 5):
                ws.cell(row=fila, column=columna).font = Font(
                    name=FUENTE, size=10,
                    color=STOP if estado == "SIN MEDIR" else WARN)
        ws.row_dimensions[fila].height = 30
        fila += 1

    fila += 1
    _nota(ws, fila,
          "Lo que convierte esto en un modelo y no en un escenario: tres a cinco "
          "clientes de pago y treinta dias midiendo bajas, minutos de soporte por "
          "cuenta y cuantas horas te cuesta cerrar una venta. Con esas tres "
          "cifras medidas, las demas dejan de importar tanto.")


def main() -> int:
    wb = Workbook()
    ref = panel(wb)
    horas_del_founder(wb, ref)
    rampa(wb, ref)
    escenarios(wb, ref)
    fuentes(wb)
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    wb.save(DESTINO)
    print(f"Escrito: {DESTINO}")
    print("Hojas:", ", ".join(h.title for h in wb.worksheets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
