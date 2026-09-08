# Administración organizada — candidato local

## Objetivo

Separar el control de Bynoesis de los datos privados de sus clientes y permitir
identificar dónde está el operador, qué está viendo y qué puede hacer.

## Organización

| Apartado | Finalidad |
|---|---|
| Resumen | Prioridades, solicitudes pendientes y seis indicadores del servicio |
| Cuentas | Localizar negocios y gestionar su acceso |
| Captación | Solicitudes, visitas y evolución comercial |
| Consumo y costes | Uso técnico, estimaciones y libro de costes |
| Operaciones | Integraciones, seguridad, entregas y copias |
| Privacidad | Solicitudes de derechos y seguimiento |

Cada ficha separa Resumen, Consumo, Acceso y plan, WhatsApp, Entregas y Soporte.
El teléfono del titular permanece distinto del canal comercial. Los permisos,
formularios y restricciones existentes se mantienen. No se ha modificado el
enlace de teléfonos ni activado soporte sobre cuentas reales.

Navegación con sección activa, encabezado, migas, enlaces profundos compatibles
y foco de teclado. En móvil usa dos columnas de navegación y tarjetas apiladas.
Sin JavaScript, todos los apartados siguen disponibles. No se descarga menos
información del servidor: esta organización no equivale a carga diferida.

## Referentes consultados

Se aplica separación por tarea, no una copia de marca ni una auditoría de sus paneles privados:

- [Stripe Dashboard](https://docs.stripe.com/dashboard/basics?locale=en-GB): navegación y gestión de clientes.
- [Intercom Workspace](https://www.intercom.com/help/en/articles/15432088-your-workspace-settings): configuración separada por equipos, canales y seguridad.

## Avances técnicos acotados

- `GET /api/{business_id}/invoices`: `client_id`, `status`, `limit` (1–200) y
  `offset` opcionales. Sin parámetros conserva el listado anterior. El portal
  del cliente filtra sus facturas en SQL. Páginas con desempate estable por ID;
  no son un snapshot frente a escrituras concurrentes.
- `NOESIS_COST_USD_TO_EUR`: positivo y finito, 0,92 por defecto para conservar
  estimaciones anteriores. No afecta importes de facturas, impuestos ni cobros.
- CSS/JS administrativos incluidos en la versión de recursos para invalidar caché.

## Límites y revisión

No hay nuevas credenciales, migraciones, push ni despliegue. Siguen pendientes la
cola duradera de media, roles administrativos granulares, contexto documental,
conciliación de costes, pruebas reales de proveedores, Postgres y Safari físico.
La suite y evidencias locales se detallan en `Registro-QA.md`.

Tras fetch, `origin/main` sigue en `f8df1bce30e8145b35e582cb3319885efc8085af`.
No se ha encontrado el nuevo commit de teléfono mencionado; hace falta su SHA o
rama para revisar ese cambio específico. No se ha sobrescrito trabajo del socio.

Rollback: revertir únicamente este diff de navegación, consulta y configuración,
conservando cambios previos del árbol. Sin cambios de esquema ni borrado de datos.
