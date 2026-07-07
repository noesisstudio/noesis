# Traspaso: Documentos inteligentes v1 (facturas recibidas + clasificación)

- **De → para:** Fable 5 → Codex (implementación) / Opus (revisión de alcance)
- **Fecha:** 2026-07-07
- **Rama:** `codex/documentos-inteligentes` (crear desde `main`)
- **Nivel de confianza del que entrega:** alto en el diseño, medio en el tamaño
  (puede necesitar partirse en dos PRs: migración+backend primero, UI después)
- **¿Requiere revisión antes de implementar?** Sí: las preguntas 6 y 7 de
  [[Preguntas-abiertas]] (entidad `received_invoices` y tabla `suppliers`) tienen
  propuesta pero el founder no las ha confirmado una a una. Si no responde, seguir
  la propuesta (entidades propias) y dejarlo anotado en el PR.

### 1. Contexto del producto
Noesis convierte la "caja de zapatos" de papeles en un flujo trazable
documento→factura/gasto→gestoría. Hoy `documents/` guarda archivos, hace OCR de
imágenes y extrae borradores de gasto con Claude Vision. Esta tarea lo convierte
en un pipeline con tipos, estados y destinos, y añade la mitad que falta del ciclo:
facturas **recibidas** y proveedores. Ver [[Producto]] y [[Metodo-operativo-Fable]] §4.

### 2. Objetivo de la tarea
Que al subir un documento, el sistema proponga tipo (factura emitida/recibida,
ticket/gasto, presupuesto, otro), datos y destino con confianza visible, y que el
usuario confirme o corrija antes de que exista ningún registro contable.

### 3. Estado actual
- Funciona ya: subida/validación/almacenado por negocio (`documents/service.py`,
  `storage.py`, `repo.py`), OCR de imágenes (`ocr.py`), borrador de gasto por foto
  (`adapters/extraction.py`, prompt seguro anti-inyección), conversión
  ticket→gasto con confirmación, vínculo documento↔gasto, backup de documentos.
- A medias: la clasificación solo distingue "tiene importe o no"; no hay tipos ni
  estados ni destino; los PDF no se extraen (solo imágenes).
- NO existe: facturas recibidas, proveedores, estados documentales, historial de
  correcciones del usuario.

### 4. Decisiones tomadas
- La extracción **nunca crea registros**: borrador → confirmación humana. Ya es
  así para gastos; se mantiene para todo. — [[Decisiones]] (implícito en método §5).
- El prompt se enriquece portando el de FacturAI (líneas, NIF emisor/receptor,
  confianza 0-100) **dentro del estilo del adaptador actual** (validación estricta
  campo a campo, contenido de imagen = datos, no instrucciones). No copiar su stack.
- Clasificación emitida/recibida comparando NIFs extraídos con el NIF del negocio
  (idea `_detect_empresa_context` de FacturAI, reescrita).

### 5. Decisiones pendientes
- PREGUNTA 6 y 7 de [[Preguntas-abiertas]] (entidades propias vs. extensión).
  Propuesta por defecto: tablas nuevas `suppliers` y `received_invoices`.

### 6. Mapa de la tarea
- **Archivos:** `src/noesis/migrations.py` (migración 17, aditiva),
  `src/noesis/db.py` (funciones nuevas, seguir el estilo de las de `expenses`),
  `src/noesis/documents/service.py` y `repo.py` (tipo/estado/destino),
  `src/noesis/adapters/extraction.py` (segunda función `extract_invoice`),
  `src/noesis/web/server.py` (rutas API de revisión/confirmación),
  `src/noesis/web/templates/documentos.html` y `costes.html`.
- **Tablas nuevas (migración 17):** `suppliers` (por negocio),
  `received_invoices` (proveedor, fechas, base/IVA/total, estado de pago,
  `document_id`), columnas en `documents`: `doc_type`, `doc_status`, `confidence`,
  `reviewed_at`, `review_note`. Todo con `business_id` y FKs compuestas como las
  tablas existentes.
- **Estados documentales:** `pendiente_revisar` → `revisado` →
  `enviado_gestoria` → `validado`; más `rechazado`/`duplicado`.
- **Servicios a reutilizar:** todo `documents/`, el patrón de borrador de
  `extraction.py`, el paquete gestoría (`web/gestoria.py`) debe incluir las
  recibidas en el ZIP y el CSV.

### 7. Riesgos y qué NO hacer
- No tocar tablas append-only (Veri*Factu, fichaje) ni `web/auth.py`.
- No dejar que un fallo de extracción bloquee la subida (degradación digna).
- No renombrar columnas existentes de `documents`; solo añadir.
- El paquete gestoría no puede romperse: si no hay recibidas, el ZIP sale igual.
- Si el diseño de `received_invoices` empieza a duplicar `expenses`, parar y
  preguntar antes de seguir.

### 8. Criterios de aceptación
- [ ] Subo una factura recibida (foto o PDF) → borrador con tipo, proveedor,
      importes y confianza → confirmo → existe `received_invoice` vinculada al
      documento y al proveedor.
- [ ] Subo un ticket → flujo actual de gasto intacto.
- [ ] Si la IA no está segura (o no hay clave), el documento queda
      `pendiente_revisar` sin datos inventados.
- [ ] Puedo corregir tipo/proveedor/fechas/importes antes de confirmar; la
      corrección queda registrada (`review_note`/historial).
- [ ] El ZIP de gestoría incluye las recibidas del período.
- [ ] Migración 17 con upgrade/downgrade probados; tests verdes (126 + nuevos).
- [ ] Aislamiento por `business_id` en toda consulta nueva.
- [ ] Estados vacío/cargando/error en las vistas tocadas; páginas en 200.

### 9. Pruebas mínimas
Tests nuevos: alta/lectura de proveedor y recibida con aislamiento multiempresa;
documento sin clave IA queda pendiente sin datos; confirmación crea la recibida y
vincula el documento; downgrade de la migración 17. Manual: flujo completo desde
móvil (cámara) en `documentos.html`.

### 10. Próximo paso recomendado
Escribir la migración 17 + funciones de `db.py` con sus tests **antes** de tocar
ninguna plantilla. Si el PR crece, cortar ahí y entregar la UI en un segundo PR.

### 11. Preguntas para el founder
Ninguna bloqueante si se aceptan las propuestas 6-7 de [[Preguntas-abiertas]].
