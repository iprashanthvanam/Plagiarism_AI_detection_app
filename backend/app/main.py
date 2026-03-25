





"""
main.py — TKREC Plagiarism Analysis API  v3

═══════════════════════════════════════════════════════════════════════
WHAT CHANGED FROM v2  (Issue 4 integration)
═══════════════════════════════════════════════════════════════════════

1. GOOGLE SEARCH — now uses google_search_with_matches()
   ─ Returns verbatim n-gram match % per URL (not just URL list)
   ─ Scraping is done INSIDE google_search.py (no separate gather loop)
   ─ Per-URL match data embedded into matched_sources for the report

2. PLAGIARISM SCORE — web component uses verbatim match directly
   ─ old: local_plagiarism_score(text, web_texts)  ← ensemble on scraped pages
   ─ new: top_match_pct from google_search_with_matches() ← verbatim exact match
   ─ This matches Turnitin's "similarity index" methodology much more closely
   ─ Internal DB score still uses ensemble (no verbatim source available)

3. SOURCES LIST — richer format
   ─ Each web source now carries: { type, source, match_pct, scraped }
   ─ Stored as JSON-encoded string in matched_web_sources (DB-safe)
   ─ Decoded back to dict in /analysis-status response for the frontend/report

4. AI DETECTION — now uses detect_ai_content_detailed()
   ─ Returns breakdown + is_academic flag for logging
   ─ Public score is still a single float (backward compatible)

5. SCORING FORMULA — updated for verbatim web matching
   ─ plagiarism = max(verbatim_web_score, commoncrawl_score × 0.5)
   ─ verbatim_web_score = top_match_pct from google_search_with_matches()
   ─ originality = 100 − plagiarism  (unchanged)
   ─ ai_score = independent  (unchanged)

═══════════════════════════════════════════════════════════════════════
SCORING ARCHITECTURE — INDUSTRY STANDARD (Turnitin / Copyleaks model)
═══════════════════════════════════════════════════════════════════════

THREE INDEPENDENT METRICS — they do NOT sum to 100%:

  ┌─────────────────┬──────────────────────────────────────────────┐
  │ Metric          │ What it measures                             │
  ├─────────────────┼──────────────────────────────────────────────┤
  │ ai_score        │ Probability text was AI-generated (6-method) │
  │                 │ FULLY INDEPENDENT of plagiarism              │
  ├─────────────────┼──────────────────────────────────────────────┤
  │ plagiarism_score│ % of text verbatim-matching external sources │
  │                 │ = max(verbatim_web, commoncrawl × 0.5)       │
  │                 │ internal_db shown separately (not folded in) │
  ├─────────────────┼──────────────────────────────────────────────┤
  │ originality     │ 100 − plagiarism_score                       │
  │                 │ NOT affected by ai_score (by design)         │
  │                 │ AI text can be original (not copied)         │
  └─────────────────┴──────────────────────────────────────────────┘

FORMULA:
  plagiarism  = max(verbatim_web_score, commoncrawl_score × 0.5)
  originality = 100 − plagiarism
  ai_score    = 6-method ensemble  ← independent
  internal    = local_db_ensemble()  ← separate report field

INTERPRETATION MATRIX — 4 canonical cases:
  AI <20% + Plag >60%  →  Case 1: Human Plagiarism
  AI >70% + Plag <20%  →  Case 2: AI Generated (Original)
  AI >70% + Plag >60%  →  Case 3: AI Generated + Plagiarized
  AI <20% + Plag <20%  →  Case 4: Human Original (Clean)
  AI 40-70%             →  Case 5: Possible AI Assistance
  Plag 20-60%           →  Case 6: Moderate Similarity

═══════════════════════════════════════════════════════════════════════
DATABASE MIGRATION (run once if adding match_pct support)
═══════════════════════════════════════════════════════════════════════

No schema changes required. Per-URL match percentages are stored as
JSON-encoded strings inside the existing matched_web_sources TEXT[] column.

Format stored:  "web::https://example.com::14.3"
                  ^type  ^url                 ^match_pct

Decoded in /analysis-status response to:
  { "type": "web", "source": "https://...", "match_pct": 14.3 }

═══════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, List, Optional
import logging
import magic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("analysis")

sys.path = [p for p in sys.path if "agents/python" not in p]
if "typing_extensions" in sys.modules:
    del sys.modules["typing_extensions"]

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, JSONResponse, Response  # ✅ ADD Response HERE
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

from app.libs.database import db_service, start_retention_scheduler
from app.libs.extract import extract_text
from app.libs.google_search import google_search_with_matches          # NEW: returns URLs + match%
from app.libs.scraper import extract_text_from_url
from app.libs.ai_detection import detect_ai_content, detect_ai_content_detailed  # NEW: detailed version
from app.libs.plagiarism import (
    local_plagiarism_score,
    local_plagiarism_score_with_commoncrawl,
    build_web_source_tokens,
)
from app.libs.models import AnalysisResult
from slowapi.errors import RateLimitExceeded
from app.core.limitter import limiter
from app.core.celery_client import celery_app
from app.tasks import run_analysis, process_document_task
from app.api.student import router as student_router

load_dotenv()

SECRET_KEY                  = os.getenv("SECRET_KEY")
ALGORITHM                   = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
STORAGE_DIR                 = os.getenv("STORAGE_DIR", "/home/site/wwwroot/storage")
MIN_TEXT_LENGTH             = int(os.getenv("MIN_ANALYSIS_TEXT_LENGTH", 20))
SEARCH_TEXT_WORD_LIMIT      = int(os.getenv("SEARCH_TEXT_WORD_LIMIT", 300))

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY missing in .env")

os.makedirs(STORAGE_DIR, exist_ok=True)

app = FastAPI(
    title="Plagiarism Analysis API",
    version="3.0.0",
    description="Upload documents, detect plagiarism & AI content (verbatim matching)",
)
app.state.limiter = limiter

# ─────────────────────────────────────────────────────────────────────────────
# RATE LIMIT CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

RATE_LIMIT_LOGIN   = os.getenv("RATE_LIMIT_LOGIN",   "10/minute")
RATE_LIMIT_UPLOAD  = os.getenv("RATE_LIMIT_UPLOAD",  "20/minute")
RATE_LIMIT_ANALYZE = os.getenv("RATE_LIMIT_ANALYZE", "20/minute")
RATE_LIMIT_STATUS  = os.getenv("RATE_LIMIT_STATUS",  "30/minute")

# ─────────────────────────────────────────────────────────────────────────────
# RATE LIMIT EXCEPTION HANDLER
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={
            "error": "Too many requests",
            "detail": "Rate limit exceeded. Please try again later.",
            "retry_after": 60,
        },
        headers={"Retry-After": "60"},
    )

origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://plagiarism-analysis-app.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    scopes={"admin": "Admin access", "student": "Student access"},
)

@app.on_event("startup")
async def startup():
    await db_service.init_db()
    # Start retention cleanup scheduler
    start_retention_scheduler()
    logger.info("Application startup complete")


# ═══════════════════════════════════════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════════════════════════════════════

def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(request: Request):
    """Extract and validate JWT token from cookies."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id  = payload.get("sub")
        username = payload.get("username")
        role     = payload.get("role")
        if not user_id or not username or not role:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"id": user_id, "username": username, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_role(required_role: str):
    """Dependency to enforce role-based access."""
    def checker(user: Dict[str, Any] = Depends(get_current_user)):
        if user["role"] != required_role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return checker


# ✅ NEW: Validate login credentials
async def validate_login(form_data: OAuth2PasswordRequestForm = Depends()) -> Dict[str, Any]:
    """
    Authenticate user by username and password.
    
    Args:
        form_data: OAuth2 form with username and password
    
    Returns:
        User dict with id, username, role
        
    Raises:
        HTTPException 401 if credentials invalid
    """
    # Get user from database
    user = await db_service.get_user_by_username(form_data.username)
    
    if not user:
        logger.warning("Login failed: user '%s' not found", form_data.username)
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )
    
    # Verify password
    if not pwd_context.verify(form_data.password, user["password_hash"]):
        logger.warning("Login failed: invalid password for user '%s'", form_data.username)
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )
    
    logger.info("Login successful for user '%s' (role: %s)", user["username"], user["role"])
    
    return {
        "id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
    }


# ═══════════════════════════════════════════════════════════════════════
# SOURCE ENCODING / DECODING
# ═══════════════════════════════════════════════════════════════════════
#
# Sources are stored in the DB as a list of encoded strings.
# Three formats:
#   Web source with match %:  "web::https://example.com::14.3"
#   Web source (no match %):  "web::https://example.com"
#   Internal DB match:        "local_db::document:42"
#
# This avoids any schema changes while carrying per-URL match data.

def encode_web_source(url: str, match_pct: Optional[float] = None) -> str:
    """
    Encode a web source URL (with optional match%).
    ✅ NEW: Only encode if match_pct >= 0.1%
    
    Returns DB-safe string format: "web::URL::match_pct"
    """
    # ✅ Filter: Don't encode 0% matches
    if match_pct is not None and match_pct < 0.1:
        logger.debug("Skipping 0%% match URL: %s", url[:60])
        return None  # Return None to signal skip in caller
    
    if match_pct is not None:
        return f"web::{url}::{round(match_pct, 2)}"
    return f"web::{url}"


def decode_source(s: str) -> Optional[Dict[str, Any]]:
    """
    Decode a stored source string into a dict for the API response.

    Returns:
      { "type": "web",      "source": "https://...", "match_pct": 14.3 }
      { "type": "local_db", "source": "document:42"                    }
      None if the format is unrecognised.
    """
    if not isinstance(s, str) or "::" not in s:
        return None

    parts = s.split("::")

    if parts[0] == "web":
        if len(parts) >= 3:
            # Has match percentage
            try:
                return {
                    "type":      "web",
                    "source":    parts[1],
                    "match_pct": float(parts[2]),
                }
            except (ValueError, IndexError):
                pass
        # No match percentage (legacy or failed scrape)
        return {"type": "web", "source": parts[1], "match_pct": None}

    if parts[0] == "local_db":
        return {"type": "local_db", "source": parts[1]}

    # Generic fallback (any other :: format)
    return {"type": parts[0], "source": "::".join(parts[1:])}


# ═══════════════════════════════════════════════════════════════════════
# SCORE ENGINE
# ═══════════════════════════════════════════════════════════════════════

def compute_scores(
    verbatim_web_score: float,
    commoncrawl_score:  float,
    local_score:        float,
    ai_score:           float,
) -> Tuple[float, float, float, float]:
    """
    Compute the four final report metrics from raw analysis signals.

    Returns: (plagiarism, originality, ai, internal_similarity)

    CHANGES FROM v2:
    - google_score (ensemble similarity) replaced by verbatim_web_score
      (direct % of document that verbatim-matches a web source).
    - verbatim_web_score is already Turnitin-comparable — no further
      calibration needed in this function.

    Each metric is independent and rounded to 2dp.
    Do NOT add them — they are not meant to sum to any fixed total.
    """
    # External web plagiarism — verbatim match is the primary signal
    plagiarism = max(verbatim_web_score, commoncrawl_score * 0.5)
    plagiarism = round(min(100.0, max(0.0, plagiarism)), 2)

    # Originality = inverse of plagiarism (not inverse of ai+plagiarism)
    originality = round(max(0.0, 100.0 - plagiarism), 2)

    # AI: clamped, independent of plagiarism
    ai = round(min(100.0, max(0.0, ai_score)), 2)

    # Internal DB similarity: separate concern, reported separately
    internal = round(min(100.0, max(0.0, local_score)), 2)

    return plagiarism, originality, ai, internal


# ═══════════════════════════════════════════════════════════════════════
# INTERPRETATION MATRIX
# ═══════════════════════════════════════════════════════════════════════

def classify_submission(ai_pct: float, plagiarism_pct: float) -> Dict[str, str]:
    """
    Map (AI%, Plagiarism%) to one of 4 canonical cases + 2 edge cases.

    Thresholds (Turnitin-aligned):
      AI HIGH  ≥ 70%   (near-certain AI at RoBERTa threshold)
      AI MED   40–69%  (possible AI assistance / formal writing style)
      PLAG HIGH ≥ 60%  (Turnitin flags ≥50% as high similarity)
      PLAG MED  20–59% (Turnitin flags ≥25% for review)
    """
    ai_high   = ai_pct >= 70
    ai_med    = 40 <= ai_pct < 70
    plag_high = plagiarism_pct >= 60
    plag_med  = 20 <= plagiarism_pct < 60

    # ── Case 3: AI Generated AND Plagiarized ───────────────────────────
    if ai_high and plag_high:
        return {
            "case":        "Case 3 — AI Generated & Plagiarized",
            "verdict":     "AI-Generated AND Plagiarized",
            "description": (
                "Strong AI authorship signals combined with high verbatim web similarity. "
                "High probability this was generated by an AI tool using source "
                "material it was trained on or directly accessed."
            ),
            "risk":   "critical",
            "action": "Reject. Request original human-authored work with proper citations.",
        }

    # ── Case 1: Human Plagiarism ───────────────────────────────────────
    if not ai_high and plag_high:
        return {
            "case":        "Case 1 — Human Plagiarism",
            "verdict":     "Human Plagiarism Detected",
            "description": (
                "Low AI probability with high verbatim web similarity. "
                "Content appears manually copied or paraphrased from existing "
                "sources without proper attribution."
            ),
            "risk":   "high",
            "action": "Reject. Request original work with citations for all borrowed content.",
        }

    # ── Case 2: AI Generated, Original ────────────────────────────────
    if ai_high and not plag_high and not plag_med:
        return {
            "case":        "Case 2 — AI Generated (Original)",
            "verdict":     "AI-Generated Content — Not Copied",
            "description": (
                "High AI authorship probability. Content does not match known web "
                "sources — this appears to be original AI output, not copied from "
                "existing material."
            ),
            "risk":   "high",
            "action": "Review per institution AI policy. Original content but likely not student's own work.",
        }

    # ── Case 4: Human Original (Clean) ────────────────────────────────
    if not ai_high and not ai_med and not plag_high and not plag_med:
        return {
            "case":        "Case 4 — Human Original",
            "verdict":     "Likely Original Human Work",
            "description": (
                "Low AI probability and low verbatim web similarity. "
                "Content appears to be original human-authored work with no "
                "significant plagiarism concerns."
            ),
            "risk":   "low",
            "action": "Accept. No significant concerns detected.",
        }

    # ── Case 5: Possible AI Assistance ────────────────────────────────
    if ai_med and not plag_high:
        return {
            "case":        "Case 5 — Possible AI Assistance",
            "verdict":     "Possible AI Assistance Detected",
            "description": (
                "Moderate AI signals detected. Content may have been drafted or "
                "edited with AI assistance. Verbatim web plagiarism is not significant."
            ),
            "risk":   "medium",
            "action": (
                "Request student to confirm authorship. "
                "May be acceptable if institution permits AI assistance with disclosure."
            ),
        }

    # ── Case 6: Moderate Web Similarity ───────────────────────────────
    if plag_med:
        ai_note = " with possible AI assistance" if ai_med else ""
        return {
            "case":        "Case 6 — Moderate Similarity",
            "verdict":     f"Moderate Web Similarity{' + Possible AI Assistance' if ai_med else ''}",
            "description": (
                f"Moderate verbatim overlap with web sources{ai_note}. "
                "Common in research-heavy work; review matched sources to confirm "
                "adequate citation of borrowed content."
            ),
            "risk":   "medium",
            "action": "Review matched sources. Verify all borrowed content is properly cited.",
        }

    # ── Fallback ───────────────────────────────────────────────────────
    return {
        "case":        "Inconclusive",
        "verdict":     "Manual Review Recommended",
        "description": "Mixed signals detected. Automated classification is inconclusive.",
        "risk":        "medium",
        "action":      "A human reviewer should assess this submission.",
    }


# ═══════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    return {"status": "Plagiarism Analysis API v3 running"}


@app.post("/auth/login")
@limiter.limit(RATE_LIMIT_LOGIN)
async def login(request: Request, user=Depends(validate_login)):
    """
    ✅ FIXED: Set JWT token as HttpOnly cookie (not JSON).
    
    Browser automatically sends cookie on all subsequent requests.
    get_current_user() reads it from request.cookies.
    """
    
    # Create JWT payload
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
    }
    
    access_token = create_access_token(payload)
    
    # ✅ CRITICAL: Create response object to set cookie
    response = JSONResponse(
        status_code=200,
        content={
            "success": True,
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
        }
    )
    
    # ✅ SET COOKIE (HttpOnly = not accessible via JavaScript)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 30 minutes
        httponly=True,  # Prevents JavaScript theft (XSS protection)
        secure=False,   # Set to True in production (HTTPS only)
        samesite="lax",  # CSRF protection
    )
    
    logger.info(
        "Login successful | user=%s role=%s | token set in cookie",
        user["username"], user["role"]
    )
    
    return response


@app.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"success": True}


@app.get("/auth/validate-token")
async def validate_token(user=Depends(get_current_user)):
    return user


@app.get("/admin/dashboard")
async def admin_dashboard(user=Depends(require_role("admin"))):
    return await db_service.get_all_documents()


MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB

ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "text/plain",
    "image/png",
    "image/jpeg",
}

@app.post("/upload")
@limiter.limit("20/minute")
async def upload_file(request: Request, file: UploadFile = File(...), user=Depends(get_current_user)):
    """Upload — 20 requests per minute per IP"""
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE//1024//1024}MB)")
    
    # Server-side MIME check
    mime = magic.from_buffer(content, mime=True)
    if mime not in ALLOWED_MIMES:
        raise HTTPException(400, f"File type not allowed: {mime}")
    
    ext       = os.path.splitext(file.filename)[1].lower()
    uid       = str(uuid.uuid4())
    file_path = os.path.join(STORAGE_DIR, f"{uid}{ext}")

    with open(file_path, "wb") as f:
        f.write(content)

    extracted_text = ""
    try:
        extracted_text = await extract_text(file_path, file.content_type)
    except Exception as e:
        logger.exception("Text extraction failed for %s: %s", file.filename, e)

    doc = await db_service.create_document(
        user_id=user["id"],
        file_name=file.filename,
        content_type=file.content_type,
        size=len(content),
        file_path=file_path,
    )

    if extracted_text and len(extracted_text.strip()) >= MIN_TEXT_LENGTH:
        await db_service.store_extracted_text(doc["id"], extracted_text)
        logger.info("Stored %d chars for document %d", len(extracted_text), doc["id"])
    else:
        logger.warning(
            "Document %d (%s): no meaningful text extracted (len=%d)",
            doc["id"], file.filename, len(extracted_text)
        )

    return {"success": True, "document_id": doc["id"]}


# ═══════════════════════════════════════════════════════════════════════
# BATCH UPLOAD — accept N files, save to disk, enqueue one Celery task
# per file, return all document_ids immediately (no blocking extraction).
#
# Flow:
#   POST /upload-batch  (FormData with multiple "files" fields)
#     → for each file:
#         ① validate MIME + size
#         ② save raw bytes to disk
#         ③ create_document() in DB  (metadata only — no text yet)
#         ④ process_document_task.delay(doc_id, user_id)  → Redis queue
#     → return { document_ids: [25, 26, 27] }  ← INSTANT
#
# Redis queue now has:
#   [process_document(25), process_document(26), process_document(27)]
#
# Celery workers pick them up simultaneously.  Each worker:
#   ① extract_text()
#   ② store_extracted_text()
#   ③ PARALLEL: local_plagiarism + web_search + AI detection
#   ④ save AnalysisResult
#
# Frontend polls /analysis-status/{doc_id} for each returned id.
# ═══════════════════════════════════════════════════════════════════════

@app.post("/upload-batch")
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    user=Depends(get_current_user),
):
    """
    Batch file upload.  Accepts 1-N files in a single multipart request.
    Saves files to disk, creates DB records, enqueues a Celery
    process_document_task for every file, and returns all document_ids
    immediately — no blocking extraction inside the HTTP request.
    """
    if not files:
        raise HTTPException(400, "No files provided")

    document_ids: List[int] = []

    for file in files:
        content = await file.read()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                413,
                f"File '{file.filename}' exceeds limit "
                f"({MAX_FILE_SIZE // 1024 // 1024}MB).",
            )

        mime = magic.from_buffer(content, mime=True)
        if mime not in ALLOWED_MIMES:
            raise HTTPException(
                400,
                f"File '{file.filename}' has disallowed type: {mime}",
            )

        ext       = os.path.splitext(file.filename)[1].lower()
        uid       = str(uuid.uuid4())
        file_path = os.path.join(STORAGE_DIR, f"{uid}{ext}")

        with open(file_path, "wb") as f:
            f.write(content)

        doc = await db_service.create_document(
            user_id=user["id"],
            file_name=file.filename,
            content_type=file.content_type,
            size=len(content),
            file_path=file_path,
        )
        doc_id = doc["id"]

        task = process_document_task.delay(doc_id, user["id"])

        try:
            await db_service.store_task_id(doc_id, task.id)
        except Exception:
            pass

        document_ids.append(doc_id)

        logger.info(
            "upload-batch: queued doc_id=%d task_id=%s file=%s user=%s",
            doc_id, task.id, file.filename, user["id"],
        )

    return {
        "success":      True,
        "document_ids": document_ids,
        "queued":       len(document_ids),
        "message":      (
            f"{len(document_ids)} file(s) queued for processing. "
            "Poll /analysis-status/{document_id} for each id."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════
# CORE ANALYSIS ENDPOINT — NOW ASYNC (returns task_id immediately)
# ═══════════════════════════════════════════════════════════════════════

@app.post("/analyze/{document_id}")
@limiter.limit(RATE_LIMIT_ANALYZE)
async def analyze(request: Request, document_id: int, user=Depends(get_current_user)):
    """
    CHANGED: Now returns immediately with a task_id.
    Analysis runs in the background via Celery.
    
    Old flow (synchronous, blocking):
      POST /analyze/123 → blocks 30-120s → returns complete result
    
    New flow (asynchronous, non-blocking):
      POST /analyze/123 → returns {task_id: "abc123"} immediately
      GET /task-status/abc123 → polls Celery result backend
      Frontend polls until status = "SUCCESS"
    """
    doc = await db_service.get_document(document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Unauthorized")

    text = doc.get("extracted_text", "") or ""
    if len(text.strip()) < MIN_TEXT_LENGTH:
        logger.warning("Document %d has insufficient text (%d chars)", document_id, len(text))
        raise HTTPException(400, detail=(
            "Insufficient text extracted from document. "
            "If this is a scanned PDF, image, or .doc file, "
            "ensure GEMINI_API_KEY is valid and not revoked."
        ))

    # ── Enqueue background task ──────────────────────────────────────────
    # This returns immediately and runs in a separate Celery worker process
    task = run_analysis.delay(document_id, user["id"])

    # ── Store task_id on the document so /analysis-status can find it ────
    try:
        await db_service.store_task_id(document_id, task.id)
    except Exception:
        pass  # Non-critical — /task-status/{task_id} still works

    logger.info(
        "Analysis task queued for document %d | task_id=%s | user=%s",
        document_id,
        task.id,
        user["id"],
    )

    return {
        "success": True,
        "status": "queued",
        "task_id": task.id,
        "document_id": document_id,
        "message": "Analysis queued. Poll /task-status/{task_id} for progress.",
    }


# ═══════════════════════════════════════════════════════════════════════
# TASK STATUS POLLING — replaces /analysis-status/{document_id}
# ═══════════════════════════════════════════════════════════════════════

@app.get("/task-status/{task_id}")
@limiter.limit(RATE_LIMIT_STATUS)
async def task_status(request: Request, task_id: str, user=Depends(get_current_user)):
    """Poll Celery task status and return result when complete."""
    task = celery_app.AsyncResult(task_id)
    
    if task.state == "PENDING":
        return {"success": False, "status": "pending", "progress": 0}
    
    if task.state == "PROGRESS":
        return {"success": False, "status": "analyzing", "progress": task.info.get("progress", 0)}
    
    if task.state == "FAILURE":
        return {"success": False, "status": "failed", "error": str(task.info)}
    
    if task.state == "SUCCESS":
        result_dict = task.result
        document_id = result_dict.get("document_id")
        
        # Fetch full result from DB
        doc = await db_service.get_document(document_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc["user_id"] != user["id"] and user["role"] != "admin":
            raise HTTPException(403, "Unauthorized")
        
        db_result = await db_service.get_analysis_result_for_document(document_id)
        if not db_result:
            raise HTTPException(404, "Analysis result not found")
        
        # ── Decode matched sources ───────────────────────────────────
        raw_sources = db_result.get("matched_web_sources", []) or []
        decoded_sources = []
        for s in raw_sources:
            decoded = decode_source(s)
            if decoded:
                decoded_sources.append(decoded)
        
        # ── Parse sentence source map from JSONB ────────────────────
        sentence_source_map = {}
        raw_map = db_result.get("sentence_source_map")
        if raw_map:
            if isinstance(raw_map, str):
                import json
                sentence_source_map = json.loads(raw_map)
            elif isinstance(raw_map, dict):
                sentence_source_map = raw_map
        
        # ── Pull scores ──────────────────────────────────────────────
        extracted_text = doc.get("extracted_text", "") or ""
        ai_pct = float(db_result["ai_detected_percentage"])
        plag_pct = float(db_result["web_source_percentage"])
        orig_pct = float(db_result["human_written_percentage"])
        interpretation = classify_submission(ai_pct, plag_pct)
        
        return {
            "success": True,
            "status": "completed",
            "progress": 100,
            "result": {
                "document_id": document_id,
                "ai_detected_percentage": ai_pct,
                "web_source_percentage": plag_pct,
                "human_written_percentage": orig_pct,
                "local_similarity_percentage": float(db_result.get("local_similarity_percentage", 0)),
                "interpretation": {
                    "case": interpretation["case"],
                    "verdict": interpretation["verdict"],
                    "description": interpretation["description"],
                    "risk": interpretation["risk"],
                    "action": interpretation["action"],
                },
                "analysis_summary": db_result["analysis_summary"],
                "analysis_date": db_result["analysis_date"].isoformat() if db_result["analysis_date"] else None,
                "matched_sources": decoded_sources,
                "processing_time_seconds": db_result.get("processing_time_seconds", 0),
                "extracted_text": extracted_text,
                "sentence_source_map": sentence_source_map,  # ✅ NEW
            },
        }
    
    return {"success": False, "status": "unknown"}


@app.get("/analysis-status/{document_id}")
@limiter.limit(RATE_LIMIT_STATUS)
async def analysis_status(request: Request, document_id: int, user=Depends(get_current_user)):
    """
    Poll analysis status by document_id.
    Checks Celery task state first (via stored task_id on the document row),
    then falls back to DB result when the task is complete.
    This is the primary polling route used by the frontend.
    """
    doc = await db_service.get_document(document_id)
    if not doc:
        raise HTTPException(404)
    if doc["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(403)

    # ── Check Celery task state via task_id stored on the document ───────
    stored_task_id = doc.get("task_id")
    if stored_task_id:
        task = celery_app.AsyncResult(stored_task_id)

        if task.state == "PENDING":
            return {"success": False, "status": "pending", "progress": 0}

        if task.state == "PROGRESS":
            return {
                "success": False,
                "status": "analyzing",
                "progress": task.info.get("progress", 0),
                "stage": task.info.get("stage", ""),
            }

        if task.state == "FAILURE":
            return {
                "success": False,
                "status": "failed",
                "error": str(task.info),
            }

    # ── Task SUCCESS or no task_id stored — read result from DB ─────────
    result = await db_service.get_analysis_result_for_document(document_id)
    if not result:
        # Still running (task_id not stored yet) — report pending
        return {"success": False, "status": "pending", "progress": 0}

    # ── Decode matched sources ───────────────────────────────────────────
    raw_sources = result.get("matched_web_sources", []) or []
    decoded_sources = []
    for s in raw_sources:
        decoded = decode_source(s)
        if decoded:
            decoded_sources.append(decoded)

    # ── Parse sentence source map ────────────────────────────────────────
    sentence_source_map = {}
    raw_map = result.get("sentence_source_map")
    if raw_map:
        if isinstance(raw_map, str):
            import json
            sentence_source_map = json.loads(raw_map)
        elif isinstance(raw_map, dict):
            sentence_source_map = raw_map

    # ── Pull scores ──────────────────────────────────────────────────────
    extracted_text = doc.get("extracted_text", "") or ""
    ai_pct   = float(result["ai_detected_percentage"])
    plag_pct = float(result["web_source_percentage"])
    orig_pct = float(result["human_written_percentage"])
    interpretation = classify_submission(ai_pct, plag_pct)

    return {
        "success": True,
        "status": "completed",
        "progress": 100,
        "result": {
            "document_id":              result["document_id"],
            "ai_detected_percentage":   ai_pct,
            "web_source_percentage":    plag_pct,
            "human_written_percentage": orig_pct,
            "local_similarity_percentage": float(result.get("local_similarity_percentage", 0)),
            "interpretation": {
                "case":        interpretation["case"],
                "verdict":     interpretation["verdict"],
                "description": interpretation["description"],
                "risk":        interpretation["risk"],
                "action":      interpretation["action"],
            },
            "analysis_summary":        result["analysis_summary"],
            "analysis_date":           result["analysis_date"].isoformat() if result["analysis_date"] else None,
            "matched_sources":         decoded_sources,
            "processing_time_seconds": result.get("processing_time_seconds", 0),
            "extracted_text":          extracted_text,
            "sentence_source_map":     sentence_source_map,
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# FILE SERVING
# ═══════════════════════════════════════════════════════════════════════

@app.get("/files/original/{document_id}")
async def view_file(document_id: int, user=Depends(get_current_user)):
    doc = await db_service.get_document(document_id)
    if not doc:
        raise HTTPException(404)
    if doc["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(403)
    return FileResponse(
        path=doc["file_path"],
        filename=doc["file_name"],
        media_type=doc["content_type"],
    )


# ═══════════════════════════════════════════════════════════════════════
# SERVE REACT FRONTEND
# ═══════════════════════════════════════════════════════════════════════

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(BASE_DIR, "build")

if os.path.isdir(os.path.join(BUILD_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(BUILD_DIR, "assets")), name="assets")

@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    file_path = os.path.join(BUILD_DIR, full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    index_path = os.path.join(BUILD_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend build not found."}

# Register routes
app.include_router(student_router)