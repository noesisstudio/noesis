# Constitución y primer euro

> **Aviso.** Esto no es asesoramiento jurídico ni fiscal. Es el mapa de decisiones y
> dependencias para que la conversación con una gestoría dure una hora y no tres.
> Cada importe, plazo y epígrafe debe confirmarse con un profesional antes de firmar.
> Fecha de redacción: **3 de septiembre de 2026**.

Tres preguntas, una respuesta encadenada: la forma jurídica la decide Meta antes que
Hacienda; lo legal se ordena por dependencias, no por importancia; y el primer euro
llega antes de lo que parece porque **WhatsApp no está en el camino crítico**.

---

## 1. SL o autónomo: la decide Meta, no el ahorro

**Recomendación: SL, constituida en septiembre, antes de pedir la verificación de
empresa en Meta.** No por prestigio ni por fiscalidad —a este volumen el autónomo
paga menos impuestos—, sino porque hay una puerta que solo se cruza bien una vez.

### Lo que Meta comprueba de verdad

La verificación de empresa no es un formulario: Meta contrasta lo que declaras
contra **registros públicos y bases de datos empresariales de terceros**. Una S.L.
española aparece en el Registro Mercantil y en el BORME, con nombre, NIF, domicilio
y fecha de inscripción. Un autónomo **no aparece en ningún registro que Meta pueda
consultar**: su expediente depende por completo de que un revisor acepte un
certificado de situación censal de la AEAT como prueba de existencia.

Esto no lo hace imposible, lo hace **frágil**. Y [`Meta-Verificacion.pdf`](Meta-Verificacion.pdf)
ya documenta el coste de la fragilidad: Meta no compromete plazo, los tres motivos
de rechazo más frecuentes son datos incompletos, documentos ilegibles y datos
legales que no coinciden, y **cada rechazo reinicia el reloj**.

### Por qué no vale «empiezo como autónomo y luego ya veré»

La entidad legal está pegada al Business Manager. Cambiar de titular después
significa rehacer la verificación desde cero con la nueva entidad, y mover o volver
a conceder los WABA de los clientes que ya estuvieran conectados. Es decir: el
camino «autónomo ahora, SL después» **paga la verificación de Meta dos veces** y
mete una migración de activos justo cuando ya hay clientes reales dentro.

### Las otras cuatro fuerzas, en orden de peso

| Fuerza | Siendo autónomo | Siendo SL |
|---|---|---|
| **Responsabilidad** | Respondes con tu patrimonio personal de un error fiscal en la factura de un tercero | La responsabilidad queda en la sociedad |
| **Canal de gestorías** | Un despacho firma un contrato de encargado del tratamiento con una persona física a regañadientes | Es el contrato que esperan |
| **Cobro y facturación** | Stripe y el IVA funcionan igual | Igual |
| **Futuro: socios, inversión, Embedded Signup** | Hay que constituir sí o sí antes | Ya está hecho |

La primera fila es la que cierra el debate. Noesis emite facturas con validez
fiscal, encadena huellas Veri\*Factu y guarda datos tributarios de terceros. Un
fallo en el cálculo de una retención no es un bug: es un problema con Hacienda de
otra persona. Asumir eso con responsabilidad personal ilimitada, con 4.000 € de
capital y sin seguro, es la decisión de riesgo peor pagada del proyecto.

### El coste real de la diferencia

Primer año, sin contar el capital social —que no es gasto: es tu dinero dentro de la
empresa y se usa para pagar los gastos.

| Concepto | Autónomo | SL |
|---|---|---|
| Alta / constitución | 0 € | 120-270 € por el PAE con estatutos tipo; 400-800 € con gestoría y estatutos propios |
| Denominación (RMC) | — | ~16 € |
| Gestoría mensual | 480-720 € | 720-1.440 € |
| RETA con tarifa plana, 12 meses | ~960 € | ~960 € como autónomo societario |
| **Total orientativo** | **1.400-1.700 €** | **1.800-2.700 €** |

**La diferencia real es de 400 a 1.000 € el primer año.** Es menos de lo que cuesta
una verificación de Meta rechazada dos veces, y muchísimo menos que un susto de
responsabilidad. Con 4.000 € de capital inicial entra sin ahogar el proyecto.

### Sobre el capital social: pon 3.000 €, no 1 €

Desde la Ley 18/2022 se puede constituir con 1 €, pero por debajo de 3.000 € la
sociedad arrastra dos reglas: hay que destinar al menos el **20 % del beneficio a
reserva legal** hasta alcanzar esa cifra, y en caso de liquidación con patrimonio
insuficiente **los socios responden de la diferencia hasta 3.000 €**. Además, una
S.L. de 1 € es exactamente la señal que no quieres dar a Meta, a Stripe y a una
gestoría que va a confiarte su cartera. Con 3.000 € de los 4.000 € disponibles el
dinero sigue siendo tuyo y sigue estando disponible para pagar gastos.

### La rama que no puedo resolver yo: tu empresa de eventos

Si esa empresa **ya es una S.L. tuya**, existe un atajo legítimo: ampliar el objeto
social, dar de alta el epígrafe informático y operar Noesis como marca comercial de
esa sociedad. Ahorra la constitución entera y la verificación de Meta se puede pedir
ya, con una entidad que lleva tiempo inscrita —lo cual, además, verifica mejor.

El precio del atajo: **las facturas a los clientes de Noesis saldrán con la razón
social de eventos**, los dos negocios comparten responsabilidad patrimonial, y
separarlos después obliga a una escisión o a una venta de rama de actividad. Mi
criterio: úsalo solo si el efectivo es el problema real; si no, sociedad limpia.

Si en eventos eres autónomo, hay una buena noticia colateral: **ya estás de alta en
RETA**, así que ser administrador de la nueva S.L. no te añade una segunda cuota.

---

## 2. Todo lo legal, ordenado por dependencias

Cinco bloques. El orden importa: cada uno desbloquea el siguiente, y el bloque C es
el que de verdad puede pararte antes del primer cliente de pago.

### Bloque A · Existir (días 1-20)

1. **Certificación negativa de denominación social** en el Registro Mercantil
   Central. Pide cinco nombres por orden de preferencia. Vale 3 meses. ~16 €.
2. **Cuenta bancaria a nombre de la sociedad en constitución** y desembolso del
   capital; el banco emite el certificado que va a la notaría.
3. **Escritura pública de constitución** ante notario, con estatutos y nombramiento
   de administrador. Por el PAE/CIRCE con estatutos tipo son 24-48 h y aranceles
   reducidos; con estatutos propios, más caro y más lento pero más flexible.
4. **Declaración de titularidad real** en la propia escritura y su constancia en el
   Registro Central de Titularidades Reales.
5. **NIF provisional** (modelo 036) inmediatamente después de la escritura. Es la
   pieza que desbloquea casi todo lo demás.
6. **Inscripción en el Registro Mercantil** y **NIF definitivo**. Anota los datos
   registrales: van literalmente en `NOESIS_LEGAL_REGISTRY`.
7. **Alta censal definitiva (036)**: epígrafe de IAE de servicios informáticos
   —confirma con la gestoría cuál corresponde exactamente a un SaaS—, alta en IVA,
   y **alta en el ROI/VIES** si vas a facturar a empresas de otros países de la UE.
   La exención de IAE cubre los dos primeros años y, después, mientras la cifra de
   negocio esté por debajo de 1 M€.
8. **Alta del administrador en RETA** como autónomo societario, con tarifa plana si
   cumples los requisitos. Salvo que ya estés de alta por la otra actividad.
9. **Libro registro de socios** y legalización de libros contables en el plazo legal
   tras el cierre del ejercicio; depósito de cuentas anuales al año siguiente.

### Bloque B · Poder cobrar

- **Cuenta Stripe a nombre de la sociedad**, con el NIF y el domicilio exactos.
  Verificación de identidad del titular real: de 1 a 3 días.
- **Catálogo real 29/49/99 € + IVA** con sus seis `price_id` mensuales y anuales, y
  `automatic_tax` activo. La tarea P0 correspondiente en [[Tareas-vivas]] avisa de un
  detalle que rompe cobros: **todos los precios deben tener un `tax_behavior`
  distinto de `unspecified`**.
- **Obligaciones periódicas**: modelo 303 trimestral y 390 anual de IVA; 202 de
  pagos fraccionados y 200 del Impuesto sobre Sociedades; 111 si pagas a
  profesionales con retención; 115 si alquilas local; 349 si hay operaciones
  intracomunitarias; 347 si superas el umbral con algún tercero.
- **Facturación propia**: numeración correlativa, datos completos y conservación
  durante cuatro años. Noesis va a facturarse a sí mismo con las mismas reglas que
  exige a sus clientes.

### Bloque C · Poder tratar datos de terceros — *aquí está el bloqueo real*

Noesis es **encargado del tratamiento** de los datos que el autónomo mete sobre sus
clientes, y **responsable** de los datos del propio autónomo. Eso implica, y no es
opcional:

- **Contrato de encargado del tratamiento (art. 28 RGPD)** aceptado por cada cliente.
  La plantilla ya existe (`encargado-tratamiento.html`) y está **pendiente de
  revisión profesional**, según [[Tareas-vivas]].
- **Registro de actividades de tratamiento** (art. 30), como responsable y como
  encargado.
- **Lista de subencargados** publicada y con derecho de objeción: Railway, Stripe,
  Brevo, Google, Meta y el proveedor de IA que se elija.
- **Transferencias internacionales**: cualquier proveedor fuera del EEE necesita base
  legal —decisión de adecuación o cláusulas contractuales tipo— y constar en la
  lista. Esto afecta directamente a la decisión pendiente de proveedor de IA en
  [[Preguntas-abiertas]]: **la elección tiene consecuencia legal, no solo de coste**.
- **Evaluación de impacto (art. 35)**: con datos fiscales y financieros de terceros a
  escala, es muy probable que sea exigible. Pregúntalo explícitamente.
- **Procedimiento de brecha de seguridad**: notificación en 72 h. Debe estar escrito
  antes, no después.
- **Aviso legal (LSSI)**, política de privacidad, términos y política de cookies con
  la identidad legal real. El producto **ya falla cerrado** si faltan
  `NOESIS_LEGAL_NAME`, `NOESIS_LEGAL_NIF`, `NOESIS_LEGAL_ADDRESS` y
  `NOESIS_LEGAL_EMAIL`: la comprobación está en `readiness.py`.

**Esta es la única partida legal en la que no recomiendo ahorrar.** Presupuesta
300-800 € de revisión por un abogado de protección de datos antes del primer cliente
de pago. Casi todo lo demás se puede hacer barato; esto no.

La auditoría detallada de qué cumple ya el código, qué está publicado y no es cierto,
y qué encargarle exactamente al abogado está en [[RGPD-estado-y-plan]].

### Bloque D · Poder vender un programa de facturación

Aquí hay una obligación que no aparece en ninguna guía de «cómo montar una empresa»
y que te afecta a ti más que a tus clientes.

[[Fiscalidad]] recoge bien los plazos de **los obligados tributarios**: 1 de enero de
2027 para contribuyentes del Impuesto sobre Sociedades y 1 de julio de 2027 para el
resto. Pero Noesis no es solo usuario: es **productor de un sistema informático de
facturación**, y el productor tiene obligaciones propias y anteriores, entre ellas
emitir una **declaración responsable** de que el sistema cumple el Real Decreto
1007/2023.

Consecuencia práctica, y es una decisión tuya: el registro Veri\*Factu está
construido, pero la **remisión a la AEAT está construida y no validada externamente**
—así consta en [[Fiscalidad]]—. Antes de cobrar al primer cliente hay que elegir una
de dos:

- **(a)** completar la validación técnica y publicar la declaración responsable; o
- **(b)** declarar explícitamente, en los términos y dentro del producto, que durante
  el piloto **el módulo de facturación no se ofrece como sistema Veri\*Factu**.

Vender un programa de facturación sin resolver esto es el riesgo legal más específico
y menos visible del proyecto. Llévalo a la gestoría con el número del Real Decreto en
la mano.

### Bloque E · Proteger (puede esperar al primer cliente, no más)

- **Seguro de responsabilidad civil profesional y ciberriesgo**. 300-600 €/año. Antes
  del primer cliente de pago; además, es de lo primero que pregunta una gestoría
  antes de meterte su cartera.
- **Marca «Noesis» en la OEPM**, clase 42 y probablemente 35. ~150 €/clase. Puede
  esperar a tener diez clientes, pero comprueba **hoy** que el nombre está libre:
  descubrirlo tarde es carísimo.
- **Cesión de propiedad intelectual del código a la sociedad**. Si has desarrollado a
  título personal, el activo está fuera de la empresa. Se arregla con una aportación
  o una cesión en la constitución; después es más incómodo.

---

## 3. El plan del primer euro

### El hallazgo que acorta seis semanas

**WhatsApp no está en el camino crítico, y la verificación de Meta tampoco.** Sin
verificar tienes 250 conversaciones cada 24 h y dos números: sobra para tres a cinco
autónomos. La verificación limita *cuándo puedes crecer*, no *cuándo puedes cobrar*.

El propio producto lo refuerza: el alta comercial es recuperable y **permite posponer
WhatsApp voluntariamente** y seguir hasta el cobro. Así que Meta corre en paralelo, no
por delante.

Lo que sí está en el camino crítico es una cadena corta y dura:

> **NIF → identidad legal publicada → Stripe live → alta manual de un cliente → cobro**

Sin NIF no hay Stripe. Sin identidad legal el servidor falla cerrado. Sin cobro no hay
euro. Todo lo demás es paralelo.

### Semana 1 (3-10 sep) · Existir

- Decidir forma jurídica y resolver la rama de la empresa de eventos.
- Contratar gestoría: pide precio cerrado de constitución **y** cuota mensual.
- Pedir la denominación en el RMC. Cinco nombres.
- Comprobar la marca «Noesis» en la OEPM. Diez minutos, hoy.
- **En paralelo, producto:** empezar por la P0 que no depende de nadie: **rotar
  `NOESIS_SECRET`, SMTP y toda credencial que haya aparecido en una captura, un PDF o
  una conversación**. Esto no espera a la notaría.

### Semana 2 (11-17 sep) · Firmar y desbloquear

- Certificado bancario, escritura, titularidad real.
- **Modelo 036 y NIF provisional.** Este es el hito que abre todo lo demás.
- Encargar la revisión legal del bloque C. Es lo que más tarda por depender de otro:
  lánzalo el día que tengas NIF, no cuando esté todo lo demás listo.
- **En paralelo, producto:** completar el recorrido del alta recuperable en escritorio
  y móvil, y la validación visual de `/acceso`. Ambas son P0 sin dependencia externa.

### Semana 3 (18-24 sep) · Cobrar se vuelve posible

- Inscripción en el Registro Mercantil, NIF definitivo, alta censal completa, RETA.
- Publicar en Railway `NOESIS_LEGAL_NAME`, `NOESIS_LEGAL_NIF`, `NOESIS_LEGAL_ADDRESS`,
  `NOESIS_LEGAL_EMAIL` y `NOESIS_LEGAL_REGISTRY`. Verificar que `/ready` deja de
  señalar la identidad legal como pendiente.
- Abrir la cuenta Stripe de la sociedad y superar la verificación de identidad.
- **Arrancar la verificación de empresa en Meta**, con el nombre y el NIF copiados
  **literalmente** de la escritura, carácter a carácter. En paralelo, enviar a aprobar
  las nueve plantillas: no dependen de nada.

### Semana 4 (25 sep - 1 oct) · La cadena del dinero

- Crear en Stripe live los tres productos con sus seis precios, `automatic_tax` y un
  `tax_behavior` válido en los seis.
- Recorrer el Customer Portal autenticado de verdad: alta, cambio de tarjeta, cambio
  de plan, anualidad, cancelación e impago. Está pendiente en [[Tareas-vivas]], y
  siete contratos locales verdes **no** lo sustituyen.
- **Compra real con tu propia tarjeta y reembolso.** Es el ensayo general: si el IVA,
  la factura y el webhook no salen bien contigo, no van a salir bien con un cliente.
- Cerrar la lista de tres a cinco autónomos de tu entorno. Nombres y teléfonos, no
  perfiles.

### Semanas 5-6 (2-15 oct) · El euro

- Dar de alta a los tres primeros **manualmente desde Administración**, con
  `NOESIS_PUBLIC_SIGNUP_ENABLED=false`. Cobrar no exige abrir el registro público:
  exige poder facturar. Mantener el alta cerrada mientras dure la lista P0 es
  exactamente lo que ya decidiste.
- Demo de diez minutos, alta acompañada y **cobro el mismo día**.
- **Primer euro cobrado.**

### El precio del primer cliente: descuento, nunca gratis

[[Estrategia-Marketing]] plantea «gratis o precio fundador». Elige precio fundador, y
por una razón que no es el dinero: **gratis destruye la única señal que necesitas del
piloto**. Un cliente que no paga no te dice si el producto vale; te dice que no le
molesta tenerlo.

Cómo hacerlo sin ensuciar el catálogo: **no crees precios nuevos**. Usa el de 29 € y
aplícale un cupón de Stripe —por ejemplo, 12 meses al 50 %— condicionado a dos cierres
semanales acompañados y a permiso escrito para publicar sus cifras. Así el catálogo
mantiene seis `price_id` limpios, que es justo lo que comprueban las pruebas del
repositorio.

### Qué NO hace falta para el primer euro

Para que nadie se invente trabajo:

- **La revisión de la aplicación en Meta.** Es del camino B (Embedded Signup).
  Ignórala hasta que dar de alta a mano te ocupe más de media hora.
- **Inicio de sesión con Facebook para empresas.** En blanco.
- **La verificación de empresa de Meta.** Necesaria para crecer, no para cobrar.
- **Abrir el registro público.** El alta manual auditada ya existe.
- **Google OAuth, la voz, el recepcionista telefónico, la app móvil, i18n.**
- **La marca registrada.** Comprobar que está libre, sí. Registrarla, después.

### Definición de «primer euro» y criterio de parada

**Primer euro = primer cargo en Stripe *live*, de una persona que no eres tú, con
factura emitida y contrato de encargado del tratamiento aceptado.** Un cargo sin
factura correcta no cuenta: sería empezar la empresa incumpliendo lo que vende.

Y el criterio de parada, que es lo que casi nadie escribe antes de empezar: **si a 15
de noviembre de 2026 ninguno de los tres pilotos ha pagado un segundo mes**, el
problema no es el marketing ni el precio. Es que el producto todavía no ha demostrado
el ahorro que promete, y toca volver a [[Tareas-vivas]] antes de gastar un euro en
captación.

---

## 4. Presupuesto del arranque

Sobre los 4.000 € de capital inicial, en la ruta austera.

| Partida | Importe | Cuándo |
|---|---|---|
| Capital social (no es gasto) | 3.000 € | Semana 2 |
| Denominación + notaría + registro por el PAE | 150-300 € | Semanas 1-3 |
| Gestoría de constitución, si no lo haces por el PAE | 200-400 € | Semana 2 |
| Gestoría mensual | 60-120 €/mes | Desde el mes 1 |
| RETA con tarifa plana | ~80 €/mes | Desde el alta |
| **Revisión legal RGPD, DPA y términos** | **300-800 €** | **Antes del primer cobro** |
| Seguro RC profesional y ciberriesgo | 300-600 €/año | Antes del primer cobro |
| Marca OEPM | 150-300 € | Aplazable |
| **Salida de caja hasta el primer euro** | **~1.100-1.900 €** | Semanas 1-6 |

---

## 5. Lo que necesito de ti para afinar esto

Tres respuestas cambian el plan de forma material. Van a [[Preguntas-abiertas]]:

1. **¿La empresa de eventos es S.L. o eres autónomo?** Decide entre constituir o
   ampliar objeto social, y si hay o no una segunda cuota de RETA.
2. **¿Verificas Meta con la sociedad nueva o con la existente?** Determina si la
   verificación arranca en la semana 3 o puede arrancar ya.
3. **¿Camino (a) o (b) del bloque D en Veri\*Factu?** Completar la validación técnica,
   o declarar el módulo fuera del alcance Veri\*Factu durante el piloto.
