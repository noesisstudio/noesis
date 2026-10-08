# Runbook del futuro piloto v1 — G-PREP, no ejecutar

[Orden](FASE-1.10G-prep-orden.md), [checklist](FINANCIAL-PILOT-CHECKLIST-v1.md),
[contrato](FINANCIAL-PILOT-READINESS-v1.md), [F](FINANCIAL-PROVIDERS-runbook.md).
A–F CODE-VERIFIED PASS; G-LIVE NO AUTORIZADO; H NO INICIADA. Este runbook no
autoriza comandos de control plane, reads reales, red, deploy ni cron/alertas.

## Preparación local disponible hoy

En checkout local de G-PREP, usar el Python del proyecto con PYTHONPATH=src.
`python -m noesis.financial_pilot --code-sha SHA_COMPLETO` genera JSON por stdout
con business/profile NULL y blockers explícitos. Redirigir únicamente el reporte
documental saneado a una carpeta privada; no cargar dumps ni fuentes reales.
Para describir selección humana futura, --business-id ID y --capability por cada
capability exacta; eso sigue sin verificar cuenta/evidencia y permanece BLOCKED.
`--fiscal-required unknown` es el default conservador. No usar no para excluir
AEAT de facturación cuando no se haya verificado el modo fiscal real.

La CLI no tiene --activate/--approve/--check-network/--database/--backup.
No existe ruta de JSON import para retirar blockers. El reporte actual y las
alternativas se revisan por el titular; sin business/perfil elegido no hay pilot.

## Personas y responsabilidad

| Rol | Función | Estado actual |
|---|---|---|
| Primary operator | Revisa evidence/contexto; presente T0/2h; solicita pausa y conserva UUID/hash; no inventa certeza de dinero/provider | sin asignar |
| Secondary/on-call | Cobertura 72h; verifica worker detenido y UNKNOWN; mantiene hold ante falta de primario | sin asignar |
| Privacy/legal owner | Profesional revisa E/uso fiscal/retención/base legal y propósito real, titular confirma hash por mecanismo E | sin asignar/aprobación pendiente |
| Backup custodian | Copia/cifrado/clave/ACL/drill/replay E/freshness; conserva snapshot y cadena de custodia | sin asignar |

Engineering owner prepara integración/roles/keys/runbooks con autorización;
business holder selecciona cuenta/perfil y confirma cada operación económica real.
Una misma persona puede ocupar roles sólo por elección humana documentada. No IA
ni grants/admin global sustituyen esa decisión. Referencias de asignación quedan
en expediente privado; reporte sólo roles/hash, sin nombres/contactos.

## Futuras lecturas reales: plan, permiso y salida

1. Obtener autorización exacta: sistema, tenant, campos/queries, propósito, fecha,
   snapshot y destino privado. No heredar permiso antiguo de backup/1.9F.
2. Autenticar interactivamente sin mostrar tokens/URLs. Identificar origen real;
   registrar sólo referencia técnica saneada. No consultar Railway/QA ahora.
3. Ejecutar Q_SCHEMA sola. Si no es schema79, STOP: no ejecutar migrations/reads
   del Core nuevo ni afirmar compatibility. Plan de integración/rollout separado.
4. Reader especializado futuro recibe FinancialSession prestada del pool existente,
   snapshot REPEATABLE READ READ ONLY, 5s statement/1s lock timeout, tenant validado.
   SQLite sintético usa BEGIN de lectura. No crear pool ni guardar datos en db.py.
5. Consultar los fragmentos [SQL](FINANCIAL-PILOT-READONLY-QUERIES-v1.sql), sólo
   SELECT. Counts/UUID/hash/status/fechas/bools; nunca SELECT * / payload / secretos.
   Q_RUNTIME_ROLE/Q_KEY_ACCESS son metadata infraestructura autorizada, no fuentes
   de otros tenants. Dejar names de rol/DB en evidencia privada, no chat público.
6. Expected outputs: negocio exactamente 1; EMPTY counts cero; cierre cero;
   control off, G0, ever_enabled=false; A FULL vigente/perfil exacto; history
   certificado/E PASS; policy approved sólo tras profesional; export completo
   vigente; providers exactamente requeridos con proof real actual; runtime roles
   restringidos/clave inaccesible. Unknown/missing nunca equivalen a esos outputs.
7. Comparar hashes/tenant/expiry con verifiers SELECT existentes A/B/E/F; no
   ejecutar evaluator.evaluate, E.export/register_policy, F.check/evaluate ni D.
   `verify_readiness` incluye row locks: el futuro lector deberá usar predicados
   SELECT de fuentes existentes sin adquirir locks incompatibles con READ ONLY;
   no llamar mecánicamente a un verifier que escriba/tome FOR UPDATE en esa TX.
8. Report de observación privado cerrado: tenant, scope/query IDs, capture UTC,
   código/schema, resultados/counts/UUID/hash, source_context_hash, responsable
   humano, provenance real/autorización exacta. No PII raw ni respuestas provider.
   Su ingestión/verificación real aún no está implementada; references no son PASS.
9. Cerrar snapshot con ROLLBACK. Revalidar al T0; lectura pasada no activa ni
   representa el estado actual de producción. No volver a usar informe caducado.

## Runtime, código y claves: comandos propuestos, no ejecutados

Tras permiso separado Railway, operador identifica cada replica/web/worker/scheduler.
No usar `railway variables` sin filtro ni imprimir environment. Comando dentro de
**cada** contenedor, filtrado exclusivamente por código/esquema/flags:

```python
from noesis import config
print({"release_id": config.RELEASE_ID,
       "flags": {k: bool(getattr(config, k)) for k in (
           "FINANCIAL_CORE_ENABLED", "LEDGER_REPORTING_ENABLED", "OPEN_ITEMS_ENABLED",
           "NEW_TAX_ENGINE_ENABLED", "NEW_BANK_RECONCILIATION_ENABLED")}})
```

Comparar SHA con release Railway y code SHA de cada proceso; revisar imagen/version
de worker, no sólo filesystem en una replica. Q_SCHEMA y role/privilege checks
son lectura; no leer tabla verifier ni SECRET_KEY. Hash/HMAC usando configuración
F en reader confiable privado sólo después de permiso explícito para esa lectura.
SHA/booleans correctos no demuestran key usable: probar guards en clon sintético
del código/role, revisar gestión de claves por operador y mantener RUNTIME_KEY_NOT_VERIFIED
hasta prueba real autorizada. No hacer INSERT SQL de prueba en producción.

Integración futura: rama nueva **desde main vigente**, merge A–G en esa rama sin
rebase, resolver conflictos/nota sigue.md, CI general+18 PG completa y fresca,
inspección y autorización separada de merge/deploy. No se realiza hoy. Rollout
sin workers antiguos ni configuración IS_PRODUCTION=false para eludir D.

## Incidente y pausa D/F: procedimiento humano

Hoy D.transaction rechaza IS_PRODUCTION. No hay CLI pública ni acceso productivo
de pausa autorizados: es un blocker de preparación, no promesa de botón funcional.
La integración futura debe exponer estas APIs internas con auth humana específica;
no se ejecutan desde el reporte y no se elimina el guard durante G-PREP.

1. Detectar hard-stop en read model F/evidence; anotar hora, tenant, G, perfil,
   request/binding/attempt/receipt UUID/hash y reason. No copiar cuerpos ni secretos.
2. Operador ordena STOP de nuevos requests/claims en workers financieros del tenant.
   Suplente verifica procesos detenidos/inflight; bloquear nuevas entradas. No
   reiniciar, reencolar, borrar outboxes, editar flags o actualizar estado por SQL.
3. Con canal D humano autorizado futuro: `FinancialActivation(bid, code_version=sha)`;
   `prepare(principal, request_uuid, ActivationAction.PAUSE,
   pause_reason=PauseReason.INTEGRITY_INCIDENT|PROVIDER_UNCERTAIN|OPERATOR_REQUEST)`.
   Revisar request/hash/G/revision/session/expiry; titular confirma hash exacto;
   `authorize(principal, request_uuid, approved_hash=request.content_hash)` y
   `advance(principal, request_uuid, 'paused')`. No aprobar automáticamente.
4. Verificar receipt durable y control.state paused, misma G, ever_enabled
   conservado, PREPARED/APPROVED canceladas y mandates revocados. EE/Operations
   committed/history/grants/generaciones previas se conservan. Si pausa denegada,
   mantener STOP físico de nuevos workers/ingress y escalar; nunca fallback legacy.
5. Email/Meta HOLD_DISPATCH. AEAT sólo DRAIN_COMMITTED con binding exacto de operación
   committed/G/capability/fiscal record y attestation actual, sin cierre E. El operador
   no adopta registros legacy, cambia G ni llama dispatch por este runbook.
6. Un START anterior puede conservar resultado TX2 después de pausa; verificarlo.
   Cierre E domina y detiene nuevos claims/drain. No borrar UNKNOWN/pending.
7. Revalidar incidente/snapshot/E/export/providers/history/config/flags/code/roles,
   ausencia de incertidumbre y vigencia A original/F. Resume usa nuevo request D,
   confirmación exacta y preflight F actual; crea G+1 sólo tras autorización futura.
8. Si A original caducó, recovery está bloqueado en D79: **mantener paused**.
   Resolver contrato/operación de recuperación con autorización técnica posterior;
   no sustituir A, resetear G, borrar recibos ni poner false ever_enabled.

## UNKNOWN: nunca retry por el modelo

1. Identificar tenant → binding → Operation/source → G → attempt → START → result.
   Sin START no afirmar I/O; con START y sin resultado existe ventana incierta.
2. Parar y comprobar worker original (PID/instancia y no inflight), mantener HOLD.
   No asumir muerte por TTL ni recuperar mientras pueda escribir resultado.
3. Leer metadata/HMAC/idempotency/ref/fechas, no contenido libre. Con receipt terminal,
   replay devuelve receipt, **no** envío. Sin START, claim puede iniciar su única
   llamada futura autorizada; no hacerlo como resolución de UNKNOWN.
4. Tras parada confirmada, API F interna `FinancialProviderDispatch(bid).recover_unknown(binding_uuid)`
   conserva incertidumbre de START sin resultado. No hace I/O ni vuelve a llamar.
   Si ya existe otro resultado, conservarlo; no fabricar SUCCESS/FAILED.
5. Consulta externa específica exige permiso aparte y personal cualificado:

| Provider | Cómo contrastar | Quién decide | Qué nunca repetir / cuándo retry |
|---|---|---|---|
| AEAT | Registro concreto y cadena/identidad/hash en portal/consulta oficial autorizada, con asesor fiscal; referencia privada saneada | operador + titular + responsable fiscal | No retransmitir/cancelar para ver qué pasa. F no tiene contrato de reconciliación manual externo ni corrección de result inmutable. Duplicado válido sólo parser/registro exacto; no clasificar timeout como rechazo. Mantener manual review hasta procedimiento autorizado. |
| Meta | Dashboard/logs de cuenta y message reference exacta si existe, sin leer chats completos; sin referencia no hay certeza | operador + titular | No resend de UNKNOWN ni reset attempt. Evidencia de entrega/ausencia por sí sola no autoriza operación económica ni nuevo binding. Nueva comunicación sólo necesidad real, confirmación y protocolo posterior autorizado. |
| Email | Logs Brevo/Gmail/SMTP del request/message-id concreto, sender y ventana; ausencia de log no es prueba de no entrega | operador + titular | No reenviar UNKNOWN ni cambiarlo a FAILED para permitir retry. Revisión manual/protocolo autorizado; no revocar credenciales como parte de investigación automática. |

Registrar decisión humana/ref/hash fuera de PII, mantener result original y guardar
la evidencia de incertidumbre. No existe API F de overwrite o retry de un attempt:
ningún plazo, doble clic, pausa/resume o IA permite repetirlo. START recovery sólo
conserva UNKNOWN. No crear EE por resultado de transporte.

## Monitoring reutilizando F

Usar `financial_providers.observability.read(session,bid,principal)` sobre snapshot
prestado: state/G/grants/handoff refs, preflight/expiry, attestations/expiry,
pending/unknown/errors, colas/edad, history/fence/diagnostics, E/readiness/closure.
Edad naive puede ser NULL: no inventarla. Complementar backup freshness/drill y
compatibilidad runtime con expediente privado; F no monitoriza almacenamiento remoto.
Continuidad/source hashes se contrastan con pruebas A/B/D/history. Read model no
renueva attestations, crea observaciones, alertas, approval ni autoridad financiera.
Pantalla externa/dashboard nuevo, notificaciones y polling automático no implementados.

## Hard-stop

Ante cualquiera: PAUSE / STOP PILOT, conservar evidencia y no continuar:
integrity mismatch, efecto económico duplicado, stale G, EE inesperado, UNKNOWN,
credential/config drift, preflight expirado, E/privacy/policy invalid, backup
no disponible, fallo guard SQL, anomalía cross-tenant, cadena fiscal incoherente.
También expiry A/providers, closed/closing E, runtime inconsistente o volumen >64.
Warning no convierte BLOCKED en READY. TTL no libera fence ni autoriza retry.

## Primera operación y observación futura

Propuesta perfil mínimo: un **gasto auténtico necesario**, pequeño, con documento
real y categoría/importe EUR revisados; titular presente confirma request/hash.
ExpenseCapture conserva source/coverage/Operation/EE atómicos; receipt verificable,
export/continuidad exactos, sin caja ficticia. Void sólo si corrección real necesaria,
conservación documental; no borrar evidencia ni prometer reversibilidad fiscal.
Si no existe gasto necesario, **no hacer operación**. No factura cero/falsa, cliente
inventado, gasto de prueba ni banco simulado en negocio real. No es pilot de factura.

| Momento propuesto | Revisión por personas |
|---|---|
| T0 inmediato | autorización/identidad/perfil/G/evidence vigentes, recibo y efecto único, control/hashes/queues |
| +15 min | continuity, EE esperado, pendientes/UNKNOWN/drift, provider expiry y backup |
| +1 h | actor/grants/G/colisiones/retries/queues, E/closure y hashes |
| +2 h | cierre de atención activa, handover al suplente, incidentes y disponibilidad |
| +24 h | freshness/drill/guard/code/providers/config, cambios/reconciliación y revisión humana |
| +72 h | expediente de observación, decisión humana mantener/pausar; no cierre H automático |

Dos horas activas y 72 h observación son propuesta, **no SLO**. TTL A/F/providers
de 5 min exige verificación every_use; no se promete que un único preflight cubra
72 h. No programar automations/alertas. Cada hard-stop prevalece sobre calendario.


## Continuidad G-VERIFY

G-PREP permanece documental/anti-READY, sin ingestión de approvals. La [capa de verificación](FINANCIAL-PILOT-VERIFICATION-v1.md) es separada y sólo acepta pruebas de verifiers, sin acceso real autorizado. La [continuidad D79](FINANCIAL-RECOVERY-READINESS-v1.md) resuelve el TTL A para nuevos resumes con proof actual; guard producción/policy real/flags siguen bloqueados. No afirmar real-world readiness ni G-LIVE. El cierre G-PREP anterior conserva su alcance histórico.
