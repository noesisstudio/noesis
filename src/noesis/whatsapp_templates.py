"""Espejo comprobable de las plantillas aprobadas en Meta.

La fuente de verdad es el runbook `WhatsApp-Puesta-en-marcha`: ahí están los
cuerpos que se pegan en WhatsApp Manager. Este módulo los repite en código con
una sola finalidad: que una máquina pueda avisar si un envío deja de encajar
con lo aprobado. Meta no avisa —simplemente rechaza el mensaje— y las pruebas
no lo ven porque simulan su respuesta.

Dos reglas de Meta explican por qué los cuerpos son como son:

1. **El cuerpo no puede ser solo una variable.** Por eso los cinco avisos al
   titular llevan un encabezado fijo delante del hueco, aunque el texto lo
   componga Bynoesis entero.
2. **Un hueco no admite saltos de línea, tabuladores ni cuatro espacios
   seguidos.** De eso se encarga `whatsapp.sanitize_template_param`, que los
   convierte en un separador visible al encolar.

Ejecuta ``python -m noesis.whatsapp_templates`` para ver qué no cuadra.
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
    category: str         # categoría de Meta: siempre utility en Bynoesis
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
        default_name="bynoesis_resumen_diario",
        category="utility",
        audience="titular",
        purpose="El parte de la mañana.",
        body="Tu parte de hoy en Bynoesis: {{1}}",
        params=(
            "el parte entero",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_WEEKLY_SUMMARY",
        default_name="bynoesis_resumen_semanal",
        category="utility",
        audience="titular",
        purpose="El repaso de la semana.",
        body="Tu semana en Bynoesis: {{1}}",
        params=(
            "el repaso entero",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_DAILY_CLOSING",
        default_name="bynoesis_cierre_dia",
        category="utility",
        audience="titular",
        purpose="El cierre del día.",
        body="Cierre del día: {{1}}",
        params=(
            "el cierre entero",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_TAX_NOTICE",
        default_name="bynoesis_aviso_fiscal",
        category="utility",
        audience="titular",
        purpose="Aviso trimestral de los modelos 303 y 130.",
        body="Aviso fiscal de Bynoesis: {{1}}",
        params=(
            "el aviso entero",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_PAYMENT_ALERT",
        default_name="bynoesis_aviso_cobros",
        category="utility",
        audience="titular",
        purpose="Propuesta de reclamar una factura vencida, que espera un SÍ.",
        body="Tienes un cobro pendiente: {{1}}",
        params=(
            "el aviso entero",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_PAYMENT_REMINDER",
        default_name="bynoesis_recordatorio_cobro",
        category="utility",
        audience="cliente",
        purpose="Recordatorio de cobro al cliente del autónomo.",
        body="Hola {{1}}, te escribe {{2}}. Tienes pendiente la factura {{3}} por un importe de {{4}}. Puedes verla y pagarla aquí: {{5}}",
        params=(
            "nombre del cliente",
            "nombre del negocio",
            "número del documento",
            "importe",
            "enlace privado",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_INVOICE",
        default_name="bynoesis_factura_lista",
        category="utility",
        audience="cliente",
        purpose="Entrega de la factura emitida. Sin ella no hay entrega por WhatsApp.",
        body="Hola {{1}}, te escribe {{2}}. Ya tienes lista la factura {{3}} por {{4}}. La puedes descargar aquí: {{5}}",
        params=(
            "nombre del cliente",
            "nombre del negocio",
            "número del documento",
            "importe",
            "enlace privado",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_QUOTE_FOLLOWUP",
        default_name="bynoesis_seguimiento_presupuesto",
        category="utility",
        audience="cliente",
        purpose="Seguimiento de un presupuesto que lleva días abierto.",
        body="Hola {{1}}, te escribe {{2}}. ¿Has podido revisar el presupuesto {{3}} por {{4}}? Lo tienes aquí: {{5}}",
        params=(
            "nombre del cliente",
            "nombre del negocio",
            "número del documento",
            "importe",
            "enlace privado",
        ),
    ),
    TemplateSpec(
        setting="WHATSAPP_TEMPLATE_APPOINTMENT_REMINDER",
        default_name="bynoesis_recordatorio_cita",
        category="utility",
        audience="cliente",
        purpose="Confirmación de cita. Aquí no hay enlace: son cuatro huecos, no cinco.",
        body="Hola {{1}}, te escribe {{2}}. Te recordamos la cita del {{3}} para {{4}}. Si necesitas cambiarla, responde a este mensaje.",
        params=(
            "nombre del cliente",
            "nombre del negocio",
            "cuándo es la cita",
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
