"""Inspección local sin efectos: una coincidencia parcial no acredita una orden.

No almacena mensajes, no consulta modelos y no concede permisos. Los códigos
permiten convertir incidentes en regresiones sin registrar datos personales.
"""
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class IntentRisk:
    code: str
    reply: str


def inspect_money_intent(message: str) -> IntentRisk | None:
    """Abstención conservadora para casos que el parser simple no representa.

    No es un clasificador universal ni una autorización si devuelve None.
    Los cálculos y permisos siguen validándose en las herramientas existentes.
    """
    text = "".join(c for c in unicodedata.normalize("NFKD", message.lower())
                   if not unicodedata.combining(c))
    if not re.search(r"\b(factur\w*|tiquet|ticket|presupuest\w*|pressupost\w*|"
                     r"gast\w*|compre|compra|pago|cobro)\b", text):
        return None
    # No interpretar signos como separadores ni convertir un abono en un cargo.
    # Excluir guiones internos de fechas/referencias: FACT-2026-001 no es -2026 €.
    if re.search(r"(?<![\w\d])[-−﹣－]\s*(?:€\s*)?\d", text) or re.search(
        r"[-−﹣－]\s*\d+(?:[.,]\d+)?\s*(?:€|euros?\b|eur\b)", text
    ) or re.search(
        r"\bmenos\s+\d|\(\s*\d+(?:[.,]\d+)?\s*(?:€|euros?)\s*\)", text
    ):
        return IntentRisk("signed_amount", "He detectado un importe negativo. "
                          "¿Quieres corregir un importe o registrar una devolución? "
                          "No he registrado ningún cargo ni gasto.")
    # El parser histórico solo admite una línea: no tomar la cantidad de horas
    # como base ni ignorar importes adicionales, descuentos o subtotales.
    prices = re.findall(r"\d+(?:[.,]\d+)?\s*(?:€|euros?\b|eur\b)", text)
    quantity = re.search(r"\b\d+(?:[.,]\d+)?\s*(?:horas?|piezas?|unidades?|"
                         r"metros?|uds?)\b", text)
    multiplication = re.search(r"\d\s*[x×*]\s*\d", text)
    priced_quantity = re.search(r"\b\d+(?:[.,]\d+)?\s+[a-z ]{1,100}?\s+a\s+\d", text)
    if len(prices) > 1 or quantity or multiplication or priced_quantity:
        return IntentRisk("multiple_amounts", "La orden contiene cantidades o varios importes. "
                          "Para conservar cada línea y su precio, prepara este documento "
                          "desde el formulario con líneas. No he guardado una operación parcial.")
    return None
