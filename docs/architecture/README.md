# Financial Core: punto de entrada y continuidad

## Orden vigente — exclusivamente Fase 1.8H

Fases 0–1.8 implementadas; hardening 1.8H cerrado con B1–B5 PASS.
Único alcance de esta unidad cerrada:
DELETE PostgreSQL (migración de reparación), gate de negocio antes de operación/
fuente, recurrencia común en servidor, consulta COMMITTED con sesión renovada y
CI completa verde. Cinco flags OFF. No 1.9, backfill, activación ni nuevos eventos.
Leer [orden](FASE-1.8H-orden.md), [ADR-013](ADR-013-financial-hardening.md)
y [cierre/evidencia](FASE-1.8H-cierre.md).
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
Leer [orden](FASE-1.8-orden.md), [inventario previo](FASE-1.8-entrada-audit.md), [ADR-012](ADR-012-financial-channels.md), [contrato de canales](FINANCIAL-CHANNELS-v1.md) y [cierre](FASE-1.8-cierre.md).
Las órdenes y cierres inferiores son históricos; no amplían esta autorización.


## Referencia histórica de Fase 1.7

1.1–1.6 aceptadas. SupplierInvoiceCapture/ExpenseCapture conectan solo
supplier_invoice.confirmed/corrected/voided y expense.confirmed/voided v1.
Writers compartidos, autorización durable, cobertura inmutable por revisión,
continuidad antes/después, logical void y guards SQL. Documento/clasificación/
source/EE/resultado comparten commit. Flags OFF; no1.8, históricos ni activación.
Pagada es etiqueta operativa, no supplier payment/AP settlement. No GL/Tax/
OpenItems/reporting nuevo. Legacy no capturado conserva comportamiento.
[Orden](FASE-1.7-orden.md), [ADR-011](ADR-011-purchasing-capture.md),
[API](PURCHASING-CAPTURE-v1.md), [cierre](FASE-1.7-cierre.md).
Las secciones inferiores describen entregas históricas; no son la orden vigente.

## Referencia histórica de Fase 1.6

Fases 1.1–1.5 aceptadas. Solo PaymentCapture y BankCapture: cobro real v1,
importación bancaria v1 y match v1 Evidence-only, sobre writers existentes.
Coberturas específicas, vínculo bank→payment, identidad cuenta/batch/fila,
aprobación durable y resultado en una transacción. Flags OFF. No avanzar 1.7.
[Orden](FASE-1.6-orden.md), [ADR-010](ADR-010-payment-bank-capture.md),
[API](PAYMENT-BANK-CAPTURE-v1.md), [auditoría de entradas](FASE-1.6-entrada-audit.md)
y [cierre](FASE-1.6-cierre.md). Lo inferior conserva historia, no autoridad vigente.

## Referencia histórica de 1.5

Fases 1.1–1.4 aceptadas; solo emisión capturada F1/F2 y rectificativas R1–R5.
Servicio `invoice_capture/`: operaciones/aprobación durable + writer1.4 + evento
v2 + resultado en un commit. Migración65: cobertura inmutable con FKs diferidas;
v1/legacy/fiscalidad conservados. Flags apagados; otros productores y1.6 no autorizados.
[ADR-009](ADR-009-invoice-capture.md), [API](INVOICE-CAPTURE-v1.md),
[entradas auditadas](FASE-1.5-entrada-audit.md) e
[informe de cierre](FASE-1.5-cierre.md). Los alcances inferiores son históricos.

## Referencia histórica de 1.4

Decisión del titular, 2-oct-2026: Fase 0 aceptada y cerrada; planificación de
Fase 1 aprobada como referencia; 1.1–1.3 aceptadas. **Solo 1.4 autorizada**:
escritores prestados, snapshots, revisiones y precisión en la frontera legacy.
Sin productores de Economic Events. **1.5 no autorizada**. Los acontecimientos
operativos conservan su dominio y no se incorporan automáticamente.

Continuidad: [plan incremental](FASE-1-plan.md),
[contrato y catálogo v1](ECONOMIC-EVENTS-v1.md) y
[cierre de 1.1](FASE-1.1-cierre.md),
[operaciones v1](FINANCIAL-OPERATIONS-v1.md) y [cierre de 1.2](FASE-1.2-cierre.md),
[persistencia v1](ECONOMIC-PERSISTENCE-v1.md) y [cierre de 1.3](FASE-1.3-cierre.md),
[writers v1](BORROWED-WRITERS-v1.md), [mapa auditado](FASE-1.4-writers-audit.md)
y [cierre de 1.4](FASE-1.4-cierre.md).

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
| [006](ADR-006-financial-operations.md) | Operación, aprobación, resultado e idempotencia durables |
| [007](ADR-007-economic-persistence.md) | Eventos/links inmutables, FKs tipadas, contador y migración protegida |
| [008](ADR-008-borrowed-writers.md) | Un núcleo por dominio, commit exterior, precisión/procedencia, revisiones y locks |
| [009](ADR-009-invoice-capture.md) | Productor único de emisión, autorización exacta, cobertura diferida y replay |
| [010](ADR-010-payment-bank-capture.md) | Cobro real, identidad bancaria, vínculo durable y match como evidencia |
| [011](ADR-011-purchasing-capture.md) | Recibidas/gastos, continuidad por revisión y conservación lógica |

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

## Pendientes de ejecución de Fase 1 después de 1.5

- Conservar el catálogo cerrado v1: `quote.accepted` y `job.completed` son
  operativos y no se insertarán en Economic Events. No crear un bus genérico.
- Integrar la identidad/idempotencia durable de 1.2 en los canales y puentes
  futuros; no conectar otros productores sin otra orden. InvoiceCapture conecta
  exclusivamente emisión y rectificativas desde servicio interno/adaptador con
  operación aprobada; los canales externos y recurrentes esperan 1.8.
- Capturar cobros parciales, completos y conciliados por su escritor común.
- No inferir un pago real a proveedor desde el estado legacy `pagada`.
- Cubrir correcciones/bajas de gastos y recibidas; no crear snapshots obsoletos.
- Conservar evidencia de aprobación estable: las propuestas pendientes se consumen.
- Planificar históricos, corte/activación y rollback sin huecos ni reenvíos fiscales.
- Lock común de cadena resuelto mínimamente en 1.4; el resto de gaps VERI*FACTU
  sigue fuera de alcance. No deducir cumplimiento AEAT de las pruebas locales.

## Estado y rollback

El estado verificable vive en `docs/project-state.json`; las pruebas en
`docs/Registro-QA.md`. Fase 0 no añade tablas ni cambia la versión de esquema.
Sus flags están reservados y no tienen consumidores financieros. El rollback
consiste en revertir los cambios de fundamentos, sin tocar datos ni huellas y
conservando las actualizaciones de seguridad del lockfile. Evidencia y alcance
exactos en el informe de cierre.

1.3 registra la migración 63 sobre main 62 verificado. Rollback vacío permitido;
con eventos/links durables la bajada y la baja destructiva se bloquean. No revertir
código de migración antes de comprobar datos. Las clausuras anteriores describen
su entrega histórica; el estado superior, JSON y QA reflejan la orden vigente.

1.4 añade tres revisiones mutables (64), sin migrar dinero legacy. Revertir código
es compatible con estas columnas; no retirar revisión con evidencia mutable.
Las restricciones y procedencia se documentan en ADR-008 y el cierre.
