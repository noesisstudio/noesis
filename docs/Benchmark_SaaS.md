# Benchmark SaaS

Referencias revisadas para orientar el pulido de producto de Noesis sin copiar marca,
interfaz ni funcionalidades propietarias.

## Productos mirados

- Holded: facturación, cobros, estados de factura, tesorería y cumplimiento Verifactu.
  https://www.holded.com/es/programa-facturacion
- Forjia: facturación por WhatsApp para autónomos; audio/foto/mensaje, revisión y
  confirmación antes de enviar.
  https://getforjia.com/
- Quipu: facturación, cobros/pagos, impuestos, bancos y digitalización de tickets.
  https://getquipu.com/
- Declarando: tranquilidad fiscal para autónomos y lenguaje de "sin miedo a sanciones".
  https://declarando.es/programa-facturacion-electronica
- Jobber: software para servicios de campo; flujo presupuesto -> agenda -> factura ->
  cobro, acciones recomendadas y vista rápida de negocio.
  https://www.getjobber.com/features/field-service-management-software/
- Housecall Pro: servicios de campo; agenda, estimaciones, pagos, app móvil y ahorro de
  tiempo operativo.
  https://www.housecallpro.com/field-service-management-software/

## Patrones aplicados a Noesis

- Priorizar la acción siguiente, no solo mostrar métricas.
- Separar "facturado" de "cobrado" y destacar cobros atrasados.
- Hacer que agenda, clientes, facturas y cobros parezcan un mismo flujo operativo.
- Usar estados vacíos que indiquen el siguiente paso real.
- Reforzar el asistente como puerta de entrada a acciones, no como chat decorativo.
- Mantener lenguaje de confianza: fiscalidad clara, WhatsApp oficial futuro, datos
  exportables y mínimo uso de APIs externas.
- Cuidar móvil y tablas con scroll horizontal cuando la densidad de datos lo exige.

## Límite consciente

Noesis no debe convertirse en un ERP amplio como Holded. Su hueco diferencial sigue
siendo: autónomo de servicios, WhatsApp primero, oficina ligera y proactiva.
