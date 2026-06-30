"""Acceso único a SQLite/Postgres con aislamiento multiempresa.

Cada autónomo que se da de alta es un "business". Todos sus datos (clientes,
agenda, facturas, gastos) van marcados con su business_id, de modo que los datos
de un cliente nunca se mezclan con los de otro.

Postgres se activa con ``DATABASE_URL``. SQLite se mantiene como fallback local.
El esquema no se crea aquí: lo gestionan las migraciones versionadas.
"""

from __future__ import annotations

import logging
import math
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import config

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
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} debe ser un número.") from exc
    if not math.isfinite(number) or number <= 0 or number > 10_000_000:
        raise ValueError(f"{label} debe ser mayor que 0 y tener un importe válido.")
    return round(number, 2)


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
    sql = "SELECT * FROM jobs WHERE id=? AND business_id=?"
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
        conn.execute("DELETE FROM jobs WHERE id=? AND business_id=?",
                     (job_id, business_id))


def jobs_for_date(day: str, business_id) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT j.*, c.name AS client_name, c.zone AS client_zone "
            "FROM jobs j LEFT JOIN clients c ON c.id = j.client_id "
            "AND c.business_id = j.business_id "
            "WHERE j.business_id=? AND CAST(j.scheduled_for AS TEXT) LIKE ? "
            "ORDER BY j.scheduled_for",
            (business_id, f"{day}%"),
        ).fetchall()
        return [dict(r) for r in rows]


def jobs_between(start: str, end: str, business_id) -> list[dict]:
    """Trabajos entre dos fechas ISO (para el calendario semanal)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT j.*, c.name AS client_name FROM jobs j "
            "LEFT JOIN clients c ON c.id = j.client_id "
            "AND c.business_id = j.business_id "
            "WHERE j.business_id=? AND j.scheduled_for >= ? AND j.scheduled_for <= ? "
            "ORDER BY j.scheduled_for",
            (business_id, start, end + "T23:59"),
        ).fetchall()
        return [dict(r) for r in rows]


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
    vat_amount = round(base * vat_rate / 100, 2)
    irpf_amount = round(base * (irpf_rate or 0) / 100, 2)
    total = round(base + vat_amount - irpf_amount, 2)
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


def get_invoice(invoice_id, business_id) -> dict | None:
    where = "i.id=? AND i.business_id=?"
    params = [invoice_id, business_id]
    with get_conn() as conn:
        row = conn.execute(
            "SELECT i.*, c.name AS client_name FROM invoices i "
            "LEFT JOIN clients c ON c.id = i.client_id "
            "AND c.business_id=i.business_id WHERE " + where,
            params,
        ).fetchone()
        return dict(row) if row else None


def list_invoices(business_id, status=None) -> list[dict]:
    q = ("SELECT i.*, COALESCE(i.recipient_name, c.name) AS client_name FROM invoices i "
         "LEFT JOIN clients c ON c.id = i.client_id AND c.business_id=i.business_id "
         "WHERE i.business_id=?")
    params: list = [business_id]
    if status:
        q += " AND i.status=?"
        params.append(status)
    q += " ORDER BY i.created_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


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


def issue_invoice(invoice_id: int, business_id: int, payment_term_days: int = 15) -> dict:
    """Emite una factura una sola vez, numera y congela sus datos fiscales."""
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        inv = conn.execute(
            "SELECT * FROM invoices WHERE id=? AND business_id=?",
            (invoice_id, business_id),
        ).fetchone()
        if not inv:
            raise ValueError("No existe esa factura.")
        if inv["status"] != "borrador" or inv["number"]:
            existing = get_invoice(invoice_id, business_id)
            if existing and existing["status"] in {"enviada", "cobrada"}:
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
    return get_invoice(invoice_id, business_id)


def mark_invoice_sent(invoice_id, number, due_date=None, *, business_id: int) -> dict | None:
    """Marca una factura como enviada. Filtra por business_id (aislamiento): si la
    factura no es de ese negocio, no toca nada y devuelve None."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE invoices SET status='enviada', number=?, issued_at=?, due_date=? "
            "WHERE id=? AND business_id=? AND status='borrador' AND number IS NULL",
            (number, _now(), due_date, invoice_id, business_id),
        )
        ok = cur.rowcount > 0
    return get_invoice(invoice_id, business_id) if ok else None


def mark_invoice_paid(invoice_id, business_id) -> dict | None:
    """Marca una factura como cobrada. Filtra por business_id (aislamiento): si la
    factura no es de ese negocio, no toca nada y devuelve None."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE invoices SET status='cobrada', paid_at=? "
            "WHERE id=? AND business_id=? AND status='enviada'",
            (_now(), invoice_id, business_id))
        ok = cur.rowcount > 0
    return get_invoice(invoice_id, business_id) if ok else None


def delete_invoice(invoice_id, business_id) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM invoices WHERE id=? AND business_id=? AND status='borrador'",
            (invoice_id, business_id),
        )
        return cur.rowcount > 0


def pending_payments(business_id) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT i.*, c.name AS client_name FROM invoices i "
            "LEFT JOIN clients c ON c.id = i.client_id "
            "AND c.business_id=i.business_id "
            "WHERE i.business_id=? AND i.status='enviada' ORDER BY i.issued_at",
            (business_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("issued_at"):
            issued = datetime.fromisoformat(d["issued_at"]).date()
            d["days_outstanding"] = (date.today() - issued).days
        else:
            d["days_outstanding"] = None
        out.append(d)
    return out


# ----------------------------------------------------------------- Gastos ---
def add_expense(concept, amount, vat_rate=None, category=None, spent_on=None,
                *, business_id: int) -> dict:
    concept = (concept or "").strip()
    if not concept or len(concept) > 500:
        raise ValueError("El concepto es obligatorio y no puede superar 500 caracteres.")
    amount = _positive_money(amount, "El importe")
    if vat_rate not in (None, ""):
        vat_rate = _tax_rate(vat_rate, "El IVA", {0, 4, 10, 21})
    else:
        vat_rate = None
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO expenses (business_id, concept, amount, vat_rate, category, "
            "spent_on, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, concept, amount, vat_rate, category,
             spent_on, _now()),
        ).fetchone()
        new_id = row["id"]
    with get_conn() as conn:
        return dict(conn.execute(
            "SELECT * FROM expenses WHERE id=? AND business_id=?",
            (new_id, business_id),
        ).fetchone())


def delete_expense(expense_id, business_id) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM expenses WHERE id=? AND business_id=?",
                     (expense_id, business_id))


def list_expenses(business_id) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM expenses WHERE business_id=? ORDER BY created_at DESC",
            (business_id,)).fetchall()]


# --------------------------------------------------------------- Resúmenes ---
def month_billing(month: str | None = None, *, business_id: int) -> dict:
    month = month or date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("El mes debe tener formato YYYY-MM.")
    with get_conn() as conn:
        invoices = [
            dict(row) for row in conn.execute(
                "SELECT * FROM invoices WHERE business_id=? "
                "AND CAST(COALESCE(issued_at, created_at) AS TEXT) LIKE ? "
                "AND status IN ('enviada','cobrada')",
                (business_id, f"{month}%"),
            ).fetchall()
        ]
        collected_rows = conn.execute(
            "SELECT COALESCE(SUM(total),0) AS total FROM invoices WHERE business_id=? "
            "AND CAST(paid_at AS TEXT) LIKE ? AND status='cobrada'",
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
    pending = sum(
        item["total"] for item in invoices if item["status"] == "enviada"
    )
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
            "WHERE i.business_id=? AND i.status IN ('enviada','cobrada') "
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
            "   AND i.status IN ('enviada','cobrada')) AS facturado, "
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
    collected = round(sum(i["total"] for i in invoices if i["status"] == "cobrada"), 2)
    pending = round(sum(i["total"] for i in invoices if i["status"] == "enviada"), 2)
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
    vat_amount = round(base * vat_rate / 100, 2)
    irpf_amount = round(base * (irpf_rate or 0) / 100, 2)
    total = round(base + vat_amount - irpf_amount, 2)
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
        row = conn.execute("SELECT * FROM quotes WHERE id=? AND business_id=?",
                           (quote_id, business_id)).fetchone()
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
        q = conn.execute(
            "SELECT * FROM quotes WHERE id=? AND business_id=?",
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
        if i.get("status") in ("enviada", "cobrada")
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
        row = conn.execute(
            "SELECT * FROM password_resets WHERE token_hash=? AND used=FALSE",
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


def claim_webhook_event(source: str, event_id: str) -> bool:
    """Registra un evento una sola vez. False significa que ya fue procesado."""
    if not event_id:
        return False
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO webhook_events (source, event_id, created_at) "
                "VALUES (?, ?, ?)",
                (source, event_id, _now()),
            )
        return True
    except IntegrityError:
        return False


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
        row = conn.execute(
            "SELECT business_id FROM whatsapp_links "
            "WHERE code_hash=? AND expires_at>=?",
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
                     "initials": business_initials(biz.get("name"))},
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


# ----------------------------------------------------- Panel de administración ---
def admin_overview() -> dict:
    """Cifras globales del negocio Noesis (solo para el fundador). NO expone datos
    operativos de cada autónomo, solo metadatos de cuenta y agregados."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT b.id, b.name, b.sector, b.owner_email, b.created_at, "
            "b.whatsapp_status, b.plan, b.subscription_status, b.trial_ends_at, "
            "b.team_size, b.province, b.primary_goal, "
            "(SELECT COUNT(*) FROM invoices i WHERE i.business_id=b.id) AS n_facturas, "
            "(SELECT COUNT(*) FROM clients c WHERE c.business_id=b.id) AS n_clientes, "
            "(SELECT COALESCE(SUM(total),0) FROM invoices i WHERE i.business_id=b.id "
            "  AND i.status IN ('enviada','cobrada')) AS facturado "
            "FROM businesses b ORDER BY b.created_at DESC").fetchall()
    biz = [dict(r) for r in rows]
    for business in biz:
        activation = activation_snapshot(business["id"])
        business["activation_progress"] = activation["progress"]
        business["activated"] = activation["activated"]
        business["outcome_reached"] = activation["outcome_reached"]
    PRICES = {"trial": 0, "autonomo": 29, "pro": 39}
    activos = [b for b in biz if b["subscription_status"] == "active"]
    mrr = sum(PRICES.get(b["plan"], 0) for b in activos)
    activated = [b for b in biz if b["activated"]]
    return {
        "total": len(biz), "activos": len(activos),
        "en_prueba": len([b for b in biz if b["subscription_status"] == "trial"]),
        "whatsapp_conectados": len([b for b in biz if b["whatsapp_status"] == "conectado"]),
        "perfiles_completos": len([
            b for b in biz if b.get("team_size") and b.get("primary_goal")
        ]),
        "activados": len(activated),
        "resultados": len([b for b in biz if b["outcome_reached"]]),
        "tasa_activacion": round(len(activated) / len(biz) * 100) if biz else 0,
        "mrr": mrr, "businesses": biz,
    }


# ----------------------------------------------------------- RGPD (export/borrado) ---
def export_business_data(business_id) -> dict:
    """Vuelca TODOS los datos de un negocio (derecho de portabilidad RGPD)."""
    return {
        "business": get_business(business_id),
        "clients": list_clients(business_id),
        "jobs": [dict(r) for r in _rows(
            "SELECT * FROM jobs WHERE business_id=?", business_id)],
        "invoices": list_invoices(business_id),
        "quotes": list_quotes(business_id),
        "expenses": list_expenses(business_id),
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
            "AND status IN ('enviada','cobrada')",
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
        conn.execute("DELETE FROM jobs WHERE business_id=? AND client_id=?",
                     (business_id, client_id))
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
            "AND status IN ('enviada','cobrada')",
            (business_id,),
        ).fetchone()["total"]
        if issued:
            raise ValueError(
                "La cuenta tiene facturas emitidas que deben conservarse. "
                "Solicita una baja con conservación fiscal."
            )
        # Borra los ficheros físicos de los documentos antes que sus metadatos (RGPD).
        from .documents import storage as _docstore
        _docstore.delete_business_dir(business_id)
        for table in (
            "portal_tokens", "product_events", "copilot_recommendations",
            "documents", "quotes", "invoices", "jobs", "clients", "expenses"
        ):
            conn.execute(f"DELETE FROM {table} WHERE business_id=?", (business_id,))
        conn.execute("DELETE FROM password_resets WHERE user_id IN "
                     "(SELECT id FROM users WHERE business_id=?)", (business_id,))
        conn.execute("DELETE FROM users WHERE business_id=?", (business_id,))
        conn.execute("DELETE FROM businesses WHERE id=?", (business_id,))
    return True
