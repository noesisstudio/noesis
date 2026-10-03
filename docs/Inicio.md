# 🧭 Bynoesis — Inicio

## 2026-10-03 — Financial Core1.9B

Inventario/dry-run diagnóstico completado localmente, cinco flags OFF. [Entrada](architecture/README.md),
[contrato](architecture/FINANCIAL-HISTORY-INVENTORY-v1.md), [cierre](architecture/FASE-1.9B-cierre.md).
No producción, importación, certificación ni1.9C. Alcances inferiores históricos.

## 2026-10-03 — Financial Core1.9A

Solo contratos/gobernanza históricos; cero importaciones y cinco flags OFF.
[Entrada](architecture/README.md), [contrato](architecture/FINANCIAL-HISTORY-v1.md),
[cierre](architecture/FASE-1.9A-cierre.md). No1.9B ni activación.

## 2026-10-02 — Fase 1.8, canales financieros

Solo integración de canales con los Capture existentes, sin 1.9 ni activación.
`financial_channels/` enlaza propuestas y recibos mínimos con operaciones y
aprobaciones; no añade un motor financiero ni un event log operativo. Web exige
sesión/CSRF y UUID; chat turno/slot; WhatsApp provider/receptor/negocio/wamid;
documentos review UUID/documento/item/revisión; recurrentes schedule/vencimiento.
Autorización + recibo + consumo de pending atómicos; efecto posterior reintentable
con la misma operación. Scheduler genera borradores y exige confirmación humana;
no mandato abierto. Migración 68, enlaces inmutables y huella mínima de plantilla.
Cinco flags siguen OFF, guards capturados conservados y opt-in sin fallback.
Cierre técnico: **31 PASS / 0 FAIL**. Nuevas SQLite41/PG41, PostgreSQL total234,
general1617 (1298.519 s), Node9 y gates locales PASS. Último transporte de
revisión revalidado en ambos motores/HTTP/Node; alcance exacto en el [cierre](architecture/FASE-1.8-cierre.md).
Incluye autoauditorías, límites externos y diagnóstico/rollback.
Pendientes externos: CI remoto/despliegue y Meta real no certificados aquí;
activación y otra fase solo con nueva orden. CSV antiguo sin cuenta/batch y audio sin UUID quedan bloqueados
para mutaciones capturadas. Históricos, retención/export financiero y rollout
siguen en fases posteriores expresamente autorizadas.


## Orden vigente — exclusivamente Fase1.7

1.1–1.6 aceptadas. SupplierInvoiceCapture/ExpenseCapture conectan solo
supplier_invoice.confirmed/corrected/voided y expense.confirmed/voided v1.
Writers compartidos, autorización durable, cobertura inmutable por revisión,
continuidad antes/después, logical void y guards SQL. Documento/clasificación/
source/EE/resultado comparten commit. Flags OFF; no1.8, históricos ni activación.
Pagada es etiqueta operativa, no supplier payment/AP settlement. No GL/Tax/
OpenItems/reporting nuevo. Legacy no capturado conserva comportamiento.
[Orden](architecture/FASE-1.7-orden.md), [ADR-011](architecture/ADR-011-purchasing-capture.md),
[API](architecture/PURCHASING-CAPTURE-v1.md), [cierre](architecture/FASE-1.7-cierre.md).
Las secciones inferiores describen entregas históricas; no son la orden vigente.

## Continuidad del Financial Core

Orden vigente: exclusivamente1.6; [gobernanza](architecture/README.md),
[contrato cobros/banco](architecture/PAYMENT-BANK-CAPTURE-v1.md) y
[cierre verificable](architecture/FASE-1.6-cierre.md). No inferir permiso para1.7.

[Financial Core: gobernanza, ADR y cierre de Fase 0](architecture/README.md). Leer antes de continuar cualquier fase financiera.

Mapa de contenido (MOC) del proyecto. Abre esta carpeta como *vault* en Obsidian y
usa la vista de grafo para navegar.

## Cómo está ordenada la carpeta

| Carpeta | Qué contiene |
|---|---|
| `docs/` (raíz) | Núcleo vivo: este índice, `project-state.json`, estado, tareas, bitácoras, decisiones, arquitectura y mapa de código. Sus rutas son fijas: las usan la CI, la comprobación de producción y los agentes. |
| `01-producto/` | Qué es Bynoesis, plan maestro, roadmap, retención, demo y piloto. |
| `02-tecnico/` | Guía de ingeniería, despliegue, IA local, fiabilidad conversacional y diagnóstico. |
| `03-whatsapp-e-integraciones/` | WhatsApp, Meta, Google, correo y la guía única de credenciales. |
| `04-seguridad-y-datos/` | Seguridad operativa, permisos, almacenamiento, copias y residencia de datos. |
| `05-legal-y-rgpd/` | Ruta legal, constitución, fiscalidad, RGPD y `cumplimiento/` (RAT, EIPD, brechas...). |
| `06-negocio-y-finanzas/` | Primer euro, plan a 60 días, unit economics, costes, modelo económico y mercado. |
| `07-marketing/` | Estrategia, manual maestro, calendario, guiones y publicación en redes. |
| `08-agentes-ia/` | Método de trabajo, plantilla y archivo de traspasos, prompts. |
| `09-historico/` | Auditorías, revisiones y fotos fechadas que ya no son estado actual. |
| `design/` | Sistema de diseño (principios, tokens, copy). |
| `qa/` | Capturas de evidencia citadas en `Registro-QA`. |

Documento nuevo: al tema que le toque, nunca suelto en la raíz. Los enlaces
`[[Nombre]]` de Obsidian funcionan esté donde esté el archivo.

## Mapa
- [[Como-funciona-la-empresa]] — **empieza aquí si llegas sin contexto**: las cinco
  piezas de la máquina, el dinero, las cuatro puertas hasta el primer euro, cómo se
  captan clientes y quién hace qué. No repite cifras vivas: apunta a dónde están.
- [[Lista-de-captacion]] — de dónde salen los 40 nombres en Lleida y el Segrià, el
  ritmo diario de llamadas y qué se puede hacer y qué no al contactar en frío.
- [[Correo-que-no-cae-en-spam]] — por qué el correo acaba en spam cuando la
  autenticación está bien: el diagnóstico real del dominio, los registros que sí
  faltan, la prueba de cabeceras y cómo escribir un primer contacto que llegue.
- [[Estado-actual-main]] — única fotografía viva de lo construido y publicado.
- [[Tareas-vivas]] — único listado vivo de pendientes y prioridades.
- [[Registro-cambios]] — bitácora cronológica obligatoria: qué cambió, pruebas,
  riesgos y pista para diagnosticar o revertir una regresión.
- [[Plan-maestro-Bynoesis]] — visión, principios, arquitectura objetivo y criterios.
- [[Producto]] — qué es Bynoesis, para quién y la propuesta de valor.
- [[Propuesta-sistema-retencion-habito-valor]] — propuesta para socios que integra
  Habit, Trust, Value, WUB y las fases posteriores de Insight, Progress y Confidence.
- [[Registro-interno-valor]] — contrato técnico del esquema 54: taxonomía,
  idempotencia, WUB, outcomes, privacidad, flags, auditoría y rollback.
- [[Competencia]] — Forjia y el resto del mercado.
- [[Investigación]] — hallazgos de research (mercado, diseño, coste IA).
- [[Benchmark_SaaS]] — patrones de SaaS profesionales usados para orientar la UX.
- [[Arquitectura]] — cómo está construido el sistema.
- [`areas/`](areas/README.md) — **una guía por apartado** (visión general, ramas,
  cerebro, facturas, correo, RGPD y lo automático): archivos, reglas que no se
  rompen, estado real y qué comprobar al revisar código. Léela antes de tocar la zona.
- [`Mapa-Bynoesis.html`](02-tecnico/Mapa-Bynoesis.html) — el sistema entero en
  esquemas con líneas: entradas, cerebro, facturas, correo, RGPD, ramas de la
  empresa y lo que pasa solo cada día, con el estado real de cada pieza.
- [`Permisos-y-acceso.pdf`](04-seguridad-y-datos/Permisos-y-acceso.pdf) — las cuatro identidades, qué
  puede hacer cada una, cómo se da y se quita acceso, y cómo cumple el RGPD.
- [[Seguridad-operativa]] — amenazas, controles, secretos, incidentes y puerta de
  salida segura al piloto.
- [[Almacenamiento-y-copias]] — foto técnica de dónde vive cada archivo, qué hace
  exactamente el sistema de copias y sus siete puntos débiles conocidos.
- [`cumplimiento/`](05-legal-y-rgpd/cumplimiento/README.md) — dónde se almacena cada dato, en qué
  servidores, cómo se hacen las copias y qué exige la normativa europea: registro
  del art. 30, retención, subencargados y transferencias, riesgos, brechas,
  derechos y continuidad con RPO/RTO. El prompt que lo generó está en
  [`prompts/Prompt-Seguridad-Datos-UE`](08-agentes-ia/prompts/Prompt-Seguridad-Datos-UE.md).
- [[RGPD-Registro-actividades]] — inventario vivo de tratamientos como responsable
  y como encargado, con categorías, bases, destinatarios y controles.
- [[RGPD-Matriz-proveedores]] — rol, datos, activación y evidencia contractual que
  se exige a cada proveedor antes de recibir datos reales.
- [[RGPD-Procedimiento-derechos-y-bajas]] — recepción, verificación, conservación,
  resolución y prueba de las solicitudes de derechos y baja.
- [[RGPD-Procedimiento-brechas]] — contención, evaluación, comunicaciones y cierre
  de incidentes con datos personales.
- [`Diagnostico.pdf`](02-tecnico/Diagnostico.pdf) — cuando algo falla, dónde mirar: las siete
  piezas, las cuatro puertas de una petición, síntomas y causas, y qué preguntar.
- [`Diagnostico-tecnico.pdf`](02-tecnico/Diagnostico-tecnico.pdf) — lo mismo con el archivo, la
  función y la tabla al lado, más cómo levantar el proyecto desde cero.
- [[Guia-tecnica-ingeniero]] — entrada técnica de extremo a extremo para ingeniería:
  web, datos, cerebro, automatizaciones, WhatsApp y despliegue.
- [`WhatsApp-Como-funciona.pdf`](03-whatsapp-e-integraciones/WhatsApp-Como-funciona.pdf) — el canal multicanal
  explicado sin código: los dos tipos de número, por qué el receptor decide antes
  que el remitente, qué ve cada rol y qué falta por validar.
- [`Meta-Verificacion.pdf`](03-whatsapp-e-integraciones/Meta-Verificacion.pdf) — qué hay que completar de
  verdad en Meta y qué se puede ignorar: los dos caminos, por qué la revisión de
  la aplicación no hace falta todavía, y cómo verificar cada pieza.
- [`WhatsApp-Puesta-en-marcha.pdf`](03-whatsapp-e-integraciones/WhatsApp-Puesta-en-marcha.pdf) — runbook visual
  para llevar Meta Cloud API del número de prueba a clientes reales: canal central,
  alta de números comerciales, plantillas y prueba con dos negocios. El `.html` del
  mismo nombre es la fuente: se edita ahí y se reimprime el PDF.
- [`Conectar-Correo.pdf`](03-whatsapp-e-integraciones/Conectar-Correo.pdf) — guía del correo saliente con
  Brevo: por qué un servidor no puede enviar solo, autenticar el dominio para no
  caer en spam, las dos variables y la prueba de aceptación.
- [`Conectar-Google.pdf`](03-whatsapp-e-integraciones/Conectar-Google.pdf) — guía completa del acceso con
  Google: por qué bloquea hoy el panel de administración, los cinco pasos en la
  consola, las dos variables, la prueba de aceptación y los errores típicos.
- [`facebook/Conectar-Facebook.html`](../facebook/Conectar-Facebook.html) — guía
  paso a paso para dejar la página publicando sola: por qué hay dos tokens, qué
  copiar de Meta, dónde guardarlo y cómo probarlo sin publicar nada. Vive junto a
  la automatización, en `facebook/`, con su fuente en Markdown al lado.
- [[Conectar-Gmail-y-recibir-facturas]] — puesta en marcha paso a paso de las dos
  funciones de correo del autónomo: enviar desde su Gmail y recibir facturas solas.
- [[Conectar-APIs]] — guía única de credenciales, callbacks, variables y pruebas
  externas para conectar producción sin confundir código con servicio activo.
- [[Demo-comercial]] — dos accesos dentro del SaaS real, portal de cliente,
  credenciales, solo lectura y activación segura.
- [[IA-local]] — servicio privado, enrutamiento y límites de IA.
- [[Analisis-coste-IA.ipynb]] — cálculo reproducible de coste y autoalojamiento.
- [`Bynoesis-Modelo-Economico.xlsx`](06-negocio-y-finanzas/Bynoesis-Modelo-Economico.xlsx) — modelo vivo:
  supuestos, unit economics, escenarios, proyección a 24 meses, sensibilidad,
  capacidad de soporte, captación y KPIs del piloto. Se regenera con
  `python analysis/build_modelo_economico.py`.
- [`Estrategia-Marketing.pdf`](07-marketing/Estrategia-Marketing.pdf) — a quién vendemos, con qué
  mensaje, por qué canales, cuánto podemos pagar por un cliente, dónde entra la IA
  y las vías de escape con sus criterios de parada.
- [`Marketing-Bynoesis.pdf`](07-marketing/Marketing-Bynoesis.pdf) — **manual maestro de marketing**:
  consolida la estrategia, la marca, las 24 piezas de contenido con su gancho, copy,
  CTA y métrica, la producción, la publicación en Instagram y Facebook, la medición
  y los criterios de parada. Sustituye a `Estrategia-Marketing` y `Publicar-en-redes`.
- [`Publicar-en-redes.pdf`](07-marketing/Publicar-en-redes.pdf) — manual operativo de publicación
  en Instagram y Facebook. Su contenido está incorporado al manual maestro.
- [`Ruta-legal.pdf`](05-legal-y-rgpd/Ruta-legal.pdf) — qué falta para poder cobrar el primer euro:
  Veri*Factu como productor, App Review de Meta, AI Act y protección de datos; tres
  rutas completas con su coste y el material para encargar las revisiones.
- [[Preguntas-abogado-TIC]] — las 23 preguntas para la reunión con el abogado TIC,
  con el contexto de cada una y cómo reconocer una respuesta útil; actualizadas al
  código del 15-sep (Groq, Analytics, paso a S.L. y marca).
- [`Plan-60-dias.pdf`](06-negocio-y-finanzas/Plan-60-dias.pdf) — el plan de ejecución que pone fecha a todo
  lo anterior: cuatro frentes en paralelo, nueve semanas y una puerta de salida por
  semana.
- [`Estado-Bynoesis.xlsx`](03-whatsapp-e-integraciones/Estado-Bynoesis.xlsx) — estado de cada pieza en hoja de cálculo:
  canal de Meta, plantillas y catálogos por oficio. Se regenera con
  `python scripts/build_estado_xlsx.py`.
- [[Constitucion-y-primer-euro]] — la pieza que `Ruta-legal` no cubre: S.L. o
  autónomo decidido por lo que Meta verifica de verdad, los trámites de constitución
  en orden de dependencia y el presupuesto del arranque.
- [[RGPD-estado-y-plan]] — auditoría de protección de datos contra el código y los
  textos publicados, complementaria a la parte 5 de `Ruta-legal`: qué cumple ya y los
  hallazgos concretos que quedaban fuera.
- [[Servidores-y-residencia-de-datos]] — no existe la «licencia RGPD»: qué exige de
  verdad un proveedor, qué cumple Railway, dónde están hoy los datos y por qué mover
  la región es más barato antes del primer cliente.
- [[RGPD-QUE-HACER]] — la lista ejecutable que sale de los dos anteriores: qué hacer
  hoy, qué antes de cobrar, qué encargar fuera y diez criterios verificables.
- [[Unit-economics-y-cerebro-interno]] — precios, márgenes, escala y decisión de IA.
- [[Analisis-unit-economics.ipynb]] — modelo reproducible completo por plan.
- [[Piloto-operativo]] — puerta de salida, casos reales, métricas e incidentes.
- [[Fiscalidad]] — IVA, IRPF y Verifactu.
- [[Roadmap]] — qué está hecho y qué falta, por fases.
- [[Despliegue]] — cómo operar Bynoesis online 24/7 en bynoesis.com.
- [[Decisiones]] — registro de decisiones importantes (y por qué).
- [[Metodo-operativo-Fable]] — el criterio de trabajo, heredable por Opus y Codex.
- [[Preguntas-abiertas]] — dudas que esperan respuesta del founder.
- [[Estado-traspaso-MVP]] — estado real y traspaso entre agentes.
- [`AI_HANDOFF_TEMPLATE.md`](08-agentes-ia/AI_HANDOFF_TEMPLATE.md) — plantilla de traspaso.

## Estado en una frase

No se repite aquí para evitar desincronizaciones. Consulta [[Estado-actual-main]]
para la fotografía auditada y [[Tareas-vivas]] para lo siguiente.

> Fundador: graduado en ADE, 23 años, ya tiene una empresa de eventos. Capital
> inicial ~4.000 €. Rol: negocio/dirección. Desarrollo: Claude.
