"""Servicio transaccional interno; ejecutores de servidor de confianza.

Los ejecutores futuros recibirán la misma FinancialSession. No llamadas externas,
conexiones propias ni commits en un ejecutor: efecto y resultado se confirman juntos.
"""

from contextlib import contextmanager
from datetime import datetime, timezone

from noesis import db
from noesis.core.locks import lock_business
from noesis.core.persistence import FinancialSession
from .contracts import (
    AccessDenied, AuthorizationKind, EntryIdentity, EntryNamespace, FinancialRequest,
    Operation, OperationState, Principal, StateError, canonical_json, digest, positive_id, uuid_text,
)
from .repository import OperationsRepository


def _clock():
    return datetime.now(timezone.utc)


def _now():
    return _clock().isoformat(timespec="microseconds")


def _timestamp(value):
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Instante con zona requerido.")
    return result.astimezone(timezone.utc)


class FinancialOperations:
    """Infraestructura interna de dominio; sin acceso directo del modelo de IA."""

    def __init__(self, business_id):
        self.business_id = positive_id(business_id)

    def _permission(self, session, principal, *, write):
        if not isinstance(principal, Principal):
            raise AccessDenied("Contexto autenticado requerido.")
        lock = " FOR SHARE" if session.dialect == "postgres" else ""
        user = session.execute(
            "SELECT id, business_id, session_version, is_active FROM users WHERE id=? AND business_id=?"
            + lock, (principal.user_id, self.business_id),
        ).fetchone()
        if (not user or not user["is_active"]
                or user["session_version"] != principal.session_version):
            raise AccessDenied("Acceso financiero no autorizado.")
        business = session.execute(
            "SELECT subscription_status, trial_ends_at, is_demo FROM businesses WHERE id=?" + lock,
            (self.business_id,),
        ).fetchone()
        if not business:
            raise AccessDenied("Acceso financiero no autorizado.")
        if write:
            # La fecha nativa se convierte a texto, nunca los importes legacy a float.
            ends = business["trial_ends_at"]
            if isinstance(ends, datetime):
                business["trial_ends_at"] = ends.date().isoformat()
            elif hasattr(ends, "isoformat"):
                business["trial_ends_at"] = ends.isoformat()
            if not db.subscription_allows_access(business):
                raise AccessDenied("Negocio en modo consulta.")

    @contextmanager
    def _transaction(self, principal, *, write=True):
        with db.get_conn() as conn:
            session = FinancialSession(conn)
            if session.dialect == "sqlite":
                session.execute("BEGIN IMMEDIATE")
            self._permission(session, principal, write=write)
            # También lecturas con FOR UPDATE: nunca tomar operación antes del gate.
            lock_business(session, self.business_id)
            yield session, OperationsRepository(session, self.business_id)

    def prepare(self, principal, identity, request):
        if not isinstance(identity, EntryIdentity) or not isinstance(request, FinancialRequest):
            raise TypeError("Identidad de servidor y request tipado requeridos.")
        with self._transaction(principal) as (_, repo):
            return repo.prepare(principal, identity, request, _now())

    def recover(self, principal, operation_uuid):
        with self._transaction(principal, write=False) as (_, repo):
            return Operation.from_row(repo.load(operation_uuid, principal.user_id))

    @staticmethod
    def _revision(session, request, revision_reader):
        if request.expected_revision is not None:
            if revision_reader is None:
                raise StateError("Falta lector de revisión en la misma transacción.")
            actual = revision_reader(session, request)
            if type(actual) is not int or actual != request.expected_revision:
                raise StateError("La revisión cambió; preparar otra operación.")

    def grant_mandate(self, principal, request, *, channel, expires_at, revision_reader=None):
        """Mandato humano previo, de alcance exacto por hash y con caducidad obligatoria."""
        channel = EntryNamespace(channel)
        if not isinstance(request, FinancialRequest):
            raise TypeError("Request tipado requerido.")
        expires = _timestamp(expires_at)
        if expires <= _clock():
            raise StateError("El mandato debe caducar en el futuro.")
        with self._transaction(principal) as (session, repo):
            self._revision(session, request, revision_reader)
            return repo.add_authorization(operation_uuid=None, kind=AuthorizationKind.MANDATE,
                actor=principal.user_id, recorded_by=principal.user_id,
                session_version=principal.session_version, request=request, channel=channel,
                permission="financial.mandate", now=_now(), expires_at=expires.isoformat())

    def _mandate(self, session, repo, mandate_uuid, principal, request):
        row = repo.authorization(mandate_uuid)
        if (row["kind"] != AuthorizationKind.MANDATE.value or row["operation_uuid"] is not None
                or row["actor_user_id"] != principal.user_id or row["revoked_at"] is not None
                or _timestamp(row["expires_at"]) <= _clock()
                or row["actor_session_version"] != principal.session_version
                or row["approved_request_hash"] != request.request_hash
                or row["approved_revision"] != request.expected_revision):
            raise AccessDenied("Mandato no válido para esta operación.")
        self._permission(session, Principal(row["actor_user_id"], row["actor_session_version"]), write=True)
        return row

    def authorize(self, principal, operation_uuid, *, channel, approved_hash, approved_revision,
                  kind=AuthorizationKind.HUMAN, mandate_uuid=None, revision_reader=None, request_validator=None,
                  approval_recorder=None):
        """La revisión temporal se puede consumir solo DESPUÉS de confirmar este recibo."""
        kind, channel = AuthorizationKind(kind), EntryNamespace(channel)
        with self._transaction(principal) as (session, repo):
            guard = getattr(self, "_channel_guard", None)
            if guard is not None:
                guard(session, None, "lock")
            row = repo.load(operation_uuid, principal.user_id)
            operation = Operation.from_row(row)
            request = operation.request
            guard = getattr(self, "_channel_guard", None)
            if guard is not None:
                guard(session, operation, "authorize")
            if approved_hash != request.request_hash or approved_revision != request.expected_revision:
                raise StateError("Contenido/revisión aprobados no coinciden.")
            if approved_revision is not None and type(approved_revision) is not int:
                raise StateError("Revisión aprobada inválida.")
            if row["state"] != OperationState.PREPARED.value:
                if row["state"] in (OperationState.APPROVED.value, OperationState.COMMITTED.value):
                    if approval_recorder is not None:
                        approval_recorder(session, operation)
                    return operation
                raise StateError("Operación terminal no autorizable.")
            if kind == AuthorizationKind.HISTORICAL_UNKNOWN and row["authorization_uuid"] is not None:
                existing = repo.authorization(row["authorization_uuid"])
                if existing["kind"] == kind.value:
                    return operation
            if request_validator is not None:
                request_validator(session, request)
            self._revision(session, request, revision_reader)
            if kind == AuthorizationKind.MANDATE:
                if mandate_uuid is None:
                    raise AccessDenied("Mandato durable requerido.")
                mandate_uuid = uuid_text(mandate_uuid)
                self._mandate(session, repo, mandate_uuid, principal, request)
            elif mandate_uuid is not None:
                raise StateError("Mandato incompatible con la clase de autorización.")
            historical = kind == AuthorizationKind.HISTORICAL_UNKNOWN
            if historical and channel != EntryNamespace.HISTORICAL:
                raise StateError("Procedencia desconocida requiere canal histórico.")
            authorization_uuid = repo.add_authorization(
                operation_uuid=row["operation_uuid"], kind=kind,
                actor=None if historical else principal.user_id, recorded_by=principal.user_id,
                session_version=None if historical else principal.session_version, request=request,
                channel=channel, permission=("historical.record" if historical else
                    "financial.mandate" if kind == AuthorizationKind.MANDATE else "financial.authorize"),
                now=_now(), mandate_uuid=mandate_uuid)
            repo.transition(row, OperationState.PREPARED if historical else OperationState.APPROVED,
                            _now(), authorization_uuid=authorization_uuid)
            operation = Operation.from_row(repo.load(operation_uuid, principal.user_id))
            if approval_recorder is not None:
                approval_recorder(session, operation)
            return operation

    def revoke_mandate(self, principal, mandate_uuid):
        with self._transaction(principal) as (_, repo):
            row = repo.authorization(mandate_uuid)
            if row["operation_uuid"] is not None or row["actor_user_id"] != principal.user_id:
                raise AccessDenied("Mandato no disponible.")
            if row["revoked_at"] is None:
                repo.revoke_mandate(row, _now())

    def execute(self, principal, operation_uuid, executor, *, revision_reader=None, request_validator=None):
        """Claim por lock; efecto+resultado comparten commit exterior, sin estado executing."""
        with self._transaction(principal) as (session, repo):
            guard = getattr(self, "_channel_guard", None)
            if guard is not None:
                guard(session, None, "lock")
            row = repo.load(operation_uuid, principal.user_id)
            operation = Operation.from_row(row)
            guard = getattr(self, "_channel_guard", None)
            if guard is not None:
                guard(session, operation, "execute")
            if request_validator is not None:
                request_validator(session, operation.request)
            if operation.state == OperationState.COMMITTED:
                return operation  # Reintento tras perder la respuesta: no llamar al ejecutor.
            if operation.state != OperationState.APPROVED:
                raise StateError("Operación sin aprobación ejecutable.")
            authorization = repo.authorization(operation.authorization_uuid)
            if (str(authorization["operation_uuid"]) != operation.operation_uuid
                    or authorization["approved_request_hash"] != operation.request.request_hash
                    or authorization["actor_user_id"] != principal.user_id
                    or authorization["actor_session_version"] != principal.session_version
                    or authorization["kind"] == AuthorizationKind.HISTORICAL_UNKNOWN.value):
                raise AccessDenied("Autorización no válida.")
            if authorization["mandate_uuid"] is not None:
                self._mandate(session, repo, authorization["mandate_uuid"], principal, operation.request)
            self._revision(session, operation.request, revision_reader)
            result = executor(session, operation.request)
            if not isinstance(result, dict):
                raise TypeError("Resultado versionado requiere mapping JSON.")
            canonical = canonical_json(result)
            repo.transition(row, OperationState.COMMITTED, _now(), result=canonical, result_hash=digest(canonical))
            return Operation.from_row(repo.load(operation_uuid, principal.user_id))

    def finish_without_effect(self, principal, operation_uuid, state):
        state = OperationState(state)
        if state not in (OperationState.REJECTED, OperationState.CANCELLED):
            raise StateError("Solo rechazo/cancelación sin efecto.")
        with self._transaction(principal) as (_, repo):
            row = repo.load(operation_uuid, principal.user_id)
            if row["state"] == state.value:
                return Operation.from_row(row)
            if row["state"] not in (OperationState.PREPARED.value, OperationState.APPROVED.value):
                raise StateError("Operación terminal inmutable.")
            repo.transition(row, state, _now())
            return Operation.from_row(repo.load(operation_uuid, principal.user_id))
