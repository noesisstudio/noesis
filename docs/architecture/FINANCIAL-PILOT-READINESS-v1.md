# PilotReadinessReport v1 — G-PREP

[Orden](FASE-1.10G-prep-orden.md), [checklist](FINANCIAL-PILOT-CHECKLIST-v1.md),
[runbook](FINANCIAL-PILOT-RUNBOOK-v1.md). A–F CODE-VERIFIED PASS. Software verified
no equivale a real-world ready. G-LIVE NO AUTORIZADO; H NO INICIADA.

## Alcance y frontera de confianza

`financial_pilot/` es cálculo puro y tooling documental. No abre conexiones, importa
writers/adapters, llama providers ni escribe tablas. Reutiliza Profile/Capability/
canonical/digest de A, spec C y OperationalPolicy F. No crea state machine,
registry, provider layer, autoridad ni migration80. A–F permanecen byte a byte.

La API `prepare_report(PreparationContext(...), now=aware_datetime)` produce un
archivo calculado. `python -m noesis.financial_pilot --code-sha SHA` imprime JSON;
no lee un expediente externo, .env, credenciales, DB, producción, QA o backups.
`--business-id` y `--capability` sólo describen una selección humana presentada;
no acreditan que la cuenta exista ni que el perfil sea elegible. Sin selección
se conservan NULL y los dos blockers correspondientes. Exit 0 significa cálculo
correcto de un expediente bloqueado, jamás permiso de pilot.

Resultados del vocabulario: PILOT_READY / PILOT_BLOCKED. En esta implementación
G-PREP, READY está **reservado y deliberadamente no habilitado**: policy real
provisional, integración main pendiente y guard D productivo siguen vigentes.
Retirar esos blockers exigirá autorización separada y verificación real, no
editar JSON ni marcar un input como approved/pass. No se construye aquí un
verificador de evidencia externa sin acceso autorizado. Esto es un límite
explícito, no un fallo ni una política ficticia de aprobación.

## Contrato cerrado

Campos exactos: version=1, scope=G_PREP_ONLY, result, software_status,
context, context_hash, capability_closure, provider_requirements, blockers,
created_at, expires_at, activation_authorized=false, real_evidence_verified=false.
Context: code_sha hex40, source_context_hash hex64, business_id positivo o NULL,
profile A v1 o NULL, fiscal_required bool o NULL, findings cerrados.
Finding: reason_code + evidence_reference. Referencia: kind, content_hash,
business_id. Kind: missing/documentation/synthetic/unverified_real_reference.
No kind verified_real ni PASS/approval libre. Missing requiere hash/tenant NULL;
referencias de datos exigen mismo tenant, documental global puede tener tenant NULL.
Ni los IDs técnicos ni los hashes acreditan autoridad/autenticidad.

Blocker: reason_code del catálogo cerrado, evidence_reference, remediation fija,
responsible_party (rol, no nombre inventado), requires_external_action bool.
No URLs, paths, nombres, NIF, teléfono, email, texto de factura, respuesta provider,
tokens ni secretos como inputs. Floats/bools como IDs/versiones rechazados.
Remediaciones/roles se derivan del catálogo, nunca texto del solicitante.

Canonical A y SHA256; resultado inmutable por bytes, `.body` devuelve copia.
`PilotReadinessReport` rederiva el contenido completo y rechaza tampering de
closure/reasons/hash/authority/READY. Orden de campos/capabilities/findings
irrelevante; mismos inputs y fecha de observación producen mismos bytes/hash.
La fecha explícita forma parte del report; no se pretende igualar observaciones
distintas. Context drift exige nuevo informe; `current()` rechaza cambio de hash,
reloj anterior a created_at o expiración a 300 s, reutilizando TTL F.
Un informe ya caducado conserva su valor documental, nunca se vuelve vigente.

## Perfil mínimo derivado de C

| Alternativa | Request exacto | Closure | Providers | Valor / riesgo / situación legal |
|---|---|---|---|---|
| A recomendado | expense.confirm, expense.void | channel.web_financial, expense.confirm, expense.void | ninguno | Confirmación humana y anulación documental de gasto real, Operation/EE/coverage/continuidad. No demuestra caja ni IVA correcto para toda actividad. E profesional y resto de prerequisitos pendientes: no pilotable hoy. |
| B web + fiscal | invoice.issue, con VF requerido | channel.web_financial, invoice.issue, invoice.rectify, invoice.fiscal_cancel, provider.aeat_dispatch | AEAT_VERIFACTU | Emisión/rectificación/fiscal; efectos irreversibles externos y autorización fiscal profesional. Bloqueado por safe check/attestation, además del resto. |
| C web + canales | expense.confirm, expense.void, channel.whatsapp_financial, provider.email_delivery | esas cuatro + channel.web_financial | META_WHATSAPP, EMAIL_DELIVERY | Confirmaciones/comunicaciones financieras multicanal; entrega incierta/PII. Bloqueado por dos providers, además del resto. |

`channel.web_financial` solo no contiene comando financiero: no es pilot útil ni
cumple D. Un cobro exige factura antecedente verificada; no es el mínimo para EMPTY.
No banco. SupplierInvoice también es posible, pero se propone gasto con void
porque no exige simular una obligación/tesorería. Selección definitiva: titular.
Condición VF desconocida de invoice.issue conserva AEAT/cancelación por prudencia
y FISCAL_CONTEXT_UNVERIFIED; sólo condición real verificada podrá evaluar el modo
legal. No se cambia VF para excluir AEAT. Historia/privacidad son transversales:
ninguna propuesta elimina hallazgos de una cuenta, ni sustituye el perfil recibido.

## Catálogo y resultados actuales

ReasonSpec vive en `financial_pilot.report.SPECS`; incluye todos los mínimos de
la orden, usando SAFE_CHECK_UNIMPLEMENTED existente en F. Añade
FISCAL_CONTEXT_UNVERIFIED, REAL_EVIDENCE_NOT_VERIFIED,
PRODUCTION_ACTIVATION_NOT_AUTHORIZED y RESUME_READINESS_CONTINUITY_UNVERIFIED.
La tabla completa de acción/owner se encuentra en el [cierre](FASE-1.10G-prep-cierre.md).

El [expediente actual](FASE-1.10G-prep-report.json) no tiene negocio ni perfil
seleccionados, evidencia real ni conexión a fuentes: PILOT_BLOCKED. No afirma
que la historia de una cuenta real sea mala; HISTORY_BLOCKED indica que no está
verificada. Missing/stale/unsupported no se normalizan a éxito.

## Compatibilidad y límites

No modificación de safe_check, D producción, A–F, migrations, db.py, routing,
five flags o workflows. La política real sigue PROVISIONAL / PENDIENTE DE
APROBACIÓN PROFESIONAL; LEGAL_POLICY_UNAPPROVED + PRIVACY_NOT_READY obligatorios.
Export/readiness/handoff/attestation reales requieren permisos separados y TX
existentes; no se llaman durante G-PREP ni desde la CLI documental.

El retiro del guard D productivo y la recuperación después de caducidad de A
original son dos decisiones técnicas pendientes antes de G-LIVE. No se eluden
con IS_PRODUCTION=false en producción, reset de control, resume sin prueba,
otra generación, policy sintética o flag ON. No existe CLI pública de pausa real
en D; el runbook distingue pasos humanos y APIs internas que deberá exponer una
integración futura autorizada. Ningún comando ficticio se presenta como ejecutable.


## Continuidad G-VERIFY

G-PREP permanece documental/anti-READY, sin ingestión de approvals. La [capa de verificación](FINANCIAL-PILOT-VERIFICATION-v1.md) es separada y sólo acepta pruebas de verifiers, sin acceso real autorizado. La [continuidad D79](FINANCIAL-RECOVERY-READINESS-v1.md) resuelve el TTL A para nuevos resumes con proof actual; guard producción/policy real/flags siguen bloqueados. No afirmar real-world readiness ni G-LIVE. El cierre G-PREP anterior conserva su alcance histórico.
