# SCHEMA-LINEAGE FOUNDATION + 1.10A75
# IMPLEMENTACIÓN LOCAL
# SIN MAIN / SIN PRODUCCIÓN / SIN DEPLOY

ESTADO DE PARTIDA VERIFICADO

CURRENT MAIN:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

CURRENT MAIN SCHEMA:

74

MIGRATION74:

captacion_hoja_y_tipo

BACKUP V2 CRM74 REMOTE CODE-VERIFIED PASS:

branch:
codex/recovery-backup-v2-crm74

HEAD:

ac6a03d3b70794a4081c3b1d834581e91edb3133

Ancestry:

678bd3f...
→ 01248c5...
→ ac6a03d...

Remote CI:

38412924290

Tests i migracions:
SUCCESS

PostgreSQL18 y POSTGRES_BACKUP_V2 sin outbound:
SUCCESS

NO merge a main.

---

HISTORICAL A

La implementación histórica de 1.10A está en:

branch:
codex/phase-1-10a

SHA exacto:

c9106165195cc053c8d713b7a94557df28bc4099

Ese commit implementaba:

74 / evaluacion_readiness_financiera

y fue CODE-VERIFIED históricamente.

NO cherry-pick ciego.

Usarlo únicamente como FUENTE SEMÁNTICA
de la implementación A original.

La nueva implementación debe ser:

75 / evaluacion_readiness_financiera

sobre CRM74 + Backup V2.

---

DISEÑO APROBADO

Lineage canónica:

74 = CRM
75 = A readiness
76 = B antecedentes
77 = C fiscal cancellation
78 = D handoff/generaciones
79 = E privacy/export/retention
80 = F providers/preflight
G = sin migración, exige canonical80

Esta orden implementa SOLAMENTE:

FOUNDATION DE LINEAGE
+
A75

NO B76–F80.

---

# 1. RAMA

Crear desde exactamente:

ac6a03d3b70794a4081c3b1d834581e91edb3133

rama:

codex/phase-1-10a75

Verificar:

HEAD base exacto = ac6a03d...

No partir de main directamente.

No rebase.

No cherry-pick de c910.

---

# 2. PRINCIPIO

El objetivo NO es:

"cambiar 74 por75 hasta que pasen tests".

El objetivo es:

preservar la semántica completa de A
+
introducir identidad de lineage explícita.

No aceptar nunca:

MAX(version) == identidad.

---

# 3. SCHEMA LINEAGE FOUNDATION

Implementar un módulo central de identidad de schema.

Nombre sugerido:

src/noesis/schema_lineage.py

o equivalente coherente con el repo.

Debe poder clasificar al menos:

CANONICAL_PRE74
CANONICAL_CRM74
CANONICAL_FINANCIAL_75_80_PREFIX
LEGACY_FINANCIAL_74_79
UNKNOWN_OR_CORRUPT

En esta fase sólo existe físicamente hasta canonical75,
pero el diseño puede conocer el catálogo futuro aprobado.

No considerar futuras migrations instaladas hasta que existan.

---

# 4. EXPECTED MIGRATION IDENTITY

La validación debe comprobar:

version
+
name

en orden.

Para schema75 esperado:

1..73 exactos históricos
74 / captacion_hoja_y_tipo
75 / evaluacion_readiness_financiera

No aceptar:

74 / evaluacion_readiness_financiera

como CRM74.

No aceptar:

75 sin A objects.

No aceptar gaps.

No aceptar duplicate version.

No aceptar nombres desconocidos.

No aceptar future81.

---

# 5. FINGERPRINT

Reutilizar exactamente el contrato aprobado:

noesis.schema-lineage.v1

SHA-256
sobre JSON canónico
de pares version/name ordenados.

Sin:

applied_at
secrets
authority.

Golden CRM74 existente debe seguir verificando:

ee2de64c6e47629811c6cee2bfa8f28fea66bb9e23e28caa50bc0b62db697e24

Crear nuevo golden canonical75.

NO modificar el golden CRM74.

---

# 6. MIGRATOR IDENTITY CHECK

Modificar migrations de forma que:

ANTES de upgrade:

valide la identidad completa del registry conocido.

Especialmente:

CRM74
→ puede instalar A75.

Legacy Financial74
→ FAIL CLOSED.

Unknown74
→ FAIL CLOSED.

Corrupt/gap
→ FAIL CLOSED.

No puede continuar basándose sólo en:

MAX(version).

---

# 7. ADVISORY LOCK POSTGRESQL

Implementar el diseño aprobado de serialización del migrador.

Key estable:

2533761095082033151

Timeout:

30 s

PostgreSQL:

advisory transaction lock
+
registry lock antes de snapshot/decisión.

Objetivo:

dos preDeploy concurrentes NO ejecutan DDL simultáneamente.

SQLite conserva su protocolo local existente.

No implementar locks inventados fuera del diseño aprobado.

---

# 8. REVALIDACIÓN

Después de adquirir locks:

releer registry
y volver a validar lineage.

No usar información leída antes del lock
como autoridad.

Fail closed ante drift.

---

# 9. MIGRATION75

Añadir:

75 / evaluacion_readiness_financiera

Semántica debe corresponder a historical A:

c9106165195cc053c8d713b7a94557df28bc4099

Adaptada al contexto actual.

Crear:

financial_activation_control
financial_readiness_evaluations
financial_readiness_capabilities

con los mismos invariantes históricos,
salvo los cambios explícitos de lineage/schema75.

---

# 10. ESTADO INICIAL

Para cualquier business:

activation:

off

generation:

0

ever_enabled:

false

Nada debe activar automáticamente.

Migration75:

NO crea handoff.
NO genera generation1.
NO concede capabilities.
NO provider I/O.
NO Financial Operation.
NO Economic Event.

---

# 11. SCHEMA VERSION EN A

Todos los lugares de historical A que representaban
realmente el PHYSICAL SCHEMA:

74

deben convertirse a:

75.

Incluye:

CHECK(schema_version=...)
evaluation inserts
context
repository
diagnostics
contracts físicos
tests.

Pero NO hacer reemplazo global.

---

# 12. VERSIONES NO FÍSICAS

NO cambiar automáticamente:

payload_version
contract_version
canonical_version
proof_version
economic version
money version
event version

si no representan physical schema.

Mantener semántica histórica.

---

# 13. HASHES

Cualquier hash nuevo de A75 debe construirse
con sus nuevos valores físicos reales.

NO recalcular:

historical A74 hashes.

NO modificar historical branches/docs.

No inventar compatibilidad hash A74→A75.

A75 genera evidencia NUEVA.

---

# 14. OBJECT INTEGRITY PROFILE

Lineage validator no debe acreditar A75 únicamente
porque existe fila75.

Para canonical75,
verificar presencia mínima de objetos A esperados:

financial_activation_control
financial_readiness_evaluations
financial_readiness_capabilities

y constraints/columns críticos definidos por el diseño.

La comprobación no necesita rehacer todo DDL hash
si ya existe el perfil aprobado,
pero debe detectar:

fila75 sin tablas A.

Fail closed.

---

# 15. STARTUP

Runtime A75 debe distinguir:

migration ownership
vs
runtime schema identity.

Normal runtime canonical75:

acepta sólo lineage compatible conocida.

Legacy Financial74–79:

NO serving normal.

Unknown:

NO serving.

No construir todavía Recovery Bridge.

---

# 16. HISTORY

Actualizar history compatibility para canonical75.

Debe reconocer:

73 canonical
74 CRM canonical
75 CRM+A canonical

por IDENTIDAD.

No por simple rango.

Legacy Financial74
debe seguir distinguida y bloqueada
en serving normal.

---

# 17. BACKUP V2

Extender identity classification V2
para canonical75.

Backup V2 de canonical75 debe almacenar:

migration_identities 1..75
schema_lineage_fingerprint canonical75
schema_lineage_id correcto.

Restore:

debe reconstruir exacto75
sin migrations.

Después del restore:

registry exacto
fingerprint exacto
objects exactos
serving_authorized=false.

---

# 18. PRIVACY

A75 NO instala E.

Canonical75 debe resultar:

NO_E_INSTALLED

No:

POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED

por el mero número75.

Legacy historical lineage con E
mantiene su clasificación histórica.

---

# 19. V1

V1 sigue catalog-dependent.

Runner canonical75:

acepta únicamente catálogo exacto canonical75
cuando corresponda.

No promover automáticamente:

V1 CRM74
→75

No reinterpretar:

legacy Financial75
como canonical75.

---

# 20. CI MIGRATION COLLISION GUARD

Implementar el guard permanente aprobado.

Debe verificar:

- migration versions únicas;
- mapping version→name único;
- catálogo append-only contra baseline main autorizado;
- ninguna migration histórica cambia de nombre;
- ninguna desaparece;
- nueva migration es75;
- migration74 sigue siendo CRM;
- no existe segunda74.

Guardar un manifest/baseline canónico versionado
si el diseño lo requiere.

No depender de comentarios.

---

# 21. BRANCH POLICY CHECK

Añadir documentación/gate de ingeniería:

antes de añadir futura migration:

fetch current main
→ inspect latest
→ validate lineage
→ allocate next.

Esto evitará otra colisión futura P2–P16.

---

# 22. TESTS DE LINEAGE

Crear tests explícitos:

canonical73 PASS
canonical CRM74 PASS
canonical CRM74+A75 PASS

reject:

legacy Financial74
legacy Financial75
unknown74
wrong-name74
wrong-name75
row75 missing A objects
gap
duplicate
future76 if migration not yet implemented physically
future81
corrupt registry.

Importante:

future canonical76 está DISEÑADA,
pero todavía NO instalada/aceptada
por este runtime A75.

---

# 23. MIGRATION PATHS

Test obligatorio:

fresh 0→75

73→74→75

canonical74→75

y rejection de:

legacy Financial74→75.

No saltar directamente:

73→75

sin ejecutar CRM74.

---

# 24. DOWNGRADE

Mantener downgrade técnico
sólo dentro del contrato seguro existente.

Probar:

75→74

en DB sintética/empty permitida.

No afirmar rollback productivo.

No borrar evidencia real.

No modificar producción.

---

# 25. CONCURRENCY

PostgreSQL18:

probar dos migradores concurrentes.

Esperado:

uno adquiere lock
otro espera/falla según contrato
NO DDL concurrente
NO duplicate migration75
NO partial state.

Probar timeout.

Probar crash/rollback
si el diseño histórico/approved lo exige.

---

# 26. BORROWED TRANSACTION

Lineage/readiness checks llamados dentro de TX
no deben:

commit
rollback
abrir conexión propia
cambiar isolation silenciosamente.

Preservar patrón borrowed session.

---

# 27. MULTI-TENANT

A75 sigue siendo multi-tenant.

No hardcodear business15.

No lógica especial "pilot business".

Todas las claves/queries:

tenant scoped.

Business15 NO se usa en tests.

---

# 28. FLAGS

Cinco flags deben seguir OFF por defecto.

No añadir activación implícita.

D/G production guards no se relajan.

---

# 29. HISTORICAL A PARITY

Crear matriz de equivalencia semántica contra:

c9106165195cc053c8d713b7a94557df28bc4099

Por cada invariant A histórico:

SAME
ADAPTED FOR LINEAGE
INTENTIONALLY CHANGED

No aceptar pérdidas silenciosas.

---

# 30. TEST SUITE COMPLETA

Ejecutar:

full Python suite
Node
CRM
SQLite
PostgreSQL18
Backup V2
history
Core
Operations/Auth
EE
writers
captures
channels
A75
lineage
migration concurrency
backup/restore75
security gates.

No necesitamos B–G tests nuevos aún,
pero ninguna regresión histórica existente puede romperse.

---

# 31. SECURITY

Secrets
Bandit HIGH/HIGH
Ruff
pip-audit
links
diff-check
project truth.

La alerta:

sharp HIGH

sigue como:

SEPARATE SECURITY DEBT
PRE-PRODUCTION TRIAGE REQUIRED

No resolver en esta fase.

---

# 32. DOCUMENTACIÓN

Actualizar de forma factual:

schema target local =75 candidate

pero NO decir que producción está75.

Producción sigue:

CRM74.

Preservar:

historical A74 closure
historical A–G evidence
Backup V2 historical docs
CRM74 docs.

Crear cierre nuevo:

FASE-1.10A75-cierre.md

o equivalente coherente.

---

# 33. NO PUSH INICIAL

Primero implementación LOCAL.

NO push.

NO PR.

NO main.

NO deploy.

---

# 34. RESULTADO

Cerrar sólo si:

LINEAGE FOUNDATION PASS

+
A75 semantic parity PASS

+
0→75 PASS

+
74→75 PASS

+
legacy74 rejection PASS

+
concurrency PASS

+
Backup V2 canonical75 PASS

+
full regression PASS

+
security PASS.

Etiqueta:

1.10A75 LOCAL CODE-VERIFIED PASS

No REMOTE todavía.

---

# 35. ENTREGA

Devuelve:

1.10A75 STATUS

1. branch;
2. base SHA;
3. final local SHA;
4. parent;
5. changed files;
6. LATEST_VERSION;
7. migration74 identity;
8. migration75 identity;
9. lineage states implemented;
10. canonical75 fingerprint;
11. validator behavior;
12. object integrity behavior;
13. advisory lock behavior;
14. collision CI guard;
15. A historical parity matrix;
16. startup behavior;
17. history compatibility;
18. V1 behavior;
19. V2 canonical75 behavior;
20. privacy classification;
21. migration paths;
22. downgrade synthetic;
23. concurrency tests;
24. Python totals;
25. PostgreSQL totals;
26. Node totals;
27. CRM totals;
28. A75-specific totals;
29. lineage totals;
30. security gates;
31. skips/warnings;
32. remaining risks.

Confirmar:

NO B76
NO C77
NO D78
NO E79
NO F80
NO Recovery Bridge
NO production
NO business15
NO main
NO push
NO deploy
NO flags
NO G-LIVE
NO H.

FINAL:

1.10A75 LOCAL CODE-VERIFIED PASS

o:

BLOCKED

con causa exacta.