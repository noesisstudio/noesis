# Fase 1: referencia aprobada y autorización incremental

La planificación de Economic Event Layer fue aprobada por el titular el
2-oct-2026. Esa aprobación fija arquitectura de referencia, **no ejecución de
todas sus unidades**. La siguiente orden autoriza solo **1.1: contratos**.
Fase 0 está aceptada y cerrada. 1.2 y siguientes esperan otra orden explícita.

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
El detalle de migración debe contrastarse con `main` antes de autorizar 1.3.

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
| 1.2 | Contratos de comandos y autorización estable | 1.1; deduplicar operación antes del efecto; reintentos/identidades probados |
| 1.3 | Persistencia, repositorios y constraints de eventos/operaciones/autorizaciones | 1.2; migración revisada; SQLite/PostgreSQL, relaciones y concurrencia |
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
