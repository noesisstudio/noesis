# Financial Core: punto de entrada y continuidad

Decisión del titular, 2-oct-2026: ejecutar **solo Fase 0**, como entrega
independiente. La Fase 1 requiere una orden nueva. No convertir Economic Events
en un registro genérico de acontecimientos de Noesis.

## Orden de lectura y autoridad

1. `AGENTS.md`, `docs/project-state.json`, `Estado-actual-main` y `Tareas-vivas`.
2. Este índice y [08 · Financial Core](../areas/08-financial-core.md).
3. Los ADR aceptados de esta carpeta; QA y cierre en
   [Fase 0](FASE-0-cierre.md).
4. [Documentos de referencia](references/README.md): blueprint para la visión,
   Master Plan para la secuencia y auditoría específica para VERI*FACTU.
5. Código, migraciones y tests reales antes de decidir una implementación.

Las referencias son propuestas de diseño, no órdenes de ejecución. Ante
contradicciones manda el alcance autorizado por el titular y estas decisiones
explícitas. La normativa aplicable se contrasta con fuentes oficiales y revisión
especializada; ninguna especificación interna certifica cumplimiento.

## Decisiones aceptadas

| ADR | Contrato |
|---|---|
| [001](ADR-001-financial-core.md) | Monolito modular, repositorios y transacción compartida |
| [002](ADR-002-economic-events.md) | Eventos económicos separados de eventos operativos |
| [003](ADR-003-double-entry-ledger.md) | Invariantes futuras del ledger, sin implementarlo |
| [004](ADR-004-money-decimal.md) | Decimal, moneda, precisión y persistencia exacta |
| [005](ADR-005-accounting-periods.md) | Fechas, períodos y cierres futuros |

## Secuencia y límites de fase

| Fase | Entrega | Dependencia técnica principal |
|---|---|---|
| 0 | Contratos, Money, acceso exacto, flags, gobernanza | Infraestructura existente |
| 1 | Economic Events | 0; transacciones e identidad de operación |
| 2 | Cuentas y General Ledger | 1; reglas contables validadas |
| 3 | AR/AP y Open Items | 2; cobros/pagos trazables |
| 4 | Tax Ledger | 1–2; perfil y reglas fiscales |
| 5 | Banco y conciliación | 2–3 |
| 6 | Períodos y cierre | 2–5 |
| 7 | Reporting | 2–6; reconciliaciones |
| 8 | Dimensiones | 2 y 7; proyectos existentes |
| 9 | Tesorería/CFO | Obligaciones de 3–5 e informes de 7 |
| 10 | AP profesional | 3; documentos y aprobaciones |
| 11 | Activos | 2, 4 y 6 |
| 12 | Nómina por adaptador | 2–4 y 6 |
| 13 | Inventario, si hay demanda | 2, 4 y 8 |
| 14 | Factura electrónica estructurada | Factura canónica y cumplimiento |
| 15 | RBAC/segregación avanzada | Controles mínimos ya presentes en cada fase |
| 16 | Multi-entidad/divisa/intercompany | Núcleo y controles consolidados |

El orden autorizado es el de las fases numeradas del Master Plan, no su sección
«PR 1», que agrupa 0–2, ni su secuencia alternativa de PR que mueve el cierre.
No adelantar Open Items ni posting dentro de Fase 1. No construir funcionalidades
futuras porque tengan un archivo reservado. Los permisos mínimos se exigen desde
cada operación; no se posponen a Fase 15. Reporting por dimensión espera a Fase 8.

## Protocolo obligatorio para continuar

- Registrar la fase expresamente autorizada; no inferir autorización del roadmap.
- Leer la fase completa, buscar equivalentes, identificar lectores/escritores,
  tablas, transacciones, idempotencia, pruebas y riesgos de regresión.
- Presentar diagnóstico y unidades validables antes de editar.
- Mantener código, migración si procede, tests, guía, QA y estado en un mismo commit.
- Auditar duplicidades, multiempresa, concurrencia, dinero, reintentos, rollback,
  fuentes antiguas y cobertura de migración. Informar PASS/FAIL con evidencia.
- Separar probado localmente, probado en PostgreSQL, validado externamente y
  desplegado. No rellenar carencias con stubs ni marcar fases futuras completadas.
- Detenerse tras el cierre; el próximo modelo comienza aquí, no en el chat.

## Pendientes que condicionan Fase 1

- Revisar su catálogo: `quote.accepted` y `job.completed` son operativos; no se
  insertarán automáticamente en Economic Events. No crear un bus genérico.
- Diseñar clave idempotente de la operación, no solo del evento posterior.
- Capturar cobros parciales, completos y conciliados por su escritor común.
- No inferir un pago real a proveedor desde el estado legacy `pagada`.
- Cubrir correcciones/bajas de gastos y recibidas; no crear snapshots obsoletos.
- Conservar evidencia de aprobación estable: las propuestas pendientes se consumen.
- Planificar históricos, corte/activación y rollback sin huecos ni reenvíos fiscales.
- Resolver el lock común de cadena y documentar el resto de gaps VERI*FACTU antes
  de ampliar su uso; Fase 0 no toca ni resuelve esos gaps.

## Estado y rollback

El estado verificable vive en `docs/project-state.json`; las pruebas en
`docs/Registro-QA.md`. Fase 0 no añade tablas ni cambia la versión de esquema.
Sus flags están reservados y no tienen consumidores financieros. El rollback
consiste en revertir los cambios de fundamentos, sin tocar datos ni huellas y
conservando las actualizaciones de seguridad del lockfile. Evidencia y alcance
exactos en el informe de cierre.
