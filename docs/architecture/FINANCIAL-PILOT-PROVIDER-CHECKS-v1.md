# Diseño de checks inocuos — propuestas no ejecutadas

`safe_check()` F permanece intacto y fail-closed. Ninguna propuesta siguiente
está implementada/certificada ni produce production_config_verified. No se ha
contactado cuenta/API real; sólo se consultó documentación pública de referencia.
Perfil mínimo expense web requiere **cero** providers; no significa legal readiness.

Para todos: autorización específica provider/tenant/entorno/operación/timeout;
allowlist host/TLS, redirects prohibidos, ningún retry de red por defecto, response
máximo acotado (64 KiB propuesto), no body/headers/tokens en logs. Evidencia futura
en F: attestation UUID/hash + actor/SV/código/schema/entorno/fecha/expiry y HMAC de
configuración/credencial; closed safe_check/check_reference_hash sólo tras verificar.
No conservar respuestas raw ni PII. No aprobar scope nuevo ni cambiar credenciales.
Una lectura de control no acredita delivery, fiscalidad ni production_observed.

| Provider | Operación candidata / método | Credencial y datos enviados | Respuesta / redacción | Riesgo / timeout propuesto | Límite |
|---|---|---|---|---|---|
| AEAT | **Sin endpoint autenticado inocuo validado** en el contrato actual | Ninguna llamada. Verificar localmente cadena/key/cert público sólo da local_verified | Sólo huella del certificado público y HMAC privado local | TLS/local no prueba aceptación/identidad productiva; ninguna red | SAFE_CHECK_UNIMPLEMENTED. No SOAP de suministro, cancelación ni factura cero. Una consulta fiscal puede enviar identidad/leer hechos y exige análisis/autorización separados. |
| Meta | GET `https://graph.facebook.com/{version}/{WABA-ID}/phone_numbers?fields=id` | Token existente de la conexión exacta, permiso de gestión existente; WABA ID técnico. Nunca access_token en URL | IDs de números para comprobar membership del PHONE_ID configurado; comparar en memoria, no persistir IDs/teléfonos ni paginar fuera de allowlist | Expone metadata de cuenta, rate limits/access logs; 10 s, sin sends/register/webhook changes | Candidato de lectura documentado; no prueba permiso de envío ni templates/delivery. No mintar attestation hasta implementar/probar verificador exacto. |
| Brevo | GET `https://api.brevo.com/v3/account` | api-key existente en header, sin cuerpo/destinatario | Metadata de cuenta incluye PII; permitir sólo validación en memoria y evidencia cerrada sin respuesta raw | Lectura de cuenta/consumo cuota/log de acceso; 10 s propuesto | Candidato; validar identidad/config de sender por separado si esta operación no las acredita. No POST smtp/email. |
| Gmail | GET `https://gmail.googleapis.com/gmail/v1/users/me/profile` | Access token existente y scopes compatibles ya concedidos; sin body. No renovar token ni ampliar scopes durante check | emailAddress/counts/historyId; descartar todo, comparar identidad en memoria sin registrarla | PII/cuota/OAuth; 20 s | gmail.send por sí solo **no** está en los scopes de este endpoint. Si falta scope compatible, SAFE_CHECK_UNIMPLEMENTED para esa configuración; no pedir scope amplio para pasar readiness. |
| SMTP | EHLO + STARTTLS + EHLO + QUIT, sin AUTH/MAIL/RCPT/DATA | Host/puerto configurado y hostname no-PII de checker; sin password | Capacidades/TLS públicos, sólo huella pública y estado cerrado | Conexión crea logs/cuota; 15 s | Prueba conectividad/TLS, no autentica la credencial ni acredita sender. AUTH no definido aquí como inocuo verificado: SAFE_CHECK_UNIMPLEMENTED para production_config_verified. |

Fuentes primarias: [colección oficial Meta](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api),
[Brevo GET account](https://developers.brevo.com/reference/get-account),
[Gmail users.getProfile y scopes](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/getProfile).
No se depende de respuestas de foros ni se prueban estos endpoints. Revisar versión,
permisos y semántica oficiales otra vez antes de implementar check futuro.

La producción real sigue sin attestations/production_observed/preflight externos
creados por esta entrega. No transformar estas URLs/diseños/documentos en evidencia
provider. Un fallo, timeout, scope faltante o respuesta ambigua bloquea; no enviar
comunicación/registro fiscal para demostrar acceso. Todos los efectos requieren G-LIVE
y autoridad financiera separadas, además de aprobación del provider check futuro.
