# Plan maestro de Noesis

> Documento de dirección para producto, diseño, tecnología, operaciones, finanzas
> y marketing. Es la referencia que debe leer cualquier IA antes de proponer o
> construir trabajo nuevo. Última revisión: 2026-07-12.

## 1. Propósito de este documento

Este documento separa con claridad:

- lo que está publicado;
- lo que ya está construido en una rama local;
- lo que funciona parcialmente;
- lo que todavía es visión;
- el orden recomendado para convertir Noesis en un MVP profesional y validable.

No sustituye la documentación especializada. Para fiscalidad, seguridad, diseño o
WhatsApp deben consultarse también `Fiscalidad.md`, `Arquitectura.md`,
`WhatsApp-Cerebro.md` y `docs/design/`.

## 2. Estado real a 2026-07-12

### Producción

- `https://app.bynoesis.com` está activa sobre Railway y Postgres.
- Railway despliega desde `main`.
- Producción todavía no contiene los dos últimos commits de producto.
- La última capa publicada corresponde aproximadamente a la plataforma base
  (migración 18), no al producto local completo descrito debajo.

### Rama de implementación preparada

Rama: `codex/mvp-professional`.

- `878ba64`: nueva Home, diseño progresivo, preferencia de explicación y proyectos
  rentables.
- `202b387`: acompañante persistente, memoria controlable, clasificación documental
  universal y señales explicables de clientes.
- Esquema local: migración 21.
- Verificación: 164 pruebas correctas.
- La rama todavía debe subirse, revisarse, fusionarse y desplegarse.

### Regla de comunicación

Nunca se debe confundir «construido localmente» con «publicado». Una función solo
se considera operativa para clientes cuando ha pasado revisión, migración de
producción, smoke tests y prueba real del canal correspondiente.

## 3. Visión y misión

### Visión

Ser el sistema operativo sencillo del autónomo de servicios: una oficina digital
que entiende qué ocurre, se ocupa de la administración y deja al profesional
centrarse en su oficio.

### Misión

Quitar ruido mental del ciclo completo:

```text
petición -> presupuesto -> agenda -> trabajo -> proyecto -> coste
         -> factura -> cobro -> documentación -> gestoría
```

### Promesa principal

> Noesis lleva la oficina mientras tú haces el trabajo.

Noesis no debe posicionarse como «otro programa de facturas con IA». La
facturación por WhatsApp ya es una categoría competida. La diferenciación debe ser
la coordinación proactiva del negocio: parte diario, siguiente acción, control de
cobros, rentabilidad, equipo, proyectos y gestoría.

## 4. Público inicial

El mercado potencial es amplio, pero el primer segmento debe ser concreto:

- autónomos y microempresas de 1 a 10 personas;
- fontanería, electricidad, climatización, reformas, mantenimiento, limpieza y
  jardinería;
- trabajo organizado principalmente mediante WhatsApp;
- facturación tardía, cobros lentos y documentos dispersos;
- poco tiempo o interés por aprender un ERP.

Ampliar a otros sectores solo después de validar retención y uso semanal en este
segmento.

## 5. Principios no negociables

### 5.1 Interno y local primero

Noesis debe resolver internamente todo lo que sea razonable para reducir coste,
dependencia, latencia y exposición de datos.

Orden de preferencia:

1. reglas y cálculos deterministas locales;
2. librerías ligeras ejecutadas en nuestra infraestructura;
3. modelos pequeños o procesamiento propio cuando el volumen lo justifique;
4. API externa solo cuando aporte una capacidad difícil de reproducir o reduzca
   claramente el coste total de operación.

Una API barata no siempre es más barata si genera dependencia, reintentos,
soporte, cambios de precio o riesgo de privacidad. Una solución interna tampoco es
gratis: consume RAM, CPU, mantenimiento y tiempo de ingeniería. La decisión debe
comparar coste total, no solo precio por llamada.

### 5.2 Arquitectura híbrida de IA

- NLU y cálculos locales para lo frecuente.
- IA externa opcional para lenguaje ambiguo o documentos complejos.
- Posibilidad futura de modelos propios para clasificación y extracción cuando
  exista volumen y un conjunto de datos autorizado.
- Ninguna acción económica, fiscal o irreversible se ejecuta por una inferencia
  silenciosa.

### 5.3 Datos honestos

- No inventar predicciones ni porcentajes de confianza.
- Explicar qué evidencia sustenta una recomendación.
- Mostrar «datos insuficientes» cuando corresponda.
- Distinguir hechos confirmados, cálculos, hipótesis y sugerencias.

### 5.4 Simplicidad progresiva

La primera capa debe responder tres preguntas:

1. ¿Cómo está mi negocio?
2. ¿Qué debo hacer ahora?
3. ¿Qué está haciendo Noesis por mí?

El detalle numérico permanece disponible por capas para usuarios avanzados.

### 5.5 Seguridad y aislamiento

- Toda operación filtra por `business_id`.
- Los webhooks se firman, deduplican y reintentan.
- El acceso de trabajador, cliente y gestoría es revocable.
- Dinero, impuestos, envíos y borrados requieren autorización adecuada.
- El historial y la memoria forman parte de la exportación y borrado RGPD.

## 6. Estado funcional por área

| Área | Estado | Lectura honesta |
|---|---|---|
| Base SaaS | Sólida | Login, sesiones, onboarding, suscripción, Postgres, migraciones y multiempresa. |
| Autonomía del usuario | Avanzada | Ciclo administrativo amplio, pero todavía exige trabajo manual entre módulos. |
| Diseño nuevo | Avanzado en rama | Coherente, cálido, progresivo y móvil; no está publicado. |
| Cerebro | Parcial | Buen núcleo híbrido, pero pocas herramientas y aprendizaje limitado. |
| WhatsApp | Avanzado en código | Texto, audio, imagen y PDF; falta validación real de extremo a extremo. |
| Documentos | Avanzado | Clasificación y revisión humana; falta corpus real y casos difíciles. |
| Clientes | Inicialmente inteligente | Señales explicables, no un modelo conductual completo. |
| Proyectos | Funcional aislado | Presupuesto, costes, horas y margen; no está conectado al trabajo de campo. |
| Equipo | Base sólida | Portal y fichaje legal; faltan tareas y operativa completa de campo. |
| Gestoría | Fase 1 sólida | Portal por token y paquetes; no es aún plataforma multi-cliente. |
| Fiscalidad | Avanzada técnicamente | Requiere validación y certificado reales antes de prometer operación completa. |
| Operaciones SaaS | Parcial | Faltan observabilidad, soporte, alertas y simulacros de escala. |
| Negocio y marketing | Por validar | Propuesta potente, pero competencia directa y sin pilotos suficientes. |

## 7. El cerebro final de Noesis

### Lo que ya existe

- NLU local para agenda, presupuestos, facturas, gastos, cobros y resúmenes.
- IA opcional para lenguaje complejo.
- Historial persistente entre web y WhatsApp.
- Memoria confirmada, visible y borrable.
- Contexto de página.
- Señales de cliente basadas en facturas, pagos, presupuestos y actividad.

### Lo que falta

Noesis todavía no aprende de forma completa los hábitos de cada cliente. Debe
construirse un perfil explicable que pueda incluir:

- canal y horario preferido;
- ritmo habitual de pago;
- respuesta a recordatorios;
- tasa y tiempo de aceptación de presupuestos;
- tipos de trabajo y rentabilidad histórica;
- incidencias, ampliaciones de alcance y sensibilidad al precio;
- resultado de las recomendaciones anteriores de Noesis.

### Arquitectura objetivo

```text
evento o mensaje
  -> contexto de negocio, cliente, proyecto y canal
  -> reglas locales / modelo interno / IA externa opcional
  -> propuesta con evidencia, confianza y nivel de riesgo
  -> confirmación cuando corresponda
  -> acción mediante una herramienta autorizada
  -> resultado observado
  -> aprendizaje corregible y auditable
```

### Capacidades pendientes del agente

- Proyectos, tareas y costes.
- Equipo, asignaciones y fitxajes.
- Documentos y revisión.
- Gestoría y solicitudes.
- CRM y seguimientos.
- Importación histórica.
- Automatizaciones configurables.
- Comunicación con clientes y soporte humano.

### Calidad necesaria

- Conjunto de pruebas con lenguaje real, errores y dialectos.
- Evaluaciones de precisión de herramientas y seguridad.
- Observabilidad de tokens, coste, latencia, fallos y correcciones.
- Resumen de conversaciones largas.
- Resolución de entidades ambiguas.
- Feedback útil/no útil y resultado de cada recomendación.

## 8. Experiencia del autónomo: pendientes

- Sincronización bancaria y conciliación.
- Calendarios externos.
- Facturas recurrentes.
- Reservas en línea.
- Rutas y desplazamientos.
- Mensaje «estoy de camino».
- Fotografías antes/después.
- Firma del cliente.
- Checklists por servicio.
- Materiales consumidos.
- Trabajo terminado -> factura preparada.
- Importación histórica segura.
- Enlace de pago y conciliación real.
- Historial completo de comunicación por cliente.
- Recuperación de errores y soporte humano.

No se debe construir una contabilidad general completa si puede integrarse con
Holded, Quipu u otro proveedor. Noesis debe poseer la experiencia y la
orquestación, y delegar la profundidad contable regulada cuando sea más eficiente.

## 9. Equipo y trabajador: pendientes

### Ya construido

- trabajadores, enlace personal y PIN;
- trabajos del día;
- entrada, pausa, reanudación y salida;
- GPS puntual y no continuo;
- historial y correcciones append-only;
- informes PDF/CSV;
- envío de jornada por WhatsApp.

### Falta para la operativa de campo

- mostrar proyectos asignados;
- tareas, subtareas y checklists;
- estado del trabajo;
- notas, fotos, vídeos e incidencias;
- materiales y gastos desde campo;
- firma del cliente;
- documentos y planos;
- notificaciones por cambios;
- modo offline;
- varios trabajadores por trabajo;
- permisos por rol;
- ausencias y disponibilidad;
- integración con nómina.

### Integración crítica

```text
proyecto -> trabajo/tarea -> trabajador -> fitxaje -> coste laboral
         -> material/gasto -> avance -> factura -> margen
```

Hoy proyecto, trabajo y fitxaje usan estructuras separadas. Su unión es uno de los
mayores multiplicadores de valor pendientes.

## 10. Proyectos: pendientes

La base calcula presupuesto, coste, horas, progreso y margen. Falta:

- conectar trabajos y tareas al proyecto;
- importar horas automáticamente desde fitxajes;
- convertir salarios/hora en coste laboral;
- vincular gastos, tickets, facturas de proveedor y materiales;
- adjuntar fotos y documentos;
- avisar antes de superar presupuesto u horas;
- facturación por hitos o certificaciones;
- permitir que el trabajador actualice avance y consumo;
- comparar rentabilidad por proyecto, servicio, trabajador y cliente.

## 11. Gestoría: pendientes

### Ya construido

- portal privado por token;
- períodos mensuales o trimestrales;
- ZIP con facturas emitidas, gastos, justificantes, resumen y XML cuando existe;
- CSV de facturas recibidas;
- solicitudes y respuestas bidireccionales.

### Correcciones próximas

- garantizar que los PDFs originales de facturas recibidas estén en el paquete;
- estructura clara por ingresos, gastos, recibidas y justificantes;
- trazabilidad de qué se envió y cuándo;
- bloqueo o versión de períodos cerrados.

### Fase profesional posterior

- cuentas de gestoría y MFA;
- una gestoría con varios negocios;
- permisos y auditoría;
- carpetas navegables y revisión documento a documento;
- aprobación, rechazo y corrección;
- descarga masiva;
- mensajería segura y notificaciones;
- integración con software contable;
- programa de partners.

## 12. WhatsApp: pendientes

### Ya construido en código

- texto, audio, imagen, PDF y caption;
- confirmaciones SÍ/NO;
- tickets y gastos;
- facturas recibidas;
- protección de facturas históricas emitidas;
- contratos, presupuestos y albaranes como documentos;
- webhook firmado, idempotencia, límites y outbox durable.

### Validación imprescindible

- audio con ruido y acentos reales;
- catalán/castellano mezclados;
- nombres similares;
- correcciones de importes;
- varios conceptos y acciones en un mensaje;
- fotos borrosas, inclinadas o incompletas;
- HEIC;
- PDFs escaneados y multipágina;
- conversaciones interrumpidas;
- recuperación de errores;
- soporte humano;
- coste y latencia por cuenta.

Noesis no debe prometer «entender todo». Debe entender mucho, reconocer cuándo no
está segura y formular una única pregunta clara.

## 13. Posicionamiento y competencia

### Forjia

Competidor directo en WhatsApp, facturación, gastos, cobros y gestoría. Comunica
además funciones recurrentes, albaranes, firma, idiomas, multiusuario y precios
inferiores. Referencias: `https://getforjia.com/` y
`https://getforjia.com/advisors/`.

### Holded

Referencia de profundidad en contabilidad, bancos, proyectos, inventario, CRM,
RRHH e integraciones. Noesis debe integrarse cuando convenga, no copiar su
complejidad. Referencia: `https://www.holded.com/es/funcionalidades`.

### Jobber y ServiceTitan

Referencias de operativa de campo: dispatch, app de trabajador, checklists, GPS,
coste laboral, rutas, portal cliente y job costing.

### TaxDome y Dext

Referencias para gestoría: documentos, portal seguro, revisión, flujos,
mensajería y multi-cliente.

### Diferenciación defendible

Noesis debe destacar en:

1. parte diario y siguiente acción;
2. trabajo administrativo ejecutado, no solo datos mostrados;
3. persecución profesional de cobros;
4. conexión del campo con margen y caja;
5. memoria y aprendizaje explicables;
6. simplicidad para quien no entiende de números;
7. profundidad disponible para quien sí la necesita.

## 14. Riesgos actuales

1. Confundir código preparado con función publicada.
2. Prometer WhatsApp o Veri*Factu antes de validar el extremo real.
3. Competir solo en facturación por WhatsApp.
4. Crear demasiados módulos sin conectarlos.
5. Mostrar un cerebro más capaz que sus herramientas reales.
6. No medir coste total de IA, WhatsApp, soporte e infraestructura.
7. No disponer de corpus real de documentos y conversaciones.
8. Falta de observabilidad y escalado humano.
9. Público inicial demasiado amplio.
10. No demostrar ahorro de tiempo ni dinero recuperado.

## 15. Orden de ejecución recomendado

### P0 - Publicar y pilotar con seguridad

1. Subir y revisar `codex/mvp-professional`.
2. Fusionar en `main` mediante PR.
3. Backup y prueba de migraciones 19-21 en Postgres.
4. Desplegar y ejecutar smoke tests.
5. Revisar promesas públicas de WhatsApp y Veri*Factu.
6. Completar herramientas del cerebro para módulos críticos.
7. Unir proyecto, trabajo, trabajador, fitxaje y coste.
8. Garantizar paquetes completos de gestoría.
9. Crear demo rica con proyectos y equipo.
10. Probar documentos, audios y lenguaje real.
11. Añadir monitorización, alertas y soporte.
12. Ejecutar un piloto completo con un negocio.

### P1 - Durante el piloto

1. Importación histórica segura.
2. Calendario, email y pagos.
3. Conciliación bancaria.
4. Facturas recurrentes.
5. Checklists, fotos, materiales y firmas.
6. Perfil inteligente de cliente.
7. Feedback sobre recomendaciones.
8. Métricas de ahorro y cobro.
9. Primera versión de gestoría multi-cliente.

### P2 - Después de demostrar retención

1. Rutas inteligentes.
2. Recepcionista telefónico.
3. App nativa y funcionamiento offline avanzado.
4. Geofencing automático.
5. Inventario profundo.
6. Portal de gestoría avanzado y partners.
7. Modelos propios entrenados con datos autorizados.

## 16. Puertas de calidad antes de producción

Una función no está terminada hasta cumplir:

- aislamiento `business_id`;
- prueba feliz, error, reintento e idempotencia;
- revisión humana para dinero/fiscalidad;
- exportación y borrado RGPD;
- responsive y teclado;
- copy sin tecnicismos innecesarios;
- métrica de uso y fallo;
- documentación actualizada;
- migración Postgres probada;
- smoke test de producción y rollback definido.

## 17. Métricas de producto, negocio y operaciones

### Producto

- tiempo hasta el primer resultado útil;
- tiempo hasta primera factura y primer cobro;
- porcentaje del ciclo completo;
- tareas administrativas resueltas sin ayuda;
- trabajos terminados sin facturar;
- documentos que requieren corrección;
- recomendaciones aceptadas y útiles;
- retención D30/D90.

### Finanzas

- MRR y margen bruto por plan;
- coste de IA, WhatsApp e infraestructura por cuenta;
- minutos de soporte por cuenta;
- CAC y período de recuperación;
- churn y expansión;
- dinero cobrado antes gracias a Noesis.

### Operaciones

- disponibilidad y latencia;
- tasa de 5xx;
- mensajes fallidos/reintentados;
- outbox WhatsApp y Veri*Factu;
- errores de clasificación;
- restauración de backups;
- incidentes de seguridad y privacidad.

## 18. Criterios orientativos de «MVP profesional»

- Ninguna acción monetaria incorrecta.
- Más del 80% de peticiones habituales resueltas sin ayuda humana.
- Primera experiencia de valor en menos de dos minutos.
- Primera factura en menos de 24 horas.
- Clasificación documental útil superior al 90%, siempre revisable.
- Mensajería entregada o recuperada por encima del 99%.
- Coste por cuenta compatible con el margen de cada plan.
- Proyecto con horas y costes actualizados sin doble entrada manual.
- Backups restaurables y alertas activas.
- Evidencia real de ahorro de tiempo, menos impagos o mayor margen.

Estos son objetivos recomendados, no resultados actuales.

## 19. Instrucciones para futuras IA

Antes de actuar:

1. Leer `AGENTS.md`, este documento y los principios de diseño.
2. Verificar rama y estado de producción.
3. Buscar si la capacidad ya existe para no duplicarla.
4. Distinguir publicado, construido, simulado y pendiente.
5. Priorizar integración entre módulos antes que nuevas pantallas.
6. Preferir solución interna/local cuando sea segura y económicamente sensata.
7. No añadir una API sin comparar coste total y alternativa interna.
8. No hacer claims fiscales, de IA o WhatsApp sin prueba real.
9. Actualizar documentación y QA al cambiar estado estructural.
10. Entregar siempre qué se probó y qué quedó bloqueado.

## 20. Norte del producto

El resultado final no es un dashboard. Es una jornada como esta:

- Noesis prepara el día y prioriza.
- El trabajador recibe su trabajo, ficha y registra materiales.
- El proyecto actualiza horas, coste, avance y margen.
- Al terminar, queda la factura preparada.
- El cliente recibe, paga y se hace seguimiento.
- Los documentos se clasifican y llegan a la gestoría.
- El autónomo recibe una explicación sencilla y una siguiente acción.

Cuando todo ese flujo ocurra sin duplicar datos ni perseguir personas, Noesis será
el empleado digital que promete ser.
