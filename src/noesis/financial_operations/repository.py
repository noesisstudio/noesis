"""Repositorio interno: conexión prestada, sin commit, pools ni permisos implícitos."""

from uuid import uuid4
from contextlib import nullcontext

from .contracts import AccessDenied, ConflictError, Operation, StateError, uuid_text
from .historical import ensure_historical_authorization, ensure_not_historical_execution


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

    def prepare(self, principal, identity, request, now, *, activation=None):
        # Capturadores especializados también prestan este repositorio. La
        # misma frontera impide crear filas sin generation desde un override.
        from noesis.financial_activation.runtime import binding
        actual = binding(self.session, self.business_id, request)
        if activation is not None and activation != actual:
            raise StateError("Binding distinto del control/grant vigente.")
        activation = actual
        canonical = request.canonical()
        operation_uuid = str(uuid4())
        from noesis.financial_activation.execution_context import execution_context
        context = nullcontext() if activation is None else execution_context(self.session, dict(activation, kind='prepare', operation_uuid=operation_uuid))
        binding_columns = '' if activation is None else ', activation_generation, activation_capability'
        binding_values = '' if activation is None else ', ?, ?'
        binding_params = () if activation is None else (activation['generation'], activation['capability'])
        # El índice único arbitra también procesos/conexiones concurrentes.
        with context:
            self.session.execute(
            "INSERT INTO financial_operations (business_id, operation_uuid, entry_namespace, entry_key, "
            "created_by, command_type, command_version, request_canonical, request_hash, expected_revision, "
            "state, created_at, updated_at" + binding_columns + ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'prepared', ?, ?" + binding_values + ") "
            "ON CONFLICT(business_id, entry_namespace, entry_key) DO NOTHING",
            (self.business_id, operation_uuid, identity.namespace.value, identity.key, principal.user_id,
             request.command_type.value, request.command_version, canonical, request.request_hash,
             request.expected_revision, now, now, *binding_params),
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
                          request, channel, permission, now, mandate_uuid=None, expires_at=None, activation=None):
        if operation_uuid is not None:
            row = self.load(operation_uuid, recorded_by)
            ensure_historical_authorization(row["entry_namespace"], kind, channel,
                                            has_history=self.has_historical_receipt(operation_uuid))
        authorization_uuid = str(uuid4())
        binding_columns = '' if activation is None else ', activation_generation, activation_capability'
        binding_values = '' if activation is None else ', ?, ?'
        binding_params = () if activation is None else (activation['generation'], activation['capability'])
        self.session.execute(
            "INSERT INTO financial_authorizations (business_id, authorization_uuid, operation_uuid, kind, "
            "actor_user_id, recorded_by, actor_session_version, validated_permission, approved_request_hash, "
            "approved_revision, channel, mandate_uuid, authorized_at, expires_at" + binding_columns + ") "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?" + binding_values + ")",
            (self.business_id, authorization_uuid, operation_uuid, kind.value, actor, recorded_by,
             session_version, permission, request.request_hash, request.expected_revision,
             channel.value, mandate_uuid, now, expires_at, *binding_params),
        )
        return authorization_uuid

    def transition(self, row, state, now, *, authorization_uuid=None, result=None, result_hash=None):
        if state.value in ("approved", "committed"):
            ensure_not_historical_execution(row["entry_namespace"],
                                           has_history=self.has_historical_receipt(row["operation_uuid"]))
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

    def has_historical_receipt(self, operation_uuid):
        return self.session.execute(
            "SELECT 1 FROM financial_authorizations WHERE business_id=? AND operation_uuid=? "
            "AND kind='historical_unknown' LIMIT 1", (self.business_id, uuid_text(operation_uuid)),
        ).fetchone() is not None

    def revoke_mandate(self, row, now):
        self.session.execute("UPDATE financial_authorizations SET revoked_at=? "
                             "WHERE business_id=? AND authorization_uuid=? AND revoked_at IS NULL",
                             (now, self.business_id, row["authorization_uuid"]))
