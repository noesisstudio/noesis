# Informe de cierre — exclusivamente Fase 1.6

Estado: **cerrada, 25 PASS / 0 FAIL**. No avanzar a 1.7.
Base main `56717d4`, esquema anterior65, árbol limpio y pull ff-only.
Trabajo en C:/Users/mikic/Documents/noesis, un único escritor.

## Entrega y arquitectura

[Orden del titular](FASE-1.6-orden.md), [auditoría de entradas](FASE-1.6-entrada-audit.md),
[ADR-010](ADR-010-payment-bank-capture.md), [contrato/API](PAYMENT-BANK-CAPTURE-v1.md).
PaymentCapture y BankCapture componen Operations/autorización durable y los
writers prestados existentes. Sin nuevo motor monetario ni lógica grande en db.py.
Autorización valida contexto dentro de TX también para imports sin entidad previa.

PaymentCapture: review parcial/full/remaining → prepare → authorize → execute,
importe congelado, factura/evento original válidos, saldo bajo lock. Parciales
iguales legítimos pueden coexistir si alcanza saldo; full exige fingerprint de
liquidación inalterado y mismo importe restante aprobado. Reutiliza add_invoice_payment.

BankCapture: importación firmada y CSV puro con cuenta/batch/fila; match positivo
exige imported capturado previo y factura capturada. Writer bank crea pago/estado
y vínculo antes del append, dentro de la misma TX; esto conserva el núcleo SQL
existente y cumple las ocho fronteras de fallo de la orden. El productor de pago
es común. Match añade únicamente evidencia: dos eventos, un pago, una sola caja.

| Evento producido | Slot | Relaciones | Payload | Semántica futura |
|---|---|---|---|---|
| customer_payment.received | payment | settles → invoice.issued/rectified correspondiente | v1 intacto | GL / AR / Treasury / Evidence |
| bank_transaction.imported | import | ninguna | v1 intacto | Evidence / Treasury, no GL automático |
| bank_transaction.matched | match | matches → payment de misma operación; evidence_for → imported del mismo movimiento | v1 intacto | Evidence-only, nunca segundo cobro |

## Cobertura, identidad y exactitud

Migración66 añade exclusivamente payment_economic_coverage, bank_import_coverage,
bank_match_coverage y bank_payment_links, índices/FKs/guards. Reservas preceden
writer; IDs nuevos se adjuntan una sola vez. FK diferida a operación committed
y guard de transición exigen cobertura completa, evento(s)/links, importes,
source revision y resultado concordante. No reserva incompleta durable ni commit
de un ejecutor que omita cobertura/evento. Sin framework genérico ni FK circular
entre coberturas/eventos; el esquema de obligación diferida sigue el modelo1.5.

Link bank→payment: PK por negocio/movimiento, unicidad de pago, FKs reales por
negocio y concordancia invoice/importe; inmutable. Se conserva en nuevas
confirmaciones legacy, sin cambios de respuesta ni backfill de confirmados previos.
Un movimiento capturado no puede confirmar por legacy sin reserva del match.

Identidad import: cuenta opaca + UUID batch + fila; batch vinculado a cuenta/hash
del extracto. Contenido distinto con misma identidad → conflicto. Dos filas
iguales conservan dos IDs. Entre extractos de una cuenta, coincidencia señala
ambigüedad: decisión humana «movimiento distinto» con motivo y candidatos
congelados. No descartar automáticamente ni declarar duplicado demostrado.
Retry recupera request/operación originales, incluso otro día o con candidatos
posteriores. CSV por fila, sin afirmar atomicidad de todo el batch.

Decimal/EUR/string exactos, céntimos inválidos/float/no finitos/moneda inválida
rechazados. Evento de pago desde fila y snapshot reales, no respuesta pública:
invoice_id, amount, paid_at/método, source revision/fingerprint. Guards cotejan
contra representación de columnas legacy, no almacenan nuevo dinero binario.
Escritura REAL/DOUBLE sigue localizada en boundary; snapshot declara procedencia
legacy_binary_storage. Cursor exacto preserva Decimal al leer y adapta solo fechas.
EE persiste NUMERIC PostgreSQL/TEXT SQLite/JSON string. Payloadv1 y catálogo intactos.

paid_at local, día real sin inventar zona; entrada con zona falla cerrada porque
TIMESTAMP legacy no la conserva. imported_on y matched_on proceden de filas
reales. value_on null: el writer no conserva fecha valor. Captura CSV no confunde
fecha valor con booked_on; falta de fecha de operación → rechazo explícito.

## Pruebas y gates

- SQLite: **30/30** nuevas de 1.6; regresiones dirigidas **125/125 OK** (134.378 s).
- PostgreSQL16.15: **39/39** nuevas de 1.6; combinado **149/149 OK** (76.823 s),
  incluyendo emisión27, writers18, eventos27, operaciones32 y fundamentos6.
- Suite general: **1538 ejecutadas en 1140.814 s; 1537 PASS y una aserción de
  formato DDL fallida**, corregida cambiando únicamente espacios de ERRCODE.
  El SQLSTATE real ya era23514. Revalidación final **33/33 SQLite/DDL OK**
  (28.607 s) y **39/39 PostgreSQL OK** (19.497 s). No quedan fallos pendientes;
  no afirmar una segunda ejecución general completa sin fallos.
- Ocho fallos match, cinco manuales y fallo import: rollback completo;
  omisión de cada evento/ejecutor sin reserva no puede commit.
- Procesos PG: mismo UUID, parciales válidos/exceso, parcial/full, dos full,
  mismo match/distintos matches e import repetido: sin sobrecobro ni duplicados.
- Migraciones SQLite0→66→0→66; 65→66→65→66 con origen legacy conservado;
  PG histórico32→66, rollback protegido con link y ciclo aislado66→55→54→53→54→55→66.
  36 rutas, copia/restauración, privacidad y conversación correctas; HTTP local200
  en health/ready/portada/login. Código base53 sobre esquema66: emisión/cobro/export OK.
- Ruff, Bandit high/high de CI, pip-audit sin vulnerabilidades conocidas, uv lock,
  secretos incluidos nuevos archivos, Node3/3, verdad documental, enlaces y diff PASS.
- **25 criterios PASS / 0 FAIL**, dos autoauditorías documentadas. Flags OFF;
  ningún avance1.7, canal nuevo ni consumidor financiero. CI remota/despliegue no verificados.

Nuevas pruebas compartidas: importes/método/fecha, parciales/full/restante,
saldo/stale, mismo UUID y request conflictivo, original issued/rectified, import
positivo/negativo, identidad/retry/cuentas/batches y ambigüedad, match y vínculos,
inmutabilidad/multiempresa, omisión de cada evento/ejecutor sin cobertura,
no normalización pública float, semántica Evidence-only, flags y migración.

Procesos PostgreSQL con barrera y conexiones independientes: misma operación,
dos parciales válidos, parciales que excederían saldo, parcial/full, dos full,
dos matches distintos, replay mismo match y retry de importación. Un solo ganador
cuando no pueden coexistir. Sin sobrecobro.

Fallos match tras lock, pago, invoice state, bank state, link, paymentEE, matchEE
y resultado durable: rollback completo. Fallos manuales en pago/status/legacy
event/EE/result y fallo import tras movimiento antes de evento: todo revertido.
Retry autorizado después del fallo produce el efecto una vez.

El gate de rollback PG verifica que vínculo durable impide downgrade y ejecuta
ciclo histórico en schema aislado sin esa evidencia. No purga el humo principal.
Primeros fallos locales de fixtures: reloj/puerto PG, expectativa fija65 y
downgrade saltando migraciones dependientes; corregidos sin debilitar guards.
La primera suite general se interrumpió para endurecer fechas CSV; no acredita
cierre. La ejecución general final registra una aserción de formato, corregida y
revalidada en el gate final; no se repitió toda la suite tras ese ajuste de espacios.

## Criterios de aceptación de la orden

| Criterio | Estado y evidencia |
|---|---|
| 1 Customer Payment Capture | PASS — servicio canónico, writer compartido, un commit |
| 2 Factura capturada y settles | PASS — emitida/rectificada válidas; legacy falla sin backfill |
| 3 Importe real v1 | PASS — snapshot de payment_id real, huella/fecha/método |
| 4 Parcial exacto/capacidad | PASS — 10/100 €, varios iguales, sin sobrecobro |
| 5 Full/remaining congelados | PASS — cambio de pagos stale, nunca ejecutar saldo variable |
| 6 Idempotencia y concurrencia | PASS — operación/request estable, conflicto y procesos PG |
| 7 Import positivo/negativo | PASS — evidencia firmada, cero rechazado, sin GL |
| 8 Identidad mínima/ambigüedad | PASS — cuenta/batch/fila; no deduplicación universal por contenido |
| 9 Match un pago/dos eventos | PASS — una TX, slots payment/match |
| 10 Relaciones match | PASS — payment de misma operación e imported real del mismo origen |
| 11 Vínculo durable | PASS — tabla específica, FKs por negocio, único e inmutable |
| 12 Replay match | PASS — mismo resultado/pago/eventos; otra operación en conflicto |
| 13 Atomicidad | PASS — rollback de estados, pago/link, eventos y resultado |
| 14 Cobertura estructural | PASS — reservas, FKs diferidas y guard COMMITTED; omisiones fallan |
| 15 Import vs match/revisiones | PASS — evento inicial intacto, match posterior y stale |
| 16 Canales | PASS — interno autenticado; bridges pendientes1.8, sin autoridad inventada |
| 17 CSV composable | PASS — parseo exacto puro, requests por fila e identidad estable |
| 18 No supplier payments | PASS — negativo no infiere pago/gasto/AP |
| 19 Migración mínima | PASS —66, cuatro tablas específicas; sin GL/Tax/OpenItems/BankLedger |
| 20 Tests cobros | PASS — SQLite30/PG39 y regresiones125/149; gate DDL33/PG39 revalidado |
| 21 Tests import | PASS — SQLite30/PG39 y regresiones125/149; gate DDL33/PG39 revalidado |
| 22 Tests match | PASS — SQLite30/PG39 y regresiones125/149; gate DDL33/PG39 revalidado |
| 23 Fallos inyectados | PASS — ocho fronteras match + manual/import |
| 24 Doble reconocimiento | PASS — catálogo y test semántico, ningún consumidor implementado |
| 25 Autoauditoría/gobernanza | PASS — respuestas abajo y estado/documentación obligatorios |

## Autoauditoría de la orden

1. Payment capturado sin evento: no; reserva antes de writer y FK diferida/guard
   committed lo impiden incluso con error capturado. Legacy sigue fuera de captura.
2. Payment event sin payment: no; origen tipado y FK inmediata por negocio.
3. Cobro capturado sin EE de factura: no; contexto válido y FK a cobertura original.
4. Retry duplica cobro: no; committed recupera resultado y no llama writer/append.
5. Full cambia importe aprobado: no; fingerprint de liquidación e igualdad amount/saldo.
6. Match doble caja: no; un payment, paymentEE de caja y matchEE Evidence-only.
7. Match sin paymentEE: no; FK a cobertura de misma operación, guard y dos slots.
8. Match sin importedEE: no; origen/coverage previo requerido; sin backfill.
9. Bank→payment de otro negocio: no; FKs compuestas y concordancia de tenant/invoice.
10. Reimport elimina fila legítima idéntica: no; identidad por fila; ambiguo exige resolución.
11. Negativo infiere supplier payment: no; solo imported, match exige positivo.
12. Float presentado exacto: no; origen binario declarado, campos nuevos Decimal/string.
13. Canal inventa autorización: no; ningún canal crea el puente; Principal/recibo reales.
14. Banking2/OpenItems/GL adelantados: no; cuatro tablas mínimas y tres productores.

## Autoauditoría Master Plan §44

1. EE: los tres hechos/slots/relaciones de la tabla, excluyendo eventos operativos.
2. Asientos: ninguno. 3. Cuentas: ninguna. 4. TaxLines: ninguna.
5. OpenItems: ninguno; settles es evidencia futura, no motor AR.
6. Dimensiones: negocio, factura/pago/movimiento, fecha y cuenta/batch/fila reales;
   no motor dimensional.
7. Permisos: sesión/usuario/negocio/creador/suscripción, aprobación hash/revisión
   y contexto; IA sin autoridad. Mandato solo mediante el contrato durable1.2.
8. Reversible: fallo revierte toda TX; después de commit conservar evidencia.
   No se implementa devolución/anulación de pago ni edición de eventos.
9. Idempotente: identidad request/operación, UUID por slot, unicidades de cobertura/origen.
10. Período cerrado: no hay motor de períodos todavía; no afirmar validación de
    un cierre inexistente ni permitir efectos ledger/Tax adelantados.
11. Auditoría: autorización, request/hash, operación/result, snapshot/revisión/huella,
    eventos/relaciones/cobertura y link durable por negocio; no logs de conversaciones.
12. Prueba: contrato compartido, procesos reales, fallos/guards, regresiones/golden,
    suite y gates; límites de CI/despliegue explícitos.

## Decisiones, diferencias y riesgos

- El plan de referencia hablaba de pagos/match; la orden humana1.6 autoriza además
  imported y CSV, con prioridad sobre esa referencia. No ampliación fuera de orden.
- Tabla de link específica en lugar de columna visible; reserva previa con
  adjunción única de IDs generados. Son opciones expresamente permitidas.
- v1 intacto; parcial verifica capacidad y full fingerprint completo. La política
  de fecha local y rechazo de CSV con solo fecha valor evita inventar fechas.
- Banco sin identificador universal: ambigüedad/resolución, no prueba de duplicado.
  Unificación, proveedores bancarios y Banking2 siguen fuera de alcance.
- Orígenes siguen REAL/DOUBLE; no recuperar precisión histórica ni reclamarla.
- La política1.2 mantiene acceso por creador de operación; otro actor del mismo
  negocio no consume automáticamente la evidencia original. No ampliar permisos.
- Canales 1.8, históricos1.9, retención/exportación/cierre/activación1.10 pendientes.
  Ningún proveedor externo/AEAT, flag o permiso de canal activado.
- CI remota y despliegue no verificados por QA local ni por push.

Rollback: conservar66 y evidencias al revertir código compatible; flags OFF,
sin downgrade/purga con coberturas o vínculos durables. No avanzar a 1.7.

## Archivos creados/modificados

- `.github/workflows/ci.yml`
- `AGENTS.md`
- `docs/Arquitectura.md`
- `docs/Decisiones.md`
- `docs/Estado-actual-main.md`
- `docs/Inicio.md`
- `docs/Mapa-codigo.md`
- `docs/Registro-QA.md`
- `docs/Registro-cambios.md`
- `docs/Tareas-vivas.md`
- `docs/architecture/ADR-010-payment-bank-capture.md`
- `docs/architecture/BORROWED-WRITERS-v1.md`
- `docs/architecture/ECONOMIC-EVENTS-v1.md`
- `docs/architecture/ECONOMIC-PERSISTENCE-v1.md`
- `docs/architecture/FASE-1-plan.md`
- `docs/architecture/FASE-1.6-cierre.md`
- `docs/architecture/FASE-1.6-entrada-audit.md`
- `docs/architecture/FASE-1.6-orden.md`
- `docs/architecture/FINANCIAL-OPERATIONS-v1.md`
- `docs/architecture/INVOICE-CAPTURE-v1.md`
- `docs/architecture/PAYMENT-BANK-CAPTURE-v1.md`
- `docs/architecture/README.md`
- `docs/areas/01-vision-general.md`
- `docs/areas/04-facturas.md`
- `docs/areas/06-rgpd-y-seguridad.md`
- `docs/areas/08-financial-core.md`
- `docs/project-state.json`
- `src/noesis/bank_capture/__init__.py`
- `src/noesis/bank_capture/service.py`
- `src/noesis/banking.py`
- `src/noesis/db.py`
- `src/noesis/financial_operations/service.py`
- `src/noesis/financial_writers/bank.py`
- `src/noesis/financial_writers/boundary.py`
- `src/noesis/migrations.py`
- `src/noesis/payment_capture/__init__.py`
- `src/noesis/payment_capture/schema.py`
- `src/noesis/payment_capture/service.py`
- `tests/borrowed_writers_contract.py`
- `tests/invoice_capture_contract.py`
- `tests/payment_bank_capture_contract.py`
- `tests/payment_bank_capture_worker.py`
- `tests/postgres_payment_bank_capture.py`
- `tests/postgres_release_smoke.py`
- `tests/test_payment_bank_capture.py`
