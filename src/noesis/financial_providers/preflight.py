"""Preflight integrado A/E/F: sólo SELECT en Core y un recibo propio inmutable."""

from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import uuid4

from noesis import config, db
from noesis.core.persistence import FinancialSession, schema_version
from noesis.financial_activation.contracts import Capability, Profile, digest, instant
from noesis.financial_activation.evaluator import FinancialReadinessEvaluator
from noesis.financial_activation.readiness_verifier import verify_readiness
from noesis.financial_activation.configuration_snapshot import configuration_hash
from noesis.financial_operations.contracts import AccessDenied, ConflictError, StateError, uuid_text
from noesis.financial_privacy.retention import readiness_evidence as privacy_evidence
from .contracts import Permission, Reason, Result, OperationalPolicy, Environment, clock, requirement, closed
from .repository import ProviderRepository
from .attestations import verify
from .schema import RUNS, RESULTS, ATTEMPTS


FIELDS = ("version", "business_id", "preflight_uuid", "evaluation_uuid", "context", "context_hash",
          "result", "reasons", "created_at", "expires_at")


@contextmanager
def transaction(business_id, principal, permission=Permission.PREFLIGHT):
    if permission != Permission.PREFLIGHT:
        raise AccessDenied("financial.providers.preflight requerido.")
    with db.get_conn() as conn:
        s = FinancialSession(conn)
        from .limits import acquire_gate
        acquire_gate(s, business_id)
        if schema_version(conn) != 79:
            raise StateError("Schema79 exacto requerido.")
        ProviderRepository(s, business_id).principal(principal)
        yield s


class FinancialIntegratedPreflight:
    def __init__(self, business_id, *, code_version):
        from .contracts import tenant
        self.bid, self.code_version = tenant(business_id), code_version

    def _context(self, s, principal, evaluation_uuid, attestations, environment, action):
        ev = FinancialReadinessEvaluator(s, self.bid)
        business = ev._permission(principal, locking=True, activation_verification=True)
        row = ev.repo.load(uuid_text(evaluation_uuid))
        if not row or row["created_by"] != principal.user_id or row["session_version"] != principal.session_version:
            raise AccessDenied(Reason.SESSION_STALE)
        value = ev.repo.result(row)
        reasons = set()
        if value["outcome"] != "fully_eligible" or value["reasons"]:
            reasons.add(Reason.READINESS_NOT_FULL)
        if clock() >= datetime.fromisoformat(value["expires_at"]):
            reasons.add(Reason.READINESS_STALE)
        if value["context"]["code_version"] != self.code_version or self.code_version != config.RELEASE_ID:
            reasons.add(Reason.CONFIGURATION_CHANGED)
        profile = Profile(tuple(value["profile"]["capabilities"]), value["profile"]["profile_version"])
        closure, edges = profile.closure(fiscal_cancel_required=bool(business["verifactu_enabled"]))
        if any(c in (Capability.BANK_IMPORT, Capability.BANK_MATCH) for c in closure):
            reasons.add(Reason.BANK_UNVALIDATED)
        privacy = privacy_evidence(s, self.bid)
        from noesis.financial_privacy.schema import POLICIES, EXPORTS
        privacy_refs = {}
        for table in (POLICIES, EXPORTS):
            evidence = s.execute("SELECT evidence_uuid,content_hash FROM " + table + " WHERE business_id=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1", (self.bid,)).fetchone()
            privacy_refs[table] = dict(uuid=str(evidence["evidence_uuid"]), content_hash=evidence["content_hash"]) if evidence else None
        if not privacy["privacy_ready"]:
            reasons.add(Reason.PRIVACY_NOT_READY)
        if not privacy["export_ready"]:
            reasons.add(Reason.EXPORT_NOT_READY)
        proofs, requirements = {}, {}
        expected = {c.value for c in closure if requirement(c) is not None and not (c == Capability.AEAT and not business["verifactu_enabled"])}
        if set(attestations) - expected:
            raise ValueError("Attestations ajenas al cierre exacto.")
        for c in closure:
            if c.value not in expected:
                continue
            requirements[c.value] = requirement(c).value
            uid = attestations.get(c.value)
            if uid is None:
                reasons.add(Reason.ATTESTATION_MISSING)
                continue
            try:
                proofs[c.value] = verify(s, self.bid, uid, c.value, environment=environment, code_version=self.code_version)
            except StateError as exc:
                reasons.add(Reason(str(exc)))
        control = ev.s.execute("SELECT state,activation_generation,ever_enabled,control_revision,current_transition_uuid FROM financial_activation_control WHERE business_id=?", (self.bid,)).fetchone()
        if control is None:
            raise StateError("Control A ausente.")
        recovery = None
        try:
            if action == "enable":
                evidence = verify_readiness(s, self.bid, principal, value["evaluation_uuid"])
                history_hash = digest(evidence["history"])
            elif action == "resume":
                from noesis.financial_activation.handoff import FinancialActivation
                api = FinancialActivation(self.bid, code_version=self.code_version)
                origin, _, recovery = api.recovery(s, principal, control)
                if origin["evaluation_uuid"] != value["evaluation_uuid"] or origin["profile"] != value["profile"]:
                    reasons.add(Reason.READINESS_NOT_FULL)
                history_hash = digest(origin["history"])
            else:
                raise ValueError("Preflight sólo enable/resume.")
        except (ConflictError, StateError):
            history_hash = digest(value["context"]["history"])
            reasons.add(Reason.HISTORY_INVALID)
        sources = ev._sources()
        if "pending_live_operation" in sources["economic_kinds"]:
            reasons.add(Reason.PENDING_OPERATION)
        if "uncertain_dispatch" in sources["economic_kinds"]:
            reasons.add(Reason.UNKNOWN_RESULT)
        pending = s.execute(f"SELECT a.evidence_uuid FROM {ATTEMPTS} a LEFT JOIN {RESULTS} r ON r.business_id=a.business_id AND r.attempt_uuid=a.evidence_uuid WHERE a.business_id=? AND (r.evidence_uuid IS NULL OR r.result='UNKNOWN_EXTERNAL_RESULT') ORDER BY a.evidence_uuid", (self.bid,)).fetchall()
        if pending:
            reasons.add(Reason.UNKNOWN_RESULT)
        history = value["context"]["history"]
        items = s.execute("SELECT COUNT(*) AS n FROM financial_history_items WHERE business_id=? AND manifest_uuid=?", (self.bid, history.get("manifest_uuid"))).fetchone()["n"] if history else 0
        if items > OperationalPolicy().history_max_items:
            reasons.add(Reason.VOLUME)
        from noesis.financial_privacy.schema import AUTHORIZATIONS, RECEIPTS, RESTORED
        if s.execute(f"SELECT 1 FROM {RECEIPTS} WHERE business_id=? UNION SELECT 1 FROM {RESTORED} WHERE business_id=? AND scope='account_local_access' LIMIT 1", (self.bid, self.bid)).fetchone():
            reasons.add(Reason.CLOSED)
        elif s.execute(f"SELECT 1 FROM {AUTHORIZATIONS} WHERE business_id=?", (self.bid,)).fetchone():
            reasons.add(Reason.CLOSING)
        return dict(evaluation_uuid=value["evaluation_uuid"], evaluation_hash=value["content_hash"],
                    profile=value["profile"], profile_hash=profile.content_hash, capabilities=[c.value for c in closure],
                    dependencies=edges, requirements=requirements, attestations=proofs, environment=Environment(environment).value,
                    privacy=privacy, privacy_refs=privacy_refs, history_hash=history_hash, source_hash=digest(sources), configuration_hash=configuration_hash(s, self.bid),
                    volume=items, uncertain_attempts_hash=digest([str(r["evidence_uuid"]) for r in pending]),
                    control={k: bool(control[k]) if k == "ever_enabled" else control[k] for k in ('state','activation_generation','ever_enabled','control_revision')},
                    policy_version=1, operational_limits=OperationalPolicy().value(), code_version=self.code_version,
                    schema_version=79, actor_user_id=principal.user_id, actor_session_version=principal.session_version,
                    permission=Permission.PREFLIGHT.value, action=action, recovery=recovery), reasons

    def evaluate(self, principal, evaluation_uuid, *, preflight_uuid=None, attestations=None,
                 environment=Environment.PRODUCTION, action="enable", permission=Permission.PREFLIGHT):
        uid = uuid_text(preflight_uuid or uuid4())
        with transaction(self.bid, principal, permission) as s:
            repo = ProviderRepository(s, self.bid)
            context, reasons = self._context(s, principal, evaluation_uuid, attestations or {}, environment, action)
            old = repo.load(RUNS, uid)
            if old:
                if old["context"] != context:
                    raise ConflictError("Preflight UUID/contexto distinto.")
                return old
            now = clock()
            value = dict(version=1, business_id=self.bid, preflight_uuid=uid, evaluation_uuid=uuid_text(evaluation_uuid),
                         context=context, context_hash=digest(context), result=Result.BLOCKED.value if reasons else Result.PASS.value,
                         reasons=sorted(r.value for r in reasons), created_at=instant(now), expires_at=instant(now + timedelta(minutes=5)))
            return repo.append(RUNS, uid, principal, value, now, evaluation_uuid=value["evaluation_uuid"],
                               context_hash=value["context_hash"], result=value["result"], expires_at=value["expires_at"])

    def verify(self, s, principal, preflight_uuid, *, activation_request=None):
        value = ProviderRepository(s, self.bid).load(RUNS, preflight_uuid)
        if not value:
            raise StateError("Preflight PASS requerido.")
        closed(value, FIELDS)
        if digest(value["context"]) != value["context_hash"] or value["result"] != Result.PASS or value["reasons"] or clock() >= datetime.fromisoformat(value["expires_at"]):
            raise StateError("Preflight bloqueado/caducado/incoherente.")
        refs = {c: p["attestation_uuid"] for c, p in value["context"]["attestations"].items()}
        current, reasons = self._context(s, principal, value["evaluation_uuid"], refs,
                                         value["context"]["environment"], value["context"]["action"])
        original = value["context"]
        if activation_request is not None:
            # D puede avanzar off→validating→ready dentro de SU solicitud exacta.
            original, current = dict(original), dict(current)
            ctrl = current.pop("control")
            original.pop("control")
            if ctrl["activation_generation"] != activation_request.body["previous_generation"]:
                raise ConflictError("Generación cambió durante handoff.")
        if reasons or current != original:
            raise ConflictError("Preflight stale: revalidación every_use falló.")
        return value


def bind_activation(session, business_id, principal, request, preflight_uuid, code_version):
    from .schema import BINDINGS
    api = FinancialIntegratedPreflight(business_id, code_version=code_version)
    value = api.verify(session, principal, preflight_uuid, activation_request=request)
    b, context = request.body, value["context"]
    if (b["evaluation_uuid"] != value["evaluation_uuid"] or b["profile_hash"] != context["profile_hash"]
            or b["capabilities"] != context["capabilities"] or b["configuration_hash"] != context["configuration_hash"]
            or b["action"] != context["action"] or b["actor_user_id"] != context["actor_user_id"]
            or b["actor_session_version"] != context["actor_session_version"]):
        raise ConflictError("Solicitud D/preflight distintos.")
    body = dict(version=1, business_id=business_id, request_uuid=b["request_uuid"], preflight_uuid=value["preflight_uuid"], preflight_hash=digest(value))
    ProviderRepository(session, business_id).append(BINDINGS, b["request_uuid"], principal, body, clock(),
        request_uuid=b["request_uuid"], preflight_uuid=body["preflight_uuid"], preflight_hash=body["preflight_hash"])
    return body


def verify_activation(session, business_id, principal, request, code_version):
    from .schema import BINDINGS
    binding = ProviderRepository(session, business_id).load(BINDINGS, request.body["request_uuid"])
    if not binding:
        raise StateError("Binding F obligatorio para schema79.")
    value = FinancialIntegratedPreflight(business_id, code_version=code_version).verify(
        session, principal, binding["preflight_uuid"], activation_request=request)
    if digest(value) != binding["preflight_hash"]:
        raise ConflictError("Hash de preflight cambió.")
    return binding
