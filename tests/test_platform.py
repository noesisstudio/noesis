"""Regresión de plataforma: dominios base, proyectos y memoria de Noesis."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from noesis import config, db, migrations
from noesis.web import chat


class _RecordingPGConn:
    """Conexión falsa con dialecto Postgres: registra las sentencias en el mismo
    orden en que las enviaría db.Connection (split de executescript por ';')."""

    dialect = "postgres"

    def __init__(self):
        self.statements: list[str] = []

    def execute(self, sql, params=()):
        self.statements.append(sql.strip())
        return self

    def executescript(self, script):
        for statement in script.split(";"):
            if statement.strip():
                self.statements.append(statement.strip())

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class PostgresDDLOrderTest(unittest.TestCase):
    """Guarda contra un bug que SQLite NO detecta: en Postgres una FK compuesta
    exige que la columna referida ya tenga índice único al crearse la FK. Este
    test simula el orden de sentencias del dialecto Postgres y lo comprueba."""

    # Uniques compuestos que ya existen del esquema inicial y migraciones previas.
    PREEXISTING = {("clients", ("business_id", "id")),
                   ("invoices", ("business_id", "id")),
                   ("expenses", ("business_id", "id")),
                   ("workers", ("business_id", "id")),
                   ("businesses", ("id",))}

    def test_composite_fks_have_unique_index_first(self):
        original = migrations._column_names
        migrations._column_names = lambda conn, table: []
        try:
            uniques = set(self.PREEXISTING)
            for version, name, upgrade, _down in migrations.MIGRATIONS:
                if version < 17:  # capa plataforma (los previos ya están en prod)
                    continue
                conn = _RecordingPGConn()
                upgrade(conn)
                for stmt in conn.statements:
                    mu = re.search(
                        r"UNIQUE INDEX (?:IF NOT EXISTS )?\w+\s+ON (\w+)\((.*?)\)",
                        stmt)
                    if mu:
                        cols = tuple(c.strip() for c in mu.group(2).split(","))
                        uniques.add((mu.group(1), cols))
                    for m in re.finditer(r"REFERENCES (\w+)\((.*?)\)", stmt):
                        cols = tuple(c.strip() for c in m.group(2).split(","))
                        if len(cols) == 2:
                            self.assertIn(
                                (m.group(1), cols), uniques,
                                f"Migración {version} ({name}): FK compuesta a "
                                f"{m.group(1)}{cols} sin índice único previo "
                                "(fallaría en Postgres).")
        finally:
            migrations._column_names = original


class PlatformTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_docs_path = config.DOCS_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "test.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()
        self.business = db.create_business("Obras Delta", "delta@example.com")
        self.other = db.create_business("Ajeno SL", "ajeno@example.com")
        self.bid = self.business["id"]

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.DOCS_PATH = self.original_docs_path
        config.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    # -------------------------------------------------------------- Productos
    def test_product_margin_only_with_cost(self):
        with_cost = db.add_product("Hora de obra", price=45, cost=20,
                                   business_id=self.bid)
        self.assertEqual(with_cost["margin"], 25.0)
        self.assertEqual(with_cost["margin_pct"], 55.6)
        without = db.add_product("Visita", price=30, business_id=self.bid)
        self.assertIsNone(without["margin"])
        self.assertIsNone(without["margin_pct"])

    def test_product_validation_and_isolation(self):
        db.add_product("Hora", price=40, business_id=self.bid)
        with self.assertRaises(ValueError):
            db.add_product("Hora", price=40, business_id=self.bid)
        with self.assertRaises(ValueError):
            db.add_product("Mal IVA", price=10, vat_rate=15,
                           business_id=self.bid)
        with self.assertRaises(ValueError):
            db.add_product("Negativo", price=-5, business_id=self.bid)
        self.assertEqual(db.list_products(self.other["id"]), [])

    def test_product_low_stock_and_deactivate(self):
        p = db.add_product("Tornillos", kind="producto", price=3, stock=2,
                           stock_alert=5, business_id=self.bid)
        self.assertTrue(p["low_stock"])
        db.update_product(p["id"], business_id=self.bid, active=False)
        self.assertEqual(db.list_products(self.bid), [])
        self.assertEqual(
            len(db.list_products(self.bid, include_inactive=True)), 1)
        with self.assertRaises(ValueError):
            db.update_product(p["id"], business_id=self.bid, price="no")
        with self.assertRaises(ValueError):
            db.update_product(p["id"], business_id=self.other["id"], price=4)

    # ------------------------------------------------------------------- CRM
    def test_lead_lifecycle_and_convert(self):
        lead = db.add_lead("María — reforma baño", phone="600111222",
                           source="WhatsApp", value_estimate=1500,
                           next_action_on="2026-07-01", business_id=self.bid)
        self.assertEqual(lead["status"], "nuevo")
        db.update_lead(lead["id"], business_id=self.bid,
                       status="presupuesto_enviado")
        due = db.leads_due_today(self.bid)
        self.assertEqual([l["id"] for l in due], [lead["id"]])
        result = db.convert_lead_to_client(lead["id"], business_id=self.bid)
        self.assertEqual(result["lead"]["status"], "ganado")
        self.assertEqual(result["lead"]["client_id"], result["client"]["id"])
        # Convertido: ya no cuenta como seguimiento pendiente.
        self.assertEqual(db.leads_due_today(self.bid), [])
        with self.assertRaises(ValueError):
            db.convert_lead_to_client(lead["id"], business_id=self.bid)

    def test_lead_validation_and_isolation(self):
        with self.assertRaises(ValueError):
            db.add_lead("", business_id=self.bid)
        with self.assertRaises(ValueError):
            db.add_lead("X", next_action_on="1/7/2026", business_id=self.bid)
        lead = db.add_lead("Solo mío", business_id=self.bid)
        self.assertIsNone(db.get_lead(lead["id"], self.other["id"]))
        with self.assertRaises(ValueError):
            db.update_lead(lead["id"], business_id=self.bid, status="volando")

    # ------------------------------------------------- Solicitudes gestoría
    def test_gestoria_request_flow(self):
        req = db.add_gestoria_request("Falta la factura de la furgoneta.",
                                      business_id=self.bid)
        self.assertEqual(req["status"], "abierta")
        with self.assertRaises(ValueError):
            db.add_gestoria_request("", business_id=self.bid)
        replied = db.reply_gestoria_request(
            req["id"], "Subida, la tienes en Documentos.",
            business_id=self.bid)
        self.assertEqual(replied["status"], "respondida")
        self.assertEqual(
            db.list_gestoria_requests(self.bid, status="abierta"), [])
        with self.assertRaises(ValueError):
            db.reply_gestoria_request(req["id"], "Fuga",
                                      business_id=self.other["id"])

    # ---------------------------------------------------------------- Idioma
    def test_language_persists_and_validates(self):
        db.update_language(self.bid, "ca")
        self.assertEqual(db.get_business(self.bid)["language"], "ca")
        with self.assertRaises(ValueError):
            db.update_language(self.bid, "klingon")

    # ------------------------------------------------------------------- P&G
    def test_pnl_never_invents_numbers(self):
        empty = db.profit_and_loss(self.bid)
        self.assertIsNone(empty["revenue"])
        self.assertIsNone(empty["gross_result"])
        self.assertIsNone(empty["ebitda_estimate"])
        self.assertTrue(any("factura" in m for m in empty["missing"]))
        # Con solo gastos sigue sin inventar resultado.
        db.add_expense("Gasolina", 50, vat_rate=21, business_id=self.bid)
        partial = db.profit_and_loss(self.bid)
        self.assertIsNotNone(partial["costs"])
        self.assertIsNone(partial["gross_result"])

    # ------------------------------------------------------------ Plan diario
    def test_daily_plan_includes_new_signals(self):
        from noesis.documents import service as docservice
        db.add_lead("Frío SA", next_action_on="2026-01-01",
                    business_id=self.bid)
        db.add_gestoria_request("Necesito el modelo 130.",
                                business_id=self.bid)
        doc = docservice.upload(self.bid, "papel.pdf", b"%PDF-1.4 x",
                                run_ocr=False)
        from noesis.documents import repo as docrepo
        docrepo.set_review(doc["id"], self.bid,
                           doc_status="pendiente_revisar")
        db.add_received_invoice(99.0, business_id=self.bid)
        topics = {item["topic"] for item in
                  chat._daily_plan(chat._business_state(self.bid))}
        self.assertLessEqual({"crm", "gestoria", "documentos", "pagos"},
                             topics)

    # ------------------------------------------------------- Asistente por página
    def test_page_briefing_uses_real_data(self):
        text = chat.page_briefing(self.bid, "documentos")
        self.assertIn("No tienes documentos pendientes", text)
        self.assertIsNone(chat.page_briefing(self.bid, "pagina-inventada"))
        reply = chat.handle(self.bid, "¿qué significa esta página?",
                            page="crm")
        self.assertEqual(reply["source"], "local")
        self.assertIn("CRM".lower(), reply["reply"].lower())

    # ------------------------------------------------- Parte de Noesis (Home)
    def test_daily_briefing_honest_and_actionable(self):
        empty = chat.daily_briefing(self.bid)
        self.assertFalse(empty["has_activity"])
        self.assertEqual(empty["tasks"], [])
        self.assertIn("Aún no tengo nada", empty["lead"])
        # Un lead con seguimiento vencido genera una tarea de CRM con acción y
        # enlace válido, y el parte deja de decir "nada que ordenar".
        db.add_lead("Frío SA", next_action_on="2020-01-01", business_id=self.bid)
        b = chat.daily_briefing(self.bid)
        crm = [t for t in b["tasks"] if t["topic"] == "crm"]
        self.assertTrue(crm)
        self.assertTrue(crm[0]["href"].endswith("/crm"))
        self.assertTrue(crm[0]["action"])
        self.assertNotIn("Aún no tengo nada", b["lead"])

    def test_page_note_voice_and_resilience(self):
        # El Home no lleva línea (ya tiene su parte); una página inventada tampoco.
        self.assertIsNone(chat.page_note(self.bid, "resumen"))
        self.assertIsNone(chat.page_note(self.bid, "pagina-inventada"))
        # Una página real devuelve una línea (honesta aunque no haya datos).
        self.assertTrue(chat.page_note(self.bid, "cobros"))
        # Resiliencia: si la lectura del negocio peta, devuelve None, no lanza.
        original = chat._business_state

        def boom(_bid):
            raise RuntimeError("fallo simulado")

        chat._business_state = boom
        try:
            self.assertIsNone(chat.page_note(self.bid, "cobros"))
        finally:
            chat._business_state = original

    def test_daily_briefing_never_crashes_the_home(self):
        # Si al leer el negocio algo falla (p. ej. una consulta que solo peta en
        # Postgres), el parte devuelve un mínimo honesto en vez de tumbar el Home.
        original = chat._compose_briefing

        def boom(_business_id):
            raise RuntimeError("fallo simulado de lectura")

        chat._compose_briefing = boom
        try:
            b = chat.daily_briefing(self.bid)
        finally:
            chat._compose_briefing = original
        self.assertEqual(b["tasks"], [])
        self.assertIn("greeting", b)
        self.assertIn("No he podido preparar", b["lead"])

    # -------------------------------------------------------------- Proyectos
    def test_project_budget_hours_margin_and_isolation(self):
        client = db.add_client("Comunidad Marina", business_id=self.bid)
        worker = db.create_worker(self.bid, "Pau")
        project = db.add_project(
            "Instalación comunitaria", 8000, client_id=client["id"],
            planned_hours=80, business_id=self.bid,
        )
        db.add_project_member(
            project["id"], worker["id"], 22, "Oficial", business_id=self.bid
        )
        db.add_project_entry(
            project["id"], "horas", "Montaje", 10, 22, worker["id"],
            business_id=self.bid,
        )
        db.add_project_entry(
            project["id"], "material", "Tubería", 2, 150,
            business_id=self.bid,
        )
        detail = db.get_project(project["id"], self.bid)
        self.assertEqual(detail["actual_hours"], 10)
        self.assertEqual(detail["actual_cost"], 520)
        self.assertEqual(detail["margin"], 7480)
        self.assertEqual(detail["members"][0]["worker_name"], "Pau")
        self.assertIsNone(db.get_project(project["id"], self.other["id"]))

    def test_project_cross_tenant_relations_are_rejected(self):
        foreign_client = db.add_client("Privado", business_id=self.other["id"])
        foreign_worker = db.create_worker(self.other["id"], "Ajeno")
        with self.assertRaises(ValueError):
            db.add_project(
                "Ataque", 1000, client_id=foreign_client["id"],
                business_id=self.bid,
            )
        project = db.add_project("Seguro", 1000, business_id=self.bid)
        with self.assertRaises(ValueError):
            db.add_project_member(
                project["id"], foreign_worker["id"], business_id=self.bid
            )

    def test_explanation_level_is_account_wide(self):
        db.update_explanation_level(self.bid, "detallado")
        self.assertEqual(db.get_business(self.bid)["explanation_level"], "detallado")
        with self.assertRaises(ValueError):
            db.update_explanation_level(self.bid, "inventado")

    # ------------------------------------------------------ Memoria y señales
    def test_assistant_history_and_memory_are_durable_and_isolated(self):
        result = chat.handle(self.bid, "resumen")
        self.assertTrue(result["reply"])
        history = db.list_assistant_messages(self.bid)
        self.assertEqual([item["role"] for item in history], ["user", "assistant"])
        self.assertEqual(db.list_assistant_messages(self.other["id"]), [])

        db.remember(
            self.bid, "forma_de_cobro", "transferencia",
            user_confirmed=True, confidence=100,
        )
        self.assertEqual(db.list_memories(self.bid)[0]["memory_value"], "transferencia")
        self.assertEqual(db.list_memories(self.other["id"]), [])

        memory_id = db.list_memories(self.bid)[0]["id"]
        self.assertFalse(db.delete_memory(self.other["id"], memory_id))
        self.assertTrue(db.delete_memory(self.bid, memory_id))
        self.assertEqual(db.list_memories(self.bid), [])

    def test_client_insights_explain_overdue_risk(self):
        client = db.add_client("Cliente lento", business_id=self.bid)
        invoice = db.add_invoice(
            client["id"], "Trabajo", 100, business_id=self.bid
        )
        db.mark_invoice_sent(
            invoice["id"], "EXT-1", due_date="2020-01-01",
            business_id=self.bid,
        )
        insight = db.client_insights(self.bid)[0]
        self.assertEqual(insight["level"], "alto")
        self.assertIn("reclamar", insight["headline"].lower())
        self.assertGreater(insight["pending_amount"], 0)
        self.assertEqual(db.client_insights(self.other["id"]), [])

    def test_imported_invoice_can_never_be_reissued(self):
        client = db.add_client("Cliente histórico", business_id=self.bid)
        invoice = db.add_invoice(
            client["id"], "Factura importada", 250, business_id=self.bid
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE invoices SET source='importada', external_number='A-17' "
                "WHERE id=? AND business_id=?",
                (invoice["id"], self.bid),
            )
        with self.assertRaises(ValueError):
            db.issue_invoice(invoice["id"], self.bid)
        with self.assertRaises(ValueError):
            db.mark_invoice_sent(
                invoice["id"], "F-2026-999", business_id=self.bid
            )

    # -------------------------------------------------------- RGPD y migración
    def test_export_and_cascade_cover_new_tables(self):
        db.add_product("Hora", price=40, business_id=self.bid)
        db.add_lead("Lead", business_id=self.bid)
        db.add_gestoria_request("Hola", business_id=self.bid)
        db.add_supplier("Prov", business_id=self.bid)
        db.add_received_invoice(10, business_id=self.bid)
        project = db.add_project("Obra", 1000, business_id=self.bid)
        db.add_project_entry(project["id"], "material", "Piezas", 1, 10,
                             business_id=self.bid)
        db.add_assistant_message(self.bid, "user", "hola")
        db.remember(self.bid, "clave", "valor", user_confirmed=True)
        data = db.export_business_data(self.bid)
        for key in ("products", "leads", "gestoria_requests", "suppliers",
                    "received_invoices", "projects", "project_entries",
                    "assistant_messages", "business_memories"):
            self.assertEqual(len(data[key]), 1, key)
        self.assertTrue(db.delete_business_cascade(self.bid))
        self.assertIsNone(db.get_business(self.bid))

    def test_latest_migration_roundtrip(self):
        self.assertEqual(migrations.current_version(),
                         migrations.LATEST_VERSION)
        self.assertEqual(migrations.downgrade(18), 18)
        self.assertEqual(migrations.upgrade(), migrations.LATEST_VERSION)
        db.add_product("Post", price=1, business_id=self.other["id"])


if __name__ == "__main__":
    unittest.main()
