# Matriz de proveedores y transferencias

Versión interna: 2026-09-03. Esta matriz diferencia lo comprobado en código de
lo que todavía exige una evidencia contractual o del panel de producción.

| Proveedor | Función | Rol habitual | Datos posibles | Activación | Evidencia requerida antes de datos reales |
|---|---|---|---|---|---|
| Railway | Web, PostgreSQL y volumen | Encargado | Cuenta y contenido operativo completo | Siempre en producción | DPA ejecutado; región de web, BD y volumen; lista de subencargados; medidas y transferencias |
| Google Cloud / Cloudflare | Infraestructura usada por Railway | Subencargados de Railway | Según la prestación de Railway | Indirecta | Lista vigente de Railway y mecanismo de transferencia aplicable |
| Brevo o SMTP identificado | Correo transaccional | Encargado | Destinatario, asunto, cuerpo y adjuntos necesarios | Si se configura | DPA, región, remitente autenticado y nombre publicado |
| Meta Platforms | WhatsApp Business | Según servicio/operación | Teléfono, mensajes, archivos y metadatos de entrega | Solo si el negocio conecta WhatsApp | Condiciones, DPA, plantillas, base de las comunicaciones y transferencias |
| Anthropic | Ayuda avanzada | Encargado/subencargado según contrato | Fragmento mínimo de consulta no resuelta | Por negocio y con activación | Contrato/DPA, región, retención y configuración de no entrenamiento aplicable |
| Proveedor OpenAI-compatible | Ayuda avanzada alternativa | Por determinar | Fragmento mínimo de consulta no resuelta | Solo con variables completas | Razón social y región obligatorias; DPA y transferencias. No activar un endpoint anónimo |
| Groq | Transcripción de voz | Encargado/subencargado según contrato | Archivo de audio y resultado transcrito | Solo si se configura voz | DPA/condiciones, retención, transferencias y texto público |
| Stripe | Suscripción, pago, impuestos y fraude | Encargado y responsable independiente según operación | Titular, contacto, pago, factura y señales antifraude | Si se cobra | DPA, cuenta verificada, webhooks, portal, política y reparto de roles |
| Google | OAuth/OpenID Connect | Responsable/encargado según operación | Email, nombre e identificador de cuenta | Solo si la persona elige Google | Proyecto verificado, pantalla de consentimiento, privacidad/términos y credenciales restringidas |
| Cal.com | Reserva externa | Servicio independiente para la reserva | Datos que introduce quien reserva | Solo al abrir el enlace externo | Política enlazada y cuenta configurada. No se incrusta en Noesis |
| Proveedor S3 | Copia externa | Encargado | Base, metadatos y archivos cifrados | Solo con configuración completa | Nombre, DPA, residencia contractual, región de firma, cifrado, versionado, retención y restauración probada |

## Regla de alta de un proveedor

Ningún proveedor nuevo puede recibir datos reales solo porque exista una clave.
Antes deben constar: propietario interno, finalidad, minimización, rol, DPA o
condiciones, subencargados, región/residencia, mecanismo de transferencia,
retención, procedimiento de salida, texto público y prueba de fallo cerrado.

## Estado que debe comprobar el founder

- [ ] Railway DPA ejecutado y copia archivada.
- [ ] Región de web, PostgreSQL y volumen demostrada con capturas fechadas.
- [ ] Proveedor de correo y región reflejados en variables legales.
- [ ] DPA/condiciones de Stripe, Meta, Google y proveedores de IA archivados.
- [ ] Copia externa: proveedor, residencia y restauración real comprobados.
- [ ] Una revisión trimestral detecta cambios de subencargados o condiciones.
