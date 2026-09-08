# Centro de mando Bynoesis — 7 de septiembre de 2026

## Qué cambia

La administración es un espacio interno separado del negocio del autónomo.
Dirección abre con prioridades y deriva a seis departamentos: Cuentas y soporte,
Marketing y ventas, Finanzas y consumo, Operaciones, Ingeniería y seguridad y
Administración legal. Cada vista tiene un único encabezado, explicación de su
alcance y acciones existentes agrupadas por tarea. Se eliminan los emoticonos.

- Navegación activa y enlaces profundos; menú plegable en móvil. Sin JavaScript
  todos los apartados y formularios siguen disponibles.
- Búsqueda de cuentas por nombre, correo o teléfono, ignorando tildes; teléfono
  del titular separado del canal comercial. Las acciones de acceso se despliegan
  deliberadamente y conservan sus permisos, formularios y auditoría.
- Actualizar recarga los datos conservando el departamento. La fecha de lectura
  es visible: no se promete monitorización en tiempo real.
- Consumo mensual observado por proveedor/modelo y cuenta; API de consulta solo
  para el administrador, auditada, sin credenciales ni contenido de documentos.
- Ingresos de catálogo, costes registrados y estimaciones se distinguen de la
  caja y de la facturación de los clientes. Falta de datos no se presenta como cero.
- Marketing distingue páginas vistas de visitantes y hitos de adopción de un
  embudo por cohortes. Entregas distingue registros de confirmaciones de envío.

## Alcance de esta publicación

Solo panel, navegación, consultas administrativas de consumo y dependencias.
Sin migraciones ni nuevos privilegios. No cambia facturación, cobros, WhatsApp,
extracción, agenda, documentos ni estrategia de copias. Los otros cambios del
árbol local permanecen fuera del commit. Base: `f8df1bc`.

Los patrones de navegación y separación por tarea se apoyan en la documentación
de [Stripe Dashboard](https://docs.stripe.com/dashboard/basics) y
[Intercom](https://www.intercom.com/help/en/articles/15432088-your-workspace-settings),
con los tokens y la marca propios. No se han copiado sus métricas ni sus datos.

## Validación

Pruebas automáticas sobre una copia aislada de los archivos seleccionados, no
sobre el árbol local con otros candidatos. Resultado final en `Registro-QA.md`.
La copia aislada también sirve el navegador local con base de datos sintética.

Verificados: navegación, búsqueda sin tildes, estado sin resultados, despliegue
de acciones sin ejecutarlas, recarga con departamento conservado, menú móvil
cerrado tras navegar, una sola sección visible y ausencia de desbordamiento
horizontal a 390 px. Consola del navegador sin errores durante esta revisión.

Comparación de Finanzas a igual anchura/altura y estado inicial:

- Antes: `qa/admin-v2-2026-09-07/01-before-finance.jpg`.
- Después: `qa/admin-v2-2026-09-07/05-finance-final.jpg`.
- Dirección móvil: `qa/admin-v2-2026-09-07/04-direction-mobile.jpg`.

## Límites y siguiente control

No equivale a auditoría WCAG completa ni prueba de Safari físico. Quedan para
validación externa Postgres, datos/proveedores reales y conciliación de gastos.
No existen aún roles de empleado por departamento, atribución publicitaria
completa, CAC, SLA ni cobertura de costes de todas las APIs. El panel no los inventa.

Tras el push, comprobar la huella del commit en `/health` y `/ready`, la CI y el
acceso administrativo autorizado. Un push no implica por sí solo deploy sano.
Rollback: revertir el commit del panel; no requiere rollback de base de datos.
