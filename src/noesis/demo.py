"""Datos de demostración para ver Noesis lleno, como en un negocio real.

Dos niveles:

- ``seed()`` — mínimo (clientes, trabajos de hoy, una factura). Lo usa el chat de
  consola (``cli.py``) solo para tener algo con lo que hablar.
- ``seed_rich()`` — un negocio completo y verosímil (un fontanero-reformista con
  meses de actividad): clientes, catálogo con márgenes y stock bajo, proveedores,
  facturas recibidas, facturas emitidas en todos sus estados (borrador, emitida sin
  cobrar, cobro parcial, cobrada, vencida), gastos por categoría, CRM con embudo y
  seguimientos vencidos, solicitudes de gestoría, documentos en revisión y agenda
  de hoy. Sirve para **ver cómo se comporta cada pantalla con datos de verdad** y
  detectar problemas de diseño que con la app vacía no se ven.

  Crea además una cuenta con login real para poder entrar por el navegador.

Ejecutar:  ``python -m noesis.demo``  → siembra y muestra las credenciales.

Seguridad: ``seed_rich`` **se niega a correr sobre la base de producción**
(``DATABASE_URL`` definido) salvo ``force=True``, porque hace ``reset`` y borraría
datos reales. Nunca debe ejecutarse en el arranque del servidor.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from . import config, db


def seed(*, reset: bool = True) -> int:
    """Carga clientes, trabajos de hoy y una factura pendiente de ejemplo."""
    if reset:
        db.reset_db()
    business = db.create_business(
        "Fontanería Demo", "demo@bynoesis.com", "Fontanería"
    )
    business_id = business["id"]
    db.update_fiscal(
        business_id, name="Fontanería Demo", nif="12345678Z",
        address="Calle Principal 1, Barcelona",
    )

    marta = db.add_client(
        "Marta García", phone="+34600111222", zone="Badalona",
        nif="11111111H", address="Calle Marina 10, Badalona",
        business_id=business_id,
    )
    carlos = db.add_client(
        "Carlos Ruiz", phone="+34600333444", zone="Barcelona",
        nif="22222222J", address="Calle Aragón 20, Barcelona",
        business_id=business_id,
    )
    laura = db.add_client(
        "Laura Soler", phone="+34600555666", zone="Barcelona",
        nif="33333333P", address="Calle Mallorca 30, Barcelona",
        business_id=business_id,
    )

    today = date.today()
    at = lambda h, m=0: datetime(today.year, today.month, today.day, h, m).isoformat(timespec="minutes")

    db.add_job(marta["id"], "Cambio de grifo cocina", scheduled_for=at(9, 30),
               zone="Badalona", price_estimate=95, business_id=business_id)
    db.add_job(carlos["id"], "Revisión caldera", scheduled_for=at(12, 0),
               zone="Barcelona", price_estimate=120, business_id=business_id)
    db.add_job(laura["id"], "Presupuesto reforma baño", scheduled_for=at(17, 0),
               zone="Barcelona", business_id=business_id)

    # Una factura ya enviada y sin cobrar (para ver los avisos de cobro).
    inv = db.add_invoice(
        carlos["id"], "Sustitución termo eléctrico", 180,
        business_id=business_id,
    )
    # Se emite con fecha histórica en la misma transición para respetar la
    # inmutabilidad fiscal de la cabecera tanto en SQLite como en PostgreSQL.
    db.issue_invoice(
        inv["id"], business_id, payment_term_days=10,
        _issued_at_override=(today - timedelta(days=12)).isoformat(),
    )

    # Proyectos realistas para revisar la nueva vista de margen sin datos ficticios
    # en producción: solo forman parte de la cuenta demo local.
    worker = db.create_worker(business_id, "Pau Martínez", phone="600777888")
    bathroom = db.add_project(
        "Reforma integral de baño", 8000, client_id=laura["id"],
        location="L'Hospitalet", planned_hours=96,
        starts_on=(today - timedelta(days=8)).isoformat(), business_id=business_id,
    )
    db.update_project(bathroom["id"], business_id=business_id, progress=38,
                      status="en_curso")
    db.add_project_member(bathroom["id"], worker["id"], 22, "Oficial",
                          business_id=business_id)
    db.add_project_entry(bathroom["id"], "material", "Sanitarios y grifería",
                         1, 1450, entry_on=(today - timedelta(days=5)).isoformat(),
                         business_id=business_id)
    db.add_project_entry(bathroom["id"], "horas", "Demolición y preparación",
                         26, 22, worker_id=worker["id"],
                         entry_on=(today - timedelta(days=2)).isoformat(),
                         business_id=business_id)
    boiler = db.add_project(
        "Instalación de caldera", 2400, client_id=carlos["id"],
        location="Barcelona", planned_hours=24, starts_on=today.isoformat(),
        business_id=business_id,
    )
    db.update_project(boiler["id"], business_id=business_id, progress=10,
                      status="planificado")
    return business_id


# ---------------------------------------------------------------------------
#  Demo completo (para revisar la UI con datos reales)
# ---------------------------------------------------------------------------

DEMO_EMAIL = "demo@noesis.app"
DEMO_PASSWORD = "demo1234"


def seed_rich(*, reset: bool = True, force: bool = False,
              email: str = DEMO_EMAIL, password: str = DEMO_PASSWORD) -> dict:
    """Siembra un negocio completo y verosímil. Devuelve credenciales y conteos."""
    if config.DATABASE_URL and not force:
        raise RuntimeError(
            "seed_rich() hace reset y borraría la base. DATABASE_URL está definido "
            "(producción). Ejecútalo solo en local, o pasa force=True a conciencia.")

    from .web.auth import hash_password

    if reset:
        db.reset_db()

    business, _user = db.create_account(
        "Reformas y Fontanería Delta", email, hash_password(password),
        sector="Fontanería y reformas")
    bid = business["id"]
    db.update_fiscal(bid, name="Reformas y Fontanería Delta SL",
                     nif="B66123456", address="Carrer de Sardenya 210, Barcelona")
    db.update_payment_details(bid, iban="ES91 2100 0418 4502 0005 1332",
                              bizum="600 12 34 56",
                              note="Pago a 15 días desde la fecha de factura.")
    try:
        db.update_language(bid, "es")
    except Exception:  # noqa: BLE001 — el idioma no es crítico para el demo
        pass

    today = date.today()
    d = lambda n: (today + timedelta(days=n)).isoformat()
    at = lambda h, m=0: datetime(today.year, today.month, today.day, h, m
                                 ).isoformat(timespec="minutes")

    # -- Clientes (con domicilio: hace falta para emitir factura) ---------
    clients = {}
    for key, name, phone, zone, nif, address in [
        ("marta", "Marta García", "+34600111222", "Badalona", "11111111H",
         "Carrer de la Marina 10, 08911 Badalona"),
        ("carlos", "Carlos Ruiz", "+34600333444", "Barcelona", "22222222J",
         "Carrer d'Aragó 20, 08015 Barcelona"),
        ("laura", "Laura Soler", "+34600555666", "L'Hospitalet", "33333333P",
         "Carrer de Mallorca 30, 08901 L'Hospitalet"),
        ("comunidad", "Comunidad Aragó 121", "+34934445566", "Barcelona", "H66000111",
         "Carrer d'Aragó 121, 08015 Barcelona"),
        ("bar", "Bar El Rincón", "+34600777888", "Barcelona", "44444444A",
         "Carrer de Sants 88, 08014 Barcelona"),
        ("inmo", "Inmobiliaria Vallès", "+34937771122", "Sabadell", "B66222333",
         "Rambla de Sabadell 45, 08202 Sabadell"),
        ("ana", "Ana Torres", "+34600999000", "Barcelona", "55555555K",
         "Carrer del Rosselló 200, 08008 Barcelona"),
    ]:
        clients[key] = db.add_client(name, phone=phone, zone=zone, nif=nif,
                                     address=address, business_id=bid)

    # -- Catálogo (con márgenes reales y dos productos en stock bajo) ------
    for name, kind, price, cost, vat, stock, alert in [
        ("Hora de mano de obra", "servicio", 45, 22, 21, None, None),
        ("Desplazamiento / hora de camino", "servicio", 25, 12, 21, None, None),
        ("Reforma de baño completa", "servicio", 4500, 3100, 10, None, None),
        ("Instalación de caldera estanca", "servicio", 1200, 780, 21, None, None),
        ("Termo eléctrico 50L", "producto", 320, 210, 21, 3, 2),
        ("Grifo monomando cocina", "producto", 60, 28, 21, 8, 4),
        ("Válvula antirretorno 1\"", "producto", 15, 6, 21, 1, 3),
        ("Tubo de cobre (metro)", "producto", 8, 3.5, 21, 40, 10),
    ]:
        db.add_product(name, kind=kind, price=price, cost=cost, vat_rate=vat,
                       stock=stock, stock_alert=alert, business_id=bid)

    # -- Proveedores + facturas recibidas ---------------------------------
    suppliers = {}
    for key, name, nif in [
        ("hidra", "Suministros Hidra SL", "B08111222"),
        ("roca", "Almacén Roca Distribución", "B08333444"),
        ("ferre", "Ferretería Central", "B08555666"),
    ]:
        suppliers[key] = db.add_supplier(name, nif=nif, business_id=bid)

    def recibida(sup, total, base, concept, issued, due, paid=False, cat="materiales"):
        vat = round(base * 0.21, 2)
        ri = db.add_received_invoice(
            total, supplier_id=suppliers[sup]["id"], concept=concept,
            issued_on=issued, due_on=due, base=base, vat_rate=21,
            vat_amount=vat, category=cat, business_id=bid)
        if paid:
            with db.get_conn() as conn:
                conn.execute("UPDATE received_invoices SET status='pagada' "
                             "WHERE id=? AND business_id=?", (ri["id"], bid))
        return ri

    recibida("hidra", 605, 500, "Material de fontanería (pedido #4021)",
             d(-28), d(-13), paid=True)
    recibida("roca", 1391.5, 1150, "Caldera estanca + accesorios",
             d(-20), d(-5), paid=True)
    recibida("hidra", 302.5, 250, "Tubería de cobre y valvulería",
             d(-9), d(6), paid=False)
    recibida("ferre", 96.8, 80, "Herramienta y consumibles", d(-4), d(11),
             paid=False)
    recibida("roca", 484, 400, "Sanitarios para reforma Aragó", d(-2), d(28),
             paid=False)

    # -- Facturas emitidas en todos sus estados ---------------------------
    def emitida(client, concept, base, *, vat=21, irpf=0, issued_days=None,
                pay=None, overdue=False):
        inv = db.add_invoice(clients[client]["id"], concept, base, vat_rate=vat,
                             irpf_rate=irpf, business_id=bid)
        if issued_days is None:
            return inv  # se queda en borrador
        issued_on = d(issued_days)
        db.issue_invoice(
            inv["id"], bid, _issued_at_override=issued_on,
        )
        if pay == "full":
            db.mark_invoice_paid(inv["id"], bid)
        elif isinstance(pay, (int, float)):
            db.add_invoice_payment(inv["id"], pay, business_id=bid,
                                   method="Transferencia", paid_at=d(issued_days + 5),
                                   note="Anticipo del cliente")
        return inv

    emitida("carlos", "Sustitución de termo eléctrico 50L", 180,
            issued_days=-30, pay="full")
    emitida("bar", "Reparación de fuga y cambio de sifón", 240,
            issued_days=-18, overdue=True)          # emitida, sin cobrar, vencida
    emitida("comunidad", "Reforma de baño 2ºA (fase 1)", 4500, vat=10,
            issued_days=-12, pay=2000)              # cobro parcial
    emitida("inmo", "Revisión de instalación piso Sabadell", 320, irpf=15,
            issued_days=-6)                          # emitida reciente, sin cobrar
    emitida("marta", "Instalación de grifo monomando", 105, issued_days=-2)
    emitida("laura", "Presupuesto reforma baño (borrador)", 3900)  # borrador

    # -- Gastos por categoría ---------------------------------------------
    for concept, amount, vat, cat, days in [
        ("Gasolina furgoneta", 78.4, 21, "Combustible", -3),
        ("Gasolina furgoneta", 65.2, 21, "Combustible", -17),
        ("Cuota de autónomos", 294, 0, "Seguridad Social", -6),
        ("Seguro de responsabilidad civil", 132, 21, "Seguros", -10),
        ("Teléfono y datos móvil", 35, 21, "Suministros", -8),
        ("Renting furgoneta", 289, 21, "Vehículo", -6),
        ("Comida en obra", 14.5, 10, "Dietas", -1),
        ("Material de oficina", 22.9, 21, "Oficina", -22),
    ]:
        db.add_expense(concept, amount, vat_rate=vat, category=cat,
                       spent_on=d(days), business_id=bid)

    # -- CRM: embudo con seguimientos vencidos y de hoy -------------------
    def lead(name, source, value, status, next_days=None, note=None):
        ld = db.add_lead(name, source=source, value_estimate=value,
                         next_action_on=d(next_days) if next_days is not None else None,
                         note=note, business_id=bid)
        if status != "nuevo":
            db.update_lead(ld["id"], business_id=bid, status=status)
        return ld

    lead("Jordi — caldera nueva", "WhatsApp", 1200, "presupuesto_enviado",
         next_days=0, note="Pide presupuesto de caldera de condensación.")
    lead("Comunidad Nàpols 88", "Boca a boca", 6500, "seguimiento",
         next_days=-2, note="Reforma portal + bajantes. Seguir: llamar al presidente.")
    lead("Farmàcia Guinardó", "Web", 800, "interesado", next_days=1,
         note="Fuga en trastienda; quiere visita.")
    lead("Marc — reforma cocina", "Instagram", 2200, "contactado", next_days=3)
    lead("Restaurante Nou", "Llamada", 450, "nuevo", next_days=0,
         note="Atasco recurrente en cocina.")
    won = lead("Ana Torres — baño", "Boca a boca", 3800, "presupuesto_enviado")
    db.convert_lead_to_client(won["id"], business_id=bid)
    lead("Oficinas Meridiana", "Web", 1500, "perdido",
         note="Eligieron a otro por precio.")

    # -- Solicitudes de gestoría ------------------------------------------
    r1 = db.add_gestoria_request(
        "Falta la factura de compra de la caldera (proveedor Roca) para cuadrar el "
        "IVA del trimestre. ¿La puedes subir?", requested_by="gestoria",
        business_id=bid)
    db.add_gestoria_request(
        "Recuérdame el kilometraje de la furgoneta de junio para el modelo 130.",
        requested_by="gestoria", business_id=bid)
    db.reply_gestoria_request(
        r1["id"], "Subida en Documentos, es la de 1.391,50 €.", business_id=bid)
    # Una respondida y otra abierta → se ve el estado mixto.
    db.add_gestoria_request(
        "¿Puedo desgravar la comida en obra?", requested_by="autonomo",
        business_id=bid)

    # -- Documentos en revisión -------------------------------------------
    from .documents import repo as docrepo
    from .documents import service as docservice

    def demo_bytes(filename: str) -> bytes:
        if filename.lower().endswith((".jpg", ".jpeg")):
            from io import BytesIO
            from PIL import Image
            output = BytesIO()
            Image.new("RGB", (2, 2), (244, 241, 232)).save(output, format="JPEG")
            return output.getvalue()
        return b"%PDF-1.4 demo\n%%EOF"

    def doc(filename, status, confidence=None, note=None):
        dd = docservice.upload(bid, filename, demo_bytes(filename),
                               run_ocr=False)
        docrepo.set_review(dd["id"], bid, doc_status=status,
                           confidence=confidence, review_note=note)
        return dd

    doc("factura-hidra-4021.pdf", "validado", confidence=96)
    doc("caldera-roca.pdf", "enviado_gestoria", confidence=91)
    doc("ticket-ferreteria.jpg", "pendiente_revisar", confidence=54,
        note="La IA no está segura del total; revisar a mano.")
    doc("albaran-sin-importe.pdf", "pendiente_revisar",
        note="Sin importe legible.")
    doc("contrato-alquiler-local.pdf", "revisado")

    # -- Agenda de hoy -----------------------------------------------------
    db.add_job(clients["marta"]["id"], "Cambio de grifo cocina",
               scheduled_for=at(9, 30), zone="Badalona", price_estimate=95,
               business_id=bid)
    db.add_job(clients["bar"]["id"], "Revisión de fuga en almacén",
               scheduled_for=at(11, 30), zone="Barcelona", price_estimate=140,
               business_id=bid)
    db.add_job(clients["comunidad"]["id"], "Reforma baño 2ºA (jornada)",
               scheduled_for=at(13, 0), zone="Barcelona", business_id=bid)
    db.add_job(clients["laura"]["id"], "Visita presupuesto reforma",
               scheduled_for=at(17, 30), zone="L'Hospitalet", business_id=bid)

    return {
        "business_id": bid,
        "email": email,
        "password": password,
        "clients": len(clients),
    }


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # acentos en consola de Windows
    db.init_db()
    info = seed_rich()
    print("\n  Demo cargado en Reformas y Fontanería Delta")
    print("  " + "-" * 44)
    print("  Entra en:   /login")
    print(f"  Email:      {info['email']}")
    print(f"  Contraseña: {info['password']}")
    print(f"  Negocio #{info['business_id']} - {info['clients']} clientes\n")
