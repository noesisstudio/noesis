# 08 · Financial Core

## 2026-10-07 — F CODE-VERIFIED PASS técnico local

[Orden F](../architecture/FASE-1.10F-orden.md), [ADR024](../architecture/ADR-024-providers-integrated-preflight.md), [contrato](../architecture/FINANCIAL-PROVIDERS-PREFLIGHT-v1.md), [cierre](../architecture/FASE-1.10F-cierre.md). Registry único C; FinancialSession/gate/TX compartidos, sin lógica financiera grande en db.py. Attestations/preflight/attempts separados de autoridad/economía. HMAC de secretos, ninguna red en A/D. Post-handoff con binding explícito; UNKNOWN sin retry automático, pausa/cierre dominan. D sigue protegido en producción, cinco flags OFF y policy real provisional. Sólo fixtures sintéticos; sin push ni G–H.


## 2026-10-07 — Fase 1.10E local, CODE-VERIFIED PASS técnico

[Orden E](../architecture/FASE-1.10E-orden.md), [contrato](../architecture/FINANCIAL-PRIVACY-EXPORT-RETENTION-v1.md),
[ADR023](../architecture/ADR-023-financial-privacy-export-retention.md), [cierre](../architecture/FASE-1.10E-cierre.md).
financial_privacy es dominio del monolito modular sobre FinancialSession/gate/TX compartidos. Decimal exacto; binary legacy como evidencia. Ninguna autoridad IA ni nueva lógica grande en db.py.
Migration78 aditiva, catálogo cerrado y snapshot completo sin límites silenciosos.
Policy provisional no permite activación; revisión profesional real pendiente.
Readiness nuevo sólo retira los dos motivos E con evidencia válida; A antigua intacta.
Export/client/cierre conserva EE/Operations/history/A–D y documentos. Restore requiere
registro vigente y reaplica antes de servir. E no borra bytes ni consulta QA/backups reales.
Cinco flags OFF. No push/merge/deploy/providers/F–H. Resultados finales en cierre E.

## 2026-10-06 — Fase 1.10D, cierre local CODE-VERIFIED PASS

A/B/C CODE-VERIFIED PASS según la orden del titular.
[Orden D](../architecture/FASE-1.10D-orden.md), [contrato](../architecture/FINANCIAL-ACTIVATION-HANDOFF-v1.md),
[ADR022](../architecture/ADR-022-activation-handoff-generations.md) y [cierre](../architecture/FASE-1.10D-cierre.md)
son la continuación vigente; los encabezados posteriores son históricos.
D se trabaja únicamente en `codex/phase-1-10d`, sin push, merge ni despliegue.
La migración candidata es aditiva respecto de las fuentes; las CHECK de lifecycle
se amplían conservando las FKs y la evidencia histórica. Activación por tenant,
generaciones, grants exactos y contexto ligado a operación/TX; Decimal/EUR,
repositorios de dominio y conexión/gate/TX compartidos. Ninguna autoridad IA.
Después de ever_enabled, flag OFF o pause no permite fallback financiero legacy.
Pausa cancela operaciones pendientes y revoca mandatos; resume exige prueba D
sin drift y otra generación. El corte mantiene certifiable al quedar handed_off.
Borradores y preparación operativa siguen permitidos; transporte outbox se conserva.
No nuevos endpoints ni cambios de UI; el control plane es interno.
E/F/G/H no iniciadas; blockers de privacidad/export/provider siguen vigentes en A.
Cinco flags OFF. Sin producción, restauración real, backups ni providers.
D CODE-VERIFIED PASS local: criterios, resultados iniciales y retests se detallan
en el informe de cierre enlazado. E/F/G/H no autorizadas ni iniciadas.


## 2026-10-06 — Alcance C: registry y anulación fiscal interna

[Orden](../architecture/FASE-1.10C-orden.md), [contrato](../architecture/FINANCIAL-CAPABILITIES-FISCAL-CANCELLATION-v1.md), [ADR021](../architecture/ADR-021-capabilities-fiscal-cancellation.md), [cierre](../architecture/FASE-1.10C-cierre.md).

Zona nueva: src/noesis/financial_activation/capabilities.py y
src/noesis/fiscal_cancellation_capture/{service,schema}.py. A/B CODE-VERIFIED PASS.
Monolito modular y repositorios especializados sobre FinancialSession/gate/TX
compartidos. Registry único de A con spec v1 y once mappings cerrados, sin
enforcement/routing. FiscalCancellationCapture interno reutiliza writer fiscal:
resolución B durable live/verified/resolved, revalidación every_use, autoridad
humana exacta, registro/outbox pendiente/coverage/EE evidence-only/result atómicos.
Decimal/EUR, total contextual del EE verificado, amount=None, snapshot real.
No nueva lógica grande en db.py ni autoridad IA. Migration76 aditiva protegida;
tuplas explícitas A/B/history. No provider I/O, activación, generation, handoff,
fence release o cambios de cinco flags OFF. Historical v2, observed_state,
mandates y rectificativas negativas bloqueadas por B se conservan.
No routing público ni 1.10D–H. Solo fixtures sintéticos, no producción/QA real/backups.
Revisar callbacks prestados, hashes/request, source revision, FKs/guards,
exact money, SQL adversarial, rollback/recovery, ausencia de provider I/O y snapshots.
La conservación de coverage impide baja destructiva del negocio; no hay nuevo
tratamiento/export/privacy productivo aún. Límites completos en contrato/cierre.

## 2026-10-06 — Fase 1.10B: antecedentes, no autoridad

[Orden](../architecture/FASE-1.10B-orden.md), [ADR020](../architecture/ADR-020-financial-antecedents.md), [contrato](../architecture/FINANCIAL-ANTECEDENTS-v1.md), [cierre](../architecture/FASE-1.10B-cierre.md).

Zona: `src/noesis/financial_antecedents/{contracts,proofs,resolver,repository,schema}.py`.
Solo B en rama dedicada, no C–H; encabezados inferiores históricos. Monolito
modular, repositorio especializado, infraestructura compartida de conexión/TX/gate.
Resolver/check solo SELECT; persistir exclusivamente tabla B. Revalidar cada uso.
Referencia fuerte y FK por business; propósito cerrado, origen historical/live,
calidad verified_fact/observed_state sin promoción. Historical exige importación
original y E PASS durable; live exige operación/auth/coverage/links exactos.
No normalización legacy para conceder certeza: Decimal/NUMERIC y JSON string,
NULL/binary desconocidos conservados; no saldo desde status/registro_anterior.
Factura histórica v2 bloqueada, bank match solo evidencia. IA sin autoridad.

Comprobar UUID/contexto/idempotencia/rollback/stale, SQL inmutable/estructural,
tenant uniforme, dependencias faltantes/extra, cobertura exhaustiva de cobros,
proof histórica y live positivas reales sintéticas, unknowns, precisión, snapshots
de todas las tablas anteriores/flags, PG concurrencia y migración aditiva.
Sin routing, provider I/O, EE/Operations, activación/generation/fence ni 1.10C.

## 2026-10-05 — Fase 1.10A: evaluación sin activación

[Orden](../architecture/FASE-1.10A-orden.md), [contrato](../architecture/FINANCIAL-READINESS-v1.md), [ADR019](../architecture/ADR-019-financial-readiness.md), [cierre](../architecture/FASE-1.10A-cierre.md), [plan](../architecture/FASE-1.10-plan.md).

Zona nueva: `src/noesis/financial_activation/{contracts,evaluator,repository,schema}.py`.
Solo contratos y evaluación; schema aditivo consultable en project-state.json.
Mantener monolito modular, repositories por dominio, conexión/gate/TX compartidos,
Decimal/NUMERIC e IA sin autoridad. Evaluator solo SELECT de fuentes y writes en
sus tres tablas, nunca Capture/EE/Operations/E/release/provider ni routing.

Probar perfil exacto/cierre, razón cerrada y not_applicable con prueba fiscal,
caducidad, idempotencia/hash sin UUID/reloj propios, tenant/usuario actual,
boundary/source drift/E vigente, C/D transversales, SQL inmutable/anti-enabled,
cinco flags OFF, rollback y snapshots de todas las tablas previas. B/C/D/E usan
matriz explícita compatible: no >=73. FULL mínimo web vacío no habilita dinero.
PARTIAL nunca ready. Privacidad/export/providers/continuidad pendientes bloquean.
1.9 técnicamente cerrada con límites; 1.9F conserva PASS WITH LIMITATIONS.

## 2026-10-05 — Fase1.9F: PASS WITH LIMITATIONS, solo QA

[Orden](../architecture/FASE-1.9F-orden.md), [cierre](../architecture/FASE-1.9F-cierre.md) y [runbook](../architecture/FASE-1.9F-runbook.md).

1.9F ejecutó contratos existentes B/C/D/E en copia aislada. Decimal/NUMERIC, dinero binario solo evidencia raw; IA sin autoridad. C certificable no equivale a importable. No nuevos repositorios/conexiones/reglas; legacy inalterado. Informes con counts/hashes/seudónimos y límites de cobertura; no1.9G/1.10.

## 2026-10-05 — Fase1.9E: reconciliación histórica implementada y validada

[Orden](../architecture/FASE-1.9E-orden.md), [ADR018](../architecture/ADR-018-financial-history-reconciliation.md),
[contrato](../architecture/FINANCIAL-HISTORY-RECONCILIATION-v1.md), [informe](../architecture/FASE-1.9E-cierre.md).
Solo audita por identidad; writes exclusivamente run/findings propios. TX/gate y
conexión compartidos, repositorio especializado, Decimal/NUMERIC, IA sin autoridad.
B/C/D siguen inmutables; unknown/B/NULL conservados. PASS no libera fence, activa
flags ni acredita producción. Cinco flags OFF. Sin1.9F ni activación. Validación
local y CI final PASS; cierre técnico1.9E registrado. Encabezados inferiores históricos.

## 2026-10-05 — Fase1.9D: importer histórico (implementada y validada)

Solo incorporación de candidatos congelados de C vigente. Flags OFF; no1.9E,
reconciliación, activación, continuidad live ni producción.
[Orden](../architecture/FASE-1.9D-orden.md), [ADR017](../architecture/ADR-017-financial-history-import.md),
[contrato](../architecture/FINANCIAL-HISTORY-IMPORT-v1.md), [cierre](../architecture/FASE-1.9D-cierre.md).
Monolito modular; importer/repositorio especializados sobre conexión y TX
compartidas. Decimal/NUMERIC y JSON decimal string; IA sin autoridad.
Intent item-scoped con UUID/request/candidato exactos; fence permanece activo.
Operación histórica PREPARED y historical_unknown, actor/session NULL; resultado
en import_items, ninguna ejecución ni cobertura live65–67. Tres v2 históricos
durables cerrados; factura histórica v2 bloqueada. Nuevos inventarios reconocen
evidencia histórica existente sin promover B a A ni modificar batches anteriores.
Los encabezados inferiores conservan historia y no amplían autorización.


## 2026-10-04 — Fase1.9C: epoch/T0/fence (implementada y validada)

Únicamente corte consistente por negocio, control durable y nuevo sobre de
inventory certificable, siempre eligible_for_import=false. Schema71, flags OFF.
[ADR016](../architecture/ADR-016-financial-history-cutoff.md), [contrato](../architecture/FINANCIAL-HISTORY-CUTOFF-v1.md),
[writers previos](../architecture/FASE-1.9C-writers.md), [cierre](../architecture/FASE-1.9C-cierre.md).
SQL/application guard por tenant y TX prestada; no promoteB ni histórico EE/Operations/
v2/importer/reconciliación/activación.1.9D NO autorizada. Pruebas SQLite/PG sintéticas,
ninguna producción consultada. Invalidated conserva fence, release explícito pierde
boundary; TTL/crash no liberan. Encabezados inferiores conservan historia.


## Orden vigente — exclusivamente Fase1.9B

[ADR015](../architecture/ADR-015-financial-history-diagnostic-inventory.md) y [API](../architecture/FINANCIAL-HISTORY-INVENTORY-v1.md)
definen lector raw prestado, clasificador puro y repositorio/service de diagnóstico
sobre conexiones/TX existentes. Schema70 solo cuatro history_* con diagnostic/
eligible_for_import=false/certifiable=false por SQL. Decimal/NUMERIC/candidate JSON
string; bits/raw no Money. Freeze/plan inmutables, review append-only, operador
actual/session/tenant y historical.record sin receipts ni IA. Auxiliares no productores.
Comprobar SQLite/PG, precisión/procedencia, memberships/hash/retry/drift, coverage,
deps, tenant, permisos/inmutabilidad, memoria/páginas/lookups agrupados, snapshots
zero effects y AST. [Orden](../architecture/FASE-1.9B-orden.md), [fuentes](../architecture/FASE-1.9B-fuentes.md),
[cierre](../architecture/FASE-1.9B-cierre.md). Solo fixtures sintéticos; flags OFF.
No1.9C, T0/epoch/fence/write blocking/validating/live boundary, históricos EE/Operations,
importer/backfill/coverage/reconciliación/GL/Tax/AR/AP/reporting/activación.
Los encabezados y prohibiciones de unidades inferiores son históricos.

## Orden vigente — exclusivamente Fase 1.9A

financial_history/ contiene contracts/payloads/money_evidence/canonical puros,
sin DB. Frozen, catálogos/versiones cerrados, raw binary separado de exacto,
NULL distinto de cero; B distinto de verified_fact. Dependencias C/D/missing
bloquean; B padre también por prudencia. Importable no es autorización.
Historical namespace o receipt previo bloquean promoción/execute en Operations
y autoridad live en EE. Sin nuevos estados/migraciones; SQL directo no adquiere
efecto por ese metadato. Acceso ordinario no cambia.
[Orden](../architecture/FASE-1.9A-orden.md), [ADR-014](../architecture/ADR-014-financial-history-contracts.md),
[API/límites](../architecture/FINANCIAL-HISTORY-v1.md), [cierre](../architecture/FASE-1.9A-cierre.md).
Comprobar tests puros, regresiones compartidas SQLite/PG, bytes v1, emisión v2,
precisión/fechas/autoridad y gates completos. No reader real, manifest/importer,
fence/dry-run/reconciliación/activación ni1.9B; cinco flags OFF. V2 especiales
solo wrapper; candidatos emisiónv2 requieren raw por línea/fiscal, aún bloqueados.
Alcances inferiores históricos.

## Orden vigente — exclusivamente Fase 1.8H

Fases 0–1.8 implementadas; hardening 1.8H cerrado con B1–B5 PASS.
Único alcance de esta unidad cerrada:
DELETE PostgreSQL (migración de reparación), gate de negocio antes de operación/
fuente, recurrencia común en servidor, consulta COMMITTED con sesión renovada y
CI completa verde. Cinco flags OFF. No 1.9, backfill, activación ni nuevos eventos.
Leer [orden](../architecture/FASE-1.8H-orden.md), [ADR-013](../architecture/ADR-013-financial-hardening.md)
y [cierre/evidencia](../architecture/FASE-1.8H-cierre.md).
Los alcances y encabezados inferiores describen entregas históricas aunque digan
«vigente»; no amplían la orden actual. No reescribir los cierres anteriores.


## Orden vigente — exclusivamente Fase 1.8

Fases 1.1–1.7 aceptadas. Solo bridges autenticados de web, chat/tools,
WhatsApp, revisión documental y recurrentes hacia los cinco Capture existentes.
Identidad durable, request exacto, autorización humana antes de consumir pending,
ejecución idempotente y recuperación de respuesta. La IA solo propone.
Recurrentes: borrador + confirmación humana por vencimiento; auto_issue no es
mandato. CSV: revisión por fila, upload no autoriza. Cinco flags OFF. No 1.9,
activación, nuevos eventos, GL, Tax Ledger, Open Items ni cambios de VERI*FACTU.
Leer [orden](../architecture/FASE-1.8-orden.md), [inventario previo](../architecture/FASE-1.8-entrada-audit.md), [ADR-012](../architecture/ADR-012-financial-channels.md), [contrato de canales](../architecture/FINANCIAL-CHANNELS-v1.md) y [cierre](../architecture/FASE-1.8-cierre.md).
Las órdenes y cierres inferiores son históricos; no amplían esta autorización.


## Referencia histórica de Fase 1.7

1.1–1.6 aceptadas. SupplierInvoiceCapture/ExpenseCapture conectan solo
supplier_invoice.confirmed/corrected/voided y expense.confirmed/voided v1.
Writers compartidos, autorización durable, cobertura inmutable por revisión,
continuidad antes/después, logical void y guards SQL. Documento/clasificación/
source/EE/resultado comparten commit. Flags OFF; no1.8, históricos ni activación.
Pagada es etiqueta operativa, no supplier payment/AP settlement. No GL/Tax/
OpenItems/reporting nuevo. Legacy no capturado conserva comportamiento.
[Orden](../architecture/FASE-1.7-orden.md), [ADR-011](../architecture/ADR-011-purchasing-capture.md),
[API](../architecture/PURCHASING-CAPTURE-v1.md), [cierre](../architecture/FASE-1.7-cierre.md).
Las secciones inferiores describen entregas históricas; no son la orden vigente.

## Referencia histórica de Fase 1.6

Fases 1.1–1.5 aceptadas. Solo PaymentCapture y BankCapture: cobro real v1,
importación bancaria v1 y match v1 Evidence-only, sobre writers existentes.
Coberturas específicas, vínculo bank→payment, identidad cuenta/batch/fila,
aprobación durable y resultado en una transacción. Flags OFF. No avanzar 1.7.
[Orden](../architecture/FASE-1.6-orden.md), [ADR-010](../architecture/ADR-010-payment-bank-capture.md),
[API](../architecture/PAYMENT-BANK-CAPTURE-v1.md), [auditoría de entradas](../architecture/FASE-1.6-entrada-audit.md)
y [cierre](../architecture/FASE-1.6-cierre.md). Lo inferior conserva historia, no autoridad vigente.

## Referencia histórica de 1.5

Fases 1.1–1.4 aceptadas; solo emisión capturada F1/F2 y rectificativas R1–R5.
Servicio `invoice_capture/`: operaciones/aprobación durable + writer1.4 + evento
v2 + resultado en un commit. Migración65: cobertura inmutable con FKs diferidas;
v1/legacy/fiscalidad conservados. Flags apagados; otros productores y1.6 no autorizados.
[ADR-009](../architecture/ADR-009-invoice-capture.md), [API](../architecture/INVOICE-CAPTURE-v1.md),
[entradas auditadas](../architecture/FASE-1.5-entrada-audit.md). Los alcances inferiores son históricos.

## Qué hace

Fundamentos internos para evolucionar el producto a un monolito modular con
autoridad financiera determinista. Estado, alcance y órdenes futuras en
[architecture/README](../architecture/README.md); no asumir fases implementadas.

## Esquema

```text
Servicio propietario de la transacción
  → db.get_conn() (pool y commit/rollback existentes)
    → operación legacy con conn.execute()
    → repositorio(business_id, FinancialSession(conn))
      → conn.execute_exact() → NUMERIC/Decimal sin normalización legacy
```

## Archivos y reglas

- `core/money.py`: importe canónico y precisión; [ADR-004](../architecture/ADR-004-money-decimal.md).
- `core/persistence.py`: conexión prestada, sin commit/rollback/cierre propio.
- `financial_writers/`: un núcleo SQL por dominio, sin commit/rollback/conexión/IA/red.
  Fachadas públicas compatibles y propietario exterior; [API](../architecture/BORROWED-WRITERS-v1.md).
  [ADR-008](../architecture/ADR-008-borrowed-writers.md): orden de locks, revisiones
  monotónicas de BD y huellas inmutables, snapshot real y procedencia binaria legacy.
- `core/locks.py`: advisory transaccional por negocio y cadena fiscal, sin nueva tabla.
- `db.py`: fachada legacy e infraestructura común; no nuevos motores financieros.
  Baja: solo tablas financieras vacías; con evidencia rechazar antes de borrar.
- `accounting/__init__.py`: reserva, sin ledger ni posting.
- `economic_events/contracts.py`: catálogo cerrado v1, payloads/sobre inmutables,
  validaciones, dinero exacto y canonicalización sin efectos ni datos.
  [Especificación completa](../architecture/ECONOMIC-EVENTS-v1.md).
  No importar este módulo desde productores antes de otra autorización.
- `financial_operations/contracts.py`: Principal, EntryIdentity, FinancialRequest,
  clases de autorización, estados y resultados canónicos inmutables.
- `financial_operations/repository.py` y `service.py`: reserva atómica, acceso por
  negocio/creador/sesión, autorización durable, mandato exacto, ejecución compartida
  y recuperación sin repetir efecto. Sin productores registrados.
- `financial_operations/schema.py`: DDL/guards de migración 62, registrada en
  migrations.py; dos tablas de operaciones/autorizaciones.
- `economic_events/schema.py`: migración 63, events/links y contador mínimo;
  FKs reales a seis tipos de fuente, triggers de inmutabilidad y conjunto de
  relaciones sellado. Downgrade vacío; bloquear con evidencia durable.
- `economic_events/repository.py`: FinancialSession prestada, SQL por negocio,
  contador serializado; no permisos/conexión/commit/rollback propios.
- `economic_events/service.py`: append/read, autorización de 1.2, revisión de
  origen mediante lector confiable obligatorio, replay/conflicto, SAVEPOINT para
  revertir contador/evento/links aun si se captura el error dentro de la transacción.
  El llamador posee la transacción exterior; SQLite debe abrirla antes de append.
- `economic_events/persistence.py`: StoredEvent y verificación estricta al leer,
  content_hash v1 intacto + record_hash para metadatos durables. No reparar.
- [Persistencia v1](../architecture/ECONOMIC-PERSISTENCE-v1.md) y ADR-007 antes
  de tocar esta capa. Ningún productor puede importarla en 1.3.
- [Operaciones v1](../architecture/FINANCIAL-OPERATIONS-v1.md) y ADR-006 son la
  puerta de lectura antes de modificar esta infraestructura.
- `config.py` y `.env.example`: cinco flags reservados, apagados, sin consumidores.

Toda futura lectura/escritura de dominio exige business_id; las relaciones entre
entidades del negocio se protegen con claves compuestas. FinancialSession NO
infiere el tenant ni permisos. Rutas sin SQL; IA propone sin autoridad directa;
servicios y revisión humana deciden ejecución. No duplicar pools, transacciones,
pagos, motores fiscales ni conciliadores. PostgreSQL es la referencia productiva.

Eventos operativos como presupuesto aceptado y trabajo terminado no van
automáticamente a Economic Events. Una regla explícita puede producir después
una obligación/reconocimiento distinto, con evidencia. No construir un log o bus
genérico. Los registros fiscales/seguridad/producto conservan responsabilidades.

## Estado y pruebas

Fase 0 y 1.1–1.3 aceptadas; solo 1.4 autorizada. Writers prestados, snapshots
y revisiones reales preparados, sin productores. 1.5 no autorizada. VERI*FACTU
solo añade lock común de cadena, sin cambiar huellas, XML ni QR.
No convertir lecturas antiguas a Decimal de forma
global. SQLite nuevo: dinero TEXT y cálculo Decimal; no aritmética SQL sobre TEXT.

- `tests/test_financial_operations.py` y `financial_operations_contract.py`: mismo
  contrato de operación/autorización/rollback en SQLite y PostgreSQL.
- `tests/economic_persistence_contract.py` y `test_economic_persistence.py`:
  once tipos, SQL inmutable, FKs, replay/conflicto, hashes, rollback y migraciones.
- `python -m unittest tests.postgres_economic_persistence.EconomicPersistencePostgres`:
  mismo contrato y concurrencia real de conexiones/procesos; paso específico CI.
- `python -m tests.postgres_financial_operations`: concurrencia de conexiones y
  procesos, crash real; esquema aislado local /noesis_ci, conectado a CI.
- `tests/test_economic_events.py`: once tipos, versiones, campos cerrados, relaciones,
  fechas, Decimal y canonicalización/hash; no necesita SQLite ni PostgreSQL.
- `tests/test_financial_core.py`: Money, flags y contrato SQLite.
- `tests/financial_core_contract.py`: persistencia y transacción compartidas.
- `python -m tests.postgres_financial_core`: mismo contrato en PostgreSQL local
  descartable `/noesis_ci`, con esquemas aislados; conectado a CI.
- Regresiones existentes de facturas, cobros, documentos, fiscalidad y HTTP.

## Antes de cerrar una fase

- [ ] Orden explícita y alcance; leer fase, ADR, migraciones y código real.
- [ ] Ningún float canónico ni normalización legacy en el dominio nuevo.
- [ ] Misma conexión; fallo revierte también la operación original.
- [ ] Multiempresa e idempotencia probadas donde haya operaciones.
- [ ] Sin cambios ocultos de fiscalidad ni historia emitida.
- [ ] Tests PostgreSQL reales; no confundir mocks con aceptación AEAT.
- [ ] Estado, QA, bitácora, mapa y ADR actualizados; PASS/FAIL con límites.
- [ ] Detenerse: el siguiente número de fase no se autoriza automáticamente.

- Writers: `test_borrowed_writers`, contrato compartido y
  `postgres_borrowed_writers.BorrowedWritersPostgres`; commit/rollback de veinte
  caminos, dinero, revisiones, composición con 1.2, concurrencia y fixture fiscal.
