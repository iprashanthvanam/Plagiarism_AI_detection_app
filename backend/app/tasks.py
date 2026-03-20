"""
Background analysis tasks — run asynchronously in Celery workers.

BUG FIXED IN THIS VERSION
──────────────────────────────────────────────────────────────────────
TypeError: '>' not supported between instances of 'coroutine' and 'float'

ROOT CAUSE:
  local_plagiarism_score() is declared as `async def` in plagiarism.py.

  The code was calling it like this:
      local_score = await asyncio.to_thread(local_plagiarism_score, text, other_texts)

  asyncio.to_thread(fn, *args) runs fn(*args) in a thread pool executor.
  When fn is an `async def`, calling fn(*args) in the thread returns a
  COROUTINE OBJECT — it does not execute the function, it does not await it.
  The coroutine is never run. local_score = <coroutine object at 0x...>.

  Later, compute_scores() tries: max(0.0, local_score)
  Python cannot compare a coroutine with a float → TypeError crash.

  The logger line before that also crashed:
      logger.info("...%.1f%%...", local_score, ...)
  → TypeError: must be real number, not coroutine

FIX:
  Since local_plagiarism_score IS async def, call it with await directly:
      local_score = await local_plagiarism_score(text, other_texts)

  asyncio.to_thread() is only for SYNC (non-async) functions.
  For async def functions: use await directly.

ALSO FIXED:
  asyncio.run() replaced with persistent event loop (loop.run_until_complete).
  asyncio.run() creates + destroys the event loop each task call, which
  corrupts asyncpg's internal pool state. A persistent loop prevents this.
──────────────────────────────────────────────────────────────────────
"""

import asyncio
import logging
import threading
from datetime import datetime
from typing import List, Optional, Dict

from app.core.celery_client import celery_app
from app.libs.database import db_service
from app.libs.google_search import google_search_with_matches
from app.libs.ai_detection import detect_ai_content_detailed
from app.libs.plagiarism import (
    local_plagiarism_score,
    local_plagiarism_score_with_commoncrawl,
    compute_sentence_source_map,  # ✅ ADD THIS IMPORT
)
from app.libs.models import AnalysisResult
from app.libs.extract import extract_text  # ✅ CORRECT MODULE NAME

# ── Logger ─────────────────────────────────────────────────────────────────────
logger = logging.getLogger("tasks")

# ── Configuration ──────────────────────────────────────────────────────────────
MIN_TEXT_LENGTH        = 20
SEARCH_TEXT_WORD_LIMIT = 300


# ── PERSISTENT EVENT LOOP — one per Celery worker process ─────────────────────
# Replaces asyncio.run() which creates + destroys a loop per task call.
# asyncpg pools are bound to the loop they were created on. If asyncio.run()
# destroys the loop, the pool becomes invalid and the next task hangs.
# A persistent loop lets asyncpg reuse the same healthy pool for all tasks.

_worker_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()


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
):
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


# ── Core async pipeline ────────────────────────────────────────────────────────

async def _run_analysis_async(document_id: int, user_id: str, task_self) -> dict:
    """
    Full analysis pipeline. Runs on the persistent worker event loop.
    """
    import time as _time
    from datetime import datetime as dt

    logger.info("[doc=%d] analysis_task_started", document_id)
    task_self.update_state(state="PROGRESS", meta={"progress": 10, "stage": "Loading document"})

    # ── Load document ──────────────────────────────────────────────────────────
    doc = await db_service.get_document(document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found in database")

    if doc["user_id"] != user_id:
        raise PermissionError(f"User {user_id} not authorized for document {document_id}")

    file_name = doc.get("file_name", "")
    file_path = doc.get("file_path", "")
    content_type = doc.get("content_type", "")

    start = dt.utcnow()

    # ── STAGE 1: Extract text from file ────────────────────────────────────────
    logger.info("[doc=%d] Extracting text from %s", document_id, file_name)
    extracted_text = await extract_text(file_path, content_type)
    
    if not extracted_text or len(extracted_text.strip()) < 50:
        raise ValueError(
            f"Text extraction failed or returned empty/tiny text. "
            f"Extracted {len(extracted_text) if extracted_text else 0} chars."
        )
    
    # ✅ Store extracted text
    logger.info("[doc=%d] Storing extracted text (%d chars) to database",
                document_id, len(extracted_text))
    
    success, stored_length = await db_service.store_extracted_text(
        document_id, extracted_text
    )
    
    if not success:
        logger.error(
            "[doc=%d] ❌ TEXT STORAGE VALIDATION FAILED. "
            "Sent %d chars, only %d stored.",
            document_id, len(extracted_text), stored_length
        )
    else:
        logger.info(
            "[doc=%d] ✅ Text storage validated: %d chars stored ✓",
            document_id, stored_length
        )
    
    text = extracted_text.strip()

    # ── STAGE 2: Internal DB Similarity (20%) ─────────────────────────────────
    task_self.update_state(state="PROGRESS", meta={"progress": 20, "stage": "Checking internal database"})
    t1 = _time.perf_counter()

    others = await db_service.get_all_documents_texts(exclude_id=document_id)
    other_texts: List[str] = [
        (d.get("extracted_text") or d.get("text") or "")
        for d in others
        if (d.get("extracted_text") or d.get("text") or "").strip()
    ]

    local_score = 0.0
    try:
        local_score = await local_plagiarism_score(text, other_texts)
        logger.info(
            "[doc=%d] internal_db=%.1f%% docs=%d ms=%.0f",
            document_id, local_score, len(other_texts),
            (_time.perf_counter() - t1) * 1000,
        )
    except Exception as e:
        logger.exception("[doc=%d] internal_db_failed: %s", document_id, e)
        local_score = 0.0

    # ── STAGE 3: Web Search + Verbatim Matching (40%) ───────────────────────────
    task_self.update_state(state="PROGRESS", meta={"progress": 40, "stage": "Searching web sources"})
    t2 = _time.perf_counter()

    verbatim_web_score = 0.0
    web_search_result = {"urls": [], "matches": {}, "top_match_pct": 0.0, "queries_used": []}
    search_text = " ".join(text.split()[:SEARCH_TEXT_WORD_LIMIT])

    try:
        web_search_result = await asyncio.to_thread(google_search_with_matches, search_text)
        verbatim_web_score = web_search_result.get("top_match_pct", 0.0)
        logger.info(
            "[doc=%d] web_search urls=%d top_match=%.1f%% ms=%.0f",
            document_id,
            len(web_search_result.get("urls", [])),
            verbatim_web_score,
            (_time.perf_counter() - t2) * 1000,
        )
    except Exception as e:
        logger.exception("[doc=%d] web_search_failed: %s", document_id, e)
        verbatim_web_score = 0.0

    # ── STAGE 3b: Extract source texts for sentence mapping ──────────────────
    task_self.update_state(state="PROGRESS", meta={"progress": 35, "stage": "Extracting source content"})
    
    web_source_texts: List[str] = []
    web_source_urls: List[str] = []
    
    try:
        for url in web_search_result.get("urls", [])[:5]:
            try:
                source_text = await asyncio.to_thread(_fetch_url_text, url)
                if source_text and len(source_text.strip()) > 100:
                    web_source_texts.append(source_text)
                    web_source_urls.append(url)
            except Exception as e:
                logger.debug("Could not fetch text from %s: %s", url, e)
                continue
        
        logger.info(
            "[doc=%d] Extracted text from %d web sources",
            document_id, len(web_source_texts)
        )
    except Exception as e:
        logger.warning("[doc=%d] Web source extraction failed: %s", document_id, e)

    # ── STAGE 3c: Sentence to Source Mapping ────────────────────────────────
    task_self.update_state(state="PROGRESS", meta={"progress": 38, "stage": "Mapping sentences to sources"})
    
    sentence_source_map: Dict[str, int] = {}
    try:
        if web_source_texts:
            sentence_source_map = await compute_sentence_source_map(
                text,
                web_source_texts,
                web_source_urls
            )
            logger.info(
                "[doc=%d] ✅ Sentence map computed: %d sentences matched",
                document_id, len(sentence_source_map)
            )
        else:
            logger.warning("[doc=%d] No web source texts to map sentences against", document_id)
    except Exception as e:
        logger.exception("[doc=%d] Sentence mapping failed: %s", document_id, e)
        sentence_source_map = {}

    # ── STAGE 4: AI Detection (50%) ────────────────────────────────────────────
    task_self.update_state(state="PROGRESS", meta={"progress": 50, "stage": "Detecting AI content"})
    t3 = _time.perf_counter()

    ai_score = 0.0
    ai_breakdown = {}
    try:
        result = detect_ai_content_detailed(text)  # ✅ NO AWAIT — it's sync   #result = await asyncio.to_thread(detect_ai_content_detailed, text)
        ai_score = result.get("score", 0.0)
        ai_breakdown = result.get("breakdown", {})
        logger.info(
            "[doc=%d] ai_detection=%.1f%% ms=%.0f",
            document_id, ai_score,
            (_time.perf_counter() - t3) * 1000,
        )
    except Exception as e:
        logger.exception("[doc=%d] ai_detection_failed: %s", document_id, e)
        ai_score = 0.0
        ai_breakdown = {}

    # ── STAGE 5: Compute final scores ──────────────────────────────────────────
    task_self.update_state(state="PROGRESS", meta={"progress": 80, "stage": "Computing final scores"})

    commoncrawl_score = 0.0  # CommonCrawl integration is future work
    try:
        commoncrawl_score = await asyncio.to_thread(
            local_plagiarism_score_with_commoncrawl, text
        )
    except Exception as e:
        logger.warning("[doc=%d] commoncrawl_failed: %s", document_id, e)
        commoncrawl_score = 0.0

    plagiarism_score, originality_score, ai_score, internal_score = compute_scores(
        verbatim_web_score=verbatim_web_score,
        commoncrawl_score=commoncrawl_score,
        local_score=local_score,
        ai_score=ai_score,
    )

    interpretation = classify_submission(ai_score, plagiarism_score)

    # ── STAGE 6: Build sources list ────────────────────────────────────────────
    sources = []
    for url in web_search_result.get("urls", []):
        match_data = web_search_result.get("matches", {}).get(url, {})
        match_pct = match_data.get("match_pct", 0.0)
        
        # Only encode sources with match% >= 0.1
        if match_pct >= 0.1:
            encoded = encode_web_source(url, match_pct)
            if encoded:
                sources.append(encoded)

    # Add local DB sources if significant match
    if local_score > 0.1:
        sources.append("local_db::internal_database")

    # ── Compute processing time ────────────────────────────────────────────────
    end = dt.utcnow()
    processing_time = (end - start).total_seconds()

    # ── STAGE 7: Store analysis result ─────────────────────────────────────────
    task_self.update_state(state="PROGRESS", meta={"progress": 90, "stage": "Storing results"})

    result_obj = AnalysisResult(
        document_id=document_id,
        analyzed_by=user_id,
        ai_detected_percentage=ai_score,
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
        "[doc=%d] analysis_complete | %s | risk=%s | "
        "ai=%.1f%% plag=%.1f%% orig=%.1f%% internal=%.1f%% | "
        "sources=%d duration=%.2fs text_extracted=%d chars",
        document_id,
        interpretation["case"], interpretation["risk"],
        ai_score, plagiarism_score, originality_score, internal_score,
        len(sources), processing_time, len(extracted_text),
    )

    return {
        "document_id": document_id,
        "status": "completed",
        "scores": {
            "ai": ai_score,
            "plagiarism": plagiarism_score,
            "originality": originality_score,
            "internal": internal_score,
        },
        "processing_time": processing_time,
    }


# ── Celery task ────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="run_analysis")
def run_analysis(self, document_id: int, user_id: str):
    """
    Celery task wrapper. Uses a persistent event loop instead of asyncio.run().

    asyncio.run() creates and destroys an event loop per task call.
    asyncpg pools are bound to the loop they were created on — destroying
    the loop corrupts the pool. Subsequent tasks hang waiting on invalid fds.

    loop.run_until_complete() on a persistent loop prevents this entirely.
    """
    logger.info("Task received | task_id=%s doc_id=%d user=%s",
                self.request.id, document_id, user_id)

    analysis_started()

    try:
        loop   = _get_worker_loop()
        result = loop.run_until_complete(
            _run_analysis_async(document_id, user_id, self)
        )

        analysis_completed(result.get("processing_time", 0.0))
        logger.info("Task SUCCESS | task_id=%s doc_id=%d scores=%s",
                    self.request.id, document_id, result.get("scores", {}))
        return result

    except Exception as e:
        analysis_failed()
        logger.exception("Task FAILED | task_id=%s doc_id=%d error=%s",
                         self.request.id, document_id, str(e))
        self.update_state(
            state="FAILURE",
            meta={"progress": 0, "stage": "Failed", "error": str(e)},
        )
        raise


def _fetch_url_text(url: str, timeout: int = 5) -> Optional[str]:
    """
    Fetch and extract plain text from a URL.
    
    Args:
        url: Web URL to fetch
        timeout: Request timeout in seconds
    
    Returns:
        Extracted text or None if fetch failed
    """
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Academic Research Bot)'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text if text else None
    
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url, e)
        return None