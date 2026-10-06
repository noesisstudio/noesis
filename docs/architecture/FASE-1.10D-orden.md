# IMPLEMENTAR FASE 1.10D — ACTIVACIÓN ATÓMICA, HANDOFF, GENERACIONES, PAUSA Y RECUPERACIÓN

Las Fases 1.10A, 1.10B y 1.10C quedan CODE-VERIFIED PASS.

Base exacta autorizada:

0e99db609b1f7ad21996b0eb9c48d95366913f4a

Crea una nueva rama LOCAL desde ESE commit:

codex/phase-1-10d

NO partas de main.

NO hagas merge a main.
NO hagas push a main.
NO despliegues.
NO accedas a producción.
NO accedas a Noesis19FQA.
NO accedas a backups reales.
NO llames AEAT, Meta, email ni ningún provider real.

Trabaja inicialmente SOLO en local.

Ejecuta exclusivamente Fase 1.10D.

NO avances a 1.10E–H.

---

# OBJETIVO

Implementar la frontera que convierte:

historical protegido por fence

en

Financial Core live protegido por:

- activation state;
- activation generation;
- grants exactos de capability;
- autoridad humana;
- Operations;
- guards SQL/runtime.

El handoff debe ser ATÓMICO.

Nunca puede existir una ventana:

fence OFF
+
live protection todavía OFF.

1.10D también implementa:

- lifecycle de activación;
- generación;
- capability grants durables;
- protección de Operations;
- invalidez de operaciones antiguas;
- pause;
- recuperación/reanudación segura.

NO implementa:

- privacy/export/retention de E;
- provider preflight de F;
- piloto de G;
- auditoría final de H.

---

# 1. PRINCIPIO ABSOLUTO

Readiness ≠ autoridad.

Authority ≠ activación.

Activation ≠ Financial Operation.

Capability grant ≠ human confirmation.

Global feature flag ≠ autorización por business.

Mantener estas capas separadas.

---

# 2. STATE MACHINE

Ampliar el lifecycle durable a:

off
→ validating
→ ready
→ enabled
→ paused

No permitir saltos arbitrarios.

Primer alta:

off
→ validating
→ ready
→ enabled

Abortar antes de la primera activación puede volver:

validating/ready
→ off

solo si:

ever_enabled = false.

Después de haber estado enabled:

NUNCA volver a off.

Pausa:

enabled
→ paused

Reanudación:

paused
→ validating
→ ready
→ enabled

pero mediante recovery proof de D, no falsificando una evaluación A nueva.

NO:

paused → enabled directo.

NO:

off → enabled.

NO:

validating → enabled.

NO:

enabled → off.

---

# 3. EVER_ENABLED

`ever_enabled` es MONÓTONO.

Inicial:

false

Primer handoff:

true

Nunca vuelve a false.

Una vez true:

el business nunca recupera fallback financiero legacy.

Ni aunque:

- se pause;
- se desactive el flag global;
- falle un provider;
- haya un error operativo.

El comportamiento debe ser fail closed.

---

# 4. ACTIVATION GENERATION

Primera activación:

generation = 1

Cada reanudación segura posterior:

generation = generación anterior + 1

Nunca decrece.

Nunca se reutiliza una generación antigua.

Generation identifica la época LIVE autorizada.

No confundirla con:

financial_history_epochs.generation.

Son conceptos distintos.

---

# 5. MIGRACIÓN 77

Crear migration:

77

aditiva/protegida.

NO modificar migrations 63–76.

Debe ampliar la infraestructura necesaria de:

financial_activation_control

para admitir:

- off
- validating
- ready
- enabled
- paused

y:

activation_generation >= 0
ever_enabled monotónico.

Añadir las tablas estrictamente necesarias para:

- activation requests/authorizations;
- activation transitions;
- activation generations/grants;
- handoff receipts;
- pause/recovery receipts;
- execution protection transaccional;

según la arquitectura que resulte más segura.

Evitar tablas duplicadas sin función real.

---

# 6. AUTORIDAD DE ACTIVACIÓN

Crear permiso/control-plane específico.

Conceptualmente:

financial.activation.manage

NO reutilizar como autoridad suficiente:

- financial.authorize;
- financial.mandate;
- historical.record;
- financial.readiness.evaluate.

Activar un business requiere confirmación humana explícita
sobre un request/hash exacto.

No autoridad IA.

No mandate.

No historical_unknown.

No aprobación implícita.

Si el modelo actual de usuarios NO tiene un rol tenant-scoped adecuado:

NO reutilices `users.is_admin` sin demostrar que significa exactamente eso.

No convertir un administrador global de la plataforma en “owner del business”
por conveniencia.

En ese caso:

- principal del mismo business;
- sesión actual;
- permiso semántico explícito;
- confirmación humana durable exacta;

y documentar que RBAC/SoD avanzada llegará en P15.

---

# 7. ACTIVATION REQUEST

Crear contrato cerrado/versionado de activación.

Debe congelar como mínimo:

- business_id;
- requested transition;
- evaluation UUID;
- evaluation content hash;
- exact profile;
- exact capability closure;
- capability grant hash;
- epoch UUID;
- historical generation;
- manifest;
- batch;
- reconciliation;
- source hash;
- plan hash;
- reconciliation hash;
- code/schema version;
- activation generation propuesta;
- actor/session;
- request hash.

No payload libre.

No secretos.

No PII innecesaria.

---

# 8. READINESS VERIFIER PURO

D necesita una verificación READ-ONLY del resultado A.

NO crear una nueva evaluación durante handoff.

NO llamar a una función que abra otra TX.

Crear/refactorizar una vía pura con:

FinancialSession prestada.

Debe verificar:

- evaluación final;
- content hash;
- profile hash;
- outcome = fully_eligible;
- no caducada;
- business correcto;
- actor/session válidos;
- profile exacto;
- dependency closure exacta;
- capability proofs intactos;
- source evidence actual;
- configuration evidence actual;
- history/reconciliation actual;
- boundary actual cuando sea primer handoff;
- ausencia de drift;
- cero C/D;
- E PASS;
- cero blockers.

Reutiliza la lógica A existente.

NO dupliques otra implementación con semántica distinta.

---

# 9. EVITAR SELF-DRIFT DEL CONTROL

La evaluación A incorpora estado del activation control en su contexto.

D cambia:

off/validating
→ ready
→ enabled.

No hagas que ese cambio administrativo invalide artificialmente
toda la evidencia económica.

Separa explícitamente:

EVIDENCIA EXTERNA que debe seguir idéntica

de

LIFECYCLE DE ACTIVACIÓN que D está cambiando intencionadamente.

NO modificar evaluaciones A finalizadas.

NO recalcular sus hashes.

NO editar sus contextos.

La revalidación D debe demostrar equivalencia de la evidencia externa
y validar por separado la transición de control permitida.

Añadir tests específicos para evitar self-invalidating readiness.

---

# 10. FULL NO ES SUFICIENTE POR SÍ SOLO

Para conceder grants:

cada capability necesaria del perfil exacto
y su closure transitiva

debe estar:

eligible

NO:

blocked.

NO:

not_requested.

NO:

not_applicable.

`not_applicable` nunca se transforma en granted.

Aunque el outcome global A sea FULL.

Si el perfil explícitamente pide una capability que resulte not_applicable:

NO activar ese perfil.

Requiere otro perfil/evaluación.

---

# 11. PERFIL ACTIVABLE

Para primer enable exigir al menos UNA capability financiera real
asociada a CommandType.

No hacer handoff únicamente para:

channel.web_financial

o una capability de canal/provider aislada.

Un handoff histórico→live tiene sentido porque existe al menos
una capacidad financiera que podrá ser autorizada en esa generación.

IMPORTANTE:

A hoy mantiene blockers E/F para capacidades financieras.

NO elimines esos blockers para conseguir un test positivo.

Para pruebas D se permite un fixture sintético TEST-ONLY que construya
evidencia A estructuralmente válida para probar guards/handoff.

Ese fixture:

- no entra en runtime;
- no cambia evaluator productivo;
- no se documenta como readiness real;
- no prueba E/F.

---

# 12. GRANTS DURABLES

Crear grants por:

business
+
activation_generation
+
capability

Solo guardar capabilities realmente concedidas.

Derivarlas de la evaluación exacta.

Un grant debe acreditar:

- capability;
- evaluation;
- profile;
- generation;
- dependency closure;
- proof hash;
- activation/handoff receipt.

Append-only/inmutable.

No existe grant global.

No existe:

“Financial Core enabled → todo permitido”.

---

# 13. HANDOFF — PRIMER ENABLE

Éste es el núcleo de D.

TODO dentro de UNA ÚNICA transacción exterior.

Orden conceptual:

1. autenticar principal;
2. validar sesión/suscripción;
3. adquirir business gate;
4. revalidar principal bajo gate;
5. bloquear activation control;
6. exigir state=ready;
7. verificar human activation authorization exacta;
8. revalidar evaluación A completa;
9. revalidar source scope;
10. revalidar reconciliation E con verifier SELECT prestado;
11. revalidar boundary/T0/epoch/control;
12. revalidar configuración;
13. verificar cero operaciones live pendientes incompatibles;
14. verificar cero dispatch incierto relevante;
15. derivar grants exactos;
16. crear generación live;
17. instalar protección live;
18. crear handoff receipt;
19. transferir epoch historical a handed_off;
20. desactivar fence histórico;
21. cambiar activation control a enabled;
22. set activation_generation;
23. set ever_enabled=true;
24. commit único.

Cualquier fallo:

ROLLBACK COMPLETO.

---

# 14. NO USAR `HistoryCutoff.release()`

El handoff NO es:

released.

Añadir estado explícito:

handed_off

a:

financial_history_epochs

mediante migration77.

Significado:

el corte histórico fue consumido correctamente por una activación live.

No fue:

- invalidado;
- abandonado;
- liberado manualmente.

---

# 15. CRÍTICO — CONSERVAR CERTIFICACIÓN HISTÓRICA

Migration71 actualmente revoca:

certifiable
y
boundary_current

cuando cambia el epoch.

NO puedes aplicar esa semántica sin cambios a `handed_off`.

Después del handoff:

boundary_current = FALSE

porque el fence histórico ya no es el boundary operativo actual.

PERO:

certifiable DEBE PERMANECER TRUE.

La evidencia histórica certificada sigue siendo válida.

Reconciliation PASS sigue siendo evidencia.

Los antecedentes B historical deben seguir pudiendo verificarse
DESPUÉS del handoff.

Esto es CRÍTICO.

Migration77 debe sustituir/extender los triggers/guards de71
sin modificar migration71.

Semántica:

invalidated/released
→ comportamiento de revocación previo.

handed_off
→ fence OFF
→ boundary_current FALSE
→ certifiable CONSERVADO
→ hashes/manifest/batch/E conservados.

Test obligatorio:

un antecedente histórico válido B antes del handoff
sigue verificándose después del handoff.

---

# 16. HANDOFF RECEIPT

Persistir recibo inmutable como mínimo con:

- business;
- handoff UUID;
- activation generation;
- activation request/auth;
- profile;
- evaluation UUID/hash;
- grant set/hash;
- epoch UUID/generation;
- manifest;
- batch;
- reconciliation;
- source_set_hash;
- plan_hash;
- reconciliation result_hash;
- T0;
- fence version;
- previous activation state;
- final activation state;
- actor/session;
- code/schema version;
- timestamp;
- canonical/content hash.

Sin secretos.

---

# 17. HISTORY CONTROL DESPUÉS DEL HANDOFF

Debe quedar:

epoch.state = handed_off

epoch.fence_enabled = FALSE

financial_history_control.fence_enabled = FALSE

pero la identidad:

business
epoch
historical generation

se conserva.

NO borrar control.

NO borrar epoch.

NO borrar manifest.

NO borrar reconciliation.

---

# 18. PROHIBIR NUEVO HISTORICAL DESPUÉS DE EVER_ENABLED

Una vez:

ever_enabled = true

NO permitir:

- abrir nuevo historical epoch;
- volver a fence histórico;
- importar otra historia legacy;
- reconciliar una nueva importación como mecanismo de fallback.

No existe vuelta:

live → legacy migration mode.

Si se necesita reparación futura:

pause + reparación explícita + nueva evidencia.

No reabrir 1.9.

---

# 19. OPERATION GENERATION BINDING

Añadir de forma aditiva a Financial Operations la vinculación necesaria:

- activation_generation;
- activation_capability;

o estructura equivalente fuerte.

Filas históricas/legacy existentes pueden quedar NULL.

Después de:

ever_enabled=true

toda NUEVA operación financiera live debe tener:

- generation actual;
- capability exacta;
- capability granted;
- command↔capability mapping C exacto.

No command sin mapping.

No generation implícita.

---

# 20. AUTHORIZATION GENERATION

Human confirmations y mandates live deben estar ligados a generación
cuando el business ya fue activado.

Una autorización de generación G:

NO sirve para G+1.

Historical_unknown:

no recibe generación live.

Autorizaciones legacy anteriores:

no se promueven.

---

# 21. MANDATES

No amplíes B/C.

Si el business está ever_enabled:

un mandate solo puede utilizarse si:

- pertenece a la generación vigente;
- capability coincide;
- request hash coincide;
- revisión coincide;
- sigue válido;
- no fue revocado.

Mandates anteriores o generation NULL:

NO pueden autorizar operaciones post-handoff.

Durante pause:

revocar o inutilizar de forma durable los mandates activos
de la generación según la solución más segura.

No borrarlos.

---

# 22. OPERACIONES PREVIAS AL HANDOFF

PREPARED o APPROVED creadas antes del handoff:

NO pueden ejecutarse después.

Aunque:

- request hash coincida;
- usuario sea el mismo;
- sesión siga viva.

Deben:

- ser requisito bloqueante antes del handoff,
  o
- quedar terminalizadas explícitamente de forma segura.

Preferencia:

el handoff exige cero PREPARED/APPROVED incompatibles.

No editar request/auth existentes.

Nueva generación:

nueva revisión
+
nueva propuesta
+
nueva aprobación.

---

# 23. COMMITTED ANTIGUAS

Una operación ya COMMITTED:

puede seguir siendo leída/recuperada.

Nunca repetir efecto.

No exigir generación actual para:

recover de un resultado ya committed.

Sí verificar integridad durable.

---

# 24. GLOBAL FLAG

`FINANCIAL_CORE_ENABLED` pasa conceptualmente a ser:

GLOBAL AVAILABILITY

NO autorización por business.

NO cambies su valor/default en D.

Los cinco flags del entorno/repositorio permanecen OFF.

Para un business:

ever_enabled=false
→ comportamiento legacy actual intacto.

ever_enabled=true + FINANCIAL_CORE_ENABLED=false
→ FAIL CLOSED para nuevos efectos financieros.

NUNCA fallback legacy.

Los otros cuatro flags:

siguen OFF y fuera de D.

Tests pueden monkeypatchar disponibilidad únicamente
dentro de fixtures sintéticos.

No cambiar config real.

---

# 25. RUNTIME CAPABILITY GUARD

Cuando:

ever_enabled=true

FinancialOperations debe comprobar antes de un nuevo efecto:

business state = enabled
+
generation actual
+
operation generation = actual
+
command capability exacta
+
grant durable vigente.

Usar registry C.

No duplicar command mapping.

---

# 26. PAUSED

En:

paused

bloquear:

- nuevos prepare financieros;
- nuevas authorizations;
- execute de operaciones no committed;
- nuevos Financial Effects;
- Economic Events live nuevos;
- writers económicos nuevos.

Permitir:

- consultas;
- lectura de evidencia;
- export futuro;
- recover de COMMITTED;
- inspección/auditoría;
- terminalizar de forma segura operaciones pendientes cuando corresponda.

Pause NO borra nada.

Pause NO reactiva history fence.

Pause NO hace restore.

---

# 27. PROTECCIÓN DE WRITERS DESPUÉS DEL HANDOFF

Éste es el segundo punto crítico.

Hoy el history fence protege mutations mientras está activo.

Después de handed_off:

fence=false.

NO basta con proteger solamente FinancialOperations en Python.

Debe existir protección live frente a rutas legacy/direct SQL
que intenten escribir un hecho financiero fuera de una operación
de la generación actual.

Audita TODAS las superficies de mutación económica.

Distingue:

A. cambios documentales/draft no económicos;

B. efectos económicos finales.

No bloquees innecesariamente:

- crear/editar un borrador de factura;
- preparar datos no confirmados;

si no constituyen un hecho económico.

Pero sí bloquear bypass como:

- emitir factura directamente;
- registrar cobro directo;
- confirmar/corregir/retirar recibida;
- confirmar/retirar gasto;
- importar/matchear banco;
- registrar cancelación fiscal;

fuera de una operación/grant/generation válida.

---

# 28. GUARD SQL + GUARD APLICACIÓN

Necesito DOS capas.

Aplicación:

FinancialOperations / writers / EconomicEvents.

DB:

guards estructurales para los efectos financieros protegidos.

Un error en routing no puede reabrir el legacy bypass
después de ever_enabled.

---

# 29. NO GENERIC BYPASS TOKEN

Si implementas un execution claim/context para permitir
al writer autorizado atravesar guards SQL:

NO puede ser un row/token reutilizable por otra transacción posterior.

Debe estar ligado como mínimo a:

- business;
- operación;
- generation;
- capability;
- transacción/connection context;
- state APPROVED.

Y debe ser imposible reutilizarlo después del commit.

PostgreSQL y SQLite deben tener una solución demostrable.

Una fila durable genérica:

“business X puede escribir”

NO es aceptable.

Si no puedes demostrar un mecanismo seguro:

DETÉN D como BLOCKED.

No debilites guards para terminar la fase.

---

# 30. DIRECT SQL ADVERSARIAL

Tests obligatorios:

después de ever_enabled:

SQL directo sin contexto autorizado intentando:

- emitir invoice;
- insertar payment;
- confirmar supplier;
- confirmar expense;
- importar/matchear bank;
- crear cancellation;

→ FAIL.

SQL directo con:

- generation vieja;
- capability incorrecta;
- operation incorrecta;
- business ajeno;
- operation committed;
- fake claim;

→ FAIL.

Solo la TX legítima de ejecución actual:

→ PASS.

---

# 31. DRAFTS NO DEBEN ROMPERSE

Test explícito:

business ever_enabled

puede seguir creando/editando elementos NO económicos
que el producto necesita antes de confirmarlos.

Por ejemplo:

invoice draft

si esa acción no crea un Economic Event.

No conviertas D en un bloqueo general de toda la UX.

Audita caso por caso.

---

# 32. ECONOMIC EVENTS

EconomicEvents.append también debe fallar cerrado después de activation si:

- business paused;
- operation generation stale;
- capability no granted;
- command/capability mismatch;
- operation no pertenece a generación actual.

No aceptar un EE live mediante llamada interna directa
saltándose FinancialOperations.

Historical EE existentes permanecen legibles.

---

# 33. CAPTURES EXISTENTES

Sin reescribir su lógica.

D debe proteger de forma común:

InvoiceCapture
PaymentCapture
BankCapture
SupplierInvoiceCapture
ExpenseCapture
FiscalCancellationCapture

No meter un `if activation...` diferente en veinte rutas si puede existir
una frontera común.

Preferencia:

FinancialOperations + boundary/guard central + DB guards.

---

# 34. ROUTING PÚBLICO

NO crear todavía nueva UI/API de “Activar Financial Core”.

NO conectar activation a WhatsApp.

NO crear comandos de usuario para activar.

D implementa API interna/control plane y guards.

G será el piloto autorizado.

---

# 35. HANDOFF Y SOURCE WRITES CONCURRENTES

PostgreSQL:

business gate debe garantizar:

writer anterior al handoff
→ termina antes de corte final

o

handoff gana
→ writer encuentra nuevo guard.

Nunca cruzarse a medias.

Test con conexiones/procesos reales.

---

# 36. READINESS RACE

Casos obligatorios:

evaluation FULL
→ antes de handoff cambia source

= BLOCK/ROLLBACK.

evaluation FULL
→ cambia configuración

= BLOCK/ROLLBACK.

evaluation FULL
→ aparece operación pendiente

= BLOCK/ROLLBACK.

evaluation FULL
→ expira

= BLOCK.

evaluation FULL
→ cambia session_version

= BLOCK.

No handoff parcial.

---

# 37. PAUSE

Implementar acción humana durable:

enabled
→ paused

con:

- reason tipado/acotado;
- actor;
- session;
- generation;
- timestamp;
- transition receipt;
- snapshot/integrity hash necesario para recovery.

Bajo business gate.

Desde que commit pausa:

cero nuevos efectos financieros.

---

# 38. OPERACIONES PENDIENTES AL PAUSAR

Definir política explícita y conservadora.

Preferencia:

PREPARED/APPROVED de la generación pausada
no deben quedar ejecutables posteriormente.

Puedes:

- terminalizarlas como CANCELLED de forma auditada;

o

- inutilizarlas por generation y exigir nueva identidad/review.

Pero debe quedar demostrado que:

resume nunca revive una autorización vieja.

No borrar operaciones ni autorizaciones.

---

# 39. RECOVERY / RESUME

D solo soporta recuperación del MISMO perfil/grant set.

NO expansión/reducción de capabilities en D.

Para reanudar:

paused
→ validating
→ ready
→ enabled

mediante recovery proof.

No falsificar una nueva evaluación A sobre un boundary
que ya dejó de estar current.

Crear verificador D específico de continuidad post-handoff.

Debe comprobar como mínimo:

- activation receipt intacto;
- grants intactos;
- generation anterior;
- pause receipt;
- no financial source mutation durante pause;
- no EE inesperado;
- no operation effect inesperado;
- configuration compatible;
- no corruption;
- actor/session actual;
- global availability según política;
- exact same profile.

Si hay drift:

PERMANECE PAUSED.

No “arreglar” automáticamente.

---

# 40. PAUSE SNAPSHOT

Después de detener/invalidar operaciones pendientes según política,
guardar un proof/hash canónico del estado relevante.

Debe permitir demostrar en resume:

“desde que se pausó no ocurrió un efecto financiero fuera del control”.

Excluir únicamente cambios transport-level expresamente permitidos
si se justifica.

No esconder cambios económicos.

---

# 41. GENERATION EN RESUME

Resume exitoso:

generation G
→ G+1.

Copiar/reemitir grants exactos bajo nueva generación
con nueva evidencia de recovery.

No reutilizar los rows de grant de G como si fueran actuales.

Las operaciones/auth/mandates de G:

no sirven para G+1.

---

# 42. PROVIDER OUTBOX DURANTE PAUSE

D NO implementa la política completa F.

No borrar:

- outboxes;
- intentos;
- respuestas;
- estados externos.

Una acción externa ya comprometida no se “deshace”.

Documentar claramente qué transport updates existentes
pueden seguir ocurriendo durante pause.

No hacer provider I/O en tests.

F cerrará la política operativa final.

---

# 43. HISTORICAL ANTECEDENTS POST HANDOFF

Test obligatorio:

history candidate válido
→ import
→ E PASS
→ B resolution historical válida
→ activation handoff
→ fence OFF / epoch handed_off
→ B verify_resolution sigue PASS

mientras la fuente histórica no cambie.

Esto demuestra que handoff:

NO destruye la evidencia histórica.

---

# 44. NEW HISTORY POST HANDOFF

Test:

ever_enabled=true
→ HistoryCutoff.open()

FAIL CLOSED.

También:

- new certifiable inventory;
- new historical import;
- new reconciliation de incorporación;

no deben reabrir migration mode.

No afectar lectura/auditoría de historia ya existente.

---

# 45. ACTIVATION CONTROL SQL GUARDS

Proteger estructuralmente:

- states válidos;
- transiciones válidas;
- control_revision monotónico;
- ever_enabled monotónico;
- generation monotónica;
- current profile/evaluation coherentes;
- enabled requiere receipt/grants;
- paused requiere transition receipt;
- direct SQL enabled sin handoff → FAIL;
- direct SQL ever_enabled=false después de true → FAIL;
- direct SQL generation decrement/reuse → FAIL.

---

# 46. HANDOFF SQL GUARDS

Direct SQL no puede marcar:

epoch=handed_off

sin receipt de activación correspondiente.

Tampoco:

fence_enabled=false

para simular handoff sin completar activation.

Los cambios deben quedar coordinados por FKs/guards/transaction.

---

# 47. CONCURRENCIA POSTGRESQL

Como mínimo:

- dos handoff misma solicitud;
- dos handoff diferentes;
- handoff vs writer;
- handoff vs source drift;
- handoff vs session invalidation;
- handoff vs pause imposible;
- pause vs execute;
- pause vs prepare;
- resume vs stale execute;
- dos resume;
- otro business progresa;
- history open vs handoff;
- SQL bypass concurrente.

Sin deadlock.

---

# 48. CRASH POINTS — HANDOFF

Inyectar crash/exception en:

- antes de grants;
- después de grants;
- después de receipt;
- después de live protection;
- después de epoch handed_off;
- después de fence OFF;
- después de activation enabled;
- antes del commit;
- después del commit antes de respuesta.

Antes de commit:

TODO rollback.

Después de commit:

recover exacto.

Nunca:

fence OFF + activation incompleta durable.

---

# 49. CRASH POINTS — PAUSE/RESUME

Probar:

pause antes/después de cada write durable.

resume:

- nueva generation;
- grants;
- state;
- receipt.

Crash precommit:

estado anterior intacto.

Postcommit:

recovery idempotente.

---

# 50. IDEMPOTENCIA

Misma activation request UUID + mismo contenido:

mismo resultado.

Misma UUID + contenido distinto:

Conflict.

Retry handoff ya committed:

devuelve mismo handoff receipt.

Retry pause:

misma transición/receipt.

Retry resume:

misma nueva generación.

No repetir side effects.

---

# 51. MULTI-TENANT

Todo:

business scoped.

FKs compuestas donde proceda.

Otro tenant:

respuesta uniforme.

No filtrar:

- profile;
- evaluation;
- grants;
- epoch;
- operations;
- handoff.

---

# 52. FLAGS

Los cinco valores reales permanecen OFF.

No cambiar:

FINANCIAL_CORE_ENABLED
LEDGER_REPORTING_ENABLED
OPEN_ITEMS_ENABLED
NEW_TAX_ENGINE_ENABLED
NEW_BANK_RECONCILIATION_ENABLED

Tests pueden patchar disponibilidad en memoria.

Ningún commit cambia defaults/config productivos.

---

# 53. SIN PROVIDERS

Parchea para fallar si se intenta llamar:

- AEAT;
- Meta;
- email;
- Stripe mutable;
- webhooks externos;
- almacenamiento externo mutable.

D es 100% DB/local.

---

# 54. SIDE-EFFECT PROOF

Antes/después.

Durante readiness/ready:

solo activation-control evidence.

Durante handoff:

solo:

- activation control;
- activation request/auth;
- grants;
- handoff/transition receipts;
- history epoch/control boundary metadata autorizada.

NO Financial Event por activar.

NO operación financiera.

NO provider.

Durante pause/resume:

solo control plane
+
terminalización/revocación explícitamente autorizada de pending authority,
si esa es la política elegida.

---

# 55. NO ECONOMIC EVENT DE ACTIVACIÓN

Activation/handoff/pause:

NO son Economic Events.

No introducir:

business.activated

en Economic Events.

Son control-plane/audit evidence.

---

# 56. MIGRATION COMPATIBILITY

Actualizar matrices explícitas a schema77:

A
B
C
history

solo donde corresponda.

NO `>=77`.

Migration77:

aditiva cuando sea posible.

Si para ampliar CHECKs SQLite requiere rebuild:

hacerlo transaccionalmente,
con FKs activas,
con copia exacta,
sin normalizar dinero,
sin perder UUID/hash/evidence.

---

# 57. DOWNGRADE

77→76:

solo permitido si NO existe evidencia D.

Si existe:

- grants;
- activation transition;
- handoff;
- ever_enabled;
- pause/recovery;
- operation generation binding;

bloquear downgrade destructivo.

Nunca “volver a legacy” eliminando D.

---

# 58. REGRESIÓN

Ejecutar:

- D SQLite;
- D PostgreSQL;
- concurrencia PG;
- crash processes PG;
- migrations77;
- A readiness;
- B antecedents;
- C fiscal cancellation;
- history A–E;
- InvoiceCapture;
- PaymentCapture;
- BankCapture;
- Supplier/Expense Capture;
- Channels;
- Operations/Auth;
- EE;
- writer guards;
- suite completa;
- JavaScript;
- HTTP smoke.

---

# 59. TEST PRODUCTIVO-SEMÁNTICO IMPORTANTE

Business con:

ever_enabled = false

y sin activación:

el comportamiento pre-D debe permanecer igual.

Deploy de schema77 NO activa automáticamente a nadie.

NO romper negocios legacy existentes.

---

# 60. TEST FAIL-CLOSED IMPORTANTE

Business con:

ever_enabled = true

pero:

FINANCIAL_CORE_ENABLED = false

NO puede ejecutar nuevos efectos.

NO cae a legacy.

---

# 61. PRIMER ENABLE SOLO SINTÉTICO

No activar ningún business real.

Usar únicamente fixtures.

No Noesis19FQA.

No producción.

No backup real.

El hecho de que un test sintético llegue a enabled:

NO significa pilot readiness.

E, F y G siguen pendientes.

---

# 62. DOCUMENTACIÓN

Crear:

- ADR022 o siguiente ADR disponible;
- FINANCIAL-ACTIVATION-HANDOFF-v1.md;
- FASE-1.10D-orden.md;
- FASE-1.10D-cierre.md.

Actualizar:

- FASE-1.10-plan;
- Arquitectura;
- Decisiones;
- Estado;
- Mapa;
- QA;
- Registro cambios;
- project-state;
- guías afectadas.

Registrar:

A CODE-VERIFIED PASS.
B CODE-VERIFIED PASS.
C CODE-VERIFIED PASS.
D solo local hasta revisión.

E NO iniciada.

---

# 63. GATES

- Ruff;
- Bandit;
- credential scan;
- pip-audit;
- migration checks;
- AST previous migrations;
- documentation truth;
- links;
- SQLite;
- PostgreSQL;
- concurrency;
- crash recovery;
- side-effect proof.

---

# 64. ENTREGA LOCAL PRIMERO

Al terminar:

NO PUSH.

Devuélveme:

- rama;
- commit local;
- padre exacto;
- migration77;
- archivos;
- state machine;
- activation request/auth;
- readiness verifier;
- grants;
- generation model;
- handoff receipt;
- epoch handed_off;
- conservación certifiable;
- live write protection;
- Operations generation binding;
- Authorization generation binding;
- mandate policy;
- old operation policy;
- pause;
- recovery;
- SQL guards;
- direct SQL adversarial;
- concurrency;
- crash tests;
- side-effect proof;
- SQLite;
- PostgreSQL;
- suite general;
- riesgos;
- limitaciones;
- autoauditoría.

---

# 65. AUTOAUDITORÍA

Responder explícitamente:

1. ¿Puede D activar producción?
2. ¿Puede activar sin FULL exacto?
3. ¿Puede conceder not_applicable?
4. ¿Puede activar sin human activation authority?
5. ¿Puede usar financial.authorize como activation authority?
6. ¿Puede liberar fence antes de instalar live protection?
7. ¿Puede usar HistoryCutoff.release como handoff?
8. ¿Pierde certifiable el histórico al handoff?
9. ¿Deja de funcionar B historical por hacer handoff?
10. ¿Puede abrirse otro historical epoch después de ever_enabled?
11. ¿Puede una operación pre-handoff ejecutarse después?
12. ¿Puede una operation de generation vieja ejecutarse?
13. ¿Puede una authorization vieja servir en nueva generation?
14. ¿Puede un mandate viejo servir en nueva generation?
15. ¿Puede un command sin grant ejecutarse?
16. ¿Puede un command usar capability distinta?
17. ¿Puede SQL legacy emitir/registrar efecto después de enable sin contexto?
18. ¿Puede un bypass/claim de otra TX reutilizarse?
19. ¿Puede pause crear nuevos efectos?
20. ¿Puede pause borrar historia/evidencia?
21. ¿Puede resume revivir una autorización vieja?
22. ¿Puede resume cambiar el profile en D?
23. ¿Puede global flag OFF provocar fallback legacy?
24. ¿Puede activation crear Economic Events?
25. ¿Puede D hacer provider I/O?
26. ¿Puede D cambiar los cinco flags reales?
27. ¿Puede otro tenant usar grants/evaluation ajenos?
28. ¿Puede una sesión vieja hacer handoff/pause/resume?
29. ¿Puede un crash dejar fence OFF sin activation completa?
30. ¿Se inició 1.10E?

Todas las respuestas peligrosas deben ser:

NO.

---

# CRITERIO FINAL

1.10D solo puede cerrar PASS si queda demostrado:

historical fence
→ atomic handoff
→ generation live protected

sin ninguna ventana desprotegida.

Y además:

- certifiable histórico se conserva;
- B histórico sigue verificable;
- grants son exactos;
- generations invalidan autoridad vieja;
- direct legacy financial writes fallan después de activation;
- drafts no económicos siguen funcionando;
- pause es fail-closed;
- recovery no revive operaciones/autorizaciones viejas;
- crash precommit revierte todo;
- retry postcommit recupera exactamente;
- ningún business real se activa.

Si cualquiera de estas invariantes no puede demostrarse:

NO debilites el diseño.

Devuelve:

1.10D BLOCKED — <motivo concreto>

y detente.

NO avanzar a 1.10E.