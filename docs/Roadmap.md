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
- [ ] Stripe real — el adaptador ya habla con Stripe; faltan las claves y los dos
  precios en Railway (clics del founder).
- [x] Despliegue 24/7 con HTTPS en **app.bynoesis.com** + marco legal completo
  (términos, privacidad, encargado del tratamiento, cookies, aviso legal).
- [x] Transcripción de audios (Whisper, instalación opcional).

## 💶 Cerrar el ciclo del cobro (siguiente en producto)
- [x] Datos de pago (IBAN/Bizum) en Ajustes, el PDF de la factura y el portal.
- [x] **Cobros parciales** (anticipo + resto) con ledger separado, estado derivado
  y métricas sobre el restante (migración 11 en `codex/cobros-parciales`, pendiente
  de revisión y fusión).
- [ ] **Gasto por foto** (OCR sobre el módulo de documentos existente).
- [ ] Persecución de cobros automática por WhatsApp (bloqueada por Meta).

## 🚀 Fase 3 — validar
- [ ] Piloto con 5-10 negocios de servicios antes de escalar.
- [ ] Medir semanalmente: alta → perfil → cliente → trabajo → factura → cobro.
- [ ] Entrevistar abandonos y activados; corregir el paso con mayor caída.
- [ ] Validar disposición a pagar y retención antes de ampliar sectores o funciones.
- [ ] Definir objetivos de activación, conversión, churn e ingreso por cuenta con
  datos reales del piloto.

## 🌱 Más adelante
Optimización de rutas por zona · agente de voz telefónico · inventario y
  trabajadores · modelos 303/130 estimados.
