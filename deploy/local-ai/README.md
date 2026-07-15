# Servicio privado de IA para Noesis

Este despliegue levanta Ollama en `127.0.0.1:11434` y prepara Qwen3 8B. No
descarga pesos durante el build de la aplicación ni expone el modelo a Internet.
Está pensado para desarrollo, evaluación y una máquina privada con RAM suficiente;
no constituye por sí solo un SLA de producción.

## Arranque

```powershell
docker compose -f deploy/local-ai/compose.yml up -d ollama
docker compose -f deploy/local-ai/compose.yml --profile setup run --rm model-pull
```

Configuración de Noesis:

```env
NOESIS_LOCAL_AI_BASE_URL=http://127.0.0.1:11434
NOESIS_LOCAL_AI_MODEL=qwen3:8b
NOESIS_LOCAL_AI_API_KEY=
NOESIS_LOCAL_AI_TIMEOUT_SECONDS=45
```

Si Noesis y Ollama viven en contenedores distintos, usa la URL privada del servicio
en lugar de `127.0.0.1`. No publiques el puerto. Si cruza máquinas, usa una red
privada y TLS o mTLS.

## Capacidad y criterio de paso a producción

- Qwen3 8B cuantizado necesita normalmente varios GB de RAM/VRAM; CPU funciona,
  pero hay que medir latencia real en castellano y catalán.
- Empieza con una petición en paralelo. Sube concurrencia solo después de medir RAM,
  p50/p95, timeouts y correcciones.
- Fija una versión de imagen y el digest del modelo antes del piloto; `latest` solo
  facilita la evaluación inicial.
- Mantén Haiku como respaldo hasta que Qwen supere el corpus de herramientas y
  seguridad de Noesis.
- Un modelo abierto no hace gratis la infraestructura. Una GPU 16 GB encendida todo
  el mes ronda 423,40 USD con la referencia usada; a bajo volumen pagar por uso es
  mucho más barato.

## Qué resuelve sin el modelo

`src/noesis/internal_brain.py` redacta con datos confirmados recordatorios de cobro,
seguimientos de presupuesto, citas, comunicaciones con gestoría y correos sencillos.
No consume LLM y nunca envía en el mismo paso: el titular ve el borrador y confirma
por WhatsApp con SÍ o NO. Ollama se reserva para lenguaje libre que no cubre esa capa.
