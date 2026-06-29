"""Almacenamiento (SQLite) — multi-negocio (multi-tenant).

Cada autónomo que se da de alta es un "business". Todos sus datos (clientes,
agenda, facturas, gastos) van marcados con su business_id, de modo que los datos
de un cliente nunca se mezclan con los de otro.

Es deliberadamente sencillo: el día de mañana esto se migra a Postgres/Supabase
sin cambiar la lógica de negocio (las funciones de aquí son el único punto de
contacto con la base de datos).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config

DEFAULT_BUSINESS_ID = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    owner_email     TEXT,
    sector          TEXT,
    nif             TEXT,
    address         TEXT,
    default_vat     REAL NOT NULL DEFAULT 21,
    default_irpf    REAL NOT NULL DEFAULT 0,
    whatsapp_phone  TEXT,
    whatsapp_status TEXT NOT NULL DEFAULT 'no_conectado',  -- no_conectado|pendiente|conectado
    onboarding_done INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    business_id   INTEGER NOT NULL REFERENCES businesses(id),
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL DEFAULT 1,
    name        TEXT NOT NULL,
    phone       TEXT,
    address     TEXT,
    zone        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id     INTEGER NOT NULL DEFAULT 1,
    client_id       INTEGER REFERENCES clients(id),
    description     TEXT NOT NULL,
    scheduled_for   TEXT,
    zone            TEXT,
    price_estimate  REAL,
    status          TEXT NOT NULL DEFAULT 'pendiente',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL DEFAULT 1,
    number      TEXT,
    client_id   INTEGER REFERENCES clients(id),
    concept     TEXT NOT NULL,
    base        REAL NOT NULL,
    vat_rate    REAL NOT NULL,
    vat_amount  REAL NOT NULL,
    irpf_rate   REAL NOT NULL DEFAULT 0,
    irpf_amount REAL NOT NULL DEFAULT 0,
    total       REAL NOT NULL,
    status      TEXT NOT NULL DEFAULT 'borrador',
    due_date    TEXT,
    issued_at   TEXT,
    paid_at     TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL DEFAULT 1,
    concept     TEXT NOT NULL,
    amount      REAL NOT NULL,
    vat_rate    REAL,
    category    TEXT,
    spent_on    TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quotes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL DEFAULT 1,
    number      TEXT,
    client_id   INTEGER REFERENCES clients(id),
    concept     TEXT NOT NULL,
    base        REAL NOT NULL,
    vat_rate    REAL NOT NULL,
    vat_amount  REAL NOT NULL,
    irpf_rate   REAL NOT NULL DEFAULT 0,
    irpf_amount REAL NOT NULL DEFAULT 0,
    total       REAL NOT NULL,
    status      TEXT NOT NULL DEFAULT 'borrador',  -- borrador|enviado|aceptado|rechazado
    valid_until TEXT,
    invoice_id  INTEGER REFERENCES invoices(id),   -- factura creada al aceptar
    created_at  TEXT NOT NULL,
    accepted_at TEXT
);

CREATE TABLE IF NOT EXISTS password_resets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    token_hash  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
"""

# Migraciones suaves: columnas añadidas después del esquema inicial. Se aplican con
# ALTER TABLE solo si faltan, para no perder datos de las cuentas ya creadas.
_MIGRATIONS: list[tuple[str, str, str]] = [
    ("businesses", "plan", "TEXT NOT NULL DEFAULT 'trial'"),
    ("businesses", "subscription_status", "TEXT NOT NULL DEFAULT 'trial'"),  # trial|active|past_due|canceled
    ("businesses", "trial_ends_at", "TEXT"),
    ("businesses", "stripe_customer_id", "TEXT"),
    ("businesses", "stripe_subscription_id", "TEXT"),
    ("users", "is_admin", "INTEGER NOT NULL DEFAULT 0"),
    ("invoices", "last_reminder_at", "TEXT"),
    ("invoices", "reminders_sent", "INTEGER NOT NULL DEFAULT 0"),
]


@contextmanager
def get_conn():
    """Conexión a SQLite que hace commit al salir y SIEMPRE cierra.

    Cerrar es importante en Windows: una conexión abierta bloquea el fichero
    y luego no se puede borrar/recrear la base de datos.
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate() -> None:
    """Aplica columnas nuevas a tablas existentes sin perder datos (idempotente)."""
    with get_conn() as conn:
        for table, column, decl in _MIGRATIONS:
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    _migrate()
    _ensure_default_business()


def reset_db() -> None:
    Path(config.DB_PATH).unlink(missing_ok=True)
    init_db()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------- Negocios ---
def _ensure_default_business() -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM businesses WHERE id=?",
                           (DEFAULT_BUSINESS_ID,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO businesses (id, name, created_at) VALUES (?, ?, ?)",
                (DEFAULT_BUSINESS_ID, config.BUSINESS_NAME, _now()),
            )


def create_business(name, owner_email=None, sector=None) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO businesses (name, owner_email, sector, created_at) "
            "VALUES (?, ?, ?, ?)",
            (name, owner_email, sector, _now()),
        )
        new_id = cur.lastrowid
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


def get_business_by_phone(phone: str) -> dict | None:
    """Encuentra el negocio cuyo WhatsApp coincide con el teléfono que escribe."""
    target = normalize_phone(phone)
    if not target:
        return None
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM businesses WHERE whatsapp_phone IS NOT NULL").fetchall()
    for r in rows:
        if normalize_phone(r["whatsapp_phone"]) == target:
            return dict(r)
    return None


def list_businesses() -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM businesses ORDER BY id").fetchall()]


def set_whatsapp_status(business_id, status, phone=None) -> dict:
    with get_conn() as conn:
        if phone is not None:
            conn.execute("UPDATE businesses SET whatsapp_status=?, whatsapp_phone=? "
                         "WHERE id=?", (status, phone, business_id))
        else:
            conn.execute("UPDATE businesses SET whatsapp_status=? WHERE id=?",
                         (status, business_id))
    return get_business(business_id)


def finish_onboarding(business_id) -> dict:
    with get_conn() as conn:
        conn.execute("UPDATE businesses SET onboarding_done=1 WHERE id=?", (business_id,))
    return get_business(business_id)


def update_fiscal(business_id, name=None, nif=None, address=None,
                  default_vat=None, default_irpf=None) -> dict:
    """Actualiza los datos fiscales del negocio (NIF, dirección, IVA/IRPF por defecto)."""
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


# ---------------------------------------------------------------- Usuarios ---
def create_user(email, password_hash, business_id) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, business_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (email.lower().strip(), password_hash, business_id, _now()),
        )
        new_id = cur.lastrowid
    return get_user(new_id)


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
def add_client(name, phone=None, address=None, zone=None,
               business_id=DEFAULT_BUSINESS_ID) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO clients (business_id, name, phone, address, zone, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (business_id, name, phone, address, zone, _now()),
        )
        new_id = cur.lastrowid
    return get_client(new_id)


def get_client(client_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        return dict(row) if row else None


def find_client(name, business_id=DEFAULT_BUSINESS_ID) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE business_id=? AND name LIKE ? "
            "ORDER BY id LIMIT 1",
            (business_id, f"%{name}%"),
        ).fetchone()
        return dict(row) if row else None


def list_clients(business_id=DEFAULT_BUSINESS_ID) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM clients WHERE business_id=? ORDER BY name",
            (business_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_or_create_client(name, business_id=DEFAULT_BUSINESS_ID, **kw) -> dict:
    return find_client(name, business_id) or add_client(name, business_id=business_id, **kw)


def update_client(client_id, business_id, name=None, phone=None, address=None,
                  zone=None) -> dict | None:
    fields, params = [], []
    for col, val in [("name", name), ("phone", phone), ("address", address),
                     ("zone", zone)]:
        if val is not None:
            fields.append(f"{col}=?")
            params.append(val)
    if fields:
        params += [client_id, business_id]
        with get_conn() as conn:
            conn.execute(f"UPDATE clients SET {', '.join(fields)} "
                         f"WHERE id=? AND business_id=?", params)
    return get_client(client_id)


def delete_client(client_id, business_id) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM clients WHERE id=? AND business_id=?",
                     (client_id, business_id))


# ------------------------------------------------------------------ Agenda ---
def add_job(client_id, description, scheduled_for=None, zone=None,
            price_estimate=None, business_id=DEFAULT_BUSINESS_ID) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (business_id, client_id, description, scheduled_for, "
            "zone, price_estimate, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (business_id, client_id, description, scheduled_for, zone,
             price_estimate, _now()),
        )
        new_id = cur.lastrowid
    return get_job(new_id)


def get_job(job_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def update_job_status(job_id, status, business_id) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET status=? WHERE id=? AND business_id=?",
                     (status, job_id, business_id))


def delete_job(job_id, business_id) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM jobs WHERE id=? AND business_id=?",
                     (job_id, business_id))


def jobs_for_date(day: str, business_id=DEFAULT_BUSINESS_ID) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT j.*, c.name AS client_name, c.zone AS client_zone "
            "FROM jobs j LEFT JOIN clients c ON c.id = j.client_id "
            "WHERE j.business_id=? AND j.scheduled_for LIKE ? "
            "ORDER BY j.scheduled_for",
            (business_id, f"{day}%"),
        ).fetchall()
        return [dict(r) for r in rows]


def jobs_between(start: str, end: str, business_id=DEFAULT_BUSINESS_ID) -> list[dict]:
    """Trabajos entre dos fechas ISO (para el calendario semanal)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT j.*, c.name AS client_name FROM jobs j "
            "LEFT JOIN clients c ON c.id = j.client_id "
            "WHERE j.business_id=? AND j.scheduled_for >= ? AND j.scheduled_for <= ? "
            "ORDER BY j.scheduled_for",
            (business_id, start, end + "T23:59"),
        ).fetchall()
        return [dict(r) for r in rows]


# --------------------------------------------------------------- Facturas ---
def add_invoice(client_id, concept, base, vat_rate=config.DEFAULT_VAT_RATE,
                irpf_rate=0, business_id=DEFAULT_BUSINESS_ID) -> dict:
    """Crea una factura calculando IVA y retención de IRPF.

    Total = base + IVA − IRPF retenido (así sale el importe que el cliente paga).
    """
    base = round(float(base), 2)
    vat_amount = round(base * vat_rate / 100, 2)
    irpf_amount = round(base * (irpf_rate or 0) / 100, 2)
    total = round(base + vat_amount - irpf_amount, 2)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO invoices (business_id, client_id, concept, base, vat_rate, "
            "vat_amount, irpf_rate, irpf_amount, total, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?)",
            (business_id, client_id, concept, base, vat_rate, vat_amount,
             irpf_rate or 0, irpf_amount, total, _now()),
        )
        new_id = cur.lastrowid
    return get_invoice(new_id)


def get_invoice(invoice_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT i.*, c.name AS client_name FROM invoices i "
            "LEFT JOIN clients c ON c.id = i.client_id WHERE i.id=?",
            (invoice_id,),
        ).fetchone()
        return dict(row) if row else None


def list_invoices(business_id=DEFAULT_BUSINESS_ID, status=None) -> list[dict]:
    q = ("SELECT i.*, c.name AS client_name FROM invoices i "
         "LEFT JOIN clients c ON c.id = i.client_id WHERE i.business_id=?")
    params: list = [business_id]
    if status:
        q += " AND i.status=?"
        params.append(status)
    q += " ORDER BY i.created_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def mark_invoice_sent(invoice_id, number, due_date=None, business_id=None) -> dict | None:
    """Marca una factura como enviada. Filtra por business_id (aislamiento): si la
    factura no es de ese negocio, no toca nada y devuelve None."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE invoices SET status='enviada', number=?, issued_at=?, due_date=? "
            "WHERE id=? AND business_id=?",
            (number, _now(), due_date, invoice_id, business_id),
        )
        ok = cur.rowcount > 0
    return get_invoice(invoice_id) if ok else None


def mark_invoice_paid(invoice_id, business_id) -> dict | None:
    """Marca una factura como cobrada. Filtra por business_id (aislamiento): si la
    factura no es de ese negocio, no toca nada y devuelve None."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE invoices SET status='cobrada', paid_at=? WHERE id=? AND business_id=?",
            (_now(), invoice_id, business_id))
        ok = cur.rowcount > 0
    return get_invoice(invoice_id) if ok else None


def delete_invoice(invoice_id, business_id) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM invoices WHERE id=? AND business_id=?",
                     (invoice_id, business_id))


def pending_payments(business_id=DEFAULT_BUSINESS_ID) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT i.*, c.name AS client_name FROM invoices i "
            "LEFT JOIN clients c ON c.id = i.client_id "
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
                business_id=DEFAULT_BUSINESS_ID) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO expenses (business_id, concept, amount, vat_rate, category, "
            "spent_on, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (business_id, concept, round(float(amount), 2), vat_rate, category,
             spent_on, _now()),
        )
        new_id = cur.lastrowid
    with get_conn() as conn:
        return dict(conn.execute("SELECT * FROM expenses WHERE id=?", (new_id,)).fetchone())


def delete_expense(expense_id, business_id) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM expenses WHERE id=? AND business_id=?",
                     (expense_id, business_id))


def list_expenses(business_id=DEFAULT_BUSINESS_ID) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM expenses WHERE business_id=? ORDER BY created_at DESC",
            (business_id,)).fetchall()]


# --------------------------------------------------------------- Resúmenes ---
def month_billing(month: str | None = None,
                  business_id=DEFAULT_BUSINESS_ID) -> dict:
    month = month or date.today().strftime("%Y-%m")
    with get_conn() as conn:
        def one(sql, *extra):
            return conn.execute(sql, (business_id, f"{month}%", *extra)).fetchone()[0]

        invoiced = one("SELECT COALESCE(SUM(total),0) FROM invoices WHERE business_id=? "
                       "AND created_at LIKE ? AND status IN ('enviada','cobrada')")
        collected = one("SELECT COALESCE(SUM(total),0) FROM invoices WHERE business_id=? "
                        "AND created_at LIKE ? AND status='cobrada'")
        pending = one("SELECT COALESCE(SUM(total),0) FROM invoices WHERE business_id=? "
                      "AND created_at LIKE ? AND status='enviada'")
        vat = one("SELECT COALESCE(SUM(vat_amount),0) FROM invoices WHERE business_id=? "
                  "AND created_at LIKE ? AND status IN ('enviada','cobrada')")
        expenses = one("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE business_id=? "
                       "AND created_at LIKE ?")
    return {
        "month": month,
        "invoiced": round(invoiced, 2),
        "collected": round(collected, 2),
        "pending": round(pending, 2),
        "vat_estimated": round(vat, 2),
        "expenses": round(expenses, 2),
        "estimated_profit": round(invoiced - expenses, 2),
    }


def expenses_by_category(business_id=DEFAULT_BUSINESS_ID) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT COALESCE(NULLIF(category,''),'Sin categoría') AS category, "
            "SUM(amount) AS total, COUNT(*) AS n FROM expenses "
            "WHERE business_id=? GROUP BY category ORDER BY total DESC",
            (business_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def income_by_client(business_id=DEFAULT_BUSINESS_ID, limit: int = 8) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.name AS client_name, SUM(i.total) AS total, COUNT(*) AS n "
            "FROM invoices i LEFT JOIN clients c ON c.id=i.client_id "
            "WHERE i.business_id=? AND i.status IN ('enviada','cobrada') "
            "GROUP BY i.client_id ORDER BY total DESC LIMIT ?",
            (business_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def client_stats(business_id=DEFAULT_BUSINESS_ID) -> list[dict]:
    """Cada cliente con su facturación total, nº facturas y nº trabajos."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.*, "
            " (SELECT COALESCE(SUM(total),0) FROM invoices i WHERE i.client_id=c.id "
            "   AND i.status IN ('enviada','cobrada')) AS facturado, "
            " (SELECT COUNT(*) FROM invoices i WHERE i.client_id=c.id) AS n_facturas, "
            " (SELECT COUNT(*) FROM jobs j WHERE j.client_id=c.id) AS n_trabajos "
            "FROM clients c WHERE c.business_id=? ORDER BY facturado DESC",
            (business_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def financial_analysis(business_id=DEFAULT_BUSINESS_ID) -> dict:
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
    collected = round(sum(i["total"] for i in invoices if i["status"] == "cobrada"), 2)
    pending = round(sum(i["total"] for i in invoices if i["status"] == "enviada"), 2)
    gastos = round(sum(e["amount"] for e in expenses), 2)
    beneficio = round(invoiced - gastos, 2)
    vat_repercutido = round(sum(i.get("vat_amount") or 0 for i in invoices), 2)
    # IVA soportado solo si el gasto guarda su tipo; si no, queda en 0 (no se inventa).
    vat_soportado = round(sum(
        (e["amount"] - e["amount"] / (1 + (e["vat_rate"] or 0) / 100)) if e.get("vat_rate") else 0
        for e in expenses), 2)

    n = len(invoices)
    ticket_medio = round(invoiced / n, 2) if n else 0.0
    margen_pct = round(beneficio / invoiced * 100, 1) if invoiced else 0.0
    ratio_gasto = round(gastos / invoiced * 100, 1) if invoiced else 0.0
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
        "invoiced": invoiced, "collected": collected, "pending": pending,
        "gastos": gastos, "beneficio": beneficio, "n_facturas": n,
        "ticket_medio": ticket_medio, "margen_pct": margen_pct,
        "ratio_gasto": ratio_gasto, "cobro_pct": cobro_pct,
        "dso": dso, "morosidad": morosidad, "morosidad_pct": morosidad_pct,
        "solvencia": solvencia, "concentracion": concentracion,
        "top_cliente": top["name"] if top else None,
        "vat_repercutido": vat_repercutido, "vat_soportado": vat_soportado,
        "vat_liquidar": round(vat_repercutido - vat_soportado, 2),
        "clientes_activos": len(clients),
    }


def monthly_series(business_id=DEFAULT_BUSINESS_ID, months: int = 6) -> list[dict]:
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
        b = month_billing(key, business_id)
        series.append({"month": key, "invoiced": b["invoiced"],
                       "expenses": b["expenses"], "profit": b["estimated_profit"]})
    return series


# ----------------------------------------------------------- Presupuestos ---
def add_quote(client_id, concept, base, vat_rate=config.DEFAULT_VAT_RATE,
              irpf_rate=0, valid_days=30, business_id=DEFAULT_BUSINESS_ID) -> dict:
    """Crea un presupuesto (mismo cálculo que una factura, pero sin valor fiscal
    hasta que se acepta y se convierte en factura)."""
    base = round(float(base), 2)
    vat_amount = round(base * vat_rate / 100, 2)
    irpf_amount = round(base * (irpf_rate or 0) / 100, 2)
    total = round(base + vat_amount - irpf_amount, 2)
    valid_until = (date.today() + timedelta(days=valid_days)).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO quotes (business_id, client_id, concept, base, vat_rate, "
            "vat_amount, irpf_rate, irpf_amount, total, status, valid_until, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?, ?)",
            (business_id, client_id, concept, base, vat_rate, vat_amount,
             irpf_rate or 0, irpf_amount, total, valid_until, _now()),
        )
        new_id = cur.lastrowid
    return get_quote(new_id)


def get_quote(quote_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT q.*, c.name AS client_name FROM quotes q "
            "LEFT JOIN clients c ON c.id = q.client_id WHERE q.id=?",
            (quote_id,),
        ).fetchone()
        return dict(row) if row else None


def list_quotes(business_id=DEFAULT_BUSINESS_ID, status=None) -> list[dict]:
    q = ("SELECT q.*, c.name AS client_name FROM quotes q "
         "LEFT JOIN clients c ON c.id = q.client_id WHERE q.business_id=?")
    params: list = [business_id]
    if status:
        q += " AND q.status=?"
        params.append(status)
    q += " ORDER BY q.created_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def _next_quote_number(conn, business_id) -> str:
    year = date.today().year
    n = conn.execute(
        "SELECT COUNT(*) FROM quotes WHERE business_id=? AND number IS NOT NULL "
        "AND number LIKE ?", (business_id, f"P{year}/%")).fetchone()[0]
    return f"P{year}/{n + 1:04d}"


def mark_quote_sent(quote_id, business_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM quotes WHERE id=? AND business_id=?",
                           (quote_id, business_id)).fetchone()
        if not row:
            return None
        number = row["number"] or _next_quote_number(conn, business_id)
        conn.execute("UPDATE quotes SET status='enviado', number=? "
                     "WHERE id=? AND business_id=?", (number, quote_id, business_id))
    return get_quote(quote_id)


def reject_quote(quote_id, business_id) -> dict | None:
    with get_conn() as conn:
        cur = conn.execute("UPDATE quotes SET status='rechazado' "
                           "WHERE id=? AND business_id=?", (quote_id, business_id))
        ok = cur.rowcount > 0
    return get_quote(quote_id) if ok else None


def accept_quote(quote_id, business_id) -> dict | None:
    """Acepta un presupuesto y crea la factura borrador equivalente. Aislado por
    negocio: si el presupuesto no es de ese negocio, no hace nada."""
    q = get_quote(quote_id)
    if not q or q.get("business_id") != business_id:
        return None
    inv = add_invoice(q["client_id"], q["concept"], q["base"], vat_rate=q["vat_rate"],
                      irpf_rate=q["irpf_rate"], business_id=business_id)
    with get_conn() as conn:
        conn.execute("UPDATE quotes SET status='aceptado', accepted_at=?, invoice_id=? "
                     "WHERE id=? AND business_id=?",
                     (_now(), inv["id"], quote_id, business_id))
    return {"quote": get_quote(quote_id), "invoice": inv}


def delete_quote(quote_id, business_id) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM quotes WHERE id=? AND business_id=?",
                     (quote_id, business_id))


# -------------------------------------------------------- Impuestos (303/130) ---
_QUARTERS = {1: ("01", "03"), 2: ("04", "06"), 3: ("07", "09"), 4: ("10", "12")}


def tax_quarter(year: int, quarter: int, business_id=DEFAULT_BUSINESS_ID) -> dict:
    """Resumen fiscal de un trimestre: IVA (modelo 303) e IRPF pago fraccionado
    (modelo 130, estimación directa simplificada). Son CIFRAS DE APOYO para el
    gestor, no una presentación oficial."""
    m0, m1 = _QUARTERS[quarter]
    start, end = f"{year}-{m0}", f"{year}-{m1}"

    def _in_range(d: str | None) -> bool:
        return bool(d) and start <= d[:7] <= end

    invoices = [i for i in list_invoices(business_id)
                if i.get("status") in ("enviada", "cobrada")
                and _in_range(i.get("issued_at") or i.get("created_at"))]
    expenses = [e for e in list_expenses(business_id)
                if _in_range(e.get("spent_on") or e.get("created_at"))]

    ingresos = round(sum(i["base"] for i in invoices), 2)
    iva_repercutido = round(sum(i.get("vat_amount") or 0 for i in invoices), 2)
    irpf_retenido = round(sum(i.get("irpf_amount") or 0 for i in invoices), 2)
    gastos = round(sum(e["amount"] for e in expenses), 2)
    # IVA soportado solo de gastos que registran su tipo (no se inventa).
    iva_soportado = round(sum(
        (e["amount"] - e["amount"] / (1 + (e["vat_rate"] or 0) / 100)) if e.get("vat_rate") else 0
        for e in expenses), 2)
    base_gastos = round(sum(
        (e["amount"] / (1 + (e["vat_rate"] or 0) / 100)) if e.get("vat_rate") else e["amount"]
        for e in expenses), 2)

    iva_resultado = round(iva_repercutido - iva_soportado, 2)          # modelo 303
    rendimiento = round(ingresos - base_gastos, 2)
    # Modelo 130: 20% del rendimiento neto del trimestre, menos retenciones soportadas.
    irpf_pago = round(max(rendimiento * 0.20 - irpf_retenido, 0), 2)

    return {
        "year": year, "quarter": quarter, "label": f"{quarter}T {year}",
        "ingresos": ingresos, "iva_repercutido": iva_repercutido,
        "gastos": gastos, "base_gastos": base_gastos, "iva_soportado": iva_soportado,
        "iva_resultado": iva_resultado, "irpf_retenido": irpf_retenido,
        "rendimiento": rendimiento, "irpf_pago": irpf_pago,
        "n_facturas": len(invoices), "n_gastos": len(expenses),
    }


# ----------------------------------------------------------- Recordatorios ---
def overdue_invoices(business_id=DEFAULT_BUSINESS_ID, min_days: int = 1) -> list[dict]:
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
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",
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
            "SELECT * FROM password_resets WHERE token_hash=? AND used=0",
            (token_hash,)).fetchone()
        if not row:
            return None
        if row["expires_at"] < datetime.now().isoformat(timespec="seconds"):
            return None
        conn.execute("UPDATE password_resets SET used=1 WHERE id=?", (row["id"],))
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


# ----------------------------------------------------- Panel de administración ---
def admin_overview() -> dict:
    """Cifras globales del negocio Noesis (solo para el fundador). NO expone datos
    operativos de cada autónomo, solo metadatos de cuenta y agregados."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT b.id, b.name, b.sector, b.owner_email, b.created_at, "
            "b.whatsapp_status, b.plan, b.subscription_status, b.trial_ends_at, "
            "(SELECT COUNT(*) FROM invoices i WHERE i.business_id=b.id) AS n_facturas, "
            "(SELECT COUNT(*) FROM clients c WHERE c.business_id=b.id) AS n_clientes, "
            "(SELECT COALESCE(SUM(total),0) FROM invoices i WHERE i.business_id=b.id "
            "  AND i.status IN ('enviada','cobrada')) AS facturado "
            "FROM businesses b WHERE b.id<>1 ORDER BY b.created_at DESC").fetchall()
    biz = [dict(r) for r in rows]
    PRICES = {"trial": 0, "autonomo": 29, "pro": 39}
    activos = [b for b in biz if b["subscription_status"] == "active"]
    mrr = sum(PRICES.get(b["plan"], 0) for b in activos)
    return {
        "total": len(biz), "activos": len(activos),
        "en_prueba": len([b for b in biz if b["subscription_status"] == "trial"]),
        "whatsapp_conectados": len([b for b in biz if b["whatsapp_status"] == "conectado"]),
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
        "exported_at": _now(),
    }


def export_client_data(client_id, business_id) -> dict | None:
    """Vuelca los datos de un cliente final concreto (RGPD por persona)."""
    client = get_client(client_id)
    if not client or client.get("business_id") != business_id:
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
    """Borra un cliente y todo lo asociado (derecho al olvido RGPD)."""
    client = get_client(client_id)
    if not client or client.get("business_id") != business_id:
        return False
    with get_conn() as conn:
        conn.execute("DELETE FROM quotes WHERE business_id=? AND client_id=?",
                     (business_id, client_id))
        conn.execute("DELETE FROM invoices WHERE business_id=? AND client_id=?",
                     (business_id, client_id))
        conn.execute("DELETE FROM jobs WHERE business_id=? AND client_id=?",
                     (business_id, client_id))
        conn.execute("DELETE FROM clients WHERE id=? AND business_id=?",
                     (client_id, business_id))
    return True


def delete_business_cascade(business_id) -> None:
    """Borra una cuenta entera y todos sus datos (baja RGPD del autónomo)."""
    if business_id == DEFAULT_BUSINESS_ID:
        return
    with get_conn() as conn:
        for table in ("quotes", "invoices", "jobs", "clients", "expenses"):
            conn.execute(f"DELETE FROM {table} WHERE business_id=?", (business_id,))
        conn.execute("DELETE FROM password_resets WHERE user_id IN "
                     "(SELECT id FROM users WHERE business_id=?)", (business_id,))
        conn.execute("DELETE FROM users WHERE business_id=?", (business_id,))
        conn.execute("DELETE FROM businesses WHERE id=?", (business_id,))
