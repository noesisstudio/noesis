"""Conservación del subgrafo financiero de cliente, antes del borrado legacy."""

from noesis import db
from noesis.core.locks import lock_business
from noesis.core.persistence import FinancialSession
from .repository import installed
from .repository import PrivacyRepository
from .contracts import digest, RetentionMode, PolicyStatus
from .schema import POLICIES, CLIENT_ERASURES, TOMBSTONES, RESTORED
from .export import read_sections
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5


def preserve_financial_client(client_id, business_id, principal=None):
    """No reescribir hashes ni eliminar justificantes; política pendiente es bloqueo."""
    with db.get_conn() as conn:
        s = FinancialSession(conn)
        if not installed(s):
            return None
        if s.dialect == "sqlite":
            s.execute("BEGIN IMMEDIATE")
        lock_business(s, business_id)
        if not s.execute("SELECT 1 FROM clients WHERE business_id=? AND id=?", (business_id, client_id)).fetchone():
            return False
        from noesis.financial_history.fence import assert_writable
        assert_writable(s, business_id)
        protected = s.execute("SELECT 1 FROM invoices i WHERE i.business_id=? AND i.client_id=? AND (i.status<>'borrador' OR EXISTS(SELECT 1 FROM invoice_payments p WHERE p.business_id=i.business_id AND p.invoice_id=i.id) OR EXISTS(SELECT 1 FROM economic_events e WHERE e.business_id=i.business_id AND e.invoice_id=i.id)) LIMIT 1", (business_id, client_id)).fetchone()
        documents = s.execute("SELECT 1 FROM documents WHERE business_id=? AND client_id=? AND (invoice_id IS NOT NULL OR received_invoice_id IS NOT NULL OR expense_id IS NOT NULL) LIMIT 1", (business_id, client_id)).fetchone()
        history = s.execute("SELECT 1 FROM financial_history_manifests WHERE business_id=? LIMIT 1", (business_id,)).fetchone()
        if protected or documents or history:
            if principal is None:
                raise ValueError("Cliente con evidencia financiera conservada; requiere privacidad autenticada y política aprobada. No se han borrado datos.")
            repo = PrivacyRepository(s, business_id)
            repo.principal(principal)
            row = s.execute(f"SELECT evidence_uuid FROM {POLICIES} WHERE business_id=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1", (business_id,)).fetchone()
            if not row:
                raise ValueError("Política de minimización pendiente.")
            policy = repo.body(POLICIES, str(row["evidence_uuid"]))
            from .contracts import validate_policy
            contract = validate_policy(policy["policy"])
            if (contract["status"] != PolicyStatus.APPROVED or policy["approved_hash"] != digest(contract)
                    or not any(r["category"] == "operational_personal" and r["mode"] == RetentionMode.MINIMIZE for r in contract["rules"])):
                raise ValueError("Política de minimización pendiente.")
            uid = uuid5(NAMESPACE_URL, f"client-erasure:{business_id}:{client_id}:{contract['policy_uuid']}:{principal.user_id}:{principal.session_version}")
            old = repo.load(CLIENT_ERASURES, uid)
            if old:
                apply_client_actions(s, business_id, client_id)
                return True
            # Usar privacy_requests, nunca un segundo ticket financiero. Esta
            # inserción comparte TX; las referencias originales se mantienen.
            stamp = datetime.now(timezone.utc).isoformat()
            request = s.execute("SELECT id FROM privacy_requests WHERE business_id=? AND requester_user_id=? AND request_type='erasure' AND status IN ('received','in_review','legal_hold') ORDER BY id LIMIT 1", (business_id, principal.user_id)).fetchone()
            if not request:
                request = s.execute("INSERT INTO privacy_requests(business_id,requester_user_id,request_type,status,retention_required,requested_at,updated_at) VALUES (?,?,'erasure','received',TRUE,?,?) RETURNING id", (business_id, principal.user_id, stamp, stamp)).fetchone()
            proof = read_sections(s, business_id, client_id=client_id)
            # El recibo de cliente se excluye del hash de la prueba financiera.
            proof.pop(CLIENT_ERASURES, None)
            proof.pop(TOMBSTONES, None)
            proof.pop(RESTORED, None)
            body = dict(version=1, business_id=business_id, client_id=client_id, policy_uuid=contract["policy_uuid"],
                        policy_hash=digest(policy), privacy_request_id=request["id"], actor_user_id=principal.user_id,
                        session_version=principal.session_version, authority="authenticated_human_client_erasure",
                        fields=["phone", "email", "address", "zone"], credential_actions=["REVOKE_CLIENT_PORTAL_LOCAL"], retained_financial_hash=digest(proof),
                        retained_client_id=client_id, document_bytes="retained", applied_at=stamp)
            repo.store(CLIENT_ERASURES, uid, principal, body, stamp, client_id=client_id,
                       policy_uuid=contract["policy_uuid"], privacy_request_id=request["id"])
            tombstone = dict(version=1, business_id=business_id, suppression_uuid=str(uid), scope="client_contact",
                             category=["operational_personal"], policy_uuid=contract["policy_uuid"], selector_version=1,
                             selector={"business_id": business_id, "client_id": client_id},
                             evidence_hash=digest(body), applied_at=stamp)
            repo.store(TOMBSTONES, uuid5(NAMESPACE_URL, "client-tombstone:" + str(uid)), principal, tombstone, stamp, client_erasure_uuid=str(uid))
            # Nombre/NIF/identidad conservados; no alterar campos fiscales vivos.
            apply_client_actions(s, business_id, client_id)
            after = read_sections(s, business_id, client_id=client_id)
            after.pop(CLIENT_ERASURES, None)
            after.pop(TOMBSTONES, None)
            after.pop(RESTORED, None)
            if digest(after) != body["retained_financial_hash"]:
                raise ValueError("Minimización afectó prueba financiera: rollback obligatorio.")
            return True
    return None


def apply_client_actions(session, business_id, client_id):
    """Selector técnico tenant/cliente; ninguna ruta ni dato de contacto en tombstone."""
    session.execute("UPDATE clients SET phone=NULL,email=NULL,address=NULL,zone=NULL WHERE id=? AND business_id=?", (client_id, business_id))
    session.execute("UPDATE portal_tokens SET revoked=TRUE WHERE client_id=? AND business_id=?", (client_id, business_id))
