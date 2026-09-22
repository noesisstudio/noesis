"""Modelo de IA: Sonnet 5 en todo, sin Haiku, y el razonamiento bajo control.

Decisión del founder del 22-09-2026. Lo que se fija aquí es lo que se rompe sin
avisar al cambiar de modelo:

1. Que vuelva a colarse Haiku como valor por defecto.
2. Que Sonnet 5 razone por defecto. Ese razonamiento cuenta dentro de
   `max_tokens`, y las lecturas de documentos piden entre 220 y 700: pensar
   cortaría el JSON y el documento se quedaría «pendiente» sin motivo.
3. Que el coste medido siga con la tarifa del modelo anterior.
"""
import importlib
import os
import unittest
from unittest.mock import MagicMock, patch

from noesis import config


class ModeloPorDefectoTests(unittest.TestCase):
    def _recargar(self, **entorno):
        limpio = {k: v for k, v in os.environ.items()
                  if not k.startswith("NOESIS_")}
        limpio.update(entorno)
        with patch.dict(os.environ, limpio, clear=True):
            return importlib.reload(config)

    def tearDown(self):
        importlib.reload(config)

    def test_sonnet_everywhere_and_no_haiku(self):
        cfg = self._recargar()
        self.assertEqual(cfg.MODEL, "claude-sonnet-5")
        self.assertEqual(cfg.FALLBACK_MODEL, "claude-sonnet-5")
        self.assertEqual(cfg.EXTRACTION_MODEL, "claude-sonnet-5")
        for valor in (cfg.MODEL, cfg.FALLBACK_MODEL, cfg.EXTRACTION_MODEL):
            self.assertNotIn("haiku", valor)

    def test_the_measured_cost_uses_the_sonnet_5_rate(self):
        # Con la tarifa de Haiku (1/5) el panel de consumo mediría la mitad de lo
        # que de verdad se gasta.
        cfg = self._recargar()
        self.assertEqual((cfg.MODEL_INPUT_USD_PER_MTOK,
                          cfg.MODEL_OUTPUT_USD_PER_MTOK), (2.0, 10.0))
        self.assertEqual((cfg.FALLBACK_INPUT_USD_PER_MTOK,
                          cfg.FALLBACK_OUTPUT_USD_PER_MTOK), (2.0, 10.0))

    def test_a_railway_variable_still_wins(self):
        cfg = self._recargar(NOESIS_FALLBACK_MODEL="claude-opus-5")
        self.assertEqual(cfg.FALLBACK_MODEL, "claude-opus-5")

    def test_thinking_is_off_unless_explicitly_adaptive(self):
        self.assertEqual(self._recargar().ai_thinking(), {"type": "disabled"})
        self.assertEqual(self._recargar(NOESIS_AI_THINKING="adaptive").ai_thinking(),
                         {"type": "adaptive"})
        # Un error de tecleo no puede encender el razonamiento.
        self.assertEqual(self._recargar(NOESIS_AI_THINKING="adaptativo").ai_thinking(),
                         {"type": "disabled"})


class LlamadasTests(unittest.TestCase):
    def test_document_reading_sends_thinking_off(self):
        from noesis.adapters import extraction
        cliente = MagicMock()
        extraction._message(cliente, model="claude-sonnet-5", max_tokens=220,
                            messages=[{"role": "user", "content": "x"}])
        enviado = cliente.messages.create.call_args.kwargs
        self.assertEqual(enviado["thinking"], {"type": "disabled"})
        self.assertEqual(enviado["model"], "claude-sonnet-5")

    def test_an_explicit_thinking_value_is_respected(self):
        from noesis.adapters import extraction
        cliente = MagicMock()
        extraction._message(cliente, model="claude-sonnet-5", max_tokens=4000,
                            thinking={"type": "adaptive"},
                            messages=[{"role": "user", "content": "x"}])
        self.assertEqual(cliente.messages.create.call_args.kwargs["thinking"],
                         {"type": "adaptive"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
