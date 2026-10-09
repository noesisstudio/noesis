"""Dispatch con identidad durable: TX de claim / I/O exterior / TX de resultado."""

from uuid import uuid4
from noesis import config, db
from noesis.core.persistence import FinancialSession, schema_version
from noesis.core.locks import lock_business
from noesis.financial_activation.contracts import Capability, instant
from noesis.financial_activation.configuration_snapshot import configuration_hash
from noesis.financial_activation.runtime import control, ActivationUnavailable
from noesis.financial_operations.contracts import Principal, StateError, ConflictError, uuid_text
from noesis.financial_privacy.repository import assert_open
from .contracts import Provider, Reason, DispatchResult, clock, requirement
from .configuration import keyed
from .attestations import verify
from .repository import ProviderRepository
from .schema import OUTBOXES, OUTBOX_BINDINGS, ATTESTATIONS, ATTEMPTS, STARTS, RESULTS


def request_fingerprint(row, outbox_type):
    fields = ("invoice_id", "record_id") if outbox_type.startswith("verifactu") else (
        ("to_email", "subject", "text_body", "html_body", "entity_type", "entity_id") if outbox_type == "email_outbox"
        else ("connection_id", "to_phone", "message_type", "text_body", "template_name", "template_params", "template_language"))
    return keyed("dispatch-request:" + str(row["business_id"]), {k: row.get(k) for k in fields})


def bind(session, business_id, principal, outbox_type, outbox_id, operation_uuid):
    """El productor proporciona identidad exacta; nunca asunto, importe o destinatario."""
    if outbox_type not in OUTBOXES:
        raise ValueError("Outbox financiero desconocido.")
    repo = ProviderRepository(session, business_id)
    repo.principal(principal)
    assert_open(session, business_id)
    row = session.borrowed_connection.execute_exact("SELECT * FROM " + outbox_type + " WHERE business_id=? AND id=?", (business_id, outbox_id)).fetchone()
    op = session.execute("SELECT * FROM financial_operations WHERE business_id=? AND operation_uuid=?", (business_id, uuid_text(operation_uuid))).fetchone()
    current = control(session, business_id)
    if (not row or not op or (outbox_type.startswith('verifactu') and op["state"] != "committed") or op['entry_namespace']=='historical' or not current or not current["ever_enabled"]
            or current["state"] != "enabled" or current["activation_generation"] != op["activation_generation"]):
        raise StateError(Reason.UNBOUND)
    cap = Capability.AEAT if outbox_type.startswith("verifactu") else Capability.EMAIL if outbox_type == "email_outbox" else Capability.WHATSAPP
    if not session.execute("SELECT 1 FROM financial_activation_grants WHERE business_id=? AND activation_generation=? AND capability=?", (business_id, current["activation_generation"], cap.value)).fetchone():
        raise StateError("Grant de provider no disponible.")
    if outbox_type.startswith("verifactu"):
        table = "invoice_economic_coverage" if outbox_type == "verifactu_outbox" else "invoice_fiscal_cancellation_coverage"
        clause = "invoice_id=?" if outbox_type == "verifactu_outbox" else "cancellation_record_id=?"
        coverage = session.execute("SELECT operation_uuid FROM " + table + " WHERE business_id=? AND " + clause,
                                   (business_id, row["invoice_id"] if outbox_type == "verifactu_outbox" else row["record_id"])).fetchone()
        if not coverage or str(coverage["operation_uuid"]) != uuid_text(operation_uuid):
            raise StateError(Reason.UNBOUND)
        record_table = "invoice_records" if outbox_type == "verifactu_outbox" else "invoice_cancellation_records"
        if not session.execute("SELECT 1 FROM " + record_table + " WHERE business_id=? AND id=? AND invoice_id=?", (business_id, row["record_id"], row["invoice_id"])).fetchone():
            raise StateError(Reason.UNBOUND)
    uid = str(uuid4())
    old = session.execute(f"SELECT evidence_uuid FROM {OUTBOX_BINDINGS} WHERE business_id=? AND outbox_type=? AND outbox_id=?", (business_id, outbox_type, outbox_id)).fetchone()
    if old:
        value = repo.load(OUTBOX_BINDINGS, str(old["evidence_uuid"]))
        if value["operation_uuid"] != uuid_text(operation_uuid) or value["request_fingerprint"] != request_fingerprint(row, outbox_type):
            raise ConflictError("Outbox ya ligada a otro efecto.")
        return value
    values = dict(outbox_type=outbox_type, outbox_id=outbox_id, operation_uuid=uuid_text(operation_uuid),
                  activation_generation=current["activation_generation"], capability=cap.value, provider=requirement(cap).value,
                  request_fingerprint=request_fingerprint(row, outbox_type))
    body = dict(version=1, business_id=business_id, binding_uuid=uid, **values)
    return repo.append(OUTBOX_BINDINGS, uid, principal, body, clock(), **values)


def bind_committed_fiscal(session, business_id, principal, operation_uuid):
    if schema_version(session.borrowed_connection) != 79:
        return
    for table, coverage, column in (("verifactu_outbox", "invoice_economic_coverage", "invoice_id"),
                                     ("verifactu_cancellation_outbox", "invoice_fiscal_cancellation_coverage", "cancellation_record_id")):
        join = "q.invoice_id=c.invoice_id" if column == "invoice_id" else "q.record_id=c.cancellation_record_id"
        rows = session.execute(f"SELECT q.id FROM {table} q JOIN {coverage} c ON c.business_id=q.business_id AND {join} WHERE q.business_id=? AND c.operation_uuid=?", (business_id, uuid_text(operation_uuid))).fetchall()
        for row in rows:
            bind(session, business_id, principal, table, row["id"], operation_uuid)


def _identity(session, business_id, binding):
    current = control(session, business_id)
    assert_open(session, business_id)
    if not current or not current["ever_enabled"] or not config.FINANCIAL_CORE_ENABLED:
        raise ActivationUnavailable("Disponibilidad global no concede autoridad de dispatch.")
    fence = session.execute("SELECT fence_enabled FROM financial_history_control WHERE business_id=?", (business_id,)).fetchone()
    if fence and fence["fence_enabled"]:
        raise StateError(Reason.FENCE)
    if current["activation_generation"] != binding["activation_generation"]:
        raise StateError(Reason.STALE_GENERATION)
    if current["state"] != "enabled" and not (current["state"] == "paused" and binding["provider"] == Provider.AEAT):
        raise StateError(Reason.PAUSED)
    op = session.execute("SELECT * FROM financial_operations WHERE business_id=? AND operation_uuid=?", (business_id, binding["operation_uuid"])).fetchone()
    if not op or (binding['provider'] == Provider.AEAT and op["state"] != "committed") or op["activation_generation"] != binding["activation_generation"]:
        raise StateError(Reason.UNBOUND)
    grant = session.execute("SELECT 1 FROM financial_activation_grants WHERE business_id=? AND activation_generation=? AND capability=?", (business_id, binding["activation_generation"], binding["capability"])).fetchone()
    if not grant:
        raise StateError(Reason.STALE_GENERATION)
    from noesis.financial_activation.activation_contracts import ActivationRequest
    origin = session.execute("SELECT r.request_canonical FROM financial_activation_generations g JOIN financial_activation_requests r ON r.business_id=g.business_id AND r.request_uuid=g.request_uuid WHERE g.business_id=? AND g.activation_generation=?", (business_id, binding["activation_generation"])).fetchone()
    if not origin or ActivationRequest.decode(origin["request_canonical"]).body["configuration_hash"] != configuration_hash(session, business_id) or ActivationRequest.decode(origin['request_canonical']).body['code_version'] != config.RELEASE_ID:
        raise StateError(Reason.CONFIGURATION_CHANGED)
    from .schema import BINDINGS, RUNS
    request_uuid = ActivationRequest.decode(origin['request_canonical']).body['request_uuid']
    if not session.execute(f"SELECT 1 FROM {BINDINGS} b JOIN {RUNS} f ON f.business_id=b.business_id AND f.evidence_uuid=b.preflight_uuid WHERE b.business_id=? AND b.request_uuid=? AND f.result='PASS' AND f.content_hash=b.preflight_hash",(business_id,request_uuid)).fetchone():
        raise StateError('GENERATION_REQUIRES_F_PREFLIGHT_PROVENANCE')
    row = session.borrowed_connection.execute_exact("SELECT * FROM " + binding["outbox_type"] + " WHERE business_id=? AND id=?", (business_id, binding["outbox_id"])).fetchone()
    if not row or request_fingerprint(row, binding["outbox_type"]) != binding["request_fingerprint"]:
        raise StateError(Reason.CONFIG_DRIFT)
    if binding['provider'] == Provider.AEAT and not db._verify_invoice_record_rows(db._fiscal_record_rows(session.borrowed_connection, business_id))['valid']:
        raise StateError(Reason.INTEGRITY)
    if binding['provider'] == Provider.EMAIL:
        from .configuration import snapshot
        implementation = snapshot(session, business_id, Provider.EMAIL)['implementation']
        from noesis.adapters.google_mail import TIPOS_PROPIOS
        if implementation == 'gmail' and row['entity_type'] not in TIPOS_PROPIOS:
            raise StateError(Reason.CONFIG_DRIFT)
    return row


class FinancialProviderDispatch:
    def __init__(self, business_id):
        from .contracts import tenant
        self.bid = tenant(business_id)

    def checkpoint(self, point):
        """Puntos de crash sintético; no hooks externos configurables."""

    def _transaction(self):
        from contextlib import contextmanager
        @contextmanager
        def owned():
            with db.get_conn() as conn:
                s = FinancialSession(conn)
                from .limits import acquire_gate
                acquire_gate(s, self.bid)
                if schema_version(conn) != 79:
                    raise StateError("Schema79 requerido para dispatch F.")
                yield s
        return owned()

    def _principal(self, s, binding):
        row = s.execute("SELECT created_by,session_version FROM " + OUTBOX_BINDINGS + " WHERE business_id=? AND evidence_uuid=?", (self.bid, binding["binding_uuid"])).fetchone()
        # Worker no hereda financial.authorize. Sólo consume la obligación ya committed.
        return Principal(row["created_by"], row["session_version"])

    def claim(self, binding_uuid):
        self.checkpoint("before_claim")
        with self._transaction() as s:
            repo = ProviderRepository(s, self.bid)
            binding = repo.load(OUTBOX_BINDINGS, binding_uuid)
            if not binding:
                raise StateError(Reason.UNBOUND)
            old = s.execute(f"SELECT evidence_uuid FROM {ATTEMPTS} WHERE business_id=? AND binding_uuid=?", (self.bid, uuid_text(binding_uuid))).fetchone()
            if old:
                return repo.load(ATTEMPTS, str(old["evidence_uuid"]))
            row = _identity(s, self.bid, binding)
            principal = self._principal(s, binding)
            refs = s.execute(f"SELECT evidence_uuid FROM {ATTESTATIONS} WHERE business_id=? AND capability=? ORDER BY created_at DESC,evidence_uuid DESC LIMIT 1", (self.bid, binding["capability"])).fetchone()
            if not refs:
                raise StateError(Reason.ATTESTATION_MISSING)
            proof = verify(s, self.bid, str(refs["evidence_uuid"]), binding["capability"],code_version=config.RELEASE_ID)
            if row["status"] not in ("queued", "pendiente", "retrying"):
                raise StateError("Outbox no disponible para primer claim.")
            uid = str(uuid4())
            values = dict(binding_uuid=binding["binding_uuid"], attestation_uuid=proof["attestation_uuid"],
                          operation_uuid=binding["operation_uuid"], activation_generation=binding["activation_generation"],
                          capability=binding["capability"], provider=binding["provider"], request_fingerprint=binding["request_fingerprint"],
                          idempotency_fingerprint=keyed("dispatch-idempotency", [self.bid, binding["binding_uuid"]]))
            body = dict(version=1, business_id=self.bid, attempt_uuid=uid, claimed_at=instant(clock()),
                        attestation_hash=proof["content_hash"], **values)
            repo.append(ATTEMPTS, uid, principal, body, body["claimed_at"], **values)
            s.execute("UPDATE " + binding["outbox_type"] + " SET status=?, attempts=attempts+1,locked_at=?,updated_at=? WHERE business_id=? AND id=?",
                      ('enviado' if binding['outbox_type'].startswith('verifactu') else 'processing', body["claimed_at"], body["claimed_at"], self.bid, binding["outbox_id"]))
        self.checkpoint("after_claim_commit")
        return body

    def _start(self, attempt):
        with self._transaction() as s:
            repo = ProviderRepository(s, self.bid)
            old = s.execute(f"SELECT evidence_uuid FROM {RESULTS} WHERE business_id=? AND attempt_uuid=?", (self.bid, attempt["attempt_uuid"])).fetchone()
            if old:
                return repo.load(RESULTS, str(old["evidence_uuid"]))
            if s.execute(f"SELECT 1 FROM {STARTS} WHERE business_id=? AND attempt_uuid=?", (self.bid, attempt["attempt_uuid"])).fetchone():
                # Otro worker puede estar fuera de TX ejecutando el mismo intento.
                # No declarar un crash ni repetir su llamada por mera concurrencia.
                raise StateError(Reason.UNKNOWN_RESULT)
            binding = repo.load(OUTBOX_BINDINGS, attempt["binding_uuid"])
            try:
                _identity(s, self.bid, binding)
                proof = verify(s, self.bid, attempt["attestation_uuid"], attempt["capability"],code_version=config.RELEASE_ID)
                if proof["content_hash"] != attempt["attestation_hash"]:
                    raise StateError(Reason.ATTESTATION_STALE)
            except (StateError, ConflictError):
                return self._finish(s, attempt, DispatchResult.ABORTED, "guard_before_io")
            principal = self._principal(s, binding)
            body = dict(version=1, business_id=self.bid, start_uuid=str(uuid4()), attempt_uuid=attempt["attempt_uuid"], started_at=instant(clock()))
            repo.append(STARTS, body["start_uuid"], principal, body, body["started_at"], attempt_uuid=attempt["attempt_uuid"])
        return None

    def recover_unknown(self, binding_uuid):
        """Recuperación explícita conservadora; nunca hace I/O ni repite el intento."""
        with self._transaction() as s:
            repo = ProviderRepository(s, self.bid)
            row = s.execute(f"SELECT evidence_uuid FROM {ATTEMPTS} WHERE business_id=? AND binding_uuid=?", (self.bid, uuid_text(binding_uuid))).fetchone()
            if not row:
                raise StateError(Reason.UNBOUND)
            attempt = repo.load(ATTEMPTS, str(row['evidence_uuid']))
            if not s.execute(f"SELECT 1 FROM {STARTS} WHERE business_id=? AND attempt_uuid=?", (self.bid, attempt['attempt_uuid'])).fetchone():
                raise StateError('Un claim sin start aún puede iniciar una única llamada.')
            return self._finish(s, attempt, DispatchResult.UNKNOWN, 'crash_after_start')

    def _finish(self, s, attempt, result, category, *, reference=None, status_code=None, real_io=False):
        repo = ProviderRepository(s, self.bid)
        old = s.execute(f"SELECT evidence_uuid FROM {RESULTS} WHERE business_id=? AND attempt_uuid=?", (self.bid, attempt["attempt_uuid"])).fetchone()
        if old:
            return repo.load(RESULTS, str(old["evidence_uuid"]))
        binding = repo.load(OUTBOX_BINDINGS, attempt["binding_uuid"])
        # Una cuenta cerrada puede registrar el resultado del intento YA iniciado.
        # No validar acceso de usuario desactivado como autorización nueva.
        principal = self._principal(s, binding)
        body = dict(version=1, business_id=self.bid, result_uuid=str(uuid4()), attempt_uuid=attempt["attempt_uuid"],
                    result=DispatchResult(result).value, category=category, provider_reference_hash=keyed("provider-reference", reference) if reference else None,
                    status_code=status_code, completed_at=instant(clock()), real_io=real_io)
        repo.append(RESULTS, body["result_uuid"], principal, body, body["completed_at"], attempt_uuid=attempt["attempt_uuid"], result=body["result"])
        status = "sent" if result == DispatchResult.SUCCEEDED else "failed" if result == DispatchResult.FAILED else "processing"
        if binding["outbox_type"].startswith("verifactu"):
            status = "aceptado_con_errores" if category == 'accepted_with_errors' else "aceptado" if result == DispatchResult.SUCCEEDED else "rechazado" if result == DispatchResult.FAILED else "enviado"
        if result == DispatchResult.ABORTED:
            status = 'pendiente' if binding['outbox_type'].startswith('verifactu') else 'queued'
        s.execute("UPDATE " + binding["outbox_type"] + " SET status=?,locked_at=?,updated_at=? WHERE business_id=? AND id=?", (status, attempt['claimed_at'] if result == DispatchResult.UNKNOWN else None, body["completed_at"], self.bid, binding["outbox_id"]))
        if result in (DispatchResult.SUCCEEDED, DispatchResult.FAILED):
            field = 'completed_at' if binding['outbox_type'].startswith('verifactu') else 'sent_at'
            s.execute('UPDATE ' + binding['outbox_type'] + ' SET ' + field + '=? WHERE business_id=? AND id=?', (body['completed_at'] if result == DispatchResult.SUCCEEDED or field == 'completed_at' else None, self.bid, binding['outbox_id']))
        if result == DispatchResult.SUCCEEDED and reference:
            field = 'aeat_csv' if binding['provider'] == Provider.AEAT else 'meta_message_id' if binding['provider'] == Provider.META else None
            if field:
                s.execute('UPDATE '+binding['outbox_type']+' SET '+field+'=? WHERE business_id=? AND id=?',(reference,self.bid,binding['outbox_id']))
        self.checkpoint("during_result_transaction")
        return body

    def dispatch(self, binding_uuid, *, transport=None):
        """Sólo obligaciones exactas con prueba suficiente; fake exclusivo de tests."""
        real_io = transport is None
        if config.IS_PRODUCTION and not real_io:
            raise StateError("Transporte sintético prohibido en producción.")
        attempt = self.claim(binding_uuid)
        if real_io:
            with self._transaction() as s:
                body = ProviderRepository(s, self.bid).load(ATTESTATIONS, attempt['attestation_uuid'])
                if body['evidence']['synthetic']:
                    raise StateError("REAL_PROVIDER_IO_NOT_AUTHORIZED_BY_SYNTHETIC_PROOF")
        final = self._start(attempt)
        if final is not None:
            return final
        self.checkpoint("before_provider_call")
        # Volver a comprobar después de cualquier pausa/cierre/rotation entre
        # claim/start y la ventana de I/O. Ningún lock/TX llega al adapter.
        with self._transaction() as s:
            repo = ProviderRepository(s, self.bid)
            binding = repo.load(OUTBOX_BINDINGS, attempt['binding_uuid'])
            try:
                _identity(s, self.bid, binding)
                verify(s, self.bid, attempt['attestation_uuid'], attempt['capability'],code_version=config.RELEASE_ID)
            except (StateError, ConflictError):
                return self._finish(s, attempt, DispatchResult.ABORTED, "guard_before_io")
        try:
            # Sin conexión/TX/gate del negocio mientras el provider puede bloquear.
            if real_io:
                from .transports import deliver
                outcome = deliver(binding)
            else:
                outcome = transport(attempt)
            allowed = {"success", "accepted_with_errors", "rejected", "timeout", "duplicate_confirmed"}
            if binding['provider'] != Provider.AEAT:
                allowed -= {'accepted_with_errors', 'duplicate_confirmed'}
            if (type(outcome) is not dict or set(outcome) != {"category", "reference", "status_code"} or outcome["category"] not in allowed
                    or outcome['reference'] is not None and (type(outcome['reference']) is not str or len(outcome['reference'])>512)
                    or outcome['status_code'] is not None and (type(outcome['status_code']) is not int or not 100<=outcome['status_code']<=599)):
                outcome = dict(category="timeout", reference=None, status_code=None)
            category = outcome["category"]
            result = DispatchResult.SUCCEEDED if category in ("success", "accepted_with_errors", "duplicate_confirmed") else DispatchResult.FAILED if category == "rejected" else DispatchResult.UNKNOWN
        except Exception:  # noqa: BLE001 - nunca repetir un efecto cuyo resultado se perdió
            category, result = "timeout", DispatchResult.UNKNOWN
            outcome = dict(reference=None, status_code=None)
        self.checkpoint("after_provider_before_result")
        with self._transaction() as s:
            final = self._finish(s, attempt, result, category, reference=outcome["reference"], status_code=outcome["status_code"], real_io=real_io)
        self.checkpoint("after_result_commit")
        if real_io and final['result'] == DispatchResult.SUCCEEDED:
            # Derivación DESPUÉS del commit económico de transporte. Su fallo no
            # puede perder el resultado ni provocar otro provider side effect.
            try:
                with self._transaction() as s:
                    from .attestations import record_observed
                    record_observed(s,self.bid,self._principal(s,binding),attempt['attempt_uuid'])
            except Exception:  # noqa: BLE001 - diagnóstico best effort, resultado ya durable
                pass
        return final


def legacy_predicate(connection, tenant_expression):
    """Los claims legacy no adoptan filas financieras tras handoff."""
    table = tenant_expression.split(".")[0]
    if table not in OUTBOXES:
        raise ValueError("Worker F desconocido.")
    s = connection if isinstance(connection, FinancialSession) else FinancialSession(connection)
    if schema_version(s.borrowed_connection) != 79:
        return "TRUE"
    binding = f"EXISTS(SELECT 1 FROM {OUTBOX_BINDINGS} fb WHERE fb.business_id={tenant_expression} AND fb.outbox_type='{table}' AND fb.outbox_id={table}.id)"
    if table == 'whatsapp_outbox':
        # Metadatos declarados por el catálogo de plantillas y el bridge.
        # No inspeccionar texto/importes/teléfonos ni adoptar filas legacy.
        from noesis.whatsapp_templates import SPECS
        from noesis.financial_channels.whatsapp import PREFIX
        settings = {'WHATSAPP_TEMPLATE_INVOICE', 'WHATSAPP_TEMPLATE_PAYMENT_REMINDER', 'WHATSAPP_TEMPLATE_PAYMENT_ALERT'}
        names = sorted({name for spec in SPECS if spec.setting in settings for name in (spec.name, spec.default_name)})
        literals = ','.join("'" + name.replace("'", "''") + "'" for name in names)
        financial = f"({binding} OR ({table}.message_type='template' AND {table}.template_name IN ({literals})) OR substr(COALESCE({table}.idempotency_key,''),1,{len(PREFIX)})='{PREFIX}')"
    else:
        financial = "TRUE" if table.startswith("verifactu") else f"({binding} OR COALESCE({table}.entity_type,'')='invoice')"
    return f"NOT ({financial} AND EXISTS(SELECT 1 FROM financial_activation_control fc WHERE fc.business_id={tenant_expression} AND fc.ever_enabled=TRUE))"


def bind_delivery(connection, business_id, outbox_type, outbox_id, *, invoice_id=None, operation_uuid=None):
    """Shim de productor: referencia relacional explícita en la misma TX de cola."""
    s = connection if isinstance(connection, FinancialSession) else FinancialSession(connection)
    if schema_version(s.borrowed_connection) != 79 or business_id is None:
        return
    state = control(s, business_id)
    if not state or not state['ever_enabled']:
        return
    if operation_uuid is None:
        row = s.execute('SELECT operation_uuid FROM invoice_economic_coverage WHERE business_id=? AND invoice_id=?', (business_id, invoice_id)).fetchone()
        if not row:
            raise StateError(Reason.UNBOUND)
        operation_uuid = str(row['operation_uuid'])
    op = s.execute('SELECT created_by FROM financial_operations WHERE business_id=? AND operation_uuid=?', (business_id, uuid_text(operation_uuid))).fetchone()
    if not op:
        raise StateError(Reason.UNBOUND)
    user = s.execute('SELECT session_version FROM users WHERE business_id=? AND id=? AND is_active=TRUE', (business_id, op['created_by'])).fetchone()
    if not user:
        raise StateError(Reason.SESSION_STALE)
    return bind(s, business_id, Principal(op['created_by'], user['session_version']), outbox_type, outbox_id, operation_uuid)


def process_bound(outbox_type, *, limit=25, only_ids=None, transport=None):
    """Selección cerrada F separada de claims legacy; no modificar otras colas."""
    if outbox_type not in OUTBOXES:
        raise ValueError('Worker F desconocido.')
    with db.get_conn() as c:
        if schema_version(c) != 79:
            return []
        if not config.FINANCIAL_CORE_ENABLED:
            return []
        args = [outbox_type]
        where = ''
        if only_ids:
            where = ' AND b.outbox_id IN (' + ','.join('?' for _ in only_ids) + ')'
            args += list(only_ids)
        args += [max(1, min(int(limit), 1000))]
        rows = c.execute_exact(f"SELECT b.business_id,b.evidence_uuid,b.outbox_id FROM {OUTBOX_BINDINGS} b JOIN financial_activation_control ctl ON ctl.business_id=b.business_id WHERE b.outbox_type=? AND (ctl.state='enabled' OR (ctl.state='paused' AND b.provider='AEAT_VERIFACTU')) AND ctl.activation_generation=b.activation_generation AND NOT EXISTS(SELECT 1 FROM financial_closure_authorizations e WHERE e.business_id=b.business_id) AND NOT EXISTS(SELECT 1 FROM financial_restore_suppressions e WHERE e.business_id=b.business_id AND e.scope='account_local_access') AND NOT EXISTS(SELECT 1 FROM {ATTEMPTS} a JOIN {RESULTS} r ON r.business_id=a.business_id AND r.attempt_uuid=a.evidence_uuid WHERE a.business_id=b.business_id AND a.binding_uuid=b.evidence_uuid)" + where + ' ORDER BY b.created_at,b.evidence_uuid LIMIT ?', args).fetchall()
    completed = []
    for row in rows:
        try:
            result = FinancialProviderDispatch(row['business_id']).dispatch(str(row['evidence_uuid']), transport=transport)
        except (StateError, ConflictError):
            # Sólo un bloqueo operativo cerrado. Ningún raw error/provider body.
            continue
        status = {'SUCCEEDED':'sent','FAILED_TERMINAL':'failed','UNKNOWN_EXTERNAL_RESULT':'unknown','ABORTED_BEFORE_IO':'queued'}[result['result']]
        completed.append(dict(id=row['outbox_id'], status=status, result=result))
    return completed


def prepare_queue(connection, business_id):
    """Gate antes de INSERT de una comunicación financiera identificada."""
    if business_id is None or schema_version(connection) != 79:
        return
    s = FinancialSession(connection)
    if s.dialect == 'sqlite' and not connection.raw.in_transaction:
        s.execute('BEGIN IMMEDIATE')
    lock_business(s, business_id)


def reject_unbound_direct_io(business_id):
    """PDF/upload directo no tiene attempt durable: nunca bypass post-handoff."""
    with db.get_conn() as c:
        row = control(c, business_id)
        if row and row['ever_enabled']:
            raise ActivationUnavailable(Reason.UNBOUND)
