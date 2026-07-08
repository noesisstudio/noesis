"""Acceso único a SQLite/Postgres con aislamiento multiempresa.

Cada autónomo que se da de alta es un "business". Todos sus datos (clientes,
agenda, facturas, gastos) van marcados con su business_id, de modo que los datos
de un cliente nunca se mezclan con los de otro.

Postgres se activa con ``DATABASE_URL``. SQLite se mantiene como fallback local.
El esquema no se crea aquí: lo gestionan las migraciones versionadas.
"""

from __future__ import annotations

import json
import logging
import math
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from . import config
from .clockin_integrity import clockin_seal
from . import verifactu

log = logging.getLogger("noesis.db")

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # SQLite local no necesita cargar el driver.
    psycopg = None
    dict_row = None


IntegrityError = (
    (sqlite3.IntegrityError, psycopg.IntegrityError)
    if psycopg
    else (sqlite3.IntegrityError,)
)
DatabaseError = (
    (sqlite3.Error, psycopg.Error) if psycopg else (sqlite3.Error,)
)


class Record(dict):
    """Fila común: acceso por nombre y compatibilidad puntual por índice."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def _normalise_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _normalise_row(row) -> Record | None:
    if row is None:
        return None
    if isinstance(row, dict):
        values = row.items()
    elif hasattr(row, "keys"):
        values = ((key, row[key]) for key in row.keys())
    else:
        values = ((str(index), value) for index, value in enumerate(row))
    return Record((key, _normalise_value(value)) for key, value in values)


class Cursor:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self) -> Record | None:
        return _normalise_row(self._cursor.fetchone())

    def fetchall(self) -> list[Record]:
        return [_normalise_row(row) for row in self._cursor.fetchall()]


class Connection:
    def __init__(self, raw, dialect: str):
        self.raw = raw
        self.dialect = dialect

    def execute(self, sql: str, params=()) -> Cursor:
        if self.dialect == "postgres":
            if sql.strip().upper() == "BEGIN IMMEDIATE":
                sql = "SELECT 1"
            sql = sql.replace("?", "%s")
        return Cursor(self.raw.execute(sql, params))

    def executescript(self, script: str) -> None:
        if self.dialect == "sqlite":
            self.raw.executescript(script)
            return
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        self.raw.close()


@contextmanager
def get_conn():
    """Abre la BD configurada, confirma al salir y siempre cierra."""
    if config.DATABASE_URL:
        if psycopg is None:
            raise RuntimeError(
                "DATABASE_URL está configurada pero falta psycopg."
            )
        raw = psycopg.connect(config.DATABASE_URL, row_factory=dict_row)
        conn = Connection(raw, "postgres")
    else:
        raw = sqlite3.connect(config.DB_PATH)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        raw.execute("PRAGMA busy_timeout = 10000")
        raw.execute("PRAGMA journal_mode = WAL")
        conn = Connection(raw, "sqlite")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(*, auto_migrate: bool | None = None) -> None:
    """Prepara SQLite local o valida que Postgres ya fue migrada en pre-deploy."""
    from . import migrations

    if auto_migrate is None:
        auto_migrate = not bool(config.DATABASE_URL)
    if auto_migrate:
        migrations.upgrade()
    elif not migrations.is_current():
        raise RuntimeError(
            "El esquema no está actualizado. Ejecuta: python -m noesis.migrations upgrade"
        )
    _backfill_phone_norms()


def reset_db() -> None:
    if config.DATABASE_URL:
        raise RuntimeError("No se permite reset_db sobre Postgres.")
    Path(config.DB_PATH).unlink(missing_ok=True)
    init_db()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _positive_money(value, label: str) -> float:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} debe ser un número.") from exc
    if not number.is_finite() or number <= 0 or number > Decimal("10000000"):
        raise ValueError(f"{label} debe ser mayor que 0 y tener un importe válido.")
    return float(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _tax_amount(base, rate) -> float:
    """Redondea importes fiscales al céntimo con criterio comercial."""
    amount = (
        Decimal(str(base))
        * Decimal(str(rate or 0))
        / Decimal("100")
    )
    return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _tax_rate(value, label: str, allowed: set[float]) -> float:
    try:
        rate = float(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} no es válido.") from exc
    if not math.isfinite(rate) or rate not in allowed:
        values = ", ".join(str(int(v)) for v in sorted(allowed))
        raise ValueError(f"{label} debe ser uno de estos valores: {values}.")
    return rate


# --------------------------------------------------------------- Negocios ---
def create_business(name, owner_email=None, sector=None) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO businesses (name, owner_email, sector, created_at) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            (name, owner_email, sector, _now()),
        ).fetchone()
        new_id = row["id"]
    return get_business(new_id)


def get_business(business_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
        return dict(row) if row else None


def normalize_phone(phone: str) -> str:
    """Deja solo dígitos y se queda con los últimos 9 (España), para comparar
    teléfonos escritos de mil formas (+34 600..., 0034..., 600 00 00 00)."""
    digits = "".join(c for c in (phone or "") if c.isdigit())
    return digits[-9:] if len(digits) >= 9 else digits


def _backfill_phone_norms() -> None:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, whatsapp_phone FROM businesses "
            "WHERE whatsapp_phone IS NOT NULL AND whatsapp_phone_norm IS NULL"
        ).fetchall()
        for row in rows:
            norm = normalize_phone(row["whatsapp_phone"])
            if not norm:
                continue
            try:
                conn.execute(
                    "UPDATE businesses SET whatsapp_phone_norm=? WHERE id=?",
                    (norm, row["id"]),
                )
            except IntegrityError:
                log.error(
                    "El teléfono de WhatsApp está duplicado en el negocio %s.",
                    row["id"],
                )


def get_business_by_phone(phone: str) -> dict | None:
    """Encuentra el negocio cuyo WhatsApp coincide con el teléfono que escribe."""
    target = normalize_phone(phone)
    if not target:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM businesses WHERE whatsapp_phone_norm=?",
            (target,),
        ).fetchone()
        return dict(row) if row else None


def list_businesses() -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM businesses ORDER BY id").fetchall()]


def set_whatsapp_status(business_id, status, phone=None) -> dict:
    if status not in {"no_conectado", "pendiente", "conectado"}:
        raise ValueError("Estado de WhatsApp no válido.")
    with get_conn() as conn:
        if phone is not None:
            norm = normalize_phone(phone)
            if status == "conectado" and len(norm) != 9:
                raise ValueError("El teléfono debe tener 9 dígitos.")
            conn.execute("UPDATE businesses SET whatsapp_status=?, whatsapp_phone=? "
                         ", whatsapp_phone_norm=? WHERE id=?",
                         (status, phone, norm or None, business_id))
        else:
            conn.execute("UPDATE businesses SET whatsapp_status=? WHERE id=?",
                         (status, business_id))
    return get_business(business_id)


def finish_onboarding(business_id) -> dict:
    with get_conn() as conn:
        conn.execute("UPDATE businesses SET onboarding_done=TRUE WHERE id=?", (business_id,))
    return get_business(business_id)


def update_payment_details(business_id, *, iban=None, bizum=None, note=None) -> dict:
    """Guarda cómo quiere cobrar el negocio: IBAN, Bizum y una nota libre.

    Se muestra en el PDF de la factura y en el portal del cliente para que el
    cliente sepa pagar sin tener que preguntar. Validación ligera y tolerante:
    lo que no cuadra se rechaza con un mensaje claro, no se corrompe.
    """
    clean_iban = (iban or "").replace(" ", "").upper().strip()
    if clean_iban:
        if not re.fullmatch(r"[A-Z]{2}[0-9A-Z]{13,32}", clean_iban):
            raise ValueError("El IBAN no tiene un formato válido.")
    clean_bizum = re.sub(r"[^\d+]", "", (bizum or "").strip())
    if clean_bizum and not re.fullmatch(r"\+?\d{9,15}", clean_bizum):
        raise ValueError("El número de Bizum debe ser un teléfono válido.")
    clean_note = (note or "").strip()[:300]
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET payment_iban=?, payment_bizum=?, payment_note=? "
            "WHERE id=?",
            (clean_iban or None, clean_bizum or None, clean_note or None, business_id),
        )
    return get_business(business_id)


# ----------------------------------------------------------------- Gestoría ---
GESTORIA_CADENCES = {"off", "mensual", "trimestral"}


def update_gestoria_settings(business_id, *, name=None, email=None,
                             cadence="off") -> dict | None:
    """Configura la gestoría del negocio. Al activarla se garantiza el token."""
    cadence = (cadence or "off").strip().lower()
    if cadence not in GESTORIA_CADENCES:
        raise ValueError("La cadencia debe ser mensual, trimestral u off.")
    name = (name or "").strip()[:120] or None
    email = (email or "").strip().lower()[:200] or None
    if cadence != "off":
        if not email or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError(
                "Indica el email de la gestoría para poder avisarla."
            )
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE businesses SET gestoria_name=?, gestoria_email=?, "
            "gestoria_cadence=? WHERE id=?",
            (name, email, cadence, business_id),
        )
        if cur.rowcount != 1:
            return None
    if cadence != "off":
        get_or_create_gestoria_token(business_id)
    return get_business(business_id)


def get_or_create_gestoria_token(business_id) -> str | None:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT gestoria_token FROM businesses WHERE id=?" + lock,
            (business_id,),
        ).fetchone()
        if not row:
            return None
        if row["gestoria_token"]:
            return row["gestoria_token"]
        token = secrets.token_urlsafe(24)
        conn.execute(
            "UPDATE businesses SET gestoria_token=? WHERE id=?",
            (token, business_id),
        )
        return token


def revoke_gestoria_token(business_id) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET gestoria_token=NULL WHERE id=?",
            (business_id,),
        )


def resolve_gestoria_token(token: str) -> dict | None:
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM businesses WHERE gestoria_token=?",
            (token,),
        ).fetchone()
        return dict(row) if row else None


def gestoria_period_range(label: str) -> tuple[str, str]:
    """'2026-06' → mes natural; '2026-T2' → trimestre. Valida el formato."""
    label = (label or "").strip()
    match_month = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", label)
    if match_month:
        year, month = int(match_month.group(1)), int(match_month.group(2))
        start = date(year, month, 1)
        end = (
            date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        ) - timedelta(days=1)
        return start.isoformat(), end.isoformat()
    match_quarter = re.fullmatch(r"(\d{4})-T([1-4])", label)
    if match_quarter:
        year, quarter = int(match_quarter.group(1)), int(match_quarter.group(2))
        start = date(year, 3 * quarter - 2, 1)
        end_month = 3 * quarter
        end = (
            date(year + 1, 1, 1) if end_month == 12
            else date(year, end_month + 1, 1)
        ) - timedelta(days=1)
        return start.isoformat(), end.isoformat()
    raise ValueError("Período no válido.")


def _closed_period_labels(cadence: str, count: int, today: date) -> list[str]:
    labels = []
    if cadence == "trimestral":
        year, quarter = today.year, (today.month - 1) // 3 + 1
        for _ in range(count):
            quarter -= 1
            if quarter == 0:
                quarter, year = 4, year - 1
            labels.append(f"{year}-T{quarter}")
    else:
        year, month = today.year, today.month
        for _ in range(count):
            month -= 1
            if month == 0:
                month, year = 12, year - 1
            labels.append(f"{year}-{month:02d}")
    return labels


def gestoria_invoices_in(business_id, start: str, end: str) -> list[dict]:
    return [
        invoice for invoice in list_invoices(business_id)
        if invoice.get("status") in ("enviada", "parcial", "cobrada")
        and start <= str(invoice.get("issued_at") or "")[:10] <= end
    ]


def gestoria_expenses_in(business_id, start: str, end: str) -> list[dict]:
    out = []
    for expense in list_expenses(business_id):
        day = str(expense.get("spent_on") or expense.get("created_at") or "")[:10]
        if start <= day <= end:
            out.append(expense)
    return out


def gestoria_received_in(business_id, start: str, end: str) -> list[dict]:
    out = []
    for received in list_received_invoices(business_id):
        day = str(received.get("issued_on") or received.get("created_at") or "")[:10]
        if start <= day <= end:
            out.append(received)
    return out


def gestoria_periods(business_id, count: int = 8) -> list[dict]:
    """Últimos períodos cerrados según la cadencia, con recuentos."""
    business = get_business(business_id)
    if not business:
        return []
    cadence = business.get("gestoria_cadence") or "off"
    if cadence == "off":
        return []
    periods = []
    for label in _closed_period_labels(cadence, count, date.today()):
        start, end = gestoria_period_range(label)
        invoices = gestoria_invoices_in(business_id, start, end)
        expenses = gestoria_expenses_in(business_id, start, end)
        periods.append({
            "label": label, "start": start, "end": end,
            "invoices": len(invoices), "expenses": len(expenses),
        })
    return periods


def parse_payment_reminder_days(value) -> list[int]:
    """Normaliza una cadencia corta, ordenada y segura para el scheduler."""
    if isinstance(value, (list, tuple, set)):
        parts = list(value)
    else:
        parts = str(value or "").replace(";", ",").split(",")
    try:
        days = sorted({int(str(part).strip()) for part in parts if str(part).strip()})
    except (TypeError, ValueError) as exc:
        raise ValueError("La cadencia debe contener días separados por comas.") from exc
    if not days or len(days) > 6 or any(day < 1 or day > 90 for day in days):
        raise ValueError("Indica entre 1 y 6 días, del 1 al 90.")
    return days


def payment_reminder_days(business: dict | None) -> list[int]:
    try:
        return parse_payment_reminder_days(
            (business or {}).get("payment_reminder_days") or "3,7,15"
        )
    except ValueError:
        return [3, 7, 15]


def update_payment_reminder_settings(
    business_id: int,
    *,
    enabled: bool,
    days,
) -> dict | None:
    cadence = parse_payment_reminder_days(days)
    with get_conn() as conn:
        updated = conn.execute(
            "UPDATE businesses SET payment_reminders_enabled=?, "
            "payment_reminder_days=? WHERE id=?",
            (bool(enabled), ",".join(str(day) for day in cadence), business_id),
        )
        if updated.rowcount != 1:
            return None
    return get_business(business_id)


def update_fiscal(business_id, name=None, nif=None, address=None,
                  default_vat=None, default_irpf=None) -> dict:
    """Actualiza los datos fiscales del negocio (NIF, dirección, IVA/IRPF por defecto)."""
    if default_vat is not None:
        default_vat = _tax_rate(default_vat, "El IVA", {0, 4, 10, 21})
    if default_irpf is not None:
        default_irpf = _tax_rate(default_irpf, "El IRPF", {0, 7, 15})
    fields, params = [], []
    for col, val in [("name", name), ("nif", nif), ("address", address),
                     ("default_vat", default_vat), ("default_irpf", default_irpf)]:
        if val is not None and val != "":
            fields.append(f"{col}=?")
            params.append(val)
    if fields:
        params.append(business_id)
        with get_conn() as conn:
            conn.execute(f"UPDATE businesses SET {', '.join(fields)} WHERE id=?", params)
    return get_business(business_id)


def update_business_profile(business_id, *, sector=None, team_size=None,
                            province=None, primary_goal=None) -> dict | None:
    """Guarda la segmentación mínima que personaliza el producto y permite medir
    qué perfiles se activan y retienen mejor."""
    allowed_team_sizes = {"solo", "2-5", "6-10", "11+"}
    allowed_goals = {"facturar", "agenda", "cobros", "control"}
    if team_size not in allowed_team_sizes:
        raise ValueError("El tamaño del equipo no es válido.")
    if primary_goal not in allowed_goals:
        raise ValueError("El objetivo principal no es válido.")
    sector = (sector or "").strip()
    if not sector:
        raise ValueError("El sector es obligatorio.")
    province = (province or "").strip()[:80] or None
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET sector=?, team_size=?, province=?, primary_goal=? "
            "WHERE id=?",
            (sector[:80], team_size, province, primary_goal, business_id),
        )
    return get_business(business_id)


def record_product_event(business_id: int, event_name: str,
                         event_data: str | None = None) -> None:
    """Analítica propia y mínima del ciclo SaaS; no incluye datos operativos."""
    event_name = (event_name or "").strip()
    if not event_name or len(event_name) > 80:
        raise ValueError("El nombre del evento no es válido.")
    if event_data is not None and len(event_data) > 500:
        raise ValueError("Los datos del evento son demasiado largos.")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO product_events "
            "(business_id, event_name, event_data, created_at) VALUES (?, ?, ?, ?)",
            (business_id, event_name, event_data, _now()),
        )


def count_product_events(business_id: int, event_name: str,
                         since: str | None = None) -> int:
    """Cuántas veces ha ocurrido un evento (opcionalmente desde una fecha ISO)."""
    q = ("SELECT COUNT(*) AS n FROM product_events "
         "WHERE business_id=? AND event_name=?")
    params: list = [business_id, event_name]
    if since:
        q += " AND CAST(created_at AS TEXT) >= ?"
        params.append(since)
    with get_conn() as conn:
        return int(conn.execute(q, params).fetchone()["n"])


def activation_snapshot(business_id: int) -> dict:
    """Estado de activación basado en resultados reales, no en visitas o clics.

    Activado = ya existe cliente + trabajo/presupuesto + factura. Cobrar la primera
    factura es el primer resultado económico y se muestra como fase posterior.
    """
    business = get_business(business_id)
    if not business:
        raise ValueError("Negocio no encontrado.")
    with get_conn() as conn:
        counts = conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM clients WHERE business_id=?) AS clients, "
            "(SELECT COUNT(*) FROM jobs WHERE business_id=?) AS jobs, "
            "(SELECT COUNT(*) FROM quotes WHERE business_id=?) AS quotes, "
            "(SELECT COUNT(*) FROM invoices WHERE business_id=?) AS invoices, "
            "(SELECT COUNT(*) FROM invoices WHERE business_id=? "
            " AND status='cobrada') AS paid",
            (business_id, business_id, business_id, business_id, business_id),
        ).fetchone()
    profile_done = bool(
        business.get("sector")
        and business.get("team_size")
        and business.get("primary_goal")
    )
    has_client = counts["clients"] > 0
    has_work = counts["jobs"] > 0 or counts["quotes"] > 0
    has_invoice = counts["invoices"] > 0
    has_paid = counts["paid"] > 0
    steps = [
        {
            "key": "profile",
            "label": "Personaliza tu negocio",
            "detail": "Sector, tamaño y objetivo principal",
            "done": profile_done,
            "href": f"/onboarding/setup/{business_id}",
        },
        {
            "key": "whatsapp",
            "label": "Conecta WhatsApp",
            "detail": "Gestiona el día desde el móvil",
            "done": business.get("whatsapp_status") == "conectado",
            "href": f"/b/{business_id}/ajustes",
        },
        {
            "key": "client",
            "label": "Añade tu primer cliente",
            "detail": "Crea una ficha para empezar el flujo",
            "done": has_client,
            "href": f"/b/{business_id}/clientes",
        },
        {
            "key": "work",
            "label": "Registra un trabajo o presupuesto",
            "detail": "Pasa de petición a trabajo organizado",
            "done": has_work,
            "href": f"/b/{business_id}/agenda",
        },
        {
            "key": "invoice",
            "label": "Prepara tu primera factura",
            "detail": "Convierte el trabajo terminado en facturación",
            "done": has_invoice,
            "href": f"/b/{business_id}/facturas",
        },
        {
            "key": "payment",
            "label": "Registra tu primer cobro",
            "detail": "Cierra el ciclo con dinero cobrado",
            "done": has_paid,
            "href": f"/b/{business_id}/cobros",
        },
    ]
    completed = sum(1 for step in steps if step["done"])
    first_pending = next((step for step in steps if not step["done"]), None)
    activated = has_client and has_work and has_invoice
    return {
        "steps": steps,
        "completed": completed,
        "total": len(steps),
        "progress": round(completed / len(steps) * 100),
        "activated": activated,
        "first_value": activated,
        "outcome_reached": has_paid,
        "next_step": first_pending,
    }


# --------------------------------------------------------- Marca / plantillas ---
BRAND_COLOR_DEFAULT = "#14463b"
INVOICE_TEMPLATES = {"clasica", "minimal", "editorial"}
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_LOGO_B64 = 400_000  # ~300 KB de imagen


def business_initials(name: str | None) -> str:
    """Iniciales para el monograma automático (cuando el negocio no sube logo)."""
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    if not parts:
        return "N"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def business_brand_color(business: dict | None) -> str:
    """Color de marca del negocio, con el verde Noesis como valor por defecto."""
    color = (business or {}).get("brand_color")
    return color if color and _HEX_RE.match(color) else BRAND_COLOR_DEFAULT


# ----------------------------------------------------- Panel personalizable ---
# Bloques del inicio que el autónomo puede ordenar y ocultar a su gusto.
# El orden de esta tupla es la disposición por defecto (recomendada por Noesis).
PANEL_BLOCKS = (
    ("foco", "Lo primero hoy"),
    ("pulso", "Pulso del negocio"),
    ("kpis", "Indicadores del mes"),
    ("balance", "Balance · tu posición"),
    ("hoy", "Trabajos de hoy"),
    ("grafica", "Gráfica y plan del día"),
    ("detalle", "Clientes, gastos y cobros"),
)
PANEL_BLOCK_KEYS = tuple(k for k, _ in PANEL_BLOCKS)


def resolve_panel_layout(business: dict | None) -> dict:
    """Devuelve la disposición del panel de un negocio, siempre válida y completa.

    Tolera datos corruptos o de versiones antiguas: parte del orden por defecto,
    respeta lo que el usuario haya guardado y descarta claves desconocidas."""
    order: list[str] = []
    hidden: set[str] = set()
    raw = (business or {}).get("panel_layout")
    if raw:
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, dict):
                for key in data.get("order", []):
                    if key in PANEL_BLOCK_KEYS and key not in order:
                        order.append(key)
                hidden = {k for k in data.get("hidden", []) if k in PANEL_BLOCK_KEYS}
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    # Los bloques nuevos o ausentes se añaden al final en su orden canónico.
    for key in PANEL_BLOCK_KEYS:
        if key not in order:
            order.append(key)
    return {"order": order, "hidden": sorted(hidden)}


def update_panel_layout(business_id, order, hidden) -> dict:
    """Guarda cómo el negocio ordena y oculta los bloques de su inicio."""
    seen: list[str] = []
    for key in order or []:
        if key in PANEL_BLOCK_KEYS and key not in seen:
            seen.append(key)
    for key in PANEL_BLOCK_KEYS:  # completa por si el cliente manda una lista parcial
        if key not in seen:
            seen.append(key)
    hidden_clean = sorted({k for k in (hidden or []) if k in PANEL_BLOCK_KEYS})
    payload = json.dumps({"order": seen, "hidden": hidden_clean})
    with get_conn() as conn:
        conn.execute("UPDATE businesses SET panel_layout=? WHERE id=?",
                     (payload, business_id))
    return get_business(business_id)


def update_branding(business_id, *, template=None, brand_color=None,
                    logo_data=None, logo_mime=None, clear_logo=False) -> dict | None:
    """Guarda la personalización de documentos: plantilla, color y logo/monograma."""
    fields: list[str] = []
    params: list = []
    if template is not None:
        if template not in INVOICE_TEMPLATES:
            raise ValueError("La plantilla seleccionada no es válida.")
        fields.append("invoice_template=?")
        params.append(template)
    if brand_color is not None:
        color = (brand_color or "").strip()
        if color and not _HEX_RE.match(color):
            raise ValueError("El color de marca debe ser un hexadecimal tipo #14463b.")
        fields.append("brand_color=?")
        params.append(color or None)
    if clear_logo:
        fields += ["logo_data=?", "logo_mime=?"]
        params += [None, None]
    elif logo_data is not None:
        if len(logo_data) > MAX_LOGO_B64:
            raise ValueError("El logo es demasiado grande (máximo ~300 KB).")
        fields += ["logo_data=?", "logo_mime=?"]
        params += [logo_data, logo_mime]
    if not fields:
        return get_business(business_id)
    params.append(business_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE businesses SET {', '.join(fields)} WHERE id=?", params)
    return get_business(business_id)


# ----------------------------------------------- Ledger del copiloto (consejos) ---
# Cierra el bucle del consejo: lo que Noesis RECOMIENDA, lo que el autónomo ACEPTA
# (entra a la acción) y lo que COMPLETA. Permite medir si el copiloto sirve y
# enseñarle al autónomo qué hizo con lo que le sugerimos.
REC_STATES = {"recomendado", "aceptado", "completado", "descartado"}
_REC_ACTIVE = ("recomendado", "aceptado")


def get_recommendation(rec_id, business_id) -> dict | None:
    sql = "SELECT * FROM copilot_recommendations WHERE id=? AND business_id=?"
    params = [rec_id, business_id]
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def record_recommendation(business_id: int, topic: str, summary: str) -> dict:
    """Registra una recomendación como 'recomendado'. Idempotente: si ya hay una
    activa (recomendado/aceptado) con el mismo tema y texto, la reutiliza para no
    duplicar el plan en cada visita."""
    topic = (topic or "general").strip()[:40]
    summary = (summary or "").strip()[:300]
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM copilot_recommendations WHERE business_id=? AND topic=? "
            "AND summary=? AND status IN ('recomendado','aceptado') "
            "ORDER BY id DESC LIMIT 1",
            (business_id, topic, summary),
        ).fetchone()
        if row:
            return dict(row)
        row = conn.execute(
            "INSERT INTO copilot_recommendations "
            "(business_id, topic, summary, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'recomendado', ?, ?) RETURNING id",
            (business_id, topic, summary, now, now),
        ).fetchone()
        rec_id = row["id"]
    return get_recommendation(rec_id, business_id)


def set_recommendation_status(rec_id, business_id, status) -> dict | None:
    """Transición de estado, aislada por negocio."""
    if status not in REC_STATES:
        raise ValueError("Estado de recomendación no válido.")
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE copilot_recommendations SET status=?, updated_at=? "
            "WHERE id=? AND business_id=?",
            (status, _now(), rec_id, business_id),
        )
        if cur.rowcount == 0:
            return None
    return get_recommendation(rec_id, business_id)


def list_recommendations(business_id, status=None,
                         limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM copilot_recommendations WHERE business_id=?"
    params: list = [business_id]
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def recommendation_stats(business_id) -> dict:
    """Conteo por estado: cuántas se recomendaron, aceptaron y completaron."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM copilot_recommendations "
            "WHERE business_id=? GROUP BY status",
            (business_id,),
        ).fetchall()
    by = {r["status"]: r["n"] for r in rows}
    total = sum(by.values())
    return {
        "total": total,
        "recomendado": by.get("recomendado", 0),
        "aceptado": by.get("aceptado", 0),
        "completado": by.get("completado", 0),
        "descartado": by.get("descartado", 0),
    }


# ---------------------------------------------------------------- Usuarios ---
def create_user(email, password_hash, business_id) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO users (email, password_hash, business_id, created_at) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            (email.lower().strip(), password_hash, business_id, _now()),
        ).fetchone()
        new_id = row["id"]
    return get_user(new_id)


def create_account(name, email, password_hash, sector=None, trial_days: int = 14) -> tuple[dict, dict]:
    """Crea negocio y propietario en una sola transacción."""
    email = (email or "").strip().lower()
    ends = (date.today() + timedelta(days=trial_days)).isoformat()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise ValueError("Ya existe una cuenta con ese email.")
        row = conn.execute(
            "INSERT INTO businesses (name, owner_email, sector, created_at, plan, "
            "subscription_status, trial_ends_at) "
            "VALUES (?, ?, ?, ?, 'trial', 'trial', ?) RETURNING id",
            (name, email, sector, _now(), ends),
        ).fetchone()
        business_id = row["id"]
        user_row = conn.execute(
            "INSERT INTO users (email, password_hash, business_id, created_at) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            (email, password_hash, business_id, _now()),
        ).fetchone()
        user_id = user_row["id"]
    return get_business(business_id), get_user(user_id)


def get_user(user_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_email(email) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?",
                           (email.lower().strip(),)).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------- Clientes ---
def add_client(name, phone=None, address=None, zone=None, nif=None, email=None,
               *, business_id: int) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("El nombre del cliente es obligatorio.")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO clients (business_id, name, phone, address, zone, nif, email, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, name, phone, address, zone, nif, email, _now()),
        ).fetchone()
        new_id = row["id"]
    return get_client(new_id, business_id)


def import_clients(rows: list[dict], business_id: int) -> dict:
    """Alta en bloque de clientes (p. ej. pegados desde Excel o la agenda).

    Devuelve cuántos se crearon y cuántas líneas se ignoraron. Salta duplicados por
    nombre (para que reimportar no cree la cartera dos veces) y filas sin nombre.
    """
    created = 0
    skipped = 0
    existing = {c["name"].strip().lower() for c in list_clients(business_id)}
    for row in rows[:1000]:  # tope defensivo por si pegan un archivo enorme
        name = (str(row.get("name") or "")).strip()
        if not name or name.lower() in existing:
            skipped += 1
            continue
        add_client(
            name,
            phone=(str(row.get("phone") or "").strip() or None),
            email=(str(row.get("email") or "").strip() or None),
            nif=(str(row.get("nif") or "").strip() or None),
            zone=(str(row.get("zone") or "").strip() or None),
            address=(str(row.get("address") or "").strip() or None),
            business_id=business_id,
        )
        existing.add(name.lower())
        created += 1
    return {"created": created, "skipped": skipped}


# Conceptos frecuentes por oficio: para que la primera factura no parta de una hoja
# en blanco. Solo sugerencias editables; nunca imponen precio ni IVA.
INVOICE_CONCEPT_SUGGESTIONS: dict[str, list[str]] = {
    "Fontanería": [
        "Reparación de fuga", "Cambio de grifo", "Desatasco de tubería",
        "Instalación de sanitario", "Sustitución de calentador",
    ],
    "Electricidad": [
        "Reparación de avería eléctrica", "Instalación de puntos de luz",
        "Cambio de cuadro eléctrico", "Boletín de instalación",
        "Sustitución de mecanismos",
    ],
    "Reformas": [
        "Reforma de baño", "Reforma de cocina", "Alicatado y solado",
        "Pintura de vivienda", "Trabajos de albañilería",
    ],
    "Climatización": [
        "Instalación de aire acondicionado", "Mantenimiento de equipo",
        "Recarga de gas refrigerante", "Reparación de bomba de calor",
        "Limpieza de filtros y unidades",
    ],
    "Limpieza": [
        "Limpieza de fin de obra", "Limpieza periódica de local",
        "Limpieza de comunidad", "Limpieza de cristales",
        "Servicio de limpieza puntual",
    ],
    "Jardinería": [
        "Mantenimiento de jardín", "Poda de árboles y setos",
        "Siega y desbroce", "Diseño y plantación", "Sistema de riego",
    ],
    "Mantenimiento": [
        "Mantenimiento preventivo", "Reparación general", "Aviso urgente",
        "Revisión periódica", "Sustitución de piezas",
    ],
}
INVOICE_CONCEPTS_GENERIC = [
    "Mano de obra", "Desplazamiento", "Material y mano de obra",
    "Servicio profesional", "Trabajo realizado",
]


def invoice_concept_suggestions(business: dict | None) -> list[str]:
    """Sugerencias de concepto según el sector del negocio, con genéricas de apoyo."""
    sector = (business or {}).get("sector") or ""
    specific = INVOICE_CONCEPT_SUGGESTIONS.get(sector, [])
    return specific + INVOICE_CONCEPTS_GENERIC


def get_client(client_id, business_id) -> dict | None:
    sql = "SELECT * FROM clients WHERE id=? AND business_id=?"
    params = [client_id, business_id]
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def find_client(name, business_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE business_id=? AND LOWER(name)=LOWER(?) "
            "ORDER BY id LIMIT 1",
            (business_id, (name or "").strip()),
        ).fetchone()
        return dict(row) if row else None


def list_clients(business_id) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM clients WHERE business_id=? ORDER BY name",
            (business_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_or_create_client(name, business_id, **kw) -> dict:
    return find_client(name, business_id) or add_client(name, business_id=business_id, **kw)


def update_client(client_id, business_id, name=None, phone=None, address=None,
                  zone=None, nif=None, email=None) -> dict | None:
    fields, params = [], []
    for col, val in [("name", name), ("phone", phone), ("address", address),
                     ("zone", zone), ("nif", nif), ("email", email)]:
        if val is not None:
            fields.append(f"{col}=?")
            params.append(val)
    if fields:
        params += [client_id, business_id]
        with get_conn() as conn:
            conn.execute(f"UPDATE clients SET {', '.join(fields)} "
                         f"WHERE id=? AND business_id=?", params)
    return get_client(client_id, business_id)


def delete_client(client_id, business_id) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM clients WHERE id=? AND business_id=?",
                     (client_id, business_id))


# ------------------------------------------------------------------ Equipo ---
_WORKER_TOKEN_TTL_DAYS = 120
_WORKER_DEFAULT_COLOR = "#2e8b74"


def _worker_color(value: str | None) -> str:
    color = (value or _WORKER_DEFAULT_COLOR).strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("El color del trabajador no es válido.")
    return color.lower()


def _worker_phone(value: str | None) -> tuple[str | None, str | None]:
    phone = (value or "").strip()
    if not phone:
        return None, None
    norm = normalize_phone(phone)
    if len(norm) != 9:
        raise ValueError("El teléfono del trabajador debe tener 9 dígitos.")
    return phone, norm


def _worker_pin_hash(pin: str | None) -> str | None:
    clean_pin = (pin or "").strip()
    if clean_pin and (not clean_pin.isdigit() or not 4 <= len(clean_pin) <= 8):
        raise ValueError("El PIN debe tener entre 4 y 8 números.")
    if not clean_pin:
        return None
    from .web import auth
    return auth.hash_password(clean_pin)


def _worker_phone_in_use(
    conn, business_id: int, phone_norm: str | None, exclude_id: int | None = None
) -> bool:
    if not phone_norm:
        return False
    extra = " AND id<>?" if exclude_id is not None else ""
    params: list[Any] = [business_id, phone_norm]
    if exclude_id is not None:
        params.append(exclude_id)
    return bool(conn.execute(
        "SELECT 1 AS found FROM workers "
        "WHERE business_id=? AND phone_norm=?" + extra,
        tuple(params),
    ).fetchone())


def list_workers(business_id: int, *, include_inactive: bool = True) -> list[dict]:
    where = "" if include_inactive else " AND active=TRUE"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, business_id, name, phone, phone_norm, color, access_code, "
            "active, created_at, CASE WHEN pin_hash IS NULL THEN FALSE ELSE TRUE END "
            "AS has_pin FROM workers WHERE business_id=?" + where
            + " ORDER BY active DESC, name",
            (business_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_worker(worker_id: int, business_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT *, CASE WHEN pin_hash IS NULL THEN FALSE ELSE TRUE END AS has_pin "
            "FROM workers WHERE id=? AND business_id=?",
            (worker_id, business_id),
        ).fetchone()
        return dict(row) if row else None


def _new_worker_access_code(conn, business_id: int) -> str:
    for _ in range(20):
        code = secrets.token_hex(3).upper()
        exists = conn.execute(
            "SELECT 1 AS found FROM workers "
            "WHERE business_id=? AND access_code=?",
            (business_id, code),
        ).fetchone()
        if not exists:
            return code
    raise RuntimeError("No se pudo generar un código de acceso único.")


def create_worker(
    business_id: int,
    name: str,
    phone: str | None = None,
    color: str | None = None,
    pin: str | None = None,
) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("El nombre del trabajador es obligatorio.")
    if not get_business(business_id):
        raise ValueError("El negocio no existe.")
    phone, phone_norm = _worker_phone(phone)
    color = _worker_color(color)
    pin_hash = _worker_pin_hash(pin)
    with get_conn() as conn:
        if _worker_phone_in_use(conn, business_id, phone_norm):
            raise ValueError("Ese teléfono ya pertenece a otro trabajador.")
        access_code = _new_worker_access_code(conn, business_id)
        row = conn.execute(
            "INSERT INTO workers "
            "(business_id, name, phone, phone_norm, color, access_code, pin_hash, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                business_id, name[:120], phone, phone_norm, color,
                access_code, pin_hash, _now(),
            ),
        ).fetchone()
        worker_id = row["id"]
    return get_worker(worker_id, business_id)


def update_worker(
    worker_id: int,
    business_id: int,
    *,
    name: str | None = None,
    phone: str | None = None,
    color: str | None = None,
) -> dict | None:
    if not get_worker(worker_id, business_id):
        return None
    fields: list[str] = []
    params: list[Any] = []
    if name is not None:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("El nombre del trabajador es obligatorio.")
        fields.append("name=?")
        params.append(clean_name[:120])
    if phone is not None:
        clean_phone, phone_norm = _worker_phone(phone)
        fields.extend(("phone=?", "phone_norm=?"))
        params.extend((clean_phone, phone_norm))
    if color is not None:
        fields.append("color=?")
        params.append(_worker_color(color))
    if fields:
        params.extend((worker_id, business_id))
        with get_conn() as conn:
            if (
                phone is not None
                and _worker_phone_in_use(
                    conn, business_id, phone_norm, exclude_id=worker_id
                )
            ):
                raise ValueError("Ese teléfono ya pertenece a otro trabajador.")
            conn.execute(
                f"UPDATE workers SET {', '.join(fields)} "
                "WHERE id=? AND business_id=?",
                tuple(params),
            )
    return get_worker(worker_id, business_id)


def set_worker_active(worker_id: int, business_id: int, active: bool) -> dict | None:
    if not get_worker(worker_id, business_id):
        return None
    with get_conn() as conn:
        conn.execute(
            "UPDATE workers SET active=? WHERE id=? AND business_id=?",
            (bool(active), worker_id, business_id),
        )
        if not active:
            conn.execute(
                "UPDATE worker_tokens SET revoked=TRUE "
                "WHERE worker_id=? AND business_id=?",
                (worker_id, business_id),
            )
    return get_worker(worker_id, business_id)


def set_worker_pin(
    worker_id: int, business_id: int, pin: str | None
) -> dict | None:
    if not get_worker(worker_id, business_id):
        return None
    pin_hash = _worker_pin_hash(pin)
    with get_conn() as conn:
        conn.execute(
            "UPDATE workers SET pin_hash=? WHERE id=? AND business_id=?",
            (pin_hash, worker_id, business_id),
        )
    return get_worker(worker_id, business_id)


def bind_worker_phone(
    business_id: int, access_code: str, phone: str
) -> dict | None:
    """Vincula el teléfono que escribe por WhatsApp al trabajador del código."""
    clean_phone, phone_norm = _worker_phone(phone)
    code = (access_code or "").strip().upper()
    if not code:
        return None
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        worker = conn.execute(
            "SELECT id FROM workers WHERE business_id=? AND access_code=? "
            "AND active=TRUE",
            (business_id, code),
        ).fetchone()
        if not worker:
            return None
        duplicate = conn.execute(
            "SELECT id FROM workers WHERE business_id=? AND phone_norm=? "
            "AND id<>? AND active=TRUE",
            (business_id, phone_norm, worker["id"]),
        ).fetchone()
        if duplicate:
            raise ValueError("Ese teléfono ya pertenece a otro trabajador.")
        conn.execute(
            "UPDATE workers SET phone=?, phone_norm=? "
            "WHERE id=? AND business_id=?",
            (clean_phone, phone_norm, worker["id"], business_id),
        )
        worker_id = worker["id"]
    return get_worker(worker_id, business_id)


def get_worker_by_phone(phone: str) -> dict | None:
    """Resuelve una identidad de trabajador solo si el teléfono no es ambiguo."""
    phone_norm = normalize_phone(phone)
    if len(phone_norm) != 9:
        return None
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT *, CASE WHEN pin_hash IS NULL THEN FALSE ELSE TRUE END AS has_pin "
            "FROM workers WHERE phone_norm=? AND active=TRUE ORDER BY id",
            (phone_norm,),
        ).fetchall()
        return dict(rows[0]) if len(rows) == 1 else None


# ------------------------------------------------------------------ Agenda ---
def add_job(client_id, description, scheduled_for=None, zone=None,
            price_estimate=None, *, business_id: int) -> dict:
    if not get_client(client_id, business_id):
        raise ValueError("El cliente no pertenece a este negocio.")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO jobs (business_id, client_id, description, scheduled_for, "
            "zone, price_estimate, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, client_id, description, scheduled_for, zone,
             price_estimate, _now()),
        ).fetchone()
        new_id = row["id"]
    return get_job(new_id, business_id)


def get_job(job_id, business_id) -> dict | None:
    sql = (
        "SELECT j.*, w.name AS worker_name, w.color AS worker_color "
        "FROM jobs j LEFT JOIN workers w ON w.id=j.worker_id "
        "AND w.business_id=j.business_id WHERE j.id=? AND j.business_id=?"
    )
    params = [job_id, business_id]
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def update_job_status(job_id, status, business_id) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET status=? WHERE id=? AND business_id=?",
                     (status, job_id, business_id))


def delete_job(job_id, business_id) -> None:
    with get_conn() as conn:
        used = conn.execute(
            "SELECT 1 AS found FROM worker_clockins "
            "WHERE job_id=? AND business_id=? LIMIT 1",
            (job_id, business_id),
        ).fetchone()
        if used:
            raise ValueError(
                "El trabajo tiene fichajes y debe conservarse como justificante."
            )
        conn.execute("DELETE FROM jobs WHERE id=? AND business_id=?",
                     (job_id, business_id))


def jobs_for_date(day: str, business_id) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT j.*, c.name AS client_name, c.zone AS client_zone, "
            "w.name AS worker_name, w.color AS worker_color "
            "FROM jobs j LEFT JOIN clients c ON c.id = j.client_id "
            "AND c.business_id = j.business_id "
            "LEFT JOIN workers w ON w.id=j.worker_id "
            "AND w.business_id=j.business_id "
            "WHERE j.business_id=? AND CAST(j.scheduled_for AS TEXT) LIKE ? "
            "ORDER BY j.scheduled_for",
            (business_id, f"{day}%"),
        ).fetchall()
        return [dict(r) for r in rows]


def jobs_between(start: str, end: str, business_id) -> list[dict]:
    """Trabajos entre dos fechas ISO (para el calendario semanal)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT j.*, c.name AS client_name, w.name AS worker_name, "
            "w.color AS worker_color FROM jobs j "
            "LEFT JOIN clients c ON c.id = j.client_id "
            "AND c.business_id = j.business_id "
            "LEFT JOIN workers w ON w.id=j.worker_id "
            "AND w.business_id=j.business_id "
            "WHERE j.business_id=? AND j.scheduled_for >= ? AND j.scheduled_for <= ? "
            "ORDER BY j.scheduled_for",
            (business_id, start, end + "T23:59"),
        ).fetchall()
        return [dict(r) for r in rows]


def assign_job_worker(
    job_id: int, worker_id: int | None, business_id: int
) -> dict | None:
    job = get_job(job_id, business_id)
    if not job:
        return None
    if worker_id is not None:
        worker = get_worker(worker_id, business_id)
        if not worker or not worker.get("active"):
            raise ValueError("El trabajador no pertenece a este negocio o está inactivo.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET worker_id=? WHERE id=? AND business_id=?",
            (worker_id, job_id, business_id),
        )
    return get_job(job_id, business_id)


def jobs_for_worker(
    worker_id: int, business_id: int, day: str | None = None
) -> list[dict]:
    if not get_worker(worker_id, business_id):
        return []
    day_filter = (
        " AND CAST(j.scheduled_for AS TEXT) LIKE ?" if day is not None else ""
    )
    params: list[Any] = [business_id, worker_id]
    if day is not None:
        params.append(f"{day}%")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT j.*, c.name AS client_name, c.address AS client_address, "
            "c.zone AS client_zone, w.name AS worker_name, w.color AS worker_color "
            "FROM jobs j "
            "LEFT JOIN clients c ON c.id=j.client_id "
            "AND c.business_id=j.business_id "
            "JOIN workers w ON w.id=j.worker_id "
            "AND w.business_id=j.business_id "
            "WHERE j.business_id=? AND j.worker_id=?" + day_filter
            + " ORDER BY j.scheduled_for",
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]


# --------------------------------------------------------------- Fichajes ---
def _gps_value(value, label: str, lower: float, upper: float) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} no es válido.") from exc
    if not math.isfinite(number) or not lower <= number <= upper:
        raise ValueError(f"{label} está fuera de rango.")
    return number


def _parse_clockin_at(value: Any, label: str = "La fecha") -> str:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} no es válida.") from exc
    if parsed.tzinfo is not None:
        raise ValueError(f"{label} debe usar la hora local de la empresa.")
    return parsed.isoformat(timespec="seconds")


def _clockin_rows_with_corrections(
    conn, business_id: int, worker_id: int
) -> list[dict]:
    rows = conn.execute(
        "SELECT wc.*, cor.id AS correction_id, cor.status AS correction_status, "
        "cor.reason AS correction_reason, cor.old_at AS correction_old_at, "
        "cor.new_at AS correction_new_at, cor.created_at AS correction_created_at "
        "FROM worker_clockins wc "
        "LEFT JOIN worker_clockin_corrections cor ON cor.id=("
        "SELECT MAX(c2.id) FROM worker_clockin_corrections c2 "
        "WHERE c2.business_id=wc.business_id AND c2.clockin_id=wc.id"
        ") WHERE wc.business_id=? AND wc.worker_id=? ORDER BY wc.id",
        (business_id, worker_id),
    ).fetchall()
    result: list[dict] = []
    for raw in rows:
        item = dict(raw)
        item["annulled"] = item.get("correction_status") == "anulado"
        item["effective_at"] = (
            item.get("correction_new_at")
            if item.get("correction_status") == "corregido"
            else item.get("at")
        )
        result.append(item)
    return result


def worker_clockin_history(
    worker_id: int,
    business_id: int,
    *,
    from_day: str | None = None,
    to_day: str | None = None,
) -> list[dict]:
    if not get_worker(worker_id, business_id):
        return []
    with get_conn() as conn:
        records = _clockin_rows_with_corrections(conn, business_id, worker_id)
    start = datetime.fromisoformat(from_day) if from_day else None
    end = (
        datetime.fromisoformat(to_day) + timedelta(days=1)
        if to_day else None
    )
    filtered = []
    for record in records:
        display_at = record.get("effective_at") or record["at"]
        point = datetime.fromisoformat(str(display_at))
        if start and point < start:
            continue
        if end and point >= end:
            continue
        filtered.append(record)
    return sorted(
        filtered,
        key=lambda item: (str(item.get("effective_at") or item["at"]), item["id"]),
        reverse=True,
    )


def _active_clockin_records(records: list[dict]) -> list[dict]:
    return sorted(
        (record for record in records if not record.get("annulled")),
        key=lambda item: (str(item["effective_at"]), item["id"]),
    )


def _shift_state(records: list[dict]) -> dict:
    working = False
    paused = False
    entry = None
    for record in _active_clockin_records(records):
        action = record["action"]
        if action == "entrada" and not working:
            working, paused, entry = True, False, record
        elif action == "pausa" and working and not paused:
            paused = True
        elif action == "reanudar" and working and paused:
            paused = False
        elif action == "salida" and working:
            working, paused, entry = False, False, None
    return {"working": working, "paused": paused, "entry": entry}


def _worked_seconds_for_day(
    records: list[dict], day: str, now: datetime | None = None
) -> float:
    now = now or datetime.now()
    day_start = datetime.fromisoformat(day)
    day_end = day_start + timedelta(days=1)
    intervals: list[tuple[datetime, datetime]] = []
    working = False
    paused = False
    segment_start: datetime | None = None
    for record in _active_clockin_records(records):
        point = datetime.fromisoformat(str(record["effective_at"]))
        action = record["action"]
        if action == "entrada" and not working:
            working, paused, segment_start = True, False, point
        elif action == "pausa" and working and not paused:
            if segment_start is not None and point >= segment_start:
                intervals.append((segment_start, point))
            paused, segment_start = True, None
        elif action == "reanudar" and working and paused:
            paused, segment_start = False, point
        elif action == "salida" and working:
            if not paused and segment_start is not None and point >= segment_start:
                intervals.append((segment_start, point))
            working, paused, segment_start = False, False, None
    if working and not paused and segment_start is not None:
        intervals.append((segment_start, now))
    seconds = 0.0
    for start, finish in intervals:
        clipped_start = max(start, day_start)
        clipped_end = min(finish, day_end, now)
        if clipped_end > clipped_start:
            seconds += (clipped_end - clipped_start).total_seconds()
    return seconds


def worker_open_shift(worker_id: int, business_id: int) -> dict | None:
    if not get_worker(worker_id, business_id):
        return None
    with get_conn() as conn:
        records = _clockin_rows_with_corrections(conn, business_id, worker_id)
    state = _shift_state(records)
    if not state["working"]:
        return None
    return {**state["entry"], "paused": state["paused"]}


def clock_worker(
    business_id: int,
    worker_id: int,
    action: str,
    source: str,
    job_id: int | None = None,
    lat=None,
    lng=None,
    accuracy=None,
) -> dict:
    if action not in {"entrada", "salida", "pausa", "reanudar"}:
        raise ValueError("La acción de fichaje no es válida.")
    if source not in {"web", "whatsapp"}:
        raise ValueError("El origen del fichaje no es válido.")
    worker = get_worker(worker_id, business_id)
    if not worker or not worker.get("active"):
        raise ValueError("El trabajador no está disponible.")
    if job_id is not None:
        job = get_job(job_id, business_id)
        if not job or job.get("worker_id") != worker_id:
            raise ValueError("Ese trabajo no está asignado al trabajador.")
    lat = _gps_value(lat, "La latitud", -90, 90)
    lng = _gps_value(lng, "La longitud", -180, 180)
    accuracy = _gps_value(accuracy, "La precisión", 0, 100_000)
    now = _now()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        conn.execute(
            "SELECT id FROM workers WHERE id=? AND business_id=?" + lock,
            (worker_id, business_id),
        ).fetchone()
        records = _clockin_rows_with_corrections(conn, business_id, worker_id)
        state = _shift_state(records)
        if action == "entrada" and state["working"]:
            raise ValueError("Ya hay una jornada abierta.")
        if action == "pausa" and (
            not state["working"] or state["paused"]
        ):
            raise ValueError("No se puede iniciar esa pausa.")
        if action == "reanudar" and (
            not state["working"] or not state["paused"]
        ):
            raise ValueError("No hay una pausa que reanudar.")
        if action == "salida" and not state["working"]:
            raise ValueError("No hay una jornada abierta para registrar la salida.")
        last = conn.execute(
            "SELECT seal FROM worker_clockins "
            "WHERE business_id=? AND worker_id=? ORDER BY id DESC LIMIT 1",
            (business_id, worker_id),
        ).fetchone()
        prev_seal = last["seal"] if last else None
        seal = clockin_seal({
            "business_id": business_id,
            "worker_id": worker_id,
            "action": action,
            "at": now,
            "source": source,
            "lat": lat,
            "lng": lng,
            "job_id": job_id,
        }, prev_seal)
        row = conn.execute(
            "INSERT INTO worker_clockins "
            "(business_id, worker_id, job_id, action, at, source, lat, lng, "
            "accuracy, created_at, seal, prev_seal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "RETURNING id",
            (
                business_id, worker_id, job_id, action, now, source, lat, lng,
                accuracy, now, seal, prev_seal,
            ),
        ).fetchone()
        clockin_id = row["id"]
    with get_conn() as conn:
        result = conn.execute(
            "SELECT * FROM worker_clockins "
            "WHERE id=? AND business_id=? AND worker_id=?",
            (clockin_id, business_id, worker_id),
        ).fetchone()
        return dict(result)


def verify_clockin_chain(business_id: int, worker_id: int) -> dict:
    if not get_worker(worker_id, business_id):
        return {
            "valid": False, "checked": 0, "broken_at": None,
            "error": "Trabajador no encontrado.",
        }
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM worker_clockins "
            "WHERE business_id=? AND worker_id=? ORDER BY id",
            (business_id, worker_id),
        ).fetchall()
    previous = None
    for index, raw in enumerate(rows):
        row = dict(raw)
        expected = clockin_seal(row, previous)
        if row.get("prev_seal") != previous or row.get("seal") != expected:
            return {
                "valid": False,
                "checked": index,
                "broken_at": row["id"],
                "expected_seal": expected,
                "stored_seal": row.get("seal"),
            }
        previous = row["seal"]
    return {
        "valid": True,
        "checked": len(rows),
        "broken_at": None,
        "last_seal": previous,
    }


def correct_worker_clockin(
    business_id: int,
    worker_id: int,
    clockin_id: int,
    author_user_id: int,
    *,
    new_at: str | None,
    reason: str,
) -> dict | None:
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ValueError("El motivo de la corrección es obligatorio.")
    if len(reason) > 1000:
        raise ValueError("El motivo de la corrección es demasiado largo.")
    corrected_at = (
        _parse_clockin_at(new_at, "La nueva fecha") if new_at else None
    )
    author = get_user(author_user_id)
    if not author or author["business_id"] != business_id:
        raise ValueError("El autor no pertenece a este negocio.")
    if not get_worker(worker_id, business_id):
        return None
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        conn.execute(
            "SELECT id FROM workers WHERE id=? AND business_id=?" + lock,
            (worker_id, business_id),
        ).fetchone()
        clockin = conn.execute(
            "SELECT * FROM worker_clockins "
            "WHERE id=? AND business_id=? AND worker_id=?",
            (clockin_id, business_id, worker_id),
        ).fetchone()
        if not clockin:
            return None
        latest = conn.execute(
            "SELECT * FROM worker_clockin_corrections "
            "WHERE business_id=? AND clockin_id=? ORDER BY id DESC LIMIT 1",
            (business_id, clockin_id),
        ).fetchone()
        old_at = (
            latest.get("new_at")
            if latest and latest.get("status") == "corregido"
            else (None if latest and latest.get("status") == "anulado"
                  else clockin["at"])
        )
        status = "corregido" if corrected_at else "anulado"
        created_at = _now()
        row = conn.execute(
            "INSERT INTO worker_clockin_corrections "
            "(business_id, clockin_id, author_user_id, reason, status, old_at, "
            "new_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                business_id, clockin_id, author_user_id, reason, status,
                old_at, corrected_at, created_at,
            ),
        ).fetchone()
        correction_id = row["id"]
    with get_conn() as conn:
        correction = conn.execute(
            "SELECT * FROM worker_clockin_corrections "
            "WHERE id=? AND business_id=?",
            (correction_id, business_id),
        ).fetchone()
    return dict(correction)


def clockin_corrections(
    business_id: int, worker_id: int, clockin_id: int
) -> list[dict]:
    if not get_worker(worker_id, business_id):
        return []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT cor.*, u.email AS author_email "
            "FROM worker_clockin_corrections cor "
            "JOIN worker_clockins wc ON wc.id=cor.clockin_id "
            "AND wc.business_id=cor.business_id "
            "LEFT JOIN users u ON u.id=cor.author_user_id "
            "WHERE cor.business_id=? AND wc.worker_id=? AND cor.clockin_id=? "
            "ORDER BY cor.id",
            (business_id, worker_id, clockin_id),
        ).fetchall()
        return [dict(row) for row in rows]


def clockins_today(business_id: int) -> list[dict]:
    today = date.today().isoformat()
    now = datetime.now()
    workers = list_workers(business_id)
    summaries: list[dict] = []
    for worker in workers:
        with get_conn() as conn:
            records = _clockin_rows_with_corrections(
                conn, business_id, worker["id"]
            )
        state = _shift_state(records)
        today_records = [
            record for record in _active_clockin_records(records)
            if str(record["effective_at"]).startswith(today)
        ]
        last = today_records[-1] if today_records else (
            state["entry"] if state["working"] else None
        )
        location_record = next(
            (
                record for record in reversed(today_records)
                if record.get("lat") is not None and record.get("lng") is not None
            ),
            state["entry"] if state["working"] else None,
        )
        last_location = (
            {
                "lat": location_record["lat"], "lng": location_record["lng"],
                "accuracy": location_record.get("accuracy"),
                "at": location_record.get("effective_at") or location_record["at"],
            }
            if location_record
            and location_record.get("lat") is not None
            and location_record.get("lng") is not None
            else None
        )
        seconds = _worked_seconds_for_day(records, today, now)
        summaries.append({
            **worker,
            "hours_today": round(seconds / 3600, 2),
            "hours": round(seconds / 3600, 2),
            "last_action": last["action"] if last else None,
            "last_clock_at": (
                last.get("effective_at") or last["at"] if last else None
            ),
            "last_location": last_location,
            "open_shift": state["working"],
            "paused": state["paused"],
        })
    return summaries


def team_productivity(business_id: int, days: int = 30) -> dict:
    """Rendimiento por persona para el dueño del negocio: trabajos asignados y
    completados, ventas estimadas (precio de los trabajos hechos) y horas
    fichadas dentro del período. Solo agregados del propio negocio."""
    days = max(1, min(int(days or 30), 365))
    today = date.today()
    since = (today - timedelta(days=days - 1)).isoformat()
    now = datetime.now()
    done_ph = ",".join("?" for _ in _JOB_DONE_STATES)
    dead_ph = ",".join("?" for _ in _JOB_DEAD_STATES)
    items = []
    for worker in list_workers(business_id):
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS asignados, "
                f"SUM(CASE WHEN status IN ({done_ph}) THEN 1 ELSE 0 END) AS hechos, "
                f"COALESCE(SUM(CASE WHEN status IN ({done_ph}) "
                "THEN COALESCE(price_estimate, 0) ELSE 0 END), 0) AS ventas "
                "FROM jobs WHERE business_id=? AND worker_id=? "
                f"AND status NOT IN ({dead_ph}) "
                "AND substr(CAST(COALESCE(scheduled_for, created_at) AS TEXT), 1, 10) >= ?",
                (*_JOB_DONE_STATES, *_JOB_DONE_STATES,
                 business_id, worker["id"], *_JOB_DEAD_STATES, since),
            ).fetchone()
            records = _clockin_rows_with_corrections(
                conn, business_id, worker["id"]
            )
        seconds = sum(
            _worked_seconds_for_day(
                records, (today - timedelta(days=offset)).isoformat(), now
            )
            for offset in range(days)
        )
        hours = round(seconds / 3600, 1)
        ventas = round(float(row["ventas"] or 0), 2)
        items.append({
            "id": worker["id"],
            "name": worker["name"],
            "color": worker.get("color"),
            "active": worker["active"],
            "jobs_asignados": int(row["asignados"] or 0),
            "jobs_hechos": int(row["hechos"] or 0),
            "ventas": ventas,
            "horas": hours,
            "eur_hora": round(ventas / hours, 2) if hours else None,
        })
    items.sort(key=lambda i: (-i["ventas"], -i["jobs_hechos"], i["name"]))
    return {"days": days, "since": since, "items": items}


def clockin_report_data(
    business_id: int, worker_id: int, from_day: str, to_day: str
) -> dict | None:
    worker = get_worker(worker_id, business_id)
    business = get_business(business_id)
    if not worker or not business:
        return None
    start = datetime.fromisoformat(from_day)
    end = datetime.fromisoformat(to_day)
    if end < start:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")
    if (end - start).days > 1461:
        raise ValueError("El informe no puede superar cuatro años.")
    with get_conn() as conn:
        records = _clockin_rows_with_corrections(conn, business_id, worker_id)
    days = []
    point = start
    while point <= end:
        day = point.date().isoformat()
        day_events = []
        for record in records:
            display_at = record.get("effective_at") or record["at"]
            event_day = str(display_at)[:10]
            if event_day == day:
                day_events.append(record)
        if day_events or _worked_seconds_for_day(records, day) > 0:
            days.append({
                "day": day,
                "hours": round(
                    _worked_seconds_for_day(records, day) / 3600, 2
                ),
                "events": sorted(
                    day_events,
                    key=lambda item: (
                        str(item.get("effective_at") or item["at"]), item["id"]
                    ),
                ),
            })
        point += timedelta(days=1)
    return {
        "business": business,
        "worker": worker,
        "from": from_day,
        "to": to_day,
        "days": days,
        "integrity": verify_clockin_chain(business_id, worker_id),
        "generated_at": _now(),
    }


def update_clockin_policy(business_id: int, policy: str | None) -> dict | None:
    text = (policy or "").strip()
    if len(text) > 5000:
        raise ValueError("La política de registro no puede superar 5.000 caracteres.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET clockin_policy=? WHERE id=?",
            (text or None, business_id),
        )
    return get_business(business_id)


# ------------------------------------------------ Enlace de cada trabajador ---
def get_or_create_worker_token(
    business_id: int,
    worker_id: int,
    ttl_days: int = _WORKER_TOKEN_TTL_DAYS,
) -> str | None:
    worker = get_worker(worker_id, business_id)
    if not worker or not worker.get("active"):
        return None
    now = _now()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT token FROM worker_tokens "
            "WHERE business_id=? AND worker_id=? AND revoked=FALSE "
            "AND expires_at>=? ORDER BY created_at DESC LIMIT 1",
            (business_id, worker_id, now),
        ).fetchone()
        if row:
            return row["token"]
        token = secrets.token_urlsafe(24)
        expires = (
            datetime.now() + timedelta(days=ttl_days)
        ).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO worker_tokens "
            "(token, business_id, worker_id, expires_at, revoked, created_at) "
            "VALUES (?, ?, ?, ?, FALSE, ?)",
            (token, business_id, worker_id, expires, now),
        )
        return token


def resolve_worker_token(token: str) -> dict | None:
    if not token:
        return None
    with get_conn() as conn:
        ref = conn.execute(
            "SELECT business_id, worker_id FROM worker_tokens "
            "WHERE token=? AND revoked=FALSE AND expires_at>=?",
            (token, _now()),
        ).fetchone()
    if not ref:
        return None
    worker = get_worker(ref["worker_id"], ref["business_id"])
    business = get_business(ref["business_id"])
    if not worker or not worker.get("active") or not business:
        return None
    return {"worker": worker, "business": business}


def revoke_worker_tokens(worker_id: int, business_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE worker_tokens SET revoked=TRUE "
            "WHERE worker_id=? AND business_id=?",
            (worker_id, business_id),
        )


# Estados que indican que un trabajo ya se realizó.
_JOB_DONE_STATES = ("hecho", "hecha", "completado", "completada", "realizado",
                    "realizada", "terminado", "terminada", "finalizado", "finalizada")
_JOB_DEAD_STATES = ("cancelado", "cancelada", "anulado", "anulada")


def unbilled_jobs(business_id) -> list[dict]:
    """Trabajos que probablemente están SIN FACTURAR: o ya pasó su fecha o están
    marcados como hechos, y el cliente no tiene ninguna factura creada desde
    entonces. Es una SEÑAL de apoyo para el copiloto (puede tener falsos positivos
    si se factura en bloque), no un dato fiscal. Aislado por business_id."""
    today = date.today().isoformat()
    done_ph = ",".join("?" for _ in _JOB_DONE_STATES)
    dead_ph = ",".join("?" for _ in _JOB_DEAD_STATES)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT j.*, c.name AS client_name FROM jobs j "
            "LEFT JOIN clients c ON c.id=j.client_id AND c.business_id=j.business_id "
            "WHERE j.business_id=? AND j.client_id IS NOT NULL "
            f"AND j.status NOT IN ({dead_ph}) "
            f"AND (j.status IN ({done_ph}) "
            "OR substr(CAST(j.scheduled_for AS TEXT),1,10) < ?) "
            "ORDER BY j.scheduled_for",
            (business_id, *_JOB_DEAD_STATES, *_JOB_DONE_STATES, today),
        ).fetchall()
        jobs = [dict(r) for r in rows]
        out = []
        for j in jobs:
            day = (j.get("scheduled_for") or j.get("created_at") or "")[:10]
            billed = conn.execute(
                "SELECT 1 FROM invoices WHERE business_id=? AND client_id=? "
                "AND substr(CAST(created_at AS TEXT),1,10) >= ? LIMIT 1",
                (business_id, j["client_id"], day),
            ).fetchone()
            if not billed:
                out.append(j)
        return out


# --------------------------------------------------------------- Facturas ---
_VERIFACTU_INVOICE_TYPES = {"F1", "F2", "R1", "R2", "R3", "R4", "R5"}


def _verifactu_nif(value: str | None, label: str) -> str:
    nif = (value or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{9}", nif):
        raise ValueError(f"{label} debe tener 9 caracteres alfanuméricos.")
    return nif


def verifactu_configuration_errors() -> list[str]:
    errors = []
    if not config.VERIFACTU_PRODUCER_NAME:
        errors.append("nombre del productor")
    try:
        _verifactu_nif(config.VERIFACTU_PRODUCER_NIF, "El NIF del productor")
    except ValueError:
        errors.append("NOESIS_VERIFACTU_PRODUCER_NIF")
    if not 1 <= len(config.VERIFACTU_SYSTEM_NAME) <= 30:
        errors.append("nombre del sistema (máximo 30 caracteres)")
    if not 1 <= len(config.VERIFACTU_SYSTEM_ID) <= 2:
        errors.append("identificador del sistema (máximo 2 caracteres)")
    if not config.VERIFACTU_SYSTEM_VERSION:
        errors.append("versión del sistema")
    if config.VERIFACTU_HASH_ALGORITHM != "sha256":
        errors.append("algoritmo SHA-256")
    if config.VERIFACTU_HASH_TYPE != "01":
        errors.append("tipo de huella 01")
    if not config.VERIFACTU_QR_BASE_URL.startswith("https://"):
        errors.append("URL HTTPS del QR")
    return errors


def update_verifactu_mode(business_id: int, enabled: bool) -> dict | None:
    business = get_business(business_id)
    if not business:
        return None
    if enabled:
        errors = verifactu_configuration_errors()
        if errors:
            raise ValueError(
                "Antes de activar configura: " + ", ".join(errors) + "."
            )
        _verifactu_nif(business.get("nif"), "El NIF del negocio")
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET verifactu_enabled=? WHERE id=?",
            (bool(enabled), business_id),
        )
    return get_business(business_id)


def add_invoice(client_id, concept, base, vat_rate=config.DEFAULT_VAT_RATE,
                irpf_rate=0, *, business_id: int) -> dict:
    """Crea una factura calculando IVA y retención de IRPF.

    Total = base + IVA − IRPF retenido (así sale el importe que el cliente paga).
    """
    if not get_client(client_id, business_id):
        raise ValueError("El cliente no pertenece a este negocio.")
    concept = (concept or "").strip()
    if not concept or len(concept) > 500:
        raise ValueError("El concepto es obligatorio y no puede superar 500 caracteres.")
    base = _positive_money(base, "La base")
    vat_rate = _tax_rate(vat_rate, "El IVA", {0, 4, 10, 21})
    irpf_rate = _tax_rate(irpf_rate, "El IRPF", {0, 7, 15})
    vat_amount = _tax_amount(base, vat_rate)
    irpf_amount = _tax_amount(base, irpf_rate)
    total = float(
        (
            Decimal(str(base))
            + Decimal(str(vat_amount))
            - Decimal(str(irpf_amount))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO invoices (business_id, client_id, concept, base, vat_rate, "
            "vat_amount, irpf_rate, irpf_amount, total, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?) RETURNING id",
            (business_id, client_id, concept, base, vat_rate, vat_amount,
             irpf_rate or 0, irpf_amount, total, _now()),
        ).fetchone()
        new_id = row["id"]
    return get_invoice(new_id, business_id)


def create_rectifying_invoice(
    original_invoice_id: int,
    business_id: int,
    *,
    concept: str,
    base,
    vat_rate=config.DEFAULT_VAT_RATE,
    irpf_rate=0,
    invoice_type: str = "R1",
    reason: str,
) -> dict:
    """Crea una rectificativa incremental; el original nunca se modifica."""
    original = get_invoice(original_invoice_id, business_id)
    if not original or original.get("status") not in {
        "enviada", "parcial", "cobrada"
    }:
        raise ValueError("Solo se puede rectificar una factura ya emitida.")
    invoice_type = (invoice_type or "").strip().upper()
    if invoice_type not in {"R1", "R2", "R3", "R4", "R5"}:
        raise ValueError("El tipo de factura rectificativa no es válido.")
    concept = (concept or "").strip()
    reason = (reason or "").strip()
    if not concept or len(concept) > 500:
        raise ValueError("El concepto es obligatorio y no puede superar 500 caracteres.")
    if len(reason) < 3 or len(reason) > 1000:
        raise ValueError("El motivo de rectificación es obligatorio.")
    try:
        signed_base = float(base)
    except (TypeError, ValueError) as exc:
        raise ValueError("La base rectificada debe ser un número distinto de cero.") from exc
    if (
        not math.isfinite(signed_base)
        or signed_base == 0
        or abs(signed_base) > 10_000_000
    ):
        raise ValueError("La base rectificada debe ser un número distinto de cero.")
    vat_rate = _tax_rate(vat_rate, "El IVA", {0, 4, 10, 21})
    irpf_rate = _tax_rate(irpf_rate, "El IRPF", {0, 7, 15})
    signed_base = float(
        Decimal(str(signed_base)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )
    vat_amount = _tax_amount(signed_base, vat_rate)
    irpf_amount = _tax_amount(signed_base, irpf_rate)
    total = float(
        (
            Decimal(str(signed_base))
            + Decimal(str(vat_amount))
            - Decimal(str(irpf_amount))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO invoices (business_id, client_id, concept, base, vat_rate, "
            "vat_amount, irpf_rate, irpf_amount, total, status, invoice_type, "
            "rectifies_invoice_id, rectification_type, rectification_reason, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?, ?, "
            "'I', ?, ?) RETURNING id",
            (
                business_id, original["client_id"], concept, signed_base, vat_rate,
                vat_amount, irpf_rate or 0, irpf_amount, total, invoice_type,
                original_invoice_id, reason, _now(),
            ),
        ).fetchone()
        new_id = row["id"]
    return get_invoice(new_id, business_id)


def _invoice_payment_state(invoice: dict) -> dict:
    """Añade importes y estado de cobro derivados del ledger."""
    data = dict(invoice)
    total = round(float(data.get("total") or 0), 2)
    paid = round(float(data.get("paid_amount") or 0), 2)
    remaining = round(max(total - paid, 0), 2)
    if total <= 0 or remaining <= 0:
        payment_status = "pagada"
    elif paid > 0:
        payment_status = "parcial"
    else:
        payment_status = "pendiente"
    data["paid_amount"] = paid
    data["remaining_amount"] = remaining
    data["payment_status"] = payment_status
    return data


def get_invoice(invoice_id, business_id) -> dict | None:
    where = "i.id=? AND i.business_id=?"
    params = [invoice_id, business_id]
    with get_conn() as conn:
        row = conn.execute(
            "SELECT i.*, c.name AS client_name, "
            "COALESCE((SELECT SUM(p.amount) FROM invoice_payments p "
            "WHERE p.business_id=i.business_id AND p.invoice_id=i.id), 0) "
            "AS paid_amount FROM invoices i "
            "LEFT JOIN clients c ON c.id = i.client_id "
            "AND c.business_id=i.business_id WHERE " + where,
            params,
        ).fetchone()
        return _invoice_payment_state(row) if row else None


def list_invoices(business_id, status=None) -> list[dict]:
    q = (
        "SELECT i.*, COALESCE(i.recipient_name, c.name) AS client_name, "
        "COALESCE((SELECT SUM(p.amount) FROM invoice_payments p "
        "WHERE p.business_id=i.business_id AND p.invoice_id=i.id), 0) "
        "AS paid_amount, "
        "CASE WHEN EXISTS (SELECT 1 FROM invoice_records vr "
        "WHERE vr.business_id=i.business_id AND vr.invoice_id=i.id) "
        "THEN TRUE ELSE FALSE END AS verifactu_registered, "
        "vo.status AS verifactu_status, vo.aeat_csv AS verifactu_csv, "
        "vo.aeat_error_description AS verifactu_error "
        "FROM invoices i "
        "LEFT JOIN clients c ON c.id = i.client_id AND c.business_id=i.business_id "
        "LEFT JOIN verifactu_outbox vo ON vo.invoice_id=i.id "
        "AND vo.business_id=i.business_id "
        "WHERE i.business_id=?"
    )
    params: list = [business_id]
    if status:
        q += " AND i.status=?"
        params.append(status)
    q += " ORDER BY i.created_at DESC"
    with get_conn() as conn:
        return [
            _invoice_payment_state(r)
            for r in conn.execute(q, params).fetchall()
        ]


def _next_document_number(conn, business_id: int, kind: str) -> int:
    year = date.today().year
    table = "invoices" if kind == "invoice" else "quotes"
    prefix = f"{year}/" if kind == "invoice" else f"P{year}/"
    existing = conn.execute(
        f"SELECT number FROM {table} WHERE business_id=? AND number LIKE ?",
        (business_id, f"{prefix}%"),
    ).fetchall()
    used = []
    for item in existing:
        try:
            used.append(int(item["number"].rsplit("/", 1)[1]))
        except (AttributeError, IndexError, ValueError):
            continue
    initial = max(used, default=0) + 1
    row = conn.execute(
        "INSERT INTO document_sequences (business_id, kind, year, last_number) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT (business_id, kind, year) DO UPDATE "
        "SET last_number=document_sequences.last_number+1 "
        "RETURNING last_number",
        (business_id, kind, year, initial),
    ).fetchone()
    return row["last_number"]


def _record_invoice_event(
    conn,
    business_id: int,
    event_type: str,
    *,
    invoice_id: int | None = None,
    record_id: int | None = None,
    details: str | None = None,
    created_at: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO invoice_events "
        "(business_id, invoice_id, record_id, event_type, details, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            business_id, invoice_id, record_id, event_type, details,
            created_at or verifactu.generated_at_with_timezone(),
        ),
    )


def _create_invoice_record(conn, business_id: int, invoice_id: int) -> dict:
    invoice = conn.execute(
        "SELECT * FROM invoices WHERE id=? AND business_id=?",
        (invoice_id, business_id),
    ).fetchone()
    business = conn.execute(
        "SELECT * FROM businesses WHERE id=?", (business_id,)
    ).fetchone()
    if not invoice or not business:
        raise ValueError("No se puede generar el registro de facturación.")
    existing = conn.execute(
        "SELECT * FROM invoice_records WHERE business_id=? AND invoice_id=?",
        (business_id, invoice_id),
    ).fetchone()
    if existing:
        return dict(existing)

    issuer_nif = _verifactu_nif(invoice["issuer_nif"], "El NIF del emisor")
    recipient_nif = _verifactu_nif(
        invoice["recipient_nif"], "El NIF del destinatario"
    )
    invoice_type = (invoice.get("invoice_type") or "F1").strip().upper()
    if invoice_type not in _VERIFACTU_INVOICE_TYPES:
        raise ValueError("El tipo de factura no es válido para Veri*Factu.")
    issue_date = verifactu.aeat_date(invoice["issued_at"])
    generated_at = verifactu.generated_at_with_timezone()
    previous = conn.execute(
        "SELECT * FROM invoice_records "
        "WHERE business_id=? AND issuer_nif=? ORDER BY id DESC LIMIT 1",
        (business_id, issuer_nif),
    ).fetchone()
    previous_hash = previous["record_hash"] if previous else None

    rectified = None
    if invoice_type.startswith("R"):
        rectified = conn.execute(
            "SELECT * FROM invoices WHERE id=? AND business_id=?",
            (invoice.get("rectifies_invoice_id"), business_id),
        ).fetchone()
        if not rectified or not rectified.get("number") or not rectified.get("issued_at"):
            raise ValueError("La factura original de la rectificativa no es válida.")

    record_hash = verifactu.invoice_record_hash(
        issuer_nif=issuer_nif,
        invoice_number=invoice["number"],
        issue_date=issue_date,
        invoice_type=invoice_type,
        vat_total=invoice["vat_amount"],
        invoice_total=invoice["total"],
        previous_hash=previous_hash,
        generated_at=generated_at,
    )
    breakdown = json.dumps(
        [{
            "vat_rate": invoice["vat_rate"],
            "base": invoice["base"],
            "vat_amount": invoice["vat_amount"],
        }],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    invoice_qr_url = verifactu.qr_url(
        issuer_nif=issuer_nif,
        invoice_number=invoice["number"],
        issue_date=issue_date,
        total=invoice["total"],
    )
    row = conn.execute(
        "INSERT INTO invoice_records ("
        "business_id, invoice_id, record_type, record_version, invoice_type, "
        "rectification_type, rectified_issuer_nif, rectified_invoice_number, "
        "rectified_issue_date, issuer_nif, issuer_name, invoice_number, issue_date, "
        "recipient_nif, recipient_name, description, breakdown_json, vat_total, "
        "invoice_total, generated_at, previous_record_id, previous_issuer_nif, "
        "previous_invoice_number, previous_issue_date, previous_hash, "
        "hash_algorithm, hash_type, hash_spec_version, record_hash, qr_url, "
        "producer_name, producer_nif, system_name, system_id, system_version, "
        "installation_id, created_at) VALUES ("
        "?, ?, 'alta', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (
            business_id, invoice_id, config.VERIFACTU_RECORD_VERSION, invoice_type,
            invoice.get("rectification_type"),
            issuer_nif if rectified else None,
            rectified["number"] if rectified else None,
            verifactu.aeat_date(rectified["issued_at"]) if rectified else None,
            issuer_nif, invoice["issuer_name"], invoice["number"], issue_date,
            recipient_nif, invoice["recipient_name"], invoice["concept"], breakdown,
            invoice["vat_amount"], invoice["total"], generated_at,
            previous["id"] if previous else None,
            previous["issuer_nif"] if previous else None,
            previous["invoice_number"] if previous else None,
            previous["issue_date"] if previous else None,
            previous_hash, config.VERIFACTU_HASH_ALGORITHM,
            config.VERIFACTU_HASH_TYPE, config.VERIFACTU_HASH_SPEC_VERSION,
            record_hash, invoice_qr_url, config.VERIFACTU_PRODUCER_NAME,
            config.VERIFACTU_PRODUCER_NIF, config.VERIFACTU_SYSTEM_NAME,
            config.VERIFACTU_SYSTEM_ID, config.VERIFACTU_SYSTEM_VERSION,
            f"{config.VERIFACTU_INSTALLATION_PREFIX}-{business_id}",
            generated_at,
        ),
    ).fetchone()
    record_id = row["id"]
    event_type = "rectificacion" if invoice_type.startswith("R") else "alta"
    _record_invoice_event(
        conn, business_id, event_type, invoice_id=invoice_id,
        record_id=record_id, details=f"huella={record_hash}",
        created_at=generated_at,
    )
    queued_at = _now()
    conn.execute(
        "INSERT INTO verifactu_outbox "
        "(business_id, invoice_id, record_id, status, attempts, max_attempts, "
        "next_attempt_at, created_at, updated_at) "
        "VALUES (?, ?, ?, 'pendiente', 0, ?, ?, ?, ?) "
        "ON CONFLICT (business_id, record_id) DO NOTHING",
        (
            business_id, invoice_id, record_id, config.VERIFACTU_MAX_ATTEMPTS,
            queued_at, queued_at, queued_at,
        ),
    )
    return dict(conn.execute(
        "SELECT * FROM invoice_records WHERE id=? AND business_id=?",
        (record_id, business_id),
    ).fetchone())


def issue_invoice(invoice_id: int, business_id: int, payment_term_days: int = 15) -> dict:
    """Emite una factura una sola vez, numera y congela sus datos fiscales."""
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        inv = conn.execute(
            "SELECT * FROM invoices WHERE id=? AND business_id=?" + lock,
            (invoice_id, business_id),
        ).fetchone()
        if not inv:
            raise ValueError("No existe esa factura.")
        if inv["status"] != "borrador" or inv["number"]:
            existing = get_invoice(invoice_id, business_id)
            if existing and existing["status"] in {
                "enviada", "parcial", "cobrada"
            }:
                return existing
            raise ValueError("La factura no se puede emitir desde su estado actual.")

        biz = conn.execute(
            "SELECT * FROM businesses WHERE id=?", (business_id,)
        ).fetchone()
        client = conn.execute(
            "SELECT * FROM clients WHERE id=? AND business_id=?",
            (inv["client_id"], business_id),
        ).fetchone()
        if not biz or not client:
            raise ValueError("Faltan el negocio o el cliente de la factura.")
        missing = []
        for value, label in (
            (biz["name"], "nombre fiscal del negocio"),
            (biz["nif"], "NIF del negocio"),
            (biz["address"], "domicilio del negocio"),
            (client["name"], "nombre del cliente"),
            (client["nif"], "NIF del cliente"),
            (client["address"], "domicilio del cliente"),
        ):
            if not (value or "").strip():
                missing.append(label)
        if missing:
            raise ValueError(
                "Antes de emitir completa: " + ", ".join(missing) + "."
            )

        seq = _next_document_number(conn, business_id, "invoice")
        year = date.today().year
        number = f"{year}/{seq:04d}"
        issued_at = _now()
        due_date = (
            date.today() + timedelta(days=max(0, min(payment_term_days, 365)))
        ).isoformat()
        conn.execute(
            "UPDATE invoices SET status='enviada', number=?, issued_at=?, due_date=?, "
            "issuer_name=?, issuer_nif=?, issuer_address=?, recipient_name=?, "
            "recipient_nif=?, recipient_address=? "
            "WHERE id=? AND business_id=? AND status='borrador'",
            (
                number, issued_at, due_date, biz["name"], biz["nif"], biz["address"],
                client["name"], client["nif"], client["address"], invoice_id,
                business_id,
            ),
        )
        if biz.get("verifactu_enabled"):
            errors = verifactu_configuration_errors()
            if errors:
                raise ValueError(
                    "No se puede emitir en modo Veri*Factu; configura: "
                    + ", ".join(errors) + "."
                )
            _create_invoice_record(conn, business_id, invoice_id)
    return get_invoice(invoice_id, business_id)


def mark_invoice_sent(invoice_id, number, due_date=None, *, business_id: int) -> dict | None:
    """Marca una factura como enviada. Filtra por business_id (aislamiento): si la
    factura no es de ese negocio, no toca nada y devuelve None."""
    business = get_business(business_id)
    if business and business.get("verifactu_enabled"):
        raise ValueError(
            "El modo Veri*Factu nativo debe emitir con la numeración interna."
        )
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE invoices SET status='enviada', number=?, issued_at=?, due_date=? "
            "WHERE id=? AND business_id=? AND status='borrador' AND number IS NULL",
            (number, _now(), due_date, invoice_id, business_id),
        )
        ok = cur.rowcount > 0
    return get_invoice(invoice_id, business_id) if ok else None


def _payment_text(value, label: str, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) > max_length:
        raise ValueError(f"{label} no puede superar {max_length} caracteres.")
    return text or None


def _payment_paid_at(value=None) -> str:
    if value in (None, ""):
        return _now()
    text = str(value).strip()
    try:
        datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("La fecha de cobro no es válida.") from exc
    return text


def _locked_invoice_with_paid(conn, invoice_id: int, business_id: int):
    lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
    invoice = conn.execute(
        "SELECT * FROM invoices WHERE id=? AND business_id=?" + lock,
        (invoice_id, business_id),
    ).fetchone()
    if not invoice:
        return None, Decimal("0.00")
    paid = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS total FROM invoice_payments "
        "WHERE invoice_id=? AND business_id=?",
        (invoice_id, business_id),
    ).fetchone()["total"]
    return invoice, Decimal(str(paid or 0)).quantize(Decimal("0.01"))


def _insert_invoice_payment(
    conn,
    invoice,
    amount: Decimal,
    method: str | None,
    paid_at: str,
    note: str | None,
) -> int:
    row = conn.execute(
        "INSERT INTO invoice_payments "
        "(business_id, invoice_id, amount, method, paid_at, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (
            invoice["business_id"], invoice["id"], float(amount), method,
            paid_at, note, _now(),
        ),
    ).fetchone()
    return row["id"]


def _set_invoice_payment_state(
    conn,
    invoice,
    paid: Decimal,
    paid_at: str,
) -> None:
    total = Decimal(str(invoice["total"])).quantize(Decimal("0.01"))
    if paid >= total:
        conn.execute(
            "UPDATE invoices SET status='cobrada', paid_at=? "
            "WHERE id=? AND business_id=?",
            (paid_at, invoice["id"], invoice["business_id"]),
        )
    else:
        conn.execute(
            "UPDATE invoices SET status='parcial', paid_at=NULL "
            "WHERE id=? AND business_id=?",
            (invoice["id"], invoice["business_id"]),
        )


def add_invoice_payment(
    invoice_id,
    amount,
    *,
    business_id: int,
    method=None,
    paid_at=None,
    note=None,
) -> dict:
    """Registra un cobro sin alterar el registro fiscal inmutable de la factura."""
    amount_decimal = Decimal(str(_positive_money(amount, "El importe"))).quantize(
        Decimal("0.01")
    )
    method = _payment_text(method, "El método", 50)
    note = _payment_text(note, "La nota", 500)
    paid_at = _payment_paid_at(paid_at)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        invoice, already_paid = _locked_invoice_with_paid(
            conn, invoice_id, business_id
        )
        if not invoice:
            raise ValueError("Factura no encontrada.")
        if invoice["status"] == "borrador" or not invoice.get("number"):
            raise ValueError("Solo se pueden cobrar facturas emitidas.")
        total = Decimal(str(invoice["total"])).quantize(Decimal("0.01"))
        if total <= 0:
            raise ValueError("Esta factura no admite cobros.")
        new_paid = already_paid + amount_decimal
        if new_paid > total:
            remaining = max(total - already_paid, Decimal("0.00"))
            raise ValueError(
                f"El cobro supera el importe pendiente ({float(remaining):.2f} €)."
            )
        payment_id = _insert_invoice_payment(
            conn, invoice, amount_decimal, method, paid_at, note
        )
        _set_invoice_payment_state(conn, invoice, new_paid, paid_at)
        payment = conn.execute(
            "SELECT * FROM invoice_payments "
            "WHERE id=? AND business_id=? AND invoice_id=?",
            (payment_id, business_id, invoice_id),
        ).fetchone()
    return dict(payment)


def list_invoice_payments(invoice_id, business_id) -> list[dict]:
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 AS found FROM invoices WHERE id=? AND business_id=?",
            (invoice_id, business_id),
        ).fetchone()
        if not exists:
            return []
        rows = conn.execute(
            "SELECT * FROM invoice_payments "
            "WHERE invoice_id=? AND business_id=? ORDER BY paid_at, id",
            (invoice_id, business_id),
        ).fetchall()
    return [dict(row) for row in rows]


def invoice_paid_amount(invoice_id, business_id) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(i.id) AS invoices, COALESCE(SUM(p.amount),0) AS total "
            "FROM invoices i LEFT JOIN invoice_payments p "
            "ON p.business_id=i.business_id AND p.invoice_id=i.id "
            "WHERE i.id=? AND i.business_id=?",
            (invoice_id, business_id),
        ).fetchone()
    if not row or not row["invoices"]:
        return None
    return round(float(row["total"]), 2)


def mark_invoice_paid(invoice_id, business_id) -> dict | None:
    """Registra el importe restante; repetir la operación no duplica el cobro."""
    payment_time = _now()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        invoice, already_paid = _locked_invoice_with_paid(
            conn, invoice_id, business_id
        )
        if not invoice or invoice["status"] == "borrador" or not invoice.get("number"):
            return None
        total = Decimal(str(invoice["total"])).quantize(Decimal("0.01"))
        remaining = total - already_paid
        if total <= 0:
            return None
        if remaining > 0:
            _insert_invoice_payment(
                conn, invoice, remaining, None, payment_time,
                "Cobro completo registrado",
            )
            _set_invoice_payment_state(conn, invoice, total, payment_time)
    return get_invoice(invoice_id, business_id)


def delete_invoice(invoice_id, business_id) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM invoices WHERE id=? AND business_id=? AND status='borrador'",
            (invoice_id, business_id),
        )
        return cur.rowcount > 0


def get_invoice_record(invoice_id: int, business_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM invoice_records "
            "WHERE invoice_id=? AND business_id=?",
            (invoice_id, business_id),
        ).fetchone()
        return dict(row) if row else None


def list_invoice_records(
    business_id: int,
    *,
    from_day: str | None = None,
    to_day: str | None = None,
) -> list[dict]:
    if not get_business(business_id):
        return []
    start = date.fromisoformat(from_day) if from_day else None
    end = date.fromisoformat(to_day) if to_day else None
    if start and end and end < start:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM invoice_records WHERE business_id=? ORDER BY id",
            (business_id,),
        ).fetchall()
    result = []
    for raw in rows:
        record = dict(raw)
        issued = datetime.strptime(record["issue_date"], "%d-%m-%Y").date()
        if start and issued < start:
            continue
        if end and issued > end:
            continue
        result.append(record)
    return result


def list_invoice_events(business_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM invoice_events WHERE business_id=? ORDER BY id",
            (business_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_verifactu_outbox(invoice_id: int, business_id: int) -> dict | None:
    """Consulta el envío de una factura sin permitir cruces entre negocios."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM verifactu_outbox "
            "WHERE invoice_id=? AND business_id=?",
            (invoice_id, business_id),
        ).fetchone()
        return dict(row) if row else None


def list_verifactu_outbox(
    business_id: int, *, limit: int = 100
) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM verifactu_outbox WHERE business_id=? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (business_id, max(1, min(int(limit), 500))),
        ).fetchall()
        return [dict(row) for row in rows]


def enqueue_missing_verifactu_records(now: str | None = None) -> int:
    """Crea la cola pendiente para registros anteriores al despliegue de fase 2."""
    created_at = now or _now()
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO verifactu_outbox "
            "(business_id, invoice_id, record_id, status, attempts, max_attempts, "
            "next_attempt_at, created_at, updated_at) "
            "SELECT r.business_id, r.invoice_id, r.id, 'pendiente', 0, ?, ?, ?, ? "
            "FROM invoice_records r "
            "JOIN businesses b ON b.id=r.business_id "
            "WHERE b.verifactu_enabled=TRUE AND NOT EXISTS ("
            "SELECT 1 FROM verifactu_outbox o "
            "WHERE o.business_id=r.business_id AND o.record_id=r.id)",
            (
                config.VERIFACTU_MAX_ATTEMPTS,
                created_at,
                created_at,
                created_at,
            ),
        )
        return max(0, cursor.rowcount)


def claim_next_verifactu_submission(
    *, now: str, stale_before: str
) -> dict | None:
    """Reserva un registro vencido; Postgres evita dobles envíos con SKIP LOCKED."""
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        suffix = " FOR UPDATE SKIP LOCKED" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT * FROM verifactu_outbox WHERE attempts<max_attempts AND "
            "((status='pendiente' AND next_attempt_at<=?) OR "
            "(status='enviado' AND locked_at<=?)) "
            "ORDER BY next_attempt_at, id LIMIT 1" + suffix,
            (now, stale_before),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE verifactu_outbox SET status='enviado', attempts=attempts+1, "
            "locked_at=?, sent_at=COALESCE(sent_at, ?), last_error=NULL, "
            "updated_at=? WHERE id=?",
            (now, now, now, row["id"]),
        )
        _record_invoice_event(
            conn,
            row["business_id"],
            "remision",
            invoice_id=row["invoice_id"],
            record_id=row["record_id"],
            details=f"intento={int(row['attempts']) + 1}",
            created_at=now,
        )
        claimed = conn.execute(
            "SELECT * FROM verifactu_outbox WHERE id=?", (row["id"],)
        ).fetchone()
        return dict(claimed)


def mark_verifactu_retry(
    outbox_id: int,
    *,
    error: str,
    next_attempt_at: str,
    updated_at: str,
) -> dict | None:
    """Reprograma solo errores temporales; un rechazo AEAT nunca pasa por aquí."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE verifactu_outbox SET status='pendiente', next_attempt_at=?, "
            "last_error=?, locked_at=NULL, updated_at=? "
            "WHERE id=? AND status='enviado'",
            (next_attempt_at, error[:1500], updated_at, outbox_id),
        )
        row = conn.execute(
            "SELECT * FROM verifactu_outbox WHERE id=?", (outbox_id,)
        ).fetchone()
        return dict(row) if row else None


def mark_verifactu_result(
    outbox_id: int,
    *,
    status: str,
    csv: str | None,
    global_status: str | None,
    error_code: str | None,
    error_description: str | None,
    response: str,
    wait_seconds: int,
    completed_at: str,
) -> dict | None:
    if status not in {"aceptado", "aceptado_con_errores", "rechazado"}:
        raise ValueError("Estado de respuesta Veri*Factu no válido.")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM verifactu_outbox WHERE id=?", (outbox_id,)
        ).fetchone()
        if not row or row["status"] != "enviado":
            return dict(row) if row else None
        conn.execute(
            "UPDATE verifactu_outbox SET status=?, aeat_csv=?, "
            "aeat_global_status=?, aeat_error_code=?, "
            "aeat_error_description=?, aeat_response=?, wait_seconds=?, "
            "completed_at=?, locked_at=NULL, last_error=NULL, updated_at=? "
            "WHERE id=?",
            (
                status, csv, global_status, error_code, error_description,
                response, max(0, int(wait_seconds)), completed_at, completed_at,
                outbox_id,
            ),
        )
        details = json.dumps(
            {
                "estado": status,
                "csv": csv,
                "codigo_error": error_code,
                "descripcion_error": error_description,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        _record_invoice_event(
            conn,
            row["business_id"],
            "rechazo" if status == "rechazado" else "aceptacion",
            invoice_id=row["invoice_id"],
            record_id=row["record_id"],
            details=details,
            created_at=completed_at,
        )
        updated = conn.execute(
            "SELECT * FROM verifactu_outbox WHERE id=?", (outbox_id,)
        ).fetchone()
        return dict(updated)


def postpone_verifactu_submissions(until: str, updated_at: str) -> int:
    """Aplica globalmente el tiempo de espera indicado por la AEAT."""
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE verifactu_outbox SET next_attempt_at=?, updated_at=? "
            "WHERE status='pendiente' AND next_attempt_at<?",
            (until, updated_at, until),
        )
        return max(0, cursor.rowcount)


def verifactu_queue_counts() -> dict[str, int]:
    counts = {
        "pendiente": 0,
        "enviado": 0,
        "aceptado": 0,
        "aceptado_con_errores": 0,
        "rechazado": 0,
        "agotado": 0,
    }
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS total FROM verifactu_outbox "
            "GROUP BY status"
        ).fetchall()
        exhausted = conn.execute(
            "SELECT COUNT(*) AS total FROM verifactu_outbox "
            "WHERE status='pendiente' AND attempts>=max_attempts"
        ).fetchone()
    for row in rows:
        counts[row["status"]] = int(row["total"])
    counts["agotado"] = int(exhausted["total"])
    return counts


def verify_invoice_record_chain(
    business_id: int, issuer_nif: str | None = None
) -> dict:
    business = get_business(business_id)
    if not business:
        return {
            "valid": False, "checked": 0, "broken_at": None,
            "error": "Negocio no encontrado.",
        }
    records = list_invoice_records(business_id)
    if issuer_nif:
        target_nif = issuer_nif.strip().upper()
        records = [row for row in records if row["issuer_nif"] == target_nif]
    previous_by_issuer: dict[str, dict] = {}
    last_record = None
    for index, record in enumerate(records):
        previous = previous_by_issuer.get(record["issuer_nif"])
        previous_hash = previous["record_hash"] if previous else None
        expected = verifactu.invoice_record_hash(
            algorithm=record["hash_algorithm"],
            issuer_nif=record["issuer_nif"],
            invoice_number=record["invoice_number"],
            issue_date=record["issue_date"],
            invoice_type=record["invoice_type"],
            vat_total=record["vat_total"],
            invoice_total=record["invoice_total"],
            previous_hash=previous_hash,
            generated_at=record["generated_at"],
        )
        if (
            record.get("previous_hash") != previous_hash
            or record.get("record_hash") != expected
        ):
            return {
                "valid": False,
                "checked": index,
                "broken_at": record["id"],
                "expected_hash": expected,
                "stored_hash": record.get("record_hash"),
            }
        previous_by_issuer[record["issuer_nif"]] = record
        last_record = record
    return {
        "valid": True,
        "checked": len(records),
        "broken_at": None,
        "last_hash": last_record["record_hash"] if last_record else None,
    }


def export_verifactu_xml(
    business_id: int,
    *,
    from_day: str | None = None,
    to_day: str | None = None,
) -> bytes:
    business = get_business(business_id)
    if not business:
        raise ValueError("Negocio no encontrado.")
    records = list_invoice_records(
        business_id, from_day=from_day, to_day=to_day
    )
    if not records:
        raise ValueError("No hay registros Veri*Factu en el periodo indicado.")
    integrity = verify_invoice_record_chain(business_id)
    if not integrity["valid"]:
        with get_conn() as conn:
            _record_invoice_event(
                conn, business_id, "anomalia",
                record_id=integrity.get("broken_at"),
                details=json.dumps(integrity, ensure_ascii=False),
            )
        raise ValueError(
            "La cadena Veri*Factu presenta una anomalía y no se puede exportar."
        )
    xml_business = dict(business)
    if records:
        xml_business["name"] = records[0]["issuer_name"]
        xml_business["nif"] = records[0]["issuer_nif"]
    elif not xml_business.get("nif"):
        raise ValueError("El negocio no tiene NIF para la cabecera XML.")
    payload = verifactu.build_aeat_xml(xml_business, records)
    with get_conn() as conn:
        _record_invoice_event(
            conn, business_id, "exportacion",
            details=json.dumps(
                {
                    "from": from_day,
                    "to": to_day,
                    "records": len(records),
                    "last_hash": integrity.get("last_hash"),
                },
                ensure_ascii=False,
            ),
        )
    return payload


def pending_payments(business_id) -> list[dict]:
    rows = [
        invoice for invoice in list_invoices(business_id)
        if invoice["status"] != "borrador"
        and invoice["remaining_amount"] > 0
    ]
    rows.sort(key=lambda item: item.get("issued_at") or "")
    out = []
    for r in rows:
        d = dict(r)
        d["invoice_total"] = d["total"]
        d["total"] = d["remaining_amount"]
        if d.get("issued_at"):
            issued = datetime.fromisoformat(d["issued_at"]).date()
            d["days_outstanding"] = (date.today() - issued).days
        else:
            d["days_outstanding"] = None
        out.append(d)
    return out


def global_search(business_id, query: str, limit: int = 6) -> dict:
    """Buscador global del negocio: clientes, facturas, presupuestos y trabajos
    por nombre, número, concepto o teléfono. Siempre aislado por business_id."""
    text = (query or "").strip()
    if len(text) < 2:
        return {"clients": [], "invoices": [], "quotes": [], "jobs": []}
    like = f"%{text.lower()}%"
    limit = max(1, min(int(limit or 6), 20))
    with get_conn() as conn:
        clients = conn.execute(
            "SELECT id, name, phone, zone FROM clients WHERE business_id=? "
            "AND (lower(name) LIKE ? OR lower(COALESCE(phone,'')) LIKE ? "
            "OR lower(COALESCE(nif,'')) LIKE ?) ORDER BY name LIMIT ?",
            (business_id, like, like, like, limit),
        ).fetchall()
        invoices = conn.execute(
            "SELECT i.id, i.number, i.concept, i.total, i.status, "
            "c.name AS client_name FROM invoices i "
            "LEFT JOIN clients c ON c.id=i.client_id "
            "AND c.business_id=i.business_id "
            "WHERE i.business_id=? AND (lower(COALESCE(i.number,'')) LIKE ? "
            "OR lower(i.concept) LIKE ? OR lower(COALESCE(c.name,'')) LIKE ?) "
            "ORDER BY i.id DESC LIMIT ?",
            (business_id, like, like, like, limit),
        ).fetchall()
        quotes = conn.execute(
            "SELECT q.id, q.number, q.concept, q.total, q.status, "
            "c.name AS client_name FROM quotes q "
            "LEFT JOIN clients c ON c.id=q.client_id "
            "AND c.business_id=q.business_id "
            "WHERE q.business_id=? AND (lower(COALESCE(q.number,'')) LIKE ? "
            "OR lower(q.concept) LIKE ? OR lower(COALESCE(c.name,'')) LIKE ?) "
            "ORDER BY q.id DESC LIMIT ?",
            (business_id, like, like, like, limit),
        ).fetchall()
        jobs = conn.execute(
            "SELECT j.id, j.description, j.scheduled_for, j.status, "
            "c.name AS client_name FROM jobs j "
            "LEFT JOIN clients c ON c.id=j.client_id "
            "AND c.business_id=j.business_id "
            "WHERE j.business_id=? AND (lower(j.description) LIKE ? "
            "OR lower(COALESCE(c.name,'')) LIKE ?) "
            "ORDER BY j.id DESC LIMIT ?",
            (business_id, like, like, limit),
        ).fetchall()
    return {
        "clients": [dict(r) for r in clients],
        "invoices": [dict(r) for r in invoices],
        "quotes": [dict(r) for r in quotes],
        "jobs": [dict(r) for r in jobs],
    }


def list_admin_emails() -> list[str]:
    """Correos de los administradores de Noesis (para los partes internos)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT email FROM users WHERE is_admin=TRUE ORDER BY email"
        ).fetchall()
        return [row["email"] for row in rows]


def cash_forecast(business_id, days: int = 30) -> dict:
    """Previsión de caja: lo que debería entrar (facturas pendientes de cobro),
    lo que suele salir (media de gastos de los últimos 90 días) y el IVA del
    trimestre en curso que conviene apartar. Estimación de apoyo, no contable."""
    days = max(7, min(int(days or 30), 90))
    pending = pending_payments(business_id)
    entra = round(sum(float(p["total"]) for p in pending), 2)
    today = date.today()
    since = (today - timedelta(days=90)).isoformat()
    with get_conn() as conn:
        spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS total FROM expenses "
            "WHERE business_id=? "
            "AND substr(CAST(COALESCE(spent_on, created_at) AS TEXT),1,10) >= ?",
            (business_id, since),
        ).fetchone()["total"]
    sale = round(float(spent) / 90 * days, 2)
    quarter = (today.month - 1) // 3 + 1
    try:
        taxes = tax_quarter(today.year, quarter, business_id)
        iva_reserva = max(float(taxes.get("iva_resultado") or 0), 0.0)
    except ValueError:
        iva_reserva = 0.0
    neto = round(entra - sale - iva_reserva, 2)
    return {
        "days": days,
        "entra": entra,
        "n_facturas": len(pending),
        "sale": sale,
        "iva_reserva": round(iva_reserva, 2),
        "neto": neto,
    }


# ----------------------------------------------------------------- Gastos ---
def add_expense(
    concept,
    amount,
    vat_rate=None,
    category=None,
    spent_on=None,
    document_id=None,
    *,
    business_id: int,
) -> dict:
    concept = (concept or "").strip()
    if not concept or len(concept) > 500:
        raise ValueError("El concepto es obligatorio y no puede superar 500 caracteres.")
    amount = _positive_money(amount, "El importe")
    if vat_rate not in (None, ""):
        vat_rate = _tax_rate(vat_rate, "El IVA", {0, 4, 10, 21})
    else:
        vat_rate = None
    if spent_on not in (None, ""):
        try:
            spent_on = date.fromisoformat(str(spent_on).strip()).isoformat()
        except ValueError as exc:
            raise ValueError("La fecha del gasto no es válida.") from exc
    else:
        spent_on = None
    if document_id not in (None, ""):
        try:
            document_id = int(document_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("El documento no es válido.") from exc
        if document_id <= 0:
            raise ValueError("El documento no es válido.")
    else:
        document_id = None
    with get_conn() as conn:
        if document_id is not None:
            conn.execute("BEGIN IMMEDIATE")
            lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
            document = conn.execute(
                "SELECT id, expense_id FROM documents "
                "WHERE id=? AND business_id=?" + lock,
                (document_id, business_id),
            ).fetchone()
            if not document:
                raise ValueError("Documento no encontrado.")
            if document["expense_id"] is not None:
                raise ValueError("Este documento ya está vinculado a un gasto.")
        row = conn.execute(
            "INSERT INTO expenses (business_id, concept, amount, vat_rate, category, "
            "spent_on, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, concept, amount, vat_rate, category,
             spent_on, _now()),
        ).fetchone()
        new_id = row["id"]
        if document_id is not None:
            linked = conn.execute(
                "UPDATE documents SET expense_id=? "
                "WHERE id=? AND business_id=? AND expense_id IS NULL",
                (new_id, document_id, business_id),
            )
            if linked.rowcount != 1:
                raise ValueError("No se pudo vincular el documento al gasto.")
        expense = dict(conn.execute(
            "SELECT * FROM expenses WHERE id=? AND business_id=?",
            (new_id, business_id),
        ).fetchone())
    expense["document_id"] = document_id
    return expense


def delete_expense(expense_id, business_id) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE documents SET expense_id=NULL "
            "WHERE expense_id=? AND business_id=?",
            (expense_id, business_id),
        )
        conn.execute("DELETE FROM expenses WHERE id=? AND business_id=?",
                     (expense_id, business_id))


def list_expenses(business_id) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM expenses WHERE business_id=? ORDER BY created_at DESC",
            (business_id,)).fetchall()]


# ------------------------------------------------------------- Proveedores ---
def _clean_nif(value) -> str | None:
    nif = (str(value or "")).strip().upper().replace(" ", "").replace("-", "")
    return nif or None


def add_supplier(name, nif=None, email=None, phone=None, note=None, *,
                 business_id: int) -> dict:
    name = (name or "").strip()
    if not name or len(name) > 200:
        raise ValueError("El nombre del proveedor es obligatorio (máx. 200).")
    nif = _clean_nif(nif)
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM suppliers WHERE business_id=? AND name=?",
            (business_id, name)).fetchone()
        if existing:
            raise ValueError("Ya existe un proveedor con ese nombre.")
        row = conn.execute(
            "INSERT INTO suppliers (business_id, name, nif, email, phone, note, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, name, nif, (email or "").strip() or None,
             (phone or "").strip() or None, (note or "").strip() or None,
             _now()),
        ).fetchone()
        return dict(conn.execute(
            "SELECT * FROM suppliers WHERE id=? AND business_id=?",
            (row["id"], business_id)).fetchone())


def get_supplier(supplier_id, business_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM suppliers WHERE id=? AND business_id=?",
            (supplier_id, business_id)).fetchone()
        return dict(row) if row else None


def list_suppliers(business_id) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM suppliers WHERE business_id=? ORDER BY name",
            (business_id,)).fetchall()]


def find_supplier(business_id, *, nif=None, name=None) -> dict | None:
    """Busca proveedor por NIF (prioritario) o nombre exacto, para no duplicar."""
    nif = _clean_nif(nif)
    with get_conn() as conn:
        if nif:
            row = conn.execute(
                "SELECT * FROM suppliers WHERE business_id=? AND nif=?",
                (business_id, nif)).fetchone()
            if row:
                return dict(row)
        name = (name or "").strip()
        if name:
            row = conn.execute(
                "SELECT * FROM suppliers WHERE business_id=? AND name=?",
                (business_id, name)).fetchone()
            if row:
                return dict(row)
    return None


# ------------------------------------------------------ Facturas recibidas ---
RECEIVED_STATUSES = {"pendiente", "pagada"}


def _optional_date(value, label: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError as exc:
        raise ValueError(f"{label} no es una fecha válida.") from exc


def add_received_invoice(total, supplier_id=None, number=None, concept=None,
                         issued_on=None, due_on=None, base=None, vat_rate=None,
                         vat_amount=None, irpf_amount=None, category=None,
                         note=None, document_id=None, *,
                         business_id: int) -> dict:
    """Registra una factura recibida y, si se indica, la vincula a su documento.

    Nunca la crea la IA directamente: este es el paso de confirmación humana.
    """
    total = _positive_money(total, "El total")
    if vat_rate not in (None, ""):
        vat_rate = _tax_rate(vat_rate, "El IVA", {0, 4, 10, 21})
    else:
        vat_rate = None
    for field_label, value in (("La base", base), ("La cuota de IVA", vat_amount),
                               ("El IRPF", irpf_amount)):
        if value not in (None, "") and float(value) < 0:
            raise ValueError(f"{field_label} no puede ser negativa.")
    base = round(float(base), 2) if base not in (None, "") else None
    vat_amount = round(float(vat_amount), 2) if vat_amount not in (None, "") else None
    irpf_amount = round(float(irpf_amount), 2) if irpf_amount not in (None, "") else None
    issued_on = _optional_date(issued_on, "La fecha de emisión")
    due_on = _optional_date(due_on, "El vencimiento")
    number = (number or "").strip()[:50] or None
    concept = (concept or "").strip()[:500] or None
    with get_conn() as conn:
        if supplier_id not in (None, ""):
            supplier = conn.execute(
                "SELECT id FROM suppliers WHERE id=? AND business_id=?",
                (supplier_id, business_id)).fetchone()
            if not supplier:
                raise ValueError("Proveedor no encontrado.")
        else:
            supplier_id = None
        if document_id not in (None, ""):
            conn.execute("BEGIN IMMEDIATE")
            lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
            document = conn.execute(
                "SELECT id, received_invoice_id, expense_id FROM documents "
                "WHERE id=? AND business_id=?" + lock,
                (document_id, business_id),
            ).fetchone()
            if not document:
                raise ValueError("Documento no encontrado.")
            if document["received_invoice_id"] is not None:
                raise ValueError(
                    "Este documento ya está vinculado a una factura recibida.")
            if document["expense_id"] is not None:
                raise ValueError("Este documento ya está vinculado a un gasto.")
        else:
            document_id = None
        row = conn.execute(
            "INSERT INTO received_invoices (business_id, supplier_id, number, "
            "concept, issued_on, due_on, base, vat_rate, vat_amount, "
            "irpf_amount, total, status, category, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?, ?) "
            "RETURNING id",
            (business_id, supplier_id, number, concept, issued_on, due_on,
             base, vat_rate, vat_amount, irpf_amount, total, category,
             (note or "").strip() or None, _now()),
        ).fetchone()
        new_id = row["id"]
        if document_id is not None:
            linked = conn.execute(
                "UPDATE documents SET received_invoice_id=?, "
                "doc_status='revisado', reviewed_at=? "
                "WHERE id=? AND business_id=? AND received_invoice_id IS NULL",
                (new_id, _now(), document_id, business_id),
            )
            if linked.rowcount != 1:
                raise ValueError(
                    "No se pudo vincular el documento a la factura recibida.")
        received = dict(conn.execute(
            "SELECT * FROM received_invoices WHERE id=? AND business_id=?",
            (new_id, business_id)).fetchone())
    received["document_id"] = document_id
    return received


def get_received_invoice(received_id, business_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT r.*, s.name AS supplier_name FROM received_invoices r "
            "LEFT JOIN suppliers s ON s.id=r.supplier_id "
            "AND s.business_id=r.business_id "
            "WHERE r.id=? AND r.business_id=?",
            (received_id, business_id)).fetchone()
        return dict(row) if row else None


def list_received_invoices(business_id, status=None) -> list[dict]:
    q = ("SELECT r.*, s.name AS supplier_name FROM received_invoices r "
         "LEFT JOIN suppliers s ON s.id=r.supplier_id "
         "AND s.business_id=r.business_id WHERE r.business_id=?")
    params: list = [business_id]
    if status:
        if status not in RECEIVED_STATUSES:
            raise ValueError("Estado de factura recibida desconocido.")
        q += " AND r.status=?"
        params.append(status)
    # issued_on es TEXT y created_at es timestamp: en Postgres COALESCE exige el
    # mismo tipo, así que casteamos created_at a texto (en SQLite es indiferente).
    q += " ORDER BY COALESCE(r.issued_on, CAST(r.created_at AS TEXT)) DESC, r.id DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def set_received_invoice_status(received_id, status, *, business_id) -> dict:
    if status not in RECEIVED_STATUSES:
        raise ValueError("Estado de factura recibida desconocido.")
    with get_conn() as conn:
        updated = conn.execute(
            "UPDATE received_invoices SET status=? WHERE id=? AND business_id=?",
            (status, received_id, business_id))
        if updated.rowcount != 1:
            raise ValueError("Factura recibida no encontrada.")
    return get_received_invoice(received_id, business_id)


def delete_received_invoice(received_id, business_id) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE documents SET received_invoice_id=NULL "
            "WHERE received_invoice_id=? AND business_id=?",
            (received_id, business_id))
        conn.execute(
            "DELETE FROM received_invoices WHERE id=? AND business_id=?",
            (received_id, business_id))


# ---------------------------------------------------- Productos y servicios ---
PRODUCT_KINDS = {"producto", "servicio"}


def add_product(name, kind="servicio", price=0, cost=None, vat_rate=None,
                unit=None, category=None, stock=None, stock_alert=None,
                note=None, *, business_id: int) -> dict:
    name = (name or "").strip()
    if not name or len(name) > 200:
        raise ValueError("El nombre es obligatorio (máx. 200 caracteres).")
    if kind not in PRODUCT_KINDS:
        raise ValueError("El tipo debe ser 'producto' o 'servicio'.")
    try:
        price = round(float(price or 0), 2)
    except (TypeError, ValueError) as exc:
        raise ValueError("El precio no es válido.") from exc
    if price < 0:
        raise ValueError("El precio no puede ser negativo.")
    if cost not in (None, ""):
        cost = round(float(cost), 2)
        if cost < 0:
            raise ValueError("El coste no puede ser negativo.")
    else:
        cost = None
    if vat_rate not in (None, ""):
        vat_rate = _tax_rate(vat_rate, "El IVA", {0, 4, 10, 21})
    else:
        vat_rate = None
    for label, value in (("El stock", stock), ("El aviso de stock", stock_alert)):
        if value not in (None, "") and float(value) < 0:
            raise ValueError(f"{label} no puede ser negativo.")
    stock = float(stock) if stock not in (None, "") else None
    stock_alert = float(stock_alert) if stock_alert not in (None, "") else None
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT id FROM products WHERE business_id=? AND name=?",
            (business_id, name)).fetchone()
        if exists:
            raise ValueError("Ya existe un producto o servicio con ese nombre.")
        row = conn.execute(
            "INSERT INTO products (business_id, name, kind, price, cost, "
            "vat_rate, unit, category, stock, stock_alert, active, note, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE, ?, ?) "
            "RETURNING id",
            (business_id, name, kind, price, cost, vat_rate,
             (unit or "").strip() or None, (category or "").strip() or None,
             stock, stock_alert, (note or "").strip() or None, _now()),
        ).fetchone()
        created = dict(conn.execute(
            "SELECT * FROM products WHERE id=? AND business_id=?",
            (row["id"], business_id)).fetchone())
    return _product_with_margin(created)


def get_product(product_id, business_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE id=? AND business_id=?",
            (product_id, business_id)).fetchone()
    if not row:
        return None
    return _product_with_margin(dict(row))


def _product_with_margin(product: dict) -> dict:
    """Margen calculado SOLO si hay coste real; nunca se inventa."""
    price, cost = product.get("price"), product.get("cost")
    if cost is not None and price:
        product["margin"] = round(price - cost, 2)
        product["margin_pct"] = round((price - cost) / price * 100, 1)
    else:
        product["margin"] = None
        product["margin_pct"] = None
    stock, alert = product.get("stock"), product.get("stock_alert")
    product["low_stock"] = (stock is not None and alert is not None
                            and stock <= alert)
    return product


def list_products(business_id, include_inactive: bool = False) -> list[dict]:
    q = "SELECT * FROM products WHERE business_id=?"
    if not include_inactive:
        q += " AND active IN (TRUE, 1)"
    q += " ORDER BY name"
    with get_conn() as conn:
        rows = conn.execute(q, (business_id,)).fetchall()
    return [_product_with_margin(dict(r)) for r in rows]


def update_product(product_id, *, business_id: int, **fields) -> dict:
    allowed = {"name", "kind", "price", "cost", "vat_rate", "unit", "category",
               "stock", "stock_alert", "active", "note"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Campos no editables: {', '.join(sorted(unknown))}.")
    current = get_product(product_id, business_id)
    if not current:
        raise ValueError("Producto no encontrado.")
    merged = {key: fields.get(key, current.get(key)) for key in allowed}
    if "active" in fields:
        merged["active"] = bool(fields["active"])
    # Revalida TODO con las mismas reglas del alta (sin duplicar el nombre propio).
    name = (merged["name"] or "").strip()
    if not name or len(name) > 200:
        raise ValueError("El nombre es obligatorio (máx. 200 caracteres).")
    if merged["kind"] not in PRODUCT_KINDS:
        raise ValueError("El tipo debe ser 'producto' o 'servicio'.")
    price = round(float(merged["price"] or 0), 2)
    if price < 0:
        raise ValueError("El precio no puede ser negativo.")
    cost = merged["cost"]
    cost = round(float(cost), 2) if cost not in (None, "") else None
    if cost is not None and cost < 0:
        raise ValueError("El coste no puede ser negativo.")
    vat_rate = merged["vat_rate"]
    if vat_rate not in (None, ""):
        vat_rate = _tax_rate(vat_rate, "El IVA", {0, 4, 10, 21})
    else:
        vat_rate = None
    stock = merged["stock"]
    stock = float(stock) if stock not in (None, "") else None
    stock_alert = merged["stock_alert"]
    stock_alert = float(stock_alert) if stock_alert not in (None, "") else None
    with get_conn() as conn:
        clash = conn.execute(
            "SELECT id FROM products WHERE business_id=? AND name=? AND id<>?",
            (business_id, name, product_id)).fetchone()
        if clash:
            raise ValueError("Ya existe un producto o servicio con ese nombre.")
        conn.execute(
            "UPDATE products SET name=?, kind=?, price=?, cost=?, vat_rate=?, "
            "unit=?, category=?, stock=?, stock_alert=?, active=?, note=? "
            "WHERE id=? AND business_id=?",
            (name, merged["kind"], price, cost, vat_rate,
             (merged["unit"] or "").strip() or None,
             (merged["category"] or "").strip() or None,
             stock, stock_alert, merged["active"],
             (merged["note"] or "").strip() or None,
             product_id, business_id))
    return get_product(product_id, business_id)


# ------------------------------------------------------------------ CRM ------
LEAD_STATUSES = {"nuevo", "contactado", "interesado", "presupuesto_enviado",
                 "seguimiento", "ganado", "perdido", "dormido"}


def add_lead(name, phone=None, email=None, source=None, note=None,
             value_estimate=None, next_action_on=None, *,
             business_id: int) -> dict:
    name = (name or "").strip()
    if not name or len(name) > 200:
        raise ValueError("El nombre del lead es obligatorio (máx. 200).")
    if value_estimate not in (None, ""):
        value_estimate = round(float(value_estimate), 2)
        if value_estimate < 0:
            raise ValueError("El valor estimado no puede ser negativo.")
    else:
        value_estimate = None
    next_action_on = _optional_date(next_action_on, "La fecha de seguimiento")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO leads (business_id, name, phone, email, source, "
            "status, value_estimate, note, next_action_on, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'nuevo', ?, ?, ?, ?) RETURNING id",
            (business_id, name, (phone or "").strip() or None,
             (email or "").strip() or None, (source or "").strip() or None,
             value_estimate, (note or "").strip() or None, next_action_on,
             _now()),
        ).fetchone()
        return dict(conn.execute(
            "SELECT * FROM leads WHERE id=? AND business_id=?",
            (row["id"], business_id)).fetchone())


def get_lead(lead_id, business_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM leads WHERE id=? AND business_id=?",
            (lead_id, business_id)).fetchone()
        return dict(row) if row else None


def list_leads(business_id, status=None) -> list[dict]:
    q = "SELECT * FROM leads WHERE business_id=?"
    params: list = [business_id]
    if status:
        if status not in LEAD_STATUSES:
            raise ValueError("Estado de lead desconocido.")
        q += " AND status=?"
        params.append(status)
    q += (" ORDER BY CASE WHEN next_action_on IS NULL THEN 1 ELSE 0 END, "
          "next_action_on, created_at DESC")
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def update_lead(lead_id, *, business_id: int, status=None, note=None,
                next_action_on=None, value_estimate=None) -> dict:
    lead = get_lead(lead_id, business_id)
    if not lead:
        raise ValueError("Lead no encontrado.")
    if status is not None and status not in LEAD_STATUSES:
        raise ValueError("Estado de lead desconocido.")
    updates, params = ["updated_at=?"], [_now()]
    if status is not None:
        updates.append("status=?")
        params.append(status)
    if note is not None:
        updates.append("note=?")
        params.append(note.strip()[:1000] or None)
    if next_action_on is not None:
        updates.append("next_action_on=?")
        params.append(_optional_date(next_action_on, "La fecha de seguimiento"))
    if value_estimate is not None:
        value = round(float(value_estimate), 2)
        if value < 0:
            raise ValueError("El valor estimado no puede ser negativo.")
        updates.append("value_estimate=?")
        params.append(value)
    params.extend([lead_id, business_id])
    with get_conn() as conn:
        conn.execute(f"UPDATE leads SET {', '.join(updates)} "
                     "WHERE id=? AND business_id=?", params)
    return get_lead(lead_id, business_id)


def convert_lead_to_client(lead_id, *, business_id: int) -> dict:
    """Lead ganado → cliente real (o vínculo al existente por nombre)."""
    lead = get_lead(lead_id, business_id)
    if not lead:
        raise ValueError("Lead no encontrado.")
    if lead.get("client_id"):
        raise ValueError("Este lead ya está convertido en cliente.")
    client = find_client(lead["name"], business_id) if lead.get("name") else None
    if not client:
        client = add_client(lead["name"], phone=lead.get("phone"),
                            email=lead.get("email"), business_id=business_id)
    with get_conn() as conn:
        conn.execute(
            "UPDATE leads SET status='ganado', client_id=?, updated_at=? "
            "WHERE id=? AND business_id=?",
            (client["id"], _now(), lead_id, business_id))
    return {"lead": get_lead(lead_id, business_id), "client": client}


def leads_due_today(business_id) -> list[dict]:
    today = date.today().isoformat()
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM leads WHERE business_id=? AND next_action_on<=? "
            "AND status NOT IN ('ganado','perdido') ORDER BY next_action_on",
            (business_id, today)).fetchall()]


# ------------------------------------------------- Solicitudes de gestoría ---
GESTORIA_REQUEST_STATUSES = {"abierta", "respondida", "cerrada"}


def add_gestoria_request(message, requested_by="gestoria", document_id=None, *,
                         business_id: int) -> dict:
    message = (message or "").strip()
    if not message or len(message) > 2000:
        raise ValueError("El mensaje es obligatorio (máx. 2000 caracteres).")
    if requested_by not in {"gestoria", "autonomo"}:
        raise ValueError("Origen de la solicitud desconocido.")
    with get_conn() as conn:
        if document_id not in (None, ""):
            doc = conn.execute(
                "SELECT id FROM documents WHERE id=? AND business_id=?",
                (document_id, business_id)).fetchone()
            if not doc:
                raise ValueError("Documento no encontrado.")
        else:
            document_id = None
        row = conn.execute(
            "INSERT INTO gestoria_requests (business_id, requested_by, message, "
            "status, document_id, created_at) VALUES (?, ?, ?, 'abierta', ?, ?) "
            "RETURNING id",
            (business_id, requested_by, message, document_id, _now()),
        ).fetchone()
        return dict(conn.execute(
            "SELECT * FROM gestoria_requests WHERE id=? AND business_id=?",
            (row["id"], business_id)).fetchone())


def list_gestoria_requests(business_id, status=None) -> list[dict]:
    q = "SELECT * FROM gestoria_requests WHERE business_id=?"
    params: list = [business_id]
    if status:
        if status not in GESTORIA_REQUEST_STATUSES:
            raise ValueError("Estado de solicitud desconocido.")
        q += " AND status=?"
        params.append(status)
    q += " ORDER BY created_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def reply_gestoria_request(request_id, reply, *, business_id: int,
                           document_id=None, close: bool = False) -> dict:
    reply = (reply or "").strip()
    if not reply or len(reply) > 2000:
        raise ValueError("La respuesta es obligatoria (máx. 2000 caracteres).")
    status = "cerrada" if close else "respondida"
    with get_conn() as conn:
        if document_id not in (None, ""):
            doc = conn.execute(
                "SELECT id FROM documents WHERE id=? AND business_id=?",
                (document_id, business_id)).fetchone()
            if not doc:
                raise ValueError("Documento no encontrado.")
            conn.execute(
                "UPDATE gestoria_requests SET document_id=? "
                "WHERE id=? AND business_id=?",
                (document_id, request_id, business_id))
        updated = conn.execute(
            "UPDATE gestoria_requests SET reply=?, status=?, replied_at=? "
            "WHERE id=? AND business_id=?",
            (reply, status, _now(), request_id, business_id))
        if updated.rowcount != 1:
            raise ValueError("Solicitud no encontrada.")
        return dict(conn.execute(
            "SELECT * FROM gestoria_requests WHERE id=? AND business_id=?",
            (request_id, business_id)).fetchone())


# ------------------------------------------------- Pérdidas y ganancias ------
def profit_and_loss(business_id, year: int | None = None) -> dict:
    """P&G orientativo del año. REGLA: sin datos suficientes, no se inventa el
    número — se devuelve None y se explica qué falta en 'missing'."""
    year = year or date.today().year
    prefix = f"{year}-"
    invoices = [
        inv for inv in list_invoices(business_id)
        if inv["status"] in {"enviada", "parcial", "cobrada"}
        and str(inv.get("issued_at") or inv.get("created_at") or "").startswith(prefix)
    ]
    with get_conn() as conn:
        expense_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM expenses WHERE business_id=? "
            "AND CAST(COALESCE(spent_on, created_at) AS TEXT) LIKE ?",
            (business_id, f"{prefix}%")).fetchall()]
        received_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM received_invoices WHERE business_id=? "
            "AND COALESCE(issued_on, CAST(created_at AS TEXT)) LIKE ?",
            (business_id, f"{prefix}%")).fetchall()]

    revenue = round(sum(inv["base"] for inv in invoices), 2)
    # Gasto SIN IVA cuando se conoce el tipo; si no, el importe tal cual (y se avisa).
    expense_base = sum(
        e["amount"] / (1 + (e.get("vat_rate") or 0) / 100) if e.get("vat_rate")
        else e["amount"] for e in expense_rows)
    received_base = sum(
        r["base"] if r.get("base") is not None else r["total"]
        for r in received_rows)
    costs = round(expense_base + received_base, 2)

    missing: list[str] = []
    if not invoices:
        missing.append("No hay facturas emitidas este año: sin ingresos que contar.")
    if not expense_rows and not received_rows:
        missing.append("No hay gastos ni facturas recibidas registrados: el "
                       "resultado saldría inflado.")
    untyped = [e for e in expense_rows if not e.get("vat_rate")]
    if untyped:
        missing.append(f"{len(untyped)} gasto(s) sin IVA especificado: se cuentan "
                       "con IVA incluido y el coste real es algo menor.")
    missing.append("Amortizaciones e intereses no están registrados en Noesis: "
                   "el EBITDA y el resultado son aproximados. El cierre "
                   "definitivo es de tu gestoría.")

    complete = bool(invoices) and bool(expense_rows or received_rows)
    result = round(revenue - costs, 2) if complete else None
    return {
        "year": year,
        "revenue": revenue if invoices else None,
        "costs": costs if (expense_rows or received_rows) else None,
        "gross_result": result,
        # Sin datos de amortización/financieros, EBITDA ≈ resultado operativo.
        "ebitda_estimate": result,
        "margin_pct": (round(result / revenue * 100, 1)
                       if complete and revenue else None),
        "invoice_count": len(invoices),
        "expense_count": len(expense_rows) + len(received_rows),
        "missing": missing,
    }


# ----------------------------------------------------------------- Idioma ----
LANGUAGES = {"es": "Español", "ca": "Català", "en": "English"}


def update_language(business_id, language) -> None:
    if language not in LANGUAGES:
        raise ValueError("Idioma no disponible.")
    with get_conn() as conn:
        conn.execute("UPDATE businesses SET language=? WHERE id=?",
                     (language, business_id))


# --------------------------------------------------------------- Resúmenes ---
def month_billing(month: str | None = None, *, business_id: int) -> dict:
    month = month or date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("El mes debe tener formato YYYY-MM.")
    invoices = [
        invoice for invoice in list_invoices(business_id)
        if invoice["status"] in {"enviada", "parcial", "cobrada"}
        and str(invoice.get("issued_at") or invoice.get("created_at", "")).startswith(
            month
        )
    ]
    with get_conn() as conn:
        collected_rows = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS total FROM invoice_payments "
            "WHERE business_id=? AND CAST(paid_at AS TEXT) LIKE ?",
            (business_id, f"{month}%"),
        ).fetchone()["total"]
        expense_rows = [
            dict(row) for row in conn.execute(
                "SELECT * FROM expenses WHERE business_id=? "
                "AND CAST(COALESCE(spent_on, created_at) AS TEXT) LIKE ?",
                (business_id, f"{month}%"),
            ).fetchall()
        ]
    invoiced = sum(item["total"] for item in invoices)
    revenue_base = sum(item["base"] for item in invoices)
    pending = sum(item["remaining_amount"] for item in invoices)
    vat_output = sum(item["vat_amount"] for item in invoices)
    expenses = sum(item["amount"] for item in expense_rows)
    expense_base = sum(
        item["amount"] / (1 + (item.get("vat_rate") or 0) / 100)
        if item.get("vat_rate") else item["amount"]
        for item in expense_rows
    )
    vat_input = expenses - expense_base
    return {
        "month": month,
        "invoiced": round(invoiced, 2),
        "revenue_base": round(revenue_base, 2),
        "collected": round(collected_rows, 2),
        "pending": round(pending, 2),
        "vat_output": round(vat_output, 2),
        "vat_input": round(vat_input, 2),
        "vat_estimated": round(vat_output - vat_input, 2),
        "expenses": round(expenses, 2),
        "expense_base": round(expense_base, 2),
        "estimated_profit": round(revenue_base - expense_base, 2),
    }


def expenses_by_category(business_id) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT COALESCE(NULLIF(category,''),'Sin categoría') AS category, "
            "SUM(amount) AS total, COUNT(*) AS n FROM expenses "
            "WHERE business_id=? GROUP BY category ORDER BY total DESC",
            (business_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def income_by_client(business_id, limit: int = 8) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.name AS client_name, SUM(i.total) AS total, COUNT(*) AS n "
            "FROM invoices i LEFT JOIN clients c ON c.id=i.client_id "
            "AND c.business_id=i.business_id "
            "WHERE i.business_id=? AND i.status IN ('enviada','parcial','cobrada') "
            "GROUP BY i.client_id ORDER BY total DESC LIMIT ?",
            (business_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def client_stats(business_id) -> list[dict]:
    """Cada cliente con su facturación total, nº facturas y nº trabajos."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.*, "
            " (SELECT COALESCE(SUM(total),0) FROM invoices i WHERE i.client_id=c.id "
            "   AND i.business_id=c.business_id "
            "   AND i.status IN ('enviada','parcial','cobrada')) AS facturado, "
            " (SELECT COUNT(*) FROM invoices i WHERE i.client_id=c.id "
            "   AND i.business_id=c.business_id) AS n_facturas, "
            " (SELECT COUNT(*) FROM jobs j WHERE j.client_id=c.id "
            "   AND j.business_id=c.business_id) AS n_trabajos "
            "FROM clients c WHERE c.business_id=? ORDER BY facturado DESC",
            (business_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def financial_analysis(business_id) -> dict:
    """Cuadro de mando financiero: KPIs, márgenes, solvencia y morosidad.

    Se calcula sobre TODO el histórico (más significativo que un solo mes) a partir
    de los ayudantes ya existentes, para no duplicar SQL ni inventar fórmulas.
    Total de cada factura = base + IVA − IRPF. Ver docs/Fiscalidad.md.
    """
    invoices = [i for i in list_invoices(business_id) if i.get("status") != "borrador"]
    expenses = list_expenses(business_id)
    pend = pending_payments(business_id)
    clients = client_stats(business_id)

    invoiced = round(sum(i["total"] for i in invoices), 2)
    revenue_base = round(sum(i["base"] for i in invoices), 2)
    collected = round(sum(i["paid_amount"] for i in invoices), 2)
    pending = round(sum(i["remaining_amount"] for i in invoices), 2)
    gastos = round(sum(e["amount"] for e in expenses), 2)
    expense_base = round(sum(
        e["amount"] / (1 + (e.get("vat_rate") or 0) / 100)
        if e.get("vat_rate") else e["amount"]
        for e in expenses
    ), 2)
    beneficio = round(revenue_base - expense_base, 2)
    vat_repercutido = round(sum(i.get("vat_amount") or 0 for i in invoices), 2)
    # IVA soportado solo si el gasto guarda su tipo; si no, queda en 0 (no se inventa).
    vat_soportado = round(sum(
        (e["amount"] - e["amount"] / (1 + (e["vat_rate"] or 0) / 100)) if e.get("vat_rate") else 0
        for e in expenses), 2)

    n = len(invoices)
    ticket_medio = round(invoiced / n, 2) if n else 0.0
    margen_pct = round(beneficio / revenue_base * 100, 1) if revenue_base else 0.0
    ratio_gasto = round(expense_base / revenue_base * 100, 1) if revenue_base else 0.0
    cobro_pct = round(collected / invoiced * 100, 1) if invoiced else 0.0

    # DSO (días medios de cobro), ponderado por importe pendiente.
    tot_pend = sum(p["total"] for p in pend) or 0
    dso = round(sum((p.get("days_outstanding") or 0) * p["total"] for p in pend) / tot_pend) if tot_pend else 0
    morosidad = round(sum(p["total"] for p in pend if (p.get("days_outstanding") or 0) > 30), 2)
    morosidad_pct = round(morosidad / invoiced * 100, 1) if invoiced else 0.0

    # Solvencia operativa: cuántas veces cubre la caja cobrada los gastos del negocio.
    solvencia = round(collected / gastos, 2) if gastos else None

    # Concentración del mejor cliente sobre el total facturado.
    fact_total = sum(c.get("facturado") or 0 for c in clients) or 0
    top = clients[0] if clients else None
    concentracion = round(top["facturado"] / fact_total * 100) if (top and fact_total) else 0

    return {
        "invoiced": invoiced, "revenue_base": revenue_base,
        "collected": collected, "pending": pending,
        "gastos": gastos, "expense_base": expense_base,
        "beneficio": beneficio, "n_facturas": n,
        "ticket_medio": ticket_medio, "margen_pct": margen_pct,
        "ratio_gasto": ratio_gasto, "cobro_pct": cobro_pct,
        "dso": dso, "morosidad": morosidad, "morosidad_pct": morosidad_pct,
        "solvencia": solvencia, "concentracion": concentracion,
        "top_cliente": top["name"] if top else None,
        "vat_repercutido": vat_repercutido, "vat_soportado": vat_soportado,
        "vat_liquidar": round(vat_repercutido - vat_soportado, 2),
        "clientes_activos": len(clients),
    }


def monthly_series(business_id, months: int = 6) -> list[dict]:
    """Serie de los últimos N meses: ingresos vs gastos (para el gráfico)."""
    today = date.today()
    series = []
    for i in range(months - 1, -1, -1):
        y = today.year
        m = today.month - i
        while m <= 0:
            m += 12
            y -= 1
        key = f"{y:04d}-{m:02d}"
        b = month_billing(key, business_id=business_id)
        series.append({"month": key, "invoiced": b["invoiced"],
                       "expenses": b["expenses"], "profit": b["estimated_profit"]})
    return series


# ----------------------------------------------------------- Presupuestos ---
def add_quote(client_id, concept, base, vat_rate=config.DEFAULT_VAT_RATE,
              irpf_rate=0, valid_days=30, *, business_id: int) -> dict:
    """Crea un presupuesto (mismo cálculo que una factura, pero sin valor fiscal
    hasta que se acepta y se convierte en factura)."""
    if not get_client(client_id, business_id):
        raise ValueError("El cliente no pertenece a este negocio.")
    concept = (concept or "").strip()
    if not concept or len(concept) > 500:
        raise ValueError("El concepto es obligatorio y no puede superar 500 caracteres.")
    base = _positive_money(base, "La base")
    vat_rate = _tax_rate(vat_rate, "El IVA", {0, 4, 10, 21})
    irpf_rate = _tax_rate(irpf_rate, "El IRPF", {0, 7, 15})
    vat_amount = _tax_amount(base, vat_rate)
    irpf_amount = _tax_amount(base, irpf_rate)
    total = float(
        (
            Decimal(str(base))
            + Decimal(str(vat_amount))
            - Decimal(str(irpf_amount))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    valid_until = (date.today() + timedelta(days=valid_days)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO quotes (business_id, client_id, concept, base, vat_rate, "
            "vat_amount, irpf_rate, irpf_amount, total, status, valid_until, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?, ?) RETURNING id",
            (business_id, client_id, concept, base, vat_rate, vat_amount,
             irpf_rate or 0, irpf_amount, total, valid_until, _now()),
        ).fetchone()
        new_id = row["id"]
    return get_quote(new_id, business_id)


def get_quote(quote_id, business_id) -> dict | None:
    where = "q.id=? AND q.business_id=?"
    params = [quote_id, business_id]
    with get_conn() as conn:
        row = conn.execute(
            "SELECT q.*, c.name AS client_name FROM quotes q "
            "LEFT JOIN clients c ON c.id = q.client_id "
            "AND c.business_id=q.business_id WHERE " + where,
            params,
        ).fetchone()
        return dict(row) if row else None


def list_quotes(business_id, status=None) -> list[dict]:
    q = ("SELECT q.*, c.name AS client_name FROM quotes q "
         "LEFT JOIN clients c ON c.id = q.client_id "
         "AND c.business_id=q.business_id WHERE q.business_id=?")
    params: list = [business_id]
    if status:
        q += " AND q.status=?"
        params.append(status)
    q += " ORDER BY q.created_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def _next_quote_number(conn, business_id) -> str:
    year = date.today().year
    n = _next_document_number(conn, business_id, "quote")
    return f"P{year}/{n:04d}"


def mark_quote_sent(quote_id, business_id) -> dict | None:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT * FROM quotes WHERE id=? AND business_id=?" + lock,
            (quote_id, business_id),
        ).fetchone()
        if not row:
            return None
        if row["status"] in {"enviado", "aceptado"} and row["number"]:
            return get_quote(quote_id, business_id)
        if row["status"] != "borrador":
            raise ValueError("El presupuesto no se puede enviar desde su estado actual.")
        number = row["number"] or _next_quote_number(conn, business_id)
        conn.execute("UPDATE quotes SET status='enviado', number=? "
                     "WHERE id=? AND business_id=? AND status='borrador'",
                     (number, quote_id, business_id))
    return get_quote(quote_id, business_id)


def reject_quote(quote_id, business_id) -> dict | None:
    with get_conn() as conn:
        cur = conn.execute("UPDATE quotes SET status='rechazado' "
                           "WHERE id=? AND business_id=?", (quote_id, business_id))
        ok = cur.rowcount > 0
    return get_quote(quote_id, business_id) if ok else None


def accept_quote(quote_id, business_id) -> dict | None:
    """Acepta un presupuesto y crea la factura borrador equivalente. Aislado por
    negocio: si el presupuesto no es de ese negocio, no hace nada."""
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        q = conn.execute(
            "SELECT * FROM quotes WHERE id=? AND business_id=?" + lock,
            (quote_id, business_id),
        ).fetchone()
        if not q:
            return None
        if q["status"] == "aceptado" and q["invoice_id"]:
            return {
                "quote": get_quote(quote_id, business_id),
                "invoice": get_invoice(q["invoice_id"], business_id),
            }
        if q["status"] != "enviado":
            raise ValueError("Primero debes enviar el presupuesto antes de aceptarlo.")
        invoice_row = conn.execute(
            "INSERT INTO invoices (business_id, client_id, concept, base, vat_rate, "
            "vat_amount, irpf_rate, irpf_amount, total, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?) RETURNING id",
            (
                business_id, q["client_id"], q["concept"], q["base"], q["vat_rate"],
                q["vat_amount"], q["irpf_rate"], q["irpf_amount"], q["total"], _now(),
            ),
        ).fetchone()
        invoice_id = invoice_row["id"]
        conn.execute(
            "UPDATE quotes SET status='aceptado', accepted_at=?, invoice_id=? "
            "WHERE id=? AND business_id=? AND status='enviado'",
            (_now(), invoice_id, quote_id, business_id),
        )
    return {
        "quote": get_quote(quote_id, business_id),
        "invoice": get_invoice(invoice_id, business_id),
    }


def delete_quote(quote_id, business_id) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM quotes WHERE id=? AND business_id=? AND status='borrador'",
            (quote_id, business_id),
        )
        return cur.rowcount > 0


# -------------------------------------------------------- Impuestos (303/130) ---
_QUARTERS = {1: ("01", "03"), 2: ("04", "06"), 3: ("07", "09"), 4: ("10", "12")}


def tax_quarter(year: int, quarter: int, business_id) -> dict:
    """Resumen fiscal de un trimestre: IVA (modelo 303) e IRPF pago fraccionado
    (modelo 130, estimación directa simplificada). Son CIFRAS DE APOYO para el
    gestor, no una presentación oficial."""
    if quarter not in _QUARTERS:
        raise ValueError("El trimestre debe estar entre 1 y 4.")
    m0, m1 = _QUARTERS[quarter]
    quarter_start, end = f"{year}-{m0}", f"{year}-{m1}"
    year_start = f"{year}-01"

    def _in_range(d: str | None, start: str) -> bool:
        return bool(d) and start <= d[:7] <= end

    all_invoices = [
        i for i in list_invoices(business_id)
        if i.get("status") in ("enviada", "parcial", "cobrada")
    ]
    all_expenses = list_expenses(business_id)
    invoices = [
        i for i in all_invoices
        if _in_range(i.get("issued_at") or i.get("created_at"), year_start)
    ]
    expenses = [
        e for e in all_expenses
        if _in_range(e.get("spent_on") or e.get("created_at"), year_start)
    ]
    quarter_invoices = [
        i for i in all_invoices
        if _in_range(i.get("issued_at") or i.get("created_at"), quarter_start)
    ]
    quarter_expenses = [
        e for e in all_expenses
        if _in_range(e.get("spent_on") or e.get("created_at"), quarter_start)
    ]

    ingresos = round(sum(i["base"] for i in invoices), 2)
    iva_repercutido = round(
        sum(i.get("vat_amount") or 0 for i in quarter_invoices), 2
    )
    irpf_retenido = round(sum(i.get("irpf_amount") or 0 for i in invoices), 2)
    gastos = round(sum(e["amount"] for e in expenses), 2)
    # IVA soportado solo de gastos que registran su tipo (no se inventa).
    iva_soportado = round(sum(
        (e["amount"] - e["amount"] / (1 + (e["vat_rate"] or 0) / 100)) if e.get("vat_rate") else 0
        for e in quarter_expenses), 2)
    base_gastos = round(sum(
        (e["amount"] / (1 + (e["vat_rate"] or 0) / 100)) if e.get("vat_rate") else e["amount"]
        for e in expenses), 2)

    iva_resultado = round(iva_repercutido - iva_soportado, 2)          # modelo 303
    rendimiento = round(ingresos - base_gastos, 2)
    # Modelo 130: datos acumulados desde enero hasta el fin del trimestre. Restamos
    # los pagos estimados de trimestres anteriores para obtener el importe del periodo.
    irpf_acumulado = round(max(rendimiento * 0.20 - irpf_retenido, 0), 2)
    pagos_previos = round(sum(
        tax_quarter(year, previous, business_id)["irpf_pago"]
        for previous in range(1, quarter)
    ), 2)
    irpf_pago = round(max(irpf_acumulado - pagos_previos, 0), 2)

    return {
        "year": year, "quarter": quarter, "label": f"{quarter}T {year}",
        "ingresos": ingresos, "iva_repercutido": iva_repercutido,
        "gastos": gastos, "base_gastos": base_gastos, "iva_soportado": iva_soportado,
        "iva_resultado": iva_resultado, "irpf_retenido": irpf_retenido,
        "rendimiento": rendimiento, "irpf_acumulado": irpf_acumulado,
        "pagos_previos_estimados": pagos_previos, "irpf_pago": irpf_pago,
        "n_facturas": len(quarter_invoices), "n_gastos": len(quarter_expenses),
    }


# ----------------------------------------------------------- Recordatorios ---
def overdue_invoices(business_id, min_days: int = 1) -> list[dict]:
    """Facturas enviadas cuyo vencimiento ya pasó (para reclamar el cobro)."""
    out = []
    for p in pending_payments(business_id):
        due = p.get("due_date")
        days_late = None
        if due:
            days_late = (date.today() - date.fromisoformat(due[:10])).days
        if days_late is not None and days_late >= min_days:
            p["days_late"] = days_late
            out.append(p)
    return out


def mark_reminder_sent(invoice_id, business_id) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE invoices SET last_reminder_at=?, "
            "reminders_sent=COALESCE(reminders_sent,0)+1 "
            "WHERE id=? AND business_id=?", (_now(), invoice_id, business_id))


# ------------------------------------------------- Reset de contraseña ---
def set_password(user_id, password_hash) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET password_hash=?, "
                     "session_version=session_version+1 WHERE id=?",
                     (password_hash, user_id))


def create_password_reset(user_id, token_hash, ttl_minutes: int = 60) -> None:
    expires = (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO password_resets (user_id, token_hash, expires_at, created_at) "
            "VALUES (?, ?, ?, ?)", (user_id, token_hash, expires, _now()))


def use_password_reset(token_hash) -> dict | None:
    """Devuelve el reset válido (no usado, no caducado) y lo marca usado."""
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT * FROM password_resets "
            "WHERE token_hash=? AND used=FALSE" + lock,
            (token_hash,)).fetchone()
        if not row:
            return None
        if row["expires_at"] < datetime.now().isoformat(timespec="seconds"):
            return None
        conn.execute("UPDATE password_resets SET used=TRUE WHERE id=?", (row["id"],))
        return dict(row)


# --------------------------------------------------------- Suscripción ---
def set_trial(business_id, days: int = 14) -> None:
    ends = (date.today() + timedelta(days=days)).isoformat()
    with get_conn() as conn:
        conn.execute("UPDATE businesses SET subscription_status='trial', plan='trial', "
                     "trial_ends_at=? WHERE id=?", (ends, business_id))


def set_subscription(business_id, status, plan=None, customer_id=None,
                     subscription_id=None) -> dict | None:
    fields, params = ["subscription_status=?"], [status]
    for col, val in [("plan", plan), ("stripe_customer_id", customer_id),
                     ("stripe_subscription_id", subscription_id)]:
        if val is not None:
            fields.append(f"{col}=?")
            params.append(val)
    params.append(business_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE businesses SET {', '.join(fields)} WHERE id=?", params)
    return get_business(business_id)


def get_business_by_stripe_customer(customer_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM businesses WHERE stripe_customer_id=?",
                           (customer_id,)).fetchone()
        return dict(row) if row else None


def subscription_allows_access(business: dict | None) -> bool:
    if not business:
        return False
    status = business.get("subscription_status") or "trial"
    if status == "active":
        return True
    if status != "trial":
        return False
    ends = business.get("trial_ends_at")
    return not ends or ends >= date.today().isoformat()


def claim_webhook_event(
    source: str,
    event_id: str,
    *,
    stale_before: str | None = None,
) -> bool:
    """Reserva un evento y permite recuperar fallos o procesos abandonados."""
    if not event_id:
        return False
    now = _now()
    stale_before = stale_before or (
        datetime.now() - timedelta(minutes=5)
    ).isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        existing = conn.execute(
            "SELECT * FROM webhook_events WHERE source=? AND event_id=?" + lock,
            (source, event_id),
        ).fetchone()
        if existing:
            status = existing.get("status") or "done"
            if status == "done":
                return False
            if (
                status == "processing"
                and str(existing.get("locked_at") or "") > stale_before
            ):
                return False
            conn.execute(
                "UPDATE webhook_events SET status='processing', locked_at=?, "
                "processed_at=NULL, attempts=attempts+1, last_error=NULL "
                "WHERE source=? AND event_id=?",
                (now, source, event_id),
            )
            return True
        conn.execute(
            "INSERT INTO webhook_events "
            "(source, event_id, status, locked_at, attempts, created_at) "
            "VALUES (?, ?, 'processing', ?, 1, ?)",
            (source, event_id, now, now),
        )
        return True


def webhook_event(source: str, event_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM webhook_events WHERE source=? AND event_id=?",
            (source, event_id),
        ).fetchone()
        return dict(row) if row else None


def complete_webhook_event(source: str, event_id: str) -> None:
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "UPDATE webhook_events SET status='done', processed_at=?, "
            "locked_at=NULL, last_error=NULL WHERE source=? AND event_id=?",
            (now, source, event_id),
        )


def fail_webhook_event(source: str, event_id: str, error: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE webhook_events SET status='failed', locked_at=NULL, "
            "last_error=? WHERE source=? AND event_id=?",
            ((error or "error")[:1000], source, event_id),
        )


def enqueue_whatsapp_message(
    *,
    business_id: int | None,
    to_phone: str,
    message_type: str,
    text_body: str | None = None,
    template_name: str | None = None,
    template_language: str | None = None,
    template_params: str | None = None,
    idempotency_key: str | None = None,
    max_attempts: int = 6,
    now: str | None = None,
) -> dict:
    """Persiste un mensaje antes de intentar enviarlo a Meta."""
    if message_type not in {"text", "template"}:
        raise ValueError("Tipo de mensaje de WhatsApp no válido.")
    if message_type == "text" and not text_body:
        raise ValueError("Un mensaje de texto necesita contenido.")
    if message_type == "template" and not template_name:
        raise ValueError("Un mensaje de plantilla necesita nombre.")
    if not to_phone:
        raise ValueError("Falta el teléfono de destino.")
    created_at = now or _now()
    try:
        with get_conn() as conn:
            row = conn.execute(
                "INSERT INTO whatsapp_outbox "
                "(business_id, to_phone, message_type, text_body, template_name, "
                "template_language, template_params, idempotency_key, status, "
                "attempts, max_attempts, next_attempt_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, ?, ?, ?, ?) "
                "RETURNING id",
                (
                    business_id, to_phone, message_type, text_body, template_name,
                    template_language, template_params, idempotency_key,
                    max_attempts, created_at, created_at, created_at,
                ),
            ).fetchone()
            message_id = row["id"]
    except IntegrityError:
        if not idempotency_key:
            raise
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM whatsapp_outbox WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if not existing:
                raise
            if existing.get("business_id") != business_id:
                raise ValueError(
                    "La clave idempotente pertenece a otro negocio."
                )
            return dict(existing)
    return _get_whatsapp_message_internal(message_id)


def _get_whatsapp_message_internal(message_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_outbox WHERE id=?", (message_id,)
        ).fetchone()
        return dict(row) if row else None


def get_whatsapp_message(message_id: int, business_id: int) -> dict | None:
    """Lectura acotada al negocio para paneles, soporte y auditoría."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_outbox WHERE id=? AND business_id=?",
            (message_id, business_id),
        ).fetchone()
        return dict(row) if row else None


def get_whatsapp_message_by_idempotency_key(
    idempotency_key: str,
    business_id: int,
) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_outbox "
            "WHERE idempotency_key=? AND business_id=?",
            (idempotency_key, business_id),
        ).fetchone()
        return dict(row) if row else None


# ------------------------------------------ Confirmaciones por WhatsApp ---
def set_pending_action(business_id, phone, kind, payload: dict,
                       ttl_minutes: int = 30) -> dict:
    """Guarda el borrador pendiente de un teléfono (reemplaza el anterior)."""
    expires = (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat(
        timespec="seconds"
    )
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM whatsapp_pending_actions "
            "WHERE business_id=? AND phone=?",
            (business_id, phone),
        )
        row = conn.execute(
            "INSERT INTO whatsapp_pending_actions "
            "(business_id, phone, kind, payload, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, phone, kind, body, expires, _now()),
        ).fetchone()
        new_id = row["id"]
    return {"id": new_id, "business_id": business_id, "phone": phone,
            "kind": kind, "payload": body, "expires_at": expires}


def get_pending_action(business_id, phone) -> dict | None:
    """Devuelve la acción pendiente viva de un teléfono; purga la caducada."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_pending_actions "
            "WHERE business_id=? AND phone=?",
            (business_id, phone),
        ).fetchone()
        if not row:
            return None
        if str(row["expires_at"]) < _now():
            conn.execute(
                "DELETE FROM whatsapp_pending_actions WHERE id=? AND business_id=?",
                (row["id"], business_id),
            )
            return None
        return dict(row)


def clear_pending_action(business_id, phone) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM whatsapp_pending_actions WHERE business_id=? AND phone=?",
            (business_id, phone),
        )


# --------------------------------------------- Informes por WhatsApp ---
WHATSAPP_REPORT_DEFAULTS = {
    "brief_manana": True,
    "cierre_tarde": True,
    "hora_tarde": 19,
    "resumen_semanal": True,
    "aviso_fiscal": True,
}


def resolve_whatsapp_reports(raw) -> dict:
    """Preferencias de informes con tolerancia a JSON corrupto o versiones viejas."""
    prefs = dict(WHATSAPP_REPORT_DEFAULTS)
    if raw:
        try:
            data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (ValueError, TypeError):
            data = {}
        if isinstance(data, dict):
            for key in ("brief_manana", "cierre_tarde", "resumen_semanal",
                        "aviso_fiscal"):
                if key in data:
                    prefs[key] = bool(data[key])
            try:
                hora = int(data.get("hora_tarde", prefs["hora_tarde"]))
                if 17 <= hora <= 21:
                    prefs["hora_tarde"] = hora
            except (TypeError, ValueError):
                pass
    return prefs


def update_whatsapp_reports(business_id, prefs: dict) -> dict | None:
    clean = resolve_whatsapp_reports(prefs)
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE businesses SET whatsapp_reports=? WHERE id=?",
            (json.dumps(clean, separators=(",", ":")), business_id),
        )
        if cur.rowcount != 1:
            return None
    return get_business(business_id)


def payments_received_on(business_id, day: str) -> float:
    """Total cobrado un día concreto (YYYY-MM-DD) según el ledger de pagos."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS total FROM invoice_payments "
            "WHERE business_id=? AND CAST(paid_at AS TEXT) LIKE ?",
            (business_id, f"{day}%"),
        ).fetchone()
    return round(float(row["total"]), 2)


def find_whatsapp_message_by_meta_id(meta_message_id: str) -> dict | None:
    """Lookup interno para asociar callbacks de Meta, que no incluyen business_id."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_outbox WHERE meta_message_id=?",
            (meta_message_id,),
        ).fetchone()
        return dict(row) if row else None


def list_whatsapp_messages(business_id: int, limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM whatsapp_outbox WHERE business_id=? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (business_id, max(1, min(int(limit), 500))),
        ).fetchall()
        return [dict(row) for row in rows]


def claim_next_whatsapp_message(
    *,
    now: str,
    stale_before: str,
    only_ids: list[int] | None = None,
) -> dict | None:
    """Bloquea un mensaje vencido; SKIP LOCKED evita dobles envíos en Postgres."""
    filters = (
        "((status IN ('queued', 'retrying') AND next_attempt_at<=?) "
        "OR (status='processing' AND locked_at<=?))"
    )
    params: list[Any] = [now, stale_before]
    if only_ids:
        filters += f" AND id IN ({','.join('?' for _ in only_ids)})"
        params.extend(only_ids)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        suffix = " FOR UPDATE SKIP LOCKED" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT * FROM whatsapp_outbox WHERE " + filters
            + " ORDER BY next_attempt_at, id LIMIT 1" + suffix,
            tuple(params),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE whatsapp_outbox SET status='processing', attempts=attempts+1, "
            "locked_at=?, updated_at=? WHERE id=?",
            (now, now, row["id"]),
        )
        claimed = conn.execute(
            "SELECT * FROM whatsapp_outbox WHERE id=?", (row["id"],)
        ).fetchone()
        return dict(claimed)


def mark_whatsapp_sent(message_id: int, meta_message_id: str, sent_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE whatsapp_outbox SET status='sent', meta_message_id=?, "
            "sent_at=?, last_error=NULL, locked_at=NULL, updated_at=? "
            "WHERE id=? AND status='processing'",
            (meta_message_id, sent_at, sent_at, message_id),
        )


def mark_whatsapp_retry(
    message_id: int,
    *,
    error: str,
    next_attempt_at: str,
    updated_at: str,
) -> dict | None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE whatsapp_outbox SET "
            "status=CASE WHEN attempts>=max_attempts THEN 'failed' ELSE 'retrying' END, "
            "next_attempt_at=?, last_error=?, locked_at=NULL, updated_at=? "
            "WHERE id=? AND status='processing'",
            (next_attempt_at, error[:1000], updated_at, message_id),
        )
        row = conn.execute(
            "SELECT * FROM whatsapp_outbox WHERE id=?", (message_id,)
        ).fetchone()
        return dict(row) if row else None


def update_whatsapp_delivery(
    meta_message_id: str,
    status: str,
    event_at: str,
    error: str | None = None,
) -> dict | None:
    """Avanza el estado sin degradarlo si Meta entrega eventos desordenados."""
    if status not in {"sent", "delivered", "read", "failed"}:
        return None
    rank = {"queued": 0, "processing": 0, "retrying": 0, "sent": 1,
            "delivered": 2, "read": 3, "failed": -1}
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        suffix = " FOR UPDATE" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT * FROM whatsapp_outbox WHERE meta_message_id=?" + suffix,
            (meta_message_id,),
        ).fetchone()
        if not row:
            return None
        current = row["status"]
        next_status = status
        if status != "failed" and rank.get(current, 0) > rank[status]:
            next_status = current
        if status == "failed" and current in {"delivered", "read"}:
            next_status = current
        sent_at = (
            event_at
            if status == "sent" and not row.get("sent_at")
            else row.get("sent_at")
        )
        delivered_at = (
            event_at if status == "delivered" and not row.get("delivered_at")
            else row.get("delivered_at")
        )
        read_at = (
            event_at
            if status == "read" and not row.get("read_at")
            else row.get("read_at")
        )
        conn.execute(
            "UPDATE whatsapp_outbox SET status=?, sent_at=?, delivered_at=?, "
            "read_at=?, last_error=?, updated_at=? WHERE id=?",
            (
                next_status, sent_at, delivered_at, read_at,
                error[:1000] if error else row.get("last_error"),
                event_at, row["id"],
            ),
        )
        updated = conn.execute(
            "SELECT * FROM whatsapp_outbox WHERE id=?", (row["id"],)
        ).fetchone()
        return dict(updated)


def create_whatsapp_link(code_hash: str, business_id: int, expires_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM whatsapp_links WHERE business_id=? OR expires_at<?",
            (business_id, _now()),
        )
        conn.execute(
            "INSERT INTO whatsapp_links (code_hash, business_id, expires_at, created_at) "
            "VALUES (?, ?, ?, ?)",
            (code_hash, business_id, expires_at, _now()),
        )


def consume_whatsapp_link(code_hash: str) -> int | None:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT business_id FROM whatsapp_links "
            "WHERE code_hash=? AND expires_at>=?" + lock,
            (code_hash, _now()),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM whatsapp_links WHERE code_hash=?", (code_hash,))
        return row["business_id"]


# ---------------------------------------------------- Portal del cliente (Hub) ---
# Enlace privado sin contraseña: una URL-capacidad por cliente. El autónomo la envía
# (por WhatsApp) y su cliente entra a aprobar presupuestos, ver facturas y descargar
# PDF. El token va siempre ligado a (business_id, client_id): no cruza datos de otro
# cliente ni de otro negocio. Es revocable y caduca.
_PORTAL_TTL_DAYS = 120


def get_or_create_portal_token(business_id: int, client_id: int,
                               ttl_days: int = _PORTAL_TTL_DAYS) -> str | None:
    """Devuelve el enlace vigente del cliente o crea uno nuevo. Reutiliza el mismo
    token mientras no haya caducado ni se haya revocado, para que el enlace que el
    autónomo ya envió siga funcionando."""
    if not get_client(client_id, business_id):
        return None
    now = _now()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT token FROM portal_tokens WHERE business_id=? AND client_id=? "
            "AND revoked=FALSE AND expires_at>=? ORDER BY created_at DESC LIMIT 1",
            (business_id, client_id, now),
        ).fetchone()
        if row:
            return row["token"]
        token = secrets.token_urlsafe(24)
        expires = (datetime.now() + timedelta(days=ttl_days)).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO portal_tokens (token, business_id, client_id, expires_at, "
            "revoked, created_at) VALUES (?, ?, ?, ?, FALSE, ?)",
            (token, business_id, client_id, expires, now),
        )
        return token


def resolve_portal_token(token: str) -> dict | None:
    """Resuelve un token de portal a (business_id, client_id) si es válido. None si
    no existe, está revocado o caducado."""
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT business_id, client_id FROM portal_tokens "
            "WHERE token=? AND revoked=FALSE AND expires_at>=?",
            (token, _now()),
        ).fetchone()
        return dict(row) if row else None


def revoke_portal_tokens(client_id: int, business_id: int) -> None:
    """Invalida todos los enlaces de portal de un cliente (p. ej. al borrarlo)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE portal_tokens SET revoked=TRUE WHERE client_id=? AND business_id=?",
            (client_id, business_id),
        )


def client_portal_view(business_id: int, client_id: int) -> dict | None:
    """Datos que ve el cliente en su portal: el negocio que le atiende, sus
    presupuestos (para aprobar/rechazar) y sus facturas (para ver/descargar).
    Todo filtrado por (business_id, client_id): nada de otros clientes."""
    biz = get_business(business_id)
    client = get_client(client_id, business_id)
    if not biz or not client:
        return None
    quotes = [q for q in list_quotes(business_id) if q.get("client_id") == client_id]
    invoices = [i for i in list_invoices(business_id) if i.get("client_id") == client_id]
    logo = None
    if biz.get("logo_data") and biz.get("logo_mime"):
        logo = f"data:{biz['logo_mime']};base64,{biz['logo_data']}"
    return {
        "business": {"name": biz.get("name"), "nif": biz.get("nif"),
                     "address": biz.get("address"),
                     "brand_color": business_brand_color(biz),
                     "logo": logo,
                     "initials": business_initials(biz.get("name")),
                     "payment_iban": biz.get("payment_iban"),
                     "payment_bizum": biz.get("payment_bizum"),
                     "payment_note": biz.get("payment_note")},
        "client": {"id": client["id"], "name": client.get("name")},
        "quotes": quotes,
        "invoices": invoices,
    }


def claim_scheduled_run(run_key: str) -> bool:
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO scheduled_job_runs (run_key, created_at) VALUES (?, ?)",
                (run_key, _now()),
            )
        return True
    except IntegrityError:
        return False


def record_backup_result(
    filename: str | None,
    size_bytes: int,
    status: str,
    storage: str,
    error: str | None = None,
) -> dict:
    """Guarda el resultado global y deja el mismo evento en cada negocio.

    El backup contiene todos los negocios. Replicar el evento por ``business_id``
    mantiene la analítica aislada sin inventar un negocio global.
    """
    if status not in {"ok", "error"}:
        raise ValueError("El estado del backup no es válido.")
    created_at = _now()
    clean_error = (error or "").strip()[:300] or None
    event_data = json.dumps(
        {
            "created_at": created_at,
            "filename": filename,
            "size_bytes": max(0, int(size_bytes)),
            "status": status,
            "error": clean_error,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO backup_runs "
            "(created_at, filename, size_bytes, status, storage, error) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (
                created_at,
                filename,
                max(0, int(size_bytes)),
                status,
                storage,
                clean_error,
            ),
        ).fetchone()
        businesses = conn.execute("SELECT id FROM businesses ORDER BY id").fetchall()
        for business in businesses:
            conn.execute(
                "INSERT INTO product_events "
                "(business_id, event_name, event_data, created_at) "
                "VALUES (?, 'backup_verificado', ?, ?)",
                (business["id"], event_data, created_at),
            )
    return get_backup_run(row["id"])


def get_backup_run(backup_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM backup_runs WHERE id=?", (backup_id,)
        ).fetchone()
    return dict(row) if row else None


def latest_backup_run(*, status: str | None = None) -> dict | None:
    if status is not None and status not in {"ok", "error"}:
        raise ValueError("El estado del backup no es válido.")
    sql = "SELECT * FROM backup_runs"
    params: tuple = ()
    if status:
        sql += " WHERE status=?"
        params = (status,)
    sql += " ORDER BY created_at DESC, id DESC LIMIT 1"
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


# ----------------------------------------------------- Panel de administración ---
def ai_usage_summary(month: str | None = None) -> dict:
    """Tokens y llamadas de IA por negocio en un mes (de product_events)."""
    month = month or date.today().strftime("%Y-%m")
    per_business: dict[int, dict] = {}
    total = {"calls": 0, "input": 0, "output": 0, "extractions": 0}
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT business_id, event_name, event_data FROM product_events "
            "WHERE event_name IN ('ai_usage','media_ingested') "
            "AND CAST(created_at AS TEXT) LIKE ?",
            (f"{month}%",),
        ).fetchall()
    for row in rows:
        entry = per_business.setdefault(
            row["business_id"],
            {"calls": 0, "input": 0, "output": 0, "extractions": 0},
        )
        if row["event_name"] == "media_ingested":
            entry["extractions"] += 1
            total["extractions"] += 1
            continue
        try:
            data = json.loads(row["event_data"] or "{}")
        except ValueError:
            data = {}
        entry["calls"] += 1
        entry["input"] += int(data.get("in") or 0)
        entry["output"] += int(data.get("out") or 0)
        total["calls"] += 1
        total["input"] += int(data.get("in") or 0)
        total["output"] += int(data.get("out") or 0)
    return {"month": month, "total": total, "per_business": per_business}


def admin_alerts() -> list[dict]:
    """Alarmas operativas para el fundador: qué está fallando y dónde llamar."""
    alerts: list[dict] = []
    with get_conn() as conn:
        wa_failed = conn.execute(
            "SELECT COUNT(*) AS n FROM whatsapp_outbox WHERE status='failed'"
        ).fetchone()["n"]
        wa_stuck = conn.execute(
            "SELECT COUNT(*) AS n FROM whatsapp_outbox "
            "WHERE status IN ('queued','retrying') AND attempts>=3"
        ).fetchone()["n"]
        past_due = [dict(r) for r in conn.execute(
            "SELECT id, name, owner_email FROM businesses "
            "WHERE subscription_status IN ('past_due','unpaid')"
        ).fetchall()]
    if wa_failed:
        alerts.append({
            "level": "rojo", "area": "WhatsApp",
            "text": f"{wa_failed} mensaje(s) agotaron los reintentos (failed).",
        })
    if wa_stuck:
        alerts.append({
            "level": "ambar", "area": "WhatsApp",
            "text": f"{wa_stuck} mensaje(s) llevan 3+ intentos sin salir.",
        })
    verifactu = verifactu_queue_counts()
    if verifactu.get("rechazado"):
        alerts.append({
            "level": "rojo", "area": "Veri*Factu",
            "text": f"{verifactu['rechazado']} registro(s) RECHAZADOS por la AEAT.",
        })
    if verifactu.get("agotado"):
        alerts.append({
            "level": "rojo", "area": "Veri*Factu",
            "text": f"{verifactu['agotado']} registro(s) agotaron los reintentos.",
        })
    backup = latest_backup_run()
    if not backup:
        alerts.append({
            "level": "ambar", "area": "Backups",
            "text": "Nunca se ha completado una copia de seguridad.",
        })
    else:
        if backup.get("status") == "error":
            alerts.append({
                "level": "rojo", "area": "Backups",
                "text": f"La última copia FALLÓ: {backup.get('error') or ''}",
            })
        else:
            try:
                age = datetime.now() - datetime.fromisoformat(
                    str(backup["created_at"])[:19]
                )
                if age > timedelta(hours=48):
                    alerts.append({
                        "level": "ambar", "area": "Backups",
                        "text": f"La última copia buena tiene {age.days} día(s).",
                    })
            except ValueError:
                pass
    for business in past_due:
        alerts.append({
            "level": "ambar", "area": "Cobro",
            "text": (f"Suscripción impagada: {business['name']} "
                     f"({business.get('owner_email') or 'sin email'})."),
        })
    return alerts


def admin_overview() -> dict:
    """Cifras globales del negocio Noesis (solo para el fundador). NO expone datos
    operativos de cada autónomo, solo metadatos de cuenta y agregados."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT b.id, b.name, b.sector, b.owner_email, b.created_at, "
            "b.whatsapp_status, b.whatsapp_phone, b.plan, b.subscription_status, "
            "b.trial_ends_at, b.team_size, b.province, b.primary_goal, "
            "b.gestoria_cadence, "
            "(SELECT COUNT(*) FROM invoices i WHERE i.business_id=b.id) AS n_facturas, "
            "(SELECT COUNT(*) FROM clients c WHERE c.business_id=b.id) AS n_clientes, "
            "(SELECT COUNT(*) FROM jobs j WHERE j.business_id=b.id) AS n_trabajos, "
            "(SELECT COUNT(*) FROM workers w WHERE w.business_id=b.id) AS n_equipo, "
            "(SELECT COALESCE(SUM(p.amount),0) FROM invoice_payments p "
            "  WHERE p.business_id=b.id) AS cobrado, "
            "(SELECT MAX(CAST(pe.created_at AS TEXT)) FROM product_events pe "
            "  WHERE pe.business_id=b.id) AS last_event, "
            "(SELECT MAX(CAST(i.created_at AS TEXT)) FROM invoices i "
            "  WHERE i.business_id=b.id) AS last_invoice, "
            "(SELECT MAX(CAST(j.created_at AS TEXT)) FROM jobs j "
            "  WHERE j.business_id=b.id) AS last_job, "
            "(SELECT COALESCE(SUM(total),0) FROM invoices i WHERE i.business_id=b.id "
            "  AND i.status IN ('enviada','parcial','cobrada')) AS facturado "
            "FROM businesses b ORDER BY b.created_at DESC").fetchall()
        checkouts = conn.execute(
            "SELECT COUNT(DISTINCT business_id) AS n FROM product_events "
            "WHERE event_name = 'checkout_started'").fetchone()
    checkouts_iniciados = int(dict(checkouts)["n"] or 0)
    biz = [dict(r) for r in rows]
    usage = ai_usage_summary()
    today = date.today()
    for business in biz:
        activation = activation_snapshot(business["id"])
        business["activation_progress"] = activation["progress"]
        business["activated"] = activation["activated"]
        business["outcome_reached"] = activation["outcome_reached"]
        last = max(
            (v for v in (business.pop("last_event"), business.pop("last_invoice"),
                         business.pop("last_job")) if v),
            default=None,
        )
        business["last_activity"] = str(last)[:10] if last else None
        if last:
            try:
                business["days_inactive"] = (
                    today - date.fromisoformat(str(last)[:10])
                ).days
            except ValueError:
                business["days_inactive"] = None
        else:
            business["days_inactive"] = None
        business["ai"] = usage["per_business"].get(
            business["id"],
            {"calls": 0, "input": 0, "output": 0, "extractions": 0},
        )
    from .adapters.billing import PLAN_PRICES  # fuente única del catálogo de planes
    PRICES = {"trial": 0, **PLAN_PRICES}
    activos = [b for b in biz if b["subscription_status"] == "active"]
    mrr = sum(PRICES.get(b["plan"], 0) for b in activos)
    activated = [b for b in biz if b["activated"]]
    wa_conectados = len([b for b in biz if b["whatsapp_status"] == "conectado"])
    perfiles = len([b for b in biz if b.get("team_size") and b.get("primary_goal")])

    # Datos ya masticados para los gráficos del panel (solo primitivas JSON).
    month_start = today.replace(day=1)
    months: list[str] = []
    point = month_start
    for _ in range(12):
        months.append(point.isoformat()[:7])
        point = (point - timedelta(days=1)).replace(day=1)
    months.reverse()
    altas_by_month: dict[str, int] = {}
    for b in biz:
        key = str(b["created_at"])[:7]
        altas_by_month[key] = altas_by_month.get(key, 0) + 1
    planes: dict[str, int] = {}
    for b in biz:
        planes[b["plan"] or "trial"] = planes.get(b["plan"] or "trial", 0) + 1
    top = sorted(biz, key=lambda b: -float(b["facturado"] or 0))[:8]
    ia_top = sorted(
        biz, key=lambda b: -(b["ai"]["input"] + b["ai"]["output"])
    )[:8]
    charts = {
        "meses": months,
        "altas": [altas_by_month.get(m, 0) for m in months],
        "planes": planes,
        "cuentas": [b["name"] for b in top],
        "facturado": [round(float(b["facturado"] or 0), 2) for b in top],
        "cobrado": [round(float(b["cobrado"] or 0), 2) for b in top],
        "ia_cuentas": [b["name"] for b in ia_top],
        "ia_tokens": [b["ai"]["input"] + b["ai"]["output"] for b in ia_top],
        "funnel_labels": ["Altas", "Perfil completo", "WhatsApp", "Activadas",
                          "Checkout", "De pago"],
        "funnel": [len(biz), perfiles, wa_conectados, len(activated),
                   checkouts_iniciados, len(activos)],
    }
    # Departamentos: cada área "informa" a dirección con una frase y sus cifras.
    ai_total = usage["total"]
    ai_cost_eur = round(
        (ai_total["input"] * 3 + ai_total["output"] * 15) / 1_000_000 * 0.92
        + ai_total["extractions"] * 0.014,
        2,
    )
    margen_pct = round((mrr - ai_cost_eur) / mrr * 100) if mrr else None
    altas_mes = altas_by_month.get(today.strftime("%Y-%m"), 0)
    en_riesgo = len([
        b for b in biz if b["activated"] and (b["days_inactive"] or 0) >= 14
    ])
    vq = verifactu_queue_counts()
    backup = latest_backup_run()
    alerts = admin_alerts()
    backup_text = {
        "ok": "última copia verificada OK",
        "error": "la última copia FALLÓ",
    }.get((backup or {}).get("status"), "sin copias todavía")
    finanzas = {
        "mrr": mrr,
        "run_rate": mrr * 12,
        "ai_cost_eur": ai_cost_eur,
        "margen_pct": margen_pct,
    }
    dept_reports = {
        "finanzas": (
            f"MRR de {mrr} € ({mrr * 12} €/año). La IA del mes cuesta "
            f"~{ai_cost_eur} €: margen bruto ~{margen_pct}%."
            if mrr else
            f"Aún sin suscripciones de pago. La IA del mes cuesta "
            f"~{ai_cost_eur} € ({ai_total['calls']} llamadas al agente)."
        ),
        "crecimiento": (
            f"{altas_mes} alta(s) este mes. {len(activated)} de {len(biz)} "
            f"cuentas activadas ({round(len(activated) / len(biz) * 100) if biz else 0}%) "
            f"y {en_riesgo} en riesgo de fuga (14+ días sin uso)."
        ),
        "operaciones": (
            f"{len(alerts)} alarma(s) activa(s). Veri*Factu: "
            f"{vq['pendiente']} pendiente(s), {vq['rechazado']} rechazada(s). "
            f"Copias: {backup_text}."
        ),
        "marketing": (
            f"Embudo: {len(biz)} alta(s) → {perfiles} con perfil completo → "
            f"{wa_conectados} con WhatsApp → {len(activated)} activada(s) → "
            f"{checkouts_iniciados} checkout(s) → {len(activos)} de pago "
            f"(conversión alta→pago del "
            f"{round(len(activos) / len(biz) * 100) if biz else 0}%)."
        ),
        "clientes": (
            f"{wa_conectados} "
            f"de {len(biz)} cuentas con WhatsApp conectado; "
            f"{len([b for b in biz if b['outcome_reached']])} ya han cobrado "
            "su primera factura (ciclo completo)."
        ),
    }
    return {
        "charts": charts,
        "finanzas": finanzas,
        "dept_reports": dept_reports,
        "total": len(biz), "activos": len(activos),
        "en_prueba": len([b for b in biz if b["subscription_status"] == "trial"]),
        "whatsapp_conectados": wa_conectados,
        "perfiles_completos": perfiles,
        "activados": len(activated),
        "resultados": len([b for b in biz if b["outcome_reached"]]),
        "tasa_activacion": round(len(activated) / len(biz) * 100) if biz else 0,
        "en_riesgo": en_riesgo,
        "mrr": mrr, "businesses": biz, "backup": backup,
        "verifactu_queue": vq,
        "ai_usage": usage,
        "alerts": alerts,
    }


# ----------------------------------------------------------- RGPD (export/borrado) ---
def export_business_data(business_id) -> dict:
    """Vuelca TODOS los datos de un negocio (derecho de portabilidad RGPD)."""
    return {
        "business": get_business(business_id),
        "clients": list_clients(business_id),
        "jobs": [dict(r) for r in _rows(
            "SELECT * FROM jobs WHERE business_id=?", business_id)],
        "workers": [dict(r) for r in _rows(
            "SELECT id, business_id, name, phone, phone_norm, color, access_code, "
            "active, created_at FROM workers WHERE business_id=? ORDER BY id",
            business_id)],
        "worker_clockins": [dict(r) for r in _rows(
            "SELECT * FROM worker_clockins WHERE business_id=? ORDER BY at, id",
            business_id)],
        "worker_clockin_corrections": [dict(r) for r in _rows(
            "SELECT * FROM worker_clockin_corrections "
            "WHERE business_id=? ORDER BY id",
            business_id)],
        "invoices": list_invoices(business_id),
        "invoice_payments": [dict(r) for r in _rows(
            "SELECT * FROM invoice_payments WHERE business_id=? "
            "ORDER BY paid_at, id",
            business_id)],
        "invoice_records": list_invoice_records(business_id),
        "invoice_events": list_invoice_events(business_id),
        "verifactu_outbox": list_verifactu_outbox(business_id, limit=500),
        "quotes": list_quotes(business_id),
        "expenses": list_expenses(business_id),
        "suppliers": list_suppliers(business_id),
        "received_invoices": list_received_invoices(business_id),
        "products": list_products(business_id, include_inactive=True),
        "leads": list_leads(business_id),
        "gestoria_requests": list_gestoria_requests(business_id),
        "product_events": [dict(r) for r in _rows(
            "SELECT * FROM product_events WHERE business_id=? ORDER BY id",
            business_id)],
        "copilot_recommendations": [dict(r) for r in _rows(
            "SELECT * FROM copilot_recommendations WHERE business_id=? ORDER BY id",
            business_id)],
        "documents": _documents_repo().export_for_business(business_id),
        "exported_at": _now(),
    }


def _documents_repo():
    """Acceso perezoso al repositorio de documentos (módulo aislado)."""
    from .documents import repo
    return repo


def export_client_data(client_id, business_id) -> dict | None:
    """Vuelca los datos de un cliente final concreto (RGPD por persona)."""
    client = get_client(client_id, business_id)
    if not client:
        return None
    return {
        "client": client,
        "jobs": [dict(r) for r in _rows(
            "SELECT * FROM jobs WHERE business_id=? AND client_id=?",
            business_id, client_id)],
        "invoices": [dict(r) for r in _rows(
            "SELECT * FROM invoices WHERE business_id=? AND client_id=?",
            business_id, client_id)],
        "invoice_payments": [dict(r) for r in _rows(
            "SELECT p.* FROM invoice_payments p JOIN invoices i "
            "ON i.business_id=p.business_id AND i.id=p.invoice_id "
            "WHERE p.business_id=? AND i.client_id=? ORDER BY p.paid_at, p.id",
            business_id, client_id)],
        "quotes": [dict(r) for r in _rows(
            "SELECT * FROM quotes WHERE business_id=? AND client_id=?",
            business_id, client_id)],
        "exported_at": _now(),
    }


def _rows(sql: str, *params):
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def delete_client_cascade(client_id, business_id) -> bool:
    """Borra lo prescindible y conserva facturas emitidas por obligación fiscal."""
    client = get_client(client_id, business_id)
    if not client:
        return False
    # Borra antes los ficheros físicos de los documentos del cliente (derecho al olvido).
    from .documents import repo as _docrepo, storage as _docstore
    for stored in _docrepo.stored_names_for_client(business_id, client_id):
        _docstore.delete(business_id, stored)
    _docrepo.purge_for_client(business_id, client_id)
    with get_conn() as conn:
        issued = conn.execute(
            "SELECT COUNT(*) AS total FROM invoices WHERE business_id=? AND client_id=? "
            "AND status IN ('enviada','parcial','cobrada')",
            (business_id, client_id),
        ).fetchone()["total"]
        conn.execute("DELETE FROM portal_tokens WHERE business_id=? AND client_id=?",
                     (business_id, client_id))
        conn.execute("DELETE FROM quotes WHERE business_id=? AND client_id=?",
                     (business_id, client_id))
        conn.execute(
            "DELETE FROM invoices WHERE business_id=? AND client_id=? "
            "AND status='borrador'",
            (business_id, client_id),
        )
        conn.execute(
            "DELETE FROM jobs WHERE business_id=? AND client_id=? "
            "AND NOT EXISTS (SELECT 1 FROM worker_clockins wc "
            "WHERE wc.business_id=jobs.business_id AND wc.job_id=jobs.id)",
            (business_id, client_id),
        )
        conn.execute(
            "UPDATE jobs SET client_id=NULL WHERE business_id=? AND client_id=?",
            (business_id, client_id),
        )
        if issued:
            conn.execute(
                "UPDATE clients SET name='Cliente conservado por obligación fiscal', "
                "phone=NULL, address=NULL, zone=NULL, nif=NULL, email=NULL "
                "WHERE id=? AND business_id=?",
                (client_id, business_id),
            )
        else:
            conn.execute(
                "DELETE FROM clients WHERE id=? AND business_id=?",
                (client_id, business_id),
            )
    return True


def delete_business_cascade(business_id) -> bool:
    """Borra una cuenta entera y todos sus datos (baja RGPD del autónomo)."""
    with get_conn() as conn:
        issued = conn.execute(
            "SELECT COUNT(*) AS total FROM invoices WHERE business_id=? "
            "AND status IN ('enviada','parcial','cobrada')",
            (business_id,),
        ).fetchone()["total"]
        if issued:
            raise ValueError(
                "La cuenta tiene facturas emitidas que deben conservarse. "
                "Solicita una baja con conservación fiscal."
            )
        clockins = conn.execute(
            "SELECT COUNT(*) AS total FROM worker_clockins WHERE business_id=?",
            (business_id,),
        ).fetchone()["total"]
        if clockins:
            raise ValueError(
                "La cuenta tiene registros de jornada que deben conservarse "
                "durante cuatro años. Solicita una baja con conservación legal."
            )
        # Primero confirma todas las eliminaciones referenciales en la base de datos.
        for table in (
            "whatsapp_pending_actions", "whatsapp_links", "whatsapp_outbox",
            "verifactu_outbox", "document_sequences",
            "worker_tokens", "worker_clockin_corrections", "worker_clockins",
            "invoice_events", "invoice_records", "portal_tokens",
            "product_events", "copilot_recommendations", "gestoria_requests",
            "documents", "received_invoices", "suppliers", "products",
            "leads", "quotes",
            "invoice_payments", "invoices", "jobs", "workers", "clients", "expenses"
        ):
            conn.execute(f"DELETE FROM {table} WHERE business_id=?", (business_id,))
        conn.execute("DELETE FROM password_resets WHERE user_id IN "
                     "(SELECT id FROM users WHERE business_id=?)", (business_id,))
        conn.execute(
            "DELETE FROM scheduled_job_runs WHERE run_key LIKE ?",
            (f"gestoria:{business_id}:%",),
        )
        conn.execute("DELETE FROM users WHERE business_id=?", (business_id,))
        conn.execute("DELETE FROM businesses WHERE id=?", (business_id,))
    # El borrado físico va después del commit: un fallo de FK nunca deja
    # metadatos vivos apuntando a archivos ya eliminados.
    from .documents import storage as _docstore
    _docstore.delete_business_dir(business_id)
    return True
