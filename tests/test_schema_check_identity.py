"""El único rewrite aprobado no oculta diferencias de reglas/metadata."""

import unittest

from noesis.schema_check_identity import SOURCE_AMOUNT_CHECK, canonical_amount_check
from noesis.schema_objects import normalized_sql, expected_objects


RESTORED = "CHECK (((amount IS NULL) OR ((amount >= '-9999999999999999.99'::numeric) AND (amount <= 9999999999999999.99) AND (amount = trunc(amount, 2)))))"


class AmountCheckIdentity(unittest.TestCase):
    def test_two_demonstrated_trees_keep_original_canonical_descriptor(self):
        self.assertEqual(canonical_amount_check(SOURCE_AMOUNT_CHECK), SOURCE_AMOUNT_CHECK)
        self.assertEqual(canonical_amount_check(RESTORED), SOURCE_AMOUNT_CHECK)
        expected = expected_objects('postgres', 75)['constraint:economic_events:economic_events_amount_check']
        self.assertEqual(normalized_sql(canonical_amount_check(RESTORED)), expected[-1])

    def test_changed_leaves_structure_or_metadata_never_equal(self):
        changes = (
            RESTORED.replace('9999999999999999.99)', '9999999999999999.98)'),
            RESTORED.replace('trunc(amount, 2)', 'trunc(amount, 3)'),
            RESTORED.replace('>=', '>'),
            RESTORED.replace(' AND ', ' OR ', 1),
            RESTORED.replace('::numeric', '::double precision'),
            RESTORED.replace('trunc', 'round'),
            RESTORED.replace('IS NULL', 'IS NOT NULL'),
            RESTORED + ' NOT VALID', RESTORED + ' NO INHERIT',
            RESTORED.replace(' AND (amount = trunc(amount, 2))', ''),
            'CHECK (amount IS NULL OR amount=trunc(amount,2))',
        )
        for changed in changes:
            with self.subTest(changed=changed):
                self.assertEqual(canonical_amount_check(changed), changed)
                self.assertNotEqual(normalized_sql(canonical_amount_check(changed)), normalized_sql(SOURCE_AMOUNT_CHECK))

    def test_retention_profiles_closed_versions_and_stable_distinct_fingerprints(self):
        from noesis.schema_retention import retention_objects
        from noesis.schema_lineage import canonical
        import hashlib
        goldens = {  # Huellas públicas de perfiles técnicos, nunca evidencia REAL.
            53: '4b86e9ac505049fd7530a4086ce109ea723db6507fc4b21deedd936c40f2aea5',  # pragma: allowlist secret
            54: '00f1b30e9d0c3be2fe77910a0bc072df242c900c01900acec6b572978ec5c15b',  # pragma: allowlist secret
            55: 'fe69f4d396605716b3a25c7d655943f247253315c83a8242f047cf682bd0f2ec',  # pragma: allowlist secret
            58: 'de02550ecab527f23c047261141285ccf630aede5ba15b3014c06aa92d5910bc',  # pragma: allowlist secret
        }
        for version in (53, 54, 55, 58):
            canonical_profile = expected_objects('postgres', version)
            technical = retention_objects(version)
            self.assertEqual(len(set(technical) - set(canonical_profile)), 33 if version == 58 else 34)
            self.assertTrue(all(technical[key] == value for key, value in canonical_profile.items()))
            fingerprint = lambda value: hashlib.sha256(canonical(value).encode()).hexdigest()
            self.assertNotEqual(fingerprint(technical), fingerprint(canonical_profile))
            self.assertEqual(fingerprint(technical), fingerprint(retention_objects(version)))
            self.assertEqual(fingerprint(technical), goldens[version])
        for version in (0, 52, 56, 57, 59, 60, 74, 75, 76):
            self.assertIsNone(retention_objects(version))

    def test_technical_integrity_cannot_be_promoted_by_version_or_profile_claim(self):
        from dataclasses import replace
        from noesis.schema_lineage import CATALOG, SchemaLineageError, classify_registry
        for version in (53, 54, 55, 58, 75):
            for profile in (f'postgres/retention-owner/{version}/v1', 'postgres/canonical75/v1'):
                observation = replace(classify_registry(CATALOG[:version]),
                                      integrity='TECHNICAL_ONLY', object_profile_id=profile)
                for consumer in (observation.binding, lambda: observation.require_canonical((version, 75))):
                    with self.assertRaisesRegex(SchemaLineageError, 'SCHEMA_LINEAGE_MISMATCH'):
                        consumer()
