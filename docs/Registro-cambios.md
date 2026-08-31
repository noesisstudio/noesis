# Registro de cambios

Bitácora cronológica obligatoria de modificaciones del repositorio. Su objetivo es
permitir responder rápido a cuatro preguntas cuando algo falla: **qué cambió, qué
área puede haberlo causado, cómo se verificó y cómo se puede aislar o revertir**.

No sustituye `Registro-QA.md` (evidencia detallada), `Estado-actual-main.md`
(fotografía del producto) ni Git (diff exacto). Los conecta.

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
  página; textos sin marcadores, verdad del proyecto y `git diff --check`.
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
  y devolver la marca a la misión aprobada: Noesis lleva la oficina, quita ruido
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
- **Objetivo:** dar a Noesis un paquete de branding profesional y reproducible para
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
  original. En ese caso Noesis rechaza el mensaje; nunca intenta deducir el negocio
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
  Google el nombre y el logo de **Noesis** solo se muestran tras publicar la app y
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
  conecta su numero desde la web del proveedor. **Noesis no lo usa**: verificado por
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
  del founder con el remitente «Noesis». Queda demostrado que la clave es valida, que
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
  necesitara usar Noesis para su propio negocio, el enlace "Mi panel de negocio" se lo
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
  configuración de portal o catálogo fiscal incompatible. Si crearla falla, Noesis
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
  si tampoco abre, Noesis muestra un fallo sin aplicar cambios ni cargos.
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
- **Riesgo/punto probable de fallo:** si el portal no está configurado, Noesis falla
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
  técnica mantenible, sin prometer reseñas, frescura ni capacidades que Noesis no
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
  - `docs/Noesis-Modelo-Economico.xlsx` (nuevo): diez hojas con formulas vivas
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
- **Objetivo:** separar el canal interno de Noesis de la recepción comercial de cada
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
  lectura fiscal, manteniendo a Noesis como canal compartido con el autónomo.
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
