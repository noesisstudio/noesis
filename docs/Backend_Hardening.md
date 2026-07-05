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

## Pendiente de infraestructura
- Migrar SQLite a Postgres antes de escalar horizontalmente.
- Cola durable para procesar WhatsApp fuera del proceso web.
- Copias cifradas y externas con simulacro periódico de restauración.
- Holded real con credenciales y series separadas por negocio.
- Plantillas aprobadas por Meta para avisos proactivos fuera de la ventana de atención.
- Flujo administrativo de baja con conservación fiscal y eliminación al vencer plazos.
