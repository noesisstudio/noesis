"""Comprobación prestada por identidad; persistir es una operación separada."""

from decimal import Context, Decimal, localcontext

from noesis import db, migrations
from noesis.core.locks import lock_business
from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import (
    AccessDenied,
    ConflictError,
    Principal,
    StateError,
    uuid_text,
)
from noesis.financial_history.reconciliation_verifier import storage_hash
from .contracts import (
    AntecedentRef,
    CATALOG,
    FIELDS,
    Permission,
    Purpose,
    Reason as R,
    ResolutionRequest,
    SCHEMAS,
    canonical,
    digest,
    field_proof,
    validate_result,
)
from .proofs import (
    ProofChecker,
    TABLES,
    InvalidProof,
    physical_identity,
    matches_projection,
    require,
    ERRORS,
)


class AntecedentResolver:
    def __init__(self, session, business_id):
        if not isinstance(session, FinancialSession):
            raise TypeError("FinancialSession prestada requerida.")
        from noesis.financial_operations.contracts import positive_id

        self.s, self.bid = session, positive_id(business_id)

    def _access(self, principal, permission):
        if not isinstance(principal, Principal) or permission not in (
            Permission.RESOLVE,
            Permission.READ,
        ):
            raise AccessDenied("Acceso a antecedente denegado.")
        if self.s.dialect == "sqlite" and not self.s.borrowed_connection.raw.in_transaction:
            raise StateError("Transacción exterior requerida.")
        if self.s.dialect == "postgres":
            from psycopg.pq import TransactionStatus

            if self.s.borrowed_connection.raw.info.transaction_status != TransactionStatus.INTRANS:
                raise StateError("Transacción exterior requerida.")
        lock_business(self.s, self.bid)
        suffix = " FOR SHARE" if self.s.dialect == "postgres" else ""
        user = self.s.execute(
            "SELECT is_active,session_version FROM users WHERE business_id=? AND id=?" + suffix,
            (self.bid, principal.user_id),
        ).fetchone()
        business = self.s.borrowed_connection.execute_exact(
            "SELECT * FROM businesses WHERE id=?" + suffix, (self.bid,)
        ).fetchone()
        if (
            not user
            or not user["is_active"]
            or user["session_version"] != principal.session_version
            or not business
        ):
            raise AccessDenied("Acceso a antecedente denegado.")
        check = dict(business)
        if hasattr(check["trial_ends_at"], "isoformat"):
            check["trial_ends_at"] = check["trial_ends_at"].isoformat()
        if not db.subscription_allows_access(check):
            raise AccessDenied("Acceso a antecedente denegado.")
        if migrations.current_version_connection(self.s.borrowed_connection) not in SCHEMAS:
            raise StateError("Esquema de antecedentes incompatible.")

    def _source(self, ref):
        suffix = " FOR SHARE" if self.s.dialect == "postgres" else ""
        row = self.s.borrowed_connection.execute_exact(
            "SELECT * FROM "
            + TABLES[ref.source_type.value]
            + " WHERE business_id=? AND id=?"
            + suffix,
            (self.bid, ref.source_id),
        ).fetchone()
        if not row:
            # Mismo rechazo para id inexistente o ajeno. Nunca consultar otro tenant.
            raise AccessDenied("Acceso a antecedente denegado.")
        return row

    def _event_row(self, ref):
        if ref.event_uuid is not None:
            row = self.s.execute(
                "SELECT * FROM economic_events WHERE business_id=? AND event_uuid=?",
                (self.bid, ref.event_uuid),
            ).fetchone()
            if not row:
                raise AccessDenied("Acceso a antecedente denegado.")
            return row
        rows = self.s.execute(
            "SELECT * FROM economic_events WHERE business_id=? AND source_type=? AND source_id=? AND source_revision=? ORDER BY event_uuid",
            (self.bid, ref.source_type.value, ref.source_id, ref.revision),
        ).fetchall()
        require(len(rows) <= 1, R.DEPENDENCY_INVALID)
        return rows[0] if rows else None

    def resolve(self, principal, request, *, permission=Permission.RESOLVE):
        """SELECT exclusivamente. No persistencia, conexión ni commit propio."""
        if permission != Permission.RESOLVE:
            raise AccessDenied("Acceso a antecedente denegado.")
        if not isinstance(request, ResolutionRequest):
            raise TypeError("Request v1 tipado requerido.")
        self._access(principal, permission)
        with localcontext(Context(prec=50)):
            return self._resolve(principal, request)

    def _resolve(self, principal, request):
        ref = request.antecedent
        source = self._source(ref)
        checker = ProofChecker(self.s, self.bid)
        reasons, evidence, dependencies = set(), {}, []
        proof = {f: field_proof(False) for f in FIELDS}
        result = dict(
            resolution_version=1,
            business_id=self.bid,
            request=request.value(),
            outcome="blocked",
            reasons=[],
            origin=None,
            quality=None,
            event_uuid=None,
            operation_uuid=None,
            authorization_uuid=None,
            batch_uuid=None,
            item_uuid=None,
            reconciliation_uuid=None,
            source_hash=storage_hash(source),
            event_content_hash=None,
            event_record_hash=None,
            proof=proof,
            amount=None,
            currency=None,
            remaining=None,
            dependencies=[],
        )
        # Estado físico desconocido no se interpreta como pago ni hecho económico.
        proof["source_state"] = field_proof(True, storage_hash(source))
        if source.get("method") == "registro_anterior":
            reasons.add(R.NOT_VERIFIED)
        kind, types = CATALOG[request.purpose]
        if kind is not None and kind != ref.source_type.value:
            reasons.add(R.PURPOSE_NOT_ALLOWED)
        try:
            row = self._event_row(ref)
            if row is None:
                reasons.add(R.EVENT_MISSING)
                money_field = {
                    "invoice": "total",
                    "expense": "amount",
                    "received_invoice": "total",
                    "invoice_payment": "amount",
                    "bank_transaction": "amount",
                }.get(ref.source_type.value)
                if money_field is not None:
                    reasons.add(R.MONEY_UNCERTAIN)
                if ref.source_type.value == "invoice":
                    reasons.add(R.UNSUPPORTED)
            else:
                require(
                    row["source_type"] == ref.source_type.value
                    and row["source_id"] == ref.source_id,
                    R.DEPENDENCY_INVALID,
                )
                require(row["source_revision"] == ref.revision, R.SOURCE_CHANGED)
                result.update(
                    event_uuid=str(row["event_uuid"]),
                    origin=row["origin"],
                    operation_uuid=str(row["operation_uuid"]) if row["operation_uuid"] else None,
                    authorization_uuid=str(row["authorization_uuid"])
                    if row["authorization_uuid"]
                    else None,
                    event_content_hash=row["content_hash"],
                    event_record_hash=row["record_hash"],
                )
                if row["origin"] == "historical" and ref.source_type.value == "invoice":
                    raise InvalidProof(R.UNSUPPORTED)
                checked = checker.check(row)
                stored, e = checked["stored"], checked["stored"].event
                evidence = dict(checked["proof"], event_storage_hash=storage_hash(row))
                result.update(
                    quality=checked["quality"],
                    batch_uuid=evidence.get("batch_uuid"),
                    item_uuid=evidence.get("item_uuid"),
                    reconciliation_uuid=evidence.get("reconciliation_uuid"),
                )
                if stored.origin == "live":
                    revision, _ = physical_identity(self.s, self.bid, ref.source_type.value, source)
                    require(revision == ref.revision, R.SOURCE_CHANGED)
                if types and e.event_type.value not in types:
                    reasons.add(R.PURPOSE_NOT_ALLOWED)
                if request.purpose != Purpose.INSPECT and checked["quality"] != "verified_fact":
                    reasons.add(R.OBSERVED_INSUFFICIENT)
                if e.amount is not None:
                    result["amount"] = format(e.amount, ".2f")
                    proof["amount"] = field_proof(True, digest(result["amount"]))
                result["currency"] = e.currency.value
                proof["currency"] = field_proof(True, digest(e.currency.value))
                state_fields = e.payload.get("after", e.payload)
                for field in ("base", "vat_amount", "irpf_amount", "invoice_number", "due_on"):
                    value = state_fields.get(field)
                    if value is not None:
                        proof[field] = field_proof(True, digest(value))
                if e.economic_date is not None:
                    proof["economic_date"] = field_proof(True, digest(e.economic_date.isoformat()))
                if request.purpose != Purpose.INSPECT:
                    if e.amount is None:
                        reasons.add(R.MONEY_UNCERTAIN)
                    if e.economic_date is None:
                        reasons.add(R.DATE_UNCERTAIN)
                    if ref.source_type.value == "received_invoice":
                        state = e.payload.get("after", e.payload)
                        complete = all(
                            state.get(f) is not None
                            for f in (
                                "total",
                                "base",
                                "vat_amount",
                                "irpf_amount",
                                "issued_on",
                                "invoice_number",
                            )
                        )
                    elif ref.source_type.value == "expense":
                        state = e.payload
                        complete = all(
                            state.get(f) is not None for f in ("total", "vat_amount", "spent_on")
                        )
                    else:
                        complete = True
                    if complete:
                        proof["state_components"] = field_proof(True, digest(e.payload))
                    else:
                        reasons.add(R.NOT_VERIFIED)
                dependencies += evidence.get("dependencies", [])
                if ref.source_type.value == "invoice" and request.purpose != Purpose.INSPECT:
                    self._invoice(checker, stored, source, result, reasons, evidence)
                if request.purpose == Purpose.BANK_MATCH:
                    if request.bank_movement is None:
                        reasons.add(R.DEPENDENCY_INVALID)
                    else:
                        bank_source = self._source(request.bank_movement)
                        bank_row = self._event_row(request.bank_movement)
                        require(bank_row is not None, R.EVENT_MISSING)
                        bank = checker.check(bank_row)
                        be = bank["stored"].event
                        require(
                            be.source_type.value == "bank_transaction"
                            and be.source_id == request.bank_movement.source_id
                            and be.source_revision == request.bank_movement.revision
                            and bank["stored"].origin == "live"
                            and be.event_type.value == "bank_transaction.imported"
                            and bank["quality"] == "verified_fact"
                            and bank_source["status"] == "imported",
                            R.LIVE_INVALID,
                        )
                        require(
                            be.amount > 0
                            and result["remaining"] is not None
                            and be.amount <= Decimal(result["remaining"]),
                            R.MONEY_UNCERTAIN,
                        )
                        proof["bank_movement"] = field_proof(True, bank["hash"])
                        evidence["bank_hash"] = bank["hash"]
                        dependencies.append(
                            dict(
                                relation="bank_evidence",
                                event_uuid=str(be.event_id),
                                source_type="bank_transaction",
                                source_id=be.source_id,
                                revision=be.source_revision,
                                evidence_hash=bank["hash"],
                            )
                        )
        except InvalidProof as exc:
            reasons.add(exc.reason)
        except ERRORS:
            reasons.add(R.EVENT_INVALID)
        result["dependencies"] = sorted(
            dependencies, key=lambda d: (d["relation"], d["event_uuid"])
        )
        result["reasons"] = sorted(r.value for r in reasons)
        result["outcome"] = "blocked" if reasons else "resolved"
        context = dict(
            actor=principal.user_id,
            session=principal.session_version,
            request=request.value(),
            evidence=evidence,
            result=result,
        )
        result["context_hash"] = digest(context)
        result["evidence_hash"] = digest(result)
        return validate_result(result)

    def _invoice(self, checker, stored, source, result, reasons, evidence):
        e = stored.event
        if e.payload_version != 2 or e.amount is None or e.currency.value != "EUR":
            reasons.add(R.UNSUPPORTED)
            return
        if source["status"] not in ("enviada", "parcial", "cobrada"):
            reasons.add(R.NOT_VERIFIED)
        payments = checker.rows("invoice_payments", "invoice_id", e.source_id)
        coverages = checker.rows("payment_economic_coverage", "invoice_id", e.source_id)
        linked_payments = self.s.execute(
            "SELECT e.event_uuid FROM economic_events e JOIN economic_event_links l "
            "ON l.business_id=e.business_id AND l.event_uuid=e.event_uuid "
            "WHERE e.business_id=? AND e.event_type='customer_payment.received' "
            "AND l.relation_type='settles' AND l.target_event_uuid=?",
            (self.bid, str(e.event_id)),
        ).fetchall()
        if len(payments) != len(coverages) or len({c["payment_id"] for c in coverages}) != len(
            payments
        ):
            reasons.add(R.PAYMENT_HISTORY_INCOMPLETE)
            return
        total, hashes = Decimal("0.00"), []
        for payment in sorted(payments, key=lambda r: r["id"]):
            if payment["method"] == "registro_anterior":
                reasons.add(R.PAYMENT_HISTORY_INCOMPLETE)
                return
            coverage = next((c for c in coverages if c["payment_id"] == payment["id"]), None)
            require(
                coverage is not None and str(coverage["invoice_event_uuid"]) == str(e.event_id),
                R.PAYMENT_HISTORY_INCOMPLETE,
            )
            paid = checker.event(str(coverage["event_uuid"]))
            require(
                paid["quality"] == "verified_fact" and paid["stored"].event.amount is not None,
                R.PAYMENT_HISTORY_INCOMPLETE,
            )
            total += paid["stored"].event.amount
            hashes.append(paid["hash"])
        if {str(p["event_uuid"]) for p in linked_payments} != {
            str(c["event_uuid"]) for c in coverages
        }:
            reasons.add(R.PAYMENT_HISTORY_INCOMPLETE)
            return
        # Verificar status/paid_at, jamás deducir pagos desde sus etiquetas.
        expected = "enviada" if total == 0 else "parcial" if total < e.amount else "cobrada"
        if (
            total > e.amount
            or source["status"] != expected
            or (total == 0 and source["paid_at"] is not None)
        ):
            reasons.add(R.PAYMENT_HISTORY_INCOMPLETE)
            return
        result["remaining"] = format(e.amount - total, ".2f")
        result["proof"]["prior_payments"] = field_proof(True, digest(hashes))
        evidence["payment_hashes"] = hashes
        invoice_evidence = e.payload["evidence"]
        fiscal = invoice_evidence["fiscal_record"]
        business = self.s.execute(
            "SELECT verifactu_enabled FROM businesses WHERE id=?", (self.bid,)
        ).fetchone()
        evidence["fiscal_mode"] = bool(business["verifactu_enabled"])
        required = (
            business["verifactu_enabled"]
            or result["request"]["purpose"] == Purpose.FISCAL_CANCEL.value
        )
        if fiscal is not None:
            rows = checker.rows("invoice_records", "id", fiscal["id"])
            if (
                len(rows) == 1
                and rows[0]["invoice_id"] == e.source_id
                and rows[0]["record_hash"] == fiscal["record_hash"]
                and all(matches_projection(rows[0].get(k), v) for k, v in fiscal.items())
            ):
                result["proof"]["fiscal_evidence"] = field_proof(True, storage_hash(rows[0]))
                evidence["fiscal_hash"] = storage_hash(rows[0])
            else:
                reasons.add(R.FISCAL_INCOMPLETE)
        if required and result["proof"]["fiscal_evidence"]["state"] != "known":
            reasons.add(R.FISCAL_INCOMPLETE)

    def persist_resolution(
        self, principal, resolution_uuid, request, *, permission=Permission.RESOLVE
    ):
        """Recomprueba en esta TX, luego escribe exclusivamente una tabla B."""
        value = self.resolve(principal, request, permission=permission)
        from .repository import AntecedentRepository

        return AntecedentRepository(self.s, self.bid).store(
            principal, uuid_text(resolution_uuid), value
        )

    def read(self, principal, resolution_uuid, *, permission=Permission.READ):
        if permission != Permission.READ:
            raise AccessDenied("Acceso a antecedente denegado.")
        self._access(principal, permission)
        from .repository import AntecedentRepository

        return AntecedentRepository(self.s, self.bid).read(principal, uuid_text(resolution_uuid))

    def verify_resolution(self, principal, resolution, *, permission=Permission.RESOLVE):
        """Revalidación obligatoria en cada uso; stale nunca concede ejecución."""
        original = self.read(principal, resolution["resolution_uuid"])
        if canonical(original) != canonical(resolution):
            raise ConflictError(R.SOURCE_CHANGED.value)
        req = original["result"]["request"]
        request = ResolutionRequest(
            AntecedentRef(**req["antecedent"]),
            req["purpose"],
            None if req["bank_movement"] is None else AntecedentRef(**req["bank_movement"]),
        )
        current = self.resolve(principal, request, permission=permission)
        if current["context_hash"] != original["result"]["context_hash"]:
            raise ConflictError(R.SOURCE_CHANGED.value)
        return original


def verify_resolution(session, business_id, principal, resolution):
    return AntecedentResolver(session, business_id).verify_resolution(principal, resolution)
