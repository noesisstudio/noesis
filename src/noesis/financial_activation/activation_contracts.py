"""Contratos cerrados del control plane D; ninguna autoridad financiera implícita."""

from dataclasses import dataclass
from enum import Enum

from noesis.financial_operations.contracts import strict_json, uuid_text
from .contracts import Capability, Profile, canonical, digest, instant, tenant


class ActivationPermission(str, Enum):
    MANAGE = "financial.activation.manage"


class ActivationState(str, Enum):
    OFF = "off"
    VALIDATING = "validating"
    READY = "ready"
    ENABLED = "enabled"
    PAUSED = "paused"


class ActivationAction(str, Enum):
    ENABLE = "enable"
    ABORT = "abort"
    PAUSE = "pause"
    RESUME = "resume"


class PauseReason(str, Enum):
    OPERATOR_REQUEST = "operator_request"
    INTEGRITY_INCIDENT = "integrity_incident"
    PROVIDER_UNCERTAIN = "provider_uncertain"


FIELDS = frozenset((
    "request_version", "business_id", "request_uuid", "action", "expected_state",
    "expected_control_revision", "activation_generation", "previous_generation",
    "evaluation_uuid", "evaluation_content_hash", "profile", "profile_hash",
    "capabilities", "capability_grant_hash", "history", "external_evidence_hash", "configuration_hash",
    "code_version", "schema_version", "actor_user_id", "actor_session_version",
    "permission", "created_at", "expires_at", "pause_reason", "recovery_proof",
))


@dataclass(frozen=True, init=False)
class ActivationRequest:
    """Snapshot derivado por servidor; no recibe parámetros libres del modelo."""

    _canonical_text: str

    def __init__(self, body):
        value = strict_json(canonical(body))
        if set(value) != FIELDS or type(value["request_version"]) is not int or value["request_version"] != 1:
            raise ValueError("Contrato de activation request/version desconocido.")
        tenant(value["business_id"])
        tenant(value["actor_user_id"])
        for field in ("expected_control_revision", "activation_generation", "previous_generation", "actor_session_version"):
            if type(value[field]) is not int or value[field] < 0:
                raise ValueError("Revisión/generación/sesión entera requerida.")
        if value["schema_version"] != 77 or type(value["schema_version"]) is not int:
            raise ValueError("Schema77 requerido.")
        for field in ("request_uuid", "evaluation_uuid"):
            if value[field] != uuid_text(value[field]):
                raise ValueError("UUID canónico requerido.")
        action = ActivationAction(value["action"])
        state = ActivationState(value["expected_state"])
        generation, previous = value['activation_generation'], value['previous_generation']
        valid = {
            ActivationAction.ENABLE: previous == 0 and generation == 1 and state in (ActivationState.OFF, ActivationState.VALIDATING, ActivationState.READY),
            ActivationAction.ABORT: previous == generation == 0 and state in (ActivationState.VALIDATING, ActivationState.READY),
            ActivationAction.PAUSE: previous == generation and generation > 0 and state == ActivationState.ENABLED,
            ActivationAction.RESUME: previous > 0 and generation == previous + 1 and state == ActivationState.PAUSED,
        }
        if not valid[action]:
            raise ValueError('Action/estado/generaciones incompatibles.')
        if value["permission"] != ActivationPermission.MANAGE.value:
            raise ValueError("Autoridad específica de activación requerida.")
        if not isinstance(value["profile"], dict) or set(value["profile"]) != {"capabilities", "profile_version"}:
            raise ValueError("Perfil cerrado requerido.")
        profile = Profile(tuple(value["profile"]["capabilities"]), value["profile"]["profile_version"])
        if profile.value() != value["profile"]:
            raise ValueError("Perfil canónico requerido.")
        if digest(value["profile"]) != value["profile_hash"]:
            raise ValueError("Perfil exacto incoherente.")
        if not isinstance(value["capabilities"], list) or value["capabilities"] != sorted(set(value["capabilities"])):
            raise ValueError("Capability closure exacta ordenada requerida.")
        for capability in value["capabilities"]:
            Capability(capability)
        closures = ([cap.value for cap in profile.closure(fiscal_cancel_required=required)[0]] for required in (False, True))
        if value['capabilities'] not in closures:
            raise ValueError('Closure completa del perfil requerida.')
        history_fields = {"epoch_uuid", "manifest_uuid", "batch_uuid", "reconciliation_uuid", "generation", "plan_hash", "result_hash", "rechecked_hash", "epoch_storage_hash", "cut_storage_hash", "manifest_storage_hash", "batch_storage_hash", "reconciliation_storage_hash", "t0", "fence_version", "source_scope_hash", "source_set_hash"}
        if not isinstance(value["history"], dict) or set(value["history"]) != history_fields:
            raise ValueError("Historia de corte/E cerrada requerida.")
        for field in ("epoch_uuid", "manifest_uuid", "batch_uuid", "reconciliation_uuid"):
            if value["history"][field] != uuid_text(value["history"][field]):
                raise ValueError("Identidad histórica canónica requerida.")
        if type(value["history"]["generation"]) is not int or value["history"]["generation"] <= 0:
            raise ValueError("Generación histórica positiva requerida.")
        for field in ("plan_hash", "result_hash", "rechecked_hash", "epoch_storage_hash", "cut_storage_hash", "manifest_storage_hash", "batch_storage_hash", "reconciliation_storage_hash", "source_scope_hash", "source_set_hash"):
            h = value["history"][field]
            if type(h) is not str or len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
                raise ValueError("Hash histórico requerido.")
        from datetime import datetime
        if type(value['history']['fence_version']) is not int or value['history']['fence_version'] != 1 or instant(datetime.fromisoformat(value['history']['t0'])) != value['history']['t0']:
            raise ValueError('Frontera histórica canónica requerida.')
        recovery = value["recovery_proof"]
        if (value["action"] == "resume") != (recovery is not None):
            raise ValueError("Prueba exclusiva de recuperación requerida.")
        if recovery is not None and (not isinstance(recovery, dict) or set(recovery) != {"version", "pause_receipt_uuid", "pause_receipt_hash", "generation_receipt_hash", "snapshot"} or type(recovery["version"]) is not int or recovery["version"] != 1):
            raise ValueError("Prueba cerrada de recuperación requerida.")
        if recovery is not None:
            if recovery['pause_receipt_uuid'] != uuid_text(recovery['pause_receipt_uuid']):
                raise ValueError('Recibo de pausa canónico requerido.')
            snapshot = recovery['snapshot']
            from noesis.financial_history.cut_scope import guarded_columns
            tables = set(guarded_columns()) | {'financial_operations', 'financial_authorizations'}
            if (not isinstance(snapshot, dict) or set(snapshot) != {'version', 'configuration_hash', 'financial_hash', 'table_hashes'}
                    or type(snapshot['version']) is not int or snapshot['version'] != 1
                    or not isinstance(snapshot['table_hashes'], dict) or set(snapshot['table_hashes']) != tables):
                raise ValueError('Snapshot cerrado de recuperación requerido.')
            hashes = [recovery['pause_receipt_hash'], recovery['generation_receipt_hash'], snapshot['configuration_hash'], snapshot['financial_hash'], *snapshot['table_hashes'].values()]
            if any(type(h) is not str or len(h) != 64 or any(c not in '0123456789abcdef' for c in h) for h in hashes):
                raise ValueError('Hashes de recuperación requeridos.')
        for field in ("evaluation_content_hash", "profile_hash", "capability_grant_hash", "external_evidence_hash", "configuration_hash"):
            if not isinstance(value[field], str) or len(value[field]) != 64 or any(c not in "0123456789abcdef" for c in value[field]):
                raise ValueError("Hash canónico requerido.")
        if type(value["code_version"]) is not str or not value["code_version"] or len(value["code_version"]) > 128:
            raise ValueError("Identidad de código requerida.")
        from datetime import datetime

        created = datetime.fromisoformat(value["created_at"])
        expires = datetime.fromisoformat(value["expires_at"])
        if instant(created) != value["created_at"] or instant(expires) != value["expires_at"] or expires <= created:
            raise ValueError("Instantes/caducidad exactos requeridos.")
        if (expires-created).total_seconds() > 300:
            raise ValueError("Caducidad máxima de cinco minutos.")
        if value["pause_reason"] is not None:
            PauseReason(value["pause_reason"])
        if (value["action"] == "pause") != (value["pause_reason"] is not None):
            raise ValueError("Motivo tipado exclusivo de pausa requerido.")
        object.__setattr__(self, "_canonical_text", canonical(value))

    @property
    def body(self):
        # Una copia profunda evita mutar el snapshot mediante listas/dicts anidados.
        return strict_json(self._canonical_text)

    @property
    def content_hash(self):
        return digest(self.body)

    def canonical(self):
        return self._canonical_text

    @classmethod
    def decode(cls, text):
        result = cls(strict_json(text))
        if result.canonical() != text:
            raise ValueError("Request no canónico.")
        return result
