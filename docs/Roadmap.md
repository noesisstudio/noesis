# Roadmap

Principio rector: **no lanzar un MVP que falle**. Endurecer el núcleo antes de exponerlo.

## ✅ Hecho
- App web multipágina (FastAPI) con [[Arquitectura|sistema de diseño propio]].
- Apartados en profundidad: resumen, ingresos, costes, facturas, cobros, agenda,
  clientes, asistente (chatbot interno), ajustes.
- Cerebro local (gratis) + IA opcional. Ver [[Investigación]].
- [[Fiscalidad]] correcta: IVA (21/10/4) + IRPF + datos fiscales del negocio.
- Marca aplicada (verde bosque + teal + crema), iconos SVG propios, logo, móvil.
- **Login y seguridad**: contraseñas cifradas, sesiones, aislamiento por dueño.
- Informes CSV, alertas programadas (diaria/semanal).
- Suite de regresión del backend: aislamiento multiempresa, facturación idempotente,
  webhooks firmados, sesiones revocables y validación fiscal.
- **Fase 1 completa**: editar/borrar (clientes, facturas, gastos, trabajos),
  **PDF de factura** (fpdf2) con datos fiscales, validaciones de formularios.
- Alta SaaS en tres pasos, recorrido de activación hasta el primer cobro, eventos de
  producto internos y embudo operativo en administración.
- Posicionamiento alrededor del ciclo "del trabajo terminado al dinero cobrado",
  para autónomos y pequeños negocios de servicios (público amplio).
- Endpoints de salud y disponibilidad para despliegue (`/health` y `/ready`).
- Registro Veri*Factu nativo fase 1 en `main`: huella, QR, eventos, rectificativas
  y XML AEAT.
- Veri*Factu fase 2 en `codex/verifactu-fase2`: vectores oficiales, SOAP mTLS y
  cola durable; pendiente de revisión y prueba real con certificado AEAT.

## 🚧 Fase 1 — núcleo sólido (COMPLETA ✅)
- [x] Editar / borrar entidades (clientes, facturas, gastos, trabajos).
- [x] PDF de factura.
- [x] Validaciones de formularios.

## 🔌 Fase 2 — conectar lo real
- [x] Base de datos de producción (Postgres en Railway) + copias de seguridad
  verificadas (migración 8, restauración probada, S3 opcional).
- [x] Veri*Factu nativo fase 1 (registro local conforme a formato técnico, sin envío).
- [x] Veri*Factu fase 2 fusionada en `main` (migración 9): vectores oficiales AEAT,
  cliente SOAP mTLS, cola durable. Falta certificado digital y validar el entorno
  de pruebas antes de activar (trámite del founder).
- [ ] WhatsApp real (Meta Cloud API) — la cola durable ya está; faltan credenciales
  de Meta (verificación de empresa, clics del founder).
- [ ] Stripe real — el adaptador ya habla con Stripe; faltan las claves y los tres
  precios en Railway (clics del founder).
- [x] Despliegue 24/7 con HTTPS en **app.bynoesis.com** + marco legal completo
  (términos, privacidad, encargado del tratamiento, cookies, aviso legal).
- [x] Transcripción de audios (Whisper, instalación opcional).

## 💶 Cerrar el ciclo del cobro (siguiente en producto)
- [x] Datos de pago (IBAN/Bizum) en Ajustes, el PDF de la factura y el portal.
- [x] **Cobros parciales** (anticipo + resto) con ledger separado, estado derivado
  y métricas sobre el restante (migración 11 en `main`).
- [x] **Gasto por foto** con borrador extraído por Claude, confirmación obligatoria
  y documento vinculado (migración 12 en `main`).
- [x] Persecución de cobros automática por WhatsApp: opt-in por negocio, cadencia,
  restante, portal e idempotencia por escalón (migración 13, en `main`; el envío
  real sigue bloqueado hasta encender Meta).

## 🚀 Fase 3 — validar
- [ ] Piloto con 5-10 negocios de servicios antes de escalar.
- [ ] Medir semanalmente: alta → perfil → cliente → trabajo → factura → cobro.
- [ ] Entrevistar abandonos y activados; corregir el paso con mayor caída.
- [ ] Validar disposición a pagar y retención antes de ampliar sectores o funciones.
- [ ] Definir objetivos de activación, conversión, churn e ingreso por cuenta con
  datos reales del piloto.

## 🏗️ Plataforma por capas (aprobado 2026-07-07, en paralelo al piloto)
Visión "sistema operativo del autónomo", construida **por capas sobre lo que ya
existe** (criterio en [[Metodo-operativo-Fable]]; decisión en [[Decisiones]]).

### Capa B — MVP plataforma (extiende, no rediseña)
- [x] **Documentos inteligentes v1** (rama `claude/documentos-inteligentes`, PR #16):
  tipos, confianza, estados (pendiente→revisado→enviado a gestoría→validado),
  captura con cámara, lectura IA de imagen y PDF con revisión humana obligatoria.
- [x] **Facturas recibidas + proveedores** (migración 17) con detección
  emitida/recibida por NIF y presencia en Costes y en el ZIP de gestoría.
- [x] **Productos/servicios básico** (migración 18): catálogo con precio, coste,
  margen (solo si hay coste real), IVA, stock con aviso, y prefill al crear factura.
- [x] **Asistente contextual**: sabe en qué página está el usuario (botón «?» en
  la barra), la explica con datos reales y la IA hereda contexto e idioma.
- [x] **Vista Hoy ampliada**: el plan diario incluye documentos pendientes,
  recibidas por pagar, seguimientos de CRM y solicitudes de gestoría.
- [x] **CRM de leads** (migración 18, adelantado de la capa C): embudo con 8
  estados, seguimiento con fecha, valor estimado y conversión a cliente en 1 clic.
- [x] **Solicitudes de gestoría**: la gestoría pide documentación desde su enlace
  `/g/{token}` y el autónomo responde desde Documentos. Sin cuentas todavía.
- [x] **P&G del año con EBITDA estimado** en Análisis — sin inventar: «datos
  insuficientes» y lista de qué falta.
- [x] **Idioma persistente** (ES/CA/EN) en Ajustes: se guarda por negocio y la IA
  responde en él. La traducción completa de la interfaz queda para la capa C.
- [x] Partir `server.py` en routers por dominio.

### Capa C — V1
- [ ] Portal gestoría con cuentas y permisos multi-negocio (tras feedback real
  del flujo de solicitudes por enlace).
- [ ] Abstracción de canales (`ChannelProvider`) + Telegram según caso de uso
  confirmado (duda 2 de [[Preguntas-abiertas]]).
- [ ] Oportunidades y presupuestos conectados al CRM de leads.
- [x] Proyectos/obras: portada agregada y detalle progresivo con presupuesto vs.
  real, horas, equipo, gastos y margen por proyecto (migración 19).
- [x] Nivel de explicación de cuenta en Ajustes: claro, directo o detallado
  (migración 20); nunca se pregunta dentro de cada pantalla.
- [ ] Multiidioma completo de la interfaz (ES/CA/EN) — diseñar i18n antes de más UI.

### Capa D — V2
Ratios avanzados y EBITDA · stock y ventas por canal · aprendizaje de
preferencias (visible, borrable, con consentimiento) · WhatsApp Business
completo con plantillas · portal gestoría avanzado (modelos 303/130/390 con
revisión humana siempre) · automatizaciones profundas.

## 🌱 Más adelante
Optimización de rutas por zona · agente de voz telefónico · inventario y
  trabajadores · modelos 303/130 estimados.
