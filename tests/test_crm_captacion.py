"""CRM de captación: el embudo de Bynoesis, no el del autónomo.

Lo que aquí se fija es lo que se rompe sin avisar:

1. Que la lista pegada a mano se entienda. Es como entran los cuarenta nombres, y
   se escribe en catalán y en castellano, con el teléfono en cualquier formato.
2. Que nadie entre dos veces, y que quien pidió no ser contactado no vuelva a
   entrar al pegar la lista otra vez. Volver a llamar a quien dijo que no es el
   único fallo de este panel con consecuencias fuera del ordenador.
3. Que el embudo no se vacíe solo al avanzar la gente.
4. Que los guiones no tengan huecos que nadie rellena.
5. Que la página y el CSV no queden accesibles sin ser administrador.
"""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from noesis import config, db, sales


class ListaPegadaTests(unittest.TestCase):
    """La lista se escribe en la libreta del móvil, no en un CSV."""

    def test_reads_a_line_written_by_hand(self):
        fila = sales.parse_lista("Jordi Mas; fontanero; Palafrugell; 600 11 22 33")[0]
        self.assertEqual(fila["nombre"], "Jordi Mas")
        self.assertEqual(fila["oficio"], "fontaneria")
        self.assertEqual(fila["poblacion"], "Palafrugell")
        self.assertEqual(fila["telefono"], "+34600112233")

    def test_reads_the_trade_written_in_catalan(self):
        # «Lampista» y «fuster» son como lo escribe media Cataluña. Si no los
        # reconoce, la lista entra sin oficio y el filtro por oficio no sirve.
        for texto, oficio in (("Pep - lampista - la Bisbal", "fontaneria"),
                              ("Can Roca, fuster, Torroella", "carpinteria"),
                              ("Marc · reformes · Begur", "reformas"),
                              ("Neteges Vidal, neteja, Palamós", "limpieza")):
            self.assertEqual(sales.parse_lista(texto)[0]["oficio"], oficio, texto)

    def test_separators_and_stray_dashes_do_not_end_up_in_the_name(self):
        fila = sales.parse_lista("Anna Soler - electricista, Begur, +34611223344")[0]
        self.assertEqual(fila["nombre"], "Anna Soler")
        self.assertEqual(fila["email"], None)

    def test_the_phone_is_found_wherever_it_is(self):
        for texto in ("600112233 Jordi", "Jordi (600 11 22 33) Begur",
                      "Jordi; 0034600112233", "Jordi; +34 600 11 22 33"):
            self.assertEqual(sales.parse_lista(texto)[0]["telefono"],
                             "+34600112233", texto)

    def test_what_it_does_not_understand_goes_to_the_note(self):
        fila = sales.parse_lista(
            "Jordi Mas; fontanero; Palafrugell; 600112233; me lo presenta Marta; "
            "trabaja con su hermano")[0]
        self.assertIn("Marta", fila["nota"])
        self.assertIn("hermano", fila["nota"])

    def test_a_table_with_headers_is_respected_instead_of_guessed(self):
        # La prospección que ya existe en `outputs/prospeccion/` sale así. Si se
        # adivinara, el nombre acabaría siendo «Oficio» y el teléfono, una calle.
        pegado = (
            "grupo;actividad;nombre;telefono;web;direccion;mapa;estado;notas\n"
            "Oficio;Carpintería;Fusteria Arroyos;+34687436564;;"
            "Carrer d'Àger 35, 25001;https://osm.org/node/1;;\n"
            "Almacén o ferretería;Ferretería;Can Pau;973 11 22 33;;"
            "Carrer Major 2;https://osm.org/node/2;;")
        filas = sales.parse_lista(pegado)
        self.assertEqual([f["nombre"] for f in filas],
                         ["Fusteria Arroyos", "Can Pau"])
        self.assertEqual(filas[0]["oficio"], "carpinteria")
        self.assertEqual(filas[0]["telefono"], "+34687436564")
        self.assertIn("Carrer d'Àger", filas[0]["poblacion"])
        # La columna que no conocemos se conserva; la dirección de mapa, no.
        self.assertIn("Oficio", filas[0]["nota"])
        self.assertNotIn("osm.org", filas[0]["nota"] or "")

    def test_a_row_without_a_name_but_with_a_phone_is_still_a_client(self):
        pegado = ("nombre;telefono;web\n"
                  ";+34973229644;https://www.singularlleida.com/\n"
                  ";;")
        filas = sales.parse_lista(pegado)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["nombre"], "singularlleida.com")
        self.assertEqual(filas[0]["telefono"], "+34973229644")

    def test_a_handwritten_line_with_semicolons_is_not_taken_for_a_table(self):
        filas = sales.parse_lista("Jordi Mas; fontanero; Palafrugell; 600112233")
        self.assertEqual(filas[0]["nombre"], "Jordi Mas")

    def test_an_empty_paste_creates_nothing(self):
        self.assertEqual(sales.parse_lista("\n  \n"), [])

    def test_phone_normalisation_rejects_what_is_not_a_phone(self):
        self.assertIsNone(sales.normalizar_telefono("12"))
        self.assertIsNone(sales.normalizar_telefono(""))
        self.assertEqual(sales.normalizar_telefono("972 11 22 33"), "+34972112233")


class GuionesTests(unittest.TestCase):
    """Los guiones se mandan a personas reales: no pueden tener huecos."""

    # Los que sustituye `admin-crm.js`. Uno nuevo saldría literal en el mensaje.
    HUECOS = {"nombre", "yo", "quien", "oficio", "zona", "novedad"}

    def test_every_script_has_both_languages_and_known_holes(self):
        import re
        for clave, guion in sales.GUIONES.items():
            for lengua in ("es", "ca"):
                texto = guion[lengua]
                self.assertTrue(texto.strip(), f"{clave}.{lengua}")
                huecos = set(re.findall(r"\{(\w+)\}", texto))
                self.assertTrue(huecos <= self.HUECOS,
                                f"{clave}.{lengua} usa {huecos - self.HUECOS}")
            self.assertIn(guion["canal"], sales.CANALES, clave)

    def test_every_state_points_at_scripts_that_exist(self):
        for estado, claves in sales.GUION_POR_ESTADO.items():
            self.assertIn(estado, sales.ESTADOS, estado)
            for clave in claves:
                self.assertIn(clave, sales.GUIONES, clave)

    def test_the_funnel_targets_name_real_states(self):
        for clave, meta, _que in sales.OBJETIVO:
            self.assertIn(clave, sales.ESTADOS, clave)
            self.assertGreater(meta, 0, clave)

    def test_the_cold_call_script_says_where_the_number_came_from(self):
        # Es el requisito del artículo 14 y, además, lo que hace que la llamada no
        # suene a spam. Si alguien reescribe el guion y lo quita, salta aquí.
        for lengua, pista in (("es", "He visto tu ficha"), ("ca", "He vist la teva fitxa")):
            self.assertIn(pista, sales.GUIONES["lista_frio"][lengua])


class EmbudoTests(unittest.TestCase):
    """Contar mal el embudo es peor que no contarlo."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "test.db",
            BACKUP_DIR=Path(self.temp.name) / "backups",
            DOCS_PATH=Path(self.temp.name) / "docs")
        self.settings.start()
        db.init_db()

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def test_moving_someone_forward_does_not_empty_the_step_behind(self):
        # Quien está en piloto ya tuvo su conversación: si el peldaño de
        # conversaciones solo contara el estado actual, avanzar la gente haría
        # que el embudo pareciera vaciarse.
        db.add_prospect(nombre="Uno", estado="lista")
        db.add_prospect(nombre="Dos", estado="piloto")
        embudo = {p["clave"]: p["hay"] for p in
                  sales.resumen(db.list_prospects())["embudo"]}
        self.assertEqual(embudo["lista"], 2)
        self.assertEqual(embudo["hablado"], 1)
        self.assertEqual(embudo["piloto"], 1)
        self.assertEqual(embudo["carta"], 0)

    def test_someone_who_said_no_is_out_of_every_count(self):
        db.add_prospect(nombre="Uno", estado="lista",
                        siguiente_el=date.today().isoformat())
        segundo = db.add_prospect(nombre="Dos", estado="lista",
                                  siguiente_el=date.today().isoformat())
        db.prospect_opt_out(segundo["id"], "No le interesa")
        resumen = sales.resumen(db.list_prospects())
        self.assertEqual(resumen["total"], 1)
        self.assertEqual(resumen["bajas"], 1)
        self.assertEqual([p["nombre"] for p in resumen["hoy"]], ["Uno"])

    def test_today_holds_what_is_due_and_not_what_is_closed(self):
        ayer = (date.today() - timedelta(days=1)).isoformat()
        db.add_prospect(nombre="Vencido", estado="contactado", siguiente_el=ayer)
        db.add_prospect(nombre="Cerrado", estado="descartado", siguiente_el=ayer)
        db.add_prospect(nombre="Futuro", estado="contactado",
                        siguiente_el=(date.today() + timedelta(days=5)).isoformat())
        hoy = [p["nombre"] for p in sales.resumen(db.list_prospects())["hoy"]]
        self.assertEqual(hoy, ["Vencido"])

    def test_a_freshly_pasted_list_does_not_ask_for_seventy_calls(self):
        # Al pegar la lista, «hoy» vence entera. Pedir setenta llamadas es como se
        # consigue que no se haga ninguna: la página pide un día de trabajo y dice
        # cuántos quedan detrás.
        hoy = date.today().isoformat()
        for i in range(25):
            db.add_prospect(nombre=f"Contacto {i}", estado="lista", siguiente_el=hoy)
        resumen = sales.resumen(db.list_prospects())
        self.assertEqual(len(resumen["hoy"]), 25)
        self.assertEqual(len(resumen["hoy_lote"]), sales.LOTE_DIARIO)
        self.assertEqual(resumen["hoy_mas"], 25 - sales.LOTE_DIARIO)
        self.assertIn("no caben en un día", resumen["parte"])

    def test_the_verdict_says_what_to_do_when_the_list_is_short(self):
        self.assertIn("cuarenta nombres", sales.resumen([])["parte"])
        db.add_prospect(nombre="Uno", estado="lista")
        self.assertIn("faltan 39", sales.resumen(db.list_prospects())["parte"])


class FichaTests(unittest.TestCase):
    """La ficha, el historial y lo que obliga el origen del dato."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "test.db",
            BACKUP_DIR=Path(self.temp.name) / "backups",
            DOCS_PATH=Path(self.temp.name) / "docs")
        self.settings.start()
        db.init_db()

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def test_a_touch_moves_the_state_and_sets_the_next_date(self):
        ficha = db.add_prospect(nombre="Jordi", estado="lista")
        db.add_sales_touch(ficha["id"], canal="llamada",
                           resumen="Los presupuestos los hace el domingo",
                           estado_despues="cita")
        despues = db.get_prospect(ficha["id"])
        self.assertEqual(despues["estado"], "cita")
        self.assertEqual(despues["siguiente_el"],
                         (date.today() + timedelta(days=1)).isoformat())
        self.assertEqual(despues["siguiente_accion"],
                         sales.ESTADOS["cita"]["siguiente"])
        historial = db.list_sales_touches(ficha["id"])
        self.assertEqual(len(historial), 1)
        self.assertIn("domingo", historial[0]["resumen"])

    def test_public_data_asks_to_be_told_and_stops_asking_once_told(self):
        ficha = db.add_prospect(nombre="Jordi", origen="maps")
        self.assertTrue(sales.enriquecer(db.get_prospect(ficha["id"]))["debe_informar"])
        db.update_prospect(ficha["id"], informado_el=date.today().isoformat())
        self.assertFalse(sales.enriquecer(db.get_prospect(ficha["id"]))["debe_informar"])

    def test_data_given_by_the_person_never_asks(self):
        ficha = db.add_prospect(nombre="Marta", origen="circulo")
        self.assertFalse(sales.enriquecer(db.get_prospect(ficha["id"]))["debe_informar"])

    def test_an_unknown_state_or_trade_is_refused(self):
        ficha = db.add_prospect(nombre="Jordi")
        with self.assertRaises(ValueError):
            db.update_prospect(ficha["id"], estado="pensandoselo")
        with self.assertRaises(ValueError):
            db.add_prospect(nombre="Otro", oficio="astronauta")
        with self.assertRaises(ValueError):
            db.add_sales_touch(ficha["id"], canal="paloma")

    def test_a_name_is_required(self):
        with self.assertRaises(ValueError):
            db.add_prospect(nombre="   ")

    def test_deleting_takes_the_history_with_it(self):
        ficha = db.add_prospect(nombre="Jordi")
        db.add_sales_touch(ficha["id"], canal="llamada", resumen="Hablamos")
        self.assertTrue(db.delete_prospect(ficha["id"]))
        self.assertEqual(db.list_sales_touches(ficha["id"]), [])
        self.assertIsNone(db.get_prospect(ficha["id"]))


class ImportarTests(unittest.TestCase):
    """Pegar la lista dos veces es lo normal, no la excepción."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "test.db",
            BACKUP_DIR=Path(self.temp.name) / "backups",
            DOCS_PATH=Path(self.temp.name) / "docs")
        self.settings.start()
        db.init_db()

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def test_pasting_the_list_twice_only_adds_what_is_new(self):
        lista = "Jordi; 600112233\nAnna; 611223344"
        db.import_prospects(sales.parse_lista(lista), origen="maps")
        segundo = db.import_prospects(
            sales.parse_lista(lista + "\nMarc; 622334455"), origen="maps")
        self.assertEqual(len(segundo["creados"]), 1)
        self.assertEqual(len(segundo["repetidos"]), 2)
        self.assertEqual(len(db.list_prospects()), 3)

    def test_the_same_phone_in_another_format_is_still_the_same_person(self):
        db.import_prospects(sales.parse_lista("Jordi Mas; 600 11 22 33"))
        segundo = db.import_prospects(
            sales.parse_lista("Jordi M.; +34600112233"))
        self.assertEqual(segundo["creados"], [])

    def test_someone_who_asked_not_to_be_contacted_does_not_come_back(self):
        # Es el fallo de este panel con consecuencias fuera del ordenador: pegar
        # otra vez la lista y volver a llamar a quien ya dijo que no.
        creados = db.import_prospects(sales.parse_lista("Jordi; 600112233"))
        db.prospect_opt_out(creados["creados"][0]["id"], "No me llames más")
        otra_vez = db.import_prospects(sales.parse_lista("Jordi; 600112233"))
        self.assertEqual(otra_vez["creados"], [])
        self.assertTrue(db.list_prospects()[0]["baja"])

    def test_the_whole_list_starts_due_today(self):
        db.import_prospects(sales.parse_lista("Jordi; 600112233"))
        self.assertEqual(db.list_prospects()[0]["siguiente_el"],
                         date.today().isoformat())


class PaginaTests(unittest.TestCase):
    """La página, el CSV y quién puede verlos."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "test.db",
            BACKUP_DIR=Path(self.temp.name) / "backups",
            DOCS_PATH=Path(self.temp.name) / "docs")
        self.settings.start()
        db.init_db()
        self.business = db.create_business("Bynoesis", "test@example.com")["id"]

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def _client(self):
        from starlette.testclient import TestClient

        from noesis.web import auth, server
        password = "test-only-password"  # pragma: allowlist secret
        db.create_user("admin@example.com", auth.hash_password(password),
                       self.business)
        contexto = (patch.object(config, "ADMIN_EMAIL", "admin@example.com"),
                    patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
                    patch.object(server, "start_scheduler", lambda: None))
        return contexto, TestClient(server.app), password

    def _entrar(self, client, password):
        client.post("/login", data={"email": "admin@example.com",
                                    "password": password})

    def test_everything_requires_an_admin_session(self):
        contexto, client, _ = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            for ruta in ("/admin/crm", "/admin/crm/export.csv"):
                respuesta = client.get(ruta, follow_redirects=False)
                self.assertEqual(respuesta.status_code, 303, ruta)
                self.assertEqual(respuesta.headers["location"], "/login")
            for ruta in ("/admin/crm/nuevo", "/admin/crm/importar",
                         "/admin/crm/1/toque", "/admin/crm/1/baja"):
                respuesta = client.post(ruta, data={}, follow_redirects=False)
                self.assertEqual(respuesta.status_code, 303, ruta)
                self.assertEqual(respuesta.headers["location"], "/login")

    def test_an_empty_page_says_where_to_start(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            pagina = client.get("/admin/crm")
            self.assertEqual(pagina.status_code, 200)
            self.assertIn("cuarenta nombres", pagina.text)
            self.assertIn("círculo", pagina.text)

    def test_pasting_a_list_fills_the_funnel(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            client.post("/admin/crm/importar", data={
                "lista": "Jordi Mas; lampista; Palafrugell; 600112233\n"
                         "Anna Soler - electricista - Begur - 611223344",
                "origen": "maps"}, follow_redirects=True)
            self.assertEqual(len(db.list_prospects()), 2)
            pagina = client.get("/admin/crm")
            self.assertIn("Jordi Mas", pagina.text)
            self.assertIn("Anna Soler", pagina.text)

    def test_the_card_shows_the_script_in_both_languages(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            client.post("/admin/crm/nuevo",
                        data={"nombre": "Jordi Mas", "oficio": "fontaneria",
                              "poblacion": "Palafrugell", "origen": "referido",
                              "presentado_por": "Marta"}, follow_redirects=True)
            ficha = db.list_prospects()[0]["id"]
            pagina = client.get(f"/admin/crm?contacto={ficha}")
            self.assertIn("Estic fent una eina", pagina.text)
            self.assertIn("No te voy a vender nada", pagina.text)

    def test_a_touch_from_the_page_writes_the_history(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            client.post("/admin/crm/nuevo", data={"nombre": "Jordi Mas",
                                                  "origen": "maps"},
                        follow_redirects=True)
            ficha = db.list_prospects()[0]["id"]
            client.post(f"/admin/crm/{ficha}/toque",
                        data={"canal": "llamada", "resumen": "Le llamo el jueves",
                              "estado_despues": "cita", "informado": "si"},
                        follow_redirects=True)
            despues = db.get_prospect(ficha)
            self.assertEqual(despues["estado"], "cita")
            self.assertEqual(despues["informado_el"], date.today().isoformat())
            self.assertEqual(len(db.list_sales_touches(ficha)), 1)

    def test_the_csv_carries_the_whole_list(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            db.add_prospect(nombre="Jordi Mas", telefono="600112233")
            descarga = client.get("/admin/crm/export.csv")
            self.assertEqual(descarga.status_code, 200)
            self.assertIn("text/csv", descarga.headers["content-type"])
            self.assertIn("Jordi Mas", descarga.text)
            # BOM: sin él, Excel en Windows parte las tildes.
            self.assertTrue(descarga.text.startswith("﻿"))

    def test_a_paste_that_says_nothing_does_not_create_rows(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            client.post("/admin/crm/importar", data={"lista": "   \n  "},
                        follow_redirects=True)
            self.assertEqual(db.list_prospects(), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
