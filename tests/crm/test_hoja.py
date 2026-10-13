"""La hoja de Google y el CRM: lo que se rompe sin avisar.

1. Que la hoja se entienda aunque cambien el orden o el nombre de las columnas,
   y que una pestaña que no es la lista se rechace en vez de importarse.
2. Que leerla dos veces no duplique a nadie, y que una lectura nueva corrija el
   teléfono sin tocar el estado, el historial ni la nota.
3. Que quien pidió la baja, o que se le borrase, no vuelva a entrar por la hoja.
   Es el único fallo de esto con consecuencias fuera del ordenador.
4. Que solo se hable con Google y que una hoja sin compartir se explique.
5. Que la dirección que lee la hoja no se abra sin su clave.
"""
import io
import unittest
import urllib.error
from datetime import date, timedelta
from unittest.mock import patch

from noesis import db, sales
from noesis.crm import google, hoja, sincronizar, zonas

from .base import ENLACE, HOJA, ConBase


class LeerColumnasTests(unittest.TestCase):
    def test_reads_the_real_columns_of_the_leads_sheet(self):
        leido = hoja.parse_hoja(HOJA)
        pons = leido["filas"][0]
        self.assertEqual(pons["nombre"], "Gestoria Pons")
        self.assertEqual(pons["email"], "info@gestoriapons.cat")
        self.assertEqual(pons["telefono"], "+34973223344")
        self.assertEqual(pons["provincia"], "Lleida")
        self.assertEqual(pons["poblacion"], "Lleida")
        self.assertEqual(pons["web"], "https://gestoriapons.cat")
        self.assertEqual(pons["correo_verificacion"], "Buzón existe")
        self.assertEqual(leido["ignoradas"], [])

    def test_the_postcode_gives_the_province_when_the_column_is_empty(self):
        riera = hoja.parse_hoja(HOJA)["filas"][1]
        self.assertEqual(riera["provincia"], "Girona")

    def test_column_order_and_accents_do_not_matter(self):
        leido = hoja.parse_hoja(
            "Provincia,Teléfono,Correo,Empresa,Lo que sea\n"
            "Lérida,600 11 22 33,HOLA@Pons.cat,Gestoria Pons,ruido\n")
        fila = leido["filas"][0]
        self.assertEqual((fila["nombre"], fila["email"], fila["provincia"]),
                         ("Gestoria Pons", "hola@pons.cat", "Lleida"))
        self.assertEqual(leido["ignoradas"], ["Lo que sea"])

    def test_a_tab_that_is_not_the_list_is_refused(self):
        # Conectar la pestaña equivocada es fácil: el enlace sin `gid` abre la
        # primera. Importarla llenaría el CRM de filas sin sentido.
        with self.assertRaises(ValueError):
            hoja.parse_hoja("Student Name,Gender,Class Level\nAlexandra,F,4\n")
        with self.assertRaises(ValueError):
            hoja.parse_hoja("")

    def test_a_title_row_above_the_header_is_skipped(self):
        leido = hoja.parse_hoja("LEADS GESTORIAS,,\n,,\nEMPRESA,EMAIL,PROVINCIA\n"
                                "Gestoria Pons,info@pons.cat,Lleida\n")
        self.assertEqual(len(leido["filas"]), 1)

    def test_the_same_office_twice_in_the_sheet_enters_once(self):
        leido = hoja.parse_hoja("EMPRESA,EMAIL\nPons,info@pons.cat\n"
                                "Pons SL,info@pons.cat\n")
        self.assertEqual(len(leido["filas"]), 1)

    def test_only_the_first_address_of_a_cell_is_kept(self):
        fila = hoja.parse_hoja(
            "EMPRESA,EMAIL\nPons,\"info@pons.cat / admin@pons.cat\"\n")["filas"][0]
        self.assertEqual(fila["email"], "info@pons.cat")

    def test_what_is_written_by_hand_maps_to_a_step_or_to_nothing(self):
        casos = {"WEB ACTIVA": None, "": None, "Solicitar info": None,
                 "Trabaja con autónomos": None, "ENVIADO 2-oct": "contactado",
                 "Ha respondido": "hablado", "Reunión el martes": "cita",
                 "No contactar": "descartado", "Descartada": "descartado"}
        for texto, esperado in casos.items():
            self.assertEqual(hoja.estado_desde_hoja(texto), esperado, texto)

    def test_a_date_in_the_sent_column_counts_as_written(self):
        fila = hoja.parse_hoja("EMPRESA,EMAIL,ENVIADO\nPons,info@pons.cat,2-oct\n"
                               "Riera,hola@riera.cat,\n")["filas"]
        self.assertEqual(fila[0]["estado_pista"], "contactado")
        self.assertIsNone(fila[1]["estado_pista"])

    def test_the_sheet_only_moves_people_forward(self):
        self.assertTrue(hoja.avanza("lista", "contactado"))
        self.assertFalse(hoja.avanza("cita", "contactado"))
        self.assertFalse(hoja.avanza("contactado", "contactado"))
        # Lo cerrado aquí no lo reabre la hoja.
        self.assertFalse(hoja.avanza("descartado", "contactado"))
        self.assertFalse(hoja.avanza("dormido", "cita"))
        self.assertTrue(hoja.avanza("piloto", "descartado"))


class ZonasTests(unittest.TestCase):
    def test_the_same_province_written_three_ways_is_one(self):
        for texto in ("LLEIDA", "Lérida", " lleida "):
            self.assertEqual(zonas.normalizar_provincia(texto), "Lleida")
        self.assertIsNone(zonas.normalizar_provincia("  "))

    def test_catalan_only_in_catalonia(self):
        self.assertEqual(zonas.lengua_de("Girona"), "ca")
        self.assertEqual(zonas.lengua_de("Huesca"), "es")
        self.assertEqual(zonas.lengua_de(None), "es")

    def test_verified_means_verified(self):
        self.assertTrue(zonas.correo_verificado("Buzón existe"))
        self.assertFalse(zonas.correo_verificado("No existe"))
        self.assertFalse(zonas.correo_verificado("Dominio con MX"))
        self.assertFalse(zonas.correo_verificado(None))


class EnlaceTests(unittest.TestCase):
    def test_the_tab_number_comes_from_the_link(self):
        self.assertTrue(google.url_csv(ENLACE).endswith("/export?format=csv&gid=5"))
        self.assertIn("gid=0", google.url_csv(
            ENLACE.split("/edit")[0] + "/edit?usp=sharing"))

    def test_a_published_link_is_understood_too(self):
        url = google.url_csv("https://docs.google.com/spreadsheets/d/e/"
                             "2PACX-1vAbCdEfGhIjKlMnOpQrStUvWxYz/pubhtml?gid=7")
        self.assertIn("/pub?output=csv&gid=7", url)

    def test_only_google_sheets_links_are_accepted(self):
        # La dirección la escribe una persona en un formulario y el servidor va a
        # pedirla: cualquier otro destino sería usar la app como puente.
        for malo in ("https://evil.example/spreadsheets/d/" + "a" * 30 + "/edit",
                     "http://docs.google.com/spreadsheets/d/" + "a" * 30,
                     "https://docs.google.com.evil.example/spreadsheets/d/" + "a" * 30,
                     "https://docs.google.com/document/d/" + "a" * 30 + "/edit",
                     "file:///etc/passwd", ""):
            with self.assertRaises(google.EnlaceNoValido, msg=malo):
                google.url_csv(malo)

    def test_a_redirect_outside_google_is_not_followed(self):
        with self.assertRaises(google.HojaNoDisponible):
            google._SoloGoogle().redirect_request(
                None, None, 302, "Found", {}, "https://evil.example/x")

    def _respuesta(self, cuerpo: bytes, tipo: str, url: str):
        class Respuesta(io.BytesIO):
            headers = {"Content-Type": tipo}

            def geturl(self):
                return url
        return Respuesta(cuerpo)

    def _abridor(self, resultado):
        class Abridor:
            def open(self, peticion, timeout=None):
                if isinstance(resultado, Exception):
                    raise resultado
                return resultado
        return patch.object(google.urllib.request, "build_opener",
                            lambda *a, **k: Abridor())

    def test_a_sheet_that_is_not_shared_is_explained_not_parsed(self):
        # Google no contesta con un error: contesta con la página de entrada.
        pagina = self._respuesta(b"<html>Sign in</html>", "text/html; charset=utf-8",
                                 "https://accounts.google.com/ServiceLogin")
        with self._abridor(pagina), self.assertRaises(google.HojaNoCompartida) as ctx:
            google.descargar(ENLACE)
        self.assertIn("Compartir", str(ctx.exception))

    def test_a_shared_sheet_comes_back_as_text(self):
        csv = self._respuesta("EMPRESA,EMAIL\nPons,a@b.cat\n".encode("utf-8-sig"),
                              "text/csv", "https://doc-0.googleusercontent.com/x")
        with self._abridor(csv):
            self.assertTrue(google.descargar(ENLACE).startswith("EMPRESA"))

    def test_a_deleted_sheet_says_so(self):
        error = urllib.error.HTTPError(ENLACE, 404, "Not Found", {}, None)
        with self._abridor(error), self.assertRaises(google.HojaNoDisponible):
            google.descargar(ENLACE)


class SincronizarTests(ConBase):
    def setUp(self):
        super().setUp()
        self.hoja = sincronizar.connect_sheet(url=ENLACE, nombre="Gestorías")

    def _leer(self, texto=HOJA):
        return sincronizar.leer_hoja(self.hoja["id"], texto=texto)

    def test_the_first_reading_creates_one_card_per_row(self):
        resultado = self._leer()
        self.assertTrue(resultado["ok"])
        self.assertEqual((resultado["nuevas"], resultado["actualizadas"]), (3, 0))
        fichas = db.list_prospects()
        self.assertEqual({p["tipo"] for p in fichas}, {"gestoria"})
        self.assertEqual({p["origen"] for p in fichas}, {"web"})

    def test_a_thousand_rows_do_not_become_a_thousand_calls_for_today(self):
        self._leer()
        self.assertEqual(sales.resumen(db.list_prospects())["hoy"], [])

    def test_reading_twice_adds_nobody(self):
        self._leer()
        segundo = self._leer()
        self.assertEqual((segundo["nuevas"], segundo["actualizadas"]), (0, 0))
        self.assertEqual(len(db.list_prospects()), 3)

    def test_the_sheet_fixes_contact_data_and_leaves_the_rest_alone(self):
        self._leer()
        pons = next(p for p in db.list_prospects() if p["nombre"] == "Gestoria Pons")
        db.add_sales_touch(pons["id"], canal="email", resumen="Primer correo",
                           estado_despues="contactado")
        db.update_prospect(pons["id"], nota="Preguntar por la Marta")
        resultado = self._leer(HOJA.replace("973 22 33 44", "973 99 88 77"))
        self.assertEqual(resultado["actualizadas"], 1)
        despues = db.get_prospect(pons["id"])
        self.assertEqual(despues["telefono"], "+34973998877")
        self.assertEqual(despues["estado"], "contactado")
        self.assertEqual(despues["nota"], "Preguntar por la Marta")
        self.assertEqual(len(db.list_sales_touches(pons["id"])), 1)

    def test_an_empty_cell_does_not_erase_what_was_known(self):
        self._leer()
        self._leer(HOJA.replace("973 22 33 44", ""))
        pons = next(p for p in db.list_prospects() if p["nombre"] == "Gestoria Pons")
        self.assertEqual(pons["telefono"], "+34973223344")

    def test_a_changed_address_updates_the_card_instead_of_duplicating_it(self):
        self._leer()
        self._leer(HOJA.replace("info@gestoriapons.cat", "hola@gestoriapons.cat"))
        fichas = [p for p in db.list_prospects() if p["nombre"] == "Gestoria Pons"]
        self.assertEqual(len(fichas), 1)
        self.assertEqual(fichas[0]["email"], "hola@gestoriapons.cat")

    def test_someone_already_in_the_list_is_linked_not_repeated(self):
        db.add_prospect(nombre="Pons (gestoría)", email="info@gestoriapons.cat",
                        origen="referido", tipo="gestoria")
        resultado = self._leer()
        self.assertEqual(resultado["nuevas"], 2)
        self.assertEqual(len(db.list_prospects()), 3)

    def test_marking_it_sent_in_the_sheet_moves_it_here_and_leaves_a_note(self):
        self._leer()
        resultado = self._leer(HOJA.replace(
            "WEB ACTIVA,,hola@riera.cat", "ENVIADO 2-oct,,hola@riera.cat"))
        self.assertEqual(resultado["avanzadas"], 1)
        riera = next(p for p in db.list_prospects()
                     if p["nombre"] == "Assessoria Riera")
        self.assertEqual(riera["estado"], "contactado")
        self.assertEqual(riera["siguiente_el"],
                         (date.today() + timedelta(days=7)).isoformat())
        apunte = db.list_sales_touches(riera["id"])[0]
        self.assertIn("ENVIADO 2-oct", apunte["resumen"])
        # Y leerla otra vez no lo vuelve a apuntar.
        self._leer(HOJA.replace(
            "WEB ACTIVA,,hola@riera.cat", "ENVIADO 2-oct,,hola@riera.cat"))
        self.assertEqual(len(db.list_sales_touches(riera["id"])), 1)

    def test_who_asked_not_to_be_contacted_is_left_alone(self):
        self._leer()
        pons = next(p for p in db.list_prospects() if p["nombre"] == "Gestoria Pons")
        db.prospect_opt_out(pons["id"], "No nos escribáis más")
        resultado = self._leer(HOJA.replace("973 22 33 44", "973 99 88 77")
                               .replace("WEB ACTIVA,973", "ENVIADO,973"))
        self.assertEqual(resultado["bajas"], 1)
        despues = db.get_prospect(pons["id"])
        self.assertTrue(despues["baja"])
        self.assertEqual(despues["estado"], "descartado")
        self.assertEqual(despues["telefono"], "+34973223344")

    def test_who_asked_to_be_erased_does_not_come_back_from_the_sheet(self):
        self._leer()
        pons = next(p for p in db.list_prospects() if p["nombre"] == "Gestoria Pons")
        sincronizar.recordar_supresion(pons)
        db.delete_prospect(pons["id"])
        resultado = self._leer()
        self.assertEqual(resultado["nuevas"], 0)
        self.assertEqual(resultado["bajas"], 1)
        self.assertNotIn("Gestoria Pons",
                         [p["nombre"] for p in db.list_prospects()])
        # Lo guardado no es el dato: es una huella que no lo contiene.
        with db.get_conn() as conn:
            huellas = [f["huella"] for f in conn.execute(
                "SELECT huella FROM sales_suppressions").fetchall()]
        self.assertTrue(huellas)
        self.assertFalse(any("pons" in h for h in huellas))

    def test_rows_gone_from_the_sheet_are_kept_and_counted(self):
        self._leer()
        resultado = self._leer("\n".join(HOJA.splitlines()[:3]) + "\n")
        self.assertEqual(resultado["ausentes"], 1)
        self.assertEqual(len(db.list_prospects()), 3)

    def test_a_failed_reading_is_recorded_and_changes_nothing(self):
        self._leer()
        mal = self._leer("Student Name,Gender\nAlexandra,F\n")
        self.assertFalse(mal["ok"])
        apuntada = sincronizar.get_sheet(self.hoja["id"])
        self.assertEqual(apuntada["ultimo_estado"], "error")
        self.assertIn("pestaña", apuntada["ultimo_error"])
        # Las cifras de la última lectura buena siguen ahí.
        self.assertEqual(apuntada["filas"], 3)
        self.assertEqual(len(db.list_prospects()), 3)

    def test_a_sheet_that_is_not_shared_is_reported_in_words(self):
        with patch.object(google, "descargar",
                          side_effect=google.HojaNoCompartida("Pulsa «Compartir»")):
            resultado = sincronizar.leer_hoja(self.hoja["id"])
        self.assertFalse(resultado["ok"])
        self.assertIn("Compartir", sincronizar.frase_de_lectura(resultado))

    def test_one_broken_sheet_does_not_stop_the_daily_reading(self):
        otra = sincronizar.connect_sheet(url=ENLACE.replace("gid=5", "gid=6"),
                                         nombre="Gremios", tipo="gremio")

        def descargar(url):
            if "gid=6" in url:
                raise RuntimeError("inesperado")
            return HOJA
        with patch.object(google, "descargar", side_effect=descargar):
            resultados = sincronizar.leer_todas()
        self.assertEqual([r["ok"] for r in resultados], [True])
        self.assertEqual(sincronizar.get_sheet(otra["id"])["ultimo_estado"], "error")

    def test_the_same_tab_cannot_be_connected_twice(self):
        with self.assertRaises(ValueError):
            sincronizar.connect_sheet(url=ENLACE + "&usp=sharing")

    def test_disconnecting_keeps_the_cards_unless_asked(self):
        self._leer()
        sincronizar.disconnect_sheet(self.hoja["id"])
        self.assertEqual(len(db.list_prospects()), 3)
        self.assertEqual(sincronizar.list_sheets(), [])

    def test_undoing_a_wrong_tab_only_removes_what_was_never_touched(self):
        self._leer()
        pons = next(p for p in db.list_prospects() if p["nombre"] == "Gestoria Pons")
        db.add_sales_touch(pons["id"], canal="email", resumen="Primer correo",
                           estado_despues="contactado")
        resultado = sincronizar.disconnect_sheet(self.hoja["id"],
                                                 quitar_sin_tocar=True)
        self.assertEqual(resultado["quitadas"], 2)
        self.assertEqual([p["nombre"] for p in db.list_prospects()],
                         ["Gestoria Pons"])


class EnlaceParaLaHojaTests(ConBase):
    def test_the_key_opens_it_and_a_new_one_closes_the_old(self):
        primera = sincronizar.crear_enlace()
        self.assertTrue(sincronizar.enlace_valido(primera))
        segunda = sincronizar.crear_enlace()
        self.assertFalse(sincronizar.enlace_valido(primera))
        self.assertTrue(sincronizar.enlace_valido(segunda))
        self.assertTrue(sincronizar.revocar_enlace())
        self.assertFalse(sincronizar.enlace_valido(segunda))

    def test_the_key_itself_is_not_stored(self):
        clave = sincronizar.crear_enlace()
        with db.get_conn() as conn:
            fila = dict(conn.execute("SELECT * FROM sales_feeds").fetchone())
        self.assertNotIn(clave, fila.values())

    def test_nothing_opens_without_a_key(self):
        for clave in ("", "x", "a" * 500):
            self.assertFalse(sincronizar.enlace_valido(clave))

    def test_the_table_says_where_each_one_is_and_keeps_the_notes_out(self):
        ficha = db.add_prospect(nombre="Gestoria Pons", email="info@pons.cat",
                                telefono="973223344", provincia="lleida",
                                tipo="gestoria", nota="Dijo que su socio no quiere")
        db.add_sales_touch(ficha["id"], canal="email", resumen="Secreto",
                           estado_despues="contactado", fecha="2026-10-02")
        tabla = sincronizar.csv_para_hoja()
        self.assertIn("Gestoria Pons,info@pons.cat,973 223 344,Lleida,Gestoría,"
                      "Contactado,2026-10-02,Correo,1,Insistir una vez,2026-10-09,",
                      tabla)
        self.assertNotIn("socio", tabla)
        self.assertNotIn("Secreto", tabla)

    def test_a_name_that_looks_like_a_formula_is_defused(self):
        db.add_prospect(nombre='=IMPORTXML("http://evil.example";"//a")')
        linea = sincronizar.csv_para_hoja().splitlines()[1]
        self.assertTrue(linea.startswith("\"'=") or linea.startswith("'="), linea)

    def test_who_opted_out_is_flagged_and_has_no_next_step(self):
        ficha = db.add_prospect(nombre="Gestoria Pons", email="info@pons.cat")
        db.prospect_opt_out(ficha["id"], "No")
        self.assertTrue(sincronizar.csv_para_hoja().splitlines()[1].endswith(",,SÍ"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
