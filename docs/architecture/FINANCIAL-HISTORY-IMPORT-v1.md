# Financial History Import v1 — registro durable sin ejecución

[Orden1.9D](FASE-1.9D-orden.md), [ADR017/auditoría previa](ADR-017-financial-history-import.md),
[cierre](FASE-1.9D-cierre.md). Solo fixtures sintéticos. No1.9E.

## Frontera interna

HistoryImporter(business_id,page_size) comparte get_conn/FinancialSession y gate
con HistoryCutoff. No endpoint, tool, CLI, scheduler, IA ni productor conectado.
prepare(principal,manifest_uuid,batch_uuid) valida permiso actual, flags OFF,
cut C frozen/certifiable/boundary_current, epoch fenced/control/generación/scope,
versiones y hashes iguales al carrier congelado. Diagnóstico B nunca autoriza.
record_item autentica y revalida todo en una TX por candidato. run pagina el plan
con gates breves, guarda solo claves/edges O(N+E), ordena topológicamente y llama
record_item por candidato. read_batch ofrece auditoría paginada64 bajo permisos
actuales también después de revocación, sin permitir nuevo registro.

HistoricalImportContext es frozen: tenant, epoch/generación, manifest, batch,
item, candidate hash, identity hash, operador/sesión actuales, UUIDs esperados y
importer_version=1. No datos de canal/LLM ni bypass flags. El recorder prestado
contrasta el objeto con las filas intent/batch dentro de la misma TX; los guards
SQL comprueban además frontera actual, sesión, payload, identidad y request.

## Tablas y sellado transaccional

Migración72 añade financial_history_import_batches y financial_history_import_items.
Batch FK tenant a C y epoch/generación; conserva hashes, versión, creador y fechas.
Estados prepared/running/completed/blocked/partial. Items FK tenant a batch+
manifest/item, al evento/operación/autorización y operador. Guard retención y
resultados terminales inmutables. Índice identity_hash/business_id resuelve cobertura
histórica; no segunda tabla ni inserciones en coverage live65–67.

Intent recording incluye raw/candidate hashes, identidad canónica, event/op/auth
UUID exactos, evento/request canónicos, secuencia esperada y sesión vigente.
Índice parcial admite solo un recording por tenant. completion_key=recorded y
FK propia diferida al mismo PK+state obligan a concluir el resultado antes del
commit. No intent recording confirmado ni resultado recorded sin su evento.
El resultado se sella al cambiar recording→recorded; no efecto en Operations.result.

## Excepción SQL cerrada

Se conservan todos los guards71;72 reemplaza únicamente INSERT de events/links/
sequences y UPDATE del contador. El guard sigue adquiriendo noesis_history_gate
en PG (try-lock, READ COMMITTED). UPDATE valida OLD y NEW tenant. Solo permite
el UUID exacto de un intent vigente con candidato A/B congelado y soportado,
sin incidencia blocking ni sesión revocada. El payload/identidad/request esperado
coincide con el candidato congelado. Un EE live no cumple origin=historical.
Sin intent, batch/manifest/item/hash equivocado o intent para otro UUID: rechazo.

Links se validan contra las relaciones del evento esperado antes de que exista
el evento. Los guards63 conservan tipos/targets/conjunto sellado y FKs diferidas.
El contador sigue siendo el único por negocio: permite INSERT0 y exactamente
OLD+1=expected_sequence; retry existente no incrementa y rollback lo revierte.
Application assert_writable/EconomicEvents.append/Capture conservan rechazo
bajo fence; importer usa exclusivamente repositorios y recorder específicos.

El FK/boundary del intent demuestra event→batch→C→epoch→T0. SQL impide nuevas
inserciones históricas sin intent incluso sin fence. Evidencia anterior72 se
conserva sin inventarle un batch retroactivo. Propietario DDL que desactive guards
no es una API autorizada; fixtures de corrupción se identifican como tales.

## Operación y autorización

HistoricalIdentity v1 intacta determina event UUIDv5 y EntryIdentity historical.
operation_uuid UUIDv5 con namespace propio constante + identity hash; ni operador,
manifest, reloj o retry lo alteran. Authorization UUIDv5 de esa operación.
FinancialRequest v1 contiene historical_recording_version, identity/candidate hash,
tipo/payload_version y amount/currency/date/revisión exactos. created_by y
recorded_by son registrador actual; nunca autor original. Una sola autorización
historical_unknown, actor/session NULL, permiso historical.record, canal historical.

Operación D PREPARED permanente, result/committed_at NULL. SQL bloquea HUMAN,
MANDATE, APPROVED, COMMITTED, cambio de namespace y cancelación de registros D.
Las operaciones contractuales históricas previas sin import intent conservan
sus salidas REJECTED/CANCELLED sin ejecución; datos previos incoherentes siguen
bloqueados en decoder/servicio. FinancialOperations.execute nunca se utiliza.

## Matriz durable y fechas

| Origin | Versiones admitidas |
|---|---|
| live | v1 once tipos; v2 invoice.issued/invoice.rectified existentes |
| historical | v1 válido; v2 supplier_invoice.confirmed, expense.confirmed, bank_transaction.imported |

EconomicEvent live mantiene su validador. HistoricalEconomicEvent separado valida
EventPayload histórico, y StoredEvent selecciona el contrato por origin durable.
canonical_version=1 y bytes/hashes anteriores no cambian. Nueva v2 factura
histórica no se admite en SQL ni importer. Los tres v2 conservan todos los campos
de A: confirmed_on/imported_on obligatorios anulables, evidence_basis/hash.
No float, subcéntimo, moneda ajena ni NULL sustituido por cero.

| Historical v2 | Obligatorios | Opcionales |
|---|---|---|
| supplier_invoice.confirmed | total; issued_on y confirmed_on anulables; evidence_basis/evidence_hash | invoice_number, due_on, base, vat_amount, irpf_amount anulables |
| expense.confirmed | total, description; spent_on y confirmed_on anulables; evidence_basis/evidence_hash | vat_amount anulable |
| bank_transaction.imported | amount; booked_on e imported_on anulables; evidence_basis/evidence_hash | value_on y bank_reference anulables |

Schema cerrado: campos adicionales se rechazan. Basis observed_state no acredita
el hecho original; una fecha económica conocida tampoco acredita la fecha de
confirmación/importación. Todos los importes usan el contrato Money de A.

Observed_at se rehidrata de started_at del carrier congelado: B/C lo excluyen de
su hash semántico, no se calcula al importar/reintentar. Occurred/economic/date
provenance proceden de HistoricalDates; no dar zona a naive ni inventar fecha.
Recorded_at es el instante de la primera incorporación durable y queda inmutable.
Provenance historical_import_v1, date_provenance historical_dates_v1.kind.

## Fuentes, dependencias y retry

RawReader.read_key consulta tenant+PK real mediante execute_exact. Contrasta
RawSource canonical/hash/revisión y los importes contractuales y campos necesarios
con el plan. Referencias fiscales congeladas se leen sin recalcular hash/QR/XML;
solo se conserva su verificación previa si todos los campos raw coinciden.
No writer, emisión/cobro/banco/compra, llamada externa o modificación legacy.
SOURCE_DRIFT revierte la TX, guarda un bloqueo de importación y permite invalidación
explícita por el dueño del cut después del rollback; fence permanece activo.

Única ampliación de soporte: not_durably_supported para los tres v2 A aprobados.
Se conserva classification/assessment/severity/candidate/plan original. Incidencia
blocking o dependencia no acreditada impide importación; no se aplica excepción
a factura, C/D, out_of_scope/excluded ni transformación de binario a Money.

Dependencias por HistoricalIdentity exacta, assessment A y evento durable validado;
live cubierto o histórico previo permiten parent si el contrato lo admite.
Se verifica source/revisión/tipo/hash/links reales, no basta coverage. Los SQL guards cotejan cada edge con el padre congelado A y el evento/proof exactos antes de aceptar el intent. Padre B
no satisface verified dependency. No heurística importe/fecha/cliente. Parent
ausente/C/D/cruzado/conflictivo bloquea. No continuidad live desde histórico.

Retry mismo item devuelve resultado original tras verificar fuente/evento.
Otro batch del mismo plan compara candidate/raw/identity y evento/links exactos;
referencia existing sin append ni cambiar batch original. Nuevos inventarios
reconocen los tres v2 históricos sin relaciones y con hash del
payload/coherencia de identidad exactos; conservan B como B y producen
covered_existing. También reconocen v1 D determinista con contraste de fuente,
payload y conjunto exacto de relaciones/targets; no fabrican cobertura live. D verifica además prueba durable de importación/op/auth.
Contenido incompatible produce EXISTING_EVENT_CONFLICT sin otra UUID.

## Finalización, reversión y límites

Manifest BLOCKED puede importar candidatos seguros independientes: batch partial
si hubo evidencia, blocked si no. completed expresa terminar el plan de un C sin
pendientes, jamás reconciliation PASS ni activation ready. Éxito/crash no libera
epoch ni activa flags. Release/invalidate compiten por el mismo gate y prohíben
items siguientes; auditoría de resultados anteriores permanece disponible.

Downgrade72 vacío restituye CHECK65 y guards71. Con batch/items/v2 histórico se
bloquea antes de retirar defensas. SQLite actualiza únicamente la definición del CHECK y el trigger capture_event
dentro de la TX de migración, recarga schema_version y comprueba integrity_check
y foreign_key_check. No reconstruye tablas referenciadas ni desactiva FKs.
El procedimiento de metadatos sigue [SQLite ALTER TABLE, apartado 8](https://www.sqlite.org/lang_altertable.html).
La prueba 71→72→71→72 conserva filas/bytes/hashes/links/secuencia y verifica rollback
tras fallo posterior al cambio del CHECK. PG ALTER CHECK sin reescribir eventos.
Migración71 no se modifica. Retención/purga/transición live esperan1.10;
restauración de copia real espera1.9F. Cinco flags OFF, producción no consultada.
