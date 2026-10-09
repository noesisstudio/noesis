"""Proceso D descartable. Ninguna referencia a QA/restauraciones/proveedores."""

import json
import os
import sys
from urllib.parse import urlsplit
from unittest.mock import patch

from noesis import config, db
from noesis.financial_operations.contracts import Principal
from noesis.financial_activation.handoff import FinancialActivation


def main():
    url = urlsplit(config.DATABASE_URL)
    if url.hostname not in ('127.0.0.1', 'localhost', '::1') or url.path != '/noesis_ci' or config.IS_PRODUCTION:
        raise RuntimeError('Worker únicamente PostgreSQL sintético local.')
    args = json.loads(sys.argv[1])
    from noesis.financial_history.service import FLAGS
    from noesis.financial_activation.configuration_snapshot import PRODUCER_FIELDS
    values = args['fixture_configuration']
    if set(values) != set(PRODUCER_FIELDS):
        raise ValueError('Configuración sintética cerrada requerida.')
    settings = patch.multiple(config, **values, **dict.fromkeys(FLAGS, False))
    settings.start()
    api = FinancialActivation(args['business_id'], code_version='fixture')
    def checkpoint(name):
        if name == args.get('crash_point'):
            os._exit(17)
    api.checkpoint = checkpoint
    print('READY', flush=True)
    if sys.stdin.readline().strip() != 'go':
        raise RuntimeError('Inicio explícito requerido.')
    try:
        result = api.advance(Principal(args['user_id'], 0), args['request_uuid'], args['stage'])
        print(json.dumps(dict(receipt=result['receipt_uuid'], generation=result['activation_generation'])), flush=True)
    except (ValueError, PermissionError) as exc:
        print(json.dumps(dict(denied=type(exc).__name__)), flush=True)
    finally:
        db.close_pool()


if __name__ == '__main__':
    main()
