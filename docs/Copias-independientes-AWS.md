# Copias independientes: propuesta y puesta en marcha

Estado 2026-09-06: plantilla y código preparados localmente, **sin cuenta contratada,
sin bucket creado, sin datos enviados y sin despliegue**. No confundir preparación
con protección externa activa.

## Decisión propuesta

Amazon S3 en **Europa, Irlanda (`eu-west-1`)**, en una cuenta de recuperación
independiente del acceso cotidiano a Railway. Se ha considerado también Backblaze
B2, que ofrece región europea, cifrado y Object Lock. Se propone AWS por sus
políticas de acceso explícitas y la posibilidad de reproducir la configuración
con CloudFormation, no porque un proveedor haga invulnerable el sistema.

La plantilla es `infra/backups/aws-s3.json`. No se aplica al ejecutar tests ni al
desplegar Bynoesis. Crear el stack exige una acción separada del propietario.

## Qué protege y qué no

- Base de datos y ZIP documental con el mismo identificador de juego.
- Bucket privado, acceso público bloqueado, HTTPS, AES256 y versiones.
- Object Lock en modo GOVERNANCE; el usuario de subida no puede borrar, leer ni
  saltarse retención. Una cuenta administrativa con permisos de bypass sí puede:
  protegerla con MFA y no guardar esas credenciales en Railway.
- Se conserva el bucket aunque se elimine o sustituya el stack.
- No impide que un atacante que controle la aplicación robe datos de la base
  operativa. No sustituye permisos, actualizaciones, MFA, alertas ni respuesta a
  incidentes. Un hash tampoco demuestra autenticidad ante un administrador malicioso.
- No demuestra recuperación hasta descargar y restaurar desde otro equipo/servidor.

## Pasos del propietario

1. Aprobar proveedor, región y presupuesto. Crear la cuenta AWS empresarial,
   verificar facturación y configurar MFA. Guardar recuperación fuera de Railway.
2. Revisar/archivar el acuerdo de tratamiento y actualizar la matriz de proveedores
   antes de copiar datos reales. Una región europea no resuelve por sí sola todas
   las cuestiones contractuales o de acceso internacional.
3. Aprobar el plazo operativo de retención con la política de conservación. La
   plantilla exige `RetentionDays` sin valor predeterminado. No es un plazo fiscal.
4. En CloudFormation, región Irlanda, subir `infra/backups/aws-s3.json`, revisar
   recursos y permisos IAM y crear el stack. No seleccionar COMPLIANCE sin una
   decisión aparte: protege incluso frente a root durante el plazo. Object Lock
   activado no se puede desactivar; ensayar primero con datos ficticios.
5. Anotar las salidas Bucket, UploadUser y Region. Generar una clave únicamente
   para UploadUser. No usar root ni añadir permisos generales. La plantilla no
   genera ni imprime claves.
6. Guardar la clave en variables protegidas de Railway, nunca en Git, archivos
   compartidos o el chat. Mantener una identidad separada para restauraciones con
   lectura de versiones y retención; esa identidad no vive en la aplicación.
7. Configurar alertas de gasto y un responsable. La plantilla no tiene borrado
   automático: revisar crecimiento y añadir lifecycle solo tras aprobar los plazos.
   Bloquear borrado no impide que una credencial robada suba basura y genere coste.

## Variables del servicio web

```text
NOESIS_BACKUP_S3_ENDPOINT=https://s3.eu-west-1.amazonaws.com
NOESIS_BACKUP_S3_REGION=eu-west-1
NOESIS_BACKUP_S3_PROVIDER_NAME=Amazon Web Services
NOESIS_BACKUP_S3_DATA_REGION=UE - Irlanda
NOESIS_BACKUP_S3_PREFIX=noesis
NOESIS_BACKUP_S3_SSE=AES256
NOESIS_BACKUP_S3_BUCKET=<salida Bucket>
NOESIS_BACKUP_S3_ACCESS_KEY=<clave de UploadUser, solo en gestor de secretos>
NOESIS_BACKUP_S3_SECRET_KEY=<secreto de UploadUser, solo en gestor de secretos>
```

El código nuevo solicita cifrado, firma con SHA-256 y añade Content-MD5 para la
integridad de transporte exigida por Object Lock; MD5 no se utiliza para firmas
ni contraseñas. La aceptación HTTP no prueba por sí sola la retención efectiva.

## Prueba de aceptación antes de producción

1. Crear un negocio ficticio en entorno aislado, con cliente, factura y archivo.
2. Crear una copia local y verificar restauración. Confirmar nombres emparejados.
3. Activar el destino de ensayo, ejecutar copia y verificar dos objetos en S3.
4. Desde la identidad de recuperación, comprobar AES256, versión y fecha de
   retención de cada objeto. Guardar evidencia sin credenciales ni datos personales.
5. Con la clave de UploadUser, intentar leer y borrar **un objeto ficticio**:
   ambas acciones deben ser rechazadas. Nunca probar borrados contra datos reales.
6. Descargar las dos versiones del mismo juego desde otro equipo con disco cifrado.
   Restaurar la BD en una instancia/esquema aislado y verificar el ZIP con sus hashes.
   No sustituir ni apuntar a la BD productiva. Una restauración de ensayo no debe
   arrancar scheduler, WhatsApp, correo o cobros reales.
7. Comparar esquema, recuentos e integridad; verificar una factura y un documento
   ficticios. Registrar tiempo de recuperación (RTO) y antigüedad de la copia (RPO).
   El horario diario actual puede dejar hasta aproximadamente un día de pérdida
   si todo va bien; no prometer cero pérdida. Ajustar frecuencia según necesidad.
8. Simular un rechazo de subida: el panel debe indicar fallo externo aunque la
   copia local sea correcta. Repetir y comprobar recuperación del estado.
9. Solo después autorizar producción y repetir la recuperación externa de forma
   controlada. Definir alerta independiente por ausencia de copias; el panel solo
   ayuda mientras alguien puede entrar en Bynoesis.

## Compatibilidad y rollback

Sin migración de BD. Los juegos nuevos usan el mismo prefijo para base y ZIP.
Las copias históricas no se borran ni se renombran: sus dos marcas de tiempo eran
distintas y el nuevo simulacro no adivina una pareja por «último archivo». Crear
un juego nuevo tras publicar. Para recuperar un histórico, identificar su pareja
en el registro de creación y validarla explícitamente en aislamiento.

Volver al código anterior conserva la BD 55 y los archivos; mantener ambos
artefactos. Desactivar variables S3 detiene nuevas subidas, no borra lo ya enviado.
No destruir el bucket como procedimiento de rollback.

## Coste y fuentes

Escenarios y calculadora offline: [[Costes-backups-y-desarrollo-interno]]. Incluye
salida Railway y crecimiento sin borrado; el cálculo no configura retención.

Se paga por volumen retenido, operaciones y posibles descargas; no hay un coste
mensual fijo verificado para Bynoesis. Presupuestar con el tamaño real de los juegos
y las versiones, no solo con el tamaño de la BD. Revisar la [tarifa oficial de
S3](https://aws.amazon.com/s3/pricing/) antes de contratar.

- [CISA: backups cifrados, independientes y ensayos de recuperación](https://www.cisa.gov/stopransomware/ransomware-guide).
- [AWS: funcionamiento de Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html).
- [AWS: límites, cifrado y checksum de subida](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html).
- [CloudFormation: retención predeterminada](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-s3-bucket-defaultretention.html).
- [Alternativa considerada: regiones de Backblaze](https://www.backblaze.com/docs/cloud-storage-data-regions).

La plantilla tiene validación local estructural, no una ejecución real de
CloudFormation. Esa validación y las pruebas externas anteriores siguen pendientes.
