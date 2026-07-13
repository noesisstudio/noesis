# Estado actual de `main`

> Auditoría: 2026-07-13. Distinguir siempre producción de ramas en revisión.

## En `origin/main` y producción

- Commit `4ba9946` (PR #27), esquema 24.
- 170 pruebas Python y 26 subpruebas verdes.
- Centro de control, proyectos conectados, trabajador/WhatsApp operativo y entregas
  versionadas a gestoría desplegados; `/health` y `/ready` respondieron 200.

## En `codex/field-workflow`, aún no fusionado

- Migración 25: materiales, notas, incidencias, fotos, cierre, firma/conformidad y
  factura borrador por trabajo.
- El parte de campo no modifica el fichaje legal. El cliente confirma o pide revisión
  desde su portal. Emitir/enviar sigue bajo control del autónomo.
- Los materiales alimentan el coste del proyecto una sola vez.
- Migración 26: preferencias confirmadas y perfil explicable de cliente con pagos,
  presupuestos, avisos y margen directo conocido.
- Rama verificada: 175 pruebas; QA desktop/móvil sin errores de consola.

## Dependencias externas pendientes

- Meta real, Stripe real, certificado/entorno AEAT, auditoría legal y de seguridad,
  restauración externa y piloto con 3-5 negocios.
