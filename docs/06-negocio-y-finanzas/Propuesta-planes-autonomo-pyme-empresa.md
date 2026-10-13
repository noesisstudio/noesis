# Propuesta: planes por segmento, tarifa al alza y precio de lanzamiento

> **Actualización 12/10/2026:** el founder decidió la escalera y las pestañas de este
> documento con un tachado del doble (60 / 100 / 200 €, −50 %) sobre 29 / 49 / 99 €.
> Está hecho en local y registrado en [[Decisiones]]. Siguen abiertas las preguntas
> 3, 4, 5, 6 y 7 del §10 y la condición exacta del lanzamiento.
>
> Propuesta para aprobar · 09/10/2026 · importes mensuales **sin IVA** salvo indicación.
> **Nada de este documento está decidido.** El catálogo adoptado sigue siendo
> 29 / 49 / 99 € ([[Decisiones#Precio adoptado, prueba completa y después modo consulta (2026-07-15)]]).
> Las cifras salen del mismo motor que usa `/admin/economia`
> (`src/noesis/economics.py`) con sus supuestos de fábrica. Son escenarios, no
> datos: no hay clientes de pago.

Dirección del founder (09/10/2026):

- No se bajan precios ni se crean planes más baratos: **la tarifa sube**.
- La tarifa se enseña **con el precio de oferta al lado**, como hace Holded, para que
  se vea el potencial de venta.
- Las altas costarán cada vez menos tiempo.

## Resumen

1. **Holded no tiene tres catálogos: tiene una escalera de cinco planes**
   (15 / 29 / 59 / 99 / 199 €). Cada pestaña de su web (autónomos, empresas pequeñas,
   medianas) enseña tres peldaños seguidos de esa escalera. Sobre cada uno pone el
   precio tachado y al lado el −50 % de los tres primeros meses. Copiamos la escalera,
   las pestañas y el precio al lado. No copiamos sus peldaños baratos.
2. **Propuesta:**

   | Plan | Tarifa | Precio de lanzamiento |
   |---|---:|---:|
   | Autónomo | 39 € | 29 € |
   | Pyme (antes Negocio) | 69 € | 49 € |
   | Avanzado (antes Premium) | 129 € | 99 € |
   | Empresa (más adelante, cuando haya roles) | 299 € | 199 € |

   **El precio de lanzamiento son los precios de hoy.** Se mantiene 12 meses para
   quien se dé de alta en los 12 primeros meses.
3. **El primer año queda igual que hoy y, a partir de ahí, el negocio mejora mucho:**

   | | Hoy | Con la propuesta |
   |---|---:|---:|
   | Ingreso al mes 36 | 4.814 € | 6.533 € (+36 %) |
   | Clientes para pagarte el sueldo | 43 | 32 |
   | Bajas mensuales que se aguantan sin perder valor por cliente | 4 % | 5,8 % |

4. **Captación de pago (§6):** solo es rentable con CAC ≤ 150–175 €. Eso exige un
   CPC de ~1 € (no 2,50 €) y conversiones de 7 % y 18 %. Pero los anuncios no hacen
   crecer nada si antes no se libera soporte: con −30 % de soporte y una media jornada,
   600 €/mes a CAC 80 € llevan el mes 36 a ~409 clientes y ~18.000 €/mes de resultado,
   sin necesitar más caja que hoy.
5. **La voz deja de ir incluida** en Avanzado y pasa a ser un extra. La **gestoría
   pasa a ser gratis en todos los planes** (hoy está cerrada en Autónomo).
6. **Un aviso legal.** Un precio tachado tiene que ser real. La tarifa debe
   publicarse y aplicarse de verdad al acabar la oferta, y la oferta debe tener fecha
   o condición de fin. Pregunta para el abogado (§9).

---

## 1. Cómo vende Holded (consultado el 09/10/2026)

Fuente: [holded.com/es/precios](https://www.holded.com/es/precios), las cuatro
pestañas y el selector mensual/anual.

### Una escalera, cuatro puertas

| Plan | Precio | Primeros 3 meses | Usuarios | Facturas/año | Qué añade |
|---|---:|---:|---:|---:|---|
| Plus | 15 € | 7,50 € | 1 | 250 | Facturación Verifactu, escáner de gastos, cash flow |
| Básico | 29 € | 14,50 € | 2 | 1.000 | Contactos ilimitados, rentabilidad de proyectos, modelos IRPF |
| Estándar | 59 € | 29,50 € | 4 | 3.000 | Contabilidad completa, SII, sociedades, remesas, activos |
| Avanzado | 99 € | 49,50 € | 7 | 10.000 | Roles y campos personalizados, soporte prioritario |
| Premium | 199 € | 99,50 € | 15 | ∞ | IVA multipaís, soporte premium por teléfono |

| Pestaña | Para quién | Planes que enseña (en negrita, el «popular») |
|---|---|---|
| Autónomos | Profesionales independientes | Plus · **Básico** · Estándar |
| Empresas pequeñas | De 1 a 10 personas | Básico · **Estándar** · Avanzado |
| Empresas medianas | Más de 10 empleados | Estándar · **Avanzado** · Premium |
| Asesorías | Despachos | A medida, por teléfono y sin precio público |

### Los mecanismos

- **Pestañas solapadas:** el plan de la derecha de una pestaña es el primero de la
  siguiente.
- **Precio tachado y oferta al lado:** −50 % durante 3 meses, con «Ahorra X €».
- **Lo que sube de un plan a otro son los usuarios:** 1, 2, 4, 7 y 15. Cada usuario
  extra cuesta 10 €/mes.
- **La asesoría entra gratis en todos los planes** y no ocupa plaza.
- **Extras de pago** («Gemas»): inventario 25 €, nóminas 5 €/empleado, TPV 25 €,
  wallet 10 €.
- **El anual no tiene descuento:** son 12 mensualidades.
- **Soporte escalonado:** prioritario desde Avanzado y teléfono en Premium.

## 2. Lo que vendemos hoy

En [bynoesis.com/precios](https://www.bynoesis.com/precios) y en
`src/noesis/adapters/billing.py`:

| Plan | Precio | Anual (paga 11, usa 12) | Acciones IA | Qué incluye |
|---|---:|---:|---:|---|
| Autónomo | 29 € | 319 € | 75 | Agenda, clientes, trabajos, presupuestos, facturas, cobros, WhatsApp, documentos |
| Negocio | 49 € | 539 € | 300 | + equipo y fichaje, portal de gestoría, proyectos, soporte prioritario |
| Premium | 99 € | 1.089 € | 1.500 | + puesta en marcha acompañada y línea directa. Voz en *beta* («incluirá 100 min») |

Lo que se ve en el código:

- **Negocio y Premium dan exactamente las mismas funciones**
  (`PLAN_ENTITLEMENTS`). Tampoco hay un límite de trabajadores por plan.
- **La gestoría conectada está bloqueada en Autónomo.**
- **Hay una sola cuenta de acceso por negocio y no hay roles.** El equipo entra como
  trabajador, por WhatsApp o con enlace. Las gestorías sí tienen una cuenta
  multiempresa (`gestoria_accounts`).
- **La voz es lo que hunde el margen de Premium:** de 18,47 € de coste, 11,40 € son la
  voz.

## 3. Qué copiar y qué no

| Mecanismo de Holded | ¿Copiar? | Por qué |
|---|---|---|
| Escalera y pestañas por segmento | **Sí** | Ordena la web y el discurso sin multiplicar producto |
| Precio de oferta al lado de la tarifa | **Sí, adaptado** | Nuestra oferta dura 12 meses a precios de hoy, no −50 % tres meses: protege la caja (§5) |
| Planes baratos de entrada (15 €) | **No** | Decisión del founder. Además, con nuestros números rinden la mitad por minuto de soporte |
| Unidad que escala: usuarios | **Adaptar** | Nuestra unidad es el **trabajador** (WhatsApp, fichaje). Sin roles no podemos vender usuarios |
| Asesoría gratis en todos los planes | **Sí, ya** | Es nuestro canal ([[Canal-comercial-y-comisiones]]) |
| Extras de pago | **Sí** | La voz sale del plan de 99 € y se cobra lo que cuesta |
| Límite por facturas al año | **No** | Una factura nos cuesta casi cero. Limitamos IA, voz y WhatsApp |
| Anual sin descuento | **No** | «Paga 11, usa 12» adelanta caja |
| Contabilidad completa, SII, inventario | **No** | No es nuestro hueco ([[Benchmark_SaaS#Límite consciente]]) |
| Asesorías sin precio público | **Sí** | Encaja con la comisión propuesta y con el panel multiempresa |

## 4. La propuesta

### Las cuatro puertas de la web

| Pestaña | Para quién | Planes que enseña (en negrita, el destacado) |
|---|---|---|
| **Autónomos** | Una persona, oficios y servicios | **Autónomo** · Pyme · Avanzado |
| **Pymes** | De 2 a 10 personas con trabajadores | Autónomo · **Pyme** · Avanzado |
| **Empresas** | De 10 a 50 personas | Pyme · **Avanzado** · Empresa (próximamente) |
| **Gestorías** | Despachos con cartera | Acceso gratis + programa partner, sin precio público |

### La escalera

| Plan | Tarifa | Lanzamiento | Anual a tarifa (11×) | Personas | Acciones IA | Qué añade |
|---|---:|---:|---:|---|---:|---|
| **Autónomo** | 39 € | 29 € | 429 € | Titular | 75 | Lo de hoy **+ gestoría conectada gratis** |
| **Pyme** | 69 € | 49 € | 759 € | Titular + 5 trabajadores | 300 | Equipo y fichaje, proyectos y rentabilidad, paquete trimestral, soporte prioritario |
| **Avanzado** | 129 € | 99 € | 1.419 € | Titular + 15 trabajadores | 1.500 | Puesta en marcha acompañada, línea directa. **Sin voz incluida** |
| Empresa | 299 € | 199 € | 3.289 € | Roles + 50 trabajadores | 3.000 | Roles, auditoría de accesos, varias sedes, gestor de cuenta. **Fase 3** |

**Reglas del precio de lanzamiento** (para que la tarifa tachada sea creíble y
legal):

- Lo consigue quien se da de alta en los **12 primeros meses** desde la publicación.
  Se puede limitar también a los primeros 100 clientes.
- Se mantiene **12 meses** desde el alta. Después, la cuenta pasa a la tarifa,
  avisando con 30 días de antelación.
- En la web: «39 € tachado · **29 €** + IVA/mes · precio de lanzamiento durante 12
  meses». La tarifa tiene que ser la que se cobra de verdad después.
- En el anual, el lanzamiento se aplica al primer año completo: 319 / 539 / 1.089 €,
  igual que hoy.

### Variante del founder: precio de comparación 90 / 120 / 250 €

Pedida el 09/10/2026. Tachado de 90 / 120 / 250 € y venta a 29 / 49 / 99 €. El
descuento que se enseña es del 68 / 59 / 60 %.

| Si el tachado… | Mes en positivo | Caja mínima | Ingreso mes 36 |
|---|---:|---:|---:|
| …nunca se cobra (solo referencia) | 10 | −3.333 € | 4.814 € (igual que hoy) |
| …se cobra al acabar 12 meses de oferta | 10 | −3.333 € | 13.181 €* |

\* Es un techo, no una previsión. Supone que nadie se da de baja cuando su cuota se
triplica (+210 / +145 / +153 %).

- **Como referencia que nunca se cobra, no cambia ni un euro del negocio.** Solo
  cambia lo que se enseña.
- **Es el caso típico de precio de referencia ficticio.** Si nadie paga nunca 90 €,
  tacharlo da a entender un ahorro que no existe: es una práctica engañosa según la
  Ley de Competencia Desleal. Para consumidores, la normativa exige además que el
  precio anterior sea el más bajo aplicado en los 30 días previos.
- **Hay otra forma de enseñar ese potencial sin el riesgo:** comparar con lo que
  cuesta hacerlo de otra manera, sin tachar nada. Por ejemplo: «Gestoría +
  administrativo + software: ~250 €/mes · Bynoesis Avanzado: 99 €». Las cifras
  tienen que poder justificarse con una fuente.

### Extras

| Extra | Precio | Coste estimado | Contribución | Nota |
|---|---:|---:|---:|---|
| Recepcionista de voz (100 min) | 29 €/mes | 11,40 € | 16,09 € (55 %) | Solo cuando la voz exista. Hoy sigue en *beta* gratis |
| Trabajador adicional | 5 €/mes | < 0,50 € | ~4,30 € | Nuestro «usuario extra» |
| Pack de 500 acciones IA | 9 € | 1–6 € (peor caso) | ≥ 3 € | Para un mes puntual sin subir de plan |
| Puesta en marcha acompañada | 99 € una vez | tu tiempo | — | Gratis en el anual y en Avanzado |

### Gestorías

- Acceso gratis a la cartera de cada cliente **en todos los planes**.
- La comisión propuesta (estructura D: una mensualidad + 10 % durante 12 meses) solo
  se paga en clientes de pago. Sin aprobar ([[Canal-comercial-y-comisiones]]).
- Condiciones por volumen solo cuando exista la liquidación de comisiones.

## 5. Los números

Motor: `src/noesis/economics.py` con los supuestos de fábrica: mezcla de planes
60/30/10, retirada 1.200 €, cuota de autónomos 300 €, 60 h/mes, 3 h por alta, bajas
del 8 % y luego del 4 %, y caja inicial de 4.000 €. El precio de lanzamiento se
simula por cohortes con la misma aritmética. Con oferta cero reproduce al céntimo
el motor del producto.

### Por plan, a tarifa

| Plan | Tarifa | Coste de servir | Margen bruto | Contribución en caja | Soporte | € por minuto de soporte |
|---|---:|---:|---:|---:|---:|---:|
| Autónomo | 39 € | 1,70 € | 95,6 % | 36,13 € | 12 min | 3,01 |
| Pyme | 69 € | 3,84 € | 94,4 % | 63,09 € | 22 min | 2,87 |
| Avanzado (sin voz) | 129 € | 7,73 € | 94,0 % | 117,40 € | 40 min | 2,94 |
| Empresa | 299 € | 18,07 € | 94,0 % | 271,96 € | 90 min | 3,02 |
| *Hoy: Autónomo 29 €* | *29 €* | *1,48 €* | *94,9 %* | *26,65 €* | *12 min* | *2,22* |

### Por escenario

| Escenario | Equilibrio con tu sueldo | Mes en positivo | Caja mínima | Ingreso mes 36 |
|---|---:|---:|---:|---:|
| **Hoy** 29/49/99 | 43 | 10 | −3.333 € | 4.814 € |
| +20 %: 35/59/119 | 36 | 8 | −2.039 € | 5.800 € |
| **+35 %: 39/69/129** | **32** | **8** | **−1.324 €** | **6.533 €** |
| +55 %: 45/79/149 | 28 | 7 | −605 € | 7.519 € |
| **+35 % con lanzamiento 12 meses** (recomendado) | 32 (43 durante la oferta) | 10 | −3.333 € | 6.533 € |
| +35 % con lanzamiento 6 meses | 32 | 9 | −3.108 € | 6.533 € |
| +35 % con −50 % tres meses para siempre, como Holded | 32 | 8 | −2.410 € | 6.334 € |

«Caja mínima» es el punto más bajo de la caja, ya contando los 4.000 € iniciales. Un
valor negativo es dinero que habría que poner además de esos 4.000 €.

### Lo que dicen las tablas

1. **El lanzamiento a precios de hoy no cuesta nada que no estuviera ya en el plan.**
   El primer año es idéntico al escenario actual (mes 10, −3.333 €), y a partir del
   mes 13 las primeras cuentas pasan a la tarifa. Lo que se vende como «oferta» es
   el precio que ya habíamos aprobado.
2. **Subir la tarifa paga margen de error en las bajas.** Con 39/69/129, el valor de un
   cliente a lo largo de su vida (LTV) se mantiene como hoy aunque las bajas mensuales
   suban del 4 % al 5,8 %. Con bajas del 10 % y luego del 5 %, la tarifa nueva sigue
   ingresando 5.900 € en el mes 36, frente a 4.347 € con los precios de hoy.
3. **+55 % da más, pero nos pone por encima de Holded en todos los peldaños.**
   Autónomo a 45 € es más de lo que Holded cobra a una pyme pequeña (Básico, 29 €).
   La opción +35 % deja la oferta al nivel de Holded y la tarifa algo por encima,
   justificada por WhatsApp e IA.
4. **El −50 % de Holded, aplicado a la tarifa nueva, es peor que nuestro
   lanzamiento** a partir del primer año (6.334 € frente a 6.533 € en el mes 36), y
   enseña un descuento que dura muy poco.

### Si las altas cada vez cuestan menos

Con altas más baratas, la cartera crece más rápido. Con 3 h → 0,5 h en 24 meses, la
cartera del mes 36 pasa de 117 a unos 156 clientes con los precios de la fase
anterior. Hacia el mes 19 el soporte se come el 70 % de tus horas, y desde entonces
el límite es el **dinero por minuto de soporte**. La subida lo mueve de ~2,2 a ~3 € por
minuto (tabla por plan). Es el mejor argumento para no tener planes baratos: un plan
de 15 € deja 1,37 € por minuto.

## 6. Captación de pago: CPC, embudo y rentabilidad

Mismo motor por cohortes, con los precios nuevos (tarifa 39/69/129 y lanzamiento
29/49/99 durante 12 meses) y altas cada vez más baratas: de 3 h a 0,5 h en 24 meses.
Cada alta de pago entra con su propio coste de captación (CAC) y sus propias horas.
El gasto en anuncios sale de la caja el mes en que se gasta.

### Cuánto puede costar un cliente

Un alta durante el lanzamiento deja **1.061 €** de contribución en caja a lo largo de
su vida (hoy: 861 €). El CAC máximo depende de lo que se exija:

| Regla | CAC máximo | Lectura |
|---|---:|---|
| Recuperar el CAC en ≤ 6 meses | 175 € | **Objetivo de trabajo.** Protege la caja, que es lo que falta |
| Recuperar el CAC en ≤ 12 meses | 320 € | Límite duro: por encima, la campaña se para |
| LTV / CAC ≥ 3 | 354 € | Referencia SaaS. Aquí es más laxa que el payback, así que manda el payback |

| CAC | LTV / CAC | Meses para recuperarlo |
|---:|---:|---:|
| 80 € | 13,3 | 3 |
| 150 € | 7,1 | 6 |
| 250 € | 4,2 | 9 |
| 417 € | 2,5 | 16 |

### Del CPC al CAC: el embudo

**CAC = CPC ÷ (clic → prueba × prueba → pago)**

| Embudo | CPC | Clic → prueba | Prueba → pago | CAC |
|---|---:|---:|---:|---:|
| Sin optimizar: Search genérico («programa de facturación») | 2,50 € | 4 % | 15 % | **417 €** |
| Base | 1,50 € | 6 % | 17 % | **147 €** |
| **Objetivo** | **1,00 €** | **7 %** | **18 %** | **79 €** |
| Muy bueno | 0,80 € | 8 % | 20 % | 50 € |

CPC máximo que se puede pagar según la conversión que se consiga:

| Conversión (clic → prueba / prueba → pago) | CAC 80 € | CAC 150 € | CAC 320 € (límite) |
|---|---:|---:|---:|
| 4 % / 15 % | 0,48 € | 0,90 € | 1,92 € |
| 6 % / 17 % | 0,82 € | 1,53 € | 3,26 € |
| 7 % / 18 % | 1,01 € | 1,89 € | 4,03 € |

De dónde salen las referencias:

- **CPC:** en España, una guía sitúa la media de Search en 2,69 € y otra da entre
  0,80 € y 2,50 € para la mayoría de sectores. En Meta, la mediana va de 0,40 a
  1,05 USD.
- **Conversión:** las pruebas sin tarjeta convierten de media un 8,5 % de visita a
  prueba (tráfico orgánico) y un 18,2 % de prueba a pago, según First Page Sage.
  ChartMogul da cifras más bajas.

Ninguna es un dato nuestro. El CPC real de las palabras clave hay que sacarlo del
Planificador de Google Ads antes de gastar.

**Lectura:** con conversiones normales, pujar por «programa de facturación» contra
Holded, Quipu y Sage no es rentable. El CPC tiene que bajar de 2,50 € a ~1 € y la
conversión subir a la vez.

### Cómo bajar el CPC

1. **No pujar por lo genérico.** «Programa de facturación» o «software de facturación»
   es la palabra más disputada del sector. Mejor long tail de oficio y de problema:
   «app para hacer facturas fontanero», «presupuestos desde el móvil electricista»,
   «facturar por WhatsApp», «Verifactu autónomos móvil». Menos volumen, clic más
   barato y más intención.
2. **Palabras negativas desde el día 1:** gratis, plantilla, Excel, curso, empleo,
   «login», nombres de competidores. Cada clic que no compra sube el CAC.
3. **Nivel de calidad de Google.** Una landing por oficio, con el anuncio repitiendo la
   palabra buscada. Un nivel de calidad alto rebaja el CPC real que cobra Google.
4. **Meta con vídeo de uso real** (15 s: audio por WhatsApp → factura hecha). El clic es
   más barato que en Search.
   - Los anuncios que abren una conversación de WhatsApp encajan con el producto, pero
     **dependen de tener la verificación de Meta, hoy rechazada**. Mientras tanto, a la
     landing.
5. **Retargeting** de quien visitó precios o empezó el alta: el clic más barato y el más
   caliente.
6. **Acotar** por provincia (primero donde haya gestorías partner) y por franja horaria
   (tardes y domingos, cuando el autónomo hace papeles).

### Cómo subir la conversión

- **Clic → prueba (4 % → 7 %):**
  - Landing por oficio con un vídeo de 15 s.
  - El precio de lanzamiento visible.
  - Alta en 3 campos sin tarjeta (ya existe).
  - Opción «pruébalo por WhatsApp» cuando Meta lo permita.
  - Testimonios de los pilotos con su permiso.
- **Prueba → pago (15 % → 18 %):**
  - La primera factura real en los primeros 10 minutos.
  - Invitar a la gestoría durante la prueba: es lo que más ata, y ahora va gratis en
    todos los planes.
  - Mensajes en los días 1, 3, 7 y 12.
  - Pedir el plan el día 10, con el precio de lanzamiento garantizado 12 meses y la
    opción anual.
- **Bajas:** acompañamiento el primer mes y la gestoría conectada. Cada punto de bajas
  que se baja vale más que cualquier campaña ([[Escalado-de-Bynoesis]]).

### ¿Es rentable? Escenarios a 36 meses

Todas las filas usan los precios nuevos y las altas decrecientes. «Caja mínima»
incluye los 4.000 € iniciales.

| Escenario | Gasto en anuncios | Mes en positivo | Caja mínima | Clientes mes 36 | Ingreso mes 36 | Resultado mes 36 |
|---|---:|---:|---:|---:|---:|---:|
| Hoy (29/49/99, sin anuncios) | 0 | 10 | −3.333 € | 117 | 4.814 € | 2.727 € |
| A · Precios nuevos, sin anuncios | 0 | 10 | −3.333 € | 156 | 8.776 € | 6.415 € |
| B · Anuncios sin optimizar (CAC 417 €) | 600 €/mes | 11 | −6.254 € | 159 | 8.854 € | 6.314 € |
| C · Anuncios base (CAC 150 €) | 600 €/mes | 9 | −4.562 € | 160 | 8.892 € | 6.456 € |
| D · Anuncios objetivo (CAC 80 €, alta pagada 0,5 h) | 600 €/mes | 8 | −3.321 € | 160 | 8.921 € | 6.535 € |
| E · D + soporte −30 % | 600 €/mes | 8 | −3.321 € | 221 | 12.335 € | 9.643 € |
| **F · E + media jornada de soporte** | 600 €/mes | **8** | **−3.321 €** | **409** | **22.583 €** | **18.098 €** |
| G · F con 1.200 €/mes de anuncios | 1.200 €/mes | 9 | −4.694 € | 452 | 25.125 € | 20.486 € |
| I · F, pero con CAC 150 € | 600 €/mes | 9 | −4.562 € | 357 | 19.496 € | 14.723 € |
| K · G, pero con CAC 417 € | 1.200 €/mes | 12 | **−9.508 €** | 338 | 18.431 € | 13.146 € |

La media jornada de soporte cuesta 900 €/mes en el libro, aunque
[[Escalado-de-Bynoesis]] usa 1.300 €. Se contrata cuando el soporte llega al 70 % de
tus 60 h y aporta 65 h al mes. El modelo solo contrata una vez.

### Lo que dicen estos escenarios

1. **Los anuncios solos no hacen crecer nada.** B, C y D añaden 3 o 4 clientes en el mes
   36, porque el límite son tus horas y no el número de clientes interesados. Sin
   optimizar (B), además, empeoran la caja en 3.000 €.
2. **Lo que convierte los anuncios en crecimiento es el soporte:** −30 % de minutos por
   cuenta y una media jornada cuando toca. Con eso, 600 €/mes a CAC 80 € llevan de 156
   a **409 clientes** y a **18.098 €/mes de resultado** en el mes 36, sin necesitar más
   caja que hoy.
3. **El CPC importa por la caja, no por el volumen.** Con CAC 417 € (K) la caja cae a
   −9.508 € y el positivo se retrasa al mes 12. Con CAC 80 €, al mes 8.
4. **Más presupuesto da poco:** de 600 a 1.200 €/mes (F → G) se ganan 43 clientes, pero
   la caja necesita 1.400 € más. Se sube por tramos solo si el CAC aguanta.

Las cifras a partir del mes 24 multiplican varios supuestos sin medir: bajas,
soporte, CAC y que haya demanda suficiente. Sirven para fijar objetivos y reglas de
corte, no como previsión.

### Plan de captación rentable

| Etapa | Cuándo | Presupuesto | Qué se hace | Puerta para seguir |
|---|---|---:|---|---|
| 0 · Medir | Antes del primer euro en anuncios | 0 € | Guardar el **origen de cada alta** (UTM, gclid, fbclid), enviar conversiones prueba y pago a Google y Meta con el consentimiento de cookies, e importar el coste a `/admin/economia`. Landing por oficio. **Hoy no hay nada de esto en el código** | Embudo visible de punta a punta |
| 1 · Probar | Con Stripe en real y pilotos cerrados | 300–600 €/mes | Search long tail + retargeting + Meta con vídeo, 3–4 semanas | CAC ≤ 150 €, prueba → pago ≥ 15 % |
| 2 · Escalar | Soporte ≤ 12,5 min/cuenta y alta pagada ≤ 30 min | 600–1.200 €/mes | Subir por tramos de 300 €; media jornada de soporte al 70 % | CAC ≤ 175 € (payback ≤ 6 meses) |

**Reglas de corte**, revisadas cada semana:

- Se para la campaña si el CAC de las últimas 30 pruebas supera 320 €.
- Se para si el LTV/CAC baja de 3.
- Se pausa la captación si las bajas del cuarto mes superan el 6 %.
- No se gastan más de 2.000 € sin haber llegado a la puerta de la etapa 1.

## 7. Lo que tiene que existir antes de vender cada plan

| Plan o cambio | Ya existe | Falta |
|---|---|---|
| Autónomo + gestoría gratis | Panel de gestoría multiempresa, enlaces `/g/`, TOTP | Quitar `gestoria` de `ENTITLEMENT_MINIMUM_PLAN` y repasar textos |
| Precio de lanzamiento | Stripe preparado con precios por plan y periodicidad | Precio de oferta en Stripe (cupón de 12 meses o precio propio), fecha de fin guardada en la cuenta, aviso 30 días antes del cambio |
| Pyme (5 trabajadores) | Equipo, fichaje, proyectos, portal de gestoría | Límite de trabajadores por plan en servidor y extra en Stripe |
| Avanzado sin voz | Todo | Quitar los «100 minutos» del plan; voz como extra en *beta* |
| Extra de voz | Adaptador de voz | Recepcionista sin construir: no se cobra hasta que funcione |
| Empresa | Cuenta de gestoría con varias empresas | **Roles, varios accesos por negocio, auditoría de accesos, sedes.** `users` solo tiene `is_admin` |
| Todo | — | Siguen los bloqueos de siempre: entidad legal, Stripe en real, Veri\*Factu y textos legales revisados |

## 8. Plan de cambio

**Fase 1 (precio y web):**

1. Aprobar tarifa 39 / 69 / 129 €, lanzamiento 29 / 49 / 99 € y la voz como extra.
2. Código:
   - `PLANS` (tarifa + precio de lanzamiento) y `PLAN_ENTITLEMENTS` en
     `adapters/billing.py`.
   - `precio` en `economics.py` y un supuesto nuevo para el precio de lanzamiento en
     `/admin/economia`.
   - Plantillas `site_precios.html`, `suscripcion.html` y `landing.html`.
   - `STRIPE_PRICE_*` en `config.py`.
   - Cifras fijadas en `tests/test_economics.py`.

   Las claves `pro` y `premium` se mantienen: solo cambian el nombre visible y el
   precio.
3. Web: pestañas Autónomos / Pymes / Empresas / Gestorías en `/precios`, con la tarifa
   tachada y el lanzamiento al lado.
4. Registrar la decisión en [[Decisiones]].

**Fase 2 (cuando se mida el soporte):** extras de trabajadores y pack de IA.

**Fase 3 (cuando existan roles):** Empresa 299 € y la pestaña Empresas completa.

## 9. Riesgos

- **Precio tachado.** Tiene que ser una tarifa real, publicada y aplicada al acabar
  la oferta. Para consumidores, la normativa española exige que el «precio anterior»
  sea el más bajo aplicado en los 30 días previos. Nuestros clientes son sobre todo
  empresarios, pero la Ley de Competencia Desleal también prohíbe las prácticas
  engañosas entre empresas. Por eso se habla de «precio de lanzamiento con fecha de
  fin» y no de «antes 39 €». **Pregunta para el abogado:** redacción exacta y si hace
  falta limitarlo por fecha o por número de clientes.
- **Comparación con Holded.** A tarifa somos más caros: 39 € frente a su Básico de
  29 €. El argumento no puede ser «hacemos lo mismo», sino «lo llevas desde WhatsApp
  y la gestoría lo recibe hecho».
- **El paso a tarifa al mes 13 puede provocar bajas.** Se mitiga avisando con 30 días,
  ofreciendo pasar al anual a precio de lanzamiento y midiendo las bajas de esa
  cohorte antes de quitar la oferta a las altas nuevas.
- **Todos los supuestos siguen sin medir:** bajas, soporte, mezcla y horas por alta.
  El documento compara catálogos con la misma vara. No predice ingresos.

## 10. Decisiones que te pido

1. ¿Tarifa +35 % (39 / 69 / 129, Empresa 299), +20 % / +55 %, o tachado de
   90 / 120 / 250 €? Si es la última, ¿se cobrará de verdad o pasamos a una
   comparación con el coste de las alternativas?
2. ¿Lanzamiento a precios de hoy, 12 meses, para las altas de los primeros 12 meses
   (o los primeros 100 clientes)?
3. ¿Voz fuera de Avanzado y como extra de 29 € cuando exista?
4. ¿Gestoría conectada gratis también en Autónomo?
5. ¿Unidad de equipo = trabajador (5 / 15 / 50), con extra de 5 €?
6. ¿Apruebas el plan de captación por etapas (medir → probar con 300–600 € →
   escalar) con sus reglas de corte, y construir antes el registro del origen de
   cada alta?
7. ¿Media jornada de soporte cuando el soporte llegue al 70 % de tus horas?

## Fuentes

- Holded, precios y comparativa: <https://www.holded.com/es/precios> (cuatro pestañas
  y selector anual), consultado el 09/10/2026.
- Bynoesis, precios publicados: <https://www.bynoesis.com/precios>, consultado el
  09/10/2026.
- Catálogo en código: `src/noesis/adapters/billing.py`. Motor económico:
  `src/noesis/economics.py`.
- Análisis previos: [[Unit-economics-y-cerebro-interno]],
  [[Canal-comercial-y-comisiones]], [[Escalado-de-Bynoesis]] y
  `Bynoesis-Modelo-Economico.xlsx`.
- CPC en España: [Dobleo, guía 2026](https://dobleo.com/blog/pago-por-click/coste-google-ads/),
  [Organik, guía 2026](https://www.organikmarketing.es/cuanto-cuesta-google-ads-espana/);
  Meta: [Adsuploader](https://adsuploader.com/es/blog/facebook-ads-cost),
  [Trendtrack](https://www.trendtrack.io/es/blog-post/inversion-publicitaria-meta-por-industria).
- Conversión de pruebas: [Userpilot](https://userpilot.com/blog/free-trial-conversion-rate/),
  [Shno, recopilación](https://www.shno.co/marketing-statistics/free-trial-conversion-statistics).
- Coste de la voz: Retell, 0,11 USD/min + 2 USD/mes por número, tarifa del 15/07/2026.
