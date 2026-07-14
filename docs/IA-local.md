# IA local y experiencia inteligente desde el primer día

## Decisión de producto

Noesis debe sentirse inteligente desde la primera sesión, sin quitar control al
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
  → servicio privado OpenAI-compatible, si está configurado
  → proveedor externo, si el negocio lo autorizó y conserva créditos
  → respuesta local honesta si los niveles avanzados no están disponibles
```

Una interacción resuelta por reglas o por IA privada no consume créditos externos.
La reserva del crédito externo se hace de forma atómica y aislada por
`business_id`, antes de crear la consulta avanzada.

## Servicio privado

Noesis no obliga a una marca de modelo. `src/noesis/adapters/ai.py` acepta el
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
