# Traspaso: columna operativa y control de autonomía

- **De → para:** Codex → siguiente agente/revisor
- **Fecha:** 2026-07-13
- **Rama:** `codex/operating-spine`
- **Confianza:** alta en lógica interna; media en conexiones externas no probadas.
- **Requiere revisión:** sí, especialmente migraciones Postgres y alcance fiscal.

## 1. Contexto

Noesis quita ruido mental a autónomos de servicios. Esta rama une el ciclo
proyecto → trabajo → fichaje/coste → documento/gasto → factura/cobro → gestoría y
aplica el principio de que el usuario conserva la última palabra.

## 2. Resultado observable

El autónomo ve una lectura sencilla y puede abrir el detalle; el trabajador recibe
su parte y registra ejecución; la gestoría descarga un archivo trazable; Noesis
acompaña y propone sin poder mover dinero ni presentar obligaciones por sí solo.

## 3. Qué funciona

- Centro de control y registro de acciones.
- Proyectos con trabajos, equipo, fichajes, tareas, gastos y documentos vinculados.
- Coste laboral real y avisos de desviación explicables.
- Portal y WhatsApp del trabajador.
- Cerebro local ampliado y contexto IA con permisos efectivos.
- Gestoría versionada con originales, manifiesto y eventos.

## 4. Qué no existe todavía

- Transferencias bancarias reales: deliberadamente no se implementan sin adaptador
  y confirmación puntual.
- Validación real de Meta, Stripe, IA externa o AEAT.
- Certificación legal/fiscal: los cálculos internos no sustituyen revisión profesional.

## 5. Decisiones

- Las acciones críticas solo admiten `confirm` o `blocked`.
- Recordatorios y gestoría pueden usar `rules` cuando el usuario guarda una cadencia.
- Un cambio de contacto de gestoría no reabre un permiso restringido.
- Las tareas sin asignar solo son operables por miembros del proyecto.

## 6. Mapa técnico

- Migraciones: 22 `control_autonomia`, 23 `columna_operativa`, 24
  `entregas_gestoria`.
- Núcleo: `db.py`, `tools.py`, `nlu.py`, `agent.py`.
- Web: routers `assistant`, `projects`, `portal`, `documents`, `gestoria`.
- Canales: `web/chat.py`, `web/whatsapp.py`, `web/scheduler.py`.
- UI: `ajustes.html`, `proyectos.html`, `agenda.html`, `documentos.html`,
  `costes.html`, `fichaje.html`, `app.css`.

## 7. Riesgos

- No relajar `allowed_modes` de acciones críticas.
- No contar a la vez horas manuales y fichajes para el mismo coste real.
- No eliminar filtros `business_id` ni triggers/FK compuestas.
- No describir la rama como desplegada hasta verificar Railway después del merge.

## 8. Aceptación

- [x] Aislamiento multiempresa probado en los nuevos vínculos.
- [x] Estados vacíos y detalle progresivo en UI.
- [x] Páginas afectadas en 200 y sin errores de consola.
- [x] Confirmación humana en documentos y acciones críticas.
- [x] Suite completa final: 170 pruebas y 26 subpruebas.
- [ ] Revisión y smoke test Postgres/Railway.

## 9. Próximo paso

Ejecutar suite completa, revisar el diff, hacer commits pequeños, push y PR. Tras el
merge, comprobar migraciones 22-24 y salud del despliegue antes de iniciar el piloto.
