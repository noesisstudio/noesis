"""Cerebro local de Bynoesis (NLU por reglas) — sin coste, sin APIs externas.

Resuelve los comandos más frecuentes (facturar, agendar, gastos, cobros, resumen)
con expresiones regulares y un pequeño parser de fechas en español. Así el chatbot
de la web funciona GRATIS y los datos no salen del servidor. Solo lo que no entiende
se delega (opcionalmente) a la IA en la nube. Es la arquitectura híbrida recomendada:
local para lo rutinario, IA solo para lo complejo.
"""

from __future__ import annotations

import json
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
    # Whisper escribe «veintitrés» y «dieciséis» con tilde; la tabla va sin ella.
    text = re.sub(r"\b(?:dieciséis|veintidós|veintitrés|veintiséis|veintiún)\b",
                  lambda m: _strip_accents(m.group(0)), text, flags=re.I)
    palabra = "|".join(sorted(_PALABRA_NUMERO, key=len, reverse=True))

    def con_centimos(match: re.Match) -> str:
        valor = _numero_en_letra(_norm(match.group("cifra")).split())
        sueltos = _numero_en_letra(_norm(match.group("centimos")).split())
        if not valor or sueltos is None or not 0 < sueltos < 100:
            return match.group(0)
        return f"{valor},{sueltos:02d}{match.group('unidad')}"

    # «veintitrés con cincuenta euros»: los céntimos van antes de la unidad.
    text = re.sub(
        rf"\b(?P<cifra>(?:(?:{palabra})\s+)*(?:{palabra}))\s+(?:con|amb)\s+"
        rf"(?P<centimos>(?:(?:{palabra})\s+)*(?:{palabra}))"
        rf"(?P<unidad>\s*(?:€|euros?|eur\b))",
        con_centimos, text, flags=re.I)
    palabras_sueltas = "|".join(sorted(_PALABRA_NUMERO, key=len, reverse=True))
    text = re.sub(
        # «He gastado veintitrés con cincuenta en el parking»: tras el verbo del
        # gasto la cifra es el importe aunque no se diga «euros».
        rf"(?<=\b)(?P<marca>(?:de|por|importe|precio|son|es|gastado|gaste|gasté|"
        rf"pagado|pague|pagué|gastat)\s+)"
        rf"(?P<cifra>(?:(?:{palabras_sueltas})\s+)*(?:{palabras_sueltas}))"
        rf"(?:\s+(?:con|amb)\s+(?P<centimos>(?:(?:{palabras_sueltas})\s*)+?))?"
        # «y» cierra la cifra solo si no sigue otra cifra: «treinta y cinco» es una.
        rf"(?=\s+(?:a|para|per|con|en)\b|\s+(?:y|i)\s+(?!(?:{palabras_sueltas})\b)"
        rf"|\s*[,.;]|$)",
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
    # «mañana 10h», «el lunes 16:30h»: la hora escrita como en un mensaje.
    suelta = re.search(r"(?<![\d.,])(\d{1,2})(?:[:.](\d{2}))?\s*h(?:oras?)?\b", norm)
    if suelta:
        hora, minuto = int(suelta.group(1)), int(suelta.group(2) or 0)
        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            return (hora, minuto)
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


_DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")


def fecha_larga(dia: date) -> str:
    """«miércoles 30 de septiembre»."""
    return f"{_DIAS_SEMANA[dia.weekday()]} {dia.day} de {_MESES[dia.month - 1]}"


def dia_humano(valor: str, hoy: date | None = None) -> str:
    """«2026-10-01T10:00» → «mañana a las 10:00»: al usuario no se le enseña ISO."""
    try:
        momento = datetime.fromisoformat(valor)
    except (TypeError, ValueError):
        return str(valor or "")
    hoy = hoy or date.today()
    dia = momento.date()
    diferencia = (dia - hoy).days
    if diferencia == 0:
        texto = "hoy"
    elif diferencia == 1:
        texto = "mañana"
    elif diferencia == -1:
        texto = "ayer"
    else:
        texto = f"el {fecha_larga(dia)}"
        if dia.year != hoy.year:
            texto += f" de {dia.year}"
    if "T" in str(valor):
        texto += f" a las {momento.hour}:{momento.minute:02d}"
    return texto


def _cuenta(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


_MES_DICHO = {"enero": 1, "gener": 1, "febrero": 2, "febrer": 2, "marzo": 3, "marc": 3,
          "abril": 4, "mayo": 5, "maig": 5, "junio": 6, "juny": 6, "julio": 7,
          "juliol": 7, "agosto": 8, "agost": 8, "septiembre": 9, "setiembre": 9,
          "setembre": 9, "octubre": 10, "noviembre": 11, "novembre": 11,
          "diciembre": 12, "desembre": 12}


def _fecha_concreta(norm: str, base: date) -> date | None:
    """Día y mes dichos: si ya ha pasado este año, es el del año que viene."""
    meses = "|".join(sorted(_MES_DICHO, key=len, reverse=True))
    anio = None
    m = re.search(rf"\b(\d{{1,2}})\s+(?:de\s+|d')?({meses})\b(?:\s+(?:de\s+|del\s+)?(\d{{4}}))?",
                  norm)
    if m:
        dia, mes = int(m.group(1)), _MES_DICHO[m.group(2)]
        anio = int(m.group(3)) if m.group(3) else None
    else:
        m = re.search(r"(?<![\d.,])(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?(?![\d/])", norm)
        if m:
            dia, mes = int(m.group(1)), int(m.group(2))
            if m.group(3):
                anio = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
        else:
            m = re.search(r"\b(?:el\s+)?dia\s+(\d{1,2})\b", norm)
            if not m:
                return None
            dia, mes = int(m.group(1)), base.month
            try:
                candidata = date(base.year, mes, dia)
            except ValueError:
                return None
            if candidata < base:
                mes = mes % 12 + 1
                anio = base.year + (1 if mes == 1 else 0)
    try:
        fecha = date(anio or base.year, mes, dia)
    except ValueError:
        return None
    if anio is None and fecha < base:
        try:
            fecha = date(base.year + 1, mes, dia)
        except ValueError:
            return None
    return fecha


def _quitar_fecha_concreta(text: str) -> str:
    """Borra «el 15 de octubre», «el día 15» o «15/10» de una orden."""
    meses = "|".join(sorted(_MES_DICHO, key=len, reverse=True)).replace("marc", "mar[cç]")
    meses = meses.replace("septiembre", "sept?iembre")
    patron = (rf"\s*\b(?:el\s+)?(?:d[ií]a\s+)?\d{{1,2}}\s+(?:de\s+|d')?(?:{meses})\b"
              r"(?:\s+(?:de\s+|del\s+)?\d{4})?"
              r"|\s*\b(?:el\s+)?\d{1,2}/\d{1,2}(?:/\d{2,4})?(?![\d/])"
              r"|\s*\b(?:el\s+)?d[ií]a\s+\d{1,2}\b")
    return re.sub(patron, "", text, flags=re.I)


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
    # «El 15 de octubre», «el día 15», «15/10»: antes no se entendían y agendar
    # para una fecha concreta solo funcionaba con días de la semana.
    concreta = _fecha_concreta(norm, base)
    if concreta:
        day = concreta
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
_SALUDO = re.compile(
    # Las fórmulas largas primero: si no, «buenas» deja suelto «tardes».
    r"^(?:(?:buenos dias|buenas tardes|buenas noches|hola|hey|buenas|que tal|"
    r"como estas|como va)\s+)+")
_PREGUNTAS_DE_AYUDA = {
    "que puedes hacer", "que sabes hacer", "que haces", "ayuda", "help",
    "en que me puedes ayudar", "en que me ayudas", "como funciona",
    "como funcionas", "que puedes hacer por mi",
}


def pide_capacidades(text: str) -> bool:
    """«Hola, ¿qué puedes hacer?» pide la lista de lo que hace Bynoesis.

    Un saludo suelto no: ese se contesta con la lectura del negocio. Solo cuenta
    si tras el saludo no queda nada más, así «hola, factura a Juan…» sigue siendo
    una factura.
    """
    return _sin_saludo(text) in _PREGUNTAS_DE_AYUDA


def _sin_saludo(text: str) -> str:
    pregunta = re.sub(r"[¿?¡!.,;:]", " ", _norm(_erratas(text)))
    return _SALUDO.sub("", " ".join(pregunta.split()) + " ").strip()


def solo_saludo(text: str) -> bool:
    """«Hola, ¿qué tal?» o «buenas tardes» sin nada más."""
    return bool(_norm(text)) and _sin_saludo(text) == ""
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


# Lo que no describe un trabajo: una fecha. «la caldera» o «el termo» sí lo
# describen, aunque empiecen por artículo (eso solo descarta nombres).
_AGENDA_NOT_A_TASK = (
    r"^(?:hoy|manana|dema|pasado|proxim\w*|este|esta|lunes|martes|miercoles|jueves|"
    r"viernes|sabado|domingo|a\s+las|por\s+la|de\s+la\s+(?:manana|tarde|noche)|dia\b|"
    r"semana|mes\b|\d|(?:el|la|los|las)\s+(?:lunes|martes|miercoles|jueves|viernes|"
    r"sabado|domingo|semana|mes|dia|proxim\w*|tarde|manana|noche)\b)"
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
    # Dentro de un lookahead para ver también las coincidencias solapadas: en
    # «a las 12 a Jordi» el primer «a» se tragaba el nombre del final.
    for match in re.finditer(
        r"(?=\b(?:a|con|para|per\s+a)\s+(.+?)"
        # «con» corta además de introducir: sin él, «apúntame mañana a las 10 con
        # Jordi Mas» se lo tragaba entero desde el «a» de «a las» y el nombre
        # quedaba dentro, así que se pedía el cliente teniéndolo delante.
        r"(?=\s+(?:hoy|avui|mañana|demà|dema|pasado|passat|el|la|los|las|"
        r"próximo|proxima|a las|a les|per|por la|en|para|de|con|"
        r"dilluns|dimarts|dimecres|dijous|divendres|dissabte|diumenge)\b"
        r"|[,;]|$))",
        text, re.I,
    ):
        candidate = _limpiar_cliente(match.group(1))
        # «a la Marta», «amb en Joan»: en catalán el nombre lleva artículo.
        personal = re.match(r"^(?:la|el|en|na)\s+([A-ZÁÉÍÓÚÀÈÒÏÜÇ][\w'·-]+(?:\s+[A-ZÁÉÍÓÚÀÈÒÏÜÇ][\w'·-]+)*)$",
                            candidate)
        if personal:
            candidate = personal.group(1)
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
    for match in re.finditer(r"\b(?:para|de|per(?=\s+[a-zàèéíòóú]+(?:ar|er|ir|re)\b))\s+(.+?)"
                             + _HASTA_LA_FECHA, text, re.I):
        value = match.group(1).strip().rstrip(".!?¿¡;")
        folded = _norm(value)
        if (not value or value == cliente or len(value) > 200
                # «de la mañana» dejaba el trabajo en «la».
                or folded in {"la", "el", "los", "las", "un", "una", "lo"}
                or re.match(_AGENDA_NOT_A_TASK, folded)
                or re.search(_AGENDA_NOUN, folded)
                or (cliente and _norm(value) == _norm(cliente))):
            continue
        if _looks_like_task(value) or value != cliente:
            return value
    return "Trabajo"


def _seccion_web(norm: str) -> str:
    """Dónde se hace en la web lo que por WhatsApp no se hace: «su apartado» no
    le decía a nadie adónde ir."""
    for palabras, seccion in (
        (("factura", "ticket", "tiquet"), "Facturas"),
        (("presupuest", "pressupost"), "Presupuestos"),
        (("gasto", "despesa"), "Costes"),
        (("cita", "trabajo", "visita", "agenda", "feina"), "Trabajos"),
        (("proyecto", "projecte", "obra"), "Proyectos"),
        (("cliente", "client"), "Clientes"),
        (("cobro", "pago"), "Cobros"),
    ):
        if any(palabra in norm for palabra in palabras):
            return seccion
    return "el apartado correspondiente"


def safety_refusal(text: str) -> str | None:
    """Una orden negativa o destructiva nunca se interpreta como un alta."""
    risk = inspect_money_intent(text)
    if risk:
        return risk.reply
    norm = _norm(text)
    if _cambio_de_cita(text, norm):
        # Mover o cancelar una cita sí se prepara: no se borra nada y pasa por
        # la tarjeta de SÍ (ver `_cambio_de_cita`).
        return None
    # Verbos conjugados, no prefijos: «Carla Borràs» o «Cancelas» son nombres.
    if re.search(
        r"\b(borr(?:a|ar|ame|alo|ala|alos|alas|ad)|elimin(?:a|ar|ame|alo|ala|alos|alas|ad)|"
        r"anul(?:a|ar|alo|ala|ad)|cancel(?:a|ar|ame|alo|ala|ad)|esborr(?:a|ar|eu)|"
        r"suprim(?:e|ir|elo|ela|id))\b", norm):
        return ("Borrar, anular o cancelar no lo hago por WhatsApp: es difícil de "
                f"deshacer y prefiero que lo veas tú. Hazlo en la web, en "
                f"**{_seccion_web(norm)}**. No he cambiado nada.")
    if re.search(r"^(?:por favor[, ]+)?(cambia\w*|modifica\w*|mueve|reprograma\w*|rectifica\w*)\b", norm) \
            and not _dato_de_cliente(text):
        # Corregir el teléfono o el NIF de una ficha sí se prepara (con revisión).
        return ("Cambiar algo que ya está guardado no lo hago por WhatsApp. Hazlo en la "
                f"web, en **{_seccion_web(norm)}**. No he creado ni cambiado nada.")
    if re.match(r"^(?:por favor[, ]+)?(?:paga|pagar|pagame|abona|abonar|ingresa|ingresar)\b", norm):
        # «Paga la factura de la luz» acababa pidiendo datos para crear una factura.
        return ("No puedo pagar nada ni mover dinero por ti. Si lo que quieres es apuntar "
                "que ya lo has pagado, dime «he pagado 60 euros de luz» y lo registro como "
                "gasto. No he ejecutado ninguna operación.")
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
    r"^(?:si|sii|sip|vale|ok|okey|okay|confirmo|confirmar|confirmalo|confirmala|"
    r"correcto|exacto|perfecto|adelante|dale|claro|de acuerdo|eso es|hazlo|hazla|"
    r"venga|guardalo|guardala|endavant|d'acord|fes-ho)\b")
# Palabras que pueden acompañar a un sí sin cambiar lo que se confirma.
_COLA_SIN_ORDEN = re.compile(
    r"^(?:[\s,.;:!¡]|y|i|tambien|ademes|ademas|por favor|porfa|gracias|si|"
    r"confirmo|confirmar|confirmalo|confirmala|correcto|exacto|perfecto|vale|ok|"
    r"okey|claro|dale|esta bien|todo bien|bien|guardalo|guardala|venga|"
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
    # «Factura a cliente María» también, sin artículo.
    nombre = re.sub(r"^(?:(?:el|la|els|les|l')\s+)?(?:client[ea]?|proveedor[a]?)\s*:?\s+",
                    "", nombre, flags=re.I)
    partes = nombre.split()
    while partes and partes[-1].lower().strip(",.") in _CONECTORES_FINALES:
        partes.pop()
    return " ".join(partes).strip(" ,.")


_CITA = r"(?:cita|visita|trabajo|feina)"
_VERBO_CANCELA_CITA = (r"(?:cancela|cancelar|cancelame|cancelala|anula|anular|anulame|anulala|"
                       r"desconvoca|suspende)")
_VERBO_MUEVE_CITA = (r"(?:mueve|muevela|mover|moverla|muevame|cambia|cambiame|cambiala|"
                     r"cambiar|aplaza|aplazame|aplazala|aplazar|retrasa|retrasame|"
                     r"retrasala|retrasar|adelanta|adelantame|adelantala|adelantar|"
                     r"reprograma|reprogramame|reprogramala|pasa|pasame|pasala)")
_DIA_DICHO = (r"(?:hoy|avui|manana|dema|pasado|lunes|martes|miercoles|jueves|viernes|"
              r"sabado|domingo|dia|\d)")
# Lo que corta el nombre del cliente: «… de Juan García | del jueves | al lunes».
_CORTE_NOMBRE = {"del", "al", "para", "a", "que", "y", "por", "este", "esta", "hoy",
                 "manana", "pasado", "lunes", "martes", "miercoles", "jueves", "viernes",
                 "sabado", "domingo"}


def _cambio_de_cita(text: str, norm: str) -> tuple[str, dict] | None:
    """«Cancela la cita de Juan», «mueve la visita de Ana al jueves a las 10».

    El verbo tiene que ir pegado a la cita («cancela la cita», «Juan ha
    cancelado la visita»): «pasa la factura del trabajo» no es mover nada. La
    cita se nombra por su número o por el cliente, y «del jueves» dice cuál si
    tiene varias. Antes se remitía a la web, que solo deja borrarla.
    """
    if re.match(r"^(?:no|nunca)\b", norm) \
            or re.search(r"\b(?:factur\w*|presupuest\w*|gast\w*|cobr\w*)\b", norm):
        return None
    articulo = r"(?:\s+(?:la|el|mi|su|esa|ese|esta|este))?"
    cancelar = re.search(rf"\b{_VERBO_CANCELA_CITA}{articulo}\s+{_CITA}\b", norm) \
        or re.search(rf"\b(?:ha|han)\s+(?:cancelado|anulado){articulo}\s+{_CITA}\b", norm)
    mover = re.search(rf"\b{_VERBO_MUEVE_CITA}{articulo}\s+{_CITA}\b", norm) \
        or re.search(rf"\b(?:ha|han)\s+(?:aplazado|movido|cambiado|retrasado|adelantado)"
                     rf"{articulo}\s+{_CITA}\b", norm)
    if not cancelar and not mover:
        return None
    if "?" in text or "¿" in text:
        return (NEED_REVIEW, {"reply": (
            "Sí: dime «cancela la cita de Juan» o «mueve la cita de Juan al jueves a "
            "las 10». Te enseño la cita y no cambio nada hasta que digas SÍ.")})
    tool = "cancelar_cita" if cancelar else "mover_cita"
    args: dict = {}
    crudo = str(text or "").strip().rstrip(".!")
    numero = re.search(rf"\b{_CITA}\s*(?:n[uú]mero\s+)?#?\s*(\d{{1,9}})\b", norm)
    resto = ""
    if numero:
        args["trabajo_id"] = int(numero.group(1))
        resto = norm[numero.end():]
    else:
        de_quien = re.search(rf"\b{_CITA}\s+(?:de|con|a|del cliente|de la cliente)\s+(.+)$",
                             crudo, re.I)
        quien_dice = re.match(r"^\s*(?:el\s+cliente\s+|la\s+cliente\s+)?(.+?)\s+(?:me\s+)?"
                              r"(?:ha|han)\s+(?:cancelado|anulado|aplazado|movido|cambiado|"
                              r"retrasado|adelantado)\b", crudo, re.I)
        palabras = (de_quien.group(1) if de_quien else
                    quien_dice.group(1) if quien_dice else "").split()
        nombre = []
        for i, palabra in enumerate(palabras):
            plano = _norm(palabra).strip(",.;")
            siguiente = _norm(palabras[i + 1]) if i + 1 < len(palabras) else ""
            if plano in _CORTE_NOMBRE or plano[:1].isdigit() or (
                    plano in {"el", "la", "de"} and re.match(_DIA_DICHO, siguiente)):
                break
            nombre.append(palabra)
            if palabra.endswith((",", ";")):
                break
        cliente = _limpiar_cliente(" ".join(nombre))
        if cliente:
            args["cliente"] = cliente
        if de_quien:
            resto = _norm(" ".join(palabras[len(nombre):]))
        else:
            resto = _norm(crudo[(quien_dice.end() if quien_dice else 0):])
    origen, destino = "", resto
    tramo = re.search(r"\bdel?\s+(.+?)\s+(?:al|a el|para el|para)\s+(.+)$", resto)
    if tramo and re.match(_DIA_DICHO, tramo.group(1)):
        origen, destino = tramo.group(1), tramo.group(2)
    elif tool == "cancelar_cita":
        origen, destino = resto, ""
    if origen:
        dia = parse_date(origen)
        if dia:
            args["dia"] = dia[:10]
    # «Cancela la cita de mañana» vale sin cliente (la única de ese día); mover
    # sin cliente no, que «la de mañana a las 11» no dice cuál es el origen.
    if not args.get("cliente") and not args.get("trabajo_id") \
            and (tool == "mover_cita" or not args.get("dia")):
        return (NEED_REVIEW, {"reply": (
            "¿Qué cita? Dime de qué cliente es: «cancela la cita de Juan» o «mueve la "
            "visita de Ana al jueves a las 10». No he cambiado nada.")})
    if tool == "mover_cita":
        # Sin hora dicha no se inventa: «al jueves» conserva la hora de la cita.
        explicita = re.search(r"\ba\s+l(?:a|as|es)\s+\S|\d{1,2}(?:[:.]\d{2})?\s*h\b|"
                              r"\b(?:por|de)\s+la\s+(?:manana|tarde|noche)\b", destino)
        fecha = parse_date(destino)
        if fecha and args.get("dia") and fecha[:10] < args["dia"] \
                and not re.search(r"\badelant\w*", norm):
            # «Del martes al viernes» un jueves: el viernes que sigue a ese martes.
            fecha = parse_date(destino, base=date.fromisoformat(args["dia"]))
        if fecha:
            args["nueva_fecha"] = fecha[:10]
        hora = _parse_time(destino) if explicita else None
        if hora:
            args["nueva_hora"] = f"{hora[0]:02d}:{hora[1]:02d}"
        if not fecha and not hora:
            return (NEED_REVIEW, {"reply": (
                "¿A qué día y hora la paso? Dímelo entero: «mueve la cita de "
                f"{args.get('cliente') or 'Juan'} al jueves a las 10». No he cambiado nada.")})
    return (tool, args)


_RECHAZA_PRESUPUESTO = (r"\b(?:rechaz\w*|rebutj\w*|no lo quiere|no le interesa|"
                        r"(?:ha|han|me ha|me han) dicho que no|dice que no)\b")
_ACEPTA_PRESUPUESTO = (r"\b(?:acept\w*|aprueb\w*|aprobad\w*|accept\w*|"
                       r"(?:ha|han|me ha|me han) dicho que si|dice que si)\b"
                       r"|\b(?:pasa\w*|convier\w*|convertir\w*|transform\w*)\b.*\b(?:a|en) factura\b"
                       r"|\bfactura\w* (?:el|del) presupuesto\b")
_VERBO_DECISION = (r"(?:me\s+)?(?:ha\s+|han\s+)?(?:aceptado|acepta|aprobado|aprueba|"
                   r"rechazado|rechaza|dicho que (?:s[ií]|no)|dice que (?:s[ií]|no))\b")


def _decision_de_presupuesto(text: str, norm: str) -> tuple[str, dict] | None:
    """«Acepta el presupuesto 12», «Juan ha rechazado el presupuesto».

    Aceptar deja la factura en borrador, así que «pasa el presupuesto a factura»
    es lo mismo. El presupuesto se nombra por su número (#id, el que sale en «mis
    presupuestos») o por su cliente, si tiene uno solo sin decidir. Antes se
    contestaba que por WhatsApp no se hacía.
    """
    if not re.search(r"\b(?:presupuesto|pressupost)\b", norm):
        return None
    if re.search(_RECHAZA_PRESUPUESTO, norm):
        tool = "rechazar_presupuesto"
    elif re.search(_ACEPTA_PRESUPUESTO, norm):
        tool = "aceptar_presupuesto"
    else:
        return None
    numero = re.search(r"\b(?:presupuesto|pressupost)\s*#?\s*(\d{1,9})\b|#\s*(\d{1,9})\b", norm)
    # «¿Qué presupuestos tengo aceptados?» es una consulta, no una decisión.
    if not numero and ("?" in text or "¿" in text or re.search(r"\bpresupuestos\b", norm)):
        return None
    if numero:
        return (tool, {"presupuesto_id": int(numero.group(1) or numero.group(2))})
    crudo = str(text or "").strip()
    nombre = ""
    de_quien = re.search(r"\b(?:presupuesto|pressupost)\s+(?:de|a|para|del|per a)\s+(.+)$",
                         crudo, re.I)
    if de_quien:
        nombre = re.split(r"\s*[,.;!]\s*|\s+(?:y|i|que|a factura|en factura)\s+",
                          de_quien.group(1), maxsplit=1)[0]
    else:
        quien = re.match(r"^\s*(?:ya\s+)?(.+?)\s+" + _VERBO_DECISION, crudo, re.I)
        if quien:
            nombre = quien.group(1)
    nombre = _limpiar_cliente(nombre)
    if nombre and _norm(nombre) not in {"me", "le", "lo", "se", "ya", "el", "la", "si"} \
            and len(nombre.split()) <= 5:
        return (tool, {"cliente": nombre})
    return (NEED_REVIEW, {"reply": (
        "¿Qué presupuesto? Dime su número («acepta el presupuesto 12») o el cliente "
        "(«Juan ha aceptado el presupuesto»). Con «mis presupuestos» te enseño los "
        "números. No he cambiado nada.")})


_IMPORTE_SUELTO = re.compile(
    rf"^(?:(?:por|de|son|total|importe|precio|base)\s*:?\s*)?({_AMOUNT_RE})\s*(?:€|euros?|eur)?"
    r"(?:\s*(?:\+|mas|más)\s*(?:el\s+)?iva|\s+(?:con\s+)?iva\s+incluido|\s+con\s+(?:el\s+)?iva|"
    r"\s+sin\s+iva)?$", re.I)


def _documento_por_trozos(text: str, palabra: str) -> dict | None:
    """«Factura a Juan García, 120 euros, cambio de grifo»: la orden dictada a trozos.

    Por voz se dice así, con pausas que Whisper escribe como comas o puntos, y la
    lectura por posición se llevaba «euros, cambio de grifo» como concepto. Cada
    trozo es el cliente (el primero), el importe (el único con cifra) o parte del
    concepto; «concepto X» e «importe X» mandan. Ante la duda —dos importes, una
    cifra dentro del concepto— devuelve `None` y decide el lector de siempre.
    """
    m = re.match(rf"^\s*(?:(?:hazme|haz|crea|creame|créame|prepara|preparame|prepárame|"
                 rf"genera|quiero|necesito)\s+)?(?:una?\s+|el\s+|la\s+)?{palabra}\s+"
                 r"(?:a|para|per\s+a)\s+", text, re.I)
    if not m:
        return None
    trozos = [t.strip(" .") for t in re.split(r"\s*[,;:]\s+|\.\s+|\.$", text[m.end():])
              if t.strip(" .")]
    # «Reformas Martínez, S.L., 120 euros…»: la coma de la forma societaria.
    while len(trozos) > 1 and trozos[1].replace(".", "").upper() in _SIGLAS_CON_PUNTO:
        trozos[0:2] = [f"{trozos[0]}, {trozos[1]}."]
    if len(trozos) < 3 or re.search(r"\d|\s(?:por|de)\s+\d", trozos[0]):
        return None
    importe, conceptos = None, []
    for trozo in trozos[1:]:
        etiqueta = re.match(r"^(concepto|importe|precio|total|base)\s*:?\s*(.+)$", trozo, re.I)
        if etiqueta and _norm(etiqueta.group(1)) == "concepto":
            conceptos.append(etiqueta.group(2))
            continue
        cifra = _IMPORTE_SUELTO.match(trozo)
        if cifra:
            if importe is not None:
                return None
            importe = _amount_value(cifra.group(1))
            continue
        # «2 grifos» es el concepto con su cantidad; otra cifra suelta, no se sabe.
        cantidad = re.match(r"^\d{1,3}\s+[^\W\d_]", trozo)
        if (re.search(r"\d", trozo) and not cantidad) or re.search(r"\b(?:iva|irpf)\b", _norm(trozo)):
            return None
        conceptos.append(re.sub(r"^(?:por|para)\s+", "", trozo, flags=re.I))
    concepto = _limpiar_concepto(", ".join(conceptos))
    cliente = _limpiar_cliente(trozos[0])
    if trozos[0].endswith(".") and trozos[0][:-1] == cliente:
        cliente = trozos[0]  # «S.L.» lleva su punto en la factura
    if not importe or importe <= 0 or not concepto or not cliente:
        return None
    return {"cliente": cliente, "concepto": concepto, "base": importe}


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
    # «juan 500 baño»: con el importe en medio, delante va el cliente y detrás el
    # concepto. Antes salía el cliente «juan baño» con concepto «Servicio».
    limpia = lambda trozo: re.sub(  # noqa: E731
        r"\s*\b(?:euros?|eur|€|mas iva|más iva|con iva)\b\s*", " ", trozo, flags=re.I
    ).strip(" ,.;:")
    detras = limpia(text[importe.end():])
    delante = limpia(text[:importe.start()])
    if detras and re.search(r"[^\W\d_]", detras) and resto.endswith(detras) \
            and len(resto) > len(detras):
        nombre = _limpiar_cliente(resto[:len(resto) - len(detras)].strip(" ,.;:"))
        if nombre and delante:
            return {"cliente": nombre, "concepto": _limpiar_concepto(
                re.sub(r"^(?:de|por|para)\s+", "", detras, flags=re.I)), "base": valor}
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
    # «factura a  por  euros»: solo conectores y unidades no son el nombre de nadie.
    if all(p in {"por", "de", "del", "para", "a", "al", "con", "y", "el", "la", "un", "una",
                 "euro", "euros", "eur", "mas", "iva", "en"} for p in _norm(valor).split()):
        return None
    return valor


# Datos etiquetados, como se escriben en el móvil: «concepto: reforma de la
# habitación», «cliente: María Antonia», «el cliente es: …». Cada valor llega
# hasta la siguiente etiqueta. Antes solo se entendía «factura a X por Y» y un
# mensaje con todo etiquetado dejaba un borrador sin cliente ni concepto.
_ETIQUETA = re.compile(
    r"(?:\b(?:el|la|mi)\s+)?\b(?P<campo>clienta|cliente|concepto|importe|precio)\b"
    r"\s*(?:(?:es|ser[aá]|son)\b)?\s*[:=]?\s*", re.I)
_COLA_SIN_VALOR = re.compile(
    r"(?:\s+|^)(?:a|al|para|para\s+el|para\s+la|de|del|y|el|la|con|por|al\s+que|"
    r"a\s+nombre\s+de)\s*$", re.I)
_IMPORTE_AL_FINAL = re.compile(
    rf"\s*(?:de\s+)?{_AMOUNT_RE}\s*(?:€|euros?|eur)?(?:\s*\+\s*iva)?\s*$", re.I)


def campos_etiquetados(text: str) -> dict:
    """Cliente y concepto dichos con etiqueta, o «María es el cliente»."""
    texto = _erratas(text or "")
    datos: dict = {}
    marcas = list(_ETIQUETA.finditer(texto))
    for i, marca in enumerate(marcas):
        campo = marca.group("campo").lower()
        if campo in {"importe", "precio"}:
            continue
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        valor = re.split(r"[;\n]", texto[marca.end():fin])[0]
        # «Maria Antonia por 350 + iva» o «ventana con el 10%»: el importe y los
        # impuestos no son parte del nombre ni del concepto.
        valor = re.split(rf"\s+(?:(?:por|de|son|x)\s+)?{_AMOUNT_RE}\s*(?:€|euros?|eur\b|%)"
                         rf"|\s+(?:por|de|son)\s+{_AMOUNT_RE}\b|\s*\+\s*iva\b"
                         r"|\s+(?:con|mas|más)\s+(?:el\s+)?(?:iva|irpf|\d)", valor,
                         maxsplit=1, flags=re.I)[0]
        valor = re.sub(r"^(?:de|del)\s+", "", valor.strip(" ,.:"), flags=re.I)
        valor = _COLA_SIN_VALOR.sub("", valor).strip(" ,.:")
        if campo == "concepto":
            valor = _IMPORTE_AL_FINAL.sub("", valor).strip(" ,.:")
            valor = _limpio_o_nada(valor)
            if valor:
                datos.setdefault("concepto", valor)
        else:
            # «Crea el cliente Pere» es dar de alta, no decir de quién es la
            # factura: el cliente necesita «es», «:» o ir detrás de «a/para».
            separado = re.search(r"(?:\bes\b|ser[aá]|[:=])", marca.group(0), re.I)
            detras = re.search(r"\b(?:a|para|per)\s*$", texto[:marca.start()], re.I)
            if not (separado or detras):
                continue
            valor = _limpio_o_nada(_limpiar_cliente(valor))
            if valor:
                datos.setdefault("cliente", valor)
    if "cliente" not in datos:
        m = re.match(r"\s*(?:(?:vale|ok|pues),?\s+)?(.+?)\s+es\s+(?:el|la|mi)\s+client[ea]\b",
                     texto, re.I)
        if m:
            valor = _limpio_o_nada(_limpiar_cliente(m.group(1)))
            if valor:
                datos["cliente"] = valor
    return datos


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
    # Lo etiquetado manda sobre lo deducido por la posición de las palabras.
    args.update(campos_etiquetados(text))
    return args


_TELEFONO_RE = re.compile(r"(\+?\d[\d\s.\-]{7,}\d)")
# Lo que viene detrás del nombre cuando alguien dicta la ficha entera de un tirón.
_DATO_DE_CONTACTO = re.compile(
    r"\b(?:tel[eéè]fono?|telf?|m[oóò]vil|m[oò]bil|whatsapp|correo|correu|email|e-mail|nif|cif|dni|adre[çc]a|"
    r"direcci[oó]n|domicilio|calle|avenida|zona)\b", re.I)


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# NIF, NIE y CIF sueltos («con nif 12345678Z» o «B12345678» a secas).
_NIF_RE = re.compile(
    r"\b(\d{8}\s?-?[A-Z]|[XYZ]\s?-?\d{7}\s?-?[A-Z]|[ABCDEFGHJNPQRSUVW]\s?-?\d{7}[0-9A-J])\b",
    re.I)
_CLAVE_NIF = re.compile(r"\b(?:nif|cif|dni|nie)\b\s*(?:es\s+(?:el\s+)?)?:?\s*", re.I)
_CLAVE_DIRECCION = re.compile(
    r"\b(?:direcci[oó]n|domicilio|adre[çc]a|vive\s+en|est[aá]\s+en)\b\s*(?:es\s+)?:?\s*"
    r"|\b(?=(?:calle|c/|avenida|avda\.?|av\.|plaza|pza\.?|paseo|pg\.?|carrer|"
    r"camino|ronda|traves[ií]a|urbanizaci[oó]n)\s)", re.I)
# Un móvil o fijo español dictado con o sin espacios, con o sin prefijo.
_MOVIL_SUELTO = re.compile(r"(?<![\w+])((?:\+?34[\s.\-]?)?[6789](?:[\s.\-]?\d){8})(?!\d)")
_CLAVE_TELEFONO = re.compile(r"\b(?:tel[eéè]fono?|telf?|tlf|m[oóò]vil|m[oò]bil|whatsapp|n[uú]mero)\b"
                             r"\s*(?:es\s+(?:el\s+)?)?:?\s*", re.I)
_CLAVE_EMAIL = re.compile(r"\b(?:correo(?:\s+electr[oó]nico)?|correu|email|e-mail|mail)\b"
                          r"\s*(?:es\s+)?:?\s*", re.I)


def correo_dictado(texto: str) -> str:
    """«juan punto garcia arroba gmail punto com» → «juan.garcia@gmail.com»."""
    if not re.search(r"\barroba\b", texto or "", re.I):
        return texto
    def une(m: re.Match) -> str:
        trozo = m.group(0)
        trozo = re.sub(r"\s*\barroba\b\s*", "@", trozo, flags=re.I)
        trozo = re.sub(r"\s*\bpunto\b\s*", ".", trozo, flags=re.I)
        trozo = re.sub(r"\s*\bgui[oó]n\s+bajo\b\s*", "_", trozo, flags=re.I)
        trozo = re.sub(r"\s*\bgui[oó]n\b\s*", "-", trozo, flags=re.I)
        return trozo.replace(" ", "").lower()
    # Solo el tramo que forma el correo: palabras sueltas unidas por punto/arroba.
    return re.sub(r"[\w.+-]+(?:\s+(?:punto|gui[oó]n(?:\s+bajo)?)\s+[\w+-]+)*\s+arroba\s+"
                  r"[\w-]+(?:\s+punto\s+[\w-]+)+", une, texto, flags=re.I)


def datos_de_ficha(texto: str) -> tuple[int, dict]:
    """Datos de contacto dictados con el nombre: teléfono, correo, NIF y dirección.

    Devuelve `(dónde empiezan, datos)`. Antes solo se guardaba el teléfono, y el
    correo o el NIF acababan pegados al nombre o perdidos sin avisar; justo lo
    que luego hace falta para emitir y enviar la factura.
    """
    texto = correo_dictado(str(texto or ""))
    datos: dict = {}
    inicios: list[int] = []
    correo = _EMAIL_RE.search(texto)
    if correo:
        datos["email"] = correo.group(0).lower()
        clave = None
        for clave in _CLAVE_EMAIL.finditer(texto[:correo.start()]):
            pass
        inicios.append(clave.start() if clave and not texto[clave.end():correo.start()].strip()
                       else correo.start())
    clave_nif = _CLAVE_NIF.search(texto)
    nif = _NIF_RE.search(texto, clave_nif.end() if clave_nif else 0)
    if nif and (clave_nif or not correo or not (correo.start() <= nif.start() < correo.end())):
        datos["nif"] = re.sub(r"[\s-]", "", nif.group(1)).upper()
        inicios.append(clave_nif.start() if clave_nif else nif.start())
    elif clave_nif:
        inicios.append(clave_nif.start())
    tapados = [m.span() for m in (correo, nif) if m]

    def libre(m) -> bool:
        return not any(a <= m.start() < b for a, b in tapados)

    clave_tel = _CLAVE_TELEFONO.search(texto)
    movil = next((m for m in _MOVIL_SUELTO.finditer(texto, clave_tel.end() if clave_tel else 0)
                  if libre(m)), None)
    if not movil and clave_tel:
        movil = next((m for m in _TELEFONO_RE.finditer(texto, clave_tel.end()) if libre(m)), None)
    if movil:
        datos["telefono"] = re.sub(r"[\s.\-]", "", movil.group(1))
        inicios.append(clave_tel.start() if clave_tel else movil.start())
        tapados.append(movil.span())
    direccion = _CLAVE_DIRECCION.search(texto)
    if direccion:
        inicios.append(direccion.start())
        resto = texto[direccion.end():]
        # La dirección acaba donde empieza otro dato.
        fin = len(resto)
        for patron in (_CLAVE_TELEFONO, _CLAVE_EMAIL, _CLAVE_NIF, _EMAIL_RE, _MOVIL_SUELTO):
            otro = patron.search(resto)
            if otro:
                fin = min(fin, otro.start())
        valor = re.sub(r"\s+(?:y|con|i|amb)\s*$", "", resto[:fin].strip(" ,;")).strip(" ,;.")
        if valor and re.search(r"[^\W\d_]", valor):
            datos["direccion"] = valor
    return (min(inicios) if inicios else -1, datos)


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
    inicio, datos = datos_de_ficha(texto)
    if inicio > 0:
        # «Laura Gimeno tel 612 34 56 78» o «Laura Gimeno laura@x.es»: el nombre
        # acaba donde empiezan los datos, con o sin «con» delante.
        texto = re.sub(r"(?:[\s,;:]+(?:y|con|i|amb|su|sus|es|de|el|la|que|tiene|seu|té))*[\s,;:]*$",
                       "", texto[:inicio], flags=re.I).strip()
        texto = _recortar(texto) if texto else texto
        if not texto:
            return (None, None)
    elif inicio == 0:
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
    telefono = telefono or datos.get("telefono")
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
    # «Ticket a Marta de 50 euros por revisión»: un ticket A alguien es una venta;
    # se apuntaba como gasto.
    if re.match(r"^(?:un\s+)?(?:ticket|tiquet)\s+(?:a|para|per\s+a)\s+\S", norm):
        text = re.sub(r"\b(ticket|tiquet)\b", "ticket de venta", text, count=1, flags=re.I)
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


_CAMPO_FICHA = (r"(?P<campo>nif|cif|dni|nie|tel[eé]fono|telf?|m[oó]vil|n[uú]mero(?:\s+de\s+tel[eé]fono)?|"
                r"correo(?:\s+electr[oó]nico)?|email|e-mail|mail|direcci[oó]n|domicilio)")
_CAMPO_A_ARG = (("nif", "nif"), ("cif", "nif"), ("dni", "nif"), ("nie", "nif"),
                ("tel", "telefono"), ("movil", "telefono"), ("numero", "telefono"),
                ("correo", "email"), ("email", "email"), ("e-mail", "email"),
                ("mail", "email"), ("direccion", "direccion"), ("domicilio", "direccion"))


def _pregunta_por_cliente(text: str, norm: str) -> tuple[str, dict] | None:
    """«Dame el teléfono de X», «¿cuál es el NIF de X?», «¿qué facturas tiene X?»."""
    campos = {"telefono": "telefono", "movil": "telefono", "numero": "telefono",
              "correo": "email", "email": "email", "mail": "email", "nif": "nif",
              "cif": "nif", "dni": "nif", "direccion": "direccion",
              "domicilio": "direccion", "datos": None, "ficha": None,
              "facturas": "facturas", "historial": "facturas"}
    claves = "|".join(campos)
    m = re.match(
        rf"^(?:y\s+)?(?:dame|dime|pasame|ensename|muestrame|cual es|que|cual|ver|mira|busca|"
        rf"tienes|tengo)?\s*(?:el|la|los|las|su|sus)?\s*({claves})\s+(?:de|del|de la)\s+"
        r"(?:client[ea]\s+)?(.+?)\s*\??$", norm)
    if not m:
        m2 = re.match(r"^(?:y\s+)?(?:que|cuantas|quines|quantes)\s+(?:facturas|factures)\s+"
                      r"(?:tiene|te|le he hecho a|tengo con|tinc amb|le he hecho|le hice a|hay de)\s+"
                      r"(?:el\s+cliente\s+|el\s+client\s+)?(.+?)\s*\??$", norm)
        if not m2:
            return None
        campo, nombre_norm = "facturas", m2.group(1)
    else:
        campo, nombre_norm = campos[m.group(1)], m.group(2)
    if re.search(r"\b(?:factura|presupuesto|ticket|mes|semana|ano|trimestre)\b", nombre_norm) \
            or re.match(r"^(?:hoy|manana|este|esta|mis|los|las)\b", nombre_norm):
        return None
    crudo = text.strip().rstrip("?¿!. ")
    nombre = crudo[len(crudo) - len(nombre_norm):] if len(crudo) >= len(nombre_norm) else nombre_norm
    nombre = _limpiar_cliente(nombre)
    if not nombre:
        return None
    return ("ver_cliente", {"cliente": nombre, **({"dato": campo} if campo else {})})


def _dato_de_cliente(text: str) -> tuple[str, dict] | None:
    """«El NIF de Laura Gimeno es 12345678Z» completa la ficha que ya existe.

    También «añade el correo x@y.es a Laura», «ponle a Laura el teléfono …» y
    «cambia el teléfono de Laura a …». Antes soltaba el parte del día.
    """
    t = correo_dictado(text.strip().rstrip(".!"))
    formas = (
        # «el NIF de Laura es X», «el teléfono del cliente Laura Gimeno es X»
        rf"^(?:(?:cambia|cambiar|actualiza|corrige)\s+)?(?:el|la|su)?\s*{_CAMPO_FICHA}\s+"
        r"(?:de|del|de\s+la)\s+(?:client[ea]\s+)?(?P<cliente>.+?)\s+"
        r"(?:es|és|será|sera|a|por|:)\s*(?:el\s+|la\s+)?(?P<valor>.+)$",
        # «añade el correo X a Laura», «pon el NIF X al cliente Laura»
        rf"^(?:añade|anade|agrega|pon|ponle|guarda|apunta|mete)\s+(?:el|la|su)?\s*{_CAMPO_FICHA}"
        r"\s*:?\s+(?P<valor>.+?)\s+(?:a|al|para|de|del)\s+(?:client[ea]\s+)?(?P<cliente>.+)$",
        # «ponle a Laura el teléfono X», «añade a Laura el correo X»
        r"^(?:añade|anade|agrega|pon|ponle|guarda|apunta)(?:le)?\s+(?:a|al)\s+(?:client[ea]\s+)?"
        rf"(?P<cliente>.+?)\s+(?:el|la|su)?\s*{_CAMPO_FICHA}\s*:?\s+(?P<valor>.+)$",
    )
    for forma in formas:
        m = re.match(forma, t, re.I)
        if not m:
            continue
        campo = _norm(m.group("campo"))
        arg = next(a for clave, a in _CAMPO_A_ARG if campo.startswith(clave))
        cliente = _limpiar_cliente(m.group("cliente"))
        valor = m.group("valor").strip(" ,;:")
        if (not cliente or not valor or len(cliente.split()) > 6
                or re.search(r"\b(?:factura|presupuesto|ticket|tiquet|gasto|proyecto)\b",
                             _norm(cliente))):
            return None
        if arg in {"nif", "telefono"}:
            valor = re.sub(r"[\s.\-]", "", valor)
        # El valor tiene que parecer lo que se dice que es: «el número de la
        # factura 3 es 12» no es un teléfono.
        if ((arg == "telefono" and not re.fullmatch(r"\+?\d{9,15}", valor))
                or (arg == "email" and "@" not in valor)
                or (arg == "nif" and not re.fullmatch(r"[A-Z0-9]{8,10}", valor.upper()))
                or (arg == "direccion" and not re.search(r"[^\W\d_]", valor))):
            return None
        return ("actualizar_cliente", {"cliente": cliente, arg: valor})
    return None


_OTRO_TEMA = re.compile(
    r"\b(?:cobr\w*|pag\w*|factur\w*|iva|irpf|gast\w*|presupuest\w*|deb\w*|"
    r"impuest\w*|clientes?|proveedor\w*|document\w*|gestori\w*|proyect\w*)\b")


_FIN_DE_TROZO = (r"(?=\s+(?:a|para)\s+[a-záéíóúñ]+(?:ar|er|ir)\b|\s+(?:hoy|mañana|manana|pasado|"
                 r"el|este|esta|a\s+las|por\s+la|en)\b|[,.;]|$)")


def _visita_dicha(text: str) -> tuple[str, dict] | None:
    """«Mañana a las diez tengo que ir a casa de Juan a mirar la caldera».

    Así se cuenta una cita por voz, sin el verbo «agendar», y acababa en el parte
    del día. Solo cuenta con un sitio al que se va (casa de, la obra de…) y una
    fecha; si falta la fecha, que la pregunte la agenda de siempre.
    """
    m = re.search(r"\b(?:tengo que ir|he de ir|tengo que pasar|voy|ir[eé]|pasar[eé]|paso)\s+"
                  r"(?:a\s+|por\s+)(?:casa\s+de|la\s+casa\s+de|la\s+obra\s+de|el\s+local\s+de|"
                  r"la\s+tienda\s+de|ver\s+a|donde)\s+(.+?)" + _FIN_DE_TROZO, text, re.I)
    fecha = parse_date(text) if m else None
    if not m or not fecha:
        return None
    cliente = _limpiar_cliente(m.group(1))
    if not cliente or re.match(_AGENDA_NOT_A_NAME, _norm(cliente)):
        return None
    tarea = re.search(r"\b(?:a|para)\s+([a-záéíóúñ]+(?:ar|er|ir)\b.*?)"
                      r"(?=\s+(?:hoy|mañana|manana|pasado|este|esta|a\s+las|por\s+la|"
                      r"el\s+(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo|d[ií]a)|"
                      r"en\s+[A-ZÁÉÍÓÚ])\b|[,.;]|$)",
                      text[m.end():])
    return ("agendar_trabajo", {"cliente": cliente,
                                "descripcion": tarea.group(1).strip() if tarea else "Visita",
                                "fecha_hora": fecha})


# Lo que un autónomo apunta como gasto con dos palabras: «gasolina 20 euros».
_COSA_DE_GASTO = re.compile(
    r"\b(?:gasolina|gasoil|gasoleo|diesel|combustible|parking|aparcamiento|peaje\w*|"
    r"material\w*|herramienta\w*|ferreteria|tornill\w*|pintura|brocas?|silicona|cemento|"
    r"comida|menu|desayuno|cafe\w*|almuerzo|cena|dietas?|taxi|tren|metro|autobus|hotel|"
    r"luz|agua|telefono|movil|internet|seguro\w*|alquiler|renting|itv|taller|recambios?|"
    r"repuestos?|gestoria|autonomos|cuota|furgoneta|ruedas?|neumaticos?|uniformes?|"
    r"epis?|guantes|limpieza|papeleria|sellos|correos|mensajeria|envio)\b")


def _gasto_sin_verbo(text: str, norm: str) -> tuple[str, dict] | None:
    """«gasolina 20 euros» o «20 euros gasolina», sin «gasté» ni «apunta».

    Solo con palabras que son gasto de por sí: «Juan 100 euros» no se apunta como
    gasto, que igual es un cobro o una factura a medias.
    """
    limpio = norm.strip(" .,!")
    antes = re.fullmatch(rf"([a-z ]{{3,40}}?)\s+({_AMOUNT_RE})\s*(?:€|euros?|eur)?", limpio)
    despues = re.fullmatch(rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)\s+(?:de\s+|en\s+)?([a-z ]{{3,40}})",
                           limpio)
    m = antes or despues
    if not m:
        return None
    concepto_norm, cifra = (m.group(1), m.group(2)) if antes else (m.group(2), m.group(1))
    if not _COSA_DE_GASTO.search(concepto_norm) or re.search(
            r"\b(?:factura\w*|presupuest\w*|cobr\w*|cliente\w*|me (?:debe|pago|han))\b", limpio):
        return None
    importe = _amount_value(cifra)
    if importe <= 0:
        return None
    # El concepto con sus tildes, tal como se escribió.
    crudo = re.sub(rf"{_AMOUNT_RE}\s*(?:€|euros?|eur\b)?", " ", text, count=1, flags=re.I)
    concepto = _limpiar_concepto(re.sub(r"^\s*(?:de|en)\s+", "", " ".join(crudo.split()),
                                        flags=re.I))
    return ("registrar_gasto", {"concepto": concepto or concepto_norm.strip(),
                                "importe": importe})


def _pide_agendar(text: str, norm: str) -> bool:
    """«Agenda para mañana a las 12 a Jordi» crea una cita; no la consulta."""
    if not re.match(r"^(?:agenda\w*|apunta\w*|anota\w*|pon\w*)\b", norm):
        return False
    if _agenda_client(_quitar_fecha_concreta(text)):
        return True
    # «… a las 12 a Jordi»: el nombre va al final, detrás de la hora.
    return any(not re.match(_AGENDA_NOT_A_NAME, palabra) and not re.search(_AGENDA_NOUN, palabra)
               for palabra in re.findall(r"\b(?:a|con)\s+([a-z]{3,})\b", norm))


def _consulta_de_agenda(text: str, norm: str) -> tuple[str, dict] | None:
    """«¿Qué tengo el viernes?», «agenda de la semana», «mi agenda».

    Antes solo se entendían hoy y mañana: el resto acababa en la IA o, peor, en
    «me falta el cliente» como si se quisiera crear una cita.
    """
    from datetime import timedelta
    pregunta = re.search(
        r"^(?:y\s+)?(?:que|q)\s+(?:tengo|hay|tenemos|me toca|toca)\b|"
        r"^(?:y\s+)?(?:que|cuantos|cuantas)\s+(?:trabajos|citas|visitas)\b|"
        r"^(?:tengo|tenemos)\s+(?:algo|trabajo|citas?|visitas?)\b|"
        r"^(?:tinc|tenim)\s+(?:feina|res|alguna\s+cosa|visites?)\b|"
        r"^(?:estoy|estamos)\s+libres?\b|"
        r"^(?:mi|la|ver|ensename|muestrame|dime|pasame)\s+(?:la\s+)?agenda\b|"
        r"^agenda\s+(?:de|del|para|per)\s+(?:hoy|manana|la\s+semana|esta|el|la|este|"
        r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|pasado)|^agenda$|"
        r"^(?:mis|las|los)\s+(?:citas|trabajos|visitas)\b|"
        r"^(?:que|quins|quines)\s+(?:tinc|feines|treballs)\b", norm)
    if not pregunta or _OTRO_TEMA.search(norm) or _pide_agendar(text, norm):
        return None
    hoy = date.today()
    if re.search(r"\b(?:semana que viene|proxima semana|siguiente semana|"
                 r"setmana que ve|proxima setmana)\b", norm):
        lunes = hoy + timedelta(days=7 - hoy.weekday())
        return ("ver_agenda", {"fecha": lunes.isoformat(),
                               "hasta": (lunes + timedelta(days=6)).isoformat()})
    if re.search(r"\b(?:semana|setmana)\b", norm):
        return ("ver_agenda", {"fecha": hoy.isoformat(),
                               "hasta": (hoy + timedelta(days=6 - hoy.weekday())).isoformat()})
    if re.search(r"\b(?:mes|este mes)\b", norm):
        return None
    cuando = parse_date(text)
    if cuando:
        return ("ver_agenda", {"fecha": cuando[:10]})
    if re.search(r"agenda\s*$", norm) or re.search(r"\bproximos dias\b", norm):
        return ("ver_agenda", {"fecha": hoy.isoformat(),
                               "hasta": (hoy + timedelta(days=6)).isoformat()})
    return None


def _consulta_de_gastos(norm: str) -> tuple[str, dict] | None:
    """«¿Qué gastos he apuntado hoy?», «mis gastos del mes», «en qué he gastado»."""
    if not re.search(
            r"^(?:y\s+)?(?:que|cuales|cuantos|ver|mis|lista(?:me)?|ensename|muestrame|dime|"
            r"pasame)\s+(?:(?:son|han sido|los|las|mis|de)\s+)?gastos\b|^gastos(?:\s+de|\s+del|$)|"
            r"^(?:en que|en que cosas)\s+(?:he|hemos)\s+gastado", norm):
        return None
    from datetime import timedelta
    hoy = date.today()
    if re.search(r"\bhoy\b", norm):
        return ("ver_gastos", {"desde": hoy.isoformat(), "hasta": hoy.isoformat()})
    if re.search(r"\bayer\b", norm):
        ayer = (hoy - timedelta(days=1)).isoformat()
        return ("ver_gastos", {"desde": ayer, "hasta": ayer})
    if re.search(r"\bsemana\b", norm):
        return ("ver_gastos", {"desde": (hoy - timedelta(days=hoy.weekday())).isoformat(),
                               "hasta": hoy.isoformat()})
    return ("ver_gastos", {})


_MESES_DEL_ANIO = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                   "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def _periodo_del_resumen(norm: str) -> dict:
    """«Este año», «el mes pasado», «en agosto»: antes siempre era el mes en curso."""
    hoy = date.today()
    anio = re.search(r"\b(?:en|de|del)\s+(20\d\d)\b", norm)
    if re.search(r"\b(?:este|aquest)\s+(?:ano|any)\b|\bel ano\b|\ben lo que va de ano\b", norm):
        return {"anio": hoy.year}
    if re.search(r"\b(?:el\s+)?ano\s+pasado\b", norm):
        return {"anio": hoy.year - 1}
    if re.search(r"\b(?:el\s+)?mes\s+(?:pasado|anterior)\b|\bmes passat\b", norm):
        previo = (hoy.replace(day=1) - timedelta(days=1))
        return {"mes": previo.strftime("%Y-%m")}
    for numero, nombre in enumerate(_MESES_DEL_ANIO, start=1):
        if re.search(rf"\b(?:en|de|del mes de)\s+{nombre}\b", norm):
            year = int(anio.group(1)) if anio else (hoy.year if numero <= hoy.month else hoy.year - 1)
            return {"mes": f"{year}-{numero:02d}"}
    if anio:
        return {"anio": int(anio.group(1))}
    return {}


_PARTICULAS_DE_NOMBRE = {"de", "del", "la", "las", "los", "el", "y", "i", "e", "da", "do",
                         "dos", "van", "von", "d'", "en", "a", "al"}
_FORMAS_SOCIETARIAS = {"sl": "SL", "sa": "SA", "slu": "SLU", "sau": "SAU", "scp": "SCP",
                       "cb": "CB", "sc": "SC", "sll": "SLL", "sccl": "SCCL",
                       "s.l.": "S.L.", "s.a.": "S.A.", "s.l.u.": "S.L.U.", "s.c.p.": "S.C.P.",
                       "c.b.": "C.B."}


def nombre_presentable(nombre: str) -> str:
    """«pepe garcia» → «Pepe Garcia». Solo si se escribió todo en minúsculas.

    En el móvil casi nadie pone mayúsculas, y ese nombre es el que sale en la
    factura. Si quien escribe ha puesto alguna mayúscula se respeta tal cual:
    «McDonald's», «iPhone Reparaciones» o «de la Fuente» son decisiones suyas.
    """
    texto = str(nombre or "").strip()
    if not texto or texto != texto.lower():
        return texto
    palabras = []
    for indice, palabra in enumerate(texto.split()):
        suelta = palabra.strip(",")
        if suelta in _FORMAS_SOCIETARIAS:
            palabras.append(palabra.replace(suelta, _FORMAS_SOCIETARIAS[suelta]))
        elif indice and suelta in _PARTICULAS_DE_NOMBRE:
            palabras.append(palabra)
        else:
            # Cada trozo de un nombre compuesto («garcia-lopez», «o'brien»).
            palabras.append(re.sub(r"(^|[-'’])([^\W\d_])",
                                   lambda m: m.group(1) + m.group(2).upper(), palabra))
    return " ".join(palabras)


def _party_intent(papel: str, nombre: str) -> tuple[str, dict]:
    """Alta de cliente o proveedor con el nombre ya separado de sus datos."""
    tipo = "cliente" if _norm(papel).startswith("client") else "proveedor"
    nombre = re.sub(
        r"^(?:(?:que\s+)?se\s+llama|llamad[oa]|con\s+(?:el\s+)?nombre(?:\s+de)?|"
        r"de\s+nombre|a\s+nombre\s+de|que\s+es\s+diu|anomenad[ao]|que\s+es)\s*:?\s+",
        "", str(nombre or "").strip(), flags=re.I)
    # «crea al cliente Pepe y hazle una factura…»: la segunda orden no es parte
    # del nombre (se avisa aparte de que hay que mandarla por separado).
    nombre = re.split(r",?\s+(?:y|i)\s+(?:luego\s+|despu[eé]s\s+|adem[aá]s\s+)?"
                      r"(?=(?:haz\w*|crea\w*|agenda\w*|apunta\w*|anota\w*|registra\w*|"
                      r"factura\w*|presupuest\w*|prepara\w*|manda\w*|env[ií]a\w*)\b)",
                      nombre, maxsplit=1, flags=re.I)[0]
    limpio, telefono = parse_party_name(nombre)
    if not limpio:
        # Un «cliente» que es solo un número de teléfono no es el nombre de
        # nadie: se pregunta en vez de dejar una ficha llamada «600123456».
        return (NEED_PARTY_NAME, {"tipo": tipo, "motivo": "sin_nombre"})
    args: dict = {"nombre": nombre_presentable(limpio)}
    if tipo == "cliente":
        datos = datos_de_ficha(nombre)[1]
        if telefono:
            datos["telefono"] = telefono
        args.update({k: datos[k] for k in ("telefono", "email", "nif", "direccion")
                     if datos.get(k)})
    return (f"crear_{tipo}", args)


# Erratas de teclado del móvil en las palabras que deciden la orden. Una
# «fatura» no se entendía y la conversación acababa en el parte del negocio.
# Palabras que deciden la orden. Una falta cercana («factra», «fatura», «presupesto»,
# «clinte», «cocepto») se corrige; las formas válidas no se tocan.
_PALABRAS_CLAVE = ("factura", "presupuesto", "cliente", "concepto", "proveedor")
_FORMAS_VALIDAS = {
    "factura", "facturas", "facturar", "facturame", "facturo", "facturado",
    "facturamos", "facturaste", "facturaron", "facturaba",
    "facturada", "facturadas", "facturados", "facturacion",
    "presupuesto", "presupuestos", "presupuestar", "presupuestame", "presupuestado",
    "cliente", "clientes", "clienta", "clientas", "concepto", "conceptos",
    "proveedor", "proveedores", "proveedora", "proveedoras", "proveer", "proveido",
    "proveidor", "proveidors", "proveidora",
    # Catalán: son palabras correctas, no faltas.
    "facturat", "facturats", "facturada", "factures", "facturacio", "facturem",
    "facturen", "facturi", "facturam", "pressupost", "pressupostos", "pressupostar",
    "client", "clients", "clienta", "concepte", "conceptes",
    # Parecidas pero son otra cosa.
    "fractura", "fracturas", "concreto", "contento", "concierto", "presupone",
}
# Abreviaturas de móvil, solo como palabra suelta.
_ABREVIATURAS = (
    (re.compile(r"(?<![\w\d])(?:q|k|ke|qe)(?![\w\d])", re.I), "que"),
    (re.compile(r"(?<![\w\d])(?:xq|pq|porq)(?![\w\d])", re.I), "por qué"),
    (re.compile(r"(?<![\w\d])pa(?![\w\d'’])", re.I), "para"),
    (re.compile(r"(?<![\w\d])acer(?![\w\d])", re.I), "hacer"),
    (re.compile(r"(?<![\w\d])(?:tb|tmb)(?![\w\d])", re.I), "también"),
    (re.compile(r"(?<![\w\d])(?:fra|fras|fact|fctra|ftra)(?![\w\d])", re.I), "factura"),
    # «200e» o «200 e» es como se teclea el euro en el móvil.
    (re.compile(r"(\d)\s?e(?![\w\d])", re.I), r"\1 euros"),
    # Faltas sueltas de la ronda real del 30-sep: cada una rompía la orden entera.
    (re.compile(r"(?<![\w\d])oy(?![\w\d])", re.I), "hoy"),
    (re.compile(r"(?<![\w\d])nueb([oa]s?)(?![\w\d])", re.I), r"nuev\1"),
    # «factura ha juan»: la hache de más detrás de la orden.
    (re.compile(r"\b(factura\w*|presupuesto|cita|agenda\w*|ticket)\s+ha\s+(?=\S)", re.I),
     r"\1 a "),
    # «100 euors», «100 pavos», «100 eurs»: el euro mal tecleado o dicho en la calle.
    (re.compile(r"(\d)\s*(?:euors|eurso|euos|erous|eurs|euroz|uros|leuros|pavos|napos|"
                r"lereles)(?![\w\d])", re.I), r"\1 euros"),
    (re.compile(r"(?<![\w\d])presu(?![\w\d])", re.I), "presupuesto"),
    # «emite la 70»: sin decir «factura». Vale igual en la web que en WhatsApp.
    (re.compile(r"^\s*(?:emitir|emite|emitela|emetre|emet)\s+(?:la\s+|el\s+)?(?:n[uú]mero\s+)?"
                r"#?(\d{1,9})\s*[.!]?\s*$", re.I), r"emitir factura \1"),
    # «la factura número 72», «factura nº 72»: el número va pegado a la palabra.
    (re.compile(r"\b(factura|ticket|tiquet|presupuesto|trabajo)\s+(?:n[uú]mero|num\.?|n[ºo°]\.?)"
                r"\s*(?=#?\d)", re.I), r"\1 "),
    (re.compile(r"(?<![\w\d])ajend(a\w*)(?![\w\d])", re.I), r"agend\1"),
    (re.compile(r"(?<![\w\d])en[bv]i(a\w*)(?![\w\d])", re.I), r"envi\1"),
    (re.compile(r"(?<![\w\d])(?:resumn|resumne|rsumen|resuemn)(?![\w\d])", re.I), "resumen"),
    (re.compile(r"(?<![\w\d])clint(es?)(?![\w\d])", re.I), r"client\1"),
    (re.compile(r"(?<![\w\d])(?:provedor|probeedor|provedor|proveedro|porveedor)(?![\w\d])",
                re.I), "proveedor"),
    (re.compile(r"(?<![\w\d])(?:mñn|mñna|mñana|mnn|mañna|manaña)(?![\w\d])", re.I), "mañana"),
    (re.compile(r"(?<![\w\d])(?:biernes|vierns|viernez)(?![\w\d])", re.I), "viernes"),
    (re.compile(r"(?<![\w\d])(?:juebes|jueve)(?![\w\d])", re.I), "jueves"),
    (re.compile(r"(?<![\w\d])(?:sabdo|savado|sabado)(?![\w\d])", re.I), "sábado"),
    (re.compile(r"(?<![\w\d])sita(s?)(?![\w\d])", re.I), r"cita\1"),
    (re.compile(r"(?<![\w\d])deven(?![\w\d])", re.I), "deben"),
    (re.compile(r"(?<![\w\d])deve(?![\w\d])", re.I), "debe"),
    (re.compile(r"(?<![\w\d])gastao(?![\w\d])", re.I), "gastado"),
    (re.compile(r"(?<![\w\d])e\s+(gastado|pagado|comprado|cobrado|facturado|hecho)\b", re.I),
     r"he \1"),
    (re.compile(r"(?<![\w\d])bent(a|as)(?![\w\d])", re.I), r"vent\1"),
    (re.compile(r"(?<![\w\d])(?:grasias|grasis|gracis|grax|grcias)(?![\w\d])", re.I), "gracias"),
    (re.compile(r"^\s*ola(?![\w\d])", re.I), "hola"),
    # «iba» por «IVA» solo donde no puede ser el verbo.
    (re.compile(r"\b(el|del|de|cuanto|cuánto|mi|con|sin|mas|más|\+)\s+iba\b", re.I), r"\1 iva"),
    (re.compile(r"\biba\s+(?=tengo|del|trimestral|incluido|a pagar|repercutido|soportado)",
                re.I), "iva "),
    # «Juan x 200»: la «x» del móvil es «por» entre una palabra y un importe.
    # Entre dos cifras («3 x 20») es una multiplicación y no se toca.
    (re.compile(r"(?<=[^\W\d_])\s+x\s+(?=\d)", re.I), " por "),
)


def _corrige_palabra(match: re.Match) -> str:
    from difflib import get_close_matches

    palabra = match.group(0)
    plegada = _strip_accents(palabra.lower())
    if plegada in _FORMAS_VALIDAS or len(plegada) < 6 or palabra.lower().endswith("é"):
        return palabra  # «facturé», «presupuesté»: pasado dicho a propósito
    plural = plegada.endswith("s") and plegada[:-1] not in _FORMAS_VALIDAS
    raiz = plegada[:-1] if plural else plegada
    parecida = get_close_matches(raiz, _PALABRAS_CLAVE, n=1, cutoff=0.8)
    if not parecida:
        return palabra
    return parecida[0] + ("s" if plural else "")


# Muletillas con las que empieza una nota de voz («Oye, apúntame un gasto…»).
# Las órdenes se reconocen por cómo empiezan, así que la muletilla las tapaba.
_MULETILLA_INICIAL = re.compile(
    r"^(?:(?:oye|oiga|mira|eh+|ehm+|mm+|bueno|pues nada|pues|a ver|venga|perdona|por favor|"
    r"porfa|hey)\b[\s,.…!¡]*)+", re.I)


_EMOJI_DICE = (
    ("👍👌✅🆗💪🤝☑✔", "vale"),
    ("👎❌🚫⛔✖", "no"),
    ("🙏😊☺🥰😘❤💚💙🫶👏🙌😁😃😄🤗", "gracias"),
    ("👋", "hola"),
)
_RESPUESTA_CORTA = {"si": "sí", "no": "no", "ok": "ok", "vale": "vale", "gracias": "gracias",
                    "hola": "hola", "nada": "nada", "venga": "venga", "dale": "dale"}


def normalizar_entrada(text: str) -> str:
    """Deja en una palabra lo que se contesta con un gesto o alargando letras.

    Un 👍 escrito, «nooo», «okkk», «no no no» o «valee» soltaban el parte del día,
    y con una propuesta pendiente ni la confirmaban ni la descartaban. Un mensaje
    de varias líneas pierde las que solo saludan o dan las gracias, que partían la
    orden por la mitad. Lo demás se devuelve tal cual.
    """
    crudo = str(text or "")
    sin_espacios = re.sub(r"[\s\ufe0f\u200d]", "", crudo)
    sin_tono = re.sub(r"[\U0001F3FB-\U0001F3FF]", "", sin_espacios)
    if sin_tono and not re.search(r"[\w¿?¡!.,]", sin_tono):
        for emojis, palabra in _EMOJI_DICE:
            if all(c in emojis for c in sin_tono):
                return palabra
        return crudo
    plano = _norm(crudo).strip(" .,!¡¿?…")
    if plano and len(plano) <= 24 and re.fullmatch(r"[a-z ]+", plano):
        palabras = [re.sub(r"(.)\1+", r"\1", p) for p in plano.split()]
        # «valee» → «vale», pero «llama» no es «lama»: solo si queda una respuesta corta.
        if len(set(palabras)) == 1 and palabras[0] in _RESPUESTA_CORTA \
                and (len(palabras) > 1 or palabras[0] != plano):
            return _RESPUESTA_CORTA[palabras[0]]
    if "\n" in crudo:
        lineas = [linea.strip() for linea in crudo.splitlines() if linea.strip()]
        utiles = [linea for linea in lineas
                  if not solo_saludo(linea)
                  and _norm(linea).strip(" .,!¡") not in {"gracias", "muchas gracias", "porfa",
                                                          "por favor", "un saludo", "saludos"}]
        if utiles and len(utiles) < len(lineas):
            return "\n".join(utiles)
    return crudo


def _numero_de_documento_dicho(text: str) -> str:
    """«Emite la factura uno», «la factura número setenta y dos está cobrada».

    Por voz el número del documento llega en letra y sin «euros», así que el
    conversor de importes no lo toca. Solo se convierte justo detrás de la palabra
    que nombra el documento.
    """
    palabra = "|".join(sorted(_PALABRA_NUMERO, key=len, reverse=True))

    def cifra(m: re.Match) -> str:
        valor = _numero_en_letra(_norm(m.group(2)).split())
        return f"{m.group(1)}{valor}" if valor and 0 < valor < 1_000_000 else m.group(0)

    return re.sub(
        rf"\b((?:factura|ticket|tiquet|presupuesto|trabajo|borrador)\s+(?:n[uú]mero\s+)?)"
        rf"((?:(?:{palabra})\s+)*(?:{palabra}))\b(?!\s*(?:€|euros?))",
        cifra, text, flags=re.I)


def _erratas(text: str) -> str:
    """Corrige faltas en las palabras clave y abreviaturas de móvil."""
    text = _numero_de_documento_dicho(text or "")
    sin_muletilla = _MULETILLA_INICIAL.sub("", text.strip())
    if sin_muletilla.strip(" ,.…!¡?¿"):
        text = sin_muletilla
    # «¿Cuánto facture…?», «ya facture…»: pasado sin tilde, no una errata de factura.
    pasado = re.compile(r"\b(cu[aá]nto|qu[eé]|lo que|ya|no|si|cuando|cu[aá]ndo)\s+(facture)\b", re.I)
    text = pasado.sub(lambda m: f"{m.group(1)} factur\u00e9", text)
    text = re.sub(r"[^\W\d_]{6,}", _corrige_palabra, text)
    for patron, correcto in _ABREVIATURAS:
        text = patron.sub(correcto, text)
    return text


corregir_erratas = _erratas


_ORDENES_DE_ACCION = {
    "crear_factura", "crear_presupuesto", "registrar_gasto", "agendar_trabajo",
    "crear_cliente", "crear_proveedor", "crear_proyecto", "crear_factura_a_medias",
    "actualizar_cliente", "terminar_trabajo",
}
# Se corta donde empieza otra orden: «…, y hazle una factura…», «…; agenda…».
_CORTE_DE_ORDEN = re.compile(
    r"[;\n]|\.\s+|,?\s+y\s+(?:luego\s+|despues\s+|después\s+|ademas\s+|además\s+|"
    r"tambien\s+|también\s+)?(?=(?:haz\w*|crea\w*|agenda\w*|apunta\w*|anota\w*|"
    r"registra\w*|factura\w*|presupuest\w*|gast\w*|he\s+gastado|compr\w*)\b)",
    re.I)


def ordenes_extra(text: str) -> list[str]:
    """Órdenes de un mismo mensaje que no son la que se ha preparado.

    «He gastado 30 en material y hazle una factura a Pedro» solo preparaba la
    factura y el gasto se perdía sin decir nada. Esto no ejecuta nada: devuelve
    los trozos para pedir que se manden por separado.
    """
    trozos = [t.strip(" ,.") for t in _CORTE_DE_ORDEN.split(_erratas(text or ""))]
    trozos = [t for t in trozos if t]
    if len(trozos) < 2:
        return []
    ordenes = []
    for trozo in trozos:
        orden = parse(trozo)
        # «He gastado 30 en material y 15 de parking» no se entiende sola (dos
        # importes), pero es una orden: también cuenta, para no perderla.
        pide_algo = re.search(r"\b(?:gast\w*|compr\w*|factur\w*|presupuest\w*|agend\w*|"
                              r"apunt\w*|anot\w*)\b", _norm(trozo))
        # «…y hazle una factura de 100 por pintar» sola no dice a quién: el parser
        # pide datos, pero es una orden y hay que avisar de que no se ha preparado.
        a_medias = bool(orden and orden[0] in {NEED_INVOICE, NEED_JOB_CLIENT, NEED_DATE})
        if (orden and orden[0] in _ORDENES_DE_ACCION) or ((not orden or a_medias) and pide_algo):
            ordenes.append((trozo, orden))
    if len(ordenes) < 2:
        return []
    hecha = parse(text)
    return [t for t, o in ordenes if o is None or o != hecha]


_IVA_DICHO = (
    (re.compile(r"[\s,]+(?:con\s+(?:el\s+|un\s+)?|al\s+|a\s+)?(0|4|10|21)\s*(?:%|por\s*ciento)\s*"
                r"(?:de\s+)?iva\b", re.I), None),
    (re.compile(r"[\s,]+(?:con\s+(?:el\s+)?)?iva\s*(?:del|al|de|:)?\s*(0|4|10|21)\s*%?(?!\w)", re.I), None),
    (re.compile(r"[\s,]+(?:con\s+(?:el\s+)?)?iva\s+(super\s*reducido|superreducido)\b", re.I), 4.0),
    (re.compile(r"[\s,]+(?:con\s+(?:el\s+)?)?iva\s+reducido\b", re.I), 10.0),
    (re.compile(r"[\s,]+(?:exento|exenta)\s+de\s+iva\b", re.I), 0.0),
)
_IRPF_DICHO = (
    re.compile(r"[\s,]+(?:y\s+|con\s+)?(?:el\s+|la\s+|un\s+|una\s+)?(?:irpf|retenci[oó]n)\s*"
               r"(?:del|de|al|:)?\s*(0|7|15)\s*(?:%|por\s*ciento)?(?!\w)", re.I),
    re.compile(r"[\s,]+(?:y\s+|con\s+)?(?:el\s+|un\s+)?(0|7|15)\s*(?:%|por\s*ciento)\s*(?:de\s+)?"
               r"(?:irpf|retenci[oó]n)\b", re.I),
)


def _extraer_impuestos(text: str) -> tuple[str, dict]:
    """Quita «al 10 % de IVA», «con retención del 15 %», «IVA reducido»… y los devuelve.

    Detrás del importe se colaban en el cliente o el concepto: «factura a Juan por
    grifo 95 euros al 10% de IVA» daba el concepto «al 10%» y el IVA seguía al 21.
    """
    impuestos: dict = {}
    for patron, fijo in _IVA_DICHO:
        m = patron.search(text)
        if m:
            impuestos["iva"] = fijo if fijo is not None else float(m.group(1))
            text = text[:m.start()] + text[m.end():]
            break
    for patron in _IRPF_DICHO:
        m = patron.search(text)
        if m:
            impuestos["irpf"] = float(m.group(1))
            text = text[:m.start()] + text[m.end():]
            break
    # «sin IVA» dice que el importe es la base, que ya es lo que se entiende.
    text = re.sub(r"[\s,]+sin\s+iva\b", "", text, flags=re.I)
    return text, impuestos


# «Factura 2026/0001»: número visible con año. Sin esto «2026» se leía como el
# id interno y se proponía cobrar o emitir otra factura.
_NUMERO_VISIBLE = re.compile(
    r"\b((?:factura|ticket|tiquet|fra)\s*(?:n[ºo.]?\s*|n[uú]mero\s+)?#?\s*)"
    r"([A-Za-z]{0,3}\d{4}\s*[/-]\s*\d{1,6})\b", re.I)
_ID_CENTINELA = 987654321


_PRONOMBRE_CLIENTE = re.compile(
    r"^(?:(?:este|ese|esta|esa|dicho|dicha|aquel|aquella|aquest|aquesta)\s+client[ea]?|"
    r"(?:el|la)\s+mism[oa](?:\s+client[ea])?|[eé]l|ella|ell)$", re.I)
# «Hazle una factura…», «prepárale un presupuesto…»: el «le» es el cliente del que
# se viene hablando. Sin esto pedía otra vez cliente, concepto e importe.
_ORDEN_CON_LE = re.compile(
    r"^(haz|hace|prepara|prepára|crea|créa|manda|mánda|agenda|agénda|apunta|apúnta)le\b\s+"
    r"(una?\s+(?:factura|presupuesto|pressupost|ticket|tiquet|cita|visita|trabajo))\b", re.I)


REPETIR_FACTURA = "__repetir_factura__"
FACTURA_DE_TRABAJO = "__factura_de_trabajo__"
_OTRA_IGUAL = re.compile(
    r"^(?:(?:hazme|haz|crea\w*|prepara\w*|quiero|necesito|ponme)\s+)?"
    r"(?:otra(?:\s+factura)?\s+(?:igual|como\s+la\s+(?:ultima|anterior|de\s+antes))|"
    r"la\s+misma(?:\s+factura)?|(?:repite|repetir|duplica|duplicar|copia|copiar)\s+"
    r"(?:la\s+)?(?:ultima\s+)?factura(?:\s+(?:anterior|de\s+antes))?)"
    r"(?P<resto>\b.*)$")


def _repetir_factura(text: str) -> tuple[str, dict] | None:
    """«Hazme otra igual», «otra igual para Juan», «la misma pero de 400».

    Las cuotas y los trabajos repetidos se facturan así. Lo que se cambia —el
    cliente o el importe— se dice detrás; el resto sale de la última factura.
    """
    text = _cifras_dictadas(text)  # «pero de quinientos euros»
    m = _OTRA_IGUAL.match(_norm(text).strip(" .!"))
    if not m:
        return None
    resto = m.group("resto").strip(" ,")
    crudo = text.strip().rstrip(".! ")
    crudo_resto = crudo[len(crudo) - len(resto):] if resto and len(crudo) >= len(resto) else resto
    args: dict = {}
    importe = re.search(rf"(?:de|por|pero\s+de|pero\s+por)\s+({_AMOUNT_RE})\s*(?:€|euros?|eur)?",
                        crudo_resto, re.I)
    if importe:
        args["base"] = _amount_value(importe.group(1))
        crudo_resto = (crudo_resto[:importe.start()] + " " + crudo_resto[importe.end():]).strip()
    crudo_resto = re.sub(r"(?:\s+|^)(?:y|e|pero|,)\s*$", "", crudo_resto, flags=re.I).strip()
    quien = re.search(r"\b(?:a|para|per\s+a)\s+(.+?)\s*(?:\bpero\b.*)?$", crudo_resto, re.I)
    if quien:
        nombre = _limpiar_cliente(quien.group(1))
        if nombre:
            args["cliente"] = nombre
    elif crudo_resto and not re.fullmatch(r"(?:pero|y|,|\s|que la ultima|a la ultima)*", _norm(crudo_resto)):
        return None  # hay algo más que no se entiende: mejor no adivinar
    return (REPETIR_FACTURA, args)


def parse(text: str) -> tuple[str, dict] | None:
    repetida = _repetir_factura(text or "")
    if repetida:
        return repetida
    con_le = _ORDEN_CON_LE.match((text or "").strip())
    if con_le:
        # «Hazle un presupuesto a Juan…» ya dice el cliente: el «le» es él. Antes
        # se añadía «a este cliente» igualmente y salía «este cliente a Juan».
        nombra = re.match(r"\s+(?:a|para|per\s+a)\s+\S", text.strip()[con_le.end():], re.I)
        sufijo = "" if nombra else " a este cliente"
        text = _ORDEN_CON_LE.sub(
            lambda m: f"{_strip_accents(m.group(1))}me {m.group(2)}{sufijo}",
            text.strip(), count=1)
    resultado = _parse_con_numero(text)
    if resultado and _PRONOMBRE_CLIENTE.match(str(resultado[1].get("cliente") or "").strip()):
        return (resultado[0], {**resultado[1], "cliente": CLIENTE_DE_LA_CONVERSACION})
    return resultado


def _parse_con_numero(text: str) -> tuple[str, dict] | None:
    visible = _NUMERO_VISIBLE.search(text or "")
    if visible:
        numero = re.sub(r"\s+", "", visible.group(2)).replace("-", "/").upper()
        resultado = _parse_sin_numero(_NUMERO_VISIBLE.sub(
            lambda m: f"{m.group(1)}{_ID_CENTINELA}", text, count=1))
        if resultado and resultado[1].get("factura_id") == _ID_CENTINELA:
            args = {k: v for k, v in resultado[1].items() if k != "factura_id"}
            return (resultado[0], {**args, "factura_numero": numero})
        if resultado and str(_ID_CENTINELA) in json.dumps(resultado[1], ensure_ascii=False):
            return _parse_sin_numero(text)
        return resultado
    return _parse_sin_numero(text)


def _parse_sin_numero(text: str) -> tuple[str, dict] | None:
    limpio, impuestos = _extraer_impuestos(text)
    if impuestos or limpio != text:
        resultado = _parse(limpio)
        if resultado and resultado[0] in {"crear_factura", "crear_presupuesto",
                                          PARTIAL_INVOICE}:
            return (resultado[0], {**resultado[1], **impuestos})
        if resultado and resultado[0] not in {NEED_REVIEW}:
            return resultado
    return _parse(text)


def _parse(text: str) -> tuple[str, dict] | None:
    # Lo primero: pasar a cifras los importes dictados en letra. Todo lo que
    # viene detrás busca números, y una nota de voz los trae escritos.
    # «El 21 por ciento» es como se dice un porcentaje hablando. Sin traducirlo,
    # «ciento» acababa siendo el concepto de la factura.
    text = re.sub(r"(\d+(?:[.,]\d+)?)\s*por\s*ciento\b", r"\1%", text, flags=re.I)
    # Whisper cierra cada frase con un punto, y muchas reglas miran el final de la
    # frase. «S.L.» conserva el suyo.
    if text.rstrip().endswith(".") and not text.rstrip().endswith("..."):
        text = _recortar(text.rstrip()) if text.strip() else text
    text = _cifras_dictadas(text)
    text = _erratas(text)
    norm = _norm(text)

    # Antes que la negativa general a «cancelar» o «cambiar»: una cita no se borra
    # (queda cancelada) y todo pasa por la tarjeta de SÍ.
    cita = _cambio_de_cita(text, norm)
    if cita:
        return cita
    refusal = safety_refusal(text)
    if refusal:
        return (NEED_REVIEW, {"reply": refusal})
    for field, allowed in (("iva", {0, 4, 10, 21}), ("irpf", {0, 7, 15})):
        rate = re.search(rf"\b{field}\s*(?:(?:del|al)\s*)?(\d+(?:[.,]\d+)?)(?![\w.,])", norm)
        if rate and float(rate.group(1).replace(",", ".")) not in allowed:
            return (NEED_REVIEW, {"reply": "El tipo fiscal indicado no está admitido. Revisa IVA e IRPF en Facturas; no he sustituido el porcentaje por otro."})
    decision = _decision_de_presupuesto(text, norm)
    if decision:
        return decision

    consulta = _consulta_de_agenda(text, norm)
    if consulta:
        return consulta
    gastos = _consulta_de_gastos(norm)
    if gastos:
        return gastos
    # «Me han pagado 300», «ya me pagó Reformas Martínez»: un cobro sin decir de
    # qué factura. Se enseña lo pendiente para que diga cuál; antes iba a la IA.
    cobro = re.match(r"^(?:ya\s+)?(?:me\s+(?:han|ha)\s+pagado|me\s+pag(?:o|aron)|he\s+cobrado|"
                     r"cobre|ya\s+he\s+cobrado)\b(.*)$", norm)
    if cobro and not re.search(r"\bfactura\s*#?\s*\d", norm):
        resto = re.sub(rf"\b(?:{_AMOUNT_RE})\s*(?:€|euros?|eur)?", " ", cobro.group(1))
        resto = re.sub(r"\b(?:ya|hoy|ayer|la|el|factura|de|del|a|por|todo|toda)\b", " ", resto)
        nombre = " ".join(resto.split())
        crudo = text.strip().rstrip("?¿!. ")
        cliente = crudo[len(crudo) - len(nombre):] if nombre and len(crudo) >= len(nombre) else ""
        return ("ver_cobros_pendientes", {"tras_cobro": True,
                                          **({"cliente": _limpiar_cliente(cliente)} if cliente else {})})
    # «¿Qué facturas tengo pendientes?» se quedaba sin respuesta local.
    if (re.search(r"^(?:y\s+)?(?:que|cuales|cuantas|ver|mis|dime)\b.*\bfacturas?\b.*\bpendientes?\b", norm)
            and not re.search(r"\b(?:emitir|borrador\w*|sin emitir|de enviar|facturar)\b", norm)):
        return ("ver_cobros_pendientes", {})
    # Se compara contra `norm`, sin acentos: contra el texto crudo, «qué trabajos
    # tengo mañana» no encajaba con «que.*trabajos» por la tilde y la orden se
    # perdía entera.
    if re.search(r"(?:(?:que|quins|quines|quin)\b.*"
                 r"\b(?:trabajos|citas|tengo|treballs|feines|tinc)\b.*"
                 r"|agenda (?:de|para|per) )(?:hoy|avui|manana|dema)", norm) \
            and not _pide_agendar(text, norm):
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
    # «Hola, ¿qué puedes hacer?» es la primera frase de casi todo el mundo y no
    # coincidía por el saludo y los signos. Solo cuenta si no queda nada más: un
    # «hola, factura a Juan…» sigue siendo una factura.
    if pide_capacidades(text) or solo_saludo(text):
        return (HELP, {})

    # --- Centro de control: límites reales de Bynoesis
    # «(by)?noesis»: la marca cambió y quien escribe puede usar cualquiera de las dos.
    if re.search(r"(que puedes hacer solo|que puedes hacer sin|permisos de (?:by)?noesis|"
                 r"control de (?:by)?noesis|que haces sin preguntar|autonomia)", norm):
        return ("ver_control_noesis", {})

    # Altas explícitas: no hace falta crear una factura de rebote para guardar
    # una relación comercial. El acceso de una persona, en cambio, exige correo,
    # rol e invitación segura y no se concede desde una frase incompleta.
    dato_cliente = _dato_de_cliente(text)
    if dato_cliente:
        return dato_cliente
    pregunta_cliente = _pregunta_por_cliente(text, norm)
    if pregunta_cliente:
        return pregunta_cliente
    llamar = re.match(r"^(?:llama|llamar|llamame|telefonea)\s+(?:a|al)\s+(?:client[ea]\s+)?(.+?)\s*$",
                      text.strip().rstrip(".!"), re.I)
    if llamar and _limpiar_cliente(llamar.group(1)):
        # No hago llamadas; lo útil es dar el teléfono para que llame el autónomo.
        return ("ver_cliente", {"cliente": _limpiar_cliente(llamar.group(1)),
                                "dato": "telefono", "llamar": True})
    _PAPEL = r"(client[ea]s?|client|proveedor[a]?|prove[ïi]dor[a]?)"
    _VERBO_ALTA = (r"(?:crea\w*|crear|cre[ao]|anade\w*|añade\w*|a[ñn]adir\w*|agrega\w*|agregar|"
                   r"apunta\w*|registra\w*|guarda\w*|mete\w*|hazme|haz|hacer|afegeix\w*|fes|"
                   r"(?:da|dar|dame|donar?|dona)\s+(?:de\s+)?alta|alta|"
                   r"nuevo|nueva|nou|nova)")
    party = re.search(
        # El artículo determinado entra igual que el indeterminado: «crea el
        # cliente Talleres Pino» se decía tan a menudo como «un cliente», y
        # antes caía en la regla de listar clientes sin dar de alta a nadie.
        # «Agrega», «apunta», «registra» o «dar de alta» también son altas.
        rf"\b{_VERBO_ALTA}\s+"
        # «alta de cliente X» se dice tanto como «alta cliente X».
        r"(?:de\s+|a\s+)?(?:un|una|el|la|los|las|l'|al|este|esta|ese|esa)?\s*"
        r"(?:(?:nuev[oa]|nou|nova|otr[oa]|altre|altra)\s+)?"
        # «client» y «proveïdor» en catalán se dicen tanto como en castellano.
        rf"{_PAPEL}(?:\s+(?:nuev[oa]|nou|nova))?\s*[:,]?\s+(.+?)\s*$",
        text, re.I,
    )
    if not party:
        # Orden inverso: primero el nombre y después el papel («añade a Laura
        # como cliente», «guarda a Laura en clientes», «Laura es un cliente nuevo»).
        inversa = (
            re.search(rf"\b{_VERBO_ALTA}\s+(?:a\s+)?(.+?)\s+(?:como|com|en|a|de)\s+"
                      rf"(?:(?:un|una|el|la|mis|los|les|els)\s+)?(?:nuev[oa]\s+)?{_PAPEL}\b",
                      text, re.I)
            or re.search(rf"^(?:tengo|tinc)\s+(?:un|una)\s+(?:nuev[oa]\s+|nou\s+|nova\s+)?{_PAPEL}"
                         r"\s+(?:nuev[oa]|nou|nova)?\s*[,:]?\s*(?:que\s+se\s+llama|se\s+llama|"
                         r"llamad[oa]|que\s+es\s+diu|es\s+diu)\s+(.+?)\s*$", text.strip(), re.I)
            # «Cliente nuevo: Pepe García, 666 777 888», sin verbo.
            or re.search(rf"^{_PAPEL}\s+(?:nuev[oa]|nou|nova)\s*[:,]?\s+(.+?)\s*$",
                         text.strip(), re.I)
            or re.search(rf"^(.+?)\s+(?:es|és)\s+(?:un|una)\s+(?:nuev[oa]\s+|nou\s+|nova\s+)?"
                         rf"{_PAPEL}(?:\s+(?:nuev[oa]|nou|nova))?\s*[.!]?\s*$", text.strip(), re.I)
        )
        if inversa:
            grupos = inversa.groups()
            papel, nombre = ((grupos[1], grupos[0]) if _norm(grupos[1]).startswith(("client", "prove"))
                             else (grupos[0], grupos[1]))
            # «Hazme un presupuesto a cliente Juan…» no da de alta a «un presupuesto».
            if not re.search(r"\b(?:factura\w*|presupuest\w*|ticket|tiquet|gasto\w*|cita\w*|"
                             r"trabajo\w*|albaran\w*|recordatorio\w*)\b", _norm(nombre)):
                return _party_intent(papel, nombre)
    if party:
        return _party_intent(party.group(1), party.group(2))
    # «Crea el cliente» o «nuevo proveedor» a secas. Antes no casaba con nada de
    # aquí y acababa listando clientes o dando el parte del día: la orden se
    # perdía entera por faltar una palabra.
    sin_nombre = re.match(
        r"(?:(?:quiero|necesito|tengo que|hay que|puedes|me puedes)\s+)?"
        r"(?:crea|crear|creame|anade|anademe|anadir|agrega\w*|hazme|hacer|nuevo|nueva|alta|"
        r"dar de alta|da de alta|dame de alta|registra\w*|apunta\w*)\s+(?:de\s+|a\s+)?"
        r"(?:un|una|el|la)?\s*(?:nuev[oa]\s+)?(cliente|proveedor)(?:\s+nuev[oa])?\s*$", norm
    ) or re.match(r"(cliente|proveedor)\s+nuev[oa]\s*$", norm)
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
            # «… con presupuesto de 20000» no puede dejar «con» en el nombre.
            rf"(?:proyecto|projecte|obra)\s+(.+?)\s+(?:(?:(?:con|amb)\s+(?:un\s+)?)?"
            rf"(?:presupuesto|pressupost)\s+(?:de\s+)?|(?:de|por|per)\s+)?"
            rf"({_AMOUNT_RE})\s*(?:€|euros?|eur)?(?:\s|$)",
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
        args = _documento_por_trozos(text, r"(?:presupuesto|pressupost)")
        if args:
            _add_tax_rates(norm, args)
            return ("crear_presupuesto", args)
        args = _parse_doc_command(
            text, norm, r"(?:presupuest(?:o|ar|a|ame)?|pressupost(?:ar|a|am)?)"
        )
        if not args and re.match(r"(?:(?:hazme|haz|crea\w*|prepara\w*|pasame)\s+)?(?:un\s+)?"
                                 r"(?:presupuesto|pressupost)\s+\S", norm) \
                and not re.search(r"\b(?:acept\w*|rechaz\w*|que|cual\w*|cuant\w*|ver)\b", norm):
            # «presupuesto juan 500 baño»: sin «a» ni «por», como «factura juan 500 baño».
            args = _factura_sin_preposicion(
                re.sub(r"presupuesto|pressupost", "factura", text, count=1, flags=re.I),
                re.sub(r"presupuesto|pressupost", "factura", norm, count=1))
        if args:
            _add_tax_rates(norm, args)
            return ("crear_presupuesto", args)

    # «Ya he terminado el trabajo de Marta», «he acabado lo de Marta López».
    hecho = re.match(
        r"^(?:ya\s+)?(?:he|hemos)\s+(?:terminado|acabado|finalizado|hecho|cerrado)\s+"
        r"(?:el\s+trabajo|la\s+obra|la\s+visita|la\s+cita|lo|el\s+encargo|la\s+faena)\s+"
        r"(?:de|del|en casa de|con)\s+(?:la\s+|el\s+)?(.+?)\s*$", text.strip().rstrip(".!"), re.I)
    if not hecho:
        hecho = re.match(r"^(?:marca|pon|da)\s+(?:como\s+)?(?:hecho|terminado|por\s+hecho|"
                         r"por\s+terminado)\s+(?:el\s+trabajo|lo|la\s+cita)\s+(?:de|del|con)\s+"
                         r"(.+?)\s*$", text.strip().rstrip(".!"), re.I)
    if hecho and _limpiar_cliente(hecho.group(1)):
        return ("terminar_trabajo", {"cliente": _limpiar_cliente(hecho.group(1))})
    # «Factura el trabajo de Marta López (por 120 euros)».
    del_trabajo = re.match(
        r"^(?:factura\w*|hazme\s+la\s+factura\s+de|prepara\w*\s+la\s+factura\s+de)\s+"
        r"(?:el\s+trabajo|lo|la\s+obra|la\s+visita|la\s+cita)\s+(?:de|del|con)\s+(.+?)\s*$",
        text.strip().rstrip(".!"), re.I)
    if del_trabajo:
        resto = del_trabajo.group(1)
        importe = re.search(rf"\s+(?:por|de|son)\s+({_AMOUNT_RE})\s*(?:€|euros?|eur)?\s*$", resto, re.I)
        datos: dict = {}
        if importe:
            datos["base"] = _amount_value(importe.group(1))
            resto = resto[:importe.start()]
        if _limpiar_cliente(resto):
            return (FACTURA_DE_TRABAJO, {"cliente": _limpiar_cliente(resto), **datos})
    # «¿Qué presupuestos tengo?», «mis presupuestos», «presupuestos de Juan».
    presus = re.match(r"^(?:y\s+)?(?:(?:que|cuales|cuantos|ver|mis|lista(?:me)?|ensename|muestrame|"
                      r"dime)\s+(?:los\s+|mis\s+)?)?(?:presupuestos|pressupostos)\b"
                      r"(?:\s+(?:tengo|hay|llevo|tinc))?(?:\s+(?:pendientes?|enviados?|abiertos?))?"
                      r"(?:\s+(?:de|del|a|para)\s+(?:el\s+cliente\s+)?(.+?))?\s*\??$", norm)
    if presus:
        if presus.group(1):
            crudo = text.strip().rstrip("?¿!. ")
            return ("ver_presupuestos", {"cliente": _limpiar_cliente(
                crudo[len(crudo) - len(presus.group(1)):])})
        return ("ver_presupuestos", {})
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
        args = (_documento_por_trozos(text, r"factura")
                or _parse_doc_command(text, norm, r"fact[uú]ra(?:r|me)?"))
        if args:
            args["tipo_factura"] = "F1"
            _add_tax_rates(norm, args)
            if "iva incluido" in norm or "iva inclos" in norm:
                args["importe_incluye_iva"] = True
            return ("crear_factura", args)
        # Si el parser de siempre no ha sacado la factura y hay etiquetas
        # («concepto: …», «cliente: …»), mandan las etiquetas: la
        # lectura por posición convertía «factura de 350€ + iva concepto: X el
        # cliente es: Y» en una factura para el cliente «+ iva».
        if (campos_etiquetados(text)
                and (_VERBO_CREAR_FACTURA.search(norm) or _LLEVA_IMPORTE.search(norm))
                and not _CONSULTA_FACTURA.search(norm)
                and not _FACTURA_RECURRENTE.search(norm)):
            args = parse_partial_invoice(text)
            _add_tax_rates(norm, args)
            if {"cliente", "concepto", "base"} <= args.keys():
                if "iva incluido" in norm or "iva inclos" in norm:
                    args["importe_incluye_iva"] = True
                return ("crear_factura", {**args, "tipo_factura": "F1"})
            return (PARTIAL_INVOICE, args)
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
                     # «He pagado 60 de seguro», «pagué la gasolina, 55 euros».
                     # «Me han pagado» no entra: empieza por «me han».
                     r"he pagado\b|pague\b|compra de\b|"
                     # Catalán: «he gastat 35 euros» no registraba nada.
                     r"despesa\b|he gastat\b|m'he gastat\b|he comprat\b|rebut\b)")
    # «Hoy he gastado 45…», «ayer compré…»: el cuándo delante tapaba la orden.
    _CUANDO = r"(?:(?:hoy|ayer|antes|esta manana|esta tarde|esta mañana)\s*,?\s+)?"
    es_gasto = bool(
        re.match(rf"{_CUANDO}(?:{_VERBO_GASTO}\s+(?:un[oa]?\s+)?)?{_NOMBRE_GASTO}", norm)
        # «apunta 20 euros de material»: con el verbo y el importe basta, no hace
        # falta decir «gasto». No se toma por gasto si la frase habla de facturar
        # o de citas, que son otras cosas con importe.
        or (re.match(rf"{_VERBO_GASTO}\s+(?:un[oa]?\s+)?{_AMOUNT_RE}", norm)
            and not re.search(r"\b(?:factura\w*|presupuesto\w*|cliente\w*|"
                              r"cobr\w+|trabajo\w*|cita\w*|agenda\w*)\b", norm))
    )
    if es_gasto:
        # Sin el «hoy/ayer» delante, para que el concepto no sea «compré tornillos».
        text = re.sub(r"^\s*(?:hoy|ayer|antes|esta\s+ma[ñn]ana|esta\s+tarde)\s*,?\s+", "",
                      text, flags=re.I)
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
            if not concepto:
                # «gasto 20 gasolina», «gasté 20 euros gasolina»: el concepto va
                # detrás del importe, sin «en» ni «de».
                cola = re.search(rf"{_AMOUNT_RE}\s*(?:€|euros?|eur\b)?\s+([^\d€]{{2,60}})$",
                                 text.strip().rstrip("."), re.I)
                concepto = _limpiar_concepto(cola.group(1)) if cola else ""
            concepto = re.sub(r"\s+(?:hoy|ayer|esta\s+ma[ñn]ana|esta\s+tarde)$", "",
                              concepto, flags=re.I).strip()
            concepto = concepto or "Gasto"
            args = {"concepto": concepto, "importe": amount}
            if re.search(r"\biva\b", norm):
                rate = re.search(r"\biva\s*(?:incluido|inclos)?\s*(?:del|al)?\s*(0|4|10|21)(?![\d.,])\s*%?", norm)
                if (not rate or not re.search(r"\b(?:incluido|inclos)\b", norm)
                        or re.search(r"\b(?:no\s+incluido|sin\s+iva|mas\s+iva)\b", norm)):
                    return (NEED_REVIEW, {"reply": "Para conservar el IVA del gasto, dime el importe final con IVA incluido y su porcentaje. No he registrado el gasto."})
                args["iva"] = int(rate.group(1))
            return ("registrar_gasto", args)

    suelto = _gasto_sin_verbo(text, norm)
    if suelto:
        return suelto
    visita = _visita_dicha(text)
    if visita:
        return visita
    # --- Agenda: «agenda a Marta el jueves por la mañana en Badalona» y también
    # «añade un trabajo para mañana a las 12», que antes no se entendía.
    if _is_agenda_order(norm):
        fecha = parse_date(text)
        # «El 15 de octubre» no es ni el cliente ni el trabajo: el «de» se leía
        # como «trabajo de octubre».
        sin_fecha = _quitar_fecha_concreta(text)
        cliente = _agenda_client(sin_fecha)
        zona = None
        zm = re.search(r"\ben\s+([A-Za-záéíóúñ ]+)$", sin_fecha.strip())
        if zm:
            zona = zm.group(1).strip()
        descripcion = _agenda_description(sin_fecha, cliente)
        if not cliente and _REFERENCIA_CLIENTE.search(norm):
            cliente = CLIENTE_DE_LA_CONVERSACION
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
    # «¿Cuánto me debe Reformas Martínez?»: los cobros de ese cliente.
    debe = re.match(r"^(?:y\s+)?(?:cuanto|que|lo que)\s+(?:me\s+)?(?:debe|deben|adeuda)\s+"
                    r"(?:todavia\s+|aun\s+)?(?:el\s+cliente\s+|la\s+cliente\s+)?(.+?)\s*\??$", norm)
    if debe and not re.match(r"^(?:de|en|el mes|este|total|todo|todos)\b", debe.group(1)):
        nombre = text.strip().rstrip("?¿!. ")
        nombre = nombre[len(nombre) - len(debe.group(1)):] if len(nombre) >= len(debe.group(1)) else debe.group(1)
        return ("ver_cobros_pendientes", {"cliente": _limpiar_cliente(nombre)})
    if re.search(r"(cobr|por cobrar|quien me debe|pendiente de cobro|me deben?\b|"
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
    if re.search(r"(gestoria|gestor).*(pide|solicitud|pendient)"
                 r"|(pide|solicitud|pendient).*\b(gestoria|gestor)\b", norm):
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
        hoy = date.today()
        if "trimestre" not in args:
            if re.search(r"\b(?:trimestre pasado|trimestre anterior|ultimo trimestre)\b", norm):
                actual = (hoy.month - 1) // 3 + 1
                args["trimestre"] = actual - 1 or 4
                if actual == 1:
                    args.setdefault("anio", hoy.year - 1)
            elif re.search(r"\b(?:este|aquest)\s+trimestre\b|\btrimestre actual\b|\bllevo\b", norm):
                # Dicho expresamente: el trimestre en curso, no el que toca presentar.
                args["trimestre"] = (hoy.month - 1) // 3 + 1
        return ("ver_impuestos", args)

    # --- Resumen / ingresos
    if re.search(r"(cuanto.*factur(?:ad|e\b|amos|aste|o\b)|ingresos|resumen|como va|como voy|que tal va|"
                 r"balance|beneficio|facturacion|este mes|mis numeros|cuanto llevo|"
                 # Catalán: «quant he facturat», «com va», «aquest mes».
                 r"quant.*facturat|ingressos|com va|com vaig|com anem|benefici|"
                 r"facturacio|aquest mes|els meus numeros|quant porto)", norm):
        return ("resumen_negocio", _periodo_del_resumen(norm))

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
        # «Factura» es femenino y «ticket» masculino: el texto concuerda con cada uno.
        if f.get("invoice_type") == "F2":
            label, preparado, pron, correcto = "Ticket de venta", "preparado", "lo", "correcto"
        else:
            label, preparado, pron, correcto = "Factura", "preparada", "la", "correcta"
        aviso = result.get("aviso_fiscal")
        # El concepto se enseña: si no se dijo, es «Servicio» y así se ve.
        concepto = f" ({f['concept']})" if f.get("concept") else ""
        return (f"🧾 {label} #{f['id']} {preparado} para {f['client_name']}{concepto}: "
                f"**{_eur(f['total'])}** ({desglose}). {pron.capitalize()} dejo en "
                f"borrador para que {pron} revises. Cuando esté {correcto}, escribe "
                f"«emitir factura {f['id']}»; para entregar{pron} también, «emitir "
                f"y enviar factura {f['id']}»."
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
        f = result["factura"]
        return (f"✅ Cobro registrado: la factura {f.get('number') or '#' + str(f['id'])}"
                f"{' de ' + f['client_name'] if f.get('client_name') else ''} "
                f"({_eur(f.get('total') or 0)}) ya consta como cobrada.")
    if tool == "crear_cliente":
        client = result["cliente"]
        suffix = " Ya existía; he reutilizado su ficha." if result.get("existing") else ""
        enlazadas = result.get("facturas_enlazadas") or []
        if enlazadas:
            suffix += (" Lo he enlazado al borrador "
                       + ", ".join(f"#{n}" for n in enlazadas)
                       + " que lo esperaba.")
        completados = [{"phone": "teléfono", "email": "correo", "nif": "NIF",
                        "address": "dirección"}[k] for k in result.get("completados") or []]
        if result.get("existing") and completados:
            suffix = (" Ya existía; le he añadido " + " y ".join(completados) + ".")
        datos = [f"{etiqueta}: {client[k]}" for k, etiqueta in (
            ("phone", "Teléfono"), ("email", "Correo"), ("nif", "NIF"),
            ("address", "Dirección")) if client.get(k)]
        texto = f"Cliente guardado: **{client['name']}**.{suffix}"
        if datos:
            texto += "\n" + "\n".join(datos)
        for aviso in result.get("avisos") or []:
            texto += f"\n⚠️ {aviso}"
        if not (client.get("nif") and client.get("address")):
            texto += ("\n\nPara emitirle facturas completas faltará "
                      + " y ".join(x for x, ok in (("el NIF", client.get("nif")),
                                                  ("la dirección", client.get("address")))
                                   if not ok)
                      + ": dímelo («el NIF de " + client["name"] + " es …») o añádelo en Clientes.")
        return texto
    if tool == "ver_presupuestos":
        quien = f" de {result['cliente']}" if result.get("cliente") else ""
        if result.get("sin_ficha"):
            return f"No tengo ficha de cliente «{result['cliente']}»."
        if not result["presupuestos"]:
            return (f"No tienes presupuestos{quien}. Dime, por ejemplo, «presupuesto a Ana por "
                    "reforma de baño 1200 euros».")
        estados = {"borrador": "sin enviar", "enviado": "enviado, esperando respuesta",
                   "aceptado": "aceptado", "rechazado": "rechazado", "caducado": "caducado"}
        lines = [f"📝 {_cuenta(result['n'], 'presupuesto', 'presupuestos')}{quien}:"]
        for p in result["presupuestos"]:
            # El #id va siempre delante: es el número con el que se acepta o
            # rechaza («acepta el presupuesto 12»), tenga o no número de serie.
            numero = f" · {p['number']}" if p.get("number") else ""
            lines.append(f"• #{p['id']}{numero} · {p.get('client_name') or ''} · "
                         f"{p.get('concept') or ''} · {_eur(p.get('total') or 0)} · "
                         f"{estados.get(p.get('status'), p.get('status') or '')}")
        if result["n"] > len(result["presupuestos"]):
            lines.append("…y más en Presupuestos.")
        pendiente = next((p for p in result["presupuestos"]
                          if p.get("status") in {"borrador", "enviado"}), None)
        if pendiente:
            lines.append(f"Cuando te contesten, dime «acepta el presupuesto {pendiente['id']}» "
                         f"(queda su factura en borrador) o «rechaza el presupuesto "
                         f"{pendiente['id']}».")
        return "\n".join(lines)
    if tool == "cancelar_cita":
        t = result["trabajo"]
        return (f"Cita cancelada: {t.get('client_name') or 'sin cliente'} — "
                f"{t.get('description') or 'Trabajo'} ({dia_humano(t.get('scheduled_for')) or 'sin día'}). "
                "Queda en la agenda como cancelada. Si quieres avisarle, dime "
                f"«escribe a {t.get('client_name') or 'el cliente'} que anulamos la visita».")
    if tool == "mover_cita":
        t = result["trabajo"]
        return (f"📅 Cita movida: {t.get('client_name') or 'sin cliente'} — "
                f"{t.get('description') or 'Trabajo'}, ahora {dia_humano(t.get('scheduled_for'))} "
                f"(antes {dia_humano(result.get('antes')) or 'sin día'}). Al cliente no le he "
                "avisado.")
    if tool == "aceptar_presupuesto":
        p, f = result["presupuesto"], result.get("factura") or {}
        return (f"✅ Presupuesto {p.get('number') or '#' + str(p['id'])} de "
                f"{p.get('client_name') or 'tu cliente'} aceptado. Su factura #{f.get('id')} "
                f"({_eur(f.get('total') or 0)}) queda en borrador para que la revises. "
                f"Cuando esté bien, escribe «emitir factura {f.get('id')}».")
    if tool == "rechazar_presupuesto":
        p = result["presupuesto"]
        return (f"Presupuesto {p.get('number') or '#' + str(p['id'])} de "
                f"{p.get('client_name') or 'tu cliente'} marcado como rechazado. "
                "No se ha creado ninguna factura.")
    if tool == "terminar_trabajo":
        if result.get("error"):
            return result["error"] + " No he cambiado nada."
        t, c = result["trabajo"], result["cliente"]
        precio = t.get("price_estimate")
        siguiente = (f"«factura el trabajo de {c['name']}»" if precio else
                     f"«factura a {c['name']} por {t.get('description') or 'el trabajo'} … euros»")
        return (f"✅ Trabajo de **{c['name']}** marcado como hecho: {t.get('description') or 'Trabajo'}.\n"
                f"Para que no se quede sin facturar, dime {siguiente}.")
    if tool == "ver_cliente":
        if not result.get("ok"):
            return (result.get("error") or "No encuentro ese cliente.") + \
                " Dime el nombre como lo tienes en Clientes."
        c = result["cliente"]
        etiquetas = {"telefono": ("phone", "teléfono"), "email": ("email", "correo"),
                     "nif": ("nif", "NIF"), "direccion": ("address", "dirección")}
        dato = result.get("dato")
        if dato in etiquetas:
            columna, nombre = etiquetas[dato]
            if c.get(columna):
                if result.get("llamar"):
                    return (f"Yo no hago llamadas, pero aquí tienes el teléfono de "
                            f"**{c['name']}**: {c[columna]}.")
                return f"El {nombre} de **{c['name']}** es {c[columna]}."
            ejemplo = {"phone": "612 34 56 78", "email": "correo@ejemplo.es",
                       "nif": "12345678Z", "address": "Calle Mayor 3, Valencia"}[columna]
            return (f"No tengo el {nombre} de **{c['name']}**. Dímelo así y lo guardo: "
                    f"«el {nombre} de {c['name']} es {ejemplo}».")
        lines = [f"📇 **{c['name']}** · ficha #{c['id']}"]
        for columna, nombre in (("phone", "Teléfono"), ("email", "Correo"), ("nif", "NIF"),
                                ("address", "Dirección")):
            aviso = ""
            if columna == "nif" and c.get("nif"):
                from .fiscal_validation import valid_spanish_tax_id
                if not valid_spanish_tax_id(c["nif"]):
                    aviso = " ⚠️ no parece un NIF válido: revísalo antes de emitir"
            lines.append(f"{nombre}: {c.get(columna) or '—'}{aviso}")
        if result["n_facturas"]:
            borradores = result.get("n_borradores") or 0
            emitidas = result["n_facturas"] - borradores
            partes = []
            if emitidas:
                partes.append(_cuenta(emitidas, "emitida", "emitidas"))
            if borradores:
                partes.append(_cuenta(borradores, "borrador sin emitir", "borradores sin emitir"))
            lines.append(f"\n{_cuenta(result['n_facturas'], 'factura', 'facturas')} ("
                         + " y ".join(partes) + ")"
                         + (f", pendiente de cobro **{_eur(result['pendiente'])}**"
                            if result["pendiente"] else
                            ", nada pendiente de cobro" if emitidas else "") + ":")
            for f in result["facturas"]:
                estado = {"borrador": "borrador", "enviada": "sin cobrar", "parcial": "cobro parcial",
                          "cobrada": "cobrada"}.get(f.get("status"), f.get("status") or "")
                lines.append(f"• {f.get('number') or '#' + str(f['id'])} · {f.get('concept') or ''}"
                             f" · {_eur(f.get('total') or 0)} · {estado}")
        else:
            lines.append("\nTodavía no le has hecho ninguna factura.")
        return "\n".join(lines)
    if tool == "actualizar_cliente":
        client = result["cliente"]
        etiquetas = {"phone": "teléfono", "email": "correo", "nif": "NIF",
                     "address": "dirección"}
        cambios = result.get("cambios") or {}
        texto = (f"Ficha de **{client['name']}** actualizada: "
                 + ", ".join(f"{etiquetas[k]} {v[1]}" for k, v in cambios.items()) + "."
                 if cambios else f"La ficha de **{client['name']}** ya tenía esos datos.")
        for aviso in result.get("avisos") or []:
            texto += f"\n⚠️ {aviso}"
        return texto
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
        numero = f" #{q['id']}" if q.get("id") else ""
        return (f"📝 Presupuesto{numero} preparado para {q['client_name']}: **{_eur(q['total'])}** "
                f"({desglose}). Lo tienes en Presupuestos: envíalo y, si lo aceptan, "
                "se convierte en factura con un clic.")
    if tool == "registrar_gasto":
        g = result["gasto"]
        return (f"📉 Gasto registrado: {g['concept']} — {_eur(g['amount'])}.\n"
                "Bien hecho: gasto apuntado al momento, beneficio más real.")
    if tool == "agendar_trabajo":
        t = result["trabajo"]
        cuando = dia_humano(t["scheduled_for"]) if t.get("scheduled_for") else "sin día"
        return (f"📅 Agendado: {result['cliente']['name']}, {cuando}.\n"
                "Lo importante ahora: que no se quede sin facturar cuando termines.")
    if tool == "ver_agenda" and result.get("hasta"):
        jobs = result["trabajos"]
        desde, hasta = dia_humano(result["fecha"]), dia_humano(result["hasta"])
        if not jobs:
            return f"No tienes trabajos agendados entre {desde} y {hasta}."
        lines = [f"Tienes {_cuenta(len(jobs), 'trabajo', 'trabajos')} entre {desde} y {hasta}:"]
        dia_actual = None
        for j in jobs:
            dia, _, hora = str(j.get("scheduled_for") or "").partition("T")
            if dia != dia_actual:
                dia_actual = dia
                lines.append(f"\n*{dia_humano(dia)[:1].upper()}{dia_humano(dia)[1:]}*")
            lugar = j.get("zone") or j.get("project_location")
            lines.append(f"• {hora[:5]} {j.get('client_name') or ''} — {j['description']}"
                         + (f" ({lugar})" if lugar else ""))
        return "\n".join(lines)
    if tool == "ver_gastos":
        desde, hasta = result["desde"], result["hasta"]
        # El día 1, «mis gastos» es el mes entero aunque empiece y acabe hoy.
        un_dia = desde == hasta and not result.get("del_mes")
        periodo = (dia_humano(desde) if un_dia
                   else "este mes" if result.get("del_mes") or (
                       desde.endswith("-01") and hasta == date.today().isoformat())
                   else f"entre {dia_humano(desde)} y {dia_humano(hasta)}")
        if not result["gastos"]:
            return f"No tienes gastos apuntados {'para ' if un_dia else ''}{periodo}."
        lines = [f"Gastos {'de ' if un_dia else ''}{periodo}: "
                 f"{_cuenta(result['n'], 'apunte', 'apuntes')}, **{_eur(result['total'])}**."]
        for g in result["gastos"][:10]:
            cuando = str(g.get("spent_on") or g.get("created_at") or "")[:10]
            lines.append(f"• {g['concept']}: {_eur(g['amount'])}"
                         + (f" ({dia_humano(cuando)})" if cuando and not un_dia else ""))
        if result["n"] > 10:
            lines.append(f"…y {result['n'] - 10} más. Los tienes todos en Gastos.")
        return "\n".join(lines)
    if tool == "ver_agenda":
        jobs = result["trabajos"]
        if not jobs:
            return f"No tienes trabajos agendados para {dia_humano(result['fecha'])}."
        lines = [f"Tienes {_cuenta(len(jobs), 'trabajo', 'trabajos')} para "
                 f"{dia_humano(result['fecha'])}:"]
        for j in jobs:
            # Postgres guarda «10:00:00»: al usuario se le dice «10:00».
            h = j["scheduled_for"].split("T")[1][:5] if j.get("scheduled_for") and "T" in j["scheduled_for"] else ""
            lines.append(f"• {h} {j.get('client_name') or ''} — {j['description']}")
        lines.append("Al cerrar cada trabajo, deja la factura preparada. Ahí se escapa mucho dinero.")
        return "\n".join(lines)
    if tool == "ver_cobros_pendientes" and result.get("tras_cobro"):
        if not result["facturas"]:
            return ("No tengo ninguna factura pendiente de cobro"
                    + (f" de {result['cliente']}" if result.get("cliente") else "")
                    + ", así que no hay nada que marcar. Si el cobro es de una factura "
                      "que aún no has emitido, emítela primero.")
        lines = ["¿Qué factura te han pagado? Estas siguen pendientes:"]
        for p in result["facturas"][:8]:
            numero = p.get("number") or f"#{p.get('id')}"
            lines.append(f"• {numero} · {p.get('client_name') or ''} · {_eur(p['total'])}")
        ejemplo = result["facturas"][0].get("number") or result["facturas"][0].get("id")
        lines.append(f"\nDímelo así: «la factura {ejemplo} está cobrada». No he marcado nada.")
        return "\n".join(lines)
    if tool == "ver_cobros_pendientes" and result.get("cliente"):
        quien = result["cliente"]
        if result.get("sin_ficha"):
            return f"No tengo ficha de cliente «{quien}», así que no me consta que te deba nada."
        if result["n"] == 0:
            return f"✅ {quien} no te debe nada: no tiene facturas pendientes de cobro."
        lines = [f"💸 {quien} te debe **{_eur(result['total_pendiente'])}** en "
                 f"{_cuenta(result['n'], 'factura', 'facturas')}:"]
        for p in result["facturas"]:
            d = p.get("days_outstanding")
            lines.append(f"• {p.get('number') or '#' + str(p.get('id'))}: {_eur(p['total'])}"
                         + (f" ({d} días)" if d else ""))
        lines.append(f"Si quieres, dime «recuérdale a {quien} que me pague».")
        return "\n".join(lines)
    if tool == "ver_cobros_pendientes":
        if result["n"] == 0:
            return "✅ No tienes cobros pendientes. Caja limpia. Mantén el hábito: revisarlo una vez al día basta."
        lines = [f"💸 {'Hay' if result['n'] != 1 else 'Tienes'} "
                 f"{_cuenta(result['n'], 'factura', 'facturas')} sin cobrar: "
                 f"**{_eur(result['total_pendiente'])}**."]
        for p in result["facturas"]:
            d = p.get("days_outstanding")
            lines.append(f"• {p['client_name']}: {_eur(p['total'])}" + (f" ({d} días)" if d else ""))
        lines.append("Mi consejo: reclama primero las de más de 7 días, corto y sin disculparte.")
        return "\n".join(lines)
    if tool == "resumen_negocio":
        r = result
        if r.get("anio"):
            periodo = (f"{r['anio']}" if r.get("hasta_mes") == 12
                       else f"{r['anio']} (hasta {_MESES_DEL_ANIO[max(r.get('hasta_mes', 1), 1) - 1]})")
            return (f"📊 Lectura de {periodo}: facturado **{_eur(r['invoiced'])}**, cobrado "
                    f"{_eur(r['collected'])}, pendiente {_eur(r['pending'])}, gastos "
                    f"{_eur(r['expenses'])}.\n\nBeneficio estimado: **{_eur(r['estimated_profit'])}**.")
        mes = str(r.get("month") or "")
        if mes and mes != date.today().strftime("%Y-%m"):
            nombre = _MESES_DEL_ANIO[int(mes[5:7]) - 1]
            etiqueta = nombre if mes[:4] == str(date.today().year) else f"{nombre} de {mes[:4]}"
            return (f"📊 Lectura de {etiqueta}: facturado **{_eur(r['invoiced'])}**, cobrado "
                    f"{_eur(r['collected'])}, pendiente {_eur(r['pending'])}, gastos "
                    f"{_eur(r['expenses'])}.\n\nBeneficio estimado: **{_eur(r['estimated_profit'])}**.")
        hoy = date.today()
        dias = f"llevas {_cuenta(hoy.day, 'día', 'días')}"
        texto = (f"📊 Lectura de {_MESES_DEL_ANIO[hoy.month - 1]} ({dias}): facturado "
                 f"**{_eur(r['invoiced'])}**, cobrado {_eur(r['collected'])}, "
                 f"pendiente {_eur(r['pending'])}, gastos {_eur(r['expenses'])}.\n\n"
                 f"Beneficio estimado: **{_eur(r['estimated_profit'])}**."
                 + (f" Aparta al menos {_eur(r['vat_estimated'])} de IVA para no "
                    "confundirte: no es caja libre." if r.get("vat_estimated") else ""))
        a = r.get("anterior")
        if a:
            nombre = _MESES_DEL_ANIO[int(str(a.get("month") or "0000-01")[5:7]) - 1]
            texto += (f"\n\n{nombre[:1].upper()}{nombre[1:]}, que acaba de cerrar: facturado "
                      f"**{_eur(a['invoiced'])}**, cobrado {_eur(a['collected'])}, gastos "
                      f"{_eur(a['expenses'])}; beneficio estimado {_eur(a['estimated_profit'])}.")
        return texto
    if tool == "ver_impuestos":
        if not result.get("ok"):
            return result.get("error") or "No he podido calcular el trimestre."
        iva = result["iva_resultado"]
        signo = "a pagar" if iva >= 0 else "a tu favor"
        plazo = f" ({result['plazo']})" if result.get("plazo") else ""
        lines = [
            f"🧾 {result['label']}{plazo}. IVA {signo}: **{_eur(abs(iva))}**.",
            f"• Repercutido {_eur(result['iva_repercutido'])} − soportado "
            f"{_eur(result['iva_soportado'])} (modelo 303)",
            f"• IRPF del periodo: {_eur(result['irpf_pago'])} (modelo 130)",
        ]
        if result["datos_incompletos"]:
            lines.append(
                f"⚠️ Hay {_cuenta(result['datos_incompletos'], 'apunte', 'apuntes')} "
                "sin IVA o sin base: "
                "la cifra se moverá cuando los completes."
            )
        lines.append(
            "Son cifras de apoyo con lo registrado hasta hoy. "
            "Quien presenta y valida es tu gestoría."
        )
        if result.get("plazo"):
            lines.append("Si querías el trimestre que acaba de empezar, dime «IVA de este "
                         "trimestre».")
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
            f"🧰 Tienes {_cuenta(result['active_count'], 'proyecto activo', 'proyectos activos')}. "
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
            f"👷 Equipo: {_cuenta(len(people), 'persona', 'personas')}. "
            + ("Ahora mismo nadie tiene la jornada abierta." if not inside else
               f"Ahora mismo {len(inside)} {'tiene' if len(inside) == 1 else 'tienen'} "
               "la jornada abierta.")
        )
    if tool == "ver_documentos_pendientes":
        return (
            "📎 No tienes documentos pendientes de revisar."
            if not result.get("n") else
            f"📎 Hay {_cuenta(result['n'], 'documento', 'documentos')} esperando tu confirmación. "
            f"{'Lo' if result['n'] == 1 else 'Los'} encontrarás en Documentos."
        )
    if tool == "ver_solicitudes_gestoria":
        return (
            "Tu gestoría no tiene solicitudes abiertas."
            if not result.get("n") else
            f"Tu gestoría tiene {_cuenta(result['n'], 'solicitud abierta', 'solicitudes abiertas')}. "
            "Te digo cuál atender primero si quieres."
        )
    if tool == "ver_control_noesis":
        automatic = [p for p in result["permisos"] if p["modo"] == "automatic"]
        confirmed = [p for p in result["permisos"] if p["modo"] == "confirm"]
        return (
            f"Puedo ocuparme solo de {_cuenta(len(automatic), 'tipo', 'tipos')} de tarea "
            f"interna. En {_cuenta(len(confirmed), 'acción', 'acciones')} siempre te "
            "pregunto. Transferencias, "
            "impuestos, devoluciones y borrados nunca son automáticos."
        )
    return "Hecho."
