"""Repositorio interno: conexión prestada, sin commit, pools ni permisos implícitos."""

from uuid import uuid4

from .contracts import AccessDenied, ConflictError, Operation, StateError, uuid_text


class OperationsRepository:
    def __init__(self, session, business_id):
        self.session = session
        self.business_id = business_id

    def _lock(self):
        return " FOR UPDATE" if self.session.dialect == "postgres" else ""

    def load(self, operation_uuid, user_id):
        row = self.session.execute(
            "SELECT * FROM financial_operations WHERE business_id=? AND operation_uuid=? "
            "AND created_by=?" + self._lock(),
            (self.business_id, uuid_text(operation_uuid), user_id),
        ).fetchone()
        if not row:
            raise AccessDenied("Operación no disponible.")
        return row

    def prepare(self, principal, identity, request, now):
        canonical = request.canonical()
        # El índice único arbitra también procesos/conexiones concurrentes.
        self.session.execute(
            "INSERT INTO financial_operations (business_id, operation_uuid, entry_namespace, entry_key, "
            "created_by, command_type, command_version, request_canonical, request_hash, expected_revision, "
            "state, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'prepared', ?, ?) "
            "ON CONFLICT(business_id, entry_namespace, entry_key) DO NOTHING",
            (self.business_id, str(uuid4()), identity.namespace.value, identity.key, principal.user_id,
             request.command_type.value, request.command_version, canonical, request.request_hash,
             request.expected_revision, now, now),
        )
        row = self.session.execute(
            "SELECT * FROM financial_operations WHERE business_id=? AND entry_namespace=? AND entry_key=?"
            + self._lock(), (self.business_id, identity.namespace.value, identity.key),
        ).fetchone()
        if row["created_by"] != principal.user_id:
            raise AccessDenied("Operación no disponible.")
        if row["request_hash"] != request.request_hash or row["request_canonical"] != canonical:
            raise ConflictError("Misma identidad con contenido diferente.")
        return Operation.from_row(row)

    def authorization(self, authorization_uuid):
        row = self.session.execute(
            "SELECT * FROM financial_authorizations WHERE business_id=? AND authorization_uuid=?"
            + self._lock(), (self.business_id, uuid_text(authorization_uuid)),
        ).fetchone()
        if not row:
            raise AccessDenied("Autorización no disponible.")
        return row

    def add_authorization(self, *, operation_uuid, kind, actor, recorded_by, session_version,
                          request, channel, permission, now, mandate_uuid=None, expires_at=None):
        authorization_uuid = str(uuid4())
        self.session.execute(
            "INSERT INTO financial_authorizations (business_id, authorization_uuid, operation_uuid, kind, "
            "actor_user_id, recorded_by, actor_session_version, validated_permission, approved_request_hash, "
            "approved_revision, channel, mandate_uuid, authorized_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (self.business_id, authorization_uuid, operation_uuid, kind.value, actor, recorded_by,
             session_version, permission, request.request_hash, request.expected_revision,
             channel.value, mandate_uuid, now, expires_at),
        )
        return authorization_uuid

    def transition(self, row, state, now, *, authorization_uuid=None, result=None, result_hash=None):
        authorization_uuid = authorization_uuid or row["authorization_uuid"]
        count = self.session.execute(
            "UPDATE financial_operations SET state=?, authorization_uuid=?, updated_at=?, "
            "result_version=?, result_canonical=?, result_hash=?, committed_at=? "
            "WHERE business_id=? AND operation_uuid=? AND state=?",
            (state.value, authorization_uuid, now, None if result is None else 1, result, result_hash,
             None if result is None else now, self.business_id, row["operation_uuid"], row["state"]),
        ).rowcount
        if count != 1:
            raise StateError("Transición concurrente o inválida.")

    def revoke_mandate(self, row, now):
        self.session.execute("UPDATE financial_authorizations SET revoked_at=? "
                             "WHERE business_id=? AND authorization_uuid=? AND revoked_at IS NULL",
                             (now, self.business_id, row["authorization_uuid"]))
