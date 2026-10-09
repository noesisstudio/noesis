"""Verificador PostgreSQL del contexto firmado; no concede permisos de negocio."""

from .execution_context import signing_key

KEYS = "financial_execution_verifier_key"


def install(conn):
    if conn.dialect != "postgres":
        return
    from psycopg import sql

    schema = conn.execute_exact("SELECT current_schema() AS name").fetchone()["name"]
    qualified = sql.Identifier(schema, KEYS).as_string(conn.raw)
    conn.execute(f"CREATE TABLE {qualified} (id INTEGER PRIMARY KEY CHECK(id=1), verifier BYTEA NOT NULL CHECK(octet_length(verifier)=32), usable BOOLEAN NOT NULL)")
    from noesis import config
    usable = len(config.SECRET_KEY.encode()) >= 32 and config.SECRET_KEY != "dev-secret-cambiar-en-produccion"
    conn.execute_exact(f"INSERT INTO {qualified} VALUES (1,?,?)", (signing_key(), usable))
    conn.execute(f"REVOKE ALL ON {qualified} FROM PUBLIC")
    # RFC2104, SHA256 nativo PostgreSQL: no pgcrypto ni extensión adicional.
    conn.execute(f"""CREATE FUNCTION noesis_execution_context() RETURNS jsonb
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $fn$
      DECLARE body text; signature text; key bytea; ipad bytea; opad bytea;
        calculated text; proof jsonb; i integer; usable boolean;
      BEGIN
        body := current_setting('noesis.execution_context',true);
        signature := current_setting('noesis.execution_signature',true);
        IF body IS NULL OR body='' OR signature IS NULL OR length(signature)<>64 THEN RETURN '{{}}'::jsonb; END IF;
        -- El login runtime no puede ser propietario, superuser ni lector de clave.
        -- No confiar en SET ROLE: se comprueba session_user, no current_user definer.
        IF has_table_privilege(session_user,'{qualified}','SELECT') OR
           EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND (rolsuper OR rolcreaterole OR rolbypassrls))
          THEN RETURN '{{}}'::jsonb; END IF;
        SELECT verifier, {qualified}.usable INTO STRICT key, usable FROM {qualified} WHERE id=1;
        IF NOT usable THEN RETURN '{{}}'::jsonb; END IF;
        key := key || decode(repeat('00',32),'hex');
        ipad := key; opad := key;
        FOR i IN 0..63 LOOP
          ipad := set_byte(ipad,i,get_byte(key,i) # 54);
          opad := set_byte(opad,i,get_byte(key,i) # 92);
        END LOOP;
        calculated := encode(sha256(opad || sha256(ipad || convert_to(body,'UTF8'))),'hex');
        IF signature<>calculated THEN RETURN '{{}}'::jsonb; END IF;
        proof := body::jsonb;
        IF proof->>'tx'<>pg_current_xact_id()::text OR (proof->>'backend')::integer<>pg_backend_pid()
          THEN RETURN '{{}}'::jsonb; END IF;
        RETURN proof;
      EXCEPTION WHEN invalid_text_representation OR no_data_found OR too_many_rows THEN RETURN '{{}}'::jsonb;
      END $fn$""")
    from noesis.financial_history.schema import guard

    for action in ("INSERT", "UPDATE", "DELETE"):
        guard(conn, KEYS + "_" + action.lower(), KEYS, action, "TRUE")


def uninstall(conn):
    if conn.dialect != "postgres":
        return
    from noesis.financial_history.import_schema import _drop

    for action in ("insert", "update", "delete"):
        _drop(conn, KEYS + "_" + action, KEYS)
    conn.execute("DROP FUNCTION noesis_execution_context()")
    conn.execute("DROP TABLE " + KEYS)
