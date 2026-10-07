# Fase 1.10D — cierre técnico local

## 2026-10-07 — Corrección de CI remota 1.10D

La publicación de la rama D fue autorizada posteriormente por el titular. La primera CI remota (37586733490) falló antes de la suite general: conflicto de PK en la restauración sintética de semillas M77 y tres SHAs públicos señalados por credential scan. Se corrigen únicamente el restaurador y sus excepciones exactas revisadas; sin nueva migración, guard, workflow, activación o E. CI completa desde cero pendiente; el cierre local inferior se conserva como registro histórico.

Estado: **CODE-VERIFIED PASS local**, pendiente de revisión independiente. Publicación no autorizada.

Rama `codex/phase-1-10d`. Padre exacto autorizado:
`0e99db609b1f7ad21996b0eb9c48d95366913f4a`.
El commit local se obtiene con `git rev-parse codex/phase-1-10d` una vez cerrados
los gates; no se incrusta su propio SHA en el documento que forma parte de él.
Migración nueva: **77**. A/B/C: **CODE-VERIFIED PASS**, aceptadas por la orden D.
D solo local. Sin push, merge, deploy ni 1.10E–H.

## Contrato y comportamiento

[ADR022](ADR-022-activation-handoff-generations.md),
[contrato v1](FINANCIAL-ACTIVATION-HANDOFF-v1.md) y
[orden autorizada](FASE-1.10D-orden.md) son las referencias heredables.

| Acción | Origen | Resultado | Generación |
|---|---|---|---|
| enable | off, nunca habilitado | validating → ready → enabled | 1 al commit final |
| abort | validating/ready, nunca habilitado | off | 0 |
| pause | enabled | paused | conserva G y ever_enabled |
| resume | paused | validating → ready → enabled, una TX | G+1 |

Cada etapa initial enable revalida A por SELECT, sin reescribir su canonical/hash.
Request v1 cerrado de 26 campos congela actor/sesión, perfil/closure, A/hash,
pruebas E/historia, T0, fence, código/esquema, G y acción. La confirmación humana
solo acepta el hash exacto y `financial.activation.manage` en la misma cuenta y
sesión vigente escribible. No autoridad IA, admin global, `financial.authorize`,
mandate ni `historical_unknown` para activar.

Los grants durables son exactamente la closure FULL, todos ELIGIBLE; al menos
una capability financiera. NOT_APPLICABLE nunca concede autoridad. Se conserva
el mapping único command/capability C. Los blockers A de E/F siguen intactos;
la evaluación FULL positiva se fabrica únicamente en fixtures sintéticos.

Handoff: gate por negocio → locks → autoridad ready exacta → revalidación sin
pending/uncertain → recibo/G/grants → epoch handed_off/fence=false → control
enabled/ever=true → commit exterior único. La FK diferida recibo/revisión impide
un recibo parcial durable. No usa `HistoryCutoff.release`.
Cut conserva certifiable=true, T0, UUID, hashes, manifiesto, batch y reconciliación;
solo boundary_current deja de ser true. B verifica el corte con el recibo de G1,
normaliza únicamente boundary_current y conserva su resolución byte por byte.
Se prohíbe reabrir epoch/import/reconciliation históricos después de ever_enabled.

Operations y Authorizations incorporan el par nullable G/capability. NULL legado
no se promueve. Cada nuevo efecto exige enabled, Core disponible, misma G, grant
exacto, operación APPROVED y autoridad humana/mandate vigente. COMMITTED se
recupera sin repetir el executor, incluso tras pausa/cambio de G/flag.
Pause cancela PREPARED/APPROVED live y revoca mandates abiertos, conserva evidencia
y registra recibo/snapshot. Resume exige prueba D sin drift, mismo perfil/grants,
sin dispatch incierto; no revive nada ni crea otra evaluación A.

SQLite usa contexto privado de conexión/TX y authorizer que impide COMMIT/ROLLBACK
dentro del contexto. PostgreSQL usa HMAC de backend/TX en GUC local, verificador
privado SECURITY DEFINER y login runtime sin lectura de clave ni privilegios
superuser/createrole/bypassrls. SET ROLE no elude la comprobación de session_user.
No token persistido o claim manual concede autoridad. El contexto desaparece
antes del commit exterior. Los guards SQL exigen también op/G/capability/tenant,
estado, autorización y scope exactos. Testigos diferidos exigen operación COMMITTED
y cobertura por origen de esa operación: una fila extra huérfana no se confirma.
EE estrecha el contexto al UUID/hash/relaciones canónicos de su sobre.

Emitir/rectificar no permite registrar paid_at ni estado de cobro; payment/match
no permite reescribir los importes de factura. SQL final sin contexto falla;
los borradores y sugerencias bancarias operativas permanecen disponibles. Tras
ever_enabled, flag global OFF bloquea nuevos efectos y nunca recupera legacy.
El transporte de respuestas de outbox se conserva; dispatch queda bloqueado
conservadoramente hasta F. D no crea EE ni operaciones por activar ni llama providers.

## Validación y regresiones

| Batería/gate | Resultado |
|---|---|
| D SQLite | PASS: 21/21 en la versión final, 122.660 s |
| D PostgreSQL 16.15 | PASS: 35/35, 68.487 s |
| Matrices PG previas + D | PASS final: 556 casos; C repetida completa 46/46 tras corregir su expectativa |
| General SQLite | 1.940 casos ejecutados en cuatro partes; 1.932 PASS iniciales, 2 skip, 6 defectos de harness/expectativas |
| Retests de los seis casos anteriores + otro de secretos | PASS: 7/7, 2.315 s; cero defectos pendientes |
| JavaScript | PASS: 9/9 |
| HTTP smoke sintético PostgreSQL | PASS: 36 rutas |
| Ruff / Bandit / credential scan / pip-audit | PASS |
| AST de migraciones / registro anterior | PASS: 174 funciones y 76 entradas previas intactas |
| Verdad documental / enlaces nuevos | PASS: 61 enlaces locales válidos, revalidados al cierre |
| Migraciones D | PASS SQLite completo; PASS PostgreSQL 77/76/77 |

No se declara una segunda ejecución completa general limpia: el resultado final
combina los casos ya correctos con retests explícitos de los seis afectados.
No hubo cambios funcionales nuevos tras esos resultados; las correcciones finales
son las fixtures de SQL y las expectativas de esquema. Los dos skip son carreras
exclusivas PostgreSQL omitidas intencionadamente en SQLite; pasan en su matriz PG.
La ejecución inicial general usó Python 3.13; el retest del gate de secretos usó
el entorno del proyecto con su extra security instalado. No se omite ese gate.

Conteos finales de matrices PostgreSQL:

| Matriz | Casos | Resultado final |
|---|---:|---|
| Core | 6 | PASS |
| Operations/Auth | 37 | PASS |
| Economic Events | 28 | PASS |
| Borrowed writers | 18 | PASS |
| InvoiceCapture | 27 | PASS |
| Payment/Bank | 41 | PASS |
| Supplier/Expense | 44 | PASS |
| Channels | 50 | PASS |
| History inventory | 37 | PASS |
| History cutoff | 50 | PASS |
| History import | 25 | PASS |
| History reconciliation | 31 | PASS |
| A readiness | 29 | PASS |
| B antecedents | 52 | PASS |
| C fiscal cancellation | 46 | PASS: repetida completa |
| D handoff | 35 | PASS |

Duraciones generales por parte: 1.422,614 / 1.208,236 / 1.383,154 / 1.253,074 s.
Cada parte cubrió 485 casos. La parte 1 se reinició tras corregir la comprobación
de borrado, conservando su índice de selección. Las ejecuciones antiguas
supersedidas no se incluyen en estos conteos. CI queda preparada con el job D y
margen de 60 min general / 35 min PostgreSQL; no se ejecutó CI remota ni se publica
esta rama.

La suite general se reparte sin duplicaciones por índice en cuatro procesos con
bases SQLite propias, uploads/backups sintéticos y sockets externos bloqueados.
No se usan .env como destino de datos, backups reales ni Noesis19FQA. Las matrices
PostgreSQL usan un cluster descartable localhost/noesis_ci y esquemas nuevos;
D usa un login runtime restringido separado del migrador.

Se verifican las trece carreras obligatorias: handoff mismo request, distinto
request, writer, source drift, invalidación de sesión, pause imposible; pause vs
execute y prepare; resume vs stale execute; dos resume; progreso de otro tenant;
history open; bypass SQL concurrente. Las barreras demuestran contención SQL real
o rechazo mientras el gate está retenido; no se acepta DeadlockDetected.
Se añade una sentencia SQL empezada antes de enable y detenida antes del guard:
el guard debe ver el estado live confirmado y rechazarla tras el handoff.

Crashes de procesos os._exit y excepciones cubren todos los writes durables de
handoff, pause y resume. Incluyen receipt, G, grants, epoch, retirada de fence,
control, cancelaciones/revocaciones y antes/después del commit. Precommit conserva
el estado anterior; pérdida de respuesta postcommit recupera el mismo recibo,
sin duplicar G, grants ni efectos. Las once familias Capture existentes ejecutan
con sus grants precisos. Se prueba SQL adversarial sin contexto, contexto falso,
G/capability/op/tenant/TX incorrectos, replay de COMMITTED y claim copiado.

El snapshot completo de fuentes/Operations/Auth/configuración antes y después
del handoff coincide; no crea Operations ni EE. Los flags reales siguen OFF y
ningún business real se activa. La ruta D rechaza IS_PRODUCTION.

Defectos encontrados y corregidos durante esta entrega:

- Un executor autorizado podía escribir un segundo origen huérfano junto a otro
  correctamente cubierto. Se reprodujo y añadió testigo diferido por fuente,
  limitado a una fuente por operación y a su cobertura exacta.
- Emitir podía intentar usar el mismo contexto para marcar la factura cobrada:
  el guard limita issue/rectify a borrador → enviada, paid_at NULL.
- La inserción de autoridad D necesita stage=authorize; un contexto prepare no
  puede fabricar una confirmación humana.
- Adelantar el gate D en fuentes nunca activadas alteraba el orden C y bloqueaba
  una barrera histórica. Se conserva el orden previo antes del primer enable;
  los tests demuestran protección de la sentencia antigua después del commit.
- El test de migración 69 debía construir su baseline realmente en 68/69, en
  vez de comparar nullable bindings 77 con columnas inexistentes en 69.
  Se ajustó exclusivamente esa fixture; no se filtra ni normaliza evidencia.
- La prueba estructural de borrado no reconocía la lista dinámica D. El borrado
  usa ahora doce nombres explícitos reales, conserva su rechazo de evidencia y
  elimina las tablas solo vacías. Las cuatro regresiones de cuentas pasan; el
  test de handoff prueba rechazo de baja y conservación íntegra del control.

Otros ajustes de validación, sin cambio funcional:

- La conexión SQL estática implementa execute_exact/current_schema y recupera
  las definiciones generadas de cut/readiness anteriores; no omite M77 ni sus
  comprobaciones de FK, SQLSTATE o placeholders.
- La expectativa de LATEST_VERSION en el contrato histórico se actualiza a 77.
- La prueba de downgrade C exige conservar la versión inicial y toda la evidencia
  tras el rechazo, en vez de fijar 76. Pasa SQLite y la matriz PG C completa.
- La dependencia detect-secrets faltaba en Python global; el gate se ejecutó y
  pasó con el entorno del proyecto/extra security, sin modificar requisitos.

## Migraciones y límites

SQLite 77 → 76 → 77 → 0 → 77: PASS, PRAGMA foreign_keys=ON y foreign_key_check vacío.
PostgreSQL 77 → 76 → 77: PASS en schema sintético vacío.
Con evidencia D/bindings/ever_enabled se rechaza downgrade destructivo.
Las CHECK de tres padres se amplían sin modificar fuentes ni valores monetarios;
SQLite reconstruye con FKs activas/copia exacta, sin PRAGMA foreign_keys=OFF ni
renombrar padres. Se prueba con padres poblados y evaluación A sellada.
Las 174 funciones de migración anteriores conservan su AST; 63–76 intactas.

El ciclo PostgreSQL hasta 0 detectó un defecto heredado de SQL de downgrade del
bank reconciliation guard (falta ON), anterior a D. No se cambia esa migración:
el ciclo pertinente 77/76 pasa. No se declara PASS del ciclo PG completo hasta 0.

Provisionamiento y rotación reales de clave/login pertenecen a F. Usar el login
migrador para live falla cerrado. Cambiar SECRET_KEY sin el ciclo previsto también
falla cerrado. La solicitud expira a los cinco minutos. La recuperación es
conservadora: incluso cambios operativos incluidos en el snapshot pueden bloquear
resume y exigir diagnóstico; no se flexibiliza ni reabre la incorporación histórica.
El permiso D es específico pero el modelo actual carece de RBAC tenant más fino;
la separación avanzada de roles corresponde a P15. No se publica ninguna ruta D.

Rollback: antes de evidencia D, downgrade vacío a 76 y volver a la base autorizada.
Después de evidencia D, pausa fail-closed y diagnóstico; no borrar evidencia,
reutilizar autoridad vieja ni volver a legacy. No hay rollback productivo ejecutado.

## Archivos creados/modificados

- `.github/workflows/ci.yml`
- `AGENTS.md`
- `docs/Arquitectura.md`
- `docs/Decisiones.md`
- `docs/Estado-actual-main.md`
- `docs/Mapa-codigo.md`
- `docs/Registro-QA.md`
- `docs/Registro-cambios.md`
- `docs/Tareas-vivas.md`
- `docs/architecture/ADR-022-activation-handoff-generations.md`
- `docs/architecture/FASE-1.10-plan.md`
- `docs/architecture/FASE-1.10D-cierre.md`
- `docs/architecture/FASE-1.10D-orden.md`
- `docs/architecture/FINANCIAL-ACTIVATION-HANDOFF-v1.md`
- `docs/architecture/README.md`
- `docs/areas/01-vision-general.md`
- `docs/areas/04-facturas.md`
- `docs/areas/06-rgpd-y-seguridad.md`
- `docs/areas/08-financial-core.md`
- `docs/project-state.json`
- `src/noesis/db.py`
- `src/noesis/economic_events/service.py`
- `src/noesis/financial_activation/activation_contracts.py`
- `src/noesis/financial_activation/commit_schema.py`
- `src/noesis/financial_activation/configuration_snapshot.py`
- `src/noesis/financial_activation/context_schema.py`
- `src/noesis/financial_activation/contracts.py`
- `src/noesis/financial_activation/evaluator.py`
- `src/noesis/financial_activation/execution_context.py`
- `src/noesis/financial_activation/gate_schema.py`
- `src/noesis/financial_activation/handoff.py`
- `src/noesis/financial_activation/handoff_schema.py`
- `src/noesis/financial_activation/historical_proof.py`
- `src/noesis/financial_activation/live_schema.py`
- `src/noesis/financial_activation/readiness_verifier.py`
- `src/noesis/financial_activation/runtime.py`
- `src/noesis/financial_antecedents/contracts.py`
- `src/noesis/financial_antecedents/proofs.py`
- `src/noesis/financial_history/fence.py`
- `src/noesis/financial_history/reconciliation_verifier.py`
- `src/noesis/financial_history/schema_compatibility.py`
- `src/noesis/financial_operations/contracts.py`
- `src/noesis/financial_operations/repository.py`
- `src/noesis/financial_operations/service.py`
- `src/noesis/financial_writers/boundary.py`
- `src/noesis/financial_writers/recurring.py`
- `src/noesis/migrations.py`
- `tests/financial_activation_handoff_worker.py`
- `tests/fiscal_cancellation_contract.py`
- `tests/payment_bank_capture_contract.py`
- `tests/postgres_financial_activation_handoff.py`
- `tests/test_financial_activation_handoff.py`
- `tests/test_financial_history.py`
- `tests/test_platform.py`

## Criterios de cierre

| Criterio de la orden | Estado | Evidencia |
|---|---|---|
| Handoff sin ventana desprotegida | PASS | SQL concurrente y sentencia previa al enable, commit único |
| Conservación del certifiable histórico | PASS | Snapshot/certificado e identidades antes/después |
| B histórico verificable | PASS | Resolución sellada byte por byte |
| Grants exactos | PASS | Closure FULL/ELIGIBLE, request cerrado y guards |
| Generaciones invalidan autoridad vieja | PASS | Binding G/cap, NULL, pause/resume y mandatos |
| SQL final legacy sin contexto rechazado | PASS | Seis dominios, fake/old/cross-TX/backend/login |
| Borradores no económicos disponibles | PASS | Crear/editar en paused |
| Pause fail-closed | PASS | Cancelación/revocación, carreras y crashes |
| Recovery no revive autoridad | PASS | Nueva G, proof D sin drift, antiguo executor rechazado |
| Precommit rollback completo | PASS | Excepciones y procesos os._exit en cada punto durable |
| Postcommit retry exacto | PASS | Mismo recibo/G/grants/resultado |
| Ningún negocio real activado | PASS | Fixtures propias, flags OFF, production deny, sin acceso real |

12 PASS / 0 FAIL de criterios D aplicables. El defecto heredado del ciclo PG hasta
0 permanece documentado como limitación adicional, no como un ciclo que haya pasado.
Publicación, E/F/G/H, provisionamiento real y piloto siguen sin autorización.

## Autoauditoría de la orden

La evidencia técnica correspondiente está en el contrato, los tests D y los
resultados anteriores. Estas respuestas cubren el control plane D implementado,
los accesos runtime sin privilegios DDL y el alcance local autorizado.

1. ¿Puede D activar producción? **NO.**
2. ¿Puede activar sin FULL exacto? **NO.**
3. ¿Puede conceder not_applicable? **NO.**
4. ¿Puede activar sin human activation authority? **NO.**
5. ¿Puede usar financial.authorize como activation authority? **NO.**
6. ¿Puede liberar fence antes de instalar live protection? **NO.**
7. ¿Puede usar HistoryCutoff.release como handoff? **NO.**
8. ¿Pierde certifiable el histórico al handoff? **NO.**
9. ¿Deja de funcionar B historical por hacer handoff? **NO.**
10. ¿Puede abrirse otro historical epoch después de ever_enabled? **NO.**
11. ¿Puede una operación pre-handoff ejecutarse después? **NO.**
12. ¿Puede una operation de generation vieja ejecutarse? **NO.**
13. ¿Puede una authorization vieja servir en nueva generation? **NO.**
14. ¿Puede un mandate viejo servir en nueva generation? **NO.**
15. ¿Puede un command sin grant ejecutarse? **NO.**
16. ¿Puede un command usar capability distinta? **NO.**
17. ¿Puede SQL legacy emitir/registrar efecto después de enable sin contexto? **NO.**
18. ¿Puede un bypass/claim de otra TX reutilizarse? **NO.**
19. ¿Puede pause crear nuevos efectos? **NO.**
20. ¿Puede pause borrar historia/evidencia? **NO.**
21. ¿Puede resume revivir una autorización vieja? **NO.**
22. ¿Puede resume cambiar el profile en D? **NO.**
23. ¿Puede global flag OFF provocar fallback legacy? **NO.**
24. ¿Puede activation crear Economic Events? **NO.**
25. ¿Puede D hacer provider I/O? **NO.**
26. ¿Puede D cambiar los cinco flags reales? **NO.**
27. ¿Puede otro tenant usar grants/evaluation ajenos? **NO.**
28. ¿Puede una sesión vieja hacer handoff/pause/resume? **NO.**
29. ¿Puede un crash dejar fence OFF sin activation completa? **NO.**
30. ¿Se inició 1.10E? **NO.**

Ninguna revisión remota, aprobación de piloto ni fase posterior se infiere de
estas pruebas. No push/merge/deploy; producción, Noesis19FQA, backups reales y
provider I/O no consultados. Main no se modifica.

El cluster PostgreSQL sintético se detuvo y se confirmó su parada tras todos los
tests. Comprobación final: cinco flags OFF, rama D, padre autorizado y main local
sin cambios. La referencia origin/main comprobada es la local cacheada; no se
consultó el remoto para esta entrega.
