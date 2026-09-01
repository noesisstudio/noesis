"""Dependencias compartidas de la capa web."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import config, db
from ..adapters import billing as billing_adapter
from ..adapters import transcription
from ..documents import ocr
from . import auth

HERE = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(HERE / "templates"))


def _asset_version() -> str:
    """Versiona assets por fecha de modificacion para romper cache tras despliegues."""
    paths = [HERE / "static" / "app.css", HERE / "static" / "app.js"]
    try:
        return str(int(max(p.stat().st_mtime for p in paths if p.exists())))
    except ValueError:
        return "1"


# Disponible en todas las plantillas como {{ asset_v }}.
TEMPLATES.env.globals["asset_v"] = _asset_version()
# Dominio público: lo usan las etiquetas canónicas y de compartición social.
TEMPLATES.env.globals["base_url"] = config.BASE_URL
TEMPLATES.env.globals["public_signup_available"] = config.public_signup_available()
TEMPLATES.env.globals["public_contact_email"] = config.PUBLIC_CONTACT_EMAIL
TEMPLATES.env.globals["voice_available"] = transcription.available()
TEMPLATES.env.globals["ocr_available"] = (
    ocr.available() or bool(config.ANTHROPIC_API_KEY)
)

# Una sola fuente para la identidad que leen los buscadores. Se publica únicamente
# en la portada: repetir la misma Organization en todas las páginas añade ruido y
# hace más fácil que dos copias terminen contradiciéndose.
_public_origin = config.BASE_URL.rstrip("/")
TEMPLATES.env.globals["seo_home_graph"] = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "Organization",
            "@id": f"{_public_origin}/#organization",
            "name": "Noesis",
            "url": _public_origin,
            "logo": f"{_public_origin}/static/noesis-mark.svg",
            "email": config.PUBLIC_CONTACT_EMAIL,
            "contactPoint": {
                "@type": "ContactPoint",
                "contactType": "customer support",
                "email": config.PUBLIC_CONTACT_EMAIL,
                "availableLanguage": ["es", "ca", "en"],
            },
            "areaServed": "ES",
            "description": (
                "Noesis ordena trabajos, clientes, documentos, facturas y cobros "
                "desde WhatsApp para autónomos y pequeños negocios de servicios."
            ),
        },
        {
            "@type": "WebSite",
            "@id": f"{_public_origin}/#website",
            "name": "Noesis",
            "url": _public_origin,
            "inLanguage": "es",
            "publisher": {"@id": f"{_public_origin}/#organization"},
        },
    ],
}


def _eur(value) -> str:
    """Formato de dinero en espanol (1.234,56 EUR) para las plantillas."""
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


# Disponible en plantillas como {{ importe | eur }}.
TEMPLATES.env.filters["eur"] = _eur


def _human_date(value) -> str:
    """Convierte fechas ISO de la base en una fecha legible para personas."""
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        point = value.date()
    elif isinstance(value, date):
        point = value
    else:
        text = str(value).strip()
        try:
            point = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                point = date.fromisoformat(text[:10])
            except ValueError:
                return text
    return point.strftime("%d/%m/%Y")


# Evita que los portales enseñen marcas ISO internas como 2026-08-14T00:00:00.
TEMPLATES.env.filters["date_es"] = _human_date


def current_user(request: Request) -> dict | None:
    return auth.current_user(request)


def require_business(request: Request, business_id: int) -> dict | None:
    user = current_user(request)
    if not user or user["business_id"] != business_id:
        return None
    return db.get_business(business_id)


def _host_parts(value: str) -> tuple[str, int | None]:
    """Normaliza un ``Host`` sin confiar en comparaciones de texto literales."""
    try:
        parsed = urlsplit(f"//{value}")
        return (parsed.hostname or "").lower(), parsed.port
    except ValueError:
        return "", None


def _trusted_origin(request: Request, origin: str) -> bool:
    """Acepta el origen público aunque Railway entregue un Host interno.

    El navegador ve ``bynoesis.com``, pero el proxy puede reenviar la petición al
    contenedor con el dominio privado de Railway. Ambos extremos deben estar en
    listas configuradas; nunca se confía en ``X-Forwarded-Host`` aportado por el
    cliente ni se abre un comodín de orígenes.
    """
    try:
        parsed = urlsplit(origin)
        origin_host = (parsed.hostname or "").lower()
        origin_port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme not in {"http", "https"}
        or not origin_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return False

    request_host, request_port = _host_parts(request.headers.get("host", ""))
    if not request_host:
        return False
    allowed_request_hosts = {
        host.lower() for host in config.ALLOWED_HOSTS if host and host != "*"
    }
    if config.IS_PRODUCTION and request_host not in allowed_request_hosts:
        return False

    # Mismo host: conserva la semántica same-origin y admite el puerto HTTPS
    # explícito que algunos proxies añaden al Host.
    if origin_host == request_host:
        default_port = 443 if parsed.scheme == "https" else 80
        if origin_port is not None and request_port not in {origin_port, None}:
            return False
        if request_port is not None and origin_port is None and request_port != default_port:
            return False
        return not config.IS_PRODUCTION or parsed.scheme == "https"

    if not config.IS_PRODUCTION:
        return False

    # Salto legítimo del proxy: el origen solo puede ser el público de Noesis,
    # siempre HTTPS estándar, y el Host interno también debe estar autorizado.
    public_hosts = {
        (urlsplit(config.BASE_URL).hostname or "").lower(),
        config.CANONICAL_PUBLIC_HOST.lower(),
        config.PUBLIC_HOST_ALIAS.lower(),
    }
    return (
        parsed.scheme == "https"
        and origin_port in {None, 443}
        and origin_host in public_hosts
        and request_host in allowed_request_hosts
    )


def csrf_response(request: Request) -> JSONResponse | None:
    path = request.url.path
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if path.startswith("/webhook/"):
        return None
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()
    if fetch_site == "cross-site":
        return JSONResponse({"error": "petición cross-site rechazada"}, status_code=403)
    # ``Sec-Fetch-Site`` es una cabecera controlada por el navegador. Chrome la
    # envía en formularios normales y describe mejor el origen visto por el usuario
    # que el Host interno que Railway entregue al contenedor. Priorizar
    # ``same-origin`` evita falsos 403 sin abrir formularios a otra web. Navegadores
    # antiguos o clientes que no la envían siguen pasando por la allowlist estricta.
    if fetch_site == "same-origin":
        return None
    if origin and not _trusted_origin(request, origin):
        return JSONResponse({"error": "origen no autorizado"}, status_code=403)
    return None


def required_entitlement(path: str, business_id: int) -> str | None:
    """Traduce rutas vendidas como modulo a una capacidad comprobable."""
    web_prefix = f"/b/{business_id}/"
    api_prefix = f"/api/{business_id}/"
    if path.startswith(web_prefix):
        area = path[len(web_prefix):].split("/", 1)[0]
        return {
            "proyectos": billing_adapter.ENTITLEMENT_PROJECTS,
            "equipo": billing_adapter.ENTITLEMENT_TEAM,
            "clockin-policy": billing_adapter.ENTITLEMENT_TEAM,
            "gestoria": billing_adapter.ENTITLEMENT_GESTORIA,
            "analisis": billing_adapter.ENTITLEMENT_ADVANCED_ANALYSIS,
        }.get(area)
    if not path.startswith(api_prefix):
        return None
    parts = path[len(api_prefix):].strip("/").split("/")
    area = parts[0] if parts else ""
    if area == "projects":
        return billing_adapter.ENTITLEMENT_PROJECTS
    if area == "workers":
        return billing_adapter.ENTITLEMENT_TEAM
    if area == "gestoria":
        return billing_adapter.ENTITLEMENT_GESTORIA
    if area in {"analysis", "forecast", "pnl"}:
        return billing_adapter.ENTITLEMENT_ADVANCED_ANALYSIS
    if area == "jobs" and len(parts) >= 3:
        if parts[2] == "project":
            return billing_adapter.ENTITLEMENT_PROJECTS
        if parts[2] == "assign":
            return billing_adapter.ENTITLEMENT_TEAM
    return None


async def auth_guard(request: Request, call_next):
    path = request.url.path
    csrf_error = csrf_response(request)
    if csrf_error is not None:
        return csrf_error

    if path.startswith("/b/") or path.startswith("/api/"):
        user = current_user(request)
        if not user:
            request.session.clear()
            if path.startswith("/api/"):
                return JSONResponse({"error": "no autenticado"}, status_code=401)
            return RedirectResponse("/login")
        parts = path.split("/")
        try:
            wanted = int(parts[2])
        except (IndexError, ValueError):
            wanted = None
        own_business_id = user["business_id"]
        if wanted is not None and own_business_id != wanted:
            if path.startswith("/api/"):
                return JSONResponse({"error": "no autorizado"}, status_code=403)
            return RedirectResponse(f"/b/{own_business_id}/resumen")
        # La plantilla base necesita saber si quien mira es administracion, para
        # ofrecerle la entrada al panel interno. Es solo para pintar un enlace: el
        # permiso real lo vuelve a comprobar `routers.admin._is_admin` contra la
        # base de datos y, en produccion, exige ademas sesion de Google.
        request.state.is_admin = bool(user.get("is_admin")) or config.is_admin_email(
            user.get("email")
        )
        business = db.get_business(own_business_id)
        entitlements = billing_adapter.entitlements_for(business)
        request.state.entitlements = entitlements
        required = required_entitlement(path, own_business_id)
        if required and required not in entitlements:
            plan = billing_adapter.minimum_plan_for(required)
            if path.startswith("/api/"):
                return JSONResponse(
                    {
                        "error": (
                            f"{billing_adapter.ENTITLEMENT_LABELS[required]} "
                            "no está incluido en tu plan actual."
                        ),
                        "code": "plan_upgrade_required",
                        "required_plan": plan,
                        "subscription_url": (
                            f"/b/{own_business_id}/suscripcion?plan={plan}"
                            f"&status=upgrade&feature={required}"
                        ),
                    },
                    status_code=403,
                )
            return RedirectResponse(
                f"/b/{own_business_id}/suscripcion?plan={plan}"
                f"&status=upgrade&feature={required}",
                status_code=303,
            )
        is_demo = bool(business and business.get("is_demo"))
        allowed_when_blocked = (
            not is_demo
            and (
                path.startswith(f"/b/{own_business_id}/suscripcion")
                or path == f"/b/{own_business_id}/account/delete"
                or path == f"/api/{own_business_id}/export"
            )
        )
        can_write = db.subscription_allows_access(business)
        request.state.subscription_read_only = not can_write
        safe_read = request.method in {"GET", "HEAD", "OPTIONS"}
        demo_readonly_chat = (
            is_demo
            and request.method == "POST"
            and path == f"/api/{own_business_id}/chat"
        )
        if (
            not can_write
            and not safe_read
            and not allowed_when_blocked
            and not demo_readonly_chat
        ):
            if is_demo:
                if path.startswith("/api/"):
                    return JSONResponse(
                        {
                            "error": "La demostración es de solo lectura.",
                            "code": "demo_read_only",
                        },
                        status_code=403,
                    )
                return RedirectResponse(
                    f"/b/{own_business_id}/resumen?demo=readonly",
                    status_code=303,
                )
            if path.startswith("/api/"):
                return JSONResponse(
                    {
                        "error": (
                            "Tu panel está en modo consulta. Activa una suscripción "
                            "para crear, cambiar o enviar."
                        ),
                        "code": "subscription_required",
                        "subscription_url": f"/b/{own_business_id}/suscripcion",
                    },
                    status_code=402,
                )
            return RedirectResponse(
                f"/b/{own_business_id}/suscripcion?status=readonly",
                status_code=303,
            )
    return await call_next(request)


async def _read_json(request: Request) -> dict:
    declared = request.headers.get("content-length")
    if declared:
        try:
            declared_size = int(declared)
        except ValueError as exc:
            raise ValueError("Content-Length no es válido.") from exc
        if declared_size > config.MAX_JSON_BYTES:
            raise ValueError("La petición es demasiado grande.")
    raw = await request.body()
    if len(raw) > config.MAX_JSON_BYTES:
        raise ValueError("La petición es demasiado grande.")
    try:
        data = json.loads(raw or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("El JSON no es válido.") from exc
    if not isinstance(data, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON.")
    return data
