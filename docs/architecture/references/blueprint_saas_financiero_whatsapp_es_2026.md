# BLUEPRINT MAESTRO — SaaS financiero, contable y administrativo controlado por conversación

> **Versión:** 1.0  
> **Fecha de referencia normativa:** 1 de octubre de 2026  
> **Ámbito principal:** España, con arquitectura preparada para Unión Europea  
> **Objetivo:** describir, desde cero y con detalle de producto, contabilidad, fiscalidad, control interno, automatización y arquitectura, cómo construir un SaaS que reduzca al mínimo el trabajo administrativo de autónomos y empresas y permita operar gran parte del negocio desde WhatsApp u otra interfaz conversacional.

---

## 0. La fórmula en una frase

El producto no debe ser un programa de facturación con un chatbot encima. Debe ser un **sistema operativo financiero de la empresa** con una interfaz conversacional.

La fórmula de diseño es:

```text
HECHO ECONÓMICO
    ↓
CAPTURA UNA SOLA VEZ
    ↓
DOCUMENTO + CONTRAPARTE + IMPUESTO + CONTABILIDAD + VENCIMIENTO
    ↓
COBRO/PAGO + BANCO + CONCILIACIÓN
    ↓
LIBROS + IMPUESTOS + TESORERÍA + REPORTING
    ↓
GESTORÍA / CONTROLLER / CFO / DIRECCIÓN
```

La regla fundamental es:

> **Un hecho económico se registra una sola vez y alimenta todos los sistemas posteriores.**

Nunca debe existir una factura en un módulo, una copia manual en contabilidad, otra en Excel para impuestos, otra en tesorería y otra en la gestoría. Todo debe derivarse del mismo registro económico canónico.

---

# PARTE I — PRINCIPIOS NO NEGOCIABLES

## 1. El objetivo real del producto

El objetivo no es que una persona “haga la contabilidad más rápido”. El objetivo es que la mayoría de usuarios **no tengan que hacer contabilidad**.

El usuario debería expresar hechos empresariales:

- “He pagado esta factura.”
- “Factura 2.500 € a este cliente.”
- “Este ticket es una comida con un cliente.”
- “Contratamos a Ana a partir del día 15.”
- “Compra tres ordenadores para el equipo comercial.”
- “¿Cuánto IVA llevo acumulado?”
- “¿Quién me debe dinero?”
- “¿Puedo contratar a dos personas sin quedarme sin caja?”

El sistema debe traducir esas acciones a:

- documentación;
- factura/recibo;
- asiento;
- libro fiscal;
- obligación de cobro/pago;
- movimiento esperado de tesorería;
- conciliación bancaria;
- impacto fiscal;
- reporting financiero;
- control presupuestario;
- trazabilidad;
- datos para gestoría;
- previsiones de caja.

La complejidad contable debe existir, pero debe estar **oculta al usuario que no la necesita**.

---

## 2. Separar tres verdades

El producto debe distinguir tres capas que a menudo se mezclan.

### 2.1. Verdad documental

Qué ocurrió según los documentos:

- factura;
- ticket;
- nómina;
- extracto;
- contrato;
- pedido;
- albarán;
- justificante;
- factura electrónica estructurada.

### 2.2. Verdad contable/fiscal

Cómo debe registrarse legalmente:

- cuenta contable;
- debe/haber;
- IVA;
- retención;
- devengo;
- amortización;
- periodificación;
- cuenta de cliente/proveedor;
- libros registro;
- registro de facturación.

### 2.3. Verdad de gestión

Cómo quiere analizarlo la dirección:

- centro de coste;
- departamento;
- sede;
- producto;
- proyecto;
- comercial;
- unidad de negocio;
- canal;
- campaña;
- cliente;
- contrato;
- cohorte.

Estas tres capas deben enlazarse, pero no confundirse.

---

## 3. Arquitectura de confianza: IA arriba, motor financiero debajo

La inteligencia artificial nunca debe ser el libro mayor.

La arquitectura correcta es:

```text
WhatsApp / Web / App / API
            ↓
Interpretación del lenguaje
            ↓
Motor de intención y contexto
            ↓
POLÍTICAS + PERMISOS + REGLAS
            ↓
Motor financiero determinista
            ↓
Ledger / fiscal / bancos / documentos / auditoría
```

### 3.1. Qué puede decidir la IA

La IA puede:

- interpretar una petición;
- extraer datos de documentos;
- proponer una categoría;
- sugerir una cuenta contable;
- detectar anomalías;
- explicar desviaciones;
- preparar un borrador;
- buscar información dentro de la empresa;
- generar una previsión como apoyo;
- resumir situación financiera;
- formular preguntas cuando falte información.

### 3.2. Qué no debe decidir libremente

La IA no debe inventar:

- tipos de IVA;
- bases imponibles;
- reglas de devengo;
- números de factura;
- saldos;
- asientos descuadrados;
- fechas fiscales;
- identidades de aprobadores;
- IBAN de pago;
- permisos;
- registros VERI*FACTU;
- periodos cerrados.

Todo eso debe estar gobernado por reglas, estados y validadores.

### 3.3. Regla de oro

> **El modelo interpreta; el motor determina; el humano aprueba cuando el riesgo lo exige.**

---

# PARTE II — MODELO EMPRESARIAL Y ONBOARDING

## 4. Crear un “perfil fiscal-contable digital” de cada empresa

Antes de emitir la primera factura, el sistema debe conocer la identidad y obligaciones del cliente.

### 4.1. Datos jurídicos

- nombre o razón social;
- NIF/NIE;
- forma jurídica;
- fecha de inicio;
- domicilio fiscal;
- domicilio social;
- establecimientos;
- administradores;
- representantes;
- certificado/certificados cuando proceda;
- país y territorio fiscal;
- Hacienda estatal o foral cuando corresponda.

### 4.2. Datos de actividad

- actividades económicas;
- epígrafes IAE;
- CNAE;
- actividades principales/secundarias;
- países en los que opera;
- si vende bienes o servicios;
- si tiene stock;
- si trabaja con clientes B2B, B2C o ambos;
- si opera intracomunitariamente;
- si importa/exporta;
- si vende online.

### 4.3. Datos tributarios

- régimen IRPF si persona física;
- Impuesto sobre Sociedades si procede;
- modalidad de estimación;
- régimen de IVA;
- prorrata si aplica;
- recargo de equivalencia si aplica;
- REDEME;
- SII;
- régimen especial de grupo IVA;
- operaciones intracomunitarias;
- retenciones habituales;
- obligaciones periódicas;
- periodicidad mensual/trimestral;
- ejercicio fiscal;
- fecha de cierre.

### 4.4. Datos contables

- PGC general, PGC Pymes u otro marco aplicable;
- año fiscal;
- plan de cuentas;
- cuentas de apertura;
- dimensiones analíticas;
- método de valoración de existencias;
- políticas de amortización;
- reglas de periodificación;
- moneda funcional;
- monedas transaccionales;
- materialidad interna;
- política de cierre.

### 4.5. Datos financieros

- bancos;
- cuentas bancarias;
- tarjetas;
- cajas;
- préstamos;
- pólizas;
- leasing;
- confirming;
- factoring;
- líneas de crédito;
- pasarelas de pago.

### 4.6. Datos organizativos

- empleados;
- departamentos;
- responsables;
- centros de coste;
- proyectos;
- sedes;
- unidades de negocio;
- niveles de aprobación.

### 4.7. Resultado del onboarding

El sistema debe producir un objeto interno:

```yaml
company_profile:
  legal_type: SL
  accounting_framework: PGC_PYMES
  vat_regime: GENERAL
  sii: false
  verifactu_mode: ENABLED
  fiscal_frequency: QUARTERLY
  currency: EUR
  year_end: 12-31
  inventory: false
  payroll: true
  employees: 7
  approvals:
    expense_0_500: MANAGER
    expense_500_5000: FINANCE
    expense_over_5000: CEO
```

A partir de este perfil se activan o desactivan reglas, libros y workflows.

---

# PARTE III — EL MODELO DE DATOS: EL NÚCLEO REAL

## 5. La unidad fundamental debe ser el “Economic Event”

No diseñaría la base de datos alrededor de “facturas”.

La entidad central sería:

```text
EconomicEvent
```

Ejemplos:

- venta;
- compra;
- nómina;
- pago;
- cobro;
- adquisición de activo;
- amortización;
- préstamo;
- interés;
- devolución;
- rectificación;
- impuesto;
- transferencia;
- anticipo;
- ajuste de cierre.

Cada hecho económico puede tener relacionados:

```text
EconomicEvent
 ├── Document
 ├── Counterparty
 ├── TaxTreatment
 ├── JournalEntry
 ├── Receivable/Payable
 ├── Payment
 ├── BankTransaction
 ├── Approval
 ├── FiscalRecord
 ├── Asset
 ├── InventoryMovement
 ├── AnalyticDimensions
 ├── AuditEvent
 └── Attachments
```

### 5.1. Ventaja

Si una factura cambia de estado, no hace falta recrear el mundo entero.

El mismo hecho económico evoluciona:

```text
DRAFT
→ VALIDATED
→ APPROVED
→ ISSUED/RECEIVED
→ ACCOUNTED
→ DUE
→ PARTIALLY_PAID
→ PAID
→ RECONCILED
→ CLOSED
```

---

## 6. Entidades maestras mínimas

### 6.1. Company

Entidad legal que genera contabilidad.

### 6.2. Counterparty

Cliente/proveedor/acreedor/deudor/empleado/Administración.

Debe permitir que una misma contraparte pueda actuar simultáneamente como cliente y proveedor.

Campos importantes:

- identificador interno inmutable;
- NIF/VAT ID;
- razón social;
- nombre comercial;
- país;
- dirección fiscal;
- emails;
- teléfonos;
- IBAN validados;
- condiciones de pago;
- límite de crédito;
- riesgo;
- cuenta contable por defecto;
- impuestos habituales;
- estado de verificación;
- documentos KYC internos si la organización los requiere.

### 6.3. Document

Nunca sobreescribir el original.

Guardar:

- fichero original;
- hash;
- MIME type;
- fecha recepción;
- fuente;
- usuario que lo aportó;
- versión;
- extracción OCR/document AI;
- campos normalizados;
- estado de validación.

### 6.4. JournalEntry

Debe tener:

- empresa;
- número asiento;
- fecha contable;
- fecha de operación;
- periodo;
- origen;
- referencia;
- líneas;
- moneda;
- tipo de cambio;
- usuario/proceso creador;
- estado;
- bloqueo;
- trazabilidad.

Cada asiento debe cumplir:

```text
SUM(DEBE) = SUM(HABER)
```

sin excepción.

### 6.5. JournalLine

- cuenta;
- debe;
- haber;
- moneda transaccional;
- dimensión analítica;
- contraparte;
- factura;
- vencimiento;
- impuesto;
- proyecto;
- centro de coste.

### 6.6. TaxLine

Separar el tratamiento fiscal de la línea contable.

Campos:

- impuesto;
- jurisdicción;
- tipo;
- base;
- cuota;
- deducibilidad;
- exención;
- inversión sujeto pasivo;
- prorrata;
- clave libro fiscal;
- periodo declaración.

### 6.7. OpenItem

Una deuda pendiente de cliente/proveedor.

- origen;
- importe original;
- pendiente;
- vencimiento;
- estado;
- cobros/pagos aplicados;
- disputa;
- recordatorios.

---

# PARTE IV — MOTOR CONTABLE

## 7. Principio de partida doble

Toda operación contable debe registrarse mediante una o varias líneas cuyo debe y haber cuadren.

Ejemplo: factura de venta de 1.000 € + 21 % IVA.

```text
Debe
430 Clientes                         1.210

Haber
705 Prestaciones de servicios       1.000
477 HP IVA repercutido                 210
```

Cobro:

```text
Debe
572 Bancos                           1.210

Haber
430 Clientes                         1.210
```

Nunca convertiría estos ejemplos en reglas universales sin contexto: la cuenta concreta, el tipo impositivo y tratamiento fiscal dependen de la operación y de la empresa.

---

## 8. Plan General de Contabilidad como modelo canónico en España

El PGC español se estructura en grupos. El software debe soportar la codificación legal y permitir ampliaciones internas.

### Grupo 1 — Financiación básica

Ejemplos de familias:

- 100 Capital social;
- 11 Reservas;
- 12 Resultados pendientes;
- 129 Resultado del ejercicio;
- 13 Subvenciones/donaciones/ajustes en patrimonio;
- 14 Provisiones;
- 16 Deudas a largo plazo con partes vinculadas;
- 17 Deudas a largo plazo;
- 18 Pasivos por fianzas/garantías a largo plazo.

### Grupo 2 — Activo no corriente

- 20 Inmovilizado intangible;
- 21 Inmovilizado material;
- 22 Inversiones inmobiliarias;
- 23 Inmovilizado en curso;
- 24/25 Inversiones financieras;
- 28 Amortización acumulada;
- 29 Deterioros.

### Grupo 3 — Existencias

- 30 Comerciales;
- 31 materias primas;
- 32 otros aprovisionamientos;
- 33 productos en curso;
- 34 productos semiterminados;
- 35 productos terminados;
- 36 subproductos/residuos;
- 39 deterioros.

### Grupo 4 — Acreedores/deudores por operaciones comerciales

- 40 Proveedores;
- 41 Acreedores diversos;
- 43 Clientes;
- 44 Deudores;
- 46 Personal;
- 47 Administraciones públicas;
- 48 Ajustes por periodificación;
- 49 Deterioros/provisiones de operaciones comerciales.

### Grupo 5 — Cuentas financieras

- financiación a corto plazo;
- inversiones financieras a corto;
- caja;
- bancos;
- transferencias internas;
- partidas pendientes.

### Grupo 6 — Compras y gastos

- compras;
- variaciones de existencias;
- servicios exteriores;
- tributos;
- gastos de personal;
- otros gastos de gestión;
- gastos financieros;
- pérdidas/deterioros;
- amortizaciones.

### Grupo 7 — Ventas e ingresos

- ventas;
- prestaciones de servicios;
- variaciones de existencias;
- subvenciones;
- otros ingresos de gestión;
- ingresos financieros;
- reversiones/excesos cuando proceda.

### Grupos 8 y 9

Gastos e ingresos imputados directamente al patrimonio neto cuando proceda bajo el PGC general.

---

## 9. No usar el plan contable para resolver reporting de gestión

Una empresa mediana/grande no debe multiplicar cuentas únicamente para saber “dónde” o “quién” ha gastado.

Mala arquitectura:

```text
6290001 Teléfono Madrid
6290002 Teléfono Barcelona
6290003 Teléfono Lleida
6290004 Teléfono Ventas Madrid
6290005 Teléfono Ventas Barcelona
...
```

Arquitectura correcta:

```text
Cuenta: 629 Comunicaciones
Centro de coste: Ventas
Sede: Barcelona
Proyecto: Alpha
Departamento: Comercial
Responsable: Ana
Unidad de negocio: España B2B
```

### 9.1. Dimensiones recomendadas

- sociedad;
- unidad de negocio;
- centro de coste;
- centro de beneficio;
- departamento;
- sede;
- proyecto;
- cliente;
- proveedor;
- producto;
- servicio;
- canal;
- comercial;
- campaña;
- contrato;
- empleado;
- vehículo;
- activo;
- región.

No todas deben ser obligatorias. Cada cuenta puede definir dimensiones obligatorias.

Ejemplo:

```yaml
account_627_publicidad:
  mandatory_dimensions:
    - business_unit
    - channel
  optional_dimensions:
    - campaign
    - product
```

---

## 10. Subledgers

No depender únicamente de subcuentas contables para gestionar clientes, proveedores y activos.

El sistema debe tener auxiliares detallados:

- accounts receivable;
- accounts payable;
- fixed assets;
- inventory;
- payroll;
- loans;
- taxes.

El mayor contable recibe el total y el subledger conserva el detalle operativo.

Control:

```text
Saldo subledger clientes = saldo cuentas de clientes en mayor
Saldo subledger proveedores = saldo cuentas de proveedores en mayor
Saldo activos = saldo inmovilizado - amortización - deterioro
```

La conciliación de auxiliares debe ejecutarse automáticamente en cada cierre.

---

# PARTE V — CATÁLOGO CONTABLE PRÁCTICO

## 11. Cuentas maestras recomendadas

No se trata de imponer exactamente estas subcuentas a todas las empresas, sino de contar con plantillas profesionales que se adapten durante el onboarding.

### 11.1. Patrimonio

- capital;
- prima de emisión;
- reservas legales/voluntarias;
- aportaciones socios;
- resultados de ejercicios anteriores;
- resultado ejercicio;
- dividendos pendientes;
- subvenciones de capital.

### 11.2. Deuda

Separar:

- largo/corto plazo;
- entidad bancaria;
- préstamo concreto;
- principal;
- intereses devengados;
- comisiones;
- vencimientos.

Cada préstamo debe tener un **schedule financiero** con:

```text
Fecha | cuota | principal | interés | saldo pendiente
```

El asiento puede generarse automáticamente cada mes.

### 11.3. Activos fijos

Clases:

- aplicaciones/software;
- propiedad industrial;
- terrenos;
- edificios;
- instalaciones;
- maquinaria;
- mobiliario;
- equipos informáticos;
- vehículos;
- otros.

Cada activo tendrá ficha individual.

### 11.4. Clientes

No crear manualmente una subcuenta arbitraria cada vez.

Usar identificador interno de cliente + mapping de cuenta contable.

Estados:

- normal;
- dudoso cobro;
- judicializado;
- incobrable;
- bloqueado comercialmente.

### 11.5. Proveedores

Separar proveedores comerciales de acreedores por servicios cuando proceda según política contable.

Mantener:

- condiciones de pago;
- cuenta bancaria;
- historial de cambios;
- incidencias;
- documentos;
- retenciones aplicables.

### 11.6. Administración

Crear cuentas configuradas para:

- IVA soportado;
- IVA repercutido;
- retenciones practicadas;
- retenciones soportadas/pagos a cuenta;
- Hacienda acreedora/deudora por distintos conceptos;
- Seguridad Social;
- impuestos corrientes/diferidos cuando proceda.

### 11.7. Tesorería

Una cuenta auxiliar por:

- IBAN;
- tarjeta;
- caja;
- cuenta de pasarela de pago;
- wallet corporativa cuando proceda.

No mezclar varias cuentas reales en una sola conciliación.

### 11.8. Gastos

Catálogo base de categorías traducidas a cuentas:

- mercaderías;
- materias primas;
- arrendamientos;
- reparaciones;
- profesionales;
- transporte;
- seguros;
- servicios bancarios;
- publicidad;
- suministros;
- telecomunicaciones;
- software/SaaS;
- viajes;
- dietas;
- salarios;
- Seguridad Social;
- formación;
- tributos;
- intereses;
- amortizaciones;
- deterioros;
- otros.

### 11.9. Ingresos

No usar una sola cuenta “ventas”. Separar, cuando aporte valor:

- venta de productos;
- prestación de servicios;
- ingresos recurrentes;
- setup/implantación;
- mantenimiento;
- licencias;
- comisiones;
- alquileres;
- ingresos accesorios;
- ingresos financieros.

Y utilizar dimensiones para granularidad adicional.

---

# PARTE VI — FACTURACIÓN / ORDER-TO-CASH

## 12. Flujo comercial completo

```text
Lead
→ Cliente
→ Presupuesto
→ Aceptación
→ Pedido
→ Entrega / prestación
→ Albarán / evidencia
→ Factura
→ Vencimiento
→ Cobro
→ Conciliación
→ Cierre
```

No todas las empresas usarán todas las fases; el workflow se configura.

---

## 13. Crear una factura desde WhatsApp

Ejemplo:

> “Factura a Construcciones Norte 2.500 más IVA por instalación eléctrica, a 30 días.”

### 13.1. Interpretación

El sistema obtiene:

```yaml
intent: CREATE_SALES_INVOICE
customer: Construcciones Norte
amount_net: 2500
vat: AUTO
concept: Instalación eléctrica
terms: NET_30
```

### 13.2. Enriquecimiento determinista

El backend consulta:

- ficha cliente;
- NIF;
- domicilio;
- país;
- tratamiento IVA;
- serie aplicable;
- numeración siguiente;
- fecha;
- condiciones de pago;
- retención si procede;
- reglas B2B/B2C;
- requisitos de factura electrónica.

### 13.3. Confirmación

El chatbot debe devolver un resumen estructurado antes de una acción irreversible.

```text
Cliente: Construcciones Norte SL
Base: 2.500,00 €
IVA 21 %: 525,00 €
Total: 3.025,00 €
Vencimiento: 31/10/2026
Serie: F2026
Acción: emitir factura
```

### 13.4. Ejecución

Tras aprobación:

1. reservar número;
2. generar factura;
3. registrar fiscalmente;
4. generar estructura electrónica si aplica;
5. generar representación PDF;
6. crear asiento;
7. crear cuenta a cobrar;
8. programar vencimiento;
9. enviar al canal definido;
10. registrar trazabilidad;
11. actualizar forecast de tesorería.

---

## 14. Estados de factura

Separar estado documental de estado de cobro.

### Documental

- draft;
- validated;
- issued;
- delivered;
- accepted;
- rejected;
- rectified;
- cancelled mediante mecanismos permitidos;
- archived.

### Financiero

- not_due;
- due;
- partially_paid;
- paid;
- disputed;
- overdue;
- written_off.

### Fiscal/técnico

- record_pending;
- record_sent;
- accepted_by_tax_authority;
- accepted_with_warnings;
- rejected_by_tax_authority;
- retry_pending.

Nunca usar un solo booleano `paid=true/false`.

---

## 15. Facturas rectificativas

No permitir editar silenciosamente una factura emitida.

Workflow:

```text
Factura original
→ solicitud de corrección
→ motivo
→ documento rectificativo
→ enlace bidireccional
→ registro fiscal correspondiente
→ asiento corrector
→ ajuste cuenta cliente/proveedor
```

Conservar siempre ambas versiones.

---

## 16. Facturación recurrente

Plantilla:

- cliente;
- periodicidad;
- concepto;
- precio;
- impuestos;
- fecha inicio;
- fecha fin;
- regla de actualización;
- medio de cobro;
- aprobación previa sí/no.

Cada periodo crea una factura independiente y trazable.

---

# PARTE VII — VERI*FACTU Y SISTEMAS INFORMÁTICOS DE FACTURACIÓN

## 17. Diseñar VERI*FACTU como parte del núcleo

No debe añadirse al final del proyecto.

En España, el Reglamento de Sistemas Informáticos de Facturación y su desarrollo técnico exigen características de integridad, conservación, accesibilidad, legibilidad, trazabilidad e inalterabilidad de los registros. La Orden HAC/1177/2024 concreta, entre otros aspectos, registros, huellas/hash y remisión XML.

### 17.1. Fechas vigentes a 01/10/2026

Según la AEAT:

- contribuyentes sujetos al Impuesto sobre Sociedades: sistemas adaptados antes del **1 de enero de 2027**;
- resto de obligados dentro del ámbito: antes del **1 de julio de 2027**.

Estas fechas deben parametrizarse en configuración normativa y no enterrarse en código.

### 17.2. Entidades técnicas internas

```text
FiscalInvoiceRecord
FiscalCancellationRecord
FiscalChain
FiscalSubmission
FiscalResponse
SoftwareDeclaration
```

### 17.3. Hash

La Orden HAC/1177/2024 define datos de la huella del registro, incluyendo, según el tipo de registro, datos como NIF emisor, serie/número, fecha, tipo, cuotas/importes, huella anterior y fecha/hora/huso de generación.

No crear un “hash propio parecido”. Implementar exactamente la especificación oficial vigente.

### 17.4. Cadena por obligado tributario

En un SaaS multiempresa:

```text
Company A → cadena A
Company B → cadena B
Company C → cadena C
```

Nunca mezclar cadenas fiscales de distintos obligados.

### 17.5. Remisión

Diseñar:

- cola de salida;
- idempotencia;
- reintentos;
- backoff;
- control de flujo;
- persistencia del payload enviado;
- persistencia exacta de la respuesta;
- monitor de errores;
- reconciliación entre registros locales y enviados.

### 17.6. QR y representación

La factura deberá generar la representación exigida por la normativa que sea aplicable en cada momento y modalidad, incluyendo QR cuando corresponda.

### 17.7. Declaración responsable

El productor/comercializador del SIF debe gestionar la declaración responsable requerida por el marco normativo. El producto debe mantener versionado:

- versión de software;
- identificador;
- declaración asociada;
- fecha;
- release;
- cambios relevantes.

### 17.8. Regla de release

Ninguna versión que afecte facturación se despliega a producción sin:

1. test unitarios fiscales;
2. test de esquema;
3. test de hash;
4. test de encadenamiento;
5. test de XML;
6. test contra entorno de pruebas AEAT cuando proceda;
7. test de regresión de numeración;
8. test de anulación/rectificación;
9. revisión de declaración responsable.

---

# PARTE VIII — FACTURA ELECTRÓNICA B2B ESPAÑA

## 18. Construir factura estructurada, no PDF

El PDF debe ser una representación visual, no la fuente de verdad.

Modelo interno:

```text
Invoice canonical model
      ├── UBL
      ├── CII
      ├── Facturae
      ├── EDIFACT
      └── PDF/render
```

El Real Decreto 238/2026 establece un sistema basado en factura electrónica estructurada y contempla sintaxis como CII, UBL, EDIFACT y Facturae, con el modelo semántico EN16931.

### 18.1. Aplicación efectiva

A 01/10/2026, el Real Decreto 238/2026 ya está publicado, pero su aplicación efectiva se difiere respecto de las obligaciones principales hasta la entrada en vigor de la orden ministerial técnica de la solución pública.

Desde la entrada en vigor de dicha orden:

- 12 meses para empresarios/profesionales que hayan superado 8 M€ de volumen de operaciones en el año anterior;
- 24 meses para el resto, según el reglamento.

Por ello el SaaS debe estar preparado ahora, pero el calendario de obligación debe ser **configurable y revisado automáticamente contra normativa vigente**.

### 18.2. Punto de entrada

Diseñar la entidad:

```text
EInvoiceEndpoint
```

con:

- empresa;
- tipo plataforma;
- identificador;
- endpoint;
- credenciales/referencia segura;
- sintaxis;
- fecha de vigencia.

### 18.3. Estados

El sistema debe modelar explícitamente:

- emitida;
- recibida;
- rechazada;
- pagada completamente;
- fecha efectiva de pago;
- vencimiento;
- otras comunicaciones admitidas.

### 18.4. Repositorio universal y copia UBL

El RD 238/2026 prevé la solución pública gestionada por la AEAT y exige, para sistemas que no emitan mediante la solución pública, remisión simultánea de una copia fiel en UBL cuando la obligación produzca efectos.

Por ello se necesita un conector específico y no un simple “botón exportar XML”.

---

# PARTE IX — COMPRAS / PROCURE-TO-PAY

## 19. Flujo profesional de compra

Para un autónomo puede comenzar directamente con una factura. Para una empresa mediana/grande:

```text
Necesidad
→ solicitud de compra
→ aprobación
→ proveedor
→ pedido de compra
→ recepción del bien/servicio
→ factura proveedor
→ matching
→ contabilización
→ vencimiento
→ propuesta de pago
→ aprobación
→ pago
→ conciliación
```

---

## 20. Three-way matching

Comparar:

1. Purchase Order;
2. Goods Receipt / Service Confirmation;
3. Supplier Invoice.

Reglas:

```text
cantidad factura <= cantidad recibida
precio factura ≈ precio pedido
total dentro tolerancia
proveedor coincide
referencias coinciden
impuestos plausibles
```

Tolerancias configurables:

```yaml
matching:
  amount_tolerance_eur: 2.00
  percent_tolerance: 1.0
  quantity_tolerance: 0
```

Si pasa:

> contabilización automática.

Si falla:

> excepción a responsable.

---

## 21. Factura recibida por WhatsApp

Usuario envía PDF/foto.

Pipeline:

```text
UPLOAD
→ malware scan
→ hash
→ clasificación documental
→ extracción
→ identificación proveedor
→ detección duplicado
→ validación fiscal
→ asignación contable
→ dimensiones
→ workflow aprobación
→ contabilización
→ vencimiento
→ pago
```

### 21.1. Detección de duplicados

Score usando:

- NIF proveedor;
- número factura;
- fecha;
- base;
- IVA;
- total;
- hash fichero;
- similitud documento;
- IBAN;
- patrón histórico.

Ejemplo:

```text
NIF igual       +30
Número igual    +40
Total igual     +15
Fecha igual     +10
Hash igual      +100
```

Por encima de umbral: bloquear hasta revisión.

---

# PARTE X — GASTOS DE EMPLEADOS

## 22. Flujo

Empleado:

> “Gasto taxi 34,20 € visita Cliente Norte.”

Adjunta ticket.

Sistema:

1. identifica empleado;
2. extrae ticket;
3. clasifica gasto;
4. pregunta por cliente/proyecto si falta;
5. evalúa política interna;
6. calcula tratamiento fiscal según reglas;
7. solicita aprobación;
8. crea deuda con empleado o reconcilia tarjeta corporativa;
9. contabiliza;
10. conserva justificante.

### 22.1. Política de gasto

Ejemplo:

```yaml
travel:
  taxi:
    max_without_manager: 75
  hotel:
    nightly_limit: 180
  meals:
    requires_business_purpose: true
    requires_attendees: true
```

La política empresarial y la deducibilidad fiscal son cosas diferentes. El sistema debe tratarlas separadamente.

---

# PARTE XI — BANCA Y CONCILIACIÓN

## 23. Banco como fuente operacional crítica

Integrar mediante proveedores autorizados/open banking cuando corresponda, o mediante extractos normalizados cuando no exista conexión.

Nunca almacenar credenciales bancarias de forma insegura.

Entidades:

```text
BankAccount
BankConnection
BankTransaction
ReconciliationMatch
PaymentInstruction
```

---

## 24. Motor de conciliación

Cada movimiento obtiene candidatos.

### Señales

- importe exacto;
- importe aproximado;
- referencia;
- factura;
- nombre contraparte;
- IBAN;
- fecha;
- vencimiento;
- patrón histórico;
- concepto;
- remesa.

### Score

```text
confidence =
  amount_match * weight
+ counterparty_match * weight
+ reference_match * weight
+ date_proximity * weight
+ historical_pattern * weight
```

### Política

- ≥99 % y regla segura: auto-conciliar;
- 90–99 %: propuesta;
- <90 %: revisión;
- conflicto: bloquear.

Los umbrales no deben ser universales; deben calibrarse según riesgo y empresa.

---

## 25. Pagos

Separar:

```text
APPROVED_FOR_PAYMENT
```

de

```text
PAYMENT_EXECUTED
```

Un documento aprobado contablemente no significa que deba pagarse inmediatamente.

### 25.1. Payment run

El usuario:

> “Prepara pagos de esta semana.”

Sistema agrupa:

- facturas vencidas;
- facturas próximas;
- descuentos pronto pago;
- prioridades;
- caja mínima;
- proveedores bloqueados;
- incidencias.

Genera propuesta, no necesariamente ejecución.

---

# PARTE XII — ACCOUNTS RECEIVABLE

## 26. Cobros

Para cada factura:

- fecha emisión;
- vencimiento;
- importe;
- pendiente;
- días vencidos;
- promesa de pago;
- disputa;
- responsable comercial;
- último contacto.

### 26.1. Aging

Buckets:

```text
No vencido
0–30
31–60
61–90
>90
```

### 26.2. DSO

Fórmula simple de seguimiento:

```text
DSO = Clientes pendientes / Ventas a crédito del periodo × días del periodo
```

Debe documentarse la variante utilizada para evitar comparar métricas calculadas con métodos distintos.

### 26.3. Automatización de reclamaciones

Secuencia configurable:

```text
-5 días: recordatorio amistoso
0: vencimiento
+7: recordatorio
+15: responsable comercial
+30: finanzas
+60: escalado
```

No automatizar mensajes sensibles sin política específica.

---

# PARTE XIII — ACCOUNTS PAYABLE

## 27. Proveedores

KPIs:

- total pendiente;
- vencido;
- próximos 7/30/60 días;
- descuentos perdidos;
- DPO;
- concentración proveedores;
- facturas en disputa;
- facturas sin pedido;
- pagos bloqueados.

### DPO

```text
DPO = Proveedores medios / Compras a crédito × días
```

Usar consistencia temporal y metodología documentada.

---

# PARTE XIV — TESORERÍA

## 28. No confundir beneficio con caja

El SaaS debe enseñar explícitamente:

```text
Beneficio ≠ saldo bancario
```

Una venta puede generar beneficio y no haber sido cobrada.

Una compra de activo puede reducir caja sin ser gasto completo del periodo.

Un préstamo aumenta caja pero no es ingreso.

---

## 29. Cash position

Vista diaria:

```text
Banco A
Banco B
Banco C
Caja
Pasarela
- saldos restringidos
= liquidez disponible
```

---

## 30. Forecast de tesorería

Tres horizontes:

### Diario — 30 días

Para pagos inmediatos.

### Semanal — 13 semanas

Herramienta central para CFO/tesorería.

### Mensual — 12/24 meses

Para planificación estratégica.

### 30.1. Fórmula

```text
Caja final(t) =
Caja inicial(t)
+ cobros previstos(t)
+ financiación(t)
- proveedores(t)
- personal(t)
- impuestos(t)
- deuda(t)
- capex(t)
- otros pagos(t)
```

### 30.2. Capas de certeza

Cada flujo:

- confirmado;
- altamente probable;
- forecast base;
- scenario.

No mezclar todos como si fueran iguales.

---

# PARTE XV — ACTIVOS FIJOS

## 31. Ficha de activo

Campos:

- ID activo;
- categoría;
- descripción;
- proveedor;
- factura;
- fecha adquisición;
- fecha puesta en funcionamiento;
- coste;
- valor residual;
- vida útil;
- método;
- cuenta activo;
- cuenta amortización acumulada;
- cuenta gasto;
- centro coste;
- ubicación;
- responsable;
- serie;
- estado;
- fecha baja.

### 31.1. Automatización

Cada cierre:

```text
activos activos
→ calcular cuota
→ generar propuesta de amortización
→ contabilizar
→ actualizar valor neto
```

La política de vida útil debe ser configurable y validada contablemente; no deducirla únicamente de una predicción de IA.

---

# PARTE XVI — INVENTARIO

## 32. Si el cliente tiene stock, el producto cambia de nivel

Entidades:

- SKU;
- almacén;
- ubicación;
- lote;
- serie;
- movimiento;
- coste;
- reserva;
- inventario físico;
- ajuste.

Flujo:

```text
Compra
→ recepción
→ inventario
→ coste
→ venta
→ salida
→ coste de ventas
```

### 32.1. Controles

- stock negativo configurable/bloqueable;
- inventarios físicos;
- diferencias;
- trazabilidad;
- stock obsoleto;
- deterioro;
- rotación.

### 32.2. DIO

```text
DIO = Inventario medio / Coste de ventas × días
```

---

# PARTE XVII — PERSONAL Y NÓMINA

## 33. Integrar, no necesariamente reinventar nómina

Para comenzar, el SaaS puede integrar un sistema laboral/nómina especializado y convertir el resultado a contabilidad y tesorería.

Datos:

- empleado;
- departamento;
- coste empresa;
- nómina;
- Seguridad Social;
- retención;
- anticipos;
- dietas;
- gastos;
- bonus;
- vacaciones si se desea gestión HR.

### 33.1. Coste real del empleado

No responder solo “salario”.

```text
Coste persona =
bruto
+ Seguridad Social empresa
+ bonus
+ beneficios
+ seguros
+ formación
+ equipos
+ otros costes atribuibles
```

### 33.2. Simulador de contratación

Pregunta:

> “¿Qué pasa si contrato dos personas a 35.000 €?”

Resultado:

- coste anual aproximado bajo supuestos parametrizados;
- incremento de burn mensual;
- caja final prevista;
- runway;
- punto de equilibrio adicional;
- escenario ventas necesarias.

No presentar estimaciones de cargas sociales o fiscales como definitivas si no se dispone de los parámetros laborales exactos.

---

# PARTE XVIII — IMPUESTOS

## 34. Motor fiscal separado del motor contable

Una operación debe tener:

```text
AccountingTreatment
TaxTreatment
```

porque una misma realidad puede tener efectos distintos en contabilidad y fiscalidad.

---

## 35. Tax Profile

El sistema define las obligaciones concretas del cliente.

Ejemplo conceptual:

```yaml
obligations:
  VAT_303: quarterly
  IRPF_130: quarterly
  WITHHOLDING_111: quarterly
  INFORMATION_190: annual
```

Los modelos exactos deben activarse por censal/régimen/actividad, no por una lista genérica para todos.

---

## 36. Calendario fiscal

Para cada obligación:

- periodo;
- fecha inicio preparación;
- fecha interna cierre;
- fecha límite legal;
- responsable;
- estado;
- importe estimado;
- importe final;
- presentado sí/no;
- NRC/justificante cuando corresponda.

Estados:

```text
NOT_STARTED
DATA_COLLECTION
REVIEW
READY
APPROVED
FILED
PAID
CLOSED
```

---

## 37. Autónomos y libros registro

El sistema debe adaptar la experiencia a las obligaciones reales.

Según la AEAT, en términos generales:

### Profesional en estimación directa

- libro de ingresos;
- libro de gastos;
- libro de bienes de inversión;
- libro de provisiones de fondos y suplidos.

### Empresario no mercantil en estimación directa normal o empresario en simplificada

- ventas e ingresos;
- compras y gastos;
- bienes de inversión.

### Actividad empresarial mercantil en estimación directa normal

- contabilidad conforme Código de Comercio y PGC.

La interfaz puede parecer idéntica para el usuario, pero el motor debe generar los libros correspondientes.

---

# PARTE XIX — SII

## 38. Suministro Inmediato de Información

Debe existir un módulo de IVA/SII independiente de VERI*FACTU.

El SII supone llevanza de determinados libros de IVA mediante suministro electrónico de registros a la AEAT. Actualmente afecta obligatoriamente, entre otros supuestos, a determinados sujetos con liquidación mensual como grandes empresas, REDEME y grupos de IVA.

Arquitectura:

```text
VATLedgerRecord
→ SII mapper
→ validation
→ AEAT submission
→ response
→ correction/retry
```

No confundir SII con emisión de factura ni con VERI*FACTU.

---

# PARTE XX — CIERRE CONTABLE

## 39. El cierre mensual debe ser un producto

No una tarea improvisada.

Checklist configurable:

### Bancos

- todos extractos importados;
- conciliación ≥ objetivo;
- partidas antiguas revisadas.

### Clientes

- subledger = mayor;
- vencidos revisados;
- cobros no aplicados;
- dudoso cobro.

### Proveedores

- subledger = mayor;
- facturas faltantes;
- pagos no aplicados;
- GRNI/recepciones no facturadas cuando proceda.

### Personal

- nóminas;
- Seguridad Social;
- anticipos;
- gastos empleados.

### Impuestos

- IVA;
- retenciones;
- otras obligaciones.

### Activos

- altas;
- bajas;
- amortización.

### Periodificación

- seguros;
- alquileres;
- suscripciones;
- ingresos/gastos devengados.

### Inventario

- valoración;
- diferencias;
- deterioros.

### Financiación

- intereses;
- principal;
- reclasificación CP/LP cuando corresponda.

### Intercompany

- saldos cruzados;
- diferencias.

---

## 40. Hard close y soft close

### Soft close

Reporting provisional.

### Hard close

Periodo bloqueado.

Regla:

> una operación posterior no puede modificar silenciosamente un periodo cerrado.

Opciones:

- contabilizar en periodo actual;
- solicitar reapertura;
- asiento de ajuste autorizado.

Toda reapertura queda registrada.

---

# PARTE XXI — GESTORÍA / DESPACHO PROFESIONAL

## 41. La gestoría trabaja por excepciones

El portal de gestoría debe mostrar:

```text
Empresa X
98,2 % documentos procesados
12 operaciones para revisar
3 IVA dudosos
2 facturas duplicadas
1 cuenta bancaria sin conciliar
IVA provisional: X
Impuestos próximos: Y
Cierre septiembre: 93 %
```

El profesional debería dedicar tiempo a juicio, no a transcribir documentos.

### 41.1. Cola de excepciones

Ordenar por:

- riesgo fiscal;
- importe;
- proximidad a declaración;
- incertidumbre;
- antigüedad.

### 41.2. Correcciones del asesor

Cuando un asesor cambia:

```text
AWS → 629xxx
```

por

```text
AWS → cuenta específica cloud
```

el sistema puede aprender una **regla de empresa**, no una regla universal.

---

# PARTE XXII — CONTROL DE GESTIÓN

## 42. P&L analítica

Permitir:

- empresa;
- grupo;
- unidad de negocio;
- departamento;
- producto;
- cliente;
- proyecto;
- canal;
- comercial.

Ejemplo:

```text
Ingresos cliente A
- costes directos
= margen bruto
- coste equipo asignado
- costes variables
= margen de contribución
- costes indirectos asignados
= resultado analítico
```

No confundir este resultado de gestión con el resultado contable legal.

---

## 43. Presupuesto

Versionado:

```text
Budget 2027 v1
Budget 2027 Board Approved
Forecast Jan
Forecast Apr
Forecast Jul
Latest Estimate
```

Nunca sobrescribir forecasts históricos.

### 43.1. Granularidad

Presupuestar por:

- cuenta;
- centro coste;
- mes;
- proyecto;
- unidad negocio.

### 43.2. Variación

```text
Variance € = Actual - Budget
Variance % = (Actual - Budget) / |Budget|
```

La presentación debe respetar convenciones de signo para ingresos/gastos.

---

# PARTE XXIII — CFO DIGITAL

## 44. Dashboard directivo

Responder primero a cinco preguntas:

1. ¿Cuánto hemos vendido?
2. ¿Cuánto hemos ganado?
3. ¿Cuánto dinero tenemos?
4. ¿Cuánto nos deben y debemos?
5. ¿Qué pasará con la caja?

Después profundizar.

---

## 45. KPIs fundamentales

### Ingresos

```text
Revenue growth % = (Revenue_t - Revenue_t-1) / Revenue_t-1
```

### Margen bruto

```text
Gross Margin % = (Revenue - COGS) / Revenue
```

### EBITDA

Construir desde el P&L conforme a una definición documentada. No esconder reclasificaciones “ajustadas”.

### Margen EBITDA

```text
EBITDA Margin = EBITDA / Revenue
```

### Current ratio

```text
Current Ratio = Current Assets / Current Liabilities
```

### Quick ratio

```text
Quick Ratio = (Cash + Receivables + liquid short-term assets) / Current Liabilities
```

### Net debt

```text
Net Debt = Financial Debt - Cash and cash equivalents
```

### Net debt / EBITDA

```text
Net Debt / EBITDA
```

Documentar tratamiento de leasing, caja restringida y deuda asimilada.

### Burn

```text
Net Burn = Cash Outflows - Cash Inflows
```

para empresas que consumen caja.

### Runway

```text
Runway months = Available Cash / Monthly Net Burn
```

Solo tiene sentido si el burn es representativo; puede usarse forecast en lugar de promedio histórico.

### Break-even

```text
Break-even revenue = Fixed Costs / Contribution Margin %
```

### Customer concentration

```text
Top1 Revenue / Total Revenue
Top5 Revenue / Total Revenue
```

---

## 46. Cash Conversion Cycle

```text
CCC = DIO + DSO - DPO
```

Debe permitir ver qué componente empeora la caja:

- inventario demasiado lento;
- clientes cobrando tarde;
- proveedores pagados demasiado pronto.

---

## 47. Escenarios

Crear scenario engine.

Variables:

- crecimiento ventas;
- precio;
- volumen;
- churn;
- margen;
- contrataciones;
- salarios;
- alquiler;
- marketing;
- capex;
- financiación;
- plazo cobro;
- plazo pago;
- tipos interés.

Outputs:

- P&L;
- balance;
- cash flow;
- caja mínima;
- runway;
- deuda;
- impuestos aproximados bajo supuestos definidos.

Escenarios:

```text
BASE
UPSIDE
DOWNSIDE
STRESS
```

---

# PARTE XXIV — IA FINANCIERA

## 48. Sistema de confianza

Cada recomendación automática debe devolver:

```yaml
prediction:
  value: "629-SaaS"
  confidence: 0.982
  evidence:
    supplier_history: true
    text_match: true
    prior_accounting: true
```

### Política sugerida

```text
> 99 % + bajo riesgo → automatización
95–99 % → automatización si regla histórica fuerte
80–95 % → propuesta
<80 % → preguntar/revisión
```

Los números son puntos de partida de producto, no un estándar legal; deben calibrarse con datos reales.

---

## 49. Memoria empresarial

El sistema debe aprender datos explícitos y auditables como:

- proveedor X siempre es software;
- sede Madrid usa centro de coste MAD;
- responsable de marketing aprueba campañas;
- cliente Y paga por confirming;
- proyecto Z exige PO del cliente;
- gastos de hosting se reparten 70/30 entre productos.

Estas reglas deben ser visibles y editables.

No “enterrar” conocimiento financiero crítico en memoria opaca de un modelo.

---

## 50. Preguntas que debe poder responder

### Autónomo

- ¿Cuánto he facturado este mes?
- ¿Cuánto me deben?
- ¿Qué gastos llevo?
- ¿Qué IVA estimado tengo?
- ¿Cuánto dinero puedo retirar sin tensionar caja?

### Responsable

- ¿Qué gastos tengo pendientes de aprobar?
- ¿Cómo voy respecto a presupuesto?

### Controller

- ¿Por qué subió el gasto de software?
- ¿Qué cuentas tienen movimientos anómalos?
- ¿Qué centros están por encima de presupuesto?

### CFO

- ¿Qué caja mínima tendremos en 13 semanas?
- ¿Qué clientes explican la subida del DSO?
- ¿Cuál es el impacto de contratar 10 personas?

### CEO

- ¿Cómo va la empresa?
- ¿Qué tres cosas requieren atención?
- ¿Estamos generando caja?

---

# PARTE XXV — CONTROL DESDE WHATSAPP

## 51. WhatsApp es un control remoto, no un ERP embebido

No intentar representar todo con mensajes.

Usar WhatsApp para:

- comandos;
- consultas;
- confirmaciones;
- alertas;
- adjuntar documentos;
- aprobaciones;
- resúmenes.

Usar web/app para:

- configuración masiva;
- reporting complejo;
- conciliaciones múltiples;
- cierre;
- auditoría;
- dashboards detallados;
- administración de permisos.

---

## 52. Intent DSL

La IA debería traducir lenguaje a una instrucción estructurada.

Ejemplo:

```json
{
  "intent": "CREATE_INVOICE",
  "company_id": "cmp_123",
  "customer_id": "cus_456",
  "lines": [
    {
      "description": "Instalación eléctrica",
      "quantity": 1,
      "unit_price": 2500
    }
  ],
  "payment_terms": "NET_30"
}
```

Después el motor valida.

La IA nunca llama directamente a SQL de producción.

---

## 53. Identidad en WhatsApp

Un número no basta como única prueba para operaciones sensibles.

Mapeo:

```text
WhatsApp identity
→ User
→ Company membership
→ Role
→ Permissions
→ Approval limits
```

Para operaciones críticas:

- confirmación reforzada;
- segundo factor;
- deep link a app;
- firma/aprobación adicional.

---

## 54. Comandos sensibles

Clasificar por riesgo.

### Riesgo bajo

- consultar saldo;
- buscar factura;
- descargar documento;
- crear borrador.

### Medio

- emitir factura;
- aprobar gasto moderado;
- enviar recordatorio.

### Alto

- cambiar IBAN proveedor;
- pagar;
- presentar impuestos;
- modificar periodos cerrados;
- crear administrador;
- exportar datos completos.

### Crítico

- transferencias altas;
- cambios masivos de permisos;
- eliminación legal de datos;
- cambios de configuración fiscal.

Cada nivel requiere controles mayores.

---

# PARTE XXVI — ROLES Y SEGREGACIÓN DE FUNCIONES

## 55. Roles base

- owner;
- CEO;
- CFO;
- finance admin;
- accountant;
- external advisor;
- controller;
- AP clerk;
- AR clerk;
- manager;
- employee;
- auditor read-only;
- developer/support restricted.

### 55.1. Permisos por acción

No usar únicamente “admin/no admin”.

Ejemplo:

```text
invoice.create
invoice.issue
invoice.cancel
vendor.create
vendor.bank.change
expense.approve
payment.prepare
payment.approve
payment.execute
period.close
period.reopen
tax.file
user.invite
```

---

## 56. Segregation of Duties

Combinaciones peligrosas:

```text
Crear proveedor + cambiar IBAN + aprobar factura + ejecutar pago
```

El sistema debe detectar conflicto.

Reglas:

```yaml
sod:
  vendor_bank_change:
    cannot_self_approve: true
  payment_over_25000:
    approvers_required: 2
```

---

# PARTE XXVII — FRAUDE Y ANOMALÍAS

## 57. Riesgos a detectar

### Proveedor

- IBAN nuevo;
- dominio email distinto;
- factura duplicada;
- numeración extraña;
- importe muy superior a histórico;
- proveedor inactivo;
- alta reciente + pago alto.

### Empleado

- ticket repetido;
- gasto fuera de política;
- gasto fin de semana inusual;
- mismos importes reiterados;
- comercio no habitual.

### Cliente

- aumento de morosidad;
- concentración;
- pagos parciales repetidos;
- descuentos comerciales fuera de política.

### Contabilidad

- asientos manuales fuera horario;
- movimiento en cuenta restringida;
- redondeos repetidos;
- asientos cerca del cierre;
- reaperturas de periodo.

Anomalía no significa fraude. Debe generar revisión, no acusación automática.

---

# PARTE XXVIII — DOCUMENTOS Y TRAZABILIDAD

## 58. Drill-down completo

Desde un número del P&L:

```text
Publicidad: 84.231 €
→ movimientos
→ asiento
→ factura
→ proveedor
→ aprobación
→ PDF/XML original
→ pago
→ banco
```

Y desde banco, al revés.

Ese recorrido debe estar disponible con uno o pocos clics.

---

## 59. Retención y conservación

El Código de Comercio establece con carácter general la conservación durante seis años de libros, correspondencia, documentación y justificantes concernientes al negocio, desde el último asiento, sin perjuicio de otros plazos o normas especiales.

El motor de retención debe permitir políticas por clase documental y fundamento legal.

No borrar automáticamente documentos financieros solo porque un usuario pulse “eliminar”.

---

# PARTE XXIX — SEGURIDAD Y PRIVACIDAD

## 60. Base de seguridad

- MFA;
- RBAC/ABAC;
- principio de mínimo privilegio;
- cifrado en tránsito;
- cifrado en reposo;
- gestión segura de secretos;
- rotación de claves;
- copias de seguridad;
- restore tests;
- logs de seguridad;
- alertas;
- separación de entornos;
- protección frente a inyección;
- rate limits;
- WAF donde corresponda;
- escaneo de dependencias;
- gestión de vulnerabilidades.

---

## 61. GDPR/RGPD

Diseñar desde el inicio:

- finalidad;
- minimización;
- exactitud;
- limitación del plazo;
- confidencialidad;
- accountability;
- contratos de encargado;
- subencargados;
- transferencias internacionales;
- derechos de interesados;
- registro de tratamientos;
- seguridad conforme riesgo.

El RGPD exige medidas técnicas y organizativas apropiadas al riesgo y menciona, entre otras, cifrado/seudonimización, confidencialidad, integridad, disponibilidad, resiliencia y capacidad de restauración.

---

## 62. Multi-tenant seguro

Nunca confiar solo en filtros de frontend.

Cada consulta backend debe quedar ligada a:

```text
user_id
organization_id
legal_entity_id
permission_scope
```

Tests automáticos de aislamiento tenant son obligatorios.

---

# PARTE XXX — INTEGRACIONES

## 63. Capas de integración

### Fiscal

- AEAT SIF/VERI*FACTU;
- SII;
- factura electrónica pública/privada;
- otros conectores futuros.

### Bancos

- open banking mediante proveedor autorizado;
- ficheros bancarios;
- SEPA;
- pasarelas.

### Comercial

- CRM;
- ecommerce;
- TPV;
- suscripciones;
- marketplaces.

### Personal

- nómina;
- HRIS;
- control horario si procede.

### Operaciones

- almacén;
- procurement;
- proyectos;
- logística.

### Documentos

- email;
- drive;
- SFTP;
- API;
- upload;
- WhatsApp.

---

# PARTE XXXI — API Y EVENTOS

## 64. API-first

Todo lo que hace el frontend debería poder hacerse mediante servicios internos/API con permisos.

Ejemplos:

```text
POST /invoices/drafts
POST /invoices/{id}/issue
POST /expenses
POST /approvals/{id}/approve
POST /payments/batches
GET  /reports/pnl
GET  /cash/forecast
```

---

## 65. Event-driven

Eventos:

```text
invoice.issued
invoice.delivered
invoice.overdue
payment.received
bank.transaction.imported
expense.approved
journal.posted
period.closed
vendor.bank_changed
```

Consumidores:

- contabilidad;
- fiscal;
- reporting;
- notificaciones;
- riesgo;
- tesorería.

Usar idempotency keys para evitar dobles efectos.

---

# PARTE XXXII — REPORTING

## 66. Estados legales

Según marco aplicable, soportar la generación/datos para:

- balance;
- pérdidas y ganancias;
- estado de cambios en patrimonio neto cuando proceda;
- estado de flujos de efectivo cuando proceda;
- memoria/datos auxiliares;
- balance de sumas y saldos;
- libro diario;
- libro mayor;
- inventarios.

El Código de Comercio exige contabilidad ordenada y contempla Libro Diario y Libro de Inventarios y Cuentas Anuales para empresarios sujetos a estas obligaciones.

---

## 67. Reporting de gestión

- P&L mensual;
- YTD;
- rolling 12 months;
- comparativo año anterior;
- presupuesto;
- forecast;
- P&L por dimensión;
- cash flow;
- bridge de EBITDA;
- bridge de caja;
- ventas por cliente;
- margen por producto;
- gasto por proveedor.

---

# PARTE XXXIII — ESCALADO POR TIPO DE CLIENTE

## 68. Autónomo individual

### Debe ver

- facturar;
- cobrar;
- gastos;
- banco;
- impuestos estimados;
- beneficio;
- caja;
- gestoría.

### Debe ocultarse

- plan contable complejo;
- journals;
- consolidación;
- procurement sofisticado.

### Automatización objetivo

> 90 %+ de tareas repetitivas sin interacción manual, una vez aprendidas reglas seguras.

Ese porcentaje es una meta de producto, no una promesa contable universal.

---

## 69. Autónomo con empleados

Añadir:

- empleados;
- nóminas;
- gastos;
- aprobaciones;
- proyectos;
- coste de personal;
- previsión de nóminas;
- permisos.

---

## 70. Microempresa

Añadir:

- clientes/proveedores;
- AR/AP;
- cash forecast;
- facturación recurrente;
- control de gastos;
- cierre mensual;
- gestoría colaborativa.

---

## 71. Pequeña empresa

Añadir:

- departamentos;
- presupuesto;
- proyectos;
- rentabilidad cliente/producto;
- workflows;
- activos;
- inventario opcional;
- reporting gerencial.

---

## 72. Mediana empresa

Añadir:

- procurement;
- three-way matching;
- múltiples aprobadores;
- controller;
- rolling forecast;
- 13-week cash flow;
- SII cuando aplique;
- múltiples bancos;
- límites de crédito;
- intercompany básico;
- BI/API avanzada.

---

## 73. Gran empresa

Añadir:

- multi-entidad;
- multi-país;
- multi-moneda;
- consolidación;
- intercompany matching;
- treasury;
- cash pooling;
- IFRS/reporting paralelo cuando corresponda;
- SSO/SAML;
- SCIM;
- auditoría avanzada;
- SoD;
- workflows complejos;
- SLA;
- data warehouse;
- integración ERP coexistente.

En grandes empresas, el producto puede funcionar como capa financiera inteligente y operativa incluso si un ERP corporativo sigue siendo el system of record para determinados módulos.

---

# PARTE XXXIV — MULTIEMPRESA Y CONSOLIDACIÓN

## 74. Jerarquía

```text
Organization
 ├── Legal Entity A
 │    ├── Branch
 │    └── Departments
 ├── Legal Entity B
 └── Legal Entity C
```

Cada sociedad mantiene ledger independiente.

---

## 75. Intercompany

Cuando A factura a B:

- documento emisor;
- documento receptor;
- vínculo intercompany;
- saldos cruzados;
- conciliación;
- diferencias;
- eliminación consolidación.

Crear un identificador común:

```text
intercompany_transaction_id
```

---

## 76. Moneda

Guardar siempre:

- moneda de transacción;
- importe original;
- tipo de cambio;
- moneda funcional;
- importe funcional;
- fecha/tipo de fuente.

Nunca sustituir el importe original.

---

# PARTE XXXV — CONTROL DE CAMBIOS

## 77. Audit log inmutable

Ejemplo:

```text
10:24 invoice draft created by user_123
10:26 amount changed 2,500 → 2,750
10:27 approved by manager_44
10:28 issued F2026/00123
10:28 fiscal record generated
10:29 fiscal submission accepted
15/10 payment matched
31/10 period closed
```

Guardar:

- actor;
- fecha/hora;
- IP/device cuando legalmente/proporcionalmente proceda;
- acción;
- before/after;
- motivo;
- request ID;
- source channel.

---

# PARTE XXXVI — MOTOR DE REGLAS

## 78. Tipos de reglas

### Regla legal

No editable por usuario salvo actualización normativa del producto.

### Regla fiscal de empresa

Configurada por asesor.

### Regla contable

Mapping proveedor/categoría/cuenta.

### Regla de gestión

Dimensión/centro coste.

### Regla de aprobación

Importe/rol/departamento.

### Regla de automatización

Cuándo puede ejecutarse sin humano.

---

## 79. Precedencia

```text
Legal constraint
> fiscal/company policy
> accounting policy
> explicit user rule
> learned rule
> AI suggestion
```

Una sugerencia de IA jamás puede superar una restricción legal.

---

# PARTE XXXVII — MOTOR DE EXCEPCIONES

## 80. Diseñar para excepciones, no para casos perfectos

La automatización real falla en los bordes:

- factura sin NIF;
- dos proveedores con nombre similar;
- abono;
- pago agregado;
- pago parcial;
- factura en divisa;
- factura con varias bases IVA;
- inversión sujeto pasivo;
- factura anterior a recepción;
- anticipo;
- diferencia de céntimos;
- factura duplicada;
- devolución bancaria;
- impago;
- proveedor con nuevo IBAN.

El producto excelente tiene una **cola de excepciones impecable**.

Cada excepción debe mostrar:

1. qué ocurrió;
2. por qué el sistema no decidió;
3. evidencia;
4. opciones válidas;
5. impacto;
6. aprobación necesaria.

---

# PARTE XXXVIII — EXPERIENCIA CONVERSACIONAL

## 81. Patrones de conversación

### Consulta

> “¿Cuánto debemos a proveedores?”

Respuesta:

```text
Pendiente total: 84.210 €
Vencido: 12.400 €
Próximos 7 días: 24.600 €
Próximos 30 días: 51.800 €
```

Luego permitir drill-down.

### Acción reversible

> “Crea borrador de factura.”

Puede ejecutar y devolver borrador.

### Acción irreversible/sensible

> “Emite esta factura.”

Debe devolver resumen y pedir confirmación cuando la política lo requiera.

### Ambigüedad

> “Paga la factura de López.”

Si hay tres:

no adivinar.

Mostrar opciones.

---

## 82. Respuestas financieras

Cada respuesta debería poder incluir:

- periodo;
- moneda;
- alcance;
- si es dato real o forecast;
- fecha de actualización;
- enlace a evidencia;
- nivel de incertidumbre si es estimación.

Ejemplo:

```text
Caja disponible hoy: 182.430 €
Datos bancarios actualizados: 17:10
Incluye 3 bancos. Excluye 20.000 € restringidos.
```

---

# PARTE XXXIX — CONTROL DE CALIDAD CONTABLE

## 83. Validadores automáticos diarios

- asiento descuadrado: imposible;
- cuentas no permitidas;
- factura sin contraparte;
- IVA sin base;
- cliente con saldo anómalo;
- proveedor con saldo deudor inesperado;
- cuenta banco contable ≠ extracto;
- duplicados;
- saltos de numeración;
- periodos cerrados modificados;
- documento sin soporte;
- movimientos antiguos pendientes;
- intercompany no conciliado.

---

## 84. Health score financiero

No como “nota de empresa buena/mala”, sino como panel de calidad operativa.

Ejemplo:

```text
Bank reconciliation      99.2 %
AR matched              100.0 %
AP matched               98.6 %
Missing documents         12
Close tasks complete      91 %
Tax exceptions             3
```

---

# PARTE XL — CONTABILIDAD TEMPORAL Y DEVENGO

## 85. Diferenciar fechas

Una operación puede tener:

- fecha documento;
- fecha expedición;
- fecha operación;
- fecha contable;
- fecha recepción;
- fecha vencimiento;
- fecha fiscal;
- fecha pago.

No usar una única columna `date`.

---

## 86. Periodificaciones

Ejemplo: seguro anual de 12.000 € pagado en enero.

El sistema puede mantener schedule:

```text
1.000 €/mes
```

Y generar los ajustes necesarios según la política contable.

Esto evita P&L distorsionados.

---

# PARTE XLI — RECONOCIMIENTO DE INGRESOS Y CONTRATOS

## 87. Para servicios/proyectos complejos

Separar:

- contrato;
- obligación/prestación;
- facturación;
- reconocimiento de ingreso;
- cobro.

Porque:

```text
facturar ≠ necesariamente reconocer todo el ingreso en ese mismo instante
```

El motor debe admitir schedules y reglas definidas por política contable.

---

# PARTE XLII — CIERRE ANUAL

## 88. Checklist anual

Además del cierre mensual:

- inventario físico;
- confirmación saldos;
- circularización si auditoría;
- deterioros;
- vidas útiles;
- provisiones;
- litigios informados por responsables;
- periodificaciones;
- deuda CP/LP;
- impuestos;
- operaciones vinculadas;
- intercompany;
- subvenciones;
- patrimonio;
- resultado;
- cuentas anuales;
- memoria;
- libros;
- legalización/depósito mediante procesos externos o integrados cuando corresponda.

---

# PARTE XLIII — MÉTRICAS DEL PROPIO PRODUCTO

## 89. Medir cuánto trabajo elimina

KPIs de producto:

```text
% facturas emitidas por conversación
% facturas recibidas autoextraídas
% contabilización automática
% conciliación automática
% documentos sin intervención
minutos administrativos por 100 documentos
número de excepciones / 100 operaciones
correcciones del asesor / 100 asientos
close time
```

### KPI estrella

```text
Human touches per financial transaction
```

Objetivo: acercarlo a cero en operaciones rutinarias.

---

# PARTE XLIV — SLA Y FIABILIDAD

## 90. Principios

Un software financiero no puede tratar la disponibilidad como una app social.

Necesita:

- colas durables;
- retries;
- idempotencia;
- observabilidad;
- trazas;
- métricas;
- alertas;
- backups;
- disaster recovery;
- reconciliadores de integridad.

### 90.1. Regla

> Nunca asumir que porque una API devolvió timeout, la operación no ocurrió.

Especialmente en:

- emisión fiscal;
- pagos;
- emails;
- facturas electrónicas.

Siempre implementar consulta/reconciliación por identificador idempotente.

---

# PARTE XLV — MODELO DE APROBACIONES

## 91. Approval Engine

Objeto:

```text
ApprovalRequest
```

Campos:

- action;
- amount;
- currency;
- requester;
- company;
- department;
- risk level;
- approver chain;
- deadline;
- evidence;
- status.

### Ejemplo

```text
< 500 € → responsable
500–5.000 € → responsable + finanzas
5.000–25.000 € → CFO
>25.000 € → CFO + CEO
```

Todo configurable.

---

# PARTE XLVI — CATÁLOGO DE AUTOMATIZACIONES

## 92. Automatizaciones de nivel 1 — Captura

- leer factura;
- identificar proveedor;
- extraer líneas;
- detectar IVA;
- detectar vencimiento;
- detectar duplicado;
- archivar.

## 93. Nivel 2 — Enriquecimiento

- categoría;
- cuenta;
- dimensiones;
- proyecto;
- política;
- aprobación.

## 94. Nivel 3 — Contabilidad

- asiento;
- open item;
- libro fiscal;
- amortización;
- periodificación;
- conciliación.

## 95. Nivel 4 — Operaciones

- recordatorios;
- propuesta de pagos;
- emisión recurrente;
- cierre de tareas.

## 96. Nivel 5 — Dirección

- forecast;
- alertas de caja;
- explicación de desviaciones;
- escenarios;
- detección de riesgos.

---

# PARTE XLVII — ALERTAS QUE SÍ APORTAN VALOR

## 97. Alertas económicas

- caja prevista por debajo del mínimo;
- cliente importante vencido;
- gasto +X % vs budget;
- margen cae;
- ventas caen;
- proveedor aumenta precio;
- concentración de cliente;
- deuda próxima a covenant;
- impuestos altos próximos.

## 98. Alertas contables

- conciliación incompleta;
- cuenta anómala;
- factura duplicada;
- documento faltante;
- asiento manual inusual;
- periodo reabierto.

## 99. Alertas de seguridad

- cambio IBAN;
- nuevo administrador;
- exportación masiva;
- login extraño;
- permiso elevado;
- pago excepcional.

Evitar spam. Priorizar impacto y urgencia.

---

# PARTE XLVIII — CONTABILIDAD PARA GRANDES EMPRESAS

## 100. Diseño escalable

Para empresas grandes, soportar:

- varios ledgers;
- local GAAP;
- reporting ledger;
- adjustments;
- group chart of accounts;
- mappings;
- múltiples calendarios;
- intercompany;
- eliminaciones;
- monedas;
- consolidación;
- auditoría.

### 100.1. Ledger local

Cumplimiento legal de la entidad.

### 100.2. Ledger de reporting

Ajustes para grupo/NIIF cuando corresponda.

### 100.3. Ledger de gestión

Ajustes internos que no deben contaminar contabilidad legal.

---

# PARTE XLIX — CONSOLIDACIÓN

## 101. Proceso

```text
Trial balance entidades
→ mapping group CoA
→ FX translation
→ intercompany match
→ eliminations
→ consolidation adjustments
→ consolidated statements
```

No construir consolidación avanzada en un MVP para autónomos, pero dejar el modelo de datos preparado para no romperlo más adelante.

---

# PARTE L — PRINCIPIOS DE UX

## 102. Progressive disclosure

Un autónomo no debe ver 200 opciones.

Interfaz:

### Nivel simple

```text
Facturar
Gastos
Cobros
Banco
Impuestos
Cómo va mi negocio
```

### Nivel profesional

mostrar módulos adicionales.

### Nivel experto

plan contable, diarios, cierres, reporting avanzado.

---

## 103. Toda cifra debe poder explicarse

Si el sistema dice:

```text
EBITDA = 73.421 €
```

Debe poder responder:

> “¿De dónde sale?”

Y bajar hasta los documentos.

No crear “cajas negras de KPI”.

---

# PARTE LI — ARQUITECTURA TÉCNICA RECOMENDADA

## 104. Servicios lógicos

No significa que deban ser microservicios desde el primer día. Pueden comenzar en un modular monolith bien separado.

Dominios:

```text
Identity
Organizations
MasterData
Documents
Sales
Purchasing
Expenses
Ledger
Tax
Banking
Treasury
Assets
Inventory
PayrollIntegration
Approvals
Reporting
Forecasting
Compliance
Notifications
AI-Orchestration
Audit
```

### Recomendación inicial

> modular monolith + boundaries claros + event bus/outbox.

Evita complejidad prematura sin sacrificar diseño.

---

## 105. Base de datos

Relacional como source of truth financiero.

Necesidades:

- ACID;
- constraints;
- foreign keys;
- transacciones;
- versionado;
- índices;
- auditoría.

Documentos en object storage con hashes; metadatos en DB.

Analytics puede replicarse a warehouse.

---

## 106. Nunca usar floats para dinero

Usar decimal/fixed precision.

Guardar:

```text
amount_decimal
currency
```

Redondeos deben seguir reglas por moneda/impuesto.

---

## 107. Idempotencia

Toda acción externa sensible:

```text
idempotency_key
```

Ejemplo: el usuario pulsa dos veces “emitir”.

Resultado correcto:

> una factura.

No dos.

---

# PARTE LII — TESTING FINANCIERO

## 108. Tests indispensables

### Contabilidad

- debe=haber;
- cierres;
- reversos;
- moneda;
- periodo.

### Facturación

- numeración;
- series;
- rectificativas;
- impuestos;
- descuentos;
- anticipos.

### Fiscal

- esquemas;
- payloads;
- respuestas;
- edge cases.

### Banco

- cobro parcial;
- pago agregado;
- comisión bancaria;
- devolución;
- duplicado.

### Permisos

- cada endpoint;
- cross-company;
- escalado de privilegios.

### AI

- extracción;
- clasificación;
- adversarial prompts;
- alucinaciones;
- datos de otra empresa;
- intent ambiguity.

---

# PARTE LIII — QUÉ NO HARÍA

## 109. Anti-patrones

### No: chatbot escribiendo directamente a DB

Sí: intents validados por APIs.

### No: plan contable usado como BI

Sí: dimensiones.

### No: PDF como fuente de verdad

Sí: factura estructurada + representación.

### No: “IA 100 % autónoma”

Sí: autonomía proporcional al riesgo.

### No: borrar facturas

Sí: rectificación/anulación conforme mecanismo legal aplicable + trazabilidad.

### No: Excel paralelo para impuestos

Sí: libros derivados del mismo ledger.

### No: una cuenta bancaria contable para todos los IBAN

Sí: auxiliares separados.

### No: `is_paid=true`

Sí: pagos parciales y asignaciones.

### No: una fecha única

Sí: documento/operación/contable/fiscal/vencimiento/pago.

### No: admin universal

Sí: permisos granulares y SoD.

---

# PARTE LIV — EL “AUTOPILOTO” IDEAL

## 110. Rutina diaria automática

Cada madrugada o continuamente:

```text
1. importar bancos
2. recibir facturas
3. extraer documentos
4. detectar duplicados
5. proponer contabilización
6. auto-contabilizar reglas seguras
7. conciliar
8. detectar vencimientos
9. actualizar forecast
10. actualizar impuestos estimados
11. detectar anomalías
12. preparar excepciones
13. generar digest
```

Mensaje matinal:

```text
Buenos días.

Caja disponible: 182.430 €
Cobros esperados hoy: 12.600 €
Pagos previstos hoy: 8.220 €
3 facturas requieren revisión
2 clientes vencidos por 9.830 €
No hay incidencias fiscales críticas
```

---

# PARTE LV — DIGEST PARA CADA PERFIL

## 111. Autónomo

Máximo cinco datos y acciones.

## 112. Administración

Excepciones + vencimientos + conciliación.

## 113. CFO

Caja + forecast + desviaciones + working capital + riesgo.

## 114. CEO

Ventas + margen + EBITDA + caja + alertas estratégicas.

## 115. Gestoría

Datos faltantes + fiscal + cierre + excepciones.

---

# PARTE LVI — MATRIZ DE PRODUCTO

## 116. Qué módulos activar

| Módulo | Autónomo | Autónomo + equipo | Pyme | Mediana | Grande |
|---|---:|---:|---:|---:|---:|
| Facturación | ✓ | ✓ | ✓ | ✓ | ✓ |
| Gastos | ✓ | ✓ | ✓ | ✓ | ✓ |
| Banco | ✓ | ✓ | ✓ | ✓ | ✓ |
| Libros IRPF/IVA | ✓ | ✓ | opc. | opc. | — |
| Partida doble completa | oculta/opc. | oculta/opc. | ✓ | ✓ | ✓ |
| Nómina integración | opc. | ✓ | ✓ | ✓ | ✓ |
| Aprobaciones | simple | ✓ | ✓ | ✓✓ | ✓✓ |
| Presupuesto | básico | básico | ✓ | ✓✓ | ✓✓ |
| Proyectos | opc. | ✓ | ✓ | ✓ | ✓ |
| Inventario | opc. | opc. | opc. | ✓ | ✓ |
| Procurement | — | básico | opc. | ✓ | ✓✓ |
| SII | si aplica | si aplica | si aplica | si aplica | habitual si aplica |
| Consolidación | — | — | opc. | opc. | ✓ |
| Treasury | básico | básico | ✓ | ✓✓ | ✓✓ |
| SoD | — | básico | ✓ | ✓✓ | ✓✓ |

---

# PARTE LVII — ROADMAP DE CONSTRUCCIÓN

## 117. Fase 0 — Fundaciones

Antes de UI sofisticada:

- modelo empresa;
- usuarios/roles;
- ledger;
- documentos;
- impuestos;
- auditoría;
- idempotencia;
- cierres;
- integridad.

## 118. Fase 1 — Autónomo impecable

- facturas venta;
- gastos;
- clientes/proveedores;
- banco;
- conciliación;
- libros;
- VERI*FACTU;
- gestoría;
- WhatsApp;
- dashboard simple.

## 119. Fase 2 — Micro/pyme

- partida doble visible;
- AP/AR;
- approvals;
- activos;
- proyectos;
- centros coste;
- presupuesto;
- cash forecast.

## 120. Fase 3 — Empresa mediana

- procurement;
- inventory;
- SII;
- advanced reporting;
- rolling forecast;
- treasury;
- multiempresa;
- API enterprise.

## 121. Fase 4 — Enterprise

- consolidation;
- multi-GAAP;
- intercompany;
- SSO/SCIM;
- SoD avanzado;
- custom workflows;
- data warehouse;
- SLA enterprise.

---

# PARTE LVIII — CRITERIOS DE ACEPTACIÓN

## 122. Un módulo no está terminado porque “funciona”

Ejemplo: invoice issuing solo está terminado si:

- valida identidad fiscal;
- valida numeración;
- valida serie;
- valida impuestos;
- genera documento;
- crea registro fiscal;
- crea asiento;
- crea open item;
- registra auditoría;
- maneja retry;
- es idempotente;
- controla permisos;
- soporta rectificación;
- testea edge cases;
- soporta exportación;
- puede ser explicado al auditor.

---

# PARTE LIX — LAS 20 REGLAS SECRETAS

## 123. Regla 1

**Una operación se introduce una vez.**

## 124. Regla 2

**Todo número debe poder trazarse hasta evidencia.**

## 125. Regla 3

**La IA propone; las reglas validan.**

## 126. Regla 4

**Nunca editar historia financiera sin dejar historia.**

## 127. Regla 5

**Legal accounting y management accounting son capas distintas.**

## 128. Regla 6

**Los documentos no son contabilidad; generan contabilidad.**

## 129. Regla 7

**El banco no es contabilidad; concilia con contabilidad.**

## 130. Regla 8

**Facturado no significa cobrado.**

## 131. Regla 9

**Cobrado no significa ingreso del periodo.**

## 132. Regla 10

**Pagado no significa gasto del periodo.**

## 133. Regla 11

**Beneficio no significa caja.**

## 134. Regla 12

**El plan contable no sustituye las dimensiones analíticas.**

## 135. Regla 13

**La automatización debe aumentar cuando aumenta la certeza, no cuando aumenta el entusiasmo por la IA.**

## 136. Regla 14

**Cada acción sensible necesita identidad, permiso, evidencia y auditoría.**

## 137. Regla 15

**La gestoría debe revisar excepciones, no picar datos.**

## 138. Regla 16

**El cierre mensual debe ser un workflow medible.**

## 139. Regla 17

**La empresa debe saber hoy qué ocurrirá con su caja mañana.**

## 140. Regla 18

**Todo sistema fiscal debe diseñarse para cambios normativos.**

## 141. Regla 19

**La interfaz debe simplificarse según el usuario; el backend no.**

## 142. Regla 20

**La mejor operación administrativa es la que el usuario nunca tuvo que hacer.**

---

# PARTE LX — MODELO DE “EMPRESA AUTÓNOMA”

## 143. El estado ideal

Imagina una pyme en la que:

- las ventas generan automáticamente facturas;
- las facturas cumplen requisitos fiscales;
- los documentos entrantes se capturan solos;
- los gastos se clasifican;
- los responsables solo aprueban excepciones;
- el banco concilia automáticamente;
- se sabe quién debe dinero;
- los recordatorios salen según política;
- los pagos se preparan;
- las amortizaciones se calculan;
- los impuestos se estiman continuamente;
- la gestoría ve todo en tiempo real;
- el cierre es un checklist;
- el CFO tiene forecast diario;
- el CEO pregunta por WhatsApp;
- cada número puede auditarse.

Entonces el personal administrativo deja de actuar como “middleware humano” entre PDF, Excel, banco y gestoría.

---

# PARTE LXI — EJEMPLOS END-TO-END

## 144. Caso A — Autónomo vende servicio

Mensaje:

> “Factura 500 + IVA a Cliente A.”

Sistema:

```text
identifica cliente
→ tratamiento fiscal
→ muestra borrador
→ aprobación
→ número
→ registro SIF
→ factura
→ asiento/libro
→ vencimiento
→ envío
→ forecast cobro
```

Cuando entra transferencia:

```text
bank feed
→ match
→ cobro
→ conciliación
→ cuenta cliente cerrada
→ forecast actualizado
```

Trabajo manual final: una orden y, si la política lo exige, una confirmación.

---

## 145. Caso B — Pyme recibe factura recurrente

Llega factura AWS.

```text
email ingest
→ proveedor conocido
→ no duplicada
→ importe dentro rango
→ categoría cloud
→ centro coste Tecnología
→ impuesto validado
→ aprobación automática según política
→ asiento
→ vencimiento
```

Si el importe es 5 veces superior al normal:

```text
anomaly
→ bloquear autoaprobación
→ responsable recibe alerta
```

---

## 146. Caso C — Empresa compra portátil

Empleado envía factura 1.800 €.

El sistema detecta que puede ser activo y no mero gasto.

Pregunta:

> “Parece equipo informático con vida útil superior a un ejercicio. ¿Registrar como inmovilizado?”

Si se aprueba:

```text
asset
→ alta inmovilizado
→ IVA según tratamiento
→ proveedor
→ schedule amortización
→ pago
```

---

## 147. Caso D — Gran empresa pago sospechoso

Proveedor habitual cambia IBAN y factura 90.000 €.

Sistema:

```text
new_bank_account = true
amount_zscore = high
vendor = existing
requestor = same_person_who_changed_bank
```

Resultado:

```text
BLOCK PAYMENT
require independent vendor verification
require second approver
```

No acusa de fraude; impide una operación de alto riesgo hasta verificar.

---

# PARTE LXII — FUENTES Y FUNDAMENTO NORMATIVO

> Este documento es un diseño funcional/técnico, no asesoramiento jurídico o fiscal individual. Antes de producción deben revisarse las obligaciones concretas de cada cliente y las normas vigentes en ese momento.

## 148. Plan General de Contabilidad

Real Decreto 1514/2007, de 16 de noviembre. Texto consolidado BOE.

https://www.boe.es/buscar/act.php?id=BOE-A-2007-19884

Fundamenta el marco contable general español, principios, criterios y estructura del PGC.

## 149. PGC Pymes y criterios de microempresa

Real Decreto 1515/2007, de 16 de noviembre.

https://www.boe.es/buscar/act.php?id=BOE-A-2007-19966

A la fecha consultada, contempla la aplicación del PGC Pymes a empresas que reúnan al menos dos de determinadas condiciones durante dos ejercicios consecutivos, con los límites recogidos en el texto vigente; también contiene criterios específicos para microempresas.

## 150. Código de Comercio

Real Decreto de 22 de agosto de 1885, texto consolidado.

https://www.boe.es/buscar/act.php?id=BOE-A-1885-6627

Artículos especialmente relevantes para arquitectura:

- art. 25: contabilidad ordenada y libros;
- art. 28: Inventarios/Cuentas Anuales y Diario;
- art. 29: claridad y corrección de anotaciones;
- art. 30: conservación general de seis años;
- art. 34: cuentas anuales e imagen fiel.

## 151. Obligaciones contables de actividades económicas IRPF

AEAT:

https://sede.agenciatributaria.gob.es/Sede/irpf/Obligaciones.html

https://sede.agenciatributaria.gob.es/Sede/irpf/empresarios-individuales-profesionales/obligaciones-contables-registrales/actividades-profesionales-estimacion-directa.html

https://sede.agenciatributaria.gob.es/Sede/irpf/empresarios-individuales-profesionales/obligaciones-contables-registrales/actividades-empresariales-caracter-mercantil-estimacion-normal.html

Sirven para definir qué libros debe mantener el producto según actividad/modalidad.

## 152. Reglamento de facturación

Real Decreto 1619/2012, de 30 de noviembre, texto consolidado.

https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696

Debe utilizarse como fuente para contenido, expedición, conservación, rectificación y factura electrónica junto con sus modificaciones vigentes.

## 153. Sistemas informáticos de facturación / VERI*FACTU

Real Decreto 1007/2023 y normativa de desarrollo.

Orden HAC/1177/2024:

https://www.boe.es/buscar/act.php?id=BOE-A-2024-22138

Portal técnico AEAT:

https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/informacion-tecnica.html

Calendario AEAT consultado:

https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/nota-informativa-ampliacion-plazo-adaptacion-facturacion.html

## 154. Factura electrónica B2B

Real Decreto 238/2026, de 25 de marzo.

https://www.boe.es/buscar/act.php?id=BOE-A-2026-7295

Ley 18/2022, de creación y crecimiento de empresas:

https://www.boe.es/buscar/act.php?id=BOE-A-2022-15818

El diseño debe revalidar la publicación/entrada en vigor de la orden técnica prevista por el RD 238/2026 antes de fijar fechas de obligación en producción.

## 155. SII

AEAT:

https://sede.agenciatributaria.gob.es/Sede/iva/suministro-inmediato-informacion/informacion-general.html

El SII es un sistema de llevanza de libros registro de IVA mediante suministro electrónico de información y tiene un ámbito de obligados específico.

## 156. Morosidad comercial

Ley 3/2004, de 29 de diciembre.

https://www.boe.es/buscar/act.php?id=BOE-A-2004-21830

Debe considerarse al diseñar vencimientos, seguimiento del pago y reporting de morosidad.

## 157. RGPD

Reglamento (UE) 2016/679.

https://eur-lex.europa.eu/eli/reg/2016/679/oj

Relevante para minimización, seguridad, encargados, conservación y responsabilidad proactiva.

## 158. PSD2 / acceso a cuentas

Directiva (UE) 2015/2366.

https://eur-lex.europa.eu/eli/dir/2015/2366/oj

Si el producto accede o inicia operaciones sobre cuentas, debe hacerlo dentro del marco aplicable y normalmente apoyarse en proveedores debidamente autorizados cuando el propio SaaS no tenga esa condición.

## 159. ViDA

Directiva (UE) 2025/516, de 11 de marzo de 2025, sobre IVA en la era digital.

https://eur-lex.europa.eu/eli/dir/2025/516/oj

Refuerza la conveniencia estratégica de que el modelo de facturación europeo del producto sea estructurado, interoperable y preparado para reporting digital.

---

# PARTE LXIII — CHECKLIST MAESTRO DE CONSTRUCCIÓN

## 160. Identidad / organización

- [ ] Organization
- [ ] Legal Entity
- [ ] establecimientos
- [ ] ejercicios
- [ ] usuarios
- [ ] roles
- [ ] permisos granulares
- [ ] límites de aprobación
- [ ] MFA
- [ ] auditoría

## 161. Maestros

- [ ] clientes
- [ ] proveedores
- [ ] productos
- [ ] servicios
- [ ] cuentas
- [ ] impuestos
- [ ] centros coste
- [ ] proyectos
- [ ] bancos
- [ ] activos

## 162. Ventas

- [ ] presupuestos
- [ ] pedidos
- [ ] albaranes
- [ ] facturas
- [ ] rectificativas
- [ ] recurrentes
- [ ] cobros parciales
- [ ] vencimientos
- [ ] recordatorios
- [ ] aging

## 163. Compras

- [ ] solicitudes
- [ ] aprobación
- [ ] PO
- [ ] recepción
- [ ] factura
- [ ] matching
- [ ] contabilización
- [ ] vencimiento
- [ ] pagos

## 164. Contabilidad

- [ ] diario
- [ ] mayor
- [ ] balance sumas/saldos
- [ ] ledger
- [ ] subledgers
- [ ] periodificaciones
- [ ] amortizaciones
- [ ] cierres
- [ ] bloqueo periodos
- [ ] reaperturas controladas

## 165. Fiscal

- [ ] perfil fiscal
- [ ] libros
- [ ] IVA
- [ ] retenciones
- [ ] calendario
- [ ] SIF/VERI*FACTU
- [ ] SII
- [ ] B2B e-invoice
- [ ] evidencias de presentación

## 166. Banco

- [ ] conexiones
- [ ] importación
- [ ] conciliación
- [ ] partidas pendientes
- [ ] payment batches
- [ ] anomalías

## 167. CFO

- [ ] P&L
- [ ] balance
- [ ] cash flow
- [ ] cash forecast
- [ ] budget
- [ ] forecast
- [ ] scenarios
- [ ] working capital
- [ ] KPIs
- [ ] explicación de variaciones

## 168. IA

- [ ] intent parser
- [ ] document extraction
- [ ] account suggestion
- [ ] anomaly detection
- [ ] confidence scoring
- [ ] human review
- [ ] company rules
- [ ] grounded Q&A
- [ ] no direct DB access

## 169. Seguridad

- [ ] tenant isolation
- [ ] encryption
- [ ] secrets
- [ ] audit logs
- [ ] backups
- [ ] restore
- [ ] security monitoring
- [ ] export controls
- [ ] incident response

---

# CONCLUSIÓN

El producto ideal no se define por cuántas pantallas tiene, sino por cuántas acciones administrativas desaparecen.

La arquitectura correcta empieza por un **ledger financiero serio, determinista y auditable**. Encima se construyen facturación, compras, banco, impuestos, tesorería y reporting. Encima de todo ello se coloca una interfaz conversacional capaz de convertir lenguaje humano en acciones estructuradas.

La secuencia de valor debe ser:

```text
HABLAR / ENVIAR DOCUMENTO
        ↓
ENTENDER
        ↓
VALIDAR
        ↓
AUTORIZAR
        ↓
EJECUTAR
        ↓
CONTABILIZAR
        ↓
CUMPLIR
        ↓
CONCILIAR
        ↓
EXPLICAR
        ↓
PREDECIR
```

El mejor sistema no intenta sustituir el criterio profesional en los casos difíciles. Automatiza brutalmente los casos repetitivos, identifica las excepciones y lleva al profesional directamente a aquello que requiere juicio.

Para un autónomo, debe sentirse como hablar con una persona que lleva la administración.

Para una pyme, como tener administración + contabilidad + tesorería coordinadas.

Para una empresa mediana, como disponer de un controller y un CFO con los datos al día.

Para una gran empresa, como una capa financiera inteligente y auditable sobre procesos, entidades y sistemas complejos.

Y detrás de todos esos niveles debe existir **el mismo principio**:

> **una única verdad económica, registrada una vez, trazable de principio a fin y reutilizada para operar, contabilizar, cumplir, controlar y decidir.**
