"""Contratos del presupuesto offline; sin importar el runtime de Bynoesis."""

import unittest
from decimal import Decimal

from scripts.estimate_backup_cost import estimate


class BackupCostEstimateTests(unittest.TestCase):
    def test_retained_full_copies_and_provider_costs(self):
        result = estimate(set_gib=1, retention_days=30)
        self.assertEqual(result["retained_gib"], "30")
        self.assertEqual(Decimal(result["s3_storage_usd"]), Decimal("0.69"))
        self.assertEqual(Decimal(result["s3_put_usd"]), Decimal("0.0003"))
        self.assertEqual(Decimal(result["monthly_run_rate_usd"]), Decimal("2.300912736"))

    def test_no_lifecycle_keeps_growing(self):
        result = estimate(set_gib=1)
        self.assertEqual(result["retained_gib"], "365")
        self.assertFalse(result["deletion_policy_assumed"])

    def test_young_bucket_and_frequency(self):
        result = estimate(set_gib=2, elapsed_days=10, retention_days=30, copies_per_day=2)
        self.assertEqual(result["retained_gib"], "40")
        self.assertEqual(result["monthly_upload_gib"], "120")

    def test_invalid_values_and_unsupported_tier(self):
        for value in (0, -1, "nan", "inf", "abc", "-Infinity", 100000):
            with self.subTest(value=value), self.assertRaises(ValueError):
                estimate(set_gib=value)
        for field in ("copies_per_day", "elapsed_days", "retention_days"):
            for value in (0, -1, True, 1.5):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    estimate(set_gib=1, **{field: value})
