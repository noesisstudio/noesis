"""La baja de una cuenta tiene que borrar de verdad, no dar un error interno.

Una cuenta con WhatsApp conectado no se podía dar de baja: la tabla de conexiones
no entraba en el borrado y la clave foránea rechazaba la operación, así que tanto
el titular como el admin veían un error interno. La primera prueba es estructural
a propósito: recorre el esquema y exige que **toda** tabla con `business_id` esté
cubierta, para que una tabla nueva no vuelva a romper la baja en silencio.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from noesis import config, db

RAIZ = Path(__file__).resolve().parents[1]


def _tablas_del_borrado() -> set[str]:
    fuente = (RAIZ / "src" / "noesis" / "db.py").read_text(encoding="utf-8")
    bloque = fuente[fuente.index("def delete_business_cascade"):]
    bloque = bloque[:bloque.index("return True")]
    return set(re.findall(r'"([a-z_]+)"', bloque))


class AccountDeletionTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_docs_path = config.DOCS_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.DOCS_PATH = self.original_docs_path
        config.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    def test_every_table_with_business_data_is_covered_by_the_deletion(self):
        """Estructural: ninguna tabla con `business_id` puede quedarse fuera."""
        cubiertas = _tablas_del_borrado()
        sin_cubrir = []
        with db.get_conn() as conn:
            tablas = [fila["name"] for fila in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()]
            for tabla in tablas:
                columnas = [c["name"] for c in conn.execute(
                    f"PRAGMA table_info({tabla})").fetchall()]
                if "business_id" not in columnas:
                    continue
                # `users` se borra aparte, al final y por su propia consulta.
                if tabla in cubiertas or tabla == "users":
                    continue
                claves = conn.execute(
                    f"PRAGMA foreign_key_list({tabla})").fetchall()
                a_negocios = [c for c in claves if c["table"] == "businesses"]
                # Con ON DELETE CASCADE la base de datos ya se encarga.
                if a_negocios and a_negocios[0]["on_delete"] == "CASCADE":
                    continue
                sin_cubrir.append(tabla)
        self.assertEqual(
            sin_cubrir, [],
            "Estas tablas guardan datos de un negocio y no las borra "
            f"delete_business_cascade, así que la baja fallará: {sin_cubrir}. "
            "Añádelas a la lista respetando el orden de claves foráneas.",
        )

    def _cuenta_como_la_de_un_cliente(self) -> int:
        """Una cuenta con lo que tiene cualquiera: WhatsApp, equipo y papeles."""
        business = db.create_business("Reformas Norte", "norte@example.com")
        bid = business["id"]
        cliente = db.add_client("Hotel Mar", business_id=bid)
        db.add_expense("Material", 50, business_id=bid)
        db.add_invoice(cliente["id"], "Reforma", 100, vat_rate=21,
                       business_id=bid)  # borrador: no bloquea la baja
        proveedor = db.add_supplier("Suministros Pepe", business_id=bid)
        db.add_received_invoice(121, supplier_id=proveedor["id"],
                                business_id=bid)
        ahora = db._now()
        with db.get_conn() as conn:
            conexion = conn.execute(
                "INSERT INTO whatsapp_connections (business_id, waba_id, "
                "phone_number_id, created_at, updated_at) "
                "VALUES (?, 'WABA-1', 'PHONE-1', ?, ?) RETURNING id",
                (bid, ahora, ahora),
            ).fetchone()["id"]
            contacto = conn.execute(
                "INSERT INTO whatsapp_contacts (business_id, connection_id, "
                "wa_id, phone_norm, created_at, updated_at) "
                "VALUES (?, ?, '34600111222', '34600111222', ?, ?) "
                "RETURNING id", (bid, conexion, ahora, ahora),
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO whatsapp_conversations (business_id, connection_id, "
                "contact_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (bid, conexion, contacto, ahora, ahora),
            )
            conn.execute(
                "INSERT INTO access_requests (name, email, status, created_at, "
                "business_id) VALUES ('Ana', 'ana@example.com', 'alta', ?, ?)",
                (ahora, bid),
            )
        return bid

    def test_an_account_with_whatsapp_connected_can_be_deleted(self):
        bid = self._cuenta_como_la_de_un_cliente()
        self.assertTrue(db.delete_business_cascade(bid))
        self.assertIsNone(db.get_business(bid))
        with db.get_conn() as conn:
            for tabla in ("whatsapp_connections", "whatsapp_contacts",
                          "whatsapp_conversations", "access_requests",
                          "clients", "expenses", "received_invoices"):
                quedan = conn.execute(
                    f"SELECT COUNT(*) AS total FROM {tabla} WHERE business_id=?",
                    (bid,)).fetchone()["total"]
                self.assertEqual(quedan, 0, f"quedan filas en {tabla}")

    def test_deleting_one_account_never_touches_another(self):
        victima = self._cuenta_como_la_de_un_cliente()
        otra = db.create_business("Limpiezas Sur", "sur@example.com")
        db.add_client("Cliente ajeno", business_id=otra["id"])
        db.delete_business_cascade(victima)
        self.assertIsNotNone(db.get_business(otra["id"]))
        self.assertEqual(len(db.list_clients(otra["id"])), 1)

    def test_an_account_with_issued_invoices_asks_for_the_legal_closure(self):
        """Una factura emitida no se borra: eso sigue siendo una obligación."""
        business = db.create_business("Con facturas", "facturas@example.com")
        db.update_fiscal(business["id"], nif="B11111111",
                         address="Calle Uno 1, 08001 Barcelona")
        cliente = db.add_client("Hotel Mar", nif="B22222229",
                                address="Calle Dos 2, 08002 Barcelona",
                                business_id=business["id"])
        factura = db.add_invoice(cliente["id"], "Reforma", 100, vat_rate=21,
                                 business_id=business["id"])
        db.issue_invoice(factura["id"], business_id=business["id"])
        with self.assertRaises(ValueError):
            db.delete_business_cascade(business["id"])
        self.assertIsNotNone(db.get_business(business["id"]))


if __name__ == "__main__":
    unittest.main()
