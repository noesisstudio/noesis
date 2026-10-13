# Recovery Backup V2 — informe de cierre local

Fecha: 2026-10-13. Estado: BACKUP_V2 TECHNICAL CODE-VERIFIED PASS
— G REAL BACKUP/RESTORE EVIDENCE STILL PENDING.
Rama: `codex/recovery-backup-v2`.
Base exacta: `08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d`.
Catálogo propio: 73; catálogo79 sólo en copia aislada autorizada, sin importar A–G.

Implementación, contrato y límites en [ADR](ADR-RECOVERY-001-postgres-native-backup.md),
[contrato](RECOVERY-BACKUP-V2-contrato.md) y [orden](RECOVERY-BACKUP-V2-orden.md).

## Resultados ya observados

- Mise versionado 2026.10.8 y conda PostgreSQL18.6 instalados y ejecutados.
- pg_dump/restore/initdb/pg_ctl/postgres18.6; lock Linux x64 con hashes.
- POSTGRES_BACKUP_V2 A–Y más ocho defensas adicionales:33 PASS.
- Contratos portables y seguridad:20 PASS en Linux; Windows omite sólo permisos POSIX.
- Clone73:112 tablas; clone79:148 tablas; runner catálogo73. Integridad completa
  de counts, filas, objetos y secuencias; fuentes idénticas antes/después.
- Business15 existe y todos los contadores financieros presentes son cero;
  ningún writer de aplicación. El esquema73 carece de tablas provider79: no
  confundir ausencia física con evidencia de provider real.
- Encoding UTF8 y locale libc C.UTF-8 idénticos en ambos restores reales. Collations
  de usuario desconocidas y drift del locale probados en fixtures.
- Documentos: ZIP asociado verificado, hashes íntegros. Referencias/huellas/dumps
  del ensayo real sólo en almacenamiento privado fuera de Git.
- Extensiones existentes comparadas por nombre/versión; falta bloqueada.
- >=78: POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED, serving_authorized=false,
  g_real_evidence=false. No G RESTORE/BACKUP PASS.

## Validación completa

Suite general fresca:1820 tests en2230.461s,1817 PASS,3 skips,0 FAIL,0 ERROR.
Dos skips heredados son de PostgreSQL y están cubiertos en History cutoff; el
tercero exige permisos POSIX y pasó en Linux. JavaScript:9 PASS,0 FAIL.
Matrices base PostgreSQL seleccionadas exactamente como CI:394 PASS. Matriz V2:
33 PG +20 contratos portables,53 PASS. El recorrido PostgreSQL completo final,
incluido HTTP/default backup/restore, terminó con todos los jobs PASS. Tras el
último hardening V1 se repitieron los53 casos:23.067s,0 FAIL,0 ERROR.
Ciclo73→0→73, Ruff, Bandit, secretos,
dependencias (sin vulnerabilidades conocidas), verdad documental, AST y diff PASS.
Los primeros procesos WSL de suites se interrumpieron sin resultado final; no se
incluyen como éxito. No se ha demostrado una causa. La suite general completa
posterior Windows terminó limpia; PG se relanzó en un namespace nuevo.
Una conexión WSL posterior devolvió E_UNEXPECTED; el log y código de salida
confirman que la ejecución final ya había terminado correctamente. Se recuperó
sólo la distribución PREDEPLOY autorizada y la última matriz53 también pasó.
CI remota no ejecutada: la orden prohíbe push. Workflow preparado localmente.

| Matriz PostgreSQL | Casos | Resultado |
|---|---:|---|
| Core | 6 | PASS |
| Operations/Auth | 37 | PASS |
| Economic Events | 28 | PASS |
| Borrowed writers | 18 | PASS |
| Invoice Capture | 27 | PASS |
| Payment/Bank | 41 | PASS |
| Supplier/Expense | 44 | PASS |
| Channels | 50 | PASS |
| History inventory | 37 | PASS |
| History cutoff | 50 | PASS |
| History import | 25 | PASS |
| History reconciliation | 31 | PASS |
| POSTGRES_BACKUP_V2 | 33 | PASS |
| Contratos portables Linux | 20 | PASS |

Migrations32→73 con datos, humo HTTP, backup/restore nativo por fachada, privacidad/
bajas, código anterior catálogo53 y rollback protegido: todos PASS. Los conteos
no suman retests ni duplican contratos portables dentro de la suite general.

## Inventario real source/restored

Cada celda contiene source = restored. No se publican hashes reales en Git.

| Categoría | Schema73 | Schema79 |
|---|---:|---:|
| Tablas | 112 =112 | 148 =148 |
| Schemas usuario | 1 =1 | 1 =1 |
| Relaciones (incluye índices y secuencias) | 560 =560 | 661 =661 |
| Columnas de relaciones | 2407 =2407 | 2951 =2951 |
| Índices | 378 =378 | 443 =443 |
| Constraints, incluido NOT NULL PG18 | 1573 =1573 | 2253 =2253 |
| Funciones | 204 =204 | 672 =672 |
| Triggers usuario | 207 =207 | 672 =672 |
| Tipos, incluidos arrays/composites de tablas | 224 =224 | 296 =296 |
| Secuencias | 70 =70 | 70 =70 |
| Views / policies / collations usuario | 0 =0 | 0 =0 |

El fixture futuro prueba enum/domain/view/collation e hstore además de PK,
UNIQUE, CHECK, FK deferred, function, trigger e identity con gap hasta500.
En los clones reales la extensión es plpgsql1.0; ambos ZIP contienen18 documentos.
Todos los hashes de filas/definiciones/estados de secuencia y counts coinciden;
la fuente antes/después también. Business15 tiene invoices/payments/received/
expenses/bank/cancellations/EE/Operations/Authorizations/attempts/results=0 en79,
y todas las tablas presentes a cero en73. Ninguna escritura de aplicación en15.

## Archivos creados/modificados

Código: web/backups.py, web/routers/admin.py; nuevos web/postgres_native_backup.py,
web/postgres_backup_tools.py, web/postgres_backup_inventory.py.
Pruebas: tests/test_postgres_backup_v2.py, tests/postgres_backup_v2.py.
Tooling: mise.toml, mise.lock, railpack.json, .github/workflows/ci.yml;
scripts/check_postgres_toolchain.py, run_postgres_backup_lab.py, mise-linux-x64.sha256.
Gobernanza: AGENTS.md; architecture/README, orden/contrato/cierre Recovery V2 y
ADR-RECOVERY-001; project-state.json, Estado-actual-main, Tareas-vivas,
Registro-cambios, Registro-QA, Mapa-codigo, Decisiones; guías01/02/06/07/08.
Orquestación, resultados, dumps y manifest reales permanecen fuera de Git.

## Riesgos y trabajo posterior

- Railpack declara Mise/lock y gate de build; instalación real demostrada en lab,
  no se ha construido/desplegado imagen Railway. El worker de restore debe ser
  no root, POSIX y sin outbound. La web ordinaria falla cerrada sin ese entorno.
- Archive comprimido contiene datos personales; cifrado/custodio/retención y
  procedencia autorizada son prerrequisitos operativos, no propiedades del formato.
- Secuencias no MVCC: drift invalida; filesystem no comparte snapshot de DB.
- Se excluyen roles/ACL/tablespaces globales. Extensiones disponibles exactas.
- Hashes no son firma ni autoridad; verificación O(n), memoria de hashes por tabla.
- Reconciliación E actual y evidencia G pendientes; policy real no aprobada.
- Bridge, compatibility range, db.init_db y readiness siguen intactos. No G-LIVE/H.

## Autoauditoría técnica

| Pregunta | Resultado |
|---|---|
| Rama aislada y base exacta, sin A–G | PASS |
| V2 contiene DDL nativo independiente de catálogo | PASS |
| Snapshot compartido y fuente READ ONLY | PASS |
| Tabla/columna desconocida preservadas | PASS |
| Decimal raw sin normalización legacy | PASS |
| Índices/PK/UNIQUE/CHECK/FK/deferred preservados | PASS |
| Funciones/triggers/types/domain/views preservados | PASS |
| Secuencias conservan valor y is_called | PASS |
| Inventario completo, no sólo KEY_TABLES | PASS |
| Manifest/docs/archive requeridos y verificados | PASS |
| Herramientas18 y servidor más nuevo bloqueado | PASS |
| Password temporal privado y sin argv/logs | PASS |
| No shell, timeout, errores sanitizados | PASS |
| Destino propio vacío/identidad/consumo comprobados | PASS |
| Restore sin migrations ni --clean | PASS |
| Extensión ausente bloquea, no descarga automática | PASS |
| Fallo conserva copias buenas y no rota/sube | PASS |
| V1 futuro falla antes de DDL | PASS |
| E/G separados, sin autoridad/activación | PASS |
| Encoding, locale y collation no cambian silenciosamente | PASS |
| Suite completa y gates finales | PASS |

No producción, writes producción, main, push, deploy, relajación del bridge,
operaciones financieras reales, provider I/O, G-LIVE ni H.
