# IMPLEMENTAR FASE 1.10C — CAPACIDADES Y FISCAL CANCELLATION LIVE

Las Fases 1.10A y 1.10B quedan validadas.

Base exacta autorizada:

8eb18dbe0c3e97227ee46069fa65087005c39fc8

Crea una nueva rama local desde ESE commit:

codex/phase-1-10c

NO partas de main.

NO hagas merge a main.
NO hagas push a main.
NO despliegues.
NO accedas a producción.
NO accedas a Noesis19FQA.
NO uses backups reales.

Trabaja inicialmente SOLO en local.

Ejecuta exclusivamente Fase 1.10C.

NO avances a 1.10D–H.

---

# OBJETIVO

1.10C tiene DOS entregas estrechamente relacionadas:

A. consolidar el contrato central de capacidades financieras que utilizará
posteriormente la activación;

B. implementar el productor live que falta para:

invoice.fiscal_cancel

de forma totalmente integrada con:

Financial Operations
→ autorización humana
→ writer fiscal existente
→ cancellation record
→ outbox fiscal
→ Economic Event
→ durable result

SIN activar ningún negocio y SIN realizar ninguna llamada a AEAT.

---

# PRINCIPIO ABSOLUTO

Fase 1.10C NO activa el Financial Core.

Debe seguir siendo imposible:

off → ready
off → enabled
validating → enabled

No implementar handoff.

No liberar fence.

No incrementar activation_generation.

No cambiar ever_enabled.

No conectar todavía Web, WhatsApp, tools, API, documents,
recurrentes o workers al nuevo activation control.

Los cinco flags permanecen OFF.

---

# 1. BASE ARQUITECTÓNICA

Conserva:

- Financial Core modular monolith.
- FinancialSession prestada.
- outer service owns transaction.
- business gate antes de efectos.
- AI nunca concede autoridad.
- Economic Events son hechos, no comandos.
- Operations/Auth son autoridad y ejecución.
- Antecedent resolution es evidencia, no autoridad.

No introducir:

- bus genérico;
- CQRS;
- microservicios;
- ORM nuevo;
- segunda conexión dentro de una TX financiera.

---

# 2. CAPABILITY REGISTRY CENTRAL

A ya definió 15 capacidades.

No crear un segundo catálogo contradictorio.

Construye una representación central/versionada que permita responder:

Capability
→ dependencias
→ comando/productor asociado
→ disponibilidad de implementación
→ requisitos adicionales

Debe seguir existiendo UN catálogo conceptual.

Puedes refactorizar de forma mínima el catálogo A si mejora la arquitectura,
pero:

- no cambies su semántica;
- no cambies content hashes anteriores;
- no alteres evaluaciones A existentes;
- añade tests de compatibilidad.

---

# 3. COMMAND → CAPABILITY

Crear mapping cerrado para TODOS los CommandType financieros actuales.

Como mínimo:

invoice.issue
→ invoice.issue

invoice.rectify
→ invoice.rectify

customer_payment.record
→ customer_payment.record

supplier_invoice.confirm
→ supplier_invoice.confirm

supplier_invoice.correct
→ supplier_invoice.correct

supplier_invoice.void
→ supplier_invoice.void

expense.confirm
→ expense.confirm

expense.void
→ expense.void

bank_transaction.import
→ bank_transaction.import

bank_transaction.match
→ bank_transaction.match

invoice.fiscal_cancel
→ invoice.fiscal_cancel

Nada queda sin mapping silenciosamente.

Si aparece CommandType desconocido:

FAIL CLOSED.

---

# 4. NO ENFORCEMENT PRODUCTIVO TODAVÍA

El registry/policy de capabilities NO se conecta todavía al routing actual.

No bloquear actuales clientes legacy porque activation state todavía no existe.

No añadir checks parciales solo en algunos canales.

La enforcement live por business/generation llegará en 1.10D.

C deja preparado el contrato que D consumirá.

---

# 5. ESTADO DE `invoice.fiscal_cancel`

Actualmente existe:

- CommandType.INVOICE_FISCAL_CANCEL;
- EventType invoice.fiscal_cancellation_registered;
- SourceType invoice_cancellation_record;
- writer existente:
  financial_writers.invoices.create_invoice_cancellation_record;
- generación de registro Veri*Factu;
- cadena fiscal;
- verifactu_cancellation_outbox.

Lo que falta es el PRODUCTOR CAPTURE live.

NO reimplementes el cálculo fiscal.

NO reimplementes el hash Veri*Factu.

NO reimplementes el encadenamiento.

NO reconstruyas registros existentes.

Reutiliza el writer actual.

---

# 6. NUEVO PRODUCTOR

Implementa un productor interno coherente con:

InvoiceCapture
PaymentCapture
BankCapture
Purchasing Capture

Nombre orientativo:

FiscalCancellationCapture

o una ubicación coherente dentro de invoice_capture si arquitectónicamente
es mejor.

Debe exponer el flujo:

review
→ prepare
→ authorize
→ execute

No endpoint público todavía.

---

# 7. ANTECEDENTE OBLIGATORIO

FiscalCancellationCapture debe exigir una resolución B DURABLE:

purpose = fiscal_cancel_invoice
outcome = resolved
quality = verified_fact

NO aceptar:

- invoice_id libre sin proof;
- event_uuid libre;
- status textual;
- histórico aproximado;
- payload suministrado por IA.

El caller proporciona la resolution durable exacta.

El productor debe ejecutar:

verify_resolution(...)

dentro de la FinancialSession prestada.

Revalidar como mínimo en:

- review;
- antes de autorizar cuando corresponda;
- execute.

Una resolution stale:

ABORT.

---

# 8. FACTURA HISTÓRICA

Invoice historical v2 sigue BLOQUEADA.

FiscalCancellationCapture NO es una vía indirecta para cancelarla.

Actualmente B bloquea factura historical.

Mantenerlo.

No crear excepciones.

---

# 9. OPERACIÓN FINANCIERA

Usar:

CommandType.INVOICE_FISCAL_CANCEL

La operación debe tener autoridad live NORMAL:

human_confirmation

No historical_unknown.

No aprobación IA.

No mandato en C salvo que exista proof suficiente ya aprobado;
la política actual B que bloquea mandates insuficientes se conserva.

Preferencia conservadora para C:

human_confirmation exclusivamente.

---

# 10. SEMÁNTICA DEL REQUEST

La cancelación fiscal NO es una reversión económica.

Preferencia:

FinancialRequest.amount = None

porque el comando no representa movimiento monetario.

El total original debe quedar únicamente como contexto exacto
de la evidencia/evento.

Target:

invoice_id exacto.

Reason:

obligatorio, 5–1000 caracteres, coherente con writer existente.

El request debe vincular de forma cerrada:

- antecedent resolution UUID;
- resolution content/context hash;
- invoice event UUID;
- source revision;
- evidencia fiscal relevante;
- configuración aprobada necesaria.

No duplicar payloads completos innecesariamente.

---

# 11. REVIEW

review() debe:

1. autenticar principal;
2. usar Financial Operations transaction;
3. verificar resolution B;
4. comprobar purpose exacto;
5. comprobar quality verified_fact;
6. comprobar factura exacta;
7. comprobar fiscal evidence;
8. comprobar que el alta original es fiscalmente válida;
9. comprobar que la AEAT aceptó el alta según evidencia local durable;
10. comprobar que no existe cancellation previa;
11. construir FinancialRequest completo.

NO crear cancellation record.

NO crear outbox.

NO crear EE.

NO llamar AEAT.

---

# 12. PREPARE

prepare() usa EntryIdentity existente.

No inventar identidad nueva.

Debe:

- validar contrato;
- preparar Financial Operation;
- comprobar revisión/contexto;
- no producir efecto financiero/fiscal.

Retry exacto:

misma operación.

---

# 13. AUTHORIZE

authorize() debe usar FinancialOperations.

Exigir:

- human_confirmation;
- approved request hash exacto;
- revisión/contexto exactos;
- resolution aún válida.

No autoridad implícita.

No AI approval.

---

# 14. EXECUTE

Dentro de UNA ÚNICA transacción:

1. FinancialOperations valida operación/auth.
2. business gate ya adquirido.
3. revalidar resolution B.
4. revalidar factura y evidencia fiscal.
5. confirmar ausencia de cancellation previa incompatible.
6. llamar al writer EXISTENTE:

   financial_writers.invoices.create_invoice_cancellation_record

7. obtener SourceSnapshot real del cancellation_record.
8. registrar coverage C.
9. crear Economic Event:
   invoice.fiscal_cancellation_registered
10. relacionarlo mediante:
    evidence_for → invoice.issued / invoice.rectified original
11. persistir resultado durable.
12. commit único del propietario exterior.

NO llamada AEAT dentro de esta transacción.

El writer ya crea el outbox local pendiente.

Eso es correcto.

---

# 15. ECONOMIC EVENT

Usar exactamente el contrato existente:

EventType.INVOICE_FISCAL_CANCELLATION_REGISTERED

SourceType.INVOICE_CANCELLATION_RECORD

Payload v1:

- invoice_id
- invoice_number
- original_total
- registered_on
- reason

IMPORTANTÍSIMO:

event.amount debe seguir siendo None.

`original_total` es SOLO contexto firmado.

NO:

- reducir deuda;
- cambiar saldo;
- borrar cobros;
- crear devolución;
- crear reversión GL;
- marcar factura como económicamente anulada.

Mantener:

fiscal cancellation
≠ economic reversal
≠ debt cancellation

---

# 16. TOTAL ORIGINAL

`original_total` debe proceder del antecedente verified.

Decimal/EUR exacto.

Nunca:

- invoice.total legacy float convertido;
- Decimal(str(float));
- SUM legacy aproximado.

Debe coincidir con el Economic Event original verificado.

---

# 17. SOURCE REVISION

NO inventar source_revision=1.

Utiliza la revisión/fingerprint producida por:

financial_writers.boundary.snapshot

sobre:

invoice_cancellation_record

después del writer.

La revisión del Event debe ser la del SourceSnapshot real.

---

# 18. EVENT UUID

Derivar deterministicamente desde operation_uuid con UUIDv5
y slot/nombre cerrado.

Por ejemplo conceptualmente:

invoice.fiscal_cancellation.primary.v1

Elige naming coherente con productores existentes.

Retry de misma operación:

mismo event UUID.

---

# 19. COVERAGE DURABLE

Migration 76 debe crear coverage específico.

Nombre orientativo:

invoice_fiscal_cancellation_coverage

Debe vincular como mínimo:

- business_id;
- invoice_id;
- cancellation_record_id;
- antecedent_resolution_uuid;
- original_invoice_event_uuid;
- event_uuid;
- operation_uuid;
- event_type;
- source_revision;
- operation_state = committed.

Añade hashes/proof refs solo cuando aporten una invariante real.

No duplicar toda resolution.

---

# 20. FKs COVERAGE

Tenant-scoped.

Debe poder demostrar estructuralmente:

operation
↔ cancellation record
↔ invoice
↔ antecedent resolution
↔ original event
↔ cancellation EE

Utiliza FKs compuestas y diferidas donde corresponda.

No quitar FKs antiguas.

---

# 21. SQL GUARDS

Probar en PostgreSQL y SQLite.

Coverage solo puede insertarse cuando:

- operation está approved;
- command_type = invoice.fiscal_cancel;
- target invoice coincide;
- resolution pertenece al mismo business;
- resolution está resolved;
- purpose=fiscal_cancel_invoice;
- quality=verified_fact;
- original event coincide;
- no cancellation diferente previa.

Economic Event solo es válido si:

- origin=live;
- source=cancellation_record;
- tipo exacto;
- operation exacta;
- coverage exacta;
- relation evidence_for exacta;
- payload coherente.

Operation solo puede COMMIT si:

- coverage existe;
- EE existe;
- result exacto coincide.

---

# 22. IDEMPOTENCIA

Misma operation:

→ original result.

Timeout después de commit:

→ recover mismo resultado.

Misma EntryIdentity/request:

→ misma operación.

Una SEGUNDA operación diferente contra invoice ya cancelada:

→ BLOCK/CONFLICT.

NO adjuntar el cancellation_record ya existente a una operación nueva.

---

# 23. LEGACY CANCELLATION EXISTENTE

Si ya existe invoice_cancellation_record pero NO pertenece a este producer/coverage:

NO adoptarlo como live.

NO crear EE retrospectivo.

NO crear coverage ficticio.

Bloquear como antecedente/estado ya existente.

History deberá tratarlo por sus contratos propios.

---

# 24. OUTBOX

El writer existente crea:

verifactu_cancellation_outbox

con estado pendiente.

1.10C NO debe despacharlo.

NO llamar:

verifactu_client.submit_records

NO HTTP.

NO AEAT pruebas ni producción.

Solamente probar que el outbox local correcto se crea
atómicamente con el registro fiscal.

---

# 25. AEAT ORIGINAL ACCEPTED

La cancelación local solo se permite cuando el alta original
tiene evidencia durable local de:

aceptado
o
aceptado_con_errores

según contrato/writer actual.

No reinterpretar timeout como aceptación.

No inventar provider attestation.

---

# 26. CAPABILITY `invoice.fiscal_cancel`

Ahora que el producer live existe, deja de ser correcto bloquearla
únicamente porque “el producer no está implementado”.

Actualiza readiness/capability policy SOLO en lo estrictamente necesario:

- producer implementation → disponible localmente;
- provider.aeat_dispatch → sigue requiriendo preflight futuro;
- privacy/export → siguen pendientes;
- continuity → donde corresponda sigue pendiente;
- cinco flags OFF.

NO convertir ningún perfil financiero artificialmente en FULL.

---

# 27. DEPENDENCIA `invoice.issue`

En modo Veri*Factu:

invoice.issue

debe seguir cerrando sus dependencias necesarias:

- invoice.rectify;
- invoice.fiscal_cancel;
- provider.aeat_dispatch;
- channel correspondiente.

La existencia del producer cancel NO implica
provider.aeat_dispatch listo.

Por tanto la readiness global puede continuar BLOCKED/PARTIAL
hasta fases posteriores.

---

# 28. CAPABILITY BLOCKING TRANSVERSAL

Construir contrato reusable para que D pueda posteriormente exigir:

command
→ capability
→ granted capability exacta.

Pero NO conectarlo aún al runtime de clientes.

Tests deben demostrar que:

- ningún CommandType financiero queda sin capability;
- una dependencia blocked bloquea consumidor;
- capability desconocida falla cerrado;
- not_applicable no equivale a granted.

---

# 29. `not_applicable`

Regla importante heredada de A:

not_applicable

puede ayudar al resultado de readiness,
pero NUNCA significa:

capability granted.

Deja contrato/test explícito para consumo futuro.

---

# 30. OBSERVED_STATE

Nada de C puede convertir:

observed_state

en antecedente operativo.

Fiscal cancellation exige:

verified_fact.

`inspect_evidence` sigue siendo el único uso resolved admitido
para observed_state.

Añade regresión explícita.

---

# 31. MANDATES

NO ampliar B silenciosamente.

Actualmente ProofChecker no considera suficientes los mandates
para antecedente verified.

Conservar esta limitación.

Documentar que soporte completo de operaciones/antecedentes creados
mediante mandate requerirá proof adicional futuro.

No degradar seguridad para hacer pasar C.

---

# 32. NO ROUTING

No modificar todavía:

- web routes;
- WhatsApp;
- tools;
- agent;
- recurrentes;
- documentos;
- workers;

para llamar FiscalCancellationCapture.

El producer debe existir como API interna de servidor y tests.

Routing llegará cuando D/F hayan cerrado activation/preflight.

---

# 33. NO HANDOFF

No implementar:

- ready;
- enabled;
- paused;
- handed_off;
- activation_generation>0;
- activation transition receipts.

Eso es 1.10D.

---

# 34. SIDE-EFFECT PROOF

Para policy/capability evaluation:

cero efectos financieros.

Para review/prepare:

solo Operations cuando corresponda.

Para execute fiscal cancellation se permiten EXCLUSIVAMENTE
los efectos contractuales necesarios:

- financial_operations;
- financial_authorizations;
- invoice_cancellation_records;
- verifactu_cancellation_outbox;
- invoice_events operacional ya generado por writer existente;
- nueva fiscal cancellation coverage;
- economic_events;
- economic_event_links;
- economic_event_sequences;
- resultado de operation.

NO modificar:

- invoice original económica;
- invoice payments;
- bank transactions;
- received invoices;
- expenses;
- history A–E;
- antecedent resolution;
- activation control;
- readiness evidence;
- cinco flags.

Snapshot antes/después.

---

# 35. NO CAMBIAR VERI*FACTU

Especialmente:

NO modificar algoritmos existentes de:

- invoice_record_hash;
- cancellation_record_hash;
- chain;
- QR;
- XML;
- record numbering;
- previous_hash;
- outbox existing semantics.

Goldens/parity existentes deben seguir verdes.

---

# 36. CONCURRENCIA

PostgreSQL obligatoria.

Probar:

- dos execute misma operation;
- dos operaciones distintas intentando cancelar misma invoice;
- cancel vs rectification concurrente;
- source/config change;
- stale antecedent resolution;
- otro business progresa;
- respuesta perdida después del commit;
- lock fiscal chain + business gate sin deadlock.

Mismo negocio debe serializar correctamente.

---

# 37. CRASH POINTS

Probar rollback/crash:

- antes del writer;
- después de cancellation_record;
- después de outbox;
- después de coverage;
- después de EE;
- antes de result;
- después de commit/antes de respuesta.

Antes de commit:

0 efecto parcial durable.

Después de commit:

recover exacto.

---

# 38. TEST POSITIVO COMPLETO

Fixture sintético:

1. invoice draft;
2. InvoiceCapture review/prepare/authorize/execute;
3. invoice EE live v2;
4. fiscal record existente;
5. alta AEAT localmente marcada con respuesta fixture aceptada
   usando mecanismos de test existentes, SIN red;
6. persistir B resolution purpose fiscal_cancel_invoice;
7. FiscalCancellationCapture review;
8. prepare;
9. human authorize;
10. execute.

Verificar:

- cancellation_record creado;
- outbox cancellation pendiente;
- coverage C;
- Economic Event fiscal cancellation;
- relation evidence_for original exacta;
- operation committed;
- result exacto;
- invoice original intacta económicamente;
- pagos intactos;
- event.amount=None.

---

# 39. NEGATIVOS

Como mínimo:

- invoice no emitida;
- invoice historical;
- invoice historical v2 unsupported;
- resolution blocked;
- resolution observed_state;
- purpose incorrecto;
- resolution stale;
- otro tenant;
- sesión vieja;
- alta AEAT no aceptada;
- fiscal record ausente;
- outbox alta pendiente;
- outbox alta rechazada;
- cancellation existente legacy;
- cancellation ya capturada;
- wrong invoice event;
- corrupted fiscal record;
- corrupted chain;
- source revision drift;
- reason inválido;
- operation no autorizada;
- mandate no probado;
- SQL directo coverage falsa;
- SQL directo EE incompatible;
- duplicate operation diferente;
- provider I/O llamado por error.

---

# 40. MIGRACIÓN

Nueva migration:

76

salvo blocker técnico fuerte documentado.

Aditiva.

No modificar migrations 63–75.

Actualizar matrices explícitas:

A readiness compatible con schema 76.
B antecedents compatible con schema 76.
History A–E según corresponda.

NO usar `>=`.

Downgrade 76→75:

permitido si tablas/evidencia C están vacías.

Si existe coverage/event/result que dependa de C:

bloquear pérdida.

SQLite + PostgreSQL.

---

# 41. TESTS REGRESIÓN

Ejecutar:

- C SQLite;
- C PostgreSQL;
- concurrencia PG;
- migration 76;
- A readiness;
- B antecedents;
- history A–E;
- InvoiceCapture;
- PaymentCapture;
- BankCapture;
- Purchasing Capture;
- VERI*FACTU goldens/parity;
- Operations/Auth;
- suite completa;
- JavaScript si workflow lo exige.

---

# 42. GATES

Además:

- Ruff;
- Bandit;
- credential/secrets scan;
- dependency audit;
- documentation truth;
- enlaces;
- AST / migrations previous intactas.

---

# 43. PRODUCCIÓN / QA

NO:

Railway
producción
Noesis19FQA
backup real
AEAT real
Meta real

Fixtures sintéticos únicamente.

---

# 44. DOCUMENTACIÓN

Crear:

- contrato 1.10C;
- ADR correspondiente;
- FASE-1.10C-orden.md;
- FASE-1.10C-cierre.md.

Actualizar plan/estado/arquitectura.

Registrar explícitamente:

- 1.10A CODE-VERIFIED PASS;
- 1.10B CODE-VERIFIED PASS;
- 1.10C no activa negocios;
- cinco flags OFF;
- 1.10D no iniciada.

---

# 45. ENTREGA LOCAL PRIMERO

Al terminar:

NO hagas push todavía.

Devuélveme:

- rama;
- commit local;
- padre exacto;
- migration;
- archivos;
- capability registry;
- command mapping;
- producer fiscal;
- request contract;
- coverage;
- SQL guards;
- antecedent integration;
- exact money;
- Economic Event;
- relation;
- outbox;
- idempotency;
- concurrency;
- crash tests;
- side-effect proof;
- SQLite;
- PostgreSQL;
- suite;
- riesgos;
- limitaciones;
- autoauditoría.

---

# 46. AUTOAUDITORÍA

Responder explícitamente:

1. ¿Puede C activar un business?
2. ¿Puede pasar a ready/enabled/paused?
3. ¿Puede incrementar activation_generation?
4. ¿Puede liberar/handoff fence?
5. ¿Puede cambiar los cinco flags?
6. ¿Puede llamar AEAT?
7. ¿Puede hacer cualquier provider I/O?
8. ¿Puede fiscal cancellation generar un amount económico?
9. ¿Puede reducir deuda?
10. ¿Puede borrar/alterar cobros?
11. ¿Puede modificar invoice original económicamente?
12. ¿Puede adoptar una cancellation legacy como live?
13. ¿Puede cancelar una invoice historical unsupported?
14. ¿Puede usar observed_state operativamente?
15. ¿Puede usar resolution stale?
16. ¿Puede saltarse human confirmation?
17. ¿Puede un segundo operation adoptar el mismo cancellation record?
18. ¿Puede un CommandType quedar sin capability mapping?
19. ¿Puede not_applicable interpretarse como capability granted?
20. ¿Se inició 1.10D?

Todas las respuestas peligrosas deben ser:

NO.

---

# CRITERIO DE CIERRE

1.10C solo puede cerrar PASS si:

- capability model es cerrado y compatible con A;
- todos los CommandType financieros están mapeados;
- fiscal cancellation producer usa Financial Operations;
- antecedent B se revalida;
- human authorization es exacta;
- writer Veri*Factu existente se reutiliza;
- cancellation record + outbox + coverage + EE + result son atómicos;
- EE es evidence-only;
- original_total nunca se interpreta como reversión;
- no provider I/O ocurre;
- no activación ocurre;
- todos los gates pasan.

NO avanzar a 1.10D.