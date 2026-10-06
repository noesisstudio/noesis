"""Fence transaccional tenant-scoped; conexión prestada, sin autoridad económica."""

from contextlib import contextmanager
import logging

from noesis.core.locks import lock_business
from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import StateError, positive_id

log = logging.getLogger(__name__)


class HistoricalFenceActive(StateError):
    """Rechazo cerrado y reconocible; nunca es una invitación a fallback."""


class HistoricalWriterBusy(StateError):
    """SQL directo perdió el gate: reintentar la transacción completa."""


def installed(connection):
    if isinstance(connection, FinancialSession):
        connection = connection.borrowed_connection
    if connection.dialect == 'postgres':
        return connection.execute_exact("SELECT to_regclass('financial_history_control') AS name").fetchone()['name'] is not None
    return bool(connection.execute_exact("SELECT 1 FROM sqlite_master WHERE type='table' AND name='financial_history_control'").fetchone())


def assert_writable(connection, business_id):
    """En la TX del writer: gate → control, antes de operación/fuente/contador."""
    business_id = positive_id(business_id)
    if not installed(connection):
        return  # Compatibilidad de código con esquema anterior; no existe epoch.
    raw = connection.borrowed_connection if isinstance(connection, FinancialSession) else connection
    if raw.dialect == 'sqlite' and not raw.raw.in_transaction:
        raw.execute('BEGIN IMMEDIATE')
    lock_business(connection, business_id)
    row = raw.execute_exact('SELECT fence_enabled FROM financial_history_control WHERE business_id=?', (business_id,)).fetchone()
    if row and row['fence_enabled']:
        log.warning('historical blocked writer business=%s', business_id)
        raise HistoricalFenceActive('El negocio tiene un corte histórico protegido; requiere intervención del operador.')


def translate(error):
    """Solo traduce nuestros códigos; errores legacy mantienen su tipo y contenido."""
    message = str(error)
    if 'NOESIS_HISTORY_FENCE_ACTIVE' in message:
        log.warning('historical blocked SQL writer')
        return HistoricalFenceActive('El negocio tiene un corte histórico protegido.')
    if 'NOESIS_HISTORY_WRITER_BUSY' in message:
        return HistoricalWriterBusy('Gate financiero ocupado o aislamiento SQL incompatible; reintentar la TX.')
    return None


@contextmanager
def external_guard(business_id):
    """Ventana externa auditada: filesystem/dispatch, gate hasta acabar la acción.

    Reutiliza db.get_conn. No persiste efectos financieros ni mantiene el scan.
    Un epoch espera una acción anterior; una posterior falla antes de IO.
    """
    from noesis import db
    with db.get_conn() as conn:
        assert_writable(conn, business_id)
        from noesis.financial_activation.runtime import control, ActivationUnavailable
        row = control(conn, business_id)
        if row and row['ever_enabled']:
            raise ActivationUnavailable('Dispatch externo post-handoff requiere la política F; D no concede acceso a providers.')
        yield


def available_predicate(connection, tenant_expression):
    """SQL cerrado para los workers auditados; nunca una tabla del cliente."""
    if tenant_expression not in ('verifactu_outbox.business_id', 'verifactu_cancellation_outbox.business_id', 'r.business_id'):
        raise ValueError('Scope de worker desconocido.')
    if not installed(connection):
        return 'TRUE'
    return f'NOT EXISTS(SELECT 1 FROM financial_history_control hc WHERE hc.business_id={tenant_expression} AND hc.fence_enabled=TRUE)'
