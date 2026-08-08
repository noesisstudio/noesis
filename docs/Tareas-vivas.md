# Tareas vivas

> Único listado vivo de pendientes. La fotografía verificable está en
> [`project-state.json`](project-state.json); planes y traspasos no duplican estados.

## P0 — publicar y pilotar con seguridad

- [ ] Desplegar y validar visualmente en escritorio y móvil la nueva entrada
  `/acceso`: selección autónomo/empresa o gestoría, retorno entre accesos, login de
  ambos perfiles y solicitud profesional. Confirmar que una solicitud de gestoría
  no crea cuenta ni concede acceso a ninguna empresa.
- [ ] Rotar `NOESIS_SECRET`, SMTP y cualquier credencial que haya aparecido en una
  captura, PDF o conversación; revocar la anterior y eliminar/redactar las copias
  compartidas. No reutilizar secretos sugeridos por una IA.
- [ ] Desplegar el `main` actual, aplicar la migración indicada en
  `project-state.json` y confirmar que `/health` devuelve el release esperado y
  `/ready` la migración vigente; comprobar además dominio canónico, cookies
  `__Host-`, hosts, logs sin query string, Google OAuth admin, panel CISO, bitácora
  encadenada, Home, modo consulta, ficha de proyecto y login de gestoría mediante
  el proxy real. Release/esquema, cabeceras, textos legales, alta cerrada y
  redirección 308 de `www` ya se comprobaron el 6-ago. El 7-ago se verificaron el
  nuevo release, esquema, CI, humo PostgreSQL, origen propio 303/origen externo 403
  y login/cartera/logout sintéticos de la gestoría demo. El founder confirmó después
  que Chrome ya entra y muestra la cartera/ficha con la prioridad
  `Sec-Fetch-Site: same-origin`. El espacio fiscal del esquema 41 ya se desplegó y
  `/ready` lo confirmó. Falta desplegar y recorrer visualmente la separación nueva
  entre Resumen, Documentos, Impuestos, Períodos y Solicitudes, además de completar
  las demás pruebas autenticadas.
- [ ] Completar `NOESIS_LEGAL_NAME`, `NOESIS_LEGAL_NIF`,
  `NOESIS_LEGAL_ADDRESS` y `NOESIS_LEGAL_EMAIL`; revisar aviso legal, privacidad,
  términos, DPA y fiscalidad con profesionales. Mantener
  `NOESIS_PUBLIC_SIGNUP_ENABLED=false` hasta cerrar toda esta lista P0.
- [ ] Validar en producción la puerta de apertura: con el alta cerrada, las cuentas
  existentes entran y una alta por contraseña o Google no crea cuenta; al abrirla,
  repetir prueba, contratación, preferencias, checkout, webhook, modo consulta y
  reactivación.
- [ ] Crear o actualizar en Stripe los productos **29/49/99 € + IVA**, enlazar sus
  seis `price_id` y probar en modo test dirección, NIF y `automatic_tax`; comprobar
  importe e IVA resultantes, checkout, webhook, impago, reactivación y portal de
  cliente antes de usar claves live.
- [ ] Meta real: número, webhook firmado, texto, audio, foto/PDF, plantillas, estados,
  reintentos y bloqueo de cuenta inactiva.
- [ ] Activar y validar voz (Groq Whisper o faster-whisper local) y OCR
  con corpus real en castellano/catalán. La ruta privada de OCR ya incorpora
  Tesseract/pytesseract para imágenes y PDFium para PDF escaneado, y Railpack instala
  los idiomas `spa/eng`; falta comprobar el despliegue y medir precisión/tiempo. Sin
  esa validación, mantener las promesas públicas degradadas.
- [ ] Activar una vez `NOESIS_SEED_DEMO=true` en Railway, desplegar y recorrer los
  accesos reales de autónomo y gestoría y `/demo/cliente`. Confirmar que ambos
  negocios muestran datos completos y que cualquier escritura, envío o automatización
  queda bloqueada. Después se puede volver a `false`: los registros persisten.
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

- [ ] Evaluar servicio privado y proveedor compatible con el mismo corpus en
  castellano/catalán: herramientas, calidad, latencia, coste, concurrencia y caídas.
- [ ] Documentos: deduplicación, búsqueda, PDF digital y OCR acotado de PDF escaneado
  están construidos; faltan HEIC, extracción fiable de líneas y corrección masiva,
  y validar el conjunto con corpus real.
- [ ] Calendario: validar la suscripción ICS en Google/Apple/Outlook; después decidir
  si el piloto necesita sincronización bidireccional OAuth y recurrentes.
- [ ] Conciliación: validar CSV de bancos reales; dejar PSD2/API bancaria y cobro por
  enlace para después del piloto. Ningún movimiento se confirma automáticamente.
- [ ] Correo: panel interno de detalle/reejecución manual si los avisos agregados de
  la outbox resultan insuficientes durante el piloto.
- [ ] Equipo: varios trabajadores reales, offline, ausencias y permisos finos.
- [x] Gestoría con cuenta profesional, invitaciones de un solo uso, varias empresas,
  acceso revocable, revisión y previsualización por documento, filtros, períodos,
  perfil fiscal y borradores explicables sin permisos de presentación o dinero.
- [ ] Gestoría: validar con un despacho real el cálculo previo de 303/130/111/115 y
  candidatos 347; definir deducibilidad, prorrata, regímenes especiales y los datos
  que faltan para 131/349/200/202 antes de prometer confección completa.
- [ ] Canal de gestorías: aprobar atribución, descuento para el cliente, comisión,
  duración, liquidación, devoluciones y fiscalidad del incentivo. El producto solo
  muestra clientes conectados hasta que el founder apruebe esas condiciones.
- [ ] Gestoría: MFA/passkeys, recuperación de contraseña, roles finos y piloto real
  con un despacho antes de abrir el acceso a terceros.
- [ ] Observabilidad por negocio para IA, extracción, colas, latencia, errores,
  correcciones y coste.
- [ ] Eliminar `unsafe-inline` de la CSP efectiva tras migrar scripts/estilos inline;
  mientras tanto observar la política estricta en report-only sin romper la UI.
- [ ] Evaluar MFA/passkeys y permisos finos para gestoría antes de abrir acceso a
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
