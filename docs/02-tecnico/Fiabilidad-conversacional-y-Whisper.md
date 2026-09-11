# Fiabilidad conversacional y voz privada

8-sep-2026. Candidato local `codex/conversation-safety`, basado en
`be3ab2b7a326189e5bc3b2766dc337fe9380f015`. No publicado.

## Decisión de producto

Priorizar que el titular revise destino, importe y efecto antes de actuar. No
prometer comprensión perfecta ni sustituir validaciones fiscales o permisos.
El modo nuevo está apagado por defecto. No hay migración de base de datos.

## Correcciones y funcionamiento

- «Borra el gasto 5» no crea un gasto. Órdenes negativas, destructivas o de
  modificación no soportadas terminan sin escritura y remiten al apartado correcto.
- IVA/IRPF no contaminan el cliente. «IRPF del 2T» sigue siendo consulta y
  «por cambiar el termo» sigue siendo concepto de factura.
- Una cita sin cliente no crea la ficha «las». Se conserva la descripción.
- Un pago no crea una factura. Los pagos parciales se revisan en Facturas.
- Con `NOESIS_ASSISTANT_REVIEW_ENABLED=true`, las herramientas de escritura del
  chat, por reglas o IA, proponen antes de ejecutar. Las que no tienen contrato
  de revisión se bloquean en este modo y remiten a la app.
- Se resuelve el cliente dentro del negocio, se muestra nombre/ficha y se fija su
  identificador. Con varios clientes se pide el nombre completo. Un desconocido
  necesita alta explícita: no se crea de rebote al dictar una factura.
- Los gastos generales no se atribuyen por inferencia a clientes/proyectos.
  La asignación a proyecto sigue requiriendo Costes.
- La propuesta caduca a los 30 minutos, pertenece a negocio y conversación y se
  consume una vez. Web/audio comparten usuario y versión de sesión; WhatsApp usa
  el teléfono vinculado. No se confirma desde otra identidad o canal.

Ejemplo: «Factura a Marta López por revisión 121 euros IVA incluido» prepara un
borrador con cliente/ficha, concepto, base 100 €, IVA 21%, IRPF 0% y total 121 €.
No guarda hasta SÍ. NO descarta. «Corregir: factura a Marta López por revisión
242 euros IVA incluido» reemplaza la propuesta. Una corrección incompleta o un
audio ilegible descartan lo anterior para que otro SÍ no confirme datos antiguos.

Confirmar ejecuta los argumentos guardados, sin volver a interpretar el mensaje.
Si cambia la ficha o factura relevante, se pide revisar de nuevo. Preparar una
factura no equivale a emitir, entregar ni cobrar. Los documentos/entregas WhatsApp
mantienen su contrato previo de confirmación; esta capa no reescribe todos sus
flujos. Recibir otro documento invalida la propuesta conversacional anterior.

## Servicio privado de voz

`private_voice.py` expone `/health` y `/transcribe`. El Dockerfile
`infra/whisper/Dockerfile` usa faster-whisper, CPU int8, dos hilos y modelo `small`
multilingüe fijado por revisión. El modelo se descarga al construir la imagen;
Hugging Face queda offline en ejecución. El servicio no incluye BD ni necesita
claves de Meta, Stripe o correo.

Clave de servicio de al menos 32 caracteres, sin Swagger ni access logs. Audio
temporal eliminado al terminar, sin transcripciones en logs del servicio. El
hosting puede guardar sus propios logs/volcados: no activar depuración con datos
ni montar un volumen de audios.

Límites: 12 MiB, 120 segundos de audio, 30 segundos de subida, proceso de inferencia
de máximo 120 segundos y una solicitud simultánea por instancia. Saturación: 429.
Audio vacío, ilegible o dudoso: error sin acción. La inferencia corre en un proceso
separado que termina por timeout. Hay que fijar RAM/CPU también en el hosting.

`PrivateWhisperProvider` acepta HTTPS o HTTP de loopback/red privada Railway.
No sigue redirecciones con credenciales ni cambia automáticamente a Groq si falla.
Sin configuración privada conserva la selección anterior. No hay tarifa externa
por minuto; sí coste de infraestructura y mantenimiento.

Fuentes: [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[opciones de CTranslate2](https://opennmt.net/CTranslate2/environment_variables.html).

## Activación controlada

1. Revisar diff y `Registro-QA.md`. No mezclar cambios sin confirmar del directorio
   principal. Crear un entorno de pruebas antes de producción.
2. Crear un servicio separado de `web`, con contexto raíz del repositorio y
   Dockerfile `infra/whisper/Dockerfile`. **No se ha contratado ni creado aquí.**
3. Usar la misma región europea y red privada que la aplicación. Sin dominio
   público, BD, datos de clientes ni variables compartidas con secretos ajenos.
4. Generar una clave con `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   en un terminal privado. Guardarla en servicio y aplicación como
   `NOESIS_PRIVATE_WHISPER_TOKEN`; nunca enviarla por chat o al repositorio.
5. En la aplicación de pruebas, configurar
   `NOESIS_PRIVATE_WHISPER_URL=http://NOMBRE-REAL.railway.internal:8080`.
   Sustituir el nombre por el dominio privado real. `/health` comprueba modelo y
   configuración: un 200 no demuestra precisión ni credenciales de la transcripción.
6. Fijar presupuesto y límites de recursos; medir RAM/latencia con concurrencia.
   No dimensionar producción a partir de una sola nota sintética en Windows.
7. Activar `NOESIS_ASSISTANT_REVIEW_ENABLED=true` en pruebas y reiniciar la app.
   Mantener producción apagada hasta aceptación y decisión explícita de publicación.
8. Probar nombres parecidos, importes/decimales, IVA/IRPF, silencio, ruido, ca/es y
   acentos. Comparar audio → texto → propuesta → registro. Rechazar y corregir
   siempre debe funcionar. No aceptar errores silenciosos de cliente/total/destino.
9. Recorrer móvil y Meta reales y acordar un piloto limitado. Pruebas locales no
   equivalen a entrega real de WhatsApp ni a precisión sobre documentos reales.

## Evidencia de voz

faster-whisper 1.2.1 instalado en un venv temporal. Modelo `small` y nota SAPI
sintética en español. MKL de Windows falló al cargar (`mkl_malloc`); con
`CT2_USE_MKL=0` funcionó. No se modificó globalmente el equipo.

Transcripción directa: 10,69 s. Prueba real del servicio HTTP local, autenticación,
adaptador y proceso aislado: health 200 y transcripción en 7,92 s, sin mocks.
Identificó Marta López y 121 euros, pero «IVA incluido» pasó a «y va incluido».
Se añadió regresión para bloquear esa ambigüedad y pedir orden corregida.
Esto no mide precisión general. Faltan corpus real, catalán, ruido y decimales.

Docker no está instalado aquí: build Linux y red privada Railway pendientes.
No afirmar que el servicio de producción está operativo.

## Riesgos y reversión

Reclamar y ejecutar son pasos separados: se evita repetir una propuesta ante dos
SÍ, pero un cierre entre ambos pasos puede consumirla sin ejecutarla. Revisar el
registro antes de repetir tras un error; no hay garantía transaccional de extremo
a extremo. La comprobación de cambios tampoco bloquea todas las ediciones
concurrentes de otros canales. Ampliar control transaccional antes de escalar.

Una propuesta estructuralmente válida puede interpretar mal una frase. La revisión
humana sigue siendo la barrera final, no una puntuación de confianza. Cualquier
orden o consulta nueva invalida la propuesta anterior; explicarlo en el piloto.

Rollback sin migración: apagar flag, retirar URL privada si se quiere recuperar el
proveedor anterior y revertir el código. Antes de reactivar, dejar vencer propuestas
(30 min) o eliminarlas solo en el entorno afectado con procedimiento autorizado.
No restaurar una base entera para revertir este código.

## Orden de negocio pendiente

Primero cerrar revisión, build Linux y corpus; después piloto con confirmaciones.
En paralelo: resolver rechazo de correo y comprobar recuperación de acceso con
destinatario controlado; contratar/configurar copia independiente y restaurarla
fuera de Railway; recorrer alta, cambio, cancelación y recuperación de pagos Stripe
en sandbox. No dar esos frentes por resueltos porque exista un adaptador o botón.
Este candidato no compra recursos ni cambia producción.
