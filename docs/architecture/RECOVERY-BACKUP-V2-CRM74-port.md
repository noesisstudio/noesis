# Recovery Backup V2 — port CRM74 local

Fecha: 2026-10-13. Rama `codex/recovery-backup-v2-crm74`.
Estado: **BACKUP_V2_CRM74 LOCAL CODE-VERIFIED PASS**.
No evidencia remota ni permiso de despliegue.

## Base, historia y alcance

Base exacta `678bd3fdf2f9891b373b0fe8d46ac37b97f0310d`, catálogo real 1–74,
con `74 / captacion_hoja_y_tipo`. El commit que contiene este informe es el
commit del port; su padre debe ser esa base. No se cambia la rama local main.
Su puntero previo es distinto del main actual representado por origin/main:
el merge-base con main local es acff183; con origin/main es la base 678bd3f.
No se mueve main para ocultar esa diferencia.

V2 histórico: `f272582663f35a6e1c6ed9e34e8b0e737d235b49`, padre
`08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d`, rama `codex/recovery-backup-v2`.
Se inspeccionó su delta y se portaron únicamente los componentes de backup,
herramientas, tests y configuración. No cherry-pick ni sustitución del producto.
Los [contrato](RECOVERY-BACKUP-V2-contrato.md),
[ADR histórico](ADR-RECOVERY-001-postgres-native-backup.md) y
[cierre histórico](RECOVERY-BACKUP-V2-cierre.md) se conservan byte a byte.
Sus cifras, schema73 y ensayos reales son historia, no pruebas de este port.
Esta adenda prevalece para CRM74 y manifest contract2.

Se conservan sin cambios migrations.py, CRM/esquema, db.py, scheduler, NLU/voz,
precios, pyproject/lock de dependencias, templates y assets CRM y local_dates.
El contexto de imports de admin.py se adaptó a su estructura actual: sólo ZIP
de descarga V2 y eliminación de ese temporal, ninguna ruta CRM antigua.
No hay DDL persistente nuevo, A75–F80, bridge ni implementación de activación.
El [diseño aprobado](SCHEMA-LINEAGE-75-80-contract.md) permanece documental.

### Comparación del delta con f272

| Componente | Port sobre current main |
|---|---|
| Toolchain/libpq/destino sellado y check de herramientas | Funcionalidad histórica conservada |
| Inventario semántico raw | Misma lógica de objetos/filas/secuencias; añade identidad del registry |
| Native backup/restore | Añade revisión2, JSON cerrado sin claves duplicadas, comparación de lineage; conserva revisión1 |
| Privacidad | Cambia umbral numérico por nombre E instalado; mantiene no serving/hold legacy |
| Backups V1 | Catálogo74 actual + prefijo version/name completo, applied_at no NULL; no MAX-only |
| Admin | Adaptación manual del delta ZIP/BackgroundTask a imports actuales; CRM extraído intacto |
| CI/Railpack/Mise | Conserva gates/Tesseract/local_dates y agrega lab18, contrato2 y fixture legacy79 |
| Tests | A–Y + defensas previas; actualiza fixtures73 a CRM74 real y agrega identidad/compatibilidad/legacy |
| Documentación | Cuatro documentos históricos y diez de diseño sin cambiar contenido; nueva adenda/gobernanza |

### Archivos del delta

Código: `src/noesis/web/backups.py`, `src/noesis/web/routers/admin.py`,
`src/noesis/web/postgres_backup_identity.py`, `postgres_backup_inventory.py`,
`postgres_backup_tools.py`, `postgres_native_backup.py`.
Tests: `tests/postgres_backup_v2.py`, `test_postgres_backup_identity.py`,
`test_postgres_backup_v2.py`.
Herramientas/configuración: `.github/workflows/ci.yml`, `.gitignore`, `railpack.json`,
`mise.toml`, `mise.lock`, `scripts/check_postgres_toolchain.py`,
`scripts/mise-linux-x64.sha256`, `scripts/run_postgres_backup_lab.py`.
Gobernanza: `AGENTS.md`, `docs/project-state.json`, `Registro-cambios.md`,
`Registro-QA.md`, `Estado-actual-main.md`, `Tareas-vivas.md`, `Mapa-codigo.md`,
`Decisiones.md`, `docs/areas/06-rgpd-y-seguridad.md`, `07-lo-automatico.md`,
`08-financial-core.md` y `docs/architecture/README.md`.
Arquitectura nueva/copiada: `ADR-RECOVERY-001-postgres-native-backup.md`,
`RECOVERY-BACKUP-V2-{orden,contrato,cierre}.md`,
`RECOVERY-BACKUP-V2-CRM74-{orden,port}.md`,
`ADR-SCHEMA-LINEAGE-001-crm74-financial75-80.md`,
`SCHEMA-LINEAGE-75-80-{orden,contract,mapping,hash-impact,test-matrix,
implementation-order,cierre,fingerprints}.md` y
`SCHEMA-LINEAGE-75-80-catalog-design.json`.
Lista exacta y clasificación A/M: `git show --name-status` del commit del port.

## Contrato del manifest

`format_version=noesis-postgres-native-v2`, `manifest_contract_version=2`.
Claves cerradas; JSON con claves duplicadas, revisión desconocida, identidad
incompleta, gap, duplicado, orden incorrecto, nombre incorrecto o futuro
desconocido se rechazan. La identidad sale de todos los registros de la TX
READ ONLY de origen; nunca exclusivamente de MAX(version).

Campos adicionales: `migration_identities` contiene pares `[version,name]`
ordenados, `schema_lineage_fingerprint` y `schema_lineage_id`. Continúan fecha UTC,
versiones de servidor/dump, code SHA opcional, hashes/tamaños de archive y ZIP,
counts/hash de datos por tabla, inventario/hash de objetos y TOC, extensiones,
estado de secuencias y encoding/provider/locale/version de collation.
No DSN, credenciales, cuerpos SQL ni valores de filas en el manifest. Nombres de
objetos son metadatos del catálogo; el archivo documental y dump contienen datos.

Fingerprint: UTF-8 de JSON con `sort_keys=True`, separadores `,` y `:`,
`ensure_ascii=False`, `allow_nan=False`; objeto con
`format=noesis.schema-lineage.v1` y `migrations` como lista de objetos version/name.
No applied_at. SHA-256 CRM74:
`ee2de64c6e47629811c6cee2bfa8f28fea66bb9e23e28caa50bc0b62db697e24`.
Coincide con el [golden aprobado](SCHEMA-LINEAGE-75-80-fingerprints.md).
Los applied_at no se reescriben y forman parte del hash raw de filas.
Un applied_at NULL impide capturar un registry válido.
El fingerprint no es firma, autoridad, certificado ni proof financiero.

La revisión histórica1 (sin campo manifest_contract_version) mantiene su contrato
exacto y sus bytes. Se comparan sus inventarios originales y se deriva la identidad
del registry restaurado; no se añade retroactivamente metadata al manifest.
La revisión2 compara además lista completa, clasificación y fingerprint exactos
después de pg_restore. Ninguna reparación del registry ni migrations en restore V2.

## V1, V2 y privacidad

V1 es catalog-dependent: sólo header74, catálogo completo de tablas/columnas
y registry exacto CRM74. Schema73 requiere su runner73; legacy Financial74,
future unknown, registro corrupto/gap/duplicado/nombre falso y objetos desconocidos
fallan antes de SQL PostgreSQL. Inspección SQLite offline no toca el destino.
No conversión V1→V2 ni promoción de schema73 a74.

V2 usa DDL nativo: objetos desconocidos en un archive CRM74 se preservan sin
agregarlos a migrations. Lineage física es distinta de compatibilidad de aplicación.
Se admiten prefijos conocidos 1–73, CRM74 y legacy Financial74–79 exactos;
un registry futuro desconocido sigue bloqueado. La independencia del catálogo
de objetos no implica aceptar identidades desconocidas.

Legacy `74 / evaluacion_readiness_financiera` nunca es CRM74. Sus nombres 74–79
se verifican y se etiquetan `LEGACY_FINANCIAL74_79`. La presencia exacta de
`privacy_export_retention_closure` determina
`POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED`; se elimina el criterio >=78.
CRM74 da `NO_E_INSTALLED`. El futuro catálogo canonical E79 sigue siendo diseño.
Todo restore devuelve serving_authorized=false y g_real_evidence=false.
No se aplica ni aprueba policy E, no se sirve el restore ni se genera evidencia REAL.

## Seguridad y herramientas

Se conservan snapshot exportado coherente READ ONLY, pg_dump custom,
dos inventarios/estado de secuencias, manifest publicado al final, SHA de archivos,
destino sellado vacío/propio/consumible, no root, socket UNIX sin listener TCP,
namespace Linux sin outbound, single-transaction/exit-on-error y ningún migrator V2.
Shell=False, límites de tiempo, errores sanitizados, entorno libpq acotado y
PGPASSFILE 0600 en directorio0700 con eliminación garantizada.
La descarga admin empaqueta los tres archivos, no expone rutas ni configuración.
No se probó subida offsite real. La capacidad de restore no acepta un endpoint
externo ni un indicador is_test. El dump no está cifrado ni firmado.

Mise2026.10.8, conda PostgreSQL18.6 fijado con mise.lock Linux x64. Se verifican
pg_dump, pg_restore, initdb, pg_ctl y postgres major18. Railpack conserva sus cuatro
paquetes Tesseract y añade el check de toolchain; no se construyó imagen Railway.
CI conserva todos los gates actuales y local_dates. Añade V2 y checkout de código
legacy79 congelado únicamente para crear fixtures nuevos, sin datos reales.
La CI remota no se ejecuta: esta orden prohíbe push y PR.

## Validación y autoauditoría

Suite general completa actual fresca: **1925 tests, 1922 PASS, 3 skips, 0 FAIL,
0 ERROR**, 2274.488s de unittest; 2281.672s incluyendo discovery/orquestación.
Windows/Python3.12.3. Código de salida0. Incluye88 de tests/crm y40 de
test_crm_captacion, todos PASS. No se reutiliza el total histórico1820 ni los
1894 agregados de main. Treinta y un tests nuevos portables del port están en esta
misma pasada (20 V2 +11 identidad). JavaScript actual:11/11 PASS,0 FAIL.

Skips exactos: dos de History cutoff exclusivos PostgreSQL (gate try-lock y
repeatable snapshot), cubiertos en su matriz50; PGPASSFILE/POSIX, cubierto en los
70 del grupo V2/Linux. Los tres motivos se conservan, no se ocultan ni cuentan
como PASS Windows. Linux/V2 no omitió ningún caso.

Ruff src/tests, Bandit HIGH/HIGH, credential scan completo versionado, dependency
audit del entorno uv.lock (0 vulnerabilidades conocidas; noesis local no está en
PyPI), verdad documental, enlaces del delta, migrations.py/CRM idénticos y
git diff --check PASS. La baseline de secretos no se modificó.
Los controles de verdad usan PYTHONPATH de este worktree; una invocación inicial
sin esa ruta encontró el editable de otra rama y no se usa como resultado.
Configuración local verificada: cinco flags por defecto OFF, catálogo74 y golden
exacto. No se leen ni certifican flags o datos de producción.
Laboratorio nuevo `NoesisBackupV2CRM74Synthetic`, usuario noesisqa, Python3.13.16,
PostgreSQL18.6. Sólo fixtures propios en namespaces sin interfaces externas.
No se inicia Noesis19FQA ni una distribución que contenga copias reales.
Logs y artefactos sintéticos fuera de Git en NoesisSynthetic/backup-v2-crm74-20261013.

La primera ejecución general Linux y el primer runner completo PostgreSQL se
interrumpieron con Hangup, sin cierre de suite. No se contabilizan como PASS ni se
suman. Causa no acreditada. La pasada general final se relanza íntegramente en
Windows/Python3.12 con guard de sockets/DNS externos y almacenamiento sintético;
PostgreSQL se relanza íntegramente desde0 en un proceso WSL independiente de la
conexión del chat, Python3.13. Los artefactos finales deben incluir código de salida.
La orquestación de laboratorio no forma parte del producto ni aporta autoridad.

Antes de estas pasadas se corrigieron dos errores del fixture portado (variable
archive73 residual y row_factory dict_row de la construcción legacy79). El scanner
señaló las dos contraseñas ficticias de prueba: excepción explícita sólo en esas
líneas, sin cambiar detectores ni baseline. No hubo cambios de CRM ni relajación
de guardas. Las anotaciones no cambian el comportamiento de los tests.

El test unknown-objects conserva tabla, columna Decimal exacta, índice, CHECK,
FK deferred, función, trigger, domain/enum, view, collation, hstore y secuencia500.
Legacy79 se construye con código congelado8705521, sin datos ni negocios reales;
demuestra integridad física y privacy hold, no canonical80 ni recovery operativo.
La matriz cubre también corrupción, set incompleto, destino ajeno/no vacío,
credenciales excluidas, timeout, drift de locale y comparación exacta de metadata.

### Autoauditoría de cierre

| Criterio | Resultado |
|---|---|
| Nueva rama desde678, sin rebase/cherry-pick ciego | PASS |
| Padre directo del commit único de port es678 | PASS |
| f272/parent08 y rama histórica intactos | PASS |
| Diseño aprobado75–80 conserva contenido; sin implementación | PASS |
| CRM/migration74/db/scheduler/NLU/voz/precios/dependencias/templates/assets intactos | PASS |
| LATEST_VERSION74; registry completo version/name, sin MAX-only de backup | PASS |
| No DDL/migration75 nueva, A75–F80 ni bridge | PASS |
| V1 CRM74 exacto;73/legacy/futuro/corrupción bloqueados | PASS |
| Manifest2 cerrado; revisión1 válida sin mutación | PASS |
| Fingerprint aprobado, sin applied_at ni autoridad | PASS |
| Restore compara registry/applied_at/hash sin repararlos | PASS |
| Snapshot READ ONLY/exportado; hashes/filas/objetos/secuencias completos | PASS |
| Destino propio/sellado/vacío; no source/arbitrary endpoint | PASS |
| No migrations V2; SQL restore atómico | PASS |
| Unknown table/column/index/CHECK/deferredFK/function/trigger/domain/enum/view/sequence | PASS |
| Legacy79 sintético físico; identidad legacy, hold E, no serving/evidence | PASS |
| E por identidad instalada; no umbral >=78 | PASS |
| pg_dump/restore/initdb/pg_ctl/postgres18.6, lock/Mise comprobados | PASS |
| Railpack Tesseract y gates/Node actuales conservados | PASS — build Railway no ejecutado |
| Shell=False, timeouts, errores sanitizados, PGPASSFILE privado/excluido | PASS |
| Fallos no rotan/suben; ZIP admin completo/temporal propio | PASS |
| Suite general fresca1925; CRM88+40; JS11 | PASS |
| Runner PostgreSQL18 completo,464 casos y18 pasos | PASS |
| SQLite/PG0/32/73→74; SQLite ciclo0→74→0→74 | PASS |
| Ruff/Bandit/secretos/dependencias/truth/links/diff/preservación/AST | PASS |
| No producción/Railway/QA/backups reales/provider I/O/business15 real | PASS |
| No push/PR/main/merge/deploy/flags/evidence REAL/EMPTY/G-LIVE/H | PASS |

**27 PASS, 0 FAIL**, dentro del alcance local/sintético. Los límites operativos
siguientes impiden llamarlo remote PASS, recovery REAL PASS, READY o GO.
El SHA local final se obtiene del commit que contiene este informe; no se introduce
una autorreferencia SHA imposible dentro de su propio contenido. Base/padre y
SHA definitivo se entregan además en el cierre externo de la tarea.

### PostgreSQL final (ejecución fresca completa)

| Matriz | Casos | Resultado | Segundos de tests |
|---|---:|---|---:|
| migrations32 | smoke/gate | PASS | ver duración por paso |
| migrations historical | smoke/gate | PASS | ver duración por paso |
| HTTP + backup + restore | smoke/gate | PASS | ver duración por paso |
| Core | 6 | PASS | 0.046 |
| Operations/Auth | 37 | PASS | 3.74 |
| Economic Events | 28 | PASS | 68.357 |
| Borrowed writers | 18 | PASS | 6.354 |
| Invoice Capture | 27 | PASS | 16.35 |
| Payment/Bank | 41 | PASS | 19.698 |
| Supplier/Expense | 44 | PASS | 13.947 |
| Channels | 50 | PASS | 174.203 |
| History inventory | 37 | PASS | 20.691 |
| History cutoff | 50 | PASS | 381.277 |
| History import | 25 | PASS | 187.717 |
| History reconciliation | 31 | PASS | 297.662 |
| legacy catalog53 | smoke/gate | PASS | ver duración por paso |
| privacy + rollback | smoke/gate | PASS | ver duración por paso |
| POSTGRES_BACKUP_V2_CRM74 | 70 | PASS | 46.444 |

Total unittest del runner: **464 PASS, 0 skips, 0 FAIL, 0 ERROR**.
Doce matrices base:394; native V2:39; contratos portables:20; identidad:11.
Grupo V2/identidad:70 PASS en46.444s. Los31 contratos portables están también
en la suite general: estos recuentos son ejecuciones, no una suma de casos únicos.
Los18 pasos terminaron con returncode0; suma de duración por paso:1355.563s.
HTTP/default backup/restore, código anterior53 sobre74 y privacy/rollback PASS.
0/32/73→74 en SQLite y PostgreSQL PASS; ciclo SQLite0→74→0→74 PASS.
CRM74→V2→CRM74 conserva registry/applied_at, fingerprint, DDL/filas/objetos/secuencias.
Unknown-objects y frozen legacy79 PASS; serving/evidence false, legacy E con hold.
Código de salida del runner completo:0. No datos reales ni migrations en restore V2.

## Riesgos y pendientes

- Coste de lectura/hash O(n), sin SLO de producción acreditado.
- Binarios/extensiones/locale y permisos del worker son prerrequisitos operativos.
  Un entorno web normal con outbound no puede ejecutar verificación de restore:
  falla cerrado; el worker de recovery y build Railway deben validarse posteriormente.
- Ausencia de firma/cifrado nativo: requiere origen/custodia autorizados.
- Roles, ACL y tablespaces globales se excluyen como en V2 histórico; no es un
  clon de cluster ni una autorización operativa. El filesystem documental no
  comparte snapshot DB: el ZIP se verifica por separado, sin promesa de atomicidad
  entre archivos y referencias DB. Las secuencias no MVCC exigen ausencia de drift.
- No se implementa el validator runtime ni collision guard completo75–80;
  esta validación existe sólo en los límites de backup/restore, no cambia el migrator.
- CI remota, despliegue, backup/restore real y evidence G pendientes de órdenes
  posteriores. Policy E REAL continúa provisional/pendiente de profesional;
  PRIVACY_NOT_READY, los cinco flags OFF y business15 no reciben cambios.
- Si E se instala, el restore técnico no habilita uso hasta replay/supresiones
  actuales mediante un mecanismo aprobado en una fase posterior.

[Orden local](RECOVERY-BACKUP-V2-CRM74-orden.md).
