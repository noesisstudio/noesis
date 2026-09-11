"""Comprueba que la documentación de cumplimiento está completa y al día.

No verifica cumplimiento real: verifica higiene documental. Que un documento
exista y esté revisado no significa que el control descrito funcione; eso lo
demuestra el simulacro trimestral y la evidencia asociada.

Uso:
    python scripts/check_cumplimiento.py
    python scripts/check_cumplimiento.py --strict   # avisos también fallan
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "docs" / "05-legal-y-rgpd" / "cumplimiento"

# Documento -> meses máximos sin revisar. 0 = revisión continua, no caduca.
PLAZOS: dict[str, int] = {
    "README.md": 12,
    "Plan-Datos-Servidores-Copias.md": 3,
    "RAT-Registro-actividades.md": 6,
    "Politica-de-retencion.md": 6,
    "Subencargados-y-transferencias.md": 3,
    "Analisis-riesgos-y-EIPD.md": 6,
    "Procedimiento-brechas.md": 6,
    "Derechos-de-los-interesados.md": 6,
    "Continuidad-RPO-RTO.md": 3,
    "Registro-de-evidencias.md": 0,
}

PLANTILLAS = (
    "Notificacion-brecha-AEPD.md",
    "Respuesta-derechos.md",
    "Registro-simulacro-restauracion.md",
    "Alta-subencargado.md",
)

REVISION = re.compile(r"Última revisión:\s*(\d{4}-\d{2}-\d{2})")


def _meses_desde(momento: date, hoy: date) -> int:
    meses = (hoy.year - momento.year) * 12 + (hoy.month - momento.month)
    return meses - 1 if hoy.day < momento.day else meses


def revisar(hoy: date | None = None) -> tuple[list[str], list[str]]:
    """Devuelve (errores, avisos)."""
    hoy = hoy or date.today()
    errores: list[str] = []
    avisos: list[str] = []

    if not CARPETA.is_dir():
        return [f"Falta la carpeta {CARPETA.relative_to(RAIZ)}"], []

    for nombre, plazo in PLAZOS.items():
        ruta = CARPETA / nombre
        if not ruta.is_file():
            errores.append(f"Falta {ruta.relative_to(RAIZ)}")
            continue
        if nombre == "README.md":
            continue
        encontrado = REVISION.search(ruta.read_text(encoding="utf-8"))
        if not encontrado:
            errores.append(
                f"{nombre}: sin línea 'Última revisión: AAAA-MM-DD' en la cabecera"
            )
            continue
        if plazo == 0:
            continue
        revisado = date.fromisoformat(encontrado.group(1))
        if revisado > hoy:
            errores.append(f"{nombre}: la fecha de revisión {revisado} está en el futuro")
            continue
        antiguedad = _meses_desde(revisado, hoy)
        if antiguedad > plazo:
            errores.append(
                f"{nombre}: revisado hace {antiguedad} meses; el plazo es {plazo}"
            )
        elif antiguedad >= plazo:
            avisos.append(f"{nombre}: toca revisarlo este mes (plazo {plazo} meses)")

    for nombre in PLANTILLAS:
        ruta = CARPETA / "plantillas" / nombre
        if not ruta.is_file():
            errores.append(f"Falta {ruta.relative_to(RAIZ)}")

    pendientes = (CARPETA / "Registro-de-evidencias.md").read_text(encoding="utf-8")
    if "Pendiente del primer simulacro externo" in pendientes:
        avisos.append(
            "Registro-de-evidencias: aún no hay ningún simulacro de restauración "
            "externa. RPO y RTO siguen siendo estimaciones."
        )

    return errores, avisos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict", action="store_true", help="Los avisos también devuelven error."
    )
    args = parser.parse_args()

    errores, avisos = revisar()
    for aviso in avisos:
        print(f"AVISO: {aviso}")
    for error in errores:
        print(f"ERROR: {error}")

    if errores or (avisos and args.strict):
        print(f"\nRevisión de cumplimiento: {len(errores)} error(es), {len(avisos)} aviso(s).")
        return 1
    print(f"Documentación de cumplimiento completa y al día ({len(avisos)} aviso(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
