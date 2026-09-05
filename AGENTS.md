# AGENTS.md - Manual del proyecto Bynoesis

Este archivo es la fuente de verdad compartida para cualquier agente de IA que
trabaje en el repositorio. Léelo entero antes de tocar nada. La visión y el contexto
están en `docs/`, empezando por [`docs/Inicio.md`](docs/Inicio.md).

> Si retomas trabajo, lee primero [`docs/project-state.json`](docs/project-state.json),
> [`docs/Estado-actual-main.md`](docs/Estado-actual-main.md) y
> [`docs/Tareas-vivas.md`](docs/Tareas-vivas.md). El JSON es la fuente verificable por
> máquinas; los otros dos explican el estado y los pendientes. Los traspasos son
> históricos.

> Si vas a tocar una pantalla, texto o estilo, lee antes
> [`docs/design/PRODUCT_PRINCIPLES.md`](docs/design/PRODUCT_PRINCIPLES.md),
> [`docs/design/DESIGN.md`](docs/design/DESIGN.md),
> [`docs/design/UX_COPY.md`](docs/design/UX_COPY.md) y
> [`docs/design/STYLE_TOKENS.json`](docs/design/STYLE_TOKENS.json). Bynoesis da el
> parte del día; no es un dashboard fintech.

## 1. Qué es Bynoesis

Copiloto de negocio por WhatsApp para autónomos de servicios: fontanería,
electricidad, reformas, limpieza, jardinería y similares. Gestiona agenda, clientes,
cobros, documentos, proyectos y facturas para quitar ruido mental. Detalle en
[`docs/Producto.md`](docs/Producto.md).

## 2. Cómo arrancar

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
noesis-web
```

- Demo comercial real: `python -m noesis.demo` crea un autónomo, una cartera de
  gestoría y un portal de cliente conectados y de solo lectura. Accesos y activación
  en [`docs/Demo-comercial.md`](docs/Demo-comercial.md).
- CLI de chat: `py -m noesis`.
- Sin proveedor de IA, el producto funciona con `nlu.py`. Un servicio privado se
  configura según [`docs/IA-local.md`](docs/IA-local.md); la IA externa requiere
  `ANTHROPIC_API_KEY` y consentimiento por negocio.
- Credenciales, callbacks y pruebas externas: [`docs/Conectar-APIs.md`](docs/Conectar-APIs.md).

## 3. Arquitectura resumida

```text
WhatsApp / Web / App
  -> reglas locales -> IA privada opcional -> IA externa autorizada
  -> tools.py -> db.py -> adapters/
```

Archivos clave:

- `src/noesis/db.py`: acceso único SQLite/Postgres; toda operación filtra por
  `business_id`.
- `src/noesis/migrations.py`: esquema versionado; la versión vigente se consulta en
  `docs/project-state.json` y se valida automáticamente contra el código.
- `src/noesis/web/server.py` y `src/noesis/web/routers/`: FastAPI por dominios.
- `src/noesis/web/static/` y `src/noesis/web/templates/`: sistema de diseño propio.
- `src/noesis/nlu.py`, `web/chat.py`, `agent.py`, `tools.py`: cerebro y acciones.
- `src/noesis/adapters/ai.py`: servicio privado OpenAI-compatible.
- `src/noesis/documents/`: documentos, OCR, revisión y gestoría.
- `src/noesis/adapters/`: integraciones externas reemplazables.

## 4. Reglas de oro

1. UI, textos y comentarios en español; imita los identificadores existentes.
2. Stdlib y ejecución local primero. Sin CDNs en runtime ni dependencias pesadas
   sin justificar coste total.
3. Rutinas y cálculos en local. Solo el contenido no resuelto puede llegar a un
   proveedor externo autorizado.
4. Toda lectura/escritura filtra por `business_id`; rutas `/b/` y `/api/` con sesión.
5. IVA 21/10/4/0 e IRPF. Total = base + IVA - IRPF. Ver `docs/Fiscalidad.md`.
6. Marca: `#14463b`, `#2e8b74`, `#f4f1e8`; usar variables de `app.css`.
7. Facturación, pagos, email, voz, IA y extracción detrás de adaptadores.
8. Bynoesis prepara; el autónomo confirma dinero, fiscalidad y acciones irreversibles.
9. Antes de cerrar: tests, servidor, páginas afectadas y estado documental.

## 5. Protocolo multi-agente y trazabilidad

- Decisión del founder (2026-07-20): después de fusionar el PR de consolidación,
  los agentes trabajan directamente sobre `main`, salvo que él pida expresamente
  una rama/PR. Antes de editar: `git switch main`, `git pull --ff-only` y árbol
  limpio. Nunca hacer force-push ni reescribir historia.
- `main` auto-despliega: una tarea, un objetivo y un commit pequeño; no hacer push
  si fallan las pruebas proporcionales al riesgo. No editar a la vez el mismo archivo
  desde dos agentes: con un único `main`, solo puede haber un escritor activo.
- Verificar `git branch --show-current` antes de operar con git.
- **Toda modificación** actualiza `docs/Registro-cambios.md` en el mismo commit:
  fecha, objetivo, áreas/archivos, pruebas, límites externos, riesgo y pista de
  diagnóstico/rollback. Es la bitácora cronológica para encontrar regresiones.
- Actualizar: estado en `docs/Estado-actual-main.md`, pendientes en
  `docs/Tareas-vivas.md`, código en `docs/Mapa-codigo.md`, QA en
  `docs/Registro-QA.md` y decisiones en `docs/Decisiones.md`.
- Todo cambio que afecte `src/noesis/` actualiza `docs/project-state.json` y
  `docs/Registro-QA.md`. CI lo exige con `scripts/check_project_truth.py`. Si cambia
  arquitectura, actualiza también `Mapa-codigo`, `Arquitectura` o `Decisiones`.
- No fijar aquí commits, PR abiertos, conteos de pruebas, precios ni migraciones:
  se desincronizan. Si una IA cambia producto, pruebas, esquema, precios o bloqueos
  externos, actualiza la foto compartida en la misma rama; no lo deja a otra IA.
- No subir `.env`, bases locales, uploads, `.venv/` ni worktrees auxiliares.

## 6. Reparto recomendado

| Área | Responsable sugerido |
|---|---|
| Seguridad, fiscalidad, integraciones, arquitectura, despliegue | Claude/Fable |
| Frontend, vistas, diseño, copy, refactors acotados, CI y QA | Codex |

Si cruza áreas, separar objetivos para evitar pisarse.

## 7. Estado actual

No duplicarlo aquí. Leer [`docs/project-state.json`](docs/project-state.json),
[`docs/Estado-actual-main.md`](docs/Estado-actual-main.md) y
[`docs/Tareas-vivas.md`](docs/Tareas-vivas.md). La comprobación automática impide
fusionar código sin actualizar la foto y el registro de QA.

## 8. Criterio heredable

El método está en [`docs/Metodo-operativo-Fable.md`](docs/Metodo-operativo-Fable.md).
Los traspasos usan [`docs/AI_HANDOFF_TEMPLATE.md`](docs/AI_HANDOFF_TEMPLATE.md) y
las dudas del founder viven en [`docs/Preguntas-abiertas.md`](docs/Preguntas-abiertas.md).
