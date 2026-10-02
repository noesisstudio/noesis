"""Revisión de estado actual mutable; no reconstruye historia anterior."""

TABLES = ("received_invoices", "expenses", "bank_transactions")


def upgrade(conn):
    for table in TABLES:
        if conn.dialect == "sqlite":
            columns = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        else:
            columns = [
                r["column_name"]
                for r in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?",
                    (table,),
                ).fetchall()
            ]
        if "_financial_revision" not in columns:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN _financial_revision BIGINT NOT NULL DEFAULT 1 CHECK (_financial_revision > 0)"
            )
        fields = [c for c in columns if c != "_financial_revision"]
        if conn.dialect == "sqlite":
            changed = " OR ".join(f"OLD.{c} IS NOT NEW.{c}" for c in fields)
            conn.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_revision_insert
                BEFORE INSERT ON {table} WHEN NEW._financial_revision <> 1
                BEGIN SELECT RAISE(ABORT, 'revision inicial uno'); END""")
            # execute separado: executescript confirmaría la transacción SQLite.
            conn.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_revision_guard
                BEFORE UPDATE ON {table}
                WHEN NEW._financial_revision <> OLD._financial_revision
                AND NEW._financial_revision <> OLD._financial_revision + 1
                BEGIN SELECT RAISE(ABORT, 'revision no monotona'); END""")
            conn.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_revision_bump
                AFTER UPDATE ON {table}
                WHEN NEW._financial_revision = OLD._financial_revision AND ({changed})
                BEGIN UPDATE {table} SET _financial_revision=OLD._financial_revision+1
                WHERE business_id=NEW.business_id AND id=NEW.id; END""")
        else:
            changed = " OR ".join(f"OLD.{c} IS DISTINCT FROM NEW.{c}" for c in fields)
            conn.execute(f"""CREATE OR REPLACE FUNCTION {table}_revision_bump() RETURNS trigger AS $$
                BEGIN
                IF TG_OP='INSERT' THEN
                    IF NEW._financial_revision<>1 THEN
                        RAISE EXCEPTION 'revision inicial uno' USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                END IF;
                IF NEW._financial_revision <> OLD._financial_revision
                   AND NEW._financial_revision <> OLD._financial_revision+1 THEN
                    RAISE EXCEPTION 'revision no monotona' USING ERRCODE = '23514';
                END IF;
                IF NEW._financial_revision = OLD._financial_revision AND ({changed}) THEN
                    NEW._financial_revision := OLD._financial_revision+1;
                END IF;
                RETURN NEW; END; $$ LANGUAGE plpgsql""")
            conn.execute(f"DROP TRIGGER IF EXISTS {table}_revision_bump ON {table}")
            conn.execute(
                f"CREATE TRIGGER {table}_revision_bump BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_revision_bump()"
            )


def downgrade(conn):
    incorporated = conn.execute(
        "SELECT 1 FROM economic_events WHERE source_type IN "
        "('received_invoice','expense','bank_transaction') LIMIT 1"
    ).fetchone()
    if incorporated:
        raise ValueError("No retirar revisiones mientras exista evidencia económica mutable.")
    for table in TABLES:
        if conn.dialect == "sqlite":
            for suffix in ("guard", "bump", "insert"):
                conn.execute(f"DROP TRIGGER IF EXISTS {table}_revision_{suffix}")
        else:
            conn.execute(f"DROP TRIGGER IF EXISTS {table}_revision_bump ON {table}")
            conn.execute(f"DROP FUNCTION IF EXISTS {table}_revision_bump()")
        conn.execute(f"ALTER TABLE {table} DROP COLUMN _financial_revision")
