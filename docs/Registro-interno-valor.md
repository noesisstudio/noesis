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
  confirmación, estado, entidad, idempotencia y el booleano auditable
  `qualifies_for_wub` de esa instancia.
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

| Familia | Proceso | Puede contar para WUB | Momento observado |
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

La columna de taxonomía `counts_for_wub` solo indica que la familia es candidata.
Cada instancia calcula además `qualifies_for_wub` sin puntos ni pesos. Solo vale
`true` si la acción es candidata y procede de un contexto material de delegación:

- petición del usuario ejecutada por el asistente web o WhatsApp;
- propuesta proactiva de Noesis confirmada por el usuario;
- regla previamente autorizada;
- automatización identificada explícitamente.

Una operación realizada mediante un formulario ordinario queda como
`trigger_source=manual_form` y `qualifies_for_wub=false`. También quedan fuera por
defecto las integraciones que solo notifican un hecho externo. Se conserva esa
telemetría para auditoría, pero nunca incrementa WUB.

## Origen, canal y confirmación

Son dimensiones distintas:

- `trigger_source`: `manual_form`, `user_initiated`, `noesis_proposed`,
  `authorized_rule`, `automation` o `external_integration`.
- `channel`: `whatsapp`, `web`, `email` o `system`.
- `completion_mode`: `user_confirmed`, `authorized_rule`, `system_observed` o
  `external_confirmed`.

Así, una propuesta de Noesis aceptada por WhatsApp no se confunde con una regla
previamente autorizada que ejecuta el scheduler.

## Cálculos

- **WUB actual:** ventana móvil de siete días, útil para operación.
- **WUB oficial:** última semana cerrada, lunes 00:00 a lunes 00:00 en la zona del
  negocio.
- **Negocio WUB:** tres o más acciones núcleo con `qualifies_for_wub=true` en dos o
  más procesos.
- **WUB Rate:** negocios WUB / negocios elegibles.
- **Profundidad:** distribución de 0, 1, 2, 3 o 4+ procesos.
- **Consistencia:** semanas WUB de las últimas cuatro y racha consecutiva.
- **Trust:** propuestas ofrecidas, aceptadas, rechazadas y pendientes, más tiempo
  hasta confirmación, por proceso y familia. El modelo admite estados corregidos y
  revertidos, pero todavía no existen hooks de lifecycle conectados por proceso.

`transition_useful_action()` y los estados `corrected`, `reverted` e `invalidated`
son infraestructura disponible. La instrumentación de reversión por proceso queda
pendiente: en esta fase ningún flujo operativo llama todavía a esa transición y no
se declara cobertura real de correcciones o reversiones.

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

- `NOESIS_VALUE_LEDGER_ENABLED=false` es el valor por defecto y mantiene apagadas
  Useful Actions, Useful Outcomes y las métricas nuevas. La auditoría histórica en
  `assistant_actions` continúa escribiéndose; solo omite los cuatro campos de Trust
  añadidos por el esquema 53. Activarlo no cambia permisos ni flujos.
- `NOESIS_VALUE_LEDGER_ADMIN_ENABLED=false` mantiene oculto el endpoint interno
  `/admin/value-ledger`; al activarlo sigue exigiendo administrador y registra el
  acceso en la bitácora de seguridad.
- No se copian conceptos, descripciones, mensajes, nombres, teléfonos, emails,
  documentos ni notas. Solo IDs, taxonomía y metadatos acotados.
- Confidence, Delegation, Insight, Progress y Goals no tienen interfaz ni cambian
  autonomía. Necesitan primero datos reales del piloto.

## Rollback

La combinación `código 53 + esquema 52` **no está soportada**: el código 53 conoce
columnas nuevas de `assistant_actions` que PostgreSQL elimina al bajar a 52. La
secuencia segura es obligatoria:

1. Poner `NOESIS_VALUE_LEDGER_ENABLED=false` y comprobar que cesan las escrituras
   nuevas del ledger sin perder la auditoría preexistente.
2. Volver al código anterior manteniendo inicialmente la base en esquema 53.
3. Validar con ese código los flujos principales de facturación, clientes, cobros,
   agenda, documentos, presupuestos, WhatsApp y auditoría.
4. Solo después, si se necesita rollback completo, ejecutar el downgrade 53→52.

Nunca se baja la base a 52 mientras código 53 pueda seguir sirviendo tráfico.
PostgreSQL elimina las columnas aditivas únicamente en el paso 4. SQLite conserva
columnas inertes para no reconstruir tablas críticas. La prueba local ejecutada con
el código base `294ce375` sobre esquema 53 cubre negocio, cliente, trabajo, cierre,
factura, cobro, presupuesto y `assistant_actions`.

El primer despliegue es opt-in: preparar `NOESIS_VALUE_LEDGER_ENABLED=false` y
`NOESIS_VALUE_LEDGER_ADMIN_ENABLED=false`, migrar 52→53 en un entorno PostgreSQL no
productivo, ejecutar smoke, comprobar el producto, activar después el ledger y
reconciliar los datos piloto. Solo entonces se considera una activación gradual.
Antes se exige suite completa, rollback seguro y revisión de índices. Ninguna
métrica se muestra al cliente durante esta fase.
