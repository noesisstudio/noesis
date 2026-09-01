# Recepcionista de llamadas 24/7

> Estado: **diseño aprobado, pendiente de construir** (beta privada con el plan Premium).
> Decisión de negocio: se vende ya en la página de precios como "beta · acceso preferente"
> para medir demanda antes de construir. No se cobra hasta que funcione.

## Qué es

Un número de teléfono al que el autónomo desvía su móvil (desvío condicional: solo si no
contesta o está ocupado). Noesis atiende la llamada con voz natural, y hace lo mismo que ya
hace por WhatsApp:

1. Entiende qué necesita el cliente (cita, presupuesto, urgencia, información).
2. Da cita real mirando la agenda (huecos libres de `jobs`), la confirma en voz alta.
3. Crea/actualiza el cliente y el trabajo en la base de datos.
4. Al colgar, deja el resumen por WhatsApp al dueño: quién llamó, qué quería, qué se agendó,
   con audio y transcripción. Si era urgente, avisa al momento.

Es el mismo cerebro que el asistente de WhatsApp (mismos handlers de agenda/clientes), con
otra puerta de entrada. **No es un contestador: resuelve.**

## Por qué

- La competencia que solo hace "answering con IA" no tiene el negocio dentro: apunta el
  recado y ahí acaba. Noesis tiene la agenda, los clientes y los precios: puede cerrar la
  cita de verdad.
- El autónomo pierde trabajos por no coger el teléfono en la obra/consulta/ruta. Cada
  llamada perdida es dinero perdido y ruido mental ("tengo que devolver la llamada").

## Arquitectura elegida

**Fase beta: proveedor gestionado de voz** (Retell AI o Vapi) conectado por webhook a
nuestro backend. Nos da número, STT, TTS y el bucle de conversación; nosotros ponemos las
funciones (`buscar_hueco`, `crear_cita`, `crear_cliente`, `avisar_dueno`) contra la API
interna. Es lo mismo que ya hacemos con Meta para WhatsApp: ellos el transporte, nosotros
el cerebro.

- Coste variable aproximado: 0,07–0,10 €/min todo incluido (voz + LLM + telefonía).
- 100 min/mes incluidos en Premium → coste máx. ~8-10 €/mes, cubierto por el margen
  del plan (~50 % en uso máximo).
- Minuto extra: 0,15 € (se factura como add-on en Stripe, metered price).

**Fase 2 (si el volumen lo justifica):** Twilio Media Streams + Groq Whisper (STT que ya
usamos) + TTS propio. Baja el coste por minuto ~40 % a cambio de operar nosotros el bucle
de audio. Solo compensa a partir de ~5.000 min/mes agregados.

## Encaje en planes

| Plan | Recepcionista |
|---|---|
| Autónomo (29 €) | No incluido |
| Negocio (49 €) | Add-on opcional: +15 €/mes con 100 min (cuando salga de beta) |
| Premium (99 €) | Incluido, 100 min/mes, minuto extra 0,15 € |

## Cumplimiento (antes de la beta)

- Locución inicial obligatoria: "Le atiende el asistente de [negocio]; la llamada se
  transcribe para darle cita" (RGPD art. 13, deber de información).
- La grabación de audio se borra tras transcribir (mismo criterio que las notas de voz de
  WhatsApp); se conserva solo la transcripción asociada al cliente.
- Registro de actividad de tratamiento actualizado y cláusula en el contrato de encargo.

## Plan de construcción (cuando haya 3+ interesados reales)

1. Cuenta Retell/Vapi + número español + webhook `POST /webhook/voz` (1-2 días).
2. Funciones de agenda/cliente expuestas al agente de voz reutilizando los handlers del
   asistente (2-3 días).
3. Resumen post-llamada por WhatsApp con la plantilla de aviso existente (1 día).
4. Beta con 3 clientes del plan Premium, 1 mes, midiendo: llamadas atendidas, citas
   cerradas, falsos positivos.
