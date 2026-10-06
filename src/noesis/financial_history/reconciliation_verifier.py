"""Auditoría SELECT por identidad; páginas de payload, índices de hashes/edges."""

from dataclasses import replace
import hashlib
import json
import struct
from datetime import datetime
from uuid import UUID, uuid5

from noesis.economic_events.persistence import StoredEvent
from noesis.financial_operations.contracts import Operation, StateError
from .classifier import revision
from .durable import HistoricalEconomicEvent, operation_uuid
from .import_contracts import candidate as decode_candidate, coverage as decode_coverage
from .import_repository import ImportRepository, result_values
from .payloads import HISTORICAL_V2
from .readers import RawReader, RawSource
from .reconciliation_contracts import FindingCode as FC, ReconciliationFinding, digest
from .repository import canonical, hash_source, HistoryRepository
from .sources import SOURCES

ERRORS = (ValueError, TypeError, KeyError, ArithmeticError, StateError)


def storage_hash(row):
    """Huella del registro observado, sin copiar strings grandes ni bins a Money."""
    values = {}
    for key, value in dict(row).items():
        if key in ('activation_generation', 'activation_capability') and value is None:
            continue  # Columnas77 aditivas: conservar hashes previos sin binding live.
        if isinstance(value, str):
            value = {"text_hash":hashlib.sha256(value.encode()).hexdigest()}
        elif isinstance(value, float):
            value = {"invalid_binary":struct.pack(">d",value).hex()}
        elif isinstance(value, datetime):
            # Timestamp físico legacy sin zona: conservarla desconocida.
            value = {"storage_timestamp":value.isoformat(timespec="microseconds")}
        elif isinstance(value,(bytes,bytearray,memoryview)):
            value = {"bytes_hash":hashlib.sha256(value).hexdigest()}
        values[key] = value
    return digest(values)


class ReconciliationVerifier:
    def __init__(self, session, business_id, batch, base, repo, checkpoint, page_size):
        self.s, self.bid, self.batch, self.base = session, business_id, batch, base
        self.repo, self.checkpoint, self.size = repo, checkpoint, page_size
        self.manifest = str(batch["manifest_uuid"])
        self.sources, self.nodes, self.events, self.identity_events = {}, {}, {}, {}
        self.explained_events, self.history_operations, self.history_authorizations = set(), set(), set()
        self.valid_history, self.links, self.deps = set(), set(), []
        self.covered_live, self.live_authority = set(), set()
        self.findings = set()
        self.query_count = 0

    def execute(self, sql, params=()):
        self.query_count += 1
        return self.s.borrowed_connection.execute_exact(sql, params)

    def pages(self, table, key, where="", params=(), columns="*"):
        # table/key provienen únicamente de llamadas internas cerradas.
        after = None
        composite = table == "economic_events"
        while True:
            sql = f"SELECT {columns} FROM {table} WHERE business_id=?" + where
            args = (self.bid,*params)
            if after is not None:
                sql += f" AND ({key}>? OR ({key}=? AND id>?))" if composite else f" AND {key}>?"
                args += (after[0], after[0], after[1]) if composite else (after,)
            rows = self.execute(sql+f" ORDER BY {key}"+(",id" if composite else "")+" LIMIT ?",(*args,self.size)).fetchall()
            if not rows:
                return
            yield rows
            after = (rows[-1][key],rows[-1]["id"]) if composite else rows[-1][key]

    def grouped(self, table, field, values, where="", columns="*", params=()):
        values = sorted({str(v) for v in values if v is not None})
        if not values:
            return []
        return self.execute(f"SELECT {columns} FROM {table} WHERE business_id=? AND {field} IN ("+
                            ",".join("?" for _ in values)+")"+where,(self.bid,*values,*params)).fetchall()

    def finding(self, code, item=None, expected=None, actual=None, ref=None):
        f = ReconciliationFinding(code,None if item is None else str(item),expected,actual,None,ref)
        if f.content_hash not in self.findings:
            if self.repo is not None:
                self.repo.finding(f)
            self.findings.add(f.content_hash)

    def manifest_index(self):
        plan = hashlib.sha256(canonical({"scope":json.loads(self.base["scope_canonical"]),
                                       "classifier_version":1,"canonical_version":1}).encode())
        try:
            frozen_hash = HistoryRepository(self.s,self.bid,self.manifest).source_set_hash()
        except ERRORS:
            frozen_hash = None
            self.finding(FC.MANIFEST_INCONSISTENT)
        if frozen_hash != self.batch["source_set_hash"]:
            self.finding(FC.MANIFEST_INCONSISTENT,expected=self.batch["source_set_hash"],actual=frozen_hash)
        for page in self.pages("financial_history_items","item_uuid"," AND manifest_uuid=?",(self.manifest,)):
            incidences = self.grouped("financial_history_incidences","item_uuid",[r["item_uuid"] for r in page],
                                     " AND manifest_uuid=? ORDER BY item_uuid,code", "item_uuid,code,severity,evidence_hash,rule_version", (self.manifest,))
            incs = {}
            for inc in incidences:
                incs.setdefault(str(inc["item_uuid"]),[]).append({k:inc[k] for k in ("code","severity","evidence_hash","rule_version")})
                if inc["severity"] == "blocking":
                    self.finding(FC.BLOCKING_HISTORY_REMAINS,inc["item_uuid"])
            for row in page:
                uid = str(row["item_uuid"])
                plan.update(canonical({key:row[key] for key in ("item_uuid","revision_canonical","raw_hash","assessment_canonical",
                    "disposition","candidate_hash","dependency_canonical","unresolved_dependency_canonical","existing_coverage_canonical","terminal_result")}
                    | {"incidences":incs.get(uid,[])}).encode())
                try:
                    raw = RawSource.from_canonical(row["raw_canonical"])
                    if raw.content_hash != row["raw_hash"] or raw.business_id != self.bid or canonical(raw.key) != row["source_key"] or revision(raw).canonical_bytes().decode() != row["revision_canonical"]:
                        raise ValueError("Raw/identidad incoherentes.")
                    source_key = (raw.source_kind,canonical(raw.key))
                    value = dict(hash=raw.content_hash, revision=canonical(revision(raw)),
                                 fiscal_valid=raw.fields.get("fiscal_hash_valid"), uid=uid)
                    if source_key in self.sources and self.sources[source_key]["hash"] != raw.content_hash:
                        raise ValueError("Slots contradictorios.")
                    self.sources[source_key] = value
                    node = dict(uid=uid,classification=row["classification"],severity=row["severity"],
                                source_type=row["source_type"],source_id=row["source_id"],fact_slot=row["fact_slot"])
                    if row["candidate_canonical"]:
                        c = decode_candidate(row["candidate_canonical"],self.base["started_at"])
                        if c.content_hash != row["candidate_hash"] or c.assessment.canonical_bytes().decode() != row["assessment_canonical"] or canonical(c.dependencies) != row["dependency_canonical"]:
                            raise ValueError("Candidato/hash incoherente.")
                        self.candidate_source(c,raw,row)
                        node["identity"] = c.identity
                    elif row["existing_coverage_canonical"]:
                        node["identity"] = decode_coverage(row["existing_coverage_canonical"]).identity
                    if "identity" in node:
                        if node["identity"].content_hash in self.nodes:
                            self.finding(FC.MANIFEST_INCONSISTENT,uid)
                        self.nodes[node["identity"].content_hash] = node
                except ERRORS:
                    self.finding(FC.MANIFEST_INCONSISTENT,uid)
            self.checkpoint("manifest_page")
        if plan.hexdigest() != self.batch["plan_hash"]:
            self.finding(FC.MANIFEST_INCONSISTENT,expected=self.batch["plan_hash"],actual=plan.hexdigest())

    def candidate_source(self,c,raw,row):
        """Solo contraste congelado: no reclasifica ni redondea el raw observado."""
        if (c.identity.revision != revision(raw) or c.evidence.revision != revision(raw)
            or str(c.identity.source.source_id) != raw.source_id or c.identity.source.source_type.value != raw.source_kind
            or c.identity.fact_slot != row["fact_slot"] or c.identity.event_type.value != row["proposed_event_type"]
            or c.assessment.classification.value != row["classification"]):
            raise ValueError("Identidad/candidato/raw incoherente.")
        fields = {"received_invoice":{"total":"total","base":"base","vat_amount":"vat_amount","irpf_amount":"irpf_amount"},
                  "expense":{"total":"amount","vat_amount":"_captured_vat_amount"},
                  "invoice_payment":{"amount":"amount"},"bank_transaction":{"amount":"amount"},
                  "invoice":{"base":"base","vat_amount":"vat_amount","irpf_amount":"irpf_amount","total":"total"}}
        for payload_field, raw_field in fields.get(raw.source_kind,{}).items():
            if payload_field in c.evidence.money and c.evidence.money[payload_field] != raw.money[raw_field].evidence:
                raise ValueError("Dinero raw distinto de evidencia congelada.")
        f, payload = raw.fields,c.event_payload.payload
        comparisons = {"received_invoice":{"invoice_number":f.get("number"),"issued_on":f.get("issued_on"),"due_on":f.get("due_on")},
                       "expense":{"description":f.get("concept"),"spent_on":None if f.get("spent_on") is None else f["spent_on"][:10]},
                       "invoice_payment":{"invoice_id":f.get("invoice_id"),"method":f.get("method"),"received_on":None if f.get("paid_at") is None else f["paid_at"][:10]},
                       "invoice_cancellation_record":{"invoice_id":f.get("invoice_id"),"invoice_number":f.get("invoice_number"),"reason":f.get("reason"),"registered_on":f.get("generated_at","")[:10]}}
        if c.identity.event_type.value == "bank_transaction.imported":
            comparisons["bank_transaction"] = {"booked_on":f["booked_on"]}
        if any(payload.get(k) != v for k,v in comparisons.get(raw.source_kind,{}).items()):
            raise ValueError("Payload semántico distinto del raw congelado.")
        if c.evidence.references:
            raise ValueError("Referencias no acreditadas por el scanner vigente.")

    def events_index(self):
        event_hash = hashlib.sha256(b"financial-history-events-v1")
        previous = 0
        for page in self.pages("economic_events","business_sequence"):
            ids = [r["event_uuid"] for r in page]
            links = self.grouped("economic_event_links","event_uuid",ids)
            by_links = {}
            for link in links:
                by_links.setdefault(str(link["event_uuid"]),set()).add((link["relation_type"],str(link["target_event_uuid"])))
            ops = {str(r["operation_uuid"]):r for r in self.grouped("financial_operations","operation_uuid",[r["operation_uuid"] for r in page])}
            auth_rows = self.grouped("financial_authorizations","operation_uuid",list(ops))
            auths = {}
            for auth in auth_rows:
                auths.setdefault(str(auth["operation_uuid"]),[]).append(auth)
            proofs = self.grouped("financial_history_import_items","event_uuid",ids," AND state='recorded'")
            by_proof = {}
            for proof in proofs:
                by_proof.setdefault(str(proof["event_uuid"]),[]).append(proof)
            originals = self.execute("""SELECT i.*, m.started_at AS observation, x.event_uuid AS proof_event_uuid
                FROM financial_history_import_items x
                JOIN financial_history_items i ON i.business_id=x.business_id AND i.manifest_uuid=x.manifest_uuid AND i.item_uuid=x.item_uuid
                JOIN financial_history_manifests m ON m.business_id=i.business_id AND m.manifest_uuid=i.manifest_uuid
                JOIN financial_history_import_batches b ON b.business_id=x.business_id AND b.manifest_uuid=x.manifest_uuid AND b.batch_uuid=x.batch_uuid
                JOIN financial_history_cut_manifests c ON c.business_id=b.business_id AND c.manifest_uuid=b.manifest_uuid AND c.epoch_uuid=b.epoch_uuid AND c.generation=b.generation
                WHERE x.business_id=? AND x.state='recorded' AND x.event_uuid IN ("""+",".join("?" for _ in ids)+") AND m.status='frozen' AND c.status='frozen' AND c.certifiable=TRUE AND b.source_set_hash=m.source_set_hash AND b.plan_hash=m.plan_hash AND c.source_set_hash=m.source_set_hash AND c.plan_hash=m.plan_hash",
                (self.bid,*(str(v) for v in ids))).fetchall()
            originals = {str(r["proof_event_uuid"]):r for r in originals}
            for row in page:
                uid = str(row["event_uuid"])
                op = ops.get(str(row["operation_uuid"]))
                ars = auths.get(str(row["operation_uuid"]),[])
                rels = by_links.get(uid,set())
                event_hash.update(canonical(dict(event=storage_hash(row),operation=None if op is None else storage_hash(op),
                    authorizations=sorted(storage_hash(a) for a in ars),links=sorted(rels),proofs=sorted(storage_hash(p) for p in by_proof.get(uid,[])))).encode())
                sequence = row["business_sequence"]
                if type(sequence) is not int or sequence != previous+1:
                    self.finding(FC.SEQUENCE_CONFLICT,ref=uid)
                previous = sequence
                key = (row["source_type"],row["source_id"],row["source_revision"],row["event_type"])
                if key in self.identity_events:
                    self.finding(FC.EVENT_CONTENT_CONFLICT,ref=uid)
                self.identity_events[key] = uid
                try:
                    stored = StoredEvent.from_row(row)
                    e = stored.event
                    if rels != {(r.kind.value,str(r.target_event_id)) for r in e.relations}:
                        self.finding(FC.DEPENDENCY_CONFLICT,ref=uid)
                    self.events[uid] = dict(source_type=e.source_type.value,source_id=e.source_id,revision=e.source_revision,
                        type=e.event_type.value,hash=e.content_hash,record_hash=stored.record_hash,origin=stored.origin,
                        batch=stored.historical_batch_uuid,op=stored.operation_uuid,auth=stored.authorization_uuid,
                        slot=stored.event_slot,links=rels)
                    self.links.update((uid,*r) for r in rels)
                    if stored.origin == "historical":
                        if self.historical(stored,op,ars,by_proof.get(uid,[]),originals.get(uid)):
                            self.valid_history.add(uid)
                    elif op is not None:
                        operation = Operation.from_row(op)
                        authorization = next((a for a in ars if str(a["authorization_uuid"]) == stored.authorization_uuid),None)
                        if (op["state"] != "committed" or not authorization or authorization["kind"] not in ("human_confirmation","mandate")
                            or op["entry_namespace"] == "historical" or authorization["channel"] == "historical"
                            or type(authorization["actor_user_id"]) is not int or authorization["actor_user_id"] <= 0
                            or type(authorization["actor_session_version"]) is not int or authorization["actor_session_version"] < 0
                            or authorization["recorded_by"] != authorization["actor_user_id"]
                            or authorization["validated_permission"] != ("financial.authorize" if authorization["kind"] == "human_confirmation" else "financial.mandate")
                            or str(op["authorization_uuid"]) != stored.authorization_uuid
                            or authorization["approved_request_hash"] != operation.request.request_hash
                            or authorization["approved_revision"] != operation.request.expected_revision):
                            self.finding(FC.LIVE_COVERAGE_CONTAMINATION,ref=uid)
                        else:
                            self.live_authority.add(uid)
                except ERRORS:
                    self.finding(FC.EVENT_CONTENT_CONFLICT,ref=uid)
            self.checkpoint("event_page")
        last = self.execute("SELECT last_sequence FROM economic_event_sequences WHERE business_id=?",(self.bid,)).fetchone()
        if (0 if not last else last["last_sequence"]) != previous:
            self.finding(FC.SEQUENCE_CONFLICT)
        # Relaciones huérfanas también se buscan fuera de las páginas de eventos.
        if self.execute("SELECT 1 FROM economic_event_links l LEFT JOIN economic_events e ON e.business_id=l.business_id AND e.event_uuid=l.event_uuid LEFT JOIN economic_events t ON t.business_id=l.business_id AND t.event_uuid=l.target_event_uuid WHERE l.business_id=? AND (e.event_uuid IS NULL OR t.event_uuid IS NULL) LIMIT 1",(self.bid,)).fetchone():
            self.finding(FC.DEPENDENCY_CONFLICT)
        return event_hash

    def historical(self, stored, op, auths, proofs, original):
        uid = str(stored.event.event_id)
        before = len(self.findings)
        if len(proofs) != 1:
            self.finding(FC.UNEXPECTED_HISTORICAL_EVENT,ref=uid)
            return False
        proof = proofs[0]
        self.history_operations.add(stored.operation_uuid)
        self.history_authorizations.add(stored.authorization_uuid)
        try:
            if not original:
                raise ValueError("Sin cadena original.")
            c = decode_candidate(original["candidate_canonical"],original["observation"])
            raw = RawSource.from_canonical(original["raw_canonical"])
            if raw.content_hash != original["raw_hash"]:
                raise ValueError("Raw original incoherente.")
            self.candidate_source(c,raw,original)
            ident = c.identity
            self.events[uid]["classification"] = c.assessment.classification.value
            expected = HistoricalEconomicEvent(ident.event_uuid,self.bid,ident.event_type,ident.source.source_type,
                ident.source.source_id,ident.revision.value,c.dates.occurred_at,c.dates.observed_at,c.event_payload.payload,
                c.event_payload.payload_version,c.currency,stored.event.relations)
            if (expected.content_hash != stored.event.content_hash or c.content_hash != proof["candidate_hash"]
                or c.content_hash != original["candidate_hash"] or proof["raw_hash"] != original["raw_hash"]
                or proof["identity_hash"] != ident.content_hash or proof["identity_canonical"] != ident.canonical_bytes().decode()
                or proof["expected_event_canonical"] != expected.canonical_bytes().decode()
                or proof["content_hash"] != stored.event.content_hash or proof["record_hash"] != stored.record_hash
                or str(proof["event_uuid"]) != uid or str(proof["operation_uuid"]) != stored.operation_uuid
                or str(proof["authorization_uuid"]) != stored.authorization_uuid
                or proof["expected_sequence"] != stored.business_sequence or proof["completed_at"] is None
                or proof["completion_key"] != "recorded" or proof["reason"] is not None
                or str(proof["batch_uuid"]) != stored.historical_batch_uuid or str(proof["expected_event_uuid"]) != uid
                or stored.event_slot != ident.fact_slot or stored.idempotency_key != ident.content_hash
                or stored.provenance != "historical_import_v1" or stored.date_precision != c.dates.precision.value
                or stored.date_provenance != "historical_dates_v1."+c.dates.legacy_kind.value):
                raise ValueError("Evento/proof original incompatible.")
            self.deps.append((uid,c.dependencies))
            request = ImportRepository(self.s,self.bid,str(proof["batch_uuid"])).request(c)
            if (not op or str(op["operation_uuid"]) != operation_uuid(ident) or op["entry_namespace"] != "historical"
                or op["state"] != "prepared" or op["entry_key"] != ident.content_hash or op["created_by"] != proof["recorded_by"]
                or op["result_canonical"] is not None or op["committed_at"] is not None
                or op["request_canonical"] != request.canonical() or op["request_hash"] != request.request_hash
                or proof["expected_request_canonical"] != request.canonical()
                or str(proof["expected_operation_uuid"]) != stored.operation_uuid):
                self.finding(FC.OPERATION_CONFLICT,ref=uid)
            else:
                Operation.from_row(op)
            a = auths[0] if len(auths) == 1 else None
            expected_auth = str(uuid5(UUID(operation_uuid(ident)),"historical-authorization-v1"))
            if (not a or str(a["authorization_uuid"]) != expected_auth or stored.authorization_uuid != expected_auth
                or str(proof["expected_authorization_uuid"]) != expected_auth or a["kind"] != "historical_unknown"
                or a["actor_user_id"] is not None or a["actor_session_version"] is not None
                or a["mandate_uuid"] is not None or a["expires_at"] is not None or a["revoked_at"] is not None
                or a["recorded_by"] != proof["recorded_by"] or a["validated_permission"] != "historical.record"
                or a["channel"] != "historical" or a["approved_request_hash"] != request.request_hash
                or a["approved_revision"] != request.expected_revision
                or not op or str(op["authorization_uuid"]) != expected_auth):
                self.finding(FC.AUTHORIZATION_CONFLICT,ref=uid)
            if json.loads(proof["result_canonical"]) != result_values(str(proof["item_uuid"]),"recorded",stored):
                self.finding(FC.IMPORT_RESULT_CONFLICT,ref=uid)
        except ERRORS:
            self.finding(FC.EVENT_CONTENT_CONFLICT,ref=uid)
        return len(self.findings) == before

    def matches(self, ident, event):
        return (ident.source.business_id == self.bid and event["source_type"] == ident.source.source_type.value
                and event["source_id"] == ident.source.source_id and event["revision"] == ident.revision.value
                and event["type"] == ident.event_type.value)

    def item_accounting(self):
        import_hash = hashlib.sha256(b"financial-history-import-v1")
        for page in self.pages("financial_history_import_items","item_uuid"," AND batch_uuid=?",(str(self.batch["batch_uuid"]),)):
            for result in page:
                import_hash.update(canonical({f:result[f] for f in ("item_uuid","identity_hash","candidate_hash","state","event_uuid",
                    "content_hash","record_hash","operation_uuid","authorization_uuid")}).encode())
                if str(result["manifest_uuid"]) != self.manifest:
                    self.finding(FC.IMPORT_ITEM_UNEXPECTED)
                if result["state"] == "recording":
                    self.finding(FC.IMPORT_RESULT_CONFLICT,result["item_uuid"])
                expected_result = dict(result_version=1,item_uuid=str(result["item_uuid"]),state=result["state"],reason=result["reason"],
                    **{f:result[f] if f not in ("event_uuid","operation_uuid","authorization_uuid") or result[f] is None else str(result[f]) for f in
                       ("event_uuid","operation_uuid","authorization_uuid","content_hash","record_hash")})
                try:
                    if (result["completion_key"] != result["state"] or result["completed_at"] is None
                        or canonical(expected_result) != result["result_canonical"]
                        or result["state"] in ("skipped","blocked") and any(result[f] is not None for f in
                            ("event_uuid","operation_uuid","authorization_uuid","content_hash","record_hash"))):
                        self.finding(FC.IMPORT_RESULT_CONFLICT,result["item_uuid"])
                except ERRORS:
                    self.finding(FC.IMPORT_RESULT_CONFLICT,result["item_uuid"])
        if self.execute("SELECT 1 FROM financial_history_import_items x LEFT JOIN financial_history_items i ON i.business_id=x.business_id AND i.manifest_uuid=x.manifest_uuid AND i.item_uuid=x.item_uuid WHERE x.business_id=? AND x.batch_uuid=? AND i.item_uuid IS NULL LIMIT 1",(self.bid,str(self.batch["batch_uuid"]))).fetchone():
            self.finding(FC.IMPORT_ITEM_UNEXPECTED)
        for page in self.pages("financial_history_items","item_uuid"," AND manifest_uuid=?",(self.manifest,)):
            results = {str(r["item_uuid"]):r for r in self.grouped("financial_history_import_items","item_uuid",[r["item_uuid"] for r in page]," AND batch_uuid=?",params=(str(self.batch["batch_uuid"]),))}
            durable_rows = {str(r["event_uuid"]):r for r in self.grouped("economic_events","event_uuid",[r["event_uuid"] for r in results.values()])}
            for row in page:
                uid = str(row["item_uuid"])
                r = results.get(uid)
                event = None if not r or not r["event_uuid"] else self.events.get(str(r["event_uuid"]))
                try:
                    ident = None
                    if row["candidate_canonical"]:
                        c = decode_candidate(row["candidate_canonical"],self.base["started_at"])
                        ident = c.identity
                    elif row["existing_coverage_canonical"]:
                        coverage = decode_coverage(row["existing_coverage_canonical"])
                        ident = coverage.identity
                    if row["classification"] in ("C","D") or row["terminal_result"] == "blocked" or json.loads(row["unresolved_dependency_canonical"]):
                        self.finding(FC.BLOCKING_HISTORY_REMAINS,uid)
                    if row["disposition"] in ("out_of_scope","excluded") and row["proposed_event_type"]:
                        raw = RawSource.from_canonical(row["raw_canonical"])
                        logical = (row["source_type"],int(row["source_id"]),revision(raw).value,row["proposed_event_type"])
                        if logical in self.identity_events:
                            self.finding(FC.UNEXPECTED_HISTORICAL_EVENT,uid)
                    if not r:
                        if row["disposition"] in ("candidate","covered_existing"):
                            self.finding(FC.IMPORT_ITEM_MISSING,uid)
                        continue
                    if r["raw_hash"] != row["raw_hash"] or r["candidate_hash"] != row["candidate_hash"] or str(r["manifest_uuid"]) != self.manifest:
                        self.finding(FC.IMPORT_RESULT_CONFLICT,uid)
                    terminal = r["state"]
                    if row["disposition"] in ("out_of_scope","excluded"):
                        if terminal != "skipped" or event is not None or r["event_uuid"] is not None:
                            self.finding(FC.IMPORT_RESULT_CONFLICT,uid)
                        continue
                    if terminal in ("blocked","skipped"):
                        self.finding(FC.BLOCKING_HISTORY_REMAINS,uid)
                        continue
                    if terminal not in ("recorded","existing","covered_existing") or ident is None:
                        self.finding(FC.IMPORT_RESULT_CONFLICT,uid)
                        continue
                    if event is None:
                        self.finding(FC.EVENT_MISSING,uid)
                        continue
                    if not self.matches(ident,event) or event["hash"] != r["content_hash"] or event["record_hash"] != r["record_hash"] or event["op"] != str(r["operation_uuid"]) or event["auth"] != str(r["authorization_uuid"]):
                        self.finding(FC.IMPORT_RESULT_CONFLICT,uid)
                    if row["disposition"] == "covered_existing":
                        if terminal != "covered_existing" or str(coverage.event_uuid) != str(r["event_uuid"]) or coverage.event_content_hash != event["hash"] or coverage.origin.value != event["origin"]:
                            self.finding(FC.EXISTING_COVERAGE_CONFLICT,uid)
                    elif row["disposition"] != "candidate" or terminal == "covered_existing":
                        self.finding(FC.IMPORT_RESULT_CONFLICT,uid)
                    else:
                        if event["origin"] != "historical" or str(r["event_uuid"]) != str(ident.event_uuid) or r["identity_hash"] != ident.content_hash:
                            self.finding(FC.IMPORT_RESULT_CONFLICT,uid)
                        if terminal == "recorded" and event["batch"] != str(self.batch["batch_uuid"]):
                            self.finding(FC.IMPORT_RESULT_CONFLICT,uid)
                        if c.assessment.classification.value not in ("A","B") or c.event_payload.payload_version == 2 and c.event_payload.event_type not in HISTORICAL_V2:
                            self.finding(FC.BLOCKING_HISTORY_REMAINS,uid)
                        whitelist = c.event_payload.payload_version == 2 and c.event_payload.event_type in HISTORICAL_V2 and row["terminal_result"] == "not_durably_supported"
                        if not whitelist and (row["severity"] == "blocking" or row["terminal_result"] != "planned_diagnostic"):
                            self.finding(FC.BLOCKING_HISTORY_REMAINS,uid)
                        stored = StoredEvent.from_row(durable_rows[str(r["event_uuid"])])
                        expected = HistoricalEconomicEvent(ident.event_uuid,self.bid,ident.event_type,ident.source.source_type,
                            ident.source.source_id,ident.revision.value,c.dates.occurred_at,stored.event.observed_at,c.event_payload.payload,
                            c.event_payload.payload_version,c.currency,stored.event.relations)
                        if expected.content_hash != event["hash"]:
                            self.finding(FC.EVENT_CONTENT_CONFLICT,uid)
                    if event["origin"] == "historical" and str(r["event_uuid"]) not in self.valid_history:
                        self.finding(FC.EVENT_CONTENT_CONFLICT,uid)
                    expected_result = dict(result_version=1,item_uuid=uid,state=terminal,reason=r["reason"],
                        **{f:r[f] if f not in ("event_uuid","operation_uuid","authorization_uuid") or r[f] is None else str(r[f]) for f in
                           ("event_uuid","operation_uuid","authorization_uuid","content_hash","record_hash")})
                    if json.loads(r["result_canonical"]) != expected_result:
                        self.finding(FC.IMPORT_RESULT_CONFLICT,uid)
                    self.explained_events.add(str(r["event_uuid"]))
                    if ident.content_hash in self.nodes:
                        self.nodes[ident.content_hash]["event"] = str(r["event_uuid"])
                except ERRORS:
                    self.finding(FC.MANIFEST_INCONSISTENT,uid)
            self.checkpoint("import_page")
        if self.batch["state"] == "blocked" or self.batch["blocking_code"]:
            self.finding(FC.BLOCKING_HISTORY_REMAINS)
        return import_hash

    def dependency_graph(self):
        for uid,deps in self.deps:
            actual = self.events[uid]["links"]
            if len(actual) != len(deps):
                self.finding(FC.DEPENDENCY_CONFLICT,ref=uid)
            for dep in deps:
                target = next((t for kind,t in actual if kind == dep.relation.value),None)
                event = self.events.get(target)
                if (not dep.satisfied or not event or not self.matches(dep.target,event)
                    or event["origin"] == "historical" and (target not in self.valid_history or event.get("classification") != "A")
                    or event["origin"] == "live" and target not in self.covered_live):
                    self.finding(FC.DEPENDENCY_CONFLICT,ref=uid)
                node = self.nodes.get(dep.target.content_hash)
                if node and (node["classification"] != "A" or node.get("event") != target or node["severity"] == "blocking"):
                    self.finding(FC.DEPENDENCY_CONFLICT,node["uid"],ref=uid)
        # Grafo de todo el conjunto EE: Kahn detecta ciclos sin O(N²).
        from collections import deque
        degree, children = dict.fromkeys(self.events,0), {u:[] for u in self.events}
        for uid,event in self.events.items():
            for _,target in event["links"]:
                if target not in self.events:
                    self.finding(FC.DEPENDENCY_CONFLICT,ref=uid)
                else:
                    degree[uid] += 1
                    children[target].append(uid)
        queue = deque(u for u,d in degree.items() if not d)
        visited = 0
        while queue:
            parent = queue.popleft()
            visited += 1
            for child in children[parent]:
                degree[child] -= 1
                if not degree[child]:
                    queue.append(child)
        if visited != len(self.events):
            self.finding(FC.DEPENDENCY_CONFLICT)

    def source_recheck(self):
        reader = RawReader(self.s,self.bid,page_size=self.size,cut_scope=True)
        recheck = hashlib.sha256(canonical({"scope_version":1,"reader_version":1}).encode())
        seen = set()
        for kind in sorted(SOURCES):
            after = None
            while True:
                fiscal = kind in ("invoice_record","invoice_cancellation_record")
                page = reader._rows(kind,after=after,frozen_fiscal_valid=False) if fiscal else reader.page(kind,after)
                if not page:
                    break
                for raw in page:
                    key = (kind,canonical(raw.key))
                    frozen = self.sources.get(key)
                    if fiscal and frozen:
                        raw = replace(raw,fields=dict(raw.fields,fiscal_hash_valid=frozen["fiscal_valid"]))
                        if frozen["fiscal_valid"] is not True:
                            self.finding(FC.FISCAL_REFERENCE_CONFLICT,frozen["uid"])
                    if not frozen and kind == "economic_event" and str(raw.fields["event_uuid"]) in self.valid_history & self.explained_events:
                        continue
                    if not frozen and kind == "economic_event_link" and (str(raw.fields["event_uuid"]),raw.fields["relation_type"],str(raw.fields["target_event_uuid"])) in self.links and str(raw.fields["event_uuid"]) in self.valid_history & self.explained_events:
                        continue
                    hash_source(recheck,raw)
                    seen.add(key)
                    if not frozen or raw.content_hash != frozen["hash"] or canonical(revision(raw)) != frozen["revision"]:
                        self.finding(FC.SOURCE_DRIFT,None if not frozen else frozen["uid"],None if not frozen else frozen["hash"],raw.content_hash)
                        if fiscal:
                            self.finding(FC.FISCAL_REFERENCE_CONFLICT,None if not frozen else frozen["uid"])
                    if kind.endswith("coverage"):
                        event = self.events.get(str(raw.fields.get("event_uuid")))
                        source_fields = {"invoice_coverage":("invoice","invoice_id"),"payment_coverage":("invoice_payment","payment_id"),
                                         "bank_import_coverage":("bank_transaction","bank_transaction_id"),"bank_match_coverage":("bank_transaction","bank_transaction_id"),
                                         "supplier_coverage":("received_invoice","source_id"),"expense_coverage":("expense","source_id")}
                        source_type, source_field = source_fields[kind]
                        if (not event or event["origin"] != "live" or raw.fields.get("operation_state") != "committed"
                            or str(raw.fields.get("operation_uuid")) != event["op"] or raw.fields.get("event_type") != event["type"]
                            or event["source_type"] != source_type or event["source_id"] != raw.fields[source_field]
                            or str(raw.fields.get("event_uuid")) not in self.live_authority
                            or "source_revision" in raw.fields and str(raw.fields["source_revision"]) != str(event["revision"])):
                            self.finding(FC.LIVE_COVERAGE_CONTAMINATION)
                        elif kind == "bank_match_coverage" and event["links"] != {("matches",str(raw.fields["payment_event_uuid"])),("evidence_for",str(raw.fields["imported_event_uuid"]))}:
                            self.finding(FC.LIVE_COVERAGE_CONTAMINATION)
                        else:
                            self.covered_live.add(str(raw.fields["event_uuid"]))
                after = page[-1].key
                self.checkpoint("source_page")
        for key in self.sources.keys()-seen:
            self.finding(FC.SOURCE_DRIFT,self.sources[key]["uid"],self.sources[key]["hash"])
        if recheck.hexdigest() != self.batch["source_set_hash"]:
            self.finding(FC.SOURCE_DRIFT,expected=self.batch["source_set_hash"],actual=recheck.hexdigest())
        return recheck

    def orphan_checks(self, event_hash):
        after = None
        while True:
            sql = "SELECT x.*,i.raw_hash AS original_raw_hash,i.candidate_hash AS original_candidate_hash,b.manifest_uuid AS batch_manifest FROM financial_history_import_items x LEFT JOIN financial_history_items i ON i.business_id=x.business_id AND i.manifest_uuid=x.manifest_uuid AND i.item_uuid=x.item_uuid LEFT JOIN financial_history_import_batches b ON b.business_id=x.business_id AND b.batch_uuid=x.batch_uuid WHERE x.business_id=?"
            args = (self.bid,)
            if after:
                sql += " AND (x.batch_uuid>? OR (x.batch_uuid=? AND x.item_uuid>?))"
                args += (after[0],after[0],after[1])
            page = self.execute(sql+" ORDER BY x.batch_uuid,x.item_uuid LIMIT ?",(*args,self.size)).fetchall()
            if not page:
                break
            for row in page:
                # No payloads retenidos; compromete también alias de batches previos.
                event_hash.update(canonical({"import_proof":storage_hash(row)}).encode())
                try:
                    expected = dict(result_version=1,item_uuid=str(row["item_uuid"]),state=row["state"],reason=row["reason"],
                        **{f:str(row[f]) if f.endswith("uuid") and row[f] is not None else row[f] for f in
                           ("event_uuid","operation_uuid","authorization_uuid","content_hash","record_hash")})
                    if (row["original_raw_hash"] != row["raw_hash"] or row["original_candidate_hash"] != row["candidate_hash"]
                        or str(row["batch_manifest"]) != str(row["manifest_uuid"]) or row["state"] == "recording"
                        or row["completion_key"] != row["state"] or row["completed_at"] is None
                        or canonical(expected) != row["result_canonical"]):
                        self.finding(FC.IMPORT_RESULT_CONFLICT,ref=str(row["batch_uuid"]))
                    if row["state"] in ("recorded","existing","covered_existing"):
                        event = self.events.get(str(row["event_uuid"]))
                        if not event:
                            self.finding(FC.EVENT_MISSING,ref=str(row["batch_uuid"]))
                        elif (event["hash"] != row["content_hash"] or event["record_hash"] != row["record_hash"]
                              or event["op"] != str(row["operation_uuid"]) or event["auth"] != str(row["authorization_uuid"])):
                            self.finding(FC.IMPORT_RESULT_CONFLICT,ref=str(row["batch_uuid"]))
                except ERRORS:
                    self.finding(FC.IMPORT_RESULT_CONFLICT,ref=str(row["batch_uuid"]))
            after = (page[-1]["batch_uuid"],page[-1]["item_uuid"])
        for page in self.pages("financial_operations","operation_uuid"," AND entry_namespace='historical'"):
            for row in page:
                event_hash.update(canonical({"historical_operation":storage_hash(row)}).encode())
                if str(row["operation_uuid"]) not in self.history_operations:
                    self.finding(FC.OPERATION_CONFLICT,ref=str(row["operation_uuid"]))
        for page in self.pages("financial_authorizations","authorization_uuid"," AND kind='historical_unknown'"):
            for row in page:
                event_hash.update(canonical({"historical_authorization":storage_hash(row)}).encode())
                if str(row["authorization_uuid"]) not in self.history_authorizations:
                    self.finding(FC.AUTHORIZATION_CONFLICT,ref=str(row["authorization_uuid"]))
        for uid,e in self.events.items():
            if e["origin"] == "historical" and uid not in self.valid_history:
                self.finding(FC.UNEXPECTED_HISTORICAL_EVENT,ref=uid)
        if self.execute("SELECT 1 FROM financial_history_import_items x LEFT JOIN economic_events e ON e.business_id=x.business_id AND e.event_uuid=x.event_uuid WHERE x.business_id=? AND x.state='recorded' AND e.event_uuid IS NULL LIMIT 1",(self.bid,)).fetchone():
            self.finding(FC.EVENT_MISSING)
        if self.execute("SELECT 1 FROM financial_history_import_batches b LEFT JOIN financial_history_cut_manifests m ON m.business_id=b.business_id AND m.manifest_uuid=b.manifest_uuid AND m.epoch_uuid=b.epoch_uuid AND m.generation=b.generation LEFT JOIN financial_history_epochs e ON e.business_id=b.business_id AND e.epoch_uuid=b.epoch_uuid AND e.generation=b.generation WHERE b.business_id=? AND (m.manifest_uuid IS NULL OR e.epoch_uuid IS NULL OR m.source_set_hash<>b.source_set_hash OR m.plan_hash<>b.plan_hash) LIMIT 1",(self.bid,)).fetchone():
            self.finding(FC.MANIFEST_INCONSISTENT)

    def run(self):
        self.manifest_index()
        event_hash = self.events_index()
        import_hash = self.item_accounting()
        self.orphan_checks(event_hash)
        recheck = self.source_recheck()
        self.dependency_graph()
        findings_hash = hashlib.sha256(b"financial-history-findings-v1")
        for value in sorted(self.findings):
            findings_hash.update(value.encode())
        return dict(import_set_hash=import_hash.hexdigest(),event_set_hash=event_hash.hexdigest(),
                    source_recheck_hash=recheck.hexdigest(),findings_hash=findings_hash.hexdigest())
