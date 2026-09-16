"""Lectura local de facturas y revisión conversacional de lo leído.

Los textos imitan lo que devuelven pypdf o Tesseract con documentos reales:
columnas desalineadas, teléfonos, fechas, NIF y líneas de pago que no son totales.
"""

import unittest
from datetime import date

from fpdf import FPDF

from noesis.adapters import extraction
from noesis.documents import local_reader, pdf_text, reading, review

OWN_NIF = "B12345674"  # pragma: allowlist secret
SUPPLIER_NIF = "A81948077"  # pragma: allowlist secret
BUSINESS = {"name": "Reformas Norte SL", "nif": OWN_NIF}

SUPPLIER_INVOICE = """FERRETERIA SOL S.L.
C/ Mayor 12, 08001 Barcelona  Tel. 93 123 45 67
CIF: A81948077
FACTURA Nº: F-2026/0153
Fecha: 12/09/2026      Vencimiento: 12/10/2026
Cliente: Reformas Norte SL
NIF: B12345674
Descripción              Cantidad  Precio   Importe
Tubo cobre 15mm            10       3,20     32,00
Codo 90                    20       1,15     23,00
Base imponible                               55,00
IVA 21%                                      11,55
TOTAL FACTURA                                66,55 €
"""

CATALAN_TICKET = """SUPERMERCAT BONPREU
FACTURA SIMPLIFICADA T-0098812
Data 03-09-26 18:22
PA RUSTIC            1,20
AIGUA 1,5L           0,65
IMPORT TOTAL        12,35 €
IVA 10%   BASE 11,23  QUOTA 1,12
EFECTIU             20,00
CANVI                7,65
"""

TWO_VAT_RATES = """Suministros Levante SA  CIF A81948077
Factura 2026-77  fecha 01/08/2026
Base 10%   100,00   IVA 10,00
Base 21%   200,00   IVA 42,00
Total factura 352,00
"""

PROFESSIONAL = """Asesoria Pons
NIF 12345678Z
Factura n.º 41
Fecha de emisión 30 de agosto de 2026
Base imponible 1.000,00
IVA 21 % 210,00
Retención IRPF 15 % 150,00
Total a pagar 1.060,00 €
"""

HEADER_AND_VALUES = """Electro Barna SL
CIF A81948077
Factura FB-9
Base imponible   IVA 21%   Total
250,00           52,50     302,50
"""

OWN_INVOICE = """Reformas Norte SL
NIF B12345674
Factura 2026-15   Fecha 10/09/2026
Cliente: Ferreteria Sol S.L.
CIF A81948077
Base imponible 200,00
IVA 21% 42,00
Total 242,00
"""

STATEMENT = """Ferreteria Sol S.L.  CIF A81948077
EXTRACTO DE FACTURAS PENDIENTES
Cliente: Reformas Norte SL
Factura      Fecha        Vencimiento   Importe
F-2026/0101  02/07/2026   02/08/2026    121,00
F-2026/0120  15/07/2026   15/08/2026    60,50
F-2026/0153  12/09/2026   12/10/2026    66,55
Saldo pendiente                          248,05
"""


def read_fields(text):
    return local_reader.fields_from_text(text, business_nif=OWN_NIF, business_name=BUSINESS["name"])


class LocalReaderTests(unittest.TestCase):
    def test_supplier_invoice_is_read_from_its_labels(self):
        fields = read_fields(SUPPLIER_INVOICE)
        self.assertEqual(fields["number"], "F-2026/0153")
        self.assertEqual(fields["issued_on"], "2026-09-12")
        self.assertEqual(fields["due_on"], "2026-10-12")
        self.assertEqual(fields["supplier"], "FERRETERIA SOL S.L.")
        self.assertEqual(fields["supplier_nif"], SUPPLIER_NIF)
        self.assertEqual(fields["customer_nif"], OWN_NIF)
        self.assertEqual(float(fields["base"]), 55.0)
        self.assertEqual(fields["vat_rate"], 21)
        self.assertEqual(float(fields["vat_amount"]), 11.55)
        self.assertEqual(float(fields["total"]), 66.55)
        self.assertEqual(review.mode_for(fields["kind"], fields, BUSINESS)[0], "recibida")

    def test_catalan_ticket_ignores_cash_given_and_change(self):
        fields = read_fields(CATALAN_TICKET)
        self.assertEqual(fields["kind"], "ticket")
        self.assertEqual(float(fields["total"]), 12.35)
        self.assertEqual(fields["issued_on"], "2026-09-03")
        self.assertEqual(fields["vat_rate"], 10)
        self.assertEqual(review.mode_for(fields["kind"], fields, BUSINESS)[0], "gasto")

    def test_several_vat_rates_add_up_without_inventing_a_single_rate(self):
        fields = read_fields(TWO_VAT_RATES)
        self.assertEqual(float(fields["base"]), 300.0)
        self.assertEqual(float(fields["vat_amount"]), 52.0)
        self.assertIsNone(fields["vat_rate"])
        self.assertEqual(float(fields["total"]), 352.0)

    def test_withholding_is_read_and_the_invoice_adds_up(self):
        fields = read_fields(PROFESSIONAL)
        self.assertEqual(fields["issued_on"], "2026-08-30")
        self.assertEqual(float(fields["irpf_amount"]), 150.0)
        self.assertEqual(float(fields["total"]), 1060.0)
        item = review.new_item(fields=fields, kind=fields["kind"], business=BUSINESS, document_id=1)
        self.assertTrue(review.evaluate(item)["ready"])

    def test_labels_on_one_line_and_values_on_the_next(self):
        fields = read_fields(HEADER_AND_VALUES)
        self.assertEqual(float(fields["base"]), 250.0)
        self.assertEqual(float(fields["vat_amount"]), 52.5)
        self.assertEqual(float(fields["total"]), 302.5)

    def test_phones_dates_and_tax_ids_are_never_amounts(self):
        fields = read_fields("Tel. 93 123 45 67\nFecha 12/09/2026\nNIF A81948077\nTOTAL 20,00")
        self.assertEqual(float(fields["total"]), 20.0)
        self.assertEqual(fields["guessed"], [])

    def test_own_invoice_puts_the_business_as_issuer(self):
        fields = read_fields(OWN_INVOICE)
        self.assertEqual(fields["supplier_nif"], OWN_NIF)
        self.assertEqual(fields["customer_nif"], SUPPLIER_NIF)
        self.assertEqual(review.mode_for(fields["kind"], fields, BUSINESS)[0], "emitida")

    def test_statement_rows_are_listed_instead_of_one_total(self):
        result = local_reader.read(STATEMENT, business_nif=OWN_NIF, business_name=BUSINESS["name"])
        self.assertEqual(result["documents"], [])
        statement = result["statement"]
        self.assertEqual(statement["issuer_nif"], SUPPLIER_NIF)
        self.assertEqual([row["number"] for row in statement["items"]],
                         ["F-2026/0101", "F-2026/0120", "F-2026/0153"])
        self.assertEqual(float(statement["items"][1]["total"]), 60.5)

    def test_several_invoices_in_one_pdf_are_split_by_page(self):
        document = FPDF()
        for number in (1, 2, 3):
            document.add_page()
            document.set_font("helvetica", size=11)
            document.multi_cell(0, 7, (
                f"FERRETERIA SOL S.L.\nCIF A81948077\nFactura F-{number}\n"
                f"Fecha 0{number}/09/2026\nBase imponible {number}00,00\n"
                f"IVA 21% {number * 21},00\nTOTAL FACTURA {number * 121},00"
            ))
        pages = pdf_text.extract_pages(bytes(document.output()))
        result = local_reader.read("\n".join(pages), pages=pages, business_nif=OWN_NIF)
        self.assertEqual(len(result["documents"]), 3)
        self.assertEqual([doc["pages"] for doc in result["documents"]], [[1, 1], [2, 2], [3, 3]])
        self.assertEqual([float(doc["total"]) for doc in result["documents"]], [121.0, 242.0, 363.0])

    def test_total_factura_does_not_become_the_invoice_number(self):
        # Con una factura real del founder: «FACTURA N 2026-118» no se reconocía
        # (el patrón exigía la «º» voladita) y entonces la palabra «FACTURA» de
        # «TOTAL FACTURA 508,20» numeraba el documento como «508».
        fields = read_fields(
            "SUMINISTROS LEVANTE SA\nCIF A81948077\nFACTURA N 2026-118\n"
            "Fecha 14/09/2026\nBase imponible 420,00\nIVA 21% 88,20\n"
            "TOTAL FACTURA 508,20"
        )
        self.assertEqual(fields["number"], "2026-118")
        self.assertEqual(float(fields["total"]), 508.2)
        solo_total = read_fields("FERRETERIA\nCIF A81948077\nTOTAL FACTURA 508,20")
        self.assertIsNone(solo_total["number"])

    def test_unlabelled_amounts_are_marked_as_a_guess_that_blocks_confirmation(self):
        fields = read_fields("Material 10,00\nMano de obra 25,00")
        self.assertEqual(fields["guessed"], ["total"])
        item = review.new_item(fields=fields, kind=fields["kind"], business=BUSINESS,
                               document_id=1, guessed=fields["guessed"])
        self.assertFalse(review.evaluate(item)["ready"])
        review.apply_correction(item, "total 25")
        self.assertTrue(review.evaluate(item)["ready"])


class ReviewTests(unittest.TestCase):
    TODAY = date(2026, 9, 15)

    def item(self, kind="factura_recibida", **fields):
        return review.new_item(fields=fields, kind=kind, business=BUSINESS, document_id=1)

    def test_owner_total_replaces_the_reading_that_does_not_add_up(self):
        item = self.item(supplier="Ferretería Sol", base=37.36, vat_rate=21, vat_amount=7.84, total=45.20)
        changed, unknown = review.apply_correction(item, "no, el total es 54,20", today=self.TODAY)
        self.assertIn("total", changed)
        self.assertEqual(unknown, [])
        state = review.evaluate(item)
        self.assertTrue(state["ready"])
        self.assertEqual(state["values"]["total"], 54.2)
        self.assertEqual(state["values"]["base"], 44.79)
        self.assertEqual(state["values"]["vat_amount"], 9.41)

    def test_several_corrections_in_one_message_keep_names_intact(self):
        item = self.item()
        changed, unknown = review.apply_correction(
            item, "total 121 y proveedor Hijos y Nietos S.L.", today=self.TODAY
        )
        self.assertEqual(unknown, [])
        self.assertEqual(item["fields"]["supplier"], "Hijos y Nietos S.L.")
        self.assertEqual(item["fields"]["total"], 121.0)

    def test_rate_with_total_derives_base_and_vat_as_calculated(self):
        item = self.item(supplier="Bar Pepe", total=110)
        review.apply_correction(item, "iva 10", today=self.TODAY)
        state = review.evaluate(item)
        self.assertEqual((state["values"]["base"], state["values"]["vat_amount"]), (100.0, 10.0))
        self.assertIn("(calculado)", review.render(item))

    def test_withholding_percent_and_rate(self):
        item = self.item(supplier="Asesoria Pons", base=1000)
        review.apply_correction(item, "irpf 15, iva 21", today=self.TODAY)
        values = review.evaluate(item)["values"]
        self.assertEqual((values["irpf_amount"], values["vat_amount"], values["total"]),
                         (150.0, 210.0, 1060.0))

    def test_unreadable_photo_accepts_amount_and_name_in_one_reply(self):
        item = review.new_item(fields={}, kind=None, business=BUSINESS, document_id=1, media="image")
        self.assertIn("Escríbeme el total", review.render(item))
        changed, _ = review.apply_correction(item, "45,20 gasolinera Repsol", today=self.TODAY)
        self.assertEqual(set(changed), {"total", "concept", "supplier"})
        self.assertTrue(review.evaluate(item)["ready"])

    def test_kind_can_be_changed_by_the_owner(self):
        item = self.item(supplier="X", total=10)
        review.apply_correction(item, "es un gasto", today=self.TODAY)
        self.assertEqual(item["mode"], "gasto")
        review.apply_correction(item, "es un albarán", today=self.TODAY)
        self.assertEqual((item["mode"], item["archive_kind"]), ("archivo", "albaran"))
        self.assertTrue(review.evaluate(item)["ready"])

    def test_invalid_tax_id_blocks_until_it_is_fixed_or_removed(self):
        item = self.item(supplier="X", total=10)
        review.apply_correction(item, "nif A81948078", today=self.TODAY)
        self.assertFalse(review.evaluate(item)["ready"])
        review.apply_correction(item, "quita el nif", today=self.TODAY)
        self.assertTrue(review.evaluate(item)["ready"])

    def test_dates_without_year_stay_in_a_sensible_year(self):
        item = self.item()
        review.apply_correction(item, "fecha 12/09", today=self.TODAY)
        self.assertEqual(item["fields"]["issued_on"], "2026-09-12")
        review.apply_correction(item, "fecha 20/12", today=self.TODAY)
        self.assertEqual(item["fields"]["issued_on"], "2025-12-20")
        review.apply_correction(item, "vence 05/01", today=self.TODAY)
        self.assertEqual(item["fields"]["due_on"], "2026-01-05")

    def test_text_that_is_not_a_correction_changes_nothing(self):
        item = self.item(supplier="X", total=10)
        before = dict(item["fields"])
        self.assertEqual(review.apply_correction(item, "hola, qué tal")[0], [])
        self.assertEqual(item["fields"], before)

    def test_disagreeing_readings_wait_for_the_owner(self):
        item = review.new_item(
            fields={"supplier": "X", "total": 45.2}, kind="factura_recibida", business=BUSINESS,
            document_id=1, conflicts=[{"field": "total", "values": [45.2, 54.2]}],
        )
        self.assertFalse(review.evaluate(item)["ready"])
        review.apply_correction(item, "total 54,20", today=self.TODAY)
        self.assertTrue(review.evaluate(item)["ready"])


class ReadingTests(unittest.TestCase):
    def test_ai_reading_is_completed_by_text_and_disagreement_is_kept(self):
        ai = {"documents": [{"kind": "factura_recibida", "total": 45.2, "number": None,
                             "supplier": "Sol"}], "statement": None, "source": "ia"}
        local = {"documents": [{"kind": "factura", "total": 54.2, "number": "F-1",
                                "supplier": "Sol", "guessed": []}], "statement": None}
        merged = reading.merge(ai, local)
        document = merged["documents"][0]
        self.assertEqual(merged["source"], "mixto")
        self.assertEqual(document["number"], "F-1")
        self.assertEqual(document["conflicts"], [{"field": "total", "values": [45.2, 54.2]}])

    def test_without_ai_the_text_reading_is_used(self):
        local = local_reader.read(SUPPLIER_INVOICE, business_nif=OWN_NIF)
        merged = reading.merge(None, local)
        self.assertEqual(merged["source"], "texto")
        self.assertEqual(merged["documents"][0]["total"], 66.55)

    def test_ai_payload_is_validated_field_by_field(self):
        raw = [
            {"kind": "factura", "pages": [1, 2], "total": "121.5", "vat_rate": 7, "supplier": "A"},
            {"kind": "ticket", "pages": 3, "total": -5, "number": "T1"},
            {"kind": "otro"},
        ]
        documents = extraction._validated_reading(raw)["documents"]
        self.assertEqual(len(documents), 2)
        self.assertEqual((documents[0]["kind"], documents[0]["pages"]), ("factura_recibida", [1, 2]))
        self.assertIsNone(documents[0]["vat_rate"])
        self.assertEqual(documents[0]["total"], 121.5)
        self.assertEqual((documents[1]["pages"], documents[1]["total"]), ([3, 3], None))
        self.assertIsNone(extraction._reading_statement({"items": [{"number": "1", "total": 5}]}))
        self.assertEqual(extraction._json_payload('```json\n{"documents": []}\n```'), {"documents": []})


if __name__ == "__main__":
    unittest.main()
