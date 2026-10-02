# Financial Operations v1 — infraestructura de Fase 1.2

No hay productores conectados. No se persisten Economic Events, links, asientos,
Open Items, Tax Ledger ni reporting. Los cinco flags financieros permanecen
apagados y sin nuevos consumidores. El API interno solo se invoca en tests.

## Entrada, identidad y contenido

`Principal(user_id, session_version)` viene del middleware/canal autenticado;
no se deserializa de argumentos IA. El servicio verifica esos datos contra
usuarios y negocio dentro de la transacción, incluso al recuperar resultados.
El modelo no tiene herramienta, endpoint ni acceso al API interno.

`EntryIdentity` deriva SHA-256 de componentes estables y namespace cerrado:

| Factory | Namespace | Fuente de identidad que debe aportar el servidor/canal |
|---|---|---|
| `web_api(request_uuid)` | web_api | UUID de envío resuelto por canal autenticado; conservar en reintentos |
| `chat(turn_uuid, proposal_revision)` | chat | Recibo durable del turno y versión concreta de propuesta |
| `whatsapp(provider_message_id, action_index)` | whatsapp | ID de mensaje validado por transporte y posición de acción |
| `document_review(document_id, revision)` | document_review | Documento del negocio y revisión confirmada |
| `recurring(schedule_id, cycle)` | recurring | Programación autorizada y ciclo civil explícito |
| `imported(batch_uuid, row_key)` | import | Lote estable y fila fuente |
| `historical(source_type, source_id, revision)` | historical | Origen cerrado, ID y revisión histórica |

Las factories derivan claves, **no autentican** un mensaje/turno/documento. Su
validación y pertenencia real al negocio corresponden al canal/servicio futuro.
Nada conectado en 1.2. No generar un UUID de envío nuevo en cada reintento ni usar
el hash del contenido como identidad. `operation_uuid` lo genera siempre el
repositorio con uuid4; el llamador no puede escogerlo al preparar.

`FinancialRequest` v1 exige campos explícitos: command_type, target_id, amount,
effective_on, expected_revision, reason y parameters. EUR y command_version=1 son
defaults constantes. Campos anulables significan **desconocido/no aplicable**,
no «usa el valor actual al ejecutar». No consulta hora, IVA o configuración al
canonicalizar. Los productores futuros deben resolver defaults una vez, incluir
todos los valores del efecto y validar su semántica por dominio antes de prepare.

Tipos cerrados de comando: invoice.issue, invoice.rectify, customer_payment.record,
supplier_invoice.confirm/correct/void, expense.confirm/void,
bank_transaction.import/match e invoice.fiscal_cancel. El comando determina el
dominio del target_id; no se construye una FK polimórfica a datos legacy.
El target y sus snapshots/revisiones se comprobarán en el futuro puente de dominio.

`parameters` contiene los parámetros/snapshots financieros adicionales explícitos;
se copia y congela recursivamente. La validación es estructural y exacta, no un
motor de cálculos ni validación fiscal del comando. No ejecutar directamente una
propuesta de IA por haber pasado este contrato. Rechaza claves de identidad o
autoridad, también anidadas: operation_uuid, entry_key, entry_namespace,
idempotency_key, business_id, authorization_uuid y approved_by_ai.

Todo float se rechaza, incluido en parámetros/resultados. Amount final admite
solo Decimal/string decimal exacto a céntimos; EUR exclusivamente. Decimal
intermedio en parámetros conserva su escala, rango y finitud. JSON financiero
solo strings decimales, nunca números decimales binarios. IDs enteros/flags bool
son datos no monetarios; su semántica se valida en el puente futuro.

JSON UTF-8 compacto con claves ordenadas, canonical_version=1 y payload/version
del comando incluidos; SHA-256 de los bytes. Se preserva texto Unicode original.
Límites: 64 KiB, profundidad 12, 256 elementos por contenedor, strings hasta 8192.
Decoder estricto: rechaza claves repetidas, NaN, infinito y números decimales JSON.
El request persistido debe reproducir exactamente esos bytes y su hash al leerlo.

## Schema final: migración 62

| Tabla | Columnas |
|---|---|
| financial_operations | business_id, operation_uuid, entry_namespace, entry_key, created_by, command_type, command_version, request_canonical, request_hash, expected_revision, state, authorization_uuid, result_version, result_canonical, result_hash, created_at, updated_at, committed_at |
| financial_authorizations | business_id, authorization_uuid, operation_uuid, kind, actor_user_id, recorded_by, actor_session_version, validated_permission, approved_request_hash, approved_revision, channel, mandate_uuid, authorized_at, expires_at, revoked_at |

PostgreSQL: UUID nativo, BIGINT en referencias, TIMESTAMPTZ, versiones INTEGER,
contenido/hash/estado TEXT. SQLite: UUID/instantes/contenido como TEXT, referencias
INTEGER. No dinero en REAL/DOUBLE/NUMERIC SQLite: request/result JSON canónicos
con strings exactos. Timestamps normalizados UTC desde el servidor.

- PK `(business_id, uuid)`; UUID unique global en cada tabla; unique de identidad
  de entrada por negocio/namespace. Unique compuestos adicionales sostienen FKs.
- Usuario enlazado por `(business_id, user_id)`; índice unique de usuarios para
  esta referencia, sin nuevas columnas o cambios a su comportamiento.
- Autorización enlazada a operación **y request_hash** del mismo negocio.
  Mandato referenciado por negocio/UUID. PostgreSQL añade FK diferida de la
  operación a su aprobación; SQLite impone la misma correspondencia con trigger,
  ya que no admite ADD CONSTRAINT y se evita un ciclo de creación de tablas.
- CHECKs de catálogo, versiones, revisión positiva, clases, nulabilidad y resultado:
  committed exige autorización, result_version=1, contenido/hash y committed_at.
  En otros estados todos los campos de resultado están null.
- Guards en ambos motores: insert prepared; identidad/request inmutables,
  transiciones válidas, aprobación correspondiente a hash/revisión/operación,
  terminales inmutables, no delete de evidencia. Una autorización asociada a una
  operación no cambia; el único update permitido en concesiones es revocación.
- Índices por negocio/estado/fecha y negocio/operación de autorización.
- Baja de cuenta: el camino legacy admite las tablas vacías y conserva su comportamiento.
  Con cualquier operación o concesión durable se rechaza explícitamente antes
  de eliminar datos. Integrar retención/exportación/cierre antes de productores.
- Downgrade 62→61 solo si ambas tablas están vacías; con evidencia/resultados
  falla y revierte la migración completa. No borrar datos para permitirlo.

## API interna pequeña

`FinancialOperations(business_id)` posee cada transacción mediante db.get_conn;
`OperationsRepository(FinancialSession(conn), business_id)` la recibe prestada.
El repositorio es infraestructura interna, no un API autorizado para routers/IA.

| Método | Garantía |
|---|---|
| prepare(principal, identity, request) | INSERT ON CONFLICT atómico y lectura bloqueada; misma identidad/contenido recupera operación original; distinto contenido da ConflictError |
| authorize(principal, uuid, channel, approved_hash, approved_revision, ...) | Recibo durable enlazado al request/revisión; prepared→approved solo humano o mandato válido |
| grant_mandate(principal, request, channel, expires_at, ...) | Concesión humana previa, exacta al hash/revisión, caducidad obligatoria; sin cron ni ejecución |
| revoke_mandate(principal, uuid) | Revocación durable de concesión propia, ordenada con la ejecución por lock |
| execute(principal, uuid, executor, revision_reader=...) | Claim por bloqueo; revalidación de permisos/autoridad/revisión; ejecutor+resultado v1+committed en una sola transacción |
| recover(principal, uuid) | Operación/resultado original tras verificar negocio, usuario activo, sesión y creador; no ejecuta |
| finish_without_effect(principal, uuid, rejected/cancelled) | Terminal sin efecto, idempotente para el mismo estado; no revierte un committed |

`executor(session, request)` es código de servidor de confianza; en 1.2 solo hay
ejecutores sintéticos en tests. El puente futuro debe asociarlo al tipo de comando,
validar semántica, entidad, snapshots y datos desconocidos; usar exclusivamente
la conexión prestada y no abrir/confirmar conexiones propias ni llamar proveedores.
No es un dispatcher ni un workflow engine. Commit de resultado es interno a execute,
sin método público que pueda marcar committed antes de un efecto transaccional.

Si expected_revision no es null, authorize/grant_mandate/execute requieren
`revision_reader(session, request)` de servidor, que lea el origen del mismo negocio
bajo bloqueo adecuado y devuelva la revisión actual. Una revisión antigua rechaza
antes del efecto; no se actualiza el request original. La revisión enviada por el
cliente por sí sola no prueba el estado del origen.

## Permisos y autorización

Cada llamada revalida usuario/negocio/versión de sesión. Solo el creador puede
consultar o actuar sobre la operación; ni otro usuario del mismo negocio ni un
administrador de otra empresa obtienen acceso por conocer UUID/key. Escrituras
exigen suscripción activa/trial vigente y no demo, con las reglas legacy.
Una cuenta en modo consulta puede recover con sesión vigente; no execute/prepare.
PostgreSQL retiene FOR SHARE de usuario/negocio mientras decide/ejecuta, y
FOR UPDATE de operación/autorización/mandato. SQLite serializa con BEGIN IMMEDIATE.

Confirmación humana: actor de la sesión autenticada, permiso financial.authorize,
hash/revisión aprobados, canal y timestamp. Solo evidence mínima; no conversación,
teléfono, token, nombre ni fila temporal completa en la tabla de autorización.
Mandato: autorización individual enlazada a concesión durable previa de contenido
exacto y mismo actor/negocio/sesión. Se comprueban alcance, caducidad y revocación
antes de aprobar y antes del efecto. No convertir un flag legacy de automatización
en mandato ni permitir variaciones de importe/fecha sin otra aprobación.
Procedencia histórica desconocida: actor original/session null, recorded_by
autenticado separado, permiso historical.record, canal historical; **no approved**.
Una aprobación humana posterior crea otro recibo; preserva el histórico desconocido.

Cambio de sesión/usuario suspendido invalida accesos antiguos y aprobación previa;
no hay renovación silenciosa. Nueva sesión permite leer según política vigente;
para ejecutar con otra aprobación se cancela y prepara otra identidad. Resultado
committed se recupera con acceso vigente, sin reejecutar ni renovar aprobaciones.

## Puerta futura de action_review y otros canales

Situación observada: respond obtiene payload, elimina pending en una transacción,
comprueba snapshot y llama run_tool después, fuera de esa transacción. Documentos
y WhatsApp tienen sus propias filas temporales/revisiones; chat no aporta aún un
recibo de comando financiero durable. Se conserva todo ese comportamiento en 1.2.

El puente posterior deberá: autenticar actor/entrada → fijar request/revisión →
prepare → verificar snapshot → authorize y confirmar su recibo → consumir la fila
temporal → execute usando el request durable. Una pérdida de respuesta antes/después
de execute deberá recuperar por la misma entrada/UUID, nunca reinterpretar el «sí».
Los consumidores futuros deberán enlazar propuesta con identidad durable antes de
eliminarla y conservar ese enlace para reintentos. No inferirlo de mensajes o de IA.

En 1.2 solo se añade esa advertencia a la docstring de respond. No se crea ninguna
operación desde run_tool, canales, documentos, facturas, cobros, banco o VERI*FACTU.
