# RGPD: QUÉ TENGO QUE HACER

> **AVISO.** No es asesoramiento jurídico. Es la lista de acciones que salen de las
> dos auditorías: [[RGPD-estado-y-plan]] (código y textos publicados) y
> [[Servidores-y-residencia-de-datos]] (dónde viven los datos). Para las obligaciones
> y las tres rutas completas, [`Ruta-legal.pdf`](Ruta-legal.pdf); para el calendario,
> [`Plan-60-dias.pdf`](../06-negocio-y-finanzas/Plan-60-dias.pdf). Aquí no se explica el
> porqué: se explica **qué hacer, quién lo hace y cómo saber que está cerrado**.
> Fecha: **3 de septiembre de 2026**.

## CÓMO USAR ESTE DOCUMENTO

Cuatro bloques, en orden estricto. **No saltes bloques.** El bloque 0 es de hoy y lo
haces tú solo. El bloque 1 es lo que impide cobrar al primer cliente. El bloque 2 es
lo que encargas fuera. El bloque 3 no bloquea nada todavía.

**Regla:** nada de esto necesita esperar a la constitución de la sociedad, salvo
donde se diga expresamente.

---

## RESUMEN EN UNA PANTALLA

| Bloque | Cuántas cosas | Quién | Cuándo | ¿Bloquea? |
|---|---|---|---|---|
| **0 · HOY** | 4 | Tú, en el panel de Railway | Hoy, 1 hora | Una de ellas se encarece cada día |
| **1 · ANTES DE COBRAR** | 7 | Producto (Claude/Codex) + tú | Semanas 2-4 | **Sí: bloquea el primer euro** |
| **2 · ENCARGO EXTERNO** | 7 | Abogado de protección de datos | Al tener NIF | Sí, dos de ellos |
| **3 · ANTES DE ESCALAR** | 8 | Mixto | Tras el piloto | No |

---

# BLOQUE 0 · HOY, TÚ SOLO, EN UNA HORA

Nada de esto depende de nadie. Detalle en [[Servidores-y-residencia-de-datos]].

## 0.1 · FIRMAR EL CONTRATO DE ENCARGADO DE RAILWAY

- [ ] Entrar en `railway.com/legal/dpa` y firmarlo. Es autoservicio: existe, pero no
      se aplica solo.
- [ ] Guardar el PDF firmado en una carpeta «RGPD» junto al resto de papeles.

**Por qué importa:** sin él tienes un encargado del tratamiento procesando datos
personales **sin contrato del art. 28**, y el incumplimiento es tuyo, no de Railway.
Es el primer papel que pide una gestoría.

**Tiempo: 10 minutos.**

## 0.2 · COMPROBAR DÓNDE ESTÁN LOS DATOS

- [ ] Panel de Railway → servicio **web** → Settings → Scale → Regions. Anotar.
- [ ] Repetir con el servicio **Postgres**. Anotar.

`railway.json` no fija ninguna región, así que se usa la preferida de tu cuenta, que
por defecto es estadounidense. Si aparece `us-west2` o `us-east4`, la base de datos y
los papeles escaneados están en California o Virginia.

**Tiempo: 5 minutos.**

## 0.3 · MOVER A ÁMSTERDAM — ESTA ES LA URGENTE

- [ ] Si el paso 0.2 dio una región fuera de la UE, cambiar ambos servicios a
      `europe-west4-drams3a`.
- [ ] Comprobar después que `/health` y `/ready` responden y que el volumen sigue
      montado con los documentos dentro.

**Por qué hoy y no después:** cambiar de región con un volumen montado obliga a
migrarlo y **causa una parada** proporcional a su tamaño. Hoy el volumen está
prácticamente vacío y no hay clientes. Con tres pilotos dentro, la misma operación es
una ventana de mantenimiento negociada con gente que está trabajando. **Es la única
tarea de esta lista que se encarece sola con el tiempo.**

**Tiempo: 30 minutos, casi todo esperando.**

## 0.4 · ARREGLAR LA REGIÓN DE LAS COPIAS DE SEGURIDAD

- [ ] Fijar `NOESIS_BACKUP_S3_REGION` en producción a una región europea
      (`eu-west-1`, `eu-central-1` o la equivalente del proveedor).
- [ ] Confirmar que `NOESIS_BACKUP_DIR` apunta al volumen persistente y no a una
      carpeta junto a la base de datos.
- [ ] Decidir si quieres que cambie el valor por defecto en `config.py:476`, que hoy
      es `us-east-1`.

**Por qué importa:** si se activa la copia externa sin esa variable, la base de datos
completa se replica a Virginia. Las copias son el peor sitio para equivocarse: son
las que más tiempo viven y **sobreviven a los borrados**. Un cliente ejerce su derecho
de supresión, lo borras bien de la base… y sigue entero en un bucket estadounidense.

**Tiempo: 10 minutos.**

---

# BLOQUE 1 · ANTES DEL PRIMER CLIENTE DE PAGO

Siete cosas. La 1.0 es la única que puede convertirse en incumplimiento sin que
nadie toque un texto. Las tres siguientes son **afirmaciones publicadas que hoy no
son ciertas**, y eso es peor que una carencia. Detalle en [[RGPD-estado-y-plan]].

## 1.0 · DECIDIR QUÉ PASA CON GROQ — LA MÁS URGENTE DEL BLOQUE

- [x] Se ha elegido **declararlo**: Groq aparece de forma condicional en privacidad,
      contrato de encargado y matriz de proveedores cuando existe `GROQ_API_KEY`.
      Falta archivar el DPA/condiciones antes de activar la variable en producción.
- [ ] Mientras no se hayan archivado contrato/DPA y garantías, **no configurar
      `GROQ_API_KEY` en producción**.

**Problema:** `adapters/transcription.py` envía audio a `api.groq.com`, en Estados
Unidos, y Groq no aparece en la lista de subencargados. Basta con que alguien ponga
la variable para estar mandando las notas de voz de los clientes de tus clientes a un
subencargado no declarado, sin base contractual y sin notificación.

**Por qué va antes que las demás:** las otras cinco son textos que hay que corregir.
Esta se convierte en un incumplimiento real en el segundo en que alguien active una
variable de entorno. Hallazgo de [`Ruta-legal.pdf`](Ruta-legal.pdf).

**Quién: tú decides, producto ejecuta. Tiempo: la decisión, minutos.**

## 1.1 · QUITAR EL IFRAME DE CAL.COM

- [x] Eliminar el `<iframe>` de `site_contacto.html` y dejar los enlaces a
      `cal.com/bynoesis` que ya están justo debajo.
- [x] Quitar también la excepción de la CSP en `server.py`, que hoy abre
      `frame-src` a `cal.com` y `app.cal.com` solo en `/contacto`. Si se borra el
      iframe pero se deja la excepción, queda un permiso abierto sin motivo.

**Problema:** el iframe manda la IP de cada visitante a un tercero antes de cualquier
consentimiento, mientras `cookies.html` afirma que *no intervienen empresas ajenas* y
que por eso no hace falta banner. No es un descuido que la CSP frene: `server.py`
abre `frame-src` a cal.com **a propósito** en esa ruta, con un comentario que dice
que es «el único contenido externo que se incrusta». El código lo sabe; el texto
legal dice lo contrario.

**Por qué así:** quitarlo elimina de golpe un subencargado, una transferencia
internacional y un banner de consentimiento entero. La alternativa —carga bajo clic
más banner— cuesta mucho más y no mejora nada.

**Quién: producto. Tiempo: 5 minutos. No necesita abogado.**

## 1.2 · COMPLETAR LA LISTA DE SUBENCARGADOS

- [x] Añadir a `privacidad.html` y `encargado-tratamiento.html`: **Stripe** (trata
      nombre, dirección, NIF e importes), **Google** (si se activa el acceso con
      Google), y el **proveedor de copias de seguridad**.
- [x] Quitar Cal.com de la carga de Bynoesis; el enlace externo y su rol sí se explican.
- [x] Llevar las variables de proveedor a la comprobación de `readiness.py`, junto a
      la identidad legal.

**Problema añadido:** hoy el proveedor de correo **solo se pinta si la variable está
configurada**. Si falta, los correos salen igual pero la tabla no lo dice: la lista
miente por omisión sin que nadie lo note. Por eso hace falta la comprobación
automática, no solo corregir el texto.

**Quién: producto. Tiempo: media jornada. No necesita abogado.**

## 1.3 · REESCRIBIR `/CUMPLIMIENTO`

- [x] Aplicar el criterio conservador: no presentarlo como definitivamente conforme
      hasta pruebas AEAT, documentación técnica y declaración responsable.
- [x] Reescribir el apartado 2 sin inventar una integración homologada externa.

**Problema:** la página dice que *«Bynoesis se integra con un sistema homologado cuando
lo conectas»*. No existe tal integración: Veri\*Factu es desarrollo propio. Es una
afirmación engañosa sobre cumplimiento, en la página titulada «Usar Bynoesis en regla».

**Quién: producto corregido; founder y asesor validan antes de activar AEAT.**

## 1.4 · DAR SALIDA AL DERECHO DE SUPRESIÓN

- [x] Escribir el procedimiento de «baja con conservación legal», registrar la
      solicitud, devolver referencia, encolar avisos y dar seguimiento interno.
- [x] Sustituir el mensaje de error por una confirmación y estado visibles en Ajustes.
- [ ] Validar con abogado la tabla exacta de qué se conserva, por qué y hasta cuándo.

**Problema:** el borrado de cuenta falla si hay facturas emitidas o registros de
jornada, y remite a «solicita una baja con conservación fiscal» — **un procedimiento
que no existe**. El cliente que ejerce su derecho se encuentra un error y ahí acaba.

**Depende de:** la tabla de plazos del encargo 2.4.

**Quién: producto escribe, abogado valida la tabla.**

## 1.5 · PURGAR LAS CUENTAS CANCELADAS

- [ ] Fijar el plazo (propuesta: 30 días de gracia tras la cancelación).
- [ ] Escribirlo en `privacidad.html`.
- [ ] Programar la purga de todo lo no sujeto a obligación legal sobre
      `scheduled_job_runs`, que ya existe.

**Problema:** la política promete conservar «mientras la cuenta esté activa», pero
solo se borra si el titular pulsa el botón. Una cuenta abandonada guarda los datos de
sus clientes **para siempre**.

**Depende de:** la tabla de plazos del encargo 2.4. Sin ella no se puede programar.

**Quién: producto, después del abogado.**

## 1.6 · CREAR EL REGISTRO DE ACTIVIDADES DEL TRATAMIENTO

- [x] Borrador vivo con tablas como **responsable** (datos de las cuentas) y como
      **encargado** (datos de los clientes de tus clientes).
- [x] Anotar en él la cadena de subencargados: Railway → Google Cloud → Cloudflare.
- [ ] Anotar, razonada, la decisión sobre delegado de protección de datos.

**Problema original:** es **obligatorio** (art. 30) y no existía. Ya hay un borrador
operativo basado en el sistema real; el abogado debe validarlo y dirección mantenerlo.

**Quién: abogado lo redacta (encargo 2.2), tú lo mantienes.**

---

# BLOQUE 2 · LO QUE LE ENCARGAS AL ABOGADO

Presupuesto: **300-800 €**. Encárgalo **el día que tengas NIF**, no cuando esté todo
lo demás: es lo que más tarda por depender de un tercero.

Entra con esta lista escrita. Siete encargos:

- [ ] **2.1** Revisar los cuatro textos publicados —privacidad, encargado del
      tratamiento, cookies y aviso legal— **y su coherencia entre sí**, con los
      puntos 1.1, 1.2 y 1.3 encima de la mesa.
- [ ] **2.2** Redactar el **registro de actividades** (art. 30), como responsable y
      como encargado.
- [ ] **2.3** Dictaminar si procede **evaluación de impacto** (art. 35) y, si
      procede, el guion. *(Datos económicos y fiscales de terceros, a escala, con
      tratamiento por IA: es probable que sí.)*
- [ ] **2.4** Fijar la **tabla de plazos de conservación** por tipo de dato: fiscal,
      mercantil, registro de jornada, documentos, conversaciones del asistente y
      logs. **Pide este primero: desbloquea 1.4 y 1.5.**
- [ ] **2.5** Definir el **rol de la gestoría**: ¿subencargada de Bynoesis, o
      responsable independiente a la que el cliente concede acceso? Decide quién
      responde si un despacho filtra un expediente.
- [ ] **2.6** Revisar la **limitación de responsabilidad** de los términos frente a
      un error de cálculo fiscal. Es el riesgo real del producto.
- [ ] **2.7** Confirmar la **base de cada transferencia internacional**, proveedor
      por proveedor: Railway, Anthropic, el proveedor de IA compatible, Meta, Stripe,
      Google y el de copias.

**Añade a la misma consulta, aunque no sea RGPD:** desde el 2 de agosto de 2026
aplican las obligaciones de transparencia del Reglamento de IA (art. 50) — dejar
claro que se interactúa con un sistema de IA. Bynoesis lo cumple de hecho; conviene una
línea explícita en los términos.

---

# BLOQUE 3 · ANTES DE ESCALAR, NO ANTES DE COBRAR

- [ ] **3.1** Ejecutar la evaluación de impacto si el encargo 2.3 dice que procede.
      Hacerla con tres clientes es un documento; con doscientos es una auditoría.
- [ ] **3.2** Decidir el **cifrado en reposo** de los documentos, que hoy se guardan
      en claro. La política de privacidad **no lo promete**, así que no miente. Mantén
      la decisión de [[Seguridad-operativa]]: se decide con evidencia del piloto. Pero
      ten la respuesta escrita, porque la gestoría lo va a preguntar.
- [ ] **3.3** Escribir el **rol de la gestoría** en el contrato, según 2.5.
- [ ] **3.4** Corregir el **procedimiento de brecha**: como encargado no evalúas,
      **notificas al cliente sin dilación indebida** (art. 33.2) y decide él sobre la
      Agencia. Añadir esa frase y un plazo interno propio de 24 horas.
- [ ] **3.5** Construir el **aviso de cambios**: `LEGAL_DOCUMENT_VERSION` está fija en
      el código y el contrato promete avisar de los cambios de subencargado «con
      antelación razonable», pero no hay nada que envíe ese aviso. Mínimo: evento más
      correo a las cuentas activas.
- [ ] **3.6** Implementar la **baja parcial** con anonimización: borrar agenda,
      documentos, conversaciones y memorias del asistente, y dejar solo el bloque
      fiscal congelado. Es la versión buena de 1.4.
- [ ] **3.7** Documentar la decisión sobre **delegado de protección de datos**.
- [ ] **3.8** Revisar la **residencia de las copias** una vez el piloto genere volumen
      real, y anotar la región en [[Despliegue]] para que no viva solo en un panel.

---

# QUIÉN HACE QUÉ

| Tarea | Tú | Producto | Abogado |
|---|---|---|---|
| 0.1 - 0.4 (servidores) | **Todo** | Solo 0.4 si cambias el código | — |
| 1.0 Groq | **Decides** | Ejecuta | — |
| 1.1 iframe Cal.com | — | **Sí** | — |
| 1.2 subencargados | — | **Sí** | Valida en 2.1 |
| 1.3 `/cumplimiento` | **Decides Veri\*Factu** | Escribe | Valida en 2.1 |
| 1.4 salida de supresión | — | Escribe | **Fija la tabla (2.4)** |
| 1.5 purga automática | Fijas el plazo | Programa | **Fija la tabla (2.4)** |
| 1.6 registro art. 30 | Lo mantienes | — | **Lo redacta (2.2)** |
| Bloque 3 | Decides | Implementa | Dictamina |

---

# CÓMO SÉ QUE ESTÁ CERRADO

No vale «lo hemos revisado». Estos son los criterios verificables:

1. El **PDF del contrato de Railway** está firmado y archivado.
1. Groq está **declarado en el contrato o retirado del código**; no hay una tercera
   opción con la variable configurada.
2. Los **dos servicios** de Railway dicen `europe-west4-drams3a`, y `/ready` responde.
3. `NOESIS_BACKUP_S3_REGION` está fijada a una región europea **en producción**.
4. La página de contacto **no carga ningún dominio externo**. Compruébalo abriendo la
   pestaña de red del navegador: solo debe aparecer `bynoesis.com`.
5. La tabla de subencargados **nombra a todos** los proveedores configurados, y
   `readiness.py` falla si falta alguno.
6. `/cumplimiento` **no menciona ningún sistema homologado de terceros**.
7. El mensaje de error de baja **lleva a un procedimiento que existe**.
8. Existe una **tarea programada** que purga cuentas canceladas, y su plazo coincide
   con el que dice la política de privacidad.
9. Existe el **registro de actividades**, en dos tablas, con fecha y firma.
10. Existe un **informe del abogado** que cubre los siete encargos del bloque 2.

**Los diez, antes de cobrarle a nadie.** Los tres primeros, esta semana.
