# Plantilla de traspaso entre modelos (AI Handoff)

> Copia esta plantilla para cada traspaso (Fable→Codex, Fable→Opus, Codex→Fable…).
> El handoff debe poder leerse **sin acceso a la conversación que lo originó**.
> Guárdalo como `docs/08-agentes-ia/handoffs/AAAA-MM-DD-<tarea>.md` o como descripción del PR.
> Contexto general del método: [[Metodo-operativo-Fable]].

---

## Traspaso: <título corto de la tarea>

- **De → para:** <modelo que entrega> → <modelo que recibe>
- **Fecha:** AAAA-MM-DD
- **Git:** `main` actualizado y limpio, o rama/PR si el founder la pidió
- **Nivel de confianza del que entrega:** alto / medio / bajo — <por qué>
- **¿Requiere revisión antes de implementar?** sí / no — <de quién>

### 1. Contexto del producto (2-4 líneas)
<Qué es Bynoesis y qué papel juega esta tarea en el ciclo trabajo→factura→cobro→gestoría.
No repitas los docs: enlaza [[Producto]] / [[Arquitectura]] y di solo lo específico.>

### 2. Objetivo de la tarea
<Una frase con el resultado observable. Si no cabe en una frase, son dos tareas.>

### 3. Estado actual
- Qué funciona ya: <…>
- Qué está a medias: <…>
- Qué NO existe aún (no asumir): <…>

### 4. Decisiones tomadas (con porqué)
- <decisión> — <motivo>. Registrada en [[Decisiones]]: sí/no.

### 5. Decisiones pendientes
- PREGUNTA / DECISIÓN PENDIENTE: <qué falta decidir y quién decide (founder/Opus)>.

### 6. Mapa de la tarea
- **Archivos relevantes:** <rutas exactas>
- **Entidades/tablas implicadas:** <tablas y si la migración es aditiva o estructural>
- **Rutas web afectadas:** <GET/POST …>
- **Servicios a reutilizar (no reinventar):** <p. ej. `documents/service.py`, `adapters/…`>

### 7. Riesgos y qué NO hacer
- No tocar: <tablas append-only, auth, …>
- Riesgo principal: <…>
- Si aparece <situación>, parar y preguntar.

### 8. Criterios de aceptación
- [ ] <criterio verificable 1>
- [ ] <criterio verificable 2>
- [ ] Tests verdes: `python -m unittest discover -s tests`
- [ ] Aislamiento por `business_id` verificado en toda consulta nueva
- [ ] Estados vacío/cargando/error en la UI afectada
- [ ] Servidor arrancado y páginas afectadas en 200

### 9. Pruebas mínimas
<Qué test añadir/ejecutar y qué flujo manual recorrer antes de cerrar.>

### 10. Próximo paso recomendado
<El primer movimiento concreto que haría el que entrega si continuara él.>

### 11. Preguntas para el founder
<Solo las que bloquean. Si no bloquean, van a [[Preguntas-abiertas]].>
