"""Crash worker sólo para namespace PostgreSQL sintético /noesis_ci."""

import sys
from urllib.parse import urlsplit
from unittest.mock import patch

from noesis import config, db, migrations


def main():
    url = urlsplit(config.DATABASE_URL)
    if (config.IS_PRODUCTION or url.hostname not in ("127.0.0.1", "localhost")
            or url.path != "/noesis_ci" or "lineage_case_" not in config.DATABASE_URL):
        raise SystemExit("Sólo namespace sintético de lineage.")
    boundary = sys.argv[1]
    def stop():
        print("READY", flush=True)
        sys.stdin.readline()
    if boundary == "before_registry":
        original = migrations._upgrade_readiness75
        def paused(conn):
            original(conn)
            stop()
        entries = migrations.MIGRATIONS[:-1] + ((75, "evaluacion_readiness_financiera", paused, migrations._downgrade_readiness75),)
        with patch.object(migrations, "MIGRATIONS", entries):
            migrations.upgrade()
    elif boundary == "after_registry":
        with db.get_conn() as conn:
            migrations.upgrade_connection(conn)
            stop()
    else:
        raise SystemExit("Frontera desconocida.")


if __name__ == "__main__":
    main()
