"""Propuestas acotadas, persistentes y de un solo uso para ambos canales.

No ejecuta texto otra vez al confirmar: conserva los argumentos y la identidad
revisada. La reclamación atómica evita duplicados entre procesos del servidor.
"""
from __future__ import annotations

import json
import re
from contextvars import ContextVar
from decimal import Decimal, ROUND_HALF_UP

from . import config, db, nlu, local_invoice

context: ContextVar[dict | None] = ContextVar("action_review", default=None)
READS = {
    "ver_agenda", "ver_gastos", "ver_cobros_pendientes", "resumen_negocio", "ver_impuestos",
    "listar_clientes", "ver_cliente", "ver_presupuestos", "ver_perfil_cliente", "ver_proyectos", "ver_proyecto",
    "ver_equipo", "ver_documentos_pendientes", "ver_solicitudes_gestoria",
    "ver_control_noesis",
}
LABELS = {
    "crear_cliente": "Guardar cliente", "crear_proveedor": "Guardar proveedor",
    "actualizar_cliente": "Actualizar datos del cliente",
    "crear_factura": "Preparar factura borrador", "crear_presupuesto": "Preparar presupuesto",
    "agendar_trabajo": "Agendar trabajo", "registrar_gasto": "Registrar gasto",
    "terminar_trabajo": "Marcar trabajo como hecho",
    "registrar_pago": "Registrar el saldo pendiente como cobrado",
    "enviar_factura": "Emitir factura (la entrega se gestiona por separado)",
    "entregar_factura": "Entregar la factura al cliente",
}



# Dónde se hace en la web lo que por WhatsApp aún no se prepara.
_SECCION_DE_TOOL = {
    "crear_proyecto": ("Proyectos", "proyectos"),
    "crear_tarea_proyecto": ("Proyectos", "proyectos"),
    "preparar_factura_trabajo": ("Facturas", "facturas"),
}


def _muestra_irpf(bid: int, irpf) -> bool:
    """El IRPF se enseña si se aplica o si el negocio suele aplicarlo: un 0 % que
    se aparta de lo habitual es un dato; un 0 % de siempre es ruido."""
    if float(irpf or 0):
        return True
    return bool(float((db.get_business(bid) or {}).get("default_irpf") or 0))

def _preview(bid: int, tool: str, args: dict) -> tuple[str, dict]:
    if tool not in LABELS:
        nombre, ruta = _SECCION_DE_TOOL.get(tool, ("Inicio", "resumen"))
        raise ValueError(
            f"Esto todavía no lo preparo por WhatsApp. Hazlo en la web, en {nombre}: "
            f"{config.BASE_URL}/b/{bid}/{ruta}. No he cambiado nada.")
    lines = [LABELS[tool]]
    if tool == "crear_factura" and args.get("tipo_factura") == "F2":
        lines[0] = "Preparar ticket de venta borrador"
    snapshot = {}
    if tool in {"crear_factura", "crear_presupuesto", "agendar_trabajo"}:
        name = str(args.get("cliente") or "").strip()
        mostrador = not name and args.get("tipo_factura") == "F2"
        if mostrador:
            name = "Cliente de mostrador"
        if not name:
            raise ValueError("Falta el cliente. No elegiré uno por mi cuenta.")
        client = db.resolve_client_reference(name, bid)
        if mostrador and not client:
            # Un ticket sin comprador es una venta de mostrador: no hay ficha que
            # elegir. Con la revisión encendida esto fallaba pidiendo crear la
            # ficha «Cliente de mostrador», y los tickets no salían.
            lines.append("Cliente: venta de mostrador, sin datos del comprador")
        elif client:
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
        # Lo dictado junto al nombre también se guarda: que se vea en la tarjeta.
        for clave, etiqueta in (("telefono", "Teléfono"), ("email", "Correo"),
                                ("nif", "NIF"), ("direccion", "Dirección")):
            if args.get(clave):
                aviso = ""
                if clave == "nif":
                    from .fiscal_validation import valid_spanish_tax_id
                    if not valid_spanish_tax_id(args[clave]):
                        aviso = " ⚠️ no es válido: no lo guardaré"
                lines.append(f"{etiqueta}: {args[clave]}{aviso}")
        if tool == "crear_cliente":
            from .tools import ficha_para_alta
            existing = ficha_para_alta(name, bid)
            if existing:
                args["nombre"] = existing["name"]
                snapshot["client"] = {k: existing.get(k) for k in ("id", "name", "nif")}
                lines.append(f"Reutilizaré la ficha existente: {existing['name']} · #{existing['id']}")
    if tool == "terminar_trabajo":
        from .tools import trabajo_abierto_de
        ficha, trabajo = trabajo_abierto_de(bid, str(args.get("cliente") or ""))
        if not ficha:
            raise ValueError(f"No tengo ficha de cliente «{args.get('cliente')}». No he cambiado nada.")
        if not trabajo:
            raise ValueError(f"{ficha['name']} no tiene ningún trabajo abierto que cerrar. "
                             "No he cambiado nada.")
        args["cliente"] = ficha["name"]
        snapshot["job"] = {"id": trabajo["id"], "status": trabajo.get("status")}
        lines.extend([f"Cliente: {ficha['name']} · ficha #{ficha['id']}",
                      f"Trabajo: {trabajo.get('description') or 'Trabajo'}",
                      f"Cuándo: {nlu.dia_humano(trabajo.get('scheduled_for')) or 'sin día'}",
                      "Solo cambia el estado: la factura se pide aparte."])
    if tool == "actualizar_cliente":
        from .tools import datos_de_cliente_validos
        nombre = str(args.get("cliente") or "").strip()
        ficha = db.resolve_client_reference(nombre, bid) if nombre else None
        if not ficha:
            raise ValueError(f"No tengo ficha de cliente «{nombre}». Créala con «crea el "
                             f"cliente {nombre}» y dime sus datos. No he cambiado nada.")
        datos, avisos = datos_de_cliente_validos(args)
        if avisos and not datos:
            raise ValueError(" ".join(avisos) + " No he cambiado nada.")
        args["cliente"] = ficha["name"]
        lines.append(f"Cliente: {ficha['name']} · ficha #{ficha['id']}")
        snapshot["client"] = {k: ficha.get(k) for k in ("id", "name", *datos)}
        etiquetas = {"phone": "Teléfono", "email": "Correo", "nif": "NIF",
                     "address": "Dirección"}
        for columna, valor in datos.items():
            antes = ficha.get(columna)
            lines.append(f"{etiquetas[columna]}: {valor}" if not antes else
                         f"{etiquetas[columna]}: {antes} → {valor}" if antes != valor else
                         f"{etiquetas[columna]}: {valor} (ya lo tenía)")
        lines.extend(f"⚠️ {aviso}" for aviso in avisos)
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
        lines.extend([f"Concepto: {args.get('concepto', 'Servicio')}", f"Base: {nlu._eur(base)} · IVA {float(vat):g} %" + (f" · IRPF {float(irpf):g} %" if _muestra_irpf(bid, irpf) else ""), f"Total: {nlu._eur(total)}"])
    if tool == "registrar_gasto":
        if args.get("proyecto_id"):
            raise ValueError("Para asignar el gasto a un proyecto, revisa primero el proyecto en Costes. No he asignado nada.")
        amount = Decimal(str(args.get("importe", 0)))
        if not amount.is_finite() or amount <= 0:
            raise ValueError("El gasto debe tener un importe positivo.")
        lines.extend([f"Concepto: {args.get('concepto') or 'Gasto'}", f"Importe: {nlu._eur(amount)}", "Destino: gastos generales del negocio; sin asignación a cliente."])
    if tool == "agendar_trabajo":
        lines.extend([f"Trabajo: {args.get('descripcion') or 'Trabajo'}", f"Cuándo: {nlu.dia_humano(args.get('fecha_hora')) or 'sin día'}", f"Lugar: {args.get('zona') or 'sin especificar'}"])
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
        if tool == "enviar_factura" and invoice.get("status") == "borrador" \
                and invoice.get("invoice_type") != "F2":
            from .fiscal_validation import problema_nif_cliente
            nif_malo = problema_nif_cliente((client or {}).get("nif"))
            if nif_malo:
                raise ValueError(f"No la emito: {nif_malo}. Corrígelo con «el NIF de "
                                 f"{(client or {}).get('name')} es …» o en Clientes.")
        referencia = invoice.get("number") or f"#{invoice['id']}"
        lines.extend([f"Factura {referencia} · {invoice.get('client_name')}", f"Total: {nlu._eur(invoice['total'])}", f"Estado: {invoice['status']}"])
        if tool == "registrar_pago":
            if invoice.get("status") == "borrador" or not invoice.get("number"):
                # Se enseñaba la tarjeta «Estado: borrador» y el SÍ acababa en error.
                raise ValueError(
                    f"La factura #{invoice['id']} todavía es un borrador: no se puede "
                    "cobrar lo que no se ha emitido. Emítela primero con «emitir "
                    f"factura {invoice['id']}» y después dime que está cobrada.")
            if invoice.get("status") == "cobrada":
                raise ValueError(f"La factura {invoice.get('number')} ya consta como "
                                 "cobrada. No he cambiado nada.")
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
    if tool == "agendar_trabajo":
        return _correccion_de_cita(text, args)
    if tool not in {"crear_factura", "crear_presupuesto", "registrar_gasto"}:
        return None
    crudo = str(text or "").strip().strip(".!¡")
    norm = nlu._norm(crudo)
    # No convertir una consulta fiscal en una corrección por encontrar «IVA».
    if "?" in crudo or "¿" in crudo or re.match(r"^(?:que(?!\s+sean?\b)|cuanto|como|por que|quin|quant)\b", norm):
        return None
    # Separar solo ante un campo explícito: «Pedro y Ana» sigue siendo un nombre
    # y la coma decimal nunca es un separador. Todo se valida antes de proponer.
    separador = (r"\s*;\s*|(?:\s+(?:y|i)\s+|,\s+)(?="
                 r"(?:el\s+)?(?:cliente|concepto|importe|iva|irpf)\b|"
                 r"(?:es\s+)?para\b|(?:con\s+)?iva\b|"
                 r"\d+(?:\s*%)(?:\s+de)?\s+(?:iva|irpf)\b)")
    cortes = list(re.finditer(separador, norm))
    if cortes:
        partes, inicio = [], 0
        for corte in cortes:
            partes.append(crudo[inicio:corte.start()])
            inicio = corte.end()
        partes.append(crudo[inicio:])
        if len(partes) > 6:
            raise ValueError("Indica como máximo seis cambios en cada mensaje.")
        revisado = dict(args)
        for numero, parte in enumerate(partes):
            cambio = _correccion(parte, tool, revisado)
            if cambio is None:
                if numero == 0:
                    return None
                raise ValueError("No he entendido todos los cambios. Indica cada campo y su valor.")
            revisado = cambio
        return revisado
    cambios: dict = {}

    # Importe: «no, eran 120», «mejor 120 euros», o la cifra a secas.
    importe = (re.fullmatch(_ARRANQUE + rf"(?:{_VERBO_CAMBIO}|(?:el\s+)?importe\s*(?:es|:))\s+({nlu._AMOUNT_RE})"
                            r"\s*(?:€|euros?|eur)?", norm)
               or re.fullmatch(_ARRANQUE + rf"({nlu._AMOUNT_RE})\s*(?:€|euros?|eur)",
                               norm))
    if importe:
        valor = nlu._amount_value(importe.group(1))
        if valor > 0:
            cambios["importe" if tool == "registrar_gasto" else "base"] = valor

    # IVA e IRPF: «con IVA incluido», «ponle 10% de IVA», «15% de IRPF».
    if re.fullmatch(r"(?:con\s+(?:el\s+)?)?iva\s*(?:incluido|inclos|dentro)|con\s+el\s+iva", norm):
        cambios["importe_incluye_iva"] = True
    prefijo_tipo = _ARRANQUE + r"(?:(?:y|i|ponle|pon|con)\s+)?"
    tipo_iva = re.fullmatch(prefijo_tipo + r"(?:iva\s*(?:del|al)?\s*(0|4|10|21)\s*%?|(0|4|10|21)\s*%?\s*"
                         r"(?:de\s+)?iva)", norm)
    if tipo_iva:
        cambios["iva"] = float(tipo_iva.group(1) or tipo_iva.group(2))
    tipo_irpf = re.fullmatch(prefijo_tipo + r"(?:irpf\s*(?:del|al)?\s*(0|7|15)\s*%?|(0|7|15)\s*%?\s*"
                          r"(?:de\s+)?irpf)", norm)
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
    if args.get("lineas"):
        # Cliente e IRPF no deben borrar el desglose. Cambiar
        # un total o el IVA de varias líneas exige indicar cómo repartirlo.
        if any(key in cambios for key in ("base", "iva", "importe_incluye_iva", "concepto")):
            raise ValueError("La factura tiene varias líneas. Indica qué línea y "
                             "precio, cantidad, concepto o IVA quieres corregir.")
        revisado["lineas"] = [dict(line) for line in args["lineas"]]
    return revisado


def _correccion_de_cita(text: str, args: dict) -> dict | None:
    """«Mejor a las 11», «el lunes», «en Badalona»: solo cambia lo que se nombra.

    Antes no se entendía: la propuesta se descartaba y la IA contestaba con una
    tarjeta «corregida» que no existía, así que el SÍ no agendaba nada.
    """
    crudo = str(text or "").strip().strip(".!¡")
    norm = nlu._norm(crudo)
    if ("?" in crudo or "¿" in crudo or len(norm.split()) > 9
            or re.search(r"\b(?:agend\w*|factur\w*|presupuest\w*|gast\w*|cliente\s+nuevo)\b", norm)):
        return None
    cambios: dict = {}
    anterior = str(args.get("fecha_hora") or "")
    dia_anterior, _, hora_anterior = anterior.partition("T")
    fecha = nlu.parse_date(crudo)
    hora = nlu._parse_time(norm)
    if fecha and "T" in fecha:
        cambios["fecha_hora"] = fecha
    elif fecha:
        cambios["fecha_hora"] = fecha + ("T" + hora_anterior if hora_anterior else "")
    elif hora and dia_anterior:
        h = hora[0]
        # «Mejor a las seis» sobre una cita de las 17:00 son las 18:00, no las 6.
        antes = int(hora_anterior[:2]) if hora_anterior[:2].isdigit() else 0
        if (antes >= 13 and 1 <= h <= 11
                and not re.search(r"manana|madrugada|mati\b", norm)):
            h += 12
        cambios["fecha_hora"] = f"{dia_anterior}T{h:02d}:{hora[1]:02d}"
    lugar = re.match(r"^(?:no\s*,?\s*)?(?:mejor\s+|es\s+|que\s+sea\s+|sera\s+)?en\s+(.+)$", norm)
    if lugar and not fecha and not hora:
        zona = crudo[len(crudo) - len(lugar.group(1)):].strip(" ,.")
        if zona and len(zona) <= 80:
            cambios["zona"] = zona
    quien = re.match(r"^(?:no\s*,?\s*)?(?:el cliente es|la cliente es|cliente:?)\s+(.+)$", norm)
    if quien:
        nombre = nlu._limpiar_cliente(crudo[len(crudo) - len(quien.group(1)):].strip())
        if nombre:
            cambios.update(cliente=nombre, cliente_id=None)
    que = re.match(r"^(?:no\s*,?\s*)?(?:el\s+)?trabajo\s*(?:es|:)\s*(.+)$", norm)
    if que:
        cambios["descripcion"] = crudo[len(crudo) - len(que.group(1)):].strip(" ,.")
    if not cambios:
        return None
    return {**args, **cambios}


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
            try:
                revisado = _correccion(text, guardado.get("tool"), guardado["args"])
            except ValueError as exc:
                db.discard_pending_action_version(bid, actor, pendiente["id"])
                return {"reply": f"{exc} La propuesta anterior queda descartada.",
                        "source": "local"}
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
