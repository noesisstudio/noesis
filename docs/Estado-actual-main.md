# Estado actual de `main`

> Última auditoría: 2026-07-13. Este documento distingue el código ya fusionado de
> lo que está listo en una rama para evitar que otra IA dé por desplegado algo local.

## En `origin/main`

- Último commit auditado: `37a2a99` (merge de PR #26).
- Esquema: migración 21.
- Suite auditada antes de esta rama: 164 pruebas verdes.
- Existe la base de plataforma: Home como parte diario, proyectos iniciales,
  documentos inteligentes, facturas recibidas, proveedores, CRM, gestoría,
  memoria confirmada y asistente contextual.
- El despliegue de Railway correspondiente a ese commit estaba saludable.

## Listo en `codex/operating-spine`, aún no fusionado

- Migraciones 22-24: control de autonomía, columna operativa y entregas a gestoría.
- Proyecto conectado con trabajo, trabajador, fichaje, coste laboral real, gasto,
  documento y tarea.
- Portal de trabajador con trabajos y checklist; equivalentes básicos por WhatsApp.
- Centro de control que impide automatizar pagos, transferencias, devoluciones,
  presentación fiscal, emisión definitiva y borrados irreversibles.
- Cerebro local ampliado para proyectos, equipo, documentos y gestoría.
- Gestoría con carpetas claras, originales, manifiesto, huella, versiones y eventos
  de preparación, aviso y descarga.
- Verificación final de la rama: 170 pruebas y 26 subpruebas verdes.

## No está en producción hasta que ocurra

1. Commit y push de `codex/operating-spine`.
2. PR revisada y fusionada.
3. Migraciones 22, 23 y 24 aplicadas en Railway/Postgres.
4. `/health`, `/ready` y smoke test autenticado verificados después del despliegue.

## Dependencias externas aún pendientes

- Credenciales y prueba real de WhatsApp Cloud API.
- Proveedor de IA opcional y prueba controlada de coste/privacidad.
- Stripe y conciliación real de pago.
- Certificado, entorno y validación oficial de la conexión AEAT/Veri*Factu.
- Revisión legal/fiscal profesional y pilotos con datos reales.
