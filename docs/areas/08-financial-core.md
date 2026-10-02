# 08 · Financial Core

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
