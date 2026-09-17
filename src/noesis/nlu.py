"""Cerebro local de Bynoesis (NLU por reglas) — sin coste, sin APIs externas.

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
from .intent_safety import inspect_money_intent

_WEEKDAYS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}

# Importe dictado en formato español: 1200, 1.200, 1.200,50 o 95,50.
_AMOUNT_RE = r"(?:\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)"


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _norm(s: str) -> str:
    return _strip_accents(s.lower()).strip().strip("¿?¡!.")


def _parse_amount(text: str) -> float | None:
    m = re.search(rf"({_AMOUNT_RE})\s*(?:€|euros?|eur\b)", text, re.I)
    if not m:
        m = re.search(rf"({_AMOUNT_RE})", text)
    if m:
        return _amount_value(m.group(1))
    return None


def _amount_value(value: str) -> float:
    compact = str(value).replace(" ", "")
    if "," in compact:
        compact = compact.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", compact):
        compact = compact.replace(".", "")
    return float(compact)


def _parse_time(norm: str) -> tuple[int, int] | None:
    m = re.search(r"a las (\d{1,2})(?:[:h](\d{2}))?(?:\s*y media)?", norm)
    if m:
        h = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else (30 if "y media" in norm else 0)
        return (h, mn) if 0 <= h <= 23 and 0 <= mn <= 59 else None
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
NEED_INVOICE = "__need_invoice__"
NEED_USER_INVITE = "__need_user_invite__"
NEED_REVIEW = "__need_review__"
NEED_DATE = "__need_date__"
# Un trabajo necesita cliente en la base de datos. Cuando la orden trae la fecha
# pero no el cliente, se pregunta solo eso en vez de descartar toda la frase.
NEED_JOB_CLIENT = "__need_job_client__"

# «Añade un trabajo para mañana a las 12» era una orden corriente que no se
# entendía: solo se reconocían agenda/apunta/cita/reserva y siempre con cliente.
_AGENDA_DIRECT = r"\b(?:agenda|agendame|agendar|apunta|apuntame|apuntar|cita|citas|reserva|reservar)\b"
_AGENDA_VERB = (
    r"\b(?:agenda\w*|apunta\w*|anade|anadir|anademe|agrega\w*|pon|ponme|poner|"
    r"crea\w*|programa\w*|mete|meter|reserva\w*|afegeix|afegir|posa|posar)\b"
)
_AGENDA_NOUN = r"\b(?:trabajo|trabajos|treball|treballs|cita|citas|visita|visites|visitas|servicio|aviso|faena|encargo)\b"
# Palabras con las que empieza una fecha: «para mañana» no nombra a un cliente.
_AGENDA_NOT_A_NAME = (
    r"^(?:hoy|manana|dema|pasado|el|la|los|las|proxim\w*|este|esta|lunes|martes|"
    r"miercoles|jueves|viernes|sabado|domingo|a\s+las|por\s+la|de\s+la|dia|"
    r"semana|mes|un|una|\d)"
)


def _is_agenda_order(norm: str) -> bool:
    if re.search(_AGENDA_NOUN, norm) and re.search(_AGENDA_VERB, norm):
        return True
    return bool(re.search(_AGENDA_DIRECT, norm))


def _looks_like_task(value: str) -> bool:
    """«para cambiar el termo» describe el trabajo; «para Marta» es el cliente.

    Un infinitivo en minúscula es tarea. La minúscula importa: «Oscar» también
    termina en -ar y es un nombre, así que una palabra capitalizada nunca se
    descarta por su terminación.
    """
    first = value.strip().split(" ")[0] if value.strip() else ""
    if not first or first[:1].isupper():
        return False
    return bool(re.fullmatch(r"\w{3,}(?:ar|er|ir)(?:se)?", _norm(first)))


def _agenda_client(text: str) -> str | None:
    """Nombre tras «a/con/para» que no sea una fecha, una tarea ni el sustantivo."""
    for match in re.finditer(
        r"\b(?:a|con|para|per\s+a)\s+(.+?)"
        r"(?=\s+(?:hoy|mañana|demà|pasado|el|la|los|las|próximo|proxima|a las|por la|en|para|de)\b|[,;]|$)",
        text, re.I,
    ):
        candidate = _limpiar_cliente(match.group(1))
        folded = _norm(candidate)
        if not candidate or len(candidate) > 60 or not folded:
            continue
        if re.match(_AGENDA_NOT_A_NAME, folded) or re.search(_AGENDA_NOUN, folded):
            continue
        if _looks_like_task(candidate) or not re.search(r"[a-z]", folded):
            continue
        return candidate
    return None


def _agenda_description(text: str, cliente: str | None) -> str:
    """Primer «para …» que describa una tarea; se corta en el siguiente «para»."""
    for match in re.finditer(r"\b(?:para|de)\s+(.+?)(?=\s+para\b|\s+en\s+|[,;]|$)", text, re.I):
        value = match.group(1).strip()
        folded = _norm(value)
        if (not value or value == cliente or len(value) > 200
                or re.match(_AGENDA_NOT_A_NAME, folded)
                or re.search(_AGENDA_NOUN, folded)):
            continue
        if _looks_like_task(value) or value != cliente:
            return value
    return "Trabajo"


def safety_refusal(text: str) -> str | None:
    """Una orden negativa o destructiva nunca se interpreta como un alta."""
    risk = inspect_money_intent(text)
    if risk:
        return risk.reply
    norm = _norm(text)
    # Verbos conjugados, no prefijos: «Carla Borràs» o «Cancelas» son nombres.
    if re.search(
        r"\b(borr(?:a|ar|ame|alo|ala|alos|alas|ad)|elimin(?:a|ar|ame|alo|ala|alos|alas|ad)|"
        r"anul(?:a|ar|alo|ala|ad)|cancel(?:a|ar|ame|alo|ala|ad)|esborr(?:a|ar|eu)|"
        r"suprim(?:e|ir|elo|ela|id))\b", norm):
        return ("No he cambiado nada. Para borrar, anular o cancelar un registro, "
                "ábrelo en su apartado y revisa la acción concreta.")
    if re.search(r"^(?:por favor[, ]+)?(cambia\w*|modifica\w*|mueve|reprograma\w*|rectifica\w*)\b", norm):
        return "Para modificar un registro existente, ábrelo en su apartado y revisa los nuevos datos. No he creado ni cambiado nada."
    if re.search(r"\b(transferencia|transfiere|transferir|devolucion|devuelve)\b", norm):
        return "No puedo mover dinero ni hacer transferencias o devoluciones. No he ejecutado ninguna operación."
    if re.search(r"\b(no|nunca)\b.*\b(cre\w*|ha\w*|registr\w*|factur\w*|apunt\w*|anad\w*|envi\w*|gast\w*|paga\w*)\b", norm):
        return "Entendido. No he registrado ni enviado nada."
    if re.search(r"\by va\s+(incluido|incluida)\b", norm):
        return "La transcripción del impuesto es dudosa. Escribe de nuevo la orden indicando «IVA incluido» o «más IVA». No he registrado nada."
    if re.search(r"(?:\by\s+|;\s*)(?:despues\s+)?(?:crea|factura a|registra|gaste|gasto \d+|agenda a)\b", norm):
        return "Revisemos una operación cada vez. Envíame primero una orden completa; no he guardado ninguna."
    return None


# Conectores que el hablante pone entre el nombre y el importe. El patron los
# arrastra al capturar hasta el numero, asi que "factura para Juan Perez de 250
# euros" dejaba un cliente llamado "Juan Perez de". Al dictar una factura por voz
# esa frase es la natural, y el nombre sucio crea un cliente nuevo mal escrito en
# vez de reconocer al que ya existe.
_CONECTORES_FINALES = ("de", "del", "por", "per", "para", "a", "en", "d")


def _limpiar_cliente(nombre: str) -> str:
    """Quita los conectores que se cuelan al final de un nombre dictado."""
    # «factura a nombre de Carla» / «a nom de Carla»: el cliente es Carla.
    nombre = re.sub(r"^(?:a\s+)?nom(?:bre)?\s+(?:de\s+|d')", "", str(nombre or "").strip(), flags=re.I)
    # «factura para el cliente Marta» no da de alta a nadie llamado «el cliente
    # Marta»: la palabra que describe el papel no forma parte del nombre.
    nombre = re.sub(r"^(?:el|la|els|les|l')\s+(?:client[ea]?|proveedor[a]?)\s+",
                    "", nombre, flags=re.I)
    partes = nombre.split()
    while partes and partes[-1].lower().strip(",.") in _CONECTORES_FINALES:
        partes.pop()
    return " ".join(partes).strip(" ,.")


def _parse_doc_command(text: str, norm: str, verb_re: str) -> dict | None:
    """Parser flexible para facturas y presupuestos. Acepta varios órdenes naturales:
      - "factura a Juan por reparación de grifo 95 euros"  (concepto antes de importe)
      - "factura a Juan 95€ por reparación de grifo"       (importe antes de concepto)
      - "factura a Juan 95 euros"                          (sin concepto explícito)
    """
    # Los impuestos son campos separados, nunca parte del cliente o concepto.
    text = re.sub(r"\s+(?:(?:con|más|mas)\s+)?(?:IVA|IRPF)\s*(?:(?:del|al)\s*)?(?:incluido|inclos|\d+(?:[.,]\d+)?\s*%?)", "", text, flags=re.I).strip(" ,.")
    # Variante frecuente: "factura a Juan de 100 euros". Debe resolverse antes
    # del patrón con concepto para que el 100 no se parta en "1" + "00".
    m = re.search(
        verb_re + rf"\s+(?:a|para|per\s+a)\s+(.+?)\s+(?:de|por|per)\s+"
        rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?$",
        text, re.I,
    )
    if m:
        return {
            "cliente": _limpiar_cliente(m.group(1)),
            "concepto": "Servicio",
            "base": _amount_value(m.group(2)),
        }
    # Orden 1: verbo a CLIENTE por CONCEPTO IMPORTE
    m = re.search(verb_re + r"\s+(?:a|para|per\s+a)\s+(.+?)\s+(?:por|de|per)\s+(.+?)[,]?\s*"
                  rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?$", text, re.I)
    if m:
        return {"cliente": _limpiar_cliente(m.group(1)), "concepto": m.group(2).strip(),
                "base": _amount_value(m.group(3))}
    # Orden 2: verbo a CLIENTE IMPORTE por CONCEPTO
    m = re.search(verb_re + r"\s+(?:a|para|per\s+a)\s+(.+?)\s+"
                  rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?\s+"
                  r"(?:por|de|per)\s+(.+)", text, re.I)
    if m:
        return {"cliente": _limpiar_cliente(m.group(1)), "concepto": m.group(3).strip(),
                "base": _amount_value(m.group(2))}
    # Orden 3: verbo a CLIENTE IMPORTE (sin concepto, "Servicio" por defecto)
    m = re.search(verb_re + r"\s+(?:a|para|per\s+a)\s+(.+?)\s+"
                  rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?(?:\s|$)", text, re.I)
    if m:
        return {"cliente": _limpiar_cliente(m.group(1)), "concepto": "Servicio",
                "base": _amount_value(m.group(2))}
    # Orden 4: verbo IMPORTE a CLIENTE por CONCEPTO.
    m = re.search(
        verb_re + rf"\s+(?:de\s+)?({_AMOUNT_RE})\s*(?:€|euros?|eur)?\s+"
        r"(?:a|para|per\s+a)\s+(.+?)(?:\s+(?:por|de|per)\s+(.+))?$",
        text, re.I,
    )
    if m:
        return {
            "cliente": _limpiar_cliente(m.group(2)),
            "concepto": (m.group(3) or "Servicio").strip(),
            "base": _amount_value(m.group(1)),
        }
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
    # «Créame un tiquet para Jana» es una venta explícita, no un gasto recibido.
    if re.match(r"^(?:crea\w*|hazme|fes\w*|prepara\w*)\s+(?:un\s+)?(?:ticket|tiquet)\b", norm):
        text = re.sub(r"\b(ticket|tiquet)\b(?!\s+de\s+(?:venta|venda))", "ticket de venta", text, count=1, flags=re.I)
        text = re.sub(r"\bconcepto\b", "por", text, flags=re.I)
        norm = _norm(text)
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
            verb + rf"\s+({_AMOUNT_RE})\s*(?:€|euros?|eur)\s+"
            r"(?:por|de|per)\s+(.+)$",
            verb + r"\s+(?:por|de|per)\s+(.+?)[,]?\s*"
            rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?$",
        )
        first = re.search(patterns[0], text, re.I)
        second = re.search(patterns[1], text, re.I) if not first else None
        if first:
            args = {
                "cliente": "", "concepto": first.group(2).strip(),
                "base": _amount_value(first.group(1)),
            }
        elif second:
            args = {
                "cliente": "", "concepto": second.group(1).strip(),
                "base": _amount_value(second.group(2)),
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

    refusal = safety_refusal(text)
    if refusal:
        return (NEED_REVIEW, {"reply": refusal})
    for field, allowed in (("iva", {0, 4, 10, 21}), ("irpf", {0, 7, 15})):
        rate = re.search(rf"\b{field}\s*(?:(?:del|al)\s*)?(\d+(?:[.,]\d+)?)(?![\w.,])", norm)
        if rate and float(rate.group(1).replace(",", ".")) not in allowed:
            return (NEED_REVIEW, {"reply": "El tipo fiscal indicado no está admitido. Revisa IVA e IRPF en Facturas; no he sustituido el porcentaje por otro."})
    if re.search(r"(?:que.*(?:trabajos|citas).*|agenda de )(hoy|mañana|demà)", text, re.I):
        when = parse_date(text)
        if when:
            return ("ver_agenda", {"fecha": when[:10]})
    # Un cobro no crea una factura. Los pagos parciales necesitan importe explícito
    # y se revisan en Facturas mientras el contrato de esta orden sea saldo total.
    if re.search(r"\b(pagado|cobrado|pago|cobro)\b", norm) and "factura" in norm:
        paid = re.search(r"\bfactura\s*#?\s*(\d+)\b", norm)
        if paid and re.search(r"\b(pagado|cobrado)\b", norm) and not re.search(r"\b(parcial|parte|euros|eur)\b|€", norm):
            return ("registrar_pago", {"factura_id": int(paid.group(1))})
        return (NEED_REVIEW, {"reply": "Para registrar un cobro parcial, abre la factura e indica el importe recibido. No he cambiado su estado."})

    if norm in {"hola", "hey", "buenas", "ayuda", "help", "que puedes hacer"}:
        return (HELP, {})

    # --- Centro de control: límites reales de Bynoesis
    # «(by)?noesis»: la marca cambió y quien escribe puede usar cualquiera de las dos.
    if re.search(r"(que puedes hacer solo|que puedes hacer sin|permisos de (?:by)?noesis|"
                 r"control de (?:by)?noesis|que haces sin preguntar|autonomia)", norm):
        return ("ver_control_noesis", {})

    # Altas explícitas: no hace falta crear una factura de rebote para guardar
    # una relación comercial. El acceso de una persona, en cambio, exige correo,
    # rol e invitación segura y no se concede desde una frase incompleta.
    party = re.search(
        # El artículo determinado entra igual que el indeterminado: «crea el
        # cliente Talleres Pino» se decía tan a menudo como «un cliente», y
        # antes caía en la regla de listar clientes sin dar de alta a nadie.
        r"\b(?:crea|crear|anade|añade|nuevo|nueva|alta)\s+"
        # «alta de cliente X» se dice tanto como «alta cliente X».
        r"(?:de\s+)?(?:un|una|el|la|los|las)?\s*"
        r"(cliente|proveedor)\s*:?\s+(.+?)\s*$",
        text, re.I,
    )
    if not party:
        # Orden inverso: primero el nombre y después el papel.
        inversa = re.search(
            r"\b(?:da|dar)\s+de\s+alta\s+(?:a\s+)?(.+?)\s+como\s+"
            r"(cliente|proveedor)\b",
            text, re.I,
        )
        if inversa:
            return (
                "crear_cliente" if _norm(inversa.group(2)) == "cliente"
                else "crear_proveedor",
                {"nombre": inversa.group(1).strip(" ,.")},
            )
    if party:
        name = re.sub(r"^(?:llamad[oa]|que se llama)\s+", "", party.group(2), flags=re.I).strip(" ,.")
        return (
            "crear_cliente" if _norm(party.group(1)) == "cliente" else "crear_proveedor",
            {"nombre": name},
        )
    if re.search(
        r"\b(?:crea|crear|anade|añade|nuevo|nueva|alta)\s+(?:un|una)?\s*usuario\b",
        norm,
    ):
        return (NEED_USER_INVITE, {})

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

    # --- Emitir un borrador ya revisado. El mensaje que confirma la creación
    #     sugiere esta misma orden, así que tiene que valer en la web igual que
    #     en WhatsApp; si no, el borrador se queda sin emitir.
    issue = re.search(
        r"\b(?:emitir\s+y\s+enviar|enviar\s+y\s+emitir|emitir|emite|emitela)\s+"
        r"(?:la\s+)?(?:factura|tiquet|ticket)\s*#?\s*(\d{1,9})\s*$",
        norm,
    )
    if issue:
        return ("enviar_factura", {"factura_id": int(issue.group(1))})

    # --- Crear factura: acepta varios órdenes naturales ---
    if "factura" in norm:
        args = _parse_doc_command(text, norm, r"fact[uú]ra(?:r|me)?")
        if args:
            args["tipo_factura"] = "F1"
            _add_tax_rates(norm, args)
            if "iva incluido" in norm or "iva inclos" in norm:
                args["importe_incluye_iva"] = True
            return ("crear_factura", args)
        if re.search(r"\b(?:hazme|crea|crear|nueva|quiero|necesito|prepara|factura)\b", norm):
            return (NEED_INVOICE, {})

    # --- Registrar gasto: "gasto 45 en gasolina", "gasté 45 de material",
    #     "me he gastado 45", "compré 30 de tornillos", "ticket de 12"
    if re.match(r"(?:(?:registra|registrar|apunta|añade|anade)\s+(?:un\s+)?)?(?:gasto\b|gaste\b|he gastado\b|me he gastado\b|compre\b|ticket\b|recibo\b)", norm):
        amount = _parse_amount(text)
        if amount is not None:
            cm = re.search(r"(?:en|de|por)\s+([a-záéíóúñ ]+)", text, re.I)
            concepto = cm.group(1).strip() if cm else "Gasto"
            args = {"concepto": concepto, "importe": amount}
            if re.search(r"\biva\b", norm):
                rate = re.search(r"\biva\s*(?:incluido|inclos)?\s*(?:del|al)?\s*(0|4|10|21)(?![\d.,])\s*%?", norm)
                if (not rate or not re.search(r"\b(?:incluido|inclos)\b", norm)
                        or re.search(r"\b(?:no\s+incluido|sin\s+iva|mas\s+iva)\b", norm)):
                    return (NEED_REVIEW, {"reply": "Para conservar el IVA del gasto, dime el importe final con IVA incluido y su porcentaje. No he registrado el gasto."})
                args["iva"] = int(rate.group(1))
            return ("registrar_gasto", args)

    # --- Agenda: «agenda a Marta el jueves por la mañana en Badalona» y también
    # «añade un trabajo para mañana a las 12», que antes no se entendía.
    if _is_agenda_order(norm):
        fecha = parse_date(text)
        cliente = _agenda_client(text)
        zona = None
        zm = re.search(r"\ben\s+([A-Za-záéíóúñ ]+)$", text.strip())
        if zm:
            zona = zm.group(1).strip()
        descripcion = _agenda_description(text, cliente)
        if cliente and fecha:
            return ("agendar_trabajo", {
                "cliente": cliente, "descripcion": descripcion, "fecha_hora": fecha,
                **({"zona": zona} if zona else {}),
            })
        if fecha:
            # La fecha se conserva: solo falta a quién, y eso se pregunta.
            return (NEED_JOB_CLIENT, {
                "fecha_hora": fecha, "descripcion": descripcion,
                **({"zona": zona} if zona else {}),
            })
        if cliente:
            return (NEED_DATE, {"cliente": cliente})
        return (NEED_REVIEW, {"reply": "Me falta el cliente o una fecha válida. Dime, por ejemplo: «agenda a Marta López mañana a las 10 para reparar la caldera». No he creado ninguna cita."})

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

    # --- Impuestos: va antes del resumen porque "como va mi iva" casa con ambos y
    # la pregunta fiscal es la concreta. El resumen del mes no responde al 303.
    if re.search(r"(\biva\b|\birpf\b|impuesto|hacienda|modelo\s*(303|130)|"
                 r"trimestral|declaracion)", norm):
        args: dict = {}
        trimestre = re.search(r"\b([1-4])\s*(?:t\b|er\s+trimestre|º?\s*trimestre)", norm)
        if trimestre:
            args["trimestre"] = int(trimestre.group(1))
        anio = re.search(r"\b(20\d{2})\b", norm)
        if anio:
            args["anio"] = int(anio.group(1))
        return ("ver_impuestos", args)

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
    return ("Soy Bynoesis. No soy un chat para entretenerte: soy tu oficina pequeña.\n\n"
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
    if result.get("confirmation_required"):
        return result["reply"]
    if result.get("error"):
        # El nombre de la herramienta le sirve al agente, no a quien lee: deja
        # solo el motivo, que es lo único accionable.
        motivo = re.sub(
            r"^Par[áa]metros inv[áa]lidos para \w+:\s*", "", str(result["error"])
        )
        return f"Uy, algo no ha ido bien: {motivo}"

    if tool == "crear_factura":
        f = result["factura"]
        desglose = f"base {_eur(f['base'])} + IVA {_eur(f['vat_amount'])}"
        if f.get("irpf_amount"):
            desglose += f" − IRPF {_eur(f['irpf_amount'])}"
        label = "Ticket de venta" if f.get("invoice_type") == "F2" else "Factura"
        aviso = result.get("aviso_fiscal")
        return (f"🧾 {label} #{f['id']} preparado para {f['client_name']}: "
                f"**{_eur(f['total'])}** ({desglose}). Lo dejo en borrador para "
                f"que lo revises. Cuando esté correcto, escribe «emitir factura "
                f"{f['id']}»; para entregarlo también, «emitir y enviar factura "
                f"{f['id']}»."
                + (f"\n\n⚠️ {aviso}" if aviso else ""))
    if tool == "registrar_pago":
        return f"Cobro registrado en la factura #{result['factura']['id']}."
    if tool == "crear_cliente":
        client = result["cliente"]
        suffix = " Ya existía; he reutilizado su ficha." if result.get("existing") else ""
        return f"Cliente guardado: **{client['name']}**.{suffix}"
    if tool == "crear_proveedor":
        supplier = result["proveedor"]
        suffix = " Ya existía; he reutilizado su ficha." if result.get("existing") else ""
        return f"Proveedor guardado: **{supplier['name']}**.{suffix}"
    if tool == "enviar_factura":
        f = result["factura"]
        quien = f.get("client_name") or f.get("recipient_name") or "tu cliente"
        return (
            f"✅ Factura **{f['number']}** emitida por {_eur(f['total'])} para "
            f"{quien}. Ya tiene número definitivo y cuenta en tus ingresos, "
            "impuestos y gestoría. El PDF y el envío al cliente los tienes en "
            "Facturas."
        )
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
            return f"No tienes trabajos agendados para {result['fecha']}."
        lines = [f"Tienes {len(jobs)} trabajo(s) para {result['fecha']}:"]
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
    if tool == "ver_impuestos":
        if not result.get("ok"):
            return result.get("error") or "No he podido calcular el trimestre."
        iva = result["iva_resultado"]
        signo = "a pagar" if iva >= 0 else "a tu favor"
        lines = [
            f"🧾 {result['label']}. IVA {signo}: **{_eur(abs(iva))}**.",
            f"• Repercutido {_eur(result['iva_repercutido'])} − soportado "
            f"{_eur(result['iva_soportado'])} (modelo 303)",
            f"• IRPF del periodo: {_eur(result['irpf_pago'])} (modelo 130)",
        ]
        if result["datos_incompletos"]:
            lines.append(
                f"⚠️ Hay {result['datos_incompletos']} apunte(s) sin IVA o sin base: "
                "la cifra se moverá cuando los completes."
            )
        lines.append(
            "Son cifras de apoyo con lo registrado hasta hoy. "
            "Quien presenta y valida es tu gestoría."
        )
        return "\n".join(lines)
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
