"""Política conservadora, inventario sin PII duplicada y revisión explícita."""

from datetime import datetime, timezone
import json

from .catalog import COLUMNS, FINANCIAL_TABLES
from .contracts import Category, Permission, PolicyStatus, RetentionMode, digest, evidence_value, validate_policy
from .repository import PrivacyRepository
from .schema import POLICIES, INVENTORIES
from noesis.financial_operations.contracts import ConflictError, AccessDenied, uuid_text


CREDENTIAL_TABLES = ("oauth_credentials", "portal_tokens", "worker_tokens", "whatsapp_links", "gestoria_invitations", "support_access_grants")
COMMUNICATION_TABLES = ("assistant_messages", "business_memories", "whatsapp_pending_actions")

# Sólo estos campos tienen acción implementada en E. Una regla de categoría no
# concede permiso para borrar otras columnas, tablas ni justificantes.
ACTION_FIELDS = {
    "clients": ("phone", "email", "address", "zone"),
    "leads": ("name", "phone", "email", "note"),
    "assistant_messages": ("content",),
    "whatsapp_pending_actions": ("rows",),
    "users": ("is_active", "password_hash", "session_version"),
    "oauth_credentials": ("refresh_token", "access_token", "status", "account_email", "last_error"),
    "portal_tokens": ("revoked",), "worker_tokens": ("revoked",),
    "workers": ("active", "access_code", "pin_hash"),
    "password_resets": ("used",), "whatsapp_links": ("rows",),
    "gestoria_invitations": ("revoked_at",),
    "support_access_grants": ("status", "revoked_at"),
    "businesses": ("gestoria_token", "calendar_token"),
    "inbound_email_routes": ("active",),
    "whatsapp_connections": ("outbound_enabled", "inbound_enabled"),
}


def quoted_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def provisional_policy(policy_uuid):
    reference = "professional-review-pending"
    return dict(version=1, policy_uuid=uuid_text(policy_uuid), status=PolicyStatus.PROVISIONAL.value,
                reference=reference, rules=[dict(category=c.value, basis_reference=reference,
                                                mode=RetentionMode.HOLD.value, purge_after=None,
                                                review_status=PolicyStatus.PROVISIONAL.value) for c in Category])


def category_for(table):
    if table in CREDENTIAL_TABLES or table in ("password_resets", "users"):
        return Category.CREDENTIAL
    if table.startswith("financial_activation") or table.startswith("financial_readiness") or table == "financial_authorizations":
        return Category.ACTIVATION
    if table.startswith("financial_") or table.startswith("economic_") or table.endswith("coverage") or table == "bank_payment_links":
        return Category.PROVENANCE
    if table.startswith("verifactu_"):
        return Category.TRANSPORT
    if table in ("documents", "document_classifications", "document_profiles"):
        return Category.DOCUMENT
    if table == "privacy_requests":
        return Category.PRIVACY
    if table in FINANCIAL_TABLES or table.startswith("worker_clockin"):
        return Category.FISCAL
    if table in COMMUNICATION_TABLES or table == "email_outbox":
        return Category.COMMUNICATION
    return Category.PERSONAL


def source_inventory(session, bid):
    """Hash de filas raw, incluidas credenciales, sin conservar contenido ni selector PII.

    E se excluye para evitar autorreferencia. Toda tabla tenant, incluso fuera de
    export, se clasifica; no tener fecha aprobada sigue explícitamente bajo hold.
    """
    conn = session.borrowed_connection
    if session.dialect == "postgres":
        tables = [r["table_name"] for r in conn.execute_exact("SELECT table_name FROM information_schema.columns WHERE table_schema=current_schema() AND column_name='business_id' ORDER BY table_name").fetchall()]
    else:
        tables = [r["name"] for r in conn.execute_exact("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
                  if any(col["name"] == "business_id" for col in conn.execute_exact("PRAGMA table_info(" + quoted_identifier(r["name"]) + ")").fetchall())]
    from .schema import TABLES
    result = {}
    for t in tables + ["businesses", "password_resets"]:
        if t in TABLES:
            continue
        clause = "business_id=?" if t != "businesses" else "id=?"
        if t == "password_resets":
            clause = "user_id IN (SELECT id FROM users WHERE business_id=?)"
        hashes = sorted(digest(evidence_value(dict(r))) for r in conn.execute_exact("SELECT * FROM " + quoted_identifier(t) + " WHERE " + clause, (bid,)).fetchall())
        result[t] = dict(count=len(hashes), source_hash=digest(hashes), category=category_for(t).value)
    return result


def register_policy(session, bid, principal, value, *, approved_hash=None, permission=Permission.POLICY):
    repo = PrivacyRepository(session, bid)
    repo.principal(principal)
    validate_policy(value)
    if permission != Permission.POLICY:
        raise AccessDenied("privacy.retention.approve requerido.")
    if value["status"] == PolicyStatus.PROVISIONAL and approved_hash is not None:
        raise AccessDenied("Política provisional no admite aprobación.")
    if value["status"] == PolicyStatus.APPROVED and approved_hash != digest(value):
        raise AccessDenied("Confirmación humana exacta de política requerida.")
    body = dict(policy=value, approved_by=principal.user_id if approved_hash else None,
                approval_session_version=principal.session_version if approved_hash else None,
                approved_hash=approved_hash)
    repo.store(POLICIES, value["policy_uuid"], principal, body, datetime.now(timezone.utc).isoformat(), status=value["status"])
    return body


def inventory(session, bid, principal, inventory_uuid, policy_uuid):
    repo = PrivacyRepository(session, bid)
    repo.principal(principal)
    policy_body = repo.body(POLICIES, policy_uuid)
    policy = validate_policy(policy_body["policy"])
    rules = {r["category"]: r for r in policy["rules"]}
    sections = source_inventory(session, bid)
    for name, proof in sections.items():
        rule = rules[proof["category"]]
        proof.update(rule=rule, policy_uuid=policy["policy_uuid"], policy_version=policy["version"],
                     classification=rule["mode"], legal_hold=rule["mode"] == RetentionMode.HOLD,
                     approved_purge_date=None, eligible_fields=list(ACTION_FIELDS.get(name, ())),
                     other_fields="retained_no_action_v1")
    body = dict(version=1, business_id=bid, inventory_uuid=uuid_text(inventory_uuid),
                policy_uuid=policy["policy_uuid"], policy_hash=digest(policy_body), sections=sections,
                source_hash=digest(source_inventory(session, bid)))
    repo.store(INVENTORIES, inventory_uuid, principal, body, datetime.now(timezone.utc).isoformat(), policy_uuid=policy["policy_uuid"])
    return body


def verify_inventory(session, bid, value):
    if value["business_id"] != bid or digest(source_inventory(session, bid)) != value["source_hash"]:
        raise ConflictError("Inventario stale: crear versión nueva.")


def readiness_evidence(session, bid):
    """Pruebas E exclusivamente para evaluaciones nuevas; no editar A anterior."""
    from .repository import installed
    if not installed(session):
        return dict(export_ready=False, privacy_ready=False, reason="E_SCHEMA_MISSING")
    from .schema import EXPORTS, AUTHORIZATIONS, RESTORED
    if session.execute(f"SELECT 1 FROM {AUTHORIZATIONS} WHERE business_id=? UNION SELECT 1 FROM {RESTORED} WHERE business_id=? AND scope='account_local_access' LIMIT 1", (bid, bid)).fetchone():
        return dict(export_ready=True, privacy_ready=False, reason="ACCOUNT_CLOSING_OR_CLOSED")
    # Contrato/implementación/catálogo presentes y última exportación verificable
    # contra el snapshot económico (metadatos E posteriores no invalidan fuentes).
    row = session.execute(f"SELECT * FROM {EXPORTS} WHERE business_id=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1", (bid,)).fetchone()
    export_ready = False
    if row:
        manifest = json.loads(row["body_canonical"])
        from .export import read_section
        export_ready = (digest(manifest) == row["content_hash"] and manifest["client_id"] is None
                        and manifest["schema_version"] == 78 and manifest["final_result"] == "complete"
                        and all(manifest["sections"].get(t) == {"count": len(rows), "content_hash": digest(rows)}
                                for t in FINANCIAL_TABLES if t in COLUMNS and t not in ("financial_readiness_evaluations", "financial_readiness_capabilities", "financial_activation_control")
                                for rows in [read_section(session, bid, t)]))
    policy = session.execute(f"SELECT * FROM {POLICIES} WHERE business_id=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1", (bid,)).fetchone()
    privacy_ready = False
    if policy and policy["status"] == PolicyStatus.APPROVED:
        body = PrivacyRepository(session, bid).body(POLICIES, str(policy["evidence_uuid"]))
        value = validate_policy(body["policy"])
        privacy_ready = body["approved_hash"] == digest(value) and body["approved_by"] == policy["created_by"]
    return dict(export_ready=export_ready, privacy_ready=privacy_ready,
                policy_status=policy["status"] if policy else "provisional", reason="LEGAL_POLICY_PENDING" if not privacy_ready else "E_CONTRACT_INSTALLED")
