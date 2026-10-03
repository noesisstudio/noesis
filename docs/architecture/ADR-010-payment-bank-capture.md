# ADR-010 · Captura de cobros y evidencia bancaria

## Adenda vigente 1.8H

[ADR-013](ADR-013-financial-hardening.md) corrige los defects auditados sin
ampliar funcionalidades: business gate precede operation/source incluso en
prepare/reprepare y lecturas FOR UPDATE; DELETE permitido devuelve OLD en PG,
con reparación de instalaciones existentes; el bridge resuelve procedencia
recurrente con sesión prestada para todos los canales y una identidad económica.
Consulta COMMITTED exige creador/negocio/sesión actual, no sv histórico;
PREPARED/APPROVED y aprobación/ejecución conservan la autoridad original.
Sin reescritura de evidencia. Flags OFF; no 1.9. Las descripciones inferiores
con orden anterior de locks se conservan como contexto histórico, supersedido
por esta adenda y su [validación](FASE-1.8H-cierre.md).

Estado: aceptado para implementar exclusivamente 1.6 (2026-10-02).

## Diagnóstico previo

Los writers prestados crean cobros con transacción compartida y snapshot exacto,
pero la conciliación no conserva el ID del pago. El hash por contenido del CSV
legacy no demuestra identidad entre extractos. Las columnas monetarias de esos
orígenes siguen siendo REAL/DOUBLE con procedencia binaria explícita.

## Decisión

PaymentCapture compone Operations, autorización durable, writer existente,
evento v1 y resultado en un commit. `payment` es el slot del único hecho de caja;
`settles` exige la factura capturada válida, sin backfill. Parciales congelan
importe y evidencia de factura; pueden coexistir si el saldo bloqueado lo permite.
Full/remaining congelan además todas las filas de cobro y su fingerprint:
cualquier cambio exige nueva revisión. No se ejecuta «lo que quede».

BankCapture importa con cuenta opaca, UUID de batch, fila y hash del extracto.
Contenido idéntico con otra fila conserva dos movimientos. Entre batches de la
misma cuenta es una posible duplicidad: requiere decisión humana explícita
«movimiento distinto», motivo y candidatos congelados; nunca prueba duplicado.
El batch queda vinculado a una cuenta/extracto y no se reinterpreta en un retry.
La revisión CSV es pura y prepara requests, sin aprobación ni ejecución automática.

Match reutiliza el writer bancario: movimiento bloqueado, factura bloqueada,
pago, estado y vínculo bank→payment. El productor común crea `payment`; `match`
crea Evidence-only, con `matches` al pago de la misma operación y `evidence_for`
a la importación original. Dos eventos; una sola entrada de caja.

Tres coberturas específicas reservadas antes del writer enlazan por FKs diferidas
evento y operación committed. Solo se permite adjuntar una vez el ID recién
creado; no existe reserva incompleta que pueda commit. Guards del resultado
exigen cobertura completa y relaciones. La tabla bank_payment_links tiene FKs
por negocio y es inmutable; también guarda el vínculo de futuras confirmaciones
legacy, sin reconstruir confirmaciones históricas.

## Límites

Servicios internos con Principal real; canales pendientes de 1.8 y flags OFF.
Solicitud de captura sin contexto falla cerrada. Payloads v1 sin cambios, EUR,
Decimal/string; snapshots de almacenamiento binario declarado. Migración 66
aditiva, sin GL, AP, Tax, consumidores, backfill ni Banking 2.0. Downgrade y baja
destructiva bloqueados cuando exista evidencia; retención/exportación pendiente.

## Validación exigida

Contrato compartido SQLite/PG, procesos PG, fallos en cada frontera, guards SQL,
paridad legacy y suite general, gates y autoauditoría antes del cierre.
