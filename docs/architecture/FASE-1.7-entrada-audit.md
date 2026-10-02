# Fase 1.7 — auditoría previa

Base: main fb46eec, esquema66, árbol limpio y pull ff-only. Orden humana posterior
acepta1.1–1.6 y autoriza solamente1.7. No1.8 ni activación.

Escritores: purchasing.add/update/set_status/delete_received_invoice y
add/delete_expense; documents.record/confirm_received_invoice y ticket→expense.
Las fachadas db/documents poseen TX; los writers1.4 ya componen proveedor,
documento, clasificación y fuente sin I/O. No existe escritor de corrección de
gasto. OCR/upload/clasificación provisional nunca confirma por sí solo.

Lectores SQL inventariados: db.get/list_received_invoice, list/expenses_between,
project_cost_totals/list_projects/get_project_workspace, profit_and_loss,
month_billing, expenses_by_category y conteos internos. Gestoría, informes CSV/XLSX,
tax_quarter, resumen, chat y exportación operativa delegan en esos lectores.
Snapshot/lectura exacta y evidencia durable conservan acceso al origen retirado.
Los documentos conservan vínculos para auditoría; su existencia no suma costes.

## Respuestas previas — Master Plan §44

1. Cinco hechos v1: supplier_invoice.confirmed/corrected/voided y
   expense.confirmed/voided; ningún acontecimiento operativo nuevo.
2. Asientos: ninguno. 3. Cuentas: ninguna. 4. TaxLines: ninguna.
5. OpenItems/settlement: ninguno, incluso si status=pagada.
6. Dimensiones: negocio, origen/revisión, documento y proveedor existentes.
7. Principal autenticado, creador/sesión/suscripción, request y aprobación1.2.
8. Rollback total antes de commit; después corrección/retirada conserva historia.
9. Identidad de entrada y UUID de operación; replay devuelve resultado original.
10. No motor de períodos aún; no afirmar validación de cierre ni hacer posting.
11. Cobertura inmutable por revisión, antes/después, relación al último estado,
    operación/aprobación/resultado/evento, procedencia binaria explícita.
12. Contrato compartido SQLite/PG, concurrencia real, bypass SQL/API, omisiones,
    fallos inyectados, lectores y regresiones de fases anteriores.

## Decisiones de implementación

Dos coberturas específicas, reserva anterior a corrección/void y adjunción única
del snapshot final. FK diferida a operación committed y evento completo impide
confirmar una mutación parcial. Guards de origen bloquean UPDATE económico y
DELETE capturados sin productor autorizado. Continuidad compara proyección
económica completa, no status/nota ni UUID/fecha. Revisiones operativas pueden
crear huecos legítimos. Última cobertura se selecciona por revisión.

Migración mínima67: voided_at/void_reason en ambos orígenes, cuota IVA opcional
en gasto, coberturas/guards y actualización del trigger de revisión. Sin migrar
REAL/DOUBLE. v1 no admite proveedor en payload: conservarlo en proyección cubierta
y huella/procedencia, sin ampliar versión ni inventar campos.

Operativo permitido: status pendiente/pagada y nota de recibida; categoría,
proyecto y concepto se cubren conservadoramente como información relevante.
Cambios operativos revisionan pero no representan pagos. Fuentes retiradas se
congelan; no reactivación legacy. Canal/acción humana durable se exige solo en
servicios internos; bridges externos esperan1.8. Capture solicitado falla cerrado.
