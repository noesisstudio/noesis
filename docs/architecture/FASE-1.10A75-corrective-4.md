# A75 CORRECTIVE4 — candidato, validación fresca PENDING

Validación local fresca antes del commit:100tests/99PASS/1skip POSIX/0FAIL/0ERROR,
123.235s; siete nuevas pruebasguards incluidas. Node11/11PASS,266.9567ms.
Ruff/Bandit HIGH-HIGH/AST histórico/verdad/diff/dependency auditPASS; paquete local
noesis no auditable porPyPI. Count collection Lineage18/V273/lab20 confirmados,
sin ejecuciónPGlocal. Secretos890archivos/0nuevos; enlaces634/0rotosPASS; receipt privado antes delcommit.


[Orden](FASE-1.10A75-corrective-4-orden.md),
[candidato anterior](FASE-1.10A75-corrective-3-remote.md),
[decisión TECH](FASE-1.10A75-corrective-3-retention-decision.md).

## Diagnóstico y correcciones mínimas

Base93dbac0, main678bd3f, branchcodex/phase-1-10a75 exactos; árbol inicial limpio.
CI38587900781 generalSUCCESS/PG18de20. Stage17fallaba al importar el diagnóstico
cuando se lanzaba por filename con PYTHONPATHsrc. Sólo CASES cambia a
-m tests.postgres_release_smoke, conservando escenario entero y precondiciones.

Stage19: castinet_server_addr()::text conserva/32. El guard compara con127.0.0.1.
Sólo SQL cambia a host(inet_server_addr()), que conserva dirección y omite máscara.
Valores permitidos siguenNULL/127.0.0.1. Producción, POSIX/nonroot, redlo exclusiva,
/proc/net/route, lockexclusivo, listener local, cluster nv2-temp/data, uid/0700
permanecen idénticos. No autoridad ni fallback. No otro cambio de producto.

## Regresiones y evidencia requerida

Siete regresiones portables nuevas cubren loopback/socket y SQLhost exacto,
direcciones/listeners distintos, red/ruta noaislada, producción/root/plataforma/
locking, directorio exacto y propietario/permisos/metadata ausente; además module
Stage17/resolución diagnóstico y veinteetapas. MetadataPOSIX simulada en Windows:
NO equivalente a PostgreSQL real. PruebasPG nuevas son subtests de los dos casos
existentes de retención: Lineage sigue18casos; V2sin cambios sigue73casos.

Cada retained53/54/55/58: fullphysicalmap/id/hashTECH exactos, nuncaVERIFIED,
runtime/binding/financialreadiness/startupserving/doctor rechazados, producción/red
rechazadas y vuelta75VERIFIEDexacta. Seis mutaciones por perfil: parcial, modificada,
unknownownedcolumn,missingconstraint,futurefinancialtable yextraunrelatedtable;
SAVEPOINT conserva snapshot físico. Recibos sólo ids/hashes/estados, nunca SQL,
filas,DSNs o secretos. T1/T2/stage17/ciclo/snapshots/privacy/fiscalguards conservados.

## Alcance congelado y cierre

Migration75/históricas/canonical profiles/schemaObjects/CHECKnormalization/locks/
readiness/privacy/providers/SOURCE_DRIFT/flags intactos. SharpHIGH sigue
SEPARATE SECURITY DEBT / PRE-PRODUCTION TRIAGE REQUIRED. Policy provisional y
PRIVACY_NOT_READY intactos. SinWSL/real/QA/backups/providers/business15/main/merge/
deploy/B76–F80/bridge/G-LIVE/H. Pruebas sólo fixtures sintéticos.

Validación local y gates se registran antes del únicocommit normalparent93dbac0.
Commit no implica PASS. Push sólofeature y NUEVOworkflow_dispatchLinux/PG18.6:
generaldesde cero,20/20etapasPASS, Readiness29PASS,Lineage18PASS,V273PASS,0FAIL/
0ERROR ysoloskips previstos cubiertosPG. Cualquier fallo nuevoBLOCKED sincorrectivo.
No reutilizar verdes anteriores ni afirmar cierre parcial.

Al guardar el commit, CI siguePENDING. Recibo finalSHA/parent/main/jobs/contadores/
20etapas/errores/warnings fueraGit en C:/Users/mikic/NoesisSynthetic/
phase-1-10a75-20261013/1.10A75-CORRECTIVE4-FINAL-STATUS.md y
corrective-4-remote-final.json. Leer ese recibo antes de continuar. No segundo
commit documental autorizado para registrar el SHA futuro o el resultado final.
