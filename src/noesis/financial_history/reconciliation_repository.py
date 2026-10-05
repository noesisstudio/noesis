"""Persistencia E prestada; todas sus escrituras son exclusivamente run/findings."""

from uuid import UUID, uuid5
import hashlib
import json
from noesis.financial_operations.contracts import ConflictError
from .reconciliation_contracts import ReconciliationFinding, digest, result_value
from .reconciliation_schema import RUNS, FINDINGS
from .repository import canonical, stamp


class ReconciliationRepository:
    def __init__(self, session, business_id, reconciliation_uuid):
        self.session, self.business_id, self.uuid = session, business_id, reconciliation_uuid

    @property
    def scope(self):
        return self.business_id, self.uuid

    def load(self):
        row = self.session.execute(f"SELECT * FROM {RUNS} WHERE business_id=? AND reconciliation_uuid=?", self.scope).fetchone()
        if row:
            self.manifest_uuid = str(row["manifest_uuid"])
        return row

    def create(self, principal, batch):
        self.manifest_uuid = str(batch["manifest_uuid"])
        self.session.execute(f"""INSERT INTO {RUNS}
            (business_id,reconciliation_uuid,epoch_uuid,generation,manifest_uuid,batch_uuid,reconciliation_version,
            created_by,session_version,started_at,state,source_set_hash,plan_hash)
            VALUES (?,?,?,?,?,?,1,?,?,?,'running',?,?)""",
            (*self.scope,str(batch["epoch_uuid"]),batch["generation"],str(batch["manifest_uuid"]),str(batch["batch_uuid"]),
             principal.user_id,principal.session_version,stamp(),batch["source_set_hash"],batch["plan_hash"]))

    def finding(self, finding):
        value = finding.value()
        uid = str(uuid5(UUID(self.uuid),finding.content_hash))
        self.session.execute(f"""INSERT INTO {FINDINGS}
            (business_id,reconciliation_uuid,finding_uuid,manifest_uuid,item_uuid,code,severity,finding_version,
            expected_hash,actual_hash,expected_ref,actual_ref,evidence_canonical,finding_hash,created_at)
            VALUES (?,?,?,?,?,?,'blocking',1,?,?,?,?,?,?,?) ON CONFLICT(business_id,reconciliation_uuid,finding_hash) DO NOTHING""",
            (*self.scope,uid,self.manifest_uuid,finding.item_uuid,finding.code.value,
             finding.expected_hash,finding.actual_hash,finding.expected_ref,finding.actual_ref,canonical(value),finding.content_hash,stamp()))

    def freeze(self, hashes, result):
        row = dict(self.load(),**hashes,result=result)
        value = result_value(row)
        self.session.execute(f"""UPDATE {RUNS} SET state='frozen',result=?,completed_at=?,import_set_hash=?,
            event_set_hash=?,source_recheck_hash=?,findings_hash=?,result_hash=?,result_canonical=?
            WHERE business_id=? AND reconciliation_uuid=?""",
            (result,stamp(),hashes["import_set_hash"],hashes["event_set_hash"],hashes["source_recheck_hash"],
             hashes["findings_hash"],digest(value),canonical(value),*self.scope))
        return self.result()

    def result(self):
        row = self.load()
        value = result_value(row)
        if row["state"] != "frozen" or digest(value) != row["result_hash"] or canonical(value) != row["result_canonical"]:
            raise ConflictError("Resultado E durable incoherente; no reparar.")
        h, after, count = hashlib.sha256(b"financial-history-findings-v1"), "", 0
        while True:
            page = self.session.execute(f"SELECT * FROM {FINDINGS} WHERE business_id=? AND reconciliation_uuid=? AND finding_hash>? ORDER BY finding_hash LIMIT 64", (*self.scope, after)).fetchall()
            if not page:
                break
            for finding in page:
                body = json.loads(finding["evidence_canonical"])
                f = ReconciliationFinding(**{k:body[k] for k in ("code","item_uuid","expected_hash","actual_hash","expected_ref","actual_ref","finding_version")})
                if (f.value() != body or f.content_hash != finding["finding_hash"]
                    or canonical(body) != finding["evidence_canonical"]
                    or str(finding["manifest_uuid"]) != self.manifest_uuid):
                    raise ConflictError("Finding durable incoherente; no reparar.")
                for k in ("code","item_uuid","severity","expected_hash","actual_hash","expected_ref","actual_ref","finding_version"):
                    actual = finding[k]
                    if k == "item_uuid" and actual is not None:
                        actual = str(actual)
                    if actual != body[k]:
                        raise ConflictError("Finding/columnas incoherentes; no reparar.")
                h.update(f.content_hash.encode())
                count += 1
            after = page[-1]["finding_hash"]
        if h.hexdigest() != row["findings_hash"] or (row["result"] == "PASS" and count):
            raise ConflictError("Conjunto de findings incoherente; no reparar.")
        return dict(reconciliation_uuid=self.uuid,state="frozen",**value,result_hash=row["result_hash"])
