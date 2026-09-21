"""Panel de economía: el modelo, los dos documentos y quién puede verlos.

Tres cosas que pueden romperse sin avisar y que aquí se fijan:

1. Que el modelo del producto se separe de los libros de `analysis/`. Las cifras
   ancla del 15/07/2026 se comprueban al céntimo: si alguien toca un driver, salta.
2. Que Word o Excel salgan corruptos. Son ZIPs de XML escritos a mano, y Office no
   da un error legible, da «archivo dañado». Aquí se abren y se revisan las piezas.
3. Que la página o las descargas queden accesibles sin ser administrador.
"""
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from noesis import config, db, economics, economics_docs, officedocs


class ModeloEconomicoTests(unittest.TestCase):
    """Las cifras ancla del análisis del 15/07/2026, al céntimo."""

    def test_every_editable_field_exists_in_the_model(self):
        # Un campo editable que el modelo no usa es peor que no tenerlo: la web
        # deja escribirlo y no cambia nada. Esto lo impide.
        for key, spec in economics.EDITABLE.items():
            self.assertIn(key, economics.ASSUMPTIONS, key)
            defecto = economics.ASSUMPTIONS[key]
            if spec["tipo"] == "plan":
                self.assertEqual(len(defecto), len(economics.PLANES), key)
            else:
                self.assertIsInstance(defecto, (int, float), key)
            self.assertIn(spec["grupo"], {g[0] for g in economics.GRUPOS}, key)
            self.assertLessEqual(spec["min"], spec["max"], key)

    def test_editing_a_field_actually_moves_the_model(self):
        # Y que exista no basta: tiene que cambiar alguna cifra al tocarlo.
        base = economics.build_report()
        def firma(r):
            return (round(r["medias"]["cogs"], 6),
                    round(r["medias"]["contribucion_caja"], 6),
                    [n["cuentas"] for n in r["equilibrios"]],
                    r["capacidad"]["techo"], r["rampa"]["mes_positivo"],
                    round(r["rampa"]["caja_minima"], 2),
                    round(r["vida_media"], 6), round(r["ltv_cac"] or 0, 6),
                    round(r["payback"] or 0, 6))
        # La cuota de implantacion solo entra en caja si alguien la paga, y por
        # defecto no la paga nadie. No es un campo muerto: depende de otro.
        depende = {"implantacion": {"pct_implantacion": 1.0}}
        for key, spec in economics.EDITABLE.items():
            defecto = economics.ASSUMPTIONS[key]
            if spec["tipo"] == "plan":
                movido = [min(spec["max"], float(v) * 2 + 1) for v in defecto]
                if key == "mix":
                    movido = [0.2, 0.3, 0.5]
            else:
                movido = min(spec["max"], float(defecto) * 2 + 1)
            extra = depende.get(key, {})
            partida = economics.build_report(saved=extra) if extra else base
            distinto = economics.build_report(saved={key: movido, **extra})
            self.assertNotEqual(firma(partida), firma(distinto),
                                f"{key} se puede editar pero no mueve nada")

    def test_cost_per_plan_matches_the_published_analysis(self):
        planes = economics.per_plan(economics.ASSUMPTIONS)
        costes = [round(p["cogs"], 2) for p in planes]
        self.assertEqual(costes, [1.48, 3.04, 18.47])

    def test_weighted_averages_and_contributions(self):
        rep = economics.build_report()
        med = rep["medias"]
        self.assertEqual(round(med["arpu"], 2), 43.00)
        self.assertEqual(round(med["cogs"], 4), 3.7276)
        # Ponderados por la mezcla 55/35/10, no los 12 min del plan Autónomo:
        # esa confusión es la que hacía creer que cabían 300 cuentas.
        self.assertEqual(round(med["soporte_min"], 1), 18.1)
        self.assertEqual(round(med["contribucion_caja"], 2), 37.98)
        self.assertEqual(round(med["contribucion_cargada"], 2), 28.72)

    def test_the_three_breakevens_and_the_fourth_with_paid_support(self):
        rep = economics.build_report()
        self.assertEqual([n["cuentas"] for n in rep["equilibrios"]], [4, 12, 44, 57])
        clave = [n for n in rep["equilibrios"] if n["clave"]]
        self.assertEqual(len(clave), 1)
        self.assertEqual(clave[0]["cuentas"], 44)

    def test_ramp_capacity_and_lifetime(self):
        rep = economics.build_report()
        self.assertEqual(rep["capacidad"]["techo"], 198)
        self.assertEqual(rep["rampa"]["mes_positivo"], 10)
        self.assertEqual(round(rep["rampa"]["caja_minima"]), -3390)
        self.assertEqual(round(rep["rampa"]["cuentas_final"]), 116)
        # Dos tramos de bajas dan menos vida que un churn plano del 4 % (25 meses).
        self.assertEqual(round(rep["vida_media"], 1), 22.2)
        self.assertLess(rep["vida_media"], 25)

    def test_levers_are_clamped_and_never_crash_the_model(self):
        for valor in ("-999", "99999", "no-es-un-numero", "", None):
            rep = economics.build_report({"retirada": valor, "horas_mes": valor,
                                          "churn_maduro": valor, "soporte_medio": valor})
            self.assertGreater(rep["medias"]["contribucion_caja"], 0)
            self.assertEqual(len(rep["rampa"]["filas"]), 36)
        acotado = economics.with_levers({"churn_maduro": "999"})
        self.assertEqual(acotado["churn_maduro"], 0.30)
        self.assertEqual(acotado["churn_nuevo"], economics.ASSUMPTIONS["churn_nuevo"])

    def test_saved_new_churn_survives_empty_and_unrelated_levers(self):
        for overrides in ({key: None for key in economics.LEVERS}, {"retirada": "1800"}):
            rep = economics.build_report(overrides, saved={"churn_nuevo": 0.25})
            self.assertEqual(rep["assumptions"]["churn_nuevo"], 0.25)

    def test_nonfinite_levers_do_not_change_assumptions(self):
        for value in ("nan", "inf", "-inf"):
            self.assertEqual(economics.with_levers({"retirada": value}), economics.ASSUMPTIONS)

    def test_initial_cash_is_not_counted_twice(self):
        rep = economics.build_report()
        ramp = rep["rampa"]
        self.assertFalse(ramp["financiable"])
        self.assertAlmostEqual(ramp["financiacion_adicional"], -ramp["caja_minima"])
        funded = economics.build_report(saved={"caja_inicial": 8000})["rampa"]
        self.assertTrue(funded["financiable"])
        self.assertEqual(funded["financiacion_adicional"], 0)
        self.assertIn("adicionales", economics_docs._parte(rep))

    def test_negative_contribution_cannot_fit_the_founder_hours(self):
        rep = economics.build_report(saved={"precio": [0, 0, 0]})
        self.assertEqual(rep["cabe_en_horas"]["estado"], "sin_equilibrio")
        economics_docs.summary_docx(rep)
        economics_docs.summary_xlsx(rep)

    def test_zero_cost_is_observed_but_unknown_revenue_is_not_zero(self):
        rep = economics.build_report(observed={"paying_accounts": 2, "observed_cost_eur": 0})
        rows = rep["observado"]["filas"]
        self.assertIsNone(rows[0]["real"])
        self.assertEqual(rows[1]["real"], 0)
        self.assertIsNone(rows[2]["real"])

    def test_raising_the_draw_moves_only_the_third_step(self):
        base = economics.build_report()
        caro = economics.build_report({"retirada": "2000"})
        self.assertEqual(base["equilibrios"][0]["cuentas"],
                         caro["equilibrios"][0]["cuentas"])
        self.assertGreater(caro["equilibrios"][2]["cuentas"],
                           base["equilibrios"][2]["cuentas"])

    def test_less_support_per_account_raises_the_ceiling_without_selling_more(self):
        base = economics.build_report()
        ligero = economics.build_report({"soporte_medio": "9"})
        self.assertGreater(ligero["capacidad"]["techo"], base["capacidad"]["techo"])
        self.assertGreater(ligero["medias"]["contribucion_cargada"],
                           base["medias"]["contribucion_caja"] - 12)

    def test_observed_data_sits_beside_the_assumption_and_never_replaces_it(self):
        rep = economics.build_report(observed={
            "paying_accounts": 10, "mrr": 500.0, "observed_cost_eur": 60.0})
        self.assertTrue(rep["observado"]["hay_datos"])
        cuota = rep["observado"]["filas"][0]
        self.assertEqual(cuota["real"], 50.0)
        self.assertEqual(round(cuota["supuesto"], 2), 43.00)
        self.assertIsNotNone(cuota["desvio"])
        # Y el modelo sigue calculándose con el supuesto, no con el dato.
        self.assertEqual(round(rep["medias"]["arpu"], 2), 43.00)


class DocumentosOfimaticosTests(unittest.TestCase):
    """Word y Excel escritos con zipfile: Office no perdona un XML mal formado."""

    def setUp(self):
        self.rep = economics.build_report()

    def test_docx_is_a_valid_package_with_two_pages(self):
        blob = economics_docs.summary_docx(self.rep)
        with zipfile.ZipFile(__import__("io").BytesIO(blob)) as z:
            nombres = set(z.namelist())
            self.assertLessEqual({"[Content_Types].xml", "_rels/.rels",
                                  "word/document.xml", "word/styles.xml"}, nombres)
            documento = z.read("word/document.xml").decode("utf-8")
            ElementTree.fromstring(documento)  # revienta si el XML no es válido
            ElementTree.fromstring(z.read("word/styles.xml").decode("utf-8"))
        # Un solo salto de página: el documento son exactamente dos.
        self.assertEqual(documento.count('w:type="page"'), 1)
        self.assertIn("Los tres equilibrios", documento)
        self.assertIn("44", documento)

    def test_xlsx_is_a_valid_package_with_two_sheets(self):
        blob = economics_docs.summary_xlsx(self.rep)
        with zipfile.ZipFile(__import__("io").BytesIO(blob)) as z:
            nombres = set(z.namelist())
            self.assertLessEqual({"[Content_Types].xml", "_rels/.rels",
                                  "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
                                  "xl/styles.xml", "xl/worksheets/sheet1.xml",
                                  "xl/worksheets/sheet2.xml"}, nombres)
            for parte in nombres:
                if parte.endswith(".xml") or parte.endswith(".rels"):
                    ElementTree.fromstring(z.read(parte).decode("utf-8"))
            hoja = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("Los tres equilibrios", hoja)

    def test_text_is_escaped_so_a_quote_cannot_break_the_file(self):
        blob = officedocs.build_docx([("p", 'Cuentas & "margen" <alto>', "Normal")])
        with zipfile.ZipFile(__import__("io").BytesIO(blob)) as z:
            documento = z.read("word/document.xml").decode("utf-8")
        ElementTree.fromstring(documento)
        self.assertIn("&amp;", documento)
        self.assertNotIn("<alto>", documento)

    def test_xlsx_numbers_stay_numbers_and_text_stays_text(self):
        blob = officedocs.build_xlsx([{"nombre": "H", "anchos": [10], "filas": [
            [("texto", officedocs.S_TEXTO), (42.5, officedocs.S_EUR)],
        ]}])
        with zipfile.ZipFile(__import__("io").BytesIO(blob)) as z:
            hoja = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn('t="inlineStr"', hoja)
        self.assertIn("<v>42.5</v>", hoja)


class PanelEconomiaTests(unittest.TestCase):
    """La página y las descargas: solo administradores, y sin datos no revientan."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "test.db",
            BACKUP_DIR=Path(self.temp.name) / "backups",
            DOCS_PATH=Path(self.temp.name) / "docs")
        self.settings.start()
        db.init_db()
        self.business = db.create_business("Prueba", "test@example.com")["id"]

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()

    def _client(self):
        from starlette.testclient import TestClient

        from noesis.web import auth, server
        password = "test-only-password"  # pragma: allowlist secret
        db.create_user("admin@example.com", auth.hash_password(password), self.business)
        contexto = (patch.object(config, "ADMIN_EMAIL", "admin@example.com"),
                    patch.object(config, "ADMIN_REQUIRE_GOOGLE_OAUTH", False),
                    patch.object(server, "start_scheduler", lambda: None))
        return contexto, TestClient(server.app), password

    def test_page_and_downloads_require_an_admin_session(self):
        contexto, client, _ = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            for ruta in ("/admin/economia", "/admin/economia/resumen.docx",
                         "/admin/economia/resumen.xlsx"):
                respuesta = client.get(ruta, follow_redirects=False)
                self.assertEqual(respuesta.status_code, 303, ruta)
                self.assertEqual(respuesta.headers["location"], "/login")
            datos = client.get("/admin/economia/datos")
            self.assertEqual(datos.status_code, 403)

    def test_page_renders_and_says_what_is_not_measured(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            client.post("/login", data={"email": "admin@example.com",
                                        "password": password})
            page = client.get("/admin/economia")
            self.assertEqual(page.status_code, 200)
            self.assertIn("Los tres equilibrios", page.text)
            self.assertIn("44", page.text)
            # Con una cuenta de prueba y ninguna de pago, el aviso tiene que salir:
            # el hueco se dice, no se rellena con ceros disfrazados de dato.
            self.assertIn("Sin cuentas de pago", page.text)
            self.assertIn("todo escenario", page.text)
            # Y el coste real sigue vacío porque no hay facturas cargadas.
            self.assertIn("Del libro de costes", page.text)
        eventos = {e["event_type"] for e in db.list_security_events()}
        self.assertIn("admin.economia_viewed", eventos)

    def test_levers_travel_from_the_url_to_the_downloaded_document(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            client.post("/login", data={"email": "admin@example.com",
                                        "password": password})
            base = client.get("/admin/economia/datos").json()
            self.assertFalse(base["rampa"]["financiable"])
            self.assertGreater(base["rampa"]["financiacion_adicional"], 0)
            movido = client.get("/admin/economia/datos?retirada=2400").json()
            self.assertGreater(movido["equilibrios"][2]["cuentas"],
                               base["equilibrios"][2]["cuentas"])
            self.assertEqual(len(movido["rampa"]["filas"]), 36)

            descarga = client.get("/admin/economia/resumen.docx?retirada=2400")
            self.assertEqual(descarga.status_code, 200)
            self.assertIn("wordprocessingml", descarga.headers["content-type"])
            self.assertIn("attachment", descarga.headers["content-disposition"])
            with zipfile.ZipFile(__import__("io").BytesIO(descarga.content)) as z:
                documento = z.read("word/document.xml").decode("utf-8")
            # La retirada movida tiene que aparecer en el Word, no la de por defecto.
            self.assertIn("2", documento)
            self.assertIn(str(movido["equilibrios"][2]["cuentas"]), documento)

            hoja = client.get("/admin/economia/resumen.xlsx")
            self.assertEqual(hoja.status_code, 200)
            self.assertIn("spreadsheetml", hoja.headers["content-type"])
        eventos = {e["event_type"] for e in db.list_security_events()}
        self.assertIn("admin.economia_docx_downloaded", eventos)
        self.assertIn("admin.economia_xlsx_downloaded", eventos)

    def test_costs_can_be_edited_saved_and_change_every_number(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            client.post("/login", data={"email": "admin@example.com",
                                        "password": password})
            page = client.get("/admin/economia")
            self.assertIn("eco-form", page.text)
            self.assertIn("Los costes y los supuestos", page.text)
            # Todos los campos del catálogo se pintan, incluidos los tres de cada
            # supuesto por plan: un campo que la web no enseña no se puede corregir.
            esperados = sum(3 if spec["tipo"] == "plan" else 1
                            for spec in economics.EDITABLE.values())
            self.assertEqual(page.text.count('type="number"'), esperados)

            antes = economics.build_report()["equilibrios"][2]["cuentas"]
            client.post("/admin/economia/supuestos", data={
                "gestoria": "145", "retirada": "1800", "seguro": "45",
                "precio": ["39", "59", "119"]})
            guardado = db.economy_assumptions()
            self.assertEqual(guardado["gestoria"], 145.0)
            self.assertEqual(guardado["precio"], [39.0, 59.0, 119.0])

            # Y lo guardado manda en todo: página, modelo y descargas.
            datos = client.get("/admin/economia/datos").json()
            self.assertEqual(round(datos["medias"]["arpu"], 2), 54.00)
            self.assertNotEqual(datos["equilibrios"][2]["cuentas"], antes)
            despues = client.get("/admin/economia")
            self.assertIn("54", despues.text)
            with zipfile.ZipFile(__import__("io").BytesIO(
                    client.get("/admin/economia/resumen.xlsx").content)) as z:
                hoja = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
            self.assertIn("<v>39.0</v>", hoja)
        eventos = {e["event_type"] for e in db.list_security_events()}
        self.assertIn("admin.economia_assumptions_saved", eventos)

    def test_a_bad_value_is_ignored_instead_of_breaking_the_save(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            client.post("/login", data={"email": "admin@example.com",
                                        "password": password})
            client.post("/admin/economia/supuestos", data={"gestoria": "145"})
            # Una coma de más en un campo no debe tumbar el resto del guardado ni
            # borrar lo que ya estaba bien.
            client.post("/admin/economia/supuestos", data={
                "gestoria": "no-es-un-numero", "seguro": "55"})
            guardado = db.economy_assumptions()
            self.assertEqual(guardado["gestoria"], 145.0)
            self.assertEqual(guardado["seguro"], 55.0)
            # Un valor fuera de rango se acota, no se rechaza en silencio.
            client.post("/admin/economia/supuestos", data={"retirada": "999999"})
            self.assertEqual(db.economy_assumptions()["retirada"],
                             economics.EDITABLE["retirada"]["max"])
            # Y una clave que no existe no entra en la tabla.
            client.post("/admin/economia/supuestos", data={"lo_que_sea": "3"})
            self.assertNotIn("lo_que_sea", db.economy_assumptions())

    def test_going_back_to_the_factory_value_deletes_the_row(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            client.post("/login", data={"email": "admin@example.com",
                                        "password": password})
            client.post("/admin/economia/supuestos", data={"gestoria": "145"})
            self.assertIn("gestoria", db.economy_assumptions())
            defecto = economics.ASSUMPTIONS["gestoria"]
            client.post("/admin/economia/supuestos", data={"gestoria": str(defecto)})
            # No se guarda una copia del valor de fábrica: la tabla solo dice lo
            # que está tocado de verdad.
            self.assertNotIn("gestoria", db.economy_assumptions())

    def test_restore_returns_everything_to_factory(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            client.post("/login", data={"email": "admin@example.com",
                                        "password": password})
            client.post("/admin/economia/supuestos", data={
                "gestoria": "145", "retirada": "1800"})
            self.assertEqual(len(db.economy_assumptions()), 2)
            client.post("/admin/economia/restaurar")
            self.assertEqual(db.economy_assumptions(), {})
            datos = client.get("/admin/economia/datos").json()
            self.assertEqual(datos["equilibrios"][2]["cuentas"], 44)
        eventos = {e["event_type"] for e in db.list_security_events()}
        self.assertIn("admin.economia_assumptions_reset", eventos)

    def test_saving_and_restoring_require_an_admin_session(self):
        contexto, client, _ = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            for ruta in ("/admin/economia/supuestos", "/admin/economia/restaurar"):
                respuesta = client.post(ruta, data={"gestoria": "1"},
                                        follow_redirects=False)
                self.assertEqual(respuesta.status_code, 303, ruta)
                self.assertEqual(respuesta.headers["location"], "/login")
            self.assertEqual(db.economy_assumptions(), {})

    def test_a_broken_mix_is_flagged_instead_of_silently_skewing_the_average(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            client.post("/login", data={"email": "admin@example.com",
                                        "password": password})
            respuesta = client.post("/admin/economia/supuestos",
                                    data={"mix": ["0.5", "0.5", "0.5"]})
            self.assertIn("100", respuesta.text)
            self.assertIn("mezcla de planes", respuesta.text.lower())
            self.assertNotIn("mix", db.economy_assumptions())
            self.assertEqual(economics.build_report(saved={"mix": [0.5, 0.5, 0.5]})[
                "assumptions"]["mix"], economics.ASSUMPTIONS["mix"])

    def test_timeline_marks_what_it_cannot_know_instead_of_guessing(self):
        serie = db.economy_timeline(12)
        self.assertEqual(len(serie["filas"]), 12)
        # Hay una cuenta (la del setUp) pero ninguna factura de coste cargada:
        # el coste queda en None, no en cero, que sería mentir.
        self.assertTrue(serie["hay_cuentas"])
        self.assertFalse(serie["hay_costes"])
        self.assertIsNone(serie["filas"][-1]["coste"])
        self.assertIsNone(serie["filas"][-1]["coste_por_cuenta"])
        self.assertEqual(serie["filas"][-1]["de_pago"], 0)
        # Y un coste cargado sí aparece, con su mes.
        mes = serie["filas"][-1]["mes"]
        db.add_platform_cost(mes, "hosting", "80", source="actual", note="")
        con_coste = db.economy_timeline(12)
        self.assertTrue(con_coste["hay_costes"])
        self.assertEqual(con_coste["filas"][-1]["coste"], 80.0)

    def test_timeline_range_is_clamped(self):
        self.assertEqual(len(db.economy_timeline(0)["filas"]), 1)
        self.assertEqual(len(db.economy_timeline(999)["filas"]), 36)

    def test_timeline_keeps_older_accounts_and_does_not_invent_history(self):
        with db.get_conn() as conn:
            conn.execute("UPDATE businesses SET created_at=?, subscription_status='active' WHERE id=?",
                         ("2020-01-01", self.business))
        rows = db.economy_timeline(2)["filas"]
        self.assertEqual([r["cuentas"] for r in rows], [1, 1])
        self.assertIsNone(rows[0]["de_pago"])
        self.assertEqual(rows[-1]["de_pago"], 1)
        self.assertTrue(all(r["mrr"] is None and r["margen"] is None for r in rows))

    def test_timeline_excludes_forecast_costs(self):
        month = db.economy_timeline(1)["filas"][0]["mes"]
        db.add_platform_cost(month, "hosting", "90", source="forecast", note="")
        self.assertIsNone(db.economy_timeline(1)["filas"][0]["coste"])
        db.add_platform_cost(month, "hosting", "20", source="actual", note="")
        self.assertEqual(db.economy_timeline(1)["filas"][0]["coste"], 20)

    def test_timeline_connections_include_older_real_but_not_demo_accounts(self):
        demo = db.create_business("Demo", "demo@example.com")["id"]
        with db.get_conn() as conn:
            conn.execute("UPDATE businesses SET is_demo=1 WHERE id=?", (demo,))
        db.create_whatsapp_connection(self.business, waba_id="123456", phone_number_id="111111")
        db.create_whatsapp_connection(demo, waba_id="654321", phone_number_id="222222")
        with db.get_conn() as conn:
            conn.execute("UPDATE whatsapp_connections SET created_at=?", ("2020-01-01",))
        self.assertEqual(db.economy_timeline(1)["filas"][0]["conexiones"], 1)

    def test_saved_churn_survives_page_json_and_downloads(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            client.post("/login", data={"email": "admin@example.com", "password": password})
            client.post("/admin/economia/supuestos", data={"churn_nuevo": "0.25"})
            expected = economics.build_report(saved={"churn_nuevo": 0.25})
            payload = client.get("/admin/economia/datos").json()
            self.assertAlmostEqual(payload["vida_media"], expected["vida_media"])
            self.assertEqual(client.get("/admin/economia").status_code, 200)
            with zipfile.ZipFile(__import__("io").BytesIO(
                    client.get("/admin/economia/resumen.xlsx").content)) as archive:
                self.assertIn("<v>0.25</v>", archive.read("xl/worksheets/sheet2.xml").decode())

    def test_http_server_login_page_and_json(self):
        import socket
        import threading
        import time

        import httpx
        import uvicorn
        from noesis.web import server

        contexto, _, password = self._client()
        with contexto[0], contexto[1], contexto[2], socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            app_server = uvicorn.Server(uvicorn.Config(server.app, log_level="error"))
            thread = threading.Thread(target=app_server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 10
                while not app_server.started and thread.is_alive() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(app_server.started)
                with httpx.Client(base_url=f"http://127.0.0.1:{listener.getsockname()[1]}") as client:
                    self.assertEqual(client.get("/health").status_code, 200)
                    login = client.post("/login", data={"email": "admin@example.com", "password": password})
                    self.assertEqual(login.status_code, 303)
                    self.assertEqual(client.get("/admin/economia").status_code, 200)
                    self.assertFalse(client.get("/admin/economia/datos").json()["rampa"]["financiable"])
            finally:
                app_server.should_exit = True
                thread.join(10)
                self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
