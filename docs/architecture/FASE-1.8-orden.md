Las Fases 1.1–1.7 quedan aceptadas.

Ejecuta exclusivamente:

**FASE 1.8 — Integración segura de canales, Action Review, WhatsApp/chat/web y recurrentes con los servicios Financial Core ya construidos**

NO avances a 1.9.

Esta fase NO crea nuevos Economic Event types ni nuevos motores financieros.

Su objetivo es hacer que los canales reales del producto puedan invocar de forma segura los servicios canónicos ya existentes:

- InvoiceCapture
- PaymentCapture
- BankCapture
- SupplierInvoiceCapture
- ExpenseCapture

manteniendo:

identidad durable
+
request exacto
+
revisión
+
autorización durable
+
ejecución idempotente.

---

# 1. PRINCIPIO CENTRAL

Los canales NO ejecutan directamente writers financieros.

La cadena debe ser:

usuario/canal
→ interpretación
→ propuesta concreta
→ FinancialRequest
→ EntryIdentity estable
→ review
→ autorización durable
→ servicio Capture canónico
→ FinancialOperations
→ writer + Economic Event + resultado
→ commit
→ respuesta al canal

La IA puede:

- interpretar;
- extraer;
- preguntar;
- preparar;
- explicar.

La IA NO puede:

- escoger operation_uuid;
- fabricar EntryIdentity;
- aprobar;
- saltar confirmación;
- cambiar el request después de aprobado;
- llamar writers internos directamente.

---

# 2. AUDITORÍA PREVIA DE ENTRADAS

Antes de modificar código, inventaría todas las entradas actuales que pueden terminar en una mutación financiera:

### Web
- emitir factura;
- rectificativa;
- registrar cobro;
- marcar cobrada;
- confirmar banco;
- importar banco;
- recibida;
- corregir/retirar recibida;
- gasto;
- retirar gasto.

### Chat web

### WhatsApp

### Tools / agent

### Revisión documental

### Recurrentes / scheduler

### cualquier endpoint/API o adaptador interno alternativo.

Para cada camino indica:

- identidad disponible;
- propuesta/request;
- cómo se confirma actualmente;
- dónde se guarda pending;
- actor;
- business;
- sesión;
- posibilidad de retry;
- posibilidad de doble clic/mensaje;
- servicio Capture canónico que debe usar;
- si puede conectarse ahora o debe quedar bloqueado.

No conectar una ruta sin identidad/autorización suficiente.

---

# 3. ENTRY IDENTITY POR CANAL

Implementa o completa factories server-side estables.

## Web/API

Una acción financiera debe tener UUID durable generado/gestionado por servidor/cliente autenticado.

Doble clic y retry de la misma acción:

→ misma identidad.

Nueva intención legítima:

→ nueva identidad.

---

## Chat web

La identidad debe derivar de una fuente durable del mensaje/turno y del slot de acción.

Conceptualmente:

chat_message_id
+
proposal/action slot.

No usar texto del mensaje como identidad.

---

## WhatsApp

La identidad debe usar valores reales y no controlados por el modelo.

Conceptualmente:

provider
+
business/recipient
+
WhatsApp message ID durable (`wamid` o equivalente real)
+
action slot/version.

Un mensaje repetido por webhook:

→ misma operación.

Dos mensajes distintos con el mismo texto:

→ operaciones distintas.

---

## Document review

Identidad durable:

review UUID / document ID
+
item
+
revision.

No usar OCR result hash como única identidad de intención.

---

## Recurrentes

Identidad estable por vencimiento:

business
+
recurring schedule
+
scheduled occurrence.

Nunca UUID aleatorio nuevo por cada retry del worker.

---

# 4. ACTION_REVIEW

Éste es un punto crítico.

Actualmente el sistema histórico puede consumir/eliminar la propuesta antes o durante la ejecución.

Para toda acción financiera capturada:

**la autorización durable debe existir ANTES de eliminar/consumir la propuesta temporal.**

Orden obligatorio:

propuesta actual
→ usuario confirma versión exacta
→ crear/vincular Financial Operation
→ persistir Financial Authorization
→ solamente entonces consumir/archivar pending temporal
→ execute

Si falla la persistencia de autorización:

pending debe seguir siendo recuperable.

Si falla execute después de autorización:

retry debe reutilizar la misma operation_uuid.

No crear otra propuesta/operación automáticamente.

---

# 5. CORRECCIÓN DE PROPUESTAS

Si el usuario responde corrigiendo un dato:

“sí, pero son 120 €”

NO modificar el request ya aprobado.

Debe generarse:

nueva versión/propuesta
→ nuevo request/hash
→ nueva aprobación.

Una autorización nunca debe cubrir contenido distinto del mostrado al usuario.

---

# 6. CONFIRMACIÓN HUMANA

El usuario debe poder saber qué está aprobando.

Para acciones financieras muestra una síntesis concreta suficiente según el dominio.

Ejemplos:

Factura:
- destinatario;
- importe;
- IVA/IRPF relevante;
- fecha;
- acción “emitir”.

Cobro:
- factura;
- importe;
- fecha;
- método cuando exista.

Recibida/gasto:
- proveedor/concepto;
- importe;
- fecha;
- acción.

Banco:
- movimiento;
- factura propuesta;
- importe.

No hace falta mostrar términos contables internos.

No mostrar:

journal entries
debe/haber
EconomicEvent UUID
hashes técnicos

al autónomo salvo diagnóstico.

---

# 7. YES / NO

Confirmación positiva debe estar ligada a una propuesta específica y su revisión.

“sí” aislado no puede aprobar:

- otra propuesta antigua;
- una propuesta modificada;
- otro negocio;
- otro usuario;
- otro mensaje.

“no” o cancelar:

→ operación/propuesta queda rechazada/cancelada según corresponda;
→ ningún efecto financiero.

Doble “sí”:

→ mismo resultado;
→ cero duplicados.

---

# 8. EXPIRACIÓN / STALE

Antes de autorizar y antes de ejecutar:

revalidar según el Capture service correspondiente.

Si source/revisión/contexto cambió:

→ no ejecutar;
→ informar que necesita revisar de nuevo;
→ crear nueva propuesta/request si el usuario continúa.

Nunca ajustar silenciosamente.

---

# 9. WHATSAPP WEBHOOK RETRIES

Probar explícitamente:

Meta entrega el mismo webhook varias veces.

Resultado:

- una propuesta;
- una EntryIdentity;
- una operación;
- una autorización;
- un efecto.

No usar únicamente memoria de proceso para deduplicar.

La identidad debe sobrevivir a reinicio.

---

# 10. MENSAJES DE CONFIRMACIÓN REPETIDOS

Ejemplo:

usuario:
“sí”

Meta reenvía ese mensaje.

No debe producir una segunda acción.

La identidad de la confirmación y la operación deben permitir replay seguro.

---

# 11. CHAT / TOOLS

Los tools que actualmente puedan mutar directamente dominios financieros deben clasificarse.

Para acciones capturadas:

tool/agent
→ prepara Capture request/proposal

NO:

tool
→ writer financiero directo.

Si existe una herramienta que actualmente emite/cobra/crea gasto directamente:

mantener compatibilidad legacy con flags OFF si procede,

pero el camino Financial Core debe usar exclusivamente Capture service.

No habilitar al LLM acceso directo a:

- financial_writers;
- EconomicEvents.append;
- FinancialOperations.execute arbitrario.

---

# 12. WEB

Conecta las rutas web que dispongan de contexto suficiente.

Usar:

- usuario autenticado;
- business;
- sesión;
- CSRF/controles existentes;
- EntryIdentity estable.

Un refresh/retry después del commit:

→ recuperar resultado.

Un doble submit:

→ no duplicar.

No inventar autorización implícita porque el usuario pulse un endpoint genérico.

La UI debe hacer explícita la confirmación cuando la política actual la exija.

---

# 13. DOCUMENTOS

Conecta revisión documental a:

- SupplierInvoiceCapture
- ExpenseCapture

solo cuando el usuario confirma los datos.

OCR/extraction:

→ prepara campos.

No:

OCR
→ execute automático.

La revisión debe conservar:

document_id
+
document fingerprint/revision
+
campos mostrados
+
request hash.

Cambiar documento/clasificación entre review y execute:

→ stale.

---

# 14. BANK IMPORT

Importar CSV puede preparar múltiples operaciones.

NO aprobar todo el batch implícitamente por haber subido el archivo.

Mantén la semántica aprobada de 1.6.

Cada fila financiera tiene identidad estable.

Si el producto ofrece confirmación por lote, esa aprobación debe dejar evidencia durable de qué requests exactos cubría.

No construir un workflow genérico de batch.

---

# 15. RECURRENTES

Este punto requiere especial cuidado.

El writer de Fase 1.4 ya es componible; ahora conecta identidad y autorización.

Una ocurrencia recurrente debe tener identidad:

schedule
+
scheduled_for

estable entre retries/workers.

Nunca generar una identidad nueva porque el scheduler reinició.

---

# 16. AUTORIDAD PARA RECURRENTES

NO uses una confirmación humana antigua como permiso abierto ilimitado si el contrato de 1.2 no lo permite.

Antes de implementar, analiza el modelo actual de recurrencia.

Debes diferenciar:

A) configuración operativa de recurrencia

de

B) autoridad financiera para emitir una ocurrencia concreta.

Si actualmente no existe evidencia durable suficiente de que el usuario autorizó emisión automática de futuras facturas:

**no inventes esa autoridad.**

En ese caso:

- el scheduler puede preparar la factura/propuesta;
- el usuario debe confirmar la emisión;
- o debe existir un mandato durable explícito y acotado antes de automatizarla.

---

# 17. MANDATO RECURRENTE

Solo si el producto ya dispone de una autorización explícita adecuada o si puede modelarse de forma mínima y segura dentro de los contratos existentes:

un mandato debe estar acotado por ejemplo a:

- business;
- recurring schedule;
- destinatario;
- reglas de importe;
- impuestos;
- concepto;
- frecuencia;
- período/expiración;
- límites.

NO crear un permiso como:

“puede emitir cualquier factura futura”.

Si ampliar el modelo de mandato excede el alcance de 1.8:

no lo hagas.

Deja recurrentes en modo propuesta + confirmación humana.

**Seguridad antes que automatización.**

---

# 18. WORKER RECURRENTE

Probar:

dos workers procesan la misma ocurrencia.

Resultado:

una sola operación/ocurrencia.

Fallos:

- antes de preparar;
- después de preparar;
- después de autorización;
- durante emisión;
- después de commit antes de marcar scheduler.

Retry:

→ recuperar operación/resultado existente.

No crear factura duplicada.

---

# 19. RESPUESTA DESPUÉS DE COMMIT

Una respuesta de WhatsApp/web puede fallar después de que la operación ya haya terminado.

Eso NO debe hacer retry del efecto.

La respuesta posterior puede consultar:

operation_uuid
→ result durable

y volver a informar al usuario.

Separar:

efecto financiero
de
entrega de mensaje.

---

# 20. ERRORES DE CANAL

Meta caído, navegador cerrado, timeout HTTP, websocket perdido:

NO deben cambiar semántica financiera.

Si commit ocurrió:

→ resultado durable.

Si no ocurrió:

→ operación permanece reintentable según estado.

No inferir éxito a partir de que se envió un mensaje.

---

# 21. FLAGS

Los cinco flags financieros siguen apagados globalmente salvo infraestructura necesaria para tests.

NO activar todavía cuentas reales.

No implementar 1.10.

Los bridges pueden existir detrás de flags/gates.

Captura solicitada explícitamente:

→ nunca fallback silencioso.

---

# 22. LEGACY

Mientras flags estén OFF:

los caminos legacy no capturados pueden seguir funcionando según compatibilidad aprobada.

Pero no introduzcas nuevas rutas directas legacy.

Y cualquier source YA capturado mantiene los guards de fases anteriores.

No debilitar protección para facilitar canales.

---

# 23. PRIVACIDAD

La evidencia durable debe guardar lo mínimo necesario.

NO copiar conversaciones completas dentro de Financial Operations o Authorizations.

Guardar:

- message/action identifier;
- canal;
- actor;
- hash/request;
- revision;
- timestamps;
- evidencia mínima de aprobación.

No convertir el Financial Core en archivo completo de chat.

---

# 24. MIGRACIÓN

Añadir únicamente metadatos mínimos de canal/bridge que sean imprescindibles.

Evitar tablas si las de:

- financial_operations;
- financial_authorizations;
- pending actions;
- recurring runs

pueden representar correctamente la identidad.

No crear:

- GL;
- Tax Ledger;
- Open Items;
- historial/backfill;
- activación por cuenta;
- event bus;
- workflow engine.

---

# 25. TESTS WHATSAPP

Como mínimo:

- propuesta;
- sí;
- no;
- corrección;
- doble sí;
- webhook duplicado;
- confirmación duplicada;
- mensaje distinto mismo texto;
- proposal stale;
- reinicio entre proposal y confirm;
- reinicio después de commit antes de respuesta;
- otra empresa/usuario;
- sesión revocada.

Comprobar un solo efecto.

---

# 26. TESTS WEB

- doble submit;
- refresh;
- timeout tras commit;
- request UUID repetido;
- request UUID + contenido diferente;
- sesión expirada;
- CSRF/permiso existente;
- otra empresa.

---

# 27. TESTS CHAT/TOOLS

- tool prepara pero no ejecuta sin aprobación;
- modelo intenta cambiar importe;
- modelo intenta proporcionar operation UUID;
- modelo intenta invocar writer directamente;
- corrección genera nueva versión;
- “sí” solo consume propuesta exacta.

---

# 28. TESTS DOCUMENTALES

- OCR prepara;
- usuario corrige;
- nueva propuesta;
- confirmación;
- Economic Event una sola vez;
- clasificación/documento cambia → stale;
- PDF batch no autorizado sigue bloqueado.

---

# 29. TESTS RECURRENTES

- misma ocurrencia dos workers;
- retry después de crash;
- schedule modificado;
- schedule desactivado;
- mandato revocado si existe;
- autorización insuficiente;
- fecha/importe distinto al autorizado.

No emitir automáticamente si la autoridad durable no está demostrada.

---

# 30. NO NUEVOS EVENTOS

No modificar catálogo.

Los bridges solo pueden terminar en productores ya autorizados:

- invoice.issued
- invoice.rectified
- customer_payment.received
- bank_transaction.imported
- bank_transaction.matched
- supplier_invoice.confirmed
- supplier_invoice.corrected
- supplier_invoice.voided
- expense.confirmed
- expense.voided

`invoice.fiscal_cancellation_registered` sigue sin conectarse salvo orden específica posterior.

No absorber eventos operativos.

---

# 31. AUTOAUDITORÍA

Antes de cerrar responde:

1. ¿Puede la IA ejecutar directamente un writer?
2. ¿Puede inventar operation_uuid?
3. ¿Puede “sí” aprobar una propuesta distinta?
4. ¿Puede una propuesta consumirse antes de guardar autorización durable?
5. ¿Puede doble webhook duplicar un efecto?
6. ¿Puede timeout después del commit duplicarlo?
7. ¿Puede un canal cambiar el request aprobado?
8. ¿Puede una sesión revocada ejecutar?
9. ¿Puede un documento OCR aprobarse solo?
10. ¿Puede un recurrente emitir sin autoridad durable suficiente?
11. ¿Dos workers crean dos facturas?
12. ¿Se guardan conversaciones completas innecesariamente?
13. ¿Algún bridge hace fallback silencioso a legacy?
14. ¿Se ha adelantado históricos/activación/GL/Tax/OpenItems?

---

# CIERRE

Devuélveme:

- mapa de canales antes/después;
- bridges conectados;
- EntryIdentity por canal;
- flujo ActionReview;
- manejo de propuesta/versiones;
- autorización durable;
- WhatsApp;
- web;
- chat/tools;
- documentos;
- recurrentes;
- mandates si los hay;
- migración;
- pruebas SQLite;
- pruebas PostgreSQL;
- pruebas de procesos/retries;
- riesgos pendientes;
- canales que aún no puedan activarse;
- PASS/FAIL individual.

No declares 1.8 terminada si cualquier canal puede producir una mutación financiera sin pasar por identidad estable + request exacto + autorización durable + Capture service.

**No avances a 1.9.**