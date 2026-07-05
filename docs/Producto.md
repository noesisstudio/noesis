# Producto

## Qué es
**Noesis**: el copiloto de negocio por WhatsApp para autónomos de servicios. Hablas
con él por texto o audio y se ocupa de tu agenda, clientes, cobros y facturas, para
que tú solo tengas que hacer tu trabajo. Quita "ruido mental".

## Cliente objetivo
Autónomos y micro-pymes de servicios que trabajan mucho por WhatsApp, pierden
mensajes, se olvidan de facturar y cobran tarde:
fontaneros, electricistas, reformas, climatización, limpieza, jardinería,
mantenimiento, instaladores, talleres pequeños.

### Enfoque inicial
El público es **amplio**: autónomos y micro-pymes de servicios (1 a 10 personas).
El producto se construye alrededor de un **flujo repetible y medible** común a casi
todos ellos:
petición → presupuesto → agenda/trabajo → factura → cobro.

El piloto arranca con unos pocos negocios para validar retención y adquisición
rentable antes de escalar, **sin cerrarse a ningún sector**.

## Propuesta de valor (el hueco real)
No competir en "facturar por WhatsApp" (ahí está [[Competencia|Forjia]]), sino ser el
**copiloto proactivo** que orquesta todo y avisa solo:
agenda inteligente + control de cobros + **resumen diario** + facturación integrada.
Ver [[Investigación]] sobre por qué este es el hueco.

## Canales
- **WhatsApp** (principal, futuro): texto y audio.
- **Web/app**: dashboard de control + chatbot interno. Ver [[Arquitectura]].

## Modelo de negocio
SaaS de suscripción. Forjia ancla precio en 12,90 €/mes; Noesis justifica
**24-39 €/mes** por la capa proactiva + agenda. Coste interno ~5-8 €/usuario/mes.

### Precios calculados por costes y márgenes (unit economics)
Márgenes objetivo fijados por el fundador: **~90% en el básico, ~80% en el
medio y ~50% en el superior si el cliente lo usa al máximo** (el superior
incluye muchos créditos de IA). Precio = coste máximo / (1 − margen).

**Coste unitario de la IA** (stack actual: Claude Sonnet 4.6 a 3/15 $ por
millón de tokens entrada/salida, fallback Haiku 4.5 a 1/5 $, voz con Groq
Whisper ~0,04 $/hora; 1 $ ≈ 0,92 €):

| Acción (1 crédito) | Tokens típicos | Coste |
|---|---|---|
| Mensaje al agente (Sonnet) | ~2.000 entrada + 500 salida | ~1,2 c€ |
| Foto/PDF → gasto o factura | ~2.000 (imagen incl.) + 400 | ~1,4 c€ |
| Nota de voz 1 min (Groq) + agente | transcripción + llamada | ~1,3 c€ |
| Consulta rutinaria (NLU local) | 0 | 0 € |

Para calcular se usa **2 c€ por crédito** (colchón por retries, contexto
largo y picos). Coste fijo por usuario (infra Railway/Postgres, backups,
plantillas WhatsApp): **~1,5-2,5 €/mes**.

**Los tres planes** (coste si el cliente agota los créditos):

| Plan | Precio | Créditos IA/mes | Coste IA máx | Fijo | Coste total | Margen a tope de uso |
|---|---|---|---|---|---|---|
| Básico (Autónomo) | **29 €** | ~75 (≈2-3/día) | 1,50 € | 1,50 € | ~3,00 € | **~90%** |
| Medio (Negocio) | **39 €** | ~300 (≈10/día) | 6,00 € | 2,00 € | ~8,00 € | **~80%** |
| Superior (propuesta) | **59 €** | ~1.300 ("sin mirar el contador") | 26,00 € | 2,50 € | ~28,50 € | **~52%** |

Notas:
- El margen real será mayor: casi nadie agota los créditos, y lo rutinario se
  resuelve gratis con NLU local. El 50% del superior es el **suelo aceptado**:
  el cliente intensivo sigue siendo rentable y es el que más retiene.
- Si se quiere el superior exactamente al 50% con 1.500 créditos:
  coste máx ≈ 32,5 € → precio ≈ **65 €**. Entre 59 y 69 € es decisión de
  posicionamiento, no de coste.
- El margen se vigila en `/admin` (tokens por cuenta vs. plan). Una cuenta del
  básico que consume como el superior es señal de *upsell*, no de recorte.
- Palancas si el coste sube: enrutar más tráfico a Haiku (÷3 el coste del
  crédito), cachear el prompt del agente (lecturas a ~0,1×) y subir el umbral
  de lo que resuelve el NLU local.

## Activación y resultado principal
Una cuenta se considera **activada** cuando ha creado al menos un cliente, un trabajo
o presupuesto y una factura. El primer resultado completo llega al registrar el
cobro. El producto guía estos seis pasos:

1. Perfil del negocio completo.
2. WhatsApp conectado.
3. Primer cliente.
4. Primer trabajo o presupuesto.
5. Primera factura.
6. Primer cobro.

La métrica principal de producto es el porcentaje de cuentas que completa el ciclo
hasta el cobro; el tiempo hasta la primera factura es su indicador adelantado.
