IMPLEMENTAR FASE 1.10A — CONTRATOS Y ELIGIBILITY
El diseño de Fase 1.10 queda aprobado con las correcciones indicadas abajo.
Ejecuta exclusivamente 1.10A.
NO implementes 1.10B–H.
NO actives ningún business.
NO hagas handoff del fence.
NO liberes epochs.
NO modifiques producción ni sus datos/configuración/flags.
NO habilites ninguno de los cinco feature flags.
Trabaja en una rama dedicada a 1.10A, no hagas merge/push a main sin autorización posterior.
OBJETIVO
Implementar la infraestructura durable que permita responder, sin activar nada:
“¿Este business está preparado para solicitar este perfil exacto de capacidades, y por qué?”
1.10A termina en evaluación.
No termina en ready.
No termina en enabled.
1. PRINCIPIOS
Separar estrictamente:
evidence/readiness ≠ human authorization ≠ activation ≠ financial execution
Una evaluación nunca concede autoridad financiera.
No Economic Events.
No Financial Operations nuevas por evaluar.
No provider I/O.
No modificación de fuentes financieras.
2. CORRECCIÓN OBLIGATORIA DEL DISEÑO
La evaluación puede producir internamente:
- fully_eligible
- partially_eligible
- blocked
Pero:
solo fully_eligible respecto al perfil exacto solicitado podrá ser candidato futuro a ready.
partially_eligible significa:
“este perfil solicitado no puede activarse completo; podría formularse otro perfil menor y reevaluarlo”.
Nunca:
partially_eligible → activación parcial automática.
3. CATÁLOGO DE CAPACIDADES
Crear catálogo cerrado/versionado inicial conforme al diseño:
- invoice.issue
- invoice.rectify
- customer_payment.record
- supplier_invoice.confirm
- supplier_invoice.correct
- supplier_invoice.void
- expense.confirm
- expense.void
- bank_transaction.import
- bank_transaction.match
- invoice.fiscal_cancel
- channel.web_financial
- channel.whatsapp_financial
- provider.aeat_dispatch
- provider.email_delivery
No añadir capacidades arbitrarias.
Modelar dependencias explícitamente.
Especial:
si un perfil fiscal de emisión requiere capacidad de cancelación completa:
invoice.issue no puede ser eligible si invoice.fiscal_cancel requerida está bloqueada.
No esconder esta dependencia en UI.
4. PERFILES
Introducir perfiles versionados de capacidades solicitadas.
Una evaluación trabaja siempre sobre:
business + profile_version + exact capability set
“Fully eligible” significa todas las capacidades obligatorias del perfil y su cierre transitivo de dependencias.
No significa que todas las funciones futuras de Noesis estén activables.
5. SCHEMA
Implementar únicamente lo necesario para A.
Preferencia:
financial_activation_control
Una fila por business.
En esta fase podrá existir:
- off
- validating
pero NO implementar transición a ready, enabled ni paused operativa todavía.
Incluir desde ahora los campos estructurales necesarios para evolución:
- business_id
- state
- control_revision
- activation_generation
- ever_enabled
- current_profile
- current_evaluation_uuid
- timestamps/provenance mínimos
ever_enabled permanece false en toda 1.10A.
financial_readiness_evaluations
Inmutable una vez finalizada:
- business
- evaluation UUID
- evaluation/policy version
- code/schema version
- created_by/session
- requested profile
- requested capabilities
- epoch/generation histórica
- manifest/batch/reconciliation
- source/plan/reconciliation hashes
- context hashes
- result
- created/completed/expires
- canonical
- content hash
financial_readiness_capabilities
Por evaluación/capacidad:
- result:
  - eligible
  - blocked
  - not_requested
  - not_applicable
- reason codes cerrados
- dependency proof
- evidence refs/hashes
Nada de texto libre como autoridad.
No crear todavía
- activation transitions reales
- operation activation bindings
- antecedent resolutions
- provider attestations funcionales
- handoff receipts
salvo que sean necesarios solo como contratos sin ejecución y esté claramente justificado.
6. EVALUACIÓN
Crear servicio específico:
FinancialReadinessEvaluator
o nombre coherente con arquitectura.
Debe usar sesión/conexión prestada y no ser writer financiero.
Evaluar como mínimo:
- current business/session/permission
- estado actual de activation control
- historia existente
- epoch/fence cuando aplique
- manifest
- import batch
- reconciliation
- blocking incidences
- requested capabilities
- dependencies
- restricciones conocidas de invoice historical v2
- fiscal cancellation capability
- límites de volumen/policy
- requisitos de privacidad/export todavía disponibles o bloqueados
Puede devolver blocked porque B–F aún no existen.
Eso es correcto.
No falsear readiness para hacer pasar tests.
7. HISTORIA
Regla transversal:
C/D pendiente o reconciliation BLOCKED:
business profile BLOCKED.
No existe partial activation para esquivar historia económica relevante.
Invoice historical v2 necesaria:
BLOCKED.
registro_anterior:
nunca cuenta como cobro verificado.
Historical authorization:
nunca cuenta como autoridad live.
8. BUSINESS VACÍO
Implementar únicamente evaluación de “vacío”, no activación.
Vacío exige ausencia, dentro del scope completo, de hechos económicos relevantes:
- facturas emitidas
- cobros
- movimientos bancarios
- received invoices económicas
- gastos económicos
- fiscal records
- cancelaciones
- rectificativas
- operaciones pendientes relevantes
- dispatches inciertos relevantes
Clientes/configuración/borradores por sí solos no constituyen historia económica.
No usar únicamente counts simples si existen fuentes relacionadas que deban explicar la ausencia.
9. FLAGS
Los cinco flags permanecen OFF.
No cambiar comportamiento runtime actual.
FINANCIAL_CORE_ENABLED NO se convierte en autorización por business en A.
Introducir solo contratos que permitan hacerlo correctamente en fases posteriores.
10. PERMISOS
Definir permiso específico para:
- evaluar readiness
Diferente de:
- financial.authorize
- historical.record
- futura activation authorization
No conceder permiso de activación todavía salvo contrato cerrado sin ruta ejecutable.
Sesión/usuario se revalidan.
Multi-tenant obligatorio.
11. IDEMPOTENCIA
Misma evaluation UUID + mismo contexto:
→ recuperar mismo resultado.
Misma UUID + contenido/contexto diferente:
→ conflict.
Una nueva evaluación después de cambio:
→ nueva UUID/evidencia.
No modificar evaluación finalizada.
12. CADUCIDAD
Evaluaciones pueden caducar.
Caducidad no modifica fuentes ni libera fence.
Una evaluación caducada no podrá utilizarse para futura activación.
No implementar todavía el handoff que la consume.
13. HASHES
Hash canónico determinista de:
- profile
- capabilities
- dependencies
- historical boundary
- reconciliation proof
- relevant configuration revisions
- reason codes
- final outcome
Mismo estado lógico:
mismo hash independientemente de reloj/UUID donde el contrato así lo requiera.
Hash ≠ autorización.
14. not_applicable
Debe exigir razón tipada y evidencia verificable.
No utilizarlo para:
“no tenemos esta función”.
“no apareció en el test”.
“queremos saltarnos este requisito”.
15. RAZONES BLOCKED
Catálogo cerrado como mínimo para:
- HISTORY_PENDING
- RECONCILIATION_BLOCKED
- RECONCILIATION_MISSING
- BOUNDARY_INVALID
- SOURCE_DRIFT
- UNSUPPORTED_HISTORICAL_INVOICE
- CAPABILITY_DEPENDENCY_BLOCKED
- FISCAL_CAPABILITY_INCOMPLETE
- BANK_EVIDENCE_UNVALIDATED
- PROVIDER_PREFLIGHT_MISSING
- PRIVACY_NOT_READY
- EXPORT_NOT_READY
- VOLUME_OUTSIDE_POLICY
- PERMISSION_DENIED
- CONTEXT_CHANGED
Ajustar nombres si existen convenciones mejores, pero mantener catálogo cerrado y documentado.
16. NO PROVIDER I/O
A puede comprobar si existe evidencia/configuración requerida.
No:
- llamar AEAT
- llamar Meta
- enviar emails
- disparar webhooks
- validar producción externamente
Provider attestations reales pertenecen a 1.10F.
17. MIGRACIÓN
Nueva migration posterior a 73.
Aditiva.
No modificar migrations 63–73.
Upgrade/downgrade probado en SQLite y PostgreSQL.
Downgrade debe bloquearse cuando exista evidencia durable cuya pérdida no sea segura.
No usar >=73 indiscriminado para compatibilidad histórica.
Actualizar matriz explícita de schema compatible.
18. SQL GUARDS
Probar:
- evaluación final immutable
- capability rows final immutable
- no cross-tenant
- no cambio arbitrario de ever_enabled
- no transición manual a enabled
- no eliminación de evidencia final
Si existe activation_control, SQL directo no debe poder convertir un negocio en enabled porque 1.10A todavía no implementa esa transición.
19. TESTS
SQLite + PostgreSQL.
Como mínimo:
- business vacío eligible para perfil mínimo cuando todos los requisitos A conocidos se satisfacen;
- historia C;
- historia D;
- E BLOCKED;
- E missing;
- E PASS válido;
- source drift;
- invoice historical v2;
- registro_anterior;
- dependency closure;
- invoice.issue con fiscal_cancel requerida y bloqueada;
- partially_eligible nunca usable como fully;
- not_applicable válido/inválido;
- permission/session stale;
- cross tenant;
- UUID idempotency;
- conflict same UUID/different context;
- immutable finalized evaluation;
- expiry;
- schema migration cycles;
- direct SQL corruption attempts;
- five flags remain OFF;
- no Economic Events/Operations/source writes.
20. SIDE-EFFECT PROOF
Snapshot antes/después.
1.10A solo puede modificar:
- activation/readiness tables nuevas;
- metadata/migration correspondiente.
No puede modificar:
- legacy financial sources;
- Economic Events;
- Operations/Auth;
- history manifests/import/reconciliation;
- fiscal;
- bank;
- providers;
- channels;
- flags.
21. NO ROUTING TODAVÍA
No modificar todavía Web/WhatsApp/API/tools/recurrentes para usar activation control.
Ese cambio llegará cuando existan guards live completos.
Evitar un estado donde algunos canales respeten activation y otros no.
22. DOCUMENTACIÓN
Crear:
- contrato 1.10A/readiness
- ADR de activation/readiness
- cierre de fase
Actualizar arquitectura/guía/estado.
Registrar explícitamente:
- Fase 1.9 cerrada técnicamente con limitaciones;
- 1.9F sigue PASS WITH LIMITATIONS;
- 1.10A no activa nada.
23. GATES
Ejecutar:
- tests específicos SQLite
- PostgreSQL
- suite completa
- migrations
- Ruff
- Bandit/security
- secrets
- dependency audit
- project/documentation truth
24. CIERRE
Entregar:
- commit de la rama
- lista de archivos
- migration
- schema
- contracts
- reason catalog
- capability catalog
- dependency model
- evaluator
- idempotency
- immutable evidence
- SQL guards
- permissions
- multi-tenant
- side-effect proof
- SQLite
- PostgreSQL
- suite completa
- riesgos/limitaciones
- autoauditoría.
Responder explícitamente:
1. ¿Puede 1.10A activar un business?
2. ¿Puede liberar un fence?
3. ¿Puede producir Economic Events?
4. ¿Puede ejecutar Financial Operations?
5. ¿Puede hacer provider I/O?
6. ¿Puede partially_eligible llegar a ready?
7. ¿Puede ocultar C/D mediante capability exclusions?
8. ¿Puede tratar registro_anterior como pago real?
9. ¿Puede desbloquear invoice historical v2?
10. ¿Puede cambiar los cinco flags?
11. ¿Puede un SQL directo marcar enabled?
12. ¿Puede modificar una evaluación final?
13. ¿Puede usar un PASS de reconciliación de otro contexto?
14. ¿Puede una sesión vieja evaluar readiness?
15. ¿Puede cruzar tenants?
16. ¿not_applicable requiere evidencia?
17. ¿invoice.issue cierra dependencias fiscales necesarias?
18. ¿los resultados son deterministas?
19. ¿el runtime existente sigue funcionando igual?
20. ¿se ha iniciado 1.10B?
Todas las respuestas peligrosas deben ser NO.
NO avanzar a 1.10B.