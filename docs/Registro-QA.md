# Registro de QA

## 2026-07-27 — portada: un día real en vez de listas de funciones

### Qué se probó y con qué resultado

- **Entradilla del hero**: pasa a nombrar WhatsApp lo primero, cumpliendo la ley 2 de
  `PRODUCT_PRINCIPLES` («primero WhatsApp, después app»). El titular **no se toca**: es
  la frase canónica del producto, fijada como base de la landing.
- **Sección «cada momento de tu día» sustituida** por «Así se ve un día con Noesis»: una
  conversación real de WhatsApp con las cuatro horas del día perfecto descrito en
  `WhatsApp-Cerebro` §10. Elimina de paso la redundancia con «Cómo funciona», que contaba
  el mismo ciclo con otras palabras.
- **Sección «Historias reales, cuando estén verificadas» sustituida**: anunciaba en un
  sitio privilegiado que no hay testimonios. Ahora presenta a los dos fundadores con sus
  caras y explica el acompañamiento, que es la confianza que sí se puede ofrecer hoy.
- **CSS muerto retirado**: los estilos de la sección eliminada, incluidos sus selectores
  dentro de las reglas responsive compartidas, comprobando antes que ninguna plantilla
  los usara. Hoja de estilos 806 bytes más pequeña.
- Las siete páginas públicas responden 200, la hoja de estilos sirve las clases nuevas,
  Ruff en verde y la prueba de precios sigue pasando.

### Qué no se pudo probar

- **El aspecto real**: la línea de tiempo y el bloque de fundadores están verificados por
  marcado y estilos, no con una captura de navegador. Falta mirar en móvil que la hora
  sobre la burbuja no descuadre.

### Decisión del founder registrada

- Las promesas de foto de ticket y notas de voz **se mantienen** en la portada aunque las
  funciones no respondan todavía por falta de claves externas. Queda advertido y es una
  decisión consciente suya: primero la web, luego el sistema.

## 2026-07-27 — optimización de la carga del sitio público

### Qué se probó y con qué resultado

- **Medición previa en producción**: portada 92 KB de HTML, `app.css` 174 KB, Chart.js
  205 KB, sin `Cache-Control` (solo `etag`). Comprimido, que es lo que viaja de verdad:
  portada 16,8 KB, CSS 34,6 KB y **Chart.js 70,4 KB**, con diferencia el activo más
  pesado del sitio.
- **Cacheo de estáticos**: se sirve `Cache-Control: public, max-age=31536000, immutable`
  en producción y `no-cache` en desarrollo. Verificado arrancando el servidor en los dos
  modos. Es seguro porque las plantillas ya piden los archivos con `?v=`, sello que
  cambia en cada despliegue.
- **Chart.js deja de cargarse de entrada**: la portada ya no trae la etiqueta de script;
  la librería se descarga al acercarse la demo al viewport, o al primer clic dentro de
  ella. Comprobado que la portada no la referencia al cargar y que conserva la ruta
  versionada para pedirla después.
- **Imagen del taller** (72 KB, muy abajo en la página) pasa a carga diferida con sus
  dimensiones declaradas para no provocar saltos de maquetación.
- Ruff y las pruebas de solicitudes y de hardening siguen en verde; las páginas responden.

### Qué se descartó tras medirlo

- **Partir el HTML de la portada**: pesaba 92 KB en bruto, pero comprime a 16,8 KB porque
  los 19 paneles de demo son muy repetitivos. El ahorro no compensaba el riesgo de tocar
  la página que más convierte.
- **Convertir a WebP la captura del producto**: solo se usa como imagen de compartir en
  redes; no la descarga ningún visitante y varias plataformas no admiten WebP ahí.
- **Separar el CSS público del panel**: ahorraría del orden de 15 KB comprimidos a cambio
  de un refactor amplio de clases justo antes de entrar clientes reales. Queda anotado
  para cuando el piloto esté estable.

### Qué no se pudo probar

- **El efecto real en un navegador**: no se ha medido con herramientas de rendimiento ni
  comprobado visualmente que las gráficas aparezcan al bajar hasta la demo. Confirmar
  tras el despliegue.

## 2026-07-27 — corrección del calendario y rediseño de la solicitud

### Qué se probó y con qué resultado

- **Calendario, en dos pasos**: la primera captura mostraba el **perfil** de cal.com —la
  lista de tipos de reunión, que obliga a pulsar antes de ver horas— con medio recuadro
  vacío. Se apuntó entonces a la cita concreta usando la vista `/embed`, y la segunda
  captura salió **en blanco**: esa vista espera que la página anfitriona cargue el script
  de cal.com y haga un saludo por mensajes, y sin él se queda esperando. Queda apuntando
  a la URL normal de `sesion-de-estrategia`, que se pinta sola, con 820 px de alto para
  que el calendario no se corte.
- **`/onboarding` con el alta cerrada**: deja de mostrar una pantalla intermedia y
  redirige (303) directamente al formulario, conservando el plan. Verificado con el
  servidor en modo producción. El envío del alta sigue rechazándose, que es lo que de
  verdad protege.
- **Correos de la solicitud**: comprobado que se generan los dos —aviso al equipo y
  confirmación al solicitante— con sus destinatarios correctos. El aviso cae en
  `NOESIS_ADMIN_EMAIL` y, si faltara, en el contacto público.
- **`/solicitar-acceso` rediseñada**: pasa a usar el diseño del sitio público (cabecera,
  menú y pie) en lugar del formato del flujo de cuenta. Verificado que renderiza esos
  elementos y responde 200.
- **Formulario simplificado**: se retira el nombre del negocio y el selector de plan
  deja de mostrarse; el plan viaja oculto desde la página de precios. Comprobado que un
  envío válido se guarda conservando plan y teléfono, y que sigue rechazando el envío
  sin consentimiento.
- Ruff en verde, las 7 pruebas del alta por solicitud y la de precios siguen pasando.

### Qué no se pudo probar

- **Que el calendario se pinte ya correctamente**: la URL actual es la misma familia que
  la que sí funcionaba en la primera captura, pero no se ha abierto en un navegador con
  red tras este cambio. Confirmar visualmente en producción; es el segundo intento.
- **Entrega real de los dos correos**: en local no hay SMTP, así que solo se comprueba
  que se emiten y a quién. Falta ver que llegan y no caen en spam.
- **Aspecto real de la página rediseñada**: verificada por marcado y estilos, no con una
  captura en navegador.

## 2026-07-27 — alta por solicitud, contacto con calendario y portada única

### Qué se probó y con qué resultado

- **Migración 36 (`access_requests`)**: ciclo limpio `35 → 36 → 35 → 36` en SQLite.
  El humo obligatorio del PR la aplicó en PostgreSQL 16 y quedó en verde, que es
  el entorno que usa producción.
- **Formulario público `/solicitar-acceso`**: envío válido guardado con su
  contexto comercial (plan que miraba, teléfono, sector); correo normalizado a
  minúsculas para no duplicar por mayúsculas; rechazo sin consentimiento y con
  correo inválido; señuelo antispam que responde como a una persona pero no
  guarda nada; corte a la cuarta solicitud del mismo correo en el día.
- **Aprobación desde `/admin`**: recorrido completo ejecutado a mano contra el
  servidor local — solicitud, alta, enlace de invitación, contraseña elegida por
  el titular, inicio de sesión y acceso a su propio panel. El enlace no se puede
  reutilizar. La prueba arranca el día del alta (verificado: alta el 27/07,
  caducidad el 10/08). Un cliente normal no ve ni aprueba solicitudes ajenas.
- **Sitio público**: las once páginas responden 200 y `/producto` y `/demo`
  redirigen con 301 sin dejar enlaces rotos. Cabeceras `Open Graph` y canónica
  presentes. Fotos del equipo servidas correctamente.
- **CSP del calendario**: `frame-src` permite cal.com **solo** en `/contacto`;
  comprobado que en el resto del sitio sigue en `'none'`.
- **Suite completa**: 361 pruebas en local. Herramientas en verde: Ruff, Bandit,
  detector de secretos sobre todos los archivos versionados y validador de la
  fuente de verdad.

### Qué no se pudo probar

- **Suite completa sin incidencias en Windows**: queda un error intermitente al
  limpiar carpetas temporales (`PermissionError` de `tearDown`), porque un hilo
  del planificador mantiene abierto el SQLite y Windows no permite borrar
  ficheros en uso. Cambia de prueba en cada ejecución y desaparece al ejecutar
  los archivos aislados. En Linux, que es donde corre el CI, no se reproduce.
- **Renderizado real del calendario incrustado**: la CSP ya lo permite, pero no
  se ha abierto `/contacto` en un navegador con red para confirmar que cal.com
  pinta el iframe. Verificar tras el despliegue.
- **Entrega real de los correos** (aviso de solicitud al equipo e invitación al
  cliente): sin SMTP en local solo se registran en el log. Falta comprobar que
  llegan y no caen en spam.
- **Comportamiento en producción**: nada de esto se ha ejecutado aún contra
  `bynoesis.com`. Antes del despliegue hay que confirmar `NOESIS_BASE_URL` y
  `NOESIS_ALLOWED_HOSTS`, ya corregidas en Railway.

## 2026-07-27 — equipo real y botón de agendar reunión en la web pública

- `/equipo`: captura de escritorio (1400px) y móvil (390px) con Playwright/Chromium
  confirman que las dos tarjetas de fundadores (avatar, nombre, rol, bio, chips de
  habilidades) renderizan correctamente y colapsan a una columna en móvil.
- `/preguntas`: captura de la nueva sección de contacto con el botón "Agendar
  reunión" confirma el mismo patrón visual que `/equipo`.
- `curl -I https://cal.com/bynoesis` devuelve 200 y el HTML contiene
  `<title>ByNoesis | Cal.com</title>` antes de enlazarlo desde ambas páginas.
- `grep` sobre el HTML servido confirma que los dos enlaces apuntan exactamente a
  `https://cal.com/bynoesis` con `target="_blank" rel="noopener"`.
- Suite completa tras el cambio: 345/347 verdes (mismos 2 fallos de macOS en
  `test_backups.py`, sin relación). `tests/test_backend.py` verifica 200 en
  `/equipo` y `/preguntas` y sigue en verde.
- Pendiente: sustituir el monograma de iniciales por fotos reales y confirmar el
  texto final de las bios con el fundador; no bloquea la publicación.

## 2026-07-27 — migración de facturación profesional con facturas ya emitidas

- Reproducido el fallo real: copia SQLite local con facturas en estado `enviada` y
  `cobrada` generadas antes de llegar a schema 35. `python -c "from noesis import
  db; db.init_db()"` fallaba con `sqlite3.IntegrityError: una factura emitida no
  puede alterarse` en `_upgrade_professional_invoicing`.
- Tras el arreglo: la misma base migra `0 -> ... -> 35` sin error. Verificado por
  consulta directa: `schema_migrations` llega a 35, las facturas emitidas quedan con
  `series_id` relleno (no `NULL`) y los triggers `invoices_issued_immutable_update` /
  `invoices_issued_immutable_delete` siguen presentes tras la migración.
- Verificación de que la inmutabilidad sigue activa: un `UPDATE invoices SET
  series_id=999999 WHERE status<>'borrador'` posterior a la migración sigue siendo
  rechazado por SQLite con el mismo mensaje de error legal.
- Suite completa: **345 pruebas verdes / 347** en ~57 s. Los 2 fallos son
  `test_backups.py::VerifiedBackupTestCase` comparando `PosixPath` con y sin el
  prefijo `/private` que macOS antepone a `/var` por symlink; no reproducen en Linux/CI
  y no están relacionados con este cambio. `Ruff` no ejecutado en este ciclo (cambio
  acotado a una función de migración, sin tocar estilo).
- Pendiente: confirmar en CI (Linux, PostgreSQL 16 y SQLite) que el ciclo
  `0 -> 35 -> 0 -> 35` sigue limpio como en el registro del 2026-07-21; no se pudo
  ejecutar Postgres en este entorno local.

## 2026-07-21 — bitácora CISO, antivirus y simulacro de restauración

- Migración 35: crea `security_events`, instala triggers append-only en SQLite y
  PostgreSQL y permite downgrade/upgrade. Dos eventos consecutivos enlazan la huella
  anterior; UPDATE y DELETE son rechazados por base de datos. El humo PostgreSQL 16
  inserta un evento real, verifica la cadena e intenta una mutación que debe fallar.
- La bitácora elimina metadatos con claves de email, teléfono, IP, token, secreto,
  contraseña, fichero, documento, mensaje o cuerpo. La verificación recalcula toda
  la cadena; el centro CISO la consulta sin crear eventos ni mutar controles.
- ClamAV: probado protocolo `INSTREAM` con respuesta limpia y EICAR, además de caída
  obligatoria. En fallo cerrado el documento no llega a almacenamiento y queda una
  señal crítica sin nombre de fichero ni contenido.
- Backups: el flujo habitual sigue creando y restaurando la copia antes de marcarla
  correcta. El simulacro independiente vuelve a restaurar el último SQLite y valida
  el manifiesto documental, registra duración/resultado y nunca toca la base activa.
- Admin: entrar al panel y descargar la copia quedan auditados con IDs internos y
  `request_id`; producción exige Google OAuth incluso si faltan credenciales, caso
  en que el arranque falla de forma segura.
- Pruebas específicas de operaciones, hardening, backups y readiness: 24 verdes.
  Suite completa final: **347 pruebas verdes en 239,9 s**. PostgreSQL 16 se completa
  en CI
  antes de publicar. Pendiente externo: daemon ClamAV, OAuth real,
  restauración desde bucket/otra infraestructura, pentest y revisión RGPD.
- Cierre local: ciclo limpio `0 -> 35 -> 0 -> 35`; Ruff, Bandit, detector de
  secretos (incluidos archivos nuevos), `pip-audit`, `git diff --check` y
  `check_project_truth.py` verdes. `pip-audit` solo omite el paquete local `noesis`,
  que no existe en PyPI, y no encuentra vulnerabilidades conocidas.
- Smoke HTTP aislado: login admin 303, `/admin` 200, bloque CISO renderizado y
  `X-Request-ID` presente. El aviso Starlette/httpx ya conocido no afecta el flujo.
- PR #54: `Tests i migracions` verde en 2m26s y `Humo contra Postgres` verde en
  38s. PostgreSQL 16 aplicó la migración 35, verificó la cadena y rechazó el UPDATE
  de la bitácora; la suite general repitió seguridad, 347 pruebas y ciclo completo.

## 2026-07-21 — hardening de seguridad previo al piloto

- Suite completa: **339 pruebas verdes**. Incluye 80 casos generados con Hypothesis
  para invariantes de IVA/IRPF y total, además de sesiones, documentos, webhooks,
  facturación, portales, WhatsApp y aislamiento existente. Los logs de caídas de IA,
  Meta, SMTP, Stripe, AEAT y backup son fallos simulados que prueban reintentos.
- Migración 34 validada en SQLite con ciclo limpio `0 -> 34 -> 0 -> 34`; crea el
  límite de autenticación persistente y seudonimizado. El job obligatorio del PR
  aplicó el esquema y completó el humo funcional en PostgreSQL 16.
- Archivos: se rechazan imagen con extensión falsa, PDF con acciones activas y
  payloads que exceden límites antes de OCR/almacenamiento. Se acepta un JPEG real;
  fixtures antiguos se corrigieron sin relajar la validación.
- Autenticación: probado el límite compartido por cuenta sin persistir email/IP en
  claro, la caducidad por inactividad, request IDs, cabeceras y limpieza al salir.
- Los portales privados por token responden `no-store` y `no-referrer`. La descarga
  de medios de WhatsApp rechaza hosts engañosos y redirects fuera de Meta antes de
  enviar una petición o exponer el bearer.
- Las peticiones con `Content-Length` superior al techo global se rechazan antes de
  parsear formularios o multipart; los límites más bajos por JSON, audio y documento
  permanecen activos.
- Herramientas: Ruff y Bandit sin hallazgos bloqueantes; `pip-audit` sin
  vulnerabilidades conocidas en dependencias publicadas; detector de secretos pasa
  para archivos versionados y nuevos. La distribución local `noesis` no existe en
  PyPI y por ello `pip-audit` la marca correctamente como no auditable.
- Cadena de suministro: lock reproducible, acciones de GitHub fijadas por SHA y
  Dependabot habilitado. En GitHub se activaron alertas de dependencias vulnerables
  y actualizaciones automáticas de seguridad; secret scanning avanzado no aparece
  disponible para este repositorio/plan y se cubre localmente en CI.
- Pendiente externo: dominio/TLS y cookies reales, pentest, revisión RGPD/fiscal,
  credenciales de proveedores y restauración aislada. No se
  declara desplegado ni auditado externamente.
- Primer run del PR #49: la migración 34 llegó correctamente a PostgreSQL. Los dos
  fallos fueron de fixtures: datos demo con extensión JPG y bytes PDF, y falsos
  positivos Linux del detector de secretos. Se corrigieron los datos, manteniendo
  la validación, y se marcaron individualmente solo constantes de prueba revisadas.
  La siembra rica corregida se ejecutó en SQLite aislado y creó sus 5 documentos.
  El siguiente run confirmó el humo PostgreSQL 16 completo en verde. Los datos
  ficticios repetidos se centralizaron en constantes revisadas para conservar la
  sensibilidad del detector sin excepciones dispersas; las 261 pruebas del módulo
  backend siguieron verdes tras la refactorización.
- Run final de código del PR #49: `Tests i migracions` verde en 2m28s y `Humo contra
  Postgres` verde en 31s, incluyendo auditoría de dependencias, detector de secretos,
  Ruff, Bandit, fuente de verdad, suite, ciclo de migraciones y PostgreSQL 16.

## 2026-07-20 — facturación profesional, entrega y anulación fiscal

- WhatsApp separa `ticket de venta` F2 del ticket de gasto, entiende castellano y
  catalán, reutiliza un cliente habitual solo si es inequívoco y no crea duplicados
  ante referencias ambiguas. Facturar un trabajo cerrado reutiliza su borrador.
- Emitir/entregar requiere una segunda confirmación. Se verificó el recorrido
  mensaje → borrador → SÍ → número de serie → PDF → email durable y su reflejo en
  facturación mensual, ficha de cliente, resumen fiscal y selección de gestoría.
- La web distingue emisión de entrega. La entrega automática respeta el canal
  habitual; email adjunta el PDF y WhatsApp queda en plantilla aprobable con enlace
  privado. Sin contacto no se declara un envío inexistente.
- La migración 33 añade series independientes, líneas con cantidad/precio/descuento
  e IVA, metadatos de factura, programaciones recurrentes idempotentes, adjuntos de
  correo y registros/outbox de anulación. SQLite permite bajar/subir la migración y
  el guardián DDL verifica el orden de índices únicos antes de las FK en PostgreSQL.
- Se probaron totales de IVA mixto e IRPF, edición de borrador, inmutabilidad de
  cabecera/líneas emitidas, series general/simplificada/rectificativa, límite general
  de 400 € de F2, recurrencia sin doble generación y emisión automática solo con
  autorización explícita.
- El correo de factura se persiste antes de SMTP, genera el PDF al entregar, lo
  adjunta y registra preparación/envío. El portal registra visualización y el
  historial por factura incluye emisión, cobros, remisión y respuesta fiscal.
- La anulación conserva factura y alta, exige confirmación con el número, calcula la
  huella oficial, comparte la cadena cronológica con las altas y usa una outbox
  durable independiente. Se verificaron inmutabilidad, encadenamiento posterior,
  respuesta/CSV y rechazo de rectificar un registro ya anulado.
- XML combinado de alta + anulación validado con
  `SuministroLR.xsd`, `SuministroInformacion.xsd` y el esquema XMLDSig oficiales.
  El JavaScript del editor pasa `node --check`; la pantalla y las APIs de borrador,
  series, recurrencia, emisión e historial pasan un flujo HTTP autenticado.
- Suite completa final: **325 pruebas y 52 subtests verdes**. Solo aparece el aviso
  conocido Starlette/httpx. El humo PostgreSQL se amplió a factura profesional,
  trigger inmutable, PDF, historial, series y recurrencia; su ejecución real queda
  para el CI con PostgreSQL 16.
- No se declara homologación: siguen pendientes certificado/mTLS real, subsanación
  de rechazos, exenciones/no sujeción, declaración responsable y auditoría fiscal.

## 2026-07-20 — facturación nativa e integridad fiscal reforzadas

- La migración 32 hace único el número de factura por negocio y bloquea en base de
  datos la modificación o eliminación de sus datos legales una vez emitida. Cobros,
  recordatorios y estados operativos permanecen actualizables sin reescribir la
  factura.
- La emisión reserva la secuencia anual dentro de la transacción, congela emisor y
  receptor y crea registro, evento y outbox Veri*Factu de forma atómica. Se retiró
  el atajo histórico que permitía asignar numeración desde fuera del motor nativo.
- La cadena se verifica antes de añadir y antes de remitir. Se bloquean huellas
  alteradas, retrocesos anómalos del reloj y cambios del NIF emisor después del
  primer registro; la remisión fiscal ya creada continúa aunque se cancele la
  suscripción comercial.
- El cliente AEAT usa TLS 1.2+, certificado ordinario o de sello, clave PEM cifrada,
  límite de respuesta y cierre idempotente de duplicados ya aceptados. Los XML F1 y
  R1 generados se validaron localmente contra los XSD oficiales del 20-07-2026.
- El PDF diferencia una rectificativa, referencia la original, explica la causa y
  ajusta conceptos largos. IVA e IRPF conservan cálculo decimal y redondeo al
  céntimo.
- Suite de este primer cierre: **301 pruebas y 52 subtests verdes** en 221,84 s;
  la cifra actual está en `project-state.json` y en la sección superior. En aquel
  corte quedaban pendientes anulación y subsanación; la primera ya está construida.
  mTLS real, subsanación, declaración responsable y revisión fiscal externa siguen
  pendientes y no se presentan como homologados.

## 2026-07-20 — auditoría documental y mapa único de conexiones

- Corrección posterior del founder: Holded no es una integración futura. Se elimina
  `HOLDED_API_KEY`, el proveedor externo y cualquier selección dinámica; una prueba
  de regresión exige que `get_provider()` devuelva siempre el motor nativo. La
  facturación y Veri*Factu quedan como desarrollo propio de Noesis.

- Se contrastaron los documentos vivos con `origin/main`, `config.py`, todos los
  adaptadores y las salidas HTTP/SMTP reales. Las integraciones externas del código
  quedan inventariadas en `Conectar-APIs.md`, con variables, callback y prueba de
  aceptación; calendario bidireccional, PSD2, cobro por enlace y voz se distinguen
  como capacidades aún no conectables.
- Se retiraron preguntas ya resueltas sobre routers, facturas recibidas y proveedores,
  y se reescribió el roadmap sin duplicar migraciones, ramas o conteos vivos.
- Se corrigieron referencias antiguas de dominio, Postgres y Veri*Factu; los planes
  de 2026-07-03 se marcan como históricos. `.env.example` incorpora los tres precios
  anuales de Stripe y las variables explícitas de seguridad para demo/reset/proxy.
- Riesgo detectado y no ocultado: Stripe live no aplica aún el IVA explícitamente
  en Checkout.
- Validación ejecutada: suite completa con **286 pruebas y 52 subtests verdes**,
  `scripts/check_project_truth.py`, parseo de `project-state.json`, `compileall` y
  `git diff --check`. Solo aparece el aviso conocido de deprecación Starlette/httpx.

## 2026-07-17 — comparación anual clara y sector abierto

- El paso 1 del alta muestra, al elegir pago anual, el coste de doce mensualidades
  tachado, el precio anual, su equivalente mensual y el ahorro en el rojo apagado de
  marca. Al volver a mensual, la oferta se oculta.
- Sector deja de ser un listado cerrado en alta por email, alta por Google y perfil
  de negocio. Acepta hasta 80 caracteres, conserva el texto entre pasos y permite
  segmentar después desde datos reales sin excluir oficios no previstos.
- Se verifican renderizado, selección anual y persistencia de un sector libre con la
  suite completa: **285 pruebas verdes** en 171,6 s. Google/Stripe reales siguen
  sujetos a sus credenciales.
- Servidor real temporal: `/ready` y las altas mensual/anual respondieron 200; el
  HTML anual contiene la oferta y el campo libre. No se abrió navegador visual por
  los cierres previos de la aplicación de escritorio.

## 2026-07-17 — alta profesional, configuración operativa y pago

- La web pública distingue `Probar 14 días` de `Contratar ahora` en cada plan y
  conserva plan y periodicidad hasta el final. La prueba entra al panel sin tarjeta;
  la contratación llega a la revisión y checkout después de configurar el negocio.
- El onboarding tiene cuatro pasos reales: cuenta, negocio, operativa y WhatsApp.
  Fiscalidad, vencimiento, plantilla, cobro, recordatorios, informes y gestoría se
  persisten en las mismas columnas y reglas que usa el producto. Se verificó además
  que una factura emitida adopta el vencimiento elegido.
- Google OAuth conserva intención, plan y periodicidad en alta y acceso. El botón se
  prueba con credenciales simuladas, pero permanece oculto si faltan cliente o secreto;
  no se llamó a Google real.
- Suite completa: **285 pruebas verdes** en 185,5 s. `compileall`, sintaxis del JS,
  `git diff --check`, ciclo de migraciones hasta 31 y verdad de proyecto también se
  validan antes de publicar. Los pagos Stripe y Google reales siguen pendientes de
  credenciales y prueba extremo a extremo.
- Servidor real con SQLite temporal: `/health`, `/ready`, Home, Precios, login y las
  altas de prueba/contratación respondieron 200. Se cerró el servidor después de QA;
  no se usó navegador visual para evitar los cierres de la aplicación ya observados.

## 2026-07-17 — conexiones útiles sin exponer infraestructura al cliente

- Ajustes deja de publicar el catálogo/estado de Meta, SMTP, IA, calendario, banco,
  cobro por enlace o AEAT. El cliente conserva controles reales de WhatsApp, gestoría
  y ayuda avanzada; el diagnóstico completo, incluido Google OAuth, queda en admin.
- Google mantiene alta y acceso OAuth ya implementados y probados; el botón solo se
  renderiza con cliente y secreto presentes. No se llamó a Google real y siguen
  pendientes las credenciales y el callback de producción.
- Agenda incorpora un feed ICS privado, aislado por negocio y revocable. Cobros
  incorpora importación CSV, deduplicación, propuesta explicable y confirmación
  idempotente; una coincidencia ambigua no se acepta automáticamente.
- Correo incorpora outbox durable con reintentos, backoff, deduplicación, alerta
  interna y cobertura RGPD. Recuperación de contraseña, gestoría, digest y
  comunicaciones confirmadas se encolan antes de SMTP.
- Suite completa: **284 pruebas verdes** en 206,5 s. También `compileall` y
  `git diff --check` verdes. Los logs de caídas de SMTP/Meta/Stripe/AEAT y lecturas
  simuladas pertenecen a pruebas deliberadas de degradación.
- Ciclo SQLite validado 0→30→0→30, `scripts/check_project_truth.py`, `compileall` y
  `git diff --check` verdes. El smoke Postgres se amplió para ejercer calendario,
  conciliación, correo y Cobros; no se ejecutó localmente porque esta máquina no
  tiene Docker, por lo que queda como comprobación obligatoria del CI de la PR.
- No se afirma QA visual con navegador porque las sesiones anteriores cerraban la
  aplicación de escritorio; las rutas afectadas sí se renderizaron por TestClient.

## 2026-07-16 — corrección: los subnavs de la demo salían todos a la vez

- En producción los tres subnavs (Dinero, Facturas, Clientes) aparecían apilados
  sobre cualquier pantalla: la clase `.subnav` declara `display:flex`, que gana
  al atributo `hidden`. Se añade `.demo-app-main .demo-subnav[hidden]
  { display:none; }`.
- Lección de QA registrada: la comprobación anterior validaba la propiedad
  `hidden` del DOM, no el renderizado. Esta vez se verificó con
  `getComputedStyle().display` y `offsetHeight` por cada apartado: en Inicio y
  Trabajos no se ve ningún subnav; Dinero, Facturas y Clientes muestran solo el
  suyo.

## 2026-07-16 — la muestra pública replica las pantallas reales del panel

- Cada apartado de la demo de la portada reproduce ahora la plantilla real del
  panel (misma jerarquía y clases: nota de Noesis, cabecera, métricas, tarjetas,
  tablas, calendario, chat y ajustes) reducida con `zoom`, con datos inventados
  coherentes entre pantallas. Antes eran resúmenes aproximados.
- Añadida la barra de subapartados real bajo la barra superior: Dinero abre
  Caja/Análisis/Ingresos/Costes, Facturas abre Presupuestos/Cobros/Impuestos y
  Clientes abre CRM/Productos. 21 pestañas en total; el apartado del menú
  lateral queda activo mientras se navega por sus subapartados.
- Los gráficos de la demo (inicio, análisis, ingresos, costes) se crean la
  primera vez que su panel se muestra, porque un canvas no puede medirse oculto.
- QA: en servidor local se verificaron por DOM las 21 pestañas (panel visible,
  miga correcta tipo «Dinero · Análisis», subnav mostrado/ocultado según grupo,
  sin desbordamiento horizontal) y el ancho de los cuatro gráficos tras abrir su
  panel; consola sin errores. La captura del navegador integrado sigue sin
  responder; no se afirma QA en píxeles.
- Suite completa: 274 pruebas y 52 subpruebas verdes con el árbol del cambio.

## 2026-07-16 — arreglo del marco de la muestra pública y ancho alineado

- Corregido el marco de la muestra de la portada: `.hero-operating-proof`
  conservaba un grid de dos columnas (`190px 1fr`) heredado del diseño con
  `hero-journey`; al retirar la cabecera de ejemplo, el panel entero caía en la
  columna de 190 px y el resto quedaba en blanco. Ahora es un bloque normal.
- La muestra y la franja de cifras se limitan a 960 px centrados, el mismo ancho
  que el texto del hero, para respetar los márgenes de la estructura de la web.
  Esquinas redondeadas completas y sombra simétrica al quedar rodeada de verde.
- Retirado el CSS muerto de `hero-journey` (ninguna plantilla lo usa).
- QA: verificado en servidor local por métricas de DOM (contenedor en bloque,
  panel 142 px + contenido fluido, métricas del Inicio en 4 columnas, diez
  pestañas visibles sin desbordamiento, sin scroll horizontal de página). La
  captura de pantalla del navegador integrado sigue sin responder; no se afirma
  QA visual en píxeles. Nota: el service worker cachea `app.css` hasta que
  cambia `?v=`; en producción el redeploy renueva la versión.
- Test de la portada en verde con el árbol del cambio.

## 2026-07-16 — ampliación de la muestra pública de producto

- La muestra de la portada conserva el Inicio basado en el panel y permite recorrer
  ejemplos de Trabajos, Proyectos, Clientes, Dinero, Facturas, Documentos, Equipo,
  Asistente y Ajustes con datos de una empresa ficticia. No hay llamadas a datos ni
  acciones de una cuenta real desde esta vista pública.
- Se añadieron métricas de impacto etiquetadas como estimación para negocios de
  servicios de 1 a 10 personas; no se presentan como resultados medidos de clientes.
- Validación local pendiente en este cambio: comprobación automática de la plantilla
  y de la coherencia del estado. La revisión visual manual continúa bloqueada por el
  cierre del navegador integrado de Codex.

## 2026-07-16 — portada centrada y acceso con Google preparado

- La portada adopta una jerarquía de campaña centrada: promesa, explicación breve,
  prueba de 14 días, enlace para entender el producto y el Inicio real debajo. Se
  conserva la identidad de Noesis; no se copian marca, promociones, clientes ni
  métricas de Holded.
- La muestra ya no abre pestañas o resúmenes inventados. Expone solo el Inicio real
  con datos de una empresa de ejemplo, la misma barra superior, menú y bloques que
  el panel. El texto declara que las acciones no se ejecutan.
- Google OAuth cubierto por pruebas: estado de un solo uso, alta nueva con correo
  verificado, aceptación legal, conservación de plan/anual y acceso posterior de la
  misma cuenta. Solo aparece cuando existen las dos credenciales de entorno; no se
  hizo ninguna llamada a Google real.
- Suite completa: 274 pruebas verdes, sin fallos; también `compileall`, sintaxis
  JavaScript, render HTTP y el control de verdad del proyecto.
- La revisión visual actual permanece bloqueada por los cierres del navegador
  integrado de Codex. Esta iteración se valida por render HTML, CSS responsive,
  JavaScript, TestClient y pruebas automáticas; no se afirma una comparación visual
  nueva.

## 2026-07-16 — demo pública alineada con el Inicio real

- La pestaña «Inicio» de la vista pública reutiliza la jerarquía y los componentes
  del panel real: Parte de hoy, prioridad, métricas, agenda, trabajo de Noesis,
  lectura de dinero, gráfico y cobros pendientes. También replica su armazón:
  marca, menú agrupado, negocio activo, barra superior y puesta en marcha. El marco
  se presenta como «Vista del producto» y «Empresa de ejemplo»; no llama a datos ni
  acciones de una cuenta real.
- La navegación provisional que reflejaba los diez apartados se retiró en la
  iteración posterior: hasta que cada uno pueda renderizar su pantalla real, la
  vista pública se limita al Inicio y no presenta resúmenes inventados.
- El hero gana anchura útil en escritorio y reduce el titular para evitar cortes
  prematuros. En anual, el ahorro ahora muestra «−8,3 % · 1 mes gratis», importe
  ahorrado y equivalente mensual con contraste rojo informativo.
- Servidor aislado en `127.0.0.1:8022`: Home HTTP 200; se verificaron los diez
  tabs, estructura del Inicio real, gráfico local y selector anual en el HTML.
  La revisión visual volvió a cerrar la aplicación incluso después de actualizarla;
  Windows registró nuevos fallos de `ChatGPT.exe` a las 09:58 y 09:59.
- Suite completa: 240 pruebas y 39 subpruebas verdes (279 casos JUnit), sin fallos
  ni errores; `compileall`, sintaxis JavaScript, verdad del proyecto y
  `git diff --check` también verdes.

## 2026-07-16 — demo pública interactiva y facturación anual

- La Home ofrece una cuenta ficticia identificada como datos simulados. Sus ocho
  apartados usan pestañas accesibles y mantienen trabajos, clientes, facturas,
  cobros, documentos, equipo y lectura de Noesis coherentes entre sí.
- CTA públicos cambiados a «Empieza ahora →». Desde cada plan se conserva plan y
  periodicidad en el alta; los errores de formulario no pierden esa selección.
- Selector mensual/anual sincronizado en Home, Precios y Suscripción. Catálogo
  anual: 319 / 539 / 1.089 euros + IVA, una mensualidad gratis. El checkout elige
  un `price_id` Stripe diferente y registra periodicidad en metadatos.
- Unit economics recalculado: margen de contribución anual estimado de 70,3% / 69,3%
  / 54,1%, sujeto a los supuestos documentados y a validación con uso real.
- Suite completa: 240 pruebas y 39 subpruebas verdes; `compileall`, sintaxis JS,
  verdad del proyecto y `git diff --check` verdes. Permanece el aviso conocido
  Starlette/httpx.
- No se usó el navegador integrado por petición del usuario tras cierres repetidos
  de la aplicación. No se presenta esta iteración como una nueva QA visual; HTML,
  responsive e interacciones se verificaron de forma estática y automática.

## 2026-07-15 — rediseño integral del sitio público

- Home, Producto, Precios, Equipo, Preguntas, login, onboarding y conexión de
  WhatsApp comparten el nuevo lenguaje editorial cálido, pero cada página conserva
  una estructura propia según su función.
- Los tres precios públicos se muestran como 29, 49 y 99 euros al mes más IVA. La
  nota beta de recepción 24/7 del plan premium queda dentro del flujo del plan y no
  tapa contenido.
- No se añadieron valoraciones, testimonios, logotipos de clientes ni cifras sin
  evidencia. La futura prueba social se presenta como historias de piloto aún por
  verificar.
- Rutas públicas y legales comprobadas por HTTP en 200. La Home se comparó con la
  dirección visual aprobada en escritorio, sin errores de consola.
- Suite completa: 239 pruebas y 39 subpruebas verdes; permanece un único aviso de
  deprecación Starlette/httpx ya conocido.
- El navegador integrado cerró la aplicación después de la captura de escritorio;
  por ese motivo la revisión final se completó con pruebas automáticas, inspección
  de HTML/CSS responsive y la evidencia ya guardada, sin repetir el navegador.

## 2026-07-15 — verdad compartida, precios, modo consulta y acompañamiento

- Suite completa desde el código de esta rama: **238 pruebas verdes** en 205,7 s.
  Permanecen el aviso conocido Starlette/httpx y logs esperados de caídas simuladas.
- Pruebas nuevas: una cuenta inactiva puede leer panel y API, pero recibe HTTP 402
  al crear o generar enlaces; el portal de cliente no acepta presupuestos; WhatsApp
  no ejecuta inbound ni entrega outbox; el plan diario no escribe recomendaciones.
- Catálogo de código y vistas sincronizado a **29/49/99 € + IVA**; el script de
  verdad compara automáticamente precios y versión de esquema.
- El acompañante devuelve lectura, preguntas propias y siguiente acción con motivo;
  el caso degradado no tumba la pantalla. Abrir el panel no llama a IA por sí solo.
- `compileall`, `git diff --check` y `scripts/check_project_truth.py` verdes.
- Se verificó HTML y comportamiento por `TestClient`; no se hizo QA visual con
  navegador porque las sesiones anteriores estaban cerrando la aplicación. No se
  sustituye esa comprobación por una afirmación visual ficticia.
- No se llamó a Meta, Stripe, SMTP, Qwen, Anthropic ni AEAT reales. Los precios de
  Stripe, credenciales, entregas y reactivación siguen en [[Tareas-vivas]].

## 2026-07-15 — compositor interno y unit economics

- Rama alineada con `origin/main` en `0471d2c`, incluido el rediseño interior.
- Suite completa final: **199 pruebas verdes** en 160,1 s. Permanecen el aviso
  conocido Starlette/httpx y logs esperados de caídas simuladas.
- Diez pruebas específicas cubren cobro, presupuesto, cita, correo, catalán,
  ambigüedad, aislamiento, confirmación SÍ/NO, reintento y API web autenticada en 200.
- Una orden genérica de facturación no queda capturada por el compositor. El
  WhatsApp pasa el teléfono del titular y mantiene deduplicación de inbound.
- `compileall` y `git diff --check` verdes.
- Notebook ejecutado de principio a fin. Workbook inspeccionado sin errores de
  fórmula, siete hojas renderizadas y `MODEL STATUS = PASS`; cifras reconciliadas
  con el notebook independiente.
- No se llamó a Meta, SMTP real, Qwen, Haiku, Stripe, Retell ni AEAT. Las plantillas,
  credenciales, latencia y entregas reales permanecen en [[Tareas-vivas]].
- El `compose.yml` de Ollama se revisó estáticamente, pero no se ejecutó
  `docker compose config` porque Docker no está instalado en esta máquina.

## 2026-07-14 — coste de IA y preparación del piloto

- Suite completa: **188 pruebas verdes**; permanecen el aviso conocido de
  Starlette/httpx y los logs esperados de caídas simuladas.
- Proveedor compatible: contrato, herramientas, coste estimado y fallback a
  Anthropic cubiertos. Una caída entre proveedores consume un solo crédito.
- Si una herramienta pudo escribir antes de una caída, el segundo proveedor no
  repite la orden automáticamente; el usuario recibe un aviso para revisar actividad.
- `noesis-doctor`: salida humana/JSON, avisos, bloqueos por configuración parcial,
  HTTPS obligatorio para el proveedor externo y ausencia de secretos cubiertos.
- Notebook de costes ejecutado de principio a fin; SQL reproducible contrastado con
  la tabla del informe. Artefacto ejecutivo validado y renderizado.
- Servidor real con base temporal: `/health`, `/ready`, `/privacidad` y
  `/encargado-tratamiento` en 200; el subencargado compatible configurado apareció
  en ambos documentos legales.
- `compileall` y `git diff --check` verdes. No se llamó a Meta, Stripe, AEAT ni a un
  modelo real; esas pruebas siguen siendo P0 del piloto.

## 2026-07-14 — IA desde el primer día y guardián PostgreSQL

- `compileall`, `git diff --check`, suite completa: 182 pruebas y 26 subpruebas
  verdes; permanece el aviso conocido Starlette/httpx.
- Regresión PostgreSQL corregida en la ficha de proyecto: fecha de entrada y fecha
  de creación se ordenan como texto compatible. El smoke añade listado/detalle de
  proyecto, Ajustes, integraciones y parte de campo. GitHub Actions aplicó la
  migración 27/27 y pasó el smoke en PostgreSQL 16.
- IA privada: contrato OpenAI-compatible, herramientas validadas por servidor,
  historial y contexto por negocio, métricas sin contenido y cero créditos externos.
- IA externa: consentimiento explícito en onboarding, opción completa recomendada,
  límite mensual por plan y reserva atómica aislada por `business_id`.
- Servidor real con base temporal: `/health`, `/ready`, Home, onboarding, Ajustes,
  proyectos, detalle y campo en 200; creación de proyecto 201. Se renderizaron
  «Experiencia completa» e «IA privada».
- No se validó un modelo privado, Anthropic ni Meta reales porque no se usaron
  credenciales ni servicio de inferencia. Ese extremo permanece en [[Tareas-vivas]].

## 2026-07-13 — integraciones y salud por negocio

- Migración 27 verificada en SQLite con ida y vuelta hasta 25.
- Suite completa tras combinar `main`: 178 pruebas verdes y 26 subpruebas; aviso
  conocido Starlette/httpx.
- Aislamiento probado para preferencias de IA y solicitudes de banco; la API queda
  además protegida por la guarda común de sesión y `business_id`.
- La salud operativa cuenta por negocio uso/latencia de IA, documentos pendientes,
  correcciones, cola WhatsApp y cola Veri*Factu; no muestra contenido ni credenciales.
- La IA externa y la extracción documental respetan la preferencia. En cuentas nuevas
  parte apagada; reglas, OCR y clasificador local siguen funcionando.
- Smoke HTTP con servidor real: login, Ajustes, API de integraciones, `/health` y
  `/ready` en 200; ocho integraciones renderizadas y detalle operativo presente.
- QA visual pendiente: el navegador interno se cerró antes de alcanzar localhost y
  Chrome no estaba disponible en la sesión. No se sustituye por una validación
  visual ficticia. También queda el smoke Meta/IA/AEAT con credenciales reales.

## 2026-07-13 — monitorización admin Veri*Factu

- Suite completa: 176 pruebas verdes; avisos/logs esperados de tests de reintentos
  Stripe, WhatsApp, Veri*Factu, backup y resiliencia del parte.
- Tests específicos: `VerifactuTestCase` + `AdminCommandCenterTestCase` -> 20 OK.
- `compileall` y `git diff --check` verdes.
- Servidor local con base temporal: `/health` 200, `/ready` 200, login admin 303 y
  `/admin` 200 mostrando “Cola Veri*Factu” y “Vencidas para enviar”.
- Sin conexión AEAT real: solo se validó la observabilidad de la cola, no la
  remisión externa.

## 2026-07-13 — cierre de campo y perfil de cliente

- Suite completa: 175 pruebas verdes; aviso conocido Starlette/httpx.
- Migraciones 25-26 y orden de FK Postgres verificados.
- Aislamiento probado para trabajador, cliente, evidencia, firma y factura.
- QA local desktop/móvil de Clientes, Proyectos y portal del trabajador: 200, sin
  overflow horizontal ni errores de consola.

## 2026-07-13 — columna operativa y control del usuario

- Migraciones 22-24 verificadas en SQLite y generación DDL de Postgres: permisos y
  auditoría, vínculos de proyecto/tarea y entregas versionadas a gestoría.
- Suite completa final: 170 pruebas y 26 subpruebas verdes; queda una advertencia
  de deprecación Starlette/httpx ya conocida, sin error funcional.
- Proyectos: coste real combinado de fichaje, tarifa horaria, gastos y entradas
  manuales sin doble conteo; aislamiento cruzado cubierto.
- Gestoría: paquete con emitidas, gastos, recibidas, originales, manifiesto y huella;
  una fuente sin cambios conserva versión y un cambio crea la siguiente.
- Navegador local: Inicio, Proyectos, Documentos, Ajustes y portal del trabajador en
  200, sin errores de consola. Se comprobó el modal de proyecto y un trabajador con
  trabajo y checklist reales.
- WhatsApp interno: texto, foto, PDF y audio ya tenían flujo; se añadió `HOY`, fichaje
  por trabajo y actualización de tarea para el trabajador vinculado.
- Pendiente externo: Meta, Stripe, proveedor de IA y certificado AEAT no se validan
  sin credenciales reales y siguen figurando como bloqueo de piloto.

## 2026-07-12 — Noesis persistente y entrada documental universal

- Migración 21 aplicada en SQLite: historial del asistente, memoria confirmada,
  clasificación documental trazable y protección de facturas históricas.
- Suite completa: 164 pruebas pasan, incluida separación por negocio, exportación
  RGPD, señales de clientes y confirmación de una factura recibida enviada por PDF
  en WhatsApp.
- Navegador: historial persistente comprobado entre Home y Clientes; el panel de
  Noesis abre desde cada pantalla y conserva el contexto de página.
- Documentos: subida web sin selector técnico; Noesis propone el tipo y la persona
  confirma. Web y WhatsApp usan el mismo clasificador.
- Responsive comprobado a 390 × 844: asistente y panel inferior sin solapamiento
  del campo de texto ni scroll horizontal (`scrollWidth = clientWidth = 375`).
- Pendiente externo: prueba de extremo a extremo con Meta, claves del proveedor de
  IA, Stripe y certificado AEAT. No se han simulado conexiones reales.

## 2026-07-11 — MVP profesional

- Suite completa: 158 pruebas y 26 subpruebas pasan; queda una advertencia de
  deprecación ya existente de Starlette/httpx, sin errores funcionales.
- Proyectos: migraciones SQLite, aislamiento entre negocios, presupuesto, horas,
  coste, margen, equipo, exportación RGPD y borrado en cascada cubiertos por pruebas.
- Navegador: Home y Proyectos renderizan con datos demo; APIs sin errores de consola.
- Responsive comprobado a 390 × 844: Home y Proyectos sin scroll horizontal.
- Menú móvil: `aria-expanded` y `aria-hidden` sincronizados al abrir/cerrar.
- Regresiones corregidas: imports que rompían descarga/subida de Documentos y
  verificación/entrada del webhook de WhatsApp.
- Pendiente externo: prueba real con credenciales Meta, Stripe y certificado AEAT.
