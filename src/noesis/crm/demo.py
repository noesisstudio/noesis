"""Demo del CRM con datos inventados: la página de verdad, sin servidor.

Para enseñar el panel sin conectar la hoja real ni abrir una sesión, este módulo
monta una base temporal, la llena de gestorías y autónomos **inventados**, pide
la página a la app como la pediría un administrador y la guarda en archivos que
se abren solos: estilos y script dentro, y `static/crm/demo.js` haciendo de
servidor.

Lo que se ve es exactamente `/admin/crm`: mismas plantillas, mismos cálculos de
`panel.py`. Si la página cambia, la demo se regenera y cambia con ella.

    python -m noesis.crm.demo carpeta/

Nunca toca la base configurada: `construir` trabaja siempre sobre una carpeta
temporal, y `sembrar` se niega a escribir en una base con Postgres o con
contactos ya dentro.
"""
from __future__ import annotations

import base64
import json
import random
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from .. import config, db, sales
from . import sincronizar

ENLACE_INVENTADO = ("https://docs.google.com/spreadsheets/d/"
                    "1DEMOdemoDEMOdemoDEMOdemoDEMOdemoDEMOdemo00/edit#gid=5")
VISTAS = {"index.html": "", "gestorias.html": "gestoria",
          "autonomos.html": "autonomo"}
# provincia: (prefijo telefónico, poblaciones, cuántas gestorías)
_ZONAS = {
    "Barcelona": ("93", ("Barcelona", "Terrassa", "Sabadell", "Manresa", "Vic",
                         "Mataró", "Granollers", "Igualada"), 320),
    "Lleida": ("973", ("Lleida", "Balaguer", "Tàrrega", "Mollerussa",
                       "Cervera", "La Seu d'Urgell"), 150),
    "Zaragoza": ("976", ("Zaragoza", "Calatayud", "Ejea de los Caballeros",
                         "Utebo"), 140),
    "Girona": ("972", ("Girona", "Figueres", "Olot", "Blanes", "Palafrugell"),
               120),
    "Tarragona": ("977", ("Tarragona", "Reus", "Valls", "Tortosa", "Cambrils"),
                  110),
    "Huesca": ("974", ("Huesca", "Barbastro", "Monzón", "Fraga", "Jaca"), 60),
    "Madrid": ("91", ("Madrid", "Alcalá de Henares", "Getafe"), 40),
    "Teruel": ("978", ("Teruel", "Alcañiz"), 30),
    "Valencia": ("96", ("València", "Gandia", "Sagunt"), 25),
    "Navarra": ("948", ("Pamplona", "Tudela"), 12),
    "La Rioja": ("941", ("Logroño", "Calahorra"), 8),
    "Castellón": ("964", ("Castelló de la Plana", "Vila-real"), 6),
}
_CP = {"Barcelona": "08", "Lleida": "25", "Zaragoza": "50", "Girona": "17",
       "Tarragona": "43", "Huesca": "22", "Madrid": "28", "Teruel": "44",
       "Valencia": "46", "Navarra": "31", "La Rioja": "26", "Castellón": "12"}
_CATALANAS = ("Barcelona", "Lleida", "Girona", "Tarragona")
_APELLIDOS_CA = ("Pons", "Riera", "Vila", "Soler", "Mas", "Ferrer", "Puig",
                 "Roca", "Serra", "Font", "Costa", "Bosch", "Camps", "Vidal",
                 "Molins", "Sala", "Pujol", "Casals", "Esteve", "Torrent")
_APELLIDOS_ES = ("Lacasa", "Gracia", "Sanz", "Navarro", "Marín", "Royo", "Abad",
                 "Laborda", "Bernal", "Aznar", "Pardo", "Gil", "Lahoz", "Blasco",
                 "Ferrando", "Mur", "Ibáñez", "Cebrián", "Otal", "Villar")
_AUTONOMOS = (
    ("Jordi Mas", "lampista", "Palafrugell", "cita", "llamada",
     "Café el jueves a las 8"),
    ("Anna Soler", "electricista", "Begur", "hablado", "cafe",
     "Hace los presupuestos el domingo por la noche"),
    ("Pere Camps", "fuster", "Lleida", "piloto", "cafe",
     "Empieza el piloto con dos obras"),
    ("Marc Vidal", "pintor", "Balaguer", "contactado", "whatsapp", ""),
    ("Laia Font", "reformes", "Tàrrega", None, None, ""),
    ("Oriol Serra", "clima", "Mollerussa", None, None, ""),
)


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", sales._sin_tildes(texto)).strip("-")


def hoja_inventada(azar: random.Random) -> str:
    """El CSV de una pestaña «Gestorias» que no existe, con las columnas reales."""
    lineas = ["EMPRESA,DIRECCION,ESTADO,TELEFONO,EMAIL IA,PAGINA WEB,PROVINCIA,"
              "VERIFICACION CORREO"]
    usados: set[str] = set()
    numero = 0
    for provincia, (prefijo, poblaciones, cuantas) in _ZONAS.items():
        catalana = provincia in _CATALANAS
        apellidos = _APELLIDOS_CA if catalana else _APELLIDOS_ES
        formas = (("Gestoria", "Assessoria", "Gestoria Administrativa")
                  if catalana else ("Gestoría", "Asesoría", "Asesores"))
        for indice in range(cuantas):
            poblacion = poblaciones[indice % len(poblaciones)]
            while True:
                uno, otro = azar.sample(apellidos, 2)
                nombre = f"{azar.choice(formas)} {uno}"
                if azar.random() < 0.55:
                    nombre += f" {'i' if catalana else 'y'} {otro}"
                if azar.random() < 0.3 or nombre in usados:
                    nombre += f" {poblacion}"
                if nombre not in usados:
                    usados.add(nombre)
                    break
            numero += 1
            dominio = f"{_slug(nombre)}.example"
            # Teléfonos que no pueden ser de nadie: prefijo, ceros y un contador.
            telefono = f"{prefijo}{numero:0{9 - len(prefijo)}d}"
            verificado = azar.choice(("Buzón existe", "Buzón existe", "",
                                      "Dominio con MX"))
            lineas.append(
                f'{nombre},"Carrer Major {indice % 90 + 1}, '
                f'{_CP[provincia]}0{indice % 9 + 1}0 {poblacion}",WEB ACTIVA,'
                f"{telefono},info@{dominio},https://{dominio},{provincia},"
                f"{verificado}")
    return "\n".join(lineas) + "\n"


def sembrar(semilla: int = 7) -> dict:
    """Llena la base **actual** de contactos inventados. Solo si está vacía."""
    if config.DATABASE_URL:
        raise RuntimeError("La demo no se siembra en una base PostgreSQL.")
    if db.list_prospects():
        raise RuntimeError("Esta base ya tiene contactos: la demo no se mezcla "
                           "con datos de verdad.")
    azar = random.Random(semilla)
    hoy = date.today()
    hoja = sincronizar.connect_sheet(url=ENLACE_INVENTADO, nombre="Gestorías")
    leido = sincronizar.leer_hoja(hoja["id"], texto=hoja_inventada(azar))
    gestorias = sorted(db.list_prospects(), key=lambda p: p["id"])
    escritas = azar.sample(gestorias, 96)
    for indice, ficha in enumerate(escritas):
        cuando = hoy - timedelta(days=azar.randint(0, 70))
        db.add_sales_touch(ficha["id"], canal="email", resumen="Primer correo",
                           estado_despues="contactado", fecha=cuando.isoformat())
        despues = min(hoy, cuando + timedelta(days=azar.randint(1, 6))).isoformat()
        if indice % 5 == 0:
            db.add_sales_touch(
                ficha["id"], canal="email", estado_despues="hablado",
                fecha=despues,
                resumen="Contestan: lo que más horas les quita es perseguir "
                        "los tiques de gasolina cada trimestre")
        if indice % 15 == 0:
            db.add_sales_touch(ficha["id"], canal="llamada", fecha=despues,
                               resumen="Quedamos para verlo en su despacho",
                               estado_despues="cita")
        if indice % 24 == 0:
            db.add_sales_touch(ficha["id"], canal="email", fecha=despues,
                               resumen="Ahora no, en enero",
                               estado_despues="dormido")
        if indice % 32 == 0:
            db.add_sales_touch(ficha["id"], canal="cafe", fecha=despues,
                               resumen="Lo prueban con dos clientes suyos",
                               estado_despues="piloto")
    # Una demo con ochenta seguimientos vencidos no se parece a un día normal:
    # se dejan ocho para hoy y el resto, repartidos en los próximos días.
    vencidas = [p for p in db.list_prospects()
                if p.get("siguiente_el") and p["siguiente_el"] <= hoy.isoformat()
                and sales.ESTADOS[p["estado"]]["abierto"]]
    vencidas.sort(key=lambda p: p["siguiente_el"], reverse=True)
    for ficha in vencidas[8:]:
        db.update_prospect(ficha["id"], siguiente_el=(
            hoy + timedelta(days=azar.randint(1, 9))).isoformat())
    db.prospect_opt_out(gestorias[5]["id"], "Piden que no se les escriba más")
    for numero, (nombre, oficio, poblacion, estado, canal, dicho) in enumerate(
            _AUTONOMOS, start=1):
        ficha = db.add_prospect(
            nombre=nombre, oficio=sales.adivina_oficio(oficio),
            poblacion=poblacion, telefono=f"60000000{numero}", origen="circulo",
            tipo="autonomo", estado="lista", siguiente_el=hoy.isoformat(),
            siguiente_accion=sales.ESTADOS["lista"]["siguiente"])
        if estado:
            db.add_sales_touch(ficha["id"], canal=canal, resumen=dicho,
                               estado_despues=estado)
    return {"gestorias": leido["nuevas"], "autonomos": len(_AUTONOMOS)}


# ------------------------------------------------------ De la app a archivos --
_ESTILOS_DEMO = """
/* Solo en la demo: la banda que avisa y el mensaje de lo que no se guarda. */
:root { color-scheme: light; }
.crm-demo-banda {
  margin: 16px 0 0; padding: 10px 14px; border-radius: 10px;
  background: var(--amber-soft); border: 1px solid var(--border-strong);
  font-size: .84rem; line-height: 1.5; color: var(--text);
}
.crm-demo-banda b { font-weight: 700; }
.crm-demo-rail { font-size: 12px; line-height: 1.6; color: var(--muted); margin: 0; }
.crm-demo-aviso {
  position: fixed; left: 50%; transform: translateX(-50%); z-index: 60;
  bottom: calc(18px + env(safe-area-inset-bottom, 0px));
  width: max-content; max-width: min(560px, calc(100% - 32px));
  padding: 12px 16px; border-radius: 12px; background: var(--text); color: #fff;
  font-size: .86rem; line-height: 1.45; box-shadow: var(--shadow);
}
"""
_FUENTES = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
            'family=Fraunces:opsz,wght@9..144,400..600&amp;'
            'family=Inter:wght@400..700&amp;display=swap">')
_BANDA = ('<div class="crm-demo-banda" role="note"><b>Demo con datos inventados.'
          '</b> Las gestorías, los correos y las cifras no existen. Puedes '
          'cambiar de apartado, abrir fichas, arrastrar tarjetas y marcar una '
          'tanda: nada se guarda.</div>')
_RAIL = ('<p class="crm-demo-rail">Esta es la página de Captación del panel '
         'interno, sacada de la app con una lista inventada. El resto de '
         'departamentos no está en la demo.</p>')


def _estaticos() -> Path:
    return Path(__file__).resolve().parents[1] / "web" / "static"


def _estilos() -> str:
    raiz = _estaticos()
    hojas = [(raiz / nombre).read_text(encoding="utf-8")
             for nombre in ("app.css", "admin-workspace.css", "crm/crm.css")]
    # Las tipografías de la app se sirven desde su propio servidor; en la demo
    # llegan de Google Fonts con el mismo nombre de familia.
    css = re.sub(r"@font-face\s*\{.*?\}", "", "\n".join(hojas), flags=re.S)
    return css + _ESTILOS_DEMO


def _guiones() -> str:
    raiz = _estaticos() / "crm"
    return "\n".join((raiz / nombre).read_text(encoding="utf-8")
                     for nombre in ("demo.js", "crm.js"))


def _autonoma(html: str, *, entera: bool) -> str:
    """Convierte la página de la app en un archivo que no necesita servidor."""
    cuerpo = re.search(r"<body[^>]*>(.*)</body>", html, flags=re.S).group(1)
    cuerpo = re.sub(r'<script src="/static/[^"]*"[^>]*></script>', "", cuerpo)
    marca = base64.b64encode(
        (_estaticos() / "noesis-mark.svg").read_bytes()).decode()
    cuerpo = cuerpo.replace('src="/static/noesis-mark.svg"',
                            f'src="data:image/svg+xml;base64,{marca}"')
    # Navegación del resto del panel y acciones de sesión: fuera de la demo.
    cuerpo = re.sub(r'<details class="admin-nav-disclosure".*?</details>', _RAIL,
                    cuerpo, flags=re.S)
    cuerpo = re.sub(r'(<div class="admin-top-actions">).*?(</div>)', r"\1\2",
                    cuerpo, count=1, flags=re.S)
    cuerpo = re.sub(r'<p class="admin-rail-footer">.*?</p>', "", cuerpo,
                    flags=re.S)
    cuerpo = cuerpo.replace('<a class="admin-brand" href="/admin">',
                            '<a class="admin-brand" href="index.html">')
    for archivo, tipo in VISTAS.items():
        destino = "/admin/crm" + (f"?tipo={tipo}" if tipo else "")
        cuerpo = cuerpo.replace(f'<a href="{destino}" ', f'<a href="{archivo}" ')
    cuerpo = cuerpo.replace(f'href="{sincronizar.hojas.url_canonica(ENLACE_INVENTADO)}"',
                            'href="#hoja"')
    cuerpo = re.sub(r"(<main class=\"admin-wrap crm\"[^>]*)>",
                    r'\1 data-crm-demo-fichas="fichas.json">' + _BANDA, cuerpo,
                    count=1)
    pagina = (
        "<title>CRM de captación</title>\n" + _FUENTES
        + f"\n<style>{_estilos()}</style>\n"
        + f'<div class="admin-workspace">{cuerpo}</div>\n'
        + f"<script>{_guiones()}</script>\n")
    if not entera:
        return pagina
    return ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, '
            'viewport-fit=cover">\n' + pagina.replace("</style>\n", "</style>\n"
                                                      "</head>\n<body>\n", 1)
            + "</body>\n</html>\n")


def construir(destino: Path) -> dict:
    """Genera la demo en `destino` y devuelve qué ha escrito."""
    try:
        from starlette.testclient import TestClient
    except ImportError as exc:  # pragma: no cover - solo sin dependencias de pruebas
        raise RuntimeError("Generar la demo necesita las dependencias de "
                           "pruebas (httpx).") from exc
    from ..web import auth, server

    destino.mkdir(parents=True, exist_ok=True)
    clave = "solo-para-la-demo"  # pragma: allowlist secret
    with tempfile.TemporaryDirectory() as carpeta, patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(carpeta) / "demo.db",
            BACKUP_DIR=Path(carpeta) / "copias", DOCS_PATH=Path(carpeta) / "docs",
            ADMIN_EMAIL="demo@bynoesis.example", ADMIN_REQUIRE_GOOGLE_OAUTH=False,
            BASE_URL="https://bynoesis.com"), patch.object(
                server, "start_scheduler", lambda: None):
        db.init_db()
        cuantos = sembrar()
        negocio = db.create_business("Bynoesis", "demo@bynoesis.example")["id"]
        db.create_user("demo@bynoesis.example", auth.hash_password(clave), negocio)
        with TestClient(server.app) as cliente:
            cliente.post("/login", data={"email": "demo@bynoesis.example",
                                         "password": clave})
            paginas: dict[str, str] = {}
            for archivo, tipo in VISTAS.items():
                # La fórmula para la hoja se enseña una vez: se pide antes de
                # cada página para que la demo la lleve en todas.
                cliente.post("/admin/crm/hoja/enlace", data={},
                             follow_redirects=False)
                paginas[archivo] = cliente.get(
                    "/admin/crm", params={"tipo": tipo} if tipo else None).text
            fichas: dict[str, str] = {}
            for archivo, html in paginas.items():
                for ficha_id in sorted(set(re.findall(r"contacto=(\d+)", html)),
                                       key=int):
                    if ficha_id in fichas:
                        continue
                    con_ficha = cliente.get("/admin/crm", params={
                        "contacto": ficha_id, "tipo": VISTAS[archivo]}).text
                    trozo = re.search(
                        r'<section class="card crm-ficha" id="ficha">.*?</section>',
                        con_ficha, flags=re.S)
                    if trozo:
                        fichas[ficha_id] = trozo.group(0)
    for archivo, html in paginas.items():
        (destino / archivo).write_text(
            _autonoma(html, entera=archivo != "index.html"), encoding="utf-8")
    (destino / "fichas.json").write_text(
        json.dumps(fichas, ensure_ascii=False), encoding="utf-8")
    return {**cuantos, "fichas": len(fichas),
            "archivos": [*VISTAS, "fichas.json"]}


def main(argv: list[str] | None = None) -> int:
    argumentos = sys.argv[1:] if argv is None else argv
    if len(argumentos) != 1:
        print("Uso: python -m noesis.crm.demo CARPETA_DE_SALIDA")
        return 2
    resultado = construir(Path(argumentos[0]))
    print(f"Demo generada en {argumentos[0]}: {resultado['gestorias']} gestorías "
          f"y {resultado['autonomos']} autónomos inventados, "
          f"{resultado['fichas']} fichas.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
