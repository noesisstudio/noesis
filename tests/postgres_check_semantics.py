"""Prueba de dos CHECK reales contra el contrato Decimal; ningún dato de negocio."""
from decimal import Decimal, ROUND_DOWN, localcontext
import random

from psycopg import sql
from psycopg.rows import dict_row

from tests.postgres_identity_diagnostic import persist


def probes():
    values = [None, '0', '0.00', '0.01', '-0.01', '1.23', '-1.23', '1.230',
              '1.231', '-1.231', '9999999999999999.99', '-9999999999999999.99',
              '9999999999999999.991', '-9999999999999999.991',
              '10000000000000000', '-10000000000000000',
              '0.00000000000000000000000000000000000000000001',
              '-0.00000000000000000000000000000000000000000001',
              'NaN', 'Infinity', '-Infinity']
    rng = random.Random(751832)
    with localcontext() as context:
        context.prec = 160
        for _ in range(2048):
            coefficient = rng.randrange(-(10**40), 10**40)
            scale = rng.randrange(0, 81)
            values.append(str(Decimal(coefficient).scaleb(-scale)))
        for sign in (-1, 1):
            boundary = Decimal('9999999999999999.99') * sign
            for scale in (2, 3, 6, 20, 40, 80):
                for delta in (-2, -1, 0, 1, 2):
                    values.append(str(boundary + Decimal(delta).scaleb(-scale)))
    return values


def intended(value):
    if value is None:
        return True
    amount = Decimal(value)
    if not amount.is_finite():
        return False
    with localcontext() as context:
        context.prec = 160
        return (Decimal('-9999999999999999.99') <= amount <= Decimal('9999999999999999.99')
                and amount == amount.quantize(Decimal('0.01'), rounding=ROUND_DOWN))


def evaluate(target, expression, values):
    # SQL proviene del CHECK de nuestra instancia sintética sellada. El FROM
    # sólo contiene probes parametrizados; jamás consulta economic_events rows.
    statement = sql.SQL(
        'SELECT probe_id, ({}) AS result FROM '
        '(SELECT probe_id, raw_value::numeric AS amount '
        'FROM unnest(%s::int[],%s::text[]) AS probes(probe_id,raw_value)) sample ORDER BY probe_id'
    ).format(sql.SQL(expression))
    with target.connection() as conn:
        conn.row_factory = dict_row
        return [row['result'] for row in conn.execute(statement, (list(range(len(values))), values)).fetchall()]


class AmountCheckSemanticProof:
    def test_amount_check_semantic_equivalence(self):
        source = self.source_check['descriptor']
        restored = self.restored_check['descriptor']
        metadata = tuple(k for k in source if k not in ('constraintdef', 'expression'))
        self.assertTrue(all(source[k] == restored[k] for k in metadata), 'CHECK metadata differs')
        self.assertEqual(self.source_check['column'], self.restored_check['column'])
        self.assertEqual(self.source_check['column'], {'column_type': 'numeric', 'atttypmod': -1,
                                                      'numeric_precision': None, 'numeric_scale': None})
        for receipt in (self.source_check, self.restored_check):
            self.assertEqual(int(receipt['server']['version_num']) // 10000, 18)
        values = probes()
        source_results = evaluate(self.source, source['expression'], values)
        restored_results = evaluate(self.target75, restored['expression'], values)
        intent = [intended(value) for value in values]
        mismatches = [i for i, expected in enumerate(intent)
                      if source_results[i] != restored_results[i] or source_results[i] != expected]
        receipt = {'total': len(values), 'mismatches': mismatches,
                   'probes': [{'value': value, 'source': a, 'restored': b, 'intended': c}
                              for value, a, b, c in zip(values, source_results, restored_results, intent)]}
        persist('v2-check-semantic-proof', receipt)
        print('PG_CHECK_SEMANTIC_PROOF', len(values), 'probes;', len(mismatches), 'mismatches', flush=True)
        self.assertFalse(mismatches, 'REAL CHECK SEMANTIC MISMATCH at probe indices')
