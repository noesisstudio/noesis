# Registro de QA

## 2026-07-13 — integraciones y salud por negocio

- Migración 27 verificada en SQLite con ida y vuelta hasta 25.
- Suite completa: 177 pruebas verdes y 26 subpruebas; aviso conocido Starlette/httpx.
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
