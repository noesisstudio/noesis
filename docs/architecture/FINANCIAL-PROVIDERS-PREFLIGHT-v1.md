# Financial Providers y Preflight v1

Implementación local F CODE-VERIFIED PASS técnico; leer [orden](FASE-1.10F-orden.md) y
[ADR024](ADR-024-providers-integrated-preflight.md). No piloto ni autorización G.

Catálogo cerrado: AEAT_VERIFACTU/aeat_soap, META_WHATSAPP/meta_graph,
EMAIL_DELIVERY/brevo|smtp|gmail. La spec C declara provider.aeat_dispatch → AEAT,
channel.whatsapp_financial → Meta, provider.email_delivery → Email; web no añade
dependencia externa. Desconocidos fallan cerrados.

`ProviderAttestation` v1 contiene tenant/UUID/provider/implementación/capability/
environment/level/huellas de configuración y credencial/checker/código/schema79/
actor/sesión/checked_at/expires_at/result/reasons/evidence/source_attempt_uuid.
JSON canónico, hash SHA-256, sin float, PII, tokens, paths o respuestas libres.
Evidencia cerrada: configuration_valid, safe_check, certificate_sha256,
check_reference_hash, synthetic. Resultados PASS/BLOCKED. TTL máximo 300 segundos.

local_verified sólo acredita archivos/configuración local y fingerprints, sin red.
sandbox_verified acredita exclusivamente sandbox concreto. production_config_verified
requiere un check seguro específico del entorno productivo exacto. production_observed
sólo deriva de intento real durable SUCCEEDED; no admite preflight manual, mocks ni
SQL runtime sin contexto. No existe una escala numérica que permita subir de nivel.

`attestations.check` exige financial.providers.preflight; network_authorized está
apagado por defecto y los checks externos actuales bloquean incluso con permiso.
`verify` revalida tenant, capability, entorno, código, expiración y huellas actuales.
`readiness_evidence` sólo SELECT; evaluaciones A anteriores permanecen inmutables.
La IA no recibe estas interfaces ni autoridad financiera.

`FinancialIntegratedPreflight.evaluate/verify` congela evaluación UUID/hash, perfil
y cierre/dependencias, providers estrictamente requeridos, attestations UUID/hash,
policy/export E UUID/hash, fuentes/history/configuración, volumen, pendientes/
incertidumbre, estado/generación, límites, código/schema, actor/sesión y acción.
Sólo escribe recibo F; misma UUID/mismo contexto reproduce exactamente, distinto
contexto Conflict. PASS debe revalidarse antes de cada uso. BLOCKED conserva causas
cerradas, incluidas PRIVACY_NOT_READY y BANK_CAPABILITY_UNVALIDATED.

En schema79, D enable/resume requiere `preflight_uuid` y binding separado a request
exacto. Cambios internos off→validating→ready de esa solicitud no son drift externo.
Requests D77 y evidencia A–E anteriores no se reescriben. Guard de producción D,
cinco flags OFF y aprobación humana exacta se conservan.

Outboxes: relación explícita fuente/FinancialOperation/generación/capability/provider,
con huella HMAC del request. Fiscal usa coverage y record_id exactos, sin adoptar
legacy. Email invoice usa FK invoice→coverage→operation; WhatsApp recibe referencia
explícita del bridge o invoice productor. No inferir identidad de asunto/cuerpo/
importe/teléfono. Comunicación de propuesta no ejecuta su operación económica.

Cada binding admite un intento inicial durable. Start y resultados son inmutables;
SUCCEEDED, FAILED_TERMINAL, UNKNOWN_EXTERNAL_RESULT o ABORTED_BEFORE_IO. Nunca
repetir la llamada de un attempt. UNKNOWN requiere revisión externa explícita;
F no inventa exactly-once ni un resultado positivo de timeout. Resultado y estado
outbox comparten TX2. Telemetría no concede autoridad ni modifica Core.

Pausa: AEAT DRAIN_COMMITTED exclusivamente con obligación previa y generación
verificada; email/Meta HOLD_DISPATCH. Cierre E bloquea nuevos claims/drain. Un
resultado ya iniciado se conserva aunque la sesión original se haya invalidado.
F no llama providers durante esta entrega; todos los ejercicios son sintéticos.

El read model expone sólo estados, UUID/hash, contadores, edades y motivos cerrados.
No alerta remota ni cambios automáticos de flags/grants. Consultar límites y
procedimiento en [runbook](FINANCIAL-PROVIDERS-runbook.md).

Persistencia M79, exclusivamente evidencia de control/transporte:

| Tabla | Relación durable |
|---|---|
| financial_provider_attestations | Tenant, actor/sesión, configuración/credencial y source attempt sólo observed |
| financial_provider_preflight_runs | Evaluación A exacta y contexto congelado |
| financial_activation_preflight_bindings | Request D → preflight UUID/hash; separado del contrato D77 |
| financial_provider_outbox_bindings | Outbox → operación, generación, capability y request HMAC |
| financial_provider_dispatch_attempts | Un único intento por binding; attestation UUID/hash e idempotencia |
| financial_provider_dispatch_starts | Inicio único de ventana de posible I/O |
| financial_provider_dispatch_results | Un resultado terminal por intento, sin respuesta libre |
| financial_operational_observations | Metadata diagnóstica cerrada, append-only y sin autoridad |

Los guards verifican contexto privado de conexión/TX, hash canónico y actor/sesión.
Las FKs por tenant no se suspenden. El runtime PostgreSQL no puede leer la clave
del execution verifier. Un resultado ya iniciado conserva su derecho a registrar
la evidencia aunque se invalide después la sesión original; no abre otro intento.

El filtro legacy reconoce las plantillas financieras declaradas de factura,
recordatorio/propuesta de cobro y el namespace `financial-review:` del bridge.
Post-handoff, una fila reconocida sin binding queda retenida; nunca se adopta.
Las comunicaciones genéricas declaradas no financieras conservan su worker.
No existe clasificación por texto, importe, teléfono o destinatario.

Huellas: Meta incluye versión Graph, timeout y conexión exacta; Gmail incluye
cuenta, permisos, remitente y timeout; Brevo incluye sender/endpoint/timeout; SMTP
incluye host/puerto/remitente/usuario/timeout. Credenciales siempre HMAC privadas.
Los valores usados para calcular huellas no se copian a evidence, logs o export.

Backup sintético79 restaura Operations/EE/attempt/start/result exactos, incluido
UNKNOWN, sin iniciar delivery. PostgreSQL ordena las FKs inmediatas y comprueba
las diferidas antes de reactivar triggers USER. La FK circular F observed→attempt
es diferible sólo por solicitud explícita durante la restauración completa;
es inmediata en una transacción normal. Migraciones anteriores no se reescriben.

La baja legacy comprueba las ocho tablas F antes de borrar una cuenta en schema79.
Cualquier evidencia F bloquea ese borrado y exige cierre con conservación. El
inventario E clasifica todas las tablas tenant de F y no concede acciones de purga.
