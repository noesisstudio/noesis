"""La hoja de Google y el CRM de captación, juntos.

Dos caminos, uno en cada sentido, y ninguno escribe en la hoja:

1. **De la hoja al CRM** (`leer_hoja`). Se baja la pestaña en CSV y cada fila se
   convierte en una ficha o pone al día la que ya existía. La hoja manda en los
   datos de contacto (`hoja.CAMPOS_DE_HOJA`); el CRM manda en el estado, el
   historial, la nota y la baja. Quien pidió no ser contactado no vuelve a entrar
   ni se toca, por mucho que siga en la hoja.
2. **Del CRM a la hoja** (`csv_para_hoja`). La hoja lee con `IMPORTDATA` una
   dirección con una clave larga y enseña en una pestaña el estado de cada
   contacto. En la base solo se guarda la huella de esa clave; crear una nueva
   anula la anterior.

Vive en la carpeta `crm/`, y no en `db.py`, porque es un dominio con sus reglas:
la conexión y la transacción siguen siendo las de `db.get_conn()`.
"""
from __future__ import annotations

import csv
import hmac
import io
import logging
import secrets
from datetime import date

from .. import db, sales
from . import google as hojas
from . import hoja as lectura
from .zonas import sin_tildes

log = logging.getLogger(__name__)

FEED = "hoja"
_COLUMNAS_FICHA = (
    "nombre", "tipo", "origen", "estado", "oficio", "poblacion", "provincia",
    "direccion", "telefono", "email", "web", "hoja_id", "hoja_clave",
    "hoja_estado", "correo_verificacion", "hoja_vista_el", "siguiente_accion",
    "siguiente_el",
)


# ------------------------------------------------------------- Hojas --------
def list_sheets() -> list[dict]:
    with db.get_conn() as conn:
        return [dict(f) for f in conn.execute(
            "SELECT * FROM sales_sheets ORDER BY id").fetchall()]


def get_sheet(sheet_id) -> dict | None:
    with db.get_conn() as conn:
        fila = conn.execute("SELECT * FROM sales_sheets WHERE id=?",
                            (sheet_id,)).fetchone()
        return dict(fila) if fila else None


def connect_sheet(*, url: str, nombre: str = "", tipo: str = "gestoria",
                  origen: str = "web") -> dict:
    """Apunta la hoja. No la lee: eso lo hace `leer_hoja` justo después."""
    if tipo not in sales.TIPOS:
        raise ValueError("Tipo de contacto desconocido.")
    if origen not in sales.ORIGENES:
        raise ValueError("Origen desconocido.")
    limpia = hojas.url_canonica(url)  # lanza EnlaceNoValido con el motivo
    nombre = " ".join((nombre or "").split())[:80] or sales.TIPOS[tipo]["plural"]
    with db.get_conn() as conn:
        if conn.execute("SELECT id FROM sales_sheets WHERE url=?",
                        (limpia,)).fetchone():
            raise ValueError("Esa pestaña ya está conectada.")
        fila = conn.execute(
            "INSERT INTO sales_sheets (nombre, url, tipo, origen, created_at) "
            "VALUES (?,?,?,?,?) RETURNING id",
            (nombre, limpia, tipo, origen, db._now())).fetchone()
    return get_sheet(fila["id"])


def disconnect_sheet(sheet_id, *, quitar_sin_tocar: bool = False) -> dict:
    """Deja de leer la hoja. Las fichas se quedan, salvo que se pida lo contrario.

    `quitar_sin_tocar` es la salida para cuando se conecta la pestaña equivocada:
    borra solo lo que entró por esta hoja y sigue intacto (en la lista, sin
    historial y sin baja). Nada con lo que ya se haya trabajado se borra así.
    """
    quitadas = 0
    with db.get_conn() as conn:
        if quitar_sin_tocar:
            cur = conn.execute(
                "DELETE FROM sales_prospects WHERE hoja_id=? AND estado='lista' "
                "AND baja=? AND nota IS NULL AND id NOT IN "
                "(SELECT prospect_id FROM sales_touches)", (sheet_id, False))
            quitadas = int(getattr(cur, "rowcount", 0) or 0)
        conn.execute("UPDATE sales_prospects SET hoja_id=NULL, hoja_clave=NULL "
                     "WHERE hoja_id=?", (sheet_id,))
        cur = conn.execute("DELETE FROM sales_sheets WHERE id=?", (sheet_id,))
        existia = bool(getattr(cur, "rowcount", 0))
    return {"existia": existia, "quitadas": quitadas}


def _anotar_lectura(sheet_id, *, estado: str, error: str | None = None,
                    filas: int = 0, nuevas: int = 0, actualizadas: int = 0) -> None:
    ahora = db._now()
    with db.get_conn() as conn:
        if estado == "ok":
            conn.execute(
                "UPDATE sales_sheets SET ultima_lectura=?, ultimo_estado='ok', "
                "ultimo_error=NULL, filas=?, nuevas=?, actualizadas=?, "
                "updated_at=? WHERE id=?",
                (ahora, filas, nuevas, actualizadas, ahora, sheet_id))
        else:
            # Un fallo no borra las cifras de la última lectura buena.
            conn.execute(
                "UPDATE sales_sheets SET ultima_lectura=?, ultimo_estado='error', "
                "ultimo_error=?, updated_at=? WHERE id=?",
                (ahora, (error or "")[:300], ahora, sheet_id))


# ------------------------------------------------- De la hoja al CRM --------
def _nombre_plano(nombre) -> str:
    return " ".join(sin_tildes(nombre).split())


def _huellas(email, telefono) -> list[str]:
    from ..web import auth

    return [auth.hash_token(clave) for clave in (
        f"e:{email}" if email else None,
        f"t:{telefono}" if telefono else None) if clave]


def recordar_supresion(ficha: dict) -> int:
    """Antes de borrar a alguien: que la hoja no lo vuelva a traer mañana.

    Borrar la ficha cumple el derecho de supresión; si esa persona sigue en la
    hoja, la lectura de la mañana la crearía otra vez. Se guarda la huella de su
    correo y de su teléfono (no el dato) para reconocerla y dejarla fuera.
    """
    huellas = _huellas((ficha.get("email") or "").lower() or None,
                       ficha.get("telefono"))
    with db.get_conn() as conn:
        for huella in huellas:
            if not conn.execute("SELECT 1 FROM sales_suppressions WHERE huella=?",
                                (huella,)).fetchone():
                conn.execute(
                    "INSERT INTO sales_suppressions (huella, created_at) "
                    "VALUES (?,?)", (huella, db._now()))
    return len(huellas)


def aplicar_filas(hoja: dict, filas: list[dict]) -> dict:
    """Lleva las filas leídas a las fichas, en una sola transacción.

    Devuelve cuántas son nuevas, cuántas han cambiado y cuántas se han dejado
    estar porque pidieron la baja. Si algo falla a medias no queda media lista.
    """
    sello = db._now()
    hoy = date.today()
    nuevas = actualizadas = bajas = avanzadas = 0
    vistas: list[int] = []
    with db.get_conn() as conn:
        suprimidas = {f["huella"] for f in conn.execute(
            "SELECT huella FROM sales_suppressions").fetchall()}
        fichas = [dict(f) for f in conn.execute(
            "SELECT * FROM sales_prospects").fetchall()]
        por_clave = {p["hoja_clave"]: p for p in fichas
                     if p.get("hoja_id") == hoja["id"] and p.get("hoja_clave")}
        por_email = {p["email"]: p for p in fichas if p.get("email")}
        por_telefono = {p["telefono"]: p for p in fichas if p.get("telefono")}
        por_nombre = {_nombre_plano(p["nombre"]): p for p in fichas}

        def mover(ficha_id, tipo, pista, texto) -> None:
            conn.execute(
                "UPDATE sales_prospects SET estado=?, siguiente_el=?, "
                "siguiente_accion=?, updated_at=? WHERE id=?",
                (pista,
                 None if pista == "descartado"
                 else sales.siguiente_fecha(pista, hoy, tipo),
                 sales.ESTADOS[pista]["siguiente"] or None, sello, ficha_id))
            conn.execute(
                "INSERT INTO sales_touches (prospect_id, fecha, canal, resumen, "
                "estado_despues, created_at) VALUES (?,?,?,?,?,?)",
                (ficha_id, hoy.isoformat(), "otro",
                 f"Tomado de la hoja «{hoja['nombre']}»: {texto or 'marcado'}"[:2000],
                 pista, sello))

        for fila in filas:
            ficha = (por_clave.get(fila["clave"])
                     or (fila["email"] and por_email.get(fila["email"]))
                     or (fila["telefono"] and por_telefono.get(fila["telefono"]))
                     or por_nombre.get(_nombre_plano(fila["nombre"])))
            if ficha is None:
                if suprimidas.intersection(
                        _huellas(fila["email"], fila["telefono"])):
                    bajas += 1
                    continue
                campos = db._prospecto_campos({
                    "nombre": fila["nombre"], "tipo": hoja["tipo"],
                    "origen": hoja["origen"], "estado": "lista",
                    "oficio": fila.get("oficio"),
                    "poblacion": fila.get("poblacion"),
                    "provincia": fila.get("provincia"),
                    "direccion": fila.get("direccion"),
                    "telefono": fila.get("telefono"), "email": fila.get("email"),
                    "web": fila.get("web"), "hoja_id": hoja["id"],
                    "hoja_clave": fila["clave"],
                    "hoja_estado": fila.get("hoja_estado"),
                    "correo_verificacion": fila.get("correo_verificacion"),
                    "hoja_vista_el": sello,
                    # Sin fecha a propósito: mil gestorías recién leídas no son
                    # mil llamadas para hoy. Entran por tandas (`panel.tanda`).
                    "siguiente_accion": sales.ESTADOS["lista"]["siguiente"],
                    "siguiente_el": None,
                })
                columnas = [c for c in _COLUMNAS_FICHA if c in campos]
                creada = conn.execute(
                    f"INSERT INTO sales_prospects ({', '.join(columnas)}, "
                    f"created_at) VALUES ({', '.join('?' for _ in columnas)}, ?) "
                    "RETURNING id",
                    [*[campos[c] for c in columnas], sello]).fetchone()
                ficha = {**campos, "id": creada["id"], "baja": False}
                nuevas += 1
                if fila.get("estado_pista"):
                    mover(ficha["id"], hoja["tipo"], fila["estado_pista"],
                          fila.get("hoja_estado"))
                    avanzadas += 1
                # Para que la misma persona repetida más abajo no entre dos veces.
                por_clave[fila["clave"]] = ficha
                if fila["email"]:
                    por_email[fila["email"]] = ficha
                if fila["telefono"]:
                    por_telefono[fila["telefono"]] = ficha
                por_nombre[_nombre_plano(fila["nombre"])] = ficha
                continue
            if ficha.get("baja"):
                bajas += 1
                continue
            vistas.append(ficha["id"])
            cambios = {}
            for campo in lectura.CAMPOS_DE_HOJA:
                valor = fila.get(campo)
                # Una celda vacía no borra un dato que ya se tenía, salvo en las
                # dos columnas que solo existen en la hoja.
                if valor is None and campo not in ("hoja_estado",
                                                   "correo_verificacion"):
                    continue
                if valor != ficha.get(campo):
                    cambios[campo] = valor
            if ficha.get("hoja_id") in (None, hoja["id"]) and (
                    ficha.get("hoja_id") != hoja["id"]
                    or ficha.get("hoja_clave") != fila["clave"]):
                cambios.update({"hoja_id": hoja["id"], "hoja_clave": fila["clave"]})
            if cambios:
                limpio = db._prospecto_campos(cambios)
                conn.execute(
                    f"UPDATE sales_prospects SET "
                    f"{', '.join(f'{c}=?' for c in limpio)}, updated_at=? "
                    "WHERE id=?", [*limpio.values(), sello, ficha["id"]])
                if set(cambios) - {"hoja_id", "hoja_clave"}:
                    actualizadas += 1
            if lectura.avanza(ficha.get("estado") or "lista",
                            fila.get("estado_pista")):
                mover(ficha["id"], ficha.get("tipo") or hoja["tipo"],
                      fila["estado_pista"], fila.get("hoja_estado"))
                avanzadas += 1
        for inicio in range(0, len(vistas), 400):
            trozo = vistas[inicio:inicio + 400]
            conn.execute(
                "UPDATE sales_prospects SET hoja_vista_el=? WHERE id IN "
                f"({', '.join('?' for _ in trozo)})", [sello, *trozo])
        # Estaban enlazadas a esta hoja y hoy no han aparecido. Se cuenta con lo
        # visto en esta lectura, no por la fecha: dos lecturas en el mismo
        # segundo llevarían el mismo sello.
        hoy_vistas = set(vistas)
        ausentes = sum(1 for p in fichas
                       if p.get("hoja_id") == hoja["id"] and not p.get("baja")
                       and p["id"] not in hoy_vistas)
    return {"filas": len(filas), "nuevas": nuevas, "actualizadas": actualizadas,
            "bajas": bajas, "avanzadas": avanzadas, "ausentes": int(ausentes)}


def leer_hoja(sheet_id, *, texto: str | None = None) -> dict:
    """Baja la pestaña y la aplica. Deja anotado cómo fue, haya ido bien o mal.

    Devuelve el resultado con `ok`. No lanza por un fallo de Google o de la hoja:
    lo devuelve en `error`, con una frase que se puede enseñar tal cual.
    """
    hoja = get_sheet(sheet_id)
    if not hoja:
        raise ValueError("Esa hoja ya no está conectada.")
    try:
        leido = lectura.parse_hoja(texto if texto is not None
                                 else hojas.descargar(hoja["url"]))
        if not leido["filas"]:
            raise ValueError("La pestaña tiene cabecera pero ninguna fila.")
        resultado = aplicar_filas(hoja, leido["filas"])
    except (hojas.EnlaceNoValido, hojas.HojaNoCompartida,
            hojas.HojaNoDisponible, ValueError) as exc:
        _anotar_lectura(sheet_id, estado="error", error=str(exc))
        return {"ok": False, "error": str(exc), "hoja": hoja}
    _anotar_lectura(sheet_id, estado="ok", filas=resultado["filas"],
                    nuevas=resultado["nuevas"],
                    actualizadas=resultado["actualizadas"])
    return {"ok": True, "hoja": hoja, "columnas": leido["columnas"],
            "ignoradas": leido["ignoradas"], **resultado}


def leer_todas() -> list[dict]:
    """La lectura diaria. Una hoja que falla no impide leer las demás."""
    resultados = []
    for hoja in list_sheets():
        if not hoja.get("activa"):
            continue
        try:
            resultados.append(leer_hoja(hoja["id"]))
        except Exception:  # noqa: BLE001 - una hoja rota no para el reloj
            # Sin traza: el error puede llevar correos de la lista.
            log.error("No se pudo leer la hoja de captación %s.", hoja["id"])
            _anotar_lectura(hoja["id"], estado="error",
                            error="Fallo inesperado al leer la hoja.")
    return resultados


def frase_de_lectura(resultado: dict) -> str:
    """Lo que se le dice al founder después de leer la hoja."""
    if not resultado.get("ok"):
        return resultado.get("error") or "No se pudo leer la hoja."
    partes = [f"Leídas {resultado['filas']} filas de «{resultado['hoja']['nombre']}»: "
              f"{resultado['nuevas']} nuevas y {resultado['actualizadas']} "
              "puestas al día."]
    if resultado.get("avanzadas"):
        partes.append(f"{resultado['avanzadas']} avanzan de estado por lo que "
                      "pone en la hoja.")
    if resultado.get("bajas"):
        partes.append(f"{resultado['bajas']} siguen en la hoja pero pidieron no "
                      "ser contactados o que se les borrase: no se tocan.")
    if resultado.get("ausentes"):
        partes.append(f"{resultado['ausentes']} ya no están en la hoja; aquí se "
                      "conservan con su historial.")
    if resultado.get("ignoradas"):
        partes.append("Columnas que no uso: "
                      + ", ".join(resultado["ignoradas"][:6]) + ".")
    return " ".join(partes)


# ------------------------------------------------- Del CRM a la hoja --------
def crear_enlace() -> str:
    """Genera la clave del enlace y anula la anterior. Se enseña una sola vez."""
    from ..web import auth

    token = secrets.token_urlsafe(32)
    with db.get_conn() as conn:
        conn.execute("DELETE FROM sales_feeds WHERE clave=?", (FEED,))
        conn.execute(
            "INSERT INTO sales_feeds (clave, token_hash, created_at) "
            "VALUES (?,?,?)", (FEED, auth.hash_token(token), db._now()))
    return token


def revocar_enlace() -> bool:
    with db.get_conn() as conn:
        cur = conn.execute("DELETE FROM sales_feeds WHERE clave=?", (FEED,))
    return bool(getattr(cur, "rowcount", 0))


def estado_enlace() -> dict | None:
    with db.get_conn() as conn:
        fila = conn.execute(
            "SELECT created_at, leido_el FROM sales_feeds WHERE clave=?",
            (FEED,)).fetchone()
        return dict(fila) if fila else None


def enlace_valido(token: str) -> bool:
    """Comprueba la clave en tiempo constante y apunta que se ha leído."""
    from ..web import auth

    if not token or len(token) > 200:
        return False
    with db.get_conn() as conn:
        fila = conn.execute("SELECT token_hash FROM sales_feeds WHERE clave=?",
                            (FEED,)).fetchone()
        if not fila or not hmac.compare_digest(fila["token_hash"],
                                               auth.hash_token(token)):
            return False
        conn.execute("UPDATE sales_feeds SET leido_el=? WHERE clave=?",
                     (db._now(), FEED))
    return True


CABECERA_FEED = (
    "EMPRESA", "CORREO", "TELEFONO", "PROVINCIA", "TIPO", "ESTADO CRM",
    "ULTIMO CONTACTO", "CANAL", "CONTACTOS", "SIGUIENTE PASO",
    "SIGUIENTE FECHA", "NO CONTACTAR",
)


def _celda(valor) -> str:
    """Texto seguro para una hoja de cálculo.

    Una celda que empieza por `=`, `+`, `-` o `@` se interpreta como fórmula. El
    nombre de una empresa lo escribe un tercero en su web: se desactiva con un
    apóstrofo delante, que la hoja no enseña.
    """
    texto = " ".join(str(valor if valor is not None else "").split())
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def _telefono_legible(telefono) -> str:
    # Con espacios para que la hoja lo deje como texto y no lo sume.
    t = str(telefono or "")
    if t.startswith("+34") and len(t) == 12:
        return f"{t[3:6]} {t[6:9]} {t[9:]}"
    return t.lstrip("+")


def csv_para_hoja() -> str:
    """El estado de cada contacto, listo para `IMPORTDATA`.

    Lleva lo justo para cruzarlo con la lista (el correo) y saber por dónde va
    cada uno. No lleva las notas ni lo que dijeron: eso se queda en el CRM.
    """
    fichas = db.list_prospects()
    ultimo: dict[int, dict] = {}
    cuenta: dict[int, int] = {}
    for toque in db.list_all_sales_touches():
        ultimo[toque["prospect_id"]] = toque
        cuenta[toque["prospect_id"]] = cuenta.get(toque["prospect_id"], 0) + 1
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\n")
    escritor.writerow(CABECERA_FEED)
    for p in sorted(fichas, key=lambda f: (f.get("nombre") or "").lower()):
        toque = ultimo.get(p["id"]) or {}
        estado = sales.ESTADOS.get(p.get("estado") or "lista",
                                   sales.ESTADOS["lista"])
        escritor.writerow([
            _celda(p.get("nombre")), _celda(p.get("email")),
            _telefono_legible(p.get("telefono")), _celda(p.get("provincia")),
            sales.TIPOS.get(p.get("tipo") or "autonomo",
                            sales.TIPOS["autonomo"])["etiqueta"],
            estado["etiqueta"], str(toque.get("fecha") or "")[:10],
            sales.CANALES.get(toque.get("canal") or "", ""),
            cuenta.get(p["id"], 0),
            "" if p.get("baja") else _celda(p.get("siguiente_accion")),
            "" if p.get("baja") else str(p.get("siguiente_el") or "")[:10],
            "SÍ" if p.get("baja") else "",
        ])
    return salida.getvalue()
