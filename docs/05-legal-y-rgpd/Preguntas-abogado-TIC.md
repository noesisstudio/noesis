# Preguntas para el abogado TIC

> Preparación de la reunión de revisión jurídica. Actualizado el **15 de septiembre
> de 2026** contra el código y los textos publicados ese día. Versión para compartir:
> <https://claude.ai/code/artifact/436dff63-05c4-408a-9d63-bf3317a3096f>.
> No es asesoramiento jurídico: es material para que quien sí puede darlo cobre por
> revisar en vez de por averiguar.

Veintitrés preguntas, cada una con el contexto que hay que darle y cómo saber si la
respuesta sirve. Complementa el encargo redactado en
[`Ruta-legal`](Ruta-legal.html) (apartado 19) y los siete encargos de
[[RGPD-estado-y-plan]] (apartado 4): añade facturación por cuenta de terceros,
mensajes a clientes finales, registro de jornada, cookies de analítica, cambio a
S.L. y marca.

## Antes de entrar

Los textos legales ya están escritos y publicados: el encargo es **revisar**, no
redactar, y eso lo abarata.

**Qué llevar**

- Los textos publicados: aviso legal, privacidad, términos, cookies y contrato de
  encargado del tratamiento con su lista de subencargados.
- La guía `/cumplimiento` que publica la web.
- Los borradores internos de `cumplimiento/`: `RAT-Registro-actividades.md`,
  `Politica-de-retencion.md`, `Analisis-riesgos-y-EIPD.md`,
  `Procedimiento-brechas.md` y `Derechos-de-los-interesados.md`.
- Esta lista. Dile que la has preparado tú.

**La pregunta que vale por todas, al final:** «Decidme expresamente **qué no cubre**
vuestro informe.»

## Cómo explicar qué es Bynoesis (60 segundos)

> «Vendemos un programa de gestión a autónomos de servicios: fontaneros,
> electricistas, limpieza. Ellos lo usan por WhatsApp y por web.
>
> Hay tres capas de datos. **Primera:** los datos de nuestros clientes, los
> autónomos; ahí somos responsables. **Segunda:** los datos que ellos meten en el
> programa —sus clientes, trabajadores, facturas y documentos—; ahí creemos que somos
> encargados. **Tercera:** nuestro sistema compone y envía mensajes de WhatsApp a los
> clientes finales de nuestros clientes, con la identidad del autónomo.
>
> Además el programa emite facturas en nombre del autónomo, registra la jornada de
> sus trabajadores, transcribe notas de voz con un proveedor de EE. UU. y una
> gestoría externa puede ver sus períodos cerrados.
>
> Vendemos solo a profesionales. Todavía no cobramos a nadie.»

---

## A · Qué sois en protección de datos

**01. ¿Confirmáis que en los datos que nuestros clientes meten en la plataforma somos
encargados del tratamiento, y que nuestro contrato lo refleja bien?** *(clave)*
- Contexto: el contrato ya tiene subencargados con ubicación, cláusulas tipo,
  notificación de brechas, derechos y fin de contrato.
- Buena respuesta: señala **en qué tratamientos concretos** podríais ser responsables
  sin daros cuenta.

**02. Cuando una gestoría entra a ver los datos de nuestro cliente, ¿qué es:
subencargada nuestra, encargada del autónomo o cesionaria?** *(clave)*
- Contexto: la invita el autónomo; tiene cuenta profesional con doble factor, ve sus
  expedientes y descarga paquetes; no emite, no mueve dinero ni presenta impuestos.
- Buena respuesta: **quién firma qué con quién** y si hay que registrar la
  instrucción del autónomo.

**03. ¿Necesitamos delegado de protección de datos y evaluación de impacto?**
- Contexto: datos de terceros a escala, fiscales y de jornada laboral. Hay borrador de
  análisis de riesgos y EIPD sin validar.
- Buena respuesta: sí o no **razonado sobre los arts. 35 y 37**.

**04. ¿Nos validáis el registro de actividades en nuestros dos papeles?**
- Contexto: art. 30; hay borrador (`RAT-Registro-actividades.md`). Su ausencia es
  infracción por sí sola.
- Buena respuesta: lo entrega **archivado y firmado**, no como plantilla.

**05. Nuestros proveedores en EE. UU., ¿están cubiertos y cómo lo verificamos de
forma continuada?**
- Contexto: Anthropic (IA de respaldo), Meta (WhatsApp) y Groq (transcripción de
  notas de voz, elegido el 14-sep y pendiente de activar). La certificación en el
  marco de adecuación puede caerse sin avisar.
- Buena respuesta: un **procedimiento de revisión con periodicidad**.

## B · Textos que han cambiado

**06. Hemos retirado Veri\*Factu de la web pública, de `/cumplimiento` y de los
términos hasta que esté disponible. ¿Nos validáis la redacción actual y qué podremos
afirmar cuando se active?**
- Contexto: la versión anterior hablaba de un «sistema homologado», concepto que no
  existe; ya no aparece. Los textos antiguos están archivados en
  `Verifactu-textos-archivados.md`.
- Buena respuesta: **la redacción concreta** permitida hoy y la que exigirá el día que
  se active.

**07. Vamos a activar Groq para transcribir notas de voz. Nuestro contrato dice que
avisaremos de cambios de subencargados «con antelación razonable». ¿Qué plazo
concreto fijamos, y hay que avisar a los clientes antes de poner la clave?**
- Contexto: Groq aparece en la lista de subencargados en cuanto se configura; el DPA
  de Groq está pendiente de archivar. Hay alternativa local sin salida de datos.
- Buena respuesta: **plazo en días, canal de aviso** y base de la transferencia.

## C · Emitir facturas en nombre de otro

**08. Nuestro sistema expide facturas por cuenta del autónomo. ¿Es expedición por un
tercero, y hace falta un acuerdo previo documentado con cada cliente?** *(clave)*
- Contexto: el Reglamento de facturación regula la expedición por terceros. Hoy solo
  existe la aceptación de los términos.
- Buena respuesta: **cláusula en términos o mandato separado**, y qué debe decir.

**09. Si el programa calcula mal un IVA o una retención y el cliente presenta un
modelo con ese dato, ¿de quién es la responsabilidad ante la Agencia Tributaria?**
*(clave)*
- Contexto: el autónomo confirma todo lo irreversible y queda registrado.
- Buena respuesta: valora **si la confirmación humana os protege** y qué registrar
  para demostrarlo.

**10. ¿Hasta dónde podemos limitar nuestra responsabilidad en los términos, vendiendo
solo a profesionales?**
- Contexto: una limitación que un juez tumbe entera es peor que una moderada.
- Buena respuesta: **un tope concreto** y qué daños no se pueden excluir.

**11. ¿Nos recomendáis un seguro de responsabilidad civil profesional, y con qué
cobertura?**
- Contexto: hoy el titular publicado es Xavier Griñó como persona física, con NIF
  personal; está preparado el paso a S.L. Cambia la respuesta.
- Buena respuesta: **tipo de póliza** y un orden de magnitud.

## D · Mensajes a los clientes de vuestros clientes

**12. Un recordatorio de cobro o un aviso de cita por WhatsApp, ¿es comunicación
comercial (LSSI) o comunicación de servicio derivada de un contrato?** *(clave)*
- Contexto: plantillas de categoría «utilidad» en Meta, siempre ligadas a una factura,
  presupuesto o cita reales de ese destinatario.
- Buena respuesta: distingue por tipo de mensaje y dice **cuál necesitaría
  consentimiento previo**.

**13. ¿Quién garantiza la base jurídica para escribir a esa persona: el autónomo o
nosotros?** *(clave)*
- Contexto: el autónomo mete el teléfono; no verificáis su origen. Hay opt-out.
- Buena respuesta: **la cláusula** que fija esa obligación y qué hacer si sabéis que se
  incumple.

**14. El cliente final, ¿ante quién ejerce sus derechos y qué información tiene que
poder ver?**
- Contexto: portal privado por enlace para ver su factura o presupuesto sin registro.
- Buena respuesta: **qué debe decir el portal y el propio mensaje**.

## E · Registro de jornada

**15. ¿Cumple nuestro registro de jornada la normativa laboral, y qué falta para que un
cliente se apoye en él ante una inspección?** *(clave)*
- Contexto: cada registro va sellado y encadenado; se conserva y bloquea la baja
  dentro de plazo.
- Buena respuesta: **conservación, acceso para Inspección y trabajador**, y reformas en
  curso.

**16. ¿Qué hay que decirle al trabajador, y quién se lo dice?**
- Contexto: el trabajador es un dato del cliente y entra por un enlace propio.
- Buena respuesta: **el texto informativo** y de quién es la obligación.

## F · Inteligencia artificial

**17. ¿Nos aplica la transparencia del art. 50 del Reglamento de IA, o cabe la
excepción de que «resulta evidente por el contexto»?** *(clave)*
- Contexto: aplicable desde el 2-ago-2026. Comprobado el 15-sep: ni la web ni el
  primer mensaje de WhatsApp dicen que sea un sistema de IA. Arreglarlo son dos frases.
- Buena respuesta: **una redacción concreta** y la decisión por escrito.

**18. En los mensajes que el sistema compone con la identidad del autónomo, ¿quién es
responsable del despliegue a efectos del art. 50?** *(clave)*
- Contexto: el destinatario cree que le escribe su fontanero; el autónomo aprueba el
  envío, pero el texto lo compone una máquina.
- Buena respuesta: un **criterio prudente por escrito**.

**19. ¿Algo de lo que hacemos es de alto riesgo, o tenemos obligaciones como
proveedores además de la transparencia?**
- Contexto: propone acciones económicas y fiscales, nunca las ejecuta sin
  confirmación; no puntúa personas.
- Buena respuesta: razona **contra los anexos del Reglamento**.

## G · Conservar, borrar y cookies

**20. ¿Nos validáis la tabla de plazos de conservación, incluido qué hacer cuando
alguien pide borrar datos que una obligación fiscal o laboral obliga a guardar?**
- Contexto: con facturas emitidas o jornada en plazo, la baja conserva bloqueado. La
  purga automática está parada hasta validar `Politica-de-retencion.md`.
- Buena respuesta: **plazo por plazo con su fundamento legal**.

**21. Hemos añadido Google Analytics con aviso de cookies. ¿Cumple el aviso tal como
está?**
- Contexto: Aceptar y Rechazar con el mismo peso; Analytics solo se carga tras aceptar
  y sin señales publicitarias; la decisión se guarda 12 meses y se revoca desde el pie
  y `/cookies`. El aviso dice «analítica propia y de terceros» sin nombrar a Google
  (sí lo hace `/cookies`). El contador propio no usa cookies ni guarda IP.
- Buena respuesta: si **hay que nombrar a Google en el aviso**, si el plazo de 12
  meses vale y confirmación de que el contador propio queda fuera.

## H · Identidad legal y marca

**22. Vamos a pasar de autónomo a S.L. ¿Qué hay que rehacer en textos, contrato de
encargado y aceptaciones ya registradas?** *(clave)*
- Contexto: el aviso legal publica nombre y NIF personal; términos y contrato se
  aceptan hoy frente a una persona física. El cambio de titular está preparado en la
  configuración, sin activar.
- Buena respuesta: **lista de documentos a reemitir**, si hace falta nueva aceptación y
  qué hacer con el NIF personal publicado.

**23. ¿Registramos «Bynoesis» en la OEPM, y hay riesgo de conflicto con las empresas de
software «Noesis» que operan en España?**
- Contexto: Noesis Technologies SL (Madrid, desde 2009) y la consultora Noesis del
  Grupo Altia. Desde el 10-sep la web usa solo «Bynoesis».
- Buena respuesta: **clases concretas** (software y servicios en la nube) y una
  valoración del riesgo, o la derivación a un agente de marcas.

## I · Vender con comerciales a comisión

**24. Vamos a pagar comisión a comerciales autónomos que nos traigan clientes. ¿Es un
contrato de agencia, y pueden reclamarnos indemnización por clientela al terminarlo?**
*(clave)*
- Contexto: propuesta todavía sin firmar, en
  [[Canal-comercial-y-comisiones]]: una mensualidad al alta más un 10 % durante doce
  meses, con devolución si la cuenta se da de baja antes del cuarto mes. Se liquida
  contra factura del comercial y solo sobre lo cobrado. También habrá gestorías que
  traigan carteras enteras de autónomos.
- Buena respuesta: **qué hace que un acuerdo se califique como agencia en la práctica**,
  con independencia del título del contrato; si cabe redactarlo como mediación mercantil
  sin ese efecto; y qué orden de magnitud tendría la indemnización por clientela de la
  Ley 12/1992 con estas cifras.

## J · Buscar clientes nosotros

**25. Para captar autónomos, ¿podemos llamar por teléfono al número que ellos mismos
publican como contacto profesional, y guardarlo en nuestro CRM?** *(clave)*
- Contexto: lista propia de oficios de Lleida y el Segrià, sacada de fichas públicas
  (mapas, directorios de gremios) y de presentaciones de terceros. Guardamos nombre,
  teléfono, oficio, población y el origen del dato en `sales_prospects`
  (`/admin/crm`), con fecha del aviso del art. 14 y baja anotada.
- Nuestra lectura, a confirmar: art. 19 LOPDGDD (datos de contacto de empresarios
  individuales) más interés legítimo del art. 6.1.f RGPD, informando en el primer
  contacto y con baja inmediata.
- Buena respuesta: **si esa base aguanta**, qué hay que decir literalmente en la
  primera llamada, y **cuánto tiempo** podemos conservar a quien nunca llegó a ser
  cliente.

**26. El artículo 21 de la LSSI, ¿nos cierra el WhatsApp y el correo para el primer
contacto comercial, aunque el destinatario sea una empresa?**
- Contexto: el primer contacto lo hacemos por teléfono o en persona a propósito. La
  duda es si una respuesta suya por WhatsApp basta como consentimiento para seguir
  por ahí, y si la relación de piloto gratuito cuenta como «relación contractual
  previa» para escribirle después.
- Buena respuesta: **dónde está la línea** entre responder a quien te escribe y
  enviar comunicación comercial, por escrito y con un ejemplo de cada.

**27. ¿Qué información hay que darle a alguien cuyo teléfono hemos sacado de una
ficha pública, y cuándo?**
- Contexto: art. 14 RGPD. Hoy lo decimos en la primera frase de la llamada y el CRM
  marca la ficha hasta que está hecho; no mandamos nada por escrito.
- Buena respuesta: **si la información oral basta** o hace falta un enlace a la
  política de privacidad, y qué registro hay que poder enseñar si lo reclaman.

---

## Lo administrativo, antes de despedirte

- Honorarios cerrados y plazo de entrega comprometido.
- Si el precio incluye **aplicar** las correcciones o solo señalarlas.
- Qué pasa cuando cambie la normativa: revisión anual o pago completo.
- **Qué no cubre el informe.**

## Con qué tienes que irte

- [ ] Presupuesto cerrado, con plazo y alcance escrito.
- [ ] Criterio por escrito sobre **quién responde** si el programa calcula mal un impuesto.
- [ ] Redacción concreta para avisar de que es IA, en la web y en WhatsApp.
- [ ] Respuesta sobre **mandato separado** para facturar en nombre del cliente.
- [ ] Quién garantiza la base jurídica de los mensajes al cliente final.
- [ ] **Plazo concreto** para avisar de un nuevo subencargado antes de activar Groq.
- [ ] Lista de lo que hay que rehacer al pasar a **S.L.**
- [ ] Criterio sobre si el acuerdo con comerciales es **contrato de agencia**, y con qué
  redacción se evita la indemnización por clientela.
- [ ] Registro de actividades **archivado**, no como plantilla.
- [ ] La lista de lo que el informe **no** cubre.

> **Lo que este abogado no resuelve:** la conformidad Veri\*Factu y la declaración
> responsable son de la **asesoría fiscal**. Son dos encargos distintos; pídelos en
> paralelo. Preguntas fiscales:
> <https://claude.ai/code/artifact/a4f510c6-939f-421c-ba5c-c2fa7f487fba>.
