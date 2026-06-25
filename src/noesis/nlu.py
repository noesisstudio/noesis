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
    elif "manana" in norm and "por la manana" not in norm.replace("manana", "manana", 1):
        # "mañana" como día (evita confundir con "por la mañana")
        if re.search(r"\bmanana\b", norm) and "a las" not in norm or "manana" in norm:
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


def parse(text: str) -> tuple[str, dict] | None:
    norm = _norm(text)

    if norm in {"hola", "hey", "buenas", "ayuda", "help"} or "que puedes hacer" in norm:
        return (HELP, {})

    # --- Crear factura: "factura a X por Y 95 euros [más iva]"
    if "factura" in norm:
        m = re.search(r"factura(?:r)?\s+a\s+(.+?)\s+por\s+(.+?)[,]?\s*"
                      r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?|eur)?", text, re.I)
        if m:
            return ("crear_factura", {
                "cliente": m.group(1).strip(),
                "concepto": m.group(2).strip(),
                "base": float(m.group(3).replace(",", ".")),
            })

    # --- Registrar gasto: "gasto 45 en gasolina", "gasté 45 euros de material"
    if re.search(r"\bgast", norm) or norm.startswith("gasto"):
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
    if re.search(r"(que tengo|que hay).*(hoy)", norm) or "agenda de hoy" in norm \
            or norm in {"hoy", "que tengo hoy"}:
        return ("ver_agenda", {"fecha": date.today().isoformat()})

    # --- Cobros pendientes
    if re.search(r"(cobr|por cobrar|quien me debe|pendiente de cobro|me deben|deudas?)", norm):
        return ("ver_cobros_pendientes", {})

    # --- Resumen / ingresos
    if re.search(r"(cuanto.*facturad|ingresos|resumen|como va|balance|beneficio|"
                 r"facturacion|este mes)", norm):
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
            "• «Agenda a Marta el jueves por la mañana en Badalona»\n"
            "• «Gasté 45 euros en gasolina»\n"
            "• «¿Qué tengo hoy?»\n"
            "• «¿Quién me debe?»\n"
            "• «¿Qué harías tú ahora?»")


def format_reply(tool: str, result: dict) -> str:
    if result.get("error"):
        return f"Uy, algo no ha ido bien: {result['error']}"

    if tool == "crear_factura":
        f = result["factura"]
        desglose = f"base {_eur(f['base'])} + IVA {_eur(f['vat_amount'])}"
        if f.get("irpf_amount"):
            desglose += f" − IRPF {_eur(f['irpf_amount'])}"
        return (f"🧾 Factura preparada para {f['client_name']}: **{_eur(f['total'])}** "
                f"({desglose}). La dejo en borrador para que puedas revisarla antes de enviarla.")
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
    return "Hecho."
