"""Las acciones que Bynoesis sabe ejecutar (multi-negocio).

Cada herramienta tiene (1) un esquema que se le da a Claude para que sepa cuándo
y cómo usarla, y (2) una función Python que la ejecuta contra la base de datos.

Las acciones SIEMPRE reciben el `business_id` del negocio sobre el que operan, así
las mismas herramientas valen para el chat web (cualquier negocio), el WhatsApp y
el CLI. El cerebro (agente o NLU local) decide cuál usar; aquí solo se ejecutan.
"""

from __future__ import annotations

import json
import re
import logging
from contextvars import ContextVar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from . import config, db
from .adapters import billing as billing_adapter
from .adapters import invoicing

_provider = invoicing.get_provider()
log = logging.getLogger("noesis.tools")

# Recibos de ejecución del turno: contexto aislado, nunca texto inventado por IA.
execution_receipts: ContextVar[list | None] = ContextVar("execution_receipts", default=None)


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
        "description": ("Muestra los trabajos programados para un día concreto o, con "
                        "«hasta», para varios días seguidos (máximo 31)."),
        "input_schema": {
            "type": "object",
            "properties": {"fecha": {"type": "string", "description": "YYYY-MM-DD"},
                           "hasta": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["fecha"],
        },
    },
    {
        "name": "ver_gastos",
        "description": "Lista los gastos apuntados entre dos fechas (por defecto, este mes).",
        "input_schema": {
            "type": "object",
            "properties": {"desde": {"type": "string", "description": "YYYY-MM-DD"},
                           "hasta": {"type": "string", "description": "YYYY-MM-DD"}},
        },
    },
    {
        "name": "crear_factura",
        "description": (
            "Prepara una factura en BORRADOR. Puede ser completa F1 o simplificada "
            "F2 (ticket de venta). NO la emite ni la envía. Reutiliza el cliente "
            "habitual si la referencia es inequívoca."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cliente": {"type": "string"},
                "concepto": {"type": "string"},
                "base": {"type": "number", "description": "Importe SIN IVA."},
                "iva": {"type": "number", "description": "Tipo de IVA (21, 10 o 4). Por defecto el del negocio."},
                "irpf": {"type": "number", "description": "Retención de IRPF (ej. 15 o 7). Por defecto el del negocio."},
                "tipo_factura": {"type": "string", "enum": ["F1", "F2"]},
                "importe_incluye_iva": {"type": "boolean"},
                "lineas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit_price": {"type": "number"},
                            "discount_rate": {"type": "number"},
                            "vat_rate": {"type": "number"},
                        },
                        "required": ["description", "quantity", "unit_price"],
                    },
                },
            },
            "required": ["concepto", "base"],
        },
    },
    {
        "name": "preparar_factura_trabajo",
        "description": (
            "Recupera el cierre de un trabajo y prepara su factura sin duplicarla. "
            "El trabajo debe estar cerrado y tener un importe."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"trabajo_id": {"type": "integer"}},
            "required": ["trabajo_id"],
        },
    },
    {
        "name": "crear_presupuesto",
        "description": (
            "Prepara un PRESUPUESTO para un cliente con un concepto e importe BASE "
            "(sin IVA). No es una factura: es una oferta que el cliente puede aceptar. "
            "Al aceptarse se convierte en factura. Crea el cliente si no existe."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cliente": {"type": "string"},
                "concepto": {"type": "string"},
                "base": {"type": "number", "description": "Importe SIN IVA."},
                "iva": {"type": "number"},
                "irpf": {"type": "number"},
                "validez_dias": {"type": "integer"},
                "notas": {"type": "string"},
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
        "description": ("Lista facturas enviadas y no cobradas, con días de retraso y "
                        "total. Con «cliente», solo las de ese cliente."),
        "input_schema": {"type": "object",
                         "properties": {"cliente": {"type": "string"}}},
    },
    {
        "name": "resumen_negocio",
        "description": ("Cifras del mes (o del año con «anio»): facturado, cobrado, "
                        "pendiente, IVA, gastos, beneficio."),
        "input_schema": {
            "type": "object",
            "properties": {"mes": {"type": "string", "description": "YYYY-MM"},
                           "anio": {"type": "integer"}},
        },
    },
    {
        "name": "ver_impuestos",
        "description": (
            "IVA del modelo 303 e IRPF del modelo 130 de un trimestre. Cifras de "
            "apoyo calculadas con lo registrado; la gestoría valida la presentación."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "trimestre": {"type": "integer", "description": "1 a 4"},
                "anio": {"type": "integer", "description": "Año; por defecto el actual"},
            },
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
                "proyecto_id": {
                    "type": "integer",
                    "description": "Proyecto al que pertenece, si el usuario lo indica.",
                },
            },
            "required": ["concepto", "importe"],
        },
    },
    {
        "name": "entregar_factura",
        "description": ("Entrega al cliente una factura YA EMITIDA por correo o "
                        "WhatsApp. No emite: para eso está enviar_factura."),
        "input_schema": {
            "type": "object",
            "properties": {
                "factura_id": {"type": "integer"},
                "canal": {"type": "string", "enum": ["auto", "email", "whatsapp"]},
            },
            "required": ["factura_id"],
        },
    },
    {
        "name": "crear_cliente",
        "description": "Crea o reutiliza un cliente por su nombre, sin generar documentos.",
        "input_schema": {
            "type": "object",
            "properties": {"nombre": {"type": "string"},
                           "telefono": {"type": "string"},
                           "email": {"type": "string"},
                           "nif": {"type": "string"},
                           "direccion": {"type": "string"}},
            "required": ["nombre"],
        },
    },
    {
        "name": "actualizar_cliente",
        "description": ("Añade o corrige el teléfono, correo, NIF o dirección de un "
                        "cliente que ya existe. No cambia su nombre ni sus facturas."),
        "input_schema": {
            "type": "object",
            "properties": {"cliente": {"type": "string"},
                           "telefono": {"type": "string"},
                           "email": {"type": "string"},
                           "nif": {"type": "string"},
                           "direccion": {"type": "string"}},
            "required": ["cliente"],
        },
    },
    {
        "name": "crear_proveedor",
        "description": "Crea o reutiliza un proveedor por su nombre, sin registrar gastos.",
        "input_schema": {
            "type": "object",
            "properties": {"nombre": {"type": "string"}},
            "required": ["nombre"],
        },
    },
    {
        "name": "listar_clientes",
        "description": "Lista los clientes guardados.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_presupuestos",
        "description": "Lista los presupuestos con su estado (borrador, enviado, aceptado, rechazado).",
        "input_schema": {"type": "object", "properties": {"cliente": {"type": "string"}}},
    },
    {
        "name": "terminar_trabajo",
        "description": ("Marca como hecho el trabajo agendado de un cliente. No factura: "
                        "solo cambia el estado del trabajo."),
        "input_schema": {"type": "object", "properties": {"cliente": {"type": "string"}},
                         "required": ["cliente"]},
    },
    {
        "name": "ver_cliente",
        "description": ("Ficha de un cliente: teléfono, correo, NIF, dirección y sus "
                        "últimas facturas con lo pendiente de cobro."),
        "input_schema": {"type": "object", "properties": {
            "cliente": {"type": "string"},
            "dato": {"type": "string", "description": "telefono|email|nif|direccion|facturas"}},
            "required": ["cliente"]},
    },
    {
        "name": "ver_perfil_cliente",
        "description": (
            "Explica el historial observado y las preferencias confirmadas de un "
            "cliente: pagos, presupuestos, actividad y margen directo conocido."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"cliente": {"type": "string"}},
            "required": ["cliente"],
        },
    },
    {
        "name": "ver_proyectos",
        "description": (
            "Lista los proyectos con presupuesto, avance, horas, coste y margen. "
            "Úsala antes de responder sobre una obra o instalación."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_proyecto",
        "description": (
            "Muestra el detalle real de un proyecto: trabajos, tareas, equipo, "
            "fichajes, gastos, documentos y margen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"proyecto_id": {"type": "integer"}},
            "required": ["proyecto_id"],
        },
    },
    {
        "name": "crear_proyecto",
        "description": (
            "Crea un proyecto de trabajo con presupuesto y horas previstas. "
            "No factura ni mueve dinero."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string"},
                "presupuesto": {"type": "number"},
                "cliente": {"type": "string"},
                "ubicacion": {"type": "string"},
                "horas_previstas": {"type": "number"},
            },
            "required": ["nombre", "presupuesto"],
        },
    },
    {
        "name": "crear_tarea_proyecto",
        "description": (
            "Añade una tarea o comprobación a un proyecto existente. Si no sabes "
            "el id, consulta primero ver_proyectos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "proyecto_id": {"type": "integer"},
                "titulo": {"type": "string"},
                "trabajador_id": {"type": "integer"},
                "trabajo_id": {"type": "integer"},
                "fecha_limite": {"type": "string"},
                "tipo": {"type": "string", "enum": ["tarea", "checklist", "incidencia"]},
                "nota": {"type": "string"},
            },
            "required": ["proyecto_id", "titulo"],
        },
    },
    {
        "name": "ver_equipo",
        "description": "Lista el equipo y su estado de jornada de hoy.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_documentos_pendientes",
        "description": "Lista documentos cuya clasificación o revisión está pendiente.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_solicitudes_gestoria",
        "description": "Lista las solicitudes abiertas entre el negocio y su gestoría.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_control_noesis",
        "description": "Consulta qué puede hacer Bynoesis solo y qué debe confirmar el usuario.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


# --------------------------------------------------------------------------- #
# Implementaciones (todas reciben business_id).
# --------------------------------------------------------------------------- #
def _reviewed_client(business_id, cliente, cliente_id=None, **kwargs):
    if cliente_id is None:
        return db.get_or_create_client(cliente, business_id=business_id, **kwargs)
    client = db.get_client(cliente_id, business_id)
    if not client or client["name"] != cliente:
        raise ValueError("La ficha del cliente ha cambiado. Revisa la propuesta otra vez.")
    return client


def _agendar_trabajo(business_id, cliente, descripcion, fecha_hora, zona=None,
                     precio_estimado=None, cliente_id=None):
    c = _reviewed_client(business_id, cliente, cliente_id, zone=zona)
    job = db.add_job(c["id"], descripcion, scheduled_for=fecha_hora,
                     zone=zona or c.get("zone"), price_estimate=precio_estimado,
                     business_id=business_id)
    return {"ok": True, "trabajo": job, "cliente": c}


def ficha_para_alta(nombre: str, business_id: int) -> dict | None:
    """La ficha que ya es este cliente, para no duplicarla al darlo de alta.

    Primero la del mismo nombre exacto (sin mayúsculas ni tildes); si no, la que
    encaje sin ambigüedad. Si encajan varias —«Prueba Claude» con «Lucia Prueba
    Claude» y «Pedro Prueba Claude»— ninguna es este cliente: antes el alta se
    bloqueaba pidiendo «el nombre completo» cuando ya lo era.
    """
    from .nlu import _norm
    buscado = _norm(nombre or "").strip()
    for ficha in db.list_clients(business_id):
        if _norm(ficha.get("name") or "").strip() == buscado:
            return ficha
    try:
        return db.resolve_client_reference(nombre, business_id)
    except ValueError:
        return None


def _crear_cliente(business_id, nombre, telefono=None, email=None, nif=None,
                  direccion=None):
    datos, avisos = datos_de_cliente_validos(
        {"telefono": telefono, "email": email, "nif": nif, "direccion": direccion})
    before = ficha_para_alta(nombre, business_id)
    client = before or db.add_client(nombre, business_id=business_id, **datos)
    nuevos = {k: v for k, v in datos.items() if v and before and not before.get(k)}
    if nuevos:
        # La ficha existía sin esos datos y ahora se han dicho: se completa en
        # vez de perderlos. Un dato ya guardado no se pisa desde una frase.
        db.update_client(client["id"], business_id=business_id, **nuevos)
        client = db.get_client(client["id"], business_id) or client
    # Los borradores a medias que esperaban a este cliente por su nombre quedan
    # enlazados en el mismo paso: «factura para Jordi, ya te paso los datos» +
    # «crea el cliente Jordi» no debe obligar a volver a pedir la factura.
    try:
        enlazadas = db.link_partial_invoices_to_client(business_id, client)
    except ValueError:
        enlazadas = []
    return {"ok": True, "cliente": client, "existing": bool(before),
            "facturas_enlazadas": enlazadas, "completados": sorted(nuevos),
            "avisos": avisos}


_CAMPOS_CLIENTE = {"telefono": "phone", "email": "email", "nif": "nif",
                   "direccion": "address"}


def datos_de_cliente_validos(datos: dict) -> tuple[dict, list[str]]:
    """Normaliza teléfono, correo, NIF y dirección; lo que no vale se avisa."""
    from .fiscal_validation import valid_spanish_tax_id
    limpios, avisos = {}, []
    for campo, columna in _CAMPOS_CLIENTE.items():
        valor = str(datos.get(campo) or "").strip()
        if not valor:
            continue
        if campo == "nif":
            valor = re.sub(r"[\s.\-]", "", valor).upper()
            if not valid_spanish_tax_id(valor):
                avisos.append(f"El NIF {valor} no es válido y no lo he guardado.")
                continue
        if campo == "email":
            valor = valor.lower()
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", valor):
                avisos.append(f"El correo {valor} no parece válido y no lo he guardado.")
                continue
        if campo == "telefono":
            valor = re.sub(r"[\s.\-()]", "", valor)
            if not re.fullmatch(r"\+?\d{9,15}", valor):
                avisos.append(f"El teléfono {valor} no parece válido y no lo he guardado.")
                continue
        limpios[columna] = valor[:300]
    return limpios, avisos


def _actualizar_cliente(business_id, cliente, telefono=None, email=None, nif=None,
                        direccion=None):
    ficha = db.resolve_client_reference(cliente, business_id)
    if not ficha:
        return {"error": f"No tengo ficha de cliente «{cliente}». Créala con «crea el "
                         f"cliente {cliente}» y dime sus datos."}
    datos, avisos = datos_de_cliente_validos(
        {"telefono": telefono, "email": email, "nif": nif, "direccion": direccion})
    if not datos and not avisos:
        return {"error": "Dime qué dato quieres guardar: teléfono, correo, NIF o dirección."}
    cambios = {k: (ficha.get(k), v) for k, v in datos.items() if ficha.get(k) != v}
    if cambios:
        db.update_client(ficha["id"], business_id=business_id,
                         **{k: v for k, (_, v) in cambios.items()})
        ficha = db.get_client(ficha["id"], business_id) or ficha
    return {"ok": bool(cambios) or not avisos, "cliente": ficha,
            "cambios": {k: list(v) for k, v in cambios.items()}, "avisos": avisos}


def _crear_proveedor(business_id, nombre):
    before = db.find_supplier(business_id, name=nombre)
    supplier = before or db.add_supplier(nombre, business_id=business_id)
    return {"ok": True, "proveedor": supplier, "existing": bool(before)}


def _ver_agenda(business_id, fecha, hasta=None):
    if hasta and hasta > fecha:
        from datetime import timedelta
        tope = (date.fromisoformat(fecha) + timedelta(days=31)).isoformat()
        hasta = min(hasta, tope)
        jobs = db.jobs_between(fecha, hasta, business_id)
        return {"fecha": fecha, "hasta": hasta, "n": len(jobs), "trabajos": jobs}
    jobs = db.jobs_for_date(fecha, business_id)
    return {"fecha": fecha, "n": len(jobs), "trabajos": jobs}


def _ver_gastos(business_id, desde=None, hasta=None):
    hoy = date.today()
    del_mes = not desde and not hasta
    desde = desde or hoy.replace(day=1).isoformat()
    hasta = hasta or hoy.isoformat()
    gastos = db.expenses_between(desde, hasta, business_id)
    total = sum(float(g.get("amount") or 0) for g in gastos)
    return {"desde": desde, "hasta": hasta, "n": len(gastos), "del_mes": del_mes,
            "total": round(total, 2), "gastos": gastos}


_TICKET_LIMIT_ERROR = (
    "El ticket supera el límite general de 400 € IVA incluido. "
    "Prepara una factura completa con los datos fiscales del cliente."
)


def _crear_factura(
    business_id, concepto, base, cliente=None, iva=None, irpf=None,
    tipo_factura="F1", importe_incluye_iva=False, lineas=None, cliente_id=None,
):
    biz = db.get_business(business_id) or {}
    invoice_type = str(tipo_factura or "F1").strip().upper()
    if invoice_type not in {"F1", "F2"}:
        raise ValueError("El tipo debe ser factura completa F1 o simplificada F2.")
    client_name = str(cliente or "").strip()
    if not client_name:
        if invoice_type != "F2":
            raise ValueError("Indica el cliente de la factura completa.")
        client_name = "Cliente de mostrador"
    # Un precio final conocido se rechaza antes de tocar clientes: un ticket
    # inválido no puede dejar una ficha nueva como efecto secundario.
    if (invoice_type == "F2" and importe_incluye_iva and not lineas
            and not db._fits_simplified_invoice(base)):
        raise ValueError(_TICKET_LIMIT_ERROR)
    c = _reviewed_client(business_id, client_name, cliente_id)
    rate = biz.get("default_vat", 21) if iva is None else iva
    irpf_rate = (
        0 if invoice_type == "F2" and irpf is None
        else biz.get("default_irpf", 0) if irpf is None else irpf
    )
    gross_total = None
    if importe_incluye_iva and not lineas:
        gross = Decimal(str(base))
        gross_total = gross
        divisor = (
            Decimal("1") + Decimal(str(rate)) / Decimal("100")
            - Decimal(str(irpf_rate)) / Decimal("100")
        )
        if divisor <= 0:
            raise ValueError("Los tipos fiscales no permiten calcular la base.")
        base = float((gross / divisor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ))
    inv = db.add_invoice(c["id"], concepto, base, vat_rate=rate,
                         irpf_rate=irpf_rate, business_id=business_id,
                         invoice_type=invoice_type, lines=lineas, gross_total=gross_total)
    if invoice_type == "F2" and not db._fits_simplified_invoice(inv["total"]):
        db.delete_invoice(inv["id"], business_id)
        raise ValueError(_TICKET_LIMIT_ERROR)
    msg = (f"Borrador listo: {inv['total']:.2f} € (base {inv['base']:.2f} "
           f"+ IVA {inv['vat_amount']:.2f}")
    if inv["irpf_amount"]:
        msg += f" − IRPF {inv['irpf_amount']:.2f}"
    from . import trades
    return {
        "ok": True, "factura": inv, "mensaje": msg + ").",
        "aviso_fiscal": trades.reduced_rate_warning(
            db.get_invoice_lines(inv["id"], business_id)
        ),
    }


def _preparar_factura_trabajo(business_id, trabajo_id):
    invoice = db.prepare_job_invoice_draft(int(trabajo_id), business_id)
    return {"ok": True, "factura": invoice}


def _crear_presupuesto(business_id, cliente, concepto, base, iva=None, irpf=None,
                       validez_dias=None, notas=None, cliente_id=None):
    biz = db.get_business(business_id) or {}
    c = _reviewed_client(business_id, cliente, cliente_id)
    rate = biz.get("default_vat", 21) if iva is None else iva
    irpf_rate = biz.get("default_irpf", 0) if irpf is None else irpf
    q = db.add_quote(c["id"], concepto, base, vat_rate=rate, irpf_rate=irpf_rate,
                     valid_days=validez_dias, notes=notas,
                     business_id=business_id)
    return {"ok": True, "presupuesto": q}


def _enviar_factura(business_id, factura_id):
    inv = db.get_invoice(factura_id, business_id)
    # Aislamiento: solo se puede operar sobre facturas del propio negocio.
    if not inv or inv.get("business_id") != business_id:
        return {"ok": False, "error": "No existe esa factura."}
    client = db.get_client(inv["client_id"], business_id)
    # La emisión y la huella quedan siempre dentro del motor nativo de Bynoesis.
    issued = _provider.issue(inv, client or {})
    inv = db.get_invoice(factura_id, business_id)
    return {"ok": True, "factura": inv, "emision": issued}


def prepare_invoice_delivery(
    business_id: int, factura_id: int, *, channel: str = "auto"
) -> dict:
    """Prepara PDF y entrega durable tras una confirmación explícita del titular."""
    from .adapters import email as email_adapter
    from .web import whatsapp
    from .web.invoice_pdf import build_invoice_pdf

    invoice = db.get_invoice(factura_id, business_id)
    if not invoice or invoice.get("status") == "borrador" or not invoice.get("number"):
        raise ValueError("Emite la factura antes de entregarla.")
    client = db.get_client(invoice["client_id"], business_id) or {}
    business = db.get_business(business_id) or {}
    pdf = build_invoice_pdf(factura_id, business_id)
    if not pdf:
        raise ValueError("No se ha podido generar el PDF de la factura.")
    token = db.get_or_create_portal_token(business_id, invoice["client_id"])
    pdf_url = (
        f"{config.BASE_URL}/p/{token}/invoices/{factura_id}/pdf"
        if token else None
    )
    owner_pdf_url = f"{config.BASE_URL}/api/{business_id}/invoices/{factura_id}/pdf"
    preferences = db.get_client_preferences(invoice["client_id"], business_id) or {}
    requested = str(channel or "auto").strip().lower()
    if requested not in {"auto", "email", "whatsapp", "none"}:
        raise ValueError("El canal de entrega no es válido.")
    selected = requested
    if selected == "auto":
        preferred = preferences.get("preferred_channel")
        if preferred in {"email", "whatsapp"}:
            selected = preferred
        elif client.get("email"):
            selected = "email"
        elif whatsapp.recipient_phone(client.get("phone")):
            selected = "whatsapp"
        else:
            selected = "none"
    queued = False
    target = None
    amount = f"{invoice['total']:.2f} EUR"
    day = date.today().isoformat()
    if selected == "email":
        target = str(client.get("email") or "").strip()
        if not target:
            raise ValueError("El cliente no tiene correo configurado.")
        # Sin proveedor de correo no se encola nada: encolarlo hacía que la app
        # dijera «en camino» y el autónomo creyera que su cliente tenía la
        # factura. Un envío que no puede salir se dice, no se promete.
        from .adapters import google_mail

        if not (email_adapter.available() or google_mail.disponible(business_id)):
            raise ValueError(
                "El correo no está configurado, así que no puedo enviarla. "
                "Conecta tu Gmail desde Ajustes, o configura el correo del "
                "servidor. Mientras tanto, descarga el PDF y mándalo tú.")
        email_adapter.queue_email(
            target,
            f"Factura {invoice['number']} — {business.get('name') or 'Bynoesis'}",
            (
                f"Hola {client.get('name') or ''},\n\n"
                f"Te enviamos la factura {invoice['number']} por {amount}. "
                "Encontrarás el PDF adjunto.\n\n"
                f"— {business.get('name') or 'Bynoesis'}"
            ),
            business_id=business_id,
            idempotency_key=f"invoice:{business_id}:{factura_id}:email:{day}",
            entity_type="invoice",
            entity_id=factura_id,
        )
        queued = True
    elif selected == "whatsapp":
        target = whatsapp.recipient_phone(client.get("phone"))
        if not target:
            raise ValueError("El cliente no tiene un WhatsApp válido configurado.")
        if not (whatsapp._TOKEN and whatsapp._PHONE_ID.strip()):
            raise ValueError(
                "WhatsApp no está configurado en el servidor, así que no puedo "
                "enviarla. Mientras tanto, descarga el PDF y mándalo tú.")
        whatsapp.queue_template(
            target,
            config.WHATSAPP_TEMPLATE_INVOICE,
            [
                client.get("name") or "cliente",
                business.get("name") or "Tu proveedor",
                invoice["number"], amount, pdf_url or config.BASE_URL,
            ],
            business_id=business_id,
            idempotency_key=f"invoice:{business_id}:{factura_id}:whatsapp:{day}",
        )
        queued = True
    if queued:
        db.record_invoice_communication(
            factura_id, business_id, "entrega_preparada",
            details=f"canal={selected};destino={target}",
        )
    return {
        "ok": True, "factura": invoice, "pdf_url": pdf_url,
        "owner_pdf_url": owner_pdf_url,
        "channel": selected, "target": target, "queued": queued,
    }


def _entregar_factura(business_id, factura_id, canal="auto"):
    """Entrega al CLIENTE una factura ya emitida, por el canal que se pida.

    Separada de `enviar_factura`, que emite: emitir pone número definitivo y
    cuenta para Hacienda; entregar es mandársela a otra persona. Decir «envía la
    factura 3 por correo» no encontraba ningún camino y acababa en el redactor de
    correos, preguntando a qué cliente escribir.
    """
    try:
        entrega = prepare_invoice_delivery(business_id, factura_id, channel=canal)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "entrega": entrega, "factura": entrega["factura"]}


def _registrar_pago(business_id, factura_id):
    inv = db.get_invoice(factura_id, business_id)
    # Aislamiento: solo se puede operar sobre facturas del propio negocio.
    if not inv or inv.get("business_id") != business_id:
        return {"ok": False, "error": "No existe esa factura."}
    if inv["status"] == "cobrada":
        return {"ok": True, "factura": inv}
    paid = db.mark_invoice_paid(factura_id, business_id)
    if not paid:
        return {"ok": False, "error": "Solo se puede cobrar una factura emitida."}
    return {"ok": True, "factura": paid}


def _ver_cobros_pendientes(business_id, cliente=None, tras_cobro=False):
    pend = db.pending_payments(business_id)
    if cliente:
        try:
            ficha = db.resolve_client_reference(cliente, business_id)
        except ValueError:
            ficha = None
        if not ficha:
            return {"n": 0, "total_pendiente": 0, "facturas": [],
                    "cliente": cliente, "sin_ficha": True,
                    **({"tras_cobro": True} if tras_cobro else {})}
        pend = [p for p in pend if p.get("client_id") == ficha["id"]]
        cliente = ficha["name"]
    total = round(sum(p["total"] for p in pend), 2)
    return {"n": len(pend), "total_pendiente": total, "facturas": pend,
            **({"cliente": cliente} if cliente else {}),
            **({"tras_cobro": True} if tras_cobro else {})}


def _resumen_negocio(business_id, mes=None, anio=None):
    if anio:
        hoy = date.today()
        anio = int(anio)
        ultimo = hoy.month if anio == hoy.year else 12
        if anio > hoy.year:
            ultimo = 0
        claves = ("invoiced", "collected", "pending", "expenses", "estimated_profit",
                  "vat_estimated")
        total = {k: 0.0 for k in claves}
        for m in range(1, ultimo + 1):
            cifras = db.month_billing(f"{anio}-{m:02d}", business_id=business_id)
            for k in claves:
                total[k] += float(cifras.get(k) or 0)
        return {"anio": anio, "hasta_mes": ultimo, **{k: round(v, 2) for k, v in total.items()}}
    return db.month_billing(mes, business_id=business_id)


def _ver_impuestos(business_id, trimestre=None, anio=None):
    hoy = date.today()
    year = int(anio or hoy.year)
    quarter = int(trimestre or (hoy.month - 1) // 3 + 1)
    plazo = None
    # En plazo de presentación (1–20 de abril, julio y octubre; 1–30 de enero), «¿cuánto
    # IVA tengo que pagar?» pregunta por el trimestre que se acaba de cerrar, no por
    # el que empieza: el 1 de octubre se contestaba con el 4T a cero.
    limite = 30 if hoy.month == 1 else 20
    if not trimestre and not anio and hoy.month in (1, 4, 7, 10) and hoy.day <= limite:
        quarter = (hoy.month - 1) // 3 or 4
        if hoy.month == 1:
            year -= 1
        mes = {1: "enero", 4: "abril", 7: "julio", 10: "octubre"}[hoy.month]
        plazo = f"se presenta hasta el {limite} de {mes}"
    if quarter not in (1, 2, 3, 4):
        return {"ok": False, "error": "El trimestre debe estar entre 1 y 4."}
    return {"ok": True, **db.tax_quarter(year, quarter, business_id),
            **({"plazo": plazo} if plazo else {})}


def _registrar_gasto(
    business_id, concepto, importe, iva=None, categoria=None, proyecto_id=None
):
    return {"ok": True, "gasto": db.add_expense(concepto, importe, vat_rate=iva,
                                                category=categoria,
                                                project_id=proyecto_id,
                                                business_id=business_id)}


def _ver_presupuestos(business_id, cliente=None):
    presupuestos = db.list_quotes(business_id)
    if cliente:
        try:
            ficha = db.resolve_client_reference(cliente, business_id)
        except ValueError:
            ficha = None
        if not ficha:
            return {"presupuestos": [], "n": 0, "cliente": cliente, "sin_ficha": True}
        presupuestos = [p for p in presupuestos if p.get("client_id") == ficha["id"]]
        cliente = ficha["name"]
    return {"presupuestos": presupuestos[:10], "n": len(presupuestos),
            **({"cliente": cliente} if cliente else {})}


def trabajo_abierto_de(business_id: int, cliente: str) -> tuple[dict | None, dict | None]:
    """El trabajo sin cerrar más cercano de un cliente: `(ficha, trabajo)`."""
    try:
        ficha = db.resolve_client_reference(cliente, business_id)
    except ValueError:
        ficha = None
    if not ficha:
        return None, None
    from datetime import timedelta
    hoy = date.today()
    trabajos = [j for j in db.jobs_between((hoy - timedelta(days=60)).isoformat(),
                                           (hoy + timedelta(days=30)).isoformat(), business_id)
                if j.get("client_id") == ficha["id"]
                and str(j.get("status") or "") not in (*db._JOB_DONE_STATES, *db._JOB_DEAD_STATES)]
    if not trabajos:
        return ficha, None
    # El más cercano a hoy: lo normal es cerrar el de hoy o el último que pasó.
    return ficha, min(trabajos, key=lambda j: abs(
        (date.fromisoformat(str(j.get("scheduled_for") or hoy.isoformat())[:10]) - hoy).days))


def _terminar_trabajo(business_id, cliente):
    ficha, trabajo = trabajo_abierto_de(business_id, cliente)
    if not ficha:
        return {"error": f"No tengo ficha de cliente «{cliente}»."}
    if not trabajo:
        return {"error": f"{ficha['name']} no tiene ningún trabajo abierto que cerrar."}
    db.update_job_status(trabajo["id"], "hecho", business_id)
    return {"ok": True, "cliente": ficha, "trabajo": db.get_job(trabajo["id"], business_id)}


def _ver_cliente(business_id, cliente, dato=None, llamar=False):
    try:
        ficha = db.resolve_client_reference(cliente, business_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not ficha:
        return {"ok": False, "error": f"No tengo ficha de cliente «{cliente}»."}
    facturas = [f for f in db.list_invoices(business_id, client_id=ficha["id"], limit=50)
                if f.get("status") != "anulada"]
    return {"ok": True, "cliente": ficha, "dato": dato, "llamar": bool(llamar),
            "facturas": facturas[:5],
            "n_facturas": len(facturas),
            "n_borradores": sum(1 for f in facturas if f.get("status") == "borrador"),
            "pendiente": round(sum(float(f.get("remaining_amount") or 0) for f in facturas
                                   if f.get("status") in {"enviada", "parcial"}), 2)}


def _listar_clientes(business_id):
    return {"clientes": db.list_clients(business_id)}


def _ver_perfil_cliente(business_id, cliente):
    record = db.find_client(cliente, business_id)
    if not record:
        return {"ok": False, "error": "Cliente no encontrado."}
    insight = next(
        (item for item in db.client_insights(business_id)
         if item["client_id"] == record["id"]),
        None,
    )
    return {"ok": True, "perfil": insight}


def _ver_proyectos(business_id):
    return db.project_summary(business_id)


def _ver_proyecto(business_id, proyecto_id):
    project = db.get_project(int(proyecto_id), business_id)
    return project or {"ok": False, "error": "Proyecto no encontrado."}


def _crear_proyecto(
    business_id, nombre, presupuesto, cliente=None, ubicacion=None,
    horas_previstas=0,
):
    client_id = None
    if str(cliente or "").strip():
        client_id = db.get_or_create_client(
            cliente, business_id=business_id
        )["id"]
    return {
        "ok": True,
        "proyecto": db.add_project(
            nombre, presupuesto, client_id=client_id, location=ubicacion,
            planned_hours=horas_previstas, business_id=business_id,
        ),
    }


def _crear_tarea_proyecto(
    business_id, proyecto_id, titulo, trabajador_id=None, trabajo_id=None,
    fecha_limite=None, tipo="tarea", nota=None,
):
    return {
        "ok": True,
        "tarea": db.add_project_task(
            int(proyecto_id), titulo, business_id=business_id, kind=tipo,
            note=nota, worker_id=trabajador_id, job_id=trabajo_id,
            due_on=fecha_limite,
        ),
    }


def _ver_equipo(business_id):
    return {
        "personas": db.list_workers(business_id, include_inactive=False),
        "jornada_hoy": db.clockins_today(business_id),
    }


def _ver_documentos_pendientes(business_id):
    from .documents import repo

    items = repo.list_pending_review(business_id)
    return {"n": len(items), "documentos": items}


def _ver_solicitudes_gestoria(business_id):
    items = db.list_gestoria_requests(business_id, status="abierta")
    return {"n": len(items), "solicitudes": items}


def _ver_control_noesis(business_id):
    return {
        "permisos": [
            {
                "accion": item["key"], "nombre": item["label"],
                "modo": item["mode"], "riesgo": item["risk"],
            }
            for item in db.automation_catalog(business_id)
        ]
    }


_DISPATCH = {
    "crear_cliente": _crear_cliente,
    "crear_proveedor": _crear_proveedor,
    "actualizar_cliente": _actualizar_cliente,
    "agendar_trabajo": _agendar_trabajo,
    "ver_agenda": _ver_agenda,
    "ver_gastos": _ver_gastos,
    "crear_factura": _crear_factura,
    "preparar_factura_trabajo": _preparar_factura_trabajo,
    "crear_presupuesto": _crear_presupuesto,
    "enviar_factura": _enviar_factura,
    "entregar_factura": _entregar_factura,
    "registrar_pago": _registrar_pago,
    "ver_cobros_pendientes": _ver_cobros_pendientes,
    "resumen_negocio": _resumen_negocio,
    "ver_impuestos": _ver_impuestos,
    "registrar_gasto": _registrar_gasto,
    "listar_clientes": _listar_clientes,
    "ver_cliente": _ver_cliente,
    "ver_presupuestos": _ver_presupuestos,
    "terminar_trabajo": _terminar_trabajo,
    "ver_perfil_cliente": _ver_perfil_cliente,
    "ver_proyectos": _ver_proyectos,
    "ver_proyecto": _ver_proyecto,
    "crear_proyecto": _crear_proyecto,
    "crear_tarea_proyecto": _crear_tarea_proyecto,
    "ver_equipo": _ver_equipo,
    "ver_documentos_pendientes": _ver_documentos_pendientes,
    "ver_solicitudes_gestoria": _ver_solicitudes_gestoria,
    "ver_control_noesis": _ver_control_noesis,
}

_TOOL_ENTITLEMENTS = {
    "ver_proyectos": billing_adapter.ENTITLEMENT_PROJECTS,
    "ver_proyecto": billing_adapter.ENTITLEMENT_PROJECTS,
    "crear_proyecto": billing_adapter.ENTITLEMENT_PROJECTS,
    "crear_tarea_proyecto": billing_adapter.ENTITLEMENT_PROJECTS,
    "ver_equipo": billing_adapter.ENTITLEMENT_TEAM,
    "ver_solicitudes_gestoria": billing_adapter.ENTITLEMENT_GESTORIA,
}


def run_tool(
    name: str,
    tool_input: dict,
    business_id: int,
    *,
    channel: str = "web",
    trigger_source: str = "user_initiated",
    completion_mode: str = "user_confirmed",
) -> str:
    """Ejecuta una herramienta para un negocio y devuelve JSON (para Claude/NLU)."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"Herramienta desconocida: {name}"})
    entitlement = _TOOL_ENTITLEMENTS.get(name)
    business = db.get_business(business_id)
    if entitlement and not billing_adapter.has_entitlement(business, entitlement):
        return json.dumps(
            {
                "error": (
                    f"{billing_adapter.ENTITLEMENT_LABELS[entitlement]} forma parte "
                    "del plan Negocio. Puedes activarlo desde Suscripción."
                ),
                "code": "plan_upgrade_required",
                "required_plan": billing_adapter.minimum_plan_for(entitlement),
            },
            ensure_ascii=False,
        )
    if "factura_numero" in (tool_input or {}):
        # «La factura 2026/0001»: se resuelve por su número visible, nunca por
        # las cifras sueltas del año.
        tool_input = dict(tool_input)
        numero = str(tool_input.pop("factura_numero") or "").strip().upper()
        plegado = re.sub(r"[^A-Z0-9]", "", numero)
        coinciden = [f for f in db.list_invoices(business_id)
                     if f.get("number") and (
                         str(f["number"]).upper() == numero
                         or re.sub(r"[^A-Z0-9]", "", str(f["number"]).upper()).endswith(plegado))]
        if len(coinciden) != 1:
            return json.dumps({"error": (
                f"No encuentro una única factura con el número {numero}. "
                "Dime el número tal como sale en Facturas."
                if not coinciden else
                f"Hay varias facturas que acaban en {numero}: "
                + ", ".join(str(f["number"]) for f in coinciden[:5]) + ". Dime cuál.")},
                ensure_ascii=False)
        tool_input["factura_id"] = coinciden[0]["id"]
    try:
        from . import action_review
        proposed = action_review.propose(business_id, name, tool_input)
        if proposed is not None:
            return json.dumps(proposed, ensure_ascii=False)
        from . import value_ledger
        with value_ledger.observation_context(
            channel=channel,
            trigger_source=trigger_source,
            completion_mode=completion_mode,
        ):
            result = fn(business_id=business_id, **tool_input)
    except (TypeError, ValueError) as e:
        result = {"error": f"Parámetros inválidos para {name}: {e}"}
    except Exception:  # noqa: BLE001
        log.exception("Fallo ejecutando la herramienta %s.", name)
        result = {"error": f"No se pudo ejecutar {name}. Inténtalo de nuevo."}
    receipts = execution_receipts.get()
    if receipts is not None:
        receipts.append({"tool": name, "business_id": business_id, "result": result})
    return json.dumps(result, ensure_ascii=False, default=str)
