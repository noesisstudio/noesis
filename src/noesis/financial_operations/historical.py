"""Invariantes de registro histórico, sin permiso de ejecución ni efectos."""

from dataclasses import dataclass

from .contracts import AuthorizationKind, EntryNamespace, OperationState, StateError, positive_id


@dataclass(frozen=True, slots=True)
class HistoricalAuthorization:
    recorded_by: int
    actor_user_id: None
    actor_session_version: None
    namespace: EntryNamespace
    kind: AuthorizationKind
    permission: str
    state: OperationState

    def __post_init__(self):
        positive_id(self.recorded_by)
        object.__setattr__(self, "namespace", EntryNamespace(self.namespace))
        object.__setattr__(self, "kind", AuthorizationKind(self.kind))
        object.__setattr__(self, "state", OperationState(self.state))
        if (self.actor_user_id is not None or self.actor_session_version is not None
                or self.namespace != EntryNamespace.HISTORICAL or self.kind != AuthorizationKind.HISTORICAL_UNKNOWN
                or self.permission != "historical.record"
                or self.state not in (OperationState.PREPARED, OperationState.REJECTED, OperationState.CANCELLED)):
            raise StateError("Registro histórico no ejecutable, sin actor original ni promoción.")


def ensure_historical_authorization(namespace, kind, channel, *, has_history=False):
    """Un receipt histórico previo conserva su naturaleza incluso en namespaces antiguos."""
    historical = EntryNamespace(namespace) == EntryNamespace.HISTORICAL or has_history
    if historical and (AuthorizationKind(kind) != AuthorizationKind.HISTORICAL_UNKNOWN
                       or EntryNamespace(channel) != EntryNamespace.HISTORICAL):
        raise StateError("Una operación histórica no se convierte en aprobación HUMAN/MANDATE.")
    if AuthorizationKind(kind) == AuthorizationKind.HISTORICAL_UNKNOWN and EntryNamespace(channel) != EntryNamespace.HISTORICAL:
        raise StateError("Procedencia desconocida requiere canal histórico.")
    if AuthorizationKind(kind) == AuthorizationKind.HISTORICAL_UNKNOWN and not historical:
        raise StateError("Nuevos registros históricos requieren namespace historical.")


def ensure_not_historical_execution(namespace, *, has_history=False):
    if EntryNamespace(namespace) == EntryNamespace.HISTORICAL or has_history:
        raise StateError("Una operación histórica nunca admite ejecución ni resultado COMMITTED.")
