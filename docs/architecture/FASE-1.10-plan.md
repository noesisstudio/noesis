# Fase1.10 — referencia aprobada y corrección1.10A

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
