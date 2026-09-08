"""Publica en la página de Facebook de Noesis lo que toque hoy.

Se ejecuta todos los días desde GitHub Actions, pero solo publica cuando el día
cae en la cadencia del calendario (cada 3 días desde el ancla). No guarda estado
en el repositorio: la verdad es lo que hay publicado en la página, y se consulta
antes de escribir nada.

Uso habitual:
    python marketing/facebook/publicar.py                # lo que toque hoy
    python marketing/facebook/publicar.py --simulacro    # enseña el texto, no publica
    python marketing/facebook/publicar.py --forzar       # publica aunque hoy no toque
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone

import nucleo


def _dia(valor: str) -> date:
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:  # pragma: no cover - lo valida argparse
        raise argparse.ArgumentTypeError(f"fecha inválida: {valor}") from exc


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publicador de Facebook de Noesis.")
    parser.add_argument("--fecha", type=_dia, default=None, help="simula otro día (YYYY-MM-DD).")
    parser.add_argument("--simulacro", action="store_true", help="enseña qué haría, sin publicar.")
    parser.add_argument("--forzar", action="store_true", help="publica aunque hoy no toque.")
    parser.add_argument(
        "--sin-recuperacion",
        action="store_true",
        help="no recupera una publicación que se saltó por un fallo del día anterior.",
    )
    parser.add_argument(
        "--verificar",
        action="store_true",
        help="solo comprueba la conexión con la página y sale.",
    )
    return parser.parse_args(argv)


def _pendiente_por_recuperar(
    dia: date,
    calendario: nucleo.Calendario,
    publicadas: list[nucleo.PublicacionPagina],
) -> tuple[date, nucleo.Publicacion] | None:
    """Turno reciente que se quedó sin publicar por un fallo de la automatización.

    Solo se recupera si la página lleva callada desde entonces. Si hay cualquier
    publicación posterior —automática o escrita a mano— se deja estar: es mejor
    saltarse una pieza que repetir una.
    """

    ultimo = nucleo.turno_anterior(dia, calendario)
    if ultimo is None or ultimo == dia:
        return None
    if (dia - ultimo).days > calendario.cadencia_dias:
        return None
    prevista = nucleo.publicacion_de(ultimo, calendario)
    if prevista is None:
        return None
    corte = datetime(ultimo.year, ultimo.month, ultimo.day, tzinfo=timezone.utc)
    if any(publicada.creada >= corte for publicada in publicadas):
        return None
    return ultimo, prevista[0]


def _publicar(credenciales: nucleo.Credenciales, publicacion: nucleo.Publicacion) -> str:
    datos = {"message": publicacion.texto}
    if publicacion.enlace:
        datos["link"] = publicacion.enlace
    respuesta = nucleo.graph_post(credenciales, f"{credenciales.pagina}/feed", datos)
    return str(respuesta.get("id", ""))


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    calendario = nucleo.cargar_calendario()
    dia = args.fecha or nucleo.hoy()

    try:
        credenciales = nucleo.leer_credenciales()
    except nucleo.ErrorConfiguracion as exc:
        if args.simulacro:
            credenciales = None
        elif args.forzar:
            print(f"ERROR · {exc}", file=sys.stderr)
            return 1
        else:
            # En la ejecución diaria automática no interesa un fallo rojo cada día
            # mientras la página aún no está conectada: se avisa y se para.
            print(f"PAUSA · {exc}")
            nucleo.resumen_github(["### Facebook", f"⏸ Automatización en pausa: {exc}"])
            return 0

    if args.verificar:
        if credenciales is None:
            print("PAUSA · faltan credenciales, no hay nada que verificar.")
            return 0
        estado = nucleo.diagnostico_conexion(credenciales)
        print(f"Página: {estado.nombre_pagina or '(sin nombre)'} · @{estado.usuario or '?'}")
        print(f"Lectura de publicaciones: {'sí' if estado.lee_publicaciones else 'no'}")
        dias = estado.dias_de_token
        print(f"Token: {'caduca en ' + str(dias) + ' días' if dias is not None else 'sin caducidad conocida'}")
        for aviso in estado.avisos:
            print(f"AVISO · {aviso}")
        return 1 if any("no responde" in aviso for aviso in estado.avisos) else 0

    prevista = nucleo.publicacion_de(dia, calendario)
    if prevista is None and args.forzar:
        referencia = nucleo.turno_anterior(dia, calendario) or calendario.ancla
        prevista = nucleo.publicacion_de(referencia, calendario)

    publicacion = prevista[0] if prevista else None
    vuelta = prevista[1] if prevista else 0
    dia_previsto = dia

    if credenciales is None:
        # Simulacro sin credenciales: enseñar el plan y salir.
        if publicacion is None:
            print(f"{dia.isoformat()} · hoy no toca publicar.")
            return 0
        print(f"{dia.isoformat()} · SIMULACRO (sin credenciales) · {publicacion.identificador}")
        print(f"--- {publicacion.titulo} [{publicacion.pilar}] · vuelta {vuelta + 1} ---")
        print(publicacion.texto)
        if publicacion.enlace:
            print(f"[enlace] {publicacion.enlace}")
        return 0

    try:
        publicadas = nucleo.publicaciones_recientes(credenciales)
        lectura = True
    except nucleo.ErrorGraph as exc:
        publicadas = []
        lectura = False
        print(f"AVISO · no se han podido leer las publicaciones de la página: {exc}", file=sys.stderr)

    if publicacion is None:
        if args.sin_recuperacion or not lectura:
            print(f"{dia.isoformat()} · hoy no toca publicar.")
            return 0
        rescate = _pendiente_por_recuperar(dia, calendario, publicadas)
        if rescate is None:
            print(f"{dia.isoformat()} · hoy no toca publicar.")
            return 0
        dia_previsto, publicacion = rescate
        print(
            f"RECUPERACIÓN · la publicación del {dia_previsto.isoformat()} no llegó a "
            "la página; se publica ahora."
        )

    repetida = nucleo.ya_publicada(publicacion, publicadas) if lectura else None
    if repetida is not None and not args.forzar:
        print(
            f"{dia.isoformat()} · {publicacion.identificador} ya está en la página "
            f"({repetida.creada.date().isoformat()}). No se repite."
        )
        return 0

    if args.simulacro:
        print(f"{dia.isoformat()} · SIMULACRO · {publicacion.identificador} · {publicacion.titulo}")
        print(publicacion.texto)
        if publicacion.enlace:
            print(f"[enlace] {publicacion.enlace}")
        return 0

    try:
        identificador = _publicar(credenciales, publicacion)
    except nucleo.ErrorGraph as exc:
        print(f"ERROR · no se ha podido publicar {publicacion.identificador}: {exc}", file=sys.stderr)
        nucleo.resumen_github(
            ["### Facebook", f"❌ Falló la publicación `{publicacion.identificador}`: {exc}"]
        )
        return 1

    restantes = nucleo.restantes_sin_repetir(dia_previsto + timedelta(days=1), calendario)
    print(f"PUBLICADO · {publicacion.identificador} · {publicacion.titulo} · id {identificador}")
    nucleo.resumen_github(
        [
            "### Facebook",
            f"✅ Publicado **{publicacion.titulo}** (`{publicacion.identificador}`, {publicacion.pilar}).",
            "",
            f"> {publicacion.primera_linea}",
            "",
            f"Quedan {restantes} publicaciones nuevas antes de que el calendario dé la vuelta.",
        ]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
