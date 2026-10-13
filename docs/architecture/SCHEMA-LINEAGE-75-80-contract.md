# Schema lineage75–80 — contrato de diseño v1

Estado: **DESIGN ONLY**. [ADR](ADR-SCHEMA-LINEAGE-001-crm74-financial75-80.md),
[orden](SCHEMA-LINEAGE-75-80-orden.md), [catálogo de diseño](SCHEMA-LINEAGE-75-80-catalog-design.json).
Nada de este documento es código ejecutado, evidencia REAL ni permiso de migración.

## 1. Identidad y catálogo único

La futura fuente de identidades será un artefacto empaquetado y versionado,
conceptualmente `core/schema_lineage_catalog.json`. MIGRATIONS conserva callbacks;
sus pares version/name deben coincidir exactamente con ese catálogo. CI compara
ambos. No listas independientes por A–G ni normalización de nombres.

El JSON adjunto es **sólo diseño**, con los80 nombres exactos:1–74 extraídos por
AST de main678,75–80 definidos en esta orden. No cambia MIGRATIONS ni su latest.
En el port V2 inicial el catálogo propietario termina74;75–80 sólo se incorporan
cuando sus callbacks/perfiles físicos estén implementados y revalidados.
Un catálogo de reconocimiento histórico no concede propiedad de migración.

Observation conceptual: `lineage_id`, `schema_version`, `migration_identity`,
`lineage_fingerprint`, `integrity`, `object_profile_id`, `errors`.
Es global de infraestructura, no una lectura de filas financieras por negocio.
Resultados no equivalen a permisos, readiness, autenticación o tenant authority.

| lineage_id | Condición | Uso |
|---|---|---|
| CANONICAL_PRE74 | Prefijo exacto1..N, N=1..73; N=0 sólo bootstrap vacío demostrado | Migrador propietario y lectores explícitamente compatibles |
| CANONICAL_CRM74 | Prefijo1..74 exacto,74=CRM y objetos74 válidos | Runtime74/bridge74 y camino a75 |
| CANONICAL_CRM74_FINANCIAL75_80 | Prefijo exacto1..N, N=75..80, con objetos de cada etapa | Familia canónica; N sigue obligatorio, sólo N80 es CANONICAL80 |
| LEGACY_FINANCIAL74_79 | Sentinel74=evaluacion_readiness_financiera | Siempre bloqueado para runtime/migración canónicos |
| UNKNOWN_OR_CORRUPT | Cualquier otra secuencia/metadata/estructura | FAIL CLOSED |

El sentinel legacy prevalece en la clasificación, incluso si después hay gaps o
nombres mezclados: `integrity=CORRUPT` añade el diagnóstico, no legitima el legacy.
Legacy íntegro exige el prefijo histórico1..73 más A74..F79, sin CRM74 ni mezclas.
Una fila81, aunque venga detrás de80 correcto, es FUTURE_SCHEMA_UNSUPPORTED;
no se reduce la observación a80 ignorando filas extras.

## 2. Inspección read-only y errores cerrados

Detector futuro sobre conexión/FinancialSession prestada, target namespace
explícito, sin init_db, DDL, insert, conexión propia, commit, rollback o red:

1. Comprobar existencia/forma de schema_migrations, columnas/PK requeridas.
2. Leer **todas** las filas version/name/applied_at en orden numérico en snapshot
   consistente. Enteros estrictos positivos; sin bool/float, duplicados o NULL.
   Nombre Unicode exacto, sin trim, casefold ni alias. applied_at no se modifica.
3. Clasificar sentinel legacy; verificar pares completos contra el catálogo
   propietario/reconocedor adecuado y prefix continuo1..N. Ningún gap se rellena.
4. Verificar perfil físico conocido por dialecto/etapa: tablas, columnas/tipos,
   defaults, PK/FK/deferred, CHECK, índices, triggers y funciones propios de Noesis.
   Tabla A ausente con filaA75 presente no es canonical75 válido.
5. Recomputar fingerprint, no confiar en un hash/JSON del llamador. Devolver
   resultado cerrado y luego aplicar la política de compatibilidad del consumidor.

Sin tabla/filas de versiones y sin objetos Noesis: sólo migrador con bootstrap
explícito puede clasificar0. Sin metadata pero con objetos/datos: bloquear.
Una migración aplicada a medias, nombres inesperados, metadata presente sin sus
objetos o objetos financieros de etapas futuras no explicados bloquean; nunca
reparar nombres, recrear tablas ni marcar versiones por deducción.

Perfiles físicos: manifest por etapa y SQLite/PostgreSQL18, generado en DB
sintética y revisado. Descriptores semánticos ordenados sin OID, owner, rutas,
applied_at, claves privadas o datos. Namespace propio normalizado en descriptor,
pero el namespace real y conexión se verifican aparte. No usar igualdad textual
indiscriminada de DDL entre motores. Funciones/triggers verifican definición
esperada por hash, sin publicar cuerpo sensible. Sólo residuos documentados del
downgrade SQLite en modo sintético pueden admitirse; no abren runtime normal.
Objeto ajeno a Noesis no demuestra etapa; objetos extra propios desconocidos
bloquean. Un fingerprint de filas correcto no sustituye estos perfiles.

| Error | Motivo/acción |
|---|---|
| MIGRATION_IDENTITY_MISMATCH | Par version/name inesperado; sin corrección automática |
| MIGRATION_GAP | Falta una fila del prefijo; no rellenar |
| LEGACY_FINANCIAL_LINEAGE_DETECTED | Sentinel A74; sólo diagnóstico/recuperación futura aislada |
| FUTURE_SCHEMA_UNSUPPORTED | Número por encima del catálogo reconocido |
| SCHEMA_METADATA_INCOMPLETE | Tabla/PK/campos ausentes, NULL o duplicados |
| SCHEMA_OBJECT_MISMATCH | Registry y objetos incompatibles |
| UNKNOWN_SCHEMA_LINEAGE | Identidad sin perfil reconocido |
| SCHEMA_LINEAGE_MISMATCH | Consumidor/target requiere otra identidad válida |
| SCHEMA_LINEAGE_DRIFT | Observación/binding cambió durante un uso |
| MIGRATION_LOCK_TIMEOUT | Lock no adquirido en30s; no DDL |
| MIGRATION_PLAN_STALE | Base/catálogo/release del plan ya no corresponde |
| SCHEMA_TX_PROTOCOL_REQUIRED | TX prestada tomó snapshot antes del lock de identidad; propietario debe reiniciar el uso |

Sin secretos, SQL con parámetros reales, PII ni dumps en errores. Sólo versión,
nombre de migración público, perfil y código de error. Readiness rechazada por
lineage no persiste una evaluación en una tabla cuyo esquema no se reconoce.

## 3. Fingerprint canónico

Bytes UTF-8 del JSON **exacto**:

```json
{"format":"noesis.schema-lineage.v1","migrations":[{"name":"esquema_inicial","version":1}]}
```

Array contiene todos los pares aplicados, sorted por version ascendente. Keys
lexicográficamente ordenadas, separators coma/dos puntos sin espacios, ensure_ascii
false, sin newline/BOM, sin floats/NaN, strings exactos. SHA-256, hex minúscula64.
Ejemplo muestra sólo prefijo1; no representa80. Golden73/74/75..80 y legacy79
están en el catálogo de diseño. applied_at se excluye: instalaciones nuevas y
restores exactos pueden compartir identidad; la integridad de timestamps/filas
completas la conserva por separado el inventario del backup.

Pros: determinista entre motores, identifica cada prefijo y detecta nombres/gaps;
no ambiguo como concatenar strings con delimitadores. Contras: no prueba DDL,
procedencia, permisos, software desplegado, frescura ni aislamiento. Dos copias
del mismo esquema comparten hash; entorno/DB/tenant/code SHA deben vincularse
aparte. No HMAC ni firma, no autoridad criptográfica; no llamar a un hash READY.

`SchemaBinding v1` cerrado, futuro: `binding_version=1`, `catalog_id=canonical-v1`,
`lineage_id`, `schema_version` física real N, `lineage_fingerprint`,
`object_profile_id` (motor/etapa), `object_profile_hash` (perfil esperado revisado).
La comprobación de objetos debe pasar además de comparar hash del perfil.
No contiene migraciones duplicadas, credenciales, datos personales ni timestamp.
Runtime recomputa observación en cada uso; el binding serializado no es autoridad.
Binding del75 no se convierte en binding80, aunque ambos prefijos sean canónicos.

## 4. Ownership, startup y servicios

Migrador propietario80 admite0..80 **canónicos** para targets aprobados de su
catálogo. Valida después de adquirir lock y antes de crear metadata o hacer DDL;
revalida después de cada paso y antes de commit. Un target igual al observado,
completo y exacto retorna ALREADY_AT_TARGET sin writes. Origen cambiado a una
etapa distinta de origen/target autorizados produce PLAN_STALE. Identidades
legacy/unknown/future abortan antes de toda mutation.

Runtime normal canonical80 exige prefijo80+objetos80; no arranca scheduler,
workers, writers, init_db ni ready positivo con74/75..79/legacy/future. Health
puede comunicar proceso vivo; ready falla503 con razón saneada. Startup no migra
ni «repara» la BD. Conexión válida no equivale a esquema válido.

Antes de readiness, activation, preflight, restore y cada writer final se aplica
identidad exacta sobre misma conexión/TX/gate existentes. Compartir observación
inmutable **sólo durante esa TX**; no cache global por MAX. Guards SQL de writes
comparan todo el prefijo contra el catálogo compilado y binding de contexto,
además de guards de permiso/tenant/generación/capability existentes. Ningún
SQL guard pierde condiciones por renumerar. Runtime sin derecho a cambiar DDL o
schema_migrations; rol migrador separado no es autoridad financiera. Su
configuración real requiere autorización posterior, no la concede este documento.

History conserva tuplas exactas con identidad: diagnostic70..80, cutoff71..80,
import72..80, reconciliation73..80. N74 exige CRM; N75..80 exige cada prefijo
canónico completo y perfil. Legacy74–79 nunca entra por una tupla numérica.
Conexión/gate/TX, Decimal/NUMERIC, business_id y hashes históricos conservados.

## 5. Concurrencia de migración

Clave estable: primeros8 bytes SHA-256 de UTF-8
`bynoesis.schema-migrations.v1`, interpretados como int64 big-endian con signo.
Valor calculado en catálogo de diseño. Misma clave para todos los releases,
upgrade/downgrade y bridge; no incluye latest, SHA, deployment ni business.
Advisory locks PostgreSQL son por database: todos los despliegues sobre la misma
BD/namespace Noesis compiten; los targets de otra BD no afectan al origen.

`pg_try_advisory_xact_lock(key)` exclusivo, misma conexión/TX exterior del DDL.
Espera limitada a30s con reloj monotónico y sondeos250ms; timeout aborta sin DDL.
No sesión-lock que sobreviva al retorno de una conexión al pool. READ COMMITTED
para migrador; primera lectura registry después de lock, no snapshot obsoleto
tomado antes. Todas las etapas solicitadas en una TX, incluidos inserts de
metadata; crash libera lock/rollback, jamás filas «aplicadas» falsas.

Además, el migrador obtiene `LOCK TABLE schema_migrations IN ACCESS EXCLUSIVE MODE`
antes de inspección/DDL, excepto bootstrap0 donde aún no existe la tabla y no
puede servir ningún runtime. Se conserva hasta el commit exterior. Servicios
compatibles usan `LOCK TABLE schema_migrations IN SHARE MODE` como primera
operación tras BEGIN/SET TRANSACTION, **antes de cualquier SELECT/data statement**,
incluidos consultas de permisos/gate y funciones advisory por SELECT. Después
validan y conservan ese SHARE durante toda la TX prestada. lock_timeout30s,
sin session-lock ni conexión adicional. Migra: advisory exclusivo→registry
exclusivo→validación→DDL, nunca gate tenant. Service: registry SHARE→gate tenant→
validación→writer; no solicita advisory exclusivo, evitando inversión.

Esta regla evita que un SELECT para esperar un advisory lock congele un snapshot
REPEATABLE READ anterior al DDL. TX prestada que ya leyó sin protocolo se rechaza
con SCHEMA_TX_PROTOCOL_REQUIRED; sólo su propietario puede rollback/reintentar.
El servicio no reinicia ni degrada aislamiento. SHARE es compatible entre readers
y bloquea writes del registry, sin bloquear DML financiero de otras tablas.
La implementación futura debe verificar permisos/timeout y probar esta secuencia
en PostgreSQL18, incluida TX READ ONLY, no asumir que un lock tardío refresca snapshot.
DDL waits/statement timeout adicional acotado aborta el conjunto; no mata sesiones
ni desactiva guards para forzar paso. SQLite usa BEGIN IMMEDIATE exterior y busy
timeout30s, valida tras adquirirla, transacción de todos los pasos; no doble BEGIN.

El lock coordina sólo código que lo respeta. Antes de rollout se retiran caminos
viejos de preDeploy/startup capaces de DDL, y todas las réplicas usan bridge/
migrador compatibles; no puede afirmarse exclusión frente a un cliente anterior
sin lock. Manual DDL/migration no coordinada exige mantenimiento autorizado.

Fundamento verificado en documentación primaria: [locks advisory y de transacción](https://www.postgresql.org/docs/18/explicit-locking.html#ADVISORY-LOCKS),
[LOCK antes del snapshot repeatable read](https://www.postgresql.org/docs/18/sql-lock.html),
[aislamiento READ COMMITTED/REPEATABLE READ](https://www.postgresql.org/docs/18/transaction-iso.html).
La combinación, clave y tiempos son decisiones de este diseño; no una configuración aplicada.

## 6. Downgrade y rollback

Primero misma clasificación/lock/plan, después revisión de todos los callbacks
de bajada. Sólo DB sintética vacía o recuperación aislada específicamente
autorizada. Evidencia, supresiones CRM, ever_enabled, history, EE/Operations,
receipts/grants/provider attempts y resultados conservan todos sus bloqueos.
Un fallo intermedio revierte **todo**; no actualizar metadata antes del callback.

No usar80→74 como rollback productivo. Operacional: bridge compatible con80,
conservación y HOLD/pausa según contrato D/F/E, sin reactivar legacy después de
ever_enabled. Restore de punto antiguo requiere protocolo E y control de efectos
externos posteriores, no sólo un dump íntegro. Ninguna de esas acciones se ejecuta.

## 7. Backup/restore y bridge

V2 futuro mantiene archive `noesis-postgres-native-v2` y separa
`manifest_contract_version=2`: metadata nueva `schema_identity` con binding y
lista completa de pares. Verifica hash del manifest, dump/docs, inventario completo,
fila exacta de migrations (incluido applied_at), identidad y objetos restaurados.
No editar registry ni migrar durante restore. Deriva identidad desde origen con
snapshot exportado compartido con pg_dump; sin usar claims del cliente.

V2 viejo sin campos de lineage conserva bytes/hash y reader histórico; restore
aislado puede reconstruir y observar identidad desde filas/objetos reales, pero
el manifest viejo no se transforma en manifest nuevo ni serving/G evidence.
Lineage legacy se conserva como archivo histórico y se rechaza para serving.
La herramienta nativa puede verificar integridad sin poseer todas las migraciones;
si carece del perfil físico requerido, resultado IDENTITY_UNVERIFIED y no servir.

Regla E: perfil canónico con capability **PRIVACY_E** instalada (E79 o F80) exige
POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED y replay vigente de supresiones antes
de servir. D78 no tiene E: NO_E_INSTALLED, pero serving_authorized=false hasta
revisión de compatibilidad/privacidad; no «no hace falta privacidad». LegacyE78/
F79: LEGACY_RECOVERY_REQUIRED, no servir y conservar obligación de supresiones.
Unknown/missing identity bloquea; nunca elegir E por >=78 o >=79. Capabilities de
esquema son instalación técnica, distintas de capabilities/grants financieros.

V1: header schema_version no basta. Preflight offline parsea **todas** las filas
de schema_migrations del stream, catálogo de tablas/columnas y sus versiones,
sin ejecutar SQL ni importar la app.73 usa runner/catalog73, CRM74 runner74;
legacyFinancial79 usa sólo futuro workflow histórico aislado autorizado, nunca
runner canonical79. Metadata ausente/contradictoria: FAIL CLOSED. Catálogo80 no
reconstruye V1 de73 por improvisación. No relajar guards V1 de versión/columnas;
runner se selecciona explícitamente y se autentica su SHA/toolchain.

Bridge futuro: detector compartido, runtime permite **sólo** canonicalCRM74 o
canonicalFinancial80 completos.74 sirve comportamiento74 con flags OFF;80 impide
nuevos efectos financieros, conserva controles/captures/evidencia y no permite
fallback legacy tras ever_enabled. No inicia provider I/O; tratamiento de intentos
ya iniciados sólo bajo política D/F/E y autorización posterior.75–79 intermedios
no sirven, aunque un migrador los reconozca; ampliación exige necesidad y orden.
No owner80 implícito en startup bridge, ni downgrade a74 al arrancar sobre80.

## 8. CI y ramas paralelas

Artifact canónico por prefijo con nombres y hashes, comparación semántica con
latest main obtenido por fetch read-only en futura integración. Versiones únicas
y contiguas, nombres únicos, ninguna entrada/nombre histórico eliminado/cambiado;
callbacks AST y módulos DDL ya aplicados conservados. Nuevas versiones después
de latest main. Baseline CRM74 fijada y fingerprint esperado; manifest, registry,
DDL sintético, package-data y project-state deben coincidir. PR basado en main
obsoleto falla MIGRATION_PLAN_STALE; no regenerar baseline para silenciar CI.

Rama larga P2–P16: no reserva números globales por haberlos usado localmente.
Antes de integrar: fetch main actual→inspeccionar catálogo→asignar siguientes
números→revisar cambios de schema/bindings→CI collision gate. Branch protection/
merge queue exige gate fresco sobre tip main, no sólo SHA inicial del PR.
Cambiar tip main invalida la evidencia de integración; jamás force-push de
historia auditada. Correcciones nuevas append-only, fuentes históricas preservadas.

## 9. Invariantes y diagnóstico

Identidad ≠ integridad completa de datos ≠ autorización humana ≠ readiness ≠
activación. Policy E PROVISIONAL y PRIVACY_NOT_READY, niveles provider, UNKNOWN,
tenant isolation, no-authority IA, cinco flags OFF y guard producción D/G se
conservan. No GL/OpenItems/Tax/reporting nuevo ni cambios funcionales VERI*FACTU.
Diagnóstico expone código cerrado, lineage/prefijo/fingerprint públicos, nunca
secretos, claves verifier, respuestas provider o contenido de negocio.
