# ADR-021 — Registry único y captura de evidencia de anulación fiscal

Fecha: 2026-10-06. Alcance exclusivo: [orden C](FASE-1.10C-orden.md).
A y B CODE-VERIFIED PASS. Candidato local en rama dedicada; no publicación.

## Problema y decisión

A define quince capacidades pero falta el productor fiscal live requerido por la
dependencia de emisión Veri*Factu. Se reutilizan su Enum, Profile y DEPENDENCIES
en un registry/spec v1 cerrado, con mapping de los once CommandType, requisitos
y disponibilidad local explícitos. No se crea un catálogo conceptual paralelo
ni se conecta enforcement al runtime. Grants por negocio/generación esperan D.

Nuevo dominio `fiscal_cancellation_capture` usa Operations/Auth y el writer fiscal
existente. Requiere resolución B durable live/verified/resolved del propósito exacto
y la revalida dentro de la TX prestada, con gate y locks compartidos. Solo autorización
humana. No otro pool, ORM, bus ni lógica financiera grande en db.py.

Request no monetario, importe None. Total contextual del EE verificado en Decimal,
EUR/JSON decimal string. SourceSnapshot real y UUIDv5 cerrado; registro/outbox/
coverage/EE/link/result en commit exterior único. Migración76 aditiva, FKs compound
diferidas, guards de inserción/resultado/inmutabilidad, downgrade protegido.
El evento evidence-only no revierte deuda, cobros o factura económicamente.
No se toca el algoritmo fiscal; outbox permanece pendiente y no se despacha.

## Consecuencias y validación

Se mantiene idempotencia/recovery por operación y se rechaza una segunda operación
o adopción de anulación legacy. Cambios de fuente/cadena/config/outbox hacen stale
la aprobación. La recuperación COMMITTED devuelve el resultado confirmado sin
repetir el efecto. B historical/observed/mandate y rectificativas negativas conservan
sus bloqueos; C no amplía B para conseguir positivos ficticios.

Readiness deja de declarar ausente este productor; privacidad/export/continuidad/
preflight siguen bloqueando. Hashes y evaluaciones A anteriores intactos. Tests
sintéticos SQLite/PostgreSQL, SQL adversarial, concurrencia de conexiones/procesos,
crashes antes/después de commit y snapshots de efectos permitidos/excluidos.
El [contrato](FINANCIAL-CAPABILITIES-FISCAL-CANCELLATION-v1.md) y el
[cierre](FASE-1.10C-cierre.md) registran evidencia y límites. Cinco flags OFF;
sin main, despliegue, producción, QA real, proveedores, handoff ni D–H.
