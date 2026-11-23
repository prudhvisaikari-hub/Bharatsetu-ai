import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Default to valid Claude 3.5 Sonnet or 3.7 Sonnet model name
BHARATSETU_MODEL = os.getenv("BHARATSETU_MODEL", "claude-3-5-sonnet-20241022")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'bharatsetu.db'}")
JWT_SECRET = os.getenv("JWT_SECRET", "bharatsetu-dev-secret-key-change-in-production-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 8 * 1024 * 1024))  # 8 MB
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))

DPI_MODE = os.getenv("DPI_MODE", "mock").lower()  # "mock" or "real"
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "true" if DEMO_MODE else "false").lower() in ("true", "1", "yes")
TRUSTED_PROXY = os.getenv("TRUSTED_PROXY", "false").lower() in ("true", "1", "yes")
BHASHINI_API_KEY = os.getenv("BHASHINI_API_KEY", "")
BHASHINI_USER_ID = os.getenv("BHASHINI_USER_ID", "")
BHASHINI_PIPELINE_ID = os.getenv("BHASHINI_PIPELINE_ID", "")

WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "bharatsetu_verify_token")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
