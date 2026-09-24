"""Propuestas acotadas, persistentes y de un solo uso para ambos canales.

No ejecuta texto otra vez al confirmar: conserva los argumentos y la identidad
revisada. La reclamación atómica evita duplicados entre procesos del servidor.
"""
from __future__ import annotations

import json
import re
from contextvars import ContextVar
from decimal import Decimal, ROUND_HALF_UP

from . import db, nlu, local_invoice

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
    "entregar_factura": "Entregar la factura al cliente",
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
        business = db.get_business(bid) or {}
        vat = args.get("iva")
        vat = business.get("default_vat", 21) if vat is None else vat
        irpf = args.get("irpf")
        irpf = (0 if tool == "crear_factura" and args.get("tipo_factura") == "F2" and irpf is None
                else business.get("default_irpf", 0) if irpf is None else irpf)
        args.update(iva=vat, irpf=irpf)
        if vat not in (0, 4, 10, 21) or irpf not in (0, 7, 15):
            raise ValueError("Revisa los tipos de IVA e IRPF en la factura.")
        if args.get("lineas"):
            if not local_invoice.enabled() or tool != "crear_factura" or args.get("importe_incluye_iva"):
                raise ValueError("Revisa la factura de varias líneas en Facturas antes de guardarla.")
            normalized_lines = db._normalize_invoice_lines(args["lineas"], fallback_vat=vat)
            totals = db._invoice_totals(normalized_lines, irpf)
            if args.get("tipo_factura") == "F2" and not db._fits_simplified_invoice(totals["total"]):
                raise ValueError("El total supera el límite del ticket. Prepara una factura completa.")
            args["base"] = totals["base"]
            snapshot["calculation"] = {"lines": normalized_lines, "totals": totals}
            for line in normalized_lines:
                lines.append(f"{line['position']}. {line['description']}: {line['quantity']:g} × {nlu._eur(line['unit_price'])} · base {nlu._eur(line['base'])} · IVA {line['vat_rate']:g}%")
            lines.append(f"Base: {nlu._eur(totals['base'])} · IVA: {nlu._eur(totals['vat_amount'])} · IRPF: {nlu._eur(totals['irpf_amount'])}")
            lines.append(f"Total: {nlu._eur(totals['total'])}")
            return "\n".join(lines), snapshot
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
    if tool == "entregar_factura":
        invoice = db.get_invoice(int(args.get("factura_id", 0)), bid)
        if not invoice:
            raise ValueError("No existe esa factura en tu negocio.")
        if invoice.get("status") == "borrador" or not invoice.get("number"):
            raise ValueError("Esa factura todavía es un borrador. Emítela antes de "
                             "entregarla, o dime «emitir y enviar factura "
                             f"{invoice['id']}».")
        cliente = db.get_client(invoice["client_id"], bid) or {}
        canal = str(args.get("canal") or "auto")
        snapshot["invoice"] = invoice
        snapshot["client"] = {k: cliente.get(k) for k in ("id", "name", "email", "phone")}
        destino = (cliente.get("email") if canal == "email"
                   else cliente.get("phone") if canal == "whatsapp" else None)
        if canal == "email" and not destino:
            raise ValueError(f"{cliente.get('name') or 'Ese cliente'} no tiene "
                             "correo en su ficha. Añádeselo en Clientes.")
        if canal == "whatsapp" and not destino:
            raise ValueError(f"{cliente.get('name') or 'Ese cliente'} no tiene "
                             "teléfono en su ficha. Añádeselo en Clientes.")
        lines.extend([
            f"Factura {invoice.get('number')} · {cliente.get('name') or ''}",
            f"Canal: {'el que tenga en ficha' if canal == 'auto' else canal}"
            + (f" · {destino}" if destino else ""),
            "Se manda al CLIENTE, no a ti.",
        ])
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


def propose(bid: int, tool: str, args: dict, *, expected_id: int | None = None) -> dict | None:
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
        payload = {"tool": tool, "args": args, "snapshot": snapshot, "preview": preview}
        if expected_id is None:
            row = db.set_pending_action(bid, state["actor"], "reviewed_tool", payload)
        else:
            row = db.revise_pending_action(bid, state["actor"], expected_id, payload)
            if not row:
                raise ValueError("La propuesta cambió o ya se confirmó. Vuelve a pedirla; no he repetido nada.")
        reply = preview + "\n\nNo he guardado cambios. Responde SÍ para confirmar, NO para descartar o «corregir:» seguido de la orden completa."
        result = {"confirmation_required": True, "reply": reply, "proposal_id": row["id"]}
    except (ValueError, TypeError, ArithmeticError) as exc:
        if expected_id is not None:
            db.discard_pending_action_version(bid, state["actor"], expected_id)
        result = {"error": str(exc), "reply": str(exc)}
    state["proposal"] = result
    return result


# --------------------------------------------------- Correcciones habladas ---
# Con la revisión encendida, la conversación de cada día es «propongo → confirmas
# o corriges». Corregir solo funcionaba escribiendo «corregir:» y repitiendo la
# orden entera: «no, eran 120» soltaba el parte del día y, peor, descartaba la
# propuesta, así que había que reescribirlo todo. Aquí se entienden los cambios
# como se dicen, **y solo cambian lo que se nombra**: una corrección de importe
# no toca el cliente ni el concepto.
_ARRANQUE = r"^(?:no\s*,?\s*)?(?:que\s+)?"
_VERBO_CAMBIO = (r"(?:eran?|son|es|seran?|serian?|mejor|ponle|pon|dejalo en|"
                 r"cambialo a|cambiala a|cambia a|que sean?)")


def _correccion(text: str, tool: str, args: dict) -> dict | None:
    """Lo que cambia de una propuesta ya hecha. `None` si no es una corrección."""
    if tool not in {"crear_factura", "crear_presupuesto", "registrar_gasto"}:
        return None
    crudo = str(text or "").strip().strip(".!¡")
    norm = nlu._norm(crudo)
    cambios: dict = {}

    # Importe: «no, eran 120», «mejor 120 euros», o la cifra a secas.
    importe = (re.fullmatch(_ARRANQUE + rf"{_VERBO_CAMBIO}\s+({nlu._AMOUNT_RE})"
                            r"\s*(?:€|euros?|eur)?", norm)
               or re.fullmatch(_ARRANQUE + rf"({nlu._AMOUNT_RE})\s*(?:€|euros?|eur)",
                               norm))
    if importe:
        valor = nlu._amount_value(importe.group(1))
        if valor > 0:
            cambios["importe" if tool == "registrar_gasto" else "base"] = valor

    # IVA e IRPF: «con IVA incluido», «ponle 10% de IVA», «15% de IRPF».
    if re.search(r"\biva\s*(?:incluido|inclos|dentro)\b|\bcon\s+el\s+iva\b", norm):
        cambios["importe_incluye_iva"] = True
    tipo_iva = re.search(r"(?:iva\s*(?:del|al)?\s*(0|4|10|21)|(0|4|10|21)\s*%?\s*"
                         r"(?:de\s+)?iva)\b", norm)
    if tipo_iva:
        cambios["iva"] = float(tipo_iva.group(1) or tipo_iva.group(2))
    tipo_irpf = re.search(r"(?:irpf\s*(?:del|al)?\s*(0|7|15)|(0|7|15)\s*%?\s*"
                          r"(?:de\s+)?irpf)\b", norm)
    if tipo_irpf:
        cambios["irpf"] = float(tipo_irpf.group(1) or tipo_irpf.group(2))

    # Cliente: «es para Pedro», «el cliente es Pedro».
    quien = re.match(_ARRANQUE + r"(?:es\s+)?(?:para|el cliente es|"
                     r"la cliente es|cliente:?)\s+(.+)$", norm)
    if quien and tool != "registrar_gasto":
        nombre = nlu._limpiar_cliente(crudo[quien.start(1):].strip())
        if nombre:
            cambios["cliente"] = nombre
            cambios["cliente_id"] = None

    # Concepto: «el concepto es ventana», «concepto: ventana».
    que = re.match(_ARRANQUE + r"(?:el\s+)?concepto\s*(?:es|:)?\s+(.+)$", norm)
    if que:
        concepto = nlu._limpiar_concepto(crudo[que.start(1):].strip())
        if concepto:
            cambios["concepto"] = concepto

    if not cambios:
        return None
    # Lo que no se nombra no se toca: se parte de la propuesta vigente.
    revisado = {**args, **cambios}
    revisado.pop("lineas", None)  # una corrección simple no rehace las líneas
    return revisado


def respond(bid: int, actor: str, text: str) -> dict | None:
    """Consume una propuesta exacta; no interpreta de nuevo lo confirmado."""
    norm = nlu._norm(text)
    # «si, genera el pdf» es un sí: antes no lo era, la propuesta se quedaba sin
    # confirmar y la frase se reinterpretaba como una petición nueva. Lo que
    # cambie la operación —una cifra, un «pero»— sigue sin ser un sí.
    yes = nlu.es_confirmacion(text)
    no = norm in {"no", "descartar", "ahora no"}
    if not yes and not no:
        if local_invoice.enabled():
            pending = db.get_pending_action(bid, actor)
            if pending and pending["kind"] == "reviewed_tool":
                payload = json.loads(pending["payload"])
                if payload.get("tool") == "crear_factura":
                    try:
                        revised = local_invoice.revise(text, payload["args"])
                    except (ValueError, ArithmeticError) as exc:
                        db.discard_pending_action_version(bid, actor, pending["id"])
                        return {"reply": str(exc) + " La propuesta anterior queda descartada.", "source": "local"}
                    if revised is not None:
                        token = context.set({"actor": actor})
                        try:
                            return {**propose(bid, "crear_factura", revised, expected_id=pending["id"]), "source": "local"}
                        finally:
                            context.reset(token)
        # Corrección hablada sobre cualquier propuesta pendiente, sin depender
        # del planificador local ni de que la factura tenga varias líneas.
        pendiente = db.get_pending_action(bid, actor)
        if pendiente and pendiente["kind"] == "reviewed_tool":
            guardado = json.loads(pendiente["payload"])
            revisado = _correccion(text, guardado.get("tool"), guardado["args"])
            if revisado is not None:
                token = context.set({"actor": actor})
                try:
                    return {**propose(bid, guardado["tool"], revisado,
                                      expected_id=pendiente["id"]),
                            "source": "local"}
                except ValueError as exc:
                    db.discard_pending_action_version(bid, actor, pendiente["id"])
                    return {"reply": f"{exc} La propuesta anterior queda "
                                     "descartada.", "source": "local"}
                finally:
                    context.reset(token)
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
        from .conversation_plan import expected_invoice, invoice_fingerprint
        expected = None
        if payload["tool"] == "enviar_factura":
            invoice = current["invoice"]
            expected = (bid, invoice["id"], invoice_fingerprint(invoice, current["lines"]))
        token = expected_invoice.set(expected)
        try:
            result = json.loads(run_tool(payload["tool"], args, bid, channel="whatsapp" if actor.startswith("wa:") else "web"))
        finally:
            expected_invoice.reset(token)
        outcome = "failed" if result.get("error") or result.get("ok") is False else "completed"
        response = {"reply": nlu.format_reply(payload["tool"], result), "source": "local", "action_result": outcome, "proposal_id": pending["id"]}
        if outcome == "completed" and result.get("factura"):
            response["invoice_ids"] = [result["factura"]["id"]]
        return response
    except (ValueError, TypeError) as exc:
        return {"reply": str(exc) + " No he repetido la operación.", "source": "local", "action_result": "failed"}
