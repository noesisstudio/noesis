"""Dar de alta a un cliente hablando, sin que se confunda con consultarlos.

«Crea el cliente Talleres Pino» listaba los clientes en vez de crearlo: la regla
de alta solo aceptaba artículo indeterminado («un cliente»), así que con «el»
caía en la regla de listar. Mientras hubo IA externa el fallo quedaba tapado;
cuando el proveedor se cayó, salió a la luz.
"""

from __future__ import annotations

import unittest

from noesis import nlu


class ClientSignupOrdersTestCase(unittest.TestCase):
    def test_the_usual_ways_of_asking_for_a_new_client_all_create_it(self):
        for frase in (
            "Crea el cliente Talleres Pino",
            "crea un cliente Talleres Pino",
            "Nuevo cliente Talleres Pino",
            "Añade el cliente Talleres Pino",
            "Alta de cliente Talleres Pino",
            "Crea un cliente que se llama Talleres Pino",
            "Da de alta a Talleres Pino como cliente",
            "dar de alta Talleres Pino como cliente",
        ):
            with self.subTest(frase=frase):
                self.assertEqual(
                    nlu.parse(frase), ("crear_cliente", {"nombre": "Talleres Pino"}),
                )

    def test_the_same_orders_work_for_a_supplier(self):
        for frase in (
            "Crea el proveedor Suministros Pepe",
            "Nuevo proveedor Suministros Pepe",
            "Da de alta a Suministros Pepe como proveedor",
        ):
            with self.subTest(frase=frase):
                self.assertEqual(
                    nlu.parse(frase),
                    ("crear_proveedor", {"nombre": "Suministros Pepe"}),
                )

    def test_asking_about_clients_still_only_lists_them(self):
        for frase in ("clientes", "¿Cuáles son mis clientes?",
                      "enseñame mis clientes", "lista de clientes"):
            with self.subTest(frase=frase):
                self.assertEqual(nlu.parse(frase), ("listar_clientes", {}))

    def test_the_word_client_is_never_part_of_the_name(self):
        """«factura para el cliente Marta» no da de alta a «el cliente Marta»."""
        for frase, esperado in (
            ("Crea una factura para el cliente Marta de 100 euros", "Marta"),
            ("presupuesto para la clienta Ana de 300 euros", "Ana"),
            ("factura a Marta por la caldera 120 euros", "Marta"),
        ):
            with self.subTest(frase=frase):
                resultado = nlu.parse(frase)
                self.assertIsNotNone(resultado, frase)
                self.assertEqual(resultado[1]["cliente"], esperado)


if __name__ == "__main__":
    unittest.main()
