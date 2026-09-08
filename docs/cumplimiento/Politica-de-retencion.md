# Política de retención y supresión

> - Creado: 2026-09-08 · Última revisión: 2026-09-08 · Próxima revisión: 2027-03-08
> - Responsable: founder (Xavier).
> - Principio rector: art. 5.1.e RGPD. Un dato que no tiene fecha de caducidad
>   escrita es un dato que se conserva indefinidamente por descuido.

## 1. Tabla de retención

| Dato | Plazo | Fundamento | Al vencer |
|---|---|---|---|
| Cuenta de usuario y credenciales | Vida de la cuenta + 12 meses | Contrato, art. 6.1.b | Supresión |
| Facturas emitidas por el negocio | 4 años desde el fin del plazo de declaración; 6 años como libro mercantil | LGT arts. 66-70; Código de Comercio art. 30 | Bloqueo y después supresión |
| Facturas de la suscripción de Noesis | 6 años | Código de Comercio art. 30 | Supresión |
| Registros de jornada (fichajes) | 4 años | Art. 34.9 ET (RD-ley 8/2019) | Supresión |
| Bienes de inversión, si los hubiera | 10 años | Ley 37/1992 del IVA | Supresión |
| Documentos y adjuntos | Instrucción del responsable; por defecto, vida de la cuenta | Contrato | Supresión real en disco |
| Contenido de mensajes de WhatsApp | 90 días | Minimización; el resultado de entrega sí se conserva | Purga del cuerpo |
| Registros de aplicación (logs) | 30 días | Interés legítimo, seguridad | Rotación del proveedor |
| Bitácora `security_events` | 24 meses | Art. 32 como prueba de diligencia | Exportación y purga |
| Solicitudes de acceso no convertidas | 12 meses | Interés legítimo | Supresión |
| Copias de seguridad | 14 diarias + 8 semanales | Continuidad, art. 32 | Sobrescritura por ciclo |
| Consentimientos (IA, comunicaciones) | Mientras estén vigentes + 4 años | Prueba del art. 7.1 | Supresión |

## 2. Cómo se ejecuta una supresión

1. **Sistemas vivos, inmediatamente.** El borrado de un cliente purga sus
   documentos y sus datos personales, y conserva únicamente lo que una obligación
   legal impide borrar: las facturas emitidas y los fichajes. El nombre queda
   sustituido por una etiqueta neutra, no se conserva identificado.
2. **Bloqueo, no conservación libre.** Lo que se conserva por obligación legal
   queda bloqueado en el sentido del art. 32 LOPDGDD: solo puede usarse para
   atender a la Administración, jueces y tribunales durante el plazo de
   prescripción. No entra en informes, ni en agregados, ni en la IA.
3. **Copias de seguridad.** El dato suprimido permanece en las copias hasta que el
   ciclo las sobrescribe (máximo ~2 meses). Durante ese tiempo está bloqueado: solo
   se accedería restaurando un desastre. Si se restaura una copia anterior a una
   supresión, **reaplicar la supresión inmediatamente después de restaurar** es un
   paso obligatorio del runbook, no una recomendación.
4. **Evidencia.** Cada supresión a petición de un interesado se anota en
   [`Registro-de-evidencias`](Registro-de-evidencias.md) con fecha, alcance y quién
   la ejecutó. Nunca se anota el dato suprimido.

## 3. Lo que impide borrar

El código bloquea la baja completa cuando existen facturas emitidas o registros de
jornada dentro de plazo, y ofrece en su lugar una baja con conservación legal. Es
correcto y debe seguir así: borrar una factura emitida no es un derecho del
cliente, es una infracción tributaria.

Al comunicárselo al interesado hay que explicarlo con esas palabras: no se le
deniega el derecho, se le informa de que parte de sus datos se conservan
bloqueados por obligación legal y durante cuánto tiempo.
