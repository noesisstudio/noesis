# A75 CORRECTIVE1 — REMOTE VALIDATION PENDING

[Orden](FASE-1.10A75-corrective-1-orden.md). Un único commit encima de f5150b27;
main678bd3f reservado. NoPASS final antes deCI limpia del nuevo SHA exacto.

## Fallos originales y correcciones

Run 38527937181:2004 tests/1965 PASS/2 skips/3 FAIL/34 ERROR;PG 338/333 PASS/2 FAIL/3 ERROR;
runner 13/20. Sin crash Linux, sin atribución genérica aWSL.

1. Baseline: exactamente UNA excepción en docs/project-state.json,
   Hex High Entropy String, hashed_secret9bbbffa630d384ced2e8355f94cd5abea4bfd922,
   is_verified=true/is_secret=false, golden público75. Config/detectores/filtros y
   entradas anteriores intactos. Control negativo de hash temporalPASS.
2. PublicMarketing prepara db.init_db explícito tras patches y antes de TestClient;
   ExitStack+addCleanup liberan DB temporal y patches incluso si __enter__ falla.
   SEO tiene DB SQLite temporal por test, DATABASE_URL vacío, SEED_DEMO/RESET_DB
   false, scheduler neutralizado y preparación explícita. Startup producto intacto.
3. Test flags exige75 y identidades74CRM/75A exactas. Test de migrations recorre
   73→74→75 en DB propia:74sólo sales_*,75sólo las tres tablas readiness y objetos
   asociados;DDL/rows de todas las tablas previas y timestamps registry preservados.
4. SOURCE_DRIFT: reproducción ANTES de cambiar producto confirmó BEGIN/read de
   schema → snapshot fijo→write externo confirmado→RawReader observa Servicio antiguo;
   resultado READY_FOR_REVIEW y scan/comparison hashes iguales. PRAGMA data_version
   en el snapshot también permanece 2. Observador independiente en autocommit
   mediante db.get_conn compartido observa 2→3, nunca lee tenant ni aporta autoridad.
   Fix mínimo: comparar contador antes/después de cada página de comparación;
   ante commit repetir misma keyset en nuevo contexto propietario de infraestructura,
   revalidando lineage/permisos. Dos observaciones inestables conservan SOURCE_DRIFT
   y BLOCKED; nunca READY. Sin commit/rollback propio, conexión de autoridad nueva,
   nuevo pool, autoDDL o cambio de perfil. PG conserva exactamente el camino previo.
   Después:RawReader antiguo→relecturaCOMMITTED_DRIFT; BLOCKED/hashes distintos.
   Regresiones:validation-before-reader,commit de otro tenant sin falso SOURCE_DRIFT,
   commits repetidos bloquean y replay acotado. El contrato compartido corre también en PG.
5. PGsnapshot race: función QA VOLATILE aislada que retornaTEXT, invocada desde
   expresión VALUES del INSERT. No trigger extra en expenses. query_start/pg_locks
   verifican statement iniciado antes de T0, pause antes del guard canónico yrechazo tras
   fence. require_runtime antes de SELECT del observador conserva protocoloSHARE.
   finally elimina función incluso ante assertion; caso explícito cleanup y caso
   trigger extra owned→SCHEMA_OBJECT_MISMATCH→cleanup→canonical75. Sin qa bypass.
   Dos carreras anteriores retienen expectativas y tiempos, no sleeps arbitrarios.
6. Runner cada etapa crea DB noesis_ci nueva en SU cluster sellado/local sin outbound,
   directorios docs/backups propios y registraOID distinto. Prerrequisitos32/legacy/
   privacy se preparan explícitos en su etapa;20 resultados acumulados incluso ante
   fail/timeout de un proceso. Ningún cluster real/QA/backups tocado.

## Pruebas y límites

Windows: 7 controles inicialesPASS / 11.894 s;111 web/SEO/fixtures/A75/lineage PASS / 189.255 s.
Son dirigidos, no fullPASS. Regresiones inventory/cutoff completas: 86 casos, 84 PASS y los dos skips PG
previstos, en 253.306 s. Sin FAIL/ERROR. Ruff/Bandit HIGH/HIGH PASS. Fuente del código congelado:
server._startup/schema_lineage/schema_objects/profiles/migrations/FinancialSession
byte idénticos al candidato; sólo producto HistoryDiagnostics cambia.
Sin PG nativo Windows disponible, sin reparar/reintentarWSL inestable. Pruebas nuevas
PG son PENDING hasta ejecución autoritativa Linux18.6; no afirmar demostrado antes.
Nuevo fullPython/Node/CRM/20etapasPG/V1/V2canonical75/advisory30s/crashes/parity/
legacy/privacy/gates todavíaPENDING. El recibo final quedará fueraGit ligado al
nuevo SHA/run, sin segundo commit documental que herede CI de otro SHA.

## Autoauditoría y riesgos

Lineage exacto/noMAX, TX prestada, permisos tenant, Decimal, no autoridad IA,
fuentes raw/history/hash anteriores y A74 sin reinterpretación. Observador únicamente
metadatos; relectura financiera siempre exige mismosguards. Concurrencia continua
puede bloquear prudencialmente diagnóstico, jamás autorizar READY. Cada etapa PG
nueva evita contaminación;cleanup de función QA yextrarechazo owned medidos enCI.
No nueva DDL productiva, startup autoDDL, perfiles relajados, nuevo ledger/provider.
Policy REAL provisional/PRIVACY_NOT_READY, cinco flags OFF ydeuda sharp HIGH intactos.
Sólo con 20/20 verde y 0 FAIL/ERROR se declaraREMOTE CODE-VERIFIED PASS. Sin producción,
Railway,QA/backups reales, business15,main/merge/deploy,providers,flags,B76–F80,
bridge,G-LIVE,H. Rollback del correctivo sólo revert autorizado, sin rewrite/autoDDL.
