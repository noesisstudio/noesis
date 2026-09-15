# Cerebro local: piloto de facturas y correcciones

## Alcance de esta entrega — 15-sep-2026

Se amplía el código existente, sin sustituir el SaaS ni migrar datos. Esta entrega
es un planificador determinista acotado, no un modelo entrenado ni comprensión
universal. Usa stdlib, no hace llamadas a IA y no incorpora dependencias.

`local_invoice.py` prepara planes sin efectos. `action_review.py` resuelve el
cliente del negocio, presenta las líneas, calcula con las funciones nativas de
facturación y persiste una propuesta. Solo SÍ crea el borrador. La emisión exige
otra propuesta y otra confirmación; una descarga no emite.

## Activación controlada

Por defecto está apagado. En un entorno aislado de pruebas se necesitan ambas:

```env
NOESIS_ASSISTANT_REVIEW_ENABLED=true
NOESIS_LOCAL_PLANNER_ENABLED=true
NOESIS_ASSISTANT_LEARNING_ENABLED=false
```

No activar en producción solo por tener las pruebas locales correctas. Antes:
suite completa, PostgreSQL, regresión de web/WhatsApp y piloto físico. No requiere
credenciales de IA. Mantener apagados los proveedores externos durante su prueba.

## Recorrido implementado

Con una ficha existente llamada Marta López:

1. «Crea una factura para Marta López con 2 horas de trabajo a 35 euros y 3 piezas
   a 12,50 euros, más IVA del 21%»: propone base 107,50 y total 130,08.
2. «No, las piezas eran 4»: reemplaza la propuesta, total 145,20; no crea aún.
3. «cambia la linea 2 precio a 15 euros»: cambia solo ese precio y vuelve a mostrar
   el resultado. También admite «cambia linea 2 cantidad a 5».
4. «cambia el cliente a Ana Ruiz»: resuelve la ficha existente y solicita confirmar.
5. «sí»: crea un solo borrador. Repetir SÍ no crea otro.
6. En el chat web: «pásame el PDF» devuelve el enlace autenticado de ese documento.
   «emítela» propone la emisión del documento enfocado, no la ejecuta directamente.

Admite también la forma catalana «Fes una factura per a Marta López amb 2 hores a
35 euros i 3 peces a 12,50 euros més IVA del 21%». No significa soporte completo
de todas las formas catalanas. El texto de salida conserva el idioma de producto.

La gramática exige precios netos y un IVA explícito 0/4/10/21 al final. No interpreta
en esta ruta varias líneas con precios finales/IVA incluido, descuentos o retención
dictada. No ignora palabras finales: si no encaja la orden completa, no aprovecha
una coincidencia parcial. Los tickets respetan el límite configurado del motor.

## Estado y seguridad

- Propuestas aisladas por negocio, actor y canal; el modelo no proporciona permisos.
- El cliente debe existir y resolverse inequívocamente. No hay altas de rebote.
- Una corrección reclama la versión anterior bajo transacción y crea un ID nuevo;
  conserva la caducidad original. Una corrección concurrente antigua no resucita
  una propuesta confirmada ni borra su sucesora.
- Las confirmaciones reclaman la propuesta una sola vez. Un fallo no la reejecuta.
- Antes de emitir se comprueba la huella de la factura dentro de la transacción
  del motor nativo, además de verificar el estado contra la vista previa.
- El foco PDF almacena solo un ID verificado durante diez minutos, por actor y
  negocio. No usa como sustituto «la última factura del negocio».
- Memoria de aprendizaje y modelos privados no se activan. No se exportan ejemplos
  de clientes ni se reentrena nada. El corpus de regresión es sintético.
- WhatsApp conserva el ID real al confirmar el borrador por la ruta revisada;
  sus envíos posteriores siguen utilizando el adaptador y los controles existentes.

Un SÍ genérico confirma la propuesta vigente de la conversación. Esta entrega no
añade botones con firma de versión ni resuelve todas las carreras de mensajes
nuevos; revisar ese contrato antes de ampliar a múltiples usuarios concurrentes
que compartan una conversación. La interfaz HTTP mantiene sus permisos actuales.

## Pruebas y reversión

`tests/test_local_invoice.py`: planes ES/CA, céntimos, rechazo de órdenes parciales,
correcciones, cliente inexistente, separación entre actores/negocios, doble SÍ,
caducidad, referencias PDF y flujo de entrada WhatsApp con transporte simulado.
El cálculo de la vista previa se contrasta con las líneas realmente guardadas.

Comando dirigido:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
.venv/Scripts/python.exe -m unittest tests.test_local_invoice.LocalInvoiceTests tests.test_intent_safety.IntentSafetyTest tests.test_conversation_safety.ConversationSafetyTests -q
```

Para revertir la nueva ruta: desactivar `NOESIS_LOCAL_PLANNER_ENABLED`; no hace
falta restaurar datos ni eliminar tablas. Los borradores creados siguen siendo
facturas nativas editables. Las propuestas pendientes se descartan o caducan; no
confirmar propuestas de una versión anterior tras un cambio de despliegue.

## Pendientes, sin promesas de completitud

- Gramática más amplia, importes incluidos/descuentos/IRPF multilínea y elección
  de cliente mediante opciones; siempre contra el corpus, no reglas improvisadas.
- Correcciones de gastos, presupuestos, agenda y proyectos; hoy no heredan este
  planificador. Memoria de objetivos compuestos entre dominios pendiente.
- Enviar PDF después de crear/emitir en una sola orden, con reintento verificable.
- Conciliación económica y validación/deduplicación de facturas recibidas del
  informe QA, que son otro bloque de integridad y no una capacidad del modelo.
- Evaluación del modelo privado con corpus reservado antes de provisionar servidor.
- PostgreSQL, móvil y entrega física Meta. No equivalen a los tests con mocks.

Los resultados concretos de ejecución están en `../Registro-QA.md`.
