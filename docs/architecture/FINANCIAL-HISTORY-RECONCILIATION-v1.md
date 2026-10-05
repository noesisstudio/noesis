# Financial History Reconciliation v1

Orden: [1.9E](FASE-1.9E-orden.md). Decisión: [ADR018](ADR-018-financial-history-reconciliation.md).
Entrega interna, sin endpoint, tool, CLI, scheduler ni autoridad de IA. No1.9F.
`inventory certifiable ≠ import completed ≠ reconciliation PASS ≠ production rehearsal ≠ activation`.

## API y frontera de transacción

`HistoryReconciliation(business_id, page_size=64)` admite páginas de1 a64.
`reconcile(principal, epoch_uuid, manifest_uuid, batch_uuid, reconciliation_uuid,
reconciliation_version=1)` exige UUID válidas y versión entera1. `read(principal,
reconciliation_uuid, after="")` devuelve resultado y findings paginados por hash.
La lectura exige permiso y sesión actuales incluso después de revocar el epoch.
Ningún resultado concede permisos ni cambia elegibilidad.

Schema73; operador actual con historical.record, sesión/suscripción/tenant vigentes,
cinco flags OFF, epoch fenced/control generation actual, boundary_current,
C frozen/certifiable/eligible_for_import=false y scope/hash/comparison/plan
coherentes. Batch completed/partial/blocked; prepared/running o recording rechaza
antes de crear el run. Se conserva la política opened_by de C/D.

Una TX exterior prestada por `get_conn`/`FinancialSession`: gate común antes del
lock de usuario/negocio. SQLite BEGIN IMMEDIATE; PostgreSQL advisory por negocio
y FOR SHARE. Repositorio E únicamente INSERT run/findings y UPDATE running→frozen.
No commit/pool/ORM propio. Revalida permisos y frontera antes de sellar. Release e
invalidate se serializan; si ganan antes de E, E se rechaza. PASS nunca libera fence.

## Persistencia y lifecycle

Migración73 añade solo `financial_history_reconciliations` y
`financial_history_reconciliation_findings`. No modifica63–72. B/C/D admiten73.
Run: tenant/UUID/epoch/generation/manifest/batch/version, operador/session_version,
started/completed, running/frozen, PASS/BLOCKED, seis hashes y result_hash/canonical.
FK compuestas a epoch, batch/manifest y operador. Solo un running por negocio/batch;
varias UUID frozen admisibles. Identidad del run inmutable, frozen sin UPDATE/DELETE.
Findings únicamente discrepancias: item_uuid nullable global, code/severity blocking,
version1, expected/actual hash/ref mínimos, canonical/hash, created_at y UUID estable
derivada de run+hash. Sin texto libre, payload duplicado, éxito por item ni PII nueva.
INSERT solo en run running; no UPDATE/DELETE; FK tenant/manifest/item.
Nuevo guard73 prohíbe reabrir batch terminal como prepared/running. Retry D de un
resultado ya existente sigue permitido; E no modifica D.

Running y frozen ocurren en la misma TX. Crash precommit revierte todo E, retry
reinicia. Pérdida de respuesta postcommit recupera frozen exacto. Misma UUID con
otro contexto/hash/version es conflicto. Retry reaudita estado actual sin escribir
findings: si difiere del resultado sellado, conflicto y otra UUID para nuevo run.
`read` conserva la evidencia anterior; verifica canonical/columnas/hash del run y
del conjunto paginado de findings. Downgrade vacío73→72→73 permitido; con cualquier
evidencia E se bloquea para toda la base. Retención también en baja de negocio.

## Algoritmo y PASS

1. Recalcular fuente congelada y plan B sin modificar incidencias. Decodificar raw,
   revisiones, candidato/assessment/dependencias/coverage, hashes y tenant.
2. Paginar todos los EE del negocio por (business_sequence,id), cargar por lotes
   links, operaciones, autorizaciones, proofs recorded y cadena original B/C/D.
   Verificar StoredEvent completo, columnas nativas, contenido y record hash.
3. Indexar identidad source/type/revision/event_type y detectar duplicados. Los
   huecos del id físico son legítimos; business_sequence debe ser positiva y
   consecutiva, con contador coherente. Nunca renumerar.
4. Cada candidato y covered_existing debe tener resultado terminal correcto:
   estado/completion_key/canonical/UUID/hash/manifest/raw/candidato/operación/auth.
   Fuera de ámbito/excluido puede no producir resultado; si lo produce, skipped
   coherente y sin evento, ni evento económico inesperado para el hecho excluido.
   C/D, incidencias bloqueantes y pendientes necesarios impiden PASS.
5. Cada histórico debe conservar proof recorded original único: identidad/UUID,
   batch original, contenido esperado, raw/candidato, fechas/provenance, secuencia,
   request exacto, operación histórica PREPARED sin resultado/committed_at y una
   historical_unknown con actor/session NULL, registrador, historical.record y
   canal históricos exactos, sin mandato/expiración/revocación. HUMAN/MANDATE o
   APPROVED/COMMITTED bloquean. También buscar huérfanos fuera del batch actual.
6. Existing y covered_existing históricos preservan batch/observación/proof original;
   no exigir batch actual ni reappend. Covered live exige evento/origen/hash/source/
   revisión/links exactos y cobertura/autorización/operación live COMMITTED válidas.
7. Releer TODAS las fuentes de scope C por RawReader, sin normalización a float.
   Validar cada fila live coverage y relacionarla con evento real. Cubre documentos,
   perfiles, fiscal, transportes según exclusiones C, recurrentes, EE y links.
8. Contrastar dependencias congeladas con relaciones exactas; padres A y evidencia
   válida, nunca B. Padre live requiere cobertura real; padre histórico proof válido.
   Detectar missing/extra/wrong/cross-tenant/huérfanos y ciclos con Kahn O(N+E).
9. Congelar BLOCKED si hay una sola discrepancia; PASS únicamente con todas las
   identidades explicadas. Las counts no sustituyen ningún control.

El estado D partial por antiguo `not_durably_supported` de los tres v2 cerrados
puede PASS cuando TODOS estén efectivamente incorporados/explicados y no quede
ningún impedimento. No se reescribe el resultado de C/D. Partial con candidato
pendiente y batch blocked dan BLOCKED. Histórico invoice v2 continúa bloqueado;
factura live v2 preexistente es válida por el contrato de captura.

## Scope, dinero y fiscal

C contiene EE/links. D agrega legítimamente EE/links después del corte. E escanea
el conjunto físico completo y reproduce `source_recheck_hash` del conjunto C:
solo separa las nuevas filas EE/link que tengan proof D válido Y explicación en
el manifest actual. No se excluyen fuentes de C; cualquier otra alta/baja/cambio
es SOURCE_DRIFT. El delta autorizado queda comprometido en event_set_hash. Un
nuevo inventario incluye los EE anteriores, que ya deben coincidir con su raw.

Decimal/NUMERIC/TEXT canónico y JSON monetario string; sin nuevos float, SUM/CAST
binarios ni redondeo para reconciliar. Raw binary se conserva como bits/evidencia
diagnóstica y nunca se convierte en Money acreditado. Raw→evidencia de candidato→
payload/evento exactos; NULL/unknown nunca se sustituyen por cero ni por fecha de
observación. Supplier/expense B mantienen observed_state. El hash de registro
diagnóstico tolera representación legacy nativa como evidencia de almacenamiento,
incluidos timestamps sin zona, sin inventarle zona.

Fiscal: referencias/hashes/tipos/versiones/identidades congeladas y fuente real.
Reader fiscal usa validación congelada y jamás invoice_record_hash ni
cancellation_record_hash durante E. No genera XML/QR/registro/outbox ni llama a
AEAT/proveedor. Bank matched conserva el importe de evidencia y links matches a
payment/evidence_for a import; impacto exclusivo Evidence. No es segundo cobro,
posting ni reporting. No agregados financieros nuevos.

## Hashes

Canónico propio v1 (no firma ni RFC8785). source_set/plan son los congelados B/C.
import_set: semilla financial-history-import-v1 y filas ordenadas por item UUID:
item_uuid, identity_hash, candidate_hash, state, event_uuid, content_hash,
record_hash, operation_uuid, authorization_uuid. event_set: semilla events-v1,
EE ordenados y hash físico completo de evento/operación/auth/proofs más links
ordenados; incluye operaciones históricas y unknown globales para detectar huérfanos.
source_recheck: mismo algoritmo C y proyección explicada arriba. Findings: semilla
findings-v1 y hashes semánticos ordenados, excluyendo UUID/timestamps propios E.
Result compromete versión, negocio, epoch/generation, manifest, batch, seis hashes
y PASS/BLOCKED. Cambiar contexto o dato relevante cambia hash o bloquea; mismo
estado y contexto con otra UUID E produce result_hash idéntico.

## Catálogo cerrado

SOURCE_DRIFT, MANIFEST_INCONSISTENT, BATCH_NOT_TERMINAL, IMPORT_ITEM_MISSING,
IMPORT_ITEM_UNEXPECTED, IMPORT_RESULT_CONFLICT, EVENT_MISSING,
EVENT_CONTENT_CONFLICT, OPERATION_CONFLICT, AUTHORIZATION_CONFLICT,
DEPENDENCY_CONFLICT, EXISTING_COVERAGE_CONFLICT, UNEXPECTED_HISTORICAL_EVENT,
LIVE_COVERAGE_CONTAMINATION, SEQUENCE_CONFLICT, FISCAL_REFERENCE_CONFLICT,
BLOCKING_HISTORY_REMAINS. Todos blocking. BATCH_NOT_TERMINAL se rechaza normalmente
como precondición antes de crear run. Code/version desconocidos se rechazan.

## Escala y límites

Payload/raw por páginas; índices de metadatos/hashes/edges O(N+E), no payloads de
toda la base. Lookups agrupados, SQL tenant e índices batch/items/event source y
secuencia. Findings se deduplican por hash; read paginado. TX única puede retener
el gate durante un scan grande y SQLite serializa writers globales: medición
sintética, no SLO productivo. Las garantías no equivalen a resistencia frente a
un administrador que falsifique coordinadamente todas las fuentes y hashes.
No producción, restauración real, Railway, backups descargados ni1.9F/activación.

La autoridad durable del padre live exige namespace/canal no históricos, actor y
session presentes, registrador y permiso coherentes con HUMAN/MANDATE, además del
request/hash y operación COMMITTED. Se conserva la aprobación original: revocarla
posteriormente no convierte un hecho ejecutado correctamente en histórico unknown.
