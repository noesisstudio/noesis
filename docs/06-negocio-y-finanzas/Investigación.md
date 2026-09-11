# Investigación

Resumen de research aplicado al producto. Detalle de fuentes en el historial.

## Mercado
- WhatsApp es canal crítico en España (>90% uso diario). Ver [[Competencia]].
- Gremios quieren: facturar en segundos, móvil, flujo conectado
  presupuesto→cita→factura→cobro, **nada de mil herramientas**.

## Diseño (aplicado al dashboard)
- **Minimalismo estratégico** + *progressive disclosure*: el dato clave primero, el
  detalle al entrar en cada apartado. Ver [[Arquitectura]].
- **Barras > tarta** (se leen 3-4× más rápido).
- Sidebar + jerarquía F-pattern (lo valioso arriba-izquierda).

## Coste de IA / privacidad (clave para el founder)
- Por debajo de ~500M tokens/mes **NO compensa** auto-hospedar un LLM.
- Estrategia **híbrida**: cerebro local por reglas (gratis, interno) para lo
  rutinario; IA en la nube solo para lo complejo. Implementado en `nlu.py`.
  Ver [[Decisiones]] y [[Arquitectura]].

## Fiscal
- Verifactu obligatorio para autónomos desde **1-jul-2027** (retrasado) → ola de
  adopción a favor. Detalle en [[Fiscalidad]].
