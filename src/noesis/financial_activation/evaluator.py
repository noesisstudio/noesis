"""SELECT de evidencia y writes únicamente readiness. Sin routing ni providers."""

from datetime import datetime, timedelta, timezone
import hashlib

from noesis import config, db, migrations
from noesis.core.locks import lock_business
from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import (
    AccessDenied,
    ConflictError,
    Principal,
    StateError,
    uuid_text,
)
from noesis.financial_history.readers import RawReader
from noesis.financial_history.sources import SOURCES
from noesis.financial_history.repository import hash_source
from noesis.financial_history.reconciliation_verifier import ReconciliationVerifier, storage_hash
from noesis.financial_history.reconciliation_repository import ReconciliationRepository
from noesis.financial_history.reconciliation_contracts import (
    digest as reconciliation_digest,
    result_value,
)
from noesis.financial_history.importer import HistoryImporter
from noesis.financial_history.cutoff import label
from noesis.financial_history.service import FLAGS
from .contracts import (
    Capability as C,
    CapabilityResult as CR,
    FINANCIAL,
    HistoryContext,
    Outcome,
    Permission,
    Policy,
    Profile,
    Reason as R,
    SCHEMAS,
    capability_proof,
    digest,
    instant,
    tenant,
)
from .repository import ReadinessRepository
from .schema import CONTROL


class FinancialReadinessEvaluator:
    """API interna con FinancialSession prestada; no concede activación."""

    def __init__(self, session, business_id):
        if not isinstance(session, FinancialSession):
            raise TypeError("FinancialSession prestada requerida.")
        self.s, self.bid = session, tenant(business_id)
        self.repo = ReadinessRepository(session, self.bid)

    def _permission(self, principal, *, locking=False, activation_verification=False):
        if not isinstance(principal, Principal):
            raise AccessDenied(R.PERMISSION_DENIED.value)
        suffix = " FOR SHARE" if locking and self.s.dialect == "postgres" else ""
        user = self.s.execute(
            "SELECT id,is_active,session_version FROM users WHERE business_id=? AND id=?" + suffix,
            (self.bid, principal.user_id),
        ).fetchone()
        business = self.s.execute(
            "SELECT id,subscription_status,trial_ends_at,is_demo,verifactu_enabled,name,nif,address FROM businesses WHERE id=?"
            + suffix,
            (self.bid,),
        ).fetchone()
        if (
            not user
            or not user["is_active"]
            or user["session_version"] != principal.session_version
            or not business
        ):
            raise AccessDenied(R.PERMISSION_DENIED.value)
        check = dict(business)
        if hasattr(check["trial_ends_at"], "isoformat"):
            check["trial_ends_at"] = check["trial_ends_at"].isoformat()
        flags = tuple(f for f in FLAGS if not activation_verification or f != "FINANCIAL_CORE_ENABLED")
        if not db.subscription_allows_access(check) or any(getattr(config, f) for f in flags):
            raise AccessDenied(R.PERMISSION_DENIED.value)
        # Permiso específico: el usuario autenticado de cuenta escribible puede evaluar.
        # No se infiere financial.authorize ni historical.record de esta decisión.
        return business

    def _sources(self):
        reader = RawReader(self.s, self.bid, page_size=64, cut_scope=True)
        h = hashlib.sha256(b"readiness-scope-v1")
        relevant, invoices, related, document_refs, counts = [], set(), [], [], {}
        source_ids = {k: set() for k in ("invoice", "expense", "received_invoice")}
        primary = {
            "invoice_payment",
            "bank_transaction",
            "received_invoice",
            "expense",
            "invoice_record",
            "invoice_cancellation_record",
            "bank_payment_link",
            "economic_event",
            "economic_event_link",
        }
        for kind in sorted(SOURCES):
            after, count = None, 0
            while True:
                page = reader.page(kind, after)
                if not page:
                    break
                for raw in page:
                    hash_source(h, raw)
                    count += 1
                    if kind in source_ids:
                        source_ids[kind].add(int(raw.source_id))
                    if kind == "invoice":
                        invoices.add(int(raw.source_id))
                        if raw.fields["status"] != "borrador":
                            relevant.append(kind)
                    elif kind in primary:
                        relevant.append(kind)
                    elif kind == "invoice_line":
                        related.append(raw.fields["invoice_id"])
                    elif kind == "document":
                        document_refs += [
                            (k, raw.fields[field])
                            for k, field in (
                                ("invoice", "invoice_id"),
                                ("expense", "expense_id"),
                                ("received_invoice", "received_invoice_id"),
                            )
                            if raw.fields[field] is not None
                        ]
                    elif kind == "invoice_event" and raw.fields["event_type"] in (
                        "emision",
                        "rectificacion",
                        "anulacion",
                    ):
                        relevant.append(kind)
                    elif kind in ("verifactu_transport", "cancellation_transport"):
                        relevant.append(kind)
                    elif kind == "recurring_run" and (
                        raw.fields["invoice_id"] is not None
                        or raw.fields["status"] not in ("draft", "completed")
                    ):
                        relevant.append(kind)
                after = page[-1].key
            counts[kind] = count
        if any(i not in invoices for i in related):
            relevant.append("unexplained_invoice_line")
        if any(value not in source_ids[kind] for kind, value in document_refs):
            relevant.append("unexplained_document_reference")
        # Fuentes relacionadas fuera del scope C: nunca acreditar vacío ocultando pendientes.
        extra = {}
        for table in (
            "financial_operations",
            "financial_authorizations",
            "whatsapp_outbox",
            "email_outbox",
        ):
            rows = self.s.borrowed_connection.execute_exact(
                "SELECT * FROM " + table + " WHERE business_id=?", (self.bid,)
            ).fetchall()
            extra[table] = sorted(storage_hash(r) for r in rows)
            if table == "financial_operations" and any(
                r["state"] in ("prepared", "approved") and r["entry_namespace"] != "historical"
                for r in rows
            ):
                relevant.append("pending_live_operation")
            elif table.endswith("outbox") and any(
                r.get("status") not in ("sent", "delivered", "cancelled", "failed") for r in rows
            ):
                relevant.append("uncertain_dispatch")
        return dict(
            source_hash=h.hexdigest(),
            counts=counts,
            related_hash=digest(extra),
            empty=not relevant,
            economic_kinds=sorted(set(relevant)),
        )

    def _configuration(self, business):
        from .configuration_snapshot import PRODUCER_FIELDS
        producer = PRODUCER_FIELDS
        # Solo huellas, sin certificados, tokens ni contenido personal en evidencia.
        fields = dict(
            business_hash=storage_hash(business),
            producer_hash=digest({name: getattr(config, name, "") for name in producer}),
        )
        for table in ("invoice_series", "recurring_invoices"):
            rows = self.s.borrowed_connection.execute_exact(
                "SELECT * FROM " + table + " WHERE business_id=?", (self.bid,)
            ).fetchall()
            fields[table] = sorted(storage_hash(r) for r in rows)
        return digest(fields)

    def _history(self, reference):
        reasons, proof = set(), {}
        if reference is None:
            return proof, {R.RECONCILIATION_MISSING}
        if not isinstance(reference, HistoryContext):
            raise TypeError("Contexto histórico cerrado requerido.")
        proof.update(reference.value())
        # Una referencia ajena nunca revela filas ni se convierte en evidencia local.
        for table, key, value in (
            ("financial_history_epochs", "epoch_uuid", reference.epoch_uuid),
            ("financial_history_cut_manifests", "manifest_uuid", reference.manifest_uuid),
            ("financial_history_import_batches", "batch_uuid", reference.batch_uuid),
        ):
            if not self.s.execute(
                "SELECT 1 FROM " + table + " WHERE business_id=? AND " + key + "=?",
                (self.bid, value),
            ).fetchone():
                raise AccessDenied(R.PERMISSION_DENIED.value)
        rec = self.s.execute(
            "SELECT * FROM financial_history_reconciliations WHERE business_id=? AND reconciliation_uuid=?",
            (self.bid, reference.reconciliation_uuid),
        ).fetchone()
        if not rec:
            return proof, {R.RECONCILIATION_MISSING}
        proof.update(
            generation=rec["generation"], plan_hash=rec["plan_hash"], result_hash=rec["result_hash"]
        )
        if (
            str(rec["epoch_uuid"]) != reference.epoch_uuid
            or str(rec["manifest_uuid"]) != reference.manifest_uuid
            or str(rec["batch_uuid"]) != reference.batch_uuid
        ):
            return proof, {R.CONTEXT_CHANGED, R.BOUNDARY_INVALID}
        pending = self.s.execute(
            "SELECT 1 FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND (classification IN ('C','D') OR disposition='pending_incidence' OR unresolved_dependency_canonical<>'[]') LIMIT 1",
            (self.bid, reference.manifest_uuid),
        ).fetchone()
        if pending:
            reasons.add(R.HISTORY_PENDING)
        if rec["result"] != "PASS":
            reasons.add(R.RECONCILIATION_BLOCKED)
        try:
            repository = ReconciliationRepository(self.s, self.bid, reference.reconciliation_uuid)
            repository.result()
            batch, cut, base = HistoryImporter(self.bid)._batch(self.s, reference.batch_uuid)
            if (
                batch["state"] not in ("completed", "partial", "blocked")
                or str(cut["epoch_uuid"]) != reference.epoch_uuid
                or str(batch["manifest_uuid"]) != reference.manifest_uuid
            ):
                reasons.add(R.BOUNDARY_INVALID)
            verifier = ReconciliationVerifier(
                self.s, self.bid, batch, base, None, lambda _: None, 64
            )
            hashes = verifier.run()
            current = result_value(
                dict(rec, **hashes, result="BLOCKED" if verifier.findings else "PASS")
            )
            proof["rechecked_hash"] = reconciliation_digest(current)
            if proof["rechecked_hash"] != rec["result_hash"]:
                reasons.add(R.SOURCE_DRIFT)
            if verifier.findings:
                reasons.add(R.HISTORY_PENDING)
        except (ValueError, TypeError, KeyError, StateError):
            reasons.add(R.BOUNDARY_INVALID)
        return proof, reasons

    def evaluate(
        self,
        principal,
        evaluation_uuid,
        profile,
        *,
        history=None,
        policy=Policy(),
        code_version,
        now=None,
        permission=Permission.EVALUATE,
    ):
        if permission != Permission.EVALUATE:
            raise AccessDenied(R.PERMISSION_DENIED.value)
        if not isinstance(profile, Profile) or not isinstance(policy, Policy):
            raise TypeError("Perfil y política cerrados requeridos.")
        uid, code_version = uuid_text(evaluation_uuid), label(code_version)
        now = now or datetime.now(timezone.utc)
        instant(now)
        if self.s.dialect == "sqlite" and not self.s.borrowed_connection.raw.in_transaction:
            raise StateError("Transacción exterior requerida.")
        self._permission(principal)
        lock_business(self.s, self.bid)
        business = self._permission(principal, locking=True)
        if migrations.current_version_connection(self.s.borrowed_connection) not in SCHEMAS:
            raise StateError("Esquema readiness incompatible; matriz explícita requerida.")
        control = self.s.execute(
            "SELECT state,activation_generation,ever_enabled FROM "
            + CONTROL
            + " WHERE business_id=?",
            (self.bid,),
        ).fetchone()
        control = (
            dict(control)
            if control
            else dict(state="off", activation_generation=0, ever_enabled=False)
        )
        control["ever_enabled"] = bool(control["ever_enabled"])
        sources = self._sources()
        history_proof, global_reasons = self._history(history)
        if (
            control["state"] not in ("off", "validating")
            or control["ever_enabled"]
            or control["activation_generation"] != 0
        ):
            global_reasons.add(R.CONTROL_INVALID)
        if not sources["empty"] and history is None:
            global_reasons.add(R.HISTORY_PENDING)
        if (
            "pending_live_operation" in sources["economic_kinds"]
            or "uncertain_dispatch" in sources["economic_kinds"]
        ):
            global_reasons.add(R.HISTORY_PENDING)
        items = sum(v for k, v in sources["counts"].items() if k != "scope_anchor")
        if history is not None:
            items = self.s.execute(
                "SELECT COUNT(*) AS n FROM financial_history_items WHERE business_id=? AND manifest_uuid=?",
                (self.bid, history.manifest_uuid),
            ).fetchone()["n"]
        if items > policy.max_items:
            global_reasons.add(R.VOLUME_OUTSIDE_POLICY)
        fiscal = bool(business["verifactu_enabled"])
        needed, edges = profile.closure(fiscal_cancel_required=fiscal)
        context = dict(
            schema_version=74,
            code_version=code_version,
            policy=policy.value(),
            control=control,
            principal=dict(
                user_id=principal.user_id,
                session_version=principal.session_version,
                permission=Permission.EVALUATE.value,
            ),
            history=history_proof,
            configuration_hash=self._configuration(business),
            verifactu_enabled=fiscal,
            dependencies=edges,
            **sources,
        )
        existing = self.repo.load(uid)
        if existing:
            if existing["profile_hash"] != profile.content_hash or existing[
                "context_hash"
            ] != digest(context):
                raise ConflictError(R.CONTEXT_CHANGED.value)
            return self.repo.result(existing)
        results, reasons = {}, {}
        for c in needed:
            r = set(global_reasons)
            if c in FINANCIAL:
                r.update((R.PRIVACY_NOT_READY, R.EXPORT_NOT_READY))
            if c in (C.WHATSAPP, C.EMAIL) or c == C.AEAT and fiscal:
                r.add(R.PROVIDER_PREFLIGHT_MISSING)
            from .capabilities import specification
            if c == C.FISCAL_CANCEL and not specification(c).implemented:
                r.add(R.FISCAL_CAPABILITY_INCOMPLETE)
            if c in (C.BANK_IMPORT, C.BANK_MATCH):
                r.add(R.BANK_EVIDENCE_UNVALIDATED)
            if (
                c
                in (
                    C.CUSTOMER_PAYMENT_RECORD,
                    C.INVOICE_RECTIFY,
                    C.SUPPLIER_INVOICE_CORRECT,
                    C.SUPPLIER_INVOICE_VOID,
                    C.EXPENSE_VOID,
                )
                and not sources["empty"]
            ):
                r.add(R.CONTINUITY_NOT_IMPLEMENTED)
            if (
                c in (C.INVOICE_ISSUE, C.INVOICE_RECTIFY, C.CUSTOMER_PAYMENT_RECORD)
                and sources["counts"]["invoice"]
                and "invoice" in sources["economic_kinds"]
            ):
                r.add(R.UNSUPPORTED_HISTORICAL_INVOICE)
            results[c] = (
                CR.BLOCKED
                if r
                else CR.NOT_APPLICABLE
                if c == C.AEAT and not fiscal
                else CR.ELIGIBLE
            )
            reasons[c] = r or (
                {R.FISCAL_PROVIDER_NOT_APPLICABLE} if results[c] == CR.NOT_APPLICABLE else set()
            )
        changed = True
        while changed:
            changed = False
            for c in needed:
                if any(results[C(d)] == CR.BLOCKED for d in edges[c.value]):
                    reasons[c].add(R.CAPABILITY_DEPENDENCY_BLOCKED)
                    if c == C.INVOICE_ISSUE and fiscal and results[C.FISCAL_CANCEL] == CR.BLOCKED:
                        reasons[c].add(R.FISCAL_CAPABILITY_INCOMPLETE)
                    if results[c] != CR.BLOCKED:
                        results[c] = CR.BLOCKED
                        changed = True
        proofs = []
        for c in sorted(C, key=lambda c: c.value):
            evidence = dict(
                configuration_hash=context["configuration_hash"], verifactu_enabled=fiscal
            )
            dependencies = {d: results[C(d)].value for d in edges.get(c.value, ())}
            proofs.append(
                capability_proof(
                    c, results.get(c, CR.NOT_REQUESTED), reasons.get(c, ()), dependencies, evidence
                )
            )
        if global_reasons or all(results[c] == CR.BLOCKED for c in needed):
            outcome = Outcome.BLOCKED
        elif any(results[c] == CR.BLOCKED for c in needed):
            outcome = Outcome.PARTIAL
        else:
            outcome = Outcome.FULL
        body = dict(
            evaluation_version=1,
            profile=profile.value(),
            context=context,
            capabilities=proofs,
            outcome=outcome.value,
            reasons=sorted(r.value for r in global_reasons),
        )
        self._permission(principal, locking=True)
        return self.repo.store(
            principal,
            uid,
            profile,
            policy,
            code_version,
            context,
            body,
            instant(now),
            instant(now + timedelta(seconds=policy.ttl_seconds)),
        )

    def read(self, principal, evaluation_uuid):
        self._permission(principal)
        row = self.repo.load(uuid_text(evaluation_uuid))
        if not row or row["created_by"] != principal.user_id:
            raise AccessDenied(R.PERMISSION_DENIED.value)
        return self.repo.result(row)
