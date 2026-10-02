"""Locks transaccionales compartidos; nunca abren ni terminan transacciones."""

import hashlib


def lock_key(namespace: str, *parts) -> int:
    raw = "\x00".join((namespace, *(str(p) for p in parts))).encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=True)


def lock_business(connection, business_id: int) -> None:
    if connection.dialect == "postgres":
        connection.execute(
            "SELECT pg_advisory_xact_lock(?)", (lock_key("financial-writer", business_id),)
        )


def lock_fiscal_chain(connection, business_id: int, issuer_nif: str) -> None:
    if connection.dialect == "postgres":
        connection.execute(
            "SELECT pg_advisory_xact_lock(?)", (lock_key("fiscal-chain", business_id, issuer_nif),)
        )
