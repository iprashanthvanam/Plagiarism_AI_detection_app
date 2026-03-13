"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         TKREC GEMINI VISION OCR SERVICE — WITH M5: CIRCUIT BREAKER          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  GEMINI PRIMARY PATH (for scanned PDFs, images):                            ║
║  1. Multilingual by design (Telugu, Hindi, Tamil, etc.)                    ║
║  2. Handles handwriting, diagrams, embedded images natively                 ║
║  3. Per-minute rate limit: 15 requests/min (free tier)                      ║
║  4. Per-day quota: 1,500 requests/day (free tier)                           ║
║                                                                              ║
║  M5: CIRCUIT BREAKER (NEW)                                                 ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  Detects Gemini API quota exhaustion (429, RESOURCE_EXHAUSTED errors).      ║
║  - Tracks consecutive failures per model (primary + fallback)               ║
║  - Opens circuit after 2 failures (stops calling API)                       ║
║  - Returns empty string gracefully                                          ║
║  - Extraction falls back to local Tesseract OCR                             ║
║  - Analysis continues without Gemini (lower accuracy on scanned)            ║
║  - Logs warnings for monitoring                                             ║
║  - Auto-recovery after 1 hour timeout                                       ║
║                                                                              ║
║  FALLBACK CHAIN:                                                             ║
║  Primary Model (gemini-2.0-flash)                                           ║
║    ↓ (if quota)                                                              ║
║  Fallback Model (gemini-2.0-flash-lite)                                     ║
║    ↓ (if both quota'd)                                                       ║
║  Local Tesseract OCR                                                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import re
import time
import mimetypes
import asyncio
import hashlib
import logging
import unicodedata
from typing import Optional, Dict
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel

GEMINI_API_KEY        = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL          = os.getenv("GEMINI_MODEL",          "gemini-2.0-flash")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash-lite")
GEMINI_MAX_RETRIES    = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
GEMINI_RETRY_DELAY    = int(os.getenv("GEMINI_RETRY_DELAY", "60"))

# ─────────────────────────────────────────────────────────────────────────────
# CIRCUIT BREAKER CONFIGURATION (M5)
# ─────────────────────────────────────────────────────────────────────────────
CIRCUIT_BREAKER_THRESHOLD = 2  # Failures before opening circuit
CIRCUIT_BREAKER_RESET_SECS = 3600  # Reset after 1 hour

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

class TextExtractionResult(BaseModel):
    extracted_text: str


# ─────────────────────────────────────────────────────────────────────────────
# M5: CIRCUIT BREAKER CLASS FOR GEMINI
# ─────────────────────────────────────────────────────────────────────────────

class GeminiCircuitBreaker:
    """
    Circuit breaker for Gemini Vision API.
    
    States:
    - CLOSED (normal): API calls proceed
    - OPEN (quota hit): API calls blocked, returns empty immediately
    
    Tracks failures per model separately.
    Detects quota exhaustion (429, RESOURCE_EXHAUSTED, rate limit, etc.)
    """
    
    def __init__(self, threshold: int = CIRCUIT_BREAKER_THRESHOLD,
                 reset_timeout: int = CIRCUIT_BREAKER_RESET_SECS):
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        # Per-model failure tracking
        self.failure_counts: Dict[str, int] = {}
        self.last_failure_times: Dict[str, datetime] = {}
        self.is_open_models: Dict[str, bool] = {}
    
    def record_success(self, model: str):
        """Call after successful API request."""
        if model in self.failure_counts:
            self.failure_counts[model] = 0
            self.is_open_models[model] = False
            logger.info("✅ Gemini (%s) recovered — circuit CLOSED", model)
    
    def record_failure(self, model: str, error: str = ""):
        """Call after failed API request."""
        if model not in self.failure_counts:
            self.failure_counts[model] = 0
        
        self.failure_counts[model] += 1
        self.last_failure_times[model] = datetime.utcnow()
        
        logger.warning(
            "❌ Gemini (%s) failure #%d/%d | Error: %s",
            model, self.failure_counts[model], self.threshold, error[:100]
        )
        
        if self.failure_counts[model] >= self.threshold:
            self.is_open_models[model] = True
            logger.error(
                "⛔ CIRCUIT BREAKER OPEN [%s] — Gemini quota likely exhausted. "
                "Falling back to local Tesseract OCR for %d seconds.",
                model, self.reset_timeout
            )
    
    def can_attempt(self, model: str) -> bool:
        """Check if we can attempt an API call for this model."""
        if not self.is_open_models.get(model, False):
            return True
        
        # Check if recovery timeout has passed
        last_failure = self.last_failure_times.get(model)
        if last_failure:
            elapsed = (datetime.utcnow() - last_failure).total_seconds()
            if elapsed > self.reset_timeout:
                self.is_open_models[model] = False
                self.failure_counts[model] = 0
                logger.info(
                    "🔄 Circuit breaker timeout reached [%s] — attempting recovery",
                    model
                )
                return True
        
        return False
    
    def is_quota_error(self, error_text: str) -> bool:
        """Detect if error is quota/rate-limit related."""
        error_lower = error_text.lower()
        quota_signals = {
            "quota", "429", "resource_exhausted", "rate limit",
            "too many requests", "exceeded", "exhausted",
            "quota exceeded", "quota_exceeded",
        }
        return any(sig in error_lower for sig in quota_signals)
    
    def get_status(self, model: str) -> Dict[str, any]:
        """Return circuit breaker status for monitoring."""
        return {
            "model": model,
            "is_open": self.is_open_models.get(model, False),
            "failure_count": self.failure_counts.get(model, 0),
            "threshold": self.threshold,
            "last_failure_time": (
                self.last_failure_times.get(model, None).isoformat()
                if self.last_failure_times.get(model) else None
            ),
            "status": "⛔ OPEN" if self.is_open_models.get(model, False) else "✅ CLOSED",
        }


# Global circuit breaker instances (one per model)
_circuit_breaker_primary = GeminiCircuitBreaker()
_circuit_breaker_fallback = GeminiCircuitBreaker()


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI CLIENT INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────

# Google AI SDK doesn't override our explicit api_key arg.
# Temporarily remove GOOGLE_API_KEY so Gemini client uses only GEMINI_API_KEY
_google_key_backup = os.environ.pop("GOOGLE_API_KEY", None)

client = None
_genai_available = False

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set — Gemini OCR disabled (local OCR will be used)")
else:
    try:
        from google import genai as _genai
        client = _genai.Client(api_key=GEMINI_API_KEY)
        _genai_available = True
        logger.info(
            "✅ Gemini client ready (primary=%s, fallback=%s)",
            GEMINI_MODEL, GEMINI_FALLBACK_MODEL
        )
    except Exception as e:
        logger.error("❌ Gemini client init failed: %s", e)

if _google_key_backup is not None:
    os.environ["GOOGLE_API_KEY"] = _google_key_backup

# MIME types Gemini Files API accepts directly
GEMINI_SUPPORTED_MIMES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
}

_EXT_MIME = {
    ".pdf":  "application/pdf",
    ".doc":  "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _hash_file(path: str) -> str:
    """Compute SHA256 hash of file for caching."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize(text: str) -> str:
    """Normalize Unicode text to ASCII-safe format."""
    try:
        return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    except Exception:
        return text


def _parse_retry_delay(err: str) -> int:
    """Extract retry-after delay from error message."""
    m = re.search(r"retry in (\d+)", err)
    return int(m.group(1)) + 5 if m else GEMINI_RETRY_DELAY


def _parse_json(response_text: str) -> Optional[str]:
    """
    Extract JSON object from Gemini response text.
    Handles cases where response contains non-JSON wrapper text.
    """
    text = response_text.strip()
    if not text.startswith("{"):
        safe = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'{{"extracted_text": "{safe}"}}'
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    TextExtractionResult.model_validate_json(candidate)
                    return candidate
                except Exception:
                    return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI API CALLS (WITH CIRCUIT BREAKER & RETRY LOGIC)
# ─────────────────────────────────────────────────────────────────────────────

def _call_gemini_sync(uploaded_file, model: str) -> Optional[str]:
    """
    Synchronous Gemini call with per-minute retry and model fallback.
    
    WITH M5 CIRCUIT BREAKER:
    - Checks circuit breaker before attempting call
    - Detects 429 / RESOURCE_EXHAUSTED errors
    - Records failures in circuit breaker
    - Falls back to next model if quota hit
    
    Returns response text or None on error.
    """
    models = [model]
    if model != GEMINI_FALLBACK_MODEL:
        models.append(GEMINI_FALLBACK_MODEL)

    prompt = (
        "Extract ALL readable text from the provided file accurately. "
        "Preserve reading order. Include all text, numbers, tables, symbols. "
        'Return ONLY valid JSON: { "extracted_text": "..." }'
    )

    for current_model in models:
        # ── Check circuit breaker before attempting ──────────────────────
        circuit_breaker = (
            _circuit_breaker_primary if current_model == GEMINI_MODEL
            else _circuit_breaker_fallback
        )
        
        if not circuit_breaker.can_attempt(current_model):
            logger.warning(
                "🔴 Circuit breaker OPEN [%s] — skipping Gemini call. "
                "Quota likely exhausted. Falling back to local OCR.",
                current_model
            )
            continue
        
        for attempt in range(1, GEMINI_MAX_RETRIES + 1):
            try:
                logger.info(
                    "Gemini: model=%s attempt=%d/%d",
                    current_model, attempt, GEMINI_MAX_RETRIES
                )
                resp = client.models.generate_content(
                    model=current_model,
                    contents=[prompt, uploaded_file],
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": TextExtractionResult,
                    },
                )
                
                # ── SUCCESS: Record success in circuit breaker ───────────
                circuit_breaker.record_success(current_model)
                logger.info("✅ Gemini success (model=%s)", current_model)
                return resp.text

            except Exception as e:
                err = str(e)
                
                # ── Check if quota error ──────────────────────────────
                is_quota = circuit_breaker.is_quota_error(err)
                
                if "404" in err or "NOT_FOUND" in err:
                    logger.error("❌ Model %s not found — trying next", current_model)
                    break
                
                if "429" in err or "RESOURCE_EXHAUSTED" in err or is_quota:
                    error_msg = "quota/rate-limit" if is_quota else "429"
                    circuit_breaker.record_failure(current_model, error_msg)
                    
                    wait = _parse_retry_delay(err)
                    if attempt < GEMINI_MAX_RETRIES:
                        logger.warning(
                            "⛔ Gemini %s on %s (attempt %d/%d) — waiting %ds",
                            error_msg, current_model, attempt, GEMINI_MAX_RETRIES, wait
                        )
                        time.sleep(wait)
                        continue
                    logger.warning(
                        "⛔ Quota exhausted on %s after %d attempts — trying next model",
                        current_model, GEMINI_MAX_RETRIES
                    )
                    break
                
                # ── Non-quota errors (auth, network, etc.) ──────────────
                error_msg = err[:200]
                circuit_breaker.record_failure(current_model, error_msg)
                logger.error(
                    "❌ Gemini non-retryable error (model=%s): %s",
                    current_model, error_msg
                )
                return None

    logger.error("⛔ All Gemini models exhausted or circuit open")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI CACHE (reduce repeated API calls)
# ─────────────────────────────────────────────────────────────────────────────

_GEMINI_CACHE: Dict[str, str] = {}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — EXTRACT TEXT WITH GEMINI
# ─────────────────────────────────────────────────────────────────────────────

async def extract_text_with_gemini(file_path: str, is_pdf: bool = False) -> str:
    """
    Gemini OCR fallback. Called when local extraction fails.
    
    WITH M5 CIRCUIT BREAKER:
    - Detects quota exhaustion gracefully
    - Returns empty string if quota hit (analysis continues with local OCR)
    - Never blocks the analysis pipeline
    
    Args:
        file_path: Path to file (PDF, image, etc.)
        is_pdf: Kept for backward compatibility, ignored (MIME detection used instead)
    
    Returns:
        Extracted text, or empty string on failure
    """
    if not _genai_available or not client:
        logger.warning("Gemini unavailable — local OCR should have handled this")
        return ""

    if not os.path.exists(file_path):
        return ""

    ext = os.path.splitext(file_path)[1].lower()
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = _EXT_MIME.get(ext)

    if not mime_type or mime_type not in GEMINI_SUPPORTED_MIMES:
        logger.warning("Unsupported MIME for Gemini: %s (%s)", mime_type, file_path)
        return ""

    # ── Cache check ──────────────────────────────────────────────────
    file_hash = None
    try:
        file_hash = _hash_file(file_path)
        if file_hash in _GEMINI_CACHE:
            logger.info("✅ Gemini cache hit: %s", file_path)
            return _GEMINI_CACHE[file_hash]
    except Exception:
        pass

    uploaded_file = None
    try:
        logger.info(
            "Gemini OCR upload: %s (mime=%s)",
            os.path.basename(file_path), mime_type
        )
        uploaded_file = client.files.upload(file=file_path)

        # ── Call Gemini with circuit breaker protection ──────────────
        response_text = await asyncio.to_thread(
            _call_gemini_sync, uploaded_file, GEMINI_MODEL
        )
        if not response_text:
            logger.warning("Gemini returned empty response for %s", file_path)
            return ""

        json_str = _parse_json(response_text)
        if not json_str:
            logger.error(
                "❌ Bad Gemini JSON for %s: %s",
                file_path, response_text[:150]
            )
            return ""

        result = TextExtractionResult.model_validate_json(json_str)
        clean = _normalize(result.extracted_text)

        if file_hash and clean:
            _GEMINI_CACHE[file_hash] = clean
        
        logger.info(
            "✅ Gemini extraction success: %s (%d chars)",
            os.path.basename(file_path), len(clean)
        )
        return clean

    except Exception as e:
        logger.error("❌ Gemini extraction error for %s: %s", file_path, e)
        return ""

    finally:
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH & MONITORING
# ─────────────────────────────────────────────────────────────────────────────

def get_gemini_circuit_breaker_status() -> Dict[str, any]:
    """
    Return Gemini circuit breaker status for monitoring/debugging.
    Called by /health endpoint or admin dashboard.
    
    Returns status for both primary and fallback models.
    """
    return {
        "primary_model": {
            **_circuit_breaker_primary.get_status(GEMINI_MODEL)
        },
        "fallback_model": {
            **_circuit_breaker_fallback.get_status(GEMINI_FALLBACK_MODEL)
        },
        "cache_size": len(_GEMINI_CACHE),
    }