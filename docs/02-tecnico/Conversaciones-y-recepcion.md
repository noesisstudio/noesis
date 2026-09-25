# Memoria y recepción durable — candidato local

## Qué existe y qué cambia

Se mantienen el motor del chat, las confirmaciones versionadas, webhook_events,
la bandeja comercial `whatsapp_inbox` y la outbox. Se añade únicamente el estado
que faltaba: atribución de historial y persistencia de transporte antes de ejecutar.

`NOESIS_CONVERSATION_ISOLATION_ENABLED=false`: escribir actor en mensajes nuevos
no altera todavía las lecturas. Al activar, modelo, referencias e historial web
usan negocio + actor autenticado. No se mezclan web y WhatsApp ni otros usuarios.
El historial antiguo permanece exportable; no se adivina su propietario.

`NOESIS_WHATSAPP_INBOX_ENABLED=false`: el webhook conserva ejecución síncrona.
Al activar, firma/tamaño se validan antes de guardar mensajes normalizados en una
transacción. Solo después se acusa recepción. El scheduler consume cada 2 segundos
usando el procesador existente, sin descargar medios ni llamar IA en el webhook.

## Seguridad operacional

- FIFO por orden de recepción persistida, no por un orden inventado a partir del
  timestamp de Meta. Conversaciones distintas pueden progresar por separado.
- Reserva transaccional entre consumidores; IDs repetidos no duplican entrada.
- Payload vaciado al completar. Los errores solo guardan un código, no excepción
  ni contenido. El panel interno muestra el número de entradas en revisión.
- Si cambia el negocio vinculado antes de consumir, se detiene la entrada.
- Fallo o reserva abandonada (>15 minutos): revisión, sin reintento automático.
  Las siguientes entradas de esa conversación esperan; otras no se bloquean.
- Cola acotada a 10.000 no terminadas. Saturación/fallo de BD no devuelve éxito:
  el proveedor deberá reintentar. No sustituye un dimensionamiento con carga real.
- Los mensajes previos al vínculo pueden no tener business_id; no son accesibles
  por API de cliente. Los vinculados se exportan y borran con su negocio.

## Antes de activar

1. CI PostgreSQL: migraciones, rollback, restauración, reservas concurrentes.
2. Dos cuentas, dos usuarios y ambos canales: no arrastrar nombres ni propuestas.
3. Meta real: texto, PDF, foto, eventos repetidos, estados y caída del trabajador.
4. Preparar la resolución de incidencias por un operador autorizado: cotejar
   recibos, historial, documento y outbox; no reenviar un evento incierto por SQL.
   Este candidato NO incorpora un botón universal de reejecución.
5. Definir retención y alertado de pendientes/no vinculados; el candidato no borra
   automáticamente una orden no atendida ni la conserva por una política inventada.
6. Activar por separado en piloto, con métricas de espera y errores. No masivamente.

## Rollback

### Diagnóstico y tratamiento de incidencias

Recuperación limitada disponible: `python -m noesis.whatsapp_diagnostics
--business-id ID --recover INCIDENCIA --operator-id ADMIN`. Solo acepta
`routing_changed`: el motor no se ejecutó. Audita el intento antes de reencolar,
mantiene el orden y vuelve a comprobar el vínculo al consumir. Si no se ha
restaurado el vínculo, se detiene de nuevo. Exige acceso autorizado al servidor y
un usuario con is_admin; no es una API pública. Fallo de auditoría impide mutación.
`processing_failed` e `interrupted` siguen requiriendo investigación humana:
no hay reintento genérico ni cierre que libere confirmaciones antiguas.

Con acceso autorizado al servidor y al esquema 60:
`python -m noesis.whatsapp_diagnostics --business-id ID --limit 50`.
No migra ni consume la cola. Muestra contadores y hasta 200 incidencias, con
fecha, código de error y número de entradas posteriores esperando. No muestra
mensajes, teléfonos, IDs de Meta ni claves de conversación. Salida 1 si hay
revisión, 0 si no; un error de conexión/esquema no se disfraza de cola vacía.

Ante una incidencia, cotejar recibos de ejecución y outbox con el documento real.
No pasar `review` a `queued` por SQL: podría duplicar una escritura. Tampoco marcar
`done` sin más: las respuestas «sí» que esperan pueden confirmar propuestas viejas.
`interrupted` significa que expiró la reserva, no que el trabajador haya muerto;
se requiere detener/verificar ese trabajador antes de cualquier recuperación.
Todavía no hay recuperación automática segura: mantener el flag apagado hasta
completar procedimiento, retención y pruebas de fallo. Este diagnóstico es una
herramienta de soporte, no un cierre del pendiente de resolución.

### Volver a la versión anterior

Apagar ambos flags antes de revertir runtime; resolver o drenar las entradas
aceptadas primero. La migración 60 impide bajar con queued/processing/review.
La 59 conserva la columna nullable actor; la 60 conserva recibos completados.
Un downgrade completo a cero elimina tablas: solo en base descartable de pruebas.
No hacer rollback del webhook mientras queden entradas aceptadas sin atender.

## Límites honestos

No garantiza exactly-once para todos los efectos externos, no recupera
automáticamente una escritura incierta y no demuestra entrega real de Meta.
El estado por actor no sustituye todavía una máquina de estados transaccional
completa para todos los dominios. Sin prueba operativa, ambos flags siguen apagados.
