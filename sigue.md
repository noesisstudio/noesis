# sigue.md — por dónde seguir con las pruebas de WhatsApp

> Nota temporal del 1-oct-2026. **Cuando el founder diga «sigue», leer esto, borrar
> este archivo del repo (commit) y continuar.** El detalle de lo hecho está en
> `docs/Registro-cambios.md` y `docs/Registro-QA.md` (entradas del 30-sep y 1-oct).

## Prioridad que ha pedido el founder: el AUDIO

Quiere dedicar más tiempo a las notas de voz. Estado real:

- **La transcripción real nunca se ha probado de punta a punta.** WhatsApp Web no
  deja adjuntar el audio generado: el WAV lo rechaza («archivo no compatible») y el
  AAC se queda cargando. Lo que sí está probado es lo que pasa **después** de
  transcribir: ~60 frases escritas como las deja Whisper, por la ruta de nota de voz
  (`whatsapp._audio_to_text` simulado; helper `voz()` en `tests/test_charla_whatsapp.py`).
- Siguiente paso: conseguir un audio **ogg/opus** real (el formato de las notas de voz).
  No hay `ffmpeg` en el Mac (`brew install ffmpeg` lo resolvería: `say` → aiff → ogg
  opus) ni `faster-whisper`. Alternativa: que el founder mande 5–10 notas de voz
  desde su móvil y mirar en Railway qué texto transcribió Groq y qué contestó el bot.
- Probar con audio de verdad: ruido de obra, catalán y castellano mezclados, cifras
  («ciento veinte con cincuenta»), nombres propios de clientes, notas largas (>60 s),
  nota vacía o inaudible, y qué dice el bot cuando falla (`_VOZ_EXPLICACION`).
- Revisar `adapters/transcription.py`: idioma forzado (`WHISPER_LANGUAGE`), umbrales
  de «fragmento dudoso» y si el vocabulario del negocio (nombres de clientes) se le
  puede pasar a Whisper como `prompt` para que no los deforme.
- Regla que no se rompe: emitir por voz pide una segunda confirmación.

## Pendiente de comprobar en producción

- **Railway MCP se desconectó** tras reiniciar el Mac: el último despliegue que vi
  funcionando en el WhatsApp real es `ce9c164`. Los commits `e9932fd`, `75ab452` y el
  de esta nota no los he verificado en producción (fichaje de trabajadores, número de
  documento en letra, «emite la 1» y PDF por enlace en el chat web).
- La web de producción no está probada: no hay sesión iniciada y no meto contraseñas.
  En local (demo sembrada) sí: 15 páginas sin errores y chat web.
- El canal de **recepcionista** (clientes escribiendo al número del negocio) y los
  mensajes proactivos con plantilla no se han tocado.

## Fallos y huecos conocidos, sin arreglar

- **Orden de los mensajes**: dos mensajes seguidos se contestan a veces en orden
  distinto al de envío (el webhook no garantiza orden con
  `NOESIS_WHATSAPP_INBOX_ENABLED` apagado). Un «sí» rápido puede llegar antes que la
  tarjeta a la que responde.
- **Lentitud en frío**: la primera respuesta tras un rato tardó más de 9 segundos.
- **Respuestas siempre en castellano**: el cerebro local entiende catalán, pero
  contesta en castellano aunque el negocio esté en catalán.
- Por WhatsApp todavía no se hace: aceptar / rechazar / pasar a factura un
  presupuesto, facturas con varias líneas («3 horas a 40 euros la hora»), asignar un
  gasto a una obra o cliente, mover o cancelar una cita. Hoy se explica y se remite a
  la web.
- Dependabot avisa de **6 vulnerabilidades** en dependencias (5 altas, 1 moderada).
  Hay una tarea aparte sugerida; hace falta `pip-audit`.

## Datos de prueba que quedaron en la cuenta real del founder

- En **Documentos**: el ticket «Ferretería La Llave» (foto), el mismo como sticker y
  el PDF «Suministros Eléctricos Levante». Archivados, no apuntados como gasto. Se
  pueden borrar.
- Un gasto «gasolina 45 €» del 30-sep que no supe verificar de dónde salió.
- La ficha «reformas martínez» tiene un NIF inválido (`481234129L`) y 13 facturas en
  borrador: desde ahora el bot no deja emitirle hasta corregirlo.
- No se emitió, cobró ni envió nada: todo se descartó con NO.

## Cómo retomar

1. `git pull`, leer este archivo y borrarlo (`git rm sigue.md`, commit).
2. Suite completa (5 min): ver `noesis-arranque-local` en la memoria. Última: 1355.
3. Método de prueba: memoria `noesis-probar-whatsapp` (real por WhatsApp Web en
   Chrome, simulador con `handle_inbound`, fotos y PDF por el selector de archivos).
