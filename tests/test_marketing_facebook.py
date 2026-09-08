"""Pruebas de la automatización de Facebook.

No tocan la red: las llamadas a Meta se sustituyen por dobles. Lo que se verifica
es lo que puede romperse sin que nadie se entere: la cadencia de tres días, que no
se repita una publicación, que se recupere una que falló y que el calendario
respete los límites editoriales de la marca.
"""

import importlib
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
DIRECTORIO = RAIZ / "marketing" / "facebook"


def _cargar_modulos():
    """Carga los scripts de marketing, que viven fuera del paquete del producto."""

    if str(DIRECTORIO) not in sys.path:
        sys.path.insert(0, str(DIRECTORIO))
    return (
        importlib.import_module("nucleo"),
        importlib.import_module("publicar"),
        importlib.import_module("revision"),
    )


nucleo, publicar, revision = _cargar_modulos()

ENTORNO = {
    "FACEBOOK_PAGE_ID": "111222333",
    "FACEBOOK_PAGE_TOKEN": "ficticio-para-pruebas",
    "FACEBOOK_APP_ID": "",
    "FACEBOOK_APP_SECRET": "",
}

PROHIBIDAS = (
    "100%",
    "revoluciona",
    "garantiza",
    "sin errores",
    "inteligencia artificial",
    "para siempre",
)


def _pagina(mensaje, creada, enlace="/noesis/posts/1"):
    return nucleo.PublicacionPagina(
        identificador="1_1", mensaje=mensaje, creada=creada, enlace=enlace
    )


class CalendarioEditorial(unittest.TestCase):
    def setUp(self):
        self.calendario = nucleo.cargar_calendario()

    def test_hay_cola_para_meses(self):
        # Con cadencia de 3 días, 40 piezas son cuatro meses sin repetir nada.
        self.assertGreaterEqual(len(self.calendario), 40)
        self.assertEqual(self.calendario.cadencia_dias, 3)

    def test_identificadores_unicos(self):
        identificadores = [pub.identificador for pub in self.calendario.publicaciones]
        self.assertEqual(len(identificadores), len(set(identificadores)))

    def test_enlaces_solo_al_sitio_propio(self):
        for pub in self.calendario.publicaciones:
            if pub.enlace:
                self.assertTrue(
                    pub.enlace.startswith(nucleo.DOMINIO_PERMITIDO),
                    f"{pub.identificador} enlaza fuera de bynoesis.com",
                )

    def test_gancho_corto_y_texto_acotado(self):
        for pub in self.calendario.publicaciones:
            self.assertLessEqual(
                len(pub.primera_linea), 130, f"{pub.identificador} empieza demasiado largo"
            )
            self.assertLessEqual(len(pub.texto), nucleo.LARGO_MAXIMO_TEXTO)

    def test_sin_promesas_prohibidas_por_la_marca(self):
        for pub in self.calendario.publicaciones:
            texto = pub.texto.lower()
            for prohibida in PROHIBIDAS:
                self.assertNotIn(
                    prohibida, texto, f"{pub.identificador} usa una promesa prohibida"
                )

    def test_calendario_invalido_avisa_del_motivo(self):
        import json
        import tempfile

        datos = {
            "cadencia_dias": 3,
            "ancla": "2026-09-09",
            "publicaciones": [
                {"id": "X1", "pilar": "p", "titulo": "t", "texto": "hola"},
                {"id": "X1", "pilar": "p", "titulo": "t", "texto": "adiós", "enlace": "https://otro.com"},
            ],
        }
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "calendario.json"
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            with self.assertRaises(nucleo.ErrorCalendario) as error:
                nucleo.cargar_calendario(ruta)
        self.assertIn("repetido", str(error.exception))
        self.assertIn("bynoesis.com", str(error.exception))


class Cadencia(unittest.TestCase):
    def setUp(self):
        self.calendario = nucleo.cargar_calendario()
        self.ancla = self.calendario.ancla

    def test_publica_cada_tres_dias_y_no_los_demas(self):
        for salto in range(0, 30):
            dia = self.ancla + timedelta(days=salto)
            previsto = nucleo.publicacion_de(dia, self.calendario)
            if salto % 3 == 0:
                self.assertIsNotNone(previsto, f"{dia} debería publicar")
            else:
                self.assertIsNone(previsto, f"{dia} no debería publicar")

    def test_antes_del_ancla_no_publica(self):
        self.assertIsNone(nucleo.publicacion_de(self.ancla - timedelta(days=1), self.calendario))

    def test_orden_y_vuelta_del_calendario(self):
        primera, vuelta = nucleo.publicacion_de(self.ancla, self.calendario)
        self.assertEqual(primera, self.calendario.publicaciones[0])
        self.assertEqual(vuelta, 0)
        despues = self.ancla + timedelta(days=3 * len(self.calendario))
        repetida, segunda_vuelta = nucleo.publicacion_de(despues, self.calendario)
        self.assertEqual(repetida, self.calendario.publicaciones[0])
        self.assertEqual(segunda_vuelta, 1)

    def test_proximos_turnos_estan_separados_tres_dias(self):
        agenda = nucleo.proximos_turnos(self.ancla + timedelta(days=1), 4, self.calendario)
        self.assertEqual(len(agenda), 4)
        fechas = [fecha for fecha, _, _ in agenda]
        self.assertEqual(fechas[0], self.ancla + timedelta(days=3))
        for anterior, siguiente in zip(fechas, fechas[1:]):
            self.assertEqual((siguiente - anterior).days, 3)

    def test_restantes_avisan_antes_de_repetir(self):
        self.assertEqual(nucleo.restantes_sin_repetir(self.ancla, self.calendario), len(self.calendario))
        ultimo = self.ancla + timedelta(days=3 * (len(self.calendario) - 1))
        self.assertEqual(nucleo.restantes_sin_repetir(ultimo, self.calendario), 1)

    def test_firma_ignora_acentos_mayusculas_y_espacios(self):
        self.assertEqual(
            nucleo.firma("Día  29\n\ny llama la GESTORÍA"),
            nucleo.firma("dia 29 y llama la gestoria"),
        )


class Publicador(unittest.TestCase):
    def setUp(self):
        self.calendario = nucleo.cargar_calendario()
        self.ancla = self.calendario.ancla
        self.primera = self.calendario.publicaciones[0]
        parche = mock.patch.dict(os.environ, ENTORNO, clear=False)
        parche.start()
        self.addCleanup(parche.stop)

    def _ejecutar(self, argumentos, publicadas):
        with mock.patch.object(nucleo, "publicaciones_recientes", return_value=publicadas), \
                mock.patch.object(nucleo, "graph_post", return_value={"id": "1_9"}) as envio:
            codigo = publicar.main(argumentos)
        return codigo, envio

    def test_publica_lo_que_toca_con_texto_y_enlace(self):
        codigo, envio = self._ejecutar(["--fecha", self.ancla.isoformat()], [])
        self.assertEqual(codigo, 0)
        envio.assert_called_once()
        _, ruta, datos = envio.call_args[0]
        self.assertEqual(ruta, "111222333/feed")
        self.assertEqual(datos["message"], self.primera.texto)
        self.assertEqual(datos["link"], self.primera.enlace)

    def test_un_dia_sin_turno_no_publica(self):
        codigo, envio = self._ejecutar(
            ["--fecha", (self.ancla + timedelta(days=1)).isoformat(), "--sin-recuperacion"], []
        )
        self.assertEqual(codigo, 0)
        envio.assert_not_called()

    def test_no_repite_lo_que_ya_esta_en_la_pagina(self):
        publicada = _pagina(self.primera.texto, datetime.now(timezone.utc))
        codigo, envio = self._ejecutar(["--fecha", self.ancla.isoformat()], [publicada])
        self.assertEqual(codigo, 0)
        envio.assert_not_called()

    def test_recupera_la_publicacion_que_no_llego_a_salir(self):
        codigo, envio = self._ejecutar(
            ["--fecha", (self.ancla + timedelta(days=1)).isoformat()], []
        )
        self.assertEqual(codigo, 0)
        envio.assert_called_once()
        self.assertEqual(envio.call_args[0][2]["message"], self.primera.texto)

    def test_no_recupera_si_la_pagina_ya_ha_publicado_algo(self):
        otra = _pagina(
            "Un aviso escrito a mano",
            datetime(self.ancla.year, self.ancla.month, self.ancla.day, 10, tzinfo=timezone.utc),
        )
        codigo, envio = self._ejecutar(
            ["--fecha", (self.ancla + timedelta(days=1)).isoformat()], [otra]
        )
        self.assertEqual(codigo, 0)
        envio.assert_not_called()

    def test_sin_credenciales_queda_en_pausa_sin_fallar(self):
        with mock.patch.dict(os.environ, {"FACEBOOK_PAGE_ID": "", "FACEBOOK_PAGE_TOKEN": ""}):
            with mock.patch.object(nucleo, "graph_post") as envio:
                codigo = publicar.main(["--fecha", self.ancla.isoformat()])
        self.assertEqual(codigo, 0)
        envio.assert_not_called()

    def test_un_error_de_meta_devuelve_fallo(self):
        with mock.patch.object(nucleo, "publicaciones_recientes", return_value=[]), \
                mock.patch.object(nucleo, "graph_post", side_effect=nucleo.ErrorGraph("token caducado")):
            codigo = publicar.main(["--fecha", self.ancla.isoformat()])
        self.assertEqual(codigo, 1)


class RevisionSemanal(unittest.TestCase):
    def setUp(self):
        self.calendario = nucleo.cargar_calendario()
        parche = mock.patch.dict(os.environ, ENTORNO, clear=False)
        parche.start()
        self.addCleanup(parche.stop)
        self.diagnostico = nucleo.Diagnostico(
            nombre_pagina="Noesis",
            usuario="bynoesis",
            lee_publicaciones=True,
            caduca=None,
            permisos=("pages_manage_posts",),
            avisos=(),
        )

    def test_marca_lo_publicado_y_avisa_de_lo_que_falta(self):
        ancla = self.calendario.ancla
        domingo = ancla + timedelta(days=4)  # cubre los turnos del ancla y del día +3
        primera = self.calendario.publicaciones[0]
        publicadas = [
            _pagina(primera.texto, datetime(ancla.year, ancla.month, ancla.day, 8, tzinfo=timezone.utc))
        ]
        with mock.patch.object(nucleo, "publicaciones_recientes", return_value=publicadas), \
                mock.patch.object(nucleo, "diagnostico_conexion", return_value=self.diagnostico):
            lineas, avisos = revision.construir_informe(domingo, self.calendario)
        informe = "\n".join(lineas)
        self.assertIn(f"✅ **{revision._fecha_larga(ancla)}**", informe)
        segunda = self.calendario.publicaciones[1]
        self.assertIn(f"❌ **{revision._fecha_larga(ancla + timedelta(days=3))}**", informe)
        self.assertTrue(any(segunda.identificador in aviso for aviso in avisos))

    def test_informe_sin_credenciales_explica_la_pausa(self):
        with mock.patch.dict(os.environ, {"FACEBOOK_PAGE_ID": "", "FACEBOOK_PAGE_TOKEN": ""}):
            lineas, avisos = revision.construir_informe(date(2026, 9, 13), self.calendario)
        informe = "\n".join(lineas)
        self.assertIn("pausa", informe.lower())
        self.assertTrue(avisos)

    def test_ensena_las_proximas_publicaciones(self):
        ancla = self.calendario.ancla
        with mock.patch.object(nucleo, "publicaciones_recientes", return_value=[]), \
                mock.patch.object(nucleo, "diagnostico_conexion", return_value=self.diagnostico):
            lineas, _ = revision.construir_informe(ancla, self.calendario)
        informe = "\n".join(lineas)
        for siguiente in self.calendario.publicaciones[1:4]:
            self.assertIn(siguiente.titulo, informe)


if __name__ == "__main__":
    unittest.main()
