"""Gate de build: mismo major nativo que requiere el contrato V2."""
import re
import subprocess


def main():
    for binary in ("pg_dump", "pg_restore", "initdb", "pg_ctl", "postgres"):
        result = subprocess.run([binary, "--version"], shell=False, capture_output=True,
                                timeout=15, check=True)  # nosec B603,B607
        version = result.stdout.decode().strip()
        if not re.fullmatch(r"\S+ \(PostgreSQL\) 18\.6(?: .*|)", version):
            raise SystemExit("POSTGRES_18_6_TOOLCHAIN_REQUIRED")
        print(version)


if __name__ == "__main__":
    main()
