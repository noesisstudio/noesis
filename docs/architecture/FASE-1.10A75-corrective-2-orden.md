# 1.10A75 — CORRECTIVE #2 / FINAL CLOSURE
# CERRAR LOS 4 BLOQUEOS RESTANTES DEL SHA b3a93361
# NO REDISEÑAR A75 / NO RELAJAR GUARDS / NO B76

ESTADO AUTORIZADO

Branch:

codex/phase-1-10a75

Current HEAD:

b3a93361975693a157cf3874346dcfa456ce7162

Padre:

f5150b27076ab5725bae436fba781095a0a9c0ee

origin/main esperado:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

CI bloqueada:

run 38539348109

Estado:

1.10A75 CORRECTIVE STATUS — BLOCKED

---

OBJETIVO

Resolver EXCLUSIVAMENTE los cuatro bloqueos restantes:

1. falso positivo documental de secret scan;
2. preparación explícita canonical75 de stages PostgreSQL 3 y 17;
3. instrumentación Psycopg del test cutoff;
4. diagnóstico y cierre correcto de V2 populated A75 restore.

Después:

crear UN único commit correctivo,
push normal a la misma feature branch,
y ejecutar CI fresca completa.

Sólo si TODO queda verde:

1.10A75 REMOTE CODE-VERIFIED PASS.

---

# 1. FREEZE DE A75

NO modificar:

- migration75;
- Financial Readiness contracts;
- evaluator;
- repository;
- schema lineage semantics;
- migration locking protocol;
- activation state semantics;
- startup productivo;
- guards de objetos;
- cinco flags;
- providers;
- A–G históricos.

El único código de producto actualmente añadido por corrective1
para SOURCE_DRIFT está CONGELADO.

No tocarlo salvo que una nueva prueba demuestre regresión.

SOURCE_DRIFT ya está probado en SQLite y PostgreSQL.

---

# 2. REVALIDAR MAIN

Antes de cualquier cambio:

origin/main debe seguir exactamente:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

Si ha cambiado:

DETENTE

MAIN_DRIFT

No rebase.
No merge.

---

# 3. SECRET SCAN — FALSO POSITIVO SHA PÚBLICO

Finding actual:

docs/project-state.json

campo:

failed_candidate_sha

valor público:

f5150b27076ab5725bae436fba781095a0a9c0ee

Es un SHA Git público del propio repositorio,
NO una contraseña/token/DSN.

Añadir UNA excepción exacta detect-secrets:

filename exacto
detector exacto
hashed_secret generado
is_verified=true
is_secret=false.

NO:

- bajar thresholds;
- excluir project-state.json;
- desactivar Hex High Entropy;
- aceptar otros findings;
- regenerar baseline indiscriminadamente.

Control negativo obligatorio:
un secreto/hash temporal nuevo sigue siendo detectado.

---

# 4. ENCODING DEL SECRET SCANNER

Ya está demostrado que Windows cp1252 puede omitir
docs/project-state.json UTF-8 mientras Linux sí lo analiza.

Cerrar esa divergencia.

El scanner debe comportarse de forma determinista UTF-8
en Windows y Linux.

Preferir solución mínima y explícita:

- ejecución Python en UTF-8 mode;
- o mecanismo equivalente demostrado.

No depender del locale del host.

Añadir regresión:

archivo JSON UTF-8 con caracteres no ASCII
+
high entropy fixture

debe ser analizado y detectado en ambos entornos lógicos.

No cambiar la sensibilidad del detector.

---

# 5. EVITAR CICLO INFINITO DE SHAs DOCUMENTALES

NO añadir el futuro NEW_SHA correctivo
a docs/project-state.json antes de la CI
si eso crea otro finding high-entropy.

El receipt final exacto del SHA/run
puede seguir FUERA de Git,
como en los cierres anteriores.

No crear una cadena infinita:

commit → documentar SHA → secret finding → commit.

---

# 6. STAGE 3 — HTTP + BACKUP + RESTORE

Problema demostrado:

la DB se recrea vacía
y postgres_smoke.py llama db.init_db()
con PostgreSQL auto_migrate=false.

Eso es comportamiento PRODUCTIVO CORRECTO.

NO activar autoDDL.

Corregir el harness.

Después de crear la DB nueva para stage3:

ejecutar explícitamente:

python -m noesis.migrations upgrade

y comprobar:

schema_version = 75
74 = captacion_hoja_y_tipo
75 = evaluacion_readiness_financiera

ANTES de lanzar postgres_smoke.py.

Si el upgrade falla:
stage3 FAIL.

---

# 7. STAGE 17 — PRIVACY + ROLLBACK

Mismo principio.

La base de stage17 es aislada y vacía.

Preparar explícitamente canonical75 ANTES
del smoke/precondition y del test de release/privacy.

No depender de stage3.

No compartir DB entre stages.

No autoDDL runtime.

Stage17 debe comenzar demostrando:

canonical75 exacto.

Después ejecutar su contrato privacy/rollback.

---

# 8. CUT-OFF — ERROR PSYCOPG

Fallo:

query LIKE 'INSERT INTO expenses%'
AND query LIKE '%qa_cut_pause()%'

con params=()

Psycopg interpreta los % literales como placeholders.

Corregir exclusivamente la consulta
de instrumentación.

Preferencia:

usar parámetros reales.

Ejemplo conceptual:

WHERE query LIKE ?
AND query LIKE ?
AND wait_event_type='Lock'

params:

("INSERT INTO expenses%", "%qa_cut_pause()%")

adaptado correctamente al wrapper actual.

Alternativamente escapar % según Psycopg,
pero preferir parametrización.

NO cambiar:

- sleep;
- timeout;
- expectations;
- cutoff;
- historical fence;
- physical validator.

---

# 9. CUT-OFF SEMÁNTICA OBLIGATORIA

Después de corregir el query,
el test debe demostrar realmente:

INSERT statement comienza

→ se bloquea dentro de qa_cut_pause()

→ query_start es anterior a T0

→ cutoff se abre

→ se libera advisory

→ el INSERT continúa

→ HistoricalFenceActive

→ ninguna fila "SQL fixture" queda persistida.

No declarar PASS si sólo desaparece ProgrammingError.

---

# 10. V2 — NO CAMBIAR PRODUCTO TODAVÍA

Este es el único bloqueo que requiere diagnóstico.

Estado actual del fixture:

source75.pgdump

se crea DESPUÉS de poblar A75
y ANTES de añadir objetos future/hstore.

Luego se añaden:

future schema
future types
domain
collation
tables
index
function
trigger
view
hstore
sequence state.

Después se crea:

unknown-objects75.pgdump

Y:

self.target

se restaura desde unknown-objects75.pgdump.

El test:

test_populated_A75_restore_preserves_hash_binding_and_off_state

actualmente ejecuta:

require_runtime(self.target)

por tanto mezcla:

A75 populated runtime roundtrip

con:

unknown-object preservation fixture.

NO asumir todavía que ésa sea la única causa.
Demostrarlo.

---

# 11. V2 — CREAR DOS ROUNDTRIPS SEPARADOS

Separar explícitamente dos matrices.

MATRIZ A — CANONICAL75 POPULATED

source canonical75
+
A75 evaluation populated

→ archive75

→ NEW dedicated fresh target75

→ restore archive75

→ require_runtime(target75)

→ exact schema binding

→ exact evaluation hash/body

→ control off/generation0/ever_enabled=false.

No objetos future.

No hstore añadido por fixture.

Ésta es la prueba que debe acreditar:

V2 canonical75 populated restore.

---

MATRIZ B — UNKNOWN OBJECT PRESERVATION

source con objetos future

→ unknown-objects75.pgdump

→ separate unknown_target

→ restore

→ comprobar preservación completa:

tables
columns
types
domain
collation
indexes
constraints
functions
triggers
views
sequences
extension
rows.

serving_authorized=false.

No reutilizar unknown_target
como target de la prueba canonical75 populated.

---

# 12. DIAGNÓSTICO DE OBJECT PROFILE

ANTES de modificar schema_objects.py,
profiles o restore:

comparar para MATRIZ A:

SOURCE canonical75
EXPECTED canonical75
RESTORED canonical75.

Usar:

physical_objects(..., "public")
expected_objects("postgres", 75)

Si hay diferencia,
emitir sólo información técnica segura:

object key
missing / changed / extra
hash SHA256 del descriptor normalizado
source-hash
expected-hash
restored-hash.

NO imprimir:

datos de negocio
filas
payloads
DSNs
passwords
documentos.

---

# 13. DECISIÓN V2

CASO A:

Dedicated archive75 → target75 pasa require_runtime
y binding/hash/off state exactos.

Entonces:

clasificar fallo anterior como FIXTURE COUPLING.

Corregir sólo test fixture.

NO cambiar:

schema_objects.py
normalized_sql
profiles
restore.

---

CASO B:

Dedicated archive75 → target75 sigue dando
SCHEMA_OBJECT_MISMATCH.

Entonces:

DETENTE antes de relajar nada.

Identificar objeto EXACTO.

Comparar:

source vs expected vs restored.

Sólo si se demuestra transformación semánticamente equivalente
de pg_dump/pg_restore o del deparser:

proponer corrección mínima de canonicalización
con regression específica.

NO implementarla automáticamente
si modifica el contrato de object identity
sin poder demostrar equivalencia exacta.

Si es un objeto realmente diferente:

BLOCKED.

---

# 14. UNKNOWN OBJECT TARGET

La matriz unknown-object
NO puede convertirse implícitamente
en autoridad de serving.

Preservar:

technical_integrity = PASS

serving_authorized = false

g_real_evidence = false.

Backup preservation ≠ runtime authority.

---

# 15. NO RELAJAR UNKNOWN FINANCIAL OBJECT GUARD

Mantener prueba:

objeto/trigger financiero desconocido
sobre tabla owned

→ SCHEMA_OBJECT_MISMATCH.

No introducir:

if test
if backup
if future schema
bypass global.

---

# 16. V2 BINDING

Para MATRIZ A canonical75 populated,
comprobar exactamente:

observed.schema_version == 75

observed.binding()
==
evaluation.context.schema_binding

financial_readiness_evaluations.content_hash
==
original evaluation content_hash

result_canonical.context
==
original context

capabilities
==
original capabilities

activation_control:

state = off
activation_generation = 0
ever_enabled = false.

No grants/handoff/effects.

---

# 17. V2 PRIVACY

Canonical75:

privacy_status = NO_E_INSTALLED

serving_authorized = false

g_real_evidence = false.

No convertir Backup V2 en evidencia G REAL.

---

# 18. LOCAL TARGETED TESTS

Antes del commit ejecutar, donde sea posible:

secret scan UTF-8
secret negative control
stage3 prep
stage17 prep
cutoff targeted PG
canonical75 dedicated V2 roundtrip
unknown-object roundtrip
A75 readiness
lineage PG
Ruff
Bandit
links
diff
truth.

Si algo falla:

NO commit todavía.

---

# 19. ARCHIVOS DE PRODUCTO

Ideal esperado de Corrective #2:

cero cambios productivos.

Cambios deberían concentrarse en:

- scanner/baseline;
- CI/harness;
- PG test instrumentation;
- Backup V2 fixtures/tests;
- documentación factual.

Si parece necesario modificar src/noesis/*
por V2:

primero demostrar CASO B.

No tocar producto por intuición.

---

# 20. CREAR UN ÚNICO COMMIT

Parent exacto:

b3a93361975693a157cf3874346dcfa456ce7162

No amend.
No rebase.
No squash.
No force.

Mensaje sugerido:

test(financial-core): close A75 postgres and backup validation

Registrar NEW_SHA.

---

# 21. PUSH

Antes del push comprobar de nuevo:

origin/main ==
678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

Si no:

DETENTE.

Si sí:

git push origin codex/phase-1-10a75

normal.

---

# 22. NUEVA CI

Lanzar NUEVO workflow_dispatch.

NO rerun del:

38539348109.

CI debe ejecutar sobre NEW_SHA exacto.

---

# 23. GENERAL JOB

Debe terminar:

SUCCESS.

Requerido:

secret scan PASS
dependency audit PASS
Bandit PASS
Ruff PASS
Node PASS
project truth PASS
links PASS
diff PASS
collision/AST PASS
full Python PASS
migration cycle PASS.

Resultados frescos.

---

# 24. POSTGRES JOB

Debe ejecutar:

20 / 20 stages

en 20 DB aisladas.

Todas:

PASS.

No heredar resultados de b3a93361.

---

# 25. STAGES OBLIGATORIAS

1 migrations32
2 migrations historical
3 HTTP + backup + restore
4 Core
5 Operations/Auth
6 Economic Events
7 Borrowed writers
8 Invoice Capture
9 Payment/Bank
10 Supplier/Expense
11 Channels
12 History inventory
13 History cutoff
14 History import
15 History reconciliation
16 legacy catalog53
17 privacy + rollback
18 A75 Readiness
19 Lineage Foundation
20 POSTGRES_BACKUP_V2_CANONICAL75

20/20 PASS obligatorio.

---

# 26. A75 CRITERIOS QUE NO SE REABREN

Deben seguir PASS:

fingerprint:

289b8eb580edd4c45d2de40233ffd7dfc193999b10f49825661cba18905696a1

74:
captacion_hoja_y_tipo

75:
evaluacion_readiness_financiera

A75:
off
generation0
ever_enabled=false

Advisory key:
2533761095082033151

timeout real:
30s

two migrators:
PASS

reread:
PASS

no duplicate75:
PASS

rollback/crash:
PASS

SOURCE_DRIFT:
PASS.

---

# 27. CRITERIO FINAL

Sólo declarar:

1.10A75 REMOTE CODE-VERIFIED PASS

si:

General job SUCCESS
PG job SUCCESS
20/20 stages PASS
0 FAIL
0 ERROR

y únicamente los skips históricos previstos
están presentes y cubiertos en PG.

No aceptar:

"technical partial PASS"
"close enough"
"fixture failure ignored".

---

# 28. SI V2 REVELA BUG REAL

Si dedicated canonical75 restore
demuestra diferencia estructural real:

NO maquillar.

Devolver:

1.10A75 BLOCKED — V2 STRUCTURAL MISMATCH

con:

object key
source descriptor hash
expected descriptor hash
restored descriptor hash
clasificación
impact.

No tercer cambio automático.

---

# 29. SI CI FALLA POR OTRO MOTIVO

NO crear otro commit.

Devolver:

1.10A75 CORRECTIVE #2 BLOCKED

con causa exacta.

---

# 30. NO AVANZAR

NO:

B76
C77
D78
E79
F80
Recovery Bridge
MAIN merge
deploy
Railway
production
business15
real backup
providers
flags
G-LIVE
H.

---

# 31. ENTREGA

Devuelve:

1.10A75 CORRECTIVE #2 STATUS

- old SHA b3a93361
- NEW_SHA
- parent
- archivos cambiados
- origin/main
- secret exact baseline delta
- UTF-8 scanner proof
- stage3 canonical75 prep
- stage17 canonical75 prep
- cutoff SQL fix
- snapshot-before-fence proof
- V2 diagnostic result
- dedicated canonical75 target result
- unknown-object target result
- object mismatch diff if any
- product files changed yes/no
- Python totals
- Node totals
- CRM totals
- PG totals
- 20/20 stages
- A75 readiness
- lineage
- advisory
- timeout
- concurrency
- rollback/crash
- SOURCE_DRIFT
- V1
- V2
- privacy
- legacy
- secrets
- Ruff
- Bandit
- dependency audit
- links
- diff
- truth
- warnings/skips
- Sharp status
- final verdict.

FINAL sólo si TODO verde:

1.10A75 REMOTE CODE-VERIFIED PASS

En caso contrario:

BLOCKED.