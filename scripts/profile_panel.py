"""Mide qué cuesta pintar cada pantalla del panel del negocio.

Monta una base temporal con datos de tamaño realista, pide cada página como la
pediría el navegador y anota tres cosas por pantalla: cuánto tarda el servidor,
cuántas consultas SQL hace y cuánto HTML devuelve.

Sirve para responder a «el panel va lento» con números en vez de con opiniones,
y para distinguir los tres motivos posibles: demasiadas consultas (N+1), una
consulta lenta, o demasiado HTML para el navegador.

Uso:

    python scripts/profile_panel.py
    python scripts/profile_panel.py --clientes 200 --facturas 400
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

PAGINAS = (
    "resumen", "agenda", "clientes", "facturas", "gastos",
    "documentos", "proyectos", "equipo", "impuestos", "ajustes",
)


CORREO = "perfilado@example.com"
CLAVE = "password-de-perfilado-123"  # pragma: allowlist secret


def _sembrar(db, auth, clientes: int, facturas: int) -> int:
    """Crea un negocio con datos suficientes para que se note el coste."""
    negocio = db.create_business("Perfilado", CORREO)
    bid = negocio["id"]
    db.create_user(CORREO, auth.hash_password(CLAVE), bid)
    db.update_fiscal(bid, nif="12345678Z", address="Calle Principal 1")
    ids = []
    for i in range(clientes):
        ids.append(db.add_client(
            f"Cliente {i:03d}", nif="87654321X",
            address=f"Calle {i} 1", business_id=bid,
        )["id"])
    for i in range(facturas):
        cliente = ids[i % len(ids)]
        factura = db.add_invoice(
            cliente, f"Trabajo {i}", 100.0 + i, vat_rate=21, business_id=bid,
        )
        if i % 3 == 0:
            db.issue_invoice(factura["id"], bid)
    for i in range(facturas // 2):
        db.add_expense(f"Gasto {i}", 20.0 + i, vat_rate=21, business_id=bid)
    return bid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Perfila el panel del negocio.")
    parser.add_argument("--clientes", type=int, default=60)
    parser.add_argument("--facturas", type=int, default=150)
    parser.add_argument("--repeticiones", type=int, default=3)
    args = parser.parse_args(argv)

    from noesis import config

    carpeta = tempfile.TemporaryDirectory()
    config.DATABASE_URL = ""
    config.DB_PATH = Path(carpeta.name) / "perfil.db"
    config.BACKUP_DIR = Path(carpeta.name) / "backups"
    config.DOCS_PATH = Path(carpeta.name) / "uploads"

    from noesis import db
    from noesis.web import auth

    db.init_db()
    print(f"Sembrando {args.clientes} clientes y {args.facturas} facturas...")
    bid = _sembrar(db, auth, args.clientes, args.facturas)

    # Contamos consultas envolviendo la fábrica de conexiones de db.
    contador = {"n": 0}
    original_get_conn = db.get_conn

    class _ConexionContada:
        def __init__(self, gestor):
            self._gestor = gestor

        def __enter__(self):
            conexion = self._gestor.__enter__()
            ejecutar = conexion.execute

            def _execute(*a, **k):
                contador["n"] += 1
                return ejecutar(*a, **k)

            conexion.execute = _execute
            return conexion

        def __exit__(self, *a):
            return self._gestor.__exit__(*a)

    db.get_conn = lambda *a, **k: _ConexionContada(original_get_conn(*a, **k))

    from starlette.testclient import TestClient

    from noesis.web.server import app

    cliente = TestClient(app)
    # Sesión directa: perfilamos el coste de pintar, no el del login.
    cliente.cookies.clear()
    with cliente as http:
        entrada = http.post(
            "/login", data={"email": CORREO, "password": CLAVE}, follow_redirects=False
        )
        if entrada.status_code not in (302, 303):
            print(f"No se pudo entrar (HTTP {entrada.status_code}). Se aborta.")
            return 1

        print(f"\n{'pantalla':<14}{'ms':>8}{'consultas':>11}{'KB HTML':>10}  estado")
        print("-" * 56)
        filas = []
        for pagina in PAGINAS:
            mejor, consultas, tam, estado = None, 0, 0, 0
            for _ in range(args.repeticiones):
                contador["n"] = 0
                inicio = time.perf_counter()
                respuesta = http.get(f"/b/{bid}/{pagina}", follow_redirects=False)
                transcurrido = (time.perf_counter() - inicio) * 1000
                if mejor is None or transcurrido < mejor:
                    mejor, consultas = transcurrido, contador["n"]
                    tam, estado = len(respuesta.content), respuesta.status_code
            filas.append((pagina, mejor, consultas, tam / 1024, estado))
            print(f"{pagina:<14}{mejor:>8.0f}{consultas:>11}{tam / 1024:>10.1f}  {estado}")

        print("-" * 56)
        lentas = sorted(filas, key=lambda f: -f[1])[:3]
        print("Las tres más caras:")
        for nombre, ms, consultas, kb, _ in lentas:
            print(f"  {nombre}: {ms:.0f} ms, {consultas} consultas, {kb:.1f} KB")
    carpeta.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
