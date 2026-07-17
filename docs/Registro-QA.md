# Registro de QA

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
