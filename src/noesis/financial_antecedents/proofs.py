"""Pruebas SELECT reutilizadas por el resolver. Ningún productor ni autoridad."""

from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import struct

from noesis import migrations
from noesis.economic_events.persistence import StoredEvent
from noesis.financial_operations.contracts import Operation, StateError, strict_json
from noesis.financial_history.classifier import revision
from noesis.financial_history.import_contracts import candidate
from noesis.financial_history.readers import RawReader, RawSource
from noesis.financial_history.reconciliation_repository import ReconciliationRepository
from noesis.financial_history.reconciliation_verifier import ReconciliationVerifier, storage_hash
from .contracts import Reason as R, digest

TABLES = {
    "invoice": "invoices",
    "invoice_payment": "invoice_payments",
    "received_invoice": "received_invoices",
    "expense": "expenses",
    "bank_transaction": "bank_transactions",
    "cancellation_record": "invoice_cancellation_records",
}
COVERAGES = {
    "invoice": "invoice_economic_coverage",
    "invoice_payment": "payment_economic_coverage",
    "received_invoice": "supplier_invoice_economic_coverage",
    "expense": "expense_economic_coverage",
    "bank_transaction": "bank_import_coverage",
}
ERRORS = (ValueError, TypeError, KeyError, ArithmeticError, StateError)


def matches_projection(physical, exact):
    """Contraste de almacenamiento contra evidencia YA exacta, nunca inferencia."""
    if isinstance(physical, float):
        return isinstance(exact, Decimal) and struct.pack(">d", physical) == struct.pack(
            ">d", float(exact)
        )
    if isinstance(physical, (date, datetime)):
        return physical.isoformat() == exact
    return physical == exact


class InvalidProof(ValueError):
    def __init__(self, reason):
        self.reason = R(reason)
        super().__init__(self.reason.value)


def require(condition, reason):
    if not condition:
        raise InvalidProof(reason)


def physical_identity(session, bid, kind, row):
    """Compatibilidad de huellas 1.4; representación binaria NO es importe exacto.

    Solo comprueba identidad física. Money procede exclusivamente del EE y su
    request/evidencia acreditados. Nunca convierte float en Decimal/Money.
    """
    values = dict(row)
    if kind == "invoice":
        values = {k: row.get(k) for k in migrations._IMMUTABLE_INVOICE_FIELDS}
        values["lines"] = session.borrowed_connection.execute_exact(
            "SELECT * FROM invoice_lines WHERE business_id=? AND invoice_id=? ORDER BY position,id",
            (bid, row["id"]),
        ).fetchall()
        values["identity"] = [bid, row["id"]]

    def representation(v):
        if isinstance(v, dict):
            return {k: representation(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [representation(x) for x in v]
        if isinstance(v, float):
            # Compatibilidad textual de huella, sin usarlo en aritmética.
            return repr(v)
        if isinstance(v, Decimal):
            return format(v, "f")
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return v

    fingerprint = hashlib.sha256(
        json.dumps(
            representation(values), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    rev = (
        row["_financial_revision"]
        if kind in ("expense", "received_invoice", "bank_transaction")
        else int(fingerprint[:15], 16) + 1
    )
    return rev, fingerprint


class ProofChecker:
    def __init__(self, session, bid):
        self.s, self.bid = session, bid
        self.cache, self.visiting = {}, set()

    def rows(self, table, field, value):
        return self.s.borrowed_connection.execute_exact(
            f"SELECT * FROM {table} WHERE business_id=? AND {field}=?", (self.bid, value)
        ).fetchall()

    def event(self, uid):
        rows = self.rows("economic_events", "event_uuid", uid)
        require(len(rows) == 1, R.DEPENDENCY_INVALID)
        return self.check(rows[0])

    def check(self, row):
        uid = str(row["event_uuid"])
        if uid in self.cache:
            return self.cache[uid]
        require(uid not in self.visiting and len(self.visiting) < 64, R.DEPENDENCY_INVALID)
        self.visiting.add(uid)
        try:
            try:
                stored = StoredEvent.from_row(row)
            except ERRORS as exc:
                raise InvalidProof(R.EVENT_INVALID) from exc
            e = stored.event
            require(e.business_id == self.bid, R.EVENT_INVALID)
            links = self.rows("economic_event_links", "event_uuid", uid)
            actual = {(r["relation_type"], str(r["target_event_uuid"])) for r in links}
            expected = {(r.kind.value, str(r.target_event_id)) for r in e.relations}
            require(len(links) == len(expected) and actual == expected, R.DEPENDENCY_INVALID)
            deps = []
            for rel in e.relations:
                parent = self.event(str(rel.target_event_id))
                require(
                    parent["stored"].event.event_type == rel.target_event_type
                    and rel.business_id == self.bid,
                    R.DEPENDENCY_INVALID,
                )
                require(parent["quality"] == "verified_fact", R.DEPENDENCY_INVALID)
                pe = parent["stored"].event
                if rel.kind.value in ("corrects", "voids"):
                    require(
                        pe.source_type == e.source_type
                        and pe.source_id == e.source_id
                        and pe.source_revision + 1 == e.source_revision,
                        R.DEPENDENCY_INVALID,
                    )
                elif rel.kind.value == "settles":
                    require(
                        pe.source_type.value == "invoice"
                        and pe.source_id == e.payload["invoice_id"],
                        R.DEPENDENCY_INVALID,
                    )
                elif rel.kind.value == "rectifies":
                    sources = self.rows("invoices", "id", e.source_id)
                    require(
                        len(sources) == 1
                        and sources[0]["rectifies_invoice_id"] == pe.source_id
                        and pe.source_type.value == "invoice",
                        R.DEPENDENCY_INVALID,
                    )
                deps.append(
                    dict(
                        relation=rel.kind.value,
                        event_uuid=str(rel.target_event_id),
                        source_type=parent["stored"].event.source_type.value,
                        source_id=parent["stored"].event.source_id,
                        revision=parent["stored"].event.source_revision,
                        evidence_hash=parent["hash"],
                    )
                )
            ops = self.rows("financial_operations", "operation_uuid", stored.operation_uuid)
            require(len(ops) == 1, R.OPERATION_INVALID)
            op = ops[0]
            try:
                operation = Operation.from_row(op)
            except ERRORS as exc:
                raise InvalidProof(R.OPERATION_INVALID) from exc
            auths = self.rows("financial_authorizations", "operation_uuid", stored.operation_uuid)
            if stored.origin == "historical":
                evidence, quality, original = self.historical(stored, op, auths)
            else:
                require(stored.origin == "live", R.EVENT_INVALID)
                evidence, quality, original = (
                    self.live(stored, op, operation, auths),
                    "verified_fact",
                    None,
                )
            evidence["dependencies"] = sorted(deps, key=lambda d: (d["relation"], d["event_uuid"]))
            result = dict(
                stored=stored,
                quality=quality,
                proof=evidence,
                hash=digest(evidence),
                original=original,
            )
            self.cache[uid] = result
            return result
        finally:
            self.visiting.remove(uid)

    def historical(self, stored, op, auths):
        uid = str(stored.event.event_id)
        proofs = self.rows("financial_history_import_items", "event_uuid", uid)
        require(len(proofs) == 1 and proofs[0]["state"] == "recorded", R.HISTORICAL_INVALID)
        proof = proofs[0]
        items = self.rows("financial_history_items", "item_uuid", str(proof["item_uuid"]))
        require(len(items) == 1, R.HISTORICAL_INVALID)
        original = dict(items[0])
        manifests = self.rows(
            "financial_history_manifests", "manifest_uuid", str(proof["manifest_uuid"])
        )
        batches = self.rows(
            "financial_history_import_batches", "batch_uuid", stored.historical_batch_uuid
        )
        cuts = self.rows(
            "financial_history_cut_manifests", "manifest_uuid", str(proof["manifest_uuid"])
        )
        require(len(manifests) == len(batches) == len(cuts) == 1, R.HISTORICAL_INVALID)
        base, batch, cut = manifests[0], batches[0], cuts[0]
        require(
            str(batch["manifest_uuid"])
            == str(proof["manifest_uuid"])
            == str(original["manifest_uuid"])
            and str(batch["epoch_uuid"]) == str(cut["epoch_uuid"])
            and batch["generation"] == cut["generation"]
            and base["status"] == cut["status"] == "frozen"
            and cut["certifiable"]
            and batch["state"] in ("completed", "partial")
            and not batch["blocking_code"]
            and batch["source_set_hash"] == base["source_set_hash"] == cut["source_set_hash"]
            and batch["plan_hash"] == base["plan_hash"] == cut["plan_hash"],
            R.HISTORICAL_INVALID,
        )
        reconciliations = self.rows(
            "financial_history_reconciliations", "batch_uuid", stored.historical_batch_uuid
        )
        valid = []
        for rec in reconciliations:
            try:
                result = ReconciliationRepository(
                    self.s, self.bid, str(rec["reconciliation_uuid"])
                ).result()
                if (
                    result["result"] == "PASS"
                    and str(rec["manifest_uuid"]) == str(batch["manifest_uuid"])
                    and str(rec["epoch_uuid"]) == str(batch["epoch_uuid"])
                    and rec["generation"] == batch["generation"]
                    and rec["source_set_hash"]
                    == batch["source_set_hash"]
                    == rec["source_recheck_hash"]
                    and rec["plan_hash"] == batch["plan_hash"]
                ):
                    valid.append(rec)
            except ERRORS:
                pass
        require(bool(valid), R.HISTORICAL_INVALID)
        rec = sorted(valid, key=lambda r: str(r["reconciliation_uuid"]))[0]
        original["observation"] = base["started_at"]
        verifier = ReconciliationVerifier(self.s, self.bid, batch, base, None, lambda _: None, 64)
        verifier.events[uid] = {}
        require(verifier.historical(stored, op, auths, proofs, original), R.HISTORICAL_INVALID)
        c = candidate(original["candidate_canonical"], base["started_at"])
        raw = RawSource.from_canonical(original["raw_canonical"])
        require(
            c.identity.revision == revision(raw) and raw.content_hash == original["raw_hash"],
            R.HISTORICAL_INVALID,
        )
        reader = RawReader(self.s, self.bid)
        current = (
            reader.read_fiscal_reference(raw)
            if raw.source_kind == "invoice_cancellation_record"
            else reader.read_key(raw.source_kind, raw.key)
        )
        require(
            current is not None
            and current.content_hash == raw.content_hash
            and revision(current) == c.identity.revision,
            R.SOURCE_CHANGED,
        )
        require(len(c.dependencies) == len(stored.event.relations), R.DEPENDENCY_INVALID)
        for dep in c.dependencies:
            target = next((r for r in stored.event.relations if r.kind == dep.relation), None)
            require(dep.satisfied and target is not None, R.DEPENDENCY_INVALID)
            parent = self.cache.get(str(target.target_event_id))
            pe = parent["stored"].event if parent else None
            require(
                pe is not None
                and pe.source_type == dep.target.source.source_type
                and pe.source_id == dep.target.source.source_id
                and pe.source_revision == dep.target.revision.value
                and pe.event_type == dep.target.event_type,
                R.DEPENDENCY_INVALID,
            )
        quality = {"A": "verified_fact", "B": "observed_state"}.get(
            c.assessment.classification.value
        )
        require(quality is not None, R.HISTORICAL_INVALID)
        from noesis.financial_activation.historical_proof import historical_cut_hash
        evidence = dict(
            origin="historical",
            source_hash=current.content_hash,
            import_hash=storage_hash(proof),
            item_hash=storage_hash(items[0]),
            batch_hash=storage_hash(batch),
            cut_hash=historical_cut_hash(self.s, self.bid, cut),
            reconciliation_hash=rec["result_hash"],
            reconciliation_uuid=str(rec["reconciliation_uuid"]),
            batch_uuid=stored.historical_batch_uuid,
            item_uuid=str(proof["item_uuid"]),
            operation_hash=storage_hash(op),
            authorization_hash=digest(sorted(storage_hash(a) for a in auths)),
            identity_hash=c.identity.content_hash,
            event_content_hash=stored.event.content_hash,
            event_record_hash=stored.record_hash,
        )
        return evidence, quality, current

    def live(self, stored, op, operation, auths):
        e = stored.event
        require(
            op["state"] == "committed"
            and op["entry_namespace"] != "historical"
            and op["committed_at"] is not None
            and operation.result is not None
            and str(op["authorization_uuid"]) == stored.authorization_uuid,
            R.OPERATION_INVALID,
        )
        a = next(
            (a for a in auths if str(a["authorization_uuid"]) == stored.authorization_uuid), None
        )
        require(
            a is not None
            and a["kind"] in ("human_confirmation", "mandate")
            and a["channel"] != "historical"
            and type(a["actor_user_id"]) is int
            and a["actor_user_id"] > 0
            and type(a["actor_session_version"]) is int
            and a["actor_session_version"] >= 0
            and a["recorded_by"] == a["actor_user_id"]
            and a["revoked_at"] is None
            and a["validated_permission"]
            == ("financial.authorize" if a["kind"] == "human_confirmation" else "financial.mandate")
            and a["approved_request_hash"] == operation.request.request_hash
            and a["approved_revision"] == operation.request.expected_revision,
            R.AUTHORIZATION_INVALID,
        )
        # Los Capture existentes admiten human_confirmation. Mandatos no se
        # acreditan aquí por metadatos incompletos de una fila de autorización.
        require(
            a["kind"] == "human_confirmation" and a["mandate_uuid"] is None, R.AUTHORIZATION_INVALID
        )
        from noesis.economic_events.persistence import instant

        require(
            instant(a["authorized_at"]) <= instant(op["committed_at"])
            and (
                a["expires_at"] is None or instant(op["committed_at"]) <= instant(a["expires_at"])
            ),
            R.AUTHORIZATION_INVALID,
        )
        mapping = {
            "invoice.issued": "invoice.issue",
            "invoice.rectified": "invoice.rectify",
            "customer_payment.received": ("customer_payment.record", "bank_transaction.match"),
            "supplier_invoice.confirmed": "supplier_invoice.confirm",
            "supplier_invoice.corrected": "supplier_invoice.correct",
            "supplier_invoice.voided": "supplier_invoice.void",
            "expense.confirmed": "expense.confirm",
            "expense.voided": "expense.void",
            "bank_transaction.imported": "bank_transaction.import",
        }
        commands = mapping.get(e.event_type.value, ())
        commands = (commands,) if isinstance(commands, str) else commands
        require(op["command_type"] in commands, R.OPERATION_INVALID)
        result = operation.result
        # Banco puede contener varios slots. Solo aceptar el slot de importación
        # cuya evidencia propia coincide con el resultado del productor validado.
        require(
            str(result.get("event_uuid")) == str(e.event_id)
            and result.get("content_hash") == e.content_hash
            and result.get("captured") is True,
            R.LIVE_INVALID,
        )
        kind = e.source_type.value
        require(kind in COVERAGES, R.LIVE_INVALID)
        coverages = self.rows(COVERAGES[kind], "event_uuid", str(e.event_id))
        require(len(coverages) == 1, R.COVERAGE_INCOMPLETE)
        coverage = coverages[0]
        field = {
            "invoice": "invoice_id",
            "invoice_payment": "payment_id",
            "bank_transaction": "bank_transaction_id",
        }.get(kind, "source_id")
        require(
            coverage[field] == e.source_id
            and str(coverage["operation_uuid"]) == stored.operation_uuid
            and coverage["operation_state"] == "committed"
            and coverage["event_type"] == e.event_type.value
            and (
                "source_revision" not in coverage
                or coverage["source_revision"] == e.source_revision
            ),
            R.COVERAGE_INCOMPLETE,
        )
        rows = self.rows(TABLES[kind], "id", e.source_id)
        require(len(rows) == 1, R.SOURCE_CHANGED)
        source = rows[0]
        rev, fp = physical_identity(self.s, self.bid, kind, source)
        current = rev == e.source_revision
        if kind in ("expense", "received_invoice"):
            all_coverage = sorted(
                self.rows(COVERAGES[kind], "source_id", e.source_id),
                key=lambda r: r["source_revision"],
            )
            require(
                [r["source_revision"] for r in all_coverage]
                == list(range(1, source["_financial_revision"] + 1)),
                R.COVERAGE_INCOMPLETE,
            )
            state = strict_json(coverage["after_state"])
            require(bool(state), R.COVERAGE_INCOMPLETE)
            payload = e.payload.get("after", e.payload.get("before", e.payload))
            fields = (
                {
                    "total": "total",
                    "base": "base",
                    "vat_amount": "vat_amount",
                    "irpf_amount": "irpf_amount",
                    "invoice_number": "number",
                    "issued_on": "issued_on",
                    "due_on": "due_on",
                }
                if kind == "received_invoice"
                else {
                    "total": "amount",
                    "vat_amount": "_captured_vat_amount",
                    "description": "concept",
                    "spent_on": "spent_on",
                }
            )
            compared = (
                strict_json(coverage["before_state"])
                if e.event_type.value.endswith(".voided")
                else state
            )
            for key, source_key in fields.items():
                require(
                    digest(payload.get(key)) == digest(compared.get(source_key)),
                    R.COVERAGE_INCOMPLETE,
                )
            for prior, next_row in zip(all_coverage, all_coverage[1:]):
                require(
                    str(next_row["antecedent_uuid"]) == str(prior["event_uuid"])
                    and next_row["before_state"] == prior["after_state"],
                    R.DEPENDENCY_INVALID,
                )
        else:
            require(current, R.SOURCE_CHANGED)
        expected_fp = (
            e.payload.get("evidence", {}).get("source_fingerprint")
            if kind == "invoice"
            else coverage.get("source_fingerprint")
        )
        require(expected_fp is not None and (not current or expected_fp == fp), R.SOURCE_CHANGED)
        require(
            (kind == "bank_transaction" and stored.provenance.endswith(":" + expected_fp))
            or result.get("source_fingerprint") == expected_fp,
            R.LIVE_INVALID,
        )
        if e.amount is not None:
            from noesis.core.money import parse_money

            require(
                result.get("currency") == "EUR"
                and parse_money(result["amount"]) == e.amount
                and operation.request.amount == e.amount,
                R.MONEY_UNCERTAIN,
            )
        if kind == "invoice_payment":
            require(
                source["method"] != "registro_anterior"
                and e.payload["invoice_id"] == coverage["invoice_id"] == source["invoice_id"]
                and {(r.kind.value, str(r.target_event_id)) for r in e.relations}
                == {("settles", str(coverage["invoice_event_uuid"]))},
                R.PAYMENT_HISTORY_INCOMPLETE,
            )
        return dict(
            origin="live",
            operation_hash=storage_hash(op),
            authorization_hash=storage_hash(a),
            coverage_hash=storage_hash(coverage),
            source_hash=storage_hash(source),
            event_content_hash=e.content_hash,
            event_record_hash=stored.record_hash,
        )
