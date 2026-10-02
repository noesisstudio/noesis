# ADR-006 · Identidad de operación, autorización y resultado durables

- Estado: aceptado por orden de ejecución de 1.2, 2-oct-2026.
- Alcance: infraestructura interna; sin productores ni persistencia de Economic Events.
- Especificación: [Financial Operations v1](FINANCIAL-OPERATIONS-v1.md).

## Decisión

Una operación es una solicitud con identidad independiente de su contenido y de
su resultado. El servidor genera `operation_uuid`; el canal autenticado deriva
`entry_namespace/entry_key` de un recibo estable. Nunca se aceptan esas claves en
argumentos de IA. Unique `(business_id, entry_namespace, entry_key)` y reserva
atómica `INSERT ... ON CONFLICT DO NOTHING`; comparar después hash **y bytes**.
Misma identidad/contenido recupera el registro; otro contenido da conflicto sin
mutarlo. Identidades distintas permiten solicitudes legítimas iguales.

Estados: prepared, approved, committed, rejected y cancelled. El servicio toma
un lock de fila en PostgreSQL o BEGIN IMMEDIATE en SQLite. No hay lease ni estado
durable executing: el ejecutor y el resultado comparten la transacción de
`db.get_conn()` mediante FinancialSession. La fila se marca committed dentro de
esa transacción, y solo su commit hace durable el efecto/resultado. Crash o fallo
revierte ambos; queda la aprobación anterior para un reintento. No cubrir efectos
externos con esta garantía: deben usar outbox en su fase, nunca este callback.

La evidencia de aprobación es append-only, separada de propuestas temporales:
operación/hash/revisión, actor autenticado, permiso validado, canal y timestamp.
Un registro histórico desconocido tiene actor/aprobación originales null y no
habilita ejecución. El usuario que lo documenta se conserva como recorded_by.
Mandatos: concesión humana durable previa, contenido exacto por hash, caducidad,
revocación y enlace desde cada autorización de operación. Sin reglas recurrentes
de importe variable, roles nuevos ni motor genérico de workflow.

Cada acceso comprueba negocio, usuario activo, versión de sesión y propiedad de
operación. Escrituras comprueban además suscripción y bloqueo de demo. La base
impone referencias compuestas y guards de transición/evidencia. No existe acceso
por UUID sin permiso ni excepción administrativa entre empresas. Los mandatos se
revalidan antes del efecto. PostgreSQL mantiene locks sobre usuario/negocio para
ordenar una revocación concurrente con la ejecución. El cambio de sesión invalida
la autorización anterior: no se renueva silenciosamente.

## Precisión de alcance y alternativas descartadas

El plan inicial situaba persistencia de operaciones/autorizaciones en 1.3. La
orden posterior de 1.2 exige expresamente estas tablas y pruebas de concurrencia;
esa orden prevalece. El trabajo futuro de 1.3 corresponde a Economic Events y
requiere una nueva orden explícita; no se inicia ahora.

Descartados: deduplicar solo un evento posterior, SELECT→INSERT sin unique,
huella como identidad, marcar ejecutado antes del commit, aprobación en una fila
temporal eliminada, inferir autorización humana de históricos, mutex solo de
proceso, framework de workflow/bus/CQRS y conexiones paralelas por repositorio.

## Consecuencias

Migración 62 crea solo financial_operations/financial_authorizations e índice
compuesto de usuarios necesario para sus FKs. Dinero solo dentro de JSON TEXT
canónico como strings, en ambos motores; ninguna columna FLOAT nueva. Rollback
vacío permitido; con registros bloquea para conservar evidencia/resultados.
Baja actual conserva comportamiento cuando están vacías; con evidencia se bloquea
explícitamente antes de borrar cualquier dato. Retención, exportación/cierre con
conservación de estas tablas y actores de automatización deberán
integrarse antes de activar productores, sin inventar una política legal aquí.
