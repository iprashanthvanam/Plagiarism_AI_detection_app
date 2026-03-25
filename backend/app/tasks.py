


"""
tasks.py — Celery background tasks for TKREC Plagiarism Analysis

ARCHITECTURE v4 — PARALLEL PIPELINE
══════════════════════════════════════════════════════════════════════

NEW: process_document_task  ← called by /upload-batch for each file
     ┌─────────────────────────────────────────────────────────────┐
     │  Stage 1  Extract text from file (sequential, mandatory)    │
     │  Stage 2  Store extracted text to DB                        │
     │  Stage 3  PARALLEL via asyncio.gather:                      │
     │           ├─ local_plagiarism_score()  ← async, DB fetch    │
     │           ├─ google_search_with_matches()  ← sync→thread    │
     │           └─ detect_ai_content_detailed()  ← sync→thread    │
     │  Stage 4  Fetch web source texts (for sentence mapping)     │
     │  Stage 5  Compute sentence→source map                       │
     │  Stage 6  Compute final scores                              │
     │  Stage 7  Save AnalysisResult to DB                         │
     └─────────────────────────────────────────────────────────────┘

KEPT:  run_analysis  ← legacy task, used by existing /analyze/{id} route
       Still works for single-file upload via old flow.

KEY CHANGE in _run_analysis_async:
  OLD — sequential:
    local_score  = await local_plagiarism_score(...)        # ~5s
    web_result   = await to_thread(google_search...)        # ~40s
    ai_result    = detect_ai_content_detailed(...)          # ~6s
    Total: ~51s sequential

  NEW — parallel:
    local_score, web_result, ai_result = await asyncio.gather(
        _local_plag_with_fetch(text, document_id),          # ~5s ─┐
        asyncio.to_thread(google_search_with_matches, ...),  # ~40s ├─ run at same time
        asyncio.to_thread(detect_ai_content_detailed, ...),  # ~6s ─┘
    )
    Total: ~40s (bottleneck = Google search, others overlap for free)

PERSISTENT EVENT LOOP:
  Each Celery worker process gets one long-lived event loop.
  asyncio.run() is NOT used — it destroys the loop each call, which
  corrupts asyncpg's pool state. loop.run_until_complete() on the
  same persistent loop lets asyncpg safely reuse its connection pool.
══════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
import threading
from datetime import datetime
from typing import List, Optional, Dict, Tuple

from app.core.celery_client import celery_app
from app.libs.database import db_service
from app.libs.google_search import google_search_with_matches
from app.libs.ai_detection import detect_ai_content_detailed
from app.libs.plagiarism import (
    local_plagiarism_score,
    local_plagiarism_score_with_commoncrawl,
    compute_sentence_source_map,
)
from app.libs.models import AnalysisResult
from app.libs.extract import extract_text

# ── Logger ─────────────────────────────────────────────────────────────────────
logger = logging.getLogger("tasks")

# ── Configuration ──────────────────────────────────────────────────────────────
MIN_TEXT_LENGTH        = 20
SEARCH_TEXT_WORD_LIMIT = 300


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENT EVENT LOOP — one per Celery worker process
# ══════════════════════════════════════════════════════════════════════════════

_worker_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock   = threading.Lock()


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    """Return the worker-process-persistent event loop, created once."""
    global _worker_loop
    if _worker_loop is not None and not _worker_loop.is_closed():
        return _worker_loop
    with _loop_lock:
        if _worker_loop is not None and not _worker_loop.is_closed():
            return _worker_loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _worker_loop = loop
        logger.info("Celery worker: created persistent event loop id=%s", id(loop))
        return loop


# ── Task metrics ───────────────────────────────────────────────────────────────
_metrics = {"active": 0, "completed": 0, "failed": 0}


def analysis_started() -> None:
    _metrics["active"] += 1
    logger.info("Metrics | active=%d completed=%d failed=%d",
                _metrics["active"], _metrics["completed"], _metrics["failed"])


def analysis_completed(duration_s: float = 0.0) -> None:
    _metrics["active"]    = max(0, _metrics["active"] - 1)
    _metrics["completed"] += 1
    logger.info("Metrics | active=%d completed=%d failed=%d | duration=%.1fs",
                _metrics["active"], _metrics["completed"], _metrics["failed"], duration_s)


def analysis_failed() -> None:
    _metrics["active"] = max(0, _metrics["active"] - 1)
    _metrics["failed"] += 1
    logger.warning("Metrics | active=%d completed=%d failed=%d",
                   _metrics["active"], _metrics["completed"], _metrics["failed"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def encode_web_source(url: str, match_pct: Optional[float] = None) -> str:
    if match_pct is not None:
        return f"web::{url}::{round(match_pct, 2)}"
    return f"web::{url}"


def compute_scores(
    verbatim_web_score: float,
    commoncrawl_score:  float,
    local_score:        float,
    ai_score:           float,
) -> Tuple[float, float, float, float]:
    plagiarism  = max(verbatim_web_score, commoncrawl_score * 0.5)
    plagiarism  = round(min(100.0, max(0.0, plagiarism)), 2)
    originality = round(max(0.0, 100.0 - plagiarism), 2)
    ai          = round(min(100.0, max(0.0, ai_score)), 2)
    internal    = round(min(100.0, max(0.0, local_score)), 2)
    return plagiarism, originality, ai, internal


def classify_submission(ai_pct: float, plagiarism_pct: float) -> dict:
    ai_high   = ai_pct >= 70
    ai_med    = 40 <= ai_pct < 70
    plag_high = plagiarism_pct >= 60
    plag_med  = 20 <= plagiarism_pct < 60

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
    if plag_med:
        return {
            "case":        "Case 6 — Moderate Similarity",
            "verdict":     f"Moderate Web Similarity{' + Possible AI Assistance' if ai_med else ''}",
            "description": (
                f"Moderate verbatim overlap with web sources"
                f"{' with possible AI assistance' if ai_med else ''}. "
                "Common in research-heavy work; review matched sources to confirm "
                "adequate citation of borrowed content."
            ),
            "risk":   "medium",
            "action": "Review matched sources. Verify all borrowed content is properly cited.",
        }
    return {
        "case":        "Inconclusive",
        "verdict":     "Manual Review Recommended",
        "description": "Mixed signals detected. Automated classification is inconclusive.",
        "risk":        "medium",
        "action":      "A human reviewer should assess this submission.",
    }


def _fetch_url_text(url: str, timeout: int = 5) -> Optional[str]:
    """Sync helper: fetch plain text from a URL (used via asyncio.to_thread)."""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {"User-Agent": "Mozilla/5.0 (Academic Research Bot)"}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines  = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return " ".join(chunk for chunk in chunks if chunk) or None
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url, e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# PARALLEL ANALYSIS HELPER — fetches other-doc texts AND runs local plagiarism
# ══════════════════════════════════════════════════════════════════════════════

async def _local_plag_with_fetch(
    text: str,
    document_id: int,
) -> Tuple[float, List[str]]:
    """
    Fetch all other documents' texts from DB then run local_plagiarism_score.
    Returns (local_score, other_texts).
    Wrapped in a single coroutine so asyncio.gather can run it in parallel
    with Google search and AI detection.
    """
    others = await db_service.get_all_documents_texts(exclude_id=document_id)
    other_texts: List[str] = [
        (d.get("extracted_text") or d.get("text") or "")
        for d in others
        if (d.get("extracted_text") or d.get("text") or "").strip()
    ]
    try:
        score = await local_plagiarism_score(text, other_texts)
        return float(score), other_texts
    except Exception as e:
        logger.exception("[doc=%d] local_plagiarism failed: %s", document_id, e)
        return 0.0, []


# ══════════════════════════════════════════════════════════════════════════════
# NEW TASK — process_document_task
# Called by /upload-batch for each uploaded file.
# Does EVERYTHING: extract → store → parallel analysis → save results.
# ══════════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, name="process_document")
def process_document_task(self, document_id: int, user_id: str):
    """
    All-in-one Celery task enqueued by /upload-batch.

    Stages:
      1. Extract text from the raw file on disk
      2. Store extracted text to DB
      3. PARALLEL: local plagiarism + web search + AI detection
      4. Sentence-to-source mapping
      5. Compute scores
      6. Persist AnalysisResult

    Multiple instances run simultaneously (one per uploaded file), each in
    its own Celery worker slot, giving true parallel per-file processing.
    """
    logger.info(
        "process_document | task_id=%s doc_id=%d user=%s",
        self.request.id, document_id, user_id,
    )
    analysis_started()

    try:
        loop   = _get_worker_loop()
        result = loop.run_until_complete(
            _process_document_async(document_id, user_id, self)
        )
        analysis_completed(result.get("processing_time", 0.0))
        logger.info(
            "process_document SUCCESS | task_id=%s doc_id=%d scores=%s",
            self.request.id, document_id, result.get("scores", {}),
        )
        return result

    except Exception as e:
        analysis_failed()
        logger.exception(
            "process_document FAILED | task_id=%s doc_id=%d error=%s",
            self.request.id, document_id, str(e),
        )
        self.update_state(
            state="FAILURE",
            meta={"progress": 0, "stage": "Failed", "error": str(e)},
        )
        raise


async def _process_document_async(
    document_id: int,
    user_id: str,
    task_self,
) -> dict:
    """
    Full async pipeline for process_document_task.

    Stage 1 — Extract text  (blocking I/O → OCR/PDF parsing)
    Stage 2 — Store text to DB
    Stage 3 — THREE-WAY PARALLEL:
                 a) local_plagiarism_score  (asyncpg query + ensemble)
                 b) google_search_with_matches  (HTTP → to_thread)
                 c) detect_ai_content_detailed  (CPU  → to_thread)
    Stage 4 — Fetch web source texts for sentence mapping
    Stage 5 — Compute sentence→source map
    Stage 6 — Compute final scores + classification
    Stage 7 — Persist AnalysisResult
    """
    import time as _time
    from datetime import datetime as dt

    start = dt.utcnow()

    # ── Load document metadata ─────────────────────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 5, "stage": "Loading document"},
    )
    doc = await db_service.get_document(document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    if doc["user_id"] != user_id:
        raise PermissionError(f"User {user_id} not authorised for doc {document_id}")

    file_name    = doc.get("file_name", "")
    file_path    = doc.get("file_path", "")
    content_type = doc.get("content_type", "")

    # ── STAGE 1: Extract text ──────────────────────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 10, "stage": "Extracting text"},
    )
    logger.info("[doc=%d] extracting text from %s", document_id, file_name)

    extracted_text = await extract_text(file_path, content_type)

    if not extracted_text or len(extracted_text.strip()) < MIN_TEXT_LENGTH:
        raise ValueError(
            f"Text extraction failed or returned too-short text "
            f"({len(extracted_text) if extracted_text else 0} chars). "
            f"Check file integrity and GEMINI_API_KEY."
        )

    # ── STAGE 2: Store extracted text ─────────────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 18, "stage": "Storing extracted text"},
    )
    success, stored_len = await db_service.store_extracted_text(
        document_id, extracted_text
    )
    if not success:
        logger.error(
            "[doc=%d] TEXT STORAGE VALIDATION FAILED sent=%d stored=%d",
            document_id, len(extracted_text), stored_len,
        )
    else:
        logger.info(
            "[doc=%d] text stored: %d chars", document_id, stored_len,
        )

    text        = extracted_text.strip()
    search_text = " ".join(text.split()[:SEARCH_TEXT_WORD_LIMIT])

    # ── STAGE 3: THREE-WAY PARALLEL ANALYSIS ──────────────────────────────────
    #
    #  a) _local_plag_with_fetch  — DB query + TF-IDF ensemble   (async)
    #  b) google_search_with_matches — HTTP + scrape              (sync→thread)
    #  c) detect_ai_content_detailed — 6-method CPU ensemble      (sync→thread)
    #
    # All three have NO dependency on each other → run simultaneously.
    # Wall-clock time = max(a, b, c) instead of a + b + c.
    # ──────────────────────────────────────────────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={
            "progress": 25,
            "stage": "Running parallel analysis (plagiarism + web search + AI detection)",
        },
    )
    t_parallel = _time.perf_counter()

    (local_score, other_texts), web_search_result, ai_raw = await asyncio.gather(
        _local_plag_with_fetch(text, document_id),                     # a
        asyncio.to_thread(google_search_with_matches, search_text),    # b
        asyncio.to_thread(detect_ai_content_detailed, text),           # c
    )

    logger.info(
        "[doc=%d] parallel analysis complete in %.1fs | "
        "local=%.1f%% web_top=%.1f%% ai=%.1f%%",
        document_id,
        _time.perf_counter() - t_parallel,
        local_score,
        web_search_result.get("top_match_pct", 0.0),
        ai_raw.get("score", 0.0),
    )

    verbatim_web_score = web_search_result.get("top_match_pct", 0.0)
    ai_score           = ai_raw.get("score", 0.0)
    ai_breakdown       = ai_raw.get("breakdown", {})

    # ── STAGE 4: Fetch web source texts (for sentence mapping) ────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 68, "stage": "Fetching web source content"},
    )
    web_source_texts: List[str] = []
    web_source_urls:  List[str] = []

    for url in web_search_result.get("urls", [])[:5]:
        try:
            src_text = await asyncio.to_thread(_fetch_url_text, url)
            if src_text and len(src_text.strip()) > 100:
                web_source_texts.append(src_text)
                web_source_urls.append(url)
        except Exception as e:
            logger.debug("[doc=%d] Could not fetch %s: %s", document_id, url, e)

    logger.info(
        "[doc=%d] fetched %d web source texts",
        document_id, len(web_source_texts),
    )

    # ── STAGE 5: Sentence → Source mapping ────────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 75, "stage": "Mapping sentences to sources"},
    )
    sentence_source_map: Dict[str, int] = {}
    try:
        if web_source_texts:
            sentence_source_map = await compute_sentence_source_map(
                text, web_source_texts, web_source_urls
            )
            logger.info(
                "[doc=%d] sentence map: %d sentences matched",
                document_id, len(sentence_source_map),
            )
    except Exception as e:
        logger.exception("[doc=%d] sentence mapping failed: %s", document_id, e)

    # ── STAGE 6: Compute CommonCrawl score (optional, non-blocking) ───────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 80, "stage": "Computing final scores"},
    )
    commoncrawl_score = 0.0
    try:
        commoncrawl_score = await asyncio.to_thread(
            local_plagiarism_score_with_commoncrawl, text
        )
    except Exception as e:
        logger.warning("[doc=%d] commoncrawl failed (non-fatal): %s", document_id, e)

    plagiarism_score, originality_score, final_ai, internal_score = compute_scores(
        verbatim_web_score=verbatim_web_score,
        commoncrawl_score=commoncrawl_score,
        local_score=local_score,
        ai_score=ai_score,
    )
    interpretation = classify_submission(final_ai, plagiarism_score)

    # ── Build sources list ─────────────────────────────────────────────────────
    sources = []
    for url in web_search_result.get("urls", []):
        match_data = web_search_result.get("matches", {}).get(url, {})
        match_pct  = match_data.get("match_pct", 0.0)
        if match_pct >= 0.1:
            encoded = encode_web_source(url, match_pct)
            if encoded:
                sources.append(encoded)
    if local_score > 0.1:
        sources.append("local_db::internal_database")

    # ── STAGE 7: Persist AnalysisResult ───────────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 90, "stage": "Saving results"},
    )
    end             = dt.utcnow()
    processing_time = (end - start).total_seconds()

    result_obj = AnalysisResult(
        document_id=document_id,
        analyzed_by=user_id,
        ai_detected_percentage=final_ai,
        web_source_percentage=plagiarism_score,
        local_similarity_percentage=internal_score,
        human_written_percentage=originality_score,
        analysis_summary=interpretation["verdict"],
        analysis_date=end,
        matched_web_sources=sources,
        sentence_source_map=sentence_source_map,
        processing_time_seconds=processing_time,
    )
    await db_service.create_analysis_result(result_obj)

    logger.info(
        "[doc=%d] COMPLETE | %s | risk=%s | "
        "ai=%.1f%% plag=%.1f%% orig=%.1f%% internal=%.1f%% | "
        "sources=%d duration=%.2fs text=%d chars",
        document_id,
        interpretation["case"], interpretation["risk"],
        final_ai, plagiarism_score, originality_score, internal_score,
        len(sources), processing_time, len(extracted_text),
    )

    return {
        "document_id": document_id,
        "status": "completed",
        "scores": {
            "ai":          final_ai,
            "plagiarism":  plagiarism_score,
            "originality": originality_score,
            "internal":    internal_score,
        },
        "processing_time": processing_time,
    }


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY TASK — run_analysis
# Used by the existing /analyze/{document_id} route (single-file upload flow).
# Expects extracted_text to already be in the DB (set by /upload).
# Kept for backward compatibility — new code should use process_document_task.
# ══════════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, name="run_analysis")
def run_analysis(self, document_id: int, user_id: str):
    """
    Legacy task wrapper. Kept for backward compat with /analyze/{document_id}.
    Uses persistent event loop (same pattern as process_document_task).
    """
    logger.info(
        "run_analysis | task_id=%s doc_id=%d user=%s",
        self.request.id, document_id, user_id,
    )
    analysis_started()

    try:
        loop   = _get_worker_loop()
        result = loop.run_until_complete(
            _run_analysis_async(document_id, user_id, self)
        )
        analysis_completed(result.get("processing_time", 0.0))
        logger.info(
            "run_analysis SUCCESS | task_id=%s doc_id=%d scores=%s",
            self.request.id, document_id, result.get("scores", {}),
        )
        return result

    except Exception as e:
        analysis_failed()
        logger.exception(
            "run_analysis FAILED | task_id=%s doc_id=%d error=%s",
            self.request.id, document_id, str(e),
        )
        self.update_state(
            state="FAILURE",
            meta={"progress": 0, "stage": "Failed", "error": str(e)},
        )
        raise


async def _run_analysis_async(
    document_id: int,
    user_id: str,
    task_self,
) -> dict:
    """
    Legacy pipeline — assumes extracted_text is already stored in DB.
    Restructured to use asyncio.gather for parallel analysis (same as new task).
    """
    import time as _time
    from datetime import datetime as dt

    logger.info("[doc=%d] run_analysis_async started", document_id)
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 10, "stage": "Loading document"},
    )

    # ── Load document ──────────────────────────────────────────────────────────
    doc = await db_service.get_document(document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found in database")
    if doc["user_id"] != user_id:
        raise PermissionError(f"User {user_id} not authorized for document {document_id}")

    file_name    = doc.get("file_name", "")
    file_path    = doc.get("file_path", "")
    content_type = doc.get("content_type", "")
    start        = dt.utcnow()

    # ── STAGE 1: Extract & store text ─────────────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 15, "stage": "Extracting text"},
    )
    extracted_text = await extract_text(file_path, content_type)

    if not extracted_text or len(extracted_text.strip()) < 50:
        raise ValueError(
            f"Text extraction failed or returned empty/tiny text. "
            f"Extracted {len(extracted_text) if extracted_text else 0} chars."
        )

    success, stored_len = await db_service.store_extracted_text(
        document_id, extracted_text
    )
    if not success:
        logger.error(
            "[doc=%d] TEXT STORAGE VALIDATION FAILED. sent=%d stored=%d",
            document_id, len(extracted_text), stored_len,
        )
    else:
        logger.info("[doc=%d] text stored: %d chars", document_id, stored_len)

    text        = extracted_text.strip()
    search_text = " ".join(text.split()[:SEARCH_TEXT_WORD_LIMIT])

    # ── STAGE 2: THREE-WAY PARALLEL ANALYSIS ──────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={
            "progress": 30,
            "stage": "Running parallel analysis (plagiarism + web search + AI detection)",
        },
    )
    t_parallel = _time.perf_counter()

    (local_score, other_texts), web_search_result, ai_raw = await asyncio.gather(
        _local_plag_with_fetch(text, document_id),
        asyncio.to_thread(google_search_with_matches, search_text),
        asyncio.to_thread(detect_ai_content_detailed, text),
    )

    logger.info(
        "[doc=%d] parallel analysis complete in %.1fs | "
        "local=%.1f%% web_top=%.1f%% ai=%.1f%%",
        document_id,
        _time.perf_counter() - t_parallel,
        local_score,
        web_search_result.get("top_match_pct", 0.0),
        ai_raw.get("score", 0.0),
    )

    verbatim_web_score = web_search_result.get("top_match_pct", 0.0)
    ai_score           = ai_raw.get("score", 0.0)

    # ── STAGE 3: Sentence mapping ─────────────────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 65, "stage": "Mapping sentences to sources"},
    )
    web_source_texts: List[str] = []
    web_source_urls:  List[str] = []

    for url in web_search_result.get("urls", [])[:5]:
        try:
            src_text = await asyncio.to_thread(_fetch_url_text, url)
            if src_text and len(src_text.strip()) > 100:
                web_source_texts.append(src_text)
                web_source_urls.append(url)
        except Exception as e:
            logger.debug("[doc=%d] Could not fetch %s: %s", document_id, url, e)

    sentence_source_map: Dict[str, int] = {}
    try:
        if web_source_texts:
            sentence_source_map = await compute_sentence_source_map(
                text, web_source_texts, web_source_urls
            )
    except Exception as e:
        logger.exception("[doc=%d] sentence mapping failed: %s", document_id, e)

    # ── STAGE 4: CommonCrawl + final scores ───────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 80, "stage": "Computing final scores"},
    )
    commoncrawl_score = 0.0
    try:
        commoncrawl_score = await asyncio.to_thread(
            local_plagiarism_score_with_commoncrawl, text
        )
    except Exception as e:
        logger.warning("[doc=%d] commoncrawl failed: %s", document_id, e)

    plagiarism_score, originality_score, final_ai, internal_score = compute_scores(
        verbatim_web_score=verbatim_web_score,
        commoncrawl_score=commoncrawl_score,
        local_score=local_score,
        ai_score=ai_score,
    )
    interpretation = classify_submission(final_ai, plagiarism_score)

    sources = []
    for url in web_search_result.get("urls", []):
        match_data = web_search_result.get("matches", {}).get(url, {})
        match_pct  = match_data.get("match_pct", 0.0)
        if match_pct >= 0.1:
            encoded = encode_web_source(url, match_pct)
            if encoded:
                sources.append(encoded)
    if local_score > 0.1:
        sources.append("local_db::internal_database")

    # ── STAGE 5: Persist ──────────────────────────────────────────────────────
    task_self.update_state(
        state="PROGRESS",
        meta={"progress": 90, "stage": "Storing results"},
    )
    end             = dt.utcnow()
    processing_time = (end - start).total_seconds()

    result_obj = AnalysisResult(
        document_id=document_id,
        analyzed_by=user_id,
        ai_detected_percentage=final_ai,
        web_source_percentage=plagiarism_score,
        local_similarity_percentage=internal_score,
        human_written_percentage=originality_score,
        analysis_summary=interpretation["verdict"],
        analysis_date=end,
        matched_web_sources=sources,
        sentence_source_map=sentence_source_map,
        processing_time_seconds=processing_time,
    )
    await db_service.create_analysis_result(result_obj)

    logger.info(
        "[doc=%d] run_analysis_async COMPLETE | %s | risk=%s | "
        "ai=%.1f%% plag=%.1f%% orig=%.1f%% internal=%.1f%% | "
        "sources=%d duration=%.2fs text=%d chars",
        document_id,
        interpretation["case"], interpretation["risk"],
        final_ai, plagiarism_score, originality_score, internal_score,
        len(sources), processing_time, len(extracted_text),
    )

    return {
        "document_id": document_id,
        "status": "completed",
        "scores": {
            "ai":          final_ai,
            "plagiarism":  plagiarism_score,
            "originality": originality_score,
            "internal":    internal_score,
        },
        "processing_time": processing_time,
    }