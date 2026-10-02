"""Núcleo de mutación prestado; el propietario exterior confirma o revierte."""

from .. import db

from . import readers

from .boundary import run


def _mutate_add_invoice(
    conn,
    client_id,
    concept,
    base,
    vat_rate=db.config.DEFAULT_VAT_RATE,
    irpf_rate=0,
    *,
    business_id: int,
    lines=None,
    invoice_type: str = "F1",
    series_id: int | None = None,
    operation_date: str | None = None,
    notes: str | None = None,
    payment_method: str | None = None,
    legal_mention: str | None = None,
    gross_total=None,
) -> dict:
    """Crea una factura calculando IVA y retención de IRPF.

    Total = base + IVA − IRPF retenido (así sale el importe que el cliente paga).
    """
    if not readers.get_client(conn, client_id, business_id):
        raise ValueError("El cliente no pertenece a este negocio.")
    invoice_type = (invoice_type or "F1").strip().upper()
    if invoice_type not in {"F1", "F2"}:
        raise ValueError("Solo se pueden crear facturas completas o simplificadas.")
    normalized = db._normalize_invoice_lines(
        lines, fallback_concept=concept, fallback_base=base, fallback_vat=vat_rate, _exact=True
    )
    totals = db._invoice_totals(normalized, irpf_rate, _exact=True)
    if gross_total is not None:
        gross = db.Decimal(str(gross_total)).quantize(db.Decimal("0.01"), rounding=db.ROUND_HALF_UP)
        if len(normalized) != 1 or not gross.is_finite() or gross <= 0:
            raise ValueError("El precio final requiere una única línea positiva.")
        difference = gross - db.Decimal(str(totals["total"]))
        if abs(difference) > db.Decimal("0.01"):
            raise ValueError("El precio final no coincide con el desglose calculado.")
        if difference and normalized[0]["vat_rate"] == 0:
            raise ValueError("Revisa el redondeo del precio final sin IVA antes de guardar.")
        normalized[0]["vat_amount"] = db.Decimal(
            str(db.Decimal(str(normalized[0]["vat_amount"])) + difference)
        )
        normalized[0]["total"] = db.Decimal(
            str(db.Decimal(str(normalized[0]["total"])) + difference)
        )
        totals = db._invoice_totals(normalized, irpf_rate, _exact=True)
    concept = normalized[0]["description"]
    if len(normalized) > 1:
        concept = f"{concept} y {len(normalized) - 1} línea(s) más"
    if operation_date:
        try:
            operation_date = db.date.fromisoformat(str(operation_date)).isoformat()
        except ValueError as exc:
            raise ValueError("La fecha de operación no es válida.") from exc
    notes = (notes or "").strip() or None
    payment_method = (payment_method or "").strip() or None
    legal_mention = (legal_mention or "").strip() or None
    for value, label, maximum in (
        (notes, "Las notas", 2000),
        (payment_method, "La forma de pago", 120),
        (legal_mention, "La mención legal", 500),
    ):
        if value and len(value) > maximum:
            raise ValueError(f"{label} supera {maximum} caracteres.")
    document_type = db._series_document_type(invoice_type)
    if series_id is None:
        series = db._ensure_default_invoice_series(conn, business_id, document_type)
        series_id = series["id"]
    else:
        series = conn.execute(
            "SELECT * FROM invoice_series WHERE id=? AND business_id=? AND active=TRUE",
            (series_id, business_id),
        ).fetchone()
        if not series or series["document_type"] != document_type:
            raise ValueError("La serie no corresponde al tipo de factura.")
    row = conn.execute(
        "INSERT INTO invoices (business_id, client_id, concept, base, vat_rate, vat_amount, irpf_rate, irpf_amount, total, status, invoice_type, series_id, operation_date, notes, payment_method, legal_mention, currency, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?, ?, ?, ?, ?, ?, 'EUR', ?) RETURNING id",
        (
            business_id,
            client_id,
            concept,
            totals["base"],
            totals["vat_rate"],
            totals["vat_amount"],
            totals["irpf_rate"],
            totals["irpf_amount"],
            totals["total"],
            invoice_type,
            series_id,
            operation_date,
            notes,
            payment_method,
            legal_mention,
            db._now(),
        ),
    ).fetchone()
    new_id = row["id"]
    created_at = db._now()
    for line in normalized:
        conn.execute(
            "INSERT INTO invoice_lines (business_id, invoice_id, position, description, kind, quantity, unit_price, discount_rate, vat_rate, base, vat_amount, total, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                business_id,
                new_id,
                line["position"],
                line["description"],
                line["kind"],
                line["quantity"],
                line["unit_price"],
                line["discount_rate"],
                line["vat_rate"],
                line["base"],
                line["vat_amount"],
                line["total"],
                created_at,
            ),
        )
    return readers.get_invoice(conn, new_id, business_id)


def add_invoice(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_add_invoice,
        borrowed,
        args,
        kwargs,
        kind="invoice",
        identity=None,
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_create_rectifying_invoice(
    conn,
    original_invoice_id: int,
    business_id: int,
    *,
    concept: str,
    base,
    vat_rate=db.config.DEFAULT_VAT_RATE,
    irpf_rate=0,
    invoice_type: str = "R1",
    rectification_type: str = "I",
    reason: str,
    lines=None,
    series_id: int | None = None,
) -> dict:
    """Crea una rectificativa por diferencias; el original nunca se modifica."""
    original = readers.get_invoice(conn, original_invoice_id, business_id)
    if not original or original.get("status") not in {"enviada", "parcial", "cobrada"}:
        raise ValueError("Solo se puede rectificar una factura ya emitida.")
    if readers.get_invoice_cancellation_record(conn, original_invoice_id, business_id):
        raise ValueError("El registro fiscal de esta factura está anulado; no puede rectificarse.")
    invoice_type = (invoice_type or "").strip().upper()
    if invoice_type not in {"R1", "R2", "R3", "R4", "R5"}:
        raise ValueError("El tipo de factura rectificativa no es válido.")
    if invoice_type == "R5" and original.get("invoice_type") != "F2":
        raise ValueError("R5 solo puede rectificar una factura simplificada F2.")
    if invoice_type != "R5" and original.get("invoice_type") == "F2":
        raise ValueError("Una factura simplificada F2 debe rectificarse como R5.")
    rectification_type = (rectification_type or "").strip().upper()
    if rectification_type != "I":
        raise ValueError(
            "Bynoesis solo prepara rectificativas por diferencias. La rectificación por sustitución requiere revisión fiscal."
        )
    concept = (concept or "").strip()
    reason = (reason or "").strip()
    if not concept or len(concept) > 500:
        raise ValueError("El concepto es obligatorio y no puede superar 500 caracteres.")
    if len(reason) < 3 or len(reason) > 1000:
        raise ValueError("El motivo de rectificación es obligatorio.")
    normalized = db._normalize_invoice_lines(
        lines,
        fallback_concept=concept,
        fallback_base=base,
        fallback_vat=vat_rate,
        allow_negative=True,
        _exact=True,
    )
    totals = db._invoice_totals(normalized, irpf_rate, _exact=True)
    if totals["base"] == 0:
        raise ValueError("La base rectificada debe ser distinta de cero.")
    concept = normalized[0]["description"]
    if len(normalized) > 1:
        concept = f"{concept} y {len(normalized) - 1} línea(s) más"
    lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
    current_original = conn.execute(
        "SELECT * FROM invoices WHERE id=? AND business_id=?" + lock,
        (original_invoice_id, business_id),
    ).fetchone()
    if not current_original or current_original["status"] not in {"enviada", "parcial", "cobrada"}:
        raise ValueError("Solo se puede rectificar una factura ya emitida.")
    cancelled = conn.execute(
        "SELECT 1 FROM invoice_cancellation_records WHERE invoice_id=? AND business_id=? LIMIT 1",
        (original_invoice_id, business_id),
    ).fetchone()
    if cancelled:
        raise ValueError("El registro fiscal de esta factura está anulado; no puede rectificarse.")
    pending = conn.execute(
        "SELECT id FROM invoices WHERE business_id=? AND rectifies_invoice_id=? AND status='borrador' LIMIT 1",
        (business_id, original_invoice_id),
    ).fetchone()
    if pending:
        raise ValueError(
            "Ya existe una rectificativa en borrador para esta factura. Revísala antes de crear otra."
        )
    original = dict(current_original)
    if invoice_type == "R5" and original.get("invoice_type") != "F2":
        raise ValueError("R5 solo puede rectificar una factura simplificada F2.")
    if invoice_type != "R5" and original.get("invoice_type") == "F2":
        raise ValueError("Una factura simplificada F2 debe rectificarse como R5.")
    if series_id is None:
        series = db._ensure_default_invoice_series(conn, business_id, "rectifying")
        series_id = series["id"]
    else:
        series = conn.execute(
            "SELECT * FROM invoice_series WHERE id=? AND business_id=? AND document_type='rectifying' AND active=TRUE",
            (series_id, business_id),
        ).fetchone()
        if not series:
            raise ValueError("La serie rectificativa no es válida.")
    row = conn.execute(
        "INSERT INTO invoices (business_id, client_id, concept, base, vat_rate, vat_amount, irpf_rate, irpf_amount, total, status, invoice_type, rectifies_invoice_id, rectification_type, rectification_reason, series_id, currency, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?, ?, ?, ?, ?, 'EUR', ?) RETURNING id",
        (
            business_id,
            original["client_id"],
            concept,
            totals["base"],
            totals["vat_rate"],
            totals["vat_amount"],
            totals["irpf_rate"],
            totals["irpf_amount"],
            totals["total"],
            invoice_type,
            original_invoice_id,
            rectification_type,
            reason,
            series_id,
            db._now(),
        ),
    ).fetchone()
    new_id = row["id"]
    created_at = db._now()
    for line in normalized:
        conn.execute(
            "INSERT INTO invoice_lines (business_id, invoice_id, position, description, kind, quantity, unit_price, discount_rate, vat_rate, base, vat_amount, total, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                business_id,
                new_id,
                line["position"],
                line["description"],
                line["kind"],
                line["quantity"],
                line["unit_price"],
                line["discount_rate"],
                line["vat_rate"],
                line["base"],
                line["vat_amount"],
                line["total"],
                created_at,
            ),
        )
    return readers.get_invoice(conn, new_id, business_id)


def create_rectifying_invoice(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_create_rectifying_invoice,
        borrowed,
        args,
        kwargs,
        kind="invoice",
        identity=None,
        target_kind="invoice",
        target_identity="original_invoice_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_issue_invoice(
    conn,
    invoice_id: int,
    business_id: int,
    payment_term_days: int | None = None,
    *,
    _issued_at_override: str | None = None,
) -> dict:
    """Emite una factura una sola vez, numera y congela sus datos fiscales.

    ``_issued_at_override`` existe únicamente para construir cuentas demo con
    historia coherente. No se expone en las rutas de producto.
    """
    pendientes = db.invoice_pending_fields(readers.get_invoice(conn, invoice_id, business_id))
    if pendientes:
        raise ValueError(
            "Esta factura está a medias y no se puede emitir todavía. Falta: "
            + ", ".join(pendientes)
            + "."
        )
    lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
    inv = conn.execute(
        "SELECT * FROM invoices WHERE id=? AND business_id=?" + lock, (invoice_id, business_id)
    ).fetchone()
    if not inv:
        raise ValueError("No existe esa factura.")
    if inv.get("source") == "importada":
        raise ValueError(
            "Una factura importada es histórica: no se puede emitir ni entrar en la cadena Veri*Factu."
        )
    if inv["status"] != "borrador" or inv["number"]:
        existing = readers.get_invoice(conn, invoice_id, business_id)
        if existing and existing["status"] in {"enviada", "parcial", "cobrada"}:
            return existing
        raise ValueError("La factura no se puede emitir desde su estado actual.")
    biz = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    client = conn.execute(
        "SELECT * FROM clients WHERE id=? AND business_id=?", (inv["client_id"], business_id)
    ).fetchone()
    if not biz or not client:
        raise ValueError("Faltan el negocio o el cliente de la factura.")
    invoice_type = (inv.get("invoice_type") or "F1").upper()
    missing = []
    required = [
        (biz["name"], "nombre fiscal del negocio"),
        (biz["nif"], "NIF del negocio"),
        (biz["address"], "domicilio del negocio"),
        (client["name"], "nombre del cliente"),
    ]
    if invoice_type != "F2":
        required.extend(
            ((client["nif"], "NIF del cliente"), (client["address"], "domicilio del cliente"))
        )
    for value, label in required:
        if not (value or "").strip():
            missing.append(label)
    if missing:
        aviso = "Antes de emitir completa: " + ", ".join(missing) + "."
        solo_falta_el_cliente = missing and all(
            (label in {"NIF del cliente", "domicilio del cliente"} for label in missing)
        )
        if solo_falta_el_cliente and db._fits_simplified_invoice(inv["total"]):
            aviso += " Si es un particular, puedes emitirla como factura simplificada: hasta 400 € no necesita NIF ni domicilio del cliente."
        elif solo_falta_el_cliente:
            aviso += " Es una factura completa: también requiere esos datos si el cliente es un particular. El límite general del ticket sin identificación del destinatario es 400 € IVA incluido; las excepciones sectoriales no se aplican automáticamente."
        raise ValueError(aviso)
    lines = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM invoice_lines WHERE business_id=? AND invoice_id=? ORDER BY position, id",
            (business_id, invoice_id),
        ).fetchall()
    ]
    if not lines:
        raise ValueError("La factura no contiene ninguna línea.")
    from ..conversation_plan import expected_invoice, invoice_fingerprint

    expectation = expected_invoice.get()
    if expectation and expectation[:2] == (business_id, invoice_id) and expectation[2]:
        if invoice_fingerprint(inv, lines) != expectation[2]:
            raise ValueError("La factura cambió desde la confirmación. Revísala antes de emitir.")
    totals = db._invoice_totals(lines, inv.get("irpf_rate") or 0, _exact=True)
    for key in ("base", "vat_amount", "irpf_amount", "total"):
        if db.Decimal(str(totals[key])).quantize(db.Decimal("0.01")) != db.Decimal(
            str(inv[key])
        ).quantize(db.Decimal("0.01")):
            raise ValueError(
                "Los totales del borrador no coinciden con sus líneas; revísalo antes de emitir."
            )
    if invoice_type == "F2" and (not db._fits_simplified_invoice(inv["total"])):
        raise ValueError(
            "La factura simplificada supera el límite general de 400 €. Emítela como factura completa con los datos fiscales del cliente."
        )
    expected_document_type = db._series_document_type(invoice_type)
    series = conn.execute(
        "SELECT * FROM invoice_series WHERE id=? AND business_id=? AND active=TRUE",
        (inv.get("series_id"), business_id),
    ).fetchone()
    if not series:
        series = db._ensure_default_invoice_series(conn, business_id, expected_document_type)
        conn.execute(
            "UPDATE invoices SET series_id=? WHERE id=? AND business_id=?",
            (series["id"], invoice_id, business_id),
        )
    if series["document_type"] != expected_document_type:
        raise ValueError("La serie no corresponde al tipo de factura.")
    number = db._next_invoice_series_number(conn, business_id, series["id"])
    if _issued_at_override:
        try:
            issued_day = db.date.fromisoformat(str(_issued_at_override)[:10])
        except ValueError as exc:
            raise ValueError("La fecha de emisión demo no es válida.") from exc
        if issued_day > db.date.today():
            raise ValueError("La fecha de emisión demo no puede ser futura.")
        issued_at = f"{issued_day.isoformat()}T12:00:00"
    else:
        issued_at = db._now()
        issued_day = db.date.today()
    if inv.get("operation_date"):
        try:
            operation_day = db.date.fromisoformat(inv["operation_date"])
        except ValueError as exc:
            raise ValueError("La fecha de operación del borrador no es válida.") from exc
        if operation_day > db.date.today():
            raise ValueError("La fecha de operación no puede estar en el futuro.")
    if payment_term_days is None:
        configured_term = biz.get("default_payment_term_days")
        payment_term_days = int(15 if configured_term is None else configured_term)
    due_date = (issued_day + db.timedelta(days=max(0, min(payment_term_days, 365)))).isoformat()
    document_profile = db._ensure_current_document_profile(conn, dict(biz))
    conn.execute(
        "UPDATE invoices SET status='enviada', number=?, issued_at=?, due_date=?, issuer_name=?, issuer_nif=?, issuer_address=?, recipient_name=?, recipient_nif=?, recipient_address=?, document_profile_id=? WHERE id=? AND business_id=? AND status='borrador'",
        (
            number,
            issued_at,
            due_date,
            biz["name"],
            biz["nif"],
            biz["address"],
            client["name"],
            client.get("nif"),
            client.get("address"),
            document_profile["id"],
            invoice_id,
            business_id,
        ),
    )
    if biz.get("verifactu_enabled"):
        errors = db.verifactu_configuration_errors()
        if errors:
            raise ValueError(
                "No se puede emitir en modo Veri*Factu; configura: " + ", ".join(errors) + "."
            )
        db._create_invoice_record(conn, business_id, invoice_id)
    else:
        db._record_invoice_event(
            conn,
            business_id,
            "emision",
            invoice_id=invoice_id,
            details=f"numero={number}",
            created_at=issued_at,
        )
    saved = readers.get_invoice(conn, invoice_id, business_id)
    conn.observations.append(
        (
            "observe_useful_action",
            (business_id, "invoice_issued"),
            {
                "entity_type": "invoice",
                "entity_id": invoice_id,
                "completed_at": issued_at,
                "metadata": {"invoice_type": invoice_type},
            },
        )
    )
    conn.observations.append(
        (
            "observe_job_invoiced_from_invoice",
            (business_id,),
            {"invoice_id": invoice_id, "occurred_at": issued_at},
        )
    )
    return saved


def issue_invoice(borrowed, *args, legacy=False, expected_revision=None, **kwargs):
    return run(
        _mutate_issue_invoice,
        borrowed,
        args,
        kwargs,
        kind="invoice",
        identity="invoice_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )


def _mutate_create_invoice_cancellation_record(
    conn, invoice_id: int, business_id: int, *, reason: str
) -> dict:
    """Anula ante la AEAT un alta aceptada sin borrar ni alterar la factura."""
    conn.execute(
        "SELECT id FROM invoices WHERE business_id=? AND id=?"
        + (" FOR UPDATE" if conn.dialect == "postgres" else ""),
        (business_id, invoice_id),
    ).fetchone()
    reason = (reason or "").strip()
    if not 5 <= len(reason) <= 1000:
        raise ValueError("Explica el motivo de la anulación (5 a 1.000 caracteres).")
    existing = conn.execute(
        "SELECT * FROM invoice_cancellation_records WHERE invoice_id=? AND business_id=?",
        (invoice_id, business_id),
    ).fetchone()
    if existing:
        return dict(existing)
    invoice = conn.execute(
        "SELECT * FROM invoices WHERE id=? AND business_id=?", (invoice_id, business_id)
    ).fetchone()
    original = conn.execute(
        "SELECT * FROM invoice_records WHERE invoice_id=? AND business_id=?",
        (invoice_id, business_id),
    ).fetchone()
    outbox = conn.execute(
        "SELECT * FROM verifactu_outbox WHERE invoice_id=? AND business_id=?",
        (invoice_id, business_id),
    ).fetchone()
    if not invoice or not original:
        raise ValueError("Solo se puede anular un registro Veri*Factu ya generado.")
    if not outbox or outbox["status"] not in {"aceptado", "aceptado_con_errores"}:
        raise ValueError("La anulación requiere que el alta haya sido aceptada por la AEAT.")
    issuer_nif = original["issuer_nif"]
    from ..core.locks import lock_fiscal_chain

    lock_fiscal_chain(conn, business_id, issuer_nif)
    chain = db._fiscal_record_rows(conn, business_id, issuer_nif)
    integrity = db._verify_invoice_record_rows(chain)
    if not integrity["valid"]:
        raise ValueError("La cadena Veri*Factu presenta una anomalía; no se ha anulado.")
    previous = chain[-1] if chain else None
    generated_at = db.verifactu.generated_at_with_timezone()
    if previous:
        previous_time = db.datetime.fromisoformat(previous["generated_at"])
        current_time = db.datetime.fromisoformat(generated_at)
        if current_time < previous_time - db.timedelta(minutes=1):
            raise ValueError("El reloj del sistema retrocede respecto al último registro.")
        if current_time <= previous_time:
            generated_at = (previous_time + db.timedelta(milliseconds=1)).isoformat(
                timespec="milliseconds"
            )
    previous_hash = previous["record_hash"] if previous else None
    record_hash = db.verifactu.cancellation_record_hash(
        issuer_nif=issuer_nif,
        invoice_number=original["invoice_number"],
        issue_date=original["issue_date"],
        previous_hash=previous_hash,
        generated_at=generated_at,
    )
    row = conn.execute(
        "INSERT INTO invoice_cancellation_records (business_id, invoice_id, original_record_id, record_type, record_version, issuer_nif, issuer_name, invoice_number, issue_date, reason, generated_at, previous_record_type, previous_record_id, previous_issuer_nif, previous_invoice_number, previous_issue_date, previous_hash, hash_algorithm, hash_type, hash_spec_version, record_hash, producer_name, producer_nif, system_name, system_id, system_version, installation_id, created_at) VALUES (?, ?, ?, 'anulacion', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (
            business_id,
            invoice_id,
            original["id"],
            db.config.VERIFACTU_RECORD_VERSION,
            issuer_nif,
            original["issuer_name"],
            original["invoice_number"],
            original["issue_date"],
            reason,
            generated_at,
            previous.get("record_type") if previous else None,
            previous["id"] if previous else None,
            previous["issuer_nif"] if previous else None,
            previous["invoice_number"] if previous else None,
            previous["issue_date"] if previous else None,
            previous_hash,
            db.config.VERIFACTU_HASH_ALGORITHM,
            db.config.VERIFACTU_HASH_TYPE,
            db.config.VERIFACTU_HASH_SPEC_VERSION,
            record_hash,
            db.config.VERIFACTU_PRODUCER_NAME.strip(),
            db.config.VERIFACTU_PRODUCER_NIF.strip().upper(),
            db.config.VERIFACTU_SYSTEM_NAME,
            db.config.VERIFACTU_SYSTEM_ID,
            db.config.VERIFACTU_SYSTEM_VERSION,
            f"{db.config.VERIFACTU_INSTALLATION_PREFIX}-{business_id}",
            generated_at,
        ),
    ).fetchone()
    record_id = row["id"]
    queued_at = db._now()
    conn.execute(
        "INSERT INTO verifactu_cancellation_outbox (business_id, invoice_id, record_id, status, attempts, max_attempts, next_attempt_at, created_at, updated_at) VALUES (?, ?, ?, 'pendiente', 0, ?, ?, ?, ?)",
        (
            business_id,
            invoice_id,
            record_id,
            db.config.VERIFACTU_MAX_ATTEMPTS,
            queued_at,
            queued_at,
            queued_at,
        ),
    )
    db._record_invoice_event(
        conn,
        business_id,
        "anulacion",
        invoice_id=invoice_id,
        details=f"motivo={reason};huella={record_hash}",
        created_at=generated_at,
    )
    created = conn.execute(
        "SELECT * FROM invoice_cancellation_records WHERE id=? AND business_id=?",
        (record_id, business_id),
    ).fetchone()
    return dict(created)


def create_invoice_cancellation_record(
    borrowed, *args, legacy=False, expected_revision=None, **kwargs
):
    return run(
        _mutate_create_invoice_cancellation_record,
        borrowed,
        args,
        kwargs,
        kind="cancellation_record",
        identity=None,
        target_kind="invoice",
        target_identity="invoice_id",
        legacy=legacy,
        expected_revision=expected_revision,
    )
