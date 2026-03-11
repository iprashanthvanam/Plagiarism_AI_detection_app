import os
import re
import time
import mimetypes
import asyncio
import hashlib
import logging
import unicodedata
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

#.env GOOGLE_API_KEY  # noqa: F401
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY        = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL          = os.getenv("GEMINI_MODEL",          "gemini-2.0-flash")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash-lite")
GEMINI_MAX_RETRIES    = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
GEMINI_RETRY_DELAY    = int(os.getenv("GEMINI_RETRY_DELAY", "60"))

logger = logging.getLogger(__name__)


class TextExtractionResult(BaseModel):
    extracted_text: str


_GEMINI_CACHE: dict[str, str] = {}

# -------------------------------------------------------
# Init client — temporarily remove GOOGLE_API_KEY so the
# Google AI SDK doesn't override our explicit api_key arg.
# -------------------------------------------------------
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
            
            "Gemini client ready (primary=%s, fallback=%s)",
            GEMINI_MODEL, GEMINI_FALLBACK_MODEL
        )
    except Exception as e:
        logger.error("Gemini client init failed: %s", e)

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


# -------------------------------------------------------
# Helpers
# -------------------------------------------------------
def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize(text: str) -> str:
    try:
        return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    except Exception:
        return text


def _parse_retry_delay(err: str) -> int:
    m = re.search(r"retry in (\d+)", err)
    return int(m.group(1)) + 5 if m else GEMINI_RETRY_DELAY


def _parse_json(response_text: str) -> Optional[str]:
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


def _call_gemini_sync(uploaded_file, model: str) -> Optional[str]:
    """Synchronous Gemini call with per-minute retry and model fallback."""
    models = [model]
    if model != GEMINI_FALLBACK_MODEL:
        models.append(GEMINI_FALLBACK_MODEL)

    prompt = (
        "Extract ALL readable text from the provided file accurately. "
        "Preserve reading order. Include all text, numbers, tables, symbols. "
        'Return ONLY valid JSON: { "extracted_text": "..." }'
    )

    for current_model in models:
        for attempt in range(1, GEMINI_MAX_RETRIES + 1):
            try:
                logger.info("Gemini: model=%s attempt=%d/%d", current_model, attempt, GEMINI_MAX_RETRIES)
                resp = client.models.generate_content(
                    model=current_model,
                    contents=[prompt, uploaded_file],
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": TextExtractionResult,
                    },
                )
                logger.info("Gemini success (model=%s)", current_model)
                return resp.text

            except Exception as e:
                err = str(e)
                if "404" in err or "NOT_FOUND" in err:
                    logger.error("Model %s not found — trying next", current_model)
                    break
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    wait = _parse_retry_delay(err)
                    if attempt < GEMINI_MAX_RETRIES:
                        logger.warning("Gemini 429 on %s (attempt %d/%d) — waiting %ds",
                                       current_model, attempt, GEMINI_MAX_RETRIES, wait)
                        time.sleep(wait)
                        continue
                    logger.warning("Quota exhausted on %s after %d attempts — trying next model",
                                   current_model, GEMINI_MAX_RETRIES)
                    break
                # auth error, network, invalid file — don't retry
                logger.error("Gemini non-retryable error (model=%s): %s", current_model, err[:200])
                return None

    logger.error("All Gemini models exhausted: %s", models)
    return None


# -------------------------------------------------------
# Public API
# -------------------------------------------------------
async def extract_text_with_gemini(file_path: str, is_pdf: bool = False) -> str:
    """
    Gemini OCR fallback. Called only when local extraction fails.
    Always returns str ("" on any failure).
    `is_pdf` is kept for backward compatibility but ignored —
    PDFs are uploaded directly as application/pdf.
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

    # Cache
    file_hash = None
    try:
        file_hash = _hash_file(file_path)
        if file_hash in _GEMINI_CACHE:
            logger.info("Gemini cache hit: %s", file_path)
            return _GEMINI_CACHE[file_hash]
    except Exception:
        pass

    uploaded_file = None
    try:
        logger.info("Gemini fallback upload: %s (mime=%s)", os.path.basename(file_path), mime_type)
        uploaded_file = client.files.upload(file=file_path)

        response_text = await asyncio.to_thread(_call_gemini_sync, uploaded_file, GEMINI_MODEL)
        if not response_text:
            return ""

        json_str = _parse_json(response_text)
        if not json_str:
            logger.error("Bad Gemini JSON for %s: %s", file_path, response_text[:150])
            return ""

        result = TextExtractionResult.model_validate_json(json_str)
        clean = _normalize(result.extracted_text)

        if file_hash and clean:
            _GEMINI_CACHE[file_hash] = clean

        logger.info("Gemini fallback success: %s (%d chars)", os.path.basename(file_path), len(clean))
        return clean

    except Exception as e:
        logger.error("Gemini fallback error for %s: %s", file_path, e)
        return ""

    finally:
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass