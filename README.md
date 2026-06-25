# Noesis

El copiloto de negocio por WhatsApp para autónomos de servicios (fontaneros,
electricistas, reformas, limpieza, jardinería…). Hablas con Noesis por texto o
audio y se ocupa de tu agenda, clientes, cobros y facturas — para que tú solo
tengas que hacer tu trabajo.

> Estado actual: **prototipo local del cerebro**. Funciona en tu ordenador como
> un chat de prueba (simula WhatsApp). Más adelante enchufamos WhatsApp real y la
> facturación legal (Verifactu vía API de Holded/Quipu).

## Qué hace ya el prototipo

Le escribes en lenguaje natural, como en WhatsApp:

- "Agenda a Marta el jueves por la mañana en Badalona."
- "Haz factura a Carlos por reparación de caldera, 180 € más IVA."
- "¿Qué tengo pendiente hoy?"
- "¿Cuánto he facturado este mes?"
- "Recuérdame que Laura me debe la factura."

Y Noesis entiende, ejecuta y te responde como lo haría el asistente real.

## Arquitectura (modular a propósito)

```
WhatsApp / CLI  ─►  Agente (Claude)  ─►  Herramientas  ─►  Base de datos (SQLite)
                                            │
                                            └─►  Facturación (Mock hoy → Holded/Quipu mañana)
```

Cada pieza (agenda, cobros, clientes, facturación) es independiente. Hoy la
facturación es un "mock" (simulada); el día que conectemos Holded solo se cambia
un adaptador, sin tocar el resto.

| Carpeta | Qué es |
|---|---|
| `src/noesis/agent.py` | El cerebro: habla con Claude y decide qué hacer |
| `src/noesis/tools.py` | Las acciones que Noesis sabe ejecutar |
| `src/noesis/db.py` | Dónde se guardan clientes, trabajos, facturas, cobros |
| `src/noesis/adapters/invoicing.py` | Facturación (mock hoy → Holded mañana) |
| `src/noesis/cli.py` | El chat de prueba (simula WhatsApp) |
| `src/noesis/web/server.py` | Servidor web 24/7: dashboard + API + onboarding + webhook |
| `src/noesis/web/templates/` | Dashboard, alta de negocio y conexión de WhatsApp |
| `src/noesis/web/scheduler.py` | Alertas programadas (resumen diario y semanal) |
| `src/noesis/web/reports.py` | Informes descargables (CSV de costes y facturas) |

## Cómo arrancarlo (paso a paso, sin saber programar)

1. **Instala las dependencias** (una sola vez). Abre PowerShell en esta carpeta y ejecuta:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   ```

2. **Pon tu clave de Claude.** Copia `.env.example` a `.env` y dentro pega tu
   `ANTHROPIC_API_KEY` (se saca en https://console.anthropic.com → API Keys).

3. **Arranca el chat de prueba:**

   ```powershell
   py -m noesis
   ```

   Se carga con datos de demo (clientes y trabajos de ejemplo). Escribe como si
   fuera WhatsApp. Escribe `salir` para terminar y `resumen` para ver el parte del día.

## Cómo arrancar el panel web (dashboard 24/7)

Con el entorno ya instalado (`pip install -e .`):

```powershell
noesis-web
```

Abre el navegador en **http://127.0.0.1:8000**. Es una app **multipágina** con menú
lateral; cada apartado es una vista en profundidad:

- `/b/1/resumen` → visión general (lo importante primero).
- `/b/1/ingresos` · `/costes` · `/facturas` · `/cobros` → finanzas, cada una con sus
  métricas, gráficos y explicaciones.
- `/b/1/agenda` · `/clientes` → operativa.
- `/b/1/asistente` → **chatbot dentro de la web** (cerebro local gratis + IA opcional).
- `/b/1/ajustes` → negocio, WhatsApp, informes y privacidad.
- `/onboarding` → alta de un negocio nuevo + pasos para conectar su WhatsApp.

### Diseño y coste interno
- Sistema de diseño propio (`web/static/app.css`), **sin Tailwind ni CDNs**.
- Chart.js servido en local (`web/static/vendor/`): los gráficos no llaman a terceros.
- Chatbot **híbrido**: el cerebro local (`nlu.py`) resuelve los comandos frecuentes
  sin coste ni APIs; solo lo complejo usa IA (Claude) si hay `ANTHROPIC_API_KEY`.

Para producción 24/7 en un servidor:

```bash
uvicorn noesis.web.server:app --host 0.0.0.0 --port 8000
```

## Próximos pasos del roadmap

- [ ] v1: agenda + cobros + resumen diario proactivo (núcleo del prototipo)
- [ ] Conectar WhatsApp real (Meta Cloud API)
- [ ] Transcripción de audios (Whisper)
- [ ] Facturación legal vía Holded/Quipu API (Verifactu)
- [ ] Panel web
