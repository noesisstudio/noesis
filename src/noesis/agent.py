"""Agentes avanzados del cerebro de Bynoesis.

El proveedor privado y el externo comparten contexto, herramientas y aislamiento.
Cuando el modelo propone una acción, Bynoesis valida y ejecuta la herramienta en el
servidor antes de devolver el resultado. Web y WhatsApp usan el mismo bucle.
"""

from __future__ import annotations

from datetime import date, datetime
import json
import threading
import time

import anthropic

from . import config, db
from .adapters import ai as ai_adapter
from .tools import TOOLS, run_tool

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MUTATING_TOOLS = {
    "agendar_trabajo", "crear_factura", "crear_presupuesto", "registrar_gasto",
    "crear_proyecto", "crear_tarea_proyecto", "preparar_factura_trabajo",
    "crear_cliente", "crear_proveedor",
}


def _refresh_conversation(agent) -> None:
    """Incluye también los turnos resueltos localmente entre llamadas al modelo."""
    history = db.list_assistant_messages(agent.business_id, limit=24)
    if history:
        if history[-1].get("role") == "user":
            history = history[:-1]
        agent.messages = [{"role": row["role"], "content": row["content"]}
                          for row in history if row.get("role") in {"user", "assistant"}]


class PartialAgentExecutionError(RuntimeError):
    """El proveedor falló después de que una herramienta pudiera haber escrito."""


def _estimated_cost_usd(
    input_tokens: int,
    output_tokens: int,
    input_usd_per_mtok: float,
    output_usd_per_mtok: float,
) -> float:
    """Coste estimado por llamada; nunca se usa para facturar al cliente."""
    return round(
        (input_tokens * input_usd_per_mtok
         + output_tokens * output_usd_per_mtok) / 1_000_000,
        8,
    )


def _system_prompt(business: dict) -> str:
    hoy = date.today()
    name = business.get("name") or config.BUSINESS_NAME
    sector = business.get("sector") or "servicios"
    vat = business.get("default_vat", 21)
    irpf = business.get("default_irpf", 0)
    return f"""Eres Bynoesis, el copiloto de negocio de un autónomo de {sector} \
(fontanero, electricista, reformas, limpieza, jardinería...). Hablas por WhatsApp.

Tu misión: quitarle ruido mental. Te ocupas de su agenda, sus clientes, sus \
presupuestos, sus cobros, sus facturas, sus gastos, sus proyectos, su equipo, sus \
documentos y la coordinación con su gestoría para que él solo tenga que hacer su \
trabajo.

QUÉ PUEDES HACER (y solo esto)
- Agendar trabajos y consultar la agenda de un día.
- Crear presupuestos y facturas en BORRADOR, registrar gastos.
- Crear una ficha de cliente o proveedor cuando el usuario lo pida expresamente.
- Preparar tickets de venta como factura simplificada F2 solo cuando el usuario
  diga explícitamente "ticket de venta" o "factura simplificada". Una foto de un
  ticket o "ticket de 20 euros" es un gasto, no una venta.
- Consultar cobros pendientes, el resumen del mes y la lista de clientes.
- Consultar proyectos, trabajos, tareas, horas, costes, documentos, equipo y gestoría.
- Crear proyectos y tareas cuando el usuario lo pida expresamente.
Usa SIEMPRE las herramientas para consultar o hacer cosas. Nunca te inventes \
cifras, fechas, clientes ni importes: si no tienes el dato, consúltalo con una \
herramienta o pídelo. Si te preguntan algo de lo que no hay dato, dilo con \
honestidad en vez de adivinar.

Una factura creada por chat siempre queda en borrador. Emitir, numerar o entregar
requiere una confirmación separada del titular; no afirmes que la has enviado solo
porque el borrador se haya creado.

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
el control de Bynoesis si hay dudas.

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


def _system_with_business_context(business_id: int, business: dict) -> str:
    """Construye el mismo marco verificable para cualquier proveedor de IA."""
    memories = [item for item in db.list_memories(business_id)
                if item.get("user_confirmed") and item.get("scope_type") != "language_rule"][:12]
    signals = [item for item in db.client_insights(business_id)
               if item.get("level") in {"alto", "medio"}][:3]
    permissions = db.automation_catalog(business_id)
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
    system = _system_prompt(business)
    if context_bits:
        system += "\n\nCONTEXTO DURABLE DEL NEGOCIO\n" + "\n".join(context_bits)
    return system


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
        """Procesa un mensaje del autónomo y devuelve la respuesta de Bynoesis."""
        with self._lock:
            self._mutated_in_send = False
            try:
                return self._send_locked(user_text)
            except Exception as exc:
                if self._mutated_in_send:
                    raise PartialAgentExecutionError(
                        "La consulta falló después de una posible escritura."
                    ) from exc
                raise

    def _record_usage(self, resp, duration_ms: int | None = None) -> None:
        """Apunta tokens y coste estimado de cada llamada para operaciones."""
        try:
            import json as _json

            usage = getattr(resp, "usage", None)
            is_fallback = self.model == config.FALLBACK_MODEL
            input_rate = (
                config.FALLBACK_INPUT_USD_PER_MTOK
                if is_fallback else config.MODEL_INPUT_USD_PER_MTOK
            )
            output_rate = (
                config.FALLBACK_OUTPUT_USD_PER_MTOK
                if is_fallback else config.MODEL_OUTPUT_USD_PER_MTOK
            )
            db.record_product_event(
                self.business_id,
                "ai_usage",
                _json.dumps({
                    "provider": "anthropic",
                    "model": self.model,
                    "in": getattr(usage, "input_tokens", 0) or 0,
                    "out": getattr(usage, "output_tokens", 0) or 0,
                    "estimated_cost_usd": _estimated_cost_usd(
                        getattr(usage, "input_tokens", 0) or 0,
                        getattr(usage, "output_tokens", 0) or 0,
                        input_rate,
                        output_rate,
                    ),
                    "duration_ms": duration_ms,
                }, separators=(",", ":")),
            )
            db.record_integration_result(self.business_id, "ai_external")
        except Exception:  # noqa: BLE001 — la métrica jamás rompe el chat
            pass

    def _send_locked(self, user_text: str) -> str:
        _refresh_conversation(self)
        if len(self.messages) > 32:
            self.messages = self.messages[-24:]
            while self.messages and self.messages[0].get("role") != "user":
                self.messages.pop(0)
        self.messages.append({"role": "user", "content": user_text})
        self.business = db.get_business(self.business_id) or self.business
        system = _system_with_business_context(self.business_id, self.business)

        safe_tools = [
            tool for tool in TOOLS
            if tool["name"] not in {"enviar_factura", "registrar_pago"}
        ]
        allowed_tools = {tool["name"] for tool in safe_tools}
        for _round in range(6):
            started = time.monotonic()
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                thinking=config.ai_thinking(),
                system=system,
                tools=safe_tools,
                messages=self.messages,
            )
            duration_ms = round((time.monotonic() - started) * 1000)
            self._record_usage(resp, duration_ms)
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
                    if block.name in allowed_tools and block.name in _MUTATING_TOOLS:
                        self._mutated_in_send = True
                    output = (run_tool(block.name, block.input, self.business_id)
                              if block.name in allowed_tools else
                              json.dumps({"error": "La herramienta no está autorizada."}))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })
            self.messages.append({"role": "user", "content": tool_results})
        if self._mutated_in_send:
            return (
                "He detenido la operación después de preparar una acción. "
                "Revisa la actividad reciente antes de volver a pedírmela."
            )
        return (
            "He detenido la operación porque necesitó demasiados pasos. "
            "Prueba a pedírmelo de una forma más concreta."
        )


class OpenAICompatibleNoesisAgent:
    """Agente con herramientas sobre un endpoint OpenAI-compatible validado."""

    def __init__(
        self,
        business_id: int,
        *,
        provider: str,
        model: str,
        chat_callable,
        integration_key: str,
        input_usd_per_mtok: float = 0,
        output_usd_per_mtok: float = 0,
    ):
        self.business_id = business_id
        self.provider = provider
        self.model = model
        self.chat_callable = chat_callable
        self.integration_key = integration_key
        self.input_usd_per_mtok = input_usd_per_mtok
        self.output_usd_per_mtok = output_usd_per_mtok
        self.business = db.get_business(business_id) or {}
        history = db.list_assistant_messages(business_id, limit=24)
        if history and history[-1].get("role") == "user":
            history = history[:-1]
        self.messages: list[dict] = [
            {"role": item["role"], "content": item["content"]}
            for item in history if item.get("role") in {"user", "assistant"}
        ]
        self._lock = threading.Lock()

    def send(self, user_text: str) -> str:
        with self._lock:
            self._mutated_in_send = False
            try:
                return self._send_locked(user_text)
            except Exception as exc:
                if self._mutated_in_send:
                    raise PartialAgentExecutionError(
                        "La consulta falló después de una posible escritura."
                    ) from exc
                raise

    def _record_usage(self, response: dict, duration_ms: int) -> None:
        try:
            usage = response.get("usage") or {}
            input_tokens = int(usage.get("prompt_tokens") or 0)
            output_tokens = int(usage.get("completion_tokens") or 0)
            db.record_product_event(
                self.business_id,
                "ai_usage",
                json.dumps({
                    "provider": self.provider,
                    "model": self.model,
                    "in": input_tokens,
                    "out": output_tokens,
                    "estimated_cost_usd": _estimated_cost_usd(
                        input_tokens,
                        output_tokens,
                        self.input_usd_per_mtok,
                        self.output_usd_per_mtok,
                    ),
                    "duration_ms": duration_ms,
                }, separators=(",", ":")),
            )
            db.record_integration_result(
                self.business_id, self.integration_key
            )
        except Exception:  # noqa: BLE001 - observar nunca rompe el chat
            pass

    def _send_locked(self, user_text: str) -> str:
        _refresh_conversation(self)
        if len(self.messages) > 32:
            self.messages = self.messages[-24:]
            while self.messages and self.messages[0].get("role") != "user":
                self.messages.pop(0)
        self.messages.append({"role": "user", "content": user_text})
        self.business = db.get_business(self.business_id) or self.business
        system = _system_with_business_context(self.business_id, self.business)
        safe_tools = [
            tool for tool in TOOLS
            if tool["name"] not in {"enviar_factura", "registrar_pago"}
        ]
        allowed_tools = {tool["name"] for tool in safe_tools}
        for _round in range(6):
            started = time.monotonic()
            response = self.chat_callable(
                system=system, messages=self.messages, tools=safe_tools
            )
            duration_ms = round((time.monotonic() - started) * 1000)
            self._record_usage(response, duration_ms)
            message = response["choices"][0]["message"]
            content = message.get("content") or ""
            raw_calls = message.get("tool_calls") or []
            tool_calls = [call for call in raw_calls if isinstance(call, dict)]
            assistant_message = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            self.messages.append(assistant_message)
            if not tool_calls:
                return content.strip() or (
                    "No he podido concretar una respuesta. Dímelo de otra forma."
                )
            for call in tool_calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                try:
                    arguments = function.get("arguments") or "{}"
                    args = (
                        arguments
                        if isinstance(arguments, dict)
                        else json.loads(arguments)
                    )
                    if not isinstance(args, dict):
                        raise ValueError("Los argumentos no son un objeto.")
                    if name not in allowed_tools:
                        raise ValueError("La herramienta no está autorizada.")
                    if name in _MUTATING_TOOLS:
                        self._mutated_in_send = True
                    output = run_tool(name, args, self.business_id)
                except Exception as exc:  # noqa: BLE001 - el modelo puede corregirse
                    output = json.dumps({"error": str(exc)}, ensure_ascii=False)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": str(call.get("id") or name),
                    "content": output,
                })
        if self._mutated_in_send:
            return (
                "He detenido la operación después de preparar una acción. "
                "Revisa la actividad reciente antes de volver a pedírmela."
            )
        return (
            "He detenido la operación porque necesitó demasiados pasos. "
            "Prueba a pedírmelo de una forma más concreta."
        )


class LocalNoesisAgent(OpenAICompatibleNoesisAgent):
    """Agente servido en infraestructura privada; no consume créditos externos."""

    def __init__(self, business_id: int):
        if not ai_adapter.local_available():
            raise RuntimeError("La IA privada no está configurada.")
        super().__init__(
            business_id,
            provider="local",
            model=config.LOCAL_AI_MODEL,
            chat_callable=ai_adapter.local_chat,
            integration_key="ai_local",
        )


class CompatibleNoesisAgent(OpenAICompatibleNoesisAgent):
    """Agente externo barato; requiere consentimiento y crédito antes de crearlo."""

    def __init__(self, business_id: int):
        if not ai_adapter.external_available():
            raise RuntimeError("La IA compatible externa no está configurada.")
        super().__init__(
            business_id,
            provider=config.COMPAT_AI_PROVIDER or "compatible",
            model=config.COMPAT_AI_MODEL,
            chat_callable=ai_adapter.external_chat,
            integration_key="ai_external",
            input_usd_per_mtok=config.COMPAT_AI_INPUT_USD_PER_MTOK,
            output_usd_per_mtok=config.COMPAT_AI_OUTPUT_USD_PER_MTOK,
        )


def daily_summary_text(business_id: int) -> str:
    """Genera el resumen proactivo del día (el 'parte de la mañana').

    Esto es lo que Bynoesis enviaría solo cada mañana por WhatsApp: la función
    estrella para reducir ruido mental.
    """
    today = date.today().isoformat()
    jobs = db.jobs_for_date(today, business_id)
    pend = db.pending_payments(business_id)
    total_pend = round(sum(p["total"] for p in pend), 2)
    sin_confirmar = [j for j in jobs if j["status"] == "pendiente"]
    team_pending = db.list_worker_submissions(
        business_id, status="pending", limit=100
    )
    customer_inbox = [
        item for item in db.list_whatsapp_inbox(business_id, limit=100)
        if item.get("conversation_status") == "waiting_owner"
    ]

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

    if team_pending:
        blockers = sum(item.get("kind") == "blocker" for item in team_pending)
        pending_cost = round(sum(
            float(item.get("amount") or 0) for item in team_pending
            if item.get("kind") == "cost"
        ), 2)
        detail = f" · {pending_cost:.2f} € en costes" if pending_cost else ""
        priority = f" · {blockers} bloqueo(s)" if blockers else ""
        lines.append(
            f"\n👷 Equipo: {len(team_pending)} aportación(es) por revisar"
            f"{detail}{priority}."
        )
    if customer_inbox:
        urgent = sum(bool(item.get("human_handoff")) for item in customer_inbox)
        priority = f" · {urgent} urgente(s)" if urgent else ""
        lines.append(
            f"\n💬 Clientes: {len(customer_inbox)} conversación(es) esperan "
            f"respuesta{priority}."
        )

    lines.append("\n¿Quieres que confirme yo a los clientes o reordene la ruta?")
    return "\n".join(lines)
