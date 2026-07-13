# Decisiones

Registro de decisiones importantes y su porqué (las más recientes arriba).

## Cierre controlado y aprendizaje explicable (2026-07-13)

- El parte de campo es operativo y separado del fichaje laboral append-only.
- Terminar prepara solo un borrador; emitir y enviar requieren al autónomo.
- La conformidad guarda fuente, momento y huella, sin prometer validez jurídica
  absoluta.
- Preferencias confirmadas prevalecen sobre patrones observados y son corregibles.

## Las integraciones se eligen por negocio; lo local nunca se apaga (2026-07-13)

Noesis separa capacidad interna de servicio externo. Una cuenta nueva empieza con
la IA en la nube desactivada y puede activarla desde Ajustes; una cuenta anterior
sin preferencia conserva el comportamiento previo para no romper su operativa. Al
desactivarla, el cerebro de reglas, OCR y clasificación heurística continúan dentro
del servidor. No se guardan claves de proveedor en `integration_settings`.

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
Cerebro local por reglas para lo rutinario (gratis, interno) + IA en la nube solo
para lo complejo. Motivo: por debajo de ~500M tokens/mes no compensa auto-hospedar.
Ver [[Investigación]] y [[Arquitectura]].

## Mínimas dependencias externas
Hash de contraseñas con stdlib (PBKDF2), Chart.js servido en local, sin Tailwind.
Motivo: coste, privacidad y control. Ver [[Arquitectura]].

## No reconstruir Verifactu
Se integrará vía API de un proveedor homologado (Holded/Quipu) en vez de
construir la parte regulada. Ver [[Fiscalidad]].

## Marca
Paleta del logo: verde bosque #14463b + teal #2e8b74 + crema #f4f1e8. Dominio
previsto: bynoesis.com. Ver [[Producto]].
