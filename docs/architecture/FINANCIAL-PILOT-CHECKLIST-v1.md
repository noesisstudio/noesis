# Checklist del futuro piloto real v1 — sin ejecución

[Contrato](FINANCIAL-PILOT-READINESS-v1.md), [runbook](FINANCIAL-PILOT-RUNBOOK-v1.md).
Todas las casillas permanecen pendientes salvo software A–F. No se elige una
persona/negocio ni se realiza ninguna consulta real desde este documento.

## Negocio y EMPTY

- [ ] Titular selecciona un business_id único y confirma perfil/hash exactos.
- [ ] Sin cierre E autorizado, receipt de cierre ni overlay account_local_access.
- [ ] Usuario activo/sesión/subscripción y autoridad humana específicos verificados.
- [ ] A conserva catálogo completo y relacionados; no se excluye historia por perfil.
- [ ] Cero facturas no-borrador, incluyendo rectificativas/canceladas; líneas ligadas coherentes.
- [ ] Cero pagos, incluido registro_anterior; pagada no acredita cobro exacto.
- [ ] Cero recibidas/gastos confirmados. Ante falta de clasificación/proof fiable,
  **cualquier** received_invoice/expense cuenta conservadoramente como historia.
- [ ] Cero filas bancarias/links/account batches relevantes; banco no permitido.
- [ ] Cero invoice_records/invoice_cancellation_records y outboxes fiscales.
- [ ] Cero EE y coberturas; no inferir ausencia por saldo/status.
- [ ] Cero PREPARED/APPROVED live Operations/mandates ejecutables.
- [ ] Cero START sin resultado, UNKNOWN, outboxes pendientes o sin binding financiero.
- [ ] Cero ambigüedad C/D/history no resuelta. Nunca promover B/NULL/binary legacy.
- [ ] Inventario completo/frozen, boundary vigente y reconciliación PASS con hashes
  revisados aunque la cuenta sea vacía. EMPTY no sustituye corte/certificado.
- [ ] Clientes, configuración y drafts sólo admitidos si no producen hechos, no tienen
  referencias incoherentes ni dispatch pendiente. No se borran para simular vacío.

Las [consultas preparadas](FINANCIAL-PILOT-READONLY-QUERIES-v1.sql) producen counts
técnicos. No constituyen el lector completo A, no certifican EMPTY ni prueban
absence por sí solas. Se complementan con `_sources/_history` y verifiers A/B
vigentes, en futura lectura tenant autorizada y prestada, sin llamar evaluate.
G-PREP no ejecuta SQL contra producción/Noesis19FQA/backups.

## E / evidencia humana

- [ ] Profesional responsable revisa policy E; referencia y alcance, firma humana
  durable del hash exacto. Modelo/administrador/migración no sustituyen aprobación.
- [ ] Readiness E real vigente; PRIVACY_NOT_READY no retirado por fixture.
- [ ] Export E completo de negocio, purpose autorizado, snapshot/hash actual sin secretos.
- [ ] Operador primario/suplente, legal/privacy owner y custodio asignados por titular.
- [ ] Acceso a runbooks y read model F probado, con firma de recepción/formación.

## Backup / restore real

- [ ] Permiso específico lectura para copia; backup reciente de DB actual, fecha UTC,
  SHA256 y código/schema de origen; no producción consultada hasta autorización.
- [ ] Ubicación privada fuera de Git y ACL revisada. Hash no demuestra cifrado.
- [ ] Cifrado at-rest **verificado** (volumen/objeto cifrado y gestión de clave);
  secreto separado, custodio y suplente. No dar un dump plaintext por cifrado.
- [ ] Procedimiento pg_dump consistente, lectura solamente, stderr sin secretos.
- [ ] Restore en infraestructura/schema/nombre/rol claramente aislados. Outbound
  DENY verificado antes de introducir datos reales; scheduler/workers no arrancan.
- [ ] Freshness de copia y drill propuesta ≤24 h, repetir tras cambios materiales
  y antes de T0. Límite operativo a confirmar por titular/custodio, no SLO/plazo legal.
- [ ] Restauración completa de esquema79, counts/hashes/FKs/triggers con evidencia.
- [ ] Registro de supresiones/cierres E vigente obtenido **después** de aislar copia;
  `prepare_restored_database` y reapply antes de servir. Revalidar bundle al abrir.
- [ ] Overlay mantiene cierres posteriores al backup; UNKNOWN/START preservados,
  sin replay delivery, sin repetir Operations/EE. No importar datos a negocio real.
- [ ] Snapshot previo y procedimiento de recuperación ensayado. Rollback operativo
  pause/conservar/reparar; no restore para deshacer un envío/efecto committed.
- [ ] Downgrade79→78 sólo sin evidencia F, E igualmente protegida; nunca borrarla
  para pasar guard. No cleanup/destrucción real de QA desde G-PREP.

BACKUP_NOT_VERIFIED y RESTORE_NOT_VERIFIED actuales. La restauración 1.9F anterior
y los drills sintéticos no demuestran freshness/replay/runtime del futuro piloto.

## Runtime / deployment / integración

- [ ] Rama futura desde main actual; integrar A–G sin rebase/historia reescrita;
  resolver eliminación sigue.md y posibles cambios concurrentes; CI fresca completa
  sobre SHA final e inspección. No se hace en G-PREP.
- [ ] Autorización separada de merge/deploy y guard D producción revisado.
- [ ] SHA Railway esperado = runtime web = workers = scheduler = todas las réplicas.
- [ ] Schema real79 y migration79 completa; rollout coordinado sin réplica legacy
  que omita guards D/F. Arranque controlado, sin dispatch real en comprobación.
- [ ] Rol runtime PG no propietario/superuser/migrator; sin acceso al verifier
  privado ni DDL/BYPASSRLS. Conexión/runtime reales declarados, no credenciales aquí.
- [ ] Context verifier/hash/HMAC estable preparado y validado sintéticamente contra
  mismo código/role; no imprimir valor, pg_get_functiondef sensible ni tabla privada.
- [ ] Hash de config/credencial usando F, sólo HMAC; revisión de rotación, expiry,
  certificados públicos, ámbitos/OAuth existentes sin reconfiguración automática.
- [ ] Cinco flags OFF hasta autorización independiente: FINANCIAL_CORE,
  LEDGER_REPORTING, OPEN_ITEMS, NEW_TAX_ENGINE, NEW_BANK_RECONCILIATION.
- [ ] D resume con A original caducada resuelto explícitamente antes de T0;
  mantener paused si no hay camino autorizado de recuperación.
- [ ] Providers requeridos de closure con pruebas reales actuales; checks sólo
  tras diseño aprobado/autorización aparte. Véase [diseño](FINANCIAL-PILOT-PROVIDER-CHECKS-v1.md).

## T0 futuro

- [ ] Toda evidencia anterior real actual y revalidada; expediente revisado por humano.
- [ ] G-LIVE autorización específica, negocio/perfil/hash/cohorte/ventana/roles exactos.
- [ ] A FULL + F PASS exactos vigentes, E actual, autorización D humana durable.
- [ ] No activar sólo porque exista reporte, grant, flag, ready o administrador.
- [ ] Operación real necesaria elegida por titular, documento auténtico, humano presente.
- [ ] Plan T0/+15m/+1h/+2h/+24h/+72h, hard stops y suplente disponibles.

Hoy **PILOT_BLOCKED — EXTERNAL PREREQUISITES PENDING**. G-LIVE y H bloqueados.
