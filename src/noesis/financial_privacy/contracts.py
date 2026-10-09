"""Contratos cerrados E v1, sin conexiones ni efectos financieros."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
import math
import re
from uuid import UUID

from noesis.financial_operations.contracts import positive_id, uuid_text, StateError

VERSION = 1
CANONICAL_VERSION = "financial_privacy_v1"
SCHEMAS = (78, 79)


class Purpose(StrEnum):
    PORTABILITY = "portability"
    AUDIT = "audit"
    GESTORIA = "gestoria"
    ACCOUNT_CLOSURE = "account_closure"


class Permission(StrEnum):
    EXPORT = "privacy.financial.export"
    PLAN = "privacy.financial.plan"
    AUTHORIZE = "privacy.financial.close"
    POLICY = "privacy.retention.approve"


class Category(StrEnum):
    FISCAL = "fiscal_legal_record"
    PROVENANCE = "financial_provenance"
    ACTIVATION = "activation_authority"
    TRANSPORT = "fiscal_transport"
    DOCUMENT = "supporting_document"
    PERSONAL = "operational_personal"
    CREDENTIAL = "credentials_secrets"
    COMMUNICATION = "communications_support"
    PRIVACY = "privacy_request_evidence"
    QA = "qa_restored_copy"


class PolicyStatus(StrEnum):
    PROVISIONAL = "provisional"
    APPROVED = "approved_for_operation"


class RetentionMode(StrEnum):
    HOLD = "hold_pending_review"
    RETAIN = "retain_proof"
    MINIMIZE = "minimize_prescindible"
    INVALIDATE = "invalidate_local_credentials"


def canonical(value):
    """Sólo valores JSON exactos; rechazar float aun dentro de una colección."""
    def check(v):
        if isinstance(v, float):
            raise TypeError("float no pertenece al contrato financiero.")
        if isinstance(v, dict):
            if any(not isinstance(k, str) for k in v):
                raise TypeError("Claves JSON de texto requeridas.")
            for item in v.values():
                check(item)
        elif isinstance(v, (list, tuple)):
            for item in v:
                check(item)
    check(value)
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def evidence_value(value):
    """Legacy binario conserva bits/procedencia; jamás se convierte a Money."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Evidencia binaria no finita.")
        return {"legacy_binary64": value.hex(), "provenance": "database_binary64", "exact_money": False}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Decimal no finito.")
        return format(value, "f")
    if isinstance(value, datetime):
        # Sin zona en origen continúa siendo naive: no inventar UTC.
        return value.isoformat(timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return {"sha256": hashlib.sha256(value).hexdigest(), "byte_count": len(value), "bytes_included": False}
    if isinstance(value, dict):
        return {k: evidence_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [evidence_value(v) for v in value]
    return value


def export_identity(export_uuid, business_id, purpose, client_id=None):
    return dict(export_uuid=uuid_text(export_uuid), business_id=positive_id(business_id),
                purpose=Purpose(purpose).value, client_id=positive_id(client_id) if client_id is not None else None)


def validate_policy(value):
    """No plazos inventados; referencias aprobadas son identificadores, no PII libre."""
    if not isinstance(value, dict) or set(value) != {"version", "policy_uuid", "status", "reference", "rules"} or type(value["version"]) is not int or value["version"] != VERSION:
        raise ValueError("Contrato de política desconocido.")
    uuid_text(value["policy_uuid"])
    status = PolicyStatus(value["status"])
    ref = value["reference"]
    if not isinstance(ref, str) or not 1 <= len(ref) <= 128 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-:/" for c in ref):
        raise ValueError("Referencia de decisión requerida, sin texto personal.")
    if not isinstance(value["rules"], list) or len(value["rules"]) != len(Category):
        raise ValueError("Todas las categorías deben tener regla explícita.")
    seen = set()
    for rule in value["rules"]:
        if not isinstance(rule, dict) or set(rule) != {"category", "basis_reference", "mode", "purge_after", "review_status"}:
            raise ValueError("Regla cerrada requerida.")
        category = Category(rule["category"])
        mode = RetentionMode(rule["mode"])
        if category in seen or rule["review_status"] != status.value:
            raise ValueError("Regla duplicada o revisión incoherente.")
        seen.add(category)
        # v1 no implementa purga temporal: incluso aprobación necesita un contrato posterior.
        if rule["purge_after"] is not None or rule["basis_reference"] != ref:
            raise ValueError("v1 bloquea purga temporal; referencia exacta requerida.")
        if status == PolicyStatus.PROVISIONAL and mode != RetentionMode.HOLD:
            raise ValueError("Política provisional no autoriza minimización.")
        if category == Category.CREDENTIAL and mode not in (RetentionMode.HOLD, RetentionMode.INVALIDATE):
            raise ValueError("Credenciales: conservar bajo revisión o invalidar acceso local.")
        if category in (Category.PERSONAL, Category.COMMUNICATION) and mode not in (RetentionMode.HOLD, RetentionMode.RETAIN, RetentionMode.MINIMIZE):
            raise ValueError("Categoría personal sin acción de credenciales.")
        if category in (Category.FISCAL, Category.PROVENANCE, Category.ACTIVATION,
                        Category.TRANSPORT, Category.DOCUMENT, Category.PRIVACY, Category.QA) and mode not in (RetentionMode.HOLD, RetentionMode.RETAIN):
            raise ValueError("La evidencia no admite minimización en v1.")
    canonical(value)
    return value


def tombstone_actions(value):
    """Selector/category cerrados v1: derivar replay sin campos adicionales ni PII."""
    try:
        account = value.get("scope") == "account_local_access"
        identifier = "closure_uuid" if account else "suppression_uuid"
        if set(value) != {"version", "business_id", identifier, "scope", "category", "policy_uuid", "selector_version", "selector", "evidence_hash", "applied_at"}:
            raise ValueError("Campos de tombstone no cerrados.")
        if type(value["version"]) is not int or value["version"] != 1 or type(value["selector_version"]) is not int or value["selector_version"] != 1:
            raise ValueError("Versión de tombstone desconocida.")
        bid = positive_id(value["business_id"])
        uuid_text(value[identifier])
        uuid_text(value["policy_uuid"])
        selector = {"business_id": bid}
        if not account:
            if value["scope"] != "client_contact":
                raise ValueError("Scope desconocido.")
            selector["client_id"] = positive_id(value["selector"]["client_id"])
        if value["selector"] != selector or not re.fullmatch(r"[a-f0-9]{64}", value["evidence_hash"]) or datetime.fromisoformat(value["applied_at"]).tzinfo is None:
            raise ValueError("Selector/hash/fecha de tombstone inválidos.")
        categories = value["category"]
        # Nombres de categorías/acciones del catálogo; no valores de credenciales.
        mapping = {"credentials_secrets": "invalidate_local_credentials", "operational_personal": "minimize_operational_contacts", "communications_support": "minimize_unreferenced_communications"}  # pragma: allowlist secret
        if not isinstance(categories, list) or not categories or any(not isinstance(c, str) for c in categories) or categories != sorted(set(categories)):
            raise ValueError("Categorías cerradas y ordenadas requeridas.")
        if account:
            if "credentials_secrets" not in categories or set(categories) - set(mapping):
                raise ValueError("Categoría de cierre no autorizada.")
            return [mapping[c] for c in categories]
        if categories != ["operational_personal"]:
            raise ValueError("Categoría de cliente no autorizada.")
        return ["minimize_client_contact"]
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise StateError("Tombstone v1 inválida; no servir restauración.") from exc
