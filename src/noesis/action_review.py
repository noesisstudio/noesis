"""Propuestas acotadas, persistentes y de un solo uso para ambos canales.

No ejecuta texto otra vez al confirmar: conserva los argumentos y la identidad
revisada. La reclamación atómica evita duplicados entre procesos del servidor.
"""
from __future__ import annotations

import json
from contextvars import ContextVar
from decimal import Decimal, ROUND_HALF_UP

from . import db, nlu

context: ContextVar[dict | None] = ContextVar("action_review", default=None)
READS = {
    "ver_agenda", "ver_cobros_pendientes", "resumen_negocio", "ver_impuestos",
    "listar_clientes", "ver_perfil_cliente", "ver_proyectos", "ver_proyecto",
    "ver_equipo", "ver_documentos_pendientes", "ver_solicitudes_gestoria",
    "ver_control_noesis",
}
LABELS = {
    "crear_cliente": "Guardar cliente", "crear_proveedor": "Guardar proveedor",
    "crear_factura": "Preparar factura borrador", "crear_presupuesto": "Preparar presupuesto",
    "agendar_trabajo": "Agendar trabajo", "registrar_gasto": "Registrar gasto",
    "registrar_pago": "Registrar el saldo pendiente como cobrado",
    "enviar_factura": "Emitir factura (la entrega se gestiona por separado)",
}


def _preview(bid: int, tool: str, args: dict) -> tuple[str, dict]:
    if tool not in LABELS:
        raise ValueError("Esta acción todavía requiere revisión desde su apartado en la app.")
    lines = [LABELS[tool]]
    snapshot = {}
    if tool in {"crear_factura", "crear_presupuesto", "agendar_trabajo"}:
        name = str(args.get("cliente") or "").strip()
        if not name and args.get("tipo_factura") == "F2":
            name = "Cliente de mostrador"
        if not name:
            raise ValueError("Falta el cliente. No elegiré uno por mi cuenta.")
        client = db.resolve_client_reference(name, bid)
        if client:
            args["cliente"] = client["name"]
            args["cliente_id"] = client["id"]
            snapshot["client"] = {k: client.get(k) for k in ("id", "name", "nif")}
            lines.append(f"Cliente: {client['name']} · ficha #{client['id']}")
        else:
            # Un alta implícita crea duplicados por errores de voz/ortografía.
            raise ValueError(f"No encuentro un cliente inequívoco llamado «{name}». Crea primero su ficha con «crear cliente {name}» o corrige el nombre.")
    if tool in {"crear_cliente", "crear_proveedor"}:
        name = str(args.get("nombre") or "").strip()
        if not name or len(name) > 160 or any(x in nlu._norm(name) for x in ("telefono", "nif", "correo", "@")):
            raise ValueError("Indica solo el nombre. Los datos de contacto se revisan en la ficha.")
        lines.append(f"Nombre: {name}")
        if tool == "crear_cliente":
            existing = db.resolve_client_reference(name, bid)
            if existing:
                args["nombre"] = existing["name"]
                snapshot["client"] = {k: existing.get(k) for k in ("id", "name", "nif")}
                lines.append(f"Reutilizaré la ficha existente: {existing['name']} · #{existing['id']}")
    if tool in {"crear_factura", "crear_presupuesto"}:
        if args.get("lineas"):
            raise ValueError("Revisa la factura de varias líneas en Facturas antes de guardarla.")
        business = db.get_business(bid) or {}
        vat = args.get("iva")
        vat = business.get("default_vat", 21) if vat is None else vat
        irpf = args.get("irpf")
        irpf = (0 if tool == "crear_factura" and args.get("tipo_factura") == "F2" and irpf is None
                else business.get("default_irpf", 0) if irpf is None else irpf)
        args.update(iva=vat, irpf=irpf)
        if vat not in (0, 4, 10, 21) or irpf not in (0, 7, 15):
            raise ValueError("Revisa los tipos de IVA e IRPF en la factura.")
        base = Decimal(str(args.get("base", 0)))
        if not base.is_finite() or base <= 0:
            raise ValueError("El importe debe ser positivo y válido.")
        if args.get("importe_incluye_iva"):
            base /= 1 + Decimal(str(vat)) / 100 - Decimal(str(irpf)) / 100
        base = base.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        total = base + (base * Decimal(str(vat)) / 100).quantize(Decimal(".01"), rounding=ROUND_HALF_UP) - (base * Decimal(str(irpf)) / 100).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        if tool == "crear_presupuesto":
            args.pop("importe_incluye_iva", None)
            args["base"] = float(base)
        lines.extend([f"Concepto: {args.get('concepto', 'Servicio')}", f"Base: {nlu._eur(base)} · IVA {vat}% · IRPF {irpf}%", f"Total: {nlu._eur(total)}"])
    if tool == "registrar_gasto":
        if args.get("proyecto_id"):
            raise ValueError("Para asignar el gasto a un proyecto, revisa primero el proyecto en Costes. No he asignado nada.")
        amount = Decimal(str(args.get("importe", 0)))
        if not amount.is_finite() or amount <= 0:
            raise ValueError("El gasto debe tener un importe positivo.")
        lines.extend([f"Concepto: {args.get('concepto') or 'Gasto'}", f"Importe: {nlu._eur(amount)}", "Destino: gastos generales del negocio; sin asignación a cliente."])
    if tool == "agendar_trabajo":
        lines.extend([f"Trabajo: {args.get('descripcion') or 'Trabajo'}", f"Cuándo: {args.get('fecha_hora')}", f"Lugar: {args.get('zona') or 'sin especificar'}"])
    if tool in {"registrar_pago", "enviar_factura"}:
        invoice = db.get_invoice(int(args.get("factura_id", 0)), bid)
        if not invoice:
            raise ValueError("No existe esa factura en tu negocio.")
        snapshot["invoice"] = invoice
        snapshot["lines"] = db.get_invoice_lines(invoice["id"], bid)
        client = db.get_client(invoice["client_id"], bid)
        snapshot["client"] = client
        lines.extend([f"Factura #{invoice['id']} · {invoice.get('client_name')}", f"Total: {nlu._eur(invoice['total'])}", f"Estado: {invoice['status']}"])
        if tool == "registrar_pago":
            lines.append("Registraré todo el saldo que falta. Si el pago es parcial, usa Facturas.")
    return "\n".join(lines), snapshot


def propose(bid: int, tool: str, args: dict) -> dict | None:
    state = context.get()
    if state is None or tool in READS:
        return None
    if state.get("proposal"):
        return state["proposal"]
    try:
        args = dict(args)
        # Los IDs del modelo no son autoridad: se resuelven desde el nombre.
        args.pop("cliente_id", None)
        preview, snapshot = _preview(bid, tool, args)
        row = db.set_pending_action(bid, state["actor"], "reviewed_tool", {"tool": tool, "args": args, "snapshot": snapshot, "preview": preview})
        reply = preview + "\n\nNo he guardado cambios. Responde SÍ para confirmar, NO para descartar o «corregir:» seguido de la orden completa."
        result = {"confirmation_required": True, "reply": reply, "proposal_id": row["id"]}
    except (ValueError, TypeError, ArithmeticError) as exc:
        result = {"error": str(exc), "reply": str(exc)}
    state["proposal"] = result
    return result


def respond(bid: int, actor: str, text: str) -> dict | None:
    """Consume una propuesta exacta; no interpreta de nuevo lo confirmado."""
    norm = nlu._norm(text)
    yes = norm in {"si", "confirmo", "confirmar", "si, confirmar"}
    no = norm in {"no", "descartar", "ahora no"}
    if not yes and not no:
        return None
    pending = db.get_pending_action(bid, actor)
    if not pending or pending["kind"] != "reviewed_tool":
        return {"reply": "No hay ninguna propuesta pendiente de confirmar en esta conversación.", "source": "local"}
    payload = json.loads(pending["payload"])
    with db.get_conn() as conn:
        claimed = conn.execute("DELETE FROM whatsapp_pending_actions WHERE id=? AND business_id=? AND phone=? AND expires_at>=? RETURNING id", (pending["id"], bid, actor, db._now())).fetchone()
    if not claimed:
        return {"reply": "Esa propuesta ya se ha atendido. No la he repetido.", "source": "local"}
    if no:
        return {"reply": "Descartado. No he cambiado ningún registro.", "source": "local", "action_result": "discarded"}
    if not db.subscription_allows_access(db.get_business(bid)):
        return {"reply": "Tu cuenta está en modo consulta. No he ejecutado la propuesta.", "source": "local", "action_result": "failed"}
    try:
        args = dict(payload["args"])
        _, current = _preview(bid, payload["tool"], args)
        if current != payload["snapshot"]:
            raise ValueError("Los datos han cambiado desde la propuesta. Vuelve a pedir la operación para revisarlos.")
        from .tools import run_tool
        result = json.loads(run_tool(payload["tool"], args, bid, channel="whatsapp" if actor.startswith("wa:") else "web"))
        outcome = "failed" if result.get("error") or result.get("ok") is False else "completed"
        return {"reply": nlu.format_reply(payload["tool"], result), "source": "local", "action_result": outcome, "proposal_id": pending["id"]}
    except (ValueError, TypeError) as exc:
        return {"reply": str(exc) + " No he repetido la operación.", "source": "local", "action_result": "failed"}
