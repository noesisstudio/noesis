# AGENTS.md — Manual del proyecto Noesis

Este archivo es la **fuente de verdad compartida** para cualquier agente de IA que
trabaje en este repositorio (Claude Code, Codex, etc.). Léelo entero antes de tocar
nada. La visión y el contexto completos están en el *vault* de Obsidian: **`docs/`**
(empieza por [`docs/Inicio.md`](docs/Inicio.md)).

> 🔄 **¿Retomas el trabajo (p. ej. continuando desde otro agente)?** Lee primero
> [`docs/Estado-traspaso-MVP.md`](docs/Estado-traspaso-MVP.md): dice qué está hecho,
> qué hay desplegado, qué falta para el MVP y qué tocar a continuación.

---

## 1. Qué es Noesis
Copiloto de negocio por WhatsApp para autónomos de servicios (fontaneros,
electricistas, reformas, limpieza, jardinería…). Gestiona agenda, clientes, cobros y
facturas para "quitar ruido mental". Detalle en `docs/Producto.md`.

## 2. Cómo arrancar
```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
pip install -e .
noesis-web                       # servidor web -> http://127.0.0.1:8000
```
- Login de demo: **demo@bynoesis.com / demo1234**.
- CLI de prueba (chat tipo WhatsApp): `py -m noesis`.
- La IA (Claude) es opcional: necesita `ANTHROPIC_API_KEY` en `.env`. Sin clave, el
  chat funciona igual con el cerebro local (`nlu.py`).

## 3. Arquitectura (resumen — detalle en `docs/Arquitectura.md`)
```
WhatsApp / Web / App  ─►  Cerebro (local nlu.py + IA opcional)  ─►  tools.py  ─►  db.py
                                                                       └─► adapters/ (Holded…)
```
Archivos clave (`src/noesis/`):
- `web/server.py` — FastAPI: páginas, API, login, onboarding, webhook.
- `web/static/app.css` · `app.js` — sistema de diseño propio + helpers JS.
- `web/templates/` — `base.html` (layout) + una plantilla por apartado.
- `nlu.py` — cerebro local por reglas. `web/chat.py` — orquestador local+IA.
- `tools.py` / `agent.py` — acciones y agente IA (multi-negocio).
- `db.py` — acceso único SQLite/Postgres. `migrations.py` — esquema versionado.
  `web/auth.py` — login/seguridad.
- `adapters/invoicing.py` — facturación (mock → Holded).

## 4. Reglas de oro (NO romper)
1. **Idioma:** UI, textos y comentarios en **español**. Identificadores de código en
   inglés/español como ya están; imita el estilo del archivo que edites.
2. **Mínimas dependencias externas.** Nada de librerías pesadas si se puede con la
   stdlib. Sin CDNs en runtime (Chart.js va servido en local).
3. **Privacidad/coste:** todo lo posible interno. Solo el LLM (si se activa) sale
   fuera. Lo rutinario se resuelve en local.
4. **Seguridad:** jamás romper el aislamiento por negocio. Toda consulta/escritura va
   filtrada por `business_id`. Las rutas `/b/` y `/api/` están protegidas por sesión.
5. **Fiscalidad correcta:** IVA (21/10/4) + IRPF. Total = base + IVA − IRPF. No
   inventar cálculos. Ver `docs/Fiscalidad.md`.
6. **Marca:** verde bosque `#14463b`, teal `#2e8b74`, crema `#f4f1e8`. Usa las
   variables CSS de `app.css`, no colores sueltos.
7. **Adaptadores:** integraciones externas (facturación, pagos) detrás de un
   adaptador, para cambiar de proveedor tocando un solo archivo.
8. **Verifica antes de cerrar:** arranca el servidor y comprueba que las páginas dan
   200 y los flujos funcionan. No entregues sin probar.

## 5. Protocolo multi-agente (trabajar dos sin pisarse)
- **Rama por agente.** No trabajéis sobre `main` directamente.
  - Claude: ramas `claude/<tarea>`.
  - Codex: ramas `codex/<tarea>`.
  - Se fusiona a `main` revisando el *diff*. Resolver conflictos antes de mezclar.
- **Áreas separadas.** No editar el mismo archivo a la vez (ver reparto abajo).
- **Una tarea = un objetivo claro.** Commits pequeños y descriptivos.
- **Actualizar la documentación** (`docs/` y este archivo) cuando cambie algo
  estructural, para que el otro agente herede el contexto.
- **No subir** `.env`, `noesis.db` ni `.venv/` (ya en `.gitignore`).

## 6. Reparto de trabajo recomendado
| Área | Responsable sugerido | Por qué |
|---|---|---|
| Seguridad, fiscalidad, integraciones (Holded/WhatsApp), arquitectura, despliegue | **Claude** | Tareas delicadas y de riesgo |
| Frontend/UI, nuevas vistas, pulido de diseño, textos, contenido | **Codex** | Tareas más visuales/mecánicas |

Si una tarea cruza ambas áreas, divídela en dos sub-tareas (una por agente) en vez de
editar los mismos archivos en paralelo.

## 7. Estado actual
Todo el trabajo de ambos agentes está **fusionado en `main`** (auditado el
2026-07-07): núcleo completo, equipo y fichaje inalterable, Veri*Factu fases 1 y 2
(migración 9), backups verificados, cobros parciales (11), gasto por foto (12),
recordatorios de cobro (13) y webhooks recuperables (16). Esquema en la migración
**16**, 126 tests verdes. GitHub Actions ejecuta tests y migraciones en cada PR y
push a `main`.
Siguiente: encender lo externo (claves IA/WhatsApp/Stripe, certificado AEAT),
pilotar con clientes reales y crecer por capas según `docs/Roadmap.md`.

## 8. Criterio heredable
El método de trabajo (cómo se prioriza, cómo se diseña, qué no hacer) está en
**`docs/Metodo-operativo-Fable.md`**. Todo traspaso entre modelos usa
**`docs/AI_HANDOFF_TEMPLATE.md`**. Las dudas pendientes del founder están en
`docs/Preguntas-abiertas.md`. Léelos antes de decidir nada estructural.
