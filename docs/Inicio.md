# 🧭 Noesis — Inicio

Mapa de contenido (MOC) del proyecto. Abre esta carpeta como *vault* en Obsidian y
usa la vista de grafo para navegar.

## Mapa
- [[Estado-actual-main]] — única fotografía viva de lo construido y publicado.
- [[Tareas-vivas]] — único listado vivo de pendientes y prioridades.
- [[Registro-cambios]] — bitácora cronológica obligatoria: qué cambió, pruebas,
  riesgos y pista para diagnosticar o revertir una regresión.
- [[Plan-maestro-Noesis]] — visión, principios, arquitectura objetivo y criterios.
- [[Producto]] — qué es Noesis, para quién y la propuesta de valor.
- [[Propuesta-sistema-retencion-habito-valor]] — propuesta para socios que integra
  Habit, Trust, Value, WUB y las fases posteriores de Insight, Progress y Confidence.
- [[Registro-interno-valor]] — contrato técnico del esquema 54: taxonomía,
  idempotencia, WUB, outcomes, privacidad, flags, auditoría y rollback.
- [[Competencia]] — Forjia y el resto del mercado.
- [[Investigación]] — hallazgos de research (mercado, diseño, coste IA).
- [[Benchmark_SaaS]] — patrones de SaaS profesionales usados para orientar la UX.
- [[Arquitectura]] — cómo está construido el sistema.
- [`Permisos-y-acceso.pdf`](Permisos-y-acceso.pdf) — las cuatro identidades, qué
  puede hacer cada una, cómo se da y se quita acceso, y cómo cumple el RGPD.
- [[Seguridad-operativa]] — amenazas, controles, secretos, incidentes y puerta de
  salida segura al piloto.
- [[RGPD-Registro-actividades]] — inventario vivo de tratamientos como responsable
  y como encargado, con categorías, bases, destinatarios y controles.
- [[RGPD-Matriz-proveedores]] — rol, datos, activación y evidencia contractual que
  se exige a cada proveedor antes de recibir datos reales.
- [[RGPD-Procedimiento-derechos-y-bajas]] — recepción, verificación, conservación,
  resolución y prueba de las solicitudes de derechos y baja.
- [[RGPD-Procedimiento-brechas]] — contención, evaluación, comunicaciones y cierre
  de incidentes con datos personales.
- [`Diagnostico.pdf`](Diagnostico.pdf) — cuando algo falla, dónde mirar: las siete
  piezas, las cuatro puertas de una petición, síntomas y causas, y qué preguntar.
- [`Diagnostico-tecnico.pdf`](Diagnostico-tecnico.pdf) — lo mismo con el archivo, la
  función y la tabla al lado, más cómo levantar el proyecto desde cero.
- [[Guia-tecnica-ingeniero]] — entrada técnica de extremo a extremo para ingeniería:
  web, datos, cerebro, automatizaciones, WhatsApp y despliegue.
- [`WhatsApp-Como-funciona.pdf`](WhatsApp-Como-funciona.pdf) — el canal multicanal
  explicado sin código: los dos tipos de número, por qué el receptor decide antes
  que el remitente, qué ve cada rol y qué falta por validar.
- [`Meta-Verificacion.pdf`](Meta-Verificacion.pdf) — qué hay que completar de
  verdad en Meta y qué se puede ignorar: los dos caminos, por qué la revisión de
  la aplicación no hace falta todavía, y cómo verificar cada pieza.
- [`WhatsApp-Puesta-en-marcha.pdf`](WhatsApp-Puesta-en-marcha.pdf) — runbook visual
  para llevar Meta Cloud API del número de prueba a clientes reales: canal central,
  alta de números comerciales, plantillas y prueba con dos negocios. El `.html` del
  mismo nombre es la fuente: se edita ahí y se reimprime el PDF.
- [`Conectar-Correo.pdf`](Conectar-Correo.pdf) — guía del correo saliente con
  Brevo: por qué un servidor no puede enviar solo, autenticar el dominio para no
  caer en spam, las dos variables y la prueba de aceptación.
- [`Conectar-Google.pdf`](Conectar-Google.pdf) — guía completa del acceso con
  Google: por qué bloquea hoy el panel de administración, los cinco pasos en la
  consola, las dos variables, la prueba de aceptación y los errores típicos.
- [[Conectar-APIs]] — guía única de credenciales, callbacks, variables y pruebas
  externas para conectar producción sin confundir código con servicio activo.
- [[Demo-comercial]] — dos accesos dentro del SaaS real, portal de cliente,
  credenciales, solo lectura y activación segura.
- [[IA-local]] — servicio privado, enrutamiento y límites de IA.
- [[Analisis-coste-IA.ipynb]] — cálculo reproducible de coste y autoalojamiento.
- [`Noesis-Modelo-Economico.xlsx`](Noesis-Modelo-Economico.xlsx) — modelo vivo:
  supuestos, unit economics, escenarios, proyección a 24 meses, sensibilidad,
  capacidad de soporte, captación y KPIs del piloto. Se regenera con
  `python analysis/build_modelo_economico.py`.
- [`Estrategia-Marketing.pdf`](Estrategia-Marketing.pdf) — a quién vendemos, con qué
  mensaje, por qué canales, cuánto podemos pagar por un cliente, dónde entra la IA
  y las vías de escape con sus criterios de parada.
- [`Marketing-Noesis.pdf`](Marketing-Noesis.pdf) — **manual maestro de marketing**:
  consolida la estrategia, la marca, las 24 piezas de contenido con su gancho, copy,
  CTA y métrica, la producción, la publicación en Instagram y Facebook, la medición
  y los criterios de parada. Sustituye a `Estrategia-Marketing` y `Publicar-en-redes`.
- [`Publicar-en-redes.pdf`](Publicar-en-redes.pdf) — manual operativo de publicación
  en Instagram y Facebook. Su contenido está incorporado al manual maestro.
- [`Ruta-legal.pdf`](Ruta-legal.pdf) — qué falta para poder cobrar el primer euro:
  Veri*Factu como productor, App Review de Meta, AI Act y protección de datos; tres
  rutas completas con su coste y el material para encargar las revisiones.
- [`Plan-60-dias.pdf`](Plan-60-dias.pdf) — el plan de ejecución que pone fecha a todo
  lo anterior: cuatro frentes en paralelo, nueve semanas y una puerta de salida por
  semana.
- [`Estado-Noesis.xlsx`](Estado-Noesis.xlsx) — estado de cada pieza en hoja de cálculo:
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
- [[Despliegue]] — cómo operar Noesis online 24/7 en bynoesis.com.
- [[Decisiones]] — registro de decisiones importantes (y por qué).
- [[Metodo-operativo-Fable]] — el criterio de trabajo, heredable por Opus y Codex.
- [[Preguntas-abiertas]] — dudas que esperan respuesta del founder.
- [[Estado-traspaso-MVP]] — estado real y traspaso entre agentes.
- [`AI_HANDOFF_TEMPLATE.md`](AI_HANDOFF_TEMPLATE.md) — plantilla de traspaso.

## Estado en una frase

No se repite aquí para evitar desincronizaciones. Consulta [[Estado-actual-main]]
para la fotografía auditada y [[Tareas-vivas]] para lo siguiente.

> Fundador: graduado en ADE, 23 años, ya tiene una empresa de eventos. Capital
> inicial ~4.000 €. Rol: negocio/dirección. Desarrollo: Claude.
