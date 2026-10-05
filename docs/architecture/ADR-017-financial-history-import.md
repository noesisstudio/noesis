# ADR-017 — Incorporación histórica sin ejecución financiera

Estado: implementación autorizada, validación pendiente. Fecha: 5-oct-2026.
[Orden completa](FASE-1.9D-orden.md). Exclusivamente1.9D; no1.9E.

## Auditoría previa del runtime main

Schema71 protege fuentes, eventos, links y secuencia con el gate de negocio.
EconomicEvents.append siempre consulta assert_writable: no se modifica esa puerta.
Los links preceden al evento y sus FKs son diferidas. Operations.prepare genera
UUID aleatoria; el recorder histórico requiere una derivación propia estable.
Los guards62 conservan identidad pero aún permiten una autorización humana para
una operación histórica por SQL. El wrapper1.9A admite tres v2 especiales;
EconomicEvent y CHECK65 todavía no. capture_event exige cobertura live para todo
v2: debe limitarse explícitamente a factura v2, conservando su enforcement.
El planB/C contiene DiagnosticCandidate/InventoryEvidence sin observed_at en el
hash; la observación durable se recupera de started_at del carrier congelado.
not_durably_supported y severity=blocking de los tres wrappers expresan ausencia
de soporte durable, no permiten cambiar la clasificación/evidencia congelada.

## Decisión

Migración72 añade batch e items/intents, sin alterar71. Un item en recording se
inserta y se completa en la misma TX prestada: gate, permisos actuales, epoch,
manifest, candidato/evidencia real, dependencias, recorder, evento y resultado.
Los guards solo exceptúan las inserciones exactas de su event/operation UUID y
el incremento esperado de la secuencia común. Un FK propio diferido obliga a
completar recording antes del commit en ambos motores. No bandera de conexión,
no desactivar fence ni bypass por negocio. Application append live sigue intacto.

HistoricalIdentity determina event UUID, EntryIdentity y operation UUID sin
operador/manifest/retry. Una autorización historical_unknown registra al operador
actual, actor/session originales NULL. Operación PREPARED permanente, resultado
NULL; resultado histórico en import_items. GuardsSQL impiden ejecución/promoción.
Solo los tres v2 aprobados y v1 contractualmente válido; factura histórica v2
bloqueada. Bytes/hashes anteriores deben conservarse por pruebas golden.

La matriz cerrada se exige también en HistoricalEconomicEvent antes del wrapper:
el objeto durable no admite factura histórica v2 aunque el wrapper de A pudiera
validarla en memoria. Golden usa una factura live v2 real y verifica preservación
de bytes/hashes y rechazo histórico en ambos motores.

Batch guarda hashes de C, epoch/generación/T0 indirectos e importer_version.
Resultados son cobertura histórica indexada, jamás cobertura live65–67.
Reintentar verifica el registro original; otro batch conserva su procedencia y
solo referencia evidencia existente coherente. Relaciones solo por identidad
exacta y evento durable verificado; padresB no satisfacen dependencias.

Permitir candidatos seguros independientes de manifest BLOCKED produce partial;
completed solo expresa terminar candidatos seguros de un plan sin pendientes.
SOURCE_DRIFT revierte primero y se registra como bloqueo separado, sin corregir
fuentes ni reescribir plan. Éxito/crash nunca libera fence ni activa flags.
Solo fixtures sintéticos y DB descartables. Sin productor/Capture/writer fiscal,
sin I/O externo ni acceso productivo. Reconciliación/activación esperan otra orden.
