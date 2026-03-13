import os
from dotenv import load_dotenv

# Load .env from the project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

def get_env_var(name: str, default: str = None, required: bool = False) -> str:
    """Get environment variable with optional default and required flag."""
    value = os.getenv(name, default)
    if required and not value:
        raise ValueError(f"Required environment variable '{name}' not set")
    return value

# ============================================================
# DATABASE CONFIGURATION
# ============================================================
DB_USER = get_env_var("DB_USER", "postgres")
DB_PASSWORD = get_env_var("DB_PASSWORD", "password")
DB_HOST = get_env_var("DB_HOST", "localhost")
DB_PORT = get_env_var("DB_PORT", "5432")
DB_NAME = get_env_var("DB_NAME", "plagiarism_db")

# ============================================================
# STORAGE CONFIGURATION
# ============================================================
STORAGE_DIR = get_env_var("STORAGE_DIR", "/tmp/plagiarism_files")

# ============================================================
# SECURITY
# ============================================================
SECRET_KEY = get_env_var("SECRET_KEY", "your-secret-key")
ALGORITHM = get_env_var("ALGORITHM", "HS256")

# ============================================================
# API KEYS (CRITICAL)
# ============================================================
GOOGLE_API_KEY = get_env_var("GOOGLE_API_KEY", required=False)
GOOGLE_CSE_ID = get_env_var("GOOGLE_CSE_ID", required=False)
GEMINI_API_KEY = get_env_var("GEMINI_API_KEY", required=False)

# ============================================================
# GEMINI CONFIGURATION
# ============================================================
GEMINI_MODEL = get_env_var("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_FALLBACK_MODEL = get_env_var("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash-lite")
GEMINI_MAX_RETRIES = int(get_env_var("GEMINI_MAX_RETRIES", "3"))
GEMINI_RETRY_DELAY = int(get_env_var("GEMINI_RETRY_DELAY", "60"))

# ============================================================
# FRONTEND CONFIGURATION
# ============================================================
FRONTEND_URL = get_env_var("FRONTEND_URL", "http://localhost:3000")

# ============================================================
# DATA RETENTION
# ============================================================
DATA_RETENTION_DAYS = int(get_env_var("DATA_RETENTION_DAYS", "365"))

# ============================================================
# REDIS CONFIGURATION (for distributed rate limiting)
# ============================================================
REDIS_URL = get_env_var("REDIS_URL", "redis://localhost:6379")

# ============================================================
# RATE LIMITING
# ============================================================
RATE_LIMIT_LOGIN = get_env_var("RATE_LIMIT_LOGIN", "10/minute")
RATE_LIMIT_UPLOAD = get_env_var("RATE_LIMIT_UPLOAD", "20/minute")
RATE_LIMIT_ANALYZE = get_env_var("RATE_LIMIT_ANALYZE", "20/minute")
RATE_LIMIT_STATUS = get_env_var("RATE_LIMIT_STATUS", "30/minute")

# Ensure storage directory exists
os.makedirs(STORAGE_DIR, exist_ok=True)