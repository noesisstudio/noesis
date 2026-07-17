# Decisiones

Registro de decisiones importantes y su porqué (las más recientes arriba).

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

## No reconstruir Verifactu
Se integrará vía API de un proveedor homologado (Holded/Quipu) en vez de
construir la parte regulada. Ver [[Fiscalidad]].

## Marca
Paleta del logo: verde bosque #14463b + teal #2e8b74 + crema #f4f1e8. Dominio
previsto: bynoesis.com. Ver [[Producto]].
