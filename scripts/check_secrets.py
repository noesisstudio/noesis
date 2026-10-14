"""Escanea archivos versionados sin reescribir la baseline ni depender de sus líneas.

Conserva los detectores y filtros de detect-secrets. Las excepciones siguen siendo
por archivo, tipo y huella exacta; nunca se aceptan hallazgos nuevos automáticamente.
"""

import json
from pathlib import Path
import subprocess
import sys


def scan(files: list[str], data: dict):
    from detect_secrets.core import baseline
    from detect_secrets.core.secrets_collection import SecretsCollection
    from detect_secrets.settings import transient_settings

    # El repositorio puede haberse preparado en Windows y CI ejecutarse en Linux.
    data = dict(data)
    data["results"] = {
        name.replace("\\", "/"): [
            {**item, "filename": name.replace("\\", "/")} for item in entries
        ] for name, entries in data["results"].items()
    }
    with transient_settings(data):
        known = baseline.load(data, filename=".secrets.baseline")
        found = SecretsCollection()
        for name in files:
            found.scan_file(name)
        return found - known


def main() -> int:
    # detect-secrets abre texto con el encoding del intérprete; cp1252 puede
    # omitir silenciosamente UTF-8. Reejecutar sin depender del locale del host.
    if not sys.flags.utf8_mode:
        return subprocess.call([sys.executable, "-X", "utf8", str(Path(__file__).resolve())])
    files = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True,
    ).stdout.decode("utf-8").split("\0")
    data = json.loads(Path(".secrets.baseline").read_text(encoding="utf-8"))
    new = scan([name for name in files if name], data)
    if new:
        for name, secret in new:
            # No imprimir contenido sensible, solo localización y detector.
            print(f"Posible secreto nuevo: {name}:{secret.line_number} ({secret.type})")
        return 1
    print("Sin secretos nuevos en los archivos versionados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
