# A75 CORRECTIVE #2 — REMOTE VALIDATION PENDING

[Orden](FASE-1.10A75-corrective-2-orden.md). Parent b3a93361; main reservado678bd3f.
Sólo cuatro bloqueos del run38539348109. Un commit, push normal de la feature y
workflow_dispatch nuevo completo; no rerun ni segundo correctivo si falla.

## Cambios y diagnóstico

- Baseline: UNA entrada nueva exacta para el SHA Git público failed_candidate_sha
  de docs/project-state.json, Hex High Entropy String; hashed_secret
  08bf2bad71eb7da2c5761c9c7fe6efdcf3272e4e, is_verified=true/is_secret=false.
  Resto de entradas, detectores, filtros y thresholds intactos.
- Scanner CLI se reejecuta en Python UTF-8 cuando no está habilitado; CI usa
  -X utf8 explícito. Regresión JSON con caracteres no ASCII y hash temporal
  desconocido, modos UTF8=0/1: ambos detectan sin imprimir el valor. Mismo detector.
- Runner prepara cada DB propia de stage3 y17 con upgrade75 y checker SELECT
  require_runtime + registry completo exacto74CRM/75A, antes de smoke.
  Stage17 hace además su propio HTTP smoke antes de privacy/release. Ante fallo
  de upgrade/identidad no lanza smoke/contrato. Veinte OIDs separados conservados.
- Cutoff: sólo query pg_stat_activity con dos LIKE parametrizados. Se conservan
  espera real dentro de función VOLATILE, query_start anterior a T0, apertura,
  liberación, HistoricalFenceActive y ausencia de fila. Sin cambiar tiempos/guards.
- V2: archive75 poblado se restaura a target75 nuevo ANTES de future/hstore.
  Unknown archive tiene destino separado. Source/expected/restored public se
  comparan antes de require_runtime; diferencias sólo object key/tipo/hashes
  de descriptor normalizado. No SQL crudo ni payload/filas/DSNs en diagnóstico.
  Canonical verifica binding/hash/body/context/capabilities y control off/0/false,
  ausencia future/hstore y EE/Operations. Unknown conserva inventario completo.
  Ambos siguen NO_E_INSTALLED, serving=false, g_real_evidence=false.
  FIXTURE COUPLING sólo podrá declararse tras PASS dedicado. Si canonical difiere:
  STOP/BLOCKED con hashes, nunca modificar producto/profiles/normalización/restore.

## Evidencia previa y validación pendiente

Run38539348109 bloqueado: fullPython2011/2009PASS/2skips/0FAIL/0ERROR,
PG20 etapas/16PASS/4FAIL,514 casos/512PASS/2ERROR. No heredar esos resultados.
Controles locales correctivos:8PASS/6.956s,0FAIL/0ERROR. Checks PG dirigidos no
disponibles en Windows; no reparar/reintentarWSL. CI Linux18.6 autoritativa pendiente.
Readiness/lineage/collision/correctivos:64PASS/174.818s,0FAIL/0ERROR.
BackupV2/identity locales:31 casos/30PASS/1skip POSIX en Windows/3.897s; no prueba
roundtrip PG. Secret scan completo UTF8 y delta stagedPASS, Ruff/Bandit HIGH/HIGH,
dependencias, AST/collision, truth, diff y760 enlaces/0rotosPASS.
Receipt final exacto SHA/run/recuentos queda FUERA de Git; no otro commit documental.

## Freeze, autoauditoría y riesgos

Cero archivos src/noesis cambiados respecto al parent. SOURCE_DRIFT correctivo1,
startup, locking, guards, perfiles físicos, migration75 y contratos A intactos.
No autoDDL, nuevo pool/TX, autoridad IA, relajación de tenant o secret sensitivity.
Objeto/trigger extra owned sigue rechazado. Backup técnico no concede serving.
Cinco flags OFF y policy REAL provisional/PRIVACY_NOT_READY intactos.
Riesgo abierto: runtime canonical restaurado todavía exige diagnóstico PG fresco.
Sharp HIGH: SEPARATE SECURITY DEBT / PRE-PRODUCTION TRIAGE REQUIRED, sin cambio.
Sin main/merge/deploy/producción/Railway/QA/backups reales/providers/business15,
B76–F80/bridge/G-LIVE/H. Rollback sólo revert autorizado; no rewrite.
PASS final sólo General SUCCESS + PG SUCCESS +20/20PASS +0FAIL/0ERROR,
únicamente dos skips históricos cubiertos enPG. Cualquier otro fallo bloquea sin
nuevo commit automático. Estado actual: REMOTE VALIDATION PENDING.
