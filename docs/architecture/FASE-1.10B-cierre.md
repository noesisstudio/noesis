# Fase 1.10B — antecedentes y continuidad historical→live

Fecha: 2026-10-06. Estado: **PASS — cierre técnico local; aceptación humana pendiente.**
Rama `codex/phase-1-10b`, creada desde la base exacta autorizada
`c9106165195cc053c8d713b7a94557df28bc4099`. Commit de entrega: el que incorpora
este informe, recuperable con `git log -1 --format=%H -- docs/architecture/FASE-1.10B-cierre.md`.
Aceptación humana pendiente. No autoriza merge, publicación, despliegue ni 1.10C–H.

[Orden conservada](FASE-1.10B-orden.md), [ADR020](ADR-020-financial-antecedents.md),
[contrato completo](FINANCIAL-ANTECEDENTS-v1.md), [plan](FASE-1.10-plan.md).

## Entrega y contrato

Una resolución identifica evidencia existente y su aptitud para un propósito;
nunca autoridad ni ejecución. Monolito modular, FinancialSession/gate/TX prestados,
sin conexión/commit propios. `resolve` solo SELECT; `persist_resolution` recomprueba
y escribe exclusivamente tabla B; `read` valida forma/columnas/hashes/creador/sesión;
`verify_resolution` recomprueba toda la prueba en la misma TX de cada futuro uso.
Cambio relevante implica stale/Conflict. UUID/contexto/cuerpo iguales retornan fila
original; cualquier diferencia Conflict. UUID/reloj propios fuera del contexto.

Request v1: `ResolutionRequest(AntecedentRef(source_type, source_id, revision,
event_uuid=None), purpose, bank_movement=None)`. Business obligatorio en resolver,
queries/FKs. Sin UUID solo se admite evento único de esa revisión exacta. Nunca
importe/fecha/cliente/texto/status como identidad. Referencia inexistente o ajena:
AccessDenied uniforme, sin consultas a otro tenant. Cuenta escribible, usuario
activo/sesión actual; permisos resolve/read, nunca financial.authorize/mandate.

Origen historical/live; calidad verified_fact/observed_state; outcome resolved/blocked.
Resultado v1 cerrado: request/tenant, reasons, origen/calidad, event/op/auth/batch/item/E,
source/content/record/context/evidence hashes, importe/moneda/saldo y dependencias.
Proof de trece campos: amount/currency/economic_date/source_state/state_components/
prior_payments/fiscal_evidence/bank_movement/base/vat_amount/irpf_amount/invoice_number/
due_on. Sin payload completo ni PII libre. Revalidation=`every_use`; no permiso perpetuo.

| Propósito cerrado v1 | Antecedente requerido |
|---|---|
| customer_payment_against_invoice | Factura live v2, total/EUR/fecha/estado acreditados y todos los cobros íntegros |
| rectify_invoice | Factura exacta y vínculos exactos cuando existan; no crea rectificativa |
| fiscal_cancel_invoice | Factura/registro fiscal documental íntegros; no productor/capability |
| bank_match_invoice | Factura anterior y movimiento live imported exacto, positivo y dentro del saldo |
| supplier_invoice_correct | confirmed/corrected verified, estado anterior completo y cadena contigua |
| supplier_invoice_void | Igual evidencia completa; no retira fuente |
| expense_void | confirmed verified con total/IVA/fecha/estado anterior |
| inspect_evidence | Consulta de observed_state/verified, unknowns conservados, no aptitud operativa |

18 reasons cerrados: ANTECEDENT_NOT_FOUND, ANTECEDENT_UNSUPPORTED,
ANTECEDENT_NOT_VERIFIED, OBSERVED_STATE_INSUFFICIENT, SOURCE_CHANGED,
EVENT_MISSING, EVENT_INVALID, OPERATION_INVALID, AUTHORIZATION_INVALID,
COVERAGE_INCOMPLETE, PAYMENT_HISTORY_INCOMPLETE, MONEY_UNCERTAIN, DATE_UNCERTAIN,
FISCAL_EVIDENCE_INCOMPLETE, DEPENDENCY_INVALID, PURPOSE_NOT_ALLOWED,
HISTORICAL_PROOF_INVALID, LIVE_PROOF_INVALID. not_found no introduce otro estado;
referencia inaccessible conserva el rechazo uniforme descrito arriba.

## Proof, dinero y dependencias

Histórica exige EE/HistoricalIdentity/slot/revisión originales, raw/candidato
congelados, intent/item recorded, operación historical PREPARED,
historical_unknown sin actor/autoridad original, batch/C/manifest y E PASS
correspondiente íntegra. Reutiliza proof original; contrasta fuente/dependencias
actuales, sin nueva importación ni reescritura. Batch partial solo con item recorded,
sin blocking_code y E PASS correspondiente. Acredita ese hecho particular; no
exige congelar otra vez todas las futuras fuentes live. Handoff/readiness no se simulan.

El positivo obligatorio recorre importación sintética real → operación →
historical_unknown → EE historical → E PASS → resolved/inspect_evidence.
Es observed_state B, sin promoción. Los tres v2 históricos existentes conservan
calidad observada; no se afirma un histórico verified que sus contratos no prueban.
Factura histórica v2 continúa unsupported incluso para consulta resoluble.

Live exige request/result COMMITTED íntegros, confirmación humana exacta válida
al commit, EE canonical/content/record, coverage del dominio, source/revisión y links.
Supplier/expense: todas las revisiones y before/after/antecedente contiguos.
Mandato con metadata insuficiente permanece bloqueado. Positivo mediante Capture
sintético existente; B no ejecuta Capture/FinancialOperations durante resolución.
Vínculos deben coincidir exactamente con el envelope y probar target/type/tenant/
revisión y semántica. Links ausentes/extra o padres no verificados bloquean.

EUR/Decimal y JSON string decimal canónico. Dinero solo de EE/request/evidencia
acreditados. Binary legacy solo identidad opaca; nunca Decimal(str(float)) para
certeza. Proyección de valor YA exacto hacia bits físicos no acredita origen binario.
Unknown/NULL conservados; no fecha→hoy, NULL→0 ni pagada→cobro.
source_state conocido solo significa huella física, no verdad económica.

Saldo = total verificado menos pagos exactos. Filas, coverages y todos los eventos
settles deben formar el mismo conjunto: evento huérfano bloquea. Ausencia exhaustiva
acreditada permite suma cero, diferente de normalizar NULL. registro_anterior bloquea.
El modo fiscal entra en contexto y revalidación. No Open Items. Bank match solo
resuelve evidencia de factura/movimiento: cero payment/cash/EE nuevos.

## Schema, FKs y archivos

Migración **75** aditiva: `financial_antecedent_resolutions`, PK business/UUID,
version/purpose/source/revisión/outcome/origen/calidad, known_unknown/result canónicos,
hashes, refs de evento/op/auth/importación/E, creador/sesión, fecha y every_use.
Seis columnas FK de fuente tipadas, una sola activa y source_id consistente;
todas las FKs por business. Clave protegida permite futura FK por
business/resolution/outcome/purpose/quality/origin/event; ningún hijo/writer se conecta.
UPDATE/DELETE prohibidos; INSERT guarda actor/catálogos/proof/origen consistente y
refs durables. SQL protege estructura; aplicación verifica semántica y revalida.
Downgrade vacío permitido; cualquier evidencia, incluida blocked, impide pérdida/baja.
Funciones/entradas de migraciones 1–74 conservan AST idéntico. Ninguna FK anterior eliminada.

Creados: `src/noesis/financial_antecedents/{__init__,contracts,proofs,resolver,repository,schema}.py`,
`tests/financial_antecedents_contract.py`, `tests/test_financial_antecedents.py`,
`tests/test_financial_antecedents_migrations.py`, `tests/postgres_financial_antecedents.py`
y los cuatro documentos B enlazados arriba. contracts tipa/canonicaliza;
proofs verifica cadenas; resolver comprueba propósito; repository persiste; schema
protege estructura. Tests comunes: 46; PG añade cinco carreras y un ciclo de esquema.

Modificados: `src/noesis/migrations.py` solo wrappers/entrada75; `db.py` dos líneas
de conservación; `financial_history/schema_compatibility.py` y
`financial_activation/contracts.py` solo compatibilidad explícita. Tests
`test_financial_history.py`/`test_financial_readiness_migrations.py` ajustan expectativas
de esquema. `.github/workflows/ci.yml` añade matriz PG B. Gobernanza actualizada:
AGENTS, arquitectura README/plan, guías01/06/08, Arquitectura, Decisiones,
Estado-actual-main, Tareas-vivas, Mapa-codigo, Registro-QA, Registro-cambios y
project-state.json. Sin nuevas dependencias ni cambios de rutas/productores.

## Validación y criterios

Solo fixtures sintéticos: Python3.12.3, SQLite3.45.1 y PostgreSQL16.15, cluster nuevo
en127.0.0.1/noesis_ci, schema aleatorio por matriz. Cluster detenido al terminar. Nunca Railway, producción,
Noesis19FQA o backups reales. Sin merge/push main ni despliegue. Main local conserva `e95c19beea7a9cda291f045459b06eb639e171e5` y remoto `acff183319f476a5f0b25a820751dca4523fd8fd`. Dos backups sintéticos de smoke conservados fuera del repositorio/Git; ninguna BD/dump/secreto incluido en el commit.

| Gate/criterio | Resultado |
|---|---|
| B SQLite y migración | PASS: 47 pruebas, 98.710s |
| B PostgreSQL y migración/concurrencia | PASS: 52 pruebas, 33.367s |
| Cinco carreras PG | PASS: mismo UUID, dos UUID, source drift, corrupción links, otro negocio |
| Mig75 vacío/conservación | PASS: 74→75→74→75 ambos, SQLite75→0→75, evidencia bloquea bajada/baja |
| Regresiones PG anteriores A–E/readiness/Capture/Operations | PASS: 423 pruebas; total PG incluido B: 475 |
| Smoke PG | PASS: 32→75, HTTP, código53 sobre75, privacidad/rollback/conservación |
| Suite general | PASS: 1875 pruebas, 2596.044s, cero failures/errors, dos skips existentes |
| Ruff | PASS |
| Bandit, umbral CI high/high | PASS |
| Secret scan, incluye archivos nuevos staged | PASS: ningún secreto nuevo |
| pip-audit | PASS: cero vulnerabilidades conocidas; paquete local noesis fuera de PyPI no auditable |
| JavaScript | PASS: 9 pruebas |
| AST anterior/módulo A | PASS: migraciones1–74 y evaluator/schema/repository A intactos |
| Verdad documental | PASS: foto/esquema sincronizados y documentación requerida en la misma entrega; gate contra base tras commit |
| Enlaces Markdown | PASS: 182 documentos, 1.321 destinos locales, cero rotos |
| Side effects | PASS: snapshot de TODAS las tablas previas y flags; al persistir solo tabla B |

Negativos: versiones/tipos/purpose/float, binary sin proof, NULL y fecha desconocida,
invoice histórica v2/registro_anterior/observed insuficiente, event/op/auth/coverage
corruptos/ausentes, pagos faltantes/huérfanos, links extra/ausentes, tenant/sesión/
permisos, drift/stale y UUID conflict. Positivos históricos y live recorren cadenas
durables existentes, no filas inventadas para fingir autoridad.
Primeras ejecuciones detectaron fixture NULL sobre NOT NULL, planes PG cacheados
tras downgrade sintético y prioridad de reason al ampliar exhaustividad. Corregidos
solo en B y matrices completas reejecutadas; sin parche funcional legacy.
Wrapper de smoke: error de consola al imprimir una flecha DESPUÉS de cinco comandos
exitosos y cleanup; todos los comandos de prueba devolvieron0, verificación posterior ASCII PASS.

## Decisiones, diferencias, riesgos y límites

inspect_evidence es el propósito adicional justificado para consulta observed_state
sin inventar aptitud operativa; catálogo sigue cerrado. Batch partial admite solo
proof individual completo/E PASS. A estable, solo esquema75 compatible; no resolver
integrado ni outcomes/blockers alterados. Sin desviación funcional del alcance.

Bloqueos conservadores: mandatos sin proof específico, banco revisado después de
import original, factura histórica v2, huecos en cobros y estado anterior incompleto.
Representaciones legacy inusuales pueden fallar la huella textual: bloqueo seguro,
no certeza aproximada. Sin SLO de escala grande. SQL privilegiado que deshabilita
guards fuera del threat model; fixtures adversariales solo para detectar corrupción.
Hashes no son firmas/autoridad. Futuro consumidor exige revalidación en TX y su
propia autoridad/readiness/generación; omitirla sería integración incorrecta.

Privacidad/export/retención/proveedores siguen pendientes y no habilitados;
blockers A intactos. PG downgrade hasta0 no se afirma: fallo heredado DROP TRIGGER
sin ON fuera de alcance; ciclos75/74 y rollback53 sí probados. CI remota B no
ejecutada, workflow preparado y rama sin publicar. Rollback: revertir entrega sin
consumo runtime; bajar75 solo vacía, conservando evidencia si existe.

## Autoauditoría obligatoria

| # | Pregunta | Respuesta / criterio |
|---|---|---|
| 1 | ¿Puede B activar business? | NO — PASS |
| 2 | ¿Puede cambiar activation state/generation? | NO — PASS |
| 3 | ¿Puede liberar fence? | NO — PASS |
| 4 | ¿Puede producir EE? | NO — PASS |
| 5 | ¿Puede ejecutar Financial Operations? | NO — PASS |
| 6 | ¿Puede convertir historical en live? | NO — PASS |
| 7 | ¿Puede copiar historical a live coverage? | NO — PASS |
| 8 | ¿Puede promover observed_state a verified? | NO — PASS |
| 9 | ¿Puede resolver por importe/fecha aproximada? | NO — PASS |
| 10 | ¿Puede tratar registro_anterior como cobro? | NO — PASS |
| 11 | ¿Puede desbloquear invoice historical v2? | NO — PASS |
| 12 | ¿Puede crear bank match/payment? | NO — PASS |
| 13 | ¿Puede hacer provider I/O? | NO — PASS |
| 14 | ¿Puede mutar source/event/op/auth? | NO — PASS |
| 15 | ¿Puede una resolution stale seguir válida? | NO — PASS |
| 16 | ¿Puede cruzar tenant? | NO — PASS |
| 17 | ¿Puede reutilizar UUID con otro contexto? | NO — PASS |
| 18 | ¿Unknown se conserva? | SÍ — PASS |
| 19 | ¿Cinco flags siguen OFF? | SÍ — PASS |
| 20 | ¿Se inició 1.10C? | NO — PASS |

Todas las respuestas peligrosas NO, acreditadas por guards, revalidación y matrices
de pruebas descritas. Ninguna aceptación/fusión/publicación ni siguiente fase implícita.
