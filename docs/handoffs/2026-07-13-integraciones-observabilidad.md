# Traspaso: integraciones y salud operativa por negocio

- **De → para:** Codex → siguiente agente revisor
- **Fecha:** 2026-07-13
- **Rama:** `codex/field-workflow`
- **Nivel de confianza del que entrega:** alto en código local; medio en proveedores
  reales porque faltan credenciales.
- **¿Requiere revisión antes de implementar?** no para continuar; sí antes de fusionar
  por ampliar el PR de campo con una migración adicional.

## 1. Contexto del producto

Noesis debe quitar ruido sin convertir al autónomo en administrador de un ERP. Este
bloque unifica conexiones y problemas operativos en Ajustes, pero mantiene WhatsApp,
la gestoría y la fiscalidad en sus flujos existentes.

## 2. Objetivo

Dar a cada negocio control visible sobre servicios externos y explicar si IA,
documentos y colas están funcionando, sin exponer secretos ni datos de otro negocio.

## 3. Estado actual

- Migración 27 crea `integration_settings` con modos explícitos.
- Las cuentas nuevas parten con IA externa desactivada; las heredadas conservan el
  comportamiento anterior hasta decidir.
- Chat, clasificación y extracción respetan la preferencia; el fallback local sigue.
- Revocar WhatsApp impide que salgan mensajes que aún estaban en cola.
- Ajustes muestra conexiones reales, futuras solicitudes y detalle operativo plegado.
- No existen todavía OAuth de calendario/banco ni cobro mercantil por enlace.

## 4. Decisiones

- No guardar credenciales por negocio en la tabla.
- No duplicar estados de WhatsApp, gestoría o Veri*Factu.
- No presentar interés en banca como permiso para mover dinero.

## 5. Mapa

- Datos: `src/noesis/migrations.py`, `src/noesis/db.py`.
- Control IA: `src/noesis/web/chat.py`, `src/noesis/agent.py`.
- Documentos: `src/noesis/adapters/extraction.py`,
  `src/noesis/documents/service.py`, `src/noesis/web/whatsapp.py`.
- API/UI: `src/noesis/web/routers/account.py`, `pages.py`, `ajustes.html`, `app.css`.
- Rutas: `GET /api/{business_id}/integrations` y
  `POST /api/{business_id}/integrations/{integration_key}`.

## 6. Riesgos y límites

- No confundir Stripe de suscripción de Noesis con cobro de facturas del autónomo.
- No permitir que una preferencia sustituya confirmación de pagos o impuestos.
- La salud local no reemplaza monitorización, alertas y restauración externas del P0.

## 7. Criterios verificados

- [x] Preferencias aisladas por `business_id`.
- [x] IA y extracción externa revocables sin apagar el cerebro local.
- [x] Error, latencia, documentos, correcciones y colas visibles por negocio.
- [x] Exportación y borrado RGPD incluyen `integration_settings`.
- [x] Suite local verde.
- [x] Servidor, Ajustes, API de integraciones, `/health` y `/ready` en 200.
- [ ] QA visual desktop/móvil; la sesión no tuvo un navegador capaz de alcanzar
  localhost. No confundir este bloqueo de herramienta con un fallo HTTP de Noesis.
- [ ] Smoke con proveedores reales.

## 8. Próximo paso

Completar QA visual de Ajustes, aplicar migración 27 en Postgres de ensayo y, tras
fusionar, abordar duplicados/HEIC/PDF escaneado y corrección masiva de documentos.
