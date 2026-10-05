# Cierre Fase 1.10A — contratos y eligibility

2026-10-05. Candidato en `codex/phase-1-10a`, base local `e95c19b`.
Implementación exclusivamente A; no merge/push ni despliegue. Commit identificable
mediante `git log -1 --format=%H -- docs/architecture/FASE-1.10A-cierre.md`.
El hash exacto del commit se entrega en el informe de conversación; no se incluye
un hash autorreferente imposible dentro del mismo commit.
Resultado técnico: PASS de los18 criterios A, con límites explícitos y aceptación
humana pendiente. No es ready ni enabled.

[Orden humana](FASE-1.10A-orden.md), [contrato completo](FINANCIAL-READINESS-v1.md),
[ADR019](ADR-019-financial-readiness.md), [plan de referencia](FASE-1.10-plan.md).
1.9 cerrada técnicamente con limitaciones por instrucción humana; 1.9F conserva
PASS WITH LIMITATIONS. Esta entrega no aumenta su cobertura real ni acredita
producción. No se ha iniciado 1.10B.

## Resultado e infraestructura

Tres tablas nuevas en migración74 `evaluacion_readiness_financiera`:

| Tabla | Contrato |
|---|---|
| financial_activation_control | Una fila por business, off/validating, revisión CAS lógica, generation0, ever_enabled=false, perfil/puntero/provenance |
| financial_readiness_evaluations | UUID por tenant, perfil/policy/code/schema/actor/session, contexto histórico/hash/config/fuentes, building→final, resultado/canonical/hash y fechas/expiry |
| financial_readiness_capabilities | Las15 capacidades por evaluación, outcome cerrado, reason codes, dependency proof y evidencia/hash |

`FinancialReadinessEvaluator` usa FinancialSession y transacción exterior, business
gate y locks de sesión actuales. Revalida suscripción y permiso propio
`financial.readiness.evaluate`; usuario autenticado activo de cuenta escribible
puede evaluar, nunca activar/autorizar dinero. No nuevo rol/grant de activación.
Read exige mismo usuario actual/tenant. Referencias históricas ajenas se deniegan.

Solo escribe esas tres tablas; no administra una conexión/commit/rollback propios.
Off no cambia al evaluar. SQL no admite ready/enabled/paused, generation distinta
de0 ni ever_enabled=true. Evaluación final/capabilities no se actualizan ni borran;
FK compuesta impide pointer/proof de otro tenant. Todas las15 filas se exigen antes
de finalización; FULL exige E PASS frozen y boundary/fence coincidentes enSQL.
El repositorio valida hashes, columnas, contrato de proof y semántica del perfil/
closure/outcome al recuperar. SQL privilegiado que elimina constraints/triggers
queda fuera del modelo de protección; ningún hash equivale a firma o autoridad.

Downgrade74→73 solo con las tres tablas vacías; conserva cualquier evidencia.
Matriz de compatibilidad explícita B70–74/C71–74/D72–74/E73–74; readiness solo74.
Migraciones63–73 intactas. db.py añade únicamente nombres para conservación/baja;
no se introdujo lógica financiera allí.

## Catálogos, reglas y decisiones

Capacidades15: invoice.issue, invoice.rectify, customer_payment.record,
supplier_invoice.confirm, supplier_invoice.correct, supplier_invoice.void,
expense.confirm, expense.void, bank_transaction.import, bank_transaction.match,
invoice.fiscal_cancel, channel.web_financial, channel.whatsapp_financial,
provider.aeat_dispatch, provider.email_delivery. No extensiones arbitrarias.
Perfil/policy/evaluación v1; cierre transitivo explícito en contrato/tablas.
Emisión incluye rectificación/web y, con modoVF actual, cancelación fiscal/AEAT.
Una dependencia bloqueada bloquea su consumidor, sin esconderla enUI.

Razones18: HISTORY_PENDING, RECONCILIATION_BLOCKED, RECONCILIATION_MISSING,
BOUNDARY_INVALID, SOURCE_DRIFT, UNSUPPORTED_HISTORICAL_INVOICE,
CAPABILITY_DEPENDENCY_BLOCKED, FISCAL_CAPABILITY_INCOMPLETE,
BANK_EVIDENCE_UNVALIDATED, PROVIDER_PREFLIGHT_MISSING, PRIVACY_NOT_READY,
EXPORT_NOT_READY, VOLUME_OUTSIDE_POLICY, PERMISSION_DENIED, CONTEXT_CHANGED,
CONTROL_INVALID, FISCAL_PROVIDER_NOT_APPLICABLE, CONTINUITY_NOT_IMPLEMENTED.

FULL solo sobre perfil exacto y todo su cierre. PARTIAL propone otro perfil menor
y requiere nueva evaluación; nunca ready. BLOCKED transversal con C/D/E negativa,
boundary inválida/drift/volumen. Invoice historical v2 y registro_anterior no se
promueven. Authorization histórica no satisface permiso ni autoridad live.

Vacío contrasta scope C completo, membership/referencias y fuentes relacionadas,
operaciones live preparadas/aprobadas y outboxes no terminales. Un borrador no es
hecho económico; no se acredita vacío contando únicamente facturas. El único
FULL mínimo demostrado es Web sin comandos en fixtures vacíos con E PASS.
Privacy/export/provider/continuidad ausentes siguen blocked. not_applicable solo
AEAT con modoVF=false y razón/prueba de configuración actual verificable.

SHA256 canónico sin float incluye perfil, closure, contexto/control, actor/sesión,
boundary/E/config/fuentes/razones/outcome. PropiaUUID/reloj/revisión informativa
excluidos. MismaUUID+contexto devuelve mismo resultado; distinto contexto/perfil
conflict CONTEXT_CHANGED. NuevaUUID y mismo estado lógico conserva content hash.
Expiry no muta evidencia ni fence; resultado caducado no es candidato futuro.
Ese predicado puro no sustituye revalidación futura ni consume/hace handoff.

No diferencias de alcance respecto a orden aprobada. Decisiones concretadas:
permiso de evaluación para usuario actual, límite conservador64items/300s,
NA fiscal solo con prueba tipada, retención ante baja y tres razones adicionales.
No attestations simuladas, flags nuevos, autoridad/grants o tablas de B–F.

## Archivos creados y modificados

Creados:

- `src/noesis/financial_activation/__init__.py`, `contracts.py`, `evaluator.py`, `repository.py`, `schema.py`.
- `src/noesis/financial_history/schema_compatibility.py`.
- `tests/financial_readiness_contract.py`, `test_financial_readiness.py`, `postgres_financial_readiness.py`, `test_financial_readiness_migrations.py`.
- `docs/architecture/ADR-019-financial-readiness.md`, `FINANCIAL-READINESS-v1.md`, `FASE-1.10-plan.md`, `FASE-1.10A-orden.md`, este cierre.

Modificados:

- `src/noesis/migrations.py`, `db.py`, `financial_history/service.py`, `cutoff.py`, `importer.py`, `reconciliation.py`.
- `tests/test_financial_history.py`, `.github/workflows/ci.yml`.
- `AGENTS.md`, `docs/architecture/README.md`, guías08/01/06.
- `docs/project-state.json`, `Estado-actual-main.md`, `Tareas-vivas.md`, `Mapa-codigo.md`, `Arquitectura.md`, `Decisiones.md`, `Registro-cambios.md`, `Registro-QA.md`.

## Verificación local

Fixtures exclusivamente sintéticos. PostgreSQL18.6 localhost en cluster nuevo
descartable `/noesis_ci`, cada clase con schema UUID; no se usó Noesis19FQA ni
se consultó producción. SQLite en carpetas temporales. Sin nuevo proveedor/dependencia.
Cluster PostgreSQL sintético detenido después de las pruebas.
Los cinco flags permanecen OFF; cada flag encendido deniega evaluación.

| Gate | Estado/evidencia |
|---|---|
| SQLite específico y migration | PASS28 pruebas, 78.917s |
| PostgreSQL específico y migration/concurrencia | PASS29 pruebas, 19.141s |
| Regresión PostgreSQL relacionada | PASS410 pruebas, 347.762s |
| Suite completa local | PASS1828 tests, 2093.223s, cero failures/errors, dos skips existentes |
| Ruff | PASS src/tests |
| Bandit security CI (-lll -iii) | PASS |
| Dependency audit | PASS pip-audit, sin vulnerabilidades conocidas; proyecto local no publicado excluido de PyPI |
| Secrets incluyendo archivos nuevos | PASS escaneo versionado y archivos nuevos preparados |
| Project/documentation truth | PASS esquema/precios/estado y obligaciones documentales del diff preparado; revalidación del commit al cerrar |
| Git diff/check | PASS |
| Documentación/compatibilidad/inspección AST | PASS623 enlaces locales sin roturas; funciones/entradas previas intactas; formato nuevo con AST idéntico |
| Frontend JS sin red | PASS9 pruebas |
| CI remoto/publicación | NO ejecutados, sin push |

Cobertura: vacío con E PASS/missing, C/D/E BLOCKED, drift/corte inválido, contexto
ajeno, invoice historical, registro_anterior, closure fiscal, PARTIAL, NA válido/
inválido, sesión/permisos/tenant, retry/conflict/caducidad/determinismo, SQL final/
capability immutable, anti-enabled/ever_enabled/generation, cross-tenantpointer,
flags, volumen, snapshot global, rollback exterior, borrador/pendingoperación/
dispatch incierto, no calls a EE/execute/reconcile/red, baja conservadora.
Concurrencia PG de mismaUUID devuelve una única evaluación idéntica.

Snapshot de todas las tablas previas, esquema metadata incluido, antes/después:
solo cambian las tres tablasA. Sources/EE/Operations/Auth/history/fiscal/banco/
channels/flags idénticos. Fallo exterior revierte nuevas filas. Pruebas de drift
eliminan temporalmente guards únicamente en fixtures descartables para simular
corrupción; escritura normal de fuente bajo fence se rechaza.

SQLite prueba74→73→74 y74→0→74; PG74→73→74. Intento PG hasta cero detectó fallo
preexistente en downgrade antiguo bank_reconciliation: DROP TRIGGER sin ON.
No se reparó migración antigua fuera de alcance. Ciclo A enPG pasa por separado.
Esa limitación no se presenta como PASS de rollback PG completo hasta cero.
Una pasada inicial de suite con código anterior a la corrección de conservación
se detuvo para liberar recursos. Solo la suite final se usa como gate de cierre.

## Criterios de aceptación

Cada criterio se corresponde con orden/test/inspección, no con readiness productiva.

| Criterio | Estado |
|---|---|
| Alcance A y separación evidencia/autoridad/activación/ejecución | PASS |
| Catálogo cerrado15/perfiles v1 exactos | PASS |
| Closure/dependencia fiscal y PARTIAL nunca ready | PASS |
| Tres tablas aditivas/control0/OFF/noenabled | PASS |
| Evaluator prestado/permiso/sesión/tenant | PASS |
| Boundary/E/config/fuentes/volumen actuales | PASS |
| C/D/E BLOCKED transversales/invoicev2/registroanterior | PASS |
| Emptyproof con fuentes relacionadas/pending/dispatch | PASS |
| Reason codes cerrados/NA tipado con prueba | PASS |
| Idempotencia/conflict/hashdeterminista/expiry | PASS |
| SQL guard final/capability/delete/tenant/ever/enabled | PASS |
| Side effects solo tres tablas nuevas/rollback | PASS |
| Migration74/matriz explícita/63–73 intactas | PASS |
| SQLite y PostgreSQL/migración propia | PASS |
| Suite/regresiones y gates completos | PASS |
| Cinco flagsOFF/no provider I/O ni routing/fence/producción | PASS |
| Gobernanza heredable/1.9 cerrado con límites/F inalterado | PASS |
| Commit dedicado sin merge/push/main/1.10B | PASS; referencia git del encabezado y hash exacto entregado |

## Riesgos y límites

No capacidades financieras habilitables: privacy/export, continuidad, productores
fiscales/providers y banco permanecen pendientes. E PASS histórico no garantiza
continuidad live. Toda factura económica previa bloquea emisión/rectificación/
cobro; no se resuelven antecedentes de capturas previas ni su continuidad futura.
Escaneo actual conserva gate y consulta relacionados completos; 64items es
política conservadora, no SLO ni autorización de mayor escala.
Permiso solo de evaluación; futuros roles/grants/autoridad requieren diseño propio.
Retención conservadora nueva no acredita política RGPD/export completa ni plazo
legal: no se fijan plazos productivos. No datos personales ni secretos nuevos enGit.
Runtime financiero/canales existentes sin rutas nuevas; única ampliación de baja
es conservar nueva evidencia cuando exista. No merge/deploy/producción/QA real.
No se afirma compatibilidad PG hasta cero ni CI remoto verde sin ejecutarlos.

## Autoauditoría obligatoria (20 respuestas)

| # | Pregunta | Respuesta/evidencia |
|---|---|---|
| 1 | ¿Puede A activar un business? | NO; sin API ni estado enabled |
| 2 | ¿Puede liberar un fence? | NO; SELECT y snapshots |
| 3 | ¿Puede producir EE? | NO; sin append ni writer, snapshots |
| 4 | ¿Puede ejecutar Operations? | NO; sin execute, snapshot |
| 5 | ¿Puede hacer provider I/O? | NO; sin adaptador/llamada y pruebas |
| 6 | ¿Puede PARTIAL llegar a ready? | NO; otro perfil/evaluación obligatorios |
| 7 | ¿Puede ocultar C/D mediante exclusions? | NO; blockers transversales |
| 8 | ¿Puede registro_anterior ser pago real? | NO; D y no vacío |
| 9 | ¿Puede desbloquear invoice historical v2? | NO; razón explícita |
| 10 | ¿Puede cambiar cinco flags? | NO; solo lectura y snapshot |
| 11 | ¿Puede SQL directo marcar enabled? | NO; CHECK/guards |
| 12 | ¿Puede modificar evaluación final? | NO; UPDATE/DELETE rechazados |
| 13 | ¿Puede usar E PASS de otro contexto? | NO; tenant/boundary/hash/proof |
| 14 | ¿Puede sesión vieja evaluar? | NO; revalidación con locks |
| 15 | ¿Puede cruzar tenants? | NO; filtro/FK/permisos |
| 16 | ¿NA requiere evidencia? | SÍ; razón/prueba/config actual |
| 17 | ¿Emisión cierra dependencias fiscales necesarias? | SÍ; modoVF actual añade cancel/AEAT |
| 18 | ¿Resultados deterministas? | SÍ; perfil/config/proof canónicos, clock/UUID propios fuera |
| 19 | ¿Runtime financiero existente conserva comportamiento? | SÍ; rutas/canales/flags intactos y regresiones; nueva evidencia conservada al dar baja |
| 20 | ¿Se ha iniciado B? | NO; no contratos/ejecución B |

Todas las respuestas peligrosas NO. Una evaluación no concede autoridad y
este cierre no autoriza 1.10B–H ni fusión/publicación.
