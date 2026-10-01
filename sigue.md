# sigue.md — por dónde seguir (sesión del 1-oct-2026, tarde)

> Nota temporal. **Cuando el founder diga «sigue», leer esto, borrarlo del repo
> (commit) y continuar.** El detalle de cada cambio está en `docs/Registro-cambios.md`
> (entradas 11 a 19 del 1-oct) y `docs/Registro-QA.md`. Lo pendiente fijo está en
> `docs/Tareas-vivas.md` (sección «Pruebas de WhatsApp»).

## Qué se hizo en esta sesión

El founder subió el repo con otra cuenta de GitHub (xavier.gp2003); el remoto sigue
siendo `noesisstudio/noesis` y se trabaja en `main`, que se despliega solo en Railway.
Pidió arreglar lo de la nota anterior y «mejorar toda la aplicación», con permiso
total para subir. Todo lo siguiente está subido y desplegado salvo lo que se diga:

1. **Voz**: el aviso de fallo dice el motivo verdadero (nota larga, dudosa, Groq
   saturado) en vez de «mal configurado»; el chat web pasa el idioma del negocio.
2. **Presupuestos por WhatsApp**: aceptar (factura en borrador), rechazar, por
   número o por cliente. «Mis presupuestos» enseña el `#id`.
3. **Citas por WhatsApp**: cancelar (se marca `cancelado`, no se borra), mover,
   corrección «mejor a las 12», por día sin cliente. Agenda web la tacha.
4. **Facturas de varias líneas dictadas** («3 horas a 40 euros la hora y material
   45 euros»), IVA del negocio si no se dice.
5. **Gasto a una obra** («para la obra de X»).
6. **cryptography 47 → 50** (las 6 alertas de Dependabot). Producción la instaló.
7. **Prueba real por WhatsApp Web** (Claude in Chrome, chat «Bynoesis»): todo lo
   anterior funciona en producción. Encontró y se arreglaron:
   - «hazle un presupuesto a X…» buscaba el cliente «este cliente a X».
   - «no» a «¿creo su ficha?» contestaba «no hay ninguna propuesta pendiente».
   - La tarjeta de factura no avisaba de un NIF inválido hasta emitir.
   - «¿Cuánto he facturado este mes?» no decía el mes; a principio de mes ahora
     enseña también el anterior.
   - «k tngo q hacer oy» caía en la IA, que se equivocó de fecha y de agenda: ahora
     abreviaturas de móvil en local y fecha escrita entera en el prompt de la IA.
   - «Resumen de la semana» daba el mes: ahora lunes a domingo.
8. Pie de tarjetas sin «corregir:» (enseña a corregir hablando) y aviso de IVA que
   nombra el apunte incompleto.

## Cómo probar (método que funcionó)

- **Real**: el founder conecta Claude in Chrome escribiendo `@browser` en el chat de
  VS Code (en VS Code no se conecta solo). Abrir `web.whatsapp.com`, chat «Bynoesis».
  Leer respuestas con `javascript_tool`:
  `Array.from(document.querySelector('#main').querySelectorAll('[role="row"]')).slice(-4).map(r=>r.innerText).join('\n---\n')`.
  Escribir: clic en (900, 653) con la ventana a 1300×900, `type`, `Return`, esperar
  ~10 s. Todo lo que propone se descarta con «no».
- **Producción**: `curl https://bynoesis.com/ready` da el `release` desplegado.
  Railway MCP (proyecto «autonoms») para despliegues y registros.
- **Suite**: `NOESIS_SECRET=noesis-local-secret-fixed-32-characters-minimum
  NOESIS_DB_PATH=/tmp/noesis-tests.db .venv/bin/python -m unittest discover -s tests
  -p "test_*.py"` (~6 min). `scripts/check_project_truth.py --base-ref origin/main`
  antes de subir.

## Lo siguiente (en este orden)

1. **Seguir la ronda real por WhatsApp Web** con frases de autónomo: corregir lo que
   falle. Ya probado y bien: presupuestos, citas, varias líneas, gasto a obra,
   cobros, IVA, teléfono, agenda, «recuérdale a X que me pague», «que tinc demà».
   Sin probar aún: notas de voz, fotos de tickets, «envíale la factura 3 por
   correo», más catalán y más faltas de móvil.
2. **Audio real**: sigue sin probarse una nota de voz de punta a punta. Opciones:
   el founder manda 5–10 notas desde el móvil y se leen en Railway; o
   `brew install ffmpeg` y generar ogg/opus (`say` → aiff → ogg).
3. **Respuestas en catalán** cuando el negocio está en catalán (grande).
4. **Gasto a un cliente sin obra**: `expenses` no tiene `client_id` (migración).
5. **Orden de mensajes y lentitud**: mediana del webhook ~45 ms, p99 hasta 15 s
   (IA o transcripción en la propia petición). Lo arregla
   `NOESIS_WHATSAPP_INBOX_ENABLED`, pero activarlo es decisión del founder y antes
   hay que probarlo con Meta real.

## Datos de prueba en la cuenta real del founder

- Nada nuevo guardado en esta sesión: todas las propuestas se descartaron con «no».
- Siguen de antes: ticket «Ferretería La Llave», su sticker y el PDF «Suministros
  Eléctricos Levante» en Documentos; gasto «gasolina 45 €» del 30-sep; la ficha
  «reformas martínez» con NIF inválido (`481234129L`) y borradores; el presupuesto
  #8 (reforma de baño, sin enviar) y la cita de hoy «revisar el parque».
