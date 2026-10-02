# AGENTS.md - Manual del proyecto Bynoesis

> Para Financial Core, leer [gobernanza y ADR](docs/architecture/README.md) y
> [guía 08](docs/areas/08-financial-core.md). Fase 0 cerrada; Fase 1
> planificada y aprobada como referencia. 1.1 aceptada; 1.2 (operaciones y autorización durable) cerrada. Ninguna unidad posterior autorizada.
> Leer [plan](docs/architecture/FASE-1-plan.md) y
> [contrato v1](docs/architecture/ECONOMIC-EVENTS-v1.md),
> [operaciones](docs/architecture/FINANCIAL-OPERATIONS-v1.md) y ADR-006. No avanzar a 1.3.
> Las referencias no autorizan ejecutar otras unidades.

## Contrato del Financial Core

- Monolito modular: servicios y repositorios especializados por dominio; conexión,
  pool y transacciones compartidos mediante `db.get_conn()` y `FinancialSession`.
- Prohibida nueva lógica financiera grande dentro de `db.py`: únicamente cambios
  acotados de infraestructura o mantenimiento legacy. Nada de nuevos pools/ORM.
- `Decimal/NUMERIC` es el contrato del núcleo; SQLite usa TEXT decimal canónico
  para preservar exactitud. No pasar por normalización legacy a float ni usar
  REAL, SUM/CAST binarios o JSON numérico para importes nuevos.
- La IA propone; no autoriza, contabiliza, liquida ni cambia reglas financieras.
  El servicio valida permisos, aprobación, invariantes e idempotencia.
- Economic Events son hechos financieros, no un log genérico. `quote.accepted`
  y `job.completed` son operativos; solo una regla explícita posterior puede
  producir una obligación o reconocimiento diferente y trazable.

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

> **Antes de revisar o cambiar código, lee la guía de su área** en
> [`docs/areas/`](docs/areas/README.md) (tabla en [§3](#guías-por-área)). Cada una dice
> qué archivos forman la zona, qué reglas no se pueden romper y qué comprobar al
> revisar. Si tu cambio contradice una guía, actualiza la guía en el mismo commit.

## 1. Qué es Bynoesis

Copiloto de negocio por WhatsApp para autónomos de servicios: fontanería,
electricidad, reformas, limpieza, jardinería y similares. Gestiona agenda, clientes,
cobros, documentos, proyectos y facturas para quitar ruido mental. Detalle en
[`docs/01-producto/Producto.md`](docs/01-producto/Producto.md).

## 2. Cómo arrancar

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
noesis-web
```

- Demo comercial real: `python -m noesis.demo` crea un autónomo, una cartera de
  gestoría y un portal de cliente conectados y de solo lectura. Accesos y activación
  en [`docs/01-producto/Demo-comercial.md`](docs/01-producto/Demo-comercial.md).
- CLI de chat: `py -m noesis`.
- Sin proveedor de IA, el producto funciona con `nlu.py`. Un servicio privado se
  configura según [`docs/02-tecnico/IA-local.md`](docs/02-tecnico/IA-local.md); la IA externa requiere
  `ANTHROPIC_API_KEY` y consentimiento por negocio.
- Credenciales, callbacks y pruebas externas: [`docs/03-whatsapp-e-integraciones/Conectar-APIs.md`](docs/03-whatsapp-e-integraciones/Conectar-APIs.md).

## 3. Arquitectura resumida

```text
WhatsApp / Web / App
  -> reglas locales -> IA privada opcional -> IA externa autorizada
  -> tools.py -> db.py -> adapters/
```

Archivos clave:

- `src/noesis/db.py`: infraestructura compartida SQLite/Postgres y acceso legacy;
  los repositorios especializados reciben la misma conexión/transacción. Toda
  operación de negocio filtra por `business_id`.
- `src/noesis/migrations.py`: esquema versionado; la versión vigente se consulta en
  `docs/project-state.json` y se valida automáticamente contra el código.
- `src/noesis/web/server.py` y `src/noesis/web/routers/`: FastAPI por dominios.
- `src/noesis/web/static/` y `src/noesis/web/templates/`: sistema de diseño propio.
- `src/noesis/nlu.py`, `web/chat.py`, `agent.py`, `tools.py`: cerebro y acciones.
- `src/noesis/adapters/ai.py`: servicio privado OpenAI-compatible.
- `src/noesis/documents/`: documentos, OCR, revisión y gestoría.
- `src/noesis/adapters/`: integraciones externas reemplazables.
- `facebook/`: automatización que promociona Noesis en Facebook y
  publica sola cada 3 días. No es producto, no se despliega y no importa nada de
  `src/noesis/`; su manual es `facebook/README.md`.

### Guías por área

Siguen el [mapa visual](docs/02-tecnico/Mapa-Bynoesis.html). Léela antes de revisar
o cambiar algo de esa zona; si el cambio la contradice, actualízala en el mismo commit.

| Si el cambio toca… | Guía |
|---|---|
| Financial Core, `core/`, `economic_events/`, `financial_operations/`, `accounting/`, exactitud y repositorios financieros | [08 · Financial Core](docs/areas/08-financial-core.md) |
| Varias zonas, `web/server.py`, `web/deps.py`, `db.py` en general, `migrations.py`, `config.py` | [01 · Visión general](docs/areas/01-vision-general.md) |
| `web/routers/pages.py`, `portal.py`, `gestoria*.py`, `admin.py`, `account.py` (alta y sesión), `web/templates/`, `web/static/`, `sales.py`, `economics*.py` | [02 · Ramas de la empresa](docs/areas/02-ramas-de-la-empresa.md) |
| `web/chat.py`, `nlu.py`, `agent.py`, `tools.py`, `action_review.py`, `internal_brain.py`, `learning.py`, `local_invoice.py`, `intent_safety.py`, `web/whatsapp*.py`, `adapters/ai.py`, `adapters/transcription.py`, `adapters/extraction.py`, `documents/` (salvo `inbound_email.py`) | [03 · Cerebro](docs/areas/03-cerebro.md) |
| Facturas, presupuestos, cobros, series: `web/routers/invoicing.py`, `web/invoice_pdf.py`, `verifactu*.py`, `fiscal_validation.py`, `trades.py`, `adapters/invoicing.py` | [04 · Facturas](docs/areas/04-facturas.md) |
| `adapters/email.py`, `adapters/google_mail.py`, `secret_box.py`, `documents/inbound_email.py`, cualquier `queue_email` | [05 · Correo](docs/areas/05-correo.md) |
| Datos personales, bajas, exportación, consentimiento, cookies, `web/auth.py`, `security_center.py`, proveedores nuevos | [06 · RGPD y seguridad](docs/areas/06-rgpd-y-seguridad.md) |
| `web/scheduler.py`, colas `*_outbox`, `web/backups.py`, `production_check.py` | [07 · Lo automático](docs/areas/07-lo-automatico.md) |

## 4. Reglas de oro

1. UI, textos y comentarios en español; imita los identificadores existentes.
2. Stdlib y ejecución local primero. Sin CDNs en runtime ni dependencias pesadas
   sin justificar coste total.
3. Rutinas y cálculos en local. Solo el contenido no resuelto puede llegar a un
   proveedor externo autorizado.
4. Toda lectura/escritura filtra por `business_id`; rutas `/b/` y `/api/` con sesión.
5. IVA 21/10/4/0 e IRPF. Total = base + IVA - IRPF. Ver `docs/05-legal-y-rgpd/Fiscalidad.md`.
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

El método está en [`docs/08-agentes-ia/Metodo-operativo-Fable.md`](docs/08-agentes-ia/Metodo-operativo-Fable.md).
Los traspasos usan [`docs/08-agentes-ia/AI_HANDOFF_TEMPLATE.md`](docs/08-agentes-ia/AI_HANDOFF_TEMPLATE.md) y
las dudas del founder viven en [`docs/Preguntas-abiertas.md`](docs/Preguntas-abiertas.md).
