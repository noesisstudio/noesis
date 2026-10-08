"""G-PREP sólo calcula expedientes; fixtures sintéticos, sin autoridad ni red."""

import ast
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from noesis.financial_activation.contracts import Capability as C, Profile, canonical, digest
from noesis.financial_pilot.contracts import (EvidenceKind, EvidenceReference, Finding,
                                            PilotReadinessReport, PreparationContext, Reason)
from noesis.financial_pilot.report import prepare_report, proposals, describe_profile
from noesis.financial_pilot.__main__ import main


NOW = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)


class PilotPreparation(unittest.TestCase):
    def context(self, **changes):
        fields = dict(code_sha="a" * 40, source_context_hash=digest({"synthetic": True}),
                      business_id=1, profile=Profile((C.EXPENSE_CONFIRM, C.EXPENSE_VOID)))
        return PreparationContext(**(fields | changes))

    def report(self, **changes):
        return prepare_report(self.context(**changes), now=NOW)

    def reasons(self, **changes):
        return {b["reason_code"] for b in self.report(**changes).body["blockers"]}

    def test_policy_provisional_privacy_blocked(self):
        report = self.report().body
        self.assertEqual(report["result"], "PILOT_BLOCKED")
        self.assertIn(Reason.LEGAL, self.reasons())
        self.assertIn(Reason.PRIVACY, self.reasons())
        self.assertFalse(report["activation_authorized"])

    def test_missing_business_and_profile(self):
        reasons = self.reasons(business_id=None, profile=None)
        self.assertIn(Reason.BUSINESS, reasons)
        self.assertIn(Reason.PROFILE, reasons)

    def test_missing_provider_blocks_required_closure(self):
        reasons = self.reasons(profile=Profile((C.WHATSAPP,)))
        self.assertIn(Reason.PROVIDER, reasons)
        self.assertIn(Reason.SAFE_CHECK, reasons)

    def test_missing_backup_and_restore(self):
        self.assertTrue({Reason.BACKUP, Reason.RESTORE} <= self.reasons())

    def test_missing_operator_and_custodian(self):
        self.assertTrue({Reason.OPERATOR, Reason.CUSTODIAN} <= self.reasons())

    def test_bank_requested_blocked_without_shrinking(self):
        p = Profile((C.BANK_MATCH,))
        report = self.report(profile=p).body
        self.assertIn(Reason.BANK, {b["reason_code"] for b in report["blockers"]})
        self.assertEqual(report["context"]["profile"], p.value())
        self.assertIn(C.BANK_IMPORT, report["capability_closure"])

    def test_exact_minimum_reuses_c_registry(self):
        minimal = proposals()["web_only"]
        self.assertEqual(minimal["capability_closure"], [C.WEB, C.EXPENSE_CONFIRM, C.EXPENSE_VOID])
        self.assertEqual(minimal["provider_requirements"], {})

    def test_web_alone_is_not_financial_pilot(self):
        from noesis.financial_activation.contracts import FINANCIAL
        self.assertTrue(any(c in FINANCIAL for c in proposals()["web_only"]["capability_closure"]))
        self.assertFalse(any(c in FINANCIAL for c in Profile((C.WEB,)).closure(fiscal_cancel_required=False)[0]))

    def test_fiscal_invoice_includes_aeat_cancel_rectify(self):
        fiscal = proposals()["web_fiscal"]
        self.assertTrue({C.INVOICE_ISSUE, C.INVOICE_RECTIFY, C.FISCAL_CANCEL, C.AEAT, C.WEB}
                        == set(fiscal["capability_closure"]))
        self.assertEqual(fiscal["provider_requirements"], {C.AEAT: "AEAT_VERIFACTU"})

    def test_unknown_fiscal_condition_never_drops_aeat(self):
        report = self.report(profile=Profile((C.INVOICE_ISSUE,))).body
        self.assertIn(C.AEAT, report["capability_closure"])
        self.assertIn(Reason.FISCAL, {b["reason_code"] for b in report["blockers"]})

    def test_channels_require_meta_email(self):
        self.assertEqual(set(proposals()["web_channels"]["provider_requirements"].values()),
                         {"META_WHATSAPP", "EMAIL_DELIVERY"})

    def test_no_profile_shrinking_hides_history(self):
        findings = (Finding(Reason.UNSUPPORTED), Finding(Reason.HISTORY))
        for profile in (Profile((C.WEB,)), Profile((C.EXPENSE_CONFIRM,)), Profile((C.INVOICE_ISSUE,))):
            with self.subTest(profile=profile):
                reasons = self.reasons(profile=profile, findings=findings)
                self.assertTrue({Reason.UNSUPPORTED, Reason.HISTORY} <= reasons)

    def test_same_evidence_deterministic(self):
        a, b = self.report(), self.report()
        self.assertEqual(a.canonical_content, b.canonical_content)
        self.assertEqual(a.content_hash, b.content_hash)

    def test_order_of_capabilities_and_findings_deterministic(self):
        a = self.report(profile=Profile((C.EXPENSE_VOID, C.EXPENSE_CONFIRM)),
                        findings=(Finding(Reason.STALE), Finding(Reason.UNSUPPORTED)))
        b = self.report(findings=(Finding(Reason.UNSUPPORTED), Finding(Reason.STALE)))
        self.assertEqual(a.content_hash, b.content_hash)

    def test_drift_new_hash_and_stale_original(self):
        context = self.context()
        original = prepare_report(context, now=NOW)
        drift = self.context(source_context_hash=digest({"synthetic": "drift"}))
        self.assertFalse(original.current(drift, now=NOW))
        self.assertNotEqual(original.content_hash, prepare_report(drift, now=NOW).content_hash)

    def test_expiry_and_future_clock_fail_closed(self):
        context = self.context()
        report = prepare_report(context, now=NOW)
        self.assertTrue(report.current(context, now=NOW))
        self.assertFalse(report.current(context, now=NOW + timedelta(seconds=300)))
        self.assertFalse(report.current(context, now=NOW - timedelta(seconds=1)))

    def test_cross_tenant_reference_rejected(self):
        reference = EvidenceReference(EvidenceKind.REFERENCE, "b" * 64, 2)
        with self.assertRaises(ValueError):
            self.context(findings=(Finding(Reason.BACKUP, reference),))

    def test_unnamed_business_cannot_adopt_real_reference(self):
        reference = EvidenceReference(EvidenceKind.REFERENCE, "b" * 64, 1)
        with self.assertRaises(ValueError):
            self.context(business_id=None, findings=(Finding(Reason.BACKUP, reference),))

    def test_synthetic_or_reference_only_never_removes_blocker(self):
        for kind in (EvidenceKind.SYNTHETIC, EvidenceKind.REFERENCE, EvidenceKind.DOCUMENT):
            reasons = self.reasons(findings=(Finding(Reason.BACKUP, EvidenceReference(kind, "b" * 64, 1)),))
            self.assertIn(Reason.BACKUP, reasons)
            self.assertIn(Reason.REAL, reasons)

    def test_main_integration_pending_is_mandatory(self):
        self.assertIn(Reason.MAIN, self.reasons())

    def test_closing_closed_findings_still_block(self):
        self.assertTrue({Reason.CLOSING, Reason.CLOSED} <= self.reasons(
            findings=(Finding(Reason.CLOSING), Finding(Reason.CLOSED))))

    def test_every_blocker_has_closed_owner_remediation_external_bool(self):
        for blocker in self.report().body["blockers"]:
            self.assertEqual(set(blocker), {"reason_code", "evidence_reference", "remediation",
                                           "responsible_party", "requires_external_action"})
            self.assertIs(type(blocker["requires_external_action"]), bool)
            self.assertTrue(blocker["remediation"])

    def test_unknown_versions_extra_fields_float_and_fake_ready_rejected(self):
        for key, value in (("version", 2), ("version", True), ("result", "PILOT_READY"),
                           ("activation_authorized", True), ("real_evidence_verified", True),
                           ("password", "synthetic-sensitive-marker"), ("version", 1.0)):
            with self.subTest(key=key, value=value), self.assertRaises((ValueError, TypeError)):
                PilotReadinessReport(json.dumps(self.report().body | {key: value}))

    def test_tampered_reason_metadata_and_hash_rejected(self):
        body = self.report().body
        body["blockers"][0]["responsible_party"] = "free-text-admin"
        with self.assertRaises(ValueError):
            PilotReadinessReport(canonical(body))
        body = self.report().body | {"context_hash": "b" * 64}
        with self.assertRaises(ValueError):
            PilotReadinessReport(canonical(body))

    def test_input_closed_no_secrets_pii_or_approval_field(self):
        for key in ("token", "approved", "verified_real", "email", "DATABASE_URL"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                PreparationContext.decode(self.context().value() | {key: "synthetic-sensitive-marker"})
        with self.assertRaises(ValueError):
            EvidenceReference(EvidenceKind.REFERENCE, "synthetic-secret-marker", 1)
        self.assertNotIn("synthetic-sensitive-marker", self.report().canonical_content)

    def test_duplicate_unknown_reason_and_fake_verified_kind(self):
        with self.assertRaises(ValueError):
            self.context(findings=(Finding(Reason.STALE), Finding(Reason.STALE)))
        with self.assertRaises(ValueError):
            Finding("warning_ready")
        with self.assertRaises(ValueError):
            EvidenceReference("verified_real", "b" * 64, 1)

    def test_reason_catalog_is_complete_and_immutable(self):
        from noesis.financial_pilot.report import SPECS
        self.assertEqual(set(SPECS), set(Reason))
        with self.assertRaises(TypeError):
            SPECS[Reason.LEGAL] = ("free-admin", "fake approval", False)

    def test_null_zero_bool_and_float_not_interchangeable(self):
        for bid in (0, True, 1.0, -1):
            with self.subTest(bid=bid), self.assertRaises((TypeError, ValueError)):
                self.context(business_id=bid)
        with self.assertRaises(TypeError):
            self.context(fiscal_required=1)
        with self.assertRaises(ValueError):
            prepare_report(self.context(), now=NOW.replace(tzinfo=None))

    def test_roundtrip_closed_immutable_copies(self):
        report = self.report()
        body = report.body
        body["blockers"].clear()
        self.assertTrue(report.body["blockers"])
        self.assertEqual(PilotReadinessReport(report.canonical_content).content_hash, report.content_hash)

    def test_cli_without_selected_business_no_io(self):
        from noesis import db
        out = StringIO()
        with patch.object(db, "get_conn", side_effect=AssertionError("No DB")), \
                patch.object(socket.socket, "connect", side_effect=AssertionError("No network")), redirect_stdout(out):
            self.assertEqual(main(["--code-sha", "a" * 40]), 0)
        body = json.loads(out.getvalue())
        self.assertIsNone(body["context"]["business_id"])
        self.assertIsNone(body["context"]["profile"])
        self.assertEqual(body["result"], "PILOT_BLOCKED")

    def test_no_mutation_all_sqlite_tables_flags_and_no_writer_calls(self):
        from noesis import config, db
        from noesis.financial_activation.handoff import FinancialActivation
        from noesis.financial_providers import attestations
        with tempfile.TemporaryDirectory() as directory, patch.multiple(
                config, DATABASE_URL="", DB_PATH=Path(directory) / "synthetic.db"):
            db.init_db()
            def snapshot():
                with db.get_conn() as conn:
                    tables = [r["name"] for r in conn.execute_exact(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
                    return {t: [dict(r) for r in conn.execute_exact('SELECT * FROM "' + t + '"').fetchall()]
                            for t in tables}
            before = snapshot()
            flag_names = ("FINANCIAL_CORE_ENABLED", "LEDGER_REPORTING_ENABLED", "OPEN_ITEMS_ENABLED",
                          "NEW_TAX_ENGINE_ENABLED", "NEW_BANK_RECONCILIATION_ENABLED")
            flags = {k: getattr(config, k) for k in flag_names}
            with patch.object(db, "get_conn", side_effect=AssertionError("No DB")), \
                    patch.object(FinancialActivation, "prepare", side_effect=AssertionError("No handoff")), \
                    patch.object(attestations, "check", side_effect=AssertionError("No attestation")), \
                    patch.object(socket.socket, "connect", side_effect=AssertionError("No network")):
                self.report()
                self.report(profile=Profile((C.INVOICE_ISSUE,)))
                proposals()
            self.assertEqual(snapshot(), before)
            self.assertEqual(flags, {k: getattr(config, k) for k in flag_names})

    def test_package_imports_no_db_network_writers_or_provider_clients(self):
        root = Path(__file__).resolve().parents[1] / "src/noesis/financial_pilot"
        for path in root.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    modules = [n.name for n in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                else:
                    continue
                self.assertFalse(any(m.startswith(("socket", "httpx", "requests", "noesis.db", "noesis.adapters",
                                                   "noesis.financial_activation.handoff", "noesis.financial_providers.dispatch"))
                                     for m in modules), path)

    def test_readonly_query_plan_against_synthetic_schema79(self):
        from noesis import config, db
        text = (Path(__file__).resolve().parents[1] /
                "docs/architecture/FINANCIAL-PILOT-READONLY-QUERIES-v1.sql").read_text(encoding="utf-8")
        statements = "\n".join(line for line in text.splitlines() if not line.startswith("--")).split(";")
        checked = 0
        with tempfile.TemporaryDirectory() as directory, patch.multiple(
                config, DATABASE_URL="", DB_PATH=Path(directory) / "synthetic.db"):
            db.init_db()
            with db.get_conn() as conn:
                conn.execute("PRAGMA query_only=ON")
                for statement in statements:
                    statement = statement.strip()
                    if not statement:
                        continue
                    self.assertTrue(statement.startswith("SELECT"))
                    if "pg_roles" in statement or "has_table_privilege" in statement:
                        continue  # Catálogo PG, no fingir validación SQLite de esos dos fragmentos.
                    sql = statement.replace(":'business_id'::bigint", "?")
                    with self.subTest(query=sql[:75]):
                        conn.execute_exact("EXPLAIN QUERY PLAN " + sql, (1,) * sql.count("?")).fetchall()
                    checked += 1
        self.assertEqual(checked, 15)

    def test_profile_descriptor_rejects_unknown_capability(self):
        with self.assertRaises(ValueError):
            Profile(("quote.accepted",))
        with self.assertRaises(TypeError):
            describe_profile({"capabilities": [C.WEB]}, fiscal_required=False)


if __name__ == "__main__":
    unittest.main()
