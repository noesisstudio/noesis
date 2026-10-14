# A75 — matriz de paridad semántica con A74 histórico

[Orden](FASE-1.10A75-orden.md), [contrato nuevo](FINANCIAL-READINESS-v2.md), [ADR](ADR-SCHEMA-LINEAGE-002-foundation-a75.md).

Fuente semántica: c910616 exacto; sin cherry-pick/rebase. Tests originales portados
por invariant, fixtures propios, ninguna evidencia real leída o recalculada.

| Invariant/test histórico | Decisión | Caso A75 |
|---|---|---|
| test_empty_minimum_fully_eligible_without_any_financial_side_effect | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_no_provider_event_operation_or_history_write_api | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_baja_with_readiness_retains_evidence_before_deleting_sources | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_reconciliation_missing_even_empty_never_fully | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_unknown_reconciliation_and_different_context | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_history_c_and_blocked_reconciliation_cannot_hide_by_profile | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_registro_anterior_d_never_verified_payment | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_invoice_historical_remains_unsupported | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_exact_profile_dependencies_and_fiscal_cancel | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_partial_requires_new_smaller_profile_no_ready | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_privacy_export_and_provider_are_not_stubbed | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_not_applicable_has_fiscal_evidence_not_missing_function | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_stale_session_wrong_permission_and_tenant | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_idempotent_and_deterministic_without_clock_or_evaluation_uuid | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_same_uuid_different_profile_or_config_conflicts | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_draft_alone_is_empty_but_not_an_issued_antecedent | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_uncertain_dispatch_cannot_hide_behind_empty_history | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_prepared_live_operation_prevents_empty_proof | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_expiry_preserves_evidence_and_fence | ADAPTED FOR LINEAGE | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_final_sql_immutable_control_cannot_enable_or_lose_evidence | ADAPTED FOR LINEAGE | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_cross_tenant_sql_link_rejected | ADAPTED FOR LINEAGE | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_flags_off_and_no_flag_can_be_used_as_permission | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_volume_policy_and_no_relaxation | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_contract_closed_unknown_version_float_and_duplicates | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_source_drift_detected_without_writing_history | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_invalidated_boundary_stays_fenced | SAME | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |
| test_borrowed_transaction_rolls_back_only_new_tables | ADAPTED FOR LINEAGE | mismo contrato SQLite/PG; binding75 previo y sobre2 cuando aplica |

| Invariant adicional histórico | Decisión | Cambio exacto |
|---|---|---|
| Tablas/checks/guards/FKs/actor/session/conservación | ADAPTED FOR LINEAGE | mismas reglas; schema75/evaluation2/readiness_v2; guard prefijo completo |
| Context y proof/hash | ADAPTED FOR LINEAGE | sobre/context/proof2+binding1 actual; hashes NUEVOS |
| Profile/policy/canonical/money/economic/history versiones | SAME | no renumeración por coincidencia física |
| Permiso financiero, FULL/PARTIAL/TTL/deps/empty/source drift | SAME | sin nueva autoridad/activation |
| Reader raw/hash A74 | SAME | nuevo fixture sintético congelado con c910; hash/bytes sin transformación |
| Ciclo A74→73→74 | ADAPTED FOR LINEAGE | A75→CRM74→A75; CRM74 no desaparece |
| Startup/init_db por número | INTENTIONALLY CHANGED | owner separado; runtime75 sólo identidad+perfil; sin DDL/reset |
| History numérico74 | ADAPTED FOR LINEAGE | prefijos canonical70/71/72/73/74/75 exactos; legacy rechazado |
| Borrowed PG snapshot sin registry lock | INTENTIONALLY CHANGED | SHARE primero; late snapshot rechaza, sin downgrade aislamiento |

Los valores físicos74 cambian sólo en nuevos objetosA75. Versiones de negocio1 y
familias económicas/históricas permanecen; ninguna aprobación/hash A74 se reutiliza.
Runtime no instala B76–F80. Tabla de guards mantiene cardinalidad15 proofs, actor
activo/session exacta, boundary PASS actual para FULL, dependencia bloqueante,
inmutabilidad y baja con conservación. No pérdida silenciosa de los27 tests originales.

Regresiones foundation: orden visible PG conserva DROP/ADD con huecos attnum.
Cuerpo DELETE68 historico exacto conserva la reparacion69 original; cualquier
otro cuerpo se rechaza. /ready y backups abandonan MAX como identidad; V2 SHARE
precede snapshot. SAVEPOINT previo al protocolo rechaza sin cambios de TX.

Las fixtures historicas de import/reconciliation alteran deliberadamente nueve
columnas legacy a NUMERIC/TEXT. El producto rechaza esas estructuras. Se conserva
su semantica mediante deltas sinteticos cerrados SOLO en tests: cuatro DDL SQLite,
nueve columnas y un CHECK dependiente PG, versiones71..75. Generados en esquemas
vacios propios con callbacks exactos, nunca desde la DB bajo prueba; sin cambiar
profiles de producto, nombres/registry/funciones/FKs/grants/flags. Hash del perfil
fixture distinto del de producto. Fallback de fixture prohibido en production,
fuera de /noesis_ci local o SQLite temporal, y no admite deltas parciales ni guards
faltantes. Worker solo de tests activa el mismo adaptador; no existe flag/API runtime.
Se prueba rechazo del producto, separacion de hashes y aislamiento de guards.

Reconciliation inyecta datos danados y restaura CHECK como NOT VALID en PG para
poder examinarlos. Solo el adaptador de TEST permite esa variante: misma identidad,
nombre, flags restantes y expresion CHECK (AND/OR asociativos normalizados); no
permite quitar/cambiar checks, FKs, indices ni triggers. El producto sigue
rechazando convalidated=false. No policy/fixture de pruebas se convierte en config.
Los tiempos CI se amplian a180min general/180min PG y30min por matriz PG, debido a
la inspeccion completa en cada TX/pagina. Ningun gate se omite ni cambia el resultado.

Compatibilidad tecnica SQLite sintetica: los callbacks antiguos retienen columnas,
indices y, en ciertos recorridos profundos, omiten triggers operativos al re-upgrade.
Se versionan deltas completos de recorridos75->target->75 generados en DB vacia
propia, sin regeneracion runtime/CI ni expectativas derivadas de la DB examinada.
Solo el owner exclusivo, IS_PRODUCTION=false, DATABASE_URL vacia, DB_PATH temporal
Y fichero real de PRAGMA database_list identico puede reconocer esas estructuras.
El resultado es TECHNICAL_ONLY, nunca VERIFIED. El migrador puede completar la
prueba tecnica; require_compatible, require_runtime, binding, A75 y serving la
rechazan, incluso dentro de esa misma TX. Ninguna variante habilita escritura
financiera ni modifica guards. Un guard financiero ausente, columna adicional,
path diferente, production o consumidor corriente siguen fallando. No se afirma
rollback/recuperacion productiva. Las tres tablas A y sus guards canonicos siguen
intactos; los perfiles canonicos y goldens originales no cambian. El roundtrip
profundo sintetico no es evidencia de que el schema resultante sea apto para servir.
