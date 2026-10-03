# ADR-014 — Contratos y gobernanza de históricos

Estado: aceptado como decisión de implementación de 1.9A, 2026-10-03.
Orden: [FASE-1.9A](FASE-1.9A-orden.md). Referencia: [plan](FASE-1.9-plan.md).

## Problema contrastado

Schema 69 conserva dinero legacy REAL/DOUBLE, revisiones observadas desde 64,
no todas las confirmaciones/importaciones originales y no toda la historia de
fuentes mutables. Los v1 de recibida/gasto/banco exigen confirmed_on/imported_on.
FinancialOperations admite historical_unknown sin actor, pero antes permitía
añadir HUMAN después; COMMITTED implica ejecutar, no incorporar evidencia.
EntryIdentity.historical no distingue todos los hechos de una misma revisión.
No se consultaron datos productivos para resolver estas diferencias.

## Decisiones

- `financial_history/` contiene únicamente contratos puros congelados y catálogos
  cerrados. No repository, reader, scanner, manifest durable, fence, importer ni
  reconciliación. El catálogo económico sigue limitado a los once tipos existentes.
- Categoría A/B/C/D, disposition y severity son ejes distintos. Regla/versión,
  razón y evidencia explícitas; ninguna regla depende de IA.
- Identidad v1 propia: negocio, origen, revisión acreditada, tipo y fact_slot.
  Hash SHA-256 y UUIDv5 propios; no manifest, operador, reloj ni retry. Factory
  histórica anterior intacta; misma identidad/evidencia diferente es conflicto.
- RawMonetaryEvidence retiene representación exacta o bits IEEE754 con Decimal
  de esos bits, nunca presenta este último como decimal original. Candidate-cent
  y delta son diagnóstico HALF_UP; un importe se declara por separado y exige
  evidencia exacta o corroboración explícita compatible y referenciada.
- NULL, cero, fecha civil, timestamp naive, aware, observación e incorporación
  conservan significados distintos. No completar datos desde el reloj.
- Wrapper `EventPayload` valida los tres v2 históricos especiales en memoria.
  No ampliar EconomicEvent durable ni guards de schema69; el camino durable aún
  los rechaza. Los v1 y v2 existentes de emisión mantienen sus validadores.
- Un candidato no acepta emisión v2 mientras falte el contrato raw de líneas y
  fiscal. No basta acreditar cabecera. Esto no cambia la emisión live v2.
- Padre missing/C/D bloquea al hijo. B también bloquea conservadoramente una
  dependencia hasta una política explícita posterior. No inferir por importe/fecha.
- Namespace historical o cualquier receipt histórico previo bloquean HUMAN,
  MANDATE, APPROVED, COMMITTED y execute. Estado inicial PREPARED; REJECTED y
  CANCELLED son salidas sin efecto. Actor original/session NULL; recorded_by
  autenticado, permiso historical.record. No nuevo estado ni nueva migración.
- Acceso de auditoría futuro requiere permiso real del negocio, contexto histórico
  y manifest/item. El contrato solo expresa concordancia, no concede permisos.
  Acceso ordinario por creador/sesión se conserva.

## Límites y alternativas

Contrato puro valida coherencia; un hash no demuestra que exista un documento
ni autentica al operador. Las próximas unidades deben contrastar referencias,
revisiones, evidencia y cobertura. `importable` significa elegibilidad contractual
local, nunca autorización ni reconciliación PASS.

Cero migraciones: servicios, repositorio, decoder y frontera live de EE bloquean
operaciones históricas incluso con metadatos corruptos insertados por SQL directo.
Schema69 aún permite algunos de esos metadatos: no se afirma un nuevo guard SQL.
El importer futuro requerirá guards durables y acceso auditado específicos antes
de incorporar hechos; no podrá llamar writers ni Capture live. Una acción nueva
requiere otra operación live con intención y autorización propias.

Privacidad: IDs/hashes/valores mínimos; no copiar PDFs, XML, imágenes,
conversaciones ni notas libres en raw evidence. Retención final pendiente de 1.10.
Cinco flags OFF; no activación, GL, Open Items, Tax Ledger ni efectos fiscales.

Validación y autoauditoría: [cierre](FASE-1.9A-cierre.md).
