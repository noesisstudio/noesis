# ADR-003 · Contrato futuro de partida doble

- Estado: aceptado como restricción de diseño; implementación en Fase 2.

## Decisión

El General Ledger será determinista y tendrá repositorio propio. Ninguna ruta ni
LLM construirá libremente líneas contables. Antes de posting se validarán negocio,
evento, cuenta existente/activa/imputable, moneda, fecha y permisos.

DEBE = HABER en Decimal a precisión final de moneda. Un asiento descuadrado nunca
alcanza `posted`. Cabecera y líneas se persisten atómicamente; el reintento no
duplica efectos. Las restricciones defensivas de PostgreSQL complementarán al
servicio y a los tests; SQLite no determinará el límite de garantías de producción.

Un asiento publicado no se edita ni elimina: se corrige con reverso/ajuste
autorizado y enlazado. La numeración contable es independiente de la fiscal.
La trazabilidad alcanzará evento, operación/documento, actor, aprobación y,
cuando exista, pago y banco. Replay se valida en entorno aislado; no significa
borrar un ledger publicado ni regenerar registros fiscales.

## Integración preservada

Factura y registro fiscal mantienen su autoridad documental y sus protecciones.
El ledger consume hechos derivados de datos confirmados/congelados, no PDF ni
respuestas del modelo. Se reutiliza el cobro existente; no se crean dos pagos.
No se confunde aceptación de AEAT con reconocimiento contable ni anulación fiscal
con reverso económico automático.

Los ejemplos de cuentas del Master Plan no son reglas tributarias aprobadas.
Antes de codificarlos se validarán retenciones soportadas/practicadas, anticipos,
signos, devengo y rectificaciones con evidencia y criterio profesional. No se
universaliza «factura emitida = ingreso íntegro inmediato».

## Alternativas y verificación futura

Se descartan saldos editables como fuente de verdad, posting con float, asientos
construidos por IA y contabilización añadida a `db.py`. En Fase 2 se exigirán
balance, idempotencia, concurrencia, reversos, rollback, aislamiento y replay.
Los períodos respetarán [ADR-005](ADR-005-accounting-periods.md).

Fase 0 solo reserva `accounting/__init__.py`. No hay cuentas, tablas, modelos,
motor de posting, asientos, Open Items ni migración contable.
