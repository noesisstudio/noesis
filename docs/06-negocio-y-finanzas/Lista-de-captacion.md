# La lista de captación: de dónde salen los 40 nombres

*21 de septiembre de 2026. Complementa `Ruta-a-5000-autonomos.html`, que explica el
método; esto explica **de dónde salen los nombres concretos** en Lleida y el Segrià,
y qué hacer cada día. El sitio donde vive la lista es `/admin/crm`.*

---

## 1. Lo que ya tienes, y por qué es menos de lo que parece

`outputs/prospeccion/lleida-ciudad-osm.csv` tiene **74 fichas de Lleida ciudad**
sacadas de OpenStreetMap. Leídas una a una:

| | Cuántas | Con teléfono |
|---|---|---|
| Oficios (posibles clientes) | 36 | 22 |
| Almacenes y ferreterías | 35 | 16 |
| Gestorías | 3 | 0 |

**Solo 36 de las 74 son clientes potenciales**, y dentro de ellos el reparto no es
el que quieres: 12 electricistas, 8 de pinturas, 6 de carpintería, 4 de
climatización y **2 de fontanería**. Dos fontaneros en una ciudad de 140.000
habitantes no es la realidad: es lo que OpenStreetMap tiene cartografiado. La base
sirve para empezar, no para terminar.

**Las otras 38 fichas no son leads: son puertas.** Y son la parte más valiosa del
archivo, porque cada una te presenta a diez oficios de golpe. Ese es el cambio de
lectura que hay que hacer con esta lista.

---

## 2. Cinco sitios de donde salen los nombres, por orden

Cada nivel cuesta el doble de convencer que el anterior. Empieza arriba.

### 2.1 Tu círculo — el que más convierte, y el que no está en ningún archivo

No es «pensar a ver quién se me ocurre». Es una búsqueda concreta, de media hora:

- En WhatsApp, busca: `presupuesto`, `pressupost`, `factura`, `albarán`, `la obra`.
- En el correo, lo mismo, y filtra por adjuntos PDF de los últimos tres años.
- En el banco: transferencias a nombres de persona o de empresas de oficios.

Sale el fontanero que te arregló la caldera, el electricista de casa de tus padres,
el pintor de un amigo. **Origen `Tu círculo` en el CRM.**

### 2.2 El círculo del círculo — pregunta a diez conocidos

Una sola pregunta, por WhatsApp, a diez personas: *«¿a quién llamas cuando se te
rompe algo en casa?»*. Te dan nombres **con la recomendación incluida**, que es lo
que multiplica la tasa de respuesta. En el CRM, `Te lo presentan` + el nombre de
quien te lo presenta: el guion lo mete en la primera frase, que es donde funciona.

### 2.3 El mostrador del almacén — diez oficios en una mañana

Entre las **7:00 y las 9:00** pasa por el mostrador todo el oficio de la comarca, y
el que atiende los conoce a todos por el nombre. Los que ya tienes localizados:

- **Profesionales:** Saltoki, Obramat, Brico Dépôt, Comercial Urgell, Materials
  Piñol, Comercial i Recanvis Nolasco.
- **Ferreterías industriales:** La Industrial de Lleida, Ramon Soler (Optimus),
  El Faro, Suministros Industriales Cap-pont, Hidro Tarraco, Hidràulica i
  Pneumàtica Lleidatana.
- **Pinturas:** Comercial Pintures, Pintures Janer, Procolor, Tarròs.

Qué pides, y no es una venta: *«Estoy montando una herramienta para autónomos de
oficios. ¿Me presentas a dos o tres clientes vuestros que lleven ellos mismos los
presupuestos y las facturas?»*. Un almacén vive de que a sus clientes les vaya
bien; presentarte le cuesta cero y le hace quedar bien.

### 2.4 El gremio — el directorio de exactamente tu público

En Lleida los instaladores están agrupados, y sus listados de agremiados son
públicos:

- **El Gremi — Gremi d'Empreses Instal·ladores de Lleida** (`elgremilleida.cat`,
  federado en FENIE y CONAIF). Es el directorio más directo de electricistas,
  fontaneros y climatización de la provincia.
- **AGRISEC**, la agrupación de instaladores dentro de **COELL** (la patronal de
  las Terres de Lleida), con secciones de electricidad, calefacción, agua y gas.
- **Gremi de Constructors d'Obres de les Terres de Lleida**, también en COELL, para
  la parte de reformas.
- Asociaciones de autónomos de la provincia (Pro Lleida dels Autònoms i Petites
  Empreses; Associació Multisectorial d'Autònoms de la Província de Lleida).

Verifica los datos de contacto antes de llamar: cambian y aquí solo están anotados.
El movimiento no es mandarles un correo comercial —sería justo lo que la LSSI no
permite—, sino **pedir una reunión o asistir a una charla**. Un gremio que ve una
herramienta útil para sus agremiados es, más adelante, un canal entero.

### 2.5 Google Maps — el relleno, no la base

Es lo que menos convierte, pero completa la lista. Busca **por pueblo y por
oficio**, no «Lleida provincia»:

```
fontanero Lleida          ·  lampista Lleida
electricista Lleida       ·  instal·lador elèctric Lleida
reformas Lleida           ·  reformes integrals Lleida
aire acondicionado Lleida ·  climatització Lleida
```

Y repite con los pueblos del Segrià, que es donde la competencia comercial es menor
y el boca a boca corre más rápido: **Alcarràs, Almacelles, Alpicat, Torrefarrera,
Alfarràs, Almenar, Rosselló, Alcoletge, Torres de Segre, Aitona, Soses, Seròs,
Benavent de Segrià, Artesa de Lleida, Puigverd de Lleida**.

El criterio de la ficha buena: **entre 5 y 30 reseñas, un móvil (6xx/7xx) y ninguna
web**. Pequeño, activo, y el que contesta el teléfono es el dueño. Descarta las
empresas con web corporativa y centralita: ahí ya hay alguien haciendo las facturas.

---

## 3. Cómo se mete todo eso en el CRM

`/admin/crm` → **Pegar la lista**. Traga tres cosas:

1. **Una persona por línea**, como la escribas:
   `Jordi Mas; lampista; Alcarràs; 600 11 22 33`. Entiende el oficio en catalán,
   encuentra el teléfono esté donde esté y no duplica a quien ya esté dentro.
2. **Una tabla con cabecera**: abre `lleida-ciudad-osm.csv`, copia todo y pega. Las
   74 fichas entran con su oficio, su teléfono y su dirección en un solo pegado.
3. **Uno suelto**, el que te encuentras en el mostrador.

Marca el **origen** correcto al pegar cada tanda: no es una etiqueta decorativa.
Decide si hace falta decirle de dónde sacaste su contacto (apartado 5) y es lo que
te dirá, dentro de dos meses, qué fuente trae clientes y cuál solo trae ruido.

Después, la página ya te dice a quién toca llamar hoy y **con qué palabras**, en
castellano y en catalán, con sus datos ya metidos en el texto.

---

## 4. El ritmo: media hora al día, no una tarde heroica

| Cuándo | Qué | Cuánto |
|---|---|---|
| 7:30 – 8:30 | Llamadas. El oficio está de camino a la obra y contesta. | 5 llamadas |
| 13:30 – 14:30 | Segunda ventana buena: parada para comer. | 3 llamadas |
| 18:00 – 19:30 | La tercera, y la mejor para los cafés. | 2 llamadas |
| Viernes, 30 min | Repasar el CRM: mover estados y poner las fechas de la semana. | — |

**Nunca entre las 9:00 y las 13:00**: está con las manos dentro de una pared y te
va a decir que no por no poder hablar, no porque no le interese.

Diez llamadas al día son cuarenta en una semana. El embudo de la Ruta espera que de
40 nombres salgan unas 20 conversaciones y 5 pilotos. La página lo cuenta sola.

---

## 5. Lo que se puede hacer y lo que no

No es prudencia excesiva: la mitad de esto tiene multa y la otra mitad te cuesta el
canal de WhatsApp, que es el producto.

**Llamar por teléfono al número que un autónomo publica como contacto comercial: sí.**
El artículo 19 de la LOPDGDD permite tratar los datos de contacto de un empresario
individual para relacionarte con él **como profesional**, por interés legítimo. Dos
condiciones que el guion en frío ya cumple: decirle **quién eres y de dónde has
sacado su número** en la primera frase (artículo 14 del RGPD, porque el dato no te
lo dio él), y **anotar la baja** en cuanto diga que no. El CRM avisa de lo primero
mientras no esté hecho, y lo segundo es un botón que además impide que ese nombre
vuelva a entrar al pegar la lista otra vez.

**Mandar WhatsApp o correo comercial en frío: no.** El artículo 21 de la LSSI exige
consentimiento previo o una relación contractual anterior. Un mensaje a un número
sacado de Google Maps no tiene ninguna de las dos.

**Y hay un motivo de negocio más urgente que el legal:** la verificación de empresa
de Bynoesis en Meta está **rechazada** (ver `Plan-primer-euro.html`). Mandar
mensajes comerciales no solicitados desde ese número es la forma más rápida de
perder el canal entero por una lista de setenta nombres. El WhatsApp se usa **después**
de que la persona te haya contestado al teléfono o te haya dicho que sí a un café:
ahí ya hay una conversación que él inició.

La pregunta exacta para el abogado está en
`docs/05-legal-y-rgpd/Preguntas-abogado-TIC.md`.

---

## 6. Lo que no hay que hacer

- **Ampliar la zona antes de tener cinco pilotos.** Los cinco tienen que parecerse
  entre sí para que los fallos se repitan y sepas qué arreglar.
- **Enseñar el producto antes de que te cuente un problema.** Si enseñas primero,
  te dirá «qué bien» y no volverás a saber de él.
- **Pilotos sin fecha de fin.** Un piloto sin fecha de fin es un regalo sin fin.
- **Insistir tres veces.** Dos intentos y a dormido. Volver a los dos meses con una
  novedad concreta convierte mejor que perseguir.
- **Comprar listados de correos.** Ni son legales para esto ni convierten.

---

## 7. Lo primero, hoy

1. Pegar `lleida-ciudad-osm.csv` en `/admin/crm` y marcar origen `Ficha pública`.
2. Cambiar a origen `Almacén` las 35 fichas que no son clientes sino puertas: no son
   personas a las que vender, son personas a las que pedir que te presenten.
3. Media hora buscando en tu WhatsApp y tu correo: ahí están los diez nombres que
   más van a convertir, y no están en ningún CSV.
4. Cinco llamadas mañana entre las 7:30 y las 8:30, con el guion de la página.
