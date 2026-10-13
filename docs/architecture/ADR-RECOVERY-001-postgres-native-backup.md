# ADR Recovery 001 — PostgreSQL nativo autocontenido

Fecha: 2026-10-13. Estado: implementado localmente; sin autorización de despliegue.

El V1 conserva filas y columnas, pero reconstruye DDL con el catálogo del runner.
Un consumidor de catálogo 73 no puede restaurar tablas creadas por 74–79. Cambiar
`LATEST_VERSION` o el guard de arranque no resuelve la pérdida de DDL.

Decidimos utilizar `pg_dump --format=custom` y `pg_restore` 18.6 con esquema,
datos, secuencias y objetos desconocidos para Noesis. Noesis verifica y orquesta;
PostgreSQL produce y reconstruye DDL. No se ejecutan migrations en restore V2.
Se excluyen propietarios, ACL y tablespaces globales: la infraestructura de
destino aporta PostgreSQL y extensiones disponibles. No se exportan roles.
La base conserva encoding, proveedor/locale, LC_COLLATE/LC_CTYPE y reglas ICU;
una diferencia de versión de collation bloquea, no se oculta con hashes de filas.

Los recuentos y hashes se obtienen en una TX REPEATABLE READ READ ONLY y el dump
comparte su snapshot exportado. Las secuencias no son MVCC: un cambio entre las
lecturas antes/después invalida la copia. No convertir importes a float.

Un set completo consta de `.pgdump`, `.docs.zip` y `.manifest.json`. El manifest
se publica al final y contiene hashes, recuentos y huellas de definiciones,
nunca filas, SQL de funciones, credenciales, DSN ni nombres de documentos.
SHA-256 acredita integridad frente a corrupción; no autentica al custodio.

El destino lo crea una fábrica interna: instancia nueva, identidad aleatoria,
directorio privado, socket UNIX sin TCP. Una capacidad inmutable sólo vive
dentro de ese contexto; no admite DSN externa ni `is_test=True`. Debe existir
un namespace comprobable sin interfaces exteriores y un usuario POSIX no root.
La instancia se destruye al salir. No hay DROP/--clean en servidores existentes.
El worker aislado es requisito operativo; la web de producción no se convierte
automáticamente en ese worker ni obtiene un bypass del guard.

Mise fija `conda:postgresql@18.6`; `mise.lock` fija artefacto y dependencias
Linux x64 con SHA-256. Railpack autodetecta estos archivos y el build comprueba
las cinco herramientas. La instalación con Mise está probada en laboratorio;
el build y la organización del worker en Railway quedan para otra autorización.

V1 queda restringido al catálogo exacto que puede reconstruirse y a tablas y
columnas conocidas. Versiones futuras fallan antes de DDL PostgreSQL con
`LEGACY_BACKUP_REQUIRES_NEWER_SCHEMA_CATALOG`; no hay conversión automática.

Para schema >=78, restore devuelve separadamente
`POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED`, `serving_authorized=false` y
`g_real_evidence=false`. Este ADR no incorpora E ni G, no reconcilia supresiones
posteriores y no permite servir datos restaurados. Cifrado, custodia, retención,
registro E actual y evidencia real G siguen pendientes.

No se cambia el catálogo 73, `db.init_db`, readiness, guards ni cinco flags.
El Recovery Bridge 73↔79 es una unidad posterior independiente.

Referencias: [contrato](RECOVERY-BACKUP-V2-contrato.md),
[orden](RECOVERY-BACKUP-V2-orden.md), [cierre](RECOVERY-BACKUP-V2-cierre.md),
[Mise/Railpack](https://railpack.com/config/mise/),
[snapshot nativo](https://www.postgresql.org/docs/18/app-pgdump.html).
