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
- [ ] Base de datos de producción (Postgres/Supabase) + copias de seguridad.
- [x] Veri*Factu nativo fase 1 (registro local conforme a formato técnico, sin envío).
- [x] Veri*Factu fase 2: cliente y remisión automática implementados; falta
  configurar un certificado y validar el entorno de pruebas antes de producción.
- [ ] WhatsApp real (Meta Cloud API) — requiere verificación de empresa (founder).
- [ ] Despliegue 24/7 con HTTPS en **bynoesis.com** + RGPD (privacidad/términos).
- [x] Transcripción de audios (Whisper, instalación opcional).

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
