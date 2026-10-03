# ADR-009 — Productor único de emisión capturada

## Adenda vigente 1.8H

El orden descrito en la entrega original queda corregido por
[ADR-013](ADR-013-financial-hardening.md): permisos → business gate → operación/
autorización → factura/fuentes. La frontera común aplica también a review,
prepare/reprepare, authorize y execute, sin nuevos efectos ni reglas fiscales.
Los canales resuelven la procedencia recurrente en el bridge común. Flags OFF;
no 1.9. [Evidencia y cierre](FASE-1.8H-cierre.md). Lo inferior conserva historia.

Estado: autorizado exclusivamente en 1.5, 2-oct-2026. No autoriza 1.6.
Base: main tras 1.4, schema64. [Auditoría previa](FASE-1.5-entrada-audit.md).

## Decisión

InvoiceCapture revisa datos reales y prepara FinancialRequest explícito; identidad
EntryIdentity y Principal proceden de código autenticado de servidor. Confirmar
hash/revisión crea evidencia durable 1.2 antes de ejecutar. execute delega en
FinancialOperations: permisos → operación/autorización → gate por negocio →
factura y dependencias → writer normal → evento → resultado → commit.
No duplicar motor, conexión, reglas fiscales ni autoridad humana. La IA carece de
acceso a este servicio. Ningún endpoint/turno/message-id actual aporta todavía
el puente durable completo: web/tools/chat/WhatsApp/recurrentes esperan 1.8.
El adaptador tiene issue_captured con principal + operación; db captura explícita
sin contexto falla. El flag global continúa False; si se solicita captura nunca
hay fallback a db legacy. No implementar activación por cuenta 1.10.

Aprobación cubre SHA completo del borrador/líneas/cliente/emisor, perfil documental,
serie (sin contador variable), configuración fiscal, plazo resuelto y fecha civil.
expected_revision complementa esa huella, no la sustituye. Locks FOR SHARE de
cliente/business/serie y FOR UPDATE de invoice protegen validación y freeze en PG.
Cambio relevante, medianoche o datos desconocidos obligan a revisar de nuevo.
El servicio de operaciones admite validador estático opcional previo al replay:
rechaza recuperar un comando ajeno por un servicio de dominio; no revalida datos
actuales ni reejecuta un committed válido.

## Contrato de hecho y precisión

v1 cerrado permanece byte a byte compatible. v2 solo para invoice.issued y
invoice.rectified: añade evidence cerrado con identidad/serie, emisor/destinatario,
líneas y tasas, IRPF, perfil/huella, fiscal record y source_fingerprint completo.
Payload y sobre inmutables; JSON monetario string decimal. Ningún nuevo tipo.
La ampliación de versión es necesaria para la orden posterior que pide líneas,
cliente y referencias fiscales; no cambiar v1 silenciosamente.

La emisión congela un borrador que ya reside en REAL/DOUBLE. WriterResult conserva
exact_inputs y prepared_values; cálculo Decimal existente se contrasta con filas
congeladas, componentes, líneas y registro fiscal al céntimo, antes de append.
La procedencia siempre declara legacy_binary_storage. No afirmar recuperación
de precisión de entrada anterior; ningún float canónico, migración monetaria ni
corrección silenciosa. breakdown_json fiscal es texto opaco original con esa misma
procedencia, no un nuevo cálculo ni representación monetaria exacta histórica.

## Cobertura y migración 65

invoice_economic_coverage es inmutable y se inserta antes del writer. PK tenant/
invoice; evento y operación únicos. FK compuesta diferida a evento (tenant/UUID/
invoice/tipo/operación) y a operación (tenant/UUID/state='committed') obliga al
commit de ambas evidencias, incluso si el llamador captura un fallo. Guard exige
borrador y operación approved del mismo target/tipo. Guard v2 requiere cobertura,
fuente emitida, tipo compatible y original de rectifies real. Toda nueva operación
invoice.issue/invoice.rectify exige cobertura antes de committed, aunque un ejecutor
interno intente omitir el productor. Resultado committed
coincide con UUID/ID/tipo/hash/número/importe/moneda del evento. Sin cascadas.
La cobertura requiere un evento v2 al confirmar; un evento v1 de infraestructura
no puede acreditar una emisión nueva ni permitir un resultado capturado sin emitir.

No nuevas columnas en invoices ni modificación de históricos. Amplía CHECK de
payload_version de economic_events. PostgreSQL ALTER constraint. SQLite reconstruye
events y links conservando columnas/IDs/bytes/hashes/relaciones, transacción
explícita y foreign_key_check; nunca apaga FKs. Copia local SQL de links evita el
contador diferido falso al DROP/recrear padre; no cargar toda la historia en RAM.
Bajada a64 solo sin cobertura/v2; evidencia v1 se conserva también al bajar/subir.

## Rectificativas, replay y efectos secundarios

R1–R5 siguen restricciones existentes, original inmutable, número/registro propios.
Solo invoice.rectified, relación rectifies al evento capturado válido original.
Sin evento original falla cerrado antes de emitir, sin historia inventada. La
política 1.2 de propietario de eventos se mantiene: no ampliar permisos entre actores.
UUID de evento UUIDv5(operation_uuid,'invoice.primary.v2'); slot primary. Retry
committed recupera resultado sin writer, secuencia, número, evento ni outbox nuevos.
Otra operación del mismo borrador queda stale tras la primera emisión.

VERI*FACTU conserva algoritmo/cadena/XML/QR/number/freeze/productor/registro/outbox.
El evento no participa en SHA fiscal. Lock común 1.4 intacto, sin red AEAT. value_ledger
se ejecuta best-effort después del commit y no puede invalidarlo ni repetirlo.

## Límites y rollback

Solo productores de emisión/rectificación. Flags apagados, sin GL, posting, compras,
cobros/banco/anulación fiscal, históricos ni activación. Canales/recurrentes 1.8;
retención/exportación/cierre antes de activar 1.10, baja destructiva ya bloqueada.
Revertir código conservando 65 preserva evidencia; no retirar cobertura ni despliegue
mixto que omita este protocolo. Downgrade con captura bloqueado.
