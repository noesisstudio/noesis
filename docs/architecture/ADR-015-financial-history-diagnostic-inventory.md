# ADR-015 — Inventario histórico diagnóstico, no certificable

Estado: implementado en1.9B; QA local completa; informe y gates en cierre. Fecha:3-oct-2026.
Orden: [1.9B](FASE-1.9B-orden.md). Antecedente: [ADR-014](ADR-014-financial-history-contracts.md).

## Problema y decisión

Schema69 conserva dinero REAL/DOUBLE y varias migraciones reconstruyeron datos
sin conservar marcadores discriminantes. Un scanner no acredita el estado del
negocio en T0 ni puede autorizar efectos financieros. Necesitamos una fotografía
revisable que conserve precisamente lo que se pudo observar y lo desconocido.

Migración70 añade exclusivamente manifests/items/incidences/decisions. CHECKs
fuerzan mode=diagnostic, eligible_for_import=false y certifiable=false. Resultado
READY_FOR_REVIEW/BLOCKED separado de lifecycle scanning→planning→frozen. No estados
de importación, epoch, fence, validación certificada ni transición live.

El [mapa previo](FASE-1.9B-fuentes.md) y el catálogo sources.py determinan columnas,
claves y procedencia. Readers reciben conexión/FinancialSession prestada y hacen
SELECT tenant con keyset. La excepción raw explícita usa execute_exact de la
conexión para inspeccionar floats físicos; el resto del Core sigue Decimal.
No nuevo pool, ORM o gran lógica en db.py. Service posee TXs cortas por página;
repositorio especializado persiste solamente las cuatro tablas autorizadas.

Clasificador puro/versionado. A/B solo con dinero exacto o corroboración durable
compatible; candidato a céntimos no acredita importe. Lo sintético/ambiguo se
expone con códigos cerrados. Estados observados de compra no reconstruyen historia
ni pagos. Auxiliares no son productores. Factura histórica v2 sigue bloqueada.
Cobertura existente verifica sobre/hash/source/revisión/relaciones/datos; evita
candidato nuevo. Contradicción bloquea y no repara. IA no llama este servicio.

## Congelación, identidad y reproducibilidad

Una UUID explícita identifica la ejecución lógica, no el reloj. Retry recupera
la misma evidencia/plan; otra UUID pide otro diagnóstico. Evidencia previa
incompatible se conserva y produce SOURCE_DRIFT. Se recorre nuevamente el conjunto
con páginas, comparando pertenencia, revisión y raw completo. Sin drift detectado
también es no certificable: una escritura tras la comparación puede no observarse.

Item identifica ubicación+fact_slot+negocio+reader_version; la identidad del
candidato incluye revisión tipada. source_set_hash ordena catálogo y claves
físicas, con delimitación JSON y hashes de evidencia. plan_hash ordena item UUID,
incidencias, assessment, dependencias, candidate hash, cobertura y scope/version.
Nunca MAX(id) ni reloj como corte. Orden de claves pagina, no demuestra T0.

InventoryEvidence/DiagnosticCandidate son contratos semánticos nuevos: excluyen
el instante de observación del hash del plan. El manifest audita started_at y
completed_at; fuentes conservan fechas civiles/naive/aware sin completar zonas.
No se alteran bytes/hashes de los contratos v1 de1.9A. DiagnosticCandidate hereda
HistoricalCandidate, valida el mismo contrato y fuerza importable=false. Su
canonical durable es un PLAN dentro de history_items, no soporte durable EE v2.
Los tres v2 especiales se marcan not_durably_supported; no falsean readiness.

SQL impide modificar evidencia/raw aun durante retry; classification se escribe
una sola vez. Manifest congelado y todos sus items/incidences son inmutables.
Decisiones son append-only, actor actual autenticado/session vigente/tenant,
permiso historical.record y plan suscripción compatible con escritura. Sin receipt
financial.authorize. Revisión no reescribe/reclasifica ni cambia summary/hash;
evidencia nueva requiere otro manifest para otro plan. FKs compuestas en todas
las relaciones durables; ninguna cascada elimina evidencia. Downgrade70 con
cualquier fila se niega; vacío permite70→69→70.
La baja de cuenta integra esos cuatro nombres en su guard de conservación ya
existente: rechazo controlado con evidencia, baja anterior si no hay historia.
No política/plazo de retención nuevo; purga/exportación finales siguen1.10.

## Límites y consecuencias

Auxiliares/parent se agrupan por página con índices de referencias JSON. Contexto
acotado256 por consulta; overflow divide página, y una fuente individual que
supera el límite queda C/SOURCE_HISTORY_LOST por contexto incompleto, sin inferir.
No N+1 de fuentes/auxiliares. Insert/assessment por item es persistencia propia.
No copia de PDF, imagen, XML, OCR, conversaciones o notas; texto de concepto de
gasto y razón fiscal son mínimos contractuales explícitos. Marcas/documentos/partes
se conservan mediante IDs/hashes. Scope anchor contiene solo el ID del negocio
para registrar deriva incluso cuando el inventario inicial está vacío.

Conservar PostgreSQL y SQLite existentes; comprobar ambos en bases sintéticas.
No producción, Railway ni copia real. Cinco flags OFF. No histórico EE/Operations,
importer, cobertura histórica, conciliación final, GL, Tax, AR/AP ni activación.
1.9C requiere autorización humana separada y aún no se ha iniciado.

Contrato: [FINANCIAL-HISTORY-INVENTORY-v1](FINANCIAL-HISTORY-INVENTORY-v1.md).
Evidencia final y autoauditoría: [cierre1.9B](FASE-1.9B-cierre.md).
