"""Catálogos por oficio y el aviso del tipo reducido en obras de vivienda.

Dos cosas que van juntas. La primera es práctica: un fontanero factura casi
siempre lo mismo, así que en la puesta en marcha se carga su catálogo y a partir
de ahí facturar es elegir de una lista con el IVA ya puesto, en vez de teclearlo
cada vez.

La segunda es fiscal y depende de la primera. El tipo reducido del 10% en obras
de renovación y reparación de vivienda decae si el material que aporta quien
ejecuta la obra supera el **40% de la base imponible** (art. 91.Uno.2.10º LIVA):
entonces la operación tributa entera al 21%. Es la equivocación más fácil de
cometer en reformas, y solo se puede avisar si cada línea dice si es material o
mano de obra. Por eso el catálogo lo marca y la factura lo conserva.

Noesis **avisa, no decide**: no cambia tipos ni bloquea la emisión. Las otras
condiciones del reducido —vivienda de particular, construcción terminada hace
más de dos años— no constan en el sistema y las conoce el autónomo, así que la
elección final es suya. Los precios son orientativos: se ajustan con el cliente.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

# Límite de material del tipo reducido (art. 91.Uno.2.10º LIVA).
REDUCED_RATE_MATERIAL_LIMIT = Decimal("40")
REDUCED_RATE = 10


# Cada entrada: (nombre, tipo, precio orientativo, IVA sugerido, unidad).
# El IVA sugerido es el habitual del oficio; el autónomo lo cambia por operación.
TRADE_CATALOGS: dict[str, dict] = {
    "fontaneria": {
        "label": "Fontanería",
        "items": (
            ("Mano de obra fontanería", "servicio", 35, 21, "hora"),
            ("Desplazamiento", "servicio", 25, 21, "servicio"),
            ("Desatasco", "servicio", 90, 21, "servicio"),
            ("Reparación de fuga", "servicio", 80, 21, "servicio"),
            ("Cambio de grifo", "servicio", 60, 21, "servicio"),
            ("Sustitución de termo eléctrico", "servicio", 120, 21, "servicio"),
            ("Urgencia fuera de horario", "servicio", 60, 21, "servicio"),
            ("Grifería", "producto", 0, 21, "unidad"),
            ("Tubería y accesorios", "producto", 0, 21, "unidad"),
            ("Sanitario", "producto", 0, 21, "unidad"),
        ),
    },
    "electricidad": {
        "label": "Electricidad",
        "items": (
            ("Mano de obra electricidad", "servicio", 38, 21, "hora"),
            ("Desplazamiento", "servicio", 25, 21, "servicio"),
            ("Localización de avería", "servicio", 70, 21, "servicio"),
            ("Cambio de cuadro eléctrico", "servicio", 250, 21, "servicio"),
            ("Instalación de punto de luz", "servicio", 45, 21, "unidad"),
            ("Boletín eléctrico", "servicio", 120, 21, "documento"),
            ("Urgencia fuera de horario", "servicio", 60, 21, "servicio"),
            ("Material eléctrico", "producto", 0, 21, "unidad"),
            ("Luminaria", "producto", 0, 21, "unidad"),
        ),
    },
    "reformas": {
        "label": "Reformas y albañilería",
        "items": (
            ("Mano de obra reforma", "servicio", 32, REDUCED_RATE, "hora"),
            ("Reforma de baño (mano de obra)", "servicio", 0, REDUCED_RATE, "obra"),
            ("Reforma de cocina (mano de obra)", "servicio", 0, REDUCED_RATE, "obra"),
            ("Alicatado y solado", "servicio", 28, REDUCED_RATE, "m2"),
            ("Pintura de vivienda", "servicio", 9, REDUCED_RATE, "m2"),
            ("Demolición y retirada de escombro", "servicio", 0, REDUCED_RATE, "obra"),
            ("Material de obra", "producto", 0, 21, "unidad"),
            ("Azulejo y pavimento", "producto", 0, 21, "m2"),
            ("Sanitarios y mobiliario", "producto", 0, 21, "unidad"),
        ),
    },
    "limpieza": {
        "label": "Limpieza",
        "items": (
            ("Limpieza por horas", "servicio", 18, 21, "hora"),
            ("Limpieza de fin de obra", "servicio", 0, 21, "servicio"),
            ("Limpieza de comunidad", "servicio", 0, 21, "mes"),
            ("Limpieza de cristales", "servicio", 0, 21, "servicio"),
            ("Producto de limpieza", "producto", 0, 21, "unidad"),
        ),
    },
    "jardineria": {
        "label": "Jardinería",
        "items": (
            ("Mano de obra jardinería", "servicio", 28, 21, "hora"),
            ("Mantenimiento mensual de jardín", "servicio", 0, 21, "mes"),
            ("Poda", "servicio", 0, 21, "servicio"),
            ("Siega de césped", "servicio", 0, 21, "servicio"),
            ("Retirada de restos vegetales", "servicio", 0, 21, "servicio"),
            ("Planta y sustrato", "producto", 0, 21, "unidad"),
        ),
    },
}


def available_trades() -> list[dict]:
    """Oficios con catálogo listo, para ofrecerlos en la puesta en marcha."""
    return [
        {"key": key, "label": data["label"], "items": len(data["items"])}
        for key, data in TRADE_CATALOGS.items()
    ]


def catalog_for(trade: str) -> tuple[dict, ...]:
    """Devuelve el catálogo de un oficio como diccionarios listos para guardar."""
    data = TRADE_CATALOGS.get((trade or "").strip().lower())
    if not data:
        return ()
    return tuple(
        {
            "name": name,
            "kind": kind,
            "price": price,
            "vat_rate": vat_rate,
            "unit": unit,
            "category": data["label"],
        }
        for name, kind, price, vat_rate, unit in data["items"]
    )


def load_catalog(business_id: int, trade: str) -> dict:
    """Carga el catálogo del oficio sin duplicar lo que el negocio ya tenga."""
    from . import db

    items = catalog_for(trade)
    if not items:
        raise ValueError("Ese oficio no tiene catálogo preparado.")
    existing = {
        (product["name"] or "").strip().lower()
        for product in db.list_products(business_id)
    }
    created = []
    for item in items:
        if item["name"].strip().lower() in existing:
            continue
        created.append(db.add_product(
            item["name"], kind=item["kind"], price=item["price"],
            vat_rate=item["vat_rate"], unit=item["unit"],
            category=item["category"], business_id=business_id,
        ))
    return {
        "trade": trade,
        "created": len(created),
        "skipped": len(items) - len(created),
        "products": created,
    }


def _decimal(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def material_share(lines) -> Decimal:
    """Porcentaje de la base imponible que aporta el material."""
    base = sum((_decimal(line.get("base")) for line in lines), Decimal("0"))
    if base <= 0:
        return Decimal("0")
    material = sum(
        (
            _decimal(line.get("base")) for line in lines
            if (line.get("kind") or "servicio") == "producto"
        ),
        Decimal("0"),
    )
    return (material / base * 100).quantize(Decimal("0.1"))


def reduced_rate_warning(lines) -> str | None:
    """Avisa si el material rompe el tipo reducido; nunca cambia la factura.

    Devuelve ``None`` cuando no hay nada que advertir: sin líneas al 10%, la
    regla no aplica y no se molesta a nadie.
    """
    lines = list(lines or [])
    if not any(_decimal(line.get("vat_rate")) == REDUCED_RATE for line in lines):
        return None
    share = material_share(lines)
    if share <= REDUCED_RATE_MATERIAL_LIMIT:
        return None
    return (
        f"El material es el {float(share):g}% de la base y supera el "
        f"{float(REDUCED_RATE_MATERIAL_LIMIT):g}% que admite el tipo reducido. "
        "Si es una obra de renovación en vivienda, con ese reparto tributa "
        "entera al 21%, no al 10%. Revísalo con tu asesoría antes de emitirla; "
        "no he cambiado ningún tipo."
    )
