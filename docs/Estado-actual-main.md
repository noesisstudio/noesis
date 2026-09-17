# Estado actual del producto

## 17-sep — Descargas en Excel y el gasto ya cuadra entre pantallas

Costes y Facturas tienen botón «Descargar Excel», las facturas recibidas se pueden
descargar por primera vez (Excel y CSV) y el informe de jornada también sale en
Excel. Los archivos llevan importes como números y fechas como fechas, así que se
suman y ordenan sin arreglar nada; probado abriéndolos con Excel.

Además, el gasto del mes ya incluye las facturas de proveedor confirmadas. Antes
Costes podía decir «0 €» mientras Impuestos contaba esas mismas facturas. **La
cifra de gasto y el margen que ves cambian**, y ahora coinciden con el trimestre
fiscal. Al confirmar una factura con fecha de otro trimestre, el archivo de
Documentos te lleva a ese período en vez de esconder el documento.

## 17-sep — Adjuntar una factura deja al cliente listo para facturarle

Si subes a Documentos una factura emitida por ti y el cliente no está dado de alta,
la lectura propone ahora también su dirección, correo y teléfono. Los ves y los
corriges antes de aceptar, y al pulsar «Crear cliente y relacionar» la ficha nace
con esos datos: ya se le puede emitir una factura completa sin volver a escribirlos.
Si el cliente ya existía, sus datos no se tocan. Nada se crea sin tu clic, y sin la
IA externa autorizada no hay propuesta, igual que antes.
## 16-sep — Agenda en lenguaje normal y fallo de IA visible

Candidato sin publicar. «Añade un trabajo para mañana a las 12» ya se entiende: el
cerebro local admite añade, agrega, pon, crea, programa y mete con trabajo, cita,
visita, servicio o aviso, y separa fecha, cliente y tarea. Como un trabajo necesita
cliente, cuando falta se conserva la fecha y se pregunta solo el nombre; responder
«Marta López» lo crea. Un «sí» no completa nada y otra orden distinta sigue su curso.

Ajustes muestra el último fallo de la ayuda avanzada (tipo de error y fecha), que
antes solo se veía en el chat como «no está disponible». El modelo de respaldo pasa a
`claude-haiku-4-5`, sin sufijo de fecha; si esa variable está definida en Railway,
hay que corregirla allí también. Sin migración; esquema 55.

## 16-sep — Documentos por WhatsApp: una lectura y correcciones en el chat

Candidato sin publicar. Una foto o un PDF se leen una sola vez: la IA consentida y
el texto local (pypdf o Tesseract) se combinan y, si los totales no coinciden, se
pregunta en vez de elegir. Sin IA disponible, el lector local propone total, base,
IVA (también con varios tipos), IRPF, número, fechas, NIF validado y proveedor.

La revisión ocurre en el propio WhatsApp: «total 45,20», «proveedor Leroy Merlin»,
«IVA 10», «IRPF 15», «fecha 12/09», «es un gasto». Lo que dice el titular sustituye
a lo leído y lo deducible se marca como calculado. Un SÍ solo se acepta cuando las
cifras cuadran; si no, se dice exactamente qué falta. Un PDF con varias facturas se
separa en documentos propios y se revisan una a una o con TODAS; un extracto se
contrasta con lo registrado y no duplica. Nada se contabiliza sin confirmación y el
tipo del documento no cambia hasta ese SÍ. Sin migración; esquema 55.

## 15-sep — Documentos: revisión manual y PDF con varias facturas

Candidato sin push. Documentos abre siempre la revisión manual aunque falle la
lectura, muestra «Revisar y gestionar» sin seleccionar la fila y separa un PDF con
varias facturas por rangos de páginas. El original queda como lote no
contabilizable; cada parte se revisa y registra por separado (recibidas → Costes).
Archivar como factura propia no crea factura nativa; se explica en pantalla.

## 15-sep — Piloto local de líneas, correcciones y foco de factura

Candidato sin push ni despliegue. Nuevo `NOESIS_LOCAL_PLANNER_ENABLED=false`,
dependiente de revisión, prepara facturas multilínea de gramática acotada y permite
corregir cantidad/precio/cliente antes de SÍ. Reutiliza cálculo y tablas existentes.
Foco PDF web por actor y huella de emisión comprobada dentro del motor nativo.
Alcance y limitaciones: `02-tecnico/Cerebro-local-piloto.md`. No es modelo privado
ni aprendizaje activado. Suite final: 847 pruebas correctas; smoke HTTP con PDF
real e identidad aislada correcto. Pendientes PostgreSQL y piloto físico.

## 15-sep — Cerebro propio: contención monetaria local

Candidato sin push: barrera sin red para negativos y varias cantidades que el
parser simple no representa. Corrige nombres con «llamado» y el conector fiscal
«con IVA»; conserva el IVA incluido explícito en gastos. No es comprensión
multilínea ni un modelo privado desplegado.
Pruebas en `Registro-QA.md`; continuación en `Tareas-vivas.md`.

## 14-sep — Notas de voz listas para activar con Groq

El founder elige Groq para transcribir. El código está listo y reforzado: sin
redirecciones con la clave, formatos y tamaños validados y errores sin datos. La web
y WhatsApp tienen prueba completa pasando por Groq con la red simulada. En
producción la voz sigue apagada hasta archivar el DPA de Groq y poner
`GROQ_API_KEY` en Railway. Al hacerlo aparecen solos el micrófono, la respuesta de
`/preguntas` y Groq en las políticas. Pasos en `Conectar-APIs.md` §6.

## 14-sep — Página de bienvenida para clientes

`/bienvenida` reúne la guía de instalación para enviarla por correo junto al
vídeo. No se indexa ni sale en el sitemap. Sin `NOESIS_WELCOME_VIDEO_ID` muestra
los pasos y un aviso de que el vídeo llega pronto. Con la variable, YouTube solo se
carga al pulsar «Ver el vídeo» y las políticas de cookies y privacidad lo declaran.
Pendiente: grabar el vídeo, subirlo como oculto, poner la variable en Railway y
enlazar la página desde el correo de invitación.

## 13-sep — WhatsApp: número y mensaje exactos al conectar; revisión móvil

La pantalla de conexión (alta y Ajustes) muestra el número de Bynoesis completo
y el mensaje exacto «BYNOESIS código». Sin `NOESIS_WHATSAPP_NUMBER` ya no ofrece
un enlace roto. La web pública en móvil no desborda a 360/390 px. Contraste de
antetítulos, zona de toque del pie y casilla del formulario corregidos. Publicado
en `22cb025`; pendiente comprobar la conexión en un móvil real.

## 13-sep — Google Analytics opcional con aviso de cookies

La web pública puede usar GA4 si se define `NOESIS_GA_MEASUREMENT_ID`. Sin la
variable no cambia nada. Con ella aparece un aviso con Aceptar y Rechazar, y Google
solo se carga tras aceptar. La decisión se puede cambiar en el pie y en `/cookies`.
La CSP abre Google solo en rutas públicas. Las políticas de cookies y privacidad
lo declaran solo cuando está activo. El recuento propio sigue igual. Sin migración.
Activo y verificado visualmente en producción: el aviso aparece y «Rechazar» lo
cierra sin cargar Google. Pendiente confirmar una visita aceptada en Tiempo real
de GA4 y revisar la retirada tras una carga real.

## 10-sep — Núcleo de planificación de emisión y diagnóstico real

Nuevo plan sin efectos separa emitir/descargar/entregar. La emisión confirma una
versión concreta de borrador y líneas dentro de la transacción. Precio final de
una línea conserva céntimos. Un espacio final en el ID Meta causaba el fallo de
subida: reproducido y confirmado con subida real normalizando el ID, sin enviar.
El alcance y los siguientes dominios están en `Agente-operativo-fiable.md`; no es
todavía un agente universal. Sin migración ni modificación de facturas emitidas.

## 10-sep — Seguimiento de orden compuesta por WhatsApp

La captura real confirmó que no se vuelve a enviar una demo, pero expuso un
segundo fallo: «crear y enviar PDF» entraba en búsqueda. Corregido con creación
primero y entrega únicamente del ID real. «F2 Jana» conserva intención de buscar;
«créalo» tras rechazo fiscal conserva la explicación, no inventa un resultado.
Sin migración ni ampliación del límite fiscal. Pendiente validar entrega física.

## 10-sep — Candidato de fiabilidad de facturas por WhatsApp

Se elimina el fallback a la última factura cuando el cliente pedido no existe.
El PDF usa el documento identificado; ante ambigüedad pregunta. Adjunta borradores
marcados sin emitirlos. «Imprímela» entrega el PDF, no accede a una impresora.
Contexto reciente por negocio/teléfono, citas nuevas verificables y creaciones
anunciadas desde resultados reales de herramientas. El agente incorpora turnos
locales al historial. Publicado, sin migración y con esquema 55. La regresión local
completa queda en 808 pruebas; pendiente comprobación con WhatsApp y móvil reales.

## 10-sep — SEO y GEO: un nombre y una ficha para asistentes

Publicado en `88adfa3` y verificado en producción. La web pública deja de alternar «Noesis» y
«Bynoesis»: títulos, descripciones, FAQ, CTA y demo usan solo Bynoesis. Nuevo
`/llms.txt` con qué es, para quién, qué no hace, precios del catálogo y páginas;
sin `noindex` ni recuento de visita. `/preguntas` publica FAQPage de sus 16
respuestas desde la misma fuente que el HTML y según voz/OCR/alta reales. Sin
migración ni cambios en gestiones; esquema 55. Bing importado desde Search
Console (sitemap Success, 14 URLs) y reindexación pedida en Google para renovar
el título antiguo «Noesis». La cola de Facebook también usa ya Bynoesis.

## 10-sep — Facturas y Documentos comparten la misma fuente

El Archivo ya incluye los PDFs reproducibles de todas las facturas del período,
tanto si nacieron en web como en WhatsApp. No se duplican blobs ni registros: una
edición válida en Facturas se refleja al volver a abrir Documentos, y un original
subido que ya está vinculado evita una segunda fila. Los borradores se distinguen
como pendientes y siguen sin computar como ingreso hasta emitirse.

Proyectos ofrece un control visible de estado y un deslizador limitado a 0–100.
Se añade Cancelado como cierre que conserva trazabilidad y se separa de los activos;
Finalizado continúa fijando el avance al 100%. Sin migración ni cambio de permisos.

## 10-sep — corregida la petición real de PDF en catalán/castellano mixto

El envío de PDF ya existía, pero una lista lingüística demasiado literal dejaba
fuera «Passame…» y «No pots enviar…?». Esas expresiones ahora se resuelven antes
del modelo generativo y envían al titular el último ticket/factura emitido de su
negocio. Además, el texto generado ya no puede afirmar que Bynoesis carece de esa
capacidad. No hay migración ni cambio en facturación o permisos; falta validar la
frase contra Meta real después del despliegue.

## 9-sep — PDF real solicitado desde el chat de WhatsApp

La petición «envíame/pásame el ticket en PDF» ya no queda en manos del texto
generativo: localiza una factura emitida del propio negocio y envía el documento
real a través de Meta. Los borradores se bloquean y los errores se reconocen sin
afirmar que existe un adjunto. Los cambios visuales posteriores del socio están
integrados sin conflicto. La voz continúa bloqueada por configuración externa:
producción no tiene Whisper privado, Groq ni un motor local disponible.

## 9-sep — publicación y hotfix PostgreSQL

`ccb1b54` desplegado en Railway y puerta pública verde (14 páginas, esquema 55).
CI detecta un patrón LIKE incompatible con psycopg en los contadores del admin.
El hotfix parametriza los cinco patrones y añade regresión PostgreSQL; verificar
la ejecución remota y despliegue de este sucesor antes de declarar todo verde.

## 9-sep — rediseño público autorizado para publicación

Sobre el `main` del socio `4df5088`, conservando su corrección de identidad del
teléfono. Home centrada en **Tu negocio, por WhatsApp**, demo conversacional ligera,
Autónomos por jornada y Gestorías con expediente real de ejemplo. Contacto integra
el calendario real solo tras permiso explícito; el enlace heredado daba 404.
Eventos agregados separados de visitas en Marketing, sin identificar visitantes.
Sin migración ni cambios en las gestiones; esquema 55. El paquete instalable
incluye ahora plantillas/assets. El founder autoriza commit y push a main para
despliegue automático en Railway. En esta foto previa al push, la verificación
del nuevo despliegue queda pendiente; no se da por completada anticipadamente.
Detalle, evidencia, copy y límites: [[Rediseño-web-2026-09-09]]. QA: [[Registro-QA]].
Faltan para la aceptación externa: canal público demo WhatsApp, proveedores reales,
reserva coordinada/correo, móvil físico y métricas de campo tras publicación.

## 8-sep — release de la mañana consolidada

Código reunido sobre el último `main` del socio, publicado como `086039e0b538` y
validado con 752 pruebas, humo PostgreSQL y puerta externa. Entran
las mejoras del centro de mando, móvil, consumo por cuenta, documentos, WhatsApp,
copias y comprobadores. La revisión conversacional y el aprendizaje están presentes
pero apagados por defecto; Whisper privado sigue sin servicio Linux contratado y la
plantilla AWS no crea recursos por estar en el repositorio. Sin migración: esquema 55.
La prueba local no sustituye Meta, voz, Stripe, correo, PostgreSQL o móvil reales.
Producción respondió `health/ready`, esquema 55, 14 páginas y 8 cabeceras; revisión,
aprendizaje y ledger se comprobaron apagados en Railway.

## 8-sep — aprendizaje supervisado incluido, apagado

Correcciones aprobadas explícitamente se convierten en equivalencias literales
por negocio; cada reutilización exige revisión y confirmación. Guía persistente
de factura incompleta y recuentos de fallos/aclaraciones sin contenido personal.
`NOESIS_ASSISTANT_LEARNING_ENABLED=false`, dependiente del flag de revisión.
No reentrena modelos ni modifica código/permisos. Sin migración y sin activación.
Detalle y límites: [[Aprendizaje-supervisado-Bynoesis]].

## 8-sep — confirmación incluida y voz privada preparada

Bloqueo de interpretaciones peligrosas y revisión persistente de herramientas con
`NOESIS_ASSISTANT_REVIEW_ENABLED=false` por defecto. Identidad de cliente fijada,
corrección y confirmación de un solo uso con pruebas web/audio/WhatsApp sintéticas.
Servicio Whisper privado preparado y transcripción sintética real ejecutada mediante
HTTP local. Revisión apagada; voz no desplegada ni contratada. Faltan build Linux,
corpus real y piloto.
Detalle: [[Fiabilidad-conversacional-y-Whisper]]. Sin cambios de esquema ni Stripe.

## 7-sep — candidato de fiabilidad en revisión

La lectura de facturas ya contrasta aritmética, fechas y dígitos de control antes
de proponer un alta por WhatsApp; las discrepancias no se autocorrigen ni se
contabilizan. Costes permite corregir facturas recibidas, las fotos repetidas se
releen sin duplicarse y el ICS declara la zona horaria completa. El camino local
acepta los dictados habituales de importes y altas explícitas de clientes y
proveedores. Los usuarios siguen entrando únicamente mediante invitación segura.

Una simulación sintética recorre el trabajo de oficina sin proveedor de IA. Este
candidato no cambia esquema ni se ha desplegado; los medios reales, Stripe, Meta,
correo y calendarios físicos siguen necesitando validación externa.

## 7-sep — centro de mando preparado para publicación

Administración dividida en Dirección, Cuentas y soporte, Marketing y ventas,
Finanzas y consumo, Operaciones, Ingeniería y seguridad, Administración legal.
Sin nuevos permisos ni cambios de esquema. Consulta de consumo por cuenta y
modelo con límites explícitos; no equivale a factura completa del proveedor.
Se publica solo el panel y sus dependencias; los trabajos locales de copias,
WhatsApp, extracción y paginación no se incluyen. Ver `Admin-centro-mando-release.md`.

## Candidato local — 7-sep

Administración reorganizada por departamentos y ficha por tareas, con navegación
activa y adaptación móvil. Paginación SQL opcional de facturas y conversión FX
configurable. Detalles y límites en `Admin-organizacion-2026-09-07.md`.
No publicado; no se ha localizado el nuevo commit de teléfono del socio.

Correcciones móviles, teléfono titular en admin, consumo por cuenta/proveedor/modelo
y revisión conservadora en WhatsApp. Sin publicar. Alcance y pendientes en
[revisión de frentes](09-historico/Revision-frentes-2026-09-07.md). No es gasto completo por empleado.

> Lectura humana del estado. La fuente verificable para migración, pruebas, precios,
> política de suscripción y publicación es [`project-state.json`](project-state.json).
> Los pendientes solo viven en [[Tareas-vivas]].

## Producto construido

- Calculadora offline de costes AWS/Railway: [[Costes-backups-y-desarrollo-interno]].
  Cuatro pruebas dirigidas adicionales, sin modificar runtime ni contratar servicios.

- Candidato local del 6-sep, **sin publicar**: backups BD/ZIP emparejados; CISO
  exige evidencia reciente de subida completa al destino actual y caduca simulacros.
  S3 añade checksum para Object Lock y evita duplicar Host. La extracción múltiple
  no devuelve una primera factura parcial y WhatsApp pide separar el archivo.
  Diagnósticos de correo/Meta corregidos. AWS preparado, no contratado ni creado:
  [[Copias-independientes-AWS]]. Sin migración ni cambios de permisos.
  El cierre de la app detiene el scheduler antes de liberar la base de datos.
  Suite local final 653/653, migraciones SQLite 55→0→55 y análisis estáticos
  correctos; PostgreSQL y proveedores reales pendientes antes de publicar.

- Revisión aislada del 4-sep: pypdf actualizado a 6.16.1 por tres CVE y puerta
  legal de correo alineada con el proveedor efectivo (Brevo tiene prioridad sobre
  SMTP residual). CI manual verde: 629 pruebas, migraciones, PostgreSQL, backup y
  rollback código anterior/BD. Publicado con autorización tras copia real y
  restauración verificada: release `4f5e88f071cd`, esquema 55, comprobación pública
  y accesos demo correctos. Ver [[Revision-pre-main-2026-09-04]]. Altas públicas
  y ambos flags WUB siguen apagados; no equivale a apertura comercial.

- El candidato del esquema 55 convierte la baja con conservación en un proceso
  real y trazable. Si no hay facturas emitidas ni jornada, la cuenta se borra como
  antes; si los hay, se crea una única solicitud abierta por negocio, se devuelve
  una referencia, se encolan avisos y se audita la acción. Dirección ve la bandeja
  y debe documentar cada cambio de estado; marcarla no borra nada como efecto
  lateral. Se han añadido borradores operativos de ROPA, matriz de proveedores,
  derechos/bajas y brechas. Cal.com ya no se incrusta, la CSP prohíbe frames en
  todo el sitio, los textos nombran proveedores activos y describen los roles, y
  `/cumplimiento` deja de atribuir a Bynoesis una integración inexistente con un
  sistema homologado. La copia S3 falla cerrada si no constan región de firma,
  proveedor y residencia contractual. La purga automática sigue deliberadamente
  pendiente hasta que un profesional valide la tabla de conservación. Este
  bloque está desplegado desde el 4-sep con backup previo verificado. La copia
  externa y la validación jurídica y humana siguen pendientes.

- El candidato del esquema 54 incorpora la base de datos de retención sin cambiar
  el comportamiento del producto: un Registro Interno de Valor multiempresa,
  idempotente y fail-open observa trabajos creados/cerrados, facturas emitidas,
  recordatorios enviados, documentos confirmados y presupuestos preparados/enviados.
  Separa acciones de resultados —cobro, aceptación y trabajo facturado— y solo
  atribuye ayuda cuando existe evidencia enlazada. Calcula WUB móvil y semanal,
  profundidad, consistencia y aceptación de propuestas de forma determinista. Cada
  instancia distingue delegación útil de formulario manual mediante
  `qualifies_for_wub`; la actividad manual puede auditarse, pero no suma WUB. El
  ledger y su auditoría interna parten apagados; la auditoría histórica de acciones
  del asistente se conserva incluso con el ledger desactivado. No se muestra Confidence,
  Insight, Progress ni se concede autonomía. Exportación y baja RGPD incluyen el
  ledger. El rollback exige apagar, restaurar primero código anterior sobre esquema
  54 y bajar después la BD; nunca código 54 sobre esquema 53. El lifecycle admite
  corrección/reversión, pero sus hooks por proceso siguen pendientes. El candidato
  está desplegado con flags apagados; su uso con negocios reales no está validado.

- La identidad existente ya tiene un paquete profesional versionado en `branding/`:
  originales SVG, logo horizontal, símbolo y wordmark en versiones primaria,
  inversa y monocroma; 49 PNG transparentes y con fondo; avatares/portadas para
  redes, plantillas editables, paleta JSON/CSS, guía de uso, licencias y manifiesto
  verificable. El nombre público queda unificado como **Bynoesis**; `bynoesis.com` y
  `@bynoesis` son dominio/usuario, no una segunda marca. Su territorio verbal es
  tiempo, orden, calma y control: «Haz tu trabajo; Bynoesis te ordena el negocio».
  Facturación, cobros y margen son pruebas del valor, no el posicionamiento completo.
  La aplicación no cambia. `branding/redes-sociales/` convierte esa identidad en un
  paquete operativo: imagen de perfil, portada cuando existe, descripción y lista de
  comprobación para Instagram, Facebook y LinkedIn; también deja YouTube y TikTok
  preparados solo para reservar el usuario sin dispersar el lanzamiento. El avatar
  social 1.2.2 prescinde de la placa blanca: estrella ampliada sobre fondo verde bosque,
  interior original teal/bosque/crema y contorno tinta únicamente en la silueta
  exterior, sin alterar el símbolo maestro ni los iconos de la aplicación.

  `branding/contenido/` añade un manual editorial reproducible de 38 páginas para
  Instagram, Facebook, LinkedIn y campañas. Convierte el posicionamiento en 24
  fichas listas para producir —formato, público, objetivo, gancho, guion, rodaje,
  copy, CTA, métrica y guardarraíl—, cinco campañas, un calendario mensual y un
  sistema de producción y aprendizaje. Las demos, cifras, testimonios e
  integraciones no validadas quedan explícitamente limitadas para no confundir
  producto construido con evidencia comercial.

- El candidato del esquema 52 prepara una entrada documental por correo sin comprar
  buzones ni gastar uno de los alias de Hostinger por cliente. Un único catch-all
  entrega a direcciones privadas distintas por negocio; Bynoesis falla cerrado si no
  puede demostrar el destinatario, deduplica, valida y clasifica con el mismo motor
  de Web/WhatsApp y no conserva remitente, asunto, cuerpo ni el correo original. Las
  facturas emitidas reutilizan clientes por NIF exacto o dejan un alta editable por
  confirmar. La función permanece apagada hasta superar la prueba real de Hostinger.

- Dirección ya puede entender la rentabilidad operativa de Bynoesis **cuenta por
  cuenta** sin abrir los datos del negocio del cliente. El centro interno combina
  el precio mensual comprometido, consumo de IA, plantillas y entregas de WhatsApp,
  correo y extracciones con los costes reales del libro CFO. Cada coste se reparte
  con un criterio visible y el total asignado reconcilia con el libro; si falta un
  driver, queda explícitamente sin asignar. Las demos no contaminan el margen y las
  alertas priorizan entregas fallidas, límites de IA y cuentas con margen inferior
  al 60 %. También se ha retirado el falso coste fijo que penalizaba cada OCR local
  sin factura de proveedor. La ficha de soporte muestra la misma lectura solo con
  metadatos, nunca clientes, mensajes, documentos ni importes del negocio.

- La recuperación del titular ahora tiene las mismas garantías transaccionales que
  la nueva recuperación de gestoría. Pedir un enlace invalida los anteriores y el
  consumo del token, el cambio de contraseña y el incremento que revoca sesiones se
  confirman juntos o no se confirma nada. La respuesta sigue sin revelar si existe
  una cuenta y solicitud/finalización quedan trazadas sin correo, token ni contenido.

- El centro de soporte ya no se limita a diagnosticar un correo agotado:
  administración puede devolver **un único correo fallido** a la cola desde la ficha
  de la misma empresa. La acción no envía durante la petición, no puede cruzar
  `business_id`, no duplica un correo ya en curso o enviado, reinicia los intentos y
  queda registrada en la bitácora encadenada. Destinatario, asunto y cuerpo siguen
  ocultos para soporte.

- La gestoría ya puede recuperar su acceso sin intervención técnica y sin cruzar su
  identidad con ningún autónomo. El esquema 51 guarda tokens propios, hasheados,
  caducables y de un solo uso; pedir uno nuevo invalida los anteriores. La respuesta
  pública nunca revela si el correo existe, el envío pasa por la outbox durable y el
  cambio de clave es atómico: cierra todas las sesiones previas y conserva el MFA.
  Tres regresiones cubren no enumeración, caducidad, consumo único, nueva clave,
  revocación de sesiones y segundo factor. Falta el recorrido con buzón y autenticador
  reales después de publicar.

- La publicación ya no depende solo de una comprobación manual. El comando
  `noesis-production-check` observa Bynoesis desde fuera, sin sesiones ni secretos, y
  rechaza que producción siga detrás de `main`, una migración a medias o releases distintos entre `/health` y `/ready`,
  pérdida de protecciones HTTP, páginas públicas caídas o no indexables, canonical/H1
  rotos y marcadores legales reaparecidos. Un workflow independiente lo ejecuta cada
  seis horas y permite lanzarlo bajo demanda. La comprobación real del 26 de agosto
  confirma esquema 50, release coherente, 14 páginas públicas y todas las barreras
  verificadas. Esto aporta detección periódica; la apertura masiva sigue necesitando
  monitor 24/7 externo y procedimiento humano de respuesta.

- La primera ejecución del comprobador dentro del contenedor detectó una diferencia
  real entre desarrollo y despliegue: Railpack instala `requirements.txt`, donde no
  constaban `pypdf`, `pypdfium2` ni `pytesseract`, aunque sí estaban declarados en
  `pyproject.toml` y Tesseract tenía `cat/spa/eng`. El candidato sincroniza ambas
  fuentes y añade una regresión de empaquetado. Queda en **517 pruebas**, sin cambio
  de esquema. Producción responde con `b3c184251374` y la repetición por SSH confirma
  foto y PDF escaneado disponibles con `cat/spa/eng`.

- El candidato del 17 de agosto añade una comprobación operativa segura para cerrar
  integraciones del piloto. `noesis-integrations-check` valida OCR de foto y PDF con
  `cat/spa/eng` y, con `--network`, consulta por lectura Brevo, Google OpenID, los
  seis precios Stripe y Groq sin enviar correos, transcribir, cobrar ni mostrar
  secretos. La voz ya no fuerza castellano: detecta automáticamente catalán,
  castellano o inglés salvo que se configure una pista explícita. La suite completa
  queda en **516 pruebas**, Ruff y compilación verdes; no cambia el esquema 49.
  Producción responde con el release `808a96004b7b`; queda ejecutar el comprobador
  con las credenciales de Railway y completar las pruebas humanas.

- La auditoría visual local del piloto ya cubre portada, panel de autónomo demo,
  Documentos, asistente, cartera de gestoría en escritorio y portal de cliente en
  móvil. Se corrigieron tres defectos visibles: el distintivo central corrupto de la
  demo móvil, las sugerencias del asistente ocultas horizontalmente y las fechas ISO
  del portal; también se representa correctamente el énfasis del criterio de Bynoesis.
  Los siete contratos Stripe de gestión, tarjeta, cambio y cancelación siguen verdes
  y bloquean un segundo Checkout. El esquema continúa en 49 y el repositorio cuenta
  con **506 pruebas**. El release `aed36de59e30`, el CI completo, el humo PostgreSQL
  y las vistas publicadas están verificados; solo queda recorrer el Customer Portal
  con una sesión Stripe sandbox real.

- El candidato de fiabilidad del 14 de agosto corrige cinco fricciones visibles del
  piloto sin ampliar permisos: la demostración puede responder consultas locales
  sin guardar historial ni ejecutar acciones; cualquier orden de escritura sigue
  bloqueada. El portal de cliente y el expediente de gestoría vuelven a la misma
  pantalla con un mensaje comprensible cuando una cuenta está en modo consulta, en
  vez de mostrar JSON técnico. Los ejemplos del asistente se adaptan al sector y la
  lectura mensual separa el dinero que entró este mes del cobro de las facturas
  emitidas este mes, evitando porcentajes superiores al 100% por mezclar cohortes.
  Las **504 pruebas** completas, Ruff, CI y el humo PostgreSQL están verdes; no
  cambia el esquema 49. Producción responde con el release `ea1f5f3e628f` y
  `/ready` confirma el esquema 49. Falta el recorrido visual autenticado de las
  tres experiencias.

- La gestión de suscripción separa contratación y mantenimiento. Una cuenta activa
  muestra su **Plan actual** y separa gestión general, cambio de tarjeta,
  cancelación y mejoras mensuales/anuales mediante flujos acotados del portal de
  Stripe. Cada mejora lleva el plan y período elegidos a la confirmación segura;
  los niveles inferiores constan como incluidos. Bynoesis nunca aplica por sí mismo
  una cancelación o un cambio irreversible. No queda ningún formulario de Checkout
  en la pantalla activa y el servidor redirige también cualquier POST antiguo o
  manipulado al portal, de manera que el mismo negocio no pueda crear una segunda
  suscripción por error. Bynoesis crea y reutiliza una configuración versionada del
  Customer Portal con cambio de tarjeta, cancelación y los seis precios conocidos,
  de modo que los botones no dependen de una configuración manual incompleta en
  Stripe. El estado de carga evita dobles envíos y cualquier rechazo vuelve al
  bloque visible de gestión y queda auditado. Las 499 pruebas están verdes; el
  candidato está desplegado desde el release `52c61f9e6277` con esquema 49. Falta
  el recorrido autenticado con la suscripción sandbox real.

- La primera compra sandbox completa de Stripe confirmó precio mensual de
  Autónomo, IVA externo, suscripción `active` y tres entregas webhook con HTTP 200.
  La prueba real descubrió una carrera: un Checkout procesado después de la señal
  de pago podía volver a guardar `pending`. El candidato corrige la transición bajo
  bloqueo de fila y añade reconciliación de retorno mediante API autenticada de
  Stripe; exige coincidencia de negocio, cliente, suscripción, estado activo y
  `price_id` conocido, por lo que ni la URL ni el navegador conceden acceso. El
  panel muestra además el plan realmente contratado. Las 492 pruebas están verdes;
  producción responde con el release `9f3dc48d9d4a` y esquema 49. El founder ya ha
  confirmado el acceso activo con la cuenta sandbox.

- El sitio público dispone de una base SEO verificable: 14 páginas en el sitemap,
  títulos y descripciones únicos, canonical, compartición social completa, un H1 por
  documento y ficha `Organization`/`WebSite` solo en portada. Las nuevas entradas
  `/autonomos` y `/gestorias` responden a intenciones distintas sin duplicar la Home.
  Login, onboarding, paneles y portales envían `noindex`; el sitemap ya no finge que
  todas las páginas cambian a diario. El dominio está verificado en Search Console,
  el sitemap se ha enviado y la portada está indexada. El release `18104f0` y el
  esquema 49 responden en producción; las 14 URLs, canonical y `noindex` se han
  comprobado sin navegador gráfico. La ruta privada `/gestoria` usa anclas de fin o
  barra para no bloquear por prefijo la pública `/gestorias`; Googlebot ya recibe
  esta última en 200 e indexable. Falta que Search Console renueve su caché, esperar
  el nuevo rastreo y tomar decisiones cuando exista rendimiento real.

- El alta comercial es recuperable en el esquema 49: conserva plan, periodicidad e
  intención y, al volver a iniciar sesión, lleva al paso exacto pendiente. Negocio y
  operativa se marcan completos solo después de guardar sus datos obligatorios. La
  configuración inicial ya incluye las tres plantillas de factura, color, logotipo,
  pie textual, distintivo gráfico, alcance y condiciones de presupuesto; el último
  paso muestra un resumen antes de entrar o pagar. WhatsApp solo figura conectado
  tras recibir el código real, o queda explícitamente pospuesto. Después de Stripe,
  el titular vuelve a la puesta en marcha para crear su primer cliente. Las 485
  pruebas, el CI y el humo PostgreSQL están verdes; producción responde con el
  release `8730826a79ab` y el esquema 49. Falta el recorrido visual y Stripe/Meta
  reales.
- Ajustes incorpora un editor documental por capas: tres composiciones probadas,
  color, logotipo saneado, pie textual y una imagen inferior para distintivos de
  ayudas, fondos, certificaciones o asociaciones. El titular elige tamaño,
  alineación y si la imagen aparece solo en facturas o también en presupuestos;
  dispone de muestra inmediata y PDF de ejemplo que no crea ni numera documentos.
  PNG/JPG/WebP se validan por contenido, se limitan y se convierten a PNG sin
  metadatos. La migración 48 guarda versiones reutilizables por negocio: al emitir,
  la factura enlaza su perfil visual y posteriores cambios de marca no alteran su
  PDF. Las 485 pruebas, el ciclo completo de migraciones y las revisiones estáticas
  y de seguridad están verdes. Producción responde con el candidato y esquema 48;
  falta el recorrido visual con el distintivo real del founder.
- La autorización temporal de configuración habilita una segunda corrección
  administrativa acotada: nombre visible para el futuro, sector, provincia, tamaño,
  objetivo, idioma, nivel de explicación y apariencia predeterminada de facturas y
  presupuestos. La función no acepta correo del titular, NIF, dirección fiscal,
  impuestos, cuenta de cobro, plan, usuarios, Stripe, WhatsApp, gestoría, tokens ni
  automatizaciones. Revalida administrador, alcance y caducidad dentro de la
  transacción; la auditoría seudonimiza los textos y una factura ya emitida conserva
  su emisor congelado. El release `6a879b2b1153` está desplegado: CI completo,
  humo PostgreSQL y `/health`/`/ready` verdes con esquema 47. Falta el recorrido
  visual con una autorización real.
- El centro de soporte puede corregir la organización de documentos únicamente
  cuando el titular abre una ventana temporal con el alcance correspondiente. La
  ficha muestra un editor acotado a tipo, estado, cliente, proyecto y nota de
  revisión; no abre archivos ni OCR, no toca importes y rechaza documentos
  vinculados a facturas emitidas. El permiso se vuelve a comprobar dentro de la
  transacción, todas las referencias filtran por `business_id` y la bitácora
  encadenada conserva actor, autorización, campos y valores anteriores/posteriores
  sin guardar la nota en claro. El release `bf2df0d7afe5` está desplegado: CI
  completo, humo PostgreSQL y `/health`/`/ready` verdes con esquema 47. Falta el
  recorrido visual con una autorización real.
- Documentos separa ahora entrada, archivo y revisión. La carga ocupa una franja
  horizontal apta para cámara móvil; cliente, proyecto y nota son contexto opcional.
  El archivo presenta carpetas por período para ingresos, gastos, tickets,
  pendientes y otros, conserva búsqueda/estado y abre la primera página solo cuando
  se solicita. La demo repara de forma idempotente los tipos históricos y enseña
  cada carpeta sin duplicar originales. La clasificación real sigue siendo
  conservadora: una factura sin emisor inequívoco queda pendiente de confirmación.
  El release `5bb715a68217` está desplegado con esquema 47 y CI completo/PostgreSQL
  verdes; falta únicamente el recorrido visual manual y ejecutar una vez la
  reparación de los datos demo ya persistidos.
- La cuenta profesional de gestoría dispone de segundo factor TOTP opcional en el
  esquema 47. La contraseña abre un reto de cinco minutos; cada código temporal se
  consume atómicamente y no puede repetirse. Al activar se entregan ocho códigos de
  recuperación aleatorios de un solo uso, guardados únicamente como hash y mostrados
  en la respuesta inmediata, nunca en la cookie de sesión. Activar, regenerar o
  desactivar exige contraseña, segundo factor cuando corresponde y límites de
  intentos compartidos. La semilla se deriva de la clave maestra y no se almacena
  reversible en la base. El release `40d564555c07` está desplegado: CI completo y
  humo PostgreSQL verdes, `/ready` confirma esquema 47 y las entradas pública,
  unificada y profesional responden correctamente. Falta el recorrido humano con
  una aplicación autenticadora y una cuenta de gestoría real.
- La suscripción ya no depende de que los webhooks de Stripe lleguen ordenados.
  El esquema 46 conserva el último evento aplicado por negocio; Checkout solo
  guarda la relación con cliente/suscripción y nunca activa por sí mismo. La
  activación exige una factura pagada o que Stripe confirme `active`/`trialing`.
  `incomplete`, `paused`, `unpaid`, `past_due` y estados desconocidos quedan en
  modo consulta. Facturas aisladas, eventos antiguos y eventos de una suscripción
  anterior no pueden reactivar ni degradar la suscripción vigente. Checkout tampoco
  concede un upgrade antes del cobro, y los cambios desde el portal toman el plan
  del `price_id` vigente del catálogo, no de metadata histórica.
- Los planes tienen permisos efectivos en servidor. Autónomo conserva el núcleo de
  clientes, trabajos, facturas, cobros, documentos, impuestos y asistente; Negocio
  y Premium habilitan Proyectos, Equipo, Gestoría y Análisis avanzado. La prueba y
  la demostración enseñan el recorrido completo. La misma regla se aplica a web,
  API, herramientas del cerebro, WhatsApp del equipo, portal del trabajador,
  automatizaciones y cartera profesional; no se puede saltar cambiando de canal.
  El plan superior se llama **Premium**, no “Sin Límites”, porque conserva límites
  transparentes de uso avanzado y de la futura voz.
- WhatsApp separa dos contextos que no deben confundirse. El número central de
  Bynoesis identifica al titular o al trabajador y sirve para órdenes internas,
  fichaje, parte, costes, justificantes y dudas. Cada negocio puede conectar además
  su propio número comercial para sus clientes finales. El webhook resuelve primero
  `phone_number_id` y WABA receptores y solo después el remitente; contactos,
  conversaciones, documentos y salidas conservan `business_id` y conexión. Un
  número receptor desconocido o discordante se ignora sin crear datos ni responder
  desde otro negocio. Mientras no exista Embedded Signup, administración puede dar
  de alta WABA y `phone_number_id` como conexión pendiente desde la ficha técnica de
  la cuenta; no recibe ni muestra tokens y toda activación queda auditada.
  El número comercial es siempre propiedad del negocio: puede reutilizar el suyo o
  elegir uno separado para atención y citas; Bynoesis no compra un número por cliente.
- Los mensajes comerciales crean una bandeja trazable y un lead o vínculo con el
  cliente dentro de la empresa correcta. Fotos y PDF pasan por la entrada documental
  existente, se previsualizan desde Clientes y nunca se convierten por sí solos en
  gasto o factura. El cliente recibe acuse seguro, puede solicitar baja y el titular
  responde desde el panel únicamente dentro de la ventana de 24 horas; fuera de ella
  se exige una plantilla aprobada.
- El equipo escribe al número central, no al teléfono personal del titular. Puede
  consultar su parte y fichar, enviar `COSTE #trabajo`, dudas, bloqueos y fotos/PDF.
  Todo queda pendiente de revisión. Aceptar un coste lo aplica una sola vez al
  trabajo; descartarlo no altera proyecto ni contabilidad. Campo no ve márgenes;
  un responsable solo puede consultar el presupuesto de proyectos asignados cuando
  el titular activa ese permiso. El parte diario resume aportaciones, costes y
  conversaciones pendientes para evitar interrupciones constantes.
- Un teléfono del canal central solo puede identificar a un titular o a un
  trabajador. Bynoesis rechaza una segunda vinculación y, ante una ambigüedad heredada,
  falla cerrado: informa del conflicto sin ejecutar órdenes ni asociar documentos.
- El perfil documental del negocio controla plantilla, color, logotipo, pie común,
  condiciones y validez predeterminada. Los presupuestos incorporan IVA/IRPF,
  notas específicas y PDF profesional con la misma marca que la factura. Antes de
  compartir se exige revisión; el cliente descarga el PDF desde su enlace aislado y
  su aceptación o rechazo conserva origen, fecha, navegador acotado y una huella
  seudónima de red, nunca la IP en claro. La aceptación solo crea una factura en
  borrador: el titular continúa decidiendo su emisión.
- El OCR privado detecta en ejecución qué modelos de idioma están realmente
  instalados, prioriza catalán, castellano e inglés, corrige orientación/contraste y
  mejora tickets pequeños antes de leerlos. Los importes reconocen expresiones de
  total en los tres idiomas y el endpoint de diagnóstico distingue disponibilidad
  general de preparación trilingüe. La precisión real sigue pendiente de corpus.
- El titular puede abrir desde Ajustes una ventana de soporte de 1, 4, 24 o 72 horas,
  con motivo y permisos concretos. Solo el correo titular puede crearla;
  el administrador no puede autoconcedérsela. Caduca, se revoca y deja evidencia en
  la bitácora encadenada. Por ahora habilita la autorización y muestra el alcance en
  el centro técnico; no existe suplantación silenciosa ni un editor universal.
- El CFO interno conserva un libro mensual append-only de costes reales, previsiones
  y ajustes. El margen observado y el coste por cuenta solo aparecen cuando hay
  entradas reales; MRR comprometido, caja y estimaciones de IA no se presentan como
  la misma cifra.
- Los términos datan del 8 de agosto y describen revisión de facturas, rectificación,
  automatizaciones, suscripción, terceros, incidentes, exportación y límites que la
  ley no permite excluir. Siguen siendo un borrador pendiente de revisión jurídica.
- La web pública tiene una sola puerta de acceso y explica antes de pedir
  credenciales si la persona entra como autónomo/empresa o como gestoría. Las dos
  identidades conservan sesiones y permisos separados. El cliente final no aparece
  como un tercer panel: entra únicamente por el enlace privado de su profesional.
  Una gestoría sin cuenta puede solicitar el espacio profesional o aceptar la
  invitación de un cliente, pero nunca obtiene acceso a empresas por registrarse.
- Bynoesis cubre el ciclo cliente → presupuesto → trabajo/proyecto → fichaje y costes
  → factura → cobro, aislado siempre por `business_id`.
- La entrada documental es común para web y WhatsApp: clasifica tickets, facturas,
  presupuestos, contratos y albaranes; propone y pide confirmación cuando el efecto
  puede ser contable. La huella SHA-256 evita guardar dos veces el mismo contenido
  dentro de un negocio, incluso ante subidas simultáneas; los históricos adquieren
  la huella al reaparecer y nunca se comparan archivos entre negocios. La bandeja
  busca por archivo, cliente, proyecto, nota, contenido leído y tipo, siempre dentro
  de la empresa activa. Los PDF digitales se leen localmente con límites de páginas,
  texto y descompresión. Si no tienen una capa de texto útil, PDFium rasteriza como
  máximo cuatro páginas y Tesseract aplica OCR privado en el mismo servidor, con
  límites de píxeles, tiempo y caracteres; no se envía el documento a una API. Una
  referencia inequívoca del mensaje puede
  asociar el papel al cliente/proyecto, pero nunca se adivina ante ambigüedad.
- El titular dispone del mismo archivo temporal que la gestoría: año, trimestre,
  ingresos, gastos, tickets, pendientes y otros, con búsqueda, estado y primera
  página privada. La fecha efectiva procede de la factura, gasto o recepción ligada;
  no se mueve ni duplica el archivo original.
- Hay portales privados para cliente y trabajador. La gestoría conserva el enlace
  histórico por empresa y añade una cuenta profesional: una misma gestoría puede
  llevar varias empresas mediante invitaciones de un solo uso, acceso explícito y
  revocable, bandeja de revisión, solicitudes y paquetes por período. No puede emitir,
  mover dinero ni ejecutar decisiones fiscales desde esa cartera. El fichaje y
  Veri*Factu conservan registros inmutables.
- La cartera profesional ya funciona como espacio de trabajo fiscal: prioriza
  empresas, compara preparación por trimestre, abre una vista anual, separa
  ingresos, gastos, tickets y pendientes, y previsualiza imágenes o la primera
  página de un PDF dentro del expediente sin habilitar plugins ni iframes. Cada
  negocio conserva un perfil fiscal explícito y corregible. Los modelos 303, 390,
  130/131, 111, 115, 347, 349 y 200/202 se muestran como borradores o necesidades
  de configuración según los datos disponibles; nunca como declaraciones
  presentadas. Las facturas recibidas alimentan el IVA soportado y el resultado
  junto con los gastos simples, sin inventar cuotas que falten.
- El expediente profesional no obliga a recorrer una página interminable: Resumen,
  Documentos, Impuestos, Períodos y Solicitudes son vistas independientes. La
  navegación marca el trabajo activo, conserva trimestre y filtro después de cada
  validación y evita que la cabecera tape tablas al desplazarse.
- La demostración comercial no replica ni simula otra aplicación: crea dos accesos
  dentro del producto real —autónomo y gestoría—, una segunda empresa en la cartera
  multiempresa y un portal real para el cliente final. Todos comparten datos
  ficticios coherentes. Las empresas llevan una marca persistente de demostración:
  se pueden recorrer y descargar sus documentos/paquetes, pero el servidor bloquea
  cambios, automatizaciones, WhatsApp, correo, cobros y acciones fiscales.
- El cerebro funciona por capas: reglas locales, compositor interno, servicio privado
  compatible, proveedor externo compatible y Anthropic como respaldo autorizado.
  Que falle una IA nunca apaga el producto local.
- Bynoesis aparece en todas las secciones con una lectura contextual, el motivo y el
  siguiente paso. La estructura de cada pantalla sigue siendo propia de su función;
  no existe una plantilla universal de KPIs.
- Agenda ofrece un enlace privado y revocable para suscribirse desde Google Calendar,
  Apple Calendar u Outlook sin contratar una API. Cobros importa extractos CSV,
  propone coincidencias explicables y solo registra el pago cuando el titular lo
  confirma.
- Los correos confirmados se persisten antes de intentar la API HTTPS o SMTP, se
  deduplican y reintentan con backoff. Los errores de proveedores y el diagnóstico de preparación
  viven en administración; el cliente ve funciones y preferencias, no infraestructura.
- El panel del fundador incorpora un responsable CISO interno, determinista y de
  solo lectura. Resume controles con evidencia, presión de acceso agregada y eventos
  sin contenido de clientes. Las acciones administrativas quedan en una bitácora
  append-only encadenada por hash; producción exige Google OAuth para el admin.
- Desde cada cuenta, el fundador puede abrir un diagnóstico técnico de solo lectura:
  activación, integración, volúmenes, estados y colas. No enseña nombres de clientes,
  importes, conceptos, mensajes, archivos ni credenciales, y cada apertura queda
  auditada. El soporte todavía no puede modificar datos ni suplantar al titular;
  esa intervención requerirá consentimiento temporal, motivo y alcance explícitos.
- Cada backup se restaura al crearlo y, además, un simulacro semanal independiente
  vuelve a restaurar la última base y verifica el ZIP documental en un entorno
  descartable. La comprobación real del 26 de agosto descubrió que las copias nuevas
  fallaban al reconstruir líneas de facturas emitidas: la propia inmutabilidad las
  confundía con una modificación posterior. El release `d55be0ae6673` suspende únicamente los
  triggers de negocio dentro de la transacción de restauración, conserva claves
  foráneas y restricciones, los reactiva antes de validar y añade el recorrido al
  humo PostgreSQL. El CI restauró correctamente un conjunto con facturas emitidas y
  en producción se creó después una copia nueva de esquema 51; el simulacro
  independiente terminó `ok` en 3,22 s. Ya existe recuperación local actual, pero
  aún falta copiarla a infraestructura externa y ensayar la pérdida total del
  proveedor. La entrada documental admite ClamAV privado por streaming y puede
  fallar cerrado sin enviar archivos a una API externa.
- El alta comercial distingue con claridad entre **probar 14 días** y **contratar
  ahora**. Antes de entrar al panel recoge negocio, nivel de explicación, fiscalidad,
  estilo y vencimiento de factura, medios de cobro, recordatorios, informes,
  gestoría y WhatsApp. Esas elecciones se guardan en el producto y se aplican a la
  operativa; no son una encuesta decorativa.
- En producción, el alta pública queda cerrada por defecto. No acepta términos,
  crea cuentas ni inicia el alta con Google hasta configurar la identidad legal
  mínima y activar expresamente la apertura. Las cuentas existentes siguen entrando
  y la web cambia sus llamadas a «Solicitar acceso» sin enseñar diagnósticos internos.
- El diagnóstico previo a apertura comprueba un dominio canónico único, identidad
  legal, copias externas, WhatsApp, correo, Stripe, voz, lectura de imágenes y ClamAV.
  Las capacidades de audio/OCR se describen en la web según disponibilidad real.
- La facturación nativa admite borradores editables, varias líneas con cantidad,
  precio, descuento e IVA, series separadas para factura completa, simplificada y
  rectificativa, vencimiento configurable, duplicación y programaciones recurrentes.
  La emisión congela cabecera y líneas. La entrega genera el PDF al salir de la
  outbox de correo y el historial reúne emisión, remisión, visualización y cobros.
- Una factura emitida se corrige mediante un asistente rectificativo por diferencias:
  enseña original, período y efecto económico, exige causa y confirmación, crea un
  único borrador revisable y mantiene el original intacto. R5 queda reservado a F2;
  la modalidad por sustitución no se ofrece sin validación fiscal externa.
- WhatsApp distingue un ticket de gasto de un `ticket de venta` F2. Reutiliza un
  cliente habitual solo si la referencia es inequívoca, conecta trabajos cerrados
  con su borrador y exige otro SÍ para emitir o entregar. Tras confirmarlo asigna
  número, valida los datos obligatorios, genera el PDF y prepara email o plantilla
  WhatsApp; la misma factura alimenta KPIs, impuestos, cobros y gestoría.
- La salud pública identifica el release desplegado con una huella segura y
  `/ready` devuelve además la versión real del esquema. El checkout de Stripe pide
  dirección de facturación, NIF fiscal y cálculo automático de impuestos porque el
  catálogo se comunica como base imponible más IVA; el resultado todavía debe
  validarse en modo test antes de cobrar.
- El perímetro admite el alias público para que llegue al servidor, pero lo redirige
  con 308 al único dominio canónico conservando ruta y parámetros. Los enlaces,
  callbacks y etiquetas canonical se construyen siempre desde ese mismo origen.
- Los formularios mutables validan `Sec-Fetch-Site` y `Origin`. Un navegador que
  acredita `same-origin` no depende del `Host` interno elegido por Railway; si esa
  evidencia no existe, se aplica la lista cerrada de orígenes HTTPS. `cross-site`
  siempre se rechaza, igual que dominios externos, puertos no estándar y orígenes
  mal formados.
- Una anulación Veri*Factu nunca borra la factura: exige confirmación escrita,
  conserva el alta, crea otro registro inmutable con huella oficial, lo encadena al
  anterior y lo remite mediante una cola durable independiente.
- La actualización de facturación profesional admite datos reales del esquema 32:
  asigna serie y línea a facturas ya emitidas dentro de la transacción de migración
  y reinstala inmediatamente la inmutabilidad. El CI reproduce este salto con una
  factura emitida tanto en SQLite como en PostgreSQL.

- Cada oficio tiene su plantilla de catálogo con el IVA ya puesto en cada partida y
  la marca de si es material o mano de obra. El autónomo la ve entera antes de
  cargarla en `/b/{id}/oficios`, con su oficio el primero cuando se deduce de lo que
  escribió al darse de alta; cargarla dos veces no duplica nada. Ese marcado es lo
  que permite avisar del 40% de material que hace decaer el tipo reducido en obras
  de vivienda: Bynoesis avisa y nunca cambia el tipo.
- El canal de Meta está construido y revisado —firma, idempotencia, medios acotados
  y cola durable—, pero **los cinco avisos proactivos al titular no son aprobables
  todavía**: mandan el mensaje entero en un único hueco de plantilla. Las cuatro
  plantillas al cliente sí encajan. Los cuerpos de las nueve viven en
  `noesis/whatsapp_templates.py`. Revisión completa en [[Revision-Meta]].

## Política comercial en el código actual

- Catálogo: **29 / 49 / 99 € al mes + IVA**.
- Planes: **Autónomo / Negocio / Premium**. Los derechos comercializados se validan
  en servidor; una cuenta sin plan reconocido recibe como máximo el núcleo de
  Autónomo, nunca acceso total por error.
- La prueba dura 14 días y permite operar con normalidad.
- El código permite probar o contratar cada plan en modalidad mensual/anual. Quien
  contrata configura primero el negocio y después revisa el plan antes de ir al
  checkout; quien prueba entra al panel sin tarjeta tras la misma puesta en marcha.
  En producción esa entrada permanece cerrada hasta superar la puerta de apertura.
- Al caducar, cancelar o quedar un pago pendiente, el titular puede entrar y consultar
  sus datos, pero no crear, cambiar, enviar ni ejecutar automatizaciones.
- El bloqueo se aplica en servidor a web/API, portales, WhatsApp, colas y tareas
  programadas; no depende de ocultar botones.
- Pagos, transferencias, presentación fiscal, emisión definitiva, envíos sensibles y
  borrados irreversibles requieren confirmación específica del autónomo.

## Publicado frente a construido

La URL pública y la última comprobación constan en `project-state.json`. Los cambios
del código actual solo se consideran publicados después de fusionar, desplegar,
aplicar migraciones y repetir `/ready` y los flujos afectados. **Nunca se deduce que
algo está en producción porque exista en una rama o haya pasado tests.**

## Límites que siguen abiertos

- WhatsApp, Stripe, correo, Google OAuth, el proveedor privado de IA y AEAT están
  implementados detrás de adaptadores, pero necesitan credenciales y una prueba real
  extremo a extremo. La secuencia exacta está en [[Conectar-APIs]]. Stripe debe
  probar además la nueva máquina de estados, eventos fuera de orden, derechos por
  plan y el IVA antes de usar claves live. La facturación es nativa y no se
  conecta a otro SaaS. El calendario bidireccional y la conexión bancaria automática
  siguen pendientes; la suscripción ICS y la conciliación CSV ya funcionan en local.
- La transcripción mantiene adaptadores y degradación segura, pero requiere desplegar
  y validar Groq/faster-whisper. El OCR de imágenes y PDF escaneado ya es íntegramente
  local con pytesseract, PDFium y los idiomas `cat/spa/eng`; falta confirmar los
  binarios desplegados y medirlo con un corpus real en catalán/castellano/inglés
  antes de prometer una precisión comercial. La extracción externa consentida queda
  solo como respaldo.
- La cartera de gestoría ya cubre identidad, varias empresas, revisión documental,
  primera lectura fiscal, períodos y MFA TOTP con recuperación de emergencia. Antes
  de abrirla a despachos reales faltan recuperación de contraseña por correo,
  passkeys/roles más finos, revisión del cálculo con un asesor fiscal y una prueba
  piloto con datos y responsables reales.
- Antes del piloto deben rotarse todos los secretos que hayan aparecido en capturas
  o documentos compartidos y someter privacidad, términos y contrato de encargo a
  revisión jurídica profesional. La identidad legal mínima ya está completada y
  publicada; ningún secreto propuesto en un informe debe reutilizarse.
- La entrega de factura por WhatsApp requiere aprobar en Meta la plantilla
  `noesis_factura_lista`; el recorrido interno y la cola ya están construidos.
- Falta auditoría externa de seguridad, privacidad y fiscalidad, desplegar y probar
  ClamAV, restaurar una copia descargada del almacenamiento externo en otra
  infraestructura y pilotar con 3-5 negocios. El simulacro interno no sustituye esa
  prueba de desastre ni un pentest independiente.
- La memoria de cliente es explicable y corregible; no se promete aprendizaje autónomo
  perfecto ni decisiones legales/fiscales sin humano.
- Exenciones, no sujeción, identificación fiscal extranjera y subsanación de un
  registro rechazado todavía requieren desarrollo y validación fiscal antes de
  admitir esos casos. El 0% visible significa tipo cero, no exención.

## Regla para cualquier IA

Toda modificación de producto actualiza `project-state.json` y `Registro-QA.md`; si
cambia arquitectura, también `Mapa-codigo.md`, `Arquitectura.md` o `Decisiones.md`.
El CI ejecuta `scripts/check_project_truth.py` y rechaza una PR que cambie `src/noesis/`
sin esas actualizaciones.
