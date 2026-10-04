# ADR-016 — Epoch, T0 y fence transaccional

Estado: implementado en1.9C; validación final registrada en [cierre](FASE-1.9C-cierre.md).
Orden humana: [1.9C](FASE-1.9C-orden.md). No1.9D. Complementa ADR013/015.

## Problema y decisión

Un doble scan sin drift no prueba ausencia de un writer anterior que confirme
después del reloj. T0 nace después de adquirir el gate1.8H por negocio, tras acabar
writers anteriores, en una TX corta que persiste epoch+control+audit y fence ON.
No MAX(id), timestamp de inicio de TX PG ni locks durante scan. Generación sale
del control durable por tenant; unique parcial impide dos epochs no liberados.

Los writers de aplicación autentican sin locks, toman gate bloqueante, revalidan
sesión/suscripción bajo FOR SHARE y consultan control antes de operación/fuente.
Así un waiter no bloquea UPDATE de negocio/usuario del dueño del gate. La revocación
anterior al gate se observa al revalidar; la posterior espera la TX autorizada.
SQL directo relevante toma el mismo advisory con try-lock en BEFORE row trigger;
si otro lo posee devuelve conflicto cerrado, evitando row→gate deadlock. Su gate
dura hasta commit/rollback y el SELECT volatile del control observa el último
commit READ COMMITTED. Aislamientos superiores se rechazan para mutación directa.
SQLite BEGIN IMMEDIATE comparte invariantes observables, con contención global.

## Inventario sin promover diagnóstico

Migración70 permanece byte a byte. Migración71 añade cuatro tablas de control:
epochs, control, cut_manifests y epoch_audit. **cut_manifests es el sobre lógico
certifiable_inventory** de una ejecución NUEVA, con FK tenant a los manifests/items
de B usados como almacenamiento del scanner. El carrier B siempre sigue diagnostic
y certifiable=false por sus CHECK originales. No se puede adjuntar un carrier
con items/frozen ni un diagnóstico previo, ni cambiar mode/epoch/identidad.
No se duplica scanner/classifier/planning ni cambian reglas A/B/C/D.

Cada página de lectura/persistencia y agregación semántica valida el epoch bajo
gate corto; cierre final persiste hashes/certificación en TX breve. Índices71 sobre
terminal/severity/incidence-code permiten los guards finales sin recorrer todo
el inventario. Source y plan coinciden entre scans; raw binario no adquiere certeza.
Un corte consistente puede contener incidencias financieras BLOCKED: certificar
el inventario no acredita importabilidad, reconciliación ni activación.

## Transporte, documentos y autoridad

El scope C v1 mantiene todas las fuentes B, neutraliza campos de transporte de
outboxes y excluye remision/aceptacion/rechazo. Respuesta de remisión previa puede
registrarse sin cambiar huella fiscal/source hash. Nuevo claim/intento/dispatch
está bloqueado: gate durante llamada bounded del worker; open espera dispatch
anterior. Este coste solo afecta una llamada del mismo negocio. Sin llamada AEAT
en tests ni nuevo envío en esta fase.

Documents conservan membership completo: altas también bloqueadas; OCR/notas
fuera de proyección permitidos. stored_name/filename/mime/size protegidos. Unlink
detrás de gate y cascada cliente mueve DB a una TX antes de borrar bytes.
Revisiones64 cambian aun por note/match_score: esas columnas también se protegen.
Preferencias, sesión, mensajes, quote puro/contador quote y reminders ajenos al
hash siguen disponibles. No event log operacional ni IA autorizadora.

historical.record equivale a operador activo del negocio con sesión actual y
cuenta escribible, como B; release/invalidate requieren el mismo opened_by.
No financial.authorize ni autorización humana histórica inventada. FKs y guards
exigen actor activo del tenant. SQL de sources no puede pasar fence; DDL privilegiado,
desactivar triggers, control DML fuera de servicio o editar volumen a mano no son
APIs soportadas de operación. Las transiciones de epoch revocan el certificado y
sincronizan control también por trigger, sin borrar ni reescribir hashes.

## Fallos, liberación y límites

Invalidated conserva fence ON; released lo apaga y pierde boundary_current.
Certifiable significa certificado actualmente vigente: al revocar pasa false,
con hashes/frozen original intactos y auditoría. TTL solo attention_required.
Crash BaseException/muerte de proceso conserva fence y T0; retry exacto reanuda
manifest. Errores del scanner invalidan sin release; solicitudes inválidas/permisos/
conflictos no abortan un epoch ajeno. Sin purge ni política legal nueva.

Cinco flags OFF; no EE histórico, Operations históricas, cobertura histórica,
v2 durable, importer, reconciliación, GL/Tax/AR/AP/reporting/activación. Sin producción.
[Contrato](FINANCIAL-HISTORY-CUTOFF-v1.md) · [writers](FASE-1.9C-writers.md).
