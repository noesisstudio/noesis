# Recovery Backup V2 — contrato técnico

Fecha: 2026-10-13. Rama local `codex/recovery-backup-v2`, catálogo propio 73.
Base exacta: `08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d`.
Únicamente recovery; no bridge, activación ni importación de código A–G.

## API y archivos

`web/postgres_native_backup.py` expone `create`, `load_set`, `verify` y `restore`.
La exportación acepta conexión de origen y callbacks documentales legacy.
`restore` acepta exclusivamente la capacidad interna emitida por
`disposable_target`; nunca una DSN o un booleano de entorno.
`web/postgres_backup_tools.py` controla procesos, libpq y la instancia propia.
`web/postgres_backup_inventory.py` compara el catálogo y los datos raw.
`web/backups.py` selecciona V2 como nuevo default PostgreSQL; SQLite conserva
su camino. V1 tiene entrypoint explícito y sólo se reconstruye con catálogo exacto.

El set tiene el mismo basename: `.pgdump`, `.docs.zip`, `.manifest.json`.
La descarga admin de V2 entrega un ZIP con los tres, conserva la autorización
admin existente y elimina sólo ese ZIP temporal después de enviarlo. La subida
offsite existente incluye el manifest; tres éxitos son necesarios para éxito
del set. No se ha ejecutado subida offsite real en esta fase.

## Manifest cerrado

`format_version=noesis-postgres-native-v2`; `created_at` UTC;
`source_database_fingerprint` de instancia/OID/DB hasheados;
`source_server_version`, `source_server_major`, `pg_dump_version`, `pg_dump_major`;
`schema_version` real; `application_code_sha` SHA válido o null;
`archive_sha256`, `archive_size`, `documents_sha256`, `documents_size`;
`table_count`, `table_counts`, `table_data_hashes`; `required_extensions`;
`archive_toc_hash`, `archive_object_classes`; `objects`, `sequence_states`;
`database_settings` (encoding, provider, LC_COLLATE/LC_CTYPE, locale, versión de
collation y reglas ICU). El destino conserva estos parámetros y bloquea drift
antes del restore; locale/encoding no se infieren del template local del worker.

Las claves de tablas son pares JSON `[schema,table]`, sin whitelist de migrations.
El inventario recorre todos los schemas de usuario y datos de tablas ordinarias,
particiones y vistas materializadas; `ONLY` evita doble recuento por herencia.
Hashes de filas preservan Decimal, tipos, bytes y fechas sin normalización legacy.
El multiset de hashes detecta filas alteradas, ausentes y duplicadas sin depender
del orden físico. Memoria y lecturas son O(n); futura estrategia escalable podrá
usar ordenación externa por bloques. No se ha optimizado prematuramente.

`objects` contiene recuento/hash por schemas, relaciones, columnas, índices,
constraints, funciones, triggers, views, tipos, collations, policies y definiciones de
secuencias. No publica cuerpos SQL ni literales personales. PK/UNIQUE/CHECK/FK
y deferred/validated se comparan. La normalización de CHECK sólo aplana AND/OR
asociativos iguales; conserva literales, operadores y agrupación aritmética.
El TOC nativo normaliza IDs de catálogo y orden, hashea las entradas completas
y cuenta sus clases; no se imprime el TOC del laboratorio real.

## Consistencia e integridad

TX de origen REPEATABLE READ READ ONLY → snapshot exportado → inventario completo
→ pg_dump compartiendo snapshot → relectura de secuencias e inventario → docs
verificados → hashes → publicación del manifest. Cambios no congelables de
secuencias invalidan la copia; no hay escritura de aplicación en origen.
Los documentos conservan el ZIP y su manifest interno de hashes existente.
El filesystem no comparte snapshot con PostgreSQL: requiere documentación
estable durante copia; no acredita automáticamente todos los links DB→filesystem.

Falta/corrupción/hash/TOC distinto bloquean antes del restore. Tras restore se
comparan todas las tablas, hashes de datos, definiciones, secuencias, versión y
extensiones y se hace SELECT de humo. Ninguna migración del consumidor se ejecuta.

## Seguridad

Binarios 18 comprobados antes del dump; cliente menor que servidor bloqueado.
Build fijado a 18.6, tanto dump/restore como initdb/pg_ctl/postgres. Lista de argv,
`shell=False`, timeout explícito, stderr capturado y descartado: errores públicos
son códigos fijos. No registrar argv, DSN, SQL o valores del driver.
Entorno libpq explícito; no hereda PG*, DATABASE_URL ni tokens. PGPASSFILE temporal
0600 en directorio 0700, también vacío si no hay password, evita `~/.pgpass`.
Se limpia siempre. V2 exige almacenamiento POSIX privado; Windows usa WSL.
Formato comprimido no es cifrado: archivos locales contienen datos personales.

Restore crea un cluster nuevo sin listener TCP, DB aleatoria y directorio propio;
comprueba fingerprint, `data_directory`, vacío, vigencia y consumo de capacidad.
Usuario no root y namespace Linux sólo loopback son condiciones observables.
No `--clean`; `--single-transaction --exit-on-error`; instancia propia destruida
incluso ante fallo. Una capacidad consumida nunca puede reutilizarse.
No se descargan extensiones: nombre y versión deben existir en el destino antes
del DDL; ausencia bloquea. Roles, ACL y tablespaces del origen no se recrean.

Un fallo elimina exclusivamente el nuevo set parcial, no registra OK, no rota
ni sube. La rotación V2 conserva/elimina conjuntos completos ya íntegros.
Manifest sin firma no acredita procedencia ni legalidad; se admiten únicamente
archives de origen y custodia autorizados. El namespace impide I/O de proveedor.

## V1 y separación E/G

V1 exacto73 y estructura conocida sigue probado. V1 superior al catálogo o con
tabla/columna desconocida falla antes de DDL PostgreSQL. Versiones antiguas
distintas requieren su runner de catálogo correspondiente; no se promocionan.
No conversión automática V1→V2. No se cambia el guard de arranque ni se permiten
aplicaciones73 sobre79 por haber restaurado correctamente.

`noesis-restore-check --native-archive /ruta/archivo.pgdump` verifica sin iniciar
DB de aplicación, sin migrations y sin registrar evidencia G. Exige worker
aislado no root. Resultado técnico incluye `serving_authorized=false` y
`g_real_evidence=false`; para >=78 añade
`POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED`. Aplicar el registro E actual y
su mecanismo aprobado es una fase posterior; no se declara G RESTORE PASS.

## Laboratorio y gates

`scripts/run_postgres_backup_lab.py` crea fuente sintética propia y ejecuta todas
las matrices PostgreSQL del release base más POSTGRES_BACKUP_V2. Sólo la fuente
sintética permite loopback TCP porque tests legacy reconstruyen su URL. Todo
está dentro de namespace sin interfaces externas. Los destinos V2 conservan
exclusivamente sockets UNIX. No admite restauraciones QA ni backups reales.
El ensayo real autorizado utiliza orquestación privada fuera de Git y sólo
copias PREDEPLOY73/79. No se conservan dumps ni hashes reales en documentos Git.

Leer [ADR](ADR-RECOVERY-001-postgres-native-backup.md),
[orden](RECOVERY-BACKUP-V2-orden.md) y [cierre](RECOVERY-BACKUP-V2-cierre.md).
