# Almacenamiento y copias de seguridad

> Cómo está estructurado **hoy** el almacenamiento de Noesis y qué hace exactamente
> el sistema de copias, leído del código el 2026-09-08. Es la foto técnica: qué
> ocurre, dónde y con qué comando se comprueba.
>
> Las decisiones de arquitectura, proveedor y obligaciones legales están en
> [`cumplimiento/Plan-Datos-Servidores-Copias`](cumplimiento/Plan-Datos-Servidores-Copias.md).
> Este documento no las repite: describe la implementación.

## 1. Las tres capas de almacenamiento

```text
  Base de datos            Volumen persistente        Copias
  ─────────────            ───────────────────        ──────
  PostgreSQL en prod       /data/uploads/{negocio}/   /data/backups/*.sql
  SQLite en local          /data/models (whisper)     /data/backups/*.docs.zip
                                                      + S3 externo (opcional)
```

| Capa | Qué guarda | Variable | Valor correcto en producción |
|---|---|---|---|
| Base de datos | Todo lo estructurado, más `ocr_text` | `DATABASE_URL` | Referencia al servicio Postgres |
| Documentos | Los archivos subidos | `NOESIS_DOCS_PATH` | `/data/uploads` |
| Copias | Volcados y ZIP | `NOESIS_BACKUP_DIR` | `/data/backups` |

Las tres rutas deben estar **dentro del volumen montado en `/data`**. Cualquier
ruta fuera de él vive en el sistema de archivos del contenedor y desaparece en
cada despliegue.

## 2. Trayectoria de un documento

Un autónomo hace una foto de un ticket y la sube por WhatsApp o por la web:

1. **Validación** ([`documents/validation.py`](../src/noesis/documents/validation.py)):
   extensión en la allowlist (PDF, JPG, PNG, WEBP, HEIC), firma real del archivo,
   tamaño máximo `NOESIS_MAX_UPLOAD_MB` (15 MB), límite de páginas de PDF y de
   píxeles de imagen. Se rechaza el PDF con contenido activo.
2. **Antivirus** ([`documents/malware.py`](../src/noesis/documents/malware.py)): si
   `NOESIS_CLAMAV_HOST` está configurado, el contenido viaja en memoria al daemon
   privado por `INSTREAM`. **No se escribe en disco antes del veredicto.**
3. **Escritura en disco** ([`documents/storage.py:52`](../src/noesis/documents/storage.py#L52)):

   ```text
   {NOESIS_DOCS_PATH}/{business_id}/{uuid}.{ext}
   ```

   El nombre en disco es un uuid generado por Noesis, nunca el que envía el
   usuario: no hay forma de salirse de la carpeta. Cada negocio tiene su
   subdirectorio, así que el aislamiento existe también a nivel de sistema de
   archivos, no solo en las consultas.
4. **Metadatos en la base** (tabla `documents`, [`migrations.py:228`](../src/noesis/migrations.py#L228)):
   `business_id`, `client_id`, `invoice_id`, `filename` original, `stored_name`,
   `mime`, `size`, `note`, `created_at` y **`ocr_text`**.

**Consecuencia que conviene tener presente:** el texto extraído del documento vive
en la base de datos, no solo en el disco. Un ticket escaneado está en dos sitios, y
cualquier volcado de la base lleva su contenido en texto plano.

## 3. Qué hace el sistema de copias

Cada noche, `run_backup()` ([`web/backups.py`](../src/noesis/web/backups.py))
ejecuta cuatro pasos. El scheduler lo lanza una sola vez al día mediante
`claim_scheduled_run`, así que dos instancias no duplican trabajo.

### 3.1 Crear

| Artefacto | Cómo se genera |
|---|---|
| `noesis-AAAAMMDD-HHMM.sql` | Volcado lógico de PostgreSQL, con las tablas ordenadas por dependencias y los tipos preservados (decimales, fechas, binarios). En SQLite, copia en caliente con la API `backup` |
| `noesis-AAAAMMDD-HHMM.docs.zip` | Todo `NOESIS_DOCS_PATH` con rutas relativas, más `.noesis-manifest.json` con el sha256 de cada archivo. Ignora enlaces simbólicos y cualquier ruta que escape del directorio |

### 3.2 Verificar

No se da una copia por buena sin restaurarla:

- **Base**: se restaura en un esquema PostgreSQL con nombre aleatorio (o en un
  fichero SQLite temporal), se comprueban las tablas clave y se comparan los
  recuentos con el origen. El esquema temporal se destruye después.
- **Documentos**: se abre el ZIP, se comprueba su integridad, se recalcula el
  sha256 de cada archivo y se compara con el manifiesto ([`backups.py:491`](../src/noesis/web/backups.py#L491)).
  Si falta uno o cambia un hash, la copia se marca como fallida.

El resultado queda en la tabla `backup_runs` (migración 8) y lo lee el centro CISO
de `/admin` ([`security_center.py:68`](../src/noesis/security_center.py#L68)): si
la última copia correcta tiene más de 48 horas, baja la nota y avisa.

### 3.3 Rotar

`KEEP = 14` ([`backups.py:41`](../src/noesis/web/backups.py#L41)): se conservan las
14 copias diarias más recientes de cada tipo y se borran las anteriores.

### 3.4 Subir fuera

`_upload_offsite()` ([`backups.py:522`](../src/noesis/web/backups.py#L522)) firma la
petición con AWS Signature V4 y sube a cualquier almacén compatible con S3.
Comportamiento exacto:

- Las **cuatro** variables vacías → devuelve `None` y no se hace ninguna petición
  ni se incurre en coste.
- Algunas puestas y otras no → error en el log y no sube.
- En producción exige HTTPS.
- Pide cifrado del lado del servidor con `NOESIS_BACKUP_S3_SSE`.

### 3.5 Simulacro semanal

Los domingos a las 04:30, `noesis-restore-check` repite de forma independiente la
restauración de la última copia y la validación del manifiesto, sin tocar la base
activa. El resultado va a la bitácora y al centro CISO.

## 4. Comprobaciones rápidas

```bash
# Qué rutas está usando realmente este despliegue
python -c "from noesis import config; print(config.DOCS_PATH, config.BACKUP_DIR)"

# Estado de las últimas copias
python -c "from noesis import db; print(db.latest_backup_run())"

# Revalidar la última copia sin tocar la base activa
noesis-restore-check
```

En Railway, además: comprobar en **Settings → Volumes** dónde está montado el
volumen, y que `NOESIS_DOCS_PATH` y `NOESIS_BACKUP_DIR` apunten dentro de él.

## 5. Puntos débiles conocidos

Ordenados por lo que pueden costar. Los tres primeros pierden datos **en
silencio**: no dan error, solo se descubren el día que hay que restaurar.

| # | Problema | Dónde | Arreglo |
|---|---|---|---|
| 1 | `.env.example` documenta `NOESIS_BACKUP_DIR=/backups`, fuera del volumen montado en `/data`. Copiado tal cual al panel, **las copias se borran en cada despliegue**. El valor por defecto del código (`/data/backups`) sí es correcto: la variable explícita lo empeora | `.env.example`, [`config.py:497`](../src/noesis/config.py#L497) | Poner `/data/backups` o borrar la línea |
| 2 | `NOESIS_DOCS_PATH` vacía significa `./uploads` dentro del contenedor: **los documentos desaparecen en cada despliegue**. Todo depende de que la variable esté puesta en el panel | [`config.py:112`](../src/noesis/config.py#L112) | Documentar `/data/uploads` y verificarlo al arrancar |
| 3 | Nada valida esas rutas. `/ready`, `production_check`, `readiness` e `integration_check` comprueban esquema y release, no almacenamiento | — | Comprobación de existencia, escritura y persistencia al arrancar |
| 4 | Las copias viven en el mismo volumen que los originales, y son completas: con `KEEP = 14`, el volumen necesita **unas 15 veces** el tamaño del corpus documental. Al llenarse, fallan las subidas **y** las copias a la vez | `backups.py` | Copia externa (P0 del plan) y vigilancia de espacio libre |
| 5 | No hay cuota por negocio ni control de espacio en disco | — | Cuota por plan; alerta al 80 % del volumen |
| 6 | Base y documentos se copian en momentos distintos, sin consistencia entre ambos. Al restaurar puede haber filas de `documents` cuyo `stored_name` no esté en el ZIP, o archivos sin fila. No existe ninguna tarea que detecte esos huérfanos | `backups.py` | Comando de reconciliación en ambos sentidos |
| 7 | El volumen es de un solo adjunto: mientras los archivos vivan en disco local **solo puede haber una instancia**. Es el techo de la arquitectura actual | Diseño | Almacenamiento de objetos el día que haga falta escalar |

Los puntos 1 y 2 se verifican en el panel del proveedor en dos minutos y son, con
diferencia, los más urgentes: el resto degrada el servicio, esos dos lo vacían.

## 6. Lo que este documento no cubre

- Dónde **debería** estar alojado todo esto, con qué proveedor y bajo qué
  jurisdicción: [`cumplimiento/Plan-Datos-Servidores-Copias`](cumplimiento/Plan-Datos-Servidores-Copias.md).
- Cuánto tiempo se conserva cada dato y cómo se borra:
  [`cumplimiento/Politica-de-retencion`](cumplimiento/Politica-de-retencion.md).
- Qué hacer cuando hay que restaurar de verdad:
  [`cumplimiento/Continuidad-RPO-RTO`](cumplimiento/Continuidad-RPO-RTO.md).
- Amenazas y controles del producto: [`Seguridad-operativa`](Seguridad-operativa.md).
