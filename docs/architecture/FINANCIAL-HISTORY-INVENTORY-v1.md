# Financial History — diagnóstico persistente v1

[Orden](FASE-1.9B-orden.md), [ADR015](ADR-015-financial-history-diagnostic-inventory.md),
[fuentes reales](FASE-1.9B-fuentes.md). Complementa contratos puros
[1.9A](FINANCIAL-HISTORY-v1.md); no sustituye sus hashes ni permisos.

## API interna

```python
from noesis.financial_history.service import HistoryDiagnostics

# Principal procede de autenticación real del servidor. UUID explícita del run;
# versión de código/copia provienen del entorno confiable, nunca del modelo IA.
manifest = HistoryDiagnostics(business_id, page_size=64).run(
    principal, manifest_uuid,
    repository_version=repository_version,
    environment_identity="synthetic-fixture",
)
```

Sin router, tool, scheduler, CLI de producción ni productores. No ejecutar sobre
producción/copia real en1.9B. Tests usan SQLite TEMP y PG local /noesis_ci.
Todos los flags deben estar OFF. Principal real, is_active, session_version y
business_id se validan en cada TX; el negocio debe permitir escritura. No actor
original supuesto ni autorización financiera. Reintento mismo run/código/operador/
copia recupera el resultado; contenido incompatible falla o genera drift. Otra
UUID solicita diagnóstico nuevo. No reabrir un manifest congelado.

## Persistencia y estados

| Tabla | Contenido y garantías |
|---|---|
| financial_history_manifests | negocio/run, modos falsos de certificación/importación por CHECK, versiones, scope/código/copia/operador, timestamps, lifecycle/result, hashes y summary |
| financial_history_items | origen/clave/revisión/slot, evento propuesto nullable, raw canónico/hash, assessment ejes separados/regla, plan nullable/hash, dependencias resueltas/no resueltas, cobertura y resultado terminal |
| financial_history_incidences | 14 códigos de1.9A, UUID por item+code, severidad/hash/version, open/time; append-only |
| financial_history_decisions | actor autenticado/permiso/UUID, kind/ref/reason/interpretación/antecedente/time; append-only, FKs tenant |

scanning inserta evidencia; planning clasifica una vez; frozen fija todos los
hashes y summary. Resultado exclusivamente READY_FOR_REVIEW/BLOCKED. No READY_FOR_IMPORT.
No delete de ninguna fila con evidencia, ni modificar items clasificados. Decisión
posterior agrega una fila y deja plan original intacto. Downgrade70 vacío seguro;
con filas denegado. Las migraciones62–69 no cambian.

## Raw y procedencia

RawSource es cerrado por SourceSpec; campos físicos, clave y MoneyObservation.
Observación monetaria conserva storage_class físico, tipo/valor del driver
representado como texto/bits, texto SQL y float8send PG cuando aplica. MoneyEvidence
contiene tipo/provenance, bits binary64, Decimal.from_float exacto del binario,
candidato HALF_UP/delta exclusivamente diagnósticos. Los campos finales del
candidato usan Decimal y JSON string decimal; jamás float→str→Money.

Tolerancia diagnóstica de residuo: max(2 ULP, 1e-12). Solo distingue la incidencia
de subcéntimo material; ninguna cercanía acredita el importe. TEXT/NUMERIC finito
exacto queda separado de DOUBLE/REAL. NULL desconocido no es cero. Raw inválido,
NaN/Inf o fuera de Money permanece evidencia/incidencia. SQLite puede convertir
NaN en NULL o perder signo de cero al almacenar: se registra lo leído, no el
valor anterior que el motor ya perdió. TEXT inválido conserva texto y razón,
sin forzar RawMonetaryEvidence exacto. NUMERIC no finito tampoco se convierte.

registro_anterior→migration_derived (11). Líneas/series/perfiles sin marcador→
unknown, potencialmente migrados; no afirmar origen real por parecido. Revisión64
es observada, no historia anterior. Raw no depende de normalización legacy ni
boundary.snapshot. Verificación de huella fiscal existente es solo contraste;
no genera registro, XML, QR, cobro ni remisión.

## Reglas y catálogo

| Fuente | Tratamiento |
|---|---|
| invoice draft | B/out_of_scope; no D ni evento |
| invoice/rectificación legacy | verificar dinero/líneas/profile/fiscal; C ante contradicción, faltantes o dinero sin corroborar; eventual A conserva bloqueo invoice v2; R1–R5 siempre rectification con padre explícito |
| payment | fila real, fecha/método/parent, total acumulado y duplicados; marker sintético D; no status→payment; sin inferencia por amount/date |
| bank import | movimiento observado B solo si dinero/identidad mínima/fechas consistentes; cuenta/batch/fila desconocidos no se completan; v2 especial bloqueado |
| bank match | solo link durable explícito; suggestion o confirmed sin link C/BANK_LINK_AMBIGUOUS; depende de import y payment concretos |
| received invoice | B consistente monetariamente; NULLs conservados, pagada operativa; revisión>1 solo estado y SOURCE_HISTORY_LOST, no correcciones reconstruidas |
| expense | B consistente, IVA explícito o NULL; nunca calcular IVA desconocido; sin restaurar borrados |
| cancellation | evidencia fiscal con huella/parent/razón/fechas; original_total solo contexto; depende de invoice, no devolución/deuda extinguida |
| document/classification/transport/recurring | auxiliares sin candidato; no OCR ni outbox como hecho/autoridad/mandato |
| EE/coberturas existentes | verificar sobre/hash/source/revisión/relaciones y datos; coherent COVERED_EXISTING sin candidato; conflict BLOCKED sin repair |

No nuevo tipo económico, supplier_payment, quote.accepted ni job.completed. La
planificación tiene los once tipos aceptados según evidencia, sin nuevos eventos
operativos. Supplier correction/void y expense void solo se reconocen desde
cobertura durable existente; sin antecedente no se reconstruyen.

Assessment A/B/C/D, disposition, severity, rule_id/version siguen1.9A. Codes: los
14 existentes exactamente. Dependencias resueltas usan HistoricalIdentity o la
revisión durable de cobertura; padre A coherente no bloqueante. B/C/D/missing
bloquean. Cuando falta parent/revisión, UnresolvedDependency conserva solo tipo/
ID explícito y razón: nunca inventa una RevisionIdentity1.

## Candidatos, hashes y revisión

DiagnosticCandidate es HistoricalCandidate en memoria con importable=false
estructural. InventoryEvidence/DiagnosticCandidate tienen canonical propio con
nombre/version distintos de1.9A; excluyen observed_at del contenido SEMÁNTICO.
Manifest registra la observación actual. Hashes de candidato iguales para misma
evidencia/regla, independientes de reloj/run/actor. Fecha desconocida sigue NULL;
naive nunca recibe timezone. Candidate canonical almacenado es únicamente el
plan diagnóstico, no persistencia EE ni nuevo soporte durable de payload.

source_set_hash procesa cada source una vez en orden del catálogo y PK física;
incluye identidad/revisión/raw hash. Cambian hash altas, bajas y modificaciones.
Bank puede tener dos slots; conjunto de sources cuenta una sola fila. plan_hash
ordena UUIDs y cubre scope/version, raw/revision/assessment/disposition, candidate
hash, dependencias, cobertura, incidencias y resultado. Decisiones no lo cambian.
Comparación con otro recorrido detecta SOURCE_DRIFT. No demuestra T0, ni ausencia
de cambios posteriores. Siempre certifiable=false y eligible_for_import=false.

review permite add_evidence/select_supported_interpretation/exclude/keep_blocked,
con ReviewRecord tipado para cualquier item (incluidos auxiliares). Documento
usa content_sha256, record/cancellation record_hash, EE content_hash, perfil
profile_snapshot_hash y link/run RawSource.content_hash. Tenant/hash se verifican
contra fuente actual; refs duplicadas/ajenas, falta de evidencia o antecedente de
otra incidencia se rechazan. Excluir es una opinión registrada, no elimina
evidencia ni bloqueante. Nueva interpretación requiere nuevo manifest/plan.

## Escala y fallos

Keyset sin OFFSET. SELECTs prestados y TX por página; tablas propias indexan
tenant/manifest/source y referencias. Auxiliares consultados con IN por lote;
hashes e incidencias finales también paginados/agrupados. Memoria acotada por
página/contexto, no por negocio. Contexto máximo256 por lookup; lotes se dividen
automáticamente si desbordan. Una source individual demasiado grande produce
C/contexto incompleto, sin inventar hechos. La clasificación de datos enormes
requiere revisión/otro límite versionado; no simular completeness.

Crash en scanning/planning conserva evidencia y retry salta los items completos.
Nunca sobrescribe raw anterior. Concurrencia no certificada: no locks/fence de
sources; evidencia incompatible bloquea. Un único escritor según AGENTS. Metadata
global de schema no es dato cross-tenant. Versión de código es metadato del entorno
confiable registrado; no firma ni certificado de checkout.

No se resuelve retención final1.10; guardar evidencia bloquea downgrade/borrado
destructivo.
La baja de cuenta comprueba estas cuatro tablas mediante el guard de conservación
existente: rechazo controlado con evidencia, comportamiento anterior sin ella.
No añade política/plazo de retención ni purga/exportación final de1.10.
PostgreSQL rollback anterior a29 tiene defecto previo fuera de1.9B;
70→69→70 se comprueba, y compatibilidad anterior se valida por gates existentes.
