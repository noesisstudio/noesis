"""Proceso de prueba PostgreSQL: sólo fixture /noesis_ci y transporte fake."""

import json
import os
from pathlib import Path
import socket
import ssl
import sys
import time
from urllib.parse import urlsplit
from unittest.mock import patch

from noesis import config, db
from noesis.financial_operations.contracts import StateError, ConflictError
from noesis.financial_providers.dispatch import FinancialProviderDispatch
from noesis.financial_providers.preflight import FinancialIntegratedPreflight
from noesis.financial_operations.contracts import Principal


def main():
    parts = urlsplit(config.DATABASE_URL)
    if parts.hostname not in ('127.0.0.1','localhost') or parts.path != '/noesis_ci' or config.IS_PRODUCTION:
        raise RuntimeError('Worker exclusivamente PostgreSQL sintético loopback.')
    spec = json.loads(sys.argv[1])
    from noesis.web import whatsapp
    with patch.multiple(config, **spec['settings']), patch.multiple(whatsapp, _TOKEN='SYNTHETIC-META-TOKEN-MARKER-NOT-EXPORT', _PHONE_ID='synthetic-phone'), patch.object(ssl.SSLContext,'load_cert_chain',return_value=None), patch.object(socket.socket,'connect',side_effect=AssertionError('OUTBOUND_FORBIDDEN')):
        print('READY', flush=True)
        sys.stdin.readline()
        api = FinancialProviderDispatch(spec['business_id'])
        def checkpoint(point):
            if point == spec.get('crash'):
                os._exit(71)
        api.checkpoint = checkpoint
        def fake(attempt):
            # Evidencia de invocaciones fake fuera de Git, nunca provider real.
            with Path(spec['counter']).open('a', encoding='utf-8') as f:
                f.write(attempt['attempt_uuid']+'\n')
                f.flush()
                os.fsync(f.fileno())
            time.sleep(0.15)
            return dict(category='success',reference='synthetic-process-reference',status_code=200)
        try:
            if spec.get('action') == 'preflight':
                result = FinancialIntegratedPreflight(spec['business_id'],code_version='fixture').evaluate(Principal(spec['user_id'],0),spec['evaluation_uuid'],preflight_uuid=spec['preflight_uuid'],attestations=spec['attestations'])
            else:
                result = api.dispatch(spec['binding_uuid'],transport=fake)
            print(json.dumps(dict(result=result)),flush=True)
        except (StateError,ConflictError) as exc:
            print(json.dumps(dict(blocked=type(exc).__name__)),flush=True)
        finally:
            db.close_pool()


if __name__ == '__main__':
    main()
