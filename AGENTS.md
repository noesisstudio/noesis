# AGENTS.md - Manual del proyecto Bynoesis

## 2026-10-05 — Fase1.9D: importer histórico (validación en curso)

Solo incorporación de candidatos congelados de C vigente. Flags OFF; no1.9E,
reconciliación, activación, continuidad live ni producción.
[Orden](docs/architecture/FASE-1.9D-orden.md), [ADR017](docs/architecture/ADR-017-financial-history-import.md),
[contrato](docs/architecture/FINANCIAL-HISTORY-IMPORT-v1.md), [cierre](docs/architecture/FASE-1.9D-cierre.md).
Monolito modular; importer/repositorio especializados sobre conexión y TX
compartidas. Decimal/NUMERIC y JSON decimal string; IA sin autoridad.
Intent item-scoped con UUID/request/candidato exactos; fence permanece activo.
Operación histórica PREPARED y historical_unknown, actor/session NULL; resultado
en import_items, ninguna ejecución ni cobertura live65–67. Tres v2 históricos
durables cerrados; factura histórica v2 bloqueada. Nuevos inventarios reconocen
evidencia histórica existente sin promover B a A ni modificar batches anteriores.
Los encabezados inferiores conservan historia y no amplían autorización.


## 2026-10-04 — Fase1.9C: epoch/T0/fence (implementada y validada)

Únicamente corte consistente por negocio, control durable y nuevo sobre de
inventory certificable, siempre eligible_for_import=false. Flags OFF; versión
de esquema consultable en project-state.json.
[ADR016](docs/architecture/ADR-016-financial-history-cutoff.md), [contrato](docs/architecture/FINANCIAL-HISTORY-CUTOFF-v1.md),
[writers previos](docs/architecture/FASE-1.9C-writers.md), [cierre](docs/architecture/FASE-1.9C-cierre.md).
SQL/application guard por tenant y TX prestada; no promoteB ni histórico EE/Operations/
v2/importer/reconciliación/activación.1.9D NO autorizada. Pruebas SQLite/PG sintéticas,
ninguna producción consultada. Invalidated conserva fence, release explícito pierde
boundary; TTL/crash no liberan. Encabezados inferiores conservan historia.


## Orden vigente — exclusivamente Fase 1.9B

0–1.8H y1.9A aceptadas. Solo inventario persistente/dry-run diagnóstico, no1.9C.
Leer [orden](docs/architecture/FASE-1.9B-orden.md), [mapa previo](docs/architecture/FASE-1.9B-fuentes.md),
[ADR015](docs/architecture/ADR-015-financial-history-diagnostic-inventory.md),
[API](docs/architecture/FINANCIAL-HISTORY-INVENTORY-v1.md) y [cierre](docs/architecture/FASE-1.9B-cierre.md).
Monolito modular, repositorio por dominio, conexión/TX compartidas. Reader prestado
solo SELECT tenant; inspección raw execute_exact sin normalización legacy. Decimal/
NUMERIC y JSON decimal string para candidato; binary/céntimos diagnósticos no Money.
Raw/classification/plan congelados; revisión append-only y historical.record
con operador actual autenticado, sin autoridad original/IA/financial.authorize.
Diagnostic/eligible_for_import=false/certifiable=false por SQL. READY_FOR_REVIEW
no importa. Todos los flags OFF. Solo fixtures SQLite/PG descartables; no producción.
Ningún writer/Capture/append/Operation histórico, epoch/T0/fence/write blocking,
validating/live boundary, importer/backfill/coverage histórica/reconciliación/activación.
Los encabezados inferiores son históricos; ninguna referencia autoriza otras unidades.

## Orden vigente — exclusivamente Fase 1.9A

0–1.8H validadas. Solo contratos puros y gobernanza de históricos, más guards
mínimos de no promoción/no ejecución de historical_unknown. Ningún dato legacy
real se lee/importa. Cinco flags OFF. No scanner, manifest durable, dry-run,
epoch/fence, importer, backfill, reconciliación ni activación; no1.9B.
Leer [orden](docs/architecture/FASE-1.9A-orden.md), [referencia](docs/architecture/FASE-1.9-plan.md),
[ADR-014](docs/architecture/ADR-014-financial-history-contracts.md),
[contrato](docs/architecture/FINANCIAL-HISTORY-v1.md) y [cierre](docs/architecture/FASE-1.9A-cierre.md).
Los encabezados inferiores son históricos y no amplían la orden actual.
Importable solo expresa coherencia local; no acredita fuentes ni concede autoridad.
No convertir bits legacy ni candidato a céntimos en Money sin evidencia.
Los tres v2 especiales son wrappers en memoria; no persistirlos con EconomicEvent.
Candidato de factura v2 bloqueado hasta contrato raw de líneas/fiscal.
Historical namespace/receipt jamás se aprueba/ejecuta como live.

## Orden vigente — exclusivamente Fase 1.8H

Fases 0–1.8 implementadas; hardening 1.8H cerrado con B1–B5 PASS.
Único alcance de esta unidad cerrada:
DELETE PostgreSQL (migración de reparación), gate de negocio antes de operación/
fuente, recurrencia común en servidor, consulta COMMITTED con sesión renovada y
CI completa verde. Cinco flags OFF. No 1.9, backfill, activación ni nuevos eventos.
Leer [orden](docs/architecture/FASE-1.8H-orden.md), [ADR-013](docs/architecture/ADR-013-financial-hardening.md)
y [cierre/evidencia](docs/architecture/FASE-1.8H-cierre.md).
Los alcances y encabezados inferiores describen entregas históricas aunque digan
«vigente»; no amplían la orden actual. No reescribir los cierres anteriores.


## Orden vigente — exclusivamente Fase 1.8

Fases 1.1–1.7 aceptadas. Solo bridges autenticados de web, chat/tools,
WhatsApp, revisión documental y recurrentes hacia los cinco Capture existentes.
Identidad durable, request exacto, autorización humana antes de consumir pending,
ejecución idempotente y recuperación de respuesta. La IA solo propone.
Recurrentes: borrador + confirmación humana por vencimiento; auto_issue no es
mandato. CSV: revisión por fila, upload no autoriza. Cinco flags OFF. No 1.9,
activación, nuevos eventos, GL, Tax Ledger, Open Items ni cambios de VERI*FACTU.
Leer [orden](docs/architecture/FASE-1.8-orden.md), [inventario previo](docs/architecture/FASE-1.8-entrada-audit.md), [ADR-012](docs/architecture/ADR-012-financial-channels.md), [contrato de canales](docs/architecture/FINANCIAL-CHANNELS-v1.md) y [cierre](docs/architecture/FASE-1.8-cierre.md).
Las órdenes y cierres inferiores son históricos; no amplían esta autorización.


## Referencia histórica de Fase 1.7

1.1–1.6 aceptadas. SupplierInvoiceCapture/ExpenseCapture conectan solo
supplier_invoice.confirmed/corrected/voided y expense.confirmed/voided v1.
Writers compartidos, autorización durable, cobertura inmutable por revisión,
continuidad antes/después, logical void y guards SQL. Documento/clasificación/
source/EE/resultado comparten commit. Flags OFF; no1.8, históricos ni activación.
Pagada es etiqueta operativa, no supplier payment/AP settlement. No GL/Tax/
OpenItems/reporting nuevo. Legacy no capturado conserva comportamiento.
[Orden](docs/architecture/FASE-1.7-orden.md), [ADR-011](docs/architecture/ADR-011-purchasing-capture.md),
[API](docs/architecture/PURCHASING-CAPTURE-v1.md), [cierre](docs/architecture/FASE-1.7-cierre.md).
Las referencias inferiores a fases previas son históricas. Las reglas de trabajo
del manual siguen vigentes.

> Para Financial Core, leer [gobernanza y ADR](docs/architecture/README.md) y
> [guía 08](docs/areas/08-financial-core.md). Fase 0 cerrada; Fase 1
> planificada y aprobada como referencia. 1.1–1.7 aceptadas; solo 1.8 autorizada:
> bridges de canal con identidad y aprobación durable;
> flags apagados y sin activación.
> Leer [plan](docs/architecture/FASE-1-plan.md),
> [contrato v1](docs/architecture/ECONOMIC-EVENTS-v1.md),
> [operaciones](docs/architecture/FINANCIAL-OPERATIONS-v1.md),
> [persistencia](docs/architecture/ECONOMIC-PERSISTENCE-v1.md),
> [writers](docs/architecture/BORROWED-WRITERS-v1.md) y ADR-006/007/008.
> Para emisión capturada, leer [ADR-009](docs/architecture/ADR-009-invoice-capture.md),
> [API](docs/architecture/INVOICE-CAPTURE-v1.md) y
> [cierre de 1.5](docs/architecture/FASE-1.5-cierre.md).
> Leer [ADR-010](docs/architecture/ADR-010-payment-bank-capture.md),
> [API de cobros/banco](docs/architecture/PAYMENT-BANK-CAPTURE-v1.md),
> [orden autorizada](docs/architecture/FASE-1.6-orden.md) y
> [cierre de 1.6](docs/architecture/FASE-1.6-cierre.md).
> Leer [ADR-011](docs/architecture/ADR-011-purchasing-capture.md),
> [API de recibidas/gastos](docs/architecture/PURCHASING-CAPTURE-v1.md) y
> [cierre de 1.7](docs/architecture/FASE-1.7-cierre.md).
> No avanzar a 1.8. La fachada legacy posee la transacción; un writer prestado
> nunca abre otra conexión, hace commit/rollback ni I/O externo.
> Las referencias no autorizan ejecutar otras unidades.

## Contrato del Financial Core

- Monolito modular: servicios y repositorios especializados por dominio; conexión,
  pool y transacciones compartidos mediante `db.get_conn()` y `FinancialSession`.
- Prohibida nueva lógica financiera grande dentro de `db.py`: únicamente cambios
  acotados de infraestructura o mantenimiento legacy. Nada de nuevos pools/ORM.
- `Decimal/NUMERIC` es el contrato del núcleo; SQLite usa TEXT decimal canónico
  para preservar exactitud. No pasar por normalización legacy a float ni usar
  REAL, SUM/CAST binarios o JSON numérico para importes nuevos.
- Cobros capturados requieren settles a factura capturada; banco requiere identidad
  cuenta/batch/fila. Match es Evidence-only y nunca segunda caja. Coberturas
  específicas y link bank→payment impiden commit sin eventos; no backfill legacy.
- La IA propone; no autoriza, contabiliza, liquida ni cambia reglas financieras.
  El servicio valida permisos, aprobación, invariantes e idempotencia.
- Economic Events son hechos financieros, no un log genérico. `quote.accepted`
  y `job.completed` son operativos; solo una regla explícita posterior puede
  producir una obligación o reconocimiento diferente y trazable.
- Eventos/links incorporados son append-only en aplicación y BD. Referencias
  tipadas y FKs compuestas por negocio; ninguna cascada borra evidencia.
  `EconomicEvents` recibe `FinancialSession`; el llamador posee la transacción.
  SQLite exige transacción exterior antes de append. Solo InvoiceCapture conecta
  emisión/rectificación: operación/aprobación + writer + evento + resultado
  en un commit, cobertura obligatoria e inmutable. No otros productores ni flags.

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
| Financial Core, `core/`, `economic_events/`, `financial_operations/`, `financial_history/`, `accounting/`, exactitud y repositorios financieros | [08 · Financial Core](docs/areas/08-financial-core.md) |
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
