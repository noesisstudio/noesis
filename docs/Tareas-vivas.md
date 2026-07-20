# Tareas vivas

> Único listado vivo de pendientes. La fotografía verificable está en
> [`project-state.json`](project-state.json); planes y traspasos no duplican estados.

## P0 — publicar y pilotar con seguridad

- [ ] Fusionar el candidato fiscal, desplegar el `main` resultante, aplicar migración
  33 y confirmar `/ready`, alta por prueba, alta por contratación, preferencias operativas,
  vencimiento de factura, checkout, Home, modo consulta y una ficha de proyecto.
- [ ] Crear o actualizar en Stripe los productos **29/49/99 € + IVA**, enlazar sus
  seis `price_id`, resolver cómo aplica el IVA el Checkout y probar checkout,
  webhook, impago, reactivación y portal de cliente antes de usar claves live.
- [ ] Meta real: número, webhook firmado, texto, audio, foto/PDF, plantillas, estados,
  reintentos y bloqueo de cuenta inactiva.
- [ ] Aprobar plantillas Meta para factura (`noesis_factura_lista`), cobro,
  presupuesto y cita; validar SÍ/NO, PDF/enlace privado y entrega desde el WhatsApp
  real del titular.
- [ ] SMTP real: credenciales, invitaciones, facturas, avisos, reintentos de la outbox
  y entregabilidad. La cola durable ya está construida.
- [ ] Crear el cliente OAuth web de Google, registrar exactamente
  `https://app.bynoesis.com/auth/google/callback`, cargar `GOOGLE_OAUTH_CLIENT_ID`
  y `GOOGLE_OAUTH_CLIENT_SECRET` en producción y probar alta y acceso reales. El
  botón permanece oculto hasta que ambas credenciales existan para no prometer una
  función falsa.
- [ ] Certificado/entorno AEAT: autorización por obligado tributario, mTLS en pruebas,
  aceptación/rechazo/duplicado/CSV/reintentos, alta y anulación ya construidas,
  subsanación de rechazos, declaración
  responsable y validación con asesoría fiscal antes de producción.
- [ ] Ejecutar `noesis-doctor --strict` en producción y resolver todo bloqueo.
- [ ] Restaurar una copia externa en un entorno aislado y documentar tiempos.
- [ ] Auditoría externa de seguridad, privacidad, fiscalidad y procedimiento de
  incidentes.
- [ ] Piloto acompañado con 3-5 autónomos durante dos cierres semanales.
- [ ] Medir activación hasta primer cobro, tiempo ahorrado, trabajos sin facturar,
  cobros recuperados, correcciones, coste por cuenta y retención.

Credenciales, callbacks, variables y criterios de aceptación: [[Conectar-APIs]].

## P1 — profundidad después del primer piloto

- [ ] Evaluar servicio privado y proveedor compatible con el mismo corpus en
  castellano/catalán: herramientas, calidad, latencia, coste, concurrencia y caídas.
- [ ] Documentos: duplicados, HEIC, PDF escaneado, líneas, búsqueda y corrección
  masiva con corpus real.
- [ ] Calendario: validar la suscripción ICS en Google/Apple/Outlook; después decidir
  si el piloto necesita sincronización bidireccional OAuth y recurrentes.
- [ ] Conciliación: validar CSV de bancos reales; dejar PSD2/API bancaria y cobro por
  enlace para después del piloto. Ningún movimiento se confirma automáticamente.
- [ ] Correo: panel interno de detalle/reejecución manual si los avisos agregados de
  la outbox resultan insuficientes durante el piloto.
- [ ] Equipo: varios trabajadores reales, offline, ausencias y permisos finos.
- [ ] Gestoría con cuentas/MFA, varias empresas y revisión por documento.
- [ ] Observabilidad por negocio para IA, extracción, colas, latencia, errores,
  correcciones y coste.
- [ ] Revisar cada pantalla con evidencia visual tras estabilizar el diseño; su
  jerarquía debe responder a su tarea, no copiar la de otra sección.
- [ ] Fiscalidad ampliada: exenciones E1-E8, no sujeción N1/N2, inversión del sujeto
  pasivo, identificación extranjera y divisas, solo después de validarlas con
  asesoría y XSD/validaciones AEAT. Hasta entonces el 0% es tipo cero, no exención.

## P2 — solo con retención demostrada

- Personalización por sector, rutas, hitos, PWA profunda, inventario, nóminas y
  recepcionista de voz, sujetos a demanda real y unit economics sostenibles.

## Límites permanentes

- Noesis prepara; el autónomo confirma pagos, transferencias, impuestos, emisiones,
  envíos sensibles y borrados irreversibles.
- Todo aprendizaje distingue observado de confirmado y es visible y corregible.
- Toda operación filtra por `business_id`.
- El cerebro local sigue disponible aunque una integración falle o se desactive.
