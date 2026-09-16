"""Documentos que llegan por WhatsApp: guardar, leer, revisar con el titular y registrar.

Toda foto o PDF se guarda aunque no se entienda. Lo leído es una propuesta que el
titular corrige con frases cortas («total 45,20», «proveedor Leroy Merlin», «es un
gasto») y confirma con SÍ solo cuando las cifras cuadran. Un PDF con varias facturas
se separa y se revisa una a una; un extracto se contrasta con lo ya registrado para
no duplicar. Nada se contabiliza sin esa confirmación.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from .. import config, db
from ..documents import (
    local_reader, pdf_batch, reading as docreading, repo as docrepo, review,
    service as docservice,
)

log = logging.getLogger("noesis.whatsapp.documents")

PDF_MIME = "application/pdf"
PENDING_KIND = "doc_review"
REVIEW_TTL_MINUTES = 12 * 60
MAX_QUEUE = 20
_KIND_FOR_MODE = {"gasto": "ticket", "recibida": "factura_recibida", "emitida": "factura_emitida"}
_CONFIRM_WORDS = {
    "guardala", "guardalo", "registrala", "registralo", "apuntalo", "apuntala",
    "confirmo", "correcto", "esta bien", "perfecto", "de acuerdo",
}
_CONFIRM_ALL = re.compile(
    r"(?:si\s+)?(?:a\s+)?(?:todas|todos|totes|tots)(?:\s+si)?"
    r"|(?:guarda|registra|apunta)(?:las|los|les)?\s+(?:todas|todos|totes)"
)
_STOP = re.compile(r"cancela(?:r)?(?:\s+(?:todo|la\s+revision))?|para|dejalo|olvidalo|basta|stop")
_SKIP = re.compile(r"salta(?:la|lo)?|siguiente|descarta(?:la|lo)?|pasa|otra|next")
_SHOW = re.compile(r"ver|resumen|como\s+queda|como\s+esta|muestra(?:mela|melo)?")
_CORRECTION_START = re.compile(
    r"(?:no\s*,?\s*)?(?:el\s+|la\s+)?(?:total|importe|import|base|iva|cuota|irpf|retencion|proveedor|"
    r"emisor|nif|cif|fecha|data|vence|vencimiento|numero|num|concepto|es\s+un|es\s+una|es\s+de|son)\b"
)
_OTHER_ORDER = re.compile(
    r"(?:factura\s+a|crea|creame|hazme|haz|prepara|presupuesto|agenda|cobra|reclama|cuanto|"
    r"que|cual|dame|pasame|enviame|envia|manda|emite|borra|elimina|resumen\s+del)\b"
)


def review_key(phone: str) -> str:
    return f"doc-review:{phone}"


def _ai_allowed(business_id: int) -> bool:
    """Tope diario de lecturas con IA por negocio y consentimiento de IA externa."""
    today = datetime.now().strftime("%Y-%m-%d")
    used = db.count_product_events(business_id, "media_ingested", since=today)
    if used >= config.MAX_DAILY_EXTRACTIONS:
        return False
    return db.integration_enabled(
        business_id, "ai_external", available=bool(config.ANTHROPIC_API_KEY)
    )


def _linked_label(document: dict) -> str | None:
    if document.get("expense_id"):
        return "gasto"
    if document.get("received_invoice_id"):
        return "factura recibida"
    if document.get("invoice_id"):
        return "factura emitida"
    return None


def _norm_number(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper()).lstrip("0")


def _clean_id(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _received_duplicate(business_id: int, values: dict) -> dict | None:
    """Factura recibida ya registrada: mismo proveedor y número, o importe y fecha."""
    number = _norm_number(values.get("number"))
    nif = _clean_id(values.get("supplier_nif"))
    supplier = local_reader.fold(values.get("supplier")).strip()
    total = values.get("total")
    for row in db.list_received_invoices(business_id):
        same_supplier = bool(
            (nif and _clean_id(row.get("supplier_nif")) == nif)
            or (supplier and local_reader.fold(row.get("supplier_name")).strip() == supplier)
        )
        if number and _norm_number(row.get("number")) == number and (
            same_supplier or not (nif or supplier)
        ):
            return row
        if (
            same_supplier and total is not None and row.get("total") is not None
            and abs(float(row["total"]) - float(total)) < 0.01
            and values.get("issued_on") and str(row.get("issued_on") or "") == values["issued_on"]
        ):
            return row
    return None


def _page_ranges(documents: list[dict], count: int) -> str | None:
    """Rangos completos para separar el PDF; None si las páginas no son fiables."""
    if not 2 <= len(documents) <= pdf_batch.MAX_PARTS or count < len(documents):
        return None
    starts = []
    for document in documents:
        pages = document.get("pages")
        if not pages:
            return None
        starts.append(int(pages[0]))
    if starts != sorted(starts) or len(set(starts)) != len(starts) or starts[-1] > count:
        return None
    starts[0] = 1
    ranges = []
    for index, start in enumerate(starts):
        end = starts[index + 1] - 1 if index + 1 < len(starts) else count
        if end < start:
            return None
        ranges.append(f"{start}-{end}")
    return ";".join(ranges)


def _split_pdf(business_id: int, doc_id: int, documents: list[dict], count: int) -> list[int] | None:
    ranges = _page_ranges(documents, count)
    if not ranges:
        return None
    try:
        outcome = pdf_batch.split(business_id, doc_id, ranges)
    except Exception as exc:  # noqa: BLE001 - separar es una mejora, nunca un bloqueo.
        log.info("No se pudo separar el PDF de varias facturas: %s", type(exc).__name__)
        return None
    parts = outcome.get("documents") or []
    if not outcome.get("ok") or len(parts) != len(documents):
        return None
    return [int(part["id"]) for part in parts]


def _statement_queue(business: dict, document: dict, statement: dict,
                     source: str) -> tuple[list[dict], str]:
    business_id = business["id"]
    rows = statement.get("items") or []
    own = _clean_id(business.get("nif"))
    issuer = statement.get("issuer")
    name = local_reader.fold(business.get("name")).strip()
    issued_by_business = bool(
        (own and _clean_id(statement.get("issuer_nif")) == own)
        or (len(name) > 3 and name in local_reader.fold(issuer))
    )
    if issued_by_business:
        invoices = {
            _norm_number(invoice.get("number")): invoice
            for invoice in db.list_invoices(business_id) if invoice.get("number")
        }
        found = [invoices.get(_norm_number(row["number"])) for row in rows]
        known = [invoice for invoice in found if invoice]
        unpaid = sum(1 for invoice in known if invoice.get("status") not in ("cobrada", "anulada"))
        missing = [row["number"] for row, invoice in zip(rows, found) if not invoice]
        text = f"📑 Es una relación de {len(rows)} facturas emitidas por ti. {len(known)} constan en Bynoesis"
        text += f" ({unpaid} pendientes de cobro)." if known else "."
        if missing:
            text += " No constan: " + ", ".join(missing[:10]) + ("…" if len(missing) > 10 else "") + "."
        text += " No he creado ni cambiado nada: las facturas emitidas se crean desde Facturas."
        return [], text
    already = []
    items = []
    for row in rows:
        values = {
            "supplier": issuer, "supplier_nif": statement.get("issuer_nif"),
            "number": row.get("number"), "total": row.get("total"),
            "issued_on": row.get("issued_on"), "due_on": row.get("due_on"),
        }
        if _received_duplicate(business_id, values):
            already.append(row.get("number"))
            continue
        items.append(review.new_item(
            fields=values, kind="factura_recibida", business=business, document_id=None,
            origin_document_id=document["id"], source=source, media="document",
            note="De un extracto solo tengo el total. Para deducir el IVA, envíame también la factura original.",
        ))
    intro = f"📑 Es un extracto{(' de ' + issuer) if issuer else ''} con {len(rows)} facturas."
    if already:
        intro += f" {len(already)} ya {'consta' if len(already) == 1 else 'constan'} en Bynoesis."
    if items:
        intro += f" Te enseño una a una las {len(items)} que no constan." if len(items) > 1 else " Te enseño la que no consta."
    else:
        intro += " No hay nada nuevo que apuntar."
    return items[:MAX_QUEUE], intro


def _record_reading(business_id: int, doc_id: int, item: dict, entry: dict, source: str) -> None:
    kind = _KIND_FOR_MODE.get(item["mode"]) or item.get("archive_kind") or "documento"
    confidence = entry.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = {"ia": 80, "mixto": 80, "texto": 60}.get(source, 0)
    docrepo.record_classification(
        doc_id, business_id, detected_kind=kind, confidence=float(confidence),
        method=f"whatsapp_{source}"[:30],
        reason="Lectura por WhatsApp pendiente de confirmar por el titular.",
    )
    # El tipo no se promociona hasta que el titular confirma: queda pendiente.
    docrepo.set_review(
        doc_id, business_id, doc_status="pendiente_revisar", confidence=float(confidence),
        review_note="Leído por WhatsApp; pendiente de tu confirmación.",
    )


def _unfinished(pending: dict | None) -> int:
    if not pending:
        return 0
    try:
        payload = json.loads(pending.get("payload") or "{}")
        return max(0, len(payload.get("items") or []) - int(payload.get("index") or 0))
    except (TypeError, ValueError):
        return 0


def _save(business_id: int, phone: str, payload: dict) -> None:
    db.set_pending_action(
        business_id, review_key(phone), PENDING_KIND, payload,
        ttl_minutes=REVIEW_TTL_MINUTES,
    )


def ingest(business: dict, phone: str, message: dict, *, data: bytes, filename: str,
           mime: str, media: str, notify) -> dict:
    """Foto o PDF entrante: guardar, leer una vez y abrir la revisión por chat."""
    business_id = business["id"]
    result = {"phone": phone, "media": media}
    already_stored = False
    try:
        document = docservice.upload(
            business_id, filename, data, kind="documento", note="Recibido por WhatsApp",
            run_ocr=True, pending_review=True,
        )
    except docservice.DuplicateDocument as exc:
        document = docrepo.get(exc.existing_id, business_id)
        if not document:
            notify("Ya tenía este archivo, pero no he podido volver a leerlo. Revísalo en Documentos.")
            return {**result, "ingested": False}
        already_stored = True
    except docservice.UploadError as exc:
        notify(str(exc))
        return {**result, "ingested": False}
    doc_id = document["id"]
    result.update(ingested=True, document_id=doc_id, already_stored=already_stored)
    opening = ("Ya lo tenía guardado y lo he vuelto a leer." if already_stored
               else "Guardado en tus papeles.")
    linked = _linked_label(document)
    if linked:
        notify(f"{opening} Este documento ya está registrado como {linked}; no lo vuelvo "
               "a apuntar. Si hay que corregirlo, hazlo desde la web.")
        return {**result, "pending": False, "linked": True, "classification": linked}
    if docrepo.is_batch_source(doc_id, business_id):
        notify(f"{opening} Este PDF ya lo separé en varias facturas. Revísalas en "
               "Documentos o envíame cada factura por separado.")
        return {**result, "pending": False, "batch": True, "classification": "documento"}

    context = docservice.associate_context(business_id, doc_id, message.get("caption"))
    if context.get("matched"):
        opening += f" Lo he asociado a {context['label']}."
    elif context.get("ambiguous"):
        opening += " Hay varias coincidencias de cliente o proyecto: revísalo en Documentos."

    try:
        found = docreading.read(
            business, document, data, mime, allow_ai=_ai_allowed(business_id),
            business_id=business_id,
        )
    except Exception as exc:  # noqa: BLE001 - leer nunca impide guardar ni revisar.
        log.warning("La lectura del documento falló: %s", type(exc).__name__)
        found = {"documents": [], "statement": None, "source": "ninguno", "page_count": 0}
    documents = found.get("documents") or []
    statement = found.get("statement")
    source = found.get("source") or "ninguno"
    db.record_product_event(
        business_id, "media_ingested",
        json.dumps({"type": media, "extracted": bool(documents or statement), "source": source,
                    "ai": bool(found.get("ai_used")), "documents": len(documents)},
                   separators=(",", ":")),
    )

    intro = ""
    classification = "documento"
    if statement and statement.get("items"):
        items, intro = _statement_queue(business, document, statement, source)
        classification = "extracto"
        docrepo.set_review(doc_id, business_id, doc_status="pendiente_revisar",
                           review_note="Extracto de varias facturas revisado por WhatsApp.")
    elif len(documents) >= 2:
        children = (_split_pdf(business_id, doc_id, documents, found.get("page_count") or 0)
                    if mime == PDF_MIME else None)
        items = [
            review.new_item(
                fields=entry, kind=entry.get("kind"), business=business,
                document_id=children[index] if children else None,
                origin_document_id=doc_id, source=source, pages=entry.get("pages"),
                conflicts=entry.get("conflicts"), guessed=entry.get("guessed"), media=media,
            )
            for index, entry in enumerate(documents[:MAX_QUEUE])
        ]
        intro = f"He encontrado {len(items)} facturas en este documento."
        if children:
            intro += " Las he separado en archivos distintos para que cada una tenga su original."
        else:
            docrepo.set_review(doc_id, business_id, doc_status="pendiente_revisar",
                               review_note=f"Contiene {len(items)} facturas; revisión por WhatsApp una a una.")
        intro += " Te las enseño una a una."
        classification = "varias_facturas"
    else:
        entry = documents[0] if documents else {}
        item = review.new_item(
            fields=entry, kind=entry.get("kind"), business=business, document_id=doc_id,
            source=source, conflicts=entry.get("conflicts"), guessed=entry.get("guessed"),
            media=media,
        )
        if message.get("caption"):
            review.apply_correction(item, message["caption"], labelled_only=True)
        items = [item]
        _record_reading(business_id, doc_id, item, entry, source)
        classification = _KIND_FOR_MODE.get(item["mode"]) or item.get("archive_kind") or "documento"

    previous = db.get_pending_action(business_id, review_key(phone))
    leftover = _unfinished(previous)
    if previous and json.loads(previous.get("payload") or "{}").get("document_id") == doc_id:
        leftover = 0
    if not items:
        notify(f"{opening}\n\n{intro}".strip())
        return {**result, "pending": False, "classification": classification}

    payload = {
        "version": 1, "document_id": doc_id, "items": items, "index": 0,
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    _save(business_id, phone, payload)
    header = opening + (f"\n\n{intro}" if intro else "")
    text = header + "\n\n" + review.render(items[0], position=1, count=len(items))
    if leftover:
        text += "\n\n(La revisión del documento anterior queda pendiente en Documentos.)"
    notify(text)
    return {**result, "pending": True, "items": len(items), "classification": classification}


# ----------------------------------------------------------------- respuestas


def _register(business: dict, item: dict, values: dict) -> str:
    """Crea el registro confirmado y devuelve la línea de respuesta."""
    business_id = business["id"]
    mode = item.get("mode")
    doc_id = item.get("document_id")
    if mode == "gasto":
        concept = values.get("concept") or values.get("supplier") or "Gasto por WhatsApp"
        if doc_id:
            expense = docservice.convert_ticket_to_expense(
                business_id, doc_id, concept=concept, amount=values["total"],
                vat_rate=values.get("vat_rate"), spent_on=values.get("issued_on"),
            )
            if expense is None:
                raise ValueError("no hay un importe válido.")
        else:
            expense = db.add_expense(
                concept, values["total"], vat_rate=values.get("vat_rate"), category="Ticket",
                spent_on=values.get("issued_on"), business_id=business_id,
            )
        return (f"Apuntado ✅ Gasto de {review.eur(expense['amount'])} ({expense['concept']})."
                + (" El justificante queda guardado en tus papeles." if doc_id else ""))
    if mode == "recibida":
        duplicate = _received_duplicate(business_id, values)
        if duplicate:
            if doc_id:
                docrepo.set_review(
                    doc_id, business_id, doc_status="duplicado",
                    review_note="Duplicado de una factura recibida ya registrada.",
                )
            label = duplicate.get("number") or review.eur(duplicate.get("total"))
            return (f"Esa factura ya constaba en Bynoesis ({label}"
                    + (f", {duplicate['supplier_name']}" if duplicate.get("supplier_name") else "")
                    + "). No la he vuelto a registrar.")
        fields = {
            key: values.get(key) for key in (
                "number", "issued_on", "due_on", "base", "vat_rate", "vat_amount", "irpf_amount",
            )
        }
        fields["concept"] = values.get("concept") or "Factura recibida por WhatsApp"
        if doc_id:
            received = docservice.confirm_received_invoice(
                business_id, doc_id, total=values["total"],
                supplier_name=values.get("supplier"), supplier_nif=values.get("supplier_nif"),
                **fields,
            )
        else:
            origin = item.get("origin_document_id")
            received = docservice.record_received_invoice(
                business_id, total=values["total"], supplier_name=values.get("supplier"),
                supplier_nif=values.get("supplier_nif"),
                note=f"Leída en el documento #{origin} recibido por WhatsApp." if origin else None,
                **fields,
            )
        supplier = values.get("supplier") or values.get("supplier_nif") or "proveedor"
        return (f"Hecho ✅ Factura recibida de {supplier} por {review.eur(received['total'])}."
                + (" El original y tu confirmación quedan guardados." if doc_id else ""))
    if mode == "emitida":
        if doc_id:
            docrepo.set_review(
                doc_id, business_id, kind="factura_emitida", doc_status="revisado",
                review_note="Factura emitida histórica archivada por WhatsApp; no se ha vuelto a emitir.",
            )
            docrepo.confirm_classification(doc_id, business_id, "factura_emitida")
        return "Archivada como factura emitida por ti ✅. No la he vuelto a emitir ni enviar."
    kind = item.get("archive_kind") or "documento"
    if doc_id:
        docrepo.set_review(doc_id, business_id, kind=kind, doc_status="revisado",
                           review_note="Tipo confirmado por WhatsApp.")
        docrepo.confirm_classification(doc_id, business_id, kind)
    return f"Archivado como {review.ARCHIVE_LABELS.get(kind, kind)} ✅."


def _close_origin(business_id: int, payload: dict) -> None:
    """Un original con varias facturas sin separar queda revisado al terminar la cola."""
    doc_id = payload.get("document_id")
    items = payload.get("items") or []
    if not doc_id or len(items) < 2 and not any(item.get("origin_document_id") for item in items):
        return
    if any(item.get("document_id") == doc_id for item in items):
        return
    if docrepo.is_batch_source(doc_id, business_id):
        return
    docrepo.set_review(doc_id, business_id, doc_status="revisado",
                       review_note="Revisado por WhatsApp: contenía varias facturas.")


def _advance(business: dict, phone: str, payload: dict, line: str) -> str:
    business_id = business["id"]
    items = payload["items"]
    payload["index"] = int(payload["index"]) + 1
    if payload["index"] >= len(items):
        db.clear_pending_action(business_id, review_key(phone))
        _close_origin(business_id, payload)
        return line + ("\n\nListo: he revisado todo el documento." if len(items) > 1 else "")
    _save(business_id, phone, payload)
    following = payload["index"]
    return line + "\n\n" + review.render(items[following], position=following + 1, count=len(items))


def _confirm_current(business: dict, phone: str, payload: dict) -> str:
    items = payload["items"]
    index = int(payload["index"])
    item = items[index]
    state = review.evaluate(item)
    if not state["ready"]:
        reasons = state["issues"] + [f"Me falta {missing}." for missing in state["missing"]]
        return ("Todavía no lo guardo:\n" + "\n".join(f"• {reason}" for reason in reasons)
                + "\n\n" + review.render(item, position=index + 1, count=len(items)))
    try:
        line = _register(business, item, state["values"])
    except (ValueError, TypeError, docservice.UploadError) as exc:
        return (f"No he podido guardarlo: {exc}\n\n"
                + review.render(item, position=index + 1, count=len(items)))
    item["done"] = True
    return _advance(business, phone, payload, line)


def _confirm_all(business: dict, phone: str, payload: dict) -> str:
    business_id = business["id"]
    items = payload["items"]
    start = int(payload["index"])
    saved, waiting, errors = [], [], []
    for item in items[start:]:
        state = review.evaluate(item)
        if not state["ready"]:
            waiting.append(item)
            continue
        try:
            saved.append(_register(business, item, state["values"]))
            item["done"] = True
        except (ValueError, TypeError, docservice.UploadError) as exc:
            values = state["values"]
            errors.append(f"{values.get('number') or values.get('supplier') or 'factura'}: {exc}")
            waiting.append(item)
    parts = []
    if saved:
        parts.append(f"He guardado {len(saved)}:\n" + "\n".join(f"• {line}" for line in saved))
    if errors:
        parts.append("No he podido guardar:\n" + "\n".join(f"• {line}" for line in errors))
    if not waiting:
        db.clear_pending_action(business_id, review_key(phone))
        _close_origin(business_id, payload)
        return "\n\n".join(parts + ["Listo: he revisado todo el documento."])
    payload["items"] = items[:start] + waiting
    payload["index"] = start
    _save(business_id, phone, payload)
    parts.append(f"Faltan datos en {len(waiting)}. Seguimos con esta:")
    return ("\n\n".join(parts) + "\n\n"
            + review.render(waiting[0], position=start + 1, count=len(payload["items"])))


def _skip_current(business: dict, phone: str, payload: dict) -> str:
    item = payload["items"][int(payload["index"])]
    item["skipped"] = True
    if item.get("document_id"):
        line = "Descartado. No he apuntado nada; el documento queda guardado en tus papeles."
    else:
        line = "Descartada. No la he apuntado."
    return _advance(business, phone, payload, line)


def handle_reply(business: dict, phone: str, text: str) -> str | None:
    """Respuesta del titular durante una revisión. None si el mensaje es para otra cosa."""
    business_id = business["id"]
    if not (text or "").strip():
        return None
    pending = db.get_pending_action(business_id, review_key(phone))
    if not pending or pending.get("kind") != PENDING_KIND:
        return None
    other = db.get_pending_action(business_id, phone)
    if other and str(other.get("created_at") or "") > str(pending.get("created_at") or ""):
        return None
    try:
        payload = json.loads(pending["payload"])
        items = payload["items"]
        index = int(payload.get("index") or 0)
        item = items[index]
    except (TypeError, ValueError, KeyError, IndexError):
        db.clear_pending_action(business_id, review_key(phone))
        return None
    from . import whatsapp as channel

    folded = local_reader.fold(text).strip().strip("!.¡¿?, ")
    if channel._is_yes(text) or folded in _CONFIRM_WORDS:
        return _confirm_current(business, phone, payload)
    if len(items) - index > 1 and _CONFIRM_ALL.fullmatch(folded):
        return _confirm_all(business, phone, payload)
    if _STOP.fullmatch(folded):
        db.clear_pending_action(business_id, review_key(phone))
        return "De acuerdo, no apunto nada más. Los documentos quedan guardados en tus papeles."
    if _OTHER_ORDER.match(folded) and not _CORRECTION_START.match(folded):
        return None
    correction = re.sub(r"^\s*no\s*[,.:;]?\s+(?=\S)", "", text, flags=re.I)
    changed, unknown = review.apply_correction(item, correction)
    if changed:
        _save(business_id, phone, payload)
        labels = list(dict.fromkeys(review.LABELS.get(field, field) for field in changed))
        reply = "Cambiado: " + ", ".join(labels) + "."
        if unknown:
            reply += " No he entendido: «" + "», «".join(unknown[:2]) + "»."
        return reply + "\n\n" + review.render(item, position=index + 1, count=len(items))
    if channel._is_no(text) or _SKIP.fullmatch(folded):
        return _skip_current(business, phone, payload)
    if _SHOW.fullmatch(folded):
        return review.render(item, position=index + 1, count=len(items))
    looks_like_correction = _CORRECTION_START.match(folded) or (
        re.search(r"\d", folded) and len(folded) <= 60
    )
    if looks_like_correction:
        return review.help_text() + "\n\n" + review.render(item, position=index + 1, count=len(items))
    return None
