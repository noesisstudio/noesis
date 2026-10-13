# CRM de captación: la lista, la hoja de Google y la página visual

*5 de octubre de 2026. Guía de uso y de mantenimiento de `/admin/crm`. El método de
captación está en [`Ruta-a-5000-autonomos`](../06-negocio-y-finanzas/Ruta-a-5000-autonomos.html)
y de dónde salen los nombres en [`Lista-de-captacion`](../06-negocio-y-finanzas/Lista-de-captacion.md).*

Es el CRM **de Bynoesis** (a quién perseguimos nosotros), no el del autónomo
(`/b/<id>/crm`). Solo entra un administrador.

## Qué se ve

Arriba, **a quién miras** (Todos, Autónomos, Gestorías…): todo lo demás se calcula
sobre esa vista. Debajo, los **apartados** del panel, uno cada vez:

| Apartado | Qué hay |
|---|---|
| Resumen | El parte, lo que toca ahora, las cifras, los tres gráficos y el objetivo con autónomos |
| Tablero | Una columna por estado, con tarjetas que se arrastran |
| Hoy y tanda | Los seguimientos vencidos y la siguiente tanda de correos |
| La lista | Buscador, filtros y todos los contactos de 50 en 50 |
| Ficha | La de quien abras: historial, guion y anotar lo que ha pasado |
| Hoja de Google | Conectar, leer ahora y la fórmula para ver el CRM en la hoja |
| Añadir gente | Pegar una lista, apuntar a uno y dónde buscar |

Cada apartado tiene su dirección (`/admin/crm#tablero`, `#tanda`, `#hoja`…), así que
se puede guardar en marcadores. Sin JavaScript la página se lee entera, seguida.

En detalle:

1. **El parte**: una frase con lo que toca, y debajo tres accesos a lo urgente.
2. **A quién miras**, ya explicado.
3. **De un vistazo**: cuatro cifras y tres gráficos.
   - *El embudo*: hasta dónde ha llegado cada contacto (en la lista → contactados →
     han respondido → en piloto → clientes). Quien contestó y luego se durmió sigue
     contando como que contestó.
   - *Tu ritmo*: contactos anotados cada semana, las últimas doce.
   - *Por provincia*: dónde está la lista y cuánto llevas hecho en cada zona.
   Cada gráfico tiene debajo «Ver como tabla» con los mismos números.
4. **Tablero**: una columna por estado. Arrastrar una tarjeta a otra columna cambia
   su estado y deja un apunte en su historial.
5. **El objetivo con autónomos** (40 nombres, 20 conversaciones, 5 pilotos, 2 cartas).
   Solo cuenta autónomos: las gestorías son un canal.
6. **Hoy**: los seguimientos vencidos, de diez en diez.
7. **Siguiente tanda**: los diez siguientes sin escribir de una provincia, primero los
   que tienen el correo comprobado, con el asunto aprobado y un botón para copiar cada
   dirección. Al terminar se marcan y pasan a «Contactado»; vuelven a la semana.
8. **La lista**: buscador y filtros por estado y provincia, de 50 en 50.
9. **Hoja de Google**, **Añadir gente** y **Dónde buscar**.

## Conectar la hoja «Leads»

1. Abre la hoja en la pestaña de la lista («Gestorias»).
2. **Compartir → Acceso general → Cualquier persona con el enlace → Lector.**
3. Copia la dirección del navegador (lleva `gid=…`, que es la pestaña) y pégala en
   *Hoja de Google → Conectar una pestaña*.

A partir de ahí se lee sola **cada mañana a las 7:30**, y cuando pulses «Leer ahora».

| Columna de la hoja | Qué hace aquí |
|---|---|
| EMPRESA | Nombre de la ficha |
| DIRECCION | Dirección; del código postal salen la población y la provincia si faltan |
| TELEFONO, EMAIL (o «EMAIL IA»), PAGINA WEB, PROVINCIA | Datos de contacto |
| VERIFICACION CORREO | Decide quién va primero en la tanda |
| ESTADO y ENVIADO (si la añades) | Si pone «enviado», «respondido», «reunión», «descartado» o «no contactar», la ficha avanza a ese punto. «WEB ACTIVA» no mueve a nadie |

El orden de las columnas da igual. Las que no conoce las ignora y lo dice.

**Quién manda en qué.** La hoja manda en los datos de contacto: si corriges un correo
allí, aquí se corrige. El CRM manda en el estado, el historial, la nota y la baja: una
lectura nunca los pisa, y la hoja solo puede hacer **avanzar** a alguien, nunca
devolverlo atrás.

**Bajas y borrados.** Quien pidió no ser contactado no se toca aunque siga en la
hoja. Quien pidió que se le borrase no vuelve a entrar: se guarda una huella de su
correo y su teléfono (no el dato) para reconocerlo. Bórralo también de la hoja.

**Si conectas la pestaña equivocada**: *Desconectar* y marca «Quitar también los
contactos que trajo y con los que no he hecho nada».

## Ver el estado del CRM dentro de la hoja

En *Hoja de Google → Crear la dirección* sale una fórmula
`=IMPORTDATA("https://…/admin/crm/feed/….csv")`. Pégala en la celda A1 de una pestaña
nueva llamada «CRM»: Google la refresca sola cada hora con el estado, el último
contacto y el siguiente paso de cada uno. Para verlo en la propia lista, añade una
columna con `=SI.ERROR(BUSCARV(E2;CRM!B:F;5;FALSO);"")`, donde E es la del correo.

- La fórmula se enseña **una vez**. En la base solo queda la huella de la clave.
- Quien tenga esa dirección puede leer la tabla: solo se pega en tu hoja. «Crear
  otra» anula la anterior; «Anular» la cierra.
- No lleva las notas ni lo que te dijeron: eso se queda en el CRM.

## La demo con datos inventados

Para enseñar el panel sin la hoja real ni una sesión:

```bash
python -m noesis.crm.demo carpeta/
```

Monta una base temporal, la llena de 1.021 gestorías y 6 autónomos **inventados**
(correos `.example`, teléfonos imposibles), pide la página a la propia app y la
guarda en archivos que se abren solos: `index.html`, `gestorias.html`,
`autonomos.html` y `fichas.json`. Es la página de verdad, no una copia: si la página
cambia, se regenera y cambia con ella. `static/crm/demo.js` hace de servidor (enseña
lo que pasaría y dice que no se guarda); la app nunca carga ese archivo.

Nunca escribe en la base configurada, y `demo.sembrar()` se niega si la base es
PostgreSQL o ya tiene contactos.

## Lo que no hace, a propósito

- **No escribe en tu hoja.** Así un fallo nuestro no puede pisar una celda tuya.
- **No envía correos.** Prepara la tanda y apunta lo que tú envías.
- **No comprueba que un buzón exista.** Usa lo que pone en VERIFICACION CORREO.

## Dónde está el código

Todo en `src/noesis/crm/` (ver su `__init__.py`): `hoja.py` entiende las columnas,
`google.py` baja la pestaña, `sincronizar.py` la lleva a las fichas y sirve la tabla
para la hoja, `panel.py` calcula gráficos, tablero y tanda, `rutas.py` son las rutas,
`esquema.py` la migración 74 y `demo.py` genera la demo. Plantillas en `web/templates/crm/`, estilos y script en
`web/static/crm/`, pruebas en `tests/crm/` y `tests/test_crm_captacion.py`. Los
estados y guiones siguen en `sales.py`; las fichas, en `db.py`.

## Si algo falla

| Síntoma | Dónde mirar |
|---|---|
| «Google pide iniciar sesión» | La hoja no está compartida por enlace (paso 2) |
| «No encuentro una columna de nombre…» | El enlace apunta a otra pestaña: cópialo con la buena abierta |
| No se ha leído esta mañana | La tarjeta de la hoja dice la última lectura y el motivo del fallo; el turno es `crm-hojas:AAAA-MM-DD` en `scheduled_job_runs` |
| La pestaña «CRM» de la hoja da error | La dirección se anuló o se creó otra: genera una nueva y pega la fórmula |
| Alguien aparece dos veces | Se cruza por correo, luego teléfono, luego nombre; si cambiaron los tres a la vez, es otra persona para el sistema: borra la que sobra |
