# Revisión de frentes — 7 de septiembre de 2026

Candidato local, sin commit, push ni despliegue. Se conserva el informe original
`Frentes-abiertos.html` como evidencia histórica, no como estado actual.

## Corregido

1. Menú público móvil: enlaces oscuros sobre blanco. Heredaban el blanco de la cabecera.
2. Panel Crear: fondo opaco, altura limitada, scroll, cierre visible, Escape y retorno
   del foco. Antes se mezclaba con el contenido de Inicio por carecer de fondo.
3. Ficha admin: WhatsApp del titular leído de la cuenta, separado del canal comercial.
   Actualizar relee la BD; no se afirma tener conexión en tiempo real con Meta.
4. Consumo por negocio/proveedor/modelo y mes: llamadas, tokens, estimación USD,
   llamadas sin coste y latencia si hay muestras. JSON administrativo auditado,
   sin caché, claves, teléfono ni contenido: `/admin/cuentas/{id}/consumo`.
5. Extracción documental registra tokens incluso si después falla interpretar el
   JSON. El fallo de telemetría no rompe la operación; sin tarifas el coste es desconocido.
6. WhatsApp usa el tipo aplicado por la revisión de confianza, no la propuesta IA.
   Una posible factura dudosa no cae al flujo de gastos. Una factura recibida
   ilegible ya no se describe como emitida por el usuario.

## Límites de la medición

La unidad es el negocio, no cada trabajador: el registro no permite atribución
completa por persona. La tabla incluye eventos `ai_usage`, ahora también extracción.
WhatsApp/correo conservan recuentos en Canales, pero no equivalen al importe facturado.
Voz, pagos, almacenamiento y otras APIs no están totalmente instrumentadas.
Sin eventos no significa coste cero. No se reconstruye historial inexistente.

Las tarifas producen estimaciones. La conversión se configura mediante
`NOESIS_COST_USD_TO_EUR` (por defecto 0,92); se muestra en la ficha de consumo.
No es una cotización actualizada. Queda conciliar facturas reales. Sin claves por cliente
ni almacenamiento de conversaciones o documentos en la telemetría.

## Informe del socio: qué queda

| Frente | Estado y siguiente trabajo |
|---|---|
| Marca en Railway | Valores desplegados pendientes de comprobación autorizada. No renombrar paquete ni variables internas. |
| Voz | Adaptadores existentes; proveedor/capacidad/credenciales y acuerdos pendientes. No activado. |
| Copias externas | Candidato anterior preparado; bucket, permisos y recuperación externa aún pendientes. |
| RGPD | Acuerdos, región efectiva, conservación y validación jurídica no se resuelven solo con código. |
| Teléfono titular | Visible en ficha administrativa. |
| Números comerciales | Permisos Meta/onboarding comercial pendientes; no actualizar Graph a ciegas. |
| Latencia | Paginación opcional SQL de facturas y filtro SQL del portal implementados. Medición con volumen y optimización del resto pendientes. |
| Webhook pesado | Cola duradera con reintentos/idempotencia pendiente; una tarea en memoria no basta. |
| Roles internos | Autorización actual conservada; lectura/soporte/dirección requieren regresión transversal. |
| Cal.com | Aplazado por petición del founder. |
| Confianza documental | Corregido en entrada PDF/foto de WhatsApp. |
| Excepciones extracción | Candidato anterior registra clase de error sin contenido sensible. |
| «Registra la que te envié» | Contexto reciente pendiente, resolviendo ambigüedad y permisos antes de actuar. |
| Reenvíos | Relectura ya existente en la base; no es novedad de este bloque. |
| Varias facturas PDF | Candidato anterior evita tomar solo la primera; separación automática no implementada. |
| Tests lentos | Regresiones dirigidas y suite general; partición de CI pendiente. |

## Validación y rollback

Resultado final en `Registro-QA.md`. Capturas locales con datos ficticios en
`qa/2026-09-07/menu-mobile.png` y `create-mobile.png`. Navegador integrado con
viewport móvil: no equivale a Safari en iPhone físico. Apertura, Escape y retorno
del foco comprobados. Sin migración (55); observación aditiva no bloqueante.

Rollback por cambios de este bloque, preservando candidato anterior y datos; los
eventos nuevos pueden permanecer sin consumidores. No resetear el árbol completo.
Antes de publicar: revisión conjunta, Postgres, Safari físico e integraciones de prueba.
