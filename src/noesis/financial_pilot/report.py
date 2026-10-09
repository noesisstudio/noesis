"""Cálculo puro G-PREP. Sin readers de datos reales ni ruta de activación."""

from types import MappingProxyType

from noesis.financial_activation.contracts import Capability as C, Profile, canonical, digest, instant
from noesis.financial_activation.capabilities import specification
from .contracts import (EvidenceReference, Owner, PilotReadinessReport, PilotResult,
                        PreparationContext, Reason, expiry)


# Remediaciones cerradas, no texto suministrado por IA/operador como autoridad.
SPECS = MappingProxyType({
    Reason.LEGAL: (Owner.LEGAL, "Obtener revisión profesional y confirmación humana exacta de policy E.", True),
    Reason.BUSINESS: (Owner.HOLDER, "Seleccionar explícitamente un único negocio tras checklist EMPTY autorizada.", True),
    Reason.PROFILE: (Owner.HOLDER, "Confirmar el perfil exacto y su closure C; no reducirlo para ocultar historia.", True),
    Reason.READINESS: (Owner.PRIMARY, "Obtener A FULL vigente del negocio/perfil exactos y comprobar su contexto.", True),
    Reason.STALE: (Owner.PRIMARY, "Reevaluar A con fuentes actuales; nunca editar ni promover la evaluación antigua.", True),
    Reason.HISTORY: (Owner.PRIMARY, "Verificar corte/import/reconciliación/antecedentes existentes sin omitir fuentes.", True),
    Reason.UNSUPPORTED: (Owner.ENGINEERING, "Resolver contrato histórico no soportado con nueva autorización; conservar unknown.", False),
    Reason.PRIVACY: (Owner.LEGAL, "Verificar readiness E real; provisional sigue bloqueando.", True),
    Reason.EXPORT: (Owner.PRIMARY, "Verificar export E completo y vigente; G-PREP no crea un manifest.", True),
    Reason.PROVIDER: (Owner.PRIMARY, "Obtener attestations productivas reales del closure exacto tras permiso específico.", True),
    Reason.SAFE_CHECK: (Owner.ENGINEERING, "Validar e implementar aparte un check inocuo; no usar delivery como prueba.", True),
    Reason.PROVIDER_STALE: (Owner.PRIMARY, "Emitir nueva attestation autorizada y revalidar huellas/expiry sin refresh.", True),
    Reason.ENVIRONMENT: (Owner.PRIMARY, "Verificar entorno productivo exacto; local/sandbox no sustituyen producción.", True),
    Reason.BACKUP: (Owner.BACKUP, "Verificar copia reciente, hash, custodia y cifrado at-rest bajo permiso separado.", True),
    Reason.RESTORE: (Owner.BACKUP, "Verificar restore aislado actual con replay E antes de servir; existencia no basta.", True),
    Reason.DEPLOYMENT: (Owner.ENGINEERING, "Verificar SHA/schema79/roles/replicas/workers/scheduler compatibles sin réplicas antiguas.", True),
    Reason.KEY: (Owner.ENGINEERING, "Verificar runtime/verifier y estabilidad de HMAC sin mostrar ni copiar claves.", True),
    Reason.OPERATOR: (Owner.HOLDER, "Asignar operador primario, suplente y privacy/legal owner por decisión humana.", True),
    Reason.CUSTODIAN: (Owner.HOLDER, "Asignar responsable humano de custodia y restauración.", True),
    Reason.PAUSE: (Owner.PRIMARY, "Ensayar runbook D/F en sintético y validar su ejecutabilidad real por operador.", True),
    Reason.UNKNOWN: (Owner.SECONDARY, "Ensayar UNKNOWN por provider y aprobar revisión externa sin retry automático.", True),
    Reason.MONITORING: (Owner.PRIMARY, "Verificar acceso al read model F y evidencia de freshness de backup.", True),
    Reason.VOLUME: (Owner.ENGINEERING, "Mantener cohorte dentro de policy F64; un warning no elimina blockers.", False),
    Reason.BANK: (Owner.HOLDER, "Excluir banco del diseño piloto sólo por elección explícita; no habilitar capability no validada.", True),
    Reason.CLOSING: (Owner.LEGAL, "Mantener bloqueo E; no iniciar piloto sobre cuenta en cierre.", True),
    Reason.CLOSED: (Owner.LEGAL, "Conservar cierre E; no reabrir ni activar desde G-PREP.", True),
    Reason.MAIN: (Owner.ENGINEERING, "Integrar A–G en rama futura desde main actual y ejecutar CI completa antes de deploy.", False),
    Reason.FISCAL: (Owner.LEGAL, "Verificar modo fiscal del negocio; condición desconocida nunca omite AEAT de invoice.issue.", True),
    Reason.REAL: (Owner.PRIMARY, "Verificar evidencia real autorizada; hashes/documentación/fixtures no acreditan readiness.", True),
    Reason.D_PRODUCTION: (Owner.ENGINEERING, "Revisar guard de producción D con autorización futura explícita; no desactivarlo aquí.", False),
    Reason.RECOVERY: (Owner.ENGINEERING, "Resolver antes del piloto la recuperación D79 cuando A original haya caducado.", False),
})

BASE_BLOCKERS = frozenset((Reason.LEGAL, Reason.PRIVACY, Reason.EXPORT, Reason.READINESS,
                          Reason.HISTORY, Reason.BACKUP, Reason.RESTORE, Reason.DEPLOYMENT,
                          Reason.KEY, Reason.OPERATOR, Reason.CUSTODIAN, Reason.PAUSE,
                          Reason.UNKNOWN, Reason.MONITORING, Reason.MAIN, Reason.REAL,
                          Reason.D_PRODUCTION, Reason.RECOVERY))


def describe_profile(profile, *, fiscal_required):
    """Reutiliza exclusivamente Profile A y spec C; ninguna selección automática."""
    if type(profile) is not Profile:
        raise TypeError("Perfil A requerido.")
    if fiscal_required is not None and type(fiscal_required) is not bool:
        raise TypeError("Condición fiscal bool o desconocida requerida.")
    # Desconocido conserva conservadoramente las dependencias fiscales, sin certificar modo.
    closure, edges = profile.closure(fiscal_cancel_required=fiscal_required is not False)
    providers = {c.value: specification(c).provider_requirement for c in closure
                 if specification(c).provider_requirement is not None}
    return dict(profile=profile.value(), profile_hash=profile.content_hash,
                capability_closure=[c.value for c in closure], dependencies=edges,
                provider_requirements=providers)


def proposals():
    """Alternativas documentales; el perfil solicitado nunca se sustituye por ellas."""
    return {
        "web_only": describe_profile(Profile((C.EXPENSE_CONFIRM, C.EXPENSE_VOID)), fiscal_required=None),
        "web_fiscal": describe_profile(Profile((C.INVOICE_ISSUE,)), fiscal_required=True),
        "web_channels": describe_profile(Profile((C.EXPENSE_CONFIRM, C.EXPENSE_VOID, C.WHATSAPP, C.EMAIL)), fiscal_required=None),
    }


def assess(context: PreparationContext, *, now):
    """No se aceptan inputs 'approved/pass/verified_real' ni se consultan cuentas.

    En esta orden E es provisional, main no integrado y D productivo bloqueado.
    La retirada futura de blockers exige verificadores reales y otra autorización;
    añadir una referencia nunca los retira. READY está reservado, no implementado.
    """
    if type(context) is not PreparationContext:
        raise TypeError("Contexto cerrado requerido.")
    reasons = set(BASE_BLOCKERS) | {f.reason for f in context.findings}
    if context.business_id is None:
        reasons.add(Reason.BUSINESS)
    if context.profile is None:
        reasons.add(Reason.PROFILE)
        profile = dict(capability_closure=[], provider_requirements={})
    else:
        profile = describe_profile(context.profile, fiscal_required=context.fiscal_required)
        if any(c in profile["capability_closure"] for c in (C.BANK_IMPORT, C.BANK_MATCH)):
            reasons.add(Reason.BANK)
        if profile["provider_requirements"]:
            reasons.update((Reason.PROVIDER, Reason.SAFE_CHECK))
        if context.fiscal_required is None and C.INVOICE_ISSUE in profile["capability_closure"]:
            reasons.add(Reason.FISCAL)
    references = {f.reason: f.reference for f in context.findings}
    blockers = []
    for reason in sorted(reasons):
        owner, remediation, external = SPECS[reason]
        blockers.append(dict(reason_code=reason.value,
                             evidence_reference=references.get(reason, EvidenceReference()).value(),
                             remediation=remediation, responsible_party=owner.value,
                             requires_external_action=external))
    return dict(version=1, scope="G_PREP_ONLY", result=PilotResult.BLOCKED.value,
                software_status="A_F_CODE_VERIFIED_PASS", context=context.value(),
                context_hash=digest(context.value()), created_at=instant(now), expires_at=expiry(now),
                capability_closure=profile["capability_closure"],
                provider_requirements=profile["provider_requirements"], blockers=blockers,
                activation_authorized=False, real_evidence_verified=False)


def prepare_report(context, *, now):
    return PilotReadinessReport(canonical(assess(context, now=now)))
