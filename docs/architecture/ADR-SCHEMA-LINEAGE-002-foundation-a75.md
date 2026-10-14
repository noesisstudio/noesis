# ADR Schema Lineage002 — Foundation + A75 local

Decisión nueva del13-oct-2026, [orden](FASE-1.10A75-orden.md). Sólo candidate
local75; producción permanece CRM74. [Diseño original](SCHEMA-LINEAGE-75-80-contract.md)
y [mapping](SCHEMA-LINEAGE-75-80-mapping.md) permanecen históricos e intactos.

Identidad = prefijo completo ordenado version/name + shape de metadata + perfil
físico. MAX sólo sigue existiendo como diagnóstico legacy, nunca como autorización
del migrador, startup, history o readiness. Catálogo empaquetado1..75 único;
76..80 sólo diseñadas, no ownership ni aceptación. Legacy74–79 se reconoce para
conservación técnica y se bloquea para serving/migración canónicos.

Perfiles físicos: deltas estructurales revisados por motor/prefijo1..75, construidos
exclusivamente en fixtures. Incluyen tablas/columnas/defaults/checks/FKs/índices/
triggers/funciones/secuencias. No datos, OID, owner, rutas ni applied_at. Se cachea
el catálogo esperado inmutable; cada uso reobserva DB, sin cache global por MAX.
Objetos ajenos preservables en V2 no acreditan serving ni una etapa nueva.

Migrador: misma conexión/TX, advisory exclusivo xact PostgreSQL con clave estable
2533761095082033151 y espera30s/sondeos250ms, después registry ACCESS EXCLUSIVE.
READ COMMITTED; reread tras locks y validación antes/despuésDDL; commit exterior.
No-op exacto no toca registry/timestamps. Caller propietario de restore V1 puede
haber inspeccionado su destino vacío en RC: no reutilizar esos reads; releer bajo
lock. RR previo nunca se degrada ni reinicia. Runtime/helper prestado usa registry
SHARE antes de cualquier snapshot/permission/gate; lock tardío rechaza protocolo.
Permisos MAINTAIN/lock y roles productivos no se configuran en esta entrega.

SQLite conserva TX exterior BEGIN IMMEDIATE/busy30s del migrador. Residuos de
bajada histórica sólo en owner técnico: sales_prospects con estructura74 exacta
tras bajarCRM; document_profiles vacío con sus dos índices exactos al llegar0,
metadata0 ya existente. No bootstrap con objetos desconocidos, datos de perfiles
ni ausencia de registry. Ningún residuo permite runtime0/73 o cambia callbacks.

A75 conserva semántica A histórica, pero crea nuevas evaluaciones/context/proofs2
con SchemaBinding1 actual y provenance readiness_v2. Profile/policy/canonical y
contratos monetarios/económicos/history conservan versiones. A74 no se reescribe,
no se recalcula evidencia real ni se reutiliza como autoridad A75. IA sin autoridad.
Policy profesional provisional/PRIVACY_NOT_READY; cinco flags OFF. No activation,
generation1, grants, handoff, EE, Operations, providers, B76–F80 ni Recovery Bridge.

Startup sólo sirve canonical75 completo; sin init_db/reset/migraciones automáticas.
La propiedad de migrations pertenece al proceso explícito independiente. History
acepta sus prefijos mínimos70/71/72/73 hasta75 por identidad exacta. V1 exige runner
75/catalog75, sin promoción74; V2 preserva registry/fingerprint/objetos del snapshot,
restaura sin migrations, no serving. A75 = NO_E_INSTALLED, E legacy por nombre.

CI protege versiones/nombres únicos, append-only desde main autorizado y AST/DDL
históricos; fetch main actual→inspect latest→validate lineage→allocate next.
Drift de main/catálogo invalida la integración, no se regenera baseline para ocultarlo.

[Régimen de locks PostgreSQL18](https://www.postgresql.org/docs/18/sql-lock.html)
y [aislamiento](https://www.postgresql.org/docs/18/sql-set-transaction.html)
respaldan el orden de lock antes del snapshot; los tiempos/clave son decisiones
aprobadas del proyecto. El protocolo READ ONLY/RR se verifica en fixture PG18.

Revalidacion de regresiones: PostgreSQL compara ordinales logicos de columnas
visibles, no attnum interno (DROP/ADD conserva huecos). Tipos, nullability,
defaults, checks, FKs, indices, triggers y funciones siguen exactos. Se reconoce
solo para owner68 el cuerpo historico cerrado cash_payment_delete de antiguo66,
reproducido por la regresion69 preservada; perfil/hash de variante separado.
Otra funcion/cuerpo falla;69 debe reparar y75 exige el perfil normal completo.
No se aceptan cuerpos arbitrarios ni se modifican callbacks historicos.
SAVEPOINT previo al primer lock se rechaza: no perder un lock por ROLLBACK TO;
los savepoints posteriores conservan el lock exterior. Sin rollback/commit propio.

Coste verificado: la primera matriz PG inventory paso37 en437.669s con lexer sin
memoizacion. Se memoiza exclusivamente tokenizacion pura por texto DDL ya leido,
con4096 entradas, tokens inmutables y copia por llamada. Nunca resultados de DB,
registry, perfiles observados ni observaciones por MAX. Cada TX vuelve a leer los
objetos actuales; cambios de SQL y guards ausentes siguen fallando, incluso con
cache caliente. Hashes/perfiles y semantica del lexer permanecen identicos.

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
