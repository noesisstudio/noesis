# Registro de cambios

Bitácora cronológica obligatoria de modificaciones del repositorio. Su objetivo es
permitir responder rápido a cuatro preguntas cuando algo falla: **qué cambió, qué
área puede haberlo causado, cómo se verificó y cómo se puede aislar o revertir**.

No sustituye `Registro-QA.md` (evidencia detallada), `Estado-actual-main.md`
(fotografía del producto) ni Git (diff exacto). Los conecta.

## Plantilla para toda modificación

```markdown
## AAAA-MM-DD HH:MM — título corto

- Autor/agente:
- Objetivo:
- Áreas y archivos:
- Cambios de datos/migración:
- Pruebas ejecutadas:
- Dependencias o validaciones externas:
- Riesgo/punto probable de fallo:
- Diagnóstico y rollback:
- Estado de publicación: local / commit / main / desplegado / validado real
```

## 2026-07-27 — reconciliación del merge que mezcló dos arreglos del mismo bug

- **Autor/agente:** Claude.
- **Objetivo:** el commit local `9691898` (este agente) y el commit remoto
  `558d72b` (Codex) arreglaron, sin saberlo el uno del otro, el mismo
  `CheckViolation` de facturas emitidas partiendo del mismo commit base
  (`41fde55`). El merge manual `796e49e` los combinó quedándose con la versión
  local en `migrations.py` y descartando el refactor de Codex (helper
  `_drop_issued_invoice_integrity`, reutilizado en el downgrade), sin dejar marcas
  de conflicto. El resultado funcionaba pero dejaba un bloque duplicado inerte, y
  las entradas de Codex en este archivo y en `Registro-QA.md` desaparecieron del
  todo (su entrada en `Mapa-codigo.md` sí sobrevivió).
- **Áreas y archivos:** `src/noesis/migrations.py` (recupera el helper y quita el
  bloque duplicado); `docs/Registro-QA.md` y este registro (restauran la entrada
  de Codex perdida, con su autoría y fecha original).
- **Cambios de datos/migración:** ninguno nuevo; mismo comportamiento verificado,
  solo se elimina redundancia.
- **Pruebas ejecutadas:** suite completa 352/354 verdes (2 fallos de siempre,
  artefacto macOS ajenos a esto); `ruff check` verde en `migrations.py`.
- **Dependencias o validaciones externas:** ninguna.
- **Riesgo/punto probable de fallo:** si en el futuro dos agentes vuelven a tocar
  la misma función en paralelo sobre `main`, un merge manual puede volver a
  descartar silenciosamente uno de los dos lados sin marcar conflicto. Vale la pena
  recordar la regla de "un único escritor activo por archivo" de `AGENTS.md`.
- **Diagnóstico y rollback:** revertir este commit reintroduce el bloque muerto
  (inofensivo pero confuso) y deja sin restaurar la bitácora de Codex.
- **Estado de publicación:** commit en `main`.

## 2026-07-27 11:44 — migración profesional compatible con facturas emitidas

- **Autor/agente:** Codex.
- **Objetivo:** resolver el `CheckViolation` real de Railway al aplicar el salto
  32 → 33 sobre una factura ya emitida, sin rebajar su inmutabilidad posterior.
- **Áreas y archivos:** helper y backfill en `migrations.py`; regresión unitaria en
  `test_backend.py`; nuevo humo `postgres_migration_smoke.py`; secuencia PostgreSQL
  de GitHub Actions; estado, mapa, QA y este registro.
- **Cambios de datos/migración:** no cambia la versión (35) ni añade columnas. La
  migración 33 asigna la serie y línea históricas con el trigger de cabecera
  suspendido solo durante el backfill y restaurado inmediatamente.
- **Pruebas ejecutadas:** 352 pruebas verdes en 235,4 s; regresión específica
  SQLite, compilación, Ruff, Bandit, `pip-audit`, YAML, fuente de verdad y
  `git diff --check` verdes. El nuevo escenario PostgreSQL se completa en CI antes
  de considerar publicable el arreglo.
- **Dependencias o validaciones externas:** el error procede del predeploy real de
  Railway; no se accedió ni modificó manualmente la base de producción.
- **Riesgo/punto probable de fallo:** una excepción durante el backfill. PostgreSQL
  revierte toda la transacción, incluido el `DROP TRIGGER`; la prueba confirma que
  el guardián vuelve a impedir cambios al terminar.
- **Diagnóstico y rollback:** el síntoma original es
  `psycopg.errors.CheckViolation: una factura emitida no puede alterarse` en el
  `UPDATE invoices SET series_id`. Si reaparece, no editar la factura ni borrar el
  trigger manualmente: conservar el despliegue anterior y revisar el job de
  migración histórica. Revertir el commit no requiere downgrade de esquema.
- **Estado de publicación:** entrada restaurada tras perderse en el merge
  `796e49e`; el commit original ya está en `main` desde el 2026-07-27.

## 2026-07-27 — equipo real en la web pública y botón de agendar reunión

- **Autor/agente:** Claude.
- **Objetivo:** a petición del fundador, sustituir el enfoque deliberadamente
  anónimo de `/equipo` por perfiles reales de los dos cofundadores, y añadir un
  botón de agendar reunión (Cal.com) en `/equipo` y `/preguntas` en lugar del
  calendario embebido que no habría funcionado por la CSP del sitio.
- **Áreas y archivos:** `src/noesis/web/templates/site_equipo.html`,
  `src/noesis/web/templates/site_preguntas.html`, `src/noesis/web/static/app.css`.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** capturas reales con Playwright/Chromium en escritorio
  (1400px) y móvil (390px) de `/equipo` y `/preguntas`; verificado que
  `https://cal.com/bynoesis` responde 200 con título "ByNoesis | Cal.com" antes de
  enlazarlo. Suite completa: 345/347 (los 2 fallos son el artefacto de macOS ya
  conocido en `test_backups.py`, no relacionado). `test_backend.py` cubre `/equipo`
  y `/preguntas` con 200 y sigue en verde.
- **Dependencias o validaciones externas:** el enlace usa Cal.com externo mediante
  `<a target="_blank" rel="noopener">` normal, no iframe, para no chocar con
  `frame-src 'none'` de la CSP.
- **Riesgo/punto probable de fallo:** las bios de los fundadores y el nombre de
  usuario de Cal.com dependen de datos dados directamente por el fundador en el
  chat; las fotos son un monograma con iniciales a falta de fotos reales.
- **Diagnóstico y rollback:** revertir este commit recupera la versión anónima
  anterior de `/equipo` sin nombres ni botón de Cal.com.
- **Estado de publicación:** commit en `main`.

## 2026-07-27 — corrige migración que rompía bases con facturas ya emitidas

- **Autor/agente:** Claude.
- **Objetivo:** al levantar el entorno local para una auditoría funcional completa,
  la migración a esquema 35 fallaba con `sqlite3.IntegrityError: una factura emitida
  no puede alterarse` en cuanto la base tenía al menos una factura no borrador.
  Cualquier instalación real (no solo la demo vacía) se habría quedado sin arrancar
  al aplicar `_upgrade_professional_invoicing`.
- **Áreas y archivos:** `src/noesis/migrations.py`
  (`_upgrade_professional_invoicing`).
- **Cambios de datos/migración:** el disparador de inmutabilidad de facturas
  emitidas (instalado por `_upgrade_invoice_legal_integrity`, migración anterior)
  bloqueaba el propio `UPDATE ... SET series_id=... WHERE series_id IS NULL` de esta
  migración, porque `series_id` está en la lista de campos protegidos y toda factura
  previa a esta migración lo tiene `NULL`. Se desactiva el disparador solo durante
  ese relleno retroactivo de metadatos y se reinstala (`_install_issued_invoice_integrity`)
  inmediatamente después, en el mismo dialecto SQLite/Postgres.
- **Pruebas ejecutadas:** reproducido con una base SQLite real con facturas emitidas
  (`enviada`, `cobrada`) generadas en sesiones anteriores; tras el arreglo la
  migración llega a la versión 35, el `series_id` queda relleno en las facturas
  emitidas y una mutación directa posterior sigue bloqueada por el disparador
  reinstalado. Suite completa: **345/347** (los 2 fallos restantes son un artefacto
  de rutas `/private/var` vs `/var` de macOS en `test_backups.py`, no relacionados
  con este cambio ni nuevos).
- **Dependencias o validaciones externas:** ninguna.
- **Riesgo/punto probable de fallo:** si en el futuro se añade un campo a
  `_IMMUTABLE_INVOICE_FIELDS` que también necesite un backfill retroactivo en una
  migración posterior, hay que repetir este mismo patrón (desactivar el disparador,
  escribir, reinstalar) o la migración volverá a romperse igual.
- **Diagnóstico y rollback:** revertir este commit reintroduce el fallo en cualquier
  base con facturas emitidas antes de llegar a schema 35 (SQLite y Postgres). No hay
  cambio de esquema nuevo, solo de la secuencia de la migración existente.
- **Estado de publicación:** commit en `main`.

## 2026-07-21 — política segura de actualización de dependencias

- **Autor/agente:** Codex.
- **Objetivo:** mantener la vigilancia automática de dependencias sin volver a
  mezclar cambios heterogéneos ni romper el lockfile que exige el CI.
- **Áreas y archivos:** `.github/dependabot.yml` y este registro.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** validación sintáctica YAML, `uv sync --locked`, fuente de
  verdad del proyecto, Ruff, `pip-audit`, detector de secretos y `git diff --check`
  verdes. La suite completa local superó el límite de 3 minutos sin mostrar fallo;
  los dos jobs de CI son obligatorios antes de fusionar.
- **Dependencias o validaciones externas:** configuración contrastada con la
  referencia oficial de GitHub Dependabot. Se cambia el ecosistema de `pip` a `uv`
  para que el bot actualice `pyproject.toml` y `uv.lock` de forma coherente.
- **Riesgo/punto probable de fallo:** GitHub debe reconocer el ecosistema `uv` y
  aplicar la nueva política al siguiente ciclo. Las subidas mayores dejan de ser
  rutinarias y requieren un PR manual revisado expresamente.
- **Diagnóstico y rollback:** el PR #53 agrupó 21 cambios mediante `patterns: ["*"]`
  y falló antes de los tests porque no actualizó `uv.lock`; se cerró explicando la
  causa. Revertir este cambio recuperaría el agrupado inseguro y no es recomendable.
- **Estado de publicación:** candidato en `codex/dependabot-policy`; no estará en
  `main` ni activo para Dependabot hasta superar CI y fusionarse.

## 2026-07-21 — operaciones de seguridad y responsable CISO interno

- **Autor/agente:** Codex.
- **Objetivo:** subir la seguridad verificable del piloto sin dar autonomía a una
  IA ni enviar documentos a nuevos terceros: evidencia inmutable, restauración
  repetible, antivirus privado y acceso admin fuerte por defecto.
- **Áreas y archivos:** migración/DB, `security_center.py`, documentos/ClamAV,
  backups/scheduler/CLI, admin, readiness, configuración, pruebas y documentación
  viva. El diff del commit es el inventario exacto.
- **Cambios de datos/migración:** esquema 35 con `security_events`; eventos globales
  append-only, cadena SHA-256, severidad, área, IDs internos opcionales, `request_id`
  y metadatos escalares filtrados. Triggers impiden UPDATE/DELETE en SQLite/Postgres.
- **Pruebas ejecutadas:** 347 pruebas verdes tras añadir 8 regresiones; ciclo
  `0 -> 35 -> 0 -> 35`, Ruff, Bandit, detector de secretos, `pip-audit`, verdad de
  proyecto, diff y smoke HTTP admin verdes. PostgreSQL 16 queda para CI del PR.
- **Dependencias o validaciones externas:** no se añade paquete Python. ClamAV es un
  daemon privado opcional y no está desplegado desde este cambio; Google OAuth, S3
  y PostgreSQL de producción requieren variables y validación real.
- **Riesgo/punto probable de fallo:** despliegue sin migración 35, producción sin
  credenciales Google (fallará al arrancar por diseño), host ClamAV inaccesible en
  modo obligatorio o artefacto de backup externo no descargable.
- **Diagnóstico y rollback:** correlacionar por `X-Request-ID`, revisar el centro
  CISO y ejecutar `noesis-restore-check`. Se puede revertir la aplicación; bajar la
  migración elimina solo la bitácora y no debe hacerse en producción sin preservar
  su evidencia y una copia.
- **Estado de publicación:** PR #54 fusionado en `main` el 2026-07-21, con suite
  general y PostgreSQL 16 verdes. Despliegue, migración 35 y validación del dominio
  real continúan siendo pasos independientes pendientes de comprobar.

## 2026-07-21 — hardening de seguridad y operación previa al piloto

- **Autor/agente:** Codex.
- **Objetivo:** reducir el riesgo de fuga, abuso de autenticación, carga maliciosa,
  agotamiento de conexiones, exposición en logs y cadena de suministro sin añadir
  servicios externos obligatorios al MVP.
- **Áreas y archivos:** CI/Dependabot/lock y baseline de secretos; configuración,
  servidor/sesiones/admin, pool de base de datos, documentos, WhatsApp, XML AEAT,
  backups, despliegue, pruebas y `Seguridad-operativa.md`. El diff del commit es el
  inventario exacto.
- **Cambios de datos/migración:** esquema 34 con `auth_attempts`: eventos mínimos de
  intentos, caducables y con clave HMAC; no guarda IP ni email en claro.
- **Pruebas ejecutadas:** 339 pruebas verdes; ciclo `0 -> 34 -> 0 -> 34`; Ruff,
  Bandit, `pip-audit` y detector de secretos verdes. Dependencias nuevas bloqueadas
  en `uv.lock` y sincronizadas con `requirements.txt`.
- **Dependencias o validaciones externas:** habilitadas alertas de vulnerabilidades
  y correcciones de seguridad de Dependabot. El humo PostgreSQL 16 del PR es verde;
  quedan pendientes producción real, pentest, RGPD/fiscalidad, restauración y
  credenciales externas.
- **Riesgo/punto probable de fallo:** configuración incorrecta de hosts/OAuth en
  producción, pool insuficiente para la concurrencia real, proveedores S3 sin
  soporte de la cabecera SSE o dominio de medios Meta nuevo no permitido.
- **Diagnóstico y rollback:** usar `X-Request-ID`, `/ready`, jobs CI y contadores de
  colas sin consultar contenido personal. Revertir el commit de aplicación si hay
  regresión; la migración 34 puede bajar sin tocar datos de negocio, pero no debe
  bajarse en producción sin copia y ventana controlada.
- **Estado de publicación:** PR #49 en rama `codex/security-hardening`, verificado
  localmente y con los dos jobs CI verdes; todavía no fusionado ni desplegado.
- **Seguimiento CI:** el primer run del PR #49 confirmó la migración 34 en
  PostgreSQL y detectó una imagen demo falsa y constantes de prueba no reconocidas
  por la baseline en Linux. Se sustituyó el payload demo por JPEG real y se usaron
  constantes reutilizables con allowlist revisada, sin excluir archivos ni
  desactivar detectores. El humo PostgreSQL 16 posterior quedó verde.

## 2026-07-20 — consolidación del MVP, facturación profesional e integración total

- **Autor/agente:** Codex, continuando trabajo previo de Codex/Fable revisado en el
  mismo árbol.
- **Objetivo:** consolidar el MVP nativo sin Holded; profesionalizar alta, precios,
  integraciones, facturación, Veri*Factu preparado y el recorrido WhatsApp →
  cliente/trabajo → borrador → confirmación → número/PDF → entrega → cobro,
  impuestos, KPIs y gestoría.
- **Áreas y archivos:** configuración y adaptadores; `db.py`, `migrations.py`,
  `nlu.py`, `tools.py`, `agent.py`; routers de cuenta, facturación y portal;
  `whatsapp.py`, `scheduler.py`, PDF, plantillas/CSS; smoke PostgreSQL, pruebas y
  documentación viva. El diff exacto queda en el commit asociado.
- **Cambios de datos/migración:** esquema 33. Añade series, líneas de factura,
  recurrencias idempotentes, metadatos de entrega, registros/outbox de anulación y
  triggers que congelan cabecera y líneas emitidas. Upgrade/downgrade cubiertos.
- **Pruebas ejecutadas:** 325 pruebas y 52 subtests verdes; compilación Python,
  JavaScript de Facturas, `git diff --check`, `check_project_truth.py`, flujo HTTP
  autenticado y XML de alta/anulación validado contra XSD oficiales. El smoke real
  PostgreSQL 16 corresponde al CI del PR.
- **Dependencias o validaciones externas:** faltan credenciales/prueba real de Meta,
  plantilla `noesis_factura_lista`, SMTP, Stripe, Google OAuth, IA privada y
  certificado/entorno AEAT. Veri*Factu permanece desactivado por negocio hasta
  validación; para autónomos la obligación SIF vigente comienza el 01-07-2027.
- **Riesgo/punto probable de fallo:** despliegue sin migración 33; datos fiscales
  incompletos al emitir F1; plantilla Meta no aprobada; SMTP sin credenciales;
  certificado o respuesta AEAT; diferencias SQLite/PostgreSQL en triggers/FK.
- **Diagnóstico y rollback:** revisar `/ready`, panel admin y outboxes; ejecutar el
  smoke PostgreSQL y el flujo de factura del `Registro-QA`. Revertir el commit de
  aplicación si hay regresión; no bajar esquema ni borrar registros fiscales en
  producción sin copia, auditoría y plan específico.
- **Estado de publicación:** candidato local verificado; PR de consolidación
  solicitado, todavía no desplegado al escribir esta entrada.

## 2026-07-20 17:46 — compatibilidad PostgreSQL de la migración 28

- **Autor/agente:** Codex.
- **Objetivo:** corregir el fallo del guardián PostgreSQL detectado en el PR #48.
- **Áreas y archivos:** `src/noesis/migrations.py`, `src/noesis/db.py`,
  `src/noesis/demo.py`, `tests/test_platform.py`, `tests/test_backend.py`.
- **Cambios de datos/migración:** no cambia el esquema ni los datos resultantes;
  parametriza el patrón `R%` usado al clasificar facturas rectificativas durante la
  migración 28 y normaliza los triggers PostgreSQL con SQLSTATE de integridad
  `23514` para que SQLite y psycopg expongan el mismo tipo de fallo.
- **Pruebas ejecutadas:** prueba unitaria específica de migraciones y repetición del
  CI PostgreSQL del PR.
- **Dependencias o validaciones externas:** GitHub Actions con PostgreSQL 16.
- **Riesgo/punto probable de fallo:** únicamente la traducción de placeholders entre
  SQLite y psycopg.
- **Diagnóstico y rollback:** el error original era `psycopg.ProgrammingError` por un
  `%` literal interpretado como placeholder. El segundo error era una mutación de
  fechas posterior a la emisión en los datos demo; ahora la fecha histórica se fija
  dentro de la misma emisión y se mantiene la protección inmutable. El tercero era
  la clasificación `P0001` de los triggers PostgreSQL; ahora devuelven `23514`.
  Revertir estos commits recuperaría los errores; no requiere rollback de base de
  datos.
- **Estado de publicación:** corrección preparada en el PR #48, pendiente de CI al
  escribir esta entrada.

## 2026-07-20 18:01 — publicación de la consolidación en `main`

- **Autor/agente:** Codex.
- **Objetivo:** publicar el conjunto consolidado y dejar el entorno activo listo
  para trabajar directamente sobre `main`, según la decisión del fundador.
- **Áreas y archivos:** PR #48 y los commits `b1e4541`, `46279ad`, `0535b14` y
  `522475d`; configuración operativa documentada en `AGENTS.md` y
  `docs/Metodo-operativo-Fable.md`.
- **Cambios de datos/migración:** esquema objetivo 33; sin cambios adicionales de
  datos durante la fusión.
- **Pruebas ejecutadas:** CI completo verde en GitHub Actions: suite general, ciclo
  completo de migraciones y humo funcional con PostgreSQL 16.
- **Dependencias o validaciones externas:** no se ha validado todavía el despliegue
  de producción ni las credenciales reales de Meta, SMTP, Stripe, Google o AEAT.
- **Riesgo/punto probable de fallo:** despliegue que no aplique la migración 33 o
  variables externas incompletas; la publicación en Git no equivale por sí sola a
  despliegue validado.
- **Diagnóstico y rollback:** `main` quedó en `63c95d8` tras fusionar el PR #48. El
  CI detectó y se corrigieron un wildcard SQL no parametrizado, una mutación tardía
  de fechas demo y un SQLSTATE PostgreSQL mal clasificado. Ante una regresión,
  revisar primero esos commits y el run CI `29757337851`.
- **Estado de publicación:** PR #48 fusionado en `main`; candidato de repositorio
  validado por CI, producción todavía no verificada.
