# 1.10A75 — CORRECTIVE #3 / STRUCTURAL DIAGNOSIS + FINAL CLOSURE
# DIAGNOSTICAR LOS DOS ÚNICOS BLOQUEOS RESTANTES
# NO RELAJAR OBJECT IDENTITY / NO B76 / NO PRODUCCIÓN

ESTADO

Branch:

codex/phase-1-10a75

Current remote HEAD:

cb23aa4484c036a3125b5f0ba72968384945136d

Parent:

b3a93361975693a157cf3874346dcfa456ce7162

origin/main esperado:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

CI:

run 38547535812

GENERAL JOB:
SUCCESS

PostgreSQL job:
FAILURE

20/20 stages executed
18 PASS
2 FAIL

NO rebase.
NO amend.
NO force push.
NO main.

---

BLOQUEOS RESTANTES

A. V2 canonical75 populated restore:

único objeto distinto:

constraint:economic_events:economic_events_amount_check

source hash:
98ac9c459440f22697015c5aa154eda591b9cf1e4c9a01b2626b41305a62c052

expected hash:
98ac9c459440f22697015c5aa154eda591b9cf1e4c9a01b2626b41305a62c052

restored hash:
dafee876232a715ecaa254d7f6961771709cde11c0d63ceb825f1d32b415f6cf

B. stage17 privacy/rollback:

canonical75 precondition PASS
HTTP smoke PASS

después:

migrations.downgrade(55)

bloquea con:

SCHEMA_OBJECT_MISMATCH

objeto exacto todavía desconocido.

---

OBJETIVO

Antes de cambiar ningún contrato:

1. identificar el objeto exacto del stage17;
2. determinar si comparte root cause con economic_events_amount_check;
3. demostrar si el CHECK source/restored es:
   - semánticamente idéntico;
   - realmente distinto;
   - o sólo distinto en representación PostgreSQL;
4. implementar únicamente la corrección demostrada;
5. ejecutar CI completa nueva.

No avanzar si la equivalencia no puede demostrarse.

---

# 1. FREEZE

Congelar:

migration75
readiness
lineage identities
object profile policy
startup
locking
SOURCE_DRIFT
Backup V2 archive format
privacy semantics
cinco flags.

NO tocar estos componentes por intuición.

---

# 2. MAIN GUARD

Verificar antes de trabajar:

origin/main ==
678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

Si cambia:

DETENTE
REMOTE_MAIN_DRIFT.

---

# 3. STAGE17 — OBTENER OBJECT DIFF EXACTO

Actualmente downgrade() devuelve únicamente:

SCHEMA_OBJECT_MISMATCH.

Añadir instrumentación TEST-ONLY para comparar,
justo antes de migrations.downgrade(55):

actual =
physical_objects(conn, current_schema)

expected =
expected_objects("postgres", 75)

Calcular diff exacto:

missing keys
extra keys
changed keys

Para cada key distinta devolver únicamente:

object_key
classification
actual descriptor SHA256
expected descriptor SHA256

NO imprimir:

SQL completo
datos
rows
DSN
secrets.

La instrumentación no puede modificar
schema_objects.py productivo.

---

# 4. STAGE17 — DOS MOMENTOS

Capturar object diff en:

T1:
inmediatamente después de migrations.upgrade()
del schema release_rollback_*.

T2:
inmediatamente antes de downgrade(55),
después del seed/data operations.

Comparar.

Objetivo:

saber si:

A. 32→75 ya nace físicamente distinto;

B. alguna operación entre upgrade y downgrade
modifica DDL;

C. el mismatch es exactamente
economic_events_amount_check;

D. es otro objeto.

No hacer fix hasta saberlo.

---

# 5. V2 CHECK — CAPTURAR DESCRIPTORES TÉCNICOS

Para:

constraint:economic_events:economic_events_amount_check

capturar en SOURCE y RESTORED:

conname
contype
condeferrable
condeferred
convalidated
connoinherit
pg_get_constraintdef(oid, false)
pg_get_expr(conbin, conrelid, false)

y hashes separados de cada campo.

También:

column type de economic_events.amount
precision/scale metadata
PostgreSQL major/version.

No publicar datos de negocio.

Es aceptable persistir estos datos
sólo como artifact sintético/receipt de CI.

---

# 6. CHECK ORIGINAL

La intención económica del CHECK debe seguir siendo exactamente:

amount IS NULL

OR

amount BETWEEN
-9999999999999999.99
AND
9999999999999999.99

AND

amount = trunc(amount, 2)

No modificar límites.

No aceptar redondeo.

No introducir NUMERIC(20,4).

No cambiar NULL semantics.

---

# 7. SEMANTIC PROOF

Si SOURCE y RESTORED expresan texto diferente,
demostrar equivalencia con una matriz dirigida.

Probar ambos constraints sobre valores:

NULL

0
0.00
0.01
-0.01

1.23
-1.23

1.230
1.231
-1.231

9999999999999999.99
-9999999999999999.99

9999999999999999.991
-9999999999999999.991

fuera de límite positivo
fuera de límite negativo

valores con escala grande
valores cercanos a cero
valores NUMERIC exactos.

Para cada valor:

SOURCE expression result
RESTORED expression result

deben ser idénticos.

Añadir property test determinista
sobre un conjunto amplio de Decimal generado
sin floats.

No usar únicamente ejemplos felices.

---

# 8. NO CONFUNDIR HASH CON SEMÁNTICA

Un hash distinto sólo demuestra
descriptor textual/estructural distinto.

NO demuestra automáticamente
regla económica diferente.

Pero tampoco asumir equivalencia.

Necesitamos:

catalog diff
+
truth table/property proof
+
explicación exacta del rewrite PostgreSQL.

---

# 9. DETERMINAR CAUSA DEL REWRITE

Investigar si pg_dump/pg_restore transforma el CHECK por:

parentheses
explicit numeric casts
BETWEEN expansion
operator qualification
function qualification
search_path
constraint validation phase
deparser canonical form

u otra causa.

Identificar exactamente el delta.

No usar "PostgreSQL lo cambia"
como explicación suficiente.

---

# 10. DECISIÓN V2

CASO A — SEMÁNTICAMENTE IDÉNTICO Y TRANSFORMACIÓN DETERMINISTA

Entonces diseñar una normalización MUY ESTRECHA
exclusivamente para esa clase demostrada
de representación PostgreSQL.

Preferencia:

normalizar expresión CHECK
desde una representación estructural estable,
no con replace textual amplio.

La normalización sólo puede aceptar
transformaciones probadas equivalentes.

Añadir:

source → normalized X
restored → normalized X.

Y tests negativos:

un límite diferente NO normaliza igual.

trunc(amount,3) NO normaliza igual.

> en vez de >= NO normaliza igual.

AND/OR semánticamente diferente NO normaliza igual.

---

CASO B — NO PUEDE DEMOSTRARSE EQUIVALENCIA

DETENTE.

No modificar profile.

Resultado:

1.10A75 BLOCKED — REAL CHECK SEMANTIC MISMATCH.

---

# 11. NO GLOBAL RELAXATION

Prohibido:

ignorar CHECK differences
ignorar casts globalmente
strip all parentheses indiscriminadamente
sort arbitrary boolean expressions
permitir unknown constraint descriptors
fallback a name-only validation.

Object guard debe seguir fail-closed.

---

# 12. STAGE17 RELATION

Cuando tengamos el diff stage17:

SI el objeto es el mismo CHECK
y el delta es exactamente el mismo:

documentar root cause común.

Aplicar una única corrección estructural
y probar ambos casos.

SI es otro objeto:

tratarlo independientemente.

No asumir misma causa.

---

# 13. STAGE17 32→75 PATH

Debemos demostrar:

fresh 0→75 canonical profile

y:

32→75 con factura histórica

terminan con la MISMA identidad física canonical75
salvo variantes históricas explícitamente aprobadas.

Comparar perfiles completos.

Si 32→75 produce DDL distinto:

identificar qué migration crea la divergencia.

No añadir automáticamente otra excepción histórica
para schema75.

Preferencia:

hacer que la migration produzca un resultado canónico
si es seguro y compatible.

Pero NO cambiar migrations históricas
sin diagnóstico y regresión completa.

---

# 14. NO DATA-DEPENDENT DDL

Comprobar si alguna migration 32→75
decide DDL en función de rows existentes.

Si existe:

documentarlo.

Canonical schema identity NO debe variar
simplemente porque había una factura histórica,
salvo contrato explícito.

---

# 15. DOWNGRADE VALIDATION

Una vez canonical75 está verificado:

migrations.downgrade(55)

en el schema sintético debe poder comenzar
sólo si el profile es canonical75 exacto.

No bypass de validator para downgrade.

No:

validate=False
force=True
test_only skip.

---

# 16. DOWNGRADE SAFETY

Conservar todos los guards existentes:

draft incomplete blocks
durable evidence blocks
bank/payment link blocks
fiscal immutability
snapshot rows unchanged
legacy rollback semantics.

No borrar datos para hacer pasar downgrade.

---

# 17. TESTS V2 DESPUÉS DEL FIX

Canonical75 populated:

source75
→ Backup V2
→ fresh PG18 restore
→ require_runtime PASS.

Verificar:

registry1–75 exacto
fingerprint canonical75
object profile canonical75
evaluation content_hash exacto
result_canonical exacto
context exacto
capabilities exactas

activation:
off
generation0
ever_enabled=false

privacy:
NO_E_INSTALLED

serving_authorized=false
g_real_evidence=false.

---

# 18. UNKNOWN OBJECTS

La matriz unknown objects debe seguir PASS.

No convertir future objects
en canonical authority.

technical_integrity PASS
serving false
G REAL false.

---

# 19. NEGATIVE OBJECT TESTS

Mantener/añadir:

changed amount limit -> reject

trunc(amount,3) -> reject

extra financial trigger -> reject

missing CHECK -> reject

changed CHECK operator -> reject

unknown owned column -> reject.

Esto demuestra que la solución
NO relaja el guard.

---

# 20. STAGE17 FINAL

Después del diagnóstico/fix:

stage17 completo debe pasar:

precondition canonical75
HTTP smoke
rollback75→55→54→53→54→55→75
data snapshots iguales
fiscal immutability intacta
privacy flow
tenant isolation
security event integrity.

---

# 21. PRODUCT CHANGE POLICY

Si la única corrección necesaria es:

canonicalización estructural segura

puede modificarse src/noesis/schema_objects.py
o helper equivalente.

Pero sólo después de:
equivalence proof + negative tests.

Si necesita modificar migration DDL:

DETENTE antes de hacerlo,
salvo que quede demostrado
que la migration genera schema incorrecto.

Reportar primero.

---

# 22. LOCAL/TARGETED BEFORE COMMIT

Ejecutar:

V2 semantic diagnostic
V2 populated roundtrip
stage17 object diff
stage17 rollback
schema lineage PG
A75 readiness PG
negative object tests
Ruff
Bandit
secrets
links
diff
truth.

No commit si alguno falla.

---

# 23. UN SOLO CORRECTIVE COMMIT

Parent exacto:

cb23aa4484c036a3125b5f0ba72968384945136d

No amend.
No rebase.
No squash.

Mensaje sugerido:

fix(financial-core): canonicalize verified postgres schema identity

Sólo si ésa resulta realmente ser la causa.

Si no:
mensaje acorde a la causa demostrada.

---

# 24. PUSH

Antes:

origin/main ==
678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

Push normal:

codex/phase-1-10a75

NO force.

---

# 25. CI FRESCA COMPLETA

NUEVO workflow_dispatch.

No rerun del38547535812.

General job:
SUCCESS.

PG18:
20/20 PASS.

No heredar ningún verde anterior.

---

# 26. CIERRE A75

Sólo declarar:

1.10A75 REMOTE CODE-VERIFIED PASS

si:

General SUCCESS
PG SUCCESS
20/20 stages PASS
0 FAIL
0 ERROR

y V2 canonical75 runtime roundtrip PASS.

---

# 27. NO AVANZAR

NO:

B76
C77
D78
E79
F80
Recovery Bridge
main merge
deploy
production
business15
real backup
providers
flags
G-LIVE
H.

---

# 28. ENTREGA

Devuelve:

1.10A75 CORRECTIVE #3 STATUS

- old SHA
- new SHA
- parent
- changed files
- main SHA
- exact stage17 object diff T1/T2
- whether stage17 and V2 share root cause
- source CHECK technical descriptor hashes
- restored CHECK technical descriptor hashes
- exact syntactic/structural delta
- semantic truth-table result
- Decimal property test result
- normalization/fix if any
- negative equivalence tests
- 0→75 vs32→75 physical profile comparison
- downgrade result
- V2 populated runtime result
- binding/hash/body/off-state result
- unknown-object result
- full Python totals
- Node
- CRM
- PG totals
- 20/20 stages
- A75
- lineage
- concurrency
- SOURCE_DRIFT
- security gates
- warnings/skips
- Sharp unchanged
- final verdict.

FINAL:

1.10A75 REMOTE CODE-VERIFIED PASS

o:

BLOCKED

con causa exacta.
## Autorización humana posterior: retención técnica exacta

El titular autoriza exclusivamente perfiles TECHNICAL_ONLY53/54/55/58 derivados
de retenciones históricas existentes. Nunca canonical/startup/runtime/readiness/
activation/backup serving/PilotGate/binding/evidenceREAL. Full fingerprint e
identidad exactos, extras desconocidos SCHEMA_OBJECT_MISMATCH. Canonical53–75 y
callbacks históricas intactos; no borrar datos. Migrador/downgrade técnico aislado;
terminar canonical75 exacto. Añadir regresiones positivas y negativas anti-autoridad,
continuar fixV2 demostrado y repetir validación. Sin B76–F80/prod/bridge/G-LIVE/H.
