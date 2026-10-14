# Financial Readiness v1 — contrato1.10A

[ADR019](ADR-019-financial-readiness.md), [orden](FASE-1.10A-orden.md),
[plan aprobado](FASE-1.10-plan.md). Solo evaluación, sin ready ni activación.

## API y permisos

`FinancialReadinessEvaluator(FinancialSession(conn), business_id)` sobre transacción
exterior (BEGIN IMMEDIATE en SQLite; READ COMMITTED y business gate enPG).

`evaluate(principal, evaluation_uuid, Profile(tuple_capabilities), history=HistoryContext(...),
policy=Policy(), code_version=label, now=aware_datetime)`:
revalida permiso/sesión/suscripción, adquiere gate, revalida usuario/negocio con locks,
lee fuentes/configuración, revalida E, calcula resultado y escribe solo tres tablasA.
Clock y code_version son argumentos internos del llamador confiable, nunca IA/canal.
Por defecto relojUTC real; parámetro now permite pruebas reproducibles.
No begin/commit/rollback/conexión propios; fallo revierte en transacción exterior.

`read(principal,evaluation_uuid)` recupera evaluación propia/tenant con sesión actual.
El resultado durable no cambia al caducar. `future_ready_candidate` es exclusivamente
predicado puro FULL/no caducado; no acredita contexto actual ni concede autoridad.
El consumo de activación futuro deberá revalidar íntegramente el contexto.

Permiso `financial.readiness.evaluate` separado por identificador/policy de authorize,
historical.record y activación. Usuario autenticado activo de cuenta escribible
puede evaluar; no hay otro rol/grant nuevo ni permisos de activación. Denegación
uniforme PERMISSION_DENIED, sin escribir una evaluación para usuario inválido.

## Perfil y capacidades

Versión perfil/policy/evaluación1. Conjunto exacto no vacío sin duplicados;
orden canónico. Las dependencias se incorporan sin reducir el request original.

| Capacidad | Dependencias directas |
|---|---|
| invoice.issue | invoice.rectify, channel.web_financial; conVF: invoice.fiscal_cancel y provider.aeat_dispatch |
| invoice.rectify | channel.web_financial |
| customer_payment.record | channel.web_financial |
| supplier_invoice.confirm | channel.web_financial |
| supplier_invoice.correct | supplier_invoice.confirm |
| supplier_invoice.void | supplier_invoice.confirm |
| expense.confirm | channel.web_financial |
| expense.void | expense.confirm |
| bank_transaction.import | channel.web_financial |
| bank_transaction.match | bank_transaction.import, customer_payment.record |
| invoice.fiscal_cancel | invoice.rectify, provider.aeat_dispatch |
| channel.web_financial | ninguna |
| channel.whatsapp_financial | ninguna; preflight obligatorio pendiente |
| provider.aeat_dispatch | ninguna; preflight cuandoVF |
| provider.email_delivery | ninguna; preflight obligatorio pendiente |

La condición fiscal procede del negocio actual, no del profile enviado.
Un descendant bloqueado bloquea sus parents hasta punto fijo. No ciclos.

Resultado porcapacidad eligible/blocked/not_requested/not_applicable, con razones,
proof de dependencias y huella de configuración. Las15 filas deben estar completas
antes de finalizar. not_requested significa fuera del cierre, no «saltado».
not_applicable soloAEAT con modoVF=false y evidenciahash; productor inexistente,
caso ausente o cancelación pendiente nunca califican para esa excepción.
not_applicable acredita una condición de no obligatoriedad, nunca disponibilidad
ni permiso de dispatch. Su consumo futuro no podrá habilitar esa capacidad.

Outcome fully_eligible si todo el cierre cumple; partially_eligible si coexisten
capacidades conformes/bloqueadas; blocked si hay blocker transversal o todo bloqueado.
PARTIAL no es consumible como FULL: nuevo perfil y nueva evaluación.

## Evidencia y vacío

Reader raw completo del catálogo C: facturas/líneas/perfiles/series, cobros, compras,
banco/links, fiscal/cancelaciones/transporte, documentos/clasificaciones, recurrentes,
events/coverage. Se comprueba membership y referencias documento/fuente/línea.
Facturas borrador y clientes no son por sí hechos; received/expense se conservan
conservadoramente como historia económica. Facturas no-borrador, cobros (incluido
registro_anterior), registros fiscales yEE impiden vacío.
Además se contrastan operaciones live pendientes, autorizaciones y outboxes
email/WhatsApp: dispatch no terminal impide acreditar vacío. Es deliberadamente
conservador: no se certifica ausencia sin explicar pendientes relacionados.
Estado/ref/bits se hashean; no se guarda PII literal ni texto raw enA.

Sin HistoryContext: RECONCILIATION_MISSING; con historia además HISTORY_PENDING.
Con contexto: pertenencia tenant, correlación epoch/manifest/batch/E, frontera,
fuentes/plan/cobertura/dependencias y E frozen revalidados con verifier SELECT.
C/D/incidencias no resueltas o E BLOCKED bloquean incluso perfil solo-web.
E antigua distinta no sirve; drift no repara ni invalida/releases automáticamente.
No se convierte historical_unknown en autoridad ni registro_anterior en pago.
Invoice historical v2 necesaria sigue bloqueada.
En A, la presencia de facturas económicas previas bloquea emisión/rectificación/
cobro: no se resuelven todavía antecedentes ni se promete continuidad para
capturas anteriores. Esa distinción requiere B y una evaluación nueva.

Config: huella emisor/modo/suscripción, producer fiscal, series y recurrentes.
Secretos y URLs no se incluyen. No se validan archivoscertificados ni providers.
Su attestation ausente permanece bloqueada; se desarrollará con revisión enF.

## Razones cerradas

HISTORY_PENDING; RECONCILIATION_BLOCKED; RECONCILIATION_MISSING;
BOUNDARY_INVALID; SOURCE_DRIFT; UNSUPPORTED_HISTORICAL_INVOICE;
CAPABILITY_DEPENDENCY_BLOCKED; FISCAL_CAPABILITY_INCOMPLETE;
BANK_EVIDENCE_UNVALIDATED; PROVIDER_PREFLIGHT_MISSING; PRIVACY_NOT_READY;
EXPORT_NOT_READY; VOLUME_OUTSIDE_POLICY; PERMISSION_DENIED; CONTEXT_CHANGED;
CONTROL_INVALID; FISCAL_PROVIDER_NOT_APPLICABLE; CONTINUITY_NOT_IMPLEMENTED.

Policy por defecto64items/300segundos, solo admite límites más estrictos.
Sin evidencia de mayor escala. Caducidad se guarda fuera del hash lógico.

## Persistencia, hash e idempotencia

74 añade financial_activation_control, financial_readiness_evaluations y
financial_readiness_capabilities. Control solooff/validating, generation0,
ever_enabled=false; evaluar no cambia state. Puntero al último perfil/evaluación
es metadata informativa, nunca selección de capacidades habilitadas.

Hash lógico abarca perfil exacto, policy, fuentes/membership/relacionadas,
configuración, actor/sesión/permiso, control state/generation/ever_enabled,
identidad y prueba del corte/E, dependencias, razones y outcome.
Excluye UUID/clock propios y revisión/puntero informativos deA para que sus
propias escrituras no cambien el contexto de retry. Otroclock/UUIDA con mismo
estado lógico da mismohash; distinta frontera o actor sí cambia contexto.

MismaUUID/perfil/contexto devuelve evidencia original. Perfil/contexto cambiado:
ConflictError(CONTEXT_CHANGED), sin modificación final. read valida hashes y
columnas/proofs; finalized UPDATE/DELETE rechazados enSQL. Un hash no firma autoría.
Downgrade rechaza cualquier evidencia/control durable. Baja con conservación
registrada en inventario existente; export funcional financiero pendienteE.

## Límites heredables

El único FULL mínimo demostrado es canalweb sin comandos, en fixtures vacíos
con E PASS. No es readiness para activar dinero: todo comando requiere todavía
privacidad/export; históricos ademáscontinuidadB; bancosvalidaciónrealF; fiscal
productorC. No hay rutas/canales/flags/transiciones/Handoff/Operations/EE/I/O.
