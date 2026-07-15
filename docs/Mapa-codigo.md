# Mapa de código

## Núcleo

- `src/noesis/db.py`: única frontera de datos. Toda operación de negocio filtra por
  `business_id`. Incluye proyectos, permisos, integraciones, salud operativa y
  entregas a gestoría.
- `src/noesis/migrations.py`: esquema SQLite/Postgres. `main` llega a 27.
- `src/noesis/tools.py`: herramientas que puede invocar el cerebro: clientes,
  agenda, facturas, proyectos, equipo, documentos y gestoría.
- `src/noesis/nlu.py`: cerebro local para órdenes rutinarias sin coste de LLM.
- `src/noesis/internal_brain.py`: compositor local de comunicaciones. Usa hechos del
  negocio, evita ambigüedad y deja el envío pendiente de SÍ/NO del titular.
- `src/noesis/agent.py`: agentes privado, compatible y Anthropic con historial, recuerdos
  confirmados, permisos efectivos y contexto del negocio.
- `src/noesis/adapters/ai.py`: cliente stdlib OpenAI-compatible compartido por el
  servicio privado y el proveedor externo barato.
- `src/noesis/readiness.py`: diagnóstico de piloto sin secretos para seguridad,
  datos, copias, WhatsApp, correo, Stripe, AEAT, IA y operaciones.
- `deploy/local-ai/`: Ollama privado ligado a localhost y perfil de descarga de
  Qwen3 8B para evaluación; no expone el modelo ni lo convierte en un SLA.
- `analysis/build_unit_economics.mjs`: genera el modelo editable de costes, márgenes,
  escala, sensibilidad de IA y controles; fuente narrativa en
  `docs/Analisis-unit-economics.ipynb`.
- `docs/project-state.json`: fuente de verdad legible por máquinas para versión de
  esquema, pruebas, precios, publicación, política de suscripción y validaciones
  externas pendientes.
- `scripts/check_project_truth.py`: compara esa fuente con migraciones y catálogo;
  en CI exige actualizar estado y QA cuando cambia el producto.

## Web y acompañante

- `src/noesis/web/server.py`: ensamblador FastAPI, seguridad y routers.
- `src/noesis/web/deps.py`: aislamiento de sesión y modo consulta transversal. Una
  cuenta inactiva puede leer; toda mutación web/API devuelve redirección o HTTP 402.
- `src/noesis/web/routers/assistant.py`: conversación, memoria, permisos y registro
  de acciones de Noesis.
- `src/noesis/web/chat.py`: parte del día, plan operativo y acompañamiento. Resuelve
  por reglas, después por IA privada, proveedor compatible y Anthropic; los niveles
  externos comparten consentimiento y un crédito por mensaje.
- `src/noesis/web/templates/base.html`: capa persistente de Noesis: lectura real de
  la sección, siguiente paso con motivo, preguntas contextuales y conversación.
- `src/noesis/web/routers/projects.py`: proyectos, trabajos vinculados, tareas,
  equipo, horas y costes.
- `src/noesis/web/routers/portal.py`: portales privados de cliente, gestoría y
  trabajador; incluye parte de campo y conformidad.
- `src/noesis/db.py`: `job_materials`, `job_updates`, `job_completions` y
  `client_preferences` conectan trabajo, coste, evidencia, borrador y aprendizaje.
- `src/noesis/web/templates/proyectos.html`: resumen progresivo y detalle operativo.
- `src/noesis/web/templates/fichaje.html`: jornada, trabajos y checklist personal.
- `src/noesis/web/routers/account.py`: API del centro de integraciones y ajustes de
  cuenta; no guarda secretos de proveedores por negocio.
- `src/noesis/web/templates/ajustes.html`: preferencias, memoria, control de Noesis,
  conexiones y lectura plegable de salud operativa.
- `src/noesis/web/static/app.css`: tokens, componentes y responsive sin CDN.

## Documentos, gestoría y canales

- `src/noesis/documents/service.py`: entrada universal, clasificación y confirmación
  antes de contabilizar.
- `src/noesis/documents/repo.py`: metadatos y vínculos con cliente, proyecto, gasto o
  factura recibida.
- `src/noesis/web/gestoria.py`: paquete ordenado, manifiesto, huella y versionado.
- `src/noesis/web/whatsapp.py`: texto, audio local, fotos/PDF, confirmaciones,
  trabajador y cola durable. La entrada y la salida se detienen en modo consulta.
- `src/noesis/web/scheduler.py`: partes, recordatorios y reglas previamente
  autorizadas; consulta el centro de control y la suscripción antes de actuar.
- `src/noesis/adapters/`: Meta, email, pagos, voz, extracción y fiscalidad detrás de
  fronteras reemplazables. La extracción externa respeta la decisión de IA de cada
  negocio y conserva el clasificador local cuando está desactivada.
