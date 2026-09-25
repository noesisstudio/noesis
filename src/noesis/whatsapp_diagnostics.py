"""Diagnóstico operativo y recuperación explícita de entradas no ejecutadas."""
import argparse
import json

from . import db


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", required=True, type=int)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--recover", type=int, metavar="INCIDENCIA")
    parser.add_argument("--operator-id", type=int)
    args = parser.parse_args()
    if args.business_id <= 0:
        parser.error("El identificador de negocio debe ser positivo.")
    if args.recover is not None:
        if not args.operator_id or args.operator_id <= 0 or args.recover <= 0:
            parser.error("Recuperar exige incidencia positiva y --operator-id administrador.")
        db.recover_whatsapp_inbound(args.business_id, args.recover, operator_id=args.operator_id)
    report = db.whatsapp_ingress_diagnostics(args.business_id, limit=args.limit)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["counts"].get("review", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
