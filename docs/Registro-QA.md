# Registro de QA

## 2026-08-06 — dos cuentas demo reales y OCR privado de PDF escaneado

### Qué se probó y con qué resultado

- **Datos conectados:** la siembra crea/reutiliza el acceso real del autónomo,
  una cuenta real de gestoría, dos empresas en su cartera y el portal del cliente
  correcto. Repetirla no duplica negocios, clientes ni facturas.
- **Contenido útil:** la cuenta principal tiene al menos siete clientes, facturas y
  gastos en seis meses activos, catálogo, proveedores, CRM, trabajos, dos
  trabajadores, proyecto con presupuesto/costes/horas/tareas, documentos PDF/JPEG
  válidos y solicitudes de gestoría. El portal de cliente tiene factura y
  presupuesto; la gestoría tiene dos empresas y puede descargar un paquete ficticio.
- **Navegación real:** login del autónomo y render de todas las secciones del panel
  —Inicio, Trabajos, Proyectos, Clientes, Dinero, Análisis, Ingresos, Costes,
  Presupuestos, Facturas, Cobros, Impuestos, Equipo, CRM, Productos, Documentos,
  Asistente y Ajustes—; login/cartera/ficha/paquete de gestoría y portal/PDF del
  cliente. No se usó una aplicación o plantilla alternativa.
- **Solo lectura:** una mutación de API del autónomo queda en 403, aceptar un
  presupuesto desde el portal queda en 402 y descargar el PDF o paquete de demo no
  registra eventos ni entregas ficticias. Automatizaciones y envíos reutilizan el
  mismo bloqueo de suscripción del servidor.
- **PDF escaneado:** un PDF compuesto únicamente por una imagen se rasteriza realmente
  con PDFium y pasa cada imagen por el adaptador OCR local; el resultado alimenta
  importe y clasificación. Una página de dimensiones absurdas se rechaza antes de
  renderizar. Los límites son cuatro páginas, cinco millones de píxeles por página,
  ocho segundos de Tesseract por página y 24.000 caracteres por documento.
- **Pruebas:** 4 pruebas focalizadas, Ruff, `compileall`, Bandit alto, detección de
  secretos y `pip-audit` verdes; suite completa final **409/409** y ciclo SQLite
  0 → 40 → 0 → 40 verdes. `check_project_truth.py` confirma estado/esquema/precios.
- **CI tras publicar:** el primer run identificó correctamente la contraseña pública
  de la demo como `Secret Keyword`. Se marcó con la excepción inline oficial y una
  explicación de alcance —no se relajó el detector ni la baseline—. El primer humo
  PostgreSQL no llegó a descargar las Actions por un `Service Unavailable` de GitHub,
  sin ejecutar código de Noesis; se reintentó el workflow completo.

### Qué no se ha probado

- El Windows local no tiene instalado el binario de Tesseract: se verificaron las
  dependencias Python, la rasterización real y el contrato del adaptador con un OCR
  controlado. `railpack.json` instala Tesseract `spa/eng` en Railway, pero todavía
  hay que verificar ese binario y medir precisión/latencia con tickets y PDFs reales
  en castellano/catalán después del despliegue.
- No se enviaron WhatsApps, correos, cobros ni registros fiscales y no se hizo QA
  visual en navegador. La demo los bloquea deliberadamente; el render y los enlaces
  principales sí se recorrieron mediante la aplicación FastAPI real.
- El candidato aún no se considera publicado: falta commit, despliegue, esquema 40,
  activación temporal de `NOESIS_SEED_DEMO` y prueba autenticada en producción.

## 2026-08-06 — cartera multiempresa y PDF contextual desde WhatsApp

### Qué se probó y con qué resultado

- **Aislamiento:** una cuenta profesional recibe acceso explícito a dos empresas y
  no ve una tercera. La revocación corta el acceso. Cliente y proyecto de otro
  negocio —incluida una factura— se rechazan aunque se envíen identificadores válidos.
- **Invitaciones:** token de un solo uso guardado solo como huella, correo fijado por
  la invitación, contraseña mínima de 12 caracteres, rate limit compartido y sesión
  con caducidad por inactividad. El portal histórico `/g/` sigue funcionando.
- **Baja RGPD:** una empresa con invitación y acceso profesional aceptado se elimina
  sin dejar acceso huérfano ni bloquear la baja; la cuenta de gestoría conserva sus
  otros clientes.
- **Documentos:** un PDF digital se lee localmente, detecta `48,40` y se clasifica
  como ticket. Un PDF enviado por WhatsApp con el texto «Instalación Hotel Mar» se
  enlaza al proyecto y hereda su cliente; una coincidencia ambigua queda sin enlazar.
- **Interfaz:** comparación visual conjunta con el panel principal y revisión de
  acceso, cartera y ficha de empresa en navegador. Conserva marca, lienzo, tipografía
  y jerarquía «primero», con estructura propia para una gestoría.
- **Pruebas:** Ruff verde; 11 pruebas focalizadas de gestoría y la prueba directa de
  WhatsApp verdes; suite completa final **405/405**. Bandit, detección de secretos,
  `pip-audit`, `compileall`, fuente de verdad y ciclo 0 → 39 → 0 → 39 verdes.
- **Publicación:** CI general y humo PostgreSQL verdes para `1228da6`. Producción
  devuelve release `1228da63f625` en `/health` y estado `ready` con esquema 39.

### Qué no se ha probado

- No se llamó a Meta, correo, Stripe, AEAT ni a una gestoría real. Un PDF compuesto
  solo por imágenes no lo puede leer pypdf: necesita Tesseract/visión autorizada.
  MFA/passkeys, recuperación de contraseña y permisos por rol siguen pendientes.

## 2026-08-06 — búsqueda útil dentro de Documentos

### Qué se probó y con qué resultado

- **Campos:** una misma consulta encuentra nombre de archivo, nota, texto OCR,
  cliente y proyecto. El tipo interno `factura_recibida` también responde a la
  búsqueda humana «factura recibida».
- **Comportamiento:** ignora mayúsculas, limita la entrada a 120 caracteres y usa
  parámetros SQL. Un resultado del segundo negocio con el mismo nombre/nota nunca
  aparece en el primero.
- **Interfaz:** el campo vive junto al filtro de estado, espera 180 ms mientras se
  escribe, explica cuántos resultados hay y conserva el vacío de primera subida
  cuando no se está buscando.
- **Pruebas focalizadas:** 18 pasan y Ruff pasa. La ruta con búsqueda se añade al
  humo PostgreSQL. Suite completa final: **400 pruebas, 0 fallos**.

### Qué no se ha probado

- CI ejecutó la consulta con PostgreSQL y producción sirve el release/esquema
  esperado. Falta recorrer visualmente la pantalla con una sesión real. No se ha
  construido índice de texto completo: el `LIKE` parametrizado es suficiente para
  el volumen del piloto; se medirá antes de añadir FTS o un buscador externo.

## 2026-08-06 — un solo origen público

### Qué se probó y con qué resultado

- **Hallazgo real:** `https://www.bynoesis.com/` respondía 200 igual que el dominio
  canónico. Las cabeceras y etiquetas eran correctas, pero había dos orígenes
  públicos sirviendo la misma web.
- **Perímetro:** la construcción de hosts permitidos incorpora el canónico y su alias
  sin comodines. Railway privado, healthcheck, localhost y hosts configurados siguen
  tratados de forma independiente.
- **Redirección:** en producción solo el alias recibe 308 hacia `BASE_URL`; ruta y
  query se conservan. El dominio canónico sigue en 200 y la respuesta 308 conserva
  las cabeceras anti-iframe y demás controles del middleware exterior.
- **Pruebas focalizadas:** 3 pasan y Ruff pasa. Suite completa final: **399 pruebas,
  0 fallos**.

### Qué no se ha probado

- Producción sirve el release del commit: `www` devuelve 308 con la ruta/query intacta,
  seguirlo termina en 200 y el canónico directo devuelve 200. Las pruebas autenticadas
  del P0 siguen separadas porque requieren una cuenta real.

## 2026-08-06 — deduplicación documental aislada por negocio

### Qué se probó y con qué resultado

- **Servicio universal:** dos subidas con bytes idénticos al mismo negocio devuelven
  el documento existente y solo dejan una fila y un fichero. Los mismos bytes en
  otro negocio se aceptan como documento propio.
- **Históricos:** si un documento anterior no tiene huella, la repetición compara
  únicamente candidatos del mismo negocio y tamaño, completa SHA-256 y rechaza la
  copia. No se recorre ni consulta contenido de otro cliente.
- **Carreras:** el índice parcial único resuelve dos inserciones simultáneas; el
  servicio borra el fichero sobrante antes de devolver el conflicto HTTP 409.
- **Migración 38:** ciclo SQLite 37 → 38 → 37 → 38 correcto. El humo PostgreSQL
  incorporó una inserción doble y recibió la restricción de integridad real.
- **Pruebas:** 17 focalizadas pasan; Ruff pasa y Bandit no encuentra severidad alta.
  Suite completa final: **398 pruebas, 0 fallos**.

### Qué no se ha probado

- Producción respondió `/health` con el release del commit y `/ready` con estado 200
  y esquema 38. No se ha repetido todavía una subida manual con almacenamiento
  externo ni se usaron credenciales de proveedores.

## 2026-08-06 — release verificable, correo coherente y Checkout con IVA

### Qué se probó y con qué resultado

- **Punto de partida:** suite completa del `main` recibido, **392 pruebas, 0 fallos**.
- **Release:** `/health` devuelve la huella saneada configurada y `/ready` devuelve
  la misma huella más la migración aplicada. En producción, un release desconocido o
  inválido es bloqueo del doctor; en local sigue siendo solo informativo.
- **Correo:** el doctor acepta la API HTTPS sin exigir SMTP. El helper de factura
  adjunta reutiliza `send_email`, por lo que una instalación con Brevo ya no intenta
  saltarse la API hacia un puerto SMTP bloqueado. El PDF conserva nombre y bytes.
- **Stripe:** Checkout anual conserva el `price_id` correcto y añade dirección
  obligatoria, recogida de NIF y `automatic_tax=true`. Una configuración completa de
  credenciales con el cálculo desactivado se marca como bloqueo.
- **Pruebas focalizadas:** 17 pasan, 0 fallos. Ruff y Bandit pasan sin hallazgos;
  `pip-audit` no encuentra vulnerabilidades conocidas en las dependencias instaladas.
- **Suite completa final:** 396 pruebas, 0 fallos. La comprobación de verdad
  documental también se ejecuta antes de publicar.

### Qué no se ha probado

- Railway todavía debe desplegar el candidato y demostrar la huella por HTTP.
- No se han usado credenciales de Brevo ni Stripe; entregabilidad e IVA real se
  validarán en la fase externa.

## 2026-08-02 — el chat web emite el borrador que él mismo te dice que emitas

### Qué se probó y con qué resultado

- **El producto daba una instrucción que no sabía cumplir.** Al crear una factura
  hablando, la respuesta termina con «escribe *emitir factura 2*». Esa orden solo la
  entendía la capa de WhatsApp (`_prepare_invoice_action`), pero el texto se genera en
  `nlu.format_reply`, que también usa la web. Reproducido: por el chat web la orden
  caía al coach general y **el borrador se quedaba sin emitir**. Ahora el cerebro común
  la reconoce y emite: comprobado de punta a punta con servidor real, factura
  `2026/0002` por 605,00 €, estado `enviada` y vencimiento asignado.
- **No se ha tocado el flujo de WhatsApp**, que es el que más protección necesita
  porque una nota de voz puede entenderse mal. Verificado con el webhook real: pedir
  «emitir factura 3» sigue creando la acción pendiente `emitir_factura` y dejando la
  factura en `borrador` hasta recibir el SÍ.
- **La validación fiscal sigue mandando.** Con el cliente sin NIF ni domicilio, la
  emisión se rechaza por los dos canales. Se comprobó también que crear una factura
  nueva no se confunde con emitir una existente: «factura a Juan por reparación 95 €»
  sigue creando borrador y «factura el trabajo 42» sigue conectando el trabajo.
- **Los errores dejan de filtrar jerga interna.** Antes se leía «Parámetros inválidos
  para enviar_factura: …». Ahora solo el motivo accionable: «Antes de emitir completa:
  NIF del cliente, domicilio del cliente».
- **Promesa de voz del plan Sin Límites.** «100 minutos de llamadas incluidos» figuraba
  como prestación activa en la página pública de precios y, más grave, en la pantalla
  de contratación del panel, cuando no existe telefonía en el código. Se traslada al
  bloque de la recepcionista en beta, indicando que se incluirán cuando se active y
  que hasta entonces no se cobra por ella.
- **Copias de seguridad: dos pruebas en rojo permanente en macOS.** `_backup_dir()`
  devolvía la ruta sin normalizar y `latest_verified_backup()` sí la normalizaba; en
  macOS `/var` es un enlace a `/private/var`, así que nunca coincidían. Normalizada en
  el origen, conservando la comprobación de que el fichero cuelga del directorio de
  copias. Las cinco pruebas de copias pasan.
- **Suite completa: 392 pasan, 71 subtests, ningún fallo** (antes 382 con 2 en rojo).

### Qué no se ha probado

- Nada con credenciales reales: Stripe, Meta, SMTP, AEAT y Google siguen sin validar
  extremo a extremo. Este cambio no los toca.
- La entrega al cliente tras emitir desde la web sigue haciéndose desde Facturas; el
  chat web no prepara el envío, solo emite.

## 2026-07-30 — las páginas legales entran en el sitio y la portada recupera su título

### Qué se probó y con qué resultado

- **Las seis páginas legales usaban un armazón propio y más viejo**: sin descripción
  para buscadores, sin canonical y, sobre todo, **sin el menú del sitio**. Están en el
  sitemap, así que alguien podía aterrizar en `/privacidad` desde Google y quedarse sin
  forma de llegar al resto de la web. Ahora extienden la misma plantilla que las demás.
  Verificado en las seis: 200, menú presente, canonical correcto y descripción propia
  escrita para cada una. La llamada a la acción se retira de los textos legales —no es
  sitio para vender— y se mantiene en `/cumplimiento`, que es divulgativa.
- **La portada tenía diecinueve `<h1>`.** La maqueta del producto reproduce dieciocho
  pantallas del panel y cada una traía el suyo. Es el retrato de una app dentro de una
  página: un buscador no sabe de qué trata la portada y un lector de pantalla anuncia
  diecinueve títulos principales. Convertidos a `<h2 class="demo-title">` y extendidas
  **solo las cuatro reglas CSS que les afectaban**, comprobado una por una, para que se
  vean igual. Ahora la portada tiene un `<h1>` y las doce páginas públicas pasan la
  revisión de jerarquía sin saltos de nivel.
- **Tres direcciones de correo distintas conviviendo**: el pie mostraba una variable, la
  política de cookies un Gmail escrito a mano y la página de contacto otra puesta a
  mano. Todas pasan a la misma variable y el valor de respaldo deja de ser una cuenta
  personal. Igual con la fecha de actualización, que estaba a mano en dos páginas.
- **Enlaces internos e imágenes**: recorridas las doce páginas públicas, **ningún enlace
  roto** y **ninguna imagen sin texto alternativo**.
- **Añadido**: ficha de empresa para buscadores (JSON-LD, se comprueba que es JSON
  válido porque uno inválido Google lo ignora sin avisar) y un salto al contenido para
  quien navega con teclado, visible solo al recibir el foco.
- **Retirado**: `_legal_footer.html`, que ya no usaba nadie.
- Pruebas nuevas: **3 verdes** en `test_seo.py` (8 en total). Fijan que toda página del
  sitemap se describa y conserve el menú, que la portada tenga un solo encabezado y que
  la ficha de empresa sea legible.
- **Suite completa: 384 tests, todos los cuerpos en verde.** Los dos únicos errores son
  el artefacto de Windows ya conocido al limpiar la carpeta temporal de
  `test_security_operations`; ejecutado solo, pasa. Ruff, bandit y el validador de la
  fuente de verdad, limpios.

### Qué no se pudo probar

- **El aspecto real de las páginas legales y de la maqueta.** No hay navegador headless
  disponible en el entorno, así que la comprobación del CSS es por lectura de reglas, no
  por captura. El riesgo está acotado —se extendieron cuatro selectores concretos y la
  clase nueva no la usa nada más—, pero conviene una mirada humana a `/privacidad` y a
  la maqueta de la portada.
- **Que Google reconozca la ficha de empresa**: eso se ve en Search Console días
  después. Aquí solo se garantiza que el JSON es válido.

## 2026-07-30 — recuento de visitas sin cookies ni terceros

### Qué se probó y con qué resultado

- **Migración 37 (`page_views`)** con ciclo completo de ida y vuelta: 37 → 36 → 37 sin
  residuos. La tabla guarda página, día y dominio de procedencia con índice único sobre
  los tres, de modo que una segunda visita **suma en la fila existente** en lugar de
  añadir una nueva: crece con el número de páginas, no con el de visitas.
- **Solo se guarda el dominio de procedencia, nunca la URL entera.** Probado con
  `https://www.google.com/search?q=algo+personal`: en la tabla queda `www.google.com` y
  se comprueba que el término buscado **no aparece en ninguna columna**. Es lo que
  convertiría el recuento en dato personal.
- **Exclusiones verificadas**: `/static/`, `/robots.txt`, `/health`, `/api/...`, el panel
  y las rutas de sesión no se cuentan. Esta última exclusión la descubrió la propia
  prueba: al pedir `/admin` el cliente sigue la redirección a `/login`, que sí se estaba
  contando. Se añadieron las rutas de sesión a la lista, para no contar lo mismo que
  `robots.txt` esconde de los buscadores.
- **Que fallar midiendo no tumbe la web**: forzando una excepción en el recuento, la
  página sigue devolviendo 200. Medir es información, no funcionalidad.
- **Panel del fundador**: la sección «Visitas de la web» se pinta con totales, páginas
  más vistas y procedencias, comprobado con datos reales en local.
- **Política de cookies actualizada**: mantiene que no hay cookies de analítica —sigue
  siendo cierto— y añade qué se cuenta y qué no se guarda.
- Pruebas nuevas: **5 verdes** en `test_page_views.py`. Ruff limpio.

### Hallazgo aparte: el acceso al panel estaba roto y ningún test lo decía

Al pasar la suite completa apareció un fallo que **no venía del recuento**, sino del
cambio anterior a varios administradores. `is_admin_email()` mira `ADMIN_EMAILS`, pero
`ADMIN_EMAIL` se deriva de ella y quedaban desacopladas: cambiar solo una no surtía
efecto. Consecuencias reales, las dos malas:

- El test que comprueba que el panel muestra el diagnóstico interno **fallaba**: el
  fundador acababa redirigido al login.
- Peor, el test que comprueba que **falta de Google OAuth bloquea al administrador**
  seguía en verde por el motivo equivocado: no bloqueaba por OAuth, sino porque ya no
  reconocía a nadie como administrador. Un test que pasa por casualidad es peor que
  uno que falla, porque nadie lo mira.

Arreglado en el origen: `is_admin_email()` consulta ambas variables, de modo que no
puedan divergir en silencio. Se añade una prueba que fija justo eso. Los 14 tests del
centro de mando y los 12 de solicitudes quedan en verde, y el de OAuth ya comprueba lo
que dice comprobar.

### Qué no se pudo probar

- **El recuento en producción con visitas reales**: hasta que se despliegue no hay
  tráfico que contar. En local solo se han simulado peticiones.
- **Cuánto ocupa a largo plazo**: la estimación es baja por el diseño agregado, pero no
  hay medida sobre meses de tráfico real. No hay borrado automático de filas antiguas;
  si algún día molesta, se añade.
- **Límite conocido, no cerrado**: la procedencia la envía el navegador, así que quien
  quiera puede mandar cabeceras `Referer` inventadas y crear una fila por cada dominio
  falso. La longitud está acotada (200 caracteres la ruta, 120 el dominio) y solo se
  cuentan respuestas correctas de páginas públicas, pero no hay tope de dominios
  distintos por día. Se deja así a propósito: hoy no hay tráfico que lo justifique y la
  única consecuencia sería una lista de procedencias sucia. Si aparece, la solución es
  un tope diario, no más validación.
- **Comparar la cifra con otra fuente**: no hay Google Analytics ni logs del proveedor
  con los que cruzar el número, así que no se ha validado contra una segunda medida.
- **Suite completa en Windows, con un aviso**: 381 tests, todos los cuerpos en verde. El
  único error aparece al limpiar la carpeta temporal de `test_security_operations`
  cuando corre dentro de la suite: Windows no deja borrar un fichero SQLite que sigue
  abierto. Ejecutado solo, pasa. En Linux —donde corre CI— borrar un fichero abierto es
  legal, así que no afecta. Es ruido del entorno de desarrollo, no del código, y queda
  anotado para no confundirlo con un fallo real la próxima vez.

## 2026-07-29 — buscadores y página de dirección inexistente

### Qué se probó y con qué resultado

- **`robots.txt` y `sitemap.xml`**, que no existían: sin ellos un buscador descubre el
  sitio a tropezones y puede indexar lo que no debe. El robots excluye panel, API,
  portales por token y formularios de sesión; el mapa lista solo las doce páginas
  públicas. Verificado que el XML es válido y que **ninguna ruta privada aparece** en él.
- **Página 404 propia**: una dirección mal escrita devolvía `{"detail":"Not Found"}`, el
  error crudo del servidor, que parece una avería. Ahora se pinta con el diseño del sitio
  y ofrece salidas. Comprobado que **la API sigue devolviendo JSON**: quien la consume
  espera datos, no una página.
- **`/favicon.ico`** daba 404; los navegadores antiguos piden esa ruta fija. Se sirve el
  logotipo existente.
- Pruebas nuevas: **5 verdes** en `test_seo.py`. Ruff limpio.

### Qué no se pudo probar

- **Que Google indexe de verdad**: eso exige dar de alta el sitio en Search Console y
  esperar días. El sitemap está listo para enviárselo.

## 2026-07-29 — el panel admite varios responsables

### Qué se probó y con qué resultado

- **`NOESIS_ADMIN_EMAIL` acepta ahora varios correos separados por coma**, como ya hacía
  `NOESIS_ALLOWED_HOSTS`. El motivo: un equipo de dos no debería compartir una misma
  cuenta para entrar al panel, porque entonces ninguna acción queda atribuida a nadie.
  La marca `is_admin` de la base seguía existiendo pero no había forma de activarla sin
  tocar la base a mano.
- Se centraliza la comprobación en `config.is_admin_email()`, usada por el guardia de
  sesión y por el panel, en lugar de repetir la misma condición en dos sitios.
- **Pruebas nuevas: 3 verdes.** Cubren varios correos, normalización de mayúsculas y
  espacios, rechazo de cualquier otro y el caso sin configurar, donde nadie es
  administrador. Las 8 de solicitudes siguen pasando; Ruff limpio.

### Qué no se pudo probar

- **Entrar de verdad con el segundo correo** en producción: hace falta que exista esa
  cuenta, y el alta pública sigue cerrada.
- Queda el error intermitente conocido de Windows al limpiar carpetas temporales
  (`PermissionError` en `tearDown`), ajeno a este cambio y que no se reproduce en Linux.

## 2026-07-27 — el correo no salía: Railway bloquea SMTP

### Qué se probó y con qué resultado

- **Diagnóstico**: el registro de Railway mostraba `[Errno 101] Network is unreachable`
  al conectar con `smtp.hostinger.com`. Se descartaron una a una las causas habituales:
  desde fuera de Railway ese servidor **conecta y acepta autenticación en el 465**, el
  dominio **solo resuelve a IPv4** (así que no era un problema de rutas IPv6), y el MX y
  el SPF del dominio están bien. La conclusión es que Railway bloquea la salida a los
  puertos de SMTP, como otras plataformas del mismo tipo.
- **Vía nueva por HTTPS**: se añade Brevo al adaptador de correo, solo con biblioteca
  estándar para no incumplir la regla de mínimas dependencias. Verificado contra un
  servidor simulado que la petición lleva la clave en su cabecera, el remitente separado
  en nombre y dirección como exige la API, y los adjuntos codificados en el cuerpo.
- **Degradación conservada**: sin clave de API se sigue usando SMTP igual que antes, y
  sin ningún proveedor se registra en el log en lugar de fallar. Ambos casos con prueba.
- Pruebas nuevas: **5 verdes** en `test_email_api.py`. Las 8 de solicitudes siguen
  pasando y Ruff está limpio.

### Qué no se pudo probar

- **Un envío real por la API**: falta la clave de Brevo, que da de alta el founder. La
  prueba definitiva es enviar una solicitud tras configurarla y comprobar que el correo
  llega a `info@bynoesis.com`.
- **Que el dominio quede verificado** en el proveedor: sin ese paso los correos saldrían
  pero acabarían en spam.

## 2026-07-27 — el formulario se colgaba: puerto SMTP y envío bloqueante

### Qué se probó y con qué resultado

- **Causa 1, afecta a TODO el correo del sistema**: `_send_msg` abría siempre `SMTP` y
  pedía `starttls()`, que es el modo del puerto 587. Producción usa el **465**, que exige
  TLS desde el primer byte. Con el modo equivocado la conexión no falla rápido: se queda
  esperando hasta agotar los 15 segundos. Ahora se elige `SMTP_SSL` para el 465 y se
  mantiene STARTTLS para el resto.
- **Causa 2, introducida por mí**: los dos correos de la solicitud se enviaban durante la
  petición, así que el visitante esperaba hasta 15 segundos por cada uno —30 en total—
  ante una pantalla en blanco. El proyecto ya tenía cola durable con reintentos
  (`queue_email` + `process_email_outbox`) y no la usé. Corregido también en la
  invitación del panel, donde el enlace ya se muestra en pantalla.
- **Medido con un SMTP configurado que no responde**: la respuesta pasa de colgarse a
  **0,22 s**, y los dos correos quedan encolados con estado `queued`.
- Claves de idempotencia por solicitud para que un reintento no duplique correos.
- Pruebas del módulo: **8 verdes**. Ruff en verde.

### Qué no se pudo probar

- **Un envío real por el puerto 465**: la corrección es la estándar para SSL implícito,
  pero sin credenciales válidas en local no se ha completado un envío de verdad. Es justo
  lo que hay que confirmar tras desplegar: enviar una solicitud y comprobar que el correo
  llega a `info@bynoesis.com`.

## 2026-07-27 — el señuelo antispam podía tragarse solicitudes reales

### Qué se probó y con qué resultado

- **Mensaje de confirmación reescrito**: al enviar sale «Gracias, tu solicitud se ha
  enviado» con un icono de visto y la promesa explícita de contacto en 24 horas
  laborables. Si el envío se repite, el texto se adapta para no dar a entender que se ha
  creado otra solicitud.
- **Destino del aviso**: las solicitudes van ahora a `info@bynoesis.com` mediante su
  propia variable `NOESIS_REQUESTS_EMAIL`, no al correo del administrador. Verificado con
  el servidor: el aviso sale a ese buzón y la confirmación al solicitante.

- **Campo señuelo renombrado**: se llamaba `web`, y el autorrelleno del navegador puede
  completar solo un campo con ese nombre (Chrome ignora a menudo `autocomplete="off"`).
  Si ocurría, el visitante veía la pantalla de gracias pero su solicitud se descartaba
  en silencio por parecer un robot. Pasa a `nsx_check`, que no casa con ninguna heurística
  de autorrelleno, y cada descarte queda registrado en el log: un falso positivo aquí
  significa perder un cliente sin que nadie se entere.
- **Repetir el envío deja de ser un error**: con el mismo correo tres veces, la cuarta
  devolvía una caja roja con un texto que sonaba a éxito. Ahora se agradece y se explica
  que ya la teníamos, sin duplicar la solicitud. El corte por IP se mantiene para frenar
  envíos masivos, que es el caso que sí es un ataque.
- Verificado el ciclo completo contra el servidor: envío normal, envío repetido, mensaje
  correcto en cada caso y que no se crean duplicados en base de datos.
- Pruebas del módulo: **8 verdes** (una nueva para separar al insistente del bombardeo).

### Qué no se pudo probar

- **El autorrelleno real de un navegador**: la causa es conocida y documentada, pero no
  se ha reproducido con Chrome rellenando el campo. Conviene enviar una solicitud real
  desde el móvil tras desplegar y confirmar que aparece en el panel.

## 2026-07-27 — repaso de copy y una colisión de CSS en los retratos

### Qué se probó y con qué resultado

- **Retratos de los fundadores, corregidos**: la regla `.pilot-stories img`, escrita para
  la ilustración del taller, alcanzaba también a las fotos nuevas por estar en la misma
  sección y, al declararse después con igual especificidad, ganaba: los estiraba al 100 %
  y les aplicaba `mix-blend-mode: multiply`, fundiendo el fondo blanco del retrato con el
  crema de la página. Se acota con la clase `.pilot-illustration`, también en la regla
  responsive. Verificado que ninguna regla alcanza ya a los retratos.
- **Tamaños declarados alineados con el CSS**: los retratos anunciaban 56 px con el CSS
  pintando 44, y en equipo 112 contra 72. Se igualan para evitar saltos de maquetación.
- **Banda del hero**: usaba la maqueta de cifras de impacto (dato grande en serif) con
  conceptos dentro, así que «1 hilo» se leía como una métrica inexistente. Pasa a tres
  promesas en columnas. Se retira la nota que recordaba que aún no hay resultados medidos.
- **Bloque del asistente**: el titular se definía negando («No es un chat aparte») y la
  cita informaba sin ofrecerse a actuar, incumpliendo la regla de voz documentada. Se
  reescribe con un caso de cobros —módulo central, no proyectos, que es secundario— que
  cierra ofreciendo hacer.
- **Jerga interna barrida del sitio público**: «cerebro local» y «modo consulta» no
  significan nada para un cliente. Traducidos en precios, equipo y preguntas; comprobado
  que no queda ninguna aparición.
- Las seis páginas públicas responden 200, Ruff en verde y las pruebas de precios y de
  páginas legales siguen pasando.

### Qué no se pudo probar

- **El aspecto final**: revisado por el founder en el servidor local durante los cambios,
  pero sin captura de navegador por mi parte ni comprobación en pantalla de móvil.

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

## 2026-07-27 — reconciliación del merge: recupera el refactor perdido de la migración

- El merge `796e49e` (fusión manual de `main` con dos arreglos independientes del
  mismo bug: commit local `9691898` y el commit remoto `558d72b` de Codex) resolvió
  el conflicto en `migrations.py` quedándose enteramente con la versión local y
  descartando el refactor de Codex, sin dejar marcas de conflicto. El resultado
  funcionaba (352 pruebas verdes, incluida la regresión específica de Codex
  `test_schema_33_backfills_issued_invoice_and_restores_immutability`), pero dejaba
  un bloque duplicado inerte: un segundo `DROP`/reinstalación del disparador de
  facturas emitidas justo después del backfill de `invoice_lines`, que ya no hacía
  falta porque el primer `DROP`/reinstalación (antes del `UPDATE` de `series_id`)
  es suficiente.
- Se recupera el helper `_drop_issued_invoice_integrity` de Codex, se reutiliza en
  `_upgrade_professional_invoicing` y en `_downgrade_invoice_legal_integrity`
  (antes con la lógica duplicada inline) y se elimina el bloque muerto.
- También se detectó que el propio merge omitió tres entradas completas de Codex en
  este archivo y en `Registro-cambios.md` (las de 239ac7e, e5fd731 y 923f1fc/e78e9e4;
  la de 558d72b sí quedó, la de `Mapa-codigo.md` y `project-state.json` también
  sobrevivieron intactas). Se restauran íntegras a continuación, en su fecha y
  autoría original, para no perder la bitácora de un incidente real de Railway con
  tres caídas de despliegue en cascada y su recuperación.
- Suite completa tras la limpieza: **352 pruebas verdes / 354** (2 fallos de
  siempre: artefacto macOS `/private/var` vs `/var` en `test_backups.py`, sin
  relación). `ruff check src/noesis/migrations.py`: verde.

## 2026-07-27 — host del healthcheck de Railway (recuperación de producción)

- Los logs confirmaron que Uvicorn completaba el startup; la advertencia de Google
  solo mantenía cerrado `/admin`. La caída era posterior, durante el healthcheck.
- Railway documenta que sus healthchecks usan `Host: healthcheck.railway.app`.
  `TrustedHostMiddleware` lo rechazaba porque Noesis solo admitía el dominio público,
  el privado y localhost.
- La configuración añade ese host exacto únicamente cuando existe
  `RAILWAY_ENVIRONMENT`; no acepta comodines ni cambia los hosts de instalaciones
  ajenas a Railway.
- Nueva prueba de regresión: el host de Railway obtiene 200 en una ruta de prueba,
  `evil.example` obtiene 400 y la lista no contiene `*`. Módulo específico:
  **9 pruebas verdes**. Suite completa: **354 pruebas verdes en 223,9 s**.
- CI real verde: suite, migraciones y humo PostgreSQL. Railway activó el despliegue
  como `success`. Verificación externa final: `/health`, `/ready`, `/`, `/login`
  responden 200; `/admin` redirige correctamente a `/login` porque Google OAuth
  todavía no está configurado. **Producción recuperada.**
- **Autor/agente original de esta entrada:** Codex (restaurada tras perderse en el
  merge `796e49e`; ver entrada de reconciliación arriba).

## 2026-07-27 — admin fail-closed sin convertirlo en caída global

- Tras superar correctamente la migración real, Railway falló en el arranque. El
  botón Google ausente y el guard de startup identifican la configuración admin
  pendiente como causa más probable.
- La autorización de `/admin` ya exige una sesión cuyo `auth_provider` sea Google.
  Sin credenciales no existe forma de obtenerla, por lo que se mantiene bloqueado.
  El startup registra un error operativo, pero permite `/health`, login y paneles de
  clientes.
- Nueva prueba: simula producción con Google obligatorio y sin credenciales, inicia
  el servidor, confirma `/health` en 200, autentica al administrador por contraseña
  y verifica que `/admin` redirige a login. Total del proyecto: **353 pruebas**.
- Google OAuth real sigue siendo P0 antes de usar el centro fundador; esta corrección
  preserva seguridad y evita que su ausencia deje sin servicio a los autónomos.
- **Autor/agente original de esta entrada:** Codex (restaurada tras perderse en el
  merge `796e49e`; ver entrada de reconciliación arriba).

## 2026-07-27 — regresión de migración 32 → 33 con factura emitida

- Railway reveló un caso que el humo anterior no cubría: producción tenía una
  factura emitida sin `series_id`; la migración 33 intentaba asignárselo después de
  que la migración 32 ya hubiese instalado el trigger de inmutabilidad. PostgreSQL
  abortaba correctamente con `CheckViolation`.
- El backfill retira únicamente el trigger de cabecera, asigna la serie y lo
  reinstala inmediatamente. En PostgreSQL todo ocurre dentro de la misma transacción:
  si falla, el `DROP` también se revierte. La protección permanente no se relaja.
- Nueva regresión SQLite: parte exactamente del esquema 32, inserta una factura
  emitida, migra a 35, verifica serie y línea y confirma que modificar después el
  concepto vuelve a fallar.
- El job PostgreSQL ahora migra primero a 32, inserta una factura emitida histórica,
  ejecuta 32 → 35, verifica serie/línea y prueba el trigger restaurado antes de
  recorrer las rutas calientes. Ya no valida solo una base vacía.
- Suite completa final: **352 pruebas verdes en 235,4 s**. Ruff, Bandit,
  `pip-audit`, compilación, YAML, fuente de verdad y `git diff --check` verdes.
  La aceptación definitiva exige ambos jobs CI verdes y repetir el despliegue
  Railway; no se tocó la base real desde local ni se desactivó ningún control en
  producción.
- **Autor/agente original de esta entrada:** Codex (restaurada tras perderse en el
  merge `796e49e`; ver entrada de reconciliación arriba).

## 2026-07-27 — puerta de apertura, verdad pública y dependencias

- Suite completa: **351 pruebas verdes en 255,8 s**. Después de centralizar la
  versión legal se repitieron 9 pruebas afectadas: alta normal, alta cerrada,
  bloqueo del acceso directo de Google, páginas legales y diagnóstico de apertura.
- La apertura en producción se probó con alta desactivada: GET/POST no crean
  cuentas, Google no inicia un flujo de registro y las cuentas existentes conservan
  el acceso. El diagnóstico bloquea dominio no canónico e identidad legal ausente;
  al activar el alta, también exige copia externa, Meta, SMTP, Stripe, voz, lectura
  de imágenes y ClamAV.
- Las cuatro páginas legales renderizan en 200 sin marcadores de razón social, NIF,
  dirección ni etiquetas de borrador. La versión visible y el evento
  `legal_accepted` usan una única constante (`2026-07-27`).
- Pillow quedó en 12.3.0 y `pip-audit` no encontró vulnerabilidades conocidas; el
  paquete local `noesis` se omite porque no existe en PyPI. El extra OCR resuelve
  `pytesseract` de forma reproducible y `uv lock --check` queda verde.
- Compilación, Ruff, Bandit, `git diff --check` y ciclo limpio de migraciones
  `0 -> 35 -> 0 -> 35` verdes. El escaneo de archivos cambiados/nuevos solo devolvió
  los falsos positivos ya auditados en la baseline; se actualizó únicamente la
  línea desplazada de `readiness.py`.
- No se usó navegador por la inestabilidad conocida de la aplicación de escritorio.
  La evidencia visual y la validación real de Railway/PostgreSQL, dominio, Meta,
  Stripe, SMTP, Google, audio/OCR, ClamAV, copia externa y AEAT siguen siendo
  externas y están en [[Tareas-vivas]].
- **Autor/agente original de esta entrada:** Codex (restaurada tras perderse en el
  merge `796e49e`; ver entrada de reconciliación arriba).

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
