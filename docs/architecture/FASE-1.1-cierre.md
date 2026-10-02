# Cierre de Fase 1.1: contratos de Economic Events

Fecha: 2-oct-2026. Base: `main` actualizado desde `f01937e`, limpio antes de editar.
Trabajo sobre `C:/Users/mikic/Documents/noesis`, donde está registrado `main`;
el checkout de la conversación es un worktree antiguo. Sin push ni despliegue.

## Entrega y archivos

Creados:

- `src/noesis/economic_events/__init__.py` y `contracts.py`.
- `tests/test_economic_events.py`.
- `docs/architecture/ECONOMIC-EVENTS-v1.md`, `FASE-1-plan.md` y este informe.

Modificados: `AGENTS.md`; `docs/Arquitectura.md`, `Decisiones.md`,
`Estado-actual-main.md`, `Mapa-codigo.md`, `Tareas-vivas.md`, `Registro-cambios.md`,
`Registro-QA.md`, `project-state.json`; `docs/architecture/README.md`, ADR-002;
`docs/areas/01-vision-general.md` y `08-financial-core.md`.

Ningún archivo runtime existente se modifica. No cambian `db.py`, config,
migraciones, productores, adaptadores, rutas, flags ni dependencias.

## Contrato, catálogo y decisiones

[Contrato completo y los once tipos](ECONOMIC-EVENTS-v1.md): versión de payload 1,
campos requeridos/opcionales, origen, importe, fechas, relaciones e impactos
declarativos para cada tipo. `EconomicEvent`/`EventRelation` congelados; copias
profundas inmutables del mapping. Validación también en construcción directa.

Decimal/EUR con precisión final exacta; rechazar fracciones de céntimo no nulas,
sin redondeo implícito. JSON monetario con strings de dos decimales. Hash del
payload tipado separado del hash del sobre; canonicalización propia v1 con
vector de bytes esperado, distinta de RFC 8785 y de una identidad de comando.
Mismo contenido normalizado conserva hash; cambios relevantes lo cambian.

Business_id obligatorio ahora, no solo reservado para persistencia. Referencias
declaradas al mismo negocio y tipos compatibles, sin demostrar pertenencia real.
Snapshots before/after de recibidas; amount sustitutivo, sin sumar dos compras.
Rectificativas exigen `rectification_method=I`, sin soportar sustitución.
Retiradas contienen importe contextual, sin devolución implícita. Conciliación
y anulación fiscal solo Evidence; anulación no afirma aceptación AEAT.
Fechas desconocidas permanecen null cuando el contrato lo permite.

Sin discrepancias de alcance respecto al diseño aprobado. Se concretan en 1.1
tipos, campos, normalización e invariantes locales que la referencia dejaba por
especificar. El plan aprobado se incorpora a documentación durable para continuidad.
No se implementa el sobre persistente completo, evidencia de autorización ni
identidad/idempotencia de operación: corresponden a unidades posteriores.

## Pruebas y límites

- Nuevas: **21/21** de contratos, revalidadas junto con **16/16** Money/flags/SQLite
  tras los últimos ajustes: **37/37 en 0,226 s**.
- Suite general: **1414/1414 en 874,087 s**, Python 3.12 del entorno sincronizado.
  Descubrió las 18 pruebas nuevas iniciales; las tres adicionales y el último
  ajuste del discriminante de rectificación se validaron en el run dirigido final
  de 37. No presentar el run general como una ejecución de 1417 casos finales.
- PostgreSQL 16.15 real: **6/6** fundamentos en 0,162 s sobre /noesis_ci local;
  humo sobre base nueva noesis_phase11_smoke, migrada 0→61: **36 rutas sin 5xx**.
  Incidencias previas: rol inicial inexistente y outbox consumida en base reutilizada;
  conexión corregida y humo repetido en base limpia. Un intento inicial sobre base
  limpia sin migrar también se rechazó; aplicado el esquema y repetición correcta.
- SQLite: ciclo aislado **0→61→0→61 correcto**, base temporal descartada.
- Ruff completo, Bandit, secretos con archivos nuevos versionados, uv lock --check,
  pip-audit (sin vulnerabilidades conocidas; paquete local no publicado excluido)
  y Node **3/3**: correctos. Verdad documental, enlaces locales y diff: correctos.
- Inspección AST: ningún import del paquete desde runtime/productores existentes;
  solo stdlib/Money en el contrato. Los cinco flags siguen False.
- Autoauditoría local completa; sin CI remota ni despliegue de esta unidad.
  Los avisos/simulaciones de error de la suite pertenecen a fixtures existentes;
  la conclusión de unittest es OK, sin errores/fallos.

El contrato nuevo no contiene SQL ni accede a conexiones: no tiene una variante
SQLite/PostgreSQL que implementar. Las pruebas reales de ambos motores cubren
los fundamentos y compatibilidad existentes; no prueban persistencia de eventos.
No se requiere migración, pruebas de posting ni aceptación de AEAT/Meta en 1.1.

## Autoauditoría del Master Plan (§44)

| Pregunta | Respuesta y límite de 1.1 |
|---|---|
| ¿Cuál es el Economic Event? | Uno de los once tipos cerrados; operaciones de presupuesto/trabajo y pago a proveedor excluidas |
| ¿Genera asiento? | No; impactos futuros son declarativos y no tienen consumidores |
| ¿Qué cuentas afecta? | Ninguna; plan contable/GL no implementados |
| ¿Genera TaxLines? | No; Tax es metadato para reglas posteriores |
| ¿Genera/compensa OpenItems? | No; AR/AP son posibilidades futuras |
| ¿Qué dimensiones tiene? | Solo negocio/origen/fechas y relaciones del contrato; sin motor de dimensiones |
| ¿Qué permisos requiere? | Usar un objeto puro no ejecuta nada; futuras operaciones exigirán permisos/aprobación verificables, nunca autoridad IA |
| ¿Es reversible? | No hay efecto a revertir; identidad/payload inmutables, corrección/retirada por hechos nuevos enlazados |
| ¿Es idempotente? | Validación y canonicalización deterministas; no implementa deduplicación de operación ni garantiza exactly-once |
| ¿Funciona en período cerrado? | No abre/cierra/contabiliza períodos; conserva fechas conocidas sin fabricar fecha contable |
| ¿Cómo se audita? | Payload/hash/sobre/revisión/relaciones permiten trazabilidad declarativa; no hay auditoría persistente ni firmas |
| ¿Cómo se prueba? | Veintiuna pruebas nuevas, regresiones monetarias/legacy y gates documentados |

Revisión adicional: sin duplicar pools ni motores, sin imports de productores,
sin acceso a datos; snapshots cerrados congelados recursivamente; float rechazado;
contexto Decimal global no afecta cálculo; business_id y relaciones declaradas
coherentes; no generación de dinero/impuestos/asientos; esquema 61 y flags intactos.
Concurrencia, atomicidad, rollback del productor e idempotencia de comando se
auditarán cuando haya persistencia/operaciones; no se presentan como implementados.

## Criterios de salida

| Criterio de 1.1 | Resultado | Evidencia |
|---|---|---|
| Paquete y contrato puro, sin efectos | PASS | Dos archivos nuevos runtime; sin conexiones ni consumidores |
| Catálogo cerrado de once tipos, separado de operativos | PASS | Enum/MappingProxy y pruebas de exclusión, incluida supplier_payment.made |
| Payloads v1 y campos obligatorios/opcionales cerrados | PASS | EventSpec/Field, snapshots y rechazos por tipo/versión/campos |
| Decimal/EUR, ningún float y dinero JSON string | PASS | Validación, límites, signos, céntimos y contexto global adverso |
| Orígenes, amount, fechas, relaciones e impactos explícitos | PASS | Catálogo v1 y validación del sobre/relaciones declaradas |
| Canonicalización/hash deterministas | PASS | Vector esperado, orden, opcionales, Decimal/string y cambios relevantes |
| Identidad/payload/snapshots inmutables | PASS | Dataclasses congeladas y copia profunda de mappings |
| IA sin autoridad financiera | PASS | Sin permisos/ejecución; campo de aprobación IA rechazado |
| Sin persistencia/productores/tablas/fases posteriores | PASS | Diff runtime exclusivamente aditivo; esquema 61, flags intactos |
| Comportamiento legacy y VERI*FACTU conservados | PASS | Suite general, fundamentos SQLite/PG y humo PostgreSQL; sin edición legacy |
| Tests nuevos, regresiones y gates aplicables | PASS | Resultados y límites de los runs registrados arriba |
| Gobernanza documental heredable y autoauditoría | PASS | AGENTS/guías/estado/ADR/plan/contrato/QA/bitácora y §44 |
| Detención antes de 1.2 | PASS | Sin contratos de comandos, autorización, repositorios o migración nuevos |

## Riesgos y continuidad

- El contrato valida estructura/coherencia local, no autenticidad, existencia,
  permisos, aprobación ni pertenencia real de fuentes/relaciones. Las siguientes
  unidades deberán comprobarlo transaccionalmente; no usar el objeto como permiso.
- Hashes no son firmas, protección frente a un actor con escritura ni claves de
  deduplicación de operaciones. UUID distintos permiten operaciones legítimas iguales.
- Desgloses desconocidos no se completan; v1 no incorpora líneas/tipos fiscales,
  divisas, sustitución de rectificativas, pago a proveedor ni reversión de cobro.
  Ampliarlos exige decisión/versionado, sin caer en un catálogo genérico.
- Un mapping no conserva claves duplicadas de JSON; el futuro decoder debe
  rechazarlas antes de validarlo. Textos Unicode se preservan, sin normalización NFC.

Diagnóstico: revisar EventSpec, versión, datos canónicos y relaciones declaradas.
Rollback: revertir esta unidad; no requiere migración ni modifica datos/huellas.
Fase 0 permanece cerrada. **No comenzar 1.2 sin orden explícita**.
