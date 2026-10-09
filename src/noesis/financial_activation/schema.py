"""Migración74 aditiva. Solo off/validating; ninguna activación ejecutable."""

from noesis.financial_history.schema import guard, literals
from .contracts import Capability, CapabilityResult, Outcome, Permission, Reason

CONTROL = "financial_activation_control"
EVALUATIONS = "financial_readiness_evaluations"
CAPABILITIES = "financial_readiness_capabilities"
TABLES = (CONTROL, EVALUATIONS, CAPABILITIES)


def upgrade(conn):
    pg = conn.dialect == "postgres"
    uid, ref, stamp, boolean = (
        ("UUID", "BIGINT", "TIMESTAMPTZ", "BOOLEAN")
        if pg
        else ("TEXT", "INTEGER", "TEXT", "INTEGER")
    )
    false = "FALSE" if pg else "0"
    eq = "IS DISTINCT FROM" if pg else "IS NOT"
    conn.execute(f"""CREATE TABLE {EVALUATIONS} (
        business_id {ref} NOT NULL REFERENCES businesses(id), evaluation_uuid {uid} NOT NULL,
        evaluation_version INTEGER NOT NULL CHECK(evaluation_version=1),
        policy_version INTEGER NOT NULL CHECK(policy_version=1),
        code_version TEXT NOT NULL CHECK(length(code_version) BETWEEN 1 AND 128),
        schema_version INTEGER NOT NULL CHECK(schema_version=74),
        created_by {ref} NOT NULL, session_version INTEGER NOT NULL CHECK(session_version>=0),
        validated_permission TEXT NOT NULL CHECK(validated_permission='{Permission.EVALUATE.value}'),
        profile_version INTEGER NOT NULL CHECK(profile_version=1), profile_canonical TEXT NOT NULL,
        profile_hash TEXT NOT NULL CHECK(length(profile_hash)=64), requested_canonical TEXT NOT NULL,
        epoch_uuid {uid}, historical_generation BIGINT, manifest_uuid {uid}, batch_uuid {uid}, reconciliation_uuid {uid},
        source_hash TEXT NOT NULL CHECK(length(source_hash)=64), plan_hash TEXT, reconciliation_hash TEXT,
        context_hash TEXT NOT NULL CHECK(length(context_hash)=64), context_canonical TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('building','final')),
        result TEXT CHECK(result IN ({literals(Outcome)})),
        created_at {stamp} NOT NULL, completed_at {stamp}, expires_at {stamp} NOT NULL,
        result_canonical TEXT, content_hash TEXT CHECK(length(content_hash)=64),
        PRIMARY KEY(business_id,evaluation_uuid),
        FOREIGN KEY(business_id,created_by) REFERENCES users(business_id,id),
        CHECK(expires_at>created_at),
        CHECK((state='building' AND result IS NULL AND completed_at IS NULL AND result_canonical IS NULL AND content_hash IS NULL)
          OR (state='final' AND result IS NOT NULL AND completed_at>=created_at AND result_canonical IS NOT NULL AND content_hash IS NOT NULL)))""")
    conn.execute(f"""CREATE TABLE {CONTROL} (
            business_id {ref} PRIMARY KEY REFERENCES businesses(id),
            state TEXT NOT NULL CHECK(state IN ('off','validating')),
            control_revision BIGINT NOT NULL CHECK(control_revision>=0),
            activation_generation BIGINT NOT NULL CHECK(activation_generation=0),
            ever_enabled {boolean} NOT NULL DEFAULT {false} CHECK(ever_enabled={false}),
            current_profile TEXT, current_evaluation_uuid {uid},
            created_by {ref} NOT NULL, created_at {stamp} NOT NULL, updated_at {stamp} NOT NULL,
            provenance TEXT NOT NULL CHECK(provenance='readiness_v1'),
            FOREIGN KEY(business_id,created_by) REFERENCES users(business_id,id),
            FOREIGN KEY(business_id,current_evaluation_uuid) REFERENCES {EVALUATIONS}(business_id,evaluation_uuid) DEFERRABLE INITIALLY DEFERRED,
            CHECK((current_profile IS NULL AND current_evaluation_uuid IS NULL)
              OR (current_profile IS NOT NULL AND current_evaluation_uuid IS NOT NULL)))""")
    conn.execute(f"""CREATE TABLE {CAPABILITIES} (
        business_id {ref} NOT NULL, evaluation_uuid {uid} NOT NULL,
        capability TEXT NOT NULL CHECK(capability IN ({literals(Capability)})),
        result TEXT NOT NULL CHECK(result IN ({literals(CapabilityResult)})),
        reasons_canonical TEXT NOT NULL, dependency_canonical TEXT NOT NULL, evidence_canonical TEXT NOT NULL,
        proof_canonical TEXT NOT NULL, proof_hash TEXT NOT NULL CHECK(length(proof_hash)=64),
        PRIMARY KEY(business_id,evaluation_uuid,capability),
        FOREIGN KEY(business_id,evaluation_uuid) REFERENCES {EVALUATIONS}(business_id,evaluation_uuid))""")
    conn.execute(f"CREATE INDEX idx_readiness_created ON {EVALUATIONS}(business_id,created_at)")
    for table in TABLES:
        guard(conn, table + "_retain", table, "DELETE", "TRUE")
    actor = "EXISTS(SELECT 1 FROM users u WHERE u.business_id=NEW.business_id AND u.id=NEW.created_by AND u.is_active=TRUE AND u.session_version=NEW.session_version)"
    guard(
        conn,
        EVALUATIONS + "_insert",
        EVALUATIONS,
        "INSERT",
        "NEW.state<>'building' OR NOT (" + actor + ")",
    )
    identity = (
        "business_id",
        "evaluation_uuid",
        "evaluation_version",
        "policy_version",
        "code_version",
        "schema_version",
        "created_by",
        "session_version",
        "validated_permission",
        "profile_version",
        "profile_canonical",
        "profile_hash",
        "requested_canonical",
        "epoch_uuid",
        "historical_generation",
        "manifest_uuid",
        "batch_uuid",
        "reconciliation_uuid",
        "source_hash",
        "plan_hash",
        "reconciliation_hash",
        "context_hash",
        "context_canonical",
        "created_at",
        "expires_at",
    )
    counts = f"(SELECT COUNT(*) FROM {CAPABILITIES} c WHERE c.business_id=NEW.business_id AND c.evaluation_uuid=NEW.evaluation_uuid)"
    blocked = f"EXISTS(SELECT 1 FROM {CAPABILITIES} c WHERE c.business_id=NEW.business_id AND c.evaluation_uuid=NEW.evaluation_uuid AND c.result='blocked')"
    boundary = """EXISTS(SELECT 1 FROM financial_history_reconciliations r
        JOIN financial_history_cut_manifests m ON m.business_id=r.business_id AND m.manifest_uuid=r.manifest_uuid
        JOIN financial_history_control c ON c.business_id=r.business_id AND c.epoch_uuid=r.epoch_uuid AND c.generation=r.generation
        WHERE r.business_id=NEW.business_id AND r.reconciliation_uuid=NEW.reconciliation_uuid AND r.state='frozen' AND r.result='PASS'
        AND r.epoch_uuid=NEW.epoch_uuid AND r.generation=NEW.historical_generation AND r.manifest_uuid=NEW.manifest_uuid
        AND r.batch_uuid=NEW.batch_uuid AND r.result_hash=NEW.reconciliation_hash AND r.plan_hash=NEW.plan_hash
        AND m.certifiable=TRUE AND m.boundary_current=TRUE AND c.fence_enabled=TRUE)"""
    guard(
        conn,
        EVALUATIONS + "_update",
        EVALUATIONS,
        "UPDATE",
        "OLD.state<>'building' OR NEW.state<>'final' OR NOT ("
        + actor
        + ") OR "
        + " OR ".join(f"NEW.{f} {eq} OLD.{f}" for f in identity)
        + f" OR {counts}<>{len(Capability)} OR (NEW.result='fully_eligible' AND ({blocked} OR NOT ({boundary})))",
    )
    parent = f"EXISTS(SELECT 1 FROM {EVALUATIONS} e WHERE e.business_id=NEW.business_id AND e.evaluation_uuid=NEW.evaluation_uuid AND e.state='building')"
    reasons = (
        "jsonb_array_elements_text(NEW.reasons_canonical::jsonb) AS r(value)"
        if pg
        else "json_each(NEW.reasons_canonical) r"
    )
    count = (
        "jsonb_array_length(NEW.reasons_canonical::jsonb)"
        if pg
        else "json_array_length(NEW.reasons_canonical)"
    )
    invalid_reason = f"EXISTS(SELECT 1 FROM {reasons} WHERE r.value NOT IN ({literals(Reason)}))"
    na = f"NEW.result='not_applicable' AND (NEW.capability<>'provider.aeat_dispatch' OR {count}<>1 OR NEW.reasons_canonical<>'[\"FISCAL_PROVIDER_NOT_APPLICABLE\"]' OR NOT EXISTS(SELECT 1 FROM businesses WHERE id=NEW.business_id AND verifactu_enabled=FALSE))"
    guard(
        conn,
        CAPABILITIES + "_insert",
        CAPABILITIES,
        "INSERT",
        "NOT ("
        + parent
        + ") OR "
        + invalid_reason
        + f" OR (NEW.result='blocked' AND {count}=0) OR (NEW.result IN ('eligible','not_requested') AND {count}<>0) OR "
        + na,
    )
    guard(conn, CAPABILITIES + "_immutable", CAPABILITIES, "UPDATE", "TRUE")
    guard(
        conn,
        CONTROL + "_insert",
        CONTROL,
        "INSERT",
        "NEW.state<>'off' OR NEW.control_revision<>0 OR NEW.current_evaluation_uuid IS NOT NULL",
    )
    valid = f"EXISTS(SELECT 1 FROM {EVALUATIONS} e WHERE e.business_id=NEW.business_id AND e.evaluation_uuid=NEW.current_evaluation_uuid AND e.state='final' AND e.profile_canonical=NEW.current_profile)"
    guard(
        conn,
        CONTROL + "_update",
        CONTROL,
        "UPDATE",
        " OR ".join(
            f"NEW.{f} {eq} OLD.{f}"
            for f in (
                "business_id",
                "created_by",
                "created_at",
                "provenance",
                "activation_generation",
                "ever_enabled",
            )
        )
        + " OR NEW.control_revision<>OLD.control_revision+1 OR NOT ("
        + valid
        + ")",
    )


def downgrade(conn):
    if any(conn.execute("SELECT 1 FROM " + t + " LIMIT 1").fetchone() for t in TABLES):
        raise ValueError("Conservar evidencia readiness; bajada74 bloqueada.")
    from noesis.financial_history.import_schema import _drop

    for table, names in (
        (CAPABILITIES, ("retain", "insert", "immutable")),
        (CONTROL, ("retain", "insert", "update")),
        (EVALUATIONS, ("retain", "insert", "update")),
    ):
        for name in names:
            _drop(conn, table + "_" + name, table)
        conn.execute("DROP TABLE " + table)
