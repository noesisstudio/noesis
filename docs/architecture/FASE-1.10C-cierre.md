# Fase 1.10C — cierre técnico local

Fecha: 2026-10-06. Estado: **PASS — cierre técnico local; revisión/aceptación de C pendiente**.
Rama `codex/phase-1-10c`; padre exacto autorizado
`8eb18dbe0c3e97227ee46069fa65087005c39fc8`.
Commit local de entrega: el que incorpora este informe, consultable con
`git log -1 --format=%H -- docs/architecture/FASE-1.10C-cierre.md`.
Sin push/merge/deploy. Main intacto, sin producción/Noesis19FQA/backups reales.
A y B **CODE-VERIFIED PASS**, aceptadas por el titular. B CI final
[37446339192](https://github.com/noesisstudio/noesis/actions/runs/37446339192),
ambos jobs success sobre la base autorizada (corrección exclusivamente documental).
C no activa negocios; cinco flags OFF; **1.10D no iniciada**.

[Orden íntegra](FASE-1.10C-orden.md),
[contrato y mapping](FINANCIAL-CAPABILITIES-FISCAL-CANCELLATION-v1.md),
[ADR021](ADR-021-capabilities-fiscal-cancellation.md), [plan](FASE-1.10-plan.md).

## Entrega

Registry/spec v1 sobre el único Enum Capability de A, quince capacidades, mapping
cerrado de once CommandType. Desconocidos/versiones extra fallan cerrado;
dependencia bloqueada bloquea al consumidor, not_applicable no concede grant.
No enforcement productivo; D deberá revalidar grants tenant/generación. A mantiene
formato/hashes/evaluaciones anteriores; prueba bytes antes75/después76 y retry
misma evaluación. Producer fiscal local disponible, resto de blockers intactos.

API interna FiscalCancellationCapture review/prepare/authorize/execute sobre
Operations/FinancialSession/gate/TX compartidos. Request cerrado no monetario,
EUR/None, invoice y revisión exactos, reason5–1000, diez refs/hashes en parameters.
Durable B live/verified/resolved de propósito fiscal_cancel_invoice exacto,
verify_resolution en cada uso nuevo, auth humana exacta, alta aceptada local y
cadena íntegra; ningún mandate, histórico u observed_state operativo.

Writer fiscal existente reutilizado sin modificar algoritmos. Snapshot real de
cancellation_record, UUIDv5 de operación/nombre cerrado y slot primary.
Migration76 aditiva: coverage tenant-scoped, FKs compound/diferidas e inmutabilidad.
Guards exigen op APPROVED/auth humana/B/record/outbox/request exactos, EE compatible
y result COMMITTED exacto. Tabla/EE/op vinculados atómicamente al resultado.

EE existente fiscal_cancellation_registered v1, amount=None, original_total del
Decimal de invoice EE original verificado, JSON string exacto, fecha fiscal real.
evidence_for exacto a invoice.issued/rectified original. Outbox pendiente0, sin
dispatch. No reducción de deuda, modificación monetaria de invoice, cobros, banco,
recibidas/gastos, B/history/readiness/control/flags/GL/reporting.

Misma identidad y request conservan operación; execute COMMITTED recupera el
resultado original sin efecto nuevo incluso tras pérdida de respuesta. Otra
operación o anulación legacy se bloquean, sin adopción. Recover confirmado no
revalida ausencia de anulación: no ejecuta un efecto pendiente.

## Archivos y cambios acotados

- Nuevos: financial_activation/capabilities.py; fiscal_cancellation_capture/
  {__init__,service,schema}.py; tests/fiscal_cancellation_contract.py,
  test_financial_capabilities.py, test_fiscal_cancellation_capture.py,
  test_fiscal_cancellation_migrations.py, postgres_fiscal_cancellation_capture.py,
  fiscal_cancellation_worker.py; orden/contrato/ADR/cierre C.
- Código existente: migrations.py solo wrappers/entrada76; matrices explícitas
  A/B/history añaden76; evaluator solo disponibilidad local del producer fiscal;
  db.py solo inventario/conservación de la coverage, con comprobación de existencia
  sobre la misma conexión para conservar compatibilidad con schema75.
- Tests de Operations/EE/borrowed writer usan schema75 explícito para fixtures de
  infraestructura que COMMITan efectos ficticios fiscal_cancel sin Capture. Sus
  contratos originales se conservan; C real en76 prueba guard de COMMIT obligatorio.
  Fixtures compartidas no desactivan guards. test_financial_history usa latest76.
- La regresión de InvoiceCapture ahora usa un PaymentCapture realmente COMMITTED
  para probar rechazo de replay de otro comando; no confirmación fiscal ficticia.
  Los tests de downgrade comparan contra la versión inicial de su fixture, no
  contra LATEST_VERSION, y siguen exigiendo rollback sin pérdida.
- CI añade matriz PostgreSQL C después de B, sin ejecutar CI remota ni dispatch.
  AGENTS, guía08/01/04/06, arquitectura/mapa/decisiones, plan/A/B, estado/tareas,
  bitácora/QA/project-state actualizados en la misma entrega.

### Inventario exacto de archivos de la entrega

49 archivos creados/modificados:

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
docs/architecture/ADR-021-capabilities-fiscal-cancellation.md
docs/architecture/FASE-1.10-plan.md
docs/architecture/FASE-1.10C-cierre.md
docs/architecture/FASE-1.10C-orden.md
docs/architecture/FINANCIAL-ANTECEDENTS-v1.md
docs/architecture/FINANCIAL-CAPABILITIES-FISCAL-CANCELLATION-v1.md
docs/architecture/FINANCIAL-READINESS-v1.md
docs/architecture/README.md
docs/areas/01-vision-general.md
docs/areas/04-facturas.md
docs/areas/06-rgpd-y-seguridad.md
docs/areas/08-financial-core.md
docs/project-state.json
src/noesis/db.py
src/noesis/financial_activation/capabilities.py
src/noesis/financial_activation/contracts.py
src/noesis/financial_activation/evaluator.py
src/noesis/financial_antecedents/contracts.py
src/noesis/financial_history/schema_compatibility.py
src/noesis/fiscal_cancellation_capture/__init__.py
src/noesis/fiscal_cancellation_capture/schema.py
src/noesis/fiscal_cancellation_capture/service.py
src/noesis/migrations.py
tests/borrowed_writers_contract.py
tests/economic_persistence_contract.py
tests/financial_operations_contract.py
tests/fiscal_cancellation_contract.py
tests/fiscal_cancellation_worker.py
tests/invoice_capture_contract.py
tests/postgres_borrowed_writers.py
tests/postgres_economic_persistence.py
tests/postgres_financial_operations.py
tests/postgres_fiscal_cancellation_capture.py
tests/test_borrowed_writers.py
tests/test_economic_persistence.py
tests/test_financial_capabilities.py
tests/test_financial_history.py
tests/test_financial_operations.py
tests/test_fiscal_cancellation_capture.py
tests/test_fiscal_cancellation_migrations.py
```

## Evidencia de pruebas

| Matriz / gate | Resultado |
|---|---|
| C SQLite + registry + migration | PASS: 44, 105.505s, código final |
| C PostgreSQL, conexiones y procesos | PASS: 46, 76.050s, código final |
| Regresiones PG A/B/history/captures/Operations | PASS: 475, 478.483s (total PG521 incluyendo C) |
| Suite completa | PASS: 1919, 856.985s, cero fallos/errores, 2 skips existentes |
| JavaScript exigido por workflow | PASS: 9 |
| Ruff / Bandit umbral CI | PASS |
| pip-audit | PASS: sin vulnerabilidades conocidas; paquete local no publicado omitido |
| Credential scan, verdad, enlaces, AST | PASS: sin secretos nuevos, 1389 enlaces/0 rotos, AST1–75 y20 archivos protegidos |
| SQLite76→75→76 y76→0→76 | PASS |
| PostgreSQL76→75→76 aislado | PASS |
| PostgreSQL migración histórica / HTTP / legacy / release | PASS: 36 rutas, código53 sobre76, privacidad/rollback y backup sintético |

Python3.12.3, SQLite3.45.1, PostgreSQL16.15 efímero loopback/noesis_ci y esquemas
sintéticos aleatorios. Ningún dato real. Linux/Python3.13 y CI remota C no ejecutados
(orden de entrega local, sin push). Snapshot hash de todas las tablas incluidas
las resoluciones B; solo se excluyen los efectos contractuales de execute.

Positivos invoice emitida + payment capturado intacto, aceptado/aceptado_con_errores,
rectificativa positiva, precisión100.05/121.06 bajo contexto Decimal prec2;
revisión real no1, payload/hash/relation/resultado exactos, idempotencia y snapshots.
Negativos: draft/historical v2/observed/stale/purpose/tenant/sesión/mandate,
requests/hash/float/moneda/fields/reason, registro ausente/corrupto/cadena corrupta,
alta pendiente/rechazada/sinoutbox, anulación legacy/nueva previa y SQL falsificado.
Inyección SQL coverage de once campos, EE origen/source/revisión/amount/op/slot,
payload/links incompatibles y result falsificado; rollback de TODO el estado.
COMMIT genérico sin cobertura, UPDATE/DELETE y downgrade con evidencia abortan.

PG: dos conexiones misma/distinta operación, anulación contra rectificación,
source/config drift tras business gate, progreso de otro tenant, sin deadlocks.
Dos procesos misma operación conservan un único record/result. Terminación real
os._exit antes del writer, después de record/outbox/coverage/EE y antes del resultado:
rollback total/APPROVED conservado. Después de commit: recovery exacto sin duplicado.
SQLite y PG prueban seis puntos de excepción y pérdida de respuesta postcommit.
Provider HTTP/submit_records se parchean para fallar si se invocan; cero llamadas.

La corrida secuencial inicial detectó un único fallo de reconocimiento literal
del SQLSTATE en el gate estático: ERRCODE sin los espacios esperados. Se
alineó exclusivamente el formato del SQL generado por76 (mismo código23514,
sin cambiar semántica ni tests). Los tres tests de ese gate pasan. La suite
final se repartió por índice entre cuatro procesos con DB/docs/backups
temporales independientes; cada uno descubre todos los casos y ejecuta su
partición exacta. La suma coincide con discover, cero exclusiones y cero
deduplicación. Resultados de cada shard en project-state.json.

## Decisiones, riesgos y límites

No desviación de alcance/arquitectura aprobados. Se elige human_confirmation
exclusiva y amount=None, tal como la preferencia conservadora autorizada.
Registry implemented no equivale a permiso/grant ni preflight; canales/proveedores
no son productores de EE propios. No se conecta a ningún cliente legacy.

B conserva PAYMENT_HISTORY_INCOMPLETE en rectificativas negativas para este
propósito. C las bloquea; no se amplía B ni se simula una prueba suficiente.
Factura histórica v2, observed_state y operaciones con mandate insuficiente
siguen bloqueados. NIF/modo, cadena completa/outbox/config y fecha exactos son
precondiciones conservadoras: requieren nueva revisión si cambian. Se validan
solo AEAT statuses sintéticos locales, no aceptación externa real.

Guards SQL son defensa estructural junto al servicio verificador; no afirman
resistencia frente a administrador que desactive triggers o falsee toda prueba.
Datos/bases sintéticos y logs fuera de Git; cluster sintético detenido al terminar QA.
Downgrade76 pierde cero evidencia; si existe C, se conserva/repara sin borrar
records/outbox/results. No restore para deshacer fiscalidad real. Privacy/export,
continuidad completa y activación/providers siguen pendientes de sus fases.

## Criterios PASS/FAIL

| Criterio | Resultado |
|---|---|
| Catálogo único cerrado, versiones/mapping/dependencias compatibles A | PASS |
| Ningún CommandType sin mapping ni not_applicable como grant | PASS |
| Producer con Operations, B revalidada y autoridad humana exacta | PASS |
| Writer fiscal existente y snapshot real | PASS |
| Records/outbox/coverage/EE/result atómicos y guards en ambos motores | PASS |
| Evidence-only, amount None, original_total exacto sin reversión | PASS |
| Recovery/idempotencia/concurrencia/crash | PASS |
| Snapshots de efectos excluidos y cero provider I/O | PASS |
| Sin activación/flags/handoff/routing/D | PASS |
| Suite/regresiones/gates/documentación completos | PASS |

## Autoauditoría explícita

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿Puede C activar un business? | NO |
| 2 | ¿Puede pasar a ready/enabled/paused? | NO |
| 3 | ¿Puede incrementar activation_generation? | NO |
| 4 | ¿Puede liberar/handoff fence? | NO |
| 5 | ¿Puede cambiar los cinco flags? | NO |
| 6 | ¿Puede llamar AEAT? | NO |
| 7 | ¿Puede hacer cualquier provider I/O? | NO |
| 8 | ¿Puede fiscal cancellation generar un amount económico? | NO |
| 9 | ¿Puede reducir deuda? | NO |
| 10 | ¿Puede borrar/alterar cobros? | NO |
| 11 | ¿Puede modificar invoice original económicamente? | NO |
| 12 | ¿Puede adoptar una cancellation legacy como live? | NO |
| 13 | ¿Puede cancelar una invoice historical unsupported? | NO |
| 14 | ¿Puede usar observed_state operativamente? | NO |
| 15 | ¿Puede usar resolution stale? | NO |
| 16 | ¿Puede saltarse human confirmation? | NO |
| 17 | ¿Puede un segundo operation adoptar el mismo cancellation record? | NO |
| 18 | ¿Puede un CommandType quedar sin capability mapping? | NO |
| 19 | ¿Puede not_applicable interpretarse como capability granted? | NO |
| 20 | ¿Se inició 1.10D? | NO |
