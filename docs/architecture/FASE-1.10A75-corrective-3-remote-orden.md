# 1.10A75 — REMOTE TARGETED VALIDATION AFTER WSL FAILURE
# AUTORIZAR COMMIT CANDIDATO PARA VALIDACIÓN LINUX
# NO ES APROBACIÓN DE A75

Estado actual:

branch:
codex/phase-1-10a75

HEAD actual:
cb23aa4484c036a3125b5f0ba72968384945136d

origin/main:
678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

Corrective #3:
BLOCKED únicamente porque la validación PostgreSQL dirigida
no pudo completarse de forma estable en WSL.

WSL:
repetidos crashes c00000fd.

NO reintentar.
NO reset.
NO reparar.
NO reinstalar.
NO usar Noesis19FQA.

---

CAMBIO DE PROCEDIMIENTO AUTORIZADO

Se levanta ÚNICAMENTE la condición:

"no commit hasta completar los dirigidos PG locales"

porque el entorno local WSL ya ha demostrado
que no puede producir evidencia fiable.

Se autoriza crear UN commit candidato
y usar GitHub Actions/Linux/PostgreSQL18
como entorno autoritativo.

Ese commit NO significa:

CODE-VERIFIED PASS
merge
deploy
producción
G-LIVE.

---

# 1. FREEZE DEL CANDIDATO

Antes del commit:

NO cambiar más producto.

El candidato actual debe quedar congelado.

Cambios funcionales autorizados existentes:

- perfiles TECHNICAL_ONLY exactos53/54/55/58;
- schema retention helpers;
- normalización estrecha y demostrada del CHECK V2.

No tocar:

migration75
canonical profiles
migrations históricas
readiness semantics
activation
flags
privacy
providers
SOURCE_DRIFT
locks.

---

# 2. VERIFICAR PORTABLES

Antes del commit confirmar:

portable regressions:
91 PASS
1 skip POSIX
0 FAIL
0 ERROR

new final regressions:
4/4 PASS

Node:
11/11 PASS

Ruff:
PASS

Bandit:
PASS

Secrets:
PASS

Dependencies:
PASS

AST:
PASS

Truth:
PASS

Links:
PASS

Diff:
PASS.

Si cualquiera ha cambiado:
DETENTE.

---

# 3. COMMIT CANDIDATO

Crear UN commit encima de:

cb23aa4484c036a3125b5f0ba72968384945136d

No amend.
No rebase.
No squash.

Mensaje sugerido:

fix(financial-core): validate retained schemas and postgres check identity

Registrar NEW_SHA.

---

# 4. PUSH FEATURE BRANCH

Antes:

origin/main debe seguir:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

Si no:
DETENTE — MAIN_DRIFT.

Si sí:

git push origin codex/phase-1-10a75

normal.

NO force.
NO main.

---

# 5. CI AUTORITATIVA

Lanzar un workflow_dispatch NUEVO
sobre NEW_SHA exacto.

Linux.

PostgreSQL18.6.

No WSL.

No heredar resultados anteriores.

---

# 6. GENERAL JOB

Debe ejecutar desde cero:

full Python
Node
CRM
Ruff
Bandit
secret scan
dependency audit
AST/collision
project truth
links
diff
migration cycle.

Todo SUCCESS.

---

# 7. POSTGRES JOB — 20/20

Ejecutar las20 etapas completas.

Cada etapa:
DB aislada propia.

Necesitamos:

20/20 PASS.

Especial atención a:

17 privacy + rollback
18 A75 Readiness
19 Lineage Foundation
20 POSTGRES_BACKUP_V2_CANONICAL75.

---

# 8. TECHNICAL_ONLY RETENTION

Validar PostgreSQL real para perfiles:

53
54
55
58

Cada perfil debe:

- reconocer únicamente su set exacto retenido;
- tener identidad/fingerprint exacto;
- ser TECHNICAL_ONLY;
- no ser VERIFIED;
- no autorizar runtime;
- no autorizar readiness;
- no autorizar binding;
- no autorizar serving;
- no autorizar backup serving;
- no autorizar G evidence.

Cualquier objeto extra:
SCHEMA_OBJECT_MISMATCH.

---

# 9. STAGE17

Debe completar:

canonical75 exacta
→ downgrade55
→ retained55 TECHNICAL_ONLY exacto
→ downgrade54
→ retained54 TECHNICAL_ONLY exacto
→ downgrade53
→ retained53 TECHNICAL_ONLY exacto
→ upgrade54
→ upgrade55
→ upgrade75
→ canonical75 exacta otra vez.

Además:

data snapshots iguales;
fiscal immutability intacta;
privacy flow PASS;
tenant isolation PASS;
security integrity PASS.

TECHNICAL_ONLY nunca debe poder servir tráfico.

---

# 10. V2 CHECK NORMALIZATION

Revalidar en PostgreSQL18:

source canonical75
→ Backup V2
→ restore.

economic_events_amount_check
debe normalizar a la misma identidad.

La normalización sólo acepta la transformación demostrada:

OR(NULL, AND(AND(LOWER,UPPER),PRECISION))

vs

OR(NULL, AND(LOWER,UPPER,PRECISION)).

Mantener todos los negativos:

different limit -> reject
trunc3 -> reject
operator change -> reject
boolean semantic change -> reject
missing check -> reject
unknown owned column -> reject
extra financial trigger -> reject.

---

# 11. V2 POPULATED A75

Debe terminar:

require_runtime PASS

registry1–75 exacto

fingerprint:
289b8eb580edd4c45d2de40233ffd7dfc193999b10f49825661cba18905696a1

evaluation hash exacto

result canonical exacto

context exacto

activation:
off

generation:
0

ever_enabled:
false

privacy:
NO_E_INSTALLED

serving_authorized:
false

g_real_evidence:
false.

---

# 12. READINESS A75

Ejecutar completa en PG18.

No aceptar resultado parcial.

Registrar:

total
PASS
skip
FAIL
ERROR.

SOURCE_DRIFT debe seguir PASS.

---

# 13. LINEAGE

Ejecutar completa.

Debe cubrir:

advisory lock
timeout30s
two migrators
re-read
crash
rollback
legacy rejection
object guards
retention profiles.

---

# 14. RESULTADO

Sólo si:

general job SUCCESS

PG job SUCCESS

20/20 stages PASS

0 FAIL
0 ERROR

puede declarar:

1.10A75 REMOTE CODE-VERIFIED PASS

con nota:

local WSL remained unusable;
authoritative validation executed on isolated Linux/PostgreSQL18.

---

# 15. SI FALLA

NO otro corrective automático.

Devolver:

1.10A75 REMOTE BLOCKED

con:

stage
test
error
clasificación
si es producto / fixture / infraestructura.

No crear otro commit.

---

# 16. NO AVANZAR

NO:

B76
C77
D78
E79
F80
Recovery Bridge
main merge
deploy
Railway
production
business15
real backups
providers
flags
G-LIVE
H.

---

# ENTREGA

Devuelve:

1.10A75 REMOTE FINAL VALIDATION STATUS

- candidate SHA
- parent
- changed files
- main SHA
- CI run
- general job
- Python totals
- Node
- CRM
- PG totals
- 20/20 stages
- retained53
- retained54
- retained55
- retained58
- TECHNICAL_ONLY authority rejection
- V2 canonicalization
- negative CHECK tests
- V2 populated A75
- Readiness
- Lineage
- advisory/concurrency
- SOURCE_DRIFT
- privacy/rollback
- security gates
- warnings/skips
- Sharp status
- final verdict.

FINAL únicamente:

1.10A75 REMOTE CODE-VERIFIED PASS

o

BLOCKED.