# 06 · RGPD y seguridad

## 2026-10-06 — Alcance C: registry y anulación fiscal interna

[Orden](../architecture/FASE-1.10C-orden.md), [contrato](../architecture/FINANCIAL-CAPABILITIES-FISCAL-CANCELLATION-v1.md), [ADR021](../architecture/ADR-021-capabilities-fiscal-cancellation.md), [cierre](../architecture/FASE-1.10C-cierre.md).

Zona nueva: src/noesis/financial_activation/capabilities.py y
src/noesis/fiscal_cancellation_capture/{service,schema}.py. A/B CODE-VERIFIED PASS.
Monolito modular y repositorios especializados sobre FinancialSession/gate/TX
compartidos. Registry único de A con spec v1 y once mappings cerrados, sin
enforcement/routing. FiscalCancellationCapture interno reutiliza writer fiscal:
resolución B durable live/verified/resolved, revalidación every_use, autoridad
humana exacta, registro/outbox pendiente/coverage/EE evidence-only/result atómicos.
Decimal/EUR, total contextual del EE verificado, amount=None, snapshot real.
No nueva lógica grande en db.py ni autoridad IA. Migration76 aditiva protegida;
tuplas explícitas A/B/history. No provider I/O, activación, generation, handoff,
fence release o cambios de cinco flags OFF. Historical v2, observed_state,
mandates y rectificativas negativas bloqueadas por B se conservan.
No routing público ni 1.10D–H. Solo fixtures sintéticos, no producción/QA real/backups.
Revisar callbacks prestados, hashes/request, source revision, FKs/guards,
exact money, SQL adversarial, rollback/recovery, ausencia de provider I/O y snapshots.
La conservación de coverage impide baja destructiva del negocio; no hay nuevo
tratamiento/export/privacy productivo aún. Límites completos en contrato/cierre.

## 2026-10-06 — Fase 1.10B: evidencia mínima por tenant

[Orden](../architecture/FASE-1.10B-orden.md), [ADR020](../architecture/ADR-020-financial-antecedents.md), [contrato](../architecture/FINANCIAL-ANTECEDENTS-v1.md), [cierre](../architecture/FASE-1.10B-cierre.md).

Encabezados inferiores históricos. Antecedentes solo por identidad fuerte y
business; refs/FKs compuestas, actor/sesión actuales, AccessDenied uniforme para
referencia inexistente o ajena. Permisos resolve/read no son financial.authorize,
mandate ni historical_unknown. Guardar refs/hashes/known-unknown, sin duplicar
payload completo ni PII libre. Revalidar cada uso; stale bloquea, SQL inmutable.
SQL privilegiado que deshabilita guards queda fuera del threat model. Aún no
integrado en export de cliente ni rutas: no levantar blockers de privacidad de A.
Sin proveedores/producción/QA real; cinco flags OFF e IA sin autoridad; no C–H.

## 2026-10-05 — Fase 1.10A: evaluación sin activación

[Orden](../architecture/FASE-1.10A-orden.md), [contrato](../architecture/FINANCIAL-READINESS-v1.md), [ADR019](../architecture/ADR-019-financial-readiness.md), [cierre](../architecture/FASE-1.10A-cierre.md), [plan](../architecture/FASE-1.10-plan.md).

Readiness revalida usuario activo/sesión/suscripción y permiso específico
financial.readiness.evaluate; no concede autoridad financiera ni activación.
Evidencia sin PII literal: huellas de configuración/fuentes, referencias y razones
cerradas. Tenant en cada SELECT/write/FK; evaluación propia en read.
Final y capabilities append-only por SQL; baja física bloqueada si existe evidencia,
incluida en inventario de conservación. No ampliar export financiero por un stub:
PRIVACY_NOT_READY/EXPORT_NOT_READY bloquean comandos hasta E futura.
Datos reales QA no se consultan ni destruyen. Política formal QA/export/retención
productiva permanece pendiente; hashes no son firmas ni cifrado. Sin provider I/O.

## 2026-10-05 — Fase1.9E: reconciliación histórica implementada y validada

[Orden](../architecture/FASE-1.9E-orden.md), [ADR018](../architecture/ADR-018-financial-history-reconciliation.md),
[contrato](../architecture/FINANCIAL-HISTORY-RECONCILIATION-v1.md), [informe](../architecture/FASE-1.9E-cierre.md).
Solo audita por identidad; writes exclusivamente run/findings propios. TX/gate y
conexión compartidos, repositorio especializado, Decimal/NUMERIC, IA sin autoridad.
B/C/D siguen inmutables; unknown/B/NULL conservados. PASS no libera fence, activa
flags ni acredita producción. Cinco flags OFF. Sin1.9F ni activación. Validación
local y CI final PASS; cierre técnico1.9E registrado. Encabezados inferiores históricos.


## 2026-10-05 — Fase1.9D: importer histórico (implementada y validada)

Solo incorporación de candidatos congelados de C vigente. Flags OFF; no1.9E,
reconciliación, activación, continuidad live ni producción.
[Orden](../architecture/FASE-1.9D-orden.md), [ADR017](../architecture/ADR-017-financial-history-import.md),
[contrato](../architecture/FINANCIAL-HISTORY-IMPORT-v1.md), [cierre](../architecture/FASE-1.9D-cierre.md).
Monolito modular; importer/repositorio especializados sobre conexión y TX
compartidas. Decimal/NUMERIC y JSON decimal string; IA sin autoridad.
Intent item-scoped con UUID/request/candidato exactos; fence permanece activo.
Operación histórica PREPARED y historical_unknown, actor/session NULL; resultado
en import_items, ninguna ejecución ni cobertura live65–67. Tres v2 históricos
durables cerrados; factura histórica v2 bloqueada. Nuevos inventarios reconocen
evidencia histórica existente sin promover B a A ni modificar batches anteriores.
Los encabezados inferiores conservan historia y no amplían autorización.

Retención D: financial_history_import_batches/items se añaden a la guardia de
baja. Con evidencia no se ejecuta cascade/delete ni se retira defensa; solicitud
con conservación según flujo existente. Purga/transición futura sigue fuera de D.


## 2026-10-04 — Fase1.9C: epoch/T0/fence (implementada y validada)

Únicamente corte consistente por negocio, control durable y nuevo sobre de
inventory certificable, siempre eligible_for_import=false. Schema71, flags OFF.
[ADR016](../architecture/ADR-016-financial-history-cutoff.md), [contrato](../architecture/FINANCIAL-HISTORY-CUTOFF-v1.md),
[writers previos](../architecture/FASE-1.9C-writers.md), [cierre](../architecture/FASE-1.9C-cierre.md).
SQL/application guard por tenant y TX prestada; no promoteB ni histórico EE/Operations/
v2/importer/reconciliación/activación.1.9D NO autorizada. Pruebas SQLite/PG sintéticas,
ninguna producción consultada. Invalidated conserva fence, release explícito pierde
boundary; TTL/crash no liberan. Encabezados inferiores conservan historia.


## Inventario diagnóstico1.9B: conservación, sin purga nueva

Las cuatro financial_history_* son evidencia append-only. La baja usa el guard
existente de conservación: con filas diagnósticas devuelve ValueError controlado
antes de borrar el negocio/fuentes/usuarios. Sin filas mantiene la baja anterior.
No se introduce retención legal nueva ni se resuelve exportación/purga1.10; sigue
siendo un gate antes de habilitar uso real. Solo fixtures sintéticos y flags OFF.
[Contrato](../architecture/FINANCIAL-HISTORY-INVENTORY-v1.md), [cierre](../architecture/FASE-1.9B-cierre.md).

## Financial Core — canales capturados

Con el Core activo, los canales financieros pasan por `financial_channels/` y
Capture: identidad de servidor, propuesta congelada, autorización durable antes
de consumir el pending y ejecución idempotente. La IA no autoriza ni recibe
writers/identidades. Con flags OFF permanece legacy no capturado; opt-in explícito
nunca hace fallback. Fuente capturada conserva guards. Recurrentes preparan
borradores sin emitir; CSV se confirma por fila. Documento/OCR no es autoridad.
[Contrato y límites](../architecture/FINANCIAL-CHANNELS-v1.md),
[ADR-012](../architecture/ADR-012-financial-channels.md). Ningún flag activado.


## Orden vigente — exclusivamente Fase1.7

1.1–1.6 aceptadas. SupplierInvoiceCapture/ExpenseCapture conectan solo
supplier_invoice.confirmed/corrected/voided y expense.confirmed/voided v1.
Writers compartidos, autorización durable, cobertura inmutable por revisión,
continuidad antes/después, logical void y guards SQL. Documento/clasificación/
source/EE/resultado comparten commit. Flags OFF; no1.8, históricos ni activación.
Pagada es etiqueta operativa, no supplier payment/AP settlement. No GL/Tax/
OpenItems/reporting nuevo. Legacy no capturado conserva comportamiento.
[Orden](../architecture/FASE-1.7-orden.md), [ADR-011](../architecture/ADR-011-purchasing-capture.md),
[API](../architecture/PURCHASING-CAPTURE-v1.md), [cierre](../architecture/FASE-1.7-cierre.md).
Las secciones inferiores describen entregas históricas; no son la orden vigente.

## Actualización vigente — 1.6

PaymentCapture y BankCapture son servicios internos; [API](../architecture/PAYMENT-BANK-CAPTURE-v1.md)
y [ADR-010](../architecture/ADR-010-payment-bank-capture.md). Reutilizan writers,
conexión y TX compartidas, sin nueva lógica grande en db.py ni autoridad IA.
Cobro = caja; imported = evidencia/Treasury; match = Evidence-only. Captura exige
factura/importación original y cobertura completa. Sin backfill ni canales 1.8.
Flags OFF; las llamadas legacy conservan respuesta y comportamiento financiero.
La confirmación nueva conserva vínculo durable, y un movimiento capturado falla
cerrado si se intenta confirmar por legacy sin sus eventos.
Las nuevas coberturas y bank_payment_links figuran en baja: vacías permiten legacy;
con evidencia bloquean borrado. Retención/exportación/cierre siguen como gates 1.10.
Las secciones inferiores reflejan entregas anteriores.

## Emisión capturada de 1.5

Solo el servicio interno y el adaptador con operación aprobada producen ahora
`invoice.issued`/`invoice.rectified`; los canales externos esperan 1.8 y los flags
siguen apagados. `invoice_economic_coverage` es evidencia inmutable y figura en
el inventario de baja: con evidencia se rechaza la baja destructiva antes de
borrar; sin evidencia se conserva la baja legacy. La exportación, retención y
el cierre con conservación del núcleo siguen pendientes antes de activar los
canales o las cuentas (1.10). Esta entrega no resuelve esos pendientes.
Ver [cierre 1.5](../architecture/FASE-1.5-cierre.md).

Las secciones de infraestructura 1.2 siguientes describen su entrega histórica.

## Evidencia financiera de 1.2

[Operaciones v1](../architecture/FINANCIAL-OPERATIONS-v1.md): dos tablas internas,
sin productores conectados. Autorizaciones guardan UUID/hash/revisión, actor por
ID y permiso/canal/instante; no conversaciones, teléfonos o tokens. Históricos
separan recorded_by de un actor original desconocido, sin autorización ejecutable.
Acceso por negocio, usuario activo, sesión y creador; UUID no concede permiso.
Baja actual funciona con tablas vacías; si contienen operaciones o mandatos,
rechaza con ValueError explícito antes de borrar datos. Retención/exportación y
cierre con conservación siguen pendientes antes de activar productores; no
borrar evidencia durable por rollback automático.

> Financial Core: leer [guía 08](08-financial-core.md) y [ADR](../architecture/README.md).
> Nuevos dominios en repositorios especializados con transacción compartida;
> Decimal/NUMERIC y aprobación validada en servidor. La IA carece de autoridad
> financiera directa. Solo fundamentos: no cambia la operativa de esta guía.

> Léela antes de tocar datos personales, bajas, exportaciones, consentimientos,
> cookies, analítica, permisos, sesiones, proveedores nuevos o registros de
> seguridad. Figura 6 del [mapa visual](../02-tecnico/Mapa-Bynoesis.html).
> No es asesoramiento jurídico; lo legal está en [`05-legal-y-rgpd`](../05-legal-y-rgpd/).

## Qué hace

Bynoesis tiene **dos papeles**. Es **responsable** de sus propias cuentas (titulares,
cuotas, web y formularios) y **encargado** de lo que cada autónomo guarda (sus
clientes, facturas y documentos): ahí el responsable es el autónomo y Bynoesis solo
trata según sus instrucciones. El código protege el dato en todo su recorrido: se
recoge con permiso, se guarda aislado por negocio, se usa primero en el servidor,
solo se comparte con encargados declarados y, al darse de baja, se borra salvo lo
que la ley obliga a conservar.

## Esquema

```text
1 Se recoge ── casilla con versión de textos (LEGAL_DOCUMENT_VERSION) · cookies y
│              Analytics solo tras «Aceptar» · IA externa solo con permiso del negocio
2 Se guarda ── Railway, Ámsterdam · todo con business_id · PBKDF2 · tokens cifrados
│              (secret_box) · documentos validados y, si se configura, antivirus
3 Se usa ───── reglas locales primero · a la IA externa, solo el trozo necesario
4 Se comparte  encargados de RGPD-Matriz-proveedores (Railway, Meta, Brevo, Groq,
│              Anthropic, Stripe, Google…)
5 Derechos ─── registro de solicitudes: acceso, rectificación, supresión, limitación,
│              portabilidad, oposición y baja · exportación por negocio y por cliente
6 Fin ──────── delete_business_cascade si no hay nada protegido; si hay facturas
               emitidas o fichajes → solicitud de baja con conservación legal
De fondo: bitácora de seguridad encadenada · copias verificadas · permisos de soporte
con caducidad · procedimiento de brechas (72 h)
```

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `db.py` | `create_privacy_request`, `list_privacy_requests`, `update_privacy_request`, `export_business_data`, `delete_business_cascade`, `record_security_event`, `create_support_grant`, `revoke_support_grant`, `set_whatsapp_contact_consent` |
| `web/routers/account.py` | `/api/{id}/export`, `/api/{id}/clients/{client_id}/export`, `/b/{id}/account/delete` (pide contraseña y «BORRAR») |
| `web/routers/admin.py` | `/admin/privacidad`: seguimiento de solicitudes, siempre con nota |
| `security_center.py` | `build_security_report()`: el parte de seguridad de `/admin` (copias, accesos, bitácora) |
| `web/auth.py`, `web/deps.py` | Contraseñas PBKDF2, sesiones firmadas, cookie `__Host-` en producción, límites de intentos, guardias por negocio |
| `web/server.py` | CSP por página, `X-Robots-Tag`, hosts permitidos, cabeceras de aislamiento |
| `secret_box.py` | Cifrado de credenciales de terceros con clave derivada de `NOESIS_SECRET` |
| `documents/validation.py`, `documents/malware.py` | Contenido real de archivos y ClamAV opcional antes de guardar |
| `config.py` | `LEGAL_DOCUMENT_VERSION`, `NOESIS_GA_MEASUREMENT_ID`, datos legales publicados |
| `web/static/public-analytics.js` | Aviso de cookies; Google Analytics solo tras aceptar |

## Reglas que no se rompen

1. **Aislamiento por negocio** en ruta y en `db.py` (ver [01](01-vision-general.md)).
   Una fuga entre negocios es el peor fallo posible.
2. **Nada de terceros sin permiso.** Analytics solo tras «Aceptar», revocable desde el
   pie y `/cookies`; la CSP solo abre Google en rutas públicas y nunca en zonas con
   datos de clientes. La IA externa solo si el negocio la activó.
3. **Minimización.** A la IA externa va el fragmento que lo local no resolvió; al
   correo entrante no se le guarda cuerpo, asunto ni remitente; los logs no llevan
   query strings ni contenido personal.
4. **La bitácora de seguridad es append-only y encadenada.** No lleva contenido
   operativo ni datos de contacto. Nada la reescribe.
5. **La baja nunca borra lo que la ley obliga a guardar.** Facturas emitidas y
   fichajes se conservan; se registra una solicitud `account_closure` con
   `retention_required`. La purga automática espera a unos plazos validados por
   abogado.
6. **Cambiar el estado de una solicitud no borra datos** como efecto secundario.
7. **Soporte sin suplantación.** El founder no se concede acceso: lo concede el
   titular, con alcance y caducidad, y queda auditado.
8. **Un proveedor nuevo no recibe datos reales solo porque exista una clave.** Antes:
   finalidad, rol, DPA, región, transferencias, retención y texto público en
   [`RGPD-Matriz-proveedores`](../05-legal-y-rgpd/RGPD-Matriz-proveedores.md).
9. **Los textos legales tienen versión.** Si cambian, sube `LEGAL_DOCUMENT_VERSION`.

## Estado real (28-sep-2026)

- En código y funcionando: aislamiento, registro de solicitudes (esquema 55),
  exportación, baja con conservación, bitácora encadenada, permisos de soporte,
  consentimiento de cookies, copias diarias con simulacro.
- Pendiente fuera del código: firmar el DPA de Railway y archivar el de cada
  proveedor, revisión de un abogado de textos y plazos, copia externa fuera de
  Railway, alerta 24/7 e incidencias de guardia.

## Pruebas que lo cubren

`test_account_deletion`, `test_security_hardening`, `test_security_operations`,
`test_secrets_gate`, `test_release_configuration`, `test_public_marketing`
(consentimiento de Analytics), `test_backend` (aislamiento entre negocios),
`test_backups`.

## Al revisar código de esta zona

- [ ] ¿Una tabla nueva con datos de un negocio está en `delete_business_cascade` y en
      `export_business_data`? La prueba de borrado lo exige para el borrado; la
      exportación hay que comprobarla a mano. Evidencia del núcleo 1.2–1.5:
      financial_operations/authorizations, economic_events/links y
      invoice_economic_coverage tienen baja bloqueada con evidencia;
      exportación/retención/cierre son gates obligatorios antes de activar
      cuentas o canales. No tratar el pendiente como resuelto.
- [ ] ¿Algún dato personal va a un proveedor que no esté en la matriz?
- [ ] ¿Algún log, evento o mensaje de error lleva correos, teléfonos, NIF o contenido?
- [ ] ¿Un script de terceros nuevo carga sin consentimiento o fuera de la CSP?
- [ ] ¿Una acción de soporte o administración queda en `record_security_event`?
- [ ] ¿Algún secreto nuevo se guarda sin cifrar o se imprime?

## Dudas frecuentes

- **¿Por qué no se puede borrar todo al darse de baja?** La normativa fiscal y laboral
  obliga a conservar facturas y fichajes. Se borra lo demás y se registra.
- **¿Dónde están los datos?** Railway, región `europe-west4` (Ámsterdam). Railway
  está certificado en el Marco de Privacidad UE-EE. UU.

## Más detalle

[`RGPD-estado-y-plan`](../05-legal-y-rgpd/RGPD-estado-y-plan.md) ·
[`RGPD-Registro-actividades`](../05-legal-y-rgpd/RGPD-Registro-actividades.md) ·
[`RGPD-Procedimiento-derechos-y-bajas`](../05-legal-y-rgpd/RGPD-Procedimiento-derechos-y-bajas.md) ·
[`RGPD-Procedimiento-brechas`](../05-legal-y-rgpd/RGPD-Procedimiento-brechas.md) ·
[`Seguridad-operativa`](../04-seguridad-y-datos/Seguridad-operativa.md) ·
[`Servidores-y-residencia-de-datos`](../04-seguridad-y-datos/Servidores-y-residencia-de-datos.md)
