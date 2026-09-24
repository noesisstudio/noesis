# Tareas vivas

## Correcciones habladas — 24-sep

- [x] «No, eran 120», «con IVA incluido», «es para Pedro», «el concepto es X» y
  las variantes del importe corrigen la propuesta sin repetir la orden.
- [x] Una corrección solo cambia lo que se nombra (#12 de la lista del founder).
- [ ] Founder: **volver a poner `NOESIS_ASSISTANT_REVIEW_ENABLED=true`** si aún
  está en `false` del vídeo.
- [ ] Siguiente de la lista del founder por valor: **#3 y #4** (no interceptar con
  una coincidencia parcial), que es la causa raíz de la mayoría de lo corregido
  hoy, y **#13** (una pregunta en medio no debería descartar la propuesta viva).


## Vídeo: audio directo a PDF — 24-sep

- [x] Una nota de voz que solo prepara (borrador, gasto, presupuesto) ya no pide
  confirmación. Lo irreversible sigue pidiéndola.
- [ ] Founder, **para grabar**: `NOESIS_ASSISTANT_REVIEW_ENABLED=false` en Railway.
- [ ] Founder, **al terminar de grabar**: volver a `true`. Mientras esté en
  `false`, cualquier orden que mueva dinero se ejecuta sin preguntar.
- [ ] Founder, **antes de la toma buena**: comprobar en Clientes que solo hay una
  ficha «Reformas Martinez», y hacer una toma de prueba para ver que el PDF llega
  de verdad por WhatsApp. Esa parte no se ha podido probar contra Meta.


## Nombre cortado por el dictado — 24-sep

- [x] «Reforma» encuentra a «Reformas Martinez»: se compara también contra los
  principios de palabra, no solo contra el nombre entero.
- [x] Con una ficha parecida delante, «sí» usa **esa ficha**. Crear un duplicado
  exige decir «crea el cliente X».
- [ ] Founder: ya lo dijiste ayer y sigue pendiente. **Junta a mano los clientes
  duplicados que ya tengas** (por ejemplo «reforma» y «Reformas Martinez»): esto
  evita los nuevos, no arregla los viejos.


## Proyectos y documentos — 23-sep

- [x] El nombre del proyecto ya no se queda con la preposición delante, y el
  importe no necesita «de» ni «por» para entenderse.
- [x] Preguntar por los documentos funciona en los dos idiomas.
- [ ] Founder: mira en Proyectos si hay alguno llamado «de …» o «para …» de antes.
- [ ] Sin corpus todavía: el circuito real de documentos (foto o PDF entrantes),
  que necesita credenciales de extracción para probarse de verdad.


## Catalán — 23-sep

- [x] Las ocho consultas del barrido funcionan en catalán, y las castellanas
  siguen funcionando (probado en la misma prueba).
- [x] «Demà», «avui» y los siete días de la semana en catalán son fechas válidas.
- [ ] Founder: si algún cliente tuyo habla catalán, prueba «quant em deuen» y
  «agenda a X demà a les 10». Antes no hacían nada.
- [ ] Sin barrer todavía: proyectos (el nombre se queda con la preposición
  delante: «abre un proyecto de reforma» guarda «de reforma») y documentos.


## Tickets y consultas — 23-sep

- [x] Un ticket de 40 € ya no se guarda como 0,00 € con concepto «4».
- [x] Nombrar una factura por su número nunca ofrece crear otra.
- [ ] Founder: **revisa en Facturas si hay tickets a 0,00 €** de haber dicho
  «hazme un ticket de X euros». Esto evita los nuevos; los que ya estén, no.
- [ ] Zonas todavía sin barrer: documentos (fotos y PDF) y proyectos.


## Audio dictado — 23-sep

- [x] Importes en letra («trescientos euros», con céntimos y en catalán).
- [x] Horas en letra, «y media», «menos cuarto» y «de la tarde». Y «mañana» el día
  ya no se confunde con «por la mañana» la hora, que agendaba a las 9:00 callado.
- [ ] Founder: **`GROQ_API_KEY` en Railway**. Sigue siendo lo primero: sin ella no
  se transcribe ninguna nota de voz y nada de esto llega a usarse.
- [ ] Founder: revisa en la agenda si hay citas viejas a las 9:00 que dictaste a
  otra hora. Esto evita las nuevas; las que ya están, no las corrige.


## Barrido de órdenes — 23-sep

- [x] Gastos 9/9, agenda 5/6, cobros 6/6, presupuestos 3/3.
- [x] Decir que una factura está cobrada ya no ofrece crear otra.
- [ ] Founder: si en tu base hay facturas duplicadas de haber dicho «está
  cobrada» y que te ofreciera crear una nueva, bórralas desde Facturas.
- [ ] Zonas todavía sin barrer con corpus: tickets F2, documentos y proyectos.
  El método es el de `tests/test_ordenes_del_dia.py`: medir primero, luego tocar.


## Erratas y notas de voz — 23-sep

- [x] Una errata o un acento reutilizan la ficha del cliente en vez de crear otra.
  Con dos fichas parecidas se pregunta.
- [x] Las notas de voz dicen cuál de los cuatro fallos ha sido, y queda anotado.
- [ ] Founder: en Railway, comprobar si existe **`GROQ_API_KEY`**. Empieza por G y
  queda justo encima de lo que se ve en la captura de variables. **Sin ella
  ninguna nota de voz se transcribe**, y eso explicaría que no funcione nunca en
  vez de «por una mínima cosa».
- [ ] Founder: si ya tienes clientes duplicados de antes (el mismo con dos fichas),
  esto evita los nuevos pero no junta los viejos. Hay que fusionarlos a mano desde
  Clientes.


## Entender la orden como se hable — 23-sep

- [x] 15 formas naturales de pedir la misma factura: las 15 salen. Antes fallaban 9.
- [x] «Concepto» manda esté donde esté en la frase; sin él, «Servicio».
- [x] «Si, genera el pdf» confirma; «sí, pero 500 euros» no.
- [x] Ajustes muestra el modelo de IA configurado.
- [ ] Founder: en Railway → Variables, mirar `NOESIS_MODEL`,
  `NOESIS_FALLBACK_MODEL` y `NOESIS_EXTRACTION_MODEL`. Si existen y no ponen
  `claude-sonnet-5`, mandan ellas sobre el código. Tras desplegar se ve en Ajustes.
- [ ] Cuando una frase real vuelva a fallar, añadirla al corpus de
  `tests/test_nombre_dictado.py` con lo que se esperaba. Ese archivo es el que
  impide que el mismo fallo vuelva.


## PDF de la factura por WhatsApp — 23-sep

- [x] El PDF del borrador se adjunta al crear la factura, sin pedirlo, también
  cuando nace de un «sí» con la revisión encendida.
- [ ] Founder, **al desplegar**: pedir una factura por WhatsApp y comprobar que
  llega el PDF. Es lo único que lo prueba: aquí no hay credenciales de Meta.
- [ ] Si el PDF no llega pero sí el texto, el fallo está en la subida a Meta: el
  mensaje lo dirá y dará el enlace con sesión. Mirar el log por
  «No se pudo adjuntar borrador».


## Vista previa del enlace — 23-sep

- [x] Tarjeta propia de 1200x630 con la marca y el reclamo. Fuera la captura del
  panel, que enseñaba el nombre de una cuenta y el de un cliente.
- [ ] Founder, **en cuanto esté desplegado**: pedir a Meta que relea el enlace en
  https://developers.facebook.com/tools/debug/ («Scrape Again»). Facebook y
  WhatsApp cachean la vista previa y hasta entonces seguirá la imagen vieja.
- [ ] Founder: comprobarlo también pegando el enlace en un chat de WhatsApp y en
  LinkedIn, que cachean por su cuenta.
- [ ] Si alguna vez se quiere enseñar el producto en la tarjeta, que sea una
  pantalla dibujada a propósito, nunca una captura de una cuenta real.


## Nombre dictado por voz — 23-sep

- [x] El punto que separa frases corta el nombre del cliente; el de «S.L.» y el de
  una inicial, no. Lo que va detrás pasa a ser el concepto.
- [x] Un cliente sin ficha se ofrece crear y se sigue con la orden; el «sí» ya no
  se lo come la revisión.
- [ ] Founder: probarlo dictando de verdad por WhatsApp. La transcripción la hace
  Meta y aquí solo se puede simular el texto que llega.
- [ ] Founder: si en producción quedó alguna ficha con un nombre raro del tipo
  «Reformas Martínez. Concierto Ventanas», bórrala desde Clientes. El arreglo evita
  las nuevas, no limpia las viejas.
- [ ] Cuando una frase dictada vuelva a fallar, añadirla a
  `tests/test_nombre_dictado.py` con lo que se esperaba.


## Altas de clientes y proveedores — 23-sep

- [x] Siete fallos reales de la zona de altas, reproducidos y corregidos con
  prueba: alta sin nombre, teléfono dentro del nombre, nombre que es un número,
  proveedor duplicado por mayúsculas, nombres sin límite en clientes, error que no
  decía qué pasaba, y el 500 de la web.
- [x] Un alta que falla deja la pendiente puesta: la siguiente frase con un nombre
  la termina.
- [ ] Founder: probar en el navegador las páginas de Clientes y Proveedores. Lo
  probado automáticamente es la respuesta de la API, no la pantalla.
- [ ] Founder: si alguna vez importaste clientes con nombres larguísimos, ahora la
  importación los rechazará en vez de meterlos. Las fichas ya guardadas no se tocan.
- [ ] Cuando una frase de alta falle en producción, añadirla a
  `tests/test_alta_de_ficha.py` con lo que se esperaba.


## Factura a medias — 23-sep

- [x] El borrador guarda lo entendido y declara lo que falta; se completa por chat,
  por el formulario o al dar de alta el cliente. Emitir bloqueado mientras falte algo.
- [x] Cinco fallos propios corregidos con prueba: preguntas que creaban borradores,
  el cliente adivinado, el aviso «sin ficha» que no salía nunca, el nombre apuntado
  que sobrevivía al asignar ficha, y el archivo de pruebas que dejaba `config`
  parcheado y tumbaba 14 pruebas ajenas al correr la suite entera.
- [ ] Founder: probarlo a ojo en el navegador. El listado está cubierto por pruebas
  de datos, no visuales: mira que «A medias» se vea bien y que no salga Emitir.
- [ ] Al desplegar: la migración 58 se aplica sola; confirmar en `/ready` que el
  esquema llega a 58.
- [ ] Cuando una frase real falle en producción, añadirla a
  `tests/test_orden_a_medias.py` con lo que se esperaba. Ese archivo es el corpus.


## Sonnet 5 en todo — 22-sep

- [x] Valores por defecto a `claude-sonnet-5` (agente, respaldo y lectura de
  documentos), tarifas a 2/10 USD y razonamiento apagado por defecto.
- [ ] Founder, **antes de dar esto por hecho**: en Railway → Variables, mirar si
  existen `NOESIS_MODEL`, `NOESIS_FALLBACK_MODEL`, `NOESIS_EXTRACTION_MODEL` o las
  tarifas `NOESIS_*_USD_PER_MTOK`. Si existen, **mandan sobre el código**: bórralas o
  ponlas a `claude-sonnet-5` y 2/10.
- [ ] Tras desplegar: mandar una frase que el cerebro local no entienda y leer un
  ticket con foto. Si Ajustes muestra un error del proveedor, un 404 es el nombre
  del modelo y un 400 un parámetro.
- [ ] En `/admin/economia`, subir el supuesto de coste por interacción de IA avanzada
  de 0,014 a 0,028 USD para que el modelo refleje la tarifa de Sonnet 5.

## Gestorías como puerta — 21-sep

- [x] Guiones de correo para gestorías y gremios en el CRM, en las dos lenguas,
  sin enlaces ni adjuntos y pidiendo información en vez de vendiendo.
- [ ] Founder: dar de alta con origen `Gestoría` las tres del CSV de Lleida (ASLAF,
  Sala Assessories, Filaco) y buscar diez más. Ninguna tiene teléfono en la ficha:
  habrá que sacarlo de su web.
- [ ] Founder: cinco correos al día como mucho, cada uno escrito para ese despacho.
  La respuesta que buscas es un nombre de cliente, no una reunión comercial.
- [ ] **No prometer comisiones todavía.** No hay S.L., ni Stripe, ni decisión
  tomada sobre el porcentaje. Eso es etapa 2.

## Correo y entregabilidad — 21-sep

- [x] Diagnóstico contra el DNS real: SPF, DKIM y DMARC de `bynoesis.com` están
  bien. El spam no viene de la autenticación.
- [x] `scripts/check_email_dns.py` para volver a comprobarlo tras cada cambio.
- [ ] Founder: **terminar la autenticación de Brevo**. Falta la clave DKIM y el
  `include:spf.brevo.com` en el SPF que ya existe (nunca en un registro nuevo).
  Hoy no molesta; romperá el correo de la aplicación en cuanto se active.
- [ ] Founder: crear `dmarc@bynoesis.com` y añadirlo al `rua` del DMARC. Ahora los
  informes los recibe Brevo y no tú, así que no ves nada.
- [ ] Founder: crear una dirección con tu nombre (`xavier@bynoesis.com`) y escribir
  desde ahí, no desde `info@`.
- [ ] Founder: mandar un correo de prueba a una cuenta de Gmail y comprobar en
  «Mostrar original» que DKIM dice `bynoesis.com`. Es la única prueba que vale.
- [ ] Founder: cuatro semanas de calentamiento con volumen bajo antes de escribir a
  desconocidos. El dominio se registró el 4-jun-2026 y no tiene historial.
- [ ] Dentro de 2–3 semanas, con los informes DMARC limpios: pasar a
  `p=quarantine`. Antes de tener el DKIM de Brevo puesto, no.

## Captación de clientes — 21-sep

- [x] CRM de la empresa en `/admin/crm` (migración 57): embudo de nueve estados,
  importador que traga la lista pegada o una tabla con cabecera, guiones por
  estado en castellano y catalán, historial de contactos, bajas y CSV.
- [x] `docs/06-negocio-y-finanzas/Lista-de-captacion.md`: de dónde salen los 40
  nombres en Lleida y el Segrià, el ritmo diario y qué se puede hacer y qué no.
- [ ] Founder, **hoy**: pegar `outputs/prospeccion/lleida-ciudad-osm.csv` en el CRM
  y **reclasificar las 35 fichas de almacenes y ferreterías** con origen `Almacén`.
  No son clientes: son quien te presenta a diez oficios en una mañana.
- [ ] Founder, **hoy**: media hora buscando `presupuesto`, `pressupost`, `factura` y
  `albarán` en tu WhatsApp y tu correo. De ahí salen los diez nombres que más
  convierten, y no están en ningún CSV.
- [ ] Founder: cinco llamadas entre las 7:30 y las 8:30, con el guion de la ficha.
  Entre las 9:00 y las 13:00 está dentro de una pared y dice que no por no poder
  hablar.
- [ ] Founder: revisar `/admin/crm` en un navegador. Está probado con pruebas
  automáticas, no a ojo, y la base de desarrollo está vacía.
- [ ] Founder: confirmar los datos de contacto de El Gremi (instaladores de Lleida),
  AGRISEC/COELL y el Gremi de Constructors antes de llamar. Están anotados de una
  búsqueda, no verificados por teléfono.
- [ ] Founder: la pregunta al abogado sobre llamada en frío B2B (art. 19 LOPDGDD
  frente a art. 21 LSSI) está escrita en `Preguntas-abogado-TIC.md`. Mientras no
  haya respuesta, el primer contacto es **llamada o presencial, nunca WhatsApp**.
- [ ] Al desplegar: la migración 57 se aplica sola, pero conviene mirar `/ready`
  después para confirmar que el esquema llega a 57 en producción.
- [ ] Tras los primeros cinco pilotos: mirar qué origen los trajo. Es lo único que
  dirá si la prospección de mapas sirve para algo o si todo viene de presentaciones.

## Revisión 21-sep — Antes de publicar

- [x] Diff revisado y CI 35578171354 verde antes de publicar; main en Railway.
- [x] Humos PostgreSQL sobre esquema 56 en base efímera de CI: correctos,
  incluida compatibilidad con código anterior y rollback.
- [ ] Histórico verificado de suscripciones/precio/periodicidad para MRR real;
  no reconstruirlo con el plan actual y catálogo mensual.
- [ ] Regenerar el libro de analysis si va a distribuirse: fuente y HTML corregidos,
  pero el .xlsx anterior no es la fuente del panel y no se ha regenerado.
- [ ] Revisión jurídica del contrato, decisiones abiertas y costes/retirada/caja
  reales. No convertir los valores del escenario en hechos.

## Costes editables — 18-sep

- [x] Los 47 supuestos del modelo se editan y se guardan desde `/admin/economia`,
  con auditoría de qué se cambió y cuándo, y restauración a valores de fábrica.
- [ ] Founder: **escribir las facturas reales** en el grupo «Lo que sale de tu
  bolsillo cada mes». Mientras estén los valores por defecto (plataforma 7 €,
  herramientas 40 €, gestoría 60 €, seguro 30 €, cuota 300 €), los tres equilibrios
  siguen siendo un escenario y no una cifra de tu negocio.
- [ ] Founder: confirmar la caja inicial, que ahora también se edita ahí.
- [ ] Founder: revisar el formulario en un navegador. Se ha probado con pruebas
  automáticas, no a ojo, y la base de desarrollo está vacía.
- [ ] Al desplegar: la migración 56 se aplica sola, pero conviene mirar `/ready`
  después para confirmar que el esquema llega a 56 en producción.

## Economía en el panel — 18-sep

- [x] Modelo en el producto (`economics.py`), página `/admin/economia` con palancas,
  y Word y Excel de dos páginas generados con los datos de hoy, sin dependencias
  nuevas.
- [ ] Founder: **abrir el Word y el Excel descargados con Office real** y confirmar
  que no piden reparación. Están escritos a mano con `zipfile`; las pruebas los abren
  con `python-docx` y `openpyxl`, pero eso no es Office.
- [ ] Founder: revisar la página en un navegador. La base de desarrollo está vacía,
  así que las tablas de evolución se han visto sin datos.
- [ ] Founder: cargar en el libro de costes las facturas reales (plataforma,
  herramientas, gestoría, seguro). Hasta que haya al menos un mes cargado, la
  columna «real» de la página sigue vacía y todo es escenario.
- [ ] Decidir si los cuatro libros de `analysis/` se archivan. Hoy se conservan
  donde estaban, pero ya no son la fuente para mirar el margen y conviene que eso
  quede claro para quien los abra.
- [ ] Tras el piloto: sustituir bajas, minutos de soporte por cuenta y horas por alta
  por lo medido. Son las tres cifras que más mueven el resultado y ninguna está
  medida; la página las señala una a una.

## Modelo economico base — 18-sep

- [x] Libro base al día: tres equilibrios, dos contribuciones, cohortes con bajas,
  horas del founder como límite y caja a 36 meses, sin perder el desglose de costes
  driver a driver que solo tenía este libro.
- [ ] Founder: **abrir el libro con Excel** y confirmar que no pide reparación. Es
  la única verificación que no se ha podido hacer aquí, y en v3 fue la que
  descubrió dos errores que ninguna comprobación automática vio.
- [ ] Founder: revisar las cinco partidas de estructura con facturas reales
  (plataforma 7 €, herramientas 40 €, gestoría 60 €, seguro 30 €) y la cuota de
  autónomos (300 €). Son PENDIENTE en el libro, no supuestos.
- [ ] Founder: confirmar la caja inicial. El escenario base baja a −3.390 € y el
  prudente a −20.989 €: con 4.000 € solo sobrevive el base, y eso es lo que decide
  si el plan es financiable.
- [ ] Founder: decidir si la cuota de implantación de 99 € se aprueba. Está en el
  libro al 0 % a propósito; al 100 % el equilibrio de caja se adelanta del mes 10
  al 7 y la caja nunca llega a ser negativa.
- [ ] Tras el piloto: sustituir bajas, minutos de soporte por cuenta y horas por
  alta por lo medido. Son las tres cifras que más mueven el resultado y ninguna
  está medida.
- [ ] Founder: `Ruta-a-5000-autonomos.html` escala el soporte con **12 min/cuenta** y
  el modelo base usa **18,1** (los 12 son solo del plan Autónomo; 18,1 es la media
  ponderada por la mezcla 55/35/10). A 5.000 cuentas eso son ~12 personas de soporte
  en vez de ~8. Decidir cuál vale y dejar los dos documentos diciendo lo mismo.

## Primeros clientes — 17-sep

- [x] Guía de primeros clientes, escalado y costes: `Ruta-a-5000-autonomos.html`.
- [ ] Founder: confirmar la zona de arranque. Propuesta: pilotos en Lleida ciudad y
  el Segrià (3) y en un pueblo a menos de 30 minutos (2); en la etapa 2, primero pueblos.
- [ ] Founder: lista de 40 nombres y cinco cafés con fecha.
- [ ] Founder: pregunta escrita a la asesoría sobre el piloto gratuito y el RD 1007/2023.
- [ ] Founder: decidir el precio de fundador (propuesta: Negocio al precio de Autónomo
  durante 12 meses).
- [ ] Ampliar la prospección con búsqueda manual o la API oficial de Google Places; la
  base de OpenStreetMap recoge 74 fichas y pocos oficios. Contactar en persona o por
  presentación, no con mensajes comerciales sin consentimiento.

## Modelo economico v3 — 17-sep

- [x] Libro realista: founder con coste, horas como límite, cohortes con bajas,
  prueba gratis e impagos.
- [ ] Founder: revisar las siete partidas de estructura del Panel con las facturas
  reales (servidores, herramientas, gestoría, seguro) y la cuota de autónomos.
- [ ] Founder: decidir la retirada mensual. Es la cifra que convierte el proyecto
  en un trabajo, y de ella salen las 44 cuentas de equilibrio.
- [ ] Founder: estimar honestamente las horas al mes que puedes dedicar a vender y
  atender. Es la palanca que más mueve la rampa.
- [ ] Tras el piloto: sustituir bajas, minutos de soporte y horas por alta por lo
  medido. Con esas tres, el resto del modelo deja de ser un escenario.

## Baja de cuenta — 17-sep

- [x] Reproducido el error interno y localizadas las siete tablas que faltaban.
- [x] Prueba estructural que exige cobertura de toda tabla con `business_id`.
- [ ] Founder: repetir la baja en producción con una cuenta de prueba que tenga
  WhatsApp conectado, y confirmar que termina sin error.
- [ ] Añadir la baja completa al smoke de PostgreSQL: el orden de claves foráneas
  es el mismo, pero ahí no está probado.

## Modelo economico v2 — 17-sep

- [x] Libro nuevo por fórmula desde una sola hoja de mandos, con el de agosto intacto.
- [x] Bajas, vida y LTV; cinco estructuras de comisión; cuota de implantación;
  caja mes a mes a 36 meses.
- [x] Verificado con Excel: reproduce las cifras del 15/07 y del 16/09, y reacciona
  al cambiar un supuesto.
- [ ] Founder: revisar si los supuestos por defecto (bajas 4 %, CAC 150 €, altas 10
  al mes) son los que quiere usar para decidir sobre el canal.
- [ ] Tras el piloto: sustituir bajas, CAC y mezcla por datos medidos y volver a
  generar el libro. Hasta entonces, ninguna comisión debería firmarse.

## Audio y respaldo de IA — 17-sep

- [x] Localizado el origen real del mensaje: falla el respaldo de IA, no Groq.
- [x] Al no entender una nota de voz, se repite lo transcrito (web y WhatsApp).
- [ ] Founder: renovar `ANTHROPIC_API_KEY` en Railway (la del `.env` local da 401)
  y comprobar que una frase libre deja de dar ese mensaje.
- [ ] Founder: mandar una nota de voz en el asistente web y mirar si tu burbuja
  muestra el texto transcrito; si lo muestra, Groq funciona.
- [x] Último error del proveedor de IA visible en Ajustes (hecho el 16-sep en
  `aa0f402`: `routers/pages.py` lo pasa y `ajustes.html` lo muestra bajo el interruptor).

## Descargas en Excel — 17-sep

- [x] Escritura de `.xlsx` con la biblioteca estándar, con tipos, filtro y anchos.
- [x] Costes, Facturas, facturas recibidas y jornada del equipo.
- [x] Abierto y verificado con Excel real (fechas, sumas, filtro, sin reparación).
- [ ] Founder: abrir uno descargado desde el navegador y, si usa alguno, probarlo
  en LibreOffice o Google Sheets.
- [ ] Si hace falta, exportar también presupuestos, clientes y agenda.

## Coherencia del gasto — 17-sep

- [x] El mes suma las facturas de proveedor confirmadas, con desglose.
- [x] El gráfico por categorías las incluye.
- [ ] Founder: confirmar que la nueva cifra de gasto del mes es la que espera, y
  avisar si algún papel está apuntado dos veces (gasto manual + factura recibida).

## Cliente desde una factura adjunta — 17-sep

- [x] La lectura extrae dirección, correo y teléfono del receptor, validados.
- [x] Campos editables en la revisión y alta solo con confirmación del titular.
- [x] Una ficha que ya existe conserva sus datos de contacto.
- [ ] Probar en producción con una factura real de un cliente nuevo y comprobar
  que la dirección leída sirve para emitirle una factura completa.
- [ ] Si la dirección llega partida en varias líneas del PDF, revisar si conviene
  separar código postal y población en campos propios.
## Modelo económico y canal comercial — 16-sep

- [x] Modelo con bajas, vida del cliente, LTV, coste de canal y caja a 36 meses,
  apoyado en los costes por plan de julio: [[Canal-comercial-y-comisiones]].
- [ ] **Founder: aprobar o corregir la estructura de comisión propuesta** (una
  mensualidad al alta más 10 % durante doce meses, con devolución si la cuenta cae
  antes del cuarto mes). Sin esta aprobación no se promete nada a nadie ni se
  construye la atribución, según la decisión del 2026-08-07.
- [ ] Founder: decidir si se cobra cuota de implantación de 99 €, bonificada en
  contratación anual. Es lo que hace que captar no consuma caja.
- [ ] Founder: fijar los tramos por volumen para gestorías, distintos del porcentaje
  individual de un comercial.
- [ ] Preguntar a la abogada por la calificación como contrato de agencia (Ley
  12/1992) y la indemnización por clientela antes de firmar con ningún comercial.
- [ ] Tras aprobar la estructura: código de referido en el alta, origen guardado en
  la cuenta e informe mensual de liquidación por comercial. Hoy no existe nada de eso
  en `src/noesis/`.
- [ ] Medir en el piloto el churn real a 30/60/90 días y los minutos de soporte por
  cuenta nueva; son los dos supuestos que sostienen todo el modelo.

## Agenda y estado de la IA — 16-sep

- [x] Órdenes de agenda en lenguaje normal; fecha conservada y cliente preguntado.
- [x] Último fallo del proveedor de IA visible en Ajustes.
- [x] Modelo de respaldo sin sufijo de fecha en código y `.env.example`.
- [x] Railway vuelve a desplegar: `aa0f402` quedó publicado el 16-sep tras el
  despliegue manual del founder.
- [ ] Founder: comprobar la clave de Anthropic contra
  `https://api.anthropic.com/v1/models/claude-haiku-4-5` y corregir
  `NOESIS_FALLBACK_MODEL` en Railway si tiene el identificador con fecha.
- [ ] Tras desplegar: repetir «añade un trabajo para mañana a las 12» en la web y en
  WhatsApp, y mirar Ajustes para ver si queda algún fallo de IA registrado.
- [ ] Ampliar la agenda a rangos («de 9 a 11»), recurrencias y cambio de cita; hoy
  solo se crea un trabajo con fecha y hora.

## Lectura y revisión de documentos por WhatsApp — 16-sep

- [x] Una sola lectura por documento (IA + texto local) con desacuerdos visibles.
- [x] Lector local sin IA: total, base, varios tipos de IVA, IRPF, número, fechas,
  NIF validado, proveedor, extractos y separación por páginas.
- [x] Correcciones en el chat; el SÍ solo se acepta cuando las cifras cuadran.
- [x] PDF con varias facturas separado y revisado una a una; extracto contrastado
  con lo registrado; duplicados detectados por proveedor y número o importe y fecha.
- [ ] Probar con documentos reales del founder: fotos de tickets, PDF de proveedor
  escaneado y un extracto de verdad. Medir aciertos antes de prometer precisión.
- [ ] Validar en WhatsApp real (Meta) el recorrido completo: foto → corrección → SÍ.
- [ ] Decidir si el mismo lector se usa en la web y en el correo entrante; hoy
  conservan el recorrido anterior.
- [ ] Revisar con el piloto si `NOESIS_EXTRACTION_MODEL` debe subir de Haiku a un
  modelo mayor por calidad de lectura.
- [ ] Dos SÍ seguidos en una cola: el segundo confirma la siguiente factura aunque
  el titular no haya visto su resumen. Medir en el piloto si molesta.

## Documentos: conectividad con Facturas/Costes — 15-sep

- [x] Revisión manual cuando falla la lectura automática y acciones visibles en móvil.
- [x] Separar un PDF con varias facturas por rangos, conservando el original.
- [x] Impedir contabilizar el lote o duplicar un documento ya ligado.
- [ ] Prueba visual en navegador y móvil físico con sesión real del socio.
- [ ] Sugerir rangos automáticamente (detección de cabeceras por página); hoy los
  indica el usuario.
- [ ] Decidir con el founder cómo importar facturas emitidas históricas a Facturas
  sin romper numeración ni Verifactu; hoy solo se archivan.

## Cerebro propio y simulacro — 15-sep

- [x] Candidato local: contención de negativos y varias cantidades; nombres con
  «llamado», «cliente:» y conectores fiscales; IVA incluido en gastos y ocho regresiones.
- [x] Piloto local desactivado: líneas netas con IVA explícito, correcciones de
  cantidad/precio/cliente y propuesta versionada común a ambos canales.
- [ ] Ampliar gramática multilínea y correcciones a otros dominios; no hay
  comprensión universal ni flujos compuestos. Ver `02-tecnico/Cerebro-local-piloto.md`.
- [ ] Conciliar lecturas económicas y validar aritmética/duplicados de recibidas.
- [x] Candidato: foco PDF web por actor, emisión propuesta y huella transaccional.
- [ ] Flujos compuestos PDF y prueba física de WhatsApp.
- [ ] Evaluar modelo privado contra corpus reservado, sin autoentrenamiento ni
  activación por defecto. Conservar aislamiento de datos y permisos.
- [ ] Revisar candidato, suite y PostgreSQL antes de publicar; sin deploy nuevo.

## Notas de voz con Groq — 14-sep

Decisión del founder: activar la voz con Groq. Pasos en
[Conectar-APIs §6](03-whatsapp-e-integraciones/Conectar-APIs.md).

- [x] Proveedor Groq reforzado: sin redirecciones con la clave, formatos admitidos,
  tamaño, respuesta acotada y errores sin datos; pruebas web y WhatsApp por Groq.
- [ ] Founder: aceptar y archivar el DPA/condiciones de Groq (RGPD 1.0) **antes**
  de poner la clave.
- [ ] Founder: crear la clave en console.groq.com y poner `GROQ_API_KEY` en Railway.
- [ ] Tras reiniciar: `noesis-integrations-check --network` y preparación en verde.
- [ ] Prueba real: nota de voz en el asistente web y en WhatsApp, en castellano y
  catalán, con una orden de dinero que pida SÍ.

## Bienvenida de clientes — 14-sep

- [x] Página `/bienvenida` con la guía para clientes, sin indexar y sin guion interno.
- [x] Vídeo de YouTube inerte hasta pulsar; CSP y políticas solo con variable.
- [ ] Founder: grabar el vídeo con el guion de `Guia-instalacion-clientes.html`
  cuando la pantalla nueva de WhatsApp esté publicada.
- [ ] Founder: subirlo a YouTube como «oculto» y poner su enlace en
  `NOESIS_WELCOME_VIDEO_ID` en Railway.
- [ ] Enlazar `https://bynoesis.com/bienvenida` desde el correo «Tu acceso a
  Bynoesis ya está listo» (o en uno que salga justo después).
- [ ] Tras desplegar: abrir la página en un móvil real y reproducir el vídeo.

## Google Analytics — 13-sep

- [x] Aviso de cookies con Aceptar/Rechazar; GA4 solo tras aceptar y revocable.
- [x] CSP de Google solo en rutas públicas; políticas condicionadas al ID.
- [x] Founder: crear en analytics.google.com una propiedad GA4 con flujo web
  `https://bynoesis.com` y copiar su ID de medición (`G-...`).
- [x] Founder: poner `NOESIS_GA_MEASUREMENT_ID=G-...` en las variables de Railway.
- [ ] Tras desplegar: aceptar el aviso en producción y ver la visita en «Tiempo
  real» de GA; rechazar y comprobar que no hay peticiones a Google.

## Facturación conversacional — 10-sep

- [x] Reproducir espacio en ID de Meta con subida real, sin entregar ni emitir.
- [x] Conservar precio final y confirmar versión de borrador antes de emitir.
- [ ] Extender contrato estructurado a otros dominios en observación: alcance y
  criterios en `Agente-operativo-fiable.md`, no prometer comprensión universal.

- [x] Reproducir captura nueva: «crear y adjuntar» no busca una factura previa;
  «F2 Jana» completa búsqueda y «créalo» mantiene rechazo fiscal explícito.

- [x] Eliminar fallback de cliente desconocido a factura demo o última emitida.
- [x] PDF real de borrador marcado, sin emitir por pedir una descarga.
- [x] Contexto reciente/citas nuevas verificables; preguntar si no consta.
- [x] Pruebas de creación inventada, error F2, aislamiento y flujo completo.
- [ ] En WhatsApp real: crear un ticket nuevo, comprobar nombre/importe
  del PDF y responder a una cita nueva; validar también fallo real del proveedor.
- [ ] Asesoría: validar excepciones F2 hasta 3.000 € antes de ampliar el límite
  general; no activar por la palabra «ticket».

## SEO y GEO — 10-sep

- [x] Un solo nombre público, «Bynoesis», en títulos, descripciones, FAQ y demo.
- [x] `/llms.txt` generado desde catálogo, contacto y estado del alta.
- [x] FAQPage en `/preguntas` desde la misma fuente que las 16 respuestas visibles.
- [x] Publicado en `88adfa3` y comprobado: `/llms.txt` 200 sin `noindex`,
  `/preguntas` con FAQPage de 16 y portada sin «Noesis».
- [x] Bing Webmaster importado desde Search Console; sitemap en Success con 14 URLs.
  Search Console: sitemap Correcto (14) e indexación pedida para `/`,
  `/preguntas` y `/autonomos` para renovar el título antiguo «Noesis».
- [x] Cola de Facebook con el nombre Bynoesis antes de conectar la página.
- [x] Founder: borradas en Bing las seis URLs enviadas por error como sitemap.
- [ ] En 1-2 semanas: comprobar que «bynoesis» muestra el título nuevo y revisar
  en Search Console las 20 páginas indexadas frente a las 14 del sitemap.
- [ ] Validar `/preguntas` en validator.schema.org (Google ya no muestra FAQ
  enriquecida a la mayoría de sitios; el marcado sirve para comprensión).
- [ ] Marca: consultar en la OEPM «Bynoesis» frente a las «Noesis» de software
  existentes y decidir su registro con asesoría (pregunta 23 de
  `05-legal-y-rgpd/Preguntas-abogado-TIC.md`).
- [ ] Founder: enviar a la abogada TIC las 23 preguntas y los textos publicados, y
  pedir presupuesto cerrado con el alcance escrito.
- [ ] Decidir contenido nuevo: páginas por oficio y guía Veri*Factu 2027. Sin
  cifras, testimonios ni fichas de valoraciones hasta tener evidencia real.
- [ ] Fichas externas (LinkedIn, directorios de software) con los mismos datos
  que `/llms.txt`.

## Coherencia documental y Proyectos — 10-sep

- [x] Mostrar en Documentos las facturas generadas desde web o WhatsApp sin
  duplicar ficheros ni fuentes de verdad.
- [x] Mantener borradores visibles pero fuera de ingresos, y evitar duplicar una
  factura cuando ya existe un original vinculado.
- [x] Limitar avance de proyecto a 0–100 en cliente y servidor, y hacer visibles
  sus estados, incluido Cancelado sin pérdida de historial.
- [ ] Validar ergonomía del deslizador y controles en Safari/iPhone físico durante
  el piloto; la prueba automatizada no sustituye el gesto táctil real.

## Lenguaje real de PDF — 10-sep

- [x] Reproducir y cubrir «Passame el pdf del tiquet» y «No pots enviar el pdf per
  aqui?» sin delegarlas al modelo generativo.
- [x] Impedir que el modelo niegue el envío real de PDF por WhatsApp.
- [ ] Repetir ambas frases en el número sandbox/real tras publicar y comprobar que
  WhatsApp muestra el adjunto, no únicamente un estado HTTP aceptado por Meta.

## Entrega de PDF y voz — 9-sep

- [x] Interceptar peticiones de PDF al titular antes de la IA y enviar documento
  real por Meta, con aislamiento, estado fiscal, nombre seguro y fallback veraz.
- [x] Impedir que una respuesta generativa confirme un adjunto inexistente.
- [x] Diagnóstico remoto de voz: ningún transcriptor está configurado.
- [ ] Provisionar y validar Whisper privado o configurar Groq antes de anunciar
  notas de voz como capacidad disponible. 14-sep: elegido Groq, ver arriba.
- [ ] Prueba humana del adjunto contra el número real después del despliegue.

## Rediseño público — 9-sep, publicación autorizada

- [x] Cuatro páginas, hero conversacional, prueba de producto y navegación móvil.
- [x] Calendario real opt-in, revocación, origen del iframe y altura adaptable.
- [x] SEO coherente, contadores mínimos en Marketing y empaquetado de assets.
- [x] Preservar el último cambio del socio sobre identidad de teléfono.
- [x] Autorización del founder para publicar en main y Railway.
- [x] Verificar Railway y humo público de ccb1b54: correctos.
- [ ] Verificar CI y despliegue del hotfix de contadores PostgreSQL.
- [ ] Canal público WhatsApp preparado antes de configurar su CTA dedicado.
- [ ] Validación de voz/OCR/Meta reales, cita/correo coordinados y Safari físico.
- [ ] Continuar ajustes con el socio y recoger métricas de campo tras publicar.
  Detalle: [[Rediseño-web-2026-09-09]].

## Release consolidada — 8-sep

- [x] Reconciliar el trabajo local con el `main` del socio y conservar ambas
  protecciones en los conflictos. Validación local: 107 dirigidas y 752 completas.
- [x] Preparar para producción administración, móvil, consumo, fiabilidad y copias,
  manteniendo revisión/aprendizaje apagados y sin crear Whisper o AWS externos.
- [x] Release `086039e0b538`, `ready`, esquema 55, 14 páginas y 8 cabeceras
  verificados tras el despliegue; CI completo y humo PostgreSQL en verde.
- [ ] Activar capacidades opcionales solo en entorno aislado y después de sus
  validaciones reales; no confundir código publicado con servicio operativo.

## Aprendizaje supervisado — código incluido y apagado 8-sep

- [x] Corrección, acción confirmada y APRENDER explícito; memoria literal visible,
  eliminable y aislada, sin convertirla en instrucciones privilegiadas del modelo.
- [x] Factura incompleta guiada por campos y telemetría sin contenido; informe
  autenticado por negocio y CLI. No se añade una pantalla administrativa.
- [ ] Revisión del candidato, PostgreSQL, corpus de conversaciones ca/es y piloto
  con voz/WhatsApp reales. No afirmar comprensión universal ni aprendizaje autónomo.
- [ ] Ampliar diálogo a otros procesos y casos ambiguos solo tras evaluaciones.
  Guía: [[Aprendizaje-supervisado-Bynoesis]]. Flags apagados.

## Confirmación y voz privada — candidato local 8-sep

- [x] Preparar/revisar/confirmar/corregir detrás de flag apagado; sin clientes
  implícitos ni asignación inferida de gastos a proyectos.
- [x] Adaptador/servicio de voz con clave, límites y errores seguros. Modelo small
  local real probado mediante HTTP con audio sintético, sin API pagada.
- [x] Código de revisión preparado para publicar apagado tras QA local; falta validar
  PostgreSQL concurrente y build Linux antes de activarlo.
- [ ] Servicio privado de pruebas con presupuesto autorizado; corpus ca/es, ruido,
  nombres/decimales; móvil y Meta reales antes de activar el piloto.
- [ ] Correo, copia independiente y aceptación Stripe siguen separados. Runbook:
  [[Fiabilidad-conversacional-y-Whisper]]. Árbol principal ajeno preservado.

## Candidato de fiabilidad — 7-sep

- [x] Validación local de aritmética/fechas/NIF en borradores, corrección de
  recibidas, relectura de fotos duplicadas, `VTIMEZONE`, dictado de importes y alta
  explícita de cliente/proveedor con simulación sintética sin créditos.
- [ ] Recorrer el candidato con móvil y calendario reales; probar OCR/voz con un
  corpus anonimizado y Meta real antes de afirmar precisión externa.
- [ ] Diseñar desambiguación conversacional persistente («el primero», apellido o
  teléfono) y referencias humanas para trabajos/documentos sin mostrar ids.
- [ ] El alta de usuarios debe reutilizar el flujo de invitación de Equipo con
  correo, rol y confirmación; nunca crear credenciales desde texto libre.

## Seguimiento del centro de mando — 7-sep

- Verificar la revisión publicada y probar Safari/iPhone físico con cuenta autorizada.
- Conciliar consumo registrado con facturas de proveedores; completar cobertura
  de APIs sin presentar ausencia de eventos como coste cero.
- Roles administrativos granulares y métricas comerciales por cohorte pendientes.
- Copias independientes, WhatsApp y demás candidatos locales se revisan aparte;
  no entran en el commit del centro de mando.

## Seguimiento del informe del socio — 7-sep

- Revisar candidato móvil/admin/WhatsApp; Safari físico y Postgres antes de publicar.
- Medir APIs restantes/actor y conciliar facturas. FX ya parametrizado, no cotización en vivo.
- Cola duradera para media, paginación del resto de listados, roles internos y contexto documental reciente.
- Revisar navegación administrativa por seis apartados y fichas; candidato local.
- Voz, acuerdos/regiones, variables de marca y copia externa siguen pendientes.
- Cal.com aplazado. Detalle en [revisión de frentes](09-historico/Revision-frentes-2026-09-07.md).

> Único listado vivo de pendientes. La fotografía verificable está en
> [`project-state.json`](project-state.json); planes y traspasos no duplican estados.

## P0 — publicar y pilotar con seguridad

- [ ] Ejecutar los seis P0 de
  [`cumplimiento/Plan-Datos-Servidores-Copias`](05-legal-y-rgpd/cumplimiento/Plan-Datos-Servidores-Copias.md):
  bucket de copias en un segundo proveedor europeo con credencial de solo
  escritura, versionado y bloqueo de objetos, cifrado en cliente antes de subir,
  primer simulacro de restauración externa cronometrado (hoy RPO y RTO son
  estimaciones, no medidas), región UE y retención de logs a 30 días, y firma de
  los DPA con cada subencargado. Hasta cerrarlos, los riesgos de pérdida total del
  proveedor, ransomware y fuga de la copia siguen en alto y no deben tratarse datos
  reales de terceros a escala.
- [ ] Completar en `cumplimiento/Subencargados-y-transferencias.md` el estado real
  de cada DPA y verificar la certificación de los proveedores estadounidenses en la
  lista oficial del marco de adecuación. Sincronizar la tabla con la que publica
  `web/templates/encargado-tratamiento.html`.
- [ ] Nombrar sustituto y asesoría jurídica en la tabla de contactos de
  `cumplimiento/Procedimiento-brechas.md`: a las 3 de la mañana no se busca
  abogado, se llama al que ya está en la tabla.

- [ ] Medir tamaño comprimido y aprobar presupuesto/retención: calculadora en
  [[Costes-backups-y-desarrollo-interno]]. Multipart antes de superar PUT simple;
  no activar lifecycle por una estimación económica.

- [ ] Revisar/publicar solo con autorización el candidato local del 6-sep de
  backups, diagnóstico y multiplicidad documental. Crear un juego nuevo después:
  los ZIP históricos requieren asociación explícita. Esquema 55 sin cambios.
- [ ] Aprobar proveedor, región y retención de la copia independiente. Propuesta
  no ejecutada en [[Copias-independientes-AWS]]. Cuenta/MFA, contrato, ensayo con
  ficticios, permisos y restauración fuera de Railway pendientes. No hay bucket.
- [x] Validación técnica PostgreSQL 16 no productiva del candidato 55: migración,
  baja con factura, idempotencia/concurrencia, aislamiento, bandeja, outbox,
  exportación y rollback 55→54→53→54→55. Código anterior 53 probado sobre BD 55;
  datos e inmutabilidad conservados. Humo de rutas y backup/restauración correctos.
  Evidencia y límites: [[Revision-pre-main-2026-09-04]].
- [x] Publicación autorizada del esquema 55: backup real y restauración previa,
  release/ready, páginas públicas, accesos demo, recuentos operativos y auditoría
  verificados el 4-sep. Artefactos fijados fuera de rotación en Railway.
- [ ] Recorrer una solicitud humana completa con entrega real de correo. No se
  ha borrado ni cancelado ninguna cuenta real para probar el despliegue.

- [ ] Mantener el candidato ya publicado con
  `NOESIS_VALUE_LEDGER_ENABLED=false` y
  `NOESIS_VALUE_LEDGER_ADMIN_ENABLED=false`. El humo y rollback PostgreSQL aislados
  ya están verificados. Mantener la secuencia de rollback seguro:
  apagar ledger, restaurar código anterior aún sobre esquema 54, validar flujos y
  solo entonces ensayar 54→53. Nunca servir código 54 sobre esquema 53. Después,
  activar únicamente el ledger en 3-5 negocios piloto y reconciliar manualmente
  acciones/outcomes, contexto `qualifies_for_wub`, zonas horarias, WUB semanal,
  profundidad y aceptación. No enseñar métricas ni activar Confidence, Insight o
  Progress.

- [ ] Recorrer en escritorio y móvil el alta recuperable del esquema 49 ya
  desplegada en el release `8730826a79ab`:
  salir y volver en cada paso, revisar la identidad visual de factura, comprobar que
  WhatsApp no aparece conectado antes del webhook, posponerlo voluntariamente y
  confirmar que Stripe devuelve a la puesta en marcha y al primer cliente. El flujo,
  la persistencia y los bloqueos están cubiertos; CI completo, migración histórica
  y humo PostgreSQL están verdes. Faltan Meta y Stripe reales.
- [ ] Validar visualmente en escritorio y móvil la nueva entrada `/acceso` ya
  desplegada: selección autónomo/empresa o gestoría, retorno entre accesos, login de
  ambos perfiles y solicitud profesional. HTTP, aislamiento y ausencia de
  autoasignación de empresas ya están verificados.
- [ ] Rotar `NOESIS_SECRET`, SMTP y cualquier credencial que haya aparecido en una
  captura, PDF o conversación; revocar la anterior y eliminar/redactar las copias
  compartidas. No reutilizar secretos sugeridos por una IA.
- [ ] El release `c63bf0e` y el esquema 46 ya están desplegados: CI completo y humo
  PostgreSQL verdes, `/health` identifica el release, `/ready` confirma 46 y la
  portada responde 200. Completar la comprobación de dominio canónico, cookies
  `__Host-`, hosts, logs sin query string, Google OAuth admin, panel CISO, bitácora
  encadenada, Home, modo consulta, ficha de proyecto y login de gestoría mediante
  el proxy real. Release/esquema, cabeceras, textos legales, alta cerrada y
  redirección 308 de `www` ya se comprobaron el 6-ago. El 7-ago se verificaron el
  nuevo release, esquema, CI, humo PostgreSQL, origen propio 303/origen externo 403
  y login/cartera/logout sintéticos de la gestoría demo. El founder confirmó después
  que Chrome ya entra y muestra la cartera/ficha con la prioridad
  `Sec-Fetch-Site: same-origin`. El espacio fiscal del esquema 41 ya se desplegó y
  `/ready` lo confirmó. Falta recorrer visualmente la separación nueva entre
  Resumen, Documentos, Impuestos, Períodos y Solicitudes, además de completar las
  demás pruebas autenticadas. El release `40d5645` con esquema 47 y MFA de gestoría
  ya está publicado: CI completo/PostgreSQL verdes, `/health` y `/ready` coherentes
  y portada, `/acceso` y `/gestoria/login` en 200. Falta activar y recorrer TOTP,
  anti-replay y recuperación con una cuenta profesional y un autenticador reales.
- [ ] Residencia de datos, según [[Servidores-y-residencia-de-datos]]: firmar el DPA
  autoservicio de Railway y archivarlo; comprobar en el panel la región de los
  servicios web y Postgres, porque `railway.json` no fija ninguna y el valor por
  defecto de la cuenta es estadounidense; si están fuera de la UE, moverlos a
  una región europea adecuada con backup y ventana acordada: el volumen **ya tiene
  datos** y no se debe tratar como vacío. El candidato ya eliminó
  el valor `us-east-1` por defecto: una copia externa no sale si faltan región de
  firma, proveedor o residencia contractual. Falta verificar y configurar esos
  valores reales, no deducirlos del endpoint.
- [ ] Completar la validación profesional y externa de RGPD. El candidato ya retira
  el iframe de Cal.com y su excepción CSP; corrige `/cumplimiento`; declara Stripe,
  Google, Cal.com, Groq, correo, IA y backup según configuración; bloquea el alta si
  un proveedor configurable no está identificado; registra bajas con conservación;
  y añade [[RGPD-Registro-actividades]], [[RGPD-Matriz-proveedores]],
  [[RGPD-Procedimiento-derechos-y-bajas]] y [[RGPD-Procedimiento-brechas]]. Falta que
  el abogado valide roles, textos y tabla exacta de conservación; firmar/archivar
  DPA; demostrar regiones; ensayar una solicitud completa y una brecha; y solo
  entonces diseñar bloqueo y purga automática de cuentas canceladas. No programar
  esa purga con plazos inventados.
- [ ] La identidad legal ya está completada y publicada. Revisar aviso legal,
  privacidad, términos, DPA y fiscalidad con profesionales. Mantener
  `NOESIS_PUBLIC_SIGNUP_ENABLED=false` hasta cerrar toda esta lista P0.
- [ ] Validar en producción la puerta de apertura: con el alta cerrada, las cuentas
  existentes entran y una alta por contraseña o Google no crea cuenta; al abrirla,
  repetir prueba, contratación, preferencias, checkout, webhook, modo consulta y
  reactivación.
- [ ] Crear o actualizar en Stripe los productos **29/49/99 € + IVA**, enlazar sus
  seis `price_id` y probar en modo test dirección, NIF y `automatic_tax`; comprobar
  importe e IVA resultantes, Checkout sin activación prematura, `invoice.paid`,
  `trialing`, `incomplete`, `paused`, impago, cancelación, reactivación, eventos
  fuera de orden y portal de cliente antes de usar claves live. Verificar además
  con cuentas reales que Autónomo no puede usar Proyectos, Equipo, Gestoría ni
  Análisis avanzado y que Negocio/Premium sí pueden hacerlo por web, API, asistente,
  WhatsApp y portales. El 13-ago el Checkout sandbox de Autónomo cobró, generó una
  suscripción `active` y entregó `checkout.session.completed`, `invoice.paid` y
  `customer.subscription.created` con HTTP 200. La concurrencia podía dejar la
  cuenta en `pending`; el candidato lo impide bajo bloqueo de fila y recupera el
  pago mediante lectura autenticada de Stripe. El release `9f3dc48d9d4a` ya está
  desplegado y el founder ha confirmado que la cuenta queda activa. El candidato
  siguiente elimina la recompra del mismo plan, centraliza los cambios en el portal
  y bloquea un segundo Checkout también en el servidor. El release `3c7bd034828a`
  ya está desplegado. El candidato del 14-ago separa gestión general, tarjeta,
  cancelación y confirmación del plan/período exactos mediante deep links de Stripe.
  El siguiente candidato elimina la dependencia manual: crea y reutiliza una
  configuración de portal versionada con las seis tarifas, registra los fallos y
  vuelve a un error visible y está desplegado desde `52c61f9e6277`. Falta recorrer
  gestión, tarjeta, cancelación, anualidad y upgrade con sandbox; verificar que
  todos los precios
  usan un `tax_behavior` compatible y distinto de `unspecified`; y completar impago,
  downgrade, reactivación y permisos reales. El 14-ago se repitieron 7/7 contratos
  locales del portal (incluido el bloqueo de segundo Checkout); esto valida Bynoesis,
  pero no sustituye el clic autenticado dentro del Customer Portal de Stripe.
- [ ] Meta real: validar el número central y al menos dos números comerciales de
  negocios distintos con el mismo token de sistema/activos concedidos a Bynoesis.
  Comprobar webhook firmado, coincidencia WABA + `phone_number_id`, mismo remitente
  aislado entre empresas, texto, audio, foto/PDF, opt-out, ventana de 24 horas,
  plantillas fuera de ventana, estados, reintentos, revocación y cuenta inactiva.
  El motor multicanal, la bandeja y el alta manual auditada desde administración ya
  están construidos; falta Embedded Signup para autoservicio y la prueba extremo a
  extremo con números reales.
- [ ] **App Review de Meta para `whatsapp_business_management` en Advanced access.**
  Sin él, la API no puede operar sobre la WABA de un cliente aunque la comparta a
  mano: devuelve error 200. Afecta solo al canal comercial; el número central
  funciona con Standard access. `Meta-Verificacion` dice hoy que la revisión no
  hace falta y hay que corregirlo. Confirmar con soporte de Meta y, si se alarga,
  el plan B es un BSP para los números de cliente. Detalle en [[Ruta-legal]].
- [ ] Medir cuánto tarda el webhook de WhatsApp con una foto real: hoy responde
  cuando ha terminado descarga, OCR, extracción y respuesta. Si se pasa del tiempo
  que Meta espera, contestar 200 al instante y procesar el medio aparte.
- [ ] Confirmar la versión vigente de la Graph API (`META_GRAPH_VERSION`, hoy v23.0)
  y rehacer el margen por mensaje con la tarifa actual: el cálculo de
  [[Unit-economics-y-cerebro-interno]] usa el modelo de conversación de 24 h, que
  Meta sustituyó por cobro por mensaje de plantilla.
- [ ] Activar y validar voz (Groq Whisper o faster-whisper local) y OCR
  con corpus real en castellano/catalán/inglés. La ruta privada de OCR ya incorpora
  Tesseract/pytesseract para imágenes y PDFium para PDF escaneado, y Railpack instala
  `cat/spa/eng`, prepara orientación/contraste/escala e informa los modelos presentes;
  voz detecta el idioma automáticamente salvo pista explícita. Ejecutar
  `noesis-integrations-check --network`, comprobar el despliegue y medir
  precisión/tiempo. Sin esa validación,
  mantener las promesas públicas degradadas.
- [ ] Activar una vez `NOESIS_SEED_DEMO=true` en Railway, desplegar y recorrer los
  accesos reales de autónomo y gestoría y `/demo/cliente`. Confirmar que ambos
  negocios muestran datos completos y que cualquier escritura, envío o automatización
  queda bloqueada. Confirmar además en Documentos las carpetas de 1 ingreso,
  2 gastos, 1 ticket, 2 pendientes y 2 documentos en Otros. Después se puede volver
  a `false`: los registros persisten. El release `ea1f5f3e628f` permite ya consultas
  locales en el asistente demo sin historial, IA externa ni herramientas de
  escritura. El 14-ago se recorrieron localmente en escritorio/móvil el panel,
  Documentos, asistente, cartera de gestoría en escritorio y portal del cliente en
  móvil; se corrigieron el distintivo central, el desbordamiento de sugerencias y
  las fechas ISO. El release `aed36de59e30` ya se confirmó en producción y también
  se recorrieron el portal de cliente, el asistente y la gestoría móvil a 375 px.
- [ ] Aprobar plantillas Meta para factura (`noesis_factura_lista`), cobro,
  presupuesto y cita; validar SÍ/NO, PDF/enlace privado y entrega desde el WhatsApp
  real del titular.
- [ ] Correo real por API HTTPS o SMTP: credenciales, dominio autenticado,
  invitaciones, facturas, avisos, reintentos de la outbox y entregabilidad. La cola
  durable y las dos vías de salida ya están construidas. El comprobador de
  integraciones valida por lectura la cuenta Brevo y que `SMTP_FROM` sea un
  remitente activo, pero la entregabilidad exige envíos reales a Gmail y Outlook.
  **20-ago: primer envío real correcto.** Con `BREVO_API_KEY` y `SMTP_FROM` en
  Railway, una recuperación de contraseña disparada contra producción llegó al buzón
  de `xavier@bynoesis.com` con el remitente «Bynoesis». Queda comprobar que no cae en
  spam en Gmail y Outlook, y recorrer factura al cliente final, invitación de
  gestoría y reintento de la outbox.
- [ ] Entrada documental Hostinger: activar el catch-all hacia un único buzón de
  prueba, cargar las variables `NOESIS_INBOUND_EMAIL_*` con la función todavía
  apagada y crear una ruta para una empresa ficticia. Enviar a esa dirección un PDF,
  una foto, un duplicado, un correo sin adjunto y uno con dos destinatarios opacos.
  Solo si Hostinger conserva el destinatario original y cada caso falla o entra en
  el negocio correcto, activar `NOESIS_INBOUND_EMAIL_ENABLED=true`. Comprobar después
  en móvil que una factura de cliente conocido se relaciona por NIF y una nueva no
  aparece en Clientes hasta confirmarla. No usar todavía el catch-all para correos
  humanos o soporte: también recibirá errores tipográficos y spam del dominio.
- [ ] Crear el cliente OAuth web de Google, registrar exactamente
  `https://bynoesis.com/auth/google/callback`, cargar `GOOGLE_OAUTH_CLIENT_ID`
  y `GOOGLE_OAUTH_CLIENT_SECRET` en producción y probar alta y acceso reales. El
  botón permanece oculto hasta que ambas credenciales existan para no prometer una
  función falsa.
- [ ] Certificado/entorno AEAT: autorización por obligado tributario, mTLS en pruebas,
  aceptación/rechazo/duplicado/CSV/reintentos, alta y anulación ya construidas,
  subsanación de rechazos, declaración
  responsable y validación con asesoría fiscal antes de producción.
- [ ] Ejecutar `noesis-doctor --strict` y
  `noesis-integrations-check --network --strict` en producción; resolver cada
  bloqueo y guardar la evidencia sin copiar secretos.
- [x] Automatizar una puerta externa sin credenciales sobre producción: el comando
  `noesis-production-check` contrasta release, esquema, sitemap, las 14 páginas,
  H1/canonical, marcadores legales y cabeceras de seguridad. GitHub la ejecuta cada
  seis horas y bajo demanda. Falta contratar o configurar monitor 24/7 independiente,
  alerta multicanal y guardia de incidentes antes de una apertura masiva.
- [ ] Desplegar ClamAV en red privada, fijar `NOESIS_CLAMAV_REQUIRED=true` y probar
  archivo limpio, EICAR, caída y timeout sin almacenar el payload rechazado.
- [ ] La ejecución real del 26-ago reveló que las copias diarias posteriores al
  esquema 31 no quedaban verificadas: al restaurar, el trigger de inmutabilidad
  rechazaba las líneas históricas de facturas ya emitidas. El candidato suspende
  solo triggers de negocio durante la transacción descartable y el humo PostgreSQL
  crea y restaura una copia con facturas emitidas. Ya desplegado, producción creó una
  copia nueva de esquema 51 y `noesis-restore-check` terminó `ok` en 3,22 s. Queda
  configurar el bucket externo, descargar una copia y restaurarla en infraestructura
  distinta, documentando RPO/RTO; el mismo servidor no demuestra recuperación ante
  caída total.
- [ ] Ejecutar un pentest autenticado externo y una revisión de privacidad/RGPD,
  fiscalidad y procedimiento de incidentes. El modelo interno y la puerta de salida
  están en [[Seguridad-operativa]]; una revisión propia no sustituye esta validación.
- [ ] Piloto acompañado con 3-5 autónomos durante dos cierres semanales.
- [ ] Medir activación hasta primer cobro, tiempo ahorrado, trabajos sin facturar,
  cobros recuperados, correcciones, coste por cuenta y retención.

Credenciales, callbacks, variables y criterios de aceptación: [[Conectar-APIs]].

## P1 — profundidad después del primer piloto

- [x] Crear un paquete de branding reproducible: símbolo y lockups, transparentes y
  fondos, tamaños sociales, portadas, paleta, tipografía, plantillas, reglas de uso,
  licencias, manifiesto y revisión visual. Vive en `branding/` y no altera el runtime.
- [ ] Crear o reclamar `@bynoesis` en LinkedIn, Instagram y Facebook con doble factor
  y al menos dos administradores; seguir los textos y listas de
  `branding/redes-sociales/`, subir los activos preparados, comprobar el recorte real
  en escritorio/móvil y, cuando las URL sean definitivas, añadirlas como `sameAs` al
  `Organization` de la portada. Reservar YouTube/TikTok sin abrir un calendario
  adicional hasta sostener el canal principal.

- [ ] Conectar la automatización de Facebook: crear los secretos `FACEBOOK_PAGE_ID`
  y `FACEBOOK_PAGE_TOKEN` del repositorio siguiendo `facebook/README.md`
  (unos 15 minutos con `facebook/conectar.py`). Hasta que existan, los
  workflows quedan en pausa sin publicar nada. Después, la única tarea recurrente es
  leer cada domingo la incidencia «Revisión Facebook» y ampliar el calendario cuando
  el informe avise de que quedan pocas piezas nuevas.

- [ ] SEO operativo: publicado y verificado el candidato del 13-ago, volver a inspeccionar
  `/autonomos`, `/gestorias` y `/precios` en Search Console, solicitar indexación y
  revisar durante 2-4 semanas páginas indexadas, consultas, impresiones, clics,
  CTR y Core Web Vitals. No crear valoraciones, casos de éxito ni datos
  `SoftwareApplication` hasta que existan evidencias reales. Mantener la medición
  propia sin cookies; añadir analítica externa solo mediante una nueva decisión.

- [x] Diagnóstico técnico por cuenta para soporte: solo metadatos, estados y
  recuentos; acceso exclusivo de administración, registrado en la bitácora y sin
  contenido operativo ni credenciales.
- [x] Puerta de intervención de soporte: autorización explícita creada por el
  titular, motivo, alcances, caducidad 1/4/24/72 h, revocación y eventos encadenados.
  Administración no puede autoconcedérsela ni suplantar al usuario.
- [ ] Habilitar una a una las correcciones de soporte que demuestre el piloto,
  comprobando el permiso efectivo y registrando antes/después. Los metadatos
  documentales ya permiten corregir tipo, estado, cliente, proyecto y nota con
  permiso transaccional, aislamiento y bloqueo de facturas emitidas. Configuración
  ya limita la intervención a perfil, idioma/explicación y apariencia documental
  futura, dejando identidad fiscal, pagos, suscripción, integraciones y
  automatizaciones fuera de la firma. Falta validar ambos recorridos con un titular
  real y habilitar otras correcciones solo si el piloto las demuestra. No crear un
  editor universal.
- [x] Facturas emitidas: corrección guiada mediante rectificativa por diferencias,
  original inmutable, un solo borrador pendiente, revisión antes de emitir y causa
  R5 limitada a facturas simplificadas F2.
- [ ] Validar con asesoría y XSD AEAT si el piloto necesita rectificación por
  sustitución (`S`) y sus importes rectificados; hasta entonces Bynoesis la rechaza
  expresamente y no inventa un registro fiscal incompleto.
- [ ] Evaluar servicio privado y proveedor compatible con el mismo corpus en
  castellano/catalán: herramientas, calidad, latencia, coste, concurrencia y caídas.
- [ ] Documentos: deduplicación, búsqueda, PDF digital y OCR acotado de PDF escaneado
  trilingüe están construidos; faltan HEIC, extracción fiable de líneas y corrección
  masiva, y validar el conjunto con corpus real.
- [x] Perfil documental sin maquetador libre: tres plantillas probadas, color, logo
  saneado, pie textual, distintivo gráfico con tamaño/alineación/alcance y vista
  previa; cada factura emitida conserva una versión visual reutilizable. Incluye
  condiciones y validez, presupuesto PDF, portal aislado y decisión con evidencia
  seudónima antes de preparar la factura borrador. Falta validación visual con los
  distintivos reales que usarán los primeros clientes.
- [x] Archivo del titular por años, trimestres y tipos con el mismo criterio que la
  gestoría, entrada rápida horizontal, carpetas, filtros de estado, búsqueda y vista
  previa privada acotada bajo demanda, con distribución responsive para móvil.
- [ ] Calendario: validar la suscripción ICS en Google/Apple/Outlook; después decidir
  si el piloto necesita sincronización bidireccional OAuth y recurrentes.
- [ ] Conciliación: validar CSV de bancos reales; dejar PSD2/API bancaria y cobro por
  enlace para después del piloto. Ningún movimiento se confirma automáticamente.
- [x] Correo: el centro interno muestra fallos sin destinatario/asunto/cuerpo y
  permite reencolar de forma atómica y auditada solo correos agotados de la misma
  cuenta; el scheduler conserva la entrega y evita duplicados.
- [ ] Equipo: validar con varios trabajadores reales el canal central, offline,
  ausencias, permisos por rol y el resumen al titular. Costes, justificantes, dudas,
  bloqueos, revisión previa y presupuesto limitado al proyecto asignado ya están
  construidos; falta medir claridad, errores de asociación y carga de revisión.
- [x] Gestoría con cuenta profesional, invitaciones de un solo uso, varias empresas,
  acceso revocable, revisión y previsualización por documento, filtros, períodos,
  perfil fiscal y borradores explicables sin permisos de presentación o dinero.
- [ ] Gestoría: validar con un despacho real el cálculo previo de 303/130/111/115 y
  candidatos 347; definir deducibilidad, prorrata, regímenes especiales y los datos
  que faltan para 131/349/200/202 antes de prometer confección completa.
- [ ] Canal de gestorías: aprobar atribución, descuento para el cliente, comisión,
  duración, liquidación, devoluciones y fiscalidad del incentivo. El producto solo
  muestra clientes conectados hasta que el founder apruebe esas condiciones.
- [x] Gestoría: MFA TOTP opcional, reto tras contraseña, anti-replay, ocho códigos de
  recuperación de un solo uso y reconfiguración protegida sin semillas reversibles
  ni códigos en la cookie de sesión.
- [x] Gestoría: recuperación de contraseña por correo separada de los usuarios de
  negocio, respuesta no enumerativa, token hasheado/caducable/de un solo uso,
  sesiones anteriores revocadas y MFA preservado. Falta recorrer el correo real.
- [ ] Gestoría: passkeys, roles finos y piloto real con un despacho antes de abrir
  el acceso a terceros.
- [x] Control mensual por negocio para consumo de IA, extracciones, WhatsApp,
  correo, fallos de entrega y coste observado: reparto explícito y reconciliado,
  demos excluidas, coste sin driver visible y alertas por límite o margen.
- [ ] Completar la observabilidad por negocio con latencia y tasa de corrección por
  tipo de extracción/acción; validar umbrales con el piloto antes de prometer SLA.
- [x] Libro CFO interno por mes: costes reales, previsiones y ajustes append-only;
  contribución, margen observado y coste por cuenta de pago sin inventar gastos.
- [ ] Cargar facturas reales de Railway, proveedores, seguridad, correo, Meta,
  Stripe y horas de soporte durante el piloto; conciliar MRR comprometido con cobros
  reales y añadir CAC/churn cuando exista una muestra válida.
- [ ] Eliminar `unsafe-inline` de la CSP efectiva tras migrar scripts/estilos inline;
  mientras tanto observar la política estricta en report-only sin romper la UI.
- [ ] Evaluar passkeys y permisos finos para gestoría antes de abrir acceso a
  terceros; valorar RLS PostgreSQL y KMS/cifrado de campos tras el piloto según el
  riesgo y la complejidad observados. El antivirus privado ya tiene adaptador y
  modo de fallo cerrado; falta desplegar el daemon.
- [ ] Revisar cada pantalla con evidencia visual tras estabilizar el diseño; su
  jerarquía debe responder a su tarea, no copiar la de otra sección.
- [ ] Fiscalidad ampliada: exenciones E1-E8, no sujeción N1/N2, inversión del sujeto
  pasivo, identificación extranjera y divisas, solo después de validarlas con
  asesoría y XSD/validaciones AEAT. Hasta entonces el 0% es tipo cero, no exención.

## P2 — solo con retención demostrada

- Personalización por sector, rutas, hitos, PWA profunda, inventario, nóminas y
  recepcionista de voz, sujetos a demanda real y unit economics sostenibles.

## Límites permanentes

- Bynoesis prepara; el autónomo confirma pagos, transferencias, impuestos, emisiones,
  envíos sensibles y borrados irreversibles.
- Todo aprendizaje distingue observado de confirmado y es visible y corregible.
- Toda operación filtra por `business_id`.
- El cerebro local sigue disponible aunque una integración falle o se desactive.
