"""Repositorio tenant-scoped; la conexión y el commit pertenecen al llamador."""

import json

from noesis.financial_operations.contracts import ConflictError
from .contracts import (
    Capability,
    CapabilityResult,
    Outcome,
    Profile,
    Reason,
    canonical,
    capability_proof,
    digest,
)
from .schema import CONTROL, EVALUATIONS, CAPABILITIES


class ReadinessRepository:
    def __init__(self, session, business_id):
        self.s, self.bid = session, business_id

    def load(self, uid):
        return self.s.execute(
            f"SELECT * FROM {EVALUATIONS} WHERE business_id=? AND evaluation_uuid=?",
            (self.bid, uid),
        ).fetchone()

    def result(self, row):
        if row["state"] != "final":
            raise ConflictError("Evaluación incompleta; no recuperar como final.")
        body = json.loads(row["result_canonical"])
        if digest(body) != row["content_hash"] or canonical(body) != row["result_canonical"]:
            raise ConflictError("Evidencia readiness incoherente.")
        capabilities = []
        for proof in self.s.execute(
            f"SELECT * FROM {CAPABILITIES} WHERE business_id=? AND evaluation_uuid=? ORDER BY capability",
            (self.bid, str(row["evaluation_uuid"])),
        ).fetchall():
            value = json.loads(proof["proof_canonical"])
            if (
                capability_proof(
                    value["capability"],
                    value["result"],
                    value["reasons"],
                    value["dependencies"],
                    value["evidence"],
                )
                != value
            ):
                raise ConflictError("Contrato de capacidad incoherente.")
            if (
                digest(value) != proof["proof_hash"]
                or value["capability"] != proof["capability"]
                or value["result"] != proof["result"]
                or canonical(value["reasons"]) != proof["reasons_canonical"]
                or canonical(value["dependencies"]) != proof["dependency_canonical"]
                or canonical(value["evidence"]) != proof["evidence_canonical"]
            ):
                raise ConflictError("Prueba de capacidad incoherente.")
            capabilities.append(value)
        if (
            capabilities != body["capabilities"]
            or body["outcome"] != row["result"]
            or body["profile"] != json.loads(row["profile_canonical"])
            or digest(body["context"]) != row["context_hash"]
            or canonical(body["context"]) != row["context_canonical"]
        ):
            raise ConflictError("Columnas de evaluación incompatibles.")
        profile = Profile(
            tuple(body["profile"]["capabilities"]), body["profile"]["profile_version"]
        )
        closure, edges = profile.closure(
            fiscal_cancel_required=body["context"]["verifactu_enabled"]
        )
        results = {Capability(p["capability"]): CapabilityResult(p["result"]) for p in capabilities}
        if (
            len(results) != len(Capability)
            or profile.content_hash != row["profile_hash"]
            or canonical(body["profile"]["capabilities"]) != row["requested_canonical"]
            or body["context"]["source_hash"] != row["source_hash"]
            or body["context"]["dependencies"] != edges
        ):
            raise ConflictError("Perfil, fuentes o cierre incompatibles.")
        for proof in capabilities:
            c = Capability(proof["capability"])
            expected = {d: results[Capability(d)].value for d in edges.get(c.value, ())}
            if (
                proof["dependencies"] != expected
                or (c in closure) == (results[c] == CapabilityResult.NOT_REQUESTED)
                or any(v == "blocked" for v in expected.values())
                and results[c] != CapabilityResult.BLOCKED
            ):
                raise ConflictError("Cierre de dependencias incoherente.")
        reasons = [Reason(r).value for r in body["reasons"]]
        blocked = sum(results[c] == CapabilityResult.BLOCKED for c in closure)
        expected_outcome = (
            Outcome.BLOCKED
            if reasons or blocked == len(closure)
            else Outcome.PARTIAL
            if blocked
            else Outcome.FULL
        )
        if body["outcome"] != expected_outcome.value:
            raise ConflictError("Outcome incompatible con el perfil exacto.")

        def stamp(v):
            from datetime import datetime
            from .contracts import instant

            return instant(v if isinstance(v, datetime) else datetime.fromisoformat(v))

        return dict(
            evaluation_uuid=str(row["evaluation_uuid"]),
            business_id=self.bid,
            content_hash=row["content_hash"],
            created_at=stamp(row["created_at"]),
            completed_at=stamp(row["completed_at"]),
            expires_at=stamp(row["expires_at"]),
            **body,
        )

    def store(self, principal, uid, profile, policy, code_version, context, body, now, expiry):
        self.s.execute(
            f"""INSERT INTO {CONTROL}
            (business_id,state,control_revision,activation_generation,ever_enabled,created_by,created_at,updated_at,provenance)
            VALUES (?,'off',0,0,FALSE,?,?,?,'readiness_v1') ON CONFLICT(business_id) DO NOTHING""",
            (self.bid, principal.user_id, now, now),
        )
        history = context["history"]
        self.s.execute(
            f"""INSERT INTO {EVALUATIONS}
            (business_id,evaluation_uuid,evaluation_version,policy_version,code_version,schema_version,
             created_by,session_version,validated_permission,profile_version,profile_canonical,profile_hash,requested_canonical,
             epoch_uuid,historical_generation,manifest_uuid,batch_uuid,reconciliation_uuid,
             source_hash,plan_hash,reconciliation_hash,context_hash,context_canonical,state,created_at,expires_at)
            VALUES (?,?,1,?,?,74,?,?,'financial.readiness.evaluate',1,?,?,?,?,?,?,?,?,?,?,?,?,?,'building',?,?)""",
            (
                self.bid,
                uid,
                policy.policy_version,
                code_version,
                principal.user_id,
                principal.session_version,
                canonical(profile.value()),
                profile.content_hash,
                canonical([c.value for c in profile.capabilities]),
                history.get("epoch_uuid"),
                history.get("generation"),
                history.get("manifest_uuid"),
                history.get("batch_uuid"),
                history.get("reconciliation_uuid"),
                context["source_hash"],
                history.get("plan_hash"),
                history.get("result_hash"),
                digest(context),
                canonical(context),
                now,
                expiry,
            ),
        )
        for proof in body["capabilities"]:
            self.s.execute(
                f"""INSERT INTO {CAPABILITIES}
                (business_id,evaluation_uuid,capability,result,reasons_canonical,dependency_canonical,evidence_canonical,proof_canonical,proof_hash)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    self.bid,
                    uid,
                    proof["capability"],
                    proof["result"],
                    canonical(proof["reasons"]),
                    canonical(proof["dependencies"]),
                    canonical(proof["evidence"]),
                    canonical(proof),
                    digest(proof),
                ),
            )
        self.s.execute(
            f"UPDATE {EVALUATIONS} SET state='final',result=?,completed_at=?,result_canonical=?,content_hash=? WHERE business_id=? AND evaluation_uuid=?",
            (body["outcome"], now, canonical(body), digest(body), self.bid, uid),
        )
        self.s.execute(
            f"UPDATE {CONTROL} SET control_revision=control_revision+1,current_profile=?,current_evaluation_uuid=?,updated_at=? WHERE business_id=?",
            (canonical(profile.value()), uid, now, self.bid),
        )
        return self.result(self.load(uid))
