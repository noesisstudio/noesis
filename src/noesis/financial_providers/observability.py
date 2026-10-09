"""Read model tenant: UUID/hash/edad/estado; sin PII ni mutaciones de autoridad."""

from datetime import datetime
from noesis.financial_activation.runtime import control
from noesis.financial_privacy.retention import readiness_evidence
from .repository import ProviderRepository
from .contracts import Observation, Reason, OperationalPolicy, clock
from .schema import ATTESTATIONS, RUNS, ATTEMPTS, RESULTS, OBSERVATIONS, OUTBOXES


def observe(session, business_id, principal, observation_uuid, kind, *, reference_hash, reason=None):
    from .contracts import hash_text, uuid_text
    kind = Observation(kind)
    reason = Reason(reason).value if reason is not None else None
    body = dict(version=1, business_id=business_id, observation_uuid=uuid_text(observation_uuid),
                kind=kind.value, reference_hash=hash_text(reference_hash), reason=reason)
    return ProviderRepository(session, business_id).append(OBSERVATIONS, observation_uuid, principal, body, clock(), kind=kind.value)


def read(session, business_id, principal):
    ProviderRepository(session, business_id).principal(principal)
    current = control(session, business_id)
    now, alerts = clock(), []
    attestations = []
    for row in session.execute(f"SELECT evidence_uuid,provider,capability,expires_at,result FROM {ATTESTATIONS} WHERE business_id=? ORDER BY created_at", (business_id,)).fetchall():
        item = dict(row)
        item["evidence_uuid"] = str(item["evidence_uuid"])
        item["expired"] = now >= datetime.fromisoformat(item["expires_at"])
        if item["expired"]:
            alerts.append("PROVIDER_ATTESTATION_STALE")
        attestations.append(item)
    pending = session.execute(f"SELECT COUNT(*) AS n FROM {ATTEMPTS} a LEFT JOIN {RESULTS} r ON r.business_id=a.business_id AND r.attempt_uuid=a.evidence_uuid WHERE a.business_id=? AND r.evidence_uuid IS NULL", (business_id,)).fetchone()["n"]
    unknown = session.execute(f"SELECT COUNT(*) AS n FROM {RESULTS} WHERE business_id=? AND result='UNKNOWN_EXTERNAL_RESULT'", (business_id,)).fetchone()["n"]
    errors = session.execute(f"SELECT COUNT(*) AS n FROM {RESULTS} WHERE business_id=? AND result='FAILED_TERMINAL'", (business_id,)).fetchone()["n"]
    if unknown:
        alerts.append("UNCERTAIN_EXTERNAL_RESULT")
    if errors:
        alerts.append("PROVIDER_ERROR")
    if current and current["state"] == "paused":
        alerts.append("PAUSED")
    from noesis.financial_privacy.schema import AUTHORIZATIONS, RECEIPTS
    closed = bool(session.execute(f"SELECT 1 FROM {AUTHORIZATIONS} WHERE business_id=? UNION SELECT 1 FROM {RECEIPTS} WHERE business_id=? LIMIT 1", (business_id, business_id)).fetchone())
    if closed:
        alerts.append("ACCOUNT_CLOSING_OR_CLOSED")
    latest = session.execute(f"SELECT evidence_uuid,result,expires_at FROM {RUNS} WHERE business_id=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1", (business_id,)).fetchone()
    if latest and latest["result"] == "BLOCKED":
        alerts.append("PREFLIGHT_BLOCKED")
    if latest and now >= datetime.fromisoformat(latest['expires_at']):
        alerts.append('READINESS_STALE')
    queues = {}
    for table in OUTBOXES:
        row = session.execute("SELECT COUNT(*) AS n,MIN(created_at) AS oldest FROM " + table + " WHERE business_id=? AND status NOT IN ('sent','delivered','read','aceptado','aceptado_con_errores','rechazado','cancelled','failed')", (business_id,)).fetchone()
        oldest = row["oldest"]
        if oldest:
            dt = oldest if isinstance(oldest, datetime) else datetime.fromisoformat(oldest)
            # Una fecha legacy naive conserva esa limitación: edad no inferida.
            age = int((now - dt).total_seconds()) if dt.tzinfo is not None else None
        else:
            age = None
        queues[table] = dict(count=row["n"], oldest_age_seconds=age)
        if age is not None and age > OperationalPolicy().cutoff_intervention_seconds:
            alerts.append("OUTBOX_AGE_REVIEW_REQUIRED")
    grants = [r["capability"] for r in session.execute("SELECT capability FROM financial_activation_grants WHERE business_id=? AND activation_generation=? ORDER BY capability", (business_id, current["activation_generation"] if current else 0)).fetchall()]
    history = session.execute('SELECT h.epoch_uuid,h.fence_enabled,e.t0 FROM financial_history_control h JOIN financial_history_epochs e ON e.business_id=h.business_id AND e.epoch_uuid=h.epoch_uuid WHERE h.business_id=?', (business_id,)).fetchone()
    diagnostics = {r['kind']:r['n'] for r in session.execute(f'SELECT kind,COUNT(*) AS n FROM {OBSERVATIONS} WHERE business_id=? GROUP BY kind', (business_id,)).fetchall()}
    generations = [{'generation':r['activation_generation'],'receipt_uuid':str(r['receipt_uuid'])} for r in session.execute('SELECT activation_generation,receipt_uuid FROM financial_activation_generations WHERE business_id=? ORDER BY activation_generation',(business_id,)).fetchall()]
    if history and history['fence_enabled']:
        alerts.append('HISTORY_FENCE_ACTIVE')
    age = None
    if history:
        t0 = history['t0'] if isinstance(history['t0'],datetime) else datetime.fromisoformat(history['t0'])
        age = int((now-t0).total_seconds())
        if history['fence_enabled'] and age >= OperationalPolicy().cutoff_warning_seconds:
            alerts.append('PROTECTED_CUT_WARNING')
        if history['fence_enabled'] and age >= OperationalPolicy().cutoff_intervention_seconds:
            alerts.append('PROTECTED_CUT_INTERVENTION_REQUIRED')
    if diagnostics.get('continuity_mismatch'):
        alerts.append('CONTINUITY_MISMATCH')
    if diagnostics.get('stale_generation'):
        alerts.append('STALE_GENERATION')
    return dict(version=1, business_id=business_id, state=current["state"] if current else "off",
                activation_generation=current["activation_generation"] if current else 0,
                grants=grants, attestations=attestations, pending_attempts=pending, unknown_results=unknown,
                errors=errors, preflight=dict(evidence_uuid=str(latest["evidence_uuid"]), result=latest["result"], expires_at=latest["expires_at"]) if latest else None,
                queues=queues, privacy=readiness_evidence(session, business_id), alerts=sorted(set(alerts)),
                history=dict(epoch_uuid=str(history['epoch_uuid']), fence_enabled=bool(history['fence_enabled']),age_seconds=age) if history else None,
                handoffs=generations, diagnostics=diagnostics,
                operational_limits=OperationalPolicy().value())
