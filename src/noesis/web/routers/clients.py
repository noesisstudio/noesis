"""Rutas de clientes, productos y CRM."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ... import config, db
from ..deps import _read_json

router = APIRouter()

@router.get("/api/{business_id}/clients")
def api_clients(business_id: int):
    return db.list_clients(business_id)


@router.get("/api/{business_id}/clients/stats")
def api_clients_stats(business_id: int):
    return db.client_stats(business_id)


@router.get("/api/{business_id}/clients/insights")
def api_clients_insights(business_id: int):
    """Lecturas explicables; cada señal enseña datos y confianza."""
    return {"items": db.client_insights(business_id)}


@router.get("/api/{business_id}/clients/{client_id}/portal-link")
def api_portal_link(business_id: int, client_id: int):
    """Enlace privado del cliente (Client Hub) para que el autónomo lo envíe por
    WhatsApp. Reutiliza el mismo enlace si ya existe uno vigente."""
    token = db.get_or_create_portal_token(business_id, client_id)
    if not token:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return {"url": f"{config.BASE_URL}/p/{token}", "path": f"/p/{token}"}


@router.post("/api/{business_id}/clients")
async def api_create_client(business_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "El nombre es obligatorio."}, status_code=400)
    return db.add_client(name, phone=body.get("phone"), address=body.get("address"),
                         zone=body.get("zone"), nif=body.get("nif"),
                         email=body.get("email"), business_id=business_id)


@router.post("/api/{business_id}/clients/import")
async def api_import_clients(business_id: int, request: Request):
    """Alta en bloque de clientes pegados como texto (una línea por cliente).

    Formato tolerante separado por comas o tabuladores:
    nombre, teléfono, email, NIF, zona. Solo el nombre es obligatorio.
    """
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    raw = (body.get("text") or "").strip()
    if not raw:
        return JSONResponse({"error": "Pega al menos un cliente."}, status_code=400)
    fields = ("name", "phone", "email", "nif", "zone")
    rows: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        cells = [c.strip() for c in line.replace("\t", ",").split(",")]
        # Ignora una posible cabecera pegada desde una hoja de cálculo.
        if not rows and cells[0].lower() in {"nombre", "name", "cliente"}:
            continue
        rows.append({fields[i]: cells[i] for i in range(min(len(cells), len(fields)))})
    if not rows:
        return JSONResponse({"error": "No se reconoció ningún cliente."},
                            status_code=400)
    return db.import_clients(rows, business_id)


@router.post("/api/{business_id}/clients/{client_id}")
async def api_update_client(business_id: int, client_id: int, request: Request):
    try:
        body = await _read_json(request)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not (body.get("name") or "").strip():
        return JSONResponse({"error": "El nombre es obligatorio."}, status_code=400)
    client = db.update_client(
        client_id, business_id, name=body.get("name"), phone=body.get("phone"),
        address=body.get("address"), zone=body.get("zone"), nif=body.get("nif"),
        email=body.get("email"),
    )
    if client is None:
        return JSONResponse({"error": "Cliente no encontrado."}, status_code=404)
    return client


@router.delete("/api/{business_id}/clients/{client_id}")
def api_delete_client(business_id: int, client_id: int):
    try:
        db.delete_client(client_id, business_id)
    except db.IntegrityError:
        return JSONResponse(
            {"error": "El cliente tiene datos asociados y no se puede borrar así."},
            status_code=409,
        )
    return {"ok": True}




@router.get("/api/{business_id}/products")
def api_products(business_id: int, all: int = 0):
    return db.list_products(business_id, include_inactive=bool(all))


@router.post("/api/{business_id}/products")
async def api_add_product(business_id: int, request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        return db.add_product(
            body.get("name"), kind=body.get("kind") or "servicio",
            price=body.get("price"), cost=body.get("cost"),
            vat_rate=body.get("vat_rate"), unit=body.get("unit"),
            category=body.get("category"), stock=body.get("stock"),
            stock_alert=body.get("stock_alert"), note=body.get("note"),
            business_id=business_id)
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/products/{product_id}")
async def api_update_product(business_id: int, product_id: int,
                             request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        return db.update_product(product_id, business_id=business_id, **body)
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


# ------------------------------------------------------------------- CRM ---
@router.get("/api/{business_id}/leads")
def api_leads(business_id: int, status: str = ""):
    try:
        return db.list_leads(business_id, status=status or None)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/leads")
async def api_add_lead(business_id: int, request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        return db.add_lead(
            body.get("name"), phone=body.get("phone"), email=body.get("email"),
            source=body.get("source"), note=body.get("note"),
            value_estimate=body.get("value_estimate"),
            next_action_on=body.get("next_action_on"),
            business_id=business_id)
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/leads/{lead_id}")
async def api_update_lead(business_id: int, lead_id: int, request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        return db.update_lead(
            lead_id, business_id=business_id, status=body.get("status"),
            note=body.get("note"), next_action_on=body.get("next_action_on"),
            value_estimate=body.get("value_estimate"))
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/{business_id}/leads/{lead_id}/convert")
def api_convert_lead(business_id: int, lead_id: int):
    try:
        return db.convert_lead_to_client(lead_id, business_id=business_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


# ------------------------------------------------- Solicitudes de gestoría
