# ADR019 — Readiness durable por negocio y perfil exacto

Fecha:2026-10-05. Decisión implementada exclusivamente en1.10A, rama dedicada.
No autoriza publicación, activación ni1.10B. [Orden](FASE-1.10A-orden.md),
[contrato](FINANCIAL-READINESS-v1.md), [cierre](FASE-1.10A-cierre.md).

## Contexto y autoridad

El titular acepta cierre técnico0–1.9 con limitaciones.1.9F sigue
PASS WITH LIMITATIONS: ningún candidato real incorporado, banco/fiscal ausentes,
64items máximos, sin aval de escala. La revisión1.9G y el diseño1.10 fueron
aceptados; las referencias inferiores conservan sus límites históricos.

La corrección autorizada elimina activación parcial implícita:
`partially_eligible` solo permite solicitar un perfil menor mediante nueva UUID.
Solo `fully_eligible` respecto al perfil exacto y cierre transitivo podría ser
candidato futuro a ready. A no implementa ese consumo ni estado.

## Decisión

- Monolito modular; `financial_activation/` recibe FinancialSession prestada y
  business_id. El llamador posee transacción/commit/rollback. Ningún pool nuevo.
- Perfil versión1 con conjunto explícito, no vacío, único y ordenado. Catálogo
  cerrado de15 capacidades y dependencias estáticas/condicionales fiscales.
- Evaluación guarda contexto, hashes, razones tipadas y prueba por las15
  capacidades. Evidence≠autoridad humana≠activación≠ejecución.
- Tres tablas en migración74. Control off/validating solamente; ever_enabled=false
  y activation_generation=0 exigidos por BD. Evaluar crea/actualiza metadata en
  off; no abre epochs ni cambia control histórico.
- Permiso separado `financial.readiness.evaluate`: policy interna para usuario
  actual de su negocio, activo, sesión vigente, suscripción escribible y flags
  OFF. No se infiere financial.authorize/historical.record/activation.authorize.
  No hay ruta, tool, grants de activación ni entrada IA. Un acceso denegado lanza
  PERMISSION_DENIED sin persistir evidencia bajo actor ajeno/inválido.
- E PASS necesario: se revalida mediante verifier SELECT prestado, con repositorio
  de findings=None. Nunca se invoca reconcile ni se actualiza historia.
- C/D pendiente, E BLOCKED, drift o frontera inválida bloquean el perfil completo.
- Dinero binario queda raw; no conversión/céntimos/normalización para readiness.
- Hash lógico excluye UUID de evaluación y reloj de creación/caducidad, conserva
  identidad del corte, actor/sesión, configuración, fuentes, política y outcome.
- MismaUUID/perfil/contexto recupera evidencia, incluso caducada; contexto distinto
  conflict. Caducidad se comprueba al consumo futuro, nunca libera fence.
- Ningún perfil financiero obtiene fully mediante stubs: PRIVACY_NOT_READY y
  EXPORT_NOT_READY permanecen bloqueados hastaE; providers hastaF; continuidadB;
  banco sin evidencia real; cancelación fiscal sin productor.
- Perfil mínimo canal.web sin comandos puede ser fully sobre corte vacío E PASS.
  Esto no habilita escrituras, rutas ni uso financiero de una cuenta.
- not_applicable solo provider.aeat_dispatch cuando modoVF falso está probado
  por configuración actual. No es excepción para implementación ausente.

## SQL y límites

Evaluaciones finalizadas y pruebas de capacidades inmutables y retenidas; FKs
compuestas actor/tenant/evaluación. BD rechaza enabled/ready/paused, ever_enabled
true y generación distinta de0. Razones de capacidad pertenecen a catálogo cerrado.
Fully exige prueba E PASS propia y boundary vigente en la finalización SQL.
SQL de administrador capaz de quitar triggers no es un actor soportado;
los hashes no son firma/autoridad. El servicio comprueba íntegramente contexto.

Nuevo registro en las listas existentes de conservación/baja de db.py: vacías
preservan la baja anterior; con evidencia se rechaza antes de borrar fuentes.
Exportación de estas tablas es requisito pendienteE, no endpoint nuevoA.

La matriz explícita permite esquema74 enB/C/D/E sin cambiar semántica/hash ni
migraciones63–73. No se usa >=73. B sigue70–74; C71–74; D72–74; E73/74; A74.

## Consecuencias y validación

Las evaluaciones no son certificados de producción, performance o providers.
Control metadata no participa en routing. Cinco flags siguen OFF. No transiciones,
bindings, resoluciones durables, attestations funcionales ni handoff.
Pruebas comunes SQLite/PostgreSQL verifican fuentes completas, cadenaE, límites,
sesión, tenants, determinismo, SQL, rollback prestado y snapshot de todas las tablas
ajenas aA. Ciclo74/73 en ambos; SQLite también74/0/74. Downgrade con evidencia
propia se rechaza. No desbloquear factura histórica v2 ni registro_anterior.
