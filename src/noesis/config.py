"""Configuración central. Lee variables del archivo .env."""

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

# Carga el .env de la raíz del proyecto (si existe).
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _release_id() -> str:
    """Identificador publicable del despliegue, nunca una variable arbitraria.

    Railway expone el SHA del commit. ``NOESIS_RELEASE_ID`` permite conservar la
    misma comprobacion en otro proveedor, pero solo se aceptan caracteres seguros
    y se publica una huella corta.
    """
    raw = (
        os.getenv("NOESIS_RELEASE_ID", "").strip()
        or os.getenv("RAILWAY_GIT_COMMIT_SHA", "").strip()
    )
    if not raw:
        return "unknown" if os.getenv("RAILWAY_ENVIRONMENT") else "local"
    if not re.fullmatch(r"[A-Za-z0-9._-]{7,64}", raw):
        return "invalid"
    return raw[:12]


RELEASE_ID = _release_id()


def env_bool(name: str, default: bool = False) -> bool:
    """Interpreta booleanos de entorno sin tratar "false" o "0" como verdaderos."""
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on", "si", "sí"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"{name} debe ser un booleano (true/false o 1/0).")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("NOESIS_MODEL", "claude-sonnet-4-6")
# El agente principal puede usar una tarifa distinta al fallback. Cero evita
# inventar coste si no se ha revisado el precio del modelo elegido.
MODEL_INPUT_USD_PER_MTOK = float(
    os.getenv("NOESIS_MODEL_INPUT_USD_PER_MTOK", "0")
)
MODEL_OUTPUT_USD_PER_MTOK = float(
    os.getenv("NOESIS_MODEL_OUTPUT_USD_PER_MTOK", "0")
)
# Modelo BARATO para el respaldo del chat (cuando el cerebro local no entiende la
# frase). Haiku minimiza el coste: el 90% se resuelve gratis en local y solo lo
# realmente complejo paga, a fracción de céntimo. Cámbialo con NOESIS_FALLBACK_MODEL.
FALLBACK_MODEL = os.getenv("NOESIS_FALLBACK_MODEL", "claude-haiku-4-5-20251001")
# Segundo nivel privado opcional. Acepta servidores con contrato OpenAI-compatible
# (Ollama, llama.cpp o vLLM). Si falta, Noesis pasa a la IA externa consentida.
LOCAL_AI_BASE_URL = os.getenv("NOESIS_LOCAL_AI_BASE_URL", "").strip()
LOCAL_AI_MODEL = os.getenv("NOESIS_LOCAL_AI_MODEL", "").strip()
LOCAL_AI_API_KEY = os.getenv("NOESIS_LOCAL_AI_API_KEY", "").strip()
LOCAL_AI_TIMEOUT_SECONDS = int(os.getenv("NOESIS_LOCAL_AI_TIMEOUT_SECONDS", "45"))
# Tercer nivel opcional: proveedor externo barato con contrato OpenAI-compatible
# (por ejemplo Groq, Cloudflare Workers AI o Hugging Face). Sigue necesitando el
# consentimiento ``ai_external`` y consume un crédito del plan. Los precios se
# declaran para poder observar coste sin acoplar el código a una tarifa cambiante.
COMPAT_AI_BASE_URL = os.getenv("NOESIS_COMPAT_AI_BASE_URL", "").strip()
COMPAT_AI_MODEL = os.getenv("NOESIS_COMPAT_AI_MODEL", "").strip()
COMPAT_AI_API_KEY = os.getenv("NOESIS_COMPAT_AI_API_KEY", "").strip()
COMPAT_AI_PROVIDER = os.getenv("NOESIS_COMPAT_AI_PROVIDER", "compatible").strip()
COMPAT_AI_LEGAL_NAME = os.getenv("NOESIS_COMPAT_AI_LEGAL_NAME", "").strip()
COMPAT_AI_REGION = os.getenv("NOESIS_COMPAT_AI_REGION", "").strip()
COMPAT_AI_TIMEOUT_SECONDS = int(
    os.getenv("NOESIS_COMPAT_AI_TIMEOUT_SECONDS", "45")
)
COMPAT_AI_INPUT_USD_PER_MTOK = float(
    os.getenv("NOESIS_COMPAT_AI_INPUT_USD_PER_MTOK", "0")
)
COMPAT_AI_OUTPUT_USD_PER_MTOK = float(
    os.getenv("NOESIS_COMPAT_AI_OUTPUT_USD_PER_MTOK", "0")
)
# Tarifa del modelo de respaldo, explícita y revisable. Los valores por defecto
# corresponden a Haiku 4.5 en julio de 2026; si cambia el modelo, deben cambiarse.
FALLBACK_INPUT_USD_PER_MTOK = float(
    os.getenv("NOESIS_FALLBACK_INPUT_USD_PER_MTOK", "1")
)
FALLBACK_OUTPUT_USD_PER_MTOK = float(
    os.getenv("NOESIS_FALLBACK_OUTPUT_USD_PER_MTOK", "5")
)
BUSINESS_NAME = os.getenv("NOESIS_BUSINESS_NAME", "Mi Negocio")

# Railway inyecta DATABASE_URL al enlazar el servicio Postgres. Sin esa variable,
# Noesis conserva SQLite para desarrollo local y pruebas.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Fallback SQLite local. NOESIS_DB_PATH sigue siendo útil para conservar/copiar una
# instalación anterior, pero no se usa cuando DATABASE_URL está configurada.
DB_PATH = Path(os.getenv("NOESIS_DB_PATH", str(ROOT / "noesis.db")))

# IVA por defecto en España (servicios generales).
DEFAULT_VAT_RATE = 21

# Documentos ("papeles"): carpeta donde se guardan los archivos subidos por los
# autónomos (recibos, contratos, fotos de tickets...). En producción apunta a un
# volumen persistente con NOESIS_DOCS_PATH (igual que la BD). Por defecto, ./uploads
# en la raíz del proyecto (ignorada por git).
DOCS_PATH = Path(os.getenv("NOESIS_DOCS_PATH", str(ROOT / "uploads")))
# Tamaño máximo por archivo subido (MB). Evita llenar el disco con un único fichero.
MAX_UPLOAD_MB = int(os.getenv("NOESIS_MAX_UPLOAD_MB", "15"))

# Clave para firmar las sesiones (cookies). En producción, ponla en el .env.
SECRET_KEY = os.getenv("NOESIS_SECRET", "dev-secret-cambiar-en-produccion")

# En producción (Railway inyecta RAILWAY_ENVIRONMENT) las cookies de sesión deben
# viajar solo por HTTPS. En local (http://127.0.0.1) se desactiva para poder entrar.
HTTPS_ONLY = bool(os.getenv("RAILWAY_ENVIRONMENT")) or env_bool("NOESIS_HTTPS")

# True cuando estamos en un entorno expuesto (para exigir configuración segura).
IS_PRODUCTION = (
    HTTPS_ONLY
    or os.getenv("NOESIS_ENV", "").strip().lower() in {"production", "produccion"}
)
TRUST_PROXY_HEADERS = bool(os.getenv("RAILWAY_ENVIRONMENT")) or env_bool(
    "NOESIS_TRUST_PROXY_HEADERS"
)
# Nº de proxies de confianza delante de la app. La IP real del cliente es la que
# añade el proxy más cercano: se lee desde la DERECHA de X-Forwarded-For, saltando
# estos saltos. Así el cliente NO puede falsificar su IP para evadir el rate limit
# (si envía "X-Forwarded-For: falsa", queda a la izquierda y se ignora). Railway
# expone un único proxy → 1. Si algún día hay otro delante, súbelo a 2.
PROXY_HOPS = max(1, int(os.getenv("NOESIS_PROXY_HOPS", "1")))

# Datos de demostración: solo se siembran si se pide explícitamente (por defecto NO,
# para que producción arranque limpia con cuentas reales).
SEED_DEMO = env_bool("NOESIS_SEED_DEMO")

# Reinicio de base de datos: si se activa, BORRA todo al arrancar (para empezar de
# cero). Úsalo una vez y quita la variable después.
RESET_DB = env_bool("NOESIS_RESET_DB")

# Registro Veri*Factu nativo. Sin entorno y certificado, solo genera y conserva.
# La huella y el QR siguen los documentos técnicos publicados por la AEAT. Se
# mantienen configurables porque la Agencia puede versionarlos.
VERIFACTU_HASH_ALGORITHM = os.getenv(
    "NOESIS_VERIFACTU_HASH_ALGORITHM", "sha256"
).strip().lower()
VERIFACTU_HASH_TYPE = os.getenv(
    "NOESIS_VERIFACTU_HASH_TYPE", "01"
).strip()
VERIFACTU_HASH_SPEC_VERSION = os.getenv(
    "NOESIS_VERIFACTU_HASH_SPEC_VERSION", "0.1.2"
).strip()
VERIFACTU_RECORD_VERSION = os.getenv(
    "NOESIS_VERIFACTU_RECORD_VERSION", "1.0"
).strip()
VERIFACTU_QR_BASE_URL = os.getenv(
    "NOESIS_VERIFACTU_QR_BASE_URL",
    "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR",
).strip().rstrip("?")

# Identificación del productor y del sistema (bloque SistemaInformatico del XSD).
# El NIF no tiene valor ficticio: debe configurarse antes de activar el modo.
VERIFACTU_PRODUCER_NAME = os.getenv(
    "NOESIS_VERIFACTU_PRODUCER_NAME", "Noesis"
).strip()
VERIFACTU_PRODUCER_NIF = os.getenv(
    "NOESIS_VERIFACTU_PRODUCER_NIF", ""
).strip().upper()
VERIFACTU_SYSTEM_NAME = os.getenv(
    "NOESIS_VERIFACTU_SYSTEM_NAME", "Noesis"
).strip()
VERIFACTU_SYSTEM_ID = os.getenv(
    "NOESIS_VERIFACTU_SYSTEM_ID", "NO"
).strip()
VERIFACTU_SYSTEM_VERSION = os.getenv(
    "NOESIS_VERIFACTU_SYSTEM_VERSION", "0.1.0"
).strip()
VERIFACTU_INSTALLATION_PREFIX = os.getenv(
    "NOESIS_VERIFACTU_INSTALLATION_PREFIX", "noesis"
).strip()

# Remisión AEAT por SOAP/mTLS. Vacío = desactivado, sin llamadas externas.
VERIFACTU_CERT_PATH = os.getenv("VERIFACTU_CERT_PATH", "").strip()
VERIFACTU_KEY_PATH = os.getenv("VERIFACTU_KEY_PATH", "").strip()
VERIFACTU_KEY_PASSWORD = os.getenv("VERIFACTU_KEY_PASSWORD", "")
VERIFACTU_CERT_TYPE = os.getenv(
    "VERIFACTU_CERT_TYPE", "persona"
).strip().lower()
VERIFACTU_AEAT_ENV = os.getenv("VERIFACTU_AEAT_ENV", "").strip().lower()
VERIFACTU_HTTP_TIMEOUT_SECONDS = int(
    os.getenv("NOESIS_VERIFACTU_HTTP_TIMEOUT_SECONDS", "30")
)
VERIFACTU_RETRY_BASE_SECONDS = int(
    os.getenv("NOESIS_VERIFACTU_RETRY_BASE_SECONDS", "30")
)
VERIFACTU_RETRY_MAX_SECONDS = int(
    os.getenv("NOESIS_VERIFACTU_RETRY_MAX_SECONDS", "3600")
)
VERIFACTU_MAX_ATTEMPTS = int(
    os.getenv("NOESIS_VERIFACTU_MAX_ATTEMPTS", "6")
)
VERIFACTU_MAX_RESPONSE_BYTES = int(
    os.getenv("NOESIS_VERIFACTU_MAX_RESPONSE_BYTES", str(2 * 1024 * 1024))
)

# URL pública para emails y vueltas de pago. Railway inyecta su dominio público;
# NOESIS_BASE_URL sigue teniendo prioridad cuando hay un dominio propio.
_RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
_DEFAULT_BASE_URL = (
    f"https://{_RAILWAY_PUBLIC_DOMAIN}"
    if _RAILWAY_PUBLIC_DOMAIN
    else "http://127.0.0.1:8000"
)
BASE_URL = os.getenv("NOESIS_BASE_URL", _DEFAULT_BASE_URL).strip().rstrip("/")
CANONICAL_PUBLIC_HOST = os.getenv(
    "NOESIS_CANONICAL_PUBLIC_HOST", "bynoesis.com"
).strip().lower()
PUBLIC_HOST_ALIAS = (
    CANONICAL_PUBLIC_HOST[4:]
    if CANONICAL_PUBLIC_HOST.startswith("www.")
    else f"www.{CANONICAL_PUBLIC_HOST}"
)

# Host header: en producción solo se aceptan el dominio público y los hosts
# declarados explícitamente. Evita que enlaces y redirecciones se construyan con un
# Host falsificado. En local se mantiene abierto para TestClient y desarrollo.
def build_allowed_hosts() -> list[str]:
    if not IS_PRODUCTION:
        return ["*"]

    base_host = urlsplit(BASE_URL).hostname or ""
    configured_hosts = [
        host.strip().lower()
        for host in os.getenv("NOESIS_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    ]
    railway_private_host = os.getenv(
        "RAILWAY_PRIVATE_DOMAIN", ""
    ).strip().lower()
    # Railway usa este Host exacto durante el healthcheck previo a activar un
    # despliegue. Solo se admite dentro de Railway; no se abre un comodín.
    railway_healthcheck_host = (
        "healthcheck.railway.app"
        if os.getenv("RAILWAY_ENVIRONMENT", "").strip()
        else ""
    )
    return list(dict.fromkeys(
        configured_hosts
        + ([base_host] if base_host else [])
        + ([CANONICAL_PUBLIC_HOST, PUBLIC_HOST_ALIAS]
           if CANONICAL_PUBLIC_HOST else [])
        + ([railway_private_host] if railway_private_host else [])
        + ([railway_healthcheck_host] if railway_healthcheck_host else [])
        + ["localhost", "127.0.0.1"]
    ))


ALLOWED_HOSTS = build_allowed_hosts()

# Identidad legal y apertura comercial. En producción, el alta pública permanece
# cerrada por defecto y nunca se habilita si faltan los datos que el cliente debe
# poder consultar antes de aceptar términos o pagar.
LEGAL_NAME = os.getenv("NOESIS_LEGAL_NAME", "").strip()
LEGAL_NIF = os.getenv("NOESIS_LEGAL_NIF", "").strip().upper()
LEGAL_ADDRESS = os.getenv("NOESIS_LEGAL_ADDRESS", "").strip()
LEGAL_EMAIL = os.getenv("NOESIS_LEGAL_EMAIL", "").strip().lower()
LEGAL_REGISTRY = os.getenv("NOESIS_LEGAL_REGISTRY", "").strip()
LEGAL_DOCUMENT_VERSION = "2026-08-08"
# Buzón que se enseña en la web. El de respaldo es el del dominio propio, no una
# cuenta personal: aparece en el pie, en la política de cookies y en contacto, y
# tres direcciones distintas en un mismo sitio restan credibilidad.
PUBLIC_CONTACT_EMAIL = os.getenv(
    "NOESIS_CONTACT_EMAIL", LEGAL_EMAIL or "info@bynoesis.com"
).strip().lower()
# Buzón donde caen las solicitudes de acceso. Tiene variable propia para que no
# dependa del correo del administrador ni del de contacto público: quien atiende
# las solicitudes no tiene por qué ser quien administra el sistema.
ACCESS_REQUESTS_EMAIL = os.getenv(
    "NOESIS_REQUESTS_EMAIL", "info@bynoesis.com"
).strip().lower()
# Envío de correo por API (HTTPS). Necesario en plataformas como Railway, que
# bloquean la salida a los puertos de SMTP para evitar el envío de spam. Si hay
# clave, se usa esta vía; si no, se cae al SMTP de siempre.
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
BREVO_API_URL = os.getenv(
    "BREVO_API_URL", "https://api.brevo.com/v3/smtp/email"
).strip()
BREVO_TIMEOUT_SECONDS = int(os.getenv("BREVO_TIMEOUT_SECONDS", "15"))
SMTP_PROVIDER_NAME = os.getenv("NOESIS_SMTP_PROVIDER_NAME", "").strip()
SMTP_PROVIDER_REGION = os.getenv("NOESIS_SMTP_PROVIDER_REGION", "").strip()
PUBLIC_SIGNUP_ENABLED = env_bool(
    "NOESIS_PUBLIC_SIGNUP_ENABLED", not IS_PRODUCTION
)


def legal_identity_ready() -> bool:
    """True cuando los cuatro datos legales mínimos están configurados."""
    return all((LEGAL_NAME, LEGAL_NIF, LEGAL_ADDRESS, LEGAL_EMAIL))


def public_signup_available() -> bool:
    """Impide aceptar términos o pagos con textos legales incompletos."""
    return PUBLIC_SIGNUP_ENABLED and (legal_identity_ready() or not IS_PRODUCTION)

# Límites defensivos de documentos. Son independientes del tamaño en MB: una
# imagen comprimida pequeña puede intentar reservar cientos de megapíxeles.
MAX_IMAGE_PIXELS = max(
    1_000_000, int(os.getenv("NOESIS_MAX_IMAGE_PIXELS", "40000000"))
)
MAX_PDF_PAGES = max(1, int(os.getenv("NOESIS_MAX_PDF_PAGES", "200")))
# Techo HTTP global previo al parser multipart. Los límites por tipo siguen siendo
# más bajos; este evita que una petición declaradamente gigante llegue a parsearse.
MAX_REQUEST_BYTES = max(
    1_048_576, int(os.getenv("NOESIS_MAX_REQUEST_BYTES", "20971520"))
)

# Antivirus privado opcional. ClamAV recibe el archivo por INSTREAM dentro de la
# red del despliegue; no se manda contenido a una API externa.
CLAMAV_HOST = os.getenv("NOESIS_CLAMAV_HOST", "").strip()
CLAMAV_PORT = max(1, min(65_535, int(os.getenv("NOESIS_CLAMAV_PORT", "3310"))))
CLAMAV_TIMEOUT_SECONDS = max(
    0.5, float(os.getenv("NOESIS_CLAMAV_TIMEOUT_SECONDS", "8"))
)
CLAMAV_REQUIRED = env_bool(
    "NOESIS_CLAMAV_REQUIRED", IS_PRODUCTION and bool(CLAMAV_HOST)
)

# Pool limitado: evita agotar PostgreSQL cuando coinciden web, scheduler y colas.
DB_POOL_MIN_SIZE = max(0, int(os.getenv("NOESIS_DB_POOL_MIN_SIZE", "1")))
DB_POOL_MAX_SIZE = max(
    DB_POOL_MIN_SIZE or 1, int(os.getenv("NOESIS_DB_POOL_MAX_SIZE", "8"))
)
DB_POOL_TIMEOUT = max(1.0, float(os.getenv("NOESIS_DB_POOL_TIMEOUT", "10")))

# Registro operativo sin datos personales. Se activa por defecto en producción.
LOG_REQUESTS = env_bool("NOESIS_LOG_REQUESTS", IS_PRODUCTION)

# Caducidad por inactividad, además del máximo absoluto firmado por Starlette.
SESSION_IDLE_MINUTES = max(15, int(os.getenv("NOESIS_SESSION_IDLE_MINUTES", "720")))
ADMIN_SESSION_IDLE_MINUTES = max(
    15, int(os.getenv("NOESIS_ADMIN_SESSION_IDLE_MINUTES", "60"))
)

# Acceso opcional con Google (OAuth 2.0 / OpenID Connect). Noesis no muestra ni
# intenta este flujo hasta que ambos valores estén configurados en el entorno.
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()


def google_oauth_available() -> bool:
    return bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)

# Correos con acceso al panel de administración (/admin). Admite varios separados
# por coma, para que un equipo pequeño no tenga que compartir una misma cuenta.
ADMIN_EMAILS = tuple(dict.fromkeys(
    correo.strip().lower()
    for correo in os.getenv("NOESIS_ADMIN_EMAIL", "").split(",")
    if correo.strip()
))
# El primero sigue siendo el responsable principal: es el que reciben los avisos
# y el que se muestra en los diagnósticos.
ADMIN_EMAIL = ADMIN_EMAILS[0] if ADMIN_EMAILS else ""


def is_admin_email(correo: str | None) -> bool:
    """True si ese correo puede entrar al panel interno.

    Mira las dos variables a propósito. `ADMIN_EMAIL` se deriva de `ADMIN_EMAILS`,
    así que en producción no añade nada; pero quien cambie solo una de las dos
    —una prueba, un script— esperaría que surtiera efecto, y si no lo hiciera el
    resultado sería un permiso concedido o denegado sin que nada lo avise. Es
    exactamente la clase de silencio que no puede permitirse un control de acceso.
    """
    if not correo:
        return False
    permitidos = set(ADMIN_EMAILS)
    if ADMIN_EMAIL:
        permitidos.add(ADMIN_EMAIL.strip().lower())
    return str(correo).strip().lower() in permitidos
ADMIN_REQUIRE_GOOGLE_OAUTH = env_bool(
    "NOESIS_ADMIN_REQUIRE_GOOGLE_OAUTH",
    IS_PRODUCTION,
)

# Envío de emails (reset de contraseña, avisos). Si no hay SMTP, se registra en log.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "Noesis <no-reply@bynoesis.com>")
EMAIL_RETRY_BASE_SECONDS = int(os.getenv("EMAIL_RETRY_BASE_SECONDS", "30"))
EMAIL_RETRY_MAX_SECONDS = int(os.getenv("EMAIL_RETRY_MAX_SECONDS", "3600"))

# Cobro de la suscripción (Stripe). Si no hay clave, el alta entra en prueba manual.
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_AUTONOMO = os.getenv("STRIPE_PRICE_AUTONOMO", "")  # 29 € + IVA / mes
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "")            # 49 € + IVA / mes
STRIPE_PRICE_PREMIUM = os.getenv("STRIPE_PRICE_PREMIUM", "")    # 99 € + IVA / mes
STRIPE_PRICE_AUTONOMO_ANNUAL = os.getenv("STRIPE_PRICE_AUTONOMO_ANNUAL", "")
STRIPE_PRICE_PRO_ANNUAL = os.getenv("STRIPE_PRICE_PRO_ANNUAL", "")
STRIPE_PRICE_PREMIUM_ANNUAL = os.getenv("STRIPE_PRICE_PREMIUM_ANNUAL", "")
# El catálogo se comunica sin IVA. Checkout debe calcularlo con la dirección y
# el NIF fiscal del cliente; desactivarlo solo sirve para pruebas controladas.
STRIPE_AUTOMATIC_TAX = env_bool("NOESIS_STRIPE_AUTOMATIC_TAX", True)
TRIAL_DAYS = int(os.getenv("NOESIS_TRIAL_DAYS", "14"))
# Caducidad del enlace de invitación con el que el titular elige su contraseña.
# Más largo que un "he olvidado la contraseña" porque el alta la inicia el equipo.
INVITE_TTL_MINUTES = int(os.getenv("NOESIS_INVITE_TTL_MINUTES", str(7 * 24 * 60)))

# Firma de webhooks y límites de entrada.
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
WHATSAPP_RETRY_BASE_SECONDS = int(
    os.getenv("WHATSAPP_RETRY_BASE_SECONDS", "30")
)
WHATSAPP_RETRY_MAX_SECONDS = int(
    os.getenv("WHATSAPP_RETRY_MAX_SECONDS", "3600")
)
WHATSAPP_MAX_ATTEMPTS = int(os.getenv("WHATSAPP_MAX_ATTEMPTS", "6"))
WHATSAPP_TEMPLATE_LANGUAGE = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "es")
WHATSAPP_TEMPLATE_DAILY_SUMMARY = os.getenv(
    "WHATSAPP_TEMPLATE_DAILY_SUMMARY", "noesis_resumen_diario"
)
WHATSAPP_TEMPLATE_WEEKLY_SUMMARY = os.getenv(
    "WHATSAPP_TEMPLATE_WEEKLY_SUMMARY", "noesis_resumen_semanal"
)
WHATSAPP_TEMPLATE_PAYMENT_ALERT = os.getenv(
    "WHATSAPP_TEMPLATE_PAYMENT_ALERT", "noesis_aviso_cobros"
)
WHATSAPP_TEMPLATE_PAYMENT_REMINDER = os.getenv(
    "WHATSAPP_TEMPLATE_PAYMENT_REMINDER", "noesis_recordatorio_cobro"
)
WHATSAPP_TEMPLATE_INVOICE = os.getenv(
    "WHATSAPP_TEMPLATE_INVOICE", "noesis_factura_lista"
)
WHATSAPP_TEMPLATE_QUOTE_FOLLOWUP = os.getenv(
    "WHATSAPP_TEMPLATE_QUOTE_FOLLOWUP", "noesis_seguimiento_presupuesto"
)
WHATSAPP_TEMPLATE_APPOINTMENT_REMINDER = os.getenv(
    "WHATSAPP_TEMPLATE_APPOINTMENT_REMINDER", "noesis_recordatorio_cita"
)
WHATSAPP_TEMPLATE_DAILY_CLOSING = os.getenv(
    "WHATSAPP_TEMPLATE_DAILY_CLOSING", "noesis_cierre_dia"
)
WHATSAPP_TEMPLATE_TAX_NOTICE = os.getenv(
    "WHATSAPP_TEMPLATE_TAX_NOTICE", "noesis_aviso_fiscal"
)
# Transcripción de voz vía API (Groq/Whisper). Si falta, se intenta whisper local.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
# Vacío = detección automática. Solo se usa como pista ISO-639-1 cuando el
# despliegue sabe que todo el audio será de un idioma concreto (es/ca/en).
WHISPER_LANGUAGE = os.getenv("NOESIS_WHISPER_LANGUAGE", "").strip().lower()
# Tope diario de extracciones con IA por negocio (fotos/PDFs): protege el margen.
MAX_DAILY_EXTRACTIONS = int(os.getenv("NOESIS_MAX_DAILY_EXTRACTIONS", "30"))
MAX_JSON_BYTES = int(os.getenv("NOESIS_MAX_JSON_BYTES", "262144"))
MAX_AUDIO_BYTES = int(os.getenv("NOESIS_MAX_AUDIO_BYTES", str(12 * 1024 * 1024)))
MAX_CHAT_CHARS = int(os.getenv("NOESIS_MAX_CHAT_CHARS", "4000"))

# Las copias pueden apuntar a un volumen o directorio distinto del archivo principal.
BACKUP_DIR = Path(
    os.getenv("NOESIS_BACKUP_DIR", str(DB_PATH.parent / "backups"))
)
# Copia externa opcional compatible con S3. Sin las cuatro variables principales
# no se realiza ninguna petición ni se incurre en coste.
BACKUP_S3_ENDPOINT = os.getenv("NOESIS_BACKUP_S3_ENDPOINT", "").strip()
BACKUP_S3_BUCKET = os.getenv("NOESIS_BACKUP_S3_BUCKET", "").strip()
BACKUP_S3_ACCESS_KEY = os.getenv("NOESIS_BACKUP_S3_ACCESS_KEY", "").strip()
BACKUP_S3_SECRET_KEY = os.getenv("NOESIS_BACKUP_S3_SECRET_KEY", "").strip()
BACKUP_S3_REGION = os.getenv("NOESIS_BACKUP_S3_REGION", "us-east-1").strip()
BACKUP_S3_PREFIX = os.getenv("NOESIS_BACKUP_S3_PREFIX", "noesis").strip()
BACKUP_S3_SSE = os.getenv("NOESIS_BACKUP_S3_SSE", "AES256").strip()
BACKUP_S3_TIMEOUT_SECONDS = int(
    os.getenv("NOESIS_BACKUP_S3_TIMEOUT_SECONDS", "60")
)
