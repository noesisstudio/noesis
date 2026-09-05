# Benchmark SaaS

Referencias revisadas para orientar el pulido de producto de Bynoesis sin copiar marca,
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
- Guías recientes de landing SaaS/IA: claridad inmediata, producto visible en el hero,
  precios transparentes, FAQ, prueba de confianza y CTA repetido.
  https://www.saasframe.io/blog/10-saas-landing-page-trends-for-2026-with-real-examples
  https://www.wearetenet.com/blog/saas-landing-page-examples
  https://grooic.com/blog/best-ai-saas-landing-page-examples

## Patrones aplicados a Bynoesis

- Priorizar la acción siguiente, no solo mostrar métricas.
- Separar "facturado" de "cobrado" y destacar cobros atrasados.
- Hacer que agenda, clientes, facturas y cobros parezcan un mismo flujo operativo.
- Usar estados vacíos que indiquen el siguiente paso real.
- Reforzar el asistente como puerta de entrada a acciones, no como chat decorativo.
- Mantener lenguaje de confianza: fiscalidad clara, WhatsApp oficial solo después de
  validarlo extremo a extremo, datos
  exportables y mínimo uso de APIs externas.
- Cuidar móvil y tablas con scroll horizontal cuando la densidad de datos lo exige.
- Landing pública con hero orientado al resultado, captura real del producto, misión,
  visión, precios, FAQ y CTA hacia registro/login.
- Asistente con lectura contextual del negocio: no solo comandos, también criterio sobre
  cobros, agenda, margen y concentración de clientes.

## Comparativa funcional de facturación — 2026-07-20

La referencia pública de Holded confirma como base profesional: series de numeración,
facturas completas y simplificadas, múltiples líneas con cantidad/precio/impuesto,
borradores, rectificación, recurrencia, PDF, cobros e historial. Bynoesis cubre ya ese
nucleo con desarrollo propio y añade controles coherentes con su posicionamiento:
emisión recurrente desactivada por defecto, confirmación reforzada para anular y
trazabilidad visible por factura.

| Capacidad | Bynoesis candidato, esquema 33 | Diferencia consciente |
|---|---|---|
| Series y numeración | General, rectificativa y ticket; correlativas por negocio/serie/año | Falta editor avanzado de plantillas y prefijos por sede |
| Tipos y líneas | Completa F1 y simplificada F2; cantidad, precio, descuento e IVA mixto | El 0 % es tipo cero; faltan exenciones E1-E8 y no sujeción N1/N2 |
| Ciclo de vida | Borrador editable; emitida inmutable; duplicar y rectificar R1-R5 | Falta subsanación fiscal específica de registros rechazados |
| Recurrencia | Generación idempotente; borrador por defecto; autoemisión autorizada | Falta calendario avanzado por hitos y prorrateos |
| Entrega y seguimiento | PDF, correo durable con reintentos, portal e historial de eventos | Falta cobro por enlace y telemetría real de apertura del correo |
| Veri*Factu | Alta y anulación append-only, QR/XML, huella y colas SOAP/mTLS | Falta certificado real, pruebas AEAT, declaración responsable y auditoría fiscal |

Fuentes primarias de referencia:

- [Facturación de Holded](https://www.holded.com/es/programa-facturacion)
- [Facturas recurrentes de Holded](https://www.holded.com/es/programa-facturacion/facturas-recurrentes)
- [Numeración de documentos en Holded](https://help.holded.com/es/articles/6878171-crear-la-numeracion-de-tus-documentos)
- [Crear una factura de venta en Holded](https://help.holded.com/es/articles/6834950-crear-una-factura-de-venta)
- [Borradores, cancelación y rectificación en Holded](https://help.holded.com/es/articles/6887128-factura-en-modo-borrador-como-funciona-y-cuando-se-aplica)
- [Contenido obligatorio de las facturas — AEAT](https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/facturacion-iva/contenido-facturas.html)
- [Registros de anulación Veri*Factu — AEAT](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/registros-facturacion-anulacion.html)

## Límite consciente

Bynoesis no debe convertirse en un ERP amplio como Holded. Su hueco diferencial sigue
siendo: autónomo de servicios, WhatsApp primero, oficina ligera y proactiva.
