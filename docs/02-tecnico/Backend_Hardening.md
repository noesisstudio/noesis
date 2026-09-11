# Endurecimiento del backend

Revisión aplicada en `codex/backend-hardening` para convertir las garantías críticas
en reglas de código y pruebas, no en convenciones.

## Cerrado
- Aislamiento doble por `business_id`, incluido el retorno de mutaciones.
- Configuración booleana explícita: `false` ya no activa demo ni borrado.
- Producción no arranca con secreto de sesión de desarrollo o URL sin HTTPS.
- Contraseñas nuevas de 12 caracteres, PBKDF2 600.000 y sesiones revocables.
- Protección de origen, cabeceras de seguridad y límites de JSON/audio/chat.
- Facturas con secuencia persistente, estado válido e instantánea fiscal inmutable.
- Presupuestos y emisiones idempotentes.
- Modelo 130 acumulado desde enero; modelo 303 conserva cálculo trimestral.
- WhatsApp firmado, códigos persistentes, teléfono único y mensajes deduplicados.
- Stripe firmado, deduplicado y tolerante a eventos desordenados habituales.
- Scheduler con ejecución única y confirmación real antes de marcar recordatorios.
- CSV protegido ante fórmulas y asistente limitado en memoria/acciones irreversibles.
- Baja de cuenta ordenada por dependencias: la base confirma antes de borrar archivos.
- Webhooks con ciclo recuperable y respuesta 5xx ante fallos de procesamiento.
- Importes fiscales calculados con `Decimal` y redondeo comercial al céntimo.
- Backups verificados de base de datos y documentos subidos.
- Panel admin con salud agregada de `verifactu_outbox`: vencidas, agotadas,
  rechazos, actividad reciente y negocios afectados, sin activar remisión AEAT.

## Pendiente de infraestructura

> Esta sección no sustituye a [[Tareas-vivas]]. Evita conservar como pendientes
> trabajos que ya cerró el código.

- Desplegar el esquema actual en PostgreSQL y verificar `/ready`; SQLite queda como
  fallback local, no como base operativa de producción.
- Restaurar una copia S3-compatible en un entorno aislado y medir RPO/RTO.
- Conectar Meta, aprobar plantillas y probar firma, estados y reintentos reales. La
  outbox durable y el bloqueo entre réplicas ya están construidos.
- Mantener la facturación completamente nativa: ningún proveedor externo recibe la
  factura ni decide numeración, emisión o registro Veri*Factu.
- Completar auditoría externa de seguridad, privacidad, fiscalidad e incidentes.
- Validar con asesoría el flujo de baja, conservación fiscal y borrado al vencer los
  plazos. Credenciales y pruebas: [[Conectar-APIs]].
