"""Los números de la página: que el gráfico no mienta.

1. Que el embudo no se vacíe cuando alguien se duerme: quien contestó y luego
   dijo «ahora no» sigue habiendo contestado.
2. Que las bajas no cuenten en ningún gráfico.
3. Que mil gestorías no den por cubierto el objetivo de cuarenta autónomos.
4. Que la tanda solo proponga a quien se puede escribir y aún no se ha escrito.
"""
import unittest
from datetime import date, timedelta

from noesis import sales
from noesis.crm import panel


def ficha(numero, **campos):
    base = {"id": numero, "nombre": f"Gestoria {numero}", "tipo": "gestoria",
            "estado": "lista", "baja": False, "provincia": "Lleida",
            "email": f"info@g{numero}.cat", "siguiente_el": None}
    return {**base, **campos}


def toque(prospect_id, estado_despues=None, fecha=None):
    return {"prospect_id": prospect_id, "canal": "email",
            "estado_despues": estado_despues,
            "fecha": fecha or date.today().isoformat()}


class EmbudoTests(unittest.TestCase):
    def test_each_step_counts_everyone_who_got_that_far(self):
        fichas = [ficha(1), ficha(2, estado="contactado"),
                  ficha(3, estado="hablado"), ficha(4, estado="piloto"),
                  ficha(5, estado="cliente")]
        embudo = {p["clave"]: p["hay"] for p in panel.panel(fichas, [])["embudo"]}
        self.assertEqual(embudo, {"lista": 5, "contactado": 4, "respuesta": 3,
                                  "piloto": 2, "cliente": 1})

    def test_going_to_sleep_does_not_undo_having_answered(self):
        fichas = [ficha(1, estado="dormido"), ficha(2, estado="descartado")]
        toques = [toque(1, "contactado"), toque(1, "hablado"), toque(1, "dormido"),
                  toque(2, "contactado"), toque(2, "descartado")]
        resultado = panel.panel(fichas, toques)
        embudo = {p["clave"]: p["hay"] for p in resultado["embudo"]}
        self.assertEqual((embudo["contactado"], embudo["respuesta"]), (2, 1))
        self.assertEqual(resultado["cerrados"]["dormido"], 1)
        self.assertEqual(resultado["cerrados"]["descartado"], 1)

    def test_a_note_without_a_state_change_still_counts_as_contact(self):
        embudo = panel.panel([ficha(1)], [toque(1)])["embudo"]
        self.assertEqual(embudo[1]["hay"], 1)

    def test_opt_outs_are_in_no_chart(self):
        fichas = [ficha(1), ficha(2, estado="descartado", baja=True)]
        resultado = panel.panel(fichas, [toque(2, "contactado")])
        self.assertEqual(resultado["total"], 1)
        self.assertEqual(resultado["embudo"][1]["hay"], 0)
        self.assertEqual(resultado["cerrados"]["bajas"], 1)
        self.assertEqual(resultado["contactos_semanas"], 0)

    def test_the_answer_rate_is_over_those_contacted_not_over_the_list(self):
        fichas = [ficha(n) for n in range(1, 9)] + [
            ficha(9, estado="contactado"), ficha(10, estado="hablado")]
        cifras = {c["clave"]: c for c in panel.panel(fichas, [])["cifras"]}
        self.assertEqual(cifras["contactado"]["valor"], 2)
        self.assertEqual(cifras["respuesta"]["valor"], 1)
        self.assertIn("50 %", cifras["respuesta"]["nota"])
        self.assertIn("8 sin contactar", cifras["lista"]["nota"])

    def test_an_empty_list_draws_nothing_and_divides_by_nothing(self):
        vacio = panel.panel([], [])
        self.assertEqual(vacio["total"], 0)
        self.assertEqual([p["hay"] for p in vacio["embudo"]], [0] * 5)
        self.assertEqual(vacio["provincias"], [])


class ZonasYRitmoTests(unittest.TestCase):
    def test_each_province_splits_into_what_is_done_and_what_is_left(self):
        fichas = [ficha(1), ficha(2, estado="contactado"),
                  ficha(3, estado="cita"), ficha(4, estado="dormido"),
                  ficha(5, provincia="Girona"), ficha(6, provincia=None)]
        zonas = {z["nombre"]: z for z in panel.panel(fichas, [])["provincias"]}
        lleida = zonas["Lleida"]
        self.assertEqual((lleida["total"], lleida["sin"], lleida["contactados"],
                          lleida["respuesta"], lleida["cerrados"]), (4, 1, 1, 1, 1))
        self.assertEqual(lleida["ancho"], 100)
        self.assertEqual(sum(t["hay"] for t in lleida["tramos"]), 4)
        self.assertEqual(zonas["Sin provincia"]["total"], 1)

    def test_the_tail_of_provinces_folds_into_one_bar(self):
        fichas = [ficha(n, provincia=f"Provincia {n % 14}") for n in range(1, 60)]
        zonas = panel.panel(fichas, [])["provincias"]
        self.assertEqual(len(zonas), panel.PROVINCIAS_PANEL + 1)
        self.assertTrue(zonas[-1]["nombre"].startswith("Otras "))
        self.assertEqual(sum(z["total"] for z in zonas), 59)

    def test_contacts_land_in_their_monday_to_sunday_week(self):
        hoy = date(2026, 10, 7)                      # miércoles
        toques = [toque(1, "contactado", "2026-10-05"),   # lunes de esta semana
                  toque(1, None, "2026-10-04"),           # domingo: la anterior
                  toque(1, None, "2026-01-01")]           # fuera de las 12
        semanas = panel.panel([ficha(1)], toques, hoy=hoy)["semanas"]
        self.assertEqual(len(semanas), panel.SEMANAS_PANEL)
        self.assertEqual(semanas[-1]["inicio"], "2026-10-05")
        self.assertTrue(semanas[-1]["actual"])
        self.assertEqual((semanas[-1]["hay"], semanas[-2]["hay"]), (1, 1))
        self.assertEqual(sum(s["hay"] for s in semanas), 2)

    def test_due_today_ignores_closed_cards(self):
        ayer = (date.today() - timedelta(days=1)).isoformat()
        fichas = [ficha(1, estado="contactado", siguiente_el=ayer),
                  ficha(2, estado="dormido", siguiente_el=ayer),
                  ficha(3, estado="contactado",
                        siguiente_el=(date.today() + timedelta(days=3)).isoformat())]
        cifras = {c["clave"]: c["valor"] for c in panel.panel(fichas, [])["cifras"]}
        self.assertEqual(cifras["hoy"], 1)


class ObjetivoTests(unittest.TestCase):
    def test_a_thousand_offices_do_not_cover_the_forty_names(self):
        fichas = [ficha(n) for n in range(1, 60)]
        fichas.append(ficha(99, tipo="autonomo", nombre="Jordi"))
        resumen = sales.resumen(fichas)
        self.assertEqual(resumen["embudo"][0]["hay"], 1)
        self.assertEqual(resumen["embudo"][0]["falta"], 39)

    def test_looking_only_at_offices_talks_about_batches_not_pilots(self):
        fichas = [ficha(1), ficha(2, provincia="Girona"),
                  ficha(3, provincia="Girona")]
        parte = sales.resumen(fichas)["parte"]
        self.assertIn("3 sin escribir", parte)
        self.assertIn("Girona", parte)
        self.assertNotIn("40", parte)

    def test_an_office_waits_a_week_and_a_tradesman_three_days(self):
        lunes = date(2026, 10, 5)
        self.assertEqual(sales.siguiente_fecha("contactado", lunes, "gestoria"),
                         "2026-10-12")
        self.assertEqual(sales.siguiente_fecha("contactado", lunes, "autonomo"),
                         "2026-10-08")
        self.assertEqual(sales.siguiente_fecha("contactado", lunes), "2026-10-08")

    def test_an_office_gets_the_office_script_whatever_its_source(self):
        p = sales.enriquecer(ficha(1, origen="web"))
        self.assertEqual(p["guiones"], ["gestoria_pregunta"])
        self.assertEqual(p["lengua"], "ca")
        self.assertEqual(sales.enriquecer(ficha(2, provincia="Huesca"))["lengua"],
                         "es")


class TableroYTandaTests(unittest.TestCase):
    def _enriquecidas(self, fichas):
        return [sales.enriquecer(f) for f in fichas]

    def test_one_column_per_state_with_the_due_ones_on_top(self):
        ayer = (date.today() - timedelta(days=1)).isoformat()
        fichas = self._enriquecidas(
            [ficha(n, estado="contactado", nombre=f"B{n}") for n in range(1, 10)]
            + [ficha(50, estado="contactado", nombre="Zeta", siguiente_el=ayer)])
        columnas = {c["clave"]: c for c in panel.tablero(fichas)}
        self.assertEqual(list(columnas), list(sales.ESTADOS))
        contactado = columnas["contactado"]
        self.assertEqual(contactado["hay"], 10)
        self.assertEqual(len(contactado["tarjetas"]), panel.TARJETAS_POR_COLUMNA)
        self.assertEqual(contactado["mas"], 4)
        self.assertEqual(contactado["tarjetas"][0]["nombre"], "Zeta")
        self.assertEqual(columnas["cita"]["hay"], 0)

    def test_opt_outs_are_not_on_the_board(self):
        fichas = self._enriquecidas([ficha(1, estado="descartado", baja=True)])
        self.assertEqual(sum(c["hay"] for c in panel.tablero(fichas)), 0)

    def test_the_batch_is_ten_unwritten_with_an_address_from_one_zone(self):
        fichas = [ficha(n) for n in range(1, 20)]
        fichas += [ficha(30, email=None), ficha(31, estado="contactado"),
                   ficha(32, baja=True), ficha(33, provincia="Girona")]
        tanda = panel.tanda(fichas, "Lleida")
        self.assertEqual(len(tanda), 10)
        self.assertTrue(all(p["provincia"] == "Lleida" and p["email"]
                            and p["estado"] == "lista" for p in tanda))
        self.assertNotIn(32, [p["id"] for p in panel.tanda(fichas, "Lleida", 99)])

    def test_verified_addresses_go_first(self):
        fichas = [ficha(1, nombre="Aaa"), ficha(2, nombre="Zzz",
                                                correo_verificacion="Buzón existe")]
        self.assertEqual(panel.tanda(fichas, "Lleida")[0]["id"], 2)

    def test_zones_are_ordered_by_what_is_left_to_write(self):
        fichas = [ficha(1), ficha(2, provincia="Girona"),
                  ficha(3, provincia="Girona"),
                  ficha(4, provincia="Huesca", estado="contactado")]
        self.assertEqual(panel.zonas_pendientes(fichas),
                         [{"nombre": "Girona", "hay": 2},
                          {"nombre": "Lleida", "hay": 1}])

    def test_the_filter_ignores_accents_and_case(self):
        fichas = [ficha(1, nombre="Assessoria Güell", poblacion="Tàrrega"),
                  ficha(2, estado="contactado"), ficha(3, tipo="autonomo")]
        self.assertEqual([p["id"] for p in panel.filtrar(fichas, busca="guell")], [1])
        self.assertEqual([p["id"] for p in panel.filtrar(fichas, busca="TARREGA")],
                         [1])
        self.assertEqual([p["id"] for p in panel.filtrar(fichas, tipo="autonomo")],
                         [3])
        self.assertEqual(
            [p["id"] for p in panel.filtrar(fichas, estado="contactado")], [2])

    def test_pages_never_fall_off_the_end(self):
        pagina = panel.paginar(list(range(120)), 99)
        self.assertEqual((pagina["pagina"], pagina["paginas"]), (3, 3))
        self.assertEqual((pagina["desde"], pagina["hasta"]), (101, 120))
        self.assertEqual(panel.paginar([], 1)["desde"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
