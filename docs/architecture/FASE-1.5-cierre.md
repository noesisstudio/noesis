# Informe de cierre — exclusivamente Fase 1.5

Estado: **cerrada, 18 PASS / 0 FAIL**. No avanzar a 1.6. Base main08a6548/schema64,
árbol limpio y pull ff-only; trabajo en C:/Users/mikic/Documents/noesis.

## Arquitectura, entradas y flujo

[Auditoría previa](FASE-1.5-entrada-audit.md), [ADR-009](ADR-009-invoice-capture.md),
[contrato/API](INVOICE-CAPTURE-v1.md). Un motor real: writer extraído en 1.4.

review lee borrador/líneas y datos dependientes del mismo negocio, resuelve plazo,
fecha y configuración. prepare recibe EntryIdentity auténtica de servidor; UUID de
operación generado por repositorio. authorize conserva actor/negocio/sesión,
request/hash/revisión/canal/timestamp en evidencia 1.2. La aprobación no se crea
por haber llamado review ni por una propuesta de IA/pending temporal.

execute posee una sola transacción/conexión: permisos → lock operación/aprobación
→ gate negocio → invoice + cliente/business/serie → revisión/huella completa
→ cobertura → numeración → freeze → registro/outbox o legacy invoice event
→ snapshot/payload → validación de céntimos → append primary → resultado durable
→ committed → COMMIT. Ninguna AEAT/IA/red ni conexión o commit intermedio.
value_ledger se observa best-effort después del commit; su caída no invalida factura.

Conectados: servicio interno autenticado InvoiceCapture y método explícito del
adaptador issue_captured con Principal/operación ya aprobada. Ningún endpoint ni
herramienta IA recibe ese contexto. Web send → run_tool/pending/adaptador, chat,
WhatsApp y recurrentes carecen del puente de aprobación/identidad completo: siguen
legacy con flags False y esperan 1.8. db capture_requested o flagCore sin contexto
falla cerrado; no hay fallback solicitado. Recurrente conserva el mismo writer,
sin motor alternativo ni autorización/identidad inventada.

## Payload, Decimal y vínculo

v1 intacto, incluyendo sus bytes/hashes/vectores. Solo invoice.issued y
invoice.rectified admiten payload v2: todos los campos v1 más evidence cerrado.
Contiene IDs/serie/tipo/número/fechas, cliente/emisor congelados, líneas completas,
base/tasa/cuotaIVA, IRPF/total, perfil/hash, fiscal record con productor/SHA/previous/
QR/fecha, source_fingerprint y money_provenance=legacy_binary_storage.
Fiscal breakdown_json permanece texto opaco congelado, sin recálculo de XML.

Ningún float canónico ni columnas monetarias nuevas. El borrador previo reside
en REAL/DOUBLE: nunca afirmar precisión de entrada histórica recuperada.
exact_inputs y prepared_values conservan la frontera del writer; cálculo Decimal
existente se compara con snapshot/frozen legal al céntimo y el contrato compara
componentes, líneas y fiscal record. Discrepancia → excepción/rollback, no ajuste.
Revisión, validación y ejecución fijan contexto Decimal local de precisión 50;
un contexto de baja precisión del llamador no cambia la confirmación.
Occurred_at=None porque legacy no da instante con zona; fecha civil emitida real,
observación UTC explícita. No periodos/posting/ledger nuevo.

Migración 65: únicamente cobertura y soporte de versión2 para emisión.
invoice_economic_coverage PK(negocio,factura), evento y operación únicos, inmutable.
FK inmediata a invoice; FK compuesta diferida a event(negocio/UUID/invoice/tipo/op)
y a operación(negocio/UUID/state='committed'). Guard exige borrador + aprobación
para el target correcto; evento v2 exige cobertura + fuente emitida; rectifies
apunta al invoice original real. Commit con evento/result ausente falla incluso
si alguien captura un error del append. Toda nueva operación de emisión/rectificación
requiere cobertura al confirmar; resultado coincide con ID/UUID/tipo/hash/número/
importe/moneda/captured. Sin columna en invoice, FK circular ni cascada de borrado.
Confirmación exige evento v2: tampoco permite usar un evento v1 de infraestructura
con cobertura nueva para confirmar una factura sin emitir.

PostgreSQL altera CHECK; SQLite reconstruye events/links dentro de transacción,
con copia SQL local y foreign_key_check, sin apagar FKs ni cargar historia en RAM.
v1 bytes/links/hash/metadata preservados; no backfill ni facturas históricas tocadas.
Bajada 65→64 vacía/v1 permitida; con cobertura/v2 bloqueada conservando toda evidencia.

## Idempotencia, rectificativas y fiscalidad

Misma identidad/request recupera operación; distinto contenido conflicto.
UUIDv5(op,'invoice.primary.v2') estable y slot primary. Replay committed retorna
resultado original antes del efecto: cero nuevos números, freeze, registros,
outbox, secuencias o eventos. Validador estático de dominio se aplica al replay;
la revisión actual no se exige para recuperar un resultado pasado.
Otra operación sobre el mismo borrador queda stale tras la primera emisión.

R1–R5: restricciones previas intactas, original inmutable, número/registro propios,
solo invoice.rectified y un rectifies al evento original válido capturado v2.
Sin original válido falla antes de efecto, sin reconstruir histórico. R5 solo F2,
resto R sobre F1; sustituciónS no soportada, igual al legacy. Sin doble invoice.issued.

Golden 1.4 capturado del main anterior: F1/F2/R1–R5, líneasIVA21/10/4/0, IRPF,
registros completos, SHA, previous_hash, QR y XML siguen iguales por el nuevo camino.
EE es adicional y ajeno a huellaVERI*FACTU. Lock común de cadena 1.4 intacto; no red AEAT.

## Archivos creados/modificados

Nuevos: invoice_capture/{__init__,service,schema}.py; economic_events/invoice_payload.py;
tests/{invoice_capture_contract,test_invoice_capture,postgres_invoice_capture}.py;
architecture/{ADR-009-invoice-capture,INVOICE-CAPTURE-v1,FASE-1.5-entrada-audit,FASE-1.5-cierre}.md.
Runtime modificado: migrations, db(fachada fail-closed), adapters/invoicing,
economic_events/contracts(v2, v1 intacto), financial_operations/service(validador
estático opcional previo a replay). CI: gate PostgreSQL de productores.
Gobernanza: AGENTS; architecture README/plan/ADR002/contratos v1; guías01/03/04/06/08;
Arquitectura, Mapa-codigo, Decisiones, Estado, Tareas, Registro-cambios/QA, JSON.

## Validación

- SQLite: **24/24** pruebas nuevas de productores; dirigidas **78/78 OK**
  (48.445 s), incluyendo operaciones29, contratos21 y baja4.
- PostgreSQL16.15 real: **27/27** productores, **110/110 OK** combinado
  (37.109 s): writers18, eventos27, operaciones32 y fundamentos6.
  Carreras de dos conexiones sobre operación/factura; seis emisiones capturadas
  en dos series con una legacy concurrente: siete números y cadena única, seis EE.
- Suite general final: **1508/1508 OK**, 1053.342 s. Legado financiero,
  VERI*FACTU, web, herramientas, WhatsApp, documentos y fases previas sin regresión.
- Primera suite:1503, un fallo por omitir cobertura en inventario de baja; corregido
  con protección de evidencia y prueba en ambos motores. Repetición intermedia
  interrumpida para endurecer requisito v2; solo la ejecución completa final acredita cierre.
- Nueve fallos inyectados revierten tablas y permiten retry; pruebas alcanzan el
  intento de commit para bypass sin cobertura y cobertura con v1/factura no emitida.
  Stale, replay/conflicto, precisión/contexto Decimal, float/moneda/versión/campos,
  céntimos, multiempresa, inmutabilidad y paridad golden fiscal en ambos motores correctos.
- Migraciones SQLite0→65→0→65, 64→65→64→65 con bytes/links/hashes v1 conservados;
  PostgreSQL histórico32→35→65 y rollback65→55→54→53→54→55→65 con datos preservados.
  Downgrade con captura/v2 bloqueado. 36 rutas PG, copia/restauración, privacidad,
  conversación, deduplicación y recuperación correctas; HTTP local200 en health/ready/portada/login.
- Ruff, Bandit (gate high/high de CI), pip-audit sin vulnerabilidades conocidas,
  uv lock --check, secretos incluidos nuevos archivos, Node3/3, verdad documental,
  enlaces y diff pasan. No dependencias nuevas ni cambios de flags.
- Autoauditorías de la orden (14 respuestas) y Master Plan§44 documentadas;
  **18 PASS / 0 FAIL**. Sin aceptación AEAT, CI remota ni despliegue verificados.

## Criterios de aceptación

| Criterio de la orden | Estado/evidencia |
|---|---|
| 1 Servicio canónico único | PASS — Operations + writer existente + append + resultado |
| 2 F1/F2 → invoice.issued | PASS — uno por documento, payload congelado completo |
| 3 R1–R5 → invoice.rectified | PASS — uno, rectifies real, original sin historia inventada |
| 4 Identidad/replay/conflicto | PASS — UUID/entrada estable, mismo resultado y ningún nuevo efecto |
| 5 Autorización durable exacta | PASS — recibo 1.2 + hash/revisión/huella de dependencias |
| 6 Atomicidad | PASS — nueve fallos y bypass revierten número/freeze/registros/outbox/evento/result |
| 7 VERI*FACTU intacto | PASS — golden 1.4 de documentos/registros/SHA/QR/XML, sin AEAT |
| 8 Exactitud y provenance | PASS — Decimal, cotejo legal céntimo, floats rechazados, binary explícito |
| 9 Vínculo durable | PASS — cobertura/FKs compuestas/inmutabilidad/guards ambos motores |
| 10 Captured vs legacy | PASS — no commit sin evento/result; sin fallback y flags False |
| 11 Entradas actuales | PASS — inventario completo, servicio/adaptador; canales bloqueados para captura sin contexto |
| 12 Recurrentes | PASS — mismo motor, sin conectar identidad/autorización completa |
| 13 Observaciones | PASS — postcommit best-effort, caída probada sin revertir factura |
| 14 Rectificativas/restricciones | PASS — R1–R5, número/registro propios y un evento primario |
| 15 Migración acotada | PASS —65/cobertura+versión, conservación v1, bajada protegida |
| 16 Pruebas obligatorias | PASS — SQLite24, PG27, general1508, regresiones y gates correctos |
| 17 Prohibiciones | PASS — solo dos productores, sin flags/ledger/banco/compras/históricos/activación |
| 18 Autoauditoría/gobernanza | PASS — respuestas y documentación durable |

## Autoauditoría de la orden (14 respuestas)

1. Factura capturada sin evento: no; FK diferida de cobertura impide commit.
2. Evento capturado sin factura emitida: no; FK/guard exige fuente fiscal emitida,
   cobertura de misma operación y operación committed al commit. v1 sintético/histórico
   de infraestructura previa se conserva, no se convierte en productor autorizado.
3. Número repetido por retry: no; committed no vuelve al writer; fallo revierte secuencia.
4. EE repetido: no; cobertura/UUID/op-slot/source únicos, replay no append.
5. Rectificativa dos primarios: no; comando/tipo/cobertura/primary únicos.
6. EE altera huella: no; ninguna función fiscal usa su contenido. Golden intacto.
7. AEAT dentro de TX: no; solo outbox, red worker después del commit.
8. Fallo EE deja emitida: no; excepción exterior y FK diferida aun si se captura error.
9. Stale emite: no; huella completa+revisión bajo locks antes de efecto, tests líneas/
   cliente/fecha/importe/fiscal/profile/serie.
10. Fallback silencioso: no; capture sin contexto rechaza, evento falla revierte.
11. Float como exacto: no; procedencia binaria explícita de borrador congelado,
    cálculo/JSON nuevo Decimal/string, cent mismatch falla.
12. Canal inventa identidad: no; ningún canal integrado simula evidencia; servidor
    interno requiere Principal/EntryIdentity y recibo durable previo.
13. Otro productor accidental: no; solo dos comandos/eventos canónicos; los demás
    hechos en tests son fixtures explícitas de infraestructura, nunca hooks runtime.
14. Fase 1.6+ adelantada: no; sin cobro/banco/compras/anulación/historia/activación.

## Autoauditoría Master Plan §44

1. EE: invoice.issued o invoice.rectified exclusivo por documento confirmado.
2. Asiento: ninguno. 3. Cuentas: ninguna. 4. TaxLines: ninguna.
5. OpenItems: ninguno. 6. Dimensiones: tenant/origen/serie/cliente/fechas reales,
   sin motor dimensional. 7. Permisos:1.2 sesión/usuario/negocio/creador, suscripción/
   no demo y aprobación humana durable; IA no aprueba.
8. Reversibilidad: rollback antes de commit; después documento/evento inmutables,
   corrección por rectificativa autorizada. No borrar evidencia para downgrade.
9. Idempotencia: operación/entrada estable + cobertura/eventslot/source uniques;
   conflicto de contenido y recuperación de resultado.
10. Periodo cerrado: no modelo contable ni posting nuevo; no se afirma garantía
    futura de cierre ni se altera fecha fiscal histórica.
11. Auditoría: request/autorización/snapshot/huellas/evento/coverage/result/datos
    fiscales, bitácora/QA y mapa de entradas. 12. Prueba: dos BD reales, nueve fallos,
    multiempresa/stale/replay/cent mismatch/carreras/fiscal golden/migración/gates.

## Riesgos y próximos límites

- Borradores legacy binarios no recuperan precisión anterior; límite explicitado.
- Serialización por tenant y locks de cadena conservados; coordinar despliegue/
  rollback sin mezclar escritores que omitan el protocolo. PG READ COMMITTED.
- Request 64 KiB, líneas1–256, perfil por huella; fuera de límites falla cerrado.
- Aprobación caduca por cambio de datos o fecha civil; requiere otra revisión.
- Originales sin cobertura/v2 y rectificación entre distintos propietarios de
  operación se rechazan bajo política 1.2 vigente; no ampliar permisos ni backfill.
- Canales/recurrentes 1.8, recuperación histórica 1.9 y activación/retención/exportación/
  cierre conservando evidencia 1.10 quedan pendientes, con baja destructiva bloqueada.
- AEAT/certificados/representación/gaps fiscales, CI remota y despliegue no probados
  por estas pruebas locales ni por un push. Flags financieros continúan False.

Rollback: conservar 65 y evidencia al revertir código; nunca retirar cobertura/v2
ni reemitir originales para completar historia. No avanzar a 1.6.
