# Informe de cierre — exclusivamente Fase 1.4

Estado: **cerrada — 17 PASS / 0 FAIL**. No avanzar a 1.5.

## Entrega y mapa

[Mapa exhaustivo previo al código](FASE-1.4-writers-audit.md): emisión ordinaria,
simplificada, rectificativa y recurrente; registro/outbox; cobro parcial/completo/
bancario; recibidas manuales/documentales/corrección/baja; gastos manuales/tickets/
baja; banco import/suggest/match/ignore; anulación fiscal/outbox y llamadas
alternativas. Conexiones, BEGIN/commit, locks, tablas y efectos por camino.

[Patrón definitivo](BORROWED-WRITERS-v1.md) y [ADR-008](ADR-008-borrowed-writers.md).
Un núcleo de mutación extraído por dominio; fachada pública compatible con
transacción propia; Connection/FinancialSession prestada con commit exterior.
Sin segunda conexión, commit/rollback, IA ni red en los helpers de mutación.
Las observaciones de producto existentes siguen después del commit.

## Archivos

- Nuevos: `src/noesis/financial_writers/{__init__,boundary,readers,invoices,payments,
  purchasing,bank,documents,recurring,schema}.py`, `src/noesis/core/locks.py`.
- Modificados: `db.py`, `core/persistence.py`, `banking.py`, `documents/repo.py`,
  `documents/service.py`, `economic_events/service.py`, `migrations.py`.
- Pruebas: contrato compartido, SQLite, PostgreSQL, proceso worker, escenario
  fiscal y fixture Python golden de main anterior; ajustes de versión en pruebas 1.3.
- CI: gate PostgreSQL de writers. Documentación: AGENTS, ADR-008, API/mapa/cierre,
  índice/plan, guías 01/03/04/07/08, arquitectura/mapa/decisiones, estado/tareas,
  project-state, registro de cambios y QA.

## Migración, resultados y precisión

64: solo `_financial_revision` en received_invoices, expenses, bank_transactions,
triggers/guards para versión monotónica. Nada de tablas/enlaces/eventos nuevos.
No migrar dinero legacy. Campo oculto en resultados públicos; disponible en
lectura exacta. 63→64→63→64 conserva valores. Baja protegida con evidencia.

`WriterResult` y `SourceSnapshot` congelados: IDs/tenant/tipo/revisión/huella,
importes Decimal, filas congeladas, líneas, registro/perfil fiscal, documentos/
clasificación, snapshots de cobro/padre y payment_id bancario recién creado.
Entrada exacta capturada antes de adaptar; parámetros Decimal preservados.
Los importes de efecto derivan de la fila real en la transacción y declaran
`legacy_binary_storage`: REAL/DOUBLE no devuelve precisión histórica perdida.

API pública conserva float y redondeos antiguos. Writer exacto rechaza float,
moneda ajena, importes inválidos, aplica HALF_UP y contexto independiente. La
diferencia 2.675 de base opcional recibida está explícita: público 2.67; exacto
2.68. No hay efecto público nuevo ni migración de importes históricos.

## Revisiones y locks

Invoice: huella de identidad/header congelado/líneas, excluye estado de cobro.
Payment y cancellation: huella de fila real. Mutable: contador de BD, también
para SQL alternativo, inicial representa el estado observado desde 64. Revisión
antigua se rechaza bajo lock antes de mutar. Reader tenant/sesión real; fuente
ausente/eliminada no obtiene revisión inventada. Huella completa conservada y
proyección positiva de 60 bits +1 para el contrato entero v1.

Orden por ramas: permisos/operación → gate transaccional por negocio → schedule/
run o banco antes de invoice/origen → serie/secuencia → cadena business/NIF →
secundarios → incorporación futura EE. El gate es común con append antes de
contador y evita inversión origen/contador. Ver ADR para precondiciones y coste.

VERI*FACTU: solamente lock común de cadena y acceso prestado/lock invoice al
anular. Numeración, freeze, registro/outbox, huellas, XML y QR conservados.
Cero AEAT dentro del writer; no otras correcciones fiscales.

## Pruebas y comparación

- Suite general: **1484/1484 OK**, 1029,546 s. Primera pasada: 1481 y tres
  fallos (dos expectativas antiguas de schema63 y formato literal SQLSTATE);
  corregidos y suite repetida. No fallos finales ni skips sustitutivos.
- SQLite específicos: **12/12 OK**, 10,205 s; regresiones iniciales backend/
  VERI*FACTU 99/99 y recibidas/fundamentos 40/40. Revalidación de dinero que
  cierra a cero, matriz y recibidas tras el último ajuste: **36/36**, 33,504 s.
- PostgreSQL 16.15 real, esquemas locales aislados: **83/83 OK**, 18,715 s
  (18 writers, 27 eventos, 32 operaciones, 6 fundamentos). Revalidación del
  último ajuste de dinero: **18/18**, 8,245 s. Conexiones y procesos separados;
  una emisión, sin sobrecobro, seis facturas/dos series en cadena única sin forks,
  inversión contador/origen serializada y locks liberados tras rollback.
- Migraciones: SQLite 0→64→0→64; ambas BD prueban 63→64→63→64 y valores
  preservados. Humo PostgreSQL histórico 32→64, **36 rutas** sin 5xx;
  rollback/re-upgrade, privacidad, exportación, deduplicación/conversación y
  separación de métricas existentes correctos.
- Ruff, Bandit, pip-audit sin vulnerabilidades conocidas, uv lock --check,
  secretos (incluidos nuevos archivos), Node **3/3**, verdad documental,
  enlaces y git diff --check correctos. Excepciones de secretos son solo NIF y
  huellas de la fixture sintética fiscal, anotadas puntualmente; sin cambiar baseline.
- Servidor SQLite local: /health, /ready, / y /login HTTP200; PG HTTP autenticado
  en humo. Sin AEAT, banco externo, Meta ni evaluación de despliegue remoto.

La suite completa y la revalidación dirigida posterior se distinguen: el último
ajuste solo endurece la validación del writer exacto para importes que redondean
a cero; la fachada legacy conserva su conducta. Su contrato completo de writers
se repitió en ambos motores y las regresiones documentales relacionadas pasaron.

Matriz de veinte caminos: writer exitoso + fallo exterior deja todas las tablas
como antes; writer + marcador comparten commit. Durante el writer se prohíbe
db.get_conn para detectar llamadas indirectas. Pagos/banco comparten inserción;
recurrente usa el motor normal y documentos incluyen proveedor/clasificación.
Composición con FinancialOperations confirma efecto + resultado durable; fallo
conserva autorización y revierte efecto/resultado; replay no vuelve a ejecutar.

Golden capturado de main 6b4c144/schema63 con reloj fijo: respuestas completas,
registros, hashes, QR y XML F1/F2/R1–R5 exactamente iguales. IVA 21/10/4/0, varias
líneas e IRPF. Tests específicos de fallo después de registro fiscal revierten
factura/número/perfil/registro/outbox/auditoría. No se recalculan históricos.

## Criterios de aceptación

| Criterio solicitado | Estado / evidencia |
|---|---|
| 1. Auditoría previa completa | PASS — mapa antes de extracción |
| 2. Writer prestado único, sin duplicar motor | PASS — fachadas delegan en núcleo extraído |
| 3. Commit exterior y ausencia de segunda conexión | PASS — matriz de veinte caminos, monkeypatch get_conn, rollback |
| 4. API pública compatible | PASS — regresiones y golden anterior |
| 5. Frontera Decimal y procedencia histórica | PASS — exact_inputs/prepared_values y snapshot real etiquetado |
| 6. Snapshot en misma transacción | PASS — filas congeladas y rollback antes de salir |
| 7. Reader real para seis fuentes y stale reject | PASS — BD mutable, huella inmutable, pruebas ambos motores |
| 8. Orden de locks e inversión PostgreSQL | PASS — gate común, test contador/origen, multiserie |
| 9. VERI*FACTU acotado y sin I/O | PASS — golden y chain común sin forks |
| 10. Banco conserva payment_id solo interno | PASS — pago/movimiento/result en misma transacción; sin columna durable |
| 11. Recurrente composable, motor normal | PASS — una transacción por vencimiento, rollback sin huérfano nuevo |
| 12. Action review/canales intactos; integración futura posible | PASS — composición sintética con servicio 1.2; ningún canal conectado |
| 13. Migración mínima | PASS — tres revisiones, sin productores/backlinks/activación |
| 14. Commit/rollback/compatibilidad/concurrencia/dinero | PASS — contrato SQLite/PG y procesos independientes |
| 15. F1/F2/R1–R5, IVA/IRPF/series/huella/rollback | PASS — casos específicos/golden/carreras |
| 16. Prohibiciones y flags | PASS — sin productores/ledger/reporting/históricos ni flags activados |
| 17. Autoauditoría y cierre documental | PASS — ambas autoauditorías, suite/gates y gobernanza actualizadas |

## Autoauditoría de la orden (12 respuestas)

1. ¿Helper hace commit/rollback? No; solo propietario db.get_conn. Los helpers
   nuevos de mutación no usan savepoint ni finalizan la transacción.
2. ¿Segunda conexión? No; veinte caminos probados con get_conn prohibido dentro.
3. ¿API legacy elude locks? No; todas las APIs extraídas pasan por gate y locks.
   SQL arbitrario externo queda fuera del protocolo, pero triggers revisionan.
4. ¿Lógica duplicada? No en mutación; cuerpos anteriores se extraen y las fachadas
   delegan. Recurrente y banco reutilizan creación/emisión/inserción comunes.
5. ¿Snapshot difiere del efecto? Describe fila real en TX; entrada/preparación
   separadas permiten ver redondeo legacy. Baja conserva explícitamente el antes.
6. ¿Exacto pasa por float antes de snapshot? Entradas y parámetros Decimal se
   capturan antes del adaptador. Lecturas de REAL/DOUBLE y redondeo público legacy
   se declaran binarios; no se presentan como exactitud histórica recuperada.
7. ¿Revisiones detectan stale? Sí bajo lock, incluidos cambios SQL en mutables.
8. ¿Orden definido? Sí; ADR-008 y tests reales de ramas/inversión.
9. ¿Rollback exterior revierte todo? Sí; matriz, fiscal y operación durable.
10. ¿VERI*FACTU igual? Respuestas/registros/SHA/XML/QR iguales a referencia. Lock
    común elimina forks entre series; no se declara aceptación externa AEAT.
11. ¿Productor accidental? No; tests sintéticos y consulta de tablas/flags.
12. ¿1.5+ adelantada? No; sin enlace durable bancario ni conservación de voids,
    GL/Open Items/Tax Ledger/posting/reporting/históricos/activación.

## Master Plan §44 (12 respuestas)

1. Economic Event: ninguno emitido en 1.4; futuros once tipos del catálogo v1
   siguen separados de quote.accepted/job.completed.
2. Asiento: ninguno. 3. Cuentas: ninguna. 4. TaxLines: ninguna.
5. OpenItems: ninguno. 6. Dimensiones: tenant/origen/identidad existentes,
   sin nuevo modelo dimensional.
7. Permisos: fachada/canales existentes; servicio 1.2 mantiene autorización
   durable y request aprobado. Writer interno no confiere permisos ni autoridad IA.
8. Reversibilidad: rollback completo antes de commit; posteriores correcciones
   financieras siguen sus APIs existentes. No borrar evidencia fiscal emitida.
9. Idempotencia: emisión/cobro restante/banco/cancellation/recurrente conservan
   sus controles; 1.2 puede guardar resultado en mismo commit. Alta manual legacy
   no adquiere idempotencia nueva por inferencia.
10. Periodo cerrado: no existe implementación de periodo/cierre nueva; no se
    afirma garantía futura y no se implementa posting.
11. Auditoría: mapa previo, ADR, revisión/huella/procedencia, registros existentes
    y bitácora/QA; sin Economic Event nuevo.
12. Prueba: contrato dos motores, commits/rollbacks, concurrencia/procesos,
    golden fiscal, regresiones/gates y migraciones aisladas.

## Riesgos y pendientes delimitados

- Dinero legacy permanece binario; la frontera no inventa precisión anterior.
- Gate por negocio reduce paralelismo de escritores dentro de un negocio;
  protocolo requiere READ COMMITTED y una operación/negocio por transacción.
- Proyección de huella a revisión entera tiene riesgo criptográfico residual;
  fingerprint completo permite comparación estricta futura.
- Bajas físicas necesitan conservación del origen antes de conectar voids (1.7).
- Pago bancario recién creado conocido, replay anterior no conserva ID (1.6).
- No reparar huérfanos históricos ni reconstruir autorizaciones/aprobación.
- Mezclar réplicas/escritores anteriores que no participan en el gate no prueba
  el protocolo nuevo; coordinar despliegue/rollback sin esa mezcla.
- Gaps fiscales ajenos al lock común, aceptación AEAT, CI remota y despliegue
  requieren evidencia independiente; el push no los acredita.

Rollback: revertir código manteniendo 64 es compatible con fachada anterior;
64→63 solo sin evidencia mutable. No resetear revisiones con eventos ya durables.
Mantener flags apagados. No avanzar a 1.5.
