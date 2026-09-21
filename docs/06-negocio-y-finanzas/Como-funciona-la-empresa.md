# Cómo funciona Bynoesis: el mapa de la empresa

*21 de septiembre de 2026. Foto de dirección: qué vendes, cómo entra el dinero, qué
está bloqueado y cómo se consiguen clientes. No repite cifras que cambian —apunta a
dónde viven— porque un documento que copia números acaba mintiendo.*

> Para el estado auditado: [[Estado-actual-main]]. Para lo siguiente:
> [[Tareas-vivas]]. Para qué cambió y cuándo: [[Registro-cambios]].
> Para la visión de producto: [[Plan-maestro-Bynoesis]].

---

## 1. La empresa en una frase

Bynoesis vende a autónomos de oficios (fontanería, electricidad, clima, reformas,
limpieza, jardinería) una oficina que trabaja por WhatsApp: presupuestos, agenda,
clientes, facturas, cobros y documentos para la gestoría, sin aprender un ERP.

**Estado real:** el producto está construido y desplegado; la empresa no existe
todavía como entidad legal y no ha cobrado un euro. Lo que falta no es código.

---

## 2. Las cinco piezas de la máquina

| Pieza | Qué es | Cómo está hoy | Qué la desbloquea |
|---|---|---|---|
| **Producto** | La app: web, WhatsApp, documentos, facturas | Construido y desplegado, ~999 pruebas en verde | Nada. Está esperando usuarios |
| **Canal** | WhatsApp con Meta Cloud API | Número central operativo con límite de conversaciones; **verificación de empresa rechazada** | Identidad legal verificable |
| **Cobro** | Stripe + Veri*Factu | Apagado. Stripe exige titular verificado; Veri*Factu, NIF de productor | Identidad legal |
| **Economía** | Cuánto cuesta servir y cuántas cuentas hacen falta | Modelado y dentro del producto: `/admin/economia` | Datos reales del piloto |
| **Captación** | Conseguir los cinco primeros | Método escrito y herramienta construida: `/admin/crm` | Tú. Solo depende de llamadas |

**La única pieza que depende de otra cosa que no seas tú es la identidad legal.**
Las demás esperan a que alguien use el producto.

---

## 3. El producto: qué hace y qué está apagado

**Funciona hoy:** conversación por WhatsApp y web, agenda y trabajos, clientes y
CRM del autónomo, presupuestos, facturas emitidas y recibidas, costes, proyectos
con margen, lectura de documentos (PDF, foto, nota de voz), portal de cliente por
enlace, paquete trimestral para la gestoría, fichajes, catálogos por oficio y panel
de administración.

**Apagado a propósito hasta tener identidad legal:** emisión fiscal con Veri*Factu,
cobro por Stripe y el número de WhatsApp propio por cliente. Un piloto puede usar
casi todo el producto con la facturación fiscal desactivada.

**Prometido pero no construido:** los «100 minutos de llamadas» del plan Premium.
No existe telefonía en el código. Es el riesgo comercial número uno y sigue
pendiente de decisión (quitarlo, marcarlo beta o bajar el precio).

Detalle: [[Producto]] · [[Roadmap]] · [[Arquitectura]]

---

## 4. El dinero

Precios: **29 / 49 / 99 € + IVA** al mes (anual con un mes de descuento). Lo que
cuesta servir una cuenta y lo que deja se calcula en el producto, no en una hoja:
**`/admin/economia`**, con los costes editables desde la propia página.

Las cifras de referencia con los valores de fábrica (21-sep):

| | |
|---|---|
| Coste real por cuenta y mes | 1,48 € (Autónomo) · 3,04 € (Negocio) · 18,47 € (Premium) |
| Ingreso medio por cuenta | 43,00 € |
| Contribución **en caja** (atiendes tú) | 37,98 € |
| Contribución **cargada** (el soporte lo paga alguien) | 28,72 € |
| Vida media de un cliente | 22,2 meses |

**Las tres líneas de equilibrio** —y la diferencia entre ellas es la diferencia
entre un hobby y un trabajo:

| Nivel | Coste al mes | Cuentas |
|---|---|---|
| Cubrir la estructura (servidores, herramientas, gestoría, seguro) | 137 € | **4** |
| Y además la cuota de autónomos: dejas de poner dinero | 437 € | **12** |
| **Y además pagarte 1.200 € al mes** | 1.637 € | **44** |
| Si el soporte lo paga otra persona | 1.637 € | **57** |

**El límite no es el mercado, es tu tiempo.** Con 60 horas al mes y 18,1 minutos de
soporte por cuenta, el techo es **198 cuentas** por persona (139 en la práctica, si
se cuentan las horas de dar altas). Con 3,3 millones de autónomos en España, 5.000
cuentas son el 0,15 %: el mercado nunca es el problema.

**La rampa:** con los supuestos de fábrica, el mes 10 es el primero con resultado
positivo y la caja baja hasta **−3.390 €** antes de recuperarse. Con 4.000 € de
capital inicial sobrevive el escenario base y no el prudente. Por eso la cuota de
implantación de 99 € está en el modelo al 0 %: activarla adelanta el equilibrio de
caja del mes 10 al 7 y la caja nunca llega a ser negativa. Es una decisión abierta.

---

## 5. Las cuatro puertas hasta el primer euro

Están en este orden porque cada una bloquea la siguiente:

1. **Identidad legal.** Meta contrasta contra registros públicos y un autónomo no
   aparece en ninguno. La recomendación es **S.L.** (1.800–2.700 € el primer año).
   Cambiar de entidad después obliga a repetir la verificación y remigrar los WABA.
2. **Verificación de empresa en Meta**, con el NIF escrito igual que en la
   escritura. Hoy está **rechazada**.
3. **Advanced access** sobre `whatsapp_business_management`: obligatorio para tocar
   la WABA de otro negocio, aunque te la concedan a mano.
4. **Papeles para cobrar:** Stripe en real, declaración responsable de Veri*Factu y
   textos legales revisados por abogado.

**Lo que no necesita ninguna puerta:** la lista, los cafés, las entrevistas, los
pilotos gratuitos con la facturación fiscal apagada, las cartas de intención al
precio de fundador y el contenido orgánico. Es decir: **todo lo de la parte 6**.

La recomendación del plan es montar la S.L. **cuando tres pilotos hayan firmado**,
no antes: así se paga con la prueba de que hay a quién cobrar.

Detalle: [`Plan-primer-euro.html`](Plan-primer-euro.html) ·
[[Constitucion-y-primer-euro]] · [`Ruta-legal.html`](../05-legal-y-rgpd/Ruta-legal.html)

---

## 6. Cómo se captan clientes

### El embudo que hay que esperar

```
40 nombres → 20 conversaciones → 8 con problema real
           → 5 aceptan el piloto → 3 lo usan solos → 2 pagarían
```

Son órdenes de magnitud, no datos medidos. Sirven para saber que 40 nombres no es
exagerar.

### Dónde viven los nombres

**`/admin/crm`**, dentro del producto. Nueve estados que son los del piloto (en
lista → contactado → cita → ya hablado → piloto → carta firmada → pagando), la
lista se pega tal como esté escrita, los guiones salen en castellano y catalán con
los datos de cada persona, y la página dice **a quién llamar hoy**, en lotes de
diez. Es el CRM de la empresa; el de `/b/<id>/crm` es el del autónomo.

### De dónde salen, por orden de conversión

1. **Tu círculo.** Buscar `presupuesto`, `pressupost`, `factura`, `albarán` en tu
   WhatsApp y tu correo de los últimos tres años.
2. **El círculo del círculo.** Una pregunta a diez conocidos: «¿a quién llamas
   cuando se te rompe algo?».
3. **El mostrador del almacén**, entre las 7:00 y las 9:00. No son clientes: son
   quien te presenta a diez oficios en una mañana.
4. **El gremio.** En Lleida, El Gremi d'Empreses Instal·ladores, AGRISEC dentro de
   COELL y el Gremi de Constructors. Sus agremiados son exactamente tu público.
5. **Google Maps**, por pueblo y oficio. Ficha buena: 5–30 reseñas, móvil y sin web.

### El ritmo

Diez llamadas al día: cinco entre 7:30 y 8:30, tres a mediodía, dos por la tarde.
**Nunca entre las 9:00 y las 13:00.** Cuarenta llamadas a la semana es la lista
entera.

### Lo que se puede y lo que no

Llamar al número que un autónomo publica como contacto profesional: **sí**,
diciéndole de dónde lo sacaste y anotando la baja si dice que no. WhatsApp o correo
comercial en frío: **no** (art. 21 LSSI). Y con la verificación de Meta rechazada,
mandar mensajes no solicitados desde el número de Bynoesis es perder el canal por
una lista de setenta nombres.

Detalle: [`Ruta-a-5000-autonomos.html`](Ruta-a-5000-autonomos.html) (el método) ·
[[Lista-de-captacion]] (de dónde salen los nombres en Lleida y el Segrià)

---

## 7. De 1 a 5.000, por etapas

No se pasa de etapa por fecha, sino cuando se cumple la puerta de salida.

| Etapa | Cuentas | Dónde | Cómo captas | Puerta de salida |
|---|---|---|---|---|
| 1 · Pilotos | 0 → 5 | Tu comarca, dos oficios | Círculo, almacenes, Maps | 3 usan solos 2 semanas, 2 firman |
| 2 · Primeros de pago | 5 → 50 | La comarca y las de al lado | Referidos, gestorías, gremio | 50 de pago, bajas <5 %, resultado a cero con tu retirada |
| 3 · La provincia | 50 → 250 | Toda la provincia | Páginas por oficio y población, 10–20 gestorías | Soporte ≤7 min/cuenta, sabes de dónde viene el 60 % |
| 4 · Cataluña | 250 → 1.000 | En catalán y castellano | Comerciales a comisión, programa de gestorías, anuncios | Bajas <3 %, el equipo funciona un mes sin ti |
| 5 · España | 1.000 → 5.000 | Por comunidades | Asociaciones estatales, distribución, publicidad a escala | — |

**Dos verdades incómodas:** con 5.000 cuentas y un 4 % de bajas hacen falta **200
altas al mes solo para no encoger**; y atenderlas cuesta **8 personas** si cada una
pide 12 minutos de soporte, o 3,5 si pide 4. Bajar las bajas vale tanto como
vender, y que el producto se explique solo vale tanto como contratar.

---

## 8. Quién hace qué

| | |
|---|---|
| **Founder** | Negocio y dirección: captación, decisiones de precio, identidad legal, relación con gestoría y abogado, pilotos |
| **Agentes IA** | Todo el desarrollo. Claude/Fable: seguridad, fiscalidad, integraciones, arquitectura, despliegue. Codex: frontend, diseño, copy, CI y QA |

Dónde se escribe cada cosa, y es obligatorio: bitácora en
[[Registro-cambios]], estado en [[Estado-actual-main]], pendientes en
[[Tareas-vivas]], código en [[Mapa-codigo]], QA en [[Registro-QA]], decisiones en
[[Decisiones]] y la foto legible por máquinas en `project-state.json`, que la CI
valida contra el código. Las reglas completas están en `AGENTS.md`.

---

## 9. Qué se construyó en las dos últimas sesiones

**18-sep — La economía entra en el producto.** El modelo dejó de vivir en hojas de
cálculo: `/admin/economia` calcula en el servidor el coste por plan, las dos
contribuciones, los tres equilibrios, la capacidad en horas y la caja a 36 meses,
con **47 costes editables y guardados** desde la propia página y descargas de Word
y Excel generadas al vuelo. Antes, para cambiar la cuota de la gestoría había que
tocar un archivo.

**21-sep — La captación entra en el producto.** `/admin/crm`: el embudo de la
empresa, el importador que traga la lista pegada o una tabla con cabecera, los
guiones por estado en las dos lenguas, el historial de cada contacto, las bajas que
no se pueden deshacer por accidente y el aviso del art. 14 cuando el teléfono no te
lo dio su dueño. Más la guía de dónde salen los nombres en Lleida y el Segrià, y
tres preguntas nuevas para el abogado sobre llamada en frío.

**Lo que eso significa junto:** las dos preguntas que antes vivían fuera del
producto —«¿cuánto gano con esto?» y «¿a quién llamo hoy?»— ahora se responden
dentro, con los datos reales y sin abrir un archivo.

---

## 10. Los cinco números que deciden, y ninguno está medido

1. **Bajas mensuales.** Se supone 8 % los tres primeros meses y 4 % después.
2. **Minutos de soporte por cuenta.** Se suponen 18,1 de media ponderada. Decide
   cuánta gente hace falta y es la cifra que más mueve el plan a 5.000.
3. **Horas por alta.** Se suponen 3. Deciden cuántos clientes caben en tu mes.
4. **Cuánto convierte cada fuente de captación.** El CRM lo guardará solo.
5. **Lo que de verdad pagas cada mes.** Hasta que estén tus facturas reales en
   `/admin/economia`, los tres equilibrios son un escenario, no tu negocio.

Los cinco se miden con cinco pilotos. **Por eso todo lo demás espera.**

---

## 11. Lo siguiente, en orden

1. Cuarenta nombres en el CRM y diez llamadas al día.
2. La pregunta escrita a la asesoría: ¿un piloto gratuito es comercialización a
   efectos del RD 1007/2023? De ella depende si los pilotos pueden facturar.
3. Cinco pilotos con fecha de fin y contrapartidas por escrito.
4. Tus facturas reales en `/admin/economia`.
5. Cuando tres firmen la carta de intención: montar la S.L. y abrir las cuatro
   puertas en orden.
