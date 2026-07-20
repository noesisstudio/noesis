# Roadmap

> Dirección estable por etapas. No contiene números vivos de migración, tests,
> commits o despliegues. La verdad verificable está en
> [`project-state.json`](project-state.json) y el trabajo inmediato en
> [[Tareas-vivas]].

Principio rector: **publicar, conectar y pilotar antes de ampliar alcance**.

## Etapa A — núcleo construido

- SaaS multiempresa con sesión, aislamiento por `business_id`, alta guiada,
  suscripción y modo consulta cuando la cuenta no está activa.
- Flujo cliente → presupuesto → trabajo/proyecto → horas y costes → factura → cobro.
- Documentos inteligentes por web y WhatsApp, con clasificación explicable y
  confirmación humana antes de crear efectos contables.
- Facturas recibidas, proveedores, catálogo, CRM, equipo/fichaje, gestoría por
  portal privado, P&G y proyectos con rentabilidad.
- Asistente persistente y contextual: reglas locales, compositor interno y respaldos
  de IA opcionales sin perder el servicio local.
- Facturación nativa Veri*Factu, colas durables de WhatsApp/correo, conciliación CSV,
  feed ICS privado y portales de cliente, trabajador y gestoría.
- Landing, alta por prueba/contratación, modalidad mensual/anual y Google OAuth
  oculto hasta disponer de credenciales válidas.

## Etapa B — P0: producción verificable y piloto

1. Desplegar el `main` actual, aplicar migraciones y repetir `/ready`, doctor y
   recorridos críticos.
2. Conectar SMTP, Google OAuth, Stripe, Meta WhatsApp y al menos un respaldo de IA
   según [[Conectar-APIs]].
3. Resolver el tratamiento de IVA de Stripe antes de cobros live.
4. Configurar copia externa, restaurarla de verdad y medir recuperación.
5. Validar AEAT en pruebas con certificado y revisión fiscal externa.
6. Completar auditoría externa de seguridad, privacidad, fiscalidad e incidentes.
7. Pilotar con 3-5 autónomos durante dos cierres semanales y medir activación hasta
   primer cobro, tiempo ahorrado, errores, coste y retención.

La salida de esta etapa no es «más pantallas»: es evidencia de que un negocio real
puede entrar, trabajar, facturar, cobrar y entregar papeles sin asistencia técnica.

## Etapa C — P1: profundidad guiada por el piloto

- Comparar servicio privado, proveedor compatible y fallback con corpus ES/CA:
  herramientas, calidad, latencia, coste, concurrencia y recuperación ante fallos.
- Endurecer documentos con duplicados, HEIC, escaneados, líneas, búsqueda y
  corrección masiva según errores reales.
- Probar ICS y CSV bancarios reales antes de plantear OAuth bidireccional o PSD2.
- Equipo con varios trabajadores, offline, ausencias y permisos finos.
- Gestoría con cuentas, MFA, varias empresas y revisión por documento si el portal
  por enlace se queda corto.
- Observabilidad por negocio de colas, IA, extracción, latencia, correcciones y coste.
- Revisar cada pantalla por su tarea concreta; no imponer KPIs ni estructuras iguales.

## Etapa D — P2: expansión con retención demostrada

- Personalización por patrones de sector, rutas, hitos y automatizaciones específicas.
- Calendario bidireccional, PSD2 y cobro por enlace solo con demanda y permisos claros.
- PWA profunda, inventario avanzado, nóminas e integraciones contables adicionales.
- Recepcionista telefónico, minutos incluidos y add-on solo con unit economics medidos.
- Nuevos canales como Telegram únicamente si aportan adopción o retención real.

## Límites permanentes

- Noesis prepara y propone; el titular autoriza dinero, fiscalidad, emisiones,
  mensajes sensibles y borrados irreversibles.
- Lo observado se distingue de lo confirmado; la memoria es visible y corregible.
- Ninguna integración externa puede apagar el núcleo local.
- Construido, fusionado, desplegado y validado son estados distintos.
