"""Misma batería de invariantes en SQLite y PostgreSQL; efectos sintéticos aislados."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from unittest.mock import patch
from uuid import uuid4

from noesis import db, migrations
from noesis.financial_operations.contracts import (
    AccessDenied, AuthorizationKind, CommandType, ConflictError, EntryIdentity, EntryNamespace,
    FinancialRequest, OperationState, Principal, StateError, canonical_json, strict_json,
)
from noesis.financial_operations.repository import OperationsRepository
from noesis.financial_operations.service import FinancialOperations


class OperationsContract:
    def seed(self):
        self.business = db.create_business("Contrato de operaciones", uuid4().hex + "@example.test")
        self.other_business = db.create_business("Otra empresa", uuid4().hex + "@example.test")
        self.user = db.create_user(uuid4().hex + "@example.test", "hash de fixture", self.business["id"])
        self.other_user = db.create_user(uuid4().hex + "@example.test", "hash de fixture", self.other_business["id"])
        self.colleague = db.create_user(uuid4().hex + "@example.test", "hash de fixture", self.business["id"])
        self.principal = Principal(self.user["id"], 0)
        self.other_principal = Principal(self.other_user["id"], 0)
        self.service = FinancialOperations(self.business["id"])
        self.other_service = FinancialOperations(self.other_business["id"])
        self.identity = EntryIdentity.web_api(uuid4())
        self.request = FinancialRequest(CommandType.EXPENSE_CONFIRM, None, Decimal("10.00"),
            date(2026, 10, 2), None, "Prueba explícita", {"category": "material", "vat_amount": Decimal("0.00")})
        with db.get_conn() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS phase12_test_effects "
                         "(effect_uuid TEXT PRIMARY KEY, business_id BIGINT NOT NULL, amount TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS phase12_test_resources "
                         "(business_id BIGINT NOT NULL, id BIGINT NOT NULL, revision INTEGER NOT NULL, "
                         "PRIMARY KEY(business_id, id))")
            conn.execute("INSERT INTO phase12_test_resources VALUES (?, 1, 1)", (self.business["id"],))

    def effect(self, session, request):
        session.execute("INSERT INTO phase12_test_effects VALUES (?, ?, ?)",
                        (str(uuid4()), self.business["id"], request.amount))
        return {"resource_id": 1, "amount": request.amount, "currency": "EUR"}

    def count_effects(self):
        with db.get_conn() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM phase12_test_effects WHERE business_id=?",
                                (self.business["id"],)).fetchone()["n"]

    def reserve(self, *, identity=None, request=None):
        return self.service.prepare(self.principal, identity or self.identity, request or self.request)

    def approved(self, *, request=None, identity=None, revision_reader=None):
        op = self.reserve(request=request, identity=identity)
        return self.service.authorize(self.principal, op.operation_uuid, channel=EntryNamespace.WEB_API,
            approved_hash=op.request.request_hash, approved_revision=op.request.expected_revision,
            revision_reader=revision_reader)

    def revision(self, session, request):
        row = session.execute("SELECT revision FROM phase12_test_resources WHERE business_id=? AND id=?",
                              (self.business["id"], request.target_id)).fetchone()
        return None if row is None else row["revision"]

    def test_account_deletion_preserves_durable_evidence_and_empty_accounts(self):
        op = self.reserve()
        with self.assertRaisesRegex(ValueError, "evidencia financiera durable"):
            db.delete_business_cascade(self.business["id"])
        self.assertEqual(self.service.recover(self.principal, op.operation_uuid).state,
                         OperationState.PREPARED)
        self.assertIsNotNone(db.get_user(self.user["id"]))
        self.other_service.grant_mandate(self.other_principal, self.request,
            channel=EntryNamespace.WEB_API, expires_at=datetime.now(timezone.utc)+timedelta(days=1))
        with self.assertRaisesRegex(ValueError, "evidencia financiera durable"):
            db.delete_business_cascade(self.other_business["id"])
        empty = db.create_business("Sin evidencia", uuid4().hex + "@example.test")
        self.assertTrue(db.delete_business_cascade(empty["id"]))
        self.assertIsNone(db.get_business(empty["id"]))

    def test_stable_identity_same_request(self):
        a, b = self.reserve(), self.reserve()
        self.assertEqual(a.operation_uuid, b.operation_uuid)
        self.assertEqual(a.request.request_hash, b.request.request_hash)
        self.assertEqual(a.state, OperationState.PREPARED)
        self.assertEqual(self.count_effects(), 0)

    def test_identity_conflict_never_mutates_original(self):
        op = self.reserve()
        with self.assertRaises(ConflictError):
            self.reserve(request=replace(self.request, amount="11"))
        recovered = self.service.recover(self.principal, op.operation_uuid)
        self.assertEqual(recovered.request.amount, Decimal("10.00"))
        self.assertEqual(recovered.state, OperationState.PREPARED)

    def test_equal_legitimate_operations_and_namespace_independence(self):
        a = self.approved()
        b = self.approved(identity=EntryIdentity.web_api(uuid4()))
        self.assertNotEqual(a.operation_uuid, b.operation_uuid)
        for op in (a, b):
            self.service.execute(self.principal, op.operation_uuid, self.effect)
        self.assertEqual(self.count_effects(), 2)
        different = self.reserve(identity=EntryIdentity(EntryNamespace.CHAT, self.identity.key))
        self.assertNotIn(different.operation_uuid, (a.operation_uuid, b.operation_uuid))

    def test_timeout_after_commit_returns_original_without_effect(self):
        op = self.approved()
        original = self.service.execute(self.principal, op.operation_uuid, self.effect)
        try:
            raise TimeoutError("Respuesta perdida después del commit real")
        except TimeoutError:
            recovered = self.reserve()
            replay = self.service.execute(self.principal, recovered.operation_uuid,
                lambda *_: self.fail("No ejecutar tras commit"))
        self.assertEqual(original.result, replay.result)
        self.assertEqual(replay.result_version, 1)
        self.assertEqual(self.count_effects(), 1)
        self.assertEqual(self.service.recover(self.principal, op.operation_uuid).state, OperationState.COMMITTED)

    def test_missing_authorization_cannot_execute(self):
        op = self.reserve()
        with self.assertRaises(StateError):
            self.service.execute(self.principal, op.operation_uuid, self.effect)
        self.assertEqual(self.count_effects(), 0)

    def test_approval_hash_and_revision_are_bound(self):
        request = replace(self.request, target_id=1, expected_revision=1)
        op = self.reserve(request=request)
        for hash_value, revision in (("a" * 64, 1), (request.request_hash, 2),
                                     (request.request_hash, True), (request.request_hash, 1.0),
                                     (request.request_hash, None)):
            with self.assertRaises(StateError):
                self.service.authorize(self.principal, op.operation_uuid, channel="web_api",
                    approved_hash=hash_value, approved_revision=revision, revision_reader=self.revision)
        with db.get_conn() as conn:
            conn.execute("UPDATE phase12_test_resources SET revision=2 WHERE business_id=?",
                         (self.business["id"],))
        with self.assertRaises(StateError):
            self.service.authorize(self.principal, op.operation_uuid, channel="web_api",
                approved_hash=request.request_hash, approved_revision=1, revision_reader=self.revision)
        self.assertEqual(self.service.recover(self.principal, op.operation_uuid).state, OperationState.PREPARED)
        with self.assertRaises(StateError):
            self.service.grant_mandate(self.principal, request, channel="web_api",
                expires_at=datetime.now(timezone.utc) + timedelta(days=1), revision_reader=self.revision)

    def test_revision_rechecked_before_effect(self):
        request = replace(self.request, target_id=1, expected_revision=1)
        with self.assertRaises(StateError):
            self.approved(request=request)
        op = self.approved(request=request, revision_reader=self.revision)
        with db.get_conn() as conn:
            conn.execute("UPDATE phase12_test_resources SET revision=2 WHERE business_id=?",
                         (self.business["id"],))
        with self.assertRaises(StateError):
            self.service.execute(self.principal, op.operation_uuid, self.effect, revision_reader=self.revision)
        self.assertEqual(self.count_effects(), 0)

    def test_authorization_survives_pending_proposal_deletion(self):
        db.set_pending_action(self.business["id"], "web:fixture", "reviewed_tool", {"tool": "fixture"})
        op = self.approved()
        db.clear_pending_action(self.business["id"], "web:fixture")
        with db.get_conn() as conn:
            row = conn.execute("SELECT * FROM financial_authorizations WHERE business_id=? AND authorization_uuid=?",
                               (self.business["id"], op.authorization_uuid)).fetchone()
        self.assertEqual(row["kind"], AuthorizationKind.HUMAN.value)
        self.assertEqual(row["actor_user_id"], self.principal.user_id)
        self.assertEqual(row["approved_request_hash"], op.request.request_hash)
        self.assertNotIn("conversation", row)
        self.service.execute(self.principal, op.operation_uuid, self.effect)

    def test_historical_unknown_never_invents_human_or_executes(self):
        op = self.reserve(identity=EntryIdentity.historical("expense", 1, 1))
        unknown = self.service.authorize(self.principal, op.operation_uuid, channel="historical",
            approved_hash=self.request.request_hash, approved_revision=None,
            kind=AuthorizationKind.HISTORICAL_UNKNOWN)
        self.assertEqual(unknown.state, OperationState.PREPARED)
        with db.get_conn() as conn:
            row = conn.execute("SELECT actor_user_id, actor_session_version, recorded_by FROM financial_authorizations "
                "WHERE business_id=? AND authorization_uuid=?", (self.business["id"], unknown.authorization_uuid)).fetchone()
        self.assertIsNone(row["actor_user_id"])
        self.assertIsNone(row["actor_session_version"])
        self.assertEqual(row["recorded_by"], self.principal.user_id)
        with self.assertRaises(StateError):
            self.service.execute(self.principal, op.operation_uuid, self.effect)
        self.service.finish_without_effect(self.principal, op.operation_uuid, OperationState.CANCELLED)

    def test_unknown_history_can_receive_new_explicit_approval(self):
        op = self.reserve()
        unknown = self.service.authorize(self.principal, op.operation_uuid, channel="historical",
            approved_hash=self.request.request_hash, approved_revision=None,
            kind=AuthorizationKind.HISTORICAL_UNKNOWN)
        human = self.approved()
        self.assertNotEqual(unknown.authorization_uuid, human.authorization_uuid)
        self.service.execute(self.principal, op.operation_uuid, self.effect)

    def test_mandate_exact_scope_and_revocation(self):
        mandate = self.service.grant_mandate(self.principal, self.request, channel="web_api",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1))
        op = self.reserve()
        approved = self.service.authorize(self.principal, op.operation_uuid, channel="recurring",
            approved_hash=self.request.request_hash, approved_revision=None,
            kind=AuthorizationKind.MANDATE, mandate_uuid=mandate)
        self.assertEqual(approved.state, OperationState.APPROVED)
        self.service.revoke_mandate(self.principal, mandate)
        with self.assertRaises(AccessDenied):
            self.service.execute(self.principal, op.operation_uuid, self.effect)
        self.assertEqual(self.count_effects(), 0)

    def test_mandate_expiry_missing_and_wrong_scope(self):
        with self.assertRaises(StateError):
            self.service.grant_mandate(self.principal, self.request, channel="web_api",
                expires_at=datetime.now(timezone.utc) - timedelta(days=1))
        mandate = self.service.grant_mandate(self.principal, self.request, channel="web_api",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=10))
        op = self.reserve(request=replace(self.request, amount="11"))
        for candidate in (None, str(uuid4()), mandate):
            with self.assertRaises(AccessDenied):
                self.service.authorize(self.principal, op.operation_uuid, channel="recurring",
                    approved_hash=op.request.request_hash, approved_revision=None,
                    kind=AuthorizationKind.MANDATE, mandate_uuid=candidate)
        expiry_op = self.reserve(identity=EntryIdentity.web_api(uuid4()))
        with patch("noesis.financial_operations.service._clock",
                   return_value=datetime.now(timezone.utc) + timedelta(days=1)):
            # No se ejecuta nada; el control de caducidad se prueba sobre mandato real.
            with self.assertRaises(AccessDenied):
                self.service.authorize(self.principal, expiry_op.operation_uuid, channel="recurring",
                    approved_hash=self.request.request_hash, approved_revision=None,
                    kind=AuthorizationKind.MANDATE, mandate_uuid=mandate)

    def test_revoked_user_or_session_cannot_recover_or_execute(self):
        op = self.approved()
        with self.assertRaises(AccessDenied):
            self.service.recover(Principal(self.principal.user_id, 1), op.operation_uuid)
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET is_active=FALSE WHERE id=?", (self.principal.user_id,))
        for callback in (lambda: self.service.recover(self.principal, op.operation_uuid),
                         lambda: self.service.execute(self.principal, op.operation_uuid, self.effect)):
            with self.assertRaises(AccessDenied):
                callback()
        self.assertEqual(self.count_effects(), 0)

    def test_subscription_revocation_preserves_read_only_recovery(self):
        op = self.approved()
        with db.get_conn() as conn:
            conn.execute("UPDATE businesses SET subscription_status='cancelled' WHERE id=?", (self.business["id"],))
        with self.assertRaises(AccessDenied):
            self.service.execute(self.principal, op.operation_uuid, self.effect)
        self.assertEqual(self.service.recover(self.principal, op.operation_uuid).state, OperationState.APPROVED)

    def test_business_and_owner_permissions_before_uuid_recovery(self):
        op = self.approved()
        for service, principal in ((self.service, self.other_principal),
                                   (self.other_service, self.other_principal),
                                   (self.service, Principal(self.colleague["id"], 0))):
            for callback in (lambda: service.recover(principal, op.operation_uuid),
                             lambda: service.execute(principal, op.operation_uuid, self.effect)):
                with self.assertRaises(AccessDenied):
                    callback()
        same_key = self.other_service.prepare(self.other_principal, self.identity, self.request)
        self.assertNotEqual(op.operation_uuid, same_key.operation_uuid)
        with self.assertRaises(AccessDenied):
            self.service.prepare(Principal(self.colleague["id"], 0), self.identity, self.request)

    def test_committed_replay_still_requires_current_identity_and_permissions(self):
        op = self.approved()
        self.service.execute(self.principal, op.operation_uuid, self.effect)
        with self.assertRaises(AccessDenied):
            self.service.recover(Principal(self.colleague["id"], 0), op.operation_uuid)
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET session_version=1 WHERE id=?", (self.principal.user_id,))
        with self.assertRaises(AccessDenied):
            self.reserve()
        with self.assertRaises(AccessDenied):
            self.service.recover(self.principal, op.operation_uuid)
        self.assertEqual(self.count_effects(), 1)

    def test_database_rejects_wrong_operation_authorization_and_false_commit(self):
        original = self.approved()
        second = self.reserve(identity=EntryIdentity.web_api(uuid4()))
        with self.assertRaises(db.DatabaseError):
            with db.get_conn() as conn:
                conn.execute("UPDATE financial_operations SET state='approved', authorization_uuid=? "
                    "WHERE business_id=? AND operation_uuid=?",
                    (original.authorization_uuid, self.business["id"], second.operation_uuid))
        with self.assertRaises(db.DatabaseError):
            with db.get_conn() as conn:
                conn.execute("UPDATE financial_operations SET state='committed' "
                    "WHERE business_id=? AND operation_uuid=?", (self.business["id"], original.operation_uuid))
        self.assertEqual(self.service.recover(self.principal, original.operation_uuid).state, OperationState.APPROVED)
        self.assertEqual(self.service.recover(self.principal, second.operation_uuid).state, OperationState.PREPARED)
        for bad_uuid in ("bad", "00000000-0000-0000-0000-000000000000"):
            with self.subTest(uuid=bad_uuid), self.assertRaises(db.DatabaseError):
                with db.get_conn() as conn:
                    conn.execute("INSERT INTO financial_operations (business_id, operation_uuid, entry_namespace, "
                        "entry_key, created_by, command_type, command_version, request_canonical, request_hash, "
                        "expected_revision, state, created_at, updated_at) SELECT business_id, ?, entry_namespace, "
                        "?, created_by, command_type, command_version, request_canonical, request_hash, "
                        "expected_revision, 'prepared', created_at, updated_at FROM financial_operations "
                        "WHERE business_id=? AND operation_uuid=?",
                        (bad_uuid, EntryIdentity.web_api(uuid4()).key, self.business["id"], second.operation_uuid))

    def test_other_business_authorization_cannot_be_attached(self):
        mandate = self.other_service.grant_mandate(self.other_principal, self.request, channel="web_api",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1))
        op = self.reserve()
        with self.assertRaises(AccessDenied):
            self.service.authorize(self.principal, op.operation_uuid, channel="recurring",
                approved_hash=self.request.request_hash, approved_revision=None,
                kind=AuthorizationKind.MANDATE, mandate_uuid=mandate)
        with self.assertRaises(db.DatabaseError):
            with db.get_conn() as conn:
                conn.execute("UPDATE financial_operations SET state='approved', authorization_uuid=? "
                    "WHERE business_id=? AND operation_uuid=?", (mandate, self.business["id"], op.operation_uuid))

    def test_failure_before_or_after_effect_never_commits(self):
        op = self.approved()
        def before(*_):
            raise RuntimeError("Antes del efecto")
        def after(session, request):
            self.effect(session, request)
            raise RuntimeError("Después del efecto, antes del resultado")
        for executor in (before, after):
            with self.assertRaises(RuntimeError):
                self.service.execute(self.principal, op.operation_uuid, executor)
            self.assertEqual(self.count_effects(), 0)
            self.assertEqual(self.service.recover(self.principal, op.operation_uuid).state, OperationState.APPROVED)

    def test_result_storage_failure_rolls_back_effect(self):
        op = self.approved()
        def failed_storage(repository, row, state, now, **kwargs):
            repository.session.execute("INSERT INTO phase12_test_effects VALUES ('collision', ?, '1.00')",
                                       (self.business["id"],))
        with db.get_conn() as conn:
            conn.execute("INSERT INTO phase12_test_effects VALUES ('collision', ?, '1.00')", (self.business["id"],))
        with patch.object(OperationsRepository, "transition", failed_storage):
            with self.assertRaises(db.DatabaseError):
                self.service.execute(self.principal, op.operation_uuid, self.effect)
        self.assertEqual(self.count_effects(), 1)  # Solo la fila previa, no el nuevo efecto.
        recovered = self.service.recover(self.principal, op.operation_uuid)
        self.assertEqual(recovered.state, OperationState.APPROVED)
        self.assertIsNone(recovered.result)

    def test_float_result_rolls_back_and_decimal_result_is_exact(self):
        op = self.approved()
        def invalid(session, request):
            self.effect(session, request)
            return {"amount": 0.1}
        with self.assertRaises(TypeError):
            self.service.execute(self.principal, op.operation_uuid, invalid)
        self.assertEqual(self.count_effects(), 0)
        self.assertEqual(self.service.execute(self.principal, op.operation_uuid, self.effect).result["amount"], "10.00")

    def test_terminal_states_and_immutable_evidence(self):
        for state in (OperationState.REJECTED, OperationState.CANCELLED):
            op = self.reserve(identity=EntryIdentity.web_api(uuid4()))
            self.service.finish_without_effect(self.principal, op.operation_uuid, state)
            self.assertEqual(self.service.finish_without_effect(self.principal, op.operation_uuid, state).state, state)
            with self.assertRaises(StateError):
                self.service.execute(self.principal, op.operation_uuid, self.effect)
        op = self.approved()
        self.service.execute(self.principal, op.operation_uuid, self.effect)
        for sql, args in (
            ("UPDATE financial_operations SET request_hash=? WHERE business_id=? AND operation_uuid=?",
             ("b" * 64, self.business["id"], op.operation_uuid)),
            ("DELETE FROM financial_operations WHERE business_id=? AND operation_uuid=?", (self.business["id"], op.operation_uuid)),
            ("UPDATE financial_authorizations SET approved_request_hash=? WHERE business_id=? AND authorization_uuid=?",
             ("c" * 64, self.business["id"], op.authorization_uuid)),
            ("DELETE FROM financial_authorizations WHERE business_id=? AND authorization_uuid=?", (self.business["id"], op.authorization_uuid)),
        ):
            with self.subTest(sql=sql), self.assertRaises(db.DatabaseError):
                with db.get_conn() as conn:
                    conn.execute(sql, args)

    def test_downgrade_refuses_loss_and_excluded_tables_absent(self):
        self.reserve()
        with self.assertRaises(ValueError):
            migrations.downgrade(61)
        self.assertEqual(migrations.current_version(), migrations.LATEST_VERSION)
        with db.get_conn() as conn:
            if conn.dialect == "sqlite":
                names = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            else:
                names = [r["name"] for r in conn.execute("SELECT table_name AS name FROM information_schema.tables "
                                                        "WHERE table_schema=current_schema()").fetchall()]
        self.assertIn("financial_operations", names)
        self.assertIn("financial_authorizations", names)
        if migrations.LATEST_VERSION >= 63:
            self.assertIn("economic_events", names)
            self.assertIn("economic_event_links", names)
        self.assertFalse({"journal_entries", "journal_lines", "open_items", "tax_ledger"} & set(names))

    def test_canonical_order_relevant_changes_and_float_rejection(self):
        reordered = replace(self.request, parameters=dict(reversed(list(self.request.parameters.items()))))
        self.assertEqual(self.request.request_hash, reordered.request_hash)
        for kwargs in ({"amount": "11"}, {"target_id": 2}, {"effective_on": "2026-10-03"},
                       {"reason": "Otro"}, {"parameters": {"category": "otro"}},
                       {"target_id": 1, "expected_revision": 2}):
            self.assertNotEqual(self.request.request_hash, replace(self.request, **kwargs).request_hash)
        for kwargs in ({"amount": 0.1}, {"amount": "1.001"}, {"parameters": {"nested": [0.1]}},
                       {"currency": "USD"}, {"command_version": True}, {"command_type": "quote.accepted"}):
            with self.subTest(kwargs=kwargs), self.assertRaises((TypeError, ValueError)):
                replace(self.request, **kwargs)
        self.assertEqual(json.loads(self.request.canonical())["amount"], "10.00")
        self.assertEqual(FinancialRequest.from_canonical(self.request.canonical()).request_hash, self.request.request_hash)

    def test_identity_and_authority_cannot_come_from_request(self):
        for key in ("operation_uuid", "entry_key", "idempotency_key", "business_id", "approved_by_ai"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                replace(self.request, parameters={"nested": {key: "arbitrario"}})
        for callback in (lambda: FinancialOperations(0), lambda: Principal(0, 0),
                         lambda: EntryIdentity.web_api("bad"), lambda: EntryIdentity.web_api("00000000-0000-0000-0000-000000000000")):
            with self.assertRaises(ValueError):
                callback()
        with self.assertRaises(AccessDenied):
            self.service.prepare({"user_id": self.user["id"]}, self.identity, self.request)

    def test_all_entry_factories_are_stable(self):
        stable = uuid4()
        factories = [lambda: EntryIdentity.web_api(stable), lambda: EntryIdentity.chat(stable, 1),
            lambda: EntryIdentity.whatsapp("wamid.server.1"), lambda: EntryIdentity.document_review(1, 1),
            lambda: EntryIdentity.recurring(1, date(2026, 10, 2)), lambda: EntryIdentity.imported(stable, "row1"),
            lambda: EntryIdentity.historical("expense", 1, 1)]
        self.assertEqual(len({fn().namespace for fn in factories}), 7)
        for factory in factories:
            self.assertEqual(factory(), factory())

    def test_defaults_are_frozen_and_json_decoder_is_strict(self):
        op = self.reserve()
        with self.assertRaises(ConflictError):
            self.reserve(request=replace(self.request, effective_on="2026-11-01"))
        self.assertEqual(self.service.recover(self.principal, op.operation_uuid).request.effective_on, "2026-10-02")
        for text in ('{"amount":0.1}', '{"a":1,"a":2}', '{"a":NaN}'):
            with self.assertRaises(ValueError):
                strict_json(text)
        with self.assertRaises(TypeError):
            op.request.parameters["category"] = "mutable"
        self.assertEqual(canonical_json({"a": "á"}), '{"a":"á"}')
