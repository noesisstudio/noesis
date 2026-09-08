# Inteligencia de Bynoesis: aprendizaje supervisado

Fecha: 8 de septiembre de 2026. Candidato local, no publicado ni activado.

## Qué hemos construido y qué no

Bynoesis puede mejorar su interpretación mediante correcciones aprobadas por cada
negocio. Esta capa complementa las reglas locales y los adaptadores de IA existentes;
no es un nuevo modelo fundacional, no reentrena pesos ni modifica su propio código.
No podemos garantizar que entienda cualquier mensaje ni que nunca se equivoque.
La protección consiste en preguntar cuando falta información y mostrar la acción
antes de ejecutarla, no en presentar una respuesta probable como un hecho.

## Ejemplo real cubierto por pruebas

1. El cliente escribe «lo del carburante de siempre». Sin una interpretación
   concreta, el camino local pide aclaración y no registra un gasto.
2. Responde «corregir: gasté 35 euros en gasolina». Se prepara una propuesta.
3. Confirma con «sí». Se registra una vez y se ofrece recordar la equivalencia.
4. Solo si escribe «APRENDER» se conserva esa expresión para su negocio.
5. La próxima vez aparece de nuevo la propuesta de 35 euros para confirmar o
   corregir. No se deduce que cualquier compra futura cueste lo mismo.
6. «Mis expresiones» permite verlas; «olvidar expresión N» elimina la elegida.

La equivalencia es literal, normalizando acentos y mayúsculas; no es una regla
general sobre clientes, importes o documentos. No se aprende de un simple «sí»,
de una acción fallida ni de una propuesta pendiente. Tampoco se aprenden órdenes
de emisión, cobro, permisos o borrado, ni se sustituyen intenciones ya conocidas.

## Aclaraciones paso a paso

Una petición incompleta de factura abre un diálogo persistente: cliente, concepto,
importe con «IVA incluido» o «más IVA», revisión y confirmación. Un nombre ambiguo
requiere aclaración; un cliente inexistente requiere crear primero su ficha.
No se asigna un gasto a un cliente o proyecto por una asociación aprendida.
Esta primera guía es para facturas: no implica que todos los procesos dispongan
ya de conversaciones parciales equivalentes ni cobertura completa en catalán.

## Barreras de seguridad

- Las propuestas y ofertas de aprendizaje pertenecen al negocio y al actor del
  canal; otra conversación no puede aprobarlas. Las expresiones aprobadas se
  comparten entre usuarios autorizados de ese mismo negocio, nunca entre negocios.
- La interpretación se vuelve a validar al guardar y reutilizar una expresión.
  Un cambio de significado del parser la invalida; no es una firma criptográfica
  ni una defensa ante un administrador que comprometa directamente la base de datos.
- Las expresiones no se insertan como instrucciones de sistema para el modelo.
- La telemetría nueva contiene tipos de evento y versión, no mensajes, nombres,
  importes o documentos. Sus errores no reintentan operaciones de negocio.
- Las ofertas y aclaraciones tienen vigencia lógica de 15 minutos. La limpieza
  física utiliza los mecanismos existentes; la caducidad no garantiza borrado
  físico exactamente al minuto 15. Las propuestas de acción conservan su propio plazo.
- Las equivalencias aprobadas sí contienen la frase y la orden: son memoria del
  negocio visible y eliminable. No se debe describir todo el sistema como libre de
  datos personales. El historial y los proveedores autorizados mantienen sus
  políticas existentes; esta capa no concede un nuevo consentimiento externo.

## Control operativo y mejora continua

`GET /api/{business_id}/assistant/learning?days=7` ofrece recuentos de aclaraciones,
propuestas, correcciones, resultados y uso/aprobación de expresiones, además de
las reglas visibles. Reutiliza autenticación y aislamiento del negocio. El informe
local `python -m noesis.learning --business-id N --days 7` no incluye las frases.
La ventana admite entre 1 y 90 días. No se ha añadido una pantalla administrativa.

Son recuentos de eventos, no precisión del modelo, usuarios únicos ni detección
universal de errores. Sirven para priorizar pruebas: identificar un caso, reproducirlo
con datos sintéticos, corregirlo, añadir regresión y aprobar la publicación.
No hay entrenamiento global con datos de clientes, tarea diaria de despliegue ni
incremento automático de autonomía. Un futuro corpus debe tener autorización,
minimización y evaluación separada antes de cambiar modelos o reglas.

## Activación y rollback

Por defecto ambos flags están apagados:

```dotenv
NOESIS_ASSISTANT_REVIEW_ENABLED=false
NOESIS_ASSISTANT_LEARNING_ENABLED=false
```

El aprendizaje solo funciona con ambos activados. Validar primero en un entorno
aislado con datos sintéticos y después en un piloto autorizado. No activar por
tener una suite verde: faltan WhatsApp/voz reales, conversaciones variadas y
concurrencia en PostgreSQL. Esta modificación no contrata ni aloja un modelo.

Para retirar solo el aprendizaje, apagar su flag y reiniciar el servicio; la
revisión puede seguir activa. No hay migración: se reutilizan memorias, propuestas
y eventos existentes. Las memorias quedan inertes y pueden borrarse explícitamente;
no se deshacen facturas o gastos ya confirmados. Al reactivar, comprobar memorias
persistentes y dejar vencer las propuestas anteriores. No restaurar toda la BD
para revertir esta funcionalidad.

## Verificación y siguiente decisión

19 pruebas nuevas cubren aprobación, aislamiento, caducidad, descarte, reutilización,
corrección, diálogo de factura y WhatsApp sintético. Humo HTTP con sesión sintética:
aprendizaje, gasto único, factura de 121 euros y rechazo 403 de otro negocio.
El resultado de la regresión completa se registra en `Registro-QA.md`.

La decisión recomendada es validar esta capa antes de ampliar autonomía. Para
lenguaje abierto seguimos necesitando un modelo capaz y evaluado; para voz,
el servicio Whisper candidato necesita todavía validación real. Tener memoria
supervisada no sustituye esas dos capacidades ni certifica su fiabilidad.
