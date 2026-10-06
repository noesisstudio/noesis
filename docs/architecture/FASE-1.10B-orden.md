IMPLEMENTAR FASE 1.10B — ANTECEDENTES Y CONTINUIDAD HISTORICAL→LIVE
1.10A queda validada.
Base exacta:
c9106165195cc053c8d713b7a94557df28bc4099
Crea una nueva rama desde ese commit:
codex/phase-1-10b
NO partas de main.
NO hagas merge/push a main.
NO despliegues.
Ejecuta exclusivamente 1.10B.
NO implementes 1.10C–H.
OBJETIVO
Construir una capa durable y verificable que responda:
“¿Qué antecedente económico/documental exacto puede usar esta futura operación live, con qué grado de certeza y para qué propósito concreto?”
Debe permitir en fases posteriores continuidad segura:
historical antecedent → future live operation
y
live antecedent → future live operation
sin:
- convertir historical en live;
- copiar eventos históricos a coverages live;
- inventar autoridad;
- inferir por importe/fecha;
- activar business;
- liberar fence;
- ejecutar Financial Operations.
1. PRINCIPIO CENTRAL
Un antecedente es evidencia, NO autoridad.
Una resolución de antecedente:
- identifica un hecho existente;
- acredita su origen;
- acredita su calidad;
- declara para qué propósito puede utilizarse;
- conserva unknowns;
pero nunca:
- autoriza dinero;
- crea un hecho;
- modifica el hecho;
- activa una capability.
2. NO ACTIVACIÓN
1.10B NO puede:
- cambiar activation state;
- pasar a ready;
- pasar a enabled;
- pasar a paused;
- incrementar activation_generation;
- cambiar ever_enabled;
- liberar/handed_off epoch;
- cambiar cinco flags.
financial_activation_control de A puede ser leído, no utilizado para activar.
3. NO ROUTING
No conectar todavía:
- Web;
- WhatsApp;
- API;
- tools;
- recurrentes;
- document review;
- Capture runtime.
No modificar rutas productivas para consumir resolver.
B construye infraestructura y pruebas.
4. MODELO financial_antecedents
Implementar módulo separado, por ejemplo:
src/noesis/financial_antecedents/
con:
- contracts
- resolver
- repository
- schema
Mantener monolito modular.
No meter lógica grande en db.py.
5. HISTORICAL VS LIVE
Tipar origen cerrado:
- historical
- live
No tercer estado ambiguo.
Si no puede demostrarse:
no existe resolución verified.
6. CALIDAD
Catálogo cerrado:
- verified_fact
- observed_state
Reglas:
verified_fact
exige prueba durable completa.
observed_state
conserva incertidumbre y nunca puede usarse en un propósito que exija verdad económica completa.
No promover B observed_state a verified.
7. PROPÓSITOS
Crear catálogo cerrado/versionado de propósitos.
Como mínimo analizar:
- customer_payment_against_invoice
- rectify_invoice
- fiscal_cancel_invoice
- bank_match_invoice
- supplier_invoice_correct
- supplier_invoice_void
- expense_void
Ajusta nombres al estilo del proyecto.
Un antecedente puede ser apto para un propósito y no para otro.
NO existe:
verified → sirve para todo.
8. IDENTIDAD
Resolver siempre por identidad fuerte:
- business;
- source type;
- source id;
- revision;
- Economic Event UUID cuando exista;
- relaciones exactas.
PROHIBIDO resolver por:
- importe parecido;
- misma fecha;
- mismo cliente;
- texto;
- status legacy;
- proximidad temporal.
9. HISTORICAL PROOF
Para origen historical exigir como mínimo:
- Economic Event durable;
- origin=historical;
- HistoricalIdentity válida;
- proof original de importación;
- operation histórica correcta;
- authorization historical_unknown;
- batch original;
- reconciliation correspondiente;
- handoff/readiness todavía NO necesario en B porque aún no existe handoff;
- relaciones/dependencias exactas.
No crear proof histórica nueva.
Reutilizar/verificar la durable existente.
10. LIVE PROOF
Para origen live exigir:
- Economic Event durable;
- operación COMMITTED;
- autorización válida;
- coverage live exacta cuando el dominio la requiera;
- source/revision;
- links correctos.
No aceptar únicamente la fila legacy/source.
11. financial_antecedent_resolutions
Añadir migration posterior a 74.
Una resolución durable debe contener como mínimo:
- business_id;
- resolution_uuid;
- resolution_version;
- purpose;
- source_type/source_id/revision;
- event_uuid;
- origin;
- quality;
- known/unknown field proof;
- source/content/record hashes;
- operation/auth refs cuando apliquen;
- historical proof refs cuando apliquen;
- created_by/session;
- context hash;
- canonical result;
- content hash;
- created_at;
- expiry o mecanismo explícito de revalidación.
No duplicar payload completo innecesariamente.
No PII libre.
12. INMUTABILIDAD
Una resolución final:
- no UPDATE;
- no DELETE;
- retry mismo UUID/contexto → mismo resultado;
- mismo UUID/contexto distinto → conflict.
Una fuente que cambia exige nueva resolución.
13. UNKNOWN
Unknown continúa unknown.
No:
- NULL→0;
- fecha desconocida→hoy;
- binary legacy→Decimal exacto;
- estado “pagada”→pago confirmado.
Los campos relevantes conocidos/desconocidos deben entrar en el proof.
14. DINERO
Nunca usar:
Decimal(str(float))
para conceder certeza.
Historical legacy binary solo puede participar cuando el contrato histórico ya haya acreditado exactamente la evidencia requerida.
Si falta:
resolución BLOCKED/UNAVAILABLE.
15. FACTURA HISTÓRICA V2
Sigue BLOQUEADA.
Resolver NO puede convertirse en una vía alternativa para desbloquearla.
Si una factura histórica no dispone del contrato suficiente:
UNSUPPORTED_ANTECEDENT
o reason equivalente.
16. registro_anterior
No puede convertirse en:
- verified payment;
- saldo satisfecho;
- authority.
Mantener bloqueo.
17. COBRO FUTURO SOBRE FACTURA
Diseñar y probar resolución de antecedente de factura apta para futuro cobro.
Exigir:
- factura verificable;
- total exacto;
- currency;
- estado relevante;
- cobertura completa de cobros previos;
- ausencia de huecos;
- fiscal/documental cuando el propósito lo requiera.
Calcular saldo únicamente desde hechos exactos/verificados.
NO implementar Open Items.
NO ejecutar el cobro.
18. BANK MATCH
Un match futuro exige:
- movimiento bancario live válido;
- factura antecedente resoluble;
- propósito bank_match;
- capacidad futura todavía fuera de B.
Recordar:
bank match es Evidence-only.
Nunca crear un segundo cash event.
En B solo resolver/probar antecedentes.
19. SUPPLIER / EXPENSE
Para correct/void:
antecedente verified_fact y estado anterior completo.
Un B observed_state puede permanecer consultable pero:
si el propósito exige certeza que no tiene:
bloquear.
20. RECTIFICACIÓN
Antecedente exacto obligatorio.
No permitir:
- source aproximada;
- invoice historical v2 bloqueada;
- relación inferida.
No crear rectificativa en B.
21. FISCAL CANCEL
Resolver antecedente fiscal puede implementarse como contrato/evidencia.
NO implementar todavía productor live.
NO enviar AEAT.
NO registrar cancelación.
La capacidad seguirá bloqueada hasta 1.10C.
22. READINESS A
Integración mínima permitida:
el evaluator de A puede, si resulta arquitectónicamente necesario, utilizar solo información read-only del resolver para explicar readiness.
Pero:
- no cambiar outcomes de A para hacer perfiles artificialmente FULL;
- no activar nuevas capacidades;
- no eliminar blockers de privacidad/export/provider/continuidad que pertenecen a fases posteriores.
Preferencia:
mantener A estable y probar B independientemente.
23. RESOLVER PURO
Separar:
resolve/check
de
persist resolution.
La parte verificadora debe poder ejecutarse con FinancialSession prestada dentro de la futura transacción de handoff/ejecución.
No abrir conexión propia.
No commit propio.
24. REVALIDACIÓN
Una resolución almacenada NO es permiso perpetuo.
Diseñar:
verify_resolution(session, resolution)
que compruebe:
- source/revision actual;
- event;
- hashes;
- origin;
- operation/auth;
- links;
- historical/live proof;
- purpose.
Cualquier cambio:
stale/conflict.
25. DEPENDENCIAS
Antecedentes con relaciones deben probar:
- mismo business;
- target exacto;
- relation type exacto;
- revision exacta cuando proceda.
No aceptar links extra/ausentes silenciosamente.
26. FKs
NO elimines FKs actuales para “hacer funcionar historical”.
Si los futuros hijos necesitan referenciar antecedente histórico:
diseña adaptación aditiva/protegida.
En 1.10B puede añadirse infraestructura durable necesaria, pero NO conectar todavía writers live.
Cualquier FK nueva:
tenant-scoped.
27. REASONS
Catálogo cerrado como mínimo:
- ANTECEDENT_NOT_FOUND
- ANTECEDENT_UNSUPPORTED
- ANTECEDENT_NOT_VERIFIED
- OBSERVED_STATE_INSUFFICIENT
- SOURCE_CHANGED
- EVENT_MISSING
- EVENT_INVALID
- OPERATION_INVALID
- AUTHORIZATION_INVALID
- COVERAGE_INCOMPLETE
- PAYMENT_HISTORY_INCOMPLETE
- MONEY_UNCERTAIN
- DATE_UNCERTAIN
- FISCAL_EVIDENCE_INCOMPLETE
- DEPENDENCY_INVALID
- PURPOSE_NOT_ALLOWED
- HISTORICAL_PROOF_INVALID
- LIVE_PROOF_INVALID
Ajusta nombres si conviene, sin abrir catálogo libre.
28. RESULTADOS
Resultado de resolución:
- resolved
- blocked
Si quieres distinguir not_found, hazlo como reason, no creando estados ambiguos salvo justificación fuerte.
Una resolución BLOCKED también puede quedar durable para auditoría/idempotencia.
29. PERMISOS
Resolver/readiness no equivale a authorization.
Definir permiso de resolución/lectura si hace falta.
NO utilizar:
- financial.authorize;
- mandate;
- historical_unknown
como permiso de resolver.
Ninguna resolución concede futura ejecución.
30. MULTI-TENANT
Toda tabla/query/FK:
business-scoped.
Referencia ajena:
AccessDenied uniforme.
No confirmar existencia de eventos de otro tenant.
31. CONCURRENCIA
PostgreSQL:
probar:
- misma resolution UUID;
- dos UUID mismo antecedente;
- source change concurrente;
- event/link change/corruption fixture;
- otro business progresa.
Utilizar business gate donde sea necesario.
No deadlock con orden actual.
32. SIDE-EFFECT PROOF
Durante resolución solo pueden cambiar:
- nuevas tablas B;
- metadata migration.
NO:
- sources;
- Economic Events;
- Operations/Auth;
- coverages;
- history A–E;
- activation A;
- fiscal;
- bank;
- channels;
- flags.
Snapshot completo antes/después.
33. SQL GUARDS
Impedir:
- UPDATE/DELETE resolution final;
- cross-tenant refs;
- origin inválido;
- quality inválida;
- purpose inválido;
- resolved sin proof estructural;
- historical marcado live;
- live marcado historical cuando las refs contradigan;
- cambio de hashes después de final.
SQL privilegiado que deshabilite guards queda fuera del threat model, documentarlo.
34. TESTS POSITIVOS SINTÉTICOS
Es obligatorio ejercitar de verdad:
Historical
Un candidato histórico sintético importado correctamente:
candidate
→ historical operation
→ historical_unknown
→ historical EE
→ E PASS
→ antecedent resolved.
Esto es importante porque 1.9F no tuvo candidatos reales.
Live
Una operación live existente válida:
committed operation
→ auth
→ EE
→ coverage
→ antecedent resolved.
35. TESTS NEGATIVOS
Como mínimo:
- historical v2 invoice unsupported;
- registro_anterior;
- B observed_state para propósito que exige verified;
- float/binary uncertain;
- NULL relevante;
- missing event;
- corrupted event;
- wrong operation;
- wrong authorization;
- incomplete coverage;
- missing prior payment;
- wrong tenant;
- source drift;
- missing/extra dependency;
- wrong purpose;
- stale resolution;
- duplicate UUID different context.
36. BANK MATCH SEMÁNTICO
Test explícito:
resolver una factura para bank match NO crea:
- payment;
- customer_payment.received;
- bank_transaction.matched;
- ningún EE.
Cero side effects.
37. FLAGS
Cinco flags permanecen OFF.
Resolver debe funcionar en pruebas sin reinterpretarlos como permiso.
No alterar configuración.
38. MIGRACIÓN
Nueva migration 75 salvo motivo técnico real para otra numeración.
Aditiva.
63–74 intactas.
Schema compatibility explícita.
Downgrade:
- vacío permitido;
- con evidence durable, bloquear pérdida.
SQLite y PostgreSQL.
39. NO PROD / NO QA REAL
Solo fixtures sintéticos.
No consultar:
- Railway;
- producción;
- Noesis19FQA;
- backups reales.
No hace falta para B.
40. GATES
Ejecutar:
- B SQLite;
- B PostgreSQL;
- concurrencia PG;
- migration 75;
- regresiones A–E;
- readiness A;
- suite general;
- Ruff;
- Bandit;
- secrets;
- dependency audit;
- documentation truth;
- links.
41. CIERRE
Entregar:
- commit;
- rama;
- migration;
- archivos;
- contrato;
- ADR;
- catálogo purposes;
- catálogo reasons;
- schema;
- resolver;
- verification path;
- historical proof;
- live proof;
- unknown handling;
- money;
- dependencies;
- FKs;
- idempotency;
- concurrency;
- side-effect proof;
- SQLite;
- PostgreSQL;
- suite;
- riesgos;
- limitaciones;
- autoauditoría.
Autoauditoría:
1. ¿Puede B activar un business?
2. ¿Puede B cambiar activation state/generation?
3. ¿Puede liberar fence?
4. ¿Puede producir EE?
5. ¿Puede ejecutar Financial Operations?
6. ¿Puede convertir historical en live?
7. ¿Puede copiar historical a live coverage?
8. ¿Puede promover observed_state a verified?
9. ¿Puede resolver por importe/fecha aproximada?
10. ¿Puede tratar registro_anterior como cobro?
11. ¿Puede desbloquear invoice historical v2?
12. ¿Puede crear bank match/payment?
13. ¿Puede hacer provider I/O?
14. ¿Puede mutar source/event/op/auth?
15. ¿Puede una resolution stale seguir válida?
16. ¿Puede cruzar tenant?
17. ¿Puede un UUID reutilizarse con otro contexto?
18. ¿Unknown se conserva?
19. ¿Cinco flags siguen OFF?
20. ¿Se inició 1.10C?
Todas las respuestas peligrosas:
NO.
NO avanzar a 1.10C.