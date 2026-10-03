Las Fases 0–1.8 NO quedan todavía autorizadas para iniciar Fase 1.9.

Ejecuta exclusivamente una unidad de endurecimiento:

**FASE 1.8H — CIERRE DE BLOCKERS B1–B5 DE LA AUDITORÍA INTEGRAL**

No avances a 1.9.

No añadas funcionalidades nuevas.

No amplíes el catálogo de Economic Events.

No actives flags.

Trabaja sobre el `main` real posterior a Fase 1.8.

Lee primero:

- `AGENTS.md`
- `docs/architecture/README.md`
- todos los contratos/ADR vigentes de Financial Core;
- cierres 1.1–1.8;
- auditoría integral de Astra;
- migrations 62–68;
- código y tests reales implicados.

Los únicos blockers autorizados son:

B1. DELETE PostgreSQL de pagos no capturados.
B2. Orden inconsistente de locks.
B3. Restricciones recurrentes omitibles desde algunos canales.
B4. Recuperación de COMMITTED tras renovación de sesión.
B5. CI completa verde.

---

# B1 — CORREGIR DELETE LEGACY DE INVOICE_PAYMENTS EN POSTGRESQL

Problema confirmado:

`src/noesis/payment_capture/schema.py`

genera funciones PostgreSQL de trigger que terminan siempre en:

`RETURN NEW`

incluido `BEFORE DELETE`.

En PostgreSQL, para DELETE, `NEW` es NULL.

Consecuencia actual:

- payment capturado → guard lanza excepción correctamente;
- payment no capturado → el trigger no lanza excepción pero `RETURN NEW`/NULL cancela silenciosamente el DELETE;
- SQLite no presenta esa semántica.

## Requisito

El trigger debe:

- devolver `OLD` en DELETE permitido;
- devolver `NEW` en INSERT/UPDATE permitido;
- seguir lanzando excepción para DELETE de payment capturado.

No relajes ningún guard.

## MIGRACIÓN

NO asumas que modificar únicamente el código de migración 66 repara instalaciones existentes.

Crea la siguiente migración disponible sobre main —previsiblemente **69**, pero determina el número real— para reparar los triggers/funciones ya instalados.

Debe:

- reparar PostgreSQL existente;
- preservar SQLite;
- funcionar desde schema limpio;
- funcionar 68→nueva versión;
- no perder coberturas;
- no modificar datos económicos.

Si también corriges el helper original para instalaciones limpias/replay de migraciones, documenta claramente la compatibilidad.

## TESTS B1

PostgreSQL y SQLite:

1. payment legacy NO capturado → comportamiento de DELETE previsto y equivalente;
2. payment capturado → DELETE rechazado;
3. UPDATE capturado sigue rechazado;
4. coberturas permanecen intactas;
5. upgrade desde 68 repara una función existente;
6. fresh install termina con semántica correcta.

No introduzcas una nueva API pública para borrar pagos.

---

# B2 — UNIFICAR ORDEN DE LOCKS

Problema confirmado:

algunos `Capture.prepare()` hacen:

operation lock
→ validación
→ business lock

mientras authorize/execute con canales hacen:

business lock
→ operation lock.

Esto permite el ciclo:

T1:
operation lock
→ espera business

T2:
business lock
→ espera operation

y PostgreSQL puede detectar deadlock.

## REGLA CANÓNICA

Para workflows financieros:

**business gate antes de operation/source locks.**

Debe ser consistente en:

- prepare;
- reprepare;
- authorize;
- execute;
- recurring;
- channel bridges.

No cambies el aislamiento global ni introduzcas tablas de lock nuevas.

No abras conexiones adicionales.

## IMPLEMENTACIÓN

Prefiere centralizar la regla mínima en una frontera común si puede hacerse sin refactor grande.

Evita parchear cinco servicios de forma divergente si existe un helper común seguro.

Pero tampoco construyas un nuevo framework de transacciones.

## TEST OBLIGATORIO

PostgreSQL real, dos conexiones/procesos y sincronización determinista:

T1 = prepare/reprepare de operación existente.
T2 = authorize o execute de esa misma operación.

Fuerza el intercalado que anteriormente podía ser:

operation → business
vs
business → operation.

Resultado nuevo:

- sin deadlock;
- una semántica válida;
- ningún doble efecto;
- locks liberados tras rollback.

Añade también regresión para operaciones distintas del mismo negocio.

---

# B3 — RECURRENCIA OBLIGATORIA EN FRONTERA COMÚN

Problema confirmado:

web resuelve:

`occurrence_for_invoice(...)`

antes de proponer una emisión recurrente.

Chat/tools/WhatsApp pueden llegar a:

`FinancialChannels.propose(...)`

sin `recurring_context`.

El guard solamente aplica reglas recurrentes si dicho contexto ya está presente.

Por tanto una factura generada por recurrencia puede entrar desde otro canal como emisión ordinaria.

No elimina confirmación humana, pero evita controles de:

- schedule pausado;
- template modificado;
- run sin huella;
- ocurrencia caducada;
- contexto recurrente incoherente.

## REQUISITO

La procedencia recurrente debe resolverse **server-side en una frontera común**, no depender de que el canal recuerde hacerlo.

Para toda intención:

`invoice.issue`
o donde realmente corresponda `invoice.rectify`

el sistema debe comprobar si el invoice pertenece a una ocurrencia recurrente.

Si pertenece:

1. resolver `occurrence_for_invoice`;
2. validar schedule/run/template;
3. usar la identidad recurrente canónica;
4. conservar por separado la identidad de transporte original;
5. congelar recurring_context;
6. aplicar las mismas restricciones independientemente de Web/Chat/Tools/WhatsApp.

Si existe un run recurrente legacy sin huella durable:

→ fallar cerrado.

NO tratarlo como factura ordinaria.

## IMPORTANTE

No crear mandato automático.

La política continúa siendo:

recurrencia
→ borrador
→ propuesta
→ confirmación humana de esa ocurrencia.

## TESTS

Desde:

- web;
- chat/tool;
- WhatsApp.

Probar:

1. ocurrencia válida;
2. schedule pausado;
3. template modificado;
4. run sin fingerprint;
5. invoice que NO es recurrente;
6. mismo vencimiento intentado desde dos canales.

El último caso debe converger en una sola identidad económica/operación para la ocurrencia, manteniendo recibos de transporte separados cuando corresponda.

---

# B4 — RECUPERACIÓN DE COMMITTED CON NUEVA SESIÓN VÁLIDA

Problema confirmado:

`actor_key` incluye:

- user_id;
- session_version;
- actor.

`FinancialChannels._link()` exige igualdad con ese actor_key.

Por tanto:

usuario A ejecuta correctamente
→ operación COMMITTED
→ renueva/cambia session_version
→ usuario A autenticado correctamente con sesión nueva
→ FinancialOperations permite acceso como creador actual
→ FinancialChannels bloquea la respuesta porque el actor_key histórico contiene la sesión anterior.

## SEMÁNTICA CORRECTA

Separar:

### Autoridad para aprobar/ejecutar

Debe seguir exigiendo:

- sesión vigente;
- request exacto;
- authorization durable;
- actor correcto;
- revisión;
- recibo;
- proposal.

### Consulta de un efecto YA COMMITTED

Debe exigir:

- usuario actualmente autenticado;
- sesión actual válida;
- mismo negocio;
- mismo `created_by`/propietario autorizado de la operación;
- permiso de lectura actual.

Pero NO debe exigir que:

`session_version actual == session_version histórica de la propuesta`.

La propuesta/autorización histórica NO se modifica.

No crear una nueva autorización.

No reejecutar.

No cambiar actor histórico.

## SEGURIDAD

Una sesión antigua/revocada debe seguir fallando porque `_permission` valida la sesión vigente.

Otro usuario del mismo negocio NO debe adquirir automáticamente acceso si la política actual continúa siendo por creador.

Otro negocio siempre rechazado.

PREPARED y APPROVED deben conservar el vínculo fuerte con la sesión/propuesta original.

La relajación es exclusivamente para recuperación/lectura de `COMMITTED`.

## TESTS

1. ejecutar con session_version 1;
2. resultado COMMITTED;
3. incrementar session_version;
4. Principal actual con versión 2;
5. mismo creador recupera resultado;
6. cero ejecución del writer;
7. authorization original intacta;
8. actor/session históricos intactos;
9. Principal antiguo versión 1 rechazado;
10. otro user rechazado;
11. otro business rechazado;
12. PREPARED no se puede secuestrar con sesión nueva.

Probar Web y el bridge común.

---

# B5 — CI COMPLETA VERDE

Existe además el falso positivo conocido:

`docs/project-state.json`

contiene el SHA público:

`production.financial_core_phase0_release.commit` de `docs/project-state.json`

(Referencia al SHA público literal de la orden original, conservado sin cambios
en ese campo; esta copia evita duplicarlo en otro archivo.)

del commit real de Fase 0.

`detect-secrets` lo detecta como `Hex High Entropy String`.

No es credencial.

## REQUISITO

Resolverlo mediante la excepción exacta soportada por el sistema existente:

- archivo;
- detector;
- fingerprint/baseline exacta.

NO:

- desactivar el detector;
- ignorar todo project-state;
- añadir regex amplia;
- eliminar información necesaria del estado del proyecto.

---

# VALIDACIÓN FINAL OBLIGATORIA

Esta unidad NO puede cerrarse únicamente con tests dirigidos.

Después del ÚLTIMO cambio de código o baseline ejecuta:

### SQLite / general

- suite general COMPLETA;
- migraciones 0→latest→0→latest cuando sean seguras;
- tests Financial Core;
- tests canales;
- Node.

### PostgreSQL real

- fundamentos;
- Financial Operations;
- Economic Persistence;
- Borrowed Writers;
- InvoiceCapture;
- Payment/BankCapture;
- PurchasingCapture;
- FinancialChannels;
- nuevos tests B1;
- nueva carrera B2;
- casos B3;
- casos B4;
- migraciones históricas;
- rollback/código anterior sobre schema nuevo.

### Gates

- Ruff;
- Bandit;
- pip-audit;
- uv lock;
- secrets;
- verdad documental;
- enlaces;
- diff/gobernanza.

### CI REMOTA

Push a `main` según la política vigente.

La GitHub Actions CI COMPLETA debe terminar:

**PASS**

No basta con que pase solamente el job PostgreSQL.

---

# NO RESOLVER AHORA

No arregles todavía, salvo dependencia directa de B1–B5:

- producer runtime de `invoice.fiscal_cancellation_registered`;
- UI general de lotes CSV;
- audio sin identidad durable;
- delegación entre usuarios;
- mandatos recurrentes;
- exportación/retención 1.10;
- históricos;
- backfill;
- activación por cuenta;
- GL;
- Open Items;
- Tax Ledger;
- mejoras generales VERI*FACTU.

El pending huérfano por adjuntos WhatsApp detectado en la auditoría puede quedar documentado como deuda menor si no es necesario para B1–B5.

No amplíes el alcance por iniciativa.

---

# DOCUMENTACIÓN

Actualiza la foto vigente de arquitectura para que quede claro:

- Fases 0–1.8 implementadas;
- hardening 1.8H;
- blockers B1–B5 cerrados o abiertos;
- flags OFF;
- 1.9 no iniciada;
- CI final exacta.

No reescribas el histórico de fases anteriores como si nunca hubieran tenido esos defects.

---

# AUTOAUDITORÍA

Responde explícitamente:

1. ¿DELETE de payment no capturado funciona igual en PG/SQLite?
2. ¿DELETE de payment capturado sigue bloqueado?
3. ¿Una BD que ya pasó por 66 queda reparada?
4. ¿Todos los workflows toman business gate antes de operation/source locks?
5. ¿La carrera prepare/authorize puede deadlock?
6. ¿Chat/Tools/WhatsApp pueden tratar una recurrente como ordinaria?
7. ¿Dos canales pueden crear dos operaciones para la misma ocurrencia?
8. ¿Un COMMITTED puede recuperarse con una sesión nueva válida del mismo creador?
9. ¿Una sesión antigua revocada puede recuperarlo?
10. ¿Se ha reescrito la autorización histórica?
11. ¿Se ha rebajado detect-secrets?
12. ¿La suite general se ejecutó DESPUÉS del último cambio?
13. ¿CI remota completa está verde?
14. ¿Se inició accidentalmente 1.9?

---

# CIERRE

Devuélveme:

1. diagnóstico inicial;
2. archivos modificados;
3. migración nueva;
4. corrección B1;
5. estrategia definitiva de locks B2;
6. resolución recurrente común B3;
7. semántica de recuperación B4;
8. cambio exacto de baseline B5;
9. tests SQLite;
10. tests PostgreSQL;
11. carreras;
12. suite general completa;
13. gates;
14. GitHub Actions final;
15. riesgos restantes;
16. PASS/FAIL individual de B1–B5;
17. autoauditoría.

Criterio de cierre:

B1 PASS
B2 PASS
B3 PASS
B4 PASS
B5 PASS

Si cualquiera falla:

**NO declarar hardening cerrado.**

No implementar Fase 1.9.
