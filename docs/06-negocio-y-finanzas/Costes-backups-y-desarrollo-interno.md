# Costes de copias y desarrollo interno

6 de septiembre de 2026. Propuesta, no contratación. USD sin impuestos ni cambio
a EUR. No es una factura observada de Bynoesis.

## Recomendación

S3 Standard en Irlanda, cuenta empresarial con MFA y acceso de recuperación
separado de Railway. No hace falta contratar EC2 ni otra base de datos permanente
en AWS. Reservar inicialmente 10 USD/mes para copias y transferencia, condicionado
a medir tamaños. No es tarifa plana ni un límite automático.

Nosotros desarrollamos creación, comprobación y control; AWS guarda la copia
independiente. Guardarla solo junto a la aplicación no cubre perder Railway.

## Tarifas y fuentes

- S3 Standard Irlanda: 0,023 USD por GB-mes, primer tramo de 50 TB.
- PUT: 0,005 USD por 1.000; GET: 0,0004 USD por 1.000.
- Entrada S3 sin cargo de transferencia AWS, pero salida del servicio Railway:
  0,05 USD/GB. Entrada gratuita no significa traslado gratuito.
- AWS publica 100 GB/mes de salida gratuita compartida entre servicios/regiones
  elegibles. No asumir que queda disponible para nuestras restauraciones.

[Catálogo regional oficial AWS](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/eu-west-1/index.json),
[tarifas S3](https://aws.amazon.com/s3/pricing/) y
[tarifas Railway](https://railway.com/pricing/), consultados el 6-sep.

## Escenarios

Una copia completa diaria, BD comprimida más ZIP, tamaño constante, mes de 30 días
y **borrado efectivo aprobado que conserve 30 juegos**. Coste mensual estabilizado,
no factura del primer mes. GiB = 2^30 bytes; para Railway se convierte
conservadoramente a GB decimales.

| Tamaño del juego | Retenido | S3 almacenamiento | Salida Railway | Total aproximado/mes |
|---|---:|---:|---:|---:|
| 0,1 GiB | 3 GiB | 0,07 USD | 0,16 USD | 0,23 USD |
| 1 GiB | 30 GiB | 0,69 USD | 1,61 USD | 2,30 USD |
| 5 GiB | 150 GiB | 3,45 USD | 8,05 USD | 11,50 USD |
| 10 GiB | 300 GiB | 6,90 USD | 16,11 USD | 23,01 USD |

Incluye 60 PUT mensuales: 0,0003 USD. Los escenarios grandes son económicos, no
capacidad validada: el adaptador usa PUT simple. Antes de superar 5 GB por objeto
necesita multipart o división con restauración verificada.
[Límite oficial de subida](https://docs.aws.amazon.com/AmazonS3/latest/userguide/upload-objects.html).

**La plantilla actual no tiene borrado automático.** Object Lock protege durante
un plazo, pero no borra al finalizar. Sin lifecycle, 1 GiB diario suma 365 GiB al
año: ritmo mensual al final del año de unos 10,01 USD, no coste medio anual.
El tamaño real actual no se ha medido. No inferirlo del volumen histórico ni del
número de clientes. Duplicar frecuencia duplica aproximadamente este coste.

Excluidos: CPU, disco local y alojamiento Railway existente, reintentos, descargas
de recuperación, monitorización, soporte, impuestos y cambio de moneda. Sin
créditos promocionales. Propuesta SSE-S3, sin KMS dedicado ni soporte AWS de pago.

## Control del presupuesto

1. Medir tamaños comprimidos sin leer contenido de clientes.
2. Aprobar presupuesto y conservación; configurar avisos al 50/80/100 %.
3. Conciliar facturas AWS y salida Railway en el libro CFO existente.
4. No detener ni borrar copias automáticamente por superar presupuesto.
5. Antes de crecer, probar multipart e incremental documental con recuperación.

Los avisos no son un tope duro y aún no están configurados. Lifecycle debe
contemplar versiones anteriores, Object Lock y conservación aprobada.

## Implementado internamente ahora

`scripts/estimate_backup_cost.py`: Python estándar, sin red, .env, credenciales,
lectura de documentos ni importación de Bynoesis. Solo argumentos numéricos y JSON.
Tarifas fechadas; rechaza negativos, no finitos y más de 50 TiB retenidos.

```powershell
# Sin borrado, volumen al día 365:
.\.venv\Scripts\python.exe scripts/estimate_backup_cost.py --set-gib 1
# Solo simulación de borrado aprobado a 30 días:
.\.venv\Scripts\python.exe scripts/estimate_backup_cost.py --set-gib 1 --retention-days 30
```

El argumento de retención no borra ni configura nada. Cuatro pruebas verifican
importes, frecuencia, crecimiento sin borrado, bucket reciente y valores inválidos.
Valoración: compartible con supuestos; falta volumen real para personalizarlo.

## Siguiente desarrollo, por orden

1. Recuperación: validar PostgreSQL aislado del candidato; con autorización,
   configurar AWS y demostrar restauración fuera de Railway. Preparado no es activo.
2. WhatsApp: probar texto/audio/documento → propuesta → confirmación → resultado,
   reenvíos, caídas y aislamiento. Meta y plantillas aprobadas siguen siendo necesarios.
3. Voz privada: evaluar el adaptador existente con audios ficticios en castellano
   y catalán; medir precisión, latencia, memoria y coste antes de alojarlo.
4. Operaciones: ampliar CISO/CFO existentes con evidencia, alertas y costes reales,
   sin duplicar paneles ni registrar previsiones como gastos facturados.

Crear dentro la lógica, permisos y pruebas aporta control. Reinventar criptografía,
pagos o almacenamiento físico redundante no es una prioridad razonable. Autoalojar
voz implica infraestructura y mantenimiento, no coste cero.

En este paso no se ha modificado el runtime, contratado servicios, creado cuentas,
enviado datos, hecho commit/push ni desplegado. Guía de activación:
[[Copias-independientes-AWS]].
