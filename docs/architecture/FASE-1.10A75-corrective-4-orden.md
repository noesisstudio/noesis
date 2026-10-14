# BYNOESIS — 1.10A75 CORRECTIVE #4
## Cierre de los dos bloqueos PostgreSQL restantes

**OBJETIVO:** Resolver exclusivamente los dos bloqueos demostrados en la CI `38587900781`, sin rediseñar A75, sin relajar controles y sin avanzar a fases posteriores.

### 1. Estado de partida obligatorio

- Rama: `codex/phase-1-10a75`
- HEAD esperado: `93dbac0390de6438767e37e4b40f78137c6874d7`
- `origin/main` esperado: `678bd3fdf2f9891b373b0fe8d46ac37b97f0310d`
- CI anterior: `38587900781`
- CI general: SUCCESS.
- PostgreSQL 18.6: 18/20 etapas PASS.
- Readiness: 29/29 PASS.
- V2: 73/73 PASS.

Antes de actuar:

1. Verifica las referencias remotas y locales.
2. Comprueba el árbol de trabajo y todos los cambios pendientes.
3. Si existe drift inesperado, DETENTE y explica el motivo.
4. Conserva íntegro todo lo aprobado del Corrective #3.

### 2. Bloqueo A — Stage 17

**Error demostrado:**

`ModuleNotFoundError: No module named 'tests'`

En `scripts/run_postgres_backup_lab.py`, modifica exclusivamente la invocación del escenario `privacy + rollback` para ejecutarlo como módulo:

```python
("privacy + rollback", ["-m", "tests.postgres_release_smoke"])
```

Comprueba que `tests.postgres_identity_diagnostic` se importa correctamente desde la raíz del repositorio.

No elimines instrumentación, pruebas, diagnósticos ni verificaciones de seguridad.

La nueva ejecución debe cubrir realmente:

- T1 y T2.
- Ciclo 75→55→54→53→54→55→75.
- Snapshots y conservación de datos.
- Inmutabilidad fiscal.
- Privacidad y aislamiento entre tenants.
- Protección frente a downgrades no autorizados.

Un Stage 17 que solo consiga importar el módulo no cuenta como PASS.

### 3. Bloqueo B — Stage 19

**Error demostrado:**

`SCHEMA_OBJECT_MISMATCH` durante `downgrade(55)` por comparación de una dirección PostgreSQL convertida a texto con máscara `/32`.

Archivo:

`src/noesis/schema_retention.py`

Sustituye exclusivamente:

```sql
inet_server_addr()::text AS address
```

por:

```sql
host(inet_server_addr()) AS address
```

Conserva la comparación cerrada con los valores permitidos actuales: `NULL` y `127.0.0.1`.

No amplíes el conjunto de direcciones admitidas.

Añade o adapta regresiones dirigidas para demostrar que:

- El loopback legítimo se reconoce correctamente.
- Direcciones distintas siguen rechazadas.
- Entornos no aislados siguen rechazados.
- La condición de producción continúa bloqueando el acceso.
- Se mantienen las exigencias de propietario, permisos, directorio, red y locking.

**No se permite debilitar ningún guard para hacer pasar las pruebas.**

### 4. Validación de los perfiles TECHNICAL_ONLY

Ejecuta pruebas PostgreSQL reales sintéticas para los cuatro perfiles:

- retained53
- retained54
- retained55
- retained58

Cada perfil debe demostrar:

1. Identidad física exacta y hash esperado.
2. Integridad `TECHNICAL_ONLY` exclusivamente.
3. Rechazo de runtime, readiness, binding y serving.
4. Rechazo de objetos incompletos, modificados, desconocidos o futuros.
5. Ausencia de concesiones de autoridad.
6. Retorno a canonical75 cuando corresponda, con integridad `VERIFIED`.

No basta con comprobar que existen los perfiles.

### 5. Protocolo de ejecución

Primero ejecuta las comprobaciones locales y regresiones dirigidas que sean posibles sin WSL.

Después, si no hay fallos:

1. Revisa el diff exacto.
2. Confirma que el cambio de producto se limita a la corrección de representación de la dirección, y que los cambios de test/CI son los mínimos necesarios.
3. Crea **un único commit correctivo**, con padre directo `93dbac0`.
4. Push normal exclusivamente a `codex/phase-1-10a75`.
5. Ejecuta una CI fresca mediante `workflow_dispatch`, asociada al nuevo SHA.
6. Comprueba el resultado completo de ambas jobs y los logs de todas las etapas.

No reutilices resultados PASS antiguos como evidencia del nuevo candidato.

### 6. Criterios de aceptación obligatorios

**CI GENERAL**

- Full Python suite SUCCESS.
- Cero FAIL y cero ERROR.
- Solo skips previstos y justificados.
- Node SUCCESS.
- Ruff, Bandit, secret scan y dependencias SUCCESS.
- Lineage, collision, project truth, enlaces y migraciones SUCCESS.

**POSTGRESQL 18.6**

- Exactamente 20/20 etapas PASS.
- Etapa 17: escenario completo PASS.
- Etapa 18: Readiness PASS.
- Etapa 19: Lineage Foundation, 18/18 PASS.
- Etapa 20: V2, 73/73 PASS.
- Todos los perfiles TECHNICAL_ONLY verificados.
- Cero FAIL, ERROR y skips inesperados.
- Instancias sintéticas aisladas, sin conexiones externas.

Si aparece cualquier fallo nuevo, documenta el diagnóstico y DETENTE. No realices otro correctivo automático.

### 7. Límites absolutamente congelados

PROHIBIDO:

- WSL.
- Cambios en migraciones históricas.
- Modificar canonical profiles.
- Relajar guards de identidad, migración, seguridad o serving.
- Activar flags.
- Producción o Railway real.
- Proveedores reales.
- Merge o push a main.
- Rebase, force-push o amend.
- B76–F80.
- Recovery Bridge.
- G-LIVE.
- H.
- Expansión funcional del producto.

La deuda de seguridad HIGH debe mantenerse identificada y separada. No afirmar que está resuelta.

### 8. Entrega final obligatoria

Devuélveme un informe verificable con:

- SHA nuevo y SHA padre.
- Estado de main.
- Archivos modificados y resumen del diff.
- URL e ID de la nueva CI.
- Resultado de ambas jobs.
- Tabla completa de las 20 etapas PostgreSQL.
- Pruebas de retención 53/54/55/58.
- Resultado de Readiness y V2.
- Guards y controles conservados.
- Errores, skips y advertencias pendientes.
- Evidencia de ausencia de cambios fuera del alcance.

**Decisión final:**

Solo declarar:

`1.10A75 REMOTE CODE-VERIFIED PASS`

si se cumplen absolutamente todos los criterios anteriores.

En cualquier otro caso:

`1.10A75 CORRECTIVE #4 — BLOCKED`

No confundas código implementado con código validado. No ocultes fallos ni declares cierre parcial como definitivo.

**Prioridad: corrección mínima, evidencia máxima y seguridad intacta.**