# Mapa de código

## Aprendizaje supervisado — 8-sep

`learning.py` prepara equivalencias literales, diálogo de factura y ofertas de
aprendizaje; `chat.handle` conserva el interceptador de revisión antes de herramientas.
`action_review.py` aporta resultado/propuesta para no aprender de una operación
fallida. `agent.py` excluye `language_rule` del prompt de sistema.
Persistencia existente: `business_memories`, `whatsapp_pending_actions` con prefijos
`learn:`/`clarify:`, `product_events`. API GET de informe en `routers/assistant.py`.
Sin esquema nuevo; flags dependientes y apagados. Véase el runbook de aprendizaje.

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
  `docs/Analisis-unit-economics.ipynb`.
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
  `robots.txt`, `sitemap.xml` y `/favicon.ico`. La lista `_INDEXABLES` decide qué
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
  equipo, horas y costes.
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
  bajo demanda sin duplicar ficheros.
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
- `scripts/build_estado_xlsx.py`: genera `docs/Estado-Bynoesis.xlsx` leyendo los
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
