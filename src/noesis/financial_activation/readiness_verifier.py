"""Consumo SELECT de A en sesión prestada; no crea ni modifica evaluaciones."""

from datetime import datetime, timezone

from noesis.financial_operations.contracts import AccessDenied, ConflictError, StateError, uuid_text
from .contracts import CapabilityResult, FINANCIAL, HistoryContext, Outcome, Profile, digest, instant
from .evaluator import FinancialReadinessEvaluator


def external_context(context):
    """Excluir SOLO lifecycle administrado por D, nunca evidencia económica."""
    return {k: v for k, v in context.items() if k != "control"}


def verify_readiness(session, business_id, principal, evaluation_uuid, *, now=None):
    evaluator = FinancialReadinessEvaluator(session, business_id)
    business = evaluator._permission(principal, locking=True, activation_verification=True)
    row = evaluator.repo.load(uuid_text(evaluation_uuid))
    if not row or row["created_by"] != principal.user_id or row["session_version"] != principal.session_version:
        raise AccessDenied("Evidencia de activación no disponible.")
    result = evaluator.repo.result(row)
    now = now or datetime.now(timezone.utc)
    expires = datetime.fromisoformat(result["expires_at"])
    if result["outcome"] != Outcome.FULL.value or result["reasons"] or now >= expires:
        raise StateError("Readiness FULL exacta y vigente requerida.")
    profile = Profile(tuple(result["profile"]["capabilities"]), result["profile"]["profile_version"])
    closure, edges = profile.closure(fiscal_cancel_required=bool(business["verifactu_enabled"]))
    if not any(c in FINANCIAL for c in closure):
        raise StateError("Handoff requiere al menos una capability financiera real.")
    needed = {c.value for c in closure}
    proofs = {p["capability"]: p for p in result["capabilities"]}
    if any(proofs[c]["result"] != CapabilityResult.ELIGIBLE.value for c in needed):
        raise StateError("Cada capability del closure debe ser eligible, nunca not_applicable.")
    if result["context"]["dependencies"] != edges:
        raise ConflictError("Dependency closure cambió.")
    history = result["context"]["history"]
    reference = HistoryContext(*(history[k] for k in ("epoch_uuid", "manifest_uuid", "batch_uuid", "reconciliation_uuid")))
    current_history, reasons = evaluator._history(reference)
    if reasons:
        raise StateError("Evidencia de corte/reconciliación inválida.")
    sources = evaluator._sources()
    if "pending_live_operation" in sources["economic_kinds"] or "uncertain_dispatch" in sources["economic_kinds"]:
        raise StateError("Operación pendiente o dispatch incierto bloquea handoff.")
    current = dict(external_context(result["context"]), history=current_history,
                   configuration_hash=evaluator._configuration(business),
                   verifactu_enabled=bool(business["verifactu_enabled"]), dependencies=edges, **sources)
    if "privacy_evidence" in current:
        from noesis.financial_privacy.retention import readiness_evidence
        current["privacy_evidence"] = readiness_evidence(session, business_id)
    if "provider_evidence" in current:
        from noesis.financial_providers.attestations import readiness_evidence
        current["provider_evidence"] = readiness_evidence(session, business_id, closure, code_version=result["context"]["code_version"])
    if current != external_context(result["context"]):
        raise ConflictError("Evidencia externa de readiness cambió.")
    grants = [proofs[c] for c in sorted(needed)]
    from noesis.financial_history.reconciliation_verifier import storage_hash
    frozen_history = dict(current_history)
    for table, key, uid, label in (
        ('financial_history_epochs', 'epoch_uuid', reference.epoch_uuid, 'epoch'),
        ('financial_history_cut_manifests', 'manifest_uuid', reference.manifest_uuid, 'cut'),
        ('financial_history_manifests', 'manifest_uuid', reference.manifest_uuid, 'manifest'),
        ('financial_history_import_batches', 'batch_uuid', reference.batch_uuid, 'batch'),
        ('financial_history_reconciliations', 'reconciliation_uuid', reference.reconciliation_uuid, 'reconciliation'),
    ):
        source = session.borrowed_connection.execute_exact('SELECT * FROM ' + table + ' WHERE business_id=? AND ' + key + '=?', (business_id, uid)).fetchone()
        frozen_history[label + '_storage_hash'] = storage_hash(source)
        if label == 'epoch':
            t0 = source['t0'] if isinstance(source['t0'], datetime) else datetime.fromisoformat(source['t0'])
            frozen_history.update(t0=instant(t0), fence_version=source['fence_version'],
                                  source_scope_hash=digest(source['source_scope_canonical']))
        if label == 'cut':
            frozen_history['source_set_hash'] = source['source_set_hash']
    return dict(evaluation=result, profile=profile.value(), capabilities=sorted(needed),
                grants=grants, grant_hash=digest(grants), external_hash=digest(current), history=frozen_history)
