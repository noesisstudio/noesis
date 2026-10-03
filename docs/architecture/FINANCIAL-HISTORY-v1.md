# Financial History v1 — contrato puro de Fase 1.9A

[ADR-014](ADR-014-financial-history-contracts.md), [orden](FASE-1.9A-orden.md),
[referencia 1.9](FASE-1.9-plan.md), [cierre](FASE-1.9A-cierre.md).
Módulo `src/noesis/financial_history/`; ninguna estructura produce efectos.

## API y versiones

| Archivo | Contratos / funciones |
|---|---|
| contracts.py | Assessment; RevisionIdentity; SourceReference; HistoricalIdentity; HistoricalDates; EvidenceReference; HistoricalEvidence; ExistingCoverage; HistoricalDependency; HistoricalCandidate; HistoricalIncidence; HistoricalDecision; HistoricalAuditContext |
| money_evidence.py | RawMonetaryEvidence; StorageEngine/Type; MoneyProvenance; CorroborationStatus; MoneyReason; raw_decimal |
| payloads.py | EventPayload; EventOrigin; EvidenceBasis; HISTORICAL_V2 |
| canonical.py | CanonicalContract; canonical_bytes; freeze; sha256; instant; version_one |
| financial_operations/historical.py | HistoricalAuthorization; guards de no promoción/no ejecución |

Canonicalización y derivación de identidad v1; evidence/raw/candidate contract_version=1;
Assessment rule_version=1; payload_version por catálogo. El sobre canónico incluye
nombre de contrato y versión canónica. Cambiar semántica exige nueva versión explícita.
No hay deserializador de manifests ni firma/autenticación de evidencias.

## Clasificación

| Categoría | Regla v1 | Semántica |
|---|---|---|
| A VERIFIED_HISTORY | history.verified | Evidencia durable suficiente para el hecho requerido |
| B OBSERVED_STATE | history.observed | Estado reproducible observado, sin afirmar toda su historia |
| C AMBIGUOUS | history.ambiguous | Interpretaciones múltiples, contradicciones o dependencias no acreditadas |
| D NOT_AUTOMATICALLY_TRANSFORMABLE | history.not_transformable | Requeriría inventar hecho, relación, revisión o información |

Disposiciones: candidate, covered_existing, out_of_scope, excluded,
pending_incidence. Severidades: info, warning, blocking. Razones cerradas:
verified_fact, observed_state, covered_existing, out_of_scope, excluded, incidence.
Regla y categoría deben coincidir; hashes explícitos, incluso para documentar una
ausencia. C/D requieren incidencia/exclusión con código; nunca son candidatos.
Covered exige referencia concreta. Excluir no cambia automáticamente categoría
ni severidad. Un Assessment es una declaración validada, no un clasificador real.

`observed_state` no acredita contabilización, deducibilidad, pago, confirmación
original ni autorización del usuario. B no acepta payload implícitamente verified_fact.

## Identidad y revisiones

HistoricalIdentity = SourceReference(business_id, source_type, source_id) +
RevisionIdentity(kind, value, fingerprint) + event_type + fact_slot + derivation_version.
IDs positivos BIGINT, fuente compatible con catálogo, slot estable ASCII hasta
64 caracteres. No datos de manifest/operador/importación/retry en esta estructura.

Revisión: observed_revision, durable_revision o immutable_fingerprint. La última
requiere hash completo y ordinal explícito; las otras no mezclan evidencia en
identidad. Un ordinal declarado no prueba que exista esa revisión: deberá
acreditarlo el futuro reader. No recrear versiones anteriores a migration64.

entry_identity usa namespace historical y hash propio; event_uuid UUIDv5 con
namespace constante propio. EntryIdentity.historical original no cambia.
assert_same_evidence detecta evidencia incompatible para la misma identidad.
Observación nueva cambia el hash de evidencia aunque identidad siga igual:
será conflicto a revisar, nunca sobrescritura silenciosa.

## Evidencia monetaria

Campos obligatorios explícitos, anulables donde proceda: storage_engine,
storage_type, raw_representation, exact_decimal, binary_representation,
binary_decimal, display_representation, candidate_cent_value, delta, provenance,
corroboration, corroborated_decimal, corroborating_hashes, reason, contract_version.

| Fuente | Procedencia | Requisitos |
|---|---|---|
| PostgreSQL NUMERIC / SQLite TEXT | exact | Decimal finito fiel al texto; no bits ni corroboración binaria |
| PostgreSQL DOUBLE / SQLite REAL | legacy_binary | Bits binary64 big-endian hex y texto reproducible; exact_decimal NULL |
| NULL | unknown | Todos los valores y candidatos NULL; ningún cero automático |

binary_decimal = Decimal exacto de los bits, **no decimal financiero original**.
NaN/Infinity solo pueden registrarse como non_finite, sin candidato ni corroboración.
Subcéntimos exactos se conservan como SUBCENT, nunca se redondean para aceptar.
Corroboration: exact, corroborated, uncorroborated, unknown.
Una corroboración binaria exige valor a céntimos declarado y hashes de evidencia;
el decimal corroborante debe reproducir el binario almacenado. Un residuo distinto
como 12.340000000000002 frente a 12.34 sigue siendo discrepancia.

Candidate-cent y delta pueden ser ambos NULL o ambos explícitos; se comprueba
HALF_UP contra raw con contexto Decimal propio. No se usan como verdad ni factory
Money. validates_declared_amount solo contrasta un importe ya declarado. A/B
rechazan importes requeridos unknown, subcéntimos y binarios no corroborados.
Los importes opcionales NULL solo coinciden con raw NULL; 0.00 requiere raw cero.
EUR exclusivamente; payload monetario JSON string decimal, nunca float.

Límites raw: 1100 dígitos/exponente para representar binary64 subnormal completo;
estos límites no amplían el rango Money del núcleo. No lector de DB implementado.

## Fechas

HistoricalDates exige legacy_kind/legacy_representation, civil_date,
economic_date, occurred_at, observed_at y recorded_at explícitos.
Unknown conserva NULL. Civil/naive no acreditan instante; naive no recibe zona.
Aware conserva instante original y su fecha civil; instant se normaliza a UTC.
Economic_date conocida coincide con fecha civil acreditada. Observed_at es la
observación explícita, nunca sustituto del hecho. Recorded_at será incorporación
futura; evidencia/candidato lo mantienen NULL. No defaults today/now.
DatePrecision: unknown/day/instant, derivada sin inventar precisión.

## Payloads

EventPayload(event_type, payload_version, origin, payload, currency) es un wrapper
en memoria. V1 de los once tipos y v2 de emisión/rectificación reutilizan el
validador existente, sin modificar bytes/hash de ese payload original.
El hash del wrapper es distinto por diseño: incluye origin y nombre de contrato.

| V2 especial solo historical | Fecha original obligatoria pero anulable | Campos nuevos obligatorios |
|---|---|---|
| supplier_invoice.confirmed | confirmed_on | evidence_basis; evidence_hash |
| expense.confirmed | confirmed_on | evidence_basis; evidence_hash |
| bank_transaction.imported | imported_on | evidence_basis; evidence_hash |

Todos los demás campos obligatorios/opcionales y semántica económica se mantienen
según [catálogo v1](ECONOMIC-EVENTS-v1.md). Fecha económica original separada:
issued_on/spent_on/booked_on, ya anulables en sus v1. Bases verified_fact y
observed_state admiten fecha original conocida/desconocida; evidencia verificada
no implica precisión temporal inventada. Hash SHA256 minúsculo de evidencia
congelada. Campos extra, tipos/versiones desconocidos, float y monedas ajenas
fallan; v2 especiales live falla. No extender v2 a los demás ocho tipos.

**EconomicEvent y persistencia schema69 todavía rechazan estos tres v2.**
No append histórico nuevo ni ampliación del catálogo durable en esta unidad.
El wrapper acepta los v2 existentes de factura; HistoricalCandidate los bloquea
hasta definir evidencia raw de sus líneas y registro fiscal. Candidatos de factura
v1 representan el hecho mínimo acreditado, no la totalidad de evidencia v2.

## Candidatos, dependencia y cobertura

HistoricalCandidate agrupa identidad, EventPayload, evidencia/fechas, Assessment,
dependencies y existing_coverage. Source/type/version/basis/hash/amount/currency
son accesibles mediante estos contratos y propiedades derivadas. Frozen, mapas
copiados y congelados; sin persistencia ni construcción de EconomicEvent durable.
Evidencia retiene raw para cada importe contractual de cabecera/before/after,
incluido NULL, fechas y referencias mínimas; los hashes corroborantes deben estar
referenciados. Rechaza valores monetarios no sustentados para A/B.

Dependencias exactas del catálogo: rectifies, settles, corrects, voids, matches,
evidence_for. Identidad concreta, mismo negocio, sin auto dependencia. Corrección/
void requiere mismo origen, misma clase de revisión y ordinal anterior acreditado.
Rectificativa exige otra fuente. IDs de invoice/payment declarados deben coincidir;
match usa importación del mismo movimiento. No heurísticas amount/date.
Missing/C/D bloquean; B también bloquea conservadoramente. No grafo topológico aún.

ExistingCoverage exige identidad exacta, event_uuid, event_content_hash y origin;
covered_existing requiere esa referencia y no es importable. Esto no comprueba
todavía que el evento exista ni que su cobertura durable corresponda realmente.

`importable` solo evalúa categoría A/B candidate no blocking, padres A consistentes
y dinero sustentado. **No concede permiso, no acredita fuentes externas, no ejecuta
ni significa eligible_for_activation.** Un futuro servicio verificará evidencia real,
dependencias durables, reglas específicas por source y reconciliación global.

## Incidencias y decisiones

Catálogo cerrado de 14 códigos, sin motor genérico de tickets:

- MONEY_BINARY_UNCORROBORATED
- MONEY_SUBCENT
- REQUIRED_VALUE_UNKNOWN
- SYNTHETIC_LEGACY_PAYMENT
- PAID_WITHOUT_PAYMENT
- PAYMENT_OVER_TOTAL
- POSSIBLE_DUPLICATE_PAYMENT
- FISCAL_AMOUNT_MISMATCH
- MIGRATED_DOCUMENT_PROFILE
- RECTIFICATION_PARENT_MISSING
- BANK_LINK_AMBIGUOUS
- SOURCE_DRIFT
- SOURCE_HISTORY_LOST
- EXISTING_EVENT_CONFLICT

HistoricalIncidence exige source, evidence_hash, code y assessment concordantes.
HistoricalDecision: add_evidence, select_supported_interpretation, exclude,
keep_blocked; recorded_by/decided_at explícitos, referencias tipadas e
interpretation_hash solo para selección. Resolver requiere evidencia; una opinión
no cambia categoría ni elimina bloqueo. Ningún efecto automático sobre candidato.

## Autoridad y acceso

HistoricalAuthorization: actor/session originales NULL, recorded_by positivo,
historical namespace, historical_unknown, historical.record, PREPARED/REJECTED/
CANCELLED. El futuro servicio debe autenticar recorded_by, no aceptar identidad IA.
Namespace immutable o receipt histórico previo son marcas de no ejecución,
incluidos registros antiguos con namespace distinto. HUMAN/MANDATE posteriores
y transition APPROVED/COMMITTED fallan en servicio/repositorio; execute falla
antes de revision_reader/validator/executor/replay. Decoder bloquea estados
ejecutables históricos; EE rechaza usarlos como autoridad live. Sin nuevos estados.

No migración: SQL directo aún puede introducir algunos metadatos inconsistentes
en schema69; las fronteras de aplicación los rechazan. No prometer constraint
SQL nuevo. No importer ni bypass que escriba directamente. Guarda durable y
auditoría de incorporación serán requisitos de la futura persistencia histórica.

HistoricalAuditContext(business_id, recorded_by, manifest_uuid, item_uuid,
evidence_hash, permission=historical.audit) declara alcance. matches comprueba
negocio/hash; no autentica permiso, no comprueba manifest/item existentes ni
relaja el acceso normal por creador. Estos UUIDs no forman identidad del hecho.

## Canonicalización y privacidad

JSON UTF8 compacto con claves ordenadas, decimals como strings, NULL preservado,
enums por valor, fechas ISO, aware UTC microsegundos, UUID minúsculo. Unicode
original sin normalizar NFC; listas preservan orden, conjuntos semánticos de
refs/deps/hashes se ordenan por contrato. Máximo128KiB, profundidad16, mapas/listas256,
textos4096. No float, Decimal no finito, timestamp naive canónico ni blobs bytes.

Raw money solo texto numérico/bits; references solo IDs/hashes/kind/business.
No PDF, XML completo, imágenes, conversaciones, teléfonos, tokens ni notas libres.
Payloads existentes pueden conservar descripciones de negocio necesarias según
su esquema, sin convertir raw evidence en archivo documental. No retención/purga.

## Frontera de fase

Cinco flags OFF. No DB nueva, manifest real, scanner/reader, dry-run, epoch/fence,
import/backfill, reconciliación ni activación. Fixtures sintéticos exclusivamente.
No writer/Capture live para reconstruir historia, AEAT, numeración, QR/XML, cobros,
GL, Open Items, Tax Ledger ni reporting. 1.9B exige otra orden explícita.
