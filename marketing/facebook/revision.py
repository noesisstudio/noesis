"""Informe del domingo: qué se publicó, qué viene y qué hay que mirar.

Compara lo que el calendario decía con lo que hay de verdad en la página, revisa
la salud del token y deja el informe listo para leerlo en un minuto. Se ejecuta
desde GitHub Actions cada domingo y abre una incidencia con el resultado.

Uso:
    python marketing/facebook/revision.py               # informe por pantalla
    python marketing/facebook/revision.py --salida x.md # además lo guarda
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone

import nucleo

DIAS_REVISADOS = 7
PROXIMAS_MOSTRADAS = 4
# Con menos margen que esto toca escribir piezas nuevas antes de que el
# calendario empiece a repetirse.
MINIMO_DEPOSITO = 8

DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _fecha_larga(dia: date) -> str:
    return f"{DIAS_SEMANA[dia.weekday()]} {dia.day:02d}/{dia.month:02d}"


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Revisión semanal de Facebook.")
    parser.add_argument("--fecha", default="", help="simula otro domingo (YYYY-MM-DD).")
    parser.add_argument("--salida", default="", help="guarda el informe en un fichero.")
    return parser.parse_args(argv)


def _publica_para(mensaje: str, publicadas: list[nucleo.PublicacionPagina]) -> nucleo.PublicacionPagina | None:
    objetivo = nucleo.firma(mensaje)
    for candidata in publicadas:
        if candidata.mensaje and nucleo.firma(candidata.mensaje) == objetivo:
            return candidata
    return None


def construir_informe(dia: date, calendario: nucleo.Calendario) -> tuple[list[str], list[str]]:
    """Devuelve (líneas del informe, avisos)."""

    avisos: list[str] = []
    lineas: list[str] = []
    desde = dia - timedelta(days=DIAS_REVISADOS - 1)

    try:
        credenciales = nucleo.leer_credenciales()
    except nucleo.ErrorConfiguracion as exc:
        avisos.append(str(exc))
        credenciales = None

    lineas.append(f"## Semana del {desde.day:02d}/{desde.month:02d} al {dia.day:02d}/{dia.month:02d}")
    lineas.append("")

    previstas = nucleo.turnos_entre(desde, dia, calendario)
    publicadas: list[nucleo.PublicacionPagina] = []
    if credenciales is not None:
        try:
            publicadas = nucleo.publicaciones_recientes(credenciales, limite=25)
        except nucleo.ErrorGraph as exc:
            avisos.append(f"No se ha podido leer la página: {exc}")

    lineas.append("### 1. Lo que tenía que salir esta semana")
    lineas.append("")
    if not previstas:
        lineas.append("No había ninguna publicación programada en estos siete días.")
    for fecha, publicacion, _ in previstas:
        encontrada = _publica_para(publicacion.texto, publicadas)
        if encontrada is not None:
            enlace = f" · [ver en Facebook](https://www.facebook.com{encontrada.enlace})" if encontrada.enlace.startswith("/") else (f" · [ver en Facebook]({encontrada.enlace})" if encontrada.enlace else "")
            lineas.append(
                f"- ✅ **{_fecha_larga(fecha)}** · {publicacion.titulo} "
                f"(`{publicacion.identificador}`){enlace}"
            )
        elif credenciales is None or not publicadas:
            lineas.append(
                f"- ❔ **{_fecha_larga(fecha)}** · {publicacion.titulo} "
                f"(`{publicacion.identificador}`) · no se ha podido comprobar"
            )
        elif fecha == dia:
            lineas.append(
                f"- ⏳ **{_fecha_larga(fecha)}** · {publicacion.titulo} "
                f"(`{publicacion.identificador}`) · sale hoy más tarde"
            )
        else:
            lineas.append(
                f"- ❌ **{_fecha_larga(fecha)}** · {publicacion.titulo} "
                f"(`{publicacion.identificador}`) · no aparece en la página"
            )
            avisos.append(
                f"Falta la publicación {publicacion.identificador} del {fecha.isoformat()}."
            )
    lineas.append("")

    programadas = {nucleo.firma(pub.texto) for _, pub, _ in previstas}
    corte = datetime(desde.year, desde.month, desde.day, tzinfo=timezone.utc)
    manuales = [
        publicada
        for publicada in publicadas
        if publicada.creada >= corte and nucleo.firma(publicada.mensaje) not in programadas
    ]
    if manuales:
        lineas.append("### 2. Otras publicaciones de la página")
        lineas.append("")
        for publicada in manuales:
            primera = (publicada.mensaje.strip().splitlines() or ["(sin texto)"])[0]
            lineas.append(f"- {publicada.creada.date().isoformat()} · {primera[:110]}")
        lineas.append("")

    lineas.append(f"### {3 if manuales else 2}. Lo que saldrá si no tocas nada")
    lineas.append("")
    for fecha, publicacion, vuelta in nucleo.proximos_turnos(dia + timedelta(days=1), PROXIMAS_MOSTRADAS, calendario):
        repetida = " · ⚠️ repetida" if vuelta else ""
        lineas.append(f"- **{_fecha_larga(fecha)}** · {publicacion.titulo} (`{publicacion.identificador}`){repetida}")
        lineas.append(f"  > {publicacion.primera_linea}")
        if publicacion.enlace:
            lineas.append(f"  > Enlace: {publicacion.enlace}")
    lineas.append("")
    lineas.append(
        "Para cambiar o quitar cualquiera de estas piezas, edita "
        "`marketing/facebook/calendario.json` antes de su fecha."
    )
    lineas.append("")

    lineas.append(f"### {4 if manuales else 3}. Conexión con Facebook")
    lineas.append("")
    if credenciales is None:
        lineas.append("- ⏸ La automatización está en pausa: faltan los secretos de la página.")
        lineas.append("- Instrucciones en `marketing/facebook/README.md`, apartado «Conectar la página».")
    else:
        estado = nucleo.diagnostico_conexion(credenciales)
        lineas.append(f"- Página: **{estado.nombre_pagina or '(sin nombre)'}**"
                      + (f" (@{estado.usuario})" if estado.usuario else ""))
        lineas.append(f"- Lectura de publicaciones: {'✅ sí' if estado.lee_publicaciones else '❌ no'}")
        dias_token = estado.dias_de_token
        if dias_token is None:
            lineas.append("- Token: sin fecha de caducidad conocida.")
        else:
            marca = "✅" if dias_token > nucleo.DIAS_AVISO_TOKEN else "⚠️"
            lineas.append(f"- Token: {marca} caduca en {dias_token} días.")
        for aviso in estado.avisos:
            avisos.append(aviso)
    lineas.append("")

    restantes = nucleo.restantes_sin_repetir(dia, calendario)
    lineas.append(f"### {5 if manuales else 4}. Depósito editorial")
    lineas.append("")
    lineas.append(
        f"- Quedan **{restantes}** publicaciones nuevas de las {len(calendario)} del calendario "
        f"(unas {restantes * calendario.cadencia_dias // 7} semanas)."
    )
    if restantes <= MINIMO_DEPOSITO:
        avisos.append(
            f"Quedan solo {restantes} publicaciones nuevas: añade piezas al calendario "
            "o el contenido empezará a repetirse."
        )
    lineas.append("")

    lineas.append(f"### {6 if manuales else 5}. Qué hacer si algo va mal")
    lineas.append("")
    lineas.append(
        "1. Falta una publicación: entra en Actions → «Facebook · publicar» → "
        "«Run workflow» con `forzar` marcado."
    )
    lineas.append(
        "2. El token caduca o Meta rechaza la llamada: renueva el token de página "
        "y actualiza el secreto `FACEBOOK_PAGE_TOKEN` (README, apartado «Renovar el token»)."
    )
    lineas.append(
        "3. Un texto no te convence: edita `marketing/facebook/calendario.json`; "
        "el cambio vale desde el commit, sin desplegar nada."
    )
    return lineas, avisos


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    calendario = nucleo.cargar_calendario()
    dia = date.fromisoformat(args.fecha) if args.fecha else nucleo.hoy()

    lineas, avisos = construir_informe(dia, calendario)
    nucleo.cargar_env_local()
    en_pausa = bool(nucleo.credenciales_faltantes())

    if en_pausa:
        cabecera = [
            f"# Revisión de Facebook · {dia.isoformat()}",
            "",
            "**La automatización todavía no está conectada.**",
            "",
            "Faltan los secretos de la página en el repositorio. Hasta que estén, no se "
            "publica nada. Los pasos están en `marketing/facebook/README.md`, apartado "
            "«Conectar la página».",
            "",
        ]
        titulo = f"Revisión Facebook · {dia.isoformat()} · falta conectar la página"
    elif avisos:
        cabecera = [
            f"# Revisión de Facebook · {dia.isoformat()}",
            "",
            f"**Requiere tu atención: {len(avisos)} aviso(s).**",
            "",
            *[f"- ⚠️ {aviso}" for aviso in avisos],
            "",
        ]
        titulo = f"Revisión Facebook · {dia.isoformat()} · {len(avisos)} aviso(s)"
    else:
        cabecera = [
            f"# Revisión de Facebook · {dia.isoformat()}",
            "",
            "**Todo correcto. No tienes que hacer nada.**",
            "",
        ]
        titulo = f"Revisión Facebook · {dia.isoformat()} · todo correcto"

    informe = "\n".join(cabecera + lineas) + "\n"
    print(informe)

    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as fichero:
            fichero.write(informe)

    salida_actions = os.environ.get("GITHUB_OUTPUT", "").strip()
    if salida_actions:
        try:
            with open(salida_actions, "a", encoding="utf-8") as fichero:
                fichero.write(f"titulo={titulo}\n")
                fichero.write(f"avisos={len(avisos)}\n")
        except OSError:
            pass
    nucleo.resumen_github([informe])
    return 0


if __name__ == "__main__":
    sys.exit(main())
