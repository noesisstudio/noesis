# Backup V2 CRM74 — remote CI corrective gates

Orden humana de2026-10-13; sustituye el alcance local/no push del port únicamente
para este correctivo. Rama codex/recovery-backup-v2-crm74. Historia esperada:
base678bd3f → port01248c5 → un correctivo, sin amend/rebase/force.

[Port local histórico](RECOVERY-BACKUP-V2-CRM74-port.md),
[orden del port](RECOVERY-BACKUP-V2-CRM74-orden.md).

Attempt1: [CI38405811293](https://github.com/noesisstudio/noesis/actions/runs/38405811293),
head01248c5, BLOCKED. Tests i migracions falla sólo por dos Hex High Entropy String
públicos en docs/project-state.json: base SHA y lineage fingerprint. PG18 PASS
464 casos, grupo V2/identity70; no se hereda este verde para el nuevo SHA.

## Contrato del correctivo

.secrets.baseline admite exclusivamente dos nuevas entradas generadas por
detect-secrets1.5.0: mismo filename, detector y huella exacta; is_verified=true e
is_secret=false. Todas las entradas/configuración anteriores permanecen iguales.
El scanner no cambia, no se acepta el árbol completo ni una tercera excepción.
Control negativo temporal sin commit y retirada obligatoria.

scripts/check_doc_links.py conserva el audit inline del delta (incluye imágenes):
original550 enlaces/0 rotos. Sin red; esquemas explícitos y anchors solos se ignoran;
fragmentos sobre archivo se eliminan antes de comprobarlo. Destino local ausente,
ruta inválida o fuera del repositorio falla. Cinco tests pequeños cubren el contrato.
CI ejecuta links y git diff --check BASE HEAD antes de los tests generales.
PR: base.sha; push: before válido; dispatch/fallback: merge-base HEAD origin/main.
No gate sobre working tree limpio como sustituto del rango.

## Validación y publicación

Antes del commit: scanner completo, control negativo de secreto, checker y fixture
roto, Ruff script/test, cinco tests, documentation truth y diff del delta/rango.
No nueva suite local1925: ningún cambio de producto. CI general y PG18 nuevos
completos en el mismo SHA; sin resultados heredados ni retests como cierre.
El resultado final se entrega con run/head/jobs/logs en el informe externo de esta
operación. Este registro versionado no anticipa verde ni inventa un SHA propio.
Sólo se autoriza un commit; no crear un segundo commit documental para el receipt.

Main remoto debe seguir base678bd3f antes del push; de lo contrario STOP
REMOTE_MAIN_DRIFT. Después compareahead2/behind0, rama remota exacta y padre012.
Estado al registrar: CI final PENDIENTE. El port y su cierre original son historia.

Alert sharp HIGH de branding/package-lock.json permanece abierta y sin cambios:
SEPARATE SECURITY DEBT / PRE-PRODUCTION TRIAGE REQUIRED. Fuera del runtime del
port; no se resuelve ni se oculta en este correctivo.

Sin src/noesis, migration75, A75–F80, CRM, scheduler, Railpack/Mise, bridge,
producción/Railway/QA/backups reales/providers/business15, flags, merge/main,
deploy, G-LIVE ni H. Fixtures de validación sólo sintéticos y sin autoridad REAL.
