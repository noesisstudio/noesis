# Revisión previa a main — 4 de septiembre de 2026

## Alcance y decisión

Rama de revisión: `codex/review-value-privacy`. Base remota comprobada:
`d3740a052432a29c9306bf16629a711384df9352`. Incluye el registro de valor/WUB,
correcciones de su revisión externa y el bloque RGPD, no solamente textos legales.

**PUBLICADO con autorización del founder el 4-sep**, después de backup real y
restauración verificada. Esquema 55, páginas públicas, acceso demo y recuentos
operativos correctos. No autoriza apertura masiva ni activar el ledger.

## Resultado de publicación

- Primer release publicado: `4f5e88f071cd`; Railway
  `56d18ded-993c-4aa8-96d1-a623a8d75c79`, SUCCESS.
- Backup previo de esquema 53: `noesis-20260904-090824-601912.dump.gz`
  (123.805 bytes) y `noesis-20260904-090829-568655.docs.zip` (82.060 bytes).
  Segundo simulacro aislado de restauración OK en 3,854 s.
- Ambos artefactos fijados en `/data/backups/predeploy-schema55-20260904`, fuera
  de rotación. Siguen dentro de Railway: no demuestran recuperación offsite.
- 14 páginas y 8 cabeceras correctas; demo de autónomo en Inicio, Ajustes,
  Suscripción, Facturas y Documentos, y demo de gestoría en 200.
- Recuentos idénticos a la copia: negocios, usuarios, clientes, facturas, líneas
  y fichajes. Integridad de auditoría correcta. Altas y ambos flags de valor false.
- El commit de cierre de esta evidencia es solo documental; no cambia el runtime.

## Hallazgos corregidos

1. El lock contenía pypdf 6.15.0 con tres vulnerabilidades moderadas conocidas.
   Se actualizó a 6.16.1, manteniendo el resto de dependencias fijadas.
2. El guardián de publicación exigía datos de un SMTP residual aunque Brevo era
   el proveedor efectivo. Se alineó con el adaptador real, sin cambiar los envíos:
   Brevo tiene prioridad y su fallo no provoca un reintento por SMTP. Si se usa
   SMTP realmente, nombre y región siguen siendo obligatorios.
3. El detector de secretos no reconocía huellas públicas de branding ni algunos
   datos ficticios de pruebas. Se cotejaron las 49 huellas con los archivos y se
   añadieron excepciones exactas; no se desactivó ningún detector.
4. Se amplió el CI para comprobar el candidato en PostgreSQL, no solo SQLite,
   incluyendo la vuelta al código anterior antes de bajar el esquema.

## Evidencia

- Suite local completa inicial: 627 pruebas, OK en 642,162 segundos.
- CI final: **629 pruebas, OK en 275,502 segundos**, con pypdf 6.16.1 y las dos
  regresiones de proveedor efectivo incluidas en el mismo descubrimiento.
- Auditoría del lock actualizado: sin vulnerabilidades conocidas detectadas.
- Ruff, Bandit y comprobación de verdad documental: correctos.
- PostgreSQL 16 efímero: migración histórica, 35 rutas de humo,
  creación/restauración de copias con facturas emitidas y ledger: correctos.
- Código base de esquema 53 sobre BD 55: cliente, emisión, cobro y exportación
  correctos, sin bajar antes el esquema.
- Ciclo 55→54→53→54→55: conserva datos de facturas, clientes, usuarios y jornada;
  mantiene inmutabilidad fiscal.
- Privacidad en PostgreSQL: baja HTTP con factura conserva datos, deduplica la
  solicitud y el aviso, rechaza a otros negocios y al usuario no administrador,
  soporta concurrencia, exporta sin notas internas y permite seguimiento admin.
- CI final del candidato:
  https://github.com/noesisstudio/noesis/actions/runs/33855910788
  Ambos jobs terminan `success`. Código probado:
  `fbfa76b7379f6295cb4efac62a2c6bca9e17aaa5`. El commit posterior solo recoge
  documentación/evidencia; código, pruebas, workflow, baseline y lock no cambian.

Los scripts destructivos de rollback solo admiten host local y base `noesis_ci`.
No se ejecutaron contra Railway ni contra datos de clientes.

## Configuración comprobada sin modificarla

Lectura del control plane de Railway, mostrando únicamente presencia/ausencia y
flags, nunca credenciales:

- Alta pública: false.
- Ambos flags del ledger: ausentes; el código usa false por defecto.
- Brevo: configurado. SMTP residual: presente, sin metadatos; no se usa mientras
  Brevo esté configurado. El candidato corrige la falsa alarma.
- S3: no configurado. Esta revisión no desactiva una copia S3 que estuviera activa,
  pero sigue faltando recuperación externa ante pérdida de toda la plataforma.
- Ningún nuevo despliegue observado: último web `90504fd2-a342-46f7-9bd5-e597e831efd2`,
  del 3-sep a las 15:44 UTC. Main remoto no cambió durante la revisión.

## Secuencia de publicación, solo después de autorización

1. Volver a comprobar main remoto; si hay commits nuevos del socio, integrar y
   repetir validación del candidato resultante antes de publicar.
2. Obtener una copia reciente de base y archivos, verificarla y conservar la
   identificación del release anterior. La copia de prueba del CI no sustituye
   una copia de los datos actuales de producción.
3. Mantener alta pública y ambos flags de valor en false. No activar WUB con este
   despliegue ni confundirlo con la apertura comercial.
4. Publicar el candidato aprobado; comprobar release, esquema 55 y `/ready`,
   acceso de cuentas existentes, páginas públicas y panel de administración.
5. Si se detecta regresión: volver primero al código anterior, dejando el esquema
   nuevo. No bajar tablas mientras el candidato sirve tráfico.
6. El downgrade elimina las tablas nuevas de valor/solicitudes. Si ya contienen
   datos reales, exportarlos y preservar una copia antes de plantearlo. Preferir
   rollback solo de código mientras se investiga; no perder solicitudes de derechos.

## Lo que esta revisión no certifica

No certifica cumplimiento jurídico ni autoriza apertura masiva. Siguen pendientes
validación profesional de textos/plazos, DPA y regiones, copia externa y simulacro
con infraestructura distinta, pruebas reales de integraciones y piloto acompañado.
No se activaron proveedores, cobros, purgas ni automatizaciones nuevas.
