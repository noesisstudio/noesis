# IMPLEMENTAR FASE 1.10F — PROVIDERS, PREFLIGHT INTEGRADO, DISPATCH, OBSERVABILIDAD Y REHEARSAL

Las Fases 1.10A, 1.10B, 1.10C, 1.10D y 1.10E quedan CODE-VERIFIED PASS.

1.10E conserva explícitamente:

POLÍTICA LEGAL REAL = PROVISIONAL / PENDIENTE DE APROBACIÓN PROFESIONAL.

Eso NO se cambia en F.

Base exacta autorizada:

e02492283b6cfc07d90740fb099463be64329807

Crea una nueva rama LOCAL desde ESE commit:

codex/phase-1-10f

NO partas de main.

NO hagas merge a main.
NO hagas push a main.
NO despliegues.
NO accedas a producción.
NO accedas a Noesis19FQA.
NO accedas a backups reales.
NO destruyas QA.
NO hagas llamadas reales a AEAT, Meta, Brevo, Gmail, SMTP ni ningún provider.
NO cambies credenciales/configuración real.

Trabaja inicialmente SOLO en local.

Ejecuta exclusivamente Fase 1.10F.

NO avances a 1.10G–H.

---

# OBJETIVO

1.10F debe cerrar técnicamente:

1. provider attestations durables;
2. provider preflight integrado;
3. relación exacta capability → provider requirement;
4. configuración/credenciales fingerprinted sin almacenar secretos;
5. dispatch seguro post-handoff;
6. semántica de pause/unknown external result;
7. intentos externos con identidad durable;
8. observabilidad financiera operativa sin PII;
9. límites operativos iniciales;
10. rehearsal sintético integrado A→F.

F NO es el piloto.

F NO autoriza provider I/O real.

F NO convierte una prueba sintética en evidencia productiva.

---

# 1. PRINCIPIO CENTRAL

Preflight ≠ Provider result.

Provider attestation ≠ Financial authorization.

Capability grant ≠ credential.

Provider configured ≠ provider verified.

Provider verified ≠ provider successfully observed in production.

Production observed ≠ permiso para repetir una operación.

Mantener estas capas separadas.

---

# 2. NO ACTIVACIÓN REAL

F NO puede:

- activar producción;
- habilitar un business real;
- cambiar los cinco flags;
- quitar la protección `config.IS_PRODUCTION` de D;
- hacer handoff real;
- iniciar G;
- llamar providers reales.

Los tests pueden activar negocios SINTÉTICOS en DB descartable
utilizando fixtures controlados.

Nunca un business real.

---

# 3. CATÁLOGO CERRADO DE PROVIDERS FINANCIEROS

No ampliar F a todas las integraciones de Bynoesis.

F sólo cubre providers que participan directamente en las capabilities
financieras actuales.

Como mínimo:

AEAT_VERIFACTU

META_WHATSAPP

EMAIL_DELIVERY

EMAIL_DELIVERY puede tener variantes cerradas de implementación:

- brevo;
- smtp;
- gmail;

si el código real necesita distinguirlas.

No mezclar:

Stripe
Groq
Google login
OCR
backups

con provider readiness financiero salvo que exista una dependencia financiera
directa demostrable.

---

# 4. CAPABILITY → PROVIDER

Usar el registry C.

Mapping mínimo:

provider.aeat_dispatch
→ AEAT_VERIFACTU

channel.whatsapp_financial
→ META_WHATSAPP

provider.email_delivery
→ EMAIL_DELIVERY

channel.web_financial
→ ningún provider externo.

No crear un segundo capability registry.

No mapping por strings libres.

Capability desconocida:

FAIL CLOSED.

---

# 5. NIVELES DE ATTESTATION

Implementar exactamente la distinción conceptual:

local_verified

sandbox_verified

production_config_verified

production_observed

No tratarlos como simples números sin semántica.

---

# 6. SIGNIFICADO DE LOS NIVELES

local_verified:

- código/config local coherentes;
- archivos/variables requeridos presentes;
- fingerprints calculables;
- NO network.

sandbox_verified:

- provider sandbox/test environment comprobado;
- evidence concreta;
- NO equivale a producción.

production_config_verified:

- configuración/credencial de producción comprobada;
- entorno exacto;
- provider accesible según un check seguro;
- NO implica que una operación financiera real haya sido ejecutada.

production_observed:

- existe un resultado productivo real durable y verificable;
- se deriva de un provider attempt real;
- NO se puede crear manualmente desde preflight.

F local NO debe producir production_observed real.

---

# 7. ENVIRONMENT BINDING

Toda attestation debe estar ligada a:

- provider;
- provider implementation;
- environment;
- business;
- capability;
- configuration fingerprint;
- credential fingerprint;
- checker version;
- code/schema version.

Una attestation:

sandbox

NO sirve para:

production.

Una attestation para business A:

NO sirve para business B.

Una attestation Meta:

NO sirve para AEAT.

---

# 8. CREDENTIAL FINGERPRINTS

PROHIBIDO almacenar:

- API key;
- OAuth token;
- refresh token;
- private key;
- certificate password;
- SMTP password;
- WhatsApp token;
- secret path sensible;
- DB credential.

Para detectar rotación:

usar fingerprint IRREVERSIBLE.

Para secretos privados:

preferencia HMAC keyed usando secreto servidor estable,
no SHA256 simple del secreto.

Para certificado público:

puede usarse fingerprint público SHA256.

Para private key:

NO persistir hash raw que pueda usarse como identificador externo
si no es necesario.

Usar fingerprint keyed.

---

# 9. NO EXPORTAR FINGERPRINT KEY

La clave utilizada para fingerprints:

NO pertenece a:

- export financiero;
- logs;
- manifests de negocio;
- provider evidence;
- docs.

Mantener aislamiento equivalente a D execution verifier.

---

# 10. PROVIDER ATTESTATION CONTRACT

Crear contrato cerrado v1.

Una attestation durable debe contener como mínimo:

- business_id;
- attestation_uuid;
- provider;
- implementation;
- capability;
- environment;
- level;
- checker_version;
- schema_version;
- code_version;
- configuration_fingerprint;
- credential_fingerprint;
- checked_by;
- session_version;
- checked_at;
- expires_at;
- result;
- closed reason codes;
- evidence canonical segura;
- content hash.

No payload provider raw.

No tokens.

No PII libre.

---

# 11. RESULTADO

Resultado cerrado:

PASS
BLOCKED

No WARNING como autoridad.

Warnings pueden existir dentro de evidence operacional,
pero:

readiness requiere PASS.

---

# 12. EXPIRY

Toda attestation utilizada para activación/preflight debe tener caducidad.

No attestation perpetua.

La expiración es una política OPERATIVA, no legal/SLO.

Definir un límite conservador y documentarlo.

Preferencia inicial:

production_config_verified suficientemente reciente para que preflight y
handoff ocurran inmediatamente después.

No renovar automáticamente.

Nueva comprobación:

nueva attestation.

---

# 13. CONFIG DRIFT

Una attestation queda stale si cambia cualquier dato relevante:

- provider environment;
- credential/token;
- certificate;
- sender;
- WhatsApp phone id;
- fiscal provider config;
- issuer/system config relevante;
- selected email provider;
- business provider setting;
- checker contract.

No UPDATE de la attestation.

Nueva evidencia.

---

# 14. REUTILIZAR PROVIDERS EXISTENTES

NO implementar nuevos clientes paralelos.

AEAT:

reutilizar:

verifactu_client.py

y su configuración.

Email:

reutilizar:

adapters/email.py
y/o Gmail existente.

WhatsApp:

reutilizar:

web/whatsapp.py

No reimplementar:

SOAP
Meta Graph client
Brevo client
SMTP
Gmail sender.

---

# 15. `integration_check.py`

Puede reutilizarse como FUENTE DE LÓGICA read-only donde sea correcto.

Pero:

IntegrationCheck actual
≠ durable provider attestation.

No convertir:

warning/ok textual

directamente en authority.

La capa F debe producir evidence cerrada/versionada.

---

# 16. CHECK LOCAL — AEAT

Sin red.

Verificar como mínimo:

- VERIFACTU_AEAT_ENV válido;
- CERT_TYPE válido;
- cert path configurado;
- key path configurado;
- archivos existentes;
- configuración segura de respuesta/timeout;
- certificado fingerprintable;
- private credential fingerprint keyed;
- producer/system config relevante.

Usar:

verifactu_client.configuration_errors()

cuando corresponda.

NO construir un segundo validador contradictorio.

---

# 17. CHECK NETWORK — AEAT

Implementar la interfaz necesaria para una comprobación futura.

NO ejecutarla en F local.

No enviar registro fiscal para “probar credenciales”.

Si técnicamente puede realizarse:

- TLS/mTLS/config handshake seguro;
- endpoint/environment validation;

sin registrar un hecho fiscal,

puede ser la base de production_config_verified.

Si NO puede demostrarse de manera segura sin envío:

documentarlo.

NO falsificar production_config_verified.

---

# 18. CHECK LOCAL — WHATSAPP

Sin red.

Como mínimo:

- provider configurado;
- phone id presente;
- token presente;
- business link/config coherente;
- selected financial channel coherente;
- fingerprints.

No almacenar token.

---

# 19. CHECK NETWORK — WHATSAPP

Implementar interfaz read-only futura.

NO ejecutarla ahora.

Cuando se autorice:

usar GET/read-only del provider si existe y el cliente actual lo permite.

NO enviar mensaje como “preflight”.

Enviar un mensaje pertenece al pilot/rehearsal externo posterior.

---

# 20. CHECK LOCAL — EMAIL

Distinguir provider seleccionado.

Comprobar:

- provider disponible;
- sender;
- credenciales/config presentes;
- sender identity coherente;
- fingerprints.

No almacenar:

to/from personal data

en attestation.

---

# 21. CHECK NETWORK — EMAIL

Implementar interface futura read-only.

NO enviar email en F.

Brevo:

puede reutilizar comprobaciones GET de cuenta/senders existentes.

Gmail:

puede reutilizar discovery/config read-only.

SMTP:

si un handshake/auth sin envío se considera seguro y está implementado
correctamente, dejarlo disponible para ejecución futura explícita.

No ejecutarlo ahora.

---

# 22. NO PROVIDER I/O AUTOMÁTICO

PROHIBIDO hacer network desde:

- readiness A;
- handoff D;
- Operations;
- EconomicEvents;
- provider capability lookup;
- HTTP request normal;
- worker selection;
- application startup.

Las llamadas de preflight externas futuras deben ser:

acción de control plane explícita.

Readiness/handoff:

sólo LEEN evidence durable.

---

# 23. PERMISO

Crear permiso semántico/control-plane específico:

financial.providers.preflight

No reutilizar:

financial.authorize
financial.activation.manage
historical.record
privacy.financial.close

como authority suficiente.

No AI authority.

---

# 24. MIGRACIÓN 79

Crear migration:

79

aditiva.

NO modificar 63–78.

Tablas mínimas orientativas:

- financial_provider_attestations;
- financial_provider_preflight_runs;
- financial_activation_preflight_bindings;
- financial_provider_dispatch_attempts/results si se necesitan;
- financial_operational_observations si se justifica.

NO crear tablas sin función.

Si una arquitectura más simple demuestra las invariantes:

preferirla.

---

# 25. PREFLIGHT INTEGRADO

Crear servicio:

FinancialIntegratedPreflight

o equivalente.

Debe ser:

- tenant-scoped;
- exact-profile-scoped;
- capability-scoped;
- read-only respecto a Financial Core;
- session/premission checked;
- sin provider I/O durante verificación normal.

---

# 26. INPUT DEL PREFLIGHT

Debe congelar como mínimo:

- business;
- preflight UUID;
- evaluation UUID/hash;
- exact profile;
- capability closure;
- provider requirements;
- provider attestations exactas;
- privacy E evidence;
- export E evidence;
- history/reconciliation;
- configuration hash;
- volume;
- pending Operations;
- uncertain dispatch;
- activation state/generation;
- policy version;
- operational limits version;
- code/schema version;
- actor/session.

---

# 27. PREFLIGHT RESULT

Cerrado:

PASS
BLOCKED

Reasons cerrados.

Como mínimo:

READINESS_NOT_FULL
READINESS_STALE
PRIVACY_NOT_READY
EXPORT_NOT_READY
PROVIDER_ATTESTATION_MISSING
PROVIDER_ATTESTATION_STALE
PROVIDER_ENVIRONMENT_MISMATCH
PROVIDER_CONFIG_DRIFT
PROVIDER_LEVEL_INSUFFICIENT
PENDING_OPERATION
UNCERTAIN_EXTERNAL_RESULT
BANK_CAPABILITY_UNVALIDATED
HISTORY_INVALID
VOLUME_OUTSIDE_POLICY
ACCOUNT_CLOSING
ACCOUNT_CLOSED
SESSION_STALE
CONFIGURATION_CHANGED
CAPABILITY_DEPENDENCY_BLOCKED

Ajusta naming al repo.

---

# 28. NO DUPLICAR A

Preflight F NO reimplementa toda readiness.

Usar:

verify_readiness
readiness evidence A
history verifier
privacy evidence E
capability registry C

como fuentes.

F añade provider/operational constraints.

No crea otra definición de FULL.

---

# 29. BANK

Mantener:

BANK_EVIDENCE_UNVALIDATED

para:

bank_transaction.import
bank_transaction.match

hasta P5 / una fase específica.

F NO lo elimina.

Primer pilot futuro puede excluir bank.

No crear evidencia bancaria falsa para conseguir PASS.

---

# 30. CONTINUIDAD

Mantener blockers B/A existentes:

- historical invoice v2;
- unsupported historical invoices;
- observed_state;
- continuity limitations;
- registro_anterior;
- mandates no probados.

F NO los elimina.

---

# 31. POLICY LEGAL E

CRÍTICO.

La policy REAL permanece:

PROVISIONAL.

F NO puede:

- aprobarla;
- cambiar status;
- crear policy real synthetic;
- quitar PRIVACY_NOT_READY por provider readiness.

Los tests pueden usar policy aprobada SINTÉTICA en DB descartable.

Nunca configuración real.

---

# 32. PROVIDER REQUIREMENTS

Preflight debe derivar providers ÚNICAMENTE del exact capability closure.

Ejemplos:

profile web sin email/WhatsApp/AEAT requerido
→ ningún provider externo.

WhatsApp requested
→ Meta required.

Email delivery requested
→ Email provider required.

Fiscal emission con provider.aeat_dispatch
→ AEAT required.

No exigir Meta para uso web.

No exigir email si profile no lo solicita.

---

# 33. REQUIRED LEVEL

Para un pilot PRODUCTIVO futuro:

provider capability externa requiere como mínimo:

production_config_verified

salvo contrato específico más fuerte.

sandbox_verified:

NO habilita producción.

local_verified:

NO habilita producción.

production_observed:

NO puede ser requisito del primer efecto,
porque sólo puede existir después de una observación real.

Después del primer efecto exitoso podrá elevarse la evidencia.

---

# 34. SYNTHETIC TESTS

Fixtures pueden construir attestations contractualmente válidas.

Pero:

no deben confundirse documentalmente con pruebas reales.

Marcar en test/report:

SYNTHETIC FIXTURE ONLY.

No crear seed/migration con attestations productivas.

---

# 35. PREFLIGHT DURABLE

Persistir un receipt immutable.

Debe incluir:

- preflight UUID;
- business;
- evaluation UUID/hash;
- profile hash;
- capability closure/hash;
- provider requirement set;
- exact attestation UUIDs/hashes;
- E evidence hash;
- history proof refs;
- configuration hash;
- operational policy/version;
- result/reasons;
- actor/session;
- created_at/expires_at;
- canonical/content hash.

No PII.

No secrets.

---

# 36. IDEMPOTENCIA

Misma preflight UUID + mismo contexto:

mismo resultado.

Misma UUID + contexto distinto:

Conflict.

Context changed:

nuevo preflight.

No editar receipt anterior.

---

# 37. PREFLIGHT STALE

Antes de usar un PASS:

revalidar:

- evaluation;
- provider attestations;
- expiry;
- config fingerprints;
- privacy/export E;
- business closure;
- history;
- pending operations;
- uncertain dispatch;
- capability/profile;
- session.

Drift:

BLOCK.

---

# 38. INTEGRACIÓN CON D

Schema79 debe exigir preflight F antes de:

ENABLE
RESUME

pero:

NO modificar receipts D previos.

NO modificar contract hashes D antiguos.

Mantener schema77/78 compatible.

Preferencia:

añadir binding durable separado:

activation request
↔ preflight receipt

en vez de reescribir request v1 de D,
si eso evita romper evidencia previa.

---

# 39. ACTIVATION PREFLIGHT BINDING

El binding debe demostrar:

- mismo business;
- misma evaluation;
- mismo profile;
- mismo capability closure;
- preflight PASS;
- preflight vigente;
- provider attestations vigentes;
- exact config;
- exact actor/session cuando corresponda.

Handoff D en schema79:

revalida el binding.

No provider network.

---

# 40. PAUSE

Cerrar la política de dispatch post-handoff.

Una cuenta PAUSED:

no debe iniciar nuevos efectos financieros.

Para providers distinguir:

ALREADY COMMITTED EXTERNAL OBLIGATION

de

NEW COMMUNICATION / NEW ATTEMPT.

---

# 41. DISPATCH POLICY CERRADA

Definir policy cerrada por provider.

Como referencia inicial:

AEAT Veri*Factu:
DRAIN_COMMITTED

para un registro fiscal ya comprometido localmente
si el contrato demuestra identidad exacta.

Email financiero:
HOLD_DISPATCH

si todavía no hubo intento externo.

WhatsApp financiero:
HOLD_DISPATCH

si todavía no hubo intento externo.

No generalizar sin tests.

---

# 42. SIGNIFICADO `DRAIN_COMMITTED`

No significa:

“puedes crear una factura durante pause”.

Significa únicamente:

un outbox que YA corresponde a un hecho financiero COMMITTED antes de pause
puede completar la obligación externa exacta según policy.

No nuevo EE.

No nueva Financial Operation.

No nuevo fiscal record.

---

# 43. CLOSURE E TIENE PRIORIDAD

Si E indica:

closing / closed

NO provider claim nuevo.

Ni siquiera DRAIN_COMMITTED sin una política explícita futura.

Conservar el fail-closed E existente.

F NO puede reabrir dispatch después de closure.

---

# 44. PROVIDER DISPATCH BINDING

No inferir que un email/WhatsApp es financiero por:

- subject;
- body;
- importe;
- destinatario;
- fecha.

Necesitamos identidad durable.

Crear/adaptar binding exacto:

outbox item
↔ business
↔ Financial Operation / financial action
↔ generation
↔ capability
↔ provider.

Si el productor actual no permite identity fuerte:

esa capability permanece bloqueada.

No fuzzy matching.

---

# 45. AEAT BINDING

Para verifactu_outbox:

resolver mediante identidad durable existente:

invoice record
→ captured coverage
→ operation
→ generation/capability.

Para cancellation:

cancellation coverage C
→ operation.

No adoptar outbox legacy como live F.

Legacy outbox:

continúa bajo régimen legacy si business never_enabled.

Si business ever_enabled y el row no tiene prueba live suficiente:

FAIL CLOSED / manual review.

---

# 46. EMAIL/WHATSAPP BINDING

Auditar las rutas reales.

Si una comunicación financiera nace desde:

financial_channels / operation / receipt

persistir binding explícito al crear/encolar.

No inferir después.

Comunicación no financiera:

NO debe necesitar provider.email_delivery financial capability
si el contrato no la incluye.

No romper recuperación de contraseña,
avisos de privacidad,
etc.

---

# 47. ATTEMPT IDENTITY

Antes de cualquier provider I/O financiero post-handoff:

crear claim/attempt durable.

Debe tener identidad exacta:

- attempt UUID;
- business;
- provider;
- binding/outbox;
- operation;
- generation;
- capability;
- attestation;
- request fingerprint;
- idempotency identity;
- claimed_at.

No payload/PII.

---

# 48. NO NETWORK DENTRO DB TX

Flujo:

TX1:
claim + durable attempt
COMMIT

FUERA DE TX:
provider call

TX2:
record exact result
update outbox/attempt coherentemente
COMMIT

Nunca mantener business gate / DB TX
durante network.

---

# 49. CRASH ENTRE PROVIDER Y DB

Asumir que external exactly-once NO existe genéricamente.

Si provider pudo recibir la solicitud y la respuesta se perdió:

estado:

UNKNOWN_EXTERNAL_RESULT

No marcar:

failed retryable

automáticamente.

---

# 50. UNKNOWN RESULT — EMAIL/META

Email/WhatsApp:

si existe posibilidad razonable de que provider haya recibido el request:

NO auto retry.

Mantener:

UNKNOWN_EXTERNAL_RESULT

hasta resolución explícita/observación.

No duplicar mensajes.

---

# 51. UNKNOWN RESULT — AEAT

AEAT tiene identidad fiscal/hash y semántica de duplicado específica.

Reutilizar la lógica existente de:

duplicate_status

y record identity.

Sólo permitir retry/reconciliation cuando el protocolo demostrado lo haga seguro.

No inventar exactly-once.

---

# 52. RESULT FINAL

Provider attempt result cerrado.

Como mínimo:

SUCCEEDED
FAILED_TERMINAL
UNKNOWN_EXTERNAL_RESULT

Si existe RETRYABLE antes de cualquier envío/handshake,
demostrar que no existe ambigüedad de efecto externo.

No tratar timeout post-request como retryable genérico.

---

# 53. PRODUCTION_OBSERVED

Sólo crear una attestation:

production_observed

a partir de:

ProviderAttempt SUCCESS real

+
provider result durable

+
misma business/config/capability.

No operador manual.

No migration.

No fixture productivo.

---

# 54. EXISTING OUTBOX SEMANTICS

NO reescribir todo el sistema de colas.

Adaptar mínimamente:

verifactu_outbox
verifactu_cancellation_outbox
email_outbox
whatsapp_outbox

Preservar legacy businesses.

ever_enabled=false:

comportamiento pre-F intacto.

ever_enabled=true:

provider policy F obligatoria para financial dispatch.

---

# 55. `external_guard`

Hoy D bloquea provider dispatch post-handoff
porque F aún no existe.

Sustituir ese bloqueo transitorio por policy F.

No eliminar el guard.

Evolucionarlo:

history fence
+
closure E
+
activation state
+
generation
+
capability
+
provider attestation
+
dispatch policy.

Fail closed.

---

# 56. WORKER PREDICATES

No confiar sólo en selección SQL.

Necesito:

A. filtro/claim seguro;

B. revalidación justo antes del provider I/O.

Si state/config/attestation cambió después del claim
pero antes de network:

ABORTAR SIN LLAMADA EXTERNA.

Registrar attempt cancelado/preflight stale
sin fingir provider result.

---

# 57. DIRECT SQL

No se puede insertar un attempt válido por SQL directo
sin:

- binding;
- generation;
- grant;
- attestation;
- current state;
- exact business.

Guards SQLite/PostgreSQL.

No fake production_observed por SQL.

---

# 58. PROVIDER ATTESTATION IMMUTABLE

Final attestation:

NO UPDATE
NO DELETE.

Nueva comprobación:

nuevo UUID.

Expired:

se conserva como evidencia.

---

# 59. PREFLIGHT IMMUTABLE

Final preflight:

NO UPDATE
NO DELETE.

No “refresh” in-place.

---

# 60. OPERATIONAL POLICY v1

Codificar como contrato OPERATIVO, no SLO.

Valores iniciales aprobados de diseño:

- historical cohort max: 64 items;
- gate wait objetivo: 1s;
- handoff TX warning: 2s;
- handoff TX hard review threshold: 5s;
- readiness age: 5 min;
- protected cut warning: 5 min;
- protected cut intervention: 15 min;
- confirmed integrity duplicate: hard blocker / pause required;
- unknown external result: no unsafe automatic retry.

Si algunos ya existen en A/D:

referenciarlos.

No duplicar constantes contradictorias.

---

# 61. NO HARDSTOP IRRESPONSABLE

Los thresholds de tiempo son límites operativos/pilot,
no reglas contables.

No rollback de una transacción ya committed
porque excedió un warning.

Usar:

warning
block before action
operator intervention

según punto.

---

# 62. OBSERVABILIDAD

Crear una vista/servicio operacional tenant-scoped.

Debe poder responder sin PII:

- activation state/generation;
- current grants;
- preflight status;
- provider attestations + expiry;
- provider attempts pending/unknown/error;
- outbox counts/status;
- continuity mismatch;
- stale generation rejects;
- closure state;
- history fence/handoff state;
- export/privacy readiness.

---

# 63. TELEMETRÍA

No Economic Events.

Si persistes observaciones:

catálogo cerrado como mínimo:

provider_preflight
provider_attempt
provider_unknown_result
provider_error
activation_blocked
continuity_mismatch
stale_generation
pause_required
export_failure

No:

email
phone
NIF
message content
provider raw response
tokens.

---

# 64. NO TELEMETRY AUTHORITY

Una observación:

NO cambia:

- activation;
- grant;
- provider attestation;
- Operation;
- authorization.

Es diagnóstico.

---

# 65. ALERTAS

Implementar contrato/read model para G.

Como mínimo alertar:

- attestation expiring/stale;
- provider unknown result;
- rejected AEAT;
- duplicate/integrity conflict;
- paused;
- closure;
- preflight blocked;
- pending outbox age;
- provider error.

No enviar alertas externas en F.

Sólo generar el estado.

---

# 66. REHEARSAL SINTÉTICO

Crear rehearsal integral únicamente con fixtures.

Debe demostrar:

empty synthetic business
→ history cut
→ certifiable inventory
→ terminal batch
→ E reconciliation PASS
→ A evaluation
→ B antecedents cuando proceda
→ E privacy/export synthetic-approved fixture
→ F provider evidence synthetic fixture
→ F preflight
→ D handoff synthetic
→ one approved financial operation
→ provider dispatch fake
→ durable provider result
→ pause
→ recovery/resume
→ export
→ no duplicated external effect.

No provider real.

---

# 67. REHEARSAL NEGATIVO REALISTA

Repetir con:

policy real/default provisional

→ PRIVACY_NOT_READY

→ preflight BLOCKED

→ NO handoff.

Esto debe ser la situación real actual.

---

# 68. PROVIDER REHEARSAL RESULTS

Simular explícitamente:

AEAT success
AEAT accepted_with_errors
AEAT rejected
AEAT timeout/unknown
AEAT duplicate confirmation

Email success
Email provider terminal rejection
Email ambiguous timeout

WhatsApp success
Meta terminal rejection
Meta ambiguous timeout

No network.

---

# 69. PAUSE RACE

PostgreSQL:

attempt claim
→ pause concurrente

Si network no empezó:

NO provider I/O.

Si provider call ya comenzó:

permitir únicamente registrar el resultado de ESE attempt.

No segundo attempt.

---

# 70. CLOSURE RACE

claim
→ E closure authorization

Antes de provider call:

ABORT.

Si provider ya recibió:

registrar exact result/unknown según contrato,
pero NO iniciar otro.

Closure permanece cerrada.

---

# 71. CONFIG ROTATION RACE

Attestation válida
→ claim
→ credential/config cambia
→ antes de network

ABORT.

Nueva attestation requerida.

No provider call con evidencia stale.

---

# 72. ATTESTATION EXPIRY RACE

Igual.

Attestation expira antes del external call:

NO call.

---

# 73. GENERATION RACE

Attempt ligado a G.

Resume crea G+1 antes del provider call.

Policy:

si el attempt pertenece a obligación committed cuya policy permite drain:

validar explícitamente.

En cualquier otro caso:

NO call.

No utilizar grant G como autoridad genérica en G+1.

---

# 74. PROVIDER RESULT NO CREA EE

Provider result:

NO crea automáticamente:

Economic Event
Financial Operation
payment
invoice
bank event

Es resultado de transporte/provider.

Los hechos económicos ya existen.

---

# 75. AEAT RESPONSE

Actualizar outbox fiscal mediante semántica existente.

No crear un parser nuevo.

No reescribir:

verifactu_client.parse_response.

Provider F sólo coordina authority/evidence/attempt.

---

# 76. EMAIL/META RESULTS

Reutilizar funciones existentes de finalización cuando sean seguras.

No cambiar el significado legacy de statuses
sin migración/contrato.

---

# 77. READINESS A

Modificar únicamente provider evidence.

Para evaluaciones NUEVAS:

PROVIDER_PREFLIGHT_MISSING

puede desaparecer para una capability concreta SOLO si:

- provider requirement exacto;
- attestation exacta;
- level suficiente;
- environment correcto;
- no expired;
- config fingerprint actual;
- credential fingerprint actual;
- business correcto.

No tocar evaluaciones anteriores.

---

# 78. REAL READINESS ACTUAL

Dado que:

- policy real E sigue provisional;
- no existen real production provider attestations F;

una readiness financiera REAL actual debe seguir BLOCKED.

Esto es CORRECTO.

No fabricar FULL.

---

# 79. D HANDOFF

En schema79:

ENABLE/RESUME requiere preflight F PASS vigente.

Pero:

D sigue con:

config.IS_PRODUCTION guard.

F NO lo quita.

G será quien trate la autorización controlada productiva.

---

# 80. PREVIOUS SCHEMAS

Schema77/78:

D tests/semántica histórica siguen válidos.

No romper receipts anteriores.

Schema79:

añade requisito F.

Matrices explícitas.

No `>=79`.

---

# 81. MIGRATION DOWNGRADE

79→78:

sólo si evidencia F está vacía.

Si existe:

- attestation;
- preflight;
- activation/preflight binding;
- provider attempt/result;
- operational evidence;

BLOCK downgrade.

No borrar evidencia para bajar.

---

# 82. MULTI-TENANT

Toda evidence:

business-scoped.

FKs compuestas cuando sea posible.

Otro tenant no puede:

- leer attestation;
- usar preflight;
- bind activation;
- claim attempt;
- consultar operational state.

Respuesta uniforme.

---

# 83. SECRET TESTS

Fixtures deben incluir marcadores:

- AEAT private key;
- WhatsApp token;
- Brevo key;
- SMTP password;
- Gmail refresh token.

Ninguno aparece en:

- attestation body;
- preflight;
- logs;
- provider attempt evidence;
- operational snapshot;
- export E;
- documentation.

---

# 84. NO PROVIDER RESPONSE RAW EN F

No duplicar raw responses dentro de F evidence.

Puede guardarse:

- response/status code;
- provider reference hash;
- result hash;
- result category.

La fuente provider/outbox existente mantiene lo que ya necesite.

No segunda copia.

---

# 85. CONCURRENCIA POSTGRESQL

Como mínimo:

- dos preflight misma UUID;
- dos preflight diferentes;
- attestation rotation;
- attestation expiry;
- preflight vs config drift;
- handoff vs preflight expiry;
- two provider claims same row;
- claim vs pause;
- claim vs closure;
- claim vs generation change;
- result vs crash;
- unknown vs retry;
- otro business progresa.

Sin deadlocks.

---

# 86. CRASH POINTS PROVIDER

Simulados, sin network real:

- before attempt claim;
- after attempt claim commit;
- before fake provider call;
- after fake provider success before result TX;
- during result TX;
- after result commit before response.

Demostrar:

antes de provider call:
0 external effect.

después de simulated provider call y antes de durable result:
UNKNOWN/recovery conservador.

postcommit:
same result.

---

# 87. IDEMPOTENCIA PROVIDER

Mismo attempt:

no segunda provider call.

Mismo outbox + mismo durable result:

recover.

Nuevo attempt sólo cuando policy lo permite.

Unknown:

no auto-new-attempt para Meta/email.

---

# 88. LEGACY COMPATIBILITY

Business:

ever_enabled=false

mantiene workers/providers legacy actuales.

No exigir F attestation a:

- password reset email;
- privacy notifications;
- general nonfinancial email;
- nonfinancial WhatsApp;
- legacy fiscal business no incorporado,

salvo controles históricos/E ya existentes.

---

# 89. POST-HANDOFF

Business:

ever_enabled=true

NO puede usar fallback provider legacy
para una acción financiera.

Financial provider path:

F policy obligatoria.

---

# 90. HTTP / ROUTING

NO crear UI pública de provider preflight.

NO botón público de activar.

NO comando WhatsApp para aprobar provider.

F API interna/control-plane únicamente.

G decidirá operator workflow.

---

# 91. PROVIDER NETWORK INTERFACE

Aunque implementes funciones reales futuras:

deben requerir parámetro/authority explícita.

Por defecto:

network disabled.

Tests deben monkeypatch socket/urllib/http/smtplib y fallar si F local intenta salir.

---

# 92. FLAGS

Mantener OFF:

FINANCIAL_CORE_ENABLED
LEDGER_REPORTING_ENABLED
OPEN_ITEMS_ENABLED
NEW_TAX_ENGINE_ENABLED
NEW_BANK_RECONCILIATION_ENABLED

No cambiar defaults.

No cambiar variables reales.

---

# 93. PRODUCTION / QA

NO:

Railway
production DB
Noesis19FQA
real dump
real backup
real certificate test
AEAT
Meta
Brevo
Google
SMTP
Stripe

durante F.

---

# 94. SIDE-EFFECT PROOF

Provider local preflight:

sólo evidence F.

Integrated preflight:

sólo receipt F.

Dispatch fake:

sólo synthetic provider attempt/result + outbox fixture.

NO:

- new economic event por provider result;
- financial source mutation no prevista;
- generation/grant change;
- history rewrite;
- E policy approval;
- five flags change.

---

# 95. OBSERVABILITY SIDE EFFECT

Si operational observations se persisten:

sólo append-only diagnostic metadata.

Una falla al persistir telemetry:

NO puede repetir un provider side effect.

Diseñar order correctamente.

---

# 96. PERFORMANCE

Medir sintéticamente:

- preflight business vacío;
- 64 history items;
- múltiples provider requirements;
- >500 provider attempt rows;
- operational snapshot.

Registrar tiempo/memoria.

No SLO.

---

# 97. CI

Añadir matriz F PostgreSQL.

Ejecutar:

- F SQLite;
- F PostgreSQL;
- provider contract;
- preflight;
- dispatch policy;
- concurrency;
- crash tests;
- rehearsal;
- A readiness;
- B antecedents;
- C fiscal cancellation;
- D handoff;
- E privacy;
- history;
- all captures;
- channels;
- workers/outboxes;
- backups/restore;
- suite general completa;
- JavaScript;
- 36-route smoke.

---

# 98. SECURITY GATES

- Ruff;
- Bandit;
- credential scan;
- dependency audit;
- migrations;
- previous migration AST;
- documentation truth;
- links;
- no real PII;
- no real secrets;
- outbound blocked.

---

# 99. DOCUMENTACIÓN

Crear:

- ADR siguiente disponible;
- FINANCIAL-PROVIDERS-PREFLIGHT-v1.md;
- FASE-1.10F-orden.md;
- FASE-1.10F-cierre.md;
- provider pilot/preflight runbook;
- operational limits document.

Actualizar:

- 1.10 plan;
- arquitectura;
- decisiones;
- estado;
- mapa;
- QA;
- cambios;
- tareas;
- Financial Core;
- integraciones;
- project-state.

---

# 100. DOCUMENTAR NIVELES SIN CONFUNDIRLOS

La documentación debe decir expresamente:

local_verified
≠ sandbox_verified
≠ production_config_verified
≠ production_observed.

No escribir:

“provider listo”

sin indicar nivel.

---

# 101. REAL STATE AL CERRAR F

Si todo el código pasa pero no hicimos network real:

debe poder cerrarse:

1.10F CODE-VERIFIED PASS TÉCNICO —
REAL PROVIDER ATTESTATIONS PENDING FOR PILOT

Eso es correcto.

No es FAIL técnico.

Pero:

G no puede usar una capability provider-dependent
sin evidence real suficiente.

---

# 102. REHEARSAL NO ES PILOT

Un fake AEAT PASS:

NO demuestra AEAT.

Un fake Meta PASS:

NO demuestra Meta.

Un fake email PASS:

NO demuestra email.

Rehearsal sólo demuestra:

software/control-flow.

Documentarlo.

---

# 103. PRE-G BLOCKERS

El cierre F debe producir una lista explícita de:

REAL-WORLD BLOCKERS BEFORE G.

Como mínimo evaluar:

- legal policy E approval;
- exact pilot business;
- provider requirements del exact profile;
- production provider attestations;
- backup/restorability real;
- runtime/schema deployment compatibility;
- operator ownership/on-call;
- monitoring;
- pause procedure;
- external unknown-result procedure.

No resolverlos fingiendo fixtures.

---

# 104. ENTREGA LOCAL PRIMERO

Al terminar:

NO PUSH.

Devuélveme:

- rama;
- commit local;
- padre exacto;
- migration79;
- archivos;
- provider catalog;
- capability mappings;
- attestation contract;
- levels;
- secret fingerprints;
- preflight service;
- preflight receipt;
- D binding;
- readiness integration;
- dispatch policy;
- provider bindings;
- attempt/result model;
- unknown-result policy;
- pause/closure integration;
- observability;
- operational limits;
- rehearsal;
- concurrency;
- crashes;
- side-effect proof;
- SQLite;
- PostgreSQL;
- suite;
- performance;
- real-world blockers;
- riesgos;
- limitaciones;
- autoauditoría.

---

# 105. AUTOAUDITORÍA

Responder explícitamente:

1. ¿Puede F activar producción?
2. ¿Puede F quitar el guard production de D?
3. ¿Puede F cambiar los cinco flags?
4. ¿Puede F aprobar la policy legal E?
5. ¿Puede local_verified habilitar producción?
6. ¿Puede sandbox_verified habilitar producción?
7. ¿Puede una attestation de otro business usarse?
8. ¿Puede una attestation de otro provider usarse?
9. ¿Puede una attestation expirada usarse?
10. ¿Puede config drift mantener una attestation válida?
11. ¿Puede credential rotation mantener una attestation válida?
12. ¿Puede readiness llamar un provider?
13. ¿Puede handoff llamar un provider?
14. ¿Puede preflight automático hacer provider I/O?
15. ¿Puede un token/private key aparecer en evidence?
16. ¿Puede F exportar la fingerprint key?
17. ¿Puede un SQL directo crear production_observed válido?
18. ¿Puede production_observed crearse sin provider result?
19. ¿Puede provider result crear un EE económico nuevo?
20. ¿Puede email/Meta unknown auto-reintentarse?
21. ¿Puede AEAT timeout fingirse como rechazo/éxito?
22. ¿Puede pause iniciar una nueva comunicación financiera?
23. ¿Puede closure E iniciar/drain provider nuevo?
24. ¿Puede una generación vieja autorizar dispatch nuevo?
25. ¿Puede un outbox financiero sin binding fuerte despacharse post-handoff?
26. ¿Puede una comunicación no financiera romperse por F?
27. ¿Puede provider network ejecutarse dentro de una TX DB?
28. ¿Puede un crash tras provider side effect provocar retry ciego?
29. ¿Puede el rehearsal sintético declararse prueba real?
30. ¿Se inició 1.10G?

Todas las respuestas peligrosas:

NO.

---

# CRITERIO FINAL

1.10F sólo puede cerrar PASS técnico si:

- provider catalog cerrado;
- capability→provider exacto;
- attestations durables/inmutables;
- levels separados;
- secrets nunca almacenados;
- drift/expiry detectados;
- integrated preflight durable;
- D schema79 exige F preflight cuando corresponda;
- no provider I/O desde readiness/handoff;
- post-handoff financial dispatch no puede usar legacy fallback;
- pause/closure policies son fail closed;
- unknown external result no provoca retry inseguro;
- existing provider clients se reutilizan;
- observabilidad es no-authority/no-PII;
- operational limits están codificados/documentados;
- rehearsal sintético completo pasa;
- real state sigue honestamente bloqueado donde falte evidencia real;
- todos los gates pasan.

Si técnicamente está completo pero no hay providers reales comprobados:

cerrar como:

1.10F CODE-VERIFIED PASS TÉCNICO —
REAL PROVIDER ATTESTATIONS PENDING FOR PILOT

NO hacer provider checks reales.

NO avanzar a 1.10G.