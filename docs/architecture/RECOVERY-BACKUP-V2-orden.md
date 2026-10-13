# RECOVERY BACKUP V2 — POSTGRES NATIVE SELF-CONTAINED
# PREREQUISITO DEL RECOVERY BRIDGE 73↔79
# SIN PRODUCCIÓN / SIN DEPLOY / SIN MAIN

Estado:

PRODUCTION:
code = 08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d
schema = 73
PostgreSQL = 18.6

INTEGRATION A–G:
822c99e30cf97520356ecc88f0d8e5d9f4c48768
target schema = 79

RECOVERY BRIDGE:
codex/recovery-bridge-73-79

estado:

BLOCKED — RESTORE79 NO SOPORTADO

No hay cambios funcionales del bridge todavía.

---

ROOT CAUSE CONFIRMADA

El backup PostgreSQL actual:

POSTGRES_DUMP_FORMAT = "noesis-postgres-logical-v1"

NO es autocontenido a nivel de schema.

_create_postgres_backup():

- enumera tablas;
- guarda columnas;
- serializa filas;
- guarda counts/version.

_restore_postgres_dump():

1. ejecuta migrations.upgrade_connection();
2. crea únicamente el schema conocido por ese runtime;
3. intenta insertar las tablas exportadas.

Consecuencia:

runtime73 + backup schema79

falla porque migrations1–73 no crean objetos74–79.

El ensayo real aislado demostró:

- export79: PASS, 148 tablas;
- restore con runtime73: FAIL UndefinedTable / 42P01;
- fuente79 intacta;
- business15 sigue económicamente vacío.

NO solucionar esto relajando solamente LATEST_VERSION/is_current.

---

OBJETIVO

Diseñar e implementar:

NOESIS POSTGRES BACKUP V2

autocontenido para PostgreSQL usando herramientas nativas:

pg_dump
pg_restore

El V2 debe conservar independientemente del catálogo de migraciones
del runtime que ejecuta el restore:

- schemas;
- tablas;
- columnas;
- tipos;
- sequences/identity;
- indexes;
- PK;
- UNIQUE;
- CHECK;
- FOREIGN KEYS;
- constraints deferrables;
- functions;
- triggers;
- views si existen;
- data;
- sequence values;
- extensions/dependencias declarables.

El runtime no debe necesitar conocer las migrations que crearon esos objetos.

---

# 1. RAMA

NO continuar todavía modificando el bridge.

Crear una rama aislada:

codex/recovery-backup-v2

desde exactamente:

08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d

Motivo:

resolver primero el sistema de recovery de forma aislada.

NO A–G.
NO compatibility range bridge todavía.
NO main.
NO deploy.

---

# 2. PG_DUMP VERSION

Producción usa PostgreSQL 18.6.

El cliente utilizado para backup debe ser:

PostgreSQL major 18

o una versión compatible demostrada que NO sea inferior al major del servidor.

Preferencia:

pg_dump 18.x
pg_restore 18.x

Antes de cualquier backup:

pg_dump --version
pg_restore --version

Parsear y verificar major.

Si pg_dump major < server major:

FAIL CLOSED.

No hacer backup.

---

# 3. RAILPACK / TOOLCHAIN

El repo actual NO instala cliente PostgreSQL explícitamente.

railpack.json sólo instala actualmente paquetes relacionados con Tesseract.

Investigar la forma reproducible de disponer de:

pg_dump 18
pg_restore 18

Preferir instalación VERSIONADA mediante Mise/Railpack si es viable.

NO depender de:

"postgresql-client" sin comprobar qué major instala.

Crear configuración reproducible/pinned.

NO desplegarla todavía.

CI/lab debe demostrar:

pg_dump major18
pg_restore major18.

No cambiar Railway real.

---

# 4. FORMATO V2

Crear formato explícito nuevo.

Por ejemplo:

noesis-postgres-native-v2

NO sobrescribir silenciosamente v1.

El set debería contener al menos:

database archive:
*.pgdump

manifest:
*.manifest.json

documents:
*.docs.zip

El archivo DB debe usar preferentemente:

pg_dump --format=custom

NO SQL inventado por Noesis.

NO reconstrucción manual de DDL.

---

# 5. PG_DUMP

Crear el dump usando el mecanismo nativo.

Conceptualmente:

pg_dump
--format=custom
--no-owner
--no-privileges
--file=<private temp>
<database>

NO copiar DATABASE_URL completa al log.

NO incluir password en command line visible.

Usar de forma segura configuración libpq:

PGHOST
PGPORT
PGDATABASE
PGUSER

y mecanismo temporal seguro para password,
por ejemplo PGPASSFILE con permisos restrictivos,
o mecanismo equivalente que no filtre secretos.

Limpiar material temporal al terminar.

NO imprimir argv con credenciales.

---

# 6. CONSISTENCIA

Registrar en manifest:

format_version
created_at UTC
source_database fingerprint no secreto
source_server_version
source_server_major
pg_dump_version
schema_version
application_code_sha si está disponible
archive_sha256
archive_size
documents_sha256
documents_size
table_count
table_counts
required_extensions
archive_toc_hash

No almacenar secrets.

No almacenar PII en manifest.

---

# 7. TABLE COUNTS

Tomar counts desde una transacción/snapshot coherente.

El dump nativo ya produce snapshot consistente.

La verificación debe ser suficientemente fuerte para detectar:

- tabla ausente;
- filas ausentes;
- archive truncado;
- objeto DDL ausente;
- documento ausente.

No depender únicamente de KEY_TABLES.

Para laboratorio pequeño:
counts de todas las tablas del schema de aplicación.

Para crecimiento futuro:
diseñar posibilidad de estrategia escalable,
pero no optimizar prematuramente.

---

# 8. OBJECT INVENTORY

Usar:

pg_restore --list

para inspeccionar el TOC del archive.

Crear fingerprint normalizado del inventario.

Debe demostrar presencia de clases de objeto:

TABLE
TABLE DATA
SEQUENCE / SEQUENCE SET
INDEX
CONSTRAINT
FK CONSTRAINT
FUNCTION
TRIGGER
TYPE/DOMAIN si existen
VIEW si existen
EXTENSION si existe dependencia

No hardcodear únicamente los nombres conocidos por schema73.

El objetivo es precisamente preservar UNKNOWN FUTURE OBJECTS.

---

# 9. RESTORE

El restore V2 NO ejecuta:

migrations.upgrade()

antes de restaurar.

Ese era el defecto estructural de v1.

Debe restaurar el archive nativo en un destino VACÍO.

Preferencia:

base PostgreSQL temporal nueva.

No reutilizar schema con tablas existentes.

Secuencia conceptual:

create disposable database
→ pg_restore into empty database
→ validation
→ destroy disposable database.

Si el entorno no permite CREATE DATABASE:

usar instancia PostgreSQL temporal/aislada.

NO intentar remapear a mano DDL desconocido dentro de un schema
si eso reduce fidelidad.

---

# 10. PG_RESTORE

Conceptualmente:

pg_restore
--exit-on-error
--no-owner
--no-privileges
--dbname=<empty destination>
archive.pgdump

No usar:

--clean

sobre ningún entorno que pueda contener datos reales.

El destino debe ser inequívocamente desechable.

---

# 11. GLOBAL OBJECTS

pg_dump de una database NO es pg_dumpall.

Por diseño:

roles/usuarios globales
tablespaces globales

NO deben convertirse en requisito del archive de aplicación.

Usar:

--no-owner
--no-privileges

y documentar qué infraestructura externa debe existir
para restaurar:

- PostgreSQL server;
- application DB role;
- required extensions disponibles.

No crear roles de producción desde el backup.

---

# 12. EXTENSIONS

Inventariar:

pg_extension

en origen.

Guardar nombres/versiones no secretas en manifest.

Antes de restore:

verificar que el destino soporta las extensiones necesarias.

No instalar extensiones arbitrarias automáticamente.

Si falta una:

RESTORE BLOCKED.

---

# 13. DOCUMENTOS

Conservar el mecanismo actual:

.docs.zip
+
manifest de hashes.

El backup V2 es un SET atómico lógico:

DATABASE ARCHIVE
+
DOCUMENT ARCHIVE
+
MANIFEST.

No declarar el set válido si falta cualquiera de los elementos requeridos.

---

# 14. VERIFY

Después de pg_restore:

verificar:

schema_migrations == source schema version

table inventory
table counts
object inventory
constraints
sequences
required functions
triggers
documents hashes

Comparar contra manifest.

Además ejecutar:

DB read smoke.

No application writes todavía.

---

# 15. TEST CRÍTICO UNKNOWN OBJECTS

Crear prueba donde el productor conoce objetos que el consumidor NO conoce.

CASO PRINCIPAL REAL:

source:
schema79 creado con código 822c99e...

consumer/tool runner:
código basado en08a210a / migration catalog73.

El runner debe:

backup79
→ restore79

sin conocer migrations74–79.

Esperado:

todas las 148 tablas restauradas.

Y además:

mismo schema version79
mismos counts
mismos objetos DDL relevantes.

Eso demuestra el requisito que v1 incumple.

---

# 16. REAL CLONE TEST

Reutilizar únicamente el laboratorio autorizado del PREDEPLOY
o crear otro laboratorio aislado a partir del backup real conservado.

NO producción.

Secuencia:

real backup source clone73
→ migrate isolated clone to79 con código822
→ create Backup V2 using runtime/tooling73-compatible
→ restore archive to fresh isolated PostgreSQL18
→ validate.

No provider I/O.

No business15 writes.

---

# 17. BUSINESS15

En source y restored copy verificar sólo:

business15 existe

y contadores financieros:

invoices = 0
customer payments = 0
supplier invoices = 0
expenses = 0
bank = 0
fiscal cancellations = 0
EE = 0
Financial Operations = 0
Authorizations = 0
provider attempts/results = 0

NO escribir en business15.

---

# 18. V1 COMPATIBILITY

NO borrar soporte del formato:

noesis-postgres-logical-v1.

Los backups históricos V1 existentes siguen existiendo.

Definir comportamiento explícito:

V1:
legacy restore path, sólo cuando puede reconstruirse de forma segura.

V2:
nuevo default PostgreSQL.

NO intentar convertir automáticamente un V1 a V2
sin restaurarlo/validarlo primero.

---

# 19. FAIL CLOSED V1

Si un V1 declara:

schema_version > migrations.LATEST_VERSION del runtime

y contiene tablas desconocidas:

NO intentar restore parcial.

Debe devolver error claro:

LEGACY_BACKUP_REQUIRES_NEWER_SCHEMA_CATALOG

o equivalente.

Nunca UndefinedTable a mitad del restore como comportamiento esperado.

---

# 20. PRIVACY E — MUY IMPORTANTE

Backup V2 autocontenido NO equivale todavía a restore legalmente completo
para schema78+.

En la cadena A–G, E introduce restore/suppression semantics.

Por tanto separar:

PHYSICAL/LOGICAL RESTORE:
pg_dump/pg_restore → exact DB state at backup timestamp.

POST-RESTORE PRIVACY RECONCILIATION:
current external suppression/deletion registry
→ prepare_restored_database / mecanismo E vigente.

En esta rama basada en73:

NO copiar arquitectura E a ciegas.

Crear un hook/interface explícito o marcar:

POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED

para schema>=78.

En tests técnicos aislados, ausencia de cambios de supresión
posteriores al backup puede permitir comparar integridad,
pero NO declarar G RESTORE PASS.

No borrar esta distinción.

---

# 21. BACKUP VERIFIER G

NO marcar:

BACKUP PASS
RESTORE PASS

para G real.

Esta fase sólo puede cerrar:

BACKUP_V2 TECHNICAL CODE-VERIFIED PASS.

G requerirá posteriormente:

- custodian;
- encryption;
- retention;
- current E registry;
- real evidence;
- restore drill actual.

---

# 22. CIFRADO

El archive local NO debe considerarse protegido sólo por estar comprimido.

No inventar cifrado.

Mantener upload offsite existente si aplica,
pero distinguir claramente:

archive format
vs
storage encryption.

No imprimir destino ni credentials.

---

# 23. TESTS

Crear matriz específica:

POSTGRES_BACKUP_V2

Como mínimo:

A. pg_dump major enforcement.
B. pg_restore major enforcement.
C. backup73 → restore73.
D. backup79 → restore79 using runner catalog73.
E. unknown table survives.
F. unknown columns survive.
G. index survives.
H. FK survives.
I. CHECK survives.
J. deferred FK survives.
K. trigger survives.
L. function survives.
M. sequence value survives.
N. schema_migrations79 survives.
O. missing archive detected.
P. corrupted archive detected.
Q. hash mismatch detected.
R. missing docs detected.
S. docs hash mismatch detected.
T. missing extension blocks.
U. V1 newer-schema fails cleanly.
V. secrets absent from logs.
W. restore destination non-empty rejected.
X. restore cannot target source/prod.
Y. no migrations run during V2 restore.

---

# 24. SECURITY GUARDS

Restore helper debe exigir evidencia fuerte de entorno desechable.

No aceptar un booleano:

is_test=True

aportado libremente.

Preferir:

- explicit disposable DB identity;
- destination != source;
- production host/database fingerprint mismatch;
- environment guard;
- no IS_PRODUCTION target;
- explicit random restore identifier.

Un error nunca puede apuntar pg_restore a producción.

---

# 25. NO SHELL=TRUE

Subprocess:

NO shell=True.

Usar lista de argumentos.

Timeouts explícitos.

Capture stderr.

Sanitizar stderr antes de persistir/loguear.

No incluir connection secrets.

---

# 26. INTERRUPCIÓN

Si pg_dump o pg_restore termina con código !=0:

FAIL.

Eliminar archive parcial.

No registrar backup OK.

No rotar copias buenas anteriores.

Preservar última copia válida.

---

# 27. TOOL INSTALLATION

Preparar instalación reproducible del cliente PostgreSQL18.

Preferencia:

Mise/Railpack version pin.

No desplegar.

Demostrar en build/test:

pg_dump --version -> major18
pg_restore --version -> major18.

Si la vía elegida no garantiza major18:

BLOCK.

---

# 28. CI

Ejecutar:

suite actual completa del release base

+
POSTGRES_BACKUP_V2

+
PostgreSQL18 real/ephemeral.

Ruff.
Bandit.
Credential scan.
Dependency audit.
git diff --check.

No producción.

---

# 29. NO BRIDGE TODAVÍA

NO implementar aún:

runtime supported range73..79
db.init_db compatibility
readiness compatibility
downgrade guard bridge

hasta que:

BACKUP_V2 TECHNICAL PASS.

Después retomaremos:

codex/recovery-bridge-73-79

e integraremos este mecanismo de recovery de forma controlada.

---

# 30. ENTREGA LOCAL

NO PUSH inicialmente.

Devuelve:

BACKUP V2 STATUS

- branch;
- base SHA;
- changed files;
- pg_dump version;
- pg_restore version;
- installation/pinning method;
- archive format;
- manifest contract;
- credential handling;
- V1 behavior;
- V2 behavior;
- object classes preserved;
- backup73/restore73;
- backup79/restore79 with catalog73 runner;
- real clone79 test;
- tables source/restored;
- object inventory source/restored;
- counts/hash integrity;
- business15 diagnostic;
- docs archive;
- extension behavior;
- E post-restore status;
- full tests;
- PostgreSQL tests;
- security gates;
- remaining risks.

Final label only if all passes:

BACKUP_V2 TECHNICAL CODE-VERIFIED PASS
— G REAL BACKUP/RESTORE EVIDENCE STILL PENDING

Confirmar:

NO production access
NO production writes
NO main
NO push
NO deploy
NO bridge compatibility relaxation
NO financial operation
NO provider IO
NO G-LIVE
NO H