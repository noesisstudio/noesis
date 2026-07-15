# DESIGN.md — Dirección visual de Noesis

> Cómo se ve y se siente Noesis. Fijado con el founder 2026-07-08. Lee antes
> [`PRODUCT_PRINCIPLES.md`](PRODUCT_PRINCIPLES.md). Tokens en
> [`STYLE_TOKENS.json`](STYLE_TOKENS.json); lenguaje y voz en
> [`UX_COPY.md`](UX_COPY.md).

## 1. El norte en una imagen

**La app no es un tablero que lees; es un parte que recibes.** Cada mañana Noesis
te da el parte del negocio como te lo daría tu mano derecha: qué hay hoy, qué es lo
importante, qué puede hacer por ti. Entras y sientes: *"lo entiendo, sé qué hacer y
puedo preguntar cualquier cosa."*

Salimos de la **piel fintech** (KPIs, ratios, gráficas, tablas por defecto) y vamos a
una app que **se siente como una app de productividad personal aplicada al negocio**:
calma, cálida, poco densa, acción antes que dato.

## 2. Referencias (a qué parecerse)

- **Linear** — calma, contención, tipografía protagonista, densidad controlada. Pero
  **más cálido**.
- **Things 3 / Superhuman** — "la app te dice qué hacer ahora", foco único por
  pantalla.
- **Neobanco cálido / app de hábitos** — dinero y datos explicados en lenguaje humano.
- **Holded / Odoo = anti-referencia de experiencia** (no de credibilidad). Tomamos su
  orden y confianza; **no** su densidad ni su sensación de ERP.

## 3. La persona: Noesis habla

Noesis es una **figura con carácter**, no una voz neutra de sistema. Se dirige al
usuario por su nombre, en segunda persona, con tono de mano derecha competente y
tranquila. Detalle de voz en [`UX_COPY.md`](UX_COPY.md). Visualmente, la voz de
Noesis se distingue de los datos:

- **Voz de Noesis** (el parte, los titulares, las recomendaciones): serif editorial
  (Fraunces). Da calidez y presencia; "alguien te habla".
- **Datos** (importes, tablas, formularios): sans limpia (Inter). Precisión.

Esa dualidad serif-voz / sans-dato es la firma tipográfica de Noesis y ya existe a
medias; hay que apoyarse en ella con intención.

## 4. La jerarquía de pantalla (obligatoria, no una plantilla)

Todas comparten una jerarquía de comprensión, pero **no** la misma composición. La
forma se decide por la tarea: una agenda puede ser temporal, Clientes relacional,
Documentos una bandeja de revisión y Tesorería una previsión. No se copian bloques ni
KPIs para conseguir consistencia artificial.

La jerarquía común es:

1. **Parte de Noesis** — una lectura breve en lenguaje humano, con la marca:
   *"He revisado tus cobros: 3 vencidas por 1.240 €. ¿Te preparo los recordatorios?"*
   Con su botón de acción. En un negocio sin datos: *"Aún no tengo nada que
   ordenarte aquí. Empieza por…"*.
2. **Acciones** — lo que se puede hacer ahora: hacer factura, reclamar cobro, enviar
   presupuesto, asignar feina, mandar a gestoría.
3. **Información útil** — números, estados, calendario, personas o documentos según
   lo que ayude a decidir en esa sección.
4. **Detalle** — tablas, gráficas, histórico, exportaciones. Plegado o al final; solo
   para quien lo pide.

El "detalle" es donde vive hoy casi todo. No se borra: se **subordina**.

## 5. Navegación (V1)

Menú principal, en lenguaje de negocio, no de módulos técnicos:

```
Inicio      · el parte del día
Feinas      · trabajos: cliente, visita, equipo, materiales, factura, cobro, margen
Clientes    · fichas, historial, leads y seguimientos (CRM integrado, no separado)
Dinero      · caja, ingresos, costes, impuestos, análisis (dentro, no de golpe)
Facturas    · emitidas, recibidas, presupuestos, cobros
Documentos  · tiquets, PDFs, gestoría, clasificación, pendientes
Equipo      · asignaciones, fichajes, ubicación, horas
Noesis      · el asistente, la memoria del negocio, automatizaciones
Ajustes     · empresa, WhatsApp, gestoría, marca, permisos
```

Reglas: nada de "Tesorería" ni "DSO" a la cara. Lo financiero-técnico vive **dentro**
de "Dinero" y en modo avanzado. **Feinas** es la pieza que conecta todo (es la
columna vertebral; su construcción a fondo es su propia fase, ver §8).

## 6. Lenguaje visual

- **Lienzo cálido**, no gris frío de fintech: hueso/crema. Ver tokens (`--bg` pasa de
  `#f5f6f8` a un crema cálido). Superficies blancas sobre crema.
- **Verde de marca (#14463b) con moderación**: acento, no campos de verde. Teal
  (#2e8b74) para acentos y datos.
- **Una columna, móvil primero.** Un foco por pantalla. Aire generoso. Se acaba el
  amontonar 4 KPIs + tabla + formulario alto: esa densidad es el enemigo.
- **Alertas sin alarmismo.** Ámbar/rojo apagados, en tono de aviso, no de emergencia.
- **El "+ Crear"** abre acciones reales (factura, feina, gasto, presupuesto,
  preguntar a Noesis), no un formulario.
- **Noesis es una capa persistente**, no una pestaña: presente en todas las pantallas
  ("Preguntar a Noesis sobre esto").

## 7. Modos de complejidad (una piel, tres niveles de lenguaje)

**No** hay tres diseños visuales. Hay **una identidad** con tres niveles que cambian
lenguaje, densidad, módulos visibles y cuánto tecnicismo se muestra:

- **Simple / Oficio** (por defecto, el foco de V1): claro, directo, sin tecnicismos.
- **Profesional**: más datos, pero explicados.
- **Avanzado**: ratios, márgenes, impuestos, detalle financiero.

V1 clava **solo Simple/Oficio**. Los otros se activan con un interruptor cuando un
piloto real lo pida. Se pregunta en el onboarding: *"¿Cómo quieres que Noesis te
explique el negocio?"*.

## 8. Secuencia de trabajo (decidida con el founder)

1. **Rediseño primero, software después.** Se rediseña toda la app con esta visión
   (piel + lenguaje + Home como parte + Noesis persistente) **antes** de introducir
   las funciones que faltan. Cambio de percepción rápido, sin tocar el modelo de
   datos.
2. **Encima de los routers de Codex** (PR #19), no en paralelo, para no reabrir
   conflictos.
3. **Feina como centro**: promover el trabajo a objeto-eje toca datos y todas las
   pantallas; es su propia fase, después del reskin.
4. **Agenda-gestor**: el norte es que Noesis reorganice y agende solo; se diseña la
   interacción desde ya (propuestas confirmables), aterriza por fases.
5. **WhatsApp encendido** es camino crítico en paralelo (trámite Meta del founder).

## 9. Qué cambia respecto a hoy (concreto)

- El **Inicio** deja de ser KPIs+gráficas y pasa a ser el **parte de Noesis**.
- **Análisis / Tesorería** dejan de estar a la cara: entran bajo "Dinero" y en modo
  avanzado.
- Todo copy financiero pasa por el diccionario de [`UX_COPY.md`](UX_COPY.md).
- Cada pantalla gana su **línea de parte** arriba.
- El lienzo se calienta; la densidad baja; una columna en móvil.
