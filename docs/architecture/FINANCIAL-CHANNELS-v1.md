# Financial Channels v1 — contratos de servidor y canales

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

Solo Fase 1.8. Flag NOESIS_FINANCIAL_CORE_ENABLED OFF por defecto; los otros cuatro
flags no tienen nuevos consumidores. No activar negocios ni avanzar 1.9.

## Identidad y autoridad

| Canal | EntryIdentity de servidor | Actor y evidencia |
|---|---|---|
| Web | web_api(UUID de acción durable autenticada) | uid/sv del middleware, negocio propio, Origin/CSRF |
| Chat | chat(message UUID durable, slot 1) | web:uid:sv; localStorage de retry por negocio y sesión |
| WhatsApp | whatsapp_scoped(meta, recipient, business, wamid, slot/version) | titular real por teléfono vinculado/owner_email y sesión vigente; worker/customer sin esta autoridad |
| Documento | reviewed_document(review UUID, document ID, item, revision) | actor autenticado; transporte de origen enlazado para replay de primer SÍ |
| Recurrente | recurring(schedule ID, scheduled_for) | run único y huella de plantilla; humano confirma ocurrencia |
| CSV | imported(batch UUID, row key) | cuenta opaca/extracto exactos; confirmación por fila |

UUIDs vienen del canal autenticado o del scheduler, nunca del LLM. Dos mensajes
distintos con igual texto son intenciones distintas; retry del mismo recibo es
la misma. El contenido canónico valida concordancia y no se usa como identidad.
La UI conserva UUID hasta respuesta durable y comparte promesa ante doble click.
Nueva intención terminada → UUID nuevo. No generar otro UUID al perder respuesta.

## Servidor interno

`ChannelContext(business_id, Principal, EntryIdentity, actor, message)` es contexto
de servidor, propagado con ContextVar aislada por request/turno. message solo vive
en memoria; en evidencia se guarda hash. `FinancialChannels.propose(intent)`
acepta únicamente `{command,target_id,fields}` y llama al review del Capture.
Los diez comandos admitidos corresponden a los diez productores ya aceptados.
No admite fiscal cancellation, Domain Events ni ejecutores arbitrarios.

Money de canal es string decimal EUR, nunca JSON float. Canonicalización rechaza
claves reservadas anidadas y campos desconocidos antes de preparar. El NLU legacy
puede devolver float: el adaptador solo recupera un único lexema explícito en euros
del mensaje humano original, nunca normaliza ese float. OCR/lectura legacy se
interpreta y vuelve a mostrarse con cifras exactas antes de una aprobación nueva;
no se presenta como dinero exacto recuperado de almacenamiento binario histórico.

`propose` congela preview y request en enlace inmutable, sin efecto financiero.
Su recibo `review` liga identidad de transporte al request incluso al recuperar
una operación preparada por scheduler. Es un acuse sin autoridad; confirmación
usa UUID/recibo propio. Reutilizar UUID con otra finalidad/contenido se rechaza.
`confirm` requiere UUID/hash/revisión/decisión exactos, canal/actor/sesión/negocio y
pending ID cuando es conversacional. Autoriza por Capture; callback privada guarda
recibo y consume solo el pending exacto en la misma transacción. Expiración 30 min.
`execute` exige autorización y recibo durable, revalida y usa Capture. `replay`
consulta recibo de confirmación antes de otro pending; committed devuelve resultado.
`response/recover` consulta sin ejecutar. Entrega Meta/PDF/HTTP queda fuera del commit.

## API web cerrada

Todas bajo `/api/{business_id}`, middleware de sesión/CSRF/plan existente.

- POST `/financial-actions/prepare`: `{action_uuid,intent}`; documental añade
  `document_review:{review_uuid,document_id,item,revision}`, concordante con fields.
- POST `/financial-actions/confirm`: exclusivamente
  `{action_uuid,operation_uuid,request_hash,revision,decision:"yes"|"no"}`.
- GET `/financial-actions/{operation_uuid}`: recuperación de lectura; jamás execute.
- POST `/financial-actions/bank-csv`: `{batch_uuid,account_scope,content}` prepara
  y muestra cada fila; upload no crea movimientos ni autorización.

Respuesta transporta UUID/hash/revisión para vincular confirmación, y `reply`
humano con acción/destinatario/concepto/importe/impuestos/fecha pertinentes.
En JSON, `revision` es string decimal canónico o null: revisiones de origen pueden
superar 2^53 y JavaScript redondearía un número JSON. El servidor normaliza/valida
ese string a entero exacto; FinancialRequest y autorizaciones internas mantienen
su contrato entero. SÍ/NO y proposal_ref transportan el mismo string, sin parseFloat.
No muestra UUID de EE, hashes, asientos ni terminología contable en el copy.
No hay endpoint genérico execute. Flags OFF rechaza estos nuevos comandos.
Endpoints financieros legacy se bloquean antes de parsear/escribir cuando Core
ON o captura solicitada por body `capture_requested:true`/header explícito.
La UI común transforma las acciones soportadas a prepare/confirm y envía dinero
desde lexemas del formulario; floats monetarios se rechazan también en el cliente.

## Chat, tools y ActionReview

enviar_factura/registrar_pago/registrar_gasto son propuestas Capture con Core ON;
sin contexto autenticado fallan cerrado. El LLM no dispone de writers/EE.append/
Operations.execute. Borrador/presupuesto/agenda siguen en su dominio operativo.
ActionReview exige autorización durable antes del DELETE de pending. SÍ/NO usa
el request congelado, sin reinterpretar args. Corrección de importe crea nueva
propuesta/request/hash, cancela el anterior y exige otro SÍ. Otros cambios se
revisan desde formulario/borrador o revisión OCR; no se ajusta contenido aprobado.
Mensajes sin fuente durable no pueden mutar dinero. Audio conserva consulta,
pero no dispone de bridge financiero hasta añadir identidad de upload/turno.

POST chat añade `message_uuid` y `proposal_ref:{operation_uuid,request_hash,revision}`.
La UI conserva la tarjeta vista en sessionStorage por pestaña y el recibo de retry
en localStorage. SÍ/NO/corrección exige concordancia exacta con pending: una pestaña
antigua no aprueba la propuesta actual de otra. WhatsApp exige responder citando la
propuesta; el Meta ID saliente se resuelve en el outbox existente con negocio/teléfono
y clave op/hash. Sin cita falla cerrado. Otro SÍ citado recupera la misma aprobación
y conserva un pending posterior. El hash de recibo cubre texto/referencia/cita;
mismo message UUID con otra referencia falla. Un error de audio no borra pending
financiero. Una orden nueva cancela durablemente PREPARED antes de quitarlo.

## Documentos, banco y recurrentes

OCR/upload/clasificación prepara campos y nunca autoriza. Web review liga doc ID,
huella/clasificación/campos/hash. WhatsApp doc review conserva UUID/item/revisión:
el primer SÍ a OCR prepara preview financiero; el siguiente confirma ese request.
Cambio documental/clasificación bloquea; PDF batch/TODAS no autoriza un lote.
Avance de cola documental ocurre después del commit y puede recuperarse por replay.

Banco: API CSV por fila con cuenta/batch/extracto; incertidumbre entre extractos
requiere resolución de 1.6. Formulario multipart antiguo no tiene suficiente
identidad/contexto y queda bloqueado con Core ON. Match usa saldo/sugerencia real,
puede registrar un cobro y evidencia match; jamás dos cobros del mismo movement.

Scheduler: configuración operativa no es autoridad. Genera borrador y run únicos,
prepara por vencimiento y exige revisión humana. Tras crash de generación recupera
runs completos aunque next_run haya avanzado. Cambio/pausa/sesión/caducidad falla
cerrado; no emite automáticamente ni fabrica mandato. Run legacy sin huella no se
reconstruye. Delegación, renovación de propuestas caducadas y revisión de ocurrencias
con drift quedan bloqueadas hasta diseño explícito, nunca se ajustan silenciosamente.
Se exige plantilla `active`: el vencimiento final que la deja `ended` también
queda bloqueado. No hay reapertura ni emisión automática de esa propuesta.

## Diagnóstico, privacidad y rollback

Buscar operación/entrada, enlace op/hash, recibo/authorization UUID, estado y
contexto exacto; no reproducir manualmente writers ni cambiar el request aprobado.
Después de respuesta perdida, reenviar el mismo recibo o consultar resultado.
Metadata no archiva conversaciones. Actor/mensaje son hashes, preview/intent son
datos mínimos de la decisión. Baja/downgrade no eliminan evidencia; código anterior
puede funcionar sobre esquema aditivo. Exportación/retención completa y Meta real
no están certificadas en 1.8. [ADR](ADR-012-financial-channels.md),
[pruebas y criterios](FASE-1.8-cierre.md).
