# ADR-005 · Fechas y períodos contables

- Estado: aceptado como contrato futuro; no se implementan cierres en Fase 0.

## Decisión

Separar fecha de documento, operación, reconocimiento contable, devengo fiscal,
vencimiento, pago y registro técnico. Una fecha no sustituye automáticamente a
las demás. El nuevo núcleo usará instantes conscientes de zona (TIMESTAMPTZ en
PostgreSQL, representación ISO con offset en SQLite) y fechas civiles DATE donde
corresponda. La zona fiscal/empresarial se aplica explícitamente, no la del host.

Los períodos futuros pertenecerán a un negocio. Estados previstos: open,
soft_closed y hard_closed. Un hard close impide posting ordinario; reapertura o
ajuste exige autorización, motivo, actor, evidencia y auditoría. La comprobación
del período se hará dentro de la transacción del posting para resolver carreras
entre contabilización y cierre.

Los períodos de envío documental a gestoría existentes no son un cierre del GL.
No se reutilizarán sus etiquetas como bloqueo contable sin migración y pruebas.
Tampoco se alterarán fechas de facturas ni timestamps encadenados para encajar
históricos en el núcleo nuevo.

## Alternativas descartadas

- Un campo `date` para todo: pierde devengo y temporalidad.
- Usar el estado visual de gestoría como cierre: no protege el posting.
- Reabrir silenciosamente al llegar una factura tardía: altera historia.
- Implementar ahora períodos: fuera de la entrega autorizada.

## Consecuencias y validación futura

Fase 2 deberá respetar este contrato al definir fechas y posting; Fase 6 aporta
el workflow completo. Las reglas de autorizaciones aplican desde que exista la
operación, sin esperar RBAC enterprise. Tests futuros: límites de mes/año,
medianoche, cambios de horario, multiempresa, posting concurrente con cierre,
reapertura auditada y correcciones posteriores.
