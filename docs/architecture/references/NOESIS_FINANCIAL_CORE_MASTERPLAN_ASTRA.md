# NOESIS → Financial Operating System
## Masterplan técnico para Astra

**Fecha:** 2026-10-01  
**Repositorio actual:** `noesisstudio/noesis`  
**Objetivo:** transformar Noesis desde un SaaS operativo para autónomos/microempresas en un **sistema operativo financiero-contable modular**, manteniendo la experiencia de WhatsApp y el enfoque de automatización segura.

---

# 0. Resumen ejecutivo para Astra

Noesis **no debe rehacerse desde cero**. La capa de experiencia, facturación, documentos, WhatsApp, seguridad, colas, multiempresa, gestoría, proyectos y automatización segura es aprovechable.

El cambio central consiste en introducir debajo del producto un **Financial Core único** que pase a ser la fuente de verdad de toda la información económica.

La arquitectura objetivo será:

```text
WhatsApp / Web / API / Integraciones
                ↓
        Intent / Action Review
                ↓
        Dominio operativo
  ventas · compras · proyectos · docs
                ↓
          Economic Events
                ↓
────────────────────────────────────
          FINANCIAL CORE
────────────────────────────────────
 General Ledger / Accounting
 Tax Ledger
 Accounts Receivable
 Accounts Payable
 Open Items
 Banking & Reconciliation
 Accounting Periods & Close
 Dimensions / Cost Accounting
                ↓
────────────────────────────────────
          INFORMACIÓN DERIVADA
────────────────────────────────────
 P&L · Balance · Cash Flow
 IVA · IRPF · libros fiscales
 Gestoría · Tesorería · Forecast
 KPIs · CFO · Alertas · IA
```

**Regla esencial:** ningún dashboard, informe fiscal o respuesta financiera importante debe volver a reconstruir la realidad económica leyendo directamente `invoices + expenses + received_invoices` de formas distintas. Todo debe derivar progresivamente del Financial Core.

---

# 1. Punto de partida real

## 1.1 Lo que ya existe y debe conservarse

Mantener y reutilizar:

- SaaS multiempresa mediante `business_id`.
- PostgreSQL y sistema de migraciones.
- Facturación nativa.
- Series de facturación.
- Líneas de factura.
- Facturas rectificativas.
- Pagos parciales y completos.
- VERI*FACTU: huella, cadena, QR, XML, outbox, cliente AEAT.
- Clientes.
- Proveedores.
- Presupuestos.
- Proyectos.
- Materiales, horas y costes por proyecto.
- Facturas recibidas.
- Gastos manuales.
- Documentos y extracción.
- Portal del cliente.
- Portal de gestoría.
- MFA de gestoría.
- WhatsApp.
- Cola durable.
- Scheduler.
- Idempotencia existente.
- Backups y restore drills.
- `action_review` y confirmación humana.
- permisos de automatización.
- `assistant_actions`.
- aprendizaje supervisado.
- tests actuales.
- `value_ledger` como métrica de valor de producto.

## 1.2 Lo que NO debe considerarse Financial Core

No confundir:

- `value_ledger.py` con General Ledger.
- `profit_and_loss()` con contabilidad real.
- `cash_forecast()` con tesorería real.
- `tax_quarter()` con motor fiscal completo.
- conciliación CSV actual con reconciliación bancaria completa.

Estos componentes pueden seguir existiendo temporalmente como **legacy/compatibilidad**, pero se deben sustituir progresivamente.

---

# 2. Decisiones arquitectónicas obligatorias antes de programar

## 2.1 Modular Monolith, NO microservicios

No dividir Noesis en servicios independientes ahora.

Crear dominios internos claros en el mismo repositorio y la misma aplicación.

Estructura objetivo aproximada:

```text
src/noesis/
    core/
        money.py
        ids.py
        time.py
        idempotency.py
        errors.py

    accounting/
        models.py
        repository.py
        service.py
        posting.py
        rules.py
        periods.py
        reports.py
        close.py

    economic_events/
        models.py
        repository.py
        service.py
        handlers.py

    receivables/
        models.py
        repository.py
        service.py
        aging.py

    payables/
        models.py
        repository.py
        service.py
        approvals.py

    tax/
        models.py
        repository.py
        service.py
        rules_es.py
        reports.py

    banking/
        models.py
        repository.py
        service.py
        matching.py
        importers/

    treasury/
        service.py
        forecast.py
        scenarios.py

    dimensions/
        models.py
        repository.py
        service.py

    invoicing/
        service.py
        posting_bridge.py

    purchases/
        service.py
        posting_bridge.py

    assets/
    payroll/
    inventory/

    assistant/
    documents/
    web/
```

No es necesario mover todos los archivos el primer día. La transición será por fases.

## 2.2 PostgreSQL como referencia de comportamiento

El motor financiero debe diseñarse para PostgreSQL.

SQLite puede mantenerse para determinados tests o ejecución local, pero **no debe limitar**:

- constraints,
- locking,
- tipos monetarios,
- concurrencia,
- integridad,
- índices,
- JSON estructurado,
- operaciones contables.

Si una regla crítica funciona diferente entre SQLite y PostgreSQL, manda PostgreSQL.

## 2.3 Dinero

Para todo nuevo Financial Core:

- Python: `Decimal`.
- PostgreSQL: `NUMERIC(20, 4)` o superior donde proceda.
- Importes contables finales: precisión de moneda según divisa.
- Nunca `float` para posting, tax, bank matching final, open items, balances o reports.

Crear `core/money.py`.

Debe contener:

```python
Money
Currency
quantize_currency()
parse_money()
```

Inicialmente EUR, pero el modelo debe aceptar `currency` desde el día 1.

## 2.4 IDs e idempotencia

Cada operación económica debe ser idempotente.

Todo Economic Event tendrá:

- `event_id`
- `business_id`
- `event_type`
- `source_type`
- `source_id`
- `idempotency_key`
- `occurred_at`
- `accounting_date`
- `payload`
- `status`

`UNIQUE (business_id, idempotency_key)`.

## 2.5 No borrar historia contable

Principio permanente:

- draft puede modificarse/eliminarse.
- posted no se modifica.
- posted se corrige mediante reverse/adjustment.
- periodos cerrados no aceptan posting normal.

---

# 3. Estrategia especial porque aún no hay clientes de pago

Aprovechar esta ventana.

## Permitir ahora

- renombrar tablas internas.
- sustituir APIs internas.
- retirar duplicidades.
- cambiar contratos internos entre módulos.
- rehacer reporting financiero.
- limpiar datos demo.
- regenerar demos.
- migrar el esquema de desarrollo de manera agresiva.

## No permitir

- perder las garantías de facturación emitida.
- romper VERI*FACTU.
- quitar aislamiento multiempresa.
- saltarse confirmaciones humanas.
- hacer que Claude escriba contabilidad directamente.

---

# 4. FASE 0 — Congelar el dominio y crear la base del cambio

## Objetivo

Preparar el repositorio para que el Financial Core no se convierta en más lógica dentro de `db.py`.

## 4.1 Crear ADRs

Crear:

```text
docs/architecture/ADR-001-financial-core.md
docs/architecture/ADR-002-economic-events.md
docs/architecture/ADR-003-double-entry-ledger.md
docs/architecture/ADR-004-money-decimal.md
docs/architecture/ADR-005-accounting-periods.md
```

Documentar decisiones y alternativas descartadas.

## 4.2 Crear package `accounting/`

Aunque inicialmente esté vacío.

## 4.3 Crear repository layer nuevo

No añadir las nuevas operaciones contables a `db.py`.

Todos los nuevos módulos deben utilizar repositories propios.

Ejemplo:

```python
AccountingRepository
EconomicEventRepository
ReceivablesRepository
TaxRepository
BankingRepository
```

## 4.4 Política de compatibilidad

Durante la migración:

```text
legacy operational tables
            +
new financial core
```

Cada flujo migrado escribirá en ambos sistemas solo mientras sea necesario para comparación.

## 4.5 Feature flags

Crear al menos:

```text
NOESIS_FINANCIAL_CORE_ENABLED
NOESIS_LEDGER_REPORTING_ENABLED
NOESIS_OPEN_ITEMS_ENABLED
NOESIS_NEW_TAX_ENGINE_ENABLED
NOESIS_NEW_BANK_RECONCILIATION_ENABLED
```

Por defecto `false` hasta validación.

## Definition of Done fase 0

- nuevas carpetas creadas.
- ADRs aprobados.
- `Money` basado en Decimal.
- prohibición de nuevas funciones financieras grandes dentro de `db.py`.
- feature flags creadas.
- CI verde.

---

# 5. FASE 1 — Economic Event Layer

## Objetivo

Separar “qué ocurrió en el negocio” de “cómo se contabiliza”.

Esta capa es crítica.

## 5.1 Nueva tabla `economic_events`

```sql
CREATE TABLE economic_events (
    id BIGSERIAL PRIMARY KEY,
    business_id BIGINT NOT NULL,
    event_uuid UUID NOT NULL,
    event_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    accounting_date DATE NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'EUR',
    payload JSONB NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (business_id, event_uuid),
    UNIQUE (business_id, idempotency_key)
);
```

Estados:

```text
created
validated
posted
failed
reversed
```

## 5.2 Event types iniciales

```text
invoice.issued
invoice.rectified
invoice.cancelled
customer_payment.received
supplier_invoice.confirmed
supplier_payment.made
expense.confirmed
bank_transaction.imported
bank_transaction.matched
quote.accepted
job.completed
project.cost.recorded
```

No todos generan asiento.

Ejemplo:

`quote.accepted` es evento económico/operativo, pero no necesariamente posting contable.

## 5.3 Adaptadores desde módulos actuales

Modificar progresivamente:

- `issue_invoice()`
- `add_invoice_payment()`
- `add_received_invoice()`
- `add_expense()`
- `confirm_bank_transaction()`

para emitir Economic Events.

## 5.4 Outbox transaccional

El Economic Event debe guardarse dentro de la misma transacción que el cambio operativo importante.

Nunca:

```text
guardar factura
commit
intentar crear evento
```

Debe ser:

```text
BEGIN
factura
EconomicEvent
COMMIT
```

## Definition of Done fase 1

- todos los eventos financieros principales generan `economic_events`.
- idempotencia probada.
- tests de concurrencia.
- ninguna factura emitida puede existir sin su evento cuando el flag esté activo.
- ninguna duplicación al reintentar.

---

# 6. FASE 2 — Chart of Accounts + General Ledger

## Objetivo

Crear una contabilidad de partida doble real.

Esta es la fase más importante del masterplan.

## 6.1 Tabla `accounting_accounts`

```sql
accounting_accounts
- id
- business_id
- code
- name
- account_type
- normal_side
- parent_id
- is_postable
- is_system
- currency
- active
- created_at
```

`account_type`:

```text
asset
liability
equity
revenue
expense
off_balance
```

## 6.2 Plan inicial español

Cargar un plan canónico mínimo basado en PGC/PGC Pymes.

No hace falta mostrarlo al autónomo.

Primer conjunto operativo:

```text
430 Clientes
400 Proveedores
410 Acreedores
572 Bancos
570 Caja
700 Ventas
705 Prestaciones de servicios
600 Compras
62x Servicios exteriores
640 Sueldos
642 Seguridad Social empresa
472 IVA soportado
477 IVA repercutido
4751 HP acreedora retenciones
4700 HP deudora IVA
4750 HP acreedora IVA
520/170 Deudas
21x Inmovilizado
28x Amortización acumulada
68x Dotación amortización
```

Después ampliar.

## 6.3 Tabla `journal_entries`

```sql
journal_entries
- id
- business_id
- entry_number
- event_id
- accounting_date
- posting_date
- description
- source_type
- source_id
- status
- reversal_of_entry_id
- created_by
- approved_by
- posted_at
- created_at
```

Estados:

```text
draft
posted
reversed
```

## 6.4 Tabla `journal_lines`

```sql
journal_lines
- id
- business_id
- entry_id
- line_number
- account_id
- debit
- credit
- currency
- amount_currency
- exchange_rate
- description
- counterparty_type
- counterparty_id
- tax_line_id
- dimension_set_id
- created_at
```

Constraint conceptual:

```text
exactly one of debit/credit > 0
```

## 6.5 Invariante principal

Antes de `posted`:

```text
SUM(debit) == SUM(credit)
```

Debe comprobarse:

1. aplicación,
2. test,
3. preferiblemente constraint/trigger defensivo o procedimiento transaccional.

## 6.6 Posting Engine

Crear:

```text
accounting/posting.py
```

API conceptual:

```python
posting.post(event)
```

Nunca permitir que una route construya `journal_lines` manualmente.

## 6.7 Primeras reglas

### invoice.issued

```text
430 Cliente                         DEBE total
705 Prestación servicios           HABER base
477 IVA repercutido                HABER IVA
4751 HP retenciones                DEBE/HABER según diseño y naturaleza
```

Debe comprobarse cuidadosamente el tratamiento de retenciones.

### supplier_invoice.confirmed

```text
6xx Gasto / Compra                  DEBE base
472 IVA soportado                   DEBE IVA deducible
400/410 Proveedor                   HABER total a pagar
```

### customer_payment.received

```text
572 Banco                           DEBE
430 Cliente                         HABER
```

### supplier_payment.made

```text
400/410 Proveedor                   DEBE
572 Banco                           HABER
```

## 6.8 Reversal

Nunca editar `posted`.

Crear:

```python
reverse_entry(entry_id, reason)
```

que produzca asiento inverso.

## 6.9 Numeración contable

Separar:

- número fiscal de factura,
- número de asiento.

El asiento puede seguir secuencia por empresa/año.

## Definition of Done fase 2

- cada factura emitida genera asiento balanceado.
- cada factura recibida confirmada genera asiento.
- cobros y pagos básicos generan asiento.
- reversals funcionando.
- no se modifica un asiento posted.
- ledger reproducible desde Economic Events.
- tests con Decimal.
- pruebas de 10.000 eventos sin descuadre.

---

# 7. FASE 3 — AR / AP y Open Items

## Objetivo

Crear deudas a cobrar/pagar como objetos explícitos.

## 7.1 Tabla `open_items`

```sql
open_items
- id
- business_id
- item_type           -- receivable/payable/tax/other
- counterparty_type
- counterparty_id
- source_type
- source_id
- journal_entry_id
- currency
- original_amount
- open_amount
- due_date
- status
- created_at
- settled_at
```

Estados:

```text
open
partial
settled
disputed
written_off
```

## 7.2 Tabla `settlements`

```sql
settlements
- id
- business_id
- open_item_id
- settlement_event_id
- amount
- settled_on
- created_at
```

## 7.3 Sustituir lógica de pending invoices

Actualmente:

```python
pending_payments()
```

mira facturas y `remaining_amount`.

Nuevo mundo:

```python
receivables.list_open_items()
```

Facturas seguirán teniendo estado visual, pero el saldo económico sale de Open Items.

## 7.4 Aging

Crear buckets:

```text
not_due
1-30
31-60
61-90
90+
```

Por cliente y proveedor.

## 7.5 DSO / DPO

Mover cálculo a receivables/payables.

## Definition of Done fase 3

- AR y AP nacen del posting.
- pagos parciales funcionan.
- cobro múltiple de una factura.
- un pago puede compensar varias facturas en futuro; diseñar modelo para ello.
- aging cuadra con GL.
- saldo 430 = total AR abierto + compensado históricamente según periodo.
- saldo 400/410 = AP.

---

# 8. FASE 4 — Tax Ledger real

## Objetivo

Separar la contabilidad del tratamiento fiscal.

## 8.1 Tabla `tax_codes`

```text
tax_codes
- code
- jurisdiction
- tax_type
- rate
- deductible_default
- valid_from
- valid_to
- metadata
```

Ejemplos iniciales España:

```text
ES-VAT-21-OUTPUT
ES-VAT-21-INPUT
ES-VAT-10-OUTPUT
ES-VAT-10-INPUT
ES-VAT-4-OUTPUT
ES-VAT-4-INPUT
ES-VAT-0
ES-IRPF-RET-15
ES-IRPF-RET-7
```

## 8.2 Tabla `tax_lines`

```sql
tax_lines
- id
- business_id
- event_id
- source_type
- source_id
- tax_code_id
- tax_point_date
- taxable_base
- tax_rate
- tax_amount
- deductible_percentage
- deductible_amount
- counterparty_tax_id
- country
- regime
- status
```

## 8.3 Fiscal Profile

Reutilizar y ampliar `gestoria_fiscal_profiles`.

Añadir configuraciones estructuradas:

- autónomo / SL / otras.
- régimen IVA.
- estimación directa.
- criterio caja si corresponde.
- recargo equivalencia.
- intracomunitario.
- prorrata.
- retenciones aplicables.
- obligaciones.

## 8.4 Motor de reglas

Crear:

```text
tax/rules_es.py
```

Reglas deterministas.

La IA puede clasificar o proponer, nunca decidir en silencio.

## 8.5 Modelo 303

Rehacer cálculo desde `tax_lines`.

Comparar durante transición:

```text
legacy tax_quarter()
vs
new tax engine
```

## 8.6 Modelo 130

Rehacer desde ledger + fiscal adjustments.

## 8.7 Fiscal adjustments

Crear estructura para:

- gasto contable no deducible.
- IVA parcialmente deducible.
- diferencias permanentes.
- diferencias temporarias en futuro.

## Definition of Done fase 4

- IVA sale de Tax Ledger.
- nuevo 303 cuadra contra casos de prueba.
- IRPF separado de VAT.
- ningún informe fiscal necesita recomponer importes desde strings/documentos.
- gestoría puede ver origen de cada línea fiscal.

---

# 9. FASE 5 — Banking & Reconciliation 2.0

## Objetivo

Que el banco sea una fuente de evidencia y conciliación, no solo un importador de cobros.

## 9.1 Normalizar bank transactions

Extender modelo:

```text
bank_accounts
bank_transactions
bank_imports
bank_matches
```

## 9.2 Bank account

```sql
bank_accounts
- id
- business_id
- name
- iban_masked
- currency
- ledger_account_id
- provider
- active
```

Cada cuenta bancaria debe mapear a una cuenta 572 específica.

## 9.3 Matching engine

Orden sugerido:

1. referencia exacta.
2. importe exacto + contraparte.
3. importe + invoice number.
4. importe + cliente/proveedor.
5. ventana temporal.
6. histórico de matches.
7. fuzzy/IA como sugerencia.

Nunca match automático irreversible por IA.

## 9.4 Entradas y salidas

Eliminar la limitación conceptual actual donde solo se emparejan cobros positivos.

Soportar:

- customer payment.
- supplier payment.
- tax payment.
- payroll.
- loan payment.
- card settlement.
- transfer between own accounts.
- bank fees.
- unclassified movement.

## 9.5 Suspense account

Crear cuenta temporal para movimientos bancarios no clasificados.

Ejemplo:

```text
572 Banco              DEBE/HABER
555 Partidas pendientes
```

Hasta clasificación.

## 9.6 PSD2/open banking

NO implementarlo hasta que CSV/OFX reales estén validados con clientes piloto.

Diseñar adapter interface desde ahora:

```python
BankFeedAdapter
```

## Definition of Done fase 5

- conciliación de entradas y salidas.
- saldo contable banco comparable con extracto.
- diferencias explícitas.
- matches auditables.
- reversibles.
- no duplicación por reimportar fichero.

---

# 10. FASE 6 — Accounting Periods, Close & Controls

## Objetivo

Permitir una contabilidad profesional y trabajar con gestoría.

## 10.1 Tabla `accounting_periods`

```sql
accounting_periods
- id
- business_id
- year
- month
- starts_on
- ends_on
- status
- soft_closed_at
- hard_closed_at
- closed_by
- reopened_at
- reopened_by
```

Estados:

```text
open
soft_closed
hard_closed
```

## 10.2 Comportamiento

### open
posting normal.

### soft_closed
requiere permiso superior o warning.

### hard_closed
solo adjustment/reopen autorizado.

## 10.3 Close checklist

Crear:

```text
close_tasks
```

Checklist mensual:

- banco conciliado.
- AR revisado.
- AP revisado.
- documentos sin clasificar.
- facturas pendientes de recibir.
- IVA validado.
- amortizaciones.
- nómina.
- periodificaciones.
- incidencias.

## 10.4 Audit trail

Cualquier acción de cierre/reapertura debe registrar:

- actor,
- timestamp,
- motivo,
- periodo,
- evidencia.

## Definition of Done fase 6

- no posting normal en periodo hard closed.
- reapertura controlada.
- checklist visible a gestoría.
- auditoría completa.
- closing tests concurrentes.

---

# 11. FASE 7 — Reporting financiero real

## Objetivo

Retirar progresivamente cálculos legacy.

## 11.1 Balance

Construir desde GL.

Debe cumplirse siempre:

```text
Assets = Liabilities + Equity
```

## 11.2 P&L

Construir exclusivamente desde cuentas de ingreso/gasto.

Permitir:

- mes.
- trimestre.
- año.
- comparativa.
- por dimensión.

## 11.3 Trial Balance

Imprescindible:

```text
Saldo inicial
Debe periodo
Haber periodo
Saldo final
```

## 11.4 General Ledger / Mayor

Por cuenta.

## 11.5 Diario

Lista de asientos.

## 11.6 Cash Flow

Primera versión: método indirecto.

Después, si interesa, directo.

## 11.7 Reconciliation reports

- AR ↔ 430.
- AP ↔ 400/410.
- Tax ↔ 472/477/475.
- Bank ↔ 572.

## 11.8 Retirar legacy

Marcar deprecated:

```text
financial_analysis()
profit_and_loss()
month_billing() [parte financiera]
tax_quarter() legacy
cash_forecast() legacy
```

No borrar hasta que nuevos informes sean estables.

## Definition of Done fase 7

- P&L nuevo = ledger.
- Balance balanceado siempre.
- Trial Balance.
- mayor y diario.
- reconciliaciones.
- comparación legacy/new documentada.

---

# 12. FASE 8 — Dimensions & Management Accounting

## Objetivo

Convertir proyectos actuales en una contabilidad analítica extensible.

## 12.1 Dimensiones

Modelo genérico:

```text
dimensions
- project
- department
- cost_center
- location
- employee
- product
- channel
- customer
```

## 12.2 `dimension_sets`

Una journal line puede tener múltiples dimensiones.

No añadir 10 columnas directamente en `journal_lines`.

Usar:

```text
dimension_sets
dimension_values
dimension_set_values
```

## 12.3 Proyectos

Mapear `project_id` actual a dimensión `project`.

El margen de proyecto debe derivar finalmente de journal lines y/o subledger operativo compatible.

## 12.4 Centros de coste

Añadir cuando aparezcan empresas con equipo/departamentos.

## Definition of Done fase 8

- P&L por proyecto.
- P&L por centro de coste.
- gastos compartidos asignables.
- dimensiones no rompen ledger.

---

# 13. FASE 9 — Treasury & CFO real

## Objetivo

Construir forecast sobre obligaciones reales y escenarios.

## 13.1 Treasury events

Crear una proyección temporal unificada:

```text
TreasuryEvent
- expected_date
- amount
- direction
- probability
- source
- confidence
- currency
- scenario
```

Fuentes:

- AR vencimiento.
- AP vencimiento.
- impuestos.
- nóminas.
- préstamos.
- suscripciones recurrentes.
- facturas recurrentes.
- presupuestos probables (solo escenario, no base).

## 13.2 Forecast

Horizontes:

```text
7 días
30 días
13 semanas
12 meses
```

## 13.3 Escenarios

```text
Base
Conservador
Optimista
```

## 13.4 Working capital

KPIs:

- DSO.
- DPO.
- cash conversion cycle.
- overdue AR.
- overdue AP.
- cash runway.

## 13.5 CFO copilot

Solo aquí tiene sentido construir un CFO fuerte.

Ejemplos:

> “Si todos los clientes pagan en fecha, tendrás ~18.200 € el 30 de noviembre.”

> “Hay 4.600 € de facturas que vencen antes del IVA.”

> “La obra X tiene margen 18 %, frente a 29 % previsto.”

Siempre mostrar fuente y supuestos.

## Definition of Done fase 9

- forecast fecha por fecha.
- escenarios.
- no usar media simple de 90 días como fuente principal.
- explicabilidad de cada cifra.

---

# 14. FASE 10 — Accounts Payable profesional

## Objetivo

Preparar Noesis para pequeñas y medianas empresas.

## Añadir

- invoice intake.
- duplicate detection.
- due dates.
- payment terms.
- approval status.
- purchase orders (opcional inicial).
- three-way match futuro.
- scheduled payments.
- supplier bank change control.

## Approval workflow

Ejemplo configurable:

```text
< 500 €             owner auto-review
500–5.000 €         manager approval
> 5.000 €           dual approval
cambio IBAN         siempre revisión fuerte
```

No hardcodear límites.

---

# 15. FASE 11 — Fixed Assets

## Objetivo

Permitir P&L y Balance realistas.

## Tablas

```text
fixed_assets
asset_categories
depreciation_schedules
asset_movements
```

## Flujo

Compra de ordenador:

```text
217 Equipos proceso información    DEBE
472 IVA soportado                  DEBE
400 Proveedor                      HABER
```

Mensualmente:

```text
681 Amortización                   DEBE
2817 Amortización acumulada        HABER
```

## Definition of Done

- alta activo.
- vida útil.
- método amortización.
- bajas.
- posting automático mensual.
- roll-forward de activos.

---

# 16. FASE 12 — Payroll Integration

No construir un motor completo de nómina español desde cero inicialmente.

Crear `PayrollAdapter`.

Objetivo:

- importar resumen de nómina.
- contabilizar.
- reconocer obligaciones.
- reflejar pagos.

Asiento conceptual:

```text
640 Sueldos
642 SS empresa
    476 SS acreedora
    4751 Retenciones
    465 Remuneraciones pendientes
```

Más adelante integrar proveedor especializado.

---

# 17. FASE 13 — Inventory (solo si el mercado lo exige)

Para el target actual no debe ser prioridad.

Diseñar sólo interfaces.

Cuando se construya:

- items.
- stock locations.
- stock movements.
- valuation.
- COGS.
- purchase receipts.

No mezclar inventario con proyectos antes de necesitarlo.

---

# 18. FASE 14 — E-Invoicing estructurado

## Objetivo

Preparar B2B más allá del PDF y VERI*FACTU.

Modelo interno de factura debe ser suficientemente rico para exportar:

- Facturae.
- UBL.
- CII / EN16931 cuando corresponda.

Separar:

```text
invoice data
invoice rendering (PDF)
fiscal record (VERI*FACTU)
e-invoice transport
```

No acoplar PDF y factura electrónica.

Crear adapters:

```text
EInvoiceSerializer
EInvoiceTransport
```

---

# 19. FASE 15 — Roles, RBAC y Segregation of Duties

## Objetivo

Superar `is_admin`.

## Tablas

```text
roles
permissions
role_permissions
user_roles
approval_policies
approval_requests
approval_steps
```

## Permissions iniciales

```text
invoice.view
invoice.create
invoice.issue
invoice.rectify
invoice.send
customer.manage
supplier.manage
supplier.bank_change
expense.create
expense.approve
payment.prepare
payment.approve
journal.view
journal.create
journal.post
journal.reverse
period.close
period.reopen
tax.view
tax.approve
gestoria.manage
```

## SoD

Reglas configurables:

- quien cambia IBAN de proveedor no aprueba el pago inmediatamente.
- quien prepara pago puede no aprobarlo.
- hard close requiere rol concreto.

Para autónomo de una persona, Owner puede tener todo.

---

# 20. FASE 16 — Multi-entity, Multicurrency, Intercompany

No implementar ahora, pero diseñar sin bloquearlo.

## 20.1 Legal entities

Actualmente `business_id` mezcla en gran parte workspace y entidad económica.

A futuro introducir:

```text
organizations
legal_entities
workspaces
```

No migrar hasta que exista necesidad real.

## 20.2 Multicurrency

Desde ledger v1 incluir:

- transaction currency.
- functional currency.
- exchange rate.
- amount in both.

Aunque inicialmente solo EUR.

## 20.3 Intercompany

Futuro:

- due to/from.
- mirrored entries.
- elimination.

## 20.4 Consolidation

Solo cuando haya demanda de grupos empresariales.

---

# 21. Cambios concretos en módulos actuales

## `src/noesis/db.py`

### Hacer

- congelar crecimiento.
- mantener como façade legacy.
- extraer progresivamente domains.

### No hacer

- no añadir General Ledger aquí.
- no añadir Tax Engine aquí.
- no añadir AP completo aquí.

---

## `src/noesis/economics.py`

Mantener únicamente como **economía del SaaS Bynoesis** (unit economics de vuestra propia empresa), no como finanzas de clientes.

Separar claramente del Financial Core del cliente.

---

## `src/noesis/value_ledger.py`

Mantener.

Renombrar conceptualmente/documentar como:

```text
Product Value Ledger
```

para evitar confusión con Accounting General Ledger.

No migrar sus datos al ledger contable.

---

## `src/noesis/banking.py`

Convertir en adapter/importer.

La lógica central futura se mueve a:

```text
banking/matching.py
banking/service.py
```

---

## `src/noesis/verifactu.py`

Mantener prácticamente independiente.

VERI*FACTU pertenece al flujo de facturación/fiscal record, no al General Ledger.

Debe recibir datos de la invoice emitida congelada.

---

## `src/noesis/gestoria_workspace.py`

Rehacer gradualmente para consumir:

- trial balance,
- tax ledger,
- journal,
- open items,
- documents,
- close checklist.

Esto puede convertirse en una gran ventaja competitiva.

---

## `src/noesis/action_review.py`

Mantener filosofía.

Extender para nuevas acciones de riesgo:

```text
post manual journal
reverse journal
reopen period
approve payment
change supplier bank account
submit tax package
```

---

## `src/noesis/internal_brain.py` / IA

No permitir generación de SQL financiero.

La IA llama a tools estructuradas.

Ejemplo futuro:

```python
propose_accounting_classification(document_id)
```

respuesta:

```json
{
  "suggested_account": "629000",
  "confidence": 0.94,
  "reason": "Factura de telecomunicaciones"
}
```

Luego motor determinista valida.

---

# 22. Herramientas que Astra debe crear

Astra debería trabajar siempre mediante APIs internas de dominio.

No routes → SQL.

Ejemplos:

```python
create_economic_event()
post_event()
reverse_entry()
create_open_item()
settle_open_item()
create_tax_lines()
match_bank_transaction()
close_period()
reopen_period()
generate_trial_balance()
generate_balance_sheet()
generate_profit_and_loss()
```

---

# 23. Testing obligatorio

No basta con unit tests normales.

## 23.1 Property tests contables

Para cualquier conjunto de asientos:

```text
SUM(debits) == SUM(credits)
```

Siempre.

## 23.2 Replay tests

Vaciar ledger.

Reprocesar Economic Events.

Resultado final debe ser idéntico.

## 23.3 Idempotency tests

Procesar mismo event 2, 10 y 100 veces.

Solo un efecto financiero.

## 23.4 Concurrency tests

Dos workers procesando el mismo event.

Solo un posting.

## 23.5 Reversal tests

Entry + reversal = 0 efecto neto acumulado.

## 23.6 Subledger reconciliation

```text
AR subledger == account 430
AP subledger == accounts 400/410
VAT ledger == 472/477 relevante
Bank subledger == 572
```

## 23.7 Period close tests

No post after hard close.

## 23.8 Migration tests

Crear negocio legacy y migrarlo.

Verificar resultados.

## 23.9 Golden cases

Crear una suite fija de empresas simuladas:

### autónomo servicios

- factura 21 %.
- factura con IRPF.
- cobro parcial.
- proveedor.
- gasto.
- IVA trimestral.

### reformas

- proyecto.
- materiales.
- trabajador.
- factura anticipo.
- factura final.

### micro-SL

- nómina importada.
- préstamo.
- activo fijo.
- amortización.

Cada release debe producir exactamente los informes esperados.

---

# 24. Observabilidad financiera

Añadir métricas:

```text
financial_events_created_total
financial_events_failed_total
journal_entries_posted_total
journal_entries_unbalanced_total   # debe ser siempre 0
open_items_total
bank_unmatched_total
period_close_errors_total
tax_validation_errors_total
```

No incluir datos personales en métricas.

Crear panel admin interno de integridad financiera.

---

# 25. Data Integrity Center

Crear endpoint/pantalla interna:

```text
/admin/financial-integrity
```

Checks:

- unbalanced entries.
- event without posting.
- duplicate posting.
- invoice issued without event.
- posted entry without event/source.
- AR vs 430 discrepancy.
- AP vs 400/410 discrepancy.
- bank vs 572 discrepancy.
- closed-period violations.
- Tax Ledger vs GL mismatch.

Debe poder ejecutarse periódicamente.

---

# 26. Migración de datos actuales

Como no hay clientes oficiales:

## Recomendación

No intentar conservar todas las pruebas/demo como si fueran registros legales reales.

Clasificar cuentas:

```text
production-real
internal-test
demo
```

Para `demo`:

- regenerar desde fixtures nuevos.

Para `internal-test`:

- migrar solo si sirve para comprobar migrador.

Para cualquier factura fiscal real ya emitida:

- conservar inmutable.
- generar Economic Event retroactivo.
- generar posting con `source = migration`.
- mantener referencia al documento original.

Nunca alterar numeración ni huella VERI*FACTU histórica.

---

# 27. Nueva demo comercial

Cuando el Financial Core esté listo, la demo debe enseñar:

```text
WhatsApp: “haz factura a Reformas Martínez por 1.000 + IVA”
        ↓
Factura
        ↓
VERI*FACTU
        ↓
Asiento contable
        ↓
Cliente pendiente 1.210 €
```

Después:

```text
importar extracto
        ↓
Noesis propone conciliación
        ↓
confirmar
        ↓
cliente pendiente 0 €
        ↓
banco +1.210 €
```

Y finalmente:

```text
“¿cómo va mi negocio?”
```

Noesis responde desde Financial Core.

Eso demuestra una ventaja real, no un chatbot.

---

# 28. Orden exacto recomendado de ejecución

No alterar este orden sin motivo fuerte.

```text
0  Architecture freeze + Money
1  Economic Events
2  General Ledger
3  AR/AP + Open Items
4  Tax Ledger
5  Banking 2.0
6  Accounting Periods & Close
7  Financial Reporting
8  Dimensions
9  Treasury/CFO
10 AP workflows
11 Fixed Assets
12 Payroll adapter
13 Inventory (si demanda)
14 E-Invoicing
15 RBAC / approvals enterprise
16 Multi-entity / multicurrency / intercompany
```

---

# 29. Qué NO debe hacer Astra

No construir todo en una sola PR.

No modificar simultáneamente:

- facturación,
- contabilidad,
- VERI*FACTU,
- bancos,
- fiscalidad,
- reporting.

No crear 40 tablas sin tests funcionales.

No dejar dos fuentes de verdad permanentes.

No contabilizar mediante LLM.

No usar `float` en Financial Core.

No permitir editar entries posted.

No permitir saltarse period close.

No asumir que invoice status equivale a saldo contable.

No mezclar PDF con representación fiscal estructurada.

No crear microservicios prematuramente.

---

# 30. Regla de entrega por fase para Astra

Cada fase debe terminar con:

1. código.
2. migración.
3. tests unitarios.
4. tests PostgreSQL.
5. tests de concurrencia si aplica.
6. documentación.
7. migration/rollback plan.
8. feature flag.
9. comparación legacy vs nuevo si aplica.
10. actualización de `docs/Estado-actual-main.md`.
11. actualización de `docs/Registro-QA.md`.
12. actualización de `docs/Tareas-vivas.md`.

No empezar la siguiente fase hasta que la anterior tenga invariantes verdes.

---

# 31. Primera tarea concreta que debe ejecutar Astra

## PR 1 — Financial Core foundation

Crear únicamente:

```text
src/noesis/core/money.py
src/noesis/economic_events/
src/noesis/accounting/
docs/architecture/ADR-001-financial-core.md
```

Migración:

```text
economic_events
accounting_accounts
journal_entries
journal_lines
```

Pero en esta PR **solo** implementar posting de un único caso:

```text
invoice.issued
```

Flujo:

```text
issue_invoice()
     ↓
EconomicEvent(invoice.issued)
     ↓
PostingEngine
     ↓
JournalEntry balanced
```

No cambiar todavía dashboards ni impuestos.

Tests obligatorios:

- invoice standard 21 %.
- IVA 10 %.
- IVA 4 %.
- IVA 0 %.
- varias líneas con tipos distintos.
- IRPF.
- rectificativa.
- replay.
- idempotencia.
- concurrencia.
- Decimal.
- una empresa no puede acceder al ledger de otra.

Cuando esto sea sólido, avanzar a Open Items.

---

# 32. Segunda tarea concreta

## PR 2 — Receivables

Añadir:

```text
open_items
settlements
receivables/
```

Al emitir factura:

- posting.
- AR OpenItem.

Al registrar cobro:

- settlement.
- posting 572/430.

Comparar:

```text
legacy remaining_amount
vs
open_item.open_amount
```

Deben coincidir siempre.

---

# 33. Tercera tarea concreta

## PR 3 — Supplier invoices / AP

Añadir posting y open items de proveedor.

No cambiar todavía interfaz.

Cada `received_invoice confirmed` genera:

```text
Expense/Purchase
VAT input
Payable
```

El mapa de categoría → cuenta debe ser configurable.

---

# 34. Cuarta tarea concreta

## PR 4 — Tax Ledger

Crear TaxLines simultáneas al posting.

Comparar contra `tax_quarter()`.

No retirar legacy aún.

---

# 35. Quinta tarea concreta

## PR 5 — Bank Reconciliation v2

Migrar conciliación sobre OpenItems y accounts 572.

Soportar positivo y negativo.

---

# 36. Sexta tarea concreta

## PR 6 — Financial Reports

Crear:

```text
trial balance
P&L
balance sheet
AR aging
AP aging
```

Activar solo para admin/test.

---

# 37. Séptima tarea concreta

## PR 7 — Period Close

Después de que reporting cuadre.

---

# 38. Punto de corte para pilotar

No esperar a implementar enterprise.

Podéis empezar pilotos reales cuando estén terminadas y validadas:

```text
Fase 0
Fase 1
Fase 2
Fase 3
Fase 4 básica
Fase 5 básica
Fase 7 reporting básico
```

Es decir:

- facturar.
- cobrar.
- registrar proveedor/gasto.
- banco.
- IVA.
- P&L.
- Balance.
- gestoría.

Todo desde una fuente de verdad coherente.

Accounting close completo puede llegar durante pilotos si se limita claramente el alcance.

---

# 39. Criterios para decir “Noesis tiene un Financial Core serio”

No usar marketing. Deben cumplirse técnicamente:

- 100 % de entradas posted balanceadas.
- replay determinista.
- idempotencia.
- AR reconcilia con GL.
- AP reconcilia con GL.
- bancos reconcilian con GL.
- Tax Ledger reconcilia con GL.
- Balance siempre balanceado.
- periodo cerrado protegido.
- audit trail.
- Decimal end-to-end.
- multiempresa aislada.
- ninguna IA puede modificar ledger directamente.
- documentos y eventos enlazados.
- test PostgreSQL real.

---

# 40. Criterios para decir “Noesis está preparado para empresa mediana”

Además de lo anterior:

- RBAC.
- approval policies.
- AP workflow.
- centros de coste.
- activos.
- payroll integration.
- cash forecast.
- external bank feeds.
- e-invoice.
- observabilidad.
- audit exports.
- closing workflow.

---

# 41. Criterios para decir “Noesis está preparado para enterprise”

Solo más adelante:

- legal entities.
- multicurrency real.
- intercompany.
- consolidation.
- advanced audit controls.
- SSO/SAML.
- SCIM.
- segregation of duties completa.
- advanced treasury.
- SLA y DR maduros.

No construirlo antes de tener mercado.

---

# 42. Visión final de producto

La interfaz no debe convertirse en un ERP complejo.

Para el autónomo:

```text
“Factura a Marta 800 más IVA.”
“¿Quién me debe dinero?”
“¿Puedo comprar la furgoneta este mes?”
“Pásale el trimestre a mi gestor.”
```

El usuario no necesita ver:

```text
430
477
572
TaxLine
JournalEntry
OpenItem
```

pero deben existir detrás.

La complejidad contable debe estar en el motor, no en la experiencia.

---

# 43. Principio estratégico de Noesis

El objetivo no es ser un ERP al que se le añadió WhatsApp.

El objetivo es:

> **construir un sistema financiero y operativo completo cuya interfaz natural sea conversar y trabajar como ya trabaja una pequeña empresa.**

WhatsApp es la interfaz.

El Financial Core es la infraestructura.

La IA es el intérprete y copiloto.

El motor determinista es la autoridad.

La gestoría es el supervisor profesional.

Los datos estructurados son la ventaja acumulativa.

---

# 44. Instrucción final para Astra

Astra debe priorizar en este orden:

```text
correctness
integrity
traceability
idempotency
security
explainability
UX
speed of development
```

En software financiero, una función incompleta pero correcta es preferible a una función “mágica” que pueda crear inconsistencias.

Antes de implementar una nueva función financiera, Astra debe responder:

1. ¿Cuál es el Economic Event?
2. ¿Genera asiento?
3. ¿Qué cuentas afecta?
4. ¿Genera TaxLines?
5. ¿Genera/compensa OpenItems?
6. ¿Qué dimensiones tiene?
7. ¿Qué permisos requiere?
8. ¿Es reversible?
9. ¿Es idempotente?
10. ¿Funciona en periodo cerrado?
11. ¿Cómo se audita?
12. ¿Cómo se prueba?

Si esas preguntas no tienen respuesta, no implementar todavía.

---

# 45. Resultado esperado

Cuando este masterplan esté ejecutado hasta la fase de reporting/tesorería, Noesis habrá pasado de:

```text
SaaS que administra facturas, gastos y trabajos
```

A:

```text
Financial Operating System para pequeñas empresas
```

sin perder su principal ventaja:

```text
el usuario puede operar el negocio desde WhatsApp
sin aprender contabilidad ni un ERP complejo.
```

