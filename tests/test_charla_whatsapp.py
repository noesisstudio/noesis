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
        self.assertEqual(nlu.parse("¿qué facturas tiene el cliente Juan?"), None)
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
