# Registro de QA

## 2026-07-14 — coste de IA y preparación del piloto

- Suite completa: **188 pruebas verdes**; permanecen el aviso conocido de
  Starlette/httpx y los logs esperados de caídas simuladas.
- Proveedor compatible: contrato, herramientas, coste estimado y fallback a
  Anthropic cubiertos. Una caída entre proveedores consume un solo crédito.
- Si una herramienta pudo escribir antes de una caída, el segundo proveedor no
  repite la orden automáticamente; el usuario recibe un aviso para revisar actividad.
- `noesis-doctor`: salida humana/JSON, avisos, bloqueos por configuración parcial,
  HTTPS obligatorio para el proveedor externo y ausencia de secretos cubiertos.
- Notebook de costes ejecutado de principio a fin; SQL reproducible contrastado con
  la tabla del informe. Artefacto ejecutivo validado y renderizado.
- Servidor real con base temporal: `/health`, `/ready`, `/privacidad` y
  `/encargado-tratamiento` en 200; el subencargado compatible configurado apareció
  en ambos documentos legales.
- `compileall` y `git diff --check` verdes. No se llamó a Meta, Stripe, AEAT ni a un
  modelo real; esas pruebas siguen siendo P0 del piloto.

## 2026-07-14 — IA desde el primer día y guardián PostgreSQL

- `compileall`, `git diff --check`, suite completa: 182 pruebas y 26 subpruebas
  verdes; permanece el aviso conocido Starlette/httpx.
- Regresión PostgreSQL corregida en la ficha de proyecto: fecha de entrada y fecha
  de creación se ordenan como texto compatible. El smoke añade listado/detalle de
  proyecto, Ajustes, integraciones y parte de campo. GitHub Actions aplicó la
  migración 27/27 y pasó el smoke en PostgreSQL 16.
- IA privada: contrato OpenAI-compatible, herramientas validadas por servidor,
  historial y contexto por negocio, métricas sin contenido y cero créditos externos.
- IA externa: consentimiento explícito en onboarding, opción completa recomendada,
  límite mensual por plan y reserva atómica aislada por `business_id`.
- Servidor real con base temporal: `/health`, `/ready`, Home, onboarding, Ajustes,
  proyectos, detalle y campo en 200; creación de proyecto 201. Se renderizaron
  «Experiencia completa» e «IA privada».
- No se validó un modelo privado, Anthropic ni Meta reales porque no se usaron
  credenciales ni servicio de inferencia. Ese extremo permanece en [[Tareas-vivas]].

## 2026-07-13 — integraciones y salud por negocio

- Migración 27 verificada en SQLite con ida y vuelta hasta 25.
- Suite completa tras combinar `main`: 178 pruebas verdes y 26 subpruebas; aviso
  conocido Starlette/httpx.
- Aislamiento probado para preferencias de IA y solicitudes de banco; la API queda
  además protegida por la guarda común de sesión y `business_id`.
- La salud operativa cuenta por negocio uso/latencia de IA, documentos pendientes,
  correcciones, cola WhatsApp y cola Veri*Factu; no muestra contenido ni credenciales.
- La IA externa y la extracción documental respetan la preferencia. En cuentas nuevas
  parte apagada; reglas, OCR y clasificador local siguen funcionando.
- Smoke HTTP con servidor real: login, Ajustes, API de integraciones, `/health` y
  `/ready` en 200; ocho integraciones renderizadas y detalle operativo presente.
- QA visual pendiente: el navegador interno se cerró antes de alcanzar localhost y
  Chrome no estaba disponible en la sesión. No se sustituye por una validación
  visual ficticia. También queda el smoke Meta/IA/AEAT con credenciales reales.

## 2026-07-13 — monitorización admin Veri*Factu

- Suite completa: 176 pruebas verdes; avisos/logs esperados de tests de reintentos
  Stripe, WhatsApp, Veri*Factu, backup y resiliencia del parte.
- Tests específicos: `VerifactuTestCase` + `AdminCommandCenterTestCase` -> 20 OK.
- `compileall` y `git diff --check` verdes.
- Servidor local con base temporal: `/health` 200, `/ready` 200, login admin 303 y
  `/admin` 200 mostrando “Cola Veri*Factu” y “Vencidas para enviar”.
- Sin conexión AEAT real: solo se validó la observabilidad de la cola, no la
  remisión externa.

## 2026-07-13 — cierre de campo y perfil de cliente

- Suite completa: 175 pruebas verdes; aviso conocido Starlette/httpx.
- Migraciones 25-26 y orden de FK Postgres verificados.
- Aislamiento probado para trabajador, cliente, evidencia, firma y factura.
- QA local desktop/móvil de Clientes, Proyectos y portal del trabajador: 200, sin
  overflow horizontal ni errores de consola.

## 2026-07-13 — columna operativa y control del usuario

- Migraciones 22-24 verificadas en SQLite y generación DDL de Postgres: permisos y
  auditoría, vínculos de proyecto/tarea y entregas versionadas a gestoría.
- Suite completa final: 170 pruebas y 26 subpruebas verdes; queda una advertencia
  de deprecación Starlette/httpx ya conocida, sin error funcional.
- Proyectos: coste real combinado de fichaje, tarifa horaria, gastos y entradas
  manuales sin doble conteo; aislamiento cruzado cubierto.
- Gestoría: paquete con emitidas, gastos, recibidas, originales, manifiesto y huella;
  una fuente sin cambios conserva versión y un cambio crea la siguiente.
- Navegador local: Inicio, Proyectos, Documentos, Ajustes y portal del trabajador en
  200, sin errores de consola. Se comprobó el modal de proyecto y un trabajador con
  trabajo y checklist reales.
- WhatsApp interno: texto, foto, PDF y audio ya tenían flujo; se añadió `HOY`, fichaje
  por trabajo y actualización de tarea para el trabajador vinculado.
- Pendiente externo: Meta, Stripe, proveedor de IA y certificado AEAT no se validan
  sin credenciales reales y siguen figurando como bloqueo de piloto.

## 2026-07-12 — Noesis persistente y entrada documental universal

- Migración 21 aplicada en SQLite: historial del asistente, memoria confirmada,
  clasificación documental trazable y protección de facturas históricas.
- Suite completa: 164 pruebas pasan, incluida separación por negocio, exportación
  RGPD, señales de clientes y confirmación de una factura recibida enviada por PDF
  en WhatsApp.
- Navegador: historial persistente comprobado entre Home y Clientes; el panel de
  Noesis abre desde cada pantalla y conserva el contexto de página.
- Documentos: subida web sin selector técnico; Noesis propone el tipo y la persona
  confirma. Web y WhatsApp usan el mismo clasificador.
- Responsive comprobado a 390 × 844: asistente y panel inferior sin solapamiento
  del campo de texto ni scroll horizontal (`scrollWidth = clientWidth = 375`).
- Pendiente externo: prueba de extremo a extremo con Meta, claves del proveedor de
  IA, Stripe y certificado AEAT. No se han simulado conexiones reales.

## 2026-07-11 — MVP profesional

- Suite completa: 158 pruebas y 26 subpruebas pasan; queda una advertencia de
  deprecación ya existente de Starlette/httpx, sin errores funcionales.
- Proyectos: migraciones SQLite, aislamiento entre negocios, presupuesto, horas,
  coste, margen, equipo, exportación RGPD y borrado en cascada cubiertos por pruebas.
- Navegador: Home y Proyectos renderizan con datos demo; APIs sin errores de consola.
- Responsive comprobado a 390 × 844: Home y Proyectos sin scroll horizontal.
- Menú móvil: `aria-expanded` y `aria-hidden` sincronizados al abrir/cerrar.
- Regresiones corregidas: imports que rompían descarga/subida de Documentos y
  verificación/entrada del webhook de WhatsApp.
- Pendiente externo: prueba real con credenciales Meta, Stripe y certificado AEAT.
