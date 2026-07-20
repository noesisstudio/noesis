"""Cerebro local de Noesis (NLU por reglas) — sin coste, sin APIs externas.

Resuelve los comandos más frecuentes (facturar, agendar, gastos, cobros, resumen)
con expresiones regulares y un pequeño parser de fechas en español. Así el chatbot
de la web funciona GRATIS y los datos no salen del servidor. Solo lo que no entiende
se delega (opcionalmente) a la IA en la nube. Es la arquitectura híbrida recomendada:
local para lo rutinario, IA solo para lo complejo.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

_WEEKDAYS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _norm(s: str) -> str:
    return _strip_accents(s.lower()).strip()


def _parse_amount(text: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?|eur\b)", text, re.I)
    if not m:
        m = re.search(r"(\d+(?:[.,]\d{1,2})?)", text)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def _parse_time(norm: str) -> tuple[int, int] | None:
    m = re.search(r"a las (\d{1,2})(?:[:h](\d{2}))?(?:\s*y media)?", norm)
    if m:
        h = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else (30 if "y media" in norm else 0)
        return h, mn
    if "manana" in norm:
        return 9, 0
    if "mediodia" in norm:
        return 12, 0
    if "tarde" in norm:
        return 16, 0
    if "noche" in norm:
        return 19, 0
    return None


def parse_date(text: str, base: date | None = None) -> str | None:
    """Convierte fechas en español a ISO. Devuelve None si no encuentra fecha."""
    base = base or date.today()
    norm = _norm(text)
    day: date | None = None
    if "pasado manana" in norm:
        day = base + timedelta(days=2)
    elif re.search(r"\bmanana\b", norm.replace("por la manana", "")):
        day = base + timedelta(days=1)
    if "hoy" in norm:
        day = base
    for name, wd in _WEEKDAYS.items():
        if re.search(rf"\b{name}\b", norm):
            delta = (wd - base.weekday()) % 7
            delta = delta or 7  # el "lunes" significa el próximo, no hoy
            day = base + timedelta(days=delta)
            break
    if day is None:
        return None
    t = _parse_time(norm)
    if t:
        return datetime(day.year, day.month, day.day, t[0], t[1]).isoformat(timespec="minutes")
    return day.isoformat()


# --------------------------------------------------------------------------- #
# Parser de intención -> (tool, args)
# --------------------------------------------------------------------------- #
HELP = "__help__"


def _parse_doc_command(text: str, norm: str, verb_re: str) -> dict | None:
    """Parser flexible para facturas y presupuestos. Acepta varios órdenes naturales:
      - "factura a Juan por reparación de grifo 95 euros"  (concepto antes de importe)
      - "factura a Juan 95€ por reparación de grifo"       (importe antes de concepto)
      - "factura a Juan 95 euros"                          (sin concepto explícito)
    """
    # Orden 1: verbo a CLIENTE por CONCEPTO IMPORTE
    m = re.search(verb_re + r"\s+(?:a|para|per\s+a)\s+(.+?)\s+(?:por|de|per)\s+(.+?)[,]?\s*"
                  r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?|eur)?$", text, re.I)
    if m:
        return {"cliente": m.group(1).strip(), "concepto": m.group(2).strip(),
                "base": float(m.group(3).replace(",", "."))}
    # Orden 2: verbo a CLIENTE IMPORTE por CONCEPTO
    m = re.search(verb_re + r"\s+(?:a|para|per\s+a)\s+(.+?)\s+"
                  r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?|eur)\s+"
                  r"(?:por|de|per)\s+(.+)", text, re.I)
    if m:
        return {"cliente": m.group(1).strip(), "concepto": m.group(3).strip(),
                "base": float(m.group(2).replace(",", "."))}
    # Orden 3: verbo a CLIENTE IMPORTE (sin concepto, "Servicio" por defecto)
    m = re.search(verb_re + r"\s+(?:a|para|per\s+a)\s+(.+?)\s+"
                  r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?|eur)", text, re.I)
    if m:
        return {"cliente": m.group(1).strip(), "concepto": "Servicio",
                "base": float(m.group(2).replace(",", "."))}
    return None


def _add_tax_rates(norm: str, args: dict) -> None:
    vat = re.search(r"\biva\s*(?:del|al)?\s*(0|4|10|21)\s*%?", norm)
    irpf = re.search(r"\birpf\s*(?:del|al)?\s*(0|7|15)\s*%?", norm)
    if vat:
        args["iva"] = float(vat.group(1))
    if irpf:
        args["irpf"] = float(irpf.group(1))


def _parse_simplified_sale(text: str, norm: str) -> dict | None:
    """Interpreta solo tickets DE VENTA; una foto o un ticket suelto sigue siendo gasto."""
    explicit = bool(
        re.search(r"\b(?:ticket|tiquet)\s+de\s+(?:venta|venda)\b", norm)
        or "factura simplificada" in norm
    )
    if not explicit:
        return None
    verb = (
        r"factura\s+simplificada"
        if "factura simplificada" in norm
        else r"(?:ticket|tiquet)\s+de\s+(?:venta|venda)"
    )
    args = _parse_doc_command(text, norm, verb)
    if not args:
        patterns = (
            verb + r"\s+(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?|eur)\s+"
            r"(?:por|de|per)\s+(.+)$",
            verb + r"\s+(?:por|de|per)\s+(.+?)[,]?\s*"
            r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?|eur)?$",
        )
        first = re.search(patterns[0], text, re.I)
        second = re.search(patterns[1], text, re.I) if not first else None
        if first:
            args = {
                "cliente": "", "concepto": first.group(2).strip(),
                "base": float(first.group(1).replace(",", ".")),
            }
        elif second:
            args = {
                "cliente": "", "concepto": second.group(1).strip(),
                "base": float(second.group(2).replace(",", ".")),
            }
        else:
            amount = _parse_amount(text)
            if amount is not None:
                args = {"cliente": "", "concepto": "Venta", "base": amount}
    if not args:
        return None
    args["tipo_factura"] = "F2"
    # En un ticket el importe que dicta el autónomo es normalmente el PVP final.
    args["importe_incluye_iva"] = True
    _add_tax_rates(norm, args)
    return args


def parse(text: str) -> tuple[str, dict] | None:
    norm = _norm(text)

    if norm in {"hola", "hey", "buenas", "ayuda", "help", "que puedes hacer"}:
        return (HELP, {})

    # --- Centro de control: límites reales de Noesis
    if re.search(r"(que puedes hacer solo|que puedes hacer sin|permisos de noesis|control de noesis|"
                 r"que haces sin preguntar|autonomia)", norm):
        return ("ver_control_noesis", {})

    # --- Crear proyecto sencillo, local y sin IA
    if "proyect" in norm and re.search(r"\b(crea|crear|nuevo|abre)\b", norm):
        m = re.search(
            r"(?:proyecto|obra)\s+(.+?)\s+(?:de|por|presupuesto)\s+"
            r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?|eur)?(?:\s|$)",
            text, re.I,
        )
        if m:
            return ("crear_proyecto", {
                "nombre": m.group(1).strip(),
                "presupuesto": float(m.group(2).replace(",", ".")),
            })

    # --- Crear presupuesto: acepta varios órdenes naturales ---
    if "presupuest" in norm or "pressupost" in norm:
        args = _parse_doc_command(
            text, norm, r"(?:presupuest(?:o|ar|a|ame)?|pressupost(?:ar|a|am)?)"
        )
        if args:
            _add_tax_rates(norm, args)
            return ("crear_presupuesto", args)

    # --- Facturar un trabajo ya cerrado sin reescribir cliente ni concepto ---
    work_invoice = re.search(
        r"\b(?:factura|facturar)\s+(?:el\s+)?(?:trabajo|treball)\s*#?\s*(\d+)\b", norm
    )
    if work_invoice:
        return ("preparar_factura_trabajo", {
            "trabajo_id": int(work_invoice.group(1)),
        })

    # --- Ticket de venta / factura simplificada explícita ---
    simplified = _parse_simplified_sale(text, norm)
    if simplified:
        return ("crear_factura", simplified)

    # --- Crear factura: acepta varios órdenes naturales ---
    if "factura" in norm:
        args = _parse_doc_command(text, norm, r"factura(?:r|me)?")
        if args:
            args["tipo_factura"] = "F1"
            _add_tax_rates(norm, args)
            return ("crear_factura", args)

    # --- Registrar gasto: "gasto 45 en gasolina", "gasté 45 de material",
    #     "me he gastado 45", "compré 30 de tornillos", "ticket de 12"
    if re.search(r"\bgast", norm) or re.search(r"\bcompr[eaoé]", norm) \
            or re.search(r"\b(ticket|recibo)\b", norm) or norm.startswith("gasto"):
        amount = _parse_amount(text)
        if amount is not None:
            cm = re.search(r"(?:en|de|por)\s+([a-záéíóúñ ]+)", text, re.I)
            concepto = cm.group(1).strip() if cm else "Gasto"
            return ("registrar_gasto", {"concepto": concepto, "importe": amount})

    # --- Agenda: "agenda a Marta el jueves por la mañana en Badalona"
    if re.search(r"\b(agenda|agendame|apunta|apuntame|cita|reserva)\b", norm):
        fecha = parse_date(text)
        # Nombre tras "a/con/para": 1ª palabra siempre, 2ª solo si va en mayúscula
        # (así "Marta el jueves" captura "Marta", no "Marta el").
        cm = re.search(r"\b(?:a|con|para)\b\s+([A-Za-záéíóúñ]+)"
                       r"(?:\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+))?", text)
        cliente = None
        if cm:
            cliente = cm.group(1) + (f" {cm.group(2)}" if cm.group(2) else "")
            cliente = cliente.strip()
        zona = None
        zm = re.search(r"\ben\s+([A-Za-záéíóúñ ]+)$", text.strip())
        if zm:
            zona = zm.group(1).strip()
        if cliente and fecha:
            return ("agendar_trabajo", {
                "cliente": cliente, "descripcion": "Trabajo", "fecha_hora": fecha,
                **({"zona": zona} if zona else {}),
            })
        return ("__need_date__", {})

    # --- Ver agenda de hoy
    if re.search(r"(que tengo|que hay|trabajos|citas|que toca).*hoy", norm) \
            or "agenda de hoy" in norm or norm in {"hoy", "que tengo hoy"}:
        return ("ver_agenda", {"fecha": date.today().isoformat()})

    # --- Cobros pendientes
    if re.search(r"(cobr|por cobrar|quien me debe|pendiente de cobro|me deben|"
                 r"deudas?|sin cobrar|impagad|moroso|facturas? pendientes?)", norm):
        return ("ver_cobros_pendientes", {})

    # --- Operativa conectada
    if re.search(r"\b(proyectos?|obras?)\b", norm):
        return ("ver_proyectos", {})
    if re.search(r"(equipo|trabajadores?|quien ha fichado|fichajes? de hoy)", norm):
        return ("ver_equipo", {})
    if re.search(r"(documentos?|papeles?|tickets?).*(pendient|revis)", norm):
        return ("ver_documentos_pendientes", {})
    if re.search(r"(gestoria|gestor).*(pide|solicitud|pendient)", norm):
        return ("ver_solicitudes_gestoria", {})

    # --- Resumen / ingresos
    if re.search(r"(cuanto.*facturad|ingresos|resumen|como va|como voy|que tal va|"
                 r"balance|beneficio|facturacion|este mes|mis numeros|cuanto llevo)", norm):
        return ("resumen_negocio", {})

    # --- Clientes
    if re.search(r"\bclientes?\b", norm):
        return ("listar_clientes", {})

    return None


# --------------------------------------------------------------------------- #
# Respuestas en lenguaje natural para el camino local.
# --------------------------------------------------------------------------- #
def _eur(n) -> str:
    return f"{(n or 0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def help_text() -> str:
    return ("Soy Noesis. No soy un chat para entretenerte: soy tu oficina pequeña.\n\n"
            "Puedo registrar cosas y también ayudarte a decidir qué toca mirar:\n"
            "• «Factura a Juan por cambio de grifo 95 euros»\n"
            "• «Ticket de venta por desplazamiento 36,30 euros»\n"
            "• «Emitir y enviar factura 12» (te pediré confirmación)\n"
            "• «Presupuesto a Ana por reforma de baño 1200 euros»\n"
            "• «Agenda a Marta el jueves por la mañana en Badalona»\n"
            "• «Gasté 45 euros en gasolina»\n"
            "• «¿Qué tengo hoy?»\n"
            "• «¿Quién me debe?»\n"
            "• «¿Cómo van mis proyectos?»\n"
            "• «¿Qué documentos tengo pendientes?»\n"
            "• «¿Qué puedes hacer sin preguntarme?»\n"
            "• «¿Qué harías tú ahora?»")


def format_reply(tool: str, result: dict) -> str:
    if result.get("error"):
        return f"Uy, algo no ha ido bien: {result['error']}"

    if tool == "crear_factura":
        f = result["factura"]
        desglose = f"base {_eur(f['base'])} + IVA {_eur(f['vat_amount'])}"
        if f.get("irpf_amount"):
            desglose += f" − IRPF {_eur(f['irpf_amount'])}"
        label = "Ticket de venta" if f.get("invoice_type") == "F2" else "Factura"
        return (f"🧾 {label} #{f['id']} preparado para {f['client_name']}: "
                f"**{_eur(f['total'])}** ({desglose}). Lo dejo en borrador para "
                f"que lo revises. Cuando esté correcto, escribe «emitir factura "
                f"{f['id']}»; para entregarlo también, «emitir y enviar factura "
                f"{f['id']}».")
    if tool == "preparar_factura_trabajo":
        f = result["factura"]
        return (
            f"🧾 El trabajo ya está conectado con el borrador #{f['id']} de "
            f"{_eur(f['total'])}. Revísalo y escribe «emitir factura {f['id']}» "
            "cuando esté correcto."
        )
    if tool == "crear_presupuesto":
        q = result["presupuesto"]
        desglose = f"base {_eur(q['base'])} + IVA {_eur(q['vat_amount'])}"
        if q.get("irpf_amount"):
            desglose += f" − IRPF {_eur(q['irpf_amount'])}"
        return (f"📝 Presupuesto preparado para {q['client_name']}: **{_eur(q['total'])}** "
                f"({desglose}). Lo tienes en Presupuestos: envíalo y, si lo aceptan, "
                "se convierte en factura con un clic.")
    if tool == "registrar_gasto":
        g = result["gasto"]
        return (f"📉 Gasto registrado: {g['concept']} — {_eur(g['amount'])}.\n"
                "Bien hecho: gasto apuntado al momento, beneficio más real.")
    if tool == "agendar_trabajo":
        t = result["trabajo"]
        cuando = t["scheduled_for"].replace("T", " a las ") if t.get("scheduled_for") else "—"
        return (f"📅 Agendado: {result['cliente']['name']} · {cuando}.\n"
                "Lo importante ahora: que no se quede sin facturar cuando termines.")
    if tool == "ver_agenda":
        jobs = result["trabajos"]
        if not jobs:
            return "📅 Hoy no tienes trabajos agendados. Buen momento para revisar cobros o registrar gastos pendientes."
        lines = [f"📅 Tienes {len(jobs)} trabajo(s) hoy. Yo prepararía el día así:"]
        for j in jobs:
            h = j["scheduled_for"].split("T")[1] if j.get("scheduled_for") and "T" in j["scheduled_for"] else ""
            lines.append(f"• {h} {j.get('client_name') or ''} — {j['description']}")
        lines.append("Al cerrar cada trabajo, deja la factura preparada. Ahí se escapa mucho dinero.")
        return "\n".join(lines)
    if tool == "ver_cobros_pendientes":
        if result["n"] == 0:
            return "✅ No tienes cobros pendientes. Caja limpia. Mantén el hábito: revisarlo una vez al día basta."
        lines = [f"💸 Hay {result['n']} factura(s) sin cobrar: **{_eur(result['total_pendiente'])}**."]
        for p in result["facturas"]:
            d = p.get("days_outstanding")
            lines.append(f"• {p['client_name']}: {_eur(p['total'])}" + (f" ({d} días)" if d else ""))
        lines.append("Mi consejo: reclama primero las de más de 7 días, corto y sin disculparte.")
        return "\n".join(lines)
    if tool == "resumen_negocio":
        r = result
        return (f"📊 Lectura del mes: facturado **{_eur(r['invoiced'])}**, cobrado {_eur(r['collected'])}, "
                f"pendiente {_eur(r['pending'])}, gastos {_eur(r['expenses'])}.\n\n"
                f"Beneficio estimado: **{_eur(r['estimated_profit'])}**. "
                f"Aparta al menos {_eur(r['vat_estimated'])} de IVA para no confundirte: no es caja libre.")
    if tool == "listar_clientes":
        cs = result["clientes"]
        if not cs:
            return "Aún no tienes clientes guardados."
        return "👥 Tus clientes: " + ", ".join(c["name"] for c in cs) + "."
    if tool == "ver_proyectos":
        projects = result.get("projects") or []
        if not projects:
            return "Aún no tienes proyectos. Si me dices nombre y presupuesto, preparo el primero."
        lines = [
            f"🧰 Tienes {result['active_count']} proyecto(s) activo(s). "
            f"Quedan {_eur(result['margin'])} antes de consumir el presupuesto."
        ]
        for project in projects[:6]:
            lines.append(
                f"• {project['name']}: {project['progress']}% · "
                f"gastado {_eur(project['actual_cost'])} · "
                f"margen {_eur(project['margin'])}"
            )
        return "\n".join(lines)
    if tool == "crear_proyecto":
        project = result["proyecto"]
        return (
            f"🧰 Proyecto creado: {project['name']} · presupuesto "
            f"{_eur(project['budget'])}. Ahora conecta trabajos y equipo para que "
            "las horas y el margen se actualicen solos."
        )
    if tool == "ver_equipo":
        people = result.get("personas") or []
        today = result.get("jornada_hoy") or []
        inside = [item for item in today if item.get("working")]
        return (
            f"👷 Equipo: {len(people)} persona(s). "
            f"Ahora mismo {len(inside)} tienen la jornada abierta."
        )
    if tool == "ver_documentos_pendientes":
        return (
            "📎 No tienes documentos pendientes de revisar."
            if not result.get("n") else
            f"📎 Hay {result['n']} documento(s) esperando tu confirmación. "
            "Los encontrarás en Documentos."
        )
    if tool == "ver_solicitudes_gestoria":
        return (
            "Tu gestoría no tiene solicitudes abiertas."
            if not result.get("n") else
            f"Tu gestoría tiene {result['n']} solicitud(es) abiertas. "
            "Te digo cuál atender primero si quieres."
        )
    if tool == "ver_control_noesis":
        automatic = [p for p in result["permisos"] if p["modo"] == "automatic"]
        confirmed = [p for p in result["permisos"] if p["modo"] == "confirm"]
        return (
            f"Puedo ocuparme solo de {len(automatic)} tipo(s) de tarea interna. "
            f"En {len(confirmed)} acción(es) siempre te pregunto. Transferencias, "
            "impuestos, devoluciones y borrados nunca son automáticos."
        )
    return "Hecho."
