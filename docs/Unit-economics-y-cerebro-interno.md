# Cerebro interno y unit economics de Noesis

> Análisis ejecutivo · 15/07/2026 · importes mensuales sin IVA salvo indicación.

## Resumen ejecutivo

- **Sí conviene construir inteligencia interna; no conviene entrenar un modelo
  fundacional.** Noesis puede resolver hechos, cálculos, clasificación y redacción
  repetible con código propio; Qwen local o compatible cubre lenguaje libre y Haiku
  queda como respaldo de calidad.
- **La IA de texto no amenaza el margen en el piloto.** En el escenario híbrido, su
  coste esperado es de unos 0,05 / 0,22 / 0,69 € por cuenta y mes. Pesan más el
  soporte y los 100 minutos de voz del plan superior.
- **Precio adoptado: 29 / 49 / 99 € + IVA.** El plan Autónomo se mantiene.
  Negocio necesita más distancia por el soporte y valor que incluye. Sin Límites
  necesita 99 € si conserva 100 minutos de voz; alternativa: 79 € sin voz y add-on
  de voz de al menos 15 €.
- Con un mix 55% / 35% / 10% y 3.500 € de opex fijo supuesto, el break-even baja de
  unas **146 cuentas** con el catálogo anterior a **120 cuentas** con el adoptado.
  No es una previsión: es un escenario que el piloto debe recalibrar.

## Qué se ha construido

El servicio interno no es un chatbot paralelo. Se integra delante de la IA externa
y usa los mismos datos, permisos, adaptadores y auditoría de Noesis:

```text
mensaje web / WhatsApp
  → hechos, cálculos y NLU local
  → compositor interno trazable
  → Qwen privado, si está disponible
  → Qwen compatible externo, si existe consentimiento
  → Haiku como respaldo, dentro del límite del plan
```

El compositor cubre por ahora:

- recordatorio de factura pendiente con importe, número y portal reales;
- seguimiento de presupuesto enviado;
- confirmación o recordatorio de cita;
- acceso documental de la gestoría;
- correo sencillo a un cliente con el contenido indicado por el titular;
- español, catalán e inglés según la preferencia de cuenta.

La redacción nunca elige una deuda, presupuesto o cita ambigua. Todo dato se vuelve a
consultar con `business_id` al confirmar. En web prepara; en el WhatsApp del titular
crea una acción pendiente durante dos horas y solo envía tras recibir **SÍ**. Los
WhatsApp proactivos usan plantillas aprobadas: el modelo no puede saltarse la regla
de Meta ni inventar consentimiento.

## Economía por plan

Escenario base: 60% de las interacciones avanzadas resueltas internamente; del resto,
80% en Qwen y 20% en Haiku. Incluye Stripe, WhatsApp utility, IA, transcripción,
extracción, almacenamiento, voz, soporte, onboarding amortizado y 0,65 € de fijo por
cuenta. No incluye IVA ni CAC en el margen mensual.

| Plan | Precio anterior | COGS software | Margen bruto | Contribución | Margen contribución |
|---|---:|---:|---:|---:|---:|
| Autónomo | 29 € | 1,48 € | 94,9% | 20,83 € | 71,8% |
| Negocio | 39 € | 2,82 € | 92,8% | 25,11 € | 64,4% |
| Sin Límites | 79 € | 18,03 € | 77,2% | 37,40 € | 47,3% |

| Plan | Precio adoptado | COGS software | Margen bruto | Contribución | Margen contribución |
|---|---:|---:|---:|---:|---:|
| Autónomo | 29 € | 1,48 € | 94,9% | 20,83 € | 71,8% |
| Negocio | 49 € | 3,04 € | 93,8% | 34,89 € | 71,2% |
| Sin Límites | 99 € | 18,47 € | 81,3% | 56,96 € | 57,5% |

Si el catálogo anterior 29 / 39 / 79 € hubiera incluido IVA, el ingreso neto sería
23,97 / 32,23 / 65,29 €. Por tanto, precios, checkout y facturas deben comunicar de
forma inequívoca **«+ IVA»** o recalcular el catálogo.

## Escala mensual

| Cuentas | Ingreso anterior | Resultado tras 3.500 € opex | Ingreso adoptado | Resultado adoptado |
|---:|---:|---:|---:|---:|
| 10 | 375 € | -3.260 € | 430 € | -3.206 € |
| 50 | 1.875 € | -2.301 € | 2.150 € | -2.032 € |
| 100 | 3.750 € | -1.102 € | 4.300 € | -564 € |
| 500 | 18.750 € | 8.492 € | 21.500 € | 11.181 € |

El opex de 3.500 € es una hipótesis de planificación para cubrir founder, soporte
estructural, legal/gestoría, herramientas y una reserva de desarrollo. No es el gasto
contable actual. El modelo editable permite cambiarlo.

## Cuándo compensa alojar un modelo

Con 8.000 tokens de entrada y 1.200 de salida por interacción avanzada:

| Opción | Coste aproximado/interacción | 75/mes | 300/mes | 1.500/mes |
|---|---:|---:|---:|---:|
| Cerebro determinista Noesis | ~0 € | 0 € | 0 € | 0 € |
| Cloudflare Qwen3 30B A3B | 0,0007 € | 0,05 € | 0,21 € | 1,07 € |
| Groq Qwen3 32B | 0,0027 € | 0,20 € | 0,80 € | 3,98 € |
| Anthropic Haiku 4.5 | 0,0123 € | 0,92 € | 3,68 € | 18,41 € |

Una GPU de 16 GB a 0,58 USD/h encendida 730 horas cuesta 423,40 USD, unos 371 € al
cambio usado. Por coste puro, cruza Haiku alrededor de 30.243 interacciones/mes y
Groq Qwen cerca de 139.828. Antes de ese volumen, el servicio interno determinista
más pago por uso es normalmente más barato y requiere menos operación.

No hay un «servidor público gratuito» adecuado como núcleo de producción: los tiers
gratis pueden cambiar, limitar concurrencia, cortar solicitudes y tratar datos fuera
de Noesis. Sirven para desarrollo, no para una promesa fiable a clientes. El modelo
open source evita licencia por token; no elimina cómputo, seguridad ni mantenimiento.

## Recomendación operativa

1. Pilotar el compositor interno y medir qué porcentaje resuelve sin modelo.
2. Levantar Qwen3 8B con `deploy/local-ai/compose.yml` para el corpus de evaluación,
   no todavía como única IA de producción.
3. Mantener un proveedor compatible barato y Haiku como respaldo hasta superar
   calidad, latencia, aislamiento y caída controlada.
4. Publicar el catálogo como 29 / 49 / 99 € + IVA solo después de validar con 3-5
   clientes; mantener 39 y 79 como precio fundador si se quiere proteger el piloto.
5. Revisar a los 30 días: mensajes utility, minutos de soporte, voz consumida,
   documentos, llamadas de IA, correcciones y margen por cuenta.

## Preguntas que el piloto debe responder

- ¿El 60% de resolución interna es real o debe ser 40%/80%?
- ¿Cuántos minutos de soporte consume cada plan durante los primeros 90 días?
- ¿Premium utiliza realmente 100 minutos de voz o conviene venderlos como add-on?
- ¿Qué CAC y churn aparecen por canal y sector?
- ¿Qwen3 8B alcanza la calidad necesaria en catalán, herramientas y ambigüedad?

## Fuentes y cautelas

Tarifas consultadas el 15/07/2026: [Stripe España](https://stripe.com/es/pricing),
[Anthropic Haiku](https://www.anthropic.com/claude/haiku),
[Railway](https://docs.railway.com/pricing),
[Resend](https://resend.com/docs/knowledge-base/what-is-resend-pricing),
[WhatsApp Business](https://whatsappbusiness.com/products/platform-pricing/),
[ECB](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html),
[Retell](https://www.retellai.com/pricing),
[Groq Speech-to-Text](https://console.groq.com/docs/speech-to-text),
[Runpod](https://www.runpod.io/product/serverless) y
[Qwen3](https://github.com/QwenLM/Qwen3). La tarifa utility de WhatsApp España
usa además una rate card publicada por un tercero porque la tabla oficial dinámica
no expuso directamente el valor durante la consulta. Las tarifas pueden cambiar y
no siempre incluyen impuestos.

El cálculo reproducible está en [[Analisis-unit-economics.ipynb]] y el modelo
editable se genera con `analysis/build_unit_economics.mjs`.
