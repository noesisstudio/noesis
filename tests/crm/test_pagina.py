"""La página visual del CRM y sus rutas.

1. Que nada de `/admin/crm` se abra sin ser administrador, y que la única
   dirección sin sesión —la que lee la hoja— no se abra sin su clave.
2. Que conectar la hoja la lea, y que si no está compartida se diga cómo
   arreglarlo en vez de fallar.
3. Que apuntar una tanda dos veces no apunte dos correos.
4. Que mover una tarjeta deje rastro, y que a quien pidió la baja no se le mueva.
"""
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from noesis import config, db
from noesis.crm import google, sincronizar

from .base import ENLACE, HOJA, ConBase


class PaginaTests(ConBase):
    def setUp(self):
        super().setUp()
        self.business = db.create_business("Bynoesis", "test@example.com")["id"]

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

    def _con_hoja(self):
        hoja = sincronizar.connect_sheet(url=ENLACE, nombre="Gestorías")
        sincronizar.leer_hoja(hoja["id"], texto=HOJA)
        return hoja

    def test_every_new_route_requires_an_admin_session(self):
        contexto, client, _ = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            for ruta in ("/admin/crm/hoja/conectar", "/admin/crm/hoja/1/leer",
                         "/admin/crm/hoja/1/desconectar", "/admin/crm/hoja/enlace",
                         "/admin/crm/hoja/enlace/anular", "/admin/crm/tanda",
                         "/admin/crm/1/eliminar"):
                respuesta = client.post(ruta, data={}, follow_redirects=False)
                self.assertEqual(respuesta.status_code, 303, ruta)
                self.assertEqual(respuesta.headers["location"], "/login")
            mover = client.post("/admin/crm/1/mover", data={"estado": "cita"})
            self.assertEqual(mover.status_code, 401)
            self.assertEqual(sincronizar.list_sheets(), [])

    def test_the_page_draws_the_charts_the_board_and_the_batch(self):
        self._con_hoja()
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            pagina = client.get("/admin/crm?tipo=gestoria")
            self.assertEqual(pagina.status_code, 200)
            for trozo in ("Cómo va la captación", "El embudo", "Por provincia",
                          "Tablero", "Siguiente tanda", "Ver como tabla",
                          "Gestoria Pons", "Hoja de Google",
                          "/static/crm/crm.js", "/static/crm/crm.css"):
                self.assertIn(trozo, pagina.text, trozo)
            # Un apartado por sección, y cada pestaña apunta a un ancla que existe:
            # sin script, la barra sigue sirviendo de índice.
            for ancla in ("resumen", "tablero", "hoy", "lista", "hoja", "importar"):
                self.assertIn(f'href="#{ancla}"', pagina.text)
                self.assertIn(f'id="{ancla}"', pagina.text)
            self.assertEqual(pagina.text.count("data-crm-pestana="), 7)
            # La pestaña de la ficha solo se enseña con una ficha abierta.
            self.assertIn('data-crm-ir="ficha" hidden', pagina.text)
            # El script de la demo no se carga nunca en la app de verdad.
            self.assertNotIn("demo.js", pagina.text)
            # El objetivo de 40 nombres es de autónomos: aquí no pinta nada.
            self.assertNotIn("El objetivo con autónomos", pagina.text)
            self.assertEqual(pagina.headers["cache-control"], "no-store")

    def test_the_view_by_kind_only_shows_that_kind(self):
        self._con_hoja()
        db.add_prospect(nombre="Jordi Mas", telefono="600112233", tipo="autonomo")
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            autonomos = client.get("/admin/crm?tipo=autonomo").text
            self.assertIn("Jordi Mas", autonomos)
            self.assertNotIn("Gestoria Pons", autonomos)
            self.assertIn("El objetivo con autónomos", autonomos)
            filtrada = client.get("/admin/crm?tipo=gestoria&q=riera").text
            self.assertIn("Assessoria Riera", filtrada.split('id="lista"')[1]
                          .split('id="hoja"')[0])
            self.assertNotIn("Asesoría Ebro", filtrada.split('id="lista"')[1]
                             .split('id="hoja"')[0])
            # Un tipo inventado no rompe la página: se ignora.
            self.assertEqual(client.get("/admin/crm?tipo=<x>&pagina=zz").status_code,
                             200)

    def test_connecting_a_sheet_reads_it(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client, \
                patch.object(google, "descargar", return_value=HOJA):
            self._entrar(client, password)
            respuesta = client.post("/admin/crm/hoja/conectar", data={
                "url": ENLACE, "nombre": "Gestorías", "tipo": "gestoria"},
                follow_redirects=True)
            self.assertIn("Hoja conectada", respuesta.text)
            self.assertEqual(len(db.list_prospects()), 3)

    def test_a_sheet_that_is_not_shared_stays_connected_and_says_how_to_fix_it(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client, \
                patch.object(google, "descargar",
                             side_effect=google.HojaNoCompartida(
                                 "Pulsa «Compartir» y elige el enlace.")):
            self._entrar(client, password)
            respuesta = client.post("/admin/crm/hoja/conectar", data={
                "url": ENLACE, "tipo": "gestoria"}, follow_redirects=True)
            self.assertIn("Pulsa «Compartir»", respuesta.text)
            self.assertEqual(len(sincronizar.list_sheets()), 1)
            self.assertEqual(db.list_prospects(), [])

    def test_a_link_that_is_not_a_google_sheet_connects_nothing(self):
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client, \
                patch.object(google, "descargar") as descargar:
            self._entrar(client, password)
            respuesta = client.post("/admin/crm/hoja/conectar", data={
                "url": "https://evil.example/hoja"}, follow_redirects=True)
            self.assertIn("docs.google.com", respuesta.text)
            self.assertEqual(sincronizar.list_sheets(), [])
            descargar.assert_not_called()

    def test_the_feed_opens_with_its_key_and_only_with_it(self):
        self._con_hoja()
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            # Sin clave y sin sesión: como si no existiera.
            self.assertEqual(client.get("/admin/crm/feed/loquesea.csv").status_code,
                             404)
            self._entrar(client, password)
            pagina = client.post("/admin/crm/hoja/enlace", data={},
                                 follow_redirects=True).text
            self.assertIn("=IMPORTDATA(", pagina)
            ruta = "/admin/crm/feed/" + pagina.split("/admin/crm/feed/")[1].split(
                ".csv")[0] + ".csv"
            # La fórmula se enseña una vez: al recargar ya no está.
            self.assertNotIn("=IMPORTDATA(&#34;", client.get("/admin/crm").text)
            client.post("/logout")
            tabla = client.get(ruta)
            self.assertEqual(tabla.status_code, 200)
            self.assertIn("text/csv", tabla.headers["content-type"])
            self.assertEqual(tabla.headers["cache-control"], "no-store")
            self.assertIn("noindex", tabla.headers["x-robots-tag"])
            self.assertTrue(tabla.text.startswith("EMPRESA,CORREO"))
            self.assertIn("Gestoria Pons", tabla.text)
            self._entrar(client, password)
            client.post("/admin/crm/hoja/enlace/anular", data={})
            self.assertEqual(client.get(ruta).status_code, 404)

    def test_marking_a_batch_writes_it_once(self):
        self._con_hoja()
        ids = [p["id"] for p in db.list_prospects()][:2]
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            datos = {"ids": [str(i) for i in ids], "zona": "Lleida",
                     "vista": "gestoria", "fecha": "2026-10-02", "informado": "si"}
            primera = client.post("/admin/crm/tanda", data=datos,
                                  follow_redirects=False)
            self.assertEqual(primera.headers["location"],
                             "/admin/crm?tipo=gestoria&zona=Lleida#tanda")
            client.post("/admin/crm/tanda", data=datos)
            for ficha_id in ids:
                ficha = db.get_prospect(ficha_id)
                self.assertEqual(ficha["estado"], "contactado")
                # Una semana desde el día del envío, no desde hoy.
                self.assertEqual(ficha["siguiente_el"], "2026-10-09")
                self.assertEqual(ficha["informado_el"], "2026-10-02")
                self.assertEqual(len(db.list_sales_touches(ficha_id)), 1)

    def test_an_empty_batch_changes_nothing(self):
        self._con_hoja()
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            respuesta = client.post("/admin/crm/tanda", data={"zona": "Lleida"},
                                    follow_redirects=True)
            self.assertIn("No has marcado a nadie", respuesta.text)
            self.assertEqual(db.list_all_sales_touches(), [])

    def test_dragging_a_card_moves_it_and_leaves_a_note(self):
        ficha = db.add_prospect(nombre="Gestoria Pons", tipo="gestoria")
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            respuesta = client.post(f"/admin/crm/{ficha['id']}/mover",
                                    data={"estado": "cita"})
            self.assertEqual(respuesta.json()["estado"], "cita")
            self.assertEqual(db.get_prospect(ficha["id"])["siguiente_el"],
                             (date.today() + timedelta(days=1)).isoformat())
            self.assertEqual(db.list_sales_touches(ficha["id"])[0]["estado_despues"],
                             "cita")
            # Soltarla en su misma columna no apunta nada.
            client.post(f"/admin/crm/{ficha['id']}/mover", data={"estado": "cita"})
            self.assertEqual(len(db.list_sales_touches(ficha["id"])), 1)
            self.assertEqual(client.post(f"/admin/crm/{ficha['id']}/mover",
                                         data={"estado": "inventado"}).status_code,
                             404)

    def test_who_opted_out_cannot_be_dragged_back_in(self):
        ficha = db.add_prospect(nombre="Gestoria Pons", tipo="gestoria")
        db.prospect_opt_out(ficha["id"], "No")
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            respuesta = client.post(f"/admin/crm/{ficha['id']}/mover",
                                    data={"estado": "contactado"})
            self.assertEqual(respuesta.status_code, 409)
            self.assertEqual(db.get_prospect(ficha["id"])["estado"], "descartado")

    def test_erasing_from_the_page_keeps_them_out_of_the_next_reading(self):
        hoja = self._con_hoja()
        pons = next(p for p in db.list_prospects() if p["nombre"] == "Gestoria Pons")
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            client.post(f"/admin/crm/{pons['id']}/eliminar", data={})
            sincronizar.leer_hoja(hoja["id"], texto=HOJA)
            self.assertNotIn("Gestoria Pons",
                             [p["nombre"] for p in db.list_prospects()])

    def test_the_card_of_an_office_opens_in_its_language_with_the_subject(self):
        self._con_hoja()
        pons = next(p for p in db.list_prospects() if p["nombre"] == "Gestoria Pons")
        contexto, client, password = self._client()
        with contexto[0], contexto[1], contexto[2], client:
            self._entrar(client, password)
            pagina = client.get(f"/admin/crm?tipo=gestoria&contacto={pons['id']}").text
            self.assertIn('data-lengua="ca"', pagina)
            self.assertIn("una startup de Lleida per a gestories", pagina)
            self.assertIn("Viene de la hoja de Google", pagina)

    def test_the_daily_reading_claims_its_turn(self):
        from noesis.web import scheduler

        with patch.object(sincronizar, "leer_todas") as leer:
            scheduler.read_sales_sheets()
            scheduler.read_sales_sheets()
        self.assertEqual(leer.call_count, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
