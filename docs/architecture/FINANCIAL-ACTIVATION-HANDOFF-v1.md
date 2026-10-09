# Financial Activation Handoff v1

Contrato interno D. Estado: cierre local CODE-VERIFIED PASS. [Orden](FASE-1.10D-orden.md)
y [ADR022](ADR-022-activation-handoff-generations.md) delimitan su autoridad.

## API y estados

`FinancialActivation(business_id, code_version=...)` expone prepare, authorize y
advance. No tiene rutas, tools, CLI pública, routing IA ni provider adapters.
Cada entrada abre una sola transacción con la infraestructura existente, toma
gate y revalida tenant, usuario activo/sesión y suscripción. IS_PRODUCTION bloquea D.

| Acción | Estado de origen | Resultado | Generación |
|---|---|---|---|
| enable | off | validating → ready → enabled | 1 al último commit |
| abort | validating/ready, nunca enabled | off | 0 |
| pause | enabled | paused | conserva G |
| resume | paused | validating → ready → enabled, un commit | G+1 |

Las etapas de enable tienen recibos propios; solo la última retira el fence.
Cada etapa revalida A FULL exacta. Abort necesita su propia confirmación humana.
Resume usa prueba de recuperación D; no pide que la vieja evaluación A produzca
otra evaluación sobre un estado live que no pertenece al contrato inicial.
ever_enabled es monotónico. El flag global indica disponibilidad, nunca autoridad.

## Solicitud y autorización

ActivationRequest v1 tiene exactamente 26 campos, sin extras ni floats:

- request_version, business_id, request_uuid, action, expected_state;
- expected_control_revision, activation_generation, previous_generation;
- evaluation_uuid, evaluation_content_hash, profile, profile_hash;
- capabilities, capability_grant_hash, history, external_evidence_hash;
- configuration_hash, code_version, schema_version;
- actor_user_id, actor_session_version, permission;
- created_at, expires_at, pause_reason, recovery_proof.

El servidor deriva todos los campos; canonical JSON ordenado y SHA-256 estable.
UUID canónico, hashes hex64, enteros estrictos, UTC con microsegundos y TTL máximo
cinco minutos. action/state/generaciones forman un contrato cerrado. Motivo de
pause tipado; recovery_proof solo en resume. Los importes pertenecen a los contratos
financieros Decimal/EUR existentes; esta solicitud no produce dinero ni EE.

history congela exactamente epoch/manifest/batch/reconciliation UUID, generación
histórica, plan_hash/result_hash/rechecked_hash, cinco storage_hash, T0,
fence_version, source_scope_hash y source_set_hash. No confundir esa generación
histórica con activation_generation.

Perfil v1 y closure ordenada exacta; todas las capabilities necesarias ELIGIBLE,
al menos una financiera. No grants NOT_APPLICABLE, no omission ni extra. A mantiene
su canonical/hash original. Confirmación durable exclusivamente humana con
financial.activation.manage, mismo actor/sesión y hash exacto. Una aprobación
de Operation, mandate o administrador global no autoriza el control plane.

## Persistencia y commit

Migración D añade requests, authorizations, transitions, revisions, generations
y grants; extiende lifecycle, epoch handed_off y bindings de Operations/Auth.
Retiene baseline DDL, testigos de commit y testigos por origen. PostgreSQL añade
verificador privado; no se guardan claims reutilizables como autoridad.

El recibo v1 contiene business/receipt/request/hash/authorization UUID,
estados y revisiones anterior/final, generación, recorded_at y evidence.
Handoff evidence conserva historia y hash externo. Pause evidence conserva IDs
cancelados/revocados y snapshot. Resume evidence conserva prueba D versionada:
pause_receipt_uuid/hash, generation_receipt_hash y snapshot cerrado
(version/configuration_hash/financial_hash/table_hashes).

La FK diferida del recibo a la revisión final evita durable partial handoff.
Al primer enable, el epoch queda terminal handed_off/fence=false/handoff_uuid;
cut certifiable=true y boundary_current=false. Manifest, batch, E, T0, UUID y
hashes originales se conservan. No nuevo epoch, importación o reconciliación
histórica tras ever_enabled. Las lecturas/inspección de evidencia siguen disponibles.

## Frontera live

El mapping C determina capability del command; grant exacto vigente y disponible,
operación APPROVED y autorización humana o mandate actual de la misma G. Ningún
NULL viejo se promueve. El contexto de conexión/TX está ligado a business,
operation UUID, generation, capability y availability comprobada por servidor.
SQL exige el contexto propio y estado/grant/autoridad vigentes; scopes limitan
objetivo, command, EE y relaciones. No válido después de commit ni en otra TX.

Cada efecto tiene testigo deferred → Operations committed. Cada gasto, recibida,
cobro o hecho bancario escrito tiene además testigo deferred → su propia coverage.
No se puede introducir otra fila sin evidencia aprovechando una operación legítima.
Los testigos son inmutables, protegidos y solo prueban el commit, no dan acceso.

Pausa cancela PREPARED/APPROVED live y revoca mandates pendientes. Conserva EE,
source rows, historial, autorizaciones, outboxes y resultados. Resume no elimina
esa terminalización; exige configuración y snapshot sin drift/uncertainty y crea G+1.
Resultados committed se recuperan sin repetir el efecto ni requerir G actual/ON.

Crear/editar borradores y candidatos operativos no genera efectos. Confirmarlos
requiere la nueva frontera. Recurring fuerza draft tras ever_enabled incluso OFF.
Los updates de transporte outbox se conservan; el dispatch sigue bloqueado por
el guard externo hasta política F. No AEAT/Meta/email/Stripe I/O en D.

## Validación y límites

El [cierre](FASE-1.10D-cierre.md) registra matrices, crashes, gates y autoauditoría.
FULL financiero positivo solo se fabrica en fixtures de tests identificadas,
sin debilitar blockers A runtime. Migrador PostgreSQL no puede ejecutar live;
F debe preparar login runtime/clave sin permisos de lectura ni privilegios globales.
SECRET_KEY rotada sin preparar el verificador falla cerrado. P15 ampliará RBAC/SoD.
No real QA, backups, producción, push ni 1.10E–H autorizados aquí.

## Refinamientos demostrados por las pruebas adversariales

El contexto de preparación no permite insertar confirmaciones humanas: SQL
exige explícitamente stage=authorize y la solicitud exacta. Emitir/rectificar
solo permite borrador → enviada, con paid_at NULL. El cobro/match solo cambia
status/paid_at en la factura; no puede aprovechar esa autoridad para reescribir
sus importes. Los testigos por fuente impiden confirmar una segunda fila
huérfana aunque la primera operación y su cobertura hayan terminado.

El gate SQL D conserva el orden C en fuentes nunca activadas. Cuando ever_enabled
es true exige el gate antes del guard live; la transacción de enable toma el
gate del negocio antes de todas las filas. Las pruebas incluyen una sentencia
SQL iniciada antes del enable, detenida entre el gate inicial y el guard, que
se rechaza después del commit. No se conserva autoridad de su snapshot viejo.
