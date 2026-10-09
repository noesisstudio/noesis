# Fase 1.9F — Cierre del rehearsal aislado

Resultado: **PASS WITH LIMITATIONS — PASS técnico sobre restauración real; cobertura limitada**.
Se ejecutó exclusivamente1.9F con autorización humana expresa de2026-10-05.
No cierra Fase1.9 global, no autoriza1.9G/1.10 ni activación. Los BLOCKED de datos
son resultados correctos, no fallos técnicos convertidos en PASS.

## Origen, identidad y preservación

Backup lógico real de Noesis/Railway obtenido en preparación mediante lectura
autorizada:2026-10-05T15:02:45.910097Z,2136904 bytes,custom PostgreSQL,
origen18.6 Debian, UTF8/libc/en_US.utf8, esquema73. SHA-256:
`650d9652a4772bddcb5adc29da0c8818b3ef26a8897c6c1201b6c3e021e7dc14`.
Referencia privada fuera de Git: carpeta `NoesisPrivate/phase19f-20261005-160137`,
`backup/noesis-production-authorized-20261005.dump`; README-preparacion leído y
hashes de backup/snapshots verificados antes de1.9F.

QA: distroWSL2 Noesis19FQA, Ubuntu24.04.5, PostgreSQL18.6 PGDG; DB
noesis_19f_qa, rol local noesis_qa_operator sin superuser/createdb/createrole/
replication. Código runtime aprobado acff183319f476a5f0b25a820751dca4523fd8fd.
Marker NOESIS_19F_QA enlazado al SHA, host127.0.0.1:55444 exclusivamente dentro
de netns noesis19f; URL privada local solo en memoria, nunca en informes.
Restauración inicial completada2026-10-05T15:07:38.089340Z; baseline DB21853887 bytes.
Tipos físicos heredados DOUBLE PRECISION yNUMERIC (EE vacío); los574 campos
observados en fuentes monetarias seleccionadas conservan binary/NULL, sin conversión.
Schema inicial/final73; **cero migraciones**. El marker original de preparación
es evidencia de origen, no estado vigente: esta entrega sí ejecutó1.9F.

Snapshot inicial lógico SHA:
`4ff0caa1420a6f4d9997a6fa3f5a0f2be4fb0f8f2fee59acf9604e977308ac1f`.
Snapshot inicial físico detenido SHA:
`b47dfc4e87e6e941b421efdc747f51f5c4ae0bd2830bf86588bb951a19f0b0f2`.
Primer rehearsal preservado en /opt/noesis-19f/database/preserved-run1-data y
snapshot/rehearsal-run1-stopped-cluster.tar.gz, SHA:
`d43b8cb72fb6362f8f87d842545d1249e78f592fdac04b833c01e4708913cdcb`.
Segundo rehearsal preservado en snapshot/rehearsal-run2-stopped-cluster.tar.gz,
SHA: `614676f0e94cfa1b8afc0689e043e9def2cba07b45d405d2b7d0ed1d2e1926ec`.
Originales y datos privados nunca añadidos a Git; ACL exclusiva usuario/SYSTEM/
Administrators y VHD privado. Copias conservadas, sin destrucción.

## Aislamiento, privacidad y cero producción

Namespace solo loopback/sin rutas; capacidades eliminadas/no-new-privileges;
firewall secundario nftables, interfaces externas WSL abajo. Windows interop,
montajes Windows y systemd deshabilitados. Launcher root-owned valida aislamiento,
marker y autorización1.9F antes de cada ejecución. Noesis nunca se lanzó como
servidor/scheduler/worker; proveedores sin configuración, sin almacenamiento externo.
Pruebas IPv4/IPv6 TCP25/80/443/465/587/5432 y UDP53: ENETUNREACH, control
loopback positivo. Pruebas desde Windows y namespace Linux normal rechazan QA.
Probe final también PASS. Ningún socket externo de la aplicación puede alcanzar
AEAT/Meta/email/SMS/Stripe/storage/otros providers, aunque el dump contenga tokens.

Informes solo con seudónimos HMAC privados, counts/hashes/categorías. Logging del
harness deshabilitado antes de importar servicios y excepciones sanitizadas por
clase/frames; sin valores de excepción/raw SQL/payloads. Revisión final postgres.log:
0 patrones email/credenciales,0 STATEMENT y0 líneas parameters. Informes públicos
sin raw_canonical/payload_canonical/URLs ni PII literal; archivos privados de
selección conservan IDs solo dentro del Linux aislado. No se leen PDFs/conversaciones.
No hay prueba de anonimización criptográfica exhaustiva de texto libre: se evita su exportación.

Evidencia operacional: toda invocación del rehearsal usó QA launcher/netns,
identidad/rol propios y configs limpias; cero Railway/producción, migrations/fence/
epoch/manifest/eventos contra origen, cero flags/schema/deploy productivo. No se
consulta producción para readback ni se afirma qué hayan hecho terceros allí.
Git pull solo consultó el repositorio GitHub; ningún push/deploy en esta entrega.

## Baseline y selección

14 negocios restaurados, dos demo. Cinco no-demo con permisos existentes elegibles;
los otros nueve (incluidos demos/trials vencidos) se conservan sin alterar permisos.
Principal simulado exclusivamente en QA con usuario activo/session_version actuales
de la copia; no autentica al actor histórico ni inventa una aprobación original.
No se concluye que is_demo=false acredite historial de clientes reales.
Baseline física/lógica y hashes completos de95 tablas fuera del área permitida
histórica/operations/EE. Todos iguales tras ambos runs. Ningún efecto financiero legacy.

| Cohorte / seudónimo | Fuentes primarias | Items B | A/B/C/D | Diagnóstico |
|---|---:|---:|---|---|
| B-a755cb1dacec | 4 | 12 | 0/10/1/1 | BLOCKED |
| B-04ba43c7ff2e | 33 | 64 | 0/40/24/0 | BLOCKED |
| B-66dcecfda5d4 | 5 | 27 | 0/24/3/0 | BLOCKED |
| B-f148390f06dd | 20 | 54 | 0/53/1/0 | BLOCKED |
| B-c4e3190c97c2 | 0 | 2 | 0/2/0/0 | READY_FOR_REVIEW |

Pequeño/sintético: a755; actividad variada y mayor elegible:04ba; recibidas:66dc;
borradores/gasto: f148 (diagnostic solamente); control vacío:c4e3. Elección por
counts/tipos, sin nombres. Total159 items diagnósticos, A0/B129/C29/D1,
129 out_of_scope,30 pending_incidence;0 candidates/covered_existing/excluded.
B no equivale a candidato: aquí B son auxiliares y borradores fuera de alcance.
Incidencias agregadas: MONEY_BINARY_UNCORROBORATED30, SOURCE_HISTORY_LOST9,
MIGRATED_DOCUMENT_PROFILE9, SYNTHETIC_LEGACY_PAYMENT1. Dependencias7,
rotas7. PAID_WITHOUT_PAYMENT/rectification_missing/bank_ambiguity/fiscal_mismatch0
observados; varios escenarios ausentes, nunca inferir validación positiva por0.

## Evidencia monetaria y revisión interna

574 observaciones raw de campos monetarios **incluyen cantidades y tipos/tasas**:
561 legacy binary sin corroboración,13 NULL desconocidos,0 exact/corroborados,
0 subcéntimos materiales/no finitos observados;23 deltas binarios no cero.
Los números representables exactamente en binary64 siguen siendo legacy binary,
no evidence exact. Nunca convertir repr/cent candidato en Money aprobado.
Se contrastan bits y almacenamiento con readers originales, sin SUM/CAST/redondeo
silencioso. La ausencia de casos NUMERIC corroborados/subcent limita esta prueba.

Revisión por cada código y categoría presentes: los bloqueos concuerdan con bits
sin evidencia decimal, fuentes/perfiles/fiscal faltantes y marcador sintético.
No falso positivo/negativo identificado en esa muestra; no certifica ausencia global.
SOURCE_HISTORY_LOST y MIGRATED_DOCUMENT_PROFILE en invoices emitidas concuerdan
con ausencia de records y perfiles migrados/líneas sin marcador discriminante.
No revisión manual append-only ni override de clasificaciones para mejorar ratios.

Un invoice_payment registro_anterior en toda la copia: provenance migration_derived,
marker11, clasificación D/BLOCKED, sin candidato ni evidencia adicional autorizante.
Siete cobros seleccionados: uno sintético, seis también bloqueados.

Purchasing: tres recibidas y11 gastos; revisiones1, sin voids y sin reconstrucción
de correcciones. Gastos:11 _captured_vat_amount NULL, dos vat_rate NULL; no rellenar
con cero. Los campos NULL se conservan. Nota de evidencia: f_review inicial asumió
un campo vat_amount de expense que no existe; el recuento definitivo de unknown VAT
es repeat-verification.json por campos cerrados reales, no aquel contador inicial0.

Banco: cero movimientos/links/coverage en toda la copia. No prueba real de match,
identidad de import antiguo ni suggested_invoice_id; no matches creados.

Facturas seleccionadas41:32 borradores, nueve no borrador (6 cobradas,2 enviadas,
1 parcial). Las nueve necesitan resolver evidencia histórica antes de cualquier
vía invoice historical v2: falta de fiscal records, perfil migrado y dinero
uncorroborado, posibles líneas derivadas de migración sin marcador. Cero
rectificativas/cancellations/records/outboxes en la copia; hashes/perfiles fiscales
positivos no ejercitados. Se verifica únicamente evidencia existente, sin crear
nueva verdad fiscal; invoice historical v2 permanece bloqueado.

## C / D / E, reintentos y métricas

Se revisó B antes de abrir C. Cuatro epochs en QA, generation1. Sobres C
certifiable=true, boundary_current=true y eligible_for_import=false. Los carriers
B reutilizados mantienen mode=diagnostic/certifiable=false por contrato; el
sobre C es la autoridad de certificación, no el summary del carrier.
Sin drift y hash de comparación igual al conjunto fuente.

| Business | Items C | D | recorded / skipped / blocked | E | Findings |
|---|---:|---|---|---|---:|
| B-a755cb1dacec | 12 | blocked | 0 / 10 / 2 | BLOCKED | 3 |
| B-04ba43c7ff2e | 64 | blocked | 0 / 40 / 24 | BLOCKED | 25 |
| B-66dcecfda5d4 | 27 | blocked | 0 / 24 / 3 | BLOCKED | 4 |
| B-c4e3190c97c2 | 2 | completed | 0 / 2 / 0 | PASS | 0 |

32 findings E BLOCKING_HISTORY_REMAINS:29 items pendientes más resumen del manifest
en cada uno de tres negocios bloqueados. No otros finding codes. Cero nuevos EE,
Operations/authorizations/links/sequences; crecimiento de secuencia0. E PASS del
negocio vacío solo acredita ausencia de incoherencias en ese control.
El importador decide cada item congelado:0 candidatos elegibles, ningún selection
manual. El camino de incorporación efectiva/partial/covered_existing no se valida
sobre esta restauración. Se mantiene honestidad histórica por encima del porcentaje.

Writers normales tras fence: factura/cobro/banco/recibida/gasto/EE directo,22
intentos por run, todos HistoricalFenceActive. Valores de probe ficticios solo en
memoria; no persistencia de fixtures ni I/O externo. Se usan tenants con filas
restauradas, sin crear clientes/usuarios ni bypass de suscripción.

Segundo rehearsal desde snapshot físico original limpio; code/datos idénticos.
Cinco diagnostics/cuatro C-D-E reproducen UUIDs de run, source/plan hashes,
classifications/dispositions/results. Identidades históricas derivadas62, huella:
`5e5f4c97bf8a9382d59d24e02f31066e27e12b76c7cceaa376fb421c75302e63`.
Base de determinismo: raw/revisiones idénticos y contrato puro inalterado; no se
observa creación de UUIDs de eventos/operaciones porque no hubo candidatos.
T0/timestamps/run snapshot hashes pueden diferir por reloj y actividad PostgreSQL.
Reintentos sobre misma copia: prepare/run de4 batches,105 record_item y4 E;
mismos resultados/frozen hashes y counts, no duplicados ni pérdida de batch original.

| Business | C s | D s | E s | Gate E s | SQL E / verifier | Peak Python E bytes | T0→primera E s |
|---|---:|---:|---:|---:|---|---:|---:|
| B-a755cb1dacec | 1.039 | 0.140 | 0.273 | 0.271 | 126 / 18 | 276053 | 1.501 |
| B-04ba43c7ff2e | 2.781 | 0.644 | 1.297 | 1.295 | 154 / 18 | 2007773 | 4.746 |
| B-66dcecfda5d4 | 1.071 | 0.220 | 0.304 | 0.303 | 133 / 18 | 249755 | 1.618 |
| B-c4e3190c97c2 | 0.535 | 0.028 | 0.043 | 0.042 | 114 / 18 | 40667 | 0.627 |

Mayor elegible:64 items, C2,78s/1979SQL, D0,64s/1632SQL y E1,30s/154SQL;
18 consultas del verifier más autorización/gate/repositorio; definición distinta
respecto al contador de llamadas SQL total. Pico Python en C≈2,03MB/E≈2,01MB,
tracemalloc; no perfil completo de memoria PostgreSQL. RSS del proceso de revisión
final≈76MiB, medición separada. Total raw+assessment/candidates de los nueve
manifests:766545 bytes. Tamaño DB inicial registrado en baseline privada.
Gate mide tras adquirir lock hasta cierre/commit (cota superior de hold, no espera);
instrumentación solo contadores/observación, nunca cambia decisiones/writes.

Clasificación operacional: **aceptable para1.10 únicamente en el volumen probado**,
no autoriza iniciar1.10 ni demuestra SLO productivo. Requiere validar muestras de
mayor escala y candidatos efectivos antes de transición; no hay evidencia aquí
que justifique optimizar ni declarar segura toda escala. Primer run pequeño tuvo
29,16s hasta E por corregir un probe inválido; segundo limpio1,50s. No ocultar la
pausa de preparación del harness en medición de ventana.

PG detenido2026-10-05T15:44:24.054679Z. Intervalos observados desde T0 hasta stop:
pequeño264,06s, mayor262,366s, recibidas256,796s, vacío254,913s; incluyen revisión
humana/orquestación. **Fence lógico sigue ON**, por tanto no son duración hasta
release. No release automático. Sin servicio disponible en QA después del cierre.

## Fallos observados y decisiones

No bug Financial Core ni supuesto de contrato contradicho identificado.
Incidencias A: datos insuficientes correctamente bloqueados. Incidencias B de
harness/configuración: permiso de lectura del archivo de autorización root640;
construcción de Principal con id→user_id; probe EE en memoria sin confirmed_on,
rechazado por validación antes de append; extracción segura de tar que dejó el
directorio PG0755, PostgreSQL rehusó arrancar hasta recuperar0700/modos originales.
Ninguna reparación de sources/reglas; todos resueltos antes del paso afectado.
Segundo run limpio desde snapshot, sin cambio de runtime. La interpretación del
IVA NULL se corrigió en informe por nombre de campo real, no en dinero/BD.

Artefactos privados: scripts/ de orquestación y evidence/run1, evidence/run2,
phase19f-clean-repeat.json, phase19f-outbound-final.json, phase19f-stopped-state.json.
Solo resúmenes sanitizados exportados de Linux. Scripts privados no son nuevo CLI
de producto; no se incluyen en Git. [Runbook](FASE-1.9F-runbook.md).

## Criterios individuales

PASS limitado significa que la obligación operativa se cumplió con la muestra
presente; el escenario ausente nunca se considera prueba positiva. N/A se conserva
como falta de ejercicio explícita. No hay criterio técnico FAIL identificado.

| Nº | Criterio de la orden | Resultado | Evidencia/límite |
|---|---|---|---|
| 1 | Estado de partida | PASS | Código aprobado acff183, schema73; contratos A–E leídos; cinco flags OFF. |
| 2 | Observar antes de cambiar código | PASS | Ningún cambio funcional; bloqueos observados sin excepciones nuevas. |
| 3 | Restauración autorizada | PASS | Backup real autorizado, fecha/origen/versión/tamaño y SHA preservados. |
| 4 | Aislamiento | PASS | DB/rol propios y namespace con loopback solamente; sin procesos productivos. |
| 5 | Prohibición de outbound | PASS | TCP IPv4/IPv6 y UDP53 rechazados con ENETUNREACH; defensa secundaria nftables. |
| 6 | Privacidad | PASS | Informes de counts/hashes/categorías; sin filas/payloads/secretos literales. |
| 7 | Snapshot inicial | PASS | Baseline previa: esquema, negocios, counts, tipos monetarios, EE y hashes legacy. |
| 8 | Comprobar que es copia | PASS | Marker+SHA+DB+rol+host/puerto+launcher+red+ausencia de otros clientes. |
| 9 | Backup de la copia | PASS | Snapshots lógico y físico previos verificados; originales conservados. |
| 10 | Migración a73 | N/A | La fuente ya está en73; cero migraciones, sin cambios al esquema. |
| 11 | Sin SQL financiero manual | PASS | Ninguna reparación/eliminación/normalización de sources. Probes normales rechazados por fence. |
| 12 | Cohortes por negocio | PASS | Counts: pequeño/sintético, variado/mayor elegible, recibidas, borradores; control vacío separado. |
| 13 | No asumir clientes reales | PASS | 14 negocios: dos demo y nueve no elegibles en total. No se acredita cliente real por is_demo=false. |
| 14 | Diagnóstico antes de cut | PASS | Cinco B ejecutados y revisados antes de C/D/E; sin epoch durante B. |
| 15 | Métricas de inventario | PASS | 159 items; A0/B129/C29/D1; incidencias/dispositions/dependencias registradas. |
| 16 | False positives/negatives | PASS limitado | Revisión interna por código/categoría y fuente; no anomalía en categorías presentes, sin aval de escenarios ausentes. |
| 17 | Dinero legacy | PASS limitado | 561 observaciones binarias no corroboradas, 13 NULL, 23 residuos no cero; ningún exact/corroborado/subcent presente. |
| 18 | registro_anterior | PASS | Uno en toda la copia; marcador migration11; D, sin candidato ni promoción. |
| 19 | Recibidas/gastos | PASS limitado | Tres recibidas y11 gastos seleccionados; revisión1, sin voids; no correcciones inventadas;11 IVA capturado NULL y2 tipos IVA NULL. |
| 20 | Banco | N/A | Cero movimientos/links bancarios en toda la restauración; match/suggestions no validados con datos reales. |
| 21 | Facturación/fiscal | PASS limitado | 41 facturas seleccionadas:32 borradores fuera de alcance,9 emitidas bloqueadas; sin fiscal records/cancelaciones/outboxes. |
| 22 | Invoice historical v2 | PASS | Sigue bloqueada. Nueve emitidas necesitan resolver evidencia fiscal/perfil/líneas/dinero; no se implementa vía nueva. |
| 23 | Primer cut real | PASS | Epoch/generation/T0 en QA; seis familias de writers rechazadas; métricas registradas. |
| 24 | Manifest certificable | PASS | Cuatro sobres C certifiable=true, eligible_for_import=false, boundary_current=true; sin drift. |
| 25 | Importer real | PASS limitado | Cuatro batches:3 blocked/1 completed vacío;0 recorded/existing/covered,76 skipped y29 blocked. Camino positivo no ejercitado. |
| 26 | Reconciliation real | PASS | 3 BLOCKED honestos (32 findings BLOCKING_HISTORY_REMAINS);1 PASS vacío, sin reparación. |
| 27 | Restaurar/repetir | PASS limitado | Segundo cluster limpio del snapshot inicial; fuentes/planes/classifications/semántica iguales. UUID de eventos/operaciones sin cobertura por0 candidatos. |
| 28 | Idempotencia | PASS limitado | 105 item retries, prepare/run batch yE; mismo batch/resultados/counts; no duplicados. Inserción positiva no ejercitada. |
| 29 | Volumen real | PASS limitado | Mayor elegible:33 fuentes primarias/64 items. D/E negativos seguros; no prueba de gran escala. |
| 30 | Transacción de reconciliación | PASS limitado | Gate máximo1,295s en segundo run, aceptable únicamente para volumen probado; validación de escala pendiente antes de1.10. |
| 31 | Duración fence | PASS | T0→primera E y período observado hasta detener cluster medidos; fence lógico sigue ON, sin duración final de liberación. |
| 32 | Writes concurrentes simulados | PASS | 22 intentos por run, todos HistoricalFenceActive; sin concurrencia de clientes ni proveedores necesaria. |
| 33 | Cero outbound al finalizar | PASS | Guard en cada proceso y probe final PASS; namespace sin rutas hace imposible conexión externa de aplicación. |
| 34 | PII en logs | PASS | Logs/errores controlados y revisión de informes;0 patrones email/credenciales,0 STATEMENT/parameters; ningún raw dump nuevo. |
| 35 | Runbook reproducible | PASS | Runbook entregado; scripts/evidencias privadas. Destrucción no ejecutada ni autorizada. |
| 36 | Producción intacta | PASS | Cero Railway/producción durante rehearsal; solo conexión QA validada. No deploy/push; no consulta productiva para readback. |
| 37 | Si aparece bug | N/A | No bug Financial Core identificado. Fallos de harness/configuración resueltos antes del paso afectado, sin reparar sources. |
| 38 | Sin reglas para hacer PASS | PASS | No promoción/reclasificación/excepción/fiscal/bank match nuevos. |
| 39 | Resultado global honesto | PASS | PASS WITH LIMITATIONS; no aval de importación positiva/escala/datos bancarios/fiscales ausentes. |
| 40 | No activation | PASS | Cinco flags OFF; fence permanece ON QA; sin validating/live continuity. |
| 41 | No1.9G | PASS | No cierre global1.9 ni ejecución de1.9G/1.10. |

## Autoauditoría

| Nº | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿Algo contra producción? | No. Solo QA; backup productivo read-only fue preparación autorizada anterior. |
| 2 | ¿Credenciales productivas fuera del restore? | No. Lanzador limpia entorno y utiliza solo contraseña local privada. |
| 3 | ¿Outbound real? | No conexión externa posible desde procesos de aplicación; probes ENETUNREACH y guard permanente. |
| 4 | ¿PII en nuevos informes/logs? | No PII literal exportada. Raw/copia real permanecen privados; patrones/logs revisados. |
| 5 | ¿Source modificado para PASS? | No. Hashes de95 tablas idénticos antes/después y entre restauraciones. |
| 6 | ¿Clasificación relajada? | No. |
| 7 | ¿registro_anterior promovido? | No. D/BLOCKED. |
| 8 | ¿Bank match inventado? | No. Banco ausente. |
| 9 | ¿Fiscal inventado? | No. |
| 10 | ¿Invoice historical v2 desbloqueado? | No. |
| 11 | ¿Flags alterados? | No. Los cinco OFF. |
| 12 | ¿Fence liberado automáticamente? | No. QA sigue fenced; PostgreSQL detenido. |
| 13 | ¿Repetición determinista? | Sí para fuentes/planes/identidades derivadas/clasificaciones/resultados presentes. Eventos/operaciones nuevos: N/A. |
| 14 | ¿Idempotencia? | Sí para105 items, batches y E, sin duplicados. Inserción efectiva no ejercitada. |
| 15 | ¿Volumen/gate/fence medidos? | Sí; límites de muestra y memoria Python explícitos. |
| 16 | ¿BLOCKED honesto? | Sí. Tres E bloquean historia pendiente; PASS del control vacío no representa importación real. |
| 17 | ¿Código cambiado durante rehearsal? | No código de Noesis. Scripts privados de orquestación y documentación únicamente. |
| 18 | ¿Bug y repetición limpia? | No bug del núcleo. Se repitió igualmente desde snapshot limpio; no fix funcional. |
| 19 | ¿Producción intacta? | Ninguna acción de este rehearsal pudo llegar a ella; sin readback ni despliegue. No se afirma ausencia de cambios por terceros. |
| 20 | ¿1.9G/1.10 iniciadas? | No. |

## Verificación proporcional y continuidad

Pruebas ejecutadas: rehearsal PostgreSQL18 real en dos copias,44 probes de writers,
comparación de95 tablas, reintentos explícitos, identidad/isolation/outbound antes y
después, snapshots/hash/restore limpio y privacidad de logs/informes. No cambios
de runtime/tests/migrations/dependencias; no hace falta repetir fixtures SQLite ni
suite general sobre datos reales. Validación SQLite/PG sintética de A–E permanece
la del cierre1.9E, no se contabiliza como nueva validación de1.9F. Gates documentales,
secretos y Ruff se registran en Registro-QA; ningún servidor/página afectado.

Riesgos pendientes: no candidates positivos, historial fiscal/bancario/rectificativo
vacío, poca escala, trials/demos fuera de permiso, falta de acreditación de historial
de clientes reales, invoice historical v2 bloqueado. Copias siguen siendo datos
personales; retención/destrucción requiere política y autorización separadas.
Rollback operativo: conservar evidencias, detener PG, restaurar snapshot inicial
verificado en otra copia limpia dentro del mismo aislamiento; jamás downgrade/
borrar evidencia/reclasificar el run. No desplegar documentación mediante push
mientras siga vigente la prohibición de modificar producción.
