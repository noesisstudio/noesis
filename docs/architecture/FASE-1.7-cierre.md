# Informe de cierre — exclusivamente Fase 1.7

Fase 1.7 cerrada: **31 criterios PASS / 0 FAIL**. Pruebas finales y gates locales
correctos. No se autoriza ni inicia la fase siguiente.
Base main fb46eec, esquema 66, árbol limpio y pull ff-only antes de editar.
Implementación sobre C:/Users/mikic/Documents/noesis. No se inicia 1.8.
Los cinco feature flags permanecen apagados.

[Orden humana](FASE-1.7-orden.md), [auditoría previa](FASE-1.7-entrada-audit.md),
[ADR-011](ADR-011-purchasing-capture.md), [contrato final](PURCHASING-CAPTURE-v1.md).

## Arquitectura y resultado

SupplierInvoiceCapture y ExpenseCapture son servicios internos con review,
prepare, authorize y execute. Componen FinancialOperations, autorización durable,
writers prestados, snapshot realmente escrito, cobertura, Economic Event y
resultado en una única transacción existente. No abren otra conexión ni llaman
OCR, IA o proveedores. Las fachadas rechazan captura solicitada sin ese contexto.

Los únicos productores añadidos son supplier_invoice.confirmed/corrected/voided
y expense.confirmed/voided. Payload/canonical version 1 y catálogo cerrado intactos.
La cuota IVA explícita opcional de gasto requiere una columna exacta nueva; no
se infiere del total ni reemplaza los importes REAL/DOUBLE históricos.

| Evento v1 | Contenido del snapshot real | Relación y amount |
|---|---|---|
| supplier_invoice.confirmed | total, confirmed_on; número, emisión, vencimiento, base, IVA e IRPF opcionales | Sin antecedente; total |
| supplier_invoice.corrected | before, after, corrected_on y reason | corrects último confirmed/corrected; after.total |
| supplier_invoice.voided | before, voided_on y reason | voids último confirmed/corrected; before.total contextual |
| expense.confirmed | total, description, confirmed_on; spent_on y vat_amount opcionales | Sin antecedente; total |
| expense.voided | before, voided_on y reason | voids confirmed; before.total contextual |

El v1 de recibida no admite proveedor en payload. Su ID y los restantes campos
económicos relevantes se conservan en proyección cubierta/huella, sin ampliar
el contrato. Amount de corrección es el total sustitutivo, no delta ni posting.
Void no equivale a abono, devolución, pago ni extinción de AP.

Dos tablas específicas conservan cobertura por negocio/origen/revisión, operación,
UUID/tipo, before/after canónicos, huella y antecedente. La revisión mayor identifica
el último estado; nunca MAX(UUID) o fecha. Reserva antes de correct/void,
adjunción una vez, FK diferidas y guard del resultado impiden commit parcial.
Guards comprueban continuidad y bloquean UPDATE económico/DELETE sin productor.

Void añade fecha/motivo y conserva origen, documento, clasificación y evidencia.
Listas de recibidas/gastos, rangos, previsión de caja, costes de proyecto,
profit_and_loss, month_billing y categorías excluyen retirados. Gestoría,
exportaciones operativas, tax_quarter, resumen y chat heredan esos filtros.
Archivo documental, snapshots, EE y conteos internos siguen conservando evidencia.
Vínculos y clasificaciones confirmadas no pueden eliminarse o desasociarse.

Status pagada y nota son cambios operativos de recibida activa: incrementan revisión,
pero no producen pago ni settlement. No hay expense.corrected ni flujo nuevo:
una futura corrección de gasto deberá retirar el anterior y confirmar otro origen.

Decimal/EUR y JSON monetario string; céntimos explícitos sin redondeo silencioso.
Desconocido permanece null. Lectura exacta prestada evita normalización pública
a float. Procedencia legacy_binary_storage declara los límites del dato original.
Nueva cuota de gasto NUMERIC PostgreSQL/TEXT decimal SQLite. Fechas civiles
de proveedor/gasto y confirmación/corrección/void distintas de observed_at UTC;
occurred_at desconocido, sin inventar zona legacy ni accounting_date.

Idempotencia: identidad de entrada, UUID de operación y slot purchasing estable.
Retry devuelve resultado original aun después de correct/void; contenido distinto
bajo misma identidad falla. Operaciones distintas con iguales importes son válidas.
Gate por negocio, locks y expected_revision serializan carreras. Fallo revierte
source, proveedor, documento, revisión, cobertura, evento/relación/contador y resultado;
aprobación anterior permite retry.

Migración 67: dos coberturas y guards, voided_at/void_reason en ambos orígenes,
cuota opcional de gasto y refresco de triggers de revisión. Sin cambiar REAL/DOUBLE.
Downgrade a 66 exige ausencia de cobertura/void/cuota; con evidencia revertir código
conservando 67. Baja destructiva bloqueada. Nunca borrar evidencia para rollback.

## Pruebas y gates

- SQLite: 38 casos nuevos; dirigidas finales **157/157 OK**, 165.803 s.
- PostgreSQL real: 44 casos de captura (38 compartidos + 6 carreras de procesos);
  combinado final **193/193 OK**, 90.473 s. Cobros/banco39, emisión27, writers18,
  eventos27, operaciones32 y fundamentos6 incluidos.
- Suite general final: **1576/1576 OK**, 1274.860 s, después del último cambio de código.
- Seis carreras PG: misma confirmación recibida/gasto, dos correcciones,
  corrección frente a void, dos void de gasto y dos gastos legítimos iguales.
- Ocho puntos de fallo por correction/void: lock, before, mutación, revisión,
  cobertura, EE, relación y resultado durable; rollback completo y retry.
- Omisión de EE/cobertura, ejecutor alternativo y reserva pendiente no pueden commit.
  Bypass SQL/API, borrado, revisión stale, discontinuidad, tenant, documentos,
  dinero inválido/subcéntimos/float/contexto Decimal reducido y lectores comprobados.
- SQLite 0→67→0→67 y 67→66→67 sin evidencia; datos legacy conservados.
  PG histórico 32→67 y ciclo aislado 67→55→54→53→54→55→67.
- 36 rutas PG, copia/restauración, conversación y privacidad PASS.
  Código anterior esquema 53 sobre BD 67: cliente, factura, emisión, cobro y exportación PASS.
  Servidor local health/ready/portada/login HTTP 200.
- Ruff, Bandit high/high de CI, pip-audit, uv lock, secretos incluyendo archivos
  nuevos, Node 3/3, verdad documental, enlaces locales y diff PASS.

Primeros pases detectaron incompatibilidades de fixtures, fecha PG a medianoche,
RETURN OLD del guard DELETE y normalización de tasa 21/21.0; corregidos y cubiertos
por ejecuciones finales citadas. No quedan fallos dirigidos pendientes.
CI remota y despliegue no verificados; no sustituir pruebas locales por esas afirmaciones.

## Criterios individuales de la orden

PASS se refiere al alcance interno autorizado, con flags OFF y límites abajo.

| Nº | Criterio | Resultado y evidencia |
|---|---|---|
| 1 | Servicios canónicos | PASS — dos dominios, workflow 1.2 y writers 1.4, mismo commit |
| 2 | Confirmación recibida explícita | PASS — manual/documental aprobadas; ningún OCR/upload/provisional productor |
| 3 | Payload recibida | PASS — snapshot real v1, opcionales null, sin inferencias |
| 4 | Corrected y continuidad | PASS — before/after, motivo, corrects último estado; drift falla cerrado |
| 5 | Revisiones | PASS — expected_revision/lock y nueva revisión; stale rechazado |
| 6 | Baja recibida | PASS — source conservado, DELETE capturado rechazado |
| 7 | Voided recibida | PASS — before/fecha/motivo y voids confirmed/corrected |
| 8 | Lectores tras void | PASS — filas operativas/costes/export retirados; evidencia conservada |
| 9 | Status pagada | PASS — etiqueta operativa revisionada sin pago |
| 10 | Expense confirmed | PASS — manual/ticket explícitos; IVA conocido o null |
| 11 | Expense voided | PASS — source conservado y relación a confirmed |
| 12 | Corrección gasto acotada | PASS — sin expense.corrected; semántica futura documentada |
| 13 | Cobertura durable | PASS — específica, por revisión, histórica inmutable |
| 14 | Último estado económico | PASS — mayor revisión cubierta y antecedente exacto |
| 15 | Bypass legacy | PASS — UPDATE económico/DELETE capturados rechazados por guards |
| 16 | Documentos | PASS — source/link/clasificación/EE/resultado en TX; sin I/O externo |
| 17 | Dinero | PASS — Decimal/EUR/string, null distinto de cero, binario declarado |
| 18 | Fechas | PASS — civiles separadas de observed_at; sin zona inventada ni accounting_date |
| 19 | Idempotencia | PASS — mismo resultado; conflicto de contenido; identidades distintas permitidas |
| 20 | Atomicidad | PASS — fallos, omisiones y reservas pendientes revierten completamente |
| 21 | Fallback | PASS — flags OFF; captura solicitada falla cerrada; legacy no capturado preservado |
| 22 | Sin supplier payments | PASS — ningún productor/settlement/remesa/AP añadido |
| 23 | Sin Tax Engine | PASS — sin deducibilidad/período/Tax Ledger/posting |
| 24 | Migración acotada | PASS — esquema 67, guards/cobertura/void y cuota explícita mínima |
| 25 | Tests recibidas | PASS — completos/parciales/documentos/IRPF/corrección/void/stale/concurrencia |
| 26 | Tests gastos | PASS — confirm/ticket/IVA/fecha/void/retry/stale/concurrencia |
| 27 | Historia | PASS — cuatro hechos recibida y dos gasto, relaciones exactas e inmutabilidad |
| 28 | Tests bypass | PASS — SQL/API/DELETE rechazados; legacy no capturado preservado |
| 29 | Multiempresa | PASS — source/documento/proveedor/operación/autorización/cobertura/antecedente rechazados |
| 30 | Fallos inyectados | PASS — ocho puntos en correction/void, comparación completa y retry |
| 31 | Autoauditoría | PASS — respuestas siguientes y Master Plan §44 |

## Autoauditoría específica 1.7

| Nº | Pregunta de riesgo | Respuesta |
|---|---|---|
| 1 | ¿Recibida capturada puede cambiar económicamente sin evento? | No por servicios/API/SQL con guards activos; reserva y commit requieren nuevo EE |
| 2 | ¿Puede borrarse físicamente la recibida capturada? | No, guard DELETE |
| 3 | ¿Puede borrarse físicamente el gasto capturado? | No, guard DELETE |
| 4 | ¿Corrected puede perder before real? | No, continuidad con cobertura previa y snapshot actual; drift rechazado |
| 5 | ¿Corrected puede enlazar antecedente incorrecto? | No, última revisión, source/negocio y relación comprobados |
| 6 | ¿Void implica supplier payment? | No, solo retirada del registro |
| 7 | ¿Pagada genera pago falso? | No, no productor ni evidencia de pago |
| 8 | ¿IVA desconocido se convierte en cero? | No, null preservado y comprobado |
| 9 | ¿Gasto inventa expense.corrected? | No, catálogo y API sin ese tipo |
| 10 | ¿Retry duplica source/event? | No, resultado durable e identidad de operación |
| 11 | ¿Ruta documental capturada confirma source y EE en commits distintos? | No, writer prestado y commit exterior único; legacy no solicitado sigue sin captura |
| 12 | ¿Source de otra empresa puede enlazarse? | No, tenant/permiso/FK compuestos |
| 13 | ¿Float histórico se presenta como exactitud recuperada? | No, procedencia binaria explícita; nueva cuota sí exacta |
| 14 | ¿Se adelantó AP/OpenItems/Tax/GL? | No |

## Autoauditoría Master Plan §44 después del código

1. Eventos: los cinco v1 autorizados. Domain/Operational Events no se absorben;
   OCR y pagada no son hechos de pago.
2. Asientos: ninguno; solo evidencia económica.
3. Cuentas: ninguna; no plan contable.
4. TaxLines: ninguna; cuota explícita no decide deducibilidad/período.
5. OpenItems/settlement: ninguno, tampoco por pagada o void.
6. Dimensiones: negocio, origen/revisión, operación, documento y proveedor existentes.
7. Autoridad: Principal autenticado y autorización durable hash/revisión/actor/sesión;
   IA/OCR no autorizan. Política de creador 1.2/1.3 preservada.
8. Reversibilidad: fallo antes del commit revierte todo; después correct/void
   conservan historia. Rollback de código mantiene esquema y evidencia.
9. Idempotencia: EntryIdentity/UUID/slot; recuperación sin repetir efectos.
10. Períodos: no cierre ni accounting_date; no afirmar validación contable de períodos
    porque esta fase no realiza posting.
11. Auditabilidad: before/after, revisión, antecedente, cobertura/EE inmutables,
    aprobación/resultado, huella/procedencia y source retenidos.
12. Tests: SQLite/PG, procesos, regresiones, omisiones, fallos ocho puntos,
    bypass, documentos, dinero y lectores; resultados arriba.

## Archivos, decisiones y diferencias

- Nuevos: purchasing_capture/{__init__,service,schema}.py y cuatro módulos de
  contrato/runner/worker SQLite/PostgreSQL; ADR-011, orden, auditoría, API y cierre.
- Modificados: purchasing/documents writers, db y documents/service, migrations,
  fixtures de operaciones/writers/emisión/cobros, CI PostgreSQL.
- Gobernanza: AGENTS, arquitectura/index/plan, cinco contratos previos y ADR-002,
  guías 01/03/04/06/08, Inicio/Estado/Tareas/Mapa/Decisiones, QA/bitácora/JSON.
- Sin desviación de alcance: cuota explícita opcional de gasto es el mínimo técnico
  para vat_amount conocido. V1 cerrado obliga conservar proveedor en cobertura,
  sin añadir campo. Status/nota operativos permiten huecos de revisión legítimos.
- Fixtures sintéticas 1.2/1.4 usan comando aún sin productor para probar composición
  genérica; no conectan fiscal cancellation ni cambian VERI*FACTU.

## Riesgos y pendientes

Origen monetario sigue REAL/DOUBLE; no afirmar exactitud recuperada. Gate por negocio
puede limitar concurrencia. Política vigente de autoridad/lectura por creador limita
delegación entre usuarios; no ampliar permisos aquí. Un administrador SQL puede
quitar triggers: guards protegen rutas de aplicación, no superusuario hostil.
Prueba de drift simula esa eliminación administrativa y verifica rechazo posterior.

Exportación completa de evidencia, retención y cierre de cuenta esperan 1.10;
exportación operativa actual no es ese archivo de auditoría. Bridges web/tools/chat/
WhatsApp/recurrentes esperan 1.8; históricos/backfill esperan 1.9. Sin cuentas/canales/
flags activados ni consumidores contables/fiscales nuevos. Integraciones reales,
CI remota y despliegue no verificados en este cierre local.
No empezar 1.8 sin nueva orden humana.
