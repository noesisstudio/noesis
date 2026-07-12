# Mapa de código

- `src/noesis/web/server.py`: ensamblador FastAPI, seguridad y registro de routers.
- `src/noesis/web/routers/`: páginas, APIs, portales y webhooks por dominio.
- `src/noesis/web/routers/projects.py`: API de proyectos, equipo y entradas de coste.
- `src/noesis/web/templates/base.html`: navegación y marco compartido.
- `src/noesis/web/templates/resumen.html`: parte del día y Home progresiva.
- `src/noesis/web/templates/proyectos.html`: resumen, listado y detalle de proyecto.
- `src/noesis/web/static/app.css`: tokens, componentes y responsive.
- `src/noesis/db.py`: única frontera de acceso a datos; siempre con `business_id`.
- `src/noesis/migrations.py`: esquema versionado. Versión actual: 21.
- `src/noesis/web/chat.py`: parte diario, conversación persistente por canal y
  explicación contextual.
- `src/noesis/agent.py`: contexto de IA con historial, recuerdos confirmados y
  señales explicables de clientes.
- `src/noesis/adapters/extraction.py`: extracción y clasificación documental común
  para web y WhatsApp.
- `src/noesis/documents/service.py`: entrada documental universal, propuesta de
  tipo y confirmación humana antes de convertir o contabilizar.
- `src/noesis/web/routers/documents.py`: documentos y facturas recibidas.
- `src/noesis/web/routers/assistant.py`: conversación, historial y memoria de
  Noesis aislados por negocio.
- `src/noesis/web/routers/webhooks.py`: salud, Stripe y WhatsApp.
