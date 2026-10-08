# FASE 1.10G-PREP — PREPARACIÓN DEL PILOTO REAL, SIN ACTIVACIÓN

Las fases 1.10A–F quedan CODE-VERIFIED PASS.

1.10F:
CODE-VERIFIED PASS TÉCNICO —
REAL PROVIDER ATTESTATIONS PENDING FOR PILOT.

Base exacta autorizada:

981ffc2f26e645aa98792d9968f7d85c1246d688

Crea una nueva rama LOCAL:

codex/phase-1-10g-prep

desde ESE commit.

NO partas de main.

IMPORTANTE:

origin/main ha avanzado desde acff183... a:

08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d

mediante un único commit que sólo elimina sigue.md.

NO rebasees A–F.
NO mezcles main ahora.
NO reescribas historia.

La reconciliación con main se hará posteriormente en una rama de integración
antes de cualquier merge/deploy final.

---

# OBJETIVO

G-PREP NO ES EL PILOTO.

Su objetivo es producir un expediente completo que permita decidir de forma
binaria y humana:

PILOT_READY

o

PILOT_BLOCKED

para UN negocio y UN perfil exacto.

NO activar ningún business.

NO hacer handoff real.

NO poner ever_enabled=true.

NO ejecutar Financial Operations reales.

NO enviar AEAT.

NO enviar WhatsApp.

NO enviar email.

NO realizar provider side effects.

NO cambiar los cinco flags.

NO desplegar.

NO modificar producción.

---

# 1. PRINCIPIO

Fixtures sintéticos ya demostraron el software.

Ahora necesitamos separar rigurosamente:

SOFTWARE VERIFIED

de

REAL-WORLD READY.

No convertir mocks, configuración local ni documentación
en evidencia productiva.

---

# 2. NO NUEVA ARQUITECTURA

G-PREP no debe crear otro Financial Core.

Reutilizar:

A readiness
B antecedents
C capabilities
D activation/handoff
E privacy/export
F providers/preflight

No duplicar contratos.

No crear otra state machine.

No crear otro provider layer.

---

# 3. MIGRACIÓN

Preferencia absoluta:

NO nueva migration.

G-PREP debería ser principalmente:

- control plane;
- verificadores;
- runbooks;
- expediente;
- tests;
- operator tooling.

Si realmente se necesita persistence nueva:

DETENTE y justifica por qué F no contiene ya la evidence necesaria
antes de crear migration80.

No crear migration80 por comodidad.

---

# 4. RESULTADO

Crear contrato cerrado:

PilotReadinessReport v1

Resultado:

PILOT_READY
PILOT_BLOCKED

Nunca:

WARNING = READY.

Cada blocker debe tener:

- reason code;
- evidence reference;
- remediation;
- responsible party;
- requires_external_action bool.

---

# 5. BLOCKERS CERRADOS

Como mínimo:

LEGAL_POLICY_UNAPPROVED
PILOT_BUSINESS_NOT_SELECTED
PILOT_PROFILE_NOT_SELECTED
READINESS_NOT_FULL
READINESS_STALE
HISTORY_BLOCKED
UNSUPPORTED_HISTORY
PRIVACY_NOT_READY
EXPORT_NOT_READY
PROVIDER_ATTESTATION_MISSING
PROVIDER_SAFE_CHECK_UNIMPLEMENTED
PROVIDER_ATTESTATION_STALE
PROVIDER_ENVIRONMENT_MISMATCH
BACKUP_NOT_VERIFIED
RESTORE_NOT_VERIFIED
DEPLOYMENT_COMPATIBILITY_UNKNOWN
RUNTIME_KEY_NOT_VERIFIED
OPERATOR_NOT_ASSIGNED
BACKUP_CUSTODIAN_NOT_ASSIGNED
PAUSE_RUNBOOK_UNVERIFIED
UNKNOWN_RESULT_RUNBOOK_UNVERIFIED
MONITORING_NOT_READY
VOLUME_OUTSIDE_POLICY
BANK_NOT_ALLOWED
ACCOUNT_CLOSING
ACCOUNT_CLOSED
MAIN_INTEGRATION_PENDING

Ajustar naming si existe equivalente.

No strings libres como authority.

---

# 6. POLICY E REAL

La policy REAL continúa:

PROVISIONAL / PENDIENTE DE APROBACIÓN PROFESIONAL.

G-PREP NO puede:

- aprobarla;
- cambiar status;
- crear una approval fake;
- sustituir revisión profesional por criterio del modelo.

Por tanto, mientras siga provisional:

PILOT_READY = IMPOSIBLE.

El report debe devolver:

LEGAL_POLICY_UNAPPROVED
+
PRIVACY_NOT_READY.

Esto NO es un fallo del software.

---

# 7. PROVIDERS REALES

F ha demostrado el contrato, pero:

safe_check() real sigue fail-closed.

No modificarlo para “hacer pasar” G-PREP.

Diseñar exactamente qué check read-only inocuo sería necesario
para cada provider del perfil piloto:

AEAT
Meta
Email

pero NO ejecutarlo todavía salvo autorización separada posterior.

Para cada check documentar:

- endpoint/operación;
- método;
- qué credential usa;
- por qué es read-only;
- qué dato envía;
- qué dato recibe;
- riesgo;
- timeout;
- evidencia que se persistirá;
- cómo evitar PII;
- cómo evitar efectos fiscales/comunicaciones.

Si no existe un check realmente inocuo:

declarar:

SAFE_CHECK_UNIMPLEMENTED

y no fabricar production_config_verified.

---

# 8. PERFIL PILOTO

Proponer el PERFIL MÍNIMO útil.

Preferencia inicial:

sin bank
sin WhatsApp financiero
sin email financiero
sin provider externo

si existe una combinación WEB-ONLY que permita demostrar de forma útil
el Financial Core sin providers externos.

Pero NO asumir que existe.

Derivarlo del capability registry C.

El report debe comparar:

A. web-only mínimo;
B. web + fiscal si Veri*Factu es obligatorio;
C. perfiles con WhatsApp/email.

Para cada perfil:

- capability closure;
- provider requirements;
- blockers actuales;
- riesgo;
- valor que demuestra;
- si puede pilotarse legalmente.

NO reducir un perfil para esconder historia/blockers.

---

# 9. VERIFACTU

Si el perfil piloto requiere emisión Veri*Factu:

provider.aeat_dispatch

debe estar dentro del cierre exacto.

No activar:

invoice.issue

sin su dependencia fiscal correspondiente.

No permitir un “pilot de facturación”
que genere registros fiscales locales
pero no tenga un camino provider real validado
si el contrato exige dicho dispatch.

---

# 10. NEGOCIO PILOTO

NO selecciones automáticamente una cuenta real.

Crear criterios de selección.

Preferencia:

business nuevo o realmente vacío.

Definir EMPTY de forma exacta.

Como mínimo no debe tener:

- facturas emitidas;
- rectificativas;
- cobros;
- received invoices confirmed;
- expenses confirmed;
- bank transactions;
- fiscal cancellation;
- relevant historical ambiguity;
- PREPARED/APPROVED operations;
- uncertain provider attempts.

Clientes/config/drafts pueden existir si no crean hechos económicos.

Crear una checklist.

No leer producción todavía.

---

# 11. REAL DATA ACCESS

G-PREP actual:

NO autoriza consultar producción.

NO autoriza consultar Noesis19FQA.

NO autoriza backups reales.

Preparar únicamente:

- queries read-only necesarias;
- campos necesarios;
- expected outputs;
- redaction rules;
- evidence format.

Después se pedirá autorización humana separada para ejecutarlas.

---

# 12. BACKUP / RESTORE

Crear checklist real para pilot:

- backup reciente;
- ubicación;
- cifrado at-rest verificado;
- custodian;
- restore procedure;
- restore isolation;
- restore test freshness;
- deletion/closure replay E;
- schema79 compatibility;
- rollback procedure.

NO ejecutar backup ni restore real.

Estado actual:

BACKUP_NOT_VERIFIED / RESTORE_NOT_VERIFIED

hasta evidencia real autorizada.

---

# 13. DEPLOYMENT COMPATIBILITY

G-PREP debe definir cómo verificar ANTES de pilot:

- Railway/runtime code SHA;
- DB schema;
- migration79;
- runtime PostgreSQL role;
- verifier/fingerprint keys;
- flags;
- worker versions;
- scheduler version;
- replicas/workers compatibles;
- no old replica sin D/F guards.

NO desplegar.

NO consultar Railway todavía salvo autorización separada.

Crear comandos/queries/runbook.

---

# 14. MAIN DIVERGENCE

Documentar:

A–F branch lineage parte del main anterior.

origin/main actual:

08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d

Cambio adicional:

eliminación de sigue.md únicamente.

G-PREP sigue desde F.

Antes de deploy/pilot será obligatorio:

crear rama de integración DESDE main actual
+
integrar la cadena A–G
+
resolver conflictos
+
CI completa limpia
+
inspección.

NO hacer eso todavía.

---

# 15. OPERATOR MODEL

Definir explícitamente:

Primary operator
Secondary/on-call
Privacy/legal owner
Backup custodian

No inventar personas.

Si no se han asignado:

OPERATOR_NOT_ASSIGNED
BACKUP_CUSTODIAN_NOT_ASSIGNED.

Definir funciones/responsabilidades.

---

# 16. PAUSE RUNBOOK

Usando D/F reales:

crear procedimiento exacto para:

- detectar incidente;
- pause;
- verificar estado;
- detener nuevos attempts;
- identificar drain AEAT permitido;
- identificar HOLD Meta/email;
- revisar Operations pendientes;
- revalidar;
- resume o mantener paused.

No ejecutar.

Debe poder seguirse paso por paso por una persona.

---

# 17. UNKNOWN RESULT RUNBOOK

Separar:

AEAT
Meta
Email.

Debe explicar:

- cómo identificar attempt;
- cómo parar workers;
- qué evidence mirar;
- qué NO repetir;
- cómo comprobar realidad externa;
- quién decide;
- qué registrar;
- cuándo puede reintentarse;
- cuándo queda manual review.

No IA decide un UNKNOWN.

---

# 18. MONITORING

Definir dashboard/read model mínimo para pilot con F:

- activation state;
- generation;
- grants;
- preflight;
- attestation expiry;
- unknown results;
- provider failures;
- outbox ages;
- continuity;
- history;
- privacy;
- closure;
- backup freshness.

No crear sistema de observabilidad externo nuevo.

Reutilizar F.

No enviar alertas.

---

# 19. PILOT STOP CONDITIONS

Definir hard-stop.

Como mínimo:

- integrity mismatch;
- duplicate economic effect;
- stale generation;
- unexpected EE;
- UNKNOWN external result;
- provider credential/config drift;
- preflight expired;
- policy/privacy invalid;
- backup unavailable;
- direct SQL guard failure;
- cross-tenant anomaly;
- fiscal chain mismatch.

Ante cualquiera:

PAUSE / STOP PILOT.

No continuar “a ver si se arregla”.

---

# 20. FIRST REAL OPERATION

Diseñar cuál sería la primera operación REAL
si algún día se autoriza G-LIVE.

Debe ser:

- necesaria;
- pequeña;
- reversible documentalmente cuando corresponda;
- con humano presente;
- con resultado verificable.

NO crear actividad falsa sólo para probar.

NO emitir factura falsa.

NO crear gasto falso en negocio real.

Si el negocio tiene una operación real necesaria,
esa podrá utilizarse cuando se autorice el pilot.

---

# 21. NO FAKE CUSTOMER ACTIVITY

Pilot real no debe contaminar:

- facturación;
- IVA;
- gastos;
- banco;
- clientes;
- fiscal records;

con datos de prueba.

Los smoke tests destructivos permanecen en entornos sintéticos.

---

# 22. PILOT OBSERVATION PLAN

Preparar:

T0
2 horas de atención activa
72 horas de observación

como propuesta operativa inicial,
NO SLO.

Definir qué se revisa:

- inmediatamente;
- +15 min;
- +1 h;
- +2 h;
- +24 h;
- +72 h.

No automatizar notificaciones todavía.

---

# 23. NO 1.10H

G-PREP no audita/cierra 1.10.

H sigue bloqueada.

---

# 24. TESTS

Añadir tests sólo donde G-PREP introduzca código.

Como mínimo probar:

- report con policy provisional → BLOCKED;
- missing provider → BLOCKED;
- missing backup → BLOCKED;
- missing operator → BLOCKED;
- bank requested → blocked;
- exact minimal profile;
- no profile shrinking para ocultar history;
- same evidence → deterministic;
- context drift → stale/new report;
- cross tenant;
- report no contiene secrets/PII;
- main integration pending reason;
- no mutation de A–F.

---

# 25. SIDE EFFECT PROOF

G-PREP debe ser read-only respecto al Financial Core.

Sólo puede escribir:

evidencia propia del report
si es estrictamente necesario.

Preferencia:

report calculado/archivo documental,
sin migration.

NO:

- activation;
- grants;
- generations;
- EE;
- Operations;
- provider attempts;
- provider calls;
- privacy approval;
- flags.

---

# 26. DOCUMENTACIÓN

Crear como mínimo:

FASE-1.10G-prep-orden.md
FASE-1.10G-prep-cierre.md
FINANCIAL-PILOT-RUNBOOK-v1.md
FINANCIAL-PILOT-CHECKLIST-v1.md

Actualizar:

FASE-1.10-plan
Estado
Arquitectura
QA
Tareas
project-state

Registrar explícitamente:

A–F CODE-VERIFIED PASS.
G-LIVE NO AUTORIZADO.
H NO INICIADA.

---

# 27. REAL-WORLD ACTION TABLE

El cierre debe producir una tabla exacta:

BLOCKER
OWNER
EVIDENCE NEEDED
ACTION
CAN CODEX DO IT?
REQUIRES HUMAN?
REQUIRES REAL ACCESS?
RISK

Ejemplos:

Legal policy approval
Provider readonly check
Select pilot business
Backup proof
Restore proof
Runtime compatibility
Operator assignment

---

# 28. NO PUSH INICIAL

Trabaja local.

Al terminar:

NO PUSH.

Devuélveme:

- rama;
- commit;
- padre;
- archivos;
- si hubo migration;
- PilotReadinessReport;
- perfil mínimo recomendado;
- capability closure;
- provider requirements;
- blockers actuales;
- safe provider check design;
- production-read queries necesarias;
- backup/restore checklist;
- deployment checklist;
- operator model;
- pause runbook;
- UNKNOWN runbook;
- monitoring;
- stop conditions;
- first-operation design;
- observation plan;
- tests;
- side-effect proof;
- riesgos;
- limitaciones;
- autoauditoría.

---

# 29. AUTOAUDITORÍA

1. ¿Activó un negocio real?
2. ¿Consultó producción?
3. ¿Consultó Noesis19FQA?
4. ¿Leyó un backup real?
5. ¿Hizo provider I/O?
6. ¿Creó real production attestations?
7. ¿Aprobó la policy E?
8. ¿Cambió PRIVACY_NOT_READY real?
9. ¿Cambió los cinco flags?
10. ¿Hizo handoff?
11. ¿Creó generation/grants?
12. ¿Creó Financial Operation?
13. ¿Creó EE?
14. ¿Creó actividad económica falsa?
15. ¿Seleccionó negocio piloto sin humano?
16. ¿Ocultó un blocker reduciendo perfil?
17. ¿Consideró sandbox/local suficiente para producción?
18. ¿Consideró backup “existente” como restore verificado?
19. ¿Consideró rehearsal sintético como pilot?
20. ¿Rebaseó A–F sobre el nuevo main?
21. ¿Mezcló main en G-PREP?
22. ¿Desplegó?
23. ¿Autorizó G-LIVE?
24. ¿Inició H?

Todas las respuestas peligrosas:

NO.

---

# CRITERIO FINAL

G-PREP sólo puede cerrar:

PILOT_READY

si TODA evidencia real requerida ya existe.

Con el estado actual esperado:

debe cerrar probablemente:

PILOT_BLOCKED — EXTERNAL PREREQUISITES PENDING

Eso es CORRECTO.

No falsear READY.

NO avanzar a G-LIVE.

NO avanzar a H.