# Contrato de suscripción al servicio Bynoesis

> **Versión 1.0 — borrador para revisión jurídica.** Redactado el 18 de septiembre de
> 2026 contra el código, los textos publicados y los documentos de cumplimiento de esa
> fecha. Versión para leer y firmar: <https://claude.ai/artifact/ND5EUS5WdAWJQLvG1ddR7w>.
>
> **Esto no es asesoramiento jurídico.** Es un contrato escrito internamente para que
> un abogado TIC lo **revise** en vez de redactarlo desde cero, que es lo que abarata
> el encargo. Nada de lo que hay aquí debe firmarse con un cliente real antes de esa
> revisión y antes de cerrar los bloqueos del apartado final.
>
> Complementa —no sustituye— los textos publicados en la web: Términos de uso,
> Política de privacidad, Contrato de Encargado del Tratamiento y Aviso legal.
> Ver [`Preguntas-abogado-TIC`](../Preguntas-abogado-TIC.md): cada pregunta marcada
> como *(clave)* tiene aquí una cláusula que propone una respuesta concreta.

---

## Cómo se usa este documento

El contrato tiene tres partes y se firma **una sola vez**, en el momento en que el
cliente activa un plan de pago:

| Parte | Qué es | ¿Se firma? |
|---|---|---|
| **A · Condiciones Particulares** | La hoja de pedido: quién contrata, qué plan, a qué precio, qué módulos opcionales activa y qué consentimientos da. | **Sí.** Es la única hoja con firmas. |
| **B · Condiciones Generales** | Las 29 cláusulas que regulan la relación. No cambian de un cliente a otro. | No. Se aceptan por referencia desde la Parte A (art. 5.1 de la Ley 7/1998). |
| **C · Anexos I a VI** | Planes y límites, protección de datos, mandato de facturación, soporte, uso aceptable y consentimientos. | El Anexo III se firma. El resto forma parte del contrato por referencia. |

**Convenciones de este borrador**

- `[ENTRE CORCHETES]` = dato que hay que rellenar antes de usarlo.
- **▸ Decisión abierta** = punto en el que hay más de una redacción defendible y la
  elección es del founder o del abogado. Están recopiladas al final.
- Las referencias legales están puestas para que el revisor pueda contrastarlas
  rápido, no para lucirlas. Si una está mal, es un error que corregir, no una
  licencia literaria.

---

# PARTE A · CONDICIONES PARTICULARES

**Contrato de suscripción n.º** `[REFERENCIA]` · **Fecha** `[DD/MM/AAAA]`

## A.1 Partes

**PRESTADOR**

| | |
|---|---|
| Denominación | `[NOESIS_LEGAL_NAME]` |
| NIF | `[NOESIS_LEGAL_NIF]` |
| Domicilio | `[NOESIS_LEGAL_ADDRESS]` |
| Datos registrales | `[NOESIS_LEGAL_REGISTRY — solo si es sociedad]` |
| Representante | `[NOMBRE Y DNI]`, en calidad de `[administrador / titular]` |
| Contacto contractual | `[NOESIS_LEGAL_EMAIL]` |
| Contacto en materia de datos | `[NOESIS_LEGAL_EMAIL]` |

En adelante, **«Bynoesis»** o **«el Prestador»**.

**CLIENTE**

| | |
|---|---|
| Nombre o razón social | `[ ]` |
| NIF/CIF | `[ ]` |
| Domicilio fiscal | `[ ]` |
| Actividad / epígrafe IAE | `[ ]` |
| Persona firmante | `[NOMBRE Y DNI]`, en calidad de `[titular / representante]` |
| Email de notificaciones | `[ ]` |
| Teléfono (línea de WhatsApp) | `[ ]` |
| N.º de personas usuarias previstas | `[ ]` |

En adelante, **«el Cliente»**.

Ambas partes se reconocen capacidad suficiente para obligarse y acuerdan lo que sigue.

## A.2 Declaración del Cliente

El Cliente declara que **contrata en el ejercicio de su actividad empresarial o
profesional** y no como consumidor. En consecuencia no le resulta aplicable el texto
refundido de la Ley General para la Defensa de los Consumidores y Usuarios (RDL
1/2007) y **no dispone del derecho de desistimiento de catorce días** de su artículo
102. La baja, en cambio, es libre y sin permanencia en los términos de la cláusula 15.

## A.3 Objeto contratado

| Concepto | Valor |
|---|---|
| Plan | ☐ Autónomo ☐ Negocio ☐ Premium |
| Periodicidad | ☐ Mensual ☐ Anual (11 meses de precio, 12 de servicio) |
| Precio | `[ ]` € + IVA por `[mes / año]` |
| Tipo de IVA aplicable | 21 % |
| Total con impuestos | `[ ]` € |
| Forma de pago | Domiciliación de tarjeta o adeudo SEPA a través del proveedor de pagos |
| Fecha de inicio del servicio | `[DD/MM/AAAA]` |
| Primer período facturado | de `[ ]` a `[ ]` |
| Renovación | Automática por períodos iguales, salvo baja (cláusula 15) |
| Permanencia | **Ninguna** |
| Usuarios incluidos | Según el Anexo I |
| Condiciones especiales | `[descuento de piloto, precio fundador, meses de cortesía… o «ninguna»]` |

Los límites de uso de cada plan —acciones avanzadas de inteligencia artificial,
usuarios, almacenamiento y minutos de voz— constan en el **Anexo I** y forman parte de
lo contratado.

## A.4 Módulos opcionales y consentimientos

Cada casilla es **voluntaria, separada y revocable en cualquier momento** desde
Ajustes, sin que ello afecte al resto del servicio. El detalle está en el **Anexo VI**.

| | Módulo | Qué implica | Marcar |
|---|---|---|---|
| 1 | **WhatsApp Business** | Conectar la línea del Cliente a la API de Meta. Los mensajes pasan por Meta Platforms. | ☐ Sí ☐ No |
| 2 | **Asistente con IA externa** | Enviar a un proveedor externo el fragmento de texto que el sistema no resuelve en local. Proveedor, país y garantía en el Anexo II.3. | ☐ Sí ☐ No |
| 3 | **Transcripción de notas de voz** | Enviar el audio a un proveedor de transcripción. | ☐ Sí ☐ No |
| 4 | **Acceso de gestoría** | Dar a la asesoría designada acceso de solo lectura a los períodos cerrados. Asesoría: `[nombre y NIF]`. | ☐ Sí ☐ No |
| 5 | **Registro de jornada** | Activar el fichaje para las personas trabajadoras del Cliente (cláusula 7). | ☐ Sí ☐ No |
| 6 | **Funciones en beta** | Usar funciones en pruebas, sin nivel de servicio y sin coste mientras duren (cláusula 4.4). | ☐ Sí ☐ No |
| 7 | **Comunicaciones comerciales de Bynoesis** | Recibir novedades de producto por email. No afecta a los avisos de servicio. | ☐ Sí ☐ No |

## A.5 Documentos que se entregan y se aceptan

El Cliente declara que, **antes de firmar**, ha recibido un ejemplar completo y ha
tenido oportunidad de leer:

- [ ] Parte B · Condiciones Generales (cláusulas 1 a 29).
- [ ] Anexo I · Planes, límites y precios.
- [ ] Anexo II · Contrato de Encargado del Tratamiento (art. 28 RGPD).
- [ ] Anexo III · Mandato de expedición de facturas por cuenta del Cliente.
- [ ] Anexo IV · Nivel de servicio y soporte.
- [ ] Anexo V · Política de uso aceptable.
- [ ] Anexo VI · Consentimientos separados.

Esta entrega y esta aceptación se hacen a los efectos del artículo 5.1 de la Ley
7/1998, de 13 de abril, sobre Condiciones Generales de la Contratación.

## A.6 Firmas

| Por el Prestador | Por el Cliente |
|---|---|
| | |
| Nombre: | Nombre: |
| DNI: | DNI: |
| Cargo: | Cargo: |
| Fecha: | Fecha: |

Si la firma es electrónica, se está a lo previsto en la cláusula 28.

---

# PARTE B · CONDICIONES GENERALES

## 1. Definiciones

**Servicio**: la plataforma Bynoesis en sus canales web, WhatsApp y aplicación, con las
funcionalidades del plan contratado.

**Contenido del Cliente**: todo dato, documento, imagen, audio o texto que el Cliente o
las personas a las que autoriza introduzcan en el Servicio, incluidos los datos
personales de sus clientes, contactos, proveedores y personas trabajadoras.

**Clientes finales**: las personas o empresas a las que el Cliente presta sus servicios
y cuyos datos trata a través de la plataforma.

**Datos personales**, **responsable**, **encargado**, **subencargado**, **interesado**
y **violación de seguridad**: con el significado del Reglamento (UE) 2016/679 (RGPD).

**Propuesta**: cualquier borrador, cálculo, texto o acción que el Servicio prepara y
que requiere confirmación del Cliente antes de producir efectos (cláusula 5).

**Acción avanzada de IA**: la unidad de consumo definida en el Anexo I.3.

**Período de servicio**: el mes o el año, según la periodicidad contratada, por el que
se paga por anticipado.

## 2. Objeto y orden de prelación

2.1. El Prestador concede al Cliente el derecho no exclusivo, intransferible y limitado
a la vigencia del contrato a usar el Servicio en modalidad de software como servicio, a
cambio del precio del Anexo I. No se vende software, no se cede código y no se instala
nada en los sistemas del Cliente.

2.2. El contrato lo forman las Condiciones Particulares, estas Condiciones Generales y
los Anexos I a VI. En caso de contradicción prevalecen, por este orden: **(1)** el
Anexo II (protección de datos), **(2)** las Condiciones Particulares, **(3)** los demás
Anexos, **(4)** estas Condiciones Generales y **(5)** los textos publicados en la web
del Servicio.

2.3. El Anexo II prevalece sobre todo lo demás porque regula obligaciones que las
partes no pueden alterar libremente. Ninguna otra cláusula puede interpretarse de forma
que reduzca las garantías del artículo 28 del RGPD.

## 3. Alta, prueba y perfeccionamiento

3.1. El Servicio ofrece un período de prueba de **catorce (14) días naturales sin
tarjeta**. Terminada la prueba **no se produce ningún cargo automático**: si el Cliente
no activa un plan, la cuenta pasa al modo consulta de la cláusula 16.2 y conserva sus
datos.

3.2. El contrato se perfecciona con la firma de las Condiciones Particulares o, si la
contratación se completa en línea, con la aceptación expresa en el proceso de pago y el
primer cobro válido. En ambos casos el Prestador remite copia íntegra del contrato en
soporte duradero.

3.3. Las partes, que contratan entre profesionales, acuerdan expresamente excluir la
obligación de confirmación de recepción del artículo 28.1 de la Ley 34/2002 (LSSI),
conforme permite su artículo 28.3.b). El Prestador confirmará igualmente el alta por
correo electrónico como buena práctica.

## 4. El Servicio

4.1. **Alcance.** El Servicio permite al Cliente organizar su agenda, su cartera de
clientes, sus trabajos, presupuestos, facturas, cobros, gastos y documentos y —según el
plan— sus proyectos, su equipo, el registro de jornada y el acceso de su gestoría. El
Cliente opera por conversación en WhatsApp, por web o por ambas.

4.2. **Evolución.** El Prestador puede mejorar, modificar o reorganizar funciones sin
degradar de forma sustancial lo contratado. Si una modificación **elimina o reduce de
forma relevante** una funcionalidad que el Anexo I atribuye al plan del Cliente, se
aplica la cláusula 25.2 (resolución con devolución proporcional).

4.3. **Lo que el Servicio no es.** No es una entidad de pago ni gestiona fondos: no
cobra, no paga y no transfiere dinero por cuenta del Cliente; prepara documentos y
recordatorios de cobro. No presenta declaraciones ante la Administración. No sustituye
a una asesoría fiscal, laboral o jurídica (cláusula 5.4).

4.4. **Funciones en beta.** Las funciones identificadas como *beta* —hoy, la
recepcionista de llamadas— se prestan **«tal cual»**, sin nivel de servicio, sin
garantía de continuidad y **sin coste adicional mientras dure la beta**. El Prestador
puede retirarlas avisando con quince (15) días. Su retirada no da derecho a
indemnización ni activa la cláusula 25.2, salvo que se hubieran facturado aparte.

## 5. Naturaleza del Servicio: Bynoesis prepara, el Cliente confirma

5.1. Esta cláusula es el eje del contrato y de su régimen de responsabilidad.

5.2. El Servicio lee información, calcula importes, redacta borradores y propone
acciones. **Salvo indicación expresa en contrario, toda salida del Servicio es una
Propuesta revisable.** El Cliente conserva la decisión final sobre la emisión y
anulación de facturas, el envío de comunicaciones a terceros, la reclamación de cobros,
los pagos, las rectificaciones, la información que se traslada a la Administración y
cualquier otra actuación irreversible o con efecto económico o fiscal.

5.3. Antes de emitir una factura el Cliente debe comprobar, como mínimo, la identidad y
el NIF de emisor y destinatario, la fecha, la serie, el concepto, la base imponible, el
tipo y la cuota de IVA, la retención de IRPF si procede y el total. Emitida una factura
**no se edita**: un error se corrige por el procedimiento legal aplicable —normalmente
una factura rectificativa del artículo 15 del RD 1619/2012—, conservando el original y
la trazabilidad.

5.4. **No es asesoramiento.** Los cálculos de IVA, IRPF, totales, plazos y umbrales son
una ayuda operativa, no asesoramiento fiscal, laboral ni jurídico. La calificación de
las operaciones, la aplicación de tipos, exenciones y retenciones, la llevanza de
libros y la presentación de declaraciones corresponden al Cliente y, en su caso, a su
asesoría.

5.5. **Trazabilidad de la confirmación.** El Servicio registra qué persona confirmó
cada acción irreversible y cuándo. Ese registro está a disposición del Cliente y
acredita la intervención humana exigida por esta cláusula.

5.6. Nada de lo anterior exime al Prestador de prestar el Servicio con la diligencia
que le es exigible ni de responder de los defectos que le sean imputables conforme a la
cláusula 21. La confirmación del Cliente reparte la responsabilidad sobre la
**decisión**, no sobre el correcto funcionamiento de la herramienta.

## 6. Facturación por cuenta del Cliente y sistema informático de facturación

6.1. El Cliente encarga al Prestador el cumplimiento material de la obligación de
expedir factura, al amparo del artículo 5.1 del Reglamento por el que se regulan las
obligaciones de facturación (RD 1619/2012). El mandato, su alcance y sus límites
constan en el **Anexo III**, que las partes firman junto con este contrato.

6.2. **El obligado tributario sigue siendo el Cliente.** La expedición material por un
tercero no traslada ninguna obligación fiscal: el Cliente responde ante la
Administración del contenido, la numeración, el plazo y la conservación de sus
facturas.

6.3. **Numeración y conservación.** El Servicio mantiene series y numeración
correlativas por negocio, congela los datos de la factura una vez emitida y conserva el
registro asociado. El Cliente puede exportar en cualquier momento sus facturas y sus
registros en formato reutilizable, y se obliga a conservarlos durante los plazos
legales (cláusula 16.4).

6.4. **Veri\*Factu y sistemas informáticos de facturación.** El Servicio incorpora un
registro de facturación inalterable y encadenado, con huella y código QR, construido
según los documentos técnicos de la AEAT. **A la fecha de este contrato la remisión
telemática a la AEAT no está activada y el Prestador no declara disponer de la
declaración responsable del artículo 13 del RD 1007/2023.** El Prestador se obliga a
completar la adaptación y a emitir esa declaración **antes de la fecha en que la
obligación resulte exigible al Cliente** conforme al RD 1007/2023 y su normativa de
desarrollo —1 de enero de 2027 para contribuyentes del Impuesto sobre Sociedades y 1 de
julio de 2027 para el resto de obligados— o, en su defecto, a comunicárselo con
antelación suficiente para que pueda adoptar otra solución, con derecho a resolver sin
penalización y con devolución de la parte proporcional no consumida.

▸ *Decisión abierta 1: si el abogado o la asesoría consideran que 6.4 crea una
obligación de resultado con riesgo desproporcionado para una empresa de esta dimensión,
la alternativa es redactarla como obligación de medios más un derecho de salida
reforzado. No recomiendo eliminarla: sin compromiso de fecha, quien compra facturación
asume un riesgo que no puede valorar.*

## 7. Registro de jornada

7.1. Si el Cliente activa el módulo de fichaje, el Servicio le proporciona una
herramienta para cumplir el artículo 34.9 del Estatuto de los Trabajadores. Los
registros se sellan y encadenan para que una modificación posterior sea detectable, y
se conservan durante **cuatro (4) años** a disposición de las personas trabajadoras, sus
representantes y la Inspección de Trabajo.

7.2. **La obligación laboral es del Cliente como empresario.** Le corresponde organizar
el registro, en su caso previa consulta con la representación legal de las personas
trabajadoras; informar a cada persona trabajadora del tratamiento de sus datos con el
contenido del artículo 13 del RGPD; garantizar que el registro refleja la jornada real;
y atender los requerimientos de la Inspección. El Prestador facilita el texto
informativo modelo del Anexo II.7, que el Cliente debe revisar y asumir como propio.

7.3. El Prestador no responde de las sanciones derivadas de un registro incompleto,
falseado o no comunicado, salvo que el defecto sea consecuencia directa de un fallo
imputable al Servicio y acreditado.

7.4. La baja de la cuenta no permite borrar registros de jornada dentro del plazo legal
de conservación: se conservan bloqueados en los términos de la cláusula 16.4.

## 8. Inteligencia artificial

8.1. **Por defecto, en local.** El funcionamiento ordinario del Servicio se resuelve con
reglas y modelos propios, sin envío de contenido a terceros.

8.2. **IA externa: solo con consentimiento.** El envío de contenido a un proveedor
externo de inteligencia artificial requiere que el Cliente lo active expresamente
(Anexo VI). Antes de activarlo se le muestran el proveedor, el país de tratamiento y la
garantía de transferencia aplicable. Solo viaja **el fragmento no resuelto en local**:
nunca la base de datos, ni la cartera de clientes, ni los documentos completos. El
consentimiento es revocable en cualquier momento y su revocación no afecta al resto del
Servicio.

8.3. **Transparencia (art. 50 del Reglamento (UE) 2024/1689).** El Servicio identifica
como generado o asistido por inteligencia artificial el contenido que lo sea. Cuando el
Cliente utilice el Servicio para componer mensajes que se envían a sus clientes finales
con la identidad del Cliente, **el Cliente actúa como responsable del despliegue** y se
obliga a no suprimir ni alterar las indicaciones de transparencia que el Servicio
incorpore.

▸ *Decisión abierta 2: la pregunta 18 para el abogado es exactamente esta. Esta
redacción adopta el criterio prudente —el Cliente es responsable del despliegue, el
Prestador del sistema— y obliga a no borrar el aviso. Si el criterio jurídico es otro,
hay que cambiar esta cláusula y el texto que el producto inserta en el primer mensaje.*

8.4. **No se entrena con el Contenido del Cliente.** El Prestador **no utiliza el
Contenido del Cliente para entrenar, ajustar ni evaluar modelos de inteligencia
artificial**, ni propios ni de terceros, y lo exige contractualmente a sus subencargados
de IA. Podrá utilizar métricas de uso y datos **agregados y anonimizados** —que no
permitan reidentificar al Cliente, a sus clientes finales ni a sus personas
trabajadoras— para medir calidad, dimensionar costes y mejorar el Servicio. Cualquier
uso distinto exigirá un consentimiento separado, informado y revocable.

8.5. Las decisiones que el Servicio propone no producen efectos jurídicos ni afectan
significativamente a nadie sin intervención humana: no hay decisiones automatizadas en
el sentido del artículo 22 del RGPD y no se elabora perfilado de personas.

## 9. Mensajes a los clientes finales del Cliente

9.1. Cuando el Cliente envía —o autoriza que se envíen en su nombre— presupuestos,
facturas, recordatorios de cobro, avisos de cita o cualquier otra comunicación a sus
clientes finales, **actúa como responsable del tratamiento de esos datos** y bajo su
identidad.

9.2. El Cliente **garantiza** que dispone de base jurídica para comunicarse con cada
destinatario, que los teléfonos y correos que introduce se han obtenido lícitamente y
que ha informado a los interesados conforme a los artículos 13 y 14 del RGPD.

9.3. El Cliente se obliga a **no utilizar el Servicio para enviar comunicaciones
comerciales no solicitadas** en el sentido del artículo 21 de la Ley 34/2002 (LSSI). Los
envíos previstos por defecto están ligados a una factura, un presupuesto o una cita
reales del destinatario y se apoyan en la relación entre el Cliente y esa persona.

9.4. El Servicio atiende las solicitudes de baja de los destinatarios y bloquea los
envíos posteriores. El Prestador puede suspender el canal de mensajería de un Cliente
—no el resto del Servicio— si recibe reclamaciones fundadas, si el proveedor de
mensajería degrada su calidad o si detecta un uso contrario a esta cláusula, previo
aviso salvo urgencia.

9.5. El uso de WhatsApp queda además sujeto a las condiciones y políticas de Meta
Platforms, que el Prestador traslada al Cliente y que pueden cambiar sin intervención de
ninguna de las partes.

## 10. Obligaciones del Cliente

10.1. Facilitar datos veraces y mantenerlos actualizados, en particular los fiscales.

10.2. Custodiar sus credenciales, activar el segundo factor cuando esté disponible y
comunicar sin demora cualquier sospecha de acceso indebido.

10.3. Revisar y revocar los permisos de personas trabajadoras, gestorías y enlaces
privados cuando dejen de ser necesarios.

10.4. Disponer de base jurídica para tratar los datos que introduce y no introducir
categorías especiales del artículo 9 del RGPD salvo necesidad acreditada y base legal
suficiente.

10.5. Revisar las Propuestas antes de confirmarlas (cláusula 5) y comunicar sin demora
cualquier cálculo, documento o envío incorrecto, indicando el identificador del registro
y evitando incluir datos personales innecesarios.

10.6. Respetar la Política de uso aceptable del **Anexo V**.

10.7. Conservar fuera de la plataforma, por sus propios medios, los documentos que deba
custodiar por obligación legal. El Servicio ofrece exportación permanente; la custodia
última es del Cliente.

## 11. Cuentas, equipo, gestoría y portales

11.1. El Cliente es responsable de la actividad realizada desde su cuenta y desde las
cuentas que crea para su equipo.

11.2. Cuando el Cliente da acceso a su **gestoría**, lo hace como instrucción
documentada al Prestador. El acceso es de solo lectura sobre los períodos que el Cliente
habilita, exige doble factor y queda registrado. El Cliente regula su propia relación
con la asesoría; el Prestador se limita a ejecutar la instrucción.

▸ *Decisión abierta 3: la pregunta 02 para el abogado —qué es la gestoría: subencargada
del Prestador, encargada del Cliente o cesionaria— condiciona esta cláusula y el Anexo
II.4. La redacción actual la trata como acceso autorizado por el Cliente, no como
subencargo del Prestador. Es defendible, pero hay que confirmarlo antes de firmar.*

11.3. Los **portales de cliente final** son enlaces privados, no indexables y
caducables que permiten a un destinatario ver el documento que le concierne sin
registrarse. El Cliente decide a quién envía cada enlace.

11.4. **Soporte con acceso a la cuenta.** El Prestador no accede al Contenido del
Cliente salvo que sea imprescindible para resolver una incidencia y el Cliente lo
autorice mediante la autorización temporal del producto, limitada por motivo, alcance y
caducidad. Todo acceso queda registrado y es consultable por el Cliente. El Cliente no
debe enviar contraseñas por ningún canal.

## 12. Precio, impuestos y pago

12.1. Los precios del **Anexo I** se expresan **sin IVA**. Al importe se le añade el IVA
al tipo vigente y cualquier otro impuesto que resulte aplicable.

12.2. El pago es **por anticipado** al inicio de cada Período de servicio, mediante
tarjeta o adeudo SEPA domiciliados a través del proveedor de pagos. El Prestador no
almacena datos de tarjeta en ningún momento.

12.3. El Prestador emite factura por cada cobro y la pone a disposición del Cliente en
su cuenta y por correo electrónico.

12.4. El Cliente autoriza los cargos recurrentes correspondientes al plan y la
periodicidad contratados hasta que curse la baja conforme a la cláusula 15.

12.5. Los importes pagados no se prorratean por un uso inferior al contratado, salvo en
los supuestos expresamente previstos en las cláusulas 6.4, 13.3, 16.3, 21.6, 23 y 25.2.

## 13. Revisión de precios

13.1. El Prestador puede revisar los precios **una vez cada doce (12) meses**,
comunicándolo con **treinta (30) días naturales** de antelación a la renovación.

13.2. El incremento no superará la variación del Índice de Precios de Consumo general
publicado por el INE en los doce meses anteriores **más cinco (5) puntos porcentuales**.

13.3. Un incremento superior a ese límite, o un cambio de la estructura de planes que
empeore la posición del Cliente, le da derecho a **resolver sin coste** antes de la
renovación, conservando el acceso hasta el final del período ya pagado.

13.4. Ninguna revisión afecta a un período ya facturado. El precio anual pagado se
mantiene durante los doce meses contratados.

## 14. Impago y suspensión

14.1. Si un cobro resulta fallido, el Prestador lo comunicará al Cliente y le dará
**siete (7) días naturales** para regularizarlo, reintentando el cargo durante ese
plazo.

14.2. Transcurrido el plazo sin pago, el Prestador puede **suspender las funciones de
escritura** (crear, modificar, emitir, enviar y automatizar). **En ningún caso
suspenderá el acceso de consulta y la exportación del Contenido del Cliente**, que se
mantienen en los términos de la cláusula 16.2. El Prestador no retiene datos del Cliente
como medida de presión de cobro.

14.3. Regularizado el pago, el Servicio se restablece sin coste de reactivación.

14.4. Si el impago se prolonga **treinta (30) días**, el Prestador puede resolver el
contrato conforme a la cláusula 15.4, sin perjuicio de reclamar las cantidades
devengadas.

14.5. Tratándose de una operación entre empresas, las cantidades vencidas devengan el
interés de demora previsto en la Ley 3/2004, de 29 de diciembre, de lucha contra la
morosidad en las operaciones comerciales.

## 15. Duración, cambio de plan y baja

15.1. El contrato tiene la duración del Período de servicio contratado y **se renueva
automáticamente** por períodos iguales. **No hay permanencia mínima.**

15.2. El Cliente puede **cambiar de plan** en cualquier momento. La subida se aplica de
inmediato y se factura la diferencia prorrateada; la bajada surte efecto en la
renovación siguiente. El cambio no obliga a migrar datos ni a cambiar de herramienta.

15.3. El Cliente puede **cursar baja** en cualquier momento desde su cuenta o
comunicándolo al contacto del Prestador. La baja impide futuras renovaciones y
**mantiene el acceso hasta el final del período ya pagado**. No genera devolución del
período en curso, salvo lo previsto en las cláusulas 6.4, 13.3, 16.3, 21.6, 23 y 25.2.

15.4. Cualquiera de las partes puede resolver el contrato por **incumplimiento grave**
de la otra que no se subsane en quince (15) días desde el requerimiento escrito. El
Prestador puede además suspender o resolver de inmediato, sin ese plazo, ante un uso que
infrinja el Anexo V y ponga en riesgo la seguridad, la legalidad o el servicio a
terceros, comunicándolo simultáneamente y de forma motivada.

## 16. Efectos de la terminación

16.1. **Exportación.** El Cliente puede exportar su información —clientes, trabajos,
presupuestos, facturas, cobros, gastos y documentos— en formatos abiertos y
reutilizables **en cualquier momento, durante y después de la relación**, desde la
propia aplicación y sin coste.

16.2. **Modo consulta.** Terminada la suscripción, y salvo que el Cliente pida la
supresión, la cuenta pasa a modo consulta: sin funciones de escritura, pero **con acceso
de lectura y descarga de todo su contenido**. El Prestador garantiza el modo consulta
durante un mínimo de **doce (12) meses** desde la baja y no suprimirá la cuenta sin
avisar con **treinta (30) días** al correo de notificaciones del Cliente.

▸ *Decisión abierta 4: la web promete «si dejas de pagar, no te cerramos la puerta» sin
plazo. Mantenerlo indefinidamente tiene un coste de almacenamiento que crece con cada
baja. Este borrador convierte la promesa en un mínimo garantizado de doce meses más un
preaviso de treinta días antes de borrar nada: igual de honesta y sostenible. Si el
founder quiere mantener el «para siempre», hay que escribirlo así y asumir el coste.*

16.3. **Supresión a petición.** El Cliente puede pedir en cualquier momento la supresión
de su cuenta, que se ejecutará en los términos del Anexo II.9 con la excepción de la
cláusula siguiente. Si la petición se produce en los primeros quince (15) días de un
período anual recién renovado, se devolverá la parte proporcional no consumida.

16.4. **Lo que no se puede borrar.** Las facturas emitidas y los registros de jornada
dentro de su plazo legal de conservación **no se suprimen**: quedan **bloqueados** en el
sentido del artículo 32 de la Ley Orgánica 3/2018, accesibles únicamente para atender a
la Administración, a jueces y tribunales, y excluidos de informes, agregados y de
cualquier tratamiento con inteligencia artificial. No es una negativa a atender un
derecho: es el cumplimiento de una obligación legal, y se comunica al Cliente con el
plazo concreto de cada dato.

16.5. **Copias de seguridad.** El dato suprimido puede permanecer en copias de seguridad
hasta que el ciclo de rotación las sobrescriba, con un máximo aproximado de dos meses.
Durante ese tiempo permanece bloqueado. Si se restaura una copia anterior a una
supresión, la supresión se reaplica inmediatamente.

## 17. Disponibilidad, mantenimiento y soporte

17.1. El Prestador desplegará esfuerzos razonables para mantener el Servicio disponible
de forma continuada, con los objetivos, la ventana de soporte y los tiempos de respuesta
del **Anexo IV**.

17.2. El Prestador puede realizar tareas de mantenimiento. Las programadas se avisarán
con **cuarenta y ocho (48) horas** y se harán, siempre que sea posible, fuera del
horario laboral. Las urgentes de seguridad pueden ejecutarse sin preaviso, con
comunicación posterior.

17.3. **Continuidad.** El Prestador mantiene copias de seguridad cifradas, una copia
externa independiente del proveedor principal y procedimientos de restauración
documentados. Los objetivos de punto y tiempo de recuperación figuran en el Anexo IV.4
**expresamente como objetivos internos y no como garantía contractual**, hasta que el
simulacro de restauración completo esté ejecutado y cronometrado.

## 18. Servicios de terceros

18.1. Algunas funciones dependen de proveedores externos: alojamiento, base de datos,
pagos, mensajería de WhatsApp, correo, inteligencia artificial, transcripción y
almacenamiento de copias. Están identificados en el Anexo II.3.

18.2. Una caída, un cambio de condiciones o una interrupción de un proveedor externo
puede degradar la función que depende de él. Esa degradación **no afecta al Contenido
del Cliente conservado por el Prestador**, que sigue accesible y exportable.

18.3. El Prestador elige a sus proveedores con diligencia, suscribe con ellos los
contratos exigidos por el RGPD y responde de su actuación en los términos del artículo
28.4 del RGPD y de la cláusula 21.

18.4. Si un proveedor de una función opcional deja de estar disponible sin alternativa
equivalente, se aplica la cláusula 25.2.

## 19. Protección de datos y confidencialidad

19.1. **Dos papeles distintos.** El Prestador es **responsable** de los datos de la
relación contractual con el Cliente —identificación, facturación, acceso, soporte y
seguridad—, con la información de su Política de privacidad. Y es **encargado** respecto
del Contenido del Cliente, en los términos del **Anexo II**, que se firma junto con este
contrato y cumple el artículo 28.3 del RGPD.

19.2. **Confidencialidad.** Cada parte mantendrá en secreto la información de la otra a
la que acceda, no la usará para fines distintos del contrato y la protegerá con la
diligencia con que protege la propia. La obligación dura la vigencia del contrato y
**tres (3) años** desde su terminación, e **indefinidamente** para los datos personales y
para los secretos empresariales protegidos por la Ley 1/2019.

19.3. **Personal.** Cada parte garantiza que las personas que acceden a la información de
la otra están sujetas a confidencialidad por contrato o por obligación legal.

## 20. Propiedad intelectual y titularidad de los datos

20.1. El software, la marca, los diseños, la documentación y toda mejora del Servicio son
y seguirán siendo del Prestador o de sus licenciantes. El contrato no transmite ningún
derecho de propiedad intelectual o industrial más allá del derecho de uso de la cláusula
2.1.

20.2. **El Contenido del Cliente es del Cliente.** El Prestador solo obtiene la licencia
limitada, no exclusiva y temporal necesaria para alojarlo, procesarlo, mostrarlo,
transmitirlo y respaldarlo con el fin de prestar el Servicio y cumplir este contrato. Esa
licencia termina con la supresión del contenido.

20.3. El Cliente garantiza disponer de los derechos necesarios sobre el contenido que
introduce, incluidos logotipos y documentos de terceros.

20.4. **Sugerencias.** Si el Cliente propone mejoras, el Prestador puede implementarlas
libremente y sin contraprestación. Esto no le da derecho alguno sobre el Contenido del
Cliente ni sobre sus datos.

20.5. **Referencias comerciales.** El Prestador **no** usará el nombre, la marca ni el
logotipo del Cliente como referencia pública sin su autorización previa y por escrito,
revocable en cualquier momento.

## 21. Garantías, responsabilidad y límites

21.1. **Garantía del Prestador.** El Servicio se prestará de forma profesional y
diligente, conforme a la descripción del plan contratado y a la normativa aplicable. El
Prestador corregirá sin coste los defectos del Servicio que le sean imputables.

21.2. **Exclusión de garantías implícitas.** Salvo lo anterior y lo que la ley imponga
imperativamente, el Servicio se presta sin más garantías. El Prestador no garantiza que
esté libre de interrupciones o de errores, ni que sus Propuestas sean completas o
correctas en todos los casos: por eso existe la cláusula 5.

21.3. **Daños excluidos.** En la medida permitida por la ley, el Prestador no responde
del lucro cesante, la pérdida de negocio, de oportunidad, de clientela o de reputación,
ni de daños indirectos o consecuenciales, ni de las consecuencias de confirmar una
Propuesta sin revisarla.

21.4. **Límite cuantitativo.** La responsabilidad total y acumulada del Prestador frente
al Cliente por cualquier reclamación derivada de este contrato queda limitada a **la
mayor de estas dos cantidades: el importe efectivamente pagado por el Cliente en los
doce (12) meses anteriores al hecho que motiva la reclamación, o quinientos (500)
euros**. Para las reclamaciones derivadas del incumplimiento del Anexo II (protección de
datos) o del deber de confidencialidad, el límite se eleva a **dos (2) veces** esa
cantidad.

21.5. **Lo que nunca se limita.** Los límites anteriores **no se aplican** al dolo, a la
culpa grave, a los daños a la vida o la integridad física, a la responsabilidad frente a
los interesados del artículo 82 del RGPD, a las sanciones impuestas a una parte por
hechos imputables a la otra, ni a cualquier responsabilidad que la ley declare no
excluible ni limitable (entre otros, el artículo 1102 del Código Civil).

▸ *Decisión abierta 5: la pregunta 10 para el abogado. Un tope de doce mensualidades es
el estándar en SaaS B2B, pero sobre 29 €/mes son 348 €: un tope tan bajo puede resultar
irrisorio frente al daño de una liquidación mal calculada, y un juez podría tumbarlo por
contrario a la buena fe (art. 1255 CC y art. 8.1 de la Ley 7/1998). Por eso se añaden el
suelo de 500 € y el doble para datos. Si se contrata seguro de responsabilidad civil
(cláusula 22), lo coherente es elevar el tope hasta el límite de la póliza: un tope que
el seguro cubre no cuesta dinero y hace el contrato mucho más defendible.*

21.6. **Incumplimiento del Prestador.** Si el Prestador incumple de forma grave y no
subsana, el Cliente puede resolver y recibir la devolución de la parte proporcional del
período pagado y no disfrutado, sin perjuicio de los daños que acredite dentro de los
límites anteriores.

21.7. **Indemnidad del Cliente.** El Cliente mantendrá indemne al Prestador frente a
reclamaciones de terceros derivadas de: contenido introducido sin derecho, envío de
comunicaciones sin base jurídica (cláusula 9), incumplimiento de sus obligaciones
laborales o fiscales y uso contrario al Anexo V.

21.8. **Plazo de reclamación.** Toda reclamación deberá comunicarse por escrito dentro de
los **doce (12) meses** siguientes a que la parte afectada conozca el hecho que la
motiva, sin perjuicio de los plazos de prescripción legales imperativos.

## 22. Seguro

El Prestador mantendrá en vigor durante toda la relación una póliza de responsabilidad
civil profesional con una cobertura mínima de `[IMPORTE]` euros por siniestro, y
acreditará su vigencia a petición del Cliente.

▸ *Decisión abierta 6: esta cláusula **no debe incluirse hasta que la póliza exista**.
Declarar un seguro que no se tiene es una manifestación falsa en contrato, y de las
caras. Mientras no esté contratada, se elimina la cláusula entera; no se deja el importe
en blanco.*

## 23. Fuerza mayor

Ninguna parte responde del incumplimiento debido a causas fuera de su control razonable
—catástrofes, cortes generalizados de red o electricidad, ciberataques a infraestructuras
de terceros, decisiones de autoridad— mientras duren y siempre que lo comunique sin
demora y haga lo razonable para mitigar sus efectos. Si la causa se prolonga más de
treinta (30) días, cualquiera de las partes puede resolver sin penalización, con
devolución de la parte proporcional no disfrutada. La falta de fondos nunca es fuerza
mayor.

## 24. Cesión, subcontratación y cambio de titular del Prestador

24.1. El Cliente no puede ceder el contrato sin autorización escrita del Prestador, que
no se denegará sin motivo.

24.2. El Prestador puede subcontratar la prestación técnica en los términos del Anexo
II.3, respondiendo de sus subcontratistas como de sus propios actos.

24.3. **Cambio de titular.** El Cliente **consiente anticipadamente** que el Prestador
ceda su posición contractual a una sociedad constituida o controlada por el mismo
titular, o a la entidad resultante de una reestructuración empresarial, siempre que:
**(a)** se le comunique con **treinta (30) días** de antelación; **(b)** la cesionaria
asuma íntegramente este contrato, sus anexos y las obligaciones de protección de datos; y
**(c)** el Cliente conserve el derecho a resolver sin coste dentro de esos treinta días,
con devolución proporcional. Este consentimiento se presta a los efectos de los artículos
1205 y concordantes del Código Civil.

▸ *Decisión abierta 7: esta cláusula existe porque el Prestador es hoy una persona física
y el plan es constituir una S.L. Sin ella, el cambio de titular obliga a pedir
consentimiento cliente por cliente —o a novar los contratos uno a uno— justo cuando la
empresa tiene más que hacer. Confirmar con el abogado que basta esta redacción y qué hay
que rehacer además en textos y aceptaciones ya registradas (pregunta 22).*

## 25. Modificación del contrato y de los anexos

25.1. El Prestador puede modificar estas Condiciones Generales y sus Anexos por razones
legales, técnicas o de evolución del Servicio, comunicándolo con **treinta (30) días** de
antelación al correo de notificaciones del Cliente.

25.2. Si la modificación **perjudica de forma relevante** al Cliente —reduce
funcionalidad contratada, eleva el precio por encima del límite de la cláusula 13.2,
amplía sus obligaciones o rebaja las garantías del Prestador—, el Cliente puede
**resolver sin coste** dentro de esos treinta días, con devolución de la parte
proporcional del período pagado y no disfrutado. El uso del Servicio después de la fecha
de entrada en vigor, sin haber resuelto, implica aceptación.

25.3. Las modificaciones exigidas por una norma imperativa o por una autoridad de control
se aplican en el plazo que la propia norma imponga, informando al Cliente.

25.4. Las Condiciones Particulares y el Anexo III solo se modifican por acuerdo escrito de
ambas partes.

## 26. Comunicaciones

26.1. Las comunicaciones se dirigirán a los correos electrónicos de las Condiciones
Particulares y se entenderán recibidas el día hábil siguiente a su envío. Cada parte debe
mantener actualizada su dirección.

26.2. Las comunicaciones relativas a la **resolución del contrato, a una violación de
seguridad o a una reclamación formal** se harán por un medio que permita acreditar su
recepción y su contenido.

26.3. Los avisos de servicio, mantenimiento e incidencias pueden comunicarse además dentro
de la aplicación o por WhatsApp.

## 27. Nulidad parcial, integridad y tolerancia

27.1. La nulidad de una cláusula no afecta al resto del contrato, que seguirá vigente; la
cláusula nula se sustituirá por otra válida que se aproxime a su finalidad.

27.2. Este contrato y sus anexos sustituyen a cualquier acuerdo anterior sobre el mismo
objeto, incluidos los acuerdos de piloto o de prueba, salvo que estos prevean expresamente
su supervivencia.

27.3. La tolerancia de un incumplimiento no supone renuncia a exigirlo en el futuro.

## 28. Firma y prueba del consentimiento

28.1. El contrato puede firmarse de forma manuscrita, mediante firma electrónica conforme
al Reglamento (UE) 910/2014 y la Ley 6/2020, o mediante aceptación expresa en el proceso
de contratación en línea.

28.2. En este último caso, el Prestador conserva como prueba del consentimiento: la
versión exacta de los documentos aceptados, su huella criptográfica, la fecha y la hora,
la identidad de la cuenta y el resultado de la verificación del segundo factor cuando se
haya empleado. El Cliente puede solicitar copia de ese registro en cualquier momento.

28.3. Ambas partes reconocen a la firma electrónica y al registro anterior plena validez
probatoria entre ellas.

## 29. Ley aplicable y jurisdicción

29.1. El contrato se rige por la **legislación española**.

29.2. Las partes procurarán resolver de buena fe cualquier discrepancia antes de acudir a
los tribunales, mediante una reunión entre responsables en el plazo de quince días desde
el requerimiento.

29.3. Para cualquier controversia, y **contratando ambas partes como profesionales**, se
someten expresamente a los **Juzgados y Tribunales de `[CIUDAD]`**, con renuncia a
cualquier otro fuero que pudiera corresponderles.

29.4. En materia de protección de datos, el Cliente y los interesados pueden dirigirse en
todo caso a la **Agencia Española de Protección de Datos** (www.aepd.es).

▸ *Decisión abierta 8: la sumisión expresa a los juzgados del domicilio del Prestador es
válida entre profesionales (art. 54 LEC) y le conviene. Confirmar que no hay riesgo de que
se considere abusiva si algún cliente pudiera ser calificado como consumidor —por ejemplo,
alguien que contrata antes de darse de alta— y decidir si se excluye ese caso
expresamente.*

---

# PARTE C · ANEXOS

---

# ANEXO I · Planes, límites y precios

## I.1 Precios

Precios **sin IVA**. El anual equivale a pagar once meses y usar el Servicio doce.

| Plan | Mensual | Anual | Para quién |
|---|---|---|---|
| **Autónomo** | 29 € | 319 € | Una persona que quiere dejar de llevar clientes, trabajos y cobros de memoria |
| **Negocio** | 49 € | 539 € | Equipos que necesitan coordinar el trabajo y tener la jornada y la gestoría conectadas |
| **Premium** | 99 € | 1.089 € | Negocios con uso intensivo y puesta en marcha acompañada |

## I.2 Qué incluye cada plan

| | Autónomo | Negocio | Premium |
|---|---|---|---|
| Agenda, clientes, trabajos y presupuestos | ✓ | ✓ | ✓ |
| Facturas con IVA e IRPF | ✓ | ✓ | ✓ |
| Cobros y recordatorios preparados | ✓ | ✓ | ✓ |
| WhatsApp con texto y documentos | ✓ | ✓ | ✓ |
| Documentos e impuestos trimestrales | ✓ | ✓ | ✓ |
| Exportación completa de los datos | ✓ | ✓ | ✓ |
| Modo consulta tras la baja (cláusula 16.2) | ✓ | ✓ | ✓ |
| Asignación de trabajos y planificación | — | ✓ | ✓ |
| Registro de jornada | — | ✓ | ✓ |
| Portal de gestoría y paquete trimestral | — | ✓ | ✓ |
| Proyectos, costes y rentabilidad | — | ✓ | ✓ |
| Personas usuarias incluidas | 1 | `[N]` | `[N]` |
| **Acciones avanzadas de IA / mes** | **75** | **300** | **1.500** |
| Soporte | Estándar | Prioritario | Línea directa |
| Puesta en marcha acompañada | — | — | ✓ |

## I.3 Qué es una acción avanzada de IA

Una **acción avanzada** es cada petición que exige interpretar, redactar o razonar en
profundidad: redactar un presupuesto a partir de una descripción libre, extraer los
datos de una factura fotografiada, resumir una conversación larga o transcribir una
nota de voz.

**No consumen acciones**: consultar la agenda, preguntar qué hay hoy, buscar un
documento, recibir un aviso de cobro, crear o editar registros a mano, emitir una
factura ya preparada, ni ninguna operación resuelta por las reglas locales del
Servicio.

**Al agotarse el cupo mensual** el Servicio sigue funcionando por completo: solo se
desactivan las funciones avanzadas hasta el reinicio del cupo, que se produce el
primer día de cada período de facturación. El cupo no se acumula de un mes al
siguiente. El Servicio avisa al llegar al 80 % y al 100 %, y ofrece subir de plan.
**Nunca se factura un exceso sin petición expresa del Cliente.**

## I.4 Límites de uso razonable

| Recurso | Límite | Qué pasa al superarlo |
|---|---|---|
| Almacenamiento de documentos | `[N]` GB por cuenta | Aviso y propuesta de ampliación; nada se borra |
| Tamaño por documento | `[N]` MB | Se rechaza la subida con mensaje explicativo |
| Mensajes de WhatsApp | Los que permita la línea del Cliente ante Meta | Lo fija Meta, no el Prestador |
| Minutos de recepcionista (beta) | 100 min/mes al activarse | Sin coste durante la beta |
| Personas usuarias adicionales | `[PRECIO]` €/usuario/mes | Se factura prorrateado |

▸ *Decisión abierta 9: los límites de almacenamiento y de usuarios adicionales están
sin fijar en el producto y en el modelo económico. Son los dos huecos de este anexo.
Fijarlos antes de firmar: un contrato con `[N]` es un contrato con un agujero.*

## I.5 Piloto y precio fundador

Si las Condiciones Particulares recogen un precio de piloto o un precio fundador, ese
precio se mantiene mientras la suscripción siga activa e ininterrumpida, y solo puede
revisarse conforme a la cláusula 13. Una baja seguida de una nueva alta se contrata al
precio de catálogo vigente.

---

# ANEXO II · Contrato de Encargado del Tratamiento

**Artículo 28 del Reglamento (UE) 2016/679 (RGPD) y Ley Orgánica 3/2018 (LOPDGDD).**

Este anexo tiene valor de contrato de encargo y prevalece sobre el resto del contrato
(cláusula 2.3). Sustituye, para el Cliente que lo firma, al contrato de encargado
publicado en la web.

## II.1 Partes y papeles

**Responsable del tratamiento**: el Cliente identificado en las Condiciones
Particulares.

**Encargado del tratamiento**: el Prestador.

El Cliente decide qué datos introduce, con qué finalidad y durante cuánto tiempo. El
Prestador los trata **únicamente siguiendo sus instrucciones documentadas**, que son:
este contrato, sus anexos, la configuración que el Cliente elige en la aplicación y
cualquier instrucción adicional que le curse por escrito.

Si una instrucción del Cliente infringe, a juicio del Prestador, el RGPD o la LOPDGDD,
el Prestador **se lo informará de inmediato** y podrá suspender su ejecución hasta que
se aclare (art. 28.3, párrafo segundo).

## II.2 Descripción del tratamiento

| | |
|---|---|
| **Objeto** | Prestación del Servicio descrito en la cláusula 4 |
| **Duración** | La del contrato, más los plazos de la cláusula II.9 |
| **Naturaleza y finalidad** | Alojamiento, organización, consulta, elaboración de documentos y comunicación de los datos para gestionar la actividad del Cliente |
| **Tipo de datos** | Identificativos y de contacto de los clientes, contactos y proveedores del Cliente (nombre, teléfono, dirección, correo, NIF); datos económicos de facturación y cobro; contenido de trabajos, comunicaciones y documentos. Si el Cliente usa funciones de equipo: datos identificativos y registros de jornada de sus personas trabajadoras |
| **Categorías de interesados** | Clientes, contactos, proveedores y personas trabajadoras del Cliente |
| **Operaciones** | Recogida, registro, conservación, consulta, uso, comunicación al propio destinatario (p. ej. enviar un presupuesto o una factura), bloqueo y supresión |

El Prestador **no trata categorías especiales de datos** del artículo 9 del RGPD de
forma intencionada. El Cliente se obliga a no introducirlas salvo que sea
imprescindible y disponga de base legal. Si el Cliente previera introducir datos de
salud, biométricos o de condenas, debe comunicarlo antes para evaluar si el Servicio es
adecuado.

## II.3 Subencargados

### Autorización general

El Cliente autoriza al Prestador a recurrir a los subencargados de la tabla siguiente,
que actúan bajo contrato escrito con obligaciones equivalentes a las de este anexo (art.
28.4 RGPD).

| Subencargado | Servicio | Datos que trata | Lugar de tratamiento | Garantía de transferencia |
|---|---|---|---|---|
| `[Proveedor de alojamiento]` | Alojamiento de la aplicación, base de datos y archivos | Todos los del Servicio | Región contratada en la UE | CCT (Decisión (UE) 2021/914) si procede |
| `[Proveedor de copias]` | Copia de seguridad externa | Copia completa, **cifrada en cliente** | Francia (UE) | No hay transferencia |
| `[Proveedor de correo]` | Correo transaccional | Correo, nombre y contenido del aviso | Francia (UE) | No hay transferencia |
| Meta Platforms | Mensajería de WhatsApp — **solo si el Cliente lo activa** | Teléfono y contenido de los mensajes | UE / EE. UU. | CCT y marco de adecuación |
| `[Proveedor de IA]` | Asistente avanzado — **solo si el Cliente lo activa** | Fragmento de texto no resuelto en local | `[país]` | CCT |
| `[Proveedor de transcripción]` | Notas de voz — **solo si el Cliente lo activa** | Audio y su transcripción | `[país]` | CCT |

**No son subencargados de este anexo** el proveedor de pagos, el proveedor de inicio de
sesión y el de calendario: tratan datos de la relación directa entre el Prestador y el
titular de la cuenta —en la que el Prestador es responsable— y **no reciben la cartera de
clientes ni el contenido operativo del Cliente**.

### Altas y bajas de subencargados

El Prestador comunicará al Cliente cualquier incorporación o sustitución de subencargado
con **treinta (30) días naturales de antelación** a que empiece a tratar datos, indicando
proveedor, servicio, lugar de tratamiento y garantía. El Cliente puede **oponerse por
motivos justificados** dentro de los quince (15) días siguientes. Si la oposición no puede
resolverse con una alternativa razonable, el Cliente puede resolver el contrato sin
penalización, con devolución de la parte proporcional no consumida.

▸ *Decisión abierta 10: esto responde a la pregunta 07 para el abogado. Treinta días es
un plazo cómodo para el cliente y exigente para una empresa pequeña: obliga a planificar
cada integración nueva con un mes de margen. La alternativa habitual es quince días.
Elegir uno y, sobre todo, cumplirlo: un plazo escrito y no respetado es peor que un plazo
holgado.*

### Transferencias internacionales

Toda transferencia fuera del Espacio Económico Europeo se ampara en las Cláusulas
Contractuales Tipo de la Decisión (UE) 2021/914 y, cuando proceda, en una decisión de
adecuación vigente. El Prestador aplica además: cifrado en tránsito siempre; cifrado en
cliente de las copias, con la clave fuera del proveedor; y minimización previa al envío,
de modo que a los proveedores de inteligencia artificial solo llegue el fragmento no
resuelto en local. El Prestador verifica periódicamente que la garantía invocada sigue
vigente y, si deja de estarlo, lo comunica al Cliente y suspende la transferencia
afectada.

## II.4 Acceso de la gestoría del Cliente

Cuando el Cliente habilita el acceso de su asesoría, esa habilitación constituye una
**instrucción documentada** de comunicar datos a un tercero designado por él. El
Prestador la ejecuta y la registra. La relación entre el Cliente y su asesoría, y el
contrato de encargo que en su caso deban suscribir entre ellos, son responsabilidad del
Cliente. El Prestador facilita el registro de accesos que lo acredita.

## II.5 Obligaciones del Prestador como encargado

El Prestador se obliga a:

**(a)** Tratar los datos únicamente según las instrucciones documentadas del Cliente,
incluidas las transferencias internacionales, salvo obligación legal que le imponga otra
cosa, en cuyo caso se lo informará antes de tratarlos salvo prohibición legal.

**(b)** Garantizar que las personas autorizadas a tratar los datos se han comprometido a
respetar la confidencialidad o están sujetas a un deber legal equivalente.

**(c)** Aplicar las medidas técnicas y organizativas del artículo 32 recogidas en II.6.

**(d)** No recurrir a otro subencargado sin respetar lo previsto en II.3.

**(e)** Asistir al Cliente, mediante medidas apropiadas, para atender las solicitudes de
ejercicio de derechos de los interesados (II.8).

**(f)** Asistir al Cliente en el cumplimiento de los artículos 32 a 36 del RGPD —
seguridad, notificación de brechas, evaluaciones de impacto y consulta previa— teniendo
en cuenta la naturaleza del tratamiento y la información de que disponga.

**(g)** Suprimir o devolver los datos al terminar la prestación, conforme a II.9.

**(h)** Poner a disposición del Cliente toda la información necesaria para demostrar el
cumplimiento del artículo 28 y permitir y contribuir a auditorías, conforme a II.10.

**(i)** No usar los datos para fines propios, no cederlos a terceros salvo obligación
legal y **no utilizarlos para entrenar modelos de inteligencia artificial** (cláusula
8.4).

**(j)** Llevar el registro de actividades de tratamiento realizadas por cuenta del
Cliente (art. 30.2 RGPD).

## II.6 Medidas de seguridad (art. 32)

| Ámbito | Medida |
|---|---|
| Autenticación | Contraseñas transformadas con función de derivación robusta y sal; segundo factor disponible; rotación de sesión tras el acceso; caducidad por inactividad |
| Aislamiento entre clientes | Toda operación y consulta exige el identificador del negocio; integridad garantizada además en la base de datos |
| Transporte | HTTPS obligatorio, TLS 1.2 o superior, HSTS y cabeceras defensivas |
| Control de acceso | Permisos por perfil, enlaces privados caducables, autorización de soporte limitada por motivo y tiempo |
| Defensa frente a abuso | Límites persistentes de intentos por IP y por cuenta, con claves seudonimizadas |
| Ficheros | Validación de la firma real del archivo, límites de tamaño y de recursos, rechazo de contenido activo y análisis antivirus |
| Integridad fiscal y laboral | Registros encadenados y no editables para facturación y jornada; detección de manipulación |
| Registro y trazabilidad | Bitácora de eventos de seguridad en modo solo añadir; registro estructurado que no incluye datos personales, credenciales ni cuerpos de petición |
| Copias y recuperación | Copias cifradas, copia externa independiente del proveedor principal, verificación periódica y procedimientos de restauración escritos |
| Desarrollo | Dependencias fijadas y auditadas, análisis estático y detección de secretos antes de cada publicación |

Estas medidas pueden evolucionar. **Ninguna modificación reducirá el nivel de seguridad
existente en la fecha del contrato.**

## II.7 Información a las personas trabajadoras del Cliente

Cuando el Cliente active el registro de jornada o dé acceso a su equipo, deberá informar
a cada persona trabajadora. El Prestador pone a su disposición un texto modelo que el
Cliente debe revisar, completar con sus datos y asumir como propio, con al menos: la
identidad del Cliente como responsable; la finalidad (cumplimiento del art. 34.9 del
Estatuto de los Trabajadores y organización del trabajo); la base jurídica (obligación
legal y ejecución del contrato de trabajo); el plazo de conservación (cuatro años); la
existencia del Prestador como encargado; y la forma de ejercer sus derechos ante el
Cliente.

## II.8 Derechos de los interesados

Si un interesado se dirige al Prestador para ejercer sus derechos, este **no responderá
por su cuenta**: le indicará que debe dirigirse al Cliente y se lo comunicará a este
**dentro de los tres (3) días hábiles** siguientes, sin más datos que los necesarios.

El Prestador asistirá al Cliente con las funciones del producto —búsqueda, exportación,
rectificación, supresión y bloqueo— para atender los derechos de acceso, rectificación,
supresión, oposición, limitación y portabilidad. Esta asistencia está incluida en el
precio; solo podrán facturarse los trabajos manuales extraordinarios, previamente
presupuestados y aceptados por escrito.

## II.9 Fin del tratamiento

Terminada la prestación, y **a elección del Cliente**, el Prestador devolverá o suprimirá
los datos personales tratados por su cuenta y las copias existentes.

- El Cliente puede exportar sus datos en cualquier momento (cláusula 16.1).
- Salvo instrucción distinta, la cuenta pasa al modo consulta de la cláusula 16.2.
- Si el Cliente pide la supresión, se ejecuta sobre los sistemas vivos de inmediato; los
  datos suprimidos permanecen en las copias de seguridad hasta que el ciclo las
  sobrescriba, bloqueados durante ese tiempo (cláusula 16.5).
- Lo que una obligación legal impide borrar queda **bloqueado** conforme a la cláusula
  16.4 y se suprime al vencer el plazo.
- El Prestador acreditará por escrito la devolución o la supresión a petición del Cliente.

## II.10 Auditoría

El Cliente puede verificar el cumplimiento de este anexo:

1. **Por información.** Solicitando, una vez al año, la documentación de cumplimiento del
   Prestador: registro de actividades, política de retención, procedimiento de brechas,
   lista de subencargados y evidencias de los controles de II.6. El Prestador responderá
   en treinta (30) días.
2. **Por auditoría.** Realizando, una vez al año y con treinta (30) días de preaviso, una
   auditoría por sí o por un tercero independiente sujeto a confidencialidad y que no sea
   competidor del Prestador. Se hará en horario laboral, sin interrumpir el servicio y
   sin acceder a datos de otros clientes. El coste es del Cliente, **salvo que la
   auditoría revele un incumplimiento relevante, en cuyo caso lo asume el Prestador**
   junto con la subsanación.
3. **Sin límite de frecuencia** tras una violación de seguridad que afecte al Cliente o a
   requerimiento de una autoridad de control.

## II.11 Violaciones de seguridad

El Prestador notificará al Cliente cualquier violación de la seguridad de los datos
personales **sin dilación indebida y, en todo caso, dentro de las veinticuatro (24) horas
siguientes** a tener constancia de ella. La primera comunicación puede ser preliminar; no
se retrasará por estar la investigación en curso.

La notificación incluirá, en la medida en que se conozca: naturaleza de la violación,
categorías y número aproximado de interesados y de registros afectados, consecuencias
probables, medidas adoptadas y punto de contacto. El Prestador completará la información
por fases y asistirá al Cliente en la notificación a la autoridad de control y, si
procede, a los interesados.

**La notificación a la autoridad de control corresponde al Cliente como responsable.** El
Prestador no notificará en su nombre salvo que el Cliente se lo pida por escrito.

## II.12 Responsabilidad

Cada parte responde del cumplimiento de las obligaciones que le corresponden como
responsable o como encargado conforme al RGPD y a la LOPDGDD. Esta cláusula se interpreta
junto con la cláusula 21, con la salvedad expresa de que **los límites de responsabilidad
no se aplican a la responsabilidad frente a los interesados del artículo 82 del RGPD**.

## II.13 Delegado de protección de datos

El contacto en materia de protección de datos del Prestador figura en las Condiciones
Particulares. `[Si se designa Delegado de Protección de Datos, indicar aquí su identidad
y su comunicación a la AEPD.]`

---

# ANEXO III · Mandato de expedición de facturas por cuenta del Cliente

*Este anexo se firma junto con las Condiciones Particulares.*

## III.1 Mandato

El Cliente, en su condición de empresario o profesional obligado a expedir factura,
**encarga al Prestador el cumplimiento material de esa obligación** al amparo del
artículo 5.1 del RD 1619/2012, de 30 de noviembre, por el que se aprueba el Reglamento
por el que se regulan las obligaciones de facturación.

El mandato se refiere exclusivamente a la **expedición material** de facturas, facturas
simplificadas y facturas rectificativas correspondientes a las operaciones que el propio
Cliente registre y confirme en el Servicio.

## III.2 Lo que el mandato no incluye

El mandato **no** comprende: calificar fiscalmente las operaciones; decidir tipos,
exenciones o retenciones; presentar declaraciones o comunicaciones tributarias; llevar
los libros registro con valor fiscal; ni representar al Cliente ante la Administración.

## III.3 Responsabilidad

Conforme al artículo 5.1 del RD 1619/2012, **el Cliente sigue siendo el único
responsable** del cumplimiento de todas las obligaciones de facturación: contenido,
numeración, plazo de expedición, remisión y conservación.

Ninguna factura se expide sin la **confirmación previa del Cliente** o de la persona que
él autorice, conforme a la cláusula 5. Esa confirmación queda registrada con su autor y
su fecha.

## III.4 Series, numeración y rectificación

El Servicio asigna numeración correlativa por serie y por ejercicio, con series separadas
para facturas completas, simplificadas y rectificativas. Emitida una factura, su cabecera
y sus líneas quedan congeladas. Cualquier corrección se realiza mediante factura
rectificativa conforme al artículo 15 del RD 1619/2012.

## III.5 Conservación

El Servicio conserva las facturas expedidas y sus registros y permite su exportación en
cualquier momento en formato legible y reutilizable. **La obligación de conservación de
los artículos 19 a 23 del RD 1619/2012 sigue correspondiendo al Cliente**, que se obliga a
descargar y custodiar sus facturas por sus propios medios, además de lo que conserve el
Servicio.

## III.6 Duración y revocación

El mandato dura lo que dure el contrato y **el Cliente puede revocarlo en cualquier
momento** por escrito. La revocación no afecta a las facturas ya expedidas ni a la
obligación de conservación. Terminado el contrato, el Cliente dispone de la exportación
completa de sus facturas conforme a la cláusula 16.1.

## III.7 Firmas

| Por el Prestador | Por el Cliente |
|---|---|
| Nombre y DNI: | Nombre y DNI: |
| Fecha: | Fecha: |

▸ *Decisión abierta 11: la pregunta 08 para el abogado. El artículo 5 del RD 1619/2012
exige acuerdo previo escrito para la expedición **por el destinatario** (autofacturación);
para la expedición **por un tercero** no lo exige expresamente, salvo que el tercero no
esté establecido en la Unión Europea, en cuyo caso hace falta autorización previa de la
AEAT. Este anexo se firma igualmente porque documenta el encargo, delimita lo que no
incluye y deja escrito quién responde: es barato y cierra una discusión antes de que
ocurra. Confirmar con la asesoría fiscal si además debe comunicarse algo a la AEAT y si
el texto le sirve tal cual.*

---

# ANEXO IV · Nivel de servicio y soporte

## IV.1 Disponibilidad

El Prestador fija como **objetivo de disponibilidad mensual el 99,5 %**, medido sobre el
acceso a la aplicación y excluyendo: el mantenimiento programado avisado conforme a la
cláusula 17.2, la fuerza mayor, las caídas de proveedores externos y el uso contrario al
Anexo V.

▸ *Decisión abierta 12: hoy esto es un **objetivo**, no una garantía con penalización, y
así está redactado a propósito: los documentos internos de continuidad dicen que el
simulacro completo de restauración no se ha ejecutado nunca. Prometer un SLA con créditos
antes de haberlo medido es firmar una obligación cuyo coste se desconoce. Cuando el
simulacro esté hecho y cronometrado, la redacción recomendada es: «si la disponibilidad
mensual cae por debajo del 99,5 %, el Cliente tiene derecho, previa solicitud en los 30
días siguientes, a un crédito del 10 % de la cuota mensual; por debajo del 95 %, del
30 %». Créditos, no indemnizaciones: es lo estándar y lo que se puede sostener.*

## IV.2 Canales y horario de soporte

| | |
|---|---|
| Canales | WhatsApp, correo electrónico y formulario dentro de la aplicación |
| Horario | De lunes a viernes laborables, de `[9:00 a 18:00]`, hora peninsular española |
| Idioma | Castellano y catalán |

## IV.3 Tiempos de respuesta

Tiempo hasta la **primera respuesta útil de una persona**, dentro del horario de soporte.
No es un compromiso de resolución.

| Gravedad | Qué es | Autónomo | Negocio | Premium |
|---|---|---|---|---|
| **1 · Crítica** | El Servicio no está disponible, o hay riesgo para los datos o para una obligación fiscal o laboral con plazo | 8 h | 4 h | 2 h |
| **2 · Alta** | Una función esencial no funciona y no hay forma de rodearla | 1 día hábil | 8 h | 4 h |
| **3 · Normal** | Fallo con alternativa disponible | 2 días hábiles | 1 día hábil | 8 h |
| **4 · Consulta** | Dudas, configuración, sugerencias | 3 días hábiles | 2 días hábiles | 1 día hábil |

Una incidencia de gravedad 1 se atiende siempre, aunque se comunique fuera del horario de
soporte, en cuanto el Prestador tenga constancia.

## IV.4 Continuidad: objetivos internos

| Escenario | Objetivo de punto de recuperación (RPO) | Objetivo de tiempo de recuperación (RTO) |
|---|---|---|
| Borrado accidental de un registro | 0 | Minutos |
| Corrupción de datos | ≤ 24 h | ≤ 2 h |
| Incidente de seguridad grave | ≤ 24 h | ≤ 8 h |
| Pérdida total del proveedor de alojamiento | ≤ 24 h | ≤ 8 h |

**Son objetivos internos de trabajo, no garantías contractuales**, y así se declaran
expresamente (cláusula 17.3). Pasarán a ser compromisos el día en que el simulacro de
restauración se ejecute, se cronometre y su resultado se documente.

## IV.5 Puesta en marcha

En el plan Premium, y en los demás cuando así se pacte en las Condiciones Particulares, el
Prestador acompaña la puesta en marcha: configuración inicial, importación de la cartera
de clientes si el Cliente la aporta en formato legible, conexión de la línea de WhatsApp y
una sesión de formación.

---

# ANEXO V · Política de uso aceptable

## V.1 Está prohibido

1. Usar el Servicio para una actividad ilícita, o para documentar operaciones
   inexistentes o falseadas.
2. Emitir facturas que no correspondan a operaciones reales del Cliente, o hacerlo en
   nombre de un tercero sin su mandato.
3. Falsear el registro de jornada, o registrarlo por una persona distinta de la que
   trabaja.
4. Enviar comunicaciones comerciales no solicitadas, cadenas de mensajes o contenido a
   destinatarios que no tengan relación con la actividad del Cliente.
5. Introducir datos personales sin base jurídica, o categorías especiales del artículo 9
   del RGPD sin cumplir la cláusula 10.4.
6. Intentar acceder a datos de otros clientes, sortear los controles de acceso, probar la
   seguridad del Servicio sin autorización escrita previa, o extraer datos de forma masiva
   y automatizada al margen de la exportación prevista.
7. Revender, sublicenciar o dar acceso al Servicio a terceros ajenos al negocio del
   Cliente, salvo el acceso de la gestoría y de los portales de cliente final previstos en
   el contrato.
8. Descompilar, aplicar ingeniería inversa o intentar obtener el código fuente, salvo en
   lo permitido imperativamente por la ley.
9. Cargar programas maliciosos, o archivos diseñados para agotar los recursos del
   Servicio.
10. Sobrecargar la infraestructura con un volumen desproporcionado respecto de la
    actividad del Cliente.

## V.2 Qué ocurre si se incumple

| Situación | Reacción del Prestador |
|---|---|
| Uso excesivo de recursos sin mala fe | Aviso y propuesta de ajuste del plan |
| Incumplimiento subsanable | Requerimiento y quince (15) días para corregir |
| Riesgo inmediato para la seguridad, la legalidad o el servicio a terceros | Suspensión inmediata de la función afectada, con comunicación motivada simultánea y restablecimiento en cuanto cese el riesgo |
| Incumplimiento grave no subsanado | Resolución conforme a la cláusula 15.4 |

Toda suspensión será la **mínima necesaria**: se suspende la función afectada, no la
cuenta entera, y **nunca el acceso de consulta y exportación** del Contenido del Cliente.

---

# ANEXO VI · Consentimientos separados y revocables

Cada consentimiento de este anexo es **voluntario, independiente y revocable** desde
Ajustes o escribiendo al contacto del Prestador. La revocación surte efecto de inmediato
hacia el futuro, no afecta a la licitud del tratamiento anterior y **no degrada el resto
del Servicio**.

| N.º | Consentimiento | Qué implica exactamente | Si se revoca |
|---|---|---|---|
| 1 | **WhatsApp Business** | La línea del Cliente se conecta a la API de Meta. El teléfono y el contenido de los mensajes se tratan por Meta Platforms conforme a sus condiciones. | Se desconecta el canal. El historial conservado sigue accesible. |
| 2 | **IA externa** | El fragmento de texto que el sistema no resuelve en local se envía a `[proveedor]`, con tratamiento en `[país]` y garantía `[CCT / adecuación]`. Nunca se envían la base de datos, la cartera de clientes ni documentos completos. | El asistente sigue funcionando solo con el motor local. |
| 3 | **Transcripción de voz** | Los audios enviados al asistente se transcriben mediante `[proveedor]`, con tratamiento en `[país]`. | Los audios dejan de transcribirse automáticamente. |
| 4 | **Acceso de gestoría** | La asesoría designada accede en solo lectura a los períodos que el Cliente habilite. Todo acceso queda registrado. | Se revoca el acceso de inmediato. |
| 5 | **Registro de jornada** | Se activa el fichaje para el equipo del Cliente, con las obligaciones de la cláusula 7. | Se desactiva el fichaje. Los registros dentro del plazo legal se conservan bloqueados. |
| 6 | **Funciones en beta** | Acceso anticipado a funciones en pruebas, sin nivel de servicio y sin coste mientras dure la beta. | Se retira el acceso anticipado. |
| 7 | **Comunicaciones comerciales** | Novedades de producto por correo electrónico. No incluye los avisos de servicio, seguridad y facturación, que son necesarios para la relación y no dependen de este consentimiento. | Se deja de enviar la comunicación comercial. |

El Servicio conserva, como prueba del artículo 7.1 del RGPD, la versión del texto
aceptado, la fecha, la hora y la cuenta que lo otorgó o lo revocó.

---

# Recapitulación de decisiones abiertas

| N.º | Dónde | Qué hay que decidir | Quién |
|---|---|---|---|
| 1 | Cl. 6.4 | Compromiso Veri\*Factu: ¿obligación de resultado con fecha, o de medios con salida reforzada? | Abogado + asesoría fiscal |
| 2 | Cl. 8.3 | Quién es responsable del despliegue de IA en los mensajes al cliente final (art. 50) | Abogado |
| 3 | Cl. 11.2 | Qué es la gestoría en protección de datos | Abogado |
| 4 | Cl. 16.2 | ¿Modo consulta para siempre, o mínimo de 12 meses con preaviso? | Founder |
| 5 | Cl. 21.4 | Tope de responsabilidad: 12 mensualidades, suelo de 500 €, o el límite del seguro | Abogado + founder |
| 6 | Cl. 22 | Seguro de RC profesional: contratarlo o eliminar la cláusula | Founder |
| 7 | Cl. 24.3 | ¿Basta el consentimiento anticipado para el paso a S.L.? | Abogado |
| 8 | Cl. 29.3 | Ciudad del fuero y tratamiento del cliente que pudiera ser consumidor | Abogado |
| 9 | Anexo I.4 | Límites de almacenamiento y precio del usuario adicional | Founder |
| 10 | Anexo II.3 | Plazo de preaviso de nuevo subencargado: 15 o 30 días | Founder |
| 11 | Anexo III | ¿Hace falta algo más ante la AEAT para expedir por cuenta del cliente? | Asesoría fiscal |
| 12 | Anexo IV.1 | Cuándo se convierte el objetivo de disponibilidad en SLA con créditos | Founder |

---

# Antes de que este contrato pueda firmarse

Cinco condiciones. No son burocracia: cada una es una afirmación que el contrato hace y
que hoy no se puede sostener.

1. **Identidad legal del Prestador.** Las Condiciones Particulares empiezan con cuatro
   campos que hoy están vacíos en producción (`NOESIS_LEGAL_NAME`, `NIF`, `ADDRESS`,
   `EMAIL`). El propio código bloquea el alta pública hasta que estén completos. Un
   contrato sin prestador identificado no es un contrato.

2. **Contratos firmados con los subencargados.** El Anexo II.3 afirma que los
   subencargados actúan «bajo contrato escrito con obligaciones equivalentes». A la fecha,
   la matriz interna de proveedores marca esos acuerdos como pendientes. Firmar el Anexo
   II antes que ellos es afirmar algo que no es cierto, con el agravante de que está por
   escrito.

3. **Revisión por abogado TIC.** Las doce decisiones abiertas, y en especial la 2, 3, 5 y
   7, necesitan criterio profesional. El encargo ya está preparado en
   [`Preguntas-abogado-TIC`](../Preguntas-abogado-TIC.md).

4. **Criterio de la asesoría fiscal sobre el Anexo III y la cláusula 6.4.** Es un encargo
   distinto del anterior y conviene pedirlo en paralelo.

5. **Coherencia con los textos publicados.** Este contrato y los textos de la web deben
   decir lo mismo. Si aquí el modo consulta dura doce meses y la web dice «no te cerramos
   la puerta», el cliente puede invocar lo que leyó primero. Cuando se cierre la decisión
   4, hay que tocar `site_precios.html` y `terminos.html` en el mismo movimiento.

---

## Control de versiones

| Versión | Fecha | Cambios |
|---|---|---|
| 1.0 | 18-sep-2026 | Primera redacción completa. Sin revisión jurídica externa. |

*La versión vigente y su fecha deben coincidir con `NOESIS_LEGAL_DOCUMENT_VERSION` y con
los textos publicados en la web.*
