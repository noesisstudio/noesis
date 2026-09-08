# Subencargados y transferencias internacionales

> - Creado: 2026-09-08 · Última revisión: 2026-09-08 · Próxima revisión: 2026-12-08
> - Responsable: founder (Xavier).
> - Base: arts. 28.2 y 28.4 RGPD (subencargados) y arts. 44-49 (transferencias).

## 1. Registro de subencargados

Estado: `firmado` = DPA aceptado y archivado; `pendiente` = servicio en uso o
previsto sin DPA archivado. Un subencargado sin DPA firmado **no debe recibir
datos reales de clientes**.

| Subencargado | Servicio | Datos que ve | País de tratamiento | Jurisdicción matriz | Garantía | DPA |
|---|---|---|---|---|---|---|
| Railway | Alojamiento y base de datos | Todos los del producto | UE si se fija la región; verificar | EE. UU. | CCT + evaluación § 3 | pendiente |
| Proveedor de copias S3 (Scaleway u OVHcloud) | Copias externas | Copia completa, cifrada en cliente | Francia | UE | No hay transferencia | pendiente de alta |
| Brevo | Correo transaccional | Email, nombre, contenido del aviso | Francia | UE | No hay transferencia | pendiente |
| Stripe | Cobro de la suscripción | Identidad, NIF, dirección, importes | UE/EE. UU. | EE. UU. (Stripe Payments Europe en Irlanda) | CCT + marco de adecuación | pendiente |
| Meta Platforms | WhatsApp Business API | Teléfono y contenido de los mensajes | UE/EE. UU. | EE. UU. | CCT + marco de adecuación | pendiente |
| Anthropic | Asistente IA, solo si el negocio lo activa | Fragmento de texto no resuelto localmente | EE. UU. | EE. UU. | CCT | pendiente |
| Groq | Transcripción de voz, opcional | Audio y transcripción | EE. UU. | EE. UU. | CCT | pendiente |
| Proveedor compatible configurable | IA alternativa | Igual que Anthropic | Según `NOESIS_COMPAT_AI_REGION` | Variable | A verificar antes de activar | pendiente |
| Google | Acceso OAuth y correo del founder | Email e identificador | UE/EE. UU. | EE. UU. | CCT + marco de adecuación | pendiente |
| GitHub | Código y CI | Ningún dato personal de clientes | EE. UU. | EE. UU. (Microsoft) | CCT | pendiente |

Mantener esta tabla sincronizada con la que se publica en `/encargado-tratamiento`:
si divergen, el cliente puede alegar que no fue informado de un subencargado.

## 2. Regla de altas y bajas

1. Antes de conectar un servicio nuevo: rellenar
   [`plantillas/Alta-subencargado`](plantillas/Alta-subencargado.md).
2. Firmar el DPA del proveedor y archivarlo fuera del repositorio.
3. Añadirlo a esta tabla, a la plantilla `encargado-tratamiento.html` y al
   [`RAT`](RAT-Registro-actividades.md).
4. Informar a los clientes con antelación razonable, según exige el art. 28.2 y el
   propio DPA de Noesis, dándoles la posibilidad de oponerse.
5. Al dar de baja: confirmar por escrito la supresión o devolución de los datos y
   anotar la fecha en [`Registro-de-evidencias`](Registro-de-evidencias.md).

## 3. Evaluación de transferencias (TIA)

Para cada proveedor cuya matriz esté en EE. UU., aunque trate los datos en la UE:

**Riesgo identificado.** La matriz puede estar sujeta a requerimientos de acceso
de autoridades estadounidenses (CLOUD Act, FISA 702 según el tipo de proveedor)
con independencia de dónde estén los servidores.

**Garantía aplicada.** Cláusulas contractuales tipo de la Decisión (UE) 2021/914,
más el marco de adecuación UE-EE. UU. cuando el proveedor esté certificado.
**Comprobar la certificación de cada proveedor en la lista oficial antes de darlo
por bueno**, y volver a comprobarlo si el marco es anulado o suspendido: ya ocurrió
dos veces.

**Medidas complementarias** (Recomendaciones 01/2020 del CEPD):

- Cifrado en tránsito siempre; cifrado en cliente para las copias, con la clave
  fuera del proveedor. Es la medida más eficaz de la lista: quien reciba un
  requerimiento no puede entregar texto claro.
- Minimización antes de enviar: a los proveedores de IA solo viaja el fragmento no
  resuelto localmente, nunca la base de datos ni los documentos completos.
- Consentimiento explícito del negocio antes de activar cualquier IA externa, con
  el proveedor, el país y la garantía a la vista.
- Preferencia declarada por proveedores europeos en cada renovación: es lo único
  que elimina el riesgo en vez de documentarlo.

**Conclusión.** Aceptable para el piloto con las medidas anteriores. Para el nivel
producción, la dirección marcada en
[`Plan-Datos-Servidores-Copias`](Plan-Datos-Servidores-Copias.md) es mover
alojamiento, base de datos y copias a proveedores con matriz en la UE, dejando las
transferencias reducidas a servicios opcionales que el cliente activa a sabiendas.

**Pendiente externo.** Esta evaluación es de ingeniería. La validación jurídica y
la firma de los DPA siguen sin hacerse y son requisito antes de tratar datos
reales de terceros a escala.
