# Seguridad operativa

Guía viva para proteger Noesis, sus clientes, trabajadores y gestorías. No es una
declaración de invulnerabilidad: describe controles verificables, amenazas asumidas y
responsabilidades que siguen fuera del código.

## Activos que requieren máxima protección

- Identidad, datos fiscales, clientes, trabajos, fichajes, facturas y documentos de
  cada negocio.
- Tokens de sesión, enlaces privados de portales y recuperación, credenciales OAuth,
  Meta, Stripe, SMTP, IA, almacenamiento y certificado AEAT.
- Integridad de numeraciones, cobros y registros fiscales append-only.
- Disponibilidad de PostgreSQL, archivos, colas de salida y copias recuperables.

## Fronteras de confianza

```text
Navegador / WhatsApp / portales
              |
       proxy TLS controlado
              |
     FastAPI + sesión + límites
              |
  servicio de dominio con business_id
              |
 PostgreSQL / documentos / outboxes
              |
 adaptadores externos expresamente configurados
```

El modelo de IA no es una frontera de autorización. Puede proponer una acción, pero
los permisos, el `business_id`, la confirmación y las invariantes fiscales se validan
en servidor y base de datos.

## Amenazas prioritarias y controles

| Amenaza | Control actual | Evidencia / límite |
|---|---|---|
| Acceso cruzado entre empresas | Sesión, `business_id` obligatorio y FK compuestas | Suite de aislamiento; auditoría externa pendiente |
| Robo o fijación de sesión | Cookie `__Host-`, `Secure`, `HttpOnly`, `SameSite=Lax`, rotación tras login, caducidad por inactividad | TLS y dominio final deben verificarse en producción |
| Fuerza bruta de acceso/recuperación | Límite persistente compartido por IP y cuenta; claves seudonimizadas con HMAC | Un WAF puede añadir defensa volumétrica, no sustituir esta capa |
| Host-header, clickjacking y carga cruzada | Hosts permitidos, CSP, `frame-ancestors`, COOP/CORP, HSTS y cabeceras defensivas | CSP estricta se observa primero en modo report-only |
| Fuga por logs | Registro estructurado sin query string, cuerpo, token ni datos personales; access log de Uvicorn apagado en producción | Proveedor de hosting debe fijar retención y acceso |
| Archivo malicioso o bomba de recursos | Firma real de PDF/imagen, límite de tamaño, páginas, píxeles y rechazo de PDF activo | Antivirus de contenido queda como defensa adicional antes de gran escala |
| SSRF por medios de WhatsApp | Descarga solo por HTTPS desde dominios de medios Meta conocidos y con tamaño acotado | Revalidar dominios si Meta cambia su entrega |
| XML malicioso | Respuestas AEAT se analizan con `defusedxml` y tamaño máximo | Certificado y entorno AEAT reales pendientes |
| Dependencia vulnerable o cadena de suministro | Lock reproducible, acciones fijadas por SHA, Dependabot, `pip-audit`, Bandit, Ruff y detector de secretos en CI | Revisar alertas antes de fusionar; no actualizar a ciegas |
| Doble ejecución o carrera | Transacciones, claves idempotentes, bloqueo de fila y outboxes durables | Smoke PostgreSQL obligatorio |
| Pérdida o cifrado de datos | Backups verificados, copia externa HTTPS y cifrado S3 solicitado | Una copia no cuenta hasta restaurarla en entorno aislado |
| Abuso administrativo | Sesión admin más corta y Google OAuth obligatorio en producción cuando está configurado | MFA/passkeys para gestoría y roles finos siguen pendientes |

## Gestión de secretos

- Los secretos viven exclusivamente en el gestor de variables de producción;
  nunca en Git, documentos, tickets, capturas ni mensajes entre agentes.
- Cada proveedor tiene una credencial distinta y el menor alcance posible. No se
  comparte una clave entre desarrollo, pruebas y producción.
- Rotar inmediatamente ante exposición sospechada y periódicamente según el
  proveedor. Registrar fecha, responsable y resultado, nunca el valor.
- Credenciales prioritarias: `NOESIS_SECRET`, PostgreSQL, Meta, Stripe, SMTP,
  Google OAuth, IA, S3 y certificado/clave AEAT.
- Tras rotar `NOESIS_SECRET`, todas las sesiones quedan invalidadas. Tras rotar una
  firma de webhook, probar evento válido, firma inválida, duplicado y reintento.

## Procedimiento mínimo de incidente

1. Contener: desactivar la integración o credencial afectada sin borrar evidencia.
2. Preservar: guardar tiempos, request IDs, eventos y cambios de configuración; no
   copiar datos personales a canales no autorizados.
3. Determinar alcance por `business_id`, tipo de dato, periodo y terceros.
4. Rotar credenciales y revocar sesiones/enlaces afectados.
5. Recuperar desde estado conocido, validar `/ready`, colas, integridad fiscal y una
   restauración si aplica.
6. Evaluar con asesoría jurídica/DPO la notificación RGPD y comunicar hechos, no
   suposiciones. Documentar causa, control correctivo y prueba de no regresión.

## Puerta de salida a piloto

- CI general y PostgreSQL verdes; migración objetivo aplicada.
- Variables revisadas con `noesis-doctor --strict`, sin secretos en repositorio.
- TLS, dominio, hosts permitidos, cookies y login Google admin comprobados fuera de
  local.
- Webhooks reales prueban firma válida/inválida, duplicado y reintento.
- Copia externa restaurada en entorno aislado.
- Acceso de una segunda empresa intenta y no consigue leer recursos ajenos.
- Responsable y canal de incidentes definidos; retención de logs y backups fijada.

## Trabajo que requiere especialistas o infraestructura

Noesis puede construir controles internos, pero no debe autocertificarse. Antes de
escalar datos reales se mantienen como tareas externas: pentest autenticado, revisión
RGPD/DPA, auditoría fiscal/AEAT, configuración de red y hosting, restauración real y
respuesta a incidentes ensayada. RLS de PostgreSQL, antivirus de archivos y MFA de
gestoría se decidirán con evidencia del piloto y sin sustituir el aislamiento actual.
