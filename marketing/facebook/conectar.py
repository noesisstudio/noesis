"""Convierte un token corto de Meta en el token de página que no caduca.

Es el paso engorroso de conectar la automatización y solo se hace una vez (o
cuando haya que renovarlo). Se ejecuta desde este ordenador, nunca en GitHub: el
token que imprime es un secreto y no debe acabar en el repositorio.

Uso:
    python marketing/facebook/conectar.py --app-id 123 --app-secret ... --token-corto ...

Los tres valores salen de developers.facebook.com, como explica el README.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import nucleo


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Obtiene el token de página de Facebook.")
    parser.add_argument("--app-id", required=True, help="identificador de la app de Meta.")
    parser.add_argument("--app-secret", required=True, help="clave secreta de la app de Meta.")
    parser.add_argument(
        "--token-corto",
        required=True,
        help="token de usuario del Explorador de la API Graph, con los permisos de página.",
    )
    parser.add_argument(
        "--version",
        default=nucleo.VERSION_GRAPH_POR_DEFECTO,
        help="versión de la Graph API (por defecto la del proyecto).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    # Credenciales de trabajo: aquí el «acceso» todavía es el token corto.
    credenciales = nucleo.Credenciales(
        pagina="",
        acceso=args.token_corto,
        version=args.version,
        app_id=args.app_id,
        app_secreto=args.app_secret,
    )

    try:
        largo = nucleo.graph_get(
            credenciales,
            "oauth/access_token",
            {
                "grant_type": "fb_exchange_token",
                "client_id": args.app_id,
                "client_secret": args.app_secret,
                "fb_exchange_token": args.token_corto,
            },
        )
    except nucleo.ErrorGraph as exc:
        print(f"ERROR · no se ha podido alargar el token: {exc}", file=sys.stderr)
        return 1

    token_usuario = str(largo.get("access_token", ""))
    if not token_usuario:
        print("ERROR · Meta no ha devuelto ningún token largo.", file=sys.stderr)
        return 1

    credenciales_largas = nucleo.Credenciales(
        pagina="", acceso=token_usuario, version=args.version,
        app_id=args.app_id, app_secreto=args.app_secret,
    )
    try:
        cuentas = nucleo.graph_get(credenciales_largas, "me/accounts", {"fields": "id,name,access_token"})
    except nucleo.ErrorGraph as exc:
        print(f"ERROR · no se han podido listar las páginas: {exc}", file=sys.stderr)
        return 1

    paginas = [pagina for pagina in cuentas.get("data", []) if isinstance(pagina, dict)]
    if not paginas:
        print(
            "ERROR · este usuario no administra ninguna página. Revisa que el token "
            "corto tenga los permisos pages_show_list, pages_manage_posts y "
            "pages_read_engagement.",
            file=sys.stderr,
        )
        return 1

    print("Páginas encontradas:\n")
    for pagina in paginas:
        token_pagina = str(pagina.get("access_token", ""))
        print(f"- {pagina.get('name', '(sin nombre)')}")
        print(f"  FACEBOOK_PAGE_ID    = {pagina.get('id', '')}")
        print(f"  FACEBOOK_PAGE_TOKEN = {token_pagina}")
        if token_pagina:
            try:
                revision = nucleo.graph_get(
                    credenciales_largas,
                    "debug_token",
                    {
                        "input_token": token_pagina,
                        "access_token": f"{args.app_id}|{args.app_secret}",
                    },
                )
                datos = revision.get("data", {})
                marca = int(datos.get("expires_at", 0) or 0)
                if marca:
                    caduca = datetime.fromtimestamp(marca, tz=timezone.utc).date().isoformat()
                    print(f"  Caduca              = {caduca} (habrá que renovarlo)")
                else:
                    print("  Caduca              = no caduca mientras no cambies la contraseña ni revoques permisos")
                print(f"  Permisos            = {', '.join(str(p) for p in datos.get('scopes', []))}")
            except nucleo.ErrorGraph as exc:
                print(f"  (no se ha podido comprobar la caducidad: {exc})")
        print()

    print(
        "Guarda esos dos valores como secretos del repositorio en GitHub:\n"
        "Settings → Secrets and variables → Actions → New repository secret.\n"
        "No los pegues en ningún fichero del proyecto."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
