"""Overlay de supresión de un registro vigente antes de servir un restore antiguo.

El bundle es privado, firmado y de vida corta; no es un export de negocio. Sin
registro vigente no se certifica un restore. No consulta producción por sí mismo.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

from noesis.financial_activation.execution_context import signing_key, execution_context
from noesis.financial_operations.contracts import StateError
from .contracts import canonical, digest, tombstone_actions
from .schema import TOMBSTONES, RESTORED, RECEIPTS, CLIENT_ERASURES
from .repository import PrivacyRepository, installed
from .closure import apply_local_actions, reapply_tombstones


def _key():
    return hmac.digest(signing_key(), b"privacy.restore.registry.v1", "sha256")


def restore_bundle(session):
    """Registro vigente antes de restaurar. Sólo identificadores/acciones/hashes."""
    now = datetime.now(timezone.utc)
    values = []
    if installed(session):
        for row in session.execute(f"SELECT * FROM {TOMBSTONES} ORDER BY business_id,evidence_uuid").fetchall():
            repo = PrivacyRepository(session, row["business_id"])
            value = repo.body(TOMBSTONES, str(row["evidence_uuid"]))
            account = value["scope"] == "account_local_access"
            receipt = repo.body(RECEIPTS if account else CLIENT_ERASURES, value["closure_uuid"] if account else value["suppression_uuid"])
            replay = tombstone_actions(value)
            if value["evidence_hash"] != digest(receipt) or (account and set(replay) != set(receipt["actions"])):
                raise StateError("Tombstone sin recibo verificable; no restaurar.")
            values.append(value)
        for row in session.execute(f"SELECT * FROM {RESTORED} ORDER BY business_id,evidence_uuid").fetchall():
            value = json.loads(row["body_canonical"])
            if digest(value) != row["content_hash"]:
                raise StateError("Registro de supresión restaurada corrupto.")
            tombstone_actions(value)
            values.append(value)
    values = {digest(v): v for v in values}
    body = dict(version=1, created_at=now.isoformat(), expires_at=(now + timedelta(minutes=15)).isoformat(),
                tombstones=[values[k] for k in sorted(values)], registry_hash=digest(sorted(values)))
    return dict(body=body, signature=hmac.new(_key(), canonical(body).encode(), hashlib.sha256).hexdigest())


def prepare_restored_database(session, bundle):
    """Requiere bundle actual autorizado. No se sirve una copia sin esta comprobación."""
    if not bundle or set(bundle) != {"body", "signature"}:
        raise StateError("Restore requiere registro vigente de supresiones; no servir.")
    body = bundle["body"]
    if not isinstance(body, dict) or set(body) != {"version", "created_at", "expires_at", "tombstones", "registry_hash"} or type(body["version"]) is not int or body["version"] != 1:
        raise StateError("Registro cerrado v1 requerido; no servir.")
    expected = hmac.new(_key(), canonical(body).encode(), hashlib.sha256).hexdigest()
    now = datetime.now(timezone.utc)
    created, expires = datetime.fromisoformat(body["created_at"]), datetime.fromisoformat(body["expires_at"])
    if (created.tzinfo is None or expires.tzinfo is None or created > now or expires - created != timedelta(minutes=15)
            or not hmac.compare_digest(expected, bundle["signature"]) or now >= expires
            or body["registry_hash"] != digest(sorted(digest(v) for v in body["tombstones"]))):
        raise StateError("Registro de supresión inválido/caducado; no servir.")
    if body["tombstones"] and not installed(session):
        raise StateError("Migrar copia aislada a schema78 antes de reapply; nunca servir antes.")
    for value in body["tombstones"]:
        account = value.get("scope") == "account_local_access"
        identifier = "closure_uuid" if account else "suppression_uuid"
        replay = tombstone_actions(value)
        bid, uid, hashed = value["business_id"], value[identifier], digest(value)
        if not session.execute("SELECT 1 FROM businesses WHERE id=?", (bid,)).fetchone():
            continue
        client_id = value["selector"].get("client_id")
        if client_id is not None and not session.execute("SELECT 1 FROM clients WHERE business_id=? AND id=?", (bid, client_id)).fetchone():
            continue
        old = session.execute(f"SELECT content_hash FROM {RESTORED} WHERE business_id=? AND evidence_uuid=?", (bid, uid)).fetchone()
        if old and old["content_hash"] != hashed:
            raise StateError("Overlay de restore conflictivo.")
        if not old:
            with execution_context(session, dict(kind="financial_privacy_restore", business_id=str(bid), evidence_uuid=uid, content_hash=hashed)):
                session.execute(f"INSERT INTO {RESTORED}(business_id,evidence_uuid,scope,client_id,body_canonical,content_hash) VALUES (?,?,?,?,?,?)", (bid, uid, value["scope"], client_id, canonical(value), hashed))
        if account:
            apply_local_actions(session, bid, replay)
        else:
            from .client import apply_client_actions
            apply_client_actions(session, bid, client_id)
    reapply_tombstones(session)
    return dict(version=1, registry_hash=body["registry_hash"], result="suppression_reapplied_before_service")
