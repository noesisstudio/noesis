"""Demo comercial conectada y OCR local de PDF escaneado."""

from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fpdf import FPDF
from PIL import Image, ImageDraw

from noesis import config, db, demo
from noesis.documents import pdf_ocr, service as docservice
from noesis.web import auth


def scanned_invoice_pdf() -> bytes:
    image = Image.new("RGB", (800, 1000), "white")
    draw = ImageDraw.Draw(image)
    draw.text((50, 50), "FACTURA F-204  TOTAL 48,40 EUR", fill="black")
    payload = BytesIO()
    image.save(payload, format="PNG")
    payload.seek(0)
    pdf = FPDF()
    pdf.add_page()
    pdf.image(payload, x=10, y=10, w=180)
    return bytes(pdf.output())


class ShowcaseAndPdfOcrTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_docs_path = config.DOCS_PATH
        self.original_database_url = config.DATABASE_URL
        config.DATABASE_URL = ""
        config.DB_PATH = Path(self.tempdir.name) / "showcase.db"
        config.DOCS_PATH = Path(self.tempdir.name) / "uploads"
        db.init_db()

    def tearDown(self):
        config.DB_PATH = self.original_db_path
        config.DOCS_PATH = self.original_docs_path
        config.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    def test_showcase_connects_owner_customer_and_multi_business_gestoria(self):
        first = demo.seed_showcase(force=True)
        before = {
            "businesses": len(db.list_businesses()),
            "clients": len(db.list_clients(first["autonomo"]["business_id"])),
            "invoices": len(db.list_invoices(first["autonomo"]["business_id"])),
        }
        second = demo.seed_showcase(force=True)

        self.assertEqual(first, second)
        self.assertEqual(before, {
            "businesses": len(db.list_businesses()),
            "clients": len(db.list_clients(first["autonomo"]["business_id"])),
            "invoices": len(db.list_invoices(first["autonomo"]["business_id"])),
        })
        owner = db.get_user_by_email(demo.SHOWCASE_OWNER_EMAIL)
        self.assertTrue(auth.verify_password(
            demo.SHOWCASE_PASSWORD, owner["password_hash"]
        ))
        business_id = owner["business_id"]
        business = db.get_business(business_id)
        self.assertEqual(business["subscription_status"], "active")
        self.assertTrue(business["is_demo"])
        self.assertFalse(db.subscription_allows_access(business))
        self.assertEqual(business["whatsapp_status"], "conectado")
        activation = db.activation_snapshot(business_id)
        self.assertEqual(activation["completed"], activation["total"])
        self.assertGreaterEqual(len(db.list_clients(business_id)), 7)
        self.assertTrue(db.list_projects(business_id))
        self.assertGreaterEqual(
            sum(1 for month in db.monthly_series(business_id)
                if month["invoiced"] > 0),
            5,
        )

        token = first["cliente"]["path"].rsplit("/", 1)[-1]
        ref = db.resolve_portal_token(token)
        portal = db.client_portal_view(ref["business_id"], ref["client_id"])
        self.assertTrue(portal["quotes"])
        self.assertTrue(portal["invoices"])

        account = db.get_gestoria_account_by_email(demo.SHOWCASE_GESTORIA_EMAIL)
        self.assertTrue(auth.verify_password(
            demo.SHOWCASE_PASSWORD, account["password_hash"]
        ))
        portfolio = db.list_gestoria_businesses(account["id"])
        self.assertEqual(len(portfolio), 2)
        self.assertEqual(
            {item["name"] for item in portfolio},
            {
                "Electricidad Montseny SL · Demo",
                "Reformas y Fontanería Delta SL · Demo",
            },
        )

    def test_image_only_pdf_is_rasterized_locally_and_classified(self):
        business = db.create_business("OCR local", "ocr@example.com")
        payload = scanned_invoice_pdf()
        extracted = "FACTURA F-204\nTOTAL 48,40 EUR"
        with (
            patch.object(pdf_ocr.ocr, "available", return_value=True),
            patch.object(
                pdf_ocr.ocr, "extract_image",
                return_value={"text": extracted, "amount": 48.4},
            ) as read_image,
        ):
            document = docservice.upload(
                business["id"], "factura-escaneada.pdf", payload,
                run_ocr=True, auto_classify=True,
            )

        self.assertEqual(read_image.call_count, 1)
        self.assertIn("FACTURA F-204", document["ocr_text"])
        self.assertEqual(document["ocr_amount"], 48.4)
        self.assertEqual(document["classification"]["kind"], "documento")
        self.assertIn("factura", document["classification"]["reason"].lower())
        self.assertTrue(document["classification"]["needs_confirmation"])

    def test_pdf_ocr_rejects_absurd_page_before_rendering(self):
        class HugePage:
            @staticmethod
            def get_size():
                return 1_000_000_000, 1_000_000_000

        with self.assertRaisesRegex(ValueError, "demasiado grande"):
            pdf_ocr._safe_scale(HugePage())

    def test_three_showcase_experiences_are_navigable(self):
        from starlette.testclient import TestClient
        from noesis.web import server

        info = demo.seed_showcase(force=True)
        business_id = info["autonomo"]["business_id"]
        with patch.object(server, "start_scheduler", lambda: None):
            with TestClient(server.app) as client:
                login = client.post(
                    "/login",
                    data={
                        "email": demo.SHOWCASE_OWNER_EMAIL,
                        "password": demo.SHOWCASE_PASSWORD,
                    },
                    follow_redirects=False,
                )
                self.assertEqual(login.status_code, 303)
                for page in (
                    "resumen", "agenda", "proyectos", "clientes", "tesoreria",
                    "analisis", "ingresos", "costes", "presupuestos", "facturas",
                    "cobros", "impuestos", "equipo", "crm", "productos",
                    "documentos", "asistente", "ajustes",
                ):
                    response = client.get(f"/b/{business_id}/{page}")
                    self.assertEqual(response.status_code, 200, page)
                blocked = client.post(
                    f"/api/{business_id}/invoices", json={}
                )
                self.assertEqual(blocked.status_code, 403)
                self.assertEqual(blocked.json()["code"], "demo_read_only")

                client.post("/logout", follow_redirects=False)
                gestoria_login = client.post(
                    "/gestoria/login",
                    data={
                        "email": demo.SHOWCASE_GESTORIA_EMAIL,
                        "password": demo.SHOWCASE_PASSWORD,
                    },
                    follow_redirects=False,
                )
                self.assertEqual(gestoria_login.status_code, 303)
                self.assertEqual(client.get("/gestoria").status_code, 200)
                self.assertEqual(
                    client.get(f"/gestoria/cliente/{business_id}").status_code,
                    200,
                )
                periods = db.gestoria_periods(business_id)
                self.assertTrue(periods)
                package = client.get(
                    f"/gestoria/cliente/{business_id}/paquete/"
                    f"{periods[0]['label']}"
                )
                self.assertEqual(package.status_code, 200)
                self.assertEqual(package.headers["content-type"], "application/zip")

                client.post("/gestoria/logout", follow_redirects=False)
                self.assertEqual(client.get(info["cliente"]["path"]).status_code, 200)
                stable_portal = client.get(
                    "/demo/cliente", follow_redirects=False
                )
                self.assertEqual(stable_portal.status_code, 303)
                self.assertTrue(stable_portal.headers["location"].startswith("/p/"))
                self.assertEqual(
                    client.get(stable_portal.headers["location"]).status_code,
                    200,
                )
                token = stable_portal.headers["location"].rsplit("/", 1)[-1]
                ref = db.resolve_portal_token(token)
                portal = db.client_portal_view(
                    ref["business_id"], ref["client_id"]
                )
                invoice = portal["invoices"][0]
                event_count = len(db.list_invoice_events(
                    invoice["id"], business_id
                ))
                invoice_pdf = client.get(
                    f"/p/{token}/invoices/{invoice['id']}/pdf"
                )
                self.assertEqual(invoice_pdf.status_code, 200)
                self.assertEqual(
                    len(db.list_invoice_events(invoice["id"], business_id)),
                    event_count,
                )
                quote = portal["quotes"][0]
                self.assertEqual(
                    client.post(
                        f"/p/{token}/quotes/{quote['id']}/accept"
                    ).status_code,
                    402,
                )


if __name__ == "__main__":
    unittest.main()
