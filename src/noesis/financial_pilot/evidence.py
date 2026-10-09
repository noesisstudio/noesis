"""Frontera de confianza de colectores futuros. Ningún colector/red configurado.

TrustStore es dependencia privada de composición, jamás input de una API/chat.
Una firma autentica el origen: el verifier aún contrasta su algoritmo y la BD.
No se emiten approvals, checks externos ni credenciales desde este módulo.
"""

from dataclasses import dataclass, field
import hashlib
import hmac
from types import MappingProxyType

from noesis.financial_activation.contracts import canonical, digest
from .verification_contracts import (Verifier, CATALOG, Cohort, Failure, VerificationError,
                                     closed, timestamp, actor, identifier)


FIELDS = ('version', 'verifier', 'evidence_type', 'cohort', 'business_id', 'profile_hash',
          'context_hash', 'receipt_uuid', 'issued_at', 'expires_at', 'authority', 'actor', 'metadata')


@dataclass(frozen=True, slots=True)
class SourceAuthority:
    verifier: Verifier
    cohort: Cohort
    key: bytes = field(repr=False)

    def __post_init__(self):
        object.__setattr__(self, 'verifier', Verifier(self.verifier))
        object.__setattr__(self, 'cohort', Cohort(self.cohort))
        if type(self.key) is not bytes or len(self.key) < 32:
            raise ValueError('Clave privada de origen independiente requerida.')


class TrustStore:
    """Sin entradas por defecto: toda referencia externa queda bloqueada.

    Claves por verifier/cohorte; no fallback a SECRET_KEY, key de DB o caller JSON.
    Sólo bootstrap confiable puede construir este objeto; no existe endpoint.
    """
    def __init__(self, authorities=()):
        values = {(a.verifier, a.cohort):a.key for a in authorities if type(a) is SourceAuthority}
        if len(values) != len(authorities):
            raise ValueError('Autoridades cerradas sin duplicados requeridas.')
        self._keys = MappingProxyType(values)

    def authenticate(self, envelope, signature, verifier, context_hash, context, now):
        closed(envelope, FIELDS)
        v, spec = Verifier(verifier), CATALOG[Verifier(verifier)]
        key = self._keys.get((v, context.cohort))
        if key is None or type(signature) is not str:
            raise VerificationError(Failure.AUTHORITY)
        expected = hmac.new(key, canonical(envelope).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise VerificationError(Failure.AUTHORITY)
        if (type(envelope['version']) is not int or envelope['version'] != 1
                or envelope['verifier'] != v or envelope['evidence_type'] != spec.evidence_type
                or envelope['authority'] != spec.authority):
            raise VerificationError(Failure.AUTHORITY)
        if envelope['cohort'] != context.cohort:
            raise VerificationError(Failure.SYNTHETIC)
        if (type(envelope['business_id']) is not int or envelope['business_id'] != context.business_id
                or envelope['profile_hash'] != context.profile.content_hash):
            raise VerificationError(Failure.SCOPE)
        if envelope['context_hash'] != context_hash:
            raise VerificationError(Failure.CONTEXT)
        identifier(envelope['receipt_uuid'])
        actor(envelope['actor'])
        issued, expires = timestamp(envelope['issued_at']), timestamp(envelope['expires_at'])
        if not issued <= now < expires or (expires-issued).total_seconds() > spec.ttl_seconds:
            raise VerificationError(Failure.STALE)
        return envelope['metadata']


@dataclass(frozen=True, slots=True, init=False)
class VerifiedEvidence:
    """Objeto opaco. JSON/constructor no crean una prueba aceptable por PilotGate."""
    canonical_content: str
    _seal: bytes = field(repr=False)

    @property
    def body(self):
        import json
        return json.loads(self.canonical_content)

    @property
    def content_hash(self):
        return digest(self.body)


def _sealed(value, key):
    obj = object.__new__(VerifiedEvidence)
    text = canonical(value)
    object.__setattr__(obj, 'canonical_content', text)
    object.__setattr__(obj, '_seal', hmac.digest(key, text.encode(), 'sha256'))
    return obj


def _check_seal(obj, key):
    if (type(obj) is not VerifiedEvidence or not hasattr(obj, '_seal')
            or not hmac.compare_digest(obj._seal, hmac.digest(key, obj.canonical_content.encode(), 'sha256'))):
        raise VerificationError(Failure.INVALID)
