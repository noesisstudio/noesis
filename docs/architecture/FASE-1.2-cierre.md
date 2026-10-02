# Fase 1.2 — Operaciones, idempotencia y autorización durable

Fecha: 2-oct-2026. Base `main` posterior a 1.1 (`7aa116c`), limpio y actualizado
antes de editar. Trabajo en `C:/Users/mikic/Documents/noesis`, checkout de main;
el worktree asociado al chat es anterior. Entrega local sin push/despliegue.
No avanzar a 1.3. Estado final verificable en project-state.json y Registro-QA.

## Archivos y alcance

Creados: `src/noesis/financial_operations/{__init__,contracts,repository,service,schema}.py`;
`tests/{financial_operations_contract,test_financial_operations,postgres_financial_operations,financial_operations_worker}.py`;
`docs/architecture/{ADR-006-financial-operations,FINANCIAL-OPERATIONS-v1,FASE-1.2-cierre}.md`.

Modificados runtime: migrations.py registra 62; action_review.py **solo docstring**.
db.py: baja actual intacta sin evidencia; bloqueo explícito si hay operaciones/autorizaciones.
Verificador DDL: reconoce PK/UNIQUE declarados dentro de CREATE TABLE.
CI: nuevo paso de contrato/concurrencia PostgreSQL. Documentación: AGENTS,
arquitectura/índice/plan, guías 01/03/06/08, mapa, decisiones, estado JSON/Markdown,
tareas, bitácora y QA. No cambia config, dependencias, rutas, herramientas,
documentos, WhatsApp, facturación, banco, gastos/recibidas o VERI*FACTU.

Inventario de los 32 archivos de esta entrega (paths desde la raíz):

```text
.github/workflows/ci.yml
AGENTS.md
docs/Arquitectura.md
docs/Decisiones.md
docs/Estado-actual-main.md
docs/Mapa-codigo.md
docs/Registro-QA.md
docs/Registro-cambios.md
docs/Tareas-vivas.md
docs/architecture/ADR-006-financial-operations.md
docs/architecture/FASE-1-plan.md
docs/architecture/FASE-1.2-cierre.md
docs/architecture/FINANCIAL-OPERATIONS-v1.md
docs/architecture/README.md
docs/areas/01-vision-general.md
docs/areas/03-cerebro.md
docs/areas/06-rgpd-y-seguridad.md
docs/areas/08-financial-core.md
docs/project-state.json
src/noesis/action_review.py
src/noesis/db.py
src/noesis/financial_operations/__init__.py
src/noesis/financial_operations/contracts.py
src/noesis/financial_operations/repository.py
src/noesis/financial_operations/schema.py
src/noesis/financial_operations/service.py
src/noesis/migrations.py
tests/financial_operations_contract.py
tests/financial_operations_worker.py
tests/postgres_financial_operations.py
tests/test_financial_operations.py
tests/test_platform.py
```

Precisión al diseño inicial: la orden de 1.2 exige ahora tablas de operaciones y
autorización, originalmente agrupadas en 1.3. Se implementan solo estas; no
economic_events/economic_event_links ni productores, GL, asientos, Open Items,
Tax Ledger, reporting o cambios fiscales. Los flags siguen apagados.

## Schema, API y garantías

[Especificación completa](FINANCIAL-OPERATIONS-v1.md) y [ADR-006](ADR-006-financial-operations.md).
Migración 62, única: dos tablas, UUID/referencias/timestamps tipados en PostgreSQL,
TEXT exacto en SQLite, contenido monetario JSON string, FKs de negocio/actor y
autorización/operación/hash, uniques/índices y guards equivalentes. Rollback vacío
permitido; con cualquier evidencia/operación falla sin perderla.

API: prepare, authorize, execute (claim por lock + commit interno de resultado),
recover, finish_without_effect(rejected/cancelled), grant_mandate/revoke_mandate.
Sin dispatcher/workflow/bus/CQRS, pools nuevos o productores. Executor/lector de
revisión son código de servidor, sobre la conexión prestada; solo fixtures de
tests los invocan. Dominio/efecto real se valida e integra en sus fases futuras.

Idempotencia: identidad del canal estable, unique por negocio/namespace/key,
INSERT ON CONFLICT atómico y comparación de hash+contenido. Mismo contenido
recupera resultado durable sin reejecutar; distinto contenido da conflicto;
identidades distintas permiten operaciones iguales. Lock de fila PostgreSQL /
BEGIN IMMEDIATE SQLite; efecto sintético y resultado comparten commit exterior.
No estado durable executing; crash revierte ambos y deja approved, nunca committed.

Autorización: comprobación actual de usuario/negocio/sesión/creador en cada acceso;
suscripción/no demo en escrituras. Confirmación humana enlazada al hash/revisión;
mandato exacto humano previo con caducidad/revocación; desconocido histórico sin
actor/aprobación originales ni permiso de ejecutar. Evidencia independiente de
pending; puede sobrevivir a eliminarse la propuesta. Ningún flujo legacy la usa
todavía. La IA no controla claves, UUID, negocio, actor o permisos.

## Pruebas

- Último contrato dirigido SQLite: **66/66**, 18,002 s (29 operaciones, 21
  Economic Events y 16 Money/flags/persistencia). PostgreSQL 16.15 real: **32/32**,
  5,192 s (28 invariantes comunes + 4 de conexiones/procesos/crash).
- Regresión focal de DDL/baja y nuevo caso de conservación: **8/8**, 2,967 s.
  Dos procesos reservan la misma entrada o detectan conflicto; dos procesos y dos
  conexiones ejecutan una sola vez. os._exit(17) después del INSERT sintético
  revierte la transacción realmente; reintento posterior produce un único efecto.
- Primera suite completa: **1445 ejecutadas, 3 fallos** (915,460 s). Dos guards
  PostgreSQL necesitaban SQLSTATE 23514; el verificador de orden no reconocía
  PK/UNIQUE de CREATE TABLE; la cobertura estructural de baja exigía contemplar
  las nuevas tablas. Corregidos, sin rebajar ningún guard ni borrar evidencia.
  Se añadió un test común de baja y se repite la suite final: **1446/1446 OK**, 913,915 s.
- Migraciones finales: SQLite 61→62→61→62 conserva negocio/usuario y
  0→62→0→62 correcto. PostgreSQL schema aislado: 61→62→61→62 preserva ambos.
  Cada contrato PostgreSQL crea instalación limpia hasta 62. Bajada con datos
  durables bloqueada y sin pérdida en ambos motores. UUID nil/malformados rechazados.
- Humo PostgreSQL en base nueva local: migración histórica 32→62 conserva factura
  emitida e invariantes; **36 rutas sin 5xx**. El script imprime su encabezado
  histórico «32→35», pero versión consultada final es 62.
  Gates adicionales en schema aislado: código base d3740a0 (schema 53) sobre BD 62
  emite/cobra/exporta sin cambios; rollback 62→55→54→53→54→55→62 conserva datos
  e inmutabilidad. Conversación/deduplicación/reserva, marketing y privacidad
  HTTP/permisos/aislamiento/exportación/avisos correctos.
- Ruff src/tests, Bandit (high severity/high confidence), secretos incluyendo
  archivos nuevos, uv lock --check, pip-audit, Node **3/3**, enlaces locales,
  diff --check y verdad documental: correctos. pip-audit excluye el paquete
  local noesis que no está en PyPI; dependencias sin vulnerabilidades conocidas.
- Auditoría AST: el único import de financial_operations fuera del paquete es
  migrations→schema. Ningún productor importa service; flags false, sin nuevas
  dependencias. No hubo CI remota, red AEAT/Meta ni despliegue.

## Autoauditoría (§44 del Master Plan)

| Pregunta | Respuesta de 1.2 |
|---|---|
| ¿Cuál es el Economic Event? | Ninguno durable; la operación es una solicitud, no un hecho económico producido |
| ¿Genera asiento? | No; GL/posting fuera de alcance |
| ¿Qué cuentas afecta? | Ninguna; no hay plan contable ni movimientos nuevos |
| ¿Genera TaxLines? | No; Tax Ledger fuera de alcance |
| ¿Genera/compensa OpenItems? | No; no hay AR/AP ejecutable |
| ¿Qué dimensiones tiene? | Negocio, identidad de entrada, destino/request y revisiones; sin motor de dimensiones |
| ¿Qué permisos requiere? | Contexto autenticado, usuario activo/sesión vigente, creador y negocio; escrituras además suscripción/no demo |
| ¿Es reversible? | prepared/approved admiten rechazo/cancelación; committed no se reescribe ni cancela como reversión |
| ¿Es idempotente? | Unique atómico, locks, hash+contenido, resultado durable; pruebas en conexiones/procesos independientes |
| ¿Funciona en período cerrado? | Infraestructura no contabiliza ni decide cierre; reglas de período del productor futuro, sin inventarlas |
| ¿Cómo se audita? | Request/revisión inmutables, recibos mínimos, timestamps y resultado/hash; no una firma criptográfica |
| ¿Cómo se prueba? | Contrato en dos motores, proceso terminado realmente, conflictos, rollback, timeout, permisos, migraciones y suite legacy |

Auditoría adicional: una sola conexión/pool, filtros por negocio, propiedad antes
de recuperar contenido, FKs/guards, sin floats canónicos, clones inmutables,
revisión actual antes de efecto, autorización durable antes de ejecución,
mandato revalidado, estado committed ligado a resultado, sin edición financiera
legacy ni conexiones de productores. Hash no sustituye identidad ni autorización.

## Criterios PASS/FAIL

| Criterio solicitado | Estado | Evidencia / límite |
|---|---|---|
| Operación independiente de éxito, campos mínimos y timestamps | PASS | Dos tablas, request/result versionados; cinco estados cerrados |
| UUID válido y business obligatorio | PASS | Contrato BIGINT positivo/UUID no nil, UUID nativo PG, CHECK SQLite |
| Claves repetidas / namespaces independientes | PASS | Unique compuesto, test de namespace y identidad estable |
| Misma identidad + mismo request | PASS | Recupera UUID/request original; tras commit también resultado |
| Misma identidad + contenido distinto | PASS | ConflictError, bytes/hash originales preservados |
| Dos operaciones legítimas iguales | PASS | UUID/entradas distintas; dos efectos sintéticos permitidos |
| Entradas para siete canales | PASS | Factories deterministas; sin conectar canales |
| IA sin autoridad sobre clave/UUID/negocio | PASS | No endpoint/tool; claves reservadas rechazadas; contexto servidor |
| Contenido completo explícito / defaults congelados | PASS | Sobre v1 + parameters congelados; validación semántica futura obligatoria |
| Orden de campos → mismo hash | PASS | Canonicalización determinista y orden de keys probado |
| Cambio relevante → hash distinto | PASS | Destino, importe, fecha, motivo, revisión y parámetros probados |
| Ningún float monetario, precisión exacta/EUR | PASS | Rechazo en request/params/result; JSON strings Decimal |
| Confirmación humana durable válida | PASS | Recibo de actor/sesión/hash/revisión confirmado antes de execute |
| Propuesta temporal eliminada | PASS | Recibo sobrevive a borrar pending; ningún productor conectado |
| Revisión antigua rechazada | PASS | authorize/grant/execute exigen lector cuando aplica; fallo antes de efecto |
| Autorización inexistente u otra empresa | PASS | Servicio/constraints/guards; acceso uniforme denegado |
| Permiso/usuario/sesión revocados | PASS | Revalidación incluso replay committed; suscripción consulta solo recover |
| Mandato previo validado | PASS | Hash/revisión/actor/sesión, caducidad/revocación revalidados |
| Historia sin autorización original | PASS | Actor original null, recorded_by separado, no approved/execute |
| Negocio + identidad + permisos antes de información/efecto | PASS | Propiedad por created_by; usuario del mismo negocio tampoco obtiene UUID ajeno |
| Misma entry_key en empresas distintas | PASS | Reserva independiente y aislamiento de datos |
| PostgreSQL: dos conexiones y procesos simultáneos | PASS | Locks/unique; una ejecución; conflicto/replay según contenido |
| SQLite transaccional compatible | PASS | BEGIN IMMEDIATE y dos conexiones; infraestructura get_conn existente |
| Timeout después de commit | PASS | Respuesta perdida simulada; misma entrada devuelve resultado sin ejecutar |
| Fallo antes/después del efecto y al guardar resultado | PASS | Rollback conjunto y estado anterior approved |
| Crash real, ningún falso committed | PASS | Proceso terminado después de INSERT; cero efectos antes de reintento |
| action_review revisado, frontera durable definida | PASS | Docstring + protocolo futuro; flujo actual preservado |
| Migración limpia/vigente, dos motores | PASS | 0→62, 61→62, ciclos/reversión vacía y preservación legacy |
| Preservar aislamiento/exactitud y no tocar facturación/VF | PASS | FKs/guards y dinero string; código productores/fiscal intacto |
| API interna mínima prepare/authorize/execute/recover/reject/cancel | PASS | Commit del resultado interno; sin workflow engine/bus/CQRS |
| Baja legacy y conservación de evidencia nueva | PASS | Sin evidencia igual; con operación o mandato error explícito y cero borrados |
| Suite/regresiones action_review/WhatsApp/facturación/VF | PASS | **1446/1446 OK**, 913,915 s |
| Ruff/security gates | PASS | Ruff, Bandit, secretos, audit/lock; Node/documentación |
| Documentación obligatoria y autoauditoría | PASS | ADR/contrato/guías/estado/QA/bitácora/mapa/decisiones y §44 |
| Sin eventos durables, links, productores, asientos, Open Items, Tax/reporting | PASS | Tablas excluidas comprobadas; AST no importa servicio desde productores |
| Flags apagados y no avanzar a 1.3 | PASS | Config/JSON verificados; orden siguiente no autorizada |

El criterio de integración futura no equivale a productores ya conectados ni a
validación de negocio completa: están expresamente fuera de 1.2. Suite final
correcta: **1.2 cerrada, 36 PASS / 0 FAIL**; 1.3 no iniciada ni autorizada.

## Riesgos y límites prácticos

- Principal/factories solo son API de servidor; las futuras entradas deben validar
  sesión, firma/transporte, pertenencia y recibo estable. No hay aún ese cableado.
- El request valida estructura/precisión; cada puente debe congelar todos los
  defaults/snapshots pertinentes, validar semántica/target y seleccionar ejecutor
  de confianza por tipo. No presentar este núcleo como motor financiero listo.
- Callback exclusivamente transaccional local: una llamada externa o commit propio
  invalidaría la garantía de rollback. No hay ejecutores financieros registrados.
- Mandatos v1 son exactos al contenido/revisión, no autorizaciones abiertas para
  fechas/importes variables. Sesión renovada invalida aprobación previa; para
  ejecutar con otra confirmación, cancelar y preparar otra identidad explícita.
- Retención/exportación/cierre con conservación y actor de automatización requieren
  integración antes de productores/activación. No borrar durable para permitir rollback.
- Hash no es firma y no protege frente a un operador con privilegios de esquema.
  Los guards defienden la aplicación de mutaciones accidentales, no certifican ley.

Cambios de comportamiento financiero del producto: **ninguno**; nueva
infraestructura/esquema y docstring. Baja sin evidencia: comportamiento preservado.
Con evidencia de estas tablas internas: ValueError explícito antes de borrar datos;
no es una política de retención legal ni una implementación de cierre conservando datos. Sin operaciones financieras reales desde
canales, sin efectos fiscales/contables y sin cambios de flags. CI remota y
despliegue de esta entrega no realizados.

Diagnóstico: buscar negocio/namespace/key/UUID, estado, request/hash, versión de
sesión, autorización/revisión y mandato. No registrar contenido/conversación en logs.
Rollback de código no elimina evidencia; bajar 62→61 solo con tablas vacías.
Si ya hay datos, conservar esquema y resolver con una migración explícita.
