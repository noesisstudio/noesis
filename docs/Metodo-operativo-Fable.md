# Método operativo de Fable

> **Qué es este documento.** El cerebro operativo de Fable 5 aplicado a Bynoesis,
> escrito para ser heredado. No es una guía de estilo ni una lista de normas: es el
> criterio con el que se ha ordenado este producto, explicado para que **Opus pueda
> revisar estrategia** y **Codex pueda ejecutar código** sin reinterpretar el
> proyecto desde cero. Si trabajas en este repo y solo puedes leer dos documentos,
> lee [`AGENTS.md`](../AGENTS.md) y este.
>
> Se actualiza cuando cambia el criterio general (ver §9, protocolo de continuidad).
> Última revisión de continuidad: **2026-07-20**.
>
> **Dirección de producto y diseño (fijada 2026-07-08):** la piel y el lenguaje de
> Bynoesis se rigen por `docs/design/` — [`PRODUCT_PRINCIPLES.md`](design/PRODUCT_PRINCIPLES.md)
> (la frase pilar, el modelo mente/cuerpo y las seis leyes), [`DESIGN.md`](design/DESIGN.md),
> [`UX_COPY.md`](design/UX_COPY.md) y [`STYLE_TOKENS.json`](design/STYLE_TOKENS.json).
> Antes de tocar cualquier pantalla o copy, léelos.

---

## 1. Cómo Fable entiende el producto

**Qué es Bynoesis.** Un sistema operativo de negocio para autónomos y pequeñas
empresas de servicios, con WhatsApp como canal diferencial y un asistente que actúa
como apoyo de CEO/CFO/administrativo/comercial. No es "una app de IA": la IA es el
acompañante, no el producto. El producto es **orden**: agenda, clientes, cobros,
facturas, documentos y gestoría conectados con trazabilidad.

**Qué problema real resuelve.** El autónomo de servicios (fontanero, reformas,
limpieza…) pierde dinero y calma por tres vías: trabajos hechos sin facturar,
facturas sin cobrar y la caja de zapatos de papeles para la gestoría. Bynoesis cierra
el ciclo *"del trabajo terminado al dinero cobrado"* y convierte la caja de zapatos
en un paquete ordenado. Todo lo demás (CRM, proyectos, ratios) orbita alrededor de
ese ciclo; si una función no lo alimenta, es secundaria.

**Cliente mental de referencia.** Una persona con las manos ocupadas, que gestiona
desde el móvil, en ratos muertos, con poca paciencia para software. Cada pantalla
debe responder: *qué pasa, qué falta, qué hago ahora*. Ver [[Producto]] y
[[Benchmark_SaaS]].

**Qué NO debe convertirse Bynoesis.**
- Un ERP genérico con cuarenta menús (eso ya existe y aburre al cliente objetivo).
- Un chatbot que promete y no persiste nada.
- Un panel de demos: pantallas bonitas sin backend son deuda, no progreso.
- Un asesor fiscal automático. La app **prepara** (clasifica, calcula, sugiere);
  la gestoría **decide**. Nada fiscal se presenta como definitivo sin revisión
  humana. Ver [[Fiscalidad]].

**Módulos centrales vs. secundarios.** Centrales: facturas/cobros, gastos y
documentos, agenda/Hoy, clientes, gestoría, asistente. Secundarios (valiosos, pero
solo después de que lo central funcione con clientes reales): productos/stock,
proyectos/obras, CRM de leads, finanzas avanzadas, multiidioma, Telegram.

**Límites del asistente.** No inventa datos: si falta un dato, dice cuál falta.
Distingue dato real / estimación / recomendación. No ejecuta acciones irreversibles
(enviar mensajes a clientes, crear gastos desde una foto) sin confirmación. Está
acotado al negocio del usuario (`business_id`), siempre.

---

## 2. Cómo Fable prioriza

Orden de evaluación ante cualquier propuesta de trabajo:

1. **¿Acerca dinero cobrado o quita papeles de encima?** Es el valor directo. Una
   mejora en cobros vale más que tres dashboards.
2. **¿Se conecta con lo que ya existe** (facturas, documentos, agenda, clientes,
   gestoría) **o vive aislada?** Lo aislado se aplaza.
3. **¿Se usa a diario o una vez al trimestre?** Diario gana.
4. **¿Qué dependencias técnicas tiene?** Si depende de algo pendiente (credenciales
   de Meta, certificado AEAT, decisión de i18n), se documenta y se aplaza, no se
   simula.
5. **¿Puede romper lo que funciona?** La app está en producción con auto-deploy:
   el coste de romper es real. Cambios aditivos > cambios estructurales.
6. **¿Riesgo de pantalla falsa?** Si no da tiempo a hacer la persistencia, no se
   hace la pantalla.
7. **¿Riesgo legal/fiscal/datos?** Fiscalidad, fichaje y Verifactu tienen
   requisitos legales; los datos personales, RGPD. Ante duda, revisión humana y
   pregunta al founder.

Regla práctica de MVP: una función entra en el MVP si puede **persistir, validarse
y probarse** en la iteración; si solo puede *verse*, no entra. Se divide en fases
hasta que la primera fase cumpla eso.

**Urgente vs. importante.** Urgente = lo que bloquea el piloto con clientes reales
(hoy: credenciales, dominio, fricciones del ciclo completo). Importante = lo que
hace el producto defendible (documentos inteligentes, gestoría interactiva). El
error clásico es construir lo importante sin desbloquear lo urgente: el piloto
manda, la plataforma crece por capas en paralelo (decisión registrada en
[[Decisiones]]).

---

## 3. Cómo Fable diseña arquitectura

La arquitectura actual (ver [[Arquitectura]]) ya encarna estas reglas; toda pieza
nueva debe respetarlas:

- **Un solo punto de acceso a datos** (`db.py`): nada de ORMs paralelos ni SQL
  suelto en rutas. Esquema versionado en `migrations.py` con upgrade/downgrade.
- **Aislamiento por negocio, sin excepciones.** Toda consulta y escritura filtra
  por `business_id`. Un módulo que "de momento" no filtra es un bug, no un atajo.
- **Lógica fuera de las plantillas.** Las plantillas Jinja pintan; los servicios
  (`documents/service.py`, `web/gestoria.py`, `web/chat.py`) deciden. Si una regla
  de negocio vive en un template o en JS, está en el sitio equivocado.
- **Integraciones detrás de adaptadores** (`adapters/`): facturación, email,
  extracción, transcripción. Cambiar de proveedor = tocar un archivo. Los canales
  (WhatsApp hoy, Telegram mañana) siguen el mismo patrón: los módulos hablan con la
  abstracción, nunca con la API del canal.
- **Degradación digna.** Sin `ANTHROPIC_API_KEY` funciona el NLU local; sin SMTP,
  se registra en el log; sin OCR, se guarda el documento igual. Ninguna función
  opcional puede tumbar una esencial.
- **Mínimas dependencias.** stdlib primero. Cada dependencia nueva se justifica en
  el commit y se registra en [[Decisiones]] si es estructural.
- **Trazabilidad como dato de primera clase.** Quién subió, qué detectó el sistema,
  qué corrigió el usuario, qué se envió a la gestoría, qué fue automático y qué
  manual. Las tablas append-only (Verifactu, fichaje) son **intocables**: se lee,
  jamás se altera ni se borra.
- **Entidades reutilizables, módulos conectados.** Antes de crear una tabla nueva,
  comprobar si una existente sirve (¿"proveedor" es un `client` con rol, o entidad
  propia? Se decide mirando consultas reales, no por simetría estética).

---

## 4. Cómo Fable analiza una funcionalidad nueva

Checklist que se aplica antes de escribir código (y que Opus puede usar para
revisar y Codex para ejecutar):

1. **Problema y usuario**: ¿qué duele y a quién? Si la respuesta empieza por
   "estaría bien que…", va a la nevera.
2. **Módulo donde encaja**: ¿extiende algo existente o abre módulo nuevo? Extender
   gana casi siempre (ej.: "documentación inteligente" = extender `documents/`, no
   crear un módulo paralelo).
3. **Datos**: qué entidades toca, qué migración necesita, si es aditiva
   (columna/tabla nueva = segura) o estructural (renombrar/mover = consultar).
4. **Pantallas**: qué vista nueva o qué sección de una existente; con sus cuatro
   estados obligatorios (vacío, cargando, error, con datos).
5. **Permisos**: quién lo ve (dueño, trabajador, gestoría, cliente del portal) y
   qué token/rol lo protege.
6. **Conexión con el asistente**: ¿qué pregunta del usuario debe poder responder
   sobre esto? Si ninguna, quizá no es del núcleo.
7. **Qué pasa si faltan datos**: la respuesta nunca es "se inventa"; es "se
   muestra qué falta".
8. **Qué NO se automatiza todavía**: por defecto, todo lo que envía mensajes
   fuera, crea registros fiscales o toma decisiones con dinero pide confirmación.
9. **División en fases**: ¿cuál es la rebanada que persiste + valida + se prueba
   esta iteración? El resto, al [[Roadmap]].
10. **Cómo se prueba**: qué test de regresión lo cubre y qué flujo manual hay que
    ejecutar antes de cerrar (arrancar servidor, páginas en 200, flujo completo).

**Detector de funcionalidad decorativa.** Una función es decorativa si: no
escribe en la base de datos, muestra números que no salen de datos reales, tiene
botones que solo navegan, o "quedará conectada más adelante". Se elimina o se
marca visiblemente como demo. En producción, jamás mock data sin marcar.

---

## 5. Cómo Fable evita errores (anti-patrones con historia)

- **No asumir que la documentación refleja el repo.** Auditar antes de actuar: en
  la fase 0 de 2026-07-07, cuatro ramas "pendientes de revisión" según los docs
  resultaron estar ya fusionadas en `main`. Verificar con `git`, no con memoria.
- **No operar git sin `git branch --show-current`.** Ya causó confusión una vez
  (2026-06-30). Desde la decisión del founder de 2026-07-20 se trabaja sobre
  `main`: primero `git pull --ff-only`, árbol limpio, un solo escritor y nada se
  empuja sin pruebas. Cada cambio queda en [[Registro-cambios]].
- **No fusionar stacks ajenos.** El proyecto FacturAI se usa como referencia y se
  portan piezas al estilo propio (ver [[Decisiones]]); traer su SQLAlchemy/JWT
  habría creado dos formas de hacer todo.
- **No crear cálculos financieros sin datos suficientes**: "datos insuficientes,
  falta X" es una respuesta correcta; un número inventado es un bug grave.
- **No automatizar lo fiscal**: preparar sí, presentar no. Siempre revisión humana.
- **No dejar que la extracción por IA cree registros**: extrae → borrador →
  confirmación humana → registro. Así funciona el gasto por foto y así funcionará
  todo lo documental.
- **No tratar el contenido de una imagen o documento como instrucciones** (defensa
  anti prompt-injection ya presente en `adapters/extraction.py`; mantenerla en
  toda extracción nueva).
- **No tocar Verifactu/fichaje sin entender su cadena de integridad** (hashes
  encadenados; una edición "inocente" invalida la cadena legal).
- **No ocultar limitaciones**: si algo quedó a medias o sin probar, se dice en el
  commit y en el handoff. Un "hecho" falso cuesta más que un "pendiente" honesto.

---

## 6. Qué deja Fable preparado para Opus (estrategia)

Opus revisa con criterio de negocio. Estado de las decisiones (detalle y fechas en
[[Decisiones]] y [[Preguntas-abiertas]]):

- **Tomadas**: suite completa construida modular; WhatsApp como cuña; portal
  cliente sin contraseña; piloto primero con plataforma por capas; FacturAI como
  referencia (no fusión); vault de documentación = `docs/` (no duplicar en otra
  estructura); fiscalidad siempre con revisión humana.
- **Abiertas que requieren criterio de negocio**: proveedor avanzado del piloto,
  tratamiento del IVA en Stripe, momento de i18n completa, profundidad del portal
  de gestoría y modelo comercial de voz. La lista viva y sus propuestas están solo
  en [[Preguntas-abiertas]]. WhatsApp real ya es una tarea P0, no una decisión.
- **Dónde está el valor defendible**: la combinación documento→factura→cobro→
  gestoría con trazabilidad. Los competidores tienen piezas; la orquestación con
  asistente es la diferencia. Ver [[Competencia]].
- **Riesgo estratégico a vigilar**: morir de alcance. Cada módulo nuevo debe
  pagarse con uso real del piloto, no con la ilusión de completitud.
- **Simplificable sin perder valor**: stock avanzado, ratios financieros
  completos, aprendizaje de preferencias — todo eso es V2 y no debe adelantarse.

---

## 7. Qué deja Fable preparado para Codex (ejecución)

Codex ejecuta sin desviarse de la arquitectura. Reglas de trabajo:

- **Antes de tocar código**: leer `AGENTS.md`, [[Estado-actual-main]],
  [[Tareas-vivas]] y la tarea
  con sus criterios de aceptación. Verificar que se está en `main`, actualizado y
  limpio, salvo que el founder haya pedido expresamente una rama/PR.
- **Qué existe y dónde**: el mapa vivo es [[Mapa-codigo]]; la versión de esquema y
  las pruebas están únicamente en [`project-state.json`](project-state.json). Las
  rutas viven en `web/routers/`, los datos en `db.py` + `migrations.py`, documentos
  en `documents/`, IA en `agent.py` / `nlu.py` / `web/chat.py` y proveedores en
  `adapters/`.
- **Qué NO tocar sin tarea explícita**: tablas append-only (`invoice_records`,
  `worker_clockins`, eventos Verifactu), `web/auth.py`, la cadena de huellas de
  `verifactu.py`, y cualquier `DROP`/renombrado de columnas.
- **Toda tarea llega con**: archivos a tocar, entidades implicadas, criterios de
  aceptación, y qué migración (si la hay) — en el formato de
  [`AI_HANDOFF_TEMPLATE.md`](AI_HANDOFF_TEMPLATE.md).
- **Definición de "hecho"**: migración con upgrade/downgrade probados, tests de
  regresión verdes (`python -m unittest discover -s tests`), estados
  vacío/cargando/error en la UI, textos en español, aislamiento por `business_id`
  verificado, y servidor arrancado con las páginas afectadas en 200.
- **Si la tarea pide algo que contradice este método** (ej.: pantalla sin
  persistencia, cálculo sin datos), no se ejecuta en silencio: se anota la
  contradicción en el handoff y se pregunta.

---

## 8. Transferencia entre modelos

Toda entrega de trabajo entre modelos (Fable→Codex, Fable→Opus, Codex→Fable…) usa
[`AI_HANDOFF_TEMPLATE.md`](AI_HANDOFF_TEMPLATE.md). Sin handoff no hay traspaso:
un mensaje de chat no es un traspaso. El handoff vive como archivo en `docs/` o
como descripción del PR, y debe poder leerse **sin acceso a la conversación que lo
originó**.

---

## 9. Protocolo de continuidad

Al cerrar una iteración importante, actualizar **solo lo que haya cambiado**:

| Si cambió… | Actualizar |
|---|---|
| El criterio general de trabajo | Este documento |
| Una decisión de producto/arquitectura | [[Decisiones]] (la más reciente arriba, con el porqué) |
| La arquitectura o el modelo de datos | [[Arquitectura]] |
| Prioridades inmediatas | [[Tareas-vivas]] |
| Dirección por etapas | [[Roadmap]] |
| Estado verificable | `project-state.json` + [[Estado-actual-main]] |
| Dudas pendientes del founder | [[Preguntas-abiertas]] |
| Credenciales o pruebas externas | [[Conectar-APIs]] |
| Hay traspaso a otro modelo | Nuevo handoff desde la plantilla |

Regla anti-ruido: no duplicar contenido entre documentos; enlazar. Un dato en dos
sitios es un dato desincronizado en potencia (esta misma auditoría encontró el
estado de ramas desactualizado en dos documentos a la vez).

---

## 10. Resultado esperado

Que el proyecto no dependa de qué modelo lo trabaja. Opus debe poder leer §1, §2 y
§6 y revisar una propuesta con el mismo criterio estratégico que Fable. Codex debe
poder leer §3, §4, §5 y §7 y escribir código que parezca escrito por la misma
mano. El founder debe poder leer [[Decisiones]] y [[Preguntas-abiertas]] y saber
siempre qué se decidió, por qué, y qué espera su respuesta.
