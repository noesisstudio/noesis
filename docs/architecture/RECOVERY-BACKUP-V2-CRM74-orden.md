# RECOVERY BACKUP V2 — PORT A CURRENT MAIN CRM74
# IMPLEMENTACIÓN LOCAL
# SIN PRODUCCIÓN / SIN PUSH / SIN DEPLOY

ESTADO CANÓNICO

CURRENT MAIN / PRODUCTION CODE:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

CURRENT CANONICAL SCHEMA:

74

MIGRATION74:

captacion_hoja_y_tipo

CRM74 está aplicada en producción y es historia durable.

NO renombrar.
NO borrar.
NO reutilizar.

---

BACKUP V2 HISTÓRICO VALIDADO

Rama histórica:

codex/recovery-backup-v2

Commit histórico:

f272582663f35a6e1c6ed9e34e8b0e737d235b49

Parent:

08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d

Estado histórico:

BACKUP_V2 TECHNICAL CODE-VERIFIED PASS
— G REAL BACKUP/RESTORE EVIDENCE STILL PENDING

Ese commit NO existe todavía en origin.

NO modificarlo.
NO rebasearlo.
NO force-push.
NO convertirlo en main.

Debe conservarse como evidencia histórica.

---

SCHEMA LINEAGE DESIGN APROBADO

Nueva lineage canónica diseñada:

74 = CRM captacion_hoja_y_tipo
75 = Financial A readiness
76 = Financial B antecedentes
77 = Financial C fiscal cancellation
78 = Financial D handoff/generaciones
79 = Financial E privacy/export/retention
80 = Financial F providers/preflight
G = sin migration; requiere canonical80

PERO:

A75–F80 NO se implementan en esta orden.

Recovery Bridge NO se implementa.

---

OBJETIVO

Crear un nuevo port de:

RECOVERY BACKUP V2

sobre el CURRENT MAIN CRM74.

El resultado debe ser:

MAIN CRM74
+
todo el comportamiento actual CRM/producto
+
Backup V2 nativo PostgreSQL18

SIN:

- Financial A75–F80;
- migration75;
- schema80;
- bridge;
- G-LIVE;
- deploy.

---

# 1. RAMA NUEVA

Crear desde exactamente:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

rama:

codex/recovery-backup-v2-crm74

Verificar:

git merge-base HEAD main

y que el parent/base inicial sea exactamente:

678bd3fdf2f9891b373b0fe8d46ac37b97f0310d

NO partir de f272.

NO rebasear f272 encima.

---

# 2. PORT, NO SNAPSHOT

Portar la FUNCIONALIDAD de:

f272582663f35a6e1c6ed9e34e8b0e737d235b49

sobre main actual.

NO reemplazar archivos actuales por las versiones antiguas.

Especialmente preservar:

- CRM nuevo;
- migration74;
- db.py actual;
- scheduler actual;
- NLU/voz actual;
- precios actuales;
- pyproject actual;
- templates CRM;
- assets CRM;
- Node local_dates;
- documentación actual;
- current project-state factual data.

Usar:

git diff
git show
comparaciones por archivo

para portar únicamente el delta Backup V2.

No cherry-pick ciego.

---

# 3. FUNCIONALIDAD V2 A CONSERVAR

Conservar del V2 histórico:

PostgreSQL native backup basado en:

pg_dump
pg_restore

Formato:

native archive
+
documents zip
+
manifest.

Toolchain:

PostgreSQL18

versionado/reproducible.

Conservar:

- pg_dump major guard;
- pg_restore major guard;
- snapshot coherente;
- hashes;
- counts;
- inventario completo;
- sequence state;
- object inventory;
- extensions inventory;
- restore a DB aislada;
- no migrations durante restore V2;
- protección destino;
- no shell=True;
- secret handling;
- stderr sanitizado;
- timeouts;
- fail closed;
- documentos;
- V1 compatibility;
- V1 future schema fail closed;
- POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED;
- no serving automático.

---

# 4. MAIN CRM74 ES FUENTE DE VERDAD

El catálogo del port debe ser:

1..74 del current main.

Migration74 exacta:

74 / captacion_hoja_y_tipo

No importar:

74 / evaluacion_readiness_financiera

desde ninguna rama antigua.

No añadir:

75.

LATEST_VERSION debe continuar:

74.

---

# 5. V1 EN CURRENT MAIN

Adaptar V1 para catálogo exacto CRM74.

V1 sigue siendo:

catalog-dependent.

Debe:

PASS únicamente cuando header/schema/tables/columns
son compatibles con el catálogo que realmente conoce.

No relajar.

Debe distinguir:

V1 schema73
vs
V1 canonical CRM74
vs
legacy Financial74
vs
future schema.

No usar sólo MAX(version).

Si no puede demostrar identidad:

FAIL CLOSED.

---

# 6. BACKUP V2 — MIGRATION IDENTITY

El V2 nuevo debe incluir identidad explícita del registry.

No necesitamos implementar todavía todo el runtime
SCHEMA-LINEAGE validator A75–80.

Pero el manifest V2 debe capturar como mínimo:

ordered migration identities:

[
  [1, name1],
  ...
  [74, "captacion_hoja_y_tipo"]
]

y un fingerprint determinista:

SHA-256
sobre representación canónica
de todos los pares version/name.

NO applied_at en fingerprint.

NO secrets.

NO authority.

Objetivo:

un backup no se identifica sólo con:

schema_version = 74.

Debe poder distinguir:

CRM74

de:

legacy Financial74.

---

# 7. MANIFEST CONTRACT

Diseñar/implementar una revisión compatible del manifest V2.

Preferencia:

manifest contract v2
o equivalente explícito.

Debe contener:

format_version
created_at
schema_version
migration_identities
schema_lineage_fingerprint
source_server_version
source_server_major
pg_dump_version
pg_restore/tool metadata si corresponde
archive_sha256
archive_size
documents_sha256
documents_size
table_count
table_counts
required_extensions
archive_toc_hash
encoding
locale/collation metadata relevante

No PII.

No secrets.

---

# 8. RESTORE IDENTITY

Tras pg_restore:

leer:

schema_migrations

y comparar EXACTAMENTE:

version
name
order

contra el manifest.

Calcular de nuevo fingerprint.

Debe coincidir.

No editar:

schema_migrations.

No ejecutar migrations.

No “arreglar” lineage durante restore.

---

# 9. LEGACY FINANCIAL74

Crear fixture explícito:

74 / evaluacion_readiness_financiera

El V2 puede preservar físicamente ese archive
si el archive ya contiene esa lineage.

Pero NO debe clasificarlo como:

canonical CRM74.

Manifest debe conservar esa identidad exacta.

Si una operación exige current canonical CRM74:

rechazarla.

No convertir.

---

# 10. PRIVACY SEMANTICS

No usar ya la regla conceptual:

schema >=78 => privacy E

como criterio futuro.

En este port CRM74:

no hay E instalada.

Para archives históricos legacy79:

conservar la información histórica
y la regla conservadora existente.

Pero preparar el contrato para que,
cuando llegue canonical E79,
la reconciliación se determine por:

migration identity / installed capability

y no únicamente por número.

NO implementar A75–E79.

No rebajar protecciones actuales.

---

# 11. TOOLCHAIN

Portar:

mise.toml
mise.lock
toolchain checks
PostgreSQL18 pin
Railpack additions
CI integration

sin destruir cambios actuales de main.

Comprobar:

pg_dump --version
pg_restore --version

major18.

Server test:

PostgreSQL18.

---

# 12. RAILPACK

Main actual mantiene sus necesidades actuales.

Integrar V2 conservando:

Tesseract packages

y cualquier configuración actual.

No sustituir railpack.json
por una copia vieja completa.

Resultado debe contener:

current main requirements
+
Backup V2 toolchain.

No deploy.

---

# 13. CI

Main actual añadió:

tests/local_dates.test.cjs

Conservarlo.

Integrar también la matriz V2.

No perder tests CRM.

No perder ningún gate actual.

---

# 14. TESTS — CURRENT MAIN

Ejecutar suite COMPLETA actual.

No basta con repetir los 1820 tests antiguos.

El total probablemente será mayor
porque main tiene CRM nuevo.

Registrar total real.

Debe incluir:

CRM tests
main backend tests
history
financial core existente 0–1.9
Node current
Backup V2.

---

# 15. MIGRATION TESTS

Obligatorios:

0→74
32→74
73→74

con:

74 / captacion_hoja_y_tipo.

Rechazar:

74 con nombre incorrecto
gap
duplicate version
future unknown
corrupt registry.

No migration75.

---

# 16. BACKUP V2 TESTS

Ejecutar de nuevo la matriz V2 completa.

Como mínimo:

A–Y histórica
+
identity additions.

Necesitamos demostrar:

backup canonical CRM74
→ restore canonical CRM74

con:

same migration identities
same lineage fingerprint
same DDL
same rows
same sequences
same object inventory.

---

# 17. UNKNOWN FUTURE OBJECT TEST

Mantener la propiedad central de V2:

un runner que NO conoce los objetos
debe poder restaurarlos porque pg_restore
reconstruye DDL nativo.

Crear fixture aislado:

canonical CRM74
+
objetos adicionales desconocidos por el runtime.

Añadir:

table
column
index
CHECK
FK
deferred FK
function
trigger
type/domain/enum
view
sequence/identity

Backup
→ restore.

Todos deben sobrevivir.

Esto NO convierte el fixture en canonical75.

Es únicamente una prueba de independencia del catálogo.

---

# 18. LEGACY79 REGRESSION

Si el laboratorio/synthetic fixture del V2 histórico
puede recrearse SIN usar producción:

repetir:

legacy Financial79
→ V2 backup
→ V2 restore

con runner current-main-based.

Expected:

physical restore PASS

lineage:

LEGACY_FINANCIAL74_79

NO canonical80.

NO serving authorization.

POST_RESTORE_PRIVACY_RECONCILIATION_REQUIRED
según semántica histórica aplicable.

No usar business real para crear ese fixture.

---

# 19. BUSINESS15

NO tocar producción.

No acceder a business15.

No EMPTY.

No evidence.

Los tests usan tenants sintéticos.

---

# 20. BACKUP V2 ADMIN

Portar cambios necesarios de admin actual.

IMPORTANTE:

main extrajo CRM de admin.py.

No reintroducir rutas CRM antiguas.

Añadir únicamente UI/endpoint V2 necesario
sobre la estructura actual.

No exponer:

backup path
tokens
DB URL
credentials.

---

# 21. SECURITY

Ruff
Bandit
credential scan
dependency audit
git diff --check.

No secrets nuevos.

No connection strings en fixtures/docs/logs.

---

# 22. DOCUMENTACIÓN

Actualizar documentación factual del current main.

NO sobrescribir:

CRM74
current test counts
main history.

Preservar los documentos históricos del V2 original
como historia.

Crear adenda/port actual.

Por ejemplo:

RECOVERY-BACKUP-V2-CRM74-port.md

Explicar:

historical V2 commit:
f272...

canonical port:
nuevo SHA futuro.

---

# 23. SCHEMA-LINEAGE DESIGN

No modificar los documentos aprobados salvo:

corrección factual estrictamente necesaria.

El port debe cumplir:

SCHEMA-LINEAGE-75-80 DESIGN PASS.

No implementar A75–F80.

---

# 24. CI COLLISION GUARD

NO hace falta implementar todavía
todo el nuevo collision guard de migrations.

Pero los tests del port no pueden introducir
otra migration74.

Si descubres que V2 necesita DDL persistente:

DETENTE.

Backup V2 NO debería requerir migration propia.

---

# 25. NO PROD

No Railway.

No production DB.

No production backup.

No SSH.

No provider.

No real restore.

Sólo local/ephemeral PostgreSQL18.

---

# 26. RESULTADO LOCAL

Cerrar sólo si:

CURRENT MAIN FUNCTIONAL SUITE PASS

+
CRM PASS

+
MIGRATIONS74 PASS

+
BACKUP V2 CRM74 PASS

+
LINEAGE IDENTITY PASS

+
UNKNOWN OBJECT RESTORE PASS

+
SECURITY PASS.

Etiqueta:

BACKUP_V2_CRM74 LOCAL CODE-VERIFIED PASS

No llamarlo REMOTE CODE-VERIFIED todavía.

---

# 27. NO PUSH

Esta orden es LOCAL.

NO push.

NO PR.

NO main.

NO deploy.

---

# 28. ENTREGA

Devuelve:

BACKUP V2 CRM74 PORT STATUS

1. branch;
2. base SHA;
3. final local SHA;
4. parent;
5. changed files;
6. comparison against historical f272;
7. CRM74 preserved yes/no;
8. LATEST_VERSION;
9. migration registry identity;
10. manifest contract;
11. lineage fingerprint;
12. V1 behavior;
13. V2 behavior;
14. toolchain version;
15. railpack changes;
16. current full suite counts;
17. CRM test counts;
18. PostgreSQL test counts;
19. V2 test counts;
20. migration matrix;
21. canonical74 backup/restore;
22. unknown objects fixture;
23. legacy79 fixture if run;
24. security gates;
25. docs;
26. risks;
27. limitations.

Confirmar:

NO migration75
NO Financial A–F
NO bridge
NO production access
NO production writes
NO backup real
NO business15
NO push
NO main
NO deploy
NO G-LIVE
NO H.

FINAL:

BACKUP_V2_CRM74 LOCAL CODE-VERIFIED PASS

o:

BLOCKED

con causa exacta.