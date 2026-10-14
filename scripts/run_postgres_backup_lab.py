"""Suite PostgreSQL del release base y V2 sobre instancia nueva, sólo fixtures."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from noesis.web.postgres_backup_tools import disposable_target, outbound_blocked, run, safe_environment

CASES = [
    ("migrations32", ["-m", "noesis.migrations", "upgrade", "32"]),
    ("migrations historical", ["tests/postgres_migration_smoke.py"]),
    ("HTTP + backup + restore", ["tests/postgres_smoke.py"]),
    ("Core", ["-m", "tests.postgres_financial_core"]),
    ("Operations/Auth", ["-m", "tests.postgres_financial_operations"]),
    ("Economic Events", ["-m", "unittest", "tests.postgres_economic_persistence.EconomicPersistencePostgres"]),
    ("Borrowed writers", ["-m", "unittest", "tests.postgres_borrowed_writers.BorrowedWritersPostgres"]),
    ("Invoice Capture", ["-m", "unittest", "tests.postgres_invoice_capture.InvoiceCapturePostgres"]),
    ("Payment/Bank", ["-m", "unittest", "tests.postgres_payment_bank_capture.PaymentBankCapturePostgres"]),
    ("Supplier/Expense", ["-m", "unittest", "tests.postgres_purchasing_capture.PurchasingCapturePostgres"]),
    ("Channels", ["-m", "unittest", "tests.postgres_financial_channels.FinancialChannelsPostgres"]),
    ("History inventory", ["-m", "unittest", "tests.postgres_financial_history_inventory.HistoryInventoryPostgres"]),
    ("History cutoff", ["-m", "unittest", "tests.postgres_financial_history_cutoff.HistoryCutoffPostgres"]),
    ("History import", ["-m", "unittest", "tests.postgres_financial_history_import.HistoryImportPostgres"]),
    ("History reconciliation", ["-m", "unittest", "tests.postgres_financial_history_reconciliation.HistoryReconciliationPostgres"]),
    ("legacy catalog53", ["tests/postgres_legacy_smoke.py"]),
    ("privacy + rollback", ["-m", "tests.postgres_release_smoke"]),
    ("A75 Readiness", ["-m", "unittest", "tests.postgres_financial_readiness", "-v"]),
    ("Lineage Foundation", ["-m", "unittest", "tests.postgres_schema_lineage", "-v"]),
    ("POSTGRES_BACKUP_V2_CANONICAL75", ["-m", "unittest", "tests.postgres_backup_v2", "tests.test_postgres_backup_v2", "tests.test_postgres_backup_identity", "-v"]),
]


def invoke(args, environment):
    try:
        return subprocess.run([sys.executable, *args], env=environment, shell=False,
                              capture_output=True, timeout=1800)  # nosec B603
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(args, 124, exc.stdout or b'', exc.stderr or b'')


def run_stage(name, args, environment):
    canonical75 = [["-m", "noesis.migrations", "upgrade"],
                   ["-m", "tests.postgres_canonical75_precondition"]]
    preparations = {
        'migrations historical': [["-m", "noesis.migrations", "upgrade", "32"]],
        'legacy catalog53': [["-m", "noesis.migrations", "upgrade"]],
        'HTTP + backup + restore': canonical75,
        'privacy + rollback': [*canonical75, ["tests/postgres_smoke.py"]],
    }.get(name, [])
    preparation_result = None
    for preparation in preparations:
        preparation_result = invoke(preparation, environment)
        print('PRECONDITION', name, preparation_result.returncode, flush=True)
        print((preparation_result.stdout + preparation_result.stderr).decode(errors='replace'), flush=True)
        if preparation_result.returncode:
            return preparation_result, preparation_result.returncode
    if name == "legacy catalog53":
        environment = {**environment, "PYTHONPATH": str(Path(".legacy-baseline/src").resolve())}
    result = invoke(args, environment)
    return result, None if preparation_result is None else preparation_result.returncode


def main():
    if not outbound_blocked():
        raise SystemExit("Ejecutar dentro de namespace sin outbound, como usuario no root")
    with tempfile.TemporaryDirectory(prefix="noesis-pg-ci-") as temporary, disposable_target() as source:
        root = Path(temporary)
        with source.connection() as conn:
            conn.autocommit = True
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier("noesis_ci")))
        values = conninfo_to_dict(source.dsn)
        # Algunas regresiones históricas reconstruyen la URL y eliminan el query
        # de socket. Loopback sólo dentro del namespace sin interfaz exterior.
        data = source.directory / "data"
        with (data / "postgresql.conf").open("a") as output:
            output.write("\nlisten_addresses='127.0.0.1'\n")
        hba = data / "pg_hba.conf"
        hba.write_text("host all all 127.0.0.1/32 trust\n" + hba.read_text())
        run([source.toolchain.binary("pg_ctl"), "-D", str(data), "-l", str(source.directory / "server.log"),
             "-w", "restart"], env=safe_environment(), timeout=60)
        env = os.environ.copy()
        env.update(DATABASE_URL=f"postgresql://{values['user']}@127.0.0.1/noesis_ci",
                   NOESIS_DOCS_PATH=str(root / "documents"), NOESIS_BACKUP_DIR=str(root / "backups"),
                   NOESIS_DB_PATH=str(root / "unused.db"), NOESIS_SECRET="noesis-ci-secret-fixed-32-characters-minimum",
                   NOESIS_VALUE_LEDGER_ENABLED="false", NOESIS_VALUE_LEDGER_ADMIN_ENABLED="false")
        results = []
        for index, (name, args) in enumerate(CASES, 1):
            # La única DB reseteable pertenece al cluster sellado creado arriba.
            # Nunca heredar schema/datos/carreras de una etapa anterior.
            with source.connection() as manager:
                manager.autocommit = True
                manager.execute('DROP DATABASE IF EXISTS noesis_ci WITH (FORCE)')
                manager.execute('CREATE DATABASE noesis_ci TEMPLATE template0')
                database_oid = manager.execute("SELECT oid FROM pg_database WHERE datname='noesis_ci'").fetchone()[0]
            stage_root = root / str(index)
            stage_root.mkdir()
            current_env = {**env, 'NOESIS_DOCS_PATH':str(stage_root/'documents'),
                           'NOESIS_BACKUP_DIR':str(stage_root/'backups'),
                           'NOESIS_DB_PATH':str(stage_root/'unused.db')}
            started = time.monotonic()
            result, precondition_returncode = run_stage(name, args, current_env)
            print(name, "PASS" if result.returncode == 0 else "FAIL", flush=True)
            output = (result.stdout + result.stderr).decode(errors="replace")
            # Sólo fixtures sintéticos. Conservar el resultado íntegro para CI.
            print(output, flush=True)
            results.append({"name": name, "returncode": result.returncode,
                            "duration": round(time.monotonic() - started, 3),
                            "database_oid": database_oid, "isolated_stage": index,
                            "precondition_returncode": precondition_returncode})
        print(json.dumps(results, indent=2))
    return 1 if any(row["returncode"] for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
