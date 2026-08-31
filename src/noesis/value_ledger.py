"""Registro auditable de trabajo útil y resultados observables.

Esta capa solo observa operaciones terminales. Nunca concede permisos, ejecuta
acciones ni decide fiscalidad. Los escritores ``observe_*`` fallan abiertos para
que una incidencia de medición no altere el flujo de facturación, cobros, agenda,
documentos o WhatsApp.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import config, db

log = logging.getLogger("noesis.value_ledger")

TAXONOMY_VERSION = 1
ATTRIBUTION_VERSION = 1
DEFAULT_TIMEZONE = "Europe/Madrid"

CHANNELS = frozenset({"whatsapp", "web", "email", "system"})
TRIGGER_SOURCES = frozenset({
    "user_initiated", "noesis_proposed", "authorized_rule",
    "external_integration",
})
COMPLETION_MODES = frozenset({
    "user_confirmed", "authorized_rule", "system_observed",
    "external_confirmed",
})
ACTION_STATUSES = frozenset({"completed", "corrected", "reverted", "invalidated"})
ATTRIBUTION_TYPES = frozenset({"direct", "assisted", "observed"})


@dataclass(frozen=True)
class ActionDefinition:
    process: str
    counts_for_wub: bool
    label: str


# Fuente única, explícita y versionada. Preparar un borrador es trabajo útil, pero
# no convierte por sí solo un negocio en WUB. El envío posterior tampoco duplica
# la preparación porque solo la fase terminal marcada puede contar.
ACTION_TAXONOMY: dict[str, ActionDefinition] = {
    "job_created": ActionDefinition("scheduling", True, "Trabajo agendado"),
    "job_completed": ActionDefinition("scheduling", True, "Trabajo cerrado"),
    "invoice_issued": ActionDefinition("invoicing", True, "Factura emitida"),
    "payment_reminder_sent": ActionDefinition(
        "collections", True, "Seguimiento de cobro enviado"
    ),
    "document_classification_confirmed": ActionDefinition(
        "documents", True, "Documento clasificado y validado"
    ),
    "quote_prepared": ActionDefinition(
        "quotes", False, "Presupuesto preparado"
    ),
    "quote_sent": ActionDefinition("quotes", True, "Presupuesto enviado"),
    "client_created": ActionDefinition(
        "clients", False, "Cliente creado con ayuda de Noesis"
    ),
}

OUTCOME_TAXONOMY = frozenset({
    "payment_received", "quote_accepted", "job_invoiced",
})


@dataclass(frozen=True)
class ObservationContext:
    channel: str = "web"
    trigger_source: str = "user_initiated"
    completion_mode: str = "user_confirmed"
    source_event_type: str | None = None
    source_event_id: str | None = None


_CONTEXT: ContextVar[ObservationContext] = ContextVar(
    "noesis_value_observation_context", default=ObservationContext()
)


@contextmanager
def observation_context(
    *,
    channel: str,
    trigger_source: str,
    completion_mode: str,
    source_event_type: str | None = None,
    source_event_id: str | None = None,
):
    """Propaga el origen sin cambiar las firmas de las operaciones existentes."""
    context = ObservationContext(
        channel=_choice(channel, CHANNELS, "canal"),
        trigger_source=_choice(
            trigger_source, TRIGGER_SOURCES, "origen del trigger"
        ),
        completion_mode=_choice(
            completion_mode, COMPLETION_MODES, "forma de finalización"
        ),
        source_event_type=_short(source_event_type, 80),
        source_event_id=_short(source_event_id, 120),
    )
    token = _CONTEXT.set(context)
    try:
        yield context
    finally:
        _CONTEXT.reset(token)


def current_context() -> ObservationContext:
    return _CONTEXT.get()


def _choice(value, allowed: frozenset[str], label: str) -> str:
    clean = str(value or "").strip().lower()
    if clean not in allowed:
        raise ValueError(f"{label.capitalize()} no válido.")
    return clean


def _short(value, limit: int) -> str | None:
    clean = str(value or "").strip()
    return clean[:limit] or None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _utc_string(value: datetime | str | None) -> str:
    if value is None:
        return _utc_now()
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("La fecha del registro no es válida.") from exc
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat(
        timespec="seconds"
    )


def _metadata_json(metadata: dict | None) -> str | None:
    if not metadata:
        return None
    clean = {}
    for key, value in list(metadata.items())[:30]:
        name = str(key or "").strip()[:60]
        if not name or isinstance(value, (dict, list, tuple, set, bytes)):
            continue
        clean[name] = value
    encoded = json.dumps(clean, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > 4_000:
        raise ValueError("Los metadatos de valor son demasiado grandes.")
    return encoded


def _entity(entity_type, entity_id) -> tuple[str, str]:
    kind = _short(entity_type, 50)
    identifier = _short(entity_id, 120)
    if not kind or not identifier:
        raise ValueError("La acción necesita una entidad auditable.")
    return kind, identifier


def _business_exists(conn, business_id: int) -> bool:
    return bool(conn.execute(
        "SELECT 1 AS found FROM businesses WHERE id=?", (business_id,)
    ).fetchone())


def record_useful_action(
    business_id: int,
    action_family: str,
    *,
    entity_type: str,
    entity_id,
    idempotency_key: str | None = None,
    channel: str | None = None,
    trigger_source: str | None = None,
    completion_mode: str | None = None,
    source_event_type: str | None = None,
    source_event_id: str | None = None,
    metadata: dict | None = None,
    completed_at: datetime | str | None = None,
) -> dict:
    """Registra una operación terminal; repetir la clave devuelve la misma fila."""
    definition = ACTION_TAXONOMY.get(str(action_family or "").strip())
    if not definition:
        raise ValueError("La familia de acción útil no existe en la taxonomía.")
    entity_type, entity_id = _entity(entity_type, entity_id)
    context = current_context()
    channel = _choice(channel or context.channel, CHANNELS, "canal")
    trigger_source = _choice(
        trigger_source or context.trigger_source,
        TRIGGER_SOURCES,
        "origen del trigger",
    )
    completion_mode = _choice(
        completion_mode or context.completion_mode,
        COMPLETION_MODES,
        "forma de finalización",
    )
    key = _short(
        idempotency_key
        or f"v{TAXONOMY_VERSION}:{action_family}:{entity_type}:{entity_id}",
        240,
    )
    if not key:
        raise ValueError("La acción necesita una clave idempotente.")
    when = _utc_string(completed_at)
    event_type = _short(source_event_type or context.source_event_type, 80)
    event_id = _short(source_event_id or context.source_event_id, 120)
    metadata_json = _metadata_json(metadata)
    with db.get_conn() as conn:
        if not _business_exists(conn, int(business_id)):
            raise ValueError("Negocio no encontrado.")
        inserted = conn.execute(
            "INSERT INTO useful_actions "
            "(business_id, taxonomy_version, action_family, process_key, "
            "counts_for_wub, trigger_source, channel, completion_mode, status, "
            "entity_type, entity_id, idempotency_key, source_event_type, "
            "source_event_id, metadata_json, completed_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (business_id, idempotency_key) DO NOTHING RETURNING id",
            (
                int(business_id), TAXONOMY_VERSION, action_family,
                definition.process, definition.counts_for_wub, trigger_source,
                channel, completion_mode, entity_type, entity_id, key,
                event_type, event_id, metadata_json, when, when,
            ),
        ).fetchone()
        row = conn.execute(
            "SELECT * FROM useful_actions WHERE business_id=? AND idempotency_key=?",
            (int(business_id), key),
        ).fetchone()
        if inserted and row:
            conn.execute(
                "INSERT INTO useful_action_events "
                "(business_id, useful_action_id, event_kind, actor_type, occurred_at) "
                "VALUES (?, ?, 'completed', 'noesis', ?)",
                (int(business_id), row["id"], when),
            )
    return dict(row)


def observe_useful_action(*args, **kwargs) -> dict | None:
    """Escritor fail-open: la medición nunca rompe el trabajo del cliente."""
    if not config.VALUE_LEDGER_ENABLED:
        return None
    try:
        return record_useful_action(*args, **kwargs)
    except Exception:  # noqa: BLE001
        log.exception("No se pudo observar una acción útil.")
        return None


def transition_useful_action(
    business_id: int,
    useful_action_id: int,
    status: str,
    *,
    actor_type: str = "system",
    reason_code: str | None = None,
    occurred_at: datetime | str | None = None,
) -> dict | None:
    """Conserva el historial de una corrección, reversión o invalidación."""
    status = _choice(status, ACTION_STATUSES, "estado")
    actor_type = _choice(
        actor_type,
        frozenset({"owner", "worker", "noesis", "system", "integration"}),
        "actor",
    )
    when = _utc_string(occurred_at)
    with db.get_conn() as conn:
        current = conn.execute(
            "SELECT * FROM useful_actions WHERE id=? AND business_id=?",
            (int(useful_action_id), int(business_id)),
        ).fetchone()
        if not current:
            return None
        if current["status"] == status:
            return dict(current)
        conn.execute(
            "UPDATE useful_actions SET status=?, updated_at=? "
            "WHERE id=? AND business_id=?",
            (status, when, int(useful_action_id), int(business_id)),
        )
        conn.execute(
            "INSERT INTO useful_action_events "
            "(business_id, useful_action_id, event_kind, actor_type, reason_code, "
            "occurred_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                int(business_id), int(useful_action_id), status, actor_type,
                _short(reason_code, 80), when,
            ),
        )
        saved = conn.execute(
            "SELECT * FROM useful_actions WHERE id=? AND business_id=?",
            (int(useful_action_id), int(business_id)),
        ).fetchone()
    return dict(saved)


def record_useful_outcome(
    business_id: int,
    outcome_family: str,
    *,
    attribution_type: str,
    attribution_method: str,
    entity_type: str,
    entity_id,
    idempotency_key: str,
    useful_action_ids: list[int] | tuple[int, ...] = (),
    amount=None,
    currency: str | None = None,
    metadata: dict | None = None,
    occurred_at: datetime | str | None = None,
) -> dict:
    """Registra un resultado sin atribuir causalidad cuando no está demostrada."""
    outcome_family = str(outcome_family or "").strip()
    if outcome_family not in OUTCOME_TAXONOMY:
        raise ValueError("La familia de resultado no existe en la taxonomía.")
    attribution_type = _choice(
        attribution_type, ATTRIBUTION_TYPES, "tipo de atribución"
    )
    method = _short(attribution_method, 100)
    if not method:
        raise ValueError("El resultado necesita un método de atribución.")
    entity_type, entity_id = _entity(entity_type, entity_id)
    key = _short(idempotency_key, 240)
    if not key:
        raise ValueError("El resultado necesita una clave idempotente.")
    action_ids = sorted({int(value) for value in useful_action_ids})
    if attribution_type in {"direct", "assisted"} and not action_ids:
        raise ValueError("Una atribución directa o asistida necesita una acción enlazada.")
    amount_value = None
    currency_value = None
    if amount not in (None, ""):
        try:
            amount_value = Decimal(str(amount)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("El importe del resultado no es válido.") from exc
        if amount_value < 0:
            raise ValueError("El importe del resultado no puede ser negativo.")
        currency_value = str(currency or "EUR").strip().upper()[:3]
        if len(currency_value) != 3:
            raise ValueError("La moneda del resultado no es válida.")
    when = _utc_string(occurred_at)
    metadata_json = _metadata_json(metadata)
    with db.get_conn() as conn:
        if not _business_exists(conn, int(business_id)):
            raise ValueError("Negocio no encontrado.")
        if action_ids:
            placeholders = ",".join("?" for _ in action_ids)
            rows = conn.execute(
                f"SELECT id FROM useful_actions WHERE business_id=? "
                f"AND id IN ({placeholders})",
                [int(business_id), *action_ids],
            ).fetchall()
            if len(rows) != len(action_ids):
                raise ValueError("Alguna acción enlazada no pertenece al negocio.")
        conn.execute(
            "INSERT INTO useful_outcomes "
            "(business_id, taxonomy_version, attribution_version, outcome_family, "
            "attribution_type, attribution_method, entity_type, entity_id, amount, "
            "currency, idempotency_key, metadata_json, occurred_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (business_id, idempotency_key) DO NOTHING",
            (
                int(business_id), TAXONOMY_VERSION, ATTRIBUTION_VERSION,
                outcome_family, attribution_type, method, entity_type, entity_id,
                float(amount_value) if amount_value is not None else None,
                currency_value, key, metadata_json, when,
            ),
        )
        outcome = conn.execute(
            "SELECT * FROM useful_outcomes WHERE business_id=? AND idempotency_key=?",
            (int(business_id), key),
        ).fetchone()
        for action_id in action_ids:
            conn.execute(
                "INSERT INTO useful_action_outcomes "
                "(business_id, useful_action_id, useful_outcome_id, linked_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (int(business_id), action_id, outcome["id"], when),
            )
    return dict(outcome)


def observe_useful_outcome(*args, **kwargs) -> dict | None:
    if not config.VALUE_LEDGER_ENABLED:
        return None
    try:
        return record_useful_outcome(*args, **kwargs)
    except Exception:  # noqa: BLE001
        log.exception("No se pudo observar un resultado útil.")
        return None


def observe_trust_decision(*args, **kwargs) -> dict | None:
    """Amplía el ledger de asistente sin convertir la métrica en dependencia."""
    if not config.VALUE_LEDGER_ENABLED:
        return None
    try:
        return db.record_assistant_action(*args, **kwargs)
    except Exception:  # noqa: BLE001
        log.exception("No se pudo observar una decisión sobre una propuesta.")
        return None


def list_useful_actions(
    business_id: int,
    *,
    action_family: str | None = None,
    entity_type: str | None = None,
    entity_id=None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
) -> list[dict]:
    q = "SELECT * FROM useful_actions WHERE business_id=?"
    params: list = [int(business_id)]
    for clause, value in (
        ("action_family=?", action_family),
        ("entity_type=?", entity_type),
        ("entity_id=?", None if entity_id is None else str(entity_id)),
    ):
        if value is not None:
            q += f" AND {clause}"
            params.append(value)
    if since:
        q += " AND completed_at>=?"
        params.append(since)
    if until:
        q += " AND completed_at<?"
        params.append(until)
    q += " ORDER BY completed_at DESC, id DESC LIMIT ?"
    params.append(max(1, min(int(limit or 200), 1000)))
    with db.get_conn() as conn:
        return [dict(row) for row in conn.execute(q, params).fetchall()]


def list_useful_outcomes(business_id: int, limit: int = 200) -> list[dict]:
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM useful_outcomes WHERE business_id=? "
            "ORDER BY occurred_at DESC, id DESC LIMIT ?",
            (int(business_id), max(1, min(int(limit or 200), 1000))),
        ).fetchall()
    return [dict(row) for row in rows]


def observe_payment_received(
    business_id: int,
    *,
    invoice_id: int,
    payment_id: int,
    amount,
    occurred_at: datetime | str | None = None,
) -> dict | None:
    """Atribuye un cobro solo si existe un seguimiento previo demostrable."""
    if not config.VALUE_LEDGER_ENABLED:
        return None
    try:
        when = _utc_string(occurred_at)
        reminders = list_useful_actions(
            business_id,
            action_family="payment_reminder_sent",
            entity_type="invoice",
            entity_id=invoice_id,
            until=when,
            limit=1,
        )
        action_ids = [reminders[0]["id"]] if reminders else []
        return record_useful_outcome(
            business_id,
            "payment_received",
            attribution_type="assisted" if action_ids else "observed",
            attribution_method=(
                "reminder_before_payment_v1"
                if action_ids else "payment_observed_v1"
            ),
            entity_type="invoice_payment",
            entity_id=payment_id,
            idempotency_key=f"payment_received:invoice_payment:{payment_id}",
            useful_action_ids=action_ids,
            amount=amount,
            currency="EUR",
            metadata={"invoice_id": int(invoice_id)},
            occurred_at=when,
        )
    except Exception:  # noqa: BLE001
        log.exception("No se pudo observar el cobro como resultado útil.")
        return None


def observe_quote_accepted(
    business_id: int, *, quote_id: int, occurred_at: datetime | str | None = None
) -> dict | None:
    if not config.VALUE_LEDGER_ENABLED:
        return None
    try:
        when = _utc_string(occurred_at)
        actions = []
        for family in ("quote_sent", "quote_prepared"):
            actions = list_useful_actions(
                business_id,
                action_family=family,
                entity_type="quote",
                entity_id=quote_id,
                limit=1,
            )
            if actions:
                break
        action_ids = [actions[0]["id"]] if actions else []
        return record_useful_outcome(
            business_id,
            "quote_accepted",
            attribution_type="assisted" if action_ids else "observed",
            attribution_method=(
                "quote_action_before_acceptance_v1"
                if action_ids else "quote_acceptance_observed_v1"
            ),
            entity_type="quote",
            entity_id=quote_id,
            idempotency_key=f"quote_accepted:{quote_id}",
            useful_action_ids=action_ids,
            occurred_at=when,
        )
    except Exception:  # noqa: BLE001
        log.exception("No se pudo observar la aceptación del presupuesto.")
        return None


def observe_job_invoiced(
    business_id: int,
    *,
    job_id: int,
    invoice_id: int,
    occurred_at: datetime | str | None = None,
) -> dict | None:
    """Relaciona un cierre de trabajo con su factura ya emitida."""
    if not config.VALUE_LEDGER_ENABLED:
        return None
    try:
        actions = []
        for family, entity_type, entity_id in (
            ("job_completed", "job", job_id),
            ("invoice_issued", "invoice", invoice_id),
        ):
            rows = list_useful_actions(
                business_id,
                action_family=family,
                entity_type=entity_type,
                entity_id=entity_id,
                limit=1,
            )
            if rows:
                actions.append(rows[0]["id"])
        return record_useful_outcome(
            business_id,
            "job_invoiced",
            attribution_type="direct" if len(actions) == 2 else (
                "assisted" if actions else "observed"
            ),
            attribution_method=(
                "job_completion_and_invoice_issue_v1"
                if len(actions) == 2 else "job_invoice_link_observed_v1"
            ),
            entity_type="job_invoice",
            entity_id=f"{job_id}:{invoice_id}",
            idempotency_key=f"job_invoiced:{job_id}:{invoice_id}",
            useful_action_ids=actions,
            metadata={"job_id": job_id, "invoice_id": invoice_id},
            occurred_at=occurred_at,
        )
    except Exception:  # noqa: BLE001
        log.exception("No se pudo observar el trabajo facturado.")
        return None


def observe_job_invoiced_from_invoice(
    business_id: int,
    *,
    invoice_id: int,
    occurred_at: datetime | str | None = None,
) -> dict | None:
    """Resuelve el trabajo enlazado sin introducir una lectura crítica en emisión."""
    if not config.VALUE_LEDGER_ENABLED:
        return None
    try:
        with db.get_conn() as conn:
            completion = conn.execute(
                "SELECT job_id FROM job_completions WHERE business_id=? "
                "AND invoice_id=? ORDER BY id DESC LIMIT 1",
                (business_id, invoice_id),
            ).fetchone()
        if not completion:
            return None
        return observe_job_invoiced(
            business_id,
            job_id=completion["job_id"],
            invoice_id=invoice_id,
            occurred_at=occurred_at,
        )
    except Exception:  # noqa: BLE001
        log.exception("No se pudo resolver el trabajo de la factura observada.")
        return None


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(str(name or DEFAULT_TIMEZONE))
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _aware_utc(value: datetime | None = None) -> datetime:
    point = value or datetime.now(timezone.utc)
    if point.tzinfo is None:
        point = point.replace(tzinfo=timezone.utc)
    return point.astimezone(timezone.utc)


def _utc_bound(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat(
        timespec="seconds"
    )


def _closed_week_bounds(
    as_of: datetime | None, timezone_name: str
) -> tuple[datetime, datetime]:
    zone = _zone(timezone_name)
    local = _aware_utc(as_of).astimezone(zone)
    current_monday = local.date() - timedelta(days=local.weekday())
    end_local = datetime.combine(current_monday, time.min, tzinfo=zone)
    start_local = end_local - timedelta(days=7)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _business_timezone(business_id: int) -> str:
    business = db.get_business(business_id) or {}
    return str(business.get("timezone") or DEFAULT_TIMEZONE)


def wub_snapshot(
    business_id: int,
    *,
    start: datetime,
    end: datetime,
) -> dict:
    since = _utc_bound(_aware_utc(start))
    until = _utc_bound(_aware_utc(end))
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, action_family, process_key, completed_at "
            "FROM useful_actions WHERE business_id=? AND counts_for_wub=TRUE "
            "AND status IN ('completed', 'corrected') "
            "AND completed_at>=? AND completed_at<? "
            "ORDER BY completed_at, id",
            (int(business_id), since, until),
        ).fetchall()
    processes = sorted({row["process_key"] for row in rows})
    return {
        "business_id": int(business_id),
        "start": since,
        "end": until,
        "core_actions": len(rows),
        "process_count": len(processes),
        "processes": processes,
        "action_ids": [row["id"] for row in rows],
        "is_wub": len(rows) >= 3 and len(processes) >= 2,
    }


def rolling_wub(
    business_id: int, *, as_of: datetime | None = None
) -> dict:
    end = _aware_utc(as_of)
    snapshot = wub_snapshot(
        business_id, start=end - timedelta(days=7), end=end
    )
    snapshot["window"] = "rolling_7_days"
    return snapshot


def official_wub(
    business_id: int, *, as_of: datetime | None = None, weeks_back: int = 0
) -> dict:
    timezone_name = _business_timezone(business_id)
    start, end = _closed_week_bounds(as_of, timezone_name)
    offset = timedelta(days=7 * max(0, int(weeks_back)))
    snapshot = wub_snapshot(business_id, start=start - offset, end=end - offset)
    snapshot.update({"window": "closed_week", "timezone": timezone_name})
    return snapshot


def wub_consistency(
    business_id: int, *, as_of: datetime | None = None, weeks: int = 4
) -> dict:
    weeks = max(1, min(int(weeks or 4), 52))
    snapshots = [
        official_wub(business_id, as_of=as_of, weeks_back=index)
        for index in range(weeks)
    ]
    consecutive = 0
    for snapshot in snapshots:
        if not snapshot["is_wub"]:
            break
        consecutive += 1
    return {
        "business_id": int(business_id),
        "wub_weeks": sum(1 for item in snapshots if item["is_wub"]),
        "weeks_observed": weeks,
        "label": f"{sum(1 for item in snapshots if item['is_wub'])}/{weeks}",
        "consecutive_wub_weeks": consecutive,
        "weeks": snapshots,
    }


def _parse_business_created(business: dict) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(business.get("created_at") or ""))
    except ValueError:
        return None
    zone = _zone(business.get("timezone"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=zone)
    return value.astimezone(timezone.utc)


def business_is_wub_eligible(
    business: dict,
    *,
    window_start: datetime,
) -> tuple[bool, str | None]:
    if not business or business.get("is_demo"):
        return False, "demo"
    if not bool(business.get("value_metrics_eligible", True)):
        return False, "excluded"
    onboarding = bool(business.get("onboarding_done")) or bool(
        business.get("onboarding_profile_completed")
        and business.get("onboarding_preferences_completed")
    )
    if not onboarding:
        return False, "onboarding"
    if not db.subscription_allows_access(business):
        return False, "access"
    created = _parse_business_created(business)
    if created is None or created > _aware_utc(window_start):
        return False, "new_business"
    return True, None


def weekly_wub_rate(*, as_of: datetime | None = None) -> dict:
    eligible = []
    excluded: dict[str, int] = {}
    snapshots = []
    for business in db.list_businesses():
        timezone_name = str(business.get("timezone") or DEFAULT_TIMEZONE)
        start, end = _closed_week_bounds(as_of, timezone_name)
        allowed, reason = business_is_wub_eligible(
            business, window_start=start
        )
        if not allowed:
            excluded[reason or "unknown"] = excluded.get(reason or "unknown", 0) + 1
            continue
        eligible.append(business["id"])
        snapshots.append(wub_snapshot(business["id"], start=start, end=end))
    wub_count = sum(1 for item in snapshots if item["is_wub"])
    depth = {"0": 0, "1": 0, "2": 0, "3": 0, "4+": 0}
    for item in snapshots:
        value = item["process_count"]
        depth["4+" if value >= 4 else str(value)] += 1
    return {
        "eligible_businesses": len(eligible),
        "wub_count": wub_count,
        "wub_rate": (
            round(wub_count / len(eligible) * 100, 1) if eligible else None
        ),
        "depth_distribution": depth,
        "excluded": excluded,
        "businesses": snapshots,
    }


def trust_metrics(business_id: int) -> dict:
    """Aceptación por proceso/familia usando el ledger de acciones existente."""
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT process_key, action_family, correlation_key, status, created_at "
            "FROM assistant_actions WHERE business_id=? AND process_key IS NOT NULL "
            "AND action_family IS NOT NULL AND correlation_key IS NOT NULL "
            "ORDER BY created_at, id",
            (int(business_id),),
        ).fetchall()
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        key = (row["process_key"], row["action_family"], row["correlation_key"])
        groups.setdefault(key, []).append(dict(row))
    result: dict[tuple[str, str], dict] = {}
    for (process, family, _correlation), events in groups.items():
        bucket = result.setdefault((process, family), {
            "process": process, "action_family": family, "offered": 0,
            "accepted": 0, "rejected": 0, "pending": 0, "corrected": 0,
            "reverted": 0, "confirmation_seconds": [],
        })
        proposal = next((event for event in events if event["status"] == "proposed"), None)
        if not proposal:
            continue
        bucket["offered"] += 1
        accepted = next(
            (event for event in events if event["status"] in {"approved", "executed"}),
            None,
        )
        rejected = next(
            (event for event in events if event["status"] in {"cancelled", "rejected"}),
            None,
        )
        if accepted:
            bucket["accepted"] += 1
            try:
                start = datetime.fromisoformat(str(proposal["created_at"]))
                end = datetime.fromisoformat(str(accepted["created_at"]))
                bucket["confirmation_seconds"].append(max(0, int((end - start).total_seconds())))
            except ValueError:
                pass
        elif rejected:
            bucket["rejected"] += 1
        else:
            bucket["pending"] += 1
        bucket["corrected"] += int(any(e["status"] == "corrected" for e in events))
        bucket["reverted"] += int(any(e["status"] == "reverted" for e in events))
    metrics = []
    for bucket in result.values():
        decided = bucket["accepted"] + bucket["rejected"]
        times = bucket.pop("confirmation_seconds")
        bucket["acceptance_rate"] = (
            round(bucket["accepted"] / decided * 100, 1) if decided else None
        )
        bucket["average_confirmation_seconds"] = (
            round(sum(times) / len(times)) if times else None
        )
        metrics.append(bucket)
    return {"business_id": int(business_id), "rows": sorted(
        metrics, key=lambda item: (item["process"], item["action_family"])
    )}


def activation_snapshot(business_id: int) -> dict:
    business = db.get_business(business_id)
    if not business:
        raise ValueError("Negocio no encontrado.")
    actions = list_useful_actions(business_id, limit=1000)
    first = min(actions, key=lambda item: (item["completed_at"], item["id"])) if actions else None
    created = _parse_business_created(business)
    first_at = None
    seconds = None
    if first:
        first_at = datetime.fromisoformat(str(first["completed_at"])).replace(
            tzinfo=timezone.utc
        )
        if created:
            seconds = max(0, int((first_at - created).total_seconds()))
    return {
        "business_id": int(business_id),
        "first_useful_action_at": first["completed_at"] if first else None,
        "seconds_to_first_useful_action": seconds,
        "first_action_within_3_days": bool(seconds is not None and seconds <= 3 * 86400),
        "rolling_wub": rolling_wub(business_id),
    }


def known_control_state(business_id: int) -> dict:
    """Estado honesto: solo afirma ausencia de pendientes conocidos y cubiertos."""
    business = db.get_business(business_id)
    if not business:
        raise ValueError("Negocio no encontrado.")
    health = db.business_operational_health(business_id)
    integrations = db.integration_catalog(business_id)
    unknown = [
        item["name"] for item in integrations
        if item.get("active") and item.get("last_error")
    ]
    if unknown or health["level"] == "error":
        state = "unknown"
        title = "Hay algo que no he podido comprobar"
    elif health["attention"]:
        state = "attention"
        title = "Hay cosas que necesitan tu atención"
    else:
        state = "under_control"
        title = "Todo bajo control"
    return {
        "state": state,
        "title": title,
        "explanation": (
            "No hay tareas importantes pendientes detectadas por Noesis en los "
            "procesos conectados."
            if state == "under_control" else health["summary"]
        ),
        "attention": health["attention"],
        "unknown_integrations": unknown,
        "scope": "datos y procesos conectados a Noesis",
    }


def admin_snapshot(business_id: int | None = None) -> dict:
    """Metadatos internos mínimos; nunca expone contenido operativo."""
    if business_id is not None:
        business = db.get_business(int(business_id))
        if not business:
            raise ValueError("Negocio no encontrado.")
        return {
            "business_id": int(business_id),
            "rolling_wub": rolling_wub(int(business_id)),
            "consistency": wub_consistency(int(business_id)),
            "activation": activation_snapshot(int(business_id)),
            "trust": trust_metrics(int(business_id)),
            "control": known_control_state(int(business_id)),
            "actions": list_useful_actions(int(business_id), limit=100),
            "outcomes": list_useful_outcomes(int(business_id), limit=100),
        }
    return {"weekly": weekly_wub_rate()}
