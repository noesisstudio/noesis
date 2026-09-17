"""Escritura de hojas .xlsx con la biblioteca estándar.

Un .xlsx es un ZIP con XML dentro, así que no hace falta ninguna dependencia:
`openpyxl` traería consigo lxml y unos megas para lo que aquí ocupa un archivo.
Se escribe lo mínimo que Excel, LibreOffice y Google Sheets aceptan sin quejarse:
tipos reales (número, fecha y texto), cabecera en negrita y filtro, para que el
autónomo pueda ordenar y sumar sin reescribir nada.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import re
import zipfile

# Excel cuenta los días desde el 1899-12-31 arrastrando el bisiesto inexistente
# de 1900; por eso el origen real de la serie es el 30 de diciembre de 1899.
_EXCEL_EPOCH = date(1899, 12, 30)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Caracteres que XML 1.0 no admite ni escapados (un OCR puede colarlos).
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MAX_CELL_CHARS = 32767  # límite de Excel por celda


def _escape(text: str) -> str:
    text = _ILLEGAL_XML.sub("", text)
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _column(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    name = ""
    index += 1
    while index:
        index, resto = divmod(index - 1, 26)
        name = chr(ord("A") + resto) + name
    return name


def _cell_xml(reference: str, value, *, header: bool) -> str:
    if header:
        texto = _escape(str(value))[:_MAX_CELL_CHARS]
        return (f'<c r="{reference}" s="1" t="inlineStr">'
                f"<is><t>{texto}</t></is></c>")
    if isinstance(value, bool):  # antes que int: bool es subclase de int
        value = "Sí" if value else "No"
    elif isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, (int, float)):
        return f'<c r="{reference}" s="2"><v>{value}</v></c>'
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f'<c r="{reference}" s="3"><v>{(value - _EXCEL_EPOCH).days}</v></c>'
    texto = "" if value is None else str(value)
    if _ISO_DATE.match(texto):
        dia = date.fromisoformat(texto)
        return f'<c r="{reference}" s="3"><v>{(dia - _EXCEL_EPOCH).days}</v></c>'
    # A diferencia del CSV, aquí no hace falta anteponer una comilla: una celda
    # `inlineStr` es texto por definición y Excel nunca la evalúa. Las fórmulas
    # viven en un elemento <f> que este escritor no emite nunca, así que el dato
    # del usuario se ve tal cual lo escribió.
    if not texto:
        return f'<c r="{reference}"/>'
    return (f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">'
            f"{_escape(texto)[:_MAX_CELL_CHARS]}</t></is></c>")


def _sheet_xml(headers: list[str], rows: list[list]) -> str:
    anchos = []
    for indice, cabecera in enumerate(headers):
        largo = max([len(str(cabecera))]
                    + [len(str(fila[indice])) if indice < len(fila) else 0
                       for fila in rows[:200]])
        anchos.append(f'<col min="{indice + 1}" max="{indice + 1}" '
                      f'width="{min(max(largo + 2, 10), 48)}" customWidth="1"/>')
    filas = ["<row r=\"1\">" + "".join(
        _cell_xml(f"{_column(i)}1", cabecera, header=True)
        for i, cabecera in enumerate(headers)) + "</row>"]
    for numero, fila in enumerate(rows, start=2):
        celdas = "".join(
            _cell_xml(f"{_column(i)}{numero}", valor, header=False)
            for i, valor in enumerate(fila))
        filas.append(f'<row r="{numero}">{celdas}</row>')
    ultima = _column(max(len(headers) - 1, 0))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<cols>{''.join(anchos)}</cols>"
        f"<sheetData>{''.join(filas)}</sheetData>"
        f'<autoFilter ref="A1:{ultima}{len(rows) + 1}"/>'
        "</worksheet>"
    )


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    "</Types>"
)

_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    "</Relationships>"
)

_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    "</Relationships>"
)

# Estilos: 0 normal, 1 cabecera en negrita, 2 número con dos decimales,
# 3 fecha en formato español.
_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts>'
    '<fonts count="2">'
    '<font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font>'
    "</fonts>"
    '<fills count="2"><fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="4">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
    '<xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    "</cellXfs>"
    "</styleSheet>"
)


def _workbook_xml(title: str) -> str:
    # Excel rechaza el libro si el nombre de hoja pasa de 31 caracteres o lleva
    # los caracteres reservados.
    limpio = re.sub(r"[\\/*?:\[\]]", " ", title).strip()[:31] or "Hoja1"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{_escape(limpio)}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )


def build_sheet(headers: list[str], rows: list[list], *,
                title: str = "Datos") -> bytes:
    """Devuelve un .xlsx de una hoja con cabecera, filtro y tipos reales."""
    import io

    buffer = io.BytesIO()
    # Fecha fija en el ZIP: dos descargas del mismo dato dan el mismo archivo.
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as paquete:
        for nombre, contenido in (
            ("[Content_Types].xml", _CONTENT_TYPES),
            ("_rels/.rels", _RELS),
            ("xl/workbook.xml", _workbook_xml(title)),
            ("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS),
            ("xl/styles.xml", _STYLES),
            ("xl/worksheets/sheet1.xml", _sheet_xml(headers, rows)),
        ):
            info = zipfile.ZipInfo(nombre, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            paquete.writestr(info, contenido)
    return buffer.getvalue()


MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
