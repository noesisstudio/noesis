# Fase 1.9B — informe de cierre

Estado: Fase1.9B completada. 47 PASS, 0 FAIL. Exclusivamente diagnóstico.
CI de implementación [37137042961](https://github.com/noesisstudio/noesis/actions/runs/37137042961) SUCCESS sobre f474d42:
ambos jobs, general1709 (582.266s), PostgreSQL288, gates/migraciones/código anterior/
privacidad/rollback PASS. Adenda final solo documental: runtime/tests/dependencias/
workflow idénticos al commit validado. Despliegue no verificado; producción no consultada.
No se ha iniciado1.9C. [Orden](FASE-1.9B-orden.md), [ADR015](ADR-015-financial-history-diagnostic-inventory.md),
[contrato](FINANCIAL-HISTORY-INVENTORY-v1.md), [mapa previo](FASE-1.9B-fuentes.md).

## 1. Archivos creados y modificados

41 archivos de entrega. Nuevos módulos `src/noesis/financial_history/`:
sources.py, raw.py, readers.py, planning.py, classifier.py, review.py,
repository.py, service.py, schema.py. migrations.py solo registra70 y wrappers;
sin modificar migraciones anteriores. Nuevos tests: inventory_contract compartido,
SQLite y PostgreSQL. test_financial_history.py limita el guard a módulos puros
originales y actualiza versión esperada; payment_bank_capture_contract.py mantiene
la reparación68→69 con upgrade(69) explícito. CI añade el contrato PG.
db.py solo incorpora cuatro nombres al guard existente de conservación de baja;
sin lógica financiera nueva. La guía de seguridad06 documenta esa protección.

Nuevos documentos ADR015, FINANCIAL-HISTORY-INVENTORY-v1, FASE-1.9B-orden/fuentes/
cierre. Actualizados AGENTS, project-state, Estado-actual-main, Tareas-vivas,
Registro-QA/cambios, Mapa-codigo, Arquitectura, Decisiones, Inicio, architecture/
README/FASE-1.9-plan/FINANCIAL-HISTORY-v1, guías de áreas01/03/04/08 y guía técnica.
Sin dependencias nuevas, interfaz, canales, productores ni cambio funcional fiscal.

| Estado | Archivo |
|---|---|
| Modificado | `.github/workflows/ci.yml` |
| Modificado | `AGENTS.md` |
| Modificado | `docs/02-tecnico/Guia-tecnica-ingeniero.md` |
| Modificado | `docs/Arquitectura.md` |
| Modificado | `docs/Decisiones.md` |
| Modificado | `docs/Estado-actual-main.md` |
| Modificado | `docs/Inicio.md` |
| Modificado | `docs/Mapa-codigo.md` |
| Modificado | `docs/Registro-QA.md` |
| Modificado | `docs/Registro-cambios.md` |
| Modificado | `docs/Tareas-vivas.md` |
| Creado | `docs/architecture/ADR-015-financial-history-diagnostic-inventory.md` |
| Modificado | `docs/architecture/FASE-1.9-plan.md` |
| Creado | `docs/architecture/FASE-1.9B-cierre.md` |
| Creado | `docs/architecture/FASE-1.9B-fuentes.md` |
| Creado | `docs/architecture/FASE-1.9B-orden.md` |
| Creado | `docs/architecture/FINANCIAL-HISTORY-INVENTORY-v1.md` |
| Modificado | `docs/architecture/FINANCIAL-HISTORY-v1.md` |
| Modificado | `docs/architecture/README.md` |
| Modificado | `docs/areas/01-vision-general.md` |
| Modificado | `docs/areas/03-cerebro.md` |
| Modificado | `docs/areas/04-facturas.md` |
| Modificado | `docs/areas/06-rgpd-y-seguridad.md` |
| Modificado | `docs/areas/08-financial-core.md` |
| Modificado | `docs/project-state.json` |
| Modificado | `src/noesis/db.py` |
| Creado | `src/noesis/financial_history/classifier.py` |
| Creado | `src/noesis/financial_history/planning.py` |
| Creado | `src/noesis/financial_history/raw.py` |
| Creado | `src/noesis/financial_history/readers.py` |
| Creado | `src/noesis/financial_history/repository.py` |
| Creado | `src/noesis/financial_history/review.py` |
| Creado | `src/noesis/financial_history/schema.py` |
| Creado | `src/noesis/financial_history/service.py` |
| Creado | `src/noesis/financial_history/sources.py` |
| Modificado | `src/noesis/migrations.py` |
| Creado | `tests/financial_history_inventory_contract.py` |
| Modificado | `tests/payment_bank_capture_contract.py` |
| Creado | `tests/postgres_financial_history_inventory.py` |
| Modificado | `tests/test_financial_history.py` |
| Creado | `tests/test_financial_history_inventory.py` |

## 2. Migración

70 añade exclusivamente cuatro tablas propias, índices y triggers. Test de
catálogo verifica exactamente cuatro tablas añadidas y columnas anteriores intactas.
No cambios a62–69 ni a tablas financieras legacy. Downgrade con cualquier evidencia
se rechaza; vacío permite70→69→70. No epoch/fence ni nuevas Economic Operations.

## 3. Schema

| Tabla | Contenido |
|---|---|
| financial_history_manifests | tenant/run, modo, versiones, scope/código/copia/operador, tiempos, lifecycle/result, hashes/resumen |
| financial_history_items | source/clave/revisión/slot, raw/hash, assessment y ejes separados, plan/hash, deps resueltas/no resueltas, coverage/result |
| financial_history_incidences | item/código/severidad/evidence hash/regla/open/time, append-only |
| financial_history_decisions | incidencia/item/actor/permiso/kind/refs/razón/interpretación/antecedente/time, append-only |

SQL fuerza diagnostic, eligible_for_import=false y certifiable=false. FKs compuestas
tenant hacia manifest/item/incidencia/actor/antecedente. Raw inmutable desde inserción,
assessment una vez, ninguna eliminación de evidencia; índices propios por source/
clave ordenada y referencias.

## 4. Lifecycle de manifest

scanning→planning→frozen, separado de resultado READY_FOR_REVIEW/BLOCKED.
No READY_FOR_IMPORT ni validating. Freeze requiere clasificación terminada, hashes,
summary y timestamps; no permite alterar raw/plan/summary. Review posterior solo
agrega decisiones. Incluso READY_FOR_REVIEW conserva los tres invariantes SQL.

## 5. Readers

[Mapa previo completo](FASE-1.9B-fuentes.md), catálogo cerrado de28 kinds y campos
físicos permitidos. RawReader usa execute_exact de conexión prestada y business_id,
sin normalización legacy, nueva conexión ni commit/rollback. Servicio posee TX
por página. Keyset sin OFFSET creciente ni MAX(id). Scope anchor con solo ID del
negocio permite incidencias sobre conjunto inicial vacío. Sin locks/gate/fence.

## 6. Raw money extraction

Storage class, tipo/valor textual del driver, texto SQL, bits IEEE, float8sendPG
y Decimal.from_float exacto se conservan antes de diagnóstico. HALF_UP al céntimo/
delta son solo diagnósticos; nunca float→str→Money contractual. TEXT/NUMERIC exactos,
NULL distinto de cero, invalid/nonfinite/subcent/rango visibles. Umbral de residuo
max(2 ULP,1e-12) no acredita decimal original. SQLite NaN/signo perdidos al almacenar
se registran según estado físico observable, sin inventar el valor anterior.

## 7. Provenance de migraciones legacy

registro_anterior es migration_derived por11. Líneas/series33 y perfiles42/48
sin marcador individual quedan unknown/potencialmente retroasignados, nunca original
supuesto. Revisión64 es observada desde esa migración, sin reconstruir historia.
EE existente conserva provenance durable de ese hecho. Parecido con migración no
demuestra origen sintético si falta marcador.

## 8. Reglas de clasificación

classify puro/versionado: sin BD/LLM/proveedores. Assessment A/B/C/D,
disposition/severity/rule_id/version y14 códigos heredados. Mismo raw/contexto/regla
produce mismo resultado semántico. Dinero requerido exacto o corroborado conforme
a1.9A; cercanía al céntimo nunca basta. No se añadieron reglas que inventen
corroboración legacy. C/D sin candidato; B observed_state. Factura A hipotética
continúa bloqueada por contrato histórico v2 no soportado.

## 9. Tratamiento por cada source

| Source | Tratamiento |
|---|---|
| invoice borrador | B/out_of_scope; sin D/evento |
| invoice legacy | dinero/líneas/serie/perfil/fiscal; faltantes/contradicciones bloquean, sin nueva emisión |
| rectificativaR1–R5 | rectification, parent explícito o RECTIFICATION_PARENT_MISSING |
| payment | real/sintético, parent/fecha/método, acumulados/sobrecobro/duplicados; cobrada sin fila PAID_WITHOUT_PAYMENT |
| bank import | observado consistente; sin inventar cuenta/batch/row; v2 bloqueado |
| bank match | link durable/payment inequívoco; suggestion/confirmed sin link BANK_LINK_AMBIGUOUS |
| received_invoice | B condicional, pagada operativa, rev>1 SOURCE_HISTORY_LOST sin correcciones inventadas |
| expense | B condicional, IVA explícito o NULL; no IVA inferido ni restaurar borrados |
| cancellation | registro/huella/original/razón/fecha/invoice; total contexto, no devolución/deuda cancelada |
| líneas/series/perfiles/suppliers/records | contexto mínimo sin productor |
| documents/classifications | IDs/hashes/campos mínimos, sin contenido OCR/PDF/imágenes/conversaciones completo |
| invoice_events/transportes | evidencia auxiliar; no hecho financiero/remisión |
| recurring schedules/runs | procedencia; no mandato/autoridad supuestos |
| EE/links/coverage | verificación durable exclusivamente |
| scope_anchor | ID tenant, sin tipo económico |

No tipos nuevos ni supplier_payment.made/quote.accepted/job.completed. Los once
tipos aprobados permanecen cerrados; observación operativa no produce EE.

## 10. Existing coverage

Contrasta sobre/hash durable, negocio/type/source/revisión, amount/date/payload,
links/targets explícitos; invoice incluye líneas/partes/perfil/serie/fiscal.
Purchasing verifica antecedente/revisión y continuidad before/after disponible.
Coherent COVERED_EXISTING sin candidato/duplicado; conflict BLOCKED sin repair.
Identidad de dependencia conserva la revisión durable real de cobertura.

## 11. Candidate planning

Solo DiagnosticCandidate(HistoricalCandidate) en memoria y proyección del plan
en items. importable=false siempre. Identidad, tipo/versión/payload, basis/hash,
Decimal/string JSON, fechas/deps/hash. No nuevos EconomicEvent/FinancialOperation.
Tres v2 especiales heredados pueden mostrarse not_durably_supported, bloqueados,
sin soporte EE durable. Invoice histórico v2 sigue sin candidato soportado incluso
con dinero/líneas exactos en fixture. Bytes originales1.9A intactos.

## 12. Dependencies

Parents explícitos del mismo tenant, identidad/revisión disponible y assessment.
Padre A coherente no bloqueante puede satisfacer el contrato diagnóstico; B/C/D/
missing bloquean. UnresolvedDependency conserva tipo/ID conocido/razón cuando
falta revisión, sin inventar RevisionIdentity1. Match depende por separado de
import/payment; cancellation referencia invoice sin reversión económica.

## 13. Incidences

14 códigos aceptados, severidad/evidence hash/regla/open/time, identidad
idempotente por item+code. Incluye SOURCE_DRIFT/dinero/fiscalidad/historia/deps.
Append-only; frozen no admite nuevas incidencias del plan. Revisar exige otra
versión/manifest, sin borrado ni resolución silenciosa de evidencia.

## 14. Decisions

ReviewRecord cerrado y review interno: operador actual autenticado,
historical.record, razón/refs verificadas/interpretación/antecedente/time.
add_evidence/select_supported_interpretation/exclude/keep_blocked. Tenant/hash/
duplicados/refs requeridas/antecedente validados. Append-only/retry por UUID y
contenido. Sin financial.authorize/receipt/owner original supuesto; no cambia raw,
assessment, summary, plan ni bloqueantes por opinión manual.

## 15. Dry-run

HistoryDiagnostics(business_id,page_size=64).run(principal,manifest_uuid,
repository_version=...,environment_identity=...). API interna explícita sin router/
tool/scheduler/CLI/canales. Operador activo/sesión vigente, política de escritura,
tenant y cinco flags OFF por TX. Scan→planning→segunda lectura paginada→comparación
→freeze. Solo persistencia diagnóstica; ninguna producción/copia real.

## 16. Hashes

source_set_hash: scope/reader, catálogo/clave física ordenados, membership,
source/revision/raw hash; fila bank una vez aunque dos slots. plan_hash:
scope/versiones/items/raw/revisión/assessment/disposition/candidate hash/deps/
coverage/incidences/result ordenados. Alta/baja/modificación cambia hash.
InventoryEvidence/DiagnosticCandidate usan canonical propio sin observation time;
manifest lo audita. No cambia bytes1.9A. Decisiones no cambian hash inicial.
Drift detectado bloquea; ausencia detectada no acredita T0 ni cambios posteriores.

## 17. Idempotencia

UUID explícita identifica run lógico, nunca solo reloj. Retry mismo run/código/
copia/operador recupera frozen o reanuda scan/planning sin duplicar/sobrescribir.
Metadata incompatible falla; raw incompatible se conserva y genera drift.
Otra UUID pide diagnóstico intencional nuevo. Item UUID identifica ubicación/slot/
reader/tenant; HistoricalIdentity incluye revisión. Mismo contenido/regla produce
mismos hashes entre runs, sin convertir el plan anterior en importable.

## 18. Tests SQLite

38 pruebas nuevas (37 compartidas+AST) y39 puras anteriores: dirigida77 PASS
(108.323s) después del último ajuste de proyección inválida. Suite general local1709
PASS sobre el árbol final, incluyendo el formato SQLSTATE del test estructural.
Contratos afectados SQLite77 y matrizPG288 fueron reejecutados tras el guard.
Raw/clasificación/coverage/refs/SQL/tenant/freeze/hash/retry/crash/drift/privacidad/
sideeffects/migración. Ciclo separado vacío0→70→0→70 PASS.

## 19. Tests PostgreSQL

Matriz final288 PASS (131.586s), incluyendo37 nuevas, después del último
cambio funcional. PG16.15 localhost/noesis_ci descartable. Además32→70 con factura
legacy sintética,36 rutas calientes, código base53 sobre70, privacidad y rollback
vigente→55→54→53→54→55→vigente PASS. Nuevas pruebas limpio→70/vacío70→69→70 y
con evidencia downgrade denegado. Prueba69 ahora target69 explícito; DDL anterior intacto.

## 20. Performance

Fixture240 sources/página8: SQLite pico903760 bytes en dirigida; PG934489
bytes en matriz final;90 lookups agrupados por motor. Sin benchmark productivo.
Keyset/índices tenant/source/ref, consultas contextuales IN por lote; hashes/
incidencias finales paginados/agrupados. Máximo256 por lookup; overflow divide
lote, source individual excesiva queda C/incompleta. Sin SELECT auxiliar N+1
por source ni cargar todo el negocio en memoria.

## 21. Side-effect proof

Snapshots before/after de todas las tablas legacy/core/coberturas/outboxes,
Operations/Authorizations/canales/contador/negocio y flags. Solo cuatro history_*
cambian. AST impide imports/calls Capture/writers/services/AEAT/proveedores/escape
dinámico; clasificador sin BD/IA y readers sin conexiones/TX propias. Huella fiscal
existente solo contraste: ningún nuevo/alterado/reemitido XML/QR/registro/envío.
Regresiones live verificadas por separado.

## 22. Suite general/gates

Suite general local1709 PASS (1355.188s). PG288/Node9 PASS. Ruff src/tests, Bandit high/high,
secretos, project truth, uv lock, pip-audit sin vulnerabilidades, diff y495 enlaces
locales PASS en comprobaciones realizadas; gates de diff/estado se revalidan tras
cerrar documentación. HTTP local /health,/ready,/,/login200. Publicación/CI remoto
se acreditan aparte; producción no consultada/despliegue no verificado.
La suite general local se ejecutó tras todos los cambios funcionales. El cambio
final de espacios en SQLSTATE no altera DDL; test estructural3 PASS y PostgreSQL
comprobado de nuevo. CI de implementación [f474d42](https://github.com/noesisstudio/noesis/actions/runs/37137042961) SUCCESS: general1709
(582.266s), PG288 y todos los gates. La adenda final cambia solo documentación.

## 23. Decisiones, diferencias y riesgos

Concreciones aprobadas: lifecycle separado de result, scope anchor, canonical
semántico propio, revisión no resuelta explícita. Nombres físicos corregidos a
document_profiles/received_invoices/bank_*_coverage. Sin diferencia de alcance
autorizado ni regla económica nueva. FASE-1.9-plan es la síntesis aprobada durable;
el diseño inline original completo no existía como archivo adicional independiente.

Sin fence puede no detectar cambios posteriores y jamás certifica corte. Binario
legacy puede carecer del decimal original; no falsear exactitud. Contextos
individuales>256 bloqueados conservadoramente. Retención final1.10/copia real1.9F
requieren fases posteriores. Rollback operativo retira acceso conservando filas;
downgrade70 con evidencia está prohibido. La baja de cuenta con inventario usa el
rechazo controlado existente de conservación, sin borrar evidencia ni resolver
retención/purga final1.10. Regresiones de baja sin historia mantienen su comportamiento.

Descubierto defecto PREEXISTENTE en downgradePG29: DROP TRIGGER sin ON impide bajar
más allá de29. No modificado; fuera de1.9B. Ciclo70→69→70 y rollback53 PASS.
Cinco flags OFF. Sin epoch/T0/fence/v2durable/importer/historical coverage/
reconciliación final/activación ni1.9C.

## 24. PASS/FAIL individual

Uno a uno con los47 apartados de la orden.

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Base main y mapa previo | PASS | gobernanza/código/schema69 y mapa previo |
| 2 | Inventario sin efecto | PASS | contrato integrado/snapshots |
| 3 | No certificable/importable | PASS | CHECKs SQL/candidato false |
| 4 | Migración70 acotada | PASS | delta exactamente cuatro tablas |
| 5 | Inmutabilidad | PASS | triggers/update/delete/review ambos motores |
| 6 | Readers prestados | PASS | execute_exact/guard estructural |
| 7 | Fuentes completas | PASS | catálogo28/mapa/zero counts |
| 8 | Fila distinta de item | PASS | bank import/match y auxiliares |
| 9 | Paginación | PASS | keyset/page8/contexto agrupado |
| 10 | Evidencia física monetaria | PASS | tipo/texto/bits/decimal/delta |
| 11 | Dinero acreditado | PASS | reglas1.9A/binary/subcent bloqueados |
| 12 | Provenance retrospectiva | PASS | 11/33/42/48/64 y UNKNOWN |
| 13 | Existing coverage | PASS | contraste durable/coherente/conflict y payload inválido solo hash |
| 14 | Invoice/draft/fiscal | PASS | draft B/out_of_scope y faltantes/mismatch |
| 15 | Invoicev2 bloqueado | PASS | fixture exacto not_durably_supported |
| 16 | Rectificativa | PASS | R1–R5/parent explícito/missing |
| 17 | Pagos | PASS | real/sintético/status/sobre/duplicado |
| 18 | Banco import | PASS | sin inventar cuenta/batch/row |
| 19 | Match bancario | PASS | link válido/suggestion sin link |
| 20 | Recibidas | PASS | B condicional/rev3/unknownVAT |
| 21 | Gastos | PASS | B condicional/subcent/NULL |
| 22 | Cancellation | PASS | hash/original/dependencia/no reversión |
| 23 | Document/OCR | PASS | proyección mínima sin promoción |
| 24 | Recurring | PASS | procedencia sin mandato/productor |
| 25 | Clasificador | PASS | puro/versionado/determinista |
| 26 | Candidate | PASS | HistoricalCandidate/importable=false |
| 27 | Dependencies | PASS | A/B/C/D/missing/revisión real |
| 28 | Incidences | PASS | catálogo14/hash/tenant/idempotencia |
| 29 | Decisions | PASS | append-only/refs/razón/actor/previous |
| 30 | Dry-run interno | PASS | API explícita/snapshots |
| 31 | Guard de efectos | PASS | AST y contraste runtime |
| 32 | Drift | PASS | bloqueo incluso conjunto inicial vacío |
| 33 | source_set_hash | PASS | membership/identity/revision/raw ordenados |
| 34 | plan_hash | PASS | versiones/items/deps/incidencias/review |
| 35 | Retry/new run | PASS | UUID explícita/crash/nuevaUUID |
| 36 | Multiempresa | PASS | scope/FKs/referencias ajenas rechazadas |
| 37 | Permiso actual | PASS | historical.record/sesión/política escritura |
| 38 | No operación/auth/EE | PASS | snapshots/guard sin soporte nuevo |
| 39 | Migraciones seguras | PASS | limpio69→70/vacío70→69→70/evidencia bloquea |
| 40 | Fixtures inventory | PASS | contrato compartido37 por motor |
| 41 | Raw money matrix | PASS | TEXT/NUMERIC/REAL/DOUBLE/NULL/NaN/Inf/rango |
| 42 | Manifest tests | PASS | hash/retry/SQL/decisions/tenant |
| 43 | Cero efectos | PASS | legacy/core/outboxes/flags intactos |
| 44 | Performance | PASS | 240sources/page8/90lookups/bounded memory |
| 45 | Sin producción | PASS | solo TEMP/PG16localhost/noesis_ci |
| 46 | No1.9C | PASS | sin epoch/T0/fence/validating/live boundary |
| 47 | No1.9D+ | PASS | sin durablev2/importer/historical coverage/activation |

47 criterios PASS, 0 FAIL. Autoauditoría18 respuestas. Implementación publicada en main y CI remoto SUCCESS; código y tests del commit
validado permanecen idénticos en la adenda documental.

## 25. Autoauditoría requerida

1. ¿Dry-run escribe EE? No; sin import/llamada de servicio ni DML a EE.
2. ¿Crea Operations? No; no servicio ni DML propio para operaciones/autorizaciones.
3. ¿Toca legacy? No; solo SELECT y contraste, probado con snapshots.
4. ¿Puede parecer certificable? No; tres invariantes SQL y candidato importable=false.
5. ¿MAX(id) cutoff? No; keyset solo pagina y hash cubre miembros/contenido.
6. ¿Raw cuantiza antes de conservar? No; driver/bits/decimal exacto preceden diagnóstico.
7. ¿registro_anterior es A solo? No; D/SYNTHETIC_LEGACY_PAYMENT salvo cobertura verificada explícita.
8. ¿Cobrada inventa payment? No; PAID_WITHOUT_PAYMENT sobre evidencia de ausencia.
9. ¿Suggestion inventa match? No; BANK_LINK_AMBIGUOUS si no hay link inequívoco.
10. ¿Revisión64 inventa pasado? No; observado, sin correcciones reconstruidas.
11. ¿OCR/document productor? No; auxiliares sin candidato ni autoridad.
12. ¿Duplica coverage? No; COVERED_EXISTING sin candidato, no writer/append.
13. ¿C/D candidato importable? No; sin candidato; todos los diagnósticos importable=false.
14. ¿B se vende verified? No; payload/evidence_basis observed_state y fechas NULL explícitas.
15. ¿Decisión reescribe evidencia? No; append-only, plan/hash/clasificación intactos.
16. ¿Queries cross-business? No; negocio en SELECT/FKs/refs/actor. Schema metadata global no es source.
17. ¿Producción? No; solo fixtures descartables locales, sin Railway ni copia real.
18. ¿1.9C iniciada? No; sin epoch/T0/fence/write blocking/validating/live boundary.

Autoauditoría adicional: forma inválida de payload EE o snapshot de cobertura no
interrumpe el scan ni copia contenido libre. Se guarda hash, se bloquea la cobertura
incoherente y se preserva la fuente. Fixture malformado verificado en ambos motores.
