"""Carrera de procesos reales: únicamente PostgreSQL local descartable."""

import json
import sys
from urllib.parse import urlsplit

from noesis import config, db
from noesis.bank_capture.service import BankCapture
from noesis.financial_operations.contracts import Principal, StateError
from noesis.payment_capture.service import PaymentCapture


def main():
    url = urlsplit(config.DATABASE_URL)
    if url.hostname not in {'localhost','127.0.0.1','::1'} or url.path != '/noesis_ci' or config.IS_PRODUCTION:
        raise RuntimeError('Solo PostgreSQL local descartable.')
    args = json.loads(sys.argv[1])
    service = (BankCapture if args['mode'] == 'bank' else PaymentCapture)(args['business_id'])
    principal = Principal(args['user_id'],0)
    print('READY',flush=True)
    if sys.stdin.readline().strip() != 'go':
        raise RuntimeError('Barrera de procesos requerida.')
    try:
        op = service.execute(principal,args['operation_uuid'])
        print(json.dumps({'operation_uuid':op.operation_uuid,'result':dict(op.result)}),flush=True)
    except StateError as exc:
        print(json.dumps({'conflict':True,'reason':str(exc)}),flush=True)
    finally:
        db.close_pool()


if __name__ == '__main__':
    main()
