# Registro de cambios

## 2026-09-14 — Veri*Factu fuera de Cumplimiento y Términos (textos archivados)

Petición del founder: quitar Veri*Factu también de las páginas legales sin perder
el texto. `cumplimiento.html` pierde la sección «2. Facturación electrónica y
Verifactu» y renumera las siguientes (2–5); `terminos.html` dice «cumplimiento de la
normativa fiscal» en vez de «(incluida Verifactu)». Los textos originales quedan en
`docs/05-legal-y-rgpd/Verifactu-textos-archivados.md` con instrucciones para
restaurarlos. Solo texto. Riesgo mínimo. Rollback: revertir el commit o copiar los
textos del archivo.

## 2026-09-14 — Veri*Factu fuera de la web pública y «Próximamente» en la app

Petición del founder: Veri*Factu aún no está disponible, así que la web pública no
lo anuncia. Quitado de `landing.html` (bloque «Fiscalidad, con criterio»),
`site_precios.html` (plan y ventaja «sin coste extra»), descripción de
`site_preguntas.html`, preguntas de `public_marketing.py` (FAQ de portada y
«¿Está adaptado a Veri*Factu?»; /preguntas pasa de 16 a 15 respuestas), `llms.txt`
(`routers/pages.py`) y el botón «XML AEAT» de la demo pública. Dentro de la app,
`ajustes.html` marca la tarjeta con «Próximamente» y un aviso, y `suscripcion.html`
dice «Veri*Factu próximamente». Sin cambios de lógica: el registro sigue igual para
quien lo tenga activo. `cumplimiento.html` y `terminos.html` no se tocan (textos
legales sobre la normativa). La etiqueta del móvil vuelve a «¿Prefieres escribir tu
número? sin código» a petición del founder. Riesgo bajo. Rollback: revertir el commit.

## 2026-09-14 — Etiqueta del móvil en Ajustes

Petición del founder: la etiqueta «¿Prefieres escribir tu número? sin código»
confundía. Pasa a «Tu número de móvil». Solo texto en `ajustes.html`. Riesgo
mínimo. Rollback: revertir el commit.

## 2026-09-14 — Vincular WhatsApp escribiendo el móvil y códigos que no caducan al recargar

Petición del founder: un cliente que eligió «más adelante» no tenía dónde poner su
número y el código de Ajustes le decía «no válido». Causa: `db.create_whatsapp_link`
borraba los códigos anteriores del negocio en cada visita a Ajustes, así que
recargar invalidaba el código copiado. Ahora solo borra caducados y conserva los
cinco últimos. Nuevo campo en Ajustes («¿Prefieres escribir tu número?») →
`POST /b/{id}/whatsapp-phone` (`routers/account.py`) guarda el móvil esperado 24 h
en `whatsapp_pending_actions` (sin migración). En `web/whatsapp.py`, si ese móvil
escribe sin estar dado de alta, se le pregunta y solo un SÍ desde él lo vincula
(evita apuntar un teléfono ajeno); aplica los mismos conflictos de identidad.
Riesgo bajo. Diagnóstico: filas `kind='whatsapp_expected_phone'`. Rollback:
revertir el commit.

## 2026-09-14 — WhatsApp: tickets grandes, últimos tickets en PDF y negritas

Petición del founder a partir de una conversación real. `web/whatsapp.py`:
`queue_text` traduce `**negrita**` a `*negrita*` (salían asteriscos literales);
«muéstrame los 3 últimos tickets y mándamelos en PDF» lista hasta 5 tickets o
facturas y adjunta sus PDF reales sin pasar por la IA; un ticket de más de 400 €
deja un pendiente `factura_completa` y el SÍ prepara un borrador F1 con los mismos
datos (emitir sigue pidiendo confirmación); «vale, pero quiero que me crees este
ticket» repite la explicación en vez de caer a la IA. `web/chat.py`: «el último
cliente» se resuelve con el cliente de la última factura (antes creaba una ficha con
ese texto); oferta de factura completa; el fallo de IA externa responde con órdenes
que funcionan. `tools.py`: el límite de 400 € con precio final se comprueba antes de
crear el cliente. Riesgo bajo. Diagnóstico: pendientes `factura_completa` y claves
`invoice-request:`. Rollback: revertir el commit.

## 2026-09-14 — Guion del vídeo de la plataforma

Petición del founder: grabar un vídeo que enseñe Bynoesis por dentro, además del de
instalación. Nuevo `docs/01-producto/Guion-video-plataforma.html` (interno): preparación
con `NOESIS_SEED_DEMO`, accesos de la demo comercial, 13 escenas con tiempos, frase,
pantalla y datos a señalar sacados de `src/noesis/demo.py`, inserto de WhatsApp con la
cuenta de instalación y qué no prometer (Veri*Factu, voz/OCR, impuestos, pagos). Solo
documentación; no toca `src/noesis/`. Riesgo nulo. Rollback: borrar el archivo.

## 2026-09-14 — Aviso de cookies sin nombrar a Google Analytics

Petición del founder: el aviso habla de cookies, no de la herramienta. En
`site_base.html` el título pasa a «Esta web usa cookies» y el texto dice que se
usan cookies de analítica propias y de terceros, solo si se acepta y revocables.
Primera capa según la guía de la AEPD: finalidad, terceros y enlace a `/cookies`,
que sigue detallando Google Analytics, sus cookies y la transferencia. Sin cambios
de lógica, CSP ni políticas. Riesgo mínimo. Rollback: revertir el commit.

## 2026-09-14 — Título de /bienvenida

Petición del founder: el `<h1>` de `site_bienvenida.html` pasa de «Empieza con
Bynoesis en diez minutos.» a «Vamos a dejarlo todo listo.». Solo texto; sin
cambios de ruta, CSP ni pruebas. Riesgo mínimo. Rollback: revertir el commit.

## 2026-09-14 — Página /bienvenida con vídeo para clientes

Petición del founder: enviar a cada cliente nuevo un correo con un enlace a una
guía y a un vídeo de instalación, en vez de un HTML adjunto (los clientes de
correo lo marcan como sospechoso y en el móvil no se abre bien). Nueva ruta
pública `/bienvenida` (`routers/pages.py`) con `site_bienvenida.html`: la guía de
`Guia-instalacion-clientes.html` sin el guion de grabación, que sigue solo en docs.
Queda fuera de `_INDEXABLES`: `X-Robots-Tag` y `<meta robots>` noindex y fuera del
sitemap (`site_base.html` gana el bloque `robots`). Vídeo por
`NOESIS_WELCOME_VIDEO_ID` (`config._youtube_video_id` acepta el ID o el enlace
copiado de YouTube; lo demás lo apaga). Sin variable: aviso «muy pronto» y cero
referencias a YouTube. Con variable: `static/public-video.js` crea el iframe de
youtube-nocookie.com solo al pulsar «Ver el vídeo»; la CSP abre `frame-src` a ese
origen únicamente en `/bienvenida` (`server.py`). `cookies.html` y
`privacidad.html` declaran YouTube solo si hay vídeo. Estilos en
`public-marketing.css`. Sin migraciones. Riesgo bajo. Límite externo: grabar y
subir el vídeo (oculto) y poner la variable en Railway. Rollback: revertir el
commit o vaciar la variable para quitar el vídeo sin desplegar.

## 2026-09-13 — Guía de instalación para clientes

Petición del founder: los clientes creían que había que configurar Meta. Nueva
`docs/01-producto/Guia-instalacion-clientes.html`: qué no hace falta, alta en
cinco pasos con los textos reales de pantalla, vinculación con «BYNOESIS código»,
opciones (Ajustes, cambio de móvil, equipo, número comercial con nuestro equipo),
problemas con las respuestas reales del bot y guion para grabar el vídeo.
`routers/team.py`: el mensaje de vinculación del trabajador pasa de «NOESIS
EQUIPO» a «BYNOESIS EQUIPO»; el webhook sigue aceptando las dos. Riesgo bajo.
Rollback: revertir el commit.

## 2026-09-13 — Conexión de WhatsApp con número y mensaje exactos; ajustes móviles

Petición del founder: al conectar WhatsApp debe verse a qué número se escribe y
el mensaje completo, no solo un botón y un código. `web/whatsapp.py`
(`start_link` devuelve `message`, `number` en dígitos, `number_display`
«+34 612 345 678» y `minutes`; sin número oficial ya no genera `wa.me/TUNUMERO`),
`whatsapp_connect.html` y `ajustes.html` enseñan los dos pasos. Revisión móvil de la web
publicada (Lighthouse móvil portada: 99/96/96/100; sin desbordamiento horizontal
a 360 y 390 px en 11 páginas) y correcciones en `app.css`: antetítulos con
contraste AA (#23705d, claro en el bloque final oscuro), zona de toque de 31 px en
el pie móvil y casilla de consentimiento de 20 px. Sin migraciones. Riesgo bajo.
Rollback: revertir el commit.

## 2026-09-13 — Google Analytics con aviso de cookies

Petición del founder: poder consultar la web en Google Analytics. Áreas:
`config.py` (`NOESIS_GA_MEASUREMENT_ID`, solo formato GA4), `web/deps.py`,
`web/server.py` (la CSP añade dominios de Google solo con ID y fuera de zonas
privadas; prefijos en `_PRIVATE_ZONES`), `static/public-analytics.js` (nuevo),
`site_base.html` (aviso y «Preferencias de cookies» en el pie), `cookies.html`,
`privacidad.html`, `public-marketing.css`, `.env.example` y pruebas. Sin ID todo
queda como antes. El recuento propio de visitas se mantiene. Sin migraciones.
Límite externo: hace falta crear la propiedad GA4 y poner la variable en Railway.
Riesgo bajo; si algo falla, vaciar la variable apaga aviso, script y CSP sin
desplegar código. Rollback: revertir el commit.

## 2026-09-11 — Preparar el cambio a S.L., webhook y voz

Objetivo: que el paso de la identidad legal a la S.L. sea solo configuración y
cerrar tres fallos. Áreas: `config.py` (`NOESIS_LEGAL_DOCUMENT_VERSION` validada,
`legal_registry_missing`), `readiness.py` (aviso «datos registrales»),
`routers/webhooks.py` (token de verificación vacío rechazado, `compare_digest`,
`text/plain`), `web/whatsapp.py` (`_audio_to_text` captura un transcriptor privado
mal configurado), `.env.example`, pruebas y la lista «El día del NIF» en
`Constitucion-y-primer-euro`. Pruebas en Registro-QA. Sin migraciones.
Riesgo bajo: el aviso no bloquea; si `WHATSAPP_VERIFY_TOKEN` faltara en desarrollo,
la verificación de Meta ahora devuelve 403. Rollback: revertir el commit.

## 2026-09-11 — `docs/` ordenada por temas

Petición del founder: ordenar la documentación. 86 archivos pasan de la raíz de
`docs/` a nueve carpetas temáticas numeradas (producto, técnico, WhatsApp e
integraciones, seguridad, legal/RGPD con `cumplimiento/`, negocio, marketing,
agentes IA con `handoffs/` y `prompts/`, histórico). El núcleo vivo sigue en la
raíz porque lo leen CI (`check_project_truth.py`), `production_check.py` y los
agentes. Se reescriben los enlaces relativos, las rutas `docs/...` de `AGENTS.md`,
`README.md`, `facebook/` y los scripts (`check_cumplimiento.py`,
`build_estado_xlsx.py`, `build_modelo_economico.py`, playbook). `Inicio.md`
explica la estructura. No se toca `src/`: los comentarios de `db.py` y
`billing.py` que citan `docs/Fiscalidad.md` y `docs/Unit-economics-y-cerebro-interno.md`
se corregirán con el próximo cambio de producto. Esta bitácora y `Registro-QA`
conservan las rutas antiguas por ser históricas. Los PDF enlazados entre sí
(`Ruta-legal`) necesitan reimprimirse desde su HTML ya corregido.
Pruebas: 0 enlaces relativos rotos, `check_cumplimiento` y `check_project_truth`
OK. Riesgo bajo, solo documentación y rutas de scripts. Rollback: revertir commit.

## 2026-09-10 — Plan de emisión, céntimos y diagnóstico real de Meta

La captura mostró 100 → 99,99 €, fallo de subida y pérdida de «emitir y envíame».
Áreas: `conversation_plan.py`, `web/whatsapp.py`, `tools.py`, `db.py` y regresiones.
Se separan intención de emisión y destinatario; la confirmación verifica huella
de borrador/líneas dentro de la transacción. Descarga no autoriza envío a cliente.
La creación con total incluido conserva el céntimo residual en la cuota; vía
explícita de una línea, sin reescribir emitidas. Se normaliza espacio en ID Meta.
Pruebas: 69 de conversación/WhatsApp/fiabilidad OK; casos adicionales en QA.
Producción: configuración examinada sin mostrar secretos y PDF real subido a Meta
con ID normalizado, sin emisión ni envío al destinatario. Riesgo medio por cálculo
y confirmaciones. Sin migración; rollback por revert. Memorias previas caducan.
El agente universal sigue pendiente, alcance en `Agente-operativo-fiable.md`.

## 2026-09-10 — Crear y adjuntar en la misma petición

La prueba real del founder mostró que la búsqueda PDF interceptaba «créame un
tiquet… y envíame PDF». Se prioriza creación, se separa la entrega y solo se
adjunta el ID efectivamente devuelto. `nlu.py` acepta «créame un tiquet para…
importe concepto…» como venta, sin cambiar tickets recibidos a gastos.
`whatsapp.py` conserva diez minutos la selección PDF y únicamente rechazos
fiscales explícitos para «créalo»; nunca reintenta un resultado incierto.
F2 se explica como tipo, no número. Pruebas: tres regresiones con las frases de
la captura y casos válidos; 35 pruebas de conversación/WhatsApp OK.
Riesgo medio, sin migraciones ni cambios fiscales. Meta simulado; entrega física
pendiente. Rollback: revertir este commit; claves de contexto separadas caducan.

## 2026-09-10 — Facebook con el nombre Bynoesis y SEO verificado

Objetivo: aplicar a la cola de Facebook la decisión de nombre público único antes
de conectar la página, y dejar constancia de la verificación del SEO/GEO de
`88adfa3`. Las 48 piezas de `facebook/calendario.json` decían «Noesis» 17 veces
(p. ej. «Qué es Noesis»); publicarlas cada 3 días repetiría el nombre que Google
confunde con otras empresas de software.

Áreas: `facebook/calendario.json` (títulos, textos y descripción), docstrings de
`facebook/nucleo.py` y `facebook/publicar.py` y `facebook/README.md`. Los `id` no
cambian: el publicador identifica cada pieza por `id` y consulta la página antes de
escribir, así que ninguna se repite. Enlaces a bynoesis.com intactos. No toca
`src/noesis/` ni la web.

Verificación de producción de `88adfa3`: `/ready` esquema 55; `/llms.txt` 200
`text/markdown` sin `X-Robots-Tag`; `/preguntas` con FAQPage de 16; portada sin
«Noesis». Founder: Bing importado desde Search Console con sitemap en Success
(14 URLs); Search Console con sitemap Correcto (14) e indexación pedida para `/`,
`/preguntas` y `/autonomos`. Pruebas y límites en Registro-QA. Riesgo: bajo, solo
texto editorial aún no publicado. Rollback: revertir este commit.

## 2026-09-10 — Identidad del PDF y conversación verificable

Objetivo: impedir que pedir un cliente desconocido envíe la última factura demo.
Áreas: `web/whatsapp.py`, `web/chat.py`, `agent.py`, `tools.py`, `db.py`,
`web/invoice_pdf.py`, `templates/facturas.html` y pruebas conversacionales.
La resolución exige referencia inequívoca o contexto reciente de teléfono/negocio.
Las citas nuevas se vinculan al ID Meta; las antiguas sin asociación piden número.
El borrador usa su PDF real marcado, se sube a Meta y no se emite. Las respuestas
de creación usan resultados reales; el agente recarga también los turnos locales.
Pruebas: 13 regresiones nuevas con base/PDF reales y Meta simulado; regresión
general en Registro-QA. Límite: entrega física pendiente. F2 conserva el límite
general de 400 € IVA incluido, sin presumir excepciones sectoriales de 3.000 €.
Riesgo medio: selección documental/conversación. Rollback: revertir commit, sin
migración ni reescritura fiscal. Memoria aditiva con TTL 30 minutos/24 horas.

## 2026-09-10 — SEO y GEO: un solo nombre, llms.txt y FAQ de /preguntas

Objetivo: que buscadores y asistentes de IA reconozcan una única entidad y lean
una ficha fiable. La web pública mezclaba «Noesis» y «Bynoesis» (descripción de la
portada, FAQ marcada, CTA, demo, contacto y título del calendario); el founder fija
Bynoesis. `/llms.txt` no existía (404) y `/preguntas` mostraba 16 respuestas sin
datos estructurados.

Áreas: `web/public_marketing.py` (FAQ y CTA con Bynoesis; `question_groups` como
fuente única de las 16 preguntas, con respuestas según voz/OCR/alta), plantilla
`site_preguntas.html` (bucle + FAQPage + BreadcrumbList), `routers/pages.py`
(`/llms.txt` desde `billing.PLANS`, contacto y alta; flags a `/preguntas`),
`server.py` (`/llms.txt` sin `noindex` y fuera del recuento de visitas), plantillas
públicas y `public-calendar.js` (solo texto visible). Identificadores internos,
espacio de nombres del calendario y rutas no cambian.

Pruebas: tres contratos nuevos en `test_seo.py` (llms.txt con precios del catálogo,
enlaces, alta cerrada y sin `noindex`; FAQPage idéntica al texto visible y sin
prometer voz; ninguna página indexable dice «Noesis») y `/preguntas` añadida al
contrato de metadatos de `test_public_marketing.py`. Recuentos en Registro-QA.
Límites: no se ha publicado; Bing, resultados enriquecidos y citas en asistentes de
IA dependen de terceros y no se prometen. Riesgo: bajo, solo contenido público.
Rollback: revertir este commit; sin migración ni datos que deshacer.

## 2026-09-10 — archivo documental conectado y control claro de proyectos

Objetivo: eliminar la contradicción por la que Facturas mostraba documentos
generados desde web o WhatsApp mientras el Archivo aparecía vacío. El archivo
ahora proyecta las facturas del registro contable y enlaza su PDF reproducible,
sin crear otra fila de datos ni otra copia física que pueda quedar desactualizada.
Los borradores aparecen como pendientes, pero no se convierten en ingresos
contables; si una factura ya tiene un original subido y vinculado, solo se muestra
esa representación. La misma proyección sirve al titular y a la gestoría y sigue
aislada por `business_id` y período.

Proyectos sustituye el campo numérico de avance por un deslizador accesible de 0 a
100, conserva validación en servidor y presenta los estados como controles visibles:
planificado, en curso, en pausa, finalizado y cancelado. Finalizar fija el 100%;
cancelar conserva historial y costes, pero deja de contar el proyecto como activo.
No hay migración ni dependencia nueva. Pruebas específicas cubren límites,
aislamiento, no duplicación, proyección y portal profesional; la regresión completa
y publicación se consignan en `Registro-QA.md`. Rollback: revertir este commit;
no hay datos que transformar.

## 2026-09-10 — lenguaje real para pedir PDF por WhatsApp

Objetivo: corregir la reproducción exacta de producción «Passame el pdf del
tiquet» y «No pots enviar el pdf per aqui?». La primera versión reconocía una
lista cerrada de verbos y omitía la variante mixta `passame` y el infinitivo
`enviar`; ambas frases caían en el chat generativo, que podía negar una capacidad
que el canal ya tiene. El detector pasa a reconocer familias lingüísticas de
enviar, pasar, mandar y adjuntar, manteniendo como condiciones PDF y contexto de
documento, pronombre directo o entrega «aquí».

Se añade una defensa independiente que sustituye cualquier negación generativa
de envío/generación de PDF por una explicación veraz de la capacidad real y sus
límites: documento emitido, mismo negocio y confirmación previa si es borrador.
No cambia facturación, permisos, esquema, enlaces ni el adaptador Meta. Pruebas:
las dos frases reales envían un `document`; una respuesta simulada que niega la
capacidad queda bloqueada; clase WhatsApp completa en verde. Riesgo: una frase
con PDF, verbo y contexto se interpreta como solicitud de entrega al propio
titular; no modifica ni remite al cliente. Rollback: revertir este commit, sin
migración ni datos que deshacer.

## 2026-09-09 — el PDF pedido por WhatsApp es un adjunto real

Objetivo: corregir el caso real «envíame/pásame el ticket en PDF». Hasta ahora la
petición caía en la IA conversacional, que podía afirmar que había adjuntado un
archivo aunque el canal solo hubiese enviado texto. Se intercepta localmente la
intención en castellano o catalán, se resuelve el número o cliente dentro del mismo
`business_id`, se exige una factura ya emitida y se envía un mensaje `document`
reactivo mediante la Cloud API con el PDF del portal y nombre seguro. Un fallo de
Meta produce un mensaje veraz con enlace de descarga; nunca una falsa confirmación.

Se añade una última defensa que sustituye cualquier afirmación generativa de PDF
adjunto cuando no se ha ejecutado la operación. No cambia esquema, permisos,
facturación ni la entrega existente a clientes. Los cambios previos del socio
`f93e5c0..32aa061` se integran por fast-forward y no tocan este flujo.

Pruebas: envío real simulado, selección de Marta frente a otro cliente, seguimiento
«pásamelo en PDF», rechazo de borrador, fallo de Meta y bloqueo de afirmación falsa.
Límite externo: producción no tiene transcriptor configurado; la nota de voz de la
captura seguirá pidiendo texto hasta provisionar Whisper/Groq. Rollback: revertir
este commit restaura el comportamiento anterior sin migración ni tocar documentos.

## 2026-09-09 — la demostración de la portada es un dispositivo

Objetivo: el founder señaló que el bloque de conversación no se distinguía del
resto de la página. Era blanco sobre crema, así que el elemento más importante
de la portada era el que menos destacaba. Pasa a ser el único bloque con fondo
saturado del sitio y se lee como lo que es: una pantalla.

Se corrigen de paso tres cosas que ya estaban mal. `.mini-result > b` —la cifra
del caso de cobros— usaba el verde de marca y quedaba con menos jerarquía que su
propia etiqueta; sobre oscuro habría desaparecido. Los casos cortos dejaban medio
escenario vacío por debajo, porque la altura es fija; ahora la conversación se
ancla abajo y el hueco queda arriba, como el historial de un chat real. Y
`noesis-mark.svg` lleva los verdes fijos dentro del SVG, así que sobre oscuro se
perdía el polígono interior: recibe un disco claro propio.

El founder pidió más presencia todavía, así que el marco se refuerza: la orla
pasa a blanca para separarse del crema, y la elevación se reparte en tres sombras
—contacto, cuerpo y difusa— en vez de una sola. La pantalla deja de ser un color
plano y lleva un degradado corto con un filo de luz arriba, que la hace parecer
encendida en lugar de rellena.

El founder pidió además un marco. Se resuelve con anillos de `box-shadow`: una
orla clara y un filo finísimo que separan el dispositivo del lienzo y lo apoyan
sobre la página. No ocupan maquetación, así que no hay riesgo de desbordamiento
lateral; aun así se comprobó que no aparece scroll horizontal a 390, 768 ni
1280 px y que los márgenes quedan simétricos. En móvil la orla baja de 11 a 6 px
porque el margen lateral es de 18 y si no casi toca el borde de la pantalla.

Límite conocido: durante la animación de entrada los pasos aún no visibles siguen
ocupando su sitio con `opacity: 0`, así que en esos segundos el hueco queda abajo.
Es deliberado para evitar saltos de maquetación y no se toca.

Áreas: solo `web/static/public-marketing.css`, en un bloque nuevo al final del
archivo y con todas las reglas acotadas bajo `.conversation-demo`. Sin cambios de
plantilla, script, copy, esquema ni permisos. El borrador de ejemplo sigue en papel
a propósito: es un documento, no parte del dispositivo.

Pruebas: 12 de `test_public_marketing` y los dos contratos Node en verde;
`check_project_truth` correcto. Contrastes calculados sobre cada fondo del panel,
todos por encima de 4,5:1. Verificado con captura real a 1280 px en los casos de
factura, ticket y cobros, y a 390 px en móvil. Límites: no verificado en móvil físico, en Safari
ni en producción. Riesgo: bajo y visual; no hay lógica implicada. Diagnóstico: si
algo se vuelve ilegible, el bloque es contiguo y está comentado. Rollback: borrar
ese bloque restaura el aspecto anterior sin tocar nada más.

## 2026-09-09 — compatibilidad PostgreSQL de los contadores públicos

Tras publicar `ccb1b54`, Railway y la puerta pública (14 páginas, esquema 55,
8 cabeceras) pasan, pero CI detecta que el patrón LIKE literal con porcentaje
rompe las consultas parametrizadas de psycopg al abrir administración. Se pasa
el patrón como parámetro en las cinco consultas de `db.py`. Se amplía la puerta
PostgreSQL descartable para comprobar contadores y el acceso administrativo.
Sin migraciones, cambios de permisos ni datos de negocio. Riesgo acotado a estas
consultas; no revertir al literal defectuoso. Revalidar CI y despliegue del hotfix.

## 2026-09-09 — web pública: la conversación como demostración

Objetivo: implementar el prompt sobre `4df5088`, conservando la corrección del
socio. Cuatro páginas con WhatsApp, demo, copy verificable, SEO y navegación móvil.
Calendario real opt-in (enlace anterior 404), contador separado de visitas visible
en Marketing. Sin cambios en gestiones, permisos o esquema; versión 55.

Áreas: plantillas/parciales públicos, CSS/JS locales, `public_marketing`, `config`,
`deps`, `pages`, `server`, `db/admin` y textos legales. El wheel incluye assets;
CI ejecuta contratos JS. Archivos y QA: [[Rediseño-web-2026-09-09]], [[Registro-QA]].

Validación final: 767 pruebas Python y dos contratos Node verdes, lint/seguridad,
build con 167 archivos y navegador en cuatro anchos. `.secrets.baseline` solo
sincroniza líneas de CI, sin nuevas excepciones.
Corregidos CTA de alta cerrada y referencia de caché de gráficos durante regresión.
Riesgo: presentación, declaraciones comerciales y protocolo externo. Límites:
canal público demo, proveedores reales, cita/correo, Safari y métricas de campo.

Diagnóstico: permiso/CSP/Cal.com ante calendario vacío; `/public/event` y Marketing
ante recuentos ausentes. Rollback por revert normal, sin migración. Si el código
anterior no excluye `@event:`, conservar esa exclusión o retirar solo esos contadores
tras exportarlos. No tocar datos de negocio. Publicación autorizada por el founder:
commit y push a main, con despliegue automático de Railway. La comprobación del
SHA remoto, despliegue y humo público se realiza después de publicar este commit.

## 2026-09-09 — plan maestro para poder cobrar el primer euro

Objetivo: el founder enseñó el panel de Meta con la verificación del negocio en
«No aprobado» y pidió un documento único con todos los pasos para empezar a
vender. La información estaba repartida entre `Ruta-legal`, `Meta-Verificacion`,
`WhatsApp-Puesta-en-marcha`, `Constitucion-y-primer-euro` y `Tareas-vivas`, y dos
de esos documentos se contradicen.

Se añade `docs/Plan-primer-euro.html`: estado verificado hoy, las cuatro puertas
en orden de dependencia (identidad legal, verificación de empresa, Advanced
access, papeles para cobrar), las fases con responsable y criterio de cierre, las
nueve plantillas, las variables por servicio, la prueba de aceptación y el coste.

Resuelve la contradicción sobre App Review a favor de `Ruta-legal.html`, que es
posterior y razona el porqué: Advanced access sobre `whatsapp_business_management`
es obligatorio para acceder a la WABA de otro negocio aunque se conceda a mano, y
sin él la API devuelve error 200. `Meta-Verificacion.html` sigue diciendo lo
contrario en su tabla del Camino A y queda pendiente de corregir.

Acota además el alcance de ese permiso, que `Ruta-legal` deja abierto a la lectura
de que bloquea el piloto entero: solo afecta al número comercial de cada negocio.
El número central es activo propio, todos los clientes escriben al mismo, y
`_post_to_meta` cae a `_PHONE_ID` cuando el mensaje no lleva conexión, así que los
avisos al cliente final salen igual. La página de precios no promete número propio;
`ajustes.html` lo ofrece como conexión opcional. Conclusión documentada: se puede
cobrar sin Advanced access, y se pide ya porque tarda semanas.

Áreas: solo documentación, un archivo nuevo. Sin cambios en `src/noesis/`, sin
migración, sin credenciales y sin llamadas pagadas. Pruebas: ninguna, no hay
código afectado. Límites externos: el motivo concreto del rechazo de Meta solo se
ve en el Centro de seguridad del founder, las variables vivas de Railway no se
leen desde el repositorio, y el requisito de Advanced access se apoya en la
documentación de Meta y no en una prueba con una WABA de cliente real. Riesgo:
bajo. Diagnóstico y rollback: borrar el archivo y esta entrada.

## 2026-09-09 — vincular WhatsApp dice la verdad y no quema el código

Objetivo: un teléfono que ya está de alta en Equipo no podía vincularse como
número del titular, y el error lo escondía todo bajo «Ese teléfono ya está
vinculado o no es válido», que además consumía el código. Ahora el mensaje dice
qué identidad ocupa el número, dónde se quita y el código sigue vivo para
reenviarlo cuando esté arreglado.

El panel tampoco permitía encontrar el choque: Cuentas solo enseña el teléfono
del titular, así que una ficha de Equipo con ese número era invisible. Se añade
en Cuentas la consulta «Identidad de un teléfono en WhatsApp», que mira titulares
y fichas, y un botón para liberar el número. Ambas quedan auditadas.

Áreas: `db.whatsapp_identity_rows`, `db.free_whatsapp_phone` y
`db.whatsapp_phone_conflict` (motivo único para el choque, usado también por
`set_whatsapp_status`), `web/whatsapp._try_link` y `_revive_link`, dos rutas en
`routers/admin.py` con su sección en `admin.html`, y
`scripts/whatsapp_identidad.py` para hacer lo mismo desde consola. Sin migración
ni cambios de esquema, credenciales ni llamadas pagadas.

Pruebas: suite completa, dos pruebas nuevas en `test_whatsapp_multichannel.py`
(choque con Equipo con reintento del mismo código, y número que ya es de otro
negocio) y una en `test_admin_workspace.py` (consulta, liberación, autenticación
y eventos de seguridad). Riesgo: bajo; el bloqueo ya existía, cambian el mensaje,
la vigencia del código y la visibilidad en el panel. La liberación es destructiva
en lo suyo: quita el teléfono de la ficha y desconecta el canal, sin borrar
personas ni datos. Diagnóstico: `log.warning` «Vinculación de WhatsApp
bloqueada», eventos `admin.whatsapp_identity_*` y
`python scripts/whatsapp_identidad.py <teléfono>`. Rollback: revertir el commit.

## 2026-09-08 — consolidación de la mañana para `main`

Objetivo: ordenar y publicar en una única base el trabajo concurrente sin perder
protecciones. Se integra Facebook seguro en Windows, centro de mando móvil y consumo
por cuenta, fiabilidad documental/WhatsApp, evidencia de copias, revisión de acciones,
servicio Whisper privado y aprendizaje supervisado. Los conflictos documentales se
sumaron; en WhatsApp se preservaron foto repetida, dirección de factura y fallo de
borrador. Áreas y límites detallados en las entradas específicas siguientes.

Pruebas: 107 dirigidas y 752 completas en verde, Ruff, compilación, JSON, verdad del
proyecto, diff y detector de secretos. Los cuatro falsos positivos revisados quedan
explicados en línea: tabla pública NIF, NIF ficticios y revisión pública de modelo.
Sin migración ni credenciales. La revisión y el aprendizaje quedan
apagados por defecto; Whisper no se despliega como servicio, AWS no se provisiona y
una copia externa no sale sin configuración completa. Riesgo: combinación de rutas
de documentos, scheduler y chat. Diagnóstico: logs sin contenido, health/ready y
pruebas citadas. Rollback: apagar flags opcionales y revertir los tres commits de la
consolidación; no restaurar la BD porque el esquema no cambia ni deshacer operaciones
ya confirmadas. Publicación autorizada por el founder en esta tarea.
Release `086039e0b538` publicado y verificado en Railway; puerta externa, CI y humo
PostgreSQL verdes. Revisión, aprendizaje y ledger confirmados apagados.

## 2026-09-08 — conectar Facebook desde Windows sin dejar la clave en el historial

Objetivo: que el founder pueda completar la conexión desde su ordenador. La guía
daba rutas de macOS (`.venv/bin/python`), que en Windows no existen, y obligaba a
pasar la clave secreta y el token corto como argumentos, con lo que quedaban
escritos en el historial de PowerShell.

`facebook/conectar.py` deja de exigir esos tres valores por línea de comandos:
los toma del argumento si está, si no del entorno (`FACEBOOK_APP_ID`,
`FACEBOOK_APP_SECRET`, `FACEBOOK_TOKEN_CORTO`) y, si tampoco, los pregunta por
teclado ocultando los dos secretos. Los argumentos siguen funcionando igual para
quien los use.

Al escribir los secretos a ciegas es fácil que el pegado no entre y el fallo se confunda con una clave incorrecta, así que el script confirma cuántos caracteres ha recibido y, si Meta rechaza la clave, dice de dónde sacarla.

Se documenta además que la sección «Revisión de la aplicación» no hay que tocarla: `Standard access` es el estado correcto para publicar en la página propia, y solicitar la revisión arrastraría verificación del negocio sin necesidad.

Áreas: `facebook/conectar.py`, `facebook/README.md`,
`facebook/Conectar-Facebook.md` y `.html`. Sin migración, sin credenciales en el
repositorio y sin llamadas pagadas. Pruebas: `tests/test_facebook.py` (22 verdes)
y comprobación de la precedencia argumento → entorno → teclado. Riesgo: bajo; si
alguien invocaba el script sin los tres argumentos antes fallaba y ahora pregunta.
Rollback: revertir el commit.

## 2026-09-08 — guía de Facebook: la pantalla de casos de uso de Meta

Objetivo: desatascar el alta de la app de Meta. La guía saltaba de «Crear app» a
«tipo Empresa», pero el asistente actual pregunta antes por **casos de uso** y
ninguno de los destacados corresponde a publicar en la propia página.

Se documenta la ruta exacta: filtro «Otros» → «Otro» (bajo «¿Buscas otra cosa?»,
la que crea la app en la experiencia antigua) → tipo Empresa. Se avisa de dos
trampas de esa pantalla: «Crea una aplicación sin un caso de uso» deja la app sin
permisos de páginas y bloquea el paso del token, y el aviso *going away soon* de
«Otro» solo afecta a la creación de apps nuevas, no a las ya creadas ni a sus
tokens. Se cita «Administración de contenido» como alternativa duradera y se
recuerda reutilizar la app de WhatsApp si ya existe.

También se documenta la pantalla siguiente, «Productos disponibles»: no hay que
configurar ninguno —Messenger, Instagram, WhatsApp o marketing solo estorban—, y
la app se queda en modo desarrollo y tipo Empresa, que es lo que evita la revisión
de Meta.

Áreas: `facebook/Conectar-Facebook.md` y `facebook/Conectar-Facebook.html`.
Documentación únicamente: no se toca `src/`, ni esquema, ni pruebas, ni
credenciales. Sin límites externos nuevos. Riesgo: que Meta vuelva a renombrar la
pantalla; la guía ya advierte de ello en el paso 2. Rollback: revertir el commit.

## 2026-09-08 — aprendizaje supervisado y aclaraciones (candidato local)

Objetivo: convertir correcciones verificadas en equivalencias explícitamente
aprobadas sin aumentar autonomía. Áreas: `learning.py`, chat, revisión, contexto
del agente, API de informe, configuración, tests y runbook. Sin migración.
Flag nuevo apagado y dependiente de revisión. Guía de factura por cliente/concepto/
importe y telemetría sin contenido; memorias literales visibles y eliminables.
19 pruebas nuevas y humo HTTP autenticado con aislamiento; regresión completa
702/702 documentada en Registro-QA. Sin push, despliegue, compras ni servicios reales.
Riesgo: interpretación, memoria persistente y concurrencia; diagnóstico mediante
recuentos por negocio y reproducción sintética, no lectura global de chats.
Rollback: apagar aprendizaje, reiniciar y dejar vencer pendientes; no restaurar
BD ni deshacer acciones confirmadas. Revisión puede seguir activa. No es
reentrenamiento ni garantía de comprender cualquier mensaje.

## 2026-09-08 — revisión conversacional y Whisper privado (candidato local)

Objetivo: corregir interpretaciones peligrosas y revisar cliente/importe/acción
antes de guardar. Áreas: NLU, herramientas, `action_review.py`, chat web/audio,
WhatsApp, adaptador/servicio de voz, Dockerfile aislado y comprobador. Sin migración.
Revisión nueva detrás de flag apagado; rechazos peligrosos son correcciones locales.
Pruebas en `Registro-QA.md`; activación y límites en el runbook de fiabilidad/Whisper.
Suite final 683/683, Ruff, compilación, verdad documental y diff limpios.
Sin producción, compras, push ni credenciales; árbol principal ajeno preservado.
Riesgo: interpretación, concurrencia y capacidad de voz. Diagnóstico: corpus y
comparación propuesta/BD, proceso privado. Rollback: flag false y revert de código,
sin restaurar BD; dejar vencer propuestas antes de reactivar. No se certifica voz
ni entrega externa por tener pruebas locales.

## 2026-09-07 — fiabilidad conversacional, documentos y facturas recibidas

Objetivo: convertir los fallos reproducibles de `Arreglos.html` en contratos de
producto sin consumir IA externa. Se añade validación determinista y no
contabilizable de base/IVA/IRPF/total, fechas y NIF español; una incoherencia baja
la confianza y bloquea el alta rápida por WhatsApp hasta revisión humana. Las
facturas recibidas ya se corrigen desde Costes mediante API autenticada y aislada.

WhatsApp vuelve a leer fotos duplicadas igual que los PDF, sin crear otro archivo
ni mostrar identificadores internos. El calendario incluye `VTIMEZONE`. El cerebro
local entiende importes sin «euros», miles españoles, «factúrame» y el orden
importe→cliente; permite crear cliente/proveedor de forma explícita. Un alta de
usuario incompleta se deriva a la invitación segura de Equipo.

Áreas: `fiscal_validation.py`, extracción, documentos/Costes, WhatsApp, NLU,
herramientas, calendario y pruebas. Sin migración, credenciales, llamadas pagadas
ni producción. Pruebas dirigidas y simulación sintética en `Registro-QA.md`.
Riesgo: interpretación de lenguaje o edición accidental; diagnóstico en las rutas
locales y tests citados. Rollback: revertir este cambio completo; no hay datos de
esquema que deshacer.

## 2026-09-07 — documento «Arreglos»: nueve fallos pedidos por el founder

Objetivo: dejar por escrito, con causa localizada en el código, los nueve puntos
que el founder encontró usando el producto. Documentación únicamente; no se toca
`src/`, ni esquema, ni pruebas.

Verificado ejecutando contra base temporal (seis de los nueve): el reconocedor no
entiende «hazme una factura a Juan de 100 euros» (parte el número en el separador
«de» y deja base cero), ni importes sin la palabra «euros», ni el punto de los
miles; «crear cliente», «nuevo proveedor» y «crear usuario» no crean nada y caen
en el resumen del coach; con dos clientes homónimos la desambiguación funciona
pero viaja como excepción y aborta la operación entera.

Verificado leyendo código: `_validated_invoice` valida campo a campo y no
comprueba base + IVA − IRPF = total, ni base × tipo = cuota, ni el formato del
NIF; para las facturas recibidas solo existe `set_received_invoice_status`, así
que una mal leída no se puede corregir; `overdue_invoices` es código muerto —una
sola aparición en todo el repositorio, su propia definición—; el ICS emite
`TZID=Europe/Madrid` sin el `VTIMEZONE` que la norma exige; y la rama de
duplicados que se arregló en 7b2d8cc solo cubre PDF, no fotos.

Aclarado con el founder: los tres avisos de factura (importe, IVA y CIF) deben
avisar; «no lo digas» en el dictado original era un desliz.

Nuevo: `docs/Arreglos.html`. Sin riesgo de regresión.

## 2026-09-07 — centro de mando administrativo, publicación acotada

Objetivo: una administración interna comprensible por departamento. Siete vistas,
jerarquía sin emoticonos, búsqueda por identidad y teléfono, ficha por tareas,
menú móvil plegable, recarga real y fuentes/períodos explícitos. Consumo observado
por cuenta/proveedor/modelo con API administrativa auditada y coste no conocido
separado de cero; hipótesis USD/EUR configurable, no contable.

Áreas: templates admin, admin-workspace CSS/JS, router admin, consultas de consumo
en db, config y versionado de recursos. No cambia permisos, facturación, pagos,
WhatsApp, esquema ni copias. Los candidatos locales anteriores no forman parte
de esta publicación. QA exacta y límites en `Admin-centro-mando-release.md`.
Riesgo: regresión visual/consulta; rollback mediante revert del commit de este
panel, sin migraciones. Diagnóstico: /admin, /admin/cuentas/{id}, consola y
/admin/cuentas/{id}/consumo; comprobar período, cobertura y versión de recursos.

## 2026-09-07 — organización del administrador (local)

- Seis departamentos y seis vistas por cuenta; navegación activa, contexto, foco
  y diseño adaptable. Conserva formularios, permisos y enlaces anteriores.
- Archivos: admin.html, admin_account.html, admin_navigation.html, admin-workspace.css/js,
  deps.py; db.py/invoicing.py añaden paginación opcional y filtro SQL del portal;
  config.py parametriza la conversión de costes estimados sin afectar cobros.
- QA: Registro-QA y capturas `qa/admin-2026-09-07/`. Sin producción ni migraciones.
- Riesgo: ocultación progresiva y filtros opcionales. Sin JS todos visibles;
  revertir solo este diff para rollback. Candidato previo conservado, no push/deploy.
- Commit de teléfono del socio no localizado tras fetch; base remota sigue f8df1bc.

## 2026-09-07 — móvil, consumo y diagnóstico por cuenta (local)

- CSS/JS: contraste, superficie opaca, cierre y foco. Admin/DB: teléfono del titular,
  consumo mensual por negocio/proveedor/modelo y JSON privado auditado sin caché.
- Extracción: telemetría fail-open; WhatsApp: tipo aplicado y revisión conservadora.
- QA/límites: `Registro-QA.md` y `Revision-frentes-2026-09-07.md`.
- Riesgo: aditivo, sin migración ni nuevas autorizaciones; no emisión automática.
  Diagnóstico por cuenta/mes; rollback selectivo conservando el candidato anterior.
  Sin commit, push ni despliegue.

## 2026-09-06 — calculadora offline y presupuesto de copias

- `scripts/estimate_backup_cost.py`, cuatro pruebas y guía de costes: tarifas
  S3 Irlanda y salida Railway verificadas; crecimiento sin borrado explícito.
- QA: 4/4 dirigidas, CLI y Ruff correctos. No se repite suite general (última 653).
- Sin cambios de runtime, migraciones, producción, cuentas ni credenciales.
  Tamaño real y multipart pendientes. Rollback: retirar herramienta y guía;
  no hay datos que migrar ni borrado automático. Sin commit/push/despliegue.

## 2026-09-06 — recuperación y prevención de resultados parciales, sin publicar

- Objetivo autorizado: reforzar seguridad/fiabilidad; sin push ni despliegue.
- Áreas: backups emparejados, evidencia externa/CISO, filtro de eventos, checksum
  S3/Host/HTTPS/cifrado, extracción múltiple y aviso WhatsApp, diagnósticos Brevo/Meta,
  plantilla AWS privada. Pruebas y límites en QA del 6-sep.
- Límites: sin cuenta AWS ni datos enviados; voz, Meta real, Stripe y restauración
  externa pendientes. No se cambian permisos ni confirmaciones, ni esquema 55.
- Rollback: volver a f8df1bce conserva datos/copias. Crear juego nuevo al publicar;
  históricos con marcas distintas necesitan pareja explícita, nunca borrarlos o
  renombrarlos por suposición. CloudFormation no se ejecuta automáticamente y el
  plazo de retención no tiene valor por defecto. No borrar buckets como rollback.
- Hallazgo de QA adicional: scheduler sobrevivía al cierre de la app de prueba.
  `server.py`/`scheduler.py` añaden cierre ordenado, esperando trabajos en curso.
- Resultado final: 653/653 tests, migraciones SQLite 55→0→55, Ruff, Bandit y
  detección de secretos correctos; sin vulnerabilidades conocidas en dependencias
  instaladas según pip-audit. Sin validación PostgreSQL/CloudFormation real.

## 2026-09-04 — copia verificada y publicación autorizada del esquema 55

- **Autorización:** el founder solicita copia y publicación después del CI verde.
- **Backup real previo (esquema 53):** `noesis-20260904-090824-601912.dump.gz`
  (123.805 bytes) y `noesis-20260904-090829-568655.docs.zip` (82.060 bytes).
  Creación validada y segundo simulacro de restauración correcto en 3,854 s.
  Copia fijada fuera de rotación en `/data/backups/predeploy-schema55-20260904`.
- **Publicación:** fast-forward a main de `4f5e88f`; Railway
  `56d18ded-993c-4aa8-96d1-a623a8d75c79` termina SUCCESS. `/ready` devuelve
  esquema 55 y release `4f5e88f071cd`; 14 páginas/8 cabeceras correctas.
- **Regresión real:** demo autónomo (Inicio, Ajustes, Suscripción, Facturas,
  Documentos) y gestoría en 200; admin inaccesible para la demo normal. Recuentos
  antes/después idénticos: 9 negocios, 9 usuarios, 19 clientes, 24 facturas,
  24 líneas y 2 fichajes. Auditoría íntegra; alta y ambos flags WUB false.
- **Límites/rollback:** copia dentro de Railway, no offsite. No se ha probado una
  baja real ni enviado avisos nuevos. Para regresión, volver primero al código
  d3740a0 sobre BD 55; no borrar tablas nuevas con solicitudes reales. El cierre
  documental no modifica código, dependencias, workflow ni configuración externa.

## 2026-09-04 — puerta de revisión aislada, sin despliegue

- **Cierre:** CI `33855910788` correcto: 629 pruebas en 275,502 s, migraciones,
  PostgreSQL, restauración y rollback código/BD. Se actualizan estado, pendientes,
  despliegue e informe [[Revision-pre-main-2026-09-04]]. El commit de cierre es
  exclusivamente documental; el runtime sigue siendo el probado en `fbfa76b`.
- **Decisión:** técnicamente apto para despliegue controlado tras autorización y
  copia reciente verificada. Altas y WUB siguen apagados; revisiones jurídicas,
  pruebas reales e infraestructura de backup externa no se dan por resueltas.

- **PostgreSQL completo correcto:** ejecución `33855685663` valida migraciones,
  humo, backup/restauración, código anterior sobre esquema nuevo y privacidad.
  Se documenta como público el SHA fijo del checkout anterior para el escáner;
  el resto del CI se repite sin excepciones nuevas sobre código o dependencias.

- **Recuento verificado:** suite completa local 627/627 en 642,162 s, más dos
  contratos nuevos de proveedor. Se corrige la foto a 629 y la aserción del humo
  al rechazo real del POST administrativo (303 a login, sin cambio de permisos).

- **Rollback código primero:** se añade prueba explícita con el código base
  d3740a0 (esquema 53) sobre BD efímera 55 antes de bajar tablas; recorre cliente,
  emisión, cobro y exportación. Sin checkout ni comandos en producción.

- **Proveedor efectivo:** la lectura detectó SMTP residual junto a Brevo. El
  adaptador siempre utiliza Brevo cuando hay API key y no cae a SMTP tras error.
  Se alinea la puerta legal y su contexto con esa prioridad: ya no exige datos de
  un SMTP sin uso ni atribuye a Brevo la región de otro proveedor. Dos regresiones
  nuevas pasan; SMTP efectivo continúa exigiendo nombre y región. Sin cambios
  al envío ni a variables externas. Revertible con este commit.

- **Segunda iteración:** el escáner detectó NIF/contraseña sintéticos y huellas del
  manifiesto de branding. Se cotejaron las 49 huellas con sus archivos y se
  registran solo esos valores como falsos positivos, sin excluir archivos ni
  desactivar detectores. El humo usa los estados reales enviada/parcial/cobrada.
- **Configuración:** consulta de solo lectura al control plane de Railway, sin
  imprimir secretos ni acceder a datos: altas cerradas, flags WUB ausentes (false),
  S3 sin configurar, Brevo activo y SMTP presente sin metadatos legales.

- **Hallazgo del primer CI:** tres avisos de seguridad en pypdf 6.15.0
  (CVE-2026-84309/84310/84311). Se eleva el mínimo a 6.16.1 y se regenera únicamente
  su entrada del lock. El nuevo test PostgreSQL necesitaba `fetchall()` para el
  cursor del adaptador; se corrige el test, no el adaptador. Revalidación pendiente.

- **Objetivo:** verificar el candidato de valor/RGPD antes de decidir su publicación.
- **Áreas:** CI admite ejecución manual por rama; nuevo humo PostgreSQL exclusivo
  de `localhost/noesis_ci` prueba rollback 55→54→53→54→55 con datos históricos,
  inmutabilidad fiscal, baja HTTP, permisos, concurrencia, exportación y avisos.
- **Pruebas:** Ruff y verdad del proyecto correctos; suite completa y CI en curso.
- **Límites:** sin producción, credenciales de servicios ni envíos reales. No se
  crea PR para evitar previews automáticas. Solo rama de revisión.
- **Riesgo/rollback:** no cambia el runtime. El humo descarta tablas nuevas solo en
  la base efímera del CI; se rechaza cualquier host remoto o nombre de BD distinto.
  Revertir este commit retira únicamente esta puerta y sus notas.

Bitácora cronológica obligatoria de modificaciones del repositorio. Su objetivo es
permitir responder rápido a cuatro preguntas cuando algo falla: **qué cambió, qué
área puede haberlo causado, cómo se verificó y cómo se puede aislar o revertir**.

No sustituye `Registro-QA.md` (evidencia detallada), `Estado-actual-main.md`
(fotografía del producto) ni Git (diff exacto). Los conecta.

## 2026-09-08 — guía de Facebook en HTML y todo junto en `facebook/`

- **Autor/agente:** Claude, a petición del founder.
- **Objetivo:** poder leer la guía de conexión con comodidad y tener la
  automatización, su manual y su guía en un único sitio.
- **Áreas y archivos:** `facebook/Conectar-Facebook.html` (nuevo) y traslado de
  `docs/Conectar-Facebook.md` a `facebook/Conectar-Facebook.md`. Enlaces
  actualizados en `docs/Inicio.md` y `facebook/README.md`. No toca `src/noesis/`.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** comprobación de que el HTML está bien formado (sin
  etiquetas sin cerrar), revisión de que no queda ningún enlace a la ruta anterior
  y las 22 pruebas de `tests/test_facebook.py`.
- **Dependencias o validaciones externas:** ninguna. El HTML es autocontenido: sin
  CDNs, sin JavaScript y sin fuentes externas, con el mismo sistema visual que
  `Conectar-Correo.html` y `Conectar-Google.html`, incluidos modo oscuro y estilos
  de impresión. No se genera PDF: se obtiene imprimiendo desde el navegador.
- **Riesgo/punto probable de fallo:** el índice del vault enlaza ahora fuera de
  `docs/`, así que en Obsidian es un enlace relativo y no un enlace wiki. Si se
  vuelve a mover la carpeta, hay que revisar ese enlace y los dos del README.
- **Diagnóstico y rollback:** documental; revertir el commit devuelve la guía a
  `docs/` y borra el HTML.
- **Estado de publicación:** en `main`.

## 2026-09-08 — guía de conexión de Facebook y carpeta propia

- **Autor/agente:** Claude, a petición del founder.
- **Objetivo:** el founder no entendió cómo se conecta la automatización siguiendo
  solo el README técnico, así que se escribe una guía que explica el porqué de cada
  paso —sobre todo por qué hacen falta dos tokens, que es donde se atasca—. Además
  la automatización pasa de `marketing/facebook/` a `facebook/` en la raíz, porque
  `marketing/` no contenía nada más.
- **Áreas y archivos:** `docs/Conectar-Facebook.md` (nuevo), movimiento de
  `marketing/facebook/` a `facebook/` y de `tests/test_marketing_facebook.py` a
  `tests/test_facebook.py`, y actualización de todas las rutas en los dos
  workflows, `.env.example`, `AGENTS.md`, `branding/redes-sociales/README.md`,
  `docs/Tareas-vivas.md`, el README de la automatización y sus cuatro scripts. No
  toca `src/noesis/`.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** las 22 pruebas de `tests/test_facebook.py` desde la ruta
  nueva, `ruff check` sobre `facebook/` y el test, simulacro real
  (`python facebook/publicar.py --simulacro`) y revisión de que no queda ninguna
  referencia a `marketing/facebook` fuera de las entradas históricas de esta
  bitácora, que no se reescriben.
- **Dependencias o validaciones externas:** ninguna nueva. La guía describe
  pantallas de developers.facebook.com que Meta renombra cada pocos meses; el
  documento avisa de ello y describe la secuencia, no las palabras exactas.
- **Riesgo/punto probable de fallo:** los dos workflows invocan la ruta nueva. Si
  alguno hubiera quedado apuntando a `marketing/facebook/`, la publicación fallaría
  en silencio hasta el informe del domingo; por eso se han comprobado los dos.
- **Diagnóstico y rollback:** el movimiento es un `git mv` sin cambios de lógica;
  revertir el commit devuelve la carpeta a su sitio.
- **Estado de publicación:** en `main`. La automatización sigue en pausa hasta que
  existan los secretos `FACEBOOK_PAGE_ID` y `FACEBOOK_PAGE_TOKEN`.

## 2026-09-08 — foto técnica del almacenamiento y las copias

- **Autor/agente:** Claude.
- **Objetivo:** dejar escrito cómo está estructurado el almacenamiento hoy (base,
  volumen y copias), qué hace exactamente `backups.py` paso a paso, y los puntos
  débiles encontrados al leer el código. Complementa la carpeta de cumplimiento,
  que decide el «debería»; este documento describe el «es».
- **Áreas y archivos:** `docs/Almacenamiento-y-copias.md` (nuevo) y enlace desde
  `docs/Inicio.md`. No toca `src/noesis/`.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** lectura del código citado; cada afirmación del documento
  apunta a archivo y línea. Sin cambios ejecutables que probar.
- **Dependencias o validaciones externas:** los hallazgos 1 y 2 se verifican en el
  panel de Railway (a qué apuntan `NOESIS_DOCS_PATH` y `NOESIS_BACKUP_DIR`, y dónde
  está montado el volumen). No se ha podido comprobar desde aquí.
- **Riesgo/punto probable de fallo:** el documento afirma que `.env.example`
  documenta `NOESIS_BACKUP_DIR=/backups`, fuera del volumen `/data`. Si el panel ya
  tiene un valor correcto, el riesgo es solo documental; si se copió tal cual, las
  copias se pierden en cada despliegue. Los arreglos 1-3 y 6 no están aplicados
  todavía: el documento los describe, no los corrige.
- **Diagnóstico y rollback:** documental y aislado; borrar el archivo y el enlace.
- **Estado de publicación:** en el árbol de trabajo, sin commit.

## 2026-09-08 — plan de datos, servidores y copias, y carpeta de cumplimiento

- **Autor/agente:** Claude.
- **Objetivo:** responder por escrito a dónde se almacena cada dato, en qué
  servidores y cómo se hacen las copias, con la legislación europea aplicada, y
  dejar montada la estructura documental de cumplimiento que hoy no existía
  (registro del art. 30, retención, subencargados, brechas, derechos y
  continuidad). El detonante: las copias viven en el mismo proveedor que produce
  los datos y nunca se ha restaurado fuera de él.
- **Áreas y archivos:** carpeta nueva `docs/cumplimiento/` (índice, plan de datos y
  copias, RAT, política de retención, subencargados y transferencias, análisis de
  riesgos con cribado de EIPD, procedimiento de brechas, derechos, continuidad con
  RPO/RTO, registro de evidencias y cuatro plantillas), prompt reutilizable en
  `docs/prompts/Prompt-Seguridad-Datos-UE.md`, verificador
  `scripts/check_cumplimiento.py` y enlaces desde `docs/Inicio.md` y
  `docs/Tareas-vivas.md`. **No toca `src/noesis/`**: es documentación y una
  comprobación de higiene documental.
- **Cambios de datos/migración:** ninguno. Sin esquema, sin variables nuevas y sin
  efecto en el despliegue.
- **Pruebas ejecutadas:** `python scripts/check_cumplimiento.py` (estructura
  completa, fechas de revisión válidas, un aviso esperado por no haber simulacro
  externo todavía) y `ruff check` sobre el script.
- **Dependencias o validaciones externas:** el plan describe seis acciones P0 que
  se ejecutan **en el proveedor**, no en el repositorio: bucket externo en un
  segundo proveedor europeo con credencial de solo escritura, versionado y bloqueo
  de objetos, cifrado en cliente de las copias, primer simulacro de restauración
  externa cronometrado, región UE y retención de logs, y firma de los DPA. Siguen
  pendientes la revisión jurídica y el pentest independiente.
- **Riesgo/punto probable de fallo:** riesgo de que la documentación se
  desincronice de las páginas legales publicadas (`privacidad`, `cookies`,
  `encargado-tratamiento`): si se añade un subencargado en un sitio y no en el
  otro, el cliente puede alegar que no fue informado. El verificador detecta
  documentos sin revisar, no divergencias de contenido.
- **Diagnóstico y rollback:** todo el cambio es documental y aislado en
  `docs/cumplimiento/`, `docs/prompts/` y un script. Para revertir, borrar esas
  rutas; nada del producto depende de ellas.
- **Estado de publicación:** en el árbol de trabajo, sin commit ni despliegue. No
  afecta a lo desplegado.

## 2026-09-08 — publicación automática en Facebook cada 3 días

- **Autor/agente:** Claude.
- **Objetivo:** que la página de Facebook publique sola una pieza cada 3 días y que
  la única intervención humana sea leer un informe el domingo. Sustituye la
  publicación manual, que no se estaba haciendo con regularidad.
- **Áreas y archivos:** carpeta nueva `marketing/facebook/` (`calendario.json` con 48
  piezas, `nucleo.py`, `publicar.py`, `revision.py`, `conectar.py` y `README.md`),
  workflows `.github/workflows/facebook-publicar.yml` (diario, publica solo si el día
  cae en la cadencia) y `.github/workflows/facebook-revision.yml` (domingos, abre la
  incidencia de revisión), pruebas `tests/test_marketing_facebook.py` y bloque de
  variables de Facebook en `.env.example`. No toca `src/noesis/`: es promoción de
  Noesis, no producto.
- **Cambios de datos/migración:** ninguno. No hay estado persistido: la verdad es lo
  publicado en la página, que se consulta antes de escribir. Por eso la automatización
  no hace commits y no dispara despliegues de Railway.
- **Pruebas ejecutadas:** 22 pruebas nuevas en `tests/test_marketing_facebook.py`
  (cadencia de 3 días, rotación del calendario, antiduplicados, recuperación de una
  publicación fallida, pausa sin credenciales, error de Meta e informe semanal) más la
  suite completa; `ruff` sobre `tests` y `marketing`; simulacros del publicador y del
  informe desde este ordenador. Sin credenciales reales de Meta, la publicación
  efectiva no se ha podido validar contra Facebook.
- **Dependencias o validaciones externas:** Graph API de Meta con un token de página
  (`FACEBOOK_PAGE_ID` y `FACEBOOK_PAGE_TOKEN` como secretos del repositorio) y GitHub
  Actions programado. Solo biblioteca estándar: el workflow no instala dependencias.
- **Riesgo/punto probable de fallo:** token de página revocado o caducado (error 190),
  permisos incompletos en el token (error 200) o bloqueo temporal de la página por
  parte de Meta (error 368). Mientras falten los secretos la automatización queda en
  pausa sin fallar, y el informe del domingo avisa. Riesgo editorial: el calendario da
  la vuelta a los 144 días; el informe avisa varias semanas antes.
- **Diagnóstico y rollback:** cada ejecución deja resumen en la pestaña de Actions y
  el informe del domingo compara calendario contra página real. Para pararlo todo,
  deshabilitar los dos workflows desde Actions; para pararlo sin tocar GitHub, borrar
  el secreto `FACEBOOK_PAGE_TOKEN`. Ningún cambio afecta al producto desplegado.
- **Estado de publicación:** código en `main`. La automatización no publicará nada
  hasta que se creen los secretos de la página siguiendo `marketing/facebook/README.md`.

## 2026-09-02 — piezas de presentación e índice navegable en el manual editorial

- **Autor/agente:** Claude.
- **Objetivo:** dar guion a las dos primeras piezas que se van a grabar —quiénes son
  los socios y qué es Noesis— para que el perfil pueda explicarse antes de pedir
  nada, y hacer navegable un manual que ya pasa de cuarenta páginas.
- **Áreas y archivos:** `branding/contenido/scripts/build_content_playbook.py` (fichas
  nuevas `T00` y `P00`, grupo «Presentación» en el mapa, recuentos calculados, nota de
  calendario, página «Cómo usar este manual» y columna de ficha en el mapa) y su salida
  `branding/contenido/Plan-editorial-y-guiones-Noesis.docx`, versión 1.1 con 26 fichas.
  `T00` y `P00` abren el documento y se publican y fijan antes de la Semana 1.
- **Cambios de datos/migración:** ninguno. No cambia producto, runtime ni base de datos.
- **Pruebas ejecutadas:** regeneración del DOCX desde el generador; verificado que las
  piezas nuevas son «FICHA 01 DE 26» y «FICHA 02 DE 26», que el mapa declara 26 piezas
  y numera cada una con su ficha, que el índice lista las once partes y que las 24
  fichas anteriores conservan su contenido.
- **Dependencias o validaciones externas:** el guion usa la biografía pública de
  `site_equipo.html`; si cambia el papel de un socio hay que rehacer la ficha. La
  pieza se graba y se publica fuera del repositorio.
- **Riesgo/punto probable de fallo:** que al grabar se añadan cifras, clientes o
  resultados que todavía no existen, o que `P00` enseñe WhatsApp como disponible; los
  guardarraíles de ambas fichas lo prohíben y obligan a rotular «demo» y «piloto».
- **Diagnóstico y rollback:** el generador reconstruye el documento; revertir este
  commit deja el manual en la versión 1.0 con 24 fichas y sin índice.
- **Límites externos:** `P00` describe el flujo de WhatsApp, cuya validación real con
  Meta sigue pendiente según `docs/project-state.json`; hasta entonces solo puede
  mostrarse rotulado como piloto.
- **Estado de publicación:** guion listo para rodar; no implica que la pieza se haya
  grabado ni publicado.
## 2026-09-05 — la marca pasa de «Noesis» a «Bynoesis»

- **Autor/agente:** Claude, a petición del founder.
- **Objetivo:** el producto se llama Bynoesis. Unificar el nombre en todo lo que ve
  una persona, sin tocar lo que rompería producción.
- **Qué se ha renombrado:** 1.159 apariciones de `Noesis` como palabra suelta en 196
  ficheros —plantillas HTML, textos del asistente, correos, documentación y marca—,
  con `Noesis`, que por construcción no toca ningún identificador técnico.
  Además se renombran seis ficheros cuyo nombre llevaba la marca (`Estado-Bynoesis.xlsx`,
  `Marketing-Bynoesis.*`, `Bynoesis-Modelo-Economico.xlsx`, `Plan-maestro-Bynoesis.md`,
  y dos de `branding/`), porque las referencias ya apuntaban al nombre nuevo y habrían
  quedado rotas.
- **Qué NO se ha renombrado, y por qué.** Renombrarlo habría tumbado producción:
  - **Las 96 variables `NOESIS_*`** están puestas en Railway. Cambiarlas en el código
    deja el servidor sin clave de sesión, sin URL base, sin número de WhatsApp y sin
    identidad Veri*Factu **a la vez**.
  - **El paquete `noesis` y sus 409 imports.** `Procfile` y `railway.json` arrancan
    `noesis.web.server` y ejecutan `noesis.migrations`; renombrarlo impide el arranque.
  - **Las entradas de comando** `noesis-doctor`, `noesis-web`, y los ficheros estáticos
    `noesis-mark.svg` y compañía, referenciados por nombre.
- **Sí renombrado con cuidado:** las **nueve plantillas de Meta** pasan a `bynoesis_*`.
  Se comprobó antes que ninguna está dada de alta (9 de 9 ausentes), así que hoy es
  gratis; mañana obligaría a crearlas dos veces. **Hay que actualizar las variables
  `WHATSAPP_TEMPLATE_*` en Railway**, o borrarlas para que valgan los valores por defecto.
- **Compatibilidad de la palabra de vinculación.** El mensaje que se genera dice ya
  `BYNOESIS <código>`, pero `_try_link` y `_try_worker_link` **siguen aceptando
  `NOESIS`**: quien tenga a mano una captura o unas instrucciones antiguas no puede
  quedarse sin poder vincular. Igual en el patrón del centro de control del cerebro
  local, que acepta «permisos de noesis» y «permisos de bynoesis».
- **Valores que viajan fuera y han cambiado:** `SMTP_FROM`,
  `NOESIS_VERIFACTU_PRODUCER_NAME` y `NOESIS_VERIFACTU_SYSTEM_NAME` pasan a Bynoesis.
  Los dos últimos se graban en cada registro Veri*Factu; el entorno sigue en `pruebas`
  y no hay remisión real, así que el momento de cambiarlos es ahora. **Hay que
  actualizarlos también en Railway.**
- **Pruebas ejecutadas:** `ruff` limpio en `src`, `tests` y `scripts`; el módulo importa
  y resuelve los nombres nuevos. **Batería completa: 639 pasan, 1 falla** —
  `test_clamav_protocol_clean_and_malware`, con el `PermissionError` de `tempfile`
  en Windows al borrar el temporal; pasa aislada, así que no es del renombrado.
  Además, 56 pruebas de páginas, SEO, plataforma, configuración de release y
  readiness en verde, que son las que romperían si un texto visible hubiera quedado
  descuadrado. Prueba nueva
  `test_linking_accepts_the_old_keyword_after_the_rename` que fija que las dos palabras
  vinculan y que cualquier otra no.
- **Riesgo/punto probable de fallo:** el despliegue no cambia de comportamiento porque
  ninguna variable de entorno ni ruta de módulo se ha tocado. El riesgo real está en
  las tres variables de Railway que hay que actualizar a mano (`WHATSAPP_TEMPLATE_*`,
  `SMTP_FROM` y los dos de Veri*Factu). Si no se hacen, el remitente del correo y la
  identidad Veri*Factu seguirán diciendo «Noesis».
- **Logo:** se archiva `branding/logos/bynoesis-logo-lockup.jpg` (1934×544), el lockup
  con la marca nueva que entregó el founder. Los PNG antiguos de `branding/logos/png/`
  conservan su nombre: son binarios referenciados por ruta y renombrarlos rompería
  los enlaces sin ganar nada.
- **Diagnóstico y rollback:** `git revert` del commit devuelve el nombre anterior; los
  renombrados de fichero vuelven con él.
- **Estado de publicación:** desplegable. No cambia esquema ni datos.

## 2026-09-04 — revisión de los siete frentes abiertos

- **Autor/agente:** Claude, a petición del founder.
- **Objetivo:** reunir en un solo documento lo que hoy no funciona del todo —voz, copias,
  RGPD, teléfono del cliente, latencia, permisos de administración y Cal.com—, con la
  causa verificada de cada cosa y qué hacer, más una revisión de código.
- **Áreas y archivos:** `docs/Frentes-abiertos.html` (nuevo). Sin cambios en `src/`.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** ninguna del producto; es documentación. Todo lo afirmado se
  contrastó contra el código o contra producción antes de escribirlo.
- **Correcciones a documentos anteriores.** Dos afirmaciones de los informes de RGPD ya no
  son ciertas y el documento lo dice: (1) **el iframe de Cal.com ya no existe** y la CSP es
  `frame-src 'none'` en todas las páginas, así que el hallazgo A2 está cerrado; (2) los
  proveedores sí se declaran solos —verificado en vivo: al configurar `ANTHROPIC_API_KEY`
  su fila apareció en `/privacidad` sin tocar ningún texto.
- **Hallazgos nuevos de la revisión:** `whatsapp.py` usa el `kind` crudo de la propuesta en
  vez de `applied_kind`, así que con confianza baja el móvil ofrece registrar una factura
  que la web guarda como documento sin clasificar; el patrón `except Exception` que devuelve
  la heurística sigue en extracción de gastos y borrador de factura, donde un fallo de la IA
  es indistinguible de una duda; el asistente no ve los documentos de la conversación; y la
  batería tarda 38 minutos, que es la razón real por la que no se ejecuta antes de publicar.
- **Dependencias o validaciones externas:** el documento fija cinco preguntas concretas para
  el abogado y la lista de DPA por archivar.
- **Riesgo/punto probable de fallo:** ninguno; no toca producción.
- **Diagnóstico y rollback:** borrar el archivo revierte el cambio entero.
- **Estado de publicación:** publicado también como artefacto para poder consultarlo fuera
  del repositorio. La fuente sigue siendo este archivo.

## 2026-09-04 — un PDF con varias facturas dejaba de clasificarse

- **Autor/agente:** Claude, siguiendo la prueba real del founder.
- **Objetivo:** su PDF de 3 páginas quedaba «sin poder decidir el tipo» mientras que
  uno de 1 página se clasificaba perfecto. Parecía que el sistema «se quedaba
  atascado tras un error»; no lo estaba.
- **Causa:** un documento con varias facturas dentro se contesta como **lista** de
  objetos JSON. `_json_object` recortaba desde la primera `{` hasta la última `}`, y
  con dos o más objetos eso deja comas sueltas y deja de ser JSON válido. La
  respuesta del modelo —correcta, `factura_recibida` con confianza 95— se tiraba, se
  caía a la heurística y el usuario leía «no consigo decidir el tipo». El `except`
  solo registraba el nombre del tipo de excepción, así que un fallo de interpretación
  era indistinguible de una IA dudando: por eso costó encontrarlo.
- **Áreas y archivos:** `src/noesis/adapters/extraction.py` (`_json_object` acepta
  listas y hay un aviso propio cuando la IA responde y no se la entiende),
  `tests/test_backend.py`, `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migración:** ninguno; esquema 55 sin tocar.
- **Pruebas ejecutadas:** medición contra el modelo real con un PDF de tres facturas:
  **0 aciertos de 6 antes, 5 de 5 después**. Prueba nueva verificada por
  contradicción (con el código anterior falla con «una lista de objetos no puede
  descartarse»). 37 pruebas de OCR, facturas recibidas, correo entrante, multicanal
  y adaptador de facturación en verde. Total recolectado 639.
- **Dependencias o validaciones externas:** el arreglo se validó con llamadas reales
  a `claude-haiku-4-5-20251001`, el clasificador configurado.
- **Riesgo/punto probable de fallo:** `_json_object` lo usan también el borrador de
  factura y la extracción de gasto. Ahora intenta primero el texto entero y solo
  recorta si eso falla, así que acepta estrictamente más de lo que aceptaba; una
  lista sin objetos sigue devolviendo `None` y la prueba lo fija.
- **Diagnóstico y rollback:** `pytest -k model_answer_with_several_invoices`.
- **Estado de publicación:** desplegable. **Queda pendiente**, y es el mismo PDF que
  lo destapó: cuando el titular escribe «súbela» refiriéndose a un documento que
  acaba de mandar, el asistente no ve ese documento y le pide cliente, importe y
  concepto como si fuera a crear una factura nueva. El asistente y los documentos no
  comparten contexto.

## 2026-09-04 — reenviar un documento ya no es un callejón sin salida

- **Autor/agente:** Claude, tras probar el founder el canal real con una factura.
- **Objetivo:** el founder subió un PDF cuando aún no había IA configurada, se archivó
  sin clasificar, y al reenviarlo con la IA ya puesta el sistema contestaba «Este
  archivo ya estaba guardado como documento 8» y se paraba. **No había ninguna forma
  de volver a clasificar por WhatsApp un documento ya archivado.**
- **Causa:** `DuplicateDocument` hereda de `UploadError`, y el manejador de entrada
  trataba todos los `UploadError` igual: mandar el texto del error y salir. El
  duplicado no es un error del usuario, es una petición de releer.
- **Áreas y archivos:** `src/noesis/documents/service.py` (nueva `reclassify`),
  `src/noesis/web/whatsapp.py` (rama propia para `DuplicateDocument` y mensajes que
  dicen que el papel ya estaba archivado), `tests/test_backend.py`,
  `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migración:** ninguno; esquema 55 sin tocar. El reenvío **no crea
  una fila nueva**: reutiliza el documento existente.
- **Pruebas ejecutadas:** `ruff` limpio; prueba nueva
  `test_resending_a_stored_pdf_reclassifies_it_instead_of_dead_ending` en verde y
  verificada por contradicción (con el código anterior falla con
  `KeyError: 'already_stored'`); 36 pruebas de `test_showcase_and_pdf_ocr`,
  `test_received_invoices`, `test_inbound_email` y `test_whatsapp_multichannel` en
  verde. Total recolectado 638.
- **Límite asumido, a petición expresa del founder:** se publica **sin esperar** a que
  termine `tests/test_backend.py` completo, que estaba corriendo. Se planteó la
  objeción —este es el camino por el que entran todos los documentos— y el founder
  pidió subirlo igual. Si la batería completa saca algo, se corrige encima.
- **Riesgo/punto probable de fallo:** `already_stored` se fija en las dos ramas del
  `try`; si alguien añade una tercera salida sin fijarlo, saltará `KeyError` en el
  envío. La prueba nueva lo cubre.
- **Diagnóstico y rollback:** `pytest -k resending_a_stored_pdf`. Revertir el commit
  devuelve el comportamiento anterior, que dejaba el documento inalcanzable.
- **Estado de publicación:** desplegable. No cambia esquema ni datos.

## 2026-09-04 — el trimestre fiscal deja de releer las tablas por cada trimestre

- **Autor/agente:** Claude, a petición del founder («el panel va muy lento»).
- **Objetivo:** medir la lentitud del panel en vez de opinar, y atacar lo más caro.
- **Áreas y archivos:** `src/noesis/db.py` (`tax_quarter` se parte en una carga
  pública y `_tax_quarter_from`, que recibe los datos ya leídos),
  `scripts/profile_panel.py` (nuevo medidor), `tests/test_backend.py`,
  `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migración:** ninguno; esquema 55 sin tocar. Solo lectura.
- **Pruebas ejecutadas:** las 27 fiscales en verde, `tests/test_backend.py`,
  `test_invoicing_adapter.py` y `test_received_invoices.py` completos. Total
  recolectado 637. **Comparación de cifras antes/después con facturas y gastos
  repartidos por los cuatro trimestres y tipos de IVA e IRPF distintos: idénticas
  al céntimo en ingresos, IVA repercutido, soportado, resultado, IRPF del periodo
  y pagos previos.**
- **Medición:** con 400 facturas y 300 gastos, `tax_quarter(4T)` pasa de **281,6 ms
  a 38,8 ms** (mejor de 7). El 1T no cambia (35 ms) porque no tiene trimestres
  anteriores. En el panel, la pantalla de Impuestos baja de 34 a 25 consultas.
- **Dependencias o validaciones externas:** ninguna.
- **Riesgo/punto probable de fallo:** es código de dinero. El riesgo era que la
  recursión compartiera datos mal filtrados; por eso la comparación de cifras y una
  prueba nueva que fija **una lectura por tabla** sea cual sea el trimestre. Con el
  código anterior esa prueba falla con «list_invoices se leyó 8 veces».
- **Diagnóstico y rollback:** `python scripts/profile_panel.py` mide todas las
  pantallas; `pytest -k tax_quarter_reads_each_table_once` fija la mejora.
- **Estado de publicación:** desplegable. **Queda pendiente el patrón de fondo:**
  cada pantalla del panel hace 22-35 consultas y varias traen tablas enteras para
  filtrar en Python, así que al pasar de 60 a 250 clientes los tiempos se doblan
  aunque el número de consultas no cambie. Las siguientes peores son Ajustes
  (35 consultas, 62 KB de HTML) y Resumen. Medido en SQLite local: en producción
  con PostgreSQL cada consulta cruza además la red.

## 2026-09-04 — el asistente ya puede responder por el IVA y el IRPF

- **Autor/agente:** Claude, a petición del founder («si le pregunto cómo va mi IVA,
  ¿funcionará?»).
- **Objetivo:** que una pregunta fiscal por WhatsApp o por el chat se conteste con el
  cálculo real del trimestre en vez de con el resumen del mes.
- **Áreas y archivos:** `src/noesis/tools.py` (herramienta `ver_impuestos` y su
  despacho), `src/noesis/nlu.py` (patrón fiscal antes del de resumen y redacción de
  la respuesta), `tests/test_backend.py` (prueba nueva),
  `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migración:** ninguno; esquema 55 sin tocar. La herramienta solo
  lee: `db.tax_quarter` no escribe nada.
- **Pruebas ejecutadas:** `tests/test_backend.py` completo en verde (425 pruebas,
  0 fallos, 18 min), más cerebro interno, flujos de campo, plantillas de oficio y
  multicanal (30 pruebas). `ruff` limpio. Total recolectado 633.
- **Dependencias o validaciones externas:** ninguna. El cálculo ya existía y lo usan
  la web, la gestoría y el aviso trimestral; lo único nuevo es que el asistente
  llega a él.
- **Riesgo/punto probable de fallo:** el patrón fiscal se evalúa **antes** que el de
  resumen, porque «como va mi iva» casaba con los dos. Si alguien añade un patrón más
  arriba que capture `iva`, volverá a romperse; por eso la prueba fija que «factura a
  Pepe 500 euros iva 21» sigue creando una factura y «cuánto llevo facturado» sigue
  siendo el resumen del mes. La respuesta declara que son cifras de apoyo y que la
  gestoría valida la presentación, según la regla de oro 8.
- **Diagnóstico y rollback:** `pytest -k asking_about_vat`. Revertir el commit deja
  el comportamiento anterior, en el que la pregunta fiscal no tenía respuesta.
- **Estado de publicación:** desplegable. No cambia esquema ni datos.

## 2026-09-04 — la prueba de baja RGPD dependía del entorno del que la ejecuta

- **Autor/agente:** Claude.
- **Objetivo:** la batería completa daba 5 fallos sobre 629. Averiguar si eran del
  producto antes de subir nada.
- **Áreas y archivos:** `tests/test_backend.py`. Sin cambios en `src/`.
- **Cambios de datos/migración:** ninguno; esquema sin tocar.
- **Pruebas ejecutadas:** batería completa (624 pasan, 5 fallan, 37 min). Los cuatro
  fallos de `test_account_closure_with_legal_records_is_tracked_and_idempotent` se
  reproducen aislados y **no son del producto**: el test contaba los avisos por el
  prefijo `privacy-request-`, que casa a la vez con `privacy-request-user:` y con
  `privacy-request-admin:`. `account.py` encola los dos a propósito, y el segundo
  solo si hay `NOESIS_LEGAL_EMAIL` o `NOESIS_ADMIN_EMAIL`. Con un buzón interno
  configurado salían dos y el test exigía uno: pasaba en CI y fallaba en la máquina
  del founder. Ahora comprueba lo que quería comprobar —que reenviar la solicitud no
  duplica ningún aviso y que al titular le llega exactamente uno— y pasa con y sin
  buzón interno. El quinto,
  `test_whatsapp_multichannel::test_central_phone_cannot_mix_owner_and_worker_identities`,
  pasa aislado y con su archivo entero; en la tanda completa muere con
  `PermissionError` en `tempfile.py` al borrar un directorio temporal: es un bloqueo
  de archivos de Windows, no del código.
- **Dependencias o validaciones externas:** ninguna.
- **Riesgo/punto probable de fallo:** ninguno en producción; solo cambia una
  aserción de prueba. El aviso interno de privacidad seguía enviándose bien.
- **Diagnóstico y rollback:** `pytest -k test_account_closure` con y sin
  `NOESIS_ADMIN_EMAIL`. Antes fallaba con la variable puesta.
- **Estado de publicación:** batería verde salvo el bloqueo de ficheros de Windows,
  que no se reproduce fuera de la tanda completa. Queda por confirmar si en Linux
  desaparece.

## 2026-09-04 — el comprobador de WhatsApp valida firma y suscripción

- **Autor/agente:** Claude.
- **Objetivo:** cerrar la comprobación del canal sin depender de lo que se vea en la
  consola de Meta ni de un mensaje real. Quedaban dos incógnitas: si Meta llamaba de
  verdad a nuestra URL y si el `WHATSAPP_APP_SECRET` desplegado era el bueno.
- **Áreas y archivos:** `scripts/check_whatsapp.py`, `.env.example`
  (`WHATSAPP_WABA_ID`). Sin cambios en `src/`.
- **Cambios de datos/migración:** ninguno; esquema sin tocar.
- **Pruebas ejecutadas:** `ruff` en verde y ejecución real contra Meta y contra
  producción. **Resultado: todo verde salvo las nueve plantillas, que no están dadas
  de alta.** Verificado en `https://bynoesis.com`: webhook registrado y activo con
  `messages` suscrito, challenge correcto, verify token falso rechazado con 403,
  webhook firmado aceptado con 200 y firma falsa rechazada con 401.
- **Dependencias o validaciones externas:** el sobre firmado que manda el script no
  lleva eventos, así que atraviesa la verificación de firma sin crear ningún dato.
  Es la única forma de comprobar el secreto desplegado sin esperar a un mensaje real.
- **Riesgo/punto probable de fallo:** ninguno; el script no escribe en Meta ni en la
  base de datos. Un despliegue caído se ve como fallo de firma, no como caída.
- **Diagnóstico y rollback:** `python scripts/check_whatsapp.py`. Borrar el archivo
  revierte el cambio entero.
- **Estado de publicación:** el canal de entrada queda verificado de punta a punta.
  Falta el alta de las nueve plantillas y la conversación real con el número de
  prueba. Anotado que Meta sirve los campos en `v26.0` frente al `v23.0` del código.

## 2026-09-04 — comprobador del canal de WhatsApp contra Meta

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidió poder volver a probar el canal de Meta. No había
  forma de saber si las credenciales servían sin mandar un mensaje real, así que se
  añade un comprobador de solo lectura y se dejan localizados los dos bloqueos.
- **Áreas y archivos:** `scripts/check_whatsapp.py` (nuevo). Sin cambios en `src/`.
- **Cambios de datos/migración:** ninguno; esquema sin tocar.
- **Pruebas ejecutadas:** `ruff check scripts/check_whatsapp.py` en verde y ejecución
  real contra la Graph API y contra `https://bynoesis.com`. Detecta correctamente los
  tres fallos vigentes y devuelve código de salida 1.
- **Dependencias o validaciones externas:** **dos bloqueos confirmados con Meta.**
  (1) `WHATSAPP_TOKEN` caducó el 14-07-2026: hay que generar uno de usuario del
  sistema sin caducidad, con `whatsapp_business_messaging` y
  `whatsapp_business_management`. (2) El `WHATSAPP_VERIFY_TOKEN` del servidor no
  coincide con el de `.env`: la verificación GET del webhook devuelve 403, así que
  Meta hoy no puede suscribirlo. El rechazo de token falso sí funciona.
- **Riesgo/punto probable de fallo:** ninguno en producción; el script no escribe
  nada ni en Meta ni en la base de datos. Si Meta retira `v23.0`, todas las llamadas
  fallarán a la vez con el mismo error de versión.
- **Diagnóstico y rollback:** `python scripts/check_whatsapp.py`. Con `--sin-red`
  solo comprueba el webhook. Borrar el archivo revierte el cambio entero.
- **Ampliación del mismo día:** el comprobador lee ya la suscripción del webhook con
  el token de app (`app_id|app_secret`) y avisa si Meta sirve los campos en una
  versión distinta de `META_GRAPH_VERSION`. Se retira la consulta del campo
  `whatsapp_business_account_id` del número: no existe en la Graph API y siempre
  fallaba. El id de la WABA se pasa ahora con `--waba` o `WHATSAPP_WABA_ID`.
- **Resuelto:** token permanente de usuario del sistema en Railway y en `.env`,
  `WHATSAPP_VERIFY_TOKEN` igualado, y webhook `https://bynoesis.com/webhook/whatsapp`
  registrado y activo en Meta con el campo `messages` suscrito. El comprobador
  devuelve 0 fallos. Queda el alta de las nueve plantillas.
- **Aviso nuevo:** Meta sirve los campos del webhook en `v26.0` y el código pide
  `v23.0`. Funciona, pero hay que planificar la subida.
- **Estado de publicación:** las nueve plantillas ya encajan con sus envíos
  (`python -m noesis.whatsapp_templates` no reporta desajustes), así que el paso
  siguiente es token, verify token y alta de plantillas, en ese orden.

## 2026-09-03 — salida operativa RGPD, proveedores y baja trazable

- **Autor/agente:** Codex, a petición del founder tras la auditoría RGPD compartida.
- **Objetivo:** corregir afirmaciones públicas falsas y cerrar el callejón sin salida
  de una baja con conservación, sin inventar plazos ni ejecutar una purga automática.
- **Áreas y archivos:** esquema 55, operaciones RGPD en `db.py`, baja de cuenta,
  bandeja interna, Ajustes, contacto/CSP, privacidad, cookies, contrato de encargado,
  cumplimiento, configuración y diagnóstico de backups, pruebas y documentación
  interna de ROPA, proveedores, derechos y brechas.
- **Cambios de datos/migración:** nueva tabla multiempresa `privacy_requests` con
  tipo, estado, retención, referencia abierta idempotente, solicitante y fechas. No
  modifica tablas fiscales ni borra datos al cambiar el estado. El rollback 55→54
  elimina únicamente esta bandeja.
- **Comportamiento:** una cuenta sin registros protegidos conserva el borrado directo.
  Con facturas emitidas o jornada, se registra la solicitud, se devuelve referencia,
  se encolan avisos y se audita. Cal.com deja de cargarse en iframe; `frame-src`
  queda en `none`. La copia externa falla cerrada sin región, proveedor y residencia.
- **Pruebas ejecutadas:** 615 pruebas de regresión completas `OK`; después se
  añadieron y ejecutaron tres pruebas específicas del seguimiento desde
  administración, rollback 55→54→55 y concurrencia, también `OK` (618 verificadas
  en total). Ruff, compilación, JSON, verdad documental
  y `git diff --check` en verde.
- **Dependencias o validaciones externas:** DPA y regiones reales de Railway,
  contratos de proveedores, tabla de conservación, migración PostgreSQL 54→55→54,
  correo real, restauración S3, solicitud completa y simulacro de brecha.
- **Riesgo/punto probable de fallo:** tratar `completed` como borrado efectivo o
  activar S3/Groq sin contrato. La UI recuerda que el estado no borra; el destino S3
  falla cerrado y la purga sigue sin programarse.
- **Diagnóstico y rollback:** consultar `privacy_requests`, outbox y eventos
  `privacy.*`; ante regresión, volver al código anterior manteniendo esquema 55,
  validar flujos y solo después bajar 55→54. No borrar expedientes antes de exportar.
- **Estado de publicación:** cambio local; no se ha hecho push ni despliegue y no se
  ha ejecutado nada contra Railway o producción.

## 2026-09-01 — WUB solo mide delegación y el rollback respeta auditoría previa

- **Autor/agente:** Codex, tras revisión externa del commit `35ef41f`.
- **Objetivo:** corregir cinco observaciones sin rediseñar ni ampliar el Registro
  Interno de Valor: excluir formularios manuales de WUB, conservar auditoría previa
  con el flag apagado, hacer seguro el rollback, desplegar opt-in y declarar el
  lifecycle real.
- **Áreas y archivos:** `value_ledger.py`, esquema 53, validación de metadatos en
  `db.py`, flag en `config.py`, auditoría del scheduler, smoke PostgreSQL, pruebas
  del ledger y fecha estable del test de cohortes; documentación de despliegue,
  estado, decisión, arquitectura, propuesta, QA y operación.
- **Cambios de datos/migración:** `useful_actions` incorpora
  `qualifies_for_wub`, separado de la candidatura de taxonomía. `manual_form` y
  `automation` quedan como orígenes explícitos. El esquema sigue siendo 53 porque
  el candidato no se ha desplegado.
- **Pruebas ejecutadas:** 570/570; 20 contratos del ledger; cuatro reproducciones
  del test de cohortes; código `294ce375` sobre esquema 53; Ruff, compilación, JSON,
  verdad documental y diff check. Evidencia detallada en `Registro-QA.md`.
- **Dependencias o validaciones externas:** migración/smoke/rollback PostgreSQL en
  entorno no productivo y reconciliación con 3-5 negocios. Nada se ha ejecutado en
  Railway ni producción.
- **Riesgo/punto probable de fallo:** contexto incorrecto en un hook o downgrade de
  BD antes de retirar código 53. La decisión binaria central y la secuencia
  código-anterior-sobre-esquema-53 impiden ambos atajos.
- **Diagnóstico y rollback:** mantener ambos flags en `false`; para volver atrás,
  apagar ledger, restaurar código anterior con esquema 53, validar y solo entonces
  bajar 53→52. Nunca servir código 53 sobre esquema 52.
- **Estado de publicación:** candidato en rama de revisión; no fusionado ni
  desplegado.

## 2026-08-31 — base observacional de valor, WUB y confianza

- **Autor/agente:** Codex.
- **Objetivo:** implementar la base de Useful Actions, Useful Outcomes y WUB como
  capa aditiva, backward-compatible y auditable, sin gobernar ni alterar los
  flujos que observa.
- **Áreas y archivos:** esquema 53 en `migrations.py`; taxonomía, writers fail-open,
  outcomes, WUB y trust en `value_ledger.py`; hooks terminales en datos,
  documentos, herramientas, scheduler y WhatsApp; auditoría admin oculta; RGPD;
  smoke PostgreSQL; 17 pruebas; documentación de arquitectura, estado, pendientes,
  decisiones y QA.
- **Cambios de datos/migración:** cuatro tablas aisladas por `business_id`, zona
  horaria y elegibilidad en negocio y cuatro campos opcionales de correlación en
  `assistant_actions`. No se cambia ninguna tabla fiscal ni estado operativo. El
  rollback 53→52 elimina el ledger; SQLite conserva inertes las columnas aditivas.
- **Pruebas ejecutadas:** 567/567 pruebas, 17 contratos específicos, seguridad
  generativa, migración 53→52→53, lint Ruff, compilación, DDL PostgreSQL simulado,
  índice WUB, JSON, verdad documental y diff limpio. Evidencia en
  `Registro-QA.md`.
- **Dependencias o validaciones externas:** humo y rollback contra PostgreSQL real
  deben ejecutarse en un entorno no productivo. Después se reconcilia con 3-5
  negocios antes de mostrar métricas o fijar objetivos.
- **Riesgo/punto probable de fallo:** volumen de escritura o una taxonomía prematura.
  Las claves idempotentes e índices acotan duplicados/consultas; los errores se
  registran pero nunca bloquean la operación principal. No se copia contenido.
- **Diagnóstico y rollback:** poner `NOESIS_VALUE_LEDGER_ENABLED=false` detiene las
  escrituras; `NOESIS_VALUE_LEDGER_ADMIN_ENABLED=false` oculta auditoría. Revisar el
  log `noesis.value_ledger`. Si hace falta, bajar a 52 o revertir los hooks sin tocar
  facturas, cobros, clientes, agenda, documentos, presupuestos, WhatsApp o permisos.
- **Estado de publicación:** candidato completo y probado localmente; no desplegado.

## 2026-08-31 — propuesta integral de hábito, confianza, valor y retención

- **Autor/agente:** Codex.
- **Objetivo:** convertir las dos propuestas de retención y el acuerdo sobre WUB en
  un documento único, revisable por los socios y suficientemente preciso para
  separar decisiones de producto, instrumentación, experiencia y fases futuras.
- **Áreas y archivos:** `docs/Propuesta-sistema-retencion-habito-valor.md` y enlace
  desde `docs/Inicio.md`. Integra Registro Interno de Valor, Habit Engine, Trust
  Engine, Value Engine, WUB, Insight Engine, Progress Engine, Confidence aplazado,
  matriz de acciones, métricas, plan por fases, pruebas y puertas del piloto.
- **Cambios de datos/migración:** ninguno. Es una propuesta de dirección; no cambia
  producto, runtime, esquema, permisos ni automatizaciones.
- **Pruebas ejecutadas:** revisión estructural y de enlaces relativos;
  `git diff --check`; comprobación de verdad documental del proyecto.
- **Dependencias o validaciones externas:** los umbrales WUB, tiempos recuperados,
  atribución económica y relación con retención deben validarse con 3-5 negocios
  reales antes de convertirse en objetivos o mensajes comerciales.
- **Riesgo/punto probable de fallo:** interpretar la propuesta como funcionalidad ya
  publicada o intentar construir simultáneamente los cinco motores. El documento
  marca como primera secuencia Registro de Valor, Habit, Trust, Value y piloto.
- **Diagnóstico y rollback:** el encabezado identifica expresamente el estado de
  propuesta. Revertir este cambio retira solo documentación y no afecta datos ni
  producción.
- **Estado de publicación:** documento preparado para revisión y aprobación de
  socios; implementación todavía no autorizada.
## 2026-09-03 — refunde los documentos legales con `Ruta-legal` y corrige Meta

- **Autor/agente:** Claude.
- **Objetivo:** al fusionar con `origin/main` aparecieron 28 commits de otro agente,
  entre ellos `Ruta-legal.pdf` (29-ago), que solapaba con los documentos legales
  escritos hoy. Se refunden para que no queden dos rutas legales paralelas ni una
  contradicción publicada.
- **Áreas y archivos:** `docs/Constitucion-y-primer-euro.md` (recortado: los bloques
  C y D pasan a punteros y la sección del plan cede el calendario a
  `Plan-60-dias.pdf`), `docs/RGPD-estado-y-plan.md` y `docs/RGPD-QUE-HACER.md`
  (incorporan el hallazgo de Groq y se declaran complementarios de `Ruta-legal`),
  `docs/Inicio.md` y `docs/Tareas-vivas.md` (conflictos de fusión resueltos
  conservando ambos lados). Sin cambios en `src/`.
- **Cambios de datos/migración:** ninguno; esquema sin tocar.
- **Pruebas ejecutadas:** ninguna del producto. `scripts/check_project_truth.py` en
  verde; enlaces `[[...]]` de los documentos nuevos verificados contra `docs/`.
- **Dependencias o validaciones externas:** sigue pendiente la revisión RGPD
  profesional. La decisión sobre Groq —declararlo o retirarlo— es del founder.
- **Riesgo/punto probable de fallo:** **corrección de fondo.** Los documentos de hoy
  afirmaban, siguiendo `Meta-Verificacion.pdf`, que la revisión de la aplicación de
  Meta no hacía falta. `Ruta-legal.pdf` argumenta lo contrario con mejor base: el
  `Standard access` solo alcanza activos propios, así que la WABA de un cliente exige
  `Advanced access` y App Review. Se corrige en `Constitucion-y-primer-euro.md` y se
  remite a `Ruta-legal`. `Meta-Verificacion.pdf` sigue diciendo lo antiguo y habría
  que revisarlo.
- **Diagnóstico y rollback:** todo es documentación; ningún archivo de `src/` se ha
  tocado en ninguno de los commits de hoy.
- **Estado de publicación:** los cuatro documentos de hoy quedan subordinados a
  `Ruta-legal.pdf` como fuente principal de obligaciones y a `Plan-60-dias.pdf` como
  calendario. Aportan lo que aquellos no cubren: forma jurídica y constitución,
  auditoría del código, y residencia de datos.

## 2026-09-03 — lista de acciones de protección de datos

- **Autor/agente:** Claude.
- **Objetivo:** convertir las dos auditorías anteriores (textos/código y residencia de
  datos) en una única lista ejecutable, para que el founder sepa qué hacer hoy, qué
  antes de cobrar, qué encargar fuera y cómo comprobar que está cerrado.
- **Áreas y archivos:** documentación legal; `docs/RGPD-QUE-HACER.md` (nuevo) y enlace
  en `docs/Inicio.md`. Sin cambios en `src/`. No duplica pendientes: las tareas siguen
  en `docs/Tareas-vivas.md` y el porqué en los dos documentos de origen.
- **Cambios de datos/migración:** ninguno; esquema sin tocar.
- **Pruebas ejecutadas:** ninguna del producto (cambio solo documental).
- **Dependencias o validaciones externas:** el bloque 2 entero depende de un abogado
  de protección de datos, y el encargo 2.4 (tabla de plazos de conservación) bloquea
  dos tareas de producto. El bloque 0 no depende de nadie.
- **Riesgo/punto probable de fallo:** aplazar el punto 0.3 (mover la región de
  Railway). Es la única tarea de la lista que se encarece sola: migrar un volumen
  montado causa parada, y hoy el volumen está vacío.
- **Diagnóstico y rollback:** documento autónomo; borrarlo no afecta al producto.
- **Estado de publicación:** entregado. Ninguna de las acciones se ha ejecutado: el
  documento es la lista, no el trabajo hecho.

## 2026-09-03 — residencia de datos y verificación del proveedor de alojamiento

- **Autor/agente:** Claude.
- **Objetivo:** responder a la duda del founder sobre si Railway «sirve para RGPD» y
  separar el mito (no existe ninguna licencia RGPD) del problema real, que es dónde
  están alojados hoy los datos y las copias.
- **Áreas y archivos:** documentación de despliegue y legal;
  `docs/Servidores-y-residencia-de-datos.md` (nuevo), enlace en `docs/Inicio.md` y
  una tarea P0 nueva en `docs/Tareas-vivas.md`. Sin cambios en `src/`.
- **Cambios de datos/migración:** ninguno; esquema sin tocar.
- **Pruebas ejecutadas:** ninguna del producto (cambio solo documental). Se verificó
  la documentación pública de Railway (compliance, DPA, privacidad, regiones y config
  as code) y se leyeron `railway.json` y `src/noesis/config.py`.
- **Dependencias o validaciones externas:** **la región de los servicios no se puede
  verificar desde el repositorio**: vive en el panel de Railway y `railway.json` no
  fija ninguna. El founder debe comprobarla. Hallazgo de código: `BACKUP_S3_REGION`
  toma `us-east-1` por defecto en `config.py:476`.
- **Riesgo/punto probable de fallo:** activar la copia externa a S3 sin fijar la
  región europea replicaría la base completa a Virginia; y aplazar el cambio de
  región hasta después del piloto convierte una operación indolora en una parada
  negociada, porque migrar un volumen montado causa downtime.
- **Diagnóstico y rollback:** el documento es autónomo. No se ha cambiado el valor por
  defecto de `BACKUP_S3_REGION` en el código: es una decisión de despliegue del
  founder y se ha dejado anotada, no aplicada.
- **Estado de publicación:** entregado como análisis. Conclusión: Railway es apto para
  RGPD —DPA autoservicio, certificación en el Marco de Privacidad de Datos UE-EE. UU.,
  SOC 2 Tipo II y región en Ámsterdam—, y lo que falta son cuatro acciones del
  founder, no un cambio de proveedor.

## 2026-09-03 — auditoría RGPD del código y de los textos publicados

- **Autor/agente:** Claude.
- **Objetivo:** separar lo que Bynoesis ya cumple en materia de protección de datos de
  lo que está publicado y no es cierto, para que la revisión profesional pendiente
  llegue con la lista hecha y no descubra los problemas cobrando por horas.
- **Áreas y archivos:** documentación legal; `docs/RGPD-estado-y-plan.md` (nuevo),
  enlaces en `docs/Inicio.md` y `docs/Constitucion-y-primer-euro.md`, y una tarea P0
  nueva en `docs/Tareas-vivas.md`. Sin cambios en `src/`.
- **Cambios de datos/migración:** ninguno; esquema sin tocar.
- **Pruebas ejecutadas:** ninguna del producto (cambio solo documental). Los
  hallazgos se verificaron leyendo `src/noesis/web/templates/` (privacidad,
  encargado-tratamiento, cookies, cumplimiento, site_contacto),
  `src/noesis/web/routers/account.py`, `src/noesis/db.py`,
  `src/noesis/documents/storage.py` y `src/noesis/config.py`.
- **Dependencias o validaciones externas:** el documento **no sustituye la revisión
  RGPD profesional**, que sigue pendiente en `docs/Tareas-vivas.md`. Los plazos de
  conservación y la procedencia de una evaluación de impacto los tiene que fijar un
  abogado; sin ellos no se puede programar la purga automática.
- **Riesgo/punto probable de fallo:** tratar la auditoría como suficiente y abrir el
  cobro sin revisión externa. Tres afirmaciones publicadas son hoy incorrectas y
  corregirlas es previo a cualquier cliente de pago.
- **Diagnóstico y rollback:** el documento es autónomo; borrarlo no afecta al
  producto. Ningún archivo de `src/` se ha modificado, así que los hallazgos siguen
  presentes en el código hasta que se decida corregirlos.
- **Estado de publicación:** entregado como análisis. **No se ha tocado ningún texto
  legal publicado:** cambiar la política de cookies, la lista de subencargados o
  `/cumplimiento` es una decisión del founder, y `/cumplimiento` además depende de la
  decisión abierta sobre el alcance Veri\*Factu.

## 2026-09-03 — forma jurídica, requisitos legales y camino al primer euro

- **Autor/agente:** Claude.
- **Objetivo:** responder a tres preguntas del founder en un solo documento: si
  conviene S.L. o autónomo de cara a los permisos de Meta, qué hace falta legalmente
  desde la constitución, y cuál es el camino crítico real hasta el primer cobro.
- **Áreas y archivos:** documentación de negocio; `docs/Constitucion-y-primer-euro.md`
  (nuevo), enlace en `docs/Inicio.md` y tres preguntas nuevas en
  `docs/Preguntas-abiertas.md`. Sin cambios en `src/`.
- **Cambios de datos/migración:** ninguno; esquema sin tocar.
- **Pruebas ejecutadas:** ninguna del producto (cambio solo documental).
- **Dependencias o validaciones externas:** **todo el contenido fiscal, mercantil y
  de protección de datos debe confirmarse con una gestoría y un abogado antes de
  firmar o publicar nada.** Importes, plazos, epígrafes de IAE y requisitos de
  verificación de Meta son orientativos y cambian. El documento señala además una
  obligación no recogida hasta ahora: Bynoesis es *productor* de un sistema informático
  de facturación y como tal le aplica el RD 1007/2023 antes que a sus clientes.
- **Riesgo/punto probable de fallo:** tomar los importes o los plazos del documento
  como definitivos, o iniciar la verificación de empresa en Meta con un nombre que no
  coincida carácter a carácter con la escritura; un rechazo reinicia el reloj.
- **Diagnóstico y rollback:** el documento es autónomo; borrarlo no afecta a nada del
  producto ni de las pruebas.
- **Estado de publicación:** documento entregado. Ninguna decisión tomada todavía:
  las tres que bloquean el plan están en `docs/Preguntas-abiertas.md`.

## 2026-09-01 — plan de contenido de 60 días para redes

- **Autor/agente:** Claude.
- **Objetivo:** dar al founder un calendario y unos guiones listos para grabar que
  conviertan la estrategia comercial en publicaciones concretas, alternando
  contenido informativo del sector con contenido de producto.
- **Áreas y archivos:** documentación de marketing;
  `docs/Marketing-Calendario-60-dias.xlsx` y `docs/Marketing-Guiones-60-dias.docx`
  (ambos nuevos). Sin cambios en `src/`.
- **Cambios de datos/migración:** ninguno; esquema sin tocar.
- **Pruebas ejecutadas:** ninguna del producto (cambio solo documental). Los dos
  ficheros se han vuelto a abrir con `openpyxl` y `python-docx` para comprobar
  hojas, número de filas, tablas y codificación.
- **Dependencias o validaciones externas:** los guiones marcados con aviso contienen
  afirmaciones fiscales y legales (IVA reducido en obra, retención de IRPF, Ley de
  morosidad, Verifactu) que **deben verificarse en la AEAT o con un asesor el mismo
  día de grabar**. El vídeo 26 no puede publicarse sin cifras reales del piloto y
  permiso escrito del cliente. El vídeo 32 debe apoyarse en un fallo real de este
  registro.
- **Riesgo/punto probable de fallo:** publicar una fecha normativa o una cifra de
  resultados sin verificar; sería el único error capaz de tirar la credibilidad de
  los otros 33 vídeos.
- **Diagnóstico y rollback:** los dos ficheros son autónomos; borrarlos no afecta a
  nada del producto. El generador que los produjo no se ha añadido al repositorio
  para no introducir `openpyxl` ni `python-docx` como dependencias.
- **Estado de publicación:** documentos entregados, sin publicar todavía en ninguna
  plataforma. La primera publicación prevista es el 7 de septiembre de 2026.

## 2026-08-31 — convierte la estrategia de contenido en un manual de producción

- **Autor/agente:** Codex.
- **Objetivo:** entregar un sistema editorial ejecutable para que el equipo pueda
  producir contenido que primero identifique y ayude al autónomo, después demuestre
  el producto y solo entonces pida una prueba.
- **Áreas y archivos:** `branding/contenido/Plan-editorial-y-guiones-Bynoesis.docx`,
  su generador reproducible en `branding/contenido/scripts/` y documentación viva.
  El manual reúne 24 fichas de contenido, cinco campañas, un mes editorial, método
  de producción, métricas, checklist y límites de comunicación.
- **Cambios de datos/migración:** ninguno. No cambia producto, runtime ni base de datos.
- **Pruebas ejecutadas:** generación reproducible; DOCX válido; 38 páginas
  renderizadas y revisadas; auditoría de títulos, secciones, imagen y accesibilidad;
  logotipo con texto alternativo; `git diff --check` y verdad del proyecto.
- **Dependencias o validaciones externas:** la cadencia, los ganchos y las campañas
  deben aprender de publicación real; casos, testimonios y cifras requieren permiso
  y evidencia antes de publicarse.
- **Riesgo/punto probable de fallo:** tratar el calendario como una parrilla rígida
  o presentar como real una demo, una integración o un resultado aún no validado.
- **Diagnóstico y rollback:** cada ficha incluye métrica y guardarraíl; el generador
  reconstruye el documento. Revertir este commit retira solo material editorial.
- **Estado de publicación:** manual listo para seleccionar el primer bloque de rodaje;
  todavía no implica que se hayan publicado o validado las piezas.

## 2026-08-31 — fondo verde bosque para los avatares sociales

- **Autor/agente:** Codex.
- **Objetivo:** sustituir el fondo teal suave del avatar por el verde bosque fuerte
  de Bynoesis, manteniendo sin cambios la estrella original y su contorno exterior.
- **Áreas y archivos:** revisión 1.2.2 del generador, manifiesto y avatares de
  `branding/`; copias listas para subir, guía Word y documentación viva. Portadas,
  símbolo maestro, lockups e iconos de aplicación siguen sin cambios.
- **Cambios de datos/migración:** ninguno. No cambia producto, runtime ni base de datos.
- **Pruebas ejecutadas:** regeneración determinista de 49 PNG; comprobación exacta
  del fondo `#14463b`; revisión visual a 1080 y 400 px; copias idénticas por SHA-256;
  guía de ocho páginas renderizada y revisada; `npm audit`, verdad del proyecto y
  `git diff --check`.
- **Dependencias o validaciones externas:** queda pendiente el recorte real al subir
  la imagen a cada plataforma.
- **Riesgo/punto probable de fallo:** confundir el fondo oscuro con un cambio del
  símbolo. La prueba limita el cambio al rectángulo de fondo del avatar.
- **Diagnóstico y rollback:** el manifiesto 1.2.2 identifica los nuevos hashes y
  `npm run build` los reproduce. Revertir el commit devuelve el fondo teal anterior.
- **Estado de publicación:** activos corregidos en repositorio; perfiles aún no creados.

## 2026-08-31 — conserva el interior original del símbolo en el avatar

- **Autor/agente:** Codex.
- **Objetivo:** corregir la interpretación del contorno social: mantener exactamente
  el interior del símbolo oficial y aplicar el trazo oscuro únicamente al perímetro
  de la estrella exterior.
- **Áreas y archivos:** revisión 1.2.1 del generador, manifiesto y avatares de
  `branding/`; copias listas para subir, guía Word y documentación viva. Portadas,
  símbolo maestro, lockups e iconos de aplicación siguen sin cambios.
- **Cambios de datos/migración:** ninguno. No cambia producto, runtime ni base de datos.
- **Pruebas ejecutadas:** regeneración determinista de 49 PNG; comparación de colores
  y geometría con `noesis-mark-master.svg`; verificación de que solo el polígono
  exterior contiene `stroke`; revisión visual a 1080 y 400 px; copias idénticas por
  SHA-256; guía de ocho páginas renderizada y revisada; `npm audit`, verdad del
  proyecto y `git diff --check`.
- **Dependencias o validaciones externas:** queda pendiente el recorte real al subir
  la imagen a cada plataforma.
- **Riesgo/punto probable de fallo:** volver a introducir trazos en el polígono
  interior o en los círculos alteraría el símbolo. La prueba estructural lo impide.
- **Diagnóstico y rollback:** el manifiesto 1.2.1 identifica los nuevos hashes y
  `npm run build` los reproduce. Revertir el commit devuelve la interpretación con
  líneas interiores sin tocar el logo maestro.
- **Estado de publicación:** activos corregidos en repositorio; perfiles aún no creados.

## 2026-08-31 — simplifica y amplía el avatar social

- **Autor/agente:** Codex.
- **Objetivo:** aplicar la revisión del fundador al identificador de los perfiles:
  eliminar el recuadro blanco, aumentar la estrella y sostener su lectura con un
  contorno oscuro sobre un fondo del mismo verde.
- **Áreas y archivos:** generador y manifiesto 1.2 de `branding/`; cuatro avatares
  sociales; cinco copias operativas de `branding/redes-sociales/`; guía de marca,
  guía Word y documentación viva. El símbolo maestro, las portadas y los iconos de
  la aplicación permanecen intactos.
- **Cambios de datos/migración:** ninguno. No cambia producto, runtime ni base de datos.
- **Pruebas ejecutadas:** 49 PNG regenerados; dimensiones, hashes y alfa contrastados;
  avatar 1080 × 1080 y logo 400 × 400 revisados visualmente; copias operativas
  idénticas; DOCX renderizado en ocho páginas y revisado; `npm audit`, verdad del
  proyecto y `git diff --check`.
- **Dependencias o validaciones externas:** sigue pendiente observar el recorte real
  en cada plataforma una vez se creen los perfiles.
- **Riesgo/punto probable de fallo:** un contorno demasiado fino desaparecería en
  miniatura y uno excesivo deformaría el símbolo. La exportación usa tinta Bynoesis y
  conserva un margen amplio para la máscara circular.
- **Diagnóstico y rollback:** `manifest.json` registra la versión 1.2 y los hashes;
  `npm run build` reproduce los activos. Revertir el commit devuelve el avatar con
  placa crema sin tocar el resto del sistema visual.
- **Estado de publicación:** archivos listos en el repositorio; subida a redes pendiente.

## 2026-08-31 — prepara los perfiles oficiales para publicar

- **Autor/agente:** Codex.
- **Objetivo:** convertir el sistema de marca existente en una entrega operativa para
  crear Instagram, Facebook y LinkedIn sin improvisar imágenes, descripciones,
  botones, propiedad ni seguridad de las cuentas.
- **Áreas y archivos:** nuevo `branding/redes-sociales/` con carpetas por plataforma,
  PNG listos para subir, textos UTF-8, guía Word de ocho páginas, fuentes oficiales y
  reserva acotada de YouTube/TikTok; índice de branding y documentación viva.
- **Cambios de datos/migración:** ninguno. No cambia aplicación, runtime ni base de datos.
- **Pruebas ejecutadas:** dimensiones y hashes de los PNG contrastados con los activos
  maestros; DOCX abierto estructuralmente, renderizado a PDF y revisado página por
  página; textos sin marcadores, finales de archivo normalizados, verdad del proyecto
  y `git diff --check`.
- **Dependencias o validaciones externas:** crear las cuentas, confirmar que
  `@bynoesis` está disponible y observar el recorte real requiere acceso de los
  fundadores a cada plataforma. Las especificaciones de LinkedIn y los controles de
  Facebook se contrastaron con sus ayudas oficiales.
- **Riesgo/punto probable de fallo:** una red puede modificar campos o recortes. El
  paquete mantiene el contenido esencial centrado y obliga a probar móvil y escritorio
  antes de publicar.
- **Diagnóstico y rollback:** cada carpeta contiene el nombre exacto del archivo que
  se debe subir y una lista de comprobación. Revertir el commit elimina solo el paquete
  operativo; no afecta al branding maestro ni al producto.
- **Estado de publicación:** materiales locales listos; perfiles pendientes de alta y
  validación real por los fundadores.

## 2026-08-31 — alinea la marca con tiempo, orden y control

- **Autor/agente:** Codex.
- **Objetivo:** corregir el enfoque excesivamente centrado en cobros del primer kit
  y devolver la marca a la misión aprobada: Bynoesis lleva la oficina, quita ruido
  mental y permite al autónomo centrarse en su oficio sin perder el control.
- **Áreas y archivos:** guía, generador, manifiesto, tablero y portadas de `branding/`;
  introducción pública del `README`; mensaje rector y pruebas de
  `docs/Estrategia-Marketing.html` y su PDF sincronizado; decisión y estado vivos.
  Se conserva sin alteraciones la geometría del símbolo y el sistema visual.
- **Pruebas ejecutadas:** 49/49 PNG reconstruidos y verificados contra dimensiones,
  alfa y SHA-256 del manifiesto; regeneración determinista; SVG parseables; revisión
  visual del tablero y portada; las 13 páginas del PDF se renderizaron y revisaron;
  búsqueda negativa del lema retirado; `npm audit` sin vulnerabilidades, verdad del
  proyecto y `git diff --check`.
- **Dependencias o validaciones externas:** ninguna credencial. Sharp se actualiza a
  0.35.4 solo dentro del generador aislado de branding; no entra en el runtime web.
- **Riesgo/punto probable de fallo:** convertir «tiempo y control» en una promesa
  genérica si las piezas no enseñan pruebas. La guía obliga a sostenerla con tareas,
  documentos, facturas, agenda y resultados reales de cada cliente.
- **Diagnóstico y rollback:** `branding/manifest.json` identifica cada exportación;
  `npm run build` la reconstruye. Revertir este cambio recupera solo el copy y los
  activos sociales anteriores; no afecta datos, aplicación ni despliegue.
- **Estado de publicación:** kit corregido localmente; las redes siguen pendientes
  de creación y validación de recorte real.

## 2026-08-31 — convierte el símbolo existente en un sistema de marca exportable

- **Autor/agente:** Codex.
- **Objetivo:** dar a Bynoesis un paquete de branding profesional y reproducible para
  web, documentos y creación de LinkedIn, Instagram, Facebook y otros perfiles sin
  inventar una identidad paralela ni deformar el símbolo ya reconocido por el producto.
- **Áreas y archivos:** nueva raíz `branding/` con guía de marca, licencias,
  paleta JSON/CSS, originales SVG, 49 PNG transparentes/con fondo, avatares,
  portadas, plantillas, manifiesto con hashes y generador determinista; documentación
  viva de marca, mapa, estado, tareas y QA. No cambia runtime, base de datos ni web.
- **Pruebas ejecutadas:** regeneración completa con Sharp; 49/49 PNG decodificables,
  dimensiones y alfa contrastados contra `manifest.json`, hashes repetibles, SVG
  parseables, ningún activo social por encima de 3 MB, `git diff --check` y revisión
  visual de tablero, avatar, portada y paleta.
- **Dependencias o validaciones externas:** la portada de LinkedIn sigue su
  especificación oficial vigente de 4200 × 700 y el logo 400 × 400. Crear las cuentas,
  comprobar sus recortes reales y añadir sus URL a `sameAs` corresponde al founder.
- **Riesgo/punto probable de fallo:** una plataforma puede cambiar el recorte sin
  aviso. Por eso el avatar concentra el símbolo en el centro y las portadas evitan
  detalles esenciales en los bordes.
- **Diagnóstico y rollback:** `branding/manifest.json` identifica dimensiones,
  finalidad y SHA-256. Reejecutar `branding/scripts/build_brand_assets.mjs` reconstruye
  los PNG; revertir este commit elimina solo el paquete y no modifica la identidad
  que ya usa la aplicación.
- **Estado de publicación:** paquete local listo para uso; no requiere despliegue.

## 2026-08-27 — prepara facturas por catch-all sin mezclar empresas ni crear clientes a ciegas

- **Autor/agente:** Codex.
- **Objetivo:** recibir adjuntos de todos los clientes en un único buzón Hostinger,
  ahorrar alias y convertir una factura con cliente recurrente o nuevo en un flujo
  sencillo sin aceptar un error de identidad como dato contable.
- **Áreas y archivos:** migración 52; configuración; frontera de datos; servicio,
  repositorio y nuevo consumidor documental IMAP; scheduler; página Documentos;
  CLI; siete regresiones y documentación operativa/arquitectónica.
- **Pruebas ejecutadas:** 7/7 contratos nuevos y suite completa **550/550** en
  477,3 s; migración focalizada, página documental autenticada, Ruff, compilación,
  fuente de verdad y `git diff --check` verdes.
- **Dependencias o validaciones externas:** usa IMAP SSL de Hostinger, pero permanece
  apagado por defecto. Falta probar el catch-all real y la conservación del
  destinatario antes de activar el scheduler en producción.
- **Riesgo/punto probable de fallo:** que Hostinger reescriba o pierda el destinatario
  original. En ese caso Bynoesis rechaza el mensaje; nunca intenta deducir el negocio
  por remitente, asunto o nombre de archivo. Un catch-all también recibe spam y
  errores tipográficos, por lo que debe aislarse del soporte humano.
- **Diagnóstico y rollback:** estados/contadores de `inbound_email_messages`, eventos
  `inbound_email_processed` y CLI `python -m noesis.documents.inbound_email` sin
  secretos. Apagar `NOESIS_INBOUND_EMAIL_ENABLED` detiene la entrada sin retirar
  Documentos ni clientes; revertir el commit y bajar 52 elimina solo rutas, huellas y
  propuestas nuevas.
- **Estado de publicación:** candidato local validado; pendiente de commit, CI,
  humo PostgreSQL y prueba Hostinger.

## 2026-08-26 — controla la rentabilidad operativa por cuenta

- **Autor/agente:** Codex.
- **Objetivo:** saber qué cuentas generan o destruyen margen y dónde crece el coste
  sin abrir el contenido privado del negocio ni confundir estimación con gasto real.
- **Áreas y archivos:** agregación CFO en `db.py`, centro de mando y ficha privada
  de cuenta, estilos, dos regresiones nuevas y documentación viva. Sin migración.
- **Pruebas ejecutadas:** 4/4 contratos centrados, suite estándar completa
  **543/543**, Ruff y `git diff --check` verdes; fuente de verdad y barreras de
  seguridad se ejecutan antes de publicar.
- **Dependencias o validaciones externas:** ninguna nueva. Para que el margen sea
  representativo hay que cargar facturas reales de proveedores en el libro CFO.
- **Riesgo/punto probable de fallo:** un coste sin volumen medible queda sin asignar;
  esto reduce cobertura, pero evita inventar rentabilidad. El ingreso mostrado es
  MRR comprometido por plan, no caja cobrada ni contabilidad analítica.
- **Diagnóstico y rollback:** revisar `platform_cost_entries`, la sección
  `rentabilidad-cuentas` y `account_cost_control`; revertir elimina la lectura y las
  alertas sin tocar clientes, facturas, suscripciones ni el libro append-only.
- **Estado de publicación:** candidato local validado; pendiente de `push`, CI,
  humo PostgreSQL y despliegue automático.

## 2026-08-26 — repara la restauración de facturas emitidas en PostgreSQL

- **Autor/agente:** Codex.
- **Objetivo:** recuperar copias actuales sin relajar la inmutabilidad que protege
  una factura emitida durante el funcionamiento normal.
- **Áreas y archivos:** restaurador PostgreSQL, humo real de CI, documentación viva
  y órdenes Railway verificadas para diagnóstico/integraciones/restauración. Sin
  migración ni cambio de datos de producción.
- **Pruebas ejecutadas:** diagnóstico y simulacro reales por SSH; 5/5 pruebas locales
  de backup, Ruff y compilación. Humo PostgreSQL ampliado pendiente del `push`.
- **Dependencias o validaciones externas:** no añade proveedor ni credencial; la
  copia fuera del servidor continúa necesitando un bucket S3-compatible.
- **Riesgo/punto probable de fallo:** permisos PostgreSQL para `ALTER TABLE ...
  DISABLE TRIGGER USER`; el CI usa PostgreSQL real y debe rechazar el candidato si
  el rol no puede hacerlo o si una restricción deja de cumplirse.
- **Diagnóstico y rollback:** `backup_runs`, evento `backup.restore_drill_*` y
  `noesis-restore-check`; revertir devuelve el fallo conocido y no toca la base real.
- **Estado de publicación:** release `d55be0ae6673` desplegado. El humo PostgreSQL,
  una copia nueva de esquema 51 en producción y el simulacro independiente están
  verdes. Queda únicamente la salida y restauración fuera de Railway.

## 2026-08-26 — hace atómica la recuperación del titular

- **Autor/agente:** Codex.
- **Objetivo:** que una caída entre consumir el enlace y guardar la clave no deje un
  acceso a medias, y que un correo antiguo no siga siendo válido.
- **Áreas y archivos:** tokens y credenciales en `db.py`, router de cuenta, dos
  regresiones HTTP, documentación y retirada de una detección obsoleta de
  `.secrets.baseline`. Sin migración ni cambio visual.
- **Pruebas ejecutadas:** 2/2 contratos específicos y suite estándar completa
  **541/541** verdes; controles estáticos y de seguridad antes del commit.
- **Dependencias o validaciones externas:** ninguna nueva; llegada del enlace sigue
  dependiendo del correo ya configurado.
- **Riesgo/punto probable de fallo:** entregabilidad externa, no consistencia local;
  el estado queda íntegro aunque la petición falle antes del commit.
- **Diagnóstico y rollback:** eventos `account.password_reset_*` y outbox; revertir
  devuelve el consumo en dos pasos, sin tocar claves ya establecidas.
- **Estado de publicación:** código publicado en `main`; el primer CI pasó PostgreSQL
  y señaló que la línea eliminada seguía inventariada en el baseline. La corrección
  de esa metainformación queda en este mismo bloque antes de repetir el CI completo.

## 2026-08-26 — permite reintentar un correo agotado sin abrir su contenido

- **Autor/agente:** Codex.
- **Objetivo:** resolver desde soporte un fallo de entrega definitivo sin acceder al
  correo del cliente ni provocar envíos duplicados.
- **Áreas y archivos:** frontera de outbox en `db.py`, ruta y ficha de soporte,
  regresión HTTP y documentación viva. Sin migración.
- **Pruebas ejecutadas:** contrato específico y suite estándar completa **539/539**
  verdes; controles estáticos y de seguridad se ejecutan antes del commit.
- **Dependencias o validaciones externas:** ninguna nueva; una entrega real sigue
  dependiendo del proveedor configurado y la controla el scheduler.
- **Riesgo/punto probable de fallo:** proveedor aún caído o dirección inválida; el
  correo volverá a `retrying/failed` con su motivo técnico visible, sin bucle manual.
- **Diagnóstico y rollback:** evento `admin.email_delivery_requeued`, estado de
  `email_outbox` y sección Entregas; revertir restaura el diagnóstico de solo lectura.
- **Estado de publicación:** local verificado de forma centrada; no publicado.

## 2026-08-26 — recupera el acceso profesional de gestoría

- **Autor/agente:** Codex.
- **Objetivo:** que un despacho pueda recuperar su cuenta sin soporte manual y sin
  reducir la seguridad de todas las empresas de su cartera.
- **Áreas y archivos:** migración 51, frontera de datos de gestoría, router y dos
  pantallas de acceso, estilos acotados, tres pruebas y documentación de estado.
- **Pruebas ejecutadas:** 7/7 contratos centrados de recuperación y MFA, suite
  estándar completa **538/538**, Ruff, compilación, fuente de verdad y
  `git diff --check` verdes. Quedan las barreras de seguridad y CI/PostgreSQL.
- **Dependencias o validaciones externas:** no añade proveedor ni credencial; reutiliza
  el correo durable existente. La llegada a Gmail/Outlook requiere prueba real.
- **Riesgo/punto probable de fallo:** configuración o entregabilidad del proveedor de
  correo; el flujo responde igual y conserva la cuenta aunque el envío se retrase.
- **Diagnóstico y rollback:** revisar solo metadatos de `email_outbox` y los eventos
  `gestoria.password_reset_*`; revertir el bloque elimina rutas/tabla sin modificar
  accesos, cartera, MFA ni contraseñas existentes.
- **Estado de publicación:** local en validación; no publicado todavía.

## 2026-08-26 — automatiza la puerta externa del release publicado

- **Autor/agente:** Codex.
- **Objetivo:** detectar automáticamente despliegues incompletos y regresiones de la
  superficie pública antes de que las reporte un cliente.
- **Áreas y archivos:** `production_check.py`, su entrypoint, cinco pruebas, workflow
  programado de GitHub y documentación operativa/estado. Sin cambios de datos.
- **Pruebas ejecutadas:** Ruff completo, detector de secretos, fuente de verdad,
  `git diff --check`, cinco contratos específicos, comprobación real contra
  producción y suite completa **535/535**. CI queda pendiente del `push`.
- **Dependencias o validaciones externas:** no requiere credenciales. Producción real
  respondió con release coherente, esquema 50, 14 páginas públicas, estructura SEO,
  textos legales y cabeceras correctas.
- **Riesgo/punto probable de fallo:** un cambio deliberado de sitemap, cabeceras o
  esquema obliga a actualizar el contrato; de no hacerlo, el workflow fallará de
  forma segura sin afectar tráfico ni datos.
- **Diagnóstico y rollback:** ejecutar `noesis-production-check --json`; cada fallo
  identifica URL o protección. Revertir el bloque elimina el monitor, pero no cambia
  producción ni esquema.
- **Estado de publicación:** local verificado; pendiente de suite, commit, push y CI.

## 2026-08-26 — recupera el CI tras sincronizar el generador económico

- **Autor/agente:** Codex, revisando los cambios publicados por Claude y el socio.
- **Objetivo:** sincronizar el repositorio tras una semana de trabajo y corregir el
  bloqueo que impedía que GitHub Actions validara cualquier commit de `main`.
- **Áreas y archivos:** `pyproject.toml`, `uv.lock`, una anotación de falso positivo
  en `tests/test_integration_check.py` y bitácoras de cambios/QA. No cambia código
  de producto ni el libro económico publicado.
- **Cambios de datos/migración:** ninguno; esquema 50 sin cambios.
- **Pruebas ejecutadas:** `uv sync --locked --extra security --extra test`, Ruff,
  `check_project_truth.py`, `git diff --check` y suite completa local de **530
  pruebas**, todas verdes. El generador económico se ejecutó con el extra `analysis`
  y salida temporal: sus 17 hojas y todas las fórmulas coinciden; solo difieren las
  tres entradas 1/5/2 que el founder escribió deliberadamente en el libro publicado
  y que una regeneración limpia devuelve a cero, como ya documentaba su cambio.
- **Dependencias o validaciones externas:** el primer run confirmó el humo
  PostgreSQL 16 y reveló una vulnerabilidad en `pip 26.1.2` (`PYSEC-2026-3721`) que
  antes quedaba oculta detrás del lock roto. El extra de seguridad exige ahora
  `pip>=26.2,<27`. El segundo run confirmó auditoría y PostgreSQL, y alcanzó un
  falso positivo histórico del detector de secretos en una credencial ficticia de
  backup usada por una prueba; se anota en esa línea sin excluir el archivo ni
  debilitar el detector. Queda confirmar el siguiente run completo.
- **Riesgo/punto probable de fallo:** `pyproject.toml` declaraba `openpyxl`, pero
  `uv.lock` no contenía `openpyxl` ni `et-xmlfile`; `uv sync --locked` fallaba antes
  de ejecutar una sola prueba. Después, `pip-audit` detectó el `pip` vulnerable que
  usa transitivamente. El lock regenerado incorpora el extra y el suelo seguro.
- **Diagnóstico y rollback:** si vuelve a aparecer «lockfile needs to be updated»,
  comparar `pyproject.toml` con `uv.lock` y ejecutar `py -m uv lock`. Revertir este
  commit devolvería el CI al bloqueo y no afecta a datos ni producción.
- **Estado de publicación:** corrección local verificada; pendiente de commit,
  `push` y confirmación del CI al escribir esta entrada.

## 2026-08-17 — sincroniza el OCR con el build real de Railway

- **Autor/agente:** Codex.
- **Objetivo:** corregir el bloqueo OCR observado mediante SSH en el contenedor real.
- **Áreas y archivos:** dependencias de producción, regresión de empaquetado y
  documentación operativa/estado.
- **Cambios de datos/migración:** ninguno; esquema 49 sin cambios.
- **Pruebas ejecutadas:** 11/11 focalizadas; suite completa **517/517** en 381,7 s;
  Ruff, verdad documental y `git diff --check` verdes.
- **Dependencias o validaciones externas:** Tesseract y `cat/spa/eng` comprobados en
  Railway; falta redesplegar para verificar los módulos Python y el corpus real.
- **Riesgo/punto probable de fallo:** caché de build o wheel PDFium incompatible con
  la imagen; el healthcheck debe impedir publicar si la instalación falla.
- **Diagnóstico y rollback:** repetir el comprobador mediante SSH. El rollback solo
  revierte requisitos Python y no toca datos.
- **Estado de publicación:** `main` y producción en `b3c184251374`; comprobación
  SSH confirma OCR de foto/PDF con `cat/spa/eng` y Stripe en `OK`.

## 2026-08-17 — cierre verificable de OCR, correo, OAuth, voz, copias y Stripe

- **Autor/agente:** Codex.
- **Objetivo:** facilitar la conexión del piloto con una verificación segura que
  distinga variables presentes de capacidades realmente disponibles.
- **Áreas y archivos:** configuración, transcripción, OCR/readiness, nuevo CLI de
  comprobación, pruebas y guías operativas/estado compartido.
- **Cambios de datos/migración:** ninguno; esquema 49 sin cambios.
- **Pruebas ejecutadas:** 36/36 focalizadas y suite completa **516/516** en 435,7 s;
  Ruff, compilación y `git diff --check` verdes.
- **Dependencias o validaciones externas:** no se usaron secretos ni proveedores
  reales. Founder debe configurar Railway y completar los recorridos humanos de
  correo, OAuth, voz, restauración y Stripe descritos en `Conectar-APIs.md`.
- **Riesgo/punto probable de fallo:** credencial de otro entorno, remitente Brevo no
  activo, precio Stripe con IVA `unspecified`, idiomas Tesseract ausentes o bucket
  configurado sin restauración independiente.
- **Diagnóstico y rollback:** ejecutar `noesis-doctor --strict` y
  `noesis-integrations-check --network --strict`. Revertir el commit elimina el CLI
  y recupera la pista fija anterior, sin tocar datos ni esquema.
- **Estado de publicación:** `main` y producción en `808a96004b7b`; queda ejecutar
  el comprobador con las credenciales de Railway y guardar la aceptación externa.

## 2026-08-14 — revisión visual del piloto y cierre de detalles móviles

- **Autor/agente:** Codex.
- **Objetivo:** recorrer las experiencias comerciales reales y corregir defectos
  visibles que restaban confianza al piloto sin ampliar permisos ni acciones.
- **Áreas y archivos:** navegación móvil, asistente, portal de cliente, filtro de
  fechas de plantillas, regresiones visuales/HTTP y documentos de estado.
- **Cambios de datos/migración:** ninguno; esquema 49 sin cambios.
- **Pruebas ejecutadas:** 11/11 focalizadas verdes; suite de **506 pruebas**
  recorrida en 489,5 s con un cierre temporal de SQLite bloqueado por Windows; la
  única prueba afectada se repitió aislada y quedó verde. Revisión real local en
  escritorio y móvil de portada, panel demo, Documentos, asistente, gestoría y
  portal de cliente; `git diff --check`, Ruff, compilación y verdad documental.
- **Dependencias o validaciones externas:** el portal Stripe real sigue necesitando
  una sesión sandbox autenticada; la extensión de Chrome de Codex no está instalada,
  por lo que en este bloque se verifican los siete contratos del adaptador/rutas,
  no el clic externo dentro de Stripe.
- **Riesgo/punto probable de fallo:** caché de CSS/plantillas tras el despliegue o
  fechas heredadas que no sean ISO; el filtro conserva sin alterar cualquier texto
  que no pueda interpretar.
- **Diagnóstico y rollback:** revisar la barra inferior a 375 px, las sugerencias
  del asistente y `/p/{token}`; si falla, revertir este commit no exige rollback de
  base de datos. Las capturas quedan fuera del repositorio en la carpeta de auditoría.
- **Estado de publicación:** `main` y producción en el release `aed36de59e30`;
  CI completo y humo PostgreSQL verdes, `/ready` confirma esquema 49 y las vistas
  publicadas de asistente, portal de cliente y gestoría móvil quedaron verificadas.

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

## 2026-09-01 12:00 — manuales de ruta legal, marketing y plan de 60 días

- **Autor/agente:** Claude.
- **Objetivo:** dejar por escrito lo que falta para poder cobrar legalmente, consolidar
  todo el marketing en un solo manual y ponerle fecha a ambas cosas.
- **Áreas y archivos:** `docs/Ruta-legal.html/pdf`, `docs/Marketing-Bynoesis.html/pdf`,
  `docs/Publicar-en-redes.html/pdf`, `docs/Plan-60-dias.html/pdf`,
  `docs/Estado-Bynoesis.xlsx`, `scripts/build_estado_xlsx.py`, `docs/Inicio.md`.
- **Cambios de datos/migración:** ninguno. Solo documentación.
- **Pruebas ejecutadas:** ninguna nueva; no se toca código. La suite quedó en 577 con
  el merge anterior.
- **Hallazgos que cambian la planificación:**
  - La obligación de Veri*Factu **del productor** está viva desde el 29-jul-2025; el
    RDL 15/2025 solo aplazó la del usuario a 2027. `Fiscalidad.md` no separaba los dos
    papeles.
  - Remitir en nombre de clientes exige **convenio de colaboración social tipo 017** y
    un modelo de representación **firmado por cada cliente**: aceptar las condiciones
    del servicio no vale. Es una funcionalidad de onboarding que no existe.
  - La **subsanación** de registros rechazados no está construida y sin ella no se
    puede declarar conformidad completa del SIF.
  - El **App Review** de Meta sí hace falta para los números comerciales, al contrario
    de lo que dice la tabla del Camino A en `Meta-Verificacion`.
  - El artículo 50 del Reglamento europeo de IA es aplicable desde el 2-ago-2026 y el
    asistente no se identifica como máquina.
  - Los oficios de la estrategia comercial y los catálogos del producto no coinciden.
- **Dependencias o validaciones externas:** los apartados fiscales y de protección de
  datos requieren revisión profesional antes de actuar sobre ellos.
- **Riesgo/punto probable de fallo:** ninguno técnico. El riesgo es documental: si
  `Marketing-Bynoesis` y `Estrategia-Marketing` conviven mucho tiempo, divergirán. El
  maestro declara en su pie a cuál sustituye.
- **Diagnóstico y rollback:** son documentos; se borran sin efecto sobre el producto.
- **Estado de publicación:** local, pendiente de subir.

## 2026-09-01 — fusión de la rama local con main tras 112 commits de divergencia

- **Autor/agente:** Claude.
- **Objetivo:** cerrar un `git merge origin/main` que había quedado a medias con
  siete conflictos, e incorporar tres commits locales que llevaban un mes sin
  subir: factura simplificada, catálogos por oficio y numeración heredada.
- **Áreas y archivos:** `src/noesis/migrations.py`, `src/noesis/web/whatsapp.py`,
  `src/noesis/whatsapp_templates.py`, `tests/test_trade_templates.py`,
  `docs/project-state.json`, `docs/Mapa-codigo.md`, `docs/Tareas-vivas.md`,
  `docs/Registro-cambios.md`, `docs/Registro-QA.md`.
- **Cambios de datos/migración:** **esquema 53**. La migración local
  `material_o_mano_de_obra` chocaba en el número 40 con `demo_comercial` del
  remoto; se renumera a **53**, detrás de `documentos_por_correo`. Sin esa
  renumeración la columna `kind` no se habría creado nunca sobre una base ya en 52.
- **Cómo se resolvió cada conflicto:**
  - `migrations.py`: se conservan las 40-52 del remoto y la local pasa a 53.
  - `whatsapp.py`: gana `sanitize_template_param` del remoto, que convierte los
    saltos en un separador visible en vez de aplastarlos. Se retira el
    `template_param` local por duplicado, pero se le aporta lo único que no
    tenía: el tope de 1024 caracteres del parámetro de Meta. Se conservan
    `MetaRejected` y la retirada de `send_payment_reminder`.
  - `whatsapp_templates.py`: reescrito como **espejo** del runbook
    `WhatsApp-Puesta-en-marcha` en lugar de proponer cuerpos distintos. Tener dos
    fuentes de verdad sobre qué pegar en WhatsApp Manager era peor que no tener
    ninguna. Ahora `python -m noesis.whatsapp_templates` confirma que los nueve
    envíos encajan.
  - `project-state.json`: base del remoto más las seis capacidades locales; dos
    reescritas porque afirmaban que los cinco proactivos seguían rotos y el
    remoto ya los arregló el 20-ago.
  - Las dos bitácoras: entradas fusionadas por fecha, no concatenadas. 51+2 y
    52+1, sin perder ninguna.
  - `Tareas-vivas.md`: base del remoto más tres tareas nuevas; se descartan las
    locales que el remoto ya resolvió.
- **Pruebas ejecutadas:** suite completa **577 pasan, 132 subtests**. Ruff verde.
  Fuente de verdad verde. Quedan **5 fallos que ya existían en `origin/main`
  limpio**, comprobado en un árbol de trabajo aparte: cuatro de
  `test_month_billing_separates_cash_flow_from_invoice_cohort`, que dependen de la
  fecha del sistema, y uno de rasterización de PDF, que necesita dependencias de
  OCR no instaladas en este equipo. **La fusión no introduce ninguna regresión.**
- **Dependencias o validaciones externas:** ninguna nueva.
- **Riesgo/punto probable de fallo:** la renumeración de la migración. Una base
  que ya estuviera en 53 por otra vía quedaría descuadrada; producción está en 52,
  así que aplicará la 53 al desplegar. Verificar `/ready` después.
- **Diagnóstico y rollback:** la rama `respaldo-pre-merge` conserva el estado
  anterior a la fusión. `python -m noesis.whatsapp_templates` y
  `pytest tests/test_trade_templates.py` cubren lo tocado.
- **Estado de publicación:** local, pendiente de subir.

## 2026-08-22 — dos manuales de diagnostico

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidio un documento completo del proyecto para tener contexto
  y saber donde esta el fallo cuando algo va mal. Eligio enfoque de diagnostico y pidio
  **dos versiones**: una que entienda el y otra mezclada con la referencia tecnica.
- **Areas y archivos:** `docs/Diagnostico.html` + `.pdf` y
  `docs/Diagnostico-tecnico.html` + `.pdf` (nuevos, 8 paginas cada uno), y
  `docs/Inicio.md`. Ningun cambio en `src/`.
- **Contenido comun:** las siete piezas que pueden fallar por separado y cual es
  insustituible; las cuatro puertas que atraviesa una peticion —identidad, aislamiento,
  permisos del plan y estado de suscripcion— con el sintoma distinto de cada rechazo;
  por que nada se pierde aunque un proveedor falle; y una tabla de sintoma a causa.
- **La version tecnica anade:** como levantar el proyecto desde cero con sus extras,
  el mapa de archivos, las tablas de las colas con sus estados, los siete trabajos
  programados con su hora, la traduccion de sintoma a archivo concreto, y los
  invariantes que no se rompen nunca.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** arquitectura verificada leyendo `web/server.py` (orden real
  de los middlewares), `web/deps.py`, `web/auth.py`, `web/scheduler.py` (horas de cada
  trabajo), `db.py`, `adapters/` y `pyproject.toml` (extras de instalacion). Ambos HTML
  sin etiquetas sin cerrar y ambos PDF validos.
- **Riesgo/punto probable de fallo:** ninguna cifra viva se fija en los documentos
  salvo el recuento de pruebas y el esquema, que remiten a `project-state.json` como
  fuente. Si el codigo se reorganiza, el mapa de archivos envejece.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-22 — dictar una factura ensuciaba el nombre del cliente

- **Autor/agente:** Claude.
- **Objetivo:** el founder pregunto donde se ponen las bases al crear una factura y
  dijo que "la gracia seria hacerlo mediante audio de voz". Al comprobarlo aparecio
  que el cerebro **ya entiende** crear facturas hablando —"factura a Juan 95 euros"
  devuelve `crear_factura` con `base: 95.0`— pero que la frase natural rompe el nombre.
- **Areas y archivos:** `src/noesis/nlu.py` (`_limpiar_cliente`),
  `tests/test_backend.py`, `docs/project-state.json`.
- **El fallo:** "factura para Juan Perez de 250 euros" capturaba el cliente
  "Juan Perez de". El patron busca de forma perezosa hasta el importe y arrastra el
  conector. Al dictar por voz esa frase es la natural, y el nombre sucio **crea un
  cliente nuevo mal escrito** en vez de reconocer al que ya existe: el autonomo acaba
  con "Juan Perez" y "Juan Perez de" como dos clientes distintos.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** cuatro frases dictadas como subtests, **verificadas por
  reversion**: sin la limpieza fallan las dos que llevan conector. 73 pruebas de
  cerebro, chat y facturas en verde; `ruff` limpio.
- **Dependencias o validaciones externas:** el dictado no funciona todavia en
  produccion. El asistente web **ya graba audio** y el adaptador tiene dos vias
  —Whisper local y Groq—, pero `get_transcriber()` devuelve `None`: falta
  `GROQ_API_KEY`. Sin eso se graba y no se transcribe.
- **Riesgo/punto probable de fallo:** la lista de conectores es finita; una frase con
  otro enlace volveria a ensuciar el nombre. El sintoma seria un cliente duplicado con
  una palabra de mas al final.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-22 — el boton de Google no tenia la marca de Google

- **Autor/agente:** Claude.
- **Objetivo:** el founder dijo que "no funciona lo del logo" al conectar con Google.
  No era la pantalla de consentimiento de Google: era **nuestro** boton, que solo
  llevaba el texto "Continuar con Google" y ningun icono. Nunca lo tuvo.
- **Areas y archivos:** `web/templates/login.html`, `web/templates/onboarding.html`,
  `web/static/app.css`, `tests/test_backend.py`, `docs/project-state.json`.
- **Cambios de datos/migracion:** ninguno.
- **Como se ha hecho:** la marca oficial de cuatro colores va **en SVG dentro del
  HTML**, no como imagen externa. Las reglas del proyecto prohiben CDNs en runtime, y
  ademas un icono servido por un tercero se cae cuando ese tercero se cae y cuenta a
  quien visita la pagina de acceso. El SVG no cambia de color al pasar el raton,
  porque las normas de uso de la marca exigen respetar sus colores.
- **Pruebas ejecutadas:** prueba nueva que comprueba el boton, la clase del logo, los
  cuatro colores —si falta uno el logo sale roto— y que no hay ninguna URL externa
  dentro del boton. 65 pruebas de login, Google, onboarding y autenticacion en verde;
  `ruff` limpio. Verificado ademas contra el servidor real, descargando `/login` y
  comprobando el HTML entregado.
- **Dependencias o validaciones externas:** ninguna.
- **Riesgo/punto probable de fallo:** ninguno funcional. Aparte, en la consola de
  Google el nombre y el logo de **Bynoesis** solo se muestran tras publicar la app y
  pasar la verificacion de marca, que es automatica en minutos; hasta entonces el
  usuario ve el dominio. Eso es de Google y no de este cambio.
- **Diagnostico y rollback:** revertir el commit deja el boton con solo texto.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-20 — corregido el plazo de verificacion de Meta en la guia

- **Autor/agente:** Claude.
- **Objetivo:** el founder pregunto cuanto tarda la verificacion de empresa. La guia
  decia "de horas a una semana", una cifra que yo habia escrito de memoria y sin
  fuente.
- **Areas y archivos:** `docs/Meta-Verificacion.html` + `.pdf`.
- **Cambios de datos/migracion:** ninguno.
- **Que se corrige:** Meta **no publica ningun compromiso de plazo**. Los proveedores
  que trabajan con la plataforma dan rangos dispares: de 10 minutos a 14 dias
  laborables con casos de hasta 30 dias (Respond.io), de 2 horas a 5 dias laborables
  (ActiveCampaign), unos dias o una semana (Klaviyo). La guia pasa a decir "entre unas
  horas y dos semanas" y advierte de no comprometer una fecha de piloto que dependa
  de esto.
- **Se anaden ademas dos cosas utiles:** los tres motivos por los que Meta rechaza
  —datos incompletos, documentos ilegibles y datos legales que no coinciden—, porque
  determinan en que extremo del rango caes y cada rechazo reinicia el reloj; y el
  matiz de que **la verificacion no bloquea empezar el piloto**: sin ella hay 250
  conversaciones/24 h y dos numeros, que sobra para 3-5 autonomos. Limita cuando se
  puede crecer, no cuando se puede empezar.
- **Pruebas ejecutadas:** HTML sin etiquetas sin cerrar; PDF regenerado y valido.
- **Riesgo/punto probable de fallo:** son observaciones de terceros y pueden cambiar;
  el pie del documento lo dice y las fecha.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-20 — guia de verificacion de Meta: que hace falta y que no

- **Autor/agente:** Claude.
- **Objetivo:** el founder enseño la lista de "Requisitos y personalizacion" de Meta,
  que termina en revision y publicacion de la aplicacion, y la pantalla de Facebook
  Login. Estaba a punto de recorrer un camino de semanas que **no necesita**.
- **Areas y archivos:** `docs/Meta-Verificacion.html` + `.pdf` (nuevos) y
  `docs/Inicio.md`. Ningun cambio en `src/`.
- **Cambios de datos/migracion:** ninguno.
- **Hallazgo principal:** Meta mezcla en la misma consola dos caminos. La revision de
  la aplicacion y Facebook Login pertenecen a **Embedded Signup**, donde un cliente
  conecta su numero desde la web del proveedor. **Bynoesis no lo usa**: verificado por
  busqueda en `src/`, no hay ni una referencia, y `Conectar-APIs.md` confirma que el
  alta de WABA y numero la hace administracion a mano. Para el piloto basta con
  verificacion de empresa, numero, pago, token de sistema y plantillas.
- **Pruebas ejecutadas:** HTML sin etiquetas sin cerrar y PDF valido de 6 paginas.
- **Dependencias o validaciones externas:** los cinco tramites de Meta siguen abiertos.
- **Riesgo/punto probable de fallo:** si algun dia se construye Embedded Signup, la
  revision de la aplicacion pasa a ser obligatoria y esta guia deja de aplicar en esa
  parte. Queda dicho en el propio documento.
- **Diagnostico y rollback:** cambio solo documental.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-20 — corregido el fallo que habria roto los cinco avisos de WhatsApp

- **Autor/agente:** Claude.
- **Objetivo:** cerrar el hallazgo abierto desde el 10-ago. Meta rechaza un parametro
  de plantilla con salto de linea, tabulador o mas de cuatro espacios seguidos, y el
  planificador pasaba resumenes multilinea como un unico parametro.
- **Areas y archivos:** `web/whatsapp.py` (`sanitize_template_param`, aplicada en
  `queue_template`), `tests/test_backend.py`, los dos documentos de WhatsApp —que
  anunciaban un fallo abierto— y su PDF, `docs/project-state.json`,
  `docs/Registro-QA.md`.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** dos nuevas, **verificadas por reversion**: sin el saneado
  fallan seis comprobaciones, una por cada proactivo mas la general. 64 pruebas de
  WhatsApp, plantillas y planificador en verde; `ruff` limpio.
- **Dependencias o validaciones externas:** sigue pendiente el envio real contra un
  numero de Meta; esto elimina la causa conocida de fallo, no sustituye esa prueba.
- **Riesgo/punto probable de fallo:** el saneado se aplica al encolar. Un futuro
  camino que escriba directamente en `whatsapp_outbox` sin pasar por `queue_template`
  volveria a exponerlo; hoy no existe ninguno.
- **Diagnostico y rollback:** si un proactivo fallara, el motivo de Meta aparece en
  `/admin` -> Gestionar -> Entregas atascadas.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-20 — correo real entregado y Google validado en produccion

- **Autor/agente:** Claude.
- **Objetivo:** el founder cargo `BREVO_API_KEY` en Railway y pidio verificarlo. Se
  comprueba con un envio real, no con una lectura de configuracion.
- **Areas y archivos:** solo documentacion. `docs/Tareas-vivas.md` y
  `docs/Registro-QA.md`; ningun cambio en `src/`.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** recuperacion de contraseña disparada contra
  `https://bynoesis.com/recuperar`. HTTP 303 a `?sent=1` y el correo **llego** al buzon
  del founder con el remitente «Bynoesis». Queda demostrado que la clave es valida, que
  la via HTTPS atraviesa Railway —que bloquea SMTP— y que la cola entrega.
- **Dependencias o validaciones externas:** `smtp_real` **sigue pendiente a
  proposito**. Un envio a un buzon del propio dominio no demuestra entregabilidad:
  falta comprobar Gmail y Outlook sin caer en spam, que depende de la autenticacion
  del dominio en el DNS, mas factura al cliente final con PDF, invitacion de gestoria
  y reintento de la outbox sin duplicar.
- **Riesgo/punto probable de fallo:** el modo de fallo peligroso del correo es
  silencioso —entregado a la carpeta de spam— y no lo detecta ninguna prueba
  automatica. Solo se ve mirando una bandeja real de Gmail y de Outlook.
- **Diagnostico y rollback:** si un envio falla, el motivo del proveedor aparece en
  `/admin` -> Gestionar -> Entregas atascadas.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-20 — guia para conectar el correo

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidio que le explicara que es Brevo y una guia para
  conectarlo. El correo es el P0 mas visible: sin el, un cliente que olvide su
  contrasena no puede recuperarla.
- **Areas y archivos:** `docs/Conectar-Correo.html` + `.pdf` (nuevos) y
  `docs/Inicio.md`. Ningun cambio en `src/`.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** contenido verificado leyendo `adapters/email.py` (API
  primero, SMTP despues, degradacion a log si no hay ninguna), `config.py`
  (`BREVO_API_KEY`, `BREVO_API_URL`, `SMTP_FROM`, reintentos de 30 s a 1 h) y
  `readiness.py`. La peticion real a `api.brevo.com/v3/smtp/email` se comprobo
  interceptando la llamada HTTPS: construye remitente, destinatario, asunto y
  cabecera de clave correctamente. **El codigo esta bien; falta la clave.**
- **Dependencias o validaciones externas:** la conexion sigue pendiente del founder.
- **Riesgo/punto probable de fallo:** el paso que se salta todo el mundo es autenticar
  el dominio en el DNS. Sin el, los envios funcionan pero caen en spam, que es peor
  que no enviar porque no da senal de error. La guia lo marca como el paso critico.
- **Diagnostico y rollback:** cambio solo documental.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-20 — administracion entra a administrar, no a llevar un negocio

- **Autor/agente:** Claude.
- **Objetivo:** quitar errores del apartado de administracion y separar el perfil de
  administracion del de cliente, a peticion del founder.
- **Areas y archivos:** `web/routers/account.py` (`_account_destination` decide por
  identidad), `web/templates/admin.html` (vuelta a su propio panel),
  `web/routers/admin.py`, `tests/test_backend.py`, `docs/project-state.json`,
  `docs/Registro-QA.md`.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** una nueva que cubre las dos direcciones; 98 pruebas de
  administracion, login, sesion, onboarding y Google en verde; `ruff` limpio.
  Auditoria manual de las cinco rutas de administracion con la aplicacion levantada:
  todas 200 y sin errores en el log.
- **Dependencias o validaciones externas:** el correo sigue sin clave. Verificado que
  el adaptador construye bien la peticion a Brevo; **falta contratar `BREVO_API_KEY`**,
  que es la unica via que funciona en Railway porque bloquea los puertos SMTP.
- **Riesgo/punto probable de fallo:** si en el futuro una cuenta de administracion
  necesitara usar Bynoesis para su propio negocio, el enlace "Mi panel de negocio" se lo
  permite; nada queda inaccesible.
- **Diagnostico y rollback:** revertir el commit devuelve el aterrizaje anterior.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-20 — panel de gestion y entrada visible a administracion

- **Autor/agente:** Claude.
- **Objetivo:** el founder lo dijo claro: "despues de iniciar sesion con la cuenta de
  administrador, alli tendriamos que tener un panel donde poder gestionar todo". Tenia
  razon en las dos cosas: no habia panel de gestion y no habia forma de llegar a el.
- **Areas y archivos:** `web/deps.py` (expone `request.state.is_admin`),
  `web/templates/base.html` (enlace a administracion, solo si lo es),
  `web/templates/admin.html` (seccion `#gestion`), `web/routers/admin.py` (la accion
  admite `volver` y recibe la fecha de hoy), `web/static/app.css`,
  `tests/test_backend.py`, `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migracion:** ninguno. Reutiliza la ruta de suscripcion existente.
- **Pruebas ejecutadas:** dos nuevas —una para el panel y otra para el caso contrario,
  que una cuenta normal no ve el enlace ni entra—; 95 pruebas del bloque de
  administracion, seguridad y sesion en verde; `ruff` limpio; recorrido manual con el
  servidor levantado y tres cuentas reales.
- **Dependencias o validaciones externas:** ninguna.
- **Riesgo/punto probable de fallo:** `request.state.is_admin` solo decide si se pinta
  un enlace; el permiso real lo sigue comprobando `routers.admin._is_admin` contra la
  base de datos y, en produccion, exige sesion de Google. La prueba del caso contrario
  cubre que un cliente no vea esa entrada.
- **Diagnostico y rollback:** revertir el commit retira el panel y el enlace sin tocar
  datos ni permisos.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-20 — la puerta a la gestion de cuentas no se encontraba

- **Autor/agente:** Claude.
- **Objetivo:** el founder entro en `/admin` con Google y dijo "no me sale nada". No
  era un fallo de permisos ni de despliegue: produccion ya corria el release
  `26acdf38` con esquema 50. Era un problema de etiqueta.
- **Areas y archivos:** `web/templates/admin.html` y `web/templates/admin_account.html`.
  - El unico enlace a la ficha de una cuenta era un boton que ponia **"Diagnostico"**,
    en la ultima columna de la tabla. Era exacto cuando esa pagina solo mostraba
    recuentos; desde que gestiona permisos, acceso de personas y revocacion de
    gestorias, la etiqueta describia una fraccion de lo que hay detras y escondia el
    resto. Pasa a **"Gestionar"** y se destaca visualmente.
  - La cabecera de la ficha decia "Soporte tecnico · Diagnostico y conexiones" y
    "Diagnostico sin abrir el negocio del cliente". Ahora nombra lo que se hace
    —gestion de permisos y acceso— sin perder la frontera de privacidad, que se
    reformula como "se gestiona el acceso, no se abre el negocio".
- **Cambios de datos/migracion:** ninguno. Solo textos.
- **Pruebas ejecutadas:** 30 pruebas de administracion y soporte en verde; ambas
  plantillas compiladas con Jinja.
- **Dependencias o validaciones externas:** ninguna.
- **Riesgo/punto probable de fallo:** ninguno funcional. La leccion es de producto: al
  anadir capacidades a una pantalla hay que revisar el texto del enlace que lleva a
  ella, o la funcion existe y nadie la encuentra.
- **Diagnostico y rollback:** cambio de texto; revertir el commit restaura las
  etiquetas anteriores.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-20 — revisión del canal de Meta y espacio para las plantillas por oficio

- **Autor/agente:** Claude.
- **Objetivo:** dos encargos del founder. Revisar entero el canal de Meta antes de
  encenderlo, y dar pantalla propia a los catálogos por oficio, que existían en
  código y en dos endpoints pero no se veían por ningún sitio.
- **Áreas y archivos:** `src/noesis/whatsapp_templates.py` (nuevo),
  `src/noesis/web/whatsapp.py` (`template_param`, `MetaRejected`, retirada de
  `send_payment_reminder`), `src/noesis/trades.py` (`suggest_trade`,
  `catalog_overview`), `src/noesis/web/routers/invoicing.py` (endpoint del detalle),
  `src/noesis/web/routers/pages.py` y `templates/base.html` (alta de la página),
  `templates/oficios.html` (nueva), `tests/test_trade_templates.py` (nuevo),
  `scripts/build_estado_xlsx.py` (nuevo), `docs/Revision-Meta.md` (nuevo),
  `docs/Estado-Bynoesis.xlsx` (nuevo), `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migración:** ninguno. Los catálogos siguen en código.
- **Pruebas ejecutadas:** suite completa **437 pasan, 85 subtests, 0 fallos**. Ruff
  verde. Ocho pruebas nuevas cubren la adivinación del oficio, el IVA por partida,
  la no duplicación al cargar dos veces, el aislamiento entre negocios, la página y
  su API, y el contrato de las nueve plantillas de Meta.
- **Dependencias o validaciones externas:** el bloqueo de los cinco proactivos al
  titular **no se ha arreglado**: repartir el texto en huecos cambia la redacción
  que recibe el founder cada mañana y esa decisión es suya. Los cuerpos aprobables
  ya están escritos y `python -m noesis.whatsapp_templates` señala qué falta.
- **Riesgo/punto probable de fallo:** `template_param` aplana saltos de línea, así
  que un proactivo que hoy manda el mensaje entero en un hueco llegará como un
  párrafo corrido en lugar de fallar. Es un mal menor y transitorio: esas cinco
  plantillas no son aprobables todavía, de modo que nada empeora en producción.
- **Diagnóstico y rollback:** `pytest tests/test_trade_templates.py`. La página se
  desactiva quitando `oficios` de `_PAGES`; el saneado, retirando la llamada en
  `queue_template`. Nada de esto toca datos.
- **Aparte:** `Registro-cambios.md` y `Registro-QA.md` tenían marcadores de conflicto
  de Git **commiteados** desde `d32ff10`. Resueltos conservando ambos lados en orden
  cronológico; no se ha perdido ninguna entrada.
- **Estado de publicación:** local sobre `main`, pendiente de subir.

## 2026-08-19 — control de acceso por persona y guia de permisos

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidio poder dar y quitar acceso a nivel profesional, que el
  permiso decida lo que se puede hacer, resolver la parte de RGPD y privacidad, y una
  guia final que lo explique todo.
- **Areas y archivos:** `migrations.py` (migracion 50), `db.py`
  (`list_business_users`, `set_user_access`, `user_can_sign_in`, `AccessControlError`),
  `web/auth.py`, `web/routers/account.py`, `web/routers/admin.py`,
  `web/templates/admin_account.html`, `web/templates/login.html`,
  `tests/test_backend.py`, `docs/Permisos-y-acceso.html` + `.pdf` (nuevos, 9 paginas),
  `docs/Decisiones.md`, `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migracion:** **esquema 50**. Tres columnas en `users` con valor
  por defecto que conserva el acceso de todos los usuarios existentes, y un indice por
  `(business_id, is_active)`.
- **Pruebas ejecutadas:** cuatro nuevas, las cuatro verificadas por reversion; 185
  pruebas del bloque de seguridad y acceso en verde; migracion probada arriba, abajo,
  repetida y con un usuario preexistente; `ruff` limpio; `check_project_truth.py` en
  verde. La suite completa quedo cortada al 31% sin fallos por reinicio de sesion.
- **Dependencias o validaciones externas:** ninguna nueva. **Queda una tarea juridica
  del founder:** el contrato de encargo debe describir lo que hace el sistema
  —administracion gestiona acceso pero no lee contenido, bitacora encadenada,
  subencargados—; la guia lo deja escrito y `Tareas-vivas.md` lo tiene como P0.
- **Riesgo/punto probable de fallo:** el bloqueo se aplica en cuatro puntos; si en el
  futuro se anade otra via de inicio de sesion hay que comprobar
  `db.user_can_sign_in` tambien alli. La barrera de `current_user` cubre ese olvido,
  y su prueba la aisla a proposito.
- **Diagnostico y rollback:** revertir el commit deja la migracion aplicada pero sin
  usar; `migrations.downgrade(49)` retira las columnas si hiciera falta.
- **Estado de publicacion:** local / commit en `main`. **Falta desplegar el esquema
  50.**

## 2026-08-19 — guia completa para conectar Google

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidio la guia de Google. Al leer el codigo para escribirla
  aparece el dato que la ordena: **el panel de administracion esta cerrado en
  produccion** porque `ADMIN_REQUIRE_GOOGLE_OAUTH` vale `IS_PRODUCTION` y las
  credenciales no existen. La gestion de permisos recien construida es inalcanzable
  hasta conectarlo.
- **Areas y archivos:** `docs/Conectar-Google.html` + `.pdf` (nuevos, 7 paginas) y
  `docs/Inicio.md`. Ningun cambio en `src/`.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** contenido verificado leyendo `web/routers/account.py`
  (scopes `openid email profile`, `prompt=select_account`, comparacion del `state` con
  `hmac.compare_digest`, rechazo si `email_verified` no es verdadero o falta `sub`),
  `config.py`, `web/routers/admin.py`, `web/server.py` y `readiness.py`. HTML sin
  etiquetas sin cerrar y PDF valido comprobados.
- **Dependencias o validaciones externas:** la propia conexion sigue pendiente.
- **Riesgo/punto probable de fallo:** la guia no fija cifras de estado, pero si nombra
  rutas y variables; si cambian, hay que revisarla. El aviso sobre el panel bloqueado
  deja de aplicar en cuanto se carguen las credenciales.
- **Diagnostico y rollback:** cambio solo documental.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-19 — el soporte ya dice por que una entrega esta atascada

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidio recorrer dos situaciones reales —activar a un cliente
  a mano y atender un bug suyo— en vez de razonar sobre el codigo. Se levanto la
  aplicacion en local con un escenario real y se recorrieron ambas.
- **Areas y archivos:** `db.py` (`admin_support_delivery_failures`),
  `web/routers/admin.py`, `web/templates/admin_account.html`, `tests/test_backend.py`,
  `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migracion:** ninguno. Solo lectura sobre las colas existentes.
- **Pruebas ejecutadas:** prueba nueva verde y **verificada por reversion** (una fuga
  del destinatario la hace fallar); 109 pruebas de admin, soporte, aislamiento,
  seguridad y suscripcion en verde; `ruff` limpio; recorrido manual completo de los
  dos flujos contra el servidor real.
- **Dependencias o validaciones externas:** ninguna. El recorrido dejo ver que sin
  SMTP configurado toda entrega de correo se queda en cola: es el P0 de correo real.
- **Riesgo/punto probable de fallo:** el diagnostico devuelve el error del proveedor,
  que es texto ajeno. Se acota a 300 caracteres y se normalizan espacios; destinatario,
  asunto y cuerpo no se leen nunca. La prueba cubre esa frontera.
- **Diagnostico y rollback:** cambio acotado a una funcion de lectura y su seccion.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-19 — el propietario gestiona permisos; se retira el acceso a cuentas

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidio poder habilitar y deshabilitar perfiles. En una
  primera lectura se entendio que tambien queria entrar en el panel de cada empresa y
  se construyo; al aclararlo —"yo no quiero entrar a la cuenta, solo quiero gestionar
  los permisos"— esa parte se ha retirado por completo.
- **Areas y archivos:** `web/routers/admin.py` (ruta de suscripcion; **eliminadas** las
  de acceder y salir), `web/templates/admin_account.html` (permisos y que desbloquea
  cada plan), `tests/test_backend.py`, `docs/Decisiones.md`, `docs/project-state.json`,
  `docs/Registro-QA.md`. `web/deps.py`, `web/templates/base.html` y
  `web/static/app.css` quedan **sin cambios respecto al original**: se revirtio todo.
- **Cambios de datos/migracion:** ninguno. Reutiliza `set_subscription` y `set_trial`.
- **Pruebas ejecutadas:** prueba nueva verde; 108 pruebas de admin, soporte,
  aislamiento, seguridad y suscripcion en verde; `ruff` limpio;
  `check_project_truth.py` en verde. Comprobado por busqueda que no queda ninguna
  referencia a `admin_view_business`, `/acceder` ni `salir-de-cuenta` en el codigo.
- **Dependencias o validaciones externas:** activar desde administracion no cobra: es
  un alta manual y no sustituye la validacion pendiente de Stripe.
- **Riesgo/punto probable de fallo:** bajo. El guardian de aislamiento entre negocios
  no se toca; el cambio se limita a mover el estado de la suscripcion, que ya existia
  en `db`. Queda **sin efecto** la nota anterior sobre revisar el contrato de encargo:
  al no haber acceso a datos de cliente, no hay nada nuevo que declarar.
- **Diagnostico y rollback:** revertir el commit deja la gestion como estaba; los
  cambios de plan ya aplicados se deshacen desde la misma pantalla.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-19 — la suscripcion mostraba una marca ISO y anunciaba una prueba vencida

- **Autor/agente:** Claude.
- **Objetivo:** el founder abrio su cuenta y la cabecera decia
  `En prueba · hasta 2026-07-20T00:00:00`, un mes despues de vencer.
- **Areas y archivos:** `src/noesis/web/routers/pages.py` (calcula `trial_expired`),
  `src/noesis/web/templates/suscripcion.html` (filtro `date_es` y rotulo real),
  `src/noesis/web/static/app.css` (estado vencido en rojo),
  `tests/test_backend.py` (prueba nueva), `docs/project-state.json`,
  `docs/Registro-QA.md`.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** prueba nueva verde y **verificada por reversion** —sin la
  correccion falla—; 97 pruebas de suscripcion, planes y prueba gratuita en verde;
  `ruff` limpio; `check_project_truth.py` en verde.
- **Dependencias o validaciones externas:** ninguna. No toca Stripe ni permisos.
- **Riesgo/punto probable de fallo:** solo presentacion. Si otra pantalla imprime
  `trial_ends_at` sin `date_es`, repetira el mismo defecto; el filtro existe desde
  hace tiempo y varias plantillas podrian no usarlo.
- **Diagnostico y rollback:** revertir el commit devuelve la cabecera anterior sin
  afectar a datos.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-19 — los documentos dejan de fijar cifras que se desincronizan

- **Autor/agente:** Claude.
- **Objetivo:** la revision detecto que los tres documentos publicados afirmaban
  "esquema 47 y 469 pruebas". `project-state.json` ya va por 48 y 485, asi que los PDF
  mentian nueve dias despues de escribirse.
- **Areas y archivos:** `docs/WhatsApp-Como-funciona`, `docs/WhatsApp-Puesta-en-marcha`
  y `docs/Estrategia-Marketing` (html + pdf).
  - No se actualizan los numeros: se **eliminan**. `AGENTS.md` §5 ya lo prohibe —"no
    fijar conteos de pruebas ni migraciones: se desincronizan"— y la regla vale igual
    para un PDF que para el manual. Ahora remiten a `project-state.json`, que es la
    fuente viva.
  - Se conserva una unica mencion, fechada: "verificado sobre `main` el 10-ago-2026
    (esquema 47 entonces)". Es procedencia historica, no estado, y por eso no caduca.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** los tres HTML sin etiquetas sin cerrar, los tres PDF
  regenerados y validos (8, 16 y 13 paginas) y ninguno mas antiguo que su fuente.
  Revalidado ademas que **el fallo de plantillas multilinea sigue vivo** en `main`:
  `web/scheduler.py` conserva `"
".join(lines)` en dos puntos y `_meta_payload()`
  sigue sin sanear. Los documentos aciertan al darlo por abierto.
- **Dependencias o validaciones externas:** ninguna nueva.
- **Riesgo/punto probable de fallo:** cualquier documento que vuelva a fijar una cifra
  de estado caducara igual. La regla es remitir a `project-state.json`.
- **Diagnostico y rollback:** cambio solo documental.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-19 — revision del modelo economico: tres defectos corregidos

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidio revisar que todo funcionase. La revision encontro tres
  defectos reales en lo entregado los dias 10 y 11, todos ya en `main`.
- **Areas y archivos:** `analysis/build_modelo_economico.py`, `pyproject.toml` y el
  libro que genera.
  1. **Ruta absoluta de una carpeta temporal** codificada en el generador
     (`sys.path.insert` a un directorio de sesion). El script publicado no podia
     ejecutarse en ninguna otra maquina, ni en la misma tras limpiarse el temporal.
     Sustituida por un import normal con mensaje de ayuda si falta la libreria.
  2. **`openpyxl` no estaba declarado** en ninguna parte. Se anade el extra
     `analysis` a `pyproject.toml`: `pip install -e ".[analysis]"`.
  3. **Dos celdas mostraban `#NAME?` en Excel.** Las etiquetas `= Margen bruto` y
     `= RESULTADO` de la hoja `Calculadora` empiezan por `=`, asi que Excel las
     interpretaba como formula. Renombradas a `MARGEN BRUTO` y `RESULTADO DEL MES`,
     con la deteccion de totales por nombre en vez de por prefijo.
  - Ademas, seis avisos de `ruff` (E402 y F811) por imports duplicados a mitad de
     fichero, que el CI habria rechazado. Limpiados.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** el generador reproduce el libro publicado con **cero celdas
  de diferencia**. Barrido completo del libro: 1.014 referencias entre hojas, ninguna
  a una hoja inexistente, y **cero errores de formula** tras la correccion (antes
  dos). Contraste de los valores que **Excel calculo de verdad** con los datos que el
  founder introdujo (1 Autonomo, 5 Negocio, 2 Premium): ingreso 472 €, costes
  variables 53,64 €, servicio 103,96 €, fijos 3.565 €, resultado -3.250,60 € y
  equilibrio en 91 clientes; coincide con el calculo independiente en Python. Los
  cuatro HTML sin etiquetas sin cerrar, los tres PDF validos y ninguno mas antiguo que
  su fuente, y los cinco enlaces de `Inicio.md` resuelven. `ruff` limpio y
  `check_project_truth.py` en verde.
- **Dependencias o validaciones externas:** ninguna nueva.
- **Riesgo/punto probable de fallo:** el libro versionado conserva los valores 1/5/2
  que el founder introdujo en la calculadora; una regeneracion limpia los devuelve a
  cero. No afecta a ninguna formula.
- **Diagnostico y rollback:** `pip install -e ".[analysis]"` y despues
  `python analysis/build_modelo_economico.py`.
- **Estado de publicacion:** local / commit en `main`.
## 2026-08-14 — cierre de fricciones de confianza del piloto

- **Autor/agente:** Codex.
- **Objetivo:** eliminar respuestas técnicas y datos ambiguos en los recorridos
  comerciales, manteniendo la demostración estrictamente de solo lectura.
- **Áreas y archivos:** guardia de suscripción, asistente y prompts, portales de
  cliente/gestoría, resumen mensual, plantillas y regresiones de backend/demo.
- **Cambios de datos/migración:** ninguno; esquema 49 sin cambios. Se añade un campo
  calculado a la respuesta mensual, sin persistencia ni backfill.
- **Pruebas ejecutadas:** 3/3 focalizadas; **504/504** completas en 438,0 s; Ruff y
  `git diff --check` verdes.
- **Dependencias o validaciones externas:** falta el recorrido publicado en
  escritorio/móvil; no intervienen claves de Stripe, Meta, IA ni AEAT.
- **Riesgo/punto probable de fallo:** una nueva intención local de solo lectura debe
  añadirse explícitamente a la lista permitida de la demo; por defecto queda
  bloqueada. La caja mensual conserva su campo histórico `collected` para no romper
  consumidores y usa `invoiced_collected` solo para porcentajes de cohorte.
- **Diagnóstico y rollback:** reproducir `/api/{business_id}/chat` con una cuenta
  demo y verificar que no crece el historial; revisar redirecciones con
  `notice=readonly`/`ok=readonly`; comparar ambos campos en `/summary`. Revertir el
  commit no requiere rollback de base de datos.
- **Estado de publicación:** commit `ea1f5f3`, `main` y producción en el release
  `ea1f5f3e628f`; CI completo, humo PostgreSQL y `/ready` verdes con esquema 49.
  Pendiente recorrido visual autenticado.

## 2026-08-14 — portal Stripe autocontenido y fallo visible

- **Autor/agente:** Codex.
- **Objetivo:** corregir que los botones de gestionar, tarjeta, cancelación y cambio
  de plan parecieran inertes aunque la interfaz ya estuviera dibujada.
- **Áreas y archivos:** `adapters/billing.py`, rutas de cuenta, plantilla de
  suscripción, JavaScript público, regresiones de backend, mapa y estado documental.
- **Cambios de datos/migración:** ninguno; esquema 49 sin cambios.
- **Pruebas ejecutadas:** 7/7 focalizadas; **499/499** completas en 464,4 s; Ruff,
  `compileall`, `node --check` y `git diff --check` verdes.
- **Dependencias o validaciones externas:** falta el clic autenticado después del
  despliegue. Stripe puede rechazar upgrades si los precios tienen `tax_behavior`
  incompatible o sin especificar; tarjeta, cancelación y portal general no deben
  crear nunca una segunda suscripción.
- **Riesgo/punto probable de fallo:** permisos de la clave Stripe para crear una
  configuración de portal o catálogo fiscal incompatible. Si crearla falla, Bynoesis
  intenta el portal predeterminado; si también falla, muestra y audita el error.
- **Diagnóstico y rollback:** buscar `subscription_portal_failed` y el log
  `Stripe portal`; revisar la configuración con metadata
  `noesis_portal=noesis-v1`. Revertir el bloque vuelve a depender del portal manual,
  sin tocar suscripciones ni cobros existentes.
- **Estado de publicación:** commit `52c61f9`, `main` y producción en el release
  `52c61f9e6277`; `/ready` verde y esquema 49. Pendiente inspección autenticada del
  portal sandbox.

## 2026-08-14 — acciones reales para gestionar la suscripción

- **Autor/agente:** Codex.
- **Objetivo:** hacer funcionales gestión, tarjeta, upgrade mensual/anual y
  cancelación de una suscripción activa sin crear otro Checkout.
- **Áreas y archivos:** adaptador Stripe, rutas y contexto de suscripción, plantilla
  y estilos, regresiones HTTP/adaptador, mapa, decisión, conexión externa y estado.
- **Cambios de datos/migración:** ninguno; esquema 49 sin cambios.
- **Pruebas ejecutadas:** 4/4 focalizadas, **495/495** completas en 352,1 s,
  `compileall`, verdad documental y `git diff --check` verdes.
- **Dependencias o validaciones externas:** Stripe sandbox debe tener habilitados
  método de pago, cambio entre los seis precios y cancelación. Los deep links siguen
  la API oficial de Customer Portal; queda recorrerlos con la cuenta real de prueba.
- **Riesgo/punto probable de fallo:** una configuración incompleta del portal puede
  rechazar el flujo específico; el adaptador intenta entonces el portal general y,
  si tampoco abre, Bynoesis muestra un fallo sin aplicar cambios ni cargos.
- **Diagnóstico y rollback:** revisar `subscription_portal_requested`, los logs
  `Stripe portal (<acción>) fallo`, la entrega webhook y la configuración sandbox.
  Revertir este bloque conserva la suscripción, pero devuelve botones genéricos.
- **Estado de publicación:** commit `31d0c95`, `main` y producción en el release
  `31d0c95abcf0`; `/ready` verde y esquema 49. Pendiente recorrido humano sandbox.

## 2026-08-13 — plan actual sin doble Checkout

- **Autor/agente:** Codex.
- **Objetivo:** convertir la pantalla activa en gestión de una única suscripción y
  eliminar la posibilidad visible o manipulada de volver a comprar el mismo plan.
- **Áreas y archivos:** contexto en `web/routers/pages.py`; bloqueo y portal en
  `web/routers/account.py`; jerarquía en `templates/suscripcion.html`; estilos en
  `static/app.css`; regresión en `tests/test_backend.py`; decisión, mapa y estado.
- **Cambios de datos/migración:** ninguno; esquema 49 sin cambios.
- **Pruebas ejecutadas:** 3/3 focalizadas, **493/493** completas en 351,9 s, Ruff,
  `py_compile`, verdad documental y `git diff --check`.
- **Dependencias o validaciones externas:** el patrón adapta la gestión centralizada
  de Billing documentada oficialmente por OpenAI. Stripe debe tener habilitados en
  el portal los seis precios mensuales/anuales para que upgrade y anualidad sean
  efectivos.
- **Riesgo/punto probable de fallo:** si el portal no está configurado, Bynoesis falla
  cerrado y vuelve con `status=noportal`; nunca crea un Checkout alternativo activo.
- **Diagnóstico y rollback:** revisar el evento
  `subscription_change_requested`, la configuración del portal y la respuesta de
  `billing_portal/sessions`. Revertir reabre el riesgo de doble suscripción.
- **Estado de publicación:** commit `3c7bd03`, `main` y producción en el release
  `3c7bd034828a`, `/ready` verde y esquema 49. Pendiente comprobación sandbox del
  portal y sus cambios configurados.

## 2026-08-13 — recupera la activación Stripe sin repetir el pago

- **Autor/agente:** Codex.
- **Objetivo:** impedir que webhooks concurrentes de Stripe dejen una compra pagada
  en modo consulta y recuperar de forma segura el alta sandbox ya cobrada.
- **Áreas y archivos:** adaptador Stripe `adapters/billing.py`; estado transaccional
  en `db.py`; retorno y selector de plan en `web/routers/pages.py`; regresiones en
  `tests/test_backend.py`; estado, QA, pendientes y mapa documental.
- **Cambios de datos/migración:** ninguno; esquema 49 sin cambios.
- **Pruebas ejecutadas:** 4/4 focalizadas de Stripe, **492/492** de la suite completa
  en 390,9 s, `py_compile` y Ruff focalizado verdes.
- **Dependencias o validaciones externas:** Stripe sandbox entregó tres eventos con
  HTTP 200 y mantiene la suscripción activa. Falta validar el candidato publicado
  recargando el retorno ya pagado; no es necesario crear otro cobro.
- **Riesgo/punto probable de fallo:** clave sandbox o ids almacenados incoherentes
  impedirían la reconciliación de forma cerrada; nunca se concede acceso solo por
  parámetros de URL.
- **Diagnóstico y rollback:** revisar el estado de entrega en Stripe y los ids de
  cliente/suscripción del negocio. El evento de producto
  `subscription_reconciled_after_checkout` identifica la recuperación. Revertir el
  commit elimina la consulta de reparación y reabre la carrera de `pending`.
- **Estado de publicación:** commit `9f3dc48`, `main` y producción en el release
  `9f3dc48d9d4a`, `/ready` verde y esquema 49. Pendiente comprobación humana de la
  cuenta sandbox existente.

## 2026-08-13 — separa `/gestorias` del bloqueo privado de robots

- **Autor/agente:** Codex.
- **Objetivo:** corregir el rechazo de indexación de la página comercial de
  gestorías detectado por Google Search Console.
- **Áreas y archivos:** reglas de `robots.txt` en `web/routers/pages.py`, regresión
  en `tests/test_seo.py` y estado/QA/mapa documental.
- **Cambios de datos/migración:** ninguno; esquema 49 sin cambios.
- **Pruebas ejecutadas:** 11/11 de SEO, Ruff focalizado, verdad documental,
  JSON de estado y `git diff --check` verdes.
- **Dependencias o validaciones externas:** Search Console mostró que la prueba en
  vivo no podía indexar `/gestorias`. La página, canonical y sitemap respondían 200;
  la causa era semántica de robots: `Disallow: /gestoria` también coincide por
  prefijo con `/gestorias`.
- **Riesgo/punto probable de fallo:** usar de nuevo una regla privada sin `/` final o
  ancla `$` puede bloquear rutas públicas que empiecen igual.
- **Diagnóstico y rollback:** abrir `/robots.txt` y comprobar que existen
  `/gestoria$` y `/gestoria/`, que `/gestorias` no coincide y que el login puede leer
  su `noindex`. Revertir el commit restaura el patrón anterior, pero reabre el fallo.
- **Estado de publicación:** `main` y producción en el release `18104f0`, esquema 49;
  Googlebot recibe 200, canonical, `index, follow` y reglas de robots sin el prefijo
  conflictivo. CI completo [31681161643](https://github.com/noesisstudio/noesis/actions/runs/31681161643)
  verde. Search Console puede conservar el robots anterior en caché hasta 24 horas.

## 2026-08-13 — base SEO verificable y páginas por audiencia

- **Autor/agente:** Codex.
- **Objetivo:** convertir la configuración inicial de Search Console en una base
  técnica mantenible, sin prometer reseñas, frescura ni capacidades que Bynoesis no
  pueda demostrar.
- **Áreas y archivos:** rutas públicas y sitemap en `web/routers/pages.py`;
  cabeceras en `web/server.py`; metadatos y navegación en `site_base.html`;
  identidad estructurada en `web/deps.py`; páginas `site_autonomos.html` y
  `site_gestorias.html`; portada, icono, estilos responsive, textos públicos y
  `tests/test_seo.py`; `.secrets.baseline` actualiza únicamente la línea de una
  coincidencia histórica ya aceptada.
- **Cambios de datos/migración:** ninguno; esquema 49 sin cambios.
- **Pruebas ejecutadas:** 11/11 de SEO y **487/487** de la suite completa;
  Ruff sobre `src`/`tests`, verdad documental y `git diff --check` verdes.
- **Dependencias o validaciones externas:** el founder verificó la propiedad de
  dominio en Google Search Console, envió el sitemap y añadió usuarios. Google
  puede tardar días en rastrear de nuevo y en mostrar rendimiento. El primer CI
  dejó verde PostgreSQL y se detuvo porque el baseline de secretos conservaba la
  línea anterior de `project-state.json`; no apareció ningún hash nuevo.
- **Riesgo/punto probable de fallo:** canonical incorrecto si `NOESIS_BASE_URL`
  deja de ser el origen público, o una ruta pública nueva que no se añada a la lista
  indexable. Las áreas privadas envían `X-Robots-Tag: noindex, nofollow`.
- **Diagnóstico y rollback:** abrir `/robots.txt` y `/sitemap.xml`, inspeccionar
  title/description/canonical/OG y la cabecera de `/login`; las pruebas SEO fallan
  si se duplica un título, desaparece el H1 o se indexa una ruta privada. Revertir
  este commit restaura el sitemap y el armazón público anteriores.
- **Estado de publicación:** `main` y producción validados en el release `e5d1ac5`,
  esquema 49: `/health`, `/ready`, las 14 páginas, sitemap y `noindex` reales en
  verde. Baseline corregido para repetir el guardián completo; recrawl de Google
  pendiente.

## 2026-08-12 12:00 — editor documental con pie gráfico versionado

- **Autor/agente:** Codex.
- **Objetivo:** permitir que cada negocio adapte sus facturas e incluya distintivos
  obligatorios de ayudas o certificaciones sin convertir el documento fiscal en un
  lienzo libre ni alterar facturas ya emitidas.
- **Áreas y archivos:** migración 48, perfiles visuales y emisión en `db.py`, carga
  saneada en cuenta, PDF de factura/presupuesto/muestra, Ajustes responsive, pruebas
  y documentación viva.
- **Cambios de datos/migración:** añade pie gráfico y opciones a `businesses`, tabla
  `document_profiles` por versión y referencia multiempresa inmutable desde
  `invoices`; el histórico recibe una versión común por negocio sin duplicar imagen
  en cada fila.
- **Pruebas ejecutadas:** 3 nuevas, 485 completas y ciclo 0 → 48 → 0 → 48 verdes;
  Ruff, Bandit, detección de secretos y diff verdes. El primer pase completo detectó
  el orden ambiguo del índice compuesto PostgreSQL; se corrigió y el segundo pasó.
  Humo PostgreSQL real pendiente de CI.
- **Dependencias o validaciones externas:** ninguna API. Falta probar en escritorio
  y móvil con el distintivo real del founder.
- **Riesgo/punto probable de fallo:** imágenes desproporcionadas o antiguas; se
  validan bytes/píxeles, se recomprimen sin metadatos y el PDF limita altura, salta
  de página y degrada sin romper si un perfil histórico estuviera dañado.
- **Diagnóstico y rollback:** revisar `document_branding_updated`, última versión en
  `document_profiles`, `invoices.document_profile_id` y el PDF de muestra. Revertir
  la interfaz conserva perfiles; no retirar imágenes referenciadas por emitidas.
- **Estado de publicación:** commit `c30321c` en `main`, CI completo y humo
  PostgreSQL verdes; producción confirma el release y el esquema 48. Pendiente solo
  recorrido visual con el distintivo real del founder.

## 2026-08-12 — alta recuperable y preparada para el primer resultado

- **Autor/agente:** Codex.
- **Objetivo:** cerrar para el piloto la configuración posterior al registro sin
  perder el punto de avance ni presentar WhatsApp como conectado antes de serlo.
- **Áreas y archivos:** migraciones y estado de negocio en `migrations.py`/`db.py`;
  rutas de cuenta, Google, administración y WhatsApp; pantallas de negocio,
  operativa, revisión, suscripción e inicio; estilos responsive y pruebas HTTP.
- **Cambios de datos/migración:** esquema 49 añade estado recuperable de onboarding,
  selección comercial y decisión explícita de WhatsApp. Las cuentas históricas no
  se obligan a repetirlo; las ya completas se reconstruyen de forma compatible.
- **Pruebas ejecutadas:** 485/485 unitarias e integrales verdes; 9/9 de SEO;
  compilación; migración histórica focalizada. El ciclo 0→49→0→49 y las revisiones
  estáticas se registran al cerrar el commit.
- **Dependencias o validaciones externas:** ninguna nueva. Stripe, Meta y recorrido
  visual siguen requiriendo credenciales/servicios reales.
- **Riesgo/punto probable de fallo:** datos históricos incompletos, carga de imagen
  inválida o webhook de WhatsApp que no llegue; el recorrido no avanza en silencio.
- **Diagnóstico y rollback:** `/ready` debe informar esquema 49; revisar las columnas
  `onboarding_*`, `whatsapp_onboarding_choice` y eventos de producto. Revertir el
  commit; SQLite conserva las columnas al bajar para no perder el punto de avance.
- **Estado de publicación:** `main`, CI completo y humo PostgreSQL verdes;
  producción confirma release `8730826a79ab` y esquema 49. Recorrido visual y
  proveedores reales pendientes.

## 2026-08-11 12:00 — configuración reversible con permiso de soporte

- **Autor/agente:** Codex.
- **Objetivo:** resolver errores de configuración durante onboarding/soporte sin
  abrir acceso a fiscalidad, dinero, suscripción, integraciones o identidad.
- **Áreas y archivos:** DB y auditoría de soporte, router/pantalla administrativa,
  responsive, pruebas y documentación viva.
- **Cambios de datos/migración:** sin migración; reutiliza columnas y autorización
  temporal existentes.
- **Pruebas ejecutadas:** 2 pruebas nuevas, 22 del centro administrativo, 4
  focalizadas y suite completa **473/473** verde en 384 s; Ruff y verdad documental
  verdes.
- **Dependencias o validaciones externas:** CI
  [31478332206](https://github.com/noesisstudio/noesis/actions/runs/31478332206)
  completo; producción verificada en release `6a879b2b1153`, esquema 47 y HTTP 200
  en `/health` y `/ready`. Falta recorrido visual con una cuenta y autorización
  reales.
- **Riesgo/punto probable de fallo:** un formulario parcial no debe inventar valores;
  equipo y objetivo son obligatorios y muestran un estado sin seleccionar si faltan.
  Permiso, administrador y caducidad se comprueban en la transacción.
- **Diagnóstico y rollback:** buscar `admin.support_configuration_updated`,
  `grant_id`, `changed_fields` y estados before/after seudonimizados. Revertir el
  bloque devuelve ese alcance a solo lectura sin afectar otras funciones.
- **Estado de publicación:** commit `6a879b2b1153` en `main`, CI verde y desplegado
  y verificado en producción.

## 2026-08-11 11:25 — primera corrección segura del centro de soporte

- **Autor/agente:** Codex.
- **Objetivo:** permitir resolver errores de organización documental sin acceder
  como el cliente ni crear un editor administrativo universal.
- **Áreas y archivos:** DB y auditoría de soporte, router/pantalla administrativa,
  responsive, pruebas y documentación viva.
- **Cambios de datos/migración:** sin migración. Reutiliza la autorización temporal
  del esquema 43 y las columnas documentales existentes.
- **Pruebas ejecutadas:** 2 pruebas nuevas, 25 pruebas focalizadas y suite completa
  **471/471** verde en 340 s; Ruff, verdad documental y `git diff --check` verdes.
- **Dependencias o validaciones externas:** ninguna credencial ni proveedor. Falta
  recorrido visual con un titular que abra el alcance documental y un caso real.
- **Riesgo/punto probable de fallo:** formularios con carteras muy grandes y
  caducidad/revocación durante una intervención. La escritura revalida alcance e
  IDs en su misma transacción y falla cerrada.
- **Diagnóstico y rollback:** buscar
  `admin.support_document_metadata_updated`, `grant_id`, `item_id` y
  `changed_fields` en la bitácora. Revertir el bloque devuelve el centro a solo
  lectura sin deshacer documentos ya corregidos.
- **Estado de publicación:** `bf2df0d` en `main`; CI 31475120052 completo y humo
  PostgreSQL verdes. Producción responde release `bf2df0d7afe5`, esquema 47 y
  `/health`/`/ready` 200. Falta recorrido visual real.

## 2026-08-11 09:26 — archivo documental claro y demo bien clasificada

- **Autor/agente:** Codex.
- **Objetivo:** corregir la falsa agrupación de la demo y convertir Documentos en
  un archivo comprensible y cómodo desde móvil sin duplicar el motor existente.
- **Áreas y archivos:** sembrado comercial, pantalla/CSS de Documentos, prueba de
  demo/OCR, CI y documentación compartida de producto y WhatsApp.
- **Cambios de datos/migración:** sin migración. Al ejecutar la siembra explícita,
  seis archivos ficticios se crean o reparan por nombre de forma idempotente y se
  distribuyen en ingresos, gastos, tickets, pendientes y otros.
- **Pruebas ejecutadas:** 23 pruebas focalizadas verdes de demo, OCR, archivo,
  facturas recibidas, deduplicación, aislamiento y navegación; suite completa
  **469/469** verde en 344 s. Ruff, verdad documental y diff verdes. El primer CI
  pasó dependencias, secretos, seguridad, estática, verdad y humo PostgreSQL, pero
  canceló la suite sana al alcanzar el límite histórico de 15 minutos. Se amplía a
  25 para cubrir pruebas y ciclo de migraciones sin esconder un bloqueo ilimitado.
  El segundo CI pidió actualizar únicamente las tres líneas desplazadas de secretos
  de prueba ya conocidos en `.secrets.baseline`; no apareció hash ni hallazgo nuevo.
- **Dependencias o validaciones externas:** no añade proveedor ni credencial. La
  reparación de la demo publicada exige una ejecución explícita con
  `NOESIS_SEED_DEMO=true`. Revisión visual no ejecutada porque el founder indicó que
  el navegador gráfico provoca cierres de la aplicación; se verificó la captura
  aportada y la estructura renderizada mediante TestClient.
- **Riesgo/punto probable de fallo:** CSS responsive, selector de cámara y modal de
  vista previa son los puntos a recorrer en un teléfono real. Las facturas ambiguas
  continúan pendientes por diseño y no se fuerzan a ingreso o gasto.
- **Diagnóstico y rollback:** revisar `document_counts`, `kind` por nombre demo,
  petición `/document-archive` y consola del navegador. Revertir plantilla/CSS no
  altera documentos; revertir la reparación conserva los tipos ya corregidos.
- **Estado de publicación:** funcionalidad `065f8bb`, límite CI `633dcf6` y baseline
  `5bb715a` en `main`. CI 31470941717 completo y PostgreSQL verdes; producción
  responde release `5bb715a68217`, esquema 47 y `/health`/`/ready` 200. Falta
  revisión visual real y ejecutar una vez la reparación de la demo persistida.

## 2026-08-11 — calculadora por numero de clientes

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidio poder escribir cuantos clientes tiene y ver los costes
  y el equilibrio moverse. Las tablas anteriores usaban un mix porcentual, que no se
  puede tocar de forma intuitiva.
- **Areas y archivos:** `analysis/build_modelo_economico.py`.
  - Hoja `Calculadora` nueva, la segunda del libro para que sea lo primero que se toca.
    Tres celdas de entrada —clientes de cada plan— gobiernan seis bloques: ingreso
    mensual y anual, las siete lineas de coste variable desglosadas por plan y por
    cliente, coste de servicio, costes fijos, cuenta de resultados y distancia al
    equilibrio con veredicto automatico.
  - Los imports de `CellIsRule`, `ColorScaleRule` y `DataValidation` suben a la
    cabecera: la hoja nueva se construye antes de donde estaban declarados.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** replica independiente en Python. Con 66/42/12 clientes el
  libro debe dar ingreso 5.160 €, costes variables 447,00 €, servicio 1.111,25 €,
  fijos 3.565 € y **resultado +36,75 €/mes**, con contribucion media de 30,01 € y
  equilibrio en 119 clientes. Diecisiete hojas y referencias comprobadas al reabrir.
- **Dependencias o validaciones externas:** ninguna nueva.
- **Riesgo/punto probable de fallo:** la calculadora resta el opex fijo completo en vez
  del fijo prorrateado por cuenta que usa `Unit_Economics`, asi que su equilibrio da
  119 clientes y el de la hoja `Resumen` da 120. No es un error: son dos convenciones
  contables distintas y la de la calculadora es la mas directa. **El `.xlsx` sigue
  abierto en Excel y no ha podido regenerarse**; el archivo versionado va dos tandas
  por detras del generador.
- **Diagnostico y rollback:** `python analysis/build_modelo_economico.py`.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-11 — modelo economico completo y estrategia de marketing

- **Autor/agente:** Claude.
- **Objetivo:** cerrar el analisis economico con todo lo que el repositorio permite
  sostener y redactar la estrategia comercial de la empresa.
- **Areas y archivos:** documentacion y analisis; ningun cambio en `src/`.
  - `analysis/build_modelo_economico.py`: seis hojas nuevas hasta dieciseis en total.
    `Escenarios` con selector pesimista/base/optimista y validacion de datos;
    `PyG_Proyeccion` a 24 meses con cartera, MRR, margen, caja acumulada, ARR y los
    derivados de mes de rentabilidad y caja minima; `Sensibilidad` como matriz de
    equilibrio opex x contribucion con escala de color; `Capacidad_Soporte`, que
    traduce cuentas en horas de persona y marca el punto de contratacion;
    `KPIs_Piloto` con los indicadores comprometidos en Tareas-vivas.
  - `docs/Estrategia-Marketing.html` + `.pdf` (nuevos): estado real de partida, cliente
    ideal y quien queda fuera, mensaje jerarquizado por lo demostrable, posicionamiento
    frente a Forjia y a los ERP, cuatro fases con puerta de salida, canales ordenados
    por riesgo economico, techos de CAC derivados del margen, uso de IA con sus limites
    y siete vias de escape con criterio de parada.
  - `docs/Inicio.md`: ambos entran en el mapa de contenido.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** libro regenerado en copia de verificacion y reabierto con
  openpyxl: dieciseis hojas y referencias cruzadas comprobadas. Reparto del equilibrio
  validado a mano (120 cuentas = 66/42/12, contribuyen 3.524 € frente a 3.500 € de
  opex; por plan unico 169/101/62). Techos de CAC derivados de la contribucion a doce
  meses: 250/419/683 €. HTML sin etiquetas sin cerrar antes de imprimir.
- **Dependencias o validaciones externas:** los objetivos comerciales del documento son
  propuestas del analisis, no compromisos acordados entre los socios.
- **Riesgo/punto probable de fallo:** el `.xlsx` no pudo regenerarse porque estaba
  abierto en Excel; el libro versionado conserva las once hojas anteriores y **le
  faltan las seis nuevas** hasta ejecutar de nuevo el generador. La estrategia asume el
  mix 55/35/10 y el opex de 3.500 €, ambos sin validar.
- **Diagnostico y rollback:** `python analysis/build_modelo_economico.py` regenera el
  libro; admite ruta alternativa como primer argumento.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-11 — desglose del equilibrio por plan y hoja de publicidad

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidio ver en el punto de equilibrio cuantos clientes de cada
  plan hacen falta, y anadir el gasto variable en publicidad.
- **Areas y archivos:** `analysis/build_modelo_economico.py` y el libro que genera.
  - `Escala_Breakeven`: dos tablas nuevas. La primera reparte las cuentas de equilibrio
    segun el mix y da clientes, ingreso y contribucion por plan. La segunda calcula
    cuantos clientes harian falta si toda la cartera fuera de un solo plan, que es el
    argumento para decidir a que plan dedicar el esfuerzo comercial.
  - `Ads_Captacion` (hoja nueva): embudo completo desde presupuesto y coste por clic
    hasta CAC real, con LTV, LTV/CAC, meses de recuperacion y un veredicto automatico.
    Incluye el impacto de la campana sobre el punto de equilibrio: cuantos clientes
    adicionales debe traer solo para pagarse y en cuantos meses.
  - El generador acepta ahora una ruta de salida opcional y falla con un mensaje claro
    si el libro esta abierto en Excel, en vez de con una traza de PermissionError.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** libro regenerado en una copia de verificacion y reabierto con
  openpyxl: once hojas, referencias de las tablas nuevas comprobadas una a una y las
  siete entradas de campana confirmadas vacias. Comprobacion manual del reparto: 120
  cuentas con mix 55/35/10 dan 66/42/12, que contribuyen 3.524 € frente a 3.500 € de
  opex. Por plan unico: 169 Autonomo, 101 Negocio o 62 Premium.
- **Dependencias o validaciones externas:** ninguna cifra de embudo publicitario consta
  en el repositorio; las siete entradas quedan vacias a proposito.
- **Riesgo/punto probable de fallo:** el CAC de 150 € que ya estaba en el modelo es un
  supuesto sin validar; la hoja lo contrasta contra el CAC real en cuanto se rellene el
  embudo. Hasta entonces, todo el bloque de salud de captacion muestra "Faltan datos".
- **Diagnostico y rollback:** `python analysis/build_modelo_economico.py` regenera el
  libro; admite una ruta alternativa como primer argumento.
- **Estado de publicacion:** local / commit en `main`. El `.xlsx` estaba abierto en
  Excel al cerrar el commit y debe regenerarse tras cerrarlo.

## 2026-08-11 — modelo economico en Excel con doble escenario de coste

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidio un modelo economico completo en Excel, con todos los
  costes y sin datos inventados, a partir de una tabla de costes que le paso un
  tercero. El documento de referencia no llego; solo la tabla.
- **Areas y archivos:** solo documentacion y analisis, ningun cambio en `src/`.
  - `docs/Bynoesis-Modelo-Economico.xlsx` (nuevo): diez hojas con formulas vivas
    —Resumen, Supuestos, Unit_Economics, Hipotesis_Externa, Comparador,
    Anual_vs_Mensual, Escala_Breakeven, Opciones_IA, Datos_Pendientes y Fuentes.
    Entradas en azul, calculos en negro, convencion de modelo financiero.
  - `analysis/build_modelo_economico.py` (nuevo): generador reproducible con openpyxl.
    Sustituye a `build_unit_economics.mjs`, que dependia de `@oai/artifact-tool`, una
    libreria no disponible en este entorno.
- **Cambios de datos/migracion:** ninguno.
- **Pruebas ejecutadas:** replica independiente del modelo en Python. Las formulas del
  libro reproducen exactamente las cifras publicadas en
  `Unit-economics-y-cerebro-interno.md`: COGS 1,48 / 3,04 / 18,47 €, margen bruto
  94,9 / 93,8 / 81,3 % y contribucion 20,83 / 34,89 / 56,96 €. El break-even
  calculado da 120 cuentas, el mismo del analisis. Libro reabierto con openpyxl para
  comprobar que las diez hojas y las formulas persisten.
- **Dependencias o validaciones externas:** las tarifas son del 15/07/2026 y pueden
  haber cambiado. La tabla externa no tiene fuente ni fecha conocidas.
- **Riesgo/punto probable de fallo:** el modelo es un escenario de planificacion, no
  una contabilidad. La hoja `Datos_Pendientes` recoge las dieciseis cifras que no
  constan en el repositorio —forma juridica, reparto societario, retiradas de los dos
  socios, cuota de autonomos, gestoria, factura real de Railway, capital aportado,
  ingresos y clientes actuales, CAC y churn observados— y se han dejado **vacias a
  proposito**. Mientras lo esten, ningun total del libro describe la empresa real.
  Ademas, la hipotesis externa (6,49 €/usuario) multiplica por 4,4 el COGS estimado
  del plan Autonomo; el comparador cuantifica el impacto en margen.
- **Diagnostico y rollback:** el libro se regenera con
  `python analysis/build_modelo_economico.py`. Cambio solo documental.
- **Estado de publicacion:** local / commit en `main`.

## 2026-08-10 21:15 — segundo factor para la cartera profesional

- **Autor/agente:** Codex.
- **Objetivo:** proteger el acceso multiempresa de las gestorías antes de abrirlo a
  terceros, sin crear otra identidad ni depender de una API externa.
- **Áreas y archivos:** migración/DB de cuentas profesionales, módulo TOTP, login y
  seguridad de gestoría, plantillas/CSS, pruebas y documentación viva.
- **Cambios de datos/migración:** esquema 46→47. Añade activación MFA, hashes de
  recuperación, último contador consumido y fecha de alta. No activa MFA ni cambia
  sesiones o accesos existentes.
- **Pruebas ejecutadas:** 5 focalizadas verdes; suite completa **469/469** en 335 s,
  Ruff y diff verdes. Tras sacar los códigos en claro de la sesión, las 4 pruebas
  MFA volvieron a pasar. El primer CI confirmó migración y humo PostgreSQL, pero
  `detect-secrets` detuvo la suite al reconocer dos contraseñas ficticias de prueba;
  quedaron marcadas en su misma línea como fixtures permitidos, sin modificar la
  línea base ni relajar el detector. El hook completo, Ruff, diff y las 4 pruebas
  MFA volvieron a quedar verdes antes del commit correctivo.
- **Dependencias o validaciones externas:** no usa credenciales ni proveedor. CI,
  PostgreSQL y despliegue están validados; faltan recorrido con autenticador,
  gestoría real, revisión visual y revisión externa.
- **Riesgo/punto probable de fallo:** rotar `NOESIS_SECRET` invalida TOTP; conservar
  y probar códigos de recuperación antes de una rotación. Relojes con más de 30 s de
  desfase fallarán cerrado. La recuperación de contraseña aún no está construida.
- **Diagnóstico y rollback:** revisar `mfa_enabled`, `mfa_last_counter`,
  `mfa_recovery_hashes`, `session_version` y límites `gestoria-mfa/security`. Revertir
  el commit desactiva las rutas; mantener columnas 47 inertes evita perder acceso.
- **Estado de publicación:** funcionalidad `9b7d053` y correctivo de prueba
  `40d5645` en `main`; CI 31411139501 completo y PostgreSQL verdes. Producción
  verificada con release `40d564555c07`, esquema 47 y HTTP 200 en portada,
  `/acceso` y `/gestoria/login`.

## 2026-08-10 19:30 — cobro seguro y planes coherentes en todos los canales

- **Autor/agente:** Codex.
- **Objetivo:** impedir activaciones erróneas por webhooks Stripe desordenados y
  hacer que cada plan entregue exactamente las funciones publicadas, sin atajos por
  API, asistente, WhatsApp o portales.
- **Áreas y archivos:** billing, DB/migraciones, webhook Stripe, middleware web,
  cerebro/herramientas, WhatsApp, portales de trabajador y gestoría, scheduler,
  navegación/Ajustes/Suscripción, catálogo público, tests y documentación viva.
- **Cambios de datos/migración:** esquema 45→46. Añade a `businesses` el instante,
  prioridad e id del último evento Stripe aplicado. No cambia planes, estados ni
  facturas existentes. El nombre comercial del plan de 99 € pasa de “Sin Límites”
  a “Premium”; precios y límites permanecen iguales.
- **Pruebas ejecutadas:** 12 pruebas focalizadas de migración, activación, upgrade,
  estados, desorden, facturas aisladas y permisos; Ruff y diff verdes; suite
  completa final **465/465** en 338 s. Un Checkout superior no concede plan ni
  permisos antes de la confirmación verificable de Stripe y el `price_id` vigente
  gobierna los cambios desde su portal. Una pasada anterior tuvo un bloqueo temporal
  de limpieza SQLite en Windows; la prueba aislada y la repetición completa pasaron.
- **Dependencias o validaciones externas:** ninguna credencial usada. Faltan Stripe
  test/live, PostgreSQL del CI, despliegue/esquema 46 y recorrido visual.
- **Riesgo/punto probable de fallo:** metadata o `price_id` incorrectos en Stripe,
  cuenta histórica con plan no reconocido que cae al núcleo Autónomo, plantilla
  que no reciba `entitlements` o una ruta premium futura no añadida a la matriz.
- **Diagnóstico y rollback:** revisar `subscription_status`, `plan`,
  `stripe_event_created_at`, `stripe_event_priority`, `stripe_event_id`, eventos de
  producto y respuesta `plan_upgrade_required`. Para aislar, revertir el commit
  detiene la guardia; no bajar el esquema en producción porque las columnas son
  compatibles e inertes para versiones anteriores.
- **Estado de publicación:** commit `c63bf0e` en `main`; CI 31407830116 verde, humo
  PostgreSQL verde y producción validada con release `c63bf0e13d0d`, esquema 46 y
  portada HTTP 200. Falta la validación real de Stripe test y el recorrido visual.

## 2026-08-10 11:45 — WhatsApp multicanal y coordinación del equipo

- **Autor/agente:** Codex.
- **Objetivo:** separar el canal interno de Bynoesis de la recepción comercial de cada
  negocio, quitar interrupciones al titular y garantizar que clientes, documentos,
  conversaciones y costes nunca se crucen entre empresas.
- **Áreas y archivos:** migración/DB, motor y outbox de WhatsApp, resumen diario,
  routers de equipo, canal comercial y administración, pantallas
  Clientes/Equipo/Ajustes/soporte, estilos, pruebas específicas y documentación viva.
- **Cambios de datos/migración:** esquema 44→45. Añade conexiones WABA/número por
  negocio, contactos, conversaciones, inbox, relación de salida con conexión,
  aportaciones revisables del equipo y permisos de rol. No modifica facturas
  emitidas ni crea asientos a partir de mensajes históricos.
- **Pruebas ejecutadas:** migración limpia a 45, guardia de DDL PostgreSQL, 41 tests
  focalizados, Ruff, `compileall`, diff y suite completa **432/432** en 326 s.
- **Dependencias o validaciones externas:** ninguna credencial usada. Meta real,
  plantillas, medios, Embedded Signup/alta de activos y dos WABA siguen pendientes.
- **Riesgo/punto probable de fallo:** configuración incorrecta de WABA/Phone Number
  ID, plantilla no aprobada, mensaje fuera de 24 h, OCR real deficiente o asociación
  manual equivocada. El código falla cerrado ante receptor/WABA desconocido y no
  convierte documentos o costes sin revisión. También bloquea cualquier teléfono
  central con más de una identidad interna en vez de escoger un negocio.
- **Diagnóstico y rollback:** comprobar `/ready`=45, `whatsapp_connections`, inbox,
  outbox con `connection_id`, webhook events y aportaciones pendientes. Revertir el
  código detiene el canal empresarial; no bajar la migración en producción sin copia
  porque eliminaría conversaciones y aportaciones creadas desde el despliegue.
- **Estado de publicación:** commit `a803da4` en `main`; CI general/PostgreSQL verde
  y producción verificada con release `a803da4343e6`, `/ready` y esquema 45. La
  validación extremo a extremo con Meta real permanece pendiente.

## 2026-08-10 — runbook y explicación de WhatsApp, actualizados al modelo multicanal

- **Autor/agente:** Claude.
- **Objetivo:** el founder pidió entender el canal multicanal que construyó el socio y
  dejar la documentación al día. Los dos documentos se escribieron primero sobre una
  rama con 46 commits de retraso; se rehacen contra `main` y se trasladan aquí.
- **Áreas y archivos:** solo documentación, ningún cambio en `src/`.
  - `docs/WhatsApp-Como-funciona.html` + `.pdf` (nuevos): los dos canales, el enrutado
    por receptor con sus tres salidas, las cuatro reglas de negocio (identidad única,
    aportación pendiente, permisos cerrados por defecto, bandeja de equipo), el
    recorrido de un coste, la matriz de quién ve qué y los límites deliberados.
  - `docs/WhatsApp-Puesta-en-marcha.html` + `.pdf` (nuevos): runbook rehecho. Sustituye
    la premisa antigua de «un único número para todos los negocios» por las dos clases
    de número, añade la fase de alta de un número comercial desde administración
    (`pending` -> probar -> `active`), la exigencia de que el usuario de sistema tenga
    concedidos los activos de cada cliente, y una prueba de aceptación en dos bloques
    con el aislamiento entre dos negocios.
  - `docs/Inicio.md`: ambos entran en el mapa de contenido.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** ninguna ejecutable. Modelo verificado contra
  `web/whatsapp.py` (`_handle_inbound`), `web/routers/whatsapp_business.py`, `db.py`
  (`central_whatsapp_identity`, `resolve_worker_submission`) y la migración 45. HTML
  comprobado sin etiquetas sin cerrar antes de imprimir cada PDF.
- **Dependencias o validaciones externas:** las tareas de Meta siguen abiertas; los
  documentos las ordenan, no las cierran.
- **Riesgo/punto probable de fallo:** **hallazgo abierto y verificado hoy sobre
  `main`.** Meta rechaza los parámetros de plantilla con saltos de línea, tabuladores
  o más de cuatro espacios seguidos. `web/scheduler.py` sigue pasando
  `"
".join(lines)` como parámetro único en resumen diario, semanal, cierre, aviso
  fiscal y aviso de cobros, y `_meta_payload()` no lo sanea. Los cinco proactivos
  agotarán reintentos contra un número real; las pruebas no lo ven porque simulan Meta.
- **Diagnóstico y rollback:** cambio solo documental.
- **Estado de publicación:** local / commit en `main`.
## 2026-08-08 21:05 — soporte temporal, CFO real y términos reforzados

- **Autor/agente:** Codex.
- **Objetivo:** preparar soporte seguro para el piloto, sustituir márgenes supuestos
  por costes observables y aclarar responsabilidad/rectificación en los términos.
- **Áreas y archivos:** migraciones/DB, Ajustes, centro admin, CFO, términos, tests y
  documentación operativa.
- **Cambios de datos/migración:** 42→44; grants temporales y ledger mensual
  protegido contra `UPDATE`/`DELETE` también en base de datos. No se modifica
  contenido de cliente ni facturas emitidas.
- **Pruebas ejecutadas:** permisos entre negocios y rechazo a un usuario del mismo
  negocio que no sea el titular, creación/revocación HTTP, auditoría, render admin,
  costes reales/previsión/ajuste, inmutabilidad, cálculos y downgrade; suite completa
  426/426 y Ruff verdes.
- **Dependencias o validaciones externas:** ninguna credencial. Términos pendientes
  de abogado; recuperación externa y RPO/RTO requieren otra infraestructura.
- **Riesgo/punto probable de fallo:** formulario multipart de alcances, caducidad en
  reloj del servidor, datos CFO incompletos o interpretación jurídica del texto.
- **Diagnóstico y rollback:** revisar eventos `support.*`/`admin.platform_cost_*`,
  `/ready`=44 y ledger del mes. El downgrade elimina solo estas tablas; el
  diagnóstico de solo lectura y las cuentas siguen funcionando.
- **Estado de publicación:** commit `f472d08` en `main`, CI general/PostgreSQL verde
  y producción verificada con release `f472d08d85cb` y esquema 44.

## 2026-08-08 20:15 — documentos comerciales y OCR listos para validar en piloto

- **Autor/agente:** Codex.
- **Objetivo:** completar la personalización profesional de facturas/presupuestos y
  preparar lectura privada de tickets en catalán, castellano e inglés.
- **Áreas y archivos:** migración y DB; perfil de marca; creador/listado/portal de
  presupuestos; PDF compartido; OCR, clasificador y Railpack; pruebas y fuentes de
  verdad.
- **Cambios de datos/migración:** esquema 41→42. Añade preferencias documentales al
  negocio y notas/evidencia de decisión al presupuesto; no modifica ninguna factura
  emitida ni sus disparadores.
- **Pruebas ejecutadas:** migración descendente/ascendente, branding, PDF, aislamiento
  del portal, decisión trazable, PDF escaneado, clasificación e importes trilingües;
  suite completa 424/424 y Ruff verdes.
- **Dependencias o validaciones externas:** Railpack añade `tesseract-ocr-cat`.
  Falta verificar que la imagen real lo instala y medir precisión con corpus real.
- **Riesgo/punto probable de fallo:** paquete catalán no disponible en la imagen,
  maquetación PDF con textos extremos o migración 42 pendiente en producción.
- **Diagnóstico y rollback:** `/api/{business_id}/documents/ocr-status` informa los
  idiomas; `/ready` debe mostrar esquema 42. El downgrade elimina solo preferencias
  nuevas y evidencia de presupuestos; revertir código no altera facturas emitidas.
- **Estado de publicación:** local verificado; pendiente commit, push y despliegue.

## 2026-08-08 18:03 — diagnóstico de soporte por cuenta sin puerta trasera

- **Autor/agente:** Codex.
- **Objetivo:** permitir que dirección diagnostique incidencias de un negocio sin
  abrir ni exponer su contenido operativo.
- **Áreas y archivos:** lectura agregada en `db.py`, ruta y pantalla interna de
  administración, enlace desde cuentas, responsive, prueba y documentación viva.
- **Cambios de datos/migración:** ninguno; esquema 41. Cada consulta añade un evento
  a la bitácora de seguridad existente.
- **Pruebas ejecutadas:** prueba específica de autorización, privacidad y auditoría;
  suite completa 423/423 en la segunda pasada; Ruff, `compileall`, verdad del
  proyecto y diff verdes. La primera pasada tuvo un bloqueo temporal de Windows al
  borrar la base de una prueba OCR; esa prueba aislada y la repetición completa
  quedaron verdes.
- **Dependencias o validaciones externas:** ninguna credencial nueva. En producción
  el panel continúa exigiendo Google OAuth configurado.
- **Riesgo/punto probable de fallo:** una consulta agregada sobre una tabla grande o
  una plantilla admin en móvil; no hay mutaciones ni lectura de contenidos.
- **Diagnóstico y rollback:** abrir «Diagnóstico» desde Cuentas y buscar el evento
  `admin.support_snapshot_viewed`. Revertir la ruta/vista no afecta datos de negocio;
  los eventos de auditoría ya escritos se conservan.
- **Estado de publicación:** commit `8e9f9c4` en `main`, CI completo y humo
  PostgreSQL verdes; producción confirmó release `8e9f9c412880` y esquema 41.
  Pendiente solo el recorrido visual autenticado.

## 2026-08-08 — archivo del titular alineado con gestoría

- **Autor/agente:** Codex.
- **Objetivo:** que el autónomo encuentre y previsualice sus papeles por período y
  tipo con la misma clasificación que verá su despacho.
- **Áreas y archivos:** lectura documental compartida, router, pantalla Documentos,
  estilos, pruebas, estado y trazabilidad. Incluye la retirada del retorno residual
  señalado por Ruff en el endpoint rectificativo anterior.
- **Cambios de datos/migración:** ninguno; esquema 41. No mueve ni copia archivos.
- **Pruebas ejecutadas:** 37/37 focalizadas; suite completa 422/422; `ruff` y
  `compileall` verdes.
- **Dependencias o validaciones externas:** ninguna. OCR y preview usan el recorrido
  local ya existente.
- **Riesgo/punto probable de fallo:** representación responsive o generación de
  primera página de un PDF real. El endpoint es acotado, autenticado y `no-store`.
- **Diagnóstico y rollback:** abrir Documentos, cambiar T/año/tipo y previsualizar;
  comparar con Documentos de la gestoría en el mismo período. Revertir no pierde
  datos porque la organización es una lectura de metadatos existentes.
- **Estado de publicación:** commit `84ad8c3` en `main`; CI completo y humo
  PostgreSQL verdes. Despliegue y recorrido visual aún no verificados.

## 2026-08-08 — rectificativas guiadas sin alterar la factura emitida

- **Autor/agente:** Codex.
- **Objetivo:** permitir corregir un importe erróneo de forma entendible, trazable
  y compatible con la inmutabilidad fiscal del motor nativo.
- **Áreas y archivos:** motor y listado de facturas, API, pantalla de facturación,
  estilos, pruebas y documentación viva.
- **Cambios de datos/migración:** ninguno; esquema 41. Se reutilizan relación,
  motivo y tipo rectificativo existentes.
- **Pruebas ejecutadas:** 5/5 focalizadas y suite completa 421/421 mediante
  `unittest`; `compileall` y `git diff --check` verdes.
- **Dependencias o validaciones externas:** ninguna credencial. La modalidad por
  sustitución queda pendiente de validar con asesoría y XSD AEAT.
- **Riesgo/punto probable de fallo:** consulta correlacionada nueva en el listado o
  diferencias SQLite/PostgreSQL al bloquear el original. El CI debe ejecutar humo
  PostgreSQL antes de darlo por publicado.
- **Diagnóstico y rollback:** crear una F1/F2, emitirla, abrir «Rectificar», guardar
  y revisar el borrador; comprobar que el total original no cambia y que no se crea
  un segundo borrador. Revertir este commit conserva datos porque no migra esquema.
- **Estado de publicación:** commit `6a0e961` en `main`; humo PostgreSQL verde. La
  suite del CI se detuvo por un retorno residual de Ruff, corregido en el siguiente
  commit junto con el archivo documental.

## 2026-08-08 — corrige vulnerabilidades conocidas de pypdf

- **Autor/agente:** Codex.
- **Objetivo:** desbloquear el guardián de dependencias sin rebajar el control de
  seguridad que detectó dos CVE nuevas en el lector local de PDF.
- **Áreas y archivos:** `pyproject.toml`, `uv.lock`, QA y bitácora.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** `uv run pip-audit` sin vulnerabilidades conocidas y 40/40
  pruebas de PDF/OCR, facturas recibidas, copias y seguridad verdes.
- **Dependencias o validaciones externas:** `pypdf` pasa de 6.14.2 a 6.15.0, versión
  corregida indicada por los avisos CVE-2026-71852 y CVE-2026-71870 del CI.
- **Riesgo/punto probable de fallo:** cambios de parsing en PDF digitales. Se cubren
  extracción acotada, PDF escaneado, documentos y copias; el CI repetirá la suite.
- **Diagnóstico y rollback:** ejecutar `uv run pip-audit` y las pruebas documentales.
  No volver a 6.14.2; ante incompatibilidad, subir a una versión 6.x posterior.
- **Estado de publicación:** `b4f502b` desplegado y verificado en producción;
  `/ready` devuelve esa release y esquema 41. CI completo y humo PostgreSQL verdes.

## 2026-08-08 — puerta única para negocio y gestoría

- **Autor/agente:** Codex.
- **Objetivo:** hacer visible el canal profesional desde la web sin confundir al
  autónomo, la gestoría ni el cliente final y sin duplicar autenticación.
- **Áreas y archivos:** rutas públicas, selector y logins, solicitud de acceso,
  estilos responsive, pruebas SEO/alta y documentación viva.
- **Cambios de datos/migración:** ninguno; esquema 41. La solicitud profesional
  reutiliza `access_requests` y no crea identidad ni relación de acceso.
- **Pruebas ejecutadas:** 35/35 focalizadas de SEO, solicitudes y seguridad y suite
  completa 417/417 mediante `unittest`; `compileall`, `check_project_truth.py` y
  `git diff --check` verdes. CI queda antes de confirmar publicación real.
- **Dependencias o validaciones externas:** ninguna credencial. Falta QA visual real
  de escritorio/móvil tras desplegar porque no se usa el navegador que cierra Codex.
- **Riesgo/punto probable de fallo:** enlaces públicos cacheados o pérdida del perfil
  al devolver un error del formulario. Las redirecciones conservan `perfil=gestoria`
  y los assets llevan versión.
- **Diagnóstico y rollback:** comprobar `/acceso`, `/login`, `/gestoria/login`,
  `/solicitar-acceso?perfil=gestoria` y que `gestoria_business_access` no cambie.
  Revertir el commit devuelve los enlaces directos anteriores sin tocar datos.
- **Estado de publicación:** selector en `0af37af` y actualización de seguridad en
  `b4f502b`; producción verificada en esta última release y esquema 41. Falta QA
  visual del founder en escritorio y móvil.

## 2026-08-07 12:47 — expediente de gestoría separado por trabajo

- **Autor/agente:** Codex.
- **Objetivo:** reducir densidad y desorientación: que el despacho vea una sola tarea
  cada vez y entienda siempre cliente, período y apartado activo.
- **Áreas y archivos:** router/plantillas/CSS de gestoría, prueba de regresión,
  estado, mapa, QA y fuente de verdad.
- **Cambios de datos/migración:** ninguno; conserva esquema 41 y todos los cálculos,
  documentos, perfiles, solicitudes y permisos existentes.
- **Pruebas ejecutadas:** Ruff verde; 14/14 de `GestoriaTestCase`; suite completa
  415/415. Render de las cinco secciones y retornos de formularios cubiertos con
  FastAPI/TestClient.
- **Dependencias o validaciones externas:** ninguna API nueva. Ocho capturas reales
  del founder sirvieron de evidencia del problema anterior.
- **Riesgo/punto probable de fallo:** perder año, trimestre o filtro al cambiar de
  vista o volver de un POST. Los parámetros aceptados se limitan y las redirecciones
  tienen pruebas específicas.
- **Diagnóstico y rollback:** comprobar `section` en `/gestoria/cliente/{id}`, estado
  activo del submenú y `Location` de perfil/documento/solicitud. Revertir plantillas,
  CSS y router restaura la página única sin tocar datos.
- **Estado de publicación:** `9db728c` en `main`; CI y humo PostgreSQL verdes. El
  reintento `4fd5f15` también pasó CI, pero Railway rechazó ambos despliegues antes
  de cambiar contenedor. Producción conserva sana la release `0341986290f2` con
  esquema 41. Pendientes redeploy y capturas visuales del candidato.

## 2026-08-07 12:11 — espacio fiscal profesional para gestorías

- **Autor/agente:** Codex.
- **Objetivo:** convertir la cartera funcional pero vacía en una mesa de trabajo
  real para despachos: prioridad por cliente, períodos, archivo, revisión y primera
  lectura fiscal, manteniendo a Bynoesis como canal compartido con el autónomo.
- **Áreas y archivos:** migración y datos de gestoría, nuevo
  `gestoria_workspace.py`, router profesional, demo comercial, plantillas/CSS,
  pruebas, mapa, decisiones, estado y pendientes.
- **Cambios de datos/migración:** esquema 41 añade `gestoria_fiscal_profiles`, una
  fila por negocio con tipo de contribuyente, regímenes, periodicidad, obligaciones,
  nota y gestoría que lo actualizó. No guarda declaraciones ni autoriza envíos.
- **Pruebas ejecutadas:** Ruff verde; 281/281 backend y 134/134 del resto de
  módulos, total 415/415; 14/14 de `GestoriaTestCase`; regresiones focalizadas de
  perfil, cálculo, cartera y previsualización; ciclo SQLite 0 → 41 → 0 → 41 y
  `check_project_truth.py` verdes.
- **Dependencias o validaciones externas:** contraste de alcance con documentación
  oficial AEAT 2026 y las propuestas para despachos de Holded/Sage. Ninguna API
  nueva. Falta validar criterio y casos especiales con una gestoría real.
- **Riesgo/punto probable de fallo:** confundir una suma orientativa con una
  declaración fiscal. La UI etiqueta borradores, muestra datos incompletos y exige
  perfil explícito. La vista previa rasteriza solo la primera página con límite de
  píxeles y cada acceso revalida cuenta y `business_id`.
- **Diagnóstico y rollback:** comprobar esquema 41, `gestoria_fiscal_profiles`,
  filtros de `/gestoria/cliente/{id}` y endpoint `/preview`. Revertir aplicación
  restaura la cartera anterior; el downgrade 41 elimina únicamente perfiles
  configurables, nunca facturas, documentos ni registros fiscales.
- **Estado de publicación:** commit `2d14e2b` en `main`, CI verde y producción
  validada por HTTP con release `2d14e2b6f3b8` y `/ready` en esquema 41. Queda el
  recorrido visual autenticado del nuevo diseño en escritorio y móvil.

## 2026-08-07 11:42 — prioridad Fetch Metadata para gestorias reales y demo

- **Autor/agente:** Codex.
- **Objetivo:** cerrar el 403 que Chrome todavía reproducía aunque una prueba HTTP
  sintética hubiera pasado; el mismo acceso debe servir a demos y gestorías reales.
- **Áreas y archivos:** guardia web transversal, regresiones de seguridad, estado,
  mapa, QA, pendientes y fuente de verdad.
- **Cambios de datos/migración:** ninguno; esquema 40.
- **Pruebas ejecutadas:** 28/28 focalizadas verdes: seguridad, demo completa y
  `GestoriaTestCase` para cuentas profesionales reales; Ruff. La prueba legítima usa
  un `Host` de proxy no listado con `Sec-Fetch-Site: same-origin`; origen externo,
  `cross-site` y puerto no estándar continúan en 403.
- **Dependencias o validaciones externas:** requiere despliegue Railway y repetición
  desde Chrome; la prueba HTTP anterior ya no se considera evidencia suficiente.
- **Riesgo/punto probable de fallo:** confiar en una cabecera libre permitiría
  falsificar el origen. `Sec-Fetch-Site` es una cabecera Fetch Metadata controlada
  por el navegador; clientes antiguos sin ella conservan la allowlist estricta.
- **Diagnóstico y rollback:** si reaparece el JSON, correlacionar navegador/release
  antes de cerrar el incidente. Revertir este commit restaura el falso 403 de Chrome.
- **Estado de publicación:** local verificado; `main` tras este commit, pendiente
  Railway y prueba visual real.

## 2026-08-07 11:26 — origen seguro para el login de gestoría en Railway

- **Autor/agente:** Codex.
- **Objetivo:** corregir el 403 `origen no autorizado` del formulario real de
  gestoría cuando Railway separa el dominio público del `Host` interno.
- **Áreas y archivos:** `web/deps.py`, regresiones de seguridad, mapa, estado, QA,
  pendientes y fuente de verdad.
- **Cambios de datos/migración:** ninguno; esquema 40.
- **Pruebas ejecutadas:** tres regresiones nuevas; módulos completos 13 + 61 + 60 +
  278, total 412/412; Ruff. En producción, `/health` y `/ready` responden 200 con
  release `53d7f83da282` y esquema 40; origen propio devuelve 303 y uno externo 403.
- **Dependencias o validaciones externas:** Railway desplegado, CI general y humo
  PostgreSQL verdes. La cuenta `demo.gestoria@bynoesis.com` entra, muestra una
  cartera de dos empresas y cierra sesión por HTTP real; falta inspección visual.
- **Riesgo/punto probable de fallo:** una allowlist demasiado amplia convertiría el
  arreglo en una relajación CSRF. La implementación exige HTTPS estándar, origen
  público propio y `Host` receptor configurado; `cross-site` conserva prioridad.
- **Diagnóstico y rollback:** buscar `origen no autorizado` en `POST
  /gestoria/login`; revertir este commit restaura la comparación literal, pero
  también reproduce el 403 detrás del proxy.
- **Estado de publicación:** desplegado y validado en el perímetro real, incluida
  autenticación, cartera y cierre de sesión; pendiente solo inspección visual. Las
  actualizaciones documentales quedan en los commits de verificación posteriores.

## 2026-08-06 21:00 — continuar la numeración que el autónomo traía de otro programa

- **Autor/agente:** Claude.
- **Objetivo:** quien llega desde Holded, Quipu o una plantilla ya lleva facturas
  emitidas del ejercicio. Bynoesis empezaba siempre en el 1 y habría repetido números
  dentro del mismo año y la misma serie. Era un bloqueo de venta para el cliente que
  más interesa: el que ya factura.
- **Áreas y archivos:** `src/noesis/db.py` (`set_series_next_number` y `_series_prefix`),
  `src/noesis/web/routers/invoicing.py` (ruta nueva), `tests/test_backend.py`,
  `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migración:** ninguno nuevo. Este commit **renumera a 40** la
  migración `material_o_mano_de_obra`, que en local era la 38 y chocaba con la 38
  `huellas_documentales` ya desplegada.
- **Pruebas ejecutadas:** suite completa **429 pasan, 76 subtests, 0 fallos**. Verificado
  a mano: sin ajustar emite `2026/0001`; declarando 88 emite `2026/0088` y sigue en
  `2026/0089`; retroceder por debajo de lo emitido se rechaza con el motivo.
- **Dependencias o validaciones externas:** ninguna.
- **Riesgo/punto probable de fallo:** solo se permite avanzar. Si alguien informa de que
  no puede fijar un número, será porque ya hay una factura emitida igual o superior en
  ese prefijo; el mensaje lo dice.
- **Diagnóstico y rollback:** `pytest tests/test_backend.py -k "series_can_continue or
  never_go_back"`. Revertir es quitar la función y su ruta; no hay dato que migrar.
- **Estado de publicación:** commit local, pendiente de subir.
## 2026-08-06 19:42 — excepción explícita para la clave pública de demo

- **Autor/agente:** Codex.
- **Objetivo:** corregir los falsos positivos de las dos claves públicas de demo sin
  debilitar el guardián de secretos.
- **Áreas y archivos:** `demo.py`, `.secrets.baseline`, QA, bitácora y estado.
- **Cambios de datos/migración:** ninguno; esquema 40.
- **Pruebas ejecutadas:** logs exactos de dos intentos, detector de secretos, pruebas
  focalizadas, Ruff y fuente de verdad. La clave comercial nueva y la demo local
  histórica quedan exceptuadas en su propia línea; la baseline deja de depender de
  la posición de `demo.py`. PostgreSQL falló antes de descargar Actions por una
  indisponibilidad de GitHub y debe reintentarse.
- **Dependencias o validaciones externas:** GitHub Actions.
- **Riesgo/punto probable de fallo:** la credencial es pública por diseño; solo es
  segura mientras `is_demo` siga bloqueando cambios, envíos y automatizaciones.
- **Diagnóstico y rollback:** las excepciones están únicamente en `DEMO_PASSWORD` y
  `SHOWCASE_PASSWORD`; eliminarlas vuelve a poner CI rojo. No añadir esos valores a
  la baseline global ni reutilizarlos fuera de empresas demo.
- **Estado de publicación:** `main` tras este commit; CI pendiente de repetición.

## 2026-08-06 19:17 — cuentas comerciales reales y OCR privado de escaneados

- **Autor/agente:** Codex.
- **Objetivo:** crear dentro del SaaS real un acceso de autónomo lleno, un acceso de
  gestoría con cartera multiempresa y el portal de su cliente; leer localmente los
  PDF formados por imágenes sin contratar una API.
- **Áreas y archivos:** siembra y DB, middleware de permisos, portales/panel,
  documentos/OCR, Railpack/dependencias, pruebas y documentación operativa.
- **Cambios de datos/migración:** esquema 40 añade `businesses.is_demo` con valor
  falso por defecto. Solo las empresas ficticias preparadas expresamente se marcan
  como demo; las cuentas existentes no cambian.
- **Pruebas ejecutadas:** cuatro pruebas focalizadas, navegación de todas las rutas,
  aislamiento y solo lectura, PDFium sobre PDF de imagen, rechazo previo de páginas
  absurdas, Ruff, `compileall`, Bandit alto, secretos, `pip-audit`, fuente de verdad,
  suite 409/409 y ciclo SQLite 0 → 40 → 0 → 40. Evidencia en `Registro-QA.md`.
- **Dependencias o validaciones externas:** `pypdfium2` y `pytesseract`; Railpack
  instala Tesseract `spa/eng`. Falta verificar el binario y un corpus real tras el
  despliegue. Meta, correo, Stripe y AEAT no intervienen en la demo.
- **Riesgo/punto probable de fallo:** paquete APT/idiomas ausente en la imagen final,
  consumo de CPU del OCR y una cuenta sembrada parcialmente si el primer arranque se
  interrumpe. La demo falla hacia revisión manual y nunca tumba el arranque real.
- **Diagnóstico y rollback:** revisar el log `noesis.pdf_ocr`, disponibilidad de
  Tesseract, `businesses.is_demo` y las cuentas reservadas `demo.*@bynoesis.com`.
  Revertir el commit y bajar 40 elimina solo la marca; los datos ficticios deben
  borrarse de forma controlada si se decide retirar el escaparate.
- **Estado de publicación:** `main` tras este commit; pendiente despliegue,
  migración 40, activación temporal de `NOESIS_SEED_DEMO` y validación real.

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
## 2026-08-02 21:30 — catálogos por oficio y aviso del 40% en obras de vivienda

- **Autor/agente:** Claude.
- **Objetivo:** que la puesta en marcha deje de teclear el catálogo cliente a cliente, y
  avisar del error fiscal más fácil de cometer en reformas: el tipo reducido del 10%
  decae si el material supera el 40% de la base (art. 91.Uno.2.10º LIVA) y entonces la
  obra tributa entera al 21%.
- **Áreas y archivos:** `src/noesis/migrations.py` (migración 38), `src/noesis/db.py`
  (`kind` en líneas y sus cuatro inserciones), `src/noesis/trades.py` (nuevo: catálogos
  y regla), `src/noesis/tools.py` y `src/noesis/nlu.py` (el aviso llega al chat),
  `src/noesis/web/routers/invoicing.py` (dos rutas y `aviso_fiscal`),
  `tests/test_backend.py`, `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migración:** **esquema 38**. `invoice_lines` gana `kind` con valor
  'servicio' por defecto; lo ya emitido no se reinterpreta.
- **Pruebas ejecutadas:** suite completa **408 pasan, 71 subtests, 0 fallos**. Con
  servidor real: carga de catálogo por API, aviso al 60% de material, silencio al 28,6%
  y con factura al 21%, y emisión efectiva pese al aviso.
- **Dependencias o validaciones externas:** **la regla del 40% necesita revisión de
  asesoría fiscal** antes de venderse como garantía. Falta ejecutar la migración 38 en
  PostgreSQL.
- **Riesgo/punto probable de fallo:** el aviso depende de que las líneas estén marcadas
  como material. Una factura escrita a mano sin marcar nada cuenta como mano de obra y
  no avisará: es un falso negativo consciente, preferible a alarmar sin motivo.
- **Diagnóstico y rollback:** `pytest tests/test_backend.py -k "trade_catalog or
  reduced_rate"`. Para desactivar solo el aviso basta con que `reduced_rate_warning`
  devuelva `None`; la migración puede quedarse sin efecto secundario.
- **Estado de publicación:** commit local, pendiente de subir.

## 2026-08-02 20:10 — el error de emisión ofrece la factura simplificada cuando es legal

- **Autor/agente:** Claude.
- **Objetivo:** el fundador se topó con «Antes de emitir completa: NIF del cliente,
  domicilio del cliente» y no sabía que existía una salida. Si el destinatario es un
  particular y el total cabe en el límite general de 400 € (RD 1619/2012), la factura
  simplificada es legal y el producto ya la soporta; solo faltaba decirlo.
- **Áreas y archivos:** `src/noesis/db.py` (aviso condicionado y
  `_fits_simplified_invoice` como fuente única del límite), `src/noesis/tools.py`
  (usa el mismo ayudante), `tests/test_backend.py` (dos pruebas nuevas),
  `docs/project-state.json`, `docs/Registro-QA.md`.
- **Cambios de datos/migración:** ninguno.
- **Pruebas ejecutadas:** suite completa **400 pasan, 71 subtests, 0 fallos**. Además,
  con servidor real: aviso con 150 € (sugiere) y con 900 € (no sugiere), ciclo completo
  de simplificada emitida sin datos del destinatario con serie `T2026/0001`, y rechazo
  al crear un ticket de 900 €.
- **Dependencias o validaciones externas:** el límite de 400 € es el general; hay
  supuestos sectoriales de 3.000 €. **Conviene confirmarlo con la asesoría fiscal**
  antes de ofrecerlo a sectores con ese régimen.
- **Riesgo/punto probable de fallo:** el aviso solo aparece si lo único que falta son
  los datos del destinatario. Si alguien informa de que no lo ve, comprobar que no
  falte además el NIF o el domicilio del propio negocio.
- **Diagnóstico y rollback:** `pytest tests/test_backend.py -k simplified`. Revertir es
  devolver el `raise ValueError` original en `issue_invoice`.
- **Estado de publicación:** commit local, pendiente de subir.

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
