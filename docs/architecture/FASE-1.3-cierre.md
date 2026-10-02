# Fase 1.3 — Persistencia de Economic Events

Fecha: 2-oct-2026. Orden expresa posterior a aceptación de 1.2. Base main
`ca79797`, schema real 62, limpio/actualizado antes de editar; siguiente versión 63.
Trabajo en `C:/Users/mikic/Documents/noesis`; el worktree del chat era anterior.
**1.3 cerrada: 41 PASS / 0 FAIL; suite general 1472/1472 OK.**
No avanzar a 1.4. Esta entrega no conecta ningún productor ni activa flags.

## 1. Archivos creados/modificados

Nuevos: economic_events/{schema,repository,service,persistence}.py;
tests/{economic_persistence_contract,test_economic_persistence,postgres_economic_persistence,economic_events_worker}.py;
architecture/{ADR-007-economic-persistence,ECONOMIC-PERSISTENCE-v1,FASE-1.3-cierre}.md.

Runtime existente: economic_events/__init__.py solo descripción; migrations.py
registra 63 y abre transacción de downgrade; db.py solo extiende mantenimiento
de baja vacía/conservación. financial_operations_contract.py conserva los tests
de 1.2 sobre LATEST_VERSION y comprueba presencia/conservación de nuevas tablas.
CI añade gate PostgreSQL. AGENTS, arquitectura/índice/plan/ADR-002/contratos,
guías 01/06/08, mapa, decisiones, estado, pendientes, JSON, QA y bitácora.
No cambian contratos puros 1.1, Money, operaciones, config ni dependencias.
Inventario completo de esta unidad (33 archivos) al final de este informe.

## 2–4. Migración, schema, constraints e invariantes

[Schema/API completos](ECONOMIC-PERSISTENCE-v1.md), [ADR-007](ADR-007-economic-persistence.md).
Migración única 63 sobre 62: economic_events, economic_event_links y contador
economic_event_sequences. No migra datos financieros ni ejecuta backfill.

Evento: tenant/ID técnico/UUID/secuencia; catálogo/versión; operación/slot/key;
fuente/revisión y seis FK concretas excluyentes; fechas conocidas/desconocidas
y procedencia; EUR/amount; autorización; live/historical/batch; JSON canónico
inmutable/hash de 1.1 más record_hash; recorded_at. Sin status ni accounting_date.

FKs compuestas reales a invoices, invoice_payments, received_invoices, expenses,
bank_transactions, invoice_cancellation_records. CHECK exige exactamente el
origen compatible y mismo ID. Operación/autorización/links incluyen business_id.
No cascadas que borren hechos. UNIQUEs protegen UUID, sequence, op+slot, key y
source+revision+event_type. Compatibilidad/amount/fecha/links se comprueban en BD
y contrato/servicio; triggers impiden mutar/borrar events y links.

Rollback de 63 vacío permitido; con eventos/links bloquea antes de DROP. Si
62 bloquea por operaciones, también se restaura DDL de 63 gracias al BEGIN
exterior. Baja de negocio con evidencia bloqueada antes de borrar fuentes.
Sin evidencia mantiene comportamiento anterior. Exportación/cierre/retención
de esta evidencia siguen pendientes antes de productores/activación.

## 5. Repositorio/API interna

EventsRepository(FinancialSession, business_id): lock_business, next_sequence,
find/load/links, insert_link/insert. SQL por negocio; no conexión, autorización,
commit/rollback, proveedores o IA. EconomicEvents(session, business_id).append/read
devuelve StoredEvent congelado. Valida permisos de 1.2, live autorizado/historical
explícito, fuente real, revisión mediante lector de servidor obligatorio, targets,
identidades y hashes. No sabe emitir, cobrar, calcular IVA, contabilizar o conciliar.
No exportar esta API a modelos/rutas/herramientas antes de sus fases autorizadas.

## 6. Secuencia e idempotencia

Contador por negocio, creado en cero con INSERT ON CONFLICT. PostgreSQL lock de
fila + UPDATE last_sequence+1 RETURNING, misma transacción; SQLite transacción
exterior de escritura. No MAX+1. Secuencia representa incorporación, no fecha
económica, número fiscal ni orden contable. Replay recupera la original sin
incrementar; conflicto rechaza cambios relevantes. Dos slots pueden coexistir
en una operación; no se implementa su productor. UUID estable del contrato se
conserva en reintentos, no se vuelve a generar.

## 7. Inmutabilidad y lectura

Triggers BEFORE UPDATE/DELETE de ambas tablas. Links preinsertados en la misma
transacción con source FK diferida, target existente inmediato; el insert de
evento exige el conjunto completo del catálogo/JSON. Al incorporarlo quedan
sellados; no se pueden añadir/editar después. CTE correctiva evita ciclos, no
hay graph framework. Una corrección futura es otro hecho, nunca estado reversed.

Al leer, contrato/canonical bytes/content_hash/payload/columnas/amount/fechas,
record_hash y links reales deben coincidir. Rechaza incoherencias sin reparación.
record_hash cubre metadatos durables sin alterar hashes aprobados en 1.1.

## 8–11. Pruebas SQLite, PostgreSQL, concurrencia y rollback

- SQLite: **26/26** nuevos, 18,695 s; incluye instalación limpia en cada test,
  actualización/bajada vacía con fuentes preservadas, ciclo 0→63→0→63, rechazo
  sin transacción exterior y rollback exterior de append ya devuelto.
- PostgreSQL 16.15 real local: **65/65**, 12,396 s = 27 eventos (24 contrato
  compartido + 3 concurrencia), 32 operaciones de 1.2 y 6 fundamentos de Fase 0.
  Esquemas aislados descartables, instalación limpia y ciclo 62→63→62→63.
- Concurrencia: ocho incorporaciones por cuatro conexiones → secuencias 1..8;
  dos procesos/UUID idéntico → un hecho/misma secuencia; dos procesos/mismo slot
  distinto contenido → uno acepta/otro conflicto; distintos comandos → secuencias
  distintas. Ningún duplicado. Los negocios mantienen contadores independientes.
- Fallo inyectado después de reservar contador, insertar link e insertar evento;
  error capturado dentro de la transacción y commit posterior → cero parcial y
  secuencia no consumida. Mismo contrato probado en ambos motores.
- FKs/SQL directo: sources, operación, autorización y links de otro negocio;
  updates de UUID/payload/importe/fechas/source/hash y deletes; links incompatibles,
  ausentes, duplicados, self y ciclos; contador reset/borrado. Todos rechazados.
- Once tipos, NULL distinto de cero, máximo Decimal exacto, JSON string, fechas,
  versiones/tipos/floats/hash inválidos y lectura alterada sin reparación.
- Regresión completa: **1472/1472 OK**, 1053,797 s, incluye facturas/cobros,
  VERI*FACTU, banco, recibidas/gastos, documentos, WhatsApp/chat, Fase 0/1.1/1.2
  y nuevos tests SQLite. Se preserva comportamiento legacy y flags apagados.
- Humo PostgreSQL: datos sintéticos históricos 32→63, 36 rutas sin 5xx, código
  anterior d3740a0 emite/cobra/exporta sobre schema63, rollback/re-upgrade conserva
  datos, gates de privacidad/aislamiento/conversación/dedup/marketing correctos.
- Ruff, Bandit, secretos incluidos nuevos archivos, pip-audit, uv lock --check,
  Node 3/3, enlaces, verdad documental y diff correctos. Sin dependencia nueva.
  uv para QA se instaló solo en carpeta temporal al no estar en PATH; no altera
  entorno del producto, pyproject ni lock. Resultados durables en QA/JSON.

Incidencias de verificación: fixture fiscal requería configuración del productor
durante la activación (sin IO AEAT); ajustado el fixture. La prueba de downgrade
vacío PostgreSQL compartía datos durables de otras pruebas y fue correctamente
bloqueada; ahora usa esquema propio. No se relajó ninguna garantía de producto.
El escáner de secretos señaló dos NIF sintéticos por alta entropía: anotaciones
ajustadas en constantes de fixture, sin ampliar baseline. Revalidación dirigida
de catálogo/migración SQLite: 2/2 (2,015 s); cambio sin semántica de producto.
Catálogo de once tipos PostgreSQL revalidado tras esa anotación: 1/1 (2,005 s).
Todos los datos son sintéticos/locales; no se leen/copian históricos reales.

## 12. Riesgos conocidos

- No conectar sin definir revisiones/locks/loaders reales y proyección de la
  operación aprobada al snapshot. 1.2/1.3 protegen autoridad estructural; reglas
  específicas de cada productor esperan su fase, no se infieren aquí.
- SQLite exige transacción exterior; PG serializa incorporaciones de cada negocio.
  Resolver orden de locks con escritores legacy antes de los puentes; no hay
  benchmark productivo ni se promete throughput.
- Retención/exportación/cierre con evidencia son gates pendientes antes de uso
  real. La baja se bloquea conservando datos, no los elimina silenciosamente.
- SHA-256 detecta incoherencia, no es firma ni defensa contra superusuario que
  retire triggers. Lectura no repara. Reintento conserva UUID/observación originales.
- No se ha validado aceptación AEAT, Meta real, CI remota o despliegue de 1.3.
  Flags permanecen apagados, ningún productor importado, ninguna acción financiera.

## 13. Precisiones respecto al diseño aprobado

- event_id del contrato se guarda como event_uuid; no cambia la canonicalización.
  UUID estable lo aporta el llamador confiable; se asignan ID técnico/key/secuencia.
- Tres tablas: contador mínimo autorizado de única responsabilidad, sin activación.
- NUMERIC sin typmod + CHECK de rango/céntimos evita redondeo implícito de typmod.
- record_hash adicional conserva íntegro content_hash de 1.1 y cubre metadatos.
- Catálogo de seis relaciones, incluido settles aprobado en 1.1; la lista del
  encargo era ejemplificativa. Conjunto sellado con FK diferida para proteger SQLite.
- revision_reader obligatorio porque legacy no tiene revisión financiera uniforme;
  no añade revisiones, puentes ni productores de 1.4.
- BEGIN exterior de downgrade y ajuste mínimo de baja para conservar evidencia.
  Ninguna ampliación funcional; sin cambios de fases, contratos o tipos económicos.

## 14. Criterios PASS/FAIL

Dictamen final: **41 PASS / 0 FAIL**. Las garantías críticas pasan en ambos motores.

| # | Criterio | Resultado / evidencia |
|---|---|---|
| 1 | Once tipos válidos, catálogo intacto | PASS — contrato compartido |
| 2 | Tipo/versión/payload/hash inválidos | PASS — rechazo sin fila |
| 3 | Operativos y supplier_payment.made rechazados | PASS — contratos 1.1 intactos |
| 4 | Sobre durable con todos los metadatos pedidos | PASS — schema/StoredEvent |
| 5 | Seis sources con FKs reales tipadas | PASS — DDL y SQL directo |
| 6 | Sources compatibles y mismo business_id | PASS — CHECK/FKs y tests reales |
| 7 | Sources sin cascada que borre eventos | PASS — delete de fuente bloqueado |
| 8 | Operation/authorization/links mismo negocio | PASS — FKs compuestas |
| 9 | Live con autorización vigente requerida | PASS — actor/sesión/estado/mandato |
| 10 | Historical/batch/procedencia sin aprobación inventada | PASS — tests de metadata |
| 11 | API sin update/delete | PASS — repositorio/servicio |
| 12 | UPDATE identidad/payload/importe/fechas/source/hash | PASS — triggers ambos motores |
| 13 | DELETE rechazado en ambos motores | PASS — SQL directo |
| 14 | Relaciones de catálogo cerrado (seis) | PASS — 1.1 y DDL |
| 15 | Targets existentes y mismo negocio | PASS — FKs/servicio |
| 16 | Sin self ni duplicados | PASS — CHECK/PK/guard |
| 17 | Links compatibles y revisiones correctivas | PASS — validación/guard |
| 18 | Ciclos correctivos rechazados | PASS — CTE/test |
| 19 | Links inmutables/conjunto completo sellado | PASS — preinsert/guard/triggers |
| 20 | Secuencia concurrente PostgreSQL sin duplicados | PASS — conexiones/procesos |
| 21 | Secuencias monotónicas/independientes por negocio | PASS — contador transaccional |
| 22 | UUID único | PASS — uniques/replay/conflicto |
| 23 | Operación+slot único, varios slots permitidos | PASS — two-event fixture |
| 24 | Key/source+revision sin duplicados accidentales | PASS — uniques/lookup |
| 25 | Replay original/conflicto de contenido | PASS — hash+metadata/seq original |
| 26 | Canonicalización y lectura coherente sin reparar | PASS — lectura alterada rechazada |
| 27 | PostgreSQL NUMERIC exacto, sin float/redondeo | PASS — roundtrip/guard |
| 28 | SQLite TEXT canónico, ningún REAL nuevo | PASS — roundtrip/DDL |
| 29 | Amount concuerda con payload; NULL ≠ 0 | PASS — guard/test catálogo |
| 30 | Fecha económica/precisión; sin accounting_date | PASS — schema/roundtrip |
| 31 | Repositorio prestado sin permisos/commit/rollback | PASS — revisión de imports/API |
| 32 | Servicio acotado sin lógica ERP/IA/proveedores | PASS — código/alcance |
| 33 | Fallos tras contador/link/evento, aun capturados | PASS — SAVEPOINT ambos motores |
| 34 | Rollback exterior conserva atomicidad | PASS — tests de transacción prestada |
| 35 | Migración siguiente real/instalación limpia | PASS — main62→63, dos motores |
| 36 | Upgrade vigente/con datos legacy conservados | PASS — roundtrip y humo histórico |
| 37 | Downgrade vacío/lleno conservador | PASS — ciclo/protección/multistep |
| 38 | Solo hechos válidos, sin posted/reversed/failed | PASS — schema sin estado |
| 39 | Fases 0/1.1/1.2 y suite legacy relacionadas | PASS — 1472/1472 y humos PostgreSQL |
| 40 | Cero productores/flags/fiscalidad/backfill/fases futuras | PASS — diff/imports y tests |
| 41 | Documentación/gates/autoauditoría | PASS — Ruff/security/truth/enlaces/Node, 23 preguntas |

## Autoauditoría específica (11 preguntas)

1. ¿Puede modificarse un evento después? No: triggers y ninguna API de mutación.
2. ¿Puede borrarse? No: trigger DELETE y downgrade/baja protegidos con evidencia.
3. ¿Puede apuntar a otra empresa? No: FKs compuestas, CHECK y validación vigente.
4. ¿Dos conexiones obtienen misma secuencia? No: lock de contador/uniques; carreras reales.
5. ¿Se duplica por retry? No: identidades únicas; replay original o conflicto.
6. ¿Live sin autorización? No: CHECK/FK/guard y actor/sesión/mandato validados.
   Historical sin operación se admite explícitamente, sin fingir aprobación.
7. ¿Amount distinto al payload? No: derivado por catálogo y corroborado por guard.
8. ¿FK source distinta de source_type? No: exactamente una FK compatible e ID igual.
9. ¿Rollback consume secuencia/deja parcial? No: SAVEPOINT/fila transaccional,
   también con error capturado. La PK técnica BIGSERIAL puede tener huecos.
10. ¿Lógica contable accidental? No: sin ledger/cuentas/impuestos/posting/reporting.
11. ¿Algún productor importa el servicio? No: búsqueda/imports/diff; solo tests.

## Autoauditoría Master Plan §44 (12 preguntas)

1. Economic Event: persiste exclusivamente los once hechos aprobados, sin producirlos.
2. Asiento: ninguno; impacto futuro es declarativo del contrato 1.1.
3. Cuentas: ninguna; plan contable no implementado.
4. TaxLines: ninguna, tampoco recálculo fiscal.
5. OpenItems: ninguno; settles es relación declarativa, no aplicación de cobro.
6. Dimensiones: solo campos ya aprobados; no motor nuevo de dimensiones.
7. Permisos: usuario/tenant/sesión/creador vigentes, escritura permitida, autorización
   durable live; receipt histórico explícito no autoriza ejecución real.
8. Reversibilidad: hecho inmutable, corrección posterior enlazada; rollback de
   infraestructura solo vacío, conservación obligatoria con evidencia.
9. Idempotencia: UUID/op+slot/key/source+revision+tipo; replay/conflicto real probado.
10. Período cerrado: no posting/accounting_date/períodos nuevos; registro de hecho
    no decide contabilidad ni permite saltar reglas de cierre futuras.
11. Auditoría: sobre/payload/fechas/procedencia/revisión/operación/autorización,
    content_hash+record_hash, secuencia y links; lectura estricta sin reparación.
12. Pruebas: contrato común en dos motores, SQL directo, carreras de conexiones/
    procesos, fallos transaccionales, migraciones, regresiones y gates.

No se cierra Fase 1 completa, no se comienza 1.4 ni se conectan productores.

## Inventario completo

```text
.github/workflows/ci.yml
AGENTS.md
docs/Arquitectura.md
docs/Decisiones.md
docs/Estado-actual-main.md
docs/Mapa-codigo.md
docs/Registro-QA.md
docs/Registro-cambios.md
docs/Tareas-vivas.md
docs/architecture/ADR-002-economic-events.md
docs/architecture/ADR-007-economic-persistence.md
docs/architecture/ECONOMIC-EVENTS-v1.md
docs/architecture/ECONOMIC-PERSISTENCE-v1.md
docs/architecture/FASE-1-plan.md
docs/architecture/FASE-1.3-cierre.md
docs/architecture/FINANCIAL-OPERATIONS-v1.md
docs/architecture/README.md
docs/areas/01-vision-general.md
docs/areas/06-rgpd-y-seguridad.md
docs/areas/08-financial-core.md
docs/project-state.json
src/noesis/db.py
src/noesis/economic_events/__init__.py
src/noesis/economic_events/persistence.py
src/noesis/economic_events/repository.py
src/noesis/economic_events/schema.py
src/noesis/economic_events/service.py
src/noesis/migrations.py
tests/economic_events_worker.py
tests/economic_persistence_contract.py
tests/financial_operations_contract.py
tests/postgres_economic_persistence.py
tests/test_economic_persistence.py
```
