# ADR024 — Providers, preflight integrado y dispatch financiero

Estado: implementación local F CODE-VERIFIED PASS técnico. G–H no autorizadas.

Leer la [orden íntegra](FASE-1.10F-orden.md) y el
[contrato F](FINANCIAL-PROVIDERS-PREFLIGHT-v1.md).

F usa la spec única C y repositorios especializados sobre FinancialSession,
conexión, gate y transacciones compartidos. No crea otro registry ni clientes de
AEAT, Meta o correo. Separa evidencia, autorización, activación e intento externo.
Readiness y handoff sólo leen pruebas ya emitidas; nunca disparan checks de red.

Las attestations y recibos son append-only, tenant-scoped y firmados por contexto
privado de conexión/TX. Las huellas de credencial/configuración son HMAC con clave
derivada del secreto estable del servidor; el certificado público permite SHA-256.
Una credencial rotada requiere nueva UUID y nueva evaluación, no editar prueba.

M79 agrega tablas F y guards de control. D conserva su request v1/schema77 y sus
hashes; una relación separada exige preflight exacto vigente para enable/resume
en 79. Las matrices 77/78 prueban su semántica original explícitamente.

En exports schema79 la comprobación económica de readiness excluye recibos del
propio control plane D: de otro modo crear la solicitud invalidaría circularmente
su preflight. El export conserva esos recibos completos. F congela por separado
UUID/hash de policy y export; no omite ninguna fuente económica, operación, evento
o histórico. Schema78 mantiene su comparación anterior.

Dispatch: TX1 claim/attempt durable, start durable y revalidación antes de I/O;
provider sin conexión/TX/gate; TX2 resultado/outbox atómicos. Una respuesta perdida
tras posible entrega queda UNKNOWN_EXTERNAL_RESULT y no se reintenta sola.
AEAT puede drenar obligaciones committed de la generación pausada; correo y Meta
retienen. Cierre E domina. No nuevos EE/Operations como consecuencia de transporte.

Un upload/PDF directo carece de intento durable y se bloquea post-handoff. La
evidencia synthetic nunca habilita I/O real ni production_observed. Los checks
readonly externos permanecen SAFE_CHECK_UNIMPLEMENTED hasta validar un mecanismo
específico inocuo; F no finge production_config_verified real.

La política legal sigue PROVISIONAL / PENDIENTE DE APROBACIÓN PROFESIONAL. Los
límites F son operativos conservadores, no plazos legales ni SLO de producción.

La prueba de restore79 con operaciones committed encontró ciclos FK reales:
Operation/authorization (existente) y observed/attempt (nuevo). La restauración
ordena relaciones inmediatas, difiere únicamente las que PostgreSQL permite y
las valida antes de reactivar triggers USER. No desactiva FKs ni altera M63–78.
Downgrade79 conserva el bloqueo cuando existe cualquier evidencia F.
