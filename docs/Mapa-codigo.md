# Mapa de código

## CRM de captación — 21-sep

Dos CRM con el mismo nombre y dueños distintos, que es la confusión a evitar al
tocar esto:

- `db.leads` + `/b/<id>/crm`: **del autónomo**. Sus posibles clientes y sus
  presupuestos. Filtra por `business_id` como todo lo demás.
- `sales_prospects` + `sales_touches` + `/admin/crm` (migración **57**): **de
  Bynoesis**. A quién perseguimos nosotros. **No lleva `business_id`** a propósito:
  no es de ningún cliente, igual que `economy_assumptions`.

`src/noesis/sales.py` es el catálogo único: `ESTADOS` (nueve, los del piloto, con
cuántos días tarda en vencer el siguiente paso), `ORIGENES` (con `del_interesado`,
que decide si hay deber de informar del art. 14), `OFICIOS`, `CANALES`, `GUIONES`
(castellano y catalán, con huecos `{nombre} {yo} {quien} {oficio} {zona}`) y
`OBJETIVO` (el embudo de la parte 1 de la Ruta a 5.000). La validación de `db.py`
lee de ahí: separar las dos listas es como se acaba teniendo un desplegable que
guarda un estado que el resumen ignora.

`parse_lista()` convierte lo pegado en filas y `db.import_prospects()` las mete sin
duplicar —por teléfono normalizado y por nombre—. `enriquecer()` añade lo que la
página necesita y la base no guarda (vencido, días sin tocar, deber de informar,
qué guiones tocan) y `resumen()` cuenta el embudo **acumulado**: quien está en
piloto cuenta también en el peldaño de conversaciones.

`db.add_sales_touch()` anota el contacto y mueve el estado en la misma operación, y
fija la siguiente fecha con `sales.siguiente_fecha()`. Separarlos es como se acaba
teniendo un embudo que dice «cita puesta» sin que nadie recuerde de qué día era.

`db.prospect_opt_out()` marca la baja y **no borra la fila**: borrarla haría que el
mismo nombre volviera a entrar en la siguiente lista pegada. Para el derecho de
supresión está `db.delete_prospect()`, que sí borra ficha e historial.

## Correcciones económicas y CI — 21-sep

`economics.py` separa bajas nuevas/maduras, valida mezcla y devuelve
`rampa.financiable` y `financiacion_adicional` con caja inicial ya incluida.
El JS envía solo palancas cambiadas. `economy_timeline` no inventa MRR ni
suscripciones pasadas. `scripts/check_secrets.py` conserva detectores/filtros,
normaliza rutas y compara huellas exactas sin reescribir la baseline ni aceptar
hallazgos nuevos. CI ejecuta el test JS del panel.

## Supuestos económicos editables — 18-sep

`economics.EDITABLE` es un catálogo de 47 campos que gobierna **tres cosas a la vez**:
qué pinta el formulario de `/admin/economia`, qué acepta el guardado y qué límites se
aplican. Mantener esas tres listas separadas es como se acaba teniendo un campo que la
web deja escribir y el modelo ignora en silencio; `tests/test_economia_panel.py` lo
impide con dos pruebas estructurales —todo campo editable existe en el modelo y todo
campo editable mueve alguna cifra—.

Cada entrada declara grupo, tipo (`escalar` o `plan`, este último con un valor por
plan), mínimo, máximo, paso, unidad y nota. `coerce()` convierte y acota sin lanzar
nunca: un campo mal escrito se ignora y conserva el valor anterior. `apply_saved()`
mezcla lo guardado sobre los valores de fábrica y `form_groups()` arma el formulario
marcando lo que está tocado.

La persistencia es la migración **56** (`economy_assumptions`): clave, valor en JSON,
quién y cuándo. Guarda solo lo que se desvía del valor de fábrica —volver a la cifra
original borra la fila—, así que la tabla es a la vez el estado y la auditoría de qué
se ha tocado. `db.save_economy_assumptions` valida con el mismo `coerce` del
formulario; `db.reset_economy_assumptions` vacía la tabla y devuelve todo a fábrica.

El orden de precedencia dentro de `build_report` es: valores de fábrica, encima lo
guardado, y encima las palancas de la URL. Así mover un deslizador para probar algo no
pisa lo que el founder dejó guardado.

## Economía en el producto — 18-sep

El modelo económico ya no vive solo en `analysis/`. Tres módulos nuevos, ninguno con
dependencias fuera de la biblioteca estándar:

- `src/noesis/economics.py`: el modelo. `ASSUMPTIONS` son los supuestos de
  planificación y `LEVERS` las palancas que el panel deja mover, con sus límites;
  `with_levers()` las acota antes de nada. `build_report()` devuelve economía por
  plan, medias ponderadas, los tres equilibrios, capacidad en horas, rampa de 36
  meses con cohortes y la comparación entre lo real y lo supuesto. Dos ideas lo
  ordenan: supuesto y dato nunca se mezclan, y hay **dos contribuciones** —en caja
  mientras atiende el founder, cargada cuando el soporte lo paga alguien— porque
  cobrar el soporte y además pagar una retirada contaría su tiempo dos veces.
- `src/noesis/officedocs.py`: escribe `.docx` y `.xlsx` con `zipfile` y XML. Un
  documento de Office es un ZIP con unos cuantos XML, así que no hace falta
  `python-docx` ni `openpyxl` en producción. El alcance es corto a propósito
  —títulos, párrafos, tablas, saltos de página y formatos de número— y esa es la
  línea a partir de la cual convendría una librería de verdad.
- `src/noesis/economics_docs.py`: los dos documentos de dos páginas a partir de un
  informe.

`db.economy_timeline(months)` da la serie mensual de cartera, conexiones, ingreso y
coste real del libro CFO; lo que no puede reconstruir lo deja en `None` en vez de
rellenarlo con ceros.

En `web/routers/admin.py`, cuatro rutas detrás de `_is_admin`: `/admin/economia`
(página), `/admin/economia/datos` (JSON que recalcula al mover una palanca) y las dos
descargas. El recálculo va al servidor a propósito: una copia del modelo en
JavaScript daría dos modelos que se separarían al primer cambio. La vista usa
`templates/admin_economia.html` con `static/admin-economia.css` y
`static/admin-economia.js`, que solo pinta —los gráficos son SVG propio, sin CDN— y
mantiene los enlaces de descarga sincronizados con las palancas de la pantalla.

## Modelo economico base — 18-sep

`analysis/build_modelo_economico.py` genera
`docs/06-negocio-y-finanzas/Bynoesis-Modelo-Economico.xlsx` con openpyxl (extra
`analysis`, no es dependencia del producto). Es el libro de referencia: 19 hojas, y
el único de los tres que calcula el COGS por plan desde sus drivers en vez de
copiar un total.

Estructura del script. El diccionario `D` del principio es la **única fuente de
verdad** de los valores por defecto: de él leen tanto la hoja `Supuestos` como la
comprobación aritmética que el script imprime al terminar, así que un supuesto no
puede cambiar en un sitio y no en el otro. `construir_supuestos()` escribe las
celdas editables y rellena `ref` (clave → `Supuestos!$B$41`) y `plan_row` (clave →
número de fila, con las columnas B/C/D por plan); el resto de hojas construyen sus
fórmulas a partir de esos dos diccionarios, de modo que reordenar un bloque de
supuestos no rompe nada. Las constantes `UE_*`, `HF_TECHO`, `R_INI` y `BE_RETIRADA`
fijan las filas que unas hojas referencian en otras, con aserciones que rompen la
generación si el maquetado se desplaza.

Las funciones `_cogs_plan()`, `_medias()` y `_rampa()` reproducen en Python la misma
aritmética que las fórmulas: sirven para la comprobación impresa y para calcular los
tres escenarios de la hoja `Escenarios`, que se escriben como valores porque una
hoja de cálculo no puede simular tres futuros a la vez.

Dos cautelas heredadas del QA de v3, que Excel rechaza y openpyxl acepta sin avisar:
una regla de formato condicional **no puede mirar a otra hoja** (de ahí los espejos
locales de `Rampa_36m!F6:F9`) y `CellIsRule` solo admite operadores de comparación
(para texto hay que usar `FormulaRule`). Los libros v2 y v3 siguen en su sitio.

## Modelo economico v2 — 17-sep

`analysis/build_modelo_economico_v2.py` genera
`docs/06-negocio-y-finanzas/Bynoesis-Modelo-Economico-v2.xlsx` con openpyxl (extra
`analysis`, no es dependencia del producto). `PLANES` guarda las cifras ancla del
15/07/2026; `panel()` escribe las celdas editables y devuelve sus referencias, que
el resto de hojas usan para construir fórmulas. Las constantes `UE_FILA_MEDIA`,
`CANAL_FILA_D`, `CAJA_FILA_BREAKEVEN`, `CAJA_FILA_MINIMA` y `CAJA_TABLA_INICIO`
fijan las filas que unas hojas referencian en otras, con aserciones que rompen la
generación si el maquetado se desplaza. El generador de agosto sigue en su sitio.

## Hojas de cálculo y gasto del mes — 17-sep

`web/xlsx.py` escribe `.xlsx` con `zipfile` y XML: `build_sheet(headers, rows)`
decide el tipo por valor (número, fecha ISO o `date`, texto en `inlineStr`),
`_escape` quita los caracteres que XML no admite y `_workbook_xml` sanea el nombre
de hoja. `web/reports.py` construye las filas una vez con sus tipos y las comparte
entre CSV y Excel; `work_reports.build_clockin_xlsx` hace lo mismo con la jornada.
`db.month_billing` suma ahora las `received_invoices` del mes junto a `expenses` y
publica el desglose; `db.expenses_by_category` las agrega por categoría. Sin
esquema nuevo ni dependencias.

## Cliente de una factura emitida con sus datos de contacto — 17-sep

`extraction._validated_invoice` añade `customer_address`, `customer_email` y
`customer_phone` con validación propia (`_one_line`, `_contact_email`,
`_contact_phone`); el prompt los pide en una sola línea. `documents/service.py` los
traslada al borrador y `confirm_client_candidate` los pasa a
`db.confirm_document_client_candidate`, que solo los escribe en el INSERT de un
cliente nuevo (`_short_field` acota y normaliza). La ruta
`/documents/{id}/client-candidate/confirm` acepta los tres campos del formulario.
`documentos.html` los muestra en `#r-client-contact` únicamente cuando la factura
es emitida y la propuesta está pendiente. Sin esquema nuevo: `clients` ya tenía
las columnas.
## PDF de la factura recién creada — 23-sep

`web/whatsapp.py`: `_attach_new_invoice_pdf` es el único sitio que decide si se
adjunta el PDF de una factura recién preparada, y lo llaman los dos caminos de
`_handle_inbound`: el normal y el de la revisión (donde la factura nace al
contestar «sí», y donde antes no salía nunca). Reutiliza `_send_owner_invoice_pdf`,
que ya existía: sube el borrador a Meta con `_upload_owner_draft_pdf` y lo manda
como documento con la leyenda «BORRADOR #id». No manda nada si el borrador está a
medias (`db.invoice_pending_fields`). Los documentos **no pasan por
`whatsapp_outbox`**: se publican directos, así que la cola sigue siendo solo de
texto y plantillas.

## Pedir la factura como se hable — 23-sep

`nlu.py`: `_MARCA_DE_CONCEPTO` se busca en toda la frase y el importe puede estar
antes o después de ella, así que «concepto» manda esté donde esté. El stripper de
impuestos sustituye por un espacio (sustituir por vacío pegaba «euros» con la
palabra siguiente). `_factura_sin_preposicion` atiende «factura reformas martinez
ventana 750», sin «a» ni «por»: quita verbo e importe y deja el resto para que lo
separe la cartera; si al quitarlos no queda ninguna palabra, no era una orden
(«factura 12» no lo es). `es_confirmacion` decide si una frase es un sí: exige un
afirmativo al principio y que detrás solo haya cortesías o la petición del PDF;
cualquier cifra o palabra de cambio lo invalida. La usan `action_review.respond` y
`chat._finish_order_for_a_new_client`, que antes tenían cada una su lista.

`web/chat.py`: `_split_client_with_the_ledger` corta el nombre por donde dice la
cartera. Se llama justo antes de despachar `crear_factura`, `crear_presupuesto` y
`agendar_trabajo`.

`routers/pages.py` y `ajustes.html`: la tarjeta de la IA muestra
`config.FALLBACK_MODEL` y avisa si no hay clave de proveedor.

## El nombre dictado y el cliente sin ficha — 23-sep

`nlu.py`: `_partir_nombre` decide dónde acaba el nombre y empieza la frase. Corta en
la marca explícita `concepto`/`en concepto de` y, si no la hay, en el primer punto
seguido de espacio cuyo token anterior no sea una inicial de una letra ni una sigla
de `_SIGLAS_CON_PUNTO` (S.L., S.A., C.B., …). `_recortar` quita la puntuación de los
bordes sin comerse el punto final de «S.L.». `_limpiar_cliente` lo aplica, así que
lo heredan todas las órdenes; `_cliente_y_concepto` reparte lo que sobra al concepto
cuando el parser no encontró uno, y `parse_party_name` corta igual en las altas.

`web/chat.py`: `_client_without_record` mira si el nombre dicho tiene ficha
—devuelve `None` cuando encajan varias, que ya se resuelve enumerándolas—;
`_ask_to_create_the_client` guarda la pendiente `alta-y-orden:{actor}` con la orden
entera y pregunta; `_finish_order_for_a_new_client` acepta un «sí» o el nombre
corregido, crea la ficha **llamando a `db` directamente** (pasarla otra vez por la
revisión pedía confirmar dos veces lo mismo) y ejecuta la orden guardada. Se invoca
desde `handle` **antes** de `action_review.respond`: si no, la revisión contesta «no
hay ninguna propuesta pendiente» y la orden se pierde.

## Alta de cliente y proveedor — 23-sep

`nlu.py`: `NEED_PARTY_NAME` es el alta sin nombre utilizable («crea el cliente» a
secas, o un nombre que solo son cifras). `parse_party_name` separa el nombre de los
datos dictados detrás —corta en la coma o en el «con teléfono…» y devuelve el
teléfono en limpio— y devuelve `(None, None)` cuando lo que queda no puede ser el
nombre de nadie. `_party_intent` reúne las dos entradas («crea el cliente X» y «da
de alta a X como proveedor») en un solo sitio.

`web/chat.py`: `_ask_party_name` pregunta y guarda la pendiente `alta-ficha:{actor}`
(30 min); `_party_name_answer` acepta la respuesta solo si parece un nombre (sin
interrogación, ocho palabras como mucho, ninguna del vocabulario de otras órdenes) y
`_party_error_reply` deja la pendiente puesta cuando el alta falla, que es lo que
convierte un error en algo que se puede arreglar hablando. `_motivo` quita el nombre
interno de la herramienta del mensaje de error.

`db.py`: `add_client` gana el límite de 200 que ya tenía `add_supplier`, y los dos
distinguen «falta el nombre» de «es demasiado largo», porque se arreglan de forma
distinta. `_find_supplier_row_by_name` pliega mayúsculas y acentos, y lo usan tanto
`find_supplier` como el control de duplicados de `add_supplier`.

`tools.py`: `_crear_cliente` acepta `telefono` y lo rellena si la ficha existía sin
él; un teléfono ya guardado no se pisa desde una frase.

`routers/clients.py` y `routers/invoicing.py`: las dos altas de cliente por web
devuelven 400 con el motivo. Sin ese `except ValueError`, el nuevo límite de nombre
habría salido como un 500.

## Factura a medias — 23-sep

`migrations.py` 58 añade `invoices.pending_fields`: lista JSON con lo que falta
(`cliente`, `concepto`, `importe`). NULL o `[]` es una factura completa.

`db.py`: `create_partial_invoice` crea el borrador con lo que haya —si llegan los
tres datos delega en `add_invoice` y no hay nada especial—; `complete_invoice_fields`
rellena huecos y, al caer el último, reconstruye la factura con
`update_invoice_draft`, la misma función que valida cualquier borrador, para que no
exista un segundo camino que se salte reglas; `invoice_pending_fields` lee la lista;
`latest_partial_invoice` es a la que se refiere «el importe es 300»;
`link_partial_invoices_to_client` enlaza por nombre al dar de alta el cliente.
`issue_invoice` se niega a emitir mientras quede un hueco y dice cuál.
`update_invoice_draft` limpia `pending_fields` y `recipient_name` al guardar desde
la web: el nombre apuntado a mano manda sobre el del cliente en
`list_invoices` (`COALESCE(recipient_name, c.name)`) y, si se quedara, la factura
seguiría saliendo a nombre de quien ya no es.

`nlu.py`: `PARTIAL_INVOICE` y `parse_partial_invoice` extraen lo que haya sin exigir
los tres datos. Tres guardias deciden que una frase crea: `_VERBO_CREAR_FACTURA`
(hace falta un verbo de crear), `_CONSULTA_FACTURA` y `_FACTURA_EXISTENTE`
(determinante definido + «de/del», o «factura nº 12»: se habla de una que ya
existe). `_FACTURA_RECURRENTE` deja las recurrentes fuera, que se configuran en
Facturas.

`web/chat.py`: `_create_partial_invoice` guarda la pendiente
`factura-a-medias:{actor}` (120 min) y `_complete_from_message`, lo primero de
`_handle`, rellena el hueco cuando el mensaje trae un dato marcado («el importe
es…») o, si solo falta el importe, una cantidad sola. `_client_from_conversation`
resuelve «este cliente» con los últimos 20 mensajes y **no adivina**: con varios
clientes y nadie nombrado, el cliente queda pendiente. Con el piloto guiado
encendido manda su conversación paso a paso y esto no se activa.

`facturas.html`: `pendientes()`, `sinFicha()` y `faltan()` pintan el badge «A
medias», esconden Emitir y Duplicar, y distinguen «falta el cliente» de «el nombre
está dicho pero no tiene ficha» mirando `client_id`, no `client_name`.

## Agenda por lenguaje natural y estado de la IA — 16-sep

`nlu.py`: `_is_agenda_order` acepta verbo + sustantivo («añade un trabajo») además
de los verbos directos; `_agenda_client` descarta fechas, el propio sustantivo y las
tareas (`_looks_like_task`: infinitivo en minúscula, para no confundir «cambiar» con
un nombre y respetar «Oscar»); `_agenda_description` toma el «para/de …» correcto
cortando en el siguiente «para». Constantes nuevas `NEED_DATE` y `NEED_JOB_CLIENT`.

`web/chat.py`: `_handle` recibe el actor y, con `NEED_JOB_CLIENT`, guarda la fecha en
la pendiente `agenda-cliente:{actor}` (30 min) y pregunta el cliente;
`_job_client_answer` acepta solo un nombre (rechaza sí/no y palabras de otras
órdenes) y completa el trabajo con `agendar_trabajo`. `_human_when` traduce la fecha
ISO a «mañana a las 12:00».

`db.integration_catalog` añade al detalle de la IA su último fallo y lo pinta en
ámbar; `routers/pages.py` pasa `ai_last_error`/`ai_last_checked_at` a `ajustes.html`,
que lo muestra bajo el interruptor. El catálogo, por sí solo, no se dibuja en ninguna
pantalla: lo consume `value_ledger`.

## Lectura y revisión de documentos — 16-sep

`documents/local_reader.py`: lectura determinista del texto de un documento, sin red.
Enmascara fechas, porcentajes, NIF y teléfonos antes de buscar importes; resuelve
etiquetas (`total`, `base imponible`, `IVA`, `IRPF`) por segmentos de línea y admite
tablas de cabecera/valores; detecta desglose por tipo cuando una línea contiene el
tipo y sus dos importes; decide emisor y receptor por etiquetas de cliente antes que
por orden. También lee extractos (filas con número, fecha e importe) y agrupa varias
facturas por página.

`documents/review.py`: estado de la propuesta. `derive` completa solo lo que se
deduce con certeza aritmética y lo marca como calculado; `apply_correction` entiende
frases cortas del titular y `_reconcile` descarta lo leído cuando choca con lo que él
dice; `evaluate` decide si se puede confirmar; `render` redacta el resumen.

`documents/reading.py`: combina la lectura de IA (`extraction.read_document`, una
sola llamada que devuelve todas las facturas y el extracto) con la local; rellena
huecos y guarda un conflicto de total en vez de elegir uno.

`web/whatsapp_documents.py`: la conversación. `ingest` guarda, lee, separa el PDF con
`pdf_batch` cuando las páginas son fiables y abre la cola en la acción pendiente
`doc-review:{teléfono}`; `handle_reply` interpreta SÍ, NO, TODAS, correcciones y
órdenes ajenas (que devuelve a su camino). `_register` crea gasto o factura recibida
reutilizando `service`, y comprueba duplicados antes. `web/whatsapp.py` solo delega.

## Lotes PDF en Documentos — 15-sep

`documents/pdf_batch.py`: `inspect` y `split` separan un PDF por rangos exhaustivos
con `pypdf`, reutilizando `service.upload` (hash, validación) y reintento sin
duplicados. `repo.register_pdf_batch`/`is_batch_source` usan
`document_classifications.method='pdf_batch'`. Rutas en `web/routers/documents.py`;
UI `splitPdf` en `templates/documentos.html`. Corpus: `tests/test_pdf_batch.py`.

## Planificador local de factura — 15-sep

`local_invoice.py`: planes tipados sin efectos, gramática neta ES/CA, revisiones
acotadas y foco por actor. `action_review.py` reutiliza normalizador y totales de
`db.py`; `revise_pending_action` reemplaza una versión de forma transaccional sin
ampliar caducidad. El flag exige revisión y queda apagado. Guía:
`02-tecnico/Cerebro-local-piloto.md`; corpus: `tests/test_local_invoice.py`.

## Inspección monetaria local — 15-sep

`intent_safety.inspect_money_intent` devuelve riesgo tipado sin efectos ni red.
`nlu.safety_refusal` lo aplica antes de interpretar. No sustituye validadores de
herramientas ni autoriza al devolver None. Corpus: `tests/test_intent_safety.py`.

## Plan de emisión y confirmación de versión — 10-sep

`conversation_plan.InvoicePlan` interpreta sin efectos; `invoice_fingerprint`
vincula la confirmación a cabecera/líneas. `expected_invoice` pasa esa expectativa
por contexto al motor nativo que la valida bajo transacción. `db.add_invoice`
acepta `gross_total` explícito de una línea para conservar el precio final con
ajuste de redondeo máximo de un céntimo. `tools._crear_factura` lo pasa solo cuando
el importe incluye impuestos. No cambia el cálculo por defecto del editor.

## Orden compuesta y aclaraciones — 10-sep

`whatsapp._handle_inbound` separa creación/adjunto y enlaza el PDF solo al recibo
real. Claves `pdf-selection` e `invoice-request` por teléfono/negocio, TTL diez
minutos, sin reintento de creaciones inciertas. `nlu._parse_simplified_sale`
reconoce crear un ticket para cliente e importe seguido de «concepto».

## Selección documental y recibos de ejecución — 10-sep

`tools.execution_receipts` conserva resultados por contexto de ejecución;
`web/chat.handle` renderiza creaciones de factura desde ellos.
`agent._refresh_conversation` sincroniza el historial, incluidos turnos locales.
`web/whatsapp._invoice_for_owner_pdf` no usa fallback ante referencias desconocidas.
`_remember_invoice`/`_remember_invoice_message` reutilizan pending_actions con
claves separadas y TTL (teléfono y hash del ID Meta). `_upload_owner_draft_pdf`
sube el PDF marcado; las emitidas conservan el portal existente. Sustituye la
restricción histórica «solo emitidas» descrita más abajo.

## Variantes lingüísticas y capacidad PDF — 10-sep

`web/whatsapp.py::_is_owner_pdf_request` reconoce familias de verbos castellanas,
catalanas y mixtas junto a PDF y contexto de entrega; evita mantener una lista
frágil de frases completas. `_claims_false_pdf_limit` es la segunda defensa: si
`chat.handle` niega enviar o generar PDF, reemplaza la salida por la capacidad
real, sin fingir que se adjuntó nada. Contratos en `WhatsappMediaTestCase`.

## PDF reactivo por WhatsApp — 9-sep

`web/whatsapp.py` reconoce localmente solicitudes de factura/ticket PDF antes de
`chat.handle`, resuelve número, último documento o cliente solo dentro del negocio,
exige estado emitido y llama a Meta con `type=document` y URL del portal existente.
La misma capa bloquea afirmaciones generativas de adjuntos que no han ocurrido.
No añade tabla ni adapta la cola proactiva: es una respuesta dentro de la ventana
abierta por el mensaje entrante. Tests en `WhatsappMediaTestCase`.

## Web pública conversacional — 9-sep

`web/public_marketing.py` centraliza CTA real, FAQs, schemas y nombres de eventos.
`templates/partials/public_conversation.html` y `static/public-marketing.js/css`
demuestran tres casos sin ejecutar operaciones. `public_product_demo.html` conserva
el panel previo; `public_testimonials.html` no muestra nada sin contenido aprobado.
`public-calendar.js` conecta el iframe solo tras permiso y valida sus mensajes.
`public-analytics.js` muestra el aviso de cookies si hay `NOESIS_GA_MEASUREMENT_ID`
y solo inserta Google Analytics tras «Aceptar». Retirar el permiso borra `_ga`.
`routers/pages.py` recibe contadores acotados; `db.public_interactions_summary`
separa `@event:` de visitas; `admin` muestra ambos. Sin tablas nuevas. CSP en
`server.py` permite Cal.com solo en Contacto. Los contratos están en
`test_public_marketing.py` y dos tests Node sin red. Detalle: [[Rediseño-web-2026-09-09]].
`/bienvenida` (`site_bienvenida.html`) es la guía para clientes que ya tienen
acceso: fuera de `_INDEXABLES`, con el bloque `robots` de `site_base.html` en
noindex. `public-video.js` inserta el iframe de youtube-nocookie.com solo al
pulsar; `config.WELCOME_VIDEO_ID` activa vídeo, CSP y menciones legales.

## Aprendizaje supervisado — 8-sep

`learning.py` prepara equivalencias literales, diálogo de factura y ofertas de
aprendizaje; `chat.handle` conserva el interceptador de revisión antes de herramientas.
`action_review.py` aporta resultado/propuesta para no aprender de una operación
fallida. `agent.py` excluye `language_rule` del prompt de sistema.
Persistencia existente: `business_memories`, `whatsapp_pending_actions` con prefijos
`learn:`/`clarify:`, `product_events`. API GET de informe en `routers/assistant.py`.
Sin esquema nuevo; flags dependientes y apagados. Véase el runbook de aprendizaje.

## Notas de voz con Groq — 14-sep

`adapters/transcription.py` elige el transcriptor en este orden: Whisper privado
(`NOESIS_PRIVATE_WHISPER_URL`), Groq (`GROQ_API_KEY`) y faster-whisper local.
`GroqWhisperProvider` comparte con el privado `_NoRedirect` y valida el tamaño, el
formato (`GROQ_EXTENSIONS`) y la longitud antes y después de llamar. Lo usan
`routers/assistant.py` (`/api/{id}/chat/audio`) y `web/whatsapp.py`
(`_audio_to_text`); `readiness.py` nombra el proveedor con el mismo orden.

## Confirmación conversacional y voz privada — 8-sep

`action_review.py` intercepta herramientas en `chat.handle`, fija identidad y
argumentos y consume una propuesta por negocio/conversación. Reutiliza
`whatsapp_pending_actions` con prefijos `web:` y `wa:` sin migración. `tools.py`
conserva el cliente revisado; `nlu.py` rechaza órdenes peligrosas. Web/audio comparten
usuario/versión de sesión; WhatsApp usa la identidad vinculada previa.
`private_voice.py` e `infra/whisper/Dockerfile` son un servicio opcional sin BD,
consumido por `adapters/transcription.py` y comprobado por `integration_check.py`.
Activación y límites: [[Fiabilidad-conversacional-y-Whisper]].

## Centro de mando administrativo — 7-sep

`admin.html` organiza siete departamentos; `admin_direction.html` resume las
prioridades y `admin_delivery_summary.html` la actividad registrada de canales.
`admin_navigation.html` comparte navegación con `admin_account.html`.
`admin-workspace.css/js` aíslan estilo, búsqueda y navegación progresiva.
`db.admin_api_usage` agrega eventos ai_usage por negocio, mes y proveedor/modelo;
router admin exige autorización existente y audita el endpoint JSON de consumo.
No carga contenidos de documentos ni credenciales. `NOESIS_COST_USD_TO_EUR`
es una hipótesis de estimación, no altera contabilidad ni impuestos.

## Núcleo

- `web/templates/admin_navigation.html` y `static/admin-workspace.css/js`:
  navegación progresiva por departamentos/ficha; no cambia permisos ni POST.
- `db.list_invoices`: filtro de cliente y paginación SQL opcionales;
  `routers/invoicing.api_invoices` expone límites validados sin cambiar defaults.
- `config.COST_USD_TO_EUR`: hipótesis configurable de conversión para estimaciones.

- `db.admin_api_usage`: consumo por negocio/mes/proveedor/modelo.
  `web/routers/admin.py`: JSON administrativo auditado y ficha con teléfono titular.
- `adapters/extraction._message`: observación documental fail-open.
  `tests/test_admin_usage.py`: autorización, aislamiento y clasificación conservadora.

- `scripts/estimate_backup_cost.py`: presupuesto offline S3/Railway por tamaño,
  frecuencia y días. Sin runtime ni borrado; `tests/test_backup_cost_estimate.py`.

- Fiabilidad 6-sep: `web/backups.py` empareja BD/ZIP y registra subida externa;
  `security_center.py` exige evidencia reciente por destino. El filtro parametrizado
  `db.list_security_events(event_types=...)` no pierde esos eventos entre aperturas
  del panel. `infra/backups/aws-s3.json` es propuesta manual no desplegada.
- `adapters/extraction.py` rechaza borradores parciales de respuestas múltiples;
  `web/whatsapp.py` pide separación y conserva el archivo sin duplicarlo.
- `web/server.py` cierra `web/scheduler.py` desde lifespan antes de cerrar el pool
  de datos; espera los trabajos activos para evitar operaciones después del cierre.

- `src/noesis/db.py`: única frontera de datos. Toda operación de negocio filtra por
  `business_id`. Incluye proyectos, permisos, conciliación, outboxes y entregas a
  gestoría. La recuperación de acceso consume token, cambia credencial y revoca
  sesiones en una sola transacción; pedir otro enlace invalida los anteriores.
- `src/noesis/migrations.py`: esquema SQLite/Postgres. El candidato llega a 55;
  facturación profesional queda congelada al emitir, los límites de autenticación
  son compartidos y la bitácora de seguridad es append-only y encadenada por hash.
  El salto 32 → 33 suspende el guardián de facturas solo dentro del backfill
  transaccional, asigna serie/línea a las emitidas históricas y lo reinstala antes
  de continuar. La 39 separa las cuentas profesionales de gestoría de los usuarios
  titulares y exige una relación explícita y revocable por negocio. La 40 añade la
  marca persistente `is_demo` para bloquear en servidor las empresas ficticias. La
  41 añade un perfil fiscal por negocio, firmado por la cuenta de gestoría que lo
  actualiza, sin convertirlo en una declaración ni en autorización de presentación.
  La 42 amplía el perfil documental y conserva evidencia seudónima de la decisión
  de presupuestos sin alterar facturas emitidas.
  La 43 registra autorizaciones de soporte temporales y acotadas creadas por el
  titular. La 44 añade el libro append-only de costes internos por período. La 45
  separa conexiones, contactos, conversaciones, bandeja y salidas de WhatsApp por
  negocio/número, y añade aportaciones de campo revisables y permisos de equipo. La
  46 conserva el orden de webhooks Stripe por negocio para impedir que un evento
  antiguo sobrescriba el estado de suscripción vigente. La 47 añade MFA de gestoría,
  contador anti-replay, códigos de recuperación y fecha de alta sin modificar
  accesos profesionales existentes. La 48 añade distintivos gráficos al perfil
  documental, versiona la identidad sin duplicar imágenes por factura y congela la
  versión utilizada al emitir, con referencia multiempresa protegida. La 49 guarda
  el punto exacto del alta, el plan y la periodicidad elegidos y diferencia WhatsApp
  verificado de la decisión explícita de conectarlo más adelante. La 50 permite
  suspender una identidad concreta sin bloquear el negocio entero. La 51 separa la
  recuperación de contraseña de gestoría de los usuarios de empresa, con tokens
  hasheados, caducables y de un solo uso. La 52 añade rutas opacas de correo por
  negocio, deduplicación de mensajes sin contenido y propuestas confirmables de
  cliente para documentos. La 53 distingue material y mano de obra en líneas. La
  54 añade un registro observacional de acciones y resultados útiles, relaciones
  multiempresa protegidas, zona horaria y metadatos opcionales de correlación de
  propuestas sin modificar permisos ni flujos. La 55 registra solicitudes de
  privacidad por negocio, impide duplicar una solicitud abierta y separa seguimiento
  de cualquier supresión técnica.
- `src/noesis/value_ledger.py`: taxonomía central v1, escritores fail-open,
  idempotencia, calificación binaria por contexto de delegación, infraestructura de
  ciclo corregido/revertido todavía sin hooks operativos, outcomes muchos-a-muchos,
  WUB móvil y semanal, profundidad, consistencia, aceptación por familia, activación
  y estado conservador de control. No ejecuta acciones ni usa IA para calcular
  métricas.
- `src/noesis/gestoria_workspace.py`: lectura trimestral/anual para despachos;
  reconcilia facturas emitidas, facturas recibidas, gastos y documentos, calcula
  borradores explicables, detecta huecos y candidatos 347, y genera una primera
  página segura de imágenes/PDF para previsualizar sin iframe.
- `src/noesis/demo.py`: siembra dos accesos dentro del producto real —autónomo y
  gestoría—, una segunda empresa para la cartera y un portal de cliente. Rellena
  todos los módulos con datos ficticios conectados, repara de forma idempotente las
  carpetas documentales históricas y no reinicia producción.
- `src/noesis/trades.py`: catálogos por oficio con su IVA por partida, adivinación
  del oficio desde el sector en texto libre y el aviso del 40% de material que hace
  decaer el tipo reducido en obras de vivienda. Avisa; nunca cambia un tipo.
- `src/noesis/whatsapp_templates.py`: espejo comprobable de las nueve plantillas del
  runbook `WhatsApp-Puesta-en-marcha`. Declara nombre, categoría, destinatario,
  cuerpo y número de huecos; `python -m noesis.whatsapp_templates` avisa si un envío
  deja de encajar con lo aprobado en Meta.
- `src/noesis/security_center.py`: responsable CISO interno, determinista y de solo
  lectura; convierte controles, copias e intentos agregados en un parte accionable.
- `src/noesis/db.py` + `routers/admin.py`: diagnóstico privado, autorización de
  soporte con motivo/alcance/caducidad/revocación, alta técnica auditada de números
  comerciales sin tokens, reencolado atómico y auditado de correos agotados sin
  exponer su contenido y CFO observado. Los costes reales, previsiones y ajustes no
  se sobrescriben ni se mezclan.
- `src/noesis/banking.py`: lectura local de CSV bancario, normalización, deduplicación
  y propuestas explicables de conciliación; nunca confirma un pago por sí solo.
- `src/noesis/tools.py`: herramientas que puede invocar el cerebro, aplica los
  derechos del plan antes de consultar o modificar módulos premium y mantiene el flujo común de
  entrega de factura: PDF, canal habitual, email/plantilla WhatsApp, idempotencia y
  evento trazable.
- `src/noesis/fiscal_validation.py`: comprobación local de aritmética de borradores,
  fechas y dígitos de control de NIF/NIE/CIF. Solo genera avisos; no corrige ni
  contabiliza. WhatsApp exige revisión web si encuentra una incoherencia.
- `src/noesis/db.py` + `web/routers/documents.py` + `templates/costes.html`:
  corrección autenticada y multiempresa de facturas recibidas ya confirmadas, sin
  alterar el documento original.
- `src/noesis/documents/ocr.py` + `pdf_ocr.py`: lectura local de imágenes y PDF
  escaneado; detecta modelos Tesseract instalados, prioriza `cat+spa+eng`, prepara
  la imagen y limita páginas, píxeles, tiempo y texto antes de clasificar.
- `src/noesis/documents/inbound_email.py`: consumidor IMAP/catch-all apagado por
  defecto. Resuelve una única ruta opaca, no conserva cuerpo/remitente/asunto,
  deduplica el mensaje y entrega cada adjunto al servicio documental común. Incluye
  CLI de configuración, prueba `.eml` y sondeo de red sin mostrar credenciales.
- `src/noesis/verifactu.py`: huellas de alta y anulación, QR y XML nativos validados
  contra los XSD AEAT.
- `src/noesis/verifactu_client.py`: SOAP/mTLS directo, endpoints oficiales para
  certificado ordinario o sello, TLS mínimo, límite de respuesta e idempotencia de
  duplicados.
- `src/noesis/nlu.py`: cerebro local para órdenes rutinarias sin coste de LLM;
  separa ticket de gasto de ticket de venta F2, entiende importes españoles y
  altas explícitas de cliente/proveedor, y deriva usuarios a invitación segura.
- `src/noesis/internal_brain.py`: compositor local de comunicaciones. Usa hechos del
  negocio, evita ambigüedad y deja el envío pendiente de SÍ/NO del titular.
- `src/noesis/agent.py`: agentes privado, compatible y Anthropic con historial, recuerdos
  confirmados, permisos efectivos y contexto del negocio.
- `src/noesis/adapters/ai.py`: cliente stdlib OpenAI-compatible compartido por el
  servicio privado y el proveedor externo barato.
- `src/noesis/readiness.py`: diagnóstico de piloto sin secretos para seguridad,
  identidad legal, dominio canónico, apertura pública, audio/OCR, datos, copias,
  WhatsApp, correo, Stripe, AEAT, IA y operaciones. Al abrir el alta pública,
  servicios críticos incompletos pasan de aviso a bloqueo.
- `src/noesis/integration_check.py`: comprobación externa segura y de solo lectura.
  Valida el runtime OCR y, opcionalmente, consulta por `GET` Brevo, Google OpenID,
  los seis precios Stripe y el catálogo Groq sin enviar, cobrar ni revelar secretos.
- `src/noesis/production_check.py`: puerta posterior al despliegue, sin credenciales.
  Contrasta desde Internet release, esquema, cabeceras de seguridad, sitemap,
  indexabilidad, H1/canonical y ausencia de marcadores legales; agrega todos los
  fallos en una sola ejecución para que soporte no dependa de revisar URL por URL.
- `.github/workflows/production-smoke.yml`: ejecuta esa puerta cada seis horas y a
  demanda. Es detección periódica, no un sustituto de monitorización 24/7 externa.
- `src/noesis/config.py` + `web/routers/webhooks.py`: toman una huella publicable del
  commit de Railway (o `NOESIS_RELEASE_ID`) y la exponen en `/health`; `/ready`
  añade el esquema aplicado para distinguir sin ambigüedad fusionado de desplegado.
- `deploy/local-ai/`: Ollama privado ligado a localhost y perfil de descarga de
  Qwen3 8B para evaluación; no expone el modelo ni lo convierte en un SLA.
- `analysis/build_unit_economics.mjs`: genera el modelo editable de costes, márgenes,
  escala, sensibilidad de IA y controles; fuente narrativa en
  `docs/06-negocio-y-finanzas/Analisis-unit-economics.ipynb`.
- `docs/project-state.json`: fuente de verdad legible por máquinas para versión de
  esquema, pruebas, precios, publicación, política de suscripción y validaciones
  externas pendientes.
- `docs/Registro-cambios.md`: bitácora obligatoria por modificación; relaciona
  objetivo, áreas tocadas, validación, riesgos y diagnóstico/rollback.
- `scripts/check_project_truth.py`: compara esa fuente con migraciones y catálogo;
  en CI exige actualizar estado y QA cuando cambia el producto.

## Marca y materiales públicos

- `branding/BRAND_GUIDE.md`: nombre, posicionamiento visual, variantes del logo,
  zona de seguridad, tamaños mínimos, paleta, tipografía, fotografía, voz y uso en redes.
- `branding/sources/`: símbolo maestro y lockups SVG con la Fraunces ya autoalojada
  por Bynoesis; son los originales para impresión, edición o exportación futura.
- `branding/logos/png/` y `branding/social/`: exportaciones transparentes, con fondo,
  avatares y portadas listas para cada superficie. El avatar de redes es una adaptación
  específica —estrella ampliada, interior original y contorno solo exterior sobre
  verde bosque— y no reemplaza el símbolo maestro ni el icono de la app.
- `branding/templates/`: fondos SVG editables y PNG para cuadrado, vertical de feed
  y story/reel, en crema y verde bosque.
- `branding/redes-sociales/`: paquete operativo por canal con los PNG que se deben
  subir, textos listos para copiar, controles de seguridad, guía Word renderizada y
  archivos de reserva para YouTube/TikTok. No se carga en el runtime de la aplicación.
- `branding/contenido/Plan-editorial-y-guiones-Bynoesis.docx`: manual operativo de
  contenido con 24 fichas, campañas, calendario, producción, medición y límites.
- `branding/contenido/scripts/build_content_playbook.py`: fuente reproducible del
  manual editorial; usa la identidad existente y no forma parte del runtime.
- `branding/scripts/build_brand_assets.mjs`: generador determinista con Sharp; crea
  exportaciones y `manifest.json` con dimensiones, uso y SHA-256. Su dependencia
  queda aislada en `branding/package.json` y no entra en el runtime de Bynoesis.

## Web y acompañante

- `src/noesis/web/routers/pages.py`: además de las páginas públicas sirve
  `robots.txt`, `sitemap.xml`, `llms.txt` y `/favicon.ico`. `llms.txt` es la ficha
  en Markdown para asistentes de IA: se genera con `adapters/billing.PLANS`, el
  contacto público y el estado del alta, no lleva `noindex` y no cuenta como visita.
  Las 16 preguntas de `/preguntas` salen de `public_marketing.question_groups`,
  la misma fuente que su FAQPage. La lista `_INDEXABLES` decide qué
  ve un buscador: si se añade una página pública, hay que incluirla ahí. El sitemap
  solo declara URLs demostrables; no inventa `lastmod` ni prioridades. Las reglas
  privadas de robots usan `/` final o `$`: `/gestoria` sin ancla bloquearía también
  la página pública plural `/gestorias` por coincidencia de prefijo.
- `src/noesis/web/templates/404.html`: dirección inexistente con el diseño del
  sitio. El manejador de `server.py` sigue devolviendo JSON bajo `/api/` y
  `/webhook/`, que esperan datos y no una página.
- `src/noesis/web/server.py`: ensamblador FastAPI, seguridad, redirección al origen
  canónico y routers. Su middleware añade `X-Robots-Tag: noindex, nofollow` a toda
  ruta que no pertenezca explícitamente al sitio público, excepto assets técnicos.
- `src/noesis/web/templates/site_base.html`: estructura compartida del sitio público,
  navegación responsive, llamada final y pie legal. Home, Precios, Equipo y Preguntas
  usan composiciones propias según su objetivo, sin replicar el panel interno ni
  inventar prueba social. También la usan las seis páginas legales: están en el
  sitemap, así que alguien puede aterrizar en ellas desde un buscador y debe encontrar
  el menú del sitio. Cada página aporta su título y su descripción; los textos legales
  además vacían la llamada final, porque no son sitio para vender. Aquí viven el
  canonical, metadatos Open Graph/Twitter y el salto al contenido por teclado. La
  ficha `Organization`/`WebSite` se inyecta solo en la portada desde `web/deps.py`.
- `src/noesis/web/templates/site_autonomos.html` y `site_gestorias.html`: páginas
  públicas por audiencia; explican los flujos existentes y sus límites sin duplicar
  el panel ni prometer presentación fiscal, movimientos de dinero o comisiones.
- `src/noesis/web/templates/landing.html`: la maqueta del producto reproduce pantallas
  del panel con `h2.demo-title`, no con `<h1>`: dentro de la portada son el retrato de
  una app, y competirían con el único encabezado real de la página.
- `src/noesis/web/templates/site_equipo.html`: página pública de equipo y principios;
  explica responsabilidades reales sin atribuir personas, clientes o credenciales
  todavía no verificadas.
- `src/noesis/web/templates/site_contacto.html`: contacto y reserva mediante enlace
  externo consciente. Cal.com no se incrusta ni se carga por visitar Bynoesis; la CSP
  mantiene `frame-src 'none'` en todas las rutas.
- `src/noesis/web/templates/solicitar_acceso.html`: formulario público de solicitud de
  acceso. Producto se fusionó con la portada, que conserva las anclas `#como-funciona`
  y `#cumplimiento-legal` a las que redirigen los enlaces antiguos.
- `src/noesis/web/static/public-site.js`: hace navegable la cuenta simulada de la
  Home y sincroniza el selector mensual/anual, sus importes, ahorro, CTA y campos de
  checkout sin tocar datos reales.
- `src/noesis/adapters/billing.py`: catálogo mensual/anual y matriz central de
  derechos. Stripe usa un `price_id` distinto por plan y periodicidad; el anual
  cobra 11 meses y da 12. Autónomo conserva el núcleo y Negocio/Premium habilitan
  Proyectos, Equipo, Gestoría y Análisis avanzado. El adaptador también puede leer
  una suscripción concreta por API y convertirla en evidencia solo si coinciden
  negocio, cliente, suscripción, estado activo y un precio conocido de Bynoesis.
  Para una cuenta activa crea sesiones efímeras del portal general o deep links
  acotados a tarjeta, cancelación y confirmación del precio exacto; si Stripe aún no
  permite un flujo específico, cae al portal general sin crear un Checkout. Antes
  prepara una configuración versionada propia del Customer Portal, reutilizable y
  con las seis tarifas conocidas, para no depender de opciones manuales del panel
  de Stripe; una configuración ajena nunca se adopta por accidente.
- `src/noesis/web/deps.py`: aislamiento de sesión, modo consulta, derechos por plan y guardia CSRF
  transversal. Una cuenta inactiva puede leer; toda mutación web/API devuelve
  redirección o HTTP 402. La evidencia `Sec-Fetch-Site: same-origin` del navegador
  tiene prioridad sobre el `Host` privado de Railway; sin ella, `Origin` pasa por
  la allowlist pública estricta y `cross-site` nunca se acepta.
- `src/noesis/web/routers/webhooks.py` + `db.apply_stripe_subscription_event`:
  Checkout solo vincula ids; la activación exige factura pagada o suscripción
  `active`/`trialing`. El bloqueo de fila, orden persistente y comprobación de
  customer/subscription rechazan duplicados, cruces y eventos atrasados. Un
  Checkout concurrente nunca rebaja un estado ya activo; la vuelta del pago puede
  reparar una entrega perdida consultando Stripe de forma autenticada mediante
  `db.reconcile_stripe_subscription`, sin confiar en la URL ni en el navegador.
- `web/templates/suscripcion.html` + `web/routers/account.py`: una cuenta activa
  distingue el plan actual, niveles incluidos y mejoras. No contiene Checkout;
  gestionar, cambiar tarjeta, mejorar o cancelar abre una sesión Stripe distinta y
  la interfaz bloquea dobles envíos y explica un fallo en el mismo bloque visible
  sin fingir que se ha aplicado nada; el servidor lo registra para soporte. La
  ruta de Checkout repite esta protección en servidor ante formularios antiguos o
  peticiones manipuladas.
- `src/noesis/web/routers/assistant.py`: conversación, memoria, permisos y registro
  de acciones de Bynoesis.
- `src/noesis/web/chat.py`: parte del día, plan operativo y acompañamiento. Resuelve
  por reglas, después por IA privada, proveedor compatible y Anthropic; los niveles
  externos comparten consentimiento y un crédito por mensaje.
- `src/noesis/web/templates/base.html`: capa persistente de Bynoesis: lectura real de
  la sección, siguiente paso con motivo, preguntas contextuales y conversación.
- `src/noesis/web/routers/projects.py`: proyectos, trabajos vinculados, tareas,
  equipo, horas y costes. `db.py` limita el avance a 0–100 y separa finalizados y
  cancelados del resumen activo sin borrar su historial.
- `src/noesis/web/routers/portal.py`: portales privados de cliente, gestoría y
  trabajador; incluye parte de campo y conformidad.
- `src/noesis/db.py`: `job_materials`, `job_updates`, `job_completions` y
  `client_preferences` conectan trabajo, coste, evidencia, borrador y aprendizaje.
- `src/noesis/web/templates/proyectos.html`: resumen progresivo y detalle operativo.
- `src/noesis/web/templates/fichaje.html`: jornada, trabajos y checklist personal.
- `src/noesis/web/routers/invoicing.py` + `templates/facturas.html`: editor de
  borradores con líneas e impuestos, series, recurrencia, duplicación, emisión,
  PDF, entrega durable, historial, anulación confirmada y rectificación guiada por
  diferencias. `db.py` conserva el original, bloquea borradores rectificativos
  duplicados, valida F2/R5 y permite revisar el ajuste solo antes de emitir.
- `src/noesis/web/invoice_pdf.py` + `templates/ajustes.html` +
  `templates/presupuestos.html`: facturas y presupuestos comparten marca y pie. El
  editor sanea logo y distintivo, controla tamaño, alineación y alcance, ofrece una
  muestra inmediata y un PDF no fiscal; la factura emitida reproduce su versión
  congelada. El presupuesto añade condiciones, validez, notas y PDF; el portal
  guarda evidencia de la decisión y solo la aceptación prepara un borrador.
- `src/noesis/gestoria_workspace.py` + `routers/documents.py` +
  `templates/documentos.html`: archivo documental común para titular y gestoría.
  Deriva fecha efectiva, período y grupo una vez; el panel normal añade navegación,
  entrada rápida, carpetas responsive, búsqueda, revisión y primera página privada
  bajo demanda sin duplicar ficheros. Proyecta también cada factura como PDF
  reproducible desde su registro contable; un original ya vinculado sustituye esa
  proyección para que siempre exista una sola representación.
- `src/noesis/web/routers/account.py`: alta por prueba o contratación, sesión,
  Google OAuth, configuración operativa, checkout y cuenta. El recorrido se reanuda
  en el paso exacto, incluye la identidad completa de facturas y termina en una
  revisión que no confunde un código de WhatsApp enviado con una conexión verificada;
  el alta pública falla
  cerrada en producción si falta identidad legal o autorización explícita y no
  expone el diagnóstico de proveedores en la API del cliente. La solicitud pública
  distingue también un despacho profesional sin crearle una cuenta ni permisos.
  La baja borra directamente solo si no hay conservación obligatoria; con facturas
  o jornada crea una solicitud idempotente, avisa por la outbox y deja evidencia en
  la bitácora sin fingir que los datos ya se han suprimido.
- `src/noesis/web/routers/pages.py` + `templates/access_entry.html`: `/acceso` es la
  puerta pública única. Deriva autónomo/empresa al login titular y gestoría a su
  identidad profesional separada; un cliente final conserva el portal por enlace.
- `src/noesis/web/templates/onboarding_preferences.html`: aplica fiscalidad,
  identidad visual completa de factura, cobro, recordatorios, informes y gestoría
  antes de entrar al producto; `whatsapp_connect.html` resume lo elegido y permite
  verificar el canal o posponerlo de forma explícita.
- `src/noesis/web/routers/account.py` (`/solicitar-acceso`) + tabla `access_requests`:
  recoge la solicitud pública con su plan de interés, valida, limita repeticiones por
  correo y descarta robots con un campo señuelo. No crea ninguna cuenta.
- `src/noesis/web/routers/admin.py` + `templates/admin.html` +
  `templates/admin_account.html`: diagnóstico técnico,
  parte CISO y evidencia de seguridad reservados al fundador; audita acceso y
  descarga de copias sin guardar contenido de clientes. Desde aquí se aprueban las
  solicitudes: el alta crea el negocio, arranca la prueba ese día y devuelve un
  enlace de un solo uso —reutiliza `password_resets`— para que el titular elija su
  contraseña, de modo que el equipo nunca llega a conocerla. También resume las
  visitas de la web del último mes. La bandeja `Privacidad y bajas` muestra las
  solicitudes abiertas y exige una nota para cada cambio de estado; el estado es
  seguimiento administrativo y nunca dispara un borrado. La ficha técnica por cuenta llama a
  `db.admin_support_snapshot`: solo devuelve estados y recuentos, nunca contenido
  operativo, y registra cada consulta en la bitácora encadenada. Si el titular abre
  el alcance temporal `document_metadata`, `db.admin_support_document_metadata` y
  `db.admin_update_document_metadata` habilitan únicamente tipo, estado, cliente,
  proyecto y nota de revisión. La escritura revalida autorización e IDs dentro de
  la transacción, bloquea vínculos con facturas emitidas y registra antes/después
  sin guardar la nota en claro; nunca crea una sesión suplantada ni un editor
  universal. Con el alcance `configuration`,
  `db.admin_support_configuration` y
  `db.admin_update_safe_business_configuration` exponen y corrigen solo perfil,
  idioma/nivel y apariencia documental futura. La firma de la función no admite
  identidad fiscal, cobros, suscripción, integraciones, tokens ni automatizaciones;
  sus textos quedan seudonimizados en la auditoría.
- `src/noesis/web/server.py` (`_count_public_view`) + tabla `page_views`: suma una
  visita por página y día en el propio servidor, sin script, cookie ni tercero
  —la CSP prohíbe scripts externos—. Guarda solo página, día y dominio de
  procedencia; nunca IP, navegador ni identificador, así que no hay dato personal
  que consentir. Excluye lo mismo que `robots.txt` —panel, API, estáticos y rutas
  de sesión— y si el recuento falla la página se sirve igual: medir es
  información, no funcionalidad.
- `src/noesis/web/templates/ajustes.html`: datos, preferencias, memoria y conexiones
  que el cliente puede usar; no muestra qué proveedor falta o está caído.
- `src/noesis/web/static/app.css`: tokens, componentes y responsive sin CDN.

## Documentos, gestoría y canales

- `src/noesis/documents/service.py`: entrada universal, validación, antivirus,
  huella de contenido aislada por negocio, clasificación y confirmación antes de
  almacenar o contabilizar; una carrera concurrente no deja un fichero huérfano.
  Valida también que cliente, proyecto y factura pertenezcan al mismo negocio y solo
  asocia referencias humanas inequívocas.
- `src/noesis/documents/pdf_text.py`: lectura local de PDF digital con límites de
  páginas, caracteres y streams descomprimidos.
- `src/noesis/documents/pdf_ocr.py` + `ocr.py`: si un PDF no tiene texto útil,
  PDFium rasteriza hasta cuatro páginas con límite de píxeles y Tesseract `spa/eng`
  las lee con timeout; la misma extracción local sirve imágenes de web y WhatsApp.
- `railpack.json`: instala Tesseract y los idiomas de OCR en el contenedor de
  despliegue; `pypdfium2` aporta ruedas precompiladas sin servicio externo.
- `src/noesis/documents/malware.py`: cliente stdlib del protocolo ClamAV INSTREAM;
  escanea en memoria y permite fallo cerrado sin una API externa.
- `src/noesis/documents/repo.py`: metadatos, huellas SHA-256 y vínculos con cliente,
  proyecto, gasto o factura recibida. La migración 38 impone unicidad parcial por
  negocio, permite completar históricos de forma perezosa y busca con parámetros
  solo dentro del negocio activo.
- `src/noesis/web/gestoria.py`: paquete ordenado, manifiesto, huella y versionado;
  en una empresa demo puede generarlo sin registrar una entrega ficticia.
- `src/noesis/web/routers/gestoria_portal.py` + plantillas `gestoria_*`: identidad
  profesional, invitación de un solo uso, cartera multiempresa, preparación por
  trimestre/año, filtros, previsualización, perfil fiscal, borradores de modelos,
  solicitudes y descarga por período. El expediente sirve cinco vistas separadas
  mediante una sección validada en servidor y conserva período/filtro tras cada
  formulario; cada ruta vuelve a comprobar la relación de acceso antes de leer o
  escribir. Incluye recuperación no enumerativa por correo; el cambio atómico de
  contraseña revoca sesiones previas y no desactiva el segundo factor.
- `src/noesis/web/mfa.py`: TOTP estándar con semilla derivada de la identidad y la
  clave maestra, QR local y códigos de recuperación de 80 bits. La base solo recibe
  hashes y el último contador consumido; los códigos en claro no pasan por sesión.
- `src/noesis/web/whatsapp.py`: dos canales sobre la misma frontera durable. El
  número central atiende titular/equipo; los números comerciales se resuelven por
  WABA + `phone_number_id` y atienden clientes dentro del negocio receptor. Incluye
  texto, audio local, fotos/PDF, opt-out, ventana de 24 horas, confirmaciones y
  salidas por la conexión correcta. El trabajador envía costes/documentos/dudas a
  una bandeja revisable; no escribe contabilidad ni ve márgenes globales.
- `src/noesis/web/routers/whatsapp_business.py`: estado del canal comercial,
  activación de recepción solo tras conexión Meta activa, bandeja por negocio,
  respuesta dentro de la ventana permitida y cierre de conversaciones. Las altas
  técnicas de WABA/número no se aceptan desde un formulario de cliente.
- `templates/oficios.html` + `routers/invoicing.py`: la pantalla de plantillas por
  oficio. Muestra cada partida con su IVA, si es material o mano de obra y cuáles
  tiene ya el negocio; carga la plantilla sin duplicar lo existente.
- `scripts/build_estado_xlsx.py`: genera `docs/03-whatsapp-e-integraciones/Estado-Bynoesis.xlsx` leyendo los
  módulos reales, sin dependencias — un `.xlsx` es un zip de XML y se escribe a
  mano. Vuelve a ejecutarlo cuando cambien las plantillas o los catálogos.
- `src/noesis/web/routers/finance.py`: tesorería, conciliación CSV confirmada por el
  titular y calendario ICS privado/revocable.
- `src/noesis/web/backups.py`: copia, restauración descartable, manifiesto documental,
  salida S3 y comando `noesis-restore-check`. Al reconstruir PostgreSQL suspende
  solo los triggers de negocio dentro de la transacción aislada, mantiene
  restricciones/FK y reactiva la inmutabilidad antes de comparar el resultado.
- `src/noesis/web/scheduler.py`: partes, recordatorios, reglas autorizadas y workers
  de outbox. WhatsApp, correo y Veri*Factu se persisten y reintentan; la remisión
  fiscal de altas y anulaciones verifica una cadena común y continúa aunque la
  suscripción SaaS quede inactiva. Ejecuta copia diaria y simulacro semanal.
- `src/noesis/adapters/email.py`: frontera de correo con dos vías. Con `BREVO_API_KEY`
  sale por HTTPS —única forma de que salga correo desde Railway, que bloquea los
  puertos de SMTP—, adjuntos incluidos; sin ella usa SMTP, con SSL directo en el 465 y
  STARTTLS en el resto. Toda comunicación nueva se encola antes de salir para no
  perderla ante una caída del proveedor.
- `src/noesis/adapters/billing.py`: Checkout de suscripción propio sobre la API REST
  de Stripe. Además del precio y metadatos aislados por negocio, solicita dirección,
  NIF fiscal y `automatic_tax`. El catálogo traduce cada `price_id` mensual/anual al
  plan efectivo para que el portal de Stripe no conserve permisos de una metadata
  antigua; las credenciales y el resultado fiscal se validan externamente antes de
  pasar a live.
- `src/noesis/adapters/`: Meta, email, pagos, voz, extracción y fiscalidad detrás de
  fronteras reemplazables. La extracción externa respeta la decisión de IA de cada
  negocio y conserva el clasificador local cuando está desactivada.
