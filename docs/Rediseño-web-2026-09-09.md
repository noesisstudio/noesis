# Rediseño estratégico de la web pública

Implementación del 9 de septiembre de 2026 sobre `4df5088816e13536593a53519ef7e483769e0d2d`.
Publicación en main y Railway autorizada por el founder tras la revisión local.
No modifica cuentas, facturas, WhatsApp, permisos o proveedores en producción.
Se conserva el cambio previo del socio sobre identidad/vinculación del teléfono.

## Resultado por página

| Página | Promesa y demostración | Siguiente paso |
| --- | --- | --- |
| Inicio | **Tu negocio, por WhatsApp.** Conversación primero; factura, ticket y cobros. Contraste con el papeleo, situaciones, panel navegable existente, equipo y confianza. | Prueba real existente; demo animada en la misma página. |
| Autónomos | **Menos papeleo. Más negocio.** Factura al acabar el trabajo y una jornada con agenda, presupuesto, ticket, factura y cobros. | Prueba y comparación de planes. |
| Gestorías | Cliente → WhatsApp → Noesis → expediente autorizado. Antes/después y captura del espacio real con datos demo. | Demo con el equipo o acceso profesional existente. |
| Contacto | Demo con el equipo y agenda en la propia página. Correo y acceso alternativo reales. | Calendario opcional y adaptable, sin abandonar la página. |

No se rediseña el panel operativo. La navegación y el pie públicos se comparten;
las páginas legales, precios, equipo y preguntas conservan su contenido propio.
El sistema Product Design se utilizó para inspeccionar antes/después y comprobar
jerarquía, contraste, densidad, controles y navegación en distintos anchos.

## Hero y verdad del producto

La animación usa HTML renderizado en servidor, CSS y JavaScript local. Son tres
secuencias de 7,8 segundos, sin vídeo, audio reproducido ni llamadas a IA. El usuario
puede elegir caso, pausar y abrir un borrador ficticio sin validez fiscal. Se detiene
fuera de pantalla o al ocultar la pestaña. Con movimiento reducido muestra el
resultado estático; solo reproduce si lo pide el visitante. Una descripción fija
ofrece el equivalente accesible sin anunciar cada mensaje animado.

| Afirmación | Evidencia / límite aplicado |
| --- | --- |
| Facturas y presupuestos por texto | Rutas de chat, NLU y herramientas existentes. Se enseña un **borrador**, no un documento emitido sin confirmación. |
| Cliente e impuestos | Ejemplos completos con concepto y cliente ficticios; IVA calculado: 680 + 142,80 = 822,80. No se promete interpretación universal. |
| Audio | Burbuja de voz y copy específicos solo si `transcription.available()` está configurado. Esto no equivale a aceptación E2E del proveedor. |
| Fotos/documentos | Sin OCR disponible se enseña archivo guardado y revisión pendiente. Con capacidad configurada, lectura propuesta y confirmación. |
| Cobros y cifras | Consultas de los registros de la cuenta, no detección bancaria automática. |
| Gestoría | Espacio existente, acceso concedido y revocable, documentación por empresa/período. No sustituye criterio fiscal ni presenta impuestos. |
| VeriFactu | Registros, huellas y QR existentes; conexión AEAT necesita configuración y validación. Sin certificación inventada. |
| Prueba por WhatsApp | Solo se publica un número si está definido explícitamente en `NOESIS_PUBLIC_WHATSAPP_DEMO_PHONE` y es válido. Nunca se reutiliza un teléfono interno. |

Sin canal público preparado, el CTA lleva al alta de prueba existente o a solicitar
acceso, según la configuración del producto. No se inventan testimonios: el parcial
`public_testimonials.html` queda sin contenido por defecto y exige aprobación
editorial de publicación. Antes de añadir citas hay que conservar evidencia y permiso.
El H1 tiene una única ubicación editorial; no se activan variantes A/B simultáneas.

## Calendario y privacidad

El enlace heredado `/bynoesis/sesion-de-estrategia` devolvía 404. Se verificó en el
perfil público el evento real:
[Agenda una llamada con nosotros](https://cal.com/bynoesis/agenda-una-llamada-con-nosotros).

El calendario aparece tras **Permitir y ver calendario**. Antes no existe iframe ni
petición a Cal.com. Es una decisión necesaria para mantener la privacidad; no se
fuerza carga de terceros por la mera visita. La autorización vive solo en esa página,
puede retirarse y no se guarda en cookie/localStorage. Cerrar el iframe no borra
cookies que hubiera guardado Cal.com: se explica cómo eliminarlas desde el navegador.

No se importa un SDK externo. El adaptador local usa el protocolo público de Cal.com:
comprueba origen exacto, ventana emisora y namespace; confirma `__iframeReady`, adapta
altura a `__dimensionChanged` y recoge únicamente la señal `bookingSuccessfulV2`.
Hay enlace alternativo si el servicio tarda o no carga. CSP permite frames de Cal.com
solo en `/contacto`; mantiene `frame-src 'none'` en las otras rutas. Se actualizan
Cookies, Privacidad y Encargado del tratamiento, sin cambiar la versión de aceptación
de las condiciones de cuenta.

Se verificó disponibilidad real en móvil y escritorio, sin enviar una reserva.
El evento de reserva se probó con un emisor simulado: no afirma asistencia ni
confirmación definitiva. La aceptación real de una reserva y su correo corresponde
a una prueba humana coordinada para no ocupar una cita sin necesidad.

## Medición para la empresa

Se conservan las visitas agregadas. Los eventos se guardan por día/página/nombre en
el mismo contador, con prefijo reservado `@event:`; se excluyen de los totales de
visitas. No hay nueva migración. Administración → Marketing muestra ambos separados.

Eventos: `hero_whatsapp_cta`, `hero_demo_started`, `hero_demo_completed`,
`autonomos_cta`, `gestorias_cta`, `cal_demo_started`, `cal_demo_booked`,
`pricing_click`, `contact_whatsapp`, `final_cta`.

Solo se aceptan las cinco rutas comerciales enumeradas y nombres cerrados. Cada
evento se envía una vez por carga de página; sin cookies, query, IP, cuenta, mensajes
ni detalles de reserva. Payload máximo 256 bytes, origen comprobado, 300 eventos/minuto
por proceso y fallo de medición no bloqueante. La escritura se delega fuera del
bucle asíncrono. Se corrige la exclusión accidental de `/gestorias` por el prefijo
privado `/gestoria`.

**Interpretación:** no son usuarios únicos ni un embudo individual ni cifras
antifraude. `hero_whatsapp_cta` cuenta el CTA principal aunque la alternativa sea
el alta de prueba; consultar configuración antes de llamarlo «WhatsApps abiertos».
El límite global puede perder muestras durante tráfico alto. No tomar decisiones
de ingresos sobre estos contadores como si fueran cobros confirmados.

## SEO y rendimiento

| Ruta | Title antes del sufijo «Bynoesis» | Datos estructurados |
| --- | --- | --- |
| `/` | Tu negocio, por WhatsApp. Gestión para autónomos | Organization y WebSite existentes + FAQPage |
| `/autonomos` | Gestión y facturación por WhatsApp para autónomos | FAQPage + BreadcrumbList |
| `/gestorias` | Software para gestorías: documentos y clientes ordenados | FAQPage + BreadcrumbList |
| `/contacto` | Reserva una demo de Noesis | BreadcrumbList |

Descripción específica por ruta, canonical limpio, OpenGraph/Twitter, un H1 y
enlaces internos. FAQ visible y JSON-LD salen de la misma fuente. No se añaden
reseñas, estrellas, LocalBusiness ni promesas de posicionamiento. FAQPage describe
contenido; no garantiza resultados enriquecidos ni menciones en buscadores de IA.

CSS nuevo ~20,7 KB (4,0 KB gzip), animación ~5,1 KB (1,8 KB gzip), calendario
~3,7 KB (1,6 KB gzip), cargado solo en Contacto. Sin nuevas dependencias de runtime.
Captura real de gestoría en WebP: 56.856 bytes, con dimensiones y carga diferida.
Fuentes locales, preload existente y assets versionados. La demo completa existente
queda dentro de un desplegable; no sustituye ni pesa visualmente en el hero.
Altura reservada para la animación, incluidos tamaños de audio, y transiciones de
opacidad/transformación. Se pausa el reloj al salir de vista y se evitan escrituras
DOM en frames sin cambios. Los tamaños gzip son comparaciones locales, no una
promesa de compresión configurada en producción.

No se ha medido CrUX/Core Web Vitals de campo: requiere datos tras la publicación.
La revisión local de geometría no se presenta como un resultado de LCP/INP/CLS real.

## Archivos principales

- `src/noesis/web/templates/{landing,site_autonomos,site_gestorias,site_contacto,site_base}.html`.
- `src/noesis/web/templates/partials/public_{conversation,product_demo,faq,testimonials}.html`.
- `src/noesis/web/static/public-{marketing.css,marketing.js,calendar.js}` y `gestoria-public-preview.webp`.
- `src/noesis/web/public_marketing.py`, `routers/pages.py`, `deps.py`, `server.py`.
- `src/noesis/{config,db}.py`, `routers/admin.py`, `templates/admin.html`.
- `templates/{cookies,privacidad,encargado-tratamiento}.html`.
- `tests/test_public_marketing.py`, `tests/public_{marketing,calendar}.test.cjs`, ajuste del contrato en `test_backend.py`.
- `pyproject.toml`: incluir plantillas/assets en la distribución, ausentes en el wheel anterior.
- `.github/workflows/ci.yml`: ejecutar contratos JavaScript sin servicios externos.

## QA y evidencia

Resultado final: **767 pruebas Python superadas** (616,408 s) y dos contratos
JavaScript superados. Build wheel verificado (167 archivos, assets presentes),
Ruff, Bandit y comprobador de estado en verde. El cambio del registro cerrado
encontrado en la primera ejecución se corrigió antes de repetir la suite completa.

Ver el resultado final de ejecución en [[Registro-QA]]. Capturas en
`docs/qa/redesign-2026-09-09/`, con antes y después. Revisadas las cuatro rutas en
320, 390, 768 y 1440 px; controles de menú, ejemplos, pausa, modal, panel existente
y calendario. Sin desbordamiento horizontal del documento ni errores de consola
en las rutas verificadas. No equivale a una certificación WCAG ni a un ensayo en
Safari/iPhone físico. Se prueba automáticamente movimiento reducido y filtro de
mensajes del iframe, incluidos emisor falso y revocación.

## Riesgo, despliegue y vuelta atrás

Riesgo principal: copy comercial, adaptación del proveedor externo y regresiones de
presentación. No cambia la ejecución de gestiones ni el esquema 55. No se provisionan
servicios ni se activa audio/OCR para clientes. No hay cambios de esquema ni
migraciones manuales. El despliegue usa el proceso habitual de Railway, incluido
su comprobador de migraciones existente. El founder autoriza commit y push a main;
el resultado del despliegue se comprueba después de publicar, no se presupone.

Rollback de código por revert normal del commit de esta tarea, sin reescribir historia.
Los contadores no afectan datos de negocio. Si se vuelve a código anterior que no
excluye `@event:`, conservar esa exclusión o exportar y retirar exclusivamente esos
contadores antes de interpretar visitas. No purgar tablas de negocio. Tras despliegue
autorizado: comprobar las cuatro rutas, CSP, assets, calendario opt-in y contadores
en Administración, manteniendo los límites externos del producto.

## Dependencias externas reales

- Número público dedicado y validado para una demo abierta de WhatsApp.
- Prueba de audio/OCR/Meta reales antes de tratarlos como disponibles operativamente.
- Testimonios auténticos con evidencia y permiso, si se decide publicarlos.
- Reserva coordinada de Cal.com y recepción del correo, más revisión legal profesional.
- Safari/iPhone físico y métricas de campo después de publicación autorizada.

## Referencias consultadas

Estructura de comunicación, no copia de diseño/copy:
[Holded para autónomos](https://www.holded.com/es/autonomos),
[Quipu para autónomos](https://getquipu.com/es/autonomos).
Integración: [Cal.com, incrustar eventos](https://cal.com/help/embedding/embed-events)
y [código del protocolo](https://github.com/calcom/cal.com/tree/main/packages/embeds/embed-core/src).
Privacidad: [Guía de cookies de la AEPD](https://www.aepd.es/guias/guia-cookies.pdf).
Fiscalidad: [AEAT, declaración responsable de sistemas de facturación](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/certificacion-sistemas-informaticos-declaracion-responsable.html).
