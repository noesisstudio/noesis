# Traspaso: Postgres real en el CI (cazar bugs solo-Postgres)

- **De → para:** Fable 5 (Opus 4.8) → Codex (implementación)
- **Fecha:** 2026-07-08
- **Rama:** `codex/postgres-en-ci` (crear desde `main`)
- **Nivel de confianza del que entrega:** alto en el objetivo y el enfoque; es una
  tarea acotada de CI + un test de humo, sin tocar producto.
- **¿Requiere revisión antes de implementar?** No bloqueante. Al final, revisar que
  el job nuevo **falla** si se reintroduce el bug de hoy (ver §9), y que el resto del
  CI sigue verde.

### 1. Contexto del producto
Bynoesis corre en producción sobre **Postgres** (Railway) y en local/tests sobre
**SQLite**. Hoy nos ha mordido —por segunda vez— un bug que **solo peta en
Postgres** y es invisible para el CI actual (todo SQLite): un `COALESCE(issued_on
TEXT, created_at timestamp)` que Postgres rechaza por mezclar tipos. Tumbó el Home en
producción. Antes, el orden de una FK compuesta en la migración 18. Necesitamos que
el CI ejecute también contra Postgres para cazar esto en el PR, no en la pantalla del
founder. Ver [[Metodo-operativo-Fable]] §3 y §5.

### 2. Objetivo de la tarea
Que **cada PR y push a `main`** ejecute, además del CI actual en SQLite, un job que:
(a) levante un Postgres real, (b) aplique todas las migraciones sobre él, y (c) corra
un **test de humo** que ejercite las rutas de lectura calientes (el Home y las APIs
que usa) contra Postgres. Criterio de éxito: si se reintroduce un `COALESCE` que
mezcle tipos (o similar), el CI se pone **rojo**.

### 3. Estado actual
- `.github/workflows/ci.yml` tiene un único job `tests-and-migrations` en
  `ubuntu-latest` que: instala el proyecto (`pip install -e .`), corre
  `python -m unittest discover -s tests` y valida el ciclo upgrade/downgrade de
  migraciones — **todo en SQLite** (`NOESIS_DB_PATH`, sin `DATABASE_URL`).
- El motor se elige por `config.DATABASE_URL` (si está, Postgres vía `psycopg`; si
  no, SQLite). `psycopg[binary]` ya es dependencia.
- **Restricción importante:** la suite `unittest` **fuerza SQLite** en su `setUp`
  (p. ej. `tests/test_platform.py` hace `config.DATABASE_URL = ""` y usa un
  `NOESIS_DB_PATH` temporal por test, con aislamiento por `TemporaryDirectory`). Por
  eso **no** se puede "correr la suite tal cual contra Postgres" sin refactorizarla.
  → Esta tarea añade un **test de humo aparte**, no reescribe la suite.

### 4. Decisiones tomadas (con porqué)
- **Test de humo contra Postgres, no la suite entera** (de momento). Es el 80% del
  valor con el 20% del esfuerzo: la mayoría de bugs solo-Postgres son de **tipos/SQL**
  y se cazan simplemente **ejecutando las consultas** contra Postgres, aunque haya
  pocas o ninguna fila (Postgres valida tipos en el plan, no dependen del dato).
  Reescribir la suite para ser agnóstica de motor (con aislamiento por test en
  Postgres) es una tarea mayor y aparte. Registrar en [[Decisiones]]: sí.
- **Seed con `demo.seed_rich(force=True)`** para poblar todas las tablas: ya existe y
  cubre facturas, recibidas, CRM, gestoría, documentos, etc. `force=True` es
  necesario porque `seed_rich` se niega a correr con `DATABASE_URL` puesto (hace
  reset) salvo que se le fuerce — aquí es una BD de CI desechable, así que es seguro.

### 5. Decisiones pendientes
- Ninguna bloqueante. (Futuro, no ahora: hacer la suite `unittest` agnóstica de motor
  para correrla entera en Postgres. Anotar en [[Roadmap]] como mejora posterior.)

### 6. Mapa de la tarea
- **Archivo a editar:** `.github/workflows/ci.yml` — añadir un job nuevo
  `postgres-smoke` (paralelo al actual). No tocar el job SQLite existente.
- **Archivo nuevo:** `tests/postgres_smoke.py` — script (no parte del `discover`
  normal; se invoca explícitamente en el job de Postgres) que, con `DATABASE_URL`
  apuntando al Postgres del CI:
  1. `from noesis import db, demo` → `db.init_db()`; si no hay negocios,
     `demo.seed_rich(reset=False, force=True)`.
  2. Levanta la app con `TestClient` (o llama a `db`/servicios directamente) y hace
     **GET a las rutas de lectura calientes**, afirmando que **ninguna devuelve 5xx**:
     - `GET /b/{id}/resumen` (el Home — el que petó), y unas pocas páginas más
       (`/costes`, `/analisis`, `/documentos`, `/crm`, `/agenda`).
     - APIs que alimentan el Home y las pantallas:
       `/api/{id}/summary`, `/plan`, `/pending`, `/analysis`, `/received-invoices`,
       `/leads`, `/products`, `/suppliers`, `/gestoria/requests`, `/pnl`, `/agenda`,
       `/income/by-client`, `/costs/breakdown`, `/taxes`, `/invoices`.
     - Login: crear cuenta con `db.create_account` + `auth.hash_password`, o reutilizar
       la del seed, y autenticar el `TestClient` vía `POST /login`.
  3. Salir con código ≠ 0 si alguna dio 5xx (para que el job falle).
- **Servicio Postgres en el job** (GitHub Actions `services:`), con healthcheck.
- **Entidades/tablas:** ninguna nueva. **No hay migración.**

### 7. Riesgos y qué NO hacer
- **No tocar** el job SQLite actual ni la suite `unittest` (su `setUp` fuerza SQLite a
  propósito; no intentar "colar" Postgres ahí).
- **No** meter credenciales reales: el Postgres del CI es efímero, con usuario/clave
  de juguete y BD desechable.
- **No** dejar el job como *required* hasta verlo verde un par de veces (evita
  bloquear merges por un flake de arranque del contenedor); una vez estable, se puede
  marcar como obligatorio.
- Cuidado con el **orden de arranque**: usar el healthcheck del servicio para no
  correr las migraciones antes de que Postgres acepte conexiones.

### 8. Criterios de aceptación
- [ ] `ci.yml` tiene un job `postgres-smoke` con un servicio Postgres, que aplica
      migraciones y corre `tests/postgres_smoke.py` contra Postgres.
- [ ] El job pasa en verde con el código actual (ya arreglado).
- [ ] **Prueba del guardián:** al reintroducir temporalmente el bug (volver a
      `COALESCE(r.issued_on, r.created_at)` sin `CAST` en `db.list_received_invoices`),
      el job `postgres-smoke` se pone **rojo** con el `DatatypeMismatch`. Revertir.
- [ ] El job SQLite existente sigue igual y verde.
- [ ] Aislamiento por `business_id` intacto (no se toca ninguna consulta de producto).

### 9. Pruebas mínimas
- Local (opcional, si Codex tiene Docker): `docker run -e POSTGRES_PASSWORD=ci -p
  5432:5432 postgres:16` y `DATABASE_URL=postgresql://postgres:ci@localhost:5432/postgres
  python tests/postgres_smoke.py` → debe pasar; con el bug reintroducido, debe fallar.
- En CI: abrir el PR y confirmar que el job nuevo aparece y pasa.

### 10. Próximo paso recomendado
Escribir `tests/postgres_smoke.py` primero (con login + seed + GET a `/b/{id}/resumen`
y las APIs de la lista), probarlo local contra un Postgres en Docker, y solo después
añadir el job al `ci.yml`. Esqueleto orientativo del servicio (ajustar versiones):

```yaml
  postgres-smoke:
    name: Humo contra Postgres
    runs-on: ubuntu-latest
    timeout-minutes: 15
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: noesis
          POSTGRES_PASSWORD: noesis
          POSTGRES_DB: noesis_ci
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U noesis"
          --health-interval 5s --health-timeout 5s --health-retries 10
    env:
      DATABASE_URL: postgresql://noesis:noesis@localhost:5432/noesis_ci
      NOESIS_SECRET: noesis-ci-secret-fixed-32-characters-minimum
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with: { python-version: "3.13", cache: pip, cache-dependency-path: pyproject.toml }
      - run: pip install -e .
      - run: python -m noesis.migrations upgrade
      - run: python tests/postgres_smoke.py
```

### 11. Preguntas para el founder
Ninguna bloqueante. (Si en el futuro se quiere la suite entera en Postgres, es otra
tarea; esta ya cierra el hueco que nos ha mordido dos veces.)
