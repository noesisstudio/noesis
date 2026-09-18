"""Modelo economico de Bynoesis, calculado en el producto y no en una hoja suelta.

Hasta ahora el modelo vivia solo en `analysis/build_modelo_economico.py` y en los
libros de Excel que genera: para saber el margen o el equilibrio habia que abrir un
archivo. Aqui esta la misma aritmetica, en Python puro y sin dependencias, para que
el panel de administracion la pinte con los datos reales de la cuenta.

Dos ideas ordenan todo el modulo:

1. **Supuesto y dato no se mezclan.** `ASSUMPTIONS` son cifras de planificacion sin
   medir; lo observado llega desde `db` y se marca aparte. Cuando hay dato real, el
   informe lo pone al lado del supuesto en vez de sustituirlo en silencio, porque la
   diferencia entre los dos es justo lo que el piloto tiene que corregir.
2. **Hay dos contribuciones, no una.** Mientras el founder atiende, su tiempo no sale
   de la caja: manda la contribucion *en caja* y lo que limita son las horas. En
   cuanto ese soporte lo paga alguien, manda la *cargada*. Cobrar el soporte a
   25 EUR/hora y ademas pagar una retirada al founder contaria su tiempo dos veces.

Las cifras de coste por cuenta salen del analisis del 15/07/2026 sobre tarifas
publicadas de Stripe, Meta, Anthropic, Groq y Railway. `tests/test_economics.py` las
fija para que no puedan desviarse de los libros de `analysis/` sin que salte.
"""

from __future__ import annotations

import math
from typing import Any

PLANES = ("Autonomo", "Negocio", "Premium")

# Supuestos de planificacion. Nada de esto esta medido: no hay clientes de pago.
# Las claves por plan van en el orden de PLANES.
ASSUMPTIONS: dict[str, Any] = {
    # --- Catalogo y uso incluido ---
    "precio": (29.0, 49.0, 99.0),
    "mix": (0.55, 0.35, 0.10),
    "creditos": (75, 300, 1500),
    "uso": (0.35, 0.40, 0.25),
    "interno": (0.60, 0.60, 0.60),
    "wa_util": (30, 80, 200),
    "audio": (15, 60, 200),
    "docs": (15, 50, 200),
    "docs_fuera": (0.20, 0.20, 0.20),
    "almacen": (0.25, 1.0, 3.0),
    "voz": (0, 0, 100),
    "soporte": (12.0, 20.0, 45.0),
    "onboarding": (30.0, 60.0, 120.0),
    # --- Tarifas de proveedores (15/07/2026) ---
    "eurusd": 1 / 1.1405,
    "stripe_pay": 0.015,
    "stripe_bill": 0.007,
    "stripe_fijo": 0.25,
    "wa_precio": 0.0166,
    "haiku": 0.014,
    "qwen": 0.003028,
    "peso_qwen": 0.80,
    "whisper": 0.04,
    "extraccion": 0.012,
    "storage": 0.015,
    "voz_min": 0.11,
    "voz_num": 2.0,
    # --- Comportamiento del cliente (sin medir) ---
    "churn_nuevo": 0.08,
    "churn_maduro": 0.04,
    "dias_prueba": 14,
    "impagos": 0.03,
    "mult_nueva": 2.5,
    # --- Tiempo del founder (sin medir) ---
    "horas_mes": 60.0,
    "horas_alta": 3.0,
    "objetivo": 5,
    "crecimiento": 0.05,
    "hora_soporte": 25.0,
    # --- Estructura mensual (pendiente de facturas reales) ---
    "plataforma": 7.0,
    "herramientas": 40.0,
    "gestoria": 60.0,
    "seguro": 30.0,
    "ads": 0.0,
    "cuota_autonomos": 300.0,
    "retirada": 1200.0,
    "caja_inicial": 4000.0,
    # --- Captacion (sin medir / sin aprobar) ---
    "cac": 150.0,
    "implantacion": 99.0,
    "pct_implantacion": 0.0,
}

# Palancas que el panel deja mover. Fuera de estos limites el modelo deja de
# describir este negocio, asi que se recortan en vez de aceptarlos.
LEVERS: dict[str, tuple[float, float]] = {
    "retirada": (0.0, 5000.0),
    "horas_mes": (5.0, 200.0),
    "churn_maduro": (0.001, 0.30),
    "soporte_medio": (1.0, 120.0),
    "objetivo": (0.0, 60.0),
    "pct_implantacion": (0.0, 1.0),
}

# --------------------------------------------------------------------------- #
# QUE SE PUEDE EDITAR DESDE LA WEB
#
# Un solo catalogo gobierna tres cosas a la vez: que campos pinta el formulario,
# que valores acepta el guardado y que limites se aplican. Tener esas tres listas
# separadas es como se acaba teniendo un campo que la web deja escribir y el
# modelo ignora en silencio.
#
# "escalar" es un numero; "plan" son tres, uno por plan, en el orden de PLANES.
# --------------------------------------------------------------------------- #
GRUPOS = (
    ("estructura", "Lo que sale de tu bolsillo cada mes",
     "Las facturas reales. Es la parte que mas mueve el equilibrio y la que "
     "sigue pendiente de confirmar."),
    ("cliente", "Como se comporta un cliente",
     "Nada de esto esta medido: no hay clientes de pago. Son las cifras que mas "
     "mueven el resultado."),
    ("tiempo", "Tu tiempo",
     "En un negocio de una persona el limite no es el mercado, son las horas."),
    ("planes", "Precio y uso incluido en cada plan",
     "Lo que cada plan promete y lo que se espera que consuma."),
    ("proveedores", "Tarifas de proveedores",
     "Consultadas el 15/07/2026. Cambialas cuando llegue una factura distinta."),
    ("canal", "Captacion y canal",
     "Propuesta del 16/09/2026, sin aprobar."),
)

EDITABLE: dict[str, dict] = {
    # --- Estructura: euros al mes ---
    "plataforma": {"grupo": "estructura", "tipo": "escalar", "min": 0, "max": 5000,
                   "paso": 1, "unidad": "€/mes", "etiqueta": "Plataforma (Railway, dominio, correo)",
                   "nota": "PENDIENTE: la factura real."},
    "herramientas": {"grupo": "estructura", "tipo": "escalar", "min": 0, "max": 5000,
                     "paso": 1, "unidad": "€/mes", "etiqueta": "Herramientas y suscripciones",
                     "nota": "IDE, diseno, analitica, almacenamiento."},
    "gestoria": {"grupo": "estructura", "tipo": "escalar", "min": 0, "max": 5000,
                 "paso": 1, "unidad": "€/mes", "etiqueta": "Gestoria",
                 "nota": "PENDIENTE: presupuesto real."},
    "seguro": {"grupo": "estructura", "tipo": "escalar", "min": 0, "max": 5000,
               "paso": 1, "unidad": "€/mes", "etiqueta": "Seguro y otros fijos",
               "nota": "Responsabilidad civil. PENDIENTE."},
    "ads": {"grupo": "estructura", "tipo": "escalar", "min": 0, "max": 20000,
            "paso": 10, "unidad": "€/mes", "etiqueta": "Presupuesto de captacion",
            "nota": "A cero, captas solo con tu tiempo."},
    "cuota_autonomos": {"grupo": "estructura", "tipo": "escalar", "min": 0, "max": 2000,
                        "paso": 5, "unidad": "€/mes", "etiqueta": "Cuota de autonomos",
                        "nota": "PENDIENTE: depende de tarifa plana y forma juridica."},
    "retirada": {"grupo": "estructura", "tipo": "escalar", "min": 0, "max": 10000,
                 "paso": 50, "unidad": "€/mes", "etiqueta": "Lo que quieres cobrar tu",
                 "nota": "Es una decision, no un dato. Sin ella el equilibrio no significa nada."},
    "caja_inicial": {"grupo": "estructura", "tipo": "escalar", "min": 0, "max": 500000,
                     "paso": 100, "unidad": "€", "etiqueta": "Caja inicial disponible",
                     "nota": "Lo que puedes aguantar antes de llegar al equilibrio."},
    # --- Cliente ---
    "churn_nuevo": {"grupo": "cliente", "tipo": "escalar", "min": 0.0, "max": 0.6,
                    "paso": 0.005, "unidad": "%/mes", "porcentaje": True,
                    "etiqueta": "Bajas los tres primeros meses", "nota": "SIN MEDIR."},
    "churn_maduro": {"grupo": "cliente", "tipo": "escalar", "min": 0.001, "max": 0.3,
                     "paso": 0.005, "unidad": "%/mes", "porcentaje": True,
                     "etiqueta": "Bajas a partir del cuarto mes", "nota": "SIN MEDIR."},
    "dias_prueba": {"grupo": "cliente", "tipo": "escalar", "min": 0, "max": 60,
                    "paso": 1, "unidad": "dias", "etiqueta": "Dias de prueba gratis",
                    "nota": "El primer mes de cada alta no se cobra entero."},
    "impagos": {"grupo": "cliente", "tipo": "escalar", "min": 0.0, "max": 0.5,
                "paso": 0.005, "unidad": "%", "porcentaje": True,
                "etiqueta": "Recibos que no se cobran", "nota": "SIN MEDIR."},
    "mult_nueva": {"grupo": "cliente", "tipo": "escalar", "min": 1.0, "max": 8.0,
                   "paso": 0.1, "unidad": "x la asentada",
                   "etiqueta": "Soporte de una cuenta nueva",
                   "nota": "Los tres primeros meses preguntan mas."},
    # --- Tiempo ---
    "horas_mes": {"grupo": "tiempo", "tipo": "escalar", "min": 1, "max": 250,
                  "paso": 1, "unidad": "h/mes",
                  "etiqueta": "Horas al mes para vender y atender",
                  "nota": "Las que quedan despues de construir producto."},
    "horas_alta": {"grupo": "tiempo", "tipo": "escalar", "min": 0.1, "max": 40,
                   "paso": 0.5, "unidad": "h/alta",
                   "etiqueta": "Horas por alta (venta y puesta en marcha)",
                   "nota": "SIN MEDIR: el analisis solo cifra el onboarding."},
    "objetivo": {"grupo": "tiempo", "tipo": "escalar", "min": 0, "max": 100,
                 "paso": 1, "unidad": "altas/mes",
                 "etiqueta": "Altas que quieres cerrar al mes",
                 "nota": "Solo se cumplen las que caben en tus horas."},
    "crecimiento": {"grupo": "tiempo", "tipo": "escalar", "min": 0.0, "max": 0.5,
                    "paso": 0.01, "unidad": "%/mes", "porcentaje": True,
                    "etiqueta": "Crecimiento mensual del objetivo",
                    "nota": "Sin ads, es boca a boca."},
    "hora_soporte": {"grupo": "tiempo", "tipo": "escalar", "min": 0, "max": 200,
                     "paso": 1, "unidad": "€/hora",
                     "etiqueta": "Coste de una hora de soporte pagada",
                     "nota": "Solo aplica cuando el soporte NO lo haces tu."},
    # --- Por plan ---
    "precio": {"grupo": "planes", "tipo": "plan", "min": 0, "max": 2000, "paso": 1,
               "unidad": "€/mes", "etiqueta": "Precio mensual",
               "nota": "DATO: decision del 15/07/2026."},
    "mix": {"grupo": "planes", "tipo": "plan", "min": 0.0, "max": 1.0, "paso": 0.01,
            "unidad": "%", "porcentaje": True, "etiqueta": "Mezcla de clientes",
            "nota": "SIN MEDIR. Debe sumar 100 %."},
    "creditos": {"grupo": "planes", "tipo": "plan", "min": 0, "max": 100000, "paso": 25,
                 "unidad": "acciones/mes", "etiqueta": "Creditos de IA incluidos",
                 "nota": "Catalogo actual."},
    "uso": {"grupo": "planes", "tipo": "plan", "min": 0.0, "max": 1.0, "paso": 0.05,
            "unidad": "%", "porcentaje": True, "etiqueta": "Uso esperado del limite",
            "nota": "SUPUESTO conservador."},
    "interno": {"grupo": "planes", "tipo": "plan", "min": 0.0, "max": 1.0, "paso": 0.05,
                "unidad": "%", "porcentaje": True,
                "etiqueta": "Resuelve el cerebro interno",
                "nota": "Si baja del 40 %, el coste de IA se dispara."},
    "wa_util": {"grupo": "planes", "tipo": "plan", "min": 0, "max": 10000, "paso": 10,
                "unidad": "mensajes/mes", "etiqueta": "WhatsApp utility enviados",
                "nota": "SUPUESTO operativo."},
    "audio": {"grupo": "planes", "tipo": "plan", "min": 0, "max": 10000, "paso": 5,
              "unidad": "min/mes", "etiqueta": "Audio transcrito",
              "nota": "SUPUESTO operativo."},
    "docs": {"grupo": "planes", "tipo": "plan", "min": 0, "max": 10000, "paso": 5,
             "unidad": "docs/mes", "etiqueta": "Documentos procesados",
             "nota": "SUPUESTO operativo."},
    "docs_fuera": {"grupo": "planes", "tipo": "plan", "min": 0.0, "max": 1.0, "paso": 0.05,
                   "unidad": "%", "porcentaje": True,
                   "etiqueta": "Documentos que escalan fuera", "nota": "OCR local primero."},
    "almacen": {"grupo": "planes", "tipo": "plan", "min": 0.0, "max": 1000, "paso": 0.25,
                "unidad": "GB/cuenta", "etiqueta": "Almacenamiento",
                "nota": "SUPUESTO operativo."},
    "voz": {"grupo": "planes", "tipo": "plan", "min": 0, "max": 5000, "paso": 10,
            "unidad": "min/mes", "etiqueta": "Voz telefonica incluida",
            "nota": "Promesa Premium actual."},
    "soporte": {"grupo": "planes", "tipo": "plan", "min": 0, "max": 600, "paso": 1,
                "unidad": "min/cuenta/mes", "etiqueta": "Soporte de una cuenta asentada",
                "nota": "SIN MEDIR. Es la partida que rompe el margen."},
    "onboarding": {"grupo": "planes", "tipo": "plan", "min": 0, "max": 1200, "paso": 5,
                   "unidad": "min/cuenta", "etiqueta": "Onboarding inicial",
                   "nota": "Amortizado en 12 meses."},
    # --- Proveedores ---
    "eurusd": {"grupo": "proveedores", "tipo": "escalar", "min": 0.1, "max": 5.0,
               "paso": 0.0001, "unidad": "EUR/USD", "etiqueta": "EUR por USD",
               "nota": "ECB, 14/07/2026."},
    "stripe_pay": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 0.2,
                   "paso": 0.001, "unidad": "%", "porcentaje": True,
                   "etiqueta": "Stripe Payments", "nota": "Tarjeta EEE estandar."},
    "stripe_bill": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 0.2,
                    "paso": 0.001, "unidad": "%", "porcentaje": True,
                    "etiqueta": "Stripe Billing", "nota": "Facturacion por uso."},
    "stripe_fijo": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 5.0,
                    "paso": 0.01, "unidad": "€/transaccion",
                    "etiqueta": "Stripe fijo", "nota": "Una renovacion al mes."},
    "wa_precio": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 1.0,
                  "paso": 0.0001, "unidad": "€/mensaje",
                  "etiqueta": "WhatsApp utility Espana", "nota": "Meta / rate card."},
    "haiku": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 5.0,
              "paso": 0.001, "unidad": "USD/interaccion",
              "etiqueta": "Haiku 4.5 por interaccion", "nota": "8k entrada, 1,2k salida."},
    "qwen": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 5.0,
             "paso": 0.0001, "unidad": "USD/interaccion",
             "etiqueta": "Qwen3 32B por interaccion", "nota": "Mismo supuesto de tokens."},
    "peso_qwen": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 1.0,
                  "paso": 0.05, "unidad": "%", "porcentaje": True,
                  "etiqueta": "Peso de Qwen en el respaldo", "nota": "El resto va a Haiku."},
    "whisper": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 10.0,
                "paso": 0.001, "unidad": "USD/hora", "etiqueta": "Whisper Turbo",
                "nota": "Solo transcripcion."},
    "extraccion": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 5.0,
                   "paso": 0.001, "unidad": "€/documento",
                   "etiqueta": "Extraccion externa de documento",
                   "nota": "SUPUESTO: validar con corpus real."},
    "storage": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 5.0,
                "paso": 0.001, "unidad": "USD/GB-mes", "etiqueta": "Object storage",
                "nota": "Railway, sin egress."},
    "voz_min": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 5.0,
                "paso": 0.01, "unidad": "USD/min", "etiqueta": "Voz de agente",
                "nota": "Retell."},
    "voz_num": {"grupo": "proveedores", "tipo": "escalar", "min": 0.0, "max": 100.0,
                "paso": 0.5, "unidad": "USD/mes", "etiqueta": "Numero telefonico de voz",
                "nota": "Solo plan Premium."},
    # --- Canal ---
    "cac": {"grupo": "canal", "tipo": "escalar", "min": 0, "max": 5000, "paso": 10,
            "unidad": "€/cliente", "etiqueta": "Coste de captar un cliente",
            "nota": "SIN MEDIR."},
    "implantacion": {"grupo": "canal", "tipo": "escalar", "min": 0, "max": 2000,
                     "paso": 10, "unidad": "€/alta",
                     "etiqueta": "Cuota de implantacion", "nota": "PROPUESTA, sin aprobar."},
    "pct_implantacion": {"grupo": "canal", "tipo": "escalar", "min": 0.0, "max": 1.0,
                         "paso": 0.05, "unidad": "%", "porcentaje": True,
                         "etiqueta": "Altas que la pagan",
                         "nota": "A 0 % es como si no existiera."},
}


def coerce(key: str, raw) -> float | tuple | None:
    """Convierte y acota un valor del formulario. Devuelve None si no vale.

    Nunca lanza: un campo mal escrito se ignora y se queda el valor anterior, que
    es mejor que tumbar el guardado entero por una coma de mas.
    """
    spec = EDITABLE.get(key)
    if spec is None:
        return None
    if spec["tipo"] == "plan":
        valores = raw if isinstance(raw, (list, tuple)) else [raw]
        if len(valores) != len(PLANES):
            return None
        salida = []
        for item in valores:
            numero = _numero(item)
            if numero is None:
                return None
            salida.append(_clamp(numero, spec["min"], spec["max"]))
        return tuple(salida)
    numero = _numero(raw)
    if numero is None:
        return None
    return _clamp(numero, spec["min"], spec["max"])


def _numero(raw) -> float | None:
    if raw is None:
        return None
    texto = str(raw).strip().replace(",", ".")
    if not texto:
        return None
    try:
        valor = float(texto)
    except ValueError:
        return None
    if valor != valor or valor in (float("inf"), float("-inf")):
        return None
    return valor


def apply_saved(saved: dict | None) -> dict:
    """Mezcla los supuestos guardados sobre los de fabrica, validando cada uno.

    Lo que no este guardado sigue viniendo del valor por defecto: borrar una fila
    devuelve la cifra original sin tener que acordarse de cual era.
    """
    data = dict(ASSUMPTIONS)
    if not saved:
        return data
    for key, raw in saved.items():
        valor = coerce(key, raw)
        if valor is not None:
            data[key] = valor
    return data


def form_groups(a: dict) -> list[dict]:
    """El formulario, agrupado, con el valor actual y si esta tocado de fabrica."""
    grupos = []
    for clave, titulo, descripcion in GRUPOS:
        campos = []
        for key, spec in EDITABLE.items():
            if spec["grupo"] != clave:
                continue
            actual = a[key]
            defecto = ASSUMPTIONS[key]
            campos.append({
                "clave": key, "spec": spec, "valor": actual, "defecto": defecto,
                "tocado": tuple(actual) != tuple(defecto)
                if spec["tipo"] == "plan" else abs(float(actual) - float(defecto)) > 1e-12,
            })
        grupos.append({"clave": clave, "titulo": titulo, "descripcion": descripcion,
                       "campos": campos})
    return grupos


COST_LINES = (
    ("stripe", "Comisiones de Stripe"),
    ("whatsapp", "WhatsApp (plantillas)"),
    ("ia", "IA avanzada"),
    ("transcripcion", "Transcripcion de voz"),
    ("extraccion", "Extraccion de documentos"),
    ("almacenamiento", "Almacenamiento"),
    ("voz", "Voz telefonica"),
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def with_levers(overrides: dict[str, Any] | None = None,
                base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Devuelve los supuestos con las palancas del panel aplicadas y acotadas."""
    data = dict(base or ASSUMPTIONS)
    if not overrides:
        return data
    for key, (low, high) in LEVERS.items():
        raw = overrides.get(key)
        if raw is None or raw == "":
            continue
        try:
            value = _clamp(float(raw), low, high)
        except (TypeError, ValueError):
            continue
        if key == "soporte_medio":
            # Se mueve la media ponderada y los tres planes la siguen en proporcion,
            # para no perder que Premium consume casi cuatro veces mas que Autonomo.
            actual = weighted(data["soporte"], data["mix"])
            if actual > 0:
                factor = value / actual
                data["soporte"] = tuple(v * factor for v in data["soporte"])
            continue
        data[key] = value
    # Una cartera nueva siempre se va mas que una asentada; el panel solo mueve una.
    data["churn_nuevo"] = min(0.5, data["churn_maduro"] * 2)
    return data


def weighted(values, mix) -> float:
    return sum(v * m for v, m in zip(values, mix))


def cost_breakdown(a: dict[str, Any], i: int) -> dict[str, float]:
    """Coste de servir una cuenta del plan ``i``, linea a linea."""
    ia_unit = a["peso_qwen"] * a["qwen"] + (1 - a["peso_qwen"]) * a["haiku"]
    voz = (a["voz"][i] * a["voz_min"] + a["voz_num"]) * a["eurusd"] if a["voz"][i] else 0.0
    return {
        "stripe": a["precio"][i] * (a["stripe_pay"] + a["stripe_bill"]) + a["stripe_fijo"],
        "whatsapp": a["wa_util"][i] * a["wa_precio"],
        "ia": (a["creditos"][i] * a["uso"][i] * (1 - a["interno"][i])
               * ia_unit * a["eurusd"]),
        "transcripcion": a["audio"][i] / 60 * a["whisper"] * a["eurusd"],
        "extraccion": a["docs"][i] * a["docs_fuera"][i] * a["extraccion"],
        "almacenamiento": a["almacen"][i] * a["storage"] * a["eurusd"],
        "voz": voz,
    }


def per_plan(a: dict[str, Any]) -> list[dict[str, Any]]:
    """Economia de cada plan: coste, las dos contribuciones y sus margenes."""
    out = []
    for i, nombre in enumerate(PLANES):
        lineas = cost_breakdown(a, i)
        cogs = sum(lineas.values())
        precio = a["precio"][i]
        cobrado = precio * (1 - a["impagos"])
        servicio = (a["soporte"][i] / 60 * a["hora_soporte"]
                    + a["onboarding"][i] / 60 * a["hora_soporte"] / 12)
        caja = cobrado - cogs
        cargada = caja - servicio
        out.append({
            "plan": nombre,
            "precio": precio,
            "cobrado": cobrado,
            "lineas": lineas,
            "cogs": cogs,
            "margen_bruto": (precio - cogs) / precio if precio else 0.0,
            "servicio": servicio,
            "soporte_min": a["soporte"][i],
            "contribucion_caja": caja,
            "contribucion_cargada": cargada,
            "margen_caja": caja / precio if precio else 0.0,
            "margen_cargada": cargada / precio if precio else 0.0,
            "mix": a["mix"][i],
        })
    return out


def averages(a: dict[str, Any], planes: list[dict[str, Any]]) -> dict[str, float]:
    mix = a["mix"]
    return {
        "arpu": weighted([p["precio"] for p in planes], mix),
        "cogs": weighted([p["cogs"] for p in planes], mix),
        "servicio": weighted([p["servicio"] for p in planes], mix),
        "soporte_min": weighted([p["soporte_min"] for p in planes], mix),
        "contribucion_caja": weighted([p["contribucion_caja"] for p in planes], mix),
        "contribucion_cargada": weighted([p["contribucion_cargada"] for p in planes], mix),
    }


def lifetime(a: dict[str, Any]) -> float:
    """Vida media con bajas en dos tramos: los tres primeros meses se va mas gente.

    Es la suma de la supervivencia mes a mes. Con un churn plano del 4 % saldrian
    25 meses; con dos tramos, menos, que es como se comporta una cartera nueva.
    """
    s = 1 - a["churn_nuevo"]
    return 1 + s + s ** 2 + s ** 3 / a["churn_maduro"]


def structure(a: dict[str, Any]) -> dict[str, float]:
    base = a["plataforma"] + a["herramientas"] + a["gestoria"] + a["seguro"] + a["ads"]
    return {
        "estructura": base,
        "con_cuota": base + a["cuota_autonomos"],
        "total": base + a["cuota_autonomos"] + a["retirada"],
    }


def breakevens(a: dict[str, Any], med: dict[str, float]) -> list[dict[str, Any]]:
    """Los tres equilibrios, mas el cuarto con el soporte pagado a otra persona.

    Dar una sola cifra fue el error del modelo anterior: con 3.500 EUR de opex sin
    desglosar salian 120 cuentas y con 500 salian 17, que describe un negocio donde
    nadie cobra. Solo el tercero significa que esto da de comer.
    """
    s = structure(a)
    niveles = [
        ("Cubrir la estructura", s["estructura"], med["contribucion_caja"],
         "Servidores, herramientas, gestoria y seguro. No cobras nada.", False),
        ("Estructura y cuota de autonomos", s["con_cuota"], med["contribucion_caja"],
         "Dejas de poner dinero de tu bolsillo. Sigues sin cobrar.", False),
        ("Ademas te pagas la retirada", s["total"], med["contribucion_caja"],
         "El equilibrio de verdad: cuando esto te da de comer.", True),
        ("Con el soporte pagado a otra persona", s["total"], med["contribucion_cargada"],
         "Ya no atiendes tu: la contribucion baja y el equilibrio sube.", False),
    ]
    out = []
    for etiqueta, coste, base, nota, clave in niveles:
        cuentas = math.ceil(coste / base) if base > 0 else None
        out.append({
            "nivel": etiqueta, "coste": coste, "contribucion": base,
            "cuentas": cuentas, "nota": nota, "clave": clave,
            "ingreso": (cuentas * med["arpu"] * (1 - a["impagos"])) if cuentas else None,
        })
    return out


def capacity(a: dict[str, Any], med: dict[str, float]) -> dict[str, Any]:
    """Cuantas cuentas caben en las horas del founder, que es el limite real."""
    horas_cuenta = med["soporte_min"] / 60
    techo = math.floor(a["horas_mes"] / horas_cuenta) if horas_cuenta > 0 else None
    practico = math.floor(a["horas_mes"] * 0.7 / horas_cuenta) if horas_cuenta > 0 else None
    return {
        "horas_mes": a["horas_mes"],
        "soporte_min": med["soporte_min"],
        "horas_por_cuenta": horas_cuenta,
        "techo": techo,
        "practico": practico,
        "horas_alta": a["horas_alta"],
    }


def ramp(a: dict[str, Any], med: dict[str, float], meses: int = 36) -> dict[str, Any]:
    """Caja mes a mes con cohortes por edad y las altas limitadas por las horas.

    Las altas no son una constante: salen de las horas que quedan tras atender a la
    cartera, asi que la rampa se frena sola cuando el soporte ocupa el mes. Esa es la
    curva real de un negocio de una persona, y no aparecia en el modelo anterior.
    """
    min_madura = med["soporte_min"]
    min_nueva = min_madura * a["mult_nueva"]
    salida = structure(a)["total"]
    c = d = e = f = 0.0
    caja = a["caja_inicial"]
    filas: list[dict[str, Any]] = []
    primero = ahogo = None
    minima = None
    for mes in range(1, meses + 1):
        previo = ((c + d + e) * min_nueva + f * min_madura) / 60 if mes > 1 else 0.0
        libres = max(0.0, a["horas_mes"] - previo)
        objetivo = round(a["objetivo"] * (1 + a["crecimiento"]) ** (mes - 1))
        altas = max(0, min(objetivo, math.floor(libres / a["horas_alta"])
                           if a["horas_alta"] > 0 else 0))
        c, d, e, f = (
            float(altas),
            c * (1 - a["churn_nuevo"]) if mes > 1 else 0.0,
            d * (1 - a["churn_nuevo"]) if mes > 1 else 0.0,
            (f + e) * (1 - a["churn_maduro"]) if mes > 1 else 0.0,
        )
        cuentas = c + d + e + f
        horas = altas * a["horas_alta"] + ((c + d + e) * min_nueva + f * min_madura) / 60
        # El alta no paga los dias de prueba de su primer mes.
        facturado = cuentas * med["arpu"] - altas * med["arpu"] * a["dias_prueba"] / 30
        cobrado = (facturado * (1 - a["impagos"])
                   + altas * a["implantacion"] * a["pct_implantacion"])
        resultado = cobrado - cuentas * med["cogs"] - salida
        caja += resultado
        if primero is None and resultado > 0:
            primero = mes
        if ahogo is None and horas >= a["horas_mes"] * 0.7:
            ahogo = mes
        minima = caja if minima is None else min(minima, caja)
        filas.append({
            "mes": mes, "altas": altas, "objetivo": objetivo, "frenado": altas < objetivo,
            "cuentas": cuentas, "horas": horas, "facturado": facturado,
            "cobrado": cobrado, "resultado": resultado, "caja": caja,
        })
    return {
        "filas": filas, "mes_positivo": primero, "mes_ahogo": ahogo,
        "caja_minima": minima, "cuentas_final": filas[-1]["cuentas"] if filas else 0.0,
        "salida_mensual": salida, "financiable": (minima or 0) >= 0
        or abs(minima or 0) <= a["caja_inicial"],
    }


def build_report(overrides: dict[str, Any] | None = None,
                 observed: dict[str, Any] | None = None,
                 saved: dict[str, Any] | None = None) -> dict[str, Any]:
    """Informe completo: supuestos aplicados, economia por plan, equilibrios y caja.

    ``observed`` son las cifras reales del panel. No sustituyen al supuesto: se
    ponen al lado, con la desviacion, porque esa diferencia es lo que hay que medir.
    """
    # Orden: valores de fabrica, encima lo guardado, y encima las palancas de la
    # URL. Asi mover un deslizador no pisa lo que el founder dejo guardado.
    a = with_levers(overrides, apply_saved(saved))
    planes = per_plan(a)
    med = averages(a, planes)
    vida = lifetime(a)
    rep: dict[str, Any] = {
        "assumptions": a,
        "planes": planes,
        "medias": med,
        "estructura": structure(a),
        "equilibrios": breakevens(a, med),
        "capacidad": capacity(a, med),
        "rampa": ramp(a, med),
        "vida_media": vida,
        "ltv_caja": med["contribucion_caja"] * vida,
        "ltv_cargada": med["contribucion_cargada"] * vida,
        "ltv_cac": (med["contribucion_caja"] * vida / a["cac"]) if a["cac"] else None,
        "payback": (a["cac"] / med["contribucion_caja"]
                    if med["contribucion_caja"] > 0 else None),
        "lineas": COST_LINES,
        "medias_lineas": {
            clave: weighted([pl["lineas"][clave] for pl in planes], a["mix"])
            for clave, _ in COST_LINES
        },
    }
    equilibrio = next((n for n in rep["equilibrios"] if n["clave"]), None)
    cuentas_eq = equilibrio["cuentas"] if equilibrio else None
    horas_eq = (cuentas_eq * med["soporte_min"] / 60) if cuentas_eq else 0.0
    libres = a["horas_mes"] - horas_eq
    rep["cabe_en_horas"] = {
        "cuentas": cuentas_eq, "horas": horas_eq, "libres": libres,
        "altas_posibles": (math.floor(max(0.0, libres) / a["horas_alta"])
                           if a["horas_alta"] > 0 else 0),
        "estado": "no" if libres <= 0 else ("justo" if libres < a["horas_mes"] * 0.3
                                            else "si"),
    }
    rep["observado"] = _compare(rep, observed or {})
    return rep


def _compare(rep: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    """Pone dato y supuesto uno al lado del otro, sin dejar que uno tape al otro."""
    med = rep["medias"]
    cuentas = observed.get("paying_accounts") or 0
    mrr = observed.get("mrr") or 0.0
    coste = observed.get("observed_cost_eur")
    filas = []

    def fila(etiqueta, real, supuesto, unidad, nota):
        desvio = None
        if real is not None and supuesto:
            desvio = (real - supuesto) / supuesto
        filas.append({"etiqueta": etiqueta, "real": real, "supuesto": supuesto,
                      "unidad": unidad, "desvio": desvio, "nota": nota})

    fila("Cuota media por cuenta", (mrr / cuentas) if cuentas else None, med["arpu"],
         "€/mes", "Ingreso comprometido entre cuentas de pago.")
    fila("Coste por cuenta", (coste / cuentas) if (coste and cuentas) else None,
         med["cogs"], "€/mes",
         "Del libro de costes. Solo cuenta si hay facturas cargadas.")
    fila("Contribucion por cuenta",
         ((mrr - coste) / cuentas) if (coste is not None and cuentas) else None,
         med["contribucion_caja"], "€/mes",
         "Ingreso menos coste observado, antes de impuestos.")
    fila("Cuentas de pago", float(cuentas) if cuentas else None,
         float(rep["cabe_en_horas"]["cuentas"] or 0) or None, "cuentas",
         "Frente a las que hacen falta para el equilibrio de verdad.")
    hay = any(f["real"] is not None for f in filas)
    return {
        "filas": filas,
        "hay_datos": hay,
        "cuentas": cuentas,
        "mrr": mrr,
        "aviso": ("Sin cuentas de pago todavia: todo el modelo es un escenario."
                  if not cuentas else
                  "Las columnas reales salen del libro de costes y de las "
                  "suscripciones; el supuesto se deja al lado a proposito."),
    }
