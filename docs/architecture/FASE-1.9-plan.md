# Fase 1.9 — referencia de diseño aprobada

## 2026-10-05 — Fase1.9E: reconciliación histórica implementada y validada

[Orden](FASE-1.9E-orden.md), [ADR018](ADR-018-financial-history-reconciliation.md),
[contrato](FINANCIAL-HISTORY-RECONCILIATION-v1.md), [informe](FASE-1.9E-cierre.md).
Solo audita por identidad; writes exclusivamente run/findings propios. TX/gate y
conexión compartidos, repositorio especializado, Decimal/NUMERIC, IA sin autoridad.
B/C/D siguen inmutables; unknown/B/NULL conservados. PASS no libera fence, activa
flags ni acredita producción. Cinco flags OFF. Sin1.9F ni activación. Validación
local y CI final PASS; cierre técnico1.9E registrado. Encabezados inferiores históricos.

## 2026-10-05 — Fase1.9D: importer histórico (implementada y validada)

Solo incorporación de candidatos congelados de C vigente. Flags OFF; no1.9E,
reconciliación, activación, continuidad live ni producción.
[Orden](./FASE-1.9D-orden.md), [ADR017](./ADR-017-financial-history-import.md),
[contrato](./FINANCIAL-HISTORY-IMPORT-v1.md), [cierre](./FASE-1.9D-cierre.md).
Monolito modular; importer/repositorio especializados sobre conexión y TX
compartidas. Decimal/NUMERIC y JSON decimal string; IA sin autoridad.
Intent item-scoped con UUID/request/candidato exactos; fence permanece activo.
Operación histórica PREPARED y historical_unknown, actor/session NULL; resultado
en import_items, ninguna ejecución ni cobertura live65–67. Tres v2 históricos
durables cerrados; factura histórica v2 bloqueada. Nuevos inventarios reconocen
evidencia histórica existente sin promover B a A ni modificar batches anteriores.
Los encabezados inferiores conservan historia y no amplían autorización.


## 2026-10-04 — Fase1.9C: epoch/T0/fence (implementada y validada)

Únicamente corte consistente por negocio, control durable y nuevo sobre de
inventory certificable, siempre eligible_for_import=false. Schema71, flags OFF.
[ADR016](ADR-016-financial-history-cutoff.md), [contrato](FINANCIAL-HISTORY-CUTOFF-v1.md),
[writers previos](FASE-1.9C-writers.md), [cierre](FASE-1.9C-cierre.md).
SQL/application guard por tenant y TX prestada; no promoteB ni histórico EE/Operations/
v2/importer/reconciliación/activación.1.9D NO autorizada. Pruebas SQLite/PG sintéticas,
ninguna producción consultada. Invalidated conserva fence, release explícito pierde
boundary; TTL/crash no liberan. Encabezados inferiores conservan historia.


## Continuidad vigente — 1.9B

Referencia aprobada concretada por [orden humana1.9B](FASE-1.9B-orden.md).
Solo inventario persistente y dry-run diagnóstico, no1.9C. [ADR015](ADR-015-financial-history-diagnostic-inventory.md)
separa lifecycle/result y garantiza no certificación/importación. Cinco flags OFF,
sin producción ni efectos financieros. Los textos inferiores conservan la síntesis
histórica de diseño previa a1.9A y no son autorización para otras unidades.

La aprobación humana del diseño antecede a [orden 1.9A](FASE-1.9A-orden.md).
Este documento fija su síntesis operativa heredable, contrastada con schema69.
No es una autorización de ejecución de toda 1.9. Solo 1.9A se implementa ahora.
La precedencia es orden humana vigente → código/contratos → referencia futura.
No se ha inventariado ni clasificado ninguna fila productiva.

## Fundamentos de la referencia

1. Fuentes: invoices/lines/profile/invoice_record, rectificativas, invoice_payments,
   bank_transactions/bank_payment_links, supplier_invoices, expenses, documents,
   invoice_cancellation_records y runs recurrentes. Inspeccionar schema/código no
   demuestra qué datos existen en producción.
2. A historia verificable; B estado observado; C ambiguo; D no transformable sin
   inventar. Clasificación, disposición y severidad separadas; reglas reproducibles.
3. Monolito modular, infraestructura compartida y repositorios por dominio; nada
   de Kafka, servicios externos, IA clasificadora ni nueva lógica grande en db.py.
4. Manifest futuro congela negocio, sources/revisiones, raw, fechas, referencias,
   hashes y versiones de reglas/importer. UUID de run no identifica el hecho.
5. Corte lógico T0 y epoch deben impedir mezcla de estados legacy concurrentes;
   MAX(id) y reloj por sí solos no bastan. Freeze/validate bajo gate por negocio,
   sin locks durante toda exploración. Fence efectivo se probará antes de importar.
6. Identidad independiente de run/operador/retry; dos fact slots separan hechos.
   Drift o evidencia incompatible produce incidencia, nunca overwrite histórico.
7. Historical_unknown registra al operador actual, no inventa actor original.
   PREPARED no ejecutable; no HUMAN/MANDATE posterior ni COMMITTED con falso efecto.
8. Importer futuro específico origin=historical, sin Capture.execute ni writer;
   no reutilizar coberturas live 65–67 fingiendo aprobación/ejecución originales.
9. Los once tipos mantienen semántica. Emitida/rectificada requieren evidencia
   documental/fiscal suficiente; recibida/gasto pueden ser B sin inventar historia.
   Tres v2 históricos especiales conservan fechas originales desconocidas.
10. Dependencias concretas y orden topológico: original→rectificación/payment/
    cancelación, import+payment→match; C/D bloquean hijos. Sin amount/date heurísticos.
11. REAL/DOUBLE nunca demuestra decimal original. Raw/bits, candidato y delta
    separados de importe financiero; subcéntimos/discrepancias son incidencias.
12. Incidencias durables específicas en una unidad futura; las decisiones añaden
    evidencia o excluyen, nunca inventan hecho/autoridad. Catálogo en contrato v1.
13. Dry-run futuro no inserta eventos ni altera sources/fiscal/flags. Inventario
    completo, partición de categorías, dependencias, hashes y discrepancias visibles.
14. Reconciliación por identidad/source/revisión/importes/relaciones/fiscal/cobertura;
    contadores solos no bastan. Resultado PASS/BLOCKED, no activación automática.
15. Serialización del negocio solo en puntos críticos; snapshots/hash/revisiones
    y fence detectan escrituras concurrentes. Importar grupos de dependencias en
    transacciones acotadas; fuera de ellas nunca mantener falsa fotografía estable.
16. Crash/retry reanudables mediante items y cobertura específica; nunca repetir
    writers. Rollback de código no destruye eventos/evidencia append-only.
17. Matriz SQLite/PG: ambiguos, faltantes, corroboración, fechas, fiscal, tenant,
    crash, drift, replay, dependencias, corte concurrente y cero efectos legacy.
18. Tablas futuras mínimas de manifest/items/incidencias/decisiones/cobertura/
    reconciliación y epoch/fence, solo cuando su unidad esté autorizada. No70 en A.
19. Salida completa1.9: manifest congelado, import terminado, reconciliación PASS,
    sin bloqueantes y frontera live conocida → elegible para validar1.10. No enabled.
20. Contacto serio con datos reales solo en copia/restauración revisada antes de
    importación; sin AEAT, emisión, cobros reales, cambios de status/número/huella,
    supplier_payment, GL, OpenItems, Tax Ledger, borrado de sources ni activación.

## Unidades futuras y autorización

A: contratos/gobernanza, única unidad autorizada y [documentada](FINANCIAL-HISTORY-v1.md).
B y siguientes: inventario/manifest, corte/epoch/fence, dry-run/incidencias,
importación/reanudación, copia restaurada (1.9F) y reconciliación, en órdenes
separadas. Su reparto exacto y DDL deberán contrastarse antes de implementar.
Esta referencia no crea ninguno de esos servicios ni sustituye sus gates.
Retención/exportación/acceso finales y activación pertenecen a1.10.

## Estado vigente por unidades (5-oct-2026)

| Unidad | Estado | Referencia |
|---|---|---|
|1.9A|Aceptada, contratos|[Cierre A](FASE-1.9A-cierre.md)|
|1.9B|Aceptada, inventario diagnóstico|[Cierre B](FASE-1.9B-cierre.md)|
|1.9C|Aceptada, epoch/T0/fence|[Cierre C](FASE-1.9C-cierre.md)|
|1.9D|Aceptada, incorporación durable|[Cierre D](FASE-1.9D-cierre.md)|
|1.9E|Implementada y validada; matrices locales y CI final PASS|[Cierre E](FASE-1.9E-cierre.md)|
|1.9F|NO autorizada, NO iniciada; sin copia real ni producción|Orden humana futura separada|
|1.10|NO autorizada; ninguna activación/readiness acreditada|Referencia únicamente|

inventory certifiable ≠ import completed ≠ reconciliation PASS ≠ production rehearsal ≠ activation.
PASS en E conserva fence y flags OFF. La preparación sintética de QA no es1.9F.
