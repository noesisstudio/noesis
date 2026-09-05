# Constitución y primer euro

> **Aviso.** Esto no es asesoramiento jurídico ni fiscal. Es el mapa de decisiones y
> dependencias para que la conversación con una gestoría dure una hora y no tres.
> Cada importe, plazo y epígrafe debe confirmarse con un profesional antes de firmar.
> Fecha de redacción: **3 de septiembre de 2026**.

Este documento cubre **lo que [`Ruta-legal.pdf`](Ruta-legal.pdf) no trata**: si
constituir sociedad o darse de alta como autónomo, los trámites de constitución en
orden de dependencia y cuánto cuesta arrancar. Las obligaciones del producto
—Veri\*Factu, Meta, protección de datos, Reglamento de IA— y las tres rutas para
resolverlas están allí, y el calendario en [`Plan-60-dias.pdf`](Plan-60-dias.pdf).

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

La primera fila es la que cierra el debate. Bynoesis emite facturas con validez
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
social, dar de alta el epígrafe informático y operar Bynoesis como marca comercial de
esa sociedad. Ahorra la constitución entera y la verificación de Meta se puede pedir
ya, con una entidad que lleva tiempo inscrita —lo cual, además, verifica mejor.

El precio del atajo: **las facturas a los clientes de Bynoesis saldrán con la razón
social de eventos**, los dos negocios comparten responsabilidad patrimonial, y
separarlos después obliga a una escisión o a una venta de rama de actividad. Mi
criterio: úsalo solo si el efectivo es el problema real; si no, sociedad limpia.

Si en eventos eres autónomo, hay una buena noticia colateral: **ya estás de alta en
RETA**, así que ser administrador de la nueva S.L. no te añade una segunda cuota.

---

## 2. Todo lo legal, ordenado por dependencias

Cinco bloques, en orden de dependencia: cada uno desbloquea el siguiente. Los
bloques A y B se desarrollan aquí porque no están en ningún otro sitio; C y D
remiten a los documentos que ya los tratan, para no mantener dos versiones de lo
mismo.

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
  durante cuatro años. Bynoesis va a facturarse a sí mismo con las mismas reglas que
  exige a sus clientes.

### Bloque C · Protección de datos

Lo cubren dos documentos, y no se duplica aquí: la parte 5 de
[`Ruta-legal.pdf`](Ruta-legal.pdf) para las obligaciones, y [[RGPD-estado-y-plan]]
para la auditoría contra el código. Las acciones concretas, en [[RGPD-QUE-HACER]].

Lo único que hay que retener en este documento: **es la partida legal en la que no
se ahorra**. Presupuesta 300-800 € de revisión por un abogado de protección de datos
antes del primer cliente de pago, y encárgala el día que tengas NIF, porque es lo que
más tarda por depender de otro.

### Bloque D · Veri\*Factu como productor

También en [`Ruta-legal.pdf`](Ruta-legal.pdf), que lo desarrolla mejor que este
documento: la obligación del productor de un sistema informático de facturación está
viva desde el 29-jul-2025, no en 2027, y falta la declaración responsable.

### Bloque E · Proteger (puede esperar al primer cliente, no más)

- **Seguro de responsabilidad civil profesional y ciberriesgo**. 300-600 €/año. Antes
  del primer cliente de pago; además, es de lo primero que pregunta una gestoría
  antes de meterte su cartera.
- **Marca «Bynoesis» en la OEPM**, clase 42 y probablemente 35. ~150 €/clase. Puede
  esperar a tener diez clientes, pero comprueba **hoy** que el nombre está libre:
  descubrirlo tarde es carísimo.
- **Cesión de propiedad intelectual del código a la sociedad**. Si has desarrollado a
  título personal, el activo está fuera de la empresa. Se arregla con una aportación
  o una cesión en la constitución; después es más incómodo.

---

## 3. Dónde encaja esto en el calendario

**El plan de ejecución con fechas es [`Plan-60-dias.pdf`](Plan-60-dias.pdf).** Aquí
solo queda lo que ese plan da por hecho: la cadena de dependencias legales que decide
cuándo se puede cobrar.

> **NIF → identidad legal publicada → Stripe live → alta de un cliente → cobro**

Sin NIF no hay cuenta de Stripe a nombre de la sociedad. Sin `NOESIS_LEGAL_NAME`,
`NOESIS_LEGAL_NIF`, `NOESIS_LEGAL_ADDRESS` y `NOESIS_LEGAL_EMAIL` publicadas, el
servidor falla cerrado por diseño: la comprobación está en `readiness.py`. Y cobrar
no exige abrir el registro público, porque el alta manual auditada desde
Administración ya existe.

Por eso el **NIF provisional del modelo 036** es el hito que más desbloquea de todo
el proceso: llega pocos días después de la escritura y abre a la vez Stripe, la
identidad legal del producto y el encargo al abogado.

### Corrección sobre Meta

Una versión anterior de este documento decía que la verificación de empresa y la
revisión de la aplicación de Meta no estaban en el camino crítico, apoyándose en
[`Meta-Verificacion.pdf`](Meta-Verificacion.pdf). **[`Ruta-legal.pdf`](Ruta-legal.pdf)
sostiene lo contrario y su argumento es mejor:** el `Standard access` solo alcanza a
los activos del propio negocio, así que la WABA de un cliente —aunque la conceda a
mano— exige `Advanced access` y, con él, App Review.

Sigue siendo cierto que **se puede cobrar el primer euro sin WhatsApp**, porque el
alta permite posponerlo. Ya no es cierto que los números de clientes funcionen sin
App Review. Planifica según `Ruta-legal`.

### El precio del primer cliente: descuento, nunca gratis

Elige precio fundador sobre gratis, y por una razón que no es el dinero: **gratis
destruye la única señal que necesitas del piloto**. Un cliente que no paga no te dice
si el producto vale; te dice que no le molesta tenerlo.

Cómo hacerlo sin ensuciar el catálogo: **no crees precios nuevos**. Usa el de 29 € y
aplícale un cupón de Stripe —por ejemplo, 12 meses al 50 %— condicionado a dos
cierres semanales acompañados y a permiso escrito para publicar sus cifras. Así el
catálogo mantiene seis `price_id` limpios, que es justo lo que comprueban las pruebas
del repositorio.

### Definición de «primer euro»

**Primer cargo en Stripe *live*, de una persona que no eres tú, con factura emitida y
contrato de encargado del tratamiento aceptado.** Un cargo sin factura correcta no
cuenta: sería empezar la empresa incumpliendo lo que vende.

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
3. **¿Qué ruta de las tres de [`Ruta-legal.pdf`](Ruta-legal.pdf) eliges?** Decide a
   la vez el alcance Veri\*Factu del piloto, que es lo que bloquea reescribir la
   página `/cumplimiento` (punto 1.3 de [[RGPD-QUE-HACER]]).
