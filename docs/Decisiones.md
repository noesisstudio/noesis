# Decisiones

Registro de decisiones importantes y su porqué (las más recientes arriba).

## La gestoría recibe borradores explicables, no impuestos «hechos» (2026-08-07)

El espacio profesional puede sumar IVA, ordenar documentos y anticipar qué modelos
merecen revisión, pero no debe deducir por un NIF qué obligaciones tiene el cliente
ni presentar una cifra como definitiva. Cada empresa guarda un perfil fiscal
explícito, corregible y trazado por la gestoría. Cuando faltan base, cuota, régimen,
prorrata o una característica de la operación, la interfaz pide criterio en lugar
de rellenar el hueco.

Noesis tampoco fija todavía una comisión para el canal de gestorías. La cartera
puede medir clientes conectados y demostrar el ahorro operativo, pero descuento,
porcentaje, duración, devoluciones y liquidación son condiciones comerciales que
debe aprobar el founder antes de prometer dinero a un despacho o a su cliente.

## La demo son cuentas reales dentro de Noesis, no otro producto (2026-08-06)

Para enseñar Noesis no se mantendrá una segunda interfaz ni un conjunto de pantallas
inventadas. El acceso de autónomo, la cuenta profesional de gestoría y el portal del
cliente recorren el mismo código y los mismos datos relacionados que usaría un
cliente real. Así una reunión también prueba el producto y no una promesa separada.

Las empresas ficticias llevan una marca persistente y el servidor las trata como
solo lectura. Se permiten lecturas y descargas útiles, pero no altas, cambios,
aceptaciones, envíos, automatizaciones, cobros ni acciones fiscales. La contraseña
puede ser conocida porque nunca abre datos reales ni autoridad operativa.

## Los PDF escaneados se leen primero dentro de nuestra infraestructura (2026-08-06)

Un PDF sin capa de texto no debe obligar a enviar una factura o ticket a una API de
visión. PDFium rasteriza localmente y el mismo Tesseract de las fotos aplica OCR con
límites estrictos. Si no puede leerlo con suficiente evidencia, el documento pasa a
revisión; Noesis no inventa una clasificación. La extracción externa autorizada
queda como respaldo explícito, no como requisito del recorrido normal.

## El alias público llega al servidor, pero nunca sirve una segunda web (2026-08-06)

`www.bynoesis.com` debe estar permitido por el guardián de Host para que el servidor
pueda responder, pero no puede devolver otro 200: duplicaría la web para buscadores y
permitiría que una configuración accidental repartiera enlaces entre dos orígenes.
El runtime lo redirige con 308 a `NOESIS_BASE_URL`, conservando ruta y parámetros.
Railway, localhost y sus healthchecks exactos no participan en esa redirección.

## La deduplicación documental termina en la frontera del negocio (2026-08-06)

La misma foto o PDF no se guarda dos veces dentro de una empresa: el servicio calcula
SHA-256 después de validar y escanear, y la base impone unicidad por
`(business_id, content_sha256)`. La restricción decide también cuando dos canales
suben el archivo a la vez; el segundo fichero se elimina y se devuelve el documento
ya existente. Los documentos anteriores a la migración reciben huella solo cuando
reaparece un candidato del mismo tamaño.

No se hace deduplicación global. Confirmar que otra empresa ya posee una huella
crearía un canal lateral entre clientes y mezclaría sus ciclos de conservación. El
pequeño ahorro adicional de almacenamiento no compensa ese riesgo de privacidad.

## Publicado significa release y esquema verificables (2026-08-06)

El repositorio, GitHub y Railway pueden contar tres verdades distintas durante un
despliegue. Un documento llegó a marcar el candidato como publicado mientras la web
seguía sirviendo el copy anterior. Desde ahora no basta con que CI esté verde ni con
que exista un deployment: `/health` expone una huella corta y saneada del commit y
`/ready` devuelve esa huella junto a la migración aplicada. Si producción no puede
identificar el release, `noesis-doctor --strict` la bloquea. No se publica nombre de
rama, variables arbitrarias ni secretos.

## El catálogo «más IVA» obliga a activar impuestos en Checkout (2026-08-06)

Los seis precios de Stripe representan base imponible porque toda la comunicación
comercial dice 29/49/99 € más IVA. Checkout pide desde código dirección de
facturación, NIF fiscal y `automatic_tax`; no se deja esa regla escondida en una
configuración manual del proveedor. Desactivarla convierte el doctor en bloqueo.
Sigue siendo obligatorio validar en Stripe test base, IVA, total y factura antes de
usar claves live: pedir cálculo automático no garantiza por sí solo que la cuenta de
Stripe esté fiscalmente bien configurada.

## Las páginas legales dejan de ser un sitio aparte (2026-07-30)

Privacidad, términos, aviso legal, cookies, encargado del tratamiento y cumplimiento
arrastraban un armazón propio y más viejo que el resto de la web: cabecera distinta,
pie distinto, y ni descripción para buscadores ni canonical. Se quedaron atrás cuando
el sitio público se rehizo.

El problema no es estético. Esas seis páginas están en el sitemap, o sea que las
ofrecemos a Google. Quien busque «encargado del tratamiento autónomos» puede aterrizar
ahí sin haber pasado por la portada, y se encontraba una página sin menú: ningún camino
hacia precios, ni hacia el formulario, ni hacia nada. Una puerta de entrada convertida
en callejón sin salida.

Ahora extienden la misma plantilla que el resto. Ganan menú, canonical y una
descripción escrita para cada una. Se les quita la llamada final a la acción, porque un
texto legal no es sitio para vender; la excepción es `/cumplimiento`, que es
divulgativa y ahí sí encaja.

De paso se elimina una incoherencia que restaba credibilidad: había tres direcciones de
correo distintas conviviendo en la misma web —una por variable en el pie, un Gmail
escrito a mano en cookies y otra dirección a mano en contacto—. Todas pasan por la
misma variable, y el valor de respaldo deja de ser una cuenta personal para ser la del
dominio propio.


## La maqueta de la portada no puede tener dieciocho títulos principales (2026-07-30)

La portada enseña una cuenta simulada reproduciendo las pantallas reales del panel. Como
se copiaron tal cual, cada una traía su `<h1>`: diecinueve en total contando el de la
página.

Un `<h1>` declara de qué trata la página. Con diecinueve, un buscador no sabe cuál
pesa, y un lector de pantalla anuncia diecinueve títulos principales a quien navega a
ciegas. La maqueta no es la estructura del documento: es el retrato de una app dentro
de una página.

Pasan a `<h2 class="demo-title">`. La clase existe para no tocar el panel real, donde
esos `<h1>` sí son correctos, y para poder extender solo las cuatro reglas de estilo que
les afectaban sin arriesgar nada más. Se comprobó una por una cuáles eran; no hay
navegador headless en el entorno, así que la verificación es por lectura de reglas y
queda anotada como pendiente de una mirada humana.


## Las visitas se cuentan en nuestro servidor, no con Google Analytics (2026-07-30)

Hacía falta saber cuánta gente entra en la web y por dónde llega. La respuesta
inmediata era Google Analytics, o alguna de las alternativas respetuosas tipo
Plausible, pero cualquiera de las tres choca con dos cosas que ya habíamos decidido:
la CSP solo permite `script-src 'self'`, y la regla de arquitectura dice «sin CDNs en
runtime». Instalar cualquiera de ellas obligaba a abrir la CSP a un dominio ajeno y a
que la web pública dependiera de que ese dominio esté en pie.

Además tiene un coste legal. En cuanto un tercero recibe la IP de quien visita, hay
tratamiento de datos personales, y eso arrastra banner de consentimiento previo,
encargado del tratamiento y, con Google, la discusión de las transferencias a Estados
Unidos. Todo eso para responder a una pregunta muy modesta.

Así que el recuento se hace **en el propio servidor**, en el middleware que ya
atraviesa cada petición. Se guardan tres cosas: la página, el día y el dominio desde
el que se llegó. Nada más: ni IP, ni navegador, ni identificador, ni cookie, ni
script. De la procedencia se conserva solo el dominio, nunca la URL completa —una
búsqueda en Google lleva en la URL lo que la persona escribió, y eso sí sería un dato
personal—. Al no poder distinguir a nadie, no hay recorrido que reconstruir y no hay
consentimiento que pedir; la política de cookies lo explica en esos términos.

Se excluyen del recuento las mismas rutas que `robots.txt` esconde de los buscadores
—el panel de clientes, la API, los estáticos y las de sesión—: sería incoherente
decirle a Google que no las mire y contarlas nosotros, y ninguna describe interés por
la web. El recuento va envuelto en `try/except`, porque medir es información y no
funcionalidad: si la base de datos falla, la página se sirve igual.

Lo que se pierde a cambio: no hay visitantes únicos, ni sesiones, ni embudos, ni
tiempo en página. Son justamente las métricas que exigen identificar a alguien. Para
la pregunta real de esta etapa —qué páginas sirven y qué canal trae gente— sobra.


## El correo sale por API porque Railway bloquea SMTP (2026-07-27)

Ningún correo salía de producción. El registro daba `[Errno 101] Network is
unreachable` al conectar con `smtp.hostinger.com`, y se descartó que fuera la
contraseña, el remitente o el puerto: desde fuera de Railway ese servidor conecta y
acepta autenticación en el 465, y el dominio solo resuelve a IPv4, así que tampoco era
un problema de rutas IPv6.

La causa es que **Railway bloquea la salida a los puertos de SMTP**, como hacen otras
plataformas del mismo tipo para impedir que sus servidores se usen para enviar spam.
No hay arreglo posible en el código mientras se hable SMTP.

La salida es enviar por **HTTPS**, que nunca está bloqueado. Se añade Brevo como vía
preferida en el adaptador de correo, incluidos los adjuntos —las facturas viajan
codificadas en el propio cuerpo—, y el SMTP se conserva como alternativa para
instalaciones donde sí funcione. Se elige un proveedor europeo por el encaje con la
documentación de encargados del tratamiento, que maneja datos fiscales españoles.

La lección general: en una plataforma gestionada no se puede dar por hecho que la
salida a un puerto cualquiera está abierta. Los servicios que hablan por HTTPS son
más portables.


## Ningún formulario público habla con SMTP durante la petición (2026-07-27)

El formulario de solicitud enviaba sus dos correos dentro de la propia petición. Con el
servidor de correo mal configurado, el visitante se quedaba hasta treinta segundos ante
una pantalla en blanco y muchos se habrían ido pensando que la web estaba rota.

La regla queda fija: **lo que se dispara desde una página pública se encola**
(`queue_email`) y lo envía el scheduler, que además reintenta. Vale igual para la
invitación del panel, donde el enlace ya se enseña en pantalla y no hay motivo para
esperar a SMTP. Cada correo lleva clave de idempotencia para que un reintento no lo
duplique.

La causa de fondo era otra y afectaba a todo el correo del sistema: `_send_msg` abría
siempre una conexión en claro y pedía `STARTTLS`, que es el modo del puerto **587**. El
**465** exige TLS desde el primer byte, y usar el modo equivocado no da un error
inmediato — la conexión se queda esperando hasta agotar el tiempo límite. Ahora el modo
se elige según el puerto.

## Un antispam que se traga clientes es peor que el spam (2026-07-27)

El campo señuelo del formulario de solicitud se llamaba `web`. El autorrelleno del
navegador completa campos por heurística de nombre y Chrome ignora a menudo
`autocomplete="off"`, así que podía rellenarlo por su cuenta: la persona veía la
pantalla de gracias y su solicitud se descartaba en silencio.

Dos reglas que quedan para cualquier señuelo futuro. **El nombre no puede parecerse a
ningún campo real** (web, empresa, dirección, teléfono); se usa uno sin significado,
hoy `nsx_check`. Y **cada descarte se registra en el log**: un falso positivo aquí no
produce ningún error visible, así que sin rastro nadie se enteraría de que se están
perdiendo clientes.

En la misma línea, repetir el envío con el mismo correo dejó de tratarse como error.
Quien insiste suele ser una persona impaciente, no un ataque: se le agradece y se le
dice que ya la teníamos, sin duplicar la solicitud. El corte por IP se mantiene, porque
ese sí describe un envío masivo.

## Apertura pública cerrada por defecto y dominio canónico único (2026-07-27)

En producción, Noesis no acepta nuevas cuentas ni inicia altas con Google mientras
falten la identidad legal mínima del prestador o la activación explícita
`NOESIS_PUBLIC_SIGNUP_ENABLED`. Las cuentas ya creadas pueden seguir iniciando
sesión. La web ofrece solicitar acceso al piloto y no simula que audio, OCR,
WhatsApp o pagos reales están disponibles si sus adaptadores no están operativos.

El dominio canónico es `https://bynoesis.com`; OAuth, Stripe, Meta, correo y enlaces
privados deben usarlo de forma coherente. Motivo: impedir consentimientos o cobros
con textos incompletos, evitar callbacks divididos entre dominios y convertir la
apertura comercial en una decisión verificable, no en el efecto accidental de un
despliegue.

## Con el alta cerrada se va directo al formulario, y cal.com se incrusta sin su script (2026-07-27)

`/onboarding` mostraba una pantalla intermedia («estamos abriendo con pocos negocios»)
antes de dejar llegar al formulario. Un paso de más que no aportaba nada: ahora redirige
directamente a `/solicitar-acceso` conservando el plan. La protección real nunca fue esa
pantalla sino el rechazo del envío, que se mantiene: no se puede crear una cuenta con el
alta cerrada aunque se llame a la ruta a mano.

Sobre el calendario, dos intentos fallidos dejan la lección anotada. Apuntar al **perfil**
de cal.com muestra la lista de tipos de reunión y obliga a pulsar antes de ver una sola
hora. Y su vista **`/embed`** no sirve para un iframe suelto: espera que la página
anfitriona cargue el script de cal.com y complete un saludo por mensajes, así que sin él
se queda en blanco. Lo que funciona es la **URL normal de una cita concreta**, que se
pinta sola y no obliga a traer JavaScript de terceros —algo que además chocaría con la
regla de no depender de CDNs en tiempo de ejecución.

## El alta la aprueba el equipo, y la contraseña la elige siempre el titular (2026-07-27)

Durante el piloto no interesa que nadie se cree una cuenta solo: se acompaña negocio
a negocio. La captación pasa por un formulario que guarda la solicitud en
`access_requests`, y el alta la ejecuta el fundador desde `/admin`.

Al aprobar **no se fija ninguna contraseña**. Se crea la cuenta con un valor aleatorio
que nadie conocerá nunca y se genera un enlace de un solo uso —reaprovechando la
maquinaria ya probada de `password_resets`, con caducidad más larga— para que el
titular elija la suya. El enlace se envía por correo y además se muestra en pantalla,
porque el SMTP puede fallar y el cliente objetivo vive en WhatsApp. El motivo de fondo
es de responsabilidad: si el equipo nunca conoce la contraseña de un cliente, no puede
ser señalado ante un incidente con los datos de *sus* clientes, de los que Noesis es
encargada del tratamiento.

La prueba de 14 días arranca el día de la aprobación, no el del formulario, para que
nadie gaste días esperando respuesta.

Esto convive con el interruptor de registro público (`public_signup_available`): con el
registro abierto los planes llevan al alta normal; con el registro cerrado —el estado de
producción— llevan al formulario. La página `registro-cerrado.html` deja de ofrecer solo
un correo y apunta al formulario.

## Producto se fusiona con la portada y el calendario vive en Contáctanos (2026-07-27)

Mantener una página de Producto que repetía el recorrido y los momentos ya presentes en
la portada dividía la atención sin añadir nada. Se conserva lo que sí era único —el
bloque del asistente y el de cumplimiento legal— dentro de la portada, y `/producto`
redirige con 301 a `#como-funciona` para no perder enlaces ni posicionamiento.

La reserva de reunión pasa a `/contacto` con el calendario **incrustado** en vez de un
enlace que saca al visitante del sitio. Eso obliga a abrir `frame-src` para cal.com,
pero **solo en esa ruta**: el resto del sitio mantiene `frame-src 'none'`. Ampliar la
CSP globalmente por una única página habría sido desproporcionado.

## Los backfills de migración deben desactivar el disparador de inmutabilidad, no esquivarlo (2026-07-27)

Una migración que rellena retroactivamente un campo nuevo en filas ya existentes
(por ejemplo `series_id` en facturas ya emitidas) puede chocar con un disparador de
inmutabilidad instalado por una migración anterior en la misma cadena. La solución
correcta no es debilitar el disparador ni excluir esas filas del backfill: es
desactivarlo justo antes de la escritura histórica y reinstalarlo
(`_install_issued_invoice_integrity` u homólogo) inmediatamente después, dentro de
la misma función de migración. Motivo: el dato retroactivo no es una alteración de
factura por parte de un usuario, es completar metadatos que no existían cuando la
factura se emitió; pero cualquier migración futura que backfillee un campo listado
en `_IMMUTABLE_INVOICE_FIELDS` (o su equivalente en `invoice_lines`) sobre filas no
`borrador` debe repetir este mismo patrón o volverá a romper cualquier base con
facturas ya emitidas.

## WhatsApp prepara; un segundo consentimiento emite y entrega (2026-07-20)

`Factura a Marta…` y `ticket de venta…` crean siempre un borrador. La referencia
parcial a un cliente solo se reutiliza cuando hay una coincidencia única; ante dos
Martas se pregunta y no se crea un duplicado. `Ticket` sin indicar que es una venta
sigue siendo gasto para evitar invertir ingresos y costes.

Emitir o entregar desde WhatsApp requiere una orden posterior y un SÍ. Entonces el
motor valida campos legales, numera, congela, genera el PDF y prepara el canal
habitual. Email adjunta el PDF; WhatsApp usa plantilla aprobada y enlace privado.
Motivo: automatizar el recorrido completo sin convertir una interpretación de texto,
audio o IA en una decisión fiscal irreversible.

## Facturación progresiva: simple al entrar, completa cuando hace falta (2026-07-20)

Noesis no replica la densidad de un ERP. El camino habitual enseña cliente, líneas,
impuestos, forma de pago y total; las menciones legales, series y programaciones se
abren solo cuando el negocio las necesita. Por debajo, el motor sí conserva cantidad,
precio, descuento, IVA por línea, IRPF, fecha de operación, series separadas,
recurrencia idempotente, historial y PDF.

Un borrador se puede editar y duplicar. Al emitir, la cabecera y las líneas quedan
inalterables. Corregir se hace con rectificativa; anular ante la AEAT crea un registro
nuevo, encadenado e inmutable, y exige confirmación escrita del titular. Motivo:
combinar la facilidad de Noesis con la trazabilidad profesional observada en Holded,
sin copiar su arquitectura de ERP ni permitir atajos legalmente inseguros.

La rectificativa operativa usa por defecto diferencias (`I`): conserva el original,
solo permite un borrador pendiente y reserva R5 para rectificar F2. La sustitución
(`S`) queda bloqueada hasta que una asesoría valide los importes rectificados y el
registro AEAT completo. Noesis no ofrece una opción fiscal que todavía no puede
explicar ni exportar correctamente.

## La obligación fiscal sobrevive al estado de la suscripción (2026-07-20)

Una cuenta caducada queda en modo consulta para impedir nuevas operaciones, pero
Noesis continúa remitiendo a la AEAT los registros Veri*Factu que ya se generaron
legalmente. Un impago del SaaS no puede convertir una outbox fiscal pendiente en
incumplimiento. La factura emitida queda congelada en BD; cobros, recordatorios y
respuesta AEAT viven en ledgers y eventos separados. Cualquier anomalía de huella
bloquea el envío externo y queda auditada.

## Facturación nativa; no conectar Holded ni otro SaaS de facturación (2026-07-20)

El founder confirma que Noesis debe controlar internamente numeración, emisión, PDF,
registro Veri*Factu, trazabilidad y remisión AEAT. Holded y Quipu son únicamente
referencias de mercado; no son proveedores técnicos ni caminos de respaldo.

Se elimina la activación por `HOLDED_API_KEY` y el proveedor externo del código. La
frontera `invoicing.py` permanece para separar responsabilidades, pero devuelve
siempre el motor nativo. Motivo: control del producto, privacidad, coste, aislamiento
multiempresa y ausencia de dependencia estratégica en otro SaaS. Esta decisión
**sustituye** la antigua «No reconstruir Verifactu» de este mismo documento.

## Oferta anual explicable y sector escrito por el cliente (2026-07-17)

El alta anual compara el coste real de doce mensualidades con el pago anual, muestra
el equivalente mensual y cuantifica el ahorro. El rojo se usa como acento comercial
apagado, no como alarma. El sector es texto libre y se conserva entre pasos: Noesis
no obliga a un oficio a encajar en una lista incompleta y la segmentación interna se
construye después sobre respuestas reales.

## Configurar antes de operar o cobrar; prueba y contratación son explícitas (2026-07-17)

El alta ofrece dos compromisos distintos: probar 14 días sin tarjeta o contratar un
plan mensual/anual. Ambos preparan primero el negocio; la prueba termina en el panel
y la contratación termina en una revisión del plan y checkout. No se mezcla una
prueba con una compra implícita ni se pide pagar antes de entender qué se configura.

La puesta en marcha recoge negocio, nivel de explicación, IA, fiscalidad, factura,
vencimiento, cobro, recordatorios, informes, gestoría y WhatsApp. Cada elección se
persiste en su fuente operativa y se puede cambiar después desde Ajustes. Motivo:
entregar una cuenta funcional desde el primer día, no un cuestionario de marketing.
Google sigue la misma selección comercial, pero el botón continúa oculto hasta que
existan credenciales reales; mostrar una acción que no funciona rompería confianza.

## Funciones delante, proveedores detrás; conectores locales primero (2026-07-17)

El cliente no ve un catálogo de APIs preparadas, caídas o aún sin contratar. Ajustes
muestra únicamente controles con sentido para su trabajo —WhatsApp, gestoría,
preferencia de ayuda avanzada y datos propios—. El diagnóstico de Google, Meta,
SMTP, Stripe, IA, AEAT y copias queda reservado a administración. Motivo: la salud
de infraestructura es una responsabilidad de Noesis, no ruido para el autónomo.

Para reducir coste y dependencia se construyen primero dos conectores internos: un
calendario ICS privado y revocable, y conciliación por extracto CSV. La conciliación
solo propone por importe, referencia y cliente; una coincidencia ambigua no se
selecciona y el cobro existe únicamente después de la confirmación del titular. No
se autoriza movimiento de dinero ni se presenta el CSV como conexión bancaria viva.

Todo correo confirmado entra antes en una outbox durable. El scheduler lo reclama,
reintenta con backoff y registra el fallo para administración; la confirmación del
usuario ya no depende de que SMTP responda en ese instante. Google OAuth se mantiene
oculto hasta configurar ambas credenciales: así el acceso será real desde el primer
día que se muestre y nunca un botón decorativo.

## Acceso con Google opcional y vista pública sin pantallas inventadas (2026-07-16)

La portada toma de Holded únicamente la jerarquía de campaña —promesa centrada,
explicación breve, alta y el producto debajo—, nunca sus textos, marca, clientes,
cifras ni la sensación de ERP. La muestra pública enseña solo el **Inicio** con los
mismos componentes y armazón del panel real; no permite recorrer resúmenes ficticios
como si fueran funcionalidades terminadas. Cada apartado futuro de la muestra deberá
salir de la pantalla real correspondiente, no de una maqueta paralela.

Google OAuth queda implementado como opción de acceso y alta: state de un solo uso,
perfil OIDC con email verificado, límites por IP y alta que aún exige aceptar los
términos y completar negocio/sector. No se activa ni se muestra sin cliente y secreto
configurados; el fundador debe crear el cliente web, registrar la URL de retorno y
probarlo en producción antes del piloto. Motivo: reducir fricción sin introducir un
atajo de identidad, consentimiento o privacidad.

## Precio adoptado, prueba completa y después modo consulta (2026-07-15)

El fundador adopta **29/49/99 € al mes + IVA**. La prueba de 14 días permite usar el
producto completo; al caducar, cancelar o quedar el pago pendiente, la cuenta conserva
acceso de lectura a su información pero no puede crear, modificar, enviar ni ejecutar
automatizaciones hasta activar una suscripción. El límite se valida en servidor para
web/API, portales, WhatsApp, colas y tareas programadas: ocultar botones no es control.

La estructura de cada pantalla se diseña según su decisión principal, sin imponer una
plantilla de KPIs. La coherencia transversal la aporta Noesis: lectura contextual,
motivo, siguiente paso y conversación persistente. Abrir el acompañante muestra
primero una lectura local y no consume IA por sí solo.

## Compositor interno antes del modelo; precio se decide con piloto (2026-07-15)

Noesis redacta internamente las comunicaciones repetibles a partir de hechos
confirmados: cobros, presupuestos, citas, gestoría y correos sencillos. Esta capa no
es un LLM, no inventa importes o destinatarios y no consume créditos. Si el titular
pide enviar desde WhatsApp, primero ve el borrador y confirma con SÍ/NO; web solo
prepara. El envío vuelve a validar entidad, cliente y `business_id`.

Qwen3 8B queda preparado como servicio privado evaluable, no como única dependencia
del piloto. Se mantiene pago por uso y Haiku como respaldo hasta demostrar calidad,
latencia y seguridad. Motivo: una GPU 24/7 cuesta más que la inferencia del volumen
previsto y un servidor gratuito no ofrece SLA ni estabilidad de precios.

El análisis recomendó 29/49/99 € + IVA si Premium conserva 100 minutos de voz. El
founder lo adoptó el 2026-07-15; detalle y supuestos en
[[Unit-economics-y-cerebro-interno]].

## Pago por uso antes de GPU propia durante el piloto (2026-07-14)

Noesis admite un proveedor externo OpenAI-compatible entre la IA privada y
Anthropic. Este nivel permite evaluar modelos abiertos en Groq, Cloudflare, Hugging
Face u otro servicio sin acoplar el producto a un SDK. Sigue siendo externo: requiere
consentimiento, consume un crédito del plan y no se presenta como privado ni gratis.

Durante el piloto se prioriza pago por uso con Haiku como fallback de fiabilidad.
Una GPU propia 24/7 no se contrata hasta que el volumen, la privacidad o la calidad
medida lo justifiquen. Motivo: a bajo volumen el coste de inferencia es inferior al
coste fijo y operativo de mantener GPU; el tramo gratuito de terceros no ofrece un
SLA comercial. Cada proveedor registra modelo, tokens, latencia y coste estimado,
con tarifas configurables. Cálculo en [[Analisis-coste-IA.ipynb]] y operación en
[[Piloto-operativo]].

## IA útil desde el primer día, con control y coste acotado (2026-07-14)

El fundador decide que la experiencia recomendada de una cuenta nueva incluya IA
avanzada desde el onboarding. La elección es explícita y reversible: «Experiencia
completa» aparece recomendada, mientras «Solo cerebro local» evita enviar contenido
a un proveedor externo. Ninguna cuenta envía datos fuera antes de esa decisión.

El orden técnico es siempre reglas deterministas, servicio de IA privado compatible
con OpenAI y, solo si hace falta y el negocio lo ha autorizado, proveedor externo.
La IA privada no consume créditos externos. La externa tiene un límite mensual por
plan reservado de forma atómica por mensaje. Agotar el límite nunca apaga agenda,
facturas, cálculos, documentos ni acompañamiento local.

El modelo propone lenguaje y herramientas, pero el servidor valida la herramienta,
los argumentos, el `business_id` y los permisos. Pagos, transferencias, impuestos,
emisión definitiva, envíos sensibles y borrados irreversibles siguen requiriendo
confirmación específica del autónomo. Detalle operativo en [[IA-local]].

## Cierre controlado y aprendizaje explicable (2026-07-13)

- El parte de campo es operativo y separado del fichaje laboral append-only.
- Terminar prepara solo un borrador; emitir y enviar requieren al autónomo.
- La conformidad guarda fuente, momento y huella, sin prometer validez jurídica
  absoluta.
- Preferencias confirmadas prevalecen sobre patrones observados y son corregibles.

## Las integraciones se eligen por negocio; lo local nunca se apaga (2026-07-13)

Noesis separa capacidad interna de servicio externo. El alta crea la preferencia
externa desactivada hasta que el usuario elige durante el onboarding; la opción
recomendada es activarla con límites. Una cuenta anterior sin preferencia conserva
el comportamiento previo para no romper su operativa. Al desactivarla, el cerebro
de reglas, OCR, clasificación heurística y cualquier servicio privado configurado
continúan dentro de la infraestructura. No se guardan claves de proveedor en
`integration_settings`.

WhatsApp, gestoría y Veri*Factu conservan sus tablas y flujos como fuente de verdad:
el centro los resume y enlaza, no los duplica. La salud se calcula siempre con
`business_id` y traduce colas, errores, latencia y revisiones a lenguaje humano.
Al desconectar WhatsApp se desvincula el teléfono, se limpian confirmaciones
pendientes y los mensajes aún no enviados quedan cancelados con trazabilidad.
Las transferencias y movimientos bancarios siguen fuera del permiso automático;
marcar interés en la futura conexión bancaria no autoriza ninguna operación.

## Autonomía acotada y columna operativa única (2026-07-13)

Noesis hace automáticamente trabajo interno de bajo riesgo y comunicaciones que
siguen una regla concreta aprobada. Preparar no equivale a autorizar: transferencias,
pagos, devoluciones, presentación fiscal, emisión definitiva y borrado irreversible
siempre exigen confirmación específica del autónomo. El límite se valida en servidor
y cada propuesta o ejecución sensible deja registro.

Proyecto, trabajo, trabajador, fichaje, coste, gasto, documento y tarea forman una
sola columna operativa. Las horas reales se calculan desde fichajes inmutables y el
coste laboral desde la tarifa horaria configurada; no se duplican horas manuales con
horas de fichaje. Motivo: el margen debe surgir del trabajo cotidiano, no de pedir al
autónomo que replique información en varias pantallas.

La cadencia de gestoría es una regla explícita y revocable. Cada paquete tiene
carpetas estables, originales, manifiesto, huella, versión y trazabilidad de aviso y
descarga. Cambiar solo el nombre o email de la gestoría no amplía un permiso que el
usuario haya restringido después.

## Noesis recuerda solo lo explicable y la entrada es universal (2026-07-12)
El acompañante conserva la conversación entre pantallas y canales, pero separa el
historial de los recuerdos operativos. Un recuerdo permanente debe ser explícito,
visible, borrable y confirmado; las señales de clientes se calculan con hechos
trazables (vencimientos, cobros, presupuestos y trabajos), no con una nota opaca.

Todo archivo entra por el mismo servicio de documentos. Noesis propone si es
ticket, factura recibida o emitida, presupuesto, contrato, albarán, proveedor u
otro documento, registra confianza y motivo, y pide revisión humana cuando puede
tener efecto contable. Motivo: acompañar no significa decidir en silencio, y web y
WhatsApp no deben desarrollar cerebros distintos.

Las facturas emitidas antiguas se guardan como documento pendiente de revisión.
Nunca se reemiten ni entran en la cadena Veri*Factu. La importación histórica con
`source='importada'` se habilitará únicamente con un flujo específico y auditado.

## Noesis da el parte; el detalle se abre por capas (2026-07-11)
La Home prioriza situación, siguiente acción y trabajo de Noesis. No se eliminan
datos: se desplazan a Dinero, Cobros, Proyectos y el resto de apartados. Proyectos
aplica la misma regla: tres cifras agregadas y listado primero; margen, horas,
materiales y equipo solo al abrir un proyecto. El estilo de explicación es una
preferencia de cuenta en Ajustes, no un control repetido en cada vista.

Motivo: un autónomo sin formación financiera debe entender la app de inmediato,
mientras que quien domina sus números conserva profundidad y trazabilidad.

## Piloto primero, plataforma por capas (2026-07-07)
La visión completa ("sistema operativo empresarial": documentos inteligentes,
gestoría interactiva, productos, proyectos, CRM, finanzas avanzadas) se construye
**por capas sobre la app actual**, mientras el piloto WhatsApp avanza en paralelo.
Motivo: el producto está a días del piloto; el feedback de 3-5 autónomos reales
vale más que módulos nuevos sin usuarios. Autorizado por el founder. Plan de fases
en [[Roadmap]]; criterio en [[Metodo-operativo-Fable]].

## FacturAI: referencia, no fusión (2026-07-07)
El proyecto anterior "Automatizacion Facturas" (FacturAI) resuelve un subconjunto
de Noesis con un stack incompatible (SQLAlchemy, JWT, WeasyPrint, Supabase).
Decisión: **no copiar código ni fusionar stacks**; portar ideas concretas al
estilo propio: el prompt de extracción de facturas completo (líneas, NIFs,
confianza), la detección emitida/recibida por NIF (`_detect_empresa_context`), el
patrón de historial de estados de factura y los campos mínimos de producto.
La carpeta queda fuera de git (`.gitignore`) como material de consulta.

## El vault de documentación es `docs/` (2026-07-07)
No se crea la estructura paralela `obsidian/00-…09-…`: `docs/` ya es el vault de
Obsidian, los agentes lo conocen y duplicar estructura = documentación
desincronizada. Los documentos nuevos (método operativo, handoffs, preguntas
abiertas) viven en `docs/` y se enlazan desde [[Inicio]].

## Método operativo transferible entre modelos (2026-07-07)
El criterio de trabajo queda documentado en [[Metodo-operativo-Fable]] y todo
traspaso entre modelos usa `AI_HANDOFF_TEMPLATE.md`. Motivo: que el proyecto no
dependa de qué modelo lo trabaja (Fable diseña, Opus revisa estrategia, Codex
ejecuta) sin reinterpretar el producto desde cero.

## Posicionamiento: suite completa, construida modular
El founder eligió "suite completa desde el inicio" frente a empezar solo por el
copiloto proactivo. Se construye modular para que no se vuelva inmanejable.
Diferenciador real: orquestación + agenda, donde [[Competencia|Forjia]] es débil.

## No copiar código de competidores
El código de Holded/Forjia es propietario: copiarlo sería ilegal y una trampa. Se
copian **ideas/UX** y se usa open-source. Ver [[Competencia]].

## Arquitectura híbrida de IA (coste/privacidad)
Cerebro local por reglas para lo rutinario, modelo privado cuando esté configurado
y proveedor externo autorizado para lo complejo. La decisión de alojar un modelo
se toma por coste total, privacidad, latencia y calidad, no por una cifra universal
de tokens. Ver [[IA-local]], [[Investigación]] y [[Arquitectura]].

## Mínimas dependencias externas
Hash de contraseñas con stdlib (PBKDF2), Chart.js servido en local, sin Tailwind.
Motivo: coste, privacidad y control. Ver [[Arquitectura]].

## Operaciones de seguridad verificables, no un “agente” opaco (2026-07-21)

El responsable CISO interno es determinista, de solo lectura y trabaja únicamente
con metadatos técnicos. No recibe facturas, mensajes ni documentos y no ejecuta
correcciones. Sus evidencias viven en una bitácora append-only con cadena de hashes;
los accesos admin y descargas de copias incluyen `request_id`. Motivo: dirección
necesita saber qué pasa sin dar a una IA permisos de seguridad ni crear una falsa
sensación de certificación.

Producción exige Google OAuth para el administrador aunque falten credenciales: en
ese caso `/admin` falla cerrado, pero no se interrumpe el servicio de todos los
clientes. El diagnóstico interno y `noesis-doctor --strict` siguen marcándolo como
bloqueo hasta configurarlo. Los documentos pueden usar ClamAV
privado por streaming y fallo cerrado. Cada backup se restaura al crearlo y un
simulacro semanal independiente vuelve a verificar el último juego. Pentest, MFA de
la cuenta Google, restauración desde otro proveedor, RGPD y red siguen siendo
responsabilidades externas verificables.

## Seguridad por capas y sin dependencia obligatoria de Redis (2026-07-21)

Los límites de autenticación se comparten mediante la misma base de datos y guardan
solo una huella HMAC de IP/cuenta. PostgreSQL usa un pool acotado; los archivos se
validan por contenido; los logs no incluyen query strings; la administración exige
Google OAuth en producción. Motivo: cerrar ataques reales sin
añadir para el MVP otro servicio crítico, costes o datos personales innecesarios.

La CSP estricta se despliega inicialmente en report-only porque la UI conserva
scripts/estilos inline. RLS, KMS/cifrado selectivo y MFA/passkeys para terceros son
capas candidatas, no sustitutos de `business_id`, transacciones, validación y
confirmación actuales. Ver [[Seguridad-operativa]].

## Decisión superada — no reconstruir Verifactu

La idea inicial era integrar un proveedor homologado. Queda anulada por la decisión
de 2026-07-20: la facturación y Veri*Factu son desarrollo propio de Noesis.

## Marca
Paleta del logo: verde bosque #14463b + teal #2e8b74 + crema #f4f1e8. Dominio
previsto: bynoesis.com. Ver [[Producto]].
