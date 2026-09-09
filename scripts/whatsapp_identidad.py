"""Dice qué identidad tiene un teléfono en el WhatsApp central y la libera.

Hay un único número de Bynoesis, así que cada teléfono que escribe solo puede
ser una cosa: el móvil del titular de un negocio o el de una persona del equipo.
Cuando `BYNOESIS <código>` responde que el teléfono no es válido, casi siempre es
que ese número ya tiene la otra identidad. Este script dice cuál y dónde está.

Uso:

    python scripts/whatsapp_identidad.py 600111222
    python scripts/whatsapp_identidad.py +34 600 111 222 --liberar

Sin `--liberar` solo lee. Con `--liberar` quita el teléfono de las fichas de
equipo y desconecta el canal de los negocios que lo tuvieran, dejando el número
libre para volver a vincularlo. Usa la base de datos del entorno: `DATABASE_URL`
en Railway, el SQLite local si no está. Si hay un `.env` en la raíz, lo carga.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))


def _cargar_env() -> None:
    """Carga el .env de la raíz sin depender de python-dotenv."""
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("telefono", nargs="+", help="Teléfono en cualquier formato.")
    parser.add_argument(
        "--liberar", action="store_true",
        help="Deshace la vinculación para que el número quede libre.",
    )
    args = parser.parse_args()

    _cargar_env()
    from noesis import config, db

    norm = db.normalize_phone("".join(args.telefono))
    if len(norm) != 9:
        print(f"[FALLO] «{' '.join(args.telefono)}» no deja un teléfono de 9 dígitos.")
        return 1

    origen = "Postgres (DATABASE_URL)" if config.DATABASE_URL else str(config.DB_PATH)
    print(f"Base de datos: {origen}")
    print(f"Teléfono normalizado: {norm}\n")

    identidad = db.whatsapp_identity_rows(norm)
    negocios = identidad["businesses"]
    trabajadores = identidad["workers"]

    if not negocios and not trabajadores:
        print("[OK] El número está libre: puede vincularse como titular.")
        return 0

    for negocio in negocios:
        print(
            f"[TITULAR] Negocio {negocio['id']} · {negocio['name']} · "
            f"canal {negocio['whatsapp_status']}"
        )
    for trabajador in trabajadores:
        estado = "activo" if trabajador["active"] else "de baja"
        print(
            f"[EQUIPO] Trabajador {trabajador['id']} · {trabajador['name']} · "
            f"negocio {trabajador['business_id']} · {estado}"
        )

    if not args.liberar:
        print(
            "\nEjecuta el mismo comando con --liberar para deshacerlo, o hazlo "
            "desde la web: Equipo para el teléfono de una ficha, Ajustes para "
            "desconectar el canal de un negocio."
        )
        return 0

    db.free_whatsapp_phone(norm)
    for trabajador in trabajadores:
        print(f"[HECHO] Teléfono quitado de la ficha {trabajador['id']}.")
    for negocio in negocios:
        print(f"[HECHO] Canal desconectado del negocio {negocio['id']}.")
    print("\nEl número queda libre. Genera un código en Ajustes y vuelve a enviarlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
