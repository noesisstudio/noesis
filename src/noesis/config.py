"""Configuración central. Lee variables del archivo .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carga el .env de la raíz del proyecto (si existe).
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


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
# Modelo BARATO para el respaldo del chat (cuando el cerebro local no entiende la
# frase). Haiku minimiza el coste: el 90% se resuelve gratis en local y solo lo
# realmente complejo paga, a fracción de céntimo. Cámbialo con NOESIS_FALLBACK_MODEL.
FALLBACK_MODEL = os.getenv("NOESIS_FALLBACK_MODEL", "claude-haiku-4-5-20251001")
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

# Clave de Holded para facturación real (Verifactu). Si está, se usa Holded.
HOLDED_API_KEY = os.getenv("HOLDED_API_KEY", "")

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

# URL pública para emails y vueltas de pago. Railway inyecta su dominio público;
# NOESIS_BASE_URL sigue teniendo prioridad cuando hay un dominio propio.
_RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
_DEFAULT_BASE_URL = (
    f"https://{_RAILWAY_PUBLIC_DOMAIN}"
    if _RAILWAY_PUBLIC_DOMAIN
    else "http://127.0.0.1:8000"
)
BASE_URL = os.getenv("NOESIS_BASE_URL", _DEFAULT_BASE_URL).strip().rstrip("/")

# Email del fundador con acceso al panel de administración (/admin).
ADMIN_EMAIL = os.getenv("NOESIS_ADMIN_EMAIL", "").strip().lower()

# Envío de emails (reset de contraseña, avisos). Si no hay SMTP, se registra en log.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "Noesis <no-reply@bynoesis.com>")

# Cobro de la suscripción (Stripe). Si no hay clave, el alta entra en prueba manual.
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_AUTONOMO = os.getenv("STRIPE_PRICE_AUTONOMO", "")  # price_xxx mensual 29€
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "")            # price_xxx mensual 39€
TRIAL_DAYS = int(os.getenv("NOESIS_TRIAL_DAYS", "14"))

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
WHATSAPP_TEMPLATE_DAILY_CLOSING = os.getenv(
    "WHATSAPP_TEMPLATE_DAILY_CLOSING", "noesis_cierre_dia"
)
WHATSAPP_TEMPLATE_TAX_NOTICE = os.getenv(
    "WHATSAPP_TEMPLATE_TAX_NOTICE", "noesis_aviso_fiscal"
)
# Transcripción de voz vía API (Groq/Whisper). Si falta, se intenta whisper local.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
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
BACKUP_S3_TIMEOUT_SECONDS = int(
    os.getenv("NOESIS_BACKUP_S3_TIMEOUT_SECONDS", "60")
)
