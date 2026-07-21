# Estado actual del producto

> Lectura humana del estado. La fuente verificable para migración, pruebas, precios,
> política de suscripción y publicación es [`project-state.json`](project-state.json).
> Los pendientes solo viven en [[Tareas-vivas]].

## Producto construido

- Noesis cubre el ciclo cliente → presupuesto → trabajo/proyecto → fichaje y costes
  → factura → cobro, aislado siempre por `business_id`.
- La entrada documental es común para web y WhatsApp: clasifica tickets, facturas,
  presupuestos, contratos y albaranes; propone y pide confirmación cuando el efecto
  puede ser contable.
- Hay portales privados para cliente, trabajador y gestoría; el fichaje y Veri*Factu
  conservan registros inmutables.
- El cerebro funciona por capas: reglas locales, compositor interno, servicio privado
  compatible, proveedor externo compatible y Anthropic como respaldo autorizado.
  Que falle una IA nunca apaga el producto local.
- Noesis aparece en todas las secciones con una lectura contextual, el motivo y el
  siguiente paso. La estructura de cada pantalla sigue siendo propia de su función;
  no existe una plantilla universal de KPIs.
- Agenda ofrece un enlace privado y revocable para suscribirse desde Google Calendar,
  Apple Calendar u Outlook sin contratar una API. Cobros importa extractos CSV,
  propone coincidencias explicables y solo registra el pago cuando el titular lo
  confirma.
- Los correos confirmados se persisten antes de intentar SMTP, se deduplican y
  reintentan con backoff. Los errores de proveedores y el diagnóstico de preparación
  viven en administración; el cliente ve funciones y preferencias, no infraestructura.
- El panel del fundador incorpora un responsable CISO interno, determinista y de
  solo lectura. Resume controles con evidencia, presión de acceso agregada y eventos
  sin contenido de clientes. Las acciones administrativas quedan en una bitácora
  append-only encadenada por hash; producción exige Google OAuth para el admin.
- Cada backup se restaura al crearlo y, además, un simulacro semanal independiente
  vuelve a restaurar la última base y verifica el ZIP documental en un entorno
  descartable. La entrada documental admite ClamAV privado por streaming y puede
  fallar cerrado sin enviar archivos a una API externa.
- El alta comercial distingue con claridad entre **probar 14 días** y **contratar
  ahora**. Antes de entrar al panel recoge negocio, nivel de explicación, fiscalidad,
  estilo y vencimiento de factura, medios de cobro, recordatorios, informes,
  gestoría y WhatsApp. Esas elecciones se guardan en el producto y se aplican a la
  operativa; no son una encuesta decorativa.
- La facturación nativa admite borradores editables, varias líneas con cantidad,
  precio, descuento e IVA, series separadas para factura completa, simplificada y
  rectificativa, vencimiento configurable, duplicación y programaciones recurrentes.
  La emisión congela cabecera y líneas. La entrega genera el PDF al salir de la
  outbox de correo y el historial reúne emisión, remisión, visualización y cobros.
- WhatsApp distingue un ticket de gasto de un `ticket de venta` F2. Reutiliza un
  cliente habitual solo si la referencia es inequívoca, conecta trabajos cerrados
  con su borrador y exige otro SÍ para emitir o entregar. Tras confirmarlo asigna
  número, valida los datos obligatorios, genera el PDF y prepara email o plantilla
  WhatsApp; la misma factura alimenta KPIs, impuestos, cobros y gestoría.
- Una anulación Veri*Factu nunca borra la factura: exige confirmación escrita,
  conserva el alta, crea otro registro inmutable con huella oficial, lo encadena al
  anterior y lo remite mediante una cola durable independiente.

## Política comercial en el código actual

- Catálogo: **29 / 49 / 99 € al mes + IVA**.
- La prueba dura 14 días y permite operar con normalidad.
- La web pública permite probar o contratar cada plan en modalidad mensual/anual.
  Quien contrata configura primero el negocio y después revisa el plan antes de ir
  al checkout; quien prueba entra al panel sin tarjeta tras la misma puesta en marcha.
- Al caducar, cancelar o quedar un pago pendiente, el titular puede entrar y consultar
  sus datos, pero no crear, cambiar, enviar ni ejecutar automatizaciones.
- El bloqueo se aplica en servidor a web/API, portales, WhatsApp, colas y tareas
  programadas; no depende de ocultar botones.
- Pagos, transferencias, presentación fiscal, emisión definitiva, envíos sensibles y
  borrados irreversibles requieren confirmación específica del autónomo.

## Publicado frente a construido

La URL pública y la última comprobación constan en `project-state.json`. Los cambios
del código actual solo se consideran publicados después de fusionar, desplegar,
aplicar migraciones y repetir `/ready` y los flujos afectados. **Nunca se deduce que
algo está en producción porque exista en una rama o haya pasado tests.**

## Límites que siguen abiertos

- WhatsApp, Stripe, SMTP, Google OAuth, el proveedor privado de IA y AEAT están
  implementados detrás de adaptadores, pero necesitan credenciales y una prueba real
  extremo a extremo. La secuencia exacta está en [[Conectar-APIs]]. Stripe live
  requiere además cerrar cómo se aplica el IVA. La facturación es nativa y no se
  conecta a otro SaaS. El calendario bidireccional y la conexión bancaria automática
  siguen pendientes; la suscripción ICS y la conciliación CSV ya funcionan en local.
- La entrega de factura por WhatsApp requiere aprobar en Meta la plantilla
  `noesis_factura_lista`; el recorrido interno y la cola ya están construidos.
- Falta auditoría externa de seguridad, privacidad y fiscalidad, desplegar y probar
  ClamAV, restaurar una copia descargada del almacenamiento externo en otra
  infraestructura y pilotar con 3-5 negocios. El simulacro interno no sustituye esa
  prueba de desastre ni un pentest independiente.
- La memoria de cliente es explicable y corregible; no se promete aprendizaje autónomo
  perfecto ni decisiones legales/fiscales sin humano.
- Exenciones, no sujeción, identificación fiscal extranjera y subsanación de un
  registro rechazado todavía requieren desarrollo y validación fiscal antes de
  admitir esos casos. El 0% visible significa tipo cero, no exención.

## Regla para cualquier IA

Toda modificación de producto actualiza `project-state.json` y `Registro-QA.md`; si
cambia arquitectura, también `Mapa-codigo.md`, `Arquitectura.md` o `Decisiones.md`.
El CI ejecuta `scripts/check_project_truth.py` y rechaza una PR que cambie `src/noesis/`
sin esas actualizaciones.
