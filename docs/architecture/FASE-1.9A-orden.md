# Orden humana — Fase 1.9A

Transcripción del adjunto autorizado; única adición: marca del SHA público para el gate de secretos.

Las Fases 0–1.8H están validadas.

El diseño de Fase 1.9 está aprobado como base.

Ejecuta exclusivamente:

# FASE 1.9A — CONTRATOS Y GOBERNANZA DE HISTÓRICOS

NO avances a 1.9B.

NO implementes todavía:

- inventory scanner;
- manifest persistente;
- dry-run real;
- epoch/fence;
- importer;
- backfill;
- reconciliación;
- activación.

Esta subfase debe definir y probar las reglas formales que utilizarán las siguientes unidades.

Trabaja sobre el `main` real posterior a:

`ab40cdc03f49e8f170843936b66eea7904e6831e` <!-- pragma: allowlist secret; SHA público de main -->

y schema 69.

Los cinco flags Financial Core deben permanecer OFF.

---

# OBJETIVO

Al terminar 1.9A quiero tener contratos tipados y versionados para poder representar sin ambigüedad:

- evidencia histórica;
- clasificación A/B/C/D;
- raw monetary evidence;
- identidad histórica;
- candidatos;
- dependencias;
- incidencias;
- decisiones;
- contratos históricos de Economic Events cuando sea necesario.

Pero todavía:

**NINGÚN DATO LEGACY REAL DEBE IMPORTARSE.**

---

# 1. LEER ANTES DE CAMBIAR

Lee obligatoriamente:

- `AGENTS.md`
- `docs/architecture/README.md`
- `docs/areas/08-financial-core.md`
- `FASE-1-plan.md`
- diseño aprobado de Fase 1.9
- ADR-002, ADR-006 a ADR-013
- `ECONOMIC-EVENTS-v1.md`
- `ECONOMIC-PERSISTENCE-v1.md`
- `FINANCIAL-OPERATIONS-v1.md`
- contratos de Invoice/Payment/Bank/Purchasing/Channels
- migrations 62–69
- contratos actuales de Economic Events
- contratos actuales de Financial Operations

No implementes basándote únicamente en el documento de diseño: contrasta cada propuesta con el código real.

---

# 2. MÓDULO financial_history

Crear exclusivamente la base contractual del módulo:

`src/noesis/financial_history/`

En esta subfase, preferentemente:

- `contracts.py`
- clasificación/reglas puras si procede
- utilidades puras de identidad/canonicalización

NO crear todavía:

- repository;
- readers reales de producción;
- importer;
- reconciliation;
- fence.

No convertirlo en un framework genérico.

---

# 3. CLASIFICACIÓN A/B/C/D

Implementar catálogo cerrado y tipado:

### A — VERIFIED_HISTORY

Hecho histórico sustentado por evidencia durable suficiente para representar el hecho requerido por el contrato.

### B — OBSERVED_STATE

Estado reproducible observado, pero sin evidencia suficiente para afirmar toda su historia o confirmación original.

### C — AMBIGUOUS

Existen datos pero varias interpretaciones razonables, contradicciones o dependencias no acreditadas.

### D — NOT_AUTOMATICALLY_TRANSFORMABLE

Representarlo requeriría inventar información, relación, revisión o hecho.

Añadir también disposiciones separadas de clasificación cuando corresponda:

- `covered_existing`
- `out_of_scope`
- `excluded`
- `pending/incidence`

No mezclar:

classification
con
disposition
con
severity.

El contrato debe impedir esta confusión.

---

# 4. RULE ID Y VERSIONADO

Toda clasificación futura debe poder registrar:

- `rule_id`
- `rule_version`
- categoría
- disposición
- razón estable/código
- evidencia utilizada.

No usar strings libres como única semántica.

Diseña enumeraciones/catálogos pequeños y extensibles mediante versión explícita.

Ninguna regla puede depender de LLM.

---

# 5. IDENTIDAD HISTÓRICA

Diseña una identidad estable para hechos históricos.

Conceptualmente:

business
+
source type
+
source id
+
revision identity
+
event type
+
fact slot.

Debe ser independiente de:

- manifest UUID;
- operador;
- hora del import;
- número de retry.

Implementa una derivación versionada.

No rompas `EntryIdentity.historical()` actual si existe.

Añade una nueva versión o helper específico si el contrato actual no distingue correctamente diferentes hechos sobre la misma fuente/revisión.

Casos que debe soportar conceptualmente:

- invoice issued;
- invoice rectified;
- payment;
- bank imported;
- bank matched;
- supplier invoice observed/confirmed;
- supplier correction si acreditada;
- supplier void;
- expense;
- expense void;
- fiscal cancellation.

Mismo hecho/evidencia:

→ misma identidad.

Misma identidad con evidencia incompatible:

→ conflicto.

No inventar revisiones antiguas.

---

# 6. RAW EVIDENCE

Crear contratos tipados para conservar evidencia monetaria legacy sin presentarla como exacta.

Como mínimo conceptualmente:

- storage engine;
- storage type;
- raw representation;
- exact decimal representation cuando exista;
- binary representation cuando proceda;
- candidate cent value;
- delta;
- provenance;
- corroboration status;
- classification reason.

Distinguir expresamente:

`exact`
`legacy_binary`
`unknown`
`corroborated`
`uncorroborated`

según el diseño que mejor encaje.

## REGLA

Nunca debe existir una propiedad o método que transforme silenciosamente:

float legacy
→ Money exacto

sin evidencia/corroboración.

Un candidate cent value es diagnóstico, no verdad financiera.

---

# 7. UNKNOWN ≠ ZERO

Los contratos deben conservar:

- None/null como desconocido;
- `"0.00"` como cero conocido.

Aplicar a:

- IVA;
- base;
- IRPF;
- amount opcional;
- fechas opcionales.

No añadir defaults financieros automáticos.

---

# 8. FECHAS HISTÓRICAS

Crear semántica explícita para:

- fecha civil legacy;
- `economic_date`;
- `occurred_at`;
- `observed_at`;
- `recorded_at`.

No asignar timezone a timestamps legacy sin zona.

No convertir unknown a fecha actual.

`recorded_at` futuro será momento de incorporación al Core, no fecha del hecho.

---

# 9. EVIDENCE BASIS

Necesitamos diferenciar en payload histórico:

- `verified_fact`
- `observed_state`

Implementa un contrato cerrado.

`observed_state` NO significa:

- contabilizado;
- fiscalmente deducible;
- confirmado originalmente;
- pagado;
- autorizado por el usuario.

Debe quedar documentado.

---

# 10. PAYLOADS HISTÓRICOS V2 ACOTADOS

El diseño aprobado detectó un problema real:

los payloads v1 de:

- `supplier_invoice.confirmed`
- `expense.confirmed`
- `bank_transaction.imported`

exigen fechas de confirmación/importación que pueden no conocerse históricamente.

Diseña e implementa **v2 exclusivamente histórica** para esos tipos si el código real confirma la necesidad.

Los v2 deben:

- mantener los mismos campos económicos relevantes;
- conservar unknown;
- permitir fecha original desconocida donde proceda;
- incluir `evidence_basis`;
- incluir `evidence_hash` o referencia equivalente a evidencia congelada;
- ser válidos únicamente para `origin=historical`.

No modificar bytes/hashes/semántica de payload v1.

No cambiar payload v2 de invoice issue/rectify creado en 1.5.

No convertir esto en “todos los eventos tienen v2”.

---

# 11. VALIDACIÓN origin/version

A nivel contractual:

`origin=live`

NO puede usar las versiones históricas especiales.

`origin=historical`

puede usar únicamente versiones permitidas por catálogo.

Debe fallar:

- historical version usada live;
- live-only payload usado incorrectamente si no satisface el contrato;
- tipo desconocido;
- versión desconocida;
- evidence_basis inválido;
- evidence_hash inválido.

No crear todavía Economic Events durables.

Esto es validación de contratos.

---

# 12. HISTORICAL_UNKNOWN

Audita la implementación existente.

Define contrato explícito para que una operación histórica:

- no tenga actor original inventado;
- tenga `recorded_by` real;
- use permiso `historical.record`;
- no pueda transformarse posteriormente en HUMAN/MANDATE;
- no pueda ejecutarse mediante `FinancialOperations.execute`.

En 1.9A quiero decidir y probar la **semántica**, pero evita introducir todavía la maquinaria completa del importer.

Si se necesita endurecimiento mínimo en contratos/servicio para impedir promoción de una operación histórica, puede implementarse aquí.

NO crear operaciones históricas reales desde datos legacy todavía.

---

# 13. ESTADO DE FINANCIAL OPERATION HISTÓRICA

El diseño propone que una operación historical_unknown no se fuerce a `COMMITTED`, porque `COMMITTED` actualmente significa ejecución con efecto.

Contrasta esto con el código real.

Define formalmente:

- qué estado conserva;
- qué transiciones quedan prohibidas;
- cómo se diferencia de una operación PREPARED normal;
- cómo la reconocerá el importer;
- cómo podrá auditarse sin hacerla ejecutable.

No añadas nuevos estados si no son estrictamente necesarios.

Prefiere invariant estructural/authorization kind/namespace.

---

# 14. ACCESO HISTÓRICO INTERNO

Diseña contrato de acceso para antecedentes históricos creados por otro operador.

No relajes el acceso ordinario de FinancialOperations.

Debe existir conceptualmente:

business permission
+
historical/audit context
+
manifest/item

sin fingir que el operador actual fue el creador original.

En 1.9A puede quedar como interfaz/contrato y pruebas puras.

No crear todavía todo el repository.

---

# 15. CANDIDATE CONTRACT

Crear representación tipada de un futuro candidato histórico.

Debe poder contener:

- historical identity;
- source reference;
- event type;
- proposed payload version;
- proposed payload;
- evidence basis;
- evidence hash;
- amount;
- currency;
- dates/precision;
- dependencies;
- classification;
- reason/rule;
- existing coverage reference si existe.

Debe ser inmutable/canonicalizable.

No persistir todavía.

---

# 16. DEPENDENCIES

Crear contrato cerrado para dependencias históricas.

Ejemplos:

invoice original
→ rectification

invoice
→ payment

bank imported + payment
→ match

invoice
→ fiscal cancellation.

No inferir relaciones por amount/date.

Una dependency debe utilizar identidad concreta.

Padre C/D:

→ candidato hijo no queda importable.

No implementar todavía el grafo completo, pero sí las estructuras y reglas puras.

---

# 17. INCIDENCE CODES

Definir catálogo inicial cerrado según el diseño aprobado.

Como mínimo evaluar:

- MONEY_BINARY_UNCORROBORATED
- MONEY_SUBCENT
- REQUIRED_VALUE_UNKNOWN
- SYNTHETIC_LEGACY_PAYMENT
- PAID_WITHOUT_PAYMENT
- PAYMENT_OVER_TOTAL
- POSSIBLE_DUPLICATE_PAYMENT
- FISCAL_AMOUNT_MISMATCH
- MIGRATED_DOCUMENT_PROFILE
- RECTIFICATION_PARENT_MISSING
- BANK_LINK_AMBIGUOUS
- SOURCE_DRIFT
- SOURCE_HISTORY_LOST
- EXISTING_EVENT_CONFLICT

Puede añadirse otro únicamente si el código real demuestra una necesidad equivalente.

No crear sistema genérico de issues.

---

# 18. PRIVACIDAD CONTRACTUAL

Raw evidence no debe convertirse en copia integral de:

- PDF;
- XML completo;
- imágenes;
- conversaciones;
- notas libres.

Los contratos deben favorecer:

- IDs;
- valores necesarios;
- hashes;
- provenance;
- campos mínimos.

Documenta qué NO debe almacenarse.

No implementar todavía retención final de 1.10.

---

# 19. CANONICALIZACIÓN

Toda estructura que luego participe en:

- hash del evidence;
- identity;
- plan;
- manifest;

debe tener canonicalización determinista.

Probar:

- reorder;
- null;
- decimals;
- dates;
- enums;
- Unicode;
- listas;
- mapas.

No permitir float monetario.

---

# 20. TESTS OBLIGATORIOS

## Classification

- A válido;
- B válido;
- C;
- D;
- classification independiente de disposition/severity;
- unknown rule/version rechazado.

## Historical identity

- determinista;
- business cambia identidad;
- source cambia identidad;
- event type cambia identidad;
- fact slot cambia identidad;
- manifest/operator/retry NO cambian identidad;
- misma identidad + evidencia distinta → conflicto detectable.

## Raw money

- NUMERIC exacto;
- SQLite TEXT exacto;
- legacy REAL;
- legacy DOUBLE;
- residue binario;
- subcéntimo;
- zero;
- null;
- NaN;
- infinity;
- float no aceptado como Money exacto.

## Dates

- date;
- timestamp aware;
- timestamp naive;
- unknown;
- observed_at separado.

## Payload historical v2

Para supplier invoice / expense / bank imported:

- verified_fact;
- observed_state;
- fecha conocida;
- fecha desconocida;
- null monetario;
- evidence hash;
- origin historical requerido;
- origin live rechazado;
- v1 bytes/hash sin cambio.

## Historical authorization

- actor original NULL;
- recorded_by presente;
- historical namespace;
- no HUMAN;
- no MANDATE;
- no execute;
- no promotion posterior.

## Dependencies

- parent válido;
- missing;
- C/D parent;
- cross-business;
- self dependency si no aplica;
- deterministic canonical form.

## Privacy

- rechazo o exclusión explícita de blobs/conversaciones completas en contratos donde aplique.

---

# 21. NO MIGRACIÓN 70 TODAVÍA

Fase 1.9A es contratos/gobernanza.

NO crear todavía:

- financial_history_epochs;
- manifests;
- items;
- incidences;
- decisions;
- reconciliations.

Esas tablas pertenecen a 1.9B/C según diseño final.

Solo crea migración en 1.9A si existe una necesidad estructural IMPRESCINDIBLE para asegurar que historical operation no puede ejecutarse, y justifícala.

Preferencia:

**cero migraciones en 1.9A.**

---

# 22. NO LEER PRODUCCIÓN

No inspeccionar ni copiar datos productivos.

No hacer clasificación real.

No ejecutar queries destructivas.

Fixtures sintéticos únicamente.

El primer contacto serio con datos productivos deberá ser mediante copia/restauración en 1.9F.

---

# 23. REGRESIÓN

Nada de 1.9A puede alterar:

- productores live;
- Capture;
- writers;
- VERI*FACTU;
- cobros;
- banco;
- recibidas/gastos;
- canales;
- recurrencias;
- flags.

Suite previa debe continuar verde.

---

# 24. DOCUMENTACIÓN

Crear contrato/ADR específico de históricos que deje inequívoco:

- A/B/C/D;
- evidence basis;
- identidad;
- raw money;
- unknown;
- historical_unknown;
- payload historical v2;
- prohibición de writers/backfill en 1.9A;
- privacidad;
- límites.

Actualizar la foto vigente del Financial Core sin presentar 1.9 como implementada.

---

# AUTOAUDITORÍA

Antes de cerrar responde:

1. ¿Puede B presentarse como hecho verificado?
2. ¿Puede float legacy convertirse silenciosamente en Money?
3. ¿Unknown se convierte en zero?
4. ¿Unknown date se convierte en today?
5. ¿Puede una identidad depender del operador?
6. ¿Puede depender del manifest?
7. ¿Puede una operación histórica convertirse en live?
8. ¿Puede ejecutarse con FinancialOperations.execute?
9. ¿Puede historical_unknown inventar actor?
10. ¿Puede payload histórico especial utilizarse live?
11. ¿Se modificó v1?
12. ¿Se creó manifest/backfill antes de tiempo?
13. ¿Se conectó algún reader real?
14. ¿Se inició 1.9B?

---

# CIERRE

Devuélveme:

1. archivos;
2. contratos nuevos;
3. clasificación A/B/C/D;
4. identidad histórica;
5. raw evidence;
6. política monetaria;
7. fechas;
8. payload v2 histórico;
9. historical_unknown;
10. invariantes de no ejecución;
11. candidate/dependency contracts;
12. incidence catalog;
13. tests;
14. compatibilidad v1;
15. migraciones — idealmente ninguna;
16. suite/gates;
17. riesgos;
18. PASS/FAIL individual.

No declares 1.9A cerrada si una estructura histórica permite convertir incertidumbre legacy en un hecho financiero presentado como seguro.

**No avances a Fase 1.9B.**