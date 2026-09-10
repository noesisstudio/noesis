# Agente operativo fiable de Bynoesis

## Qué se necesita realmente

Una IA más elocuente no acredita una operación ni conoce automáticamente el
estado del negocio. La aplicación necesita separar comprensión, planificación,
resolución de referencias, autorización, ejecución y comprobación del resultado.
No se promete comprensión universal ni aprendizaje autónomo sobre datos reales.

## Núcleo incorporado en este bloque

`conversation_plan.py` empieza a separar intención de efectos en facturación:
emitir, descargar para el titular y entregar al cliente no son la misma acción.
El plan no escribe datos. WhatsApp resuelve el documento con referencias reales,
foco del teléfono y citas verificadas; ante ambigüedad no ejecuta. La emisión
requiere confirmación y una huella del borrador/líneas revisada dentro de la
transacción. Las herramientas devuelven recibos; el texto del modelo no es prueba.

El precio con impuestos incluidos conserva el total acordado mediante desglose
decimal y asignación del céntimo residual del redondeo. Solo afecta creaciones
explícitas de una línea; no reescribe documentos emitidos. Los cambios posteriores
de líneas se siguen calculando como precios netos en el editor existente.

Diagnóstico de producción: espacio final en WHATSAPP_PHONE_ID impedía la subida
del adjunto. Normalizarlo permitió subir un PDF real a Meta, sin emitir ni enviar
al destinatario. Las credenciales y errores del proveedor no se muestran al usuario.

## Lo que todavía no está implementado por este bloque

- Un plan estructurado universal para agenda, gastos, presupuestos, clientes y
  proyectos. Siguen usando sus flujos existentes; no se sustituye todo el agente.
- Aclaraciones completas de múltiples turnos, cambio de tema, correcciones de
  importe/cliente y ejecución compuesta entre dominios con dependencias.
- Clasificador semántico con evaluación y umbral de abstención medidos. El
  proveedor existente puede proponer; no puede saltarse controles del producto.
- Evaluaciones de comprensión con modelo real y corpus representativo autorizado.
- Aprendizaje revisado: convertir incidentes en pruebas, evaluar una versión nueva
  y publicarla tras revisión; nunca cambiar permisos o reglas fiscales solo.

## Siguiente implementación y criterio de salida

1. Persistir planes versionados por negocio, actor y conversación: objetivo,
   entidades verificadas, datos faltantes, estado, confirmación y recibos.
2. Añadir al proveedor semántico un contrato de salida validado contra acciones
   permitidas; resolver nombres e identificadores en servidor, nunca confiar en
   IDs inventados. Ejecutar primero en modo observación, con flag apagado.
3. Trasladar un dominio cada vez al contrato, manteniendo adaptadores y permisos.
   Ningún fallo de interpretación puede repetir cobros, emisiones o comunicaciones.
4. Corpus ES/CA: creación, corrección, pronombres, citas antiguas, cambio de cliente,
   negación, duplicados, caída del proveedor, mensajes simultáneos y negocio ajeno.
5. Comparar resultados reales: documento, destinatario, importe, estado y recibo
   de entrega. Pasar regresión, prueba de PostgreSQL y piloto físico antes de
   ampliar cobertura o activar aprendizaje.

Esta base es un primer bloque comprobable, no un agente terminado para todos los
casos. No se entrenó un modelo propio ni se activaron proveedores nuevos.
