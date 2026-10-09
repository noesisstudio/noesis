"""Mediciones F sintéticas reproducibles; sin datos reales ni promesas de SLO."""

import json
import sys
import time
import tracemalloc
from uuid import uuid4
from noesis import db
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.contracts import Capability as C
from noesis.financial_providers.observability import read
from noesis.financial_providers.dispatch import FinancialProviderDispatch
from noesis.financial_providers.schema import ATTEMPTS
from tests.financial_readiness_contract import ReadinessContract
from tests.test_financial_providers import ProviderSQLite


def measure(name, fn):
    tracemalloc.start()
    start=time.monotonic()
    value=fn()
    seconds=time.monotonic()-start
    _,peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(json.dumps(dict(case=name,seconds=round(seconds,6),peak_python_bytes=peak,result=value.get('result') if isinstance(value,dict) else None)),flush=True)
    return value


def main():
    pg = len(sys.argv)>1 and sys.argv[1]=='postgres'
    if pg:
        from tests.postgres_financial_providers import ProviderPostgres
        cls=ProviderPostgres
        cls.setUpClass()
    else:
        cls=ProviderSQLite
    try:
        for cohort in (0,63):
            case=cls('test_closed_catalog_from_single_c_registry')
            if cohort:
                def cut():
                    for i in range(cohort):
                        db.add_expense('Histórico sintético '+str(i),'1.00',business_id=case.bid)
                    return ReadinessContract.cut(case)
                case.cut=cut
            try:
                case.setUp()
                value,refs=case.ready()
                receipt=measure('preflight_empty' if not cohort else 'preflight_64_history_items',lambda:case.preflight.evaluate(case.principal,value['evaluation_uuid'],attestations=refs))
                expected=64 if cohort else 1  # La identidad fiscal también es item diagnóstico.
                assert receipt['context']['volume']==expected,receipt['context']['volume']
                measure('operational_snapshot_'+str(expected),lambda:read_model(case))
            finally:
                case.doCleanups()
        case=cls('test_closed_catalog_from_single_c_registry')
        try:
            case.setUp()
            caps=(C.EXPENSE_CONFIRM,C.INVOICE_ISSUE,C.EMAIL,C.WHATSAPP)
            value,refs=case.ready(caps,(C.AEAT,C.EMAIL,C.WHATSAPP))
            receipt=measure('preflight_three_providers',lambda:case.preflight.evaluate(case.principal,value['evaluation_uuid'],attestations=refs))
            assert receipt['result']=='PASS',receipt['reasons']
        finally:
            case.doCleanups()
        case=cls('test_closed_catalog_from_single_c_registry')
        try:
            case.setUp()
            case.enable()
            op=case.expense_operation()
            start=time.monotonic()
            for i in range(501):
                if i and i%100==0:
                    case.verified()
                    print('SYNTHETIC_PROVIDER_ATTEMPTS',i,flush=True)
                binding=case.bound_email(op)
                result=FinancialProviderDispatch(case.bid).dispatch(binding['binding_uuid'],transport=case.success)
                assert result['result']=='SUCCEEDED'
            print(json.dumps(dict(fixture_attempts=501,fixture_seconds=round(time.monotonic()-start,3))),flush=True)
            with db.get_conn() as c:
                assert c.execute('SELECT COUNT(*) AS n FROM '+ATTEMPTS+' WHERE business_id=?',(case.bid,)).fetchone()['n']==501
            measure('operational_snapshot_501_attempts',lambda:read_model(case))
            case.pause()
            case.exporter.export(case.principal,uuid4())
            ref=case.verified()
            receipt=measure('preflight_501_attempts_resume',lambda:case.preflight.evaluate(case.principal,case.origin_evaluation['evaluation_uuid'],attestations={C.EMAIL.value:ref['attestation_uuid']},action='resume'))
            # Si preparar 501 filas supera 5 min, READINESS_STALE es el bloqueo correcto.
            assert receipt['result'] in ('PASS','BLOCKED')
        finally:
            case.doCleanups()
    finally:
        if pg:
            cls.tearDownClass()


def read_model(case):
    with db.get_conn() as c:
        return read(FinancialSession(c),case.bid,case.principal)


if __name__=='__main__':
    main()
