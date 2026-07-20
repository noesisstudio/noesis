# Plan maestro de Noesis

> Documento estable de dirección de producto, diseño, tecnología, operaciones,
> finanzas y marketing. No contiene una fotografía operativa. Para saber qué existe
> o qué falta, consultar [[Estado-actual-main]] y [[Tareas-vivas]].

## 1. Visión, misión y promesa

**Visión:** ser el sistema operativo sencillo del autónomo de servicios: una
oficina digital que entiende qué ocurre, ejecuta administración segura y deja al
profesional centrarse en su oficio.

**Misión:** quitar ruido mental del ciclo completo:

```text
petición → presupuesto → agenda → trabajo → proyecto → coste
         → factura → cobro → documentos → gestoría
```

**Promesa:** «Noesis lleva la oficina mientras tú haces el trabajo».

Noesis no es otro programa de facturas con un chat añadido. Es un acompañante
persistente que conoce el estado del negocio, explica lo importante, propone la
siguiente acción y ejecuta lo autorizado por web o WhatsApp.

## 2. Público inicial

- Autónomos y microempresas de servicios de 1 a 10 personas.
- Fontanería, electricidad, climatización, reformas, mantenimiento, limpieza y
  jardinería.
- Trabajo coordinado principalmente por WhatsApp.
- Facturación tardía, cobros lentos y documentos dispersos.
- Poco tiempo o interés por aprender un ERP.

La personalización por sector llega después de demostrar retención y patrones
repetibles en este segmento.

## 3. Experiencia objetivo

La primera capa responde siempre:

1. ¿Cómo está mi negocio?
2. ¿Qué debo hacer ahora?
3. ¿Qué está haciendo Noesis por mí?

Quien no entiende de números recibe lenguaje llano, significado y una acción. Quien
sí entiende conserva cálculos, evidencia, histórico y desglose. El nivel de
explicación es una preferencia de cuenta, no un selector repetido en cada pantalla.

Una jornada ideal:

- Noesis prepara el día y prioriza.
- El trabajador recibe su trabajo, ficha y registra materiales/evidencias.
- Proyecto, horas, coste, avance y margen se actualizan sin doble entrada.
- Al terminar queda una factura preparada, nunca emitida sin control.
- El cliente recibe seguimiento profesional hasta cobrar.
- Los documentos se clasifican y llegan ordenados a la gestoría.
- El autónomo recibe tranquilidad, explicación y siguiente acción.

## 4. Principios no negociables

### Local e interno primero

Orden de preferencia:

1. reglas y cálculos deterministas;
2. librerías ligeras en infraestructura propia;
3. modelo privado cuando calidad y coste total lo justifiquen;
4. proveedor externo autorizado para lo que aporte valor diferencial.

«Local» no significa gratis: se comparan CPU/GPU, RAM, operación, latencia, soporte,
calidad y privacidad frente al coste por llamada.

### IA útil desde el primer día

La experiencia completa se recomienda en el onboarding, con decisión explícita y
reversible. El orden es reglas → IA privada → IA externa consentida y limitada.
Agotar créditos o perder un proveedor nunca desactiva la operativa local. Ver
[[IA-local]].

### Autonomía con control

Noesis puede ordenar, calcular, clasificar, preparar borradores, recordar y ejecutar
reglas de bajo riesgo previamente autorizadas. Transferencias, pagos, devoluciones,
impuestos, emisión definitiva, envíos sensibles y borrados irreversibles exigen
confirmación específica. Preparar no equivale a autorizar.

### Datos honestos

- Explicar evidencia y separar hecho, cálculo, hipótesis y sugerencia.
- Decir «datos insuficientes» en vez de inventar una predicción.
- Distinguir memoria confirmada de patrón observado.
- Permitir corregir y borrar preferencias no sujetas a conservación legal.

### Seguridad y aislamiento

- Toda operación filtra por `business_id`.
- Webhooks firmados, idempotentes, durables y reintentables.
- Accesos de trabajador, cliente y gestoría mínimos y revocables.
- Historial, memoria y documentos bajo exportación/borrado RGPD aplicable.
- El servidor valida herramientas y permisos; nunca se confía en el modelo.

### Simplicidad progresiva

Home y listados muestran situación, acción y pocas cifras. El detalle se abre por
capas. Noesis tiene voz humana y profesional; no imita un dashboard fintech ni
oculta datos importantes.

## 5. Arquitectura de producto objetivo

```text
evento, mensaje o documento
  → contexto de negocio, cliente, proyecto, pantalla y canal
  → regla local / modelo privado / proveedor externo autorizado
  → propuesta con evidencia y nivel de riesgo
  → confirmación cuando corresponde
  → herramienta autorizada
  → resultado registrado
  → aprendizaje explicable y corregible
```

La columna operativa es única:

```text
proyecto → trabajo → trabajador → fichaje → coste laboral
         → material/gasto/documento → avance → factura → cobro → margen
```

No se pide al autónomo duplicar horas, costes o documentos entre módulos.

## 6. Capacidades de la suite

### Autónomo

- Parte diario, agenda, clientes, presupuestos, facturas y cobros.
- Proyectos con presupuesto, equipo, horas, materiales, avance, coste y margen.
- Documentos universales con clasificación, confianza y revisión.
- CRM y seguimiento; comunicación y trazabilidad por cliente.
- Integraciones configurables sin perder el funcionamiento local.

### Trabajador

- Panel personal, trabajos/proyectos asignados y contexto necesario.
- Fichaje append-only separado del parte operativo.
- Checklist, notas, incidencias, fotos, materiales y cierre.
- Permisos por rol, correcciones trazables y privacidad proporcional.

### Gestoría

- Periodos y carpetas estables para ingresos, gastos, recibidas y justificantes.
- Originales, manifiesto, huella, versión, entrega y descarga trazables.
- Solicitudes bidireccionales y revisión humana.
- A futuro: cuentas/MFA, multiempresa, revisión documental e integración contable.

### WhatsApp

- Canal completo para texto, audio, imagen y PDF.
- Misma fuente de verdad, herramientas y permisos que la web.
- Una pregunta clara cuando haya ambigüedad; nunca fingir certeza.
- Outbox durable, plantillas aprobadas, estados, reintentos y soporte humano.

### Cobros y administración silenciosa

- Detectar trabajo terminado sin facturar y preparar borrador.
- Recordar cobros con cadencia autorizada, tono profesional y opt-out.
- Conciliar cuando exista integración; nunca mover dinero silenciosamente.
- Ordenar documentos y preparar entregas a gestoría.

## 7. Posicionamiento y referencias

- **Forjia:** referencia directa de WhatsApp, facturación, gastos y gestoría. Noesis
  debe diferenciarse por orquestación, parte diario, campo y rentabilidad.
- **Holded/Quipu:** referencias de mercado para profundidad contable. Noesis no les
  delega la facturación; construye internamente la parte regulada y solo conecta
  directamente con la administración o infraestructura imprescindible.
- **Jobber/ServiceTitan:** referencia de operación de campo, dispatch, checklists,
  job costing, rutas y portal cliente.
- **TaxDome/Dext:** referencia de gestoría, documentos, revisión y multi-cliente.

Diferenciación defendible:

1. parte diario y siguiente acción;
2. trabajo administrativo ejecutado, no solo datos;
3. seguimiento profesional de cobros;
4. conexión del campo con margen y caja;
5. memoria y aprendizaje explicables;
6. sencillez inicial y profundidad accesible;
7. continuidad real entre WhatsApp, web, trabajador y gestoría.

No se copia código propietario. Se estudian patrones y se implementa arquitectura
propia, modular y legal.

## 8. Orden estratégico

El orden operativo concreto vive en [[Tareas-vivas]]. La secuencia estable es:

1. Publicar y validar el ciclo ya construido.
2. Conectar Meta, pagos y fiscalidad reales con auditoría y recuperación.
3. Pilotar con 3-5 negocios y soporte cercano.
4. Corregir fiabilidad y fricciones que bloqueen el ciclo completo.
5. Profundizar equipo, documentos, gestoría e integraciones comunes.
6. Personalizar por sector solo con evidencia de retención.
7. Añadir automatización avanzada si mantiene control y unit economics.

## 9. Puertas de calidad

Una capacidad no se llama terminada hasta cumplir, según su riesgo:

- aislamiento `business_id` y permisos por rol;
- caso feliz, error, reintento, concurrencia e idempotencia;
- revisión humana para dinero, fiscalidad y acciones irreversibles;
- privacidad, exportación y borrado;
- responsive, teclado, accesibilidad y copy claro;
- métrica de uso, coste, latencia, fallo y corrección;
- documentación sin duplicar estado;
- migración PostgreSQL y rollback;
- smoke tras despliegue y prueba real del canal.

Nunca confundir construido, fusionado, desplegado y validado con clientes.

## 10. Métricas para decidir

### Valor de producto

- tiempo hasta primer resultado útil, factura y cobro;
- porcentaje del ciclo completado sin ayuda;
- trabajos terminados sin facturar;
- documentos corregidos y recomendaciones útiles;
- minutos administrativos ahorrados;
- dinero cobrado antes o margen protegido;
- retención D30/D90.

### Negocio

- MRR, churn y margen bruto por plan;
- coste de IA, WhatsApp, infraestructura y soporte por cuenta;
- CAC, recuperación y expansión;
- concentración por sector y caso de uso.

### Operaciones

- disponibilidad, latencia p50/p95 y 5xx;
- colas WhatsApp/Veri*Factu, fallos y reintentos;
- precisión/corrección de documentos y herramientas de IA;
- restauraciones verificadas e incidentes de seguridad.

Los objetivos orientativos —no resultados actuales— son: primera utilidad en menos
de dos minutos, proyecto actualizado sin doble entrada, mensajería recuperable,
coste compatible con el plan y cero acciones monetarias incorrectas.

## 11. Instrucciones para futuras IA

1. Leer `AGENTS.md`, [[Estado-actual-main]], [[Tareas-vivas]] y diseño antes de actuar.
2. Verificar rama, diff, migración y despliegue; no confiar en un traspaso antiguo.
3. Buscar si la capacidad existe antes de duplicarla.
4. Conectar módulos existentes antes de crear otra pantalla.
5. Comparar alternativa interna y coste total antes de añadir una API.
6. No hacer claims fiscales, de IA o WhatsApp sin prueba real.
7. Registrar decisiones estructurales, QA y cambios de estado una sola vez.

## 12. Norte

Noesis habrá cumplido cuando el fontanero pueda hacer de fontanero: la oficina se
mantiene ordenada, el trabajo llega al equipo, el coste llega al proyecto, la
factura queda preparada, el cliente recibe seguimiento, la gestoría obtiene los
papeles y el autónomo conserva el control sin cargar con el ruido mental.
