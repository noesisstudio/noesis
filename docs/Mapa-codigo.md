# Mapa de código

## Núcleo

- `src/noesis/db.py`: única frontera de datos. Toda operación de negocio filtra por
  `business_id`. Incluye proyectos, tareas, permisos de autonomía y entregas a
  gestoría.
- `src/noesis/migrations.py`: esquema SQLite/Postgres. La rama
  `codex/operating-spine` llega a la migración 24.
- `src/noesis/tools.py`: herramientas que puede invocar el cerebro: clientes,
  agenda, facturas, proyectos, equipo, documentos y gestoría.
- `src/noesis/nlu.py`: cerebro local para órdenes rutinarias sin coste de LLM.
- `src/noesis/agent.py`: IA opcional con historial, recuerdos confirmados,
  permisos efectivos y contexto del negocio.

## Web y acompañante

- `src/noesis/web/server.py`: ensamblador FastAPI, seguridad y routers.
- `src/noesis/web/routers/assistant.py`: conversación, memoria, permisos y registro
  de acciones de Noesis.
- `src/noesis/web/chat.py`: parte del día, plan operativo, avisos de proyecto y
  acompañamiento contextual por pantalla.
- `src/noesis/web/routers/projects.py`: proyectos, trabajos vinculados, tareas,
  equipo, horas y costes.
- `src/noesis/web/routers/portal.py`: portales privados de cliente, gestoría y
  trabajador.
- `src/noesis/web/templates/proyectos.html`: resumen progresivo y detalle operativo.
- `src/noesis/web/templates/fichaje.html`: jornada, trabajos y checklist personal.
- `src/noesis/web/templates/ajustes.html`: preferencias, memoria y centro de control.
- `src/noesis/web/static/app.css`: tokens, componentes y responsive sin CDN.

## Documentos, gestoría y canales

- `src/noesis/documents/service.py`: entrada universal, clasificación y confirmación
  antes de contabilizar.
- `src/noesis/documents/repo.py`: metadatos y vínculos con cliente, proyecto, gasto o
  factura recibida.
- `src/noesis/web/gestoria.py`: paquete ordenado, manifiesto, huella y versionado.
- `src/noesis/web/whatsapp.py`: texto, audio local, fotos/PDF, confirmaciones,
  trabajador y cola durable.
- `src/noesis/web/scheduler.py`: partes, recordatorios y reglas previamente
  autorizadas; consulta el centro de control antes de actuar.
- `src/noesis/adapters/`: Meta, email, pagos, voz, extracción y fiscalidad detrás de
  fronteras reemplazables.
