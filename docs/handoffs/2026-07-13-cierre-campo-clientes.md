# Traspaso — cierre de campo y clientes explicables

- Rama `codex/field-workflow`, base `origin/main` `4ba9946`.
- Migraciones 25 `cierre_trabajo_campo` y 26 `preferencias_cliente`.
- Flujo: parte del trabajador → trabajo hecho → borrador si hay importe → cliente
  confirma o pide revisión → autónomo decide emisión y envío.
- Materiales de campo entran en proyecto por el trabajo; no duplicar en entradas.
- Perfil: observado (`client_insights`) frente a confirmado (`client_preferences`).
- QA: 175 pruebas y navegador desktop/móvil sin errores de consola.
- Siguiente: centro de integraciones y observabilidad por negocio.
