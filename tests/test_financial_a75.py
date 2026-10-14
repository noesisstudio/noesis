"""A75: nuevos sobres bound, ninguna reutilización de autoridad A74."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.financial_activation.contracts import (
    Profile, Policy, Capability, canonical, digest, binding_value, validate_proof_v2, read_legacy_canonical,
)
from noesis.financial_activation.evaluator import FinancialReadinessEvaluator
from noesis.financial_operations.contracts import Principal
from noesis.schema_lineage import require_runtime, SchemaLineageError


class A75Tests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="noesis-a75-")
        self.addCleanup(directory.cleanup)
        settings = patch.multiple(config, DATABASE_URL="", DB_PATH=Path(directory.name) / "fixture.db")
        settings.start()
        self.addCleanup(settings.stop)
        migrations.upgrade()
        with db.get_conn() as conn:
            conn.execute("UPDATE sqlite_sequence SET seq=200000 WHERE name='businesses'")
        self.business = db.create_business("Sólo fixture")
        self.bid = self.business["id"]
        self.assertNotEqual(self.bid, 15)
        db.set_trial(self.bid, days=14)
        user = db.create_user("a75@example.test", "fixture", self.bid)
        self.principal = Principal(user["id"], 0)

    def evaluate(self):
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            return FinancialReadinessEvaluator(FinancialSession(conn), self.bid).evaluate(
                self.principal, uuid4(), Profile((Capability.EXPENSE_CONFIRM,)), code_version="synthetic")

    def test_physical75_and_new_envelopes_keep_business_versions(self):
        result = self.evaluate()
        self.assertEqual(result["evaluation_version"], 2)
        self.assertEqual(result["context"]["context_version"], 2)
        self.assertEqual(result["context"]["schema_version"], 75)
        self.assertEqual(result["profile"]["profile_version"], 1)
        self.assertEqual(result["context"]["policy"]["policy_version"], 1)
        with db.get_conn() as conn:
            conn.execute("BEGIN")
            binding = require_runtime(conn).binding()
        self.assertEqual(result["context"]["schema_binding"], binding)
        for proof in result["capabilities"]:
            self.assertEqual(proof["proof_version"], 2)
            self.assertEqual(proof["schema_binding"], binding)
            self.assertEqual(validate_proof_v2(proof), proof)
        self.assertEqual(result["content_hash"], digest({k: result[k] for k in
            ("evaluation_version", "profile", "context", "capabilities", "outcome", "reasons")}))

    def test_privacy_is_still_blocked_and_no_activation(self):
        result = self.evaluate()
        proof = next(p for p in result["capabilities"] if p["capability"] == "expense.confirm")
        self.assertIn("PRIVACY_NOT_READY", proof["reasons"])
        self.assertNotEqual(result["outcome"], "fully_eligible")
        with db.get_conn() as conn:
            row = conn.execute("SELECT * FROM financial_activation_control WHERE business_id=?", (self.bid,)).fetchone()
            self.assertEqual((row["state"], row["activation_generation"], row["ever_enabled"]), ("off", 0, 0))

    def test_binding_contract_closed_unknown_bool_and_future(self):
        binding = self.evaluate()["context"]["schema_binding"]
        for change in ({"binding_version": True}, {"schema_version": 76},
                       {"schema_version": 75.0}, {"catalog_id": "legacy"}, {"extra": "x"}):
            with self.assertRaises(ValueError):
                binding_value(dict(binding, **change))

    def test_proofs_cannot_reuse_v1_or_extra_claims(self):
        proof = self.evaluate()["capabilities"][0]
        for change in ({"proof_version": 1}, {"proof_version": True}, {"authority": True}):
            with self.assertRaises(ValueError):
                validate_proof_v2(dict(proof, **change))

    def test_relevant_binding_modification_changes_hash(self):
        context = self.evaluate()["context"]
        changed = dict(context, schema_binding=dict(context["schema_binding"], object_profile_hash="a" * 64))
        self.assertNotEqual(digest(context), digest(changed))
        self.assertEqual(Profile((Capability.WEB,)).profile_version, 1)
        self.assertEqual(Policy().policy_version, 1)

    def test_identity_error_produces_no_readiness_write(self):
        with db.get_conn() as conn:
            conn.execute("UPDATE schema_migrations SET name='wrong' WHERE version=74")
        with self.assertRaises(SchemaLineageError):
            self.evaluate()
        with db.get_conn() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM financial_readiness_evaluations").fetchone()["n"], 0)

    def test_historical_canonical_bytes_and_hash_preserved_no_promotion(self):
        from tests.a74_frozen_fixture import A74_RAW, A74_HASH
        old = read_legacy_canonical(A74_RAW, A74_HASH)
        self.assertEqual(canonical(old), A74_RAW)
        self.assertEqual(digest(old), A74_HASH)
        self.assertEqual(old["evaluation_version"], 1)
        self.assertEqual(old["context"]["schema_version"], 74)
        self.assertNotIn("schema_binding", old["context"])
        with self.assertRaises(ValueError):
            read_legacy_canonical(A74_RAW.replace('"schema_version":74', '"schema_version":75'), A74_HASH)
        self.assertNotEqual(self.evaluate()["content_hash"], A74_HASH)

    def test_sql_physical_future_and_missing_binding_rejected(self):
        result = self.evaluate()
        with db.get_conn() as conn:
            row = conn.execute_exact("SELECT * FROM financial_readiness_evaluations WHERE business_id=?", (self.bid,)).fetchone()
        for schema, context in ((76, result["context"]), (75, dict(result["context"], schema_binding=None))):
            replacement = dict(row, evaluation_uuid=str(uuid4()), schema_version=schema,
                               context_canonical=canonical(context), context_hash=digest(context),
                               state="building", result=None, completed_at=None, result_canonical=None, content_hash=None)
            names = list(replacement)
            with self.assertRaises(Exception), db.get_conn() as conn:
                conn.execute("INSERT INTO financial_readiness_evaluations (" + ",".join(names) + ") VALUES (" + ",".join("?" for _ in names) + ")", tuple(replacement.values()))


if __name__ == "__main__":
    unittest.main()
