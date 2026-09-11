# Plan de continuidad: RPO, RTO y runbooks

> - Creado: 2026-09-08 · Última revisión: 2026-09-08 · Próxima revisión: 2026-12-08
> - Responsable: founder (Xavier).
> - Base: art. 32.1.b y 32.1.c RGPD (disponibilidad y capacidad de restaurar), más
>   art. 32.1.d (verificación periódica de la eficacia).

## 1. Objetivos

| Escenario | RPO | RTO | Estado |
|---|---|---|---|
| Borrado accidental de un registro | 0 | minutos | Cubierto en producto |
| Corrupción de datos o migración fallida | ≤ 24 h | ≤ 2 h | Estimado |
| Ransomware o cuenta comprometida | ≤ 24 h | ≤ 8 h | **No cubierto** sin copia inmutable |
| Pérdida total del proveedor | ≤ 24 h | ≤ 8 h | **No cubierto**; nunca ensayado |

Son objetivos, no garantías. Pasan a ser hechos el día que el simulacro externo
se ejecuta y se cronometra. Hasta entonces, cualquier promesa a un cliente sobre
tiempos de recuperación es una promesa sin respaldo.

## 2. Runbook A — restauración de la base de datos

1. Declarar el incidente y anotar la hora. Poner la aplicación en mantenimiento
   para que no siga escribiendo sobre datos que se van a sustituir.
2. Identificar la última copia con estado correcto (`backup_runs`, o el listado
   del bucket externo).
3. Descargar la copia y **descifrarla** con la clave privada custodiada.
4. Levantar una base vacía en el destino. **Nunca restaurar sobre la base viva**
   sin haber preservado antes su estado actual.
5. Restaurar y comparar esquema y recuentos de tablas clave con lo esperado.
6. Aplicar las migraciones pendientes hasta la versión que espera el código.
7. Apuntar la aplicación a la base restaurada. Verificar `/health`, `/ready`,
   login, aislamiento entre dos negocios e integridad de la numeración fiscal.
8. **Reaplicar las supresiones** solicitadas entre la fecha de la copia y hoy.
   Paso obligatorio: sin él, la restauración resucita datos que un interesado
   había hecho borrar.
9. Anotar RPO y RTO reales en [`Registro-de-evidencias`](Registro-de-evidencias.md).

## 3. Runbook B — restauración de documentos

1. Recuperar el ZIP documental correspondiente a la misma fecha que la base.
2. Validar el manifiesto y los hashes antes de extraer nada.
3. Extraer sobre el volumen de destino conservando rutas.
4. Comprobar en la aplicación varios documentos de negocios distintos.
5. Si base y documentos son de fechas distintas, **anotar la discrepancia**: habrá
   referencias a documentos inexistentes y hay que localizarlas.

## 4. Runbook C — pérdida total del proveedor

1. Crear el proyecto en el proveedor alternativo ya identificado.
2. Base de datos gestionada nueva, vacía, región UE.
3. Aplicar los runbooks A y B con las copias del bucket externo.
4. Configurar variables desde la copia sellada de secretos. **Rotar todo lo que
   haya podido quedar expuesto** durante el incidente.
5. Apuntar el DNS de `bynoesis.com` al nuevo destino. Verificar TLS y hosts
   permitidos.
6. Volver a conectar webhooks: Stripe y Meta apuntan a la URL antigua y hay que
   reconfigurarlos, con firma nueva.
7. Recorrer la puerta de salida a piloto de `docs/04-seguridad-y-datos/Seguridad-operativa.md`.
8. Comunicar a los clientes qué pasó, qué datos se vieron afectados y qué ventana
   de información se perdió. Con hechos, no con eufemismos.

## 5. Runbook D — ransomware o credencial comprometida

1. **No restaurar todavía.** Primero cortar: revocar credenciales, rotar
   `NOESIS_SECRET`, invalidar sesiones, cerrar accesos del proveedor.
2. Determinar la fecha del compromiso antes de elegir copia: restaurar una copia
   posterior a la intrusión reinstala el problema.
3. Restaurar en infraestructura **nueva**, no sobre la comprometida.
4. Activar en paralelo el [`Procedimiento-brechas`](Procedimiento-brechas.md): el
   reloj de 72 horas ya está corriendo.
5. Conservar la infraestructura comprometida aislada como evidencia, sin borrarla.

## 6. Calendario de pruebas

| Prueba | Frecuencia | Automática | Evidencia |
|---|---|---|---|
| Restauración de cada copia recién creada | Diaria | Sí | `backup_runs` |
| Simulacro independiente `noesis-restore-check` | Semanal (domingos 04:30) | Sí | Bitácora y centro CISO |
| **Restauración externa completa cronometrada** | **Trimestral** | No | [`plantillas/Registro-simulacro-restauracion`](plantillas/Registro-simulacro-restauracion.md) |
| Prueba de descifrado de la clave custodiada | Trimestral | No | Registro de evidencias |
| Recorrido completo del runbook C | Anual | No | Registro de evidencias |

La fila en negrita es la única que prueba de verdad la supervivencia del negocio.
Las dos primeras prueban que el código de restauración funciona, que no es lo mismo.
