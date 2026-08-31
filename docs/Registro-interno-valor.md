# Registro interno de valor, WUB y confianza observada

> **Estado:** candidato implementado en esquema 53; no desplegado ni visible para
> clientes. La auditoría administrativa está apagada por defecto.

## Propósito y frontera

Esta capa registra trabajo administrativo que **ya ha terminado correctamente** en
Noesis. No decide fiscalidad, no concede permisos, no cambia estados de negocio y no
ejecuta acciones. Sus escritores se llaman después del commit principal y fallan
abiertos: si medir falla, facturar, cobrar, agendar, enviar o confirmar sigue
funcionando igual.

Los flujos existentes conservan sus contratos. La taxonomía es código determinista;
ninguna IA decide qué cuenta, calcula WUB o atribuye un resultado.

## Modelo de datos

El esquema 53 añade, siempre filtrado por `business_id`:

- `useful_actions`: acción terminal, proceso, origen, canal, modalidad de
  confirmación, estado, entidad e idempotencia.
- `useful_action_events`: historial append-only de completar, corregir, revertir o
  invalidar una acción.
- `useful_outcomes`: resultado posterior y su atribución `direct`, `assisted` u
  `observed`, con importe opcional sin duplicarlo.
- `useful_action_outcomes`: relación muchos-a-muchos entre acciones y resultados.
- cuatro campos opcionales en `assistant_actions` para correlacionar propuesta y
  decisión sin crear un segundo sistema de permisos.
- `timezone` y `value_metrics_eligible` en negocio para delimitar semanas y excluir
  explícitamente una cuenta de métricas.

Las claves únicas son por negocio. Las relaciones compuestas impiden enlazar una
acción o un resultado de otra empresa. La exportación RGPD incluye las cuatro tablas
y el borrado de una cuenta las elimina en orden referencial.

## Taxonomía v1

| Familia | Proceso | Cuenta para WUB | Momento observado |
|---|---|---:|---|
| `job_created` | agenda | sí | trabajo creado |
| `job_completed` | agenda | sí | cierre guardado |
| `invoice_issued` | facturación | sí | factura numerada y emitida |
| `payment_reminder_sent` | cobros | sí | aviso encolado correctamente |
| `document_classification_confirmed` | documentos | sí | clasificación confirmada |
| `quote_prepared` | presupuestos | no | borrador preparado |
| `quote_sent` | presupuestos | sí | presupuesto enviado |
| `client_created` | clientes | no | reservado; todavía no instrumentado |

Los resultados v1 son `payment_received`, `quote_accepted` y `job_invoiced`. Un
cobro sin recordatorio previo es `observed`, nunca se presenta como causado por
Noesis. Un borrador o una visita no cuenta. Las acciones revertidas o invalidadas
quedan auditadas pero salen del numerador WUB.

## Origen, canal y confirmación

Son dimensiones distintas:

- `trigger_source`: `user_initiated`, `noesis_proposed`, `authorized_rule` o
  `external_integration`.
- `channel`: `whatsapp`, `web`, `email` o `system`.
- `completion_mode`: `user_confirmed`, `authorized_rule`, `system_observed` o
  `external_confirmed`.

Así, una propuesta de Noesis aceptada por WhatsApp no se confunde con una regla
previamente autorizada que ejecuta el scheduler.

## Cálculos

- **WUB actual:** ventana móvil de siete días, útil para operación.
- **WUB oficial:** última semana cerrada, lunes 00:00 a lunes 00:00 en la zona del
  negocio.
- **Negocio WUB:** tres o más acciones núcleo en dos o más procesos.
- **WUB Rate:** negocios WUB / negocios elegibles.
- **Profundidad:** distribución de 0, 1, 2, 3 o 4+ procesos.
- **Consistencia:** semanas WUB de las últimas cuatro y racha consecutiva.
- **Trust:** propuestas ofrecidas, aceptadas, rechazadas, pendientes, corregidas y
  revertidas, más tiempo hasta confirmación, por proceso y familia.

La elegibilidad excluye demos, altas posteriores al inicio de la ventana,
onboarding incompleto, acceso no vigente y exclusión explícita. En esta primera
versión el acceso se evalúa con el estado actual: todavía no existe un historial
temporal de suscripción con el que reconstruir exactamente elegibilidad pasada.

## «Todo bajo control»

Solo se puede afirmar dentro del alcance conectado. El cálculo reutiliza salud
operativa real: documentos pendientes, WhatsApp fallido o reintentando, Veri*Factu
rechazado/agotado, copias y errores conocidos de integraciones activas. Si existe un
fallo o una conexión activa no comprobable devuelve estado `unknown`; si hay
pendientes, `attention`. No se muestra aún al cliente.

## Operación, privacidad y acceso

- `NOESIS_VALUE_LEDGER_ENABLED=true` activa la observación. Puede ponerse a `false`
  sin alterar ninguna operación ni borrar evidencia previa.
- `NOESIS_VALUE_LEDGER_ADMIN_ENABLED=false` mantiene oculto el endpoint interno
  `/admin/value-ledger`; al activarlo sigue exigiendo administrador y registra el
  acceso en la bitácora de seguridad.
- No se copian conceptos, descripciones, mensajes, nombres, teléfonos, emails,
  documentos ni notas. Solo IDs, taxonomía y metadatos acotados.
- Confidence, Delegation, Insight, Progress y Goals no tienen interfaz ni cambian
  autonomía. Necesitan primero datos reales del piloto.

## Rollback

1. Poner `NOESIS_VALUE_LEDGER_ENABLED=false` detiene escrituras nuevas de forma
   inmediata sin despliegue funcional adicional.
2. La migración puede bajar de 53 a 52: elimina índices y tablas observacionales.
3. PostgreSQL elimina también columnas aditivas. SQLite las conserva inertes para
   no reconstruir tablas críticas; al volver a 53 se reutilizan.
4. Revertir los hooks no exige modificar datos de facturación, clientes, cobros,
   agenda, documentos, presupuestos, WhatsApp ni permisos.

Antes de desplegar se exige suite completa, migración 52→53→52→53, humo PostgreSQL
en un entorno no productivo y revisión de consultas con índices. Después, el piloto
debe comparar el ledger con casos reales antes de mostrar métricas al cliente.
