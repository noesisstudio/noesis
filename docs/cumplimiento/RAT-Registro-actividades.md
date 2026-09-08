# Registro de actividades de tratamiento (art. 30 RGPD)

> - Creado: 2026-09-08 · Última revisión: 2026-09-08 · Próxima revisión: 2027-03-08
> - Responsable: founder (Xavier). Sin DPO designado; ver criterio en § 4.
> - Obligación: art. 30 RGPD. Es exigible aunque la empresa tenga menos de 250
>   personas, porque el tratamiento no es ocasional e incluye datos de trabajadores.

## 1. Identificación

| Campo | Valor |
|---|---|
| Responsable / encargado | `NOESIS_LEGAL_NAME` (pendiente de fijar en producción) |
| NIF | `NOESIS_LEGAL_NIF` |
| Domicilio | `NOESIS_LEGAL_ADDRESS` |
| Contacto en materia de datos | `NOESIS_LEGAL_EMAIL` |
| Delegado de Protección de Datos | No designado. Ver § 4 |

Estos cuatro campos bloquean el alta pública en producción hasta estar completos:
es una condición ya implementada en el código, no una promesa.

## 2. Tratamientos en los que Noesis es RESPONSABLE

Datos de los propios usuarios de la plataforma: quien contrata y quien administra.

### 2.1 Gestión de cuentas y acceso

| | |
|---|---|
| Finalidad | Alta, autenticación, recuperación de contraseña, segundo factor y control de sesión |
| Interesados | Personas titulares o usuarias de una cuenta de negocio o de gestoría |
| Categorías | Nombre, email, teléfono, contraseña derivada (PBKDF2), secreto TOTP, marcas de tiempo de sesión, identificador de Google si se usa OAuth |
| Base legal | Art. 6.1.b (ejecución del contrato) |
| Cesiones | Google (solo si el usuario elige OAuth) |
| Transferencias | Ver [`Subencargados-y-transferencias`](Subencargados-y-transferencias.md) |
| Conservación | Vida de la cuenta + 1 año; después, supresión o seudonimización |
| Medidas | Cookie `__Host-` firmada, rotación tras login, caducidad por inactividad, límite persistente de intentos, bitácora append-only |

### 2.2 Facturación de la suscripción

| | |
|---|---|
| Finalidad | Cobro del servicio, gestión de planes y obligaciones contables |
| Interesados | Clientes de Noesis |
| Categorías | Identidad, NIF, dirección de facturación, plan, identificadores de Stripe. **Nunca datos de tarjeta**: los trata Stripe |
| Base legal | Art. 6.1.b y art. 6.1.c (obligación contable y fiscal) |
| Conservación | 6 años (art. 30 Código de Comercio) / 4 años de prescripción tributaria, el que sea mayor |
| Medidas | Webhook firmado e idempotente; sin almacenamiento de medios de pago |

### 2.3 Solicitudes de acceso y soporte

| | |
|---|---|
| Finalidad | Atender el formulario público de solicitud y el soporte |
| Interesados | Quien solicita acceso o escribe a soporte |
| Categorías | Nombre, email, actividad, mensaje libre |
| Base legal | Art. 6.1.f (interés legítimo en atender una solicitud propia del interesado) |
| Conservación | 12 meses desde el cierre si no hay contratación |
| Medidas | Buzón dedicado (`NOESIS_REQUESTS_EMAIL`), separado del administrativo |

### 2.4 Seguridad y trazabilidad

| | |
|---|---|
| Finalidad | Detectar abuso, investigar incidentes y probar la diligencia del art. 32 |
| Interesados | Usuarios de la plataforma |
| Categorías | Tipo de evento, severidad, área, identificadores internos, `request_id`, metadatos escalares acotados. Se descartan por diseño claves de email, teléfono, IP, token, secreto, contraseña, fichero, documento, mensaje y cuerpo |
| Base legal | Art. 6.1.f, con art. 32 como fundamento del interés legítimo |
| Conservación | 24 meses |
| Medidas | Tabla `security_events` con cadena de hashes y triggers que impiden UPDATE y DELETE |

## 3. Tratamientos en los que Noesis es ENCARGADO

Datos que cada negocio cliente sube. El responsable es el negocio; Noesis actúa
únicamente conforme a sus instrucciones, formalizadas en el DPA publicado en
`/encargado-tratamiento`.

| Tratamiento | Interesados | Categorías | Conservación |
|---|---|---|---|
| Agenda, clientes y proyectos | Clientes y contactos del negocio | Identidad, contacto, dirección, historial de trabajos | Instrucción del responsable; borrado en cascada al purgar cliente, salvo conservación fiscal |
| Facturación y cobros | Clientes del negocio | Identidad fiscal, NIF, importes, estado de cobro, IBAN | Retención fiscal: ver [`Politica-de-retencion`](Politica-de-retencion.md) |
| Documentos y OCR | Terceros que aparezcan en los documentos | Contenido libre: facturas, contratos, partes, fotos | Instrucción del responsable |
| Fichajes y registro de jornada | Trabajadores del negocio | Identidad, horas de entrada y salida, ubicación si se activa | **4 años** (art. 34.9 ET) |
| Mensajería WhatsApp | Clientes del negocio | Teléfono, contenido de los mensajes, metadatos de entrega | Contenido purgado a los 90 días; se conserva el resultado |
| Asistente con IA | Quien aparezca en el texto consultado | Solo el contenido no resuelto localmente | No se almacena en el proveedor más allá de su política; requiere consentimiento del negocio |

Advertencia registrada: los documentos y los partes de trabajo pueden contener
datos del art. 9 (salud) sin que Noesis pueda impedirlo técnicamente. El DPA
instruye al cliente a no subirlos. Riesgo asumido y anotado en
[`Analisis-riesgos-y-EIPD`](Analisis-riesgos-y-EIPD.md).

## 4. Delegado de Protección de Datos

No se designa DPO. Justificación escrita, por si se pregunta: el art. 37.1 RGPD y
el art. 34 LOPDGDD lo exigen cuando hay observación habitual y sistemática a gran
escala o tratamiento a gran escala de categorías especiales. Noesis trata datos de
un número reducido de negocios, no hace perfilado ni observación sistemática de
personas y no trata categorías especiales de forma deliberada.

**Esta conclusión se revisa** cuando se supere el centenar de negocios activos, si
se incorpora perfilado o scoring, o si el tratamiento de fichajes con geolocalización
pasa a ser continuo. Hasta entonces, el contacto en materia de datos es el founder.

## 5. Revisión

Se revisa este registro cuando cambie una finalidad, se añada un subencargado, se
incorpore una categoría de datos nueva o se modifique una base legal. Como mínimo,
cada seis meses. Cada revisión se anota en
[`Registro-de-evidencias`](Registro-de-evidencias.md).
