# 1.10A75 — CORRECTIVE REMOTE VALIDATION #1
# CORREGIR FALLOS DEMOSTRADOS POR CI f5150b27
# SIN RELAJAR GUARDS / SIN MAIN / SIN PRODUCCIÓN

ESTADO

Branch:

codex/phase-1-10a75

Candidate fallido:

f5150b27076ab5725bae436fba781095a0a9c0ee

Padre histórico de A75:

ac6a03d3b70794a4081c3b1d834581e91edb3133

Current origin/main:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

CI fallida:

run 38527937181

Jobs:

Tests i migracions = FAILURE
PostgreSQL18 y POSTGRES_BACKUP_V2 sin outbound = FAILURE

NO rebase.
NO amend.
NO force push.
NO main.

---

HECHOS YA CONFIRMADOS

General:

2004 total
1965 PASS
2 skips
3 FAIL
34 ERROR

PostgreSQL:

338 ejecutados
333 PASS
2 FAIL
3 ERROR

Runner PG:
13/20 etapas ejecutadas
7 no ejecutadas.

NO hay fallo de WSL/Linux en esta ejecución.

---

OBJETIVO

Crear UN commit correctivo encima de:

f5150b27076ab5725bae436fba781095a0a9c0ee

que resuelva ÚNICAMENTE los fallos demostrados.

Después:

full CI fresca completa
sobre el NUEVO SHA.

No avanzar a B76.

---

# 1. SECRET FALSE POSITIVE

Hallazgo:

docs/project-state.json
canonical75 fingerprint:

289b8eb580edd4c45d2de40233ffd7dfc193999b10f49825661cba18905696a1

Es:

fingerprint público de schema lineage.

NO es secret.

Aplicar exactamente el mismo protocolo aprobado
en Backup V2 CRM74:

- excepción exacta;
- filename exacto;
- Hex High Entropy String;
- hashed_secret generado por detect-secrets1.5.0;
- is_verified=true;
- is_secret=false.

NO:

- bajar threshold;
- excluir project-state;
- desactivar detector;
- regenerar baseline aceptando todo.

Delta baseline:
exactamente UNA nueva excepción.

Control negativo obligatorio:
un hash/secret nuevo temporal sigue siendo detectado.

---

# 2. WEB FIXTURES — NO TOCAR STARTUP PRODUCTIVO

34 ERROR actuales:

19 PublicMarketing
15 SEO

causa:

TestClient arranca runtime contra SQLite sin schema preparado.

A75 hace correctamente:

require_runtime()

y startup NO debe auto-migrar.

NO cambiar:

server._startup()

NO volver a:

db.init_db() automático en runtime.

NO relajar:

SCHEMA_METADATA_INCOMPLETE.

Corregir exclusivamente fixtures/tests.

---

# 3. PUBLIC MARKETING FIXTURE

En:

tests/test_public_marketing.py

después de aplicar los patches de:

DB_PATH
DATABASE_URL
etc.

y ANTES de:

TestClient(...).__enter__()

preparar explícitamente la DB sintética usando
el mecanismo propietario permitido del test:

db.init_db()

o migrations.upgrade()
según el contrato actual más correcto.

Debe producir canonical75.

El producto no hace autoDDL:
EL TEST prepara su fixture.

Además hacer cleanup robusto:

si TestClient.__enter__() falla,
los patches y TemporaryDirectory
deben liberarse igualmente.

Preferir addCleanup / ExitStack
o mecanismo determinista equivalente.

No permitir cascadas por setUp fallido.

---

# 4. SEO FIXTURE

tests/test_seo.py actualmente crea TestClient
sin una DB aislada explícita.

Corregirlo para que cada test/clase use:

- SQLite temporal;
- DATABASE_URL='';
- DB_PATH temporal;
- SEED_DEMO false;
- RESET_DB false;
- migración explícita a canonical75;
- scheduler neutralizado.

No usar:

data/noesis.db
DB compartida
estado residual de otro test.

Todos los tests SEO deben ser herméticos.

---

# 5. EXPECTATIVAS HISTÓRICAS OBSOLETAS

Dos tests fallan porque fueron escritos cuando:

LATEST_VERSION=74

Actualizar el CONTRATO DE TEST,
no el producto.

test_five_flags_and_schema_unchanged:

debe seguir verificando:

cinco flags OFF

y además:

LATEST_VERSION == 75

74 == captacion_hoja_y_tipo
75 == evaluacion_readiness_financiera.

No llamar ya al test:

schema_unchanged

si el nombre induce a error.

---

# 6. MIGRATIONS AFTER73 TEST

El test antiguo esperaba:

[74]

Ahora el contrato correcto es:

[74, 75]

Pero NO basta con cambiar la lista.

Reescribirlo para verificar semánticamente:

migration74:
sólo CRM / sales_*

migration75:
sólo objetos A readiness esperados.

A75 NO puede tocar:

legacy invoices
payments
bank
economic events
history rows
CRM sales_* excepto lectura de lineage si aplica.

Mantener la prueba más fuerte,
no más débil.

---

# 7. SOURCE_DRIFT — TRATAR COMO POSIBLE BUG REAL

Falló:

test_drift_between_scan_and_freeze

Esperado:

BLOCKED
SOURCE_DRIFT

Obtenido:

READY_FOR_REVIEW.

NO cambiar el expected a READY_FOR_REVIEW.

NO eliminar el test.

NO clasificarlo automáticamente como fixture.

Diagnosticar la causa exacta.

---

# 8. HIPÓTESIS A INVESTIGAR

A75 cambió HistoryDiagnostics._session SQLite de:

sin BEGIN explícito

a:

BEGIN
→ require_compatible()
→ permission reads
→ RawReader.page()

Esto puede fijar el snapshot SQLite
ANTES de que el write concurrente inyectado
se haga visible al RawReader.

Comprobar esta hipótesis con una reproducción mínima.

Registrar:

- estado in_transaction;
- momento del primer read;
- momento del write concurrente;
- qué valor observa RawReader;
- hashes scan/comparison.

No cambiar código hasta demostrar la causa.

---

# 9. INVARIANTE SOURCE_DRIFT

Debe preservarse:

si una fuente cambia DESPUÉS del scan inicial
y ANTES de que la segunda lectura de comparación
haya leído esa fuente,

el diagnóstico debe terminar:

BLOCKED / SOURCE_DRIFT.

A75 schema validation NO puede ampliar
silenciosamente una ventana donde ese cambio
queda oculto por snapshot prematuro.

---

# 10. CORRECCIÓN SOURCE_DRIFT

Implementar la corrección mínima
sólo después de demostrar la causa.

Debe conservar simultáneamente:

A. lineage exacta;
B. no MAX-only;
C. no autoDDL;
D. borrowed service no commit/rollback propios;
E. drift detection histórica;
F. PostgreSQL semantics intactas;
G. flags OFF.

NO solucionar mediante:

- quitar require_compatible;
- ignorar drift;
- aceptar READY_FOR_REVIEW;
- cambiar expected del test;
- hacer una conexión de autoridad no controlada;
- relajar object profile.

Añadir un regression test específico:

"lineage validation before RawReader
must not hide committed source drift".

SQLite PASS obligatorio.

Si la solución afecta el protocolo TX,
añadir equivalente PG cuando proceda.

---

# 11. PG HISTORY CUTOFF — NO RELAJAR OBJECT VALIDATOR

El fallo actual:

SCHEMA_OBJECT_MISMATCH

ocurre porque el test:

test_sql_statement_snapshot_before_open_observes_fence_after_commit

instala:

trigger aa0_cut_pause
ON expenses

y luego llama:

self.open()

El nuevo physical guard detecta correctamente
un trigger extra sobre una tabla financiera owned.

Eso es COMPORTAMIENTO CORRECTO.

NO permitir:

qa_* triggers
unknown triggers
test bypass
ignore-extra-trigger
special IS_TEST path

dentro del validator.

---

# 12. REDISEÑAR INSTRUMENTACIÓN DEL TEST PG

Mantener la intención histórica:

un INSERT debe iniciar su statement/snapshot
antes de abrir el cutoff,
quedar pausado,
abrirse el fence,
y después continuar y ser rechazado.

Pero hacerlo SIN alterar el canonical object profile
de una tabla financiera.

Preferencia a evaluar:

crear únicamente una función sintética aislada,
por ejemplo qa_cut_pause(),
NO un trigger sobre expenses,

e invocarla desde una expresión del INSERT
antes de que el INSERT alcance los triggers/guards
canónicos de expenses.

Conceptualmente:

INSERT INTO expenses (..., concept, ...)
VALUES (..., qa_cut_pause(), ...)

La función puede bloquear en advisory lock
y luego devolver el valor sintético.

Así:

- el statement ya está iniciado;
- queda bloqueado antes del write;
- no aparece un trigger extra en expenses;
- self.open() puede validar canonical75;
- al liberar, los guards reales del INSERT
  deben observar el fence y rechazar.

No asumir esta propuesta:
demostrar primero que preserva exactamente
la semántica que el test pretende medir.

Alternativa equivalente aceptable
si no modifica objetos financieros owned.

---

# 13. CLEANUP PG OBLIGATORIO

Cualquier función/objeto QA temporal
debe estar en:

try/finally

o addCleanup equivalente.

Aunque falle una assertion:

DROP del objeto QA debe ejecutarse.

El fallo de un test NO puede contaminar:

ttl
two_scans
races
waiting tests.

Añadir prueba de cleanup.

---

# 14. NO IGNORAR EXTRA OBJECTS

Añadir/retener test explícito:

trigger extra sobre expenses
→ SCHEMA_OBJECT_MISMATCH.

Esto demuestra que arreglar el fixture
NO debilitó el guard físico.

---

# 15. RACES POSTGRES

Tras reparar contaminación/instrumentación,
revalidar específicamente:

test_two_processes_open_one_winner_no_implicit_retry_epoch

test_waiting_services_do_not_lock_business_before_gate

Antes de cambiar sus expectativas.

Si siguen fallando en DB limpia:

diagnosticar como posible regresión real.

NO aumentar sleeps arbitrariamente
para esconder carreras.

Los tests deben observar contención real.

---

# 16. RUNNER PG — AISLAMIENTO ENTRE ETAPAS

El runner actual fail-fast dejó:

7/20 etapas sin ejecutar.

Para el correctivo:

cada etapa crítica debe arrancar
desde estado sintético limpio o cleanup demostrado.

Puede seguir terminando CI en FAILURE
si una etapa falla,

pero preferimos que el receipt pueda distinguir:

failure de etapa
vs
contaminación de etapas posteriores.

Si es seguro,
ejecutar las20 etapas y acumular resultados
antes de devolver exit1.

Si una etapa corrupta deliberadamente schema,
debe usar DB/namespace propio.

No compartir contaminación deliberada.

---

# 17. NO HEREDAR 13/20

La próxima CI debe ejecutar:

20/20.

No reutilizar:

333 PASS

del SHA anterior.

Todo fresco sobre nuevo SHA.

---

# 18. A75 FINAL REQUIRED MATRICES

Deben quedar verdes:

General Python completa
Node
CRM
A75 SQLite
Lineage SQLite

PG:

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

---

# 19. A75 PG EVIDENCE OBLIGATORIA

En etapa18/19 demostrar:

canonical75 fingerprint:

289b8eb580edd4c45d2de40233ffd7dfc193999b10f49825661cba18905696a1

migration74:
captacion_hoja_y_tipo

migration75:
evaluacion_readiness_financiera

A75:

off
generation0
ever_enabled=false
no grants
no handoff
no effects.

---

# 20. ADVISORY MIGRATOR

Debe ejecutarse finalmente,
no quedar pendiente:

key:
2533761095082033151

timeout:
30s

two migrators
reread after lock
no duplicate75
rollback/crash
timeout.

No sustituir por pruebas SQLite.

---

# 21. V2 CANONICAL75

Etapa20 obligatoria:

canonical75
→ native V2 backup
→ fresh PG18 restore
→ canonical75 exacta.

Verificar:

registry1–75
names
applied_at
fingerprint
object profile
DDL
rows
sequences
constraints
functions/triggers
privacy = NO_E_INSTALLED
serving_authorized=false.

---

# 22. LEGACY REJECTION

Mantener:

legacy Financial74
legacy Financial75
legacy Financial79

≠ canonical75.

No promoción.

No rewrite.

---

# 23. VALIDACIÓN LOCAL DIRIGIDA ANTES DE COMMIT

No hace falta depender de WSL inestable.

Ejecutar localmente lo posible:

secret scanner
web fixture tests
SEO
history two updated contracts
SOURCE_DRIFT regression SQLite
A75 SQLite
lineage SQLite
Ruff
Bandit
links
diff
truth.

Si hay entorno PG estable disponible,
dirigidos PG.

Pero la autoridad final será CI Linux/PG18.

---

# 24. CORRECTIVE COMMIT

Sólo cuando dirigidos estén verdes.

Crear UN commit encima de:

f5150b27076ab5725bae436fba781095a0a9c0ee

NO amend.

Mensaje sugerido:

fix(financial-core): preserve A75 lineage and historical race contracts

Registrar NEW_SHA.

---

# 25. ARCHIVOS PRODUCTO

Cambios de producto permitidos SOLAMENTE
si son necesarios para corregir SOURCE_DRIFT
u otra regresión funcional demostrada.

Todo cambio productivo debe incluir
regression test.

Fixtures/test/harness pueden cambiar
para adaptarse al nuevo contrato correcto.

No tocar B76–F80.

---

# 26. PUSH

Antes:

origin/main debe seguir:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

Si drift:

DETENTE.

Si estable:

git push normal
origin codex/phase-1-10a75

NO force.

---

# 27. NUEVA CI

Workflow_dispatch NUEVO
sobre NEW_SHA exacto.

NO rerun del38527937181.

Los dos jobs deben ser SUCCESS.

20/20 etapas PG.

---

# 28. CRITERIO FINAL

Sólo declarar:

1.10A75 REMOTE CODE-VERIFIED PASS

si:

0 FAIL
0 ERROR
en todas las matrices obligatorias,

salvo skips expresamente previstos
y cubiertos en PostgreSQL.

No sumar parciales.

No heredar greens de otro SHA.

---

# 29. NO AVANZAR

NO:

B76
C77
D78
E79
F80
Recovery Bridge
production
Railway
business15
real backups
providers
flags
G-LIVE
H.

---

# 30. ENTREGA

Devuelve:

1.10A75 CORRECTIVE STATUS

- old SHA
- new SHA
- parent
- changed files
- baseline delta exacto
- web fixture correction
- SEO fixture correction
- historical expectation correction
- SOURCE_DRIFT root cause
- SOURCE_DRIFT product/test fix
- regression tests
- PG cutoff instrumentation redesign
- canonical object guard unchanged proof
- cleanup proof
- race tests
- full Python totals
- Node
- CRM
- PG totals
- 20/20 stages
- A75 parity
- lineage
- migrator advisory/concurrency
- V1
- V2 canonical75
- legacy rejection
- privacy classification
- secrets/Bandit/Ruff/audit
- links/diff/truth
- skips/warnings
- origin/main
- final verdict.

FINAL:

1.10A75 REMOTE CODE-VERIFIED PASS

o:

BLOCKED

con causa exacta.