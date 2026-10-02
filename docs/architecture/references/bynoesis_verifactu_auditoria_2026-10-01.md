---
title: "Bynoesis - Especificacion de cumplimiento VERI*FACTU"
subtitle: "Auditoria del estado actual, gaps y arquitectura objetivo del SaaS"
author: "Documento interno de producto, ingenieria y cumplimiento"
date: "1 de octubre de 2026"
lang: es-ES
---

# Bynoesis - Especificacion de cumplimiento VERI*FACTU

**Auditoria del estado actual, gaps y arquitectura objetivo del SaaS**  
**Fecha de revision:** 1 de octubre de 2026  
**Repositorio revisado:** `noesisstudio/noesis`, rama `main`  
**Objetivo:** definir todo lo que Bynoesis debe tener para operar como SaaS de facturacion profesional alineado con el RRSIF y con la modalidad VERI*FACTU.

> **Nota de uso.** Este documento es una especificacion tecnica y de producto basada en la normativa, documentacion y FAQs de la AEAT vigentes a la fecha indicada. No sustituye una revision juridico-fiscal profesional antes de firmar la declaracion responsable del productor o activar el servicio en produccion.

---

# 1. Resumen ejecutivo

Bynoesis **no parte de cero**. El repositorio ya contiene una implementacion significativa: generacion de huella SHA-256, encadenamiento, registros de alta y anulacion, XML AEAT, cliente SOAP con mTLS, QR tributario, inmutabilidad de facturas y registros, colas de envio, almacenamiento de respuestas AEAT, CSV y controles de integridad.

Sin embargo, **todavia no debe considerarse un SIF VERI\*FACTU completo para produccion**. La principal diferencia entre el estado actual y un producto comercial defendible ante clientes, gestorias y AEAT no esta en el QR, sino en cuatro bloques:

1. **Gobernanza legal y representacion:** identidad definitiva del productor, declaracion responsable por version, certificado, colaboracion social y representacion valida de los clientes.
2. **Motor fiscal completo:** mas tipos de factura y situaciones tributarias, clientes extranjeros, rectificaciones completas, subsanaciones y tratamiento de rechazos.
3. **Integridad operativa SaaS:** serializacion de la cadena fiscal, cola unificada y ordenada, manejo robusto de concurrencia, reintentos, reconciliacion y observabilidad.
4. **Validacion oficial y release gate:** XSD, portal de pruebas, bateria completa de casos, pruebas de carga/concurrencia, seguridad, recuperacion y documentacion de la version.

La recomendacion de arquitectura para Bynoesis es **operar como SIF de modalidad VERI\*FACTU para los clientes sujetos al RRSIF**, en lugar de mantener un modo dual libremente conmutable. La modalidad VERI*FACTU remite los registros a AEAT de forma continuada y evita parte de las obligaciones adicionales propias de los sistemas no verificables. [S4]

## 1.1. Estado resumido

| Bloque | Estado actual | Accion |
|---|---|---|
| Hash y encadenamiento | Construido | Validar contra especificacion y reforzar concurrencia |
| Registro de alta | Construido | Ampliar campos/casos fiscales |
| Registro de anulacion | Construido | Integrar en secuencia fiscal unica |
| XML AEAT | Construido | Validacion XSD automatica en CI |
| SOAP + mTLS | Construido | Endurecer errores, certificados y secretos |
| QR y leyenda | Construido | QA automatico de factura final |
| Inmutabilidad | Construida | Mantener y probar en PostgreSQL |
| Outbox AEAT | Construida | Unificar, ordenar y redisenar reintentos |
| Respuesta/CSV AEAT | Construido | Parser por lote y reconciliacion |
| Declaracion responsable | Falta | P0 |
| Colaboracion social / representacion | Falta | P0 |
| Subsanaciones / rechazo previo | Falta | P0 |
| Cobertura fiscal amplia | Incompleta | P0 |
| F3 | Falta | P0 |
| IDOtro / extranjero | Falta | P0 |
| Lock de cadena fiscal | Insuficiente | P0 |
| Batch AEAT | Falta | P1 |
| Consulta/reconciliacion AEAT | Falta | P1 |
| Observabilidad fiscal | Parcial | P1 |

---

# 2. Marco normativo y fechas que afectan a Bynoesis

La AEAT identifica dos colectivos afectados: los **productores/comercializadores de SIF** y los empresarios/profesionales usuarios cuando concurren las condiciones del RRSIF. [S2]

Los plazos actualmente publicados son:

- **Contribuyentes del Impuesto sobre Sociedades:** SIF adaptado antes del **1 de enero de 2027**.
- **Resto de obligados del articulo 3.1:** SIF adaptado antes del **1 de julio de 2027**.
- **Productores y comercializadores de SIF:** la FAQ de AEAT indica que debian ofrecer productos totalmente adaptados desde el **29 de julio de 2025**. [S2][S3]

Por tanto, para Bynoesis la obligacion relevante no es solo la fecha del autonomo cliente. Como productor/comercializador del software de facturacion, la conformidad del producto debe tratarse como un requisito de lanzamiento y no como una mejora futura.

La AEAT mantiene un **Portal de Pruebas Externas**, WSDL, esquemas XSD, documentos de validaciones y errores, especificacion de hash, firma, QR y ejemplos de declaracion responsable. [S8]

---

# 3. Estado actual encontrado en el repositorio

La revision se ha centrado principalmente en los siguientes componentes:

- `src/noesis/verifactu.py`
- `src/noesis/verifactu_client.py`
- `src/noesis/db.py`
- `src/noesis/migrations.py`
- `src/noesis/web/scheduler.py`
- `src/noesis/web/invoice_pdf.py`
- `src/noesis/fiscal_validation.py`
- `src/noesis/web/routers/invoicing.py`
- `docs/areas/04-facturas.md`
- `docs/05-legal-y-rgpd/Verifactu-textos-archivados.md`
- `.env.example`
- pruebas de facturacion y backend del directorio `tests/`

## 3.1. Capacidades ya construidas

### A. Registro fiscal y hash

Bynoesis ya implementa:

- cadena de hash por emisor;
- SHA-256 configurable y fijado a la opcion esperada;
- cadena canonica para registros de alta;
- cadena canonica para anulaciones;
- almacenamiento del hash anterior y hash actual;
- comprobacion de integridad antes de generar nuevos registros;
- bloqueo cuando se detecta una anomalia en la cadena;
- proteccion ante retroceso significativo del reloj.

### B. Inmutabilidad

En las migraciones existen protecciones de base de datos para impedir:

- modificar registros fiscales ya creados;
- borrar registros fiscales;
- modificar o borrar facturas emitidas;
- modificar lineas de facturas emitidas;
- insertar registros fiscales sin huella.

Esto es una buena base para cumplir el objetivo de integridad e inalterabilidad exigido a los SIF. [S6]

### C. XML, SOAP y remision

Bynoesis dispone de:

- namespaces AEAT;
- generador `RegFactuSistemaFacturacion`;
- cabecera con obligado a emision;
- bloque `SistemaInformatico`;
- XML de `RegistroAlta`;
- XML de `RegistroAnulacion`;
- sobre SOAP 1.1;
- endpoints de pruebas y produccion;
- rutas diferenciadas para certificado de persona y sello;
- mTLS con certificado y clave privada;
- TLS minimo 1.2;
- limite de tamano de respuesta.

### D. Outbox y estados AEAT

Existe una outbox persistente para remision que guarda:

- estado;
- numero de intentos;
- proximo intento;
- momento de envio;
- momento de finalizacion;
- CSV AEAT;
- estado global AEAT;
- codigo de error;
- descripcion de error;
- respuesta bruta;
- tiempo de espera indicado por AEAT.

Tambien se reconoce `Correcto`, `AceptadoConErrores` e `Incorrecto`, y existe logica para duplicados tras reintentos.

### E. QR y factura PDF

La factura PDF:

- genera el QR a partir de la URL de cotejo;
- lo incluye en la factura si existe registro fiscal;
- muestra la leyenda `VERI*FACTU`;
- conserva el QR de una factura que nacio con registro aunque el negocio cambie de configuracion para futuras facturas.

Las facturas emitidas con un SIF afectado deben incluir QR tributario; en modalidad VERI*FACTU procede tambien la referencia visual correspondiente. [S1][S10]

### F. Series y numeracion

Hay:

- series separadas para facturas, rectificativas y simplificadas;
- numeracion correlativa;
- secuencias persistentes;
- bloqueo de serie en PostgreSQL;
- posibilidad controlada de continuar numeracion de un software anterior;
- trazabilidad del cambio de numero siguiente.

---

# 4. Modelo de funcionamiento recomendado para Bynoesis

## 4.1. Recomendacion: modalidad VERI*FACTU como modo fiscal de produccion

La AEAT admite dos modalidades de SIF: VERI*FACTU y no verificable. En VERI*FACTU los registros se remiten de forma continuada a AEAT; en no verificable deben conservarse localmente con requisitos adicionales de integridad, trazabilidad, accesibilidad y, entre otros aspectos, registro de eventos. [S4][S7]

Para un SaaS como Bynoesis, la arquitectura mas simple de defender es:

**Clientes sujetos al RRSIF -> Bynoesis Fiscal -> VERI\*FACTU -> AEAT**

El producto debe poder distinguir excepciones o ambitos que no deban seguir este flujo, pero un cliente afectado no deberia tener un simple interruptor para pasar libremente de VERI*FACTU a un modo no verificable.

## 4.2. Cambiar la semantica de `verifactu_enabled`

El booleano actual es util para desarrollo, pero no es suficiente para produccion. Debe evolucionar a un estado fiscal explicito, por ejemplo:

```text
rrsif_status              # not_assessed | applicable | excluded | exception
fiscal_mode               # verifactu | external_sii | exempt | sandbox
verifactu_started_at
verifactu_production_at
verifactu_locked_until
representation_status     # pending | valid | expired | revoked
representation_id
representation_version
producer_declaration_version
```

El onboarding debe determinar la modalidad antes de permitir la primera factura definitiva.

---

# 5. Gap P0 - Identidad del productor y declaracion responsable

## 5.1. Identidad definitiva del productor

El repositorio deja vacio `NOESIS_VERIFACTU_PRODUCER_NIF`. Antes de activacion real deben quedar definidos y versionados:

- razon social productora;
- NIF del productor;
- domicilio del productor;
- datos de contacto;
- nombre comercial y nombre del SIF;
- identificador del SIF;
- version;
- identificador de instalacion;
- modalidad de funcionamiento.

## 5.2. Declaracion responsable por version

La certificacion prevista para el SIF se articula mediante **declaracion responsable del productor**. AEAT publica ejemplos y requisitos. [S5][S9]

Bynoesis debe crear un artefacto de cumplimiento por cada release fiscal relevante, por ejemplo:

```text
compliance/verifactu/
  declarations/
    bynoesis-sif-1.0.0.pdf
    bynoesis-sif-1.0.1.pdf
  manifests/
    1.0.0.json
    1.0.1.json
  xsd/
  evidence/
```

Cada declaracion debe identificar como minimo el productor y el sistema/version concreto y afirmar el cumplimiento de la normativa aplicable. [S5][S9]

### Requisito de producto

En `Ajustes > Legal y cumplimiento` debe existir:

- version del SIF instalada;
- identificador del sistema;
- productor;
- enlace/descarga de su declaracion responsable;
- fecha de declaracion;
- hash del documento;
- changelog de la version fiscal.

---

# 6. Gap P0 - Representacion del cliente y colaboracion social

## 6.1. Arquitectura recomendada

Para SaaS, la opcion mas limpia es que Bynoesis remita por cuenta de sus clientes como tercero legitimado, sin pedir que cada cliente entregue permanentemente su clave privada.

La AEAT indica que las empresas desarrolladoras de software pueden suscribir el **acuerdo de colaboracion social Tipo 017** para la remision de registros de facturacion y que deben contactar con `comunicacion.sepri@correo.aeat.es`. [S11]

## 6.2. Representacion

En colaboracion social, la autorizacion no debe reducirse a un checkbox generico. La AEAT contempla modelos normalizados de representacion: [S12]

- **Anexo I:** representacion directa del obligado tributario a la empresa suministradora de software que presta el servicio desde su plataforma.
- **Anexo III:** representacion del profesional tributario a la empresa suministradora de software cuando el profesional presta servicios a sus clientes usando la aplicacion.

## 6.3. Lo que debe guardar Bynoesis

Crear una entidad `tax_representations` con, como minimo:

```text
id
business_id
representation_type       # AEAT_ANNEX_I | AEAT_ANNEX_III | other_valid_basis
principal_name
principal_nif
representative_name
representative_nif
document_version
signed_at
valid_from
valid_until
revoked_at
status
file_storage_key
file_sha256
signature_method
signature_evidence_json
created_at
```

### Regla de bloqueo

Sin representacion valida cuando sea necesaria, **no se activa el envio en produccion**.

## 6.4. Onboarding fiscal

El alta del cliente deberia seguir:

```text
1. Datos fiscales del negocio
2. Evaluacion RRSIF
3. Modalidad aplicable
4. Series y continuidad de numeracion
5. Operaciones fiscales habituales
6. Firma de representacion
7. Validacion de identidad/NIF
8. Activacion fiscal
9. Primera factura de prueba interna
10. Primera factura real
```

---

# 7. Gap P0 - Certificado y custodia de secretos

El cliente SOAP ya soporta certificado y clave PEM. Para produccion, el requisito no es solo que existan rutas de fichero: debe existir un ciclo completo de seguridad.

## 7.1. Requisitos

- certificado cualificado valido para el modelo de representacion adoptado;
- clave privada cifrada;
- almacenamiento en secret manager/KMS o equivalente;
- el certificado no debe entrar en Git ni en imagenes de contenedor;
- minimo privilegio para el proceso fiscal;
- registro de accesos administrativos;
- rotacion;
- alerta de caducidad 60/30/15/7 dias;
- procedimiento de renovacion sin interrumpir envios;
- prueba automatizada de mTLS contra entorno AEAT de pruebas.

## 7.2. Configuracion objetivo

No depender de un path manual fijo como unica estrategia. Crear una abstraccion:

```text
CertificateProvider
  load_current_certificate()
  expires_at()
  fingerprint()
  healthcheck()
```

El transporte Veri*Factu no deberia conocer donde vive realmente el secreto.

---

# 8. Gap P0 - Serializacion de la cadena fiscal y concurrencia

Este es uno de los riesgos tecnicos mas importantes del estado actual.

Hoy se bloquea la factura y la serie, pero la creacion del registro fiscal obtiene el ultimo registro de la cadena sin un bloqueo unico de la cadena por obligado/emisor.

Con dos emisiones simultaneas en series diferentes podria ocurrir conceptualmente:

```text
                  +--> registro A
ultimo hash H ----|
                  +--> registro B
```

Ambos registros habrian usado el mismo `previous_hash`, creando una bifurcacion local.

## 8.1. Solucion recomendada

Crear estado explicito de cabeza de cadena:

```text
fiscal_chain_heads
------------------
business_id
issuer_nif
last_sequence
last_record_kind
last_record_id
last_hash
last_generated_at
updated_at
PRIMARY KEY (business_id, issuer_nif)
```

Antes de cada alta/anulacion/subsanacion:

1. abrir transaccion;
2. adquirir lock por negocio + NIF;
3. leer la cabeza;
4. verificarla;
5. calcular nuevo registro;
6. insertar registro;
7. incrementar `chain_sequence`;
8. actualizar cabeza;
9. commit.

### PostgreSQL

Se puede utilizar:

- fila `SELECT ... FOR UPDATE`, o
- `pg_advisory_xact_lock` derivado de `business_id + issuer_nif`.

### Criterio de aceptacion

Un test con multiples workers emitiendo simultaneamente desde varias series debe producir **una sola cadena lineal**, sin duplicidad de `chain_sequence`, sin bifurcaciones y con validacion completa del hash.

---

# 9. Gap P0 - Unificar el ledger y la cola fiscal

Hoy existen registros de alta y anulacion en tablas/colas separadas. Para garantizar el orden del envio, conviene modelar un **ledger fiscal unico**.

## 9.1. Modelo propuesto

```text
fiscal_records
--------------
id
business_id
issuer_nif
chain_sequence
record_kind               # alta | anulacion | subsanacion
record_payload_json
record_hash
previous_hash
generated_at
immutable_created_at
UNIQUE (business_id, issuer_nif, chain_sequence)

fiscal_submission_queue
-----------------------
id
business_id
fiscal_record_id
chain_sequence
status                    # pending | sending | accepted | accepted_with_errors |
                          # rejected | requires_action
attempts
next_attempt_at
last_transport_error
last_aeat_error_code
last_aeat_error_description
aeat_csv
sent_at
completed_at
```

Se pueden mantener las tablas actuales internamente, pero debe existir una vista/abstraccion que garantice el mismo resultado: **un unico orden fiscal por emisor**.

## 9.2. Orden de envio

Siempre seleccionar por:

```text
business_id + issuer_nif + chain_sequence ASC
```

Nunca priorizar "todas las altas y despues todas las anulaciones" si eso puede alterar el orden de generacion.

---

# 10. Gap P0 - Subsanacion, rechazo previo y estados correctivos

En el repositorio revisado no se ha encontrado implementacion de los conceptos de subsanacion/rechazo previo necesarios para cerrar la operativa real de errores.

## 10.1. Casos que el motor debe resolver

1. **Registro aceptado con error subsanable** -> generar la accion correctiva admitida por el esquema vigente.
2. **Registro rechazado por AEAT** -> corregir datos y generar nuevo registro con las marcas de rechazo previo correspondientes cuando proceda.
3. **Anulacion de registro** -> ya existe base, pero debe contemplar estados anteriores y respuesta AEAT.
4. **Error local detectado antes de remitir** -> bloquear envio y corregir mediante flujo fiscal valido; nunca sobrescribir el registro ya generado si legalmente debe conservarse.
5. **Error de estructura XML/configuracion** -> no entrar en bucle de reintento infinito; pasar a incidente tecnico.

## 10.2. Maquina de estados recomendada

```text
DRAFT
  -> GENERATED
  -> PENDING_SEND
  -> SENDING
      -> ACCEPTED
      -> ACCEPTED_WITH_ERRORS -> REQUIRES_REVIEW -> CORRECTIVE_RECORD
      -> REJECTED -> REQUIRES_ACTION -> CORRECTED_RECORD
      -> TRANSPORT_ERROR -> PENDING_SEND
      -> TECHNICAL_PERMANENT_ERROR -> INCIDENT
```

No se debe editar el registro original para "hacer desaparecer" un rechazo.

---

# 11. Gap P0 - Clasificacion de errores SOAP y AEAT

El cliente actual trata un `SOAP Fault` basicamente como error de transporte/configuracion y lo envia al circuito de reintento.

Debe distinguirse:

## 11.1. Errores temporales

- timeout;
- reset de conexion;
- indisponibilidad de red;
- 5xx temporal;
- limitacion/espera indicada por AEAT.

**Accion:** retry con backoff y sin perder orden.

## 11.2. Errores permanentes de estructura/configuracion

- XML que no valida contra XSD;
- namespace/version incorrecta;
- certificado no valido;
- error de contrato SOAP;
- campos incompatibles con esquema.

**Accion:** `technical_incident`, alerta a ingenieria y bloqueo de la cola afectada hasta corregir.

## 11.3. Rechazo funcional de un registro

**Accion:** almacenar error AEAT, mostrarlo de forma comprensible al usuario/soporte y abrir el flujo de subsanacion/correccion correspondiente.

---

# 12. Gap P0 - Politica de reintentos

La configuracion actual limita los intentos (`NOESIS_VERIFACTU_MAX_ATTEMPTS=6`). Para una obligacion fiscal, un fallo temporal no debe convertirse silenciosamente en un registro abandonado.

## 12.1. Recomendacion

- errores temporales: reintento persistente con backoff y alertas por antiguedad;
- errores funcionales: no reintentar identico de forma ciega;
- errores de integridad: bloqueo y alerta critica;
- errores de certificado: bloqueo global de remision + alerta de operacion;
- ninguna factura debe aparecer como "todo correcto" si su registro fiscal sigue pendiente o fallido.

## 12.2. SLO operativo recomendado

Medir:

```text
oldest_pending_record_seconds
pending_records_total
transport_errors_total
rejected_records_total
accepted_with_errors_total
chain_integrity_failures_total
certificate_days_to_expiry
aead_last_success_at
aeat_last_error_at
```

Alertas sugeridas:

- pendiente > 5 minutos;
- pendiente > 30 minutos;
- pendiente > 2 horas;
- cadena rota: inmediata;
- certificado < 30 dias: alta;
- certificado < 7 dias: critica.

---

# 13. Gap P0 - Motor fiscal: el modelo actual es demasiado estrecho

El XML actual fija de manera practicamente constante:

```text
Impuesto = 01
ClaveRegimen = 01
CalificacionOperacion = S1
```

Eso cubre el caso comun de IVA en regimen general, pero no convierte el producto en un motor fiscal generalista.

## 13.1. El modelo de linea debe evolucionar

Propuesta:

```text
invoice_line_tax
----------------
invoice_line_id
tax_code                   # IVA / IGIC / IPSI / other
tax_regime_key
operation_qualification
exemption_cause
tax_rate
base_amount
tax_amount
equivalence_surcharge_rate
equivalence_surcharge_amount
non_subject_reason
special_metadata_json
```

## 13.2. Casos a soportar o bloquear explicitamente

Bynoesis debe definir una matriz de alcance. Como minimo decidir y testear:

- IVA general 21%;
- IVA reducido 10%;
- IVA superreducido 4%;
- tipo 0 cuando corresponda;
- operaciones exentas;
- operaciones no sujetas;
- inversion del sujeto pasivo;
- recargo de equivalencia;
- operaciones con multiples tipos en una factura;
- clientes extranjeros;
- operaciones intracomunitarias;
- situaciones con IGIC/IPSI si se decide dar servicio en esos territorios;
- otras claves de regimen necesarias por los segmentos objetivo.

**Regla de producto:** un caso fiscal que Bynoesis no soporte debe bloquearse claramente antes de emitir, no improvisar una codificacion por defecto.

---

# 14. Gap P0 - Destinatarios extranjeros e `IDOtro`

El generador actual crea destinatarios principalmente mediante `NIF`. Para clientes/proveedores sin NIF espanol debe existir soporte de identificacion alternativa. La documentacion tecnica AEAT contempla `IDOtro` con pais, tipo de identificacion e identificador. [S13]

## 14.1. Modelo propuesto

```text
clients
  tax_id_kind              # ES_NIF | EU_VAT | PASSPORT | FOREIGN_TAX_ID | OTHER
  tax_id
  tax_country_code
  aeat_id_type
```

El XML elegira entre:

```text
NIF
```

o

```text
IDOtro
  CodigoPais
  IDType
  ID
```

Nunca forzar un VAT ID extranjero a un campo NIF espanol de nueve caracteres.

---

# 15. Gap P0 - Tipos de factura: falta F3

El motor actual admite F1, F2 y R1-R5, pero no se encontro F3.

AEAT define **F3** como factura emitida en sustitucion de facturas simplificadas facturadas y declaradas. Tambien contempla la identificacion de las facturas simplificadas sustituidas. [S14]

## 15.1. Cambios necesarios

- anadir `F3` a enumeraciones;
- crear relacion `substituted_invoice_refs`;
- permitir una F3 asociada a una o varias simplificadas;
- generar el bloque XML correspondiente;
- adaptar series;
- adaptar PDF y UI;
- tests de sustitucion;
- controles para no duplicar la sustitucion.

---

# 16. Gap P0 - Rectificativas completas

Bynoesis ya modela R1-R5 y referencia factura original. Debe completarse la casuistica de:

- rectificativa por diferencias;
- rectificativa por sustitucion;
- varias facturas rectificadas por una sola rectificativa cuando proceda;
- importes de rectificacion requeridos por el esquema/caso;
- fechas de operacion;
- referencia de factura(s) rectificada(s);
- reglas de signo y totales;
- R5 para simplificadas;
- correccion de datos no monetarios.

La UI debe pedir el **motivo fiscal real** y no solo un texto libre.

---

# 17. Gap P0 - Evaluacion RRSIF por cliente

No todos los negocios deben entrar automaticamente por el mismo camino. Bynoesis necesita una evaluacion de aplicabilidad guardada y auditable.

## 17.1. `rrsif_assessments`

```text
id
business_id
assessment_version
assessed_at
assessed_by
country
territory
corporate_taxpayer
sii_status
manual_invoicing_only
other_exclusion_reason
result                     # applicable | not_applicable | review_required
reason_json
```

La evaluacion debe revisarse cuando cambien datos clave del negocio.

---

# 18. Gap P0 - Validacion XSD antes de tocar la red

El XML debe validarse localmente contra los **XSD oficiales versionados** antes de abrir la conexion con AEAT. AEAT publica los esquemas dentro de la informacion tecnica. [S8]

## 18.1. Pipeline recomendado

```text
Domain record
  -> serializer
  -> XML
  -> XSD validation
  -> business rules validation
  -> hash consistency check
  -> enqueue
  -> SOAP transport
```

Si falla XSD:

- no se envia;
- se registra como fallo de software/configuracion;
- se alerta al equipo;
- no consume intentos de transporte.

## 18.2. Versionar esquemas

No descargar XSD de internet en cada factura. Mantener una copia controlada de la version utilizada por cada release y un proceso deliberado para actualizarla.

---

# 19. Gap P1 - Batching y parser de multiples respuestas

El codigo actual llama a `submit_records(business, [record])`, por lo que envia de uno en uno.

El servicio de remision esta preparado para envios agrupados y la documentacion tecnica contempla lotes de registros y respuesta por linea. La implementacion debe soportar batching manteniendo siempre un unico obligado tributario por envio y el orden de cadena. [S15]

## 19.1. Requisitos

- agrupar solo registros compatibles del mismo obligado/emisor;
- respetar el maximo admitido por la especificacion vigente;
- preservar `chain_sequence`;
- mapear cada `RespuestaLinea` al registro exacto;
- permitir resultado parcial del lote;
- guardar CSV/estado global y resultado individual;
- obedecer `TiempoEsperaEnvio`;
- no bloquear innecesariamente otros tenants si la espera es por contexto especifico.

## 19.2. Resultado de dominio

```text
SubmissionBatchResult
  csv
  global_status
  wait_seconds
  records[]
    fiscal_record_id
    aeat_status
    error_code
    error_description
    duplicate_status
```

---

# 20. Gap P1 - Consulta y reconciliacion con AEAT

AEAT ofrece funcionalidad de consulta de registros presentados desde su area de VERI*FACTU. [S16]

Bynoesis debe incorporar una capa de reconciliacion para soporte y auditoria.

## 20.1. Casos de uso

- confirmar si un registro existe tras un timeout ambiguo;
- investigar duplicados;
- auditar discrepancias entre BD y AEAT;
- soporte de cliente;
- comprobaciones programadas de salud.

## 20.2. No usarla como sustituto de la respuesta de envio

La respuesta sincrona de remision sigue siendo la fuente operativa principal. La consulta es una segunda linea de comprobacion.

---

# 21. Gap P1 - Dinero con Decimal de extremo a extremo

El codigo usa `Decimal` en partes criticas, pero el desglose fiscal se serializa en algun punto usando `float`.

Para software fiscal:

- BD: `NUMERIC/DECIMAL`;
- dominio: `Decimal`;
- JSON interno: string decimal canonica cuando sea fiscal;
- XML: conversion directa de `Decimal` a representacion AEAT;
- prohibir `float` en calculos tributarios.

## 21.1. Test obligatorio

Casos con cantidades que producen errores binarios tipicos (`0.1`, `0.2`, descuentos y multiples lineas) deben conservar exactamente el redondeo fiscal previsto.

---

# 22. Gap P1 - Tiempo fiscal y zona horaria

Debe definirse una estrategia explicita de tiempo:

```text
stored_at_utc
generated_at_with_offset
fiscal_timezone
fiscal_date
```

Recomendaciones:

- servidores sincronizados por NTP;
- log de drift si es posible;
- timezone del negocio almacenada;
- timestamps inmutables del registro;
- tests alrededor de medianoche y cambios de horario de verano.

---

# 23. Seguridad y aislamiento multi-tenant

VERI*FACTU convierte el subsistema de facturacion en infraestructura critica de cumplimiento.

## 23.1. Requisitos minimos

- todas las tablas fiscales con `business_id`;
- constraints que impidan referencias entre tenants;
- consultas siempre scopeadas por negocio;
- claves/secretos fuera de BD de aplicacion cuando sea posible;
- RBAC para acciones fiscales;
- MFA para administradores;
- auditoria de acciones administrativas;
- proteccion CSRF y sesiones seguras;
- cifrado en transito;
- backups cifrados;
- restore probado;
- no exponer respuestas AEAT brutas con datos de otros tenants;
- redaccion de datos sensibles en logs.

## 23.2. Permisos de producto

Separar como minimo:

```text
invoice_draft.create
invoice_draft.edit
invoice.issue
invoice.rectify
invoice.cancel_record
verifactu.view_status
verifactu.retry_transport
verifactu.resolve_rejection
verifactu.admin_reconcile
fiscal_settings.manage
representation.manage
```

Una IA/agente no debe saltarse los controles humanos ya existentes para emitir, rectificar o anular.

---

# 24. Datos que Bynoesis debe pedir al cliente

## 24.1. Datos de identidad fiscal

- razon social/nombre fiscal;
- NIF;
- domicilio fiscal;
- pais y territorio fiscal;
- tipo de contribuyente;
- email de contacto fiscal;
- telefono opcional para incidencias.

## 24.2. Aplicabilidad

- sujeto a Impuesto sobre Sociedades o no;
- situacion respecto de SII;
- regimen/territorio;
- excepciones conocidas;
- gestor/profesional tributario, si existe.

## 24.3. Numeracion

- series usadas actualmente;
- ultima factura de cada serie;
- ejercicio;
- si migra desde otro software;
- fecha efectiva de inicio en Bynoesis.

## 24.4. Perfil de operaciones

Checklist seleccionable:

- ventas nacionales B2B;
- ventas nacionales B2C;
- facturas simplificadas;
- facturas a clientes UE;
- facturas a clientes no UE;
- exentas;
- no sujetas;
- inversion sujeto pasivo;
- recargo equivalencia;
- rectificativas;
- operaciones con varios tipos de IVA;
- otras especialidades.

Con estas respuestas Bynoesis puede habilitar solo funciones que realmente soporte y marcar `review_required` cuando el caso quede fuera del alcance.

## 24.5. Representacion

- modelo correspondiente firmado;
- fecha de firma;
- identidad del firmante;
- evidencia de firma;
- version del documento;
- revocaciones.

**No pedir al usuario su clave privada como mecanismo estandar si Bynoesis opera mediante colaboracion social/representacion valida.**

---

# 25. Datos obligatorios internos de cada registro fiscal

La representacion interna debe almacenar de forma inmutable los datos suficientes para regenerar y auditar exactamente el XML enviado.

## 25.1. Identificacion

- version de registro;
- tipo de registro;
- NIF emisor;
- numero/serie;
- fecha de expedicion;
- tipo de factura.

## 25.2. Operacion

- descripcion;
- fecha de operacion cuando aplique;
- destinatario(s);
- identificacion NIF o IDOtro;
- desglose fiscal completo;
- cuota total;
- importe total.

## 25.3. Encadenamiento

- primer registro o registro anterior;
- identificacion del anterior;
- huella anterior;
- algoritmo/tipo de huella;
- huella actual;
- fecha/hora/huso de generacion;
- secuencia interna inmutable.

## 25.4. Sistema informatico

- productor;
- NIF productor;
- nombre del SIF;
- ID del SIF;
- version;
- numero de instalacion;
- indicadores de modalidad/uso.

## 25.5. Evidencia de envio

- XML exacto enviado o representacion reproducible equivalente;
- hash del XML de transporte opcional para auditoria;
- timestamp de envio;
- certificado/fingerprint utilizado;
- endpoint/entorno;
- CSV;
- respuesta AEAT;
- estado individual;
- codigo y descripcion de error.

---

# 26. Matriz minima de tipos de factura

| Tipo | Debe soportarse | Estado observado | Accion |
|---|---:|---|---|
| F1 ordinaria | Si | Si | Ampliar fiscalidad |
| F2 simplificada | Si | Si | Validar todos los casos |
| F3 sustitucion simplificadas | Si | No | Implementar [S14] |
| R1 | Si | Base | Completar |
| R2 | Si | Base | Completar |
| R3 | Si | Base | Completar |
| R4 | Si | Base | Completar |
| R5 | Si | Base | Completar simplificadas |

El alcance comercial puede restringirse inicialmente, pero cualquier tipo no soportado debe estar explicitamente bloqueado y documentado.

---

# 27. Validaciones antes de emitir

Antes de convertir un borrador en factura definitiva:

## 27.1. Identidad

- NIF emisor valido;
- identidad fiscal completa;
- destinatario requerido presente;
- identificacion extranjera correcta cuando aplique.

## 27.2. Numeracion

- serie correcta;
- siguiente numero atomico;
- no duplicado;
- no retroceso;
- fecha coherente con ejercicio/serie.

## 27.3. Importes

- lineas no vacias;
- base por linea;
- descuento;
- impuesto;
- cuota;
- total;
- IRPF cuando corresponda a la factura comercial, sin mezclarlo incorrectamente en el desglose tributario de IVA;
- redondeo determinista.

## 27.4. Fiscalidad

- impuesto y regimen soportados;
- calificacion de operacion;
- exencion/no sujecion cuando aplique;
- claves necesarias presentes;
- rectificacion valida;
- F3 valida si procede.

## 27.5. Cumplimiento operativo

- RRSIF evaluado;
- representacion valida;
- modo fiscal activo;
- version de SIF con declaracion responsable;
- certificado sano;
- cadena fiscal integra;
- XSD local disponible.

Si cualquiera de estos requisitos falla, **la numeracion definitiva no debe consumirse salvo que el flujo legal exija conservar el intento como registro fiscal**.

---

# 28. Flujo objetivo de emision

```text
Usuario/WhatsApp/API
        |
        v
Crear/editar borrador
        |
        v
Validacion comercial + fiscal
        |
        v
Confirmacion humana de emision
        |
        v
BEGIN TRANSACTION
        |
        +-- lock factura
        +-- lock serie
        +-- lock cadena fiscal
        |
        +-- asignar numero
        +-- congelar snapshot fiscal
        +-- construir registro
        +-- calcular hash
        +-- incrementar chain_sequence
        +-- guardar fiscal record
        +-- encolar envio
        |
        v
COMMIT
        |
        +--> generar PDF + QR
        |
        +--> worker AEAT
                |
                +--> XSD validate
                +--> SOAP/mTLS
                +--> resultado individual
                +--> actualizar estado
```

La transaccion debe evitar que exista factura emitida en modo VERI*FACTU sin su registro fiscal asociado.

---

# 29. Flujo objetivo de anulacion

La anulacion fiscal no equivale a borrar una factura.

```text
Solicitud de anulacion
  -> validar motivo y estado
  -> confirmar accion sensible
  -> lock cadena
  -> crear RegistroAnulacion
  -> hash/encadenamiento
  -> encolar
  -> enviar AEAT
  -> conservar factura y registro original
```

La factura original, su alta y la anulacion deben quedar auditables.

---

# 30. Factura PDF y QR

El PDF ya incorpora una buena base. Debe cerrarse con pruebas automaticas y de regresion.

## 30.1. Checklist PDF

- QR existe cuando corresponde;
- QR apunta a URL correcta por entorno;
- datos codificados coinciden con factura;
- leyenda VERI*FACTU cuando corresponde;
- numero, fecha, NIF e importe coinciden con registro fiscal;
- QR legible tras imprimir A4;
- QR no queda cortado;
- PDF no cambia datos despues de emision;
- factura rectificativa identifica su naturaleza;
- F3 tiene informacion comercial correcta.

---

# 31. Backups y recuperacion

Aunque un SIF VERI*FACTU remite los registros a AEAT y la FAQ indica que estos registros ya obran en poder de la Agencia, Bynoesis sigue necesitando backups por continuidad de negocio, facturas, clientes, evidencias de envio, representaciones y datos de aplicacion. [S17]

## 31.1. Restore test obligatorio

Mensualmente, en entorno aislado:

1. restaurar backup;
2. verificar migraciones;
3. ejecutar verificacion de cadenas;
4. comprobar secuencias y series;
5. comparar conteo de registros fiscales;
6. comprobar que ningun registro aceptado vuelve automaticamente a pendiente;
7. comprobar secretos/certificados por referencia, no por copia insegura.

---

# 32. Observabilidad y centro de cumplimiento

Crear en admin un panel `Fiscal / VERI*FACTU`.

## 32.1. Vista global

- certificado actual y caducidad;
- ultimo envio correcto;
- ultimo fallo;
- pendientes;
- rechazados;
- aceptados con errores;
- anomalias de cadena;
- version de SIF activa;
- version de declaracion responsable;
- salud del endpoint AEAT;
- tenants con representacion pendiente/expirada.

## 32.2. Vista por negocio

- modo fiscal;
- aplicabilidad RRSIF;
- representacion;
- primera fecha VERI*FACTU;
- ultima secuencia;
- ultimo hash;
- pendientes;
- errores;
- historial de remisiones;
- reconciliacion.

## 32.3. Alertas internas

Cualquier error fiscal debe ser accionable. Evitar mensajes como "ha fallado" sin codigo, registro, tenant y siguiente accion.

---

# 33. Release management y cambios del SIF

Un SaaS cambia continuamente. El cumplimiento no puede depender de una declaracion estatica olvidada.

## 33.1. Clasificar releases

### Release no fiscal

Ej.: cambio visual que no afecta generacion, registro, hash, seguridad o remision.

### Release fiscal relevante

Ej.:

- cambia XML;
- cambia calculo de hash;
- cambia modelo de impuestos;
- cambia numeracion;
- cambia inmutabilidad;
- cambia transporte;
- cambia sistema/identificador/version declarada;
- cambia funcionamiento VERI*FACTU.

Una release fiscal relevante debe ejecutar un gate de cumplimiento y determinar si exige nueva declaracion responsable/version.

## 33.2. Manifest de cumplimiento

```json
{
  "sif_version": "1.0.0",
  "git_commit": "...",
  "declaration_sha256": "...",
  "aeat_schema_version": "...",
  "hash_spec_version": "...",
  "tests_passed_at": "...",
  "approved_by": ["engineering", "fiscal-review"],
  "production_at": "..."
}
```

---

# 34. Plan completo de pruebas

## 34.1. Unitarias

- normalizacion de importes;
- fechas;
- hash alta;
- hash anulacion;
- QR;
- serializacion XML;
- identificadores;
- redondeos;
- cada tipo de factura;
- cada clase tributaria soportada.

## 34.2. XSD

Todos los fixtures XML deben validar contra el XSD versionado.

## 34.3. Integracion BD

- SQLite solo como soporte local si se mantiene;
- PostgreSQL como objetivo real;
- triggers de inmutabilidad;
- tenant isolation;
- atomicidad;
- rollback;
- migraciones desde versiones anteriores.

## 34.4. Concurrencia

- 2 emisiones simultaneas misma serie;
- 20 emisiones simultaneas misma serie;
- emisiones simultaneas series distintas;
- alta + anulacion simultaneas;
- varios procesos/replicas;
- worker duplicado;
- crash tras generar registro y antes de envio;
- crash tras enviar y antes de guardar respuesta.

## 34.5. Transporte

- certificado incorrecto;
- certificado caducado;
- timeout;
- DNS;
- TLS;
- HTTP error;
- SOAP Fault;
- respuesta truncada;
- respuesta XML invalida;
- duplicado tras timeout.

## 34.6. AEAT pruebas externas

Fixtures reales de:

- F1;
- F2;
- F3;
- R1-R5 segun alcance;
- anulacion;
- destinatario extranjero;
- varios tipos fiscales;
- error subsanable;
- rechazo previo;
- lote;
- control de `TiempoEsperaEnvio`;
- consulta/reconciliacion.

## 34.7. PDF

- render visual;
- QR escaneable;
- factura de 1 pagina;
- factura multipagina;
- textos largos;
- rectificativa;
- simplificada;
- logo/branding.

## 34.8. Recuperacion

- restore de backup;
- verificacion de cadena tras restore;
- worker reiniciado;
- despliegue entre versiones;
- migracion con registros fiscales existentes.

---

# 35. Gate de produccion: no activar hasta que todo P0 este verde

## 35.1. Legal/organizativo

- [ ] Productor juridico definitivo definido.
- [ ] NIF del productor configurado.
- [ ] Domicilio/contacto del productor.
- [ ] Declaracion responsable de la version.
- [ ] Flujo de representacion aprobado.
- [ ] Acuerdo/operativa de colaboracion social definida si se usa esta via.
- [ ] Textos legales revisados por especialista.

## 35.2. Tecnico

- [ ] Modalidad fiscal definitiva.
- [ ] Lock de cadena.
- [ ] `chain_sequence` unico.
- [ ] Cola fiscal ordenada.
- [ ] XSD local.
- [ ] Subsanacion/rechazo previo.
- [ ] F3.
- [ ] IDOtro.
- [ ] Rectificativas completas.
- [ ] Matriz fiscal objetivo.
- [ ] errores SOAP clasificados.
- [ ] politica de reintento sin abandono silencioso.
- [ ] secretos/certificado endurecidos.

## 35.3. QA

- [ ] Suite completa verde en PostgreSQL.
- [ ] concurrencia verde.
- [ ] portal AEAT de pruebas verde.
- [ ] PDF/QR verde.
- [ ] disaster recovery verde.
- [ ] reconciliacion verde.

## 35.4. Operacion

- [ ] dashboard fiscal.
- [ ] alertas.
- [ ] playbooks de incidentes.
- [ ] responsable interno de incidencias fiscales.
- [ ] renovacion de certificado documentada.
- [ ] soporte conoce estados y errores AEAT.

---

# 36. Roadmap recomendado

## Fase 0 - Decisiones y base legal (P0)

1. cerrar entidad productora y NIF;
2. definir VERI*FACTU como modalidad objetivo;
3. iniciar colaboracion social Tipo 017 si se adopta esta via;
4. cerrar modelos Anexo I/III y firma/evidencia;
5. encargar revision fiscal externa de esta especificacion.

## Fase 1 - Integridad de arquitectura (P0)

1. `fiscal_chain_heads`;
2. `chain_sequence`;
3. lock exclusivo por cadena;
4. ledger/cola unica;
5. reintentos y clasificacion de errores;
6. XSD local en CI.

## Fase 2 - Motor fiscal (P0)

1. modelo tributario por linea;
2. IDOtro;
3. F3;
4. rectificativas completas;
5. subsanacion/rechazo previo;
6. validacion de alcance por cliente.

## Fase 3 - AEAT y operacion (P0/P1)

1. certificado seguro;
2. portal de pruebas;
3. batching;
4. parser multi-linea;
5. consulta/reconciliacion;
6. observabilidad y alertas.

## Fase 4 - Certificacion interna y lanzamiento

1. test matrix final;
2. auditoria de codigo;
3. revision fiscal externa;
4. generar declaracion responsable;
5. firmar release manifest;
6. piloto controlado;
7. produccion general.

---

# 37. Backlog tecnico sugerido

## EPIC VF-01 - Fiscal identity and compliance

- VF-001 Producer identity config
- VF-002 Responsible declaration registry
- VF-003 Compliance page in UI
- VF-004 RRSIF assessment
- VF-005 Representation document workflow

## EPIC VF-02 - Chain integrity

- VF-101 Fiscal chain head
- VF-102 Chain sequence
- VF-103 Advisory/row lock
- VF-104 Concurrency tests
- VF-105 Chain repair incident tooling (solo diagnostico, nunca reescritura silenciosa)

## EPIC VF-03 - Fiscal ledger and transport

- VF-201 Unified fiscal ledger
- VF-202 Unified submission queue
- VF-203 Error taxonomy
- VF-204 Persistent retry policy
- VF-205 Batch sender
- VF-206 Multi-line parser
- VF-207 AEAT query/reconciliation

## EPIC VF-04 - Tax model

- VF-301 Tax schema per line
- VF-302 Exempt/non-subject cases
- VF-303 Reverse charge
- VF-304 Equivalence surcharge
- VF-305 Foreign ID / IDOtro
- VF-306 Territory/tax code support

## EPIC VF-05 - Invoice procedures

- VF-401 F3
- VF-402 Complete rectifying workflows
- VF-403 Subsanacion
- VF-404 Rechazo previo
- VF-405 Cancellation edge cases

## EPIC VF-06 - Security and operations

- VF-501 CertificateProvider
- VF-502 Secret manager integration
- VF-503 Expiry alerts
- VF-504 Fiscal dashboard
- VF-505 Incident playbooks
- VF-506 Backup/restore compliance tests

---

# 38. Definicion de "Bynoesis VERI*FACTU completo"

Bynoesis se considerara internamente preparado para comunicar la funcionalidad como disponible cuando, como minimo:

1. cada factura definitiva afectada genera atomicamente su registro fiscal;
2. la cadena no puede bifurcarse bajo concurrencia;
3. el registro es inmutable;
4. el XML valida contra el esquema oficial usado por la release;
5. el envio se realiza con legitimacion/certificado adecuados;
6. las respuestas AEAT se almacenan y se entienden por registro;
7. existen flujos para rechazo, subsanacion, rectificacion y anulacion;
8. el alcance tributario soportado esta explicitamente modelado y testeado;
9. clientes extranjeros se identifican correctamente;
10. F1/F2/F3 y R1-R5 estan cubiertos conforme al alcance comercial;
11. la factura incluye QR/leyenda cuando corresponde;
12. los fallos temporales no provocan perdida silenciosa de registros;
13. existe reconciliacion y soporte operativo;
14. existe declaracion responsable de la version desplegada;
15. el equipo puede demostrar con evidencias que esa version paso el gate de cumplimiento.

---

# 39. Conclusiones

La implementacion actual de Bynoesis ya contiene una parte importante y valiosa de la infraestructura VERI*FACTU. No parece necesario sustituirla por un proveedor externo solo para conseguir una primera integracion. El trabajo pendiente es, sobre todo, **cerrar el producto como sistema fiscal**, ampliar el modelo tributario y elevar la robustez operativa al nivel que requiere un SaaS multiempresa.

Las prioridades absolutas son:

1. **representacion/colaboracion + declaracion responsable**;
2. **serializacion de la cadena fiscal**;
3. **ledger/cola fiscal unificada y fiable**;
4. **subsanaciones y rechazos**;
5. **modelo tributario completo del alcance comercial**;
6. **F3, extranjeros y rectificativas completas**;
7. **XSD + pruebas AEAT + seguridad del certificado**.

Cuando estos puntos esten cerrados y exista evidencia de pruebas externas, Bynoesis podra pasar de tener una "implementacion Veri*Factu preparada" a disponer de un **subsistema de facturacion VERI\*FACTU profesional, auditable y mantenible**.

---

# 40. Fuentes oficiales consultadas

**[S1] AEAT - Sistemas Informaticos de Facturacion (SIF) y VERI\*FACTU**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu.html

**[S2] AEAT - FAQ: ambitos de aplicacion y fechas**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/cuestiones-generales-ambitos-aplicacion.html

**[S3] AEAT - Nota informativa: ampliacion de plazos**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/nota-informativa-ampliacion-plazo-adaptacion-facturacion.html

**[S4] AEAT - FAQ: sistemas VERI\*FACTU y no verificables**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/sistemas-verifactu.html

**[S5] AEAT - FAQ: certificacion y declaracion responsable**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/certificacion-sistemas-informaticos-declaracion-responsable.html

**[S6] AEAT - FAQ: integridad e inalterabilidad**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/caracteristicas-requisitos-sif-integridad-inalterabilidad.html

**[S7] AEAT - FAQ: registro de eventos**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/caracteristicas-requisitos-sif-registro-eventos_.html

**[S8] AEAT - Informacion tecnica / Portal de Pruebas externas / WSDL / XSD**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/informacion-tecnica.html

**[S9] AEAT - Ejemplos de declaraciones responsables**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/informacion-tecnica/ejemplo-declaracion-responsable.html

**[S10] AEAT - FAQ: QR y frase VERI\*FACTU**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/posibilidad-remision-informacion-factura-parte-receptor.html

**[S11] AEAT - FAQ: colaboracion social Tipo 017**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/colaboracion-social.html

**[S12] AEAT - FAQ: cumplimiento, delegacion y modelos de representacion**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/cuestiones-generales-cumplimiento-delegacion.html

**[S13] AEAT - Descripcion de servicios web VERI\*FACTU / IDOtro**  
https://sede.agenciatributaria.gob.es/static_files/AEAT_Desarrolladores/EEDD/IVA/VERI-FACTU/Veri-Factu_Descripcion_SWeb.pdf

**[S14] AEAT - FAQ: procedimientos de facturacion F1/F2/F3/R1-R5**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/procedimientos-facturacion.html

**[S15] AEAT - Descripcion tecnica del servicio web VERI\*FACTU**  
https://sede.agenciatributaria.gob.es/static_files/AEAT_Desarrolladores/EEDD/IVA/VERI-FACTU/Veri-Factu_Descripcion_SWeb.pdf

**[S16] AEAT - Gestiones / consulta de registros de facturacion**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu.html

**[S17] AEAT - FAQ: conservacion, accesibilidad y legibilidad**  
https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/caracteristicas-requisitos-sif-conservacion-accesibilidad-legibilidad.html

---

**Fin del documento.**
