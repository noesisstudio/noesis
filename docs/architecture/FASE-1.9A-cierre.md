# Fase 1.9A — contratos y gobernanza de históricos

**1.9A CERRADA — 24 criterios PASS, 0 FAIL; autoauditoría PASS.**
Solo 1.9A; no1.9B. Base schema69; cinco flags OFF; fixtures sintéticos.
[Orden humana](FASE-1.9A-orden.md), [ADR-014](ADR-014-financial-history-contracts.md),
[contrato completo](FINANCIAL-HISTORY-v1.md), [referencia1.9](FASE-1.9-plan.md).

## 1. Archivos

Nuevos:

- src/noesis/financial_history/__init__.py
- src/noesis/financial_history/canonical.py
- src/noesis/financial_history/contracts.py
- src/noesis/financial_history/money_evidence.py
- src/noesis/financial_history/payloads.py
- src/noesis/financial_operations/historical.py
- tests/test_financial_history.py
- docs/architecture/ADR-014-financial-history-contracts.md
- docs/architecture/FINANCIAL-HISTORY-v1.md
- docs/architecture/FASE-1.9-plan.md
- docs/architecture/FASE-1.9A-orden.md
- docs/architecture/FASE-1.9A-cierre.md

Modificados:

- src/noesis/financial_operations/contracts.py
- src/noesis/financial_operations/repository.py
- src/noesis/financial_operations/service.py
- src/noesis/economic_events/service.py
- tests/financial_operations_contract.py
- tests/economic_persistence_contract.py
- AGENTS.md
- docs/project-state.json
- docs/Inicio.md
- docs/Arquitectura.md
- docs/Decisiones.md
- docs/Estado-actual-main.md
- docs/Tareas-vivas.md
- docs/Mapa-codigo.md
- docs/Registro-cambios.md
- docs/Registro-QA.md
- docs/areas/01-vision-general.md
- docs/areas/08-financial-core.md
- docs/architecture/README.md
- docs/architecture/FASE-1-plan.md
- docs/architecture/ADR-002-economic-events.md
- docs/architecture/ADR-006-financial-operations.md
- docs/architecture/ADR-007-economic-persistence.md
- docs/architecture/ECONOMIC-EVENTS-v1.md
- docs/architecture/ECONOMIC-PERSISTENCE-v1.md
- docs/architecture/FINANCIAL-OPERATIONS-v1.md

## 2. Contratos nuevos

Tipos congelados: Assessment, RevisionIdentity, SourceReference, HistoricalIdentity,
HistoricalDates, EvidenceReference, HistoricalEvidence, ExistingCoverage,
HistoricalDependency, HistoricalCandidate, HistoricalIncidence, HistoricalDecision,
HistoricalAuditContext, RawMonetaryEvidence, EventPayload, HistoricalAuthorization.
Versión canónica1, identity derivation1, raw/evidence/candidate contract1,
rule1, payload1/2 permitidos explícitamente. No repository ni reader histórico.

## 3. Clasificación

A VERIFIED_HISTORY (historia suficiente); B OBSERVED_STATE (estado reproducible,
sin afirmar confirmación/historia completa); C AMBIGUOUS; D NOT_AUTOMATICALLY_
TRANSFORMABLE. Disposition/severity separados. RuleId/reason/code/evidence cerrados.
C/D no importables. B no puede llevar base verified_fact. No clasificador LLM.

## 4. Identidad

Negocio/origen/ID/revisión/tipo/fact_slot/version. SHA256 y UUIDv5 propios, sin
manifest/operador/retry/reloj. EntryIdentity.historical original intacta.
Misma identidad con evidencia distinta falla por conflicto; no inventar revisiones.

## 5. Raw evidence

PG NUMERIC/SQLite TEXT exactos; REAL/DOUBLE conservan texto/bits/decimal de bits
como procedencia binary, nunca como decimal original. NULL unknown, subcéntimos,
NaN/Infinity diagnósticos. Candidate-cent/delta explícitos sin conversión Money.
Corroboración exige decimal declarado y hashes referenciados, compatible con bits.

## 6. Política monetaria

Decimal/EUR, strings monetarios JSON, ningún float de entrada contractual. No
normalización legacy ni tolerancia que repare dinero. A/B requieren evidencia
exacta/corroborada para importes requeridos; opcional NULL se mantiene NULL, cero
requiere evidencia cero. Redondeo HALF_UP exclusivamente para diagnóstico.

## 7. Fechas

Civil/naive/aware/unknown, economic_date, occurred_at, observed_at y recorded_at
distintos y explícitos. No zona naive ni today/now por defecto. Recorded_at NULL
en candidato/evidencia; será incorporación futura, no instante del hecho.

## 8. V2 históricos

Solo supplier_invoice.confirmed, expense.confirmed, bank_transaction.imported,
con confirmed_on/imported_on nullable, evidence_basis/hash obligatorios.
Solo origin historical; campos económicos v1 conservados. Wrapper puro separado:
EconomicEvent/schema69 no los persiste aún. V2 de factura existente intacto,
pero candidato histórico v2 bloqueado hasta contrato raw de líneas/fiscal.

## 9. Historical_unknown

Actor/session originales NULL, recorded_by real autenticado, historical.record,
namespace/kind históricos. PREPARED conserva el registro; REJECTED/CANCELLED sin
efecto. No nuevo estado. El contrato no autentica por sí solo recorded_by.

## 10. No ejecución

Marca namespace histórico immutable o cualquier receipt histórico previo bloquea
HUMAN/MANDATE, APPROVED/COMMITTED, execute y autoridad EE live. Guards antes de
callbacks, validadores, ejecutores y recuperación. Registros antiguos con namespace
ordinary y receipt desconocido tampoco promocionan. Acceso ordinario intacto.
SQL directo puede insertar ciertos metadatos inconsistentes en schema69; guards
de aplicación los rechazan. No afirmar nuevas restricciones SQL ni escribir por
bypass. Persistencia histórica futura requerirá sus propios guards auditables.

## 11. Candidato / dependencias / acceso

Frozen/canonicalizable, source/version/basis/hash/amount/currency/fechas/assessment,
dependencias concretas y cobertura existente coherentes. Padres A permitidos;
missing/C/D y conservadoramente B bloquean. Cross-business/self/relaciones/revisión
incoherentes fallan. No amount/date heurístico, no grafo completo.
Importable solo consistencia local, no permiso ni acreditación de fuentes reales.
Contexto audit pure exige business/recorded_by/permission/manifest/item/hash;
matches no autentica ni consulta existencia. No acceso repository implementado.

## 12. Incidencias

Los catorce códigos aprobados, sin añadidos: MONEY_BINARY_UNCORROBORATED,
MONEY_SUBCENT, REQUIRED_VALUE_UNKNOWN, SYNTHETIC_LEGACY_PAYMENT,
PAID_WITHOUT_PAYMENT, PAYMENT_OVER_TOTAL, POSSIBLE_DUPLICATE_PAYMENT,
FISCAL_AMOUNT_MISMATCH, MIGRATED_DOCUMENT_PROFILE, RECTIFICATION_PARENT_MISSING,
BANK_LINK_AMBIGUOUS, SOURCE_DRIFT, SOURCE_HISTORY_LOST, EXISTING_EVENT_CONFLICT.
Decisiones cerradas requieren evidencia; no convierten opiniones en hechos.
Referencias mínimas; no raw PDF/XML/imagen/conversación/notas. Retención pendiente.

## 13. Tests

39 tests puros nuevos: A/B/C/D, ejes/reglas/versiones, identidad/componentes,
conflicto, raw exact/binario/residuo/subcent/NaN/Infinity/zero/null/float,
fechas, v2 origin/version/basis/hash, v1 golden, dependencias/cobertura,
privacidad/canonicalización/Unicode/maps/lists/inmutabilidad, auditcontext,
autoridad/noefecto y guards de flags/schema.
Compartidos SQLite/PG: no promoción/mandato/execute, callbacks no invocados,
receipt antiguo, SQL inconsistente y EE live rechazado. Regresiones Capture,
writers, canales, recurrencias, VERI*FACTU y legacy en suite/matriz completa.

## 14. Compatibilidad

Once v1 golden reproducen bytes/hash previos. Módulos contracts.py/invoice_payload.py
económicos originales no cambian; emisión/rectificación v2 continúa por Capture.
EntryIdentity.historical anterior intacta. Cambio intencional: se retira la
promoción antes permitida de historical_unknown; test antiguo ahora verifica rechazo.
No cambios de productores/writers/fiscal/flags.

## 15. Migraciones

Cero migraciones. Schema69 conservado; nada de tablas epochs/manifests/items/
incidences/decisions/reconciliations, ni ampliación durable v2. Guards de servicio
bastan para bloquear execute; pruebas con SQL inconsistente lo comprueban.

## 16. Suite / gates

Validación dirigida final: 121 PASS (55.350 s); PostgreSQL Operations/EE: 65 PASS
(14.064 s). Matriz PostgreSQL final: 251 PASS (101.202 s), Core/Operations/EE/
Writers/Invoice/Payment-Bank/Purchasing/Channels, después del último cambio funcional.
Ruff, Bandit high/high, pip-audit, uv lock --check, secretos sobre archivos staged,
verdad documental y diff/check PASS; Node9 PASS; 455 enlaces relativos sin errores.
SQLite0→69→0→69 PASS; PG migración histórica sintética32→69 y 36 rutas PASS.
HTTP local health/ready/portada/login200 en base sintética nueva.
Suite general final: **1671 PASS (1321.144 s)**, posterior al último cambio
funcional; incluye39 contratos nuevos y6 regresiones compartidas nuevas.
No CI remoto ni despliegue acreditado en esta validación local.
No usar ejecuciones generales interrumpidas como evidencia de cierre.
Logs locales descartables: TEMP/noesis-19A-*-final.log; nunca datos productivos.

## 17. Decisiones, diferencias y riesgos

Refinamientos conservadores: wrapper puro en vez de ampliar almacenamiento;
padre B bloquea; candidato factura v2 bloqueado hasta raw de líneas/fiscal;
marca estructural PREPARED no ejecutable en lugar de nuevo estado. No ampliación
de alcance, ningún reader/importer. Reference1.9 no sustituye órdenes posteriores.

Los contratos no prueban autenticidad ni suficiencia material de hashes/documentos.
Una revisión declarada no demuestra que exista. La lectura futura deberá acreditar
estos hechos con reglas por origen. Schema69 no recibe guard SQL nuevo contra toda
inconsistencia de metadatos; servicios rechazan su efecto. No retención final,
corte/epoch/fence, reconciliación ni eligible_for_activation. No prueba producción/
Meta/AEAT/deployment. Rollback conserva guards y evidencia, sin downgrade destructivo.

## 18. Criterios individuales y autoauditoría

Matriz final después de suite completa, regresiones y gates.

| Criterio | Resultado |
|---|---|
| Lectura/código main/schema contrastados | PASS |
| Solo módulo contractual, no repository/reader | PASS |
| A/B/C/D separados de disposición/severidad | PASS |
| Reglas/códigos/versiones cerrados sin LLM | PASS |
| Identidad estable y conflicto/factory previa | PASS |
| Raw evidence exact/binary/unknown | PASS |
| Ninguna conversión implícita float→Money | PASS |
| Unknown distinto de cero | PASS |
| Fechas sin zona/reloj inventados | PASS |
| Evidence basis sin falsa confirmación | PASS |
| Tres v2 acotados históricos, no live | PASS |
| Historical_unknown actor NULL / recorded_by | PASS |
| No promoción ni execute / PREPARED sin efecto | PASS |
| Acceso audit pure sin relajar ordinario | PASS |
| Candidatos/dependencias congelados coherentes | PASS |
| Padres missing/C/D bloquean | PASS |
| Catorce incidencias y decisiones con evidencia | PASS |
| Privacidad mínima, sin blobs/conversaciones | PASS |
| Canonicalización determinista, ningún float | PASS |
| Tests nuevos / relacionados SQLite/PG | PASS |
| Cero migraciones, schema69 | PASS |
| Fixtures sintéticos, ninguna producción | PASS |
| Regresión completa/gates/flags OFF | PASS |
| Gobernanza actualizada, no1.9B | PASS |

Autoauditoría solicitada:

| Pregunta | Respuesta / evidencia |
|---|---|
| 1. ¿B puede presentarse como verificado? | No: basis/categoría/payload concordantes; candidato rechaza B con v1 implícitamente verificado |
| 2. ¿Float legacy se convierte silenciosamente en Money? | No: bits crudos separados; ningún factory, corrob explícita |
| 3. ¿Unknown se convierte en zero? | No: NULL solo coincide con NULL |
| 4. ¿Unknown date se convierte en today? | No: sin reloj/defaults y representación unknown estricta |
| 5. ¿Identidad depende de operador? | No: campo ausente, derivación cerrada |
| 6. ¿Identidad depende de manifest? | No: campo ausente; auditcontext separado |
| 7. ¿Operación histórica se convierte en live? | No vía APIs: namespace/receipt bloquean HUMAN/MANDATE y autoridad EE live; SQL corrupto no adquiere efecto |
| 8. ¿Puede execute? | No: falla antes de callbacks/efectos/replay |
| 9. ¿Historical_unknown inventa actor? | No: actor/session NULL; recorded_by separado |
| 10. ¿Payload especial histórico se utiliza live? | No: wrapper rechaza y durable aún no acepta v2 especial |
| 11. ¿Se modificó v1? | No: once golden y validadores originales intactos |
| 12. ¿Manifest/backfill prematuro? | No: solo referencias UUID contractuales, ninguna tabla/servicio |
| 13. ¿Reader real conectado? | No: import graph puro, sin scanner/DB |
| 14. ¿1.9B iniciada? | No |
