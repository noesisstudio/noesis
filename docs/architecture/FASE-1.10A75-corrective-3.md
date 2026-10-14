# A75 CORRECTIVE #3 — BLOCKED: validación PostgreSQL del candidato incompleta

[Orden](FASE-1.10A75-corrective-3-orden.md),
[decisión de retención aprobada](FASE-1.10A75-corrective-3-retention-decision.md).
Base cb23aa4 y main678bd3f exactos; ningún commit/push nuevo. Candidato local
implementado tras autorización humana de perfiles técnicos; sin cierre remoto.

## WSL sintético autorizado y prueba ejecutada

El titular autorizó comprobar y usar sólo NoesisBackupV2CRM74Synthetic, sin
reset/repair/QA real. Probe20s devuelve0. PostgreSQL18.6/Python existentes;
clusters nuevos sellados, namespace sin outbound, cinco flags OFF. Sólo datos
sintéticos. No reinstalación ni reparación. Recibos privados fueraGit en
C:/Users/mikic/NoesisSynthetic/phase-1-10a75-20261013/corrective-3-baseline/technical/.

## V2: prueba previa al cambio; equivalencia demostrada

Campos CHECK metadata idénticos: conname/contype/deferrable/deferred/validated/
noinherit. Column typeNUMERIC unconstrained, typmod-1, precision/scaleNULL iguales;
PG18.6 iguales. Sólo constraintdef/expression distintos; hashes por campo en
recibos privados. Ningún SQL completo, filas, DSNs o secretos en stdout.

SOURCE tree: OR(NULL, AND(AND(LOWER,UPPER),PRECISION)).
RESTORED tree: OR(NULL, AND(LOWER,UPPER,PRECISION)).
Las cuatro hojas conservan tokens/hashes EXACTOS y orden. Sólo desaparece el par
de paréntesis del AND de los límites. No cambia cast/número/operador/trunc/null.

2129 probes PG pasan:21 dirigidos (incluyen NULL/escala/límites/near-zero/NaN/Inf),
2048Decimal generados con seed751832 y60probes alrededor de límites, sin floats.
SOURCE==RESTORED==intención para TODOS;26aceptados,2103rechazados. Además27casos
completos de asociatividad AND en lógica SQL TRUE/FALSE/NULL idénticos.

La expansión de BETWEEN a dos comparaciones AND se hace durante análisis;
al reparsear SQL de pg_dump, makeAndExpr aplana el AND izquierdo existente.
Ver código primario PG18.6: [transformAExprBetween](https://raw.githubusercontent.com/postgres/postgres/REL_18_6/src/backend/parser/parse_expr.c),
[makeAndExpr](https://raw.githubusercontent.com/postgres/postgres/REL_18_6/src/backend/parser/gram.y).
Recibo rewrite-structural-proof conserva árboles simbólicos y hashes de hojas.
Normalización implementada sólo para esos dos árboles en schema_check_identity.py.
Se conserva el descriptor SOURCE original y sus hashes canonical; no sort booleano
ni eliminación global de casts/paréntesis. Hojas/sufijos distintos no normalizan.

## Stage17: causa independiente, postvalidator55

T1inmediatamente después32→75 con factura histórica yT2antesdowngrade55:
0 missing,0extra,0changed. Actual==expected en ambos, y==fresh0→75.
Hash perfil completo:
cde6d981f515660e0d3421088096cb8905c63554fe63e70e89dcdbd0a2de15f3.
No se observó DDL data-dependent de75 ni modificaciónDDL por seed/data operations.

El fallo aparece DESPUÉS de ejecutar callbacks down, al validar55 dentro deTX.
Instrumentación test-only captura ese estado antes del rollback y repropaga error.
34extra,0missing,0changed: invoices.pending_fields de58, assistant_messages.actor
 de59, whatsapp_ingress y sus objetos de60. No economic_events_amount_check.
Las callbacks down conservan esas columnas/recibos EXPLÍCITAMENTE para no perder
históricos ni deduplicación. No es una migration incorrecta demostrada.
Borrar estos objetos contradice retención/snapshot; ignorarlos ampliaría el guard.
No cambiosDDL/history, validator bypass ni excepciónautomática de75.

[Decisión aprobada](FASE-1.10A75-corrective-3-retention-decision.md): perfiles
TÉCNICOS completos cerrados sólo owner53/54/55/58, nunca runtime/VERIFIED/binding.
El titular autoriza esta excepción estrecha al §1; schema_retention.py implementa
perfiles completos con id/hash propios y aislamiento real comprobado. Nunca serving.

## Negativos y bloqueo adicional de ejecución

LineagePG16/16PASS,63.902s. Incluye7negativos del CHECK y owned objects: límite,
trunc3,operador>,AND/OR,missingCHECK,unknowncolumn,extra financialtrigger, con
rollbackSAVEPOINT y vuelta75exacta. Timeoutreal30s/concurrencia/crashes conservados.
Son pruebas previas al cambio de producto; NO acreditan el candidato nuevo.

Durante ReadinessPG el cliente Windowswsl.exe volvió a fallar. Event1000
2026-10-14 16:09:57 Europe/Madrid,exceptionc00000fd. No resultado completo de
Readiness ni atribución del crash a código financiero. No reset/repair ni reintentos
automáticos después del crash. Recibos y source conservados; no QA real tocada.

Nuevos intentos autorizados: probe0, arranque dirigido con stage17exit1 (log no
recuperable), crash clienteWindows16:52:16, probe0 y otro arranque interrumpido
a16:53:51. Ambos Event1000c00000fd, sin atribuirlos al producto. Los logs estaban
vacíos: no hay diagnóstico de la causa de stage17exit1. No más intentos WSL,
reset ni reparación. V2/Lineage/Readiness del candidato no completados.

Sin commit mientras dirigidos no terminenPASS. No CI nueva ni verdes heredados:
fullPython/Node/CRM/20etapas nuevas NO EJECUTADOS en correctivo3. El último run38547535812
pertenece a cb23aa4 y conserva18/20PG, no acredita los cambios de instrumentación.
Ruff/truth/secrets/diff/enlaces de instrumentación medidos aparte. SharpHIGH sigue
SEPARATE SECURITY DEBT / PRE-PRODUCTION TRIAGE REQUIRED.

## Freeze y cierre

Sólo schema_objects y dos helpers nuevos cambian producto. Canonical profiles,
migrations/callbacks/readiness/SOURCE_DRIFT/startup/locking/formatV2/privacy/flags
byteintactos respecto a cb23aa4; gate históricoPASS. IA sin autoridad y Decimal/NUMERIC intactos.
No main/merge/deploy/producción/Railway/Noesis19FQA/backups reales/providers/business15,
B76–F80/bridge/G-LIVE/H. Sólo fixtures propios sintéticos.
**BLOCKED — dirigidos PostgreSQL del candidato incompletos: stage17exit1 sin
diagnóstico recuperable y crashes repetidos del cliente WSL.** No REAL CHECK SEMANTIC MISMATCH: la equivalencia V2 sí se probó.

## Validación candidata local efectivamente terminada

- Regresiones portables:92casos,91PASS,1skip POSIX esperado en Windows,
  0FAIL/0ERROR,151.231s. No es suite general completa ni sustituto de PostgreSQL.
- Pruebas finales nuevas:4/4PASS,0.380s. Once mutaciones CHECK distintas no
  normalizan; perfiles técnicos exactos y autoridadTECH rechazada aun con claim75.
- Node fresco:11/11PASS,0FAIL,399.8126ms.
- Ruff, Bandit HIGH/HIGH, AST/catalog histórico, truth y diffPASS.
- pip-auditPASS: sin vulnerabilidades conocidas; paquete local noesis no auditable.
- Secret scan completo885archivos:0hallazgos nuevos; enlacesdelta547/0rotosPASS.
- FullPython/CRM/20PG nuevos y CI final:NO COMPLETADOS. No reutilizar verdes anteriores.
- Dos skips generales conocidos del CI anterior siguen pendientes de coberturaPG
  fresca; el skip portátil actual es distinto (requiere POSIX para permisos nativos).
- Sin commit/push/merge/deploy/producción/QA real/backups reales/providerI/O/flags
  ni nuevas fases. No material de policy sintética promovido a policyREAL.

## Autoauditoría de límites

PASS por inspección/gates: autorización estrecha, catálogo53/54/55/58 cerrado,
id/hash técnicos distintos, canonical53–75 congelados, no future/unknown extras,
TECH nunca VERIFIED, binding/runtime exige VERIFIED, no autoridad readiness,
no migraciones históricas cambiadas, no data cleanup, cero conexión propia,
lock exclusivo conservado, prueba nonproduction/local/no-outbound, Decimal intacto,
normalización sólo dos árboles y hojas exactas, metadatos CHECK preservados,
flags/policy/SOURCE_DRIFT intactos, ninguna producción/proveedor/QA real consultada,
historia Git intacta y no nuevas fases. FAIL de cierre: vuelta75/rows/guardsPG,
V2 runtime fresco y matricesPG completas aún no acreditados. No declarar PASS remoto.
