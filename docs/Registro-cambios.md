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

## 2026-08-06 18:30 — cartera profesional y papeles con contexto

- **Autor/agente:** Codex.
- **Objetivo:** conectar WhatsApp, documentos y gestoría en un flujo multiempresa
  seguro sin duplicar los portales existentes.
- **Áreas y archivos:** migraciones/DB, documentos, WhatsApp, routers y plantillas de
  gestoría, diseño, pruebas, guía de APIs y estado compartido.
- **Cambios de datos/migración:** esquema 39; cuentas de gestoría, relación explícita
  negocio-cuenta e invitaciones de un solo uso. No migra ni elimina enlaces antiguos.
- **Pruebas ejecutadas:** compileall, Ruff, 405/405, ciclo 0 → 39 → 0 → 39,
  Bandit, detección de secretos, auditoría de dependencias y QA visual comparada
  con el panel principal; detalle en `Registro-QA.md`.
- **Dependencias o validaciones externas:** añade pypdf puro Python para texto PDF
  digital. Meta, Stripe, correo, OAuth, OCR de escaneados y AEAT siguen sin prueba real.
- **Riesgo/punto probable de fallo:** despliegue de migración 39, entregabilidad de la
  invitación y PDFs escaneados sin texto. MFA/recuperación aún no forman parte del acceso.
- **Diagnóstico y rollback:** revisar `gestoria_accounts`, `gestoria_business_access`
  y `gestoria_invitations`; las rutas `/g/` permiten continuidad. El downgrade 39
  elimina solo las tablas nuevas y el revert del commit restaura UI/rutas.
- **Baja RGPD comprobada:** las relaciones nuevas usan borrado en cascada y el
  procedimiento elimina invitaciones y accesos antes del negocio, sin dejar filas
  huérfanas ni bloquear la baja.
- **Estado de publicación:** commit `1228da6` en `main`; CI general y humo PostgreSQL
  verdes. Railway validado por HTTP con release `1228da63f625`, `/health` correcto y
  `/ready` listo en esquema 39.

## 2026-08-06 12:45 — búsqueda documental publicada sobre PostgreSQL

- **Autor/agente:** Codex.
- **Objetivo:** cerrar la diferencia entre búsqueda construida y búsqueda publicada.
- **Áreas y archivos:** estado verificable, QA y bitácora.
- **Cambios de datos/migración:** ninguno; esquema 38.
- **Pruebas ejecutadas:** CI completo 400/400, ciclo de migraciones, humo PostgreSQL
  incluyendo `documents?q=factura`, `/health` con el release esperado y `/ready`
  listo en esquema 38.
- **Dependencias o validaciones externas:** Railway/PostgreSQL; sin credenciales.
- **Riesgo/punto probable de fallo:** falta una revisión visual autenticada del campo;
  backend, aislamiento y compatibilidad de motor sí están verificados.
- **Diagnóstico y rollback:** comparar release, revisar la ruta con sesión y consultar
  el log por `X-Request-ID` si la interfaz no recibe resultados.
- **Estado de publicación:** runtime validado; sincronización documental pendiente de
  commit/despliegue.

## 2026-08-06 12:35 — los papeles se encuentran sin conocer carpetas

- **Autor/agente:** Codex.
- **Objetivo:** cerrar la búsqueda documental del piloto reutilizando la bandeja y
  el repositorio existentes, sin otro índice, servicio ni pantalla.
- **Áreas y archivos:** repositorio/route de documentos, bandeja web, prueba de
  aislamiento, humo PostgreSQL, estado, tareas, mapa y QA.
- **Cambios de datos/migración:** ninguno; esquema 38.
- **Pruebas ejecutadas:** 18 pruebas focalizadas, Ruff y suite completa 400/400; la
  búsqueda se incorpora al humo PostgreSQL de CI.
- **Dependencias o validaciones externas:** ninguna credencial ni motor de búsqueda.
- **Riesgo/punto probable de fallo:** `LIKE` sobre texto OCR puede perder rendimiento
  si el volumen deja de ser el del piloto; antes de FTS se medirá latencia y tamaño.
- **Diagnóstico y rollback:** probar `/api/{negocio}/documents?q=factura`; si falla
  solo PostgreSQL, revisar `LOWER/COALESCE` del repositorio. Retirar `search` conserva
  íntegros documentos y metadatos.
- **Estado de publicación:** commit en `main`, CI/PostgreSQL verdes y release/esquema
  verificados en producción; revisión visual autenticada pendiente.

## 2026-08-06 12:20 — redirección canónica verificada en Railway

- **Autor/agente:** Codex.
- **Objetivo:** cerrar con evidencia HTTP la publicación del origen único.
- **Áreas y archivos:** estado verificable, QA, tareas y bitácora.
- **Cambios de datos/migración:** ninguno; esquema 38 permanece listo.
- **Pruebas ejecutadas:** CI verde completo; `www` 308 con `Location` exacta,
  seguimiento a 200, canónico directo 200, `/health` con el release esperado y
  `/ready` listo en esquema 38.
- **Dependencias o validaciones externas:** Railway y DNS públicos; sin credenciales.
- **Riesgo/punto probable de fallo:** un cambio futuro de dominio o `BASE_URL`;
  readiness y la prueba de middleware deben moverse juntos.
- **Diagnóstico y rollback:** repetir las tres peticiones HTTP descritas en la entrada
  anterior y comparar release/esquema.
- **Estado de publicación:** runtime validado; sincronización documental pendiente de
  commit y despliegue.

## 2026-08-06 12:10 — el alias público deja de duplicar la web

- **Autor/agente:** Codex.
- **Objetivo:** cerrar el doble origen observado en producción sin depender de una
  regla manual del proxy ni abrir hosts por comodín.
- **Áreas y archivos:** configuración de hosts, middleware web, prueba de seguridad,
  baseline de secretos, arquitectura, decisión, estado, tareas y QA.
- **Cambios de datos/migración:** ninguno; esquema 38.
- **Pruebas ejecutadas:** auditoría HTTPS de dominio, alta, legales y cabeceras; 3
  pruebas focalizadas, Ruff y suite completa 399/399.
- **Dependencias o validaciones externas:** ninguna credencial. La respuesta real de
  `www` debe repetirse cuando Railway sirva el commit.
- **Riesgo/punto probable de fallo:** orden de middlewares o `BASE_URL` no canónica;
  el redirect solo actúa si la base coincide con `CANONICAL_PUBLIC_HOST` y la prueba
  exige que conserve las cabeceras de seguridad.
- **Diagnóstico y rollback:** `curl -I https://www.bynoesis.com/precios?plan=pro`
  debe devolver 308 a `https://bynoesis.com/precios?plan=pro`; el canónico debe
  devolver 200. Revertir el middleware restaura el comportamiento anterior.
- **Estado de publicación:** commit en `main`, CI verde, desplegado y validado por
  HTTPS con release identificable y esquema 38.

## 2026-08-06 11:50 — producción confirma release y esquema 38

- **Autor/agente:** Codex.
- **Objetivo:** convertir la publicación del bloque documental en un hecho verificable,
  no en una inferencia a partir de GitHub.
- **Áreas y archivos:** fuente de verdad de proyecto, registro de QA y bitácora.
- **Cambios de datos/migración:** ninguno nuevo; Railway ya aplicó la migración 38.
- **Pruebas ejecutadas:** CI verde completo; humo PostgreSQL verde; petición HTTPS
  directa a `/health` con el release esperado y a `/ready` con HTTP 200/esquema 38.
- **Dependencias o validaciones externas:** despliegue automático de Railway; ninguna
  credencial de producto utilizada.
- **Riesgo/punto probable de fallo:** un despliegue documental posterior puede cambiar
  la huella sin cambiar el esquema; se vuelve a verificar tras publicar esta foto.
- **Diagnóstico y rollback:** comparar siempre `/health.release`, `/ready.release` y
  `/ready.schema`; si divergen de `main`/38, Railway está sirviendo otro candidato.
- **Estado de publicación:** runtime validado; sincronización documental pendiente de
  commit y despliegue.

## 2026-08-06 11:45 — una sola copia de cada documento por negocio

- **Autor/agente:** Codex.
- **Objetivo:** cerrar la duplicación exacta de fotos y PDF sin crear otro canal ni
  comparar información entre clientes.
- **Áreas y archivos:** migración 38; repositorio, servicio y router de documentos;
  humo PostgreSQL, baseline de secretos; pruebas y documentación viva de
  arquitectura, decisión y estado.
- **Cambios de datos/migración:** `documents.content_sha256` e índice parcial único
  `(business_id, content_sha256)`; los históricos se completan de forma perezosa.
- **Pruebas ejecutadas:** 17 pruebas focalizadas; ciclo 37 → 38 → 37 → 38; Ruff,
  Bandit y suite completa 398/398. Se leyó el log del CI anterior: solo fallaba porque
  tres números de línea del baseline habían quedado antiguos. El humo PostgreSQL y
  `detect-secrets-hook` se ejecutarán también en CI Linux.
- **Dependencias o validaciones externas:** ninguna credencial ni proveedor nuevo.
- **Riesgo/punto probable de fallo:** almacenamiento histórico ausente o una carrera
  de subida; el primer caso se ignora de forma segura y el segundo lo decide la base
  eliminando el fichero sobrante.
- **Diagnóstico y rollback:** un duplicado responde HTTP 409 con
  `document_duplicate` y el id existente. Para aislar una regresión, revisar
  `content_sha256`, el índice `uq_documents_business_content` y el fichero
  físico; la migración 38 se puede bajar a 37 sin alterar el resto del documento.
- **Estado de publicación:** commit en `main`, CI verde, desplegado y validado por
  `/health` y `/ready` con esquema 38.

## 2026-08-06 11:30 — el detector distingue la clave ficticia de la prueba

- **Autor/agente:** Codex.
- **Objetivo:** recuperar el CI de `main`; `detect-secrets` confundió el valor
  deliberadamente ficticio de la prueba de correo HTTPS con una credencial real.
- **Áreas y archivos:** `tests/test_readiness.py` y esta bitácora.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** el log del run identificó un único hallazgo en la línea de
  prueba; el humo PostgreSQL del mismo commit terminó correctamente.
- **Dependencias o validaciones externas:** ninguna.
- **Riesgo/punto probable de fallo:** ninguno en runtime; solo cambia una anotación
  reconocida por el escáner y el formato de esa prueba.
- **Diagnóstico y rollback:** si el paso «Detectar secrets nous» vuelve a fallar,
  revisar el hallazgo exacto; nunca ampliar la allowlist a archivos de producción.
- **Estado de publicación:** commit en `main`; la anotación evitó el falso positivo,
  pero el CI siguió rojo porque el baseline conservaba números de línea antiguos. La
  sincronización completa queda en la entrada inmediatamente anterior.

## 2026-08-06 11:15 — producción identificable y adaptadores alineados con Railway

- **Autor/agente:** Codex.
- **Objetivo:** cerrar desajustes encontrados al auditar el `main` estable sin tocar
  credenciales: demostrar qué release/esquema sirve producción, reconocer el correo
  HTTPS ya construido y aplicar en Stripe la política comercial «precio + IVA».
- **Áreas y archivos:** configuración, salud/readiness, adaptadores de email y
  billing, pruebas y documentos vivos de arquitectura, estado y conexión de APIs.
- **Cambios de datos/migración:** ninguno; esquema 37 sin tocar.
- **Pruebas ejecutadas:** baseline completo 392/392; después 17 pruebas focalizadas,
  Ruff, Bandit y `pip-audit`, todo correcto. Suite completa final 396/396 y fuente
  de verdad documental validada.
- **Dependencias o validaciones externas:** ninguna credencial utilizada. Quedan la
  entrega real de correo, Stripe test y el despliegue de Railway.
- **Riesgo/punto probable de fallo:** proveedor que no inyecte SHA deja release
  desconocido en producción; se resuelve con `NOESIS_RELEASE_ID`. Stripe Tax requiere
  configuración correcta de la cuenta aunque Checkout lo solicite.
- **Diagnóstico y rollback:** comparar `release` de `/health` y `schema` de `/ready`;
  revisar `email.available()` y el payload de `checkout/sessions`. El cambio no altera
  tablas ni datos y puede revertirse por adaptador.
- **Estado de publicación:** local sobre `main`, validado y pendiente de push.

## 2026-08-02 18:40 — el chat web emite el borrador, y la voz del plan Sin Límites deja de prometerse como activa

- **Autor/agente:** Claude.
- **Objetivo:** cerrar tres hallazgos de la auditoría del 2-ago-2026. (1) El mensaje que
  confirma un borrador sugiere «emitir factura N», pero esa orden solo la entendía
  WhatsApp: por la web el borrador se quedaba sin emitir siguiendo una instrucción del
  propio producto. (2) La página de precios y la de contratación anunciaban «100 minutos
  de llamadas incluidos» sin telefonía en el código. (3) Dos pruebas de copias llevaban
  en rojo permanente en macOS.
- **Áreas y archivos:** `src/noesis/nlu.py` (intent de emisión y limpieza del mensaje de
  error), `src/noesis/web/backups.py` (`_backup_dir` normalizada),
  `src/noesis/web/templates/site_precios.html` y `suscripcion.html` (voz dentro de la
  beta), `tests/test_backend.py` (dos pruebas nuevas), `docs/project-state.json`,
  `docs/Registro-QA.md`.
- **Cambios de datos/migración:** ninguno. Esquema 37 sin tocar.
- **Pruebas ejecutadas:** suite completa **392 pasan, 71 subtests, 0 fallos** (antes 382
  con 2 en rojo). Además, verificación manual con servidor real: crear borrador por
  chat web, rechazo por falta de NIF/domicilio, emisión efectiva `2026/0002`, y webhook
  de WhatsApp confirmando que sigue exigiendo SÍ antes de emitir.
- **Dependencias o validaciones externas:** ninguna nueva. No toca Stripe, Meta, SMTP ni
  AEAT.
- **Riesgo/punto probable de fallo:** el intent nuevo se evalúa **antes** que el de crear
  factura. Si alguien informa de que «factura a Fulano…» dejó de crear borradores, el
  sospechoso es esa expresión regular en `nlu.parse`; exige verbo de emisión y un
  identificador numérico al final, y hay prueba que cubre los dos casos.
- **Diagnóstico y rollback:** `python -m pytest tests/test_backend.py -k "issues_the_draft
  or without_jargon"` reproduce el comportamiento esperado. Para revertir solo la emisión
  por web basta con quitar el bloque `issue = re.search(...)` de `nlu.parse`; el resto de
  cambios es independiente.
- **Estado de publicación:** commit local, pendiente de revisión del fundador antes de
  subir a `main` (auto-despliega).

## 2026-07-28 15:00 — merge de main con origin/main (13 commits: solicitud de acceso, calendario, equipo)

- **Autor/agente:** Claude.
- **Objetivo:** `main` local llevaba 3 commits sin subir (fotos reales del equipo,
  restauración de bitácora, reconciliación previa) mientras `origin/main` llevaba
  13 sin bajar (alta por solicitud, migración 36 `access_requests`, calendario de
  contacto embebido, portada única). `git merge origin/main` dejó tres conflictos.
- **Áreas y archivos:**
  - `docs/Decisiones.md` y `docs/Registro-QA.md`: conflicto solo de posición —ambas
    ramas añadieron entradas distintas el mismo día. Se conservan **ambas** entradas
    completas, sin descartar ninguna.
  - `src/noesis/web/templates/site_equipo.html`: ambas ramas cambiaron la foto de
    los fundadores por vías distintas (`team-xavier-grino.jpg`/`team-miquel-colell.jpg`
    en local vs `equipo-xavier.jpg`/`equipo-miquel.jpg` en origin, con clases CSS
    distintas `founder-avatar` vs `founder-photo`). Se optó por la versión local por
    ser el commit más reciente y explícito ("Añade fotos reales de los fundadores").
    Se eliminaron `equipo-xavier.jpg`/`equipo-miquel.jpg` (sin otras referencias en
    el código) y la regla CSS `.founder-photo` ahora muerta en `app.css`.
- **Cambios de datos/migración:** ninguno propio; se incorpora la migración 36
  (`access_requests`) ya presente en origin.
- **Pruebas ejecutadas:** `pytest` completo (359 verdes / 361; los 2 fallos son el
  artefacto conocido de macOS `/private/var` vs `/var` en `test_backups.py`, sin
  relación), `ruff check src/` limpio, `scripts/check_project_truth.py` en verde.
- **Dependencias o validaciones externas:** ninguna nueva; no se llamó a
  cal.com/SMTP/Stripe reales en este merge.
- **Riesgo/punto probable de fallo:** si alguna referencia externa (CDN, caché de
  navegador) apuntaba a `equipo-xavier.jpg`/`equipo-miquel.jpg`, dará 404 tras el
  despliegue; no había referencias internas.
- **Diagnóstico y rollback:** commit de merge `dbfd1bd` sobre `main`; revertir con
  `git revert -m 1 dbfd1bd` si algo se rompe. El commit no reescribe historia.
- **Estado de publicación:** local / commit; pendiente subir a `origin/main`.

## 2026-07-27 — reconciliación del merge que mezcló dos arreglos del mismo bug

- **Autor/agente:** Claude.
- **Objetivo:** el commit local `9691898` (este agente) y el commit remoto
  `558d72b` (Codex) arreglaron, sin saberlo el uno del otro, el mismo
  `CheckViolation` de facturas emitidas partiendo del mismo commit base
  (`41fde55`). El merge manual `796e49e` los combinó quedándose con la versión
  local en `migrations.py` y descartando el refactor de Codex (helper
  `_drop_issued_invoice_integrity`, reutilizado en el downgrade), sin dejar marcas
  de conflicto. El resultado funcionaba pero dejaba un bloque duplicado inerte, y
  tres entradas completas de Codex sobre el incidente real de Railway (239ac7e,
  e5fd731, 923f1fc/e78e9e4) desaparecieron de este archivo y de `Registro-QA.md`
  (su entrada en `Mapa-codigo.md` y sus cambios en `project-state.json` sí
  sobrevivieron intactos).
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
- **Estado de publicación:** entrada restaurada tras perderse en el merge
  `796e49e`; el commit original ya está en `main` desde el 2026-07-27.

## 2026-07-27 12:05 — healthcheck Railway compatible con hosts cerrados

- **Autor/agente:** Codex.
- **Objetivo:** permitir que Railway valide `/ready` sin relajar la protección
  contra cabeceras `Host` falsificadas.
- **Áreas y archivos:** configuración de hosts, regresión de seguridad, arquitectura,
  estado verificable, QA y este registro.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** suite completa de **354 pruebas verdes en 223,9 s**; la
  nueva regresión acepta `healthcheck.railway.app`, rechaza `evil.example` y
  confirma que no se introduce `*`. Ruff, compilación, fuente de verdad y
  `git diff --check` verdes.
- **Dependencias o validaciones externas:** la documentación oficial de Railway
  identifica `healthcheck.railway.app` como el hostname exacto de sus comprobaciones.
- **Riesgo/punto probable de fallo:** una futura modificación del hostname por
  Railway o que `/ready` devuelva 503 por una migración realmente pendiente.
- **Diagnóstico y rollback:** ante un despliegue fallido, distinguir en los logs un
  rechazo de host de un `not_ready`; revertir este commit devuelve la lista anterior,
  pero volvería a bloquear el healthcheck actual de Railway.
- **Estado de publicación:** publicada en `main`; ambos jobs de CI verdes, despliegue
  Railway marcado `success` y comprobación real de `/health`, `/ready`, portada y
  login en 200. `/admin` redirige al login mientras Google OAuth siga sin configurar.
  **Producción recuperada.** (Entrada restaurada tras perderse en el merge
  `796e49e`.)

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
- **Estado de publicación:** entrada restaurada tras perderse en el merge
  `796e49e`; el commit original ya está en `main` desde el 2026-07-27.

## 2026-07-27 — fotos reales de los fundadores en /equipo

- **Autor/agente:** Claude.
- **Objetivo:** sustituir el monograma de iniciales de `/equipo` por las fotos
  reales que el fundador subió al repositorio.
- **Áreas y archivos:** `src/noesis/web/templates/site_equipo.html`;
  `src/noesis/web/static/team-xavier-grino.jpg` y
  `src/noesis/web/static/team-miquel-colell.jpg` (nuevos).
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** las fotos originales (600x600, 340KB/712KB) se
  redimensionan a 480x480 y se recomprimen a JPEG (24-30KB) con Pillow, quitando
  metadatos EXIF. Captura real con Playwright confirma que ambas cargan
  correctamente en el círculo de 72px. Suite completa: 352/354 verdes (mismos 2
  fallos de macOS, sin relación). `check_project_truth.py` verde.
- **Dependencias o validaciones externas:** ninguna.
- **Riesgo/punto probable de fallo:** ninguno; son archivos estáticos servidos
  desde `/static/`.
- **Diagnóstico y rollback:** revertir este commit devuelve el monograma de
  iniciales.
- **Estado de publicación:** commit en `main`; pendiente de push (ver más abajo).

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
