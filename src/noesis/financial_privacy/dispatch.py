"""Disponibilidad local previa al claim; no retry/envío/revoke remoto."""

from noesis.core.persistence import FinancialSession
from .repository import installed


def available_predicate(connection, tenant_expression):
    if tenant_expression not in ("email_outbox.business_id", "whatsapp_outbox.business_id"):
        raise ValueError("Worker E desconocido.")
    s = connection if isinstance(connection, FinancialSession) else FinancialSession(connection)
    if not installed(s):
        return "TRUE"
    from noesis.financial_providers.dispatch import legacy_predicate
    return f"NOT EXISTS(SELECT 1 FROM financial_closure_authorizations ca WHERE ca.business_id={tenant_expression}) AND NOT EXISTS(SELECT 1 FROM financial_restore_suppressions rs WHERE rs.business_id={tenant_expression} AND rs.scope='account_local_access') AND " + legacy_predicate(s, tenant_expression)
