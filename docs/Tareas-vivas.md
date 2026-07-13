# Tareas vivas

Ordenadas por riesgo y por lo que desbloquea clientes reales. No volver a construir
módulos internos que ya existen: primero cerrar integración, validación y piloto.

## P0 — antes de declarar el MVP listo

- [ ] Revisar, fusionar y desplegar `codex/operating-spine`.
- [ ] Ejecutar migraciones 22-24 en Postgres y comprobar rollback en un esquema de
  ensayo.
- [ ] Meta real: verificar webhook, descarga de audio/foto/PDF, plantillas, estados
  de entrega, reintentos e idempotencia con un número de prueba.
- [ ] Fiscalidad: configurar productor, certificado y entorno AEAT; validar con una
  gestoría o asesor fiscal el flujo completo y los textos legales.
- [ ] Pagos: conectar Stripe, confirmar webhook y conciliación. No habilitar ninguna
  transferencia automática; la aceptación específica del autónomo es obligatoria.
- [ ] Seguridad: revisión externa de tokens de portales, sesiones, rate limiting,
  copias, restauración, RGPD, conservación laboral y aislamiento multiempresa.
- [ ] Piloto acompañado con 3-5 autónomos de servicios durante dos cierres de semana.

## P1 — evidencia de producto y operación

- [ ] Medir activación: WhatsApp conectado, primer cliente, primer trabajo, primera
  factura y primer cobro.
- [ ] Medir tiempo ahorrado, documentos pendientes, cobros recuperados y proyectos
  que detectan desvío antes de perder margen.
- [ ] Crear onboarding por sector con ejemplos reales sin añadir complejidad a Home.
- [ ] Añadir observabilidad de costes de IA, fallos de extracción y colas por negocio.
- [ ] Preparar soporte, recuperación ante incidentes y procedimiento de baja con
  conservación fiscal/laboral.

## P2 — después del aprendizaje del piloto

- [ ] Integraciones contables/bancarias priorizadas por demanda demostrada.
- [ ] Reglas avanzadas por cliente/proyecto, siempre explicables y revocables.
- [ ] Recepcionista de llamadas solo si el piloto valida el problema y su economía.
- [ ] App/PWA de campo más profunda si WhatsApp y el portal no cubren el uso real.

## Límites permanentes

- Noesis puede preparar una transferencia, un impuesto, una devolución o una
  emisión; nunca confirmarlos en nombre del autónomo.
- Un LLM no escribe directamente en tablas fiscales ni decide el destinatario final.
- Los hechos aprendidos deben ser visibles, corregibles y atribuibles a una fuente.
- Toda automatización externa necesita una acción puntual o una regla explícita.
