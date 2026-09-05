# Design QA — sitio público Bynoesis

- **Fuente visual:** `C:\Users\mikic\.codex\generated_images\019f52cc-5f50-7bf1-861e-1ae7f775c7be\exec-5a2c6bb9-2616-4ec9-9708-18007de7e13e.png`
- **Captura implementada:** `C:\Users\mikic\Documents\noesis-codex-internal-brain\tmp\design-qa\home-desktop-pass1.png`
- **Comparación completa:** `C:\Users\mikic\Documents\noesis-codex-internal-brain\tmp\design-qa\home-source-vs-pass1.png`
- **Comparación enfocada:** `C:\Users\mikic\Documents\noesis-codex-internal-brain\tmp\design-qa\home-hero-focus-pass1.png`
- **Viewport solicitado:** 1440 × 1024 px.
- **Captura efectiva:** 1425 × 1013 px (área útil comunicada por el navegador integrado).
- **Estado:** Home pública, escritorio, sesión local existente.

## Evidencia de comparación completa

La implementación conserva la composición aprobada: cabecera crema compacta, hero
verde bosque, promesa editorial a la izquierda, flujo operativo y producto realista a
la derecha, seguido por el bloque de proceso sobre lienzo crema. La mayor altura del
titular en la implementación es una adaptación intencionada a la tipografía Fraunces
autoalojada y al texto real; no desplaza la acción primaria ni oculta el producto.

## Evidencia enfocada

La comparación del hero confirma:

- navegación, CTA y marca alineados con la referencia;
- jerarquía serif/sans y paleta crema/verde coherentes;
- demostración de producto legible, sin tarjetas flotantes arbitrarias;
- confirmación humana visible antes de facturar;
- ningún texto, badge o botón solapado;
- el bloque de confianza queda dentro del primer encuadre.

## Superficies de fidelidad

- **Tipografía:** Fraunces para voz y titulares; Inter/fallback del sistema para datos.
  Pesos, alturas de línea y contraste son coherentes con la referencia.
- **Espaciado y ritmo:** cabecera contenida, hero equilibrado y separación clara entre
  promesa, prueba de producto y flujo. No hay tarjetas dentro de tarjetas fuera de la
  propia simulación de interfaz.
- **Color:** `#14463b`, `#2e8b74`, crema y blanco mapeados a los tokens del proyecto;
  no se introducen degradados en el nuevo sistema público.
- **Imagen:** la única ilustración nueva es un activo raster generado y optimizado a
  WebP; marca y producto no se sustituyen con SVG improvisados ni CSS decorativo.
- **Copy:** propuesta, límites y confirmación están expresados en lenguaje humano. No
  se publican valoraciones, logos, cifras ni testimonios inventados.
- **Iconos:** se prioriza texto y numeración funcional. No se añaden iconos de familias
  incompatibles ni glifos decorativos.
- **Accesibilidad:** estructura semántica, enlaces con destino real, acordeones nativos,
  foco heredado del sistema y navegación móvil mediante `details/summary`.

## Comprobaciones funcionales

- Home, Producto, Precios, Equipo, Preguntas, Login, Onboarding y las seis rutas
  legales responden HTTP 200.
- La nueva ruta `/equipo` aparece en navegación de escritorio, móvil y footer.
- Los precios visibles usan una única fuente: 29 / 49 / 99 € + IVA.
- La beta de 99 € está en el flujo normal de la tarjeta, no posicionada sobre el copy.
- La captura no mostró errores ni avisos en consola.
- El navegador integrado se cerró después de la captura; por estabilidad se evitó una
  segunda sesión y las rutas restantes se verificaron por HTTP y pruebas automáticas.

## Historial de comparación

### Pase 1

- No se detectaron P0, P1 ni P2 accionables.
- Diferencias aceptadas: el titular ocupa más líneas para preservar el copy real y la
  interfaz de producto usa texto nativo en lugar de iconos inventados.
- No se aplicaron correcciones visuales posteriores a la captura; por ello esta misma
  evidencia constituye el pase final.

## Seguimiento P3

- Sustituir el bloque honesto de pilotos por testimonios reales solo cuando exista
  autorización, nombre y texto verificable.
- Revisar una captura móvil real cuando el navegador integrado vuelva a ser estable.

## Iteración funcional · 2026-07-16

- La interfaz de producto del hero deja de ser decorativa: incluye ocho pestañas
  accesibles, datos simulados coherentes y navegación por ratón o teclado.
- Los precios mensual/anual comparten catálogo y actualizan importe, equivalencia,
  ahorro, enlace de alta y campo de checkout. El anual ofrece un mes gratis.
- Esta iteración conserva la dirección visual del pase aprobado. No se abrió una
  nueva sesión del navegador integrado porque el usuario pidió evitarla tras cierres
  repetidos de la aplicación; por tanto no se afirma una nueva comparación visual.
  Su QA se limita de forma explícita a HTML, CSS responsive, JavaScript, rutas y
  pruebas automáticas.

## Iteración de fidelidad · 2026-07-16

- «Inicio» ya no interpreta un dashboard nuevo: replica la estructura semántica y
  los bloques del `resumen.html` real con una empresa de ejemplo claramente marcada.
  La réplica incorpora también el armazón del producto real: marca, menú agrupado,
  negocio activo, barra superior, puesta en marcha y los diez apartados del panel.
- El titular del hero dispone de más superficie útil y el anual hace visible el
  ahorro sin confundirlo con una alerta: descuento, mes gratis, ahorro total y
  coste mensual equivalente.
- La imagen de referencia aportada por el usuario se inspeccionó, pero no se puede
  capturar el prototipo actualizado ni realizar la comparación lado a lado: abrir el
  navegador integrado vuelve a cerrar Codex incluso después de actualizar la app.
  Windows registra fallos de `ChatGPT.exe` a las 09:58 y 09:59. Esta iteración se
  comprueba por HTML, CSS responsive, JavaScript, HTTP local y pruebas automáticas.

## Iteración de jerarquía · 2026-07-16

- La portada adopta la jerarquía de la referencia elegida: cabecera oscura,
  promesa centrada, explicación breve, acciones de alta y producto inmediatamente
  después. Mantiene la marca, paleta y voz propias de Bynoesis.
- La muestra deja de navegar por vistas creadas únicamente para marketing. Muestra
  el Inicio basado en el panel real y explica que no ejecuta acciones.
- No hay nueva captura: la comparación de referencia y prototipo sigue bloqueada por
  el cierre del navegador integrado. La comprobación se limita explícitamente a
  HTML, CSS responsive, JavaScript y pruebas automáticas.

## Expediente de gestoría por tareas · 2026-08-07

- **Fuente visual:** las ocho capturas
  `C:\Users\mikic\AppData\Local\Temp\codex-clipboard-5ebf13e7-2eff-449d-becd-8715ee34a33c.png`,
  `C:\Users\mikic\AppData\Local\Temp\codex-clipboard-3fc0f128-1392-4403-8266-280021f9df74.png`,
  `C:\Users\mikic\AppData\Local\Temp\codex-clipboard-d574fe8d-dd60-4f57-a869-3e2c154136b1.png`,
  `C:\Users\mikic\AppData\Local\Temp\codex-clipboard-ec60cd07-b35b-494c-8acd-38ef174b1571.png`,
  `C:\Users\mikic\AppData\Local\Temp\codex-clipboard-3eeaf9b4-ede2-4a23-a995-ca9175a32a14.png`,
  `C:\Users\mikic\AppData\Local\Temp\codex-clipboard-52226f42-3782-4dfc-814d-efa9f13c3879.png`,
  `C:\Users\mikic\AppData\Local\Temp\codex-clipboard-63ddc3d2-2cb5-4471-b116-ab590144a86c.png`
  y `C:\Users\mikic\AppData\Local\Temp\codex-clipboard-5842cf5c-d968-4e24-a66d-4f5920adac02.png`,
  aportadas por el founder a 1867×896,
  1742×905, 1822×893, 1651×896, 1645×896, 1517×896, 1588×896 y
  1518×870 px respectivamente.
- **Estado de referencia:** cartera y expediente autenticados en escritorio, con
  Resumen, Documentos, Impuestos, Períodos y Solicitudes visibles durante scroll.
- **Hallazgos P1/P2:** una sola página mezclaba cinco tareas; el submenú sticky
  ocultaba filas; faltaba estado activo y cada bloque competía con el anterior.
- **Corrección implementada:** cinco vistas reales, estado activo con explicación,
  selector temporal común, superficies delimitadas y contexto conservado en POST.
- **Captura implementada y comparación conjunta:** no disponibles. Por petición
  previa del founder no se usa el navegador integrado, ya que cerraba la aplicación.
  No se afirma fidelidad visual posterior desde HTML/CSS o pruebas automáticas.
- **Comprobación no visual:** 415/415 pruebas, incluyendo separación de contenido,
  acceso documental y redirecciones que preservan el contexto.

**final result: blocked**
