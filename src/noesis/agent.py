"""El cerebro de Noesis.

Mantiene una conversación con Claude. Cuando Claude decide que hay que ejecutar
una acción (agendar, facturar, cobrar...), llama a la herramienta correspondiente,
le devuelve el resultado y deja que Claude redacte la respuesta final al autónomo.

Es el mismo bucle que usaremos cuando el canal sea WhatsApp en vez de la consola.
"""

from __future__ import annotations

from datetime import date, datetime
import threading

import anthropic

from . import config, db
from .tools import TOOLS, run_tool

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _system_prompt(business: dict) -> str:
    hoy = date.today()
    name = business.get("name") or config.BUSINESS_NAME
    sector = business.get("sector") or "servicios"
    vat = business.get("default_vat", 21)
    irpf = business.get("default_irpf", 0)
    return f"""Eres Noesis, el copiloto de negocio de un autónomo de {sector} \
(fontanero, electricista, reformas, limpieza, jardinería...). Hablas por WhatsApp.

Tu misión: quitarle ruido mental. Te ocupas de su agenda, sus clientes, sus \
presupuestos, sus cobros, sus facturas, sus gastos, sus proyectos, su equipo, sus \
documentos y la coordinación con su gestoría para que él solo tenga que hacer su \
trabajo.

QUÉ PUEDES HACER (y solo esto)
- Agendar trabajos y consultar la agenda de un día.
- Crear presupuestos y facturas en BORRADOR, registrar gastos.
- Consultar cobros pendientes, el resumen del mes y la lista de clientes.
- Consultar proyectos, trabajos, tareas, horas, costes, documentos, equipo y gestoría.
- Crear proyectos y tareas cuando el usuario lo pida expresamente.
Usa SIEMPRE las herramientas para consultar o hacer cosas. Nunca te inventes \
cifras, fechas, clientes ni importes: si no tienes el dato, consúltalo con una \
herramienta o pídelo. Si te preguntan algo de lo que no hay dato, dilo con \
honestidad en vez de adivinar.

LÍMITES (no eres un chat libre)
- Eres un asistente de NEGOCIO, no un chatbot de conversación general. Si te piden \
chistes, opiniones, temas personales o cosas ajenas al negocio, responde breve y \
amable y reconduce a lo que sí puedes hacer ("Para eso no soy yo; pero dime y te \
agendo, facturo o miro tus cobros").
- Acciones IRREVERSIBLES (emitir/enviar una factura de verdad, marcar un cobro): NO \
las ejecutes tú. Deja el borrador o el aviso preparado y dile que lo confirme él \
desde la app. Nunca muevas dinero ni envíes nada sin su confirmación explícita.
- Transferencias, pagos, devoluciones, impuestos, borrados y contratos SIEMPRE \
requieren aprobación específica. No presentes una preferencia como permiso: consulta \
el control de Noesis si hay dudas.

CONTEXTO TEMPORAL
- Hoy es {_DIAS[hoy.weekday()]} {hoy.isoformat()}.
- Cuando diga "mañana", "el jueves", "esta tarde"... calcula tú la fecha real y \
pásala a las herramientas en ISO (YYYY-MM-DD o YYYY-MM-DDTHH:MM).

FISCALIDAD DE {name}
- Los importes que te dictan suelen ser SIN IVA ("180 más IVA"). Si dicen "180 con \
IVA incluido", ajústalo. IVA por defecto: {vat}%. Retención IRPF por defecto: {irpf}%.

ESTILO
- Español cercano y directísimo, como un buen ayudante de confianza. Frases cortas, \
sin tecnicismos.
- Confirma lo hecho con datos concretos (importe, día, cliente).
- Si falta un dato imprescindible, pregúntalo en una sola frase.
- Si agendas varios trabajos el mismo día, sugiere ordenarlos por zona para ahorrar \
desplazamientos.
- Usa euros con el símbolo € y dos decimales."""


class NoesisAgent:
    def __init__(self, business_id: int, model: str | None = None):
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "Falta ANTHROPIC_API_KEY. Copia .env.example a .env y pon tu clave "
                "(https://console.anthropic.com)."
            )
        self.business_id = business_id
        # Por defecto el modelo principal; el chat web pasa el barato (Haiku) para
        # abaratar el respaldo (lo común ya se resuelve gratis en local).
        self.model = model or config.MODEL
        self.business = db.get_business(business_id) or {}
        self.business_name = self.business.get("name") or config.BUSINESS_NAME
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        history = db.list_assistant_messages(business_id, limit=24)
        # Al crear el agente desde una petición, el wrapper ya ha persistido el
        # mensaje actual. Se añadirá con el contexto de página en ``send``.
        if history and history[-1].get("role") == "user":
            history = history[:-1]
        self.messages: list[dict] = [
            {"role": item["role"], "content": item["content"]}
            for item in history if item.get("role") in {"user", "assistant"}
        ]
        self._lock = threading.Lock()

    def send(self, user_text: str) -> str:
        """Procesa un mensaje del autónomo y devuelve la respuesta de Noesis."""
        with self._lock:
            return self._send_locked(user_text)

    def _record_usage(self, resp) -> None:
        """Apunta los tokens de cada llamada (coste real, visible en /admin)."""
        try:
            import json as _json

            usage = getattr(resp, "usage", None)
            db.record_product_event(
                self.business_id,
                "ai_usage",
                _json.dumps({
                    "model": self.model,
                    "in": getattr(usage, "input_tokens", 0) or 0,
                    "out": getattr(usage, "output_tokens", 0) or 0,
                }, separators=(",", ":")),
            )
        except Exception:  # noqa: BLE001 — la métrica jamás rompe el chat
            pass

    def _send_locked(self, user_text: str) -> str:
        if len(self.messages) > 32:
            self.messages = self.messages[-24:]
            while self.messages and self.messages[0].get("role") != "user":
                self.messages.pop(0)
        self.messages.append({"role": "user", "content": user_text})
        self.business = db.get_business(self.business_id) or self.business
        memories = [item for item in db.list_memories(self.business_id)
                    if item.get("user_confirmed")][:12]
        signals = [item for item in db.client_insights(self.business_id)
                   if item.get("level") in {"alto", "medio"}][:3]
        permissions = db.automation_catalog(self.business_id)
        context_bits = []
        if memories:
            context_bits.append("Memoria confirmada por el usuario: " + "; ".join(
                f"{item['memory_key']}={item['memory_value']}" for item in memories
            ))
        if signals:
            context_bits.append("Señales calculadas (explica siempre el motivo): "
                                + "; ".join(
                f"{item['client_name']}: {item['headline']} ({item['reason']})"
                for item in signals
            ))
        context_bits.append(
            "Límites efectivos de autonomía: " + "; ".join(
                f"{item['key']}={item['mode']}" for item in permissions
            )
        )
        system = _system_prompt(self.business)
        if context_bits:
            system += "\n\nCONTEXTO DURABLE DEL NEGOCIO\n" + "\n".join(context_bits)

        safe_tools = [
            tool for tool in TOOLS
            if tool["name"] not in {"enviar_factura", "registrar_pago"}
        ]
        for _round in range(6):
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                tools=safe_tools,
                messages=self.messages,
            )
            self._record_usage(resp)
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
        return (
            "He detenido la operación porque necesitó demasiados pasos. "
            "Prueba a pedírmelo de una forma más concreta."
        )


def daily_summary_text(business_id: int) -> str:
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
