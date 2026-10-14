# 1.10A75 — REMOTE VALIDATION CANDIDATE
# USAR GITHUB ACTIONS LINUX + POSTGRESQL18 COMO ENTORNO AUTORITATIVO
# NO REPARAR WSL / NO MAIN / NO DEPLOY

ESTADO ACTUAL

branch local:

codex/phase-1-10a75

HEAD actual:

ac6a03d3b70794a4081c3b1d834581e91edb3133

Ese HEAD es todavía la base Backup V2 CRM74.

Cambios A75:

72 archivos creados/modificados
SIN commit final.

Estado actual:

1.10A75 BLOCKED

Motivo:

WSL STATUS_STACK_OVERFLOW
0xC00000FD

Windows Event1000 confirmó crash de:

wsl.exe
wslservice.exe

También cayó un control sin Noesis ni DB.

NO hay traceback Python que demuestre defecto del Financial Core.

---

CURRENT REMOTE MAIN

Verificado externamente:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

Rama remota:

codex/phase-1-10a75

NO existe todavía.

---

OBJETIVO

NO intentar reparar WSL.

Convertir el estado actual en:

REMOTE VALIDATION CANDIDATE

y ejecutar TODA la validación requerida
en GitHub Actions/Linux/PostgreSQL18
desde cero.

Publicar la rama NO equivale a aprobar A75.

---

# 1. FREEZE FUNCIONAL

Antes de crear commit:

NO cambiar lógica funcional A75.

Los 47 archivos de código/tests/config actualmente congelados
deben permanecer congelados salvo que sea estrictamente necesario
para hacer portable el runner CI.

Si cualquier cambio funcional fuese necesario:

DETENTE
y reporta antes de commit.

Permitido únicamente:

- harness CI;
- scripts de orquestación sintética;
- correcciones documentales factuales;
- exact allowlist de falso positivo público si aparece;
- wiring necesario para ejecutar las matrices ya implementadas.

NO relajar guards.

---

# 2. PRE-COMMIT INVENTORY

Registrar:

git status --porcelain

lista exacta de los72 archivos.

Confirmar:

base HEAD =
ac6a03d3b70794a4081c3b1d834581e91edb3133

origin/main =
678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

Si origin/main ha cambiado:

DETENTE:

REMOTE_MAIN_DRIFT

No rebase.
No merge.

---

# 3. VALIDACIÓN WINDOWS YA DISPONIBLE

No presentar esto como full PASS,
pero conservar como evidencia dirigida:

74 tests finales:
PASS
0 skips
0 FAIL
0 ERROR

Node:
11 PASS

Ruff:
PASS

Bandit:
PASS

Secrets:
PASS

Dependencies:
PASS

AST collision guard:
PASS

Project truth:
PASS

diff:
PASS

links:
652 / 0 rotos

NO reutilizar esos resultados
como sustitución de la CI completa remota.

---

# 4. PREPARAR CI A75 COMPLETA

La rama debe ejecutar en GitHub Actions
TODO lo requerido para cierre A75.

Usar:

Linux runner

PostgreSQL18.6
mediante el toolchain Mise/lock ya verificado
en Backup V2 CRM74.

NO PostgreSQL16.

NO WSL.

---

# 5. JOB GENERAL

Debe incluir:

pip-audit
secret scan
links
diff-check real de commits
Bandit HIGH/HIGH
Ruff
Node
project truth
full Python unittest suite
full migration cycle

y cualquier guard A75 nuevo.

Ningún paso requerido puede quedar skipped
por ordering accidental.

---

# 6. JOB POSTGRESQL18 A75

Extender/usar runner sintético para ejecutar
DESDE CERO las matrices requeridas.

No reutilizar clusters ni resultados parciales.

Debe crear su propio PostgreSQL18 temporal,
sin outbound.

Ejecutar las 20 etapas completas definidas
por A75.

Como mínimo incluir:

migrations historical
0→75
32→75
73→74→75
canonical74→75

legacy Financial74 rejection

schema lineage PostgreSQL
wrong-name
gap
duplicate
future
corrupt
missing objects
extra objects según contrato

Financial Core
Operations/Auth
Economic Events
Borrowed writers
Invoice Capture
Payment/Bank
Supplier/Expense
Channels

History inventory
History cutoff
History import
History reconciliation

Financial Readiness A75
A parity PostgreSQL

migration advisory lock
two migrators concurrency
30s timeout behavior
reread after lock
rollback/crash behavior

V1 canonical75
V2 canonical75
backup75→restore75
registry identity
fingerprint identity
unknown objects
legacy79 synthetic/privacy hold

HTTP/readiness/startup

No providers reales.

---

# 7. CONCURRENCY ES OBLIGATORIA

La fase NO puede cerrar si GitHub Actions
no demuestra el protocolo PostgreSQL de locks.

Verificar explícitamente:

advisory xact key:
2533761095082033151

timeout:
30 s

registry lock antes de decisión

reread después de lock

dos migradores no aplican DDL simultáneamente

no duplicate75

no partial registry

rollback/crash conserva estado coherente.

---

# 8. CANONICAL75

Resultado final del lab debe demostrar:

LATEST_VERSION = 75

74 =
captacion_hoja_y_tipo

75 =
evaluacion_readiness_financiera

fingerprint canonical75:

289b8eb580edd4c45d2de40233ffd7dfc193999b10f49825661cba18905696a1

y presencia/identidad de los objetos A.

No aceptar sólo MAX(version)=75.

---

# 9. A75 STATE

Después de migration75:

activation state:

off

generation:

0

ever_enabled:

false

No grants.

No handoff.

No Financial Operation.

No Economic Event.

No provider attempt.

No real effect.

---

# 10. BACKUP V2 CANONICAL75

Obligatorio cerrar el criterio que quedó FAIL localmente.

Test:

canonical75
→ Backup V2
→ restore fresh PG18
→ exact canonical75.

Verificar:

registry exacto1–75
migration names
applied_at preserved
fingerprint
DDL
rows
constraints
functions
triggers
sequences
object inventory

No migrations durante restore.

serving_authorized=false.

Privacy:

NO_E_INSTALLED.

---

# 11. LEGACY LINEAGE

Probar rechazo explícito de:

legacy Financial74
legacy Financial75
legacy Financial79

para serving canonical.

Backup V2 puede preservar físicamente
legacy79 en fixture sintético,
pero clasificación debe continuar:

LEGACY_FINANCIAL74_79

No canonical.

No authority.

---

# 12. FULL PYTHON

Necesitamos UNA suite general completa
desde cero y con cierre real.

Registrar:

total
PASS
skips
FAIL
ERROR
duration
exit code.

No agregar ejecuciones parciales.

No convertir skips en PASS.

---

# 13. CRM

Los tests CRM actuales deben formar parte
de la suite completa fresca.

Registrar:

CRM package
CRM legacy

Sin regresión.

---

# 14. SECRET SCANNER

A75 introduce fingerprints/hashes públicos.

Si detect-secrets señala exclusivamente
un SHA/fingerprint público documental nuevo:

NO bajar threshold.
NO excluir archivos.
NO desactivar detector.

Permitido añadir únicamente una excepción exacta:

filename
detector
hashed_secret

is_verified=true
is_secret=false

igual que el correctivo Backup V2.

Si aparece algo que pueda ser secreto real:

DETENTE.

---

# 15. SHARP

La alerta HIGH sigue:

SEPARATE SECURITY DEBT
PRE-PRODUCTION TRIAGE REQUIRED

No resolver aquí.

No declarar cerrada.

---

# 16. COMMIT CANDIDATO

Una vez preparados los runners,
crear un commit candidato.

Este commit NO significa PASS.

Mensaje sugerido:

feat(financial-core): canonical A75 with schema lineage guards

o equivalente.

Padre directo obligatorio:

ac6a03d3b70794a4081c3b1d834581e91edb3133

No amend.
No rebase.
No squash histórico.

Registrar SHA.

---

# 17. PUSH FEATURE BRANCH

Autorizado:

git push origin codex/phase-1-10a75

NO force.

NO main.

NO tags.

NO PR merge.

---

# 18. ANCESTRY REMOTA

Verificar:

remote head == candidate SHA

base ancestry incluye exactamente:

ac6a03d...

La rama debe estar basada en
Backup V2 CRM74 verificado.

Si main ha cambiado entretanto:

reportar drift,
pero NO rebasear automáticamente.

---

# 19. CI NUEVA

Lanzar workflow_dispatch
sobre el candidate SHA exacto.

No usar resultados de otro SHA.

No rerun de Backup V2 como evidencia A75.

---

# 20. CRITERIO DE PASS

Sólo cerrar si TODOS pasan:

general CI job SUCCESS

PostgreSQL18 A75 job SUCCESS

full Python suite completa

Node

CRM

security gates

migration0→75

73→74→75

74→75

legacy rejection

lineage object validation

A parity

PG advisory concurrency

timeout/crash

Backup V2 canonical75 restore

V1/V2 identity

history

privacy classification

HTTP/readiness

No critical unexpected skips.

---

# 21. SI CI FALLA

NO corregir automáticamente.

Devolver:

1.10A75 REMOTE BLOCKED

con:

job
step
failure
classification
logs relevant
whether code defect / infra / test / security.

No nuevo commit sin nueva autorización.

---

# 22. SI TODO PASA

Actualizar cierre documental factual
sólo si puede hacerse SIN crear un segundo SHA
que invalide la CI.

Preferencia:

el commit candidato ya debe contener
un cierre que diga:

REMOTE VALIDATION PENDING

La evidencia final puede permanecer
fuera del commit / receipt externo.

No crear un commit documental posterior
y heredar CI de otro SHA.

---

# 23. VEREDICTO

Si la CI exacta del candidate SHA pasa:

1.10A75 REMOTE CODE-VERIFIED PASS

Añadir nota:

local WSL validation environment remained unstable;
authoritative full closure executed on isolated Linux/PostgreSQL18 CI.

NO llamarlo:

LOCAL CODE-VERIFIED PASS.

---

# 24. NO PRODUCCIÓN

NO:

Railway
production DB
Noesis19FQA
backup real
restore real
business15
providers
flags.

---

# 25. NO AVANZAR

NO:

B76
C77
D78
E79
F80
Recovery Bridge
G-LIVE
H.

---

# 26. ENTREGA

Devuelve:

1.10A75 REMOTE VALIDATION STATUS

- branch
- candidate SHA
- parent
- changed files
- main SHA
- ancestry
- workflow/run ID
- exact head SHA
- job conclusions
- full Python totals
- Node totals
- CRM totals
- PG18 totals
- 20-stage PG runner
- A75-specific totals
- lineage totals
- canonical75 fingerprint
- migration paths
- advisory/concurrency results
- crash/timeout results
- A historical parity
- V1 result
- V2 canonical75 result
- legacy lineage rejection
- privacy classification
- startup/readiness
- secrets
- Bandit
- Ruff
- dependency audit
- links
- diff-check
- skips/warnings
- sharp status
- remaining risks

FINAL sólo si todo verde:

1.10A75 REMOTE CODE-VERIFIED PASS

si no:

BLOCKED.

Confirmar:

NO B76–F80
NO bridge
NO production
NO business15
NO main merge
NO deploy
NO flags
NO G-LIVE
NO H.