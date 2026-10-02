"""Núcleo de mutación prestado; el propietario exterior confirma o revierte."""

from .. import db

from . import readers

from .boundary import run, positive_money, optional_money


def _mutate_add_received_invoice(
    conn,
    total,
    supplier_id=None,
    number=None,
    concept=None,
    issued_on=None,
    due_on=None,
    base=None,
    vat_rate=None,
    vat_amount=None,
    irpf_amount=None,
    category=None,
    note=None,
    document_id=None,
    *,
    business_id: int,
) -> dict:
    """Registra una factura recibida y, si se indica, la vincula a su documento.

    Nunca la crea la IA directamente: este es el paso de confirmación humana.
    """
    total = positive_money(total, "El total", legacy=conn.legacy)
    if vat_rate not in (None, ""):
        vat_rate = db._tax_rate(vat_rate, "El IVA", {0, 4, 10, 21})
    else:
        vat_rate = None
    for field_label, value in (
        ("La base", base),
        ("La cuota de IVA", vat_amount),
        ("El IRPF", irpf_amount),
    ):
        if value not in (None, "") and db.Decimal(str(value)) < 0:
            raise ValueError(f"{field_label} no puede ser negativa.")
    base = optional_money(conn, base) if base not in (None, "") else None
    vat_amount = optional_money(conn, vat_amount) if vat_amount not in (None, "") else None
    irpf_amount = optional_money(conn, irpf_amount) if irpf_amount not in (None, "") else None
    issued_on = db._optional_date(issued_on, "La fecha de emisión")
    due_on = db._optional_date(due_on, "El vencimiento")
    number = (number or "").strip()[:50] or None
    concept = (concept or "").strip()[:500] or None
    if supplier_id not in (None, ""):
        supplier = conn.execute(
            "SELECT id FROM suppliers WHERE id=? AND business_id=?", (supplier_id, business_id)
        ).fetchone()
        if not supplier:
            raise ValueError("Proveedor no encontrado.")
    else:
        supplier_id = None
    if document_id not in (None, ""):
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        document = conn.execute(
            "SELECT id, received_invoice_id, expense_id, invoice_id FROM documents WHERE id=? AND business_id=?"
            + lock,
            (document_id, business_id),
        ).fetchone()
        if not document:
            raise ValueError("Documento no encontrado.")
        if document["received_invoice_id"] is not None:
            raise ValueError("Este documento ya está vinculado a una factura recibida.")
        if document["invoice_id"] is not None:
            raise ValueError("Este documento ya está vinculado a una factura emitida.")
        if conn.execute(
            "SELECT id FROM document_classifications WHERE document_id=? AND business_id=? AND method='pdf_batch' LIMIT 1",
            (document_id, business_id),
        ).fetchone():
            raise ValueError(
                "Este PDF es un lote. Registra sus facturas individuales, no el original."
            )
        if document["expense_id"] is not None:
            raise ValueError("Este documento ya está vinculado a un gasto.")
    else:
        document_id = None
    row = conn.execute(
        "INSERT INTO received_invoices (business_id, supplier_id, number, concept, issued_on, due_on, base, vat_rate, vat_amount, irpf_amount, total, status, category, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?, ?) RETURNING id",
        (
            business_id,
            supplier_id,
            number,
            concept,
            issued_on,
            due_on,
            base,
            vat_rate,
            vat_amount,
            irpf_amount,
            total,
            category,
            (note or "").strip() or None,
            db._now(),
        ),
    ).fetchone()
    new_id = row["id"]
    if document_id is not None:
        linked = conn.execute(
            "UPDATE documents SET received_invoice_id=?, doc_status='revisado', reviewed_at=? WHERE id=? AND business_id=? AND received_invoice_id IS NULL",
            (new_id, db._now(), document_id, business_id),
        )
        if linked.rowcount != 1:
            raise ValueError("No se pudo vincular el documento a la factura recibida.")
    received = dict(
        conn.execute(
            "SELECT * FROM received_invoices WHERE id=? AND business_id=?", (new_id, business_id)
        ).fetchone()
    )
    received["document_id"] = document_id
    return received


def add_received_invoice(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_add_received_invoice,
        borrowed,
        args,
        kwargs,
        kind="received_invoice",
        identity=None,
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_update_received_invoice(conn, received_id, *, business_id: int, **changes) -> dict:
    """Corrige una factura recibida sin tocar su documento ni cruzar negocios."""
    current = readers.get_received_invoice(conn, received_id, business_id)
    if not current:
        raise ValueError("Factura recibida no encontrada.")
    allowed = {
        "supplier_id",
        "number",
        "concept",
        "issued_on",
        "due_on",
        "base",
        "vat_rate",
        "vat_amount",
        "irpf_amount",
        "total",
        "category",
        "note",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError("Hay campos que no se pueden modificar.")
    values = {key: changes.get(key, current.get(key)) for key in allowed}
    values["total"] = positive_money(values["total"], "El total", legacy=conn.legacy)
    values["vat_rate"] = (
        db._tax_rate(values["vat_rate"], "El IVA", {0, 4, 10, 21})
        if values["vat_rate"] not in (None, "")
        else None
    )
    for key, label in (
        ("base", "La base"),
        ("vat_amount", "La cuota de IVA"),
        ("irpf_amount", "El IRPF"),
    ):
        raw = values[key]
        if raw in (None, ""):
            values[key] = None
        else:
            try:
                values[key] = optional_money(conn, raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{label} no es un importe válido.") from exc
            if values[key] < 0:
                raise ValueError(f"{label} no puede ser negativa.")
    values["issued_on"] = db._optional_date(values["issued_on"], "La fecha de emisión")
    values["due_on"] = db._optional_date(values["due_on"], "El vencimiento")
    values["number"] = str(values["number"] or "").strip()[:50] or None
    values["concept"] = str(values["concept"] or "").strip()[:500] or None
    values["category"] = str(values["category"] or "").strip()[:100] or None
    values["note"] = str(values["note"] or "").strip()[:2000] or None
    supplier_id = values["supplier_id"]
    if supplier_id not in (None, ""):
        supplier = conn.execute(
            "SELECT id FROM suppliers WHERE id=? AND business_id=?", (supplier_id, business_id)
        ).fetchone()
        if not supplier:
            raise ValueError("Proveedor no encontrado.")
    else:
        supplier_id = None
    updated = conn.execute(
        "UPDATE received_invoices SET supplier_id=?, number=?, concept=?, issued_on=?, due_on=?, base=?, vat_rate=?, vat_amount=?, irpf_amount=?, total=?, category=?, note=? WHERE id=? AND business_id=?",
        (
            supplier_id,
            values["number"],
            values["concept"],
            values["issued_on"],
            values["due_on"],
            values["base"],
            values["vat_rate"],
            values["vat_amount"],
            values["irpf_amount"],
            values["total"],
            values["category"],
            values["note"],
            received_id,
            business_id,
        ),
    )
    if updated.rowcount != 1:
        raise ValueError("Factura recibida no encontrada.")
    return readers.get_received_invoice(conn, received_id, business_id)


def update_received_invoice(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_update_received_invoice,
        borrowed,
        args,
        kwargs,
        kind="received_invoice",
        identity="received_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_set_received_invoice_status(conn, received_id, status, *, business_id) -> dict:
    if status not in db.RECEIVED_STATUSES:
        raise ValueError("Estado de factura recibida desconocido.")
    updated = conn.execute(
        "UPDATE received_invoices SET status=? WHERE id=? AND business_id=?",
        (status, received_id, business_id),
    )
    if updated.rowcount != 1:
        raise ValueError("Factura recibida no encontrada.")
    return readers.get_received_invoice(conn, received_id, business_id)


def set_received_invoice_status(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_set_received_invoice_status,
        borrowed,
        args,
        kwargs,
        kind="received_invoice",
        identity="received_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_delete_received_invoice(conn, received_id, business_id) -> None:
    conn.execute(
        "UPDATE documents SET received_invoice_id=NULL WHERE received_invoice_id=? AND business_id=?",
        (received_id, business_id),
    )
    conn.execute(
        "DELETE FROM received_invoices WHERE id=? AND business_id=?", (received_id, business_id)
    )


def delete_received_invoice(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_delete_received_invoice,
        borrowed,
        args,
        kwargs,
        kind="received_invoice",
        identity="received_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_add_expense(
    conn,
    concept,
    amount,
    vat_rate=None,
    category=None,
    spent_on=None,
    document_id=None,
    project_id=None,
    *,
    business_id: int,
) -> dict:
    concept = (concept or "").strip()
    if not concept or len(concept) > 500:
        raise ValueError("El concepto es obligatorio y no puede superar 500 caracteres.")
    amount = positive_money(amount, "El importe", legacy=conn.legacy)
    if vat_rate not in (None, ""):
        vat_rate = db._tax_rate(vat_rate, "El IVA", {0, 4, 10, 21})
    else:
        vat_rate = None
    if spent_on not in (None, ""):
        try:
            spent_on = db.date.fromisoformat(str(spent_on).strip()).isoformat()
        except ValueError as exc:
            raise ValueError("La fecha del gasto no es válida.") from exc
    else:
        spent_on = None
    if document_id not in (None, ""):
        try:
            document_id = int(document_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("El documento no es válido.") from exc
        if document_id <= 0:
            raise ValueError("El documento no es válido.")
    else:
        document_id = None
    if project_id not in (None, ""):
        try:
            project_id = int(project_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("El proyecto no es válido.") from exc
        if not readers.get_project(conn, project_id, business_id):
            raise ValueError("El proyecto no pertenece a este negocio.")
    else:
        project_id = None
    if document_id is not None:
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        document = conn.execute(
            "SELECT id, expense_id, received_invoice_id, invoice_id FROM documents WHERE id=? AND business_id=?"
            + lock,
            (document_id, business_id),
        ).fetchone()
        if not document:
            raise ValueError("Documento no encontrado.")
        if document["expense_id"] is not None:
            raise ValueError("Este documento ya está vinculado a un gasto.")
        if document["received_invoice_id"] is not None or document["invoice_id"] is not None:
            raise ValueError("Este documento ya está vinculado a una factura.")
        if conn.execute(
            "SELECT id FROM document_classifications WHERE document_id=? AND business_id=? AND method='pdf_batch' LIMIT 1",
            (document_id, business_id),
        ).fetchone():
            raise ValueError(
                "Este PDF es un lote. Registra sus facturas individuales, no el original."
            )
    row = conn.execute(
        "INSERT INTO expenses (business_id, concept, amount, vat_rate, category, spent_on, project_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (business_id, concept, amount, vat_rate, category, spent_on, project_id, db._now()),
    ).fetchone()
    new_id = row["id"]
    if document_id is not None:
        linked = conn.execute(
            "UPDATE documents SET expense_id=? WHERE id=? AND business_id=? AND expense_id IS NULL",
            (new_id, document_id, business_id),
        )
        if linked.rowcount != 1:
            raise ValueError("No se pudo vincular el documento al gasto.")
    expense = dict(
        conn.execute(
            "SELECT * FROM expenses WHERE id=? AND business_id=?", (new_id, business_id)
        ).fetchone()
    )
    expense["document_id"] = document_id
    return expense


def add_expense(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_add_expense,
        borrowed,
        args,
        kwargs,
        kind="expense",
        identity=None,
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_delete_expense(conn, expense_id, business_id) -> None:
    conn.execute(
        "UPDATE documents SET expense_id=NULL WHERE expense_id=? AND business_id=?",
        (expense_id, business_id),
    )
    conn.execute("DELETE FROM expenses WHERE id=? AND business_id=?", (expense_id, business_id))


def delete_expense(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_delete_expense,
        borrowed,
        args,
        kwargs,
        kind="expense",
        identity="expense_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )
