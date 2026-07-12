# Registro de QA

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
