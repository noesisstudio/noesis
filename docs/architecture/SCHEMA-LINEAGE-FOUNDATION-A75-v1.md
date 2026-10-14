# Schema lineage foundation — contrato instalado local A75

[Orden](FASE-1.10A75-orden.md), [ADR](ADR-SCHEMA-LINEAGE-002-foundation-a75.md),
[cierre](FASE-1.10A75-cierre.md), [paridad](FASE-1.10A75-parity.md).

src/noesis/schema_lineage.py define LineageId/Observation/SchemaLineageError,
classify_registry, fingerprint, inspect, require_compatible/require_runtime,
begin_schema_access, lock_migrator y guard registry SQL compilado. Conexión/TX
prestadas; ninguna conexión/commit/rollback/red propios. Metadatos globales de
infraestructura no son filas financieras ni autoridad tenant.

Estados: CANONICAL_PRE74; CANONICAL_CRM74;
CANONICAL_CRM74_FINANCIAL75_80 (familia, sólo75 instalada);
LEGACY_FINANCIAL74_79; UNKNOWN_OR_CORRUPT. Recognition no es ownership.
Observation REGISTRY_ONLY no acredita objetos; require exige VERIFIED y versión
permitida. Sentinel legacy prevalece también con gap/mixed; nunca se adopta.

CATALOG empaquetado1..75, version/name estricto, no trim/alias/bool/float/duplicados.
Fingerprint SHA256 UTF8 JSON noesis.schema-lineage.v1, keys ordenadas, separators
sin espacios/ASCII folding/newline/BOM, pares ordenados; applied_at excluido.
CRM74 golden intacto y canonical75 golden aprobado del diseño; no autoridad.

Shape schema_migrations exacto y PK version, name/applied_at NOT NULL, tipos de
cada motor históricos. Inspección sólo SELECT/PRAGMA; bootstrap0 exclusivamente
owner vacío demostrado. Cada perfil estructural cubre columnas/checks/FKs/
índices/triggers/functions/sequence definitions por motor. No OID/owner/valores
ni timestamps de fila. Binding cerrado1 incluye catalog_id, lineage_id,
schema_version física, lineage_fingerprint, object_profile_id/hash. Se recomputa
en la conexión/TX actual: una copia JSON/hash no habilita nada.

PostgreSQL consumer: BEGIN/SET TRANSACTION exterior→SET LOCAL lock_timeout30s→
registry SHARE→permission/gate→inspect/use. Datos/snapshot/acceso nativo previo
sin protocolo rechazan SCHEMA_TX_PROTOCOL_REQUIRED; no retry/isolation/commit
propios. Migrator READ COMMITTED→advisory xact2533761095082033151→registry exclusivo→
registry/perfil→DDL+fila→postvalidator, todo en una TX. Timeout/crash abortan conjunto.
SQLite begin exterior obligatorio en consumer y BEGIN IMMEDIATE owner; sin doble
BEGIN. Residuo técnico0/CRM descrito en ADR, sin ampliar runtime.

Errores cerrados: MIGRATION_IDENTITY_MISMATCH, MIGRATION_GAP,
LEGACY_FINANCIAL_LINEAGE_DETECTED, FUTURE_SCHEMA_UNSUPPORTED,
SCHEMA_METADATA_INCOMPLETE, SCHEMA_OBJECT_MISMATCH, SCHEMA_LINEAGE_MISMATCH,
SCHEMA_LINEAGE_DRIFT, SCHEMA_TX_PROTOCOL_REQUIRED, MIGRATION_LOCK_TIMEOUT,
MIGRATION_PLAN_STALE. Sin contenido sensible/SQL con parámetros ni DSN.

V2 conserva inventory completo de objetos ajenos; chequea mínimos estructurales A
para registry75 y no confunde esa integridad técnica con perfil completo runtime.
Restored snapshot exacto sin migrations, serving_authorized=false/g_real_evidence=false.
NO_E_INSTALLED en75. V1 catálogo75 exacto,73/74 sólo otro runner específico; no puente.

El ordinal PG representa orden visible; huecos internos attnum no son drift.
Variante historica DELETE68 solo owner, cuerpo exacto conocido y hash de perfil
separado;69 la repara. UNKNOWN no se adopta. SAVEPOINT anterior al lock falla
SCHEMA_TX_PROTOCOL_REQUIRED; nunca rollback/restart/isolation propios.

/ready vuelve a inspeccionar identidad/perfil actuales; nunca responde READY por
MAX=75 ante drift. Backup SQLite valida el perfil completo de su copia. V1 exige
catalogo75 en origen/preflight/restore; el MAX anterior deja de ser autoridad.
V2 toma SHARE del registry antes de pg_export_snapshot y de inventory, tambien
en verificacion del restore, sin migrations ni serving; valida metadata PK/tipos/
NOT NULL en todas las lineages conocidas y minimos A75 cuando corresponde.

Coste verificado: la primera matriz PG inventory paso37 en437.669s con lexer sin
memoizacion. Se memoiza exclusivamente tokenizacion pura por texto DDL ya leido,
con4096 entradas, tokens inmutables y copia por llamada. Nunca resultados de DB,
registry, perfiles observados ni observaciones por MAX. Cada TX vuelve a leer los
objetos actuales; cambios de SQL y guards ausentes siguen fallando, incluso con
cache caliente. Hashes/perfiles y semantica del lexer permanecen identicos.

Bootstrap0 valida tambien el DDL/PK/columnas exactos del propio registry antes de
cualquier callback. Registry vacio malformado no se adopta. Los perfiles monetarios
precisos usados historicamente por tests son variantes sinteticas separadas; nunca
parte del catalogo de producto ni un permiso de transformar fuentes reales.

Compatibilidad tecnica SQLite sintetica: los callbacks antiguos retienen columnas,
indices y, en ciertos recorridos profundos, omiten triggers operativos al re-upgrade.
Se versionan deltas completos de recorridos75->target->75 generados en DB vacia
propia, sin regeneracion runtime/CI ni expectativas derivadas de la DB examinada.
Solo el owner exclusivo, IS_PRODUCTION=false, DATABASE_URL vacia, DB_PATH temporal
Y fichero real de PRAGMA database_list identico puede reconocer esas estructuras.
El resultado es TECHNICAL_ONLY, nunca VERIFIED. El migrador puede completar la
prueba tecnica; require_compatible, require_runtime, binding, A75 y serving la
rechazan, incluso dentro de esa misma TX. Ninguna variante habilita escritura
financiera ni modifica guards. Un guard financiero ausente, columna adicional,
path diferente, production o consumidor corriente siguen fallando. No se afirma
rollback/recuperacion productiva. Las tres tablas A y sus guards canonicos siguen
intactos; los perfiles canonicos y goldens originales no cambian. El roundtrip
profundo sintetico no es evidencia de que el schema resultante sea apto para servir.
