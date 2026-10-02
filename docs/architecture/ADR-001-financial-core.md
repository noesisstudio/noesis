# ADR-001 · Financial Core en un monolito modular

- Estado: aceptado para Fase 0 por el titular (2-oct-2026).
- Alcance ejecutado: fundamentos; no contabilidad ni eventos económicos.

## Contexto

Noesis ya tiene facturación, documentos, cobros, conversación, permisos, colas,
migraciones SQLite/PostgreSQL y portales útiles. Los informes financieros aún
leen tablas operativas. Concentrar nuevos motores en `db.py` agravaría esa mezcla.

## Decisión

Una aplicación, una base de datos y transacciones locales. Los nuevos dominios
tendrán servicios deterministas y repositorios especializados. `db.py` mantiene
su fachada legacy y la infraestructura compartida de conexión/pool/transacción.
Queda prohibido añadir allí nuevos motores grandes de contabilidad, fiscalidad,
conciliación o tesorería. Se admiten puentes pequeños de transición.

El servicio propietario abre `db.get_conn()`. Dentro entrega
`FinancialSession(conn)` a los repositorios, junto con `business_id` obligatorio.
La vista usa `Connection.execute_exact` sin la normalización legacy. No confirma,
cierra, revierte ni abre conexiones. Los repositorios tampoco deben hacerlo.
El contexto exterior existente confirma o revierte todos los cambios juntos.

```python
with db.get_conn() as conn:
    session = FinancialSession(conn)
    # Futuro: operación legacy y repositorio de dominio en esta transacción.
    # Cada consulta del repositorio exige business_id y relaciones del mismo negocio.
```

La vista exacta no es un sistema de permisos ni un filtro SQL automático. El
aislamiento se impone en rutas, servicios, repositorios y claves compuestas de las
tablas futuras. Un proveedor nunca se llama dentro de la transacción económica.

La IA interpreta y propone; servidor, permisos, revisión humana y motor
determinista validan y ejecutan. No se permite LLM → SQL financiero, ni que el
modelo escoja empresa, permisos, tipos fiscales, numeración o saldos.

## Compatibilidad y activación

En Fase 0 los consumidores financieros actuales no usan la nueva vista. Su
`Connection.execute` conserva tipos y resultados actuales. No se migran tablas,
ni se cambia facturación, impuestos, PDF, bancos o VERI*FACTU.

Los cinco flags del Master Plan están definidos en config y `.env.example`,
todos `false`: FINANCIAL_CORE, LEDGER_REPORTING, OPEN_ITEMS, NEW_TAX_ENGINE y
NEW_BANK_RECONCILIATION (prefijo `NOESIS_`, sufijo `_ENABLED`). Son reservas sin
consumidores en esta fase: ponerlos a true no implementa capacidades ni las
certifica. Sus dependencias y gates se conectarán en sus fases autorizadas.

La comparación old/new será temporal y medible por flujo. Cuando se cambie una
fuente de verdad habrá migración, reconciliación, cambio de lectores/escritores y
retiro explícito de lógica anterior. `value_ledger` sigue siendo métrica de producto;
`economics.py` sigue siendo economía de Bynoesis, no GL del cliente.

## Alternativas descartadas

- Microservicios/event broker: coste y fallos distribuidos sin necesidad actual.
- Otro ORM/pool: rompería la transacción común y duplicaría infraestructura.
- Sustituir globalmente `_normalise_value`: cambiaría contratos de todas las APIs.
- Reorganizar todos los archivos ahora: más riesgo sin valor para Fase 0.

## Verificación y consecuencias

Contrato compartido de tests en SQLite y PostgreSQL: escritura legacy y exacta
revierten juntas, el commit exterior persiste, lectura exacta conserva tipos y la
legacy no cambia. Es infraestructura, no garantía automática de aislamiento de
repositorios que todavía no existen. Cada dominio deberá probar sus invariantes.
