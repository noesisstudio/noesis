# RGPD: estado real y plan de cierre

> **Aviso.** No es asesoramiento jurídico. Es una auditoría interna del código y de
> los textos publicados, hecha para que la revisión profesional que ya está pendiente
> en [[Tareas-vivas]] cueste menos y encuentre menos. Revisión: **3 de septiembre de
> 2026**.
>
> **Complementa la parte 5 de [`Ruta-legal.pdf`](Ruta-legal.pdf), no la sustituye.**
> Aquel documento fija las obligaciones y las rutas; este recorre el código y los
> textos publicados buscando dónde no se cumplen. Coinciden en dos hallazgos —la
> página `/cumplimiento` y el registro del art. 30— y se señala cuando así es.
>
> Contexto de por qué esto bloquea el primer cobro: [[Constitucion-y-primer-euro]],
> bloque C.

> **Estado del candidato posterior a la auditoría:** ya se han corregido el iframe
> de Cal.com, su excepción CSP, la afirmación de sistema homologado, la identificación
> condicional de proveedores, el valor S3 estadounidense por defecto y el callejón sin
> salida de la baja. El esquema 55 añade seguimiento sin borrado automático. También
> existen borradores de ROPA, matriz de proveedores, derechos y brechas. Las secciones
> de hallazgos se conservan como evidencia histórica; los pendientes vivos son la
> revisión profesional, DPA/regiones, tabla de conservación, purga y pruebas externas.

Noesis tiene dos sombreros a la vez y esa es la raíz de todo lo demás:

- **Responsable** de los datos de la cuenta del autónomo: su email, su NIF, su
  actividad, lo que escribe al asistente.
- **Encargado** de los datos que ese autónomo mete sobre *sus* clientes: nombres,
  teléfonos, direcciones, importes, fotos de documentos.

Lo segundo es lo que te expone. Si Noesis pierde datos, quien tiene que dar la cara
ante la Agencia es el fontanero, y luego se vuelve contra ti. Por eso el RGPD no es
una página en el pie de la web: es la condición para poder cobrar.

---

## 1. Lo que ya está bien y no necesita abogado

Esto está por encima de la media del sector. Conviene saberlo para no pagar por
rehacerlo, y para usarlo como argumento comercial ante gestorías.

| Pieza | Dónde está | Por qué cuenta |
|---|---|---|
| **Reparto de roles explicado y coherente** | `privacidad.html`, `encargado-tratamiento.html`, `cumplimiento.html` | Los tres textos dicen lo mismo: el cliente es responsable, Noesis encargado |
| **Evidencia de consentimiento** | `account.py`, evento `legal_accepted` | Guarda versión del documento, qué documentos, IP, método de alta y fecha. Es exactamente lo que exige el art. 7.1 para *acreditar* el consentimiento |
| **Minimización por defecto** | `db.py`, `ai_external` nace `disabled` | La IA externa está apagada por negocio hasta que el cliente la enciende. Esto es privacidad desde el diseño y por defecto (art. 25) de verdad, no en un párrafo |
| **Portabilidad (art. 20)** | `/api/{id}/export` y `/api/{id}/clients/{id}/export` | Volcado completo en JSON, de la cuenta entera y de un cliente concreto |
| **Supresión (art. 17)** | `delete_client_cascade`, `delete_business_cascade` | Borrado en cascada con verificación de contraseña y confirmación escrita, y borrado físico de los archivos después del commit |
| **Analítica sin dato personal** | Recuento propio: página, día y procedencia | Sin IP, sin identificador, sin terceros. Por eso no hay banner, y es defendible |
| **Aislamiento** | `business_id` en toda lectura/escritura; documentos con nombre uuid en carpeta por negocio | Es la medida del art. 32 que de verdad importa aquí |
| **Consentimiento de contacto en WhatsApp** | `set_whatsapp_contact_consent` con `opted_out` / `blocked` | El opt-out existe y es un estado, no una nota |
| **Cabeceras y ausencia de terceros** | CSP restrictiva, `Cache-Control: no-store` en rutas privadas, sin CDNs | Nada del panel se filtra a un tercero por accidente |

---

## 2. Los seis agujeros que bloquean el primer cliente de pago

Ordenados por gravedad. Los tres primeros son afirmaciones publicadas que hoy **no
son ciertas**, y eso es peor que una carencia: es una carencia declarada al revés.

### A1 · La lista de subencargados está incompleta, y por tanto es falsa

`encargado-tratamiento.html` y `privacidad.html` publican una tabla con Railway,
Anthropic, el proveedor de IA compatible, Meta y el proveedor de correo. **Faltan, y
tratan datos personales:**

- **Stripe** — nombre, dirección, NIF e importes de cada cliente de pago. Es un
  encargado de manual y no aparece en ningún sitio.
- **Google** — si se activa el acceso con Google, trata el email de tus usuarios.
- **Cal.com** — ver A2.
- **El almacenamiento de objetos (S3)** usado para las copias de seguridad.
- **Groq** — hallazgo de [`Ruta-legal.pdf`](Ruta-legal.pdf), no mío:
  `adapters/transcription.py` envía audio a `api.groq.com`, en Estados Unidos, y basta
  con configurar `GROQ_API_KEY` para estar mandando las notas de voz de los clientes
  de tus clientes a un subencargado no declarado. Es el más grave de la lista, porque
  incumple tu propio contrato en el momento en que alguien activa la variable.

Hay además un defecto de plantilla: el proveedor de correo **solo se pinta si
`NOESIS_SMTP_PROVIDER_NAME` está configurado**. Si la variable falta, la tabla no
muestra ese proveedor, pero los correos se siguen enviando. La lista mentiría por
omisión sin que nadie lo note.

**Arreglo:** completar la tabla y llevar las variables de proveedor a la comprobación
de `readiness.py`, junto a la identidad legal, de modo que la lista no pueda quedar
incompleta en producción.

### A2 · El iframe de Cal.com contradice la política de cookies

`site_contacto.html` incrusta `https://cal.com/bynoesis/sesion-de-estrategia` en un
iframe. Eso envía la IP del visitante a un tercero y permite que ese tercero escriba
en su navegador, **antes de cualquier consentimiento**.

Mientras tanto, `cookies.html` afirma literalmente que no hay seguimiento de
terceros, que *no intervienen empresas ajenas* y que por eso no hace falta banner. Y
`privacidad.html` no menciona Cal.com en ninguna parte.

No es un resto muerto que la CSP bloquee: `server.py` abre `frame-src` a
`cal.com` y `app.cal.com` **solo en `/contacto`, deliberadamente**, con un comentario
que reconoce que es «el único contenido externo que se incrusta». El código sabe que
incrusta un tercero; la página de cookies dice que no.

**Arreglo recomendado: quitar el iframe y, con él, la excepción de la CSP.** Justo
debajo ya hay enlaces a `cal.com/bynoesis`. Es un cambio de cinco minutos que elimina
un subencargado, una transferencia internacional y un banner de consentimiento
entero. La alternativa —carga bajo clic más banner— cuesta bastante más y no mejora
nada.

### A3 · `/cumplimiento` publica una afirmación que no es cierta

La página dice: *«Noesis se integra con un sistema homologado cuando lo conectas.
Hasta entonces, los documentos que genera Noesis son de apoyo a la gestión.»*

No existe tal integración. [[Decisiones]] y [[Fiscalidad]] son claras: Veri\*Factu es
**desarrollo propio**, con el registro construido y la remisión a la AEAT construida
pero **no validada externamente**.

Publicar que te apoyas en un sistema homologado de un tercero es una afirmación
engañosa sobre cumplimiento, en la página que precisamente se titula «Usar Noesis en
regla». Hay que reescribirla según el camino (a) o (b) del bloque D de
[[Constitucion-y-primer-euro]], y esa decisión sigue abierta.

### A4 · El derecho de supresión es todo o nada, y hoy no tiene salida

`delete_business_cascade` levanta `ValueError` si la cuenta tiene facturas emitidas o
registros de jornada, y la pantalla devuelve `error=conservacion_fiscal` con el
mensaje *«Solicita una baja con conservación fiscal»*.

**Ese procedimiento no existe.** No hay flujo, ni dirección, ni plazo. El cliente que
ejerce su derecho se encuentra un error y ahí se acaba.

El art. 17.3.b sí permite conservar lo que obliga la ley —y las facturas y el
registro de jornada lo son—, pero obliga a **borrar todo lo demás** y a informar de
qué se conserva, por qué y hasta cuándo.

**Arreglo mínimo antes de cobrar:** un procedimiento escrito (escribir a la dirección
de contacto, plazo de respuesta de un mes, y una tabla de qué se conserva y cuánto).
**Arreglo bueno, después:** baja parcial que borre agenda, documentos, conversaciones
y memorias del asistente, y deje solo el bloque fiscal congelado.

### A5 · Nada borra una cuenta cancelada

`privacidad.html` dice: *«Conservamos los datos mientras tu cuenta esté activa.»*
Pero el borrado solo ocurre si el titular pulsa el botón. Una cuenta que deja de
pagar y se abandona conserva los datos de sus clientes **para siempre**.

Eso incumple la limitación del plazo de conservación (art. 5.1.e), y es justo lo que
un despacho pregunta.

**Arreglo:** fijar un plazo —por ejemplo, 30 días de gracia tras la cancelación y
purga de todo lo no sujeto a obligación legal—, escribirlo en la política y
ejecutarlo con la infraestructura de tareas programadas que ya existe
(`scheduled_job_runs`).

### A6 · Falta el registro de actividades del tratamiento (art. 30)

No existe en el repositorio. Es obligatorio: la excepción para menos de 250
trabajadores **no aplica**, porque el tratamiento no es ocasional y es la actividad
principal.

Son dos tablas, no un proyecto: una como responsable (datos de las cuentas) y otra
como encargado (datos de los clientes de los clientes). Es lo primero que pide la
Agencia si algún día llama, y lo primero que pide una gestoría antes de firmar.

---

## 3. Lo que hay que cerrar antes de escalar, no antes de cobrar

**B1 · Evaluación de impacto (art. 35).** Datos económicos y fiscales de terceros, a
escala, con tratamiento por IA. Es muy probable que sea exigible. Hacerla ahora, con
tres clientes, es un documento. Hacerla con doscientos es una auditoría.

**B2 · Cifrado en reposo.** Los documentos se guardan en claro, con nombre uuid en
una carpeta por negocio. La política de privacidad **no lo promete**, así que no
miente —bien—, pero cualquier gestoría lo va a preguntar.
[[Seguridad-operativa]] ya lo tiene decidido con criterio: KMS y cifrado selectivo se
deciden con evidencia del piloto. Mantén esa decisión, pero ten la respuesta escrita.

**B3 · Transferencias internacionales, una por una.** La política dice «cláusulas
contractuales tipo» de forma genérica. Eso no basta: hay que verificar proveedor por
proveedor —Railway, Anthropic, el proveedor OpenAI-compatible, Meta, Stripe, Google—
que existe DPA firmado y cuál es la base concreta: decisión de adecuación si está
certificado en el marco UE-EE. UU., o cláusulas tipo más su evaluación. Es papeleo, y
es exactamente lo que se audita.

**B4 · La gestoría no está en el reparto de roles.** El producto tiene cartera
multiempresa, permisos explícitos y MFA, pero ni el contrato de encargado ni la
privacidad dicen **qué es** una gestoría: ¿subencargada de Noesis, o responsable
independiente a la que el cliente concede acceso? Mi criterio es lo segundo —el
acceso lo concede el cliente, no Noesis—, pero hay que escribirlo, porque decide
quién responde si un despacho filtra un expediente.

**B5 · Notificación de brecha: como encargado no evalúas, avisas.**
[[Seguridad-operativa]] dice «evaluar con asesoría jurídica/DPO la notificación
RGPD». Eso vale para los datos propios. Para los datos de los clientes de tus
clientes, el art. 33.2 es distinto: **notificas al cliente sin dilación indebida** y
es él quien decide si va a la Agencia. Añade esa frase y un plazo interno propio
—24 horas— al procedimiento.

**B6 · No hay mecanismo de aviso de cambios.** `LEGAL_DOCUMENT_VERSION` está fija en
el código (`2026-08-08`) y el contrato promete avisar de los cambios de subencargado
«con antelación razonable». No existe nada que envíe ese aviso. Mínimo: al cambiar la
versión, un evento y un correo a las cuentas activas.

**B7 · Delegado de protección de datos.** Probablemente no obligatorio, pero la
decisión hay que **razonarla por escrito** dentro del registro de actividades. Si el
canal de gestorías funciona, designar un contacto de privacidad ayuda a vender.

**B8 · Reglamento de IA (fuera del RGPD, misma revisión).** Desde el 2 de agosto de
2026 aplican las obligaciones de transparencia del art. 50: dejar claro que se
interactúa con un sistema de IA. Noesis lo cumple de hecho, pero conviene una línea
explícita en los términos. Confírmalo en la misma consulta.

---

## 4. Qué pedirle exactamente al abogado

Para que los 300-800 € rindan, entra con la lista hecha. Siete encargos concretos:

1. Revisar los cuatro textos publicados **y su coherencia entre sí**, con los
   hallazgos A1, A2 y A3 encima de la mesa.
2. Redactar el **registro de actividades** (art. 30), como responsable y como
   encargado.
3. Dictaminar si procede **EIPD** y, si procede, el guion.
4. Fijar la **tabla de plazos de conservación** por tipo de dato: fiscal, mercantil,
   registro de jornada, documentos, conversaciones del asistente y logs. Es la que
   alimenta A4 y A5, así que sin ella no se puede programar la purga.
5. Definir el **rol de la gestoría** en el reparto de responsabilidades.
6. Revisar la **limitación de responsabilidad** de los términos frente a un error de
   cálculo fiscal. Es el riesgo real del producto.
7. Confirmar la **base de cada transferencia internacional**, proveedor por proveedor.

---

## 5. Orden de trabajo

**Founder** — encargar la revisión el día que haya NIF, con los siete encargos de
arriba; decidir el camino (a)/(b) de Veri\*Factu, porque A3 no se puede reescribir
sin esa decisión.

**Producto, sin esperar al abogado** — son cambios de texto y de configuración, no de
arquitectura:

- Quitar el iframe de Cal.com y dejar los enlaces (A2).
- Completar la tabla de subencargados y llevar las variables de proveedor a
  `readiness.py` (A1).
- Escribir el procedimiento de baja con conservación legal y enlazarlo desde el
  mensaje de error que hoy no lleva a ninguna parte (A4).

**Producto, después de que el abogado fije los plazos** — purga automática de cuentas
canceladas sobre `scheduled_job_runs` (A5) y baja parcial con anonimización (A4, la
versión buena).

**Ninguno de estos cambios toca el esquema ni el aislamiento.** Son texto,
configuración y una tarea programada.
