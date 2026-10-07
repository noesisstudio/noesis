# Fase 1.10E — CODE-VERIFIED PASS técnico local

Fecha: 2026-10-07. Rama codex/phase-1-10e, base exacta de la orden.
Base/padre exacto: 8a775989e350daf3c2bb8c4f9c4d515b7b3ef696. Entrega local sin push.
No constituye aceptación profesional de una política real ni autorización F.

## Alcance implementado

[Orden](FASE-1.10E-orden.md), [ADR023](ADR-023-financial-privacy-export-retention.md),
[contrato v1](FINANCIAL-PRIVACY-EXPORT-RETENTION-v1.md),
[custodia QA](FINANCIAL-QA-CUSTODY-RUNBOOK.md).

Dominio financial_privacy con contratos/catálogo/snapshot/manifest durable,
políticas/inventario, plan/autoridad/receipt/tombstone y restore overlays.
Migration78 aditiva; nueve tablas protegidas, tuplas explícitas 78.
Account/client export HTTP mantiene auth existente. Cliente financiero conserva
subgrafo y permite sólo minimización autenticada con policy formal aprobada.
Cierre invalida acceso local, mantiene evidencia y exige pausa D previa.
Readiness sólo retira dos motivos E cuando existan pruebas válidas; no activa.

## Límites de diseño v1

- Política real pendiente: no plazos legales inventados, ningún piloto real.
- Documentos/bytes conservados: no filesystem delete, crashes de cleanup no aplican.
- Export materializado con paginación interna, no memoria constante ni SLO productivo.
- Bundle privado de supresiones requiere actualidad operativa al handoff; restore
  externo fuera del hook debe adoptar protocolo, servicio permanece detenido sin él.
- Roles DB con DDL quedan fuera del threat model de guards runtime.
- Sin revocaciones remotas: acciones pendientes requieren fase/autorización posterior.
- Lectura legacy interna sin Principal no acredita manifest E ni readiness.
- Un cierre autorizado stale falla cerrado: no rebase ni recuperación automática;
  requiere diagnóstico/revisión humana antes de otra operación autorizada.
- E local: sin push, merge, deploy, datos reales, providers ni F–H.

## Evidencia final

Matrices E50 SQLite/62 PostgreSQL y todas las matrices PostgreSQL618 PASS.
General completa2011 ejecutada; resultado inicial2006 PASS/2 skips/3 errores
exclusivamente en la fixture RecordingPGConn. Corrección sólo de test para devolver
la definición D real a pg_get_functiondef. Módulo plataforma completo32 PASS
(39.958 s), incluidos los tres casos antes fallidos. Cobertura final2009 PASS/2 skips;
no una única ejecución general limpia después de la última corrección de fixture.
Los skips son únicamente PG gate try-lock/repeatable snapshot en SQLite; ambos
comportamientos están probados en las matrices PostgreSQL. No skips E.

| Partición fresh por índice | Casos | PASS inicial | Error fixture | Skips | Segundos |
|---|---:|---:|---:|---:|---:|
| 0 | 503 | 501 | 1 | 1 | 1436.203 |
| 1 | 503 | 501 | 1 | 1 | 1408.328 |
| 2 | 503 | 503 | 0 | 0 | 1420.141 |
| 3 | 502 | 501 | 1 | 0 | 1321.641 |

Los manifests de selección verificaron unión de índices0..2010 exacta, sin omisión
ni solapamiento; cada partición consumió todos sus casos. No se suman retests ni
matrices PG como si fueran casos nuevos de la general. Sólo el módulo afectado se
repitió tras corregir la fixture; producto/SQL no cambiaron por ese fallo.
CI remota E no ejecutada: la orden exige entrega local y prohíbe push.

## Contratos, integración y preservación

El [contrato completo](FINANCIAL-PRIVACY-EXPORT-RETENTION-v1.md) define los cuatro
purposes, formato/manifest, política versionada/categorías, inventario, privacidad
existente, cierre, guards y restauración. El catálogo literal permite 61 secciones
financieras, ocho tablas E y el overlay de restore. El scope de cliente se recorre
por FKs fuertes; los registros no atribuibles no se copian. No claves globales,
passwords/tokens/secrets ni chats/cuerpo de email en export profesional. HTTP
mantiene attachment/no-store y auth/tenant/SV. No endpoint de cierre financiero IA.

Política real: **PROVISIONAL / APROBACIÓN PROFESIONAL PENDIENTE**. No migración
que la apruebe y no plazo legal nuevo. NULL mantiene revisión/ausencia de purga,
no certifica retención infinita. El inventario conserva counts/hashes/refs y un
allowlist de campos; fuera de ese allowlist no hay acción v1. Las aprobaciones de
tests son sintéticas y jamás habilitan un piloto real.

Plan/hash humano/auth/receipt/tombstone comparten tenant/actor/SV y revalidación.
Solicitud administrativa sola no bloquea actividad; autorización formal sí.
La aplicación conserva Financial Core y compara financial_proof_hash antes/después
en la misma TX; invalidación/minimización revierte si cambió prueba. Reintento
postcommit devuelve receipt exacto. Cuenta ever_enabled requiere pausa D previa;
E no cambia generación, grants, fence/handoff ni transiciones. Default provisional
mantiene PRIVACY_NOT_READY, nuevo export correcto sólo retira el motivo de export.
Con policy aprobada y evidencia vigente sólo desaparecen los dos motivos E.

Supresiones sin PII reaplicadas en startup/drills antes de servir, incluso cuando
el cierre/supresión ocurrió después del backup sintético. Bundle vigente privado
firmado + overlay durable y selectores business/client. La copia antigua sola no
sabe qué ocurrió después: una restauración fuera de los hooks debe cumplir el
protocolo y renovar registro al handoff; sin él no se certifica servicio seguro.
Client_contact no cierra el negocio. No se ejecutó restore real en E.

## Concurrencia, crashes y side effects

PostgreSQL prueba export vs payment, invoice, pause y closure; dos exports misma
UUID; dos planes y una sola autoridad formal; dos applies y un solo recibo;
closure vs write/resume/privacy_request duplicada; progreso de otro tenant.
Los snapshots son ANTES íntegro o DESPUÉS íntegro. Si cierre invalida SV durante
export, el último registro de manifest falla y no se entrega contenido.
El escaneo de lectura no toma gate; el registro posterior sí lo toma brevemente.

Procesos PostgreSQL reales os._exit(17): before_plan, after_inventory,
after_authorization, before_minimization, during_minimization, before_commit,
after_commit. Precommit no deja efecto parcial; postcommit devuelve prueba exacta.
SQLite también comprueba rollback y retry por excepciones en checkpoints.
Filesystem before/during/after cleanup: **NO APLICA**, todos los bytes están
conservados y Path.unlink se rechaza en una prueba de cierre. E no anuncia cleanup
completado, no implementa borrado FS ni una tabla vacía que lo finja.

Hash de evidencia y pruebas de D/history conservados, nueva autoridad financiera
no existe, ningún provider importado por el dominio E. Cinco flags OFF. Smoke
startup/HTTP con scheduler sustituido y outbound no local bloqueado.

## Medición reproducible

`python -m tests.financial_privacy_benchmark` y variante postgres admiten sólo
fixtures locales descartables. Cada export contiene exactamente 64 items de
diagnóstico histórico (63 fuentes + identidad fiscal), 1000 EE generados por
ExpenseCapture real con aprobación sintética, 501 movimientos y 501 email outbox.
No se ha medido producción ni una reconciliación histórica certifiable de ese volumen.

| Motor | Export (s) | Pico Python (bytes) | JSON canónico (bytes) | Preparación 1000 EE (s) |
|---|---:|---:|---:|---:|
| SQLite | 4.828 | 21275694 | 5761677 | 268.391 |
| PostgreSQL 16.15 | 7.344 | 21529368 | 5786943 | 98.672 |

tracemalloc mide pico de asignación Python durante export, no RSS de DB/OS.
Ejecución concurrente con suites locales; resultados orientativos, **no SLO**.
No truncamiento; verificador de manifest PASS. Lectura paginada, resultado final
materializado en memoria. Para datos mucho mayores falta presupuesto explícito.
El primer fixture produjo 65 items al contar identidad fiscal; se ajustó a 63
fuentes + identidad, sin cambiar clasificación ni ocultar registros del export.

## Correcciones descubiertas durante QA

- Dos errores de fixture E (INSERT outbox usaba columna inexistente/body y un
  vínculo bancario omitía el servicio capturado). Se usan text_body/next_attempt_at
  y BankCapture.review_match/execute; ningún guard relajado para pasar el test.
- La regresión PostgreSQL de cobros detectó consulta de versión por cursor legacy.
  Corrección funcional E: installed/version checks ahora usan FinancialSession
  exacta, no _normalise_row. Matriz completa de cobros repetida: 41 PASS. Matriz E
  PostgreSQL final repetida: 62 PASS. Suite general completa ejecutada tras ese
  cambio; desglose y retest final de fixture de plataforma arriba.
- Credential scan de archivos nuevos detectó tres literales de fixture sintético
  (marcador/password falso de restore/password HTTP). Anotaciones puntuales según
  convención del repo; sin baseline global ni detector deshabilitado. La lista cerrada de categorías/acciones
  provocó después un falso positivo de Secret Keyword por credentials_secrets;
  excepción exacta documentada en esa línea, cambio sólo de comentario/AST idéntico.
  Scan de todos los archivos de entrega PASS. No secretos reales ni PII real.
- La prueba exacta de inventario omitía BEGIN en SQLite. Se corrigió sólo el
  fixture para respetar la sesión/TX prestada; el contexto firmado sigue rechazando
  escritura fuera de TX. Matriz E SQLite completa repetida: 50 PASS. La suite
  general definitiva se inició después de verificar esa matriz.
- El humo PostgreSQL existente generó dos artefactos **sintéticos** en backups/.
  Se trasladaron al área temporal del cluster descartable y backups/ se excluye
  explícitamente de Git. No dumps/exports sensibles en la entrega. Configuración
  del runner general fija DB/uploads/backups sintéticos fuera del repositorio.
- Smoke HTTP bloqueó inicialmente también el socketpair loopback de asyncio
  Windows. El guard del smoke permite exclusivamente loopback; outbound externo
  sigue rechazado. Arranque/export/account PASS. No cambio en producto.
- La autoauditoría amplió el guard SQL de UPDATE a OLD y NEW: cambiar business_id
  no permite sacar una fuente de un negocio cerrado hacia otro abierto. La prueba
  existente de cierre formal incluye ese intento y se repite toda E en ambos
  motores después del cambio. Este es un ajuste de guard SQL de migration78 E,
  no de una migración anterior ni de comportamiento legacy de cuentas abiertas.

## Criterios de cierre técnico

| Criterio de la orden | Resultado / evidencia |
|---|---|
| Export financiero completo, consistente y verificable | PASS; catálogo, snapshot y manifest verificado |
| Sin límites silenciosos | PASS; 501 filas y 1000 EE comprobados |
| Secretos excluidos | PASS; allowlist, marcadores y verificador global fuera |
| A–D/history exportables con provenance | PASS; integración history→import→reconcile→B→D→export→pause→closure en ambos motores |
| Inventario de retención durable | PASS; inmutable y ligado a policy/hash/contexto |
| Sin plazos inventados | PASS; provisional/hold, fecha de purga NULL |
| Provisional no habilita activación real | PASS; PRIVACY_NOT_READY persiste |
| Cierre conserva evidencia del Financial Core | PASS; hash financiero antes/después y guards |
| Cierre post-D requiere pause | PASS; PAUSE_REQUIRED y generaciones/grants intactos |
| Closed bloquea resume y nuevos efectos | PASS; aplicación/SQL/outbox y OLD/NEW tenant |
| Restore reaplica supresiones | PASS dentro del protocolo; overlays cuenta/cliente sobre copias antiguas sintéticas |
| Coherencia filesystem/DB | PASS; todos los bytes retenidos, ningún cleanup anunciado |
| Cross-tenant | PASS; principal/FKs/subgrafo/carreras |
| Todos los gates y suite completa | PASS; cobertura general completa cerrada con retest íntegro de plataforma32, detalle de errores iniciales arriba |

La autoauditoría eliminó el campo adicional actions de las tombstones. Los campos
son exactamente el máximo técnico de la orden: version/business/UUID/scope/category/
policy/selector_version/selector/evidence_hash/applied_at. category es una lista
cerrada ordenada; el replay se deriva de scope/category y se contrasta con receipt.
El contrato rechaza campos adicionales, categorías desconocidas/vacías y bool como
versión. Tests comunes en ambos motores incluyen esas aserciones. No se trata de
migrar evidencia previa: E todavía no está publicada; es el formato final v1.
Las ejecuciones generales anteriores se interrumpieron para no presentar código
intermedio como suite final; las matrices E se repiten completas antes del cierre.

## Autoauditoría (perímetro runtime y protocolo documentado)

1. ¿Puede E activar un business? **NO.** Sólo metadatos/privacidad.
2. ¿Puede E hacer handoff? **NO.** Sin writer de handoff.
3. ¿Puede E cambiar generation/grants D? **NO.** Prueba antes/después.
4. ¿Puede E cambiar los cinco flags? **NO.** OFF, no escritor config.
5. ¿Puede E hacer provider I/O? **NO.** Acciones sólo locales.
6. ¿Puede un export leer otro tenant? **NO.** SQL/Principal/FKs/test.
7. ¿Puede un client export incluir otro cliente? **NO.** Subgrafo fuerte/test.
8. ¿Puede truncar silenciosamente a 500? **NO.** 501/1000 verificados.
9. ¿Puede mezclar dos snapshots? **NO.** Una conexión/TX, carreras PG.
10. ¿Puede contener passwords/tokens/keys? **NO.** Allowlist y marcadores.
11. ¿Puede exportarse financial_execution_verifier_key? **NO.** Excluido global.
12. ¿Puede una evaluación A vieja modificarse? **NO.** Append-only conservado.
13. ¿Puede PRIVACY_NOT_READY desaparecer con provisional? **NO.** Test explícito.
14. ¿Puede migration autoaprobar policy legal? **NO.** Ninguna fila aprobada.
15. ¿Puede E inventar plazo legal? **NO.** Sin fecha de purga v1.
16. ¿Puede closure borrar EE? **NO.** Conservación/hash/guards.
17. ¿Puede borrar Operations/Auth requeridas? **NO.** Conservación/hash/guards.
18. ¿Puede borrar history A–E? **NO.** Sin cascade ni reescritura.
19. ¿Puede borrar A/B/C/D evidence? **NO.** Hash de prueba antes/después.
20. ¿Puede reescribir hashes para anonimizar? **NO.** Canonical originales intactos.
21. ¿Puede ejecutarse enabled sin pause? **NO.** PAUSE_REQUIRED.
22. ¿Puede dejar PREPARED/APPROVED ejecutables? **NO.** Bloqueo y revalidación.
23. ¿Puede cuenta cerrada hacer resume? **NO.** Aplicación y SQL.
24. ¿Puede volver a legacy financiero? **NO.** Closed guard y SQL.
25. ¿Puede tombstone guardar PII borrada? **NO.** Constructor cerrado IDs/hashes.
26. ¿Puede FS borrarse antes de commit DB? **NO.** No FS delete E.
27. ¿Puede restore autorizado ignorar supresión aplicada? **NO.** Registro vigente
    obligatorio/overlay/replay antes de servir; restore externo sin protocolo no
    es un restore certificado por E y no debe habilitarse.
28. ¿Puede downgrade borrar evidencia E? **NO.** Falla con cualquier tabla E llena.
29. ¿Puede E destruir Noesis19FQA o backup real? **NO.** Sólo runbook, sin acceso.
30. ¿Se inició 1.10F? **NO.** F–H siguen sin autorización.

El propietario DB con DDL puede desactivar protecciones: no se confunde con SQL
runtime firmado/sin clave. Los treinta NO no prometen control sobre operaciones
administrativas externas que omitan los hooks o sobre una DB tomada por su dueño.

La integración histórica usa corte e import/reconciliation PASS reales del fixture
sintético, persistencia/revalidación B y handoff D. La eligibility FULL se sustituye
por el fixture estructural D; no certifica readiness real ni habilita piloto. Export
anterior/posterior al cierre conserva exactamente history/EE/ops/auth/B/D/fuentes.
Las dos variantes SQLite/PostgreSQL imprimieron PASS. El primer intento tenía
una aserción de test equivocada: la columna B es result_canonical y contiene el
result, no el wrapper de resolución. Se corrigió el fixture, sin tocar B/producto.
La CI añade esta comprobación separada en ambos motores; YAML validado localmente.

## Inventario de archivos de la entrega


Dominio E:

- `src/noesis/financial_privacy/__init__.py`
- `src/noesis/financial_privacy/catalog.py`
- `src/noesis/financial_privacy/client.py`
- `src/noesis/financial_privacy/closure.py`
- `src/noesis/financial_privacy/contracts.py`
- `src/noesis/financial_privacy/dispatch.py`
- `src/noesis/financial_privacy/export.py`
- `src/noesis/financial_privacy/repository.py`
- `src/noesis/financial_privacy/restore.py`
- `src/noesis/financial_privacy/retention.py`
- `src/noesis/financial_privacy/schema.py`

Integración y migración:

- `src/noesis/db.py`
- `src/noesis/financial_activation/contracts.py`
- `src/noesis/financial_activation/evaluator.py`
- `src/noesis/financial_activation/handoff.py`
- `src/noesis/financial_activation/readiness_verifier.py`
- `src/noesis/financial_antecedents/contracts.py`
- `src/noesis/financial_history/fence.py`
- `src/noesis/financial_history/schema_compatibility.py`
- `src/noesis/migrations.py`
- `src/noesis/web/backups.py`
- `src/noesis/web/routers/account.py`

Pruebas y CI:

- `.github/workflows/ci.yml`
- `tests/financial_privacy_benchmark.py`
- `tests/financial_privacy_history_integration.py`
- `tests/financial_privacy_worker.py`
- `tests/postgres_financial_privacy.py`
- `tests/test_financial_privacy.py`
- `tests/test_financial_history.py`
- `tests/test_platform.py`

Gobernanza y documentación:

- `.gitignore`
- `AGENTS.md`
- `docs/Arquitectura.md`
- `docs/Decisiones.md`
- `docs/Estado-actual-main.md`
- `docs/Mapa-codigo.md`
- `docs/Registro-QA.md`
- `docs/Registro-cambios.md`
- `docs/Tareas-vivas.md`
- `docs/architecture/ADR-023-financial-privacy-export-retention.md`
- `docs/architecture/FASE-1.10-plan.md`
- `docs/architecture/FASE-1.10E-cierre.md`
- `docs/architecture/FASE-1.10E-orden.md`
- `docs/architecture/FINANCIAL-PRIVACY-EXPORT-RETENTION-v1.md`
- `docs/architecture/FINANCIAL-QA-CUSTODY-RUNBOOK.md`
- `docs/architecture/README.md`
- `docs/areas/06-rgpd-y-seguridad.md`
- `docs/areas/08-financial-core.md`
- `docs/project-state.json`

Sólo código/documentación/pruebas; ningún dump/DB/export/binario sensible.

La suite general detectó una expectativa heredada de schema77 en
FinancialHistoryContractsTest. Sólo esa expectativa se actualizó a78; los cinco
flags siguen comprobándose OFF. Los 39 contratos de history repitieron PASS.
Se interrumpió la ejecución que había cargado la expectativa vieja; la suite final
se ejecuta íntegra desde cero repartida por índice de discovery en cuatro procesos
locales aislados, no reutiliza casos ni resultados anteriores. Cada proceso
bloquea outbound no loopback y escribe DB/uploads/backups sintéticos separados.
La unión de índices debe cubrir exactamente todos los casos de discovery.

## Resultados PostgreSQL finales por matriz

| Matriz | Pruebas distintas | Resultado |
|---|---:|---|
| Core | 6 | PASS |
| Operations/Auth | 37 | PASS |
| EE persistence | 28 | PASS |
| Borrowed writers | 18 | PASS |
| Invoice capture | 27 | PASS |
| Payment/bank | 41 | PASS |
| Purchasing | 44 | PASS |
| Channels | 50 | PASS |
| History inventory | 37 | PASS |
| History cutoff | 50 | PASS |
| History importer | 25 | PASS |
| History reconciliation | 31 | PASS |
| Readiness A | 29 | PASS |
| Antecedents B | 52 | PASS |
| Fiscal cancellation C | 46 | PASS |
| Handoff D | 35 | PASS |
| Privacy E | 62 | PASS (34.118 s, contrato final de tombstone) |

Total: **618 pruebas distintas PASS**. Payment/bank tuvo un fallo inicial E
de cursor legacy y se repitió completa tras la corrección (41 PASS); no se oculta
esa ejecución fallida. E PostgreSQL también se repitió completa después (62 PASS).
SQLite E final (89.074 s): **50 PASS**, incluida sesión exacta con normalizador legacy
prohibido. General completa y retest de fixture descritos arriba; no se infiere su resultado de estas matrices.

Otros resultados ya comprobados: humo migration32→vigente y postgres_smoke;
código baseline53 sobre schema78; release/rollback/privacy HTTP; ciclo vacío
PG78→77→78; ciclo SQLite78→77→78→0→78 con FKs ON; downgrade con evidencia
E rechazado. AST de 176 funciones y 77 entradas de registry anteriores intactos.
JS9 PASS, Ruff/Bandit/credential scan (incluidos archivos nuevos)/pip-audit PASS.
1518 enlaces locales finales PASS. Sólo rutas locales, no comprobación de URLs externas.

Los clusters descartables PostgreSQL16.15 (loopback/noesis_ci, uno inicial y otro fresco para el contrato final de tombstone) se detuvieron después de matrices/retests e integración histórica. Se
verificó no server running tras sus pruebas. No se operó sobre otro cluster.
No se accedió a Noesis19FQA, copias/snapshots/backups reales ni producción.
Restauración antigua de cliente repetida manualmente con el formato final: registro
vigente posterior al backup minimiza sólo el cliente objetivo, conserva factura
exacta y otro cliente, negocio permanece activo/admite gasto. PASS. La aserción
inicial del smoke usaba una etiqueta inglesa de estado que no es la del producto;
se sustituyó por comparación exacta de la factura antes/después, sin cambio de código.


## Cierre y pendientes

**1.10E CODE-VERIFIED PASS TÉCNICO — POLÍTICA LEGAL REAL PENDIENTE PARA ACTIVACIÓN.**
La evidencia cubre la infraestructura local. No es aprobación jurídica ni aceptación
operativa de un piloto. No hubo acceso a producción/Noesis19FQA/copias reales,
provider I/O, destrucción real, push/merge/deploy ni inicio F–H. Main no se operó.
48 archivos iniciales más fixture test_platform: **49 archivos** finales, todos
incluidos en el inventario. Sin dependencias nuevas ni cambios de schemas anteriores.
