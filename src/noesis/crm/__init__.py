"""CRM de captación de Bynoesis: la lista, la hoja de Google y la página visual.

Es el CRM **de la empresa** (a quién perseguimos nosotros), no el del autónomo,
y por eso nada de aquí lleva `business_id`. Todo vive detrás de `/admin`.

Qué hay en la carpeta:

- `zonas.py`       provincias, lengua del guion y correo comprobado
- `hoja.py`        entender una pestaña de la hoja (columnas, filas, estado)
- `google.py`      bajar la pestaña de Google Sheets por su enlace (solo lectura)
- `sincronizar.py` hojas conectadas, llevar las filas a las fichas y el enlace
                   por el que la hoja lee el estado del CRM
- `panel.py`       los números de los gráficos, el tablero, el filtro y la tanda
- `rutas.py`       las rutas de `/admin/crm` y la dirección que lee la hoja
- `esquema.py`     la migración 74
- `demo.py`        la demo con datos inventados (`python -m noesis.crm.demo`)

El embudo, los estados y los guiones siguen en `noesis/sales.py`, y las fichas y
su historial en `noesis/db.py` (`sales_prospects`, `sales_touches`). La plantilla
y sus trozos están en `web/templates/crm/`; los estilos y el script, en
`web/static/crm/`. La guía de uso es `docs/crm/README.md`.

Este archivo no importa nada a propósito: `sales.py` usa `crm.zonas`, y cargar
aquí el resto crearía un círculo.
"""
