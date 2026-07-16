# Design QA — sitio público Noesis

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
  También se alinea la navegación de la demo con los diez apartados del panel.
- El titular del hero dispone de más superficie útil y el anual hace visible el
  ahorro sin confundirlo con una alerta: descuento, mes gratis, ahorro total y
  coste mensual equivalente.
- No hay nueva captura ni afirmación de comparación visual. La app de escritorio
  ha cerrado durante el trabajo incluso después de actualizarse y Windows registra
  nuevos fallos de `ChatGPT.exe` a las 09:58 y 09:59;
  esta iteración se comprueba por HTML, CSS responsive, JavaScript y HTTP local.

**final result: passed**
