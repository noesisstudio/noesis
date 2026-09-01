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
| Archivo malicioso o bomba de recursos | Firma real de PDF/imagen, límite de tamaño, páginas, píxeles, rechazo de PDF activo y adaptador ClamAV privado por streaming | Desplegar el daemon y activar fallo cerrado; ningún escáner garantiza riesgo cero |
| SSRF por medios de WhatsApp | Descarga solo por HTTPS desde dominios de medios Meta conocidos y con tamaño acotado | Revalidar dominios si Meta cambia su entrega |
| XML malicioso | Respuestas AEAT se analizan con `defusedxml` y tamaño máximo | Certificado y entorno AEAT reales pendientes |
| Dependencia vulnerable o cadena de suministro | Lock reproducible, acciones fijadas por SHA, Dependabot, `pip-audit`, Bandit, Ruff y detector de secretos en CI | Revisar alertas antes de fusionar; no actualizar a ciegas |
| Doble ejecución o carrera | Transacciones, claves idempotentes, bloqueo de fila y outboxes durables | Smoke PostgreSQL obligatorio |
| Pérdida o cifrado de datos | Backups verificados, copia externa HTTPS, cifrado S3 solicitado y simulacro semanal independiente | Falta restaurar una descarga del bucket en otra infraestructura y medir RPO/RTO |

### Decisión de infraestructura para el piloto

Railway con PostgreSQL, volumen, copia externa y restauración verificada es una base
razonable para el piloto; migrar ahora añadiría riesgo operativo sin demostrar que el
proveedor sea el cuello de botella. La independencia no se consigue cambiando de
marca, sino probando una recuperación fuera del mismo fallo: descargar base y ZIP
desde el bucket, restaurarlos en otro PostgreSQL/host, cronometrar RPO y RTO y dejar
responsable y evidencia. Hasta completar esa prueba, una copia «OK» dentro de
Railway no demuestra recuperación ante pérdida total del proveedor.
| Abuso administrativo | Sesión admin corta, Google OAuth obligatorio en producción y acciones sensibles en bitácora append-only encadenada | El MFA real depende de la política del Workspace/cuenta Google; passkeys para gestoría siguen pendientes |
| Manipulación de evidencia | Triggers impiden UPDATE/DELETE y cada evento enlaza la huella anterior | Un superusuario de BD sigue siendo una frontera de confianza; exportar evidencia a un SIEM/WORM al escalar |

## Centro CISO interno

`/admin` muestra un responsable CISO determinista y de solo lectura. No es un LLM ni
un agente autónomo: calcula su parte a partir de controles verificables, antigüedad de
backups, último simulacro, presión agregada de autenticación y la bitácora. No lee
facturas, mensajes, documentos, teléfonos, emails ni IPs. Su nota es operativa: ayuda
a priorizar, pero nunca equivale a certificación o pentest.

La tabla `security_events` (migración 35) conserva tipo, severidad, área, IDs internos
opcionales, `request_id`, metadatos escalares acotados y la cadena de hashes. Triggers
SQLite/PostgreSQL bloquean actualización y borrado. Los metadatos descartan claves de
email, teléfono, IP, token, secreto, contraseña, fichero, documento, mensaje o cuerpo.

## Antivirus documental privado

- Variables: `NOESIS_CLAMAV_HOST`, `NOESIS_CLAMAV_PORT`,
  `NOESIS_CLAMAV_TIMEOUT_SECONDS` y `NOESIS_CLAMAV_REQUIRED`.
- Noesis usa `INSTREAM`: el contenido viaja en memoria al daemon privado, no a una
  API de terceros y no se escribe antes del veredicto.
- `FOUND` se rechaza siempre. Si `REQUIRED=true`, timeout, caída o respuesta inválida
  también se rechazan antes de almacenar. Sin ClamAV siguen actuando las validaciones
  estructurales, pero el centro CISO mantiene el aviso.
- El daemon debe vivir en red privada, sin puerto público, actualizado y con recursos
  limitados. Probar EICAR en un entorno de ensayo, nunca con malware real.

## Restauración y continuidad

- Al crear cada copia, Noesis ya la restaura en un fichero SQLite temporal o en un
  esquema PostgreSQL aleatorio y compara esquema y recuentos.
- Cada domingo a las 04:30, `noesis-restore-check` repite de forma independiente la
  restauración de la última base y verifica el manifiesto/hashes del ZIP documental.
  El resultado queda en la bitácora y aparece en el centro CISO.
- Esto prueba el artefacto local y el código de restauración. Para cubrir pérdida
  total del proveedor hay que descargar desde S3 y restaurar en otra infraestructura,
  cronometrar RPO/RTO y documentar el responsable.

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
  local; la cuenta Google del fundador debe tener verificación en dos pasos.
- Webhooks reales prueban firma válida/inválida, duplicado y reintento.
- ClamAV privado en fallo cerrado probado con limpio, EICAR, caída y timeout.
- `noesis-restore-check` correcto y copia externa restaurada en infraestructura
  distinta con RPO/RTO anotados.
- Acceso de una segunda empresa intenta y no consigue leer recursos ajenos.
- Responsable y canal de incidentes definidos; retención de logs y backups fijada.

## Trabajo que requiere especialistas o infraestructura

Noesis puede construir controles internos, pero no debe autocertificarse. Antes de
escalar datos reales se mantienen como tareas externas: pentest autenticado, revisión
RGPD/DPA, auditoría fiscal/AEAT, configuración de red y hosting, restauración externa
y respuesta a incidentes ensayada. RLS de PostgreSQL, KMS/cifrado selectivo y MFA de
gestoría se decidirán con evidencia del piloto y sin sustituir el aislamiento actual.
