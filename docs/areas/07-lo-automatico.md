# 07 · Lo automático: reloj, colas y copias

## 2026-10-05 — Fase1.9D: importer histórico (validación en curso)

Solo incorporación de candidatos congelados de C vigente. Flags OFF; no1.9E,
reconciliación, activación, continuidad live ni producción.
[Orden](../architecture/FASE-1.9D-orden.md), [ADR017](../architecture/ADR-017-financial-history-import.md),
[contrato](../architecture/FINANCIAL-HISTORY-IMPORT-v1.md), [cierre](../architecture/FASE-1.9D-cierre.md).
Monolito modular; importer/repositorio especializados sobre conexión y TX
compartidas. Decimal/NUMERIC y JSON decimal string; IA sin autoridad.
Intent item-scoped con UUID/request/candidato exactos; fence permanece activo.
Operación histórica PREPARED y historical_unknown, actor/session NULL; resultado
en import_items, ninguna ejecución ni cobertura live65–67. Tres v2 históricos
durables cerrados; factura histórica v2 bloqueada. Nuevos inventarios reconocen
evidencia histórica existente sin promover B a A ni modificar batches anteriores.
Los encabezados inferiores conservan historia y no amplían autorización.


## 2026-10-04 — Fase1.9C: epoch/T0/fence (implementada y validada)

Únicamente corte consistente por negocio, control durable y nuevo sobre de
inventory certificable, siempre eligible_for_import=false. Schema71, flags OFF.
[ADR016](../architecture/ADR-016-financial-history-cutoff.md), [contrato](../architecture/FINANCIAL-HISTORY-CUTOFF-v1.md),
[writers previos](../architecture/FASE-1.9C-writers.md), [cierre](../architecture/FASE-1.9C-cierre.md).
SQL/application guard por tenant y TX prestada; no promoteB ni histórico EE/Operations/
v2/importer/reconciliación/activación.1.9D NO autorizada. Pruebas SQLite/PG sintéticas,
ninguna producción consultada. Invalidated conserva fence, release explícito pierde
boundary; TTL/crash no liberan. Encabezados inferiores conservan historia.


## Financial Core — canales capturados

Con el Core activo, los canales financieros pasan por `financial_channels/` y
Capture: identidad de servidor, propuesta congelada, autorización durable antes
de consumir el pending y ejecución idempotente. La IA no autoriza ni recibe
writers/identidades. Con flags OFF permanece legacy no capturado; opt-in explícito
nunca hace fallback. Fuente capturada conserva guards. Recurrentes preparan
borradores sin emitir; CSV se confirma por fila. Documento/OCR no es autoridad.
[Contrato y límites](../architecture/FINANCIAL-CHANNELS-v1.md),
[ADR-012](../architecture/ADR-012-financial-channels.md). Ningún flag activado.


## Vencimiento recurrente (1.4)

El scheduler sigue invocando `db.process_due_recurring_invoices`. Cada vencimiento
reserva run, crea borrador con el motor normal, emite solo con opt-in y finaliza/
avanza en una transacción exterior. Error reintentable se registra tras rollback;
no se crea un motor fiscal paralelo ni se reparan huérfanos anteriores.
Identidad estable (recurring_id, scheduled_for); sin Financial Core conectado.

> Léela antes de tocar `web/scheduler.py`, cualquier cola (`*_outbox`,
> `whatsapp_ingress`), `web/backups.py` o una tarea que deba ocurrir sin que nadie
> la pida. Figura 7 del [mapa visual](../02-tecnico/Mapa-Bynoesis.html).

## Qué hace

Un reloj (`BackgroundScheduler`, hora de Madrid) arranca con la web y hace dos tipos
de trabajo: **tareas a hora fija** (parte del día, recordatorios, copias…) y
**colas** que vacía cada pocos segundos (WhatsApp, correo, Veri*Factu). Todo lo que
envía algo comprueba antes que la cuenta esté activa y que el titular lo permitió.
Si hay varias copias del servidor, una tabla evita que la misma tarea se haga dos
veces y las colas se reparten con bloqueo de filas.

## Esquema

```text
Hora de Madrid   Tarea (función en web/scheduler.py)
03:30            run_daily_backup            copia verificada de base y archivos
04:30 domingo    run_weekly_restore_drill    vuelve a restaurar la última copia
08:00            send_daily_summaries        parte del día al titular
09:00            send_payment_reminders      recordatorios de cobro (modo «rules»)
09:00 lunes      send_founder_digest         salud agregada para el founder
09:30 días 1–5   send_gestoria_packages      paquete del periodo a la gestoría
10:00            send_collection_proposals   propone seguimientos, no los envía
10:00 1 ene/abr/jul/oct  send_quarterly_tax_notices  aviso de impuestos
17:05–21:05      send_daily_closings         cierre del día, cada hora
18:00 domingo    send_weekly_summaries       resumen semanal
cada hora, :02   process_recurring_invoices  borradores de recurrentes
cada 15 s        process_whatsapp_outbox · process_email_outbox · process_verifactu_outbox
cada 60 s        process_inbound_email       correo entrante (apagado por defecto)
cada 2 s         process_whatsapp_inbox      entrada durable de WhatsApp (apagada)
```

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `web/scheduler.py` | Registro de todas las tareas (`add_job`), envíos proactivos y procesado de colas |
| `db.py` | `claim_scheduled_run` (una ejecución por tarea y periodo), reclamación de filas de cola con `FOR UPDATE SKIP LOCKED` en Postgres, marcas de reintento |
| `web/whatsapp.py` | `process_outbox()`: backoff exponencial, `connection_id` para conservar el número emisor, cancelación inmediata ante un 4xx permanente de Meta |
| `web/backups.py` | `run_backup()`, `verify_latest_backup_set()`, `admin_backup_status()`, subida S3 opcional; CLI `noesis-restore-check` |
| `security_center.py` | Avisa en `/admin` si la última copia falló o tiene más de 48 h |
| `production_check.py` + `.github/workflows/production-smoke.yml` | Comprobación externa de producción cada 6 h (`/health`, `/ready`, esquema, cabeceras, sitemap) |

## Reglas que no se rompen

1. **Una tarea periódica reclama su turno** con `claim_scheduled_run` antes de hacer
   nada. Sin eso, dos réplicas la harían dos veces.
2. **Nada proactivo sin permiso.** Cada envío comprueba suscripción activa y la
   preferencia del negocio (`preguntar`, `bloqueado` o `rules`). Los recordatorios
   respetan la baja del cliente y la cadencia aprobada.
3. **WhatsApp proactivo = plantilla aprobada**, con los valores recortados al límite
   de Meta.
4. **Las colas son durables e idempotentes**: primero se guarda, después se envía; un
   reintento nunca duplica.
5. **Copias:** una copia no vale hasta restaurarla; una copia fallida nunca provoca la
   rotación (no borra las buenas); el volcado se lee en una sola transacción.
6. **El reloj debe apagarse ordenadamente** al parar el proceso, sin dejar filas a
   medias sin reclamar.

## Estado real (28-sep-2026)

- Funcionan: todas las tareas a hora fija, las colas de WhatsApp y correo, copia
  diaria verificada (14 conservadas) y simulacro semanal.
- Apagado: cola de Veri*Factu (sin certificado), correo entrante y entrada durable de
  WhatsApp (`NOESIS_WHATSAPP_INBOX_ENABLED`).
- **Riesgo conocido de las copias:** viven en el mismo volumen de Railway que los
  originales, que en producción mide **500 MB**; no hay copia fuera de Railway ni
  vigilancia de espacio. Detalle y plan en
  [`Almacenamiento-y-copias`](../04-seguridad-y-datos/Almacenamiento-y-copias.md).

## Pruebas que lo cubren

`test_backups`, `test_backup_cost_estimate`, `test_reliability_guards`,
`test_whatsapp_inbox`, `test_whatsapp_multichannel`, `test_email_api`,
`test_inbound_email`, `test_production_check`, `test_readiness`, y en la CI los humos
de PostgreSQL (`tests/postgres_*.py`).

## Al revisar código de esta zona

- [ ] ¿La tarea nueva usa `claim_scheduled_run` o bloqueo de filas?
- [ ] ¿Comprueba suscripción y preferencia del titular antes de enviar?
- [ ] ¿Un fallo en una fila detiene toda la cola? No debe: se marca y se sigue.
- [ ] ¿La hora elegida tiene sentido en hora de Madrid, y no choca con la copia de
      las 03:30?
- [ ] ¿Un cambio en `backups.py` mantiene «verificar antes de rotar»?
- [ ] ¿Se ha añadido la tarea a esta guía y a la figura 7 del mapa?

## Dudas frecuentes

- **¿Por qué no llegó un aviso?** Mira en este orden: suscripción activa, preferencia
  del negocio, plantilla de Meta, estado de la fila en la cola (`/admin` enseña el
  motivo sin el contenido) y si la tarea reclamó su turno ese día.
- **¿Se puede lanzar una copia a mano?** `noesis-restore-check` revalida la última sin
  tocar la base activa; la copia en sí la crea el reloj.

## Más detalle

[`Almacenamiento-y-copias`](../04-seguridad-y-datos/Almacenamiento-y-copias.md) ·
[`Continuidad-RPO-RTO`](../05-legal-y-rgpd/cumplimiento/Continuidad-RPO-RTO.md) ·
[`Despliegue`](../02-tecnico/Despliegue.md)
