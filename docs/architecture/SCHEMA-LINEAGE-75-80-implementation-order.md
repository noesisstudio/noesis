# Orden posterior — diseño de secuencia, no autorización de ejecución

[Orden humana vigente](SCHEMA-LINEAGE-75-80-orden.md), [ADR](ADR-SCHEMA-LINEAGE-001-crm74-financial75-80.md),
[contrato](SCHEMA-LINEAGE-75-80-contract.md), [matriz](SCHEMA-LINEAGE-75-80-test-matrix.md).
Cada gate exige alcance/permiso posterior. Sólo esta documentación está autorizada.

## Secuencia propuesta y dependencias

| Paso | Unidad posterior | Gate para pasar |
|---:|---|---|
| 1 | Aprobar diseño lineage | Review humano de ADR/contratos/hashes/matriz; DESIGN PASS no es aprobación humana |
| 2 | Port BackupV2 desde f272 a **nueva rama** desde main678 | Port funcional, no copiar base08; preservar original/historia V2; identidad/manifest por etapas implementadas hasta74 |
| 3 | Publicar sólo rama port, sin merge/main/deploy | Autorización específica de push; commits correctivos append-only |
| 4 | CI remota V2 port | Completa fresca, CRM74/Node/PG18/V1/V2/locks si ya implementados; revisión de código posterior |
| 5 | Implementar canonical75–80 sobre main actual + V2 revisada | Nueva rama/candidato, baseline reconcile contra main actual; detector/locks/CI guard primero, después A–F/G |
| 6 | Full local CI | Matriz completa actual del SHA final, no agregación |
| 7 | Remote CI canonical75–80 | Publicación autorizada y ejecución fresca completa; sin deploy |
| 8 | Implementar RecoveryBridge74↔80 | Unidad separada, detector compartido, compatibilidad runtime ≠ propiedad del migrador, no producción |
| 9 | Validar bridge74 | CRM74/supresiones/legacy rutas, startup sin DDL, roles/flags/locks compatibles |
| 10 | Validar bridge80 | GuardD/E/F, conservación, pause/recovery/UNKNOWN, sin fallback legacy |
| 11 | Backup/restore drill real aislado | Permiso específico de lectura backup y restore aislado; origen74/target80 exactos, ACL, outbound denied, E replay y snapshot |
| 12 | Nueva integration candidate | main actual + canonical75–80 + port V2 + bridge/recovery, originales870/822/f272 como referencias históricas |
| 13 | Full remote CI integración | SHA final exacto y review humano nuevo MAIN_INTEGRATION; sin herencia de CI vieja |
| 14 | PREDEPLOY GO/NO-GO | Releases bridge74/80, backup/drill actualizado, autoridad, roles, locks, replicas, rollback y bloqueos legales |
| 15 | Explicit deploy authorization | Dos acciones distintas: bridge sin migrar y posterior rollout80; no G-LIVE implícito |
| 16 | Bridge deploy | CanonicalCRM74; preDeploy no aplica75–80; retirar migradores viejos y arranques con DDL |
| 17 | Verify bridge live74 | Permiso real limitado; todas las réplicas/workers/scheduler compatibles, identidad74+objetos, flags OFF |
| 18 | Financial80 rollout | Migrador propietario80 con lock y plan autorizado; backup reciente74; verificar canonical80; guard real OFF |
| 19 | Rollback a bridge si es necesario | Mismo esquema80 preservado; no se vuelve a08 ni se baja a74 automáticamente |
| 20 | Business15 EMPTY formal | Permiso tenant exacto para hash/lecturas sensibles y eventuales writes previos separados; nunca este diseño |
| 21 | Human/legal blockers | Cierre real profesional policy E, roles/cuidados/orígenes evidencias autorizados; no inventar personas |
| 22 | G-LIVE autorización separada | Sólo evidencias reales vigentes y permiso durable exacto; revisión del guard aparte |
| 23 | H auditoría final | Orden específica posterior, no asumida por publicar/READY |

## Ajustes de seguridad respecto al orden nominal

- **Roles, revisión humana y plan legal se avanzan documentalmente antes del14.**
  Si el deploy sólo instala infraestructura con todo OFF y sin serving financiero,
  no se finge policy approved. Evaluación profesional de retención/privacidad y
  permisos mínimos de backups deben satisfacer sus propios gates antes de usar
  copias reales. Blockers de G se cierran antes de cualquier G-LIVE, no al activarlo.
- **Paso11 se repite después del13 y antes de15/18 si cambia el SHA del candidato,
  imagen/toolchain, objeto/perfil, fuente o reglas de replay.** Un drill de un
  candidato preliminar no acredita el release final. La copia de rollback se
  actualiza antes de18 con autorización independiente; no migrar con snapshot stale.
- En18 verificar identidad80/objetos/replicas/no-ops se ejecuta antes de anunciar
  readiness/serving. La autorización de deploy no autoriza EMPTY15 ni providers.
- Paso19 es contingencia, no requisito de hacer un rollback real de prueba en
  producción; se ensaya con fixtures/clone autorizado antes de GO. Tras cambios
  durables o efectos externos no se restaura un backup antiguo sin protocolo aparte.
- Si main futuro deja de ser678 antes de integrar, detener por baseline DRIFT,
  auditar nueva migration latest y pedir alcance de reconciliación. No renumerar
  silenciosamente otra vez ni rebasear historia auditada.

## Port V2: instrucciones de integración futura

Rama futura base exacta678; preservar f272 y padre08 en su rama original. Copiar sólo
la funcionalidad revisada mediante commits nuevos (autoría/procedencia documentadas),
sin reset/readopt de todo el árbol ni rebase del original. No se ejecuta aquí.

Conservar CRM74/esquema.py, código CRM, package-data actual pyproject, Node
local_dates, scheduler de CRM y router/layout admin actual. V2 añade módulos nativos,
tools/inventory, descarga ZIP set, toolchain mise/railpack y runner PG18. CI combina
el paso Node actual con el runner V2 y, después, **todas** las matrices A–G.

Intersección estática anterior:13 archivos; hunks CI/admin separados; conflictos
de docs/JSON requieren reconciliación factual, no sustituir schema74 por73.
V1 conserva su guard catalog exacto; V2 manifest identity2 en fuentes reconocidas.
El port inicial no importa callbacks Financial80 todavía inexistentes. Tras
paso5, amplía catálogo y perfiles por append-only con pruebas de lineage/restore.

## RecoveryBridge y permisos

Matriz exacta:canonical74 y canonical80 permiten compatibilidad declarada;
canonical75..79, legacyFinancial74..79, unknown y future81 bloquean. Migración
owner80 sólo en proceso/rol autorizado separado. Un bridge que arranca80 no declara
propiedad de80 ni ejecuta DDL por MAX. Preserva datos/guards ever_enabled; flags OFF
no autoriza un fallback. Manual downgrade productivo no pertenece a esta secuencia.

No permisos implícitos de lectura real de DB, registro global E, custodias, borrar
archivos/copies, revocación de proveedores, purga o checks externos. Cada permiso define
entorno, SHA/catalog/lineage, tablas/scope/acciones, duración y rollback concreto.
No secreto al chat ni dump al Git. Business15/piloto se conserva; selección humana
Profile A v1 confirmada no resuelve secondary/legal/custodian/engineering pendientes.

## Bloqueos actuales y próxima unidad propuesta

RecoveryBridge BLOCKED hasta implementación/revalidación; port V2 sin publicar;
canonical75–80 sin implementar; MAIN_INTEGRATION humana pendiente; policy E
PROVISIONAL/PENDIENTE DE APROBACIÓN PROFESIONAL y PRIVACY_NOT_READY; guard D/G
REAL, orígenes/colectores y cuatro roles pendientes. Cinco flags OFF.

Próxima unidad, **sólo después de aprobación**: BACKUP-V2-PORT-CRM74 local en nueva
rama desde678, detector/manifest de identidad74 sin callbacks75–80, pruebas sintéticas
completas; sin push/main/deploy/producción/QA real/providers/rollout Financial canónico.
Publicación y CI remota son autorizaciones posteriores3/4. No iniciar aquí.
