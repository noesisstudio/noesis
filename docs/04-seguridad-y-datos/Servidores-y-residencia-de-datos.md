# Servidores y residencia de datos

> **Aviso.** No es asesoramiento jurídico. Verificación hecha el **3 de septiembre de
> 2026** contra la documentación pública de Railway y contra el código del
> repositorio. Complementa [[RGPD-estado-y-plan]] y [[Despliegue]].

## La premisa, corregida

**No existe ninguna «licencia RGPD».** Ningún proveedor de hosting del mundo la
tiene, porque no se emite. Si alguien te la ofrece, desconfía.

Lo que el RGPD sí exige de un proveedor de alojamiento es cuatro cosas concretas:

1. Un **contrato de encargado del tratamiento** (art. 28) firmado entre él y tú.
2. Una **base legal para la transferencia** si los datos salen del Espacio Económico
   Europeo (arts. 44-49).
3. **Medidas de seguridad** demostrables (art. 32).
4. **Transparencia sobre sus propios subencargados**.

Railway cumple las cuatro, y con buena nota:

| Requisito | Estado de Railway |
|---|---|
| Contrato de encargado (DPA) | Publicado y **autofirmable** en `railway.com/legal/dpa` |
| Transferencia a EE. UU. | **Certificada en el Marco de Privacidad de Datos UE-EE. UU.**, además de cláusulas contractuales tipo. Es la base más sólida posible: adecuación, no solo cláusulas |
| Seguridad | **SOC 2 Tipo II** y SOC 3; informes de pentest bajo petición en `trust.railway.com` |
| Subencargados | Lista publicada: Google Cloud (infraestructura), Cloudflare (CDN), Stripe (facturación) |
| Región europea | **Sí**: EU West Metal, Ámsterdam (`europe-west4-drams3a`) |

**Conclusión: Railway sirve perfectamente para RGPD.** Quien te dijo lo contrario
estaba pensando en otra cosa —probablemente en residencia de datos, que sí es un
problema real y sí lo tienes.

---

## Los tres problemas que sí tienes, y son tuyos, no de Railway

### P1 · Casi con seguridad no has firmado el DPA

El contrato de Railway es **autoservicio**: existe, pero no se aplica solo. Hay que
entrar y firmarlo.

Mientras no lo firmes, tienes un encargado del tratamiento **sin contrato del art.
28** procesando datos personales. Y eso no es un incumplimiento de Railway: es tuyo.
Es además el primer papel que te va a pedir una gestoría, y el que la Agencia pide
primero si algún día pregunta.

**Arreglo: diez minutos en `railway.com/legal/dpa`.** Guarda el PDF firmado junto al
registro de actividades del art. 30 que hay que crear.

### P2 · Los datos están, casi seguro, en Estados Unidos

`railway.json` **no fija ninguna región**, y Railway despliega en la región preferida
de tu cuenta —históricamente US West— salvo que la cambies a mano en el panel.

No puedo verificarlo desde aquí: la región vive en el panel de Railway, no en el
repositorio. **Compruébalo hoy**, en Settings → Scale → Regions de cada servicio (el
de la web *y* el de Postgres). Si pone `us-west2` o `us-east4`, entonces ahora mismo
están en California o Virginia:

- La base de datos entera: clientes, facturas, importes, NIF.
- El volumen `/data/uploads`: **los papeles escaneados**. Facturas, tickets,
  documentos con nombres, direcciones y a veces el DNI de terceros que nunca
  aceptaron nada de Bynoesis.

¿Es ilegal? **No.** Con la certificación de Railway en el Marco de Privacidad de
Datos, la transferencia tiene amparo. ¿Es vendible a una gestoría española que te
confía la cartera de cien autónomos? **Mucho más difícil.** Es la pregunta que hacen,
y «está en Estados Unidos pero es legal» es una respuesta que pierde ventas.

**Arreglo: mover los servicios a `europe-west4-drams3a` (Ámsterdam).**

Y hay una razón de calendario que lo vuelve urgente: **cambiar de región con un
volumen montado obliga a migrar el volumen, y eso causa una parada** proporcional a
su tamaño. Hoy el volumen está prácticamente vacío y no hay clientes reales. Con tres
pilotos dentro, la misma operación es una ventana de mantenimiento negociada con
gente que está trabajando. **Es el momento más barato que va a haber.**

Detalle operativo: `railway.json` no admite un campo `region` suelto, pero sí
`multiRegionConfig`, que declara réplicas por región. Merece la pena comprobarlo
contra el esquema y, si funciona, dejar la región **fijada en el repositorio** en vez
de en un panel que nadie vuelve a mirar. Si no, al menos anótala en [[Despliegue]] y
en la puerta de salida de [[Seguridad-operativa]].

### P3 · Corregido: la copia ya no adivina una región

Este es el peor de los tres, y estaba escondido en el código:

```python
# configuración vigente
BACKUP_S3_REGION = os.getenv("NOESIS_BACKUP_S3_REGION", "").strip()
```

El hallazgo original era un valor por defecto `us-east-1`. El candidato actual lo
elimina: si se activa S3 sin región de firma, nombre del proveedor y residencia
contractual declarada, la subida falla cerrada antes de abrir una conexión. Esto
evita inferir residencia a partir de un endpoint, pero todavía exige configurar y
probar un destino real.

Y las copias son la peor categoría de dato para equivocarse: son la copia que **más
tiempo vive**, la que nadie vuelve a mirar, y la que sobrevive a los borrados. Un
cliente ejerce su derecho de supresión, borras bien la base de datos… y sigue
existiendo entero en un bucket en Virginia.

Además, `NOESIS_BACKUP_DIR` apunta por defecto a una carpeta **junto a la propia base
de datos**. Una copia en el mismo volumen que el original no es una copia de
seguridad: es un archivo más que se pierde con él.

**Arreglo restante:**
- Fijar `NOESIS_BACKUP_S3_REGION` explícitamente en producción a `eu-west-1`,
  `eu-central-1` o el equivalente del proveedor que uses.
- Fijar `NOESIS_BACKUP_S3_PROVIDER_NAME` y `NOESIS_BACKUP_S3_DATA_REGION` con lo
  que diga el contrato, no con una suposición técnica.
- Declarar ese proveedor de copias en la lista de subencargados, que ya está
  incompleta por otros motivos (ver A1 de [[RGPD-estado-y-plan]]).
- Confirmar que `NOESIS_BACKUP_DIR` apunta al volumen persistente y que la copia
  externa sale de la infraestructura, como ya exige la puerta de salida de
  [[Seguridad-operativa]].

---

## Lo que queda después: la Ley CLOUD

Aunque muevas todo a Ámsterdam, queda un residuo que conviene entender para no
venderlo mal:

Railway es una **empresa estadounidense**, y su infraestructura es Google Cloud, otra
empresa estadounidense. La Ley CLOUD permite a las autoridades de EE. UU. reclamar
datos a una empresa sujeta a su jurisdicción **con independencia de dónde estén
almacenados físicamente**. Ámsterdam reduce mucho la exposición; no la elimina.

Esto no invalida nada de lo anterior: es exactamente la situación de la inmensa
mayoría del software español, incluida buena parte del que usan las gestorías. Pero
**no digas «tus datos nunca salen de Europa»** si el proveedor es estadounidense. Di
«se alojan en la Unión Europea», que es verdad y es suficiente.

Cuándo dejaría de ser suficiente: si una gestoría te lo exige por escrito, si vendes
a administración pública, o si aparece un cliente con datos de salud. Entonces toca
proveedor europeo, y no antes.

---

## Alternativas, con el coste real

Por si alguien te empuja a moverte. Mi recomendación está al final.

| Opción | A favor | En contra |
|---|---|---|
| **Railway, región de Ámsterdam** | Cero trabajo nuevo. DPA, marco de adecuación y SOC 2 ya resueltos. El despliegue, las migraciones en pre-deploy y el healthcheck siguen igual | Empresa estadounidense: queda el residuo de la Ley CLOUD |
| **PaaS europeo** (Clever Cloud, Scaleway, OVHcloud) | Empresa y datos europeos: desaparece el residuo. Experiencia parecida a Railway | Migrar el despliegue, el volumen y Postgres. Días de trabajo y una ventana de riesgo |
| **Servidor propio** (Hetzner + Coolify o similar) | El más barato con diferencia y totalmente europeo | **Te conviertes en administrador de sistemas**: parches, copias, monitorización, respuesta a incidentes. Tu rol es negocio y dirección; esto compra ahorro pagando con tu tiempo y con riesgo operativo |

**Recomendación: quedarte en Railway y mover la región.** Las tres piezas legales que
importan —contrato, base de transferencia y certificación de seguridad— ya están
resueltas por el proveedor, y replicarlas por tu cuenta en un servidor propio te
costaría meses. Migrar de proveedor antes de tener un solo cliente de pago es
optimizar la respuesta a una pregunta que todavía no te ha hecho nadie.

---

## Qué hacer, en orden

Todo esto es de hoy, y ninguna pieza depende de la constitución de la sociedad ni del
abogado:

1. **Firmar el DPA** en `railway.com/legal/dpa` y archivar el PDF. Diez minutos.
2. **Comprobar la región** de los dos servicios en el panel. Cinco minutos.
3. **Mover a `europe-west4-drams3a`** si están fuera, **ahora que el volumen está
   vacío**. Es la única de las cuatro que tiene ventana: se encarece con cada cliente.
4. **Configurar explícitamente** región de firma, proveedor y residencia, y probar
   una restauración. El código ya no aplica una región estadounidense por defecto.

Después, cuando toque el bloque de RGPD: añadir el proveedor de copias a la lista de
subencargados, anotar la cadena Railway → Google Cloud → Cloudflare en el registro de
actividades, y dejar la región escrita en [[Despliegue]] para que no vuelva a ser un
dato que solo vive en un panel.

---

## Fuentes

- [Compliance | Railway Docs](https://docs.railway.com/enterprise/compliance)
- [Data Processing Addendum | Railway](https://railway.com/legal/dpa)
- [Privacy Policy | Railway](https://railway.com/legal/privacy) — certificación en los marcos UE-EE. UU., Reino Unido-EE. UU. y Suiza-EE. UU.
- [Regions | Railway Docs](https://docs.railway.com/reference/deployment-regions)
- [Config as Code | Railway Docs](https://docs.railway.com/config-as-code/reference)
