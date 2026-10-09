"""Repositorio E tenant-scoped sobre FinancialSession prestada; ningún commit."""

import json

from noesis.core.persistence import FinancialSession
from noesis.financial_activation.execution_context import execution_context
from noesis.financial_operations.contracts import AccessDenied, ConflictError, Principal, StateError, positive_id, uuid_text
from .contracts import canonical, digest
from .schema import TABLES, RECEIPTS


class PrivacyRepository:
    def __init__(self, session, business_id):
        if not isinstance(session, FinancialSession):
            raise TypeError("FinancialSession prestada requerida.")
        self.s, self.bid = session, positive_id(business_id)

    def principal(self, principal, *, closure_read=False):
        if not isinstance(principal, Principal):
            raise AccessDenied("Identidad autenticada de privacidad requerida.")
        user = self.s.execute("SELECT id,business_id,session_version,is_active FROM users WHERE id=? AND business_id=?",
                              (principal.user_id, self.bid)).fetchone()
        if not user or user["session_version"] != principal.session_version:
            raise AccessDenied("Sesión/tenant de privacidad no disponibles.")
        if not user["is_active"]:
            # Sólo control plane privado de lectura: nunca una sesión web suspendida.
            receipt = self.s.execute(f"SELECT created_by,session_version FROM {RECEIPTS} WHERE business_id=?", (self.bid,)).fetchone()
            if not closure_read or not receipt or receipt["created_by"] != principal.user_id or receipt["session_version"] + 1 != principal.session_version:
                raise AccessDenied("Cuenta suspendida.")
        return user

    def load(self, table, uid):
        if table not in TABLES:
            raise ValueError("Tabla E desconocida.")
        row = self.s.execute(f"SELECT * FROM {table} WHERE business_id=? AND evidence_uuid=?", (self.bid, uuid_text(uid))).fetchone()
        if row and (digest(json.loads(row["body_canonical"])) != row["content_hash"] or canonical(json.loads(row["body_canonical"])) != row["body_canonical"]):
            raise ConflictError("Evidencia E corrupta.")
        return row

    def body(self, table, uid):
        row = self.load(table, uid)
        if not row:
            raise AccessDenied("Referencia E no disponible para el tenant.")
        return json.loads(row["body_canonical"])

    def store(self, table, uid, principal, body, created_at, **extra):
        uid, hashed = uuid_text(uid), digest(body)
        existing = self.load(table, uid)
        if existing:
            if existing["content_hash"] != hashed or existing["created_by"] != principal.user_id or existing["session_version"] != principal.session_version:
                raise ConflictError("UUID E ya vinculada a otro contexto.")
            return json.loads(existing["body_canonical"])
        fields = ("business_id", "evidence_uuid", "contract_version", "created_by", "session_version", "created_at", "body_canonical", "content_hash", *extra)
        values = (self.bid, uid, 1, principal.user_id, principal.session_version, created_at, canonical(body), hashed, *extra.values())
        with execution_context(self.s, dict(kind="financial_privacy", table=table, business_id=str(self.bid), evidence_uuid=uid, content_hash=hashed, created_by=str(principal.user_id), session_version=str(principal.session_version), created_at=created_at)):
            self.s.execute(f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", values)
        return body


def installed(session):
    # Incluso la consulta de versión evita Cursor legacy/_normalise_row.
    row = session.execute("SELECT COALESCE(MAX(version),0) AS version FROM schema_migrations").fetchone()
    return row["version"] in (78, 79)


def assert_open(session, business_id):
    if not installed(session):
        return
    from .schema import AUTHORIZATIONS, RESTORED
    if session.execute(f"SELECT 1 FROM {AUTHORIZATIONS} WHERE business_id=? UNION SELECT 1 FROM {RESTORED} WHERE business_id=? AND scope='account_local_access' LIMIT 1", (business_id, business_id)).fetchone():
        raise StateError("Cuenta en cierre formal/restringida: nuevos efectos bloqueados.")
