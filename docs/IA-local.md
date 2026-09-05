# IA local y experiencia inteligente desde el primer día

## Decisión de producto

Bynoesis debe sentirse inteligente desde la primera sesión, sin quitar control al
autónomo. El onboarding ofrece dos opciones explícitas:

1. **Experiencia completa (recomendada):** usa el cerebro interno y puede escalar a
   IA avanzada con un límite mensual.
2. **Solo cerebro local:** ninguna consulta se envía a un proveedor externo.

La preferencia puede cambiarse en Ajustes. Antes de elegir, la integración externa
permanece desactivada. El cerebro determinista nunca se apaga.

## Enrutamiento

```text
mensaje web o WhatsApp
  → reglas y cálculos de `nlu.py`
  → compositor interno trazable (`internal_brain.py`)
  → servicio privado OpenAI-compatible, si está configurado
  → proveedor externo OpenAI-compatible barato, si está autorizado
  → proveedor externo, si el negocio lo autorizó y conserva créditos
  → respuesta local honesta si los niveles avanzados no están disponibles
```

Una interacción resuelta por reglas o por IA privada no consume créditos externos.
Tampoco consume créditos un borrador resuelto por el compositor interno: cobros,
presupuestos, citas, gestoría y correos sencillos usan hechos de la base de datos.
Preparar nunca equivale a enviar; el WhatsApp del titular muestra el borrador y exige
SÍ/NO antes de entregar la comunicación.
La reserva del crédito externo se hace de forma atómica y aislada por
`business_id`, antes de crear la consulta avanzada. Si el proveedor compatible
falla y responde Anthropic, se usa la misma reserva: nunca dos créditos por el mismo
mensaje.

Si una herramienta de escritura pudo ejecutarse antes de la caída, Bynoesis detiene el
fallback y pide revisar la actividad reciente. Así evita que un segundo modelo cree
dos trabajos, gastos, facturas, presupuestos, proyectos o tareas iguales.

## Servicio privado

Bynoesis no obliga a una marca de modelo. `src/noesis/adapters/ai.py` acepta el
contrato `POST /v1/chat/completions` usado por Ollama, llama.cpp, vLLM y otros
servidores compatibles. Configuración:

```env
NOESIS_LOCAL_AI_BASE_URL=http://127.0.0.1:11434
NOESIS_LOCAL_AI_MODEL=modelo-instruct
NOESIS_LOCAL_AI_API_KEY=
NOESIS_LOCAL_AI_TIMEOUT_SECONDS=45
```

En producción el proceso web y el modelo pueden vivir en servicios distintos. El
endpoint debe estar en una red privada, con TLS o mTLS si cruza máquinas, sin
exposición pública innecesaria y con límites de CPU, RAM, concurrencia y tiempo.
Railway no convierte por sí solo este adaptador en un modelo alojado: hace falta
provisionar un servicio de inferencia y medir su coste total.

Para evaluación privada existe `deploy/local-ai/compose.yml`: levanta Ollama ligado
a `127.0.0.1` y descarga Qwen3 8B mediante un perfil explícito. No publica el puerto,
no incluye los pesos en la aplicación y debe fijar imagen/modelo antes del piloto.

## Proveedor compatible externo

El mismo contrato permite probar un modelo abierto servido por Groq, Cloudflare,
Hugging Face u otro proveedor sin añadir un SDK. Este nivel **no es privado** y
respeta el mismo consentimiento y límite que Anthropic.

```env
NOESIS_COMPAT_AI_BASE_URL=https://api.groq.com/openai/v1
NOESIS_COMPAT_AI_MODEL=qwen/qwen3-32b
NOESIS_COMPAT_AI_API_KEY=...
NOESIS_COMPAT_AI_PROVIDER=groq
NOESIS_COMPAT_AI_LEGAL_NAME=Groq, Inc.
NOESIS_COMPAT_AI_REGION=EE. UU. (cláusulas contractuales tipo)
NOESIS_COMPAT_AI_TIMEOUT_SECONDS=45
NOESIS_COMPAT_AI_INPUT_USD_PER_MTOK=0.29
NOESIS_COMPAT_AI_OUTPUT_USD_PER_MTOK=0.59
```

Los precios no están codificados como verdad permanente. Se declaran en entorno y
cada llamada registra proveedor, modelo, tokens, latencia y coste estimado. Cambiar
de modelo obliga a revisar las dos tarifas. El adaptador no se activa sin nombre
legal y región del subencargado; ambas aparecen en Privacidad y en el acuerdo de
encargo de tratamiento.

## Seguridad y autonomía

- El modelo solo propone llamadas a herramientas permitidas.
- El servidor valida nombre, argumentos, sesión, `business_id` y permisos.
- Las herramientas de emisión/envío de factura y registro de pago no se ofrecen al
  agente privado de forma automática.
- Transferencias, pagos, devoluciones, impuestos, emisiones definitivas, envíos
  sensibles y borrados irreversibles requieren confirmación específica.
- La memoria permanente es visible, corregible y confirmada; el historial no se
  convierte silenciosamente en una verdad.
- Los fallos registran proveedor, latencia y tipo de error, nunca credenciales ni
  contenido completo del usuario.

## Criterio económico

El modelo privado es una opción de infraestructura, no una promesa de coste cero.
Durante el piloto conviene comparar por cuenta:

- coste del proveedor externo y créditos consumidos;
- coste de CPU/GPU, memoria, almacenamiento y operación privada;
- latencia p50/p95, errores y correcciones;
- calidad de selección de herramientas en castellano y catalán;
- minutos de soporte evitados y tareas administrativas resueltas.

Se mantiene el proveedor externo como respaldo mientras el servicio privado no
iguale su fiabilidad en el corpus real del piloto. Cambiar el modelo no requiere
cambiar las herramientas ni la base de datos.

### Foto de costes revisada el 14-07-2026

Supuesto conservador por mensaje avanzado completo, sumando rondas de herramientas:
8.000 tokens de entrada y 1.200 de salida.

| Opción | Coste aproximado por mensaje | 75 / mes | 300 / mes | 1.500 / mes |
|---|---:|---:|---:|---:|
| Anthropic Haiku 4.5 | 0,014 USD | 1,05 USD | 4,20 USD | 21,00 USD |
| Groq Qwen3 32B | 0,003028 USD | 0,227 USD | 0,908 USD | 4,542 USD |
| Groq Llama 3.3 70B | 0,005668 USD | 0,425 USD | 1,700 USD | 8,502 USD |
| Cloudflare Qwen3 30B A3B | 0,000810 USD | 0,061 USD | 0,243 USD | 1,215 USD |

Fuentes oficiales: [Anthropic Haiku](https://www.anthropic.com/claude/haiku),
[Groq](https://groq.com/pricing),
[Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/platform/pricing/)
y [Runpod Serverless](https://www.runpod.io/product/serverless). No incluyen IVA,
cambio de divisa, soporte, audio, OCR ni operación.

Un servicio público gratuito no es una base de producción: Hugging Face concede
solo 0,10 USD mensuales a cuentas gratuitas y Groq/Cloudflare aplican cuotas que
pueden cambiar o cortar peticiones. Sirven para desarrollo y evaluación. El modelo
puede ser open source/open weights; el servidor de un tercero sigue teniendo coste,
límites y tratamiento de datos.

La referencia mínima de Runpod es 0,58 USD/h para 16 GB. Encendida 730 horas serían
unos 423,40 USD/mes: por coste puro no compensa frente a Haiku hasta unas 30.243
consultas avanzadas mensuales, y frente a Groq Qwen3 32B hasta unas 139.828. Un
endpoint serverless puede acercarse antes, pero añade arranque en frío, operación y
riesgo de calidad. Cálculo reproducible en [[Analisis-coste-IA.ipynb]].

### Decisión para el piloto

1. Reglas y cálculos locales siempre primero.
2. Servicio privado solo cuando exista infraestructura ya amortizada o un requisito
   de privacidad que lo justifique.
3. Proveedor compatible de pago por uso como primer respaldo barato.
4. Haiku como respaldo de fiabilidad, no como primera llamada.
5. No prometer un modelo hasta superar el corpus de herramientas, castellano,
   catalán, latencia, errores y correcciones.

## Alcance actual y siguiente validación

El adaptador privado cubre conversación y uso de herramientas. OCR, audio y visión
mantienen sus adaptadores y degradación local actuales; no se debe afirmar que un
modelo privado entiende imágenes o voz hasta validar el modelo concreto.

Antes de habilitarlo para clientes:

1. probar órdenes reales, ambigüedad, castellano/catalán y nombres parecidos;
2. medir aislamiento, timeouts, caída del servicio y fallback;
3. ejecutar una evaluación de herramientas sensibles y respuestas inventadas;
4. fijar modelo, versión, cuantización y capacidad por réplica;
5. monitorizar coste, latencia, uso de créditos y correcciones por negocio.
6. ejecutar `noesis-doctor --strict` y resolver bloqueos de configuración.

El modelo completo de precios, márgenes, escala y puntos de cruce está en
[[Unit-economics-y-cerebro-interno]] y [[Analisis-unit-economics.ipynb]].
