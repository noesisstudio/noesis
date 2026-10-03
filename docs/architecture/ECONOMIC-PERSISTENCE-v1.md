# Economic Events: persistencia v1, exclusivamente Fase 1.3

## Adenda 1.9A — persistencia histórica aún pendiente

Sin tablas/DDL nuevo ni incorporación de datos. Wrapper v2 especial es puro y no
pasa EconomicEvent durable/schema69. EE impide autoridad live desde operación
historical o receipt historical_unknown previo. SQL directo aún puede introducir
metadatos inconsistentes; los guards de aplicación los rechazan, sin prometer un
constraint nuevo. [ADR-014](ADR-014-financial-history-contracts.md), [contrato](FINANCIAL-HISTORY-v1.md).

## Adenda vigente 1.8H

[ADR-013](ADR-013-financial-hardening.md) corrige los defects auditados sin
ampliar funcionalidades: business gate precede operation/source incluso en
prepare/reprepare y lecturas FOR UPDATE; DELETE permitido devuelve OLD en PG,
con reparación de instalaciones existentes; el bridge resuelve procedencia
recurrente con sesión prestada para todos los canales y una identidad económica.
Consulta COMMITTED exige creador/negocio/sesión actual, no sv histórico;
PREPARED/APPROVED y aprobación/ejecución conservan la autoridad original.
Sin reescritura de evidencia. Flags OFF; no 1.9. Las descripciones inferiores
con orden anterior de locks se conservan como contexto histórico, supersedido
por esta adenda y su [validación](FASE-1.8H-cierre.md).

## Conexión vigente de Fase 1.8

Los contratos de esta entrega permanecen vigentes. Los cinco Capture se invocan
ahora desde bridges autenticados, detrás del gate apagado del Core. La autoridad
sigue en FinancialOperations; la IA prepara, nunca aprueba. No cambian catálogo,
payloads, fiscalidad ni writers. [ADR-012](ADR-012-financial-channels.md) y
[contrato de canales](FINANCIAL-CHANNELS-v1.md). Los límites de no conexión en el
cierre original describen aquella entrega histórica, no esta fase autorizada.


Nota vigente1.7: cinco productores de recibidas/gastos v1 con cobertura por
revisión, continuidad, void lógico y guards. Catálogo/canonicalización intactos.
[ADR-011](ADR-011-purchasing-capture.md), [API](PURCHASING-CAPTURE-v1.md).
Flags OFF, no1.8. Las notas inferiores reflejan entregas anteriores.

Nota vigente 1.6: se añaden PaymentCapture/BankCapture sobre el writer existente,
con autorización durable, cobertura específica y resultado en un commit.
customer_payment.received v1 = cobro real; bank_transaction.imported v1 = evidencia;
bank_transaction.matched v1 = Evidence-only, nunca segunda caja. No cambia
canonicalización ni catálogo. [ADR-010](ADR-010-payment-bank-capture.md) y
[API](PAYMENT-BANK-CAPTURE-v1.md). Cursor exacto del writer conserva Decimal;
link bank→payment durable. Canales1.8 pendientes, flags OFF; no avanzar1.7.
Las notas inferiores describen el alcance histórico de cada entrega.

Nota de continuidad 1.5: primer productor real de emisión/rectificativa autorizado.
v1 conserva bytes/hash. Solo estos dos hechos incorporan payloadv2 y cobertura65.
Leer [ADR-009](ADR-009-invoice-capture.md) y [API](INVOICE-CAPTURE-v1.md).
El resto de límites de las entregas anteriores se interpreta históricamente.

Contrato puro: [ECONOMIC-EVENTS-v1](ECONOMIC-EVENTS-v1.md), sin cambios de bytes/hash.
Decisión: [ADR-007](ADR-007-economic-persistence.md). Migración 63 sobre main 62.
Solo tests llaman a esta capa. No productores, efectos financieros, hooks, nuevas
rutas, backfill, GL, posting, accounting_date ni activación. 1.4 no autorizada.

## Schema final

economic_events conserva:

| Campos | Representación / significado |
|---|---|
| id | PK técnica BIGSERIAL PostgreSQL / INTEGER SQLite; puede tener huecos |
| business_id, event_uuid, business_sequence | Tenant obligatorio, UUID estable del contrato y orden durable por negocio |
| event_type, payload_version | Once tipos del catálogo; versión 1 |
| operation_uuid, event_slot, idempotency_key | Operación durable, slot estable de servidor y SHA-256 derivado |
| source_type, source_id, source_revision | Origen cerrado y revisión entera positiva corroborada |
| invoice_id, invoice_payment_id, received_invoice_id, expense_id, bank_transaction_id, invoice_cancellation_record_id | Exactamente una FK concreta, mismo tenant e ID que source_id |
| occurred_at, observed_at | Instante conocido opcional y observación obligatoria, ambos con zona |
| economic_date, date_precision, date_provenance | Fecha del payload, instant/day/unknown y procedencia explícita |
| currency, amount | EUR; NUMERIC exacto PostgreSQL / TEXT canónico SQLite, nullable según tipo |
| authorization_uuid | FK a autorización de esa operación y negocio |
| origin, historical_batch_uuid, provenance | live/historical, batch histórico obligatorio, procedencia explícita |
| canonical_version, payload_canonical, canonical_event, content_hash | Versión 1, JSON string decimal y sobre completo v1/hash de 1.1 |
| record_hash, recorded_at | Huella de metadatos durables v1 y instante UTC de incorporación |

PostgreSQL usa UUID, BIGINT, DATE y TIMESTAMPTZ nativos. SQLite usa INTEGER/TEXT;
las fechas canónicas y UUID se validan antes de persistir. No REAL ni floats.
NUMERIC no tiene typmod: CHECK rechaza fuera de rango monetario o fracción de
céntimo sin redondearla. Canonicalización monetaria cierra a dos decimales conforme
al contrato de 1.1; entrada con fracción de céntimo se rechaza, no se aproxima.

economic_event_links: business_id, event_uuid, target_event_uuid, relation_type,
recorded_at. PK (business_id,event_uuid,relation_type); un link de cada clase
permitida por contrato. Ambos extremos del mismo negocio. Source FK diferida,
target FK inmediata; al commit ambos existen. No self-link ni UPDATE/DELETE.

economic_event_sequences: business_id PK/FK y last_sequence BIGINT/INTEGER.
Inicio en cero; actualización exactamente +1 sin cambiar negocio. Referenciada
por los eventos, para impedir borrado/reset de un contador con historia.

## Orígenes e importe

| Tipo v1 | Tabla real / source_type | amount | Fecha | Links obligatorios |
|---|---|---|---|---|
| invoice.issued | invoices / invoice | total | issued_on | — |
| invoice.rectified | invoices / invoice | total rectificativa firmado | issued_on | rectifies |
| customer_payment.received | invoice_payments / invoice_payment | amount del cobro | received_on | settles |
| supplier_invoice.confirmed | received_invoices / received_invoice | total | issued_on | — |
| supplier_invoice.corrected | received_invoices / received_invoice | after.total, no delta | corrected_on | corrects |
| supplier_invoice.voided | received_invoices / received_invoice | before.total, no pago/reversión nueva | voided_on | voids |
| expense.confirmed | expenses / expense | total | spent_on | — |
| expense.voided | expenses / expense | before.total | voided_on | voids |
| bank_transaction.imported | bank_transactions / bank_transaction | amount firmado | booked_on | — |
| bank_transaction.matched | bank_transactions / bank_transaction | amount de evidencia, no segundo cobro | matched_on | matches + evidence_for |
| invoice.fiscal_cancellation_registered | invoice_cancellation_records / invoice_cancellation_record | NULL desconocido, nunca cero | registered_on | evidence_for |

La semántica completa de payload/campos/impacto declarativo sigue en el contrato
v1. No se ejecuta ningún impacto. Se mantiene settles, aprobado en 1.1 aunque la
lista de ejemplos de 1.3 no lo repita. Tipos operativos o supplier_payment.made
no entran en el catálogo. Correcciones/voids exigen mismo origen y revisión mayor.
Rectifies, matches, evidence_for y settles tienen los targets de 1.1. Se corroboran
también invoice_id del pago/anulación y el cobro/importación enlazados por matches.
El guard rechaza links incompatibles con catálogo/JSON; CTE acotada a relaciones
correctivas rechaza ciclos. La tabla no es un motor de grafos.

## API interna y autoridad

```python
service = EconomicEvents(FinancialSession(conn), business_id)
stored = service.append(
    principal, event,
    operation_uuid=operation_uuid, event_slot="primary",
    revision_reader=trusted_source_revision,
    origin="live", provenance="server", date_provenance="source",
    expected_hash=event.content_hash,
)
same = service.read(principal, event.event_id)
```

Esto no es una integración ni endpoint. El llamador abre la transacción antes del
ejemplo y posee commit/rollback. SQLite exige BEGIN IMMEDIATE (o transacción
exterior ya abierta); RELEASE de SAVEPOINT nunca se usa como commit exterior.
FinancialSession conserva acceso exacto en la conexión del pool existente.

principal, event_uuid, business_id, slots y lectores son datos/código confiables
de servidor; no parámetros decididos por IA. Se reutiliza el control de permisos
de 1.2: negocio activo, usuario, sesión vigente, creador de operación y capacidad
de escritura/suscripción. Lecturas vinculadas a operación exigen su creador actual.
El repositorio no decide permisos. No hay herramientas IA ni imports de productores.

Live exige operación approved/committed compatible con event_type, autorización
human_confirmation/mandate del mismo negocio/operación/actor/sesión y request
aprobado; el mandato se revalida con caducidad/revocación y request exacto de 1.2.
Las FKs y guard verifican vínculo durable, no permiten reemplazarlo desde payload.
Una operación bank_transaction.match admite dos hechos en distintos slots,
customer_payment.received y bank_transaction.matched, sin producir ninguno aquí.

Historical exige batch UUID y procedencia explícita. Puede no tener operación ni
autorización. Si aporta operación, exige receipt historical_unknown de 1.2, sin
actor/aprobación histórica inventados. Esto solo prepara metadata: no existe
backfill, lectura de históricos reales ni reenvío/recalculo fiscal.

La fuente se comprueba por tabla real/tenant/ID, sin leer importes legacy. La revisión
debe ser corroborada por revision_reader(session, SourceType, source_id); requiere
int exacto y coincidente. Ninguna revisión desconocida, bool o stale se acepta.
No se ha inventado un campo universal legacy. Los loaders, proyección autorizada
del comando a snapshot, reglas de dominio y orden de locks con escritores reales
se diseñarán exclusivamente en fases posteriores autorizadas.

Resultado StoredEvent congelado: id, business_sequence, event completo y todos
los metadatos/hash durables. Replay devuelve el mismo registro sin nueva secuencia.
Las excepciones diferencian validación, AccessDenied, StateError y ConflictError.
No status durable de evento, posted/reversed/failed ni accounting_date.

## Idempotencia y secuencia

UNIQUEs: (business_id,event_uuid), event_uuid global, (business_id,business_sequence),
(business_id,operation_uuid,event_slot), (business_id,idempotency_key) y
(business_id,source_type,source_id,source_revision,event_type). event_type permite
imported y matched de un movimiento sin confundirlos.

Con operación, key = SHA-256 del JSON [operation_uuid,event_slot]; sin operación
histórica: [source_type,source_id,source_revision,event_type,event_slot]. La key
está acotada por business_id. No usar hash de payload como identidad de intención.

Orden de incorporación: permiso → lock de operación si existe → lock de contador
por negocio → buscar cualquier identidad existente → validar source/revisión/links
→ UPDATE counter +1 RETURNING → preinsertar links → insertar evento. PostgreSQL
INSERT ON CONFLICT + SELECT FOR UPDATE serializa incluso creación del contador.
SQLite usa el lock de escritura de la transacción existente. Nunca SELECT MAX+1.
Negocios distintos tienen secuencias independientes. Se prueba concurrencia real.

Mismo evento/metadata recupera UUID, secuencia, hash y recorded_at originales.
Misma identidad/slot/revisión con contenido relevante distinto da conflicto.
El sobre de 1.1 incluye event_uuid y observed_at: un retry debe conservarlos;
generar otro UUID/observación no es replay válido. No se reparan identidades.
Se revalidan permisos/autorización, sin exigir que la revisión histórica del source
siga siendo actual para recuperar un hecho ya incorporado.

## Inmutabilidad, hashes y atomicidad

Triggers BEFORE UPDATE/DELETE de events/links en los dos motores rechazan toda
mutación. Links forman parte del conjunto canónico, preinsertado antes del evento
en la misma transacción; source FK diferida evita huérfanos al commit. El guard
AFTER INSERT del evento exige todos los links y sus tipos/contenido. Una vez existe
el evento, insertar un nuevo link también se rechaza. No hay API update/delete.

El content_hash aprobado de 1.1 sigue SHA-256 del sobre canónico. record_hash v1
incluye content_hash, operation/slot/auth, origin/batch/provenance, precisión y
procedencia de fecha, key, secuencia y recorded_at UTC. No incluye la PK técnica.
Al leer se reconstruye el contrato, se exigen bytes y payload canónicos, hashes,
columnas estructurales/importe/fechas y conjunto real de links coincidentes.
No hay reparación automática. SQL protege invariantes estructurales; el servicio
valida contrato completo y hashes. Un escritor SQL fuera del API no es un productor
autorizado. Hash no equivale a firma, cifrado ni evidencia contra superusuario.

SAVEPOINT interno revierte contador, links y evento si falla cualquier paso,
aunque el llamador capture el error y confirme otra acción. Un fallo exterior
revierte también el append ya devuelto. El repositorio no gestiona transacciones.
La PK técnica PostgreSQL puede tener huecos por BIGSERIAL; business_sequence no
se consume al fallar/replay porque su fila participa en la misma transacción.

## Migración, rollback y continuidad

63 crea tres tablas, siete índices UNIQUE auxiliares en sources/autorizaciones,
índices propios y guards. No actualiza datos ni llama productores. Probada limpia
y 62→63 en SQLite/PostgreSQL. Con estructura vacía: 63→62→63; SQLite también
0→63→0→63. Con cualquier evento/link: downgrade bloqueado antes de DROP.
Si no hay eventos pero 62 tiene evidencia durable, bajar a 61 tampoco puede dejar
63 parcialmente retirada: la transacción exterior restaura DDL/schema version.

delete_business_cascade elimina la infraestructura solo vacía; con evidencia de
operación/evento bloquea la baja antes de modificar fuentes. Exportación/cierre
conservando datos y retención son gates previos a productores/activación. No
presentarlos como resueltos. No cambiar flags, pagos, facturas, AEAT ni hashes fiscales.

Tests y PASS/FAIL detallados: [cierre](FASE-1.3-cierre.md). La próxima orden sería
1.4; no inferirla del plan ni de este ejemplo API.
