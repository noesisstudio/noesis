# Demostración comercial dentro de Noesis

La demostración no es una web paralela ni una maqueta. Son cuentas y portales
reales dentro del mismo SaaS, con la misma base de datos, cálculos, rutas,
plantillas y permisos que utiliza un cliente. Solo cambian dos cosas: todos los
datos son ficticios y las empresas están bloqueadas en servidor como **solo
lectura**.

## Accesos que se enseñan

| Rol | Entrada | Usuario | Contraseña |
|---|---|---|---|
| Autónomo | `/login` | `demo.autonomo@bynoesis.com` | `NoesisDemo2026!` |
| Gestoría | `/gestoria/login` | `demo.gestoria@bynoesis.com` | `NoesisDemo2026!` |
| Cliente final | `/demo/cliente` | Enlace privado, sin contraseña | No aplica |

La cuenta del autónomo es **Reformas y Fontanería Delta SL · Demo**. Incluye
clientes, contactos, catálogo, proveedores, facturas recibidas, facturas emitidas
en distintos estados, cobros, gastos históricos, gráficas, CRM, equipo, trabajos,
un proyecto con margen/costes/horas/tareas, documentos y solicitudes de gestoría.

El portal de cliente pertenece a **Comunidad Aragón 121** y muestra sus
presupuestos y facturas reales dentro del escenario. La cuenta de **Gestoría
Mirall · Demo** puede recorrer la empresa principal y **Electricidad Montseny SL ·
Demo**, de modo que la cartera multiempresa no se presenta vacía.

## Activación en Railway

1. Añadir temporalmente la variable `NOESIS_SEED_DEMO=true` al servicio web.
2. Desplegar o reiniciar el servicio. El arranque crea los registros solo si no
   existen y nunca reinicia la base completa.
3. Entrar por las tres rutas de la tabla y revisar la navegación.
4. Confirmar que las páginas muestran la etiqueta «Demo · solo lectura» y que un
   intento de cambio devuelve el aviso de demostración, sin ejecutarse.
5. Volver a poner `NOESIS_SEED_DEMO=false` si no se quiere ejecutar la comprobación
   de siembra en cada arranque. Las cuentas y sus datos permanecen en PostgreSQL.

También puede prepararse en local con:

```bash
python -m noesis.demo
```

El comando imprime los dos accesos y el enlace privado generado para el cliente.

## Límites de seguridad

- Las empresas demo tienen `businesses.is_demo=true` (esquema 40).
- El modo de solo lectura se decide en servidor, no ocultando botones.
- Se bloquean altas/cambios, emisión fiscal, pagos, correo, WhatsApp,
  automatizaciones y acciones del asistente.
- La gestoría puede descargar un paquete ficticio para enseñarlo, pero esa descarga
  no registra una entrega ni dispara comunicaciones.
- Los documentos incluidos se pueden abrir: son PDF/JPEG válidos y contienen solo
  contenido ficticio.
- Nunca se deben copiar datos reales dentro de estas cuentas ni reutilizar la
  contraseña de la demo para cuentas de producción.

## Comprobación rápida antes de una reunión

1. Abrir el autónomo y revisar Inicio, Trabajos, Proyectos, Clientes, Dinero,
   Facturas, Equipo y Documentos.
2. Abrir la gestoría en una ventana privada, comprobar que hay dos empresas y entrar
   al detalle de la principal.
3. Descargar un paquete mensual desde la gestoría y abrirlo.
4. Abrir `/demo/cliente` en otra ventana y enseñar presupuesto, factura y PDF.
5. No presentar una función externa como validada si depende todavía de Meta,
   Stripe, correo, voz, certificado AEAT o de una prueba real de OCR.
