# Fase1.9F — Runbook de copia real aislada

Este procedimiento documenta el ensayo realizado; no autoriza otra fase ni
conexión productiva. La orden actual permite solo Noesis19FQA, flags OFF.
Leer primero AGENTS, guía08, ADR014–018, contratos A–E y [cierre](FASE-1.9F-cierre.md).
Los scripts/dumps/settings/selección privada están fuera de Git, en la carpeta
privada identificada por el informe. No publicar ni adjuntar raw, PDFs o credenciales.

1. Backup: pedir autorización humana expresa antes de cualquier conexión a
   producción; únicamente pg_dump read-only para fuente autorizada, sin migrations,
   flags, writers, scanner o comandos Railway mutables. Autenticar por flujo local,
   nunca contraseña en chat. **Ya obtenido: no repetir esta conexión en1.9F**.
2. Verificar SHA del dump y snapshots en Windows y Linux; tamaño, fecha, motor,
   encoding/locale/schema, código aprobado. Conservar originales inmutables.
3. Crear entorno con DB/rol propios y secretos locales privados. No reutilizar
   .env/productive URL ni copiar config de Windows a aplicación QA. Restaurar en
   Noesis19FQA con PostgreSQL18.6; DB noesis_19f_qa, rol noesis_qa_operator.
4. Antes de introducir datos: ejecutar aislamiento root-owned noesis-qa-isolate;
   netns noesis19f solo loopback, sin rutas/capabilities/interop/automount/systemd;
   firewall secundario y egress externo bloqueado. No configurar providers. No
   server/scheduler/worker/webhook. Probar TCP/UDP con ENETUNREACH y control
   positivo loopback; rechazar conexión a QA desde Windows/default namespace.
5. Restaurar dump sin providers; comprobar marker NOESIS_19F_QA+SHA, DB/rol/host/
   puerto y ausencia de superuser/createdb/createrole/replication. Solo el launcher
   /usr/local/sbin/noesis-qa-exec puede ejecutar aplicación como noesisqa sin caps.
6. Antes de migrar/rehearsal, baseline no sensible y snapshot lógico/físico de la
   copia detenida. Si esquema anterior, migraciones normales sobre QA; fallo→STOP,
   sin editar migrations/sources. En esta copia73 no se ejecutó ninguna migración.
7. Registrar autorización humana1.9F en el archivo privado de control root:noesisqa
   0640. El marker original de preparación se conserva. qa-python.py comprueba
   config/flags/identidad; cinco flags siempre false. No autoriza continuidad live.
8. Diagnostic: f_baseline.py y f_diagnostic.py, ejecutados mediante run-19f.py:
   Windows wrapper sube solo script privado, llama qa-exec → python → qa-python.py
   --script /opt/noesis-19f/scripts/<script>.py. No usar CLI de producto ni Windows
   Python con URL QA/productiva. Principal se deriva solo de usuario activo de
   esa copia; contexto de operador QA simulado, sin acreditar actor histórico.
9. Seleccionar por counts/tipos y permiso existente; nunca por nombres. Trials
   vencidos/demos se respetan. Revisar f_review.py y conteo definitivo NULL en
   f_compare.py: expense no tiene money.vat_amount, usa _captured_vat_amount.
   Informes exclusivamente categorías/hashes/seudónimos HMAC. No imprimir money/raw.
10. Solo tras revisar B: f_rehearsal.py abre epoch con IDs/version/entorno exactos.
    Guard activo; probes normales invoice/payment/bank/received/expense/live EE
    deben levantar HistoricalFenceActive. Probes son intentos en memoria, no seeds.
    Un fallo técnico del núcleo detiene run afectado, conserva evidencia y requiere
    clasificación/propuesta/fix/CI/restauración limpia antes de repetir; jamás
    continuar reparando la copia. Datos BLOCKED no implican bug ni nueva excepción.
11. C: inventory nuevo ligado a epoch; certifiable exige consistencia/fence/scope,
    eligible_for_import=false. Carrier B mantiene su summary diagnóstico; consultar
    el sobre C para certificación. Registrar hashes/counts/drift/tiempo/queries/memoria.
12. D: preparar/run batch por contrato, sin seleccionar manualmente bloqueados.
    Medir estados/sequences/EE y cero efecto legacy. Si cero candidates, no crear
    fixtures para simular éxito; documentar camino positivo no ejercitado.
13. E: reconcile por contexto exacto; recoger todos los findings paginados y evaluar
    honestamente BLOCKED/PASS. No reparar, liberar fence ni activar flags. Instrumentar
    únicamente contadores y lock/commit sin cambiar decisiones ni resultados.
14. Reintentar prepare/run/items/E; comparar resultados frozen y counts para duplicados.
    Comparar hashes exactos de todas las95 tablas legacy (incluyendo storage float bits).
15. Primera copia detenida y archivada. Para repetir: validar rutas absolutas dentro
    de /opt/noesis-19f/database, detener PG, preservar data anterior bajo nombre propio
    que no exista; verificar SHA del snapshot inicial, membresía data/, ausencia de
    ../symlinks/hardlinks y postmaster.pid. Extraer snapshot sin escapes y **reponer
    modos originales y ownership antes de arrancar** (PG requiere data0700).
    Nunca borrar/mover recursivamente un destino no verificado. No sobrescribir
    preserved-run1-data ni evidence/phase19f-run1. Scripts clean-repeat.py y
    restore-modes.py registran la primera repetición; clean-repeat.py rechaza repetir
    sobre esos destinos existentes. Cualquier nuevo run requiere destinos propios
    y registro, no improvisar reemplazos destructivos.
16. Repetir B/C/D/E con mismo código/source; comparar source/plan hashes,
    HistoricalIdentity/revisiones/candidate hashes y semántica. UUIDs de EE/operaciones
    únicamente si se crearon de forma autorizada; ausencia implica N/A, no PASS positivo.
    Timestamps de observación/T0 pueden variar por contrato. No exigir hash físico
    de cluster igual después de diferentes relojes/checkpoints PostgreSQL.
17. f_final.py verifica identidad/legacy/flags/fences/clients/privacidad. Probe
    isolation final. export-stop.py exporta solo whitelist de resúmenes sanitizados,
    detiene PG y preserva snapshot final. Jamás exportar selection-private.json,
    pseudonym-key.private, local-settings.private.json, raw/candidate payloads o logs literales.
18. Reportar gate/transacción, ventana T0→E y período observado hasta stop. Fence
    lógico permanece ON al parar cluster, no confundirlo con release. Fase1.9G/
    activación1.10 necesitan orden separada. No push que dispare despliegue productivo.
19. Retención/destrucción: **no automática ni autorizada**. Conservar snapshots y
    hashes privados. Antes de eventual destrucción, acordar política/retención,
    verificar rutas exactas y copia necesaria. No wsl --unregister ni borrados ahora.

Comprobación y arranque exclusivos (no ejecutan1.9F ni otra fase):

```powershell
wsl -d Noesis19FQA -u root --exec /usr/local/sbin/noesis-qa-exec /opt/noesis-19f/app/.venv/bin/python /opt/noesis-19f/scripts/probe-isolation.py
wsl -d Noesis19FQA -u root --exec /usr/local/sbin/noesis-qa-exec /usr/lib/postgresql/18/bin/pg_ctl -D /opt/noesis-19f/database/data -l /opt/noesis-19f/logs/postgres.log -w start
wsl -d Noesis19FQA -u root --exec /usr/local/sbin/noesis-qa-exec /opt/noesis-19f/app/.venv/bin/python /opt/noesis-19f/scripts/qa-python.py --check
```

Para detener: mismo launcher con pg_ctl -D /opt/noesis-19f/database/data -m fast
-w stop. La entrega deja PG detenido; no arrancarlo sin una tarea que lo necesite.
Configuración/pw local solo Linux600; jamás mostrar argumentos de conexión.

Noesis no dispone de un CLI nuevo para este rehearsal. Scripts son herramientas
privadas específicas del ensayo. Copiar este runbook no copia permisos, datos ni
identidades: revalidar siempre scope, código, hashes, guard y autorización humana.
