# Registro de QA

## 2026-09-10 — SEO y GEO: nombre único, llms.txt y FAQ de /preguntas

- Contratos nuevos en `test_seo.py`: `/llms.txt` responde Markdown sin
  `X-Robots-Tag`, lista los tres planes con los precios mensual y anual de
  `billing.PLANS`, enlaza las páginas comerciales, no invita a una prueba con el
  alta cerrada e incluye el contacto público; FAQPage de `/preguntas` con 16
  entradas idénticas al `<summary>`/`<p>` visible y sin prometer voz desactivada;
  ninguna ruta de `_INDEXABLES` ni `/llms.txt` contiene «Noesis».
- `/preguntas` añadida al contrato de metadatos, JSON-LD e IDs únicos de
  `test_public_marketing.py`.
- Dirigidas: SEO, marketing público, visitas y comprobador de producción, **36
  pruebas OK**; Node `public_calendar` y `public_marketing` **2/2 OK**.
- Regresión completa sobre `main` combinado con `ecee6b9` (Facturas/Documentos/
  Proyectos del socio): **779 pruebas Python en 198 s, OK**. Ruff, puerta
  documental y `git diff --check` verdes.
- No probado: producción, Bing Webmaster Tools, prueba de resultados enriquecidos
  de Google ni lectura real por asistentes de IA.

## 2026-09-10 — Facturas, Documentos y avance de Proyectos

- Facturas en borrador y emitidas se proyectan en el archivo del mismo negocio y
  trimestre con enlace al PDF original; una factura ajena no aparece.
- Un original subido y vinculado sustituye la proyección virtual en vez de crear
  dos documentos. El portal de gestoría usa la clave de archivo y acepta ambos
  tipos sin asumir un ID físico.
- El servidor rechaza avances menores de 0 o mayores de 100; la interfaz usa un
  `range` 0–100 y estados visibles. Cancelado queda fuera del resumen activo sin
  borrar costes ni historial.
- Pruebas focalizadas: `PlatformTestCase` (29), `ShowcaseAndPdfOcrTestCase` (6) y
  archivo privado del titular (1), verdes. Ruff y `git diff --check`, verdes.
- Regresión completa: **776 pruebas en 575,523 s, OK**. Ruff, detector de secretos,
  Bandit high/high, compilación, puerta documental y `git diff --check`, verdes.
- Navegador real aislado con Edge/Chromium: Documentos mostró 13 filas y 7 facturas
  generadas; Proyectos mostró cinco estados, guardó 73% y mantuvo máximo 100. Sin
  errores de consola ni desbordamiento horizontal a 1440 o 390 px. No se han
  enviado mensajes, facturas ni documentos a proveedores reales; Safari/iPhone
  físico continúa siendo una comprobación de piloto.

## 2026-09-10 — regresión de las frases reales de PDF

- Reproducidas literalmente «Passame el pdf del tiquet» y «No pots enviar el pdf
  per aqui?» contra un ticket emitido: ambas toman la ruta determinista y producen
  un payload Meta `document`, sin respuesta textual inventada.
- Añadida regresión para una respuesta generativa que afirma «No puc generar ni
  enviar fitxers PDF»: la defensa la sustituye por la capacidad y límites reales.
- `WhatsappMediaTestCase`: **19 pruebas, OK**. Regresión completa: **773 pruebas
  Python en 641,095 s, OK**. Ruff, puerta documental, Bandit high/high y
  `git diff --check` verdes. No se llamó a Meta real ni se tocó ninguna cuenta.

## 2026-09-09 — PDF real al titular por WhatsApp

- Caso reproducido: una respuesta de chat podía decir «PDF adjunto» sin realizar
  ninguna llamada de documento a Meta.
- Contratos añadidos: catalán con cliente concreto, seguimiento sin repetir nombre,
  selección aislada por negocio, borrador no presentado como final, fallo del
  proveedor con enlace seguro y eliminación de confirmaciones inventadas.
- La estructura del mensaje sigue el contrato `document` por URL de la Cloud API:
  destinatario individual, HTTPS, filename y caption. Ningún mensaje real se envía
  durante las pruebas.
- Comprobación de producción de solo lectura: OCR operativo; transcripción no
  disponible porque Whisper privado, Groq y motor local están sin configurar.
- Regresión completa: **771 pruebas Python, OK**, además de Ruff, Bandit, estado
  documental y `git diff --check`. Los avisos de proveedor son fallos simulados.

## 2026-09-09 — demostración oscura de la portada

- Entorno aislado en localhost con SQLite temporal. Ninguna cuenta real tocada.
- `test_public_marketing`: 12 pruebas OK. Contratos Node `public_marketing` y
  `public_calendar`: 2 OK. `check_project_truth`: correcto.
- Contraste calculado para cada par de texto y fondo del panel: mínimo 6,37:1,
  todos por encima del umbral AA.
- Captura real a 1280 px en los casos «Factura» y «Cobros». Se detectó y corrigió
  que la cifra de total pendiente era invisible sobre el fondo oscuro.
- Marco: sin scroll horizontal y con márgenes simétricos medidos a 390, 768 y
  1280 px. Orla reducida en móvil para no tocar el borde.
- Pendiente: móvil físico, Safari y verificación en producción tras desplegar.

## 2026-09-09 — publicación y corrección PostgreSQL

`ccb1b54`: Railway SUCCESS; puerta externa OK (14 páginas, esquema 55,
8 cabeceras). CI detecta ProgrammingError por LIKE con porcentaje literal en
page_views_summary. Corrección: patrón parametrizado también en interacciones;
regresión explícita añadida al humo PostgreSQL antes del flujo de privacidad/admin.
El resultado de esa puerta para el hotfix debe verificarse tras su push.

## 2026-09-09 — rediseño público conversacional

- Resultado final: **767 pruebas Python en 616,408 s, OK**, más dos contratos Node.
  Ruff, Bandit y validación del estado verdes. Wheel: 167 archivos y comprobación
  explícita de plantillas, parciales, JS/CSS, WebP y fuente local incluidos.

- Entorno aislado en localhost, SQLite temporal, datos demo y planificador
  desactivado. Ninguna cuenta real modificada; ningún mensaje o reserva enviado.
- Primera suite completa: 764 pruebas, una regresión en el contrato de precios.
  Corregido CTA de registro cerrado; actualizado el selector del nuevo hero y
  restaurada la referencia versionada al gráfico diferido. El contrato vuelve a pasar.
- Contratos públicos: rutas, H1/meta/canonical, JSON-LD/FAQ, enlaces y anchors,
  copia condicionada a servicios, registro cerrado, número público explícito,
  CSP/consentimiento, payload/origen/límite de carga y visitas separadas de eventos.
- Dos contratos Node ejecutan el JS real sin red: secuencias, selección, pausa,
  ocultación, reduced motion, modal, deduplicación y payload mínimo; Cal.com,
  origen/ventana/namespace, altura, reserva simulada y revocación. Ambos verdes.
- Ruff y Bandit (criterio CI high/high), sintaxis JS y `git diff --check` verdes.
  Detector de secretos sin hallazgos nuevos; baseline solo actualiza números de
  línea de CI y fecha, sin añadir excepciones.
- Build wheel correcto con plantillas/assets incluidos; antes los omitía.
  Sin dependencias nuevas de runtime ni migración.
- Navegador: cuatro páginas a 320/390/768/1440 px sin scroll horizontal global.
  Menú/teclado, modal, panel original y pestañas Facturas/Dinero; calendario real con
  horarios y sin desbordamiento interno medido. Audio/OCR visual simulado a 320 px
  sin recortes. Sin errores de consola en las rutas revisadas.
- Administración local: una visita y una interacción de inicio de demo, separadas
  en Marketing. Servidor administrativo de prueba cerrado tras validar.
- Comparación de Autónomos/Gestorías antes y después al mismo ancho: WhatsApp y
  resultado pasan al primer bloque. CTAs según configuración de cada entorno, no
  prueba A/B de conversión. Capturas: `docs/qa/redesign-2026-09-09/`.
- Límites: no CrUX/Core Web Vitals de campo, Safari físico, proveedor de voz/OCR/Meta
  ni reserva/correo reales. No certificar WCAG o legalidad con esta revisión local.
  Sin push ni deploy. Detalle: [[Rediseño-web-2026-09-09]].

## 2026-09-09 — vinculación de WhatsApp bloqueada por identidad de equipo

- Reproducido en base temporal: con el teléfono del titular dado de alta en una
  ficha de Equipo, `BYNOESIS <código>` fallaba con el mensaje genérico y el
  código quedaba consumido. Confirmado en producción por la conversación del
  founder: el mismo número recibía antes la respuesta del canal de equipo.
- Pruebas nuevas: el mensaje nombra al trabajador y la pantalla donde se
  arregla; quitado el teléfono de la ficha, el mismo código vincula. Segundo
  caso: número que ya es el WhatsApp de otro negocio, se nombra ese negocio y no
  se toca el estado del que pide la vinculación.
- Suite completa tras integrar el remoto: **755/755** en 201,5 s (SQLite y
  proveedores simulados). Ruff correcto sobre src, tests y scripts.
- Panel: la consulta encuentra la ficha de Equipo que no aparece en Cuentas,
  liberar deja `phone_norm` a NULL, sin sesión devuelve 303 a login y quedan los
  eventos `admin.whatsapp_identity_viewed` y `..._released`.
- `scripts/whatsapp_identidad.py` probado en lectura contra la base local (ficha
  de equipo encontrada y número libre). Recorrido completo simulado en base
  temporal: bloqueo con motivo, liberación y reconexión con el mismo código.
  `--liberar` no ejecutado en producción.
- Límites: sin Meta real, sin Postgres de producción y sin envío de mensajes.

## 2026-09-08 — integración completa previa a producción

Se reconciliaron sobre `origin/main` los cambios de Facebook del socio, el bloque
local de administración/copias/fiabilidad y las capas opcionales de revisión,
Whisper privado y aprendizaje supervisado. Conflictos resueltos conservando tanto
la relectura de fotos repetidas como la distinción entre factura emitida y recibida
sin borrador válido.

Pruebas dirigidas de mayor riesgo: **107/107** en 68,272 s. Suite completa final:
**752/752** en 594,109 s sobre `src` explícito en PYTHONPATH. Ruff completo,
compilación, JSON, verdad de proyecto y `git diff --check` correctos. Una primera
ejecución completa terminó con un `HealthCheck.too_slow` de Hypothesis al generar
datos (752 tests, 690,895 s); la propiedad fiscal aislada pasó en 11,404 s y la
segunda suite completa pasó. No se ocultó ni suprimió el control.

Las trazas de Stripe, Meta, correo, AEAT, telemetría, backup y extracción son fallos
inyectados por las pruebas y no llamadas reales. Sin PostgreSQL, dispositivos,
proveedores ni credenciales reales en esta validación. Esquema permanece en 55.
Detector de secretos sin hallazgos tras revisar y marcar cuatro falsos positivos;
Bandit sin incidencias de severidad/confianza altas y `pip-audit` sin vulnerabilidades
conocidas (el paquete local `noesis` no existe en PyPI y se omite como tal).

Después del push, Railway marcó SUCCESS y sirvió `086039e0b538`; `/health` y
`/ready` correctos con esquema 55. Puerta externa: 14 páginas y 8 cabeceras.
Flags de revisión, aprendizaje y ledger comprobados apagados. GitHub CI completo:
tests/migraciones y humo PostgreSQL/rollback correctos.

## 2026-09-08 — aprendizaje supervisado y diálogo guiado (local)

19 pruebas nuevas de aprendizaje pasan (15,632 s): sin aprendizaje silencioso,
oferta solo tras éxito, actor/negocio, rechazo de órdenes peligrosas, caducidad,
olvido, firma de interpretación alterada, exclusión del prompt privilegiado,
telemetría sin contenido, fallo de telemetría sin repetir, flags legacy,
WhatsApp sintético y factura guiada con ambigüedad e IVA incluido.

Humo adicional con servidor ASGI/TestClient y sesión sintética: login 303,
desconocido/corrección/SÍ/APRENDER/reutilización/NO 200 y un único gasto;
informe propio 200 y ajeno 403; factura guiada de 121 euros confirmada 200.
No se ha probado entrega Meta, modelo externo, móvil físico ni PostgreSQL.
Ruff, compilación y diff sin incidencias. Sin cambios de esquema ni producción.
Suite completa final: **702/702**, 531,594 s, sobre este `src` explícito en
PYTHONPATH; incluye también el ajuste final F2 del candidato anterior.
Los errores de proveedores/telemetría visibles corresponden a fallos inyectados;
no hay aserciones fallidas. Verificador de estado/esquema/precios correcto.

## 2026-09-08 — confirmación persistente y voz privada (local)

Suite completa final: **683/683**, 497,572 s sobre este `src` explícito en PYTHONPATH.
Después de esa suite, revisión fiscal final: el IRPF por defecto de F2 se conserva
a cero como en la herramienta original; ampliada regresión y repetidos los 33
tests de confirmación/voz. La suite completa precede a este último ajuste acotado.
Ruff, compilación, verdad del proyecto y `git diff --check` correctos.
Los 33 tests nuevos cubren órdenes negativas/destructivas,
impuestos, cliente/cita, ambigüedad, corrección, caducidad, actor/canal/negocio,
SÍ concurrente, IA con varias herramientas, gastos sin asociación inferida,
datos desactualizados y suscripción revocada. HTTP de audio y webhook WhatsApp
sintéticos; servicio privado con clave, límites, ocupado, timeout y limpieza.

Humo adicional del servidor completo mediante TestClient y sesión real sintética:
login 303; propuesta, confirmación, audio multipart y descarte 200; otro negocio
403; páginas Asistente y Suscripción 200. Solo el texto transcrito se simula en
ese humo; la inferencia real se comprueba separadamente por HTTP más abajo.
La suite emite errores inyectados de proveedores y un aviso de tarea del scheduler
contra una BD temporal ya sin tabla de outbox al final. No falla ninguna aserción;
conviene mejorar el aislamiento del scheduler del harness. No es evidencia de una
incidencia de producción. Deprecación de httpx/TestClient pendiente del harness.

Primera suite: dos regresiones repetidas por herencia (IRPF del 2T y concepto
«cambiar el termo»), corregidas y dirigidas en verde. Fixture WhatsApp corregido
con vinculación real de pruebas, sin saltar el control de identidad.

Whisper 1.2.1, venv temporal, modelo small real y audio SAPI español sintético.
MKL Windows falló; CT2_USE_MKL=0 permitió transcribir en 10,69 s. Servicio HTTP real
con adaptador y proceso aislado: health 200, texto en 7,92 s. «IVA» confundido con
«y va»: regresión de rechazo añadida. No acredita precisión ca/es real, Meta,
Linux ni producción. No compras ni cambios externos. Detalle y rollback: runbook.

## 2026-09-07 — simulación de cliente y correcciones de fiabilidad

- Corpus de 23 mensajes de autónomo, incluido dictado acentuado, importes sin
  moneda, `1.250,50`, orden inverso, altas y consultas: todos tienen ruta local
  determinista y no consumen créditos.
- Recorrido sintético completo: cliente, proveedor, factura, presupuesto, agenda,
  gasto, resumen, IVA, cartera y cobros. Con dos clientes «Sergio», la operación se
  detiene y no crea factura ni cliente duplicados.
- Facturas: incoherencias de cuota, total, fechas y NIF generan revisión y limitan
  confianza; caso coherente conserva la confianza original.
- Factura recibida: corrección, aislamiento entre negocios, botón y `PATCH`
  autenticado verificados. Foto repetida: una sola fila/archivo, segunda lectura y
  respuesta sin id interno. Calendario: `VTIMEZONE` presente y aislamiento intacto.
- Pruebas dirigidas: 28 correctas. Suite completa: **650/650** en 604,156 s.
  Ruff, compilación y `git diff --check` correctos. Bandit no estaba instalado en
  este entorno aislado; la puerta de CI debe ejecutar el extra de seguridad.
- Límites: bytes, facturas y conversaciones sintéticos; sin Meta, OCR/modelo,
  calendario físico, correo, Stripe ni producción. No certifica precisión de
  extracción sobre documentos reales.

## 2026-09-07 — release acotada del centro de mando

- Suite completa del snapshot aislado: **644/644**, 531,053 s, SQLite y
  proveedores simulados. Código seleccionado idéntico al snapshot probado.
- Cuatro pruebas propias de administración: aislamiento del consumo, coste
  desconocido, períodos inválidos, hipótesis FX, autorización HTTP y teléfono
  vinculado, siete departamentos y estados sin costes.
- Ruff sobre src/tests, Bandit alto riesgo/confianza, detector de secretos de los
  archivos nuevos/relevantes, sintaxis JS y diff: correctos.
- Navegador local con datos sintéticos: escritorio y 390 px, comparación antes/
  después de Finanzas al mismo tamaño, menú plegable, sección activa, búsqueda
  sin tildes/sin resultados y recarga real conservando departamento. Sin errores
  de consola en la revisión. Las acciones administrativas conservan sus forms.
- Fuera de esta release: copias/WhatsApp/extracción/paginación y otros candidatos
  locales. Sin migraciones. Safari físico, Postgres y proveedores reales no
  quedan certificados por estas pruebas. Evidencia y rollback en
  `Admin-centro-mando-release.md`.

## 2026-09-07 — administración por departamentos, candidato local

- Suite completa: 668/668 en 493,461 s, SQLite y proveedores simulados.
- Repetición final dirigida: 48/48 en 51,454 s (`test_admin_usage` y
  `AdminCommandCenterTestCase`), tras ajustes finales de textos y validación HTTP.
- Nuevas regresiones: páginas de facturas sin cruces de negocio, filtros y límites;
  hipótesis FX explícita. Pruebas existentes de admin ampliadas con las seis vistas
  y validación HTTP de paginación. Ruff, sintaxis JS y verdad documental: OK.
- Comparación antes/después a 1265×720; navegación de departamentos, ficha y mes
  anterior mediante formulario real en servidor local aislado. La consulta conserva
  `#vista-consumo`. Sin errores JS observados.
- A 390×844: resumen, cuentas, captación, costes, operaciones y privacidad sin
  desbordamiento horizontal del documento; tablas conservan desplazamiento interno.
  Capturas en `qa/admin-2026-09-07/`. Viewport restaurado al terminar.
- Contraste del texto auxiliar reforzado y enlaces anteriores conservados.
  No equivale a auditoría completa WCAG ni a prueba en Safari físico.
- Sin migraciones (55), commit, push ni despliegue. Postgres e integraciones reales
  pendientes; no se han ejecutado acciones contra clientes reales.

## 2026-09-07 — móvil y administración, candidato local

- 57/57 dirigidas: `test_admin_usage`, `WhatsappMediaTestCase` y
  `AdminCommandCenterTestCase`. Incluyen ocho nuevas regresiones, autorización,
  aislamiento, JSON no-store, teléfono real de la cuenta, fallos de medición,
  baja confianza y factura recibida no extraíble. Sin proveedores reales.
- Ruff de src y nuevas pruebas, sintaxis JS y `check_project_truth.py`: OK.
- Navegador integrado móvil: menú legible, Crear opaco, Escape y foco de retorno.
  Capturas en `docs/qa/2026-09-07/`. Pendiente Safari/iPhone físico y Postgres.
- Suite general: 661/661 en 575 s. Tras añadir cuatro pruebas y ajustar dos guardas
  de WhatsApp, las 57 dirigidas se repitieron sobre el código final: OK.
  Cobertura combinada de 665 pruebas; no es una segunda suite general de 665.
  Sin migración, commit, push ni despliegue. Límites en `Revision-frentes-2026-09-07.md`.

## 2026-09-06 — presupuesto offline

- `tests.test_backup_cost_estimate`: 4/4, sin runtime ni credenciales; Ruff y CLI OK.
- 1 GiB/30 juegos: 0,69 + 0,0003 + 1,610612736 = 2,300912736 USD/mes.
- Sin borrado suma 365 juegos al año, no 30. Tamaño y factura reales pendientes.
- No se repite suite general: 653 es la última ejecución, no el recuento ampliado.

## 2026-09-06 — recuperación y revisión conservadora (candidato local)

- Primera suite general: 648 pruebas, 647 correctas y un error Windows al eliminar
  una BD temporal ocupada. Se observaron tareas del scheduler después del cierre
  de clientes de prueba. No se considera verde esa ejecución.
- Corrección: cierre de la aplicación detiene el scheduler esperando trabajos en
  curso y libera su referencia. Se añade regresión de cierre repetido.
- Regresiones dirigidas iniciales: 18/18 backup/CISO y 25/25 integración/WhatsApp;
  tras checksum S3 y plantilla, 23/23 backup/CISO/guardas. Proveedores simulados,
  restauración SQLite temporal real y ruta HTTP admin probada. Sin tráfico de negocio.
- Ruff, Bandit (umbrales CI), diff-check y verdad del proyecto correctos.
- Suite general final: **653/653 correctas en 533,180 s**, Python 3.12 Windows,
  entorno sin `.env` y BD predeterminada temporal. No se repitió el bloqueo Windows.
  Ciclo independiente SQLite **55→0→55** correcto. Ruff, compilación, Bandit con
  umbrales CI y detector de secretos correctos; `pip-audit` no encontró
  vulnerabilidades conocidas en dependencias instaladas (el proyecto local no se
  audita como paquete PyPI). Esto no equivale a pentest ni a validación productiva.
- Se descartó un intento intermedio al revisar el enlace con lifespan: el cierre
  debe estar en el gestor existente, no en un handler on_event separado. La prueba
  nueva comprueba el orden tareas→pool también ante una excepción. Guardas finales
  aisladas: 6/6. El detector de secretos solo actualizó una línea ya registrada y
  se marcó una URL ficticia de autenticación como fixture; no se añadieron secretos.
- Límites: no PostgreSQL local disponible por CLI; sin CloudFormation real, sin
  bucket creado, sin restauración externa, sin activación de voz ni plantillas Meta.
  No se ha hecho push, ni despliegue, ni cambios sobre producción. La plantilla
  tiene contratos locales, no validación real de AWS. No se certifica seguridad.

## 2026-09-04 — clasificación de un PDF con varias facturas

- **Medición contra el modelo real** (`claude-haiku-4-5-20251001`), con PDF generado
  con tres facturas donde el negocio figura como cliente: **0 aciertos de 6** antes
  del arreglo (todos caían a la heurística con `kind=documento`, confianza 55) y
  **5 de 5** después, con `kind=factura_recibida`, confianza 95 y `method=ia`.
- **Contraste:** un PDF de una sola factura acertaba siempre, antes y después. La
  diferencia no era el reenvío ni el duplicado, sino el número de facturas dentro.
- **Confirmado que el modelo respondía bien todo el tiempo:** la respuesta cruda
  contenía `factura_recibida` con confianza 95 y una explicación correcta; se perdía
  al interpretarla.
- **Límite:** medido con PDF sintético, no con el archivo real del founder, que no
  está en el repositorio. La forma reproducida (lista de objetos) es la que devolvió
  el modelo en las seis llamadas registradas.

## 2026-09-04 — primera conversación real por WhatsApp

- **Circuito completo verificado con el número de prueba y un móvil real:**
  vinculación con código de un solo uso, respuesta del asistente, envío de un PDF de
  3 páginas y guardado en Documentos. Firma, entrega y respuesta correctas.
- **Fallo encontrado en esa prueba:** reenviar el mismo PDF contestaba «ya estaba
  guardado como documento N» y terminaba ahí. Un documento archivado antes de
  configurar la IA quedaba imposible de clasificar por WhatsApp. Corregido.
- **`ANTHROPIC_API_KEY` activada en producción** y verificada de dos formas: la fila
  de Anthropic aparece ya en `/privacidad` (se pinta solo si la clave existe), y una
  llamada real confirma que responden los dos modelos configurados,
  `claude-haiku-4-5-20251001` (clasificador) y `claude-sonnet-4-6` (asistente).
- **`GROQ_API_KEY` sigue vacía a propósito**, según [[RGPD-QUE-HACER]] 1.0: no
  configurarla en producción hasta archivar DPA y garantías. La voz no funciona y esa
  es la conducta correcta hoy.
- **Límite:** no se ha medido todavía el tiempo del webhook con una foto real, que
  sigue siendo el riesgo abierto del canal.

## 2026-09-04 — perfilado del panel y equivalencia fiscal

- **Perfilado con datos reales** (`scripts/profile_panel.py`, base temporal). Con
  60 clientes/150 facturas: 123-246 ms y 22-35 consultas por pantalla. Con
  250 clientes/600 facturas: 292-691 ms **con el mismo número de consultas**. El
  coste crece con el volumen aunque los viajes no: las consultas traen tablas
  enteras y se filtra en Python.
- **Equivalencia fiscal antes/después del cambio en `tax_quarter`.** Cuatro
  trimestres de 2025 con IVA 21/10/21/4, IRPF 15/0/7/15 y gastos trimestrales:
  ingresos, IVA repercutido, soportado, resultado, IRPF del periodo y pagos previos
  **idénticos al céntimo** en los cuatro. Sin este contraste el cambio no era
  publicable.
- **Mejora medida:** `tax_quarter(4T)` de 281,6 ms a 38,8 ms con 400 facturas y
  300 gastos. Pantalla de Impuestos: de 34 a 25 consultas.
- **Prueba de regresión verificada por contradicción:** con el código anterior,
  `test_tax_quarter_reads_each_table_once_whatever_the_quarter` falla con
  «list_invoices se leyó 8 veces, se esperaba 1».
- **Límite:** medido en SQLite sobre Windows. No se ha perfilado contra PostgreSQL
  ni contra producción, donde cada consulta añade latencia de red.

## 2026-09-04 — IVA por el asistente y canal de Meta verificado

- **Canal de Meta, contra la cuenta real.** Token permanente de usuario del sistema
  válido y sin caducidad, con `whatsapp_business_messaging` y
  `whatsapp_business_management`. Número de prueba `+1 555-184-7575` en calidad
  GREEN. Meta tiene registrado `https://bynoesis.com/webhook/whatsapp`, activo y con
  `messages` suscrito. Verificación GET devuelve el challenge; un verify token falso
  se rechaza con 403. **Un webhook firmado se acepta con 200 y una firma falsa se
  rechaza con 401**, así que el `WHATSAPP_APP_SECRET` desplegado es el de Meta. El
  sobre firmado que se manda no lleva eventos y no crea ningún dato.
  Reproducible con `python scripts/check_whatsapp.py`.
- **Límite:** las nueve plantillas no están dadas de alta, así que ningún mensaje
  iniciado por Bynoesis puede salir. No se ha probado todavía una conversación real
  con el número. Meta sirve los campos en `v26.0` y el código pide `v23.0`.
- **IVA por el asistente.** Antes «¿cómo va mi IVA?» resolvía a `resumen_negocio`
  (cifras del mes) y «cuánto IVA tengo que pagar» no resolvía a nada; ninguna de las
  20 herramientas alcanzaba `db.tax_quarter`, así que una pregunta fiscal no tenía
  respuesta correcta posible. Ahora `ver_impuestos` expone el 303 y el 130 del
  trimestre, el cerebro local reconoce la pregunta y extrae trimestre y año.
  Verificado que no hay regresión: «factura a Pepe 500 euros iva 21» sigue creando
  factura y «cuánto llevo facturado» sigue siendo el resumen del mes.
- **Prueba de baja RGPD corregida.** Dependía del entorno: contaba los avisos por el
  prefijo `privacy-request-`, que casa con el del titular y con el interno. Fallaba
  con `NOESIS_ADMIN_EMAIL` puesto y pasaba sin él. Ahora pasa en ambos casos.
- **Batería:** `tests/test_backend.py` completo, **425 pruebas en 1.081,76 s, 0
  fallos**, más 30 de cerebro interno, flujos de campo y multicanal. Total
  recolectado: **633**. El único fallo restante de la tanda completa anterior era un
  `PermissionError` de `tempfile` en Windows, que no se reproduce aislado.

## 2026-09-04 — publicación real y comprobaciones posteriores

- Backup de base y documentos creado/verificado antes del push; restauración
  aislada independiente OK en 3,854 s. Artefactos fijados en
  `/data/backups/predeploy-schema55-20260904`, fuera de rotación.
- Release `4f5e88f071cd`, esquema 55, Railway SUCCESS. Comprobador externo:
  14 páginas públicas y 8 cabeceras, status ok. Accesos demo reales de titular y
  gestoría correctos; cinco pantallas autenticadas del titular en 200.
- Comparación de seis tablas operativas contra la cabecera del backup: recuentos
  idénticos. Cadena de auditoría íntegra. Flags reales: signup=false,
  ledger=false, ledger_admin=false; proveedor legal efectivo correcto.
- Límite: no se ejerció supresión ni se modificaron clientes/facturas reales; la
  solicitud humana con correo y la recuperación fuera de Railway siguen pendientes.

## 2026-09-04 — validación previa a main

- **RESULTADO FINAL:** CI `33855910788` verde en ambos jobs. **629 pruebas en
  275,502 s**, migraciones completas SQLite, PostgreSQL 16 con datos históricos,
  35 rutas, backup/restauración, código anterior 53 sobre BD 55, rollback
  55→54→53→54→55 y flujo RGPD. Auditoría de dependencias sin vulnerabilidades
  conocidas, escáner de secretos, Bandit, Ruff y verdad documental correctos.
- Código probado `fbfa76b7379f6295cb4efac62a2c6bca9e17aaa5`; el cierre posterior
  solo cambia documentación. Ver [[Revision-pre-main-2026-09-04]]. Apto técnicamente
  para publicación controlada, no apertura masiva. Falta autorización del founder
  y copia fresca verificada antes de publicar. Sin push a main ni despliegue.

- **PostgreSQL 16 completo OK:** job de `33855685663`, incluidos migración histórica,
  humo de rutas, restauración de backup, código 53 sobre BD 55, rollback completo y
  flujo RGPD con permisos/concurrencia/exportación/avisos. Solo queda el job general:
  el escáner interpretó el SHA público fijado para rollback como secreto; se anota
  ese valor concreto y se repite, sin desactivar el control.

- Suite local completa terminada: **627 pruebas, OK en 642,162 s**, más las dos
  pruebas nuevas de proveedor efectivo correctas (629 verificadas). El conteo
  previo 618 era incompleto; el CI final contrastará el total con descubrimiento.
- La ruta administrativa HTML rechaza GET y POST mediante 303 a login, no 403;
  el humo verifica ambas redirecciones sin seguirlas. No se altera el permiso.

- Se incorpora compatibilidad del código anterior d3740a0 sobre BD 55 antes del
  downgrade: cliente, factura emitida, cobro y exportación. El script exige base
  local `noesis_ci` y comprueba que está importando el código 53.

- Dos pruebas nuevas pasan para proveedor efectivo: Brevo prevalece sobre SMTP
  residual y SMTP sin API exige identificación. La suite verificada acumulada es
  620; el CI final debe ejecutar las 620 juntas con el lock actualizado.
- Tercer CI: rollback e inmutabilidad PostgreSQL correctos; se ajusta la nueva
  aserción de acceso al contrato existente (GET admin redirige, POST rechaza 403).

- Segunda ejecución: auditoría de dependencias correcta tras pypdf 6.16.1. Se
  verificaron los 49 SHA-256 del branding contra los archivos y se anotan como
  falsos positivos exactos; fixtures fiscales/contraseña se marcan explícitamente.
  El rollback PostgreSQL completó todo el ciclo; la aserción posterior utilizaba
  `emitida` en vez del estado real `enviada`, y se corrige el nuevo test.
- Lectura de configuración Railway sin SSH ni acceso a BD: altas públicas false,
  flags de valor ausentes (default false), S3 ausente, Brevo activo y SMTP presente
  sin nombre/región legales. No se cambió ninguna variable ni se lanzó despliegue.

- Primer CI `33854946594`: bloqueó tres CVE en pypdf 6.15.0. Las migraciones
  históricas y el humo PostgreSQL existente pasaron; el nuevo humo falló porque
  usaba iteración directa sobre el cursor propio. Se corrige con `fetchall()` y
  se actualiza pypdf a 6.16.1; se repite el CI sin ocultar ni excluir los avisos.

- Se prepara ejecución manual del CI desde `codex/review-value-privacy`, sin push
  a main ni PR. PostgreSQL 16 del runner es efímero y no tiene datos reales.
- El nuevo `tests/postgres_release_smoke.py` solo permite `localhost/noesis_ci`:
  valida rollback 55→54→53→54→55, datos históricos e inmutabilidad, baja HTTP,
  conservación, aislamiento, concurrencia, panel admin, exportación y outbox.
- Estado inicial: Ruff, verdad documental y diff correctos. Suite completa y CI
  pendientes de resultado; no constituye aprobación de producción.

## 2026-09-03 — RGPD operativo, transparencia y conservación

- **Regresión:** `python -m unittest discover -s tests -q` ejecutó 615 pruebas en
  529,386 s y terminó `OK`. Después se añadieron las pruebas de la bandeja
  administrativa, del rollback 55→54→55 y de concurrencia, y se ejecutaron
  aisladamente en verde; el conjunto verificado suma 618. Los logs de Meta, AEAT,
  SMTP, backup y ledger son fallos simulados esperados por sus pruebas.
- **Baja y derechos:** se comprobó que una factura emitida impide el borrado directo,
  pero ya no devuelve error: crea una única solicitud, mantiene la cuenta, muestra
  referencia, encola aviso y registra `privacy.account_closure_requested`. El reenvío
  no duplica expediente ni correo. Una nota vacía no permite cerrar la solicitud.
- **Separación de control y ejecución:** el panel admin lista el expediente y permite
  documentar `legal_hold`; la prueba confirma que el negocio sigue existiendo y que
  se añade `privacy.request_status_updated`. Cambiar estado nunca ejecuta supresión.
- **Transparencia web:** `/contacto` no contiene iframe, conserva el enlace externo y
  responde con `frame-src 'none'`; privacidad nombra Stripe, Google, Brevo, Groq y
  Cal.com cuando corresponden; encargado explica el reparto y `/cumplimiento` ya no
  contiene «sistema homologado».
- **Backups:** una configuración S3 con credenciales pero sin región de firma,
  proveedor o residencia devuelve fallo antes de conectar. Integración, centro de
  seguridad y readiness aplican el mismo contrato.
- **Calidad estática:** `python -m ruff check ...`, `py_compile`, JSON,
  `scripts/check_project_truth.py`, `git diff --check` y pruebas específicas de
  backup, seguridad, integración, producción y plataforma quedaron en verde.
- **Límites:** no se usaron credenciales, PostgreSQL externo, Railway ni producción.
  Faltan migración/rollback real, DPA/regiones, validación jurídica de conservación,
  solicitud humana extremo a extremo y simulacro de brecha.

## 2026-09-01 — correcciones de revisión externa del registro de valor

- **Regresión completa:** `py -m unittest discover -s tests -q` ejecutó **570
  pruebas** y terminó `OK`. El primer intento detectó cuatro ejecuciones heredadas
  del mismo test que fijaba el día 2 del mes y fallaba cuando el calendario real era
  día 1; se sustituyó solo esa suposición temporal por la fecha actual y las cuatro
  reproducciones más la suite completa quedaron verdes. No se relajó la protección
  que rechaza fechas de emisión futuras.
- **Delegación WUB:** 20 pruebas específicas del ledger verifican ahora el booleano
  `qualifies_for_wub`. Crear un trabajo mediante DB/formulario conserva telemetría
  `manual_form` pero aporta cero acciones WUB; crearlo mediante `run_tool` del
  asistente sí califica. También califican una regla autorizada, una propuesta
  confirmada y una automatización explícita. La consulta WUB exige simultáneamente
  familia candidata e instancia delegada.
- **Atribución conservadora:** outcomes enlazan como evidencia de Bynoesis únicamente
  acciones con contexto delegado. Los resultados posteriores a operaciones
  manuales siguen registrados, pero con atribución `observed`.
- **Flag y auditoría anterior:** con `VALUE_LEDGER_ENABLED=false`, la prueba real de
  `send_payment_reminders` encola el WhatsApp y conserva exactamente una fila
  histórica de `assistant_actions`, sin campos nuevos ni Useful Actions. Las
  propuestas/decisiones de Trust añadidas por esquema 53 permanecen apagadas.
- **Rollback seguro:** se creó localmente una base limpia en esquema 53 y se ejecutó
  contra ella el código base `294ce375`. Negocio, cliente, trabajo, cierre, factura,
  cobro, presupuesto y auditoría terminaron con
  `LEGACY_CODE_ON_SCHEMA_53_OK`. Esto valida volver primero al código anterior y
  solo después bajar la BD. No se considera soportado código 53 sobre esquema 52.
- **Lifecycle:** la transición aislada continúa cubierta, pero no hay hooks reales
  conectados por proceso. La documentación ya la presenta como infraestructura
  disponible con instrumentación pendiente, no como cobertura operativa.
- **Límites externos:** no se ha consultado ni modificado producción y no se ha
  ejecutado Railway. PostgreSQL no productivo sigue siendo puerta obligatoria para
  migración, smoke, activación opt-in y ensayo de rollback antes de cualquier merge.

## 2026-08-31 — registro de valor, WUB y confianza observada

- **Regresión completa:** `py -m unittest discover -s tests -q` ejecutó **567
  pruebas** y terminó `OK`. Incluye los 13 contratos generativos de seguridad con
  Hypothesis, invariantes fiscales, Stripe, WhatsApp, documentos, permisos,
  backups, SEO, onboarding, facturación y multiempresa. Los mensajes de error del
  log corresponden a fallos simulados que sus propias pruebas esperan.
- **Cobertura nueva:** 17 pruebas específicas comprueban taxonomía y binario WUB,
  idempotencia por negocio, aislamiento, canal/origen/confirmación separados,
  tres acciones y dos procesos, límite lunes-lunes con zona horaria, profundidad,
  consistencia y racha, elegibilidad, lifecycle/reversión, outcomes muchos-a-muchos,
  deduplicación de dinero, atribución conservadora, confianza por correlación,
  feature flag, fail-open, flujos maduros, permisos admin, índice de consulta,
  exportación/borrado RGPD y rollback 53→52→53.
- **Compatibilidad de flujos:** el test integrado recorre creación/cierre de trabajo,
  factura, emisión, cobro, presupuesto, envío y aceptación. El resultado operativo
  se conserva aunque el escritor de métricas lance una excepción.
- **Base de datos:** esquema SQLite limpio alcanza 53; downgrade y reupgrade pasan.
  Los contratos de DDL PostgreSQL —índice único antes de FK compuesta y parámetros—
  pasan en la suite. `tests/postgres_smoke.py` incorpora además idempotencia,
  relación action/outcome y alcance por negocio para ejecutarlos en el entorno
  PostgreSQL no productivo antes del despliegue.
- **Privacidad y seguridad:** el ledger no contiene el texto del trabajo probado;
  la auditoría devuelve 403 a usuario normal, 404 con el flag apagado y solo datos
  internos al administrador con el flag activo. El acceso queda en la bitácora de
  seguridad. Las cuatro tablas forman parte de portabilidad y baja RGPD.
- **Calidad estática:** `py -m ruff check src/noesis tests/test_value_ledger.py`,
  `py -m py_compile` de archivos afectados, `git diff --check`, JSON válido y
  `py scripts/check_project_truth.py` pasan.
- **Límite externo:** no se ha ejecutado el humo contra PostgreSQL real porque el
  único entorno accesible es producción. El candidato no se ha desplegado; esa
  prueba y el rollback son puerta obligatoria en un entorno no productivo.
## 2026-09-01 — fusión de 112 commits y comprobación de que no rompe nada

### Qué se probó y con qué resultado

- **Conflictos:** los siete resueltos a mano. Ningún marcador quedó en el árbol,
  comprobado con búsqueda sobre `.py`, `.md`, `.json` y `.html`.
- **Migraciones:** numeración correlativa y sin duplicados, 53 migraciones,
  `LATEST_VERSION = 53`. La local se renumeró de la 40 a la 53 porque el remoto
  ya ocupaba la 40 con `demo_comercial`.
- **Saneado de plantillas:** un salto de línea se convierte en « · » y un valor
  de 2000 caracteres se corta en 1024, que es el tope de Meta. El tope lo aporta
  la rama local; el separador visible, el remoto.
- **Contrato de plantillas:** los nueve cuerpos declarados coinciden con el
  runbook y con el número de valores que envía el código.
  `python -m noesis.whatsapp_templates` responde «todos los envíos encajan».
- **Plantillas por oficio:** las ocho pruebas siguen verdes sobre el código
  fusionado, incluidas la página y su API.
- **Suite completa:** 577 pasan, 132 subtests. Ruff verde. Fuente de verdad verde.

### Qué no se ha probado

- **Los 5 fallos que persisten son anteriores a esta fusión.** Se reprodujeron en
  un árbol de trabajo limpio sobre `origin/main`, sin nada local: cuatro de
  facturación por mes, que dependen de la fecha del sistema, y uno de
  rasterización de PDF escaneado, que necesita dependencias de OCR ausentes en
  este equipo. No se han corregido porque no son de este trabajo, pero conviene
  mirarlos: si son de fecha, volverán a aparecer solos.
- **Nada contra Meta, Stripe ni la AEAT reales.** Sigue todo sin credenciales.
- **La migración 53 no se ha aplicado a PostgreSQL**, solo a SQLite en pruebas.

## 2026-08-31 — manual editorial y guiones de contenido

- **Cobertura:** 38 páginas con estrategia, audiencia, canales, mapa de 24 piezas,
  guion orientativo, rodaje, texto en pantalla, copy, CTA, métrica y límite para
  cada contenido; añade cinco campañas, calendario mensual, producción y medición.
- **Integridad:** DOCX abre como paquete OOXML válido, con 549 párrafos, 124 tablas,
  una imagen y una sección; el generador conserva una fuente reproducible junto al
  entregable.
- **Revisión visual:** las 38 páginas se renderizaron a PNG y se revisaron sin texto
  cortado, desbordamiento, títulos truncados ni saltos accidentales. Las páginas de
  continuación de mapa, campañas y calendario son intencionadas.
- **Accesibilidad:** cero incidencias altas tras añadir título y descripción al
  logotipo; 39 tablas de datos repiten encabezado. Las 85 advertencias medias son
  fichas de dos columnas y bloques visuales sin fila de encabezado semántica.
- **Verdad comercial:** demos, WhatsApp/Meta, pilotos, testimonios y cifras quedan
  rotulados o bloqueados hasta disponer de validación y permiso. El manual no promete
  automatización fiscal ni resultados comerciales no medidos.

## 2026-08-31 — avatar social sobre verde bosque

- **Alcance:** solo cambia el fondo de los avatares sociales de teal `#2e8b74` a
  verde bosque `#14463b`; símbolo, geometría, contorno exclusivamente exterior,
  portadas, logo maestro e iconos de aplicación permanecen intactos.
- **Integridad:** manifiesto 1.2.2 con 49/49 PNG válidos; las cinco copias operativas
  coinciden por SHA-256 con sus exportaciones de Instagram, Facebook, LinkedIn y
  YouTube.
- **Revisión visual:** comprobadas las exportaciones 1080 × 1080 y 400 × 400 y las
  ocho páginas de la guía Word. El fondo es inequívocamente verde bosque y la estrella
  conserva el interior oficial sin trazos internos.
- **Límite:** la máscara de cada red se comprueba finalmente al crear los perfiles.

## 2026-08-31 — contorno exclusivamente exterior

- **Referencia:** el interior coincide con `sources/noesis-mark-master.svg`: polígono
  exterior teal `#2e8b74`, polígono interior y círculo bosque `#14463b`, y punto
  crema `#f4f1e8`.
- **Diferencia social:** el fondo es teal y solo el polígono exterior incorpora
  `stroke="#15211c"`; el polígono interior y los dos círculos no contienen trazo.
- **Integridad:** manifiesto 1.2.1 con 49/49 PNG válidos; las cinco copias operativas
  coinciden por SHA-256 con Instagram, Facebook, LinkedIn y YouTube.
- **Revisión visual:** comprobadas las exportaciones 1080 × 1080 y 400 × 400. La
  estrella queda centrada, sin placa blanca, con el interior reconocible y sin líneas
  internas añadidas. La guía Word conserva ocho páginas limpias tras render completo.
- **Límite:** la máscara de cada red se comprueba finalmente al crear los perfiles.

## 2026-08-31 — avatar social sin placa blanca

- **Geometría:** estrella centrada al 64 % del lienzo, frente al 29,8 % aproximado
  del avatar anterior; fondo y relleno teal `#2e8b74`, contorno tinta `#15211c` y
  punto crema central. El contenido queda dentro de la zona segura circular.
- **Alcance:** cambian Instagram, Facebook, LinkedIn y YouTube, además de las copias
  listas para subir y la reserva de TikTok. No cambian portadas, SVG maestro,
  lockups ni iconos PWA/app.
- **Integridad:** el generador conserva 49 PNG, manifiesto 1.2, tamaños y alfa; cada
  copia de `redes-sociales/` coincide por SHA-256 con su activo de origen.
- **Revisión visual:** avatar de 1080 × 1080 y versión de 400 × 400 revisados sin
  recortes, placa residual, deformación ni pérdida del contorno en tamaño menor. La
  guía Word actualizada conserva ocho páginas limpias tras el render completo.
- **Límite:** el recorte final dentro de Instagram, Facebook y LinkedIn se comprueba
  al subirlo; la revisión local valida el archivo, no la interfaz futura de la red.

## 2026-08-31 — perfiles sociales listos para configurar

- **Alcance:** Instagram, Facebook y LinkedIn tienen carpeta propia con imagen de
  perfil, portada donde la plataforma la utiliza, descripción exacta y controles de
  publicación. YouTube y TikTok quedan únicamente como reserva de marca.
- **Integridad:** las copias PNG coinciden por SHA-256 con los activos deterministas
  del kit principal; se verifican tamaños 1080 × 1080, 1640 × 856, 400 × 400,
  4200 × 700 y 800 × 800 según su destino.
- **Documento:** la guía Word se abre como OOXML válido, contiene ocho páginas tras
  renderizado y todas fueron revisadas: no hay solapes, cortes, desbordamientos,
  imágenes deformadas ni páginas accidentales en blanco.
- **Contenido:** los textos usan Bynoesis como marca y `@bynoesis` como usuario; el eje
  es tiempo, orden y control. No reaparece el posicionamiento centrado únicamente en
  cobros ni quedan marcadores por rellenar.
- **Límite:** no se afirma que los perfiles estén creados ni que el usuario esté
  disponible. El recorte final, botón, URL, doble factor y segundo administrador se
  validan dentro de cada plataforma por los fundadores.

## 2026-08-31 — corrección del posicionamiento de marca

- **Fuente de verdad usada:** `Plan-maestro-Bynoesis.md` fija «Bynoesis lleva la oficina
  mientras tú haces el trabajo» y `design/PRODUCT_PRINCIPLES.md` fija «Haz tu
  trabajo; Bynoesis te ordena el negocio». Cobros, facturación y margen quedan como
  pruebas concretas, no como territorio único de marca.
- **Exportaciones:** portada LinkedIn 4200 × 700, Facebook 1640 × 856, Open Graph
  1200 × 630 y tablero 1800 × 1200 regenerados con el nuevo eje de tiempo, menos
  papeleo y control. La geometría y los colores del logo no cambian.
- **Integridad:** 49/49 PNG se abren, coinciden con ancho, alto, alfa y SHA-256 del
  manifiesto; 14/14 SVG parsean; dos ejecuciones producen el mismo manifiesto.
- **Revisión visual:** tablero y portada de LinkedIn no presentan recortes,
  deformación, solapes ni pérdida de legibilidad. El PDF de estrategia conserva 13
  páginas limpias tras sustituir la tesis y la jerarquía de mensajes.
- **Dependencias:** `sharp` 0.35.4 en el paquete aislado de construcción; `npm audit`
  informa cero vulnerabilidades. No se añade ninguna dependencia al producto.
- **Límite:** el lenguaje maestro está alineado; ejemplos, campañas y contenido
  futuro deberán aportar evidencia real de tiempo, tareas, facturas, documentos,
  margen o dinero sin confundir una prueba con toda la promesa.

## 2026-08-31 — paquete de marca y exportaciones sociales

- **Alcance:** se conserva la geometría de `noesis-mark.svg` y se formalizan símbolo,
  wordmark, lockups primario/inverso/monocromo, versiones transparentes, composiciones
  con fondo, avatares, portadas y fondos editables para contenido.
- **Exportación:** el generador produjo 49 PNG y originales SVG con Fraunces
  autoalojada. `manifest.json` registra dimensiones, presencia de alfa, finalidad y
  SHA-256 de cada PNG.
- **Pruebas técnicas:** todos los PNG se abrieron con Sharp y coincidieron con sus
  dimensiones declaradas; todos los SVG se parsearon como XML; los archivos sociales
  quedan por debajo de 3 MB y la regeneración completa terminó sin error.
- **Revisión visual:** tablero general a 1800 × 1200, lámina de paleta a 1600 × 1000,
  avatar a 1080 × 1080 y portada LinkedIn a 4200 × 700 revisados sin recortes, texto
  perdido, fondo accidental ni deformación del símbolo. El avatar mantiene margen
  suficiente para máscara circular.
- **Límite:** no se ha subido nada a redes ni se ha observado el recorte real de cada
  plataforma. Esa comprobación se hace al crear los perfiles; si una interfaz cambia,
  se ajusta la composición social, no el logo maestro.

## 2026-08-27 — catch-all documental e identidad segura de clientes

- **Alcance:** migración 52, consumidor IMAP apagado por defecto, dirección opaca
  de 128 bits por negocio, deduplicación durable sin contenido, scheduler acotado y
  entrada por el mismo servicio que Web/WhatsApp. La pantalla Documentos solo muestra
  la dirección cuando la integración está habilitada y completa.
- **Aislamiento y privacidad:** mensajes sin ruta, con ruta desconocida o con dos
  rutas fallan cerrados. No se persisten remitente, asunto, cuerpo ni correo original;
  el export RGPD omite token y huella, y el borrado de negocio cubre las tablas nuevas.
- **Clientes:** una factura emitida reutiliza una coincidencia exacta por NIF o nombre;
  una identidad nueva queda pendiente. El titular puede corregir nombre/NIF antes de
  confirmar el alta y el enlace al documento dentro de una transacción. La creación
  explícita de facturas también prioriza NIF para no duplicar un cliente habitual.
- **Fallo seguro:** validación, límites, malware, OCR y clasificación son compartidos.
  Si ClamAV es obligatorio y no responde, el correo queda para reintento; no se marca
  como leído ni se archiva sin escaneo.
- **Regresiones:** 7/7 contratos nuevos cubren aislamiento entre dos empresas,
  destinatario ambiguo, duplicado, caída transitoria del escáner, NIF conocido,
  alta pendiente/corregible y reutilización explícita. Suite completa anterior más
  esos contratos y repetición final completa **550/550** en 477,3 s; ciclo de
  migración focalizado, Ruff, compilación, verdad documental y `git diff --check`
  verdes.
- **Límite externo:** todavía no se ha activado Hostinger. Falta demostrar en un
  buzón real que el catch-all conserva `Delivered-To`/destinatario original, recorrer
  PDF y foto y comprobar la experiencia móvil antes de dejarlo encendido.

## 2026-08-26 — rentabilidad operativa por cuenta

- **Alcance:** nueva lectura interna mensual por cuenta en el centro de mando y en
  su ficha privada. Usa únicamente plan/estado, metadatos de consumo y entregas y
  costes reales append-only; no abre clientes, mensajes, facturas ni documentos.
- **Criterio financiero:** IA se distribuye por coste medido, Meta por plantillas,
  correo por volumen, pagos por ingreso comprometido y costes compartidos por cuenta
  no demo. Una categoría sin driver permanece sin asignar y la cobertura lo revela.
- **Alertas:** entrega fallida, acciones avanzadas agotadas, consumo al 80 %, coste
  superior al ingreso o margen inferior al 60 %. Demos quedan separadas.
- **Corrección adicional:** una extracción OCR local ya no suma 0,014 € ficticios;
  solo se reconoce coste de proveedor medido o factura real del libro CFO.
- **Regresiones y validación:** reparto de 80 € entre dos cuentas reconcilia al 100 %,
  alerta de margen/consumo y OCR local sin coste inventado; 4/4 contratos centrados,
  suite completa **543/543**, Ruff y `git diff --check` verdes.
- **Límite:** la exactitud económica depende de cargar costes reales y de validar
  drivers/umbrales con el piloto. Falta medir latencia y correcciones por
  tipo de acción antes de fijar SLA o automatizar decisiones comerciales.

## 2026-08-26 — restauración PostgreSQL con facturas inmutables

- **Hallazgo en producción:** `noesis-restore-check` falló de forma segura. La última
  copia marcada como recuperable era del 27-jul y declaraba esquema 31/51; las copias
  diarias recientes existían, pero su verificación terminaba en error porque el
  trigger de líneas inmutables rechazaba reconstruir una factura ya emitida.
- **Corrección:** la restauración deshabilita temporalmente `TRIGGER USER` por tabla
  únicamente en el esquema/transacción descartables. Las FK y restricciones internas
  siguen activas; tras insertar y alinear secuencias se reactivan los triggers antes
  de comparar esquema, tablas y recuentos. Un error revierte la transacción y el
  esquema se elimina siempre.
- **Regresión real:** el humo PostgreSQL ahora crea una copia después de emitir una
  factura con líneas, exige que quede marcada `ok` y vuelve a ejecutar el simulacro
  independiente. Así el fallo que producción escondía no puede volver con CI verde.
- **Validación:** 5/5 pruebas de backup SQLite/adaptadores, Ruff y compilación
  verdes. El humo PostgreSQL de GitHub creó y restauró un conjunto con facturas
  emitidas. Producción en `d55be0ae6673` generó después
  `noesis-20260826-101725-080641.dump.gz`, lo marcó `ok` sin error y el simulacro
  independiente terminó `ok` en 3,22 s. No se abrió ni descargó contenido.
- **Límite restante:** el artefacto continúa en el volumen del mismo proveedor; falta
  S3 privado y una restauración desde otra infraestructura para demostrar RPO/RTO
  ante pérdida total de Railway.

## 2026-08-26 — recuperación atómica del titular

- **Alcance:** endurecimiento del flujo existente `/recuperar` y `/restablecer`, sin
  cambiar la pantalla ni el correo que conoce el cliente.
- **Garantías:** enlace nuevo invalida anteriores; token, contraseña y
  `session_version` cambian en una transacción; el token es de un solo uso; la
  respuesta de solicitud no enumera cuentas; los eventos no contienen identidad ni
  secreto.
- **Regresiones:** dos contratos HTTP cubren doble solicitud, enlace antiguo, uso
  único, nueva contraseña, revocación de una sesión abierta y trazabilidad. Verdes.
- **Validación local:** 2/2 contratos centrados y suite estándar completa **541/541**
  verdes; controles estáticos, secretos y Bandit se ejecutan como barrera final.
  Quedan CI y PostgreSQL después del `push`.

## 2026-08-26 — reintento manual y privado de correo fallido

- **Alcance:** una acción POST de administración devuelve a la outbox un correo que
  ya agotó sus intentos; el scheduler sigue siendo el único emisor.
- **Aislamiento y privacidad:** la actualización exige `id + business_id + failed`
  bajo bloqueo; otro negocio, un segundo clic, un envío activo o uno ya enviado no
  se pueden reencolar. La pantalla y el evento omiten destinatario, asunto y cuerpo.
- **Regresión:** el contrato HTTP comprueba botón, aislamiento, no exposición,
  reinicio de intentos, idempotencia práctica y un solo evento encadenado. Verde.
- **Validación local:** regresión específica y suite estándar completa **539/539**
  verdes. Ruff, compilación, fuente de verdad, secretos, Bandit y `diff --check` se
  ejecutan como barrera final; CI/PostgreSQL quedan para después del `push`.

## 2026-08-26 — recuperación segura de contraseña para gestorías

- **Alcance:** rutas y pantallas propias de recuperación profesional, migración 51,
  persistencia separada de usuarios de negocio y envío mediante la outbox durable.
- **Contratos de seguridad:** correo existente e inexistente reciben la misma
  respuesta; solo una cuenta activa encola correo; el token nunca vuelve al HTML ni
  se guarda en claro; pedir uno nuevo invalida el anterior; consumo y cambio de clave
  ocurren en una transacción; caducados y reutilizados fallan cerrados; todas las
  sesiones anteriores se invalidan y el MFA permanece activo.
- **Pruebas:** 3 regresiones específicas y las 4 de MFA profesional están verdes.
  Suite estándar completa **538/538**, Ruff, compilación, fuente de verdad y
  `git diff --check` verdes. Detector de secretos, Bandit y humo PostgreSQL quedan
  pendientes antes de publicar.
- **Límite externo:** falta comprobar llegada y entregabilidad con un buzón real y
  recorrer el segundo factor con un autenticador físico después del despliegue.

## 2026-08-26 — puerta externa automática de producción

- **Alcance:** nueva comprobación sin credenciales para `/health`, `/ready`, release,
  esquema, cabeceras de seguridad, sitemap, 14 páginas públicas, H1, canonical,
  indexabilidad y marcadores legales. No abre sesiones, no usa datos de clientes y no
  ejecuta acciones de negocio.
- **Regresiones automatizadas:** cinco contratos cubren release completo, release
  atrasado respecto de `main`, esquema a medias, marcador legal y pérdida de HSTS.
  La suite completa queda en **535/535**;
  Ruff, detector de secretos, fuente de verdad y `git diff --check` están verdes. El
  workflow programado usa el esquema de `project-state.json`, por lo que una
  migración futura no deja un número duplicado.
- **Producción real:** `noesis-production-check --json` respondió verde contra
  `https://bynoesis.com`: release `6d0e0feba7d6`, esquema 50, 14 páginas públicas y
  las ocho familias de cabeceras/CSP exigidas.
- **Límite:** un workflow cada seis horas detecta una regresión, pero no garantiza un
  SLA ni una llamada de guardia; falta monitor externo 24/7 y procedimiento de
  incidente antes de abrir de forma masiva.

## 2026-08-26 — auditoría de la semana y reparación del lockfile

- **Punto de partida:** `main` local estaba limpio en `5ae1541`; después de
  `git fetch` se detectaron 20 commits ya publicados hasta `550262a` y se aplicó
  un avance rápido, sin crear un merge ni duplicar commits.
- **Incidencia encontrada:** los runs de CI de los commits nuevos fallaban en
  `uv sync --locked --extra security --extra test`. El cambio que hizo portable
  `analysis/build_modelo_economico.py` añadió el extra `analysis` con `openpyxl` a
  `pyproject.toml`, pero no regeneró `uv.lock`.
- **Corrección:** lock regenerado con `py -m uv lock`; añade `openpyxl 3.1.5` y su
  dependencia `et-xmlfile 2.0.0`, además de reflejar el extra `analysis` del
  proyecto. No se ha cambiado ninguna dependencia de runtime de Bynoesis.
- **Segunda barrera revelada por CI:** una vez reparado el lock, `pip-audit` alcanzó
  su paso y rechazó `pip 26.1.2` por `PYSEC-2026-3721`; la versión corregida indicada
  por el auditor es 26.2. El extra `security` fija `pip>=26.2,<27` para que la propia
  cadena de auditoría no vuelva a resolver una versión vulnerable.
- **Tercera barrera revelada por CI:** al superar la auditoría, `detect-secrets`
  alcanzó por primera vez una credencial ficticia de backup añadida a una prueba el
  17 de agosto. Es un valor local y no funcional. Se marca únicamente esa línea con
  `pragma: allowlist secret`, la mitigación indicada por el propio hook; no se amplía
  la baseline, no se excluye el archivo y no se reduce la detección del repositorio.
- **Validación local:** instalación estricta desde el lock correcta; Ruff y
  `scripts/check_project_truth.py` verdes; suite estándar de `unittest` completa,
  **530/530** en 809,6 s. Los logs de caídas de IA, Stripe, WhatsApp, correo,
  Veri*Factu y backups son escenarios simulados esperados por las pruebas.
- **Modelo económico:** el generador portable produce 17 hojas y coincide con el
  libro publicado salvo `Calculadora!B6:B8`: el artefacto conserva los valores de
  ejemplo 1/5/2 que introdujo el founder, mientras que una regeneración parte de
  0/0/0. Es la diferencia intencionada ya registrada el 19 de agosto, no una fórmula
  rota ni una regresión.
- **Límit:** `project-state.json` conserva el recompte verificat de 531 perquè el CI
  afegeix comprovacions de migració i PostgreSQL fora de la descoberta estàndard.
  La validació externa definitiva és el run de GitHub Actions després del `push`.

## 2026-08-20 — corregido el fallo de parametros multilinea de WhatsApp

- **El fallo:** Meta rechaza un parametro de plantilla con salto de linea, tabulador o
  mas de cuatro espacios seguidos. `web/scheduler.py` compone el resumen diario, el
  semanal, el cierre, el aviso fiscal y el aviso de cobros como texto de varias lineas
  y lo pasa como **un unico parametro**. Contra el numero real, esos cinco proactivos
  habrian agotado sus seis reintentos en silencio. Ninguna prueba lo veia porque todas
  simulan la respuesta de Meta.
- **La correccion:** `sanitize_template_param` en `web/whatsapp.py`, aplicada al
  encolar en `queue_template`. Los saltos se convierten en un separador visible
  « · » en vez de desaparecer —un resumen sin marcas entre sus puntos se lee como un
  parrafo confuso—, los tabuladores tambien, y las tiradas de mas de cuatro espacios
  se acortan. Se limpia al encolar y no al enviar, para que lo guardado coincida con
  lo que sale: asi un reintento no cambia el texto y el diagnostico no enseña otra cosa.
- **Pruebas:** `test_template_params_never_carry_what_meta_refuses` comprueba que no
  sobrevive ningun caracter prohibido, que el contenido sigue siendo legible y que
  `_meta_payload` envia exactamente lo guardado.
  `test_every_proactive_summary_survives_the_meta_rules` recorre los cinco avisos con
  su texto real, uno por subtest: cada uno se compone en un sitio distinto y basta que
  uno se olvide para que ese aviso no llegue nunca.
- **Verificadas por reversion:** desactivando el saneado, **fallan seis** —la primera
  prueba y los cinco subtests, uno por proactivo—.
- **Alcance:** 64 pruebas de WhatsApp, plantillas y planificador en verde; `ruff`
  limpio. Documentos `WhatsApp-Puesta-en-marcha` y `WhatsApp-Como-funciona`
  actualizados: ya no anuncian un fallo abierto.

## 2026-08-20 — primer correo real entregado desde produccion

- **Que se probo:** con `BREVO_API_KEY` y `SMTP_FROM` ya cargadas en Railway, se
  disparo una recuperacion de contraseña contra `https://bynoesis.com/recuperar`
  para una direccion del propio founder.
- **Resultado:** HTTP 303 a `?sent=1` —respuesta identica exista o no la cuenta, por
  diseño— y **el correo llego** al buzon de `xavier@bynoesis.com` con el asunto
  "Restablecer tu contraseña de Bynoesis" y el remitente «Bynoesis».
- **Que queda demostrado:** la clave de Brevo es valida, la via HTTPS funciona desde
  Railway —que bloquea SMTP—, `SMTP_FROM` produce el remitente correcto y la cola
  entrega. El adaptador ya se habia verificado interceptando la peticion; ahora se
  confirma extremo a extremo contra el proveedor real.
- **Que NO queda demostrado, y por eso `smtp_real` sigue pendiente:** entregabilidad
  en Gmail y Outlook sin caer en spam, que depende de la autenticacion del dominio en
  el DNS; entrega de factura al cliente final con su PDF; invitacion de gestoria; y
  reintento de la outbox tras un fallo temporal sin duplicar el mensaje.
- **Google OAuth:** validado en el mismo periodo. El founder inicia sesion con Google
  y alcanza `/admin`, que en produccion lo exige.

## 2026-08-20 — cada identidad aterriza donde trabaja

- **Por que:** el founder lo dijo: administracion "no hace falta que utilice
  software... unicamente es para manejar y hacer de admin". Al entrar aterrizaba en
  un panel de negocio con Trabajos, Clientes y Facturas, y tenia que encontrar la
  puerta de su propio trabajo. De ahi venia la confusion con "Clientes".
- **Que cambia:** `_account_destination` recibe el usuario; si es administracion
  devuelve `/admin`. Un cliente sigue entrando a su negocio. La regla se aplica igual
  por contrasena y por las dos vias de Google.
- **No se encierra a nadie:** el cuadro de mando ofrece "Mi panel de negocio".
- **Auditoria previa con la aplicacion levantada:** las cinco rutas de administracion
  responden 200 y el log del servidor no registra ni un error. El unico 404 es
  `/admin/backups/latest` sin copias, que es correcto.
- **Prueba:** `test_each_identity_lands_where_it_works` cubre las dos direcciones —
  administracion a `/admin` con vuelta disponible, y un cliente a su negocio sin
  acabar nunca en el panel interno.
- **Correo verificado sin contratar nada:** interceptando la llamada HTTPS se
  comprueba que el adaptador construye la peticion correcta a
  `https://api.brevo.com/v3/smtp/email`, con la cabecera de clave, el remitente
  derivado de `SMTP_FROM` y el destinatario. **El codigo esta bien; falta la clave.**
- **Alcance:** 98 pruebas de administracion, login, sesion, onboarding y Google en
  verde; `ruff` limpio.

## 2026-08-20 — panel de gestion en el cuadro de mando

- **Por que:** el founder entro en `/admin` y no encontro nada. La unica via a las
  acciones era un boton al final de una tabla de doce columnas, y desde su propio
  panel no habia forma de llegar a `/admin`.
- **Que se anade:** una seccion `#gestion` al principio de `/admin` con cada cuenta,
  su estado real —distingue prueba vigente de vencida— y acciones en linea: activar
  con plan, pasar a modo consulta y ampliar la prueba. Ademas, un enlace a
  administracion en la barra del panel de negocio, visible solo para administracion.
- **Comprobado con la aplicacion levantada**, no solo con pruebas: escenario de un
  propietario y dos clientes, uno con la prueba vencida y otro activo. Se verifico el
  enlace, el listado, y que activar y desactivar cambian el estado y devuelven a
  `/admin#gestion`, mientras la misma accion desde la ficha devuelve a la ficha.
- **Pruebas:** `test_admin_dashboard_manages_accounts_without_opening_each_file` y
  `test_the_admin_entrance_is_not_offered_to_a_normal_account`, que cubre lo
  contrario: una cuenta normal no ve el enlace y `/admin` la rechaza.
- **Alcance:** 95 pruebas de administracion, soporte, seguridad, sesion y login en
  verde; `ruff` limpio.

## 2026-08-20 — canal de Meta revisado y plantillas por oficio con pantalla

### Qué se probó y con qué resultado

- **Plantillas por oficio:** el sector es texto libre, así que se comprobó que
  «Fontanero autónomo», «REFORMAS INTEGRALES» y «lampistería» caen en el oficio
  correcto y que «consultoría de marca» no cae en ninguno. Cada partida conserva su
  IVA y si es material o mano de obra; el reparto por tipo cuadra con el total.
- **No duplicar:** cargar el catálogo de fontanería dos veces crea las partidas la
  primera vez y ninguna la segunda; el número de productos no se mueve.
- **Aislamiento:** cargar el catálogo en un negocio no marca ni una partida como
  «ya la tienes» en otro.
- **Pantalla y API:** con sesión iniciada, `/b/{id}/oficios` responde 200,
  `/api/{id}/oficios/plantillas` devuelve los cinco oficios y el sugerido, y la
  carga desde la propia página deja las partidas en el catálogo real.
- **Contrato de las plantillas de Meta:** ninguna de las nueve declaradas tiene el
  cuerpo formado solo por variables ni huecos descolocados, y todas son *utility*.
- **Saneado de valores:** un salto de línea, un tabulador o seis espacios seguidos
  dentro de un valor se aplanan antes de encolar, y un valor larguísimo se corta en
  1024 caracteres. Al encolar `noesis_factura_lista` con «Ana\nGarcía», el outbox
  guarda «Ana García».
- **Pruebas:** suite completa **437 pasan, 85 subtests, 0 fallos**. Ruff verde.
  Fuente de verdad del proyecto verde.

### Qué no se ha probado

- **Nada contra Meta real**: sigue sin credenciales, así que no hay entrega,
  aprobación de plantilla ni estado de lectura verificados. Todo lo anterior es
  comportamiento propio con la API simulada.
- **Cuánto tarda el webhook** con una foto real de ticket: es la medida que decide
  si hay que contestar 200 antes de procesar. Requiere número real.
- **Los cinco proactivos al titular** siguen mandando el mensaje entero en un hueco.
  Está detectado, documentado y con cuerpo alternativo escrito, pero no corregido.
## 2026-08-19 — control de acceso por persona (esquema 50)

- **Que se anade:** `users.is_active`, `suspended_at` y `access_note`; suspension y
  restauracion desde administracion; revocacion del acceso de una gestoria.
- **Donde se aplica el bloqueo:** cuatro puntos. `set_user_access` sube
  `session_version` (mata sesiones), `auth.current_user` rechaza al inactivo (segunda
  barrera), y el login por contrasena y las dos vias de Google lo comprueban antes de
  abrir sesion.
- **Pruebas:** cuatro nuevas y **las cuatro verificadas por reversion**, cada una
  contra la barrera que dice cubrir:
  1. `test_suspended_user_loses_access_immediately_and_can_be_restored` — falla si se
     quita la comprobacion del login.
  2. `test_an_inactive_user_is_refused_even_if_the_session_still_matches` — desactiva
     la cuenta **sin** subir `session_version`, para aislar la barrera de
     `current_user`; falla si se quita. **Se escribio despues de descubrir que la
     primera prueba pasaba igual con esa barrera desactivada**, es decir, que no
     cubria lo que decia cubrir.
  3. `test_access_control_refuses_to_leave_an_account_locked_out` — las tres
     protecciones por separado; falla si se quitan.
  4. `test_admin_manages_access_per_person_and_leaves_a_signed_trail` — recorrido HTTP
     completo y eventos en la bitacora.
- **Migracion 50:** probada arriba, abajo y repetida (idempotente). Comprobado ademas
  que un usuario creado en el esquema 49 **conserva el acceso** tras migrar.
- **Alcance:** 185 pruebas de administracion, seguridad, sesion, login, gestoria,
  aislamiento y suscripcion en verde; `ruff` limpio.
- **Pendiente:** suite completa cortada al 31% sin fallos por reinicio de sesion; el
  CI en Linux es el juez.

## 2026-08-19 — recorrido real de administracion: dos flujos y tres correcciones

- **Como se probo:** servidor levantado en local con base aparte y un escenario real
  —propietario y un cliente con la prueba vencida hace 12 dias— recorriendo los dos
  flujos de verdad, no solo pruebas unitarias.
- **Flujo 1, activar a un cliente a mano:** funciona extremo a extremo. Desde
  `/admin/cuentas/<id>` la cuenta pasa a `active`/`pro`, y desde la sesion del cliente
  desaparece el aviso de modo consulta, la cabecera dice "Suscripcion activa" y el
  boton de crear se desbloquea.
- **Flujo 2, un cliente avisa de un bug:** el diagnostico decia "email retrying 1" y
  nada mas. El motivo estaba en la base (`last_error`) pero no se mostraba, que es
  justo lo que separa un fallo de configuracion nuestro de una direccion mal escrita
  del cliente.
- **Correcciones:** (1) `admin_support_delivery_failures` expone canal, estado,
  intentos, si se agotaron y el error del proveedor; (2) la etiqueta de fin de prueba
  ya no dice "vencida" en una cuenta activa, dice "ya no aplica"; (3) los permisos
  avisan de que la cuenta esta en modo consulta, porque una prueba vencida devuelve
  entitlements de premium y los cuatro salian como "incluido" en una cuenta bloqueada.
- **Prueba:** `test_support_shows_why_a_delivery_is_stuck_without_leaking_content`
  recorre el camino real de la cola (reclamar y fallar) y comprueba el motivo, los
  intentos y que **no** aparecen destinatario, asunto ni cuerpo. **Verificada por
  reversion:** introduciendo una fuga del destinatario, la prueba falla.
- **Alcance:** 109 pruebas de admin, soporte, aislamiento, seguridad y suscripcion en
  verde; `ruff` limpio.

## 2026-08-19 — el propietario gestiona permisos de cualquier cuenta

- **Que se anade:** administracion activa con plan, pasa a modo consulta o amplia la
  prueba de cualquier cuenta, y ve que funciones desbloquea el plan vigente.
- **Que NO se anade:** acceso al panel del cliente. Se construyo y se retiro a peticion
  del propietario. `auth_guard` queda identico al original.
- **Prueba:** `test_owner_manages_account_permissions_without_entering_the_account`
  recorre autonomo -> negocio -> desactivada comprobando el plan, los entitlements
  efectivos (`frozenset()` en Autonomo, Proyectos incluido en Negocio),
  `subscription_allows_access` en cada paso, que el panel ajeno sigue redirigiendo
  fuera y que los tres cambios estan en la bitacora encadenada con el negocio correcto.
- **Alcance:** 108 pruebas de admin, soporte, aislamiento, seguridad y suscripcion en
  verde; `ruff` limpio.

## 2026-08-19 — la pagina de suscripcion ensenaba una marca ISO y un estado falso

- **Que fallaba:** con la prueba ya vencida, la cabecera de `/b/<id>/suscripcion`
  mostraba `En prueba · hasta 2026-07-20T00:00:00`. Dos defectos a la vez: la marca
  ISO interna en lugar de una fecha legible, y la etiqueta "En prueba" en una cuenta
  que el propio panel ya trataba como modo consulta. El estado en base de datos sigue
  siendo `trial` hasta que alguien contrata; la caducidad solo se deduce comparando
  `trial_ends_at` con hoy, como hace `db.subscription_allows_access`.
- **Correccion:** `pages.py` calcula `trial_expired` con la misma regla y lo pasa a la
  plantilla; `suscripcion.html` aplica el filtro `date_es` —que ya existia en
  `deps.py` con el comentario "evita que los portales ensenen marcas ISO internas" y
  que esta pagina no usaba— y distingue "Prueba terminada" de "En prueba"; `app.css`
  pinta en rojo el estado vencido.
- **Prueba:** `test_subscription_page_shows_human_dates_and_a_finished_trial` cubre
  prueba vigente y vencida, comprueba que no aparece `T00:00:00`, que la fecha sale en
  `dd/mm/aaaa`, que el rotulo cambia y que coincide con `subscription_allows_access`.
  Verificada por reversion: sin la correccion, falla.
- **Alcance:** 97 pruebas de suscripcion, planes y prueba gratuita en verde; `ruff`
  limpio. Solo afecta a la presentacion del estado: no cambia permisos, cobros ni la
  maquina de estados de Stripe.

## 2026-08-17 — dependencia OCR real de Railway

- La comprobación por SSH demostró que Tesseract 5.3.0 y `cat/eng/osd/spa` sí estaban
  instalados, pero el entorno Python no contenía `pytesseract` ni `pypdfium2` porque
  Railpack construye desde `requirements.txt`, no desde las dependencias de
  `pyproject.toml`.
- Se sincronizan `pypdf`, `pypdfium2`, `pytesseract` y la versión mínima de Pillow;
  una prueba de empaquetado impide retirar otra vez el runtime OCR de Railway.
- La primera lectura externa confirmó Stripe completamente correcto. Brevo respondió
  403; Google, Groq y S3 siguen sin configurar. Ninguna comprobación envió, cobró ni
  transcribió contenido.
- Prueba focalizada de empaquetado: **11/11**. Suite completa: **517/517** en
  381,7 s; Ruff, verdad documental y `git diff --check` verdes. Esquema 49 sin
  cambios.
- Producción responde con `b3c184251374`. El comprobador remoto deja OCR en `OK`
  para foto, PDF y `cat/spa/eng`; Stripe también queda `OK`. Brevo responde 403 y
  Google, Groq y S3 todavía no están configurados.

## 2026-08-17 — comprobador seguro de integraciones y voz multilingüe

- Se añade un comprobador offline por defecto que nunca muestra secretos. Con
  `--network` solo hace peticiones `GET`: cuenta y remitentes de Brevo, discovery
  OpenID de Google, seis precios de Stripe y catálogo de modelos Groq. No envía
  correos, no inicia OAuth, no transcribe y no crea cargos.
- Stripe valida seis identificadores distintos, mismo entorno test/live, actividad,
  EUR, importes 29/49/99 mensuales y 319/539/1089 anuales, recurrencia mensual/anual
  e IVA `exclusive`. Brevo exige que `SMTP_FROM` corresponda a un remitente activo.
- OCR exige foto, PDFium y los tres paquetes `cat/spa/eng`. Voz Groq y
  `faster-whisper` dejan de forzar `es` y usan detección automática salvo
  `NOESIS_WHISPER_LANGUAGE` explícito.
- Pruebas focalizadas: **36/36**. Suite completa: **516/516** en 435,7 s.
  Ruff, compilación y `git diff --check` verdes. No se usaron credenciales reales ni
  se llamó a proveedores durante la suite; la aceptación externa sigue pendiente.
- Tras el push, `https://bynoesis.com/health` responde con `808a96004b7b`; el nuevo
  código está publicado sin necesidad de abrir el navegador integrado.

## 2026-08-14 — auditoría visual local y contratos Stripe

- La portada, el panel real de la demo, Documentos, el asistente, la cartera de
  gestoría y el portal del cliente se recorrieron con capturas reales. La jerarquía
  y la separación por tareas son coherentes con el parte de Bynoesis; Documentos
  mantiene 1 ingreso, 2 gastos, 1 ticket, 2 pendientes y 2 elementos en Otros.
- En móvil se reprodujo un mojibake en el centro de la barra inferior y una fila de
  sugerencias parcialmente oculta. El centro muestra ahora `DEMO` y todas las
  sugerencias se distribuyen en dos columnas legibles sin scroll horizontal oculto.
- La respuesta del asistente escapaba HTML pero dejaba `_Por qué:_` sin formato;
  ahora mantiene el escape y representa el énfasis como `<em>`. El DOM real confirma
  cuatro razones accesibles como énfasis, sin guiones bajos visibles.
- El portal mostraba fechas internas ISO. Presupuestos y facturas usan un filtro
  común tolerante y presentan `dd/mm/aaaa`; la captura móvil y la regresión HTTP
  verifican `11/09/2026`, `29/04/2026` y ausencia de `T00:00:00`.
- Stripe: 7/7 contratos focalizados verdes para portal general, tarjeta,
  cancelación, upgrade mensual/anual al precio exacto, reutilización de configuración
  y bloqueo de un segundo Checkout. Falta el recorrido externo autenticado porque
  esta sesión de Codex no dispone de la extensión de Chrome ni de su sesión Stripe.
- Suite completa: **506 pruebas** recorridas en 489,5 s. Una limpieza de base SQLite
  temporal quedó bloqueada por Windows al cerrar; la misma prueba pasó aislada
  inmediatamente (1/1), por lo que no se atribuye al cambio. `git diff --check`,
  Ruff, compilación y verdad documental quedaron verdes antes del push.
- Producción responde con `aed36de59e30`, `/ready` confirma esquema 49 y el CI
  completo, el humo PostgreSQL y el ciclo de migraciones están verdes. En el release
  real se recorrieron a 375 px el asistente demo, el portal de cliente y la cartera
  de gestoría; el portal no contiene fechas ISO y la barra muestra `DEMO` legible.

## 2026-08-14 — fiabilidad de demo, portales y lectura de caja

- La demo comercial responde ahora preguntas locales de agenda, cobros, clientes,
  proyectos y resumen sin persistir conversación, consumir IA ni abrir herramientas
  de escritura. Una orden de factura o agenda explica el límite y no modifica datos;
  el resto de POST de demostración continúa bloqueado en el servidor.
- Los formularios de presupuestos del portal de cliente y los de revisión, perfil
  fiscal, solicitudes y paquetes de gestoría vuelven mediante 303 a la misma vista
  con un aviso de modo consulta. Los controles aparecen desactivados de antemano y
  ya no exponen un JSON técnico a una persona.
- `month_billing` separa `collected` (caja recibida durante el mes) de
  `invoiced_collected` (cobrado sobre facturas emitidas ese mes). La regresión crea
  una factura anterior cobrada ahora y demuestra 161 € de caja, 121 € emitidos y
  solo 40 € cobrados de la cohorte actual, sin el falso 133%.
- Los ejemplos del asistente cambian según limpieza, electricidad, jardinería,
  construcción/fontanería o servicio neutro y mantienen las consultas comunes.
- Pruebas focalizadas: 3/3 verdes. Suite completa: **504/504** en 438,0 s. Ruff,
  `git diff --check` y el render HTTP de las tres experiencias comerciales verdes.
  Permanece el aviso conocido Starlette/httpx del cliente de pruebas; no afecta al
  runtime. Un job del scheduler llegó a una base temporal ya cerrada durante la
  suite, sin fallo de producto ni de prueba.
- CI remoto completo y humo PostgreSQL verdes. Producción responde con
  `ea1f5f3e628f`, `/ready` verde y esquema 49. Queda el recorrido visual autenticado
  de las tres experiencias; no se usaron credenciales ni servicios reales en este
  bloque.

## 2026-08-14 — portal Stripe gestionado y todos los botones verificables

- Se reproducía el fallo funcional: los botones dependían de que el Customer Portal
  estuviera configurado manualmente en Stripe y un rechazo volvía a la misma página
  fuera del área visible, por lo que parecía que el clic no hacía nada.
- El adaptador crea o reutiliza solo una configuración versionada de Bynoesis con
  actualización de tarjeta, cancelación al final del período, historial y cambios
  entre los seis `price_id`. Cada sesión conserva esa configuración también en el
  fallback general; una configuración externa no se reutiliza por error.
- La regresión HTTP envía los seis formularios visibles de una cuenta Autonomo y
  comprueba los flujos `manage`, `payment_method`, `cancel`, mejora mensual y anual.
  La ruta de error vuelve a `#gestion-suscripcion`, presenta el mensaje enfocable y
  registra `subscription_portal_failed`.
- Pruebas focalizadas: **7/7**. Suite completa: **499/499** en 464,4 s dentro del
  entorno 3.12 del proyecto. Ruff sobre `src`/`tests`, `compileall`, comprobación
  JavaScript y `git diff --check` verdes.
- Validación externa pendiente: abrir los flujos con la subscripción sandbox.
  Stripe exige además que los precios intercambiables tengan tratamiento
  fiscal compatible y no `unspecified`; es configuración externa, no se inventa.
- Producción: `/ready` confirmó `52c61f9e6277` y esquema 49. La carga del JavaScript
  publicado se comprobó por HTTP; queda la interacción autenticada con Stripe.

## 2026-08-14 — gestión completa de una suscripción Stripe activa

- Adaptador probado con payloads separados de Customer Portal para actualizar el
  método de pago, cancelar una suscripción concreta y confirmar un cambio al
  `price_id` anual exacto sobre su único `subscription_item`.
- La pantalla activa ofrece gestión, tarjeta, mejoras y cancelación sin ningún
  segundo Checkout; un fallo externo se explica y garantiza que no hubo cambio ni
  cargo.
- Pruebas focalizadas: 4/4 verdes; suite completa **495/495** en 352,1 s;
  `compileall`, verdad documental y `git diff --check` verdes. Aviso conocido de
  deprecación Starlette/httpx, sin fallo funcional.
- Validación real pendiente: portal sandbox, sus seis precios, prorrateo, tarjeta,
  cancelación y webhooks de retorno.
- Producción: `/ready` confirmó `31d0c95abcf0`, esquema 49. Esto valida despliegue e
  identidad del código, no sustituye el recorrido autenticado del portal sandbox.

## 2026-08-13 — plan actual y bloqueo de recompra Stripe

- Una cuenta activa de Autónomo muestra resumen de plan actual, `Gestionar plan` y
  mejoras a Negocio/Premium; no renderiza ningún formulario ni texto de activación
  de Checkout. Una cuenta Premium muestra dos niveles incluidos y ninguna mejora.
- La regresión envía además un POST directo de upgrade anual a la antigua ruta de
  Checkout. El servidor abre el portal de la suscripción existente y demuestra que
  `checkout_url` no se invoca.
- Pruebas focalizadas: **3/3**. Suite completa: **493/493** en 351,9 s. Ruff,
  `py_compile` y `git diff --check` verdes. Los avisos de proveedores corresponden
  a pruebas deliberadas de fallo cerrado.
- Producción responde con el release `3c7bd034828a`, `/ready` verde y esquema 49.
  Pendiente externo: comprobar en Stripe sandbox que el portal permite cambiar
  entre los seis precios mensual/anual configurados, además de tarjeta y cancelación.

## 2026-08-13 — activación Stripe resistente a concurrencia y recuperable

- Evidencia sandbox real: Checkout de Autónomo mensual, suscripción `active`,
  metadatos `business_id=1`, `plan=autonomo`, `billing_period=monthly` y entregas
  `checkout.session.completed`, `invoice.paid` y
  `customer.subscription.created` aceptadas por Bynoesis con HTTP 200.
- La regresión reproduce que un Checkout posterior podía degradar `active` a
  `pending`; ahora la decisión se toma bajo el bloqueo de la misma fila y conserva
  `active`/`trialing`.
- La vuelta del Checkout consulta Stripe con la clave del servidor y solo repara
  si coinciden negocio, cliente, suscripción, estado activo y un único precio del
  catálogo. También se verifica que el plan comprado sea el marcado en pantalla.
- Pruebas focalizadas Stripe: **4/4**. Suite completa: **492/492** en 390,9 s.
  `py_compile` y Ruff focalizado verdes. Los mensajes de proveedores caídos de la
  suite son escenarios deliberados de fallo cerrado y reintento.
- Producción responde con el release `9f3dc48d9d4a`, `/ready` verde y esquema 49.
  Pendiente humano: recargar la URL de retorno del pago ya hecho y confirmar que el
  panel abandona el modo consulta sin repetir el cobro.

## 2026-08-13 — regresión de robots entre gestoría privada y página pública

- La prueba reproduce la semántica de prefijo de `robots.txt` y exige que ninguna
  regla `Disallow` atrape `/gestorias`.
- La zona profesional conserva dos límites explícitos: `/gestoria$` para la raíz y
  `/gestoria/` para el árbol privado. `/gestoria/login$` se permite rastrear para
  que el buscador reciba su cabecera HTTP `noindex, nofollow`.
- `tests.test_seo`: **11/11** verde. La regresión comprueba reglas exactas y simula
  coincidencia de prefijo contra `/gestorias`; Ruff focalizado, verdad documental,
  JSON de estado y `git diff --check` también están verdes.
- Producción responde con release `18104f0b6806`, esquema 49 y `/gestorias` en 200
  para Googlebot, sin `X-Robots-Tag`, con canonical e `index, follow`. El robots real
  contiene `/gestoria$` y `/gestoria/`, no el prefijo ambiguo. CI 31681161643 dejó
  verdes secretos, Bandit, Ruff, verdad documental, 487 pruebas, ciclo completo de
  migraciones y humo PostgreSQL. Falta que Search Console renueve su caché y acepte
  la solicitud externa.

## 2026-08-13 — SEO técnico y páginas por audiencia

- Las 14 URLs públicas del sitemap tienen título y descripción únicos, canonical,
  Open Graph/Twitter, una orden explícita de indexación y exactamente un H1.
  `/autonomos` y `/gestorias` explican dos recorridos reales sin inventar clientes,
  valoraciones, declaraciones fiscales automáticas ni comisiones.
- `Organization` y `WebSite` se declaran una sola vez en la portada mediante JSON-LD
  válido. El sitemap deja de publicar una fecha diaria falsa y campos de prioridad
  ignorados por Google. El SVG de marca incorpora tamaño intrínseco.
- Login, acceso, onboarding, paneles, portales y respuestas inexistentes envían
  `X-Robots-Tag: noindex, nofollow`; `robots.txt` mantiene fuera las zonas de datos
  y permite rastrear los accesos públicos para que el buscador lea el `noindex`.
- `tests.test_seo`: **11/11** verde. Suite completa: **487/487** verde en 439 s;
  Ruff sobre `src`/`tests`, verdad documental y `git diff --check` también verdes.
  Los avisos de caídas de proveedores corresponden a pruebas deliberadas de
  degradación, reintento y fallo cerrado.
- Validación externa: propiedad de dominio verificada, sitemap enviado y usuarios
  añadidos en Search Console por el founder. Falta esperar el recrawl y revisar
  indexación, consultas, impresiones, clics y Core Web Vitals con datos reales.
- Producción responde con release `e5d1ac57742f`, esquema 49 y 200 en `/health`,
  `/ready`, las 14 URLs y el sitemap; cada página tiene un H1 y canonical. Login,
  acceso, gestoría y 404 devuelven el `noindex` esperado. El humo PostgreSQL del CI
  quedó verde. El guardián general se detuvo antes de Ruff/tests porque el baseline
  apuntaba a la línea 51 de `project-state.json`, ahora 52; los hashes y el conjunto
  de coincidencias permanecen idénticos y se versiona esa actualización mecánica.

## 2026-08-12 — alta recuperable y revisión operativa

- El esquema 49 conserva inicio, pasos completados, plan, periodicidad, intención y
  decisión de WhatsApp sin forzar a cuentas históricas a repetir el recorrido.
- Las pruebas HTTP cubren alta anual de Negocio, perfil, configuración fiscal,
  cobros, gestoría, logotipo y distintivo saneados, resumen final, comprobación de
  WhatsApp todavía pendiente, posposición explícita y continuación al pago. También
  se verifica que no se puede terminar antes de los datos obligatorios y que Google
  vuelve al paso exacto.
- Suite completa: **485/485** verde, repartida en 339 pruebas del núcleo y 146 de
  plataforma/seguridad/SEO/documentos. `tests.test_seo` mantiene 9/9 en verde y la
  inspección viva de las 12 URLs del sitemap confirmó 200, canonical, descripción,
  un H1 e imágenes con atributo `alt`.
- CI [31616995507](https://github.com/noesisstudio/noesis/actions/runs/31616995507)
  completamente verde: dependencias, secretos, Bandit, Ruff, verdad documental,
  485 pruebas, ciclo de migraciones y humo PostgreSQL. Producción devuelve release
  `8730826a79ab`, esquema 49 y HTTP 200 en `/health` y `/ready`.
- Pendiente externo: recorrido visual real, webhook de Meta y retorno de Stripe.

## 2026-08-12 — identidad documental y pie gráfico versionado

- 3 pruebas nuevas cubren carga HTTP real de logo y distintivo, saneado a PNG,
  tamaño/alineación/alcance, render de Ajustes, PDF de muestra y rechazo de bytes
  falsos; también congelación del perfil al emitir y aislamiento de referencias
  entre negocios en la base de datos.
- 485 pruebas completas están verdes después de detectar y corregir que el índice
  único compuesto de `document_profiles` debía materializarse antes de la FK en
  PostgreSQL. También están verdes Ruff, Bandit, detección de secretos,
  `git diff --check` y el ciclo local 0 → 48 → 0 → 48.
- CI completo y humo PostgreSQL verdes. Producción confirmó release `c30321c4d8e9`
  y esquema 48 en `/health` y `/ready`; queda pendiente la revisión visual con el
  distintivo real del founder en escritorio y móvil.

## 2026-08-11 — configuración segura desde soporte

- 2 pruebas nuevas cubren autorización real por el titular, render del formulario,
  actualización HTTP y auditoría; también administrador falso, alcance documental
  insuficiente, permiso caducado y ausencia total de escritura ante cada rechazo.
- La lista blanca solo incluye perfil comercial, idioma/nivel y apariencia de
  documentos futuros. Las pruebas fijan que correo titular, NIF, dirección, IVA,
  IRPF, IBAN, plan y estado de suscripción permanecen idénticos. Una factura emitida
  antes del cambio conserva el nombre original del emisor.
- Los textos libres no aparecen en claro en la bitácora: perfil y apariencia se
  registran como estados seudonimizados, junto a autorización y campos modificados.
- 22 pruebas del centro administrativo y 4 focalizadas de ambas correcciones están
  verdes. Suite completa **473/473** verde en 384 segundos; Ruff y verdad documental
  también están verdes.
- El CI [31478332206](https://github.com/noesisstudio/noesis/actions/runs/31478332206)
  quedó completamente verde: dependencias, secretos, Bandit, Ruff, verdad del
  proyecto, 473 pruebas, ciclo de migraciones y humo PostgreSQL. Producción devuelve
  release `6a879b2b1153`, esquema 47 y HTTP 200 en `/health` y `/ready`.

## 2026-08-11 — corrección documental acotada desde soporte

- 2 pruebas nuevas cubren el recorrido autenticado completo y el fallo cerrado:
  editor invisible sin alcance, autorización creada por el titular, asociación
  proyecto→cliente, actualización por el administrador, redirección, aislamiento
  frente a IDs de otro negocio y rechazo de un documento ligado a factura emitida.
- La bitácora conserva administrador, negocio, autorización, campos cambiados y
  valores anteriores/posteriores. La nota solo deja una huella SHA-256 truncada;
  su texto no aparece en eventos de seguridad.
- 25 pruebas focalizadas del centro de administración y medición pública están
  verdes. Suite completa **471/471** verde en 340 segundos; la revisión visual debe
  hacerse después con una autorización temporal real.
- El CI [31475120052](https://github.com/noesisstudio/noesis/actions/runs/31475120052)
  quedó completamente verde: dependencias, secretos, Bandit, Ruff, verdad del
  proyecto, 471 pruebas, ciclo de migraciones y humo PostgreSQL. Producción devuelve
  release `bf2df0d7afe5`, esquema 47 y HTTP 200 en `/health` y `/ready`.

## 2026-08-11 — clasificación demo y archivo documental responsive

- 23 pruebas focalizadas verdes con `unittest`: sembrado repetido sin duplicados,
  seis tipos documentales esperados, OCR de PDF escaneado, clasificación local
  conservadora, facturas recibidas, deduplicación por negocio, búsqueda aislada,
  paquete de gestoría y las tres experiencias demo navegables.
- La prueba de escaparate verifica explícitamente las carpetas del trimestre:
  6 documentos, 1 ingreso, 2 gastos, 1 ticket, 2 pendientes y 2 en Otros. El HTML
  autenticado contiene la entrada horizontal, navegación por carpetas y cámara.
- Suite completa **469/469** verde en 344 s. Ruff, verdad documental y
  `git diff --check` están verdes. Falta recorrido visual manual en
  escritorio/móvil; no se abrió navegador gráfico porque el founder ha observado
  cierres de Codex al utilizarlo.
- El CI 31469598848 pasó dependencias, secretos, Bandit, Ruff, verdad documental y
  humo PostgreSQL. La suite seguía progresando sin fallo cuando GitHub canceló el
  job exactamente por `timeout-minutes: 15`; el límite del job principal pasa a 25
  minutos para dejar terminar suite y ciclo de migraciones conservando un corte.
- El segundo CI 31470757084 volvió a dejar verde PostgreSQL y dependencias, pero el
  guardián de secretos detectó que las tres referencias permitidas dentro de
  `ci.yml` se habían desplazado dos líneas al documentar el nuevo límite. Se actualiza
  solo su número de línea; tipos y hashes permanecen idénticos.
- El CI final 31470941717 quedó completamente verde: secretos, dependencias, Bandit,
  Ruff, verdad documental, 469 pruebas, ciclo completo de migraciones y humo
  PostgreSQL. Producción devuelve release `5bb715a68217`, esquema 47 y HTTP 200 en
  `/health`, `/ready` y portada.
- No se cambió la regla segura de producción: una factura sin emisor inequívoco no
  se contabiliza ni se fuerza a ingreso/gasto. OCR/IA propone y el titular confirma.

## 2026-08-10 — MFA de gestoría sin semilla reversible

- El primer CI de `main`
  [31410800904](https://github.com/noesisstudio/noesis/actions/runs/31410800904)
  validó el ciclo de migraciones y el humo PostgreSQL con esquema 47. La suite se
  detuvo antes de ejecutarse porque `detect-secrets` clasificó como posibles
  secretos dos contraseñas literales exclusivas del test MFA. Se añadieron
  permisos inline exactamente sobre esos fixtures: no se cambió `.secrets.baseline`,
  no se excluyó el archivo y no se debilitó el control. El hook sobre todos los
  archivos versionados, Ruff, `git diff --check` y las 4 pruebas MFA pasan después
  de la corrección.
- La repetición completa
  [31411139501](https://github.com/noesisstudio/noesis/actions/runs/31411139501)
  quedó verde: 469 pruebas, auditoría de dependencias, secretos, patrones de
  seguridad, estática, verdad del proyecto, ciclo de migraciones y humo PostgreSQL.
  Producción respondió `/health` con release `40d564555c07`, `/ready` con esquema
  47 y HTTP 200 en `/`, `/acceso` y `/gestoria/login`.
- Suite completa: **469/469** en 335 segundos. Después de retirar los códigos en
  claro de la cookie de sesión, las cuatro pruebas focalizadas volvieron a pasar;
  Ruff y `git diff --check` están verdes. Permanece el aviso conocido de
  deprecación Starlette/httpx.
- Esquema 47 probado desde 46: las cuentas profesionales existentes conservan
  identidad y accesos, empiezan con MFA desactivado y reciben contador anti-replay,
  hashes de recuperación y fecha de alta sin datos ficticios.
- La contraseña correcta no abre cartera cuando MFA está activo. El código TOTP
  vigente abre una vez; repetirlo falla. Un código de recuperación abre una vez y se
  elimina atómicamente. El reto expira a los cinco minutos y comparte límites por IP
  y cuenta seudonimizados.
- Activar MFA exige la contraseña actual y un TOTP generado desde el QR/clave. Una
  sesión robada sin contraseña no puede bloquear al titular. Regenerar o desactivar
  también exige doble verificación; los ocho códigos aleatorios se almacenan solo
  como SHA-256 y su texto aparece únicamente en la respuesta inmediata.
- La primera suite completa tras subir el esquema encontró una prueba histórica que
  usaba “última versión” para verificar 45→46. Se corrigió para apuntar a 46 y evitar
  que futuras migraciones rompan evidencias históricas; la repetición final quedó
  469/469. CI, PostgreSQL y despliegue ya están verificados; faltan prueba visual,
  autenticador/cuenta profesional reales y validación externa.

## 2026-08-10 — suscripciones ordenadas y permisos comerciales efectivos

- CI de `main` [31407830116](https://github.com/noesisstudio/noesis/actions/runs/31407830116)
  verde: dependencias, secretos, seguridad, estática, verdad del proyecto, suite,
  ciclo completo de migraciones y humo PostgreSQL. Producción respondió `/health`
  con release `c63bf0e13d0d`, `/ready` con esquema 46 y la portada con HTTP 200.
- Suite completa final: **465/465** en 338 segundos. Ruff, `git diff --check` y las
  pruebas focalizadas de Stripe, migración y permisos están verdes. Las trazas de
  IA, Meta, correo, backup, AEAT y el primer intento del webhook Stripe son fallos
  adversos simulados y esperados por sus pruebas; permanece el aviso conocido de
  deprecación Starlette/httpx.
- Esquema 46 probado desde una base en 45: añade orden de evento, prioridad e id
  Stripe sin cambiar plan ni acceso existentes. La migración limpia y el salto
  histórico terminan en 46.
- Checkout pagado no activa una cuenta cancelada: queda pendiente y conserva
  customer/subscription. Solo `invoice.paid` o una suscripción `active`/`trialing`
  habilitan escritura. `incomplete`, `paused` y un estado desconocido no se
  convierten en prueba gratuita. Un Checkout Premium iniciado por una cuenta
  Autónoma activa tampoco cambia el plan ni concede módulos antes de confirmarse.
  Un cambio desde el portal usa el `price_id` actual incluso si la metadata conserva
  el plan anterior; un precio ajeno al catálogo falla cerrado.
- Se reprodujeron entregas fuera de orden: un fallo de pago antiguo y un Checkout
  todavía más antiguo no deshacen una factura pagada posterior. Una factura sin
  suscripción y una factura de una suscripción reemplazada tampoco cambian el
  estado vigente.
- Una cuenta activa Autónoma conserva Clientes y el núcleo, pero recibe 403
  `plan_upgrade_required` para Proyectos, Equipo y Análisis avanzado; la pantalla
  directa redirige a la ampliación y el cerebro rechaza crear el proyecto. Negocio
  y la prueba mantienen las mismas rutas operativas. La navegación no anuncia
  módulos no contratados.
- El control también quedó aplicado a WhatsApp y portal de trabajadores, cartera y
  paquetes de gestoría, herramientas internas y scheduler. No se usaron
  credenciales Stripe ni se hizo prueba visual con navegador: Stripe test,
  Stripe test con credenciales y QA visual siguen siendo validaciones externas
  pendientes; PostgreSQL, despliegue y esquema 46 ya quedaron verificados.
- Una ejecución previa completó las comprobaciones funcionales pero Windows retuvo
  un SQLite temporal al limpiar una prueba de WhatsApp. La prueba aislada pasó y la
  repetición completa terminó 465/465; queda registrado como incidencia ambiental
  intermitente, no como resultado verde omitido.

## 2026-08-10 — WhatsApp multicanal y equipo sin ruido

- CI de `main` [31377826100](https://github.com/noesisstudio/noesis/actions/runs/31377826100)
  verde: dependencias, secretos, seguridad, estática, verdad del proyecto, suite,
  ciclo de migraciones y humo PostgreSQL. Producción respondió `/health` y `/ready`
  con release `a803da4343e6`, estado `ready` y esquema 45.
- Esquema 45 creado desde cero en SQLite. La primera suite completa detectó que
  PostgreSQL exige índices únicos explícitos antes de tres claves foráneas compuestas
  nuevas; se añadieron antes de las tablas dependientes y la guardia de orden DDL
  quedó verde.
- Suite completa final: **432/432** en 326 segundos. Ruff, `compileall`,
  `git diff --check`, migración 45 y 41 pruebas focalizadas de WhatsApp/equipo/admin
  verdes. Las trazas de Meta, Stripe, correo, IA, backup y AEAT son fallos adversos
  simulados ya cubiertos por la suite; queda el aviso conocido Starlette/httpx y un
  job del scheduler que alcanza una base temporal ya eliminada después de terminar
  las pruebas, sin fallo de test.
- Las pruebas nuevas demuestran que un mismo remitente queda separado por número
  receptor y negocio; un destinatario o WABA desconocido no crea datos ni recibe
  respuesta; la outbox usa el `phone_number_id` de la conexión correcta; y un coste
  de trabajador no crea material hasta aceptación del titular y solo se aplica una
  vez aunque se repita la decisión.
- El canal central rechaza vincular un teléfono como titular y trabajador, o como
  dos trabajadores distintos. Si encuentra una ambigüedad histórica, no elige un
  negocio por aproximación: responde con el bloqueo de seguridad y no ejecuta nada.
- Verificación funcional sin credenciales: permisos de rol, privacidad de márgenes,
  bandeja de aportaciones, resumen al titular, contactos/conversaciones por negocio,
  opt-out, documentos de cliente sin efecto contable, respuesta desde panel y
  bloqueo de texto libre fuera de 24 horas.
- Humo HTTP autenticado con base temporal: login 303; Ajustes, Clientes y Equipo
  200; API del canal comercial y aportaciones 200. Las tres plantillas nuevas se
  renderizan sin excepción. No sustituye la revisión visual de escritorio/móvil.
- El centro administrador registra WABA y `phone_number_id` como pendientes, los
  activa de forma explícita y audita actor y negocio. La prueba HTTP confirma que
  un campo de token inesperado se ignora, el secreto no se almacena ni se renderiza
  y la recepción solo puede habilitarse para una conexión activa.
- No se validó Meta real, Embedded Signup, plantillas aprobadas, entrega de audio o
  medios ni dos WABA reales. Tampoco se realizó QA visual con navegador por el cierre
  recurrente indicado por el founder. Esos extremos permanecen en `Tareas-vivas.md`.

## 2026-08-08 — soporte consentido, CFO observado y términos operativos

- CI de `main` [31269731863](https://github.com/noesisstudio/noesis/actions/runs/31269731863)
  verde: suite/migraciones, dependencias, secretos, análisis estático y humo
  PostgreSQL. Producción respondió `/health` con release `f472d08d85cb` y `/ready`
  con esquema 44; publicación técnica verificada sin navegador.
- Migraciones 43-44 verificadas en subida y bajada: autorización de soporte y libro
  de costes. Solo el correo titular abre/revoca una ventana por motivo, alcance y
  duración; un usuario de otra empresa o un usuario secundario de la misma empresa
  no puede concederla y administración solo la visualiza. El libro rechaza cambios
  y borrados en la propia base de datos.
- Eventos `support.access_granted`, `support.access_revoked` y
  `admin.platform_cost_recorded` identifican actor y ámbito sin guardar contenido
  del cliente. No hay suplantación ni mutación genérica.
- CFO probado con coste real, previsión y abono: solo real+ajuste alimentan 18 € de
  coste observado, 81 € de contribución y 81,8% sobre 99 € de MRR; la previsión de
  100 € permanece separada.
- Términos ampliados y versión legal 2026-08-08. Es cobertura funcional y de copy,
  no validación jurídica; identidad y revisión profesional siguen bloqueando alta.
- Suite completa: **426/426** en 256 segundos. Ruff y migraciones focalizadas verdes.
  Las trazas de proveedores y backups son fallos adversos simulados.

## 2026-08-08 — perfil documental, presupuesto trazable y OCR trilingüe

- Migración 42 compatible con SQLite/Postgres: pie documental, condiciones y
  validez predeterminada por negocio; notas y evidencia de decisión en presupuestos.
  Subir/bajar el esquema y el histórico de cobros parciales pasan sus pruebas.
- PDF de presupuesto verificado desde negocio y portal. El token de un cliente no
  puede descargar el presupuesto de otro; aceptar registra `client_portal` y una
  huella SHA-256, y crea una única factura borrador conservando las notas.
- OCR privado con detección `cat/spa/eng`, orientación, escala y contraste; importes
  probados con «Import total», «Importe total» y «Amount due». Railpack solicita el
  paquete catalán y el estado del servidor expone si están los tres idiomas.
- Suite completa: **424/424** en 260 segundos. Ruff y pruebas focalizadas verdes.
  Las trazas de Stripe, Meta, correo, backup e IA son caídas adversas simuladas.
- Pendiente externo: desplegar esquema 42 y validar precisión/latencia con un corpus
  real representativo; una suite sintética no mide calidad OCR de fotos deficientes.

## 2026-08-08 — diagnóstico técnico privado por cuenta

- El administrador abre una cuenta desde el centro de mando y recibe únicamente
  activación, estados de integración, recuentos y distribución de colas/documentos/
  facturas. La consulta no recupera nombres de clientes, importes, conceptos,
  mensajes, archivos ni credenciales.
- La ruta reutiliza la autenticación reforzada del admin —Google OAuth obligatorio
  en producción— y cada apertura registra actor, negocio afectado, `request_id` y
  modo `read_only` en la bitácora append-only encadenada.
- Prueba específica verde: administrador autorizado obtiene 200, el contenido
  sensible sembrado no aparece, un usuario ordinario recibe redirección y el evento
  auditado identifica actor y negocio. Suite completa: **423/423**; Ruff,
  `compileall`, verdad del proyecto y diff verdes.
- La primera pasada completa encontró únicamente un `WinError 32` de Windows al
  limpiar la base temporal de una prueba OCR después de ejecutarla. La prueba
  afectada pasó al repetirla aislada y la segunda suite completa terminó 423/423;
  no hubo fallo funcional ni se modificó el producto para ocultar la incidencia.
- Falta recorrido visual autenticado tras desplegar. No se habilita mutación ni
  suplantación: requiere diseñar primero consentimiento temporal y permisos finos.
- CI remoto verde: 423 pruebas, migraciones, auditoría de dependencias y humo
  PostgreSQL. Producción respondió `/health` y `/ready` con release `8e9f9c412880`
  y esquema 41; queda pendiente únicamente el recorrido visual autenticado.

## 2026-08-08 — archivo documental común para titular y gestoría

- El titular navega por año, trimestre, ingresos, gastos, tickets, pendientes y
  otros con los mismos cálculos de fecha efectiva que el expediente profesional.
  Búsqueda y estado se aplican sobre el período seleccionado; no crean carpetas ni
  copias físicas divergentes.
- PDF e imágenes ofrecen una primera página acotada en un endpoint autenticado con
  `no-store`; abrir el original sigue disponible. Una sesión de otro negocio recibe
  403 incluso con identificadores válidos.
- 37/37 pruebas focalizadas de gestoría, documentos, PDF/OCR, backups y seguridad;
  suite completa **422/422** en 246 segundos. `ruff`, `compileall` y el aislamiento
  del endpoint están verdes.
- El primer commit rectificativo confirmó el humo PostgreSQL, pero Ruff detectó un
  `return invoice` residual. El commit posterior lo eliminó y el CI completo —suite,
  migraciones y humo PostgreSQL— terminó verde.
- Falta recorrido visual real de escritorio/móvil; no se usa navegador automatizado
  por el cierre recurrente de la aplicación indicado por el founder.

## 2026-08-08 — rectificación segura y revisable de facturas emitidas

- La pantalla muestra la factura original, importe, causa, dirección del ajuste,
  diferencia de base, impuestos, serie y efecto total antes de crear nada. Si el
  período ya cambió, advierte que debe confirmarse el criterio con la gestoría.
- La operación crea un borrador por diferencias (`I`), nunca edita el original y
  exige una confirmación explícita. El borrador usa un editor propio y se puede
  revisar; la pantalla genérica F1/F2 ya no intenta abrirlo.
- La base de datos vuelve a validar original, estado, anulación y serie dentro de
  la transacción; impide dos borradores pendientes para el mismo original. R5 solo
  rectifica F2 y una F2 solo admite R5. La modalidad por sustitución se rechaza.
- Pruebas focalizadas: 5/5 verdes sobre series, API, revisión, PDF y Veri*Factu.
  Suite completa: **421/421** en 277 segundos. `compileall` y `git diff --check`
  verdes. Los logs de caídas externas son escenarios adversos simulados.
- El humo PostgreSQL quedó verde. Ruff detectó un retorno residual en el endpoint
  nuevo; el commit documental posterior lo corrigió y repitió el CI completo en
  verde. Falta recorrido visual real tras desplegar.

## 2026-08-08 — actualización de seguridad de pypdf

- El CI detectó CVE-2026-71852 y CVE-2026-71870 en `pypdf 6.14.2` antes de
  ejecutar la suite. Se elevó el mínimo y el lock a `6.15.0`, versión corregida
  indicada por `pip-audit`; no se añadió ninguna excepción ni se ocultó el aviso.
- `uv run pip-audit`: ninguna vulnerabilidad conocida en dependencias publicadas;
  el paquete local `noesis` se omite porque no existe en PyPI.
- 40/40 pruebas focalizadas de lectura/OCR de PDF, facturas recibidas, copias y
  endurecimiento verdes con el lock nuevo. El humo PostgreSQL del primer commit ya
  había terminado verde; el CI completo se repetirá con la corrección.

## 2026-08-08 — puerta de acceso por tipo de relación

### Qué se probó y con qué resultado

- La cabecera pública lleva a `/acceso`, que presenta únicamente
  «Autónomo o empresa» y «Gestoría» y deriva a los dos logins ya existentes; el
  cliente final se explica como acceso por enlace privado, no como otra cuenta.
- `/app` sin sesión conduce al selector. Las sesiones titular y profesional siguen
  usando claves diferentes y no se ha unido ni relajado ninguna autorización.
- La solicitud de gestoría pide despacho y tamaño aproximado de cartera, se guarda
  como interés profesional y no crea `gestoria_account` ni acceso a ningún negocio.
- Pruebas focalizadas de SEO/rutas, solicitudes y endurecimiento: **35/35** verdes
  mediante `unittest`. El entorno local no incluye `pytest`; no se instaló una
  dependencia solo para ejecutar pruebas que ya funcionan con la biblioteca base.
- Suite completa: **417/417** pruebas verdes en 269 segundos; los logs de caídas de
  IA, Stripe, Meta, correo, backup y Veri*Factu son escenarios adversos simulados
  por las propias pruebas. `compileall`, `check_project_truth.py` y
  `git diff --check` también verdes.

### Límite visual y de publicación

- No se abrió navegador automatizado por el cierre recurrente de Codex indicado por
  el founder. Falta captura real de escritorio/móvil después del despliegue.
- Producción quedó verificada con release `b4f502bdb831` y esquema 41. `/acceso`,
  `/gestoria/login` y `/solicitar-acceso?perfil=gestoria` responden y contienen las
  decisiones/copy esperados. El CI completo y el humo PostgreSQL están verdes.

## 2026-08-07 — jerarquía y navegación del expediente de gestoría

### Qué se probó y con qué resultado

- **Evidencia de partida:** ocho capturas reales del founder mostraban una cartera
  correcta, pero el expediente reunía resumen, archivo, diez modelos, perfil,
  comparativa, ZIP y solicitudes en una sola página. La navegación sticky llegaba a
  superponerse al contenido y todas las secciones tenían un peso parecido.
- **Separación real:** el servidor solo admite `resumen`, `documentos`, `impuestos`,
  `periodos` o `solicitudes`; cualquier otro valor vuelve a Resumen. Cada vista
  renderiza su tarea y no deja debajo el resto del expediente.
- **Contexto preservado:** cambiar el período, guardar el perfil fiscal, validar un
  documento o enviar una solicitud conserva la pestaña, el año, el trimestre y el
  filtro documental aplicable. Los valores se vuelven a validar en el servidor.
- **Regresión:** 14/14 pruebas de `GestoriaTestCase` y suite completa **415/415**;
  Ruff verde en router y prueba modificada. Se verificó además que Documentos no
  renderiza Impuestos y viceversa, sin romper la previsualización aislada.
- **CI y despliegue:** los commits `9db728c` y el reintento vacío `4fd5f15`
  completaron en verde tests/migraciones y humo PostgreSQL. Railway marcó ambos
  despliegues como fallidos antes de sustituir la release; producción siguió sana
  con `0341986290f2` y esquema 41. No se confunde `main` verde con publicado.

### Límite visual

- Las ocho capturas aportadas se inspeccionaron como evidencia del estado anterior.
  No se abrió el navegador automatizado porque el founder ya identificó que esa
  acción cierra Codex. El QA visual posterior queda bloqueado hasta disponer de
  capturas del candidato desplegado en escritorio y móvil.

## 2026-08-07 — cartera fiscal y documental para gestorías

### Qué se probó y con qué resultado

- **Auditoría de partida:** las cuatro capturas reales del founder confirman login,
  cartera, ficha, períodos y solicitudes en Chrome. La estructura era legible y
  coherente con la marca, pero demasiado vacía, mensual y sin una tarea fiscal
  completa; el nuevo flujo conserva el sistema real y no crea una demo paralela.
- **Aislamiento:** el perfil fiscal solo puede actualizarlo una cuenta con acceso
  activo al negocio. La previsualización vuelve a validar cuenta, relación y
  `business_id`; pedir el documento de otra empresa devuelve 403.
- **Vista previa segura:** imágenes se sirven con caché privada desactivada; un PDF
  se rasteriza en servidor a JPEG, solo primera página, sin iframe/plugin y con
  techo de 2,5 millones de píxeles. El original conserva descarga separada.
- **Cálculo:** una factura emitida de base 100/IVA 21 y una recibida de base 100/IVA
  21 producen IVA previo cero. La factura recibida entra tanto en IVA soportado como
  en costes; si faltan base o cuota, el borrador declara el dato incompleto.
- **Flujo profesional:** render real de cartera, ficha, filtros de documentos,
  borradores fiscales, perfil y vista anual mediante FastAPI/TestClient. El portal
  sigue siendo de lectura/validación: no presenta impuestos ni mueve dinero.
- **Pruebas:** Ruff verde; 281/281 backend y 134/134 del resto de módulos, total
  **415/415**; 14/14 de `GestoriaTestCase`, incluidas tres regresiones nuevas;
  ciclo SQLite 0 → 41 → 0 → 41, `compileall` y `check_project_truth.py` verdes.
- **Publicación:** GitHub Actions completó en verde el candidato `2d14e2b`.
  Producción respondió 200 en `/health` con release `2d14e2b6f3b8` y en
  `/ready` con el mismo release, estado `ready` y esquema 41.

### Qué no se ha probado

- No se abrió un navegador automatizado porque las sesiones anteriores de la app se
  cerraban al usarlo. Las capturas aportadas son evidencia del flujo anterior, no
  QA visual del rediseño ya desplegado; hay que revisar escritorio y
  móvil con la demo real.
- Los modelos son una primera lectura, no una confección oficial. Faltan validación
  con despacho, prorrata, regímenes especiales, operaciones intracomunitarias,
  ajustes de Sociedades y pagos efectivamente presentados en períodos anteriores.

## 2026-08-07 — login de gestoría detrás del proxy de Railway

### Qué se probó y con qué resultado

- **Regresión reproducida:** un `POST /gestoria/login` podía recibir
  `{"error":"origen no autorizado"}` porque el navegador enviaba el origen público
  y Railway podía entregar al contenedor un `Host` privado o con puerto. La
  comparación anterior era textual y no entendía esa frontera de proxy.
- **Segunda evidencia real:** aunque el cliente HTTP sintético entró correctamente,
  Chrome volvió a mostrar `origen no autorizado` sobre el release `2a7c59a5cfbc`.
  Por tanto, la primera validación no se consideró suficiente ni el incidente
  cerrado. La corrección posterior prioriza `Sec-Fetch-Site: same-origin`, cabecera
  controlada por el navegador, antes de interpretar el `Host` interno del proxy.
- **Caso legítimo:** `Origin: https://bynoesis.com` con un `Host` privado de Railway
  autorizado atraviesa la guardia y llega al flujo normal de credenciales.
- **Casos hostiles:** `https://evil.example`, un puerto HTTPS no estándar, un origen
  mal formado y `Sec-Fetch-Site: cross-site` continúan en 403. No se confía en
  `X-Forwarded-Host` ni se habilitan comodines.
- **Cobertura de producto:** 28/28 pruebas focalizadas verdes: perímetro de
  seguridad, demo completa y `GestoriaTestCase` para cuentas profesionales reales,
  dos empresas invitadas sin mezcla, revocación, paquetes, correo y portal.
- **Pruebas:** 13/13 del módulo de seguridad; 61/61 de demo, plataforma, accesos,
  operaciones y readiness; 60/60 de web/documentos/correos/backups; 278/278 de
  backend. Total **412/412** ejecutadas por módulos. Ruff verde. La ejecución
  monolítica alcanzó el límite local de diez minutos sin registrar fallos; la misma
  batería separada por módulos terminó íntegramente en verde.
- **Producción después del cambio:** `/health` y `/ready` devuelven 200 con el
  release `53d7f83da282` y esquema 40. Un `POST` real con origen propio llega al
  flujo normal y responde 303; el mismo `POST` con `https://evil.example` responde
  403. El login con la cuenta demo devuelve 303 a `/gestoria`, la cartera responde
  200 con dos empresas y el logout vuelve en 303 a `/gestoria/login`. El CI general
  y el humo PostgreSQL del commit están verdes.

### Qué no se ha probado

- La segunda corrección todavía no se ha desplegado ni repetido desde Chrome. La
  sesión HTTP real confirmó autenticación, cartera de dos empresas y cierre, pero
  esa evidencia ya no se usa como sustituto de la prueba del navegador.

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
  explicación de alcance. La reejecución mostró que la antigua clave de demo local,
  ya registrada en la baseline, había cambiado de línea: también quedó exceptuada
  inline y se retiró solo esa huella histórica de la baseline. No se relajó el
  detector. Los primeros humos PostgreSQL no llegaron a descargar las Actions por
  un `Service Unavailable` de GitHub, sin ejecutar código de Bynoesis.

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
## 2026-08-02 (3) — catálogos por oficio y aviso del tipo reducido en obras de vivienda

### Qué se probó y con qué resultado

- **Migración 38**: `invoice_lines` gana `kind` ('servicio' o 'producto'). Sin ese dato
  no se puede saber qué parte de una factura es material, que es lo que decide si se
  sostiene el 10%. Las líneas ya emitidas quedan como 'servicio': **no se reinterpreta
  una factura cerrada**. Verificado el ciclo completo de migración y el roundtrip de
  bajada y subida, que al principio fallaba por intentar añadir la columna dos veces.
- **Catálogos por oficio** (`trades.py`): fontanería 10, electricidad 9, reformas 9,
  limpieza 5 y jardinería 6 conceptos, cada uno con su tipo y su IVA habitual. Cargar
  dos veces el mismo oficio **no duplica** nada y un oficio inexistente da error claro.
  Probado por API: `POST /api/{id}/oficios/reformas/cargar` creó los 9.
- **Aviso del 40%** (art. 91.Uno.2.10º LIVA), probado en tres casos reales:
  material al 28,6% → no avisa; material al 60% → avisa; factura entera al 21% → no
  avisa, porque la regla no aplica y no hay que molestar.
- **El aviso no decide**: comprobado que tras avisar los tipos siguen como los puso el
  titular (10% y 21%) y **la factura se emite igualmente** (`2026/0002`). Bynoesis no
  puede conocer las otras condiciones del reducido —vivienda de particular, terminada
  hace más de dos años—, así que la elección es del autónomo.
- El aviso viaja al detalle de la factura (`aviso_fiscal`) y al chat al crear el
  borrador.
- **Suite completa: 408 pasan, 71 subtests, ningún fallo.**

### Qué no se ha probado ni validado

- **La regla del 40% no la ha revisado un asesor fiscal.** Está implementada como
  advertencia informativa según el tipo general; hay supuestos particulares. Debe
  validarse antes de presentarla como garantía de cumplimiento.
- Los precios de los catálogos son orientativos y no se han contrastado con tarifas
  reales de mercado; están para ajustarlos con el cliente en la puesta en marcha.
- La migración 38 se probó en SQLite. **Falta ejecutarla en PostgreSQL** antes de
  desplegar.

## 2026-08-02 (2) — el error de emisión ofrece la salida legal, y prueba de concurrencia real

### Qué se probó y con qué resultado

- **«No puedo emitir» sin decir qué alternativa hay.** Al emitir una factura completa sin
  NIF ni domicilio del cliente, el mensaje enumeraba lo que falta y ahí terminaba. Si el
  cliente es un particular y el importe cabe en el límite general de 400 € del
  RD 1619/2012, la factura simplificada es una salida legal y el producto ya la soporta.
  Ahora el aviso la ofrece **solo cuando procede**: comprobado que con 150 € la sugiere y
  con 900 € no, porque ahí no sería legal.
- **El límite de 400 € estaba escrito dos veces** (`db.issue_invoice` y `tools`). Unificado
  en `_fits_simplified_invoice` para que aviso y validación no puedan contradecirse.
- **Ciclo completo de simplificada**, verificado con servidor real: «ticket de venta a
  Particular por grifo 150 €» crea F2 con el IVA calculado hacia atrás (base 123,97 +
  IVA 26,03), se emite **sin datos fiscales del destinatario** y recibe número de su
  serie separada `T2026/0001`. Por encima de 400 € se rechaza al crearlo.
- **Concurrencia de tres actores a la vez**, que era una duda abierta del fundador:
  36 peticiones simultáneas mezclando al titular creando facturas, la gestoría abriendo
  su portal y el trabajador su portal de fichaje. **Todas 200, ningún bloqueo de base de
  datos, ninguna traza de error.**
- **Numeración bajo emisión concurrente**, que es donde un fallo sería grave: 12 facturas
  emitidas en paralelo mientras la gestoría descargaba. Resultado: `2026/0001` a
  `2026/0013` **sin duplicados ni huecos**. La asignación de número es segura en
  transacción.
- **Portal del trabajador revisado**: `/t/{token}` con PIN, fichaje, trabajos del día,
  tareas de proyecto, parte de trabajo, historial de 30 días y el aviso legal del
  registro de jornada (art. 34.9 ET, conservación cuatro años). Responde 200.
- **Suite completa: 400 pasan, 71 subtests, ningún fallo.**

### Qué no se ha probado

- La concurrencia se midió sobre SQLite con WAL. En producción con PostgreSQL el
  comportamiento debería ser mejor, pero **no está medido en el entorno real**.
- Sigue sin probarse nada que dependa de credenciales externas.

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
- **Sección «cada momento de tu día» sustituida** por «Así se ve un día con Bynoesis»: una
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
  `TrustedHostMiddleware` lo rechazaba porque Bynoesis solo admitía el dominio público,
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
  facturación y Veri*Factu quedan como desarrollo propio de Bynoesis.

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
  panel (misma jerarquía y clases: nota de Bynoesis, cabecera, métricas, tarjetas,
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
  conserva la identidad de Bynoesis; no se copian marca, promociones, clientes ni
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
  del panel real: Parte de hoy, prioridad, métricas, agenda, trabajo de Bynoesis,
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
  cobros, documentos, equipo y lectura de Bynoesis coherentes entre sí.
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

## 2026-07-12 — Bynoesis persistente y entrada documental universal

- Migración 21 aplicada en SQLite: historial del asistente, memoria confirmada,
  clasificación documental trazable y protección de facturas históricas.
- Suite completa: 164 pruebas pasan, incluida separación por negocio, exportación
  RGPD, señales de clientes y confirmación de una factura recibida enviada por PDF
  en WhatsApp.
- Navegador: historial persistente comprobado entre Home y Clientes; el panel de
  Bynoesis abre desde cada pantalla y conserva el contexto de página.
- Documentos: subida web sin selector técnico; Bynoesis propone el tipo y la persona
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
