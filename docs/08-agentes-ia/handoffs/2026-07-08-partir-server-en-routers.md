# Traspaso: partir `web/server.py` en routers por dominio

- **De → para:** Fable 5 (Opus 4.8) → Codex (implementación)
- **Fecha:** 2026-07-08
- **Rama:** `codex/routers-por-dominio` (crear desde `main`)
- **Nivel de confianza del que entrega:** alto en el objetivo y el mapa; es un
  refactor mecánico sin decisiones de producto.
- **¿Requiere revisión antes de implementar?** No bloqueante. Es refactor puro:
  **cero cambios de comportamiento, cero rutas nuevas, cero SQL nuevo**. Si en el
  camino aparece la tentación de "ya que estoy, arreglo…", NO. Solo mover.

### 1. Contexto del producto
Bynoesis conecta el ciclo trabajo→factura→cobro→gestoría. Toda la capa web vive hoy
en un único `web/server.py` que ha crecido a **2.597 líneas y 145 rutas**. No es un
problema de usuario, es de mantenibilidad: es el paso técnico previo a la capa C
(portal gestoría con cuentas, canales, proyectos). Ver [[Metodo-operativo-Fable]] §3
y [[Arquitectura]].

### 2. Objetivo de la tarea
Partir `server.py` en varios `APIRouter` por dominio, **sin cambiar ni una URL ni
una respuesta**. La app se comporta exactamente igual; solo cambia dónde vive cada
ruta. Criterio de éxito: los 152 tests pasan sin tocarlos.

### 3. Estado actual
- Funciona ya: 145 rutas en `web/server.py` (páginas HTML + API JSON + webhooks +
  portal + gestoría + admin), montadas sobre `app = FastAPI(...)` con middleware de
  sesión, `lifespan`, y `_PAGES` para las páginas de la SPA multipágina.
- A medias: nada. Es refactor, no funcionalidad.
- NO existe: separación por dominio. Todo el peso está en un archivo.

### 4. Decisiones tomadas (con porqué)
- Refactor puro por fases, **un dominio por commit**, tests verdes entre cada uno —
  así, si algo se rompe, se ve en el commit exacto. Registrada en [[Decisiones]]: no
  (es táctica de ejecución, no decisión de producto).
- Se usan `fastapi.APIRouter`, no sub-aplicaciones montadas: mismo `app`, mismos
  paths absolutos, mismos decoradores; solo cambia `@app.get` → `@router.get`.

### 5. Decisiones pendientes
- Ninguna que bloquee. Nombres de los módulos router: propuesta abajo; si Codex ve
  un corte más natural, puede ajustarlo **manteniendo los paths intactos**.

### 6. Mapa de la tarea
- **Archivo origen:** `src/noesis/web/server.py`.
- **Destino propuesto:** paquete `src/noesis/web/routers/` con:
  - `pages.py` — páginas HTML de la app (`/b/{id}/<page>` y `_PAGES`).
  - `invoicing.py` — facturas, presupuestos, cobros, impuestos.
  - `clients.py` — clientes, CRM (leads), productos.
  - `documents.py` — documentos, facturas recibidas, proveedores.
  - `gestoria.py` — solicitudes y paquete de gestoría (coordinar con `web/gestoria.py`).
  - `assistant.py` — chat/asistente, briefing por página, idioma.
  - `finance.py` — resumen, análisis, tesorería, P&G (`/pnl`, `/analysis`).
  - `account.py` — ajustes, suscripción, onboarding, auth-adyacentes (NO tocar `auth.py`).
  - `portal.py` — portal de cliente `/p/...` y `/g/{token}` público.
  - `webhooks.py` — WhatsApp/Stripe/health (`/health`, `/ready`).
  - `admin.py` — panel de administración.
- **Entidades/tablas implicadas:** ninguna. **No hay migración.**
- **Rutas web afectadas:** se mueven todas; **no se altera ninguna URL**.
- **Servicios a reutilizar (no reinventar):** todo lo de `db.py`, `documents/`,
  `web/chat.py`, `web/gestoria.py`, `adapters/`. Los routers solo mueven las
  funciones de ruta; la lógica ya vive fuera y ahí se queda.

### 7. Riesgos y qué NO hacer
- **No tocar:** `web/auth.py`, la cadena de `verifactu.py`, tablas append-only, ni
  el orden de registro del middleware de sesión (`SessionMiddleware`) respecto a las
  rutas.
- **No cambiar** ni un path, ni un nombre de parámetro de query, ni un status code,
  ni el `response_class` (HTMLResponse vs JSONResponse) de ninguna ruta.
- **Orden de inclusión:** montar los routers con `app.include_router(...)` respetando
  el orden actual donde haya solapamientos de path (p. ej. rutas comodín de páginas
  al final). Verificar que ninguna ruta específica quede ensombrecida por una genérica.
- **Dependencias compartidas** (helpers como `current_user`, `require_business`,
  render de plantillas, CSRF): extraer a `web/deps.py` **sin cambiar su firma**; que
  los routers importen de ahí. No duplicar.
- Si al mover una ruta un test se pone rojo, **parar y revisar ese commit**; no seguir
  acumulando movimientos sobre una base rota.

### 8. Criterios de aceptación
- [ ] `server.py` queda como ensamblador: crea `app`, configura middleware/lifespan
      e incluye los routers. Objetivo orientativo: < 300 líneas.
- [ ] **Ninguna URL cambia.** Diff de rutas antes/después idéntico (ver §9).
- [ ] Tests verdes **sin modificarlos**: `python -m unittest discover -s tests` (152).
- [ ] Aislamiento por `business_id` intacto (no se toca ninguna consulta).
- [ ] Servidor arranca y las páginas afectadas responden 200 (usar el lanzador
      `noesis-demo`, login `demo@noesis.app` / `demo1234`, recorrer el menú).
- [ ] Un commit por dominio, con los tests verdes en cada uno.

### 9. Pruebas mínimas
- Antes de empezar, volcar el inventario de rutas y congelarlo como referencia:
  `python -c "import sys; sys.path.insert(0,'src'); from noesis.web.server import app;
  [print(sorted(m)[0] if r.methods else '', r.path) for r in app.routes]"`
  Repetir al final y comparar: **debe ser idéntico** (mismo set de (método, path)).
- Ejecutar la suite completa tras cada commit de dominio.
- Manual: arrancar `noesis-demo` y comprobar que cada apartado del menú carga con
  datos (el demo trae clientes, facturas, CRM, documentos, gestoría, P&G).

### 10. Próximo paso recomendado
Crear `web/deps.py` extrayendo los helpers compartidos (autenticación de la petición,
`require_business`, render de plantillas, CSRF) **sin cambiar firmas**, con los tests
en verde. Después, mover el **primer** dominio pequeño y autocontenido (sugerencia:
`webhooks.py` con `/health` y `/ready`) como patrón, verificar, y repetir dominio a
dominio.

### 11. Preguntas para el founder
Ninguna. Es refactor interno sin efecto observable para el usuario.
