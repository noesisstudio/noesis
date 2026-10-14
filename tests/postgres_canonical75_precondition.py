"""Precondición explícita del harness; sólo su DB sintética ya migrada."""
from noesis import db
from noesis.schema_lineage import require_runtime
from noesis.web.postgres_backup_identity import expected_identities


def main():
    with db.get_conn() as conn:
        observed = require_runtime(conn)
        rows = conn.execute("SELECT version,name FROM schema_migrations ORDER BY version").fetchall()
        identities = [[row["version"], row["name"]] for row in rows]
        if observed.schema_version != 75 or identities != expected_identities():
            raise AssertionError("CANONICAL75_PRECONDITION_FAILED")
        if identities[73:] != [[74, "captacion_hoja_y_tipo"], [75, "evaluacion_readiness_financiera"]]:
            raise AssertionError("CANONICAL75_IDENTITIES_FAILED")
    print("CANONICAL75_PRECONDITION PASS: exact registry and physical profile")


if __name__ == "__main__":
    main()
