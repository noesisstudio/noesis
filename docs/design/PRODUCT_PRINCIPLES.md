# Principios de producto de Bynoesis

> Guardarraíl para Fable, Opus y Codex. Si un diseño, un copy o una función
> contradice esto, no se ejecuta: se para y se pregunta. Enlazado desde
> [[Metodo-operativo-Fable]] y `AGENTS.md`. Fijado 2026-07-08 con el founder.

## La frase que lo une todo

> **Bynoesis es un asistente operativo que elimina el ruido del negocio, con un
> software potente detrás. "Haz tu trabajo; yo te ordeno el negocio."**

Es la base de producto, diseño, landing, pitch y desarrollo. Todo se mide contra
ella.

## El modelo: la mente y el cuerpo

- **Bynoesis es la mente / la figura.** Habla con el usuario, interpreta, recomienda,
  ejecuta y le da el **parte del día**. Tiene carácter y voz propia (ver
  [`UX_COPY.md`](UX_COPY.md)).
- **La infraestructura es el cuerpo.** Facturas, cobros, leads, agenda, gestoría,
  documentos, equipo, stock, proyectos, fiscalidad. Es enorme y funciona; pero el
  usuario **no** trabaja módulo a módulo: habla con la mente y la mente orquesta el
  cuerpo.
- **El ecosistema pesa a través del parte, no de 20 pantallas pulidas.** Cada
  servicio gana peso porque aparece en el parte cuando toca, con su acción ("¿te lo
  hago?"). No hace falta que cada módulo sea una pantalla estrella; hace falta que la
  mente sepa surtirlo.

## Las seis leyes

1. **Primero acción, después datos.** Una pantalla abre con *qué hacer hoy*, no con
   números. Las métricas vienen después de la interpretación.
2. **Primero WhatsApp, después app.** WhatsApp es donde se **opera**; la app es el
   centro de control tranquilo donde se **entiende**.
3. **Primero la feina, después la factura.** El objeto central del negocio es el
   trabajo (cliente → visita → presupuesto → materiales → equipo → factura → cobro →
   margen). La factura es una consecuencia, no el eje.
4. **Primero lenguaje humano, después el técnico.** "Días que tardas en cobrar", no
   "DSO". El término técnico solo aparece en modo avanzado o como subtítulo.
5. **Primero la lectura de Bynoesis, después los datos del usuario.** El usuario habla,
   manda fotos y audios; no rellena formularios como punto de partida.
6. **Primero confirmar, después ejecutar lo irreversible.** Enviar factura, reclamar
   cobro, mandar a gestoría o mover una cita se **propone**; el usuario confirma.

## Pantallas hechas a medida, acompañante común

- No existe una plantilla universal de tarjetas, gráficas o KPIs. Cada pantalla se
  diseña desde su tarea principal: Clientes prioriza relaciones e historial;
  Tesorería, disponibilidad y reservas; Agenda, tiempo y secuencia; Documentos,
  clasificación y revisión; Proyectos, avance y margen.
- Un dato aparece solo si ayuda a decidir en esa pantalla. La profundidad queda
  disponible por capas para quien la necesite, sin obligar a entender estadística.
- Lo transversal no es la estructura visual, sino Bynoesis: lee el contexto real,
  explica por qué, propone el siguiente paso y permite preguntar sin perder la
  pantalla ni la conversación.

## Innegociables (heredados del método)

- **Bynoesis no inventa.** Si falta un dato, dice cuál falta. El parte de un negocio
  vacío dice "aún no tengo nada que ordenarte, empieza por aquí" — nunca simula
  actividad. La "memoria del negocio" solo muestra lo que de verdad se sabe.
- **Nada fiscal se presenta como definitivo.** Bynoesis prepara; la gestoría decide.
- **Aislamiento por `business_id`, siempre.** La mente está acotada al negocio del
  usuario.
- **Trazabilidad:** qué detectó el sistema, qué corrigió el humano, qué fue
  automático. Tablas append-only (Veri*Factu, fichaje) intocables.

## Qué NO es Bynoesis

- No es un ERP con cuarenta menús (eso es Holded/Odoo; nos sirve de referencia de
  **credibilidad**, no de **experiencia**).
- No es un dashboard financiero. La piel fintech actual es justo lo que hay que dejar
  atrás.
- No es un chatbot genérico: es una mente que conoce **este** negocio.

## Norte (hacia dónde diseñamos, aunque aterrice por fases)

- **Modo por defecto:** Simple / Oficio. Es el usuario central.
- **Persona:** Bynoesis habla como figura con carácter (mano derecha del negocio).
- **Agenda-gestor:** el destino es que Bynoesis **reorganice y agende solo** (propone
  mover citas, agrupa por zona, con confirmación). Se diseña hacia ahí desde ya,
  aunque la V1 empiece mostrando y sugiriendo.
- **Voz avanzada (contestar llamadas):** nivel premium V2 (telefonía, coste por
  minuto). En el mapa, no en el foco actual.
