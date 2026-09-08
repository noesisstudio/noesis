# Bynoesis

[![CI](https://github.com/noesisstudio/noesis/actions/workflows/ci.yml/badge.svg)](https://github.com/noesisstudio/noesis/actions/workflows/ci.yml)

**Haz tu trabajo; Bynoesis te ordena el negocio.** Bynoesis es el copiloto de negocio
por WhatsApp para autónomos y pequeños negocios de servicios (fontaneros,
electricistas, reformas, limpieza, jardinería…). Hablas con él por texto o audio y
lleva la oficina —agenda, clientes, presupuestos, facturas, documentos y cobros—
para devolverte tiempo, claridad y control.

> Estado actual: **SaaS multi-empresa en producción** en
> [bynoesis.com](https://bynoesis.com) (Railway + Postgres, auto-deploy
> desde `main`). Facturación **Veri*Factu nativa** (huella encadenada, QR, XML AEAT;
> remisión a AEAT implementada, pendiente de certificado), fichaje de equipo
> inalterable (art. 34.9 ET), portal del cliente sin contraseña y copiloto proactivo.

## Qué hace

- **Ciclo comercial completo**: cliente → presupuesto → trabajo/agenda → factura
  (PDF con 3 plantillas y marca propia) → cobro (IBAN/Bizum en factura y portal).
- **Copiloto proactivo**: plan del día con el porqué de cada acción (cobros
  pendientes, trabajos sin facturar, seguimiento de presupuestos).
- **Chat en lenguaje natural** (web hoy, WhatsApp al encender Meta): "haz factura a
  Carlos por reparación de caldera, 180 € más IVA" — con cerebro local gratuito
  (`nlu.py`) e IA (Claude) solo para lo complejo.
- **Cumplimiento**: Veri*Factu nativo (fases 1 y 2 construidas), registro de jornada
  con sellado hash inalterable, RGPD (export + borrado), fiscalidad correcta
  (IVA 21/10/4 + IRPF).
- **Panel web completo**: resumen personalizable, tesorería, análisis financiero
  (márgenes, DSO, morosidad), equipo con fichaje GPS, portal del cliente.

## Arquitectura

```
WhatsApp / Web / CLI ─► Cerebro (nlu.py local + Claude opcional) ─► tools.py ─► db.py (Postgres/SQLite)
                                                                       └─► adapters/ (Stripe, WhatsApp, Whisper)
```

| Módulo (`src/noesis/`) | Qué es |
|---|---|
| `web/server.py` | FastAPI: páginas, API JSON, login, onboarding, webhooks |
| `nlu.py` · `web/chat.py` | Cerebro local por reglas + orquestador local/IA |
| `agent.py` · `tools.py` | Agente Claude (tool-use) y acciones multi-negocio |
| `db.py` · `migrations.py` | Acceso a datos aislado por `business_id` + esquema versionado |
| `verifactu.py` | Veri*Factu nativo: huella AEAT, QR, XML, remisión SOAP/mTLS |
| `clockin_integrity.py` · `work_reports.py` | Fichaje inalterable + informes |
| `web/whatsapp.py` | Cola durable de WhatsApp (Meta Cloud API) |
| `adapters/` | Stripe, transcripción local (faster-whisper), facturación |

## Cómo arrancarlo en local

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
noesis-web        # → http://127.0.0.1:8000
```

- Demo comercial dentro del producto: autónomo y gestoría con datos ficticios
  conectados, más portal de cliente. Ver [`docs/Demo-comercial.md`](docs/Demo-comercial.md).
- CLI de prueba (chat tipo WhatsApp): `py -m noesis`.
- La IA es opcional: sin `ANTHROPIC_API_KEY` en `.env`, el chat funciona con el
  cerebro local. Sin `DATABASE_URL` usa SQLite local.
- Tests: `python -m pytest tests/` (también corren en CI en cada PR).

## Principios

- **Mínimas dependencias**: sin CDNs en runtime, sistema de diseño propio,
  Chart.js servido en local, stdlib siempre que se puede.
- **Privacidad y margen**: lo rutinario se resuelve en local sin coste por uso;
  solo lo complejo llama al LLM.
- **Aislamiento multi-empresa estricto**: toda lectura/escritura filtrada por
  `business_id`, con FKs compuestas en Postgres y auditorías de seguridad periódicas.
- **Integraciones detrás de adaptadores**: cambiar de proveedor = tocar un archivo.

Manual para agentes de IA en [`AGENTS.md`](AGENTS.md) · visión y decisiones en
[`docs/Inicio.md`](docs/Inicio.md) · conexión de servicios en
[`docs/Conectar-APIs.md`](docs/Conectar-APIs.md) · roadmap en
[`docs/Roadmap.md`](docs/Roadmap.md).
