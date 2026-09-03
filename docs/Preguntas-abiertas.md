# Preguntas abiertas

> Solo contiene decisiones reales del founder. Los trabajos de conexión y QA viven
> en [[Tareas-vivas]] y [[Conectar-APIs]]. Cuando una pregunta se responde, se mueve
> a [[Decisiones]] con el porqué. Última revisión: **2026-09-03**.

## Decisiones que no bloquean la conexión inmediata

1. **Proveedor avanzado de IA para el piloto.** El cerebro local siempre permanece
   activo. Falta elegir qué respaldo se prueba primero con el mismo corpus:
   Anthropic, un proveedor OpenAI-compatible o un servicio privado. Criterio por
   defecto: calidad con herramientas y estabilidad antes que el precio teórico;
   presupuesto y consentimiento por negocio obligatorios.

2. **Idioma completo de la interfaz.** El asistente ya conserva ES/CA/EN, pero la UI
   no está internacionalizada entera. Propuesta: mantener la interfaz española en el
   piloto y adelantar i18n solo si un cliente real lo exige para usar o comprar.

3. **Voz en el plan Premium.** El recepcionista telefónico está diseñado pero no
   construido. Antes de prometer minutos incluidos hay que validar coste, demanda y
   margen con llamadas reales. Propuesta: beta cerrada o add-on hasta tener datos.

## Decisiones que bloquean la constitución y el primer cobro

Contexto y consecuencias de cada una en [[Constitucion-y-primer-euro]].

4. **Forma jurídica y empresa de eventos.** ¿La empresa de eventos que ya tienes es
   S.L. o eres autónomo? Si es S.L., ampliar su objeto social evita constituir y
   verifica mejor en Meta, a cambio de facturar con esa razón social y compartir
   responsabilidad patrimonial. Propuesta por defecto: S.L. nueva antes de pedir la
   verificación de empresa en Meta.

5. **Entidad con la que se verifica Meta.** Determina si la verificación arranca al
   tener NIF definitivo o puede pedirse ya con la sociedad existente. Cambiar de
   entidad después obliga a rehacer la verificación y a reconceder los WABA.

6. **Alcance Veri\*Factu durante el piloto.** Noesis es productor de un sistema
   informático de facturación y la remisión a la AEAT está construida pero no
   validada externamente. Dos caminos: completar la validación técnica y publicar la
   declaración responsable, o declarar explícitamente que el módulo no se ofrece como
   sistema Veri\*Factu durante el piloto. Requiere criterio de asesoría fiscal.

## Decisiones aplazadas por evidencia

- Sincronización bidireccional de calendario: decidir tras probar el ICS actual.
- PSD2 y cobro por enlace: decidir tras validar la conciliación CSV y el ciclo de
  cobro con el piloto.
- Telegram: solo si una cohorte real no puede operar por WhatsApp/web.
- Personalización profunda por sector: después de observar patrones repetidos en
  varios clientes, sin cerrar de antemano el público a fontanería u otro oficio.

## Ya resuelto — no volver a preguntar

- `server.py` ya está dividido en routers por dominio.
- Facturas recibidas y proveedores tienen entidades propias.
- WhatsApp se enciende para el piloto en cuanto Meta y las plantillas pasen QA; ya
  no es una decisión de producto, sino una tarea P0.
- El piloto inicial es de 3-5 negocios de servicios y no exige un sector cerrado.
- Las transferencias, pagos, envíos sensibles, emisiones y acciones fiscales siempre
  requieren confirmación específica del autónomo.
- Google OAuth, SMTP, Stripe, Meta y AEAT no se consideran disponibles por tener
  código: necesitan credenciales y prueba externa completa.
- Holded no se conecta: la facturación y Veri*Factu son desarrollo propio.
- Stripe mantiene el catálogo 29/49/99 EUR más IVA y Checkout solicita dirección,
  NIF y `automatic_tax`; falta validar el resultado real en Stripe test/live, no una
  decisión de producto ni código por diseñar.
- La gestoría ya dispone de cuenta profesional multiempresa, permisos explícitos,
  cartera, expedientes, documentos, fiscalidad y solicitudes. MFA y la validación
  con 2-3 despachos siguen siendo tareas de piloto, no preguntas de arquitectura.
