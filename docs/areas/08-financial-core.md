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
    → futuro repositorio(business_id, FinancialSession(conn))
      → conn.execute_exact() → NUMERIC/Decimal sin normalización legacy
```

## Archivos y reglas

- `core/money.py`: importe canónico y precisión; [ADR-004](../architecture/ADR-004-money-decimal.md).
- `core/persistence.py`: conexión prestada, sin commit/rollback/cierre propio.
- `db.py`: fachada legacy e infraestructura común; no nuevos motores financieros.
- `accounting/__init__.py`: reserva, sin ledger ni posting.
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

Fase 0 solamente: sin tablas nuevas, migración, nuevas operaciones financieras ni
cambios funcionales de VERI*FACTU. No convertir lecturas antiguas a Decimal de forma
global. SQLite nuevo: dinero TEXT y cálculo Decimal; no aritmética SQL sobre TEXT.

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
