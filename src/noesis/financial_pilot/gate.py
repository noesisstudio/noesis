"""PilotGate: evidencia opaca revalidada, resultado inmutable, ninguna activación."""

from dataclasses import dataclass, field
from datetime import timedelta
import hmac
import json

from noesis.financial_activation.contracts import canonical, digest, instant
from .verification_contracts import Verifier, Failure, VerificationError, Cohort, timestamp, CATALOG
from .evidence import VerifiedEvidence
from .contracts import PilotResult
from .verifiers import PilotVerifiers


@dataclass(frozen=True, slots=True, init=False)
class GateResult:
    canonical_content: str
    _seal: bytes = field(repr=False)

    @property
    def body(self):
        return json.loads(self.canonical_content)

    @property
    def content_hash(self):
        return digest(self.body)


class PilotGate:
    def __init__(self, verifiers):
        if type(verifiers) is not PilotVerifiers:
            raise TypeError('Verificadores cerrados requeridos.')
        self.verifiers = verifiers

    def decide(self, evidence):
        if type(evidence) is not tuple or any(type(e) is not VerifiedEvidence for e in evidence):
            raise TypeError('Sólo tupla de evidencia opaca de verifiers.')
        passed, blockers = {}, {}
        try:
            context = self.verifiers.current()
        except VerificationError as exc:
            context = dict(context=self.verifiers.context.value(), unavailable=exc.reason.value)
            blockers = {v:exc.reason.value for v in Verifier}
            evidence = ()
        for obj in evidence:
            v = Verifier(obj.body['verifier'])
            if v in passed or v in blockers:
                raise VerificationError(Failure.INVALID)
            try:
                passed[v] = self.verifiers.recheck(obj)
            except VerificationError as exc:
                blockers[v] = exc.reason.value
        for v in Verifier:
            if v not in passed and v not in blockers:
                blockers[v] = Failure.MISSING.value
        # Pruebas relacionadas deben compartir la misma copia, custodio y probe.
        if not blockers:
            p = {v: value['proof'] for v, value in passed.items()}
            backup = p[Verifier.BACKUP]
            related = (p[Verifier.RESTORE]['backup'], p[Verifier.BACKUP_CUSTODIAN]['backup'], p[Verifier.MONITORING]['access']['backup'])
            if any(item != backup for item in related):
                blockers[Verifier.RESTORE] = Failure.CONTEXT.value
            if p[Verifier.BACKUP_CUSTODIAN]['custodian'] != p[Verifier.OPERATORS]['roles']['backup_custodian']:
                blockers[Verifier.BACKUP_CUSTODIAN] = Failure.SCOPE.value
            if p[Verifier.RUNTIME_KEY] != p[Verifier.DEPLOYMENT_COMPATIBILITY]['runtime_keys']:
                blockers[Verifier.RUNTIME_KEY] = Failure.CONTEXT.value
            assignments = p[Verifier.OPERATORS]['roles']
            for v, value in passed.items():
                if value['source_actor'] is not None and value['source_actor'] != assignments[CATALOG[v].authority.value]:
                    blockers[v] = Failure.AUTHORITY.value
            for v in (Verifier.PAUSE_RUNBOOK, Verifier.UNKNOWN_RUNBOOK, Verifier.RESUME_CONTINUITY):
                if p[v]['operator'] != assignments[CATALOG[v].authority.value]:
                    blockers[v] = Failure.AUTHORITY.value
            if p[Verifier.LEGAL_POLICY]['approval_actor'] != assignments['privacy_legal_owner']:
                blockers[Verifier.LEGAL_POLICY] = Failure.AUTHORITY.value
        now = self.verifiers.clock()
        expires = min([now+timedelta(seconds=300)] + [timestamp(p['expires_at']) for p in passed.values()])
        real = self.verifiers.context.cohort == Cohort.REAL
        body = dict(version=1, context=self.verifiers.context.value(), context_hash=digest(context),
                    result=PilotResult.BLOCKED.value if blockers else PilotResult.READY.value,
                    blockers=[dict(verifier=v.value, reason=blockers[v]) for v in sorted(blockers)],
                    evidence_hashes={v.value:digest(p) for v,p in sorted(passed.items())},
                    scope='REAL' if real else 'SYNTHETIC_STRUCTURAL', real_evidence_verified=real and not blockers,
                    activation_authorized=False, created_at=instant(now), expires_at=instant(expires))
        obj = object.__new__(GateResult)
        text = canonical(body)
        object.__setattr__(obj, 'canonical_content', text)
        object.__setattr__(obj, '_seal', hmac.digest(self.verifiers._key, text.encode(), 'sha256'))
        return obj

    def validate(self, result, evidence):
        if type(result) is not GateResult or not hmac.compare_digest(result._seal, hmac.digest(self.verifiers._key, result.canonical_content.encode(), 'sha256')):
            raise VerificationError(Failure.INVALID)
        body = result.body
        if not timestamp(body['created_at']) <= self.verifiers.clock() < timestamp(body['expires_at']):
            raise VerificationError(Failure.STALE)
        fresh = self.decide(evidence).body
        if any(fresh[k] != body[k] for k in body if k not in ('created_at', 'expires_at')):
            raise VerificationError(Failure.CONTEXT)
        return body
