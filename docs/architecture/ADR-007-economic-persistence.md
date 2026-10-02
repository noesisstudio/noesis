# ADR-007 · Persistencia inmutable de Economic Events

- Estado: aceptado para la orden expresa de 1.3, 2-oct-2026.
- Base real: main posterior a 1.2, schema 62; siguiente migración disponible: 63.
- Contratos: [eventos](ECONOMIC-EVENTS-v1.md), [operaciones](FINANCIAL-OPERATIONS-v1.md),
  [persistencia](ECONOMIC-PERSISTENCE-v1.md). No autoriza 1.4 ni productores.

## Decisión

Tres tablas con responsabilidad acotada: economic_events, economic_event_links
y economic_event_sequences. El contador serializa incorporaciones por negocio;
no es numeración fiscal, orden contable ni infraestructura de activación.

Una fuente se representa con source_type/id y exactamente una de seis columnas
FK concretas. Cada FK incluye business_id y apunta a la tabla real. CHECKs unen
tipo de evento, tipo de fuente e ID. Se descarta la FK polimórfica sin integridad.
Operación, autorización y ambos extremos de links también usan FKs compuestas.
Ninguna cascada elimina hechos. Índices UNIQUE de las tablas referenciadas
soportan las claves compuestas sin cambiar sus escritores ni sus datos.

UPDATE y DELETE de eventos y links se rechazan mediante triggers en ambos motores.
Las relaciones de un evento forman parte de su contenido canónico v1 y quedan
selladas al incorporarlo. Se preinsertan dentro de la misma transacción, con FK
diferida desde el link al evento nuevo y FK inmediata al target existente. El
guard del evento verifica conjunto completo, catálogo, tipo real y correspondencia
con el JSON. Esto evita eventos incorporados sin links obligatorios en SQLite,
que no dispone de constraint triggers diferidos. No se pueden añadir relaciones
después. Una corrección es otro evento; no hay máquina de estados de eventos.

PostgreSQL usa NUMERIC sin typmod y CHECK de rango/céntimos: un NUMERIC(p,s) podría
redondear antes del CHECK. SQLite usa TEXT decimal canónico; ninguna aritmética
binaria nueva. Amount concuerda con el campo aprobado del payload; desconocido
sigue siendo NULL. El contrato puro y content_hash de 1.1 no cambian. record_hash
adicional cubre operación, autorización, secuencia y procedencia durable.

El repositorio recibe FinancialSession/negocio; no abre conexión ni confirma,
revierte o autoriza. El servicio valida permisos de 1.2, operación/autorización,
fuente real, revisión confiable y relaciones. Usa SAVEPOINT para deshacer toda
incorporación fallida aunque el llamador capture el error. Commit/rollback exterior
pertenecen al llamador. SQLite exige transacción exterior explícita. PostgreSQL
reserva el contador con lock de fila y actualización atómica, nunca MAX+1.

No hay revisión financiera uniforme en fuentes legacy. El servicio exige un
revision_reader de servidor; rechaza desconocida/obsoleta. No inventar revisión 1
ni derivarla de un timestamp mutable. Adaptadores reales, proyección del comando
aprobado al snapshot y orden de locks con escritores legacy esperan 1.4 y los
productores autorizados. Los tests usan lectores y datos exclusivamente sintéticos.

La identidad pública event_id del contrato se guarda como event_uuid; el UUID
estable viene de código confiable y se conserva en retries. El servicio asigna
ID técnico, clave derivada y secuencia. Cambiar UUID/contenido para un slot o
revisión ya incorporados es conflicto, no un nuevo efecto.

## Migración y conservación

Instalación/upgrade crean infraestructura vacía; no backfill, recálculo ni IO
fiscal. Downgrade vacío a 62 permitido. Cualquier evento/link durable bloquea
la bajada antes de DROP. BEGIN IMMEDIATE exterior en downgrade evita que SQLite
retire 63 si después 62 bloquea por operaciones durables. Baja de negocio con
evidencia se rechaza; sin evidencia mantiene comportamiento legacy.
Exportación/retención y cierre con conservación son gates antes de productores.

## Alternativas descartadas y consecuencias

- Log genérico, graph framework y bus de eventos: fuera del alcance económico.
- Un único source_type/id sin FK: permitiría orígenes inexistentes o cruzados.
- Links añadidos después: modificarían el contenido del contrato ya incorporado.
- Hash como identidad de operación: confundiría intención y contenido.
- Lectura que normaliza float o repara hash: pierde exactitud y evidencia.
- Commit propio del repositorio/servicio: separaría hecho y mutación futura.

El contador limita concurrencia dentro de un negocio de forma deliberada; negocios
distintos tienen filas independientes. El hash detecta incoherencia al leer, no
es una firma ni protege contra un administrador que retire triggers y reescriba
contenido y hashes. SQLite requiere JSON1; PostgreSQL 16 es la referencia probada.
