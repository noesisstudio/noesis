# Preguntas abiertas

> Dudas que necesitan respuesta del founder (o criterio de Opus) antes de
> implementar. Cuando una se responde, se mueve a [[Decisiones]] con su porqué.
> Las tareas puramente operativas del founder están al final.
> Última actualización: **2026-07-07**.

## Requieren decisión de negocio

1. **Catalán en el MVP.** El 2026-07-07 el founder autorizó el plan general, que
   aplaza i18n a V1 salvo que el catalán sea imprescindible para vender. Queda por
   confirmar explícitamente: ¿hay clientes del piloto que lo exijan? Si sí, la
   arquitectura i18n debe diseñarse **antes** de crear más pantallas.
2. **Telegram: ¿para quién?** Como canal del autónomo compite con la cuña WhatsApp
   (el cliente objetivo vive en WhatsApp). Como canal interno founder/gestoría es
   barato y rápido de montar. Pendiente: confirmar el caso de uso antes de
   construir la abstracción de canales con Telegram como primer proveedor extra.
3. **Gestoría interactiva: ¿antes o después del feedback del piloto?** El paquete
   ZIP actual (`/g/{token}`) resuelve el 80 % sin cuentas ni permisos nuevos. El
   portal con rol gestoría (multi-negocio) es un cambio de modelo de permisos
   serio. Propuesta vigente: esperar al feedback de 2-3 gestorías reales sobre el
   ZIP antes de diseñar el rol. PROPUESTA, NO CONFIRMADO.
4. **Precio y momento de WhatsApp Business real.** Meta cobra por conversación;
   encenderlo tiene coste variable por cliente. ¿Se enciende con el piloto o
   cuando haya ingresos? (El código está listo; es decisión de gasto.)

## Técnicas, con propuesta por defecto

5. **¿Cuándo partir `server.py` (~70 rutas) en routers?** Propuesta: primera
   tarea técnica tras el próximo hito de producto, en rama propia, sin mezclarla
   con features. Es mecánica pero toca todo; no debe convivir con otra rama
   grande abierta.
6. **Facturas recibidas: ¿entidad nueva o extensión de `expenses`?** Propuesta:
   entidad propia `received_invoices` vinculada a proveedor y documento, porque
   su ciclo (recepción→deducción→pago) no es el de un gasto de ticket. Decidir al
   diseñar la migración del módulo de documentos inteligentes.
7. **Proveedores: ¿tabla propia o `clients` con rol?** Propuesta: tabla propia
   (los campos y consultas difieren). Se decide junto con la 6.

## Operativas del founder (no técnicas, bloquean el piloto)

- Poner `ANTHROPIC_API_KEY` y variables de WhatsApp en Railway.
- Verificar el número de WhatsApp en Meta y aprobar las plantillas.
- Certificado digital de pruebas AEAT para validar Veri*Factu fase 2.
- Claves de Stripe y los dos precios en Railway.
- Reclutar 3-5 autónomos del mismo perfil para el piloto.
