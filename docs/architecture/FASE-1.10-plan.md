# Fase1.10 — referencia aprobada y corrección1.10A

## 2026-10-08 — Fase 1.10G-PREP local, sin piloto

A–F CODE-VERIFIED PASS. F CI remota fresca [37743993745](https://github.com/noesisstudio/noesis/actions/runs/37743993745) PASS: suite general 2074/2072 PASS/2 skips/0 FAIL/ERROR, 2353.757 s; PostgreSQL687 y JS9 PASS. Esa prueba corresponde al SHA F, no es una nueva suite general de G-PREP.
G-PREP calcula PilotReadinessReport v1 puro en financial_pilot, sin conexión/estado/persistencia ni migration. Reutiliza A Profile/C spec/F límites; refs documentales/sintéticas no acreditan realidad y READY no está habilitado. Perfil recomendado expense.confirm + expense.void + dependencia web, sin providers; cuenta/perfil aún no seleccionados. Policy REAL provisional, PRIVACY_NOT_READY conservado; cinco flags OFF. G-LIVE NO AUTORIZADO, H NO INICIADA.
[Orden](FASE-1.10G-prep-orden.md), [contrato](FINANCIAL-PILOT-READINESS-v1.md), [checklist](FINANCIAL-PILOT-CHECKLIST-v1.md), [runbook](FINANCIAL-PILOT-RUNBOOK-v1.md), [cierre](FASE-1.10G-prep-cierre.md).
Rama local desde F exacta, no main/rebase/integración/push/deploy. Datos reales, QA, backups/providers/Railway no consultados. main divergente sólo eliminó sigue.md según orden; integración futura y CI fresca obligatorias. Guard D producción y recuperación con A original caducada requieren revisión posterior, no se eluden. Diagnóstico por report/context hash y reason cerrado; rollback sólo retirar estos archivos puros, ninguna DB que restaurar. Headers inferiores son historia.

## 2026-10-07 — F CODE-VERIFIED PASS técnico local

[Orden F](FASE-1.10F-orden.md), [ADR024](ADR-024-providers-integrated-preflight.md), [contrato](FINANCIAL-PROVIDERS-PREFLIGHT-v1.md), [cierre](FASE-1.10F-cierre.md). Registry único C; FinancialSession/gate/TX compartidos, sin lógica financiera grande en db.py. Attestations/preflight/attempts separados de autoridad/economía. HMAC de secretos, ninguna red en A/D. Post-handoff con binding explícito; UNKNOWN sin retry automático, pausa/cierre dominan. D sigue protegido en producción, cinco flags OFF y policy real provisional. Sólo fixtures sintéticos; sin push ni G–H.


## 2026-10-07 — Fase 1.10E local, CODE-VERIFIED PASS técnico

[Orden E](FASE-1.10E-orden.md), [contrato](FINANCIAL-PRIVACY-EXPORT-RETENTION-v1.md),
[ADR023](ADR-023-financial-privacy-export-retention.md), [cierre](FASE-1.10E-cierre.md).
E implementa privacidad/export/retención/cierre local exclusivamente. F–H siguen sin autorización.
Migration78 aditiva, catálogo cerrado y snapshot completo sin límites silenciosos.
Policy provisional no permite activación; revisión profesional real pendiente.
Readiness nuevo sólo retira los dos motivos E con evidencia válida; A antigua intacta.
Export/client/cierre conserva EE/Operations/history/A–D y documentos. Restore requiere
registro vigente y reaplica antes de servir. E no borra bytes ni consulta QA/backups reales.
Cinco flags OFF. No push/merge/deploy/providers/F–H. Resultados finales en cierre E.

## 2026-10-06 — Fase 1.10D, cierre local CODE-VERIFIED PASS

A/B/C CODE-VERIFIED PASS según la orden del titular.
[Orden D](FASE-1.10D-orden.md), [contrato](FINANCIAL-ACTIVATION-HANDOFF-v1.md),
[ADR022](ADR-022-activation-handoff-generations.md) y [cierre](FASE-1.10D-cierre.md)
son la continuación vigente; los encabezados posteriores son históricos.
D se trabaja únicamente en `codex/phase-1-10d`, sin push, merge ni despliegue.
La migración candidata es aditiva respecto de las fuentes; las CHECK de lifecycle
se amplían conservando las FKs y la evidencia histórica. Activación por tenant,
generaciones, grants exactos y contexto ligado a operación/TX; Decimal/EUR,
repositorios de dominio y conexión/gate/TX compartidos. Ninguna autoridad IA.
Después de ever_enabled, flag OFF o pause no permite fallback financiero legacy.
Pausa cancela operaciones pendientes y revoca mandatos; resume exige prueba D
sin drift y otra generación. El corte mantiene certifiable al quedar handed_off.
Borradores y preparación operativa siguen permitidos; transporte outbox se conserva.
No nuevos endpoints ni cambios de UI; el control plane es interno.
E/F/G/H no iniciadas; blockers de privacidad/export/provider siguen vigentes en A.
Cinco flags OFF. Sin producción, restauración real, backups ni providers.
D CODE-VERIFIED PASS local: criterios, resultados iniciales y retests se detallan
en el informe de cierre enlazado. E/F/G/H no autorizadas ni iniciadas.


## Adenda autorizada 2026-10-06 — exclusivamente 1.10C

[Orden](FASE-1.10C-orden.md), [contrato](FINANCIAL-CAPABILITIES-FISCAL-CANCELLATION-v1.md), [ADR021](ADR-021-capabilities-fiscal-cancellation.md), [cierre](FASE-1.10C-cierre.md).

A/B CODE-VERIFIED PASS y validadas por el titular. Base exacta en orden, rama
local codex/phase-1-10c; entrega local primero, no push. Productor fiscal existe
solo como API interna; su ausencia deja de ser blocker de implementación.
Preflight/privacy/export/continuity conservan bloqueos de A. No activar perfiles.
Cinco flags OFF, D no iniciada. Encabezados inferiores históricos.
Monolito modular y repositorios especializados sobre FinancialSession/gate/TX
compartidos. Registry único de A con spec v1 y once mappings cerrados, sin
enforcement/routing. FiscalCancellationCapture interno reutiliza writer fiscal:
resolución B durable live/verified/resolved, revalidación every_use, autoridad
humana exacta, registro/outbox pendiente/coverage/EE evidence-only/result atómicos.
Decimal/EUR, total contextual del EE verificado, amount=None, snapshot real.
No nueva lógica grande en db.py ni autoridad IA. Migration76 aditiva protegida;
tuplas explícitas A/B/history. No provider I/O, activación, generation, handoff,
fence release o cambios de cinco flags OFF. Historical v2, observed_state,
mandates y rectificativas negativas bloqueadas por B se conservan.
No routing público ni 1.10D–H. Solo fixtures sintéticos, no producción/QA real/backups.

## Adenda autorizada 2026-10-06 — exclusivamente 1.10B

A validada. La [orden B](FASE-1.10B-orden.md) autoriza antecedentes durables
en rama dedicada desde la base exacta de A, solo fixtures sintéticos. Leer
[ADR020](ADR-020-financial-antecedents.md), [contrato](FINANCIAL-ANTECEDENTS-v1.md)
y [cierre](FASE-1.10B-cierre.md). Revalidación every_use con sesión/gate/TX
prestados; evidencia no autoridad. Cinco flags OFF. No activación, handoff,
fence release, routing, EE/Operations, producción, QA real ni C–H. Los párrafos
inferiores conservan la referencia aprobada y sus autorizaciones históricas;
esta adenda no cambia diseño ni outcomes/blockers del evaluator A.

Aceptación humana:2026-10-05.0–1.9 cerrado técnicamente con limitaciones;
1.9F conserva PASS WITH LIMITATIONS. Solo1.10A autorizada actualmente.
Este plan no autoriza implementación1.10B–H ni acceso/activación productivos.

## Arquitectura de referencia

Monolito modular, repositorios especializados y conexiones/TX compartidas.
Readiness/evidencia, autorización humana, activación y ejecución son distintos.
Elegibilidad durable por negocio + perfilversionado + conjuntoexacto y dependencias.
Solo FULL respecto a ese conjunto puede ser candidato futuroready. PARTIAL
requiere otra solicitud menor y reevaluación; no activa subconjuntos automáticamente.
HistoriaC/D o E BLOCKED bloquea transversalmente; no exclusions que oculten hechos.

Lifecycle futuro off→validating→ready→enabled→paused; paused reevalúa antes de
reanudar. ever_enabled monotónico; ningún fallback legacy tras incorporación.
A implementa únicamente off/validating estructurales y resultado de evaluación.

Handoff futuro: gate+TX→sesión/permisos→boundary→E revalidada SELECT sobre sesión
prestada→fuentes/eligibility/config→prueba durable→protecciónlive/generación→
transferenciafence→finalización→commitúnico. Nada de release y activación posterior.
El epoch deberá distinguir handed_off de released y conservar recibo del corte;
no se cambia nada de ese contrato enA. E actual abre TX y exige schema explícito:
D futura debe adaptar consumo prestado sin modificar pruebas anteriores.

AntecedentesB: resolver propósito/origen/fuente/revisión/calidad/prueba, conservar
históricos sin cobertura live ficticia. FKs y guards deben aceptar únicamente
prueba histórica o live verificada. B observado no promueve; invoice historicalv2
siguebloqueado; saldos no se infieren de status/registro_anterior/binary64.
Pending PREPARED/APPROVED anteriores pierden ejecutabilidad por generación;
nueva revisión/propuesta/aprobación, no edición de request/autoridad vieja.

Cancelación fiscal: bloqueada explícitamente mientras falte productor validado.
Si el perfil de emisión la necesita, no activar emisión antes de resolverla.
Cancelaciónfiscal≠reversióneconómica≠cancelacióndeuda.

FINANCIAL_CORE_ENABLED será disponibilidad global, no autorización por negocio;
otros4flags futuros siguenOFF. A no modifica consumidores ni config. Routing
por capacidad solo cuando existan todos los guards. Meta es capability separada:
no condiciona uso financiero porweb. Providers con pruebas local/sandbox/
producción diferenciadas, sin llamadas ahora.

Paused bloquea nuevos efectos, conserva consultas/export/resultados y seguimiento
deenvíosyaemitidos. Dispatch pendiente se drena o retiene segúncausa explícita,
sin borrarlo ni repetir resultados inciertos. Recuperación revalida cadena posterior
al handoff; PASS inicial no sustituye verificación de continuidad actual.
Rollback operativo pause/conservar/reparar/revalidar, nunca restore para deshacer
un envío AEAT o factura real.

QA: plazo operativo inicial30días desde aceptaciónG, inventario completo,
propietario/custodio/accesos mínimos/cifrado verificado; extensión explícita y
destrucción autorizada/acreditada posterior. No se destruye nada enA. Retención
financiera productiva independiente, requiere validación de plazos/política enE.
Export consistente por tenant con eventos/autoridad/provenance/history/activation,
hashes/contratos y evidencias necesarias, sin tokens ni claves ni datos ajenos.

Límites propuestos: un primernegociovacío; perfilhistoria máximo64items hasta
validación adicional; warninggate2s/hardstop5s/esperalock1s; ready5min,
warningcorte5min/intervención15min sin release; integridad rota pausa inmediata.
No sonSLO. Pilotprimero backup/restaurabilidad→emptyproof→dryrun→E→preflight→
confirmación→handoff→operaciónrealnecesaria→smoke/monitorización/pausa.
Rollout1→pocoscomparables→cohorteshomogéneas con autorización separada.

## Unidades y aceptación

| Unidad | Alcance |
|---|---|
| A | Contratos, catálogo, perfiles, evaluación durable y SQL, sin ready |
| B | Antecedentes/continuidad y FKs protegidas |
| C | Capabilities y cancelaciónfiscal requerida |
| D | Activación/handoff/generaciones/pausa/recuperación |
| E | Privacy/export/retención/cierreconconservación |
| F | Providers/preflight/observabilidad/límites/rehearsal |
| G | Piloto expresamente autorizado |
| H | Revisión independiente/cierre para cuentas seleccionadas |

A–F aceptadas antesdeG. Cierre1.10 exige perfil/capabilities preciso, E vigente,
cero blockers, handoff/crash/concurrencia demostrado, guardsglobales/tenant,
continuidad/autoridad/operacionesviejas, fiscalcompleto enámbitohabilitado,
providersalniveldeclarado, pausa/recuperación/export/privacy, límites/operadores,
piloto real y audit sin blockers. Testsverdes solos noacreditanreadiness.
