"""Lectura de SPF, DKIM y DMARC; sin red y sin importar el runtime.

Lo que se fija aquí es el criterio, no el DNS de hoy: que dos SPF se traten como
un fallo (el resultado real es PERMERROR, aunque los dos parezcan correctos), que
un `p=` vacío no se cuente como firma viva —los proveedores que rotan claves dejan
selectores así a propósito— y que un dominio verificado en Brevo sin firma DKIM se
señale, porque verificar la propiedad no autentica ningún correo.
"""
import unittest

from unittest.mock import patch

from scripts.check_email_dns import (
    AVISO, FALLO, OK,
    _primera_ip, clave_dkim, rangos_de_salida, revisar_dkim, revisar_dmarc,
    revisar_salida, revisar_spf, spf_autoriza,
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


class SalidaTests(unittest.TestCase):
    """Por dónde salen los correos: la reputación de esa IP no es tuya."""

    def test_it_follows_the_includes_until_the_real_ranges(self):
        def falso_dig(tipo, nombre):
            if nombre == "relay.ejemplo.com":
                return ["v=spf1 ip4:203.0.113.0/24 ip4:198.51.100.5/32 ~all"]
            return []
        with patch("scripts.check_email_dns._dig", falso_dig):
            rangos, incluidos = rangos_de_salida(
                ["v=spf1 include:relay.ejemplo.com ~all"])
        self.assertEqual(rangos, ["203.0.113.0/24", "198.51.100.5/32"])
        self.assertIn("relay.ejemplo.com", incluidos)

    def test_the_shared_relay_is_found_in_the_includes_not_in_the_ips(self):
        # El fallo que tuvo esto al escribirlo: buscar «mailchannels» entre las IP
        # no encuentra nada nunca, porque el nombre está en el include.
        with patch("scripts.check_email_dns._dig", lambda t, n: []):
            hallazgos = revisar_salida(["23.83.208.0/20"],
                                       {"relay.mailchannels.net"})
        self.assertIn("mailchannels", [t for _n, t in hallazgos])

    def test_a_listed_range_is_a_failure(self):
        with patch("scripts.check_email_dns._dig", lambda t, n: ["127.0.0.2"]):
            hallazgos = revisar_salida(["203.0.113.0/24"], set())
        self.assertIn(FALLO, niveles(hallazgos))

    def test_a_clean_range_is_reported_as_clean(self):
        with patch("scripts.check_email_dns._dig", lambda t, n: []):
            hallazgos = revisar_salida(["203.0.113.0/24"], set())
        self.assertEqual(niveles(hallazgos), [OK, OK])

    def test_without_ranges_it_says_so_instead_of_pretending(self):
        self.assertEqual(niveles(revisar_salida([], set())), [AVISO])

    def test_the_sample_ip_is_inside_the_range_and_not_the_network_address(self):
        self.assertEqual(_primera_ip("148.222.54.0/24"), "148.222.54.10")
        self.assertEqual(_primera_ip("189.12.192.0/22"), "189.12.192.10")

    def test_a_single_address_is_sampled_as_itself(self):
        # Con /32 hay una sola IP: cambiarle el último octeto comprobaría una
        # dirección que el SPF no autoriza y el resultado no diría nada.
        self.assertEqual(_primera_ip("35.85.190.185/32"), "35.85.190.185")
        self.assertEqual(_primera_ip("35.85.190.185"), "35.85.190.185")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
