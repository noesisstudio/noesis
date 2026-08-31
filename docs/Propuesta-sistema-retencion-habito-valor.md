# Noesis — propuesta integral de hábito, confianza, valor y retención

> **Estado:** estrategia aprobada para su base de datos; el candidato del esquema 53
> implementa únicamente el Registro Interno de Valor, WUB y medición de confianza.
> Las experiencias de Habit/Trust/Value siguen pendientes de piloto y
> Confidence/Insight/Progress continúan aplazadas.
> **Fecha:** 31 de agosto de 2026.  
> **Alcance:** estrategia de producto, medición e implantación. Este documento no
> implica que las funcionalidades descritas estén ya activas en producción.

## 1. Resumen ejecutivo

Noesis no debe optimizarse para que el autónomo pase más tiempo dentro de una
aplicación. Debe conseguir exactamente lo contrario: que dedique cada vez menos
tiempo a administrar su negocio porque puede delegar ese trabajo con seguridad.

La retención no se construirá mediante puntos, rachas, notificaciones constantes o
dependencia artificial. Se construirá mediante cinco motores de producto:

1. **Habit Engine:** consigue que, cuando ocurre algo administrativo, el autónomo
   piense «se lo digo a Noesis».
2. **Trust Engine:** permite confiar progresivamente más trabajo a Noesis sin
   perder confirmación, trazabilidad ni control.
3. **Value Engine:** demuestra qué trabajo ha resuelto Noesis y qué resultados
   verificables ha ayudado a conseguir.
4. **Insight Engine:** transforma un histórico suficiente en patrones útiles que
   el propietario difícilmente detectaría por sí mismo.
5. **Progress Engine:** demuestra, con períodos comparables, cómo evoluciona el
   negocio y qué ha aportado Noesis a lo largo del tiempo.

La propuesta es construir ahora la base común, Habit, Trust y Value, y medirlos
mediante **WUB — Weekly Useful Business**. Insight y Progress deben quedar diseñados
desde el principio, pero no mostrarse hasta disponer de datos reales suficientes.
El Confidence System también se aplaza: observar repetición permitirá sugerir una
regla, pero nunca concederá autonomía de manera silenciosa.

La idea central es:

> El autónomo hace su trabajo. Noesis organiza, recuerda, prepara, ejecuta lo
> autorizado, controla, aprende y demuestra lo que ha resuelto.

---

## 2. Decisión que debe tomar dirección

### Aprobar ahora

- Los cinco motores como filosofía transversal de producto, no como módulos
  independientes.
- La construcción de un **Registro Interno de Valor** como fuente única y auditable.
- Habit, Trust y Value como prioridad inmediata.
- WUB Rate como indicador principal del piloto, acompañado de profundidad y
  guardarraíles.
- La separación formal entre **Useful Action** y **Useful Outcome**.
- La recopilación desde hoy de los datos que necesitarán Insight y Progress.
- La validación con 3-5 negocios antes de convertir las hipótesis en promesas.

### No aprobar todavía

- Un Delegation Score o Delegated Work Rate aparentemente exactos.
- Aumentar autonomía basándose únicamente en comportamiento repetido.
- Mostrar horas ahorradas antes de calibrar tiempos manuales reales.
- Atribuir dinero a Noesis sin una cadena causal verificable.
- Insights basados en pocas observaciones o datos incompletos.
- Comparaciones «antes/después» entre períodos no comparables.
- Gamificación, rachas, rankings o notificaciones destinadas a generar actividad.

---

## 3. Modelo operativo completo

```text
Ocurre algo en el negocio
        ↓
El usuario se lo dice a Noesis o Noesis lo detecta
        ↓
Noesis informa, propone, prepara o ejecuta según el permiso vigente
        ↓
El usuario confirma cuando corresponde
        ↓
La tarea se completa
        ↓
Se registra una Useful Action
        ↓
Puede producirse posteriormente una Useful Outcome
        ↓
Noesis demuestra el valor de forma comprensible
        ↓
La interacción aporta contexto y mejora la siguiente
        ↓
El hábito, la confianza y la delegación se refuerzan
```

Este ciclo debe aplicarse a agenda, clientes, presupuestos, documentos, facturas,
cobros, proyectos y equipo. WhatsApp sirve principalmente para **hacer**; el SaaS
sirve para **ver, entender, decidir y controlar**.

---

## 4. Fundación común: Registro Interno de Valor

Los cinco motores necesitan una única fuente de verdad que distinga actividad de
valor. Los eventos de producto actuales siguen siendo útiles como telemetría y
auditoría, pero no deben convertirse directamente en una métrica comercial.

### 4.1 Useful Action

Una **Useful Action** es trabajo administrativo real completado con intervención
material de Noesis.

Debe cumplir todos estos criterios:

- Tiene un resultado operativo concreto.
- Ha alcanzado un estado final válido.
- Pertenece a un único negocio y a un proceso principal.
- No es una visita, una consulta ni un mensaje sin ejecución.
- No es un borrador incompleto, una propuesta rechazada o un fallo.
- No es un duplicado ni un reintento técnico.
- Si posteriormente se corrige, revierte o invalida, conserva su historia y cambia
  de estado; no desaparece del registro.

Ejemplos válidos:

- Cliente creado o actualizado y confirmado.
- Trabajo agendado, reprogramado o cerrado.
- Presupuesto preparado y enviado después de confirmación.
- Documento clasificado y validado.
- Factura emitida.
- Recordatorio de cobro enviado con confirmación o regla autorizada.
- Coste de un trabajador revisado e incorporado al proyecto.
- Paquete documental preparado para la gestoría.

No cuentan:

- Abrir una pantalla.
- Consultar cuánto debe un cliente.
- Pedir información al asistente.
- Mostrar una propuesta que no se acepta.
- Crear un borrador que nunca se completa.
- Pulsar dos veces o repetir una llamada por un error de red.
- Realizar manualmente todo el proceso en un formulario sin aportación material de
  Noesis, si lo que se está midiendo es delegación.

### 4.2 Evitar la inflación de acciones

Un mismo objetivo administrativo no puede fragmentarse para inflar la métrica.
Crear, confirmar y enviar una factura no son tres Useful Actions independientes si
forman parte del mismo ciclo de emisión.

```text
Objetivo: emitir la factura 1042
Estado inicial: borrador
Estado terminal válido: emitida
Useful Action contabilizada: 1
```

Cada acción tendrá una clave de idempotencia formada a partir del negocio, familia
de acción, entidad y ciclo de vida. Los reintentos nunca incrementarán WUB.

### 4.3 Useful Outcome

Una **Useful Outcome** es un resultado posterior y verificable relacionado con una
o varias Useful Actions.

Ejemplos:

- Factura cobrada.
- Presupuesto aceptado.
- Cita confirmada.
- Trabajo pendiente convertido en factura.
- Documento aceptado por el titular o la gestoría.
- Cobro recibido después de un seguimiento.

La atribución se clasificará como:

- **Directa:** existe una relación causal clara y comprobable.
- **Asistida:** Noesis participó, pero no puede considerarse la única causa.
- **Observada:** el resultado ocurrió, pero no se atribuye a Noesis.

Solo las dos primeras podrán aparecer como impacto ayudado por Noesis. Una outcome
observada sirve para análisis, pero no para una afirmación comercial.

Ejemplo correcto:

> Una factura de 480 € se cobró después del recordatorio que confirmaste.

Ejemplo incorrecto:

> Noesis te ha hecho ganar 480 €.

### 4.4 Modelo de datos propuesto

`useful_actions` incluirá, como mínimo:

- `business_id`.
- Familia y versión de la acción.
- Proceso principal.
- Tipo e identificador de la entidad afectada.
- Canal: WhatsApp, web, correo o sistema.
- Forma de finalización: confirmada, asistida o regla autorizada.
- Estado: completada, corregida, revertida o invalidada.
- Fecha de finalización.
- Clave de idempotencia.
- Referencia auditable al evento operativo original.

`useful_outcomes` incluirá:

- Negocio y acción o acciones relacionadas.
- Tipo de resultado.
- Entidad afectada.
- Importe y moneda cuando corresponda.
- Método y versión de atribución.
- Tipo de atribución.
- Fecha del resultado.
- Clave antduplicados.

Las operaciones se filtran siempre por `business_id`. No se copiará texto privado
innecesario: el registro referenciará las entidades existentes y conservará solo
metadatos controlados.

Cuando sea posible, la operación de negocio y su Useful Action se guardarán en la
misma transacción. Una acción no se registra al pulsar un botón, sino cuando el
resultado se completa correctamente.

### 4.5 Matriz inicial de procesos

| Proceso | Useful Actions iniciales | Useful Outcomes relacionadas |
|---|---|---|
| Clientes | Alta o actualización confirmada a partir de información tratada por Noesis | Cliente reutilizado correctamente en un ciclo posterior |
| Agenda y trabajos | Crear, reprogramar o cerrar un trabajo | Cita confirmada; trabajo convertido en factura |
| Presupuestos | Preparar y enviar; realizar seguimiento confirmado | Presupuesto aceptado o reactivado |
| Documentos y gastos | Clasificar, validar y archivar | Documento aceptado; gasto incorporado al período correcto |
| Facturación | Emitir una factura válida | Trabajo pendiente finalmente facturado |
| Cobros | Enviar un seguimiento o conciliar con confirmación | Factura cobrada después de la intervención |
| Equipo y proyectos | Revisar e incorporar coste, documento o incidencia | Proyecto actualizado sin asociación incorrecta |

Cada acción tendrá un único proceso principal. Así se evita que una sola factura
cuente simultáneamente como cliente, trabajo, facturación y cobro.

---

## 5. Habit Engine

### 5.1 Objetivo

Crear la asociación mental:

> Situación administrativa → «Se lo digo a Noesis».

El objetivo no es aumentar sesiones en el dashboard. Es hacer que más situaciones
reales se resuelvan con menos esfuerzo mediante WhatsApp, audio, web o una regla
previamente autorizada.

### 5.2 Ciclo

**Trigger:** ocurre algo o Noesis detecta una necesidad.

> Ayer terminaste dos trabajos que todavía no están facturados.

**Action:** el usuario puede responder con muy poco esfuerzo.

> Sí, prepara las dos.

**Reward:** Noesis resuelve y comunica el resultado real.

> Hecho. Una factura está lista. En la segunda falta el NIF del cliente.

**Investment:** el sistema aprende contexto confirmado: cliente, servicio, precio,
IVA, forma de cobro y preferencias. La próxima interacción requiere menos esfuerzo.

### 5.3 Resumen diario

Debe responder solo a cuatro preguntas:

1. ¿Cómo está mi negocio hoy?
2. ¿Qué necesita mi atención?
3. ¿Qué ha dejado resuelto Noesis?
4. ¿Cuál es la siguiente acción útil?

Ejemplo:

> Buenos días, Marc. Hoy tienes tres trabajos. No hay nada urgente. Ayer Noesis
> ordenó dos documentos y dejó preparada una factura. Hay un presupuesto de
> 1.400 € que lleva seis días sin respuesta.

Acciones:

- Preparar seguimiento.
- Ver presupuesto.
- Dejarlo para después.

### 5.4 «Mientras estabas trabajando»

Al volver a la aplicación:

> Mientras estabas trabajando, Noesis registró un cobro, clasificó dos documentos
> y detectó una factura vencida.

Esta pieza comunica que Noesis aporta valor mientras el usuario está fuera, no solo
cuando abre el software.

### 5.5 Closing Loops

La página principal debe concentrarse en pendientes reales:

> Necesitan tu atención: 2 cosas.

Después de resolverlas:

> Todo bajo control.

La recompensa central es alivio mental, no entretenimiento.

### 5.6 Política de interrupciones

Noesis no notificará porque el cliente lleve tiempo sin entrar. Solo lo hará si hay:

- Un riesgo.
- Una oportunidad.
- Una decisión pendiente.
- Un resultado relevante.
- Una acción cuya utilidad depende del momento.

Cada notificación debe pagar el coste de haber interrumpido al usuario. Se medirán
acciones posteriores, descartes, silencios y desactivaciones para identificar ruido.

---

## 6. Trust Engine

### 6.1 Objetivo

Conseguir que el usuario pase progresivamente de usar Noesis a confiarle una parte
mayor de su administración, siempre con límites explícitos y reversibles.

### 6.2 Escalera de confianza

**Nivel 1 — Informa**

> Tienes tres facturas vencidas.

**Nivel 2 — Propone**

> ¿Quieres que prepare los recordatorios?

**Nivel 3 — Prepara y solicita confirmación**

> He preparado los tres mensajes. ¿Los envío?

**Nivel 4 — Ofrece una regla explícita**

> ¿Quieres crear una regla para enviar un recordatorio cuando una factura lleve
> más de diez días vencida?

**Nivel 5 — Ejecuta dentro de esa regla**

> He enviado dos recordatorios siguiendo la regla que autorizaste.

### 6.3 Guardarraíles permanentes

- Las acciones fiscales, económicas o irreversibles mantienen confirmación.
- Cada automatización puede consultarse, pausarse y revocarse.
- El usuario puede ver qué hizo Noesis, cuándo, por qué y bajo qué permiso.
- Las correcciones conservan el antes, el después y el motivo.
- Los estados preparado, enviado, aceptado y cobrado nunca se confunden.
- Una conducta repetida no se interpreta como permiso silencioso.
- Una integración caída degrada la función sin inventar un resultado.

### 6.4 Confidence System aplazado

Durante el piloto solo se recopilarán:

- Propuestas ofrecidas.
- Aceptaciones y rechazos.
- Correcciones y reversiones.
- Tiempo hasta la confirmación.
- Reglas creadas, pausadas o revocadas.

Cuando exista evidencia suficiente, Noesis podrá sugerir:

> Has confirmado ocho de los últimos nueve recordatorios similares. ¿Quieres crear
> una regla para estos casos?

El usuario deberá aceptarla expresamente. La evidencia sirve para proponer, nunca
para ampliar autonomía por sí sola.

---

## 7. Value Engine

### 7.1 Objetivo

El cliente no debería tener que recordar por qué paga Noesis. El producto debe
demostrar periódicamente:

- Qué ha gestionado.
- Qué ha terminado.
- Qué ha detectado.
- Qué problemas ha ayudado a evitar.
- Qué necesita todavía confirmación.
- Qué resultados verificables se han producido.

### 7.2 Primera versión: valor operativo

> Esta semana Noesis completó siete gestiones en facturación, documentos y cobros.

Esta versión puede construirse en cuanto el Registro Interno de Valor sea fiable.

### 7.3 Tiempo recuperado

No se mostrará al cliente hasta calibrarlo con usuarios reales. La metodología será
conservadora y transparente:

```text
Tiempo recuperado estimado
= tiempo manual calibrado de la acción
− tiempo que el usuario dedicó a delegarla y confirmarla
```

Se emplearán intervalos y una versión del modelo, no precisión falsa:

> Entre 3 h 30 min y 4 h 15 min de administración evitada.

También podrá traducirse de forma prudente:

> Aproximadamente media jornada que no has dedicado a oficina.

Noesis nunca afirmará que el usuario dedicó ese tiempo a su familia, descanso o
nuevos clientes si no puede saberlo.

### 7.4 Valor potencial del tiempo

Si el usuario indica voluntariamente el valor aproximado de su hora:

> Cuatro horas recuperadas. Valor potencial de ese tiempo: aproximadamente 140 €.

Se presentará como valor potencial del tiempo liberado, nunca como ingreso o
beneficio generado.

### 7.5 Impacto económico atribuible

Mensajes válidos:

> 840 € se cobraron después de recordatorios confirmados.

> Noesis detectó 1.200 € en trabajos terminados que todavía no estaban facturados.

> Dos presupuestos fueron aceptados después de sus seguimientos.

Mensajes no válidos:

> Noesis te ha hecho ganar 5.000 €.

> Noesis ha protegido 3.000 €, cuando solo existen facturas pendientes.

### 7.6 Momentos de Proof of Value

**Diario:** estado, atención necesaria y trabajo resuelto.

**Semanal:** procesos gestionados, resultados y pendientes cerrados.

**Mensual:** qué ocurrió, qué hizo Noesis, outcomes verificables, tiempo calibrado
y dos oportunidades para el mes siguiente.

**Acumulado:** se guardará desde el primer día, pero se presentará dentro de
Progress cuando el histórico sea fiable.

---

## 8. WUB — Weekly Useful Business

WUB no es un sexto motor. Es la métrica interna que comprueba si Habit, Trust y
Value están produciendo delegación útil recurrente.

### 8.1 Definición

Un negocio será WUB cuando, durante una ventana de siete días:

- Complete al menos tres Useful Actions.
- Esas acciones pertenezcan al menos a dos procesos diferentes.
- Todas sean acciones terminales, reales y no duplicadas.
- La cuenta no sea demo, interna o de pruebas.

Habrá dos lecturas:

- **WUB semanal oficial:** semana cerrada de lunes a domingo, reproducible para
  informes y cohortes.
- **WUB actual:** últimos siete días móviles, útil para operación interna.

### 8.2 WUB Rate

```text
WUB Rate
= negocios que cumplen WUB
÷ negocios elegibles durante toda la semana
× 100
```

Un negocio elegible:

- Ha completado el onboarding mínimo.
- Tiene prueba o suscripción con acceso operativo.
- No está suspendido.
- No es demo ni cuenta interna.
- Ha tenido acceso durante toda la ventana semanal.

Los nuevos negocios se medirán separadamente mediante:

- Tiempo hasta la primera Useful Action.
- Porcentaje con una Useful Action durante sus tres primeros días.
- Porcentaje que alcanza WUB durante sus primeros siete días completos.

### 8.3 Profundidad

No se creará todavía un Delegation Score. Se medirá una distribución observable:

- Negocios con un proceso útil semanal.
- Negocios con dos procesos.
- Negocios con tres procesos.
- Negocios con cuatro o más procesos.

### 8.4 Jerarquía de métricas

**Indicador principal del piloto**

- WUB Rate.

**Drivers**

- Tiempo hasta la primera Useful Action.
- Profundidad por procesos.
- Semanas consecutivas WUB.

**Resultados**

- Useful Outcome Rate.
- Retención D30 y D90.
- Renovación, cancelación y reactivación.

**Guardarraíles**

- Correcciones y reversiones.
- Duplicados detectados.
- Notificaciones ignoradas o silenciadas.
- Atribuciones económicas incorrectas.
- Incidencias de seguridad o aislamiento.
- Carga de soporte por negocio.

No se fijará todavía un objetivo comercial de WUB Rate. Primero se medirá una línea
base y se comprobará si WUB se relaciona con valor percibido y retención.

---

## 9. Insight Engine — segunda etapa

### 9.1 Cuándo activarlo

Cuando existan varias semanas o meses de datos completos y una muestra mínima
suficiente para cada cálculo. No se generarán insights a partir de observaciones
escasas o campos incompletos.

### 9.2 Qué debe descubrir

- Servicios con mayor margen.
- Clientes que tardan más en pagar.
- Presupuestos con mejor conversión.
- Días o franjas con huecos recurrentes.
- Concentración excesiva de facturación.
- Trabajos que suelen superar el presupuesto.
- Gastos recurrentes o anomalías justificables.

### 9.3 Contrato de presentación

Cada insight indicará:

- Qué se ha detectado.
- Qué datos y período se han utilizado.
- Tamaño de la muestra.
- Limitaciones o calidad de los datos.
- Una acción posible.

Ejemplo:

> Los trabajos de mantenimiento han tenido un margen aproximadamente un 18 %
> superior durante los últimos tres meses. Se han analizado 24 trabajos con costes
> completos.

La lógica numérica será determinista. Una IA podrá ayudar a explicar el resultado,
pero no a inventar el cálculo ni la conclusión.

---

## 10. Progress Engine — segunda etapa

### 10.1 Objetivo

Demostrar evolución, no solo estado actual.

Podrá mostrar, desde una fecha verificable:

- Acciones administrativas resueltas.
- Procesos delegados.
- Tiempo estimado recuperado.
- Facturas emitidas.
- Cobros posteriores a seguimientos.
- Trabajos sin facturar detectados.
- Presupuestos reactivados.

### 10.2 Before / After

Solo se compararán períodos completos y razonablemente equivalentes.

Ejemplo:

> Durante tus primeros tres meses, el tiempo medio de cobro fue de 26 días. Durante
> los últimos tres meses ha sido de 19 días.

La comparación deberá controlar o explicar:

- Estacionalidad.
- Cambios de volumen y cartera.
- Datos incompletos.
- Cambios de precios, sector o actividad.
- Diferencias en la duración de los períodos.

Si no existe un «antes» fiable, Noesis no lo inventará.

### 10.3 Goals Engine

Se integrará dentro de Progress, no como motor separado. El usuario podrá elegir un
objetivo:

- Cobrar antes.
- Facturar trabajos más rápido.
- Reducir administración.
- Tener más control.
- Mejorar margen.
- Reducir impagos.

Solo se mostrará progreso si Noesis dispone de una línea base y una métrica válida.

### 10.4 Momentos de victoria

Sin confeti ni recompensas infantiles:

- Primer ciclo completo: trabajo, factura y cobro.
- Primer mes sin facturas vencidas.
- Cien gestiones administrativas delegadas.
- Reducción verificable del tiempo entre terminar y facturar.

El resultado empresarial constituye la recompensa.

---

## 11. Cómo se verá en la realidad

### 11.1 Ciclo completo de ejemplo

1. El autónomo termina un trabajo.
2. Escribe: «Terminado lo de Carlos, 480 más IVA».
3. Noesis identifica cliente, trabajo y fiscalidad.
4. Prepara la factura.
5. El autónomo confirma.
6. La factura se emite: Useful Action de facturación.
7. Pasan diez días sin cobrarse.
8. Noesis propone un recordatorio.
9. El autónomo confirma.
10. Se envía: Useful Action de cobros.
11. Posteriormente se registra el pago.
12. Se crea una Useful Outcome de 580,80 €, con atribución asistida.
13. Si el negocio reúne tres acciones en dos procesos, se convierte internamente en
    WUB esa semana.
14. El cliente recibe:

> Esta semana Noesis completó cinco gestiones en facturación y cobros. La factura
> de Carlos se cobró después del seguimiento que confirmaste. Ahora mismo no tienes
> nada urgente pendiente.

El cliente no ve que «es WUB». Ve tranquilidad, trabajo resuelto y resultados.

### 11.2 Panel interno de dirección

La primera versión incluirá:

- Número de negocios WUB.
- WUB Rate.
- Profundidad de uno, dos, tres y cuatro o más procesos.
- Useful Actions por proceso.
- Useful Action → Useful Outcome.
- Tiempo hasta la primera acción útil.
- Correcciones y reversiones.
- Propuestas aceptadas y rechazadas.
- Reglas activadas y revocadas.
- Notificaciones silenciadas.
- Comparación futura de retención WUB frente a no WUB.

Dirección debe poder abrir cada agregado y explicar qué acciones lo forman. Si una
cifra no es auditable hasta su operación original, no está lista para decidir ni
para mostrarse al cliente.

### 11.3 Superficies para el cliente

**Inicio**

> Necesitan tu atención: 2 cosas.

o, cuando corresponda:

> Todo bajo control.

**Parte diario**

> Ayer Noesis dejó resueltas tres gestiones: ordenó dos documentos y preparó una
> factura. Necesitas revisar una cosa.

**Resumen semanal**

> Esta semana Noesis completó siete gestiones en tres áreas: documentos,
> facturación y cobros.

**Resultado verificable**

> Una factura de 480 € se cobró después del recordatorio que confirmaste.

**Resumen mensual posterior**

> Noesis gestionó 38 tareas y te evitó aproximadamente entre siete y ocho horas de
> administración. Dos cobros llegaron después de seguimientos confirmados.

---

## 12. Plan de implantación

Las duraciones son estimaciones de orden de magnitud para un escritor activo y se
revisarán tras cerrar la matriz de acciones. La secuencia es más importante que la
fecha.

| Fase | Trabajo | Resultado | Condición de salida |
|---|---|---|---|
| 0. Contrato de medición | Aprobar taxonomía, acciones, outcomes, atribución y WUB | Definiciones no ambiguas | Los socios pueden decidir qué cuenta sin consultar al programador |
| 1. Fundación | Registro Interno de Valor, idempotencia, aislamiento y auditoría | Fuente única de valor | Cada acción puede rastrearse hasta su operación |
| 2. Habit MVP | Triggers útiles, parte diario, «Mientras trabajabas» y Closing Loops | Menor esfuerzo y hábito de delegación | Las alertas provocan acciones útiles y no ruido |
| 3. Trust MVP | Propuestas, confirmación, reglas explícitas, historial y revocación | Delegación segura | Toda ejecución dispone de permiso y explicación |
| 4. Value MVP | Resumen semanal, acciones y outcomes verificables | Valor visible | No existen duplicados ni atribuciones dudosas |
| 5. WUB interno | Panel, WUB Rate, profundidad y guardarraíles | Medición operativa | Dirección puede explicar todos los agregados |
| 6. Piloto | 3-5 negocios durante 4-6 semanas | Evidencia de uso real | Se conoce la línea base y los errores habituales |
| 7. Value avanzado | Calibración de tiempo y resumen mensual | Valor emocional y económico prudente | Las estimaciones son defendibles y transparentes |
| 8. Insight | Patrones con muestra suficiente | Conocimiento acumulado | Cada insight tiene datos, límites y acción |
| 9. Progress | Evolución, objetivos y before/after | Mejora demostrable | Existen períodos comparables |
| 10. Confidence | Sugerencias de reglas basadas en evidencia | Mayor autonomía elegida | Siempre existe aceptación explícita y revocación |

### 12.1 Orden técnico recomendado

1. Añadir migración y tablas del registro de valor.
2. Crear un servicio central con taxonomía, deduplicación y atribución versionadas.
3. Instrumentar puntos terminales de clientes, trabajos, presupuestos, documentos,
   facturación y cobros.
4. Registrar outcomes desde pagos, aceptaciones y cambios de estado posteriores.
5. Construir consultas WUB y profundidad sin tabla de agregados al principio.
6. Añadir panel interno y herramientas de auditoría.
7. Incorporar Proof of Value en el resumen semanal.
8. Activar mensajes visibles solo después de validar datos internos.
9. Añadir agregados diarios o semanales únicamente cuando el volumen lo justifique.

### 12.2 Pruebas obligatorias

- Aislamiento entre negocios.
- Reintentos e idempotencia.
- Dobles clics y webhooks duplicados.
- Acciones fallidas, rechazadas y borradores que no deben contar.
- Ciclos de vida que no pueden fragmentarse para inflar valor.
- Corrección, reversión e invalidación.
- Límites de semana y zona horaria del negocio.
- Exclusión de cuentas demo, internas y suspendidas.
- Elegibilidad de pruebas, altas nuevas y suscripciones.
- Profundidad por procesos.
- Outcomes tardías y relaciones muchos-a-muchos.
- Importe económico contado una sola vez.
- Permisos del panel interno.
- Exportación, eliminación y obligaciones RGPD.
- Rendimiento en PostgreSQL.

---

## 13. Diseño del piloto y puertas de decisión

El umbral de tres acciones y dos procesos es una hipótesis inicial, no un objetivo
comercial demostrado.

Durante el piloto se revisará:

- Si WUB coincide con la percepción de valor del cliente.
- Si predice recurrencia y retención mejor que sesiones o páginas vistas.
- Si dos procesos representan profundidad real o un umbral demasiado sencillo.
- Qué acciones se perciben como valiosas y cuáles como ruido.
- Dónde aparecen más correcciones o reversiones.
- Cuántas notificaciones son ignoradas o desactivadas.
- Cuánto soporte necesita cada negocio para alcanzar la primera Useful Action.
- Qué resultados pueden atribuirse sin exageración.

Guardarraíles de calidad previos a cualquier comunicación comercial:

- Cero cruces entre negocios.
- Cero duplicados conocidos en WUB o importes.
- Cada agregado es explicable y auditable.
- Ningún dinero se atribuye sin outcome enlazada.
- Correcciones y reversiones son visibles, no ocultas.
- Las notificaciones tienen una razón operativa identificable.
- No se amplía autonomía sin permiso explícito.

Los objetivos de WUB Rate, retención o outcomes se definirán después de obtener una
línea base. Fijarlos antes produciría precisión falsa y podría incentivar acciones
fáciles pero poco valiosas.

---

## 14. Regla para nuevas funcionalidades

Antes de aprobar una función nueva se responderá:

1. **Trigger:** ¿qué situación real hace que el usuario la necesite?
2. **Action:** ¿puede resolverse con menos esfuerzo que manualmente?
3. **Reward:** ¿qué resultado obtiene inmediatamente?
4. **Value:** ¿cómo se demuestra el trabajo resuelto?
5. **Trust:** ¿qué confirmación o permiso necesita?
6. **Investment:** ¿qué contexto confirmado mejora el futuro?
7. **Insight:** ¿podrá producir conocimiento fiable más adelante?
8. **Progress:** ¿podrá demostrar una mejora comparable?
9. **Next Trigger:** ¿existe una consecuencia futura realmente útil?

Una función que no responda bien a varias preguntas deberá justificar por qué
merece entrar en el producto.

---

## 15. Riesgos y mitigaciones

| Riesgo | Consecuencia | Mitigación |
|---|---|---|
| Contar actividad en lugar de valor | WUB sube sin que el cliente reciba utilidad | Solo acciones terminales y auditables |
| Inflar una tarea en varios eventos | Métricas y resúmenes engañosos | Familia, entidad, ciclo de vida e idempotencia |
| Exceso de notificaciones | Pérdida de confianza | Interrupciones con razón, medición de descarte y silencio |
| Atribución económica excesiva | Pérdida de credibilidad y riesgo comercial | Directa, asistida y observada; lenguaje limitado |
| Tiempo ahorrado inventado | Promesa imposible de defender | Calibración real, intervalos y metodología visible |
| Automatización prematura | Errores operativos y sensación de pérdida de control | Confirmación, reglas explícitas, pausa y revocación |
| Insights con poca muestra | Recomendaciones falsas | Mínimos de datos, calidad visible y cálculos deterministas |
| Before/after sesgado | Conclusiones incorrectas | Períodos comparables y limitaciones explícitas |
| Métricas que penalizan el plan básico | Profundidad no comparable | Procesos disponibles y cohortes por plan |
| Construir cinco motores a la vez | Complejidad y retraso del piloto | Fundación y tres motores primero; dos motores posteriores |

---

## 16. Veredicto final de dirección

La dirección estratégica es sólida. Noesis no debe competir solamente como software
de facturación, ERP sencillo o asistente por WhatsApp. Su oportunidad es convertirse
en la capa operativa inteligente del pequeño negocio.

Los cinco motores cumplen funciones distintas y complementarias:

- **Habit** hace que el cliente delegue.
- **Trust** permite delegar más sin perder control.
- **Value** demuestra por qué merece la pena pagar.
- **WUB** comprueba si esa delegación ocurre semanalmente.
- **Insight** convierte el histórico en conocimiento.
- **Progress** demuestra mejora y valor acumulado.

La secuencia recomendada es:

> **Registro de Valor → Habit → Trust → Value → WUB y piloto → Value avanzado →
> Insight → Progress → Confidence.**

Noesis ya dispone de eventos, acciones del asistente, resúmenes programados y
permisos explícitos sobre los que construir. No se trata de rehacer el SaaS, sino de
crear la capa transversal que une lo construido y lo convierte en una experiencia
de delegación, seguridad, alivio mental y valor acumulado.

La propuesta merece una valoración estratégica de **9/10**. Su principal riesgo no
es la dirección, sino intentar mostrar métricas sofisticadas antes de garantizar que
los datos son fiables y que los primeros clientes sienten realmente el valor.

La decisión recomendada a los socios es:

> Construir inmediatamente la fundación común y los MVP de Habit, Trust y Value;
> utilizar WUB como indicador interno del piloto; recopilar desde ahora los datos
> que necesitarán Insight y Progress, pero retrasar su experiencia visible hasta
> disponer de histórico suficiente, comparable y fiable.

---

## 17. Evidencia y documentos relacionados

- [`Producto.md`](Producto.md): posicionamiento y principio WhatsApp para hacer,
  SaaS para ver, entender, decidir y controlar.
- [`project-state.json`](project-state.json): estado verificable del producto,
  esquema y validaciones todavía pendientes.
- [`Tareas-vivas.md`](Tareas-vivas.md): piloto, métricas y guardarraíles operativos.
- [`Piloto-operativo.md`](Piloto-operativo.md): puerta de salida y recorrido real.
- [`PRODUCT_PRINCIPLES.md`](design/PRODUCT_PRINCIPLES.md): jerarquía de producto y
  promesa de reducir ruido mental.
- `src/noesis/db.py`: eventos, acciones del asistente y permisos existentes.
- `src/noesis/web/scheduler.py`: resúmenes y automatizaciones periódicas actuales.
