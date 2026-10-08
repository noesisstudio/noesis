# 1.10G-VERIFY — PILOT GATE Y CONTINUIDAD DE READINESS
# TODAVÍA SIN ACCESO REAL NI G-LIVE

A–F y G-PREP quedan CODE-VERIFIED PASS.

G-PREP:
PILOT_BLOCKED — EXTERNAL PREREQUISITES PENDING.

Base exacta autorizada:

42fcf529efb40fedba9debddd47332a196ee03a8

Crea una rama LOCAL:

codex/phase-1-10g-verify

desde ESE commit.

NO partas de main.
NO rebasees.
NO mezcles main.
NO hagas push inicialmente.
NO deploy.
NO producción.
NO Noesis19FQA.
NO backups reales.
NO provider I/O.
NO G-LIVE.
NO H.

---

OBJETIVO

Resolver EXCLUSIVAMENTE los prerequisitos técnicos que todavía impiden
que, en una autorización futura, podamos transformar evidencia REAL
verificada en una decisión PILOT_READY/PILOT_BLOCKED.

G-VERIFY NO resuelve los prerequisitos humanos/reales.

Debe dejar listo el mecanismo para verificarlos posteriormente.

Los dos objetivos técnicos principales son:

A. REAL-EVIDENCE VERIFICATION GATE
B. RESUME READINESS CONTINUITY D79

---

# A. REAL-EVIDENCE VERIFICATION GATE

G-PREP actualmente es deliberadamente anti-READY.

NO cambies `assess()` para aceptar:

approved=true
verified=true
PASS
hash
JSON
reference

como autoridad.

Mantener G-PREP documental e incapaz de producir READY.

Crear una capa SEPARADA de verificación futura.

Nombre orientativo:

financial_pilot/verifiers.py
financial_pilot/gate.py

o estructura equivalente.

---

# 1. PRINCIPIO

REFERENCE != VERIFIED EVIDENCE.

DOCUMENT != VERIFIED EVIDENCE.

HASH != VERIFIED EVIDENCE.

HUMAN CLAIM != DATABASE FACT.

SYNTHETIC != REAL.

La única forma de retirar un blocker debe ser mediante
un verificador explícito del tipo de evidencia correspondiente.

---

# 2. VERIFIER CATALOG CERRADO

Crear catálogo cerrado/versionado para prerequisitos reales.

Como mínimo:

LEGAL_POLICY
PILOT_BUSINESS
PILOT_PROFILE
READINESS
HISTORY
PRIVACY
EXPORT
PROVIDER_ATTESTATION
BACKUP
RESTORE
DEPLOYMENT_COMPATIBILITY
RUNTIME_KEY
OPERATORS
BACKUP_CUSTODIAN
PAUSE_RUNBOOK
UNKNOWN_RUNBOOK
MONITORING
MAIN_INTEGRATION
PRODUCTION_ACTIVATION
RESUME_CONTINUITY

No strings libres.

---

# 3. CADA VERIFIER DEBE DEFINIR

- evidence type;
- business scope;
- required authority;
- source;
- validation algorithm;
- freshness/expiry;
- canonical proof;
- failure reasons;
- whether real access is required;
- whether human confirmation is required.

No genérico:

verify("something", True)

---

# 4. EVIDENCE TYPES

Distinguir al menos:

SYSTEM_DERIVED
HUMAN_ATTESTED
EXTERNAL_PROVIDER_DERIVED
LEGAL_REVIEW_DERIVED
BACKUP_DRILL_DERIVED
DEPLOYMENT_DERIVED

Cada tipo tiene reglas distintas.

No una clase `verified=true`.

---

# 5. LEGAL POLICY

NO implementar aprobación legal automática.

El verifier únicamente debe poder verificar en el futuro que existe:

- policy E exacta;
- status approved_for_operation;
- approval receipt humano;
- policy hash;
- actor/authority;
- timestamp;
- version.

No crear esa approval.

Tests:
policy provisional → FAIL.
synthetic approved fixture → PASS estructural.

Configuración real sigue provisional.

---

# 6. PILOT BUSINESS

Crear verifier del criterio EMPTY exacto.

No leer producción ahora.

Debe reutilizar las tablas reales A–F y devolver structured result.

EMPTY no significa solo:

invoice count = 0.

Debe contemplar:

- invoices/rectifications;
- payments;
- supplier invoices;
- confirmed expenses;
- bank;
- fiscal cancellation;
- financial operations;
- pending authorities;
- economic events;
- provider attempts/results;
- historical ambiguity;
- closure state.

Draft/documental no económico puede existir según contrato.

Tests sintéticos completos.

---

# 7. PILOT PROFILE

Debe aceptar únicamente selección HUMANA explícita
del profile A exacto.

No optimizarlo.

No reducir closure.

Verificar contra capability registry C.

Persistencia sólo si ya existe infraestructura adecuada;
preferencia no migration nueva.

---

# 8. READINESS

Reutilizar A.

No reimplementar FULL.

Debe verificar:

- business;
- exact profile;
- FULL;
- content hash;
- freshness;
- configuration;
- source state;
- capability proofs.

No editar evaluación antigua.

---

# 9. HISTORY / B

Reutilizar verifiers existentes.

No transformar:

observed_state → verified_fact.

No resolver UNSUPPORTED_HISTORY automáticamente.

---

# 10. PRIVACY / EXPORT

Reutilizar E.

Verificar:

- approved policy real;
- privacy state;
- export manifest vigente;
- exact tenant/context.

No crear export desde el pilot gate salvo acción explícita futura.

---

# 11. PROVIDERS

Reutilizar F.

No provider network desde gate.

Sólo verificar attestations reales existentes:

production_config_verified

del provider/environment/capability exacto.

No aceptar:

local_verified
sandbox_verified

para producción.

---

# 12. BACKUP

Diseñar verifier future-facing que consuma únicamente metadata segura:

- backup UUID/reference;
- created_at;
- hash;
- encryption verified;
- custodian;
- storage class/location class;
- access verification;
- business/system scope.

NO leer backup.

NO recibir DB URL/path secreto.

Synthetic fixture only.

---

# 13. RESTORE

RESTORE_NOT_VERIFIED sólo se retira con evidence de drill:

- backup exacto;
- isolated environment;
- schema expected;
- restore result;
- integrity hashes;
- E tombstone replay;
- completed_at;
- operator/custodian;
- result PASS.

“Tenemos backup” NO basta.

---

# 14. DEPLOYMENT

Verifier futuro debe comprobar evidence de:

- exact code SHA;
- schema79;
- every web replica;
- every financial worker;
- scheduler;
- DB runtime role;
- required keys accessible by correct role;
- forbidden keys inaccessible;
- flags exactos;
- no old replica.

No consultar Railway ahora.

Tests sintéticos.

---

# 15. OPERATORS

NO inventar personas.

Verifier sólo admite asignaciones humanas futuras
con roles cerrados:

primary_operator
secondary_on_call
privacy_legal_owner
backup_custodian
engineering_owner
business_holder

No PII necesaria dentro del report público.

Usar IDs/references privados si se persiste.

---

# 16. RUNBOOK VERIFICATION

PAUSE_RUNBOOK_UNVERIFIED y UNKNOWN_RESULT_RUNBOOK_UNVERIFIED

NO se eliminan porque exista un Markdown.

Deben exigir en el futuro evidence de:

- rehearsal identifier;
- scenario;
- operator;
- completed_at;
- result;
- failures;
- accepted version/hash del runbook.

Fixtures sintéticos pueden demostrar contrato.

---

# 17. MONITORING

Reutilizar observability F.

Verifier debe exigir que el operador pueda leer:

- activation;
- G;
- grants;
- preflight;
- provider expiry;
- pending/unknown;
- closure;
- history;
- backup freshness reference.

No alertas externas en esta fase.

---

# 18. MAIN INTEGRATION

No integrar main todavía.

Crear/verificar contrato para una evidencia futura:

integration_base_sha
financial_chain_sha
integration_sha
CI run
CI conclusion
review result

`MAIN_INTEGRATION_PENDING` sólo desaparece con:

rama desde main vigente
+
A–G integrated
+
CI completa limpia
+
inspección.

No realizarla en G-VERIFY.

---

# 19. PILOT GATE

Crear:

PilotGate

o equivalente.

Input:
verified evidence objects producidos exclusivamente por verifiers.

No referencias libres.

Debe producir:

PILOT_READY
o
PILOT_BLOCKED.

READY sólo si:

- exact business;
- exact profile;
- no blocker;
- all required verifiers PASS;
- all evidence current;
- evidence context hashes coherent;
- no cross-tenant;
- no unsupported condition;
- real/software distinction maintained.

---

# 20. READY NO ES ACTIVATION

Incluso PILOT_READY:

activation_authorized = FALSE.

PilotGate READY significa:

prerequisitos satisfechos.

NO significa:

handoff autorizado.

G-LIVE requerirá una aprobación humana separada posterior.

---

# 21. IDEMPOTENCIA / TAMPERING

El resultado debe ser canonical y verificable.

Alterar:

- evidence;
- blocker;
- profile;
- business;
- hash;
- result;

debe invalidarlo.

No editar report viejo.

---

# B. RESUME READINESS CONTINUITY D79

Actualmente G-PREP documenta:

si A original caduca después de pause,
D79 resume queda bloqueado.

Resolver técnicamente SIN debilitar A/D.

---

# 22. PRINCIPIO

Resume NO puede depender de una evaluación A temporalmente vigente
para siempre.

Pero tampoco puede:

- reutilizar A stale sin prueba;
- crear FULL artificial;
- resetear ever_enabled;
- volver a legacy;
- crear una nueva historical activation.

Necesitamos una prueba de CONTINUIDAD LIVE.

---

# 23. RECOVERY READINESS v1

Diseñar contrato explícito para paused→resume.

Debe verificar el MISMO:

- business;
- profile;
- capability closure;
- grant set;

de la última generación válida.

NO ampliar/reducir capabilities.

---

# 24. FUENTES DE CONTINUIDAD

Como mínimo:

- original handoff receipt;
- previous generation;
- pause receipt;
- grants;
- configuration;
- source witnesses;
- no unexpected financial effects;
- no unexpected EE;
- history certification intact;
- E privacy current;
- F providers/preflight current;
- closure not active;
- account not closed;
- no corruption;
- operator/session current.

---

# 25. A ORIGINAL

Conservar A original como provenance.

No editarla.

No exigir que su TTL siga activo meses después.

En cambio:

revalidar AHORA las mismas invariantes aplicables
mediante current source verifiers.

Original evaluation hash sigue siendo ancestor/provenance.

---

# 26. NO NUEVA ACTIVACIÓN

Recovery readiness no genera:

new first activation evaluation.

No cambia ever_enabled.

No reactiva fence.

No nueva history import.

Es continuidad de un business ya live.

---

# 27. NEW GENERATION

Resume exitoso sigue creando G+1 mediante D.

Authority vieja no revive.

Operations/auth/mandates G anterior siguen inválidos.

---

# 28. PROVIDERS EN RESUME

Debe exigir F evidence actual.

Una attestation válida en G anterior pero ahora stale:

BLOCK.

No reutilizar provider evidence caducada.

---

# 29. PRIVACY EN RESUME

Policy E debe seguir válida/aprobada.

Closing/closed:

BLOCK.

---

# 30. RECOVERY DRIFT

Si existe drift no permitido:

permanece PAUSED.

No auto-repair.

No profile change dentro de este recovery.

---

# 31. INTEGRACIÓN D79

Modificar D únicamente de forma aditiva/compatible
para schema79/current code.

No modificar receipts históricos.

No reescribir request hashes antiguos.

El nuevo recovery proof se usa sólo en nuevos resumes.

Asegurar compatibilidad con existing pause receipts.

---

# 32. MIGRATION

Preferencia:

sin migration80.

Si los contracts/tables D/F actuales no permiten guardar
la nueva proof necesaria:

antes de crear migration80:

documentar exactamente por qué.

Si migration80 es imprescindible:
- aditiva;
- no modificar 63–79;
- downgrade sólo si evidence nueva vacía;
- guards SQLite/PostgreSQL;
- revisión específica.

---

# 33. TEST CRÍTICO

Synthetic business:

A FULL
→ D enable
→ tiempo avanza y A expira
→ pause
→ recovery evidence actual intacta
→ resume
→ G+1 PASS.

Debe demostrar:

A TTL expirado NO impide continuidad segura.

---

# 34. TEST NEGATIVO

A expira
→ pause
→ source drift

BLOCK.

A expira
→ provider stale

BLOCK.

A expira
→ privacy invalid

BLOCK.

A expira
→ unknown external result

BLOCK.

A expira
→ profile changed

BLOCK.

---

# 35. NO REAL ACCESS

Todos estos tests:

synthetic only.

NO producción.
NO Railway.
NO providers.
NO backup real.

---

# 36. SIDE EFFECT PROOF

PilotGate/verifiers:

read-only.

Recovery verifier:

read-only.

Sólo D resume autorizado sintético puede crear nueva generation
en tests.

No real activation.

---

# 37. CI

Ejecutar al menos:

- nuevos G-VERIFY tests;
- G-PREP;
- D handoff/recovery;
- E;
- F;
- A readiness;
- B antecedents;
- Operations/Auth;
- EconomicEvents;
- suite completa;
- PostgreSQL completa;
- JavaScript;
- migrations;
- HTTP smoke;
- security gates.

---

# 38. DOCUMENTACIÓN

Crear:

FINANCIAL-PILOT-VERIFICATION-v1.md
FINANCIAL-RECOVERY-READINESS-v1.md
FASE-1.10G-verify-orden.md
FASE-1.10G-verify-cierre.md

Actualizar G-PREP docs indicando:

G-PREP sigue siendo documental/anti-READY.

PilotGate real verifier es otra capa.

No afirmar evidencia real.

---

# 39. ENTREGA

LOCAL PRIMERO.

NO PUSH.

Devuelve:

- rama;
- commit;
- padre;
- migration sí/no;
- archivos;
- verifier catalog;
- evidence contracts;
- PilotGate;
- READY invariants;
- anti-tamper;
- tenant isolation;
- recovery readiness;
- D79 integration;
- A expiry recovery;
- provider/privacy integration;
- tests;
- SQLite;
- PostgreSQL;
- suite;
- risks;
- limitations;
- autoaudit.

---

# 40. AUTOAUDITORÍA

1. ¿Consultó producción?
2. ¿Consultó QA real?
3. ¿Leyó backup real?
4. ¿Hizo provider I/O?
5. ¿Aprobó policy legal?
6. ¿Seleccionó pilot business?
7. ¿Seleccionó profile sin humano?
8. ¿Consideró hash/reference como proof?
9. ¿Aceptó synthetic como real?
10. ¿Permitió local/sandbox provider para production?
11. ¿PilotGate READY activa un business?
12. ¿Quitó production guard D?
13. ¿Cambió cinco flags?
14. ¿Reabrió legacy después de ever_enabled?
15. ¿Reactivó history fence?
16. ¿Permitió profile change durante recovery?
17. ¿Permitió grant viejo en G+1?
18. ¿Permitió provider evidence stale?
19. ¿Permitió privacy provisional?
20. ¿Permitió UNKNOWN result?
21. ¿Editó A original?
22. ¿Reescribió D receipts?
23. ¿Mezcló main?
24. ¿Autorizó G-LIVE?
25. ¿Inició H?

Todas las respuestas peligrosas:

NO.

---

# CRITERIO

G-VERIFY PASS técnico requiere:

- G-PREP sigue incapaz de fabricar READY;
- verified evidence sólo viene de verifiers específicos;
- PilotGate sólo READY con evidence completa/current;
- READY no activa;
- D79 puede resumir con A original expirada únicamente mediante
  continuity proof actual;
- drift/privacy/provider/UNKNOWN bloquean;
- no real access;
- full regressions PASS.

NO G-LIVE.
NO H.