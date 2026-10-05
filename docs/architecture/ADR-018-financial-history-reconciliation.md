# ADR-018 — Reconciliación histórica sin reparación

Estado: implementada; matrices locales PASS, CI final pendiente. 5-oct-2026.
[Orden completa](FASE-1.9E-orden.md). Solo1.9E; no1.9F ni activación.

## Auditoría previa de main

D conserva manifests/items B/C inmutables; operaciones D PREPARED y unknown,
resultados separados, payload histórico v2 cerrado y fence por negocio. Schema72.
RawReader scopeC incluye Economic Events/links/coverage. Después de D, el conjunto
físico contiene adiciones autorizadas EE/link. Comparar counts o exigir el hash
físico completo de antes de D haría imposible un PASS correcto. Fuentes fiscales
page recalcula la validación anterior: E debe usar referencias congeladas sin
invocar las funciones de hash VERI*FACTU. D run conserva partial cuando C BLOCKED
solo por soporte v2 que entonces no era durable; E debe decidir por identidad.

## Decisión

Dos tablas nuevas: run y findings exclusivamente discrepancias. TX única del
servicio sobre get_conn/FinancialSession y gate común, scan paginado; running y
freeze atómicos. Crash precommit revierte todo E; retry reinicia o recupera frozen.
SQLite writer global; PG gate solo del negocio. Release/invalidate se serializan;
se revalida boundary antes de freeze. No sleeps ni segundo pool/conexión.

source_recheck_hash reproduce el conjunto C congelado: ninguna exclusión nueva.
Se escanea el conjunto físico completo; únicamente EE/links nuevos con proof D
válido y explicación en el manifest actual se separan como delta autorizado,
comprometido por event_set_hash. Cualquier otra alta/baja/cambio bloquea. Referencias
fiscales se contrastan conservando fiscal_hash_valid congelado, sin regenerarlo.

PASS exige explicar todos los items y validar todo histórico del negocio,
operaciones/autorizaciones/proofs, identidad, links, dinero, cobertura live y
secuencia. partial por el antiguo not_durably_supported v2 puede PASS solo si
todos los impedimentos están explicados y cada candidato soportado está incorporado;
partial/blocked con cualquier candidato necesario pendiente da BLOCKED. No se
reescribe C ni D. B observado sigue B; unknown no se sustituye por cero.

Solo se conservan índices de identidades/edges/hashes O(N+E), payloads por página.
Lookups por lote para eventos/op/auth/proofs; findings cerrados, evidencia mínima.
Hashes semánticos ordenados, sin UUID aleatorio ni reloj de reconciliación.
Frozen inmutable y guard SQL de boundary antes de PASS. Nuevo guard73 impide
reabrir batch terminal para crear otro intent; retries de resultados existentes
siguen posibles. Compatibilidad de servicios B/C/D con73, sin modificar63–72.

No endpoint/CLI/tool/scheduler/productor/IA; flags OFF y fixtures sintéticos.
Ninguna escritura fuera de run/findings durante E. Sin permisos financieros,
authorizations nuevas, repair, import, reclassify, fiscal I/O ni cambio de epoch.
