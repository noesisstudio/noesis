# Financial Antecedents v1

[Orden](FASE-1.10B-orden.md) · [ADR020](ADR-020-financial-antecedents.md) ·
[Cierre](FASE-1.10B-cierre.md). Evidencia ≠ autorización ≠ activación ≠ ejecución.

## API prestada

`AntecedentRef(source_type, source_id, revision, event_uuid=None)` es una identidad
fuerte; business_id vive en el resolver, cada query y cada FK. Sin UUID, solo buscar
el único evento de esa fuente/revisión exacta; ambigüedad bloquea. UUID externo o
fuente no accesible producen AccessDenied uniforme, sin consultar otros tenants.

`ResolutionRequest(antecedent, purpose, bank_movement=None, request_version=1)`.
Tipos/versiones/campos/dependencias cerrados. Importes no son claves de búsqueda.

`AntecedentResolver(session, business_id).resolve(principal, request)` solo SELECT.
`persist_resolution(principal, uuid, request)` recomprueba y escribe solo la tabla B.
`read(principal, uuid)` verifica hashes/columnas y creador/sesión autenticados.
`verify_resolution(principal, stored_resolution)` vuelve a resolver en esa misma
FinancialSession; cambio implica Conflict/SOURCE_CHANGED. Función prestada equivalente
`verify_resolution(session, business_id, principal, resolution)`.

Transacción exterior requerida en ambos motores. PostgreSQL: gate por negocio,
FOR SHARE de identidad de usuario/negocio/fuente; mantiene orden existente.
Resolver/reader usan permisos `financial.antecedent.resolve/read` de cuenta
autenticada activa y escribible, nunca financial.authorize/mandate/historical_unknown.
Sin abrir conexión, commit/rollback propio, arreglar evidencia ni llamadas externas.

## Catálogo v1

| Propósito | Antecedente y requisitos |
|---|---|
| customer_payment_against_invoice | Factura live v2, total/EUR/fecha/estado acreditados, todos los pagos con cobertura y hechos exactos |
| rectify_invoice | Factura exacta v2 y vínculos rectifies exactos cuando existan; sin crear rectificativa |
| fiscal_cancel_invoice | Factura y registro fiscal/documental exactos; solo evidencia, productor/capability siguen pendientes C |
| bank_match_invoice | Factura resoluble, cobertura de cobros, movimiento live imported exacto, positivo y dentro del saldo; solo Evidence |
| supplier_invoice_correct | confirmed/corrected verified_fact, estado monetario/documental anterior completo, cadena contigua |
| supplier_invoice_void | Mismos requisitos de estado anterior; sin retirar la fuente |
| expense_void | confirmed verified_fact, total/IVA/fecha acreditados, estado anterior; sin retirar gasto |
| inspect_evidence | Consulta de evidencia íntegra; permite observed_state, conserva unknowns, no aptitud para comandos |

Origen: historical/live exclusivamente. Calidad: verified_fact/observed_state.
Sin prueba suficiente no se concede calidad verificada. Un campo desconocido
continúa unknown, incluso si el importe total del hecho sí es conocido.

Outcome: resolved/blocked. not_found se expresa mediante reason, no tercer estado.
Razones cerradas: ANTECEDENT_NOT_FOUND, ANTECEDENT_UNSUPPORTED,
ANTECEDENT_NOT_VERIFIED, OBSERVED_STATE_INSUFFICIENT, SOURCE_CHANGED,
EVENT_MISSING, EVENT_INVALID, OPERATION_INVALID, AUTHORIZATION_INVALID,
COVERAGE_INCOMPLETE, PAYMENT_HISTORY_INCOMPLETE, MONEY_UNCERTAIN, DATE_UNCERTAIN,
FISCAL_EVIDENCE_INCOMPLETE, DEPENDENCY_INVALID, PURPOSE_NOT_ALLOWED,
HISTORICAL_PROOF_INVALID, LIVE_PROOF_INVALID.

## Resultado y hashes

Sin payload completo ni PII libre. Resultado v1 incluye tenant, request exacto,
outcome/reasons, origen/calidad, evento/op/auth, refs a batch/item/E originales,
source/content/record hashes, amount/currency/remaining canónicos opcionales,
dependencias con relación/UUID/source/revisión exactos y known/unknown por campo:
amount, currency, economic_date, source_state (estado físico, no pago),
state_components, prior_payments, fiscal_evidence, bank_movement, base, vat_amount,
irpf_amount, invoice_number y due_on. Valores personales solo mediante huella.

context_hash liga request, actor/sesión, fuente, operación/auth, cobertura,
dependencias/pruebas y resultado observado. UUID/reloj propios se excluyen para
retry determinista. evidence_hash liga el cuerpo; content_hash liga resultado
completo. Created_at no inventa fecha económica. Revalidation=every_use, sin TTL
que pueda interpretarse como permiso. Fuente cambiada requiere nueva resolución.

## Prueba histórica y live

Histórica verifica contrato ya existente, sin nuevo proof de importación.
HistoricalIdentity/event UUID/slot/revisión, raw/candidato originales, operación
histórica PREPARED, historical_unknown sin actor original, proof/intent/batch/C,
E PASS íntegra y relaciones exactas. Fuente actual debe coincidir con raw original.
Otros hechos posteriores no se copian al histórico ni a cobertura live ficticia.
Factura historical v2 sigue bloqueada. observed_state solo consultable con inspect.

Live verifica el request y resultado COMMITTED, autorización exacta y vigente al
commit, evento canonical/content/record, links y cobertura del dominio. Para
supplier/expense, estado before/after y secuencia de revisiones sin huecos.
Banco imported requiere cobertura original exacta y fuente todavía unchanged;
una revisión operativa posterior no se infiere como nuevo hecho acreditado.

Cobros previos: todas las filas reales de invoice_payments deben tener coverage
exacta al invoice event, evento íntegro y prueba; registro_anterior nunca sirve.
También se contrasta el conjunto de eventos relacionados por settles: un evento
huérfano no puede desaparecer del saldo al perder su fila/coverage. Conjunto vacío
acreditado permite suma cero, sin transformar NULL en cero. El modo fiscal del
negocio forma parte del contexto; su cambio exige una nueva resolución.
Status es una invariante que se contrasta contra los hechos, no una fuente de pago.
No SUM/CAST binario. No Open Items. Match no genera caja ni EE en B.

## SQL y FKs futuras

Tabla única append-only; fuente polimórfica mediante seis columnas FK tipadas,
una sola activa y source_id consistente. Toda FK compuesta por business_id.
Refs durables a EE/op/auth e importación/reconciliación. Guards de origen/calidad/
propósito/proof estructural, known/unknown y autorización/origen contradictorios.
SQL no puede añadir autoridad por insertar metadata ni evitar la revalidación.

La clave `idx_antecedent_protected_scope` permite FK futura de hijo a
business_id/resolution_uuid/outcome/purpose/quality/origin/event_uuid con CHECK
resolved y verified_fact para comandos. Hay que revalidar además dentro de TX y
comprobar la nueva autorización. Ningún FK/writer live vigente se modifica.
En el futuro hijo todos los componentes de esa FK deben ser NOT NULL; el CHECK
debe fijar además el propósito correspondiente al comando. No admitir NULL como
vía para saltar la comprobación referencial compuesta.
SQL privilegiado que deshabilite triggers fuera del threat model documentado.

A solo amplía matriz aditiva de esquema; no outcomes, blockers, providers,
privacidad/export ni consumo del resolver. Cinco flags OFF, sin C–H ni routing.
