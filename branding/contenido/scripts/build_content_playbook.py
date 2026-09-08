from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "contenido"
OUTPUT = OUTPUT_DIR / "Plan-editorial-y-guiones-Noesis.docx"
LOGO = ROOT / "logos" / "png" / "lockup" / "noesis-logo-primary-1024.png"

FOREST = "14463B"
TEAL = "2E8B74"
CREAM = "F4F1E8"
INK = "15211C"
MUTED = "5D6B66"
SAGE = "E4EFE9"
WHITE = "FFFFFF"
AMBER = "B7831F"
AMBER_SOFT = "F5EDD6"
RED = "C0533F"
LIGHT = "FAF8F3"
BORDER = "D9DCE3"


def rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def set_run(run, *, name="Aptos", size=10.5, color=INK, bold=False, italic=False):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rpr.rFonts.set(qn("w:ascii"), name)
    rpr.rFonts.set(qn("w:hAnsi"), name)
    run.font.size = Pt(size)
    run.font.color.rgb = rgb(color)
    run.bold = bold
    run.italic = italic


def shade_cell(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=70, start=120, bottom=70, end=120):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_table_geometry(table, widths: list[int], indent=120):
    total = sum(widths)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(total))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent))
    tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for index, cell in enumerate(row.cells):
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(widths[index]))
            tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def set_cell_border(cell, color=BORDER, size="6"):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:color"), color)


def set_paragraph_shading(paragraph, fill: str):
    p_pr = paragraph._p.get_or_add_pPr()
    shd = p_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        p_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def add_page_field(paragraph):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, text, end])
    set_run(run, size=8.5, color=MUTED)


def set_picture_alt(inline_shape, *, title: str, description: str):
    """Añade nombre y texto alternativo a una imagen inline del DOCX."""
    doc_pr = inline_shape._inline.docPr
    doc_pr.set("title", title)
    doc_pr.set("descr", description)


def configure_document(doc: Document):
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.72)
    section.left_margin = Inches(0.82)
    section.right_margin = Inches(0.82)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)
    section.different_first_page_header_footer = True

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Aptos"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Aptos")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Aptos")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = rgb(INK)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    style_tokens = (
        ("Title", "Georgia", 30, FOREST, 0, 8),
        ("Subtitle", "Aptos", 13, MUTED, 0, 18),
        ("Heading 1", "Georgia", 18, FOREST, 16, 8),
        ("Heading 2", "Georgia", 14, TEAL, 12, 6),
        ("Heading 3", "Aptos", 11.5, FOREST, 9, 4),
    )
    for name, font, size, color, before, after in style_tokens:
        style = styles[name]
        style.font.name = font
        style._element.rPr.rFonts.set(qn("w:ascii"), font)
        style._element.rPr.rFonts.set(qn("w:hAnsi"), font)
        style.font.size = Pt(size)
        style.font.color.rgb = rgb(color)
        style.font.bold = name != "Subtitle"
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
        # La plantilla vacía de Word puede heredar una línea azul en Title.
        # Se elimina de forma explícita para mantener la portada editorial limpia.
        ppr = style.element.get_or_add_pPr()
        p_bdr = ppr.find(qn("w:pBdr"))
        if p_bdr is not None:
            ppr.remove(p_bdr)

    for sec in doc.sections:
        header = sec.header
        hp = header.paragraphs[0]
        hp.paragraph_format.space_after = Pt(0)
        hr = hp.add_run("NOESIS  |  SISTEMA EDITORIAL")
        set_run(hr, size=8, color=TEAL, bold=True)
        footer = sec.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        fr = fp.add_run("BYNOESIS.COM  ·  ")
        set_run(fr, size=8.5, color=MUTED, bold=True)
        add_page_field(fp)


def add_title(doc, text, subtitle=None):
    p = doc.add_paragraph(style="Title")
    run = p.add_run(text)
    set_run(run, name="Georgia", size=30, color=FOREST, bold=True)
    if subtitle:
        p = doc.add_paragraph(style="Subtitle")
        run = p.add_run(subtitle)
        set_run(run, size=13, color=MUTED)


def add_heading(doc, text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    run = p.add_run(text)
    font = "Georgia" if level <= 2 else "Aptos"
    size = {1: 18, 2: 14, 3: 11.5}[level]
    color = FOREST if level != 2 else TEAL
    set_run(run, name=font, size=size, color=color, bold=True)
    return p


def add_body(doc, text, *, bold_label=None, italic=False, after=6, size=10.5, color=INK):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    if bold_label:
        label = p.add_run(bold_label)
        set_run(label, size=size, bold=True, color=FOREST)
    run = p.add_run(text)
    set_run(run, size=size, color=color, italic=italic)
    return p


def add_bullet(doc, text, *, level=0, size=10.3, after=3, color=INK):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.22 + level * 0.18)
    p.paragraph_format.first_line_indent = Inches(-0.12)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.12
    run = p.add_run(text)
    set_run(run, size=size, color=color)
    return p


def add_callout(doc, text, *, label=None, fill=SAGE, accent=FOREST, size=11):
    table = doc.add_table(rows=1, cols=1)
    set_table_geometry(table, [9360])
    cell = table.cell(0, 0)
    shade_cell(cell, fill)
    set_cell_border(cell, color=fill, size="0")
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    if label:
        run = p.add_run(f"{label.upper()}  ")
        set_run(run, size=8.5, color=accent, bold=True)
    run = p.add_run(text)
    set_run(run, name="Georgia", size=size, color=accent, bold=True)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)
    return table


def add_label_detail_table(doc, rows, *, label_width=2100, font_size=9.4, shaded=True):
    table = doc.add_table(rows=0, cols=2)
    for idx, (label, value) in enumerate(rows):
        cells = table.add_row().cells
        if shaded:
            shade_cell(cells[0], SAGE)
            shade_cell(cells[1], LIGHT if idx % 2 else WHITE)
        set_cell_border(cells[0])
        set_cell_border(cells[1])
        p0 = cells[0].paragraphs[0]
        p1 = cells[1].paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        p1.paragraph_format.space_after = Pt(0)
        set_run(p0.add_run(label), size=font_size, color=FOREST, bold=True)
        set_run(p1.add_run(value), size=font_size, color=INK)
    set_table_geometry(table, [label_width, 9360 - label_width])
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def add_matrix(doc, headers, rows, widths, *, font_size=8.9):
    table = doc.add_table(rows=1, cols=len(headers))
    header_cells = table.rows[0].cells
    set_repeat_table_header(table.rows[0])
    for i, header in enumerate(headers):
        shade_cell(header_cells[i], FOREST)
        set_cell_border(header_cells[i], color=FOREST)
        p = header_cells[i].paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        set_run(p.add_run(header), size=font_size, color=WHITE, bold=True)
    for row_idx, row in enumerate(rows):
        cells = table.add_row().cells
        for col_idx, value in enumerate(row):
            shade_cell(cells[col_idx], LIGHT if row_idx % 2 else WHITE)
            set_cell_border(cells[col_idx])
            p = cells[col_idx].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            set_run(p.add_run(value), size=font_size, color=INK)
    set_table_geometry(table, widths)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def page_break(doc):
    doc.add_page_break()


@dataclass(frozen=True)
class ContentCard:
    code: str
    title: str
    pillar: str
    format: str
    channels: str
    audience: str
    objective: str
    funnel: str
    hook: str
    idea: str
    script: tuple[str, ...]
    shots: tuple[str, ...]
    overlay: str
    caption: str
    cta: str
    kpi: str
    guardrail: str


CARDS = [
    ContentCard(
        "T00", "Hola, somos Xavier y Miquel", "Confianza y marca", "Founder video · 45–60 s",
        "Instagram + LinkedIn + Facebook", "Quien llega por primera vez al perfil", "Poner cara al proyecto y fijar la promesa antes de pedir nada",
        "Presentación", "No empezamos queriendo hacer otro programa de facturas.",
        "Los dos socios se presentan, cuentan qué vieron trabajando con autónomos y qué están construyendo, sin enseñar todavía el producto.",
        ("Xavier: ‘Hola, soy Xavier’. Miquel: ‘Y yo Miquel’. Los dos: ‘Y esto es Noesis’.", "Miquel: ‘Vimos lo mismo en casi todos los negocios con los que trabajamos: acabas a las siete y a las diez sigues con facturas, tickets y mensajes sin contestar’.", "Xavier: ‘Yo vengo de cuentas y de arquitectura de software; Miquel, de dirección de empresas y procesos. Así que en vez de imaginarlo, preguntamos y lo construimos’.", "Miquel: ‘Noesis es un copiloto por WhatsApp: le hablas como a un compañero y te deja la agenda, los clientes, los documentos y las facturas ordenados’.", "Xavier: ‘Prepara el trabajo, pero lo que toca dinero, impuestos o a un cliente lo confirmas tú. Y a tu gestoría le llega revisable: no la sustituimos’.", "Miquel: ‘Estamos en piloto y queremos autónomos de servicios que nos digan qué falta’.", "Cierre, los dos a cámara: ‘Haz tu trabajo; Noesis te ordena el negocio’."),
        ("Un solo encuadre y una sola luz para los dos: se alternan en el mismo sitio o se graba un plano a dos con espacio para subtítulos.", "Espacio de trabajo real y ropa normal; nada de plató, pared vacía ni traje.", "Rótulo con nombre y papel el primer segundo de cada uno; sin música épica ni efectos.", "Como mucho dos planos de producto al mencionar el parte del día; el resto es cara y voz."),
        "SOMOS XAVIER Y MIQUEL · ESTO ES NOESIS", "Antes de enseñarte nada, queremos que sepas quién está detrás y por qué. Somos dos socios construyendo Noesis para autónomos de servicios.",
        "Si eres autónomo de servicios, escríbenos: queremos escucharte antes de venderte nada.", "Retención al 75 % + comentarios cualificados + visitas al perfil",
        "No inventar usuarios, clientes ni resultados: se dice ‘estamos construyendo’ y ‘piloto’. No prometer presentación fiscal ni sustitución de la gestoría, ni vender la IA como argumento. En voz se dice Noesis; ‘bynoesis’ solo aparece en pantalla como web y usuario."),
    ContentCard(
        "P00", "Qué es Noesis, explicado desde cero", "Marca y producto", "Explicador a cámara · 45–60 s",
        "Instagram + LinkedIn + Facebook", "Quien no ha oído hablar de Noesis todavía", "Definir el producto entero, sin escenas ni personajes, para quien parte de cero",
        "Presentación", "Noesis lleva la oficina de tu negocio mientras tú haces el trabajo. Así es como lo hace.",
        "Explicación pura a cámara, sin dramatizar ningún caso concreto: qué es, cómo se usa y qué no hace, en el orden en que ocurre de verdad.",
        ("‘Noesis es un copiloto de negocio para autónomos de servicios: fontanería, electricidad, reformas, limpieza, mantenimiento’.", "‘Funciona por WhatsApp. Le hablas por texto o por audio, como le hablarías a alguien de tu equipo’.", "‘Le cuentas lo que ha pasado en el día y Noesis lo convierte en agenda, en cliente nuevo, en factura o en aviso de cobro’.", "‘Si le mandas un ticket o un documento, lo guarda y lo clasifica; si duda, te lo deja pendiente en vez de inventárselo’.", "‘Al final del día te da el parte: qué ha pasado, qué falta por cerrar y quién te debe dinero’.", "‘Todo lo que toca dinero, impuestos o a un cliente te lo pregunta antes de hacerlo: confirmas tú, no decide solo’.", "‘No es un ERP: sin menús ni pantallas que aprender. Y no sustituye a tu gestoría: le deja el trabajo preparado y revisable’.", "Cierre: ‘Eso es Noesis. Haz tu trabajo; nosotros te ordenamos el negocio’."),
        ("A cámara, plano fijo, espacio de trabajo real; sin actuar ninguna escena, solo explicar.", "Microcapturas de pantalla como apoyo visual —WhatsApp con audio, ticket clasificado, parte del día—; nunca sustituyen a la explicación hablada.", "Datos de prueba y rótulo ‘demo’ en toda captura; WhatsApp operativo rotulado como piloto mientras Meta no esté validado.", "Ritmo pausado y claro: es el vídeo que define qué es Noesis para quien todavía no sabe nada."),
        "NOESIS LLEVA LA OFICINA. TÚ HACES EL TRABAJO.", "Qué es Noesis, explicado desde cero: el copiloto de negocio por WhatsApp para autónomos de servicios. Sin menús que aprender y sin decisiones que no confirmes tú.",
        "Guárdalo si es la primera vez que oyes hablar de Noesis.", "Retención al 75 % + guardados + compartidos",
        "No enseñar WhatsApp operativo como disponible ni datos reales. No decir ‘100 % automático’, ‘sin errores’ ni ‘te lleva la fiscalidad’. Sin precios ni planes: esta pieza define el producto, no lo vende."),
    ContentCard(
        "E01", "La segunda jornada", "Identificación emocional", "Reel físico · 25–35 s",
        "Instagram + Facebook", "Autónomo de oficio que termina tarde", "Conseguir compartidos y reconocimiento",
        "Descubrimiento", "Terminas ocho horas de trabajo. Y empiezan las otras dos.",
        "Contrastar el final del trabajo físico con la administración nocturna.",
        ("Plano 1: cierras la furgoneta y dices: ‘Por fin, terminado’.", "Plano 2: llegas a casa; sobreimpreso: ‘facturas, tickets, mañana, cobros’.", "Plano 3: miras el móvil y dices: ‘Vale… ahora empieza mi otro trabajo’.", "Cierre: ‘Tu negocio no debería vivir entero en tu cabeza’."),
        ("Exterior real al acabar la jornada.", "Corte rápido a mesa de casa con papeles y móvil.", "Primer plano final, tono cómplice; no dramatizar en exceso."),
        "TRABAJO TERMINADO ≠ DÍA TERMINADO", "Si al llegar a casa todavía te queda llevar el negocio, no eres el único.",
        "Compártelo con quien siempre acaba dos veces.", "Compartidos + retención al 75 %", "No presentar Noesis hasta el último segundo; la pieza debe funcionar sin vender."),
    ContentCard(
        "E02", "‘Es una cosita rápida’", "Identificación emocional", "Reel sketch · 20–30 s",
        "Instagram + Facebook", "Fontanería, electricidad, reformas y mantenimiento", "Humor reconocible y alcance",
        "Descubrimiento", "Cuando un cliente dice: ‘Es una cosita rápida’.",
        "Representar cómo una petición breve se convierte en visita, compra, presupuesto y seguimiento.",
        ("Cliente fuera de cámara: ‘Es una cosita rápida’.", "Tú miras a cámara; aparecen cuatro rótulos: visita, material, presupuesto, volver.", "Corte: calendario lleno y una llamada entrante.", "Remate: ‘Rápida era la frase’."),
        ("Una sola localización de trabajo.", "Usar cambios de expresión y rótulos, no actores adicionales.", "Sonido de notificación por cada nueva tarea."),
        "RÁPIDA ERA LA FRASE", "El trabajo puede ser pequeño. Gestionarlo casi nunca lo es.",
        "¿Cuál ha sido tu ‘cosita rápida’ más larga?", "Comentarios + compartidos", "No ridiculizar al cliente; el chiste es la carga administrativa."),
    ContentCard(
        "E03", "El ticket desaparecido", "Identificación emocional", "Reel POV · 20–25 s",
        "Instagram + Facebook", "Autónomo que compra materiales", "Normalizar un dolor cotidiano y abrir paso a documentos",
        "Descubrimiento", "Ese ticket que necesitas solo desaparece cuando lo necesitas.",
        "Búsqueda absurda de un ticket entre furgoneta, bolsillo, WhatsApp y guantera.",
        ("Rótulo: ‘Yo guardándolo en un sitio seguro’.", "Montaje de cuatro escondites imposibles.", "Mensaje de la gestoría: ‘¿Tienes el ticket?’.", "Miras a cámara con el bolsillo vacío."),
        ("Planos de 2–3 segundos.", "Props reales, sin mostrar datos personales.", "Final silencioso para que el gesto haga el remate."),
        "EL SITIO SEGURO: DESCONOCIDO", "Los papeles pequeños acaban creando problemas grandes.",
        "Guárdalo para el próximo ticket fantasma.", "Guardados + finalizaciones", "Si aparece el producto, mostrar captura o envío y revisión, no clasificación infalible."),
    ContentCard(
        "E04", "La factura fantasma", "Identificación emocional", "Reel diálogo · 25–35 s",
        "Instagram + Facebook", "Autónomo con trabajos recurrentes", "Conectar olvido de facturar con pérdida de control",
        "Descubrimiento", "¿Te ha pasado terminar un trabajo y acordarte de facturarlo tres semanas después?",
        "El trabajo existe, el ingreso no, porque nadie convirtió el final en factura.",
        ("Tú: ‘Trabajo terminado’.", "Calendario acelera: una semana, dos, tres.", "Tú: ‘¿Esto lo llegué a facturar?’.", "Cierre: ‘Lo terminado también hay que cerrarlo en el negocio’."),
        ("Plano de obra o herramienta guardada.", "Transición de calendario en pantalla.", "Acabar con una libreta o app abierta, sin enseñar datos reales."),
        "TERMINADO NO SIEMPRE SIGNIFICA FACTURADO", "El olvido no se nota hoy. Se nota cuando miras la caja.",
        "¿Cuántas veces te ha pasado este año?", "Comentarios cualificados + compartidos", "No afirmar una cifra de dinero perdido sin evidencia."),
    ContentCard(
        "E05", "Día 29: llama la gestoría", "Identificación emocional", "Reel sketch · 20–30 s",
        "Instagram + Facebook", "Autónomos que trabajan con gestoría", "Hacer visible el caos documental sin culpar",
        "Descubrimiento", "Día 29. Tu gestoría ya sabe que vas a decir: ‘te lo mando ahora’.",
        "La llamada trimestral que dispara una búsqueda general de documentos.",
        ("Pantalla: ‘Gestoría llamando’.", "Tú respondes muy seguro: ‘Sí, lo tengo todo’.", "Corte a mesa/furgoneta buscando tickets.", "Remate: ‘Todo… repartido por siete sitios’."),
        ("Usar notificación ficticia, no un número real.", "Plano abierto del caos controlado.", "Cerrar con gesto de ‘otra vez’."),
        "TODO, PERO EN SIETE SITIOS", "La gestoría no necesita perseguirte; necesita que el negocio llegue ordenado.",
        "Etiqueta a quien cada trimestre vive esta película.", "Compartidos + menciones", "No prometer presentación fiscal automática; Noesis prepara y el profesional decide."),
    ContentCard(
        "E06", "Facturar más no siempre es ganar más", "Emocional + racional", "Reel a cámara · 30–40 s",
        "Instagram + LinkedIn", "Autónomo ocupado que no conoce margen", "Romper una creencia y generar guardados",
        "Consideración", "Puedes estar lleno de trabajo y aun así no saber qué trabajo te deja dinero.",
        "Separar actividad, facturación, cobro y margen en lenguaje simple.",
        ("‘Tener más trabajos no siempre significa ganar más’.", "‘Uno puede llevar más horas, más material y más desplazamientos’.", "‘Si solo miras lo facturado, no sabes qué te queda’.", "‘Empieza por apuntar horas y costes por trabajo’."),
        ("A cámara, taller o furgoneta de fondo.", "Rótulos: horas · material · desplazamiento · cobro.", "Sin gráficos complejos."),
        "DE CADA 100 €, ¿CUÁNTO TE QUEDA?", "Control no es mirar más números. Es entender qué trabajo merece la pena.",
        "Guárdalo y revisa un trabajo esta semana.", "Guardados + visitas al perfil", "No usar EBITDA ni tecnicismos; no inferir rentabilidad con datos incompletos."),

    ContentCard(
        "R01", "¿Fue rentable este trabajo?", "Valor práctico", "Carrusel · 6 diapositivas",
        "Instagram + Facebook + LinkedIn", "Autónomo que presupuesta por intuición", "Enseñar una revisión mínima por trabajo",
        "Consideración", "No mires solo cuánto cobraste. Mira lo que te costó hacerlo.",
        "Checklist de cuatro datos: ingreso, material, horas y desplazamiento/ayuda externa.",
        ("S1: ‘¿Fue rentable este trabajo?’.", "S2: importe cobrado.", "S3: material y compras.", "S4: horas propias y de equipo.", "S5: desplazamiento y subcontratas.", "S6: ‘Lo que queda antes de impuestos es la señal; compáralo con otros trabajos’."),
        ("Plantilla crema; una cifra conceptual por slide.", "Iconos simples, sin capturas de software.", "Última slide con checklist descargable visualmente."),
        "COBRADO − COSTES − TIEMPO", "Una revisión imperfecta pero constante vale más que no mirar nunca.",
        "Guárdalo para el próximo trabajo que cierres.", "Guardados + deslizados completos", "Aclarar que es una lectura operativa, no cálculo fiscal definitivo."),
    ContentCard(
        "R02", "Cinco datos antes de enviar un presupuesto", "Valor práctico", "Carrusel · 7 diapositivas",
        "Instagram + Facebook", "Servicios a domicilio", "Reducir presupuestos incompletos y revisiones",
        "Consideración", "Un presupuesto rápido puede salir caro si faltan estas cinco cosas.",
        "Checklist: alcance, materiales, horas, desplazamiento, condiciones/validez.",
        ("S1: promesa.", "S2: qué incluye y qué no.", "S3: materiales y calidades.", "S4: horas/equipo.", "S5: desplazamiento y retirada.", "S6: forma de pago y validez.", "S7: revisión final y CTA."),
        ("Diseño de checklist con casillas.", "Ejemplo de una línea buena y una ambigua.", "Nada de letra pequeña ilegible."),
        "ANTES DE ENVIAR: ALCANCE · COSTE · TIEMPO · CONDICIONES", "Un presupuesto claro ahorra conversaciones y protege el margen.",
        "Envíatelo por WhatsApp y úsalo como lista.", "Guardados + envíos", "No presentar el contenido como asesoramiento legal contractual."),
    ContentCard(
        "R03", "Recordatorio de cobro sin sonar agresivo", "Valor práctico", "Reel a cámara + plantilla · 25–35 s",
        "Instagram + Facebook", "Autónomo que evita reclamar", "Dar una acción inmediata y descargable",
        "Consideración", "Reclamar una factura no es discutir. Es recordar con claridad.",
        "Ofrecer un texto breve con factura, importe, vencimiento y siguiente paso.",
        ("‘Hola, Marta. Te escribo por la factura F-024, de 480 €, vencida el día 12’.", "‘¿Puedes confirmarme cuándo quedará abonada?’.", "‘Si ya la has pagado, ignora este mensaje. Gracias’.", "Explica: dato concreto, tono neutro, una pregunta."),
        ("A cámara 10 segundos.", "Después, plantilla grande en pantalla.", "Subtítulos completos y pausa para captura."),
        "CLARO, CONCRETO Y SIN DISCULPARTE", "Un buen recordatorio no acusa: identifica y pide una fecha.",
        "Guarda la plantilla y adáptala a tu tono.", "Guardados + compartidos", "No automatizar o enviar reclamaciones sin confirmación del titular."),
    ContentCard(
        "R04", "Facturado no es cobrado", "Valor práctico", "Carrusel comparativo · 6 diapositivas",
        "Instagram + LinkedIn", "Autónomo que mira solo facturación", "Educar sobre caja en lenguaje humano",
        "Consideración", "Puedes facturar 8.000 € y no tener 8.000 € disponibles.",
        "Explicar trabajo terminado, factura emitida, pago pendiente y dinero disponible.",
        ("S1: el mito.", "S2: trabajo terminado.", "S3: factura hecha.", "S4: factura vencida.", "S5: dinero cobrado.", "S6: ‘Gestiona cada paso, no solo el primero’."),
        ("Usar una línea temporal horizontal.", "Colores suaves para cada estado.", "Ejemplo hipotético claramente marcado."),
        "TRABAJO → FACTURA → COBRO → CAJA", "Tu negocio respira con lo cobrado, no con lo que existe solo en una factura.",
        "Revísalo con tus tres últimas facturas.", "Guardados + comentarios cualificados", "Etiquetar cualquier cantidad como ejemplo, no como caso real."),
    ContentCard(
        "R05", "Rutina de 10 minutos para los tickets", "Valor práctico", "Reel tutorial · 30–40 s",
        "Instagram + Facebook", "Autónomo que acumula documentos", "Crear un hábito sencillo",
        "Consideración", "Diez minutos los viernes evitan una tarde perdida al trimestre.",
        "Rutina: fotografiar, nombrar, vincular a trabajo y dejar pendiente lo dudoso.",
        ("‘Viernes, antes de cerrar’.", "‘1. Saca los tickets de cartera y furgoneta’.", "‘2. Haz una foto legible’.", "‘3. Apunta el trabajo o cliente’.", "‘4. Lo dudoso, a revisar; no lo inventes’.", "‘Cinco minutos ahora, menos ruido después’."),
        ("Plano cenital de mesa.", "Manos y documentos ficticios.", "Cronómetro discreto, sin acelerar tanto que no se entienda."),
        "FOTO · CONTEXTO · REVISIÓN", "Ordenar no significa decidirlo todo: significa saber qué está claro y qué falta revisar.",
        "Pruébalo este viernes y cuéntanos si te sirve.", "Guardados + respuestas a Stories", "Ocultar NIF, importes y datos de documentos usados en rodaje."),
    ContentCard(
        "R06", "Cuánto ganas realmente por hora", "Valor práctico", "Carrusel · 7 diapositivas",
        "Instagram + LinkedIn", "Autónomo que tarifa sin contar tiempo invisible", "Mejorar conciencia de precio y tiempo",
        "Consideración", "Tu hora no es solo la hora con la herramienta en la mano.",
        "Sumar visita, compra, viaje, mensajes, presupuesto, ejecución y cierre.",
        ("S1: pregunta.", "S2: visita.", "S3: compra y desplazamiento.", "S4: ejecución.", "S5: mensajes y presupuesto.", "S6: total cobrado ÷ horas reales.", "S7: comparar y aprender, no castigarse."),
        ("Reloj como recurso visual.", "Ejemplo hipotético simple.", "Última slide con huecos para que el usuario haga su cuenta."),
        "PRECIO COBRADO ÷ TODO EL TIEMPO", "El tiempo invisible también forma parte del trabajo.",
        "Guárdalo y calcula solo un trabajo, no todo el año.", "Guardados + deslizados completos", "No recomendar tarifas concretas sin conocer sector, zona y costes."),

    ContentCard(
        "P01", "De WhatsApp a documento ordenado", "Demostración de producto", "Screen demo + voz · 25–35 s",
        "Instagram + Facebook", "Autónomo móvil-first", "Mostrar el flujo documental sin exagerar",
        "Evaluación", "Mandas el ticket como siempre. Noesis te pide lo que falta y lo deja preparado.",
        "Mostrar un archivo de prueba entrando, clasificación propuesta y confirmación humana.",
        ("‘Envío este ticket de prueba’.", "‘Noesis lee los datos y propone gasto/ticket’.", "‘Si falta cliente o trabajo, me lo pregunta’.", "‘Yo confirmo y queda ordenado para revisar’."),
        ("Grabación 9:16 del flujo demo.", "Zoom a propuesta y botón de confirmar.", "Usar datos ficticios y el rótulo ‘DEMO / PILOTO’ si WhatsApp real no está validado."),
        "ENVÍAS · NOESIS PROPONE · TÚ CONFIRMAS", "Menos reenvíos y menos ‘¿dónde guardé esto?’. Siempre con revisión cuando hay dudas.",
        "Solicita acceso al piloto.", "Visitas al perfil + solicitudes", "No decir ‘automático al 100 %’. WhatsApp/Meta debe rotularse como piloto hasta validación real."),
    ContentCard(
        "P02", "Cliente nuevo detectado en una factura", "Demostración de producto", "Screen demo · 30–40 s",
        "Instagram + LinkedIn", "Autónomo con clientes nuevos frecuentes", "Probar que el sistema evita duplicados y pide confirmación",
        "Evaluación", "Si llega una factura con un cliente nuevo, Noesis no lo inventa ni lo mezcla: te lo propone.",
        "Comparar coincidencia exacta con cliente existente frente a alta editable pendiente.",
        ("‘Subo una factura de prueba’.", "‘Noesis busca una coincidencia exacta dentro de este negocio’.", "‘Si existe, la vincula como propuesta’.", "‘Si no existe, prepara un cliente nuevo editable’.", "‘Nada se consolida sin confirmar’."),
        ("Pantalla dividida: existente / nuevo.", "Enfatizar el estado ‘por confirmar’.", "No enseñar datos internos ni otros negocios."),
        "COINCIDENCIA EXACTA O ALTA POR CONFIRMAR", "Automatizar no es adivinar. Es preparar bien y preguntar cuando toca.",
        "¿Te ahorraría tiempo este flujo?", "DMs cualificados + solicitudes", "No mostrar emparejamiento por nombre ambiguo como si fuera seguro."),
    ContentCard(
        "P03", "Preparar una factura hablando", "Demostración de producto", "Screen demo conversacional · 30–45 s",
        "Instagram + Facebook", "Autónomo que trabaja por voz/móvil", "Enseñar la promesa central: conversación a borrador",
        "Evaluación", "‘Haz una factura a Marta por la reparación de hoy’. Noesis prepara; tú revisas y emites.",
        "Crear borrador desde una orden natural, mostrar resumen fiscal y confirmación final.",
        ("Orden: ‘Prepara una factura a Marta…’.", "Noesis pide el dato que falta, si falta alguno.", "Muestra cliente, concepto, base, IVA/IRPF aplicable y total.", "Usuario revisa.", "Cierre: ‘Emitir y enviar siempre requiere confirmación’."),
        ("Alternar conversación y vista previa.", "Mantener importes ficticios y redondos.", "Subrayar la pregunta de confirmación, no solo el PDF final."),
        "HABLAS → BORRADOR → REVISAS → EMITES", "La velocidad está en preparar. El control sigue siendo tuyo.",
        "Pide una demo con tu tipo de trabajo.", "Solicitudes de demo + finalizaciones", "No prometer validez fiscal externa no validada; usar ‘prepara’ y ‘borrador’."),
    ContentCard(
        "P04", "Recordatorio de cobro preparado", "Demostración de producto", "Screen demo + cara · 25–35 s",
        "Instagram + Facebook", "Autónomo con facturas pendientes", "Mostrar una acción útil con control humano",
        "Evaluación", "Noesis ve qué factura se retrasa y te prepara el mensaje. Tú decides si sale.",
        "Enseñar detección de vencida, mensaje propuesto y confirmación.",
        ("‘Esta factura lleva X días vencida’ — dato de demo.", "‘Noesis propone un mensaje con cliente, factura e importe’.", "‘Puedes editar el tono’.", "‘Solo se envía cuando confirmas’."),
        ("Comenzar con rostro y dolor.", "Cortar a pantalla para la propuesta.", "Volver al rostro para el cierre humano."),
        "NOESIS PREPARA. TÚ DECIDES.", "Reclamar deja de depender de acordarte, sin perder la relación con el cliente.",
        "Solicita acceso al piloto.", "Clics + solicitudes", "No enviar mensajes reales durante la grabación; usar entorno demo."),
    ContentCard(
        "P05", "El parte del día", "Demostración de producto", "Screen demo editorial · 30–45 s",
        "Instagram + LinkedIn", "Autónomo con muchas tareas abiertas", "Explicar el corazón del producto",
        "Evaluación", "No necesitas otro panel lleno de números. Necesitas saber qué toca hoy.",
        "Mostrar un parte que prioriza cobros, visitas, presupuesto y documento pendiente.",
        ("‘Buenos días: hoy lo primero es…’.", "Señala tres prioridades, no diez KPIs.", "Abre una acción: preparar recordatorio o presupuesto.", "Cierre: ‘La app es donde entiendes; Noesis te da el parte’."),
        ("Plano de pantalla limpio.", "Cursor lento, una acción cada vez.", "No recorrer todos los menús; mantener un único relato."),
        "QUÉ IMPORTA HOY · QUÉ PUEDE HACER NOESIS", "Orden no es tener más datos. Es que alguien te diga qué merece atención.",
        "¿Qué debería aparecer en tu parte de mañana?", "Comentarios cualificados + demos", "Usar datos demo coherentes; nunca simular actividad como si fuera un cliente real."),

    ContentCard(
        "T01", "Por qué estamos construyendo Noesis", "Confianza y marca", "Founder video · 45–60 s",
        "LinkedIn + Instagram", "Autónomos, gestorías y colaboradores", "Dar rostro, misión y motivación real",
        "Confianza", "No empezamos queriendo hacer otro programa de facturas.",
        "Explicar que el problema observado es el trabajo administrativo que continúa después del oficio.",
        ("‘Vimos que muchos autónomos terminan el trabajo y empiezan a llevar el negocio’.", "‘Agenda, clientes, documentos, facturas y cobros viven separados o en la cabeza’.", "‘Noesis nace para quitar ese ruido y dar control’.", "‘No para sustituir al profesional, sino para ser su mano derecha’."),
        ("Fundador a cámara, espacio real de trabajo.", "Intercalar 2–3 planos del producto.", "Sin música épica ni afirmaciones grandilocuentes."),
        "HAZ TU TRABAJO; NOESIS TE ORDENA EL NEGOCIO", "Estamos construyendo Noesis para que llevar el negocio no se coma el tiempo de hacer bien el oficio.",
        "Si eres autónomo de servicios, queremos escucharte.", "Comentarios cualificados + conversaciones", "Hablar desde la motivación y lo construido; no inventar número de usuarios o éxito."),
    ContentCard(
        "T02", "Por qué Noesis no quiere ser un ERP", "Confianza y categoría", "Founder post + carrusel",
        "LinkedIn", "Profesionales, gestorías, partners y early adopters", "Definir la categoría frente a software denso",
        "Confianza", "Un autónomo no necesita aprender cuarenta menús para entender su negocio.",
        "Contrastar operar hablando y entender con un parte frente a trabajar módulo por módulo.",
        ("Post: ‘Los ERP ordenan módulos. Nosotros queremos ordenar el día’.", "Explica WhatsApp como operación y app como control tranquilo.", "Cuenta por qué las acciones van antes que los datos.", "Cierra con una pregunta de investigación al público."),
        ("Carrusel 5 slides: problema, principio, ejemplo, control humano, pregunta.", "Capturas solo si refuerzan el concepto.", "Diseño sobrio de LinkedIn, no anuncio."),
        "MENOS MENÚS. MÁS CONTEXTO.", "La infraestructura puede ser potente sin obligar al usuario a vivir dentro de ella.",
        "¿Qué parte de tu software actual te obliga a pensar como un gestor?", "Comentarios de ICP + guardados", "No atacar marcas ni afirmar superioridad no probada."),
    ContentCard(
        "T03", "Por qué pedimos confirmación", "Confianza y seguridad", "Reel fundador + demo · 35–50 s",
        "Instagram + LinkedIn", "Usuarios preocupados por errores", "Convertir una fricción aparente en promesa de control",
        "Confianza", "Si afecta a dinero, impuestos o a un cliente, Noesis no debería decidir por ti.",
        "Enseñar tres momentos: emitir, reclamar y clasificar dudoso; todos con confirmación.",
        ("‘Automatizar no significa quitarte el control’.", "‘Noesis puede preparar una factura, un recordatorio o una clasificación’.", "‘Pero si es irreversible o dudoso, te pregunta’.", "‘La confianza se construye dejando claro qué sabe y qué no’."),
        ("A cámara para el principio.", "Tres microcapturas del producto.", "Cerrar con el botón de confirmar visible."),
        "PREPARAR RÁPIDO. CONFIRMAR LO IMPORTANTE.", "Diseñamos la automatización para ahorrar pasos, no para inventar decisiones.",
        "¿Qué acción no dejarías nunca sin confirmar?", "Comentarios cualificados + retención", "No presentar la confirmación como garantía absoluta; sigue siendo necesario revisar."),
    ContentCard(
        "T04", "Cómo evitamos mezclar negocios", "Confianza y seguridad", "Carrusel técnico-humano · 6 diapositivas",
        "LinkedIn + Instagram", "Autónomos, gestorías y prescriptores", "Explicar aislamiento sin jerga innecesaria",
        "Confianza", "La confianza empieza por una regla simple: cada dato pertenece a un solo negocio.",
        "Explicar aislamiento por cuenta, sesiones privadas, permisos y revisión, sin revelar detalles explotables.",
        ("S1: la regla.", "S2: cada acción lleva el contexto del negocio.", "S3: los accesos de gestoría son explícitos.", "S4: los documentos dudosos quedan pendientes.", "S5: las acciones sensibles requieren confirmación.", "S6: límites: auditoría y validaciones externas siguen siendo necesarias."),
        ("Diagramas simples, no código.", "Una empresa por columna, sin flechas cruzadas.", "Última slide con lenguaje honesto sobre el estado piloto."),
        "UN NEGOCIO · SU CONTEXTO · SUS PERMISOS", "Seguridad no es un icono: son límites que el producto aplica en cada operación.",
        "Guárdalo si evalúas herramientas para tu negocio.", "Guardados + conversaciones con partners", "No usar ‘100 % seguro’ ni afirmar auditorías externas todavía pendientes."),

    ContentCard(
        "G01", "Entrevista: el trabajo que nadie ve", "Investigación y comunidad", "Entrevista vertical · 45–60 s",
        "Instagram + LinkedIn", "Autónomo real de un oficio prioritario", "Aprender y construir cercanía antes de tener casos",
        "Investigación", "¿Qué parte de llevar tu negocio haces cuando ya has terminado de trabajar?",
        "Una pregunta, una respuesta y una conclusión del fundador; no forzar testimonio de Noesis.",
        ("Pregunta 1: ‘¿Qué haces al llegar a casa?’.", "Pregunta 2: ‘¿Qué se te suele quedar atrás?’.", "Pregunta 3: ‘¿Qué te gustaría resolver con un audio o mensaje?’.", "Cierre del founder: una frase de aprendizaje, sin vender."),
        ("Grabar en entorno real con permiso.", "Subtítulos literales, edición mínima.", "Recoger consentimiento específico de imagen y publicación."),
        "EL TRABAJO QUE NADIE VE", "Antes de construir promesas, escuchamos cómo se lleva de verdad un negocio de servicios.",
        "Cuéntanos qué tarea te sigue a casa.", "Respuestas cualitativas + entrevistas captadas", "No convertir una entrevista de investigación en testimonio comercial sin permiso explícito."),
    ContentCard(
        "G02", "El paquete que la gestoría sí puede revisar", "Gestoría y partners", "Carrusel + demo · 6 diapositivas",
        "LinkedIn + Facebook", "Gestorías y autónomos con gestor", "Explicar colaboración ordenada, no sustitución",
        "Evaluación", "Noesis no presenta por tu gestoría: prepara el trabajo para que llegue revisable.",
        "Mostrar documentos por periodo, pendientes, trazabilidad y paquete de revisión.",
        ("S1: problema: documentos repartidos.", "S2: orden por periodo y tipo.", "S3: pendientes visibles.", "S4: propuesta de datos, no verdad automática.", "S5: paquete para revisar.", "S6: la gestoría mantiene el criterio fiscal."),
        ("Capturas demo sin datos reales.", "Usar dos colores: preparado / pendiente.", "No mostrar envío o presentación fiscal como automática."),
        "NOESIS PREPARA. LA GESTORÍA REVISA.", "Menos persecución documental y más tiempo para el criterio profesional.",
        "Gestorías: solicitad una demostración del flujo.", "Demos de partners + guardados", "No decir que sustituye a la gestoría ni que presenta impuestos de forma autónoma."),
    ContentCard(
        "G03", "Caso piloto medible", "Prueba y conversión", "Caso en vídeo + carrusel",
        "Instagram + LinkedIn + web", "Prospectos similares al piloto", "Convertir evidencia real en confianza comercial",
        "Conversión", "Antes: [problema medido]. Después de 30 días: [resultado validado].",
        "Plantilla reservada para un caso con permiso, línea base y medición reproducible.",
        ("Contexto: oficio, tamaño y forma de trabajar.", "Antes: tiempo o errores observados, con método.", "Qué se activó y durante cuánto tiempo.", "Después: mismo indicador, mismo método.", "Voz del cliente aprobada.", "Límite: qué no cambió o qué sigue pendiente."),
        ("Entrevista real + capturas autorizadas.", "Mostrar el método de medición en una slide.", "Usar cifras solo tras validación y aprobación escrita."),
        "PROBLEMA MEDIDO · CAMBIO OBSERVADO · LÍMITE CLARO", "La prueba no es una frase bonita: es un cambio que podemos explicar y repetir.",
        "Solicita una prueba para tu negocio.", "Solicitud → piloto → pago", "NO PUBLICAR todavía: requiere 3–5 pilotos, permiso y evidencia. Nunca rellenar huecos con cifras estimadas."),
]


def add_cover(doc: Document):
    for _ in range(3):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
    if LOGO.exists():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        picture = p.add_run().add_picture(str(LOGO), width=Inches(3.6))
        set_picture_alt(
            picture,
            title="Logotipo de Noesis",
            description="Símbolo de estrella y nombre Noesis en verde corporativo.",
        )
        p.paragraph_format.space_after = Pt(36)
    kicker = doc.add_paragraph()
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run(kicker.add_run("MANUAL OPERATIVO DE MARKETING"), size=9.5, color=TEAL, bold=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    set_run(p.add_run("Sistema editorial y\nguiones de contenido"), name="Georgia", size=28, color=FOREST, bold=True)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.paragraph_format.space_after = Pt(34)
    set_run(sub.add_run("Instagram · Facebook · LinkedIn · Campañas"), size=13, color=MUTED)
    add_callout(doc, "Que el autónomo primero se sienta entendido, después ayudado y finalmente vea por qué Noesis merece una prueba.", fill=CREAM, accent=FOREST, size=12)
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.paragraph_format.space_before = Pt(30)
    set_run(meta.add_run("Versión 1.1 · 2 de septiembre de 2026\nUso interno · Noesis"), size=9.5, color=MUTED, bold=True)
    page_break(doc)


def add_index(doc: Document):
    add_title(doc, "Cómo usar este manual", "Qué parte responde a cada pregunta antes de grabar o publicar")
    add_matrix(doc, ["Parte", "Qué responde", "Cuándo se abre"], [
        ("La decisión editorial", "Qué debe conseguir el contenido antes de pedir una venta", "Al planificar el mes o dudar de un tema"),
        ("A quién hablamos", "Quién es el ICP y qué situaciones deben aparecer en cámara", "Al escribir un gancho o elegir localización"),
        ("Canales y cadencia", "Qué hace cada red y cuánto se publica en ella", "Al montar la parrilla y decidir formato"),
        ("Mapa de contenidos", f"Las {len(CARDS)} piezas base y en qué ficha está cada una", "Como índice de las fichas"),
        (f"Fichas 01–{len(CARDS)}", "Gancho, guion, rodaje, copy, CTA, métrica y límite de cada pieza", "En preproducción y el día del rodaje"),
        ("Campañas", "Cómo se agrupan las piezas en cinco relatos con un CTA", "Al lanzar una secuencia, no una pieza suelta"),
        ("Primer mes editorial", "Un calendario de aprendizaje semana a semana", "Al programar publicaciones"),
        ("Motor de producción", "Cómo grabar dos semanas de contenido en una mañana", "Antes de un bloque de rodaje"),
        ("Cómo medir y decidir", "Qué métrica juzga cada pieza y cuándo repetir o parar", "Al revisar resultados"),
        ("Checklist antes de publicar", "Los doce controles que protegen marca, cliente y producto", "Siempre, antes de darle a publicar"),
        ("Fuentes y límites", "En qué se apoya el manual y qué falta validar", "Al afirmar algo que aún no está probado"),
    ], [2450, 4300, 2610], font_size=8.9)
    add_callout(doc, "Las piezas se nombran por su código (E01, R03, P05, T00…) y ese código es el mismo en el mapa, en las fichas, en las campañas y en el calendario.", fill=CREAM, accent=FOREST, size=10.5)
    page_break(doc)


def add_strategy(doc: Document):
    add_title(doc, "La decisión editorial", "Qué debe conseguir el contenido antes de pedir una venta")
    add_callout(doc, "Noesis no debe parecer una empresa que publica funciones. Debe convertirse en la marca que mejor entiende el trabajo invisible de los autónomos de servicios.", label="Norte")
    add_heading(doc, "El recorrido que debe provocar", 1)
    add_matrix(doc, ["Momento", "Lo que piensa la persona", "Contenido que lo provoca"], [
        ("1 · Me identifica", "‘Estos entienden mi vida’", "Humor, escenas cotidianas, preguntas reales"),
        ("2 · Me ayuda", "‘Aquí aprendo algo útil’", "Checklists, plantillas, números explicados"),
        ("3 · Me demuestra", "‘Esto podría funcionar en mi negocio’", "Demos breves, antes/después de flujo, control humano"),
        ("4 · Me da confianza", "‘Sé quiénes son y no me venden humo’", "Founders, decisiones de producto, seguridad y límites"),
        ("5 · Me convierte", "‘Quiero probarlo’", "Piloto, demostración y caso real medido"),
    ], [1700, 3300, 4360], font_size=9.1)
    add_heading(doc, "Regla de mezcla", 1)
    add_matrix(doc, ["Pilar", "Peso", "Función"], [
        ("Identificación emocional", "35 %", "Alcance, reconocimiento y comunidad"),
        ("Valor práctico", "30 %", "Guardados, autoridad y hábito"),
        ("Demostración de producto", "20 %", "Prueba funcional y solicitud de acceso"),
        ("Confianza y marca", "15 %", "Rostro, criterio, seguridad y credibilidad"),
    ], [2600, 1300, 5460], font_size=9.2)
    add_body(doc, "No más de una de cada cuatro piezas debe pedir una prueba o enseñar directamente el producto. El resto construye la razón para escuchar esa petición.", bold_label="Guardarraíl: ")
    page_break(doc)


def add_audience(doc: Document):
    add_title(doc, "A quién hablamos", "Audiencia prioritaria y situaciones que deben aparecer en cámara")
    add_heading(doc, "Público principal", 1)
    add_label_detail_table(doc, [
        ("Perfil", "Autónomo o pequeña empresa de servicios de 1–5 personas en España."),
        ("Oficios", "Fontanería, electricidad, reformas, climatización, mantenimiento, cerrajería; después limpieza y jardinería."),
        ("Comportamiento", "Trabaja fuera, organiza por WhatsApp, resuelve sobre la marcha y no quiere aprender un ERP."),
        ("Dolor visible", "El trabajo administrativo continúa al llegar a casa: agenda, clientes, presupuestos, documentos, facturas y cobros."),
        ("Deseo", "Recuperar tiempo, reducir ruido mental y entender el negocio sin convertirse en gestor."),
        ("Objeción", "Miedo a que la herramienta se equivoque, mezcle datos o añada más trabajo."),
    ], font_size=9.7)
    add_heading(doc, "Públicos secundarios", 1)
    add_bullet(doc, "Gestorías: prescriptoras y usuarias de un flujo documental preparado, nunca sustituidas.")
    add_bullet(doc, "Empresas de 5–10 personas: interesadas en trabajos, equipo, margen y seguimiento.")
    add_bullet(doc, "Pareja, familiar o administrativo que hoy sostiene el orden del negocio.")
    add_heading(doc, "Qué no debe dominar el contenido", 1)
    add_bullet(doc, "Jerga de startup, IA o finanzas.")
    add_bullet(doc, "Promesas para cualquier empresa o cualquier sector.")
    add_bullet(doc, "Vida de oficina genérica: Noesis debe oler a furgoneta, visita, herramienta, cliente y fin de jornada.")
    page_break(doc)


def add_channels(doc: Document):
    add_title(doc, "Canales y cadencia", "El mismo sistema editorial, adaptado a la función de cada red")
    add_matrix(doc, ["Canal", "Función", "Cadencia inicial", "Formato dominante"], [
        ("Instagram", "Identificación, valor y demostración", "3 Reels + 1 carrusel/semana; Stories 4–5 días", "9:16, 20–45 s, subtítulos"),
        ("Facebook", "Reutilización, conversación local y grupos", "2–3 vídeos + 1 post práctico/semana", "Vídeo vertical + texto más contextual"),
        ("LinkedIn", "Confianza, founders, partners y categoría", "2 posts founder + 1 empresa/semana", "Post humano, carrusel y vídeo nativo"),
        ("TikTok/Shorts", "Reserva y expansión posterior", "Sin producción propia hasta hallar formato ganador", "Reutilización sin marca de agua"),
    ], [1500, 3000, 2600, 2260], font_size=8.7)
    add_heading(doc, "Reglas de producción vertical", 1)
    for item in (
        "Formato 9:16; cara, objeto o problema reconocible desde el primer segundo.",
        "Gancho en 0–2 segundos. Una sola idea por pieza.",
        "Duración objetivo: 20–40 segundos; más solo si la historia lo justifica.",
        "Subtítulos siempre. Texto central dentro de zona segura; nunca pegado a bordes.",
        "Audio comprensible antes que imagen perfecta. Luz natural y escenarios reales ganan a un plató vacío.",
        "Un único CTA: comentar, guardar, compartir, pedir demo o solicitar piloto; nunca todos.",
    ):
        add_bullet(doc, item)
    add_callout(doc, "Un contenido puede ser sencillo, pero nunca confuso: problema visible → idea útil → siguiente paso.", fill=CREAM, accent=FOREST, size=11)
    page_break(doc)


def add_content_index(doc: Document):
    add_title(doc, "Mapa de contenidos", f"{len(CARDS)} piezas base para producir, aprender y convertir")
    numbers = {card.code: idx for idx, card in enumerate(CARDS, start=1)}
    groups = [
        ("· Presentación", [c for c in CARDS if c.code in ("T00", "P00")]),
        ("E · Identificación", [c for c in CARDS if c.code.startswith("E")]),
        ("R · Valor racional", [c for c in CARDS if c.code.startswith("R")]),
        ("P · Producto", [c for c in CARDS if c.code.startswith("P") and c.code != "P00"]),
        ("T · Confianza", [c for c in CARDS if c.code.startswith("T") and c.code != "T00"]),
        ("G · Comunidad y prueba", [c for c in CARDS if c.code.startswith("G")]),
    ]
    for group_idx, (title, cards) in enumerate(groups):
        if group_idx == 3:
            page_break(doc)
            add_title(doc, "Mapa II", "Producto, confianza, comunidad y prueba")
        add_heading(doc, title, 2)
        rows = [(f"{numbers[c.code]:02d}", c.code, c.title, c.format, c.objective) for c in cards]
        add_matrix(doc, ["Ficha", "ID", "Pieza", "Formato", "Finalidad"], rows, [700, 700, 2500, 2300, 3160], font_size=8.6)
    page_break(doc)


def add_card(doc: Document, card: ContentCard, index: int):
    add_body(doc, f"FICHA {index:02d} DE {len(CARDS)}  ·  {card.code}", size=8.5, color=TEAL, after=2)
    add_heading(doc, card.title, 1)
    add_matrix(doc, ["Pilar", "Formato", "Canales", "Fase"], [(card.pillar, card.format, card.channels, card.funnel)], [2400, 2500, 2600, 1860], font_size=8.6)
    add_label_detail_table(doc, [
        ("Público", card.audience),
        ("Finalidad", card.objective),
        ("Idea", card.idea),
    ], label_width=1450, font_size=9.0)
    add_callout(doc, card.hook, label="Gancho", fill=CREAM, accent=FOREST, size=11)
    add_heading(doc, "Guion orientativo", 2)
    for line in card.script:
        add_bullet(doc, line, size=9.2, after=2)
    add_heading(doc, "Rodaje y montaje", 2)
    for line in card.shots:
        add_bullet(doc, line, size=9.0, after=2)
    add_label_detail_table(doc, [
        ("Texto en pantalla", card.overlay),
        ("Copy", card.caption),
        ("CTA", card.cta),
        ("Métrica", card.kpi),
        ("Límite", card.guardrail),
    ], label_width=1550, font_size=8.7)
    if index < len(CARDS):
        page_break(doc)


def add_campaigns(doc: Document):
    page_break(doc)
    add_title(doc, "Campañas", "Cinco conceptos capaces de agrupar piezas sin convertir el perfil en un catálogo")
    campaigns = [
        ("C1", "Que el domingo vuelva a ser domingo", "Marca emocional", "Autónomo saturado por el trabajo invisible", "Vídeo manifiesto E01 → Stories con pregunta → carrusel R05 → demo P05", "Solicitar acceso", "No usar una promesa literal de horas recuperadas sin medir."),
        ("C2", "De WhatsApp a negocio ordenado", "Demostración racional", "Usuario móvil-first", "Dolor E03 → demo P01 → demo P03 → confianza T03", "Pedir demo", "Rotular WhatsApp como piloto mientras Meta no esté validado en real."),
        ("C3", "Todo lo que llevas en la cabeza", "Carga mental", "Autónomo con agenda, clientes y cobros dispersos", "Reel E04 → carrusel R04 → parte P05 → founder T01", "Responder a una encuesta / piloto", "Evitar mensajes médicos sobre estrés; hablar de ruido y control."),
        ("C4", "La gestoría deja de perseguirte", "Partner y documentos", "Gestorías y clientes desordenados", "Humor E05 → hábito R05 → flujo G02 → demo conjunta", "Demo para gestorías", "No prometer presentación fiscal ni sustitución profesional."),
        ("C5", "Caso piloto medible", "Prueba social", "Mismo oficio y tamaño que el caso", "Contexto → línea base → uso 30 días → resultado → límite → invitación", "Prueba controlada", "Solo activar con permiso, método y cifra validada; no antes."),
    ]
    for campaign_idx, (code, name, focus, audience, sequence, cta, guardrail) in enumerate(campaigns):
        if campaign_idx == 4:
            page_break(doc)
            add_title(doc, "Campaña de prueba", "La prueba social solo se publica cuando existe evidencia")
        add_heading(doc, f"{code} · {name}", 2)
        add_label_detail_table(doc, [
            ("Enfoque", focus), ("Público", audience), ("Secuencia", sequence), ("CTA", cta), ("Guardarraíl", guardrail)
        ], label_width=1550, font_size=9.0)
    page_break(doc)


def add_calendar(doc: Document):
    add_title(doc, "Primer mes editorial", "Un calendario de aprendizaje, no una parrilla rígida")
    add_callout(doc, "T00 y P00 se publican antes de la Semana 1 y se fijan en el perfil: quiénes somos y qué es Noesis. Son el contexto que hace entendible todo lo demás y la respuesta que se manda a quien pregunta.", fill=CREAM, accent=FOREST, size=10.5)
    weeks = [
        ("Semana 1 · ‘Me entienden’", [
            ("Lunes", "IG/FB Reel", "E01 · La segunda jornada", "Compartidos"),
            ("Martes", "Stories", "Encuesta: ‘¿A qué hora acaba de verdad tu día?’", "Respuestas"),
            ("Miércoles", "LinkedIn founder", "T01 · Por qué construimos Noesis", "Conversaciones"),
            ("Jueves", "IG carrusel", "R05 · Rutina de tickets", "Guardados"),
            ("Viernes", "IG/FB Reel", "E02 · Cosita rápida", "Comentarios"),
        ]),
        ("Semana 2 · ‘Me ayudan’", [
            ("Lunes", "IG carrusel", "R01 · Rentabilidad por trabajo", "Guardados"),
            ("Martes", "Stories", "Caja de preguntas: ‘¿Qué coste se te olvida?’", "Insight ICP"),
            ("Miércoles", "IG/FB Reel", "R03 · Recordatorio de cobro", "Guardados"),
            ("Jueves", "LinkedIn founder", "T02 · No queremos ser un ERP", "Comentarios ICP"),
            ("Viernes", "IG/FB Reel", "E06 · Facturar no es ganar", "Visitas perfil"),
        ]),
        ("Semana 3 · ‘Me lo demuestran’", [
            ("Lunes", "IG Reel", "P05 · El parte del día", "Demos"),
            ("Martes", "Stories", "Antes/después de un flujo demo", "Respuestas"),
            ("Miércoles", "IG/FB Reel", "P03 · Factura hablando", "Finalizaciones"),
            ("Jueves", "LinkedIn empresa", "T03 · Por qué confirmamos", "Confianza"),
            ("Viernes", "IG Reel", "P01 · Documento desde WhatsApp (piloto)", "Solicitudes"),
        ]),
        ("Semana 4 · ‘Confío y pruebo’", [
            ("Lunes", "IG/FB Reel", "E05 · Día 29", "Compartidos"),
            ("Martes", "LinkedIn", "G02 · Gestoría preparada", "Demos partner"),
            ("Miércoles", "IG carrusel", "T04 · Aislamiento y control", "Guardados"),
            ("Jueves", "Stories", "FAQ real del piloto", "Objeciones"),
            ("Viernes", "IG/FB vídeo", "Invitación al piloto con límites claros", "Solicitudes"),
        ]),
    ]
    for idx, (title, rows) in enumerate(weeks):
        add_heading(doc, title, 2)
        add_matrix(doc, ["Día", "Canal", "Pieza", "Métrica"], rows, [1200, 1900, 4500, 1760], font_size=8.9)
        if idx == 1:
            page_break(doc)
            add_title(doc, "Mes editorial · semanas 3–4", "Demostración, confianza y conversión controlada")
    add_callout(doc, "Si una pieza genera respuestas cualitativas buenas, se repite el ángulo con otro oficio antes de inventar un tema nuevo.", fill=CREAM, accent=FOREST, size=10.5)
    page_break(doc)


def add_production(doc: Document):
    add_title(doc, "Motor de producción", "Cómo crear dos semanas de contenido en una mañana")
    add_heading(doc, "Bloque de grabación quincenal", 1)
    add_matrix(doc, ["Bloque", "Tiempo", "Salida"], [
        ("Preparación", "30 min", "Props, guiones, documentos ficticios, ajustes de audio y luz"),
        ("Humor/identificación", "60 min", "3–4 Reels físicos"),
        ("A cámara", "45 min", "2 piezas educativas + 1 founder"),
        ("Producto", "45 min", "2 demos con datos de prueba"),
        ("Stories/B-roll", "30 min", "15–20 clips: furgoneta, manos, oficina, pantallas, equipo"),
        ("Fotografía", "15 min", "Retratos y escenas para LinkedIn/carruseles"),
    ], [2600, 1600, 5160], font_size=9.0)
    add_heading(doc, "Una idea, siete salidas", 1)
    for item in (
        "Reel físico de 25–35 segundos.",
        "Facebook Reel con copy más contextual.",
        "Carrusel con la explicación práctica.",
        "Post founder con el aprendizaje o decisión.",
        "Story con encuesta o pregunta.",
        "Clip sin marca de agua reservado para Shorts/TikTok.",
        "Entrada en la biblioteca de objeciones y preguntas del equipo comercial.",
    ):
        add_bullet(doc, item)
    add_heading(doc, "Control de archivos", 1)
    add_label_detail_table(doc, [
        ("Nombre", "AAAAMMDD_ID_tema_toma.ext — ejemplo: 20260904_E01_segunda-jornada_T02.mp4"),
        ("Carpetas", "01_brutos · 02_seleccion · 03_editados · 04_subtitulos · 05_publicados · 06_metricas"),
        ("Versiones", "master_sin_texto · ig_9x16 · fb_9x16 · li_9x16 · portada"),
        ("Privacidad", "Nunca grabar documentos, teléfonos, matrículas o conversaciones reales sin permiso."),
    ], font_size=9.1)
    page_break(doc)


def add_measurement(doc: Document):
    add_title(doc, "Cómo medir y decidir", "La métrica correcta depende del trabajo de cada pieza")
    add_matrix(doc, ["Tipo", "Métrica principal", "Señal de calidad", "Decisión"], [
        ("Emocional", "Compartidos + retención", "Comentarios ‘me pasa’ del ICP", "Repetir situación con otro oficio"),
        ("Educativo", "Guardados", "Preguntas concretas o uso de plantilla", "Profundizar en la duda"),
        ("Producto", "Visitas + demos", "Pregunta por un flujo específico", "Mejorar demostración y CTA"),
        ("Confianza", "Comentarios/DM cualificados", "Conversación con autónomo o partner", "Convertir objeción en contenido"),
        ("Campaña", "Solicitud de acceso", "Solicitud encaja con ICP", "Nutrir, entrevistar o pilotar"),
        ("Negocio", "Solicitud → piloto → pago", "Retención 60 días y uso real", "Solo entonces escalar inversión"),
    ], [1600, 2100, 3300, 2360], font_size=8.8)
    add_heading(doc, "Reglas de decisión", 1)
    for item in (
        "No juzgar un formato por una sola publicación; usar al menos tres intentos con ganchos distintos.",
        "No premiar solo reproducciones: si no atrae al oficio prioritario, es alcance vacío.",
        "Registrar preguntas y objeciones textuales; son materia prima editorial y comercial.",
        "No escalar anuncios amplios hasta tener 3–5 pilotos y tres casos medibles con permiso.",
        "Cuando exista prueba, impulsar primero la pieza orgánica que ya consiguió atención cualificada.",
        "Medir CAC y retención antes de aumentar presupuesto; una venta que abandona pronto no valida el canal.",
    ):
        add_bullet(doc, item)
    add_callout(doc, "La finalidad del contenido no es parecer activo. Es aprender qué problema moviliza al cliente correcto y convertir esa comprensión en una prueba del producto.", fill=CREAM, accent=FOREST, size=11)
    page_break(doc)


def add_checklist(doc: Document):
    add_title(doc, "Checklist antes de publicar", "La última revisión protege la marca, al cliente y el producto")
    checks = [
        ("Mensaje", "¿Se entiende en dos segundos el problema o la promesa?"),
        ("Público", "¿Habla a un autónomo de servicios reconocible?"),
        ("Una idea", "¿La pieza intenta hacer una sola cosa?"),
        ("Verdad", "¿Cada cifra, función y resultado puede demostrarse?"),
        ("Estado", "¿Lo que sigue en piloto aparece como piloto/demo?"),
        ("Control", "¿Se ve que el usuario confirma lo sensible?"),
        ("Privacidad", "¿No aparecen datos reales, matrículas, clientes o documentos?"),
        ("Accesibilidad", "¿Hay subtítulos, contraste y texto dentro de zona segura?"),
        ("CTA", "¿Existe un único siguiente paso?"),
        ("Medición", "¿Sabemos qué métrica decide si repetir la pieza?"),
        ("Permiso", "¿Hay consentimiento escrito si aparece un tercero o un caso?"),
        ("Marca", "¿Suena a mano derecha tranquila, no a banco, ERP o gurú?"),
    ]
    rows = [("☐", label, question) for label, question in checks]
    add_matrix(doc, ["", "Control", "Pregunta"], rows, [600, 1800, 6960], font_size=9.2)
    add_heading(doc, "No publicar", 1)
    for item in (
        "Testimonios recreados, cifras estimadas presentadas como reales o logos de clientes sin permiso.",
        "‘100 % automático’, ‘sin errores’, ‘totalmente seguro’ o ‘te lleva la fiscalidad’.",
        "WhatsApp operativo masivo, telefonía premium o AEAT real antes de superar sus validaciones externas.",
        "Contenido genérico sobre IA que no regresa a tiempo, orden, calma y control del negocio.",
    ):
        add_bullet(doc, item, color=RED)
    page_break(doc)


def add_sources(doc: Document):
    add_title(doc, "Fuentes y límites", "Qué sostiene este manual y qué debe validarse con mercado real")
    add_heading(doc, "Fuentes internas", 1)
    for item in (
        "docs/Producto.md y docs/design/PRODUCT_PRINCIPLES.md — propósito, experiencia y confirmación humana.",
        "docs/Estrategia-Marketing.html — ICP, pilotos, fases y guardarraíles de adquisición.",
        "docs/project-state.json — capacidades verificadas y validaciones externas pendientes.",
        "branding/BRAND_GUIDE.md y branding/redes-sociales/ — identidad y configuración de canales.",
    ):
        add_bullet(doc, item, size=9.7)
    add_heading(doc, "Referencias de plataforma", 1)
    add_body(doc, "Meta for Business, Reels ads: formato vertical 9:16, audio, zona segura y pruebas creativas. https://www.facebook.com/business/ads/facebook-instagram-reels-ads", size=9.2)
    add_body(doc, "LinkedIn, The Art and Science of Video (2025): autenticidad humana, expertos y mecanismos de atención. https://business.linkedin.com/content/dam/business/marketing-solutions/global/en_US/site/pdf/wp/2025/the-art-and-science-of-video.pdf", size=9.2)
    add_body(doc, "LinkedIn Marketing Solutions, Build your brand with video: orientación actual sobre vídeo nativo. https://business.linkedin.com/marketing-solutions/marketing-partners/resources/build-your-brand-with-video-on-linkedin", size=9.2)
    add_heading(doc, "Evidencia todavía pendiente", 1)
    for item in (
        "Tres a cinco pilotos reales de oficios prioritarios.",
        "Línea base y medición de tiempo, errores, documentos pendientes y activación.",
        "Permiso escrito para casos, testimonios, imágenes y cifras.",
        "Validación real de WhatsApp/Meta y del resto de integraciones antes de prometer disponibilidad general.",
        "Aprendizaje de retención, conversión, CAC y objeciones por oficio.",
    ):
        add_bullet(doc, item)
    add_callout(doc, "Hasta que exista esa evidencia, el mejor marketing de Noesis es mostrar con honestidad cómo prepara, organiza y pide confirmación.", fill=CREAM, accent=FOREST, size=11)


def set_core_properties(doc: Document):
    props = doc.core_properties
    props.title = "Sistema editorial y guiones de contenido · Noesis"
    props.subject = "Manual operativo de contenido para Instagram, Facebook, LinkedIn y campañas"
    props.author = "Noesis"
    props.keywords = "Noesis, marketing, contenido, guiones, Instagram, Facebook, LinkedIn"
    props.comments = "Documento interno de trabajo. No contiene datos personales ni resultados simulados."


def build():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()
    configure_document(doc)
    set_core_properties(doc)
    add_cover(doc)
    add_index(doc)
    add_strategy(doc)
    add_audience(doc)
    add_channels(doc)
    add_content_index(doc)
    for idx, card in enumerate(CARDS, start=1):
        add_card(doc, card, idx)
    add_campaigns(doc)
    add_calendar(doc)
    add_production(doc)
    add_measurement(doc)
    add_checklist(doc)
    add_sources(doc)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
