from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import logging

logger = logging.getLogger("limiter")

# ─────────────────────────────────────────────────────────────────────────────
# REDIS CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

def redis_available() -> bool:
    """Check if Redis is reachable."""
    try:
        import redis
        r = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        logger.info("✅ Redis connected: %s", REDIS_URL)
        return True
    except Exception as e:
        logger.warning("❌ Redis unavailable (%s) — falling back to in-memory", e)
        return False

# ─────────────────────────────────────────────────────────────────────────────
# INITIALIZE LIMITER (with automatic fallback)
# ─────────────────────────────────────────────────────────────────────────────

try:
    if redis_available():
        # ✅ PRODUCTION: Use Redis for distributed rate limiting
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=REDIS_URL,
            strategy="moving-window",
            default_limits=["100/hour"],  # Global fallback
            in_memory_fallback_enabled=False,  # Fail fast if Redis down
        )
        logger.info("📊 Rate limiter initialized with Redis backend (distributed)")
    else:
        raise Exception("Redis not available")
        
except Exception as e:
    # ⚠️ LOCAL DEV: Fall back to in-memory (single process only)
    logger.warning(
        "⚠️  Using in-memory rate limiter (DEVELOPMENT ONLY). "
        "Multi-process deployments will bypass limits. "
        "Fix: Install Redis and set REDIS_URL in .env"
    )
    limiter = Limiter(
        key_func=get_remote_address,
        strategy="moving-window",
        default_limits=["100/hour"],
        in_memory_fallback_enabled=True,
    )
