"""Proceso independiente para las carreras de emisión/cobro de pruebas."""

import json
import sys

from noesis import db


def main():
    arguments = json.loads(sys.argv[1])
    print("READY", flush=True)
    sys.stdin.readline()
    try:
        if arguments["mode"] == "issue":
            value = db.issue_invoice(arguments["invoice_id"], arguments["business_id"])
            result = {"invoice_id": value["id"], "number": value["number"]}
        else:
            value = db.add_invoice_payment(
                arguments["invoice_id"], "100", business_id=arguments["business_id"]
            )
            result = {"payment_id": value["id"]}
    except ValueError:
        result = {"conflict": True}
    finally:
        db.close_pool()
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
