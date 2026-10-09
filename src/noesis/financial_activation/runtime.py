"""Frontera común de generación/capability; no routing ni autoridad humana nueva."""

import json

from noesis import config
from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import StateError
from .capabilities import capability_for_command
from .contracts import Profile, digest


class ActivationUnavailable(StateError):
    """Fail closed después de ever_enabled; nunca fallback financiero legacy."""


def control(session, business_id):
    if not isinstance(session, FinancialSession):
        session = FinancialSession(session)
    if session.dialect == "postgres":
        installed = session.execute("SELECT to_regclass('financial_activation_control') AS name").fetchone()["name"]
    else:
        installed = session.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='financial_activation_control'").fetchone()
    if not installed:
        return None
    return session.execute("SELECT * FROM financial_activation_control WHERE business_id=?", (business_id,)).fetchone()


def binding(session, business_id, request, operation=None):
    row = control(session, business_id)
    if not row or not row["ever_enabled"]:
        return None
    if not config.FINANCIAL_CORE_ENABLED or row["state"] != "enabled":
        raise ActivationUnavailable("Nuevos efectos financieros no disponibles; no existe fallback legacy.")
    capability = capability_for_command(request.command_type).value
    generation = row["activation_generation"]
    if operation is not None and (operation.get("activation_generation") != generation or operation.get("activation_capability") != capability):
        raise ActivationUnavailable("Operación de otra generación/capability; requiere nueva propuesta.")
    grant = session.execute("SELECT * FROM financial_activation_grants WHERE business_id=? AND activation_generation=? AND capability=?", (business_id, generation, capability)).fetchone()
    if not grant:
        raise ActivationUnavailable("Capability no concedida en esta generación.")
    evaluation = session.execute('SELECT context_canonical,profile_canonical FROM financial_readiness_evaluations WHERE business_id=? AND evaluation_uuid=?', (business_id, str(grant['evaluation_uuid']))).fetchone()
    business = session.execute('SELECT id,subscription_status,trial_ends_at,is_demo,verifactu_enabled,name,nif,address FROM businesses WHERE id=?', (business_id,)).fetchone()
    profile = json.loads(evaluation['profile_canonical'])
    closure, _ = Profile(tuple(profile['capabilities']), profile['profile_version']).closure(fiscal_cancel_required=bool(business['verifactu_enabled']))
    original = session.execute('SELECT r.request_canonical FROM financial_activation_generations g JOIN financial_activation_requests r ON r.business_id=g.business_id AND r.request_uuid=g.request_uuid WHERE g.business_id=? AND g.activation_generation=?', (business_id, generation)).fetchone()
    from .configuration_snapshot import configuration_hash
    if (json.loads(grant['closure_canonical']) != [c.value for c in closure]
            or configuration_hash(session, business_id) != json.loads(original['request_canonical'])['configuration_hash']):
        raise ActivationUnavailable('Configuración/closure cambió; no usar grants antiguos.')
    proof = json.loads(grant["proof_canonical"])
    if (digest(proof) != grant["proof_hash"] or proof["capability"] != capability or proof["result"] != "eligible"):
        raise ActivationUnavailable("Grant durable corrupto.")
    return dict(version=1, business_id=business_id, generation=generation, capability=capability,
                availability=True, request_hash=request.request_hash)


def require_context(session, business_id, *, commands=None, operation_uuid=None):
    row = control(session, business_id)
    if not row or not row["ever_enabled"]:
        return
    if not isinstance(session, FinancialSession):
        session = FinancialSession(session)
    if not config.FINANCIAL_CORE_ENABLED or row["state"] != "enabled":
        raise ActivationUnavailable("Negocio financiero pausado/no disponible.")
    context = session.execute("SELECT noesis_execution_context() AS proof").fetchone()["proof"]
    if isinstance(context, str):
        context = json.loads(context)
    if (context.get("kind") != "effect" or context.get("business_id") != business_id
            or context.get("generation") != row["activation_generation"] or context.get("availability") is not True):
        raise ActivationUnavailable("La escritura requiere la TX financiera autorizada.")
    operation = session.execute("SELECT * FROM financial_operations WHERE business_id=? AND operation_uuid=?", (business_id, context.get("operation_uuid"))).fetchone()
    if not operation or operation["state"] != "approved" or (commands is not None and operation["command_type"] not in commands):
        raise ActivationUnavailable("Operación/capability no válida para el writer.")
    if operation_uuid is not None and str(operation["operation_uuid"]) != str(operation_uuid):
        raise ActivationUnavailable("El contexto pertenece a otra operación.")
    from noesis.financial_operations.contracts import FinancialRequest
    expected = binding(session, business_id, FinancialRequest.from_canonical(operation["request_canonical"]), operation)
    if any(context.get(k) != expected[k] for k in ("generation", "capability", "request_hash")):
        raise ActivationUnavailable("Contexto no corresponde al request/generation/grant.")
    return context


def require_writer(connection, business_id, mutation):
    if mutation in ("_mutate_add_invoice", "_mutate_create_rectifying_invoice"):
        return  # Solo crean borradores: ningún hecho ni evento económico.
    if mutation in ('_mutate_suggest_bank_transaction', '_mutate_ignore_bank_transaction'):
        return  # Preparación operativa; SQL protege importe/import/match final.
    tables = {
        "_mutate_issue_invoice": "invoice_records",
        "_mutate_create_invoice_cancellation_record": "invoice_cancellation_records",
        "_mutate_add_invoice_payment": "invoice_payments",
        "_mutate_mark_invoice_paid": "invoice_payments",
        "_mutate_add_received_invoice": "received_invoices",
        "_mutate_update_received_invoice": "received_invoices",
        "_mutate_set_received_invoice_status": "received_invoices",
        "_mutate_delete_received_invoice": "received_invoices",
        "_mutate_void_received_invoice": "received_invoices",
        "_mutate_record_received_invoice": "received_invoices",
        "_mutate_confirm_received_invoice": "received_invoices",
        "_mutate_add_expense": "expenses", "_mutate_delete_expense": "expenses",
        "_mutate_void_expense": "expenses", "_mutate_convert_ticket_to_expense": "expenses",
        "_mutate_add_bank_transaction": "bank_transactions",
        "_mutate_suggest_bank_transaction": "bank_transactions",
        "_mutate_confirm_bank_transaction": "bank_transactions",
        "_mutate_ignore_bank_transaction": "bank_transactions",
    }
    if mutation == "_mutate_cycle":
        return  # Recurring crea draft; cualquier emisión interior atraviesa SQL guards.
    from .live_schema import commands_for
    if mutation not in tables:
        row = control(connection, business_id)
        if row and row['ever_enabled']:
            raise ActivationUnavailable("Writer financiero sin spec de ejecución D.")
    require_context(FinancialSession(connection), business_id, commands=commands_for(tables.get(mutation, "")))
