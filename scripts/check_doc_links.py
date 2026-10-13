"""Enlaces Markdown internos del delta: auditoría local determinista, sin red.

Conserva el alcance del audit de 550 enlaces: links inline (también imágenes),
sin disponibilidad de URLs externas ni validación de anchors. Los destinos con
fragmento se comprueban sin él; se rechazan rutas que salgan del repositorio.
"""

import argparse
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
INLINE_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
EXTERNAL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def check_links(root: Path, documents: dict[str, str]) -> tuple[int, list[tuple[str, str]]]:
    root = root.resolve()
    checked, broken = 0, []
    for name, body in sorted(documents.items()):
        for reference in INLINE_LINK.findall(body):
            reference = reference.strip().split(" ")[0].strip("<>")
            if EXTERNAL_SCHEME.match(reference) or reference.startswith("#"):
                continue
            target = unquote(reference.split("#", 1)[0])
            if not target:
                continue
            checked += 1
            if (target.startswith(("/", "\\")) or "\\" in target
                    or any(ord(char) < 32 for char in target)):
                broken.append((name, reference))
                continue
            resolved = (root / name).parent.joinpath(target).resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                broken.append((name, reference))
    return checked, broken


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--working-tree", action="store_true")
    args = parser.parse_args(argv)
    heads = [] if args.working_tree else [args.head_ref]
    names = git("diff", "--name-only", "-z", "--diff-filter=ACMR", args.base_ref, *heads)
    documents = {}
    for name in names.decode("utf-8").split("\0"):
        if not name.endswith(".md"):
            continue
        if args.working_tree:
            path = (ROOT / name).resolve()
            if not path.is_relative_to(ROOT):
                raise SystemExit("Documento fuera del repositorio")
            documents[name] = path.read_text(encoding="utf-8-sig")
        else:
            documents[name] = git("show", f"{args.head_ref}:{name}").decode("utf-8-sig")
    count, broken = check_links(ROOT, documents)
    print(f"Enlaces internos: {count} comprobados, {len(broken)} rotos.")
    for name, reference in broken:
        print(f"Enlace local inválido: {name} -> {reference}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
