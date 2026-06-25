"""El cerebro de Noesis.

Mantiene una conversación con Claude. Cuando Claude decide que hay que ejecutar
una acción (agendar, facturar, cobrar...), llama a la herramienta correspondiente,
le devuelve el resultado y deja que Claude redacte la respuesta final al autónomo.

Es el mismo bucle que usaremos cuando el canal sea WhatsApp en vez de la consola.
"""

from __future__ import annotations

from datetime import date, datetime

import anthropic

from . import config, db
from .tools import TOOLS, run_tool

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _system_prompt() -> str:
    hoy = date.today()
    return f"""Eres Noesis, el copiloto de negocio de un autónomo de servicios \
(fontanero, electricista, reformas, limpieza, jardinería...). Hablas por WhatsApp.

Tu misión: quitarle ruido mental. Te ocupas de su agenda, sus clientes, sus \
cobros y sus facturas para que él solo tenga que hacer su trabajo.

CONTEXTO TEMPORAL
- Hoy es {_DIAS[hoy.weekday()]} {hoy.isoformat()}.
- Cuando el usuario diga "mañana", "el jueves", "esta tarde"... calcula tú la \
fecha real y pásala a las herramientas en formato ISO (YYYY-MM-DD o YYYY-MM-DDTHH:MM).

NEGOCIO ({config.BUSINESS_NAME})
- Los importes de las facturas que te dictan suelen ser SIN IVA ("180 más IVA"). \
Si dicen "180 con IVA incluido", ajústalo. El IVA por defecto es 21%.
- Flujo de factura: primero 'crear_factura' (borrador) y MUESTRA el total para que \
confirme; solo si confirma, 'enviar_factura'. Nunca envíes sin confirmación.

ESTILO
- Habla en español, cercano y directísimo, como un buen ayudante de confianza. \
Frases cortas. Nada de tecnicismos.
- Confirma lo que has hecho con los datos concretos (importe, día, cliente).
- Si te falta un dato imprescindible, pregúntalo en una sola frase.
- Si agendas varios trabajos el mismo día, si puedes, sugiere ordenarlos por zona \
para ahorrar desplazamientos.
- Usa euros con el símbolo € y dos decimales."""


class NoesisAgent:
    def __init__(self, business_id: int = db.DEFAULT_BUSINESS_ID):
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "Falta ANTHROPIC_API_KEY. Copia .env.example a .env y pon tu clave "
                "(https://console.anthropic.com)."
            )
        self.business_id = business_id
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.messages: list[dict] = []

    def send(self, user_text: str) -> str:
        """Procesa un mensaje del autónomo y devuelve la respuesta de Noesis."""
        self.messages.append({"role": "user", "content": user_text})

        while True:
            resp = self.client.messages.create(
                model=config.MODEL,
                max_tokens=1024,
                system=_system_prompt(),
                tools=TOOLS,
                messages=self.messages,
            )
            self.messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason != "tool_use":
                # Respuesta final: junta el texto.
                return "".join(
                    b.text for b in resp.content if b.type == "text"
                ).strip()

            # Hay llamadas a herramientas: ejecútalas y devuelve resultados.
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    output = run_tool(block.name, block.input, self.business_id)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })
            self.messages.append({"role": "user", "content": tool_results})


def daily_summary_text(business_id: int = db.DEFAULT_BUSINESS_ID) -> str:
    """Genera el resumen proactivo del día (el 'parte de la mañana').

    Esto es lo que Noesis enviaría solo cada mañana por WhatsApp: la función
    estrella para reducir ruido mental.
    """
    today = date.today().isoformat()
    jobs = db.jobs_for_date(today, business_id)
    pend = db.pending_payments(business_id)
    total_pend = round(sum(p["total"] for p in pend), 2)
    sin_confirmar = [j for j in jobs if j["status"] == "pendiente"]

    lines = [f"☀️ Buenos días. Parte del día ({today}):"]
    if jobs:
        lines.append(f"\n📋 Tienes {len(jobs)} trabajo(s):")
        for j in jobs:
            hora = ""
            if j.get("scheduled_for") and "T" in j["scheduled_for"]:
                hora = datetime.fromisoformat(j["scheduled_for"]).strftime(" %H:%M")
            zona = f" — {j['zone']}" if j.get("zone") else ""
            lines.append(f"   •{hora} {j['client_name'] or '¿?'}: {j['description']}{zona}")
    else:
        lines.append("\n📋 Hoy no tienes trabajos agendados.")

    if sin_confirmar:
        lines.append(f"\n⏳ {len(sin_confirmar)} cliente(s) sin confirmar todavía.")
    if pend:
        lines.append(f"\n💸 {len(pend)} factura(s) sin cobrar — {total_pend:.2f} € pendientes.")
        for p in pend:
            d = p.get("days_outstanding")
            aviso = f" ({d} días)" if d else ""
            lines.append(f"   • {p['client_name']}: {p['total']:.2f} €{aviso}")

    lines.append("\n¿Quieres que confirme yo a los clientes o reordene la ruta?")
    return "\n".join(lines)
