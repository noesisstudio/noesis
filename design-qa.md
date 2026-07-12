# Design QA — Home MVP profesional

- Source visual: `docs/design/references/home-mvp-selected.png`
- Implementation: `http://127.0.0.1:8000/b/1/resumen`
- Compared state: desktop con cuenta demo cargada, navegación cerrada y datos resueltos.
- Reference viewport: 1487 × 1058.
- Implementation viewport checked: 1536 × 1024 desktop and 390 × 844 mobile.

## Comparison history

### Pass 1

- P1: la Home anterior acumulaba pulso, balance, gráfica, plan y detalle sin una
  prioridad visual única.
- P1: Proyectos no existía en la navegación ni había profundidad progresiva.
- P2: el menú móvil no sincronizaba `aria-expanded` y `aria-hidden`.
- P2: la jerarquía lateral no seguía el trabajo diario del autónomo.

### Pass 2

- Resuelto: parte de Noesis como primer bloque, una prioridad accionable y cuatro
  métricas compactas.
- Resuelto: dos columnas principales «Hoy» y «Noesis está trabajando»; el detalle
  financiero queda debajo y en su apartado.
- Resuelto: navegación ordenada por Inicio, Trabajos, Proyectos y Clientes antes de
  la gestión administrativa.
- Resuelto: Proyectos muestra resumen y lista; horas, costes, equipo y margen solo
  aparecen tras abrir un proyecto.
- Resuelto: sin desbordamiento horizontal a 390 px y menú móvil accesible.

## Remaining P3 polish

- La ilustración editorial del grifo de la referencia se omite: no aporta una acción
  y se prioriza que el parte use datos reales y mantenga más espacio útil.
- La fecha está dentro del parte en vez de ocupar la esquina izquierda del topbar.

final result: passed
