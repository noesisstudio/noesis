# Canal comercial y comisiones — propuesta para aprobar

> Análisis · 16/09/2026 · importes mensuales sin IVA salvo indicación.
> **Nada de este documento está decidido.** La decisión
> [[Decisiones#La gestoría recibe borradores explicables, no impuestos «hechos» (2026-08-07)]]
> reserva al founder el descuento, el porcentaje, la duración, las devoluciones y la
> liquidación antes de prometer dinero a un despacho o a un comercial. Esto es la
> propuesta y su aritmética; la aprobación es un paso aparte.

Complementa a [[Unit-economics-y-cerebro-interno]], cuyos costes por plan se reutilizan
sin cambios. Modelo interactivo, con los supuestos editables:
https://claude.ai/artifact/TzMmpTQRpCoaAKFSXANSNt

## Qué le faltaba al modelo anterior

El análisis del 15/07/2026 es un buen modelo de **costes** y un modelo de **negocio**
incompleto. Calcula bien lo que cuesta servir una cuenta, pero deja fuera cuatro cosas
que deciden si el negocio existe:

1. **No hay bajas.** Sin churn no hay vida media del cliente y, por tanto, no hay LTV.
   Todas las cifras describen un cliente que se queda para siempre.
2. **No hay coste de adquisición.** El propio documento lo dice: «no incluye IVA ni CAC
   en el margen mensual». El 71,8 % de margen de contribución del plan Autónomo es el
   margen de un cliente que llega solo.
3. **No hay caja.** El break-even de 120 cuentas no dice cuántos meses cuesta llegar ni
   cuánto dinero hay que poner por el camino, que es la pregunta que de verdad limita.
4. **No hay canal.** El modelo asume un solo modo de vender —el founder— y por eso el
   opex es una constante de 3.500 €.

La corrección no toca los precios: 29/49/99 € + IVA sigue adoptado
([[Decisiones#Precio adoptado, prueba completa y después modo consulta (2026-07-15)]]).

## Punto de partida verificado

Reproduciendo el cálculo del notebook con la mezcla 55/35/10:

| Métrica | Valor |
|---|---:|
| Cuota media (ARPU) | 43,00 € |
| Contribución media por cuenta | 29,36 € |
| Break-even con 3.500 € de opex | 120 cuentas |

Coinciden con [[Unit-economics-y-cerebro-interno]], así que la capa nueva se apoya en la
anterior en lugar de sustituirla.

## Vida del cliente y LTV

| Bajas al mes | Vida media | LTV (contribución) | Payback con CAC 150 € |
|---:|---:|---:|---:|
| 2 % | 50,0 meses | 1.468 € | 5,1 meses |
| 3 % | 33,3 meses | 979 € | 5,1 meses |
| 5 % | 20,0 meses | 587 € | 5,1 meses |
| 8 % | 12,5 meses | 367 € | 5,1 meses |

El CAC de 150 € que ya figuraba como supuesto en el modelo editable aguanta bien salvo
con bajas altas. **Ninguna de estas filas es un dato**: no hay todavía clientes de pago
que permitan medir el churn real.

## Las cinco estructuras de comisión evaluadas

Con ARPU 43 €, contribución 29,36 € y 4 % de bajas (vida de 25 meses):

| Estructura | Pago al alta | Coste total por cliente | Se lleva | Recupera en | Gana a 10 altas/mes (mes 12) |
|---|---:|---:|---:|---:|---:|
| A · una mensualidad al alta | 43 € | 43 € | 6 % | 1,5 meses | 430 € |
| B · dos mensualidades al alta | 86 € | 86 € | 12 % | 2,9 meses | 860 € |
| C · 20 % recurrente de por vida | 0 € | 215 € | 29 % | inmediato | 1.049 € |
| **D · 1 mes + 10 % durante 12 meses** | **43 €** | **95 €** | **13 %** | **1,7 meses** | **830 €** |
| E · 2 meses + 5 % durante 12 meses | 86 € | 112 € | 15 % | 3,2 meses | 1.090 € |

La C es la más cara de todas por cliente y la más atractiva para el comercial; la A es la
más barata y la que peor alinea (cobra igual si el cliente dura un mes que si dura tres
años). La **D** paga pronto, mantiene el coste de canal en el 13 % de la contribución y
premia la permanencia.

## Los tres hallazgos que cambian la estrategia

### Un comercial a sueldo no sale, y no es cuestión de esforzarse más

Con 43 € de cuota media, pagar 2.400 € al mes de coste cargado exige **280 cuentas
activas** suyas si solo cobra un 20 % recurrente. A diez altas al mes son más de dos
años. La conclusión no es «vende más»: es que el canal de Bynoesis tiene que ser
**comisión pura, a tiempo parcial o por prescriptor**, no una nómina.

### El soporte pesa más que la infraestructura

En el plan Autónomo, el coste técnico es de 1,48 € y el tiempo de soporte y onboarding
de 5,00 €. El soporte cuesta más de tres veces lo que los servidores. Cada comercial que
cierra clientes llena la agenda de soporte del founder: **el canal no escala si el
soporte por cuenta no baja antes**. Ese es el argumento económico para seguir invirtiendo
en el cerebro interno y en la autoexplicación del producto.

### La cuota de implantación es la pieza que faltaba

Una cuota de 99 € al alta, bonificada si el cliente entra en plan anual, cubre la
comisión de la estructura D (43 €) y deja unos 53 € netos de caja el mismo mes de la
firma. Convierte la captación en **caja neutra o positiva**, que con cero clientes y sin
inversor es la diferencia entre poder pagar a diez comerciales y no poder pagar a uno.
También es coherente con lo que el modelo ya reconoce: el onboarding consume entre 30 y
120 minutos de founder que hoy se regalan.

## Propuesta concreta

1. **Comisión híbrida con devolución**: una mensualidad al alta más un 10 % durante doce
   meses. Si la cuenta se da de baja antes del cuarto mes, la mensualidad se descuenta de
   la siguiente liquidación.
2. **Cuota de implantación de 99 €**, perdonada en contratación anual.
3. **Comisión sobre cobro, no sobre alta**: se liquida mensualmente contra la factura que
   emite el comercial como autónomo, y solo de lo efectivamente cobrado por Stripe.
4. **Gestorías por tramos de volumen** en lugar de porcentaje individual: el despacho
   gana más por diez clientes que por uno y se negocia una vez, no veinte.
5. **Ningún comercial antes del piloto.** Sin churn medido, cualquier comisión se calcula
   sobre una vida de cliente inventada. Primero tres a cinco clientes de pago y treinta
   días de medición.

## Dos riesgos que hay que resolver antes de firmar

### Contrato de agencia e indemnización por clientela

Si el acuerdo funciona en la práctica como un **contrato de agencia** (Ley 12/1992), al
terminarlo el comercial puede reclamar indemnización por clientela por los clientes que
aportó y siguen activos. El nombre del encabezado no decide la calificación: la decide
cómo se ejecuta. Debe entrar en [[Preguntas-abogado-TIC]] antes de firmar con nadie.

### Hoy no se puede atribuir un alta a un comercial

No existe en `src/noesis/` ningún código de referido, campo de origen de la cuenta ni
liquidación por comercial. Sin eso, cualquier comisión se liquida a mano y sin prueba.
Lo mínimo para sostener el canal son tres piezas pequeñas: código de referido en el alta,
origen guardado en la cuenta y un informe mensual por comercial. **No construir hasta que
el founder apruebe la estructura**, para no implementar unas condiciones que luego
cambien.

## Qué debe responder el piloto

- ¿Cuál es el churn real a 30, 60 y 90 días, y cambia según el canal?
- ¿Cuántos minutos de soporte consume de verdad una cuenta nueva?
- ¿Acepta el mercado una cuota de implantación, o hay que bonificarla siempre?
- ¿Cuántas altas al mes cierra de verdad un comercial en este sector y a este precio?
