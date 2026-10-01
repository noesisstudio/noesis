"""Conversación real por WhatsApp probada de punta a punta (2026-09-30).

Cada caso sale de hablar con el bot como lo haría un autónomo: saludar, pedir
ayuda, equivocarse al teclear, contestar «sí» o «gracias» sin nada pendiente y
seguir las sugerencias que el propio bot da.
"""
import unittest
from datetime import date
from unittest.mock import patch

from noesis import config, db, nlu
from noesis.web import chat, whatsapp
from tests import test_backend as fixtures

TELEFONO = "34600111222"


class CharlaWhatsappTestCase(unittest.TestCase):
    setUp = fixtures.BackendTestCase.setUp
    tearDown = fixtures.BackendTestCase.tearDown
    make_business = fixtures.BackendTestCase.make_business

    def charla(self, business, *textos):
        db.set_whatsapp_status(business["id"], "conectado", phone=TELEFONO)
        respuestas = []
        with patch.object(whatsapp, "send",
                          side_effect=lambda phone, text, **kw:
                          respuestas.append(text) or True), \
             patch.object(whatsapp, "_attach_new_invoice_pdf"):
            for texto in textos:
                # Cada mensaje con su id: WhatsApp descarta los repetidos.
                self._enviados = getattr(self, "_enviados", 0) + 1
                whatsapp.handle_inbound({"id": f"wamid.charla.{self._enviados}",
                                         "from": TELEFONO, "text": texto})
        return respuestas

    # --- Entender

    def test_saludo_con_pregunta_es_ayuda_pero_no_tapa_una_orden(self):
        for texto in ("hola, ¿qué puedes hacer?", "Buenas tardes. ¿En qué me puedes ayudar?",
                      "hola ¿cómo funcionas?", "ayuda"):
            self.assertEqual(nlu.parse(texto), (nlu.HELP, {}), texto)
            self.assertTrue(nlu.pide_capacidades(texto), texto)
        self.assertFalse(nlu.pide_capacidades("hola"))
        self.assertEqual(nlu.parse("hola, factura a juan por 100")[0], "crear_factura")

    def test_pedir_ayuda_da_la_lista_y_saludar_da_la_lectura(self):
        business, _ = self.make_business("Ayuda real")
        ayuda, saludo = self.charla(business, "hola, ¿qué puedes hacer?", "hola")
        self.assertIn("«¿Quién me debe?»", ayuda)
        self.assertIn("Así veo", saludo)

    def test_erratas_de_movil_no_pierden_la_orden(self):
        self.assertEqual(nlu.parse("fatura a ana por arreglo 80 euros")[0], "crear_factura")
        self.assertEqual(nlu.parse("Facutra a juan por pintar 200")[0], "crear_factura")
        self.assertEqual(nlu.parse("presupesto a juan por baño 1000 euros")[0],
                         "crear_presupuesto")

    def test_faltas_y_abreviaturas_de_movil_del_founder(self):
        """Ronda real 30-sep por WhatsApp: todo esto acababa en la IA o sin datos."""
        casos = {
            "hazme una factra a lucia de 200e por reparacion grifo":
                ("crear_factura", "lucia", "reparacion grifo", 200.0),
            "factura a lucia por pintura 200e": ("crear_factura", "lucia", "pintura", 200.0),
            "fatcura a juan por pintura 90 euros": ("crear_factura", "juan", "pintura", 90.0),
            "presupueto a juan por baño 900 euros":
                ("crear_presupuesto", "juan", "baño", 900.0),
        }
        for texto, (tool, cliente, concepto, base) in casos.items():
            with self.subTest(texto=texto):
                orden, datos = nlu.parse(texto)
                self.assertEqual((orden, datos["cliente"], datos["concepto"], datos["base"]),
                                 (tool, cliente, concepto, base))
        self.assertEqual(nlu.parse("q tengo manana")[0], "ver_agenda")
        self.assertTrue(nlu.pide_capacidades("hola k tal, q puedes acer"))
        self.assertEqual(nlu.parse("hola, ¿qué tal?"), (nlu.HELP, {}))
        agenda = nlu.parse("agenda a lucia el viernes a las 5 de la tarde pa mirar la caldera")
        self.assertEqual(agenda[1]["descripcion"], "mirar la caldera")
        # Las formas válidas y las palabras parecidas que son otra cosa no se tocan.
        for texto in ("facturame a juan 100 euros", "la fractura del azulejo",
                      "tengo 3 clientes nuevos"):
            self.assertEqual(nlu.corregir_erratas(texto), texto)

    def test_hora_de_la_agenda_sin_segundos(self):
        # En producción (Postgres) la hora llega con segundos: «10:00:00».
        texto = nlu.format_reply("ver_agenda", {"fecha": "2026-10-01", "trabajos": [{
            "scheduled_for": "2026-10-01T10:00:00", "client_name": "Ana",
            "description": "caldera"}]})
        self.assertIn("• 10:00 Ana", texto)
        self.assertNotIn("10:00:00", texto)

    def test_otra_factura_no_completa_el_borrador_a_medias(self):
        """Caso real 30-sep: el #67 (pintura, sin importe) se llevó los 200 € de
        una factura nueva por «reparacion grifo»."""
        business, _ = self.make_business("Otra factura")
        db.add_client("María Antonia", business_id=business["id"])
        self.charla(business, "factura a Maria Antonia por pintura",
                    "hazme una factra a Maria Antonia de 200e por reparacion grifo")
        facturas = {i["concept"]: i["total"] for i in db.list_invoices(business["id"])}
        self.assertEqual(facturas, {"pintura": 0.0, "reparacion grifo": 242.0})

    def test_varias_ordenes_en_un_mensaje_no_se_pierden(self):
        """Caso real: los dos gastos se perdían sin avisar."""
        business, client = self.make_business("Varias órdenes")
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            (respuesta,) = self.charla(
                business, "hoy he gastado 30 en material y 15 de parking, y hazle una "
                f"factura a {client['name']} de 100 por revision")
        self.assertIn("solo he preparado una", respuesta)
        self.assertIn("«hoy he gastado 30 en material y 15 de parking»", respuesta)
        self.assertEqual(nlu.ordenes_extra("factura a Juan por reforma de baño y cocina 800 euros"), [])
        self.assertEqual(nlu.ordenes_extra("quién me debe y qué tengo hoy"), [])

    def test_lo_que_no_se_hace_por_whatsapp_dice_donde_hacerlo(self):
        self.assertIn("**Facturas**", nlu.parse("borra la factura 67")[1]["reply"])
        self.assertIn("**Facturas**",
                      nlu.parse("cambia el importe de la factura 67 a 100 euros")[1]["reply"])
        business, fiscal = self.make_business("Sin proyectos")
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            proyecto, cliente, _, ticket = self.charla(
                business, "crea un proyecto reforma cocina con presupuesto de 8000 euros",
                "crea el cliente Pedro Prueba con telefono 600 11 22 33", "no",
                f"ticket de venta a {fiscal['name']} por desplazamiento 36,30 euros")
        self.assertIn(f"/b/{business['id']}/proyectos", proyecto)
        self.assertIn("Teléfono: 600112233", cliente)
        self.assertTrue(ticket.startswith("Preparar ticket de venta borrador"), ticket)

    def test_la_gestoria_se_pregunta_en_cualquier_orden(self):
        self.assertEqual(nlu.parse("¿Qué me pide la gestoría?")[0], "ver_solicitudes_gestoria")

    def test_las_sugerencias_del_parte_se_entienden(self):
        # «ver orden» o «ver facturas» no llevaban a ninguna parte. «Por facturar»
        # lo resuelve chat antes del parser.
        for tema, frase in chat._ATAJOS_DEL_PLAN.items():
            with self.subTest(tema=tema):
                if "por facturar" in nlu._norm(frase):
                    continue
                self.assertTrue((nlu.parse(frase) or ("",))[0].startswith("ver_"), frase)

    def test_datos_etiquetados_del_founder_30_sep(self):
        """Mensajes reales: todo etiquetado, con erratas, y un borrador sin nada."""
        self.assertEqual(
            nlu.parse("Hazme una factura de 350€ + iva concepto: reformad habitación "
                      "a clinte: Maria Antionia"),
            ("crear_factura", {"base": 350.0, "concepto": "reformad habitación",
                               "cliente": "Maria Antionia", "tipo_factura": "F1"}))
        tool, args = nlu.parse("Hazme una factura de 350€ + iva concepto: reformas "
                               "el cliente es: Maria Antionia")
        self.assertEqual((tool, args["cliente"], args["concepto"]),
                         ("crear_factura", "Maria Antionia", "reformas"))
        self.assertEqual(
            nlu.parse("Factura a cliente Maria Antonia por 350 + iva concepto: reformas"),
            ("crear_factura", {"cliente": "Maria Antonia", "concepto": "reformas",
                               "base": 350.0, "tipo_factura": "F1"}))
        # Una pregunta, no una factura: desde el 30-sep se contesta con la ficha.
        self.assertEqual(nlu.parse("¿qué facturas tiene el cliente Juan?"),
                         ("ver_cliente", {"cliente": "Juan", "dato": "facturas"}))
        self.assertEqual(
            nlu.parse("factura a Juan por cambio de grifo 95 euros")[1]["cliente"], "Juan")

    def test_borrador_a_medias_se_completa_con_frases_naturales(self):
        business, _ = self.make_business("Completar borrador")
        _, cliente, concepto = self.charla(
            business, "hazme una factura de 200 euros",
            "Maria antonia es el cliente", "concepto: pintura del pasillo")
        self.assertIn("falta *el concepto*", whatsapp.whatsapp_markup(cliente))
        # Sin ficha no se crea el cliente solo (decisión 2026-09-23: la voz
        # duplicaría clientes); el borrador guarda el nombre y lo pide.
        self.assertIn("crea el cliente Maria antonia", concepto)
        (factura,) = db.list_invoices(business["id"])
        self.assertEqual(factura["concept"], "pintura del pasillo")
        self.assertIn("Maria antonia", concepto)

    def test_con_borrador_abierto_la_orden_etiquetada_lo_completa(self):
        """Caso real: con el #62 a medias, la nueva orden completa los datos."""
        business, _ = self.make_business("Borrador abierto")
        maria = db.add_client("Maria Antonia", business_id=business["id"])
        _, respuesta = self.charla(
            business, "hazme una factura de 350 euros",
            "Factura a cliente Maria Antonia por 350 + iva concepto: reformas")
        (factura,) = db.list_invoices(business["id"])
        self.assertEqual((factura["client_id"], factura["concept"]),
                         (maria["id"], "reformas"))
        self.assertIn("completo", respuesta)

    def test_cliente_con_tilde_y_palabra_cliente_con_revision_como_en_produccion(self):
        """Caso real 30-sep, 10:37: «factura a cliente reformas martinez…»."""
        business, _ = self.make_business("Tildes")
        ficha = db.add_client("reformas martínez", business_id=business["id"])
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            for texto in ("factura a cliente reformas martinez por 800 euros + iva "
                          "concepto parque",
                          "factura a cliente reformas martínez por 800 euros + iva "
                          "concepto parque",
                          "factura a REFORMAS MARTINES por parque 800 euros"):
                with self.subTest(texto=texto):
                    tarjeta, hecho = self.charla(business, texto, "sí")
                    self.assertIn(f"reformas martínez · ficha #{ficha['id']}", tarjeta)
                    self.assertIn("IVA 21 %", tarjeta)
                    self.assertNotIn("No tengo ficha", tarjeta)
                    self.assertIn("preparada para reformas martínez (parque)", hecho)
        # Ninguna ficha duplicada de la misma empresa.
        self.assertEqual(
            [c["id"] for c in db.list_clients(business["id"])
             if "reformas" in nlu._norm(c["name"])], [ficha["id"]])

    def test_repetir_la_orden_entera_completa_el_borrador(self):
        """Caso real 30-sep, 11:04: con el #62 a medias, la orden con «a María»."""
        business, _ = self.make_business("Orden repetida")
        maria = db.add_client("María Antonia", business_id=business["id"])
        for revision in (False, True):
            with self.subTest(revision=revision), \
                    patch.object(config, "ASSISTANT_REVIEW_ENABLED", revision):
                _, respuesta = self.charla(
                    business, "hazme una factura de 350 euros",
                    "Factura a Maria Antonia por 350 + iva concepto reformas")
                self.assertIn("completo para *María Antonia*",
                              whatsapp.whatsapp_markup(respuesta))
        for factura in db.list_invoices(business["id"]):
            self.assertEqual((factura["client_id"], factura["concept"], factura["total"]),
                             (maria["id"], "reformas", 423.5))

    # --- Clientes por WhatsApp (ronda real 30-sep, tarde)

    def test_crear_cliente_como_se_dice(self):
        """«crea un cliente nuevo que se llama Laura…» guardaba «nuevo que se llama Laura»."""
        casos = {
            "crea un cliente nuevo que se llama Laura Gimeno, su telefono es 612 345 678":
                {"nombre": "Laura Gimeno", "telefono": "612345678"},
            "añade a Laura Gimeno como cliente": {"nombre": "Laura Gimeno"},
            "agrega el cliente Laura Gimeno": {"nombre": "Laura Gimeno"},
            "guarda a Laura Gimeno en clientes": {"nombre": "Laura Gimeno"},
            "tengo un cliente nuevo que se llama Laura Gimeno": {"nombre": "Laura Gimeno"},
            "Laura Gimeno es un cliente nuevo": {"nombre": "Laura Gimeno"},
            "registra un cliente con nombre Laura Gimeno": {"nombre": "Laura Gimeno"},
            "apunta un cliente nuevo, Laura Gimeno": {"nombre": "Laura Gimeno"},
            "dame de alta al cliente Pedro Ruiz": {"nombre": "Pedro Ruiz"},
            "crea un nou client que es diu Laura Gimeno": {"nombre": "Laura Gimeno"},
            "crea cliente Laura Gimeno email laura@gmail.com":
                {"nombre": "Laura Gimeno", "email": "laura@gmail.com"},
            "crea el cliente Laura Gimeno con NIF 12345678Z y direccion Calle Mayor 3, Valencia":
                {"nombre": "Laura Gimeno", "nif": "12345678Z",
                 "direccion": "Calle Mayor 3, Valencia"},
            "crea el cliente Fontaneria Lopez SL con cif B12345674":
                {"nombre": "Fontaneria Lopez SL", "nif": "B12345674"},
            "crea el cliente Reformas Martínez, S.L.": {"nombre": "Reformas Martínez, S.L."},
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(nlu.parse(texto), ("crear_cliente", esperado))
        self.assertEqual(nlu.parse("crea cliente 600123456")[0], nlu.NEED_PARTY_NAME)

    def test_alta_con_datos_fiscales_los_guarda_y_avisa_del_nif_malo(self):
        business, _ = self.make_business("Alta completa")
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            tarjeta, hecho = self.charla(
                business, "crea el cliente Laura Gimeno con NIF 12345678Z, telefono "
                "612345678 y direccion Calle Mayor 3, Valencia", "sí")
            self.assertIn("NIF: 12345678Z", tarjeta)
            self.assertNotIn("faltará", hecho)
            malo, guardado = self.charla(business, "crea el cliente Pepe Ruiz nif 12345678A", "sí")
        self.assertIn("no es válido", malo)
        self.assertIn("no lo he guardado", guardado)
        laura = db.resolve_client_reference("Laura Gimeno", business["id"])
        self.assertEqual((laura["nif"], laura["phone"], laura["address"]),
                         ("12345678Z", "612345678", "Calle Mayor 3, Valencia"))
        self.assertFalse(db.resolve_client_reference("Pepe Ruiz", business["id"])["nif"])

    def test_completar_y_corregir_la_ficha_hablando(self):
        """«el NIF de Laura es…» soltaba el parte del día."""
        business, _ = self.make_business("Completar ficha")
        db.add_client("Laura Gimeno", phone="612345678", business_id=business["id"])
        self.assertEqual(nlu.parse("cambia el importe de la factura 67 a 100 euros")[0],
                         nlu.NEED_REVIEW)
        self.assertNotEqual((nlu.parse("el numero de la factura 3 es 12") or ("",))[0],
                            "actualizar_cliente")
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            nif, _, tel, _, correo, _, nadie = self.charla(
                business, "el nif de Laura Gimeno es 12345678Z", "sí",
                "cambia el telefono de Laura Gimeno a 699 88 77 66", "sí",
                "añade el correo laura@gimeno.es a Laura Gimeno", "sí",
                "el nif de Pepito es 12345678Z")
        self.assertIn("Actualizar datos del cliente", nif)
        self.assertIn("612345678 → 699887766", tel)
        self.assertIn("Correo: laura@gimeno.es", correo)
        self.assertIn("No tengo ficha de cliente «Pepito»", nadie)
        laura = db.resolve_client_reference("Laura Gimeno", business["id"])
        self.assertEqual((laura["nif"], laura["phone"], laura["email"]),
                         ("12345678Z", "699887766", "laura@gimeno.es"))

    # --- Notas de voz como las escribe Whisper (ronda 30-sep, tarde)

    def voz(self, business, *textos):
        db.set_whatsapp_status(business["id"], "conectado", phone=TELEFONO)
        respuestas = []
        for texto in textos:
            self._enviados = getattr(self, "_enviados", 0) + 1
            with patch.object(whatsapp, "_audio_to_text", return_value=(texto, None)), \
                 patch.object(whatsapp, "send", side_effect=lambda phone, text, **kw:
                              respuestas.append(text) or True), \
                 patch.object(whatsapp, "_attach_new_invoice_pdf"):
                whatsapp.handle_inbound({"id": f"wamid.voz.{self._enviados}",
                                         "from": TELEFONO, "audio_id": "a1"})
        return respuestas

    def test_dictado_a_trozos_y_con_muletillas(self):
        casos = {
            "Factura a Juan García, 120 euros, cambio de grifo.":
                ("crear_factura", "Juan García", "cambio de grifo", 120.0),
            "Factura a Juan García, cambio de grifo, 120 euros.":
                ("crear_factura", "Juan García", "cambio de grifo", 120.0),
            "Hazme una factura para Reformas Martínez. Concepto ventanas. Importe 750 euros.":
                ("crear_factura", "Reformas Martínez", "ventanas", 750.0),
            "Factura a Reformas Martínez, S.L., 300 euros, pintura":
                ("crear_factura", "Reformas Martínez, S.L.", "pintura", 300.0),
            "Factura a Juan, 2 grifos, 120 euros": ("crear_factura", "Juan", "2 grifos", 120.0),
            "Hazme un presupuesto para Ana, reforma del baño, mil doscientos euros.":
                ("crear_presupuesto", "Ana", "reforma del baño", 1200.0),
        }
        for texto, (tool, cliente, concepto, base) in casos.items():
            with self.subTest(texto=texto):
                orden, datos = nlu.parse(nlu.corregir_erratas(texto))
                self.assertEqual((orden, datos["cliente"], datos["concepto"], datos["base"]),
                                 (tool, cliente, concepto, base))
        orden, datos = nlu.parse(nlu.corregir_erratas(
            "Oye, apúntame un gasto de 42,50 en material de fontanería."))
        self.assertEqual((orden, datos["importe"]), ("registrar_gasto", 42.5))
        self.assertEqual(nlu.parse(nlu.corregir_erratas(
            "Mañana a las diez tengo que ir a casa de Juan García a mirar la caldera."))[1]
            ["descripcion"], "mirar la caldera")
        for si in ("Sí, confírmalo.", "confírmalo", "perfecto, sí", "sí, está bien", "venga sí"):
            self.assertTrue(nlu.es_confirmacion(si), si)
        for no_es_si in ("sí, pero 200", "si, cambia el cliente"):
            self.assertFalse(nlu.es_confirmacion(no_es_si), no_es_si)

    def test_una_muletilla_no_crea_la_ficha_que_se_quedo_esperando(self):
        """Caso de la ronda de voz: «Eh... Vale, gracias.» creó el cliente «Eh» y
        un presupuesto de 1.452 € que se había pedido tres órdenes antes."""
        business, _ = self.make_business("Muletilla")
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            pregunta, gracias = self.voz(
                business, "Hazme un presupuesto para Ana de mil doscientos euros por "
                "reformar el baño.", "Eh... Vale, gracias.")
            self.assertIn("No tengo ficha de **Ana**", pregunta)
            self.assertTrue(gracias.startswith("De nada"))
            # Otra orden en medio invalida la pregunta: un «sí» después no crea nada.
            self.voz(business, "Hazme un presupuesto para Ana de 1200 euros por baño.",
                     "¿Qué tengo mañana?", "Gasté cuarenta euros en gasolina.", "no", "sí")
        self.assertEqual([c["name"] for c in db.list_clients(business["id"])
                          if c["name"] in {"Eh", "Ana"}], [])
        self.assertEqual(db.list_quotes(business["id"]), [])

    def test_corregir_la_hora_de_una_cita_por_la_tarde(self):
        business, _ = self.make_business("Cita corregida")
        db.add_client("Marta López", business_id=business["id"])
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            tarjeta, seis, lunes, lugar, _ = self.voz(
                business, "Agenda a Marta López el jueves a las cinco de la tarde para "
                "revisar la caldera.", "Mejor a las seis.", "mejor el lunes",
                "en Badalona", "sí")
        self.assertIn("Trabajo: revisar la caldera\n", tarjeta)
        self.assertIn("a las 18:00", seis)
        self.assertIn("lunes", lunes)
        self.assertIn("Lugar: Badalona", lugar)
        (cita,) = db.jobs_between("2026-01-01", "2030-12-31", business["id"])
        self.assertEqual((cita["zone"], cita["scheduled_for"][11:16]), ("Badalona", "18:00"))

    def test_la_ia_no_puede_fingir_una_tarjeta_de_revision(self):
        business, _ = self.make_business("Tarjeta falsa")
        falsa = {"reply": "Agendar trabajo\nCuándo: 11:00\n\nNo he guardado nada. "
                          "Responde SÍ para confirmarlo.", "source": "ia"}
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True), \
                patch.object(chat, "_handle", return_value=falsa):
            (respuesta,) = self.charla(business, "mejor a las 11")
        self.assertIn("no hay ninguna propuesta pendiente", respuesta)

    # --- Faltas, agenda, gastos y cobros

    def test_faltas_sueltas_de_movil(self):
        casos = {
            "hazme una factura a juan x 200 € por pintar": "crear_factura",
            "fra a lucia x 120 €": "crear_factura",
            "cuanto me deven": "ver_cobros_pendientes",
            "e gastado 20 en material": "registrar_gasto",
            "he gastao 15 en parking": "registrar_gasto",
            "agenda a luis el biernes a las 9": "agendar_trabajo",
            "q tengo oy": "ver_agenda",
            "que tengo mñana": "ver_agenda",
            "cuanto iba tengo q pagar": "ver_impuestos",
            "ticket de benta a juan por 30": "crear_factura",
        }
        for texto, tool in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(nlu.parse(nlu.corregir_erratas(texto))[0], tool)
        self.assertEqual(nlu.parse(nlu.corregir_erratas(
            "hazme una factura a juan x 200 € por pintar"))[1]["cliente"], "juan")
        self.assertEqual(nlu.corregir_erratas("iba a llamarte"), "iba a llamarte")
        self.assertEqual(nlu.corregir_erratas("3 x 20 euros"), "3 x 20 euros")
        self.assertEqual(nlu.corregir_erratas("la ola del mar"), "la ola del mar")

    def test_consultas_de_agenda_de_varios_dias_y_fechas_concretas(self):
        from datetime import timedelta
        hoy = date.today()
        domingo = hoy + timedelta(days=6 - hoy.weekday())
        self.assertEqual(nlu.parse("que tengo esta semana"),
                         ("ver_agenda", {"fecha": hoy.isoformat(), "hasta": domingo.isoformat()}))
        self.assertEqual(nlu.parse("mi agenda")[0], "ver_agenda")
        self.assertEqual(nlu.parse("mis citas de hoy"), ("ver_agenda", {"fecha": hoy.isoformat()}))
        self.assertEqual(nlu.parse("que tengo el viernes")[0], "ver_agenda")
        self.assertEqual(nlu.parse("que tengo pendiente de cobrar")[0], "ver_cobros_pendientes")
        self.assertEqual(nlu.parse("agenda para mañana a las 12 a Jordi")[1]["cliente"], "Jordi")
        self.assertEqual(nlu.parse_date("el 15/10", date(2026, 9, 30)), "2026-10-15")
        self.assertEqual(nlu.parse_date("el 3 de enero", date(2026, 9, 30)), "2027-01-03")
        self.assertEqual(nlu.parse_date("el día 5", date(2026, 9, 30)), "2026-10-05")
        self.assertIsNone(nlu.parse_date("el 31 de febrero", date(2026, 9, 30)))
        self.assertEqual(
            nlu.parse("agenda a Marta el 15 de octubre a las 10 para caldera")[1]["descripcion"],
            "caldera")
        self.assertEqual(nlu.parse("agenda a luis mañana a las 10 para la caldera")[1]
                         ["descripcion"], "la caldera")

    def test_gastos_y_deuda_de_un_cliente(self):
        business, client = self.make_business("Consultas")
        factura = db.add_invoice(client["id"], "Pintura", 100, business_id=business["id"])
        db.issue_invoice(factura["id"], business["id"])
        db.add_expense("Gasolina", 45, business_id=business["id"])
        gastos, deuda, nadie, semana = self.charla(
            business, "que gastos he apuntado hoy?", f"cuanto me debe {client['name']}?",
            "cuanto me debe Pepito", "que tengo esta semana")
        self.assertIn("Gasolina: 45,00 €", gastos)
        self.assertIn(f"{client['name']} te debe **121,00 €**", deuda)
        self.assertIn("No tengo ficha de cliente «Pepito»", nadie)
        self.assertIn("No tienes trabajos agendados entre hoy", semana)

    # --- Segunda ronda (30-sep, noche)

    def test_impuestos_dichos_detras_del_importe(self):
        casos = {
            "factura a Juan García por grifo 95 euros al 10% de IVA": {"iva": 10.0},
            "factura a Juan por grifo 95 euros con el 10% de iva": {"iva": 10.0},
            "factura a Juan por reforma 1000 euros con retención del 15%": {"irpf": 15.0},
            "factura a Juan por reforma 1000 euros, IVA reducido": {"iva": 10.0},
            "presupuesto a Ana por baño 2000 euros con el 10 por ciento de iva": {"iva": 10.0},
        }
        for texto, impuestos in casos.items():
            with self.subTest(texto=texto):
                orden, datos = nlu.parse(texto)
                self.assertIn(orden, {"crear_factura", "crear_presupuesto"})
                self.assertNotIn("%", datos["concepto"])
                self.assertNotIn(" por ", f" {datos['cliente']} ")
                for clave, valor in impuestos.items():
                    self.assertEqual(datos[clave], valor)
        self.assertEqual(nlu.parse("factura a Juan por reforma 1000 euros iva del 7")[0],
                         nlu.NEED_REVIEW)

    def test_borrador_a_medias_se_completa_hablando_y_con_irpf(self):
        business, _ = self.make_business("Borrador hablado")
        db.add_client("Juan García", business_id=business["id"])
        _, cliente, concepto, importe = self.charla(
            business, "hazme una factura", "a Juan García", "por cambio de grifo", "95 euros")
        self.assertIn("para **Juan García**", cliente)
        self.assertIn("falta **el importe**", concepto)
        self.assertIn("completo", importe)
        self.charla(business, "hazme una factura",
                    "factura a Juan García por grifo 95 euros con IRPF del 15")
        totales = sorted(f["total"] for f in db.list_invoices(business["id"]))
        self.assertEqual(totales, [100.7, 114.95])

    def test_no_se_cobra_un_borrador_y_el_numero_visible_manda(self):
        business, client = self.make_business("Cobros claros")
        borrador = db.add_invoice(client["id"], "Grifo", 80, business_id=business["id"])
        emitida = db.add_invoice(client["id"], "Pintura", 100, business_id=business["id"])
        emitida = db.issue_invoice(emitida["id"], business["id"])
        self.assertEqual(nlu.parse(f"la factura {emitida['number']} está cobrada"),
                         ("registrar_pago", {"factura_numero": emitida["number"]}))
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            (no_emitida,) = self.charla(business, f"la factura {borrador['id']} está pagada")
            tarjeta, hecho = self.charla(
                business, f"la factura {emitida['number']} está cobrada", "sí")
            (inexistente,) = self.charla(business, "la factura 2026/0999 está cobrada")
        self.assertIn("todavía es un borrador", no_emitida)
        self.assertIn(f"Factura {emitida['number']}", tarjeta)
        self.assertIn("ya consta como cobrada", hecho)
        self.assertIn("No encuentro una única factura", inexistente)

    def test_preguntas_sobre_un_cliente_y_cobros_sin_factura(self):
        business, client = self.make_business("Ficha por WhatsApp")
        db.update_client(client["id"], business_id=business["id"], phone="612345678")
        factura = db.add_invoice(client["id"], "Pintura", 100, business_id=business["id"])
        factura = db.issue_invoice(factura["id"], business["id"])
        telefono, correo, historial, cobro = self.charla(
            business, f"dame el teléfono de {client['name']}",
            f"cuál es el correo de {client['name']}?",
            f"qué facturas tiene {client['name']}?", "me han pagado 121 euros")
        self.assertIn("612345678", telefono)
        self.assertIn("No tengo el correo", correo)
        self.assertIn(factura["number"], historial)
        self.assertIn("¿Qué factura te han pagado?", cobro)
        self.assertIn(f"«la factura {factura['number']} está cobrada»", cobro)
        self.assertEqual(db.get_invoice(factura["id"], business["id"])["status"], "enviada")

    def test_resumen_del_ano_y_del_mes_pasado(self):
        self.assertEqual(nlu.parse("cuánto he facturado este año?"),
                         ("resumen_negocio", {"anio": date.today().year}))
        self.assertEqual(nlu.parse(nlu.corregir_erratas("cuanto facture el mes pasado"))[0],
                         "resumen_negocio")
        self.assertEqual(nlu.parse(nlu.corregir_erratas("facture a juan por pintar 100"))[0],
                         "crear_factura")
        business, client = self.make_business("Resumen anual")
        factura = db.add_invoice(client["id"], "Pintura", 100, business_id=business["id"])
        db.issue_invoice(factura["id"], business["id"])
        (anual,) = self.charla(business, "cuánto he facturado este año?")
        self.assertIn(f"Lectura de {date.today().year}", anual)
        self.assertIn("121,00 €", anual)

    def test_gastos_con_cuando_delante_y_pagos(self):
        casos = {"hoy he gastado 45 euros en gasolina": ("gasolina", 45.0),
                 "ayer compré tornillos por 8,40": ("tornillos", 8.4),
                 "he pagado 60 euros de seguro de la furgoneta": ("seguro de la furgoneta", 60.0),
                 "pagué la gasolina, 55 euros": ("la gasolina", 55.0)}
        for texto, (concepto, importe) in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(nlu.parse(texto),
                                 ("registrar_gasto", {"concepto": concepto, "importe": importe}))
        self.assertNotEqual((nlu.parse("me han pagado 300 euros") or ("",))[0], "registrar_gasto")

    def test_alta_de_un_nombre_contenido_en_otros(self):
        """Caso real: «Prueba Claude» con «Lucia Prueba Claude» y «Pedro Prueba
        Claude» pedía «el nombre completo» y no dejaba darlo de alta."""
        business, _ = self.make_business("Nombres parecidos")
        for nombre in ("Lucia Prueba Claude", "Pedro Prueba Claude"):
            db.add_client(nombre, business_id=business["id"])
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            tarjeta, hecho = self.charla(business, "crea el cliente Prueba Claude", "sí")
        self.assertIn("Guardar cliente", tarjeta)
        self.assertIn("Cliente guardado: **Prueba Claude**", hecho)
        self.assertEqual(db.resolve_client_reference("prueba claude", business["id"])["name"],
                         "Prueba Claude")

    def test_voz_cifras_con_tilde_y_correo_dictado(self):
        self.assertEqual(nlu.parse("He gastado veintitrés con cincuenta en el parking."),
                         ("registrar_gasto", {"concepto": "el parking", "importe": 23.5}))
        self.assertEqual(nlu._cifras_dictadas("gasté doce con treinta euros en pan"),
                         "gasté 12,30 euros en pan")
        self.assertEqual(nlu._cifras_dictadas("veintitrés con cincuenta euros"), "23,50 euros")
        self.assertEqual(
            nlu.parse("Ponle a Juan García el correo juan punto garcia arroba gmail punto com."),
            ("actualizar_cliente", {"cliente": "Juan García", "email": "juan.garcia@gmail.com"}))
        self.assertEqual(nlu.parse("crea el cliente Ana Ruiz con correo ana guion bajo ruiz "
                                   "arroba hotmail punto es")[1]["email"], "ana_ruiz@hotmail.es")
        cita = nlu.parse(nlu.corregir_erratas(
            "Apunta una cita con Marta López pasado mañana a las nueve y media de la mañana "
            "para mirar una fuga."))
        self.assertEqual((cita[1]["descripcion"], cita[1]["fecha_hora"][11:]),
                         ("mirar una fuga", "09:30"))

    def test_no_se_emite_con_un_nif_espanol_invalido(self):
        """Caso real: la ficha «reformas martínez» tenía el NIF «481234129L»."""
        from noesis.fiscal_validation import problema_nif_cliente
        self.assertIsNotNone(problema_nif_cliente("481234129L"))
        self.assertIsNone(problema_nif_cliente("12345678Z"))
        self.assertIsNone(problema_nif_cliente("FR12345678901"))
        business, _ = self.make_business("NIF malo")
        malo = db.add_client("Cliente Malo", nif="481234129L", address="Calle 1",
                             business_id=business["id"])
        borrador = db.add_invoice(malo["id"], "Obra", 100, business_id=business["id"])
        (respuesta,) = self.charla(business, f"emitir factura {borrador['id']}")
        self.assertIn("no es válido", respuesta)
        self.assertIn("«el NIF de Cliente Malo es …»", respuesta)
        self.assertEqual(db.get_invoice(borrador["id"], business["id"])["status"], "borrador")
        (ficha,) = self.charla(business, "ficha de Cliente Malo")
        self.assertIn("no parece un NIF válido", ficha)
        self.assertIn("1 borrador sin emitir", ficha)

    # --- Ronda del 1 de octubre

    def test_mas_formas_de_dar_de_alta_y_faltas(self):
        casos = {
            "añademe un cliente nuebo q se llama Marta Soler Vidal":
                ("crear_cliente", {"nombre": "Marta Soler Vidal"}),
            "quiero añadir un cliente nuevo llamado Pepe Garcia":
                ("crear_cliente", {"nombre": "Pepe Garcia"}),
            "mete a pepe garcia de cliente": ("crear_cliente", {"nombre": "Pepe Garcia"}),
            "cliente nuevo: pepe garcia, 666 777 888, pepe@gmail.com":
                ("crear_cliente", {"nombre": "Pepe Garcia", "telefono": "666777888",
                                   "email": "pepe@gmail.com"}),
            "guardame este cliente: Pepe Garcia 666777888":
                ("crear_cliente", {"nombre": "Pepe Garcia", "telefono": "666777888"}),
            "tengo una clienta nueva, se llama Ana Ruiz":
                ("crear_cliente", {"nombre": "Ana Ruiz"}),
            "hazme un cliente nuevo Pepe Garcia": ("crear_cliente", {"nombre": "Pepe Garcia"}),
            "crea el probeedor Bauhaus": ("crear_proveedor", {"nombre": "Bauhaus"}),
            "añade un provedor nuevo Leroy Merlin": ("crear_proveedor", {"nombre": "Leroy Merlin"}),
            "quiero crear un cliente": (nlu.NEED_PARTY_NAME, {"tipo": "cliente"}),
            "cliente nuevo": (nlu.NEED_PARTY_NAME, {"tipo": "cliente"}),
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(nlu.parse(nlu.corregir_erratas(texto)), esperado)
        # No se da de alta a «un presupuesto».
        self.assertEqual(
            nlu.parse("hazme un presupuesto a cliente Juan por 300 euros baño")[0],
            "crear_presupuesto")

    def test_nombre_en_minusculas_se_guarda_con_mayusculas(self):
        casos = {"pepe garcia": "Pepe Garcia", "reformas martínez, s.l.": "Reformas Martínez, S.L.",
                 "jose maria de la fuente": "Jose Maria de la Fuente",
                 "construcciones ruiz sl": "Construcciones Ruiz SL",
                 "iPhone Reparaciones": "iPhone Reparaciones", "PEPE": "PEPE"}
        for escrito, guardado in casos.items():
            self.assertEqual(nlu.nombre_presentable(escrito), guardado)

    def test_la_segunda_orden_no_es_parte_del_nombre_y_hazle_es_ese_cliente(self):
        business, _ = self.make_business("Orden doble")
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            tarjeta, _, factura, _, cita = self.charla(
                business, "crea al cliente pepe garcia y hazle una factura de 100 euros "
                "por pintar", "sí", "hazle una factura de 100 euros por pintar", "no",
                "agéndale una cita el lunes a las 10 para revisar la caldera")
        self.assertIn("Nombre: Pepe Garcia\n", tarjeta)
        self.assertIn("«hazle una factura de 100 euros por pintar»", tarjeta)
        self.assertIn("Cliente: Pepe Garcia", factura)
        self.assertIn("Cliente: Pepe Garcia", cita)
        orden = nlu.parse("presupuesto para este cliente por baño 900 euros")
        self.assertEqual(orden[1]["cliente"], nlu.CLIENTE_DE_LA_CONVERSACION)

    def test_en_plazo_se_ensena_el_trimestre_que_toca_presentar(self):
        from noesis import tools

        class Octubre(date):
            @classmethod
            def today(cls):
                return cls(2026, 10, 1)

        class Noviembre(date):
            @classmethod
            def today(cls):
                return cls(2026, 11, 5)

        business, _ = self.make_business("Plazo fiscal")
        with patch.object(tools, "date", Octubre):
            en_plazo = tools._ver_impuestos(business["id"])
            pedido = tools._ver_impuestos(business["id"], trimestre=4)
        with patch.object(tools, "date", Noviembre):
            fuera = tools._ver_impuestos(business["id"])
        self.assertTrue(en_plazo["label"].startswith("3T"))
        self.assertIn("20 de octubre", en_plazo["plazo"])
        self.assertTrue(pedido["label"].startswith("4T"))
        self.assertNotIn("plazo", pedido)
        self.assertTrue(fuera["label"].startswith("4T"))
        self.assertNotIn("plazo", fuera)

    def test_ticket_ilegible_se_completa_hablando(self):
        from noesis.documents import review
        item = review.new_item(fields={}, kind=None, business=None, document_id=1,
                               source="ninguno", media="image")
        cambiado, sin_entender = review.apply_correction(item, "son 25 euros de gasolina")
        self.assertEqual(sin_entender, [])
        self.assertIn("total", cambiado)
        self.assertEqual(float(item["fields"]["total"]), 25.0)
        self.assertEqual(review.render(item).count("gasolina"), 1)
        from noesis.web import whatsapp_documents
        self.assertTrue(whatsapp_documents._DESTINO.fullmatch("es de la obra de juan"))
        self.assertFalse(whatsapp_documents._DESTINO.fullmatch("es de leroy merlin"))

    def test_mas_faltas_en_facturas_agenda_y_gastos(self):
        casos = {
            "factura ha juan por pintar 100 euros": ("crear_factura", "juan", "pintar", 100.0),
            "factura a juan por pintar 100 euors": ("crear_factura", "juan", "pintar", 100.0),
            "factura a juan por pintar 100 pavos": ("crear_factura", "juan", "pintar", 100.0),
            "factura juan 100 pintura": ("crear_factura", "juan", "pintura", 100.0),
            "presu a juan por baño 500 euros": ("crear_presupuesto", "juan", "baño", 500.0),
            "presupuesto juan 500 baño": ("crear_presupuesto", "juan", "baño", 500.0),
        }
        for texto, (tool, cliente, concepto, base) in casos.items():
            with self.subTest(texto=texto):
                orden, datos = nlu.parse(nlu.corregir_erratas(texto))
                self.assertEqual((orden, datos["cliente"], datos["concepto"], datos["base"]),
                                 (tool, cliente, concepto, base))
        gastos = {"gasto 20 gasolina": ("gasolina", 20.0), "gasolina 20 euros": ("gasolina", 20.0),
                  "20€ de parking": ("parking", 20.0), "compra de material 45,50": ("material", 45.5)}
        for texto, (concepto, importe) in gastos.items():
            with self.subTest(texto=texto):
                self.assertEqual(nlu.parse(nlu.corregir_erratas(texto)),
                                 ("registrar_gasto", {"concepto": concepto, "importe": importe}))
        self.assertIsNone(nlu.parse("juan 100 euros"))
        cita = nlu.parse(nlu.corregir_erratas("ajenda a juan mañana 10h para revisar caldera"))
        self.assertEqual((cita[0], cita[1]["fecha_hora"][11:]), ("agendar_trabajo", "10:00"))
        self.assertEqual(nlu.parse(nlu.corregir_erratas("resumn del mes"))[0], "resumen_negocio")
        self.assertEqual(nlu.parse(nlu.corregir_erratas("enbia la factura 70 al cliente por correo")),
                         ("entregar_factura", {"factura_id": 70, "canal": "email"}))

    def test_emitir_y_pdf_sin_decir_factura(self):
        business, client = self.make_business("Sin decir factura")
        uno = db.add_invoice(client["id"], "Pintura", 100, business_id=business["id"])
        dos = db.add_invoice(client["id"], "Ventana", 200, business_id=business["id"])
        emitir, _, con_falta, _ = self.charla(
            business, f"emite la {uno['id']}", "no", f"emitir fra {dos['id']}", "no")
        self.assertIn(f"emitir el borrador #{uno['id']}", emitir)
        self.assertIn(f"emitir el borrador #{dos['id']}", con_falta)
        for texto, esperado in ((f"pasame la {uno['id']} en pdf", uno["id"]),
                                (f"el pdf de la {dos['id']}", dos["id"]),
                                (f"pdf de la factura {dos['id']}", dos["id"])):
            with self.subTest(texto=texto):
                self.assertTrue(whatsapp._is_owner_pdf_request(texto))
                factura, _ = whatsapp._invoice_for_owner_pdf(business["id"], texto, TELEFONO)
                self.assertEqual(factura["id"], esperado)
        self.assertFalse(whatsapp._is_owner_pdf_request("factura a juan por 20 euros de pdf"))

    def test_otra_igual_repite_la_ultima_factura(self):
        self.assertEqual(nlu.parse("otra igual pero para Juan García y de 250"),
                         (nlu.REPETIR_FACTURA, {"base": 250.0, "cliente": "Juan García"}))
        self.assertEqual(nlu.parse("hazme otra factura a Juan por 100 pintar")[0], "crear_factura")
        self.assertIsNone(nlu.parse("otra igual que ayer con descuento"))
        business, client = self.make_business("Repetir")
        db.add_client("Juan García", business_id=business["id"])
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            (vacio,) = self.charla(business, "hazme otra igual")
            self.charla(business, f"factura a {client['name']} por mantenimiento mensual "
                        "300 euros con irpf del 15", "sí")
            igual, _, otro, _, importe = self.charla(
                business, "hazme otra igual", "no", "otra igual para Juan García", "no",
                "la misma pero de 400 euros")
        self.assertIn("ninguna factura que repetir", vacio)
        self.assertIn("Concepto: mantenimiento mensual", igual)
        self.assertIn("IRPF 15 %", igual)
        self.assertIn("Total: 318,00 €", igual)
        self.assertIn("Cliente: Juan García", otro)
        self.assertIn("Total: 424,00 €", importe)
        self.assertEqual(len(db.list_invoices(business["id"])), 1)

    def test_entregar_una_factura_ya_emitida_no_dice_que_la_emite(self):
        business, client = self.make_business("Entrega clara")
        db.update_client(client["id"], business_id=business["id"], email="cliente@example.com")
        factura = db.add_invoice(client["id"], "Pintura", 100, business_id=business["id"])
        factura = db.issue_invoice(factura["id"], business["id"])
        (pregunta,) = self.charla(business, f"enviar factura {factura['number']}")
        self.assertIn(f"Voy a entregar la factura {factura['number']}", pregunta)
        self.assertIn("Ya está emitida", pregunta)
        self.assertNotIn("borrador", pregunta)

    def test_gestos_respuestas_alargadas_y_varias_lineas(self):
        casos = {"👍": "vale", "👍🏻": "vale", "👎": "no", "🙏": "gracias", "nooo": "no",
                 "no no no": "no", "okkk": "ok", "valee": "vale", "siii": "sí",
                 "hola\nfactura a Juan por pintar 100\ngracias": "factura a Juan por pintar 100"}
        for escrito, leido in casos.items():
            self.assertEqual(nlu.normalizar_entrada(escrito), leido, escrito)
        for intacto in ("llama", "Lola", "nono", "😂😂", "factura a juan por 100", "vale"):
            self.assertEqual(nlu.normalizar_entrada(intacto), intacto)
        business, client = self.make_business("Gestos")
        borrador = db.add_invoice(client["id"], "Pintura", 100, business_id=business["id"])
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            _, gasto = self.charla(business, "gasté 20 en gasolina", "👍")
            _, descartado = self.charla(business, "gasté 30 en parking", "nooo")
            _, gesto = self.charla(business, f"emitir factura {borrador['id']}", "👍")
            risa, duda, adios = self.charla(business, "no", "😂😂", "?", "adiós")[1:]
        self.assertIn("20,00", gasto)
        self.assertIn("Descartado", descartado)
        self.assertIn("confirmes con palabras", gesto)
        self.assertEqual(db.get_invoice(borrador["id"], business["id"])["status"], "borrador")
        self.assertIn("escríbemelo", risa)
        self.assertIn("Soy Bynoesis", duda)
        self.assertIn("Hasta luego", adios)
        self.assertEqual([g["amount"] for g in db.list_expenses(business["id"])], [20.0])

    def test_un_nombre_no_lleva_simbolos_de_codigo(self):
        """Fuzz del 1-oct: «<script>…» tras «no tengo ficha de Pedro» creó esa ficha
        y su factura."""
        business, _ = self.make_business("Nombres limpios")
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            self.charla(business, "factura a Pedro por grifo 50 euros",
                        "<script>alert(1)</script>")
        self.assertEqual([c["name"] for c in db.list_clients(business["id"])
                          if "script" in c["name"] or c["name"] == "Pedro"], [])
        self.assertEqual(db.list_invoices(business["id"]), [])
        with self.assertRaises(ValueError):
            db.add_client("<b>Juan</b>", business_id=business["id"])
        with self.assertRaises(ValueError):
            db.add_client("600123456", business_id=business["id"])
        self.assertEqual(db.add_client("Reformas & Pinturas O'Brien (Valencia)",
                                       business_id=business["id"])["name"],
                         "Reformas & Pinturas O'Brien (Valencia)")

    def test_pagar_llamar_e_importe_cero(self):
        self.assertIn("No puedo pagar nada", nlu.parse("paga la factura de la luz")[1]["reply"])
        self.assertEqual(nlu.parse("pagué la gasolina, 55 euros")[0], "registrar_gasto")
        business, client = self.make_business("Llamar y cero")
        db.update_client(client["id"], business_id=business["id"], phone="612345678")
        llamar, cero = self.charla(business, f"llama a {client['name']}",
                                   "factura a Desconocido por pintar 0 euros")
        self.assertIn("Yo no hago llamadas", llamar)
        self.assertIn("612345678", llamar)
        self.assertIn("mayor que cero", cero)

    def test_recados_al_cliente_y_envio_por_correo(self):
        """Caso real 1-oct: «mándale un whatsapp a reformas martínez…» decía que en la
        ficha no había correo ni móvil, teniendo los dos."""
        business, _ = self.make_business("Recados")
        db.add_client("Reformas Martínez", phone="611414422", email="rm@example.com",
                      business_id=business["id"])
        db.add_client("Juan García", business_id=business["id"])
        borrador, por_correo, _, sin_contacto, sin_correo, con_canal = self.charla(
            business, "mandale un whatsapp a reformas martinez diciendo que llego 20 minutos tarde",
            "envíaselo por correo", "no", "dile a Juan García que mañana no puedo ir",
            "envialo por correo",
            "avisa a reformas martinez por correo de que mañana empezamos a las 8")
        self.assertIn("https://wa.me/34611414422?text=", borrador)
        self.assertIn("rm@example.com", borrador)
        self.assertNotIn("no hay correo ni móvil", borrador)
        self.assertIn("Responde SÍ para enviarlo", por_correo)
        self.assertIn("Mañana no puedo ir.", sin_contacto)
        self.assertIn("no hay correo ni móvil", sin_contacto)
        self.assertIn("no tiene correo en su ficha", sin_correo)
        self.assertIn("Mañana empezamos a las 8.", con_canal)
        self.assertEqual(db.get_pending_action(business["id"], TELEFONO)["kind"],
                         "send_communication")

    def test_modo_consulta_lee_impuestos_y_rechaza_ordenes_raras(self):
        business, _ = self.make_business("Consulta completa")
        url = "https://example.com/activar"
        iva = chat.handle_read_only(business["id"], "cuanto iva tengo que pagar",
                                    activation_url=url)["reply"]
        emitir = chat.handle_read_only(business["id"], "emite la 1", activation_url=url)["reply"]
        gastos = chat.handle_read_only(business["id"], "mis gastos", activation_url=url)["reply"]
        self.assertIn("IVA", iva)
        self.assertIn("modelo 303", iva)
        self.assertIn("modo consulta", emitir)
        self.assertNotIn("Así veo", emitir)
        self.assertIn("este mes", gastos)

    def test_ticket_de_mostrador_y_ticket_a_un_cliente(self):
        """Con la revisión encendida un ticket sin comprador fallaba pidiendo crear la
        ficha «Cliente de mostrador», y «ticket a Marta…» se apuntaba como gasto."""
        business, _ = self.make_business("Tickets")
        db.add_client("Marta López", business_id=business["id"])
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            mostrador, hecho, a_cliente, _ = self.charla(
                business, "ticket de venta por desplazamiento 36,30 euros", "sí",
                "ticket a Marta López de 50 euros por revisión", "no")
        self.assertIn("venta de mostrador", mostrador)
        self.assertIn("Total: 36,30 €", mostrador)
        self.assertIn("Ticket de venta", hecho)
        self.assertIn("Preparar ticket de venta borrador", a_cliente)
        self.assertIn("Cliente: Marta López", a_cliente)
        self.assertEqual(nlu.parse("ticket de 12 euros de parking")[0], "registrar_gasto")
        (ticket,) = db.list_invoices(business["id"])
        self.assertEqual((ticket["invoice_type"], ticket["total"]), ("F2", 36.3))

    def test_presupuestos_listados_y_pasar_a_factura_se_explica(self):
        business, client = self.make_business("Presupuestos")
        self.assertIn("todavía no lo hago por WhatsApp",
                      nlu.parse("pasa el presupuesto 1 a factura")[1]["reply"])
        vacio, _, lista, del_cliente = self.charla(
            business, "que presupuestos tengo",
            f"presupuesto a {client['name']} por reforma del baño 3500 euros",
            "mis presupuestos", f"presupuestos de {client['name']}")
        self.assertIn("No tienes presupuestos", vacio)
        self.assertIn("reforma del baño · 4.235,00 € · sin enviar", lista)
        self.assertIn(f"de {client['name']}", del_cliente)

    def test_terminar_y_facturar_un_trabajo_de_la_agenda(self):
        business, _ = self.make_business("Trabajos")
        marta = db.add_client("Marta López", business_id=business["id"])
        trabajo = db.add_job(marta["id"], "cambiar el termo",
                             scheduled_for=f"{date.today().isoformat()}T10:00",
                             business_id=business["id"])
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            sin_importe, con_importe, _, tarjeta, hecho, otra_vez = self.charla(
                business, "factura el trabajo de Marta López",
                "factura el trabajo de Marta López por 120 euros", "no",
                "ya he terminado el trabajo de Marta López", "sí",
                "he acabado lo de Marta López")
        self.assertIn("no tiene importe", sin_importe)
        self.assertIn("Concepto: cambiar el termo", con_importe)
        self.assertIn("Total: 145,20 €", con_importe)
        self.assertIn("Marcar trabajo como hecho", tarjeta)
        self.assertIn("marcado como hecho", hecho)
        self.assertIn("ningún trabajo abierto", otra_vez)
        self.assertEqual(db.get_job(trabajo["id"], business["id"])["status"], "hecho")
        (pendiente,) = self.charla(business, "que me falta por facturar")
        self.assertIn("parece hecho", pendiente)

    def test_fichar_como_se_dice(self):
        casos = {"Entrada.": "entrada", "entro": "entrada", "ya he llegado": "entrada",
                 "entrda": "entrada", "entro en el trabajo 12": "entrada 12", "me voy": "salida",
                 "salgo": "salida", "paro a comer": "pausa", "vuelvo": "reanudar",
                 "qué tengo hoy?": "hoy"}
        for escrito, comando in casos.items():
            self.assertEqual(whatsapp._worker_command(escrito.lower()), comando, escrito)
        for intacto in ("hola", "hecho t3", "coste 25,40 material", "entrar a robar"):
            self.assertEqual(whatsapp._worker_command(intacto), intacto)
        from noesis.adapters import billing as billing_adapter
        business, _ = self.make_business("Fichajes")
        operaria = db.create_worker(business["id"], "Marta Operaria")
        db.bind_worker_phone(business["id"], operaria["access_code"], "+34 611 222 333")
        respuestas = []
        with patch.object(whatsapp, "send", side_effect=lambda phone, text, **kw:
                          respuestas.append(text) or True), \
                patch.object(billing_adapter, "has_entitlement", return_value=True):
            for numero, texto in enumerate(("ya he llegado", "paro a comer", "vuelvo", "Salgo.")):
                whatsapp.handle_inbound({"id": f"wamid.fichar.{numero}",
                                         "from": "34611222333", "text": texto})
        self.assertEqual([r.split(" registrada")[0] for r in respuestas],
                         ["Entrada", "Pausa", "Vuelta", "Salida"])

    def test_catalan_de_la_ronda(self):
        casos = {
            "crea el client Joan Puig amb telèfon 612345678":
                ("crear_cliente", {"nombre": "Joan Puig", "telefono": "612345678"}),
            "el NIF de Joan Puig és 12345678Z":
                ("actualizar_cliente", {"cliente": "Joan Puig", "nif": "12345678Z"}),
            "quines factures té Joan Puig?":
                ("ver_cliente", {"cliente": "Joan Puig", "dato": "facturas"}),
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(nlu.parse(texto), esperado)
        cita = nlu.parse("agenda a la Marta dijous a les 10 per revisar la caldera")
        self.assertEqual((cita[0], cita[1]["cliente"], cita[1]["descripcion"]),
                         ("agendar_trabajo", "Marta", "revisar la caldera"))
        self.assertEqual(nlu.parse("tinc feina demà?")[0], "ver_agenda")

    # --- Mensajes sin texto

    def _meta(self, business, mensaje):
        db.set_whatsapp_status(business["id"], "conectado", phone=TELEFONO)
        self._enviados = getattr(self, "_enviados", 0) + 1
        respuestas = []
        payload = {"entry": [{"id": "waba", "changes": [{"value": {
            "metadata": {"phone_number_id": str(whatsapp._PHONE_ID or "")},
            "messages": [{"id": f"wamid.meta.{self._enviados}", "from": TELEFONO,
                          **mensaje}]}}]}]}
        with patch.object(whatsapp, "send",
                          side_effect=lambda phone, text, **kw:
                          respuestas.append(text) or True), \
             patch.object(whatsapp, "_attach_new_invoice_pdf"), \
             patch.object(chat, "handle", wraps=chat.handle) as cerebro:
            whatsapp.handle_inbound(payload)
        return respuestas, cerebro

    def test_reaccion_sticker_y_ubicacion_no_llegan_al_cerebro(self):
        """Caso real 30-sep, 18:02: un mensaje sin texto llegó vacío a la IA, que
        contestó explicando la última factura."""
        business, _ = self.make_business("Sin texto")
        respuestas, cerebro = self._meta(
            business, {"type": "reaction", "reaction": {"message_id": "x", "emoji": "👍"}})
        self.assertEqual(respuestas, [])
        cerebro.assert_not_called()
        for tipo, esperado in (("sticker", "stickers"), ("location", "ubicación"),
                               ("video", "vídeos"), ("unsupported", "no lo puedo leer")):
            with self.subTest(tipo=tipo):
                respuestas, cerebro = self._meta(business, {"type": tipo, tipo: {}})
                self.assertEqual(len(respuestas), 1)
                self.assertIn(esperado, respuestas[0])
                cerebro.assert_not_called()

    def test_tarjeta_de_contacto_propone_el_cliente(self):
        business, _ = self.make_business("Contacto compartido")
        with patch.object(config, "ASSISTANT_REVIEW_ENABLED", True):
            (tarjeta,), _ = self._meta(business, {"type": "contacts", "contacts": [{
                "name": {"formatted_name": "Ana Pérez"},
                "phones": [{"phone": "+34 600 11 22 33", "wa_id": "34600112233"}]}]})
            # El botón de una plantilla («Sí») confirma como el texto.
            (hecho,), _ = self._meta(business, {"type": "button",
                                                "button": {"text": "Sí", "payload": "si"}})
        self.assertIn("Guardar cliente", tarjeta)
        self.assertIn("Teléfono: 34600112233", tarjeta)
        self.assertIn("Cliente guardado", hecho)

    # --- Contestar sin inventar

    def test_si_gracias_y_no_sin_nada_pendiente(self):
        business, _ = self.make_business("Respuestas cortas")
        si, dale, gracias, no = self.charla(business, "sí", "dale", "gracias", "no")
        self.assertIn("no tengo nada pendiente", si.lower())
        self.assertIn("respóndeme «sí»", dale)
        self.assertTrue(gracias.startswith("De nada"))
        self.assertIn("no he tocado nada", no)
        for texto in (si, dale, gracias, no):
            self.assertNotIn("Así veo", texto)

    def test_vale_sigue_confirmando_lo_pendiente(self):
        business, client = self.make_business("Vale confirma")
        borrador = db.add_invoice(client["id"], "Reforma", 100, business_id=business["id"])
        with patch.object(whatsapp, "_send_owner_invoice_pdf", return_value={}):
            self.charla(business, f"emitir factura {borrador['id']}", "vale")
        self.assertNotEqual(
            db.get_invoice(borrador["id"], business["id"])["status"], "borrador")

    def test_borrador_ensena_concepto_y_concuerda(self):
        business, client = self.make_business("Borrador claro")
        (respuesta,) = self.charla(business, f"factura a {client['name']} por 100")
        self.assertIn("preparada para", respuesta)
        self.assertIn("(Servicio)", respuesta)
        self.assertIn("Cuando esté correcta", respuesta)

    def test_formato_del_borrador_en_femenino_y_ticket_en_masculino(self):
        base = {"id": 60, "client_name": "reformas martínez", "total": 968,
                "base": 800, "vat_amount": 168, "concept": "ventana"}
        factura = nlu.format_reply("crear_factura", {"factura": base})
        self.assertIn("Factura #60 preparada para reformas martínez (ventana)", factura)
        self.assertIn("La dejo en borrador para que la revises", factura)
        self.assertIn("para entregarla también", factura)
        ticket = nlu.format_reply(
            "crear_factura", {"factura": {**base, "invoice_type": "F2"}})
        self.assertIn("Ticket de venta #60 preparado", ticket)
        self.assertIn("Lo dejo en borrador para que lo revises", ticket)
        self.assertIn("Cuando esté correcto", ticket)

    def test_no_emitir_dice_que_falta_y_donde_completarlo(self):
        business, _ = self.make_business("Falta NIF")
        sin_nif = db.add_client("Ana López", business_id=business["id"])
        borrador = db.add_invoice(sin_nif["id"], "Arreglo", 80, business_id=business["id"])
        (respuesta,) = self.charla(business, f"emitir factura {borrador['id']}")
        self.assertIn("falta el NIF del cliente y el domicilio del cliente", respuesta)
        self.assertIn(f"/b/{business['id']}/clientes", respuesta)
        self.assertIn("ticket de venta", respuesta)
        self.assertNotIn("Es una factura completa", respuesta)
        self.assertEqual(db.get_invoice(borrador["id"], business["id"])["status"], "borrador")

    # --- Cobros, presupuestos y proyectos

    def test_recordatorio_con_frase_natural_se_ofrece_con_si(self):
        business, _ = self.make_business("Recordatorio natural")
        marta = db.add_client("Marta Roca", phone="34600999888", nif="12345678Z",
                              address="Calle Mayor 3", business_id=business["id"])
        factura = db.add_invoice(marta["id"], "Pintura", 100, business_id=business["id"])
        db.issue_invoice(factura["id"], business["id"])
        (propuesta,) = self.charla(business, "recuérdale a Marta Roca que me pague")
        self.assertIn("sigue pendiente de pago", propuesta)
        self.assertIn("Responde SÍ para enviarlo", propuesta)
        self.assertEqual(
            db.get_pending_action(business["id"], TELEFONO)["kind"], "send_communication")

    def test_reclamar_a_quien_no_debe_lo_dice(self):
        business, _ = self.make_business("Nada que reclamar")
        db.add_client("Ana López", business_id=business["id"])
        (respuesta,) = self.charla(business, "reclámale a Ana López")
        self.assertIn("Ana López no tiene facturas pendientes de cobro", respuesta)

    def test_cuanto_me_debe_es_una_pregunta_de_cobros(self):
        self.assertEqual(nlu.parse("¿cuánto me debe Reformas Martínez?")[0],
                         "ver_cobros_pendientes")

    def test_presupuesto_dice_su_numero_y_aceptarlo_no_se_finge(self):
        business, client = self.make_business("Presupuestos claros")
        creado, aceptar = self.charla(
            business, f"presupuesto a {client['name']} por baño 1200 euros",
            "acepta el presupuesto 1")
        self.assertRegex(creado, r"Presupuesto #\d+ preparado")
        self.assertIn("todavía no lo hago por WhatsApp", aceptar)
        self.assertNotIn("Así veo", aceptar)

    def test_nombre_de_proyecto_sin_con(self):
        self.assertEqual(
            nlu.parse("crea un proyecto reforma integral con presupuesto 20000 euros"),
            ("crear_proyecto", {"nombre": "reforma integral", "presupuesto": 20000.0}))

    # --- Textos como se dicen

    def test_fechas_humanas(self):
        hoy = date(2026, 9, 30)
        self.assertEqual(nlu.dia_humano("2026-09-30", hoy), "hoy")
        self.assertEqual(nlu.dia_humano("2026-10-01T10:00", hoy), "mañana a las 10:00")
        self.assertEqual(nlu.dia_humano("2026-10-08T09:30", hoy),
                         "el jueves 8 de octubre a las 9:30")
        self.assertEqual(nlu.dia_humano("2027-01-02", hoy), "el sábado 2 de enero de 2027")

    def test_plurales_sin_parentesis(self):
        uno = nlu.format_reply("ver_cobros_pendientes", {
            "n": 1, "total_pendiente": 968,
            "facturas": [{"client_name": "Ana", "total": 968}]})
        dos = nlu.format_reply("ver_cobros_pendientes", {
            "n": 2, "total_pendiente": 200,
            "facturas": [{"client_name": "Ana", "total": 100},
                         {"client_name": "Juan", "total": 100}]})
        self.assertIn("1 factura sin cobrar", uno)
        self.assertIn("2 facturas sin cobrar", dos)
        self.assertNotIn("(s)", uno + dos)
        vacio = nlu.format_reply("resumen_negocio", {
            "invoiced": 0, "collected": 0, "pending": 0, "expenses": 0,
            "estimated_profit": 0, "vat_estimated": 0})
        self.assertNotIn("Aparta", vacio)
        self.assertIn("Lo encontrarás", nlu.format_reply("ver_documentos_pendientes", {"n": 1}))
        self.assertIn("Los encontrarás", nlu.format_reply("ver_documentos_pendientes", {"n": 2}))

    def test_parte_de_la_manana_en_castellano(self):
        from noesis.agent import daily_summary_text
        business, client = self.make_business("Parte legible")
        factura = db.add_invoice(client["id"], "Reforma", 800, business_id=business["id"])
        db.issue_invoice(factura["id"], business["id"])
        parte = daily_summary_text(business["id"])
        self.assertIn(nlu.fecha_larga(date.today()), parte)
        self.assertNotIn(date.today().isoformat(), parte)
        self.assertIn("968,00 €", parte)
        self.assertNotIn("(s)", parte)


if __name__ == "__main__":
    unittest.main()
