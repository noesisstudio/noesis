"""Orquestación de documentos: subir, validar, leer (OCR) y borrar.

Es el ÚNICO punto que usa el servidor web. Encadena storage (disco) + repo (BD) +
ocr (lectura), de forma que la lógica delicada (validaciones, límites, OCR) está
toda junta y aislada.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from .. import config
from . import malware, ocr, pdf_ocr, pdf_text, repo, storage, validation


class UploadError(Exception):
    """Error de validación al subir un documento (mensaje apto para el usuario)."""


class TransientUploadError(UploadError):
    """El archivo es válido, pero una defensa obligatoria no está disponible."""


class DuplicateDocument(UploadError):
    """El contenido ya está archivado en el mismo negocio."""

    def __init__(self, existing_id: int):
        self.existing_id = int(existing_id)
        super().__init__(
            f"Este archivo ya estaba guardado como documento {self.existing_id}."
        )


def _existing_document(business_id: int, data: bytes, digest: str) -> dict | None:
    """Encuentra huellas nuevas y completa históricos sin recorrer otros negocios."""
    from .. import db

    existing = repo.find_by_content_hash(business_id, digest)
    if existing:
        return existing
    for candidate in repo.legacy_hash_candidates(business_id, len(data)):
        previous = storage.read(business_id, candidate["stored_name"])
        if previous is None or hashlib.sha256(previous).hexdigest() != digest:
            continue
        try:
            return repo.set_content_hash(candidate["id"], business_id, digest) or candidate
        except db.IntegrityError:  # la restricción única resuelve una carrera
            return repo.find_by_content_hash(business_id, digest)
    return None


def upload(business_id: int, filename: str, data: bytes, *, kind: str = "documento",
           client_id: int | None = None, invoice_id: int | None = None,
           project_id: int | None = None,
           note: str | None = None, run_ocr: bool = True,
           auto_classify: bool = False) -> dict:
    """Valida y guarda un documento. Si es imagen y hay OCR, intenta leer el importe.

    Lanza UploadError con un mensaje claro si el archivo no es válido.
    """
    from .. import db

    if not data:
        raise UploadError("El archivo está vacío.")
    if not storage.is_allowed(filename):
        raise UploadError("Formato no admitido. Sube un PDF o una foto (JPG/PNG/WEBP/HEIC).")
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise UploadError(f"El archivo supera el límite de {config.MAX_UPLOAD_MB} MB.")
    try:
        validation.validate(filename, data)
    except validation.UnsafeDocument as exc:
        raise UploadError(str(exc)) from exc
    try:
        scan = malware.scan(data)
    except malware.ScannerUnavailable as exc:
        if config.CLAMAV_REQUIRED:
            from .. import db
            db.record_security_event(
                "document.scan_unavailable",
                severity="critical",
                area="documents",
                subject_business_id=business_id,
                metadata={"required": True},
            )
            raise TransientUploadError(
                "No puedo comprobar la seguridad del archivo ahora. Intentalo de nuevo."
            ) from exc
        scan = malware.ScanResult("unavailable")
    if scan.status == "malware":
        from .. import db
        db.record_security_event(
            "document.malware_blocked",
            severity="critical",
            area="documents",
            subject_business_id=business_id,
            metadata={"scanner": "clamav"},
        )
        raise UploadError("El archivo no ha superado el control de seguridad.")
    if client_id not in (None, ""):
        try:
            client_id = int(client_id)
        except (TypeError, ValueError) as exc:
            raise UploadError("El cliente no es válido.") from exc
        if not db.get_client(client_id, business_id):
            raise UploadError("El cliente no pertenece a este negocio.")
    else:
        client_id = None
    if invoice_id not in (None, ""):
        try:
            invoice_id = int(invoice_id)
        except (TypeError, ValueError) as exc:
            raise UploadError("La factura no es válida.") from exc
        invoice = db.get_invoice(invoice_id, business_id)
        if not invoice:
            raise UploadError("La factura no pertenece a este negocio.")
        invoice_client_id = invoice.get("client_id")
        if client_id is None and invoice_client_id:
            client_id = int(invoice_client_id)
        elif client_id and invoice_client_id not in (None, client_id):
            raise UploadError("El cliente no coincide con la factura.")
    else:
        invoice_id = None
    if project_id not in (None, ""):
        try:
            project_id = int(project_id)
        except (TypeError, ValueError) as exc:
            raise UploadError("El proyecto no es válido.") from exc
        project = db.get_project(project_id, business_id)
        if not project:
            raise UploadError("El proyecto no pertenece a este negocio.")
        project_client_id = project.get("client_id")
        if client_id is None and project_client_id:
            client_id = int(project_client_id)
        elif client_id and project_client_id not in (None, client_id):
            raise UploadError("El cliente no coincide con el proyecto.")
    else:
        project_id = None

    content_sha256 = hashlib.sha256(data).hexdigest()
    existing = _existing_document(business_id, data, content_sha256)
    if existing:
        raise DuplicateDocument(existing["id"])

    ocr_text = ocr_amount = None
    if run_ocr:
        if storage.ext_of(filename) in storage.IMAGE_EXTS:
            result = ocr.extract(data)
            if result:
                ocr_text = result.get("text") or None
                ocr_amount = result.get("amount")
        elif storage.ext_of(filename) == ".pdf":
            ocr_text = pdf_text.extract(data)
            # Un PDF escaneado suele no tener capa de texto. Solo entonces se
            # rasteriza localmente; no duplicamos trabajo en documentos digitales.
            if not ocr_text or len(ocr_text.strip()) < 24:
                scanned_text = pdf_ocr.extract(data)
                if scanned_text:
                    ocr_text = scanned_text
            ocr_amount = ocr.detect_amount(ocr_text)

    stored_name = storage.save(business_id, filename, data)
    try:
        doc = repo.add(
            business_id, filename=filename, stored_name=stored_name,
            mime=storage.mime_for(filename), size=len(data), kind=kind,
            client_id=client_id, invoice_id=invoice_id, project_id=project_id, note=note,
            ocr_text=ocr_text, ocr_amount=ocr_amount,
            doc_status="pendiente_revisar" if auto_classify else "revisado",
            content_sha256=content_sha256,
        )
    except db.IntegrityError as exc:
        storage.delete(business_id, stored_name)
        existing = repo.find_by_content_hash(business_id, content_sha256)
        if existing:
            raise DuplicateDocument(existing["id"]) from exc
        raise
    except Exception:
        storage.delete(business_id, stored_name)
        raise
    if auto_classify:
        proposal = classify(business_id, doc["id"])
        doc = repo.get(doc["id"], business_id) or doc
        doc["classification"] = proposal
    return doc


def _fold_reference(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def associate_context(business_id: int, doc_id: int, reference: str | None,
                      *, customer: str | None = None,
                      customer_nif: str | None = None) -> dict:
    """Relaciona un documento solo ante una coincidencia inequívoca.

    Se prioriza el proyecto citado (y de él se hereda el cliente). Si el texto
    encaja con más de una opción, no se adivina: el documento queda sin asociar.
    """
    from .. import db

    document = repo.get(doc_id, business_id)
    if not document:
        return {"document": None, "matched": None, "ambiguous": False}
    folded = _fold_reference(reference)

    def mentioned(name: str | None) -> bool:
        candidate = _fold_reference(name)
        return bool(candidate and folded and re.search(
            rf"(?:^| )({re.escape(candidate)})(?: |$)", folded
        ))

    projects = [project for project in db.list_projects(business_id)
                if mentioned(project.get("name"))]
    if len(projects) == 1:
        project = projects[0]
        saved = repo.set_context(
            doc_id, business_id, project_id=project["id"],
            client_id=project.get("client_id"),
        )
        return {"document": saved, "matched": "project",
                "label": project.get("name"), "ambiguous": False}
    if len(projects) > 1:
        return {"document": document, "matched": None, "ambiguous": True}

    clients = db.list_clients(business_id)
    if customer_nif:
        target_nif = re.sub(r"\W", "", customer_nif).upper()
        by_nif = [client for client in clients if re.sub(
            r"\W", "", str(client.get("nif") or "")
        ).upper() == target_nif]
        if len(by_nif) == 1:
            client = by_nif[0]
            saved = repo.set_context(doc_id, business_id, client_id=client["id"])
            return {"document": saved, "matched": "client",
                    "label": client.get("name"), "ambiguous": False}
    named = [client for client in clients if mentioned(client.get("name"))]
    if not named and customer:
        customer_folded = _fold_reference(customer)
        named = [client for client in clients
                 if _fold_reference(client.get("name")) == customer_folded]
    if len(named) == 1:
        client = named[0]
        saved = repo.set_context(doc_id, business_id, client_id=client["id"])
        return {"document": saved, "matched": "client",
                "label": client.get("name"), "ambiguous": False}
    return {"document": document, "matched": None,
            "ambiguous": len(named) > 1}


def classify(business_id: int, doc_id: int) -> dict | None:
    """Clasificación única para web y WhatsApp, siempre pendiente de confirmación."""
    from .. import db
    from ..adapters import extraction

    doc = repo.get(doc_id, business_id)
    payload = file_bytes(business_id, doc_id) if doc else None
    if not doc or not payload:
        return None
    data, mime, filename = payload
    business = db.get_business(business_id) or {}
    proposal = extraction.classify_document(
        data, mime, filename,
        text_hint=doc.get("ocr_text"),
        business_name=business.get("name"), business_nif=business.get("nif"),
        allow_external=db.integration_enabled(
            business_id, "ai_external", available=bool(config.ANTHROPIC_API_KEY)
        ),
    )
    kind = proposal.get("kind") or "documento"
    confidence = float(proposal.get("confidence") or 0)
    reason = proposal.get("reason") or "Revisa el tipo antes de registrarlo."
    # Una propuesta dudosa no cambia el tipo a la fuerza.
    applied_kind = kind if confidence >= 65 else "documento"
    repo.record_classification(
        doc_id, business_id, detected_kind=kind, confidence=confidence,
        method=proposal.get("method") or "heuristica", reason=reason,
    )
    repo.set_review(
        doc_id, business_id, kind=applied_kind,
        doc_status="pendiente_revisar", confidence=confidence,
        review_note=reason,
    )
    db.record_product_event(
        business_id, "document_classified",
        json.dumps({"kind": kind, "method": proposal.get("method"),
                    "confidence": round(confidence)}, separators=(",", ":")),
    )
    return {**proposal, "applied_kind": applied_kind,
            "needs_confirmation": True, "document_id": doc_id}


def file_bytes(business_id: int, doc_id: int) -> tuple[bytes, str, str] | None:
    """Devuelve (bytes, mime, filename) de un documento, o None si no existe."""
    doc = repo.get(doc_id, business_id)
    if not doc:
        return None
    data = storage.read(business_id, doc["stored_name"])
    if data is None:
        return None
    return data, doc.get("mime") or "application/octet-stream", doc["filename"]


def delete(business_id: int, doc_id: int) -> bool:
    """Borra metadato + fichero físico. True si existía."""
    doc = repo.delete(doc_id, business_id)
    if not doc:
        return False
    storage.delete(business_id, doc["stored_name"])
    return True


def invoice_draft(business_id: int, doc_id: int) -> dict | None:
    """Borrador de factura extraído por IA del documento, con dirección detectada.

    NUNCA crea registros: devuelve datos para que el usuario los revise. Si la IA
    no está disponible o no está segura, devuelve lo que haya (o None) y el
    documento queda pendiente de revisión manual. Los datos del documento son
    datos, no instrucciones (defensa en adapters/extraction.py).
    """
    from .. import db
    from ..adapters import extraction

    doc = repo.get(doc_id, business_id)
    if not doc:
        return None
    payload = file_bytes(business_id, doc_id)
    if not payload:
        return None
    data, mime, _filename = payload
    draft = extraction.extract_invoice(
        data, mime,
        allow_external=db.integration_enabled(
            business_id, "ai_external", available=bool(config.ANTHROPIC_API_KEY)
        ),
    )
    if draft is None:
        repo.set_review(doc_id, business_id, doc_status="pendiente_revisar",
                        review_note="Sin extracción automática: revisar a mano.")
        return None
    business = db.get_business(business_id) or {}
    draft["direction"] = extraction.detect_direction(
        draft, business_nif=business.get("nif"),
        business_name=business.get("name"))
    kind = ("factura_emitida" if draft["direction"] == "emitida"
            else "factura_recibida" if draft["direction"] == "recibida"
            else None)
    repo.set_review(doc_id, business_id, kind=kind,
                    doc_status="pendiente_revisar",
                    confidence=draft.get("confidence"))
    if draft.get("supplier") or draft.get("supplier_nif"):
        known = db.find_supplier(business_id, nif=draft.get("supplier_nif"),
                                 name=draft.get("supplier"))
        draft["supplier_id"] = known["id"] if known else None
    if draft["direction"] == "emitida" and draft.get("customer"):
        try:
            candidate = db.propose_document_client(
                business_id,
                doc_id,
                name=draft.get("customer"),
                nif=draft.get("customer_nif"),
            )
        except ValueError as exc:
            candidate = None
            draft["client_resolution"] = {
                "status": "ambiguous",
                "message": str(exc),
            }
        else:
            if candidate:
                matched = candidate.get("matched_client") or {}
                draft["client_resolution"] = {
                    "status": candidate.get("status"),
                    "candidate_name": candidate.get("proposed_name"),
                    "candidate_nif": candidate.get("proposed_nif"),
                    "client_id": candidate.get("matched_client_id"),
                    "client_name": matched.get("name"),
                }
    return draft


def confirm_client_candidate(
    business_id: int,
    doc_id: int,
    *,
    name: str | None = None,
    nif: str | None = None,
) -> dict:
    """Alta o reutilización confirmada del cliente leído en una factura emitida."""
    from .. import db

    client = db.confirm_document_client_candidate(
        doc_id, business_id, name=name, nif=nif
    )
    db.record_product_event(
        business_id,
        "document_client_confirmed",
        json.dumps(
            {"document_id": int(doc_id), "client_id": int(client["id"])},
            separators=(",", ":"),
        ),
    )
    return client


def confirm_received_invoice(business_id: int, doc_id: int, *, total,
                             supplier_name: str | None = None,
                             supplier_nif: str | None = None,
                             supplier_id: int | None = None,
                             **fields) -> dict:
    """Confirmación humana del borrador: crea la recibida y vincula el documento.

    Crea el proveedor si no existe (por NIF o nombre exacto). Lanza ValueError
    con mensaje apto para el usuario si algo no cuadra.
    """
    from .. import db

    doc = repo.get(doc_id, business_id)
    if not doc:
        raise UploadError("Documento no encontrado.")
    if supplier_id is None and (supplier_name or supplier_nif):
        known = db.find_supplier(business_id, nif=supplier_nif,
                                 name=supplier_name)
        if known:
            supplier_id = known["id"]
        elif supplier_name:
            supplier_id = db.add_supplier(
                supplier_name, nif=supplier_nif, business_id=business_id)["id"]
    received = db.add_received_invoice(
        total, supplier_id=supplier_id, document_id=doc_id,
        business_id=business_id, **fields)
    repo.set_review(doc_id, business_id, kind="factura_recibida",
                    doc_status="revisado")
    repo.confirm_classification(doc_id, business_id, "factura_recibida")
    return received


def convert_ticket_to_expense(business_id: int, doc_id: int,
                              concept: str | None = None,
                              amount: float | None = None,
                              vat_rate: float | None = None,
                              spent_on: str | None = None) -> dict | None:
    """Convierte un ticket/factura escaneada en un gasto registrado.

    Usa el importe leído por OCR si no se pasa uno. Devuelve el gasto creado, o None
    si no hay importe disponible. Vincula el documento al gasto confirmado.
    """
    from .. import db
    doc = repo.get(doc_id, business_id)
    if not doc:
        return None
    amount = amount if amount is not None else doc.get("ocr_amount")
    if not amount or float(amount) <= 0:
        return None
    concept = (concept or doc.get("filename") or "Gasto de ticket").strip()
    expense = db.add_expense(
        concept,
        float(amount),
        vat_rate=vat_rate,
        category="Ticket",
        spent_on=spent_on,
        document_id=doc_id,
        project_id=doc.get("project_id"),
        business_id=business_id,
    )
    repo.set_review(doc_id, business_id, kind="ticket", doc_status="revisado")
    repo.confirm_classification(doc_id, business_id, "ticket")
    return expense
