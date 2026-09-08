# Registro de actividades de tratamiento de Bynoesis

Versión interna: 2026-09-03. Propietario operativo: dirección de Bynoesis.

Este registro describe el producto real. Debe completarse con la razón social,
los contratos firmados, las regiones verificadas en producción y los plazos que
valide el asesor jurídico antes de abrir el alta pública. No sustituye esa revisión.

## 1. Bynoesis como responsable: cuenta y relación comercial

| Campo | Descripción |
|---|---|
| Finalidades | Gestionar solicitudes de acceso, alta, autenticación, suscripción, cobro, soporte, comunicaciones transaccionales, seguridad y ejercicio de derechos. |
| Interesados | Solicitantes, titulares y usuarios autorizados de las cuentas. |
| Datos | Identificación y contacto; negocio y configuración; datos fiscales de la cuenta; referencias de Stripe; consentimientos; soporte; eventos de seguridad; solicitudes de privacidad. Bynoesis no almacena el número completo de tarjeta. |
| Base jurídica | Medidas precontractuales y contrato; obligaciones legales; interés legítimo ponderado para seguridad y prevención de abuso. |
| Destinatarios | Railway; proveedor de correo; Stripe; Google si se usa OAuth; Meta si se conecta WhatsApp; Cal.com solo cuando la persona abre el enlace y reserva; autoridades cuando exista obligación legal. |
| Transferencias | Dependen de cada proveedor y configuración. Documentar DPF, decisión de adecuación o cláusulas tipo aplicables en la matriz de proveedores. |
| Conservación | Cuenta durante la relación y cierre; facturación propia durante el plazo legal; seguridad, soporte y derechos durante el tiempo necesario para atenderlos y acreditar su gestión. La tabla exacta debe validarla el asesor. |
| Seguridad | HTTPS, contraseñas con hash y sal, sesiones firmadas, aislamiento por `business_id`, MFA para gestorías, límites de acceso, auditoría encadenada, copias verificadas y acceso de soporte temporal y acotado. |
| Origen | La propia persona, el uso de Bynoesis y los proveedores de identidad/pago que ella inicia. |

## 2. Bynoesis como responsable: seguridad y continuidad

| Campo | Descripción |
|---|---|
| Finalidad | Detectar accesos abusivos, investigar incidentes, restaurar el servicio y demostrar actuaciones críticas. |
| Interesados/datos | Usuarios y administradores; identificadores internos, tipo de evento, fecha, área, resultado y metadatos mínimos. La bitácora filtra correos, teléfonos, IP, mensajes, documentos y secretos. |
| Base jurídica | Interés legítimo en proteger el servicio y obligaciones de seguridad del RGPD. |
| Destinatarios | Personal autorizado y proveedores de infraestructura estrictamente necesarios. |
| Conservación | Según la tabla interna de conservación y defensa de responsabilidades; pendiente de plazo definitivo validado. |
| Seguridad | Registro append-only encadenado, permisos administrativos, minimización de metadatos y pruebas de integridad. |

## 3. Bynoesis como encargado: operación del negocio cliente

| Campo | Descripción |
|---|---|
| Responsables | Cada autónomo, empresa o gestoría que contrata Bynoesis respecto de los datos que introduce de terceros. |
| Categorías de tratamientos | Agenda y trabajos; CRM; clientes y proveedores; proyectos; presupuestos; facturas, cobros y gastos; documentos y OCR; comunicaciones por web, email y WhatsApp; equipo y jornada; preparación para gestoría. |
| Interesados | Clientes finales, contactos, proveedores y trabajadores del negocio cliente. |
| Datos | Identificación, contacto, NIF y dirección cuando proceda; información económica y contractual; trabajos y citas; documentos; comunicaciones; registros de jornada. No se buscan categorías especiales. |
| Instrucciones | Contrato de encargado, configuración de la cuenta y acciones confirmadas por usuarios autorizados. Acciones fiscales, monetarias o irreversibles requieren confirmación. |
| Subencargados | Railway; proveedor de correo; Meta cuando se conecta WhatsApp; Anthropic o proveedor compatible solo si el negocio activa ayuda externa; proveedor S3 solo si está identificado y configurado. |
| Transferencias | Solo con proveedor documentado y mecanismo válido. La configuración de copia externa falla de forma cerrada si faltan proveedor, región de firma o residencia declarada. |
| Supresión/devolución | Exportación desde Ajustes. La baja borra directamente cuando no hay conservación obligatoria; en caso contrario crea una solicitud trazable y separa la decisión jurídica de la ejecución técnica. |
| Seguridad | Aislamiento multiempresa, permisos por función, cifrado en tránsito, controles documentales, trazabilidad, copias verificadas y acceso de soporte temporal. |

## 4. Evidencias que deben anexarse

- Identidad legal y contacto de privacidad publicados.
- DPA firmado con Railway y contratos/DPA de cada proveedor activo.
- Captura o exportación de región del servicio web, PostgreSQL y volumen.
- Lista vigente de subencargados de Railway y fecha de consulta.
- Configuración real de correo, IA, Meta, Stripe, OAuth y copia externa.
- Tabla de conservación validada, registro de pruebas de restauración y simulacro de brecha.
- Versiones aceptadas de política, términos y contrato de encargado por cuenta.

