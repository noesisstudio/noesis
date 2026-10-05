# Orden humana de Fase1.9F

Autorización de ejecución recibida2026-10-05: exclusivamente restauración
Noesis19FQA, leer README de preparación, verificar hashes/identidad/aislamiento,
cinco flags OFF. No consultar/modificar producción ni avanzar1.9G/1.10.
La siguiente orden define el alcance; la restauración previamente ausente fue
preparada y verificada antes de ejecutar. No autoriza repetir backup productivo.

Las Fases 0–1.8H y 1.9A–1.9E quedan aceptadas.

Ejecuta exclusivamente:

# FASE 1.9F — REHEARSAL SOBRE RESTAURACIÓN REAL AISLADA

NO avances a 1.9G.

Esta fase NO tiene como objetivo desarrollar funcionalidad nueva.

Su objetivo es comprobar que el sistema histórico construido en 1.9A–1.9E se comporta correctamente sobre una **restauración real de datos**, sin tocar producción.

---

# PRINCIPIO ABSOLUTO

NO ejecutar absolutamente nada contra la base productiva.

NO abrir epoch en producción.

NO instalar fence en producción.

NO ejecutar scanner/importer/reconciliation contra producción.

NO modificar Railway productivo.

NO usar credenciales productivas dentro de fixtures, logs o documentación.

Solo está autorizado:

**backup/restauración → entorno aislado → rehearsal.**

Si no existe una restauración real y aislada disponible:

detente en preparación y devuelve:

`1.9F BLOCKED — RESTAURACIÓN REAL AISLADA NO DISPONIBLE`

No sustituyas este criterio por fixtures.

---

# 1. ESTADO DE PARTIDA

Trabaja sobre el `main` real posterior al cierre de 1.9E:

`acff183319f476a5f0b25a820751dca4523fd8fd`

Código funcional validado:

`c6594fcb11c1d1b822abcb9cc5bdc78b491b07e1`

Schema actual:

73.

Cinco flags Financial Core deben permanecer OFF.

Lee:

- AGENTS
- ADR-014 a ADR-018
- FINANCIAL-HISTORY-v1
- INVENTORY
- CUTOFF
- IMPORT
- RECONCILIATION
- cierres 1.9A–1.9E
- runbooks/backups existentes del proyecto.

---

# 2. NO CAMBIOS DE CÓDIGO AL PRINCIPIO

Primera regla operacional:

**NO modificar código para conseguir que los datos reales “pasen”.**

Primero ejecutar y observar.

Si aparece un fallo:

clasifícalo como:

A. datos reales correctamente bloqueados;
B. configuración/rehearsal;
C. bug del Financial Core;
D. supuesto de diseño incorrecto.

Solo C/D justifican proponer cambio de código.

No hacer parche silencioso durante la misma ejecución.

---

# 3. OBTENER RESTAURACIÓN

Usar únicamente un backup/restauración autorizado.

Debe registrarse:

- origen lógico;
- fecha/hora del backup;
- motor/version;
- tamaño;
- schema original;
- identificador/hash del backup si existe;
- momento de restauración;
- entorno destino.

NO incluir en documentación:

- contraseña;
- DATABASE_URL;
- tokens;
- datos personales literales.

---

# 4. AISLAMIENTO

La restauración debe ejecutarse en un entorno distinto de producción.

Preferencia:

PostgreSQL local o infraestructura QA aislada.

Debe tener:

- DB propia;
- usuario propio;
- sin conexión de la aplicación productiva;
- sin scheduler productivo;
- sin workers productivos;
- sin webhooks Meta;
- sin AEAT real;
- sin email/SMS real;
- sin almacenamiento remoto mutable;
- sin jobs automáticos que puedan salir al exterior.

Cuando sea viable:

**egress de red deshabilitado o estrictamente restringido.**

No necesitamos que servicios externos funcionen para 1.9F.

---

# 5. PROHIBICIÓN DE OUTBOUND

Antes de ejecutar la aplicación contra la restauración:

demuestra que no puede hacer llamadas reales a:

- AEAT;
- Meta/WhatsApp;
- correo;
- SMS;
- Stripe/pagos;
- almacenamiento externo mutable;
- otros providers.

Usar:

- configuración offline;
- adapters mock;
- hosts imposibles;
- firewall/egress block;

según arquitectura existente.

No confíes únicamente en “no debería llamarlo”.

---

# 6. PRIVACIDAD

Los datos de la copia siguen siendo datos reales.

NO imprimir/exportar:

- nombres;
- NIF;
- direcciones;
- emails;
- teléfonos;
- conceptos sensibles;
- PDFs;
- facturas completas;
- conversaciones.

Informes deben utilizar:

- business IDs seudonimizados;
- counts;
- hashes;
- categorías;
- importes agregados cuando sean necesarios y seguros;
- códigos de incidencias.

No copiar raw rows al cierre.

---

# 7. SNAPSHOT DE LA RESTAURACIÓN

Antes de migrar:

registrar de forma no sensible:

- schema version;
- número de businesses;
- counts por tabla financiera relevante;
- tamaño DB;
- presencia de migrations;
- tipos monetarios;
- número de Economic Events ya existentes si los hubiera;
- flags persistidos relevantes.

No modificar nada todavía.

---

# 8. VERIFICAR QUE ES UNA COPIA

Debe existir una comprobación explícita para evitar apuntar por error a producción.

Como mínimo varias señales independientes:

- host/database distinto;
- marker QA/rehearsal;
- URL/secret no productivo;
- ausencia de workers productivos;
- guard operacional explícito.

Si existe cualquier duda:

ABORTAR.

No aceptar confirmación solo por nombre de DB.

---

# 9. BACKUP DE LA COPIA RESTAURADA

Antes de migrations/rehearsal:

crear un snapshot/backup del entorno restaurado.

Objetivo:

poder volver al estado inicial sin reutilizar producción.

Registrar hash/identificador.

No almacenar credenciales en repo.

---

# 10. MIGRACIÓN REAL  → 73

Si el backup está en una versión anterior:

ejecutar migrations normales sobre la COPIA.

Registrar:

- versión inicial;
- migrations aplicadas;
- duración;
- warnings;
- tamaño antes/después;
- integrity checks.

No editar migrations históricas para hacerlas pasar.

Cualquier fallo:

BLOCKED.

No “arreglar” datos manualmente sin registrarlo como finding.

---

# 11. CERO MIGRACIÓN DE DATOS FINANCIEROS MANUAL

No ejecutar SQL ad-hoc que:

- cambie invoice;
- cambie payment;
- cambie bank;
- cambie received invoice;
- cambie expense;
- cambie fiscal;
- añada Economic Events;
- elimine filas conflictivas.

Los datos reales deben confrontar el sistema tal como son.

---

# 12. INVENTARIO INICIAL POR BUSINESS

No empezar por toda la base de golpe.

Seleccionar primero businesses reales mediante criterios NO sensibles.

Preferencia:

### Cohorte 1
business pequeño/simple.

### Cohorte 2
business con actividad financiera variada.

### Cohorte 3
business con casos legacy relevantes si existen.

No elegir manualmente mirando nombres/clientes.

Elegir por counts/tipos de datos.

Registrar únicamente IDs seudonimizados.

---

# 13. NO ASUMIR QUE HAY CLIENTES REALES

Si la restauración contiene:

- solo demos;
- datos internos;
- datos vacíos;
- fixtures;

registrarlo.

No fingir que 1.9F valida historial de clientes si no existe.

La fase puede terminar:

`PASS TÉCNICO SOBRE RESTAURACIÓN, COBERTURA REAL LIMITADA`

si ese es el caso.

---

# 14. DIAGNOSTIC 1.9B SOBRE COPIA

Primero ejecutar únicamente dry-run diagnóstico.

Para cada business seleccionado:

- manifest diagnostic;
- A/B/C/D;
- incidencias;
- dispositions;
- event types previstos;
- raw money issues;
- migration-derived evidence;
- dependencies.

Todavía:

NO epoch.
NO fence.
NO importer.

Analizar resultados.

---

# 15. MÉTRICAS DEL INVENTARIO

Por business y agregadas:

- sources totales;
- A;
- B;
- C;
- D;
- covered_existing;
- out_of_scope;
- excluded;
- candidates;
- blocking incidences;
- MONEY_BINARY_UNCORROBORATED;
- SOURCE_HISTORY_LOST;
- PAID_WITHOUT_PAYMENT;
- SYNTHETIC_LEGACY_PAYMENT;
- rectification missing;
- bank ambiguity;
- fiscal mismatch.

No publicar datos identificativos.

---

# 16. REVISIÓN DE FALSE POSITIVES / FALSE NEGATIVES

Muestrear casos por código de incidencia.

La revisión puede consultar los datos dentro del entorno aislado.

Pero el informe solo debe registrar:

- código;
- categoría;
- source type;
- explicación técnica anonimizada.

Determina si las reglas clasifican razonablemente datos reales.

No reclasificar manualmente para mejorar porcentajes.

---

# 17. DINERO LEGACY REAL

Este es un objetivo central.

Medir:

- cuántos importes son exact evidence;
- cuántos legacy binary;
- cuántos corroborados;
- cuántos no corroborados;
- subcéntimos;
- residuos binarios.

Comprobar ejemplos internamente.

No convertirlos silenciosamente.

Determinar si las reglas actuales son:

- demasiado permisivas;
- demasiado conservadoras;
- correctas.

---

# 18. `registro_anterior`

Contar cuántos invoice_payments reales:

`method = registro_anterior`

existen.

Determinar:

- si proceden claramente de migration;
- si tienen evidencia adicional;
- qué clasificación reciben.

No promoverlos automáticamente.

Este punto debe aparecer expresamente en el cierre.

---

# 19. RECEIVED / EXPENSE

Evaluar con datos reales:

- revisiones;
- unknown VAT;
- B observed_state;
- voids;
- documents;
- amounts.

Confirmar que la falta de historia anterior a revision tracking:

NO se convierte en correcciones inventadas.

---

# 20. BANCO

Evaluar:

- movimientos con identidad suficiente;
- imports antiguos;
- links reales;
- suggested invoices;
- matches inequívocos;
- ambiguos.

Comprobar especialmente que:

`suggested_invoice_id`

no termina interpretándose como match.

---

# 21. FACTURACIÓN / FISCAL

Evaluar:

- invoice records;
- hashes;
- frozen profiles;
- lines;
- rectificativas;
- cancellation records;
- outboxes.

NO llamar funciones que creen nueva verdad fiscal.

Solo comprobar evidencia existente.

Cuantificar cuántas invoices legacy quedan bloqueadas y por qué.

---

# 22. FACTURA HISTÓRICA V2

Continúa bloqueada.

1.9F debe aportar evidencia para decidir en el FUTURO si merece diseñar ese contrato.

No implementarlo durante rehearsal.

Informe:

- cuántas invoices necesitarían esta vía;
- qué evidencia poseen;
- qué campos faltan;
- principales blockers.

---

# 23. PRIMER CUT REAL EN COPIA

Solo después de revisar diagnostic.

Elegir un business de rehearsal.

Abrir epoch/fence en la COPIA.

Registrar:

- T0;
- duración de apertura;
- generation;
- source counts;
- tamaño.

Comprobar que writers contra esa COPIA quedan bloqueados.

No producción.

---

# 24. MANIFEST CERTIFICABLE

Ejecutar inventory C real para ese business.

Medir:

- duración;
- queries;
- memoria;
- items;
- source set;
- findings;
- drift.

Debe quedar:

certifiable
pero
eligible_for_import=false.

Si BLOCKED:

eso puede ser comportamiento correcto.

No forzar PASS.

---

# 25. PRIMER IMPORT REAL EN COPIA

Solo importar candidatos que el sistema autorice exactamente.

No seleccionar manualmente candidatos bloqueados.

Ejecutar 1.9D contra la COPIA.

Medir:

- número candidatos;
- recorded;
- existing;
- covered_existing;
- skipped;
- blocked;
- partial/completed;
- duración;
- sequence growth.

Zero legacy effects obligatorio.

---

# 26. RECONCILIATION REAL EN COPIA

Ejecutar 1.9E.

Resultado puede ser:

PASS
o
BLOCKED.

Ambos son resultados válidos técnicamente si representan los datos con honestidad.

Analizar cada finding BLOCKED.

Nunca reparar durante ese run.

---

# 27. RESTORE Y REPETICIÓN

Después del primer rehearsal:

volver a una restauración limpia del mismo backup.

Repetir el mismo proceso.

Objetivo:

mismos datos
+
mismo código
→ mismas classifications/hashes/resultados semánticos.

UUIDs de runs pueden variar donde el contrato lo permite.

Pero:

- HistoricalIdentity;
- candidate hashes;
- source hashes;
- event UUIDs;
- operation UUIDs;
- result semantics

deben reproducirse.

---

# 28. IDEMPOTENCIA SOBRE MISMA COPIA

Además:

sobre una copia ya importada:

reintentar batch/item/reconciliation según contratos.

Cero duplicados.

No perder batch original.

---

# 29. VOLUMEN REAL

Elegir después uno de los businesses con mayor número de fuentes de la copia.

Ejecutar como mínimo:

diagnostic.

Si es seguro:

cut/inventory.

Import/reconciliation solo si el run no presenta blockers que lo hagan improcedente.

Medir:

- tiempos;
- memoria;
- queries;
- tiempo con gate;
- duración fence;
- tamaño manifest;
- cantidad de findings.

Objetivo principal:

detectar riesgos operativos de escala.

---

# 30. TRANSACCIÓN DE RECONCILIACIÓN

El riesgo conocido de E es que la reconciliation mantiene business gate durante la revisión.

Medir en copia real:

- duración total del gate;
- cantidad de items;
- queries;
- peor business probado.

Clasificar:

### aceptable para 1.10
o
### requiere optimización antes de 1.10.

No optimizar durante el rehearsal sin evidencia.

---

# 31. FENCE Y EXPERIENCIA OPERACIONAL

Medir cuánto tiempo queda bloqueado el business desde T0 hasta reconciliation.

Esto será crítico para 1.10.

Registrar:

- apertura T0;
- inventory;
- import;
- reconciliation;
- tiempo total.

Todavía NO diseñar UX final.

Pero identificar si la ventana es razonable.

---

# 32. WRITES CONCURRENTES REALES SIMULADOS

En la COPIA:

durante fence intentar operaciones normales:

- invoice;
- payment;
- bank;
- received/expense;
- direct EE live.

Deben fallar cerrado.

No necesitas simular cliente real.

No utilizar proveedores externos.

---

# 33. RESTAURACIÓN NO DEBE TENER OUTBOUND

Después de todo el rehearsal comprobar logs/mocks:

0 llamadas a:

- AEAT real;
- Meta;
- email/SMS;
- Stripe/payment;
- storage mutable externo.

Cualquier outbound real:

FAIL crítico.

---

# 34. PII EN LOGS

Revisar logs del rehearsal.

No deben contener nuevos dumps masivos de:

- customers;
- NIF;
- addresses;
- concepts;
- full payloads.

Si el software actual ya genera algún log sensible preexistente:

documentarlo como riesgo de 1.10/security.

No copiar el dato literal al informe.

---

# 35. BACKUP/RESTORE PROCEDURE

Documentar runbook reproducible:

1. obtener backup;
2. verificar identidad;
3. crear entorno;
4. bloquear outbound;
5. restaurar;
6. migrar;
7. snapshot inicial;
8. diagnostic;
9. seleccionar rehearsal business;
10. epoch;
11. inventory C;
12. import D;
13. reconciliation E;
14. recoger métricas;
15. destruir entorno/copia según política autorizada.

No automatizar destrucción sin comprobar política.

---

# 36. NO MODIFICAR PRODUCCIÓN

Al final demostrar:

- production database untouched;
- production flags untouched;
- production schema untouched;
- no production epoch;
- no production manifest;
- no production events históricos;
- no production fence.

No basta con declararlo.

Usar logs/config/evidencia operacional disponible sin exponer secretos.

---

# 37. SI SE ENCUENTRA BUG

Si aparece un bug real del código:

1. detener el rehearsal afectado;
2. preservar evidencia anonimizada;
3. NO corregir datos;
4. clasificar severidad;
5. crear propuesta de fix;
6. implementar fix en branch/main según política;
7. ejecutar CI completa;
8. restaurar otra copia limpia;
9. repetir rehearsal desde cero.

No continuar sobre una copia ya afectada por código defectuoso.

---

# 38. NO AÑADIR REGLAS SOLO PARA HACER PASS

Un patrón real desconocido NO justifica automáticamente:

“añadamos una excepción”.

Primero decidir:

¿hay evidencia suficiente?

Si no:

C/D/BLOCKED es correcto.

Prioridad:

honestidad histórica > porcentaje de importación.

---

# 39. RESULTADO DE 1.9F

El resultado global debe ser una de:

### PASS

Rehearsal real reproducible, sin efectos externos, clasificación razonable, cut/import/reconciliation funcionan y no aparece blocker técnico para preparar cierre 1.9G.

### PASS WITH LIMITATIONS

Tecnología correcta pero copia contiene poca historia real / cobertura insuficiente para validar algunos escenarios.

### BLOCKED

Se encontró un problema técnico, operacional, de privacidad, seguridad o evidencia que debe resolverse antes de 1.9G.

No inventar “PASS” por haber ejecutado comandos.

---

# 40. NO ACTIVATION

Incluso con reconciliation PASS:

NO:

- activar flags;
- liberar producción;
- crear cuenta validating;
- permitir live continuity histórica;
- desplegar comportamiento activado.

1.10 sigue sin iniciar.

---

# 41. NO 1.9G

No declarar Fase 1.9 completa.

No hacer closure global.

1.9G requerirá orden separada después de revisar este rehearsal.

---

# AUTOAUDITORÍA

Responder:

1. ¿Se ejecutó algo contra producción?
2. ¿Se usaron credenciales productivas fuera del restore estrictamente necesario?
3. ¿Hubo outbound real?
4. ¿Se expuso PII en informes/logs nuevos?
5. ¿Se modificó source real para conseguir PASS?
6. ¿Se relajo clasificación?
7. ¿Se promocionó registro_anterior?
8. ¿Se inventó bank match?
9. ¿Se inventó fiscal?
10. ¿Se desbloqueó invoice historical v2?
11. ¿Se alteraron flags?
12. ¿Se liberó fence automáticamente?
13. ¿Rehearsal repetido fue determinista?
14. ¿Idempotencia pasó?
15. ¿Se midió volumen/gate/fence?
16. ¿Reconciliation real detectó honestamente BLOCKED cuando tocaba?
17. ¿Se modificó código durante rehearsal?
18. Si hubo bug, ¿se repitió desde copia limpia?
19. ¿Producción quedó intacta?
20. ¿Se inició 1.9G/1.10?

---

# CIERRE

Devuélveme:

- origen y características del backup SIN secretos;
- aislamiento;
- outbound controls;
- schema inicial/final;
- counts anonimizados;
- cohortes;
- diagnostic A/B/C/D;
- incidencias reales agregadas;
- dinero legacy;
- registro_anterior;
- bank;
- purchasing;
- invoices/fiscal;
- invoice historical v2 gap;
- cut real;
- inventory C;
- importer D;
- reconciliation E;
- reproducibilidad;
- idempotencia;
- volumen/performance;
- duración gate;
- duración total fence;
- privacidad/logs;
- cero producción;
- bugs encontrados;
- fixes si fueron necesarios;
- segundo rehearsal limpio si hubo fix;
- resultado PASS/PASS WITH LIMITATIONS/BLOCKED;
- criterios individuales;
- autoauditoría.

No declares PASS si no puedes demostrar que el entorno utilizado era realmente una copia aislada y que ninguna acción pudo afectar producción o proveedores externos.

**No avances a Fase 1.9G ni 1.10.**