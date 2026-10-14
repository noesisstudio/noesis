"""Guard permanente: ni un baseline mutable ni MAX silencian una colisión."""

import unittest

from scripts.check_schema_lineage import ROOT, SOURCE, AUTHORIZED_MAIN, git, validate


class MigrationCollisionGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = git("show", f"{AUTHORIZED_MAIN}:{SOURCE}")
        cls.current = (ROOT / SOURCE).read_text(encoding="utf-8")

    def test_current_append_only_catalog_passes(self):
        self.assertEqual(validate(self.current, self.baseline, self.baseline)[-1],
                         (75, "evaluacion_readiness_financiera"))

    def test_duplicate74_and_deleted_history_fail(self):
        for altered in (self.current.replace('(75, "evaluacion_readiness_financiera"', '(74, "evaluacion_readiness_financiera"'),
                        self.current.replace('(74, "captacion_hoja_y_tipo"', '(76, "captacion_hoja_y_tipo"')):
            with self.assertRaises(ValueError):
                validate(altered, self.baseline, self.baseline)

    def test_name_changes_cannot_be_baselined_away(self):
        altered = self.current.replace('"captacion_hoja_y_tipo"', '"wrong"')
        with self.assertRaisesRegex(ValueError, "HISTORICAL_MIGRATION_CHANGED"):
            validate(altered, self.baseline, self.baseline)

    def test_historical_callback_change_fails(self):
        altered = self.current.replace('def _upgrade_sales_sheet_and_kind(conn)',
                                       'def _upgrade_sales_sheet_and_kind(conn, unexpected=None)')
        with self.assertRaisesRegex(ValueError, "HISTORICAL_DDL_CHANGED"):
            validate(altered, self.baseline, self.baseline)

    def test_main_drift_fails(self):
        with self.assertRaisesRegex(ValueError, "MIGRATION_PLAN_STALE"):
            validate(self.current, self.baseline, self.current)

    def test_missing_next_migration_fails(self):
        with self.assertRaises(ValueError):
            validate(self.baseline, self.baseline, self.baseline)


if __name__ == "__main__":
    unittest.main()
