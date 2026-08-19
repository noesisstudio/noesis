"""Acceso único a SQLite/Postgres con aislamiento multiempresa.

Cada autónomo que se da de alta es un "business". Todos sus datos (clientes,
agenda, facturas, gastos) van marcados con su business_id, de modo que los datos
de un cliente nunca se mezclan con los de otro.

Postgres se activa con ``DATABASE_URL``. SQLite se mantiene como fallback local.
El esquema no se crea aquí: lo gestionan las migraciones versionadas.
"""

from __future__ import annotations

import json
import hashlib
import logging
import math
import re
import secrets
import sqlite3
import threading
import unicodedata
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
    from psycopg_pool import ConnectionPool
    from psycopg.rows import dict_row
except ImportError:  # SQLite local no necesita cargar el driver.
    psycopg = None
    ConnectionPool = None
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


_pool = None
_pool_url = ""
_pool_lock = threading.Lock()


def _postgres_pool():
    """Pool perezoso y acotado; se recrea si un test cambia DATABASE_URL."""
    global _pool, _pool_url
    if ConnectionPool is None:
        raise RuntimeError("DATABASE_URL está configurada pero falta psycopg_pool.")
    if _pool is not None and _pool_url == config.DATABASE_URL:
        return _pool
    with _pool_lock:
        if _pool is not None and _pool_url != config.DATABASE_URL:
            _pool.close()
            _pool = None
        if _pool is None:
            candidate = ConnectionPool(
                conninfo=config.DATABASE_URL,
                kwargs={"row_factory": dict_row},
                min_size=config.DB_POOL_MIN_SIZE,
                max_size=config.DB_POOL_MAX_SIZE,
                timeout=config.DB_POOL_TIMEOUT,
                open=False,
                name="noesis",
            )
            candidate.open(wait=True)
            _pool = candidate
            _pool_url = config.DATABASE_URL
    return _pool


def close_pool() -> None:
    """Cierra conexiones persistentes durante el apagado ordenado."""
    global _pool, _pool_url
    with _pool_lock:
        if _pool is not None:
            _pool.close()
        _pool = None
        _pool_url = ""


@contextmanager
def get_conn():
    """Abre la BD configurada, confirma al salir y siempre cierra."""
    if config.DATABASE_URL:
        if psycopg is None:
            raise RuntimeError(
                "DATABASE_URL está configurada pero falta psycopg."
            )
        with _postgres_pool().connection() as raw:
            conn = Connection(raw, "postgres")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return
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


# ------------------------------------------------------ Seguridad de acceso ---
def auth_attempt_count(key_hash: str, since: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM auth_attempts "
            "WHERE key_hash=? AND attempted_at>=?",
            (key_hash, since),
        ).fetchone()
    return int(row["total"] or 0)


def record_auth_attempt(key_hash: str, attempted_at: str, *, keep_since: str) -> None:
    with get_conn() as conn:
        # Limpieza global: un atacante que rote IP/cuenta no puede hacer crecer la
        # tabla indefinidamente con claves distintas.
        conn.execute(
            "DELETE FROM auth_attempts WHERE attempted_at<?",
            (keep_since,),
        )
        conn.execute(
            "INSERT INTO auth_attempts (key_hash, attempted_at) VALUES (?, ?)",
            (key_hash, attempted_at),
        )


def clear_auth_attempts(key_hash: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM auth_attempts WHERE key_hash=?", (key_hash,))


def auth_attempt_summary(hours: int = 24) -> dict:
    """Volumen agregado de intentos fallidos; no devuelve identidades ni IP."""
    hours = max(1, min(int(hours), 168))
    since = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS attempts, COUNT(DISTINCT key_hash) AS keys "
            "FROM auth_attempts WHERE attempted_at>=?", (since,)
        ).fetchone()
    return {
        "hours": hours,
        "attempts": int(row["attempts"] or 0),
        "pseudonymous_keys": int(row["keys"] or 0),
    }


_SECURITY_SEVERITIES = {"info", "warning", "critical"}
_SECURITY_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,63}$")


def _security_metadata(metadata: dict | None) -> dict:
    """Reduce metadatos a escalares acotados; nunca acepta cuerpos ni secretos."""
    clean: dict[str, str | int | float | bool | None] = {}
    forbidden = (
        "email", "phone", "telefono", "ip", "token", "secret", "password",
        "credential", "filename", "document", "message", "body", "content",
    )
    for raw_key, value in list((metadata or {}).items())[:20]:
        key = str(raw_key).strip().lower()
        if (
            not _SECURITY_NAME_RE.fullmatch(key)
            or any(part in key for part in forbidden)
        ):
            continue
        if value is None or isinstance(value, (bool, int, float)):
            clean[key] = value
        elif isinstance(value, str):
            clean[key] = value.strip()[:200]
    return clean


def _security_event_payload(event: dict) -> str:
    return json.dumps(
        {
            "event_type": event["event_type"],
            "severity": event["severity"],
            "area": event["area"],
            "actor_user_id": event.get("actor_user_id"),
            "subject_business_id": event.get("subject_business_id"),
            "request_id": event.get("request_id"),
            "metadata": event.get("metadata") or {},
            "created_at": event["created_at"],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def record_security_event(
    event_type: str,
    *,
    severity: str = "info",
    area: str = "security",
    actor_user_id: int | None = None,
    subject_business_id: int | None = None,
    request_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Anade un evento encadenado a la bitacora global, sin datos de cliente."""
    event_type = str(event_type or "").strip().lower()
    severity = str(severity or "").strip().lower()
    area = str(area or "").strip().lower()
    if not _SECURITY_NAME_RE.fullmatch(event_type):
        raise ValueError("Tipo de evento de seguridad no valido.")
    if severity not in _SECURITY_SEVERITIES:
        raise ValueError("Severidad de seguridad no valida.")
    if not _SECURITY_NAME_RE.fullmatch(area):
        raise ValueError("Area de seguridad no valida.")
    created_at = _now()
    event = {
        "event_type": event_type,
        "severity": severity,
        "area": area,
        "actor_user_id": int(actor_user_id) if actor_user_id else None,
        "subject_business_id": (
            int(subject_business_id) if subject_business_id else None
        ),
        "request_id": str(request_id or "").strip()[:64] or None,
        "metadata": _security_metadata(metadata),
        "created_at": created_at,
    }
    with get_conn() as conn:
        # Serializa el extremo de la cadena. SQLite toma un bloqueo de escritura;
        # PostgreSQL usa un advisory lock solo durante esta transaccion.
        if conn.dialect == "sqlite":
            conn.execute("BEGIN IMMEDIATE")
        else:
            conn.execute("SELECT pg_advisory_xact_lock(?)", (730_351_001,))
        previous = conn.execute(
            "SELECT event_hash FROM security_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else None
        event_hash = hashlib.sha256(
            ((previous_hash or "") + _security_event_payload(event)).encode("utf-8")
        ).hexdigest()
        row = conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, area, actor_user_id, subject_business_id, "
            "request_id, metadata_json, previous_hash, event_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                event_type,
                severity,
                area,
                event["actor_user_id"],
                event["subject_business_id"],
                event["request_id"],
                json.dumps(
                    event["metadata"], ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"),
                ),
                previous_hash,
                event_hash,
                created_at,
            ),
        ).fetchone()
    return get_security_event(row["id"])


def get_security_event(event_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM security_events WHERE id=?", (event_id,)
        ).fetchone()
    if not row:
        return None
    event = dict(row)
    try:
        event["metadata"] = json.loads(event.pop("metadata_json") or "{}")
    except ValueError:
        event["metadata"] = {}
    return event


def list_security_events(limit: int = 50) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM security_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    events = []
    for raw in rows:
        event = dict(raw)
        try:
            event["metadata"] = json.loads(event.pop("metadata_json") or "{}")
        except ValueError:
            event["metadata"] = {}
        events.append(event)
    return events


def security_event_integrity() -> dict:
    """Verifica continuidad y huellas de toda la bitacora append-only."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM security_events ORDER BY id"
        ).fetchall()
    previous_hash = None
    for raw in rows:
        row = dict(raw)
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
        except ValueError:
            return {"ok": False, "events": len(rows), "broken_at": row["id"]}
        event = {
            "event_type": row["event_type"],
            "severity": row["severity"],
            "area": row["area"],
            "actor_user_id": row.get("actor_user_id"),
            "subject_business_id": row.get("subject_business_id"),
            "request_id": row.get("request_id"),
            "metadata": metadata,
            "created_at": str(row["created_at"]),
        }
        expected = hashlib.sha256(
            ((previous_hash or "") + _security_event_payload(event)).encode("utf-8")
        ).hexdigest()
        if row.get("previous_hash") != previous_hash or not secrets.compare_digest(
            expected, row["event_hash"]
        ):
            return {"ok": False, "events": len(rows), "broken_at": row["id"]}
        previous_hash = row["event_hash"]
    return {"ok": True, "events": len(rows), "broken_at": None}


def security_event_counts() -> dict:
    day_ago = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
    week_ago = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    with get_conn() as conn:
        day = conn.execute(
            "SELECT severity, COUNT(*) AS total FROM security_events "
            "WHERE created_at>=? GROUP BY severity", (day_ago,)
        ).fetchall()
        week = conn.execute(
            "SELECT severity, COUNT(*) AS total FROM security_events "
            "WHERE created_at>=? GROUP BY severity", (week_ago,)
        ).fetchall()
    return {
        "24h": {row["severity"]: int(row["total"]) for row in day},
        "7d": {row["severity"]: int(row["total"]) for row in week},
    }


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
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO businesses (name, owner_email, sector, created_at) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            (name, owner_email, sector, now),
        ).fetchone()
        new_id = row["id"]
        # Las cuentas nuevas deciden antes de enviar contenido a una IA externa.
        # Las instalaciones ya existentes conservan su comportamiento previo al
        # no tener una preferencia explícita tras la migración.
        conn.execute(
            "INSERT INTO integration_settings "
            "(business_id, integration_key, mode, updated_at) "
            "VALUES (?, 'ai_external', 'disabled', ?)",
            (new_id, now),
        )
    return get_business(new_id)


def get_business(business_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
        return dict(row) if row else None


def get_business_by_calendar_token(token: str) -> dict | None:
    """Resuelve un feed privado sin aceptar tokens cortos o manipulados."""
    token = (token or "").strip()
    if len(token) < 32 or len(token) > 160:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM businesses WHERE calendar_token=?", (token,)
        ).fetchone()
    return dict(row) if row else None


def get_or_create_calendar_token(business_id: int) -> str:
    business = get_business(business_id)
    if not business:
        raise ValueError("Negocio no encontrado.")
    if business.get("calendar_token"):
        return str(business["calendar_token"])
    return rotate_calendar_token(business_id)


def rotate_calendar_token(business_id: int) -> str:
    """Revoca el enlace anterior y entrega uno impredecible para este negocio."""
    if not get_business(business_id):
        raise ValueError("Negocio no encontrado.")
    for _attempt in range(4):
        token = secrets.token_urlsafe(32)
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE businesses SET calendar_token=? WHERE id=?",
                    (token, business_id),
                )
            return token
        except IntegrityError:
            continue
    raise RuntimeError("No se pudo crear un enlace de calendario seguro.")


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


def central_whatsapp_identity(phone: str) -> dict:
    """Resuelve un teléfono central sin elegir nunca entre identidades ambiguas."""
    target = normalize_phone(phone)
    if len(target) != 9:
        return {"business": None, "worker": None, "ambiguous": False}
    with get_conn() as conn:
        businesses = conn.execute(
            "SELECT * FROM businesses WHERE whatsapp_phone_norm=?",
            (target,),
        ).fetchall()
        workers = conn.execute(
            "SELECT *, CASE WHEN pin_hash IS NULL THEN FALSE ELSE TRUE END AS has_pin "
            "FROM workers WHERE phone_norm=? AND active=TRUE ORDER BY id",
            (target,),
        ).fetchall()
    total = len(businesses) + len(workers)
    return {
        "business": dict(businesses[0]) if total == 1 and businesses else None,
        "worker": dict(workers[0]) if total == 1 and workers else None,
        "ambiguous": total > 1,
    }


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
            if status == "conectado" and conn.execute(
                "SELECT 1 AS found FROM workers WHERE phone_norm=? AND active=TRUE",
                (norm,),
            ).fetchone():
                raise ValueError(
                    "Ese teléfono ya identifica a un trabajador en Noesis. "
                    "Cada número central debe tener una sola identidad."
                )
            conn.execute("UPDATE businesses SET whatsapp_status=?, whatsapp_phone=? "
                         ", whatsapp_phone_norm=? WHERE id=?",
                         (status, phone, norm or None, business_id))
        else:
            conn.execute("UPDATE businesses SET whatsapp_status=? WHERE id=?",
                         (status, business_id))
    return get_business(business_id)


def disconnect_whatsapp(business_id: int) -> dict | None:
    """Revoca el canal y deja trazados como cancelados los envíos que no salieron."""
    now = _now()
    reason = "Cancelado al desconectar WhatsApp por el usuario."
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET whatsapp_status='no_conectado', "
            "whatsapp_phone=NULL, whatsapp_phone_norm=NULL WHERE id=?",
            (business_id,),
        )
        conn.execute(
            "UPDATE whatsapp_outbox SET status='failed', last_error=?, "
            "locked_at=NULL, updated_at=? WHERE business_id=? "
            "AND status IN ('queued','retrying','processing')",
            (reason, now, business_id),
        )
        conn.execute(
            "DELETE FROM whatsapp_pending_actions WHERE business_id=?",
            (business_id,),
        )
    return get_business(business_id)


def start_onboarding(
    business_id: int, *, plan: str = "autonomo", billing: str = "monthly",
    intent: str = "trial",
) -> dict:
    """Activa el recorrido recuperable solo para altas que deben completarlo."""
    if plan not in {"autonomo", "pro", "premium"}:
        raise ValueError("El plan del alta no es válido.")
    if billing not in {"monthly", "annual"}:
        raise ValueError("La periodicidad del alta no es válida.")
    if intent not in {"trial", "subscribe"}:
        raise ValueError("La intención del alta no es válida.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET onboarding_started=TRUE, onboarding_done=FALSE, "
            "onboarding_stage=2, onboarding_plan=?, onboarding_billing=?, "
            "onboarding_intent=? WHERE id=?",
            (plan, billing, intent, business_id),
        )
    return get_business(business_id)


def _onboarding_readiness(business: dict) -> tuple[bool, bool]:
    profile_done = bool(
        business.get("onboarding_profile_completed")
        or (
            business.get("sector") and business.get("team_size")
            and business.get("primary_goal")
        )
    )
    preferences_done = bool(
        business.get("onboarding_preferences_completed")
        or (business.get("nif") and business.get("address"))
    )
    return profile_done, preferences_done


def onboarding_destination(business_id: int) -> str | None:
    """Ruta exacta donde debe continuar un alta iniciada e incompleta."""
    business = get_business(business_id)
    if not business or not business.get("onboarding_started"):
        return None
    if business.get("onboarding_done"):
        return f"/b/{business_id}/resumen"
    profile_done, preferences_done = _onboarding_readiness(business)
    if not profile_done:
        return f"/onboarding/setup/{business_id}"
    if not preferences_done:
        return f"/onboarding/preferences/{business_id}"
    return f"/onboarding/whatsapp/{business_id}"


def finish_onboarding(business_id: int, whatsapp_choice: str | None = None) -> dict:
    """Cierra el alta solo tras guardar perfil y operativa obligatorios."""
    choice = (whatsapp_choice or "").strip().lower()
    if choice and choice not in {"connected", "later"}:
        raise ValueError("La decisión de WhatsApp no es válida.")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        business = conn.execute(
            "SELECT * FROM businesses WHERE id=?" + lock, (business_id,)
        ).fetchone()
        if not business:
            raise ValueError("Negocio no encontrado.")
        profile_done, preferences_done = _onboarding_readiness(dict(business))
        if not profile_done or not preferences_done:
            raise ValueError(
                "Completa el negocio y la operativa antes de terminar el alta."
            )
        actual_choice = (
            "connected" if business.get("whatsapp_status") == "conectado"
            else choice
        )
        if actual_choice not in {"connected", "later"}:
            raise ValueError("Confirma WhatsApp o elige conectarlo más adelante.")
        conn.execute(
            "UPDATE businesses SET onboarding_started=TRUE, onboarding_done=TRUE, "
            "onboarding_profile_completed=TRUE, "
            "onboarding_preferences_completed=TRUE, onboarding_stage=5, "
            "whatsapp_onboarding_choice=? WHERE id=?",
            (actual_choice, business_id),
        )
    return get_business(business_id)


def _clean_payment_details(iban=None, bizum=None, note=None) -> tuple[str, str, str]:
    clean_iban = (iban or "").replace(" ", "").upper().strip()
    if clean_iban and not re.fullmatch(r"[A-Z]{2}[0-9A-Z]{13,32}", clean_iban):
        raise ValueError("El IBAN no tiene un formato válido.")
    clean_bizum = re.sub(r"[^\d+]", "", (bizum or "").strip())
    if clean_bizum and not re.fullmatch(r"\+?\d{9,15}", clean_bizum):
        raise ValueError("El número de Bizum debe ser un teléfono válido.")
    return clean_iban, clean_bizum, (note or "").strip()[:300]


def update_payment_details(
    business_id, *, iban=None, bizum=None, note=None,
    default_payment_term_days=None,
) -> dict:
    """Guarda cómo quiere cobrar el negocio: IBAN, Bizum y una nota libre.

    Se muestra en el PDF de la factura y en el portal del cliente para que el
    cliente sepa pagar sin tener que preguntar. Validación ligera y tolerante:
    lo que no cuadra se rechaza con un mensaje claro, no se corrompe.
    """
    clean_iban, clean_bizum, clean_note = _clean_payment_details(
        iban, bizum, note
    )
    fields = ["payment_iban=?", "payment_bizum=?", "payment_note=?"]
    params: list = [clean_iban or None, clean_bizum or None, clean_note or None]
    if default_payment_term_days is not None:
        try:
            term_days = int(default_payment_term_days)
        except (TypeError, ValueError) as exc:
            raise ValueError("El plazo de pago no es válido.") from exc
        if term_days not in {0, 7, 15, 30, 60}:
            raise ValueError("El plazo de pago no es válido.")
        fields.append("default_payment_term_days=?")
        params.append(term_days)
    params.append(business_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE businesses SET {', '.join(fields)} WHERE id=?", params,
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
    previous = get_business(business_id)
    if not previous:
        return None
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
        # Cambiar desde apagado o elegir otra cadencia aprueba esa regla concreta.
        # Editar solo el nombre/email no pisa un permiso más restrictivo posterior.
        if (previous.get("gestoria_cadence") or "off") != cadence:
            update_automation_permission(business_id, "send_gestoria", "rules")
    else:
        update_automation_permission(business_id, "send_gestoria", "blocked")
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


def create_gestoria_account(email: str, password_hash: str,
                            firm_name: str) -> dict:
    """Crea una identidad de gestoría; nunca la liga implícitamente a empresas."""
    clean_email = (email or "").strip().lower()[:200]
    clean_name = (firm_name or "").strip()[:160]
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", clean_email):
        raise ValueError("El email de la gestoría no es válido.")
    if not clean_name:
        raise ValueError("El nombre de la gestoría es obligatorio.")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO gestoria_accounts "
            "(email, password_hash, firm_name, created_at) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            (clean_email, password_hash, clean_name, _now()),
        ).fetchone()
    return get_gestoria_account(row["id"])


def get_gestoria_account(account_id: int | None) -> dict | None:
    if not account_id:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM gestoria_accounts WHERE id=?", (account_id,)
        ).fetchone()
    return dict(row) if row else None


def get_gestoria_account_by_email(email: str) -> dict | None:
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM gestoria_accounts WHERE email=?", (clean_email,)
        ).fetchone()
    return dict(row) if row else None


def mark_gestoria_login(account_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE gestoria_accounts SET last_login_at=? WHERE id=?",
            (_now(), account_id),
        )


def enable_gestoria_mfa(account_id: int, recovery_hashes: list[str],
                        last_counter: int) -> dict | None:
    hashes = [
        value for value in recovery_hashes
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
    ]
    if len(hashes) != len(recovery_hashes) or not hashes:
        raise ValueError("Los códigos de recuperación no son válidos.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE gestoria_accounts SET mfa_enabled=TRUE, "
            "mfa_recovery_hashes=?, mfa_last_counter=?, mfa_enrolled_at=?, "
            "session_version=session_version+1 WHERE id=? AND is_active=TRUE",
            (json.dumps(hashes), int(last_counter), _now(), account_id),
        )
    return get_gestoria_account(account_id)


def disable_gestoria_mfa(account_id: int) -> dict | None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE gestoria_accounts SET mfa_enabled=FALSE, "
            "mfa_recovery_hashes='[]', mfa_last_counter=-1, "
            "mfa_enrolled_at=NULL, session_version=session_version+1 "
            "WHERE id=?",
            (account_id,),
        )
    return get_gestoria_account(account_id)


def replace_gestoria_recovery_hashes(account_id: int,
                                     recovery_hashes: list[str]) -> None:
    if not recovery_hashes or any(
        not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
        for value in recovery_hashes
    ):
        raise ValueError("Los códigos de recuperación no son válidos.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE gestoria_accounts SET mfa_recovery_hashes=? "
            "WHERE id=? AND mfa_enabled=TRUE",
            (json.dumps(recovery_hashes), account_id),
        )


def consume_gestoria_mfa_counter(account_id: int, counter: int) -> bool:
    """Evita reutilizar el mismo TOTP incluso con dos peticiones concurrentes."""
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE gestoria_accounts SET mfa_last_counter=? "
            "WHERE id=? AND mfa_enabled=TRUE AND mfa_last_counter<?",
            (int(counter), account_id, int(counter)),
        )
        return cursor.rowcount == 1


def consume_gestoria_recovery_hash(account_id: int, code_hash: str) -> bool:
    """Consume un código de emergencia una sola vez bajo bloqueo de cuenta."""
    if not re.fullmatch(r"[0-9a-f]{64}", code_hash or ""):
        return False
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT mfa_enabled, mfa_recovery_hashes FROM gestoria_accounts "
            "WHERE id=?" + lock,
            (account_id,),
        ).fetchone()
        if not row or not row["mfa_enabled"]:
            return False
        try:
            hashes = json.loads(row["mfa_recovery_hashes"] or "[]")
        except (TypeError, json.JSONDecodeError):
            return False
        if code_hash not in hashes:
            return False
        hashes.remove(code_hash)
        conn.execute(
            "UPDATE gestoria_accounts SET mfa_recovery_hashes=? WHERE id=?",
            (json.dumps(hashes), account_id),
        )
        return True


def gestoria_recovery_codes_remaining(account: dict | None) -> int:
    if not account:
        return 0
    try:
        values = json.loads(account.get("mfa_recovery_hashes") or "[]")
    except (TypeError, json.JSONDecodeError):
        return 0
    return len(values) if isinstance(values, list) else 0


def create_gestoria_invitation(business_id: int, email: str,
                               token_hash: str, expires_at: str) -> dict:
    """Emite una invitación revocable y anula las anteriores del mismo destino."""
    clean_email = (email or "").strip().lower()[:200]
    if not get_business(business_id):
        raise ValueError("Negocio no encontrado.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", clean_email):
        raise ValueError("El email de la gestoría no es válido.")
    now = _now()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE gestoria_invitations SET revoked_at=? "
            "WHERE business_id=? AND email=? AND used_at IS NULL "
            "AND revoked_at IS NULL",
            (now, business_id, clean_email),
        )
        row = conn.execute(
            "INSERT INTO gestoria_invitations "
            "(business_id, email, token_hash, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?) RETURNING id",
            (business_id, clean_email, token_hash, expires_at, now),
        ).fetchone()
        saved = conn.execute(
            "SELECT * FROM gestoria_invitations WHERE id=?", (row["id"],)
        ).fetchone()
    return dict(saved)


def resolve_gestoria_invitation(token_hash: str) -> dict | None:
    if not token_hash:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT i.*, b.name AS business_name, b.nif AS business_nif, "
            "b.gestoria_name FROM gestoria_invitations i "
            "JOIN businesses b ON b.id=i.business_id "
            "WHERE i.token_hash=? AND i.used_at IS NULL "
            "AND i.revoked_at IS NULL AND i.expires_at>=?",
            (token_hash, _now()),
        ).fetchone()
    return dict(row) if row else None


def accept_gestoria_invitation(invitation_id: int,
                               account_id: int) -> dict | None:
    """Acepta una invitación una sola vez y crea/renueva el acceso en transacción."""
    now = _now()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        invitation = conn.execute(
            "SELECT * FROM gestoria_invitations WHERE id=?" + lock,
            (invitation_id,),
        ).fetchone()
        account = conn.execute(
            "SELECT * FROM gestoria_accounts WHERE id=?" + lock,
            (account_id,),
        ).fetchone()
        if (
            not invitation or not account
            or invitation["used_at"] is not None
            or invitation["revoked_at"] is not None
            or str(invitation["expires_at"]) < now
            or invitation["email"] != account["email"]
        ):
            return None
        conn.execute(
            "INSERT INTO gestoria_business_access "
            "(gestoria_account_id, business_id, role, status, created_at, accepted_at) "
            "VALUES (?, ?, 'gestor', 'active', ?, ?) "
            "ON CONFLICT(gestoria_account_id, business_id) DO UPDATE SET "
            "status='active', accepted_at=excluded.accepted_at, revoked_at=NULL",
            (account_id, invitation["business_id"], now, now),
        )
        conn.execute(
            "UPDATE gestoria_invitations SET used_at=? WHERE id=? "
            "AND used_at IS NULL AND revoked_at IS NULL",
            (now, invitation_id),
        )
        saved = conn.execute(
            "SELECT * FROM gestoria_business_access "
            "WHERE gestoria_account_id=? AND business_id=?",
            (account_id, invitation["business_id"]),
        ).fetchone()
    return dict(saved) if saved else None


def gestoria_account_can_access(account_id: int, business_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 AS allowed FROM gestoria_business_access a "
            "JOIN gestoria_accounts g ON g.id=a.gestoria_account_id "
            "WHERE a.gestoria_account_id=? AND a.business_id=? "
            "AND a.status='active' AND g.is_active=TRUE",
            (account_id, business_id),
        ).fetchone()
    return bool(row)


def gestoria_business_for_account(account_id: int,
                                  business_id: int) -> dict | None:
    if not gestoria_account_can_access(account_id, business_id):
        return None
    return get_business(business_id)


def list_gestoria_businesses(account_id: int) -> list[dict]:
    """Cartera resumida sin mezclar datos: cada agregado conserva business_id."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT b.*, "
            "(SELECT COUNT(*) FROM documents d WHERE d.business_id=b.id "
            "AND d.doc_status='pendiente_revisar') AS pending_documents, "
            "(SELECT COUNT(*) FROM gestoria_requests r WHERE r.business_id=b.id "
            "AND r.status='abierta') AS open_requests, "
            "(SELECT MAX(gd.prepared_at) FROM gestoria_deliveries gd "
            "WHERE gd.business_id=b.id) AS last_package_at "
            "FROM gestoria_business_access a "
            "JOIN gestoria_accounts g ON g.id=a.gestoria_account_id "
            "JOIN businesses b ON b.id=a.business_id "
            "WHERE a.gestoria_account_id=? AND a.status='active' "
            "AND g.is_active=TRUE ORDER BY b.name, b.id",
            (account_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_gestoria_access_for_business(business_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT a.*, g.email, g.firm_name, g.last_login_at "
            "FROM gestoria_business_access a "
            "JOIN gestoria_accounts g ON g.id=a.gestoria_account_id "
            "WHERE a.business_id=? ORDER BY a.created_at DESC",
            (business_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def revoke_gestoria_access(business_id: int, account_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE gestoria_business_access SET status='revoked', revoked_at=? "
            "WHERE business_id=? AND gestoria_account_id=? AND status='active'",
            (_now(), business_id, account_id),
        )
    return cur.rowcount == 1


GESTORIA_TAXPAYER_TYPES = {"sin_configurar", "autonomo", "sociedad", "otro"}
GESTORIA_INCOME_TAX_REGIMES = {
    "sin_configurar", "estimacion_directa", "estimacion_objetiva", "sociedades",
}
GESTORIA_VAT_REGIMES = {
    "sin_configurar", "general", "simplificado", "recargo", "exento",
}
GESTORIA_FILING_CADENCES = {"mensual", "trimestral"}
GESTORIA_TAX_OBLIGATIONS = {
    "303", "390", "130", "131", "111", "115", "347", "349", "200", "202",
}


def get_gestoria_fiscal_profile(business_id: int) -> dict:
    """Perfil de obligaciones; la ausencia siempre se muestra como no configurada."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM gestoria_fiscal_profiles WHERE business_id=?",
            (business_id,),
        ).fetchone()
    if not row:
        return {
            "business_id": business_id,
            "taxpayer_type": "sin_configurar",
            "income_tax_regime": "sin_configurar",
            "vat_regime": "sin_configurar",
            "filing_cadence": "trimestral",
            "obligations": [],
            "notes": None,
            "updated_at": None,
        }
    profile = dict(row)
    try:
        obligations = json.loads(profile.get("obligations") or "[]")
    except (TypeError, json.JSONDecodeError):
        obligations = []
    profile["obligations"] = [
        str(item) for item in obligations
        if str(item) in GESTORIA_TAX_OBLIGATIONS
    ]
    return profile


def update_gestoria_fiscal_profile(
    business_id: int,
    gestoria_account_id: int,
    *,
    taxpayer_type: str,
    income_tax_regime: str,
    vat_regime: str,
    filing_cadence: str,
    obligations,
    notes: str | None = None,
) -> dict:
    """Guarda criterio del despacho sin presentar ni confirmar ningún impuesto."""
    if not gestoria_account_can_access(gestoria_account_id, business_id):
        raise ValueError("La gestoría no tiene acceso a esta empresa.")
    taxpayer_type = (taxpayer_type or "").strip()
    income_tax_regime = (income_tax_regime or "").strip()
    vat_regime = (vat_regime or "").strip()
    filing_cadence = (filing_cadence or "").strip()
    if taxpayer_type not in GESTORIA_TAXPAYER_TYPES:
        raise ValueError("El tipo de contribuyente no es válido.")
    if income_tax_regime not in GESTORIA_INCOME_TAX_REGIMES:
        raise ValueError("El régimen de renta no es válido.")
    if vat_regime not in GESTORIA_VAT_REGIMES:
        raise ValueError("El régimen de IVA no es válido.")
    if filing_cadence not in GESTORIA_FILING_CADENCES:
        raise ValueError("La periodicidad fiscal no es válida.")
    normalized = sorted({
        str(item).strip() for item in (obligations or [])
        if str(item).strip() in GESTORIA_TAX_OBLIGATIONS
    }, key=lambda item: (len(item), item))
    notes = (notes or "").strip()[:1000] or None
    now = _now()
    payload = json.dumps(normalized, separators=(",", ":"))
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO gestoria_fiscal_profiles "
            "(business_id, taxpayer_type, income_tax_regime, vat_regime, "
            "filing_cadence, obligations, notes, updated_by_gestoria_id, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(business_id) DO UPDATE SET taxpayer_type=excluded.taxpayer_type, "
            "income_tax_regime=excluded.income_tax_regime, vat_regime=excluded.vat_regime, "
            "filing_cadence=excluded.filing_cadence, obligations=excluded.obligations, "
            "notes=excluded.notes, updated_by_gestoria_id=excluded.updated_by_gestoria_id, "
            "updated_at=excluded.updated_at",
            (business_id, taxpayer_type, income_tax_regime, vat_regime,
             filing_cadence, payload, notes, gestoria_account_id, now),
        )
    return get_gestoria_fiscal_profile(business_id)


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
    latest_delivery = {}
    for delivery in list_gestoria_deliveries(business_id, limit=100):
        latest_delivery.setdefault(delivery["period_label"], delivery)
    periods = []
    for label in _closed_period_labels(cadence, count, date.today()):
        start, end = gestoria_period_range(label)
        invoices = gestoria_invoices_in(business_id, start, end)
        expenses = gestoria_expenses_in(business_id, start, end)
        prepared = latest_delivery.get(label)
        periods.append({
            "label": label, "start": start, "end": end,
            "invoices": len(invoices), "expenses": len(expenses),
            "delivery_status": prepared.get("status") if prepared else None,
            "delivery_version": prepared.get("version") if prepared else None,
        })
    return periods


def record_gestoria_delivery(
    business_id: int,
    period_label: str,
    *,
    source_hash: str,
    artifact_hash: str,
    file_size: int,
    manifest: dict,
) -> dict:
    """Guarda una versión solo si cambiaron los datos fuente del período."""
    gestoria_period_range(period_label)
    if not get_business(business_id):
        raise ValueError("Negocio no encontrado.")
    manifest_text = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    now = _now()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        latest = conn.execute(
            "SELECT * FROM gestoria_deliveries WHERE business_id=? "
            "AND period_label=? ORDER BY version DESC LIMIT 1" + lock,
            (business_id, period_label),
        ).fetchone()
        if latest and latest["source_hash"] == source_hash:
            delivery_id = latest["id"]
            conn.execute(
                "UPDATE gestoria_deliveries SET artifact_hash=?, file_size=?, "
                "manifest=? WHERE id=? AND business_id=?",
                (artifact_hash, int(file_size), manifest_text,
                 delivery_id, business_id),
            )
        else:
            version = int(latest["version"] if latest else 0) + 1
            inserted = conn.execute(
                "INSERT INTO gestoria_deliveries "
                "(business_id, period_label, version, status, source_hash, "
                "artifact_hash, file_size, manifest, prepared_at) "
                "VALUES (?, ?, ?, 'preparado', ?, ?, ?, ?, ?) RETURNING id",
                (business_id, period_label, version, source_hash,
                 artifact_hash, int(file_size), manifest_text, now),
            ).fetchone()
            delivery_id = inserted["id"]
        saved = conn.execute(
            "SELECT * FROM gestoria_deliveries WHERE id=? AND business_id=?",
            (delivery_id, business_id),
        ).fetchone()
    result = dict(saved)
    result["manifest"] = json.loads(result["manifest"])
    return result


def mark_gestoria_delivery(
    business_id: int, period_label: str, event: str
) -> dict | None:
    """Marca aviso o descarga sobre la última versión preparada."""
    if event not in {"notified", "downloaded"}:
        raise ValueError("El evento de gestoría no es válido.")
    column = "notified_at" if event == "notified" else "downloaded_at"
    status = "avisado" if event == "notified" else "descargado"
    now = _now()
    with get_conn() as conn:
        latest = conn.execute(
            "SELECT id FROM gestoria_deliveries WHERE business_id=? "
            "AND period_label=? ORDER BY version DESC LIMIT 1",
            (business_id, period_label),
        ).fetchone()
        if not latest:
            return None
        conn.execute(
            f"UPDATE gestoria_deliveries SET {column}=?, status=? "
            "WHERE id=? AND business_id=?",
            (now, status, latest["id"], business_id),
        )
        saved = conn.execute(
            "SELECT * FROM gestoria_deliveries WHERE id=? AND business_id=?",
            (latest["id"], business_id),
        ).fetchone()
    result = dict(saved)
    result["manifest"] = json.loads(result["manifest"])
    return result


def list_gestoria_deliveries(business_id: int, limit: int = 24) -> list[dict]:
    limit = max(1, min(int(limit or 24), 100))
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM gestoria_deliveries WHERE business_id=? "
            "ORDER BY prepared_at DESC, id DESC LIMIT ?",
            (business_id, limit),
        ).fetchall()
    deliveries = []
    for row in rows:
        item = dict(row)
        item["manifest"] = json.loads(item["manifest"])
        deliveries.append(item)
    return deliveries


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
    if nif is not None and nif != "":
        nif = str(nif).strip().upper()
        with get_conn() as conn:
            current = conn.execute(
                "SELECT nif FROM businesses WHERE id=?", (business_id,)
            ).fetchone()
            has_records = conn.execute(
                "SELECT 1 AS found FROM invoice_records "
                "WHERE business_id=? LIMIT 1",
                (business_id,),
            ).fetchone()
        if (
            current
            and has_records
            and (current.get("nif") or "").strip().upper() != nif
        ):
            raise ValueError(
                "El NIF no puede cambiarse después de generar registros "
                "Veri*Factu; crea otro negocio para otra identidad fiscal."
            )
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


def update_onboarding_preferences(
    business_id: int,
    *,
    nif: str = "",
    address: str = "",
    default_vat=21,
    default_irpf=0,
    default_payment_term_days=15,
    invoice_template: str = "clasica",
    payment_iban: str = "",
    payment_bizum: str = "",
    payment_note: str = "",
    payment_reminders_enabled: bool = False,
    payment_reminder_days="3,7,15",
    whatsapp_reports: dict | None = None,
) -> dict:
    """Guarda de una vez la operativa elegida durante el alta.

    La pantalla no es una encuesta: IVA, IRPF, vencimiento, plantilla, forma de
    cobro y avisos pasan a ser los valores que usa el producto.
    """
    if not get_business(business_id):
        raise ValueError("Negocio no encontrado.")
    clean_nif = (nif or "").strip()[:40]
    clean_address = (address or "").strip()[:300]
    if not clean_nif or not clean_address:
        raise ValueError(
            "El NIF y la dirección fiscal son obligatorios para facturar."
        )
    vat = _tax_rate(default_vat, "El IVA", {0, 4, 10, 21})
    irpf = _tax_rate(default_irpf, "El IRPF", {0, 7, 15})
    try:
        term_days = int(default_payment_term_days)
    except (TypeError, ValueError) as exc:
        raise ValueError("El plazo de pago no es válido.") from exc
    if term_days not in {0, 7, 15, 30, 60}:
        raise ValueError("El plazo de pago no es válido.")
    if invoice_template not in INVOICE_TEMPLATES:
        raise ValueError("La plantilla de factura no es válida.")
    reminder_days = parse_payment_reminder_days(payment_reminder_days)
    iban, bizum, note = _clean_payment_details(
        payment_iban, payment_bizum, payment_note
    )
    reports = resolve_whatsapp_reports(whatsapp_reports or {})
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET nif=?, address=?, default_vat=?, "
            "default_irpf=?, default_payment_term_days=?, invoice_template=?, "
            "payment_iban=?, payment_bizum=?, payment_note=?, "
            "payment_reminders_enabled=?, payment_reminder_days=?, "
            "whatsapp_reports=? WHERE id=?",
            (
                clean_nif, clean_address,
                vat, irpf, term_days, invoice_template,
                iban or None, bizum or None, note or None,
                bool(payment_reminders_enabled),
                ",".join(str(day) for day in reminder_days),
                json.dumps(reports, ensure_ascii=False, separators=(",", ":")),
                business_id,
            ),
        )
    return get_business(business_id)


def complete_onboarding_step(business_id: int, step: str) -> dict:
    """Avanza el alta solo después de guardar todas las piezas de ese paso."""
    if step == "profile":
        field, stage = "onboarding_profile_completed", 3
    elif step == "preferences":
        field, stage = "onboarding_preferences_completed", 4
    else:
        raise ValueError("El paso de alta no es válido.")
    with get_conn() as conn:
        conn.execute(
            f"UPDATE businesses SET {field}=TRUE, onboarding_started=TRUE, "
            "onboarding_stage=CASE WHEN onboarding_stage<? THEN ? "
            "ELSE onboarding_stage END WHERE id=?",
            (stage, stage, business_id),
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


# ------------------------------------------------------ Integraciones y salud ---
INTEGRATION_MODES = {"default", "enabled", "disabled", "requested"}
INTEGRATION_USER_KEYS = {
    "ai_external", "calendar", "banking", "online_payments",
}


def integration_setting(business_id: int, integration_key: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM integration_settings "
            "WHERE business_id=? AND integration_key=?",
            (business_id, integration_key),
        ).fetchone()
    return dict(row) if row else None


def integration_enabled(
    business_id: int, integration_key: str, *, available: bool = True
) -> bool:
    """Resuelve el permiso efectivo sin romper instalaciones previas.

    Si nunca se tomó una decisión, ``default`` mantiene el comportamiento local:
    el servicio solo se usa cuando el servidor realmente lo tiene configurado.
    """
    setting = integration_setting(business_id, integration_key)
    mode = setting.get("mode") if setting else "default"
    if mode in {"disabled", "requested"}:
        return False
    return bool(available)


def update_integration_setting(
    business_id: int, integration_key: str, mode: str
) -> dict:
    integration_key = (integration_key or "").strip().lower()
    mode = (mode or "").strip().lower()
    if integration_key not in INTEGRATION_USER_KEYS:
        raise ValueError("Esta integración se gestiona desde su apartado propio.")
    if mode not in INTEGRATION_MODES - {"default"}:
        raise ValueError("El estado de la integración no es válido.")
    if not get_business(business_id):
        raise ValueError("Negocio no encontrado.")
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO integration_settings "
            "(business_id, integration_key, mode, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (business_id, integration_key) DO UPDATE SET "
            "mode=excluded.mode, last_error=NULL, updated_at=excluded.updated_at",
            (business_id, integration_key, mode, now),
        )
        row = conn.execute(
            "SELECT * FROM integration_settings "
            "WHERE business_id=? AND integration_key=?",
            (business_id, integration_key),
        ).fetchone()
    return dict(row)


def _ai_credit_limit(business: dict) -> int:
    from .adapters.billing import PLANS

    plan = business.get("plan") or "trial"
    if plan not in PLANS:
        plan = "autonomo"
    return int(PLANS[plan]["credits"])


def ai_credit_status(business_id: int, month: str | None = None) -> dict:
    """Créditos de IA externa; el cerebro local y privado no los consumen."""
    month = month or date.today().strftime("%Y-%m")
    business = get_business(business_id)
    if not business:
        return {"limit": 0, "used": 0, "remaining": 0, "month": month}
    limit = _ai_credit_limit(business)
    with get_conn() as conn:
        used = int(conn.execute(
            "SELECT COUNT(*) AS n FROM product_events WHERE business_id=? "
            "AND event_name='ai_credit_used' AND CAST(created_at AS TEXT) LIKE ?",
            (business_id, f"{month}%"),
        ).fetchone()["n"])
    return {
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
        "month": month,
    }


def claim_ai_credit(business_id: int, provider: str = "external") -> dict:
    """Reserva como máximo un crédito por mensaje, incluso con concurrencia."""
    now = _now()
    month = date.today().strftime("%Y-%m")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        business = conn.execute(
            "SELECT * FROM businesses WHERE id=?" + lock, (business_id,)
        ).fetchone()
        if not business:
            return {"allowed": False, "limit": 0, "used": 0, "remaining": 0}
        limit = _ai_credit_limit(dict(business))
        used = int(conn.execute(
            "SELECT COUNT(*) AS n FROM product_events WHERE business_id=? "
            "AND event_name='ai_credit_used' AND CAST(created_at AS TEXT) LIKE ?",
            (business_id, f"{month}%"),
        ).fetchone()["n"])
        if used >= limit:
            return {
                "allowed": False, "limit": limit, "used": used, "remaining": 0
            }
        conn.execute(
            "INSERT INTO product_events "
            "(business_id, event_name, event_data, created_at) VALUES (?, ?, ?, ?)",
            (business_id, "ai_credit_used", json.dumps({
                "provider": provider, "month": month
            }, separators=(",", ":")), now),
        )
    return {
        "allowed": True,
        "limit": limit,
        "used": used + 1,
        "remaining": max(0, limit - used - 1),
    }


def record_integration_result(
    business_id: int, integration_key: str, error: str | None = None
) -> None:
    """Guarda la última comprobación sin credenciales ni contenido del usuario."""
    now = _now()
    clean_error = (str(error or "").strip()[:300] or None)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO integration_settings "
            "(business_id, integration_key, mode, last_error, last_checked_at, updated_at) "
            "VALUES (?, ?, 'default', ?, ?, ?) "
            "ON CONFLICT (business_id, integration_key) DO UPDATE SET "
            "last_error=excluded.last_error, "
            "last_checked_at=excluded.last_checked_at",
            (business_id, integration_key, clean_error, now, now),
        )


def integration_catalog(business_id: int) -> list[dict]:
    """Estado humano de las conexiones, reutilizando sus fuentes de verdad."""
    business = get_business(business_id) or {}
    with get_conn() as conn:
        settings = {
            row["integration_key"]: dict(row)
            for row in conn.execute(
                "SELECT * FROM integration_settings WHERE business_id=?",
                (business_id,),
            ).fetchall()
        }
    try:
        from .adapters import ai as ai_adapter
        from .adapters import email as email_adapter
        from .web import whatsapp as whatsapp_adapter
        from . import verifactu_client

        runtime = {
            "ai_local": ai_adapter.local_available(),
            "ai_external": bool(
                ai_adapter.external_available() or config.ANTHROPIC_API_KEY
            ),
            "whatsapp": whatsapp_adapter.is_configured(),
            "email": email_adapter.available(),
            "verifactu": verifactu_client.is_enabled(),
        }
    except Exception:  # noqa: BLE001 - el centro nunca debe tumbar Ajustes
        runtime = {
            "ai_local": False,
            "ai_external": bool(
                config.COMPAT_AI_BASE_URL
                and config.COMPAT_AI_BASE_URL.startswith("https://")
                and config.COMPAT_AI_MODEL
                and config.COMPAT_AI_API_KEY
                and config.COMPAT_AI_LEGAL_NAME
                and config.COMPAT_AI_REGION
            ) or bool(config.ANTHROPIC_API_KEY),
            "whatsapp": False, "email": False, "verifactu": False,
        }

    definitions = (
        ("whatsapp", "WhatsApp", "Habla con Noesis y recibe avisos desde el móvil."),
        ("ai_local", "IA privada", "Modelo propio en infraestructura controlada por Noesis."),
        ("ai_external", "IA avanzada", "Respaldo para consultas y documentos complejos."),
        ("email", "Correo", "Envíos de gestoría, acceso y comunicaciones operativas."),
        ("verifactu", "Veri*Factu", "Registro fiscal preparado y, con certificado, envío a AEAT."),
        ("gestoria", "Gestoría", "Paquetes ordenados por período y acceso privado."),
        ("calendar", "Calendario externo", "Sincronización con tu calendario habitual."),
        ("banking", "Banco", "Cuadrar cobros y facturas sin mover dinero por ti."),
        ("online_payments", "Cobro por enlace", "Permitir que el cliente pague desde su portal."),
    )
    items: list[dict] = []
    for key, name, description in definitions:
        setting = settings.get(key) or {}
        mode = setting.get("mode") or "default"
        available = bool(runtime.get(key))
        active = False
        state = "pending"
        label = "por preparar"
        tone = "gray"
        action = None
        action_label = None
        href = None
        detail = None

        if key == "whatsapp":
            active = business.get("whatsapp_status") == "conectado"
            if active:
                state, label, tone = "connected", "conectado", "green"
                action, action_label = "disconnect", "Desconectar"
                detail = business.get("whatsapp_phone")
            elif available:
                state, label, tone = "ready", "listo para conectar", "amber"
                href, action_label = "#whatsapp-conexion", "Conectar"
            else:
                state, label = "unavailable", "falta configurar Meta"
        elif key == "ai_local":
            active = available
            state = "connected" if active else "pending"
            label = "activa" if active else "preparada, sin servidor"
            tone = "green" if active else "gray"
            detail = (
                f"Modelo {config.LOCAL_AI_MODEL}; no consume créditos externos"
                if active else "Noesis puede conectarla sin cambiar sus herramientas"
            )
        elif key == "ai_external":
            active = integration_enabled(
                business_id, key, available=available
            )
            credits = ai_credit_status(business_id)
            if active:
                state, label, tone = "connected", "activa", "green"
                action, action_label = "disable", "Desactivar"
            elif available:
                state, label, tone = "disabled", "desactivada", "gray"
                action, action_label = "enable", "Activar"
            else:
                state, label = "unavailable", "no configurada"
            detail = (
                f"Quedan {credits['remaining']} de {credits['limit']} consultas este mes"
                if active else "El cerebro local sigue funcionando"
            )
        elif key == "email":
            active = available
            state = "connected" if active else "unavailable"
            label = "disponible" if active else "falta configurar SMTP"
            tone = "green" if active else "gray"
            href, action_label = "#gestoria", "Revisar gestoría"
        elif key == "verifactu":
            active = bool(business.get("verifactu_enabled"))
            state = "connected" if active else ("ready" if available else "pending")
            label = "activo" if active else (
                "listo para activar" if available else "preparado, sin certificado"
            )
            tone = "green" if active else "amber"
            href, action_label = "#verifactu", "Revisar"
        elif key == "gestoria":
            active = bool(
                business.get("gestoria_email")
                and (business.get("gestoria_cadence") or "off") != "off"
            )
            state = "connected" if active else "ready"
            label = "activa" if active else "sin activar"
            tone = "green" if active else "gray"
            href, action_label = "#gestoria", "Configurar"
        else:
            requested = mode == "requested"
            state = "requested" if requested else "planned"
            label = "interés guardado" if requested else "próximamente"
            tone = "amber" if requested else "gray"
            action = "unrequest" if requested else "request"
            action_label = "Quitar interés" if requested else "Me interesa"

        items.append({
            "key": key, "name": name, "description": description,
            "mode": mode, "available": available, "active": active,
            "state": state, "status_label": label, "status_tone": tone,
            "action": action, "action_label": action_label, "href": href,
            "detail": detail, "last_error": setting.get("last_error"),
            "last_checked_at": setting.get("last_checked_at"),
        })
    return items


def business_operational_health(business_id: int) -> dict:
    """Lectura por negocio de IA, documentos y colas, sin jerga de SRE."""
    month = date.today().strftime("%Y-%m")
    ai = {
        "calls": 0,
        "input": 0,
        "output": 0,
        "estimated_cost_usd": 0.0,
        "durations": [],
    }
    with get_conn() as conn:
        usage_rows = conn.execute(
            "SELECT event_data FROM product_events WHERE business_id=? "
            "AND event_name='ai_usage' AND CAST(created_at AS TEXT) LIKE ?",
            (business_id, f"{month}%"),
        ).fetchall()
        for row in usage_rows:
            try:
                data = json.loads(row["event_data"] or "{}")
            except ValueError:
                data = {}
            ai["calls"] += 1
            ai["input"] += int(data.get("in") or 0)
            ai["output"] += int(data.get("out") or 0)
            ai["estimated_cost_usd"] += float(
                data.get("estimated_cost_usd") or 0
            )
            if data.get("duration_ms") is not None:
                ai["durations"].append(int(data["duration_ms"]))
        ai["estimated_cost_usd"] = round(ai["estimated_cost_usd"], 6)
        classified_rows = conn.execute(
            "SELECT event_data FROM product_events WHERE business_id=? "
            "AND event_name='document_classified' "
            "AND CAST(created_at AS TEXT) LIKE ?",
            (business_id, f"{month}%"),
        ).fetchall()
        classified_month = len(classified_rows)
        local_classifications = 0
        for row in classified_rows:
            try:
                classification_data = json.loads(row["event_data"] or "{}")
            except ValueError:
                classification_data = {}
            if classification_data.get("method") != "ia":
                local_classifications += 1
        document_row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN doc_status='pendiente_revisar' THEN 1 ELSE 0 END) AS pending "
            "FROM documents WHERE business_id=?",
            (business_id,),
        ).fetchone()
        corrections = conn.execute(
            "SELECT COUNT(*) AS total FROM document_classifications "
            "WHERE business_id=? AND confirmed_kind IS NOT NULL "
            "AND confirmed_kind<>detected_kind",
            (business_id,),
        ).fetchone()["total"]
        wa_rows = conn.execute(
            "SELECT status, COUNT(*) AS total FROM whatsapp_outbox "
            "WHERE business_id=? AND NOT (status='failed' AND "
            "last_error='Cancelado al desconectar WhatsApp por el usuario.') "
            "GROUP BY status",
            (business_id,),
        ).fetchall()
        wa = {row["status"]: int(row["total"]) for row in wa_rows}
        wa_error = conn.execute(
            "SELECT last_error FROM whatsapp_outbox WHERE business_id=? "
            "AND last_error IS NOT NULL ORDER BY updated_at DESC, id DESC LIMIT 1",
            (business_id,),
        ).fetchone()
        vf_rows = conn.execute(
            "SELECT status, COUNT(*) AS total FROM verifactu_outbox "
            "WHERE business_id=? GROUP BY status",
            (business_id,),
        ).fetchall()
        vf = {row["status"]: int(row["total"]) for row in vf_rows}

    avg_ms = (
        round(sum(ai["durations"]) / len(ai["durations"]))
        if ai["durations"] else None
    )
    pending_docs = int(document_row["pending"] or 0)
    failed_wa = int(wa.get("failed", 0))
    retrying_wa = int(wa.get("retrying", 0))
    rejected_vf = int(vf.get("rechazado", 0) + vf.get("agotado", 0))
    attention: list[dict] = []
    if failed_wa:
        attention.append({
            "level": "error", "area": "WhatsApp",
            "text": f"{failed_wa} mensaje(s) no han podido salir.",
            "detail": (wa_error["last_error"] if wa_error else None),
        })
    elif retrying_wa:
        attention.append({
            "level": "review", "area": "WhatsApp",
            "text": f"{retrying_wa} mensaje(s) se están reintentando.",
        })
    if rejected_vf:
        attention.append({
            "level": "error", "area": "Veri*Factu",
            "text": f"{rejected_vf} registro(s) necesitan revisión.",
        })
    if pending_docs:
        attention.append({
            "level": "review", "area": "Documentos",
            "text": f"{pending_docs} documento(s) esperan tu confirmación.",
        })

    backup = latest_backup_run()
    backup_label = "sin comprobar"
    if backup and backup.get("status") == "ok":
        backup_label = "última copia correcta"
    elif backup and backup.get("status") == "error":
        backup_label = "última copia con error"
        attention.append({
            "level": "error", "area": "Protección de datos",
            "text": "La última copia de seguridad falló.",
        })

    level = "error" if any(a["level"] == "error" for a in attention) else (
        "review" if attention else "ok"
    )
    if level == "ok":
        summary = "He revisado tus conexiones y colas. No hay nada atascado ahora mismo."
    elif level == "error":
        summary = "He encontrado una incidencia que conviene revisar antes de seguir."
    else:
        summary = "Todo sigue funcionando, pero hay alguna revisión pendiente."
    return {
        "level": level, "summary": summary, "attention": attention,
        "ai": {
            "calls": ai["calls"], "tokens": ai["input"] + ai["output"],
            "avg_ms": avg_ms,
        },
        "documents": {
            "total": int(document_row["total"] or 0),
            "pending": pending_docs, "corrections": int(corrections or 0),
            "classified_month": classified_month,
            "local_month": local_classifications,
        },
        "whatsapp": wa,
        "verifactu": vf,
        "backup": {"label": backup_label, "created_at": backup.get("created_at") if backup else None},
    }


# ------------------------------------------------------- Memoria de Noesis ---
def add_assistant_message(
    business_id: int,
    role: str,
    content: str,
    *,
    channel: str = "web",
    page: str | None = None,
    source: str | None = None,
) -> dict:
    """Guarda una intervención del usuario o de Noesis, aislada por negocio."""
    if role not in {"user", "assistant"}:
        raise ValueError("Rol de conversación no válido.")
    channel = (channel or "web").strip().lower()[:30]
    if channel not in {"web", "whatsapp", "audio", "system"}:
        channel = "web"
    content = str(content or "").strip()
    if not content:
        raise ValueError("El mensaje está vacío.")
    content = content[:12_000]
    page = (page or "").strip()[:50] or None
    source = (source or "").strip()[:30] or None
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO assistant_messages "
            "(business_id, channel, role, content, page, source, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, channel, role, content, page, source, _now()),
        ).fetchone()
        message_id = row["id"]
        saved = conn.execute(
            "SELECT * FROM assistant_messages WHERE id=? AND business_id=?",
            (message_id, business_id),
        ).fetchone()
    return dict(saved)


def list_assistant_messages(business_id: int, limit: int = 60) -> list[dict]:
    """Últimos mensajes en orden de lectura, compartidos entre web y WhatsApp."""
    limit = max(1, min(int(limit or 60), 200))
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM (SELECT * FROM assistant_messages "
            "WHERE business_id=? ORDER BY id DESC LIMIT ?) recent "
            "ORDER BY id ASC",
            (business_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def remember(
    business_id: int,
    key: str,
    value: str,
    *,
    scope_type: str = "business",
    scope_id: int = 0,
    source: str = "user",
    confidence: float | None = None,
    user_confirmed: bool = False,
) -> dict:
    """Memoria explícita y corregible; nunca guarda una inferencia como hecho."""
    key = str(key or "").strip()[:80]
    value = str(value or "").strip()[:2_000]
    scope_type = str(scope_type or "business").strip()[:30]
    if not key or not value:
        raise ValueError("La memoria necesita clave y valor.")
    confidence = None if confidence is None else max(0, min(float(confidence), 100))
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO business_memories "
            "(business_id, scope_type, scope_id, memory_key, memory_value, "
            "source, confidence, user_confirmed, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (business_id, scope_type, scope_id, memory_key) "
            "DO UPDATE SET memory_value=excluded.memory_value, "
            "source=excluded.source, confidence=excluded.confidence, "
            "user_confirmed=excluded.user_confirmed, updated_at=excluded.updated_at",
            (business_id, scope_type, int(scope_id or 0), key, value,
             source[:30], confidence, bool(user_confirmed), now, now),
        )
        row = conn.execute(
            "SELECT * FROM business_memories WHERE business_id=? "
            "AND scope_type=? AND scope_id=? AND memory_key=?",
            (business_id, scope_type, int(scope_id or 0), key),
        ).fetchone()
    return dict(row)


def list_memories(
    business_id: int, *, scope_type: str | None = None,
    scope_id: int | None = None,
) -> list[dict]:
    q = "SELECT * FROM business_memories WHERE business_id=?"
    params: list = [business_id]
    if scope_type:
        q += " AND scope_type=?"
        params.append(scope_type)
    if scope_id is not None:
        q += " AND scope_id=?"
        params.append(int(scope_id))
    q += " ORDER BY user_confirmed DESC, updated_at DESC, id DESC"
    with get_conn() as conn:
        return [dict(row) for row in conn.execute(q, params).fetchall()]


def delete_memory(business_id: int, memory_id: int) -> bool:
    """Olvida una memoria concreta sin poder cruzar el límite del negocio."""
    with get_conn() as conn:
        deleted = conn.execute(
            "DELETE FROM business_memories WHERE id=? AND business_id=?",
            (int(memory_id), business_id),
        ).rowcount
    return bool(deleted)


# --------------------------------------------------- Control de autonomía ---
# El catálogo vive en código para que una modificación maliciosa de la base de
# datos no pueda convertir una transferencia o una obligación fiscal en una
# acción automática. La tabla solo guarda la elección dentro de estos límites.
AUTOMATION_CATALOG: tuple[dict, ...] = (
    {
        "key": "organize_documents", "group": "Trabajo interno",
        "label": "Ordenar y clasificar documentos",
        "description": "Propone el tipo y coloca cada archivo en su apartado; nunca contabiliza sin revisión.",
        "risk": "low", "default": "automatic",
        "allowed_modes": ("automatic", "confirm", "blocked"),
    },
    {
        "key": "daily_brief", "group": "Trabajo interno",
        "label": "Preparar el parte y los avisos internos",
        "description": "Analiza el negocio y prioriza lo importante sin modificar datos económicos.",
        "risk": "low", "default": "automatic",
        "allowed_modes": ("automatic", "blocked"),
    },
    {
        "key": "project_alerts", "group": "Trabajo interno",
        "label": "Avisar de desviaciones en proyectos",
        "description": "Detecta excesos de horas, costes o trabajos pendientes de facturar.",
        "risk": "low", "default": "automatic",
        "allowed_modes": ("automatic", "confirm", "blocked"),
    },
    {
        "key": "payment_reminders", "group": "Comunicación",
        "label": "Recordar cobros a clientes",
        "description": "Puede seguir una cadencia que tú apruebes; fuera de ella debe preguntar.",
        "risk": "medium", "default": "rules",
        "allowed_modes": ("rules", "confirm", "blocked"),
    },
    {
        "key": "send_invoice", "group": "Comunicación",
        "label": "Enviar facturas y presupuestos",
        "description": "Prepara el envío, pero tú confirmas el destinatario y el contenido.",
        "risk": "high", "default": "confirm",
        "allowed_modes": ("confirm", "blocked"),
    },
    {
        "key": "send_gestoria", "group": "Comunicación",
        "label": "Enviar documentación a la gestoría",
        "description": "Prepara el paquete y pide permiso antes de compartirlo.",
        "risk": "high", "default": "confirm",
        "allowed_modes": ("confirm", "blocked"),
    },
    {
        "key": "move_appointments", "group": "Comunicación",
        "label": "Mover citas o cambiar asignaciones",
        "description": "Propone la reorganización y espera tu confirmación.",
        "risk": "high", "default": "confirm",
        "allowed_modes": ("confirm", "blocked"),
    },
    {
        "key": "issue_invoice", "group": "Decisiones sensibles",
        "label": "Emitir una factura definitiva",
        "description": "Puede dejarla preparada; la emisión siempre requiere tu aceptación.",
        "risk": "critical", "default": "confirm",
        "allowed_modes": ("confirm", "blocked"),
    },
    {
        "key": "bank_transfer", "group": "Decisiones sensibles",
        "label": "Realizar transferencias o pagos",
        "description": "Noesis nunca mueve dinero sin tu aprobación específica.",
        "risk": "critical", "default": "confirm",
        "allowed_modes": ("confirm", "blocked"),
    },
    {
        "key": "refund_payment", "group": "Decisiones sensibles",
        "label": "Devolver o reembolsar dinero",
        "description": "Prepara la operación y espera tu aprobación específica.",
        "risk": "critical", "default": "confirm",
        "allowed_modes": ("confirm", "blocked"),
    },
    {
        "key": "tax_submission", "group": "Decisiones sensibles",
        "label": "Presentar impuestos o registros fiscales",
        "description": "Noesis calcula y prepara; tú y tu gestoría revisáis antes de presentar.",
        "risk": "critical", "default": "confirm",
        "allowed_modes": ("confirm", "blocked"),
    },
    {
        "key": "delete_data", "group": "Decisiones sensibles",
        "label": "Borrar información de forma irreversible",
        "description": "Siempre exige confirmación reforzada y muestra qué desaparecerá.",
        "risk": "critical", "default": "confirm",
        "allowed_modes": ("confirm", "blocked"),
    },
)
# La cadencia de gestoría es una regla aprobada por el usuario, no autonomía
# abierta. Se habilita como modo separado y nunca afecta a pagos ni impuestos.
AUTOMATION_CATALOG = tuple(
    {
        **item,
        "allowed_modes": ("rules", "confirm", "blocked"),
        "description": (
            "Pregunta siempre, salvo que apruebes una cadencia mensual o "
            "trimestral."
        ),
    }
    if item["key"] == "send_gestoria" else item
    for item in AUTOMATION_CATALOG
)
AUTOMATION_BY_KEY = {item["key"]: item for item in AUTOMATION_CATALOG}
AUTOMATION_MODE_LABELS = {
    "automatic": "Puede hacerlo",
    "rules": "Solo con mis reglas",
    "confirm": "Preguntar siempre",
    "blocked": "No permitir",
}


def automation_catalog(business_id: int) -> list[dict]:
    """Devuelve los límites efectivos, no solo el valor guardado."""
    if not get_business(business_id):
        return []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT action_key, mode, updated_at FROM automation_permissions "
            "WHERE business_id=?",
            (business_id,),
        ).fetchall()
    saved = {row["action_key"]: dict(row) for row in rows}
    result = []
    for raw in AUTOMATION_CATALOG:
        item = dict(raw)
        item["allowed_modes"] = list(item["allowed_modes"])
        chosen = saved.get(item["key"], {}).get("mode") or item["default"]
        if chosen not in item["allowed_modes"]:
            chosen = item["default"]
        item["mode"] = chosen
        item["mode_label"] = AUTOMATION_MODE_LABELS[chosen]
        item["updated_at"] = saved.get(item["key"], {}).get("updated_at")
        result.append(item)
    return result


def update_automation_permission(
    business_id: int, action_key: str, mode: str
) -> dict:
    action_key = str(action_key or "").strip()
    mode = str(mode or "").strip().lower()
    policy = AUTOMATION_BY_KEY.get(action_key)
    if not policy:
        raise ValueError("La acción de Noesis no existe.")
    if mode not in policy["allowed_modes"]:
        if policy["risk"] == "critical":
            raise ValueError(
                "Esta acción es sensible y nunca puede ejecutarse automáticamente."
            )
        raise ValueError("Ese nivel de autonomía no está permitido para esta acción.")
    if not get_business(business_id):
        raise ValueError("Negocio no encontrado.")
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO automation_permissions "
            "(business_id, action_key, mode, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (business_id, action_key) DO UPDATE SET "
            "mode=excluded.mode, updated_at=excluded.updated_at",
            (business_id, action_key, mode, now, now),
        )
    return next(
        item for item in automation_catalog(business_id)
        if item["key"] == action_key
    )


def automation_decision(business_id: int, action_key: str) -> dict:
    """Respuesta única para cualquier herramienta que quiera actuar por Noesis."""
    policy = next(
        (item for item in automation_catalog(business_id)
         if item["key"] == action_key),
        None,
    )
    if not policy:
        raise ValueError("La acción de Noesis no existe.")
    mode = policy["mode"]
    return {
        **policy,
        "allowed": mode != "blocked",
        "requires_confirmation": mode in {"rules", "confirm"},
        "can_execute_automatically": mode == "automatic",
    }


def record_assistant_action(
    business_id: int,
    action_key: str,
    summary: str,
    *,
    status: str = "proposed",
    target_type: str | None = None,
    target_id: int | None = None,
    payload: dict | None = None,
    requested_by: str = "noesis",
    approved_by: str | None = None,
    error: str | None = None,
) -> dict:
    policy = AUTOMATION_BY_KEY.get(str(action_key or "").strip())
    if not policy:
        raise ValueError("La acción de Noesis no existe.")
    if status not in {"proposed", "approved", "executed", "failed", "cancelled"}:
        raise ValueError("El estado de la acción no es válido.")
    summary = str(summary or "").strip()
    if not summary:
        raise ValueError("La acción necesita una explicación.")
    if not get_business(business_id):
        raise ValueError("Negocio no encontrado.")
    now = _now()
    approved_at = now if status in {"approved", "executed"} else None
    executed_at = now if status in {"executed", "failed"} else None
    payload_text = None
    if payload is not None:
        payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(payload_text) > 12_000:
            raise ValueError("El detalle de la acción es demasiado grande.")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO assistant_actions "
            "(business_id, action_key, risk_level, status, summary, target_type, "
            "target_id, payload, requested_by, approved_by, created_at, approved_at, "
            "executed_at, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "RETURNING id",
            (
                business_id, action_key, policy["risk"], status, summary[:500],
                (target_type or "").strip()[:50] or None, target_id, payload_text,
                str(requested_by or "noesis")[:30],
                (approved_by or "").strip()[:80] or None,
                now, approved_at, executed_at, (error or "").strip()[:1000] or None,
            ),
        ).fetchone()
        saved = conn.execute(
            "SELECT * FROM assistant_actions WHERE id=? AND business_id=?",
            (row["id"], business_id),
        ).fetchone()
    return dict(saved)


def list_assistant_actions(business_id: int, limit: int = 30) -> list[dict]:
    limit = max(1, min(int(limit or 30), 200))
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM assistant_actions WHERE business_id=? "
            "ORDER BY id DESC LIMIT ?",
            (business_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


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
MAX_FOOTER_IMAGE_B64 = 1_200_000  # ~900 KB tras sanear y recomprimir
MAX_DOCUMENT_FOOTER = 800
MAX_QUOTE_TERMS = 1_500
QUOTE_VALIDITY_DAYS = {7, 15, 30, 45, 60, 90}
FOOTER_IMAGE_WIDTHS = {25, 50, 75, 100}
FOOTER_IMAGE_ALIGNMENTS = {"left", "center", "right"}
FOOTER_IMAGE_SCOPES = {"invoices", "all"}


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


_DOCUMENT_PROFILE_FIELDS = (
    "invoice_template", "brand_color", "logo_data", "logo_mime",
    "document_footer", "footer_image_data", "footer_image_mime",
    "footer_image_width", "footer_image_alignment", "footer_image_scope",
)


def _ensure_current_document_profile(conn, business: dict) -> dict:
    """Devuelve la versión visual vigente o crea una nueva si cambió la marca."""
    latest = conn.execute(
        "SELECT * FROM document_profiles WHERE business_id=? "
        "ORDER BY version DESC LIMIT 1", (business["id"],),
    ).fetchone()
    current = {
        "invoice_template": business.get("invoice_template") or "clasica",
        "brand_color": business.get("brand_color"),
        "logo_data": business.get("logo_data"),
        "logo_mime": business.get("logo_mime"),
        "document_footer": business.get("document_footer"),
        "footer_image_data": business.get("footer_image_data"),
        "footer_image_mime": business.get("footer_image_mime"),
        "footer_image_width": int(business.get("footer_image_width") or 100),
        "footer_image_alignment": business.get("footer_image_alignment") or "center",
        "footer_image_scope": business.get("footer_image_scope") or "invoices",
    }
    if latest and all(latest.get(key) == value for key, value in current.items()):
        return dict(latest)
    version = int(latest["version"] if latest else 0) + 1
    row = conn.execute(
        "INSERT INTO document_profiles (business_id, version, invoice_template, "
        "brand_color, logo_data, logo_mime, document_footer, footer_image_data, "
        "footer_image_mime, footer_image_width, footer_image_alignment, "
        "footer_image_scope, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "RETURNING *",
        (
            business["id"], version, current["invoice_template"],
            current["brand_color"], current["logo_data"], current["logo_mime"],
            current["document_footer"], current["footer_image_data"],
            current["footer_image_mime"], current["footer_image_width"],
            current["footer_image_alignment"], current["footer_image_scope"], _now(),
        ),
    ).fetchone()
    return dict(row)


def get_invoice_document_profile(invoice_id: int, business_id: int) -> dict | None:
    """Perfil visual congelado de una factura, siempre aislado por negocio."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT p.* FROM invoices i JOIN document_profiles p "
            "ON p.id=i.document_profile_id AND p.business_id=i.business_id "
            "WHERE i.id=? AND i.business_id=?",
            (invoice_id, business_id),
        ).fetchone()
    return dict(row) if row else None


def update_branding(business_id, *, template=None, brand_color=None,
                    logo_data=None, logo_mime=None, clear_logo=False,
                    document_footer=None, quote_terms=None,
                    default_quote_validity_days=None,
                    footer_image_data=None, footer_image_mime=None,
                    clear_footer_image=False, footer_image_width=None,
                    footer_image_alignment=None, footer_image_scope=None) -> dict | None:
    """Guarda una configuración documental segura y común a todo el negocio."""
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
    if clear_footer_image:
        fields += ["footer_image_data=?", "footer_image_mime=?"]
        params += [None, None]
    elif footer_image_data is not None:
        if len(footer_image_data) > MAX_FOOTER_IMAGE_B64:
            raise ValueError("La imagen del pie es demasiado grande (máximo ~900 KB).")
        if footer_image_mime != "image/png":
            raise ValueError("La imagen del pie debe estar saneada en formato PNG.")
        fields += ["footer_image_data=?", "footer_image_mime=?"]
        params += [footer_image_data, footer_image_mime]
    if footer_image_width is not None:
        try:
            width = int(footer_image_width)
        except (TypeError, ValueError) as exc:
            raise ValueError("El ancho de la imagen del pie no es válido.") from exc
        if width not in FOOTER_IMAGE_WIDTHS:
            raise ValueError("El ancho del pie debe ser 25, 50, 75 o 100%.")
        fields.append("footer_image_width=?")
        params.append(width)
    if footer_image_alignment is not None:
        alignment = str(footer_image_alignment or "").strip().lower()
        if alignment not in FOOTER_IMAGE_ALIGNMENTS:
            raise ValueError("La alineación de la imagen del pie no es válida.")
        fields.append("footer_image_alignment=?")
        params.append(alignment)
    if footer_image_scope is not None:
        scope = str(footer_image_scope or "").strip().lower()
        if scope not in FOOTER_IMAGE_SCOPES:
            raise ValueError("El uso de la imagen del pie no es válido.")
        fields.append("footer_image_scope=?")
        params.append(scope)
    if document_footer is not None:
        footer = str(document_footer or "").strip()
        if len(footer) > MAX_DOCUMENT_FOOTER:
            raise ValueError(
                f"El pie del documento no puede superar {MAX_DOCUMENT_FOOTER} caracteres."
            )
        fields.append("document_footer=?")
        params.append(footer or None)
    if quote_terms is not None:
        terms = str(quote_terms or "").strip()
        if len(terms) > MAX_QUOTE_TERMS:
            raise ValueError(
                f"Las condiciones no pueden superar {MAX_QUOTE_TERMS} caracteres."
            )
        fields.append("quote_terms=?")
        params.append(terms or None)
    if default_quote_validity_days is not None:
        try:
            validity = int(default_quote_validity_days)
        except (TypeError, ValueError) as exc:
            raise ValueError("La validez predeterminada no es válida.") from exc
        if validity not in QUOTE_VALIDITY_DAYS:
            raise ValueError("La validez debe ser de 7, 15, 30, 45, 60 o 90 días.")
        fields.append("default_quote_validity_days=?")
        params.append(validity)
    if not fields:
        return get_business(business_id)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        existing = conn.execute(
            "SELECT * FROM businesses WHERE id=?" + lock, (business_id,)
        ).fetchone()
        if not existing:
            return None
        params.append(business_id)
        conn.execute(f"UPDATE businesses SET {', '.join(fields)} WHERE id=?", params)
        updated = conn.execute(
            "SELECT * FROM businesses WHERE id=?", (business_id,)
        ).fetchone()
        _ensure_current_document_profile(conn, dict(updated))
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
        # El alta explicará y activará la experiencia completa en el paso de
        # personalización. Hasta esa elección explícita no sale contenido fuera.
        conn.execute(
            "INSERT INTO integration_settings "
            "(business_id, integration_key, mode, updated_at) "
            "VALUES (?, 'ai_external', 'disabled', ?)",
            (business_id, _now()),
        )
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


def _fold_client_reference(value: str | None) -> str:
    """Normaliza una referencia humana sin convertirla en una búsqueda difusa."""
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def resolve_client_reference(name, business_id) -> dict | None:
    """Reutiliza un cliente habitual solo cuando la referencia es inequívoca.

    Admite ``Marta`` para ``Marta López`` si no existe otra Marta. Ante dos
    coincidencias no elige ni crea un duplicado: pide una referencia más precisa.
    """
    reference = _fold_client_reference(name)
    if not reference:
        return None
    clients = list_clients(business_id)
    exact = [c for c in clients if _fold_client_reference(c["name"]) == reference]
    if len(exact) == 1:
        return exact[0]
    words = reference.split()
    matches = []
    for client in clients:
        candidate = _fold_client_reference(client["name"])
        candidate_words = candidate.split()
        if (
            candidate.startswith(reference + " ")
            or all(word in candidate_words for word in words)
        ):
            matches.append(client)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        options = ", ".join(client["name"] for client in matches[:5])
        raise ValueError(
            f"Hay varios clientes que encajan con «{name}»: {options}. "
            "Indica el nombre completo."
        )
    return None


def list_clients(business_id) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM clients WHERE business_id=? ORDER BY name",
            (business_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_or_create_client(name, business_id, **kw) -> dict:
    return (
        resolve_client_reference(name, business_id)
        or add_client(name, business_id=business_id, **kw)
    )


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
    params: list[Any] = [phone_norm]
    if exclude_id is not None:
        params.append(exclude_id)
    worker = conn.execute(
        "SELECT 1 AS found FROM workers WHERE phone_norm=?" + extra,
        tuple(params),
    ).fetchone()
    owner = conn.execute(
        "SELECT 1 AS found FROM businesses WHERE whatsapp_phone_norm=?",
        (phone_norm,),
    ).fetchone()
    return bool(worker or owner)


def list_workers(business_id: int, *, include_inactive: bool = True) -> list[dict]:
    where = "" if include_inactive else " AND active=TRUE"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, business_id, name, phone, phone_norm, color, access_code, "
            "role, can_submit_costs, can_view_assigned_budget, active, created_at, "
            "CASE WHEN pin_hash IS NULL THEN FALSE ELSE TRUE END "
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
    role: str = "campo",
    can_submit_costs: bool = True,
    can_view_assigned_budget: bool = False,
) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("El nombre del trabajador es obligatorio.")
    if not get_business(business_id):
        raise ValueError("El negocio no existe.")
    phone, phone_norm = _worker_phone(phone)
    color = _worker_color(color)
    pin_hash = _worker_pin_hash(pin)
    role = str(role or "campo").strip().lower()
    if role not in {"campo", "responsable", "oficina"}:
        raise ValueError("El rol del equipo no es válido.")
    with get_conn() as conn:
        if _worker_phone_in_use(conn, business_id, phone_norm):
            raise ValueError(
                "Ese teléfono ya tiene otra identidad en el WhatsApp central."
            )
        access_code = _new_worker_access_code(conn, business_id)
        row = conn.execute(
            "INSERT INTO workers "
            "(business_id, name, phone, phone_norm, color, access_code, pin_hash, "
            "role, can_submit_costs, can_view_assigned_budget, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                business_id, name[:120], phone, phone_norm, color,
                access_code, pin_hash, role, bool(can_submit_costs),
                bool(can_view_assigned_budget), _now(),
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
    role: str | None = None,
    can_submit_costs: bool | None = None,
    can_view_assigned_budget: bool | None = None,
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
    if role is not None:
        clean_role = str(role).strip().lower()
        if clean_role not in {"campo", "responsable", "oficina"}:
            raise ValueError("El rol del equipo no es válido.")
        fields.append("role=?")
        params.append(clean_role)
    if can_submit_costs is not None:
        fields.append("can_submit_costs=?")
        params.append(bool(can_submit_costs))
    if can_view_assigned_budget is not None:
        fields.append("can_view_assigned_budget=?")
        params.append(bool(can_view_assigned_budget))
    if fields:
        params.extend((worker_id, business_id))
        with get_conn() as conn:
            if (
                phone is not None
                and _worker_phone_in_use(
                    conn, business_id, phone_norm, exclude_id=worker_id
                )
            ):
                raise ValueError(
                    "Ese teléfono ya tiene otra identidad en el WhatsApp central."
                )
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
        if _worker_phone_in_use(
            conn, business_id, phone_norm, exclude_id=worker["id"]
        ):
            raise ValueError(
                "Ese teléfono ya tiene otra identidad en el WhatsApp central."
            )
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
            price_estimate=None, project_id=None, worker_id=None,
            *, business_id: int) -> dict:
    description = str(description or "").strip()
    if not description or len(description) > 500:
        raise ValueError("El trabajo necesita una descripción (máx. 500 caracteres).")
    if not get_client(client_id, business_id):
        raise ValueError("El cliente no pertenece a este negocio.")
    project = None
    if project_id not in (None, ""):
        project_id = int(project_id)
        project = get_project(project_id, business_id)
        if not project:
            raise ValueError("El proyecto no pertenece a este negocio.")
        if project.get("client_id") and project["client_id"] != int(client_id):
            raise ValueError("El trabajo y el proyecto deben tener el mismo cliente.")
    else:
        project_id = None
    if worker_id not in (None, ""):
        worker_id = int(worker_id)
        worker = get_worker(worker_id, business_id)
        if not worker or not worker.get("active"):
            raise ValueError("La persona no pertenece a este negocio o está inactiva.")
    else:
        worker_id = None
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO jobs (business_id, client_id, description, scheduled_for, "
            "zone, price_estimate, project_id, worker_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, client_id, description, scheduled_for, zone,
             price_estimate, project_id, worker_id, _now()),
        ).fetchone()
        new_id = row["id"]
    if project_id and worker_id:
        _ensure_project_member(project_id, worker_id, business_id)
    return get_job(new_id, business_id)


def get_job(job_id, business_id) -> dict | None:
    sql = (
        "SELECT j.*, w.name AS worker_name, w.color AS worker_color, "
        "p.name AS project_name, p.location AS project_location, "
        "p.status AS project_status "
        "FROM jobs j LEFT JOIN workers w ON w.id=j.worker_id "
        "AND w.business_id=j.business_id "
        "LEFT JOIN projects p ON p.id=j.project_id "
        "AND p.business_id=j.business_id WHERE j.id=? AND j.business_id=?"
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
            "SELECT 1 AS found FROM worker_clockins WHERE job_id=? AND business_id=? "
            "UNION ALL SELECT 1 FROM job_materials WHERE job_id=? AND business_id=? "
            "UNION ALL SELECT 1 FROM job_updates WHERE job_id=? AND business_id=? "
            "UNION ALL SELECT 1 FROM job_completions WHERE job_id=? AND business_id=? "
            "LIMIT 1",
            (job_id, business_id, job_id, business_id, job_id, business_id,
             job_id, business_id),
        ).fetchone()
        if used:
            raise ValueError(
                "El trabajo tiene actividad de campo y debe conservarse como justificante."
            )
        conn.execute(
            "UPDATE project_tasks SET job_id=NULL WHERE job_id=? AND business_id=?",
            (job_id, business_id),
        )
        conn.execute("DELETE FROM jobs WHERE id=? AND business_id=?",
                     (job_id, business_id))


def jobs_for_date(day: str, business_id) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT j.*, c.name AS client_name, c.zone AS client_zone, "
            "w.name AS worker_name, w.color AS worker_color, "
            "p.name AS project_name, p.location AS project_location "
            "FROM jobs j LEFT JOIN clients c ON c.id = j.client_id "
            "AND c.business_id = j.business_id "
            "LEFT JOIN workers w ON w.id=j.worker_id "
            "AND w.business_id=j.business_id "
            "LEFT JOIN projects p ON p.id=j.project_id "
            "AND p.business_id=j.business_id "
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
            "w.color AS worker_color, p.name AS project_name, "
            "p.location AS project_location FROM jobs j "
            "LEFT JOIN clients c ON c.id = j.client_id "
            "AND c.business_id = j.business_id "
            "LEFT JOIN workers w ON w.id=j.worker_id "
            "AND w.business_id=j.business_id "
            "LEFT JOIN projects p ON p.id=j.project_id "
            "AND p.business_id=j.business_id "
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
    if worker_id is not None and job.get("project_id"):
        _ensure_project_member(job["project_id"], worker_id, business_id)
    return get_job(job_id, business_id)


def assign_job_project(
    job_id: int, project_id: int | None, business_id: int
) -> dict | None:
    """Conecta un trabajo existente sin permitir relaciones entre negocios."""
    job = get_job(job_id, business_id)
    if not job:
        return None
    if project_id is not None:
        project = get_project(project_id, business_id)
        if not project:
            raise ValueError("El proyecto no pertenece a este negocio.")
        if project.get("client_id") and project["client_id"] != job["client_id"]:
            raise ValueError("El trabajo y el proyecto deben tener el mismo cliente.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET project_id=? WHERE id=? AND business_id=?",
            (project_id, job_id, business_id),
        )
    if project_id is not None and job.get("worker_id"):
        _ensure_project_member(project_id, job["worker_id"], business_id)
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
            "c.zone AS client_zone, w.name AS worker_name, w.color AS worker_color, "
            "p.name AS project_name, p.location AS project_location, "
            "p.status AS project_status "
            "FROM jobs j "
            "LEFT JOIN clients c ON c.id=j.client_id "
            "AND c.business_id=j.business_id "
            "JOIN workers w ON w.id=j.worker_id "
            "AND w.business_id=j.business_id "
            "LEFT JOIN projects p ON p.id=j.project_id "
            "AND p.business_id=j.business_id "
            "WHERE j.business_id=? AND j.worker_id=?" + day_filter
            + " ORDER BY j.scheduled_for",
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]


# ------------------------------------------------------- Cierre de trabajo ---
JOB_UPDATE_KINDS = {"nota", "incidencia", "foto"}
JOB_COMPLETION_STATUSES = {"pendiente_cliente", "confirmado", "rechazado"}


def _worker_can_access_job(job: dict, worker_id: int, business_id: int) -> bool:
    if job.get("worker_id") == worker_id:
        return True
    if not job.get("project_id"):
        return False
    with get_conn() as conn:
        member = conn.execute(
            "SELECT 1 AS found FROM project_members WHERE business_id=? "
            "AND project_id=? AND worker_id=?",
            (business_id, job["project_id"], worker_id),
        ).fetchone()
    return bool(member)


def worker_can_access_job(job_id: int, worker_id: int, business_id: int) -> bool:
    job = get_job(job_id, business_id)
    return bool(job and _worker_can_access_job(job, worker_id, business_id))


def _field_worker(job: dict, worker_id, business_id: int) -> int | None:
    if worker_id in (None, ""):
        return None
    worker_id = int(worker_id)
    worker = get_worker(worker_id, business_id)
    if not worker or not worker.get("active"):
        raise ValueError("La persona no pertenece a este negocio o está inactiva.")
    if not _worker_can_access_job(job, worker_id, business_id):
        raise ValueError("Este trabajo está asignado a otra persona.")
    return worker_id


def add_job_material(
    job_id: int, description, quantity, unit_cost, *, business_id: int,
    worker_id: int | None = None,
) -> dict:
    job = get_job(job_id, business_id)
    if not job:
        raise ValueError("Trabajo no encontrado.")
    worker_id = _field_worker(job, worker_id, business_id)
    description = str(description or "").strip()
    if not description or len(description) > 240:
        raise ValueError("Indica el material (máx. 240 caracteres).")
    quantity = _project_number(quantity, "La cantidad")
    unit_cost = _project_number(
        unit_cost, "El coste unitario", allow_zero=True
    )
    total = float((Decimal(str(quantity)) * Decimal(str(unit_cost))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ))
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO job_materials (business_id, job_id, worker_id, "
            "description, quantity, unit_cost, total, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, job_id, worker_id, description, quantity, unit_cost,
             total, _now()),
        ).fetchone()
        saved = conn.execute(
            "SELECT * FROM job_materials WHERE id=? AND business_id=?",
            (row["id"], business_id),
        ).fetchone()
    record_product_event(business_id, "job_material_added")
    return dict(saved)


def add_job_update(
    job_id: int, kind: str, body: str | None = None, *, business_id: int,
    worker_id: int | None = None, document_id: int | None = None,
) -> dict:
    job = get_job(job_id, business_id)
    if not job:
        raise ValueError("Trabajo no encontrado.")
    worker_id = _field_worker(job, worker_id, business_id)
    kind = str(kind or "").strip()
    if kind not in JOB_UPDATE_KINDS:
        raise ValueError("El tipo de actualización no es válido.")
    body = str(body or "").strip()[:2000] or None
    if kind in {"nota", "incidencia"} and not body:
        raise ValueError("Escribe qué ha pasado.")
    if document_id not in (None, ""):
        document_id = int(document_id)
        with get_conn() as conn:
            document = conn.execute(
                "SELECT id FROM documents WHERE id=? AND business_id=?",
                (document_id, business_id),
            ).fetchone()
        if not document:
            raise ValueError("La evidencia no pertenece a este negocio.")
    else:
        document_id = None
    if kind == "foto" and document_id is None:
        raise ValueError("Adjunta una foto como evidencia.")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO job_updates (business_id, job_id, worker_id, "
            "document_id, kind, body, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "RETURNING id",
            (business_id, job_id, worker_id, document_id, kind, body, _now()),
        ).fetchone()
        saved = conn.execute(
            "SELECT * FROM job_updates WHERE id=? AND business_id=?",
            (row["id"], business_id),
        ).fetchone()
    record_product_event(business_id, f"job_{kind}_added")
    return dict(saved)


def _clean_signature(signature_data: str | None) -> tuple[str | None, str | None]:
    value = str(signature_data or "").strip()
    if not value:
        return None, None
    if not value.startswith("data:image/png;base64,") or len(value) > 180_000:
        raise ValueError("La firma no tiene un formato válido.")
    return value, hashlib.sha256(value.encode()).hexdigest()


def get_job_completion(job_id: int, business_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT jc.*, i.number AS invoice_number, i.status AS invoice_status, "
            "i.total AS invoice_total FROM job_completions jc "
            "LEFT JOIN invoices i ON i.id=jc.invoice_id "
            "AND i.business_id=jc.business_id "
            "WHERE jc.job_id=? AND jc.business_id=?",
            (job_id, business_id),
        ).fetchone()
    return dict(row) if row else None


def prepare_job_invoice_draft(
    job_id: int, business_id: int, *, base=None, vat_rate=None, irpf_rate=None
) -> dict:
    job = get_job(job_id, business_id)
    completion = get_job_completion(job_id, business_id)
    if not job or not completion:
        raise ValueError("Cierra primero el trabajo antes de preparar la factura.")
    if completion.get("status") == "rechazado":
        raise ValueError("El cliente ha rechazado el cierre. Revísalo antes de facturar.")
    if completion.get("invoice_id"):
        invoice = get_invoice(completion["invoice_id"], business_id)
        if invoice:
            return invoice
    amount = job.get("price_estimate") if base in (None, "") else base
    if amount in (None, "") or float(amount) <= 0:
        raise ValueError(
            "Falta el importe del trabajo. Indícalo para preparar el borrador."
        )
    business = get_business(business_id) or {}
    invoice = add_invoice(
        job["client_id"], job["description"], amount,
        business.get("default_vat", config.DEFAULT_VAT_RATE)
        if vat_rate in (None, "") else vat_rate,
        business.get("default_irpf", 0) if irpf_rate in (None, "") else irpf_rate,
        business_id=business_id,
    )
    with get_conn() as conn:
        conn.execute(
            "UPDATE job_completions SET invoice_id=? WHERE job_id=? "
            "AND business_id=? AND invoice_id IS NULL",
            (invoice["id"], job_id, business_id),
        )
    record_product_event(business_id, "job_invoice_draft_prepared")
    return invoice


def complete_job(
    job_id: int, *, business_id: int, worker_id: int | None = None,
    summary: str | None = None, customer_name: str | None = None,
    signature_data: str | None = None, source: str = "trabajador",
    signer_ip_hash: str | None = None, signer_user_agent: str | None = None,
) -> dict:
    job = get_job(job_id, business_id)
    if not job:
        raise ValueError("Trabajo no encontrado.")
    worker_id = _field_worker(job, worker_id, business_id)
    if get_job_completion(job_id, business_id):
        raise ValueError("Este trabajo ya tiene un cierre registrado.")
    summary = str(summary or "").strip()[:2000] or None
    customer_name = str(customer_name or "").strip()[:160] or None
    signature_data, signature_hash = _clean_signature(signature_data)
    if bool(customer_name) != bool(signature_data):
        raise ValueError("Para firmar, indica el nombre del cliente y su firma.")
    status = "confirmado" if signature_data else "pendiente_cliente"
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO job_completions (business_id, job_id, worker_id, status, "
            "summary, customer_name, signature_data, signature_hash, "
            "signer_ip_hash, signer_user_agent, source, created_at, confirmed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, job_id, worker_id, status, summary, customer_name,
             signature_data, signature_hash, signer_ip_hash,
             str(signer_user_agent or "")[:300] or None, source, now,
             now if status == "confirmado" else None),
        ).fetchone()
        conn.execute(
            "UPDATE jobs SET status='hecho' WHERE id=? AND business_id=?",
            (job_id, business_id),
        )
    record_product_event(business_id, "job_completed")
    if job.get("price_estimate") and float(job["price_estimate"]) > 0:
        prepare_job_invoice_draft(job_id, business_id)
    return get_job_completion(job_id, business_id) or {"id": row["id"]}


def confirm_job_completion(
    job_id: int, client_id: int, *, business_id: int, accepted: bool,
    customer_name: str | None = None, customer_note: str | None = None,
    signature_data: str | None = None, signer_ip_hash: str | None = None,
    signer_user_agent: str | None = None,
) -> dict:
    job = get_job(job_id, business_id)
    completion = get_job_completion(job_id, business_id)
    if not job or job.get("client_id") != client_id or not completion:
        raise ValueError("Cierre de trabajo no encontrado.")
    if completion.get("status") != "pendiente_cliente":
        return completion
    now = _now()
    customer_note = str(customer_note or "").strip()[:1000] or None
    if accepted:
        customer_name = str(customer_name or "").strip()[:160]
        signature_data, signature_hash = _clean_signature(signature_data)
        if not customer_name or not signature_data:
            raise ValueError("Escribe tu nombre y firma para confirmar el trabajo.")
        values = (
            "confirmado", customer_name, customer_note, signature_data,
            signature_hash, signer_ip_hash,
            str(signer_user_agent or "")[:300] or None, now, None,
        )
    else:
        if not customer_note:
            raise ValueError("Indica qué falta o qué hay que revisar.")
        values = (
            "rechazado", None, customer_note, None, None, signer_ip_hash,
            str(signer_user_agent or "")[:300] or None, None, now,
        )
    with get_conn() as conn:
        conn.execute(
            "UPDATE job_completions SET status=?, customer_name=?, customer_note=?, "
            "signature_data=?, signature_hash=?, signer_ip_hash=?, "
            "signer_user_agent=?, confirmed_at=?, rejected_at=? "
            "WHERE job_id=? AND business_id=?",
            (*values, job_id, business_id),
        )
    record_product_event(
        business_id,
        "job_completion_confirmed" if accepted else "job_completion_rejected",
    )
    return get_job_completion(job_id, business_id) or completion


def job_field_view(job_id: int, business_id: int) -> dict | None:
    job = get_job(job_id, business_id)
    if not job:
        return None
    with get_conn() as conn:
        materials = conn.execute(
            "SELECT m.*, w.name AS worker_name FROM job_materials m "
            "LEFT JOIN workers w ON w.id=m.worker_id AND w.business_id=m.business_id "
            "WHERE m.job_id=? AND m.business_id=? ORDER BY m.created_at DESC, m.id DESC",
            (job_id, business_id),
        ).fetchall()
        updates = conn.execute(
            "SELECT u.*, w.name AS worker_name, d.filename, d.mime "
            "FROM job_updates u LEFT JOIN workers w ON w.id=u.worker_id "
            "AND w.business_id=u.business_id LEFT JOIN documents d "
            "ON d.id=u.document_id AND d.business_id=u.business_id "
            "WHERE u.job_id=? AND u.business_id=? "
            "ORDER BY u.created_at DESC, u.id DESC",
            (job_id, business_id),
        ).fetchall()
        tasks = conn.execute(
            "SELECT * FROM project_tasks WHERE job_id=? AND business_id=? "
            "ORDER BY created_at, id",
            (job_id, business_id),
        ).fetchall()
    job["materials"] = [dict(row) for row in materials]
    job["material_cost"] = round(sum(float(row["total"]) for row in materials), 2)
    job["updates"] = [dict(row) for row in updates]
    job["tasks"] = [dict(row) for row in tasks]
    job["completion"] = get_job_completion(job_id, business_id)
    return job


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


def _worked_seconds_by_job(
    records: list[dict], now: datetime | None = None
) -> dict[int, float]:
    """Reconstruye horas efectivas por trabajo desde el registro append-only."""
    now = now or datetime.now()
    totals: dict[int, float] = {}
    working = False
    paused = False
    segment_start: datetime | None = None
    active_job_id: int | None = None

    def close_segment(point: datetime) -> None:
        nonlocal segment_start
        if (
            active_job_id is not None
            and segment_start is not None
            and point >= segment_start
        ):
            totals[active_job_id] = totals.get(active_job_id, 0.0) + (
                point - segment_start
            ).total_seconds()
        segment_start = None

    for record in _active_clockin_records(records):
        point = datetime.fromisoformat(str(record["effective_at"]))
        action = record["action"]
        if action == "entrada" and not working:
            working = True
            paused = False
            active_job_id = record.get("job_id")
            segment_start = point
        elif action == "pausa" and working and not paused:
            close_segment(point)
            paused = True
        elif action == "reanudar" and working and paused:
            paused = False
            segment_start = point
        elif action == "salida" and working:
            if not paused:
                close_segment(point)
            working = False
            paused = False
            active_job_id = None
            segment_start = None
    if working and not paused:
        close_segment(now)
    return totals


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
        if state["working"] and action != "entrada":
            open_job_id = state["entry"].get("job_id")
            if job_id is not None and job_id != open_job_id:
                raise ValueError(
                    "Termina o pausa el trabajo actual antes de cambiar de trabajo."
                )
            # Pausa, reanudación y salida heredan el trabajo de la entrada para que
            # el coste no dependa del radio seleccionado después en el portal.
            job_id = open_job_id
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
    if not 1 <= len(config.VERIFACTU_PRODUCER_NAME) <= 120:
        errors.append("nombre del productor (máximo 120 caracteres)")
    try:
        _verifactu_nif(config.VERIFACTU_PRODUCER_NIF, "El NIF del productor")
    except ValueError:
        errors.append("NOESIS_VERIFACTU_PRODUCER_NIF")
    if not 1 <= len(config.VERIFACTU_SYSTEM_NAME) <= 30:
        errors.append("nombre del sistema (máximo 30 caracteres)")
    if not 1 <= len(config.VERIFACTU_SYSTEM_ID) <= 2:
        errors.append("identificador del sistema (máximo 2 caracteres)")
    if not 1 <= len(config.VERIFACTU_SYSTEM_VERSION) <= 50:
        errors.append("versión del sistema (máximo 50 caracteres)")
    if not 1 <= len(config.VERIFACTU_INSTALLATION_PREFIX) <= 80:
        errors.append("identificador de instalación")
    if config.VERIFACTU_HASH_ALGORITHM != "sha256":
        errors.append("algoritmo SHA-256")
    if config.VERIFACTU_HASH_TYPE != "01":
        errors.append("tipo de huella 01")
    if config.VERIFACTU_RECORD_VERSION != "1.0":
        errors.append("versión de registro 1.0")
    official_qr_urls = {
        "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR",
        "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR",
    }
    if config.VERIFACTU_QR_BASE_URL not in official_qr_urls:
        errors.append("URL oficial AEAT del QR")
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


_SERIES_DEFAULTS = {
    "invoice": ("GENERAL", "Facturas", "{YYYY}/"),
    "rectifying": ("RECT", "Rectificativas", "R{YYYY}/"),
    "simplified": ("TICKET", "Simplificadas", "T{YYYY}/"),
}


def _series_document_type(invoice_type: str) -> str:
    if invoice_type.startswith("R"):
        return "rectifying"
    if invoice_type == "F2":
        return "simplified"
    return "invoice"


def _ensure_default_invoice_series(conn, business_id: int, document_type: str):
    if document_type not in _SERIES_DEFAULTS:
        raise ValueError("El tipo de serie no es válido.")
    code, name, prefix = _SERIES_DEFAULTS[document_type]
    conn.execute(
        "INSERT INTO invoice_series "
        "(business_id, code, name, document_type, prefix_template, padding, "
        "is_default, active, created_at) VALUES (?, ?, ?, ?, ?, 4, TRUE, TRUE, ?) "
        "ON CONFLICT (business_id, code) DO NOTHING",
        (business_id, code, name, document_type, prefix, _now()),
    )
    return conn.execute(
        "SELECT * FROM invoice_series WHERE business_id=? AND document_type=? "
        "AND is_default=TRUE AND active=TRUE ORDER BY id LIMIT 1",
        (business_id, document_type),
    ).fetchone()


def list_invoice_series(business_id: int) -> list[dict]:
    if not get_business(business_id):
        return []
    with get_conn() as conn:
        for document_type in _SERIES_DEFAULTS:
            _ensure_default_invoice_series(conn, business_id, document_type)
        rows = conn.execute(
            "SELECT * FROM invoice_series WHERE business_id=? "
            "ORDER BY document_type, is_default DESC, id",
            (business_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def add_invoice_series(
    business_id: int,
    *,
    code: str,
    name: str,
    document_type: str,
    prefix_template: str,
    padding: int = 4,
) -> dict:
    if not get_business(business_id):
        raise ValueError("Negocio no encontrado.")
    code = (code or "").strip().upper()
    name = (name or "").strip()
    document_type = (document_type or "").strip().lower()
    prefix_template = (prefix_template or "").strip()
    if not re.fullmatch(r"[A-Z0-9_-]{1,20}", code):
        raise ValueError("El código de serie solo admite letras, números, _ y -.")
    if not 1 <= len(name) <= 80:
        raise ValueError("El nombre de la serie es obligatorio.")
    if document_type not in _SERIES_DEFAULTS:
        raise ValueError("El tipo de serie no es válido.")
    if (
        "{YYYY}" not in prefix_template
        or len(prefix_template) > 30
        or any(char in prefix_template for char in "\r\n\t")
    ):
        raise ValueError("El formato debe incluir {YYYY} y no superar 30 caracteres.")
    try:
        padding = int(padding)
    except (TypeError, ValueError) as exc:
        raise ValueError("La longitud de numeración no es válida.") from exc
    if not 2 <= padding <= 8:
        raise ValueError("La longitud de numeración debe estar entre 2 y 8.")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO invoice_series "
            "(business_id, code, name, document_type, prefix_template, padding, "
            "is_default, active, created_at) VALUES (?, ?, ?, ?, ?, ?, FALSE, TRUE, ?) "
            "RETURNING id",
            (
                business_id, code, name, document_type, prefix_template,
                padding, _now(),
            ),
        ).fetchone()
        created = conn.execute(
            "SELECT * FROM invoice_series WHERE id=? AND business_id=?",
            (row["id"], business_id),
        ).fetchone()
        return dict(created)


def _normalize_invoice_lines(
    lines,
    *,
    fallback_concept: str | None = None,
    fallback_base=None,
    fallback_vat=config.DEFAULT_VAT_RATE,
    allow_negative: bool = False,
) -> list[dict]:
    if not lines:
        lines = [{
            "description": fallback_concept,
            "quantity": 1,
            "unit_price": fallback_base,
            "discount_rate": 0,
            "vat_rate": fallback_vat,
        }]
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        raise ValueError("La factura debe tener entre 1 y 100 líneas.")
    normalized = []
    for position, raw in enumerate(lines, 1):
        if not isinstance(raw, dict):
            raise ValueError("Cada línea de factura debe ser un objeto válido.")
        description = (raw.get("description") or raw.get("concept") or "").strip()
        if not 1 <= len(description) <= 500:
            raise ValueError("Cada línea necesita una descripción de hasta 500 caracteres.")
        try:
            quantity = Decimal(str(raw.get("quantity", 1)))
            unit_price = Decimal(str(raw.get("unit_price", raw.get("price"))))
            discount = Decimal(str(raw.get("discount_rate", 0)))
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise ValueError("Cantidad, precio y descuento deben ser números válidos.") from exc
        if not quantity.is_finite() or quantity <= 0 or quantity > 1_000_000:
            raise ValueError("La cantidad debe ser mayor que cero.")
        if not unit_price.is_finite() or abs(unit_price) > Decimal("10000000"):
            raise ValueError("El precio unitario no es válido.")
        if not discount.is_finite() or discount < 0 or discount > 100:
            raise ValueError("El descuento debe estar entre 0 y 100%.")
        base = (quantity * unit_price * (Decimal("1") - discount / 100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if (not allow_negative and base <= 0) or (allow_negative and base == 0):
            raise ValueError("La base de cada línea debe ser distinta de cero.")
        vat_rate = _tax_rate(raw.get("vat_rate", fallback_vat), "El IVA", {0, 4, 10, 21})
        vat = (base * Decimal(str(vat_rate)) / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        normalized.append({
            "position": position,
            "description": description,
            "quantity": float(quantity),
            "unit_price": float(unit_price.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "discount_rate": float(discount),
            "vat_rate": vat_rate,
            "base": float(base),
            "vat_amount": float(vat),
            "total": float((base + vat).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        })
    return normalized


def _invoice_totals(lines: list[dict], irpf_rate) -> dict:
    irpf_rate = _tax_rate(irpf_rate, "El IRPF", {0, 7, 15})
    base = sum((Decimal(str(line["base"])) for line in lines), Decimal("0"))
    vat = sum((Decimal(str(line["vat_amount"])) for line in lines), Decimal("0"))
    base = base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    vat = vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    irpf = (base * Decimal(str(irpf_rate)) / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total = (base + vat - irpf).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rates = {line["vat_rate"] for line in lines}
    return {
        "base": float(base),
        "vat_rate": next(iter(rates)) if len(rates) == 1 else -1,
        "vat_amount": float(vat),
        "irpf_rate": irpf_rate,
        "irpf_amount": float(irpf),
        "total": float(total),
    }


def add_invoice(client_id, concept, base, vat_rate=config.DEFAULT_VAT_RATE,
                irpf_rate=0, *, business_id: int, lines=None,
                invoice_type: str = "F1", series_id: int | None = None,
                operation_date: str | None = None, notes: str | None = None,
                payment_method: str | None = None,
                legal_mention: str | None = None) -> dict:
    """Crea una factura calculando IVA y retención de IRPF.

    Total = base + IVA − IRPF retenido (así sale el importe que el cliente paga).
    """
    if not get_client(client_id, business_id):
        raise ValueError("El cliente no pertenece a este negocio.")
    invoice_type = (invoice_type or "F1").strip().upper()
    if invoice_type not in {"F1", "F2"}:
        raise ValueError("Solo se pueden crear facturas completas o simplificadas.")
    normalized = _normalize_invoice_lines(
        lines, fallback_concept=concept, fallback_base=base,
        fallback_vat=vat_rate,
    )
    totals = _invoice_totals(normalized, irpf_rate)
    concept = normalized[0]["description"]
    if len(normalized) > 1:
        concept = f"{concept} y {len(normalized) - 1} línea(s) más"
    if operation_date:
        try:
            operation_date = date.fromisoformat(str(operation_date)).isoformat()
        except ValueError as exc:
            raise ValueError("La fecha de operación no es válida.") from exc
    notes = (notes or "").strip() or None
    payment_method = (payment_method or "").strip() or None
    legal_mention = (legal_mention or "").strip() or None
    for value, label, maximum in (
        (notes, "Las notas", 2000),
        (payment_method, "La forma de pago", 120),
        (legal_mention, "La mención legal", 500),
    ):
        if value and len(value) > maximum:
            raise ValueError(f"{label} supera {maximum} caracteres.")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        document_type = _series_document_type(invoice_type)
        if series_id is None:
            series = _ensure_default_invoice_series(conn, business_id, document_type)
            series_id = series["id"]
        else:
            series = conn.execute(
                "SELECT * FROM invoice_series WHERE id=? AND business_id=? "
                "AND active=TRUE",
                (series_id, business_id),
            ).fetchone()
            if not series or series["document_type"] != document_type:
                raise ValueError("La serie no corresponde al tipo de factura.")
        row = conn.execute(
            "INSERT INTO invoices (business_id, client_id, concept, base, vat_rate, "
            "vat_amount, irpf_rate, irpf_amount, total, status, invoice_type, "
            "series_id, operation_date, notes, payment_method, legal_mention, "
            "currency, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', "
            "?, ?, ?, ?, ?, ?, 'EUR', ?) RETURNING id",
            (
                business_id, client_id, concept, totals["base"],
                totals["vat_rate"], totals["vat_amount"], totals["irpf_rate"],
                totals["irpf_amount"], totals["total"], invoice_type, series_id,
                operation_date, notes, payment_method, legal_mention, _now(),
            ),
        ).fetchone()
        new_id = row["id"]
        created_at = _now()
        for line in normalized:
            conn.execute(
                "INSERT INTO invoice_lines "
                "(business_id, invoice_id, position, description, quantity, "
                "unit_price, discount_rate, vat_rate, base, vat_amount, total, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    business_id, new_id, line["position"], line["description"],
                    line["quantity"], line["unit_price"], line["discount_rate"],
                    line["vat_rate"], line["base"], line["vat_amount"],
                    line["total"], created_at,
                ),
            )
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
    rectification_type: str = "I",
    reason: str,
    lines=None,
    series_id: int | None = None,
) -> dict:
    """Crea una rectificativa por diferencias; el original nunca se modifica."""
    original = get_invoice(original_invoice_id, business_id)
    if not original or original.get("status") not in {
        "enviada", "parcial", "cobrada"
    }:
        raise ValueError("Solo se puede rectificar una factura ya emitida.")
    if get_invoice_cancellation_record(original_invoice_id, business_id):
        raise ValueError(
            "El registro fiscal de esta factura está anulado; no puede rectificarse."
        )
    invoice_type = (invoice_type or "").strip().upper()
    if invoice_type not in {"R1", "R2", "R3", "R4", "R5"}:
        raise ValueError("El tipo de factura rectificativa no es válido.")
    if invoice_type == "R5" and original.get("invoice_type") != "F2":
        raise ValueError("R5 solo puede rectificar una factura simplificada F2.")
    if invoice_type != "R5" and original.get("invoice_type") == "F2":
        raise ValueError("Una factura simplificada F2 debe rectificarse como R5.")
    rectification_type = (rectification_type or "").strip().upper()
    if rectification_type != "I":
        raise ValueError(
            "Noesis solo prepara rectificativas por diferencias. "
            "La rectificación por sustitución requiere revisión fiscal."
        )
    concept = (concept or "").strip()
    reason = (reason or "").strip()
    if not concept or len(concept) > 500:
        raise ValueError("El concepto es obligatorio y no puede superar 500 caracteres.")
    if len(reason) < 3 or len(reason) > 1000:
        raise ValueError("El motivo de rectificación es obligatorio.")
    normalized = _normalize_invoice_lines(
        lines,
        fallback_concept=concept,
        fallback_base=base,
        fallback_vat=vat_rate,
        allow_negative=True,
    )
    totals = _invoice_totals(normalized, irpf_rate)
    if totals["base"] == 0:
        raise ValueError("La base rectificada debe ser distinta de cero.")
    concept = normalized[0]["description"]
    if len(normalized) > 1:
        concept = f"{concept} y {len(normalized) - 1} línea(s) más"
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        current_original = conn.execute(
            "SELECT * FROM invoices WHERE id=? AND business_id=?" + lock,
            (original_invoice_id, business_id),
        ).fetchone()
        if not current_original or current_original["status"] not in {
            "enviada", "parcial", "cobrada"
        }:
            raise ValueError("Solo se puede rectificar una factura ya emitida.")
        cancelled = conn.execute(
            "SELECT 1 FROM invoice_cancellation_records "
            "WHERE invoice_id=? AND business_id=? LIMIT 1",
            (original_invoice_id, business_id),
        ).fetchone()
        if cancelled:
            raise ValueError(
                "El registro fiscal de esta factura está anulado; no puede rectificarse."
            )
        pending = conn.execute(
            "SELECT id FROM invoices WHERE business_id=? "
            "AND rectifies_invoice_id=? AND status='borrador' LIMIT 1",
            (business_id, original_invoice_id),
        ).fetchone()
        if pending:
            raise ValueError(
                "Ya existe una rectificativa en borrador para esta factura. "
                "Revísala antes de crear otra."
            )
        original = dict(current_original)
        if invoice_type == "R5" and original.get("invoice_type") != "F2":
            raise ValueError("R5 solo puede rectificar una factura simplificada F2.")
        if invoice_type != "R5" and original.get("invoice_type") == "F2":
            raise ValueError("Una factura simplificada F2 debe rectificarse como R5.")
        if series_id is None:
            series = _ensure_default_invoice_series(
                conn, business_id, "rectifying"
            )
            series_id = series["id"]
        else:
            series = conn.execute(
                "SELECT * FROM invoice_series WHERE id=? AND business_id=? "
                "AND document_type='rectifying' AND active=TRUE",
                (series_id, business_id),
            ).fetchone()
            if not series:
                raise ValueError("La serie rectificativa no es válida.")
        row = conn.execute(
            "INSERT INTO invoices (business_id, client_id, concept, base, vat_rate, "
            "vat_amount, irpf_rate, irpf_amount, total, status, invoice_type, "
            "rectifies_invoice_id, rectification_type, rectification_reason, "
            "series_id, currency, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "'borrador', ?, ?, ?, ?, ?, 'EUR', ?) RETURNING id",
            (
                business_id, original["client_id"], concept, totals["base"],
                totals["vat_rate"], totals["vat_amount"], totals["irpf_rate"],
                totals["irpf_amount"], totals["total"], invoice_type,
                original_invoice_id, rectification_type, reason, series_id, _now(),
            ),
        ).fetchone()
        new_id = row["id"]
        created_at = _now()
        for line in normalized:
            conn.execute(
                "INSERT INTO invoice_lines "
                "(business_id, invoice_id, position, description, quantity, "
                "unit_price, discount_rate, vat_rate, base, vat_amount, total, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    business_id, new_id, line["position"], line["description"],
                    line["quantity"], line["unit_price"], line["discount_rate"],
                    line["vat_rate"], line["base"], line["vat_amount"],
                    line["total"], created_at,
                ),
            )
    return get_invoice(new_id, business_id)


def update_rectifying_invoice_draft(
    invoice_id: int,
    business_id: int,
    *,
    concept: str,
    base,
    vat_rate=config.DEFAULT_VAT_RATE,
    irpf_rate=0,
    invoice_type: str = "R1",
    rectification_type: str = "I",
    reason: str,
    lines=None,
    series_id: int | None = None,
) -> dict:
    """Revisa un borrador rectificativo sin alterar la factura original."""
    invoice_type = (invoice_type or "").strip().upper()
    if invoice_type not in {"R1", "R2", "R3", "R4", "R5"}:
        raise ValueError("El tipo de factura rectificativa no es válido.")
    rectification_type = (rectification_type or "").strip().upper()
    if rectification_type != "I":
        raise ValueError(
            "Noesis solo prepara rectificativas por diferencias. "
            "La rectificación por sustitución requiere revisión fiscal."
        )
    concept = (concept or "").strip()
    reason = (reason or "").strip()
    if not concept or len(concept) > 500:
        raise ValueError("El concepto es obligatorio y no puede superar 500 caracteres.")
    if len(reason) < 3 or len(reason) > 1000:
        raise ValueError("El motivo de rectificación es obligatorio.")
    normalized = _normalize_invoice_lines(
        lines,
        fallback_concept=concept,
        fallback_base=base,
        fallback_vat=vat_rate,
        allow_negative=True,
    )
    totals = _invoice_totals(normalized, irpf_rate)
    if totals["base"] == 0:
        raise ValueError("La base rectificada debe ser distinta de cero.")
    concept = normalized[0]["description"]
    if len(normalized) > 1:
        concept = f"{concept} y {len(normalized) - 1} línea(s) más"

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        current = conn.execute(
            "SELECT * FROM invoices WHERE id=? AND business_id=?" + lock,
            (invoice_id, business_id),
        ).fetchone()
        if not current:
            raise ValueError("Factura rectificativa no encontrada.")
        if (
            current["status"] != "borrador"
            or current.get("number")
            or not current.get("rectifies_invoice_id")
            or not str(current.get("invoice_type") or "").startswith("R")
        ):
            raise ValueError("Solo puede editarse un borrador rectificativo.")
        original = conn.execute(
            "SELECT * FROM invoices WHERE id=? AND business_id=?",
            (current["rectifies_invoice_id"], business_id),
        ).fetchone()
        if not original or original["status"] not in {"enviada", "parcial", "cobrada"}:
            raise ValueError("La factura original ya no puede rectificarse.")
        if invoice_type == "R5" and original.get("invoice_type") != "F2":
            raise ValueError("R5 solo puede rectificar una factura simplificada F2.")
        if invoice_type != "R5" and original.get("invoice_type") == "F2":
            raise ValueError("Una factura simplificada F2 debe rectificarse como R5.")
        cancelled = conn.execute(
            "SELECT 1 FROM invoice_cancellation_records "
            "WHERE invoice_id=? AND business_id=? LIMIT 1",
            (original["id"], business_id),
        ).fetchone()
        if cancelled:
            raise ValueError(
                "El registro fiscal de la factura original está anulado."
            )
        if series_id is None:
            series = _ensure_default_invoice_series(conn, business_id, "rectifying")
            series_id = series["id"]
        else:
            series = conn.execute(
                "SELECT * FROM invoice_series WHERE id=? AND business_id=? "
                "AND document_type='rectifying' AND active=TRUE",
                (series_id, business_id),
            ).fetchone()
            if not series:
                raise ValueError("La serie rectificativa no es válida.")
        conn.execute(
            "UPDATE invoices SET concept=?, base=?, vat_rate=?, vat_amount=?, "
            "irpf_rate=?, irpf_amount=?, total=?, invoice_type=?, "
            "rectification_type=?, rectification_reason=?, series_id=? "
            "WHERE id=? AND business_id=? AND status='borrador'",
            (
                concept, totals["base"], totals["vat_rate"], totals["vat_amount"],
                totals["irpf_rate"], totals["irpf_amount"], totals["total"],
                invoice_type, rectification_type, reason, series_id,
                invoice_id, business_id,
            ),
        )
        conn.execute(
            "DELETE FROM invoice_lines WHERE invoice_id=? AND business_id=?",
            (invoice_id, business_id),
        )
        created_at = _now()
        for line in normalized:
            conn.execute(
                "INSERT INTO invoice_lines "
                "(business_id, invoice_id, position, description, quantity, "
                "unit_price, discount_rate, vat_rate, base, vat_amount, total, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    business_id, invoice_id, line["position"], line["description"],
                    line["quantity"], line["unit_price"], line["discount_rate"],
                    line["vat_rate"], line["base"], line["vat_amount"],
                    line["total"], created_at,
                ),
            )
    return get_invoice(invoice_id, business_id)


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
        if not row:
            return None
        lines = conn.execute(
            "SELECT * FROM invoice_lines WHERE invoice_id=? AND business_id=? "
            "ORDER BY position, id",
            (invoice_id, business_id),
        ).fetchall()
        result = _invoice_payment_state(row)
        result["lines"] = [dict(line) for line in lines]
        return result


def find_invoice_reference(reference, business_id: int) -> dict | None:
    """Resuelve el id interno o el número visible de una factura del negocio."""
    value = str(reference or "").strip().lstrip("#").strip()
    value = re.sub(r"^factura\s+", "", value, flags=re.I).strip()
    if not value:
        return None
    if value.isdigit():
        invoice = get_invoice(int(value), business_id)
        if invoice:
            return invoice
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM invoices WHERE business_id=? "
            "AND LOWER(COALESCE(number,''))=LOWER(?) ORDER BY id DESC LIMIT 1",
            (business_id, value),
        ).fetchone()
    return get_invoice(row["id"], business_id) if row else None


def get_invoice_lines(invoice_id: int, business_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM invoice_lines WHERE invoice_id=? AND business_id=? "
            "ORDER BY position, id",
            (invoice_id, business_id),
        ).fetchall()
        return [dict(row) for row in rows]


def update_invoice_draft(
    invoice_id: int,
    business_id: int,
    *,
    client_id: int,
    lines,
    irpf_rate=0,
    invoice_type: str = "F1",
    series_id: int | None = None,
    operation_date: str | None = None,
    notes: str | None = None,
    payment_method: str | None = None,
    legal_mention: str | None = None,
) -> dict:
    if not get_client(client_id, business_id):
        raise ValueError("El cliente no pertenece a este negocio.")
    invoice_type = (invoice_type or "F1").strip().upper()
    if invoice_type not in {"F1", "F2"}:
        raise ValueError("El tipo de factura no es válido para este borrador.")
    normalized = _normalize_invoice_lines(lines)
    totals = _invoice_totals(normalized, irpf_rate)
    if operation_date:
        try:
            operation_date = date.fromisoformat(str(operation_date)).isoformat()
        except ValueError as exc:
            raise ValueError("La fecha de operación no es válida.") from exc
    notes = (notes or "").strip() or None
    payment_method = (payment_method or "").strip() or None
    legal_mention = (legal_mention or "").strip() or None
    for value, label, maximum in (
        (notes, "Las notas", 2000),
        (payment_method, "La forma de pago", 120),
        (legal_mention, "La mención legal", 500),
    ):
        if value and len(value) > maximum:
            raise ValueError(f"{label} supera {maximum} caracteres.")
    concept = normalized[0]["description"]
    if len(normalized) > 1:
        concept = f"{concept} y {len(normalized) - 1} línea(s) más"
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        current = conn.execute(
            "SELECT * FROM invoices WHERE id=? AND business_id=?" + lock,
            (invoice_id, business_id),
        ).fetchone()
        if not current:
            raise ValueError("Factura no encontrada.")
        if current["status"] != "borrador" or current.get("number"):
            raise ValueError("Una factura emitida no puede editarse.")
        expected_type = _series_document_type(invoice_type)
        if series_id is None:
            series = _ensure_default_invoice_series(conn, business_id, expected_type)
            series_id = series["id"]
        else:
            series = conn.execute(
                "SELECT * FROM invoice_series WHERE id=? AND business_id=? "
                "AND active=TRUE",
                (series_id, business_id),
            ).fetchone()
            if not series or series["document_type"] != expected_type:
                raise ValueError("La serie no corresponde al tipo de factura.")
        conn.execute(
            "UPDATE invoices SET client_id=?, concept=?, base=?, vat_rate=?, "
            "vat_amount=?, irpf_rate=?, irpf_amount=?, total=?, invoice_type=?, "
            "series_id=?, operation_date=?, notes=?, payment_method=?, "
            "legal_mention=? WHERE id=? AND business_id=? AND status='borrador'",
            (
                client_id, concept, totals["base"], totals["vat_rate"],
                totals["vat_amount"], totals["irpf_rate"],
                totals["irpf_amount"], totals["total"], invoice_type, series_id,
                operation_date, notes, payment_method, legal_mention,
                invoice_id, business_id,
            ),
        )
        conn.execute(
            "DELETE FROM invoice_lines WHERE invoice_id=? AND business_id=?",
            (invoice_id, business_id),
        )
        created_at = _now()
        for line in normalized:
            conn.execute(
                "INSERT INTO invoice_lines "
                "(business_id, invoice_id, position, description, quantity, "
                "unit_price, discount_rate, vat_rate, base, vat_amount, total, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    business_id, invoice_id, line["position"], line["description"],
                    line["quantity"], line["unit_price"], line["discount_rate"],
                    line["vat_rate"], line["base"], line["vat_amount"],
                    line["total"], created_at,
                ),
            )
    return get_invoice(invoice_id, business_id)


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
        "vo.aeat_error_description AS verifactu_error, s.name AS series_name, "
        "original.number AS rectified_number, "
        "original.issued_at AS rectified_issued_at, "
        "(SELECT pending.id FROM invoices pending WHERE "
        "pending.business_id=i.business_id AND pending.rectifies_invoice_id=i.id "
        "AND pending.status='borrador' ORDER BY pending.id DESC LIMIT 1) "
        "AS pending_rectification_id, "
        "(SELECT co.status FROM verifactu_cancellation_outbox co WHERE "
        "co.business_id=i.business_id AND co.invoice_id=i.id "
        "ORDER BY co.id DESC LIMIT 1) AS cancellation_status, "
        "(SELECT COUNT(*) FROM invoice_lines il WHERE "
        "il.business_id=i.business_id AND il.invoice_id=i.id) AS line_count "
        "FROM invoices i "
        "LEFT JOIN clients c ON c.id = i.client_id AND c.business_id=i.business_id "
        "LEFT JOIN verifactu_outbox vo ON vo.invoice_id=i.id "
        "AND vo.business_id=i.business_id "
        "LEFT JOIN invoice_series s ON s.id=i.series_id "
        "AND s.business_id=i.business_id "
        "LEFT JOIN invoices original ON original.id=i.rectifies_invoice_id "
        "AND original.business_id=i.business_id "
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


def _advance_recurring_day(day: date, cadence: str, interval_count: int) -> date:
    if cadence == "weekly":
        return day + timedelta(weeks=interval_count)
    months = interval_count * {
        "monthly": 1, "quarterly": 3, "annual": 12,
    }[cadence]
    target_month = day.month - 1 + months
    year = day.year + target_month // 12
    month = target_month % 12 + 1
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    last_day = (next_month - timedelta(days=1)).day
    return date(year, month, min(day.day, last_day))


def add_recurring_invoice(
    business_id: int,
    client_id: int,
    *,
    name: str,
    cadence: str,
    next_run_on: str,
    lines,
    interval_count: int = 1,
    ends_on: str | None = None,
    auto_issue: bool = False,
    irpf_rate=0,
    invoice_type: str = "F1",
    series_id: int | None = None,
    notes: str | None = None,
    payment_method: str | None = None,
) -> dict:
    if not get_client(client_id, business_id):
        raise ValueError("El cliente no pertenece a este negocio.")
    name = (name or "").strip()
    cadence = (cadence or "").strip().lower()
    if not 1 <= len(name) <= 120:
        raise ValueError("Pon un nombre a la programación.")
    if cadence not in {"weekly", "monthly", "quarterly", "annual"}:
        raise ValueError("La frecuencia no es válida.")
    try:
        interval_count = int(interval_count)
        start = date.fromisoformat(str(next_run_on))
        end = date.fromisoformat(str(ends_on)) if ends_on else None
    except (TypeError, ValueError) as exc:
        raise ValueError("Las fechas o el intervalo no son válidos.") from exc
    if not 1 <= interval_count <= 24:
        raise ValueError("El intervalo debe estar entre 1 y 24.")
    if end and end < start:
        raise ValueError("La fecha final no puede ser anterior al primer día.")
    invoice_type = (invoice_type or "F1").strip().upper()
    if invoice_type not in {"F1", "F2"}:
        raise ValueError("El tipo de factura programada no es válido.")
    normalized = _normalize_invoice_lines(lines)
    _invoice_totals(normalized, irpf_rate)
    now = _now()
    with get_conn() as conn:
        if series_id is not None:
            series = conn.execute(
                "SELECT * FROM invoice_series WHERE id=? AND business_id=? "
                "AND active=TRUE",
                (series_id, business_id),
            ).fetchone()
            if (
                not series
                or series["document_type"] != _series_document_type(invoice_type)
            ):
                raise ValueError("La serie no corresponde al tipo de factura.")
        row = conn.execute(
            "INSERT INTO recurring_invoices "
            "(business_id, client_id, name, cadence, interval_count, next_run_on, "
            "ends_on, auto_issue, status, lines_json, irpf_rate, invoice_type, "
            "series_id, notes, payment_method, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?) "
            "RETURNING id",
            (
                business_id, client_id, name, cadence, interval_count,
                start.isoformat(), end.isoformat() if end else None,
                bool(auto_issue), json.dumps(normalized, ensure_ascii=False),
                _tax_rate(irpf_rate, "El IRPF", {0, 7, 15}), invoice_type,
                series_id, (notes or "").strip() or None,
                (payment_method or "").strip() or None, now, now,
            ),
        ).fetchone()
    return get_recurring_invoice(row["id"], business_id)


def get_recurring_invoice(recurring_id: int, business_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT r.*, c.name AS client_name FROM recurring_invoices r "
            "JOIN clients c ON c.id=r.client_id AND c.business_id=r.business_id "
            "WHERE r.id=? AND r.business_id=?",
            (recurring_id, business_id),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["lines"] = json.loads(result.pop("lines_json"))
    return result


def list_recurring_invoices(business_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT r.*, c.name AS client_name FROM recurring_invoices r "
            "JOIN clients c ON c.id=r.client_id AND c.business_id=r.business_id "
            "WHERE r.business_id=? ORDER BY r.status, r.next_run_on, r.id",
            (business_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["lines"] = json.loads(item.pop("lines_json"))
        result.append(item)
    return result


def set_recurring_invoice_status(
    recurring_id: int, business_id: int, status: str
) -> dict | None:
    if status not in {"active", "paused", "ended"}:
        raise ValueError("El estado de la programación no es válido.")
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE recurring_invoices SET status=?, updated_at=? "
            "WHERE id=? AND business_id=?",
            (status, _now(), recurring_id, business_id),
        )
    return (
        get_recurring_invoice(recurring_id, business_id)
        if cursor.rowcount else None
    )


def process_due_recurring_invoices(
    *, today: date | None = None, limit: int = 100
) -> list[dict]:
    """Genera una vez cada vencimiento; emitir automáticamente es opt-in."""
    today = today or date.today()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT r.* FROM recurring_invoices r JOIN businesses b "
            "ON b.id=r.business_id WHERE r.status='active' "
            "AND r.next_run_on<=? ORDER BY r.next_run_on, r.id LIMIT ?",
            (today.isoformat(), max(1, min(int(limit), 500))),
        ).fetchall()
    generated = []
    for raw in rows:
        schedule = dict(raw)
        business = get_business(schedule["business_id"])
        if not business or not subscription_allows_access(business):
            continue
        scheduled_for = schedule["next_run_on"]
        now = _now()
        stale_before = (datetime.now() - timedelta(minutes=10)).isoformat(
            timespec="seconds"
        )
        with get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            run = conn.execute(
                "INSERT INTO recurring_invoice_runs "
                "(business_id, recurring_id, scheduled_for, status, created_at) "
                "VALUES (?, ?, ?, 'processing', ?) "
                "ON CONFLICT (business_id, recurring_id, scheduled_for) DO NOTHING "
                "RETURNING id",
                (
                    schedule["business_id"], schedule["id"], scheduled_for, now,
                ),
            ).fetchone()
            if not run:
                run = conn.execute(
                    "UPDATE recurring_invoice_runs SET created_at=?, error=NULL, "
                    "status='processing' WHERE business_id=? AND recurring_id=? "
                    "AND scheduled_for=? AND invoice_id IS NULL AND "
                    "(status='error' OR created_at<=?) RETURNING id",
                    (
                        now, schedule["business_id"], schedule["id"],
                        scheduled_for, stale_before,
                    ),
                ).fetchone()
            if not run:
                continue
        try:
            lines = json.loads(schedule["lines_json"])
            invoice = add_invoice(
                schedule["client_id"],
                lines[0]["description"],
                None,
                business_id=schedule["business_id"],
                lines=lines,
                irpf_rate=schedule["irpf_rate"],
                invoice_type=schedule["invoice_type"],
                series_id=schedule.get("series_id"),
                operation_date=scheduled_for,
                notes=schedule.get("notes"),
                payment_method=schedule.get("payment_method"),
            )
            if schedule.get("auto_issue"):
                invoice = issue_invoice(invoice["id"], schedule["business_id"])
            next_day = _advance_recurring_day(
                date.fromisoformat(scheduled_for),
                schedule["cadence"],
                int(schedule["interval_count"]),
            )
            end = date.fromisoformat(schedule["ends_on"]) if schedule.get("ends_on") else None
            next_status = "ended" if end and next_day > end else "active"
            completed_at = _now()
            with get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "UPDATE recurring_invoice_runs SET invoice_id=?, status='completed', "
                    "completed_at=? WHERE id=? AND business_id=?",
                    (
                        invoice["id"], completed_at, run["id"],
                        schedule["business_id"],
                    ),
                )
                conn.execute(
                    "UPDATE recurring_invoices SET next_run_on=?, status=?, "
                    "last_generated_at=?, updated_at=? WHERE id=? AND business_id=?",
                    (
                        next_day.isoformat(), next_status, completed_at,
                        completed_at, schedule["id"], schedule["business_id"],
                    ),
                )
            generated.append(invoice)
        except Exception as exc:  # noqa: BLE001 - deja el fallo trazable y reintentable.
            with get_conn() as conn:
                conn.execute(
                    "UPDATE recurring_invoice_runs SET status='error', error=? "
                    "WHERE id=? AND business_id=?",
                    (str(exc)[:1500], run["id"], schedule["business_id"]),
                )
            log.exception("No se pudo generar la factura recurrente %s", schedule["id"])
    return generated


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


def _next_invoice_series_number(conn, business_id: int, series_id: int) -> str:
    lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
    series = conn.execute(
        "SELECT * FROM invoice_series WHERE id=? AND business_id=? "
        "AND active=TRUE" + lock,
        (series_id, business_id),
    ).fetchone()
    if not series:
        raise ValueError("La serie de numeración no está disponible.")
    year = date.today().year
    prefix = series["prefix_template"].replace("{YYYY}", str(year))
    existing = conn.execute(
        "SELECT number FROM invoices WHERE business_id=? AND number LIKE ?",
        (business_id, f"{prefix}%"),
    ).fetchall()
    used = []
    for item in existing:
        suffix = str(item["number"])[len(prefix):]
        if suffix.isdigit():
            used.append(int(suffix))
    initial = max(used, default=0) + 1
    sequence_kind = f"invoice_series:{series_id}"
    row = conn.execute(
        "INSERT INTO document_sequences (business_id, kind, year, last_number) "
        "VALUES (?, ?, ?, ?) ON CONFLICT (business_id, kind, year) DO UPDATE "
        "SET last_number=document_sequences.last_number+1 RETURNING last_number",
        (business_id, sequence_kind, year, initial),
    ).fetchone()
    number = int(row["last_number"])
    return f"{prefix}{number:0{int(series['padding'])}d}"


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


def _fiscal_record_rows(
    conn, business_id: int, issuer_nif: str | None = None
) -> list[dict]:
    """Une altas y anulaciones en el orden cronológico de una sola cadena."""
    where = "business_id=?"
    params: list = [business_id]
    if issuer_nif:
        where += " AND issuer_nif=?"
        params.append(issuer_nif.strip().upper())
    records = [
        dict(row) for row in conn.execute(
            f"SELECT * FROM invoice_records WHERE {where}", params
        ).fetchall()
    ]
    cancellations = [
        dict(row) for row in conn.execute(
            f"SELECT * FROM invoice_cancellation_records WHERE {where}", params
        ).fetchall()
    ]
    records.extend(cancellations)
    records.sort(
        key=lambda item: (
            str(item.get("generated_at") or ""),
            0 if item.get("record_type") == "alta" else 1,
            int(item["id"]),
        )
    )
    return records


def _verify_invoice_record_rows(records: list[dict]) -> dict:
    """Verifica una cadena ya ordenada sin abrir otra conexión a la BD."""
    previous_by_issuer: dict[str, dict] = {}
    last_record = None
    for index, record in enumerate(records):
        previous = previous_by_issuer.get(record["issuer_nif"])
        previous_hash = previous["record_hash"] if previous else None
        if record.get("record_type") == "anulacion":
            expected = verifactu.cancellation_record_hash(
                algorithm=record["hash_algorithm"],
                issuer_nif=record["issuer_nif"],
                invoice_number=record["invoice_number"],
                issue_date=record["issue_date"],
                previous_hash=previous_hash,
                generated_at=record["generated_at"],
            )
        else:
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
                "broken_record_type": record.get("record_type") or "alta",
                "expected_hash": expected,
                "stored_hash": record.get("record_hash"),
            }
        previous_by_issuer[record["issuer_nif"]] = record
        last_record = record
    return {
        "valid": True,
        "checked": len(records),
        "broken_at": None,
        "broken_record_type": None,
        "last_hash": last_record["record_hash"] if last_record else None,
    }


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
    invoice_type = (invoice.get("invoice_type") or "F1").strip().upper()
    recipient_nif = (invoice.get("recipient_nif") or "").strip().upper()
    if invoice_type != "F2" or recipient_nif:
        recipient_nif = _verifactu_nif(
            recipient_nif, "El NIF del destinatario"
        )
    producer_nif = _verifactu_nif(
        config.VERIFACTU_PRODUCER_NIF, "El NIF del productor"
    )
    issuer_name = (invoice["issuer_name"] or "").strip()
    recipient_name = (invoice.get("recipient_name") or "").strip()
    if not 1 <= len(issuer_name) <= 120:
        raise ValueError("El nombre fiscal del emisor supera 120 caracteres.")
    if invoice_type != "F2" and not 1 <= len(recipient_name) <= 120:
        raise ValueError("El nombre fiscal del destinatario supera 120 caracteres.")
    if invoice_type not in _VERIFACTU_INVOICE_TYPES:
        raise ValueError("El tipo de factura no es válido para Veri*Factu.")
    issue_date = verifactu.aeat_date(invoice["issued_at"])
    generated_at = verifactu.generated_at_with_timezone()
    existing_chain = _fiscal_record_rows(conn, business_id, issuer_nif)
    integrity = _verify_invoice_record_rows(existing_chain)
    if not integrity["valid"]:
        raise ValueError(
            "La cadena Veri*Factu existente presenta una anomalía; "
            "la factura no se ha emitido."
        )
    previous = existing_chain[-1] if existing_chain else None
    if previous:
        try:
            previous_time = datetime.fromisoformat(previous["generated_at"])
            current_time = datetime.fromisoformat(generated_at)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "La fecha del último registro Veri*Factu no es válida."
            ) from exc
        if current_time < previous_time - timedelta(minutes=1):
            raise ValueError(
                "El reloj del sistema retrocede respecto al último registro "
                "Veri*Factu; revisa la sincronización horaria."
            )
        if current_time <= previous_time:
            generated_at = (previous_time + timedelta(milliseconds=1)).isoformat(
                timespec="milliseconds"
            )
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
    invoice_lines = conn.execute(
        "SELECT * FROM invoice_lines WHERE business_id=? AND invoice_id=? "
        "ORDER BY position, id",
        (business_id, invoice_id),
    ).fetchall()
    grouped: dict[float, dict[str, Decimal]] = {}
    for line in invoice_lines:
        rate = float(line["vat_rate"])
        target = grouped.setdefault(
            rate, {"base": Decimal("0"), "vat_amount": Decimal("0")}
        )
        target["base"] += Decimal(str(line["base"]))
        target["vat_amount"] += Decimal(str(line["vat_amount"]))
    if not grouped:
        grouped[float(invoice["vat_rate"])] = {
            "base": Decimal(str(invoice["base"])),
            "vat_amount": Decimal(str(invoice["vat_amount"])),
        }
    breakdown = json.dumps(
        [
            {
                "vat_rate": rate,
                "base": float(values["base"].quantize(Decimal("0.01"))),
                "vat_amount": float(
                    values["vat_amount"].quantize(Decimal("0.01"))
                ),
            }
            for rate, values in sorted(grouped.items())
        ],
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
        "operation_date, recipient_nif, recipient_name, description, breakdown_json, vat_total, "
        "invoice_total, generated_at, previous_record_id, previous_issuer_nif, "
        "previous_invoice_number, previous_issue_date, previous_hash, "
        "hash_algorithm, hash_type, hash_spec_version, record_hash, qr_url, "
        "producer_name, producer_nif, system_name, system_id, system_version, "
        "installation_id, created_at) VALUES ("
        "?, ?, 'alta', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (
            business_id, invoice_id, config.VERIFACTU_RECORD_VERSION, invoice_type,
            invoice.get("rectification_type"),
            issuer_nif if rectified else None,
            rectified["number"] if rectified else None,
            verifactu.aeat_date(rectified["issued_at"]) if rectified else None,
            issuer_nif, issuer_name, invoice["number"], issue_date,
            verifactu.aeat_date(invoice["operation_date"])
            if invoice.get("operation_date") else None,
            recipient_nif, recipient_name, invoice["concept"].strip(), breakdown,
            invoice["vat_amount"], invoice["total"], generated_at,
            previous["id"] if previous and previous.get("record_type") == "alta" else None,
            previous["issuer_nif"] if previous else None,
            previous["invoice_number"] if previous else None,
            previous["issue_date"] if previous else None,
            previous_hash, config.VERIFACTU_HASH_ALGORITHM,
            config.VERIFACTU_HASH_TYPE, config.VERIFACTU_HASH_SPEC_VERSION,
            record_hash, invoice_qr_url, config.VERIFACTU_PRODUCER_NAME.strip(),
            producer_nif, config.VERIFACTU_SYSTEM_NAME,
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


def issue_invoice(
    invoice_id: int,
    business_id: int,
    payment_term_days: int | None = None,
    *,
    _issued_at_override: str | None = None,
) -> dict:
    """Emite una factura una sola vez, numera y congela sus datos fiscales.

    ``_issued_at_override`` existe únicamente para construir cuentas demo con
    historia coherente. No se expone en las rutas de producto.
    """
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        inv = conn.execute(
            "SELECT * FROM invoices WHERE id=? AND business_id=?" + lock,
            (invoice_id, business_id),
        ).fetchone()
        if not inv:
            raise ValueError("No existe esa factura.")
        if inv.get("source") == "importada":
            raise ValueError(
                "Una factura importada es histórica: no se puede emitir ni "
                "entrar en la cadena Veri*Factu."
            )
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
        invoice_type = (inv.get("invoice_type") or "F1").upper()
        missing = []
        required = [
            (biz["name"], "nombre fiscal del negocio"),
            (biz["nif"], "NIF del negocio"),
            (biz["address"], "domicilio del negocio"),
            (client["name"], "nombre del cliente"),
        ]
        if invoice_type != "F2":
            required.extend((
                (client["nif"], "NIF del cliente"),
                (client["address"], "domicilio del cliente"),
            ))
        for value, label in required:
            if not (value or "").strip():
                missing.append(label)
        if missing:
            raise ValueError(
                "Antes de emitir completa: " + ", ".join(missing) + "."
            )
        lines = [dict(row) for row in conn.execute(
            "SELECT * FROM invoice_lines WHERE business_id=? AND invoice_id=? "
            "ORDER BY position, id",
            (business_id, invoice_id),
        ).fetchall()]
        if not lines:
            raise ValueError("La factura no contiene ninguna línea.")
        totals = _invoice_totals(lines, inv.get("irpf_rate") or 0)
        for key in ("base", "vat_amount", "irpf_amount", "total"):
            if Decimal(str(totals[key])).quantize(Decimal("0.01")) != Decimal(
                str(inv[key])
            ).quantize(Decimal("0.01")):
                raise ValueError(
                    "Los totales del borrador no coinciden con sus líneas; "
                    "revísalo antes de emitir."
                )
        if invoice_type == "F2" and Decimal(str(inv["total"])) > Decimal("400"):
            raise ValueError(
                "La factura simplificada supera el límite general de 400 €. "
                "Emítela como factura completa con los datos fiscales del cliente."
            )
        expected_document_type = _series_document_type(invoice_type)
        series = conn.execute(
            "SELECT * FROM invoice_series WHERE id=? AND business_id=? AND active=TRUE",
            (inv.get("series_id"), business_id),
        ).fetchone()
        if not series:
            series = _ensure_default_invoice_series(
                conn, business_id, expected_document_type
            )
            conn.execute(
                "UPDATE invoices SET series_id=? WHERE id=? AND business_id=?",
                (series["id"], invoice_id, business_id),
            )
        if series["document_type"] != expected_document_type:
            raise ValueError("La serie no corresponde al tipo de factura.")
        number = _next_invoice_series_number(conn, business_id, series["id"])
        if _issued_at_override:
            try:
                issued_day = date.fromisoformat(str(_issued_at_override)[:10])
            except ValueError as exc:
                raise ValueError("La fecha de emisión demo no es válida.") from exc
            if issued_day > date.today():
                raise ValueError("La fecha de emisión demo no puede ser futura.")
            issued_at = f"{issued_day.isoformat()}T12:00:00"
        else:
            issued_at = _now()
            issued_day = date.today()
        if inv.get("operation_date"):
            try:
                operation_day = date.fromisoformat(inv["operation_date"])
            except ValueError as exc:
                raise ValueError("La fecha de operación del borrador no es válida.") from exc
            if operation_day > date.today():
                raise ValueError("La fecha de operación no puede estar en el futuro.")
        if payment_term_days is None:
            configured_term = biz.get("default_payment_term_days")
            payment_term_days = int(
                15 if configured_term is None else configured_term
            )
        due_date = (
            issued_day + timedelta(days=max(0, min(payment_term_days, 365)))
        ).isoformat()
        document_profile = _ensure_current_document_profile(conn, dict(biz))
        conn.execute(
            "UPDATE invoices SET status='enviada', number=?, issued_at=?, due_date=?, "
            "issuer_name=?, issuer_nif=?, issuer_address=?, recipient_name=?, "
            "recipient_nif=?, recipient_address=?, document_profile_id=? "
            "WHERE id=? AND business_id=? AND status='borrador'",
            (
                number, issued_at, due_date, biz["name"], biz["nif"], biz["address"],
                client["name"], client.get("nif"), client.get("address"),
                document_profile["id"], invoice_id, business_id,
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
        else:
            _record_invoice_event(
                conn, business_id, "emision", invoice_id=invoice_id,
                details=f"numero={number}", created_at=issued_at,
            )
    return get_invoice(invoice_id, business_id)


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
        _record_invoice_event(
            conn, business_id, "cobro", invoice_id=invoice_id,
            details=(
                f"importe={float(amount_decimal):.2f};"
                f"metodo={method or 'no indicado'}"
            ),
            created_at=paid_at,
        )
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
            _record_invoice_event(
                conn, business_id, "cobro", invoice_id=invoice_id,
                details=f"importe={float(remaining):.2f};metodo=no indicado",
                created_at=payment_time,
            )
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


def get_invoice_cancellation_record(
    invoice_id: int, business_id: int
) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM invoice_cancellation_records "
            "WHERE invoice_id=? AND business_id=?",
            (invoice_id, business_id),
        ).fetchone()
        return dict(row) if row else None


def get_verifactu_cancellation_outbox(
    invoice_id: int, business_id: int
) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM verifactu_cancellation_outbox "
            "WHERE invoice_id=? AND business_id=?",
            (invoice_id, business_id),
        ).fetchone()
        return dict(row) if row else None


def create_invoice_cancellation_record(
    invoice_id: int, business_id: int, *, reason: str
) -> dict:
    """Anula ante la AEAT un alta aceptada sin borrar ni alterar la factura."""
    reason = (reason or "").strip()
    if not 5 <= len(reason) <= 1000:
        raise ValueError("Explica el motivo de la anulación (5 a 1.000 caracteres).")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT * FROM invoice_cancellation_records "
            "WHERE invoice_id=? AND business_id=?",
            (invoice_id, business_id),
        ).fetchone()
        if existing:
            return dict(existing)
        invoice = conn.execute(
            "SELECT * FROM invoices WHERE id=? AND business_id=?",
            (invoice_id, business_id),
        ).fetchone()
        original = conn.execute(
            "SELECT * FROM invoice_records WHERE invoice_id=? AND business_id=?",
            (invoice_id, business_id),
        ).fetchone()
        outbox = conn.execute(
            "SELECT * FROM verifactu_outbox WHERE invoice_id=? AND business_id=?",
            (invoice_id, business_id),
        ).fetchone()
        if not invoice or not original:
            raise ValueError(
                "Solo se puede anular un registro Veri*Factu ya generado."
            )
        if not outbox or outbox["status"] not in {
            "aceptado", "aceptado_con_errores"
        }:
            raise ValueError(
                "La anulación requiere que el alta haya sido aceptada por la AEAT."
            )
        issuer_nif = original["issuer_nif"]
        chain = _fiscal_record_rows(conn, business_id, issuer_nif)
        integrity = _verify_invoice_record_rows(chain)
        if not integrity["valid"]:
            raise ValueError(
                "La cadena Veri*Factu presenta una anomalía; no se ha anulado."
            )
        previous = chain[-1] if chain else None
        generated_at = verifactu.generated_at_with_timezone()
        if previous:
            previous_time = datetime.fromisoformat(previous["generated_at"])
            current_time = datetime.fromisoformat(generated_at)
            if current_time < previous_time - timedelta(minutes=1):
                raise ValueError(
                    "El reloj del sistema retrocede respecto al último registro."
                )
            if current_time <= previous_time:
                generated_at = (
                    previous_time + timedelta(milliseconds=1)
                ).isoformat(timespec="milliseconds")
        previous_hash = previous["record_hash"] if previous else None
        record_hash = verifactu.cancellation_record_hash(
            issuer_nif=issuer_nif,
            invoice_number=original["invoice_number"],
            issue_date=original["issue_date"],
            previous_hash=previous_hash,
            generated_at=generated_at,
        )
        row = conn.execute(
            "INSERT INTO invoice_cancellation_records ("
            "business_id, invoice_id, original_record_id, record_type, "
            "record_version, issuer_nif, issuer_name, invoice_number, issue_date, "
            "reason, generated_at, previous_record_type, previous_record_id, "
            "previous_issuer_nif, previous_invoice_number, previous_issue_date, "
            "previous_hash, hash_algorithm, hash_type, hash_spec_version, "
            "record_hash, producer_name, producer_nif, system_name, system_id, "
            "system_version, installation_id, created_at) VALUES ("
            "?, ?, ?, 'anulacion', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                business_id, invoice_id, original["id"],
                config.VERIFACTU_RECORD_VERSION, issuer_nif,
                original["issuer_name"], original["invoice_number"],
                original["issue_date"], reason, generated_at,
                previous.get("record_type") if previous else None,
                previous["id"] if previous else None,
                previous["issuer_nif"] if previous else None,
                previous["invoice_number"] if previous else None,
                previous["issue_date"] if previous else None,
                previous_hash, config.VERIFACTU_HASH_ALGORITHM,
                config.VERIFACTU_HASH_TYPE, config.VERIFACTU_HASH_SPEC_VERSION,
                record_hash, config.VERIFACTU_PRODUCER_NAME.strip(),
                config.VERIFACTU_PRODUCER_NIF.strip().upper(),
                config.VERIFACTU_SYSTEM_NAME, config.VERIFACTU_SYSTEM_ID,
                config.VERIFACTU_SYSTEM_VERSION,
                f"{config.VERIFACTU_INSTALLATION_PREFIX}-{business_id}",
                generated_at,
            ),
        ).fetchone()
        record_id = row["id"]
        queued_at = _now()
        conn.execute(
            "INSERT INTO verifactu_cancellation_outbox ("
            "business_id, invoice_id, record_id, status, attempts, max_attempts, "
            "next_attempt_at, created_at, updated_at) "
            "VALUES (?, ?, ?, 'pendiente', 0, ?, ?, ?, ?)",
            (
                business_id, invoice_id, record_id,
                config.VERIFACTU_MAX_ATTEMPTS, queued_at, queued_at, queued_at,
            ),
        )
        _record_invoice_event(
            conn, business_id, "anulacion", invoice_id=invoice_id,
            details=f"motivo={reason};huella={record_hash}",
            created_at=generated_at,
        )
        created = conn.execute(
            "SELECT * FROM invoice_cancellation_records "
            "WHERE id=? AND business_id=?",
            (record_id, business_id),
        ).fetchone()
        return dict(created)


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
        rows = _fiscal_record_rows(conn, business_id)
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


def list_invoice_events(
    business_id: int, invoice_id: int | None = None
) -> list[dict]:
    query = "SELECT * FROM invoice_events WHERE business_id=?"
    params: list = [business_id]
    if invoice_id is not None:
        query += " AND invoice_id=?"
        params.append(invoice_id)
    query += " ORDER BY id"
    with get_conn() as conn:
        rows = conn.execute(
            query,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def record_invoice_communication(
    invoice_id: int,
    business_id: int,
    event_type: str,
    details: str | None = None,
) -> None:
    if event_type not in {
        "entrega_preparada", "entrega_enviada", "visualizacion"
    }:
        raise ValueError("El evento de factura no es válido.")
    if not get_invoice(invoice_id, business_id):
        raise ValueError("Factura no encontrada.")
    with get_conn() as conn:
        _record_invoice_event(
            conn,
            business_id,
            event_type,
            invoice_id=invoice_id,
            details=(details or "")[:1500] or None,
        )


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
        claimed = conn.execute(
            "SELECT * FROM verifactu_outbox WHERE id=?", (row["id"],)
        ).fetchone()
        return dict(claimed)


def record_verifactu_submission_attempt(outbox_id: int, created_at: str) -> None:
    """Audita el intento justo antes de abrir la conexión con la AEAT."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM verifactu_outbox WHERE id=? AND status='enviado'",
            (outbox_id,),
        ).fetchone()
        if not row:
            return
        _record_invoice_event(
            conn,
            row["business_id"],
            "remision",
            invoice_id=row["invoice_id"],
            record_id=row["record_id"],
            details=f"intento={int(row['attempts'])}",
            created_at=created_at,
        )


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


def claim_next_verifactu_cancellation_submission(
    *, now: str, stale_before: str
) -> dict | None:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        suffix = " FOR UPDATE SKIP LOCKED" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT * FROM verifactu_cancellation_outbox "
            "WHERE attempts<max_attempts AND "
            "((status='pendiente' AND next_attempt_at<=?) OR "
            "(status='enviado' AND locked_at<=?)) "
            "ORDER BY next_attempt_at, id LIMIT 1" + suffix,
            (now, stale_before),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE verifactu_cancellation_outbox SET status='enviado', "
            "attempts=attempts+1, locked_at=?, sent_at=COALESCE(sent_at, ?), "
            "last_error=NULL, updated_at=? WHERE id=?",
            (now, now, now, row["id"]),
        )
        return dict(conn.execute(
            "SELECT * FROM verifactu_cancellation_outbox WHERE id=?",
            (row["id"],),
        ).fetchone())


def get_invoice_cancellation_record_by_id(
    record_id: int, business_id: int
) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM invoice_cancellation_records "
            "WHERE id=? AND business_id=?",
            (record_id, business_id),
        ).fetchone()
        return dict(row) if row else None


def record_verifactu_cancellation_attempt(
    outbox_id: int, created_at: str
) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM verifactu_cancellation_outbox "
            "WHERE id=? AND status='enviado'", (outbox_id,),
        ).fetchone()
        if row:
            _record_invoice_event(
                conn, row["business_id"], "remision",
                invoice_id=row["invoice_id"],
                details=f"anulacion;intento={int(row['attempts'])}",
                created_at=created_at,
            )


def mark_verifactu_cancellation_retry(
    outbox_id: int, *, error: str, next_attempt_at: str, updated_at: str
) -> dict | None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE verifactu_cancellation_outbox SET status='pendiente', "
            "next_attempt_at=?, last_error=?, locked_at=NULL, updated_at=? "
            "WHERE id=? AND status='enviado'",
            (next_attempt_at, error[:1500], updated_at, outbox_id),
        )
        row = conn.execute(
            "SELECT * FROM verifactu_cancellation_outbox WHERE id=?",
            (outbox_id,),
        ).fetchone()
        return dict(row) if row else None


def mark_verifactu_cancellation_result(
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
            "SELECT * FROM verifactu_cancellation_outbox WHERE id=?",
            (outbox_id,),
        ).fetchone()
        if not row or row["status"] != "enviado":
            return dict(row) if row else None
        conn.execute(
            "UPDATE verifactu_cancellation_outbox SET status=?, aeat_csv=?, "
            "aeat_global_status=?, aeat_error_code=?, "
            "aeat_error_description=?, aeat_response=?, wait_seconds=?, "
            "completed_at=?, locked_at=NULL, last_error=NULL, updated_at=? "
            "WHERE id=?",
            (
                status, csv, global_status, error_code, error_description,
                response, max(0, int(wait_seconds)), completed_at,
                completed_at, outbox_id,
            ),
        )
        _record_invoice_event(
            conn, row["business_id"],
            "rechazo" if status == "rechazado" else "aceptacion",
            invoice_id=row["invoice_id"],
            details=json.dumps(
                {
                    "operacion": "anulacion", "estado": status, "csv": csv,
                    "codigo_error": error_code,
                    "descripcion_error": error_description,
                },
                ensure_ascii=False, separators=(",", ":"),
            ),
            created_at=completed_at,
        )
        updated = conn.execute(
            "SELECT * FROM verifactu_cancellation_outbox WHERE id=?",
            (outbox_id,),
        ).fetchone()
        return dict(updated)


def postpone_verifactu_cancellations(until: str, updated_at: str) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE verifactu_cancellation_outbox SET next_attempt_at=?, "
            "updated_at=? WHERE status='pendiente' AND next_attempt_at<?",
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
            "SELECT status, COUNT(*) AS total FROM ("
            "SELECT status FROM verifactu_outbox UNION ALL "
            "SELECT status FROM verifactu_cancellation_outbox"
            ") fiscal_outbox GROUP BY status"
        ).fetchall()
        exhausted = conn.execute(
            "SELECT COUNT(*) AS total FROM ("
            "SELECT status, attempts, max_attempts FROM verifactu_outbox UNION ALL "
            "SELECT status, attempts, max_attempts FROM "
            "verifactu_cancellation_outbox) fiscal_outbox "
            "WHERE status='pendiente' AND attempts>=max_attempts"
        ).fetchone()
    for row in rows:
        counts[row["status"]] = int(row["total"])
    counts["agotado"] = int(exhausted["total"])
    return counts


def verifactu_queue_health(now: str | None = None) -> dict:
    """Resumen operativo de la cola AEAT para el panel interno.

    No procesa ni modifica la cola: solo cuenta vencidos, agotados y actividad
    reciente para saber si la remisión real se está atascando.
    """
    now = now or _now()
    counts = verifactu_queue_counts()
    with get_conn() as conn:
        due = conn.execute(
            "SELECT COUNT(*) AS total FROM ("
            "SELECT status, attempts, max_attempts, next_attempt_at "
            "FROM verifactu_outbox UNION ALL "
            "SELECT status, attempts, max_attempts, next_attempt_at "
            "FROM verifactu_cancellation_outbox) fiscal_outbox "
            "WHERE status='pendiente' AND attempts<max_attempts "
            "AND next_attempt_at<=?",
            (now,),
        ).fetchone()
        oldest = conn.execute(
            "SELECT MIN(next_attempt_at) AS next_attempt_at FROM ("
            "SELECT status, next_attempt_at FROM verifactu_outbox UNION ALL "
            "SELECT status, next_attempt_at FROM verifactu_cancellation_outbox"
            ") fiscal_outbox WHERE status='pendiente'",
        ).fetchone()
        activity = conn.execute(
            "SELECT MAX(updated_at) AS updated_at FROM ("
            "SELECT updated_at FROM verifactu_outbox UNION ALL "
            "SELECT updated_at FROM verifactu_cancellation_outbox"
            ") fiscal_outbox"
        ).fetchone()
        affected = conn.execute(
            "SELECT b.id, b.name, "
            "SUM(CASE WHEN o.status='pendiente' AND o.attempts>=o.max_attempts "
            "THEN 1 ELSE 0 END) AS agotadas, "
            "SUM(CASE WHEN o.status='rechazado' THEN 1 ELSE 0 END) AS rechazadas, "
            "SUM(CASE WHEN o.status='pendiente' AND o.attempts<o.max_attempts "
            "AND o.next_attempt_at<=? THEN 1 ELSE 0 END) AS vencidas "
            "FROM (SELECT business_id, status, attempts, max_attempts, "
            "next_attempt_at FROM verifactu_outbox UNION ALL "
            "SELECT business_id, status, attempts, max_attempts, "
            "next_attempt_at FROM verifactu_cancellation_outbox) o "
            "JOIN businesses b ON b.id=o.business_id "
            "WHERE o.status='rechazado' OR "
            "(o.status='pendiente' AND (o.attempts>=o.max_attempts "
            "OR o.next_attempt_at<=?)) "
            "GROUP BY b.id, b.name "
            "ORDER BY rechazadas DESC, agotadas DESC, vencidas DESC, b.id "
            "LIMIT 8",
            (now, now),
        ).fetchall()
    oldest_at = oldest["next_attempt_at"] if oldest else None
    oldest_days = None
    if oldest_at:
        try:
            oldest_days = max(
                0,
                (datetime.fromisoformat(str(now)[:19])
                 - datetime.fromisoformat(str(oldest_at)[:19])).days,
            )
        except ValueError:
            oldest_days = None
    return {
        **counts,
        "vencidas": int(due["total"] or 0),
        "oldest_pending_at": oldest_at,
        "oldest_pending_days": oldest_days,
        "last_activity_at": activity["updated_at"] if activity else None,
        "affected_businesses": [
            {
                "id": row["id"],
                "name": row["name"],
                "agotadas": int(row["agotadas"] or 0),
                "rechazadas": int(row["rechazadas"] or 0),
                "vencidas": int(row["vencidas"] or 0),
            }
            for row in affected
        ],
    }


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
    return _verify_invoice_record_rows(records)


def record_verifactu_anomaly(
    business_id: int,
    *,
    invoice_id: int | None = None,
    record_id: int | None = None,
    details: str,
) -> None:
    """Registra una alerta fiscal sin repetir el mismo evento indefinidamente."""
    safe_details = str(details)[:1500]
    with get_conn() as conn:
        previous = conn.execute(
            "SELECT details FROM invoice_events WHERE business_id=? "
            "AND event_type='anomalia' AND record_id=? ORDER BY id DESC LIMIT 1",
            (business_id, record_id),
        ).fetchone()
        if previous and previous.get("details") == safe_details:
            return
        _record_invoice_event(
            conn,
            business_id,
            "anomalia",
            invoice_id=invoice_id,
            record_id=record_id,
            details=safe_details,
        )


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
                record_id=(
                    integrity.get("broken_at")
                    if integrity.get("broken_record_type") == "alta" else None
                ),
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


# ----------------------------------------------------- Conciliación bancaria ---
def add_bank_transaction(
    business_id: int,
    *,
    import_hash: str,
    booked_on: str,
    amount: float,
    description: str = "",
    counterparty: str = "",
    reference: str = "",
    currency: str = "EUR",
) -> dict | None:
    """Guarda un movimiento una sola vez; nunca lo convierte en cobro solo."""
    if not get_business(business_id):
        raise ValueError("Negocio no encontrado.")
    try:
        date.fromisoformat(booked_on)
    except ValueError as exc:
        raise ValueError("La fecha del movimiento no es válida.") from exc
    number = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not number.is_finite() or number == 0:
        raise ValueError("El movimiento necesita un importe distinto de cero.")
    clean_hash = str(import_hash or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", clean_hash):
        raise ValueError("La huella del movimiento no es válida.")
    fields = {
        "description": _payment_text(description, "La descripción", 500),
        "counterparty": _payment_text(counterparty, "La contraparte", 200),
        "reference": _payment_text(reference, "La referencia", 200),
    }
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO bank_transactions "
            "(business_id, import_hash, booked_on, amount, currency, description, "
            "counterparty, reference, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (business_id, import_hash) DO NOTHING RETURNING id",
            (
                business_id, clean_hash, booked_on, float(number),
                (currency or "EUR").strip().upper()[:3],
                fields["description"], fields["counterparty"],
                fields["reference"], _now(),
            ),
        ).fetchone()
        if not row:
            return None
        transaction_id = row["id"]
    return get_bank_transaction(transaction_id, business_id)


def get_bank_transaction(transaction_id: int, business_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT bt.*, i.number AS invoice_number, i.total AS invoice_total, "
            "c.name AS client_name FROM bank_transactions bt "
            "LEFT JOIN invoices i ON i.id=bt.suggested_invoice_id "
            "AND i.business_id=bt.business_id "
            "LEFT JOIN clients c ON c.id=i.client_id AND c.business_id=i.business_id "
            "WHERE bt.id=? AND bt.business_id=?",
            (transaction_id, business_id),
        ).fetchone()
    return dict(row) if row else None


def list_bank_transactions(
    business_id: int, *, status: str | None = None, limit: int = 100
) -> list[dict]:
    sql = (
        "SELECT bt.*, i.number AS invoice_number, i.total AS invoice_total, "
        "c.name AS client_name FROM bank_transactions bt "
        "LEFT JOIN invoices i ON i.id=bt.suggested_invoice_id "
        "AND i.business_id=bt.business_id "
        "LEFT JOIN clients c ON c.id=i.client_id AND c.business_id=i.business_id "
        "WHERE bt.business_id=?"
    )
    params: list[Any] = [business_id]
    if status:
        sql += " AND bt.status=?"
        params.append(status)
    sql += " ORDER BY bt.booked_on DESC, bt.id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def suggest_bank_transaction(
    transaction_id: int,
    business_id: int,
    invoice_id: int | None,
    *,
    score: int | None = None,
    reason: str = "",
) -> dict | None:
    if invoice_id is not None:
        invoice = get_invoice(invoice_id, business_id)
        if not invoice or invoice.get("status") == "borrador":
            raise ValueError("La factura sugerida no es válida.")
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE bank_transactions SET status=?, suggested_invoice_id=?, "
            "match_score=?, match_reason=? WHERE id=? AND business_id=? "
            "AND status IN ('imported','suggested')",
            (
                "suggested" if invoice_id is not None else "imported",
                invoice_id, score, _payment_text(reason, "El motivo", 300),
                transaction_id, business_id,
            ),
        )
    return get_bank_transaction(transaction_id, business_id) if cur.rowcount else None


def confirm_bank_transaction(transaction_id: int, business_id: int) -> dict:
    """Confirma una sugerencia y registra el cobro en la misma transacción."""
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        movement = conn.execute(
            "SELECT * FROM bank_transactions WHERE id=? AND business_id=?" + lock,
            (transaction_id, business_id),
        ).fetchone()
        if not movement:
            raise ValueError("Movimiento no encontrado.")
        if movement["status"] == "confirmed":
            return dict(movement)
        invoice_id = movement.get("suggested_invoice_id")
        if movement["status"] != "suggested" or not invoice_id:
            raise ValueError("Este movimiento no tiene una factura sugerida.")
        amount = Decimal(str(movement["amount"])).quantize(Decimal("0.01"))
        if amount <= 0:
            raise ValueError("Solo una entrada de dinero puede confirmar un cobro.")
        invoice, already_paid = _locked_invoice_with_paid(
            conn, invoice_id, business_id
        )
        if not invoice or invoice["status"] == "borrador" or not invoice.get("number"):
            raise ValueError("La factura ya no admite este cobro.")
        total = Decimal(str(invoice["total"])).quantize(Decimal("0.01"))
        if already_paid + amount > total:
            raise ValueError("El movimiento supera lo que queda por cobrar.")
        note = " · ".join(
            value for value in (
                "Conciliado desde extracto",
                movement.get("reference"),
                movement.get("description"),
            ) if value
        )[:500]
        _insert_invoice_payment(
            conn, invoice, amount, "extracto_bancario",
            f"{movement['booked_on']}T12:00:00", note,
        )
        _set_invoice_payment_state(
            conn, invoice, already_paid + amount,
            f"{movement['booked_on']}T12:00:00",
        )
        _record_invoice_event(
            conn, business_id, "cobro", invoice_id=invoice_id,
            details=f"importe={float(amount):.2f};metodo=extracto_bancario",
            created_at=f"{movement['booked_on']}T12:00:00",
        )
        now = _now()
        conn.execute(
            "UPDATE bank_transactions SET status='confirmed', confirmed_at=? "
            "WHERE id=? AND business_id=?",
            (now, transaction_id, business_id),
        )
    return get_bank_transaction(transaction_id, business_id) or {}


def ignore_bank_transaction(transaction_id: int, business_id: int) -> dict | None:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE bank_transactions SET status='ignored', "
            "suggested_invoice_id=NULL, match_score=NULL, match_reason=NULL "
            "WHERE id=? AND business_id=? AND status<>'confirmed'",
            (transaction_id, business_id),
        )
    return get_bank_transaction(transaction_id, business_id) if cur.rowcount else None


def bank_reconciliation_summary(business_id: int) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n, COALESCE(SUM(amount),0) AS total "
            "FROM bank_transactions WHERE business_id=? GROUP BY status",
            (business_id,),
        ).fetchall()
    by = {row["status"]: dict(row) for row in rows}
    return {
        key: {
            "count": int(by.get(key, {}).get("n") or 0),
            "total": round(float(by.get(key, {}).get("total") or 0), 2),
        }
        for key in ("imported", "suggested", "confirmed", "ignored")
    }


# ------------------------------------------------------------- Correo durable ---
def enqueue_email_message(
    *,
    business_id: int | None,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    idempotency_key: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    max_attempts: int = 6,
    now: str | None = None,
) -> dict:
    if business_id is not None and not get_business(business_id):
        raise ValueError("Negocio no encontrado.")
    to_email = str(to_email or "").strip().lower()
    subject = str(subject or "").strip()
    text_body = str(text_body or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", to_email) or len(to_email) > 320:
        raise ValueError("El email de destino no es válido.")
    if not subject or len(subject) > 200:
        raise ValueError("El asunto del email no es válido.")
    if not text_body or len(text_body) > 100_000:
        raise ValueError("El contenido del email no es válido.")
    if html_body is not None and len(html_body) > 200_000:
        raise ValueError("El contenido HTML es demasiado grande.")
    created_at = now or _now()
    entity_type = (entity_type or "").strip().lower() or None
    if entity_type not in {None, "invoice"}:
        raise ValueError("El tipo de adjunto del correo no es válido.")
    if entity_type == "invoice":
        if business_id is None or entity_id is None or not get_invoice(
            int(entity_id), business_id
        ):
            raise ValueError("La factura adjunta no pertenece al negocio.")
        entity_id = int(entity_id)
    try:
        with get_conn() as conn:
            row = conn.execute(
                "INSERT INTO email_outbox "
                "(business_id, to_email, subject, text_body, html_body, "
                "idempotency_key, entity_type, entity_id, status, attempts, "
                "max_attempts, next_attempt_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, ?, ?, ?, ?) RETURNING id",
                (
                    business_id, to_email, subject, text_body, html_body,
                    idempotency_key, entity_type, entity_id,
                    max(1, min(int(max_attempts), 20)),
                    created_at, created_at, created_at,
                ),
            ).fetchone()
            message_id = row["id"]
    except IntegrityError:
        if not idempotency_key:
            raise
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM email_outbox WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
        if not existing or existing.get("business_id") != business_id:
            raise ValueError("La clave idempotente pertenece a otro envío.")
        return dict(existing)
    return get_email_message(message_id) or {}


def get_email_message(message_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM email_outbox WHERE id=?", (message_id,)
        ).fetchone()
    return dict(row) if row else None


def list_email_messages(
    business_id: int | None = None, *, status: str | None = None, limit: int = 100
) -> list[dict]:
    sql = "SELECT * FROM email_outbox WHERE 1=1"
    params: list[Any] = []
    if business_id is not None:
        sql += " AND business_id=?"
        params.append(business_id)
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def claim_next_email_message(*, now: str, stale_before: str) -> dict | None:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        suffix = " FOR UPDATE SKIP LOCKED" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT * FROM email_outbox WHERE "
            "((status IN ('queued','retrying') AND next_attempt_at<=?) "
            "OR (status='processing' AND locked_at<=?)) "
            "ORDER BY next_attempt_at, id LIMIT 1" + suffix,
            (now, stale_before),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE email_outbox SET status='processing', attempts=attempts+1, "
            "locked_at=?, updated_at=? WHERE id=?",
            (now, now, row["id"]),
        )
        claimed = conn.execute(
            "SELECT * FROM email_outbox WHERE id=?", (row["id"],)
        ).fetchone()
    return dict(claimed)


def mark_email_sent(message_id: int, sent_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE email_outbox SET status='sent', sent_at=?, last_error=NULL, "
            "locked_at=NULL, updated_at=? WHERE id=? AND status='processing'",
            (sent_at, sent_at, message_id),
        )


def mark_email_retry(
    message_id: int, *, error: str, next_attempt_at: str, updated_at: str
) -> dict | None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE email_outbox SET "
            "status=CASE WHEN attempts>=max_attempts THEN 'failed' ELSE 'retrying' END, "
            "next_attempt_at=?, last_error=?, locked_at=NULL, updated_at=? "
            "WHERE id=? AND status='processing'",
            (next_attempt_at, str(error or "error")[:1000], updated_at, message_id),
        )
    return get_email_message(message_id)


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


# -------------------------------------------------------------- Proyectos ---
PROJECT_STATUSES = {"planificado", "en_curso", "pausado", "terminado"}
PROJECT_ENTRY_KINDS = {"material", "horas", "subcontrata", "otro"}
PROJECT_TASK_KINDS = {"tarea", "checklist", "incidencia"}
PROJECT_TASK_STATUSES = {"pendiente", "en_curso", "hecha", "bloqueada"}


def _project_number(value, label: str, *, allow_zero: bool = False) -> float:
    try:
        number = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} debe ser un número.") from exc
    minimum_ok = number >= 0 if allow_zero else number > 0
    if not number.is_finite() or not minimum_ok or number > Decimal("10000000"):
        qualifier = "0 o mayor" if allow_zero else "mayor que 0"
        raise ValueError(f"{label} debe ser {qualifier}.")
    return float(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def add_project(name, budget, client_id=None, location=None, planned_hours=0,
                starts_on=None, ends_on=None, note=None, *, business_id: int) -> dict:
    name = (name or "").strip()
    if not name or len(name) > 200:
        raise ValueError("El nombre del proyecto es obligatorio (máx. 200 caracteres).")
    budget = _project_number(budget, "El presupuesto")
    planned_hours = _project_number(
        planned_hours, "Las horas previstas", allow_zero=True
    )
    if client_id not in (None, ""):
        client_id = int(client_id)
        if not get_client(client_id, business_id):
            raise ValueError("El cliente no pertenece a este negocio.")
    else:
        client_id = None
    starts_on = _optional_date(starts_on, "La fecha de inicio")
    ends_on = _optional_date(ends_on, "La fecha final")
    if starts_on and ends_on and ends_on < starts_on:
        raise ValueError("La fecha final no puede ser anterior al inicio.")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO projects (business_id, client_id, name, location, budget, "
            "planned_hours, starts_on, ends_on, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, client_id, name, (location or "").strip() or None,
             budget, planned_hours, starts_on, ends_on,
             (note or "").strip() or None, _now()),
        ).fetchone()
    return get_project(row["id"], business_id)


def _project_select() -> str:
    return (
        "SELECT p.*, c.name AS client_name, "
        "COALESCE((SELECT SUM(e.total) FROM project_entries e "
        "WHERE e.business_id=p.business_id AND e.project_id=p.id),0) AS entry_cost, "
        "COALESCE((SELECT SUM(e.quantity) FROM project_entries e "
        "WHERE e.business_id=p.business_id AND e.project_id=p.id "
        "AND e.kind='horas'),0) AS entry_hours, "
        "COALESCE((SELECT SUM(x.amount) FROM expenses x "
        "WHERE x.business_id=p.business_id AND x.project_id=p.id),0) AS expense_cost, "
        "COALESCE((SELECT SUM(jm.total) FROM job_materials jm "
        "JOIN jobs j ON j.id=jm.job_id AND j.business_id=jm.business_id "
        "WHERE j.business_id=p.business_id AND j.project_id=p.id),0) "
        "AS field_material_cost, "
        "(SELECT COUNT(*) FROM project_members m WHERE m.business_id=p.business_id "
        "AND m.project_id=p.id) AS member_count, "
        "(SELECT COUNT(*) FROM jobs j WHERE j.business_id=p.business_id "
        "AND j.project_id=p.id) AS job_count, "
        "(SELECT COUNT(*) FROM project_tasks t WHERE t.business_id=p.business_id "
        "AND t.project_id=p.id AND t.status!='hecha') AS pending_task_count "
        "FROM projects p LEFT JOIN clients c ON c.id=p.client_id "
        "AND c.business_id=p.business_id "
    )


def _project_clockin_metrics(project_id: int, business_id: int) -> dict:
    with get_conn() as conn:
        job_rows = conn.execute(
            "SELECT id FROM jobs WHERE business_id=? AND project_id=?",
            (business_id, project_id),
        ).fetchall()
        members = conn.execute(
            "SELECT worker_id, hourly_cost FROM project_members "
            "WHERE business_id=? AND project_id=?",
            (business_id, project_id),
        ).fetchall()
        member_records = {
            member["worker_id"]: _clockin_rows_with_corrections(
                conn, business_id, member["worker_id"]
            )
            for member in members
        }
    job_ids = {row["id"] for row in job_rows}
    total_hours = 0.0
    labor_cost = Decimal("0")
    missing_cost_worker_ids: list[int] = []
    for member in members:
        by_job = _worked_seconds_by_job(member_records[member["worker_id"]])
        hours = sum(
            seconds for job_id, seconds in by_job.items() if job_id in job_ids
        ) / 3600
        total_hours += hours
        hourly_cost = Decimal(str(member.get("hourly_cost") or 0))
        if hours and hourly_cost <= 0:
            missing_cost_worker_ids.append(member["worker_id"])
        labor_cost += Decimal(str(hours)) * hourly_cost
    return {
        "clockin_hours": round(total_hours, 2),
        "clockin_cost": float(labor_cost.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )),
        "missing_hourly_cost_worker_ids": missing_cost_worker_ids,
    }


def _project_metrics(project: dict, clockin: dict | None = None) -> dict:
    project = dict(project)
    clockin = clockin or {
        "clockin_hours": 0.0,
        "clockin_cost": 0.0,
        "missing_hourly_cost_worker_ids": [],
    }
    budget = float(project.get("budget") or 0)
    entry_cost = round(float(project.get("entry_cost") or 0), 2)
    expense_cost = round(float(project.get("expense_cost") or 0), 2)
    field_material_cost = round(
        float(project.get("field_material_cost") or 0), 2
    )
    clockin_cost = round(float(clockin.get("clockin_cost") or 0), 2)
    cost = round(
        entry_cost + expense_cost + field_material_cost + clockin_cost, 2
    )
    entry_hours = round(float(project.get("entry_hours") or 0), 2)
    clockin_hours = round(float(clockin.get("clockin_hours") or 0), 2)
    project["entry_cost"] = entry_cost
    project["expense_cost"] = expense_cost
    project["field_material_cost"] = field_material_cost
    project["clockin_cost"] = clockin_cost
    project["entry_hours"] = entry_hours
    project["clockin_hours"] = clockin_hours
    project["actual_cost"] = cost
    project["actual_hours"] = round(entry_hours + clockin_hours, 2)
    project["margin"] = round(budget - cost, 2)
    project["cost_pct"] = round(cost / budget * 100, 1) if budget else 0
    project["missing_hourly_cost_worker_ids"] = list(
        clockin.get("missing_hourly_cost_worker_ids") or []
    )
    return project


def list_projects(business_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            _project_select() + "WHERE p.business_id=? "
            "ORDER BY CASE p.status WHEN 'en_curso' THEN 0 WHEN 'planificado' THEN 1 "
            "WHEN 'pausado' THEN 2 ELSE 3 END, p.updated_at DESC, p.id DESC",
            (business_id,),
        ).fetchall()
    return [
        _project_metrics(
            row, _project_clockin_metrics(row["id"], business_id)
        )
        for row in rows
    ]


def get_project(project_id: int, business_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            _project_select() + "WHERE p.id=? AND p.business_id=?",
            (project_id, business_id),
        ).fetchone()
        if not row:
            return None
        members = conn.execute(
            "SELECT m.*, w.name AS worker_name, w.color AS worker_color "
            "FROM project_members m JOIN workers w ON w.id=m.worker_id "
            "AND w.business_id=m.business_id WHERE m.project_id=? "
            "AND m.business_id=? ORDER BY w.name",
            (project_id, business_id),
        ).fetchall()
        entries = conn.execute(
            "SELECT e.*, w.name AS worker_name FROM project_entries e "
            "LEFT JOIN workers w ON w.id=e.worker_id AND w.business_id=e.business_id "
            "WHERE e.project_id=? AND e.business_id=? "
            "ORDER BY COALESCE(e.entry_on, CAST(e.created_at AS TEXT)) DESC, "
            "e.id DESC",
            (project_id, business_id),
        ).fetchall()
        jobs = conn.execute(
            "SELECT j.*, c.name AS client_name, w.name AS worker_name "
            "FROM jobs j LEFT JOIN clients c ON c.id=j.client_id "
            "AND c.business_id=j.business_id "
            "LEFT JOIN workers w ON w.id=j.worker_id "
            "AND w.business_id=j.business_id "
            "WHERE j.project_id=? AND j.business_id=? "
            "ORDER BY j.scheduled_for DESC, j.id DESC",
            (project_id, business_id),
        ).fetchall()
        tasks = conn.execute(
            "SELECT t.*, w.name AS worker_name, j.description AS job_description "
            "FROM project_tasks t LEFT JOIN workers w ON w.id=t.worker_id "
            "AND w.business_id=t.business_id "
            "LEFT JOIN jobs j ON j.id=t.job_id AND j.business_id=t.business_id "
            "WHERE t.project_id=? AND t.business_id=? "
            "ORDER BY CASE t.status WHEN 'bloqueada' THEN 0 "
            "WHEN 'en_curso' THEN 1 WHEN 'pendiente' THEN 2 ELSE 3 END, "
            "COALESCE(t.due_on, '9999-12-31'), t.id DESC",
            (project_id, business_id),
        ).fetchall()
        expenses = conn.execute(
            "SELECT * FROM expenses WHERE project_id=? AND business_id=? "
            "ORDER BY COALESCE(spent_on, created_at) DESC, id DESC",
            (project_id, business_id),
        ).fetchall()
        documents = conn.execute(
            "SELECT * FROM documents WHERE project_id=? AND business_id=? "
            "ORDER BY created_at DESC, id DESC",
            (project_id, business_id),
        ).fetchall()
    project = _project_metrics(
        row, _project_clockin_metrics(project_id, business_id)
    )
    project["members"] = [dict(item) for item in members]
    project["entries"] = [dict(item) for item in entries]
    project["jobs"] = [dict(item) for item in jobs]
    project["tasks"] = [dict(item) for item in tasks]
    project["expenses"] = [dict(item) for item in expenses]
    project["documents"] = [dict(item) for item in documents]
    return project


def project_summary(business_id: int) -> dict:
    projects = list_projects(business_id)
    active = [p for p in projects if p["status"] != "terminado"]
    budget = round(sum(float(p["budget"]) for p in active), 2)
    cost = round(sum(float(p["actual_cost"]) for p in active), 2)
    progress = (
        round(sum(int(p["progress"]) for p in active) / len(active)) if active else 0
    )
    return {
        "projects": projects, "active_count": len(active), "progress": progress,
        "budget": budget, "cost": cost, "margin": round(budget - cost, 2),
    }


def update_project(project_id: int, *, business_id: int, progress=None,
                   status=None) -> dict | None:
    project = get_project(project_id, business_id)
    if not project:
        return None
    progress = project["progress"] if progress is None else int(progress)
    if progress < 0 or progress > 100:
        raise ValueError("El avance debe estar entre 0 y 100.")
    status = status or project["status"]
    if status not in PROJECT_STATUSES:
        raise ValueError("El estado del proyecto no es válido.")
    if status == "terminado":
        progress = 100
    with get_conn() as conn:
        conn.execute(
            "UPDATE projects SET progress=?, status=?, updated_at=? "
            "WHERE id=? AND business_id=?",
            (progress, status, _now(), project_id, business_id),
        )
    return get_project(project_id, business_id)


def add_project_member(project_id: int, worker_id: int, hourly_cost=0, role=None,
                       *, business_id: int) -> dict:
    if not get_project(project_id, business_id):
        raise ValueError("Proyecto no encontrado.")
    worker = get_worker(worker_id, business_id)
    if not worker or not worker.get("active"):
        raise ValueError("La persona no pertenece a este negocio o está inactiva.")
    hourly_cost = _project_number(hourly_cost, "El coste por hora", allow_zero=True)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO project_members (business_id, project_id, worker_id, role, "
            "hourly_cost, created_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (business_id, project_id, worker_id) DO UPDATE SET "
            "role=excluded.role, hourly_cost=excluded.hourly_cost",
            (business_id, project_id, worker_id, (role or "").strip() or None,
             hourly_cost, _now()),
        )
    return get_project(project_id, business_id)


def _ensure_project_member(
    project_id: int, worker_id: int, business_id: int
) -> None:
    """Una asignación de campo nunca deja al trabajador fuera del proyecto."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO project_members "
            "(business_id, project_id, worker_id, role, hourly_cost, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (business_id, project_id, worker_id) DO NOTHING",
            (business_id, project_id, worker_id, None, 0, _now()),
        )


def add_project_entry(project_id: int, kind, description, quantity, unit_cost,
                      worker_id=None, entry_on=None, *, business_id: int) -> dict:
    if not get_project(project_id, business_id):
        raise ValueError("Proyecto no encontrado.")
    kind = (kind or "otro").strip()
    if kind not in PROJECT_ENTRY_KINDS:
        raise ValueError("El tipo de coste no es válido.")
    description = (description or "").strip()
    if not description or len(description) > 300:
        raise ValueError("La descripción es obligatoria (máx. 300 caracteres).")
    quantity = _project_number(quantity, "La cantidad")
    unit_cost = _project_number(unit_cost, "El coste unitario", allow_zero=True)
    total = float((Decimal(str(quantity)) * Decimal(str(unit_cost))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ))
    if worker_id not in (None, ""):
        worker_id = int(worker_id)
        if not get_worker(worker_id, business_id):
            raise ValueError("La persona no pertenece a este negocio.")
    else:
        worker_id = None
    entry_on = _optional_date(entry_on, "La fecha")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO project_entries (business_id, project_id, worker_id, kind, "
            "description, quantity, unit_cost, total, entry_on, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, project_id, worker_id, kind, description, quantity,
             unit_cost, total, entry_on, _now()),
        ).fetchone()
        conn.execute(
            "UPDATE projects SET updated_at=? WHERE id=? AND business_id=?",
            (_now(), project_id, business_id),
        )
        entry = conn.execute(
            "SELECT * FROM project_entries WHERE id=? AND business_id=?",
            (row["id"], business_id),
        ).fetchone()
    return dict(entry)


def get_project_task(
    task_id: int, business_id: int
) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM project_tasks WHERE id=? AND business_id=?",
            (task_id, business_id),
        ).fetchone()
    return dict(row) if row else None


def add_project_task(
    project_id: int,
    title: str,
    *,
    business_id: int,
    kind: str = "tarea",
    note: str | None = None,
    worker_id: int | None = None,
    job_id: int | None = None,
    due_on: str | None = None,
) -> dict:
    if not get_project(project_id, business_id):
        raise ValueError("Proyecto no encontrado.")
    title = str(title or "").strip()
    if not title or len(title) > 240:
        raise ValueError("La tarea necesita un título (máx. 240 caracteres).")
    kind = str(kind or "tarea").strip()
    if kind not in PROJECT_TASK_KINDS:
        raise ValueError("El tipo de tarea no es válido.")
    if worker_id not in (None, ""):
        worker_id = int(worker_id)
        worker = get_worker(worker_id, business_id)
        if not worker or not worker.get("active"):
            raise ValueError("La persona no pertenece a este negocio o está inactiva.")
        _ensure_project_member(project_id, worker_id, business_id)
    else:
        worker_id = None
    if job_id not in (None, ""):
        job_id = int(job_id)
        job = get_job(job_id, business_id)
        if not job or job.get("project_id") != project_id:
            raise ValueError("El trabajo no pertenece a este proyecto.")
    else:
        job_id = None
    due_on = _optional_date(due_on, "La fecha límite")
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO project_tasks "
            "(business_id, project_id, job_id, worker_id, title, note, kind, "
            "status, due_on, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?, ?) RETURNING id",
            (
                business_id, project_id, job_id, worker_id, title,
                str(note or "").strip()[:2000] or None, kind, due_on, now, now,
            ),
        ).fetchone()
    return get_project_task(row["id"], business_id)


def update_project_task(
    task_id: int,
    *,
    business_id: int,
    status: str,
    actor_worker_id: int | None = None,
) -> dict | None:
    task = get_project_task(task_id, business_id)
    if not task:
        return None
    status = str(status or "").strip()
    if status not in PROJECT_TASK_STATUSES:
        raise ValueError("El estado de la tarea no es válido.")
    if (
        actor_worker_id is not None
        and task.get("worker_id") not in (None, actor_worker_id)
    ):
        raise ValueError("Esta tarea está asignada a otra persona.")
    if actor_worker_id is not None and task.get("worker_id") is None:
        with get_conn() as conn:
            member = conn.execute(
                "SELECT 1 AS found FROM project_members WHERE business_id=? "
                "AND project_id=? AND worker_id=?",
                (business_id, task["project_id"], actor_worker_id),
            ).fetchone()
        if not member:
            raise ValueError("Esta tarea pertenece a otro proyecto.")
    now = _now()
    completed_at = now if status == "hecha" else None
    with get_conn() as conn:
        conn.execute(
            "UPDATE project_tasks SET status=?, updated_at=?, completed_at=? "
            "WHERE id=? AND business_id=?",
            (status, now, completed_at, task_id, business_id),
        )
        conn.execute(
            "UPDATE projects SET updated_at=? WHERE id=? AND business_id=?",
            (now, task["project_id"], business_id),
        )
    return get_project_task(task_id, business_id)


def project_tasks_for_worker(
    worker_id: int, business_id: int, *, include_done: bool = False
) -> list[dict]:
    if not get_worker(worker_id, business_id):
        return []
    done_filter = "" if include_done else " AND t.status!='hecha'"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT t.*, p.name AS project_name, p.location AS project_location, "
            "j.description AS job_description "
            "FROM project_tasks t JOIN projects p ON p.id=t.project_id "
            "AND p.business_id=t.business_id "
            "LEFT JOIN jobs j ON j.id=t.job_id AND j.business_id=t.business_id "
            "WHERE t.business_id=? AND (t.worker_id=? OR (t.worker_id IS NULL "
            "AND EXISTS (SELECT 1 FROM project_members m "
            "WHERE m.business_id=t.business_id AND m.project_id=t.project_id "
            "AND m.worker_id=?))) "
            + done_filter +
            " ORDER BY CASE t.status WHEN 'bloqueada' THEN 0 "
            "WHEN 'en_curso' THEN 1 ELSE 2 END, "
            "COALESCE(t.due_on, '9999-12-31'), t.id",
            (business_id, worker_id, worker_id),
        ).fetchall()
    return [dict(row) for row in rows]


# ----------------------------------------------------------------- Gastos ---
def add_expense(
    concept,
    amount,
    vat_rate=None,
    category=None,
    spent_on=None,
    document_id=None,
    project_id=None,
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
    if project_id not in (None, ""):
        try:
            project_id = int(project_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("El proyecto no es válido.") from exc
        if not get_project(project_id, business_id):
            raise ValueError("El proyecto no pertenece a este negocio.")
    else:
        project_id = None
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
            "spent_on, project_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (business_id, concept, amount, vat_rate, category,
             spent_on, project_id, _now()),
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
            "SELECT x.*, p.name AS project_name FROM expenses x "
            "LEFT JOIN projects p ON p.id=x.project_id "
            "AND p.business_id=x.business_id "
            "WHERE x.business_id=? ORDER BY x.created_at DESC",
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
    q = ("SELECT r.*, s.name AS supplier_name, s.nif AS supplier_nif "
         "FROM received_invoices r "
         "LEFT JOIN suppliers s ON s.id=r.supplier_id "
         "AND s.business_id=r.business_id WHERE r.business_id=?")
    params: list = [business_id]
    if status:
        if status not in RECEIVED_STATUSES:
            raise ValueError("Estado de factura recibida desconocido.")
        q += " AND r.status=?"
        params.append(status)
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
        q += " AND active=TRUE"
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
        conn.execute(
            "UPDATE whatsapp_contacts SET client_id=?, lead_id=NULL, updated_at=? "
            "WHERE business_id=? AND lead_id=?",
            (client["id"], _now(), business_id, lead_id),
        )
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
            "AND COALESCE(CAST(spent_on AS TEXT), CAST(created_at AS TEXT)) LIKE ?",
            (business_id, f"{prefix}%")).fetchall()]
        received_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM received_invoices WHERE business_id=? "
            "AND COALESCE(CAST(issued_on AS TEXT), CAST(created_at AS TEXT)) LIKE ?",
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


EXPLANATION_LEVELS = {"claro", "directo", "detallado"}


def update_explanation_level(business_id: int, level: str) -> None:
    if level not in EXPLANATION_LEVELS:
        raise ValueError("El nivel de explicación no es válido.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET explanation_level=? WHERE id=?",
            (level, business_id),
        )


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
    invoiced_collected = sum(item["paid_amount"] for item in invoices)
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
        # Cohorte homogénea para responder "qué parte de lo emitido este mes
        # ya está cobrada". `collected` conserva su significado de caja que ha
        # entrado durante el mes, aunque corresponda a facturas anteriores.
        "invoiced_collected": round(invoiced_collected, 2),
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
            "GROUP BY i.client_id, c.name ORDER BY total DESC LIMIT ?",
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


CLIENT_CHANNELS = {"whatsapp", "email", "telefono"}
CLIENT_CONTACT_WINDOWS = {"manana", "tarde", "cualquiera"}


def get_client_preferences(client_id: int, business_id: int) -> dict | None:
    if not get_client(client_id, business_id):
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM client_preferences WHERE client_id=? AND business_id=?",
            (client_id, business_id),
        ).fetchone()
    return dict(row) if row else {
        "business_id": business_id, "client_id": client_id,
        "preferred_channel": None, "preferred_contact_window": None,
        "payment_terms_days": None, "note": None, "source": None,
        "updated_at": None,
    }


def update_client_preferences(
    client_id: int, business_id: int, *, preferred_channel=None,
    preferred_contact_window=None, payment_terms_days=None, note=None,
) -> dict:
    if not get_client(client_id, business_id):
        raise ValueError("Cliente no encontrado.")
    preferred_channel = str(preferred_channel or "").strip() or None
    if preferred_channel not in CLIENT_CHANNELS | {None}:
        raise ValueError("El canal preferido no es válido.")
    preferred_contact_window = (
        str(preferred_contact_window or "").strip() or None
    )
    if preferred_contact_window not in CLIENT_CONTACT_WINDOWS | {None}:
        raise ValueError("El horario preferido no es válido.")
    if payment_terms_days in (None, ""):
        payment_terms_days = None
    else:
        try:
            payment_terms_days = int(payment_terms_days)
        except (TypeError, ValueError) as exc:
            raise ValueError("Los días de pago no son válidos.") from exc
        if not 0 <= payment_terms_days <= 365:
            raise ValueError("Los días de pago deben estar entre 0 y 365.")
    note = str(note or "").strip()[:1000] or None
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO client_preferences (business_id, client_id, "
            "preferred_channel, preferred_contact_window, payment_terms_days, "
            "note, source, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'manual', ?) "
            "ON CONFLICT (business_id, client_id) DO UPDATE SET "
            "preferred_channel=excluded.preferred_channel, "
            "preferred_contact_window=excluded.preferred_contact_window, "
            "payment_terms_days=excluded.payment_terms_days, note=excluded.note, "
            "source='manual', updated_at=excluded.updated_at",
            (business_id, client_id, preferred_channel,
             preferred_contact_window, payment_terms_days, note, _now()),
        )
    record_product_event(business_id, "client_preferences_updated")
    return get_client_preferences(client_id, business_id) or {}


def client_insights(business_id: int) -> list[dict]:
    """Señales explicables por cliente; reglas honestas antes que ML opaco.

    Cada lectura incluye su evidencia y confianza. No se presenta como predicción
    cuando todavía no hay historial suficiente.
    """
    clients = list_clients(business_id)
    invoices = list_invoices(business_id)
    quotes = list_quotes(business_id)
    with get_conn() as conn:
        jobs = [dict(row) for row in conn.execute(
            "SELECT * FROM jobs WHERE business_id=?", (business_id,)
        ).fetchall()]
        preferences = {
            row["client_id"]: dict(row) for row in conn.execute(
                "SELECT * FROM client_preferences WHERE business_id=?",
                (business_id,),
            ).fetchall()
        }
        direct_costs = {
            row["client_id"]: float(row["total"] or 0)
            for row in conn.execute(
                "SELECT j.client_id, SUM(m.total) AS total FROM job_materials m "
                "JOIN jobs j ON j.id=m.job_id AND j.business_id=m.business_id "
                "WHERE m.business_id=? GROUP BY j.client_id",
                (business_id,),
            ).fetchall()
        }
    today = date.today()

    def _day(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except (TypeError, ValueError):
            try:
                return date.fromisoformat(str(value)[:10])
            except (TypeError, ValueError):
                return None

    out: list[dict] = []
    for client in clients:
        cid = client["id"]
        cinv = [item for item in invoices if item.get("client_id") == cid]
        cquotes = [item for item in quotes if item.get("client_id") == cid]
        cjobs = [item for item in jobs if item.get("client_id") == cid]
        pending = [item for item in cinv if item.get("remaining_amount", 0) > 0
                   and item.get("status") != "borrador"]
        overdue = []
        for item in pending:
            due = _day(item.get("due_date"))
            issued = _day(item.get("issued_at"))
            if (due and due < today) or (not due and issued and (today - issued).days > 30):
                overdue.append(item)
        paid_delays = []
        for item in cinv:
            issued, paid = _day(item.get("issued_at")), _day(item.get("paid_at"))
            if issued and paid and paid >= issued:
                paid_delays.append((paid - issued).days)
        avg_delay = round(sum(paid_delays) / len(paid_delays)) if paid_delays else None
        stale_quotes = []
        for item in cquotes:
            created = _day(item.get("created_at"))
            if item.get("status") == "enviado" and created and (today - created).days >= 7:
                stale_quotes.append(item)
        decided_quotes = [
            item for item in cquotes if item.get("status") in {"aceptado", "rechazado"}
        ]
        accepted_quotes = [
            item for item in decided_quotes if item.get("status") == "aceptado"
        ]
        quote_acceptance = (
            round(len(accepted_quotes) / len(decided_quotes) * 100)
            if decided_quotes else None
        )
        paid_after_reminder = len([
            item for item in cinv
            if item.get("paid_at") and int(item.get("reminders_sent") or 0) > 0
        ])
        known_revenue = round(sum(
            float(item.get("base") or 0) for item in cinv
            if item.get("status") in {"enviada", "parcial", "cobrada"}
        ), 2)
        known_direct_cost = round(direct_costs.get(cid, 0), 2)
        known_margin = round(known_revenue - known_direct_cost, 2)
        preference = preferences.get(cid) or {
            "preferred_channel": None, "preferred_contact_window": None,
            "payment_terms_days": None, "note": None, "source": None,
        }

        activity_days = [d for d in (
            *(_day(item.get("issued_at") or item.get("created_at")) for item in cinv),
            *(_day(item.get("created_at")) for item in cquotes),
            *(_day(item.get("scheduled_for") or item.get("created_at")) for item in cjobs),
        ) if d]
        last_activity = max(activity_days) if activity_days else None
        inactivity = (today - last_activity).days if last_activity else None
        evidence = len(cinv) + len(cquotes) + len(cjobs)
        confidence = min(95, 35 + len(cinv) * 10 + len(cjobs) * 4 + len(cquotes) * 3)

        if overdue:
            amount = round(sum(item.get("remaining_amount") or 0 for item in overdue), 2)
            amount_text = (
                f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            level = "alto"
            headline = f"Conviene reclamar {amount_text} €"
            reason = (f"Tiene {len(overdue)} factura(s) fuera de plazo"
                      + (f" y suele tardar {avg_delay} días en pagar." if avg_delay is not None else "."))
            next_action = "Preparar recordatorio de cobro"
        elif stale_quotes:
            level = "medio"
            headline = "Hay un presupuesto esperando respuesta"
            reason = f"Lleva al menos 7 días enviado sin aceptar ni rechazar ({len(stale_quotes)} pendiente(s))."
            next_action = "Preparar seguimiento del presupuesto"
        elif avg_delay is not None and avg_delay > 30:
            level = "medio"
            headline = "Suele pagar con calma"
            reason = f"Su media observada es de {avg_delay} días desde la emisión."
            next_action = "Acordar vencimiento antes del próximo trabajo"
        elif inactivity is not None and inactivity > 120 and evidence >= 2:
            level = "medio"
            headline = "Hace tiempo que no trabaja contigo"
            reason = f"La última actividad registrada fue hace {inactivity} días."
            next_action = "Valorar un mensaje de seguimiento"
        elif evidence:
            level = "bajo"
            headline = "Relación al día"
            reason = (f"Veo {len(cjobs)} trabajo(s), {len(cinv)} factura(s) y "
                      "ningún cobro vencido ahora mismo.")
            next_action = "Seguir cuidando la relación"
        else:
            level = "sin_datos"
            headline = "Aún estoy aprendiendo"
            reason = "Me faltan trabajos, presupuestos o facturas para detectar un patrón."
            next_action = "Registrar la próxima actividad"
            confidence = 0
        out.append({
            "client_id": cid,
            "client_name": client.get("name"),
            "level": level,
            "headline": headline,
            "reason": reason,
            "next_action": next_action,
            "confidence": confidence,
            "evidence_count": evidence,
            "pending_amount": round(sum(item.get("remaining_amount") or 0 for item in pending), 2),
            "average_payment_days": avg_delay,
            "last_activity_on": last_activity.isoformat() if last_activity else None,
            "quote_acceptance_pct": quote_acceptance,
            "quote_decisions": len(decided_quotes),
            "paid_after_reminder_count": paid_after_reminder,
            "known_revenue_base": known_revenue,
            "known_direct_cost": known_direct_cost,
            "known_margin": known_margin,
            "known_margin_is_partial": True,
            "preferences": preference,
            "sources": {
                "payment": f"{len(paid_delays)} factura(s) pagada(s)",
                "quotes": f"{len(decided_quotes)} presupuesto(s) decidido(s)",
                "profitability": (
                    f"{len(cinv)} factura(s) y materiales de {len(cjobs)} trabajo(s)"
                ),
                "preferences": "Confirmado manualmente" if preference.get("source") else None,
            },
        })
    priority = {"alto": 0, "medio": 1, "bajo": 2, "sin_datos": 3}
    out.sort(key=lambda item: (priority[item["level"]], -item["evidence_count"], item["client_name"] or ""))
    return out


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
              irpf_rate=0, valid_days=None, notes=None, *, business_id: int) -> dict:
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
    business = get_business(business_id) or {}
    try:
        valid_days = int(
            valid_days
            if valid_days not in (None, "")
            else business.get("default_quote_validity_days") or 30
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("La validez del presupuesto no es válida.") from exc
    if valid_days not in QUOTE_VALIDITY_DAYS:
        raise ValueError("La validez debe ser de 7, 15, 30, 45, 60 o 90 días.")
    notes = str(notes or "").strip()
    if len(notes) > 2_000:
        raise ValueError("Las notas no pueden superar 2.000 caracteres.")
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
            "vat_amount, irpf_rate, irpf_amount, total, status, valid_until, notes, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?, ?, ?) "
            "RETURNING id",
            (business_id, client_id, concept, base, vat_rate, vat_amount,
             irpf_rate or 0, irpf_amount, total, valid_until, notes or None, _now()),
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


def reject_quote(quote_id, business_id, *, decision_source="owner",
                 decision_ip_hash=None, decision_user_agent=None) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM quotes WHERE id=? AND business_id=?",
            (quote_id, business_id),
        ).fetchone()
        if not row:
            return None
        if row["status"] == "rechazado":
            return get_quote(quote_id, business_id)
        if row["status"] != "enviado":
            raise ValueError("Solo se puede rechazar un presupuesto enviado.")
        cur = conn.execute(
            "UPDATE quotes SET status='rechazado', rejected_at=?, decision_source=?, "
            "decision_ip_hash=?, decision_user_agent=? "
            "WHERE id=? AND business_id=? AND status='enviado'",
            (_now(), str(decision_source or "owner")[:30], decision_ip_hash,
             str(decision_user_agent or "")[:300] or None, quote_id, business_id),
        )
        ok = cur.rowcount > 0
    return get_quote(quote_id, business_id) if ok else None


def accept_quote(quote_id, business_id, *, decision_source="owner",
                 decision_ip_hash=None, decision_user_agent=None) -> dict | None:
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
        series = _ensure_default_invoice_series(conn, business_id, "invoice")
        invoice_row = conn.execute(
            "INSERT INTO invoices (business_id, client_id, concept, base, vat_rate, "
            "vat_amount, irpf_rate, irpf_amount, total, status, invoice_type, "
            "series_id, currency, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "'borrador', 'F1', ?, 'EUR', ?, ?) RETURNING id",
            (
                business_id, q["client_id"], q["concept"], q["base"], q["vat_rate"],
                q["vat_amount"], q["irpf_rate"], q["irpf_amount"], q["total"],
                series["id"], q["notes"], _now(),
            ),
        ).fetchone()
        invoice_id = invoice_row["id"]
        conn.execute(
            "INSERT INTO invoice_lines "
            "(business_id, invoice_id, position, description, quantity, unit_price, "
            "discount_rate, vat_rate, base, vat_amount, total, created_at) "
            "VALUES (?, ?, 1, ?, 1, ?, 0, ?, ?, ?, ?, ?)",
            (
                business_id, invoice_id, q["concept"], q["base"], q["vat_rate"],
                q["base"], q["vat_amount"], q["base"] + q["vat_amount"], _now(),
            ),
        )
        conn.execute(
            "UPDATE quotes SET status='aceptado', accepted_at=?, invoice_id=?, "
            "decision_source=?, decision_ip_hash=?, decision_user_agent=? "
            "WHERE id=? AND business_id=? AND status='enviado'",
            (_now(), invoice_id, str(decision_source or "owner")[:30],
             decision_ip_hash, str(decision_user_agent or "")[:300] or None,
             quote_id, business_id),
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
    all_received = list_received_invoices(business_id)
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
    received = [
        item for item in all_received
        if _in_range(item.get("issued_on") or item.get("created_at"), year_start)
    ]
    quarter_received = [
        item for item in all_received
        if _in_range(item.get("issued_on") or item.get("created_at"), quarter_start)
    ]

    ingresos = round(sum(i["base"] for i in invoices), 2)
    iva_repercutido = round(
        sum(i.get("vat_amount") or 0 for i in quarter_invoices), 2
    )
    irpf_retenido = round(sum(i.get("irpf_amount") or 0 for i in invoices), 2)
    gastos = round(
        sum(e["amount"] for e in expenses)
        + sum(item["total"] for item in received), 2
    )
    # IVA soportado solo de gastos que registran su tipo (no se inventa).
    iva_soportado = round(sum(
        (e["amount"] - e["amount"] / (1 + (e["vat_rate"] or 0) / 100)) if e.get("vat_rate") else 0
        for e in quarter_expenses), 2)
    iva_soportado = round(iva_soportado + sum(
        item.get("vat_amount") or 0 for item in quarter_received
    ), 2)
    base_gastos = round(sum(
        (e["amount"] / (1 + (e["vat_rate"] or 0) / 100)) if e.get("vat_rate") else e["amount"]
        for e in expenses), 2)
    base_gastos = round(base_gastos + sum(
        item.get("base") if item.get("base") is not None else item["total"]
        for item in received
    ), 2)

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
        "n_facturas_recibidas": len(quarter_received),
        "datos_incompletos": sum(
            item.get("base") is None or item.get("vat_amount") is None
            for item in quarter_received
        ) + sum(item.get("vat_rate") is None for item in quarter_expenses),
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


# --------------------------------------------------- Visitas del sitio ---
def record_page_view(path: str, referrer_host: str = "", day: str = "") -> None:
    """Suma una visita al recuento del día. Nunca guarda dato personal."""
    path = (path or "/")[:200]
    referrer_host = (referrer_host or "")[:120].lower()
    day = day or date.today().isoformat()
    with get_conn() as conn:
        # Una fila por día, página y procedencia: se incrementa, no se acumulan filas.
        actualizadas = conn.execute(
            "UPDATE page_views SET views = views + 1 "
            "WHERE day=? AND path=? AND referrer_host=?",
            (day, path, referrer_host),
        ).rowcount
        if not actualizadas:
            try:
                conn.execute(
                    "INSERT INTO page_views (day, path, referrer_host, views) "
                    "VALUES (?, ?, ?, 1)", (day, path, referrer_host),
                )
            except IntegrityError:
                # Dos peticiones simultáneas creando la misma fila: basta sumar.
                conn.execute(
                    "UPDATE page_views SET views = views + 1 "
                    "WHERE day=? AND path=? AND referrer_host=?",
                    (day, path, referrer_host),
                )


def page_views_summary(days: int = 30) -> dict:
    """Visitas del periodo: total, por día, por página y de dónde vienen."""
    desde = (date.today() - timedelta(days=max(1, int(days)))).isoformat()
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COALESCE(SUM(views), 0) AS total FROM page_views WHERE day >= ?",
            (desde,),
        ).fetchone()["total"]
        por_dia = [dict(r) for r in conn.execute(
            "SELECT day, SUM(views) AS views FROM page_views WHERE day >= ? "
            "GROUP BY day ORDER BY day", (desde,),
        ).fetchall()]
        por_pagina = [dict(r) for r in conn.execute(
            "SELECT path, SUM(views) AS views FROM page_views WHERE day >= ? "
            "GROUP BY path ORDER BY views DESC LIMIT 15", (desde,),
        ).fetchall()]
        procedencia = [dict(r) for r in conn.execute(
            "SELECT referrer_host, SUM(views) AS views FROM page_views "
            "WHERE day >= ? AND referrer_host <> '' "
            "GROUP BY referrer_host ORDER BY views DESC LIMIT 10", (desde,),
        ).fetchall()]
    return {
        "days": int(days), "total": int(total or 0), "by_day": por_dia,
        "by_path": por_pagina, "by_referrer": procedencia,
    }


# ------------------------------------------------- Solicitudes de acceso ---
ACCESS_REQUEST_STATUSES = ("nueva", "contactada", "alta", "descartada")


def create_access_request(
    name: str, email: str, *, business_name: str = "", sector: str = "",
    phone: str = "", message: str = "", plan_interest: str = "",
) -> dict:
    """Guarda una solicitud del formulario público. No crea cuenta ninguna."""
    name = (name or "").strip()[:120]
    email = (email or "").strip().lower()[:160]
    if not name or not email:
        raise ValueError("Hacen falta el nombre y el correo.")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO access_requests "
            "(name, business_name, sector, email, phone, message, plan_interest, "
            "status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'nueva', ?) RETURNING *",
            (name, (business_name or "").strip()[:160],
             (sector or "").strip()[:80], email,
             (phone or "").strip()[:40], (message or "").strip()[:2000],
             (plan_interest or "").strip()[:40], _now()),
        ).fetchone()
    return dict(row)


def list_access_requests(
    *, status: str | None = None, limit: int = 200,
) -> list[dict]:
    """Solicitudes ordenadas por llegada, las nuevas primero."""
    query = "SELECT * FROM access_requests"
    params: list = []
    if status:
        query += " WHERE status=?"
        params.append(status)
    # Las nuevas arriba; dentro de cada estado, la más reciente primero.
    query += (
        " ORDER BY CASE status WHEN 'nueva' THEN 0 WHEN 'contactada' THEN 1"
        " WHEN 'alta' THEN 2 ELSE 3 END, created_at DESC, id DESC LIMIT ?"
    )
    params.append(max(1, min(int(limit), 500)))
    with get_conn() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_access_request(request_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM access_requests WHERE id=?", (int(request_id),)
        ).fetchone()
    return dict(row) if row else None


def update_access_request(
    request_id: int, *, status: str | None = None,
    internal_note: str | None = None, business_id: int | None = None,
) -> dict | None:
    """Cambia el estado o la nota interna de una solicitud."""
    fields, params = [], []
    if status is not None:
        if status not in ACCESS_REQUEST_STATUSES:
            raise ValueError("Estado de solicitud no válido.")
        fields.append("status=?")
        params.append(status)
    if internal_note is not None:
        fields.append("internal_note=?")
        params.append(internal_note.strip()[:2000])
    if business_id is not None:
        fields.append("business_id=?")
        params.append(int(business_id))
    if not fields:
        return get_access_request(request_id)
    fields.append("updated_at=?")
    params.extend([_now(), int(request_id)])
    with get_conn() as conn:
        conn.execute(
            f"UPDATE access_requests SET {', '.join(fields)} WHERE id=?", params
        )
    return get_access_request(request_id)


def count_access_requests_since(email: str, since: str) -> int:
    """Solicitudes recientes del mismo correo: frena envíos repetidos."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM access_requests "
            "WHERE email=? AND created_at >= ?",
            ((email or "").strip().lower(), since),
        ).fetchone()
    return int(row["total"] if row else 0)


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


STRIPE_SUBSCRIPTION_STATUSES = {
    "trial", "pending", "trialing", "active", "incomplete", "past_due", "unpaid",
    "paused", "canceled", "unknown",
}


def apply_stripe_subscription_event(
    business_id: int,
    *,
    status: str,
    event_created_at: int,
    event_priority: int,
    event_id: str,
    plan: str | None = None,
    customer_id: str | None = None,
    subscription_id: str | None = None,
    allow_subscription_change: bool = False,
) -> dict:
    """Aplica un estado de Stripe solo si el evento sigue siendo vigente.

    Los webhooks pueden repetirse y llegar desordenados. La comparacion se hace
    bajo bloqueo de fila y usa fecha, prioridad semantica e id como desempate
    determinista. Un evento de una suscripcion antigua nunca puede modificar la
    suscripcion actual salvo que el propio alta/checkout autorice el reemplazo.
    """
    if status not in STRIPE_SUBSCRIPTION_STATUSES:
        raise ValueError("Estado de suscripcion Stripe no valido.")
    if not event_id:
        raise ValueError("El evento de Stripe necesita identificador.")
    try:
        created_at = max(0, int(event_created_at))
        priority = max(0, int(event_priority))
    except (TypeError, ValueError) as exc:
        raise ValueError("Orden de evento Stripe no valido.") from exc
    if plan is not None:
        from .adapters.billing import PLANS

        if plan not in PLANS:
            raise ValueError("Plan de Stripe no reconocido.")

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT * FROM businesses WHERE id=?" + lock, (business_id,)
        ).fetchone()
        if not row:
            return {"applied": False, "reason": "business_not_found", "business": None}

        existing_customer = str(row.get("stripe_customer_id") or "")
        incoming_customer = str(customer_id or "")
        if existing_customer and incoming_customer and existing_customer != incoming_customer:
            raise ValueError("El cliente de Stripe no coincide con la cuenta.")

        existing_subscription = str(row.get("stripe_subscription_id") or "")
        incoming_subscription = str(subscription_id or "")
        if (
            existing_subscription
            and incoming_subscription
            and existing_subscription != incoming_subscription
            and not allow_subscription_change
        ):
            return {
                "applied": False,
                "reason": "subscription_mismatch",
                "business": dict(row),
            }

        current_order = (
            int(row.get("stripe_event_created_at") or 0),
            int(row.get("stripe_event_priority") or 0),
            str(row.get("stripe_event_id") or ""),
        )
        incoming_order = (created_at, priority, event_id)
        if incoming_order <= current_order:
            return {
                "applied": False,
                "reason": "stale_event",
                "business": dict(row),
            }

        # Checkout solo enlaza identificadores. Si llega en paralelo o unos
        # segundos despues de la evidencia de pago, nunca puede degradar una
        # suscripcion que ya quedo activa. La decision se toma bajo el mismo
        # bloqueo de fila para no depender de una lectura previa obsoleta.
        current_status = str(row.get("subscription_status") or "")
        if priority == 10 and status == "pending" and current_status in {
            "active", "trialing",
        }:
            status = current_status

        fields = [
            "subscription_status=?",
            "stripe_event_created_at=?",
            "stripe_event_priority=?",
            "stripe_event_id=?",
        ]
        params: list = [status, created_at, priority, event_id]
        for column, value in (
            ("plan", plan),
            ("stripe_customer_id", customer_id),
            ("stripe_subscription_id", subscription_id),
        ):
            if value is not None:
                fields.append(f"{column}=?")
                params.append(value)
        params.append(business_id)
        conn.execute(
            f"UPDATE businesses SET {', '.join(fields)} WHERE id=?", params
        )
        updated = conn.execute(
            "SELECT * FROM businesses WHERE id=?", (business_id,)
        ).fetchone()
        return {"applied": True, "reason": "applied", "business": dict(updated)}


def reconcile_stripe_subscription(
    business_id: int,
    *,
    status: str,
    plan: str,
    customer_id: str,
    subscription_id: str,
) -> dict | None:
    """Recupera un estado activo desde una consulta autenticada a Stripe.

    No sustituye los webhooks: solo repara su entrega concurrente o perdida y
    exige que cliente y suscripcion coincidan con los ya enlazados a la cuenta.
    """
    if status not in {"active", "trialing"}:
        raise ValueError("La reconciliacion solo acepta suscripciones activas.")
    from .adapters.billing import PLANS

    if plan not in PLANS or not customer_id or not subscription_id:
        raise ValueError("Evidencia Stripe incompleta.")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        row = conn.execute(
            "SELECT * FROM businesses WHERE id=?" + lock, (business_id,)
        ).fetchone()
        if not row:
            return None
        if str(row.get("stripe_customer_id") or "") != customer_id:
            raise ValueError("El cliente de Stripe no coincide con la cuenta.")
        if str(row.get("stripe_subscription_id") or "") != subscription_id:
            raise ValueError("La suscripcion de Stripe no coincide con la cuenta.")
        conn.execute(
            "UPDATE businesses SET subscription_status=?, plan=? WHERE id=?",
            (status, plan, business_id),
        )
        updated = conn.execute(
            "SELECT * FROM businesses WHERE id=?", (business_id,)
        ).fetchone()
        return dict(updated)


def mark_business_as_demo(business_id: int) -> dict | None:
    """Convierte una empresa ficticia en escaparate persistente de solo lectura."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET is_demo=TRUE WHERE id=?", (business_id,)
        )
    return get_business(business_id)


def get_business_by_stripe_customer(customer_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM businesses WHERE stripe_customer_id=?",
                           (customer_id,)).fetchone()
        return dict(row) if row else None


def subscription_allows_access(business: dict | None) -> bool:
    """Indica si la cuenta puede modificar o automatizar el negocio.

    Una prueba vigente conserva el producto completo. Al terminar, la información
    sigue visible, pero las escrituras y automatizaciones exigen suscripción activa.
    """
    if not business:
        return False
    if business.get("is_demo"):
        return False
    status = business.get("subscription_status") or "trial"
    if status in {"active", "trialing"}:
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


# ------------------------------------- WhatsApp multicanal y recepción ---
def _wa_id(value: str | None) -> str:
    digits = "".join(char for char in str(value or "") if char.isdigit())
    return digits[2:] if digits.startswith("00") else digits


def create_whatsapp_connection(
    business_id: int,
    *,
    waba_id: str,
    phone_number_id: str,
    display_phone: str | None = None,
    verified_name: str | None = None,
    status: str = "pending",
    receptionist_enabled: bool = False,
) -> dict:
    """Registra un número empresarial sin almacenar credenciales del proveedor."""
    if not get_business(business_id):
        raise ValueError("El negocio no existe.")
    waba_id = _wa_id(waba_id)
    phone_number_id = _wa_id(phone_number_id)
    if not waba_id or not phone_number_id:
        raise ValueError("Faltan los identificadores de la cuenta de WhatsApp.")
    if status not in {"pending", "active", "paused", "error", "revoked"}:
        raise ValueError("El estado de la conexión no es válido.")
    now = _now()
    with get_conn() as conn:
        try:
            row = conn.execute(
                "INSERT INTO whatsapp_connections "
                "(business_id, mode, waba_id, phone_number_id, display_phone, "
                "verified_name, status, receptionist_enabled, created_at, updated_at) "
                "VALUES (?, 'business', ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (
                    business_id, waba_id, phone_number_id,
                    str(display_phone or "").strip() or None,
                    str(verified_name or "").strip()[:160] or None,
                    status, bool(receptionist_enabled), now, now,
                ),
            ).fetchone()
        except IntegrityError as exc:
            raise ValueError("Ese número de WhatsApp ya está conectado.") from exc
        connection_id = row["id"]
    return get_whatsapp_connection(connection_id, business_id)


def get_whatsapp_connection(connection_id: int, business_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_connections WHERE id=? AND business_id=?",
            (connection_id, business_id),
        ).fetchone()
    return dict(row) if row else None


def get_whatsapp_connection_by_phone_number_id(phone_number_id: str) -> dict | None:
    target = _wa_id(phone_number_id)
    if not target:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_connections WHERE phone_number_id=? "
            "AND status='active' AND inbound_enabled=TRUE",
            (target,),
        ).fetchone()
    return dict(row) if row else None


def list_whatsapp_connections(business_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM whatsapp_connections WHERE business_id=? "
            "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, id",
            (business_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def update_whatsapp_connection(
    connection_id: int,
    business_id: int,
    *,
    status: str | None = None,
    receptionist_enabled: bool | None = None,
    inbound_enabled: bool | None = None,
    outbound_enabled: bool | None = None,
) -> dict | None:
    if not get_whatsapp_connection(connection_id, business_id):
        return None
    fields = ["updated_at=?"]
    params: list[Any] = [_now()]
    if status is not None:
        if status not in {"pending", "active", "paused", "error", "revoked"}:
            raise ValueError("El estado de la conexión no es válido.")
        fields.append("status=?")
        params.append(status)
    for key, value in (
        ("receptionist_enabled", receptionist_enabled),
        ("inbound_enabled", inbound_enabled),
        ("outbound_enabled", outbound_enabled),
    ):
        if value is not None:
            fields.append(f"{key}=?")
            params.append(bool(value))
    params.extend((connection_id, business_id))
    with get_conn() as conn:
        conn.execute(
            f"UPDATE whatsapp_connections SET {', '.join(fields)} "
            "WHERE id=? AND business_id=?",
            tuple(params),
        )
    return get_whatsapp_connection(connection_id, business_id)


def _clients_by_phone(conn, business_id: int, phone: str) -> list[dict]:
    target = normalize_phone(phone)
    if len(target) != 9:
        return []
    rows = conn.execute(
        "SELECT * FROM clients WHERE business_id=? AND phone IS NOT NULL ORDER BY id",
        (business_id,),
    ).fetchall()
    return [dict(row) for row in rows if normalize_phone(row["phone"]) == target]


def _leads_by_phone(conn, business_id: int, phone: str) -> list[dict]:
    target = normalize_phone(phone)
    if len(target) != 9:
        return []
    rows = conn.execute(
        "SELECT * FROM leads WHERE business_id=? AND phone IS NOT NULL "
        "AND status NOT IN ('ganado','perdido') ORDER BY id",
        (business_id,),
    ).fetchall()
    return [dict(row) for row in rows if normalize_phone(row["phone"]) == target]


def ensure_whatsapp_customer_contact(
    connection_id: int,
    business_id: int,
    sender_phone: str,
    display_name: str | None = None,
) -> dict:
    """Crea una identidad externa acotada al número empresarial receptor."""
    connection = get_whatsapp_connection(connection_id, business_id)
    if not connection or connection.get("status") != "active":
        raise ValueError("La conexión de WhatsApp no está activa.")
    wa_id = _wa_id(sender_phone)
    phone_norm = normalize_phone(sender_phone)
    if not wa_id or len(phone_norm) != 9:
        raise ValueError("El remitente de WhatsApp no es válido.")
    clean_name = str(display_name or "").strip()[:160]
    with get_conn() as conn:
        current = conn.execute(
            "SELECT * FROM whatsapp_contacts WHERE connection_id=? AND wa_id=?",
            (connection_id, wa_id),
        ).fetchone()
        if current:
            if clean_name and clean_name != current.get("display_name"):
                conn.execute(
                    "UPDATE whatsapp_contacts SET display_name=?, updated_at=? "
                    "WHERE id=? AND business_id=?",
                    (clean_name, _now(), current["id"], business_id),
                )
            saved = conn.execute(
                "SELECT * FROM whatsapp_contacts WHERE id=? AND business_id=?",
                (current["id"], business_id),
            ).fetchone()
            return dict(saved)

        clients = _clients_by_phone(conn, business_id, sender_phone)
        client_id = clients[0]["id"] if len(clients) == 1 else None
        leads = _leads_by_phone(conn, business_id, sender_phone)
        lead_id = leads[0]["id"] if len(leads) == 1 else None
        if client_id is None and lead_id is None:
            lead_name = clean_name or f"Contacto WhatsApp · {phone_norm[-4:]}"
            lead = conn.execute(
                "INSERT INTO leads (business_id, name, phone, source, status, note, "
                "created_at) VALUES (?, ?, ?, 'WhatsApp del negocio', 'nuevo', ?, ?) "
                "RETURNING id",
                (
                    business_id, lead_name, sender_phone,
                    "Entrada creada por Noesis; pendiente de revisar y convertir.",
                    _now(),
                ),
            ).fetchone()
            lead_id = lead["id"]
        row = conn.execute(
            "INSERT INTO whatsapp_contacts "
            "(business_id, connection_id, wa_id, phone_norm, display_name, client_id, "
            "lead_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "RETURNING id",
            (
                business_id, connection_id, wa_id, phone_norm, clean_name or None,
                client_id, lead_id, _now(), _now(),
            ),
        ).fetchone()
        saved = conn.execute(
            "SELECT * FROM whatsapp_contacts WHERE id=? AND business_id=?",
            (row["id"], business_id),
        ).fetchone()
    return dict(saved)


def get_or_create_whatsapp_conversation(
    connection_id: int, contact_id: int, business_id: int
) -> dict:
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_conversations WHERE connection_id=? "
            "AND contact_id=? AND business_id=?",
            (connection_id, contact_id, business_id),
        ).fetchone()
        if not row:
            inserted = conn.execute(
                "INSERT INTO whatsapp_conversations "
                "(business_id, connection_id, contact_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?) RETURNING id",
                (business_id, connection_id, contact_id, now, now),
            ).fetchone()
            row = conn.execute(
                "SELECT * FROM whatsapp_conversations WHERE id=? AND business_id=?",
                (inserted["id"], business_id),
            ).fetchone()
    return dict(row)


def set_whatsapp_contact_consent(
    contact_id: int, business_id: int, consent_status: str
) -> dict | None:
    if consent_status not in {"active", "opted_out", "blocked"}:
        raise ValueError("El estado de consentimiento no es válido.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE whatsapp_contacts SET consent_status=?, updated_at=? "
            "WHERE id=? AND business_id=?",
            (consent_status, _now(), contact_id, business_id),
        )
        row = conn.execute(
            "SELECT * FROM whatsapp_contacts WHERE id=? AND business_id=?",
            (contact_id, business_id),
        ).fetchone()
    return dict(row) if row else None


def update_whatsapp_conversation(
    conversation_id: int,
    business_id: int,
    *,
    status: str | None = None,
    human_handoff: bool | None = None,
    summary: str | None = None,
) -> dict | None:
    if status is not None and status not in {
        "open", "waiting_owner", "resolved", "archived"
    }:
        raise ValueError("El estado de conversación no es válido.")
    fields = ["updated_at=?"]
    params: list[Any] = [_now()]
    if status is not None:
        fields.append("status=?")
        params.append(status)
    if human_handoff is not None:
        fields.append("human_handoff=?")
        params.append(bool(human_handoff))
    if summary is not None:
        fields.append("summary=?")
        params.append(str(summary).strip()[:1000] or None)
    params.extend((conversation_id, business_id))
    with get_conn() as conn:
        conn.execute(
            f"UPDATE whatsapp_conversations SET {', '.join(fields)} "
            "WHERE id=? AND business_id=?",
            tuple(params),
        )
        row = conn.execute(
            "SELECT * FROM whatsapp_conversations WHERE id=? AND business_id=?",
            (conversation_id, business_id),
        ).fetchone()
    return dict(row) if row else None


def get_whatsapp_conversation(
    conversation_id: int, business_id: int
) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT v.*, c.wa_id, c.phone_norm, c.display_name, c.consent_status "
            "FROM whatsapp_conversations v JOIN whatsapp_contacts c "
            "ON c.id=v.contact_id AND c.business_id=v.business_id "
            "WHERE v.id=? AND v.business_id=?",
            (conversation_id, business_id),
        ).fetchone()
    return dict(row) if row else None


def record_whatsapp_inbox(
    *,
    business_id: int,
    connection_id: int,
    conversation_id: int,
    contact_id: int,
    meta_message_id: str,
    sender_phone: str,
    message_type: str,
    text_body: str | None = None,
) -> dict:
    if message_type not in {"text", "audio", "image", "document", "interactive", "unknown"}:
        message_type = "unknown"
    now = _now()
    try:
        with get_conn() as conn:
            row = conn.execute(
                "INSERT INTO whatsapp_inbox "
                "(business_id, connection_id, conversation_id, contact_id, "
                "meta_message_id, sender_phone, actor_role, message_type, text_body, "
                "received_at) VALUES (?, ?, ?, ?, ?, ?, 'customer', ?, ?, ?) "
                "RETURNING id",
                (
                    business_id, connection_id, conversation_id, contact_id,
                    str(meta_message_id)[:200], sender_phone, message_type,
                    str(text_body or "")[:4000] or None, now,
                ),
            ).fetchone()
            conn.execute(
                "UPDATE whatsapp_conversations SET last_inbound_at=?, updated_at=? "
                "WHERE id=? AND business_id=?",
                (now, now, conversation_id, business_id),
            )
            inbox_id = row["id"]
    except IntegrityError:
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM whatsapp_inbox WHERE meta_message_id=?",
                (str(meta_message_id)[:200],),
            ).fetchone()
        if not existing or existing.get("business_id") != business_id:
            raise
        return dict(existing)
    return get_whatsapp_inbox(inbox_id, business_id)


def get_whatsapp_inbox(inbox_id: int, business_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_inbox WHERE id=? AND business_id=?",
            (inbox_id, business_id),
        ).fetchone()
    return dict(row) if row else None


def finish_whatsapp_inbox(
    inbox_id: int,
    business_id: int,
    *,
    status: str = "processed",
    document_id: int | None = None,
    job_id: int | None = None,
    error: str | None = None,
) -> dict | None:
    if status not in {"processed", "failed", "ignored"}:
        raise ValueError("El estado de entrada no es válido.")
    if document_id is not None:
        from .documents import repo as document_repo
        if not document_repo.get(document_id, business_id):
            raise ValueError("El documento no pertenece a este negocio.")
    if job_id is not None and not get_job(job_id, business_id):
        raise ValueError("El trabajo no pertenece a este negocio.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE whatsapp_inbox SET processing_status=?, document_id=?, job_id=?, error=?, "
            "processed_at=? WHERE id=? AND business_id=?",
            (
                status, document_id, job_id, str(error or "")[:1000] or None,
                _now(), inbox_id, business_id,
            ),
        )
    return get_whatsapp_inbox(inbox_id, business_id)


def list_whatsapp_inbox(business_id: int, *, limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT i.*, c.display_name, c.client_id, c.lead_id, "
            "v.status AS conversation_status, v.human_handoff "
            "FROM whatsapp_inbox i "
            "JOIN whatsapp_contacts c ON c.id=i.contact_id AND c.business_id=i.business_id "
            "JOIN whatsapp_conversations v ON v.id=i.conversation_id "
            "AND v.business_id=i.business_id WHERE i.business_id=? "
            "ORDER BY i.received_at DESC, i.id DESC LIMIT ?",
            (business_id, max(1, min(int(limit), 500))),
        ).fetchall()
    return [dict(row) for row in rows]


def create_worker_submission(
    business_id: int,
    worker_id: int,
    *,
    kind: str,
    description: str,
    job_id: int | None = None,
    document_id: int | None = None,
    amount: float | None = None,
) -> dict:
    """Registra una aportación de campo sin convertirla en coste definitivo."""
    worker = get_worker(worker_id, business_id)
    if not worker or not worker.get("active"):
        raise ValueError("El trabajador no está disponible.")
    if kind not in {"cost", "document", "question", "blocker", "note"}:
        raise ValueError("El tipo de aportación no es válido.")
    description = str(description or "").strip()
    if not description or len(description) > 2000:
        raise ValueError("La aportación necesita una descripción válida.")
    job = None
    project_id = None
    if job_id is not None:
        job = get_job(int(job_id), business_id)
        if not job or not _worker_can_access_job(job, worker_id, business_id):
            raise ValueError("Ese trabajo no está asignado a esta persona.")
        job_id = job["id"]
        project_id = job.get("project_id")
    if document_id is not None:
        from .documents import repo as document_repo
        if not document_repo.get(int(document_id), business_id):
            raise ValueError("El documento no pertenece a este negocio.")
        document_id = int(document_id)
    if amount is not None:
        amount = round(float(amount), 2)
        if amount < 0:
            raise ValueError("El importe no puede ser negativo.")
    if kind == "cost":
        if not worker.get("can_submit_costs"):
            raise ValueError("No tienes permiso para enviar costes.")
        if job is None:
            raise ValueError("Indica el trabajo al que corresponde el coste.")
        if amount is None:
            raise ValueError("Indica el importe del coste.")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO worker_submissions "
            "(business_id, worker_id, job_id, project_id, document_id, kind, "
            "description, amount, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "RETURNING id",
            (
                business_id, worker_id, job_id, project_id, document_id, kind,
                description, amount, _now(),
            ),
        ).fetchone()
        saved = conn.execute(
            "SELECT * FROM worker_submissions WHERE id=? AND business_id=?",
            (row["id"], business_id),
        ).fetchone()
    return dict(saved)


def list_worker_submissions(
    business_id: int, *, status: str | None = None, limit: int = 100
) -> list[dict]:
    params: list[Any] = [business_id]
    where = ""
    if status:
        if status not in {"pending", "accepted", "rejected", "resolved"}:
            raise ValueError("El estado de aportación no es válido.")
        where = " AND s.status=?"
        params.append(status)
    params.append(max(1, min(int(limit), 500)))
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.*, w.name AS worker_name, j.description AS job_description, "
            "p.name AS project_name FROM worker_submissions s "
            "JOIN workers w ON w.id=s.worker_id AND w.business_id=s.business_id "
            "LEFT JOIN jobs j ON j.id=s.job_id AND j.business_id=s.business_id "
            "LEFT JOIN projects p ON p.id=s.project_id AND p.business_id=s.business_id "
            "WHERE s.business_id=?" + where
            + " ORDER BY CASE s.status WHEN 'pending' THEN 0 ELSE 1 END, "
            "s.created_at DESC, s.id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return [dict(row) for row in rows]


def resolve_worker_submission(
    submission_id: int,
    business_id: int,
    *,
    decision: str,
    resolution_note: str | None = None,
) -> dict | None:
    """Acepta o descarta una aportación; un coste solo se aplica una vez."""
    if decision not in {"accepted", "rejected", "resolved"}:
        raise ValueError("La decisión no es válida.")
    material_added = False
    with get_conn() as conn:
        lock = " FOR UPDATE" if conn.dialect == "postgres" else ""
        if conn.dialect == "sqlite":
            conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM worker_submissions WHERE id=? AND business_id=?" + lock,
            (submission_id, business_id),
        ).fetchone()
        if not row:
            return None
        submission = dict(row)
        if submission["status"] != "pending":
            return submission
        material_id = submission.get("applied_material_id")
        if decision == "accepted" and submission["kind"] == "cost":
            material = conn.execute(
                "INSERT INTO job_materials (business_id, job_id, worker_id, "
                "description, quantity, unit_cost, total, created_at) "
                "VALUES (?, ?, ?, ?, 1, ?, ?, ?) RETURNING id",
                (
                    business_id, submission["job_id"], submission["worker_id"],
                    submission["description"], submission["amount"],
                    submission["amount"], _now(),
                ),
            ).fetchone()
            material_id = material["id"]
            material_added = True
        conn.execute(
            "UPDATE worker_submissions SET status=?, resolution_note=?, "
            "applied_material_id=?, resolved_at=? WHERE id=? AND business_id=? "
            "AND status='pending'",
            (
                decision, str(resolution_note or "").strip()[:1000] or None,
                material_id, _now(), submission_id, business_id,
            ),
        )
        saved = conn.execute(
            "SELECT * FROM worker_submissions WHERE id=? AND business_id=?",
            (submission_id, business_id),
        ).fetchone()
    if material_added:
        record_product_event(business_id, "job_material_added")
    return dict(saved)


def enqueue_whatsapp_message(
    *,
    business_id: int | None,
    connection_id: int | None = None,
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
    if connection_id is not None:
        if business_id is None or not get_whatsapp_connection(connection_id, business_id):
            raise ValueError("La conexión de WhatsApp no pertenece al negocio.")
    created_at = now or _now()
    try:
        with get_conn() as conn:
            row = conn.execute(
                "INSERT INTO whatsapp_outbox "
                "(business_id, connection_id, to_phone, message_type, text_body, template_name, "
                "template_language, template_params, idempotency_key, status, "
                "attempts, max_attempts, next_attempt_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, ?, ?, ?, ?) "
                "RETURNING id",
                (
                    business_id, connection_id, to_phone, message_type, text_body, template_name,
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
            if existing.get("connection_id") != connection_id:
                raise ValueError(
                    "La clave idempotente pertenece a otro canal de WhatsApp."
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


def mark_whatsapp_blocked(message_id: int, reason: str, updated_at: str) -> None:
    """Cancela un envío reclamado que ya no está autorizado por la cuenta."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE whatsapp_outbox SET status='failed', last_error=?, "
            "locked_at=NULL, updated_at=? WHERE id=? AND status='processing'",
            (reason[:1000], updated_at, message_id),
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
    with get_conn() as conn:
        work_completions = [dict(row) for row in conn.execute(
            "SELECT jc.id, jc.job_id, jc.status, jc.summary, jc.customer_name, "
            "jc.customer_note, jc.created_at, jc.confirmed_at, jc.rejected_at, "
            "j.description, j.scheduled_for, p.name AS project_name "
            "FROM job_completions jc JOIN jobs j ON j.id=jc.job_id "
            "AND j.business_id=jc.business_id LEFT JOIN projects p "
            "ON p.id=j.project_id AND p.business_id=j.business_id "
            "WHERE jc.business_id=? AND j.client_id=? "
            "ORDER BY jc.created_at DESC, jc.id DESC",
            (business_id, client_id),
        ).fetchall()]
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
                     "payment_note": biz.get("payment_note"),
                     "quote_terms": biz.get("quote_terms")},
        "client": {"id": client["id"], "name": client.get("name")},
        "quotes": quotes,
        "invoices": invoices,
        "work_completions": work_completions,
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
    """Tokens, proveedores y coste estimado por negocio en un mes."""
    month = month or date.today().strftime("%Y-%m")
    per_business: dict[int, dict] = {}
    total = {
        "calls": 0,
        "input": 0,
        "output": 0,
        "extractions": 0,
        "estimated_cost_usd": 0.0,
        "providers": {},
    }
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
            {
                "calls": 0,
                "input": 0,
                "output": 0,
                "extractions": 0,
                "estimated_cost_usd": 0.0,
                "providers": {},
            },
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
        cost = float(data.get("estimated_cost_usd") or 0)
        provider = str(data.get("provider") or "desconocido")
        entry["estimated_cost_usd"] += cost
        entry["providers"][provider] = entry["providers"].get(provider, 0) + 1
        total["calls"] += 1
        total["input"] += int(data.get("in") or 0)
        total["output"] += int(data.get("out") or 0)
        total["estimated_cost_usd"] += cost
        total["providers"][provider] = total["providers"].get(provider, 0) + 1
    total["estimated_cost_usd"] = round(total["estimated_cost_usd"], 6)
    for entry in per_business.values():
        entry["estimated_cost_usd"] = round(
            entry["estimated_cost_usd"], 6
        )
    return {"month": month, "total": total, "per_business": per_business}


def admin_alerts() -> list[dict]:
    """Alarmas operativas para el fundador: qué está fallando y dónde llamar."""
    alerts: list[dict] = []
    with get_conn() as conn:
        wa_failed = conn.execute(
            "SELECT COUNT(*) AS n FROM whatsapp_outbox WHERE status='failed' "
            "AND COALESCE(last_error, '')<>"
            "'Cancelado al desconectar WhatsApp por el usuario.'"
        ).fetchone()["n"]
        wa_stuck = conn.execute(
            "SELECT COUNT(*) AS n FROM whatsapp_outbox "
            "WHERE status IN ('queued','retrying') AND attempts>=3"
        ).fetchone()["n"]
        email_failed = conn.execute(
            "SELECT COUNT(*) AS n FROM email_outbox WHERE status='failed'"
        ).fetchone()["n"]
        email_stuck = conn.execute(
            "SELECT COUNT(*) AS n FROM email_outbox "
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
    if email_failed:
        alerts.append({
            "level": "rojo", "area": "Correo",
            "text": f"{email_failed} correo(s) agotaron los reintentos.",
        })
    if email_stuck:
        alerts.append({
            "level": "ambar", "area": "Correo",
            "text": f"{email_stuck} correo(s) llevan 3+ intentos sin salir.",
        })
    verifactu = verifactu_queue_health()
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
    if verifactu.get("vencidas") and not verifactu.get("agotado"):
        alerts.append({
            "level": "ambar", "area": "Veri*Factu",
            "text": (
                f"{verifactu['vencidas']} registro(s) vencidos esperan remisión."
            ),
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


PLATFORM_COST_CATEGORIES = {
    "hosting": "Infraestructura y hosting",
    "ai": "IA y extracción",
    "whatsapp": "WhatsApp",
    "email": "Correo",
    "payments": "Pagos y comisiones",
    "security_storage": "Seguridad y copias",
    "support": "Soporte y onboarding",
    "legal_admin": "Legal y administración",
    "marketing": "Marketing y ventas",
    "other": "Otros",
}
PLATFORM_COST_SOURCES = {"actual", "forecast", "adjustment"}


def add_platform_cost(period: str, category: str, amount_eur, *, source: str,
                      note: str = "", created_by_user_id: int | None = None) -> dict:
    period = str(period or "").strip()
    if not re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", period):
        raise ValueError("El período debe tener formato AAAA-MM.")
    if category not in PLATFORM_COST_CATEGORIES:
        raise ValueError("La categoría de coste no es válida.")
    if source not in PLATFORM_COST_SOURCES:
        raise ValueError("El origen del coste no es válido.")
    try:
        amount = Decimal(str(amount_eur)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except Exception as exc:  # noqa: BLE001
        raise ValueError("El importe no es válido.") from exc
    if amount == 0 or abs(amount) > Decimal("1000000"):
        raise ValueError("El coste debe ser distinto de cero y razonable.")
    if source != "adjustment" and amount < 0:
        raise ValueError("Solo los ajustes pueden tener importe negativo.")
    note = " ".join(str(note or "").split())[:500]
    if source == "adjustment" and len(note) < 10:
        raise ValueError("Un ajuste necesita explicar qué corrige.")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO platform_cost_entries "
            "(period, category, amount_eur, source, note, created_by_user_id, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (period, category, float(amount), source, note or None,
             created_by_user_id, _now()),
        ).fetchone()
        entry = conn.execute(
            "SELECT * FROM platform_cost_entries WHERE id=?", (row["id"],)
        ).fetchone()
    return dict(entry)


def platform_cost_summary(period: str) -> dict:
    if not re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", str(period or "")):
        raise ValueError("El período debe tener formato AAAA-MM.")
    with get_conn() as conn:
        entries = [dict(row) for row in conn.execute(
            "SELECT * FROM platform_cost_entries WHERE period=? ORDER BY id DESC",
            (period,),
        ).fetchall()]
    totals = {source: 0.0 for source in PLATFORM_COST_SOURCES}
    by_category: dict[str, float] = {}
    for entry in entries:
        amount = float(entry["amount_eur"] or 0)
        totals[entry["source"]] = round(totals.get(entry["source"], 0) + amount, 2)
        if entry["source"] in {"actual", "adjustment"}:
            by_category[entry["category"]] = round(
                by_category.get(entry["category"], 0) + amount, 2
            )
    return {
        "period": period, "entries": entries, "totals": totals,
        "observed_total": round(totals["actual"] + totals["adjustment"], 2),
        "forecast_total": totals["forecast"],
        "by_category": by_category,
        "category_labels": PLATFORM_COST_CATEGORIES,
        "has_observed_data": any(
            entry["source"] in {"actual", "adjustment"} for entry in entries
        ),
    }


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
    # El chat ya registra el coste por modelo/proveedor. La conversión USD→EUR es
    # solo una aproximación operativa; la factura del proveedor sigue mandando.
    ai_cost_eur = round(
        ai_total["estimated_cost_usd"] * 0.92
        + ai_total["extractions"] * 0.014,
        2,
    )
    margen_pct = round((mrr - ai_cost_eur) / mrr * 100) if mrr else None
    altas_mes = altas_by_month.get(today.strftime("%Y-%m"), 0)
    en_riesgo = len([
        b for b in biz if b["activated"] and (b["days_inactive"] or 0) >= 14
    ])
    vq = verifactu_queue_health()
    backup = latest_backup_run()
    alerts = admin_alerts()
    backup_text = {
        "ok": "última copia verificada OK",
        "error": "la última copia FALLÓ",
    }.get((backup or {}).get("status"), "sin copias todavía")
    cost_ledger = platform_cost_summary(today.strftime("%Y-%m"))
    observed_costs = cost_ledger["observed_total"]
    observed_margin = (
        round((mrr - observed_costs) / mrr * 100, 1)
        if mrr and cost_ledger["has_observed_data"] else None
    )
    finanzas = {
        "mrr": mrr,
        "run_rate": mrr * 12,
        "ai_cost_eur": ai_cost_eur,
        "margen_pct": margen_pct,
        "cost_ledger": cost_ledger,
        "observed_costs": observed_costs,
        "observed_margin_pct": observed_margin,
        "observed_contribution": (
            round(mrr - observed_costs, 2)
            if cost_ledger["has_observed_data"] else None
        ),
        "observed_cost_per_active_account": (
            round(observed_costs / len(activos), 2)
            if activos and cost_ledger["has_observed_data"] else None
        ),
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
            f"{vq['pendiente']} pendiente(s), {vq['vencidas']} vencida(s), "
            f"{vq['rechazado']} rechazada(s). "
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


SUPPORT_CONSENT_VERSION = "support-access-v1"
SUPPORT_SCOPES = {
    "configuration": "Configuración de la cuenta",
    "document_metadata": "Organización de documentos",
    "draft_records": "Borradores no emitidos",
    "integrations": "Diagnóstico de integraciones",
}


def _support_grant_dict(row) -> dict | None:
    if not row:
        return None
    grant = dict(row)
    try:
        scopes = json.loads(grant.pop("scopes_json") or "[]")
    except (TypeError, ValueError):
        scopes = []
    grant["scopes"] = [scope for scope in scopes if scope in SUPPORT_SCOPES]
    grant["scope_labels"] = [SUPPORT_SCOPES[scope] for scope in grant["scopes"]]
    return grant


def _support_admin_actor(actor_user_id: int) -> dict:
    actor = get_user(actor_user_id)
    if not actor or not (
        bool(actor.get("is_admin")) or config.is_admin_email(actor.get("email"))
    ):
        raise PermissionError("Solo administración puede aplicar esta corrección.")
    return actor


def _support_grant_with_scope(conn, business_id: int, scope: str, now: str) -> dict:
    """Revalida permiso dentro de la transacción que realizará el cambio."""
    conn.execute(
        "UPDATE support_access_grants SET status='expired' "
        "WHERE business_id=? AND status='active' AND expires_at<=?",
        (business_id, now),
    )
    row = conn.execute(
        "SELECT * FROM support_access_grants WHERE business_id=? "
        "AND status='active' AND expires_at>? ORDER BY id DESC LIMIT 1",
        (business_id, now),
    ).fetchone()
    grant = _support_grant_dict(row)
    if not grant or scope not in grant["scopes"]:
        raise PermissionError(
            "El titular no ha autorizado esta corrección o el acceso ha caducado."
        )
    return grant


def active_support_grant(business_id: int) -> dict | None:
    """Autorización vigente del titular; caduca aunque nadie abra el panel admin."""
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "UPDATE support_access_grants SET status='expired' "
            "WHERE business_id=? AND status='active' AND expires_at<=?",
            (business_id, now),
        )
        row = conn.execute(
            "SELECT * FROM support_access_grants WHERE business_id=? "
            "AND status='active' AND expires_at>? ORDER BY id DESC LIMIT 1",
            (business_id, now),
        ).fetchone()
    return _support_grant_dict(row)


def create_support_grant(business_id: int, user_id: int, *, purpose: str,
                         scopes: list[str], duration_hours: int) -> dict:
    """El titular abre una ventana acotada; nunca la puede crear administración."""
    user = get_user(user_id)
    business = get_business(business_id)
    is_owner = bool(
        user and business
        and int(user.get("business_id") or 0) == int(business_id)
        and str(user.get("email") or "").strip().lower()
        == str(business.get("owner_email") or "").strip().lower()
    )
    if not is_owner:
        raise ValueError("Solo el titular de la cuenta puede autorizar soporte.")
    purpose = " ".join(str(purpose or "").split())
    if len(purpose) < 10 or len(purpose) > 500:
        raise ValueError("Explica el motivo del soporte (entre 10 y 500 caracteres).")
    clean_scopes = sorted({str(scope) for scope in scopes if scope in SUPPORT_SCOPES})
    if not clean_scopes:
        raise ValueError("Selecciona al menos un permiso para soporte.")
    try:
        duration_hours = int(duration_hours)
    except (TypeError, ValueError) as exc:
        raise ValueError("La duración del acceso no es válida.") from exc
    if duration_hours not in {1, 4, 24, 72}:
        raise ValueError("La duración debe ser de 1, 4, 24 o 72 horas.")
    now = _now()
    expires_at = (datetime.now() + timedelta(hours=duration_hours)).isoformat(
        timespec="seconds"
    )
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE support_access_grants SET status='revoked', revoked_at=? "
            "WHERE business_id=? AND status='active'",
            (now, business_id),
        )
        row = conn.execute(
            "INSERT INTO support_access_grants "
            "(business_id, created_by_user_id, purpose, scopes_json, consent_version, "
            "status, expires_at, created_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?) "
            "RETURNING id",
            (business_id, user_id, purpose, json.dumps(clean_scopes),
             SUPPORT_CONSENT_VERSION, expires_at, now),
        ).fetchone()
        grant_id = row["id"]
    record_security_event(
        "support.access_granted", area="support", actor_user_id=user_id,
        subject_business_id=business_id,
        metadata={"grant_id": grant_id, "scopes": clean_scopes,
                  "duration_hours": duration_hours},
    )
    return active_support_grant(business_id)


def revoke_support_grant(business_id: int, user_id: int) -> bool:
    user = get_user(user_id)
    business = get_business(business_id)
    is_owner = bool(
        user and business
        and int(user.get("business_id") or 0) == int(business_id)
        and str(user.get("email") or "").strip().lower()
        == str(business.get("owner_email") or "").strip().lower()
    )
    if not is_owner:
        raise ValueError("Solo el titular de la cuenta puede revocar soporte.")
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE support_access_grants SET status='revoked', revoked_at=? "
            "WHERE business_id=? AND status='active'",
            (now, business_id),
        )
    if cur.rowcount:
        record_security_event(
            "support.access_revoked", area="support", actor_user_id=user_id,
            subject_business_id=business_id,
        )
    return bool(cur.rowcount)


def admin_support_snapshot(business_id: int) -> dict | None:
    """Diagnóstico técnico por cuenta sin exponer contenido operativo.

    Devuelve estados y recuentos. No devuelve nombres de clientes, conceptos,
    mensajes, documentos, importes de facturas ni credenciales.
    """
    business = get_business(business_id)
    if not business:
        return None

    def _grouped(conn, table: str, column: str) -> dict[str, int]:
        rows = conn.execute(
            f"SELECT {column} AS value, COUNT(*) AS total FROM {table} "
            f"WHERE business_id=? GROUP BY {column}",
            (business_id,),
        ).fetchall()
        return {str(row["value"] or "sin_estado"): int(row["total"]) for row in rows}

    with get_conn() as conn:
        counts = conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM users WHERE business_id=?) AS users, "
            "(SELECT COUNT(*) FROM clients WHERE business_id=?) AS clients, "
            "(SELECT COUNT(*) FROM jobs WHERE business_id=?) AS jobs, "
            "(SELECT COUNT(*) FROM projects WHERE business_id=?) AS projects, "
            "(SELECT COUNT(*) FROM workers WHERE business_id=?) AS workers, "
            "(SELECT COUNT(*) FROM invoices WHERE business_id=?) AS invoices, "
            "(SELECT COUNT(*) FROM expenses WHERE business_id=?) AS expenses, "
            "(SELECT COUNT(*) FROM received_invoices WHERE business_id=?) "
            "AS received_invoices, "
            "(SELECT COUNT(*) FROM documents WHERE business_id=?) AS documents, "
            "(SELECT COUNT(*) FROM documents WHERE business_id=? "
            "AND doc_status='pendiente_revisar') AS documents_pending, "
            "(SELECT COUNT(*) FROM gestoria_business_access WHERE business_id=? "
            "AND revoked_at IS NULL) AS gestoria_accesses",
            (business_id,) * 11,
        ).fetchone()
        queues = {
            "whatsapp": _grouped(conn, "whatsapp_outbox", "status"),
            "email": _grouped(conn, "email_outbox", "status"),
            "verifactu": _grouped(conn, "verifactu_outbox", "status"),
        }
        invoice_states = _grouped(conn, "invoices", "status")
        document_states = _grouped(conn, "documents", "doc_status")
        last_event = conn.execute(
            "SELECT event_name, created_at FROM product_events "
            "WHERE business_id=? ORDER BY id DESC LIMIT 1",
            (business_id,),
        ).fetchone()
    activation = activation_snapshot(business_id)
    return {
        "business": {
            "id": business["id"],
            "name": business["name"],
            "owner_email": business.get("owner_email"),
            "sector": business.get("sector"),
            "plan": business.get("plan"),
            "subscription_status": business.get("subscription_status"),
            "trial_ends_at": business.get("trial_ends_at"),
            "whatsapp_status": business.get("whatsapp_status"),
            "fiscal_profile_complete": bool(
                business.get("nif") and business.get("address")
            ),
            "created_at": business.get("created_at"),
        },
        "counts": dict(counts),
        "queues": queues,
        "invoice_states": invoice_states,
        "document_states": document_states,
        "activation": activation,
        "last_event": dict(last_event) if last_event else None,
        "support_grant": active_support_grant(business_id),
    }


def admin_support_document_metadata(business_id: int, *, limit: int = 100) -> dict | None:
    """Metadatos documentales visibles solo durante una autorización explícita.

    No devuelve OCR, importes, binarios, credenciales ni contenido de facturas. La
    lista está acotada para que el centro de soporte no se convierta en una copia
    alternativa del archivo del cliente.
    """
    grant = active_support_grant(business_id)
    if not grant or "document_metadata" not in grant["scopes"]:
        return None
    limit = max(1, min(int(limit), 200))
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS total FROM documents WHERE business_id=?",
            (business_id,),
        ).fetchone()["total"]
        documents = conn.execute(
            "SELECT d.id, d.filename, d.kind, d.doc_status, d.client_id, "
            "d.project_id, d.review_note, d.reviewed_at, d.invoice_id, "
            "d.received_invoice_id, d.created_at, c.name AS client_name, "
            "p.name AS project_name FROM documents d "
            "LEFT JOIN clients c ON c.id=d.client_id AND c.business_id=d.business_id "
            "LEFT JOIN projects p ON p.id=d.project_id AND p.business_id=d.business_id "
            "WHERE d.business_id=? ORDER BY d.created_at DESC, d.id DESC LIMIT ?",
            (business_id, limit),
        ).fetchall()
        clients = conn.execute(
            "SELECT id, name FROM clients WHERE business_id=? ORDER BY name LIMIT 250",
            (business_id,),
        ).fetchall()
        projects = conn.execute(
            "SELECT id, name, client_id FROM projects WHERE business_id=? "
            "ORDER BY name LIMIT 250",
            (business_id,),
        ).fetchall()
    return {
        "grant_id": grant["id"],
        "documents": [dict(row) for row in documents],
        "clients": [dict(row) for row in clients],
        "projects": [dict(row) for row in projects],
        "total": int(total or 0),
        "limit": limit,
    }


def admin_support_configuration(business_id: int) -> dict | None:
    """Configuración reversible visible solo con autorización del titular."""
    grant = active_support_grant(business_id)
    if not grant or "configuration" not in grant["scopes"]:
        return None
    business = get_business(business_id)
    if not business:
        return None
    allowed = (
        "name", "sector", "team_size", "province", "primary_goal", "language",
        "explanation_level", "invoice_template", "brand_color", "document_footer",
        "quote_terms", "default_quote_validity_days",
    )
    return {
        "grant_id": grant["id"],
        "values": {field: business.get(field) for field in allowed},
    }


def _support_value_hash(value: str | None) -> str | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


def _support_configuration_audit_state(values: dict) -> tuple[str, str, str]:
    """Antes/después seudonimizado y acotado para la bitácora de seguridad."""
    profile = json.dumps({
        "name": _support_value_hash(values.get("name")),
        "sector": _support_value_hash(values.get("sector")),
        "team": values.get("team_size"),
        "province": _support_value_hash(values.get("province")),
        "goal": values.get("primary_goal"),
    }, sort_keys=True, separators=(",", ":"))
    experience = json.dumps({
        "language": values.get("language"),
        "level": values.get("explanation_level"),
    }, sort_keys=True, separators=(",", ":"))
    branding = json.dumps({
        "template": values.get("invoice_template"),
        "color": values.get("brand_color"),
        "footer": _support_value_hash(values.get("document_footer")),
        "terms": _support_value_hash(values.get("quote_terms")),
        "validity": values.get("default_quote_validity_days"),
    }, sort_keys=True, separators=(",", ":"))
    return profile, experience, branding


def admin_update_safe_business_configuration(
    business_id: int,
    *,
    actor_user_id: int,
    name: str,
    sector: str,
    team_size: str,
    province: str | None,
    primary_goal: str,
    language: str,
    explanation_level: str,
    invoice_template: str,
    brand_color: str | None,
    document_footer: str | None,
    quote_terms: str | None,
    default_quote_validity_days: int,
    request_id: str | None = None,
) -> dict:
    """Corrige solo perfil y apariencia; excluye fiscalidad, pagos e integraciones."""
    _support_admin_actor(actor_user_id)
    name = " ".join(str(name or "").split())
    sector = " ".join(str(sector or "").split())
    province = " ".join(str(province or "").split()) or None
    if not name or len(name) > 160:
        raise ValueError("El nombre del negocio es obligatorio (máx. 160 caracteres).")
    if not sector or len(sector) > 80:
        raise ValueError("El sector es obligatorio (máx. 80 caracteres).")
    if province and len(province) > 80:
        raise ValueError("La provincia no puede superar 80 caracteres.")
    if team_size not in {"solo", "2-5", "6-10", "11+"}:
        raise ValueError("El tamaño del equipo no es válido.")
    if primary_goal not in {"facturar", "agenda", "cobros", "control"}:
        raise ValueError("El objetivo principal no es válido.")
    if language not in LANGUAGES:
        raise ValueError("Idioma no disponible.")
    if explanation_level not in EXPLANATION_LEVELS:
        raise ValueError("El nivel de explicación no es válido.")
    if invoice_template not in INVOICE_TEMPLATES:
        raise ValueError("La plantilla seleccionada no es válida.")
    brand_color = str(brand_color or "").strip() or None
    if brand_color and not _HEX_RE.match(brand_color):
        raise ValueError("El color de marca debe ser un hexadecimal tipo #14463b.")
    document_footer = str(document_footer or "").strip() or None
    quote_terms = str(quote_terms or "").strip() or None
    if document_footer and len(document_footer) > MAX_DOCUMENT_FOOTER:
        raise ValueError(
            f"El pie del documento no puede superar {MAX_DOCUMENT_FOOTER} caracteres."
        )
    if quote_terms and len(quote_terms) > MAX_QUOTE_TERMS:
        raise ValueError(
            f"Las condiciones no pueden superar {MAX_QUOTE_TERMS} caracteres."
        )
    try:
        default_quote_validity_days = int(default_quote_validity_days)
    except (TypeError, ValueError) as exc:
        raise ValueError("La validez predeterminada no es válida.") from exc
    if default_quote_validity_days not in QUOTE_VALIDITY_DAYS:
        raise ValueError("La validez debe ser de 7, 15, 30, 45, 60 o 90 días.")

    allowed = (
        "name", "sector", "team_size", "province", "primary_goal", "language",
        "explanation_level", "invoice_template", "brand_color", "document_footer",
        "quote_terms", "default_quote_validity_days",
    )
    after = {
        "name": name,
        "sector": sector,
        "team_size": team_size,
        "province": province,
        "primary_goal": primary_goal,
        "language": language,
        "explanation_level": explanation_level,
        "invoice_template": invoice_template,
        "brand_color": brand_color,
        "document_footer": document_footer,
        "quote_terms": quote_terms,
        "default_quote_validity_days": default_quote_validity_days,
    }
    now = _now()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        grant = _support_grant_with_scope(conn, business_id, "configuration", now)
        current_row = conn.execute(
            "SELECT * FROM businesses WHERE id=?", (business_id,)
        ).fetchone()
        if not current_row:
            raise ValueError("Negocio no encontrado.")
        current = dict(current_row)
        before = {field: current.get(field) for field in allowed}
        changed_fields = [field for field in allowed if before[field] != after[field]]
        if changed_fields:
            conn.execute(
                "UPDATE businesses SET name=?, sector=?, team_size=?, province=?, "
                "primary_goal=?, language=?, explanation_level=?, invoice_template=?, "
                "brand_color=?, document_footer=?, quote_terms=?, "
                "default_quote_validity_days=? WHERE id=?",
                (
                    name, sector, team_size, province, primary_goal, language,
                    explanation_level, invoice_template, brand_color,
                    document_footer, quote_terms, default_quote_validity_days,
                    business_id,
                ),
            )

    if changed_fields:
        before_profile, before_experience, before_branding = (
            _support_configuration_audit_state(before)
        )
        after_profile, after_experience, after_branding = (
            _support_configuration_audit_state(after)
        )
        record_security_event(
            "admin.support_configuration_updated",
            severity="warning",
            area="support",
            actor_user_id=actor_user_id,
            subject_business_id=business_id,
            request_id=request_id,
            metadata={
                "grant_id": grant["id"],
                "changed_fields": ",".join(changed_fields),
                "before_profile": before_profile,
                "after_profile": after_profile,
                "before_experience": before_experience,
                "after_experience": after_experience,
                "before_branding": before_branding,
                "after_branding": after_branding,
            },
        )
    return {"business": get_business(business_id), "changed_fields": changed_fields}


def admin_update_document_metadata(
    business_id: int,
    document_id: int,
    *,
    actor_user_id: int,
    kind: str,
    doc_status: str,
    client_id: int | None,
    project_id: int | None,
    review_note: str | None,
    request_id: str | None = None,
) -> dict:
    """Corrección acotada de soporte, autorizada y con antes/después auditado.

    La autorización se vuelve a comprobar dentro de la misma transacción que la
    escritura. No permite tocar archivos, OCR, importes ni documentos vinculados a
    una factura emitida. Tampoco concede al administrador una sesión del cliente.
    """
    from .documents import repo as document_repo

    _support_admin_actor(actor_user_id)
    if kind not in document_repo.KINDS:
        raise ValueError("Tipo de documento desconocido.")
    if doc_status not in document_repo.DOC_STATUSES:
        raise ValueError("Estado de documento desconocido.")
    client_id = int(client_id) if client_id not in (None, "") else None
    project_id = int(project_id) if project_id not in (None, "") else None
    review_note = str(review_note or "").strip()[:500] or None
    now = _now()

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        grant = _support_grant_with_scope(
            conn, business_id, "document_metadata", now
        )

        current_row = conn.execute(
            "SELECT * FROM documents WHERE id=? AND business_id=?",
            (document_id, business_id),
        ).fetchone()
        if not current_row:
            raise ValueError("Documento no encontrado.")
        current = dict(current_row)
        if current.get("invoice_id"):
            invoice = conn.execute(
                "SELECT status, number FROM invoices WHERE id=? AND business_id=?",
                (current["invoice_id"], business_id),
            ).fetchone()
            if invoice and (invoice["status"] != "borrador" or invoice["number"]):
                raise ValueError(
                    "Este documento está vinculado a una factura emitida. Debe corregirse mediante el flujo fiscal correspondiente."
                )

        project = None
        if project_id is not None:
            project = conn.execute(
                "SELECT id, client_id FROM projects WHERE id=? AND business_id=?",
                (project_id, business_id),
            ).fetchone()
            if not project:
                raise ValueError("El proyecto no pertenece a este negocio.")
            project_client_id = project["client_id"]
            if client_id is None and project_client_id:
                client_id = int(project_client_id)
            elif (
                client_id is not None
                and project_client_id is not None
                and int(project_client_id) != client_id
            ):
                raise ValueError("El cliente no coincide con el proyecto.")
        if client_id is not None:
            client = conn.execute(
                "SELECT id FROM clients WHERE id=? AND business_id=?",
                (client_id, business_id),
            ).fetchone()
            if not client:
                raise ValueError("El cliente no pertenece a este negocio.")

        before = {
            "kind": current.get("kind"),
            "status": current.get("doc_status"),
            "client_id": current.get("client_id"),
            "project_id": current.get("project_id"),
            "note": current.get("review_note"),
        }
        after = {
            "kind": kind,
            "status": doc_status,
            "client_id": client_id,
            "project_id": project_id,
            "note": review_note,
        }
        changed_fields = [name for name in before if before[name] != after[name]]
        if changed_fields:
            conn.execute(
                "UPDATE documents SET kind=?, doc_status=?, client_id=?, project_id=?, "
                "review_note=?, reviewed_at=? WHERE id=? AND business_id=?",
                (
                    kind, doc_status, client_id, project_id, review_note, now,
                    document_id, business_id,
                ),
            )

    if changed_fields:
        def _note_hash(value: str | None) -> str | None:
            if not value:
                return None
            return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

        record_security_event(
            "admin.support_document_metadata_updated",
            severity="warning",
            area="support",
            actor_user_id=actor_user_id,
            subject_business_id=business_id,
            request_id=request_id,
            metadata={
                "item_id": document_id,
                "grant_id": grant["id"],
                "changed_fields": ",".join(changed_fields),
                "before_kind": before["kind"],
                "after_kind": after["kind"],
                "before_status": before["status"],
                "after_status": after["status"],
                "before_client_id": before["client_id"],
                "after_client_id": after["client_id"],
                "before_project_id": before["project_id"],
                "after_project_id": after["project_id"],
                "before_note_hash": _note_hash(before["note"]),
                "after_note_hash": _note_hash(after["note"]),
            },
        )
    with get_conn() as conn:
        saved = conn.execute(
            "SELECT * FROM documents WHERE id=? AND business_id=?",
            (document_id, business_id),
        ).fetchone()
    return {"document": dict(saved), "changed_fields": changed_fields}


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
        "invoice_lines": [dict(r) for r in _rows(
            "SELECT * FROM invoice_lines WHERE business_id=? "
            "ORDER BY invoice_id, position", business_id)],
        "invoice_series": list_invoice_series(business_id),
        "recurring_invoices": list_recurring_invoices(business_id),
        "recurring_invoice_runs": [dict(r) for r in _rows(
            "SELECT * FROM recurring_invoice_runs WHERE business_id=? "
            "ORDER BY recurring_id, scheduled_for", business_id)],
        "invoice_payments": [dict(r) for r in _rows(
            "SELECT * FROM invoice_payments WHERE business_id=? "
            "ORDER BY paid_at, id",
            business_id)],
        "bank_transactions": list_bank_transactions(business_id, limit=500),
        "email_outbox": list_email_messages(business_id, limit=500),
        "invoice_records": list_invoice_records(business_id),
        "invoice_events": list_invoice_events(business_id),
        "verifactu_outbox": list_verifactu_outbox(business_id, limit=500),
        "invoice_cancellation_records": [dict(r) for r in _rows(
            "SELECT * FROM invoice_cancellation_records WHERE business_id=? "
            "ORDER BY generated_at, id", business_id)],
        "verifactu_cancellation_outbox": [dict(r) for r in _rows(
            "SELECT * FROM verifactu_cancellation_outbox WHERE business_id=? "
            "ORDER BY created_at, id", business_id)],
        "quotes": list_quotes(business_id),
        "expenses": list_expenses(business_id),
        "suppliers": list_suppliers(business_id),
        "received_invoices": list_received_invoices(business_id),
        "products": list_products(business_id, include_inactive=True),
        "leads": list_leads(business_id),
        "gestoria_requests": list_gestoria_requests(business_id),
        "gestoria_deliveries": list_gestoria_deliveries(business_id),
        "projects": list_projects(business_id),
        "project_members": [dict(r) for r in _rows(
            "SELECT * FROM project_members WHERE business_id=? ORDER BY project_id, worker_id",
            business_id)],
        "project_entries": [dict(r) for r in _rows(
            "SELECT * FROM project_entries WHERE business_id=? ORDER BY project_id, id",
            business_id)],
        "project_tasks": [dict(r) for r in _rows(
            "SELECT * FROM project_tasks WHERE business_id=? ORDER BY project_id, id",
            business_id)],
        "job_materials": [dict(r) for r in _rows(
            "SELECT * FROM job_materials WHERE business_id=? ORDER BY job_id, id",
            business_id)],
        "job_updates": [dict(r) for r in _rows(
            "SELECT * FROM job_updates WHERE business_id=? ORDER BY job_id, id",
            business_id)],
        "job_completions": [dict(r) for r in _rows(
            "SELECT * FROM job_completions WHERE business_id=? ORDER BY job_id, id",
            business_id)],
        "client_preferences": [dict(r) for r in _rows(
            "SELECT * FROM client_preferences WHERE business_id=? ORDER BY client_id",
            business_id)],
        "product_events": [dict(r) for r in _rows(
            "SELECT * FROM product_events WHERE business_id=? ORDER BY id",
            business_id)],
        "assistant_messages": [dict(r) for r in _rows(
            "SELECT * FROM assistant_messages WHERE business_id=? ORDER BY id",
            business_id)],
        "business_memories": [dict(r) for r in _rows(
            "SELECT * FROM business_memories WHERE business_id=? ORDER BY id",
            business_id)],
        "automation_permissions": [dict(r) for r in _rows(
            "SELECT * FROM automation_permissions WHERE business_id=? "
            "ORDER BY action_key",
            business_id)],
        "integration_settings": [dict(r) for r in _rows(
            "SELECT * FROM integration_settings WHERE business_id=? "
            "ORDER BY integration_key",
            business_id)],
        "assistant_actions": [dict(r) for r in _rows(
            "SELECT * FROM assistant_actions WHERE business_id=? ORDER BY id",
            business_id)],
        "document_classifications": [dict(r) for r in _rows(
            "SELECT * FROM document_classifications WHERE business_id=? ORDER BY id",
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
        "bank_transactions": [dict(r) for r in _rows(
            "SELECT bt.* FROM bank_transactions bt JOIN invoices i "
            "ON i.business_id=bt.business_id AND i.id=bt.suggested_invoice_id "
            "WHERE bt.business_id=? AND i.client_id=? ORDER BY bt.booked_on, bt.id",
            business_id, client_id)],
        "quotes": [dict(r) for r in _rows(
            "SELECT * FROM quotes WHERE business_id=? AND client_id=?",
            business_id, client_id)],
        "projects": [dict(r) for r in _rows(
            "SELECT * FROM projects WHERE business_id=? AND client_id=?",
            business_id, client_id)],
        "job_materials": [dict(r) for r in _rows(
            "SELECT m.* FROM job_materials m JOIN jobs j "
            "ON j.business_id=m.business_id AND j.id=m.job_id "
            "WHERE m.business_id=? AND j.client_id=? ORDER BY m.id",
            business_id, client_id)],
        "job_updates": [dict(r) for r in _rows(
            "SELECT u.* FROM job_updates u JOIN jobs j "
            "ON j.business_id=u.business_id AND j.id=u.job_id "
            "WHERE u.business_id=? AND j.client_id=? ORDER BY u.id",
            business_id, client_id)],
        "job_completions": [dict(r) for r in _rows(
            "SELECT jc.* FROM job_completions jc JOIN jobs j "
            "ON j.business_id=jc.business_id AND j.id=jc.job_id "
            "WHERE jc.business_id=? AND j.client_id=? ORDER BY jc.id",
            business_id, client_id)],
        "client_preferences": get_client_preferences(client_id, business_id),
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
    with get_conn() as conn:
        conn.execute(
            "UPDATE job_updates SET document_id=NULL WHERE business_id=? "
            "AND document_id IN (SELECT id FROM documents WHERE business_id=? "
            "AND client_id=?)",
            (business_id, business_id, client_id),
        )
    for stored in _docrepo.stored_names_for_client(business_id, client_id):
        _docstore.delete(business_id, stored)
    _docrepo.purge_for_client(business_id, client_id)
    with get_conn() as conn:
        issued = conn.execute(
            "SELECT COUNT(*) AS total FROM invoices WHERE business_id=? AND client_id=? "
            "AND status IN ('enviada','parcial','cobrada')",
            (business_id, client_id),
        ).fetchone()["total"]
        conn.execute(
            "DELETE FROM business_memories WHERE business_id=? "
            "AND scope_type='client' AND scope_id=?",
            (business_id, client_id),
        )
        conn.execute("DELETE FROM portal_tokens WHERE business_id=? AND client_id=?",
                     (business_id, client_id))
        conn.execute("DELETE FROM quotes WHERE business_id=? AND client_id=?",
                     (business_id, client_id))
        conn.execute(
            "UPDATE job_completions SET invoice_id=NULL WHERE business_id=? "
            "AND invoice_id IN (SELECT id FROM invoices WHERE business_id=? "
            "AND client_id=? AND status='borrador')",
            (business_id, business_id, client_id),
        )
        conn.execute(
            "DELETE FROM invoices WHERE business_id=? AND client_id=? "
            "AND status='borrador'",
            (business_id, client_id),
        )
        conn.execute(
            "UPDATE job_completions SET customer_name=NULL, customer_note=NULL, "
            "signature_data=NULL, signature_hash=NULL, signer_ip_hash=NULL, "
            "signer_user_agent=NULL WHERE business_id=? AND job_id IN "
            "(SELECT id FROM jobs WHERE business_id=? AND client_id=?)",
            (business_id, business_id, client_id),
        )
        conn.execute(
            "UPDATE project_tasks SET job_id=NULL WHERE business_id=? "
            "AND job_id IN (SELECT id FROM jobs WHERE business_id=? AND client_id=?)",
            (business_id, business_id, client_id),
        )
        conn.execute(
            "DELETE FROM jobs WHERE business_id=? AND client_id=? "
            "AND NOT EXISTS (SELECT 1 FROM worker_clockins wc "
            "WHERE wc.business_id=jobs.business_id AND wc.job_id=jobs.id) "
            "AND NOT EXISTS (SELECT 1 FROM job_materials jm "
            "WHERE jm.business_id=jobs.business_id AND jm.job_id=jobs.id) "
            "AND NOT EXISTS (SELECT 1 FROM job_updates ju "
            "WHERE ju.business_id=jobs.business_id AND ju.job_id=jobs.id) "
            "AND NOT EXISTS (SELECT 1 FROM job_completions jc "
            "WHERE jc.business_id=jobs.business_id AND jc.job_id=jobs.id)",
            (business_id, client_id),
        )
        conn.execute(
            "UPDATE jobs SET client_id=NULL WHERE business_id=? AND client_id=?",
            (business_id, client_id),
        )
        conn.execute(
            "UPDATE projects SET client_id=NULL WHERE business_id=? AND client_id=?",
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
            "gestoria_invitations", "gestoria_business_access",
            "whatsapp_pending_actions", "whatsapp_links", "whatsapp_outbox",
            "email_outbox",
            "verifactu_cancellation_outbox", "verifactu_outbox",
            "document_sequences",
            "worker_tokens", "worker_clockin_corrections", "worker_clockins",
            "invoice_events", "invoice_cancellation_records", "invoice_records",
            "portal_tokens",
            "product_events", "assistant_messages", "business_memories",
            "assistant_actions", "automation_permissions",
            "integration_settings",
            "document_classifications", "copilot_recommendations",
            "gestoria_deliveries", "gestoria_requests",
            "job_updates", "job_completions", "job_materials",
            "client_preferences",
            "project_tasks", "project_entries", "project_members", "projects",
            "documents", "received_invoices", "suppliers", "products",
            "leads", "quotes",
            "bank_transactions", "recurring_invoice_runs", "recurring_invoices",
            "invoice_payments", "invoice_lines", "invoices", "invoice_series",
            "jobs", "workers", "clients", "expenses"
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
