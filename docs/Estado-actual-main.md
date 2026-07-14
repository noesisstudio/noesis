# Estado actual de `main`

> Única fotografía viva del producto. Auditoría: 2026-07-14. Los pendientes viven
> únicamente en [[Tareas-vivas]]; los documentos de traspaso son históricos.

## Código fusionado en `origin/main`

- Commit auditado: `280a5cc` (PR #30).
- Esquema SQLite/Postgres: migración **27**.
- La columna proyecto → trabajo → fichaje → coste → borrador de factura está
  conectada. El cierre de campo, materiales, evidencias y conformidad no alteran el
  fichaje laboral append-only.
- Centro de control por negocio, preferencias de integración, salud operativa,
  memoria explicable y perfil de cliente corregible están fusionados.
- Emitir/enviar facturas, registrar pagos, transferencias, fiscalidad y borrados
  irreversibles permanecen bajo confirmación del autónomo.
- Última verificación publicada comunicada: Railway/Postgres aplicó las migraciones
  y `/ready` respondió 200. Esto no sustituye una nueva prueba tras cada despliegue.

## Cambio preparado en `codex/ai-first-hotfix`

- Corrige el `COALESCE` incompatible entre texto y timestamp en la ficha de proyecto
  y añade proyecto, ficha y campo al smoke de PostgreSQL.
- El onboarding recomienda IA avanzada desde el primer día, pero pide consentimiento
  explícito antes de enviar contenido a un proveedor externo.
- Enrutamiento: reglas locales → servicio privado OpenAI-compatible → IA externa
  autorizada. La caída o el límite de un nivel no apaga el producto local.
- Créditos externos mensuales por plan, reservados atómicamente y aislados por
  `business_id`. La IA privada no consume esos créditos.
- Estado de pruebas de esta rama: **182 pruebas y 26 subpruebas verdes**; smoke
  HTTP real en `/health`, `/ready`, onboarding, Ajustes, proyectos, detalle y campo.
  GitHub Actions aplicó migración 27/27 y pasó el smoke PostgreSQL ampliado.

## Capacidades que existen pero dependen de configuración externa

- WhatsApp dispone de webhook firmado, texto, audio, imagen/PDF, confirmaciones y
  outbox durable; falta validar el número y las plantillas reales de Meta.
- Stripe, email, Veri*Factu/AEAT, extracción avanzada y el proveedor de IA requieren
  credenciales, entorno o certificado reales.
- El adaptador de IA privada está construido, pero necesita un servicio de inferencia
  provisionado y evaluado; no incluye una GPU ni un modelo dentro del proceso web.

## Evidencia y límites

- «Construido» no significa «publicado»: después de cada fusión hay que confirmar
  despliegue, migración, smoke y flujo real afectado.
- No se promete cumplimiento fiscal definitivo, WhatsApp perfecto ni aprendizaje
  autónomo completo hasta validar con asesoría, auditoría y pilotos reales.
- Toda lectura y escritura operativa debe filtrar por `business_id`.
