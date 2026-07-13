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
- Migración 27: preferencias de integración por negocio. Las cuentas nuevas parten
  con la IA externa desactivada; el cerebro local sigue disponible y las cuentas
  anteriores conservan su comportamiento hasta que el usuario decida.
- Ajustes unifica WhatsApp, IA, correo, Veri*Factu, gestoría y futuras conexiones,
  con incidencias por negocio, colas, latencia, documentos y correcciones.
- Rama verificada: 177 pruebas; QA de navegador pendiente para el nuevo centro.

## Dependencias externas pendientes

- Meta real, Stripe real, certificado/entorno AEAT, auditoría legal y de seguridad,
  restauración externa y piloto con 3-5 negocios.
