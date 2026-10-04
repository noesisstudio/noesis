# Financial history cutoff v1 — contrato heredable

Solo1.9C. [ADR016](ADR-016-financial-history-cutoff.md), [orden](FASE-1.9C-orden.md),
[mapa previo](FASE-1.9C-writers.md), [cierre](FASE-1.9C-cierre.md).

## API interna

`HistoryCutoff(business_id,page_size=1..64)` usa el pool/get_conn y FinancialSession
existentes. No router/tool/CLI ni scheduler nuevo. Métodos con Principal actual:

- open(epoch_uuid,repository_version,environment_identity): etiquetas1..128
  alfanuméricas/_.- explícitas, sin URLs. UUID exacta/operador/version/scope/entorno
  reintenta el mismo T0 incluso invalidated/released; nunca lo reactiva. OtraUUID
  con epoch activo → ConflictError. State cerrado fenced/invalidated/released.
- inventory(epoch_uuid,manifest_uuid,repository_version,environment_identity):
  solo fenced/control vigente/scope fijo v1/entorno exacto. Carrier+cut nuevos
  atómicos, retry por manifestUUID, corto por página, reaprovecha B. Devuelve sobre
  `mode=certifiable_inventory`, eligible_for_import=false siempre.
- invalidate(epoch_uuid,reason): motivo identificador, actor/fecha auditados;
  invalida boundary/certifiable, marca parcial aborted/BLOCKED, conserva fence.
- release(epoch_uuid,reason): acto explícito, actor/fecha, control OFF; preserva
  hashes/inventory y evidencia. Epoch perdido como fronteraD; nuevo cut necesario.
- read(epoch_uuid,attention_after=30min): misma autorización/tenant/creador;
  attention_required nunca causa release ni cron.

Permiso historical.record: usuario activo de ese negocio, session_version actual,
suscripción escribible y flags OFF. Preflight sin locks; gate y revalidación User/negocio FOR SHARE en PG,
BEGIN IMMEDIATE en SQLite. Cambiar sesión/revocar impide nuevas operaciones.

## Identidad, datos y efectos

T0 awareUTC se toma tras gate/control; por tenant generación monotónica.
epoch_uuid/generation/source_scope_version/fence_version/versionrepositorio/entorno
son inmutables. Un active epoch es todo estado distinto de released; invalidated
también ocupa el unique parcial. Control PKbusiness_id, FKcompuesta epoch/generation.
La auditoría append-only guarda actor actual/acción/motivo identificador/instante.

Cut manifest guarda FKepoch y carrierB, generation/T0/scope/entorno, hashes, result,
status scanning/frozen/aborted, boundary_current/certifiable/eligible=false.
Carrier B siempre schema70/diagnostic/certifiable=false; no ALTER de70 ni promoción.
Certificable exige nueva ejecución después de T0, fence validado entre páginas,
freeze bajo gate, source_set_hash=comparison hash y ausencia SOURCE_DRIFT.
Plan/hash/raw/assessment/items son los existentes; no se acredita decimal original
ni historia ambigua. Result BLOCKED por incertidumbre no cambia esas reglas.
Drift→BLOCKED/no certifiable, invalida epoch manteniendo writers bloqueados.

## Enforcement y coste

Application assert_writable se ejecuta dentro de la TX writer antes de fuente/
operation/coverage/counter. HistoricalFenceActive es StateError reconocible, sin
fallback. Guard SQL en las28 fuentes menos anchor (baja/id protegido aparte), dos
contadores; UPDATE solo columnas auditadas más revisión derivada64. Cambiar tenant
valida old/new. PG try advisory antes de lectura control: HistoricalWriterBusy
exige rollback/retry completo, nunca aceptar write sin gate. READ COMMITTED, no
REPEATABLE READ/SERIALIZABLE para estos writers. Admin DDL no es writer soportado.

Scanner/second pass/plan aggregate se paginan con gate/TX breves. No conexión
paralela ni scan fullhistory en cada writer: catálogo instalado + PKcontrol lookup.
El único gate mantenido durante IO es dispatch fiscal/unlink auditado; el scan
no lo hace. Sin epoch el comportamiento financiero conserva regresiones previas.
SQLite tiene contención de writer global; PG gate por tenant.

Scope cerrado C v1 en cut_scope.py: sourcesB; transport status/sent/completed/
updated neutralizados en RawSource C; invoice_event remision/aceptacion/rechazo
excluidos; respuesta terminal previa permitida, nueva remisión no. Diferente hash
semántico del diagnóstico B declarado en el sobre C; no cambiar manifests antiguos.
Todos los documentos entran en membership conservador; OCR/notas no se copian.
Nuevo documento/relink/classification/review/replacement/deletion bloqueado.
PREPARED/APPROVED anteriores conservados pero no autorizados/ejecutados bajo fence.
Recurrencia/bancoCSV/confirmación documental delegan en guards compartidos.

## Recovery y retirada

Tras crash consultar read y reintentar MISMAUUID; no finalmente release.
Invalidate por error y release por decisión del opened_by, con sesión vigente.
Downgrade71→70 solo cuatro tablas nuevas VACÍAS; con epoch o audit o cut durable
falla antes de retirar guards/índices. Con epoch activo no es seguro instalar código anterior sin guards de dispatch/bytes.
Conservar schema y runtime compatible: rollback de schema bloqueado con evidencia.
La compatibilidad código53/schema71 se prueba únicamente sin epoch activo.
Baja de negocio con evidencia falla cerrado, aun released. Sin purga automática.

**diagnosticB ≠ certifiable_inventoryC ≠ importableD**. Certifiable ≠ activation ready.
No producción/copia real/AEAT ni activación.1.9D no autorizada.
