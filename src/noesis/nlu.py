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
    # Catalán: el producto se vende en Lleida y se habla en catalán a diario.
    "dilluns": 0, "dimarts": 1, "dimecres": 2, "dijous": 3,
    "divendres": 4, "dissabte": 5, "diumenge": 6,
}

# Importe dictado en formato español: 1200, 1.200, 1.200,50 o 95,50.
_AMOUNT_RE = r"(?:\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)"


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _norm(s: str) -> str:
    return _strip_accents(s.lower()).strip().strip("¿?¡!.")


# --------------------------------------------------- Números dictados ---
# Al dictar, el importe llega escrito en letra: «trescientos euros». El cerebro no
# veía ningún número y la orden entera se caía —«gasté treinta y cinco euros en
# gasolina» no registraba nada—, que es buena parte del «no me detecta el audio».
# Solo se traducen las cifras que van justo antes de «euros»: así un cliente
# llamado «Tres Torres» o «Ochoa» sigue siendo quien es.
_UNIDADES = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiuno": 21, "veintiun": 21, "veintiuna": 21,
    "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
    "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90,
    "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300, "cuatrocientos": 400,
    "cuatrocientas": 400, "quinientos": 500, "quinientas": 500,
    "seiscientos": 600, "seiscientas": 600, "setecientos": 700,
    "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
    "novecientos": 900, "novecientas": 900,
    # Catalán: el producto también habla catalán y se dicta igual de a menudo.
    "u": 1, "quatre": 4, "cinc": 5, "sis": 6, "set": 7, "vuit": 8, "nou": 9,
    "deu": 10, "onze": 11, "dotze": 12, "tretze": 13, "catorze": 14,
    "quinze": 15, "setze": 16, "disset": 17, "divuit": 18, "dinou": 19,
    "vint": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50, "seixanta": 60,
    "setanta": 70, "vuitanta": 80, "noranta": 90, "cent": 100, "cents": 100,
    "centes": 100,
}
_MULTIPLICADOR = {"mil": 1000, "millon": 1000000, "millones": 1000000,
                  "milions": 1000000, "milio": 1000000}
_PALABRA_NUMERO = set(_UNIDADES) | set(_MULTIPLICADOR) | {"y", "i"}


def _numero_en_letra(palabras: list[str]) -> int | None:
    """«treinta y cinco» → 35. `None` si la secuencia no es un número entero."""
    total = parcial = 0
    visto = False
    for palabra in palabras:
        if palabra in ("y", "i"):
            continue
        if palabra in _MULTIPLICADOR:
            factor = _MULTIPLICADOR[palabra]
            # «mil» a secas vale 1000; «dos mil», 2000.
            total += (parcial or 1) * factor
            parcial = 0
            visto = True
            continue
        if palabra not in _UNIDADES:
            return None
        parcial += _UNIDADES[palabra]
        visto = True
    return (total + parcial) if visto else None


def _sin_euros(match: re.Match) -> str:
    """Cifra dictada sin la palabra «euros», con sus céntimos si los lleva."""
    valor = _numero_en_letra(_norm(match.group("cifra")).split())
    if not valor or valor <= 0:
        return match.group(0)
    centimos = match.groupdict().get("centimos")
    if centimos:
        sueltos = _numero_en_letra(_norm(centimos).split())
        if sueltos is not None and 0 < sueltos < 100:
            return f"{match.group('marca')}{valor},{sueltos:02d}"
    return f"{match.group('marca')}{valor}"


def _cifras_dictadas(text: str) -> str:
    """Pasa a cifras los importes dichos en letra, y solo esos.

    «Gasté treinta y cinco euros» → «Gasté 35 euros». Se exige que la secuencia
    termine justo antes de «euros» (o «con cincuenta» de céntimos) para no tocar
    nombres propios que suenan a número.

    Al dictar también se dice el importe **sin** la palabra euros: «una factura de
    ciento veinte a Juan». Para esos se pide que la cifra vaya detrás de «de» o
    «por» y delante de un conector, nunca de otra palabra: así «Tres Torres» o
    «Cien Montaditos» siguen siendo nombres y no se convierten en números.
    """
    palabras_sueltas = "|".join(sorted(_PALABRA_NUMERO, key=len, reverse=True))
    text = re.sub(
        rf"(?<=\b)(?P<marca>(?:de|por|importe|precio|son|es)\s+)"
        rf"(?P<cifra>(?:(?:{palabras_sueltas})\s+)*(?:{palabras_sueltas}))"
        rf"(?:\s+(?:con|amb)\s+(?P<centimos>(?:(?:{palabras_sueltas})\s*)+?))?"
        rf"(?=\s+(?:a|para|per|con|y|i)\b|\s*[,.;]|$)",
        _sin_euros, text, flags=re.I)
    if not re.search(r"\b(?:euros?|eur|€)\b", text, re.I):
        return text

    def reemplazo(match: re.Match) -> str:
        palabras = _norm(match.group("cifra")).split()
        valor = _numero_en_letra(palabras)
        if valor is None or valor <= 0:
            return match.group(0)
        centimos = match.group("centimos")
        if centimos:
            sueltos = _numero_en_letra(_norm(centimos).split())
            if sueltos is not None and 0 < sueltos < 100:
                return f"{valor},{sueltos:02d}{match.group('unidad')}"
        return f"{valor}{match.group('unidad')}"

    palabra = "|".join(sorted(_PALABRA_NUMERO, key=len, reverse=True))
    return re.sub(
        rf"\b(?P<cifra>(?:(?:{palabra})\s+)*(?:{palabra}))"
        rf"(?P<unidad>\s*(?:€|euros?|eur\b))"
        rf"(?:\s+(?:con|amb|y|i)\s+(?P<centimos>(?:(?:{palabra})\s*)+?))?"
        r"(?=\s|$|[,.;])",
        reemplazo, text, flags=re.I)


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
    """La hora de una orden, dicha con cifras o en letra.

    Antes solo leía cifras, así que «mañana a las diez» no encontraba hora y caía
    en el respaldo de «por la mañana»: agendaba a las 9:00 **sin avisar**, que es
    peor que no entenderlo. Se acepta además «y media», «y cuarto», «menos
    cuarto» y «de la tarde», que es como se dicta una hora hablando.
    """
    horas = "|".join(sorted((p for p, v in _UNIDADES.items() if 1 <= v <= 23),
                            key=len, reverse=True))
    m = re.search(
        rf"\ba\s+l(?:a|as|es)\s+(?P<h>\d{{1,2}}|{horas})"
        rf"(?:\s*[:h.]\s*(?P<mn>\d{{2}}))?"
        rf"(?P<frac>\s+(?:y\s+(?:media|mitja|cuarto|quart)|menos\s+cuarto|"
        rf"menys\s+quart))?"
        rf"(?P<parte>\s+(?:de\s+la|del|de\s+l|por\s+la|a\s+la)\s*"
        rf"(?:manana|mati|tarde|vespre|noche|nit|mediodia|migdia))?",
        norm)
    if m:
        crudo = m.group("h")
        hora = int(crudo) if crudo.isdigit() else _UNIDADES.get(crudo, -1)
        minuto = int(m.group("mn")) if m.group("mn") else 0
        fraccion = m.group("frac") or ""
        if "media" in fraccion or "mitja" in fraccion:
            minuto = 30
        elif "menos" in fraccion or "menys" in fraccion:
            hora, minuto = hora - 1, 45
        elif "cuarto" in fraccion or "quart" in fraccion:
            minuto = 15
        parte = m.group("parte") or ""
        # «a las cinco de la tarde» son las 17:00, no las 5 de la madrugada.
        if re.search(r"tarde|vespre|noche|nit", parte) and 1 <= hora <= 11:
            hora += 12
        elif re.search(r"mediodia|migdia", parte) and hora == 12:
            hora = 12
        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            return (hora, minuto)
        return None
    # Sin hora explícita, el momento del día da una por defecto. «Por la mañana»
    # es una hora; «mañana» a secas es el día siguiente, y antes valían igual.
    if re.search(r"\b(?:por|de)\s+la\s+manana\b|\bal\s+mati\b", norm):
        return 9, 0
    if re.search(r"mediodia|migdia", norm):
        return 12, 0
    if re.search(r"\btardes?\b|\bvespre\b", norm):
        return 16, 0
    if re.search(r"\bnoche\b|\bnit\b", norm):
        return 19, 0
    if re.search(r"\bmanana\b", norm):
        return 9, 0  # «mañana» sin hora: a primera hora, como hasta ahora
    return None


def parse_date(text: str, base: date | None = None) -> str | None:
    """Convierte fechas en español a ISO. Devuelve None si no encuentra fecha."""
    base = base or date.today()
    norm = _norm(text)
    day: date | None = None
    if "pasado manana" in norm or "despus dema" in norm or "passat dema" in norm:
        day = base + timedelta(days=2)
    elif re.search(r"\b(?:manana|dema)\b", norm.replace("por la manana", "")):
        day = base + timedelta(days=1)
    if re.search(r"\b(?:hoy|avui)\b", norm):
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
# Factura pedida con datos a medias: se crea el borrador con lo dicho y se declara
# lo que falta, en vez de pedirlo todo de golpe y tirar lo que sí se entendió.
PARTIAL_INVOICE = "crear_factura_a_medias"
# «este cliente», «a él»: el cliente del que se está hablando. Lo resuelve el chat
# con la conversación; el analizador solo marca que es una referencia.
CLIENTE_DE_LA_CONVERSACION = "__cliente_de_la_conversacion__"
# Alta de cliente o proveedor sin nombre utilizable: se pregunta el nombre y se
# recuerda qué se estaba dando de alta, en vez de listar fichas o soltar el
# parte del día, que es lo que pasaba antes con «crea el cliente» a secas.
NEED_PARTY_NAME = "__need_party_name__"
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
        # «con» corta además de introducir: sin él, «apúntame mañana a las 10 con
        # Jordi Mas» se lo tragaba entero desde el «a» de «a las» y el nombre
        # quedaba dentro, así que se pedía el cliente teniéndolo delante.
        r"(?=\s+(?:hoy|avui|mañana|demà|dema|pasado|passat|el|la|los|las|"
        r"próximo|proxima|a las|a les|per|por la|en|para|de|con|"
        r"dilluns|dimarts|dimecres|dijous|divendres|dissabte|diumenge)\b"
        r"|[,;]|$)",
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
    # La fecha no describe el trabajo: «para Jordi Mas mañana a las 10» dejaba la
    # cita llamada «Jordi Mas mañana a las 10». Se corta en la marca de tiempo,
    # pero NO en cualquier artículo, o «reparar la caldera» perdería la caldera.
    _HASTA_LA_FECHA = (
        r"(?=\s+para\b|\s+en\s+|[,;]|$"
        r"|\s+(?:hoy|mañana|demà|pasado|a\s+las\b|por\s+la\b"
        r"|el\s+(?:lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo))\b)")
    for match in re.finditer(r"\b(?:para|de)\s+(.+?)" + _HASTA_LA_FECHA, text, re.I):
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


# Siglas mercantiles y esas iniciales que llevan punto DENTRO del nombre: en
# «Reformas Martínez S.L.» o «Talleres J. Pino» ese punto no separa nada.
_SIGLAS_CON_PUNTO = {"S", "SL", "SA", "SLU", "SAU", "SCP", "SC", "CB", "SCCL",
                     "SLL", "SAL", "SRL", "CIF", "NIF"}
# «Concepto: …» dicho a viva voz. Es una marca explícita: lo que va detrás es el
# concepto de la factura, nunca parte del nombre de quien la recibe.
_MARCA_DE_CONCEPTO = re.compile(
    r"\s*[.,;]?\s*\b(?:en\s+concepto\s+de|concepto)\b\s*:?\s+", re.I)


# Confirmar es una puerta de dinero, así que por defecto una frase NO confirma.
# Se acepta un «sí» seguido solo de cortesías o de pedir lo que el producto ya
# hace al confirmar (el PDF). Cualquier otra cosa —un número, un «pero», un
# cambio— deja de ser un sí y la frase se vuelve a interpretar.
_SI_INICIAL = re.compile(
    r"^(?:si|sii|sip|vale|ok|okey|okay|confirmo|confirmar|correcto|exacto|"
    r"perfecto|adelante|dale|claro|de acuerdo|eso es|hazlo|hazla|endavant|"
    r"d'acord|fes-ho)\b")
# Palabras que pueden acompañar a un sí sin cambiar lo que se confirma.
_COLA_SIN_ORDEN = re.compile(
    r"^(?:[\s,.;:!¡]|y|i|tambien|ademes|ademas|por favor|porfa|gracias|"
    r"confirmo|confirmar|correcto|exacto|perfecto|vale|ok|okey|claro|dale|"
    r"adelante|hazlo|hazla|generalo|generala|generame|genera|generar|creame|"
    r"crea|preparame|prepara|mandamelo|mandame|manda|enviamelo|enviame|envia|"
    r"pasamelo|pasame|pasa|adjuntamelo|adjuntame|adjunta|quiero|necesito|"
    r"el|la|los|las|lo|me|un|una|su|de|del|"
    r"pdf|factura|borrador|documento|ahora|ya|porfavor)*$")


def es_confirmacion(text: str) -> bool:
    """¿Esta frase es un «sí» a lo que se acaba de proponer?

    «Sí» a secas lo era; «si, genera el pdf» no, y la orden se perdía: se volvía a
    interpretar como una petición nueva y la factura no llegaba a existir. Lo que
    NO se acepta sigue siendo todo lo que pueda cambiar la operación: cifras,
    «pero», correcciones. Ante la duda, no es un sí.
    """
    norm = _norm(text)
    marca = _SI_INICIAL.match(norm)
    if not marca:
        return False
    cola = norm[marca.end():]
    if re.search(r"\d", cola):
        return False  # un número detrás del sí es una corrección, no un sí
    return bool(_COLA_SIN_ORDEN.fullmatch(cola))


def _limpiar_concepto(texto: str) -> str:
    """Quita los conectores que quedan colgando al final de un concepto.

    «concepto ventana por 750 euros» deja «ventana por»: ese «por» introduce el
    importe, no forma parte de lo que se factura.
    """
    partes = str(texto or "").strip(" ,.;:").split()
    while partes and partes[-1].lower().strip(",.;:") in _CONECTORES_FINALES:
        partes.pop()
    return " ".join(partes).strip(" ,.;:")


def _partir_nombre(nombre: str) -> tuple[str, str]:
    """Separa el nombre de quien factura de la frase que se le pegó detrás.

    Un nombre no lleva dentro una frase entera: «Reformas Martínez. Concepto
    ventanas» son dos cosas, el cliente y el concepto. Al dictar por voz esa
    frase es la natural, y tragársela entera acababa buscando —y creando— una
    ficha llamada «Reformas Martínez. Concepto ventanas», que no existe y que en
    una factura emitida sale como nombre fiscal.

    No corta el punto de las siglas («S.L.») ni el de una inicial («J. Pino»),
    que sí forman parte del nombre. Devuelve `(nombre, lo que venía detrás)`.
    """
    texto = str(nombre or "").strip()
    marca = _MARCA_DE_CONCEPTO.search(texto)
    if marca and marca.start() > 0:
        return (_recortar(texto[:marca.start()]),
                texto[marca.end():].strip(" ,.;:"))
    for corte in re.finditer(r"\.\s+", texto):
        previas = texto[:corte.start()].split()
        anterior = previas[-1] if previas else ""
        clave = anterior.replace(".", "").upper()
        if len(clave) <= 1 or clave in _SIGLAS_CON_PUNTO:
            continue  # el punto va dentro del nombre, no lo parte
        return (_recortar(texto[:corte.start()]),
                texto[corte.end():].strip(" ,.;:"))
    # La coma y los dos puntos cierran el nombre igual que el punto: «para
    # Reformas Martínez, ventana, 750» son tres cosas, no un nombre larguísimo.
    # La coma de la forma societaria («Reformas Martínez, S.L.») no cierra nada.
    for coma in re.finditer(r"[,:]\s*", texto):
        siguiente = texto[coma.end():].split()
        primera = siguiente[0].replace(".", "").rstrip(",").upper() if siguiente else ""
        if primera in _SIGLAS_CON_PUNTO:
            continue  # «Reformas Martínez, S.L.»: esa coma es del nombre
        return (_recortar(texto[:coma.start()]),
                texto[coma.end():].strip(" ,.;:"))
    return (texto, "")


def _recortar(nombre: str) -> str:
    """Quita la puntuación de los bordes sin comerse el punto de «S.L.»."""
    limpio = nombre.strip(" ,;:")
    ultima = limpio.split()[-1] if limpio.split() else ""
    if ultima.replace(".", "").upper() in _SIGLAS_CON_PUNTO:
        return limpio
    return limpio.strip(" ,.;:")


def _limpiar_cliente(nombre: str) -> str:
    """Quita los conectores que se cuelan al final de un nombre dictado."""
    nombre, _ = _partir_nombre(nombre)
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


def _factura_sin_preposicion(text: str, norm: str) -> dict | None:
    """«Factura reformas martinez ventana 750»: sin «a», sin «por», con importe."""
    if re.search(r"\b(?:a|para|per\s+a|por|per)\b", norm):
        return None  # con esas preposiciones lo resuelven los órdenes de siempre
    importe = re.search(rf"({_AMOUNT_RE})\s*(?:€|euros?|eur\b)?", text, re.I)
    if not importe:
        return None
    valor = _amount_value(importe.group(1))
    if valor <= 0:
        return None
    resto = (text[:importe.start()] + " " + text[importe.end():])
    resto = re.sub(r"^\s*(?:hazme|haz|crea\w*|prepara\w*|ponme|pon|quiero|"
                   r"necesito|genera\w*|monta\w*|fes\w*|apunta\w*|anota\w*|"
                   r"mete\w*|anade\w*|añade\w*|una|un|la|el)\b", "",
                   resto.strip(), flags=re.I)
    resto = re.sub(r"^\s*(?:una|un|la|el)?\s*factur\w*\s*", "", resto.strip(),
                   flags=re.I)
    resto = re.sub(r"\s*\b(?:euros?|eur|€|mas iva|más iva|con iva)\b\s*", " ",
                   resto, flags=re.I)
    # Una preposición suelta al principio no forma parte del nombre de nadie.
    resto = re.sub(r"^\s*(?:de|del|a|para|per)\b\s*", "", resto.strip(),
                   flags=re.I).strip(" ,.;:")
    if not resto or not re.search(r"[^\W\d_]", resto, re.UNICODE):
        return None
    if re.search(r"\bfactur\w*\b", _norm(resto)):
        # Si después de quitar verbo e importe todavía se habla de una factura,
        # no se ha separado limpiamente y lo que queda no es el nombre de nadie.
        return None
    cliente, concepto = _cliente_y_concepto(resto, "Servicio")
    if not cliente:
        return None
    return {"cliente": cliente, "concepto": concepto, "base": valor}


def _cliente_y_concepto(crudo: str, concepto: str) -> tuple[str, str]:
    """Nombre del cliente y concepto, con la frase pegada detrás repartida.

    Cuando el dictado pega el concepto al nombre («a Reformas Martínez. Concepto
    ventanas 850»), lo que iba detrás es el concepto de verdad; antes se perdía y
    la factura salía como «Servicio» a nombre de la frase entera.
    """
    nombre, resto = _partir_nombre(crudo)
    limpio = _limpiar_cliente(nombre) or _limpiar_cliente(crudo)
    if resto and concepto in ("", "Servicio"):
        concepto = resto
    return (limpio, concepto)


def _parse_doc_command(text: str, norm: str, verb_re: str) -> dict | None:
    """Parser flexible para facturas y presupuestos. Acepta varios órdenes naturales:
      - "factura a Juan por reparación de grifo 95 euros"  (concepto antes de importe)
      - "factura a Juan 95€ por reparación de grifo"       (importe antes de concepto)
      - "factura a Juan 95 euros"                          (sin concepto explícito)
    """
    # Los impuestos son campos separados, nunca parte del cliente o concepto.
    # Los impuestos son campos aparte, nunca parte del cliente ni del concepto.
    # El sufijo es opcional a propósito: «750 euros más IVA» deja «más IVA» suelto
    # al final, y sin quitarlo acababa siendo el concepto de la factura.
    text = re.sub(
        r"\s+(?:(?:con|más|mas|sin|\+)\s+)?(?:IVA|IRPF)\s*(?:(?:del|al)\s*)?"
        r"(?:incluido|inclos|\d+(?:[.,]\d+)?\s*%?)?",
        " ", text, flags=re.I).strip(" ,.")
    # «…concepto ventana con el 21%» dejaba el porcentaje dentro del concepto.
    text = re.sub(r"\s+(?:con|más|mas|y)\s+(?:el\s+)?\d+(?:[.,]\d+)?\s*%",
                  " ", text, flags=re.I).strip(" ,.")  # un espacio, no vacío: si no, pega
    text = re.sub(r"\s{2,}", " ", text)      # «euros mas iva concepto» → «eurosconcepto»
    # Si se dice «concepto», eso ES el concepto y manda sobre cualquier otra
    # lectura. Sin esto, «factura a reformas martinez concepto ventana por 750»
    # metía «concepto ventana» dentro del nombre del cliente, y cuando no lo
    # metía, partía el concepto por la mitad («cambio de grifo» se quedaba en
    # «grifo», porque el «de» parecía el separador del importe).
    marca = _MARCA_DE_CONCEPTO.search(text)
    if marca:
        cabeza, cola = text[:marca.start()], text[marca.end():]
        patron = rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?"
        en_cola = re.search(patron, cola, re.I)
        en_cabeza = re.search(patron, cabeza, re.I)
        importe = en_cola or en_cabeza
        if importe:
            # El importe puede ir antes o después de «concepto»: «por 750 euros
            # concepto ventana» se dice tanto como «concepto ventana por 750».
            concepto = _limpiar_concepto(cola[:en_cola.start()] if en_cola else cola)
            recorte = cabeza[:en_cabeza.start()] if en_cabeza else cabeza
            quien = re.search(verb_re + r"\s+(?:a|para|per\s+a)\s+(.+)$",
                              recorte, re.I)
            cliente = _limpiar_cliente(quien.group(1)) if quien else ""
            if concepto and cliente:
                return {"cliente": cliente, "concepto": concepto,
                        "base": _amount_value(importe.group(1))}

    # Variante frecuente: "factura a Juan de 100 euros". Debe resolverse antes
    # del patrón con concepto para que el 100 no se parta en "1" + "00".
    m = re.search(
        verb_re + rf"\s+(?:a|para|per\s+a)\s+(.+?)\s+(?:de|por|per)\s+"
        rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?$",
        text, re.I,
    )
    if m:
        cliente, concepto = _cliente_y_concepto(m.group(1), "Servicio")
        return {"cliente": cliente, "concepto": concepto,
                "base": _amount_value(m.group(2))}
    # Orden 1: verbo a CLIENTE por CONCEPTO IMPORTE
    # El `\s+` antes del importe no es cosmético: con `\s*` el grupo perezoso se
    # comía parte de la cifra («40» → concepto «4», importe «0»).
    m = re.search(verb_re + r"\s+(?:a|para|per\s+a)\s+(.+?)\s+(?:por|de|per)\s+(.+?)[,]?\s+"
                  rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?$", text, re.I)
    if m:
        cliente, concepto = _cliente_y_concepto(m.group(1), m.group(2).strip())
        return {"cliente": cliente, "concepto": concepto,
                "base": _amount_value(m.group(3))}
    # Orden 2: verbo a CLIENTE IMPORTE por CONCEPTO
    m = re.search(verb_re + r"\s+(?:a|para|per\s+a)\s+(.+?)\s+"
                  rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?\s+"
                  r"(?:por|de|per)\s+(.+)", text, re.I)
    if m:
        cliente, concepto = _cliente_y_concepto(m.group(1), m.group(3).strip())
        return {"cliente": cliente, "concepto": concepto,
                "base": _amount_value(m.group(2))}
    # Orden 3: verbo a CLIENTE IMPORTE [CONCEPTO]. Lo que quede detrás del
    # importe es el concepto: «a Juan 750 euros ventana» lo dice mucha gente.
    m = re.search(verb_re + r"\s+(?:a|para|per\s+a)\s+(.+?)\s+"
                  rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?(?:\s|$)(.*)$", text, re.I)
    if m:
        cola = _limpiar_concepto(re.sub(r"^\s*(?:de|por|per|en)\s+", "",
                                        m.group(3) or "", flags=re.I))
        cliente, concepto = _cliente_y_concepto(m.group(1), cola or "Servicio")
        return {"cliente": cliente, "concepto": concepto,
                "base": _amount_value(m.group(2))}
    # Orden 4: verbo IMPORTE a CLIENTE por CONCEPTO.
    m = re.search(
        verb_re + rf"\s+(?:de\s+)?({_AMOUNT_RE})\s*(?:€|euros?|eur)?\s+"
        r"(?:a|para|per\s+a)\s+(.+?)(?:\s+(?:por|de|per)\s+(.+))?$",
        text, re.I,
    )
    if m:
        cliente, concepto = _cliente_y_concepto(
            m.group(2), (m.group(3) or "Servicio").strip())
        return {"cliente": cliente, "concepto": concepto,
                "base": _amount_value(m.group(1))}
    return None


# Lo que dice alguien que deja la factura para luego. Nada de esto es un cliente ni
# un concepto: «factura para Jordi, los datos te los paso luego» no tiene concepto
# «los datos».
_RELLENO_NO_DATO = re.compile(
    r"\b(?:datos?|luego|despues|mas tarde|ahora|invent\w*|pasare|paso|pondre|"
    r"pongo|medias|rellen\w*|complet\w*|ya te|te lo|te los|nadie|alguien)\b"
)
_REFERENCIA_CLIENTE = re.compile(
    r"\b(?:este|ese|esta|esa|dicho|dicha|mismo|misma|aquel|aquella|aquest|aqueix)"
    r"\s+client[ea]s?\b"
    r"|\b(?:para|a|per\s+a)\s+(?:el|ella|ell)\s*(?:[,.;]|$|\s+(?:por|de|y|que)\b)"
)
# Verbos que piden crear. Sin uno de estos, «factura» es una consulta y no se crea
# nada: pedir datos por error era inofensivo, crear un borrador por error no.
_VERBO_CREAR_FACTURA = re.compile(
    r"\b(?:hazme|haz|hacer|crea|crear|creame|genera|generar|prepara|preparame|"
    r"preparar|pon|ponme|anade|añade|añademe|apunta|apuntame|nueva|nuevo|quiero|"
    r"necesito|monta|montame|fes|fes-me|crea'm)\b"
)
_CONSULTA_FACTURA = re.compile(
    r"\b(?:que|cual|cuales|cuanto|cuanta|cuantas|esta|estan|pagad\w*|cobrad\w*|"
    r"ver|veo|ensena\w*|muestra\w*|envia\w*|manda\w*|borra\w*|elimina\w*|anula\w*|"
    r"rectifica\w*|emite|emitir|pendiente)\b"
)
# «la factura de Juan», «la factura del mes pasado», «la factura nº 12»: se habla de
# una que YA existe. Ahí «necesito» o «quiero» no piden crear nada, y crear un
# borrador vacío sería inventarse una factura: peor que el fallo que se corrige. El
# determinante indefinido («una factura», «factura a Juan») sí es una orden de crear.
_FACTURA_EXISTENTE = re.compile(
    r"\b(?:la|las|esa|esas|esta|estas|mi|mis|su|sus)\s+factur\w*\s+(?:de|del)\b"
    r"|\bfactur\w*\s*(?:n[ºo°]|num\w*|#)\s*\d+"
)
# Un importe lo cambia todo: «la factura de Juan» pregunta por una que existe,
# pero «hazme la factura de Juan: ventana, 750 euros» la está pidiendo. Nadie
# dice un precio para preguntar por una factura que ya tiene.
_LLEVA_IMPORTE = re.compile(
    rf"({_AMOUNT_RE})\s*(?:€|euros?|eur\b)|\b(?:importe|precio|base)\b")
# Una factura recurrente se configura en Facturas, no es un borrador suelto: crear
# uno aquí dejaría al autónomo creyendo que ya se repite sola.
_FACTURA_RECURRENTE = re.compile(r"\b(?:recurrent\w*|periodic\w*|cada\s+mes)\b")


def _limpio_o_nada(valor: str | None) -> str | None:
    """Descarta lo que no es un dato: relleno, números sueltos, trozos vacíos."""
    valor = (valor or "").strip(" ,.;:")
    if not valor or len(valor) > 160:
        return None
    if _RELLENO_NO_DATO.search(_norm(valor)) or re.fullmatch(r"[\d\s.,€]+", valor):
        return None
    return valor


def parse_partial_invoice(text: str) -> dict:
    """Extrae de una petición de factura lo que haya, aunque falten datos.

    Devuelve solo las claves que ha entendido de verdad: `cliente`, `concepto` y
    `base`. Una clave ausente es un dato pendiente, no un error.
    """
    norm = _norm(text)
    limpio = re.sub(r"\s+(?:(?:con|más|mas)\s+)?(?:IVA|IRPF)\s*(?:(?:del|al)\s*)?"
                    r"(?:incluido|inclos|\d+(?:[.,]\d+)?\s*%?)", "", text,
                    flags=re.I)
    args: dict = {}
    if _REFERENCIA_CLIENTE.search(norm):
        args["cliente"] = CLIENTE_DE_LA_CONVERSACION
    else:
        m = re.search(
            r"fact[uú]ra\w*\s+(?:\w+\s+){0,2}?(?:a|para|per\s+a)\s+"
            rf"(.+?)(?=\s*,|\s+(?:por|per|y|que|con)\s|\s+(?:de\s+)?{_AMOUNT_RE}|$)",
            limpio, re.I)
        if m:
            cliente = _limpio_o_nada(_limpiar_cliente(m.group(1)))
            if cliente:
                args["cliente"] = cliente
    m = re.search(rf"\s(?:por|per)\s+(.+?)(?=\s*,|\s+(?:de\s+)?{_AMOUNT_RE}|\s+y\s|$)",
                  limpio, re.I)
    if m:
        concepto = _limpio_o_nada(m.group(1))
        if concepto:
            args["concepto"] = concepto
    importe = re.search(rf"({_AMOUNT_RE})\s*(?:€|euros?|eur\b)", limpio, re.I) or \
        re.search(rf"(?:de|por|son)\s+({_AMOUNT_RE})\b", limpio, re.I)
    if importe:
        valor = _amount_value(importe.group(1))
        if valor > 0:
            args["base"] = valor
    return args


_TELEFONO_RE = re.compile(r"(\+?\d[\d\s.\-]{7,}\d)")
# Lo que viene detrás del nombre cuando alguien dicta la ficha entera de un tirón.
_DATO_DE_CONTACTO = re.compile(
    r"\b(?:tel[eé]fono|telf?|m[oó]vil|whatsapp|correo|email|e-mail|nif|cif|dni|"
    r"direcci[oó]n|domicilio|calle|avenida|zona)\b", re.I)


def parse_party_name(raw: str) -> tuple[str | None, str | None]:
    """Separa el nombre de la ficha de los datos de contacto que lo acompañan.

    «Jordi Mas, teléfono 600 12 34 56» es un cliente llamado Jordi Mas con un
    teléfono, no un cliente llamado «Jordi Mas, teléfono 600 12 34 56». Devuelve
    `(None, None)` cuando lo que queda no puede ser el nombre de nadie —solo
    cifras o signos—, para preguntar en vez de crear una ficha basura.
    """
    # `_recortar` quita la puntuación de los bordes sin comerse el punto final de
    # «S.L.», que es parte del nombre y sale así en la factura.
    texto = _recortar((raw or "").strip())
    if not texto:
        return (None, None)
    # Lo dictado detrás de un punto o de una coma no es parte del nombre: «crear
    # cliente Reformas Martínez. Concierto Ventanas» da de alta a Reformas
    # Martínez. Lo que se corta NO se tira: ahí es donde viene el teléfono en
    # «Jordi Mas, teléfono 600 12 34 56», y perderlo sería cambiar un fallo por
    # otro.
    texto, cortado = _partir_nombre(texto)
    telefono = None
    if cortado and _DATO_DE_CONTACTO.search(cortado):
        encontrado = _TELEFONO_RE.search(cortado)
        if encontrado:
            telefono = re.sub(r"[\s.\-]", "", encontrado.group(1))
    # La coma ya la ha resuelto `_partir_nombre`, que sabe distinguir la de
    # «Reformas Martínez, S.L.» —parte del nombre fiscal, y va en la factura— de
    # la que introduce los datos. Aquí solo queda la palabra que los anuncia
    # («con teléfono …»).
    corte = re.search(r";|\s+(?:con|y)\s+(?=" + _DATO_DE_CONTACTO.pattern + ")",
                      texto, re.I)
    if corte and _DATO_DE_CONTACTO.search(texto[corte.start():]):
        cola = texto[corte.start():]
        texto = texto[:corte.start()].strip(" ,.;:")
        encontrado = _TELEFONO_RE.search(cola)
        if encontrado:
            telefono = re.sub(r"[\s.\-]", "", encontrado.group(1))
    elif corte:
        texto = texto[:corte.start()].strip(" ,.;:")
    if len(texto) > 200:
        # Se devuelve tal cual: la base explica que es demasiado largo, y
        # recortarlo a escondidas daría de alta a alguien que no existe.
        return (texto, telefono)
    if not re.search(r"[^\W\d_]", texto, re.UNICODE):
        return (None, telefono)
    return (texto, telefono)


def _add_tax_rates(norm: str, args: dict) -> None:
    # «Con el 21 por ciento» es como se dice el IVA hablando, sin nombrarlo. Solo
    # se toma como IVA si no hay un descuento por medio, que también va en %.
    if not re.search(r"\biva\b|\bdescuento\b|\bdto\b|\birpf\b", norm):
        suelto = re.search(r"\b(?:con|mas|más|y)\s+(?:el\s+)?(0|4|10|21)\s*%", norm)
        if suelto:
            args["iva"] = float(suelto.group(1))
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
            verb + r"\s+(?:por|de|per)\s+(.+?)[,]?\s+"
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


def _party_intent(papel: str, nombre: str) -> tuple[str, dict]:
    """Alta de cliente o proveedor con el nombre ya separado de sus datos."""
    tipo = "cliente" if _norm(papel).startswith("client") else "proveedor"
    limpio, telefono = parse_party_name(nombre)
    if not limpio:
        # Un «cliente» que es solo un número de teléfono no es el nombre de
        # nadie: se pregunta en vez de dejar una ficha llamada «600123456».
        return (NEED_PARTY_NAME, {"tipo": tipo, "motivo": "sin_nombre"})
    args: dict = {"nombre": limpio}
    if telefono and tipo == "cliente":
        args["telefono"] = telefono
    return (f"crear_{tipo}", args)


def parse(text: str) -> tuple[str, dict] | None:
    # Lo primero: pasar a cifras los importes dictados en letra. Todo lo que
    # viene detrás busca números, y una nota de voz los trae escritos.
    # «El 21 por ciento» es como se dice un porcentaje hablando. Sin traducirlo,
    # «ciento» acababa siendo el concepto de la factura.
    text = re.sub(r"(\d+(?:[.,]\d+)?)\s*por\s*ciento\b", r"\1%", text, flags=re.I)
    text = _cifras_dictadas(text)
    norm = _norm(text)

    refusal = safety_refusal(text)
    if refusal:
        return (NEED_REVIEW, {"reply": refusal})
    for field, allowed in (("iva", {0, 4, 10, 21}), ("irpf", {0, 7, 15})):
        rate = re.search(rf"\b{field}\s*(?:(?:del|al)\s*)?(\d+(?:[.,]\d+)?)(?![\w.,])", norm)
        if rate and float(rate.group(1).replace(",", ".")) not in allowed:
            return (NEED_REVIEW, {"reply": "El tipo fiscal indicado no está admitido. Revisa IVA e IRPF en Facturas; no he sustituido el porcentaje por otro."})
    # Se compara contra `norm`, sin acentos: contra el texto crudo, «qué trabajos
    # tengo mañana» no encajaba con «que.*trabajos» por la tilde y la orden se
    # perdía entera.
    if re.search(r"(?:(?:que|quins|quines|quin)\b.*"
                 r"\b(?:trabajos|citas|tengo|treballs|feines|tinc)\b.*"
                 r"|agenda (?:de|para|per) )(?:hoy|avui|manana|dema)", norm):
        when = parse_date(text)
        if when:
            return ("ver_agenda", {"fecha": when[:10]})
    # Un cobro no crea una factura. Los pagos parciales necesitan importe explícito
    # y se revisan en Facturas mientras el contrato de esta orden sea saldo total.
    # Una factura es femenina: «la factura 1 está cobrada» y «marca la factura 1
    # como pagada» son la forma natural de decirlo, y el patrón solo aceptaba el
    # masculino. Quedaban sin entender y, peor, se ofrecía crear una factura
    # nueva a quien acababa de decir que ya le habían pagado una.
    _COBRADA = r"\b(?:pagad[oa]s?|cobrad[oa]s?|liquidad[oa]s?|saldad[oa]s?|pago|cobro)\b"
    _PREGUNTA_DE_COBROS = (r"\b(?:que|cuales|cuantas|cuanto|quien|ver|veo|"
                           r"ensename|muestrame|dime|listar?|pendientes?)\b")
    if (re.search(_COBRADA, norm) and "factura" in norm
            # «Qué facturas tengo pendientes de cobro» es una pregunta, no un
            # cobro: antes contestaba con la explicación del cobro parcial.
            and not re.search(_PREGUNTA_DE_COBROS, norm)):
        paid = re.search(r"\bfactura\s*#?\s*(\d+)\b", norm)
        hecho = re.search(r"\b(?:pagad[oa]s?|cobrad[oa]s?|liquidad[oa]s?|saldad[oa]s?)\b", norm)
        if paid and hecho and not re.search(r"\b(parcial|parte|euros|eur)\b|€", norm):
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
        # «client» y «proveïdor» en catalán se dicen tanto como en castellano.
        r"(client\w*|proveedor\w*|prove[ïi]dor\w*)\s*:?\s+(.+?)\s*$",
        text, re.I,
    )
    if not party:
        # Orden inverso: primero el nombre y después el papel.
        inversa = re.search(
            r"\b(?:da|dar)\s+de\s+alta\s+(?:a\s+)?(.+?)\s+como\s+"
            r"(client\w*|proveedor\w*|prove[ïi]dor\w*)\b",
            text, re.I,
        )
        if inversa:
            return _party_intent(inversa.group(2), inversa.group(1))
    if party:
        name = re.sub(r"^(?:llamad[oa]|que se llama)\s+", "", party.group(2), flags=re.I)
        return _party_intent(party.group(1), name)
    # «Crea el cliente» o «nuevo proveedor» a secas. Antes no casaba con nada de
    # aquí y acababa listando clientes o dando el parte del día: la orden se
    # perdía entera por faltar una palabra.
    sin_nombre = re.match(
        r"(?:crea|crear|creame|anade|anademe|nuevo|nueva|alta)\s+(?:de\s+)?"
        r"(?:un|una|el|la)?\s*(cliente|proveedor)\s*$", norm)
    if sin_nombre:
        return (NEED_PARTY_NAME, {"tipo": sin_nombre.group(1)})
    if re.search(
        r"\b(?:crea|crear|anade|añade|nuevo|nueva|alta)\s+(?:un|una)?\s*usuario\b",
        norm,
    ):
        return (NEED_USER_INVITE, {})

    # --- Crear proyecto sencillo, local y sin IA
    if re.search(r"proyect|project", norm) and re.search(
            r"\b(crea|crear|creame|nuevo|nueva|abre|abrir|monta|obre)\b", norm):
        # El conector antes del importe es opcional: «el proyecto Casa Roca 12000
        # euros» no encajaba y acababa listando proyectos en vez de crear uno.
        m = re.search(
            rf"(?:proyecto|projecte|obra)\s+(.+?)\s+(?:(?:de|por|per|presupuesto|"
            rf"pressupost)\s+)?({_AMOUNT_RE})\s*(?:€|euros?|eur)?(?:\s|$)",
            text, re.I,
        )
        if m:
            # «Abre un proyecto de reforma» no se llama «de reforma»: la
            # preposición introduce el nombre, no forma parte de él.
            nombre = re.sub(r"^\s*(?:de|del|para|per\s+a|per|a|el|la|un|una|"
                            r"els|les)\b\s*", "", m.group(1).strip(), flags=re.I)
            nombre = _limpiar_concepto(nombre)
            if nombre:
                return ("crear_proyecto", {
                    "nombre": nombre,
                    "presupuesto": _amount_value(m.group(2)),
                })
        # Se pide crear un proyecto pero no se dice cuál: se pregunta, en vez de
        # listar los que ya hay, que es lo que pasaba antes.
        return (NEED_REVIEW, {"reply": (
            "Para abrir un proyecto necesito **cómo se llama** y **el "
            "presupuesto**. Por ejemplo: «crea el proyecto Casa Roca 12.000 "
            "euros». No he creado nada.")})

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
        r"\b(?:factura|facturar)\s+(?:(?:el|del)\s+)?(?:trabajo|treball)\s*#?\s*(\d+)\b",
        norm
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

    # «Envía la factura 3» no es lo mismo que «emitir la factura 3»: emitir le
    # pone número definitivo y la cuenta para Hacienda, y eso no se adivina.
    # Antes esta frase caía en «dime cliente, concepto e importe», o sea que se
    # ofrecía CREAR otra factura a quien pedía mandar una que ya existe.
    entrega = re.search(
        # «Pásame la factura 3» queda fuera a propósito: eso es pedir el PDF
        # para uno mismo, y tiene su propio camino en WhatsApp.
        r"\b(?:envia\w*|enviale|manda\w*|mandale|remite|entrega\w*)\s+"
        r"(?:le\s+)?(?:la\s+|el\s+)?(?:factura|tiquet|ticket)\s*#?\s*(\d{1,9})\b",
        norm)
    if entrega:
        numero = int(entrega.group(1))
        # Si se dice el canal, no hay nada que preguntar: se quiere entregar.
        canal = ("email" if re.search(r"\b(?:correo|email|e-?mail|mail)\b", norm)
                 else "whatsapp" if "whatsapp" in norm else None)
        if canal:
            return ("entregar_factura", {"factura_id": numero, "canal": canal})
        return (NEED_REVIEW, {"reply": (
            f"¿Quieres **emitir** la factura {numero} o **entregársela al "
            f"cliente**? No es lo mismo: emitir le pone número definitivo y la "
            f"cuenta para Hacienda.\n\n"
            f"• Para emitirla: «emitir factura {numero}».\n"
            f"• Para emitirla y que le llegue al cliente: «emitir y enviar "
            f"factura {numero}».\n"
            f"• Si ya está emitida y solo quieres reenviarla, hazlo desde "
            f"Facturas.\n\nNo he cambiado nada.")})

    # --- Crear factura: acepta varios órdenes naturales ---
    if "factura" in norm:
        args = _parse_doc_command(text, norm, r"fact[uú]ra(?:r|me)?")
        if args:
            args["tipo_factura"] = "F1"
            _add_tax_rates(norm, args)
            if "iva incluido" in norm or "iva inclos" in norm:
                args["importe_incluye_iva"] = True
            return ("crear_factura", args)
        # «factura a Jordi…» / «factura para Jordi…» al principio: ahí «factura»
        # es el verbo facturar en imperativo, que es tan orden como «hazme».
        # «Factura a Jordi…» y también «factura reformas martinez ventana 750»:
        # ahí «factura» es el verbo facturar en imperativo. Sin preposición solo
        # se acepta si lleva importe, que es lo que distingue una orden de una
        # pregunta suelta.
        imperativo = (re.match(r"(?:factura|facturar|facturame|factura'm)\s+"
                               r"(?:a|para|per\s+a)\b", norm)
                      or (re.match(r"(?:factura|facturar|facturame)\s+\S", norm)
                          and _LLEVA_IMPORTE.search(norm)))
        pide_crear = ((_VERBO_CREAR_FACTURA.search(norm) or imperativo)
                      and not _CONSULTA_FACTURA.search(norm)
                      and not _FACTURA_RECURRENTE.search(norm)
                      and (not _FACTURA_EXISTENTE.search(norm)
                           or _LLEVA_IMPORTE.search(norm)))
        # Se pide una factura, hay importe, pero no se ha dicho «a» ni «por»:
        # «factura reformas martinez ventana 750». Lo que queda tras quitar el
        # verbo y el importe es el cliente y el concepto pegados; los separa la
        # cartera en `chat._split_client_with_the_ledger`. Intentarlo y dejar que
        # el libro de clientes decida vale más que contestar «no te entiendo».
        # «Factura reformas martinez ventana 750», sin unidad detrás del número.
        # Aquí el filtro lo pone la propia frase: si al quitar el verbo y la cifra
        # no queda ninguna palabra, no era una orden («factura 12» no lo es).
        suelta = bool(re.match(r"(?:factura|facturar|facturame)\s+\S", norm)
                      and not _CONSULTA_FACTURA.search(norm)
                      and not _FACTURA_EXISTENTE.search(norm)
                      and not _FACTURA_RECURRENTE.search(norm))
        if pide_crear or suelta:
            suelto = _factura_sin_preposicion(text, norm)
            if suelto:
                _add_tax_rates(norm, suelto)
                return ("crear_factura", {**suelto, "tipo_factura": "F1"})
        if pide_crear:
            args = parse_partial_invoice(text)
            _add_tax_rates(norm, args)
            return (PARTIAL_INVOICE, args)
        if re.search(r"\b(?:hazme|crea|crear|nueva|quiero|necesito|prepara|factura)\b", norm):
            return (NEED_INVOICE, {})

    # --- Registrar gasto: "gasto 45 en gasolina", "gasté 45 de material",
    #     "me he gastado 45", "compré 30 de tornillos", "ticket de 12"
    # La lista de verbos era corta («pon un gasto…», «anota…» y «mete…» no
    # entraban) y sin ellos la frase acababa en la agenda o en el parte del día.
    _VERBO_GASTO = (r"(?:registra|registrar|registrame|apunta|apuntame|anota|"
                    r"anotame|anade|anademe|añade|pon|ponme|mete|meteme)")
    _NOMBRE_GASTO = (r"(?:gastos?\b|gaste\b|he gastado\b|me he gastado\b|"
                     r"compre\b|he comprado\b|ticket\b|tiquet\b|recibo\b|"
                     # Catalán: «he gastat 35 euros» no registraba nada.
                     r"despesa\b|he gastat\b|m'he gastat\b|he comprat\b|rebut\b)")
    es_gasto = bool(
        re.match(rf"(?:{_VERBO_GASTO}\s+(?:un[oa]?\s+)?)?{_NOMBRE_GASTO}", norm)
        # «apunta 20 euros de material»: con el verbo y el importe basta, no hace
        # falta decir «gasto». No se toma por gasto si la frase habla de facturar
        # o de citas, que son otras cosas con importe.
        or (re.match(rf"{_VERBO_GASTO}\s+(?:un[oa]?\s+)?{_AMOUNT_RE}", norm)
            and not re.search(r"\b(?:factura\w*|presupuesto\w*|cliente\w*|"
                              r"cobr\w+|trabajo\w*|cita\w*|agenda\w*)\b", norm))
    )
    if es_gasto:
        amount = _parse_amount(text)
        if amount is not None:
            cm = re.search(r"(?:en|de|por)\s+([a-záéíóúñ ]+)", text, re.I)
            # «pon un gasto de gasolina de 35 euros» dejaba el concepto en
            # «gasolina de»: el conector que introduce el importe no es concepto.
            concepto = _limpiar_concepto(cm.group(1)) if cm else ""
            if not concepto:
                # «compré material por 120 euros»: el concepto va delante del
                # importe y sin preposición. Es lo que queda entre el verbo y la
                # cifra, que antes se perdía y el gasto se llamaba «Gasto».
                medio = re.match(rf"\s*\w+\s+(.+?)\s+(?:por|de|en)?\s*{_AMOUNT_RE}",
                                 text, re.I)
                concepto = _limpiar_concepto(medio.group(1)) if medio else ""
            concepto = concepto or "Gasto"
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
                 r"deudas?|sin cobrar|impagad|moroso|facturas? pendientes?|"
                 # Catalán: «quant em deuen», «qui em deu diners», «deutes».
                 r"em deuen|em deu\b|qui em deu|deutes?|per cobrar|sense cobrar)", norm):
        return ("ver_cobros_pendientes", {})

    # --- Operativa conectada
    if re.search(r"\b(proyectos?|obras?)\b", norm):
        return ("ver_proyectos", {})
    if re.search(r"(equipo|trabajadores?|quien ha fichado|fichajes? de hoy)", norm):
        return ("ver_equipo", {})
    # «Qué documentos tengo» o «pásame los papeles» preguntan por lo mismo que
    # «documentos pendientes», y antes solo se entendía la segunda forma: el
    # resto no hacía nada. En catalán, «documents» y «papers».
    if (re.search(r"(documentos?|documents?|papeles?|papers?|tickets?|tiquets?)"
                  r".*(pendient|revis)", norm)
            or re.search(r"\b(?:que|quins|quines|cuantos|quants)\b.*"
                         r"\b(documentos?|documents?|papeles?|papers?)\b", norm)
            or re.search(r"\b(?:pasame|passa\w*|ensename|ensenya\w*|muestra\w*|"
                         r"mostra\w*|dame|veure|ver)\b.*"
                         r"\b(documentos?|documents?|papeles?|papers?)\b", norm)):
        return ("ver_documentos_pendientes", {})
    if re.search(r"(gestoria|gestor).*(pide|solicitud|pendient)", norm):
        return ("ver_solicitudes_gestoria", {})

    # --- Impuestos: va antes del resumen porque "como va mi iva" casa con ambos y
    # la pregunta fiscal es la concreta. El resumen del mes no responde al 303.
    if re.search(r"(\biva\b|\birpf\b|impuesto|hacienda|modelo\s*(303|130)|"
                 r"trimestral|declaracion|impost|isenda|declaracio)", norm):
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
                 r"balance|beneficio|facturacion|este mes|mis numeros|cuanto llevo|"
                 # Catalán: «quant he facturat», «com va», «aquest mes».
                 r"quant.*facturat|ingressos|com va|com vaig|com anem|benefici|"
                 r"facturacio|aquest mes|els meus numeros|quant porto)", norm):
        return ("resumen_negocio", {})

    # --- Clientes
    if re.search(r"\bclients?\b|\bclientes\b", norm):
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
    if tool == "entregar_factura":
        entrega = result.get("entrega") or {}
        f = result.get("factura") or {}
        if not entrega.get("queued"):
            return (f"No he entregado la factura {f.get('number') or ''}: ese "
                    "cliente no tiene un canal de contacto en su ficha. "
                    "Añádele el correo o el teléfono en Clientes.")
        return (f"📨 Factura {f.get('number')} en camino a "
                f"{entrega.get('target')} por {entrega.get('channel')}. "
                "Queda anotado en su historial.")
    if tool == "registrar_pago":
        return f"Cobro registrado en la factura #{result['factura']['id']}."
    if tool == "crear_cliente":
        client = result["cliente"]
        suffix = " Ya existía; he reutilizado su ficha." if result.get("existing") else ""
        enlazadas = result.get("facturas_enlazadas") or []
        if enlazadas:
            suffix += (" Lo he enlazado al borrador "
                       + ", ".join(f"#{n}" for n in enlazadas)
                       + " que lo esperaba.")
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
