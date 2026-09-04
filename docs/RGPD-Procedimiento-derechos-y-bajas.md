# Procedimiento de derechos, bajas y conservación

Versión interna: 2026-09-03. Responsable: dirección de Noesis hasta designar
formalmente una persona de privacidad.

## Entrada y registro

1. Las solicitudes llegan a la dirección publicada de privacidad. La baja del
   titular también puede iniciarse desde Ajustes, con contraseña y la palabra
   `BORRAR`.
2. Si la cuenta no tiene registros sujetos a conservación, el sistema puede
   ejecutar el borrado en cascada y eliminar los archivos después del commit.
3. Si hay facturas emitidas o registros de jornada, Noesis no simula un borrado:
   crea una fila en `privacy_requests`, devuelve una referencia, encola avisos al
   solicitante y al responsable, y registra un evento de seguridad.
4. Los reenvíos del formulario devuelven la misma solicitud abierta mediante una
   clave idempotente; no generan expedientes duplicados.

## Verificación y clasificación

1. Confirmar que quien solicita es el titular o una persona autorizada. Pedir solo
   información adicional proporcional; no solicitar un DNI completo por defecto.
2. Clasificar: acceso, rectificación, supresión, limitación, portabilidad,
   oposición o baja de cuenta.
3. Determinar si Noesis actúa como responsable o como encargado. Si la persona es
   cliente final de un negocio, trasladar la solicitud a ese responsable y ayudarle.
4. Anotar fecha, alcance, estado, decisiones y comunicaciones. El plazo ordinario
   del RGPD es un mes desde la recepción; cualquier ampliación debe justificarse y
   comunicarse dentro de ese primer mes.

## Resolución de una baja con conservación

1. Exportar la cuenta si el titular lo ha pedido.
2. Inventariar facturas, justificantes, jornada, litigios o bloqueos aplicables.
3. Aplicar la tabla de conservación validada por el asesor. Noesis no fija ahora
   plazos inventados en código.
4. Suprimir datos sin base de conservación; minimizar o seudonimizar lo que deba
   conservarse; limitar su acceso al motivo legal.
5. Documentar en el panel interno la actuación y el motivo. Cambiar el estado no
   ejecuta borrados automáticamente: evita que una etiqueta administrativa cause
   una pérdida irreversible.
6. Comunicar al solicitante qué se hizo, qué queda bloqueado, por qué y durante qué
   criterio temporal. Conservar prueba de la respuesta.

## Controles

- Revisar semanalmente la bandeja `Privacidad y bajas` del panel interno.
- No marcar `completed` sin nota y evidencia de ejecución.
- No enviar exportaciones por canales no verificados.
- Toda acción técnica irreversible requiere copia verificada, doble revisión y
  consulta SQL acotada por `business_id`.
- Una solicitud rechazada debe incluir fundamento y vías de reclamación.

## Lo que queda pendiente de validación profesional

- Tabla exacta de plazos por categoría y jurisdicción.
- Modelo de respuesta a cada derecho y política de identificación.
- Protocolo técnico de bloqueo, anonimización y purga programada.
- Decisión sobre conservación de copias y recuperación selectiva tras una baja.

