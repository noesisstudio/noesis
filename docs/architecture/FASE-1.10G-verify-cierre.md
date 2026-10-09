# Fase 1.10G-VERIFY — cierre técnico local

Estado: **CODE-VERIFIED PASS técnico local**. REAL permanece
**PILOT_BLOCKED — EXTERNAL PREREQUISITES PENDING**. G-LIVE no autorizado;
H no iniciada. Rama codex/phase-1-10g-verify; base/padre exacto en la orden.
No main/rebase/merge/push/deploy ni acceso producción/QA/backups/providers.

## Implementación

- Catálogo cerrado de 20 verificadores y seis tipos de evidencia, TTL/contexto/
  autoridad/origen/algoritmo/roles/scope/failures explícitos.
- PilotVerifiers separado de assess G-PREP; TrustStore vacío por defecto,
  objetos opacos sellados, revalidación de fuentes A/history/B/E/F y recibos
  autenticados específicos. Ningún endpoint/CLI/collector real se configura.
- PilotGate exige todos los verificadores actuales/coherentes; cruza actores,
  backup/restore/custodio/monitoring y runtime probes. Canonical/SHA256/sello
  privado invalidan manipulación. READY mantiene activation_authorized=false.
  Synthetic READY es sólo SYNTHETIC_STRUCTURAL; REAL sigue bloqueado por D.
- RecoveryReadiness D79 específica: A original intacta aunque caduque, mismo
  perfil/closure/grants, G anterior/pausa/snapshot/history/EE/B/E/F actuales.
  Cada EE live nuevo exige binding D y grants de su generación; fuentes nuevas
  sin prueba B/EE y secuencias incoherentes bloquean. F79 guarda la proof actual
  en context y D compromete su hash sólo en receipts nuevos de resume.
- Sin migration80, sin cambios de migrations63–79, db.py, config o adapters.
  Primera activación conserva TTL A; schema77/78 y receipts/hash previos intactos.
  Cinco flags reales OFF, E real PROVISIONAL/PENDIENTE DE APROBACIÓN PROFESIONAL;
  PRIVACY_NOT_READY sigue bloqueando readiness real.

## Archivos y contratos

Nuevos: financial_pilot/verification_contracts.py, evidence.py, verifiers.py,
gate.py; financial_activation/recovery_readiness.py; contratos/tests G compartidos
SQLite/PostgreSQL y recovery. Cambios acotados en handoff D, preflight/validation F
para el nuevo resume79; A permite lectura sin lock sólo para G en snapshot
consistente, manteniendo el default locking=True de D/F y FULL intacto.
Workflow añade sólo la matriz G sintética futura.
Gobernanza/estado/área08/mapa/decisiones/QA/bitácora actualizados en esta rama.

[Orden](FASE-1.10G-verify-orden.md), [ADR025](ADR-025-pilot-verification-recovery-continuity.md),
[Pilot verification v1](FINANCIAL-PILOT-VERIFICATION-v1.md),
[RecoveryReadiness v1](FINANCIAL-RECOVERY-READINESS-v1.md).

## Validación final

Una ejecución fresca de la colección general completa actual: **2144 total,
2142 PASS, 2 skips conocidos, 0 FAIL, 0 ERROR**, 2073.016 s de tiempo
real. Discover test_*.py en 94 módulos; el multiset exacto de IDs se ejecutó
con cuatro procesos aislados por módulo y huella de src/tests comprobada antes
y después de cada worker. No se agregaron ejecuciones anteriores ni retests.
Los ajustes finales preceden a esta ejecución; no cambió src/tests durante ella.

SQLite G: PilotVerification24 +Recovery12 =36 PASS; G-PREP34, A/D/E/F/B y
Operations/Auth/EconomicEvents incluidos en la misma suite general fresca.
Los dos skips son exclusivamente HistoryCutoffSQLite:

- test_pg_direct_sql_busy_fails_closed_no_gate_inversion: locking PG, cubierto
  por HistoryCutoffPostgres; la carrera SQLite común también se ejecuta.
- test_pg_repeatable_snapshot_direct_sql_rejected: aislamiento PG, ejecutado
  en HistoryCutoffPostgres.

PostgreSQL **16.15**, cluster nuevo descartable sólo loopback, datos sintéticos:
**724 casos únicos de matrices, todos PASS**. Tras el último ajuste de A para
lectura consistente y el test físico READ ONLY, se ejecutaron de nuevo A29/D35/
F69/G37 juntos: **170 PASS, 0 skips/FAIL/ERROR, 486.178 s**. Esa repetición no se
suma a los 724 casos únicos ni se presenta como una segunda suite general.
El cluster sintético se detuvo al finalizar PG.

| Matriz PostgreSQL | Casos | Resultado |
|---|---:|---|
| Core | 6 | PASS |
| Operations_Auth | 37 | PASS |
| EconomicEvents | 28 | PASS |
| Borrowed_writers | 18 | PASS |
| Invoice_Capture | 27 | PASS |
| Payment_Bank | 41 | PASS |
| Supplier_Expense | 44 | PASS |
| Channels | 50 | PASS |
| History_inventory | 37 | PASS |
| History_cutoff | 50 | PASS |
| History_import | 25 | PASS |
| History_reconciliation | 31 | PASS |
| A | 29 | PASS |
| B | 52 | PASS |
| C | 46 | PASS |
| D | 35 | PASS |
| E | 62 | PASS |
| F | 69 | PASS |
| G_VERIFY | 37 | PASS |

G37 contiene PilotVerification25 (incluye TX PostgreSQL REPEATABLE READ READ
ONLY en servidor sintético) +Recovery12. El código final A/D/F/G está cubierto por la repetición
fresca170; el resto de matrices no sufrió cambios de código.

JavaScript: **9 total/9 PASS/0 FAIL**. Ruff global, Bandit global, credential
scan completo y dependency audit PASS; no nuevas excepciones de secretos.
El paquete editable noesis queda excluido por no estar publicado en PyPI; las
dependencias consultadas no presentan vulnerabilidades conocidas.

Migraciones SQLite79→0→79 PASS; PostgreSQL32→79 PASS; AST íntegro de las 79
migraciones sin cambios respecto a la base exacta. Código legacy esquema53
sobre BD sintética79 PASS. HTTP smoke36 rutas PASS; restore/rollback/privacy
sintético PASS. Integración history→B→D→export→pause→closure PASS en ambos
motores. Documentation truth y enlaces locales PASS. No servidor externo,
CI remota o provider real fue invocado.

[Resumen verificable de resultados](FASE-1.10G-verify-evidencia.json).
Logs de esta sesión fuera de Git en TEMP/noesis-gverify-final-source
(general-final.json/collection.json/logs por módulo) y
TEMP/noesis-gverify-local-evidence (matrices PG/gates). No contienen datos reales.
La CI histórica G-PREP no se usa como evidencia final G-VERIFY.

## Criterios de cierre PASS/FAIL

| Criterio | Resultado | Evidencia |
|---|---|---|
| G-PREP incapaz de fabricar READY | PASS | assess sin cambios; G-PREP34 |
| Catálogo cerrado y seis tipos con autoridad/scope/TTL/algoritmo | PASS | contrato v1; pruebas de contrato |
| Sólo verifiers específicos producen evidencia aceptada | PASS | TrustStore cerrado/objetos opacos/negativos |
| READY exige evidencia completa/current/coherente | PASS | omisiones, drift, expiración, relaciones |
| READY no activa; synthetic no es real | PASS | activation_authorized=false; guard REAL |
| Anti-tamper/canonical/contexto/tenant | PASS | manipulación de evidence/resultado/hash/scope |
| Gate y verifiers read-only | PASS | no DML/red; SQLite query_only; PG READ ONLY |
| EMPTY exhaustivo; draft documental permitido | PASS | A–F/operaciones/autoridades/history/closure |
| A/B/history/E/F reutilizados sin promoción | PASS | proofs existentes; policy provisional bloqueada |
| D79 resume con A expirada sólo mediante continuidad actual | PASS | enable→A expiry→pause→resume G+1, ambos motores |
| Misma closure/grants/perfil, A y receipts originales íntegros | PASS | comparación de testigos y pruebas D anteriores |
| Drift/provider stale/privacy/UNKNOWN/profile drift bloquean | PASS | recovery negativos, permanece PAUSED |
| Nueva G+1 no revive autoridad G anterior | PASS | guards D/F/Operations/Auth; matrices completas |
| Primera activación conserva TTL A | PASS | A expirada bloquea enable; default locks intactos |
| Sin migration80; anteriores sin cambios | PASS | AST/roundtrip/compatibilidad |
| Suite general y regresiones completas | PASS | 2142 PASS/2 skips PG previstos/0 FAIL/ERROR |
| PG/JS/migraciones/HTTP/seguridad/docs | PASS | matrices y gates descritos arriba |
| Sin acceso real/flags/push/main/GLIVE/H | PASS | alcance local; autoauditoría25 |

No se marca PASS de piloto real: evidencia real/prerequisitos profesionales y
autorización G-LIVE siguen pendientes. El PASS técnico no concede autoridad.

## Inventario final de archivos

- .github/workflows/ci.yml
- AGENTS.md
- docs/Decisiones.md
- docs/Estado-actual-main.md
- docs/Mapa-codigo.md
- docs/Registro-QA.md
- docs/Registro-cambios.md
- docs/Tareas-vivas.md
- docs/architecture/ADR-025-pilot-verification-recovery-continuity.md
- docs/architecture/FASE-1.10G-verify-cierre.md
- docs/architecture/FASE-1.10G-verify-evidencia.json
- docs/architecture/FASE-1.10G-verify-orden.md
- docs/architecture/FINANCIAL-PILOT-CHECKLIST-v1.md
- docs/architecture/FINANCIAL-PILOT-READINESS-v1.md
- docs/architecture/FINANCIAL-PILOT-RUNBOOK-v1.md
- docs/architecture/FINANCIAL-PILOT-VERIFICATION-v1.md
- docs/architecture/FINANCIAL-RECOVERY-READINESS-v1.md
- docs/architecture/README.md
- docs/areas/08-financial-core.md
- docs/project-state.json
- src/noesis/financial_activation/handoff.py
- src/noesis/financial_activation/readiness_verifier.py
- src/noesis/financial_activation/recovery_readiness.py
- src/noesis/financial_pilot/evidence.py
- src/noesis/financial_pilot/gate.py
- src/noesis/financial_pilot/verification_contracts.py
- src/noesis/financial_pilot/verifiers.py
- src/noesis/financial_providers/preflight.py
- src/noesis/financial_providers/validation.py
- tests/financial_pilot_verification_contract.py
- tests/financial_recovery_readiness_contract.py
- tests/postgres_financial_pilot_verification.py
- tests/test_financial_pilot_verification.py
- tests/test_financial_recovery_readiness.py

## Riesgos y límites

No hay evidencia real verificada, política aprobada real, pilot business/profile,
proveedores reales observados, main integrado, claves/colectores reales ni permiso
de activación. La capa requiere bootstrap confiable futuro, revisión profesional
y autorización separada para obtener observaciones reales. Claves externas nunca
proceden de JSON/chat/IA. La decisión describe un snapshot; una aprobación futura
debe revalidar fuentes actuales en una TX nueva. Los sellos son de instancia,
no un formato público persistido de autoridad. SOURCE drift/corruption no se
reparan; continuidad puede bloquear conservadoramente casos no verificables B.

Rollback: retirar el candidato local no publicado; ninguna migration que revertir.
No reutilizar runtime anterior para autorizar resumes79 nuevos sin continuidad.
Conservar F preflights/bindings/D receipts si se usa en fixtures; no reescribirlos.

## Autoauditoría — 25 respuestas peligrosas

1. Producción consultada: NO.
2. QA real consultada: NO.
3. Backup real leído: NO.
4. Provider I/O real: NO.
5. Policy legal aprobada por IA/código: NO.
6. Pilot business real seleccionado: NO.
7. Perfil real seleccionado sin humano: NO.
8. Hash/reference considerado proof por sí solo: NO.
9. Synthetic aceptado como REAL: NO.
10. Local/sandbox provider admitido para producción: NO.
11. PilotGate READY activa negocio: NO.
12. Guard D productivo retirado: NO.
13. Cinco flags reales cambiados: NO (mocks scoped sintéticos no son configuración real).
14. Legacy reabierto tras ever_enabled: NO.
15. History fence reactivado por recovery: NO.
16. Perfil cambiado dentro de recovery: NO.
17. Autoridad/grant G anterior habilitado en G+1: NO.
18. Provider evidence stale admitida: NO.
19. Privacidad provisional admitida: NO.
20. UNKNOWN admitido para readiness/resume: NO.
21. A original editada: NO.
22. Recibos D previos reescritos: NO.
23. Main mezclado: NO.
24. G-LIVE autorizado: NO.
25. H iniciada: NO.

Los datos/operators/receipts/approvals/attestations/drills de pruebas son
exclusivamente fixtures sintéticos, sin personas reales inventadas ni evidencia
de AEAT/Meta/email. El cluster PG nativo se crea sólo para estas pruebas.
