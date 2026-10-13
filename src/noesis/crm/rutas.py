"""Rutas del CRM de captación: `/admin/crm` y la dirección que lee la hoja.

El embudo de la empresa: a quién perseguimos nosotros. El CRM de `/b/<id>/crm`
es el del autónomo y guarda sus presupuestos; este guarda nuestra lista, y por
eso vive detrás de `_is_admin` y no lleva `business_id`.

Una sola ruta no pide sesión: `/admin/crm/feed/{clave}.csv`. La lee la hoja de
Google con `IMPORTDATA`, que no puede iniciar sesión; se protege con una clave
larga de la que aquí solo se guarda la huella. Está bajo `/admin` para heredar
«sin caché», «sin indexar» y el `Disallow` de robots.txt.

El orden importa: las rutas con nombre fijo (`/tanda`, `/hoja/…`) van antes que
`/admin/crm/{prospect_id}`, que si no se las quedaría.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse, JSONResponse, RedirectResponse, Response,
)

from .. import config, db, sales
from ..web import auth
from ..web.deps import TEMPLATES
from ..web.routers.admin import _is_admin
from . import google, panel, sincronizar

router = APIRouter()

# Quién se persigue por correo y por tandas, y no por teléfono a las 7:30.
TIPOS_DE_TANDA = ("gestoria", "gremio", "almacen")


def _tipo(valor) -> str:
    return valor if valor in sales.TIPOS else ""


def _volver(tipo: str = "", ancla: str = "", **extra) -> RedirectResponse:
    """De vuelta a la página, conservando lo que se estaba mirando.

    La dirección se construye aquí con valores comprobados: nunca se redirige a
    algo que venga escrito en el formulario.
    """
    consulta = {k: v for k, v in {"tipo": _tipo(tipo), **extra}.items() if v}
    destino = "/admin/crm" + (f"?{urlencode(consulta)}" if consulta else "")
    return RedirectResponse(destino + (f"#{ancla}" if ancla else ""),
                            status_code=303)


def _anotar(request: Request, evento: str, **metadata) -> None:
    user = auth.current_user(request)
    db.record_security_event(
        evento, area="admin", actor_user_id=user["id"],
        subject_business_id=user["business_id"],
        request_id=getattr(request.state, "request_id", None),
        metadata=metadata or None,
    )


def _entero(valor, por_defecto: int = 1) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return por_defecto


# ================================================================ La página =
@router.get("/admin/crm", response_class=HTMLResponse)
def admin_crm(request: Request):
    """El parte, lo de hoy, los gráficos, el tablero y la lista."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    _anotar(request, "admin.crm_viewed")
    q = request.query_params
    tipo = _tipo(q.get("tipo"))
    estado = q.get("estado") if q.get("estado") in sales.ESTADOS else ""
    provincia = (q.get("provincia") or "").strip()[:60]
    busca = (q.get("q") or "").strip()[:80]
    zona = (q.get("zona") or "").strip()[:60]

    crudos = db.list_prospects()
    por_tipo = {clave: 0 for clave in sales.TIPOS}
    for p in crudos:
        if not p.get("baja"):
            clave = p.get("tipo") if p.get("tipo") in sales.TIPOS else "autonomo"
            por_tipo[clave] += 1
    de_la_vista = [p for p in crudos
                   if not tipo or (p.get("tipo") or "autonomo") == tipo]
    vista = [sales.enriquecer(p) for p in de_la_vista]
    lista = panel.paginar(
        panel.filtrar(vista, estado=estado, provincia=provincia, busca=busca),
        _entero(q.get("pagina")))
    de_tanda = [p for p in vista if p["tipo"] in TIPOS_DE_TANDA]
    zonas = panel.zonas_pendientes(de_tanda)
    if zona not in {z["nombre"] for z in zonas}:
        zona = zonas[0]["nombre"] if zonas else ""

    detalle_id = q.get("contacto")
    detalle, toques = None, []
    if detalle_id and detalle_id.isdigit():
        crudo = db.get_prospect(int(detalle_id))
        if crudo:
            detalle = sales.enriquecer(crudo)
            toques = db.list_sales_touches(int(detalle_id))
    filtros = {k: v for k, v in (("tipo", tipo), ("estado", estado),
                                 ("provincia", provincia), ("q", busca)) if v}
    return TEMPLATES.TemplateResponse(request, "crm/pagina.html", {
        # Con qué nombre se firman los guiones. La base no guarda el nombre de
        # pila de nadie, así que esto es solo el punto de partida: la página deja
        # cambiarlo y lo recuerda en el navegador.
        "yo": user["email"].split("@")[0].split(".")[0].title(),
        "tipo": tipo,
        "tipos": sales.TIPOS,
        "por_tipo": por_tipo,
        "hay_alguien": any(por_tipo.values()),
        "resumen": sales.resumen(de_la_vista),
        "panel": panel.panel(de_la_vista, db.list_all_sales_touches()),
        "tramos_zona": panel.TRAMOS_ZONA,
        "tablero": panel.tablero(vista),
        "lista": lista,
        "filtro": {"estado": estado, "provincia": provincia, "q": busca},
        "consulta_filtros": urlencode(filtros),
        "provincias": sorted({p.get("provincia") for p in vista
                              if p.get("provincia")}),
        "zonas": zonas,
        "zona": zona,
        "tanda": panel.tanda(de_tanda, zona) if zona else [],
        "hojas": sincronizar.list_sheets(),
        "enlace": sincronizar.estado_enlace(),
        "enlace_nuevo": request.session.pop("crm_enlace_nuevo", None),
        "detalle": detalle,
        "toques": toques,
        "estados": sales.ESTADOS,
        "origenes": sales.ORIGENES,
        "oficios": sales.OFICIOS,
        "canales": sales.CANALES,
        "guiones": sales.GUIONES,
        "preguntas": sales.PREGUNTAS_CAFE,
        "hoy": date.today().isoformat(),
        "admin_error": request.session.pop("admin_error", None),
        "admin_success": request.session.pop("admin_success", None),
        "admin_as_of": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
    })


# ============================================================ Meter gente ===
@router.post("/admin/crm/nuevo")
async def admin_crm_nuevo(request: Request):
    """Alta de uno a mano: el que te encuentras en el pasillo del almacén."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    formulario = await request.form()
    tipo = _tipo(formulario.get("tipo")) or "autonomo"
    try:
        creado = db.add_prospect(
            nombre=formulario.get("nombre"),
            oficio=formulario.get("oficio") or None,
            poblacion=formulario.get("poblacion"),
            provincia=formulario.get("provincia"),
            telefono=formulario.get("telefono"),
            email=formulario.get("email"),
            origen=formulario.get("origen") or "otro",
            presentado_por=formulario.get("presentado_por"),
            nota=formulario.get("nota"),
            tipo=tipo,
            estado="lista",
            siguiente_el=date.today().isoformat(),
            siguiente_accion=sales.ESTADOS["lista"]["siguiente"],
        )
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
        return _volver(formulario.get("vista"), "nuevo")
    request.session["admin_success"] = (
        f"{creado['nombre']} entra en la lista. Lo siguiente: el primer contacto.")
    return _volver(formulario.get("vista"), "ficha", contacto=creado["id"])


@router.post("/admin/crm/importar")
async def admin_crm_importar(request: Request):
    """Pega la lista de nombres tal como la tengas escrita."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    formulario = await request.form()
    filas = sales.parse_lista(formulario.get("lista") or "")
    if not filas:
        request.session["admin_error"] = (
            "No he entendido ninguna línea. Una persona por línea; el teléfono "
            "puede ir donde sea.")
        return _volver(formulario.get("vista"), "importar")
    resultado = db.import_prospects(
        filas, origen=formulario.get("origen") or "otro",
        presentado_por=formulario.get("presentado_por") or None,
        tipo=_tipo(formulario.get("tipo")) or "autonomo")
    creados, repetidos = len(resultado["creados"]), len(resultado["repetidos"])
    request.session["admin_success"] = (
        f"{creados} contacto(s) nuevos en la lista."
        + (f" {repetidos} ya estaban y no se han duplicado." if repetidos else ""))
    return _volver(formulario.get("vista"))


# ====================================================== La hoja de Google ===
@router.post("/admin/crm/hoja/conectar")
async def admin_crm_hoja_conectar(request: Request):
    """Apunta una pestaña de la hoja y la lee por primera vez."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    formulario = await request.form()
    try:
        hoja = sincronizar.connect_sheet(
            url=formulario.get("url") or "", nombre=formulario.get("nombre") or "",
            tipo=_tipo(formulario.get("tipo")) or "gestoria", origen="web")
    except (google.EnlaceNoValido, ValueError) as exc:
        request.session["admin_error"] = str(exc)
        return _volver(formulario.get("vista"), "hoja")
    resultado = sincronizar.leer_hoja(hoja["id"])
    _anotar(request, "admin.crm_sheet_connected", sheet_id=hoja["id"],
            ok=resultado["ok"], filas=resultado.get("filas", 0))
    if resultado["ok"]:
        request.session["admin_success"] = (
            "Hoja conectada. " + sincronizar.frase_de_lectura(resultado)
            + " Se volverá a leer sola cada mañana.")
        return _volver(hoja["tipo"], "panel")
    # Se deja conectada aunque la primera lectura falle: lo normal es que falte
    # compartirla, y así basta con arreglarlo y pulsar «Leer ahora».
    request.session["admin_error"] = (
        "He apuntado la hoja, pero no he podido leerla. " + resultado["error"])
    return _volver(formulario.get("vista"), "hoja")


@router.post("/admin/crm/hoja/enlace")
async def admin_crm_enlace_crear(request: Request):
    """Crea la dirección por la que la hoja lee el estado del CRM."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    formulario = await request.form()
    token = sincronizar.crear_enlace()
    _anotar(request, "admin.crm_feed_created")
    # Solo se enseña esta vez: en la base queda la huella, no la clave.
    request.session["crm_enlace_nuevo"] = (
        f"{config.BASE_URL}/admin/crm/feed/{token}.csv")
    return _volver(formulario.get("vista"), "hoja")


@router.post("/admin/crm/hoja/enlace/anular")
async def admin_crm_enlace_anular(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    formulario = await request.form()
    sincronizar.revocar_enlace()
    _anotar(request, "admin.crm_feed_revoked")
    request.session["admin_success"] = (
        "Dirección anulada. La pestaña de la hoja que la usaba dejará de "
        "actualizarse.")
    return _volver(formulario.get("vista"), "hoja")


@router.post("/admin/crm/hoja/{sheet_id}/leer")
async def admin_crm_hoja_leer(request: Request, sheet_id: int):
    """Vuelve a leer la hoja ahora, sin esperar a la lectura de la mañana."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    formulario = await request.form()
    try:
        resultado = sincronizar.leer_hoja(sheet_id)
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
        return _volver(formulario.get("vista"), "hoja")
    _anotar(request, "admin.crm_sheet_read", sheet_id=sheet_id,
            ok=resultado["ok"], filas=resultado.get("filas", 0),
            nuevas=resultado.get("nuevas", 0))
    clave = "admin_success" if resultado["ok"] else "admin_error"
    request.session[clave] = sincronizar.frase_de_lectura(resultado)
    return _volver(formulario.get("vista"), "hoja")


@router.post("/admin/crm/hoja/{sheet_id}/desconectar")
async def admin_crm_hoja_desconectar(request: Request, sheet_id: int):
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    formulario = await request.form()
    resultado = sincronizar.disconnect_sheet(
        sheet_id, quitar_sin_tocar=formulario.get("quitar") == "si")
    _anotar(request, "admin.crm_sheet_disconnected", sheet_id=sheet_id,
            quitadas=resultado["quitadas"])
    request.session["admin_success"] = (
        "Hoja desconectada."
        + (f" He quitado {resultado['quitadas']} contacto(s) que habían entrado "
           "por ella y con los que no habías hecho nada."
           if resultado["quitadas"] else
           " Los contactos que trajo se quedan en la lista."))
    return _volver(formulario.get("vista"), "hoja")


@router.get("/admin/crm/feed/{clave}.csv")
def admin_crm_feed(clave: str):
    """Lo que lee la hoja con IMPORTDATA. Sin sesión: la clave es el permiso."""
    if not sincronizar.enlace_valido(clave):
        # 404 y no 403: a quien prueba claves no se le confirma que aquí hay algo.
        return Response("No encontrado.", status_code=404)
    return Response(
        content=sincronizar.csv_para_hoja(),
        media_type="text/csv; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


# ================================================================= Tandas ===
@router.post("/admin/crm/tanda")
async def admin_crm_tanda(request: Request):
    """Apunta de una vez la tanda de correos que acabas de enviar."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    formulario = await request.form()
    ids = [int(v) for v in formulario.getlist("ids") if str(v).isdigit()][:200]
    zona = (formulario.get("zona") or "").strip()[:60]
    if not ids:
        request.session["admin_error"] = (
            "No has marcado a nadie. Marca a quién le has escrito y vuelve a "
            "pulsar.")
        return _volver(formulario.get("vista"), "tanda", zona=zona)
    hechos = 0
    try:
        for ficha_id in ids:
            ficha = db.get_prospect(ficha_id)
            # Solo quien sigue sin escribir: recargar la página y volver a pulsar
            # no debe apuntar el mismo correo dos veces.
            if not ficha or ficha.get("baja") or ficha.get("estado") != "lista":
                continue
            db.add_sales_touch(
                ficha_id, canal="email",
                resumen=("Primer correo" + (f" · tanda de {zona}" if zona else "")),
                estado_despues="contactado",
                fecha=formulario.get("fecha") or None, user_id=user["id"])
            if formulario.get("informado") == "si":
                db.update_prospect(
                    ficha_id, informado_el=(formulario.get("fecha")
                                            or date.today().isoformat()))
            hechos += 1
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
        return _volver(formulario.get("vista"), "tanda", zona=zona)
    _anotar(request, "admin.crm_batch_marked", cuantos=hechos)
    request.session["admin_success"] = (
        f"Apuntado: {hechos} escritos. Te los vuelvo a enseñar dentro de una "
        "semana si no han contestado." if hechos else
        "Esos ya estaban apuntados; no he cambiado nada.")
    return _volver(formulario.get("vista"), "tanda", zona=zona)


# ============================================================= Exportar =====
@router.get("/admin/crm/export.csv")
def admin_crm_export(request: Request):
    """La lista entera en CSV: los datos son tuyos y salen de aquí cuando quieras."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    columnas = ("id", "nombre", "tipo", "oficio", "poblacion", "provincia",
                "direccion", "telefono", "email", "web", "origen",
                "presentado_por", "estado", "siguiente_accion", "siguiente_el",
                "informado_el", "baja", "baja_motivo", "nota", "hoja_estado",
                "correo_verificacion", "created_at", "updated_at")
    buffer = io.StringIO()
    escritor = csv.DictWriter(buffer, fieldnames=columnas, extrasaction="ignore",
                              delimiter=";")
    escritor.writeheader()
    for fila in db.list_prospects():
        escritor.writerow({c: fila.get(c) for c in columnas})
    hoy = date.today().isoformat()
    return Response(
        # BOM para que Excel en Windows no parta las tildes.
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="Bynoesis-captacion-{hoy}.csv"',
                 "Cache-Control": "no-store"},
    )


# ============================================================== La ficha ====
@router.post("/admin/crm/{prospect_id}")
async def admin_crm_editar(request: Request, prospect_id: int):
    """Edita la ficha: datos, siguiente paso o nota."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    formulario = await request.form()
    campos = {c: formulario.get(c) for c in (
        "nombre", "tipo", "oficio", "poblacion", "provincia", "telefono", "email",
        "web", "origen", "presentado_por", "estado", "siguiente_accion",
        "siguiente_el", "nota")
        if c in formulario}
    if formulario.get("informado") == "si":
        campos["informado_el"] = date.today().isoformat()
    try:
        db.update_prospect(prospect_id, **campos)
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
    else:
        request.session["admin_success"] = "Ficha guardada."
    return _volver(formulario.get("vista"), "ficha", contacto=prospect_id)


@router.post("/admin/crm/{prospect_id}/toque")
async def admin_crm_toque(request: Request, prospect_id: int):
    """Anota un contacto y mueve el embudo en la misma operación."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    user = auth.current_user(request)
    formulario = await request.form()
    try:
        db.add_sales_touch(
            prospect_id, canal=formulario.get("canal") or "llamada",
            resumen=formulario.get("resumen") or "",
            estado_despues=formulario.get("estado_despues") or None,
            fecha=formulario.get("fecha") or None, user_id=user["id"])
        if formulario.get("informado") == "si":
            db.update_prospect(prospect_id, informado_el=date.today().isoformat())
        if formulario.get("siguiente_el"):
            db.update_prospect(prospect_id,
                               siguiente_el=formulario.get("siguiente_el"))
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
    else:
        request.session["admin_success"] = "Anotado."
    return _volver(formulario.get("vista"), "ficha", contacto=prospect_id)


@router.post("/admin/crm/{prospect_id}/mover")
async def admin_crm_mover(request: Request, prospect_id: int):
    """Arrastrar una tarjeta a otra columna del tablero.

    Deja un apunte en el historial igual que el formulario: un cambio de estado
    sin apunte es como se acaba con un embudo que nadie sabe explicar.
    """
    if not _is_admin(request):
        return JSONResponse({"error": "no autenticado"}, status_code=401)
    user = auth.current_user(request)
    formulario = await request.form()
    estado = formulario.get("estado") or ""
    ficha = db.get_prospect(prospect_id)
    if not ficha or estado not in sales.ESTADOS:
        return JSONResponse({"error": "Ese contacto o ese estado no existen."},
                            status_code=404)
    if ficha.get("baja"):
        return JSONResponse(
            {"error": "Pidió no ser contactado: no se mueve por el embudo."},
            status_code=409)
    if ficha.get("estado") != estado:
        db.add_sales_touch(
            prospect_id, canal="otro", resumen="Movido en el tablero",
            estado_despues=estado, user_id=user["id"])
    despues = sales.enriquecer(db.get_prospect(prospect_id))
    return JSONResponse({
        "ok": True, "estado": despues["estado"],
        "etiqueta": despues["estado_etiqueta"],
        "siguiente_el": despues.get("siguiente_el"),
    })


@router.post("/admin/crm/{prospect_id}/baja")
async def admin_crm_baja(request: Request, prospect_id: int):
    """Ha dicho que no le llames más. Se anota para no volver a llamarle."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    formulario = await request.form()
    try:
        db.prospect_opt_out(prospect_id, formulario.get("motivo") or "")
    except ValueError as exc:
        request.session["admin_error"] = str(exc)
        return _volver(formulario.get("vista"))
    _anotar(request, "admin.crm_opt_out", prospect_id=prospect_id)
    request.session["admin_success"] = (
        "Marcado como baja. No vuelve a aparecer en lo que toca hoy, y la lista "
        "no lo readmite aunque lo vuelvas a pegar ni aunque siga en la hoja.")
    return _volver(formulario.get("vista"))


@router.post("/admin/crm/{prospect_id}/eliminar")
async def admin_crm_eliminar(request: Request, prospect_id: int):
    """Supresión de verdad, con su historial: para cuando ejerce ese derecho."""
    if not _is_admin(request):
        return RedirectResponse("/login", status_code=303)
    formulario = await request.form()
    ficha = db.get_prospect(prospect_id)
    if ficha:
        sincronizar.recordar_supresion(ficha)
    borrado = db.delete_prospect(prospect_id)
    _anotar(request, "admin.crm_deleted", prospect_id=prospect_id,
            borrado=borrado)
    request.session["admin_success"] = (
        "Borrado con su historial. Si sigue en la hoja de Google, no volverá a "
        "entrar desde ella; bórralo también allí."
        if borrado else "Ese contacto ya no estaba.")
    return _volver(formulario.get("vista"))
