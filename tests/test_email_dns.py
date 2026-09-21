"""Lectura de SPF, DKIM y DMARC; sin red y sin importar el runtime.

Lo que se fija aquí es el criterio, no el DNS de hoy: que dos SPF se traten como
un fallo (el resultado real es PERMERROR, aunque los dos parezcan correctos), que
un `p=` vacío no se cuente como firma viva —los proveedores que rotan claves dejan
selectores así a propósito— y que un dominio verificado en Brevo sin firma DKIM se
señale, porque verificar la propiedad no autentica ningún correo.
"""
import unittest

from scripts.check_email_dns import (
    AVISO, FALLO, OK,
    clave_dkim, revisar_dkim, revisar_dmarc, revisar_spf, spf_autoriza,
)


def niveles(hallazgos):
    return [nivel for nivel, _texto in hallazgos]


class SpfTests(unittest.TestCase):
    def test_the_real_record_of_bynoesis_passes(self):
        hallazgos = revisar_spf(["v=spf1 include:_spf.mail.hostinger.com ~all",
                                 "google-site-verification=loquesea"])
        self.assertEqual(niveles(hallazgos), [OK])
        self.assertIn("_spf.mail.hostinger.com", hallazgos[0][1])

    def test_two_records_are_a_failure_even_if_both_look_right(self):
        hallazgos = revisar_spf(["v=spf1 include:_spf.mail.hostinger.com ~all",
                                 "v=spf1 include:spf.brevo.com ~all"])
        self.assertEqual(niveles(hallazgos), [FALLO])
        self.assertIn("PERMERROR", hallazgos[0][1])

    def test_no_record_at_all(self):
        self.assertEqual(niveles(revisar_spf(["brevo-code:abc"])), [FALLO])

    def test_plus_all_authorises_the_whole_internet(self):
        hallazgos = revisar_spf(["v=spf1 include:x.example +all"])
        self.assertEqual(hallazgos[0][0], FALLO)

    def test_missing_all_is_only_a_warning(self):
        self.assertEqual(revisar_spf(["v=spf1 include:x.example"])[0][0], AVISO)

    def test_too_many_includes_break_the_ten_lookup_limit(self):
        registro = "v=spf1 " + " ".join(f"include:s{i}.example" for i in range(9)) + " ~all"
        self.assertIn(AVISO, niveles(revisar_spf([registro])))

    def test_authorisation_lookup(self):
        registros = ["v=spf1 include:_spf.mail.hostinger.com ~all"]
        self.assertTrue(spf_autoriza(registros, "hostinger"))
        self.assertFalse(spf_autoriza(registros, "brevo"))


class DkimTests(unittest.TestCase):
    def test_a_revoked_key_is_not_a_live_key(self):
        # Hostinger publica b y c así mientras rota. Contarlas como firmas vivas
        # haría decir que todo está bien cuando solo hay una clave de verdad.
        self.assertIsNone(clave_dkim("v=DKIM1;p="))
        self.assertIsNone(clave_dkim("no es un registro dkim"))

    def test_a_real_key_is_read(self):
        self.assertEqual(clave_dkim("v=DKIM1;k=rsa;p=MIIBIjANBg"), "MIIBIjANBg")

    def test_no_key_at_all_is_a_failure(self):
        self.assertEqual(niveles(revisar_dkim({}, "Brevo")), [FALLO])

    def test_key_length_is_reported(self):
        corta = revisar_dkim({"s1": "A" * 216}, "X")[0]
        larga = revisar_dkim({"hostingermail-a": "A" * 392}, "Hostinger")[0]
        self.assertEqual(corta[0], AVISO)
        self.assertIn("1024", corta[1])
        self.assertEqual(larga[0], OK)
        self.assertIn("2048", larga[1])


class DmarcTests(unittest.TestCase):
    def test_the_real_record_warns_about_both_things(self):
        hallazgos = revisar_dmarc(
            ["v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com"], "bynoesis.com")
        self.assertEqual(niveles(hallazgos), [AVISO, AVISO])
        self.assertIn("p=quarantine", hallazgos[0][1])
        self.assertIn("no es tuyo", hallazgos[1][1])

    def test_a_policy_with_your_own_mailbox_is_clean(self):
        hallazgos = revisar_dmarc(
            ["v=DMARC1; p=quarantine; rua=mailto:dmarc@bynoesis.com"], "bynoesis.com")
        self.assertEqual(niveles(hallazgos), [OK, OK])

    def test_without_rua_you_are_blind(self):
        hallazgos = revisar_dmarc(["v=DMARC1; p=none"], "bynoesis.com")
        self.assertIn(FALLO, niveles(hallazgos))

    def test_no_record_and_duplicated_record(self):
        self.assertEqual(niveles(revisar_dmarc([], "x.com")), [FALLO])
        self.assertEqual(
            niveles(revisar_dmarc(["v=DMARC1; p=none", "v=DMARC1; p=reject"], "x.com")),
            [FALLO])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
