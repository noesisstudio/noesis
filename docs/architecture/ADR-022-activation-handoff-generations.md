# ADR022 — Handoff atómico y generaciones de activación

Fecha: 2026-10-06. Estado: implementado y verificado localmente en D; pendiente de revisión independiente.

## Contexto y alcance

La [orden D](FASE-1.10D-orden.md) acepta A/B/C CODE-VERIFIED PASS. Un corte
histórico certificado no concede autoridad para producir efectos live. Liberar
su fence por separado dejaría una ventana sin protección. D debe conservar las
identidades y pruebas existentes y permitir pausa/reanudación sin reutilizar
autoridad antigua. Solo fixtures sintéticos; ninguna activación real.

## Decisión

Mantener el monolito modular, FinancialSession prestada y el gate por negocio.
El servicio interno FinancialActivation implementa off → validating → ready →
enabled; validating/ready → off solo antes del primer enable. Pause conserva
ever_enabled y generación. Resume verifica prueba D y recorre validating/ready/
enabled en una única transacción, concediendo exactamente G+1.

La autoridad específica financial.activation.manage requiere principal del
mismo negocio, sesión vigente, cuenta escribible y confirmación humana durable
del hash de un request derivado por servidor. No se consulta users.is_admin.
No existe RBAC tenant más fino en el modelo actual; P15 deberá separar funciones.
No se reutilizan financial.authorize, mandates ni historical_unknown.

Los grants son la closure exacta del perfil FULL de A y todas sus pruebas deben
ser eligible. Se revalida A por SELECT sin alterar su resultado ni su hash;
se excluye únicamente el control lifecycle propio de la comparación externa.
Los blockers de E/F permanecen: la fixture FULL positiva está exclusivamente
en tests. D no inventa preflight ni readiness productiva.

En el primer enable, la misma transacción escribe recibo, generación y grants,
marca el epoch handed_off y retira su fence; el corte sigue certifiable y cambia
solo boundary_current. Actualiza finalmente activation control y ever_enabled.
Una FK diferida recibo → revisión de control impide confirmar solo la mitad.
No usa HistoryCutoff.release. B reconoce la frontera handed_off a través del
recibo original y verifica la huella del corte normalizando solo ese booleano.

Cada operación/autorización nueva queda ligada a G y al mapping command/capability
único de C. Los NULL legacy/historical nunca se promueven. Pause cancela pending
live y revoca mandates no ligados, conservando todo el registro. Resume exige
misma configuración/perfil/grants y snapshot financiero sin drift ni dispatch
incierto. Nunca revive operaciones ni autorizaciones; committed solo se recupera.

Guards de aplicación y SQL protegen cada superficie final. SQLite usa estado
privado de conexión y authorizer que impide cerrar la transacción dentro del
contexto. PostgreSQL usa HMAC ligado a backend y transaction ID con GUC local.
La clave de verificación queda privada; el login runtime no puede leerla ni
tener privilegios de superuser/createrole/bypassrls. SET ROLE no cambia la identidad
session_user comprobada. Los contextos se borran antes del commit exterior.

Dos tipos de testigos SQL diferidos prueban el commit: efectos → operación
committed de G, y cada origen escrito → cobertura de esa operación exacta.
Un solo committed no justificaría filas adicionales huérfanas. Para EE, el contexto
se estrecha al UUID, hash y relaciones del sobre tipado antes de reservar links.
Los testigos son evidencia retenida; nunca se consultan para conceder permiso.

## Consecuencias y límites

Después de ever_enabled, flag global OFF o pause bloquea todo nuevo efecto.
No hay fallback legacy. Borradores y sugerencias bancarias operativas siguen
permitidos; import/match y modificación de hechos siguen protegidos. Los updates
de transporte outbox permanecen; dispatch real se bloquea conservadoramente
hasta que F defina su política. Ningún provider se llama desde este control plane.

La migración nueva no cambia valores monetarios, fuentes, UUID ni hashes previos.
SQLite reconstruye padres con FKs activas y copia exacta, sin renombrarlos.
Se conserva una baseline de DDL/functions CHECK con hash para downgrade vacío.
Con evidencia D o bindings live, el downgrade queda bloqueado.

PostgreSQL necesita login runtime separado del migrador y una clave estable,
no la default de desarrollo. Provisionamiento y rotación real corresponden a F;
cambiar SECRET_KEY sin preparar ese ciclo produce fail-closed. D no configura
credenciales reales. El gate SQL usa el pg_try_advisory_xact_lock histórico:
contención de SQL directo se rechaza en vez de invertir el orden de locks.
Los APIs confiables toman gate antes de filas y ordenan tenants en SQL.
Las fuentes nunca activadas conservan el orden de guards C; D adelanta el gate
solo en su control plane y en fuentes ya live. Una sentencia SQL iniciada antes
del enable debe observar el nuevo guard al llegar a él después del commit.

La recuperación es deliberadamente conservadora: cambios incluso de tablas
operativas incluidas en el snapshot de pausa pueden exigir diagnóstico posterior.
No permite reconstruir historia ni reparar/importar después de ever_enabled.
E/F/G/H siguen pendientes. Ver [contrato](FINANCIAL-ACTIVATION-HANDOFF-v1.md)
y [cierre](FASE-1.10D-cierre.md) para pruebas y estado final.
