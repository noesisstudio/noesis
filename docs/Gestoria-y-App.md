# Gestoría, app nativa y huecos de negocio — diseño y decisiones

> **Documento histórico de diseño e implementación.** Conserva decisiones útiles,
> pero sus números y pendientes no son la fotografía actual. Consultar
> [`project-state.json`](project-state.json), [[Tareas-vivas]] y [[Mapa-codigo]].

> Complemento de [`WhatsApp-Cerebro.md`](WhatsApp-Cerebro.md). Escrito el 2026-07-03
> tras las preguntas del founder: conexión con la gestoría de cada cliente, app
> nativa con widget, y qué le falta al producto a nivel de negocio.
>
> ✅ **El módulo gestoría (§1) está CONSTRUIDO** (migración 15, mismo día):
> portal `/g/{token}`, paquete ZIP por período, job mensual/trimestral, tarjeta
> en Ajustes con "Enviar ahora". Falta SMTP configurado para el email automático
> (sin él, el autónomo comparte el enlace a mano). §2 (app) y §3 (huecos de
> negocio) siguen pendientes según su secuencia.

---

## 1. Módulo Gestoría — "tu gestor lo recibe todo solo"

### La jugada (doble)
1. **Feature de retención**: el autónomo deja de pasar la caja de zapatos con
   tickets cada trimestre. Su gestoría recibe sola un paquete limpio. Quien tiene
   esto configurado NO se da de baja: el coste de cambio se dispara.
2. **Canal de adquisición**: la gestoría descubre que los clientes con Bynoesis le
   dan cero trabajo sucio. Una gestoría mediana lleva 50-300 autónomos → es el
   canal con CAC más bajo posible (ya está en Plan-Evolucion como apuesta). El
   paquete lleva marca Bynoesis: cada envío es una demo ante un prescriptor.

### Diseño (migración 15, `gestoria`)
- Columnas en `businesses`: `gestoria_name`, `gestoria_email`,
  `gestoria_cadence` (`'off'` default | `'mensual'` | `'trimestral'`).
- **Portal de gestoría `/g/{token}`** (mismo patrón que el portal de cliente
  `/p/` y el de fichaje `/t/`: token-capacidad, sin contraseña, revocable,
  caducidad larga, rate-limit anti-escaneo ya existente). La gestoría ve la lista
  de períodos cerrados y descarga cada paquete. NO se mandan adjuntos gordos por
  email: el email solo avisa con el enlace (adapters/email.py ya existe).
- **Contenido del paquete por período** (ZIP generado bajo demanda, `zipfile` de
  la stdlib — sin deps nuevas):
  - Facturas emitidas: PDFs (ya se generan al vuelo) + `facturas.csv` (existe).
  - Gastos: `gastos.csv` (existe) + los justificantes de `documents/` vinculados
    (foto del ticket = el justificante que la gestoría necesita — sinergia
    directa con gasto-por-foto).
  - **Resumen fiscal del período** (PDF fpdf2, 1 hoja): totales, IVA repercutido/
    soportado, estimación 303/130 (`db.tax_quarter` ya lo calcula). La gestoría
    recibe el trabajo pre-masticado: eso es lo que la enamora.
  - Export XML Veri*Factu del período si está activo (`export_verifactu_xml`).
- **Job en scheduler**: los días 1-5 tras el cierre del período (mes o trimestre),
  para cada negocio con cadencia activa: materializar el período, avisar por email
  a la gestoría y por WhatsApp al autónomo ("📦 Le he enviado a tu gestoría las
  12 facturas y 34 gastos del T2. No tienes que hacer nada."). Idempotente por
  negocio+período (`claim_scheduled_run` + registro en `product_events`).
- Tarjeta "Tu gestoría" en Ajustes: nombre, email, cadencia, botón "Enviar ahora"
  (manual, para el primer wow sin esperar al cierre) y "Revocar acceso".
- **RGPD**: el autónomo comparte SUS datos con SU gestoría (encargado suyo, no
  nuestro); basta consentimiento explícito al activar (checkbox + evento
  `legal_gestoria_enabled` en product_events, mismo patrón del alta).
- Tests: aislamiento (token de gestoría A no ve negocio B), idempotencia del
  cierre, ZIP con recuentos correctos, revocación efectiva.

### Fase 2 del canal (NO ahora; cuando haya ≥10 gestorías recibiendo paquetes)
Panel multi-cliente para gestorías (una gestoría, N negocios Bynoesis) + programa
de partner (comisión recurrente o precio por volumen). No construir hasta que
las gestorías lo pidan: primero que prueben el paquete.

---

## 2. App nativa y widget — decisión honesta por etapas

**Lo que ya hay**: Bynoesis ES instalable hoy (PWA: manifest + service worker en
producción). En Android se añade a la pantalla de inicio con icono propio y
funciona a pantalla completa; en iPhone también (con límites de iOS).

**Los costes reales de una app nativa** no son de programarla (eso lo hacen los
agentes): son Apple Developer (99 €/año), Google Play (25 € una vez), el proceso
de revisión de las dos tiendas en cada update, y el mantenimiento de DOS bases de
código nativas más la web. Eso, hoy, con 0 clientes de pago, es músculo mal puesto.

**Secuencia decidida** (cada etapa se activa con demanda real, no antes):

| Etapa | Qué | Coste | Cuándo |
|---|---|---|---|
| A (ya) | PWA pulida: **share target** en Android (compartir una foto → se abre Bynoesis en "nuevo gasto" — el gesto widget-like más barato que existe) + accesos directos del icono (mantener pulsado → "Hablar", "Nueva factura", "Agenda") + push web en Android | ~0 € | con el plan WhatsApp |
| B | **Atajo de Siri/iOS Shortcuts publicado por Bynoesis**: el usuario añade un atajo que graba audio y lo manda a `/api/{id}/chat/audio` con su token. Botón en pantalla de inicio del iPhone, dos toques y hablas — SIN app, sin App Store | 0 € | cuando W4 (audio) esté vivo |
| C | App **Capacitor** (envoltorio nativo de la web actual, una sola base de código): presencia en tiendas, push nativo iOS, credibilidad | 124 € + días de agente | ≥25-50 clientes de pago o cuando lo pidan pilotos |
| D | **Widgets nativos** (WidgetKit/Glance: agenda de hoy en la pantalla de inicio, botón de voz) | semanas de agente + mantenimiento | cuando la app C tenga uso real |

**Criterio**: WhatsApp sigue siendo el canal para el 90 % del segmento (cero
fricción, cero instalación). La app es para el minorista que la pida y para la
percepción de solidez en las tiendas. No dividir el foco antes de validar.

---

## 3. Huecos de negocio (visión ADE) — qué le añadiría al sistema

Priorizados por (valor para el autónomo × datos que YA tenemos × coste de construir):

1. **Rentabilidad por trabajo y por cliente** ("job costing"). Tenemos lo que
   nadie tiene junto: horas reales del fichaje + gastos + factura por trabajo.
   Cruce → "La reforma de Sants te dejó 38 €/h; las averías de la comunidad X,
   11 €/h". Ningún competidor del segmento lo ofrece; a un perfil ADE le encanta
   y al fontanero le cambia los precios que cotiza. **El foso de datos hecho
   producto.** (Página "Rentabilidad" + aviso del copiloto cuando un cliente
   sale sistemáticamente por debajo de la media.)
2. **Provisión fiscal automática** ("aparta 412 € este mes"). El susto del 303
   es EL trauma del autónomo novato. `tax_quarter` ya calcula; falta convertirlo
   en hucha virtual visible (tesorería) y aviso mensual por WhatsApp (ya en W1).
   Barato y con carga emocional altísima.
3. **Previsión de caja a 60-90 días**. Con pendientes de cobro (fecha + DSO
   histórico real del ledger), gastos recurrentes detectados e impuestos del
   trimestre: "en noviembre te faltan ~800 € si Ríos no paga". La página
   Tesorería ya tiene la base; falta la proyección.
4. **Reseñas de Google tras cobrar** (motor de crecimiento PARA el autónomo).
   Trabajo terminado + factura pagada → mensaje automático al cliente final:
   "¿Le dejarías una reseña a Fontanería Uno? [enlace]". Las reseñas son el
   canal nº 1 de captación de un oficio. Nadie del segmento lo automatiza unido
   al cobro (el momento de máxima satisfacción). Config: enlace de perfil de
   Google en Ajustes + plantilla Meta. Coste ridículo, valor percibido enorme.
   → Esto convierte a Bynoesis de "ahorra tiempo" a "**te trae clientes**": otra
   liga de disposición a pagar.
5. **Semáforo de morosidad por cliente**. Con el ledger: días medios de pago
   reales por cliente. Al crear presupuesto/trabajo para un moroso conocido, el
   copiloto avisa: "Ojo: paga a 60+ días. ¿Pides anticipo del 40 %?" (enlaza con
   cobros parciales T1). Datos ya existentes, solo presentación + regla.
6. **Reserva online de citas** (`/r/{negocio}`, tipo Calendly de gremios): el
   cliente final elige hueco según la agenda real. Llena la agenda = valor de
   crecimiento, no de administración. Es lo que hace Experi solo. **Fase
   posterior** (toca calendario y solapamientos; hacerlo bien no es trivial).
7. Adyacencias fintech (para el plan de empresa, NO construir): anticipo de
   facturas (factoring por referral), seguro de impago, tarjeta de gastos.
   Líneas de ingreso futuras sobre la base de datos de cobros. Solo narrativa
   de upside ante inversores por ahora.

**Los tres primeros son el "CFO de bolsillo"** y salen casi enteros de datos que
ya guardamos. El 4 y el 5 son el "comercial de bolsillo". Esa pareja — CFO +
comercial por 29/49/99 € + IVA al mes — es la historia de producto completa: no un programa
de facturas, sino el empleado que el autónomo nunca pudo pagar.

### Nota para la conversación de precios pendiente
Cuando el founder traiga los márgenes: la escalera natural que sale de este doc
es gate-ar por plan — Autónomo (ciclo completo + informes WhatsApp), Negocio
(+equipo/fichaje + gestoría + rentabilidad por trabajo), Premium futuro
(+recepcionista IA + reservas). Coste variable relevante por cliente: Meta
(~conversaciones/mes), IA de extracción (presupuesto/día ya definido en
WhatsApp-Cerebro §8) y Groq (céntimos). Pendiente de sus números.
