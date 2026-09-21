"""Captacion de clientes de Bynoesis: el embudo, los guiones y la lista.

Esto es el CRM **de la empresa**, no el del autonomo. El de `db.leads` guarda los
presupuestos de un fontanero; este guarda a que fontanero perseguimos nosotros.

Tres decisiones que explican el resto del archivo:

1. **Los estados son los del piloto, no los de un CRM generico.** «Interesado» no
   significa nada; «ha aceptado el piloto» y «lo usa solo desde hace dos semanas»
   deciden si hay negocio. Salen de `docs/06-negocio-y-finanzas/Ruta-a-5000-autonomos.html`.
2. **Cada estado trae escrito lo siguiente que hay que hacer y con que palabras.**
   Un CRM que solo guarda nombres se abandona la segunda semana; lo que se usa es
   el que cuando lo abres ya sabe que toca decir hoy.
3. **El origen del dato manda en lo que se puede hacer con el.** Un telefono que
   te dio su dueno y uno que sacaste de una ficha publica no son lo mismo: el
   segundo obliga a decirle de donde ha salido en el primer contacto (art. 14
   RGPD). Por eso `ORIGENES` lleva ese dato y no es una etiqueta suelta.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import re
import unicodedata


# ---------------------------------------------------------------- Embudo ----
# clave -> (etiqueta, que significa de verdad, siguiente accion por defecto)
ESTADOS: dict[str, dict] = {
    "lista": {
        "etiqueta": "En la lista",
        "significa": "Tienes el nombre. No le has dicho nada todavía.",
        "siguiente": "Primer contacto",
        "dias": 0,
        "abierto": True,
    },
    "contactado": {
        "etiqueta": "Contactado",
        "significa": "Le escribiste o le llamaste. Aún no ha contestado.",
        "siguiente": "Insistir una vez",
        "dias": 3,
        "abierto": True,
    },
    "cita": {
        "etiqueta": "Cita puesta",
        "significa": "Hay café o llamada con día y hora.",
        "siguiente": "Recordar la víspera",
        "dias": 1,
        "abierto": True,
    },
    "hablado": {
        "etiqueta": "Ya hablado",
        "significa": "Hiciste la entrevista. Sabes cómo trabaja.",
        "siguiente": "Proponer el piloto o descartar",
        "dias": 2,
        "abierto": True,
    },
    "piloto": {
        "etiqueta": "Piloto en marcha",
        "significa": "Está dado de alta y usándolo en su trabajo real.",
        "siguiente": "Llamada de seguimiento",
        "dias": 7,
        "abierto": True,
    },
    "carta": {
        "etiqueta": "Carta firmada",
        "significa": "Firmó la carta de intención al precio de fundador.",
        "siguiente": "Cobrar en cuanto Stripe esté en real",
        "dias": 14,
        "abierto": True,
    },
    "cliente": {
        "etiqueta": "Pagando",
        "significa": "Cliente de pago. El único estado que cuenta como venta.",
        "siguiente": "Revisión mensual",
        "dias": 30,
        "abierto": False,
    },
    "dormido": {
        "etiqueta": "Dormido",
        "significa": "Ahora no, pero no ha dicho que no. Se reabre en dos meses.",
        "siguiente": "Reabrir",
        "dias": 60,
        "abierto": False,
    },
    "descartado": {
        "etiqueta": "Descartado",
        "significa": "No es cliente o ha dicho que no. No se le vuelve a llamar.",
        "siguiente": "",
        "dias": 0,
        "abierto": False,
    },
}
ESTADOS_ABIERTOS = tuple(k for k, v in ESTADOS.items() if v["abierto"])
ORDEN_ESTADOS = tuple(ESTADOS)

# El embudo esperado de la parte 1 de la Ruta a 5.000. Son ordenes de magnitud,
# no datos medidos: estan aqui para saber si 40 nombres es exagerar o quedarse
# corto, no para prometer una conversion.
# Cuántas llamadas caben en un día de verdad: cinco entre las 7:30 y las 8:30, tres
# a mediodía y dos por la tarde. Recién pegada la lista, «hoy» vence entera; sin este
# tope, la página pediría setenta llamadas y no se haría ninguna.
LOTE_DIARIO = 10

OBJETIVO = (
    ("lista", 40, "nombres en la lista"),
    ("hablado", 20, "conversaciones de verdad"),
    ("piloto", 5, "pilotos en marcha"),
    ("carta", 2, "cartas de intención"),
)

# ---------------------------------------------------------------- Origen ----
# `del_interesado`: True si el contacto te lo dio la persona. Cuando es False, el
# dato sale de un tercero o de una fuente publica y hay que decirselo en el primer
# contacto, ademas de anotar la fecha en que se le dijo.
ORIGENES: dict[str, dict] = {
    "circulo": {"etiqueta": "Tu círculo", "del_interesado": True,
                "nota": "Ya te conoce. Es el que más convierte con diferencia."},
    "referido": {"etiqueta": "Te lo presentan", "del_interesado": True,
                 "nota": "Nombra a quien os presenta en la primera frase: es lo "
                         "que más sube la tasa de respuesta."},
    "almacen": {"etiqueta": "Almacén de material", "del_interesado": False,
                "nota": "Entre las 7 y las 9 de la mañana pasa por el mostrador "
                        "todo el oficio de la comarca, y el dueño los conoce."},
    "gestoria": {"etiqueta": "Gestoría", "del_interesado": False,
                 "nota": "Pregunta solo esto: «¿qué cliente autónomo te trae los "
                         "papeles hechos un desastre?»."},
    "gremio": {"etiqueta": "Gremio o asociación", "del_interesado": False,
               "nota": "Charlas y cursos. Ahora sirven para conocer caras; el "
                       "canal viene después."},
    "maps": {"etiqueta": "Ficha pública (Maps)", "del_interesado": False,
             "nota": "Entre 5 y 30 reseñas, un móvil y ninguna web: pequeños, y "
                     "el que contesta es el dueño."},
    "plataforma": {"etiqueta": "Portal de encargos", "del_interesado": False,
                   "nota": "Si ya paga por conseguir clientes, invierte en su "
                           "negocio."},
    "entrante": {"etiqueta": "Vino él solo", "del_interesado": True,
                 "nota": "Web, redes o boca a boca. Llamar el mismo día."},
    "otro": {"etiqueta": "Otro", "del_interesado": False, "nota": ""},
}

OFICIOS: dict[str, str] = {
    "fontaneria": "Fontanería",
    "electricidad": "Electricidad",
    "clima": "Clima y calefacción",
    "reformas": "Reformas y obra",
    "pintura": "Pintura",
    "carpinteria": "Carpintería",
    "cerrajeria": "Cerrajería",
    "limpieza": "Limpieza",
    "jardineria": "Jardinería",
    "mantenimiento": "Mantenimiento",
    "otro": "Otro oficio",
}

# Palabras que aparecen escritas en una lista hecha a mano y a que oficio van.
_PISTAS_OFICIO = {
    "fontaner": "fontaneria", "lampist": "fontaneria",
    "electric": "electricidad", "electricis": "electricidad",
    "clima": "clima", "aire": "clima", "calefac": "clima", "caldera": "clima",
    "reform": "reformas", "obra": "reformas", "albañil": "reformas",
    "albanil": "reformas", "paleta": "reformas", "constru": "reformas",
    "pintor": "pintura", "pintura": "pintura",
    "fuster": "carpinteria", "carpinter": "carpinteria", "mueble": "carpinteria",
    "cerraj": "cerrajeria", "manyà": "cerrajeria", "manya": "cerrajeria",
    "limpiez": "limpieza", "neteja": "limpieza",
    "jardin": "jardineria", "jardi": "jardineria", "paisaj": "jardineria",
    "manteni": "mantenimiento",
}

CANALES: dict[str, str] = {
    "llamada": "Llamada",
    "whatsapp": "WhatsApp",
    "cafe": "Café o visita",
    "email": "Correo",
    "presencial": "Encuentro en persona",
    "otro": "Otro",
}


# ---------------------------------------------------------------- Guiones ---
# Lo que hay que decir en cada punto, en las dos lenguas. El nombre se sustituye
# al vuelo; el resto se copia tal cual. Las frases salen de la parte 1 de la Ruta
# a 5.000: pedir veinte minutos, no una demo, y preguntar por el pasado.
GUIONES: dict[str, dict] = {
    "lista_referido": {
        "titulo": "Primer contacto · te presentan",
        "cuando": "Cuando alguien os presenta. Es el que mejor funciona.",
        "canal": "whatsapp",
        "es": ("Hola, {nombre}. Soy {yo}; me ha pasado tu contacto {quien}. Estoy "
               "montando una herramienta para autónomos de oficios y, antes de "
               "vendérsela a nadie, quiero entender cómo lleváis los presupuestos, "
               "las facturas y los cobros. ¿Te invito a un café de 20 minutos esta "
               "semana? No te voy a vender nada."),
        "ca": ("Hola, {nombre}. Sóc en {yo}; m'ha passat el teu contacte {quien}. "
               "Estic fent una eina per a autònoms d'oficis i, abans de vendre-la "
               "a ningú, vull entendre com porteu els pressupostos, les factures i "
               "els cobraments. Et convido a un cafè de 20 minuts aquesta setmana? "
               "No et vull vendre res."),
    },
    "lista_frio": {
        "titulo": "Primer contacto · en frío, por teléfono",
        "cuando": ("Cuando el número sale de una ficha pública. Por teléfono, no "
                   "por WhatsApp: mira el aviso del final de la página."),
        "canal": "llamada",
        "es": ("¿Buenos días, {nombre}? Soy {yo}, de Bynoesis. He visto tu ficha "
               "en Google buscando {oficio} por {zona}, y por eso tengo tu número. "
               "No te llamo para venderte nada: estoy haciendo una herramienta para "
               "autónomos de oficios y necesito entender cómo lleváis los "
               "presupuestos y las facturas antes de terminarla. Son veinte "
               "minutos, cuando te vaya bien. Y si prefieres que no te llame más, "
               "me lo dices y te borro ahora mismo."),
        "ca": ("Bon dia, {nombre}? Sóc en {yo}, de Bynoesis. He vist la teva fitxa "
               "a Google buscant {oficio} per {zona}, i per això tinc el teu "
               "número. No et truco per vendre't res: estic fent una eina per a "
               "autònoms d'oficis i necessito entendre com porteu els pressupostos "
               "i les factures abans d'acabar-la. Són vint minuts, quan et vagi bé. "
               "I si prefereixes que no et truqui més, m'ho dius i t'esborro ara "
               "mateix."),
    },
    "contactado": {
        "titulo": "Segundo intento, a los tres días",
        "cuando": "Una vez. Si tampoco contesta, a dormido: no se insiste tres veces.",
        "canal": "whatsapp",
        "es": ("{nombre}, te escribí el otro día y igual se te pasó. Solo son "
               "veinte minutos para que me cuentes cómo te organizas con los "
               "presupuestos y las facturas. Si esta semana no puedes, lo dejamos "
               "para más adelante sin problema."),
        "ca": ("{nombre}, et vaig escriure l'altre dia i potser se't va passar. "
               "Només són vint minuts perquè m'expliquis com t'organitzes amb els "
               "pressupostos i les factures. Si aquesta setmana no pots, ho deixem "
               "per més endavant sense problema."),
    },
    "cita": {
        "titulo": "Recordatorio la víspera",
        "cuando": "El día antes. Evita la mitad de los plantones.",
        "canal": "whatsapp",
        "es": ("{nombre}, nos vemos mañana. ¿Te sigue yendo bien la hora? Llevo el "
               "portátil por si quieres ver algo, pero sobre todo voy a escuchar."),
        "ca": ("{nombre}, ens veiem demà. Et va bé l'hora? Porto el portàtil per si "
               "vols veure alguna cosa, però sobretot vinc a escoltar."),
    },
    "hablado": {
        "titulo": "La propuesta de piloto, en persona",
        "cuando": ("Solo a quien haya contado un problema real. Con fecha de fin: "
                   "un piloto sin fecha de fin es un regalo sin fin."),
        "canal": "cafe",
        "es": ("Está construido y funciona. Te propongo usarlo gratis ocho semanas "
               "en tu trabajo real. A cambio te pido tres cosas: que lo uses de "
               "verdad, quince minutos a la semana para contarme qué falla, y poder "
               "contar tus cifras si te va bien. Si al final quieres seguir, entras "
               "a precio de fundador."),
        "ca": ("Està construït i funciona. Et proposo fer-lo servir de franc vuit "
               "setmanes a la teva feina real. A canvi et demano tres coses: que el "
               "facis servir de veritat, quinze minuts a la setmana per explicar-me "
               "què falla, i poder explicar les teves xifres si et va bé. Si al "
               "final vols continuar, hi entres a preu de fundador."),
    },
    "piloto": {
        "titulo": "La pregunta del precio, semana 6",
        "cuando": "Semana 6 de las ocho. Y fíjate en si duda antes de contestar.",
        "canal": "llamada",
        "es": ("{nombre}, una pregunta incómoda a propósito: si esto costara 29 € "
               "al mes, ¿seguirías usándolo? Dime que no sin problema; me sirve "
               "igual saberlo ahora."),
        "ca": ("{nombre}, una pregunta incòmoda a propòsit: si això costés 29 € al "
               "mes, el continuaries fent servir? Digue'm que no sense problema; em "
               "serveix igual saber-ho ara."),
    },
    "dormido": {
        "titulo": "Reabrir a los dos meses",
        "cuando": "Dos meses después. Con una novedad concreta, no con un «¿qué tal?».",
        "canal": "whatsapp",
        "es": ("{nombre}, hace un par de meses hablamos y me dijiste que no era el "
               "momento. Desde entonces {novedad}. Si quieres te lo enseño en "
               "quince minutos; y si sigue sin ser el momento, no insisto más."),
        "ca": ("{nombre}, fa un parell de mesos vam parlar i em vas dir que no era "
               "el moment. Des de llavors {novedad}. Si vols t'ho ensenyo en quinze "
               "minuts; i si continua sense ser el moment, no insisteixo més."),
    },
}

# Las cinco preguntas del cafe. Todas miran al pasado a proposito: «lo usarias?»
# siempre recibe un si, y ese si no vale nada.
PREGUNTAS_CAFE = (
    "¿Cómo hiciste el último presupuesto? ¿Cuánto tardaste?",
    "¿Cuánto dinero te deben ahora mismo? ¿Quién?",
    "¿Cuándo haces las facturas: el mismo día, el viernes, a final de mes?",
    "¿Qué te pide la gestoría cada trimestre y cómo se lo mandas?",
    "¿Qué usas hoy? ¿Qué dejaste de usar, y por qué?",
)

GUION_POR_ESTADO = {
    "lista": ("lista_referido", "lista_frio"),
    "contactado": ("contactado",),
    "cita": ("cita",),
    "hablado": ("hablado",),
    "piloto": ("piloto",),
    "dormido": ("dormido",),
}


# ------------------------------------------------------------- Normalizar ---
def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto or "")
                   if unicodedata.category(c) != "Mn").lower()


def normalizar_telefono(raw) -> str | None:
    """Deja el telefono en un formato comparable. None si no parece un telefono.

    Sirve sobre todo para no meter dos veces al mismo cuando se pega la lista por
    segunda vez: en una lista escrita a mano el mismo numero aparece como
    '600 11 22 33', '+34600112233' y '0034 600112233'.
    """
    digitos = re.sub(r"[^0-9+]", "", str(raw or ""))
    if not digitos:
        return None
    digitos = digitos.replace("+", "")
    if digitos.startswith("0034"):
        digitos = digitos[4:]
    elif digitos.startswith("34") and len(digitos) == 11:
        digitos = digitos[2:]
    if len(digitos) < 9:
        return None
    return "+34" + digitos if len(digitos) == 9 else "+" + digitos


def adivina_oficio(texto: str) -> str | None:
    plano = _sin_tildes(texto)
    for pista, oficio in _PISTAS_OFICIO.items():
        if _sin_tildes(pista) in plano:
            return oficio
    return None


_RE_TELEFONO = re.compile(r"(?:\+?\d[\d\s.\-]{7,})")
# Separadores de una lista escrita a mano: punto y coma, coma, tabulador, un
# guion o punto volado rodeados de espacios, o dos espacios seguidos.
_RE_SEPARA = re.compile(r"[;,\t]|\s+[-\u2013\u00b7|]\s+|\s{2,}")
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


# Cómo se llama cada columna en las listas que ya existen: la prospección de
# OpenStreetMap, un Excel propio o lo que exporte cualquier herramienta.
_COLUMNAS = {
    "nombre": "nombre", "name": "nombre", "empresa": "nombre", "titular": "nombre",
    "telefono": "telefono", "teléfono": "telefono", "movil": "telefono",
    "móvil": "telefono", "phone": "telefono", "tel": "telefono",
    "email": "email", "correo": "email", "e-mail": "email",
    "oficio": "oficio", "actividad": "oficio", "gremio": "oficio",
    "poblacion": "poblacion", "población": "poblacion", "ciudad": "poblacion",
    "municipio": "poblacion", "localidad": "poblacion", "direccion": "poblacion",
    "dirección": "poblacion", "zona": "poblacion",
    "nota": "nota", "notas": "nota", "observaciones": "nota",
    "presentado_por": "presentado_por", "quien": "presentado_por",
    "referido_por": "presentado_por",
}


def _parse_con_cabecera(lineas: list[str]) -> list[dict] | None:
    """Si lo pegado es una tabla con cabecera, la respeta en vez de adivinar.

    La lista de 74 fichas de `outputs/prospeccion/` y cualquier Excel propio salen
    así. Adivinar sobre una tabla con columnas sería tirar información que ya está
    ordenada: el nombre acabaría siendo «Oficio» y el teléfono, una dirección.
    """
    import csv as _csv

    cabecera = [c.strip().lower() for c in re.split(r"[;\t]", lineas[0])]
    if len(cabecera) < 2 or not any(c in _COLUMNAS for c in cabecera):
        return None
    if _COLUMNAS.get(cabecera[0]) is None and "nombre" not in [
            _COLUMNAS.get(c) for c in cabecera]:
        return None
    separador = ";" if ";" in lineas[0] else "\t"
    filas: list[dict] = []
    for cruda in _csv.DictReader(lineas, delimiter=separador):
        fila: dict = {}
        sobras: list[str] = []
        webs: list[str] = []
        for columna, valor in cruda.items():
            valor = (valor or "").strip()
            if not valor or columna is None:
                continue
            destino = _COLUMNAS.get(columna.strip().lower())
            if destino == "telefono":
                fila["telefono"] = normalizar_telefono(valor)
            elif destino == "oficio":
                fila["oficio"] = adivina_oficio(valor)
                if not fila["oficio"]:
                    sobras.append(valor)
            elif destino == "nota" or (destino and destino in fila):
                sobras.append(valor)
            elif destino:
                fila[destino] = valor[:200]
            elif valor.lower().startswith(("http", "www.")):
                webs.append(valor)
            else:
                # Una columna que no conocemos no se tira: se queda en la nota.
                # Las direcciones de web y de mapa sí, que llenan la ficha de ruido.
                sobras.append(valor[:120])
        if not fila.get("nombre"):
            # Una ficha sin nombre pero con teléfono es un cliente igual: en la
            # prospección de mapas pasa a menudo. Se le pone el dominio de su web
            # o el teléfono para poder llamarle, y ya se corregirá al hablar.
            dominio = next((re.sub(r"^(https?://)?(www\.)?", "", w).split("/")[0]
                            for w in webs), None)
            if not dominio and not fila.get("telefono"):
                continue
            fila["nombre"] = dominio or f"Sin nombre · {fila['telefono']}"
        if sobras:
            fila["nota"] = " · ".join([fila.get("nota") or "", *sobras]).strip(" ·")
        filas.append({"nombre": fila["nombre"][:200],
                      "oficio": fila.get("oficio"),
                      "poblacion": fila.get("poblacion"),
                      "telefono": fila.get("telefono"),
                      "email": fila.get("email"),
                      "presentado_por": fila.get("presentado_por"),
                      "nota": fila.get("nota") or None})
    return filas or None


def parse_lista(texto: str) -> list[dict]:
    """Convierte lo pegado en filas. Perdona el formato a proposito.

    La lista de 40 nombres se escribe en la libreta del movil un martes por la
    noche, no en un CSV. Acepta una persona por linea y separadores `;`, `,`,
    tabulador o dos espacios; el telefono y el correo se reconocen esten donde
    esten, y del resto la primera parte es el nombre. Lo que no entiende lo deja
    en la nota en vez de tirarlo.
    """
    lineas = [l for l in (texto or "").splitlines() if l.strip()]
    if not lineas:
        return []
    con_cabecera = _parse_con_cabecera(lineas)
    if con_cabecera is not None:
        return con_cabecera
    filas: list[dict] = []
    for linea in lineas:
        linea = linea.strip().lstrip("-*•").strip()
        if not linea:
            continue
        telefono = None
        m = _RE_TELEFONO.search(linea)
        if m:
            candidato = normalizar_telefono(m.group(0))
            if candidato:
                telefono = candidato
                linea = (linea[:m.start()] + " " + linea[m.end():]).strip()
        email = None
        m = _RE_EMAIL.search(linea)
        if m:
            email = m.group(0)
            linea = (linea[:m.start()] + " " + linea[m.end():]).strip()
        partes = [p.strip(" \u00b7-|\u2013") for p in _RE_SEPARA.split(linea)]
        partes = [p for p in partes if p]
        if not partes and not telefono and not email:
            continue
        nombre = partes[0] if partes else (telefono or email)
        resto = partes[1:]
        oficio = None
        poblacion = None
        sobras: list[str] = []
        for parte in resto:
            if oficio is None and adivina_oficio(parte):
                oficio = adivina_oficio(parte)
                continue
            if poblacion is None and len(parte) <= 40 and not parte.lower().startswith(
                    ("me lo", "via ", "por ", "de parte")):
                poblacion = parte
                continue
            sobras.append(parte)
        if oficio is None:
            oficio = adivina_oficio(nombre)
        filas.append({
            "nombre": nombre[:200],
            "oficio": oficio,
            "poblacion": poblacion,
            "telefono": telefono,
            "email": email,
            "nota": " · ".join(sobras) or None,
        })
    return filas


# ---------------------------------------------------------------- Resumen ---
def _dias_desde(valor) -> int | None:
    if not valor:
        return None
    try:
        cuando = datetime.fromisoformat(str(valor)).date()
    except ValueError:
        try:
            cuando = date.fromisoformat(str(valor)[:10])
        except ValueError:
            return None
    return (date.today() - cuando).days


def siguiente_fecha(estado: str, desde: date | None = None) -> str:
    """Cuando toca volver a tocar a alguien que acaba de entrar en este estado."""
    dias = ESTADOS.get(estado, {}).get("dias", 3)
    return ((desde or date.today()) + timedelta(days=dias)).isoformat()


def enriquecer(prospect: dict) -> dict:
    """Anade a una fila lo que la pagina necesita y la base no guarda.

    Se calcula aqui y no en JavaScript para que la pagina, el aviso de «hay que
    informarle» y las pruebas usen exactamente la misma regla.
    """
    p = dict(prospect)
    estado = p.get("estado") or "lista"
    meta = ESTADOS.get(estado, ESTADOS["lista"])
    p["estado_etiqueta"] = meta["etiqueta"]
    p["estado_significa"] = meta["significa"]
    p["abierto"] = meta["abierto"]
    p["origen_etiqueta"] = ORIGENES.get(p.get("origen") or "otro",
                                        ORIGENES["otro"])["etiqueta"]
    p["oficio_etiqueta"] = OFICIOS.get(p.get("oficio") or "", "")
    hoy = date.today().isoformat()
    p["vencido"] = bool(p.get("siguiente_el") and p["siguiente_el"] <= hoy
                        and meta["abierto"] and not p.get("baja"))
    p["dias_sin_tocar"] = _dias_desde(p.get("updated_at") or p.get("created_at"))
    # Aviso del art. 14 RGPD: si el dato no lo dio el interesado, en el primer
    # contacto hay que decirle quien eres y de donde has sacado su telefono.
    origen = ORIGENES.get(p.get("origen") or "otro", ORIGENES["otro"])
    p["debe_informar"] = bool(not origen["del_interesado"]
                              and not p.get("informado_el")
                              and not p.get("baja"))
    p["guiones"] = [g for g in GUION_POR_ESTADO.get(estado, ()) if g in GUIONES]
    return p


def resumen(prospects: list[dict]) -> dict:
    """El parte del embudo: cuantos hay en cada sitio y que toca hoy."""
    filas = [enriquecer(p) for p in prospects]
    vivos = [p for p in filas if not p.get("baja")]
    por_estado = {clave: 0 for clave in ORDEN_ESTADOS}
    for p in vivos:
        por_estado[p.get("estado") or "lista"] = (
            por_estado.get(p.get("estado") or "lista", 0) + 1)
    hoy = [p for p in vivos if p["vencido"]]
    # «Alcanzado» de un peldano incluye a los que ya pasaron de largo: quien esta
    # en piloto tambien tuvo su conversacion. Contar solo el estado actual haria
    # que el embudo se vaciara solo al avanzar la gente.
    alcanzado = {}
    for indice, clave in enumerate(ORDEN_ESTADOS):
        if clave in ("dormido", "descartado"):
            continue
        alcanzado[clave] = sum(
            1 for p in vivos
            if p.get("estado") in ORDEN_ESTADOS
            and ORDEN_ESTADOS.index(p["estado"]) >= indice
            and p.get("estado") not in ("dormido", "descartado")
        )
    embudo = [{
        "clave": clave, "meta": meta, "que": que,
        "hay": alcanzado.get(clave, 0),
        "falta": max(0, meta - alcanzado.get(clave, 0)),
    } for clave, meta, que in OBJETIVO]
    frios = [p for p in vivos if p["abierto"] and (p["dias_sin_tocar"] or 0) >= 14]
    return {
        "total": len(vivos),
        "bajas": len(filas) - len(vivos),
        "por_estado": por_estado,
        "abiertos": sum(por_estado[k] for k in ESTADOS_ABIERTOS),
        "hoy": hoy,
        "hoy_lote": hoy[:LOTE_DIARIO],
        "hoy_mas": max(0, len(hoy) - LOTE_DIARIO),
        "frios": frios,
        "sin_informar": [p for p in vivos if p["debe_informar"]],
        "embudo": embudo,
        "parte": _parte(vivos, hoy, embudo, frios),
    }


def _parte(vivos, hoy, embudo, frios) -> str:
    """Una frase. Es lo que se recuerda al cerrar la pestana."""
    if not vivos:
        return ("Todavía no hay nadie en la lista. El primer paso no es vender: "
                "es escribir cuarenta nombres.")
    en_lista = embudo[0]
    if en_lista["falta"] > 0 and not hoy:
        return (f"Tienes {en_lista['hay']} nombres y hoy no hay nada vencido. "
                f"Lo que toca es seguir la lista hasta 40: faltan "
                f"{en_lista['falta']}.")
    if hoy:
        primero = hoy[0]
        toca = ESTADOS[primero["estado"]]["siguiente"].lower()
        if len(hoy) > LOTE_DIARIO:
            # Decir la verdad («hay 73 vencidos») y a la vez pedir un día de
            # trabajo. Pedir los 73 es como se consigue que no se haga ninguno.
            return (f"Hay {len(hoy)} esperando respuesta tuya, que no caben en un "
                    f"día. Hoy llama a {LOTE_DIARIO}: empieza por "
                    f"{primero['nombre']}, {toca}.")
        return (f"Hoy tienes {len(hoy)} persona(s) esperando respuesta tuya. "
                f"Empieza por {primero['nombre']}: {toca}.")
    if frios:
        return (f"Nada vencido hoy, pero {len(frios)} llevan más de dos semanas "
                "sin que les digas nada. Un contacto sin siguiente paso se enfría.")
    pagando = sum(1 for p in vivos if p.get("estado") == "cliente")
    return (f"{len(vivos)} en el embudo y {pagando} pagando. Todo tiene su "
            "siguiente paso puesto.")
