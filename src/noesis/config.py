"""Configuración central. Lee variables del archivo .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carga el .env de la raíz del proyecto (si existe).
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("NOESIS_MODEL", "claude-sonnet-4-6")
BUSINESS_NAME = os.getenv("NOESIS_BUSINESS_NAME", "Mi Negocio")

# La base de datos vive en la raíz del proyecto por defecto. En producción se
# apunta a un volumen persistente con NOESIS_DB_PATH (en hosts el disco es efímero).
DB_PATH = Path(os.getenv("NOESIS_DB_PATH", str(ROOT / "noesis.db")))

# IVA por defecto en España (servicios generales).
DEFAULT_VAT_RATE = 21

# Clave para firmar las sesiones (cookies). En producción, ponla en el .env.
SECRET_KEY = os.getenv("NOESIS_SECRET", "dev-secret-cambiar-en-produccion")

# En producción (Railway inyecta RAILWAY_ENVIRONMENT) las cookies de sesión deben
# viajar solo por HTTPS. En local (http://127.0.0.1) se desactiva para poder entrar.
HTTPS_ONLY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("NOESIS_HTTPS"))

# True cuando estamos en un entorno expuesto (para exigir configuración segura).
IS_PRODUCTION = HTTPS_ONLY

# Datos de demostración: solo se siembran si se pide explícitamente (por defecto NO,
# para que producción arranque limpia con cuentas reales).
SEED_DEMO = bool(os.getenv("NOESIS_SEED_DEMO"))

# Reinicio de base de datos: si se activa, BORRA todo al arrancar (para empezar de
# cero). Úsalo una vez y quita la variable después.
RESET_DB = bool(os.getenv("NOESIS_RESET_DB"))

# Clave de Holded para facturación real (Verifactu). Si está, se usa Holded.
HOLDED_API_KEY = os.getenv("HOLDED_API_KEY", "")
