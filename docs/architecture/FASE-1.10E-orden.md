# IMPLEMENTAR FASE 1.10E — PRIVACY, EXPORT, RETENCIÓN Y CIERRE CON CONSERVACIÓN

Las Fases 1.10A, 1.10B, 1.10C y 1.10D quedan CODE-VERIFIED PASS.

Base exacta autorizada:

8a775989e350daf3c2bb8c4f9c4d515b7b3ef696

Crea una nueva rama LOCAL desde ESE commit:

codex/phase-1-10e

NO partas de main.

NO hagas merge a main.
NO hagas push a main.
NO despliegues.
NO accedas a producción.
NO accedas a Noesis19FQA.
NO uses backups reales.
NO destruyas ninguna copia QA real.
NO hagas provider I/O.
NO llames AEAT, Meta, Google, Stripe, email ni almacenamiento externo mutable.

Trabaja inicialmente SOLO en local.

Ejecuta exclusivamente Fase 1.10E.

NO avances a 1.10F–H.

---

# OBJETIVO

Cerrar técnicamente las dos garantías que A mantiene bloqueadas:

PRIVACY_NOT_READY
EXPORT_NOT_READY

mediante:

1. export financiero completo, consistente y verificable;
2. política/contrato de retención explícito;
3. inventario de conservación;
4. cierre de cuenta con conservación;
5. supresión/minimización de datos no retenibles;
6. evidencia durable de export/cierre;
7. continuidad con restore/backups;
8. integración segura con readiness A.

IMPORTANTE:

E NO debe fingir una validación jurídica que no existe.

La infraestructura puede quedar técnicamente PASS aunque una cuenta real siga
bloqueada hasta que exista una política de retención formalmente aprobada.

NO inventes plazos legales.

---

# 1. REUTILIZAR PRIVACIDAD EXISTENTE

NO crear un segundo sistema RGPD paralelo.

El repositorio ya dispone de:

- privacy_requests;
- create_privacy_request;
- update_privacy_request;
- export_business_data;
- export_client_data;
- delete_business_cascade;
- delete_client_cascade;
- record_security_event;
- /api/{business_id}/export;
- /api/{business_id}/clients/{client_id}/export;
- flujo de account_closure;
- auth_guard tenant-scoped.

1.10E debe integrarse con ellos.

No duplicar:

privacy request
→ financial privacy request paralelo.

---

# 2. AUTH/TENANT EXISTENTE

`deps.auth_guard` ya protege:

/b/{business_id}
/api/{business_id}

y comprueba que:

session business_id == URL business_id.

Conservar esta defensa.

Añadir tests explícitos E para:

- no autenticado;
- business ajeno;
- client ajeno;
- export ajeno;
- cierre ajeno.

No rebajar el guard.

Si una función interna de export recibe business_id:

debe seguir aplicando aislamiento por tenant,
no confiar únicamente en que HTTP ya lo hizo.

---

# 3. PROBLEMAS DEL EXPORT ACTUAL A RESOLVER

El export actual NO debe considerarse suficiente para Financial Core porque:

- abre múltiples conexiones mediante helpers;
- no garantiza un snapshot consistente de toda la cuenta;
- algunas colecciones usan límites como 500;
- no contiene toda la evidencia A–D;
- no genera manifest/hash integral;
- no acredita provenance/authority/history/activation;
- no existe contrato financiero versionado.

NO parchear esto añadiendo unas pocas claves a un dict.

Crear un export financiero profesional.

---

# 4. MÓDULO

Crear un módulo especializado, nombre orientativo:

src/noesis/financial_privacy/

con responsabilidades separadas, por ejemplo:

- contracts.py
- export.py
- retention.py
- closure.py
- repository.py
- schema.py

No meter lógica grande en db.py.

db.py puede mantener adaptadores finos para compatibilidad.

Monolito modular.
FinancialSession/conexión prestada.
Tenant explícito.

---

# 5. FINANCIAL EXPORT v1

Crear contrato versionado:

FinancialEvidenceExport v1

Propósitos cerrados como mínimo:

- portability
- audit
- gestoria
- account_closure

No usar texto libre como autoridad.

El export debe ser:

- tenant-scoped;
- completo para su propósito;
- determinista;
- machine-readable;
- verificable;
- sin secretos;
- sin truncamiento silencioso.

---

# 6. SNAPSHOT CONSISTENTE

CRÍTICO.

Un export NO puede mezclar:

tabla A antes de un cobro
+
tabla B después del cobro.

PostgreSQL:

usar una única transacción/snapshot consistente.

Preferencia:

REPEATABLE READ READ ONLY

si encaja con la infraestructura.

No mantener el business writer gate bloqueado durante un export largo
salvo que sea estrictamente necesario y se justifique.

SQLite:

una única transacción de lectura con snapshot coherente.

NO usar:

helper → nueva conexión
helper → nueva conexión
helper → nueva conexión.

Todo Financial Evidence Export usa UNA vista consistente.

---

# 7. ORDEN DETERMINISTA

Cada sección debe tener orden canónico explícito.

Nunca depender del orden natural SQL.

Por ejemplo:

business_id + primary key
o
UUID estable
o
sequence estable.

Mismo snapshot lógico:

mismo contenido/hash.

---

# 8. MONEY

Cero float en Financial Export.

Importes Financial Core:

Decimal/EUR
→ string decimal canónica.

No:

float
Decimal(str(float))
round(float)

Valores legacy binary:

exportarlos como evidencia legacy con su representación/provenance real.

NO convertirlos en exactos.

Unknown sigue unknown.

NULL sigue NULL.

---

# 9. TIMESTAMPS

Formato canónico y explícito.

No mezclar naive/local arbitrariamente.

Conservar timezone/provenance disponible.

No inventar fechas.

---

# 10. SECCIONES MÍNIMAS DEL EXPORT FINANCIERO

Incluir, cuando existan y pertenezcan al tenant:

FUENTES Y DOCUMENTO ECONÓMICO:

- invoices relevantes;
- invoice_lines;
- invoice_records;
- invoice_events fiscales relevantes;
- invoice_cancellation_records;
- invoice_payments;
- bank_transactions;
- received_invoices;
- expenses;
- documentos financieros mediante referencia/metadata segura;
- outboxes fiscales y respuestas necesarias como evidencia.

FINANCIAL OPERATIONS:

- financial_operations;
- financial_authorizations.

ECONOMIC EVENTS:

- economic_events;
- economic_event_links;
- business sequence/provenance necesaria.

COVERAGE:

- invoice_economic_coverage;
- payment_economic_coverage;
- bank_import_coverage;
- bank_match_coverage;
- bank_payment_links;
- supplier_invoice_economic_coverage;
- expense_economic_coverage;
- invoice_fiscal_cancellation_coverage.

HISTORY:

- epochs;
- control;
- cut manifests;
- manifests;
- items;
- incidences;
- decisions;
- import batches/items;
- reconciliations/findings;
- epoch audit.

READINESS A:

- financial_activation_control;
- financial_readiness_evaluations;
- financial_readiness_capabilities.

ANTECEDENTS B:

- financial_antecedent_resolutions.

ACTIVATION D:

- activation requests;
- activation authorizations;
- transitions;
- generations;
- grants;
- revisions;
- effect commits;
- source witnesses;
- handoff identifiers.

Añadir cualquier tabla E necesaria.

No incluir una tabla solo porque exista:
debe responder a provenance/audit/portability.

---

# 11. NO EXPORTAR SECRETOS

PROHIBIDO exportar:

- password_hash;
- password reset tokens;
- OAuth tokens;
- access/refresh tokens;
- WhatsApp provider credentials;
- Stripe secrets;
- provider API keys;
- SECRET_KEY;
- claves de cifrado;
- cookies/sessions;
- raw authentication tokens;
- HMAC signing key;
- financial_execution_verifier_key.verifier;
- credenciales de DB;
- contenido de .env;
- secrets de Railway/GitHub.

Especialmente:

financial_execution_verifier_key

NO forma parte del export de un business.

Es infraestructura criptográfica global.

---

# 12. PII

El Financial Export puede contener PII legítimamente necesaria para el propósito.

Pero:

- no añadir PII que no exista en el dominio;
- no copiar mensajes/chat completos “por si acaso”;
- no copiar logs globales;
- no copiar datos de otros tenants;
- no introducir PII en manifest/hash metadata durable.

La evidencia durable del export debe guardar:

hashes/counts/refs,

NO una segunda copia del contenido personal.

---

# 13. MANIFEST

Cada export debe producir:

manifest v1

con al menos:

- export_uuid;
- business_id;
- purpose;
- contract_version;
- schema_version;
- code_version;
- snapshot identity;
- created_by;
- session_version;
- created_at;
- section names;
- section row counts;
- section content hashes;
- total hash;
- warnings/limitations tipadas;
- canonical version.

El manifest forma parte del archivo exportado.

---

# 14. EVIDENCIA DURABLE DEL EXPORT

Migration78 puede introducir:

financial_export_manifests

o equivalente.

Guardar únicamente:

- identidad;
- actor;
- purpose;
- counts;
- hashes;
- snapshot identity;
- version;
- timestamp;
- final result.

NO almacenar otra copia completa del export.

Final:

inmutable.

No UPDATE/DELETE.

---

# 15. IDEMPOTENCIA DE EXPORT

Una export request UUID debe ser estable.

Misma UUID
+
mismo snapshot/contexto
→ mismo manifest/result.

Misma UUID
+
otro contexto
→ conflict.

Un export nuevo de un estado posterior:

nueva UUID.

No hacer que un export viejo “se actualice”.

---

# 16. EXPORT SIN LIMIT 500

El Financial Export completo no puede truncar silenciosamente:

bank transactions
outboxes
events
operations
etc.

Si hay volumen alto:

paginar internamente,
pero incluir TODO el snapshot.

El manifest debe acreditar:

count total.

Tests con >500 filas.

---

# 17. ACCOUNT EXPORT EXISTENTE

Mantener compatibilidad razonable con:

/api/{business_id}/export

pero incorporar el Financial Core de forma explícita.

Preferencia:

añadir una sección versionada:

financial_core

o equivalente.

No cambiar silenciosamente nombres legacy si rompe consumidores.

Si el export completo necesita arquitectura distinta:

mantener wrapper compatible
→ nuevo exporter.

No duplicar lógica.

---

# 18. CLIENT EXPORT

Revisar:

/api/{business_id}/clients/{client_id}/export

Debe incluir únicamente evidencia realmente relacionada con ese cliente.

Cuando proceda:

- invoices;
- invoice payments;
- relevant Economic Events;
- coverage;
- bank links asociados;
- financial documents asociados.

Nunca incluir:

eventos/facturas de otro cliente
por compartir business.

Tests cross-client.

---

# 19. FORMATO

Preferencia:

JSON canónico + manifest.

Si decides ZIP:

- manifest.json;
- financial.json o secciones NDJSON;
- archivos documentales solo si están explícitamente en alcance.

NO meter rutas internas de filesystem.

NO meter nombres de bucket/URLs firmadas.

No comprimir secretos.

---

# 20. DOCUMENTOS

Para Financial Export v1:

como mínimo exportar metadata/provenance/hash de los documentos financieros.

Si incluyes bytes:

- solo documentos del business;
- solo los incluidos por el contrato;
- nombre seguro;
- no path traversal;
- sin symlinks;
- tamaño acotado;
- hash verificado;
- no upload a tercero.

No es obligatorio incluir bytes si el contrato v1 documenta que son
un artefacto separado y el manifest los referencia de forma íntegra.

No afirmar “export completo de documentos” si no incluye los bytes.

---

# 21. RETENTION POLICY

Crear un contrato cerrado/versionado de retención.

IMPORTANTE:

los documentos existentes contienen plazos orientativos,
pero el procedimiento legal también declara que la tabla exacta
requiere validación profesional.

NO conviertas automáticamente esos números en ley dentro del código.

NO hardcodear plazos nuevos solo para pasar E.

---

# 22. STATUS DE POLÍTICA

La política debe distinguir claramente entre:

- draft/provisional;
- approved_for_operation

o términos equivalentes.

NO sembrar `approved_for_operation`
si no existe una decisión humana/legal real que lo justifique.

Tests pueden utilizar una policy sintética aprobada.

La configuración real/default permanece conservadora.

---

# 23. PLAZOS

Un retention rule puede tener:

- category;
- basis/reference;
- retention mode;
- purge_after rule;
- review status.

Si el plazo no está aprobado:

purge_after = NULL
o equivalente.

Eso significa:

NO auto-purge.

No significa:

“guardar para siempre es legal”.

Significa:

“supresión automática bloqueada hasta validación”.

Documentarlo.

---

# 24. CLASES DE RETENCIÓN

Definir catálogo cerrado.

Como mínimo cubrir conceptualmente:

- fiscal/legal financial record;
- financial audit/provenance evidence;
- activation/authorization evidence;
- fiscal transport evidence;
- accounting/supporting document;
- operational personal data;
- credentials/secrets;
- communications/support data;
- privacy request evidence;
- QA/restored-copy evidence.

Ajustar nombres al dominio real.

No usar una única clase:

retain=true.

---

# 25. FINANCIAL RETENTION INVENTORY

Crear inventario durable por business.

Debe responder:

- qué existe;
- qué categoría tiene;
- por qué se retiene;
- qué puede borrarse;
- qué está bajo legal hold;
- qué política/version se aplicó;
- qué no tiene todavía fecha de purga aprobada.

Preferencia:

counts/hashes/rangos/refs.

No duplicar todas las filas económicas dentro del inventario.

---

# 26. INTEGRIDAD

El retention inventory debe usar:

- table/section;
- count;
- source hash;
- rule;
- classification;
- policy version;
- evidence hash.

Si los datos cambian:

inventario stale.

No editar el inventario viejo.

Crear otro.

---

# 27. PRIVACY REQUESTS

Reutilizar:

privacy_requests.

Financial closure debe referenciar una solicitud existente:

request_type = account_closure

o el tipo exacto existente que corresponda.

No crear un segundo ticket.

La solicitud administrativa:

NO borra datos por sí misma.

Se mantiene la regla actual.

---

# 28. CLOSURE PLAN

Crear:

FinancialClosurePlan

o equivalente.

Primero:

PLAN / DRY RUN.

Debe congelar:

- business;
- privacy_request_id;
- policy version;
- retention inventory;
- retained sections;
- deletable/minimizable sections;
- credential actions;
- document/file actions;
- counts;
- hashes;
- current activation state;
- generation;
- pending operations;
- pending/uncertain dispatch;
- plan hash.

Sin side effects.

---

# 29. AUTORIDAD DE CIERRE

No usar IA.

No utilizar:

financial.authorize
historical_unknown
mandate

como autoridad suficiente.

Usar autoridad humana exacta del titular/control plane de privacidad.

Debe estar vinculada a:

plan hash
+
business
+
sesión actual.

La contraseña/flujo existente puede seguir siendo requisito de la UI,
pero el servicio interno debe tener su propio recibo durable exacto.

---

# 30. BUSINESS EVER_ENABLED

Si:

ever_enabled=true

antes de aplicar un cierre con conservación:

state debe ser:

paused.

NO cerrar mientras:

enabled.

NO llamar automáticamente a D.pause escondido dentro de E.

Son autoridades distintas.

El operador/titular debe ejecutar el flujo de pausa correspondiente.

---

# 31. PENDING OPERATIONS

Antes de cierre:

cero operaciones financieras PREPARED/APPROVED ejecutables.

D pause ya las cancela/revoca.

Revalidar.

No cerrar dejando autoridad viva.

---

# 32. UNCERTAIN DISPATCH

Si existe:

dispatch externo incierto

NO fingir que el cierre lo resuelve.

Conservar evidencia y marcar blocker/hold.

F resolverá política completa de providers.

E:

no borra el outbox
no repite envío
no interpreta timeout como éxito.

---

# 33. CIERRE CON CONSERVACIÓN

Al aplicar un plan APROBADO:

NO borrar:

- Economic Events;
- Operations/Auth requeridas;
- financial coverage;
- history certificada;
- A/B/C/D evidence;
- fiscal records;
- required invoice/payment/bank/source evidence;
- retention/export/closure receipts.

Preservar FK/provenance.

No romper B historical.

No romper activation receipts.

No romper record hashes.

---

# 34. DATOS NO RETENIBLES

Solo purgar/minimizar automáticamente cuando:

- el plan los clasifica explícitamente;
- la policy aplicable lo permite;
- no existe FK/proof legal que lo requiera;
- tests demuestran el resultado.

No usar:

DELETE FROM <muchas tablas>

sin contrato.

---

# 35. CREDENCIALES

Un cierre definitivo debe dejar de poder utilizar:

- OAuth credentials;
- sesiones activas;
- provider tokens locales;
- portal tokens;
- reset tokens;
- support grants activos;
- otros secretos tenant-scoped.

Pero:

NO hacer provider I/O en E.

Si revocar remotamente requiere Google/Meta/etc:

crear finding/action pendiente para F
o documentar la limitación.

Sí eliminar/inutilizar la credencial LOCAL de acuerdo con el plan seguro.

---

# 36. USER IDs REFERENCIADOS

Financial evidence referencia usuarios por ID.

NO borrar un user row si rompe:

- authorization;
- historical provenance;
- activation receipt;
- privacy request.

Preferencia:

preservar identidad técnica mínima
+
desactivar acceso
+
minimizar campos personales que no deban conservarse.

No inventar la estrategia.

Auditar FKs primero.

---

# 37. BUSINESS ROW

No borrar el business si existe evidencia financiera durable.

Mantener la identidad técnica necesaria.

Minimizar únicamente campos personales/comerciales que el contrato permita.

Nunca modificar datos que formen parte de hashes/proofs
sin reconocer explícitamente que el proof se volvería inválido.

---

# 38. NO ROMPER HASHES

CRÍTICO.

No “anonimizar” cambiando in-place:

- canonical events;
- historical raw evidence;
- operations;
- authorizations;
- signed/canonical fiscal records;
- activation receipts;
- export manifests;
- hashes.

Si una obligación requiere conservarlos:

se conservan íntegros y bloqueados.

La minimización ocurre alrededor de la evidencia,
no reescribiendo historia firmada.

---

# 39. CLOSURE STATE

Crear evidencia durable del cierre.

Nombre orientativo:

financial_closure_receipts

Debe contener:

- closure UUID;
- business;
- privacy request;
- plan;
- retention inventory;
- policy;
- actor/session;
- previous activation state/G;
- final restricted state;
- retained counts/hash;
- deleted/minimized counts/hash;
- pending external actions;
- recorded_at;
- canonical/content hash.

No PII libre.

---

# 40. BLOQUEAR REACTIVACIÓN

Una cuenta con closure final aplicada:

NO puede:

- activation enable;
- activation resume;
- nuevo historical epoch;
- nueva readiness para activarse;
- nuevos Financial Operations;
- nuevo provider dispatch iniciado por el negocio.

Debe permanecer:

consulta/export/privacidad/auditoría

según contrato.

Integrar con D de forma aditiva.

No editar receipts D anteriores.

---

# 41. ACCOUNT CLOSURE PENDING

Cuando exista un cierre formal autorizado/aplicándose:

fail closed para nueva activación.

No hace falta bloquear una mera consulta RGPD.

Distinguir:

privacy request received

de

closure técnicamente autorizado/aplicado.

No convertir cualquier solicitud de acceso/portabilidad en shutdown.

---

# 42. BACKUPS Y RESTORE

La política existente dice que una supresión restaurada desde backup
debe reaplicarse.

E debe convertirlo en una garantía técnica verificable.

Crear mecanismo de:

deletion/closure tombstone
o
restore replay evidence

sin guardar el dato borrado.

Después de restore:

el sistema puede identificar que un closure/suppression ya se había ejecutado
y debe reaplicarse antes de devolver servicio.

No ejecutar un restore real en E.

Solo fixtures.

---

# 43. TOMBSTONES

Una tombstone NO contiene el dato eliminado.

Como máximo:

- business;
- closure/suppression UUID;
- scope/category;
- policy;
- canonical selector/version;
- evidence hash;
- applied_at.

No copiar:

nombre
email
teléfono
NIF
mensaje
document content

dentro del tombstone.

---

# 44. FILESYSTEM

Si closure elimina documentos/archivos locales:

DB y filesystem no pueden quedar incoherentes.

Preferencia:

1. marcar durablemente deletion intent dentro de TX;
2. commit;
3. borrar archivo;
4. registrar completion sin contenido personal.

Retry idempotente.

Si falla filesystem:

queda trabajo pendiente visible,
no se afirma supresión completa.

No eliminar archivo ANTES de saber que la DB commitió.

---

# 45. QA / RESTORE REAL DE 1.9F

NO acceder a:

Noesis19FQA
dump real
snapshots reales
C:/Users/.../NoesisPrivate

E solo crea/documenta la política.

El plazo “30 días” del diseño es OPERATIVO PROPUESTO,
NO una ley.

No hardcodearlo como obligación legal.

Diseñar:

- owner;
- custodian;
- access;
- encryption;
- created_at;
- approved retention until;
- extension;
- destruction authorization;
- destruction evidence.

No destruir nada durante E.

---

# 46. EXPORT Y BACKUPS

No guardar exports con PII dentro de:

- Git;
- CI artifacts públicos;
- docs;
- logs;
- fixtures reales.

Tests:

datos sintéticos únicamente.

Si CI genera un export:

temporal,
sintético,
eliminado al terminar.

---

# 47. READINESS A — EXPORT

Modificar A únicamente de forma compatible.

Para evaluaciones NUEVAS:

EXPORT_NOT_READY puede desaparecer SOLO si:

- schema/contract E disponible;
- exporter v1 validado;
- manifest contract vigente;
- tenant exportable;
- no blocker estructural E.

NO modificar evaluaciones A ya finalizadas.

NO reescribir sus hashes.

---

# 48. READINESS A — PRIVACY

PRIVACY_NOT_READY puede desaparecer SOLO si:

- retention contract E está instalado;
- business no está closing/closed;
- existe policy aplicable;
- policy tiene el estado requerido para activación real;
- closure-with-retention está técnicamente soportado.

IMPORTANTE:

si la política real sigue:

provisional / pending legal review

NO falsear FULL.

Mantener:

PRIVACY_NOT_READY

para cuentas reales.

Tests pueden usar una policy SINTÉTICA approved_for_operation.

---

# 49. NO HACER FULL ARTIFICIAL

Aunque E quite:

EXPORT_NOT_READY

y eventualmente:

PRIVACY_NOT_READY,

pueden seguir bloqueando:

- provider preflight F;
- bank evidence;
- continuity limitations;
- historical invoice limitations;
- volume;
- cualquier blocker real.

No tocar esos reasons.

---

# 50. EXISTING POLICY DOCS

Preservar la distinción documental:

- política operativa existente;
- validación legal profesional pendiente.

No reescribir la documentación diciendo:

“cumplimos todos los plazos legales”

si no está acreditado.

No presentar este software como asesoramiento jurídico.

---

# 51. MIGRACIÓN 78

Nueva migration:

78

salvo blocker técnico fuerte documentado.

Aditiva siempre que sea posible.

No modificar migrations 63–77.

Tablas orientativas mínimas:

- financial_export_manifests;
- financial_retention_policies o policy evidence;
- financial_retention_inventories;
- financial_closure_plans;
- financial_closure_receipts;
- privacy deletion/restore tombstones si son necesarias.

NO crees todas si una arquitectura más simple demuestra las mismas invariantes.

Justificar cada tabla.

---

# 52. INMUTABILIDAD

Final:

export manifest
retention inventory
closure plan autorizado
closure receipt
tombstone aplicada

deben ser append-only/inmutables.

No DELETE/UPDATE arbitrario.

Corrección:

nuevo objeto/version.

---

# 53. SQL GUARDS

PostgreSQL + SQLite.

Probar:

- cross tenant;
- forged export manifest;
- forged policy approval;
- closure receipt sin plan/auth;
- retention inventory mutado;
- deletion tombstone mutada;
- business cerrado intentando resume;
- business cerrado intentando operación;
- eliminación directa de financial evidence;
- downgrade destructivo.

---

# 54. POLICY APPROVAL

Si introduces aprobación de policy:

NO puede ser:

UPDATE policy SET approved=1

sin autoridad.

Requiere control-plane humano y evidencia durable,
o una policy code-owned cuya aprobación esté documentada externamente.

No IA.

No auto-aprobación de migration.

Para E local:

fixtures sintéticas pueden crear policy approved.

Configuración real:

NO se modifica.

---

# 55. EXPORT SECURITY

El endpoint/download debe enviar:

Cache-Control: no-store

y Content-Disposition attachment.

No poner contenido exportado en:

error logs
request logs
security event metadata.

El security event puede guardar:

export_uuid
business_id
purpose
result

pero no contenido.

---

# 56. PERFORMANCE

No convertir E en un lock de minutos.

Medir como mínimo:

- 64 items histórico;
- >500 bank/outbox rows;
- varios cientos/miles de EE sintéticos.

Registrar:

- tiempo;
- memoria;
- tamaño.

No inventar SLO productivo.

Si el export puede ser grande:

usar paginación/streaming interno determinista.

---

# 57. CONCURRENCIA

PostgreSQL obligatoria:

- export vs payment;
- export vs invoice;
- export vs pause;
- export vs closure;
- dos exports misma UUID;
- dos closure plans;
- closure vs write;
- closure vs resume;
- closure vs privacy request duplicate;
- otro business progresa.

Export debe ver:

ANTES completo

o

DESPUÉS completo.

Nunca mitad y mitad.

---

# 58. CLOSURE CRASHES

Probar crash:

- antes del plan;
- después del inventory;
- después de authorization;
- durante minimización DB;
- antes del commit;
- después del commit;
- antes de filesystem cleanup;
- durante filesystem cleanup;
- después del cleanup.

Precommit:

rollback.

Postcommit:

retry exacto.

Nunca:

“deleted” sin evidencia durable.

---

# 59. CLIENT ERASURE

Revalidar delete_client_cascade.

Financial Core puede añadir referencias nuevas.

Debe seguir:

- borrando/minimizando lo prescindible;
- conservando factura/evidencia exigida;
- sin romper EE/coverage/provenance;
- sin borrar pagos/evidencia financiera que deban conservarse;
- sin tocar otro cliente.

Añadir tests E.

---

# 60. BUSINESS DELETE

delete_business_cascade ya bloquea con evidencia Financial Core.

Mantener fail closed.

Después de E:

si existe financial evidence:

no ejecutar cascade destructivo.

Usar:

privacy_request
→ retention inventory
→ closure plan
→ closure-with-preservation.

Solo business realmente vacío/sin evidencia protegida puede conservar
el borrado físico legacy.

---

# 61. FIVE FLAGS

Mantener OFF:

FINANCIAL_CORE_ENABLED
LEDGER_REPORTING_ENABLED
OPEN_ITEMS_ENABLED
NEW_TAX_ENGINE_ENABLED
NEW_BANK_RECONCILIATION_ENABLED

E no los cambia.

---

# 62. D NO SE DESHACE

No modificar la semántica de:

- handoff;
- handed_off;
- generation;
- grants;
- execution context;
- SQL live guards;
- pause/recovery.

Solo añadir el blocker de closure/privacy necesario.

D receipts existentes siguen byte-identical.

---

# 63. NO PROVIDERS

No:

AEAT
Meta
Gmail
Brevo
Stripe mutable
OAuth revoke remoto
cloud storage upload
webhook externo

en E.

F se encargará de providers/preflight.

---

# 64. SIDE-EFFECT PROOF

EXPORT:

solo puede persistir metadata/manifest E.

No cambia fuentes.

RETENTION INVENTORY:

solo evidencia E.

CLOSURE PLAN:

solo control-plane E.

CLOSURE APPLY sintético autorizado:

solo los deletes/minimizaciones EXPLÍCITOS del plan
+
revocación/inutilización local permitida
+
closure receipts/tombstones.

Nunca:

- borrar Financial Core evidence;
- crear EE;
- crear Financial Operation económica;
- cambiar hashes históricos;
- cambiar D grants/receipts;
- hacer provider I/O.

---

# 65. TESTS DE SECRETOS EN EXPORT

Construir fixture con:

- password hash;
- OAuth token;
- fake provider token;
- verifier key;
- reset token;
- session-like secret.

Export:

NINGUNO aparece.

Ni en:

JSON
manifest
hash metadata legible
filename
logs.

---

# 66. TEST >500

Crear:

>500 bank transactions
y/o
>500 outbox rows

según el contrato.

Export count:

completo.

Nada truncado a 500.

---

# 67. TEST SNAPSHOT

Con dos conexiones PostgreSQL:

TX export empieza
→ writer intenta/commitea cambio
→ export termina.

Resultado debe corresponder íntegramente a un único snapshot.

No mezclar row count antiguo con hash nuevo.

---

# 68. TEST HISTORY + D

Fixture:

history
→ import
→ E PASS
→ B
→ D handed_off
→ Financial Export.

Debe contener:

- proof histórica;
- reconciliation;
- antecedent;
- activation generation/grants;
- handoff;
- EE,

sin romper hashes.

---

# 69. TEST CLOSURE POST-D

Fixture sintético:

business enabled
→ pause D
→ privacy account_closure
→ approved synthetic retention policy
→ retention inventory
→ export closure
→ closure plan
→ human closure auth
→ apply.

Verificar:

- no resume;
- no Financial Operations nuevas;
- no legacy fallback;
- evidence A–D intacta;
- export posterior posible;
- secrets/local credentials inutilizados según plan;
- retained rows intactas.

---

# 70. TEST POLICY NO APROBADA

Real/default policy:

pending/provisional.

Readiness nueva:

PRIVACY_NOT_READY

permanece.

NO activar.

Test explícito obligatorio.

---

# 71. TEST POLICY SINTÉTICA APROBADA

Fixture únicamente:

approved_for_operation.

Readiness:

puede eliminar PRIVACY_NOT_READY/EXPORT_NOT_READY

si los demás requisitos E están satisfechos.

Pero:

otros blockers F/bank/history/etc

siguen presentes.

No forzar FULL.

---

# 72. DOWNGRADE

78→77:

solo si tablas/evidence E están vacías.

Si existe:

- export manifest;
- retention inventory;
- policy approval;
- closure plan/receipt;
- tombstone;

bloquear downgrade destructivo.

Nunca borrar evidencia para poder bajar.

---

# 73. COMPATIBILITY MATRICES

Actualizar explícitamente:

A
B
C
D
history

a schema78 solo cuando corresponda.

NO usar >=78.

Preservar contract/version semantics previas.

---

# 74. CI

Añadir E a PostgreSQL CI.

Ejecutar:

- E SQLite;
- E PostgreSQL;
- concurrency;
- crash tests;
- migration78;
- A readiness;
- B antecedents;
- C fiscal cancellation;
- D handoff;
- history A–E;
- Operations/Auth;
- Economic Events;
- captures;
- channels;
- account deletion/privacy;
- backups/restore;
- suite general completa;
- JavaScript;
- HTTP smoke.

---

# 75. GATES

- Ruff;
- Bandit;
- credential scan;
- dependency audit;
- AST migrations previas;
- documentation truth;
- links;
- no raw secret in fixtures;
- no PII real.

---

# 76. DOCUMENTACIÓN

Crear:

- ADR siguiente disponible;
- FINANCIAL-PRIVACY-EXPORT-RETENTION-v1.md;
- FASE-1.10E-orden.md;
- FASE-1.10E-cierre.md.

Actualizar:

- FASE-1.10-plan;
- Arquitectura;
- Decisiones;
- Estado;
- Mapa;
- Registro QA;
- Registro cambios;
- tareas;
- área RGPD;
- área Financial Core;
- project-state.

NO declarar:

“legalmente validado”

si no lo está.

---

# 77. QA COPY POLICY

Documentar específicamente que la copia real 1.9F:

NO se toca en E.

Crear runbook para:

- inventario;
- owner;
- custodian;
- acceso;
- cifrado;
- deadline operativo;
- extensión aprobada;
- destrucción;
- evidence of destruction.

No ejecutar destrucción.

---

# 78. ENTREGA LOCAL PRIMERO

Al terminar:

NO PUSH.

Devuélveme:

- rama;
- commit local;
- padre exacto;
- migration78;
- archivos;
- export contract;
- snapshot model;
- manifest;
- secciones;
- secret exclusions;
- retention contract;
- policy status model;
- inventory;
- privacy_request integration;
- closure plan/auth/receipt;
- deletion/restore tombstone;
- D integration;
- account export integration;
- client export/erasure;
- business closure;
- side-effect proof;
- concurrency;
- crash tests;
- SQLite;
- PostgreSQL;
- suite;
- performance;
- riesgos;
- limitaciones;
- autoauditoría.

---

# 79. AUTOAUDITORÍA

Responder explícitamente:

1. ¿Puede E activar un business?
2. ¿Puede E hacer handoff?
3. ¿Puede E cambiar generation/grants D?
4. ¿Puede E cambiar los cinco flags?
5. ¿Puede E hacer provider I/O?
6. ¿Puede un export leer otro tenant?
7. ¿Puede un client export incluir otro cliente?
8. ¿Puede el export truncar silenciosamente a 500?
9. ¿Puede el export mezclar dos snapshots?
10. ¿Puede el export contener passwords/tokens/keys?
11. ¿Puede exportarse financial_execution_verifier_key?
12. ¿Puede una evaluación A vieja modificarse?
13. ¿Puede PRIVACY_NOT_READY desaparecer con policy provisional?
14. ¿Puede una migration autoaprobar política legal?
15. ¿Puede E inventar un plazo legal?
16. ¿Puede closure borrar EE?
17. ¿Puede closure borrar Operations/Auth requeridas?
18. ¿Puede closure borrar history A–E?
19. ¿Puede closure borrar A/B/C/D evidence?
20. ¿Puede closure reescribir hashes para “anonimizar”?
21. ¿Puede closure ejecutarse enabled sin pause?
22. ¿Puede closure dejar PREPARED/APPROVED ejecutables?
23. ¿Puede una cuenta cerrada hacer resume?
24. ¿Puede una cuenta cerrada volver a legacy?
25. ¿Puede una tombstone contener PII borrada?
26. ¿Puede filesystem borrarse antes del commit DB?
27. ¿Puede un restore ignorar una supresión ya aplicada?
28. ¿Puede un downgrade borrar evidencia E?
29. ¿Puede E destruir Noesis19FQA o el backup real?
30. ¿Se inició 1.10F?

Todas las respuestas peligrosas deben ser:

NO.

---

# CRITERIOS DE CIERRE

1.10E solo puede cerrar PASS técnico si:

- export financiero es completo, consistente y verificable;
- no hay límites silenciosos;
- no exporta secretos;
- A–D/history quedan exportables con provenance;
- retention inventory es durable;
- no se inventan plazos;
- policy provisional NO habilita real activation;
- closure conserva Financial Core evidence;
- cierre post-D requiere pause;
- closed bloquea resume/nuevos efectos;
- restore puede reaplicar supresiones;
- filesystem/DB no quedan incoherentes;
- cross-tenant está probado;
- todos los gates pasan.

Es aceptable terminar:

1.10E CODE-VERIFIED PASS TÉCNICO —
POLÍTICA LEGAL REAL PENDIENTE PARA ACTIVACIÓN

si la infraestructura está completa pero no existe aún aprobación profesional
de los plazos/policy reales.

Eso NO es un FAIL técnico.

Sí significa:

NINGÚN PILOTO REAL PUEDE USAR ESA POLICY COMO APROBADA.

Si para pasar tests necesitas:

- autoaprobar la política;
- inventar plazos;
- borrar evidencia;
- relajar tenant isolation;
- fingir supresión completa;
- acceder a datos reales;

DETENTE y devuelve:

1.10E BLOCKED — <motivo concreto>

NO avanzar a 1.10F.