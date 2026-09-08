"""Aprendizaje supervisado por negocio: nunca entrena ni cambia permisos.

Las correcciones generan ofertas efímeras. Solo APRENDER, después de una acción
confirmada, crea una equivalencia exacta. El texto aprendido no es un prompt.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta

from . import config, db, nlu

log = logging.getLogger(__name__)
VERSION = 1
SCOPE = "language_rule"
EVENTS = ("turn", "unclear", "proposed", "corrected", "completed", "failed",
          "discarded", "rule_used", "rule_approved", "rule_invalid", "rule_forgotten")
ALLOWED = {"registrar_gasto", "crear_factura", "crear_presupuesto", "crear_cliente",
           "crear_proveedor", "agendar_trabajo"}


def enabled() -> bool:
    return config.ASSISTANT_LEARNING_ENABLED and config.ASSISTANT_REVIEW_ENABLED


def observe(bid: int, event: str) -> None:
    if not enabled() or event not in EVENTS:
        return
    try:
        db.record_product_event(bid, "assistant_learning_" + event, '{"version":1}')
    except Exception:  # noqa: BLE001 - la telemetría nunca repite ni bloquea una acción
        log.warning("No se pudo registrar telemetría de aprendizaje.")


def _key(actor: str) -> str:
    return "learn:" + actor


def _pending(bid: int, actor: str):
    row = db.get_pending_action(bid, _key(actor))
    if not row:
        return None
    try:
        return {"kind": row["kind"], **json.loads(row["payload"])}
    except (ValueError, TypeError):
        db.clear_pending_action(bid, _key(actor))
        return None


def _save(bid: int, actor: str, kind: str, payload: dict):
    db.set_pending_action(bid, _key(actor), kind, payload, ttl_minutes=15)


def _clarify(bid: int, actor: str, text: str) -> dict | None:
    key = "clarify:" + actor
    row = db.get_pending_action(bid, key)
    if not row:
        return None
    payload = json.loads(row["payload"])
    amount_answer = payload["field"] == "amount" and re.fullmatch(
        rf"{_AMOUNT_RE_FOR_CLARIFICATION}\s*(?:€|euros?|eur)?\s*(iva incluido|mas iva)", nlu._norm(text))
    if nlu.safety_refusal(text) or (nlu.parse(text) is not None and not amount_answer) or nlu._norm(text).startswith("corregir:"):
        db.clear_pending_action(bid, key)
        return None
    args = payload.get("args", {})
    field = payload["field"]
    if field == "client":
        try:
            client = db.resolve_client_reference(text.strip(), bid)
        except ValueError as exc:
            return {"reply": str(exc), "needs_clarification": True}
        if not client:
            return {"reply": "No encuentro ese cliente. Dime su nombre completo o crea su ficha primero.", "needs_clarification": True}
        args["cliente"] = client["name"]
        field, reply = "concept", "¿Qué trabajo quieres facturar? Dime el concepto."
    elif field == "concept":
        if not 3 <= len(text.strip()) <= 200:
            return {"reply": "Dime un concepto de entre 3 y 200 caracteres.", "needs_clarification": True}
        args["concepto"] = text.strip()
        field, reply = "amount", "¿Qué importe? Indica si es «IVA incluido» o «más IVA»; por ejemplo, «121 euros IVA incluido»."
    else:
        amount = re.fullmatch(rf"({_AMOUNT_RE_FOR_CLARIFICATION})\s*(?:€|euros?|eur)?\s*(iva incluido|mas iva)", nlu._norm(text))
        if not amount:
            return {"reply": "Necesito importe e impuestos claros: «121 euros IVA incluido» o «100 euros más IVA».", "needs_clarification": True}
        args.update(base=nlu._amount_value(amount[1]), importe_incluye_iva=amount[2] == "iva incluido", tipo_factura="F1")
        db.clear_pending_action(bid, key)
        return {"tool_call": {"name": "crear_factura", "args": args}}
    db.set_pending_action(bid, key, "invoice_clarification", {"field": field, "args": args}, ttl_minutes=15)
    return {"reply": reply + " No he creado la factura.", "needs_clarification": True}


_AMOUNT_RE_FOR_CLARIFICATION = nlu._AMOUNT_RE


def _validate(phrase: str, command: str) -> str:
    if not (3 <= len(phrase) <= 300 and 3 <= len(command) <= 500):
        raise ValueError("La expresión es demasiado corta o larga.")
    if nlu.safety_refusal(phrase) or nlu.safety_refusal(command):
        raise ValueError("No puedo aprender una equivalencia que eluda una protección.")
    if nlu.parse(phrase) is not None or re.search(r"\b(aprender|olvidar|corregir|si|no)\b", nlu._norm(phrase)):
        raise ValueError("Esta expresión ya tiene significado o es una respuesta de control.")
    parsed = nlu.parse(command)
    if not parsed or parsed[0] not in ALLOWED:
        raise ValueError("Esta orden todavía no admite aprendizaje seguro.")
    if re.search(r"\b(hoy|manana|demà|ayer|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", nlu._norm(command)):
        raise ValueError("No guardaré fechas relativas como una instrucción permanente.")
    return json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def rules(bid: int) -> list[dict]:
    output = []
    for row in db.list_memories(bid, scope_type=SCOPE):
        try:
            payload = json.loads(row["memory_value"])
            if row["user_confirmed"] and payload.get("version") == VERSION:
                output.append({"id": row["id"], "phrase": payload["phrase"], "command": payload["command"]})
        except (ValueError, TypeError, KeyError):
            continue
    return output


def prepare(bid: int, actor: str, text: str) -> dict:
    """Nunca ejecuta negocio: resuelve comandos de memoria o una equivalencia."""
    result = {"message": text, "original": text}
    norm = nlu._norm(text)
    pending = _pending(bid, actor)
    if norm in {"no", "descartar", "ahora no"}:
        db.clear_pending_action(bid, _key(actor))
        db.clear_pending_action(bid, "clarify:" + actor)
    if norm == "mis expresiones":
        entries = rules(bid)
        detail = "\n".join(f"{r['id']}. «{r['phrase']}» significa «{r['command']}»" for r in entries)
        result["reply"] = (detail + "\nPara borrar una, escribe «olvidar expresión N»." if entries
                           else "No has aprobado ninguna expresión. No aprendo instrucciones en silencio.")
        return result
    forget = re.fullmatch(r"olvidar expresion (\d+)", norm)
    if forget:
        own = next((r for r in rules(bid) if r["id"] == int(forget[1])), None)
        if own:
            db.delete_memory(bid, own["id"])
            observe(bid, "rule_forgotten")
        result["reply"] = "Expresión olvidada." if own else "No encuentro esa expresión en tu negocio."
        return result
    if norm == "aprender":
        if not pending or pending["kind"] != "learning_offer":
            result["reply"] = "No hay una corrección completada pendiente de aprender en esta conversación."
            return result
        try:
            signature = _validate(pending["phrase"], pending["command"])
            if signature != pending["signature"]:
                raise ValueError("La interpretación ha cambiado; revísala otra vez.")
            if len(rules(bid)) >= 100:
                raise ValueError("Ya tienes 100 expresiones. Revisa y elimina las que no uses.")
            key = "phrase_" + hashlib.sha256(nlu._norm(pending["phrase"]).encode()).hexdigest()[:40]
            value = json.dumps({"version": VERSION, "phrase": pending["phrase"],
                                "command": pending["command"], "signature": signature}, ensure_ascii=False)
            if len(value) > 2000:
                raise ValueError("La equivalencia es demasiado larga para guardarla con seguridad.")
            db.remember(bid, key, value,
                        scope_type=SCOPE, source="confirmed_correction", user_confirmed=True)
            observe(bid, "rule_approved")
            result["reply"] = ("Recordaré esa expresión solo para tu negocio. Cada uso volverá a mostrar "
                               "cliente, importe y acción para confirmar. Puedes verla en «mis expresiones».")
        except (ValueError, TypeError, KeyError) as exc:
            result["reply"] = str(exc)
        db.clear_pending_action(bid, _key(actor))
        return result
    clarification = _clarify(bid, actor, text)
    if clarification:
        return {**result, **clarification, "guided": True}
    if norm.startswith("corregir:"):
        if pending and pending["kind"] == "learning_unclear":
            result["candidate"] = {"phrase": pending["phrase"], "command": text.split(":", 1)[1].strip()}
        observe(bid, "corrected")
        return result
    if norm in {"si", "confirmo", "confirmar", "si, confirmar", "no", "descartar", "ahora no"}:
        return result
    if pending:
        db.clear_pending_action(bid, _key(actor))
    # Una memoria no puede reinterpretar órdenes ya conocidas o peligrosas.
    if nlu.parse(text) is not None or nlu.safety_refusal(text):
        return result
    for row in db.list_memories(bid, scope_type=SCOPE):
        try:
            rule = json.loads(row["memory_value"])
            if not row["user_confirmed"] or rule.get("version") != VERSION or nlu._norm(rule["phrase"]) != norm:
                continue
            if _validate(rule["phrase"], rule["command"]) != rule["signature"]:
                raise ValueError("Interpretación modificada")
            result.update(message=rule["command"], learned=True)
            observe(bid, "rule_used")
            break
        except (ValueError, TypeError, KeyError):
            observe(bid, "rule_invalid")
    return result


def finish(bid: int, actor: str, turn: dict, result: dict) -> dict:
    observe(bid, "turn")
    if result.get("clarification_kind") == "invoice":
        db.set_pending_action(bid, "clarify:" + actor, "invoice_clarification",
                              {"field": "client", "args": {}}, ttl_minutes=15)
        result.update(reply="Vamos paso a paso. ¿A qué cliente quieres hacer la factura? Dime el nombre completo. No he creado nada.", needs_clarification=True)
    if result.get("needs_clarification"):
        observe(bid, "unclear")
        phrase = turn["original"]
        if not turn.get("guided") and len(phrase) <= 300 and nlu.parse(phrase) is None and not nlu.safety_refusal(phrase):
            _save(bid, actor, "learning_unclear", {"phrase": phrase})
    if result.get("confirmation_required"):
        observe(bid, "proposed")
        candidate = turn.get("candidate")
        if candidate:
            try:
                signature = _validate(candidate["phrase"], candidate["command"])
                _save(bid, actor, "learning_candidate", {**candidate, "signature": signature,
                      "proposal_id": result["proposal_id"]})
            except (ValueError, TypeError):
                db.clear_pending_action(bid, _key(actor))
    outcome = result.get("action_result")
    if outcome in {"completed", "failed", "discarded"}:
        observe(bid, outcome)
        pending = _pending(bid, actor)
        if (outcome == "completed" and pending and pending["kind"] == "learning_candidate"
                and pending.get("proposal_id") == result.get("proposal_id")):
            payload = {k: v for k, v in pending.items() if k != "kind"}
            _save(bid, actor, "learning_offer", payload)
            result["reply"] += (f"\n\nSi quieres que recuerde «{pending['phrase']}» como "
                                f"«{pending['command']}», escribe APRENDER. No se guardará sin tu aprobación.")
        elif pending:
            db.clear_pending_action(bid, _key(actor))
    if turn.get("learned"):
        result["reply"] = "He usado una expresión que aprobaste.\n\n" + result["reply"]
    return result


def report(bid: int, days: int = 7) -> dict:
    days = max(1, min(int(days), 90))
    since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    counts = {name: db.count_product_events(bid, "assistant_learning_" + name, since) for name in EVENTS}
    return {"enabled": enabled(), "days": days, "events": counts, "approved_rules": len(rules(bid)),
            "interpretation": "Recuentos de eventos, no precisión del modelo ni usuarios únicos.",
            "next_step": "Revisar aclaraciones y correcciones con ejemplos sintéticos antes de cambiar reglas o modelo."}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Informe local sin mensajes ni datos de clientes")
    parser.add_argument("--business-id", type=int, required=True)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    print(json.dumps(report(args.business_id, args.days), ensure_ascii=False, indent=2))
