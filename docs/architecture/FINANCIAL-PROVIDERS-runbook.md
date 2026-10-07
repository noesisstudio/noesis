# Providers y preflight — preparación del piloto, sin ejecución real

Contrato de [límites operativos v1](FINANCIAL-OPERATIONAL-LIMITS-v1.md).
Un binding de generación anterior no se adopta después de resume. Un claim sin
start puede iniciar su única llamada; un start sin resultado no puede repetirla.
Primero detener/comprobar el worker original y luego recuperar como UNKNOWN.
Con resultado durable, un replay devuelve el recibo exacto, incluso tras pausa.
No hay resolución externa automática ni revocación remota en F.

F local no autoriza los pasos reales de este documento. G requiere otra orden.

Antes de G: aprobación profesional de política legal E; negocio y perfil exactos;
backup/restaurabilidad reales autorizados; runtime/schema/despliegue verificados;
operador y suplente, monitorización, pausa y procedimiento de UNKNOWN documentados;
providers al nivel productivo exacto requerido por closure. Ningún fixture approved
o synthetic se convierte en configuración real.

1. Seleccionar business/profile/closure, probar historia y E sobre sus fuentes.
2. Revisión de huellas de credenciales y configuración sin exponer secretos.
3. Ejecutar exclusivamente checks readonly específicamente implementados y
   autorizados. Actualmente SAFE_CHECK_UNIMPLEMENTED: no enviar para "probar".
4. Emitir attestations nuevas, evaluar A y preflight F; revisar motivos y hashes.
5. Presentar solicitud D y confirmación humana exacta únicamente con autorización G.
6. Monitorizar intento/start/resultado y outbox. UNKNOWN: mantener hold, no reenvío,
   reconciliar evidencia externa de ese registro/mensaje concreto y revisión humana.
7. Ante integridad rota o duplicado económico confirmado: bloquear, solicitar pausa,
   conservar pruebas. No restore para deshacer un envío fiscal/económico committed.

Límites v1: historia 64 items, objetivo espera gate 1 s, handoff warning 2 s y
revisión 5 s, readiness/attestation 5 min, warning corte 5 min e intervención 15 min.
No SLO ni plazos legales. Un warning después de commit no deshace el handoff;
medir y revisar. TTL no libera fence ni autoriza retry. Cohortes mayores bloqueadas.

Rollback: pause/conservar/reparar/revalidar. Downgrade79→78 sólo sin evidencia F;
con evidencia bloquear downgrade. No borrar pruebas para permitirlo. F no limpia
filesystem, revoca providers ni destruye QA. No consultar datos reales para tests.
