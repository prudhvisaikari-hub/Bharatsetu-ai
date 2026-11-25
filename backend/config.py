import os
import secrets
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger("bharatsetu.config")

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")

KNOWN_FORBIDDEN_JWT_SECRETS = {
    "bharatsetu-msme-pithampur-secure-jwt-key-2026",
    "bharatsetu-dev-secret-key-change-in-production-2026",
}

def validate_jwt_secret(raw_secret: str, is_demo: bool) -> str:
    cleaned = (raw_secret or "").strip()
    if not cleaned or len(cleaned) < 32:
        if is_demo:
            ephemeral = secrets.token_urlsafe(48)
            logger.warning("⚠️ DEMO_MODE active: JWT_SECRET missing or <32 characters. Generated ephemeral secret for this process.")
            return ephemeral
        raise RuntimeError(
            "FATAL: JWT_SECRET environment variable is missing or shorter than 32 characters when DEMO_MODE=false. "
            "Configure a secure random secret using: python -c \"import secrets;print(secrets.token_urlsafe(48))\""
        )
    if not is_demo and cleaned in KNOWN_FORBIDDEN_JWT_SECRETS:
        raise RuntimeError(
            "FATAL: JWT_SECRET matches a known public default string from repository history. "
            "Generate a unique random secret using: python -c \"import secrets;print(secrets.token_urlsafe(48))\""
        )
    return cleaned

JWT_SECRET = validate_jwt_secret(os.getenv("JWT_SECRET", ""), DEMO_MODE)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Default model to claude-sonnet-5-5
BHARATSETU_MODEL = os.getenv("BHARATSETU_MODEL", "claude-sonnet-5-5")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'bharatsetu.db'}")

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 8 * 1024 * 1024))  # 8 MB
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

DPI_MODE = os.getenv("DPI_MODE", "mock").lower()  # "mock" or "real"
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "true" if DEMO_MODE else "false").lower() in ("true", "1", "yes")
TRUSTED_PROXY = os.getenv("TRUSTED_PROXY", "false").lower() in ("true", "1", "yes")
BHASHINI_API_KEY = os.getenv("BHASHINI_API_KEY", "")
BHASHINI_USER_ID = os.getenv("BHASHINI_USER_ID", "")
BHASHINI_PIPELINE_ID = os.getenv("BHASHINI_PIPELINE_ID", "")

WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
def validate_phone_hash_key(raw_key: str, is_demo: bool) -> str:
    cleaned = (raw_key or "").strip()
    if not cleaned or len(cleaned) < 32:
        if is_demo:
            ephemeral = secrets.token_urlsafe(48)
            logger.warning("⚠️ DEMO_MODE active: PHONE_HASH_KEY missing or <32 characters. Generated ephemeral key for this process.")
            return ephemeral
        raise RuntimeError(
            "FATAL: PHONE_HASH_KEY environment variable is missing or shorter than 32 characters when DEMO_MODE=false. "
            "Configure a secure random key using: python -c \"import secrets;print(secrets.token_urlsafe(48))\""
        )
    return cleaned

PHONE_HASH_KEY = validate_phone_hash_key(os.getenv("PHONE_HASH_KEY", os.getenv("PHONE_HASH_SALT", "")), DEMO_MODE)
PHONE_HASH_SALT = PHONE_HASH_KEY
