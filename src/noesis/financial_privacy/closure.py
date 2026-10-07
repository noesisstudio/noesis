"""Cierre con conservación: plan → confirmación humana exacta → recibo atómico.

Nunca pausa/activa D ni altera prueba económica. No revocación remota ni borrado
de bytes documentales en v1: todos los documentos permanecen bajo conservación.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from uuid import uuid5, NAMESPACE_URL

from noesis import db
from noesis.core.locks import lock_business
from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import AccessDenied, ConflictError, StateError, uuid_text
from .contracts import Permission, PolicyStatus, RetentionMode, digest, tombstone_actions
from .repository import PrivacyRepository, installed
from .retention import inventory, verify_inventory, validate_policy
from .schema import PLANS, POLICIES, INVENTORIES, AUTHORIZATIONS, RECEIPTS, TOMBSTONES


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def activation_state(s, bid):
    row = s.execute("SELECT state,activation_generation,ever_enabled FROM financial_activation_control WHERE business_id=?", (bid,)).fetchone()
    return dict(row) if row else dict(state="off", activation_generation=0, ever_enabled=False)


def blockers(s, bid):
    state = activation_state(s, bid)
    reasons = []
    if state["ever_enabled"] and state["state"] != "paused":
        reasons.append("PAUSE_REQUIRED")
    n = s.execute("SELECT COUNT(*) AS n FROM financial_operations WHERE business_id=? AND state IN ('prepared','approved') AND entry_namespace NOT LIKE ?", (bid, "historical%")).fetchone()["n"]
    if n:
        reasons.append("EXECUTABLE_OPERATIONS_PENDING")
    dispatch = {}
    for table in ("email_outbox", "whatsapp_outbox", "verifactu_outbox", "verifactu_cancellation_outbox"):
        uncertain = s.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE business_id=? AND (locked_at IS NOT NULL OR status IN ('processing','sending','enviado'))", (bid,)).fetchone()["n"]
        terminal = ("aceptado", "aceptado_con_errores", "rechazado", "fallido") if table.startswith("verifactu") else ("sent", "delivered", "read", "failed", "cancelled")
        pending = s.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE business_id=? AND status NOT IN ({','.join('?' for _ in terminal)})", (bid, *terminal)).fetchone()["n"]
        dispatch[table] = dict(uncertain=uncertain, pending=pending)
        if uncertain:
            reasons.append("UNCERTAIN_DISPATCH")
    return sorted(set(reasons)), dispatch, state


class FinancialClosure:
    def __init__(self, business_id):
        from noesis.financial_operations.contracts import positive_id
        self.bid = positive_id(business_id)

    @contextmanager
    def transaction(self, principal, *, retry=False):
        with db.get_conn() as conn:
            s = FinancialSession(conn)
            if s.dialect == "sqlite":
                s.execute("BEGIN IMMEDIATE")
            lock_business(s, self.bid)
            if not installed(s):
                raise StateError("Schema78 requerido.")
            repo = PrivacyRepository(s, self.bid)
            # Recuperación postcommit no concede acceso a otra sesión/persona.
            if not retry:
                repo.principal(principal)
            yield s, repo

    def plan(self, principal, plan_uuid, *, privacy_request_id, policy_uuid, inventory_uuid=None, checkpoint=None):
        with self.transaction(principal) as (s, repo):
            old = repo.load(PLANS, plan_uuid)
            if old:
                body = json.loads(old["body_canonical"])
                if body["privacy_request_id"] != privacy_request_id or body["policy_uuid"] != uuid_text(policy_uuid) or old["created_by"] != principal.user_id or old["session_version"] != principal.session_version:
                    raise ConflictError("Plan UUID pertenece a otro contexto.")
                verify_inventory(s, self.bid, repo.body(INVENTORIES, body["inventory_uuid"]))
                return body
            request = s.execute("SELECT id,request_type,status,requester_user_id FROM privacy_requests WHERE id=? AND business_id=?", (privacy_request_id, self.bid)).fetchone()
            if not request or request["request_type"] != "account_closure" or request["requester_user_id"] != principal.user_id or request["status"] in ("completed", "cancelled", "rejected"):
                raise AccessDenied("Solicitud account_closure abierta del titular requerida.")
            if checkpoint:
                checkpoint("before_plan", s)
            inv_uid = uuid_text(inventory_uuid or uuid5(NAMESPACE_URL, "closure-inventory:" + uuid_text(plan_uuid)))
            inv = inventory(s, self.bid, principal, inv_uid, policy_uuid)
            if checkpoint:
                checkpoint("after_inventory", s)
            blocked, dispatch, state = blockers(s, self.bid)
            if repo.body(POLICIES, policy_uuid)["policy"]["status"] != PolicyStatus.APPROVED:
                blocked = sorted(set(blocked) | {"LEGAL_POLICY_PENDING"})
            body = dict(version=1, plan_uuid=uuid_text(plan_uuid), business_id=self.bid, privacy_request_id=privacy_request_id,
                        policy_uuid=uuid_text(policy_uuid), policy_hash=inv["policy_hash"], inventory_uuid=inv_uid,
                        inventory_hash=digest(inv), source_hash=inv["source_hash"], activation=state,
                        retained_sections={t: p for t, p in inv["sections"].items() if p["classification"] in (RetentionMode.RETAIN, RetentionMode.HOLD)},
                        minimizable_sections={t: p for t, p in inv["sections"].items() if p["classification"] in (RetentionMode.MINIMIZE, RetentionMode.INVALIDATE)},
                        credential_actions=["INVALIDATE_LOCAL_ACCESS"], file_actions=[],
                        pending_dispatch=dispatch, blockers=blocked,
                        limitations=["DOCUMENT_BYTES_RETAINED", "REMOTE_REVOKES_PENDING_F", "NO_TEMPORAL_PURGE"],
                        created_by=principal.user_id, session_version=principal.session_version)
            repo.store(PLANS, plan_uuid, principal, body, now(), inventory_uuid=inv_uid, privacy_request_id=privacy_request_id)
            return body

    def _verify(self, s, repo, plan):
        inv = repo.body(INVENTORIES, plan["inventory_uuid"])
        verify_inventory(s, self.bid, inv)
        policy_body = repo.body(POLICIES, plan["policy_uuid"])
        policy = validate_policy(policy_body["policy"])
        latest = s.execute(f"SELECT evidence_uuid FROM {POLICIES} WHERE business_id=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1", (self.bid,)).fetchone()
        if not latest or str(latest["evidence_uuid"]) != plan["policy_uuid"]:
            raise ConflictError("Política sustituida: crear plan nuevo.")
        if policy["status"] != PolicyStatus.APPROVED or policy_body["approved_hash"] != digest(policy):
            raise StateError("Política legal pendiente: no ejecutar cierre con minimización.")
        if digest(policy_body) != plan["policy_hash"] or digest(inv) != plan["inventory_hash"]:
            raise ConflictError("Política/inventario cambió.")
        from .schema import EXPORTS
        exported = s.execute(f"SELECT * FROM {EXPORTS} WHERE business_id=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1", (self.bid,)).fetchone()
        if not exported or json.loads(exported["body_canonical"])["purpose"] != "account_closure" or json.loads(exported["body_canonical"])["client_id"] is not None:
            raise StateError("Export account_closure previo requerido.")
        # Export de cierre debe cubrir las fuentes actuales, no sólo existir.
        # La autorización formal bloquea readiness, pero no invalida el snapshot.
        from .export import read_section
        from .catalog import FINANCIAL_TABLES
        manifest = json.loads(exported["body_canonical"])
        if digest(manifest) != exported["content_hash"]:
            raise ConflictError("Manifest de cierre corrupto.")
        if any(manifest["sections"].get(t) != {"count": len(rows), "content_hash": digest(rows)}
               for t in FINANCIAL_TABLES
               for rows in [read_section(s, self.bid, t)]):
            raise ConflictError("Export de cierre stale: generar nuevo export y plan.")
        blocked, dispatch, state = blockers(s, self.bid)
        if blocked:
            raise StateError(",".join(blocked))
        if state != plan["activation"] or dispatch != plan["pending_dispatch"]:
            raise ConflictError("Estado/dispatch cambió: plan nuevo requerido.")
        request = s.execute("SELECT requester_user_id,status FROM privacy_requests WHERE business_id=? AND id=?", (self.bid, plan["privacy_request_id"])).fetchone()
        if not request or request["requester_user_id"] != plan["created_by"] or request["status"] in ("completed", "cancelled", "rejected"):
            raise StateError("Solicitud ya no disponible.")
        return inv, policy

    def authorize(self, principal, plan_uuid, *, approved_hash, authorization_uuid=None, permission=Permission.AUTHORIZE, checkpoint=None):
        if permission != Permission.AUTHORIZE:
            raise AccessDenied("privacy.financial.close requerido.")
        with self.transaction(principal) as (s, repo):
            plan = repo.body(PLANS, plan_uuid)
            if plan["created_by"] != principal.user_id or plan["session_version"] != principal.session_version or digest(plan) != approved_hash:
                raise AccessDenied("Confirmación humana exacta del plan y sesión requerida.")
            self._verify(s, repo, plan)
            prior = s.execute("SELECT plan_uuid FROM financial_closure_authorizations WHERE business_id=?", (self.bid,)).fetchone()
            if prior and str(prior["plan_uuid"]) != uuid_text(plan_uuid):
                raise StateError("Otro plan ya tiene autorización formal.")
            uid = uuid_text(authorization_uuid or uuid5(NAMESPACE_URL, "closure-authority:" + uuid_text(plan_uuid)))
            body = dict(version=1, business_id=self.bid, authorization_uuid=uid, plan_uuid=uuid_text(plan_uuid),
                        approved_hash=approved_hash, actor_user_id=principal.user_id, session_version=principal.session_version,
                        kind="human_exact", permission=Permission.AUTHORIZE.value)
            repo.store(AUTHORIZATIONS, uid, principal, body, now(), plan_uuid=uuid_text(plan_uuid), approved_hash=approved_hash)
            if checkpoint:
                checkpoint("after_authorization", s)
            return body

    def apply(self, principal, plan_uuid, *, authorization_uuid, receipt_uuid=None, checkpoint=None):
        uid = uuid_text(receipt_uuid or uuid5(NAMESPACE_URL, "closure-receipt:" + uuid_text(plan_uuid)))
        with self.transaction(principal, retry=True) as (s, repo):
            existing = repo.load(RECEIPTS, uid)
            if existing:
                body = json.loads(existing["body_canonical"])
                if (body["plan_uuid"] != uuid_text(plan_uuid) or body["authorization_uuid"] != uuid_text(authorization_uuid)
                        or existing["created_by"] != principal.user_id or existing["session_version"] != principal.session_version):
                    raise AccessDenied("Recibo de cierre no disponible para esta identidad.")
                return body
            repo.principal(principal)
            plan = repo.body(PLANS, plan_uuid)
            auth = repo.body(AUTHORIZATIONS, authorization_uuid)
            if (auth["plan_uuid"] != uuid_text(plan_uuid) or auth["approved_hash"] != digest(plan)
                    or auth["actor_user_id"] != principal.user_id or auth["session_version"] != principal.session_version):
                raise AccessDenied("Autoridad de cierre no corresponde al plan/sesión.")
            inv, policy = self._verify(s, repo, plan)
            from .export import read_sections
            from .schema import TABLES, RESTORED
            retained_before = {t: rows for t, rows in read_sections(s, self.bid).items() if t not in TABLES + (RESTORED,)}
            # Prueba económica y todas las referencias permanecen byte a byte.
            rules = {r["category"]: r for r in policy["rules"]}
            if rules["credentials_secrets"]["mode"] != RetentionMode.INVALIDATE:
                raise StateError("Política debe autorizar invalidación de credenciales locales.")
            actions = ["invalidate_local_credentials"]
            if rules["operational_personal"]["mode"] == RetentionMode.MINIMIZE:
                actions.append("minimize_operational_contacts")
            if rules["communications_support"]["mode"] == RetentionMode.MINIMIZE:
                actions.append("minimize_unreferenced_communications")
            body = dict(version=1, business_id=self.bid, receipt_uuid=uid, plan_uuid=uuid_text(plan_uuid),
                        authorization_uuid=uuid_text(authorization_uuid), privacy_request_id=plan["privacy_request_id"],
                        inventory_uuid=plan["inventory_uuid"], inventory_hash=digest(inv), policy_uuid=plan["policy_uuid"],
                        policy_hash=plan["policy_hash"], previous_activation=plan["activation"], final_state="closed_restricted",
                        retained_sections=plan["retained_sections"], retained_hash=digest(plan["retained_sections"]),
                        financial_proof_hash=digest(retained_before),
                        actions=actions, action_counts=self._action_counts(s, actions),
                        pending_external_actions=["PROVIDER_REMOTE_REVOCATION_REVIEW_F", "BACKUP_SUPPRESSION_REPLAY"],
                        applied_at=now(), actor_user_id=principal.user_id, session_version=principal.session_version)
            repo.store(RECEIPTS, uid, principal, body, body["applied_at"], plan_uuid=uuid_text(plan_uuid), authorization_uuid=uuid_text(authorization_uuid))
            tombstone = dict(version=1, business_id=self.bid, closure_uuid=uid, scope="account_local_access",
                             category=sorted({"invalidate_local_credentials": "credentials_secrets", "minimize_operational_contacts": "operational_personal", "minimize_unreferenced_communications": "communications_support"}[a] for a in actions), policy_uuid=plan["policy_uuid"], selector_version=1,
                             selector={"business_id": self.bid}, evidence_hash=digest(body), applied_at=body["applied_at"])
            repo.store(TOMBSTONES, uuid5(NAMESPACE_URL, "closure-tombstone:" + uid), principal, tombstone, body["applied_at"], receipt_uuid=uid)
            if checkpoint:
                checkpoint("before_minimization", s)
            apply_local_actions(s, self.bid, actions)
            retained_after = {t: rows for t, rows in read_sections(s, self.bid).items() if t not in TABLES + (RESTORED,)}
            if digest(retained_after) != body["financial_proof_hash"]:
                raise ConflictError("Cierre alteró evidencia financiera: rollback obligatorio.")
            if checkpoint:
                checkpoint("during_minimization", s)
                checkpoint("before_commit", s)
        if checkpoint:
            checkpoint("after_commit", None)
        return body

    def _action_counts(self, s, actions):
        from .retention import ACTION_FIELDS
        personal = {"clients", "leads"}
        communication = {"assistant_messages", "whatsapp_pending_actions"}
        result = {}
        for table, fields in ACTION_FIELDS.items():
            if table == "users" and "minimize_operational_contacts" in actions:
                fields = fields + ("email",)
            if table in personal and "minimize_operational_contacts" not in actions:
                continue
            if table in communication and "minimize_unreferenced_communications" not in actions:
                continue
            clause = "id=?" if table == "businesses" else "business_id=?"
            if table == "password_resets":
                clause = "user_id IN (SELECT id FROM users WHERE business_id=?)"
            rows = s.borrowed_connection.execute_exact(f"SELECT * FROM {table} WHERE {clause}", (self.bid,)).fetchall()
            # No duplicar PII: sólo hash de origen, campos autorizados y recuento
            # de filas seleccionadas; no afirmar que todos los campos cambiaron.
            from .contracts import evidence_value
            result[table] = dict(selected_rows=len(rows), fields=list(fields),
                                 source_hash=digest(sorted(digest(evidence_value(dict(r))) for r in rows)),
                                 result="applied_in_same_transaction", document_bytes_deleted=0)
        return result


def apply_local_actions(s, bid, actions):
    """Replay idempotente. Sólo acceso local y comunicaciones sin FK de prueba.

    No reemplazar emails por texto único: conservar identidad técnica y campos
    posiblemente usados en hashes. Password hash inutilizable; ninguna red.
    """
    if "invalidate_local_credentials" in actions:
        s.execute("UPDATE users SET is_active=FALSE,password_hash='',session_version=session_version+1 WHERE business_id=? AND (is_active=TRUE OR password_hash<>'')", (bid,))
        s.execute("UPDATE oauth_credentials SET refresh_token=NULL,access_token=NULL,status='revoked',account_email=NULL,last_error=NULL WHERE business_id=?", (bid,))
        s.execute("UPDATE portal_tokens SET revoked=TRUE WHERE business_id=?", (bid,))
        s.execute("UPDATE worker_tokens SET revoked=TRUE WHERE business_id=?", (bid,))
        s.execute("UPDATE workers SET active=FALSE,access_code='closed-' || CAST(id AS TEXT),pin_hash=NULL WHERE business_id=?", (bid,))
        s.execute("UPDATE password_resets SET used=TRUE WHERE user_id IN (SELECT id FROM users WHERE business_id=?)", (bid,))
        s.execute("DELETE FROM whatsapp_links WHERE business_id=?", (bid,))
        s.execute("UPDATE gestoria_invitations SET revoked_at=COALESCE(revoked_at,?) WHERE business_id=?", (now(), bid))
        s.execute("UPDATE support_access_grants SET status='revoked',revoked_at=COALESCE(revoked_at,?) WHERE business_id=?", (now(), bid))
        s.execute("UPDATE businesses SET gestoria_token=NULL,calendar_token=NULL WHERE id=?", (bid,))
        s.execute("UPDATE inbound_email_routes SET active=FALSE WHERE business_id=?", (bid,))
        s.execute("UPDATE whatsapp_connections SET outbound_enabled=FALSE,inbound_enabled=FALSE WHERE business_id=?", (bid,))
    if "minimize_operational_contacts" in actions:
        # No FK apunta a estos campos; prueba fiscal usa copias canónicas, no
        # contactos vivos. Business name/nif/address y fuentes quedan intactos.
        s.execute("UPDATE clients SET phone=NULL,email=NULL,address=NULL,zone=NULL WHERE business_id=?", (bid,))
        s.execute("UPDATE users SET email='closed-' || CAST(id AS TEXT) || '@invalid.local' WHERE business_id=?", (bid,))
        s.execute("UPDATE leads SET name='Contacto restringido',phone=NULL,email=NULL,note=NULL WHERE business_id=?", (bid,))
    if "minimize_unreferenced_communications" in actions:
        s.execute("UPDATE assistant_messages SET content='' WHERE business_id=?", (bid,))
        s.execute("DELETE FROM whatsapp_pending_actions WHERE business_id=?", (bid,))


def reapply_tombstones(session):
    """Antes de servir una restauración: replay de supresión ya aplicada, no nueva autoridad."""
    if not installed(session):
        return
    rows = session.execute(f"SELECT business_id,evidence_uuid FROM {TOMBSTONES} ORDER BY business_id,evidence_uuid").fetchall()
    from .schema import RESTORED
    overlays = session.execute(f"SELECT * FROM {RESTORED} ORDER BY business_id,evidence_uuid").fetchall()
    for overlay in overlays:
        value = json.loads(overlay["body_canonical"])
        selector = {"business_id": overlay["business_id"]}
        if overlay["scope"] == "client_contact":
            selector["client_id"] = overlay["client_id"]
        tombstone_actions(value)
        if digest(value) != overlay["content_hash"] or value["selector"] != selector:
            raise StateError("Overlay de supresión corrupto; no servir.")
        if overlay["scope"] == "account_local_access":
            apply_local_actions(session, overlay["business_id"], tombstone_actions(value))
        else:
            from .client import apply_client_actions
            apply_client_actions(session, overlay["business_id"], overlay["client_id"])
    for row in rows:
        repo = PrivacyRepository(session, row["business_id"])
        body = repo.body(TOMBSTONES, str(row["evidence_uuid"]))
        account = body["scope"] == "account_local_access"
        from .schema import CLIENT_ERASURES
        receipt = repo.body(RECEIPTS if account else CLIENT_ERASURES, body["closure_uuid"] if account else body["suppression_uuid"])
        selector = {"business_id": row["business_id"]}
        if not account:
            selector["client_id"] = receipt["client_id"]
        replay = tombstone_actions(body)
        if body["evidence_hash"] != digest(receipt) or body["selector"] != selector or (account and set(replay) != set(receipt["actions"])):
            raise StateError("Tombstone/recibo incoherente: no servir restauración.")
        lock_business(session, row["business_id"])
        if account:
            apply_local_actions(session, row["business_id"], tombstone_actions(body))
        else:
            from .client import apply_client_actions
            apply_client_actions(session, row["business_id"], receipt["client_id"])
