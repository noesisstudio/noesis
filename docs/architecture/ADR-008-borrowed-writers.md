# ADR-008 — Escritores prestados, snapshots y revisiones reales

## Adenda vigente 1.8H

[ADR-013](ADR-013-financial-hardening.md) corrige los defects auditados sin
ampliar funcionalidades: business gate precede operation/source incluso en
prepare/reprepare y lecturas FOR UPDATE; DELETE permitido devuelve OLD en PG,
con reparación de instalaciones existentes; el bridge resuelve procedencia
recurrente con sesión prestada para todos los canales y una identidad económica.
Consulta COMMITTED exige creador/negocio/sesión actual, no sv histórico;
PREPARED/APPROVED y aprobación/ejecución conservan la autoridad original.
Sin reescritura de evidencia. Flags OFF; no 1.9. Las descripciones inferiores
con orden anterior de locks se conservan como contexto histórico, supersedido
por esta adenda y su [validación](FASE-1.8H-cierre.md).

Estado: aceptado para la unidad 1.4 autorizada el 2026-10-02. No autoriza 1.5.

## Problema

El [mapa previo](FASE-1.4-writers-audit.md) identifica lecturas en conexiones
distintas, commits entre pasos documentales/recurrentes y falta de exclusión
común de cadena fiscal entre series. El futuro ejecutor de Financial Operations
debe poder incorporar efecto, evento y resultado en un único commit.

## Decisión

Extraer el núcleo existente a `financial_writers/` por dominio. La API pública
db/documents conserva firmas y respuestas, obtiene `db.get_conn`, inicia BEGIN
IMMEDIATE y delega. `FinancialSession.borrowed_connection` es la frontera
explícita con columnas legacy; no relaja las comprobaciones de exactitud de la
sesión. Un writer exige transacción activa, recibe la conexión y nunca obtiene
otra, confirma, revierte, hace OCR/IA/disco/red ni observa el producto.
Las observaciones existentes se devuelven como instrucciones locales y las
ejecuta la fachada tras commit. No son Economic Events.

Un vencimiento recurrente usa el mismo núcleo de creación y emisión que F1/F2;
reserva de run, factura, registro/outbox, finalización y avance son atómicos.
El propietario registra un error reintentable después del rollback, sin huérfano
nuevo. No se reparan huérfanos históricos. La confirmación documental comparte
proveedor, origen, vínculo, revisión y clasificación en el mismo commit.

## Dinero y compatibilidad

Las columnas antiguas son REAL en SQLite y DOUBLE PRECISION en PostgreSQL.
`WriterResult.exact_inputs` captura la entrada antes de normalizarla;
`prepared_values` conserva Decimal calculados antes de adaptar parámetros a
esas columnas. `SourceSnapshot.amounts/data` describe las filas realmente
escritas/leídas, con `legacy_binary_storage` explícito. Esta etiqueta también
se mantiene para filas nuevas: el almacenamiento no se ha convertido a exacto.
Nunca afirmar que Decimal(str(float histórico)) recupera precisión perdida.

Los writers exactos rechazan float y admiten solo EUR. La fachada usa
compatibilidad legacy explícita; conserva, entre otros, `round(float,2)` para
bases/cuotas opcionales de recibidas: 2.675 → 2.67. El writer exacto aplica
HALF_UP: 2.675 → 2.68. Es una política de entrada distinta sobre el mismo núcleo
SQL, sin dos motores financieros. La entrada y el efecto permiten auditar esa
diferencia. Cálculos de líneas/totales reutilizan sus funciones existentes con
salida Decimal opcional. Los pagos se suman por fila en Decimal; el resultado
público permanece float. Un contexto local de precisión 50 evita que el contexto
del llamador reduzca precisión; HALF_UP monetario explícito, HALF_EVEN donde el
legacy no anotaba rounding. No cambia la normalización monetaria global.

## Revisión de fuentes

| SourceType | Estrategia |
|---|---|
| invoice | Huella de identidad, campos fiscales/económicos protegidos y líneas. Cambiar borrador cambia revisión; status/paid_at de cobro no cambian la emisión |
| invoice_payment | Huella de la fila real; detecta cualquier edición aunque hoy no haya API de edición |
| invoice_cancellation_record | Huella de la fila append-only real |
| received_invoice, expense, bank_transaction | `_financial_revision` de BD, monotónica, incrementada por trigger también ante SQL alternativo |

La migración 64 añade únicamente tres columnas y sus guards/triggers. Inicial 1
es el primer estado **observado desde esta migración**, no revisión histórica
reconstruida. Inserción exige 1; actualización permite conservar o avanzar uno,
nunca reiniciar/saltar. Cualquier cambio de fila incrementa, incluso metadatos:
invalidación conservadora. El campo interno se omite en Cursor legacy para
preservar respuestas SELECT *. execute_exact lo conserva. Bajar 64 se rechaza
si ya existe evidencia de fuentes mutables; no reutilizar revisiones tras eventos.

Las huellas inmutables se proyectan a entero positivo de 60 bits + 1 para el
contrato v1; el SHA-256 completo se conserva en snapshot.fingerprint. No son un
contador ni constante 1. Hay riesgo criptográfico residual de colisión de la
proyección; cualquier futuro protocolo que exija equivalencia completa debe
comparar también fingerprint. `revision_reader(business_id)` usa la misma
transacción y locks; devuelve None para ausencia/origen de otra empresa.
expected_revision del writer bloquea y valida antes de mutar; creación de cobro,
rectificativa y anulación valida el invoice padre, no un origen aún inexistente.

## Orden de locks comprobado

1. Permisos de 1.2: usuario/business FOR SHARE; operación y autorización/mandato
   correspondientes, antes de llamar al writer.
2. Advisory **transaccional** por negocio (`financial-writer`, SHA estable).
3. Recurrente/run si existe; banco antes de invoice para conciliación. Origen
   principal y padres bajo FOR UPDATE. Una creación documental bloquea el
   documento existente antes de insertar su origen nuevo.
4. Serie/document_sequences para emisión; perfil y otros recursos necesarios.
5. Advisory transaccional de cadena por business_id + NIF, antes de leer cadena.
6. Recursos secundarios/vínculos documentales. Sin I/O externo.
7. Contador y orígenes/targets de EE cuando un futuro servicio incorpore: append
   adquiere la misma exclusión de negocio antes de su contador. Su orden interno
   contador→origen es seguro frente al writer origen→contador porque ambos
   comparten esa exclusión. No llamar append para tomar una operación nueva
   después de mutar: utilizar el propietario `FinancialOperations.execute`.

Es un orden por ramas, basado en código real, no una lista ficticia de tablas.
La exclusión por negocio evita inversiones dentro de las ramas. PostgreSQL
READ COMMITTED es requisito de este protocolo: tras esperar gate las consultas
ven el commit anterior. SQLite requiere BEGIN IMMEDIATE del propietario y
serializa escrituras. Transacciones sobre varios negocios están fuera del
contrato; no adquirir gates arbitrariamente en distinto orden.

El coste es serialización de escritores de un mismo negocio. No añadir tabla de
locks/captura/activación ni cambiar la cadena fiscal, huellas, XML o QR. Solo
lock común y emisión/anulación prestadas. Rollback libera locks y numeración.

## Límites

No productores, flags, guard de emisión obligatorio, backlinks a eventos ni
confirmed_payment_id. El resultado bancario retiene payment_id recién creado;
replay legacy confirmado devuelve None para ese vínculo no almacenado. 1.6 debe
persistirlo atómicamente cuando esté autorizada. Bajas siguen físicas: snapshot
previo marcado deleted; 1.7 debe decidir conservación antes de conectar voids,
pues las FKs de 1.3 requieren origen conservado. No se devuelve revisión real
de una fila eliminada. No periodos, asientos, Tax Ledger, Open Items ni reporting.

## Verificación

Matriz de veinte caminos con commit/rollback exterior y segunda conexión
prohibida; contrato compartido SQLite/PostgreSQL, dinero inválido, revisiones,
FinancialOperations dueño de efecto+resultado, carreras de conexiones/procesos,
multiserie y cadena única. Fixture fiscal capturada de main anterior 6b4c144
compara respuestas, snapshots fiscales, hashes, QR y XML de F1/F2/R1–R5.
Resultados finales y límites en [cierre](FASE-1.4-cierre.md).
