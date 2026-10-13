# SCHEMA-LINEAGE-75–80
# DISEÑO CANÓNICO DE RECONCILIACIÓN Y REVALIDACIÓN
# SOLO DOCUMENTACIÓN / SIN IMPLEMENTACIÓN

ESTADO AUTORIZADO

MAIN ACTUAL Y PRODUCCIÓN:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

PRODUCTION SCHEMA:

74

MIGRATION74 DURABLE:

74 / captacion_hoja_y_tipo

CRM74 YA ESTÁ APLICADA EN PRODUCCIÓN.

Por tanto:

NO renombrar.
NO borrar.
NO reutilizar.
NO alterar applied_at.
NO reinterpretar 74 como Financial A.

---

CADENA FINANCIAL HISTÓRICA AUDITADA

SHA G-VERIFY histórico:

87055215bcbacf6fefa9f6473a87a7d208885f0c

Mapeo histórico:

74 = A readiness
75 = B antecedentes
76 = C fiscal cancellation
77 = D handoff/generaciones
78 = E privacy/export/retention
79 = F providers/preflight

Esa cadena queda preservada como EVIDENCIA HISTÓRICA.

NO reescribirla.

NO force push.
NO rebase.
NO editar commits históricos.

---

NUEVA CADENA CANÓNICA PROPUESTA

74 = CRM / captacion_hoja_y_tipo

75 = Financial A / evaluacion_readiness_financiera
76 = Financial B / resoluciones_antecedentes_financieros
77 = Financial C / cobertura_cancelacion_fiscal_live
78 = Financial D / activacion_handoff_generaciones
79 = Financial E / privacy_export_retention_closure
80 = Financial F / providers_preflight_dispatch_evidence

G:
sin migration física nueva.

Target de G:
schema80.

---

BACKUP V2 HISTÓRICO LOCAL

branch:

codex/recovery-backup-v2

commit:

f272582663f35a6e1c6ed9e34e8b0e737d235b49

parent:

08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d

NO modificar.
NO publicar.
NO rebasear.

Debe preservarse como evidencia técnica histórica
y portarse posteriormente a main actual mediante una nueva rama.

---

RECOVERY BRIDGE

Sigue:

BLOCKED.

NO implementar todavía.

El target futuro principal será:

CANONICAL CRM74 ↔ FINANCIAL80

No aceptar silenciosamente la antigua lineage:

Financial74–79.

---

OBJETIVO DE ESTA FASE

Diseñar el contrato completo para una nueva lineage de schema
que elimine para siempre la ambigüedad causada por comparar solamente:

MAX(schema_migrations.version)

No queremos únicamente renumerar.

Queremos que Bynoesis pueda demostrar:

"estoy en schema80 CANÓNICO"

y no simplemente:

"MAX(version)=80".

---

# 1. PRINCIPIO DE IDENTIDAD

Diseñar una noción explícita de:

SCHEMA LINEAGE IDENTITY

Una versión física NO es suficiente.

Debe distinguir como mínimo:

CANONICAL_PRE74
CANONICAL_CRM74
CANONICAL_CRM74_FINANCIAL75_80
LEGACY_FINANCIAL74_79
UNKNOWN_OR_CORRUPT

Nombres concretos pueden cambiar en diseño,
pero la semántica debe existir.

---

# 2. NO MAX-ONLY

El migrador actual usa MAX(version).

Eso permitió que:

CRM74

pudiera ser interpretada erróneamente como si A74
ya estuviera instalada.

Diseñar un validator previo que inspeccione:

schema_migrations.version
+
schema_migrations.name

para TODA la lineage aplicada.

Antes de:

upgrade
downgrade
startup
readiness
activation
restore
preflight

debe poder detectar identidad incompatible.

---

# 3. EXPECTED MIGRATION IDENTITY

Diseñar una fuente canónica, por ejemplo conceptualmente:

EXPECTED_MIGRATION_IDENTITIES = {
    1: "...",
    ...
    73: "reconciliacion_historica_durable",
    74: "captacion_hoja_y_tipo",
    75: "evaluacion_readiness_financiera",
    76: "resoluciones_antecedentes_financieros",
    77: "cobertura_cancelacion_fiscal_live",
    78: "activacion_handoff_generaciones",
    79: "privacy_export_retention_closure",
    80: "providers_preflight_dispatch_evidence",
}

No implementar todavía.

Definir:

- qué valida;
- cuándo;
- errores;
- cómo se comporta con schemas parciales;
- qué ocurre con tablas/filas ausentes;
- qué ocurre con nombres inesperados.

---

# 4. LINEAGE FINGERPRINT

Evaluar y diseñar un fingerprint canónico de lineage.

Por ejemplo:

SHA-256(
  version || ":" || migration_name
  para todas las migrations aplicadas en orden
)

El objetivo NO es seguridad criptográfica de autoridad.

El objetivo es identidad inequívoca y binding.

Debe poder usarse en:

- readiness;
- deployment evidence;
- restore manifest;
- PilotGate context;
- preflight;
- recovery;
- integration evidence.

Analizar pros/contras.

---

# 5. NO REESCRIBIR EVIDENCIA VIEJA

Todos los artefactos de la cadena histórica74–79:

evaluations
receipts
proofs
manifests
handoffs
preflights
hashes
snapshots
contexts

conservan sus valores originales.

NO:

74→75 por sustitución
75→76
...
79→80

dentro de evidencia histórica.

Un hash histórico debe seguir verificando
contra el contenido histórico original.

La nueva cadena crea NUEVA evidencia.

No recalcular hashes antiguos para que parezcan nuevos.

---

# 6. CONTRATOS DE PAYLOAD

Distinguir:

schema_version física

de:

payload_version
contract_version
proof_version
canonical_version.

No renumerar automáticamente cualquier literal74–79.

El inventario anterior ya detectó falsos positivos.

Definir reglas exactas de qué campos deben cambiar
y qué campos NO.

---

# 7. LEGACY FINANCIAL74–79

Tenemos laboratorios/branches/backups que pueden contener:

74 evaluacion_readiness_financiera

en vez de:

74 captacion_hoja_y_tipo.

Diseñar detección explícita.

Si se encuentra:

74 / evaluacion_readiness_financiera

clasificar:

LEGACY_FINANCIAL74_79

NO auto-promover.

NO añadir CRM74 encima.

NO fingir canonical lineage.

NO ejecutar Financial75 esperando arreglarlo.

Debe:

FAIL CLOSED

salvo workflow aislado de recuperación
específicamente diseñado posteriormente.

---

# 8. SCHEMA73

Definir camino canónico:

73
→ CRM74
→ Financial75
→ 76
→ 77
→ 78
→ 79
→ 80

Esto importa para:

- restore histórico;
- instalaciones previas;
- test from scratch.

No usarlo todavía en producción.

Producción ya es74.

---

# 9. SCHEMA74 CANÓNICO

Producción real tiene:

74 / captacion_hoja_y_tipo.

El camino principal debe ser:

CRM74
→ A75
→ B76
→ C77
→ D78
→ E79
→ F80.

Definir preconditions exactas de cada paso.

---

# 10. A75

Anteriormente A74.

Diseñar todos los cambios necesarios.

Incluye como mínimo:

- migrations registry;
- financial readiness schema;
- CHECK(schema_version=...);
- evaluator;
- repository inserts;
- contracts;
- context serialization;
- tests;
- diagnostics.

A75 sólo puede instalarse si:

74 == captacion_hoja_y_tipo

en lineage canónica.

---

# 11. B76

Anteriormente B75.

Diseñar:

- schema contracts;
- antecedent resolution;
- proof/version guards;
- A dependency;
- tests;
- serialized context.

Debe depender de:

A75 real instalada.

No sólo MAX>=75.

---

# 12. C77

Anteriormente C76.

Diseñar:

- fiscal cancellation capture;
- capability catalog;
- dependency closure;
- tests;
- guards.

No cambiar su semántica,
sólo adaptar identidad física correctamente.

---

# 13. D78

Anteriormente D77.

Es especialmente sensible.

Diseñar revisión de:

- activation control;
- handoff;
- generations;
- pause;
- recovery;
- baseline/hash;
- borrowed execution;
- generation origin;
- fence;
- ever_enabled;
- history binding.

El cambio físico77→78 altera metadata capturada/hashes.

Definir qué se recalcula NUEVO
y qué histórico permanece intacto.

---

# 14. E79

Anteriormente E78.

Diseñar revisión completa de:

- privacy;
- retention;
- export;
- closure;
- deletion/suppression;
- restore;
- manifest;
- readiness.

IMPORTANTE:

Backup V2 actualmente usa:

schema >=78
→ POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED

Con la nueva canonical lineage:

E aparece en79.

Diseñar la nueva regla por:

CAPABILITY / LINEAGE IDENTITY

y no simplemente por:

schema >=79

si puede evitarse.

Objetivo:

no aplicar semántica E a un schema que sólo tenga D78
por accidente de número.

---

# 15. F80

Anteriormente F79.

Diseñar:

- providers;
- attestations;
- configuration;
- preflight;
- dispatch;
- recovery;
- production observations;
- context binding;
- validation;
- tests.

Todos los guards exactos79
deben convertirse de forma segura a la identidad F80.

No usar >=80 de forma genérica.

---

# 16. G SOBRE80

G no añade migration.

Diseñar actualización de:

VerificationContext
RecoveryReadiness
PilotVerifiers
PilotGate
deployment verification
MAIN_INTEGRATION
backup/restore verification
resume continuity.

Nuevo contexto real:

schema80
+
canonical lineage.

---

# 17. HISTORY COMPATIBILITY

Main actual ya permite CRM74 en:

diagnostic
cutoff
import
reconciliation.

Diseñar matrices nuevas:

DIAGNOSTIC:
70...80 según contratos reales.

CUTOFF:
71...80.

IMPORT:
72...80.

RECONCILIATION:
73...80.

PERO cada número>=74 debe validar
la identidad correspondiente.

No asumir que cualquier74 es CRM74.

Una legacy Financial74 no debe entrar
por el mismo camino sin clasificación explícita.

---

# 18. MIGRATOR FAIL-CLOSED

Diseñar nuevos errores cerrados.

Ejemplos conceptuales:

SCHEMA_LINEAGE_MISMATCH
MIGRATION_IDENTITY_MISMATCH
LEGACY_FINANCIAL_LINEAGE_DETECTED
UNKNOWN_SCHEMA_LINEAGE
MIGRATION_GAP
FUTURE_SCHEMA_UNSUPPORTED

No usar mensajes vagos únicamente de:

"schema no actualizado".

---

# 19. STARTUP

Diseñar diferencia entre:

migration catalog ownership

y:

runtime compatibility.

Esto será necesario después para el Recovery Bridge.

El código normal canonical80:

debe exigir su lineage exacta.

El bridge:

tendrá reglas distintas,
pero reutilizará el mismo detector de identidad.

---

# 20. DOWNGRADE

Diseñar política explícita.

A–F ya contienen historia/evidencia durable.

No asumir:

80→74

como rollback productivo.

Separar:

schema downgrade técnico

de:

operational rollback.

Preferencia operacional:

rollback runtime compatible
sin downgrade destructivo.

Definir qué downgrades permanecen sólo para:

tests
empty synthetic databases
isolated recovery.

---

# 21. BACKUP V2 PORT

Diseñar cómo portar:

f272582663f35a6e1c6ed9e34e8b0e737d235b49

al main actual.

NO hacerlo todavía.

Nueva futura rama debe partir de:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

y preservar:

- CRM74;
- CRM code;
- Node local_dates;
- current pyproject;
- scheduler;
- current admin/router layout.

Portar funcionalidad V2,
NO restaurar una fotografía de base08.

---

# 22. BACKUP V2 MANIFEST

Proponer que V2 conserve además de:

schema_version

una identidad de lineage,
por ejemplo:

schema_lineage_fingerprint
migration_identity

o equivalente.

Restore debe verificar ambos.

Un archive80 debe restaurarse EXACTAMENTE como80 canónico.

No editar schema_migrations durante restore.

---

# 23. V1

Diseñar comportamiento V1 tras el cambio.

V1 es dependiente del catálogo.

No relajar.

Ejemplos:

V1 schema73
→ runner/catalog73 adecuado.

V1 canonical CRM74
→ runner/catalog74 adecuado.

V1 legacy Financial79
→ NO tratar como canonical79.

Debe identificar lineage
o fallar cerradamente si no puede demostrarla.

---

# 24. RECOVERY BRIDGE

Diseño objetivo posterior:

canonical CRM74 ↔ canonical Financial80.

El bridge debe poder arrancar sobre:

canonical74
canonical80

y quizá 75–79 canonical intermedios
SÓLO si existe necesidad operacional demostrada.

NO debe aceptar:

legacy Financial74–79

por coincidencia de número.

Diseñar matriz exacta.

---

# 25. MIGRATION CONCURRENCY

Incluir en el diseño:

PostgreSQL advisory lock

para serializar:

migrations.upgrade

en Railway/preDeploy.

Debe impedir que dos deployments concurrentes
ejecuten DDL simultáneamente.

Definir:

- key estable;
- timeout;
- lock lifetime;
- failure behavior;
- tests.

NO implementar ahora.

---

# 26. MIGRATION COLLISION CI GUARD

Diseñar protección permanente para que esto
NO vuelva a ocurrir.

CI debe comprobar como mínimo:

- versión única;
- nombre único donde corresponda;
- append-only;
- ninguna versión histórica cambia de nombre;
- ninguna migration desaparece;
- lineage baseline conocida;
- migrations nuevas sólo después de latest main.

Idealmente mantener un artifact/manifest canónico versionado
que CI compare.

Diseñar la solución.

---

# 27. PARALLEL BRANCH POLICY

Definir regla de ingeniería:

NINGUNA branch larga puede reservar una migration number
sin reconciliarla contra current main antes de merge/deploy.

Para futuras P2–P16:

cada fase antes de integración debe:

fetch current main
→ inspect latest migration
→ allocate next migration
→ CI collision check.

Documentar política.

---

# 28. TEST MATRIX FUTURA

Diseñar matriz exacta a ejecutar cuando implementemos.

Mínimo:

fresh DB 0→80
73→80
canonical CRM74→80

y rechazo de:

legacy Financial74
legacy Financial75
...
legacy Financial79
unknown74
gap
wrong name
future81.

También:

SQLite
PostgreSQL18
migration up/down synthetic
history
A
B
C
D
E
F
G
Backup V1
Backup V2
restore
privacy replay
recovery
preflight
UNKNOWN
pause/resume
cross-tenant
crash/concurrency
HTTP
legacy
security.

---

# 29. HASH / CANONICAL AUDIT

Crear una tabla de TODOS los contenidos cuyo hash/canonical
puede cambiar al renumerar:

- A evaluation;
- D handoff/generation;
- E manifests;
- F attestations;
- F preflight;
- G VerificationContext;
- recovery proofs;
- deployment evidence;
- integration evidence;
- backup manifest.

Para cada uno:

OLD FIELD
OLD VALUE
NEW FIELD
NEW VALUE
HASH IMPACT
LEGACY READ?
NEW WRITE?
REUSE ALLOWED?

No implementar.

---

# 30. MAIN_INTEGRATION

La antigua:

822c99e...

queda como integración histórica válida
contra su main de entonces.

NO reutilizarla como nueva MAIN_INTEGRATION.

Después de implementar nueva lineage,
habrá que crear una NUEVA integración:

current future main
+
Financial canonical75–80
+
Backup V2 port
+
bridge/recovery changes aplicables.

Con nueva CI.

---

# 31. A–G AUDIT STATUS

No borrar los PASS anteriores.

Clasificarlos:

HISTORICAL CODE-VERIFIED
FOR LEGACY FINANCIAL74–79 LINEAGE

La nueva chain75–80 necesitará:

NEW CODE-VERIFIED PASS.

No decir que estamos "rehaciendo desde cero".

Arquitectura y invariantes se conservan;
cambia identidad física y bindings.

---

# 32. PRODUCCIÓN

NO acceso producción.

Ya tenemos evidencia suficiente:

production canonical CRM74.

No volver a consultar en esta fase.

---

# 33. BUSINESS15

No tocar.

Sigue reservado.

No EMPTY.
No writes.
No evidence.

---

# 34. DOCUMENTOS A CREAR

Sólo documentación local.

Como mínimo:

docs/architecture/ADR-SCHEMA-LINEAGE-001-crm74-financial75-80.md

docs/architecture/SCHEMA-LINEAGE-75-80-contract.md

docs/architecture/SCHEMA-LINEAGE-75-80-mapping.md

docs/architecture/SCHEMA-LINEAGE-75-80-hash-impact.md

docs/architecture/SCHEMA-LINEAGE-75-80-test-matrix.md

docs/architecture/SCHEMA-LINEAGE-75-80-implementation-order.md

docs/architecture/SCHEMA-LINEAGE-75-80-cierre.md

NO modificar código.

NO tests funcionales necesarios salvo validadores documentales.

---

# 35. ORDEN DE IMPLEMENTACIÓN POSTERIOR

Diseñar exactamente esta secuencia,
pero NO ejecutarla:

1. aprobar diseño lineage;
2. port Backup V2 a current main;
3. publicar Backup V2 port;
4. CI remota Backup V2;
5. implementar canonical Financial75–80
   sobre current main + V2;
6. full local CI;
7. remote CI;
8. implementar Recovery Bridge canonical74↔80;
9. validar bridge74;
10. validar bridge80;
11. backup/restore drill real aislado;
12. nueva integration candidate;
13. full remote CI;
14. PREDEPLOY GO/NO-GO;
15. explicit deploy authorization;
16. bridge deploy;
17. verify bridge live74;
18. Financial80 rollout;
19. rollback to bridge if needed;
20. business15 EMPTY formal;
21. human/legal blockers;
22. G-LIVE separate authorization;
23. H final audit.

Evaluar si algún paso debe reordenarse
por una razón concreta de seguridad.

---

# 36. CRITERIO DE CIERRE

Cerrar únicamente:

SCHEMA-LINEAGE-75-80 DESIGN PASS

si el diseño:

- preserva CRM74 productivo;
- preserva historia Financial74–79;
- define nueva canonical75–80;
- elimina MAX-only ambiguity;
- distingue physical schema / lineage / payload versions;
- protege hashes históricos;
- define Backup V2 port;
- define bridge74↔80;
- define CI collision guard;
- define full revalidation matrix;
- no requiere reescribir producción.

---

# 37. ENTREGA

Devuelve:

SCHEMA-LINEAGE-75-80 DESIGN STATUS

con:

- mapping final;
- lineage states;
- lineage fingerprint design;
- migrator identity validation;
- startup rules;
- downgrade rules;
- legacy74–79 rules;
- A75 changes;
- B76 changes;
- C77 changes;
- D78 changes;
- E79 changes;
- F80 changes;
- G80 changes;
- history compatibility;
- Backup V1;
- Backup V2;
- Recovery Bridge;
- hash/canonical matrix;
- migration concurrency design;
- CI collision guard;
- test matrix;
- implementation order;
- risks;
- blockers.

AUTOAUDITORÍA:

NO code implementation
NO production access
NO production writes
NO migration
NO Backup V2 modification
NO A–G history rewrite
NO bridge implementation
NO push
NO merge
NO deploy
NO financial operations
NO G-LIVE
NO H.

FINAL:

SCHEMA-LINEAGE-75-80 DESIGN PASS

o:

DESIGN BLOCKED

con causa exacta.