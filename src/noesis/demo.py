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
(``DATABASE_URL`` definido) salvo ``force=True``, porque su modo histórico podía
hacer ``reset``. El arranque solo llama a ``seed_showcase``, que reutiliza
``seed_rich(reset=False)``, cuando el founder activa expresamente
`NOESIS_SEED_DEMO`; nunca reinicia la base.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import secrets

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
    for key, name, phone, email, zone, nif, address in [
        ("marta", "Marta García", "+34600111222", "marta.garcia@example.com",
         "Badalona", "11111111H", "Carrer de la Marina 10, 08911 Badalona"),
        ("carlos", "Carlos Ruiz", "+34600333444", "carlos.ruiz@example.com",
         "Barcelona", "22222222J",
         "Carrer d'Aragó 20, 08015 Barcelona"),
        ("laura", "Laura Soler", "+34600555666", "laura.soler@example.com",
         "L'Hospitalet", "33333333P",
         "Carrer de Mallorca 30, 08901 L'Hospitalet"),
        ("comunidad", "Comunidad Aragó 121", "+34934445566",
         "administracion.arago121@example.com", "Barcelona", "H66000111",
         "Carrer d'Aragó 121, 08015 Barcelona"),
        ("bar", "Bar El Rincón", "+34600777888", "bar.rincon@example.com",
         "Barcelona", "44444444A",
         "Carrer de Sants 88, 08014 Barcelona"),
        ("inmo", "Inmobiliaria Vallès", "+34937771122", "valles@example.com",
         "Sabadell", "B66222333",
         "Rambla de Sabadell 45, 08202 Sabadell"),
        ("ana", "Ana Torres", "+34600999000", "ana.torres@example.com",
         "Barcelona", "55555555K",
         "Carrer del Rosselló 200, 08008 Barcelona"),
    ]:
        clients[key] = db.add_client(
            name, phone=phone, email=email, zone=zone, nif=nif,
            address=address, business_id=bid,
        )

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
            from PIL import Image, ImageDraw
            output = BytesIO()
            image = Image.new("RGB", (1000, 1400), "white")
            draw = ImageDraw.Draw(image)
            draw.text((80, 90), "FERRETERIA CENTRAL", fill="black")
            draw.text((80, 150), "Ticket de ejemplo Noesis", fill="black")
            draw.text((80, 230), "Material y consumibles       80,00 EUR", fill="black")
            draw.text((80, 290), "IVA 21%                      16,80 EUR", fill="black")
            draw.text((80, 370), "TOTAL                         96,80 EUR", fill="black")
            draw.text((80, 500), "Documento ficticio para demostracion.", fill="black")
            image.save(output, format="JPEG", quality=88)
            return output.getvalue()
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, "Documento de ejemplo Noesis", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=11)
        safe_name = filename.encode("latin-1", errors="replace").decode("latin-1")
        pdf.cell(0, 9, safe_name, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(8)
        pdf.multi_cell(
            0, 7,
            "Contenido ficticio preparado para recorrer el gestor documental "
            "y la cartera de gestoria sin utilizar datos reales.",
        )
        return bytes(pdf.output())

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

    # -- Histórico para que las gráficas expliquen una evolución real --------
    for offset, client_key, base, expense in [
        (2, "carlos", 980, 410),
        (3, "bar", 1260, 575),
        (4, "comunidad", 2140, 920),
        (5, "inmo", 1680, 710),
    ]:
        emitida(
            client_key, f"Servicios completados hace {offset} meses", base,
            issued_days=-(offset * 30), pay="full",
        )
        db.add_expense(
            f"Material y desplazamientos hace {offset} meses", expense,
            vat_rate=21, category="Materiales",
            spent_on=d(-(offset * 30) + 3), business_id=bid,
        )

    # -- Equipo, proyectos y presupuestos: la feina conecta todo -----------
    pau = db.create_worker(
        bid, "Pau Martínez", phone="+34610777888", color="#2e8b74",
    )
    nuria = db.create_worker(
        bid, "Núria Vidal", phone="+34610999000", color="#b7831f",
    )
    project = db.add_project(
        "Reforma integral del baño 2ºA", 8000,
        client_id=clients["comunidad"]["id"],
        location="Carrer d'Aragó 121, Barcelona", planned_hours=112,
        starts_on=d(-18), ends_on=d(24),
        note="Obra activa con costes, equipo y tareas de ejemplo.",
        business_id=bid,
    )
    db.update_project(project["id"], business_id=bid, progress=46,
                      status="en_curso")
    db.add_project_member(project["id"], pau["id"], 22, "Oficial",
                          business_id=bid)
    db.add_project_member(project["id"], nuria["id"], 18, "Ayudante",
                          business_id=bid)
    db.add_project_entry(
        project["id"], "material", "Sanitarios y grifería", 1, 1640,
        entry_on=d(-12), business_id=bid,
    )
    db.add_project_entry(
        project["id"], "horas", "Demolición y preparación", 31, 22,
        worker_id=pau["id"], entry_on=d(-8), business_id=bid,
    )
    project_job = db.add_job(
        clients["comunidad"]["id"], "Instalación de sanitarios",
        scheduled_for=at(13, 0), zone="Barcelona", project_id=project["id"],
        worker_id=pau["id"], business_id=bid,
    )
    db.add_project_task(
        project["id"], "Confirmar entrega de mampara", business_id=bid,
        kind="checklist", worker_id=nuria["id"], due_on=d(2),
    )
    db.add_project_task(
        project["id"], "Instalar sanitarios y comprobar fugas", business_id=bid,
        worker_id=pau["id"], job_id=project_job["id"], due_on=d(1),
    )
    quote = db.add_quote(
        clients["comunidad"]["id"],
        "Fase final: mampara, pintura y puesta en marcha", 1850,
        vat_rate=10, business_id=bid,
    )
    db.mark_quote_sent(quote["id"], bid)

    return {
        "business_id": bid,
        "email": email,
        "password": password,
        "clients": len(clients),
    }


# ---------------------------------------------------------------------------
#  Escenario comercial conectado (autónomo + cliente + gestoría)
# ---------------------------------------------------------------------------

SHOWCASE_OWNER_EMAIL = "demo.autonomo@bynoesis.com"
SHOWCASE_SECONDARY_EMAIL = "demo.electricidad@bynoesis.com"
SHOWCASE_GESTORIA_EMAIL = "demo.gestoria@bynoesis.com"
SHOWCASE_PASSWORD = "NoesisDemo2026!"
SHOWCASE_PORTAL_CLIENT = "Comunidad Aragó 121"
SHOWCASE_GESTORIA_NAME = "Gestoría Mirall · Demo"


def _seed_secondary_showcase(password_hash: str) -> int:
    existing = db.get_user_by_email(SHOWCASE_SECONDARY_EMAIL)
    if existing:
        business = db.get_business(existing["business_id"])
        if not business or not business.get("is_demo"):
            raise RuntimeError(
                "El correo reservado de la demo secundaria ya está en uso."
            )
        return int(existing["business_id"])
    business, _ = db.create_account(
        "Electricidad Montseny · Demo", SHOWCASE_SECONDARY_EMAIL, password_hash,
        sector="Electricidad y mantenimiento",
    )
    bid = business["id"]
    db.update_fiscal(
        bid, name="Electricidad Montseny SL · Demo", nif="B67555123",
        address="Carrer Major 42, 08460 Santa Maria de Palautordera",
    )
    db.update_business_profile(
        bid, sector="Electricidad y mantenimiento", team_size="2-5",
        province="Barcelona", primary_goal="control",
    )
    db.update_payment_details(
        bid, iban="ES79 2100 0813 6101 2345 6789", bizum="600 00 01 02",
        note="Pago a 15 días desde la fecha de factura.",
    )
    db.update_payment_reminder_settings(bid, enabled=True, days="3,7,15")
    db.set_whatsapp_status(bid, "conectado", "000000102")
    db.finish_onboarding(bid)
    db.update_gestoria_settings(
        bid, name=SHOWCASE_GESTORIA_NAME,
        email=SHOWCASE_GESTORIA_EMAIL, cadence="mensual",
    )
    db.set_subscription(bid, "active", plan="premium")
    db.mark_business_as_demo(bid)
    today = date.today()
    clients = [
        db.add_client(
            "Hotel Can Mar", phone="+34938400011", zone="Montseny",
            email="administracion.hotel@example.com",
            nif="B60333001", address="Carretera del Montseny 18, 08460",
            business_id=bid,
        ),
        db.add_client(
            "Forn Serra", phone="+34938400022", zone="Sant Celoni",
            email="forn.serra@example.com",
            nif="B60333002", address="Carrer Sant Martí 7, 08470",
            business_id=bid,
        ),
        db.add_client(
            "Laia Puig", phone="+34622000113", zone="Cardedeu",
            email="laia.puig@example.com",
            nif="47777111R", address="Carrer Llinars 26, 08440",
            business_id=bid,
        ),
    ]
    worker = db.create_worker(
        bid, "Àlex Riera", phone="+34622000444", color="#2e8b74",
    )
    project = db.add_project(
        "Renovació elèctrica Hotel Can Mar", 12600,
        client_id=clients[0]["id"], location="Montseny", planned_hours=148,
        starts_on=(today - timedelta(days=26)).isoformat(),
        ends_on=(today + timedelta(days=35)).isoformat(), business_id=bid,
    )
    db.update_project(project["id"], business_id=bid, progress=58,
                      status="en_curso")
    db.add_project_member(project["id"], worker["id"], 24, "Electricista",
                          business_id=bid)
    db.add_project_entry(
        project["id"], "material", "Cuadros, protecciones y cableado", 1, 3840,
        entry_on=(today - timedelta(days=18)).isoformat(), business_id=bid,
    )
    db.add_project_task(
        project["id"], "Certificar el cuadro de la planta primera",
        business_id=bid, worker_id=worker["id"],
        due_on=(today + timedelta(days=3)).isoformat(),
    )
    for index, (client, base, days) in enumerate([
        (clients[0], 3200, -52), (clients[1], 680, -24),
        (clients[2], 410, -7),
    ]):
        invoice = db.add_invoice(
            client["id"], f"Servicio eléctrico {index + 1}", base,
            business_id=bid,
        )
        db.issue_invoice(
            invoice["id"], bid,
            _issued_at_override=(today + timedelta(days=days)).isoformat(),
        )
        if index < 2:
            db.mark_invoice_paid(invoice["id"], bid)
    for concept, amount, days in [
        ("Material eléctrico", 1450, -48),
        ("Combustible furgoneta", 92, -19),
        ("Instrumentació i EPIs", 385, -6),
    ]:
        db.add_expense(
            concept, amount, vat_rate=21, category="Materiales",
            spent_on=(today + timedelta(days=days)).isoformat(), business_id=bid,
        )
    db.add_gestoria_request(
        "Falta el justificant del material del quadre elèctric.",
        requested_by="gestoria", business_id=bid,
    )
    return bid


def seed_showcase(*, force: bool = False) -> dict:
    """Crea una demo comercial completa sin borrar ni mezclar datos existentes."""
    if config.DATABASE_URL and not (force and config.SEED_DEMO):
        raise RuntimeError(
            "La demo comercial en producción exige NOESIS_SEED_DEMO=true."
        )
    from .web import auth

    owner = db.get_user_by_email(SHOWCASE_OWNER_EMAIL)
    if owner:
        existing_business = db.get_business(owner["business_id"])
        if not existing_business or not existing_business.get("is_demo"):
            raise RuntimeError(
                "El correo reservado de la demo principal ya está en uso."
            )
        primary_id = int(owner["business_id"])
    else:
        primary_id = int(seed_rich(
            reset=False, force=True, email=SHOWCASE_OWNER_EMAIL,
            password=SHOWCASE_PASSWORD,
        )["business_id"])
    db.set_subscription(primary_id, "active", plan="premium")
    db.update_fiscal(
        primary_id, name="Reformas y Fontanería Delta SL · Demo"
    )
    db.update_business_profile(
        primary_id, sector="Fontanería y reformas", team_size="2-5",
        province="Barcelona", primary_goal="control",
    )
    db.update_payment_reminder_settings(
        primary_id, enabled=True, days="3,7,15"
    )
    db.set_whatsapp_status(primary_id, "conectado", "000000101")
    db.finish_onboarding(primary_id)
    db.update_gestoria_settings(
        primary_id, name=SHOWCASE_GESTORIA_NAME,
        email=SHOWCASE_GESTORIA_EMAIL, cadence="mensual",
    )
    db.mark_business_as_demo(primary_id)

    secondary_id = _seed_secondary_showcase(
        auth.hash_password(SHOWCASE_PASSWORD)
    )
    clients = db.list_clients(primary_id)
    portal_client = next(
        (client for client in clients if client["name"] == SHOWCASE_PORTAL_CLIENT),
        clients[0] if clients else None,
    )
    portal_token = (
        db.get_or_create_portal_token(primary_id, portal_client["id"], ttl_days=3650)
        if portal_client else None
    )

    account = db.get_gestoria_account_by_email(SHOWCASE_GESTORIA_EMAIL)
    if account and account.get("firm_name") != SHOWCASE_GESTORIA_NAME:
        raise RuntimeError(
            "El correo reservado de la demo de gestoría ya está en uso."
        )
    if not account:
        account = db.create_gestoria_account(
            SHOWCASE_GESTORIA_EMAIL, auth.hash_password(SHOWCASE_PASSWORD),
            SHOWCASE_GESTORIA_NAME,
        )
    for business_id in (primary_id, secondary_id):
        if db.gestoria_account_can_access(account["id"], business_id):
            continue
        raw_token = secrets.token_urlsafe(32)
        invitation = db.create_gestoria_invitation(
            business_id, account["email"], auth.hash_token(raw_token),
            (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
        )
        db.accept_gestoria_invitation(invitation["id"], account["id"])

    return {
        "autonomo": {
            "email": SHOWCASE_OWNER_EMAIL, "password": SHOWCASE_PASSWORD,
            "business_id": primary_id,
        },
        "cliente": {
            "name": portal_client["name"] if portal_client else None,
            "path": f"/p/{portal_token}" if portal_token else None,
        },
        "gestoria": {
            "email": SHOWCASE_GESTORIA_EMAIL, "password": SHOWCASE_PASSWORD,
            "businesses": len(db.list_gestoria_businesses(account["id"])),
        },
    }


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # acentos en consola de Windows
    db.init_db()
    info = seed_showcase()
    print("\n  Demo comercial conectada")
    print("  " + "-" * 44)
    print("  Entra en:   /login")
    print(f"  Autónomo:   {info['autonomo']['email']}")
    print(f"  Gestoría:   {info['gestoria']['email']}")
    print(f"  Contraseña: {info['autonomo']['password']}")
    print(f"  Cliente:    {info['cliente']['path']}\n")
