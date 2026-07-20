# Registro de cambios

Bitácora cronológica obligatoria de modificaciones del repositorio. Su objetivo es
permitir responder rápido a cuatro preguntas cuando algo falla: **qué cambió, qué
área puede haberlo causado, cómo se verificó y cómo se puede aislar o revertir**.

No sustituye `Registro-QA.md` (evidencia detallada), `Estado-actual-main.md`
(fotografía del producto) ni Git (diff exacto). Los conecta.

## Plantilla para toda modificación

```markdown
## AAAA-MM-DD HH:MM — título corto

- Autor/agente:
- Objetivo:
- Áreas y archivos:
- Cambios de datos/migración:
- Pruebas ejecutadas:
- Dependencias o validaciones externas:
- Riesgo/punto probable de fallo:
- Diagnóstico y rollback:
- Estado de publicación: local / commit / main / desplegado / validado real
```

## 2026-07-20 — consolidación del MVP, facturación profesional e integración total

- **Autor/agente:** Codex, continuando trabajo previo de Codex/Fable revisado en el
  mismo árbol.
- **Objetivo:** consolidar el MVP nativo sin Holded; profesionalizar alta, precios,
  integraciones, facturación, Veri*Factu preparado y el recorrido WhatsApp →
  cliente/trabajo → borrador → confirmación → número/PDF → entrega → cobro,
  impuestos, KPIs y gestoría.
- **Áreas y archivos:** configuración y adaptadores; `db.py`, `migrations.py`,
  `nlu.py`, `tools.py`, `agent.py`; routers de cuenta, facturación y portal;
  `whatsapp.py`, `scheduler.py`, PDF, plantillas/CSS; smoke PostgreSQL, pruebas y
  documentación viva. El diff exacto queda en el commit asociado.
- **Cambios de datos/migración:** esquema 33. Añade series, líneas de factura,
  recurrencias idempotentes, metadatos de entrega, registros/outbox de anulación y
  triggers que congelan cabecera y líneas emitidas. Upgrade/downgrade cubiertos.
- **Pruebas ejecutadas:** 325 pruebas y 52 subtests verdes; compilación Python,
  JavaScript de Facturas, `git diff --check`, `check_project_truth.py`, flujo HTTP
  autenticado y XML de alta/anulación validado contra XSD oficiales. El smoke real
  PostgreSQL 16 corresponde al CI del PR.
- **Dependencias o validaciones externas:** faltan credenciales/prueba real de Meta,
  plantilla `noesis_factura_lista`, SMTP, Stripe, Google OAuth, IA privada y
  certificado/entorno AEAT. Veri*Factu permanece desactivado por negocio hasta
  validación; para autónomos la obligación SIF vigente comienza el 01-07-2027.
- **Riesgo/punto probable de fallo:** despliegue sin migración 33; datos fiscales
  incompletos al emitir F1; plantilla Meta no aprobada; SMTP sin credenciales;
  certificado o respuesta AEAT; diferencias SQLite/PostgreSQL en triggers/FK.
- **Diagnóstico y rollback:** revisar `/ready`, panel admin y outboxes; ejecutar el
  smoke PostgreSQL y el flujo de factura del `Registro-QA`. Revertir el commit de
  aplicación si hay regresión; no bajar esquema ni borrar registros fiscales en
  producción sin copia, auditoría y plan específico.
- **Estado de publicación:** candidato local verificado; PR de consolidación
  solicitado, todavía no desplegado al escribir esta entrada.

## 2026-07-20 17:46 — compatibilidad PostgreSQL de la migración 28

- **Autor/agente:** Codex.
- **Objetivo:** corregir el fallo del guardián PostgreSQL detectado en el PR #48.
- **Áreas y archivos:** `src/noesis/migrations.py`, `tests/test_platform.py`.
- **Cambios de datos/migración:** no cambia el esquema ni los datos resultantes;
  parametriza el patrón `R%` usado al clasificar facturas rectificativas durante la
  migración 28.
- **Pruebas ejecutadas:** prueba unitaria específica de migraciones y repetición del
  CI PostgreSQL del PR.
- **Dependencias o validaciones externas:** GitHub Actions con PostgreSQL 16.
- **Riesgo/punto probable de fallo:** únicamente la traducción de placeholders entre
  SQLite y psycopg.
- **Diagnóstico y rollback:** el error original era `psycopg.ProgrammingError` por un
  `%` literal interpretado como placeholder. Revertir este commit recuperaría el
  fallo; no requiere rollback de base de datos.
- **Estado de publicación:** corrección preparada en el PR #48, pendiente de CI al
  escribir esta entrada.
