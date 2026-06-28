"""Las acciones que Noesis sabe ejecutar (multi-negocio).

Cada herramienta tiene (1) un esquema que se le da a Claude para que sepa cuándo
y cómo usarla, y (2) una función Python que la ejecuta contra la base de datos.

Las acciones SIEMPRE reciben el `business_id` del negocio sobre el que operan, así
las mismas herramientas valen para el chat web (cualquier negocio), el WhatsApp y
el CLI. El cerebro (agente o NLU local) decide cuál usar; aquí solo se ejecutan.
"""

from __future__ import annotations

import json

from . import db
from .adapters import invoicing

_provider = invoicing.get_provider()

DEFAULT_BUSINESS_ID = db.DEFAULT_BUSINESS_ID


TOOLS: list[dict] = [
    {
        "name": "agendar_trabajo",
        "description": (
            "Agenda un trabajo/visita para un cliente. Crea el cliente si no existe. "
            "Úsala cuando el autónomo diga 'agenda a Marta el jueves' o similar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cliente": {"type": "string"},
                "descripcion": {"type": "string"},
                "fecha_hora": {"type": "string",
                               "description": "ISO (YYYY-MM-DD o YYYY-MM-DDTHH:MM)."},
                "zona": {"type": "string"},
                "precio_estimado": {"type": "number"},
            },
            "required": ["cliente", "descripcion", "fecha_hora"],
        },
    },
    {
        "name": "ver_agenda",
        "description": "Muestra los trabajos programados para un día concreto.",
        "input_schema": {
            "type": "object",
            "properties": {"fecha": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["fecha"],
        },
    },
    {
        "name": "crear_factura",
        "description": (
            "Prepara una factura en BORRADOR con un concepto y un importe BASE (sin "
            "IVA). Calcula IVA y total. NO la envía. Crea el cliente si no existe."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cliente": {"type": "string"},
                "concepto": {"type": "string"},
                "base": {"type": "number", "description": "Importe SIN IVA."},
                "iva": {"type": "number", "description": "Tipo de IVA (21, 10 o 4). Por defecto el del negocio."},
                "irpf": {"type": "number", "description": "Retención de IRPF (ej. 15 o 7). Por defecto el del negocio."},
            },
            "required": ["cliente", "concepto", "base"],
        },
    },
    {
        "name": "enviar_factura",
        "description": "Emite y envía una factura borrador (le da número y vencimiento).",
        "input_schema": {
            "type": "object",
            "properties": {"factura_id": {"type": "integer"}},
            "required": ["factura_id"],
        },
    },
    {
        "name": "registrar_pago",
        "description": "Marca una factura como cobrada.",
        "input_schema": {
            "type": "object",
            "properties": {"factura_id": {"type": "integer"}},
            "required": ["factura_id"],
        },
    },
    {
        "name": "ver_cobros_pendientes",
        "description": "Lista facturas enviadas y no cobradas, con días de retraso y total.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "resumen_negocio",
        "description": "Cifras del mes: facturado, cobrado, pendiente, IVA, gastos, beneficio.",
        "input_schema": {
            "type": "object",
            "properties": {"mes": {"type": "string", "description": "YYYY-MM"}},
        },
    },
    {
        "name": "registrar_gasto",
        "description": "Registra un gasto del negocio (ej. 'gasolina 45 euros').",
        "input_schema": {
            "type": "object",
            "properties": {
                "concepto": {"type": "string"},
                "importe": {"type": "number"},
                "iva": {"type": "number"},
                "categoria": {"type": "string"},
            },
            "required": ["concepto", "importe"],
        },
    },
    {
        "name": "listar_clientes",
        "description": "Lista los clientes guardados.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


# --------------------------------------------------------------------------- #
# Implementaciones (todas reciben business_id).
# --------------------------------------------------------------------------- #
def _agendar_trabajo(business_id, cliente, descripcion, fecha_hora, zona=None,
                     precio_estimado=None):
    c = db.get_or_create_client(cliente, business_id=business_id, zone=zona)
    job = db.add_job(c["id"], descripcion, scheduled_for=fecha_hora,
                     zone=zona or c.get("zone"), price_estimate=precio_estimado,
                     business_id=business_id)
    return {"ok": True, "trabajo": job, "cliente": c}


def _ver_agenda(business_id, fecha):
    jobs = db.jobs_for_date(fecha, business_id)
    return {"fecha": fecha, "n": len(jobs), "trabajos": jobs}


def _crear_factura(business_id, cliente, concepto, base, iva=None, irpf=None):
    biz = db.get_business(business_id) or {}
    c = db.get_or_create_client(cliente, business_id=business_id)
    rate = biz.get("default_vat", 21) if iva is None else iva
    irpf_rate = biz.get("default_irpf", 0) if irpf is None else irpf
    inv = db.add_invoice(c["id"], concepto, base, vat_rate=rate,
                         irpf_rate=irpf_rate, business_id=business_id)
    msg = (f"Borrador listo: {inv['total']:.2f} € (base {inv['base']:.2f} "
           f"+ IVA {inv['vat_amount']:.2f}")
    if inv["irpf_amount"]:
        msg += f" − IRPF {inv['irpf_amount']:.2f}"
    return {"ok": True, "factura": inv, "mensaje": msg + ")."}


def _enviar_factura(business_id, factura_id):
    inv = db.get_invoice(factura_id)
    # Aislamiento: solo se puede operar sobre facturas del propio negocio.
    if not inv or inv.get("business_id") != business_id:
        return {"ok": False, "error": "No existe esa factura."}
    client = db.get_client(inv["client_id"])
    issued = _provider.issue(inv, client or {})
    inv = db.mark_invoice_sent(factura_id, issued["number"], issued["due_date"],
                               business_id=business_id)
    return {"ok": True, "factura": inv, "emision": issued}


def _registrar_pago(business_id, factura_id):
    inv = db.get_invoice(factura_id)
    # Aislamiento: solo se puede operar sobre facturas del propio negocio.
    if not inv or inv.get("business_id") != business_id:
        return {"ok": False, "error": "No existe esa factura."}
    return {"ok": True, "factura": db.mark_invoice_paid(factura_id, business_id)}


def _ver_cobros_pendientes(business_id):
    pend = db.pending_payments(business_id)
    total = round(sum(p["total"] for p in pend), 2)
    return {"n": len(pend), "total_pendiente": total, "facturas": pend}


def _resumen_negocio(business_id, mes=None):
    return db.month_billing(mes, business_id)


def _registrar_gasto(business_id, concepto, importe, iva=None, categoria=None):
    return {"ok": True, "gasto": db.add_expense(concepto, importe, vat_rate=iva,
                                                category=categoria, business_id=business_id)}


def _listar_clientes(business_id):
    return {"clientes": db.list_clients(business_id)}


_DISPATCH = {
    "agendar_trabajo": _agendar_trabajo,
    "ver_agenda": _ver_agenda,
    "crear_factura": _crear_factura,
    "enviar_factura": _enviar_factura,
    "registrar_pago": _registrar_pago,
    "ver_cobros_pendientes": _ver_cobros_pendientes,
    "resumen_negocio": _resumen_negocio,
    "registrar_gasto": _registrar_gasto,
    "listar_clientes": _listar_clientes,
}


def run_tool(name: str, tool_input: dict, business_id: int = DEFAULT_BUSINESS_ID) -> str:
    """Ejecuta una herramienta para un negocio y devuelve JSON (para Claude/NLU)."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"Herramienta desconocida: {name}"})
    try:
        result = fn(business_id=business_id, **tool_input)
    except TypeError as e:
        result = {"error": f"Parámetros inválidos para {name}: {e}"}
    except Exception as e:  # noqa: BLE001
        result = {"error": f"Fallo ejecutando {name}: {e}"}
    return json.dumps(result, ensure_ascii=False, default=str)
