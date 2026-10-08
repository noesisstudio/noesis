# ADR025 — Verificación de piloto y continuidad live D79

Fecha: 2026-10-08. Alcance: G-VERIFY local, sin activación real.

G-PREP permanece documental e incapaz de producir READY. Un hash acredita
identidad, no procedencia, revisión profesional, custodia o ejecución de un drill.
La capa nueva mantiene catálogo cerrado, evidencia tipada y contexto exacto.
Reutiliza A, B, history, C, E y F mediante FinancialSession prestada. No hay
conexiones propias, nueva lógica grande en db.py, endpoints, CLI de aprobación,
lectura de backups ni checks de red.

Los hechos BD se derivan de verificadores existentes. Lo que la BD no puede
demostrar requiere un recibo de un colector específico confiable. TrustStore es
dependencia privada de composición; no se admite como input HTTP/chat/IA.
Claves independientes por origen y cohorte autentican el recibo HMAC; después
se verifican metadatos cerrados, fechas, roles, scope y relaciones. No hay claves
reales instaladas ni emisores reales implementados en esta fase. Una firma de
fuente autorizada no sustituye los contrastes BD. Aprobar o provisionar esos
orígenes reales requerirá autorización posterior específica.

Los objetos VerifiedEvidence sólo salen de verifiers y mantienen un sello
privado de instancia, además de canonicalización/SHA256. PilotGate revalida
fuentes, vigencia y contexto, y cruza backup/custodio/probe/roles. READY siempre
mantiene activation_authorized=false. SYNTHETIC_STRUCTURAL nunca acredita REAL.
PRODUCTION_ACTIVATION sigue bloqueada para REAL porque el guard D no se retira.

El llamador posee una única TX SQLite exterior o PostgreSQL REPEATABLE READ /
SERIALIZABLE. Los verificadores hacen SELECT. A permite locking=False para esta
lectura consistente sin autoridad; su default locking=True permanece intacto
en D/F y toda activación. G funciona también con TX PostgreSQL READ ONLY.
Una decisión es evidencia de su snapshot, no autorización futura.
Reutilizarla exige revalidación en un snapshot actual; cerrar la conexión invalida
la instancia. No se serializa el sello como autoridad pública ni se persiste el
resultado G en una tabla nueva.

D79 resume conserva A original como provenance, sin exigir que su TTL sea eterno.
Una prueba específica valida generación, pausa, grants, configuración, snapshot,
certificado histórico, EE/B, E y F actuales. La primera activación conserva A
FULL vigente. El certificado histórico después del handoff se verifica por
equivalencia limitada ya existente; no se invoca el arco fenced inicial ni se
reabre fence/importer. Drift, UNKNOWN, providers stale y privacidad inválida
mantienen PAUSED. No se cambia el perfil ni revive autoridad G anterior.

No hace falta migration80: RUNS F79 ya conserva context canónico inmutable,
binding D→F exacto y SQL guards. RecoveryReadiness v1 queda allí y su hash en
los nuevos receipts de resume. Requests y receipts previos mantienen sus bytes
y hashes; schema77/78 conserva el comportamiento anterior. Ninguna migration
63–79 se modifica. Cinco flags reales OFF y policy REAL provisional.

Riesgos: los colectores/trust bootstrap reales, el despliegue compatible y la
revisión profesional están pendientes. No confundir contrato sintético con
real-world readiness. La continuidad bloquea conservadoramente evidencia B
que no pueda revalidar; no repara ni reclasifica fuentes automáticamente.

[Contrato G](FINANCIAL-PILOT-VERIFICATION-v1.md),
[contrato recovery](FINANCIAL-RECOVERY-READINESS-v1.md),
[orden](FASE-1.10G-verify-orden.md), [cierre](FASE-1.10G-verify-cierre.md).
