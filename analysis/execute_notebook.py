"""Ejecutor mínimo y reproducible para notebooks de análisis sin Jupyter.

Ejecuta las celdas de código en orden, captura stdout y escribe los resultados en
el propio .ipynb. No intenta reemplazar un kernel interactivo.
"""

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import traceback


def main(notebook_path: str) -> None:
    path = Path(notebook_path)
    notebook = json.loads(path.read_text(encoding="utf-8"))
    namespace: dict = {}

    def display(value) -> None:
        if hasattr(value, "to_string"):
            print(value.to_string())
        else:
            print(value)

    namespace["display"] = display
    execution_count = 0
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        execution_count += 1
        buffer = io.StringIO()
        cell["execution_count"] = execution_count
        cell["outputs"] = []
        try:
            with redirect_stdout(buffer):
                exec("".join(cell.get("source", [])), namespace)
        except Exception as exc:
            output = buffer.getvalue()
            if output:
                cell["outputs"].append(
                    {"name": "stdout", "output_type": "stream", "text": [output]}
                )
            cell["outputs"].append(
                {
                    "ename": type(exc).__name__,
                    "evalue": str(exc),
                    "output_type": "error",
                    "traceback": traceback.format_exc().splitlines(),
                }
            )
            path.write_text(
                json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            raise
        output = buffer.getvalue()
        if output:
            cell["outputs"].append(
                {"name": "stdout", "output_type": "stream", "text": [output]}
            )
    path.write_text(
        json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: execute_notebook.py RUTA.ipynb")
    main(sys.argv[1])
