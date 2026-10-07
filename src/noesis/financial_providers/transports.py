"""Consumo de clientes existentes. Ningún cliente ni endpoint nuevo de entrega."""

from noesis import db
from .contracts import Provider


def deliver(binding):
    """Sólo tras guard F: las respuestas libres nunca se copian al contrato F."""
    table, bid = binding["outbox_type"], binding["business_id"]
    with db.get_conn() as c:
        row = c.execute("SELECT * FROM " + table + " WHERE business_id=? AND id=?", (bid, binding["outbox_id"])).fetchone()
    if binding["provider"] == Provider.AEAT:
        from noesis import verifactu_client
        business = db.get_business(bid)
        with db.get_conn() as c:
            record_table = 'invoice_records' if table == 'verifactu_outbox' else 'invoice_cancellation_records'
            record = dict(c.execute('SELECT * FROM '+record_table+' WHERE business_id=? AND invoice_id=? AND id=?',(bid,row['invoice_id'],row['record_id'])).fetchone())
        integrity = db.verify_invoice_record_chain(bid, issuer_nif=record["issuer_nif"])
        if not integrity["valid"]:
            from noesis.financial_operations.contracts import StateError
            raise StateError('CONTINUITY_MISMATCH')
        result = verifactu_client.submit_records(business, [record])
        # El parser Veri*Factu valida el registro duplicado concreto; no inventar
        # exactly-once ni convertir cualquier respuesta duplicada en aceptación.
        category = {"aceptado": "success", "aceptado_con_errores": "accepted_with_errors", "rechazado": "rejected"}.get(result.status, "timeout")
        return dict(category=category, reference=result.csv, status_code=None)
    if binding["provider"] == Provider.META:
        from noesis.web.whatsapp import _post_to_meta, _meta_payload, MetaRejected
        connection = db.get_whatsapp_connection(row["connection_id"], bid) if row["connection_id"] else None
        try:
            reference = _post_to_meta(_meta_payload(row), connection["phone_number_id"] if connection else None)
        except MetaRejected:
            return dict(category="rejected", reference=None, status_code=None)
        return dict(category="success", reference=reference, status_code=None)
    from noesis.adapters import email, google_mail
    attachments = []
    if row["entity_type"] == "invoice":
        from noesis.web.invoice_pdf import build_invoice_pdf
        invoice = db.get_invoice(row["entity_id"], bid)
        attachments = [("factura_" + str(invoice["number"]).replace("/", "-") + ".pdf", build_invoice_pdf(row["entity_id"], bid), "application", "pdf")]
    if row["entity_type"] in google_mail.TIPOS_PROPIOS and google_mail.disponible(bid):
        success = google_mail.enviar(bid, row["to_email"], row["subject"], row["text_body"], adjuntos=attachments)
    else:
        success = email.send_email(row["to_email"], row["subject"], row["text_body"], row["html_body"], attachments=attachments)
    # Los adapters bool absorben excepciones: False no prueba rechazo terminal.
    return dict(category="success" if success else "timeout", reference=None, status_code=None)
