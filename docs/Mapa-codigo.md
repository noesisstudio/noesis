# Mapa de código

## Núcleo

- `src/noesis/db.py`: única frontera de datos. Toda operación de negocio filtra por
  `business_id`. Incluye proyectos, permisos, conciliación, outboxes y entregas a
  gestoría.
- `src/noesis/migrations.py`: esquema SQLite/Postgres. El candidato llega a 41;
  facturación profesional queda congelada al emitir, los límites de autenticación
  son compartidos y la bitácora de seguridad es append-only y encadenada por hash.
  El salto 32 → 33 suspende el guardián de facturas solo dentro del backfill
  transaccional, asigna serie/línea a las emitidas históricas y lo reinstala antes
  de continuar. La 39 separa las cuentas profesionales de gestoría de los usuarios
  titulares y exige una relación explícita y revocable por negocio. La 40 añade la
  marca persistente `is_demo` para bloquear en servidor las empresas ficticias. La
  41 añade un perfil fiscal por negocio, firmado por la cuenta de gestoría que lo
  actualiza, sin convertirlo en una declaración ni en autorización de presentación.
- `src/noesis/gestoria_workspace.py`: lectura trimestral/anual para despachos;
  reconcilia facturas emitidas, facturas recibidas, gastos y documentos, calcula
  borradores explicables, detecta huecos y candidatos 347, y genera una primera
  página segura de imágenes/PDF para previsualizar sin iframe.
- `src/noesis/demo.py`: siembra dos accesos dentro del producto real —autónomo y
  gestoría—, una segunda empresa para la cartera y un portal de cliente. Rellena
  todos los módulos con datos ficticios conectados y no reinicia producción.
- `src/noesis/security_center.py`: responsable CISO interno, determinista y de solo
  lectura; convierte controles, copias e intentos agregados en un parte accionable.
- `src/noesis/banking.py`: lectura local de CSV bancario, normalización, deduplicación
  y propuestas explicables de conciliación; nunca confirma un pago por sí solo.
- `src/noesis/tools.py`: herramientas que puede invocar el cerebro y flujo común de
  entrega de factura: PDF, canal habitual, email/plantilla WhatsApp, idempotencia y
  evento trazable.
- `src/noesis/verifactu.py`: huellas de alta y anulación, QR y XML nativos validados
  contra los XSD AEAT.
- `src/noesis/verifactu_client.py`: SOAP/mTLS directo, endpoints oficiales para
  certificado ordinario o sello, TLS mínimo, límite de respuesta e idempotencia de
  duplicados.
- `src/noesis/nlu.py`: cerebro local para órdenes rutinarias sin coste de LLM;
  separa ticket de gasto de ticket de venta F2 y entiende el trabajo a facturar.
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

## Web y acompañante

- `src/noesis/web/routers/pages.py`: además de las páginas públicas sirve
  `robots.txt`, `sitemap.xml` y `/favicon.ico`. La lista `_INDEXABLES` decide qué
  ve un buscador: si se añade una página pública, hay que incluirla ahí.
- `src/noesis/web/templates/404.html`: dirección inexistente con el diseño del
  sitio. El manejador de `server.py` sigue devolviendo JSON bajo `/api/` y
  `/webhook/`, que esperan datos y no una página.
- `src/noesis/web/server.py`: ensamblador FastAPI, seguridad, redirección al origen
  canónico y routers.
- `src/noesis/web/templates/site_base.html`: estructura compartida del sitio público,
  navegación responsive, llamada final y pie legal. Home, Precios, Equipo y Preguntas
  usan composiciones propias según su objetivo, sin replicar el panel interno ni
  inventar prueba social. También la usan las seis páginas legales: están en el
  sitemap, así que alguien puede aterrizar en ellas desde un buscador y debe encontrar
  el menú del sitio. Cada página aporta su título y su descripción; los textos legales
  además vacían la llamada final, porque no son sitio para vender. Aquí viven el
  canonical, la ficha de empresa para buscadores y el salto al contenido por teclado.
- `src/noesis/web/templates/landing.html`: la maqueta del producto reproduce pantallas
  del panel con `h2.demo-title`, no con `<h1>`: dentro de la portada son el retrato de
  una app, y competirían con el único encabezado real de la página.
- `src/noesis/web/templates/site_equipo.html`: página pública de equipo y principios;
  explica responsabilidades reales sin atribuir personas, clientes o credenciales
  todavía no verificadas.
- `src/noesis/web/templates/site_contacto.html`: contacto y reserva de reunión con el
  calendario incrustado. Es la única ruta donde la CSP permite `frame-src` de cal.com;
  el resto del sitio mantiene `'none'`.
- `src/noesis/web/templates/solicitar_acceso.html`: formulario público de solicitud de
  acceso. Producto se fusionó con la portada, que conserva las anclas `#como-funciona`
  y `#cumplimiento-legal` a las que redirigen los enlaces antiguos.
- `src/noesis/web/static/public-site.js`: hace navegable la cuenta simulada de la
  Home y sincroniza el selector mensual/anual, sus importes, ahorro, CTA y campos de
  checkout sin tocar datos reales.
- `src/noesis/adapters/billing.py`: catálogo mensual y anual compartido. Stripe usa
  un `price_id` distinto por plan y periodicidad; el anual cobra 11 meses y da 12.
- `src/noesis/web/deps.py`: aislamiento de sesión, modo consulta y guardia CSRF
  transversal. Una cuenta inactiva puede leer; toda mutación web/API devuelve
  redirección o HTTP 402. La evidencia `Sec-Fetch-Site: same-origin` del navegador
  tiene prioridad sobre el `Host` privado de Railway; sin ella, `Origin` pasa por
  la allowlist pública estricta y `cross-site` nunca se acepta.
- `src/noesis/web/routers/assistant.py`: conversación, memoria, permisos y registro
  de acciones de Noesis.
- `src/noesis/web/chat.py`: parte del día, plan operativo y acompañamiento. Resuelve
  por reglas, después por IA privada, proveedor compatible y Anthropic; los niveles
  externos comparten consentimiento y un crédito por mensaje.
- `src/noesis/web/templates/base.html`: capa persistente de Noesis: lectura real de
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
  PDF, entrega durable, historial, rectificación y anulación confirmada.
- `src/noesis/web/routers/account.py`: alta por prueba o contratación, sesión,
  Google OAuth, configuración operativa, checkout y cuenta; el alta pública falla
  cerrada en producción si falta identidad legal o autorización explícita y no
  expone el diagnóstico de proveedores en la API del cliente.
- `src/noesis/web/templates/onboarding_preferences.html`: aplica fiscalidad,
  factura, cobro, recordatorios, informes y gestoría antes de entrar al producto.
- `src/noesis/web/routers/account.py` (`/solicitar-acceso`) + tabla `access_requests`:
  recoge la solicitud pública con su plan de interés, valida, limita repeticiones por
  correo y descarta robots con un campo señuelo. No crea ninguna cuenta.
- `src/noesis/web/routers/admin.py` + `templates/admin.html`: diagnóstico técnico,
  parte CISO y evidencia de seguridad reservados al fundador; audita acceso y
  descarga de copias sin guardar contenido de clientes. Desde aquí se aprueban las
  solicitudes: el alta crea el negocio, arranca la prueba ese día y devuelve un
  enlace de un solo uso —reutiliza `password_resets`— para que el titular elija su
  contraseña, de modo que el equipo nunca llega a conocerla. También resume las
  visitas de la web del último mes.
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
  solicitudes y descarga por período; cada ruta vuelve a comprobar la relación de
  acceso antes de leer o escribir.
- `src/noesis/web/whatsapp.py`: texto, audio local, fotos/PDF, confirmaciones,
  trabajador y cola durable. Emisión y entrega usan una segunda confirmación,
  validación fiscal previa, PDF y canal habitual; la entrada y la salida se detienen
  en modo consulta.
- `src/noesis/web/routers/finance.py`: tesorería, conciliación CSV confirmada por el
  titular y calendario ICS privado/revocable.
- `src/noesis/web/backups.py`: copia, restauración descartable, manifiesto documental,
  salida S3 y comando `noesis-restore-check`.
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
  NIF fiscal y `automatic_tax`; las credenciales y el resultado fiscal se validan
  externamente antes de pasar a live.
- `src/noesis/adapters/`: Meta, email, pagos, voz, extracción y fiscalidad detrás de
  fronteras reemplazables. La extracción externa respeta la decisión de IA de cada
  negocio y conserva el clasificador local cuando está desactivada.
