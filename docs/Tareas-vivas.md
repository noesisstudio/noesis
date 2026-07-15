# Tareas vivas

> Único listado vivo de pendientes. La fotografía verificable está en
> [`project-state.json`](project-state.json); planes y traspasos no duplican estados.

## P0 — publicar y pilotar con seguridad

- [ ] Fusionar y desplegar el candidato actual; confirmar `/ready`, migración, Home,
  una ficha de proyecto, modo consulta y acompañante contextual.
- [ ] Crear o actualizar en Stripe los productos **29/49/99 € + IVA**, enlazar sus
  `price_id`, probar checkout, webhook, impago, reactivación y portal de cliente.
- [ ] Meta real: número, webhook firmado, texto, audio, foto/PDF, plantillas, estados,
  reintentos y bloqueo de cuenta inactiva.
- [ ] Aprobar plantillas Meta para cobro, presupuesto y cita; validar SÍ/NO y entrega
  desde el WhatsApp real del titular.
- [ ] SMTP real: invitaciones, facturas, avisos y entregabilidad.
- [ ] Certificado/entorno AEAT y validación con asesoría fiscal.
- [ ] Ejecutar `noesis-doctor --strict` en producción y resolver todo bloqueo.
- [ ] Restaurar una copia externa en un entorno aislado y documentar tiempos.
- [ ] Auditoría externa de seguridad, privacidad, fiscalidad y procedimiento de
  incidentes.
- [ ] Piloto acompañado con 3-5 autónomos durante dos cierres semanales.
- [ ] Medir activación hasta primer cobro, tiempo ahorrado, trabajos sin facturar,
  cobros recuperados, correcciones, coste por cuenta y retención.

## P1 — profundidad después del primer piloto

- [ ] Evaluar servicio privado y proveedor compatible con el mismo corpus en
  castellano/catalán: herramientas, calidad, latencia, coste, concurrencia y caídas.
- [ ] Documentos: duplicados, HEIC, PDF escaneado, líneas, búsqueda y corrección
  masiva con corpus real.
- [ ] Calendario externo, recurrentes, comunicaciones y conciliación.
- [ ] Equipo: varios trabajadores reales, offline, ausencias y permisos finos.
- [ ] Gestoría con cuentas/MFA, varias empresas y revisión por documento.
- [ ] Observabilidad por negocio para IA, extracción, colas, latencia, errores,
  correcciones y coste.
- [ ] Revisar cada pantalla con evidencia visual tras estabilizar el diseño; su
  jerarquía debe responder a su tarea, no copiar la de otra sección.

## P2 — solo con retención demostrada

- Personalización por sector, rutas, hitos, PWA profunda, inventario, nóminas y
  recepcionista de voz, sujetos a demanda real y unit economics sostenibles.

## Límites permanentes

- Noesis prepara; el autónomo confirma pagos, transferencias, impuestos, emisiones,
  envíos sensibles y borrados irreversibles.
- Todo aprendizaje distingue observado de confirmado y es visible y corregible.
- Toda operación filtra por `business_id`.
- El cerebro local sigue disponible aunque una integración falle o se desactive.
