"""Las plantillas que hay que aprobar en Meta, escritas una sola vez.

Hasta ahora los nombres vivían en `config.py` y los textos no vivían en ningún
sitio: se decidían al escribir el mensaje en `scheduler.py` o en
`internal_brain.py`. Así no se puede dar de alta una plantilla en WhatsApp
Manager sin adivinar, ni comprobar que lo que enviamos encaja con lo aprobado.

Aquí está el contrato completo de cada plantilla: nombre, categoría, cuerpo
exacto para pegar en Meta y qué va en cada hueco. Dos reglas de Meta mandan
sobre este archivo:

1. **El cuerpo no puede ser solo variables.** Una plantilla cuyo texto es
   `{{1}}` se rechaza en la revisión. El texto fijo va en el cuerpo; en los
   huecos solo van valores.
2. **Un hueco no admite saltos de línea, tabuladores ni cuatro espacios
   seguidos.** Los saltos de línea los pone el cuerpo aprobado, nunca el
   parámetro. `whatsapp.template_param` lo garantiza al encolar.

Ejecuta ``python -m noesis.whatsapp_templates`` para imprimir lo que hay que
pegar en WhatsApp Manager y ver qué envíos no cuadran todavía.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import config

_PLACEHOLDER = re.compile(r"\{\{(\d+)\}\}")


@dataclass(frozen=True)
class TemplateSpec:
    """Una plantilla tal y como debe quedar aprobada en Meta."""

    setting: str          # variable de entorno que fija el nombre
    default_name: str     # nombre por defecto, el que hay que crear en Meta
    category: str         # categoría de Meta: siempre utility en Noesis
    audience: str         # a quién le llega: 'titular' o 'cliente'
    purpose: str
    body: str
    params: tuple[str, ...]

    @property
    def name(self) -> str:
        """Nombre vigente: respeta el override por entorno si lo hay."""
        return getattr(config, self.setting, self.default_name)

    @property
    def placeholders(self) -> int:
        """Cuántos huecos declara el cuerpo."""
        return len({int(match) for match in _PLACEHOLDER.findall(self.body)})

    def problems(self) -> list[str]:
        """Motivos por los que Meta rechazaría esta plantilla."""
        found = sorted({int(match) for match in _PLACEHOLDER.findall(self.body)})
        issues = []
        if found != list(range(1, len(found) + 1)):
            issues.append("los huecos no van numerados de 1 en adelante")
        if len(self.params) != len(found):
            issues.append(
                f"el cuerpo tiene {len(found)} huecos y se describen "
                f"{len(self.params)} valores"
            )
        if not _PLACEHOLDER.sub("", self.body).strip():
            issues.append("el cuerpo es solo variables y Meta lo rechaza")
        return issues


# El titular recibe el parte; el cliente recibe cobros, facturas y citas.
SPECS: tuple[TemplateSpec, ...] = (
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_DAILY_SUMMARY",
        default_name="noesis_resumen_diario",
        category="utility",
        audience="titular",
        purpose="El parte de la mañana: qué hay hoy y por dónde empezar.",
        body=(
            "Buenos días, {{1}}. Este es tu parte de hoy:\n"
            "\n"
            "🗓️ Trabajos: {{2}}\n"
            "💶 Por cobrar: {{3}}\n"
            "➡️ Lo primero: {{4}}\n"
            "\n"
            "Responde a este mensaje y lo vemos."
        ),
        params=(
            "nombre del negocio",
            "trabajos de hoy, en una línea",
            "importe pendiente de cobro",
            "la primera acción del día",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_DAILY_CLOSING",
        default_name="noesis_cierre_dia",
        category="utility",
        audience="titular",
        purpose="Cierre del día: qué ha entrado y qué queda para mañana.",
        body=(
            "{{1}}, cierre del día:\n"
            "\n"
            "🧾 Facturado hoy: {{2}}\n"
            "💶 Cobrado hoy: {{3}}\n"
            "➡️ Mañana lo primero: {{4}}\n"
            "\n"
            "Si algo no cuadra, dímelo por aquí."
        ),
        params=(
            "nombre del negocio",
            "importe facturado hoy",
            "importe cobrado hoy",
            "la primera acción de mañana",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_WEEKLY_SUMMARY",
        default_name="noesis_resumen_semanal",
        category="utility",
        audience="titular",
        purpose="Resumen de la semana y la acción que más mueve la aguja.",
        body=(
            "{{1}}, así ha ido tu semana:\n"
            "\n"
            "🧾 Facturado: {{2}}\n"
            "💶 Cobrado: {{3}}\n"
            "⚠️ Pendiente de cobro: {{4}}\n"
            "➡️ Acción de la semana: {{5}}\n"
            "\n"
            "Tienes el detalle en tu panel."
        ),
        params=(
            "nombre del negocio",
            "importe facturado en la semana",
            "importe cobrado en la semana",
            "importe pendiente de cobro",
            "la acción recomendada de la semana",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_TAX_NOTICE",
        default_name="noesis_aviso_fiscal",
        category="utility",
        audience="titular",
        purpose="Aviso al cerrar el trimestre, con estimaciones y plazo.",
        body=(
            "🧾 Cierre fiscal del {{1}} en {{2}}.\n"
            "\n"
            "IVA (modelo 303): {{3}}\n"
            "IRPF (modelo 130): {{4}}\n"
            "Plazo de presentación: hasta el {{5}}.\n"
            "\n"
            "Son estimaciones a partir de lo registrado. Confírmalas con tu "
            "asesoría antes de presentar."
        ),
        params=(
            "trimestre, por ejemplo «2T 2026»",
            "nombre del negocio",
            "resultado estimado del modelo 303",
            "pago estimado del modelo 130",
            "fecha límite, por ejemplo «20 de julio»",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_PAYMENT_ALERT",
        default_name="noesis_aviso_cobros",
        category="utility",
        audience="titular",
        purpose="Propuesta de reclamar una factura vencida; espera un SÍ.",
        body=(
            "💶 {{1}} te debe {{2}} de la factura {{3}}, y ya van {{4}} días.\n"
            "\n"
            "¿Le mando el recordatorio con su enlace de pago? "
            "Responde SÍ o NO."
        ),
        params=(
            "nombre del cliente",
            "importe pendiente",
            "número de factura",
            "días de retraso",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_PAYMENT_REMINDER",
        default_name="noesis_recordatorio_cobro",
        category="utility",
        audience="cliente",
        purpose="Recordatorio de pago al cliente, con su enlace privado.",
        body=(
            "Hola {{1}}. Te escribe {{2}}.\n"
            "\n"
            "Te recordamos que la factura {{3}}, por {{4}}, sigue pendiente de "
            "pago. Puedes consultarla y pagarla aquí: {{5}}\n"
            "\n"
            "Si ya la has pagado, avísanos y la damos por cerrada."
        ),
        params=(
            "nombre del cliente",
            "nombre del negocio que cobra",
            "número de factura",
            "importe pendiente",
            "enlace privado del portal del cliente",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_INVOICE",
        default_name="noesis_factura_lista",
        category="utility",
        audience="cliente",
        purpose="Entrega de una factura ya emitida, con enlace de descarga.",
        body=(
            "Hola {{1}}. Te escribe {{2}}.\n"
            "\n"
            "Ya tienes lista la factura {{3}}, por {{4}}. Puedes consultarla y "
            "descargarla aquí: {{5}}\n"
            "\n"
            "Cualquier duda, responde a este mensaje."
        ),
        params=(
            "nombre del cliente",
            "nombre del negocio que emite",
            "número de factura",
            "importe total",
            "enlace privado del PDF",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_QUOTE_FOLLOWUP",
        default_name="noesis_seguimiento_presupuesto",
        category="utility",
        audience="cliente",
        purpose="Seguimiento de un presupuesto enviado y sin respuesta.",
        body=(
            "Hola {{1}}. Te escribe {{2}}.\n"
            "\n"
            "¿Has podido revisar el presupuesto {{3}}, por {{4}}? Lo tienes "
            "aquí: {{5}}\n"
            "\n"
            "Si quieres ajustar algún punto, dímelo y lo revisamos."
        ),
        params=(
            "nombre del cliente",
            "nombre del negocio que presupuesta",
            "número de presupuesto",
            "importe del presupuesto",
            "enlace privado del portal del cliente",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_APPOINTMENT_REMINDER",
        default_name="noesis_recordatorio_cita",
        category="utility",
        audience="cliente",
        purpose="Confirmación de una cita concertada con el cliente.",
        body=(
            "Hola {{1}}. Te escribe {{2}}.\n"
            "\n"
            "Te confirmamos la cita del {{3}} para {{4}}.\n"
            "Si necesitas cambiar la hora, responde a este mensaje."
        ),
        params=(
            "nombre del cliente",
            "nombre del negocio",
            "cuándo es la cita, en una línea",
            "qué trabajo se va a hacer",
        ),
    ),
)


BY_SETTING = {spec.setting: spec for spec in SPECS}


def spec_for(template_name: str) -> TemplateSpec | None:
    """Busca la plantilla por el nombre con el que se envía a Meta."""
    for spec in SPECS:
        if spec.name == template_name:
            return spec
    return None


# Cuántos valores manda hoy cada productor. Se mantiene a mano a propósito: es
# la lista que hay que revisar cuando se toca un envío, y lo que delata que un
# proactivo sigue metiendo el mensaje entero en un solo hueco.
SENT_PARAMS: dict[str, int] = {
    "WHATSAPP_TEMPLATE_DAILY_SUMMARY": 1,
    "WHATSAPP_TEMPLATE_DAILY_CLOSING": 1,
    "WHATSAPP_TEMPLATE_WEEKLY_SUMMARY": 1,
    "WHATSAPP_TEMPLATE_TAX_NOTICE": 1,
    "WHATSAPP_TEMPLATE_PAYMENT_ALERT": 1,
    "WHATSAPP_TEMPLATE_PAYMENT_REMINDER": 5,
    "WHATSAPP_TEMPLATE_INVOICE": 5,
    "WHATSAPP_TEMPLATE_QUOTE_FOLLOWUP": 5,
    "WHATSAPP_TEMPLATE_APPOINTMENT_REMINDER": 4,
}


def mismatches() -> list[dict]:
    """Plantillas cuyo envío no encaja con el cuerpo que hay que aprobar."""
    out = []
    for spec in SPECS:
        sent = SENT_PARAMS.get(spec.setting)
        issues = spec.problems()
        if sent is not None and sent != spec.placeholders:
            issues.append(
                f"el código envía {sent} valor(es) y el cuerpo espera "
                f"{spec.placeholders}"
            )
        if issues:
            out.append({"name": spec.name, "issues": issues})
    return out


def _report() -> str:
    lines = ["PLANTILLAS A CREAR EN WHATSAPP MANAGER", ""]
    for spec in SPECS:
        lines.append(f"── {spec.name}  ({spec.category}, para el {spec.audience})")
        lines.append(f"   {spec.purpose}")
        lines.append("   Cuerpo:")
        lines.extend(f"     {line}" for line in spec.body.split("\n"))
        lines.append("   Huecos:")
        lines.extend(
            f"     {{{{{index}}}}} = {text}"
            for index, text in enumerate(spec.params, start=1)
        )
        lines.append("")
    problems = mismatches()
    if problems:
        lines.append("PENDIENTE DE AJUSTAR EN EL CÓDIGO")
        for problem in problems:
            lines.append(f"── {problem['name']}")
            lines.extend(f"   · {issue}" for issue in problem["issues"])
    else:
        lines.append("Todos los envíos encajan con las plantillas declaradas.")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - utilidad de consola
    print(_report())
