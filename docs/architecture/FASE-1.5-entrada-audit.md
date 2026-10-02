# Auditoría previa — emisión capturada 1.5

Base real: main posterior a 1.4, esquema 64, árbol limpio y pull ff-only.
Orden humana: exclusivamente emisión F1/F2 y R1–R5; no 1.6 ni activación.

| Entrada | Motor actual | Identidad/aprobación durable | Decisión 1.5 |
|---|---|---|---|
| Web invoices/{id}/send | run_tool → pending → tools → adaptador → db | No UUID estable de envío ni recibo financiero | Legacy vigente con Financial Core apagado; captura explícita bloqueada sin contexto |
| Tools / chat | _enviar_factura → adaptador | Pending consumible; no recibo 1.2 | Pendiente 1.8; ningún argumento IA habilita captura |
| WhatsApp | confirmación → run_tool | ID transporte no enlazado a operación/aprobación | Pendiente 1.8; no inferir aprobación |
| Adaptador interno | db.issue_invoice | Solo invoice/client; no actor/sesión | Método explícito con operación durable; nunca fallback |
| db / demo | fachada → writer | Sin principal | Legacy; rechazar capture_requested |
| Recurrente / scheduler | writer normal 1.4 | Flag auto_issue no es mandato 1.2 | Pendiente 1.8; mismo motor |
| Servicio interno nuevo | Operations.execute → writer → append → resultado | Principal + EntryIdentity de servidor + request aprobado | Primer camino capturado real, sin endpoint/modelo |

Un servicio especializado compone el motor extraído, no lo duplica. Revisión de
aprobación incluye huella completa del borrador/líneas, cliente, emisor, serie,
perfil documental, configuración fiscal y defaults resueltos; no solo revisión
entera de invoice. Locks de filas dependientes durante comprobación/efecto.

Payload v1 cerrado no contiene líneas/cliente/serie. Versionar a v2 exclusivamente
los dos hechos autorizados; conservar v1 y sus bytes/hash. Migración 65 amplía
ese CHECK y añade cobertura inmutable por negocio/invoice/operación/evento;
FK diferida al evento antes de mutar garantiza fallo de commit sin evento.
Guard de v2 exige factura emitida y cobertura compatible. Nada de backfill.

Pruebas: contrato común SQLite/PostgreSQL, nueve puntos de fallo, stale de datos
dependientes, replay/conflicto, tenants, SQL directo de cobertura, carreras reales,
fixture fiscal 1.4, migración con evidencia v1 preservada y bajada protegida.

Exportación/retención/cierre con evidencia siguen como gate de activación 1.10:
la baja destructiva ya falla cerrada; esta entrega interna no activa producción.
