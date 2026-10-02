"""Proceso aislado de carrera; guardado exclusivamente para PostgreSQL local de CI."""

from datetime import datetime
import json
import sys
from urllib.parse import urlsplit

from noesis import config, db
from noesis.core.persistence import FinancialSession
from noesis.economic_events.contracts import EconomicEvent, EventRelation
from noesis.economic_events.service import EconomicEvents
from noesis.financial_operations.contracts import ConflictError, Principal, strict_json


def main():
    url = urlsplit(config.DATABASE_URL)
    if (
        url.hostname not in {"localhost", "127.0.0.1", "::1"}
        or url.path != "/noesis_ci"
        or config.IS_PRODUCTION
    ):
        raise RuntimeError("Solo PostgreSQL local /noesis_ci.")
    args = json.loads(sys.argv[1])
    raw = strict_json(args["event"])
    raw.pop("canonical_version")
    raw.pop("amount")
    raw["occurred_at"] = (
        None if raw["occurred_at"] is None else datetime.fromisoformat(raw["occurred_at"])
    )
    raw["observed_at"] = datetime.fromisoformat(raw["observed_at"])
    raw["relations"] = tuple(EventRelation(**r) for r in raw["relations"])
    event = EconomicEvent(**raw)
    print("READY", flush=True)
    if input() != "go":
        raise RuntimeError("Barrera no válida.")
    try:
        with db.get_conn() as conn:
            service = EconomicEvents(FinancialSession(conn), args["business_id"])
            stored = service.append(
                Principal(args["user_id"], 0),
                event,
                operation_uuid=args["operation_uuid"],
                event_slot="primary",
                revision_reader=lambda *_: event.source_revision,
            )
        print(
            json.dumps(
                dict(
                    event_uuid=str(stored.event.event_id),
                    sequence=stored.business_sequence,
                    record_hash=stored.record_hash,
                )
            )
        )
    except ConflictError:
        print(json.dumps(dict(conflict=True)))


if __name__ == "__main__":
    main()
