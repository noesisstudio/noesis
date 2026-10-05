"""Importer interno: registra evidencia congelada, nunca ejecuta acciones originales."""

from collections import deque
import json

from noesis import migrations
from noesis.economic_events.contracts import EventRelation
from noesis.economic_events.persistence import StoredEvent
from noesis.economic_events.repository import EventsRepository
from noesis.financial_operations.contracts import AccessDenied, ConflictError, StateError, uuid_text
from .classifier import revision
from .cutoff import EpochUnavailable, HistoryCutoff
from .cut_scope import SCOPE
from .durable import HistoricalEconomicEvent, HistoricalImportContext, operation_uuid
from .import_contracts import candidate as decode_candidate, coverage as decode_coverage
from .import_repository import ImportRepository, result_values
from .payloads import HISTORICAL_V2
from .readers import RawReader, RawSource
from .repository import canonical, stamp


class ImportBlocked(StateError):
    """Conflicto de incorporación; no modifica el diagnóstico congelado."""


class HistoryImporter(HistoryCutoff):
    def _checkpoint(self, step):
        """Punto interno de observación para pruebas de crash; no callback de canal."""

    def _boundary(self, session, manifest_uuid):
        if migrations.current_version_connection(session.borrowed_connection) != 72:
            raise StateError("Schema72 requerido.")
        row = session.execute(
            "SELECT * FROM financial_history_cut_manifests WHERE business_id=? AND manifest_uuid=?",
            (self.business_id, manifest_uuid),
        ).fetchone()
        if not row:
            raise AccessDenied("Manifest C del negocio requerido; diagnóstico B no autoriza.")
        base = session.execute(
            "SELECT * FROM financial_history_manifests WHERE business_id=? AND manifest_uuid=?",
            (self.business_id, manifest_uuid),
        ).fetchone()
        epoch = session.execute(
            "SELECT * FROM financial_history_epochs WHERE business_id=? AND epoch_uuid=?",
            (self.business_id, str(row["epoch_uuid"])),
        ).fetchone()
        control = session.execute(
            "SELECT * FROM financial_history_control WHERE business_id=?", (self.business_id,)
        ).fetchone()
        if (
            not epoch
            or not control
            or epoch["state"] != "fenced"
            or not epoch["fence_enabled"]
            or not control["fence_enabled"]
            or str(control["epoch_uuid"]) != str(row["epoch_uuid"])
            or control["generation"] != row["generation"]
            or row["generation"] != epoch["generation"]
            or not row["certifiable"]
            or not row["boundary_current"]
        ):
            raise EpochUnavailable("Corte revocado/no vigente; no iniciar item.")
        if (
            row["status"] != "frozen"
            or base["status"] != "frozen"
            or row["mode"] != "certifiable_inventory"
            or row["eligible_for_import"]
            or row["source_scope_canonical"] != canonical(SCOPE)
            or row["source_scope_version"] != 1
            or any(
                base[k] != 1
                for k in (
                    "reader_version",
                    "classifier_version",
                    "canonical_version",
                    "scope_version",
                )
            )
            or row["source_set_hash"] != row["comparison_source_set_hash"]
            or any(
                row[k] != base[k]
                for k in ("source_set_hash", "comparison_source_set_hash", "plan_hash")
            )
        ):
            raise ImportBlocked("MANIFEST_INCONSISTENT")
        return row, base

    def prepare(self, principal, manifest_uuid, batch_uuid):
        manifest_uuid, batch_uuid = uuid_text(manifest_uuid), uuid_text(batch_uuid)
        with self._session(principal) as session:
            cut, _ = self._boundary(session, manifest_uuid)
            row = session.execute(
                "SELECT * FROM financial_history_import_batches WHERE business_id=? AND batch_uuid=?",
                (self.business_id, batch_uuid),
            ).fetchone()
            if row:
                if (
                    str(row["manifest_uuid"]) != manifest_uuid
                    or row["plan_hash"] != cut["plan_hash"]
                    or row["importer_version"] != 1
                ):
                    raise ConflictError("Batch vinculado a otro plan/version.")
                return row
            now = stamp()
            session.execute(
                """INSERT INTO financial_history_import_batches (business_id,batch_uuid,manifest_uuid,epoch_uuid,
                generation,importer_version,source_set_hash,plan_hash,created_by,created_at,updated_at,state)
                VALUES (?,?,?,?,?,1,?,?,?,?,?,'prepared')""",
                (
                    self.business_id,
                    batch_uuid,
                    manifest_uuid,
                    str(cut["epoch_uuid"]),
                    cut["generation"],
                    cut["source_set_hash"],
                    cut["plan_hash"],
                    principal.user_id,
                    now,
                    now,
                ),
            )
            return session.execute(
                "SELECT * FROM financial_history_import_batches WHERE business_id=? AND batch_uuid=?",
                (self.business_id, batch_uuid),
            ).fetchone()

    def _batch(self, session, batch_uuid):
        batch = session.execute(
            "SELECT * FROM financial_history_import_batches WHERE business_id=? AND batch_uuid=?",
            (self.business_id, batch_uuid),
        ).fetchone()
        if not batch:
            raise AccessDenied("Batch del negocio requerido.")
        cut, base = self._boundary(session, str(batch["manifest_uuid"]))
        if (
            str(batch["epoch_uuid"]) != str(cut["epoch_uuid"])
            or batch["generation"] != cut["generation"]
            or batch["plan_hash"] != cut["plan_hash"]
            or batch["source_set_hash"] != cut["source_set_hash"]
            or batch["importer_version"] != 1
        ):
            raise ImportBlocked("BATCH_INCONSISTENT")
        return batch, cut, base

    def _source(self, session, row):
        try:
            frozen = RawSource.from_canonical(row["raw_canonical"])
        except (ValueError, TypeError, KeyError, ArithmeticError) as error:
            raise ImportBlocked("RAW_INCONSISTENT") from error
        if frozen.business_id != self.business_id or frozen.content_hash != row["raw_hash"]:
            raise ImportBlocked("RAW_INCONSISTENT")
        reader = RawReader(session, self.business_id, cut_scope=True)
        current = (
            reader.read_fiscal_reference(frozen)
            if frozen.source_kind in ("invoice_record", "invoice_cancellation_record")
            else reader.read_key(frozen.source_kind, frozen.key)
        )
        if (
            current is None
            or current.content_hash != frozen.content_hash
            or revision(current) != revision(frozen)
        ):
            raise ImportBlocked("SOURCE_DRIFT")
        return current

    def _load_event(self, session, event_uuid):
        repo = EventsRepository(session, self.business_id)
        row = repo.load(event_uuid)
        if not row:
            raise ImportBlocked("DEPENDENCY_MISSING")
        try:
            stored = StoredEvent.from_row(row)
        except (ValueError, TypeError, KeyError, ArithmeticError) as error:
            raise ImportBlocked("EXISTING_EVENT_CONFLICT") from error
        if {(r["relation_type"], str(r["target_event_uuid"])) for r in repo.links(event_uuid)} != {
            (r.kind.value, str(r.target_event_id)) for r in stored.event.relations
        }:
            raise ImportBlocked("EXISTING_EVENT_CONFLICT")
        if stored.origin == "historical":
            proof = session.execute(
                """SELECT x.* FROM financial_history_import_items x
                JOIN financial_history_import_batches b ON b.business_id=x.business_id AND b.batch_uuid=x.batch_uuid
                WHERE x.business_id=? AND x.event_uuid=? AND x.state='recorded' AND x.batch_uuid=?""",
                (self.business_id, event_uuid, stored.historical_batch_uuid),
            ).fetchone()
            op = session.execute(
                "SELECT * FROM financial_operations WHERE business_id=? AND operation_uuid=?",
                (self.business_id, stored.operation_uuid),
            ).fetchone()
            auth = session.execute(
                "SELECT * FROM financial_authorizations WHERE business_id=? AND authorization_uuid=?",
                (self.business_id, stored.authorization_uuid),
            ).fetchone()
            if (
                not proof
                or not op
                or not auth
                or op["state"] != "prepared"
                or op["entry_namespace"] != "historical"
                or op["result_canonical"] is not None
                or auth["kind"] != "historical_unknown"
                or auth["actor_user_id"] is not None
                or auth["actor_session_version"] is not None
                or str(op["authorization_uuid"]) != stored.authorization_uuid
                or proof["content_hash"] != stored.event.content_hash
                or proof["record_hash"] != stored.record_hash
            ):
                raise ImportBlocked("EXISTING_EVENT_CONFLICT")
            from noesis.financial_operations.contracts import Operation

            try:
                operation = Operation.from_row(op)
            except (ValueError, TypeError, KeyError, ArithmeticError) as error:
                raise ImportBlocked("EXISTING_EVENT_CONFLICT") from error
            if (
                operation.request.request_hash != auth["approved_request_hash"]
                or operation.request.expected_revision != auth["approved_revision"]
                or auth["recorded_by"] != op["created_by"]
                or auth["validated_permission"] != "historical.record"
                or auth["channel"] != "historical"
                or proof["expected_request_canonical"] != op["request_canonical"]
                or proof["expected_event_canonical"] != stored.event.canonical_bytes().decode()
                or str(proof["expected_event_uuid"]) != str(stored.event.event_id)
                or str(proof["expected_operation_uuid"]) != stored.operation_uuid
                or str(proof["expected_authorization_uuid"]) != stored.authorization_uuid
            ):
                raise ImportBlocked("EXISTING_EVENT_CONFLICT")
        return stored

    def _covered(self, session, coverage):
        stored = self._load_event(session, str(coverage.event_uuid))
        self._matches_identity(coverage.identity, stored)
        if (
            stored.origin != coverage.origin.value
            or stored.event.content_hash != coverage.event_content_hash
        ):
            raise ImportBlocked("EXISTING_EVENT_CONFLICT")
        return stored

    @staticmethod
    def _matches_identity(identity, stored):
        event = stored.event
        if (
            event.business_id != identity.source.business_id
            or event.source_type != identity.source.source_type
            or event.source_id != identity.source.source_id
            or event.source_revision != identity.revision.value
            or event.event_type != identity.event_type
        ):
            raise ImportBlocked("EXISTING_EVENT_CONFLICT")

    def _dependencies(self, session, manifest_uuid, candidate):
        result = []
        for dep in candidate.dependencies:
            if not dep.satisfied:
                raise ImportBlocked("DEPENDENCY_UNVERIFIED")
            ident = dep.target
            if ident.source.business_id != self.business_id:
                raise ImportBlocked("DEPENDENCY_CROSS_BUSINESS")
            parent_rows = session.execute(
                "SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND source_type=? AND source_id=? AND fact_slot=?",
                (
                    self.business_id,
                    manifest_uuid,
                    ident.source.source_type.value,
                    str(ident.source.source_id),
                    ident.fact_slot,
                ),
            ).fetchall()
            parent = next(
                (
                    p
                    for p in parent_rows
                    if (
                        p["candidate_canonical"]
                        and decode_candidate(
                            p["candidate_canonical"], candidate.dates.observed_at
                        ).identity
                        == ident
                    )
                    or (
                        p["existing_coverage_canonical"]
                        and decode_coverage(p["existing_coverage_canonical"]).identity == ident
                    )
                ),
                None,
            )
            if not parent or parent["classification"] != "A" or parent["severity"] == "blocking":
                raise ImportBlocked("DEPENDENCY_UNVERIFIED")
            self._source(session, parent)
            if parent["existing_coverage_canonical"]:
                stored = self._covered(
                    session, decode_coverage(parent["existing_coverage_canonical"])
                )
            else:
                proofs = session.execute(
                    "SELECT * FROM financial_history_import_items WHERE business_id=? AND identity_hash=? AND state='recorded'",
                    (self.business_id, ident.content_hash),
                ).fetchall()
                if len(proofs) != 1 or proofs[0]["candidate_hash"] != parent["candidate_hash"]:
                    raise ImportBlocked("DEPENDENCY_MISSING")
                stored = self._load_event(session, str(proofs[0]["event_uuid"]))
                self._matches_identity(ident, stored)
            result.append(
                EventRelation(
                    dep.relation, stored.event.event_id, stored.event.event_type, self.business_id
                )
            )
        return tuple(result)

    def _candidate(self, session, row, observed_at):
        if (
            row["classification"] not in ("A", "B")
            or row["disposition"] != "candidate"
            or not row["candidate_canonical"]
        ):
            raise ImportBlocked("ITEM_NOT_CANDIDATE")
        try:
            candidate = decode_candidate(row["candidate_canonical"], observed_at)
        except (ValueError, TypeError, KeyError, ArithmeticError) as error:
            raise ImportBlocked("CANDIDATE_INCONSISTENT") from error
        whitelist = (
            candidate.event_payload.payload_version == 2
            and candidate.event_payload.event_type in HISTORICAL_V2
            and row["terminal_result"] == "not_durably_supported"
        )
        if (
            candidate.content_hash != row["candidate_hash"]
            or candidate.identity.source.business_id != self.business_id
            or candidate.assessment.canonical_bytes().decode() != row["assessment_canonical"]
            or candidate.assessment.classification.value != row["classification"]
            or canonical(candidate.dependencies) != row["dependency_canonical"]
            or json.loads(row["unresolved_dependency_canonical"])
            or (
                not whitelist
                and (
                    row["severity"] == "blocking" or row["terminal_result"] != "planned_diagnostic"
                )
            )
        ):
            raise ImportBlocked("CANDIDATE_NOT_SUPPORTED")
        if session.execute(
            "SELECT 1 FROM financial_history_incidences WHERE business_id=? AND manifest_uuid=? AND item_uuid=? AND severity='blocking' LIMIT 1",
            (self.business_id, str(row["manifest_uuid"]), str(row["item_uuid"])),
        ).fetchone():
            raise ImportBlocked("BLOCKING_INCIDENCE")
        current = self._source(session, row)
        if (
            candidate.identity.revision != revision(current)
            or str(candidate.identity.source.source_id) != current.source_id
            or candidate.identity.source.source_type.value != current.source_kind
            or candidate.identity.fact_slot != row["fact_slot"]
            or candidate.identity.event_type.value != row["proposed_event_type"]
        ):
            raise ImportBlocked("SOURCE_DRIFT")
        fields = {
            "received_invoice": {
                "total": "total",
                "base": "base",
                "vat_amount": "vat_amount",
                "irpf_amount": "irpf_amount",
            },
            "expense": {"total": "amount", "vat_amount": "_captured_vat_amount"},
            "bank_transaction": {"amount": "amount"},
            "invoice_payment": {"amount": "amount"},
        }
        expected_money = fields.get(current.source_kind)
        if expected_money is not None and any(
            candidate.evidence.money[k] != current.money[f].evidence
            for k, f in expected_money.items()
        ):
            raise ImportBlocked("EVIDENCE_INCONSISTENT")
        payload, f = candidate.event_payload.payload, current.fields
        comparisons = {
            "received_invoice": {
                "invoice_number": f.get("number"),
                "issued_on": f.get("issued_on"),
                "due_on": f.get("due_on"),
            },
            "expense": {
                "description": f.get("concept"),
                "spent_on": None if f.get("spent_on") is None else f["spent_on"][:10],
            },
            "invoice_payment": {
                "invoice_id": f.get("invoice_id"),
                "method": f.get("method"),
                "received_on": None if f.get("paid_at") is None else f["paid_at"][:10],
            },
            "invoice_cancellation_record": {
                "invoice_id": f.get("invoice_id"),
                "invoice_number": f.get("invoice_number"),
                "reason": f.get("reason"),
                "registered_on": f.get("generated_at", "")[:10],
            },
        }
        if candidate.identity.event_type.value == "bank_transaction.imported":
            comparisons["bank_transaction"] = {"booked_on": f["booked_on"]}
        if any(payload.get(k) != v for k, v in comparisons.get(current.source_kind, {}).items()):
            raise ImportBlocked("EVIDENCE_INCONSISTENT")
        if current.source_kind == "invoice_cancellation_record":
            for kind, source_id in (
                ("invoice_record", f["original_record_id"]),
                ("invoice", f["invoice_id"]),
            ):
                supporting = session.execute(
                    "SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND source_type=? AND source_id=?",
                    (self.business_id, str(row["manifest_uuid"]), kind, str(source_id)),
                ).fetchone()
                if not supporting:
                    raise ImportBlocked("EVIDENCE_INCONSISTENT")
                actual = self._source(session, supporting)
                if (
                    kind == "invoice"
                    and candidate.evidence.money["original_total"] != actual.money["total"].evidence
                ):
                    raise ImportBlocked("EVIDENCE_INCONSISTENT")
        if candidate.evidence.references:
            # Scanner B/C actual no construye estas referencias contractuales A.
            # No inventar lector que finja acreditarlas al ampliar futuros candidatos.
            raise ImportBlocked("EVIDENCE_REFERENCE_NOT_SUPPORTED")
        return candidate

    def _terminal(self, repo, principal, row, state, stored=None, reason=None, candidate=None):
        result = result_values(str(row["item_uuid"]), state, stored, reason)
        repo.insert(
            dict(
                manifest_uuid=str(row["manifest_uuid"]),
                item_uuid=str(row["item_uuid"]),
                candidate_hash=row["candidate_hash"],
                raw_hash=row["raw_hash"],
                identity_hash=None if candidate is None else candidate.identity.content_hash,
                identity_canonical=None
                if candidate is None
                else candidate.identity.canonical_bytes().decode(),
                recorded_by=principal.user_id,
                session_version=principal.session_version,
                state=state,
                completion_key=state,
                event_uuid=result["event_uuid"],
                operation_uuid=result["operation_uuid"],
                authorization_uuid=result["authorization_uuid"],
                content_hash=result["content_hash"],
                record_hash=result["record_hash"],
                result_canonical=canonical(result),
                reason=reason,
                created_at=stamp(),
                completed_at=stamp(),
            )
        )
        return result

    def record_item(self, principal, batch_uuid, item_uuid):
        batch_uuid, item_uuid = uuid_text(batch_uuid), uuid_text(item_uuid)
        try:
            with self._session(principal) as session:
                result = self._record_item(session, principal, batch_uuid, item_uuid)
        except ImportBlocked as error:
            # Después del rollback del item: resultado separado; sin huérfanos.
            with self._session(principal) as session:
                batch, _, _ = self._batch(session, batch_uuid)
                row = session.execute(
                    "SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND item_uuid=?",
                    (self.business_id, str(batch["manifest_uuid"]), item_uuid),
                ).fetchone()
                if not row:
                    raise AccessDenied("Item del manifest requerido.") from error
                repo = ImportRepository(session, self.business_id, batch_uuid)
                previous = repo.item(item_uuid)
                if previous:
                    # Evidencia previa sellada no se reescribe ni disimula el conflicto.
                    result = result_values(item_uuid, "blocked", reason=str(error))
                else:
                    result = self._terminal(repo, principal, row, "blocked", reason=str(error))
                session.execute(
                    "UPDATE financial_history_import_batches SET state='blocked',blocking_code=?,blocking_item_uuid=?,updated_at=? WHERE business_id=? AND batch_uuid=?",
                    (str(error), item_uuid, stamp(), self.business_id, batch_uuid),
                )
            if str(error) == "SOURCE_DRIFT":
                # Invalida explícitamente el cut roto, conservando fence y resultado.
                with self._session(principal) as session:
                    epoch = session.execute(
                        "SELECT opened_by FROM financial_history_epochs WHERE business_id=? AND epoch_uuid=?",
                        (self.business_id, str(batch["epoch_uuid"])),
                    ).fetchone()
                if epoch["opened_by"] == principal.user_id:
                    self.invalidate(
                        principal, str(batch["epoch_uuid"]), reason="import_source_drift"
                    )
        self._checkpoint("committed")
        return result

    def _record_item(self, session, principal, batch_uuid, item_uuid):
        batch, cut, base = self._batch(session, batch_uuid)
        manifest_uuid = str(batch["manifest_uuid"])
        row = session.execute(
            "SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND item_uuid=?",
            (self.business_id, manifest_uuid, item_uuid),
        ).fetchone()
        if not row:
            raise AccessDenied("Item del manifest y negocio requerido.")
        repo = ImportRepository(session, self.business_id, batch_uuid)
        previous = repo.item(item_uuid)
        if previous:
            if (
                previous["candidate_hash"] != row["candidate_hash"]
                or previous["raw_hash"] != row["raw_hash"]
            ):
                raise ImportBlocked("EXISTING_EVENT_CONFLICT")
            self._source(session, row)
            if previous["event_uuid"] is not None:
                stored = self._load_event(session, str(previous["event_uuid"]))
                if (
                    previous["content_hash"] != stored.event.content_hash
                    or previous["record_hash"] != stored.record_hash
                ):
                    raise ImportBlocked("EXISTING_EVENT_CONFLICT")
            return json.loads(previous["result_canonical"])
        if row["disposition"] in ("out_of_scope", "excluded"):
            return self._terminal(repo, principal, row, "skipped", reason=row["disposition"])
        if row["disposition"] == "covered_existing":
            self._source(session, row)
            stored = self._covered(session, decode_coverage(row["existing_coverage_canonical"]))
            return self._terminal(repo, principal, row, "covered_existing", stored)
        candidate = self._candidate(session, row, base["started_at"])
        relations = self._dependencies(session, manifest_uuid, candidate)
        ident = candidate.identity
        event = HistoricalEconomicEvent(
            ident.event_uuid,
            self.business_id,
            ident.event_type,
            ident.source.source_type,
            ident.source.source_id,
            ident.revision.value,
            candidate.dates.occurred_at,
            candidate.dates.observed_at,
            candidate.event_payload.payload,
            candidate.event_payload.payload_version,
            candidate.currency,
            relations,
        )
        events = EventsRepository(session, self.business_id)
        existing = events.find(event, operation_uuid(ident), ident.fact_slot, ident.content_hash)
        if existing:
            if len(existing) != 1:
                raise ImportBlocked("EXISTING_EVENT_CONFLICT")
            stored = self._load_event(session, str(existing[0]["event_uuid"]))
            proof = session.execute(
                "SELECT candidate_hash,raw_hash,identity_canonical FROM financial_history_import_items WHERE business_id=? AND identity_hash=? AND state='recorded'",
                (self.business_id, ident.content_hash),
            ).fetchall()
            # observed_at pertenece al primer cut y no cambia con otra incorporación.
            from dataclasses import replace

            original = replace(event, observed_at=stored.event.observed_at)
            if (
                len(proof) != 1
                or proof[0]["candidate_hash"] != candidate.content_hash
                or proof[0]["raw_hash"] != row["raw_hash"]
                or proof[0]["identity_canonical"] != ident.canonical_bytes().decode()
                or stored.origin != "historical"
                or str(stored.event.event_id) != str(event.event_id)
                or stored.operation_uuid != operation_uuid(ident)
                or original.content_hash != stored.event.content_hash
            ):
                raise ImportBlocked("EXISTING_EVENT_CONFLICT")
            return self._terminal(repo, principal, row, "existing", stored, candidate=candidate)
        context = HistoricalImportContext(
            self.business_id,
            str(cut["epoch_uuid"]),
            cut["generation"],
            manifest_uuid,
            batch_uuid,
            item_uuid,
            candidate.content_hash,
            ident.content_hash,
            principal.user_id,
            principal.session_version,
            str(event.event_id),
            operation_uuid(ident),
        )
        # Contexto cerrado vuelve a verificarse contra la fila de intent por SQL.
        session.execute(
            "UPDATE financial_history_import_batches SET state='running',updated_at=? WHERE business_id=? AND batch_uuid=?",
            (stamp(), self.business_id, batch_uuid),
        )
        last = session.execute(
            "SELECT last_sequence FROM economic_event_sequences WHERE business_id=?",
            (self.business_id,),
        ).fetchone()
        self._checkpoint("before_intent")
        request, auth = repo.intent(
            context, candidate, event, row["raw_hash"], 1 if not last else last["last_sequence"] + 1
        )
        self._checkpoint("intent")
        repo.record_operation(context, request, auth)
        self._checkpoint("operation")
        repo.record_authorization(context, request, auth)
        self._checkpoint("authorization")
        events.lock_business()
        repo.validate_context(context)
        now = stamp()
        sequence = events.next_sequence()
        for relation in event.relations:
            events.insert_link(event.event_id, relation, now)
        self._checkpoint("links")
        stored = events.insert(
            event,
            dict(
                operation_uuid=context.operation_uuid,
                event_slot=ident.fact_slot,
                authorization_uuid=auth,
                origin="historical",
                historical_batch_uuid=batch_uuid,
                provenance="historical_import_v1",
                date_precision=candidate.dates.precision.value,
                date_provenance="historical_dates_v1." + candidate.dates.legacy_kind.value,
                idempotency_key=ident.content_hash,
                business_sequence=sequence,
                recorded_at=now,
            ),
        )
        self._checkpoint("event")
        result = repo.finish(context, stored)
        self._checkpoint("result")
        return result

    def run(self, principal, batch_uuid):
        batch_uuid = uuid_text(batch_uuid)
        # Grafo O(N+E), lectura paginada y lookups PK por candidato, no scans por item.
        rows, identities = {}, {}
        after = "00000000-0000-0000-0000-000000000000"
        while True:
            with self._session(principal) as session:
                batch, _, _ = self._batch(session, batch_uuid)
                manifest_uuid = str(batch["manifest_uuid"])
                page = session.execute(
                    "SELECT item_uuid,candidate_canonical,existing_coverage_canonical,dependency_canonical FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND item_uuid>? ORDER BY item_uuid LIMIT 64",
                    (self.business_id, manifest_uuid, after),
                ).fetchall()
            if not page:
                break
            for row in page:
                from .import_contracts import identity

                uid = str(row["item_uuid"])
                # Retiene O(N+E) claves/edges; no raw ni payloads de todo el manifest.
                rows[uid] = {"dependency_canonical": row["dependency_canonical"]}
                if row["candidate_canonical"]:
                    ident = identity(json.loads(row["candidate_canonical"])["value"]["identity"])
                    identities[ident.content_hash] = uid
                elif row["existing_coverage_canonical"]:
                    identities[
                        decode_coverage(row["existing_coverage_canonical"]).identity.content_hash
                    ] = uid
                after = uid
        incoming, children = dict.fromkeys(rows, 0), {key: [] for key in rows}
        for uid, row in rows.items():
            for dep in json.loads(row["dependency_canonical"]):
                from .import_contracts import identity

                parent = identities.get(identity(dep["target"]).content_hash)
                if parent is not None:
                    incoming[uid] += 1
                    children[parent].append(uid)
        queue = deque(sorted(uid for uid, n in incoming.items() if n == 0))
        results = []
        while queue:
            uid = queue.popleft()
            results.append(self.record_item(principal, batch_uuid, uid))
            for child in children[uid]:
                incoming[child] -= 1
                if incoming[child] == 0:
                    queue.append(child)
        # Un ciclo no produce eventos; resultado separado y explícito.
        for uid, n in incoming.items():
            if n:
                with self._session(principal) as session:
                    self._batch(session, batch_uuid)
                    repo = ImportRepository(session, self.business_id, batch_uuid)
                    previous = repo.item(uid)
                    row = session.execute(
                        "SELECT * FROM financial_history_items WHERE business_id=? AND manifest_uuid=? AND item_uuid=?",
                        (self.business_id, manifest_uuid, uid),
                    ).fetchone()
                    results.append(
                        json.loads(previous["result_canonical"])
                        if previous
                        else self._terminal(
                            repo, principal, row, "blocked", reason="DEPENDENCY_CYCLE"
                        )
                    )
        with self._session(principal) as session:
            _, cut, _ = self._batch(session, batch_uuid)
            blocked = cut["result"] == "BLOCKED" or any(r["state"] == "blocked" for r in results)
            success = any(
                r["state"] in ("recorded", "existing", "covered_existing") for r in results
            )
            state = ("partial" if success else "blocked") if blocked else "completed"
            session.execute(
                "UPDATE financial_history_import_batches SET state=?,updated_at=? WHERE business_id=? AND batch_uuid=?",
                (state, stamp(), self.business_id, batch_uuid),
            )
        return dict(batch_uuid=batch_uuid, state=state, results=results, result_version=1)

    def read_batch(self, principal, batch_uuid, *, after="00000000-0000-0000-0000-000000000000"):
        """Auditoría paginada autorizada, también después de revocar el cut; sin escritura."""
        batch_uuid, after = uuid_text(batch_uuid), str(after)
        if after != "00000000-0000-0000-0000-000000000000":
            after = uuid_text(after)
        with self._session(principal) as session:
            batch = session.execute(
                "SELECT * FROM financial_history_import_batches WHERE business_id=? AND batch_uuid=?",
                (self.business_id, batch_uuid),
            ).fetchone()
            if not batch:
                raise AccessDenied("Batch del negocio requerido.")
            rows = session.execute(
                "SELECT item_uuid,result_canonical FROM financial_history_import_items WHERE business_id=? AND batch_uuid=? AND item_uuid>? ORDER BY item_uuid LIMIT 64",
                (self.business_id, batch_uuid, after),
            ).fetchall()
            return {
                "batch_uuid": batch_uuid,
                "state": batch["state"],
                "blocking_code": batch["blocking_code"],
                "blocking_item_uuid": None
                if batch["blocking_item_uuid"] is None
                else str(batch["blocking_item_uuid"]),
                "results": [json.loads(r["result_canonical"]) for r in rows],
                "next_cursor": None if len(rows) < 64 else str(rows[-1]["item_uuid"]),
            }
