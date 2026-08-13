# Tareas vivas

> Único listado vivo de pendientes. La fotografía verificable está en
> [`project-state.json`](project-state.json); planes y traspasos no duplican estados.

## P0 — publicar y pilotar con seguridad

- [ ] Recorrer en escritorio y móvil el alta recuperable del esquema 49 ya
  desplegada en el release `8730826a79ab`:
  salir y volver en cada paso, revisar la identidad visual de factura, comprobar que
  WhatsApp no aparece conectado antes del webhook, posponerlo voluntariamente y
  confirmar que Stripe devuelve a la puesta en marcha y al primer cliente. El flujo,
  la persistencia y los bloqueos están cubiertos; CI completo, migración histórica
  y humo PostgreSQL están verdes. Faltan Meta y Stripe reales.
- [ ] Validar visualmente en escritorio y móvil la nueva entrada `/acceso` ya
  desplegada: selección autónomo/empresa o gestoría, retorno entre accesos, login de
  ambos perfiles y solicitud profesional. HTTP, aislamiento y ausencia de
  autoasignación de empresas ya están verificados.
- [ ] Rotar `NOESIS_SECRET`, SMTP y cualquier credencial que haya aparecido en una
  captura, PDF o conversación; revocar la anterior y eliminar/redactar las copias
  compartidas. No reutilizar secretos sugeridos por una IA.
- [ ] El release `c63bf0e` y el esquema 46 ya están desplegados: CI completo y humo
  PostgreSQL verdes, `/health` identifica el release, `/ready` confirma 46 y la
  portada responde 200. Completar la comprobación de dominio canónico, cookies
  `__Host-`, hosts, logs sin query string, Google OAuth admin, panel CISO, bitácora
  encadenada, Home, modo consulta, ficha de proyecto y login de gestoría mediante
  el proxy real. Release/esquema, cabeceras, textos legales, alta cerrada y
  redirección 308 de `www` ya se comprobaron el 6-ago. El 7-ago se verificaron el
  nuevo release, esquema, CI, humo PostgreSQL, origen propio 303/origen externo 403
  y login/cartera/logout sintéticos de la gestoría demo. El founder confirmó después
  que Chrome ya entra y muestra la cartera/ficha con la prioridad
  `Sec-Fetch-Site: same-origin`. El espacio fiscal del esquema 41 ya se desplegó y
  `/ready` lo confirmó. Falta recorrer visualmente la separación nueva entre
  Resumen, Documentos, Impuestos, Períodos y Solicitudes, además de completar las
  demás pruebas autenticadas. El release `40d5645` con esquema 47 y MFA de gestoría
  ya está publicado: CI completo/PostgreSQL verdes, `/health` y `/ready` coherentes
  y portada, `/acceso` y `/gestoria/login` en 200. Falta activar y recorrer TOTP,
  anti-replay y recuperación con una cuenta profesional y un autenticador reales.
- [ ] La identidad legal ya está completada y publicada. Revisar aviso legal,
  privacidad, términos, DPA y fiscalidad con profesionales. Mantener
  `NOESIS_PUBLIC_SIGNUP_ENABLED=false` hasta cerrar toda esta lista P0.
- [ ] Validar en producción la puerta de apertura: con el alta cerrada, las cuentas
  existentes entran y una alta por contraseña o Google no crea cuenta; al abrirla,
  repetir prueba, contratación, preferencias, checkout, webhook, modo consulta y
  reactivación.
- [ ] Crear o actualizar en Stripe los productos **29/49/99 € + IVA**, enlazar sus
  seis `price_id` y probar en modo test dirección, NIF y `automatic_tax`; comprobar
  importe e IVA resultantes, Checkout sin activación prematura, `invoice.paid`,
  `trialing`, `incomplete`, `paused`, impago, cancelación, reactivación, eventos
  fuera de orden y portal de cliente antes de usar claves live. Verificar además
  con cuentas reales que Autónomo no puede usar Proyectos, Equipo, Gestoría ni
  Análisis avanzado y que Negocio/Premium sí pueden hacerlo por web, API, asistente,
  WhatsApp y portales. La máquina de estados y los permisos en servidor ya están
  construidos y desplegados; falta validarlos contra Stripe test.
- [ ] Meta real: validar el número central y al menos dos números comerciales de
  negocios distintos con el mismo token de sistema/activos concedidos a Noesis.
  Comprobar webhook firmado, coincidencia WABA + `phone_number_id`, mismo remitente
  aislado entre empresas, texto, audio, foto/PDF, opt-out, ventana de 24 horas,
  plantillas fuera de ventana, estados, reintentos, revocación y cuenta inactiva.
  El motor multicanal, la bandeja y el alta manual auditada desde administración ya
  están construidos; falta Embedded Signup para autoservicio y la prueba extremo a
  extremo con números reales.
- [ ] Activar y validar voz (Groq Whisper o faster-whisper local) y OCR
  con corpus real en castellano/catalán/inglés. La ruta privada de OCR ya incorpora
  Tesseract/pytesseract para imágenes y PDFium para PDF escaneado, y Railpack instala
  `cat/spa/eng`, prepara orientación/contraste/escala e informa los modelos presentes;
  falta comprobar el despliegue y medir precisión/tiempo. Sin esa validación,
  mantener las promesas públicas degradadas.
- [ ] Activar una vez `NOESIS_SEED_DEMO=true` en Railway, desplegar y recorrer los
  accesos reales de autónomo y gestoría y `/demo/cliente`. Confirmar que ambos
  negocios muestran datos completos y que cualquier escritura, envío o automatización
  queda bloqueada. Confirmar además en Documentos las carpetas de 1 ingreso,
  2 gastos, 1 ticket, 2 pendientes y 2 documentos en Otros. Después se puede volver
  a `false`: los registros persisten.
- [ ] Aprobar plantillas Meta para factura (`noesis_factura_lista`), cobro,
  presupuesto y cita; validar SÍ/NO, PDF/enlace privado y entrega desde el WhatsApp
  real del titular.
- [ ] Correo real por API HTTPS o SMTP: credenciales, dominio autenticado,
  invitaciones, facturas, avisos, reintentos de la outbox y entregabilidad. La cola
  durable y las dos vías de salida ya están construidas.
- [ ] Crear el cliente OAuth web de Google, registrar exactamente
  `https://bynoesis.com/auth/google/callback`, cargar `GOOGLE_OAUTH_CLIENT_ID`
  y `GOOGLE_OAUTH_CLIENT_SECRET` en producción y probar alta y acceso reales. El
  botón permanece oculto hasta que ambas credenciales existan para no prometer una
  función falsa.
- [ ] Certificado/entorno AEAT: autorización por obligado tributario, mTLS en pruebas,
  aceptación/rechazo/duplicado/CSV/reintentos, alta y anulación ya construidas,
  subsanación de rechazos, declaración
  responsable y validación con asesoría fiscal antes de producción.
- [ ] Ejecutar `noesis-doctor --strict` en producción y resolver todo bloqueo.
- [ ] Desplegar ClamAV en red privada, fijar `NOESIS_CLAMAV_REQUIRED=true` y probar
  archivo limpio, EICAR, caída y timeout sin almacenar el payload rechazado.
- [ ] Ejecutar `noesis-restore-check` y comprobar el simulacro semanal. Después,
  descargar una copia del bucket y restaurarla en infraestructura distinta,
  documentando RPO/RTO; la prueba local no demuestra recuperación ante caída total.
- [ ] Ejecutar un pentest autenticado externo y una revisión de privacidad/RGPD,
  fiscalidad y procedimiento de incidentes. El modelo interno y la puerta de salida
  están en [[Seguridad-operativa]]; una revisión propia no sustituye esta validación.
- [ ] Piloto acompañado con 3-5 autónomos durante dos cierres semanales.
- [ ] Medir activación hasta primer cobro, tiempo ahorrado, trabajos sin facturar,
  cobros recuperados, correcciones, coste por cuenta y retención.

Credenciales, callbacks, variables y criterios de aceptación: [[Conectar-APIs]].

## P1 — profundidad después del primer piloto

- [ ] SEO operativo: publicado y verificado el candidato del 13-ago, volver a inspeccionar
  `/autonomos`, `/gestorias` y `/precios` en Search Console, solicitar indexación y
  revisar durante 2-4 semanas páginas indexadas, consultas, impresiones, clics,
  CTR y Core Web Vitals. No crear valoraciones, casos de éxito ni datos
  `SoftwareApplication` hasta que existan evidencias reales. Mantener la medición
  propia sin cookies; añadir analítica externa solo mediante una nueva decisión.

- [x] Diagnóstico técnico por cuenta para soporte: solo metadatos, estados y
  recuentos; acceso exclusivo de administración, registrado en la bitácora y sin
  contenido operativo ni credenciales.
- [x] Puerta de intervención de soporte: autorización explícita creada por el
  titular, motivo, alcances, caducidad 1/4/24/72 h, revocación y eventos encadenados.
  Administración no puede autoconcedérsela ni suplantar al usuario.
- [ ] Habilitar una a una las correcciones de soporte que demuestre el piloto,
  comprobando el permiso efectivo y registrando antes/después. Los metadatos
  documentales ya permiten corregir tipo, estado, cliente, proyecto y nota con
  permiso transaccional, aislamiento y bloqueo de facturas emitidas. Configuración
  ya limita la intervención a perfil, idioma/explicación y apariencia documental
  futura, dejando identidad fiscal, pagos, suscripción, integraciones y
  automatizaciones fuera de la firma. Falta validar ambos recorridos con un titular
  real y habilitar otras correcciones solo si el piloto las demuestra. No crear un
  editor universal.
- [x] Facturas emitidas: corrección guiada mediante rectificativa por diferencias,
  original inmutable, un solo borrador pendiente, revisión antes de emitir y causa
  R5 limitada a facturas simplificadas F2.
- [ ] Validar con asesoría y XSD AEAT si el piloto necesita rectificación por
  sustitución (`S`) y sus importes rectificados; hasta entonces Noesis la rechaza
  expresamente y no inventa un registro fiscal incompleto.
- [ ] Evaluar servicio privado y proveedor compatible con el mismo corpus en
  castellano/catalán: herramientas, calidad, latencia, coste, concurrencia y caídas.
- [ ] Documentos: deduplicación, búsqueda, PDF digital y OCR acotado de PDF escaneado
  trilingüe están construidos; faltan HEIC, extracción fiable de líneas y corrección
  masiva, y validar el conjunto con corpus real.
- [x] Perfil documental sin maquetador libre: tres plantillas probadas, color, logo
  saneado, pie textual, distintivo gráfico con tamaño/alineación/alcance y vista
  previa; cada factura emitida conserva una versión visual reutilizable. Incluye
  condiciones y validez, presupuesto PDF, portal aislado y decisión con evidencia
  seudónima antes de preparar la factura borrador. Falta validación visual con los
  distintivos reales que usarán los primeros clientes.
- [x] Archivo del titular por años, trimestres y tipos con el mismo criterio que la
  gestoría, entrada rápida horizontal, carpetas, filtros de estado, búsqueda y vista
  previa privada acotada bajo demanda, con distribución responsive para móvil.
- [ ] Calendario: validar la suscripción ICS en Google/Apple/Outlook; después decidir
  si el piloto necesita sincronización bidireccional OAuth y recurrentes.
- [ ] Conciliación: validar CSV de bancos reales; dejar PSD2/API bancaria y cobro por
  enlace para después del piloto. Ningún movimiento se confirma automáticamente.
- [ ] Correo: panel interno de detalle/reejecución manual si los avisos agregados de
  la outbox resultan insuficientes durante el piloto.
- [ ] Equipo: validar con varios trabajadores reales el canal central, offline,
  ausencias, permisos por rol y el resumen al titular. Costes, justificantes, dudas,
  bloqueos, revisión previa y presupuesto limitado al proyecto asignado ya están
  construidos; falta medir claridad, errores de asociación y carga de revisión.
- [x] Gestoría con cuenta profesional, invitaciones de un solo uso, varias empresas,
  acceso revocable, revisión y previsualización por documento, filtros, períodos,
  perfil fiscal y borradores explicables sin permisos de presentación o dinero.
- [ ] Gestoría: validar con un despacho real el cálculo previo de 303/130/111/115 y
  candidatos 347; definir deducibilidad, prorrata, regímenes especiales y los datos
  que faltan para 131/349/200/202 antes de prometer confección completa.
- [ ] Canal de gestorías: aprobar atribución, descuento para el cliente, comisión,
  duración, liquidación, devoluciones y fiscalidad del incentivo. El producto solo
  muestra clientes conectados hasta que el founder apruebe esas condiciones.
- [x] Gestoría: MFA TOTP opcional, reto tras contraseña, anti-replay, ocho códigos de
  recuperación de un solo uso y reconfiguración protegida sin semillas reversibles
  ni códigos en la cookie de sesión.
- [ ] Gestoría: recuperación de contraseña por correo, passkeys, roles finos y
  piloto real con un despacho antes de abrir el acceso a terceros.
- [ ] Observabilidad por negocio para IA, extracción, colas, latencia, errores,
  correcciones y coste.
- [x] Libro CFO interno por mes: costes reales, previsiones y ajustes append-only;
  contribución, margen observado y coste por cuenta de pago sin inventar gastos.
- [ ] Cargar facturas reales de Railway, proveedores, seguridad, correo, Meta,
  Stripe y horas de soporte durante el piloto; conciliar MRR comprometido con cobros
  reales y añadir CAC/churn cuando exista una muestra válida.
- [ ] Eliminar `unsafe-inline` de la CSP efectiva tras migrar scripts/estilos inline;
  mientras tanto observar la política estricta en report-only sin romper la UI.
- [ ] Evaluar passkeys y permisos finos para gestoría antes de abrir acceso a
  terceros; valorar RLS PostgreSQL y KMS/cifrado de campos tras el piloto según el
  riesgo y la complejidad observados. El antivirus privado ya tiene adaptador y
  modo de fallo cerrado; falta desplegar el daemon.
- [ ] Revisar cada pantalla con evidencia visual tras estabilizar el diseño; su
  jerarquía debe responder a su tarea, no copiar la de otra sección.
- [ ] Fiscalidad ampliada: exenciones E1-E8, no sujeción N1/N2, inversión del sujeto
  pasivo, identificación extranjera y divisas, solo después de validarlas con
  asesoría y XSD/validaciones AEAT. Hasta entonces el 0% es tipo cero, no exención.

## P2 — solo con retención demostrada

- Personalización por sector, rutas, hitos, PWA profunda, inventario, nóminas y
  recepcionista de voz, sujetos a demanda real y unit economics sostenibles.

## Límites permanentes

- Noesis prepara; el autónomo confirma pagos, transferencias, impuestos, emisiones,
  envíos sensibles y borrados irreversibles.
- Todo aprendizaje distingue observado de confirmado y es visible y corregible.
- Toda operación filtra por `business_id`.
- El cerebro local sigue disponible aunque una integración falle o se desactive.
