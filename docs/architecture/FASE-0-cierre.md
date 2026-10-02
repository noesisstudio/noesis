# Informe de cierre — Fase 0 del Financial Core

Fecha: 2-oct-2026. **Resultado: PASS, Fase 0 cerrada.** Alcance: exclusivamente fundamentos. Fase 1 no iniciada.

Código `9c538e37311b41bef7beca35f34bf55933de1cfe` publicado en main;
[CI 36984999111 verde](https://github.com/noesisstudio/noesis/actions/runs/36984999111).
Railway `eda63f25-eab3-45b2-91cc-9abbbdd254be` SUCCESS sobre ese código;
/health y /ready 200 con release 9c538e37311b y esquema 61. Las cinco variables
no están definidas en producción y sus valores por defecto verificados son false.
El commit posterior de cierre solo registra evidencia documental, sin tocar runtime.

## 1. Diagnóstico y unidades ejecutadas

Se reutilizan `db.Connection`, Cursor, `get_conn`, pool, migraciones y transacciones.
El gap era la normalización global NUMERIC → float y la concentración de dominios
en `db.py`. Cambiar el camino existente habría alterado las APIs y los cálculos.
Se eligió una vista exacta adicional, sin migrar consumidores ni datos.

Unidades: (0.1) cinco ADR y límites; (0.2) Money/Decimal; (0.3) conexión exacta
prestada; (0.4) paquetes y flags reservados; (0.5) gobernanza/estado; (0.6) pruebas,
autoauditoría y cierre. Tablas de producto afectadas: ninguna. Migraciones: ninguna.

## 2. Qué se ha construido

- Monolito modular con repositorios especializados futuros sobre una transacción
  común; el servicio posee commit/rollback. Nada de nuevos pools, ORM o brokers.
- `Currency.EUR`, `Money`, `parse_money`, `quantize_currency`, serialización
  canónica y suma/resta exactas. HALF_UP explícito, límites, inmutabilidad y rechazo
  de bool/float/NaN/infinito/textos ambiguos; independencia del contexto decimal.
- `FinancialSession` y `Connection.execute_exact`: Decimal NUMERIC nativo en
  PostgreSQL, TEXT exacto en SQLite, sin normalización legacy y sin adaptadores
  globales. Rechazo de floats en parámetros/resultados, también contenedores.
- Paquetes `core` y `accounting`; este último solo contiene documentación.
- Cinco flags del Master Plan apagados por defecto, todavía sin consumidores.
- ADR-001 a 005, guía 08, lectura heredable, secuencia 0–16, referencias originales
  con SHA-256 y autoridad explícita. La IA propone, sin autoridad financiera directa.
- Paso CI para probar el contrato nuevo contra PostgreSQL real.

## 3. Archivos y migraciones

Código: `src/noesis/core/{__init__,money,persistence}.py`,
`src/noesis/accounting/__init__.py`, `src/noesis/db.py`, `src/noesis/config.py`.
Configuración: `.env.example`, `.github/workflows/ci.yml`, `.gitattributes` (saltos Markdown de originales).
Tests: `tests/financial_core_contract.py`, `tests/test_financial_core.py`,
`tests/postgres_financial_core.py`.
Documentación: `AGENTS.md`, Arquitectura, Mapa-codigo, Decisiones, Inicio,
Estado-actual-main, Tareas-vivas, Registro-QA, Registro-cambios, project-state.json,
índice/guías de áreas 01/03/04/06/08 y carpeta `docs/architecture/` completa.

Se ajustó únicamente `uv.lock` para pypdf 6.16.1 → 6.19.0 y urllib3 2.7.0 → 2.8.0:
la auditoría detectó once avisos en esas dos versiones fijadas y quedó limpia al
actualizarlas. Sin dependencias nuevas ni cambios al contrato fiscal.
**Cero migraciones; esquema 61 conservado.** Las tablas de prueba son descartables.

## 4. Pruebas nuevas

16 pruebas locales: Money, precisión, empates de redondeo positivos/negativos,
acarreo y overflow, inválidos, inmutabilidad, contexto Decimal hostil, ida/vuelta
de céntimos, flags y contrato SQLite. 6 pruebas PostgreSQL: contrato común más
NUMERIC nativo, fechas nativas y JSONB sin floats. El valor
`9999999999999999.99` permanece exacto donde la lectura legacy pierde precisión.
Se verifican commit exterior, rollback conjunto legacy/nuevo, negocio explícito,
lecturas ausentes y rechazo de afinidad NUMERIC binaria de SQLite.

## 5. Validación ejecutada y resultado

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Nuevas Money/SQLite/flags | PASS | 16/16 |
| Nuevo contrato PostgreSQL 16.15 real | PASS | 6/6; instancia local descartable, no mocks |
| Suite general final de CI | PASS | 1.396/1.396 en 542,910 s; Python 3.13, entorno sincronizado con lockfile final |
| Regresión tras actualizar dependencias | PASS | 619/619 en 478,270 s; PDF, documentos, recibidas, WhatsApp, correo, adaptador, backend y fundamentos |
| SQLite upgrade/downgrade/upgrade | PASS | 0 → 61 → 0 → 61 |
| PostgreSQL históricos | PASS | Upgrade desde 32 con factura emitida |
| Servidor y rutas PostgreSQL | PASS | 36 rutas calientes sin 5xx |
| Código anterior contra BD nueva | PASS | Baseline esquema 53 contra 61: cliente/factura/emisión/cobro/exportación |
| Rollback PostgreSQL y privacidad | PASS | vigente → 55 → 54 → 53 → 54 → 55 → vigente; datos/inmutabilidad, concurrencia, aislamiento y recuperación |
| Arranque/parada HTTP SQLite | PASS | /health, /ready, / y /login responden 200 |
| JavaScript existente | PASS | 3/3, sin red |
| Ruff y Bandit | PASS | Sin hallazgos del gate configurado |
| Secretos | PASS | Archivos nuevos incluidos; sin ampliar baseline |
| pip-audit | PASS | Sin vulnerabilidades conocidas en entorno sincronizado |
| Lockfile | PASS | uv lock --check |
| Verdad documental y diff | PASS | check_project_truth y git diff --check |
| CI remota sobre código final | PASS | Run 36984999111, ambos jobs correctos; 6 PostgreSQL adicionales, 36 rutas y seguridad |

Incidencia local previa: 1.396 pruebas en 1003,041 s, con 1.395 correctas y un
error por detect-secrets ausente en Python global. La prueba pasó en el entorno
sincronizado y la CI final pasó la suite entera; no se ocultó ni aceptó el error.

No hay type checker configurado en este repositorio. Los scripts PostgreSQL
heredados emitieron avisos al terminar hilos del pool; acabaron con exit 0 y sus
aserciones pasaron. El nuevo script cierra explícitamente el pool. Avisos de
obsolescencia de Starlette/pypdf no son fallos de los tests.

## 6. Autoauditoría solicitada

| Riesgo revisado | Resultado | Conclusión |
|---|---|---|
| Duplicidad | PASS | Sin segundo pool, ORM, motor fiscal, pagos, bus ni repositorios vacíos con stubs |
| Aislamiento | PASS para fundamentos | La vista no elige negocio ni publica rutas; prueba SQL con business_id. Cada repositorio futuro deberá imponerlo y probar FKs/permisos; no se declara protección automática |
| Concurrencia/transacciones | PASS | Ningún estado mutable monetario; se comparte la conexión. Commit/rollback conjunto probado en ambos motores; sin nuevas escrituras de negocio |
| Dinero como float | PASS en núcleo nuevo | Money y vista exacta rechazan float; legacy continúa expresamente fuera del contrato nuevo |
| Idempotencia | PASS por alcance | No se crean comandos ni efectos financieros nuevos. Los futuros productores deberán imponer clave de operación y reintentos atómicos |
| Consistencia entre tablas | PASS | Ninguna tabla/doble escritura de dominio añadida; fallo local revierte escritura legacy y exacta de prueba |
| Rutas usando lógica antigua | PASS | Conservación deliberada en Fase 0; no se anuncia ni activa un lector financiero nuevo |
| Migraciones incompletas | PASS | No hay cambios de esquema ni backfill; ciclos históricos existentes superados |
| Deuda introducida | PASS acotado | Un puente pequeño execute_exact, flags reservados y accounting vacío exigidos por la fase; retirada/migración por flujo documentadas |
| Límite económico/operativo | PASS | quote.accepted/job.completed no son productores económicos automáticos; futura regla explícita con evidencia |

Preguntas previas del Master Plan, §44: esta fase **no produce ningún Economic
Event**, asiento, cuenta, TaxLine ni OpenItem; no aplica dimensión ni período a
una operación inexistente. No expone permisos nuevos. Es reversible por código,
no altera efectos repetibles y queda auditada por ADR, Git, estado y tests. En cada
fase funcional posterior habrá que responder esas doce preguntas por operación.

## 7. Compatibilidad, paralelo y riesgos conocidos

No cambia funcionalmente facturación, cobros, presupuestos, impuestos ni
VERI*FACTU. No cambian saldos, documentos emitidos, huellas, numeración o reglas
fiscales. La regresión cubre los workflows existentes; no equivale a certificación
legal ni prueba AEAT/Meta real.

Conviven temporalmente los contratos legacy y exacto, **sin dual-write ni nuevos
lectores de negocio**. Datos históricos DOUBLE/REAL no recuperan precisión por
convertirlos a Decimal. Cada futura migración requiere escala, conciliación y
tratamiento explícito de diferencias. Los intermediarios Decimal no se guardarán
en NUMERIC de menor escala sin redondeo validado por el dominio. En SQLite no
usar SUM/CAST sobre dinero TEXT. Solo EUR: no hay cambio de divisas.

Las versiones de bibliotecas corregidas se validan con regresión específica;
no se modifica su lógica en Noesis. Los gaps VERI*FACTU de la auditoría siguen
pendientes. El alcance no incluye proveedores externos, nuevas aprobaciones,
políticas fiscales ni activación de flags.

## 8. Criterios de salida y límite de la entrega

| Criterio | Estado |
|---|---|
| ADR de fundamentos y alternativas documentados | PASS |
| Money basado en Decimal y contrato de redondeo/errores | PASS |
| Decimal extremo a extremo sin normalización legacy | PASS |
| Repositorios por dominio diseñados con conexión/transacción compartida | PASS |
| Solo paquetes necesarios; accounting vacío | PASS |
| Cinco feature flags inicialmente apagados | PASS |
| AGENTS, arquitectura y guías alineados; IA sin autoridad directa | PASS |
| Gobernanza y referencias heredables sin contexto del chat | PASS |
| Separación Domain/Operational Events y Economic Events | PASS |
| SQLite/PostgreSQL, precisión, rollback y compatibilidad probados | PASS |
| Autoauditoría y ausencia de implementación fuera de fase | PASS |
| CI verde del código final | PASS |

**Todos los criterios de salida de Fase 0: PASS.**

No se han construido economic_events, journal_entries, journal_lines, plan
contable, Open Items, Tax Ledger, reporting, asientos ni cambios funcionales en
VERI*FACTU. La siguiente fase del Master Plan es **Fase 1: Economic Event Layer**,
con catálogo corregido por ADR-002; requiere una nueva orden. **No iniciada.**

## 9. Diagnóstico y rollback

Si falla lectura nueva, comprobar tipo de columna, afinidad SQLite, floats JSON,
escala y uso de FinancialSession; no modificar globalmente normalización legacy.
Si falla una escritura mixta, comprobar que ambos repositorios reciben la misma
Connection y que nadie confirma dentro. Para revertir fundamentos, revertir su
commit sin migrar datos ni recalcular huellas; conservar las correcciones de
seguridad del lockfile para no reintroducir los avisos ya corregidos.
