# 01 · Visión general

## Fundamentos financieros (2-oct-2026)

Monolito modular: [guía 08](08-financial-core.md) y [ADRs](../architecture/README.md).
Los servicios poseen la transacción de `db.get_conn()`; los repositorios por dominio
reciben `FinancialSession` y `business_id`. No añadir grandes bloques financieros a
`db.py`, conexiones independientes ni autoridad financiera a la IA. El núcleo nuevo
usa Decimal/NUMERIC (TEXT canónico en SQLite); legacy mantiene sus contratos.
Solo Fase 0: sin tablas económicas, asientos ni consumidores nuevos.

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
