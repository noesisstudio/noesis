# Auditoría de hashes/canonical — diseño, sin reescritura

[Mapping](SCHEMA-LINEAGE-75-80-mapping.md), [contrato](SCHEMA-LINEAGE-75-80-contract.md).
OLD = SHA870 legacyFinancial74–79; NEW = evidencia futura canónica.
N significa versión física exacta observada; S es SchemaBinding v1 verificado.
En serving/G normal N=80. Datos iguales no implican contexto/binding igual.

## Matriz completa de familias afectadas y dependencias

| Contenido | OLD FIELD / VALUE | NEW FIELD / VALUE | HASH IMPACT | LEGACY READ? | NEW WRITE? | REUSE ALLOWED? |
|---|---|---|---|---|---|---|
| Registry identity | version/name A74..F79 | CRM74+A75..F80 | Nuevo fingerprint de cada prefijo | Sí, clasificar legacy | Sólo callbacks nuevos autorizados | No para canonical |
| Applied timestamps | applied_at original | Mismo valor de filas ya aplicadas; nuevo timestamp sólo nueva migration | Excluido fingerprint; incluido backup row hash | Sí, exacto | Sólo fila nueva | Sí conservar, no editar |
| A evaluation row | evaluation_version1; schema_version74 marcador; provenance readiness_v1 | evaluation_version2; schema_version N75..80; provenance readiness_v2 | Row/context/result hashes nuevos | v1 histórico | v2 | No autoridad entre lineages |
| A context/result | schema_version74; hashes/context de A1 | S+physical N; sobre/result2 | context_hash/content_hash nuevos | Canonical original | Nuevos UUID/result2 | No |
| A capability proofs | proof canónico1, source/dependency refs | proof_version2+S, refs revisadas | proof_hash y grants derivados nuevos | Sólo inspección | v2 | No |
| A profile/policy | profile_version1/policy_version1, caps/dependencies | Igual contenido v1 | Igual hash si contenido igual | Sí | Versiones originales | Igualdad semántica, no permiso |
| B resolution request/result | resolution_version1; context/result/evidence_hash | revision2+S | Context/content/evidence hashes nuevos | Preservar v1 | v2 | No promover ni reusar como nueva autoridad |
| B source/event proof | IDs, revision, quality, source/event/operation hash | Referencias originales dentro de nuevo sobre2 | Fuente igual conserva hash; sobre nuevo cambia | Sí original | Nueva resolución | No editar pruebas antiguas |
| C coverage/EE/result | Fiscal coverage; EE amount=None/payload original | Misma semántica/versions; nuevos padres B/D bound | Evento preexistente intacto; nuevos IDs/result dependientes de padre pueden diferir | Sí | Captura sólo después de permiso futuro | No duplicar evento por renumeración |
| D schema baseline | D77 captura metadata A74/history | D78 captura metadata canónica A75/history/CRM | baseline content_hash nuevo (CHECK A y metadata cambian) | Conservar descriptor y hash77 | Baseline nueva al instalarD78 | No clonar baseline/clave vieja |
| D activation request | request_version1; schema_version77 fijo | request_version2; physical N78..80+S | request_hash y approved_hash nuevos | v1 bytes exactos | v2 | No reusar aprobación humana vieja |
| D transition/handoff receipt | receipt/schema/provenance sobre1 | receipt_version2+S y request2 refs | receipt/content/hash nuevos | Lectura histórica | v2 | No re-sellar |
| D generation/grant | previous/G/origin, profile/grant/proof/receipt hashes | Mismas reglas; sobres2/refs nuevas+S | Nuevos grant/generation-receipt hashes transitivos | Originales preservados | Nueva G sólo acción futura autorizada | No G+1 por renumerar |
| D pause snapshot/recovery request | snapshot/version1, config/financial/table hashes | snapshot/recovery sobre2+S | Sobre cambia; hashes de fuentes iguales siguen iguales | Sí bloqueante/conservación | v2 | No reutilizar pausa legacy como resume80 |
| History manifests/candidates | markers70..73, canonical1, historical v2, raw hashes | Contenido histórico igual, S sólo en consumidores nuevos | Sin cambio por sustitución; nuevos scans/refs propios pueden diferir | Sí | Contrato original con guard lineage futuro | Sólo preservación; no auto-promoción |
| History cut/storage/reconciliation | source_set/plan/result/rechecked/storage hashes | Mismos datos/hash originales referenciados por nuevo sobre | Original intacto; wrapper de binding nuevo cambia | Sí | Nueva auditoría sólo permiso separado | No «reparar» hashes para80 |
| EE/Operations/Auth monetarios | payload_version1/2, canonical económico, aprobación durable | Sin cambio automático | Hash existente idéntico; más refs nuevas sólo en nuevas operaciones | Sí | Sólo flujo futuro autorizado | No reejecutar/reemitir |
| E export manifest | contract_version1; schema_version78/79 real; canonical_version1 | contract_version2; N79/80+S; canonical_version1 | context/manifest hash nuevos | Reader v1 histórico | v2 | No READY con manifest viejo |
| E export sections | E78 vs F79 catálogo; table count/hash/total/snapshot_identity | E79 vs F80 por capabilities verificadas | Fuentes idénticas conservan hash; nuevas secciones/refs alteran total | Sí con su catálogo antiguo | Nuevo snapshot | No mezclar snapshots |
| E retention policy | policy content/version/provisional/approved_hash | Contenido/versión de negocio iguales; envelope evidencia2+S | approved_hash igual si policy igual; envelope hash nuevo | Bloqueos/supresiones siempre respetados | Nuevo sobre, aprobación profesional aparte | No elevar provisional |
| E closure/inventory/erasure/tombstone | sobre1+plan/human approved_hash/receipt refs | sobre2+S, plan/revisión exactos nuevos | Plan/receipt/envelope hashes nuevos | Conservación y denegaciones sí | v2 sólo autoridad específica | No reaprovechar autorización de cierre |
| E restore suppression replay | recibo/registro previo y source hashes | registro vigente, receipt2+S del target exacto | Replay nuevo; registro viejo jamás se borra | Denegaciones anteriores conservadas | Nuevo replay aislado/autorizado | No asumir actualidad del backup |
| F attestation | version1/checker_v1/schema79 | version2/checker_v2/schema80+S | attestation/content_hash nuevos | Sólo histórico | v2, sin checks reales en esta fase | No promover local/sandbox |
| F configuration/credential fingerprints | HMAC config/credential, environment binding | Misma política HMAC/env; S separado | HMAC igual si inputs iguales; attestation2 cambia | Sin exponer inputs | Nuevo recibo técnico futuro | No inferir permiso/check externo |
| F preflight | version1; context.schema_version79 | version2; context.schema_version80+S | context_hash/preflight_hash nuevos | Histórico, no nuevos enable/resume | v2 | No |
| F D-preflight/outbox bindings | sobre1=request/preflight hashes/requestHMAC | sobre2+S y referencias2 | Binding hash nuevo; HMAC sólo cambia si request canónico cambia | Conservar intentos/resultados | Nuevos bindings fuertes | No retry de UNKNOWN |
| F attempts/starts/results/observations | version1, IDs/ref hashes/result durable | nuevos sobres2+S, mismas reglas de resultado | Nuevos hashes por sobre/refs | Terminales y UNKNOWN originales respetados | v2 bajo autoridad futura | No fabricar observed/result/EE |
| RecoveryReadiness | version1; sin campo schema, guard externo79 | version2+S80 | proof_hash nuevo y preflight/receipt resume nuevos | A original/refs intactas | Nuevo proof verificado actual | No ampliar TTL A inicial |
| G VerificationContext | version1; **sin schema_version propia** | version2+S80, code/main/base/chain nuevos | context_hash nuevo | v1 histórico | v2 | No822 como current integration |
| G verified proof/GateResult/seal | proof/gate1 +context/evidence hashes/HMAC seal | proof/gate2+context2/S actual | Canonical/hash/seal nuevo por nuevas refs | No convertir JSON en autoridad | Sólo verifiers confiables futuros | No reuse REAL/synthetic |
| Deployment evidence | schema_version79 en metadata/replicas | 80+S por cada réplica/worker/scheduler | Metadata/context/proof hashes nuevos | Histórico | Nuevo collector autorizado | No aceptar sólo MAX80 |
| MAIN_INTEGRATION evidence | old base/integration/chain/CI refs | future main+canonical chain+V2 port+bridge+fresh CI/review, S80 | Evidence/proof nuevo | Histórico PASS conservado | Nueva revisión | No heredar review/CI |
| Backup V2 manifest | native-v2; manifest sin identidad explícita; schema_version numérico | native-v2; manifest_contract_version2; schema_identity(S+pares) | Manifest hash nuevo; formato dump nativo conservado | Reader antiguo técnico | Nuevo writer futuro | No editar manifest viejo |
| Backup dump/inventory | Registry/DDLs/data/sequence/doc hashes exactos | Snapshot nuevo conserva exactamente su registry/DDL/datos | Migrations nuevas y DDL hacen nuevo objeto/row/dump hash | Original verificable | Nuevo backup autorizado aparte | No parchear dump/applied_at |
| V1 header/stream | schema_version numérico y filas completas | Bytes originales; identidad derivada offline con runner correcto | No cambiar hash del archivo | Sólo catálogo exacto probado | No migrar V1 en origen | No legacy79=canonical79 |
| Object profile/lineage binding | No campo explícito común | descriptor revisado dialecto/N +S1 | Hash nuevo técnico | No inventar una observación antigua | Nueva observación read-only | No autoridad del hash |

## Reglas de versionado cerradas

- Nuevos sobres A/B/D/E/F/G que añaden S usan revisión2 de **su familia**;
  columnas/checkers/guards/version validators deben concordar. El binding usa1
  por ser su primer contrato; JSON canonical_version1 permanece1.
- No cambiar Profile1, specC1, economic payload1/2, policy/mandates/currency,
  history canonical1/v2 o rate/amount/UUID por coincidencia numérica.
- Versiones de checker/reader de código cambian sólo si ese algoritmo cambia,
  con contrato explícito; checker provider v2 se propone por su binding nuevo.
- Readers v1 preservan bytes, payload y hash originales. Sirven inspección/
  denegaciones/conservación, no autorización canónica; sin decode→rewrite→encode.
- Si referencia cambia, todos los hashes dependientes se calculan para **objetos
  nuevos**; nunca UPDATE de hashes/receipts antiguos. Igualdad de profile/source
  hashes no acredita nuevo environment/lineage/actor/TTL.
- Una prohibición legacy (cierre/supresión/UNKNOWN) se respeta aun sin binding
  nuevo; la ausencia de binding nunca se interpreta como ausencia de prohibición.
- No crear eventos económicos ni FinancialOperation de migración para
  «trasladar» evidencia. Artefactos reales existentes no se inspeccionan aquí.

## Trazabilidad del inventario estático

423 referencias clasificadas enSHA870,110 archivos; no todos requieren edición.
Registry migrations.py4590–4595; A schema.py26/evaluator335/repository137;
D activation_contracts60/handoff204/handoff_schema baseline; E export160/246,
retention151/159/repository63; F attestations64/contracts176/preflight138,
validation83/dispatch guards; G verification_contracts.value (sin schema),
verifiers73/262/280/289/371; recovery_readiness52; db.py13984; backups363.
Líneas corresponden al SHA histórico, no a un futuro diff. Docs ADR019–025,
contratos/órdenes/cierres/JSON antiguos se preservan como evidencia histórica;
adendas de nueva cadena se incorporarán sin cambiar su resultado original.
El gate documental de esta entrega verifica que esos archivos no se editaron.
