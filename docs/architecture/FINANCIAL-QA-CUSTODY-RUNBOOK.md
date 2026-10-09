# Custodia de copias QA y backups financieros — procedimiento pendiente de aprobación

E no consulta ni destruye Noesis19FQA, NoesisPrivate, snapshots ni backups reales.
Este runbook describe una operación futura con autorización expresa. No ejecutar
comandos sobre una copia real sólo por haber leído este documento.

1. Registrar un inventario privado: identificador de copia, propósito, fecha de
   captura/restauración, hash autorizado, versión/schema y referencias de informe.
   No incluir DATABASE_URL, passwords, tokens ni export/raw PII en repositorio o CI.
2. Nombrar propietario y custodio humanos. El propietario aprueba acceso, plazo
   operativo y destrucción; custodio verifica aislamiento, cifrado y accesos.
3. Mantener acceso nominal mínimo y auditable, carpeta fuera de Git, cifrado de
   disco/artefacto verificado y llaves separadas. Registrar cómo se verificaron,
   sin guardar las llaves ni asumir que BitLocker está habilitado.
4. Bloquear outbound/proveedores antes de introducir datos, detener servicios,
   verificar identidad de copia y preparar snapshot/punto de retorno autorizado.
   Nunca usar una URL productiva ni ejecutar migraciones/importers allí.
5. Fijar deadline operativo explícito. La propuesta de 30 días desde aceptación G
   es un diseño operativo pendiente de aprobación, **no plazo legal** ni job de
   destrucción. Si falta fecha/aprobación, registrar hold y escalar revisión.
6. Toda extensión necesita propietario, motivo, nueva fecha y referencia de
   aprobación; inventario anterior conserva su historia. No autoextender silenciosamente.
7. Para restaurar: mantener servicio detenido/outbound bloqueado; obtener registro
   de supresiones vigente del control plane autorizado, verificar firma/expiry y
   reaplicar antes de servir. Renovar/revalidar registro al handoff, contemplando
   supresiones posteriores a la captura. Sin registro actual: no habilitar servicio.
8. Antes de destruir, confirmar alcance exacto y que ninguna conservación/hold lo
   prohíbe. Inventariar duplicados, snapshots, WAL, carpetas temporales y llaves.
   No declarar eliminación de todos los derivados si alguno queda sin comprobar.
9. Ejecutar destrucción sólo con autorización posterior específica, con herramientas
   compatibles con medio/cifrado y política aprobada. No hay script de destrucción E.
10. Registrar evidencia privada de destrucción: IDs/hashes del inventario, operador,
    aprobación, fecha, método, resultados y copias pendientes/limitaciones. Nunca
    copiar PII eliminada para probar que se eliminó. Revisión independiente cierra
    custodia sólo cuando cada artefacto autorizado tiene evidencia comprobable.

La retención fiscal productiva y la custodia operativa de QA son decisiones distintas.
La validación profesional de la policy productiva sigue pendiente. Ningún piloto
real debe usar una aprobación sintética de tests.
