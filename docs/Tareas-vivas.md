# Tareas vivas

## Entrega de PDF y voz — 9-sep

- [x] Interceptar peticiones de PDF al titular antes de la IA y enviar documento
  real por Meta, con aislamiento, estado fiscal, nombre seguro y fallback veraz.
- [x] Impedir que una respuesta generativa confirme un adjunto inexistente.
- [x] Diagnóstico remoto de voz: ningún transcriptor está configurado.
- [ ] Provisionar y validar Whisper privado o configurar Groq antes de anunciar
  notas de voz como capacidad disponible.
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
- Cal.com aplazado. Detalle en [revisión de frentes](Revision-frentes-2026-09-07.md).

> Único listado vivo de pendientes. La fotografía verificable está en
> [`project-state.json`](project-state.json); planes y traspasos no duplican estados.

## P0 — publicar y pilotar con seguridad

- [ ] Ejecutar los seis P0 de
  [`cumplimiento/Plan-Datos-Servidores-Copias`](cumplimiento/Plan-Datos-Servidores-Copias.md):
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
