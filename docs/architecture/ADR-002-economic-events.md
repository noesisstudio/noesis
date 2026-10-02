# ADR-002 · Hechos económicos separados de acontecimientos operativos

- Estado: aceptado; diseño para Fase 1, sin implementación en Fase 0.
- Precisión del titular (2-oct-2026): `economic_events` no será un event log genérico.

## Decisión

**Domain/Operational Events** describen acontecimientos del negocio: presupuesto
aceptado, trabajo completado, documento subido, mensaje recibido o tarea cambiada.
No implican por sí solos ingreso, deuda, pago ni registro fiscal. Se mantienen los
mecanismos operativos existentes; no se crea un bus/event log genérico.

**Economic Events** describen hechos con significado económico/financiero que
pueden alimentar contabilidad, fiscalidad, AR/AP, tesorería o reporting. Ejemplos
futuros: factura emitida, cobro registrado, compra confirmada, reconocimiento
económico autorizado o rectificación con efecto económico.

`quote.accepted` y `job.completed` NO se incorporan automáticamente a
`economic_events`. Si una regla explícita convierte una prestación en un
reconocimiento o una obligación, se validan sus condiciones, autorización, fecha,
importe y evidencia y se produce **otro hecho económico** trazable al origen.
La aceptación que crea un borrador sigue siendo operativa: borrador no es emisión.

## Contrato futuro y puerta de entrada

Antes de aceptar un tipo de evento, documentar:

1. Qué hecho financiero representa y qué dominio lo posee.
2. Qué condición/operación confirmada lo produce; actor, permisos y evidencia.
3. Qué importe, moneda y fechas son conocidos; no rellenar lo desconocido.
4. Si alimenta GL, Tax Ledger, obligaciones o solo evidencia/conciliación.
5. Qué clave identifica la operación y cómo se corrige sin reescribir historia.

No todo Economic Event genera asiento. Importar un movimiento bancario aporta
evidencia financiera y no debe duplicar el cobro ya registrado. Clasificar el
movimiento y reconocer un cobro son hechos diferentes, enlazados cuando proceda.
Un coste estimado de gestión tampoco debe duplicar la compra que lo respalda.

Cada hecho futuro tendrá negocio, identificador, versión de payload, origen,
clave idempotente, fechas, moneda, actor/canal y evidencia estable de autorización.
Payload e identidad serán inmutables; el estado de procesamiento no los modifica.
Un fallo al crear un evento obligatorio revierte la operación local. No copiar
el observador fail-open posterior al commit de `value_ledger`.

Una anulación fiscal no significa por sí sola condonar una deuda ni revertir un
asiento. Un estado de proveedor `pagada` no prueba una transferencia. El tratamiento
económico exige una regla y evidencia propias.

## Relación con registros existentes

- `invoice_records`, anulaciones y `invoice_events`: conservar historia fiscal.
- `assistant_actions`: mantener auditoría y revisión del asistente.
- Eventos de seguridad: mantener su objeto y protección actuales.
- `value_ledger`: conservar medición de producto.

No fusionar estas entidades por compartir la palabra «evento». Tampoco afirmar
que Economic Events sustituye un registro de eventos exigido por normativa SIF.

## Alternativas descartadas y consecuencias

- Registrar todo en Economic Events: convierte el núcleo en telemetría y favorece
  reconocimiento contable accidental.
- Mutar un evento desde presupuesto hasta cobro: pierde hechos y temporalidad.
- Crear ahora Domain Events genéricos: no está autorizado ni es dependencia de 0.

Se corrige explícitamente el catálogo inicial del Master Plan. En Fase 1 habrá
que revisar cada productor; esa fase no queda implementada por este ADR.
