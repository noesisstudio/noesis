# Fase 1: referencia aprobada y autorización incremental

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

Fases1.1–1.5 aceptadas. PaymentCapture/BankCapture sobre los writers reales:
cobro v1, imported v1 y match v1 Evidence-only, autorización durable y cobertura
con resultado en un commit. [Orden explícita](FASE-1.6-orden.md),
[ADR-010](ADR-010-payment-bank-capture.md), [API](PAYMENT-BANK-CAPTURE-v1.md),
[cierre](FASE-1.6-cierre.md). La orden incorpora import/CSV a la referencia1.6.
No autoriza1.7, canales1.8, históricos1.9 ni activación1.10. Flags OFF.
Los siguientes alcances son históricos.

## Referencia histórica de 1.5

Fases 1.1–1.4 aceptadas; solo emisión capturada F1/F2 y rectificativas R1–R5.
Servicio `invoice_capture/`: operaciones/aprobación durable + writer1.4 + evento
v2 + resultado en un commit. Migración65: cobertura inmutable con FKs diferidas;
v1/legacy/fiscalidad conservados. Flags apagados; otros productores y1.6 no autorizados.
[ADR-009](ADR-009-invoice-capture.md), [API](INVOICE-CAPTURE-v1.md),
[entradas auditadas](FASE-1.5-entrada-audit.md). Los alcances inferiores son históricos.

La planificación de Economic Event Layer fue aprobada por el titular el
2-oct-2026. Esa aprobación fija arquitectura de referencia, **no ejecución de
todas sus unidades**. Fase 0 y 1.1–1.3 aceptadas. La orden vigente autoriza solo
**1.4: fronteras transaccionales, escritores prestados y precisión monetaria**,
sin productores. 1.5 y siguientes esperan otra orden explícita.
Detalle y evidencia de 1.4 en [ADR-008](ADR-008-borrowed-writers.md),
[API de writers](BORROWED-WRITERS-v1.md) y [cierre](FASE-1.4-cierre.md).
Precisión respecto al plan inicial: la persistencia mínima de operaciones y
autorizaciones se adelanta a 1.2 por petición expresa; 1.3 añade eventos/links y
contador mínimo. [Contrato durable](ECONOMIC-PERSISTENCE-v1.md),
[ADR-007](ADR-007-economic-persistence.md), [cierre](FASE-1.3-cierre.md).

## Arquitectura que se conserva

Monolito modular, repositorios por dominio y conexión/transacción existentes.
Economic Events inmutables y separados de operativos. Decimal/EUR; JSON monetario
como string decimal; IA propone sin autoridad financiera. No General Ledger,
Open Items, Tax Ledger, posting ni reporting dentro de Fase 1.

El catálogo aprobado es el de [contrato v1](ECONOMIC-EVENTS-v1.md): once tipos;
rechazar `quote.accepted`, `job.completed` y `supplier_payment.made`. No fabricar
pagos a proveedores desde `pagada`. Banco conciliado y anulación fiscal aportan
evidencia sin duplicar caja, deuda o reversión. Recibidas corregidas guardarán
antes/después; retiradas preservarán el snapshot; emitidas se rectificarán sin
mutar historia. No producir dos hechos primarios por una rectificativa.

## Referencia para unidades futuras, todavía no implementadas

La identidad estable de **operación** deberá viajar entrada → revisión/aprobación
→ servicio → mutación legacy → evento. Misma clave/contenido devuelve el resultado
original; misma clave con contenido distinto rechaza; dos operaciones legítimas
iguales coexisten. Un hash de payload no sustituye la identidad del comando.
La aprobación deberá conservar evidencia estable al consumirse una propuesta;
no reconstruirla desde el estado actual ni inventar actores históricos.

El esquema futuro requerirá negocio, UUID, payload e identidad inmutables,
orígenes y relaciones tipados con claves compuestas, uniques e índices por negocio,
versiones, procedencia histórica y fechas conocidas/desconocidas diferenciadas.
La representación será NUMERIC/Decimal en PostgreSQL y TEXT exacto en SQLite.
No crear una FK polimórfica insegura ni un estado `posted` sin motor contable.
Se contrastó main vigente 62: 1.3 registra 63. El puente legacy sigue pendiente.

Cuando el evento sea obligatorio, mutación original + operación + evento se
confirmarán en la **misma transacción**. Cualquier fallo revierte todo; sin
observador fail-open como `value_ledger`. Los puentes de emisión, cobro, banco,
recibidas/gastos, rectificativas y anulación se localizarán en servicios, sobre
sus escritores comunes. No habrá llamadas AEAT dentro de esa transacción.
Numeración, huellas y registros fiscales conservan sus contratos.

Históricos: carga idempotente, discrepancias antes de activar, fechas/actores
desconocidos explícitos, sin reenvío AEAT ni recálculo de huellas. OFF → validación
→ enabled por negocio; desactivar/reactivar no podrá dejar huecos de historia.
Reversión/corrección de un cobro no tiene un productor ni tipo aprobado actual;
no inventar un evento nuevo sin otra decisión de alcance.

## Secuencia aprobada

| Unidad | Entrega de referencia | Dependencia / riesgo / salida |
|---|---|---|
| 1.1 | `economic_events/contracts.py`, catálogo, validación, canonicalización y tests | Fase 0; sin migración/efectos; cierre documentado |
| 1.2 | Operaciones, autorización y resultados durables, API interno y migración 62 | Orden posterior explícita; deduplicar efecto futuro; concurrencia/rollback/reintentos probados sin productores |
| 1.3 | Persistencia, repositorios y constraints de Economic Events y relaciones | Orden explícita recibida; migración 63, sin productores; cierre independiente |
| 1.4 | Frontera transaccional y puente legacy exacto | 1.3; rollback de ambas partes y aislamiento; no duplicar infraestructura |
| 1.5 | Emisión y rectificativas | 1.4; invariantes fiscales/huellas/numeración conservadas |
| 1.6 | Cobros y conciliación bancaria | 1.4–1.5; parciales y reintentos sin doble caja |
| 1.7 | Recibidas y gastos, correcciones/retiradas | 1.4; snapshots y relaciones sin historia obsoleta |
| 1.8 | Canales y recurrencias | Puentes comunes; doble clic, webhooks, workers y timeout tras commit |
| 1.9 | Carga histórica y reconciliación | Cobertura de productores; cero reenvíos fiscales; discrepancias visibles |
| 1.10 | Activación incremental | Validación por negocio; corte, apagado/reactivación y observabilidad sin huecos |

Antes de cada unidad: leer código real, definir archivos/migración/tests y cerrar
su criterio de salida de forma proporcional. Matriz posterior: SQLite/PostgreSQL,
multiempresa, concurrencia real, rollback, doble clic, webhook, reintento, worker,
timeout tras commit, rectificativas, cobros parciales, banco, recibidas/gastos,
correcciones, históricos y cadena VERI*FACTU. No atribuir estos resultados a 1.1.

Esta referencia durable conserva las decisiones aprobadas necesarias para
continuar; el código/QA y la orden explícita de cada unidad prevalecen sobre
propuestas de implementación futura. La Fase 1 completa todavía no está cerrada.
