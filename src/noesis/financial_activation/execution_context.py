"""Contexto privado de ejecución, acotado a conexión y transacción exterior.

No es una autorización ni un token durable. PostgreSQL verifica un HMAC con una
clave privada del esquema y rechaza identidades SQL privilegiadas. SQLite usa
una función de conexión cuyo estado no puede escribirse mediante SQL.
"""

from contextlib import contextmanager
import hashlib
import hmac
import json
import sqlite3

from noesis import config
from noesis.financial_operations.contracts import StateError


def signing_key():
    """Separación criptográfica de dominio; no publicar ni registrar esta clave."""
    return hmac.digest(config.SECRET_KEY.encode(), b"noesis.execution-context.v1", "sha256")


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def install_sqlite(connection):
    """Infraestructura de conexión; no toca tablas ni habilita un negocio."""
    if connection.dialect != "sqlite":
        return
    connection._financial_context = None

    def current():
        context = connection._financial_context
        return _canonical(context) if context and connection.raw.in_transaction else "{}"

    connection.raw.create_function("noesis_execution_context", 0, current)
    connection.raw.create_function("noesis_sha256", 1, lambda value: hashlib.sha256(value.encode()).hexdigest())


@contextmanager
def execution_context(session, value):
    """Solo el servicio confiable emite contexto después de validar autoridad.

El valor incluye business, operación/request, generation y capability exactos.
No commits dentro del executor; el contexto desaparece antes del commit exterior.
"""
    conn = session.borrowed_connection
    if session.dialect == "sqlite":
        if not conn.raw.in_transaction or not hasattr(conn, "_financial_context"):
            raise StateError("Contexto de conexión/transacción no instalado.")
        if conn._financial_context is not None:
            raise StateError("No anidar contextos de ejecución financiera.")
        conn._financial_context = dict(value)

        def authorizer(action, arg1, arg2, database, source):
            # Impide confirmar/revertir la TX y reutilizar el contexto antes de salir.
            if action == sqlite3.SQLITE_TRANSACTION:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        conn.raw.set_authorizer(authorizer)
        try:
            yield
        finally:
            conn._financial_context = None
            conn.raw.set_authorizer(None)
    else:
        identity = session.execute(
            "SELECT pg_backend_pid() AS backend, pg_current_xact_id()::text AS tx"
        ).fetchone()
        body = _canonical(dict(value, **identity))
        signature = hmac.new(signing_key(), body.encode(), hashlib.sha256).hexdigest()
        previous = session.execute(
            "SELECT current_setting('noesis.execution_context',true) AS body, "
            "current_setting('noesis.execution_signature',true) AS signature"
        ).fetchone()
        if previous["body"]:
            raise StateError("No anidar contextos de ejecución financiera.")
        session.execute("SELECT set_config('noesis.execution_context',?,true)", (body,))
        session.execute("SELECT set_config('noesis.execution_signature',?,true)", (signature,))
        try:
            yield
        finally:
            # Un error SQL aborta PostgreSQL: el rollback exterior elimina el GUC.
            if conn.raw.info.transaction_status.name != "INERROR":
                session.execute("SELECT set_config('noesis.execution_context','',true)")
                session.execute("SELECT set_config('noesis.execution_signature','',true)")

@contextmanager
def event_context(session, event):
    """Estrecha el contexto de efecto al sobre/relaciones exactos de un EE.

    Links se reservan antes del EE por el guard existente de schema63. Esta
    cápsula conserva ese orden sin dar permiso genérico a event_uuid ajenos.
    """
    proof = session.execute('SELECT noesis_execution_context() AS proof').fetchone()['proof']
    if isinstance(proof, str):
        proof = json.loads(proof)
    if proof.get('kind') != 'effect':
        yield
        return
    from noesis.economic_events.contracts import EconomicEvent
    if not isinstance(event, EconomicEvent) or event.business_id != proof['business_id'] or proof.get('event_uuid'):
        raise StateError('Sobre económico tipado de la operación actual requerido.')
    narrowed = dict(proof, event_uuid=str(event.event_id), event_hash=event.content_hash,
                    event_relations=[dict(kind=r.kind.value, target_event_uuid=str(r.target_event_id)) for r in event.relations])
    conn = session.borrowed_connection
    if session.dialect == 'sqlite':
        previous = conn._financial_context
        conn._financial_context = narrowed
        try:
            yield
        finally:
            conn._financial_context = previous
    else:
        body = _canonical(narrowed)
        signature = hmac.new(signing_key(), body.encode(), hashlib.sha256).hexdigest()
        previous = session.execute("SELECT current_setting('noesis.execution_context',true) AS body,current_setting('noesis.execution_signature',true) AS signature").fetchone()
        session.execute("SELECT set_config('noesis.execution_context',?,true)", (body,))
        session.execute("SELECT set_config('noesis.execution_signature',?,true)", (signature,))
        try:
            yield
        finally:
            if conn.raw.info.transaction_status.name != 'INERROR':
                session.execute("SELECT set_config('noesis.execution_context',?,true)", (previous['body'],))
                session.execute("SELECT set_config('noesis.execution_signature',?,true)", (previous['signature'],))
