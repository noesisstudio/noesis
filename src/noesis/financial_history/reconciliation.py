"""Servicio interno E: audita sin importar, reparar, reclasificar o liberar fence."""

from noesis import migrations
from noesis.financial_operations.contracts import AccessDenied, ConflictError, StateError, positive_id, uuid_text
from .canonical import version_one
from .cutoff import EpochUnavailable, HistoryCutoff
from .importer import HistoryImporter, ImportBlocked
from .reconciliation_contracts import FindingCode, digest, result_value
from .reconciliation_repository import ReconciliationRepository
from .reconciliation_schema import FINDINGS
from .reconciliation_verifier import ReconciliationVerifier


class HistoryReconciliation:
    def __init__(self, business_id, *, page_size=64):
        self.business_id = positive_id(business_id)
        if type(page_size) is not int or not 1 <= page_size <= 64:
            raise ValueError("Página de reconciliación de1 a64 requerida.")
        self.page_size = page_size
        self._cut = HistoryCutoff(self.business_id)
        self._reader = HistoryImporter(self.business_id)

    def _checkpoint(self, step):
        """Instrumentación interna de pruebas; nunca callback de canal."""

    def _context(self, session, epoch_uuid, manifest_uuid, batch_uuid):
        from .schema_compatibility import RECONCILIATION_SCHEMAS
        if migrations.current_version_connection(session.borrowed_connection) not in RECONCILIATION_SCHEMAS:
            raise StateError("Schema73 requerido.")
        batch, cut, base = self._reader._batch(session,batch_uuid)
        if str(cut["epoch_uuid"]) != epoch_uuid or str(batch["manifest_uuid"]) != manifest_uuid:
            raise ConflictError("Contexto de reconciliación distinto al batch/epoch.")
        if batch["state"] not in ("completed","partial","blocked") or session.execute(
            "SELECT 1 FROM financial_history_import_items WHERE business_id=? AND batch_uuid=? AND state='recording' LIMIT 1",
            (self.business_id,batch_uuid)).fetchone():
            raise StateError("BATCH_NOT_TERMINAL: no reconciliar durante import.")
        return batch, base

    def reconcile(self, principal, epoch_uuid, manifest_uuid, batch_uuid, reconciliation_uuid, *, reconciliation_version=1):
        version_one(reconciliation_version)
        epoch_uuid, manifest_uuid, batch_uuid, reconciliation_uuid = (
            uuid_text(u) for u in (epoch_uuid,manifest_uuid,batch_uuid,reconciliation_uuid))
        with self._cut._session(principal) as session:
            batch, base = self._context(session,epoch_uuid,manifest_uuid,batch_uuid)
            repo = ReconciliationRepository(session,self.business_id,reconciliation_uuid)
            existing = repo.load()
            if existing:
                if (str(existing["epoch_uuid"]) != epoch_uuid or str(existing["manifest_uuid"]) != manifest_uuid
                    or str(existing["batch_uuid"]) != batch_uuid or existing["generation"] != batch["generation"]
                    or existing["reconciliation_version"] != reconciliation_version or existing["source_set_hash"] != batch["source_set_hash"]
                    or existing["plan_hash"] != batch["plan_hash"]):
                    raise ConflictError("UUID E vinculada a otro contexto/hash/version.")
                result = repo.result()
                verifier = ReconciliationVerifier(session,self.business_id,batch,base,None,self._checkpoint,self.page_size)
                hashes = verifier.run()
                value = result_value(dict(existing,**hashes,result="BLOCKED" if verifier.findings else "PASS"))
                if digest(value) != existing["result_hash"]:
                    raise ConflictError("Estado actual distinto al run frozen; crear otra UUID E, sin reparar.")
            else:
                self._checkpoint("before_create")
                repo.create(principal,batch)
                self._checkpoint("created")
                verifier = ReconciliationVerifier(session,self.business_id,batch,base,repo,self._checkpoint,self.page_size)
                hashes = verifier.run()
                self._checkpoint("before_freeze")
                self._cut._permission(session,principal)
                try:
                    self._context(session,epoch_uuid,manifest_uuid,batch_uuid)
                except (EpochUnavailable,ImportBlocked,ConflictError,StateError):
                    verifier.finding(FindingCode.MANIFEST_INCONSISTENT)
                    import hashlib
                    h = hashlib.sha256(b"financial-history-findings-v1")
                    for value in sorted(verifier.findings):
                        h.update(value.encode())
                    hashes["findings_hash"] = h.hexdigest()
                result = repo.freeze(hashes,"BLOCKED" if verifier.findings else "PASS")
                self._checkpoint("frozen")
            self._last_queries = verifier.query_count
        self._checkpoint("committed")
        return result

    def read(self, principal, reconciliation_uuid, *, after=""):
        reconciliation_uuid = uuid_text(reconciliation_uuid)
        if after:
            from .canonical import sha256
            sha256(after)
        with self._cut._session(principal) as session:
            repo = ReconciliationRepository(session,self.business_id,reconciliation_uuid)
            if not repo.load():
                raise AccessDenied("Reconciliación del negocio requerida.")
            result = repo.result()
            rows = session.execute(f"SELECT evidence_canonical,finding_hash FROM {FINDINGS} WHERE business_id=? AND reconciliation_uuid=? AND finding_hash>? ORDER BY finding_hash LIMIT ?",
                (self.business_id,reconciliation_uuid,after,self.page_size)).fetchall()
            import json
            return dict(result=result,findings=[json.loads(r["evidence_canonical"]) for r in rows],
                        next_cursor=None if len(rows) < self.page_size else rows[-1]["finding_hash"])
