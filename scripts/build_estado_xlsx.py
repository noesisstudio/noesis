"""Genera docs/Estado-Noesis.xlsx: el estado de cada pieza, en una hoja de cálculo.

El vault de Obsidian explica el porqué de las cosas; esta hoja sirve para lo
otro: mirar de un vistazo qué está hecho, qué bloquea y qué falta, y poder
filtrar y ordenar. Se genera desde el código —las plantillas de Meta y los
catálogos por oficio se leen de sus módulos— para que no envejezca en cuanto
alguien toque `trades.py` o `whatsapp_templates.py`.

Sin dependencias: un .xlsx es un zip de XML y aquí se escribe a mano, como manda
la regla de oro de ejecutar en local y no arrastrar librerías por comodidad.

    python scripts/build_estado_xlsx.py
"""

from __future__ import annotations

import sys
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUTPUT = ROOT / "docs" / "Estado-Noesis.xlsx"

# Estilos: 0 normal, 1 cabecera, 2 texto con ajuste, 3 negrita, 4 número.
HEADER, WRAP, BOLD, NUMBER = 1, 2, 3, 4


def _column(index: int) -> str:
    letters = ""
    while index >= 0:
        letters = chr(index % 26 + 65) + letters
        index = index // 26 - 1
    return letters


def _cell(ref: str, value, style: int) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    text = escape(str(value if value is not None else ""))
    return (
        f'<c r="{ref}" s="{style}" t="inlineStr">'
        f'<is><t xml:space="preserve">{text}</t></is></c>'
    )


def _sheet_xml(rows: list[list], widths: list[int]) -> str:
    cols = "".join(
        f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>'
        for i, w in enumerate(widths)
    )
    body = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row):
            if r == 1:
                style = HEADER
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                style = NUMBER
            else:
                style = WRAP
            cells.append(_cell(f"{_column(c)}{r}", value, style))
        height = ' ht="30" customHeight="1"' if r == 1 else ""
        body.append(f'<row r="{r}"{height}>{"".join(cells)}</row>')
    last = f"{_column(max(0, len(widths) - 1))}{max(1, len(rows))}"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        f'<cols>{cols}</cols>'
        f'<sheetData>{"".join(body)}</sheetData>'
        f'<autoFilter ref="A1:{last}"/>'
        '</worksheet>'
    )


STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="3">'
    '<font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><color rgb="FFF4F1E8"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font>'
    '</fonts>'
    '<fills count="3">'
    '<fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid">'
    '<fgColor rgb="FF14463B"/><bgColor indexed="64"/></patternFill></fill>'
    '</fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="5">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1"'
    ' applyFill="1" applyAlignment="1">'
    '<alignment vertical="center" wrapText="1"/></xf>'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
    '<alignment vertical="top" wrapText="1"/></xf>'
    '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
    '<alignment horizontal="right" vertical="top"/></xf>'
    '</cellXfs>'
    '<cellStyles count="1">'
    '<cellStyle name="Normal" xfId="0" builtinId="0"/>'
    '</cellStyles>'
    '</styleSheet>'
)


def write_workbook(path: Path, sheets: list[tuple[str, list[list], list[int]]]) -> None:
    names = "".join(
        f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (name, _rows, _widths) in enumerate(sheets, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{names}</sheets></workbook>'
    )
    rels = "".join(
        '<Relationship Id="rId{0}" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/worksheet" Target="worksheets/'
        'sheet{0}.xml"/>'.format(i)
        for i in range(1, len(sheets) + 1)
    )
    style_rel = len(sheets) + 1
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{rels}'
        f'<Relationship Id="rId{style_rel}" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType='
        '"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f'{overrides}</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", content_types)
        book.writestr("_rels/.rels", root_rels)
        book.writestr("xl/workbook.xml", workbook)
        book.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        book.writestr("xl/styles.xml", STYLES)
        for i, (_name, rows, widths) in enumerate(sheets, start=1):
            book.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(rows, widths))


# --------------------------------------------------------------- contenido --
def _sheet_meta() -> tuple[str, list[list], list[int]]:
    rows = [[
        "Pieza", "Estado", "Gravedad", "Qué pasa hoy", "Qué hay que hacer",
        "Dónde",
    ]]
    rows += [
        [
            "Cuerpos de las plantillas proactivas", "BLOQUEA", "Alta",
            "Los cinco avisos al titular (resumen diario, cierre, semanal, aviso "
            "fiscal y propuesta de cobro) meten el mensaje entero en un único "
            "hueco {{1}}. Meta rechaza en revisión toda plantilla cuyo cuerpo sea "
            "solo una variable, y rechaza el envío si el valor lleva saltos de "
            "línea. Hoy esos cinco avisos no pueden llegar nunca.",
            "Aprobar los cuerpos ya redactados en noesis/whatsapp_templates.py y "
            "partir el texto en valores de una línea en scheduler.py.",
            "src/noesis/web/scheduler.py · _deliver_template",
        ],
        [
            "Cuerpos de las plantillas al cliente", "OK", "—",
            "Recordatorio de cobro, factura lista, seguimiento de presupuesto y "
            "recordatorio de cita ya envían valores sueltos de una línea y "
            "encajan con el cuerpo declarado.",
            "Crearlas en WhatsApp Manager con el cuerpo de la hoja «Plantillas Meta».",
            "src/noesis/internal_brain.py · src/noesis/tools.py",
        ],
        [
            "Saneado de parámetros", "HECHO", "—",
            "Un nombre de cliente con un salto de línea o cuatro espacios "
            "seguidos hacía fallar el mensaje entero sin explicación.",
            "Resuelto: whatsapp.template_param aplana y corta a 1024 caracteres "
            "al encolar cualquier plantilla.",
            "src/noesis/web/whatsapp.py · template_param",
        ],
        [
            "Rechazos definitivos de Meta", "HECHO", "—",
            "Un 400 de Meta (plantilla inexistente, destinatario inválido) se "
            "reintentaba seis veces durante una hora antes de darse por vencido.",
            "Resuelto: MetaRejected cancela el envío al instante y deja el motivo "
            "en el outbox; 408, 429 y 5xx siguen reintentándose con espera.",
            "src/noesis/web/whatsapp.py · _post_to_meta / process_outbox",
        ],
        [
            "Atajo de cobro con aridad rota", "HECHO", "—",
            "send_payment_reminder mandaba 3 valores a la plantilla de cobro, que "
            "espera 5. No lo usaba nadie, pero el primero que lo usara se comía "
            "un rechazo de Meta.",
            "Resuelto: retirado. Queda queue_payment_reminder, con los 5 valores.",
            "src/noesis/web/whatsapp.py",
        ],
        [
            "Contrato de las plantillas", "HECHO", "—",
            "Los nombres vivían en config.py y los cuerpos no vivían en ningún "
            "sitio: no había forma de dar de alta una plantilla en Meta sin "
            "adivinar el texto ni de comprobar que lo enviado encajaba.",
            "Resuelto: noesis/whatsapp_templates.py declara nombre, categoría, "
            "cuerpo y huecos. `python -m noesis.whatsapp_templates` imprime lo "
            "que hay que pegar en WhatsApp Manager y avisa de lo que no cuadra.",
            "src/noesis/whatsapp_templates.py",
        ],
        [
            "Webhook: firma y verificación", "OK", "—",
            "GET con hub.verify_token y POST con X-Hub-Signature-256 en HMAC "
            "SHA-256 comparado en tiempo constante. Sin secreto solo pasa fuera "
            "de producción. Tope de tamaño con MAX_JSON_BYTES antes de parsear.",
            "Nada. Comprobar el rechazo de firma falsa en el smoke con número real.",
            "src/noesis/web/routers/webhooks.py · whatsapp.verify_signature",
        ],
        [
            "Webhook: idempotencia", "OK", "—",
            "Cada mensaje y cada estado se reclaman en webhook_events antes de "
            "actuar y solo se cierran al terminar los efectos; un reintento de "
            "Meta no duplica gastos ni facturas. Un estado que se adelanta al "
            "commit del envío no se consume y vuelve a entregarse.",
            "Nada.",
            "src/noesis/web/whatsapp.py · handle_inbound / _handle_status",
        ],
        [
            "Webhook: tiempo de respuesta", "REVISAR", "Media",
            "El POST responde cuando ha terminado todo: descarga del medio, OCR, "
            "extracción con IA y respuesta. Una foto de ticket puede tardar más "
            "de lo que Meta espera; si Meta corta y reintenta, el segundo intento "
            "choca con el evento en curso y devuelve 503 en bucle.",
            "Medir el peor caso con el número real. Si se pasa, contestar 200 al "
            "instante y procesar el medio en segundo plano.",
            "src/noesis/web/routers/webhooks.py · whatsapp_inbound",
        ],
        [
            "Descarga de medios", "OK", "—",
            "Solo acepta URLs https de facebook.com, fbsbx.com y fbcdn.net, sin "
            "usuario ni contraseña en la URL, y no sigue redirecciones fuera de "
            "esos dominios: el bearer no se filtra. Tamaño acotado antes de leer.",
            "Nada.",
            "src/noesis/web/whatsapp.py · _download_media",
        ],
        [
            "Cola de salida durable", "OK", "—",
            "Todo mensaje se persiste antes de salir, se reclama con BEGIN "
            "IMMEDIATE y SKIP LOCKED en Postgres, reintenta con espera creciente "
            "y respeta la clave de idempotencia por negocio. Los estados no "
            "retroceden aunque Meta los entregue desordenados.",
            "Nada.",
            "src/noesis/db.py · whatsapp_outbox",
        ],
        [
            "Ventana de 24 horas", "OK", "—",
            "El texto libre solo se usa respondiendo a un mensaje entrante; todo "
            "lo que Noesis inicia va por plantilla. La regla se cumple por "
            "diseño, no por comprobación.",
            "Nada mientras no se añada un proactivo en texto libre.",
            "src/noesis/web/whatsapp.py · send / send_template",
        ],
        [
            "Credenciales y alta en Meta", "PENDIENTE", "Alta",
            "WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_VERIFY_TOKEN y "
            "WHATSAPP_APP_SECRET están sin rellenar: is_configured() es falso y "
            "no sale ni un mensaje. El readiness ya lo marca como bloqueante.",
            "Verificar la empresa, dar de alta el número, generar token "
            "permanente y suscribir el webhook al campo messages.",
            ".env · docs/Conectar-APIs.md sección 4",
        ],
        [
            "Versión de la Graph API", "REVISAR", "Baja",
            "META_GRAPH_VERSION fija v23.0. Las versiones de Meta caducan a los "
            "dos años y la llamada empieza a fallar sin avisar antes.",
            "Confirmar la versión vigente al encender Meta y anotar la fecha de "
            "caducidad en el calendario.",
            "src/noesis/config.py:418",
        ],
        [
            "Coste por mensaje", "REVISAR", "Media",
            "La documentación interna calcula el margen con el modelo antiguo de "
            "Meta, el de «conversación iniciada por la empresa» de 24 horas. Meta "
            "cambió a cobro por mensaje de plantilla, con la categoría utility "
            "gratis dentro de una ventana de atención abierta.",
            "Rehacer el cálculo de margen con la tarifa vigente en España antes "
            "de fijar precios sobre el número de avisos.",
            "docs/Unit-economics-y-cerebro-interno.md",
        ],
    ]
    return "Meta (WhatsApp)", rows, [34, 12, 11, 62, 52, 40]


def _sheet_templates() -> tuple[str, list[list], list[int]]:
    from noesis import whatsapp_templates as wt

    rows = [[
        "Plantilla", "Categoría", "Destinatario", "Para qué", "Huecos",
        "Valores que envía el código", "Estado", "Cuerpo exacto para Meta",
        "Qué va en cada hueco",
    ]]
    for spec in wt.SPECS:
        sent = wt.SENT_PARAMS.get(spec.setting)
        ok = sent == spec.placeholders and not spec.problems()
        rows.append([
            spec.name, spec.category, spec.audience, spec.purpose,
            spec.placeholders, sent if sent is not None else "",
            "LISTA" if ok else "AJUSTAR EL CÓDIGO",
            spec.body,
            "\n".join(
                f"{{{{{i}}}}} = {text}"
                for i, text in enumerate(spec.params, start=1)
            ),
        ])
    return "Plantillas Meta", rows, [32, 11, 13, 44, 8, 12, 18, 60, 44]


def _sheet_trades() -> tuple[str, list[list], list[int]]:
    from noesis import trades

    rows = [[
        "Oficio", "Partida", "Qué es", "Unidad", "Precio orientativo (€)",
        "IVA (%)", "Cuenta para la regla del 40%",
    ]]
    for key, data in trades.TRADE_CATALOGS.items():
        for name, kind, price, vat, unit in data["items"]:
            rows.append([
                data["label"], name,
                "material" if kind == "producto" else "mano de obra",
                unit, price, vat,
                "sí" if kind == "producto" else "no",
            ])
    return "Plantillas por oficio", rows, [22, 38, 15, 12, 20, 9, 26]


def _sheet_summary() -> tuple[str, list[list], list[int]]:
    from noesis import trades, whatsapp_templates as wt

    listas = sum(
        1 for spec in wt.SPECS
        if wt.SENT_PARAMS.get(spec.setting) == spec.placeholders
    )
    partidas = sum(len(data["items"]) for data in trades.TRADE_CATALOGS.values())
    rows = [
        ["Bloque", "Estado", "Detalle"],
        [
            "Canal de Meta: código", "Listo salvo los proactivos",
            "Webhook, firma, idempotencia, descarga de medios y cola durable "
            "están construidos y probados sin depender de Meta. Los cinco avisos "
            "al titular necesitan repartirse en huecos antes de poder aprobarse.",
        ],
        [
            "Canal de Meta: plantillas", f"{listas} de {len(wt.SPECS)} listas",
            "Las que van al cliente encajan con su cuerpo. Las cinco del titular "
            "mandan el mensaje entero en un hueco y Meta no las aprobaría.",
        ],
        [
            "Canal de Meta: cuenta", "Sin encender",
            "Faltan token, phone id, verify token y app secret. Hasta que estén, "
            "no sale ningún mensaje y el readiness lo marca como bloqueante.",
        ],
        [
            "Plantillas por oficio", "Con pantalla propia",
            f"{len(trades.TRADE_CATALOGS)} oficios y {partidas} partidas con su "
            "IVA, visibles y cargables desde /b/{id}/oficios. Antes solo existían "
            "en código y en dos endpoints sin interfaz.",
        ],
        [
            "Aviso del 40% en obras", "Activo",
            "Cada partida dice si es material o mano de obra; al facturar con "
            "líneas al 10% Noesis avisa si el material pasa del 40% de la base. "
            "Avisa, no cambia el tipo.",
        ],
    ]
    return "Resumen", rows, [30, 30, 86]


def build() -> Path:
    sheets = [
        _sheet_summary(),
        _sheet_meta(),
        _sheet_templates(),
        _sheet_trades(),
    ]
    write_workbook(OUTPUT, sheets)
    return OUTPUT


if __name__ == "__main__":
    path = build()
    print(f"{path.relative_to(ROOT)} generado el {date.today().isoformat()}")
