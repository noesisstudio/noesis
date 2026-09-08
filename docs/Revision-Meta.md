# Revisión del canal de Meta (WhatsApp Cloud API)

> Revisión completa del 2026-08-20 a petición del founder. Cubre webhook, firma,
> idempotencia, medios entrantes, cola de salida y las nueve plantillas.
> La versión filtrable está en [`Estado-Bynoesis.xlsx`](Estado-Bynoesis.xlsx),
> hoja «Meta (WhatsApp)». Para encender la cuenta, [[Conectar-APIs]] sección 4.

## Resumen en una frase

El canal está bien construido —firma verificada, idempotencia real, cola durable,
descarga de medios sin fuga del token— y tiene **un bloqueo que impide que los
cinco avisos al titular lleguen nunca**: mandan el mensaje entero dentro de un
único hueco de plantilla, y eso Meta ni lo aprueba ni lo envía.

## 1. El bloqueo: los proactivos al titular no son aprobables

`scheduler._deliver_template` compone el mensaje completo —varias líneas, con
emojis y saltos— y lo pasa como **un solo valor**:

```python
whatsapp.send_template(phone, template_name, [text], ...)
```

Eso choca con dos reglas de Meta a la vez:

1. **Una plantilla cuyo cuerpo es solo `{{1}}` se rechaza en la revisión.** El
   cuerpo tiene que llevar texto fijo; los huecos son para valores.
2. **Un valor no puede contener saltos de línea, tabuladores ni cuatro espacios
   seguidos.** Aunque la plantilla estuviera aprobada, el envío fallaría.

Afecta a `bynoesis_resumen_diario`, `bynoesis_cierre_dia`, `bynoesis_resumen_semanal`,
`bynoesis_aviso_fiscal` y `bynoesis_aviso_cobros`. Es decir: el parte de la mañana, el
cierre del día, el resumen semanal, el aviso fiscal trimestral y la propuesta de
cobro. Justo la parte que el founder llama «el punto más diferencial».

**No se ha arreglado por decisión de alcance**: repartir el texto en huecos cambia
la redacción de lo que él recibe cada mañana, y esa redacción es producto, no
implementación. Lo que sí está hecho es dejarlo listo para decidir:
[`whatsapp_templates.py`](../src/noesis/whatsapp_templates.py) ya contiene los
cuerpos redactados, aprobables y con el mismo contenido de hoy repartido en
valores de una línea.

Para verlo:

```bash
python -m noesis.whatsapp_templates
```

Imprime lo que hay que pegar en WhatsApp Manager y, al final, las cinco plantillas
cuyo envío todavía no encaja. El día que se ajuste `scheduler.py`, esa lista queda
vacía sola.

Las cuatro plantillas que van **al cliente** —cobro, factura lista, seguimiento de
presupuesto y recordatorio de cita— ya mandan valores sueltos y encajan con su
cuerpo. Esas se pueden crear en Meta hoy mismo.

## 2. Lo que estaba bien y sigue igual

- **Firma.** `X-Hub-Signature-256` con HMAC SHA-256 comparado en tiempo constante,
  y sin secreto solo pasa fuera de producción. El tope `MAX_JSON_BYTES` se aplica
  **antes** de parsear el JSON.
- **Idempotencia.** Cada mensaje y cada estado se reclaman en `webhook_events`
  antes de actuar y solo se cierran cuando todos sus efectos han terminado. Un
  reintento de Meta no duplica un gasto ni una factura. Detalle fino y correcto:
  un callback de estado que se adelante al commit del envío **no se consume**, así
  que vuelve a entregarse en lugar de perderse.
- **Descarga de medios.** Solo URLs `https` de `facebook.com`, `fbsbx.com` y
  `fbcdn.net`, sin credenciales en la URL, y un manejador de redirecciones propio
  que corta cualquier salto fuera de esos dominios: el bearer no se filtra por un
  redirect. El tamaño se acota leyendo `limit + 1`.
- **Cola de salida.** Se persiste antes de enviar, se reclama con `BEGIN IMMEDIATE`
  y `SKIP LOCKED` en PostgreSQL, reintenta con espera creciente y respeta la clave
  de idempotencia por negocio. Los estados no retroceden aunque Meta los entregue
  desordenados, y una cuenta en modo consulta cancela el envío en vez de mandarlo.
- **Ventana de 24 horas.** El texto libre solo se usa respondiendo a un entrante;
  todo lo que Bynoesis inicia va por plantilla. Se cumple por diseño.

## 3. Lo que se ha arreglado en esta revisión

- **Los valores de plantilla se sanean al encolar.** `whatsapp.template_param`
  aplana saltos de línea, tabuladores y espacios repetidos, y corta a 1024
  caracteres. Un cliente llamado «Obras\ny Reformas» ya no tumba el mensaje entero.
- **Un rechazo de Meta deja de reintentarse seis veces.** Un 4xx que no sea 408 ni
  429 —plantilla inexistente, destinatario inválido, huecos que no cuadran— lanza
  `MetaRejected` y cancela el envío al instante con el motivo guardado. Antes se
  pasaba una hora reintentando lo mismo antes de darse por vencido, retrasando la
  noticia de que algo estaba mal configurado.
- **`send_payment_reminder` retirado.** Mandaba 3 valores a la plantilla de cobro,
  que espera 5. No lo llamaba nadie, pero era una trampa esperando al primero que
  lo usara. Queda `queue_payment_reminder`, con los cinco correctos.
- **Los cuerpos de las plantillas existen.** Antes los nombres vivían en
  `config.py` y los textos no vivían en ningún sitio: no se podía dar de alta una
  plantilla en Meta sin inventarse el texto. Ahora están en
  `whatsapp_templates.py`, junto a su categoría, su destinatario y qué va en cada
  hueco.

## 4. Lo que queda por comprobar con el número real

- **Cuánto tarda el webhook en contestar.** El POST responde cuando ha terminado
  todo: descarga del medio, OCR, extracción con IA y respuesta. Una foto de ticket
  puede pasarse del tiempo que Meta espera; si Meta corta y reintenta, el segundo
  intento choca con el evento en curso y devuelve 503 en bucle. Hay que medirlo con
  el número real y, si se pasa, contestar 200 al instante y procesar aparte.
- **La versión de la Graph API.** `META_GRAPH_VERSION` fija `v23.0`. Las versiones
  de Meta caducan a los dos años; conviene confirmar la vigente al encender la
  cuenta y anotar su caducidad.
- **El coste por mensaje.** El cálculo de margen de
  [[Unit-economics-y-cerebro-interno]] usa el modelo antiguo de Meta, el de
  «conversación iniciada por la empresa» de 24 horas. Meta pasó a cobrar por
  mensaje de plantilla, con la categoría *utility* gratis dentro de una ventana de
  atención abierta. Hay que rehacer ese cálculo antes de fijar precios sobre el
  número de avisos: puede salir más barato de lo previsto, pero no se debe vender
  con un número que ya no existe.
- **Las credenciales.** `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`,
  `WHATSAPP_VERIFY_TOKEN` y `WHATSAPP_APP_SECRET` siguen vacíos:
  `is_configured()` es falso y no sale ni un mensaje. El readiness ya lo marca.

## 5. Orden sugerido para encender Meta

1. Verificar la empresa y dar de alta el número (número de prueba primero).
2. Crear en WhatsApp Manager las **cuatro plantillas al cliente**, copiando el
   cuerpo de `python -m noesis.whatsapp_templates`. Son las que ya encajan.
3. Decidir la redacción de los **cinco avisos al titular**, ajustar `scheduler.py`
   para que mande los valores por separado y crear esas plantillas.
4. Rellenar las credenciales y suscribir el webhook al campo `messages`.
5. Recorrer la prueba de aceptación de [[Conectar-APIs]] sección 4, midiendo de
   paso cuánto tarda el webhook con una foto real.
