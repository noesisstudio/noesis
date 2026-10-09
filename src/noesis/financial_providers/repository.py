"""Repositorios F sobre la conexión/TX prestada; no pool ni commit propio."""

import json
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.execution_context import execution_context
from noesis.financial_operations.contracts import AccessDenied, ConflictError, Principal
from .contracts import canonical, digest, tenant, uuid_text, stamp
from .schema import TABLES


class ProviderRepository:
    def __init__(self, session, business_id):
        if not isinstance(session, FinancialSession):
            raise TypeError("FinancialSession requerida.")
        self.s, self.bid = session, tenant(business_id)

    def principal(self, principal):
        if not isinstance(principal, Principal):
            raise AccessDenied("Sesión humana requerida.")
        row = self.s.execute("SELECT is_active,session_version FROM users WHERE business_id=? AND id=?", (self.bid, principal.user_id)).fetchone()
        if not row or not row["is_active"] or row["session_version"] != principal.session_version:
            raise AccessDenied("SESSION_STALE")
        return principal

    def load(self, table, uid):
        if table not in TABLES:
            raise ValueError("Tabla F desconocida.")
        row = self.s.execute("SELECT * FROM " + table + " WHERE business_id=? AND evidence_uuid=?", (self.bid, uuid_text(uid))).fetchone()
        if not row:
            return None
        body = json.loads(row["body_canonical"])
        from .validation import validate
        validate(table, body)
        if canonical(body) != row["body_canonical"] or digest(body) != row["content_hash"] or body["business_id"] != self.bid:
            raise ConflictError("Evidencia F incoherente.")
        return body

    def append(self, table, uid, principal, body, created_at, **columns):
        from .validation import validate
        validate(table, body)
        from .schema import RESULTS, ATTEMPTS, STARTS
        terminal = (table == RESULTS and self.s.execute(f"SELECT 1 FROM {ATTEMPTS} a JOIN {STARTS} st ON st.business_id=a.business_id AND st.attempt_uuid=a.evidence_uuid WHERE a.business_id=? AND a.evidence_uuid=? AND a.created_by=? AND a.session_version=?", (self.bid, body.get('attempt_uuid'), principal.user_id, principal.session_version)).fetchone())
        if not terminal:
            self.principal(principal)
        if table not in TABLES or body["business_id"] != self.bid:
            raise ValueError("Tabla/tenant F inválidos.")
        uid = uuid_text(uid)
        old = self.load(table, uid)
        if old is not None:
            if old != body:
                raise ConflictError("UUID F ya vinculado a otro contenido.")
            return old
        context = dict(kind="financial_provider", business_id=self.bid, table=table, evidence_uuid=uid,
                       content_hash=digest(body), actor_user_id=principal.user_id,
                       actor_session_version=principal.session_version, created_at=stamp(created_at))
        names = ["business_id", "evidence_uuid", "contract_version", "created_by", "session_version", "created_at", "body_canonical", "content_hash", *columns]
        values = [self.bid, uid, 1, principal.user_id, principal.session_version, stamp(created_at), canonical(body), digest(body), *columns.values()]
        with execution_context(self.s, context):
            self.s.execute("INSERT INTO " + table + " (" + ",".join(names) + ") VALUES (" + ",".join("?" for _ in values) + ")", values)
        return body
