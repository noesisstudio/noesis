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

## 2026-07-27 11:54 — admin bloqueado sin caída global

- **Autor/agente:** Codex.
- **Objetivo:** conservar Google OAuth obligatorio para `/admin` sin impedir que
  arranque todo el SaaS cuando sus credenciales todavía no están configuradas.
- **Áreas y archivos:** startup web, regresión HTTP, arquitectura, decisión, estado,
  QA y este registro.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** la prueba específica inicia producción simulada, confirma
  `/health` y demuestra que una sesión admin por contraseña no accede a `/admin`.
  El CI completo se exige antes de validar el despliegue.
- **Dependencias o validaciones externas:** Google OAuth real sigue sin credenciales;
  Railway debe repetir el arranque y el healthcheck.
- **Riesgo/punto probable de fallo:** creer que el admin está disponible porque la
  app arranca. `noesis-doctor --strict` conserva Google como bloqueo y `/admin`
  requiere `auth_provider=google`.
- **Diagnóstico y rollback:** revisar el error operativo de startup y el diagnóstico
  Google. Revertir recuperaría la caída global, no una protección adicional del
  panel, por lo que no se recomienda.
- **Estado de publicación:** incluido en el commit asociado; pendiente de CI y
  despliegue Railway.

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
- **Estado de publicación:** incluido en el commit asociado sobre `main`; pendiente
  de CI, nuevo predeploy Railway y validación de la versión pública.

## 2026-07-27 11:24 — apertura comercial verificable y corrección P0

- **Autor/agente:** Codex.
- **Objetivo:** corregir las divergencias críticas detectadas en la auditoría:
  dependencia vulnerable, dominio dividido, textos legales incompletos, apertura
  pública sin puerta operativa y promesas de audio/OCR no ligadas a disponibilidad.
- **Áreas y archivos:** configuración y diagnóstico (`config.py`, `readiness.py`,
  `.env.example`); alta/Google y plantillas públicas/legales; OCR y lock de
  dependencias; pruebas y documentación viva. El diff exacto queda en el commit.
- **Cambios de datos/migración:** ninguno; el esquema permanece en 35. La versión
  de documentos legales se centraliza y cada nueva aceptación registra
  `2026-07-27`.
- **Pruebas ejecutadas:** 351 pruebas verdes en 255,8 s; 9 pruebas afectadas
  repetidas tras el último cambio; compilación, Ruff, Bandit, `pip-audit`,
  `uv lock --check`, escaneo de secretos de archivos cambiados/nuevos,
  `git diff --check` y migraciones `0 -> 35 -> 0 -> 35` verdes.
- **Dependencias o validaciones externas:** no se llamó a Railway, Meta, Google,
  Stripe, SMTP, Anthropic/Groq, S3, ClamAV ni AEAT. Falta revisión jurídica/fiscal
  y prueba visual/real; el navegador se evitó por el crash reportado.
- **Riesgo/punto probable de fallo:** desplegar sin las nuevas variables deja el
  alta pública cerrada de forma intencionada. Un dominio/callback incoherente o
  habilitar el alta antes de completar servicios produce bloqueos en
  `noesis-doctor --strict`, no cuentas parcialmente operativas.
- **Diagnóstico y rollback:** consultar el centro admin y `noesis-doctor --strict`
  sin exponer secretos. Ante regresión, revertir el commit de aplicación; no hay
  rollback de datos. Para reabrir, no se elimina la puerta: se completan variables
  y se activa `NOESIS_PUBLIC_SIGNUP_ENABLED=true` tras la aceptación P0.
- **Estado de publicación:** incluido en el commit asociado sobre `main`; pendiente
  de despliegue y validación real en Railway. Git publicado no equivale a producción
  verificada.

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
