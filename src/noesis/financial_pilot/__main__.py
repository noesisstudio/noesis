"""Operator tooling local: JSON por stdout, sin leer archivos de evidencia ni DB."""

import argparse
from datetime import datetime, timezone

from noesis.financial_activation.contracts import Capability, Profile, digest
from .contracts import PreparationContext
from .report import prepare_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="G-PREP documental, sin acceso real ni activación.")
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--business-id", type=int)
    parser.add_argument("--capability", action="append", choices=[c.value for c in Capability])
    parser.add_argument("--fiscal-required", choices=("unknown", "yes", "no"), default="unknown")
    args = parser.parse_args(argv)
    fiscal = {"unknown": None, "yes": True, "no": False}[args.fiscal_required]
    context = PreparationContext(args.code_sha, digest({"real_access": "not_authorized"}),
                                 args.business_id, Profile(tuple(args.capability)) if args.capability else None,
                                 fiscal)
    report = prepare_report(context, now=datetime.now(timezone.utc))
    print(report.canonical_content)
    # Exit code no significa permiso. Una preparación bloqueada es resultado correcto.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
