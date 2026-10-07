# ADR023 — Export financiero, retención y cierre con conservación

Fecha: 2026-10-07. Estado: implementación local E; aprobación legal real pendiente.
Autoridad y alcance: [orden E](FASE-1.10E-orden.md), rama local exclusivamente.
Detalle normativo técnico: [contrato v1](FINANCIAL-PRIVACY-EXPORT-RETENTION-v1.md).

El export anterior mezclaba lecturas independientes y algunos listados acotados.
La baja física no representa la conservación de evidencia financiera ni la
invalidación local de acceso. La restauración de una copia anterior a una supresión
requiere el registro vigente, que no puede deducirse del backup antiguo.

Decidimos añadir `financial_privacy` como dominio del monolito modular. Reutiliza
FinancialSession, conexión/pool, gate por negocio y transacción del propietario.
`db.py` conserva delegaciones pequeñas; HTTP conserva autenticación y scope
existentes. No nuevos canales financieros, herramientas IA ni providers.

FinancialEvidenceExport v1 usa snapshot de lectura único, catálogo cerrado y
paginación interna determinista sin límite total. El manifest durable conserva
conteos, hashes, identidades técnicas y versiones, sin duplicar contenido personal.
Decimal/NUMERIC se serializa exacto; binary64 legacy conserva bits/procedencia
etiquetados, nunca se promociona a importe exacto. Documentos: metadatos y hash,
sin rutas ni bytes. Chat, memoria y cuerpo de correo no son evidencia financiera.

RetentionPolicy v1 distingue provisional de approved_for_operation. Ninguna
migración aprueba una política y ninguna regla inventa plazos legales. Todas las
fechas de purga v1 son NULL: revisión pendiente/contrato sin purga temporal. Una
política aprobada necesita referencia profesional externa y confirmación humana
exacta; el código no certifica esa revisión. Las aprobaciones de tests son sintéticas.
El inventario es durable y por tabla/campos explícitos; una regla de categoría no
autoriza borrar una tabla completa. Campos sin acción v1 se conservan.

El cierre reutiliza privacy_requests: plan congelado, aprobación humana específica
del hash exacto y recibo/tombstone/minimización en una sola TX. La autorización
formal bloquea nuevos efectos y dispatch; una solicitud administrativa sola no lo
hace. ever_enabled exige pausa D previa. E no cambia state/generación/grants D.
El hash de evidencia financiera se compara antes y después; cualquier alteración
revierte el cierre. Se conservan IDs, fuentes, documentos e historia A–D/E.
Se invalidan credenciales locales, sin revocaciones remotas. No se borran archivos
en E: no hay dual-write DB/filesystem ni falsas marcas de cleanup completado.

Migration78 añade nueve tablas inmutables, FKs tenant y guards de contexto firmado.
PostgreSQL mantiene **byte a byte** noesis_execution_context D. El nuevo
noesis_privacy_context sólo acepta los kinds financial_privacy y
financial_privacy_restore, con el mismo HMAC/backend/TX. Permite metadatos/restore
administrativos con el login legacy privilegiado sin conceder contexto monetario D.
La amenaza cubierta es SQL runtime sin clave ni DDL; un propietario de DB puede
desactivar triggers y queda fuera de ese perímetro. La clave global nunca se exporta.
La compatibilidad de esquema se amplía con 78 explícito, sin `>=78`.
Downgrade78→77 sólo procede sin ninguna evidencia E, sin borrar registros.

La restauración exige bundle privado del registro vigente firmado, de vida corta,
antes de servir. Un overlay inmutable lleva supresiones posteriores al backup a la
copia restaurada. El startup vuelve a aplicarlas. Los verificadores existentes de
backup usan este hook. Una restauración externa fuera de esos caminos debe adoptar
el protocolo; una copia antigua sola no demuestra actualidad del registro.
No se habilita servicio mientras falte esa comprobación.

Readiness nuevo consume evidencia E vigente y puede retirar sólo EXPORT_NOT_READY
y PRIVACY_NOT_READY. Las pruebas A antiguas no se reescriben; F/banco/history/
continuity y los demás blockers permanecen. Los cinco flags siguen OFF.
No hay producción, copia QA real, backup real, push, merge, deploy ni F–H.
