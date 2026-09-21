# Por qué tus correos caen en spam (y qué arreglar de verdad)

*21 de septiembre de 2026. Diagnóstico hecho contra el DNS real de `bynoesis.com`,
no contra una guía genérica. Se vuelve a comprobar con
`python scripts/check_email_dns.py`.*

---

## 1. Lo primero: tu autenticación no está rota

Es lo contrario de lo que uno espera, así que conviene decirlo antes de nada. Los
correos que escribes desde el webmail de Hostinger salen **correctamente
autenticados**:

| | Estado | Qué significa |
|---|---|---|
| **SPF** | Correcto | `v=spf1 include:_spf.mail.hostinger.com ~all`. Un solo registro, que es lo que hay que mirar: con dos, el resultado sería error y fallaría igual que sin ninguno. |
| **DKIM** | Correcto | `hostingermail-a._domainkey` publica una clave RSA de 2048 bits. Hostinger firma tus mensajes. |
| **DMARC** | Existe | `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com`. |
| **Listas negras** | Limpio | El dominio no está en Spamhaus DBL ni en SURBL. |

**Conclusión: tocar el DNS no va a arreglar esto.** Si fuera un problema de
autenticación, tus correos también caerían en spam escribiendo a tu asesoría o a
tu abogado, y no es lo que pasa.

---

## 1 bis. El plan, en siete pasos

Si lo que quieres es que **los correos a gestorías lleguen a bandeja de entrada**,
esto es lo que hay que hacer, en este orden. Los cinco primeros son gratis y de hoy.

1. **Crea `xavier@bynoesis.com`** en Hostinger y escribe desde ahí. `info@` es una
   dirección de rol y arrastra un castigo del que no te libra ningún DNS.
2. **Pon el webmail en texto plano.** En el webmail de Hostinger (Roundcube):
   *Configuración → Redactar mensajes → Redactar mensajes HTML: **nunca***. Un
   correo de una persona a otra persona no lleva HTML, y el HTML con una sola
   imagen o una firma de colores es una señal clásica.
3. **Calienta el buzón una semana antes de escribir a nadie.** Mándate correos a
   cuentas tuyas de Gmail, Outlook y Yahoo; si caen en spam, **márcalos «no es
   spam», muévelos a recibidos y respóndelos desde allí**. Luego diez o quince
   correos reales a gente que te va a contestar (asesoría, conocidos, proveedores).
   Cada respuesta es una señal positiva sobre tu dominio.
4. **Cinco al día como máximo**, uno a uno, cada uno escrito para ese despacho.
   Nunca en copia oculta, nunca el mismo cuerpo copiado y pegado.
5. **Cero enlaces, cero adjuntos, asunto en minúsculas y una pregunta al final.**
   Los guiones del CRM ya salen así, y hay una prueba que impide que alguien les
   meta un enlace.
6. **Mide antes de lanzarte.** Manda uno a
   [mail-tester.com](https://www.mail-tester.com): por debajo de 8/10 hay algo del
   mensaje que arreglar. Y manda otro a un Gmail tuyo y mira «Mostrar original»:
   tiene que poner `dkim=pass header.d=bynoesis.com`.
7. **Responde siempre a quien te responde**, el mismo día. Es lo que más deprisa
   construye reputación, más que cualquier registro DNS.

Si después de las cuatro semanas de calentamiento siguen cayendo, el problema ya no
es tuyo: es de por dónde sales. Eso es el apartado 3 bis.

## 2. Por qué caen entonces: tres causas, por peso

### 2.1 El dominio tiene tres meses y medio

`bynoesis.com` se registró el **4 de junio de 2026**. Para un filtro de correo, un
dominio recién registrado que de repente empieza a escribir a gente que no lo
conoce es **el patrón exacto del spam**, porque es literalmente lo que hace el
spam. No hay nada que te dé el beneficio de la duda todavía: ni historial de
entregas, ni respuestas, ni nadie que te haya marcado como «no es spam».

Esto no se arregla con un registro DNS. Se arregla con tiempo y con volumen bajo y
constante. Es lo que se llama **calentar el dominio**.

### 2.2 Escribes a gente que nunca te ha escrito

Es la señal que más pesa en Gmail, por encima de SPF y DKIM juntos. Un correo a
alguien con quien nunca has intercambiado nada compite en desventaja desde el
primer byte. Y si dos o tres de esos destinatarios pulsan «marcar como spam» —o
simplemente lo borran sin abrirlo—, el filtro aprende sobre **tu dominio entero**,
no sobre ese correo.

### 2.3 `info@` es una dirección de rol

Las direcciones de rol (`info@`, `contacto@`, `no-reply@`) reciben peor trato que
una dirección con nombre y apellido, porque casi todo el correo comercial masivo
sale de una de ellas. Para escribir a una persona, escribe desde una persona.

### 2.4 Y además estás ciego

Tus informes DMARC van a `rua@dmarc.brevo.com`. Los recibe Brevo, **no tú**. Ahora
mismo no tienes forma de saber cuántos correos tuyos se autentican bien ni quién
más está enviando en tu nombre.

---

## 3. Lo que sí hay que arreglar en el DNS

No es la causa de tu problema de hoy, pero **reventará el día que la aplicación
empiece a mandar correos** (recuperar contraseña, facturas a los clientes de tus
autónomos, avisos a la gestoría), y ese día el fallo será mucho más caro.

**El dominio está verificado en Brevo pero sin firmar por Brevo.** En el DNS está
el TXT `brevo-code:aac20b53…`, que solo demuestra que el dominio es tuyo. No hay
ninguna clave DKIM de Brevo, y Brevo tampoco está en el SPF. Es una configuración
empezada y abandonada a la mitad: todo lo que salga por ahí irá sin autenticar.

### Qué cambiar, exactamente

**1. Añadir la firma de Brevo.** En Brevo → *Senders, Domains & Dedicated IPs* →
*Domains* → `bynoesis.com` → *Authenticate this domain*. Te dará un registro DKIM
propio (normalmente `mail._domainkey` o `brevo._domainkey`). Publícalo tal cual en
el DNS de Hostinger.

**2. Meter a Brevo en el SPF que ya existe.** En el mismo registro, nunca en uno
nuevo —dos registros SPF fallan los dos—:

```
v=spf1 include:_spf.mail.hostinger.com include:spf.brevo.com ~all
```

**3. Recuperar tus propios informes DMARC.** Crea el buzón `dmarc@bynoesis.com` y
cambia el registro `_dmarc.bynoesis.com` a:

```
v=DMARC1; p=none; rua=mailto:dmarc@bynoesis.com,mailto:rua@dmarc.brevo.com; fo=1
```

**4. Dentro de dos o tres semanas**, si los informes salen limpios, endurecer:

```
v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@bynoesis.com; fo=1
```

Pasar a `p=quarantine` **antes** de tener DKIM de Brevo bien puesto haría que tus
propios correos legítimos se fueran a spam. Ese es el orden y no otro.

### Cómo comprobar que ha quedado bien

```bash
python scripts/check_email_dns.py bynoesis.com
```

Dice qué hay publicado, qué falta y qué pegar. Comprueba **lo publicado**, no lo
que hace tu servidor al enviar; para eso está el apartado siguiente.

---

## 3 bis. Por dónde salen tus correos (y por qué no es tuyo del todo)

`python scripts/check_email_dns.py` sigue los `include` de tu SPF hasta las IP que
envían de verdad. En tu caso:

```
148.222.54.0/24 · 148.222.55.0/24 · 189.12.192.0/22   (relay de Hostinger)
23.83.208.0/20 · 35.85.190.185                        (MailChannels)
```

Ninguna aparece en Spamhaus, así que **no estás bloqueado**. Pero fíjate en la
segunda línea: el correo de Hostinger sale por **MailChannels, un relay
compartido** que usan miles de cuentas de hosting barato. Tu dominio está
impecable, pero **la reputación de esa IP no es tuya**: la compartes con todo el
que envíe desde ahí, incluido quien envíe basura.

Eso no se arregla con ningún registro DNS. Se arregla de una sola manera: **saliendo
por otro sitio**.

### El salto, si lo anterior no basta

Mover el buzón a **Google Workspace** (unos 7 €/mes) o Microsoft 365. Las IP de
salida de Google tienen de las mejores reputaciones que existen, y una parte de las
gestorías a las que escribes usa Gmail o Workspace, donde la entrega entre dominios
de Google es especialmente buena.

Qué hay que cambiar en el DNS —y `check_email_dns.py` lo valida después—:

```
MX:    1 smtp.google.com          (sustituye a mx1/mx2.hostinger.com)
SPF:   v=spf1 include:_spf.google.com include:spf.brevo.com ~all
DKIM:  el registro google._domainkey que te da la consola de Workspace
```

**Es una decisión de 7 €/mes, no técnica.** Si tu plan para llegar a las gestorías
depende del correo, es barato. Si vas a usar sobre todo el teléfono, no hace falta:
con los siete pasos del apartado 1 bis vas servido.

## 4. La prueba que de verdad vale

Manda un correo desde el webmail de Hostinger a una cuenta de Gmail tuya. En Gmail,
abre el mensaje → menú de tres puntos → **«Mostrar original»**. Arriba tiene que
poner:

```
SPF:   PASS   con la IP de Hostinger
DKIM:  PASS   con el dominio bynoesis.com
DMARC: PASS
```

**Si DKIM dice `bynoesis.com`, todo está bien y el problema es de reputación**, que
es lo que dice este documento. Si dijera `hostinger.com` o `gmail.com`, la firma no
estaría alineada con tu dominio y entonces sí habría que tocar el DNS.

Complementario: [mail-tester.com](https://www.mail-tester.com) da una nota sobre 10
y explica cada punto que resta. Por debajo de 8 hay algo del mensaje que arreglar.

---

## 5. Cómo escribir un primer contacto que llegue

El contenido decide tanto como el DNS cuando no hay historial.

**Hazlo así:**

- **Desde una dirección con tu nombre**, no desde `info@`. Crea
  `xavier@bynoesis.com` en Hostinger y escribe desde ahí.
- **Texto plano y corto.** Cinco o seis líneas. Sin plantilla HTML, sin cabecera
  con logo, sin colores.
- **Cero enlaces en el primer correo.** Un enlace a un dominio de tres meses es la
  señal que más penaliza. Si necesitas que vea algo, que te lo pida él al responder.
- **Sin adjuntos.** Un PDF en un primer correo a un desconocido es casi una
  garantía de spam.
- **Sin rastreadores de apertura.** Los píxeles de seguimiento de las herramientas
  de mailing se detectan y penalizan.
- **Asunto normal**, en minúsculas y sin signos: «una pregunta sobre presupuestos»,
  no «¡¡Revoluciona tu negocio YA!!».
- **Acaba con una pregunta.** Una respuesta, aunque sea «ahora no puedo», le dice a
  Gmail que eres una persona escribiendo a otra. **Las respuestas son la forma más
  rápida de construir reputación.**
- **Cinco al día como mucho**, repartidos. Nunca veinte de golpe ni copia oculta a
  una lista: un envío a muchos destinatarios a la vez se detecta y te marca.

**Y la parte incómoda:** para posibles clientes, el correo en frío **no es el
canal**. Ni funciona —esto es justo lo que estás comprobando— ni está permitido sin
consentimiento previo (art. 21 LSSI, ver [[Lista-de-captacion]]). El primer
contacto con un fontanero es **una llamada de teléfono a las 7:30**, y el correo
viene después, cuando ya te conoce.

Donde el correo sí es el canal correcto es en lo que no es publicidad:
**gestorías, gremios, abogado, proveedores, administraciones**. Eso es
correspondencia profesional normal y debería llegar sin problema. Si esos correos
también caen en spam, vuelve al apartado 4 y mira las cabeceras: sería otra cosa.

---

## 6. Calentar el dominio: cuatro semanas

| Semana | Cuántos correos al día | A quién |
|---|---|---|
| 1 | 3–5 | Gente que te conoce y **te va a contestar**: asesoría, abogado, conocidos. Pídeles que respondan y que, si les llegó a spam, lo marquen «no es spam». |
| 2 | 5–8 | Lo anterior más proveedores y gestorías con las que ya has hablado por teléfono. |
| 3 | 8–12 | Se pueden añadir primeros contactos **que ya te conocen de una llamada**. |
| 4 en adelante | 15–20 | Ritmo normal. |

Lo que más acelera esto no es el volumen: son las **respuestas**. Diez correos que
reciben respuesta valen más que cien que nadie contesta.

---

## 7. Lo que no hay que hacer

- **Comprar listas de correos.** Ni son legales para esto ni entregan.
- **Usar una herramienta de mailing masivo para escribir a personas.** Brevo,
  Mailchimp y similares sirven para boletines a gente que se ha suscrito. Un primer
  contacto sale de tu buzón, como una carta.
- **Insistir tres veces por correo.** Si dos no han contestado, no es el canal.
- **Poner `p=reject` en el DMARC «para que se tomen en serio».** Solo consigue que
  tus propios correos legítimos desaparezcan cuando algo no esté alineado.
- **Cambiar de dominio para escapar de la mala reputación.** El nuevo empieza otra
  vez a cero y con tres meses menos de historial.

---

## 8. Resumen en cinco líneas

1. Tu SPF, tu DKIM y tu DMARC están bien. **No toques el DNS por esto.**
2. Caen en spam porque el dominio tiene tres meses, escribes a desconocidos y sales
   por un relay compartido. Los siete pasos del apartado 1 bis arreglan lo primero
   y lo segundo; lo tercero, solo cambiar de proveedor de buzón.
3. Arregla Brevo igualmente: está a medias y romperá el correo de la aplicación.
4. Recupera tus informes DMARC, que ahora los recibe Brevo y no tú.
5. Para captar clientes, el canal es el teléfono. El correo viene después.
