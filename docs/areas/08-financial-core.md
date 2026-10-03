# 08 · Financial Core

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
