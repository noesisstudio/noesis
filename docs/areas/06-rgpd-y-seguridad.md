# 06 · RGPD y seguridad

> Léela antes de tocar datos personales, bajas, exportaciones, consentimientos,
> cookies, analítica, permisos, sesiones, proveedores nuevos o registros de
> seguridad. Figura 6 del [mapa visual](../02-tecnico/Mapa-Bynoesis.html).
> No es asesoramiento jurídico; lo legal está en [`05-legal-y-rgpd`](../05-legal-y-rgpd/).

## Qué hace

Bynoesis tiene **dos papeles**. Es **responsable** de sus propias cuentas (titulares,
cuotas, web y formularios) y **encargado** de lo que cada autónomo guarda (sus
clientes, facturas y documentos): ahí el responsable es el autónomo y Bynoesis solo
trata según sus instrucciones. El código protege el dato en todo su recorrido: se
recoge con permiso, se guarda aislado por negocio, se usa primero en el servidor,
solo se comparte con encargados declarados y, al darse de baja, se borra salvo lo
que la ley obliga a conservar.

## Esquema

```text
1 Se recoge ── casilla con versión de textos (LEGAL_DOCUMENT_VERSION) · cookies y
│              Analytics solo tras «Aceptar» · IA externa solo con permiso del negocio
2 Se guarda ── Railway, Ámsterdam · todo con business_id · PBKDF2 · tokens cifrados
│              (secret_box) · documentos validados y, si se configura, antivirus
3 Se usa ───── reglas locales primero · a la IA externa, solo el trozo necesario
4 Se comparte  encargados de RGPD-Matriz-proveedores (Railway, Meta, Brevo, Groq,
│              Anthropic, Stripe, Google…)
5 Derechos ─── registro de solicitudes: acceso, rectificación, supresión, limitación,
│              portabilidad, oposición y baja · exportación por negocio y por cliente
6 Fin ──────── delete_business_cascade si no hay nada protegido; si hay facturas
               emitidas o fichajes → solicitud de baja con conservación legal
De fondo: bitácora de seguridad encadenada · copias verificadas · permisos de soporte
con caducidad · procedimiento de brechas (72 h)
```

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `db.py` | `create_privacy_request`, `list_privacy_requests`, `update_privacy_request`, `export_business_data`, `delete_business_cascade`, `record_security_event`, `create_support_grant`, `revoke_support_grant`, `set_whatsapp_contact_consent` |
| `web/routers/account.py` | `/api/{id}/export`, `/api/{id}/clients/{client_id}/export`, `/b/{id}/account/delete` (pide contraseña y «BORRAR») |
| `web/routers/admin.py` | `/admin/privacidad`: seguimiento de solicitudes, siempre con nota |
| `security_center.py` | `build_security_report()`: el parte de seguridad de `/admin` (copias, accesos, bitácora) |
| `web/auth.py`, `web/deps.py` | Contraseñas PBKDF2, sesiones firmadas, cookie `__Host-` en producción, límites de intentos, guardias por negocio |
| `web/server.py` | CSP por página, `X-Robots-Tag`, hosts permitidos, cabeceras de aislamiento |
| `secret_box.py` | Cifrado de credenciales de terceros con clave derivada de `NOESIS_SECRET` |
| `documents/validation.py`, `documents/malware.py` | Contenido real de archivos y ClamAV opcional antes de guardar |
| `config.py` | `LEGAL_DOCUMENT_VERSION`, `NOESIS_GA_MEASUREMENT_ID`, datos legales publicados |
| `web/static/public-analytics.js` | Aviso de cookies; Google Analytics solo tras aceptar |

## Reglas que no se rompen

1. **Aislamiento por negocio** en ruta y en `db.py` (ver [01](01-vision-general.md)).
   Una fuga entre negocios es el peor fallo posible.
2. **Nada de terceros sin permiso.** Analytics solo tras «Aceptar», revocable desde el
   pie y `/cookies`; la CSP solo abre Google en rutas públicas y nunca en zonas con
   datos de clientes. La IA externa solo si el negocio la activó.
3. **Minimización.** A la IA externa va el fragmento que lo local no resolvió; al
   correo entrante no se le guarda cuerpo, asunto ni remitente; los logs no llevan
   query strings ni contenido personal.
4. **La bitácora de seguridad es append-only y encadenada.** No lleva contenido
   operativo ni datos de contacto. Nada la reescribe.
5. **La baja nunca borra lo que la ley obliga a guardar.** Facturas emitidas y
   fichajes se conservan; se registra una solicitud `account_closure` con
   `retention_required`. La purga automática espera a unos plazos validados por
   abogado.
6. **Cambiar el estado de una solicitud no borra datos** como efecto secundario.
7. **Soporte sin suplantación.** El founder no se concede acceso: lo concede el
   titular, con alcance y caducidad, y queda auditado.
8. **Un proveedor nuevo no recibe datos reales solo porque exista una clave.** Antes:
   finalidad, rol, DPA, región, transferencias, retención y texto público en
   [`RGPD-Matriz-proveedores`](../05-legal-y-rgpd/RGPD-Matriz-proveedores.md).
9. **Los textos legales tienen versión.** Si cambian, sube `LEGAL_DOCUMENT_VERSION`.

## Estado real (28-sep-2026)

- En código y funcionando: aislamiento, registro de solicitudes (esquema 55),
  exportación, baja con conservación, bitácora encadenada, permisos de soporte,
  consentimiento de cookies, copias diarias con simulacro.
- Pendiente fuera del código: firmar el DPA de Railway y archivar el de cada
  proveedor, revisión de un abogado de textos y plazos, copia externa fuera de
  Railway, alerta 24/7 e incidencias de guardia.

## Pruebas que lo cubren

`test_account_deletion`, `test_security_hardening`, `test_security_operations`,
`test_secrets_gate`, `test_release_configuration`, `test_public_marketing`
(consentimiento de Analytics), `test_backend` (aislamiento entre negocios),
`test_backups`.

## Al revisar código de esta zona

- [ ] ¿Una tabla nueva con datos de un negocio está en `delete_business_cascade` y en
      `export_business_data`? La prueba de borrado lo exige para el borrado; la
      exportación hay que comprobarla a mano.
- [ ] ¿Algún dato personal va a un proveedor que no esté en la matriz?
- [ ] ¿Algún log, evento o mensaje de error lleva correos, teléfonos, NIF o contenido?
- [ ] ¿Un script de terceros nuevo carga sin consentimiento o fuera de la CSP?
- [ ] ¿Una acción de soporte o administración queda en `record_security_event`?
- [ ] ¿Algún secreto nuevo se guarda sin cifrar o se imprime?

## Dudas frecuentes

- **¿Por qué no se puede borrar todo al darse de baja?** La normativa fiscal y laboral
  obliga a conservar facturas y fichajes. Se borra lo demás y se registra.
- **¿Dónde están los datos?** Railway, región `europe-west4` (Ámsterdam). Railway
  está certificado en el Marco de Privacidad UE-EE. UU.

## Más detalle

[`RGPD-estado-y-plan`](../05-legal-y-rgpd/RGPD-estado-y-plan.md) ·
[`RGPD-Registro-actividades`](../05-legal-y-rgpd/RGPD-Registro-actividades.md) ·
[`RGPD-Procedimiento-derechos-y-bajas`](../05-legal-y-rgpd/RGPD-Procedimiento-derechos-y-bajas.md) ·
[`RGPD-Procedimiento-brechas`](../05-legal-y-rgpd/RGPD-Procedimiento-brechas.md) ·
[`Seguridad-operativa`](../04-seguridad-y-datos/Seguridad-operativa.md) ·
[`Servidores-y-residencia-de-datos`](../04-seguridad-y-datos/Servidores-y-residencia-de-datos.md)
