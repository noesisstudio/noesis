# ADR-SCHEMA-LINEAGE-001 — CRM74 y Financial75–80

Fecha: 2026-10-13. Decisión de diseño local; implementación y publicación no autorizadas.

## Contexto y fuentes

La [orden vigente](SCHEMA-LINEAGE-75-80-orden.md) fija main/producción en
`678bd3fdf2f9891b373b0fe8d46ac37b97f0310d`, con la fila durable
`74 / captacion_hoja_y_tipo`. Se usa la observación de la auditoría anterior del
13/10; **no se accede de nuevo a producción**. Su applied_at permanece intacto.

La cadena en `87055215bcbacf6fefa9f6473a87a7d208885f0c` asignó74–79 a A–F.
Se conserva como **HISTORICAL CODE-VERIFIED FOR LEGACY FINANCIAL74–79 LINEAGE**.
La integración `822c99e30cf97520356ecc88f0d8e5d9f4c48768` sigue acreditando su
base de entonces, no una MAIN_INTEGRATION nueva. Backup V2 `f272582663f35a6e1c6ed9e34e8b0e737d235b49`,
padre `08a210a6fa32575fe4a17bf5578fd4a84b3e7f6d`, queda intacto y sin publicar.

El migrador actual consulta MAX(version); no verifica los nombres aplicados.
Un registro CRM74 podría omitir indebidamente la instalación de A74. El
[mapeo](SCHEMA-LINEAGE-75-80-mapping.md) elimina esa ambigüedad sin editar historia.

## Decisión

1. Reservar CRM74. Nueva cadena A75/B76/C77/D78/E79/F80; G no añade migración.
2. Validar **todo el prefijo de pares version/name**, continuidad, metadata y
   objetos de esquema antes de migrar o usar un runtime. Un número no identifica
   una instalación. La observación se revalida dentro de la conexión/TX prestada.
3. Fingerprint v1 sobre JSON canónico de pares ordenados, sin applied_at, SHA de
   código, secretos ni datos de negocio. Complementarlo con perfiles físicos
   por dialecto. El hash identifica; no autoriza ni sustituye verificación.
4. Distinguir propiedad del catálogo de migración y compatibilidad del runtime.
   Runtime normal80 sólo sirve CANONICAL80 verificado. El futuro bridge acepta
   exactamente CRM74 y canonical80 con política de conservación propia.
5. Crear contratos de binding nuevos y evidencia nueva; los payloads económicos,
   perfil/capabilities, Money, historia y hashes anteriores no se renumeran.
6. Serializar upgrade/downgrade con la misma clave advisory PostgreSQL de
   transacción; servicios compatibles conservan lock SHARE del registry durante su TX.
   SQLite mantiene su transacción exterior de escritura. Sin pools/ORM nuevos.
7. CI compara manifiesto append-only con **main actual** y bloquea colisiones,
   cambios de nombres/callbacks históricos o una base obsoleta.

Contrato normativo en [contract](SCHEMA-LINEAGE-75-80-contract.md); impactos en
[hash-impact](SCHEMA-LINEAGE-75-80-hash-impact.md), validación en
[test-matrix](SCHEMA-LINEAGE-75-80-test-matrix.md), secuencia y permisos en
[implementation-order](SCHEMA-LINEAGE-75-80-implementation-order.md).

## Alternativas descartadas

- Mover CRM74: ya aplicada, violaría su historia durable.
- Añadir80 al catálogo antiguo: A74 ya se habría omitido antes de alcanzarla.
- Aceptar >=80: permite esquemas futuros o de otra lineage sin verificar.
- Sustituir números dentro de receipts: cambia hashes y falsifica procedencia.
- Downgrade80→74 como rollback operacional: puede destruir evidencia y efectos.

## Consecuencias y límites

La arquitectura e invariantes A–G siguen vigentes; cambian identidad física y
bindings. Nueva cadena exige **NEW CODE-VERIFIED PASS**, CI completa y nueva
revisión humana. Recovery Bridge sigue BLOCKED, pendiente de implementación
autorizada. Policy E real provisional, PRIVACY_NOT_READY y guard D/G conservados;
cinco flags OFF. Business15 reservado, sin EMPTY/evidence/actividad.

El diseño incluye el port posterior de V2, no lo ejecuta. No se cambian código,
migraciones, tests funcionales, backups, commits históricos ni configuración.
No producción/Railway/QA/providers, push/merge/deploy/G-LIVE/H.
