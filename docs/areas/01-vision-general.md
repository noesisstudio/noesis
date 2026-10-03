# 01 · Visión general

## Orden vigente — exclusivamente Fase 1.8H

Fases 0–1.8 implementadas, auditadas con blockers B1–B5. Solo endurecimiento:
DELETE PostgreSQL (migración de reparación), gate de negocio antes de operación/
fuente, recurrencia común en servidor, consulta COMMITTED con sesión renovada y
CI completa verde. Cinco flags OFF. No 1.9, backfill, activación ni nuevos eventos.
Leer [orden](../architecture/FASE-1.8H-orden.md), [ADR-013](../architecture/ADR-013-financial-hardening.md)
y [cierre/evidencia](../architecture/FASE-1.8H-cierre.md).
Los alcances y encabezados inferiores describen entregas históricas aunque digan
«vigente»; no amplían la orden actual. No reescribir los cierres anteriores.


## Financial Core — canales capturados

Con el Core activo, los canales financieros pasan por `financial_channels/` y
Capture: identidad de servidor, propuesta congelada, autorización durable antes
de consumir el pending y ejecución idempotente. La IA no autoriza ni recibe
writers/identidades. Con flags OFF permanece legacy no capturado; opt-in explícito
nunca hace fallback. Fuente capturada conserva guards. Recurrentes preparan
borradores sin emitir; CSV se confirma por fila. Documento/OCR no es autoridad.
[Contrato y límites](../architecture/FINANCIAL-CHANNELS-v1.md),
[ADR-012](../architecture/ADR-012-financial-channels.md). Ningún flag activado.


## Orden vigente — exclusivamente Fase1.7

1.1–1.6 aceptadas. SupplierInvoiceCapture/ExpenseCapture conectan solo
supplier_invoice.confirmed/corrected/voided y expense.confirmed/voided v1.
Writers compartidos, autorización durable, cobertura inmutable por revisión,
continuidad antes/después, logical void y guards SQL. Documento/clasificación/
source/EE/resultado comparten commit. Flags OFF; no1.8, históricos ni activación.
Pagada es etiqueta operativa, no supplier payment/AP settlement. No GL/Tax/
OpenItems/reporting nuevo. Legacy no capturado conserva comportamiento.
[Orden](../architecture/FASE-1.7-orden.md), [ADR-011](../architecture/ADR-011-purchasing-capture.md),
[API](../architecture/PURCHASING-CAPTURE-v1.md), [cierre](../architecture/FASE-1.7-cierre.md).
Las secciones inferiores describen entregas históricas; no son la orden vigente.

## Actualización vigente — 1.6

PaymentCapture y BankCapture son servicios internos; [API](../architecture/PAYMENT-BANK-CAPTURE-v1.md)
y [ADR-010](../architecture/ADR-010-payment-bank-capture.md). Reutilizan writers,
conexión y TX compartidas, sin nueva lógica grande en db.py ni autoridad IA.
Cobro = caja; imported = evidencia/Treasury; match = Evidence-only. Captura exige
factura/importación original y cobertura completa. Sin backfill ni canales 1.8.
Flags OFF; las llamadas legacy conservan respuesta y comportamiento financiero.
La confirmación nueva conserva vínculo durable, y un movimiento capturado falla
cerrado si se intenta confirmar por legacy sin sus eventos.
Las nuevas coberturas y bank_payment_links figuran en baja: vacías permiten legacy;
con evidencia bloquean borrado. Retención/exportación/cierre siguen como gates 1.10.
Las secciones inferiores reflejan entregas anteriores.

## Orden vigente — exclusivamente 1.5

Fases 1.1–1.4 aceptadas; solo emisión capturada F1/F2 y rectificativas R1–R5.
Servicio `invoice_capture/`: operaciones/aprobación durable + writer1.4 + evento
v2 + resultado en un commit. Migración65: cobertura inmutable con FKs diferidas;
v1/legacy/fiscalidad conservados. Flags apagados; otros productores y1.6 no autorizados.
[ADR-009](../architecture/ADR-009-invoice-capture.md), [API](../architecture/INVOICE-CAPTURE-v1.md),
[entradas auditadas](../architecture/FASE-1.5-entrada-audit.md). Los alcances inferiores son históricos.

## Frontera 1.4 vigente

La orden posterior autoriza solo 1.4; 1.5 espera autorización. `db.py` conserva
infraestructura y fachada; `financial_writers/` recibe Connection/FinancialSession
prestada. El propietario inicia/termina transacción. No segunda conexión dentro
de writer ni nuevo motor. [ADR-008](../architecture/ADR-008-borrowed-writers.md)
fija gate por negocio, cadena fiscal, revisiones y procedencia monetaria legacy.
Migración 64 solo añade revisiones mutables. No productores ni flags activados.

## Fundamentos financieros (2-oct-2026)

Monolito modular: [guía 08](08-financial-core.md) y [ADRs](../architecture/README.md).
Los servicios poseen la transacción de `db.get_conn()`; los repositorios por dominio
reciben `FinancialSession` y `business_id`. No añadir grandes bloques financieros a
`db.py`, conexiones independientes ni autoridad financiera a la IA. El núcleo nuevo
usa Decimal/NUMERIC (TEXT canónico en SQLite); legacy mantiene sus contratos.
Fase 0, 1.1 y 1.2 aceptadas; solo 1.3 autorizada. El contrato de Economic Events
sigue puro; su repositorio/servicio durable separado usa FinancialSession prestada.
Migración 63 añade events, links y contador por negocio; FKs tipadas, append-only,
idempotencia y rollback protegido. Sin productores/asientos ni flags activados.
[Persistencia v1](../architecture/ECONOMIC-PERSISTENCE-v1.md); no avanzar a 1.4.

> Léela antes de un cambio que cruce varias zonas o cuando no sepas dónde vive algo.
> Figura 1 del [mapa visual](../02-tecnico/Mapa-Bynoesis.html).

## Qué hace

Bynoesis es una sola aplicación FastAPI con una sola base de datos. Seis tipos de
persona entran por siete puertas; toda petición pasa por el mismo control, el
cerebro o las pantallas deciden qué hacer, los servicios lo hacen contra la base de
datos, y lo que debe salir hacia fuera (WhatsApp, correo, Hacienda) espera en una
cola que un reloj interno vacía cada 15 segundos.

## Esquema

```text
Autónomo ─┬─ WhatsApp central (Meta) ──┐
Trabajador┘                            │
Cliente final ─ WhatsApp del negocio ──┤
Autónomo ─── Panel web /b/{id}/… ──────┤
Cliente/Trabajador/Gestoría ─ /p /t /g ┤──► Control de entrada ──┬─► Cerebro (mensajes)
Gestoría ─── Portal /gestoria ─────────┤    firma · sesión ·     │      └─► Herramientas
Visitante ── Web pública ──────────────┤    business_id · plan   └─► Servicios (pantallas)
Founder ──── /admin ───────────────────┘                                  │
                                                                          ▼
                                        Base de datos (Postgres) + Archivos (/data)
                                          │  colas guardadas en la propia base
                                          ▼
                               Reloj (scheduler) ─► Meta · Brevo/Gmail · AEAT
```

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `src/noesis/web/server.py` | Ensambla FastAPI: middleware de seguridad (CSP, `X-Robots-Tag`, hosts), routers, arranque del scheduler |
| `src/noesis/web/deps.py` | Guardias de sesión y de `business_id` para `/b/` y `/api/` |
| `src/noesis/web/auth.py` | Contraseñas PBKDF2, sesiones firmadas, límites de intentos |
| `src/noesis/web/routers/` | Una ruta por dominio (ver [02](02-ramas-de-la-empresa.md)) |
| `src/noesis/db.py` | Infraestructura compartida y acceso legacy; los repositorios nuevos reciben su conexión/transacción |
| `src/noesis/migrations.py` | Esquema versionado con subida y bajada; Railway lo aplica antes de desplegar |
| `src/noesis/config.py` | Todas las variables de entorno, con valores por defecto seguros |
| `src/noesis/adapters/` | Un archivo por proveedor externo (IA, correo, Gmail, pagos, voz, extracción, facturación) |
| `src/noesis/web/scheduler.py` | Tareas programadas y colas (ver [07](07-lo-automatico.md)) |
| `railway.json`, `railpack.json` | Despliegue: migración previa, arranque, `/ready` como healthcheck, Tesseract |

## Reglas que no se rompen

1. **Toda lectura o escritura filtra por `business_id`**, en la ruta y otra vez en
   el repositorio especializado o las funciones legacy de `db.py`. Las relaciones entre tablas usan claves compuestas `(business_id, id)`
   para que no se pueda enlazar nada de otra empresa.
2. **Las rutas no escriben SQL.** Validan y llaman a `db.py` o a un servicio.
3. **Los proveedores se llaman solo desde `adapters/`.** Nunca desde una plantilla,
   un router o `db.py`. Cambiar de proveedor debe ser cambiar un archivo.
4. **Nada sale hacia fuera en la misma petición.** Se guarda en una cola y lo envía
   el reloj, con reintento e idempotencia.
5. **Bynoesis prepara; el titular confirma** dinero, fiscalidad, envíos y borrados.
6. **Una cuenta sin suscripción activa queda en modo consulta**, forzado en servidor
   (web, API, WhatsApp, reloj y colas), no solo ocultando botones.
7. **Toda migración tiene bajada**, o una bajada que se niega con un motivo claro si
   perdería datos.

## Estado real (28-sep-2026)

- Producción en Railway, proyecto `autonoms`, región Ámsterdam: servicio `web`
  (bynoesis.com) con un volumen de 500 MB en `/data` y servicio `Postgres`.
- Funcionan: panel, portales, web pública, `/admin`, cerebro local, facturas sin
  Veri*Factu, documentos con OCR local y copias diarias.
- Construido pero apagado o sin validar en real: número de WhatsApp de cada negocio,
  Veri*Factu, Stripe, copia externa y recepción de correo.

## Pruebas que lo cubren

`tests/test_backend.py` (aislamiento, facturación, webhooks, NLU),
`tests/test_platform.py`, `tests/test_security_hardening.py`,
`tests/postgres_smoke.py` (lo ejecuta la CI contra PostgreSQL).
La suite completa se ejecuta con
`python -m unittest discover -s tests -p "test_*.py"`: varias pruebas modifican
`config`, y por archivos sueltos pueden fallar sin estar rotas.

## Al revisar código que cruza zonas

- [ ] ¿Toda consulta nueva lleva `business_id`, y la ruta lo comprueba con `deps`?
- [ ] ¿Algún proveedor se llama fuera de `adapters/`?
- [ ] ¿Algo se envía hacia fuera sin pasar por una cola?
- [ ] ¿Una acción irreversible se ejecuta sin confirmación del titular?
- [ ] ¿La mutación respeta el modo consulta?
- [ ] ¿Cambia el esquema? Entonces migración con bajada, `schema_version` en
      `project-state.json` y prueba de subida y bajada.
- [ ] ¿Se han actualizado `Registro-cambios`, `Registro-QA` y `project-state.json`?
      La CI lo exige si se toca `src/noesis/`.

## Dudas frecuentes

- **¿SQLite o Postgres?** Postgres en producción (`DATABASE_URL`); SQLite solo en
  local y pruebas. `db.py` traduce entre los dos: prueba siempre lo nuevo en ambos.
- **¿Por qué no hay SDK de proveedores?** Stdlib primero (`AGENTS.md`, regla 2): los
  adaptadores usan `urllib` y contratos pequeños.

## Más detalle

[`Arquitectura`](../Arquitectura.md) · [`Mapa-codigo`](../Mapa-codigo.md) ·
[`Guia-tecnica-ingeniero`](../02-tecnico/Guia-tecnica-ingeniero.md) ·
[`Despliegue`](../02-tecnico/Despliegue.md)
