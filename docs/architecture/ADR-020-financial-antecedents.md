# ADR-020 — Antecedentes por propósito, evidencia sin autoridad

Fecha: 2026-10-06. Alcance: exclusivamente Fase 1.10B, rama dedicada desde la
base exacta autorizada. A aceptada; ninguna autorización para C–H, main o despliegue.

## Problema y decisión

Una fila legacy no acredita por sí sola una factura, un cobro ni un estado anterior.
El nuevo módulo `financial_antecedents/` comprueba identidad, origen y calidad para
un propósito concreto. `resolved` nunca equivale a permiso, activación o ejecución.
No usa importe, fecha, cliente, texto o status como criterio de identidad.

Monolito modular, FinancialSession prestada y transacción exterior. Gate de negocio
antes de locks de filas, como los escritores existentes. Comprobación exclusivamente
SELECT; persistencia separada exclusivamente en una nueva tabla append-only.
El evaluator A permanece estable, salvo matriz explícita de compatibilidad con
la migración aditiva. No nuevos pools, productores, consumidores de runtime o I/O.

Histórico: evento y HistoricalIdentity originales, candidato/raw congelados,
operation PREPARED de namespace historical, historical_unknown, intent/proof de
importación originales, batch/cut/manifest correspondientes y reconciliación E PASS
durable verificada. Se vuelve a contrastar la fuente y las dependencias exactas.
Se comprueba la prueba del hecho particular, sin exigir que el conjunto entero de
E siga congelado: otros hechos live futuros no convierten ni sustituyen el hecho
histórico. Handoff/readiness no se simulan. Un batch partial solo se admite si
el item exacto está recorded, no hay blocking_code y su E correspondiente es PASS.

Live: operación COMMITTED, request/result verificables, confirmación humana válida
al commit, EE/links, cobertura exacta, fuente/revisión y fingerprint del Capture.
Los mandatos no se acreditan con la sola fila de authorization: quedan bloqueados
hasta prueba específica completa. Las cadenas supplier requieren todas las
revisiones contiguas y before/after/antecedent exactos. Los niños no pueden sustituir
padres por otros del mismo importe o tenant.

La calidad histórica A/B se conserva. `inspect_evidence` es un propósito adicional
de consulta que puede devolver observed_state con unknowns. Ningún propósito
operativo admite observed_state. El positivo histórico usa la cadena real de
importación sintética y E, sin promover los tres v2 observados existentes.
La factura histórica v2 continúa unsupported, incluso para consulta resoluble.

## Moneda y desconocidos

EUR; Decimal y JSON decimal string. Dinero solo del evento y request/evidencia
acreditados. No Decimal(str(float)), NULL→0, fecha→hoy ni pagada→cobro.
Las representaciones físicas binarias se inspeccionan/hashan exclusivamente para
contrastar la identidad de los Capture anteriores; nunca conceden precisión.
La proyección binaria de un valor ya acreditado se puede contrastar con los bits
de almacenamiento fiscal, sin convertir el origen binario en importe exacto.
Saldo = total acreditado − cobros exactos con pruebas y cobertura exhaustiva.
No Open Items, cash adicional, asientos ni reporting.

## Persistencia y continuidad futura

Migración 75 crea `financial_antecedent_resolutions`; 63–74 intactas. Fuentes
tipadas con FKs compuestas, refs a evento/operation/auth y cadena histórica por
negocio. Una clave protegida adicional permite que futuros hijos referencien
resolution_uuid + outcome + purpose + quality + origin + event_uuid exactos.
No se eliminan FKs de writers actuales ni se conectan esos hijos todavía.

Mismo UUID/contexto devuelve la fila original; otro contexto Conflict. Nueva fuente
requiere otro UUID. Lectura verifica forma canónica, columnas y hashes. Revalidación
`every_use` exige recomprobar en la misma TX del futuro uso; no es permiso perpetuo.
UPDATE/DELETE finales prohibidos. Downgrade vacío; con cualquier resolución,
incluida blocked, se impide la pérdida. Baja destructiva conserva esta evidencia.

## Límites y amenaza

Los hashes no son firmas ni autoridad. SQL privilegiado que deshabilita guards
queda fuera del threat model; fixtures adversariales lo usan para demostrar
detección, nunca como reparación. SQL protege estructura/origen/tenant/inmutabilidad;
la aplicación verifica semántica y revalida. Futuro handoff deberá comprobar además
readiness, generaciones y autoridad propia, sin tratar la resolución como autorización.

Solo fixtures sintéticos SQLite/PostgreSQL. Cinco flags OFF. Sin producción,
Noesis19FQA, backups reales, liberación de fence, activación o Fase 1.10C.
