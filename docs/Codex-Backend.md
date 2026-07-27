# Codex — Órdenes de trabajo backend

> **Documento histórico de ejecución.** Conserva el contexto de 2026-07-03, pero
> sus migraciones, pruebas y pendientes ya no son estado actual. Usar
> [`project-state.json`](project-state.json), [[Tareas-vivas]], [[Mapa-codigo]] y
> [[Conectar-APIs]] antes de actuar.

> Documento para Codex. Léelo junto a [`AGENTS.md`](../AGENTS.md) antes de empezar.
> Estado histórico a 2026-07-03: `main` desplegado en Railway + Postgres. El dominio
> canónico vigente se consulta en `project-state.json`. CI verde, 79 tests,
> última migración aplicada: **10** (`datos_cobro`).
> La siguiente migración libre es la **11**.

## Reglas duras (no romper jamás)

1. **Aislamiento multi-empresa**: toda consulta/escritura filtrada por `business_id`.
   En Postgres las FKs son compuestas `(business_id, id)` — mantén el patrón.
2. **Append-only intocable**: `invoice_records`, `invoice_events` (Veri*Factu) y
   `worker_clockins` + correcciones (fichaje legal) tienen triggers que abortan
   UPDATE/DELETE. Ninguna función nueva debe intentar modificarlos.
3. **Mínimas dependencias**: stdlib primero; nada de librerías pesadas ni CDNs.
4. **Rama `codex/<tarea>` + PR con base `main`** (lección del PR #8: si apilas PRs,
   cambia la base a `main` antes de fusionar). Claude revisa, el founder fusiona.
5. **Tests**: cada tarea añade tests (aislamiento incluido) y deja la suite verde.

---

## Tarea 1 — Cobros parciales (ledger de pagos) · PRIORIDAD ALTA

> Implementada en `codex/cobros-parciales` con la migración 11 y pruebas de
> regresión. Pendiente de revisión y fusión a `main`.

**Por qué**: Forjia ya tiene anticipos/cobros parciales; nosotros solo
pagado/no-pagado. En oficios es habitual cobrar 40 % al empezar y el resto al
terminar. Es el hueco de producto nº 1 identificado.

**Diseño pedido** (migración 11, `cobros_parciales`):

- Tabla nueva `invoice_payments`:
  `id`, `business_id`, `invoice_id` (FK compuesta a invoices), `amount` (>0),
  `method` (texto libre corto: efectivo/transferencia/bizum/tarjeta),
  `paid_at`, `note`, `created_at`. **NO** tocar `invoices.status` a mano desde
  fuera: el estado se deriva.
- Estado derivado de la factura: `pendiente` (0 cobrado), `parcial`
  (0 < cobrado < total), `pagada` (cobrado ≥ total). Mantén compatibilidad con el
  estado actual: `mark_invoice_paid` pasa a registrar un pago por el restante
  (idempotente: si ya está pagada, no duplica).
- Restricción de negocio: la suma de pagos de una factura no puede superar `total`
  (validar en la función, con `BEGIN IMMEDIATE`/`FOR UPDATE` para evitar carreras).
- Funciones en `db.py`: `add_invoice_payment`, `list_invoice_payments`,
  `invoice_paid_amount`, y que `pending_invoices` / tesorería / análisis
  (`financial_analysis`, DSO, mora) pasen a contar el **restante**, no el total.
- API: `POST /api/{business_id}/invoices/{id}/payments` (valida amount>0, aislado),
  `GET .../payments`. El 404 si la factura es de otro negocio, como siempre.
- **OJO Veri*Factu**: los pagos NO tocan `invoice_records` (la factura emitida es
  inmutable). El ledger es contable, no de facturación.
- Portal del cliente (`/p/`): la tarjeta "Cómo pagar esta factura" debe mostrar el
  **restante** si hay pagos parciales. El diseño visual lo remata Claude después;
  tú deja los datos en el contexto de la plantilla.
- RGPD: incluir `invoice_payments` en export y borrado en cascada.
- Tests: suma>total rechazada, derivación de estados, aislamiento entre negocios,
  idempotencia de `mark_invoice_paid`, pending/tesorería con restantes.

## Tarea 2 — Gasto por foto (OCR de tickets) · PRIORIDAD ALTA

> Implementada en `codex/gasto-por-foto` con la migración 12 y pruebas de
> regresión. Pendiente de revisión y fusión a `main`.

**Por qué**: Forjia lo tiene ("foto al ticket → gasto"). Nosotros ya tenemos el
módulo `documents/` (subida acotada y saneada); falta la extracción.

**Diseño pedido**:

- Adaptador nuevo `adapters/extraction.py` con la interfaz
  `extract_expense(image_bytes, mime) -> {concept, amount, vat_rate, date, supplier} | None`.
- Implementación 1 (por defecto si hay `ANTHROPIC_API_KEY`): visión de Claude
  (mensaje único, salida JSON validada; modelo barato tipo Haiku). Coste por ticket
  ~céntimos, sin dependencia nueva.
- Implementación 2 (fallback sin clave): devolver `None` y que la UI prerrellene
  solo con el documento adjunto (flujo manual actual). **No** meter tesseract ni
  modelos locales pesados: la regla de mínimas deps manda.
- Endpoint `POST /api/{business_id}/expenses/from-photo`: sube imagen (reusa los
  límites de subida existentes), extrae, y devuelve un **borrador** de gasto para
  que el usuario confirme (nunca crear el gasto sin confirmación — cifras de IA
  no se dan por buenas solas).
- Vincular el documento subido al gasto creado (ya existe la tabla `documents`).
- Tests: extracción mockeada, límite de tamaño, aislamiento, no-creación sin
  confirmar.

## Tarea 3 — Recordatorios de cobro automáticos (dejar listo, activar con Meta)

> Implementada localmente en `codex/recordatorios-cobro` como migración 13.
> Pendiente de rebase y PR después de fusionar la migración 12 del PR #14.

**Por qué**: es el corazón del lema "del trabajo terminado al dinero cobrado".
Bloqueado para envío real hasta que el founder encienda WhatsApp (Meta), pero el
backend puede quedar terminado y probado ya, usando la cola durable existente.

**Diseño pedido**:

- Config por negocio (Ajustes): recordatorios on/off + cadencia (por defecto a los
  3, 7 y 15 días del vencimiento/envío). Columnas en `businesses` o tabla pequeña.
- Job en `web/scheduler.py`: cada día busca facturas enviadas no pagadas (con el
  restante de la Tarea 1), y encola en `whatsapp_outbox` un mensaje con plantilla
  aprobable por Meta (texto neutro, enlace al portal `/p/`). Idempotencia: un
  recordatorio por factura y escalón (usa `idempotency_key`).
- Registrar cada recordatorio en `product_events` para medir efecto en DSO.
- Si WhatsApp no está configurado, el job no encola (o marca `skipped`), sin error.
- Tests: idempotencia por escalón, respeto del opt-out, aislamiento.

## Tarea 4 — Partir `server.py` en routers · PRIORIDAD MEDIA

`web/server.py` tiene ~2.000 líneas y ~174 rutas decoradas en un solo archivo.
Partirlo en `APIRouter`s por área (`web/routes/portal.py`, `finanzas.py`,
`equipo.py`, `sitio.py`, `admin.py`…), manteniendo `server.py` como ensamblador
(middlewares, lifespan, mounts). **Cero cambios de comportamiento**: mismo path,
mismos guards (`auth_guard` es middleware global, no debería verse afectado, pero
verifica que las rutas públicas `/p/`, `/t/`, webhooks siguen fuera). Hazlo en un
PR aparte sin mezclar con funcionalidad, para que el diff sea revisable.

## Tarea 5 — Revisiones menores / hardening

> Monitorización `verifactu_outbox` completada en `codex/verifactu-outbox-admin`:
> el panel admin muestra vencidas, agotadas, rechazos, actividad reciente y negocios
> afectados sin activar la conexión AEAT.

- **Rate-limit en memoria** (`auth.too_many_attempts`, escaneo de tokens): hoy es
  un dict en proceso. Si Railway escala a >1 worker o reinicia, se pierde. No es
  urgente con 1 worker; deja escrito un plan (tabla `rate_limits` con ventana, o
  límite en el proxy) y súbelo a PR cuando toque escalar.
- **Índices Postgres**: revisa con `EXPLAIN` las consultas calientes
  (facturas/gastos/trabajos por `business_id`+estado/fecha, outbox pendiente) y
  añade los índices que falten en una migración.
- **Monitorización `verifactu_outbox`**: cuando el founder tenga el certificado de
  pruebas AEAT, añadir al panel admin el estado de la cola (pendientes, errores,
  último envío) y una alerta si se atasca. La remisión ya está implementada
  (migración 9); NO activar `verifactu_enabled` sin validar el entorno de pruebas.

---

## Qué NO hace falta (ya está hecho, no lo repitas)

- Postgres + FKs compuestas + migraciones versionadas (`preDeployCommand` con
  `PYTHONPATH=src`), CI en GitHub Actions, backups verificados con restauración
  probada, `/health` + `/ready`, cola durable de WhatsApp, Veri*Factu fases 1 y 2
  (solo falta certificado), fichaje inalterable, portal del cliente, Stripe por
  REST (faltan claves), marco legal, datos de pago IBAN/Bizum (migración 10),
  lifespan (ya no hay `@app.on_event`), eliminación de `DEFAULT_BUSINESS_ID`.

## Después de estas tareas: el plan WhatsApp

Cerrada la cola T1-T5 (T1-T3 ya entregadas), la siguiente prioridad de producto es
[`WhatsApp-Cerebro.md`](WhatsApp-Cerebro.md): router de mèdia entrante,
confirmaciones borrador→SÍ, informes de cierre del día, foto/PDF por WhatsApp e
histórico importado. El diseño ya está decidido allí; no re-pensar, ejecutar.

## Orden recomendado

1 (cobros parciales) → 2 (gasto por foto) → 3 (recordatorios) → 4 (routers) → 5.
Una tarea = un PR. Si una tarea pide diseño visual, deja los datos listos en el
contexto de plantilla y que Claude remate la UI en una pasada posterior.
