# Fiscalidad

Lo que hace que las facturas sean **legales y correctas**. Crítico: una factura mal
hecha le crea un problema con Hacienda al cliente.

## Ticket y datos fiscales (revisado 10-sep-2026)

La simplificada admite el caso general hasta 400 € IVA incluido sin NIF/domicilio
del destinatario; el NIF del emisor sí es obligatorio. Una factura completa de
operación interior sujeta exige los datos del cliente, también si es particular.
Para deducir IVA con simplificada deben constar NIF/domicilio del destinatario y
cuota separada. El art. 4 contempla hasta 3.000 € en operaciones enumeradas,
incluidos ciertos servicios a domicilio, pero el producto no presume que toda
reforma cumple esa excepción: conserva el límite general hasta validación.
Fuentes: [AEAT](https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/facturacion-iva/tipos-factura.html),
[RD 1619/2012, arts. 4, 6 y 7](https://www.boe.es/eli/es/rd/2012/11/30/1619).

## IVA
- General **21%**, reducido **10%**, superreducido **4%** y tipo **0%**.
- Configurable por negocio (por defecto) y por factura. Implementado.
- Un tipo 0% no equivale por sí solo a una operación exenta. Las causas de exención,
  no sujeción y los identificadores fiscales extranjeros aún no forman parte del
  alcance validado del MVP y deben completarse antes de admitir esos casos.

## IRPF (retención)
- Autónomos que facturan **a empresas** suelen aplicar retención: **15%**
  (o **7%** los tres primeros años de actividad).
- A particulares: normalmente **0%**.
- Fórmula implementada: **Total = base + IVA − IRPF retenido**.
- Base, IVA, IRPF y total se redondean al céntimo con `Decimal` y
  `ROUND_HALF_UP`; no se usa el redondeo bancario de `float`.

## Verifactu / Ley Antifraude
- Los sistemas deben estar adaptados antes del **1-ene-2027** para contribuyentes
  del Impuesto sobre Sociedades y antes del **1-jul-2027** para el resto de
  obligados, incluidos autónomos con actividad económica. Antes es periodo de
  pruebas; confirmar siempre el caso concreto con asesoría fiscal.
- **Registro nativo construido**: alta y anulación inalterables, huella SHA-256
  encadenada, QR tributario, facturas rectificativas, eventos y XML según los
  esquemas AEAT.
- La migración 33 conserva la numeración única por negocio, separa series de
  facturas completas, simplificadas y rectificativas, y congela cabecera y líneas
  después de emitir. Cobros, comunicaciones y respuesta AEAT viven en ledgers y
  eventos separados; nunca reescriben la factura.
- La emisión es transaccional e idempotente: reserva la secuencia anual por negocio,
  congela los datos fiscales y crea registro, evento y outbox en la misma transacción.
  Se eliminó el antiguo atajo que admitía una numeración externa.
- Antes de generar o remitir se vuelve a comprobar la cadena. Un reloj que retrocede
  más de un minuto, una huella manipulada o un cambio de NIF después del primer
  registro se bloquean y dejan una anomalía operativa.
- La huella sigue el orden y formato del documento técnico AEAT 0.1.2; el QR sigue
  el documento técnico 0.5.0, mide 35 mm y usa corrección M.
- Algoritmo, tipo/versión de huella, versión de registro y URL de cotejo son
  configurables por entorno.
- **Remisión construida, no validada externamente**: cliente SOAP/mTLS, certificado
  PEM, respuesta estructurada y cola durable con bloqueo entre réplicas, backoff e
  idempotencia ante duplicados. Permanece desactivada
  mientras falten `VERIFACTU_CERT_PATH`, `VERIFACTU_KEY_PATH` o
  `VERIFACTU_AEAT_ENV`.
- El transporte fuerza TLS 1.2 o superior, limita la respuesta, admite clave PEM
  cifrada y elige el endpoint oficial de certificado ordinario o de sello. Un fallo
  SOAP se reintenta; si la AEAT confirma que un duplicado ya estaba aceptado, no se
  convierte en un falso rechazo.
- El estado comercial de la suscripción nunca pausa la remisión de registros fiscales
  ya generados. Bloquear el panel por impago y cumplir una obligación fiscal son
  responsabilidades distintas.
- La anulación exige escribir el número de factura, conserva el alta original,
  genera la cadena de huella oficial de anulación y usa su propia outbox durable.
  Por seguridad solo se permite sobre un alta aceptada por la AEAT.
- El 20-07-2026 se validaron localmente XML de alta F1, simplificada F2,
  rectificativa R1 y un mensaje combinado de alta + anulación contra los XSD
  oficiales publicados por la AEAT. Esto no sustituye la prueba mTLS real.
- Datos fiscales necesarios del negocio: NIF, dirección, nombre/razón social.
- También se debe configurar el NIF real del productor del software mediante
  `NOESIS_VERIFACTU_PRODUCER_NIF`; no existe un valor ficticio por defecto.

Fuentes técnicas:
- [Plazos oficiales de adaptación](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/nota-informativa-ampliacion-plazo-adaptacion-facturacion.html)
- [Esquemas y WSDL oficiales](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/informacion-tecnica/esquemas.html)
- [Algoritmo de huella AEAT](https://www.agenciatributaria.es/static_files/AEAT_Desarrolladores/EEDD/IVA/VERI-FACTU/Veri-Factu_especificaciones_huella_hash_registros.pdf)
- [Especificaciones QR AEAT](https://www.agenciatributaria.es/static_files/AEAT_Desarrolladores/EEDD/IVA/VERI-FACTU/DetalleEspecificacTecnCodigoQRfactura.pdf)
- [Descripción de servicios y XML AEAT](https://sede.agenciatributaria.gob.es/static_files/AEAT_Desarrolladores/EEDD/IVA/VERI-FACTU/Veri-Factu_Descripcion_SWeb.pdf)

## Pendiente
- Obtener certificado y clave, montar los PEM fuera de Git, configurar el NIF real
  del productor y validar primero `VERIFACTU_AEAT_ENV=pruebas`.
- Revisar aceptación, rechazo, errores, reintentos, CSV y trazabilidad con asesoría
  fiscal antes de pasar a producción. Pasos: [[Conectar-APIs]].
- Completar en preproducción la anulación ya construida y desarrollar/validar la
  subsanación de registros rechazados antes de declarar conformidad completa del
  SIF. El MVP emite altas F1/F2 y rectificativas R1-R5; no debe presentarse como
  certificado u homologado hasta esa validación, la declaración responsable y la
  auditoría fiscal externa.
- Completar y validar las causas fiscales de exención/no sujeción y los supuestos
  internacionales antes de permitirlos como operativa comercial.
- Los modelos 303/130 son estimaciones de apoyo ya construidas; no equivalen a
  presentación oficial ni sustituyen a la gestoría.
