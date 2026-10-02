# ADR-011 — Recibidas y gastos capturados, continuidad y conservación

Estado: aceptado dentro de la orden humana de Fase1.7, 2026-10-02.

SupplierInvoiceCapture y ExpenseCapture componen FinancialOperations1.2,
writers1.4 y EconomicEvents1.3 en una TX compartida. Confirmar requiere entrada
explícita aprobada; ninguna lectura documental autoriza dinero. No duplicar
reglas de creación/corrección de purchasing ni confirmar fuera de execute.

Cobertura específica por origen/revisión conserva before/after y antecedente.
Corrección/retirada exige continuidad con el último estado cubierto y revisión
actual bajo gate por negocio. Reserva pendiente solo permite una mutación; FK
diferida y guard del resultado requieren evento/relación/proyección final. Fuente
capturada no admite DELETE; void conserva fila, fecha y razón. Lectores operativos
filtran voided_at; evidencia lee directamente, sin purgar documentos/eventos.

v1 intacto. NULL monetario significa desconocido; cuota explícita opcional de
gasto, sin inferencia fiscal. Snapshot real, céntimos verificados y procedencia
legacy_binary_storage. No recuperar exactitud histórica de REAL/DOUBLE. Fechas
civiles separadas, occurred_at desconocido y observed_at UTC, sin accounting_date.

Status pagada es etiqueta operativa sin pago/settlement. Expense.corrected no
existe: futura corrección retira y crea otro origen, sin nuevo flujo ahora.
Flags OFF. Sin AP, GL, Tax, reporting, histórico, canales1.8 ni activación1.10.
Bajada bloqueada con cobertura/void/cuota explícita; preservar esquema al revertir.
