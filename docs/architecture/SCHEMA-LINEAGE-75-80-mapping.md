# Mapeo canónico y cambios futuros por módulo

Sólo diseño. [Contrato](SCHEMA-LINEAGE-75-80-contract.md),
[hashes/versiones](SCHEMA-LINEAGE-75-80-hash-impact.md), [matriz](SCHEMA-LINEAGE-75-80-test-matrix.md).
«Cambiar» en este documento significa una implementación posterior autorizada.

## 1. Mapa final

| Identidad | Catálogo histórico SHA870 | Nueva cadena | Precondición exacta |
|---|---:|---:|---|
| CRM captacion_hoja_y_tipo | Ausente | 74 | Prefijo canónico1..73 y objetos73 completos |
| A evaluacion_readiness_financiera | 74 | 75 | CRM74 exacta, sin tablas readiness preexistentes inexplicadas |
| B resoluciones_antecedentes_financieros | 75 | 76 | A75 realmente instalada y prefijo1..75 íntegro |
| C cobertura_cancelacion_fiscal_live | 76 | 77 | B76/A75 y objetos anteriores válidos |
| D activacion_handoff_generaciones | 77 | 78 | C77, parents A/history y baseline previos verificables |
| E privacy_export_retention_closure | 78 | 79 | D78, guards/generaciones intactos y perfil físico conocido |
| F providers_preflight_dispatch_evidence | 79 | 80 | E79 con contrato instalado; policy profesional NO se aprueba por instalar |
| G PilotGate/RecoveryReadiness | Sin nueva migración | Target80 | F80 canónica; lineage binding y todos los prerequisitos propios |

Por paso: lock adquirido; origen exacto validado; callback asignado a identidad
única; DDL+fila version/name/applied_at nuevos en misma TX; validar estado
resultante antes de continuar. No IF NOT EXISTS para absorber objetos de otra
lineage. Preexistencias desconocidas bloquean, no se adoptan.1–74 y su metadata
ya aplicada no cambian. Históricos73 siguen73 hasta ejecutar un plan autorizado.

Camino73:73→CRM74→A75→B76→C77→D78→E79→F80. Camino principal de producción ya
observada:CRM74→75→76→77→78→79→80. Ninguno se ejecuta en esta fase. Desde0,
se aplican todas1..80; no saltar etapas. LegacyA74 se diagnostica y bloquea.

## 2. Versiones y namespaces

Nuevo binding `SchemaBinding v1`; familias cerradas de control/evidencia que lo
incorporan usan revisión2. No cambia la canonicalización JSON v1 ni se numeran
versiones de payload según migrations. `schema_version` en **evidencia nueva**
significa etapa física real observada, no el número mínimo del módulo.

A creada en75 declara75; A creada en80 declara80. D request en78 declara78;
en80 declara80. El módulo se identifica por tipo/contract_version, no declarando
siempre75/78. Guards aceptan exactamente prefijos soportados con binding actual;
un recibo75 no autoriza una ejecución80 tras la migración: nueva evaluación.

Histórico A74/D77 se decodifica con su contrato original. No se asigna una
lineage canónica por sustitución. Perfil A v1, spec C v1, policy financiera v1,
policy profesional E y payloads EE/Operations mantienen versiones/semántica salvo
una orden funcional distinta. Un campo legacy llamado schema_version puede ser
marcador de formato: history manifest escribe70 y A histórica74/D histórica77
eran bases del contrato. Se preservan y etiquetan como **legacy marker**, no se
inventan versiones físicas originales desconocidas.

## 3. A75 — readiness

Registry75; `financial_activation/schema.py` instala sus tres tablas con
`evaluation_version=2`, columnas existentes preservadas por nombre y CHECK físico
de schema_version en75..80. El guard completo compara prefijo/nombres/objetos y
schema_version con binding/TX, no sólo esa CHECK. Control conserva off/validating,
generation0/ever_enabled=false iniciales. Provenance nueva readiness_v2.

Evaluator elimina el literal74 como contexto físico, obtiene binding actual y
añade a context/result/proofs revisión2. Repository parametriza physical N en
INSERT, conserva actor/sesión/tenant/expiry y SQL guard. A en80 exige E79/F80
por capabilities instaladas verificadas, sin ramas numéricas heredadas78/79.
Contratos: prefijos75..80 explícitos; v1 sólo lectura histórica, no nueva autoridad.
Diagnostics razonan por código de lineage; no writes para «reportar» esquema malo.
Tests: desdeCRM74, A75 y A80, inserts falsificados, conservation de A antigua,
binding stale, proofs/hash/TTL, vacío/unknown, privacidad/provider bloqueantes.

## 4. B76 — antecedentes

Registry76; schema contract sólo prefijos76..80 validados; A75 instalada antes.
ResolutionRequest/result/evidence envelope revisión2 incluye binding actual en
context/result hashes. SourceRef, event/operation/authorization IDs, quality,
source_revision, historical_unknown y source hashes originales no se alteran.
Revalidación every_use conserva FinancialSession/gate y checks de autoridad
original, no vigencia retroactiva inventada. B v1 decodificable históricamente;
no se reutiliza para crear authority nueva ni se promueve observed_state.
Tests: A ausente con fila75, prefijo76 falso, precedentes cross-tenant, drift,
referencias inmutables, pérdidas/versiones y carreras, nuevo contexto80.

## 5. C77 — fiscal cancellation/capabilities

Registry77; coverage/revision/source y captura económica/fiscal conservan su
semántica. Spec/capability catalog y closure v1 únicos siguen iguales. Valida
canonicalC77..F80, resolución B revisión2 actual y autoridad humana exacta en
misma TX. Captura requiere guards SQL/coverage; no inferir capability desde N.
El EE fiscal mantiene amount=None/EUR/total contextual, tipo y payload version.
Coverage/result financiero no gana un campo monetario ni se renumera.
Binding técnico se compromete en el nuevo sobre B/D que autoriza el uso;
coverage e identidad EE/Operation no se reescriben. Tests incluyen negativos
legacy/missingB/binding stale, atomicidad/crash/rollback y ausencia de provider I/O.

## 6. D78 — control plane

Registry78; activation_contracts Request revisión2 acepta N78/79/80 exactos y
binding actual. SQL CHECK request_version y guards de hashes/contexto soportan
revisión2; transitions/receipts/grant proofs/snapshot/recovery envelope nuevos
revisión2. No modificar receipts v1 ni su decodificación histórica.

Baseline nueva captura DDL **canónico previo aD78** (A75/B76/C77 +history/CRM),
sin metadatos de una instalación legacy. Hash nuevo de metadata y verificador/
contexto instalados propios, no clonar claves privadas de un laboratorio.
El CHECK de A75 y contrato2 cambia ese baseline: no atribuirle el hash D77.
Generations origin handoff/recovery, G+1, fence/T0/handoff, grants exactos y
ever_enabled siguen sus reglas. History/storage/cut hashes antiguos permanecen;
un cambio sólo de columnas live NULL conserva la exclusión declarada por verifier.

Borrowed execution valida binding dentro de TX, app+SQL guards de operation/
generation/capability actuales, sin conexiones/commit propios. Pausa conserva
HOLD/DRAIN, no fallback tras ever_enabled. F80 exige preflight fuerte; D78/E79
siguen etapas sintéticas de contrato, nunca activación productiva sin G.
Tests: baseline, cada transición, actor stale, pausa/resume/A expirada,
G+1/history intactos, falsificación SQL, crash entre fence/receipt y carreras.

## 7. E79 — privacidad y conservación

Registry79; installed/readiness/export/retention/closure/replay sólo perfiles con
capability técnica PRIVACY_E y prefijos79/80. Exports nuevos contract_version2,
canonical_version1, schema_version real y binding en manifest/context.
En80 se añaden las secciones F y la exclusión de metadata handoff declarada por
F; en79 sólo catálogo E. No usar el viejo `manifest.schema_version==79` como F.
Catálogo cerrado por perfil físico/capability, sin perder secciones ni >500rows.

Policy profesional permanece provisional hasta aprobación real exacta. El
contenido de policy/approved_hash existente no se recalcula por el nuevo sobre;
sus versiones de negocio no cambian. Sobre de evidencia E nueva revisión2
vincula policy al contexto, sin crear ni heredar una aprobación. Cierre, erasure,
supresiones, inventarios y replay nuevos se atan a binding con revisión2;
legado de conservación sigue bloqueando borrado/serving aunque no habilite READY.
Restore usa capability/lineage, no >=78/79, y registro vigente de supresiones.
Pruebas: E79/D78 separados, F80 export, privacy_not_ready, closure, retención,
replay, cross-tenant, snapshots consistentes y grandes volúmenes.

## 8. F80 — providers/preflight

Registry80; todos los exactos79 actuales pasan a **F80 canónica verificada**,
incluidos baja/conservación db.py, handoff A/D, dispatch/bindings y backuplegacy.
No reemplazo global, no >=80, no exclusión de guards de otros módulos.
Attestation revisión2/checker financial_provider_checker_v2, physical80/binding;
preflight/context/binding/attempt/start/result/observation envelopes nuevos v2.
Environment/credential fingerprints HMAC, tenant, nivel/TTL, UNKNOWN y secret
exclusions conservados. Resultado provider no crea EE ni financia autoridad.
Vincular binding de esquema junto a operation/generation/capability/connection/TX;
requestHMAC nuevo sólo si cambia su request técnico, no por cambiar un importe.

Production observations siguen derivando exclusivamente de resultado real
durable, nunca de mocks. local/sandbox no habilitan producción. Readiness/handoff
sólo verifican recibos; ningún check de red. Pause/closure dominan. New F80
preflights revalidan actualSchemaBinding cada uso, incluidos resumes. Tests:
drift/cross-tenant, guards SQL, strong binding, attempts/results, UNKNOWN,
crashes/concurrency, idempotency, pausa/cierre y restore sintético sin providers.

## 9. G80 — verificación sin migración

VerificationContext revisión2 añade schema_binding80; v1 no tenía schema_version
propia, no fingir un campo79 en su JSON antiguo. PilotVerifiers/PilotGate nuevos
v2 verifican físicamente80 canónico y recomputan binding. MAIN_INTEGRATION exige
main/base/candidate/Financial chain/V2 port/bridge refs nuevas, CI fresca exacta
y review humana;822 y870 sólo referencias históricas.

RecoveryReadiness v2 compromete binding80 y refs nuevas, conserva A original
íntegra cuando haya vencido sólo para el arco permitido ever_enabled+paused.
Primera activación conserva TTL A. Deployment/restore/replicas/resume evidence
exige binding80, roles/flags/SHA/environment actuales y autoridades propias.
Los hashes antiguos no se aceptan como prueba nueva por igualdad de números.
Guard REAL sigue bloqueado y missing origins/collectors/legal no se inventan.

## 10. History y detección de schemas intermedios

| Consumidor | Prefijos canónicos permitidos por contrato | Obligación |
|---|---|---|
| Diagnostic | 70,71,72,73,CRM74,A75,B76,C77,D78,E79,F80 | Identidad exacta y sus guards/scope actuales |
| Cutoff | 71..80 enumerados como arriba | Fence/epoch y boundary_current íntegros |
| Import | 72..80 enumerados | Batches/proofs/versiones propias intactas |
| Reconciliation | 73..80 enumerados | SELECT por identidad, sólo writes propios de audit |

«..» abrevia prefijos listados, no operador >=. Esta matriz no autoriza acciones
history en esta fase ni habilita serving en un runtime normal80 sobre un intermedio.
History contratos63–73 y payloads v1/v2 se conservan; markers70/71/72/73 no se
convierten automáticamente en physical80. A/B/D/G comprometen su schema_binding
actual junto a los hashes originales, sin insertar campos en manifests históricos.

Inventario anterior:423 líneas/110 archivos,32src/26tests/52docs-CI, categorías
A–I. Referencias exactas Git enSHA870 y paths pertinentes se recogen en el
[hash-impact](SCHEMA-LINEAGE-75-80-hash-impact.md). Artefactos/hashes/tests anteriores
no prueban la adaptación: se exige una ejecución nueva del candidato final.
