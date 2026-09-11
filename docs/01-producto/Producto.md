# Producto

## Qué es
**Bynoesis**: el copiloto de negocio por WhatsApp para autónomos de servicios. Hablas
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

## Experiencia de producto
Bynoesis no se presenta como un panel financiero. La primera lectura siempre responde
en este orden: **qué está pasando, qué toca hacer y qué está resolviendo Bynoesis**.
Los datos avanzados siguen disponibles al entrar en cada apartado. La cuenta elige
en Ajustes si prefiere una explicación clara, directa o detallada; esa preferencia
se aplica al asistente completo, no mediante selectores repetidos en cada pantalla.

Los trabajos grandes viven en **Proyectos**: la portada solo muestra avance general,
presupuesto y costes. Al abrir uno aparecen margen, horas, materiales y equipo. Así
un profesional puede profundizar sin obligar al usuario no financiero a leer un ERP.

## Canales
- **WhatsApp** (principal): texto, audio, imágenes y documentos. El adaptador, el
  webhook y las colas están construidos; falta conectar y validar Meta real.
- **Web/app**: dashboard de control + chatbot interno. Ver [[Arquitectura]].

## Modelo de negocio
SaaS de suscripción. Bynoesis compite por quitar trabajo administrativo, no por ser el
facturador más barato. El catálogo adoptado es **29 / 49 / 99 € al mes + IVA**, con
75 / 300 / 1.500 créditos avanzados. La prueba completa dura 14 días; después la
cuenta queda en modo consulta hasta activar o recuperar la suscripción.

### Precios calculados por costes y márgenes

El modelo revisado separa COGS software, soporte, onboarding, infraestructura fija y
opex corporativo. En el escenario híbrido, la IA de texto cuesta menos que el
soporte y la voz: reglas y compositor interno primero, Qwen para la mayor parte del
fallback y Haiku como respaldo.

| Plan | Precio adoptado | Margen de contribución estimado |
|---|---:|---:|
| **Autónomo** | **29 € + IVA** | 71,8% |
| **Negocio** | **49 € + IVA** | 71,2% |
| **Premium** | **99 € + IVA** | 57,5% |

El código y la página de precios usan ya ese catálogo. Falta crear o actualizar los
productos reales de Stripe y validar checkout, webhook, impago y reactivación antes
de considerarlo publicado. La voz sigue siendo la principal sensibilidad de Premium.

Detalle, fuentes, escala y supuestos editables en
[[Unit-economics-y-cerebro-interno]] y [[Analisis-unit-economics.ipynb]].

**Reparto de módulos** (decidido 2026-07): equipo + fichaje + **gestoría
conectada** + análisis entran en Negocio (es lo que hace recomendable el plan
medio); el **recepcionista de llamadas 24/7** (100 min/mes incluidos, ver
`docs/01-producto/Recepcionista-llamadas.md`) es el gancho exclusivo de Premium, y
cuando salga de beta se ofrecerá como add-on de +15 €/mes en Negocio, de modo
que las llamadas se autofinancian y no rompen el margen del 80%.

Notas:
- El margen real depende del uso, soporte, voz y mix; no se presume que nadie agote
  créditos hasta medirlo.
- El margen se vigila en `/admin` (tokens por cuenta vs. plan). Una cuenta del
  básico que consume como el superior es señal de *upsell*, no de recorte.
- Palancas: ampliar el compositor interno, usar Qwen pago por uso, cachear contexto,
  limitar voz incluida y reservar Haiku para casos donde aporte calidad.

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
