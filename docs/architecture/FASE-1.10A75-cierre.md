# 1.10A75 — REMOTE VALIDATION PENDING

**REMOTE VALIDATION PENDING. No LOCAL ni REMOTE CODE-VERIFIED PASS todavía.**

[Orden remota](FASE-1.10A75-remote-orden.md). Se prepara un único commit candidato
con padreac6a03d; la evidencia completa debe venir de CI Linux/PostgreSQL18.6
sobre su SHA exacto. El informe local inferior conserva sus resultados incompletos
y límites históricos; no representa el cierre remoto. No se reparará WSL.
Sólo ci.yml cambia respecto a47 archivos congelados; sin cambios funcionales.
Recibo final fuera de Git; ningún segundo commit documental que herede otra CI.

[Orden](FASE-1.10A75-orden.md), [ADR](ADR-SCHEMA-LINEAGE-002-foundation-a75.md),
[contrato](SCHEMA-LINEAGE-FOUNDATION-A75-v1.md), [paridad](FASE-1.10A75-parity.md).

Windows Application/Event1000 confirma caídas de wsl.exe y wslservice.exe con
exception c00000fd, módulos ntdll.dll/KERNELBASE.dll, a22:59:59 y23:15:08 del
13-oct-2026. Windows no se reinició. WSL arrancó repetidamente con cierre anterior
no limpio. Ambas suites supervisadas devolvieron -1073741571 (0xC00000FD); también
cayó el control sin Noesis ni DB. No hay traceback Python que atribuya esas
terminaciones al Financial Core. No se reparó ni reinició globalmente WSL para
preservar la QA real reservada. El bloqueo temporal de suspensión quedó liberado;
sin cambios persistentes de energía.

## Entrega de32 puntos

| # | Entrega | Resultado |
|---|---|---|
| 1 | Rama | codex/phase-1-10a75 local |
| 2 | Base | ac6a03d3b70794a4081c3b1d834581e91edb3133 |
| 3 | SHA local final | No hay commit final; HEAD permanece en base, cambios revisables |
| 4 | Padre | No hay nuevo commit; futuro padre de fase debe ser ac6a03d |
| 5 | Archivos |72 creados/modificados; lista debajo |
| 6 | LATEST_VERSION |75 candidate, no producción |
| 7 |74 | captacion_hoja_y_tipo intacta |
| 8 |75 | evaluacion_readiness_financiera |
| 9 | Estados | CANONICAL_PRE74 / CANONICAL_CRM74 / CANONICAL_CRM74_FINANCIAL75_80 / LEGACY_FINANCIAL74_79 / UNKNOWN_OR_CORRUPT |
| 10 | Fingerprint75 |289b8eb580edd4c45d2de40233ffd7dfc193999b10f49825661cba18905696a1 |
| 11 | Validator | Prefijo completo version/name; sin MAX como autoridad |
| 12 | Objetos | Profiles por motor; ausencias, alteraciones y extras propios rechazan |
| 13 | Locks | Advisory xact2533761095082033151/30s/poll250ms; registry exclusivo y reread; SHARE consumidor primero |
| 14 | Collision CI | Unicidad, append-only, CRM74 y AST/DDL históricos preservados; PASS estático |
| 15 | A parity |27 invariantes originales portados; SAME/ADAPTED/INTENTIONALLY CHANGED explícitos |
| 16 | Startup | Sólo75 VERIFIED; sin DDL/reset/init_db; /ready inspecciona identidad actual |
| 17 | History | Prefijos mínimos70/71/72/73 y74CRM/75A por identidad; legacy bloqueada |
| 18 | V1 | Catálogo75 exacto; no promoción74 ni reinterpretación legacy |
| 19 | V2 | Identidad75/snapshot/restore nativos sin migrations ni serving; final completo pendiente |
| 20 | Privacy |75 NO_E_INSTALLED; E legacy por nombre; policy real provisional/PRIVACY_NOT_READY |
| 21 | Paths | SQLite0→75,73→74→75,74→75 y rechazo legacy PASS; PG final pendiente |
| 22 | Downgrade |75→74 sintético PASS; profundo conocido TECHNICAL_ONLY nunca sirve ni produce binding |
| 23 | Concurrency | SQLite PASS; PG espera/timeout30s/rollback/crashes implementados, matriz final pendiente |
| 24 | Python |74 dirigidos finales PASS/161.594s/0skip/0FAIL/0ERROR; general completa no terminada |
| 25 | PG |18.6 sintético; parcial251 base+37 inventory PASS; inventory502.879s; sin total completo |
| 26 | Node |11 PASS/0FAIL/0skips/264.5613ms |
| 27 | CRM |88 paquete+40 legacy incluidos en general; no cierre fresco completo |
| 28 | A75 | SQLite41 PASS dentro de74; PG29 dirigido anterior no sustituye final |
| 29 | Lineage | SQLite23+collision6 PASS; fixtures4 PASS; PG14 final pendiente |
| 30 | Gates | Ruff/Bandit/secrets/dependency audit/AST/truth/diff/links; recibos en bitácora |
| 31 | Skips/warnings | Dirigidos74 sin skips;2 skips generales PG pendientes de cobertura final. Starlette/httpx deprecado; noesis interno no auditable en PyPI |
| 32 | Riesgos | WSL, falta full regression/PG/V2 final, coste de inspección, roles/imagen productiva pendientes; sharp HIGH separado |

## Decisiones y límites

Evaluaciones/context/proofs2, SchemaBinding1; Profile/Policy/canonical/Money/history
siguen1. A74 bytes/hashes y cinco documentos c910 intactos. Registry bootstrap
corrupto bloquea antes de callbacks. PG compara ordinal visible; DELETE68 sólo
variante histórica exacta previa a reparación69. SAVEPOINT previo al lock rechaza
sin rollback/isolation/commit propios. Cache sólo de lexer/expectativas estáticas.

El migrador puede reconocer TECHNICAL_ONLY para deltas completos de callbacks
legacy compilados en SQLite vacío propio. Exige owner exclusivo, no producción,
sin DATABASE_URL, archivo temporal y PRAGMA database_list vinculado al config.
Nunca VERIFIED, serving, binding ni autoridad financiera. Ningún guard se repara
ni se relaja; missing financial guard, unknown/path distinto/real rechazan.
No se afirma rollback productivo. Los perfiles canónicos y goldens no cambian.

Las fixtures monetarias precisas son deltas cerrados SOLO de test: el producto
rechaza tipos legacy alterados. CHECK NOT VALID sólo en adaptador de corrupción
sintético; sin promoción a configuración real. Una unique constraint EE retirada
bloquea el servicio; el auditor SELECT interno conserva la detección de duplicados.

Wheel final: ambos recursos exactos, zip import PASS, sin adaptador de tests.
SHA256:0558eb13d43aa7ea2f31f2550ebbe3c381b094bdfb0ed373b918f78e7b2c1ae6.
Los47 archivos de código/tests/config permanecen congelados. Recibos y logs fuera
Git: C:\Users\mikic\NoesisSynthetic\phase-1-10a75-20261013.
Validación Linux exclusivamente NoesisBackupV2CRM74Synthetic, namespace sin outbound,
usuario noesisqa, clusters propios. Ningún resultado parcial se suma como full PASS.

## PASS/FAIL de criterios

FAIL incluye evidencia obligatoria incompleta, no únicamente defecto funcional.

| Criterio | Estado |
|---|---|
| Rama/base exacta; sin rebase/cherry-pick | PASS |
| Identidades/nombres/goldens; no MAX-only | PASS |
| Wrong-name/gap/duplicate/future/corrupt/legacy rechazados | PASS |
| Presencia de A/guards y extras propios | PASS |
| Sobres2/binding1; versiones negocio1; A74 intacta | PASS |
| off/validating/generation0/ever_enabled=false; ningún efecto nuevo | PASS |
| Startup/ready sin autoDDL | PASS |
| History por identidad/Decimal/TX compartida | PASS dirigido; full bloqueado |
| V1 identidad exacta75 | PASS de contrato/código; full bloqueado |
| V2 canonical75 final completo | FAIL |
| Privacy NO_E_INSTALLED; policy profesional no promovida | PASS |
| SQLite paths/downgrade75→74 | PASS |
| PG paths/carreras/crashes completos | FAIL |
| TX prestada sin conexión/commit/isolation propio | PASS |
| Tenant/actor/session/flags/IA | PASS dirigido/código |
| Paridad A SQLite | PASS |
| Paridad A PostgreSQL final | FAIL |
| General Python única completa | FAIL |
| Todas matrices PG completas | FAIL |
| Node | PASS |
| CRM general final completa | FAIL |
| Gates estáticos/documentales disponibles | PASS |
| Autoauditoría factual y alcance conservado | PASS |
| Cierre LOCAL CODE-VERIFIED PASS y commit después de suite limpia | FAIL |

## Autoauditoría20

1. Base/rama exactas: sí; historia no reescrita.
2. CRM74 preservada: sí.
3. Sólo75 física nueva: sí.
4. MAX concede compatibilidad: no.
5. Registry solo acredita objetos: no.
6. Legacy/future/gap/corrupt adoptables: no.
7. Locks antes de decisión/snapshot: protocolo implementado; PG final incompleto.
8. Timeout/crash con suite final completa: no, FAIL por infraestructura.
9. Conexión/commit propios en servicios prestados: no.
10. Reinicio/degradación de aislamiento: no.
11. Recalcular A74 evidencia: no.
12. A75 sobre nuevo ligado al schema: sí.
13. Tenant/actor/session/perfil conservados: sí, dirigidos PASS.
14. Cambio Decimal/EUR/JSON monetario: no.
15. IA/readiness conceden ejecución: no.
16. TECHNICAL_ONLY permite serving/binding: no, rechazo probado.
17. Policy/flags/effects reales modificados: no.
18. Acceso producción/QA/dumps reales/providers: no.
19. Full PASS por agregación: no; bloqueo explícito.
20. Commit/publicación/avance pese a bloqueo: no.

## Continuación

Ejecutar la orden remota: inventario original72 fuera de Git, main/base exactos,
commit candidato, push sólo feature y workflow_dispatch. Todos los criterios
remotos pendientes; si alguno falla: REMOTE BLOCKED y detener sin corregir.
El candidato NO acredita serving, autorización, datos reales ni activación.
NO B76/C77/D78/E79/F80/Recovery Bridge/producción/Railway/business15 real/
Noesis19FQA/backups reales/providers/main/PR/merge/deploy/cambio de flags/G-LIVE/H.
origin/main reservado678bd3f; main local histórico e95c19b no modificado.

Sharp HIGH: **SEPARATE SECURITY DEBT / PRE-PRODUCTION TRIAGE REQUIRED**, intacto.

## Archivos

Inventario original72 preservado fuera de Git. El candidato remoto contiene esos72
y una nueva orden documental:73 archivos. El único cambio del conjunto congelado
es ci.yml, permitido por la orden.

- `docs/architecture/FASE-1.10A75-remote-orden.md`
- `.github/workflows/ci.yml`
- `.secrets.baseline`
- `AGENTS.md`
- `docs/Arquitectura.md`
- `docs/Decisiones.md`
- `docs/Estado-actual-main.md`
- `docs/Mapa-codigo.md`
- `docs/Registro-QA.md`
- `docs/Registro-cambios.md`
- `docs/Tareas-vivas.md`
- `docs/architecture/ADR-019-financial-readiness.md`
- `docs/architecture/ADR-SCHEMA-LINEAGE-002-foundation-a75.md`
- `docs/architecture/FASE-1.10-plan.md`
- `docs/architecture/FASE-1.10A-cierre.md`
- `docs/architecture/FASE-1.10A-orden.md`
- `docs/architecture/FASE-1.10A75-cierre.md`
- `docs/architecture/FASE-1.10A75-orden.md`
- `docs/architecture/FASE-1.10A75-parity.md`
- `docs/architecture/FINANCIAL-READINESS-v1.md`
- `docs/architecture/FINANCIAL-READINESS-v2.md`
- `docs/architecture/README.md`
- `docs/architecture/SCHEMA-LINEAGE-FOUNDATION-A75-v1.md`
- `docs/areas/01-vision-general.md`
- `docs/areas/06-rgpd-y-seguridad.md`
- `docs/areas/07-lo-automatico.md`
- `docs/areas/08-financial-core.md`
- `docs/project-state.json`
- `pyproject.toml`
- `scripts/build_schema_profiles.py`
- `scripts/check_schema_lineage.py`
- `scripts/run_postgres_backup_lab.py`
- `src/noesis/core/schema_lineage_catalog.json`
- `src/noesis/core/schema_object_profiles.json`
- `src/noesis/db.py`
- `src/noesis/financial_activation/__init__.py`
- `src/noesis/financial_activation/contracts.py`
- `src/noesis/financial_activation/evaluator.py`
- `src/noesis/financial_activation/repository.py`
- `src/noesis/financial_activation/schema.py`
- `src/noesis/financial_history/cutoff.py`
- `src/noesis/financial_history/importer.py`
- `src/noesis/financial_history/reconciliation.py`
- `src/noesis/financial_history/service.py`
- `src/noesis/migrations.py`
- `src/noesis/readiness.py`
- `src/noesis/schema_lineage.py`
- `src/noesis/schema_objects.py`
- `src/noesis/web/backups.py`
- `src/noesis/web/postgres_backup_identity.py`
- `src/noesis/web/postgres_native_backup.py`
- `src/noesis/web/routers/webhooks.py`
- `src/noesis/web/server.py`
- `tests/a74_frozen_fixture.py`
- `tests/financial_history_import_contract.py`
- `tests/financial_history_import_worker.py`
- `tests/financial_history_reconciliation_contract.py`
- `tests/financial_history_reconciliation_worker.py`
- `tests/financial_readiness_contract.py`
- `tests/postgres_backup_v2.py`
- `tests/postgres_financial_readiness.py`
- `tests/postgres_schema_lineage.py`
- `tests/schema_lineage_worker.py`
- `tests/synthetic_exact_schema_profiles.json`
- `tests/synthetic_schema_profiles.py`
- `tests/test_financial_a75.py`
- `tests/test_financial_readiness.py`
- `tests/test_financial_readiness_migrations.py`
- `tests/test_lineage_startup.py`
- `tests/test_postgres_backup_identity.py`
- `tests/test_schema_collision_guard.py`
- `tests/test_schema_lineage.py`
- `tests/test_synthetic_schema_profiles.py`
