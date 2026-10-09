# Financial Privacy / Export / Retention v1

Fuente de alcance: [orden E](FASE-1.10E-orden.md); decisión: [ADR023](ADR-023-financial-privacy-export-retention.md).
Código: `src/noesis/financial_privacy/`; pruebas compartidas SQLite/PG en
`tests/test_financial_privacy.py` y `tests/postgres_financial_privacy.py`.

## Contratos y autoridad

Versión de contrato 1, canonical financial_privacy_v1, schema soportado (78,).
JSON cerrado, claves ordenadas, ASCII y separadores compactos; SHA256 de bytes
UTF-8. Rechazo recursivo de float JSON. Decimal finito → string decimal exacto;
legacy float finito → objeto legacy_binary64/provenance/exact_money=false.
NULL sigue NULL; fechas naive siguen naive; no inferir UTC ni saldos.
Esta serialización es evidencia, no una operación contable ni posting.

Purposes cerrados: portability, audit, gestoria, account_closure.
Permisos de control plane: privacy.financial.export, privacy.financial.plan,
privacy.financial.close, privacy.retention.approve. La política/aprobación de cierre
rechazan permisos financieros generales. No hay endpoint IA ni permiso inferido
de readiness/global admin. Los llamadores internos son código confiable y deben
comprobar el propósito; HTTP exige sesión existente. Principal se valida por
business_id + user_id + session_version + is_active. Lectura de cuenta cerrada
sólo por control plane privado explícito y mismo actor del cierre con SV invalidada;
jamás por cookie web vieja. IDs técnicos no son tokens de acceso.

## Export y snapshot

FinancialEvidenceExporter.export(principal, export_uuid, purpose, client_id=None,
include_legacy=False) abre una sola conexión de lectura. PostgreSQL fija
REPEATABLE READ READ ONLY antes del primer SELECT; SQLite mantiene BEGIN de
lectura. Páginas internas de 256 filas, orden cerrado, sin truncar a 500 ni gate
de negocio durante el escaneo. Se materializa el resultado completo en memoria:
no es streaming HTTP ni garantía de memoria constante. Al terminar el snapshot
una TX breve con gate revalida sesión y registra el manifest inmutable.
Si cierre invalidó la sesión, el export se rechaza entero y no se entrega snapshot.
El mismo UUID/contexto/snapshot devuelve el manifest original; cualquier cambio
de propósito, actor, versión, cliente, fuentes o contexto produce conflicto.
El manifest propio se excluye del snapshot para evitar autorreferencia.

Formato: {manifest, sections}. Manifest cerrado: export_uuid, business_id,
purpose, client_id, contract_version, canonical_version, schema_version,
code_version, snapshot_identity, created_by, session_version, created_at con zona,
sections(table→count/content_hash), total_hash, final_result=complete,
context_hash, include_legacy, warnings, limitations. verify_export es puro:
valida versiones/campos/tipos, counts, cada hash, snapshot y contexto.
Un hash de contenido demuestra integridad, no firma pública/autenticidad externa.

Catálogo revisable único: `financial_privacy/catalog.py` (61 secciones financieras
de fuentes/EE/Operations/coverage/channels/history/A–D), más ocho tablas E y
financial_restore_suppressions. Incluye EE/links/secuencias, Operations/Auth,
provenance, coverage, outboxes fiscales, fuentes/documentos, B, evaluaciones A,
generaciones/grants/transiciones/authorities/source witnesses/effect commits D y
toda historia de diagnóstico/corte/importación/reconciliación. Canonical y hashes
almacenados permanecen originales, incluidos los unknown de histórico.
EE y Operations se verifican al leer; corrupción rechaza export, no se normaliza.

No export: password/reset hashes, OAuth/access/refresh tokens, sesiones/cookies,
provider/Stripe/API/DB/env secrets, HMAC signing key,
financial_execution_verifier_key ni baseline criptográfica global. Las columnas
son allowlist literal, nunca SELECT * expansivo. Documentos sólo metadatos/hash
SHA256 existente, sin filename/stored_name/rutas ni bytes. Hash ausente sigue
ausente, no afirmar integridad de bytes no leídos.
No se copian chat, memoria, resúmenes de acciones IA ni mensajes entrantes completos
al FinancialEvidenceExport; compatibilidad conserva sus claves como listas vacías.
Correo outbox sólo metadatos, sin text_body/html_body. PII fiscal existente se
conserva donde necesaria, no se duplica en manifest/inventario/receipt/tombstone.

Account/client HTTP usan el Principal autenticado y añaden financial_core al
formato anterior, attachment y no-store. El subgrafo de cliente usa FKs fuertes
de factura→pagos→bank_payment_links→banco/EE/operaciones/autorizaciones/coverage;
no sugerencias bancarias, joins por nombre/texto ni saldos inferidos. Relaciones EE
requieren ambos extremos propios. Global history/control/policy no se atribuye a
un cliente y se excluye. Otros clientes/negocios nunca entran. Gastos/proveedores
sin relación fuerte no se atribuyen al cliente. Los hijos de trabajos/proyectos
se incluyen sólo por relación al cliente. Campos originales fiscales se conservan.

La delegación legacy sin Principal sigue siendo lectura interna saneada sobre un
snapshot: no registra manifest E, no acredita readiness y no es acceso HTTP.
No llamarla para una exportación profesional durable; pasar Principal explícito.
No loggear contenido: únicamente UUID/bid/purpose/result si se instrumenta.

## Política e inventario

RetentionPolicyv1: version, policy_uuid, status, reference y diez rules cerradas:
category, basis_reference, mode, purge_after=NULL, review_status. Categorías:
fiscal_legal_record, financial_provenance, activation_authority, fiscal_transport,
supporting_document, operational_personal, credentials_secrets,
communications_support, privacy_request_evidence, qa_restored_copy.
Provisional exige hold_pending_review en todas. approved_for_operation requiere
confirmación del hash exacto por actor actual y referencia identificadora sin PII.
La validación profesional de esa referencia es requisito operativo humano, no
prueba que el código pueda inventar. Ninguna policy real aprobada viene por defecto.
Los tests usan synthetic-test-only-not-legal-approval.
Fiscal/provenance/activation/transport/doc/privacy/QA sólo hold o retain_proof.
Personal/comunicaciones permiten minimización cerrada; credenciales invalidación
local. Ninguna regla v1 autoriza purga temporal. NULL no significa plazo legal infinito.

Inventario tenant sobre tablas existentes: counts, hashes raw, categoría/regla,
policyUUID/version/hash, legal_hold, approved_purge_date=NULL, eligible_fields
cerrados y other_fields=retained_no_action_v1. No copiar PII ni secretos: hashes
de origen efímeros se almacenan como prueba, no contenido. Inventarios append-only,
otra UUID para nueva revisión. Cambios de fuentes invalidan source_hash.
Campos con acción v1 se describen en ACTION_FIELDS; las otras columnas/tablas
continúan conservadas aunque la categoría diga minimizable. No hay borrado genérico.

## Cierre y cliente

privacy_requests(account_closure) abierta del mismo solicitante→inventario→plan
hash congelado: política, fuentes, control/generación, outboxes, pendientes,
retained/minimizable, acciones/limitaciones. Plan no cambia finanzas/acceso.
Autorización específica human_exact sobre ese hash/actor/SV. Sólo una autoridad
formal por negocio. Revalidar política más reciente aprobada, inventario vigente,
export previo completo account_closure de negocio, pausa si ever_enabled,
cero PREPARED/APPROVED ejecutables y cero dispatch incierto. Pending outbox
no se borra/reenvía: queda retenido sin claim. Histórico no equivale a pending live.

Aplicación bajo gate/TX único: receipt+tombstone+invalidación/minimización.
Receipt contiene hashes/refs/counts de filas seleccionadas y campos de acciones,
estado closed_restricted y pending_external_actions de revisión F/replay backups.
No afirmar que cada campo seleccionado cambió. financial_proof_hash se compara
antes/después; alteración de prueba hace rollback. Una excepción/crash precommit
revierte todo; postcommit retry exacto devuelve el mismo recibo y ninguna segunda
invalidación. No nuevo estado D ni cambio de G/grants/transiciones; ever_enabled
requiere pausa D previa. Nuevos efectos/epochs/resume/legacy financiero y claims
quedan bloqueados desde autorización formal. Ticket received solo no los bloquea.

Credenciales: desactivar usuarios/SV, hash password inutilizable, tokens portal/
workers revocados, OAuth local invalidado, invitaciones/support revocados, links
locales y reset inutilizados; conexiones inbound/outbound deshabilitadas localmente.
Sin llamadas de revocación a providers. Con regla personal aprobada se minimizan
phone/email/address/zone de clientes (nombre/NIF/ID conservados), email usuarios y
contactos leads. Con regla comunicaciones aprobada se vacía assistant_messages y
elimina pending_actions; business_memories y demás contenido sin acción se retienen.
Todos los documentos/bytes/identidades financieras quedan conservados.

Cliente con factura emitida/EE/pago/documento financiero/history no va al cascade.
Sin policy aprobada/principal actual: falla con conservación. Con policy aprobada
personal: privacy_request erasure, receipt y tombstone client_contact en misma TX,
sólo cuatro campos y portal propios; prueba financiera propia antes/después idéntica.
Otro cliente no cambia. Cliente sin evidencia mantiene el comportamiento legacy.
Cuenta con evidencia E/Core conserva bloqueo de baja física legacy.

## Restore, SQL y readiness

Tombstone cerrada sin PII: version, business_id, closure_uuid o suppression_uuid,
scope, category, policy_uuid, selector_version, selector técnico,
evidence_hash y applied_at. Bundle privado firmado del registro vigente contiene
sólo esas pruebas, expira en 15min. category es una lista ordenada de categorías
cerradas; el replay se deriva de scope/category, sin campo adicional actions. No exportarlo ni subirlo a Git/logs.
prepare_restored_database exige bundle válido/actual antes de servir; overlay
inmutable financial_restore_suppressions lleva cierres posteriores al backup.
Reaplicar account_local_access o client_contact según selector, no cerrar todo el
negocio por supresión de un cliente. Startup reapply_tombstones verifica hashes/
receipt y reaplica antes de scheduler. Los drills SQLite/PG usan este hook.

El operador de una restauración externa debe obtener el registro vigente después
de aislar la copia y revalidarlo al handoff del servicio. Un bundle anterior a una
supresión concurrente no acredita actualidad; mantener servicio cerrado y renovar
registro antes de habilitar. El backup solo no sabe qué ocurrió después. No se
implementa infraestructura de control plane remoto ni restore real en E.

Nueve tablas E append-only con FKs por tenant, guards firmados por conexión/TX,
bindings de body/columnas y actor/SV. noesis_privacy_context PG permite únicamente
los dos kinds E administrativos; conserva HMAC/backend/TX/search_path seguro.
El verificador financiero D original conserva restricción de login privilegiado.
No es posible usar restore context para emitir dinero D. SQL sin contexto/UUID/
hash/tenant/actor correcto se rechaza. Un dueño DB con DDL queda fuera del threat
model runtime. Migraciones previas no se editan; downgrade vacío78→77 admitido,
con cualquier evidencia E bloqueado.

Readiness E verifica export completo de negocio vigente y policy aprobada, no
cierre formal. La comparación económica excluye control/evaluaciones/capabilities
A para evitar autorreferencia del evaluator; A/D validan su propia continuidad.
Evaluaciones antiguas byte a byte. Sólo se retiran los dos motivos E; resto
F/banco/providers/history/continuity sigue igual. Provisional nunca habilita.
El cierre bloquea D desde guard compartido y SQL; no handoff/generation/flag.

Todos los bytes documentales se retienen: filesystem cleanup y sus crashes no
aplican en esta v1. Un módulo futuro que elimine bytes necesitará intento durable,
commit DB previo, cleanup idempotente y completion; no inferirlo de este cierre.
Custodia QA real: [runbook](FINANCIAL-QA-CUSTODY-RUNBOOK.md), sólo documentación.
