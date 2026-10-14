# Corrective3 — decisión humana autorizada sobre retención legacy

## Diagnóstico demostrado

T1 tras32→75 con factura histórica y T2 antes de downgrade55 son canonical75
exactos. Hash completo actual/expected en ambos:
cde6d981f515660e0d3421088096cb8905c63554fe63e70e89dcdbd0a2de15f3.
Fresh0→75 tiene el mismo perfil. No DDL data-dependent de schema75 observado.
El fallo ocurre en el postvalidator55 dentro de la TX, no al comenzar la bajada.

34 claves extra pertenecen a invoices.pending_fields (migration58),
assistant_messages.actor (59) y whatsapp_ingress con sus columnas, constraints,
índices y secuencia (60). No claves missing/changed. Las callbacks down conservan
estos objetos expresamente para no perder datos ni recibos de deduplicación.
No comparten causa con V2. No está demostrado un error en esas migrations.

## Decisión aprobada y candidato implementado, PostgreSQL incompleto

Reconocer exclusivamente perfiles completos de compatibilidad de retención para
el propietario de migración en53/54/55/58, los destinos usados por el release gate.
Los perfiles canonical existentes permanecen byte idénticos. Deltas revisados
cerrados derivados de los descriptores históricos58–60; igualdad del perfil
COMPLETO, no nombres ni ignore-extra. Nunca aceptar otra columna/trigger/constraint.

Sólo bajo lock exclusivo del migrador; resultado TECHNICAL_ONLY con id/hash
propios. Nunca VERIFIED, binding, require_compatible/runtime, startup, readiness,
serving o ejecución financiera. No variante75 ni fallback. No editar migrations
históricas, borrar filas, drops de columnas conservadas ni limpiar datos para pasar.
Al volver a75 debe recuperarse EXACTAMENTE canonical75.

Regresiones requeridas: retención de rows/snapshots, fiscal immutability, drafts
incompletos/pending inbox/durable links bloquean; consumidores rechazanTECH incluso
con lock exclusivo; variantes alteradas/objetos desconocidos rechazan; vuelta75exacta.

El titular aprobó expresamente esta excepción al freeze de §1: sólo perfiles
TECHNICAL_ONLY exactos53/54/55/58. Los canonical53–75 permanecen intactos.
Implementado en schema_retention.py: delta58pending_fields,59actor sin su índice
eliminado por down59, y delta60 completo. Igualdad de TODOS los objetos;
no flags booleanos ni nombres como sustituto de identidad. Id propio:
postgres/retention-owner/{version}/v1; SHA256 canonical del perfil completo.

| Versión | SHA256 del perfil técnico completo |
|---|---|
|53|4b86e9ac505049fd7530a4086ce109ea723db6507fc4b21deedd936c40f2aea5|
|54|00f1b30e9d0c3be2fe77910a0bc072df242c900c01900acec6b572978ec5c15b|
|55|fe69f4d396605716b3a25c7d655943f247253315c83a8242f047cf682bd0f2ec|
|58|de02550ecab527f23c047261141285ccf630aede5ba15b3014c06aa92d5910bc|

Owner: lockexclusivo, non-production, POSIX nonroot; namespace tiene sólo lo;
server listener vacío o127.0.0.1, dirección socket/127.0.0.1 y data_directory
local de cluster desechable nv2- bajo temp, directorio0700 del uid actual.
Nada de claims de aislamiento ni conexión propia. Sin estos hechos, rechazo.
Inspect devuelve TECHNICAL_ONLY; require_canonical/compatible/runtime/binding
rechazan incluso bajo lockexclusivo. Regresiones cubren retención parcial,
mutada, missingconstraint, unknownowned/extra/future; vuelta75exacta obligatoria.

No callbacks históricas, migrations, datos ni perfiles canonical modificados.
El candidato no está validado en PostgreSQL: WSL se ha interrumpido repetidamente.
No serving/readiness/activation/backup serving/PilotGate/REAL autorizado.
No commit/push/CI hasta dirigidos completosPASS.

V2 es independiente: el parser transforma BETWEEN enAND anidado y reparse de
pg_dump aplana eseAND. Los2129 probes idénticos y metadataCHECK/tipoNUMERIC sin
cambios permiten una normalización estructural MUY estrecha de esa forma concreta,
sin ordenar booleanos ni eliminar casts/paréntesis globalmente. Implementada por árbol estructural cerrado en schema_check_identity.py; runtime
V2 fresco todavía no completado por WSL. No se declara PASS remoto.
