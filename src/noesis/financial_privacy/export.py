"""FinancialEvidenceExport v1: una conexión/snapshot; sin writer gate de lectura."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from uuid import uuid4

from noesis import db
from noesis.core.locks import lock_business
from noesis.core.persistence import FinancialSession
from noesis.financial_operations.contracts import ConflictError, StateError
from .catalog import COLUMNS, FINANCIAL_TABLES, LEGACY_KEYS
from .contracts import CANONICAL_VERSION, Purpose, canonical, digest, evidence_value, export_identity
from .repository import PrivacyRepository, installed
from .schema import EXPORTS, TABLES, RESTORED


@contextmanager
def snapshot():
    """El propietario exterior fija aislamiento antes de cualquier SELECT."""
    with db.get_conn() as conn:
        if conn.dialect == "postgres":
            conn.execute_exact("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        else:
            conn.execute_exact("BEGIN")
        yield FinancialSession(conn)


def _columns(session, table):
    if table == RESTORED:
        return ("business_id", "evidence_uuid", "scope", "client_id", "body_canonical", "content_hash")
    if table in TABLES:
        return ("business_id", "evidence_uuid", "contract_version", "created_by", "session_version", "created_at", "body_canonical", "content_hash")
    return COLUMNS[table]


def _client_scope(table):
    """Subgrafo por FKs fuertes, nunca por sugerencias ni texto del payload."""
    invoices = "SELECT id FROM invoices WHERE business_id=? AND client_id=?"
    ik = ("bid", "cid")
    payments = f"SELECT id FROM invoice_payments WHERE business_id=? AND invoice_id IN ({invoices})"
    pk = ("bid",) + ik
    banks = f"SELECT bank_transaction_id FROM bank_payment_links WHERE business_id=? AND payment_id IN ({payments})"
    bk = ("bid",) + pk
    cancellations = f"SELECT id FROM invoice_cancellation_records WHERE business_id=? AND invoice_id IN ({invoices})"
    ck = ("bid",) + ik
    source = f"(invoice_id IN ({invoices}) OR invoice_payment_id IN ({payments}) OR bank_transaction_id IN ({banks}) OR invoice_cancellation_record_id IN ({cancellations}))"
    sk = ik + pk + bk + ck
    events = f"SELECT event_uuid FROM economic_events WHERE business_id=? AND {source}"
    ek = ("bid",) + sk
    operations = f"SELECT operation_uuid FROM economic_events WHERE business_id=? AND {source}"
    direct = {"invoices": "client_id", "clients": "id", "jobs": "client_id", "quotes": "client_id", "projects": "client_id", "client_preferences": "client_id",
              "financial_client_erasure_receipts": "client_id", "financial_restore_suppressions": "client_id"}
    if table in direct:
        return direct[table] + "=?", ("cid",)
    if table in ("job_materials", "job_updates", "job_completions", "worker_clockins"):
        return "job_id IN (SELECT id FROM jobs WHERE business_id=? AND client_id=?)", ik
    if table == "worker_clockin_corrections":
        return "clockin_id IN (SELECT id FROM worker_clockins WHERE business_id=? AND job_id IN (SELECT id FROM jobs WHERE business_id=? AND client_id=?))", ("bid",) + ik
    if table in ("project_members", "project_entries", "project_tasks"):
        return "project_id IN (SELECT id FROM projects WHERE business_id=? AND client_id=?)", ik
    if table == "documents":
        return f"(client_id=? OR (client_id IS NULL AND invoice_id IN ({invoices})))", ("cid",) + ik
    if table == "financial_privacy_tombstones":
        return "client_erasure_uuid IN (SELECT evidence_uuid FROM financial_client_erasure_receipts WHERE business_id=? AND client_id=?)", ik
    if table in ("invoice_lines", "invoice_records", "invoice_events", "invoice_cancellation_records", "invoice_payments", "invoice_economic_coverage", "payment_economic_coverage", "invoice_fiscal_cancellation_coverage", "verifactu_outbox", "verifactu_cancellation_outbox"):
        return f"invoice_id IN ({invoices})", ik
    if table in ("economic_events", "financial_antecedent_resolutions"):
        return source, sk
    if table == "economic_event_links":
        return f"event_uuid IN ({events}) AND target_event_uuid IN ({events})", ek + ek
    if table in ("financial_operations", "financial_authorizations", "financial_channel_proposals", "financial_channel_receipts", "financial_activation_effect_commits") or table.startswith("financial_activation_source_"):
        return f"operation_uuid IN ({operations})", ek
    if table in ("bank_transactions", "bank_payment_links", "bank_match_coverage", "bank_import_coverage"):
        column = "id" if table == "bank_transactions" else "bank_transaction_id"
        return f"{column} IN ({banks})", bk
    if table == "document_classifications":
        return f"document_id IN (SELECT id FROM documents WHERE business_id=? AND (client_id=? OR (client_id IS NULL AND invoice_id IN ({invoices}))))", ik + ik
    return "FALSE", ()


def read_section(session, bid, table, *, client_id=None, excluded_uuid=None, page_size=256):
    """Páginas acotadas en el mismo snapshot, orden por todas las columnas PK."""
    cols = _columns(session, table)
    where, params = ("id=?", [bid]) if table == "businesses" else ("business_id=?", [bid])
    if client_id is not None:
        clause, keys = _client_scope(table)
        where += " AND (" + clause + ")"
        params += [bid if key == "bid" else client_id for key in keys]
    if table == EXPORTS and excluded_uuid:
        where += " AND evidence_uuid<>?"
        params.append(excluded_uuid)
    # Orden por columnas explícitas del catálogo: estable aun sin PK numérica.
    order = ",".join(cols)
    result, offset = [], 0
    while True:
        rows = session.borrowed_connection.execute_exact(f"SELECT {','.join(cols)} FROM {table} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?", (*params, page_size, offset)).fetchall()
        if table == "economic_events":
            from noesis.economic_events.persistence import StoredEvent
            for row in rows:
                StoredEvent.from_row(row)
        elif table == "financial_operations":
            from noesis.financial_operations.contracts import Operation
            for row in rows:
                Operation.from_row(row)
        result.extend(evidence_value(dict(row)) for row in rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return result


def read_sections(session, business_id, *, client_id=None, excluded_uuid=None, legacy=False):
    tables = sorted(set(FINANCIAL_TABLES) | set(TABLES) | {RESTORED} | (set(LEGACY_KEYS) | {"businesses"} if legacy else set()))
    # Compatibilidad de claves no convierte chat/memoria/contenido de correo en
    # evidencia financiera. Sin segunda copia de conversaciones completas.
    excluded_content = {"assistant_messages", "business_memories", "assistant_actions", "inbound_email_messages"}
    return {t: [] if t in excluded_content else read_section(session, business_id, t, client_id=client_id, excluded_uuid=excluded_uuid) for t in tables}


class FinancialEvidenceExporter:
    def __init__(self, business_id, *, code_version):
        self.bid = export_identity(uuid4(), business_id, Purpose.AUDIT)["business_id"]
        if not isinstance(code_version, str) or not 1 <= len(code_version) <= 128:
            raise ValueError("Identidad de código requerida.")
        self.code_version = code_version

    def export(self, principal, export_uuid, purpose=Purpose.PORTABILITY, *, client_id=None, include_legacy=False, checkpoint=None, closure_read=False):
        identity = export_identity(export_uuid, self.bid, purpose, client_id)
        with snapshot() as session:
            if not installed(session):
                raise StateError("Schema78 requerido para FinancialEvidenceExport.")
            repo = PrivacyRepository(session, self.bid)
            repo.principal(principal, closure_read=closure_read)
            if client_id is not None and not session.execute("SELECT 1 FROM clients WHERE business_id=? AND id=?", (self.bid, client_id)).fetchone():
                return None
            existing = repo.load(EXPORTS, identity["export_uuid"])
            prior = json.loads(existing["body_canonical"]) if existing else None
            # Establecer snapshot antes del callback de concurrencia/crash.
            if checkpoint:
                checkpoint("snapshot_started", session)
            sections = read_sections(session, self.bid, client_id=client_id, excluded_uuid=identity["export_uuid"], legacy=include_legacy)
            section_proofs = {t: {"count": len(rows), "content_hash": digest(rows)} for t, rows in sections.items()}
            context = dict(**identity, code_version=self.code_version, created_by=principal.user_id,
                           session_version=principal.session_version, include_legacy=include_legacy,
                           section_proofs=section_proofs)
            context_hash = digest(context)
            if existing and existing["context_hash"] != context_hash:
                raise ConflictError("Export UUID vinculada a otro snapshot/contexto.")
            manifest = prior or dict(**identity, contract_version=1, canonical_version=CANONICAL_VERSION,
                                     schema_version=78, code_version=self.code_version, snapshot_identity=digest(section_proofs),
                                     created_by=principal.user_id, session_version=principal.session_version,
                                     created_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                                     sections=section_proofs, total_hash=digest(sections), final_result="complete",
                                     context_hash=context_hash, include_legacy=include_legacy,
                                     warnings=["LEGACY_BINARY_PRESERVED", "NAIVE_TIMESTAMPS_PRESERVED_IF_PRESENT"],
                                     limitations=["DOCUMENT_BYTES_SEPARATE_ARTIFACT", "NO_TEMPORAL_PURGE_APPROVAL"])
        # Snapshot ya concluido: gate corto únicamente para registro del manifest.
        with db.get_conn() as conn:
            s = FinancialSession(conn)
            if s.dialect == "sqlite":
                s.execute("BEGIN IMMEDIATE")
            lock_business(s, self.bid)
            repo = PrivacyRepository(s, self.bid)
            repo.principal(principal, closure_read=closure_read)
            current = repo.load(EXPORTS, identity["export_uuid"])
            if current:
                if current["context_hash"] != context_hash:
                    raise ConflictError("Export UUID concurrente con otro contexto.")
                manifest = json.loads(current["body_canonical"])
            else:
                repo.store(EXPORTS, identity["export_uuid"], principal, manifest, manifest["created_at"], context_hash=context_hash)
        if checkpoint:
            checkpoint("manifest_committed", None)
        return dict(manifest=manifest, sections=sections)


def compatibility_export(business_id, principal, *, client_id=None, export_uuid=None):
    from noesis import config
    result = FinancialEvidenceExporter(business_id, code_version="financial_privacy_v1:" + config.RELEASE_ID).export(
        principal, export_uuid or uuid4(), client_id=client_id, include_legacy=True)
    if result is None:
        return None
    sections = result["sections"]
    legacy = {k: sections.get(k, []) for k in LEGACY_KEYS}
    if client_id is None:
        legacy["business"] = next(iter(sections["businesses"]), None)
    else:
        legacy["client"] = next(iter(sections["clients"]), None)
    legacy.update(exported_at=result["manifest"]["created_at"], financial_core=result)
    if client_id is not None:
        legacy["client_preferences"] = next(iter(sections["client_preferences"]), {})
    for table in ("expenses", "received_invoices"):
        legacy[table] = [r for r in sections[table] if r.get("voided_at") is None]
    return legacy


def legacy_projection(business_id, *, client_id=None):
    """Compatibilidad interna de lectura sin actor: nunca acredita export E durable.

    HTTP siempre pasa Principal. El llamador legacy recibe el catálogo anterior
    saneado sobre un snapshot, sin afirmar autoridad ni readiness de privacidad.
    """
    from noesis.financial_operations.contracts import positive_id
    bid = positive_id(business_id)
    with snapshot() as s:
        if client_id is not None and not s.execute("SELECT 1 FROM clients WHERE id=? AND business_id=?", (client_id, bid)).fetchone():
            return None
        sections = {t: read_section(s, bid, t, client_id=client_id) for t in sorted(set(LEGACY_KEYS) | {"businesses"})}
    result = {k: sections[k] for k in LEGACY_KEYS}
    result["business" if client_id is None else "client"] = next(iter(sections["businesses" if client_id is None else "clients"]), None)
    for table in ("expenses", "received_invoices"):
        result[table] = [r for r in sections[table] if r.get("voided_at") is None]
    result["exported_at"] = datetime.now(timezone.utc).isoformat()
    return result


def verify_export(value):
    """Verificación independiente, sin acceso a BD ni secretos."""
    if set(value) != {"manifest", "sections"}:
        raise ValueError("FinancialEvidenceExport cerrado requerido.")
    m, sections = value["manifest"], value["sections"]
    expected_fields = {"export_uuid", "business_id", "purpose", "client_id", "contract_version", "canonical_version", "schema_version", "code_version", "snapshot_identity", "created_by", "session_version", "created_at", "sections", "total_hash", "final_result", "context_hash", "include_legacy", "warnings", "limitations"}
    if set(m) != expected_fields or type(m["contract_version"]) is not int or m["contract_version"] != 1:
        raise ValueError("Manifest v1 cerrado requerido.")
    export_identity(m["export_uuid"], m["business_id"], m["purpose"], m["client_id"])
    from noesis.financial_operations.contracts import positive_id
    positive_id(m["created_by"])
    if (type(m["session_version"]) is not int or m["session_version"] < 0
            or type(m["include_legacy"]) is not bool or m["final_result"] != "complete"
            or not isinstance(m["code_version"], str) or not 1 <= len(m["code_version"]) <= 128
            or not isinstance(sections, dict) or any(not isinstance(rows, list) for rows in sections.values())):
        raise ValueError("Metadatos de manifest inválidos.")
    if datetime.fromisoformat(m["created_at"]).tzinfo is None:
        raise ValueError("Manifest exige instante con zona.")
    if (m["schema_version"] != 78 or m["canonical_version"] != CANONICAL_VERSION
            or m["sections"] != {t: {"count": len(r), "content_hash": digest(r)} for t, r in sections.items()}
            or m["total_hash"] != digest(sections) or m["snapshot_identity"] != digest(m["sections"])):
        raise ConflictError("Manifest/contenido de export incompatible.")
    context = dict(export_uuid=m["export_uuid"], business_id=m["business_id"], purpose=m["purpose"], client_id=m["client_id"],
                   code_version=m["code_version"], created_by=m["created_by"], session_version=m["session_version"],
                   include_legacy=m["include_legacy"], section_proofs=m["sections"])
    if m["context_hash"] != digest(context):
        raise ConflictError("Contexto del manifest incompatible.")
    canonical(value)
    return True
