# Fase 1.8H — Informe de cierre de B1–B5

**CI REMOTA PENDIENTE — HARDENING NO CERRADO.**

Fases 0–1.8 implementadas; solo hardening autorizado. Cinco flags OFF;
**Fase 1.9 no iniciada ni autorizada**. Arquitectura y contratos en
[ADR-013](ADR-013-financial-hardening.md); [orden humana](FASE-1.8H-orden.md).

## 1. Diagnóstico inicial

Sobre main posterior a 1.8 (`89537f0`), la auditoría confirmó B1–B5: DELETE
permitido cancelado silenciosamente en PG; inversión operación/negocio; origen
recurrente omitible por canal; lectura COMMITTED bloqueada tras renovar sesión;
CI completa 37069839865 FAIL en secretos con pasos generales omitidos. PostgreSQL
verde y workflows de producción no acreditaban una CI completa verde.
Esta entrega corrige esos defects; no reescribe los cierres anteriores.

## 2. Archivos creados/modificados

Código: siete archivos de Operations, EE, Channels/recurring, payment schema,
migrations y router web. Tests: cuatro archivos de contratos compartidos,
carreras PG y gate de secretos. Baseline: un único fingerprint nuevo.
Gobernanza: orden, ADR-013, este cierre, AGENTS, foto/QA/bitácora/mapa/decisiones,
guías y adendas de contratos/ADR afectados. Inventario del commit de implementación:

- `.secrets.baseline`
- `AGENTS.md`
- `docs/Arquitectura.md`
- `docs/Decisiones.md`
- `docs/Estado-actual-main.md`
- `docs/Mapa-codigo.md`
- `docs/Registro-QA.md`
- `docs/Registro-cambios.md`
- `docs/Tareas-vivas.md`
- `docs/architecture/ADR-008-borrowed-writers.md`
- `docs/architecture/ADR-009-invoice-capture.md`
- `docs/architecture/ADR-010-payment-bank-capture.md`
- `docs/architecture/ADR-012-financial-channels.md`
- `docs/architecture/ADR-013-financial-hardening.md`
- `docs/architecture/BORROWED-WRITERS-v1.md`
- `docs/architecture/ECONOMIC-PERSISTENCE-v1.md`
- `docs/architecture/FASE-1-plan.md`
- `docs/architecture/FASE-1.8H-cierre.md`
- `docs/architecture/FASE-1.8H-orden.md`
- `docs/architecture/FINANCIAL-CHANNELS-v1.md`
- `docs/architecture/FINANCIAL-OPERATIONS-v1.md`
- `docs/architecture/INVOICE-CAPTURE-v1.md`
- `docs/architecture/PAYMENT-BANK-CAPTURE-v1.md`
- `docs/architecture/PURCHASING-CAPTURE-v1.md`
- `docs/architecture/README.md`
- `docs/areas/01-vision-general.md`
- `docs/areas/03-cerebro.md`
- `docs/areas/08-financial-core.md`
- `docs/project-state.json`
- `src/noesis/economic_events/service.py`
- `src/noesis/financial_channels/recurring.py`
- `src/noesis/financial_channels/service.py`
- `src/noesis/financial_operations/service.py`
- `src/noesis/migrations.py`
- `src/noesis/payment_capture/schema.py`
- `src/noesis/web/routers/financial_actions.py`
- `tests/financial_channels_contract.py`
- `tests/payment_bank_capture_contract.py`
- `tests/postgres_financial_channels.py`
- `tests/test_secrets_gate.py`

## 3. Migración nueva

**69: reparacion_delete_cobros_postgres** sobre main 68. CREATE OR REPLACE de las
funciones BEFORE DELETE de 66, con condiciones originales. SQLite no altera DDL
de negocio; solo avanza versión. No cambia datos económicos/coberturas.
Fresh install y 68→69 con función defectuosa instalada probados. Bajar69 conserva
la reparación compatible, no reinstala el defecto; el ciclo completo retira las
funciones mediante 66 solo cuando no hay evidencia. Downgrades protegidos intactos.

## 4. B1 — DELETE

DELETE permitido devuelve OLD; INSERT/UPDATE devuelven NEW. Payment no capturado
se borra en SQLite y PG con RETURNING comprobado. Capturado: DELETE y UPDATE
siguen rechazados. Comparación de todas las filas de evidencia antes/después de
upgrade; cobertura intacta tras intentos rechazados. Sin API pública nueva.

## 5. B2 — Estrategia de locks

Frontera común FinancialOperations._transaction: permisos → business gate →
repositorio/operación/autorización → fuentes. Incluye prepare/reprepare,
authorize/execute y lecturas con FOR UPDATE. EconomicEvents.append toma el gate
antes del savepoint y de bloquear operación/contador. Writers/recurrentes mantienen
el mismo gate prestado antes de fuentes/run/plantilla. Sin tablas de lock,
conexiones adicionales ni aislamiento global nuevo. Rollback libera locks.

## 6. B3 — Recurrencia común

propose consulta el run real para invoice.issue/rectify usando FinancialSession
prestada; valida schedule/run/template y canoniza schedule/vencimiento.
transport_identity y recibos review conservan el transporte original; el contexto
se congela y se revalida en preparación y aprobación/ejecución. Web ya no aplica
una regla separada. Chat real/tools y handle_inbound WhatsApp usan la misma frontera.
Run sin hash, pausa, plantilla cambiada y TTL caducado fallan cerrado. Una propuesta
ordinaria antigua sin contexto para un run real no puede aprobarse.
Web/chat/WhatsApp convergen en una operación para el mismo creador/sesión y
mantienen recibos separados. Pending de cada conversación referencia esa propuesta.
Otros creadores/sesiones no adquieren autoridad. Revisión ≠ aprobación; no mandato.

## 7. B4 — Recuperación

response recarga la operación real por tenant/created_by con permiso de lectura
actual. Solo COMMITTED permite omitir actor/canal/sv históricos. GET web consulta
sin writer ni nueva autorización; conserva resultado y filas históricas exactas.
Sesión revocada, otro usuario/negocio y PREPARED/APPROVED con nueva sesión siguen
rechazados. confirm/execute conservan sus controles de autoridad.

## 8. B5 — Baseline exacta

Única entrada añadida: docs/project-state.json + Hex High Entropy String + SHA1
`505913cd627cb75bfcfd157ef75b5768be5b7d57` del SHA público original de Fase 0, valor conservado en JSON.
La configuración de plugins/filtros/detectores no cambia. Sin exclusión de archivo
ni regex amplia. La copia documental de la orden referencia el campo original en
vez de duplicar el literal. Test de fingerprint/configuración y gate completo PASS.

## 9. SQLite final

**247 tests PASS (243.420 s)**: Money/Core, contratos, Operations,
Economic Persistence, Borrowed Writers, InvoiceCapture, Payment/BankCapture,
PurchasingCapture, FinancialChannels y secretos. Canales: 47 casos; pagos/banco32.
Casos nuevos B1/B3/B4 incluidos. Dinero inválido/float/redondeo y legacy incluidos.
Después del último ajuste del fixture y sin cambios posteriores de código/baseline.

## 10. PostgreSQL real final

**245 tests PASS (130.752 s)** sobre PG16 local /noesis_ci,
esquemas descartables, nunca producción. Core6, Operations32, Persistence27,
Writers18, Invoice27, Payment/Bank41, Purchasing44, Channels50.
Migraciones históricas 32→69 con factura emitida; rollback aislado
69→55→54→53→54→55→69, datos/inmutabilidad conservados. Conversación, privacidad,
copias/restauración y 36 rutas calientes correctas. Código base53 sobre schema69:
cliente/factura/emisión/cobro/exportación correctos. SQLite 0→69→0→69 correcto y
HTTP health/ready/portada/login200. Upgrade68→69 y guards con evidencia probados.

## 11. Carreras

Tres nuevas carreras de conexiones PostgreSQL con barreras y contención advisory
real: reprepare/authorize misma operación, operaciones distintas del negocio y
rollback de authorize. La preparación no entra en repo.prepare mientras el otro
posee el gate. Sin deadlock, una autorización/efecto/evento, recuperación idempotente
y gate disponible tras rollback/commit. Además se conservan carreras previas de
procesos para emisión, cobro, banco, compras, canales, recurring/retry/crash.

## 12. Suite general completa

**1626 tests PASS (1367.374 s)** con unittest discover test_*.py.
Completada después del último cambio de código/tests/baseline. No se usa como
evidencia la primera ejecución general detenida tras ajustar el fixture. Una matriz
PG intermedia falló por reutilización de teléfono entre negocios; el fixture usa
ahora teléfono único y la matriz final completa245 pasa. Un test intermedio de B4
tenía un patch de writer mal nombrado; corregido y todas las matrices finales pasan.

## 13. Gates

PASS: Ruff src/tests; Bandit high/high CI; pip-audit sin vulnerabilidades conocidas
de dependencias (proyecto local Noesis fuera de PyPI); uv lock --check; secretos
sobre todos los archivos staged; verdad documental; enlaces añadidos; diff/check
y gobernanza. Node: **9 PASS**. Sin dependencias nuevas. Cierres1.1–1.8 intactos.

## 14. GitHub Actions

**PENDIENTE**: aún sin push/CI del candidato; no cerrar B5 ni hardening.

## 15. Riesgos restantes y rollback

Gate serializa también consultas con FOR UPDATE dentro del negocio; no cubre
transacciones multinegocio ni SQL ajeno al protocolo. Legacy REAL/DOUBLE conserva
procedencia binaria, no se recupera precisión histórica. Runs sin huella,
ended/drift/TTL, delegación y renovación de propuestas siguen bloqueados.
Pending huérfano por adjuntos WhatsApp permanece como deuda menor fuera de B1–B5.
Audio durable, UI de lotes, anulación fiscal runtime, exportación/retención,
históricos/backfill, activación, GL/OpenItems/Tax esperan nuevas órdenes.
Meta/AEAT reales y activación de cuentas no se certifican con tests o CI.
Rollback conserva reparación/schema/evidencia; no bajar coberturas/enlaces con
datos ni volver al código defectuoso como solución de autoridad. Diagnóstico:
business/op/request/hash/auth/receipt/state/source, sin reejecutar writers ni
fabricar identidades/autorizaciones nuevas.

## 16. PASS/FAIL individual

| Blocker | Resultado | Evidencia |
|---|---|---|
| B1 | PASS | DELETE paritario, guards y upgrade/fresh ambos motores |
| B2 | PASS | Gate común y tres carreras PG deterministas |
| B3 | PASS | Tres canales reales, origen inválido/TTL, identidad única |
| B4 | PASS | Lectura vigente, histórico intacto, cero writer, Web/bridge |
| B5 | FAIL — CI pendiente | Suite/gates locales PASS; falta CI completa remota |

## 17. Autoauditoría explícita

| Nº | Pregunta | Respuesta |
|---|---|---|
| 1 | DELETE no capturado igual PG/SQLite | SÍ, RETURNING confirma borrado |
| 2 | DELETE capturado bloqueado | SÍ, UPDATE también; evidencia intacta |
| 3 | BD que pasó66 reparada | SÍ, 68→69 reemplaza función vieja instalada |
| 4 | Gate antes de operation/source | SÍ, frontera común y append; workflows capturados |
| 5 | Carrera prepare/authorize puede deadlock | NO en la inversión auditada; tres intercalados reales pasan |
| 6 | Chat/Tools/WA tratan recurrente como ordinaria | NO; run real resuelto común y contexto revalidado |
| 7 | Dos canales dos operaciones para ocurrencia | NO; unique de EntryIdentity recurrente y recibos separados |
| 8 | COMMITTED recuperable sesión nueva mismo creador | SÍ, lectura actual Web/bridge, resultado exacto |
| 9 | Sesión antigua revocada recupera | NO, _permission vigente la rechaza |
| 10 | Autorización histórica reescrita | NO; igualdad de filas originales comprobada |
| 11 | detect-secrets rebajado | NO, excepción exacta y plugins/filtros intactos |
| 12 | Suite general después del último cambio | SÍ, 1626 completos tras código/tests/baseline final |
| 13 | CI remota completa verde | PENDIENTE: no hay aún CI completa del candidato; B5 abierto. |
| 14 | Fase1.9 iniciada accidentalmente | NO; flags OFF y alcance restringido |

Master Plan §44: 1) ningún EE/tipo/productor nuevo; 2) ningún asiento;
3) ninguna cuenta; 4) ninguna TaxLine; 5) ningún OpenItem;
6) dimensiones business/origen/documento/actor/canal/vencimiento existentes;
7) permisos vigentes, creador y autorización exacta; 8) reparación aditiva y
evidencia conservada, reversos/void de Capture previos sin cambios;
9) identidad/recibos/op/result idempotentes; 10) períodos no implementados,
sin garantía contable futura; 11) trazabilidad anterior intacta y bitácora nueva;
12) matrices SQLite/PG, carreras, suite general, migraciones y gates anteriores.
