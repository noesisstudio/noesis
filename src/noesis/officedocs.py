"""Escribe .docx y .xlsx con la biblioteca estandar, sin dependencias nuevas.

Un .docx y un .xlsx no son mas que un ZIP con unos cuantos XML dentro. Generarlos
aqui evita meter `python-docx` y `openpyxl` en produccion solo para servir dos
descargas: son dependencias que habria que desplegar, auditar y mantener por un par
de documentos de dos paginas (AGENTS.md, regla 2: stdlib primero).

El alcance es deliberadamente corto y es lo unico que estos documentos necesitan:
titulos, parrafos, tablas con cabecera, saltos de pagina y numeros con formato. No
hay imagenes, ni graficos, ni estilos arbitrarios. Si algun dia hiciera falta algo
de eso, esa es la linea a partir de la cual conviene una libreria de verdad.

Word y Excel son estrictos con estos archivos: un XML mal formado no da un error
legible, da un aviso de «archivo dañado». `tests/test_officedocs.py` abre lo que se
genera y comprueba las piezas obligatorias.
"""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

# Paleta de marca (docs/design/STYLE_TOKENS.json), sin la almohadilla.
FOREST = "14463B"
TEAL = "2E8B74"
INK = "15211C"
MUTED = "5D6B66"
SAND = "E7E0D1"
CREAM = "F4F1EA"


def _esc(value) -> str:
    return escape("" if value is None else str(value))


# =========================================================== WORD (.docx) === #
_DOCX_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '</Types>'
)

_DOCX_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '</Relationships>'
)

_DOCX_DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '</Relationships>'
)


def _docx_style(sid: str, name: str, size_half_pt: int, *, bold=False,
                color=INK, after=120, before=0, caps=False) -> str:
    rpr = '<w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/>'
    if bold:
        rpr += "<w:b/>"
    if caps:
        rpr += '<w:caps/><w:spacing w:val="30"/>'
    rpr += f'<w:color w:val="{color}"/><w:sz w:val="{size_half_pt}"/>'
    return (
        f'<w:style w:type="paragraph" w:styleId="{sid}">'
        f'<w:name w:val="{name}"/>'
        f'<w:pPr><w:spacing w:before="{before}" w:after="{after}" w:line="264" '
        f'w:lineRule="auto"/></w:pPr>'
        f'<w:rPr>{rpr}</w:rPr></w:style>'
    )


_DOCX_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:docDefaults><w:rPrDefault><w:rPr>'
    '<w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/>'
    f'<w:color w:val="{INK}"/><w:sz w:val="20"/>'
    '</w:rPr></w:rPrDefault></w:docDefaults>'
    + _docx_style("Normal", "Normal", 20)
    + _docx_style("Titulo", "Titulo", 40, bold=True, color=FOREST, after=60)
    + _docx_style("Subtitulo", "Subtitulo", 19, color=MUTED, after=240)
    + _docx_style("Seccion", "Seccion", 24, bold=True, color=FOREST, before=240, after=100)
    + _docx_style("Etiqueta", "Etiqueta", 15, bold=True, color=MUTED, before=160,
                  after=60, caps=True)
    + _docx_style("Nota", "Nota", 17, color=MUTED, after=100)
    + _docx_style("Cifra", "Cifra", 30, bold=True, color=FOREST, after=0)
    + '</w:styles>'
)


def _docx_p(text: str, style: str = "Normal", *, runs=None) -> str:
    if runs is None:
        runs = [(text, {})]
    body = ""
    for value, fmt in runs:
        rpr = ""
        if fmt.get("bold"):
            rpr += "<w:b/>"
        if fmt.get("color"):
            rpr += f'<w:color w:val="{fmt["color"]}"/>'
        if fmt.get("size"):
            rpr += f'<w:sz w:val="{fmt["size"]}"/>'
        rpr = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
        body += f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(value)}</w:t></w:r>'
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{body}</w:p>'


def _docx_cell(text, *, bold=False, fill=None, align="left", color=INK, width=None) -> str:
    shd = f'<w:shd w:val="clear" w:fill="{fill}"/>' if fill else ""
    w = f'<w:tcW w:w="{width}" w:type="pct"/>' if width else ""
    jc = {"left": "left", "right": "right", "center": "center"}[align]
    rpr = ("<w:b/>" if bold else "") + f'<w:color w:val="{color}"/><w:sz w:val="18"/>'
    return (
        f"<w:tc><w:tcPr>{w}{shd}"
        '<w:tcMar><w:top w:w="60" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/>'
        '<w:left w:w="90" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tcMar>'
        "</w:tcPr>"
        f'<w:p><w:pPr><w:spacing w:after="0"/><w:jc w:val="{jc}"/></w:pPr>'
        f'<w:r><w:rPr>{rpr}</w:rPr>'
        f'<w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p></w:tc>'
    )


def _docx_table(rows: list[list], *, widths=None, aligns=None) -> str:
    borders = "".join(
        f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="DDD8CC"/>'
        for side in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    out = ('<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
           f"<w:tblBorders>{borders}</w:tblBorders></w:tblPr>")
    for i, row in enumerate(rows):
        cells = ""
        for j, value in enumerate(row):
            align = (aligns[j] if aligns and j < len(aligns) else "left")
            cells += _docx_cell(
                value, bold=(i == 0), fill=(SAND if i == 0 else None),
                align=("left" if i == 0 and j == 0 else align),
                color=(FOREST if i == 0 else INK),
                width=(widths[j] if widths and j < len(widths) else None),
            )
        out += f"<w:tr>{cells}</w:tr>"
    return out + "</w:tbl>"


_DOCX_PAGE_BREAK = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def build_docx(blocks: list[tuple]) -> bytes:
    """Arma un .docx a partir de bloques ``(tipo, ...)``.

    Tipos: ``("p", texto, estilo)``, ``("runs", [(texto, fmt)], estilo)``,
    ``("tabla", filas, anchos, alineaciones)`` y ``("salto",)``.
    """
    body = ""
    for block in blocks:
        kind = block[0]
        if kind == "p":
            body += _docx_p(block[1], block[2] if len(block) > 2 else "Normal")
        elif kind == "runs":
            body += _docx_p("", block[2] if len(block) > 2 else "Normal", runs=block[1])
        elif kind == "tabla":
            body += _docx_table(block[1],
                                widths=block[2] if len(block) > 2 else None,
                                aligns=block[3] if len(block) > 3 else None)
            body += '<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>'
        elif kind == "salto":
            body += _DOCX_PAGE_BREAK
        else:  # pragma: no cover - programacion defensiva
            raise ValueError(f"bloque desconocido: {kind}")
    # A4 con margenes de 2 cm (1.134 twips), que es lo que cabe en dos paginas.
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
            'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>')
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}{sect}</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
        z.writestr("_rels/.rels", _DOCX_RELS)
        z.writestr("word/_rels/document.xml.rels", _DOCX_DOC_RELS)
        z.writestr("word/styles.xml", _DOCX_STYLES)
        z.writestr("word/document.xml", document)
    return buf.getvalue()


# ========================================================== EXCEL (.xlsx) === #
# Indices de estilo que usan las hojas. El orden importa: es la posicion en cellXfs.
S_NORMAL, S_TITULO, S_SECCION, S_CABECERA = 0, 1, 2, 3
S_TEXTO, S_EUR, S_EUR_FUERTE, S_PCT, S_NUM, S_NOTA = 4, 5, 6, 7, 8, 9

_XLSX_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<numFmts count="3">'
    '<numFmt numFmtId="164" formatCode="#,##0.00\\ &quot;€&quot;"/>'
    '<numFmt numFmtId="165" formatCode="0.0%"/>'
    '<numFmt numFmtId="166" formatCode="#,##0"/>'
    '</numFmts>'
    '<fonts count="6">'
    f'<font><sz val="10"/><color rgb="FF{INK}"/><name val="Aptos"/></font>'
    f'<font><b/><sz val="17"/><color rgb="FF{FOREST}"/><name val="Aptos"/></font>'
    f'<font><b/><sz val="11"/><color rgb="FF{FOREST}"/><name val="Aptos"/></font>'
    f'<font><b/><sz val="10"/><color rgb="FF{FOREST}"/><name val="Aptos"/></font>'
    f'<font><sz val="9"/><color rgb="FF{MUTED}"/><name val="Aptos"/></font>'
    f'<font><b/><sz val="11"/><color rgb="FF{FOREST}"/><name val="Aptos"/></font>'
    '</fonts>'
    '<fills count="4">'
    '<fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill>'
    f'<fill><patternFill patternType="solid"><fgColor rgb="FF{SAND}"/>'
    '<bgColor indexed="64"/></patternFill></fill>'
    f'<fill><patternFill patternType="solid"><fgColor rgb="FF{CREAM}"/>'
    '<bgColor indexed="64"/></patternFill></fill>'
    '</fills>'
    '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
    '<border><left style="thin"><color rgb="FFDDD8CC"/></left>'
    '<right style="thin"><color rgb="FFDDD8CC"/></right>'
    '<top style="thin"><color rgb="FFDDD8CC"/></top>'
    '<bottom style="thin"><color rgb="FFDDD8CC"/></bottom><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
    '</cellStyleXfs>'
    '<cellXfs count="10">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
    '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
    '<xf numFmtId="0" fontId="3" fillId="2" borderId="1" xfId="0" applyFont="1" '
    'applyFill="1" applyBorder="1"><alignment wrapText="1" vertical="center"/></xf>'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>'
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" '
    'applyBorder="1"/>'
    '<xf numFmtId="164" fontId="5" fillId="3" borderId="1" xfId="0" applyNumberFormat="1" '
    'applyFont="1" applyFill="1" applyBorder="1"/>'
    '<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" '
    'applyBorder="1"/>'
    '<xf numFmtId="166" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" '
    'applyBorder="1"/>'
    '<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1">'
    '<alignment wrapText="1" vertical="top"/></xf>'
    '</cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    '</styleSheet>'
)


def _col_letter(index: int) -> str:
    letters = ""
    while index > 0:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _xlsx_cell(ref: str, value, style: int) -> str:
    if value is None or value == "":
        return f'<c r="{ref}" s="{style}"/>'
    if isinstance(value, bool):
        value = str(value)
    if isinstance(value, (int, float)):
        return f'<c r="{ref}" s="{style}"><v>{value!r}</v></c>'
    return (f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">'
            f"{_esc(value)}</t></is></c>")


def build_xlsx(sheets: list[dict]) -> bytes:
    """Arma un .xlsx. Cada hoja es ``{"nombre", "anchos", "filas"}``.

    Una fila es una lista de ``(valor, estilo)``; los estilos son las constantes
    ``S_*`` de este modulo.
    """
    parts_sheets = []
    for sheet in sheets:
        cols = ""
        if sheet.get("anchos"):
            cols = "<cols>" + "".join(
                f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
                for i, w in enumerate(sheet["anchos"], start=1)
            ) + "</cols>"
        rows = ""
        for r, fila in enumerate(sheet["filas"], start=1):
            celdas = "".join(
                _xlsx_cell(f"{_col_letter(c)}{r}", valor, estilo)
                for c, (valor, estilo) in enumerate(fila, start=1)
            )
            rows += f'<row r="{r}">{celdas}</row>'
        parts_sheets.append(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0" showGridLines="0"/></sheetViews>'
            f"{cols}<sheetData>{rows}</sheetData>"
            '<pageSetup paperSize="9" orientation="portrait"/></worksheet>'
        )

    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{overrides}</Types>"
    )
    sheet_tags = "".join(
        f'<sheet name="{_esc(s["nombre"])[:31]}" sheetId="{i}" r:id="rId{i}"/>'
        for i, s in enumerate(sheets, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_tags}</sheets></workbook>"
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/'
            f'officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", _XLSX_STYLES)
        for i, xml in enumerate(parts_sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", xml)
    return buf.getvalue()
