# Matriz futura de revalidación — NO EJECUTADA

[Contrato](SCHEMA-LINEAGE-75-80-contract.md), [mapping](SCHEMA-LINEAGE-75-80-mapping.md),
[hash-impact](SCHEMA-LINEAGE-75-80-hash-impact.md), [orden posterior](SCHEMA-LINEAGE-75-80-implementation-order.md).
Cada ID describe una obligación nueva; PASS anteriores siguen históricos.
SQLite y PostgreSQL18 significan fixtures descartables, sin datos reales y con
outbound bloqueado. No se ejecutan estas pruebas funcionales en la fase de diseño.

## Identidad, objetos, migrador y runtime

| ID | Fixture/acción futura | Resultado exacto esperado | Motor |
|---|---|---|---|
| L01 | Namespace vacío, metadata ausente, bootstrap explícito0→80 | Todas80 identidades, perfiles y hash80 exactos; flags OFF | Ambos |
| L02 | Prefijo canónico73→80, datos sintéticos históricos | CRM74 primero, A75..F80, fuente/evidencia anterior conservada | Ambos |
| L03 | CRM74→80 con datos CRM/supresiones | Fila74/name/applied_at y datos preservados;80 canónico | Ambos |
| L04 | Cada target canónico75,76,77,78,79,80 desde su anterior | Callback único/precondición real/postperfil exacto | Ambos |
| L05 | LegacyA74,B75,C76,D77,E78,F79, seis fixtures separados | LEGACY_FINANCIAL_LINEAGE_DETECTED antes de cualquier DDL/DML | Ambos |
| L06 | Legacy sentinel74 con gap/mixed names/filaCRM extra | Legacy detectado +integrity CORRUPT; cero repair/promoción | Ambos |
| L07 | unknown74/wrong name en cada fila1..80 | MIGRATION_IDENTITY_MISMATCH, no continuar por MAX | Ambos |
| L08 | Gap en1..80, duplicados, versión0/negativa/float/bool/null | Error cerrado gap/metadata; no autoinsert | Ambos |
| L09 | Future81 con prefijo80 correcto | FUTURE_SCHEMA_UNSUPPORTED, no downgrade ni ignorar81 | Ambos |
| L10 | Metadata ausente/vacía con objetos Noesis; columnas/name/applied_at faltantes | SCHEMA_METADATA_INCOMPLETE, sin init_db | Ambos |
| L11 | Registry75/80 correcto pero falta tabla/columna/FK/CHECK/trigger/function | SCHEMA_OBJECT_MISMATCH; no servir ni efectuar writes | Ambos |
| L12 | Registry74 con tablas A preexistentes o etapas futuras | Bloqueado, no adopción IF NOT EXISTS | Ambos |
| L13 | Orden de filas diferente; mismos pares; applied_at diferente válido | Fingerprint igual; inventario de filas puede diferir | Ambos |
| L14 | Cambio de nombre/versión/gap/extra/nombre con delimitadores/Unicode distinto | Hash distinto o rechazo estricto; no trim/normalización | Ambos |
| L15 | Binding JSON arbitrario/hash correcto pero DB diferente | Recompute+perfil/tenant/environment/code rechazan | Ambos |
| L16 | Copias con misma lineage, datos/env diferentes | Fingerprint igual, jamás hereda authority/env/EMPTY | Ambos |
| L17 | Startup normal80 sobre74/75..79/legacy79/future81 | Ready503; ningún scheduler/writer/initDb/migration | Ambos |
| L18 | Bridge sobreCRM74 y canonical80 completos | Ready según política bridge; conserva estado/guards; no provider I/O | Ambos |
| L19 | Bridge sobre75..79/legacy74..79/mixed/unknown | Fail closed, no fallback; intermediarios no habilitados | Ambos |
| L20 | Migrador propietario74 sobre80 y runtime propietario80 sobre74 | Propiedad ≠ compatibilidad; rechazar writes/serving no declarado | Ambos |
| L21 | Retry target ya aplicado exacto | ALREADY_AT_TARGET, no writes; precondición distinta no-target PLAN_STALE | Ambos |
| L22 | Rol runtime intenta registry/DDL; raw owner cambia metadata en TX antes de writer | Privilegios y guards SQL bloquean; binding drift detectable | PG18+SQLite guards |

## Locks, crashes y downgrade

| ID | Ejercicio futuro | Criterio |
|---|---|---|
| X01 | Dos procesos upgrade simultáneos a80 con claves independientes deSHA | Una TX DDL; segunda revalida y no-op exacto tras commit |
| X02 | Up y down concurrentes mismaBD | Misma clave exclusiva; nunca estados intercalados |
| X03 | Lock retenido >30s / aplicación retiene shared | Timeout sin DDL/metadata ni terminación de sesiones |
| X04 | Crash despuésDDL antesfila; despuésfila antescommit; entre etapas75..80 | Rollback completo, lock liberado, registry/objetos coinciden origen |
| X05 | Failure inyectado a cada callback, postvalidator y commit | Ningún partial applied visible; retry desde identidad exacta |
| X06 | Registry SHARE antes de snapshot/service gate vs migration advisory+registry exclusivo; TX READ ONLY/RR y lock tardío | Sin inversión/deadlock/stale; SHARE antes de SELECT, lock tardío rechaza SCHEMA_TX_PROTOCOL_REQUIRED |
| X07 | Pool devuelve/reutiliza conexión tras error/crash | Sin session-lock filtrado ni estado de contexto antiguo |
| X08 | SQLite dos conexiones BEGIN IMMEDIATE/busy timeout | Serializa prefijo antes de leer, sin doble BEGIN o commits internos |
| X09 | DB sintética vacía80→74→80 y cada paso abajo/arriba | Perfiles exactos, FKs activas; residuos SQLite explícitos sólo en QA |
| X10 | Cada A–F poblada, ever_enabled, grants, receipts, UNKNOWN o supresiónCRM | Downgrade protegido; conservación byte/hash íntegra |
| X11 | Bajada falla en segundo paso | Revierte también primer paso y sus filas |
| X12 | Cliente anterior no usa lock / old predeploy todavía activo | Release gate bloqueado; no alegar serialización global |

X01–07/X12: procesos PostgreSQL18 reales sintéticos, conexiones distintas y
barreras/crash hooks; X08: SQLite real, no mocks. Tests no cambian roles productivos.

## Contratos, hashes y dominios

| ID | Área | Criterios de revalidación |
|---|---|---|
| D01 | A75 y A80 | SQL físico real75/80+binding; proofs/result2; FULL/PARTIAL/BLOCKED/TTL, cero efectos, privacy_not_ready |
| D02 | B76/B80 | A realmente instalada; evidence2 every_use, unknown/quality conservados, cross-tenant y races |
| D03 | C77/C80 | Spec1/closure iguales, B2 exacta, coverage/result/EE amountNone y atomicidad; no AEAT |
| D04 | D78/D80 | Baseline nuevo, grants/generations/origin/fence/receipts, autorización humana exacta, SQL final guard |
| D05 | E79/E80 | Policy provisional no-ready, export snapshots/catálogos por capability, closure/retention/erasure/replay |
| D06 | F80 | Levels/env/HMAC/TTL, exact binding/preflight, attempts/results, UNKNOWN no retry, pause/closure |
| D07 | G80 | Context2/binding80, sealed proofs, origen confiable, synthetic!=REAL, no auto-authority/main-review |
| D08 | Resume continuidad80 | A expirada sólo arco allowed, G+1; perfil/grants/history originales; drift/UNKNOWN/actor stale/privacy bloquean |
| D09 | Golden legacy1..79 | Bytes y hashes originales iguales; nuevo reader no añadeS ni recalculaapproved_hash |
| D10 | Hash matrix completa | Cada fila del hash-impact con caso de conservación, caso nuevo y rechazo de reuse |
| D11 | Contract/canonical versions | Extra fields/desconocidos/bool-as-int/float/NaN rechazados; Money/EE/Profile/spec/history versiones sin renumeración |
| D12 | History70/71/72/73/CRM74/A75..F80 | Cada tupla mínima/máxima exacta y rechazo de cada legado74..79; sin source/hash promotion |
| D13 | Sources y evidence antigua | A/B/history/EE/Operations/receipts existentes idénticos después de migrar, incluso >500rows/1000EE |
| D14 | Post-handoff OFF/pause/closure | Nada de nuevo efecto ni legacy fallback; SQL raw también bloqueado |
| D15 | Tenant/session/capability/connection/TX | Binding de otrotenant/otraTX/gen stale no válido; no conexión/commit propio |

## Backup, restore, bridge y seguridad

| ID | Caso futuro | Resultado |
|---|---|---|
| R01 | NativeV2 nuevo:CRM74, intermedios, canonical80 | Dump/docs/manifest identity2/objetos/filas/secuencias exactos, sin migrations |
| R02 | NativeV2 viejo73/legacy79 sinidentity | Integridad original, derived identity aislada; no nuevo manifest ni serving/G |
| R03 | Native80 con fila equivocada/hash manifesto false/gap/objeto ausente | Rechazo; no editarregistry para hacer match |
| R04 | V1 schema73, CRM74, legacyFinancial79 | Runner exacto/offline metadata; legacy79 no canonical79; unknownmetadata rechazada |
| R05 | D78 vs E79 vs F80 vs legacyE78 vs unknown | Capability privacy precisa; replay obligatorio cuandoE, legacy/unknown no servir |
| R06 | Replay despuésrestore con supresiones posteriores albackup/cierre | Registro vigente manda; tombstones/bloqueos antiguos intactos; no resurrección |
| R07 | Native locale/extensions/DDL/triggers/verifier key/data/sequence/docs | Integridad completa/secret exclusion, aislamiento; no equivalencia sólo counts |
| R08 | Bridge runtime sobre74 antes y80 después, state ever_enabled0/1 | Sin migrations automáticas, guards preservados, rollback operacional compatible |
| R09 | Intento external UNKNOWN y committed resultado trasrestore/rollback | No auto-retry/reissue ni éxito/rechazo artificial; no EE por resultado |
| R10 | Rutas HTTP/auth/privacy/account deletion y workers/scheduler | Ready/config correctos, no providers; separación ownership/runtime |
| R11 | CI stale-main/collision/changed-name/gap/deletedmigration/modifiedhistoricalDDL | Gate falla; cambios nuevos sólo después latestmain; baseline no regenerable sinreview |
| R12 | Package/data y railpack/toolchain V2 | CRM templates/static/local_dates actuales +PG18 y runner A–G preservados |

## Gates de cierre de implementación futura

Una ejecución fresca **única** del SHA final: suite general Python/SQLite completa,
0FAIL/0ERROR, duración y recuentos por invocación, Node completo (incluido
local_dates), todos los jobs PostgreSQL18: Core, Operations/Auth, EE, borrowed
writers, InvoiceCapture, Payment/Bank, Supplier/Expense, Channels, History
inventory/cutoff/import/reconciliation, A/B/C/D/E/F/G, lineage/locks, V1/V2,
HTTP/release/legacy smoke. No sumar segmentaciones como suite fresca.

Dos skips heredados PG sólo si se identifican exactamente y pasan en PG18. Un
skip POSIX V2 en Windows exige prueba equivalente Linux; no omitirlo en CI Linux.
Reportar lo que runner realmente ejecutó, no prefijar conteos futuros a los viejos.

Ruff, Bandit, credential scan, dependency audit, ciclo de migraciones sintético,
AST/baseline historical1–74, documentation truth/links, diff y matriz rollback.
Contrastar que CI V2 port no suprima ninguna matriz A–G cuando éstas se integren.
Todo synthetic; restore real/drill, GO/NO-GO y deployment son fases separadas.

Validación **de esta entrega documental**: links relativos, JSON de diseño,
nombres1–74 contraAST main678, mapping75–80, fingerprints/golden reproducibles,
checks de coherencia entre documentos, estado compartido, diff sin código,
preservación de historial/V2, autoauditoría37 requisitos. No D01/R01 ejecutados.
