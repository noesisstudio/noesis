# Cierre de Fase 1.9C — Epoch, T0 y fence

2026-10-04. **Implementada, validada y cerrada**. Solo 1.9C, no 1.9D. Cinco flags OFF.
Ninguna producción, copia real, AEAT o proveedor real consultado.

## 1. Mapa completo de writers

[Mapa previo](FASE-1.9C-writers.md), realizado sobre main antes de schema/guards:
124 ubicaciones DML y nueve grupos dinámicos/transversales. Función/API, tabla,
tenant, gate previo y política por mutación. Incluye filesystem, dispatch,
cascadas, cinco Capture, EE directo, recurrencia, CSV y documentos.
Scope cerrado: 28 kinds B, 29 tablas mutables guardadas (27 fuentes y dos
contadores), anchor business protegido contra baja/cambio de identidad.
Ninguna tabla mutable del catálogo queda protegida solo por aplicación.

## 2. Archivos

Nuevos módulos en `src/noesis/financial_history/`: cutoff.py, cut_schema.py,
cut_scope.py y fence.py. Nuevos tests: financial_history_cutoff_contract.py,
financial_history_cutoff_races.py, financial_history_cutoff_worker.py,
test_financial_history_cutoff.py y postgres_financial_history_cutoff.py.

Runtime adaptado: db.py, migrations.py, documents/storage.py,
financial_operations/service.py, economic_events/service.py,
financial_writers/boundary.py, financial_channels/recurring.py, web/scheduler.py,
y readers/repository/service de financial_history. Dos tests B adaptan target de
schema sin cambiar diagnóstico. CI añade la suite PostgreSQL C. El test existente
test_charla_whatsapp.py fija jueves/domingo para una expectativa semanal que
fallaba en domingo también sobre main anterior; sin cambio a NLU ni producto.

Documentos nuevos: [orden](FASE-1.9C-orden.md), [ADR016](ADR-016-financial-history-cutoff.md),
[contrato](FINANCIAL-HISTORY-CUTOFF-v1.md), mapa y este cierre.
Actualizados AGENTS, project-state, Estado, Tareas, QA, Registro-cambios, Inicio,
Mapa-codigo, Arquitectura, Decisiones, guía técnica, índice/plan de arquitectura
y guías 01/03/04/06/07/08. Sin nueva pantalla, endpoint, tool ni CLI.

## 3. Migration

Migración 71: cuatro tablas de control, índice activo por negocio, relación
epoch/manifest y tres índices sobre items/incidencias para freeze acotado.
Guards de identidad, retención, transición, certificación y sources.
Migración 70 y contratos puros 1.9A intactos. PG29 no modificado.

## 4. Schema epoch/control

| Tabla | Contrato |
|---|---|
| financial_history_epochs | PK tenant/UUID, generación única tenant, actor/T0 aware, versiones/scope/código/entorno inmutables; invalidación/release con actor/fecha/motivo |
| financial_history_control | PK business_id, FK compuesta epoch/generación, fence/version/updated_at |
| financial_history_cut_manifests | Nuevo sobre lógico; FK tenant a epoch y carrier B nuevo; mode certifiable_inventory, T0/scope/entorno, tres hashes, status/result, boundary/certifiable; eligible=false |
| financial_history_epoch_audit | Append-only actor actual/acción/motivo/instante, sin contenido sensible de sources |

Ninguna de las cuatro tablas admite DELETE. No MAX(id), contador global ni nuevo
pool/ORM. Todos los repositorios comparten infraestructura de conexión/TX.

## 5. Estados

| Estado | Fence | Inventory | Writers | Frontera vigente |
|---|---|---|---|---|
| fenced | ON | Permitido | Bloqueados | Sí |
| invalidated | ON | Rechazado | Bloqueados | No |
| released | OFF | Rechazado | Reglas normales | No |

Solo fenced→invalidated/released o invalidated→released. Unique parcial
state<>released incluye invalidated. Sin reactivación ni preparing observable.

## 6. Protocolo exacto de T0

Autenticación preliminar sin row locks → gate financiero común → revalidación
de sesión/suscripción con locks → control tenant FOR UPDATE → ausencia de otro
epoch activo → generación control+1 → reloj UTC aware → epoch/control/audit → commit.
Gate retenido hasta commit/rollback. Los writers anteriores protegidos ya terminaron.
No timestamp de inicio de transacción PG, created_at ni MAX(id).

No user/business FOR SHARE antes del gate: un waiter no impide al propietario
actualizar esas filas. Revalidación posterior observa permisos revocados;
revocación posterior espera la TX autenticada. Scan/aggregate por páginas en TX
cortas; freeze solo valida control y persiste valores ya calculados.

## 7. Fence enforcement

assert_writable con conexión prestada/gate/control por PK antes de efectos.
HistoricalFenceActive reconocible, sin fallback. SQL relevante usa mismo gate
transaccional con try-lock; HistoricalWriterBusy exige rollback/retry completo
si está ocupado o aislamiento PG incompatible. Flags OFF no deshabilitan fence.

## 8. Application guards

Boundary antes de snapshot/fuente; Operations antes de operación/autorización/
coverage; EE antes de savepoint/contador. Fachadas de drafts, quote→invoice,
parciales, series, recurrencia, branding/perfil, metadata y cascadas tienen guard
temprano. execute/execute_exact solo traduce marcadores propios; otros errores
legacy conservan su comportamiento. No nuevo motor financiero dentro de db.py.

## 9. SQL guards

BEFORE INSERT/UPDATE/DELETE en las 29 tablas. UPDATE: columnas económicas/evidencia,
PK y ambos tenants. Incluye note/void_reason/match_score/match_reason que generan
revisión64. document_sequences solo invoice/invoice_series; quote permitido.
economic_event_sequences completo. Business DELETE/id protegido con evidencia.

PG: guard anterior a legacy; SHA256 builtin idéntico a lock_key Python; try-lock
evita esperar gate reteniendo source lock. SELECT volatile observa control nuevo
bajo READ COMMITTED incluso con statement iniciado antes de T0. SQLite: ABORT
en misma serialización BEGIN IMMEDIATE. Ninguna extensión/dependencia nueva.

## 10. Capture

Invoice/Payment/Bank/SupplierInvoice/Expense respetan guard común aun flags OFF.
PREPARED/APPROVED previos conservados; no authorize/execute/cancelación automática
ni COMMITTED bajo fence. Pruebas de cinco procesos confirman cero efectos.

## 11. EconomicEvents

Append live directo gate/revalidación/control antes de savepoint/contador;
SQL eventos/links/coverage protegido. Ningún nuevo productor ni append historical.
Sin EE histórico/v2 durable/event log operacional. quote.accepted/job.completed
no adquieren significado económico. Decimal/NUMERIC/execute_exact conservados.

## 12. Fiscal/async

Scope C neutraliza status/sent_at/completed_at/updated_at de outboxes y excluye
remision/aceptacion/rechazo del hash C. Evidencia fiscal inmutable incluida.
Respuesta terminal anterior permitida; claim/intento/dispatch nuevos bloqueados.
Gate durante llamada bounded existente: open espera dispatch anterior; posterior
falla antes de proveedor. Epoch entre claim/intento omite tenant sin abortar otros.
Solo stubs en QA, no AEAT. Sin cambio de reglas fiscales/protocolo de facturación.

## 13. Documents/recurring

Membership documental conservador: alta/replacement/review/classification/relink/
deletion protegidos, también stored_name/filename/mime/size. OCR/notas ajenos
permitidos. Unlink con gate durante IO. Cascada cliente cambia DB en una única
TX antes de retirar bytes: fence rechaza antes de efectos parciales.
Preprocessing puede crear archivo nuevo huérfano, nunca reemplazar evidencia.

Recurrencia no crea draft/run ni avanza agenda fenced; omite sin run error y
otro negocio continúa. Occurrence previa no emite. CSV/document review no
confirma bank/received/expense durante fence. No nuevo scheduler de históricos.

## 14. Manifests certifiable

Ejecución nueva del scanner B crea carrier y sobre C atómicos. Carrier B siempre
diagnostic/certifiable=false por CHECK70: imposible adjuntar diagnóstico antiguo
o promover por UPDATE. Readers/classifier/planning reutilizados; A/B/C/D intactos.
Scope C cerrado/versionado declara exclusión transporte.

Cada página valida epoch/control/scope/entorno; segundo pass compara source set.
Freeze: certifiable solo igualdad de hashes/sin SOURCE_DRIFT. Drift→BLOCKED e
invalidación conservando fence. Inventario consistente puede ser BLOCKED por
incertidumbre financiera. **diagnostic B ≠ certifiable inventory C ≠ importable D**.
eligible_for_import=false siempre; certifiable no significa activation ready.

## 15. Crash/retry

Crash tras open/durante scan/después de freeze conserva fence/T0. Retry exacto
recupera identidad y reanuda parcial; otra UUID con epoch activo conflicta.
Sin finally/reaper/TTL release. Atención tras 30 minutos solo señal. Error real
del inventory iniciado invalida sin release; argumentos/permisos/conflictos
no invalidan automáticamente un cut ajeno.

## 16. Invalidate/release

Actor/motivo/fecha auditados. Invalidación aborta parciales BLOCKED, revoca
certificación y conserva fence. Release explícito apaga control y revoca boundary.
Hash/inventory/freeze original conservados. Trigger sincroniza revocación/control
también con transición SQL administrativa. Nuevo cut necesario tras liberación;
ninguna elegibilidad futura de D concedida.

## 17. Permisos

Principal servidor; usuario activo tenant/session_version vigente; suscripción
escribible; cinco flags OFF. historical.record interno, sin financial.authorize
ni receipt humano histórico. Read/invalidate/release solo opened_by actual.
FKs compuestas/IDOR/actor ajeno/revocación/UUID idénticas entre tenants probados.
Código/entorno explícitos con etiquetas cerradas 1..128 sin URLs/credenciales.
IA sin autoridad financiera.

## 18. SQLite

BEGIN IMMEDIATE y SQL guards en propia TX. Barreras de procesos prueban writer
anterior commit/rollback, epoch anterior y dos aperturas. SQLite tiene un writer
por archivo: contención breve entre negocios posible, sin fence lógico cruzado
ni lock del scan completo. No se atribuye granularidad PostgreSQL.

## 19. PostgreSQL

PG16.15 real localhost/noesis_ci descartable, fixtures sintéticos. Advisory gate
tenant y control indexado READ COMMITTED. SQL relevante con REPEATABLE READ/
SERIALIZABLE rechazado; rollback/retry obligatorio. Mismo pool/FinancialSession.
Sin normalización monetaria legacy nueva ni dependencia de float en Core.

## 20. Carreras

Procesos/conexiones independientes con barreras stdin/stdout y pg_locks. Writer
primero commit/rollback→T0 posterior; epoch primero→rechazo; dos aperturas→uno;
cinco Capture; legacy/SQL/EE directo; open/release→generación/un active;
revocación protegida; waiters sin locks antes del gate; snapshot SQL anterior a
T0 observa fence posterior; epoch entre claim/intento no llega al proveedor.
Sin sleeps como única sincronización; timeouts solo detectan bloqueo de QA.

## 21. Side-effect proof

Oracle execute_exact de todas las fuentes B, Operations/authorizations, canales
y ambos contadores de negocio antes/después. Open solo epoch/control/audit;
writer rechazado no cambia importe/estado/número/outbox/coverage/secuencia EE.
29 tablas con filas reales probadas INSERT/UPDATE/DELETE. Hash estable tras
rechazo y escritura en otro tenant. Cinco flags conservados.

PG SERIAL físico puede consumir un PK en INSERT fallido: no es numeración
financiera, no define T0 y no se promete consecutividad de PK. Los contadores
de factura y EE no avanzan con writer rechazado.

## 22. Performance

Catálogo instalado + lookup PK control por writer, sin scan histórico. Medición
de 100 checks sin epoch en §24. Páginas 1..64, freeze sin full source scan/gate
gigante, agregados indexados. Solo dispatch/unlink mantiene gate durante IO
acotado. Sin optimización especulativa.

## 23. Migration cycles

SQLite clean→71,70→71,vacío71→70→71 y0→71→0→71; PG clean→71,70→71,
vacío71→70→71. Con epoch/audit/cut incluso released, downgrade71 falla antes
de retirar protección. Smokes PG preservan datos fiscales/privacidad en ciclos
inferiores soportados. PG29 preexistente no tocado. Base53 sobre71 sin epoch:
cliente/factura/emisión/cobro/export PASS. No retirada con evidencia ni paso D.

## 24. Suite/gates

CI de cierre [37201939291](https://github.com/noesisstudio/noesis/actions/runs/37201939291) SUCCESS sobre317eed8, runtime7c0055c:
general1755 PASS (897.022s, dos skips PG), PostgreSQL338 PASS, ambos jobs/gates/
migraciones/código anterior/privacidad/rollback PASS. **44 criterios PASS, 0 FAIL**.
Adenda de cierre solo documental; código/tests/workflow/dependencias idénticos
a la ejecución validada. Producción/despliegue no consultados. No1.9D.

Suite general local: 1755 tests en1762.024s, un fallo preexistente de expectativa
de agenda semanal y dos skips PG. El fallo se reproduce en main anterior b31e165
con schema70: el domingo «esta semana» contiene solo hoy. Se corrige exclusivamente
el test con fixtures explícitas de jueves/domingo; clase completa revalidada y
85 tests PASS en99.807s. Ningún cambio a comportamiento financiero
o calendario del producto. CI completa final SUCCESS, enlazada al comienzo de §24.
Resultados sobre runtime final:

| Verificación | Resultado |
|---|---|
| CI general final | PASS: 1755 tests, 897.022s, dos skips PG |
| CI PostgreSQL final | PASS: 338 tests, incluye C50 |
| PostgreSQL, matriz de todas las fases Core | PASS: 338 tests, 188.644s |
| PostgreSQL C, oracle incluye ambos contadores | PASS: 50 tests, 45.092s |
| SQLite C, oracle incluye ambos contadores | PASS: 46 tests, 110.916s; dos tests de locks PG omitidos explícitamente |
| WhatsApp, clase completa tras fixture de calendario | PASS: 85 tests, 99.807s |
| Node, marketing/calendario/admin/canales | PASS: 9 tests |
| Ruff src/tests | PASS |
| Bandit high/high | PASS |
| detect-secrets en todos los archivos versionados | PASS |
| project truth schema/estado/precios | PASS |
| uv lock --check / pip-audit | PASS; sin vulnerabilidades conocidas; editable local no se consulta como paquete PyPI |
| Enlaces Markdown locales modificados | PASS |
| Contratos puros A/migración70 contra HEAD anterior | PASS: seis archivos idénticos |
| SQLite ciclo completo 0→71→0→71 | PASS |
| PG migración histórica/rutas calientes | PASS: 36 rutas sin 5xx |
| Código base53 sobre schema71 sin epoch | PASS |
| Release smoke PG aislado | PASS: privacidad, conversación, marketing y rollback vigente→55→54→53→54→55→vigente |
| Servidor local SQLite | PASS: /health, /ready, / y /login 200; scheduler mock, sin proveedores |

La suite general local inicial NO se presenta como PASS. La CI remota final
ya supera toda la suite con el test corregido: PASS1755. No se oculta el fallo inicial.

Medición 100 checks sin epoch: PG 41.346ms en matriz y45.281ms en dirigida;
SQLite7.264ms. Son medidas sintéticas locales, no SLO de producción.
CI del commit enlazada arriba; no inferir despliegue validado en producción.

## 25. Riesgos

- Fence bloquea deliberadamente dinero hasta acto explícito; invalidated no libera.
- SQLite contención por archivo; PG dispatch/unlink acotado retiene gate tenant.
  SQL directo que pierde try-lock requiere rollback/retry.
- Scope C v1 excluye transporte y incluye documentos conservadoramente. Extender
  sources/columnas/revisiones requiere scope nuevo y nueva auditoría de writers.
- DDL privilegiado, triggers desactivados, volumen manual o control DML fuera
  del servicio no son APIs soportadas. No protección contra dueño de BD.
- Rollback a runtime anterior sin guards dispatch/bytes es inseguro con epoch
  activo: conservar runtime compatible/schema71. Downgrade con evidencia bloqueado.
  Compatibilidad con base53 demostrada solo sin epoch activo.
- Filesystem no es transaccional: tras commit metadata un fallo IO puede dejar
  bytes huérfanos; conserva evidencia, no destruye cut. Sin nueva purga automática.
- Sin certeza decimal histórica nueva, reconciliación, importabilidad, política
  RGPD final o prueba de producción/AEAT real.

## 26. PASS/FAIL individual

IDs de los 44 apartados de la [orden](FASE-1.9C-orden.md): **44 PASS, 0 FAIL**.

| ID | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Mapa previo completo | PASS | §1/mapa |
| 2 | T0 posterior a writers anteriores | PASS | §6/20 |
| 3 | Migración exclusiva | PASS | §3/4 |
| 4 | Un solo epoch activo tenant | PASS | unique/carreras |
| 5 | Gate antes de locks de control/source | PASS | §6/test permisos |
| 6 | Fence durable sin TOCTOU | PASS | §7/20 |
| 7 | Error reconocible sin fallback | PASS | §7/8 |
| 8 | Mutaciones relevantes bloqueadas | PASS | §9/21 |
| 9 | Cinco Capture/flags OFF | PASS | §10/20 |
| 10 | EE live directo protegido | PASS | §11 |
| 11 | Transporte anterior/nuevo envío | PASS | §12 |
| 12 | Evidencia documental estable | PASS | §13 |
| 13 | Scope cerrado versionado | PASS | cut_scope/contrato |
| 14 | Nuevo inventory certificable | PASS | §14 |
| 15 | No promover B por UPDATE | PASS | CHECK70/tests SQL |
| 16 | Reusar scanner/classifier/planning | PASS | §14/hooks |
| 17 | Sin TX/gate gigante | PASS | §6/22/test freeze |
| 18 | Invalidate conserva fence | PASS | §16 |
| 19 | Release explícito pierde frontera | PASS | §16 |
| 20 | Crash/retry conserva fence/T0 | PASS | §15 |
| 21 | TTL solo atención | PASS | §15 |
| 22 | SQL guards sources clave | PASS | §9/29 tablas |
| 23 | Baja negocio conserva evidencia | PASS | retención/tests |
| 24 | Carreras reales PG deterministas | PASS | §20 |
| 25 | Invariantes SQLite | PASS | §18 |
| 26 | Open solo metadata/control | PASS | §21 |
| 27 | Writer sin efectos/contadores financieros | PASS | §21/oracle |
| 28 | PREPARED/APPROVED conservados/bloqueados | PASS | §10 |
| 29 | Recurrencia no cambia membership | PASS | §13 |
| 30 | CSV/document review sin confirmación | PASS | §13 |
| 31 | Flags OFF y negocios normales | PASS | regresiones/§21 |
| 32 | Aislamiento multiempresa | PASS | §17/20/21 |
| 33 | historical.record actual | PASS | §17 |
| 34 | Sin importer/Operations históricas | PASS | scope/diff |
| 35 | Sin v2 histórico durable | PASS | contratos intactos |
| 36 | Ciclos/70 intacta/downgrade protegido | PASS | §23 |
| 37 | Hash estable/aislamiento writers | PASS | §14/21 |
| 38 | Release conserva historia | PASS | §16 |
| 39 | Invalidate antes/después freeze | PASS | §16/tests |
| 40 | Auditoría/log mínimos | PASS | §4/log test |
| 41 | Check indexado/medición | PASS | §22/24 |
| 42 | IDOR/tenant/SQL/revocación/races | PASS | §17/20 |
| 43 | Documentación y gobernanza | PASS | §2 |
| 44 | Autoauditoría completa | PASS | §27 |

## 27. Autoauditoría

| Pregunta | Respuesta | Motivo |
|---|---|---|
| 1. ¿T0 usa MAX(id)? | No | Clock aware tras gate/control |
| 2. ¿TX durante scan entero? | No | Páginas/aggregate con TX propia; freeze breve |
| 3. ¿Writer anterior confirma tras T0 y queda fuera? | No | Gate hasta commit/rollback, open espera |
| 4. ¿Writer posterior muta fuente? | No | Guard en su TX |
| 5. ¿Capture salta fence? | No | Guard común/cinco procesos |
| 6. ¿EE live directo salta fence? | No | Antes de savepoint/contador |
| 7. ¿SQL relevante soportado salta fence? | No | 29 tablas/tres acciones/snapshot test |
| 8. ¿Otro business queda fenced/bloqueado lógicamente? | No | Tenant estricto; SQLite puede contender brevemente por archivo |
| 9. ¿Dos epochs activos? | No | Unique parcial + gate |
| 10. ¿Crash libera? | No | No cleanup release |
| 11. ¿TTL libera? | No | Solo atención |
| 12. ¿Diagnostic se promueve por UPDATE? | No | CHECK70 + carrier nuevo |
| 13. ¿Certifiable implica importable? | No | eligible=false por CHECK |
| 14. ¿Release conserva falsamente boundary_current? | No | Revocación atómica, hashes conservados |
| 15. ¿Prepared/Approved previo ejecuta? | No | Guard anterior a operación/efectos |
| 16. ¿EE histórico creado? | No | Sin append histórico/importer |
| 17. ¿v2 histórico durable? | No | Contratos/event storage sin ampliación |
| 18. ¿1.9D iniciada? | No | Sin backfill/reconciliación/activación |

Resultados circunscritos a código/QA sintética local y CI. La siguiente unidad
requiere orden humana; este cierre no concede autorización de activación.

CI inicial1.9C bloqueada en secrets por SHA público completo heredado de adendaB;
se usa identificador corto del mismo commit y conserva URL verificable. Sin cambiar
baseline ni filtros de secrets. Runtime/tests/workflow/dependencias intactos.

Medición CI de100 checks: SQLite3.329ms/PG51.205ms; datos sintéticos, sin SLO
de producción. Todos los apartados del cierre y autoauditoría completados.
