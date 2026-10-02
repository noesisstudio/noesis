# Guías por área

Una guía por cada apartado del [mapa visual](../02-tecnico/Mapa-Bynoesis.html). Existen
para que quien revise o cambie código (una persona, Claude o Codex) sepa en dos
minutos qué hace esa zona, qué archivos la forman, qué reglas no se pueden romper y
qué mirar antes de dar un cambio por bueno.

## Cuándo leer cuál

| Si tocas o revisas… | Lee |
|---|---|
| Financial Core, dinero exacto y repositorios financieros | [08 · Financial Core](08-financial-core.md) |
| Algo que cruza varias zonas, o no sabes por dónde empezar | [01 · Visión general](01-vision-general.md) |
| Una pantalla, un portal, `/admin` o la web pública | [02 · Ramas de la empresa](02-ramas-de-la-empresa.md) |
| `web/chat.py`, `nlu.py`, `agent.py`, `tools.py`, `action_review.py`, WhatsApp de entrada, voz | [03 · Cerebro](03-cerebro.md) |
| Facturas, presupuestos, cobros, series, Veri*Factu, PDF, impuestos | [04 · Facturas](04-facturas.md) |
| `adapters/email.py`, `adapters/google_mail.py`, `documents/inbound_email.py`, cola de correo | [05 · Correo](05-correo.md) |
| Datos personales, bajas, exportación, consentimientos, seguridad, proveedores | [06 · RGPD y seguridad](06-rgpd-y-seguridad.md) |
| `web/scheduler.py`, colas, copias de seguridad, tareas nocturnas | [07 · Lo automático](07-lo-automatico.md) |

La tabla completa de carpeta → guía está en [`AGENTS.md`](../../AGENTS.md#guías-por-área).

## Cómo están escritas

Todas siguen el mismo orden, para poder saltar directo a lo que se busca:

1. **Qué hace**: el apartado en pocas frases.
2. **Esquema**: el recorrido real, en texto.
3. **Archivos clave**: dónde está cada responsabilidad.
4. **Reglas que no se rompen**: invariantes. Si un cambio contradice una, está mal
   el cambio o hay que decidirlo de forma explícita en [`Decisiones`](../Decisiones.md).
5. **Estado real**: qué funciona en producción y qué no, con fecha.
6. **Pruebas que lo cubren**: por dónde empezar a ejecutar.
7. **Al revisar código de esta zona**: la lista de comprobación.
8. **Dudas frecuentes** y **más detalle**.

## Cómo mantenerlas

- Si un cambio contradice una guía, **actualiza la guía en el mismo commit**. Una
  guía desfasada es peor que ninguna: hace creer que algo funciona como ya no lo hace.
- Las guías describen **cómo funciona**, no el historial. Lo que cambió y cuándo va
  en [`Registro-cambios`](../Registro-cambios.md); las cifras vivas (pruebas,
  esquema, precios) en [`project-state.json`](../project-state.json). No se copian
  aquí porque se desincronizan.
- El «Estado real» sí lleva fecha: al tocarlo, cambia la fecha.
