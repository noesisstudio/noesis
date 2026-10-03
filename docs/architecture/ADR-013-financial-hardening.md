# ADR-013 — Endurecimiento 1.8H de fronteras financieras

Estado: autorizado el 3-oct-2026 exclusivamente para B1–B5. No autoriza 1.9.
Complementa ADR-008/010/012; los cierres anteriores conservan su historia.

## Diagnóstico confirmado

Sobre main posterior a 1.8 se detectaron cinco bloqueos: RETURN NEW cancelaba
DELETE permitido en PostgreSQL; prepare y authorize invertían negocio/operación;
la procedencia recurrente dependía del canal; actor_key histórico impedía consultar
COMMITTED con sesión renovada; CI completa fallaba por el SHA público de Fase 0.
La CI 37069839865 falló en secretos y omitió los pasos posteriores del job general,
aunque PostgreSQL pasó. Los workflows de producción no acreditan esa CI completa.

## B1 — Reparación instalada y replay

Migración 69 reemplaza solamente funciones PostgreSQL BEFORE DELETE de cobertura
66 con sus condiciones originales: DELETE permitido devuelve OLD; INSERT/UPDATE
devuelven NEW. El helper de 66 también queda corregido para instalaciones limpias.
No cambia tablas, triggers, coberturas ni importes. SQLite no requiere DDL nuevo.
Bajar 69 conserva la reparación compatible; reinstalar el defecto no es rollback.
Bajar 66 mantiene su protección ante evidencia durable. Las funciones se retiran
por su migración original cuando no hay datos y se baja el esquema completo.

## B2 — Orden común obligatorio

FinancialOperations._transaction valida permisos existentes y toma el advisory
transaccional de negocio ANTES de entregar el repositorio. Aplica a prepare,
reprepare, authorize, execute y lecturas que internamente usan FOR UPDATE.
EconomicEvents.append toma el mismo gate antes del savepoint/operación/contador.
Writers y recurrentes conservan su gate prestado antes de fuentes/run/plantilla.
Orden: permisos → business gate → operación/autorización → fuentes y recursos
de la rama → contador de eventos; cadena fiscal conserva su gate específico.
Sin conexiones, tablas de locks ni aislamiento nuevos. El coste es serializar
también estas consultas financieras de un negocio mientras exista un writer.
Transacciones que abarcan varios negocios siguen fuera del contrato.

Tres pruebas PostgreSQL sincronizan conexiones reales: authorize sostiene gate,
reprepare comprueba contención advisory antes de entrar en repo.prepare; se libera
authorize y ambos terminan. Incluyen misma operación, distintas operaciones del
negocio y rollback deliberado, con un solo efecto y posterior gate disponible.

## B3 — Procedencia recurrente del servidor

FinancialChannels.propose resuelve invoice.issue/rectify desde el run real usando
la sesión prestada, antes de buscar/reservar la operación. Run sin huella falla
cerrado. Si es recurrente, EntryIdentity es schedule/vencimiento, transport_identity
conserva el recibo original y recurring_context se congela desde schedule/run/hash.
La validación se repite en el commit de preparación y al aprobar/ejecutar.
La ruta web deja de resolverlo por separado. Chat/tools y WhatsApp pasan por la
misma frontera. Una propuesta antigua ordinaria para un run real sin contexto no
puede autorizarse; no se transforma ni se reescribe evidencia histórica.

Una ocurrencia puede revisarse por transportes distintos del MISMO creador y
sesión vigente: una operación canónica, recibos review separados y pending de cada
conversación ligado a ese UUID/hash/revisión. El actor histórico permanece intacto.
Esto no concede delegación a otros usuarios. Las demás propuestas mantienen el
vínculo actor/canal original. Revisar no autoriza: sigue siendo necesario un SÍ
exacto, autorización durable y recibo; TTL, pausa, plantilla y drift se conservan.
No mandato, renovación caducada ni reconstrucción de runs antiguos.

## B4 — Consulta y autoridad separadas

response recarga la operación desde repositorio por negocio/created_by después
de validar Principal actual. Solo en lectura de COMMITTED _link permite prescindir
del actor/canal/sv históricos. PREPARED/APPROVED conservan el vínculo fuerte.
confirm/execute no usan esa excepción. Ningún writer/autorización nueva, cambio
de actor ni reescritura de proposal/auth/result. GET funciona también con Core OFF.
Sesión revocada, otro creador o negocio siguen rechazados.

## B5 — Excepción exacta y evidencia de cierre

.secrets.baseline admite solo docs/project-state.json + Hex High Entropy String +
SHA1 del SHA público de Fase 0. No desactiva detectores, excluye archivos ni amplía
regex. La prueba de secretos verifica detector y fingerprint exactos.
La validación final exige suite general posterior al último código/baseline y CI
completa de GitHub, además de SQLite/PostgreSQL/migraciones/gates. Hasta entonces
B5 permanece abierto. Flags OFF; catálogo, dinero y fiscalidad sin ampliaciones.

[Orden humana](FASE-1.8H-orden.md) · [informe y autoauditoría](FASE-1.8H-cierre.md).
