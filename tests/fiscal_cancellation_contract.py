"""C compartida: fixtures reales sintéticos, evidencia fiscal local sin red."""

from dataclasses import replace
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from noesis import config, db, migrations
from noesis.core.persistence import FinancialSession
from noesis.economic_events.service import EconomicEvents
from noesis.financial_antecedents.contracts import Purpose
from noesis.financial_operations.contracts import (
    AccessDenied, AuthorizationKind, ConflictError, EntryIdentity, EntryNamespace,
    Principal, StateError, OperationState,
)
from noesis.financial_operations.repository import OperationsRepository
from noesis.financial_writers.boundary import WriterConnection, snapshot
from noesis.financial_writers import invoices
from noesis.fiscal_cancellation_capture.service import FiscalCancellationCapture
from tests.financial_antecedents_contract import AntecedentsContract
from noesis.financial_history.reconciliation_verifier import storage_hash
from tests.invoice_capture_contract import InvoiceCaptureContract
from tests.financial_readiness_contract import ReadinessContract


class FiscalCancellationContract:
    seed = AntecedentsContract.seed
    draft = AntecedentsContract.draft
    approve = AntecedentsContract.approve
    approved = AntecedentsContract.approved
    captured = AntecedentsContract.captured
    payment = AntecedentsContract.payment
    event_ref = AntecedentsContract.event_ref
    resolve = AntecedentsContract.resolve
    tx = AntecedentsContract.tx
    exact_storage = AntecedentsContract.exact_storage
    sources = AntecedentsContract.sources
    historical = AntecedentsContract.historical
    corruption = AntecedentsContract.corruption
    migration_scope = InvoiceCaptureContract.migration_scope
    cut = ReadinessContract.cut

    def setup_capture(self):
        self.setup_cancellation()

    def setup_cancellation(self):
        AntecedentsContract.setup_antecedents(self)
        self.cancel = FiscalCancellationCapture(self.bid)
        network = patch("urllib.request.urlopen", side_effect=AssertionError("Provider I/O prohibido"))
        network.start()
        self.addCleanup(network.stop)
        aeat = patch("noesis.verifactu_client.submit_records", side_effect=AssertionError("AEAT prohibida"))
        self.aeat = aeat.start()
        self.addCleanup(aeat.stop)

    def fixture(self, *, accepted="aceptado", payments=None, **draft):
        op = self.captured(**draft)
        invoice_id = op.result["invoice_id"]
        if payments:
            self.payment(invoice_id, payments)
        with db.get_conn() as conn:
            conn.execute("UPDATE verifactu_outbox SET status=? WHERE business_id=? AND invoice_id=?",
                         (accepted, self.bid, invoice_id))
        ref = self.event_ref(op.result["event_uuid"])
        saved = self.resolve(ref, Purpose.FISCAL_CANCEL, persist=True)
        return invoice_id, saved

    def prepared(self, *, saved=None, reason="Alta duplicada por error", **draft):
        if saved is None:
            _, saved = self.fixture(**draft)
        request = self.cancel.review(self.principal, saved, reason=reason)
        identity = EntryIdentity.web_api(uuid4())
        return self.cancel.prepare(self.principal, identity, request), request, identity

    def authorized(self, **kwargs):
        op, request, identity = self.prepared(**kwargs)
        return self.cancel.authorize(
            self.principal, op.operation_uuid, channel=EntryNamespace.WEB_API,
            approved_hash=request.request_hash, approved_revision=request.expected_revision,
        )

    def rows(self, table):
        with db.get_conn() as conn:
            return conn.execute_exact("SELECT * FROM " + table + " WHERE business_id=?", (self.bid,)).fetchall()

    def state(self, *, execution=False, include_operations=False):
        allowed = set() if include_operations else {"financial_operations", "financial_authorizations"}
        if execution:
            allowed |= {"invoice_cancellation_records", "verifactu_cancellation_outbox", "invoice_events",
                        "invoice_fiscal_cancellation_coverage", "economic_events", "economic_event_links",
                        "economic_event_sequences"}
        state = AntecedentsContract.snapshot(self)
        # B no se omite: su evidencia durable también debe permanecer idéntica.
        state["financial_antecedent_resolutions"] = sorted(
            storage_hash(r) for r in self.rows("financial_antecedent_resolutions")
        )
        return {k: v for k, v in state.items() if k not in allowed}

    def test_full_positive_atomic_evidence_only_economic_sources_unchanged(self):
        _, saved = self.fixture(payments="10.01")
        before = self.state()
        op, req, identity = self.prepared(saved=saved)
        self.assertIsNone(req.amount)
        self.assertEqual(before, self.state())
        approved = self.cancel.authorize(self.principal, op.operation_uuid, channel=identity.namespace,
                                        approved_hash=req.request_hash, approved_revision=req.expected_revision)
        self.assertEqual(before, self.state())
        before_effect = self.state(execution=True)
        done = self.cancel.execute(self.principal, approved.operation_uuid)
        self.assertEqual(before_effect, self.state(execution=True))
        self.assertEqual(done.state, OperationState.COMMITTED)
        self.assertIsNone(done.result["amount"])
        self.assertEqual(done.result["original_total"], "121.00")
        records = self.rows("invoice_cancellation_records")
        self.assertEqual(len(records), 1)
        self.assertEqual(self.rows("verifactu_cancellation_outbox")[0]["status"], "pendiente")
        self.assertEqual(len(self.rows("invoice_fiscal_cancellation_coverage")), 1)
        with db.get_conn() as conn:
            stored = EconomicEvents(FinancialSession(conn), self.bid).read(self.principal, done.result["event_uuid"])
            actual = snapshot(conn, self.bid, "invoice_cancellation_record", records[0]["id"])
        self.assertIsNone(stored.event.amount)
        self.assertEqual(stored.event.payload["original_total"], Decimal("121.00"))
        self.assertEqual(stored.event.source_revision, actual.revision)
        self.assertNotEqual(stored.event.source_revision, 1)
        self.assertEqual(str(stored.event.relations[0].target_event_id), saved["result"]["event_uuid"])
        self.assertEqual(stored.event.relations[0].kind.value, "evidence_for")
        self.aeat.assert_not_called()

    def test_accepted_with_errors_supported(self):
        op = self.authorized(accepted="aceptado_con_errores")
        self.assertEqual(self.cancel.execute(self.principal, op.operation_uuid).state, OperationState.COMMITTED)

    def test_exact_retry_prepare_authorize_execute(self):
        op, request, identity = self.prepared()
        self.assertEqual(self.cancel.prepare(self.principal, identity, request), op)
        self.cancel.authorize(self.principal, op.operation_uuid, channel=identity.namespace,
                              approved_hash=request.request_hash, approved_revision=request.expected_revision)
        first = self.cancel.execute(self.principal, op.operation_uuid)
        before = self.state()
        self.assertEqual(self.cancel.execute(self.principal, op.operation_uuid), first)
        self.assertEqual(self.cancel.prepare(self.principal, identity, request), first)
        self.assertEqual(before, self.state())

    def test_lost_response_after_commit_recovers_exact_without_writer(self):
        op = self.authorized()
        commit = db.Connection.commit

        def lost(conn):
            commit(conn)
            raise TimeoutError("Respuesta perdida después de commit")

        with patch.object(db.Connection, "commit", lost), self.assertRaises(TimeoutError):
            self.cancel.execute(self.principal, op.operation_uuid)
        before = self.state()
        with patch.object(invoices, "create_invoice_cancellation_record", side_effect=AssertionError("No repetir")):
            recovered = self.cancel.execute(self.principal, op.operation_uuid)
        self.assertEqual(recovered.state, OperationState.COMMITTED)
        self.assertEqual(len(self.rows("invoice_cancellation_records")), 1)
        self.assertEqual(before, self.state())

    def test_not_accepted_pending_rejected_timeout_block_without_effect(self):
        for status in ("pendiente", "rechazado", "enviado"):
            iid, saved = self.fixture(accepted="aceptado")
            with db.get_conn() as conn:
                conn.execute("UPDATE verifactu_outbox SET status=? WHERE business_id=? AND invoice_id=?",
                             (status, self.bid, iid))
            before = self.state()
            with self.assertRaises(StateError):
                self.cancel.review(self.principal, saved, reason="Alta incorrecta")
            self.assertEqual(before, self.state())

    def test_invalid_reason_and_request_rejected(self):
        _, saved = self.fixture()
        for reason in (None, "", "abcd", "x" * 1001, " motivo válido ", 1):
            with self.assertRaises((ValueError, TypeError)):
                self.cancel.review(self.principal, saved, reason=reason)
        op, req, identity = self.prepared(saved=saved)
        for wrong in (replace(req, amount="1.00"), replace(req, target_id=None, expected_revision=None),
                      replace(req, parameters={}), replace(req, command_type="invoice.issue")):
            with self.assertRaises(StateError):
                self.cancel.prepare(self.principal, EntryIdentity.web_api(uuid4()), wrong)
        with self.assertRaises(TypeError):
            replace(req, amount=1.0)
        with self.assertRaises(ValueError):
            replace(req, currency="USD")
        with self.assertRaises(ConflictError):
            self.cancel.prepare(self.principal, identity, replace(req, reason="Otro motivo válido"))

    def test_unauthorized_operation_and_wrong_approval_rejected(self):
        op, req, identity = self.prepared()
        with self.assertRaises(StateError):
            self.cancel.execute(self.principal, op.operation_uuid)
        for approval in ({"approved_hash": "0" * 64, "approved_revision": req.expected_revision},
                         {"approved_hash": req.request_hash, "approved_revision": req.expected_revision + 1}):
            with self.assertRaises(StateError):
                self.cancel.authorize(self.principal, op.operation_uuid, channel=identity.namespace, **approval)

    def test_mandate_historical_and_forged_resolution_rejected(self):
        _, saved = self.fixture()
        op, req, identity = self.prepared(saved=saved)
        for kind in (AuthorizationKind.MANDATE, AuthorizationKind.HISTORICAL_UNKNOWN):
            with self.assertRaises(StateError):
                self.cancel.authorize(self.principal, op.operation_uuid, kind=kind, channel=identity.namespace,
                                      approved_hash=req.request_hash, approved_revision=req.expected_revision)
        forged = dict(saved, content_hash="0" * 64)
        with self.assertRaises(ConflictError):
            self.cancel.review(self.principal, forged, reason="Alta inválida")

    def test_wrong_purpose_and_blocked_resolution_rejected(self):
        iid, saved = self.fixture()
        other = self.resolve(self.event_ref(saved["result"]["event_uuid"]), Purpose.RECTIFY, persist=True)
        with self.assertRaises(StateError):
            self.cancel.review(self.principal, other, reason="Alta inválida")
        legacy = db.issue_invoice(self.draft()["id"], self.bid)
        with db.get_conn() as conn:
            src = snapshot(conn, self.bid, "invoice", legacy["id"])
        from noesis.financial_antecedents.contracts import AntecedentRef
        blocked = self.resolve(AntecedentRef("invoice", legacy["id"], src.revision), Purpose.FISCAL_CANCEL, persist=True)
        self.assertEqual(blocked["result"]["outcome"], "blocked")
        with self.assertRaises(StateError):
            self.cancel.review(self.principal, blocked, reason="Alta inválida")

    def test_observed_historical_evidence_not_operational(self):
        ref = self.historical()
        saved = self.resolve(ref, Purpose.INSPECT, persist=True)
        self.assertEqual(saved["result"]["quality"], "observed_state")
        with self.assertRaises(StateError):
            self.cancel.review(self.principal, saved, reason="Alta inválida")

    def test_stale_source_before_authorize_and_execute(self):
        op, req, identity = self.prepared()
        self.payment(req.target_id, "1.00")
        with self.assertRaises(ConflictError):
            self.cancel.authorize(self.principal, op.operation_uuid, channel=identity.namespace,
                                  approved_hash=req.request_hash, approved_revision=req.expected_revision)
        done = self.authorized()
        self.payment(done.request.target_id, "1.00")
        with self.assertRaises(ConflictError):
            self.cancel.execute(self.principal, done.operation_uuid)

    def test_config_and_fiscal_outbox_drift_block(self):
        op = self.authorized()
        with patch.object(config, "VERIFACTU_SYSTEM_VERSION", "drift"), self.assertRaises(StateError):
            self.cancel.execute(self.principal, op.operation_uuid)
        with db.get_conn() as conn:
            conn.execute("UPDATE verifactu_outbox SET status='pendiente' WHERE business_id=?", (self.bid,))
        with self.assertRaises(StateError):
            self.cancel.execute(self.principal, op.operation_uuid)

    def test_other_tenant_and_expired_session_uniform_denial(self):
        _, saved = self.fixture()
        other = db.create_business("Otro", uuid4().hex + "@example.test")
        user = db.create_user(uuid4().hex + "@example.test", "fixture", other["id"])
        with self.assertRaises(AccessDenied):
            FiscalCancellationCapture(other["id"]).review(Principal(user["id"], 0), saved, reason="Alta inválida")
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET session_version=1 WHERE business_id=?", (self.bid,))
        with self.assertRaises(AccessDenied):
            self.cancel.review(self.principal, saved, reason="Alta inválida")

    def test_existing_legacy_cancellation_never_adopted(self):
        iid, saved = self.fixture()
        db.create_invoice_cancellation_record(iid, self.bid, reason="Anulación legacy válida")
        before = self.state()
        with self.assertRaises(StateError):
            self.cancel.review(self.principal, saved, reason="Otro motivo válido")
        self.assertEqual(before, self.state())
        self.assertEqual(self.rows("invoice_fiscal_cancellation_coverage"), [])

    def test_second_distinct_operation_cannot_adopt_captured_cancellation(self):
        op, req, identity = self.prepared()
        second = self.cancel.prepare(self.principal, EntryIdentity.web_api(uuid4()), req)
        for candidate in (op, second):
            self.cancel.authorize(self.principal, candidate.operation_uuid, channel=identity.namespace,
                                  approved_hash=req.request_hash, approved_revision=req.expected_revision)
        self.cancel.execute(self.principal, op.operation_uuid)
        before = self.state()
        with self.assertRaises(StateError):
            self.cancel.execute(self.principal, second.operation_uuid)
        self.assertEqual(before, self.state())

    def test_rollback_at_all_precommit_points(self):
        op = self.authorized()
        base = self.state(include_operations=True)
        originals = (WriterConnection.execute, FinancialSession.execute, EconomicEvents.append, OperationsRepository.transition)
        for point in ("before_writer", "after_record", "after_outbox", "after_coverage", "after_event", "before_result"):
            def writer(conn, sql, params=()):
                result = originals[0](conn, sql, params)
                if (point == "after_record" and sql.startswith("INSERT INTO invoice_cancellation_records")
                        or point == "after_outbox" and sql.startswith("INSERT INTO verifactu_cancellation_outbox")):
                    raise RuntimeError(point)
                return result

            def execute(session, sql, params=()):
                result = originals[1](session, sql, params)
                if point == "after_coverage" and sql.startswith("INSERT INTO invoice_fiscal_cancellation_coverage"):
                    raise RuntimeError(point)
                return result

            def append(service, *args, **kwargs):
                result = originals[2](service, *args, **kwargs)
                if point == "after_event":
                    raise RuntimeError(point)
                return result

            def transition(repo, row, state, *args, **kwargs):
                if point == "before_result" and state == OperationState.COMMITTED:
                    raise RuntimeError(point)
                return originals[3](repo, row, state, *args, **kwargs)

            with self.subTest(point=point):
                with patch.object(WriterConnection, "execute", writer), patch.object(FinancialSession, "execute", execute), \
                        patch.object(EconomicEvents, "append", append), patch.object(OperationsRepository, "transition", transition):
                    if point == "before_writer":
                        with patch.object(invoices, "create_invoice_cancellation_record", side_effect=RuntimeError(point)), self.assertRaises(RuntimeError):
                            self.cancel.execute(self.principal, op.operation_uuid)
                    else:
                        with self.assertRaises(RuntimeError):
                            self.cancel.execute(self.principal, op.operation_uuid)
                self.assertEqual(base, self.state(include_operations=True))
                self.assertEqual(self.rows("invoice_cancellation_records"), [])
                self.assertEqual(self.cancel.operations.recover(self.principal, op.operation_uuid).state, OperationState.APPROVED)
        self.cancel.execute(self.principal, op.operation_uuid)

    def test_downgrade_retains_durable_evidence(self):
        op = self.authorized()
        self.cancel.execute(self.principal, op.operation_uuid)
        before = self.state()
        with self.assertRaises(ValueError):
            migrations.downgrade(75)
        self.assertEqual(migrations.current_version(), 76)
        self.assertEqual(before, self.state())

    def test_draft_and_historical_invoice_blocked(self):
        from noesis.financial_antecedents.contracts import AntecedentRef
        draft = self.draft()["id"]
        with db.get_conn() as conn:
            source = snapshot(conn, self.bid, "invoice", draft)
        saved = self.resolve(AntecedentRef("invoice", draft, source.revision), Purpose.FISCAL_CANCEL, persist=True)
        self.assertEqual(saved["result"]["outcome"], "blocked")
        with self.assertRaises(StateError):
            self.cancel.review(self.principal, saved, reason="Alta inválida")

    def test_reason_boundaries_and_decimal_context(self):
        from decimal import localcontext
        _, saved = self.fixture(lines=[{"description": "Precisión", "quantity": "1", "unit_price": "100.05", "vat_rate": 21}])
        for reason in ("12345", "x" * 1000):
            request = self.cancel.review(self.principal, saved, reason=reason)
            self.assertEqual(request.reason, reason)
        with localcontext() as context:
            context.prec = 2
            done = self.cancel.execute(self.principal, self.authorized(saved=saved).operation_uuid)
        self.assertEqual(done.result["original_total"], "121.06")

    def test_rectified_original_verified_total_is_only_evidence(self):
        original = self.captured()
        draft = db.create_rectifying_invoice(original.result["invoice_id"], self.bid, concept="Corrección",
                                            base="2.675", invoice_type="R1", reason="Precio incorrecto")
        done = self.capture.execute(self.principal, self.approve(draft["id"]).operation_uuid)
        with db.get_conn() as conn:
            conn.execute("UPDATE verifactu_outbox SET status='aceptado' WHERE business_id=? AND invoice_id=?",
                         (self.bid, draft["id"]))
        saved = self.resolve(self.event_ref(done.result["event_uuid"]), Purpose.FISCAL_CANCEL, persist=True)
        op = self.authorized(saved=saved)
        before = self.state(execution=True)
        result = self.cancel.execute(self.principal, op.operation_uuid)
        self.assertEqual(result.result["original_total"], "3.24")
        self.assertIsNone(result.result["amount"])
        self.assertEqual(before, self.state(execution=True))

    def test_negative_rectification_blocked_by_existing_b_payment_policy(self):
        original = self.captured()
        draft = db.create_rectifying_invoice(original.result["invoice_id"], self.bid, concept="Corrección",
                                            base="-2.675", invoice_type="R1", reason="Precio incorrecto")
        done = self.capture.execute(self.principal, self.approve(draft["id"]).operation_uuid)
        with db.get_conn() as conn:
            conn.execute("UPDATE verifactu_outbox SET status='aceptado' WHERE business_id=? AND invoice_id=?",
                         (self.bid, draft["id"]))
        saved = self.resolve(self.event_ref(done.result["event_uuid"]), Purpose.FISCAL_CANCEL, persist=True)
        self.assertEqual(saved["result"]["outcome"], "blocked")
        self.assertIn("PAYMENT_HISTORY_INCOMPLETE", saved["result"]["reasons"])
        before = self.state(include_operations=True)
        with self.assertRaises(StateError):
            self.cancel.review(self.principal, saved, reason="Alta inválida")
        self.assertEqual(before, self.state(include_operations=True))

    def test_fiscal_record_corruption_or_missing_blocks(self):
        for mode in ("corrupted",):
            iid, saved = self.fixture()
            with self.corruption("invoice_records", "verifactu_outbox") as conn:
                if mode == "corrupted":
                    conn.execute("UPDATE invoice_records SET record_hash=? WHERE business_id=? AND invoice_id=?",
                                 ("0" * 64, self.bid, iid))
                else:
                    conn.execute("DELETE FROM invoice_records WHERE business_id=? AND invoice_id=?", (self.bid, iid))
            with self.assertRaises((ConflictError, StateError)):
                self.cancel.review(self.principal, saved, reason="Alta inválida")

    def test_fiscal_record_missing_blocks(self):
        iid, saved = self.fixture()
        with self.corruption("invoice_records") as conn:
            conn.execute("DELETE FROM invoice_records WHERE business_id=? AND invoice_id=?", (self.bid, iid))
        with self.assertRaises((ConflictError, StateError)):
            self.cancel.review(self.principal, saved, reason="Alta inválida")

    def test_historical_invoice_v2_is_not_an_indirect_cancellation_path(self):
        _, saved = self.fixture()
        ref = self.event_ref(saved["result"]["event_uuid"])
        with self.corruption("economic_events") as conn:
            conn.execute("UPDATE economic_events SET origin='historical' WHERE business_id=? AND event_uuid=?",
                         (self.bid, ref.event_uuid))
        blocked = self.resolve(ref, Purpose.FISCAL_CANCEL, persist=True)
        self.assertEqual(blocked["result"]["outcome"], "blocked")
        self.assertIn("ANTECEDENT_UNSUPPORTED", blocked["result"]["reasons"])
        with self.assertRaises(StateError):
            self.cancel.review(self.principal, blocked, reason="Alta inválida")

    def test_real_durable_mandate_cannot_bypass_capture_or_sql(self):
        op, req, identity = self.prepared()
        from datetime import datetime, timedelta, timezone
        mandate = self.cancel.operations.grant_mandate(self.principal, req, channel=identity.namespace,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            revision_reader=lambda s, r: self.cancel._validate(s, r, self.principal))
        self.cancel.operations.authorize(self.principal, op.operation_uuid, channel=identity.namespace,
            approved_hash=req.request_hash, approved_revision=req.expected_revision,
            kind=AuthorizationKind.MANDATE, mandate_uuid=mandate,
            revision_reader=lambda s, r: self.cancel._validate(s, r, self.principal))
        before = self.state(include_operations=True)
        with self.assertRaises(StateError):
            self.cancel.authorize(self.principal, op.operation_uuid, channel=identity.namespace,
                approved_hash=req.request_hash, approved_revision=req.expected_revision)
        with self.assertRaises(StateError):
            self.cancel.execute(self.principal, op.operation_uuid)
        self.assertEqual(before, self.state(include_operations=True))

    def test_sql_payload_reason_total_date_and_exact_relation_rejected(self):
        from datetime import date, timedelta
        from noesis.economic_events.contracts import EventRelation, RelationType
        from noesis.economic_events.repository import EventsRepository
        first = self.captured()
        op = self.authorized()
        with db.get_conn() as conn:
            other = EconomicEvents(FinancialSession(conn), self.bid).read(self.principal, first.result["event_uuid"])
        actual = EventsRepository.insert
        before = self.state(include_operations=True)
        for mode in ("reason", "original_total", "registered_on", "relation"):
            def corrupt(repo, event, metadata):
                if event.event_type.value == "invoice.fiscal_cancellation_registered":
                    if mode == "relation":
                        event = replace(event, relations=(EventRelation(RelationType.EVIDENCE_FOR,
                            other.event.event_id, other.event.event_type, self.bid),))
                        # Cambia también el link preinsertado; solo fixture adversarial.
                        # Ese link es inmutable: se intercepta antes de incorporarlo debajo.
                    else:
                        value = {"reason": "Otro motivo válido", "original_total": "0.00",
                                 "registered_on": (date.today() - timedelta(days=1)).isoformat()}[mode]
                        event = replace(event, payload=dict(event.payload, **{mode: value}))
                return actual(repo, event, metadata)

            insert_link = EventsRepository.insert_link

            def link(repo, uid, relation, now):
                if mode == "relation":
                    relation = EventRelation(RelationType.EVIDENCE_FOR, other.event.event_id,
                                             other.event.event_type, self.bid)
                return insert_link(repo, uid, relation, now)

            with self.subTest(mode=mode), patch.object(EventsRepository, "insert", corrupt), \
                    patch.object(EventsRepository, "insert_link", link), self.assertRaises(Exception):
                self.cancel.execute(self.principal, op.operation_uuid)
            self.assertEqual(before, self.state(include_operations=True))

    def test_corrupted_chain_other_record_blocks(self):
        op = self.authorized()
        other = self.captured()
        with self.corruption("invoice_records") as conn:
            conn.execute("UPDATE invoice_records SET previous_hash=? WHERE business_id=? AND invoice_id=?",
                         ("0" * 64, self.bid, other.result["invoice_id"]))
        with self.assertRaises(StateError):
            self.cancel.execute(self.principal, op.operation_uuid)

    def test_missing_accepted_outbox_blocks(self):
        iid, saved = self.fixture()
        with db.get_conn() as conn:
            conn.execute("DELETE FROM verifactu_outbox WHERE business_id=? AND invoice_id=?", (self.bid, iid))
        with self.assertRaises(StateError):
            self.cancel.review(self.principal, saved, reason="Alta inválida")

    def test_wrong_event_binding_and_extra_request_fields_block(self):
        op, req, _ = self.prepared()
        other = self.captured()
        for params in (dict(req.parameters, invoice_event_uuid=other.result["event_uuid"]),
                       dict(req.parameters, extra="no"), dict(req.parameters, resolution_context_hash="0" * 64)):
            with self.assertRaises((StateError, ConflictError)):
                self.cancel.prepare(self.principal, EntryIdentity.web_api(uuid4()), replace(req, parameters=params))

    def test_forged_coverage_sql_every_structural_binding_rollback(self):
        op = self.authorized()
        before = self.state(include_operations=True)
        actual = FinancialSession.execute
        mutations = {
            "invoice_id": op.request.target_id + 100000,
            "cancellation_record_id": 100000, "operation_uuid": str(uuid4()),
            "antecedent_resolution_uuid": str(uuid4()), "original_invoice_event_uuid": str(uuid4()),
            "source_revision": 1, "source_fingerprint": "0" * 64,
            "resolution_context_hash": "0" * 64, "resolution_content_hash": "0" * 64,
            "event_uuid": str(uuid4()), "original_event_type": "invoice.rectified",
        }
        for key, value in mutations.items():
            def corrupt(session, sql, params=()):
                if sql.startswith("INSERT INTO invoice_fiscal_cancellation_coverage"):
                    columns = sql.split("(", 1)[1].split(")", 1)[0].split(",")
                    params = list(params)
                    params[columns.index(key)] = value
                return actual(session, sql, params)

            with self.subTest(key=key), patch.object(FinancialSession, "execute", corrupt), self.assertRaises(Exception):
                self.cancel.execute(self.principal, op.operation_uuid)
            self.assertEqual(before, self.state(include_operations=True))

    def test_forged_economic_event_sql_and_result_sql_block(self):
        import json
        from noesis.financial_operations.contracts import digest as operation_digest, canonical_json
        op = self.authorized()
        before = self.state(include_operations=True)
        actual = FinancialSession.execute
        for key, value in (("source_revision", 1), ("origin", "historical"), ("source_type", "invoice"),
                           ("amount", "121.00"), ("operation_uuid", str(uuid4())), ("event_slot", "other")):
            def corrupt(session, sql, params=()):
                if sql.startswith("INSERT INTO economic_events ("):
                    columns = sql.split("(", 1)[1].split(")", 1)[0].split(",")
                    params = list(params)
                    params[columns.index(key)] = value
                return actual(session, sql, params)

            with self.subTest(event=key), patch.object(FinancialSession, "execute", corrupt), self.assertRaises(Exception):
                self.cancel.execute(self.principal, op.operation_uuid)
            self.assertEqual(before, self.state(include_operations=True))
        transition = OperationsRepository.transition
        for key, value in (("event_uuid", str(uuid4())), ("cancellation_record_id", 999999),
                           ("original_total", "0.00"), ("source_revision", 1), ("amount", "121.00"),
                           ("captured", "true"), ("original_total", 121), ("omit_amount", True),
                           ("antecedent_resolution_uuid", str(uuid4())), ("extra", True)):
            def corrupt_result(repo, row, state, now, **kwargs):
                if state == OperationState.COMMITTED:
                    result = json.loads(kwargs["result"])
                    if key == "omit_amount":
                        result.pop("amount")
                        result["extra"] = None
                    else:
                        result[key] = value
                    kwargs["result"] = canonical_json(result)
                    kwargs["result_hash"] = operation_digest(kwargs["result"])
                return transition(repo, row, state, now, **kwargs)

            with self.subTest(result=key), patch.object(OperationsRepository, "transition", corrupt_result), self.assertRaises(Exception):
                self.cancel.execute(self.principal, op.operation_uuid)
            self.assertEqual(before, self.state(include_operations=True))

    def test_operation_cannot_commit_without_coverage_even_generic_executor(self):
        op = self.authorized()
        before = self.state(include_operations=True)
        with self.assertRaises(Exception):
            self.cancel.operations.execute(self.principal, op.operation_uuid, lambda *_: {"captured": True},
                revision_reader=lambda *_: op.request.expected_revision)
        self.assertEqual(before, self.state(include_operations=True))

    def test_coverage_update_and_delete_blocked(self):
        done = self.cancel.execute(self.principal, self.authorized().operation_uuid)
        for action in ("DELETE FROM invoice_fiscal_cancellation_coverage WHERE business_id=?",
                       "UPDATE invoice_fiscal_cancellation_coverage SET source_revision=1 WHERE business_id=?"):
            with self.assertRaises(Exception):
                with db.get_conn() as conn:
                    conn.execute(action, (self.bid,))
        self.assertEqual(self.cancel.execute(self.principal, done.operation_uuid), done)

    def test_provider_guard_actually_rejects_io_and_capture_never_calls(self):
        with self.assertRaisesRegex(AssertionError, "AEAT prohibida"):
            self.aeat([])
        self.aeat.reset_mock()
        self.cancel.execute(self.principal, self.authorized().operation_uuid)
        self.aeat.assert_not_called()

    def test_existing_a_evaluation_bytes_and_hashes_survive_migration76(self):
        from tests.financial_readiness_contract import ReadinessContract
        from noesis.financial_activation.capabilities import specification
        from noesis.financial_activation.contracts import Capability, Profile
        from noesis.financial_activation.evaluator import FinancialReadinessEvaluator
        with self.migration_scope():
            migrations.downgrade(75)
            self.cut()
            uid = uuid4()
            old_spec = replace(specification(Capability.FISCAL_CANCEL), implemented=False)
            with patch("noesis.financial_activation.capabilities.specification", return_value=old_spec):
                before = ReadinessContract.evaluate(self, Profile((Capability.INVOICE_ISSUE,)), uid)
            with db.get_conn() as conn:
                rows = conn.execute_exact("SELECT result_canonical,content_hash,context_hash FROM financial_readiness_evaluations WHERE business_id=?", (self.bid,)).fetchall()
            migrations.upgrade(76)
            with db.get_conn() as conn:
                after_rows = conn.execute_exact("SELECT result_canonical,content_hash,context_hash FROM financial_readiness_evaluations WHERE business_id=?", (self.bid,)).fetchall()
                read = FinancialReadinessEvaluator(FinancialSession(conn), self.bid).read(self.principal, uid)
            self.assertEqual(rows, after_rows)
            self.assertEqual(before, read)
            self.assertEqual(before, ReadinessContract.evaluate(self, Profile((Capability.INVOICE_ISSUE,)), uid))

    def test_readiness_producer_available_but_privacy_provider_still_block(self):
        from tests.financial_readiness_contract import ReadinessContract
        from noesis.financial_activation.contracts import Capability as C, Profile, Reason
        self.cut()
        result = ReadinessContract.evaluate(self, Profile((C.INVOICE_ISSUE,)))
        cancel = ReadinessContract.proof(self, result, C.FISCAL_CANCEL)
        aeat = ReadinessContract.proof(self, result, C.AEAT)
        self.assertNotIn(Reason.FISCAL_CAPABILITY_INCOMPLETE.value, cancel["reasons"])
        for reason in (Reason.PRIVACY_NOT_READY, Reason.EXPORT_NOT_READY):
            self.assertIn(reason.value, cancel["reasons"])
        self.assertIn(Reason.PROVIDER_PREFLIGHT_MISSING.value, aeat["reasons"])
        self.assertNotEqual(result["outcome"], "fully_eligible")
        control = self.rows("financial_activation_control")[0]
        self.assertEqual(control["state"], "off")
        self.assertEqual(control["activation_generation"], 0)
        self.assertFalse(control["ever_enabled"])

    def test_activation_states_generation_and_ever_enabled_still_forbidden(self):
        from tests.financial_readiness_contract import ReadinessContract
        ReadinessContract.evaluate(self)
        for value in ("ready", "enabled", "paused", "handed_off"):
            with self.assertRaises(Exception):
                with db.get_conn() as conn:
                    conn.execute("UPDATE financial_activation_control SET state=? WHERE business_id=?", (value, self.bid))
        for sql in ("activation_generation=1", "ever_enabled=TRUE"):
            with self.assertRaises(Exception):
                with db.get_conn() as conn:
                    conn.execute("UPDATE financial_activation_control SET " + sql + " WHERE business_id=?", (self.bid,))
