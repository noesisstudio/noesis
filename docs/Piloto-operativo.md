# Piloto operativo

Runbook de salida para 3-5 autónomos. No sustituye la validación legal, fiscal o de
seguridad externa.

## 1. Puerta de entrada

Ejecutar en el mismo entorno que se va a publicar:

```bash
noesis-doctor --strict
```

El comando no imprime secretos. Un `BLOQUEO` impide abrir el piloto; un `AVISO` debe
tener responsable, fecha y mitigación escrita. La salida JSON sirve para CI:

```bash
noesis-doctor --json --strict
```

## 2. Pruebas reales obligatorias

- WhatsApp: texto, nota de voz, ticket, factura PDF, confirmación, plantilla fuera de
  ventana, estado entregado/leído, reintento y número no vinculado. Aprobar y probar
  las plantillas `payment_reminder`, `quote_followup` y `appointment_reminder` con
  sus parámetros en el mismo orden configurado.
- Compositor interno: cobro, presupuesto, cita, gestoría y correo personalizado;
  cliente ambiguo, entidad de otro negocio, cambio antes del SÍ y fallo de entrega.
- IA: orden rutinaria local, consulta compleja, herramienta con datos reales,
  catalán, dato ausente, caída del primer proveedor, fallback y límite mensual.
- Dinero: borrador, emisión confirmada, pago parcial, impago, enlace Stripe, webhook
  duplicado, fallo y cancelación. Noesis nunca mueve dinero sin aceptación.
- Fiscal: IVA/IRPF, rectificativa, huella/QR/XML, cola y rechazo en entorno de pruebas
  AEAT; revisión con gestoría antes de producción.
- Operaciones: copia, restauración aislada, caída de correo, cola WhatsApp, alerta,
  exportación RGPD y aislamiento entre dos negocios.

Cada caso debe guardar momento, cuenta de prueba, resultado, incidencia y evidencia
sin copiar datos personales al registro de QA.

## 3. Instrumentación mínima

Medir semanalmente por negocio:

- minutos administrativos ahorrados y tareas completadas;
- trabajos terminados sin facturar y días hasta factura;
- cobros vencidos, recordatorios y dinero recuperado;
- mensajes avanzados, proveedor, coste estimado, p50/p95 y fallos;
- herramientas correctas, respuestas corregidas y escalados humanos;
- documentos bien clasificados y correcciones;
- activación, uso semanal y voluntad de pago.
- coste total por cuenta y plan: Stripe, WhatsApp utility, IA, audio, documentos,
  almacenamiento, voz, minutos de soporte y onboarding.

No ampliar módulos si el piloto no demuestra menos ruido mental y repetición de uso.

## 4. Incidentes y reversión

- Se puede desactivar IA externa por negocio; reglas y datos siguen disponibles.
- Se puede retirar el proveedor compatible y volver a Anthropic sin migrar datos.
- Mensajes, pagos, envíos fiscales y acciones irreversibles conservan confirmación.
- Ante fuga potencial, aislamiento roto o firma inválida: detener el canal afectado,
  preservar logs, revocar credenciales, informar al responsable y seguir el plan de
  incidentes validado externamente.
- Restaurar siempre en un destino aislado antes de tocar producción.

## 5. Criterio de salida del piloto

Avanzar a venta repetible solo si dos cierres semanales consecutivos muestran:

- flujos críticos sin pérdida de datos ni cruce de negocios;
- fallback de IA y canales comprensible para el usuario;
- coste variable observado compatible con el margen del plan;
- autónomos que vuelven sin acompañamiento diario del fundador;
- lista cerrada de fallos P0 con responsable y fecha.
