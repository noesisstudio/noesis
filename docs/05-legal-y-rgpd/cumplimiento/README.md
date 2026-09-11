# Cumplimiento — datos, servidores, copias y RGPD

Carpeta de cumplimiento de Noesis. Documenta **dónde vive cada dato, en qué
infraestructura, cómo se copia y qué obligaciones europeas lo condicionan**.

Se generó el 2026-09-08 ejecutando
[`docs/08-agentes-ia/prompts/Prompt-Seguridad-Datos-UE`](../../08-agentes-ia/prompts/Prompt-Seguridad-Datos-UE.md)
sobre el repositorio. No es una plantilla genérica: cada documento se apoya en lo
que hay implementado en `src/noesis/` a esa fecha.

> Trabajo de ingeniería, no dictamen jurídico. La revisión por abogado
> especializado, la firma de los DPA y el pentest independiente siguen pendientes
> y son requisito antes de tratar datos reales de terceros a escala.

## Por dónde empezar

1. [`Plan-Datos-Servidores-Copias`](Plan-Datos-Servidores-Copias.md) — **entrada
   principal**: dónde se guarda cada dato, qué servidores, cómo son las copias,
   riesgos residuales y plan de ejecución por prioridades.
2. [`Analisis-riesgos-y-EIPD`](Analisis-riesgos-y-EIPD.md) — qué puede salir mal y
   qué queda sin cubrir.
3. [`Continuidad-RPO-RTO`](Continuidad-RPO-RTO.md) — qué hacer cuando ya ha salido mal.

## Índice

| Documento | Para qué | Revisión |
|---|---|---|
| [Plan-Datos-Servidores-Copias](Plan-Datos-Servidores-Copias.md) | Diseño de almacenamiento, infraestructura y copias | Trimestral |
| [RAT-Registro-actividades](RAT-Registro-actividades.md) | Registro del art. 30, como responsable y como encargado | Semestral |
| [Politica-de-retencion](Politica-de-retencion.md) | Cuánto se guarda cada cosa y cómo se borra | Semestral |
| [Subencargados-y-transferencias](Subencargados-y-transferencias.md) | Proveedores, DPA y transferencias fuera del EEE | Trimestral |
| [Analisis-riesgos-y-EIPD](Analisis-riesgos-y-EIPD.md) | Riesgos y cribado del art. 35 | Semestral |
| [Procedimiento-brechas](Procedimiento-brechas.md) | Las 72 horas, paso a paso | Semestral |
| [Derechos-de-los-interesados](Derechos-de-los-interesados.md) | Quién responde a quién y en qué plazo | Semestral |
| [Continuidad-RPO-RTO](Continuidad-RPO-RTO.md) | Runbooks de recuperación | Trimestral |
| [Registro-de-evidencias](Registro-de-evidencias.md) | Prueba de que los controles se ejecutan | Continua |

### Plantillas

| Plantilla | Cuándo se usa |
|---|---|
| [Notificacion-brecha-AEPD](plantillas/Notificacion-brecha-AEPD.md) | Al notificar una brecha |
| [Respuesta-derechos](plantillas/Respuesta-derechos.md) | Al contestar un derecho |
| [Registro-simulacro-restauracion](plantillas/Registro-simulacro-restauracion.md) | En cada simulacro trimestral |
| [Alta-subencargado](plantillas/Alta-subencargado.md) | Antes de conectar un proveedor |

## Relación con el resto de la documentación

- `docs/04-seguridad-y-datos/Seguridad-operativa.md` — amenazas y controles técnicos del producto. Esta
  carpeta no lo duplica: lo complementa con la parte de datos, infraestructura y
  obligaciones legales.
- `docs/02-tecnico/Despliegue.md` — cómo se despliega hoy.
- `docs/05-legal-y-rgpd/Fiscalidad.md` — Veri*Factu y obligaciones de facturación.
- `web/templates/privacidad.html`, `terminos.html`, `cookies.html` y
  `encargado-tratamiento.html` — lo que ve el cliente. **Si cambia un subencargado
  o una retención aquí, hay que cambiarlo también ahí**, o el cliente podrá alegar
  que no fue informado.

## Mantenimiento

`python scripts/check_cumplimiento.py` comprueba que la estructura está completa y
que ningún documento lleva más tiempo del previsto sin revisar. Es una comprobación
de higiene documental, no de cumplimiento real.

Cada revisión se anota en [`Registro-de-evidencias`](Registro-de-evidencias.md).
