# backend/app/libs/google_search.py
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           TKREC GOOGLE SEARCH + VERBATIM MATCHING ENGINE                   ║
║                  WITH M4: CIRCUIT BREAKER + H5: SLIDING WINDOW              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  H5 ENHANCEMENT: SLIDING WINDOW COVERAGE                                    ║
║  ───────────────────────────────────────────────────────────────────────   ║
║  OLD: Search only first 50 words → misses 95% of document                  ║
║  NEW: Split text into overlapping 50-word windows with 200-word stride     ║
║       Search each window separately, aggregate max match across all         ║
║       Result: realistic coverage for entire document                        ║
║                                                                              ║
║  WINDOW CONFIG:                                                             ║
║  - Window size: 50 words (per Google verbatim query size)                  ║
║  - Stride: 200 words (overlap = 50 - (200 % 50) = 0, gaps = 150 words)    ║
║  - For 3000-word doc: ~15 windows = ~15 Google queries                     ║
║  - Throttled with delays to stay under 100/day quota                       ║
║                                                                              ║
║  QUERY CACHING (Redis):                                                     ║
║  - Cache key: md5(normalized_snippet)                                       ║
║  - TTL: 24 hours (Google results don't change much in a day)               ║
║  - Saves quota + latency for repeated snippets                             ║
║                                                                              ║
║  M4: CIRCUIT BREAKER                                                        ║
║  ───────────────────────────────────────────────────────────────────────   ║
║  Detects Google API quota exhaustion (429 Too Many Requests).              ║
║  - Tracks consecutive failures                                             ║
║  - Opens circuit after 3 failures (stops calling API)                      ║
║  - Returns empty result gracefully                                         ║
║  - Analysis continues without web search (lower plagiarism score)          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import time
import random
import re
import requests
import logging
import hashlib
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from app.env import GOOGLE_API_KEY, GOOGLE_CSE_ID
from app.libs.scraper import extract_text_from_url

logger = logging.getLogger("google_search")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

MAX_RESULTS           = 8     # Max unique URLs to return
MIN_QUERY_WORDS       = 6     # Don't bother searching tiny snippets
REQUEST_TIMEOUT       = 8
REQUEST_DELAY_RANGE   = (0.3, 0.8)

# Verbatim n-gram matching config
NGRAM_SIZE            = 8     # Words per verbatim search phrase
NGRAM_STEP            = 4     # Step between n-grams
MAX_QUERIES_PER_DOC   = 6     # Max API calls per tier
MIN_VERBATIM_NGRAM    = 6     # N-gram size for match comparison

# H5: Sliding window config (for full document coverage)
WINDOW_SIZE           = 50    # Words per search window
WINDOW_STRIDE         = 200   # Words between window starts (creates overlap)
MAX_WINDOWS_PER_DOC   = 20    # Max windows to search per document
WINDOW_CACHE_TTL_SECS = 86400 # Cache query results for 24 hours

# Circuit breaker config (M4)
CIRCUIT_BREAKER_THRESHOLD = 3  # Failures before opening circuit
CIRCUIT_BREAKER_RESET_SECS = 3600  # Reset after 1 hour

_ACADEMIC_STOP_PHRASES = {
    "in this paper", "we propose", "results show", "in this work",
    "the proposed", "as shown in", "can be seen", "it can be",
    "as a result", "in addition", "on the other hand", "for example",
    "in order to", "due to the", "based on the", "with respect to",
}

# Global query cache (in-memory dict, cleared on restart)
# Format: {md5_hash: {"urls": [...], "matches": {...}, "top_match_pct": X, "timestamp": T}}
_query_cache: Dict[str, Dict] = {}


# ─────────────────────────────────────────────────────────────────────────────
# M4: CIRCUIT BREAKER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class GoogleAPICircuitBreaker:
    """
    Circuit breaker for Google Custom Search API.
    
    States:
    - CLOSED (normal): API calls proceed
    - OPEN (quota hit): API calls blocked, returns empty immediately
    - HALF_OPEN (recovery): allows single test call after timeout
    
    Detects quota exhaustion (429, 403 'quota exceeded', etc.)
    """
    
    def __init__(self, threshold: int = CIRCUIT_BREAKER_THRESHOLD, 
                 reset_timeout: int = CIRCUIT_BREAKER_RESET_SECS):
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
    
    def record_success(self):
        """Call after successful API request."""
        self.failure_count = 0
        self.is_open = False
        logger.info("✅ Google API success — circuit CLOSED")
    
    def record_failure(self, error: str = ""):
        """Call after failed API request."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        logger.warning(
            "❌ Google API failure #%d/%d | Error: %s",
            self.failure_count, self.threshold, error[:100]
        )
        
        if self.failure_count >= self.threshold:
            self.is_open = True
            logger.error(
                "⛔ CIRCUIT BREAKER OPEN — Google API quota likely exhausted. "
                "Web search disabled for %d seconds.",
                self.reset_timeout
            )
    
    def can_attempt(self) -> bool:
        """Check if we can attempt an API call."""
        if not self.is_open:
            return True
        
        # Check if recovery timeout has passed
        if self.last_failure_time:
            elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
            if elapsed > self.reset_timeout:
                self.is_open = False
                self.failure_count = 0
                logger.info("🔄 Circuit breaker timeout reached — attempting recovery")
                return True
        
        return False
    
    def is_quota_error(self, status_code: int, error_text: str = "") -> bool:
        """Detect if error is quota-related."""
        if status_code == 429:  # Too Many Requests
            return True
        if status_code == 403:  # Forbidden (often quota)
            quota_signals = {"quota", "exceeded", "rate limit"}
            return any(sig in error_text.lower() for sig in quota_signals)
        return False


# Global circuit breaker instance
_google_circuit_breaker = GoogleAPICircuitBreaker()


# ─────────────────────────────────────────────────────────────────────────────
# H5: SLIDING WINDOW FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _create_windows(text: str, window_size: int = WINDOW_SIZE, 
                    stride: int = WINDOW_STRIDE) -> List[str]:
    """
    Split text into overlapping windows of roughly equal size.
    
    Args:
        text: Full document text
        window_size: Words per window (e.g., 50)
        stride: Words between window starts (e.g., 200)
                If stride > window_size, windows don't overlap.
                If stride < window_size, windows overlap.
    
    Returns:
        List of window texts (each is ~window_size words)
    """
    words = text.split()
    if len(words) < window_size:
        return [text]  # Document smaller than one window
    
    windows = []
    for i in range(0, len(words), stride):
        window_text = " ".join(words[i:i + window_size])
        if len(window_text.split()) >= MIN_QUERY_WORDS:
            windows.append(window_text)
        
        if len(windows) >= MAX_WINDOWS_PER_DOC:
            break
    
    return windows


def _get_cache_key(text: str) -> str:
    """Generate cache key from normalized text."""
    normalized = " ".join(text.split()).lower()
    return hashlib.md5(normalized.encode()).hexdigest()


def _get_from_cache(text: str) -> Optional[Dict]:
    """Retrieve cached query result if still valid."""
    key = _get_cache_key(text)
    
    if key not in _query_cache:
        return None
    
    cached = _query_cache[key]
    age_secs = (datetime.utcnow() - cached["timestamp"]).total_seconds()
    
    if age_secs > WINDOW_CACHE_TTL_SECS:
        del _query_cache[key]  # Expire old cache entry
        return None
    
    logger.debug("Cache hit for window: %s (age=%.1fs)", key[:8], age_secs)
    return cached["result"]


def _set_cache(text: str, result: Dict) -> None:
    """Store query result in cache."""
    key = _get_cache_key(text)
    _query_cache[key] = {
        "result": result,
        "timestamp": datetime.utcnow(),
    }
    logger.debug("Cache set for window: %s", key[:8])


def _aggregate_window_results(window_results: List[Tuple[str, Dict]]) -> Dict:
    """
    Aggregate per-window results into a single result.
    
    Args:
        window_results: List of (window_text, result_dict) tuples
    
    Returns:
        Aggregated result with:
        - urls: unique URLs across all windows (sorted by match%)
        - matches: per-URL data (taking max match% across windows)
        - top_match_pct: highest match% across all windows
        - windows_searched: count of windows processed
    """
    all_urls: Dict[str, Dict] = {}  # url → best match data
    top_match_pct = 0.0
    windows_with_results = 0
    
    for window_text, result in window_results:
        if not result.get("urls"):
            continue
        
        windows_with_results += 1
        
        for url in result.get("urls", []):
            match_data = result.get("matches", {}).get(url, {})
            match_pct = match_data.get("match_pct", 0.0)
            
            if url not in all_urls or match_pct > all_urls[url].get("match_pct", 0.0):
                all_urls[url] = match_data
                all_urls[url]["match_pct"] = match_pct
            
            top_match_pct = max(top_match_pct, match_pct)
    
    # Sort URLs by match % descending
    sorted_urls = sorted(
        all_urls.keys(),
        key=lambda u: all_urls[u].get("match_pct", 0.0),
        reverse=True,
    )[:MAX_RESULTS]
    
    return {
        "urls": sorted_urls,
        "matches": {u: all_urls[u] for u in sorted_urls},
        "top_match_pct": round(top_match_pct, 2),
        "windows_searched": windows_with_results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# QUERY BUILDING
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_for_query(text: str) -> List[str]:
    """Tokenize text into clean words for n-gram query building."""
    words = re.sub(r"[^a-zA-Z0-9\s]", " ", text).split()
    return [w.lower() for w in words if len(w) >= 3 and not w.isdigit()]


def _is_generic_phrase(phrase: str) -> bool:
    """Check if a phrase is too generic to be useful as a search query."""
    phrase_lower = phrase.lower().strip()
    for stop in _ACADEMIC_STOP_PHRASES:
        if stop in phrase_lower:
            return True
    common = {"the", "and", "for", "are", "but", "not", "you", "all",
              "can", "has", "had", "have", "its", "was", "our", "that",
              "this", "with", "from", "they", "been", "their"}
    words = phrase_lower.split()
    if not words:
        return True
    return sum(1 for w in words if w in common) / len(words) > 0.5


def build_verbatim_queries(text: str, max_queries: int = MAX_QUERIES_PER_DOC) -> List[str]:
    """
    Tier 1: Quoted verbatim n-gram queries.
    Each phrase wrapped in double quotes for Google exact-phrase matching.
    """
    words = _normalize_for_query(text)
    if len(words) < MIN_QUERY_WORDS:
        return []

    all_ngrams = []
    for i in range(0, len(words) - NGRAM_SIZE + 1, NGRAM_STEP):
        phrase = " ".join(words[i:i + NGRAM_SIZE])
        if not _is_generic_phrase(phrase):
            all_ngrams.append((i, phrase))

    if not all_ngrams:
        return []

    selected = []
    n = len(all_ngrams)

    # Strategy 1: Beginning
    for _, phrase in all_ngrams[:5]:
        if not _is_generic_phrase(phrase):
            selected.append(phrase)
            break

    # Strategy 2: Early-middle
    if n >= 4:
        selected.append(all_ngrams[n // 4][1])
    
    # Strategy 3: Middle
    if n >= 2:
        selected.append(all_ngrams[n // 2][1])
    
    # Strategy 4: Late-middle
    if n >= 4:
        selected.append(all_ngrams[(3 * n) // 4][1])

    # Strategy 5: End
    for _, phrase in reversed(all_ngrams[-5:]):
        if not _is_generic_phrase(phrase):
            selected.append(phrase)
            break

    # Strategy 6: Seeded random
    seed = hash(text[:300]) % (2**32)
    rng = random.Random(seed)
    for idx in rng.sample(range(n), min(3, n)):
        selected.append(all_ngrams[idx][1])

    # Deduplicate
    seen = set()
    unique = []
    for phrase in selected:
        if phrase not in seen:
            seen.add(phrase)
            unique.append(phrase)

    return [f'"{phrase}"' for phrase in unique[:max_queries]]


def build_broad_queries(text: str, max_queries: int = MAX_QUERIES_PER_DOC) -> List[str]:
    """
    Tier 2 + Tier 3: Broad (non-quoted) fallback queries.
    
    Used when verbatim quoted queries return 0 results — common for:
    - Government/regional sites with low Google indexing (e.g. tgpsc.gov.in)
    - Documents with highly specific proper nouns that don't phrase-match
    """
    words = text.split()
    if len(words) < MIN_QUERY_WORDS:
        return []

    queries = []
    slices = [
        words[:12],
        words[len(words) // 4: len(words) // 4 + 12],
        words[len(words) // 2: len(words) // 2 + 12],
        words[3 * len(words) // 4: 3 * len(words) // 4 + 12],
        words[-12:],
    ]

    for s in slices:
        q = " ".join(s).strip()
        if q and q not in queries:
            queries.append(q)

    # Seeded random slice
    seed = hash(text[:200])
    rng = random.Random(seed)
    start = rng.randint(0, max(0, len(words) - 12))
    q = " ".join(words[start:start + 12]).strip()
    if q and q not in queries:
        queries.append(q)

    return queries[:max_queries]


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE SEARCH API (WITH CIRCUIT BREAKER)
# ─────────────────────────────────────────────────────────────────────────────

def _do_google_search(query: str, num: int = 5) -> List[str]:
    """
    Execute a single Google Custom Search API query.
    Returns list of URLs, or empty list if quota exceeded.
    
    Circuit breaker prevents hammering API when quota is exhausted.
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []
    
    # Check circuit breaker status
    if not _google_circuit_breaker.can_attempt():
        logger.warning(
            "🔴 Circuit breaker OPEN — skipping Google API call. "
            "Quota likely exhausted. Web search disabled."
        )
        return []

    url = (
        "https://www.googleapis.com/customsearch/v1"
        f"?key={GOOGLE_API_KEY}"
        f"&cx={GOOGLE_CSE_ID}"
        f"&q={quote_plus(query)}"
        f"&num={num}"
    )

    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        # Check for quota/rate limit errors
        if _google_circuit_breaker.is_quota_error(r.status_code, r.text):
            error_msg = f"HTTP {r.status_code} — quota exceeded"
            _google_circuit_breaker.record_failure(error_msg)
            logger.error("⛔ Google API quota error: %s", error_msg)
            return []
        
        if r.status_code != 200:
            error_msg = f"HTTP {r.status_code}"
            _google_circuit_breaker.record_failure(error_msg)
            logger.warning("Google Search API error %d for query: %s", r.status_code, query[:80])
            return []
        
        # Success — reset failure count
        _google_circuit_breaker.record_success()
        
        items = r.json().get("items", [])
        links = [item.get("link") for item in items if item.get("link")]
        
        if links:
            logger.debug("✅ Google API success: %d URLs for query: %s", len(links), query[:80])
        
        return links

    except requests.exceptions.Timeout:
        error_msg = "Request timeout (8s)"
        _google_circuit_breaker.record_failure(error_msg)
        logger.warning("Google Search request timeout")
        return []
    
    except requests.exceptions.ConnectionError:
        error_msg = "Connection error"
        _google_circuit_breaker.record_failure(error_msg)
        logger.warning("Google Search connection error")
        return []
    
    except Exception as e:
        error_msg = str(e)[:100]
        _google_circuit_breaker.record_failure(error_msg)
        logger.warning("Google Search request failed: %s", e)
        return []


def _collect_urls(queries: List[str], label: str = "") -> List[str]:
    """
    Run a list of queries through Google Search, collect unique URLs.
    Stops once MAX_RESULTS is reached.
    """
    collected: List[str] = []
    
    for query in queries:
        # Circuit breaker check before each query
        if not _google_circuit_breaker.can_attempt():
            logger.warning("Circuit breaker open — stopping URL collection")
            break
        
        urls = _do_google_search(query, num=5)
        for url in urls:
            if url and url not in collected:
                collected.append(url)
        
        time.sleep(random.uniform(*REQUEST_DELAY_RANGE))
        
        if len(collected) >= MAX_RESULTS:
            break

    if collected:
        logger.info("Google Search [%s]: %d URLs found", label or "query", len(collected))
    else:
        logger.info("Google Search [%s]: No URLs found", label or "query")
    
    return collected[:MAX_RESULTS]


# ─────────────────────────────────────────────────────────────────────────────
# VERBATIM MATCH PERCENTAGE
# ─────────────────────────────────────────────────────────────────────────────

def verbatim_match_percentage(source: str, target: str, ngram_size: int = MIN_VERBATIM_NGRAM) -> float:
    """
    What % of source text appears VERBATIM in target?

    Method: sliding n-gram window over source, check each against
    a pre-built set of all target n-grams.

    Returns token coverage % averaged with n-gram match % (0–100).
    """
    if not source or not target:
        return 0.0

    def tokenize(text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return text.split()

    src_tokens = tokenize(source)
    tgt_tokens = tokenize(target)

    if len(src_tokens) < ngram_size or len(tgt_tokens) < ngram_size:
        return 0.0

    target_ngrams: set = set()
    for i in range(len(tgt_tokens) - ngram_size + 1):
        target_ngrams.add(tuple(tgt_tokens[i:i + ngram_size]))

    source_total = len(src_tokens) - ngram_size + 1
    if source_total <= 0:
        return 0.0

    source_matched = 0
    matched_positions: set = set()

    for i in range(source_total):
        gram = tuple(src_tokens[i:i + ngram_size])
        if gram in target_ngrams:
            source_matched += 1
            for j in range(i, i + ngram_size):
                matched_positions.add(j)

    token_coverage  = len(matched_positions) / len(src_tokens) * 100.0
    ngram_match_pct = source_matched / source_total * 100.0
    match_pct       = (token_coverage + ngram_match_pct) / 2.0

    logger.debug(
        "Verbatim match: %.1f%% (token_cov=%.1f%% ngram=%.1f%%) | "
        "src=%d tgt=%d ngram_size=%d",
        match_pct, token_coverage, ngram_match_pct,
        len(src_tokens), len(tgt_tokens), ngram_size,
    )

    return round(min(match_pct, 100.0), 2)


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPE + MATCH LOOP
# ─────────────────────────────────────────────────────────────────────────────

def _scrape_and_match(text: str, urls: List[str]) -> tuple:
    """
    For each URL: scrape text, compute verbatim match %.
    Returns (matches_dict, top_match_pct).
    """
    matches: Dict[str, Dict] = {}
    top_match_pct = 0.0

    for url in urls:
        try:
            scraped_text = extract_text_from_url(url)

            if not scraped_text:
                matches[url] = {
                    "match_pct": 0.0, "scraped_text_length": 0,
                    "scraped": False, "scrape_failed": True,
                }
                continue

            match_pct = verbatim_match_percentage(text, scraped_text)
            matches[url] = {
                "match_pct": match_pct,
                "scraped_text_length": len(scraped_text),
                "scraped": True,
                "scrape_failed": False,
            }

            if match_pct > top_match_pct:
                top_match_pct = match_pct

            logger.info("URL: %s | verbatim_match=%.1f%%", url[:80], match_pct)

        except Exception as e:
            logger.warning("Failed to process URL %s: %s", url[:80], e)
            matches[url] = {
                "match_pct": 0.0, "scraped_text_length": 0,
                "scraped": False, "scrape_failed": True, "error": str(e),
            }

    return matches, top_match_pct


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — WITH 3-TIER FALLBACK + CIRCUIT BREAKER + H5 SLIDING WINDOW
# ─────────────────────────────────────────────────────────────────────────────

def _search_window(window_text: str) -> Dict:
    """
    Search a single text window through all 3 tiers.
    Returns result dict with urls, matches, top_match_pct.
    """
    # Check cache first
    cached = _get_from_cache(window_text)
    if cached:
        return cached
    
    collected_urls: List[str] = []
    queries_used: List[str]   = []
    tier_used = "none"

    # ── TIER 1: Quoted verbatim n-gram queries ────────────────────────────
    verbatim_queries = build_verbatim_queries(window_text)
    if verbatim_queries:
        collected_urls = _collect_urls(verbatim_queries, label="verbatim")
        if collected_urls:
            queries_used = verbatim_queries
            tier_used    = "verbatim"
            logger.info("Tier 1 (verbatim) succeeded: %d URLs", len(collected_urls))

    # ── TIER 2: Broad keyword queries (no quotes) ─────────────────────────
    if not collected_urls:
        logger.info(
            "Tier 1 (verbatim) returned 0 URLs — trying Tier 2 (broad keyword)"
        )
        broad_queries = build_broad_queries(window_text)
        if broad_queries:
            collected_urls = _collect_urls(broad_queries, label="broad")
            if collected_urls:
                queries_used = broad_queries
                tier_used    = "broad"
                logger.info("Tier 2 (broad) succeeded: %d URLs", len(collected_urls))

    # ── TIER 3: Legacy 12-word slices (last resort) ───────────────────────
    if not collected_urls:
        logger.info(
            "Tier 2 (broad) returned 0 URLs — trying Tier 3 (legacy slices)"
        )
        words = window_text.split()
        legacy_queries = []

        if len(words) >= MIN_QUERY_WORDS:
            seed = hash(window_text[:200])
            rng  = random.Random(seed)
            start = rng.randint(0, max(0, len(words) - 12))

            for q in [
                " ".join(words[:12]),
                " ".join(words[len(words)//2: len(words)//2 + 12]),
                " ".join(words[-12:]),
                " ".join(words[start:start + 12]),
            ]:
                q = q.strip()
                if q and q not in legacy_queries:
                    legacy_queries.append(q)

        if legacy_queries:
            collected_urls = _collect_urls(legacy_queries, label="legacy")
            if collected_urls:
                queries_used = legacy_queries
                tier_used    = "legacy"
                logger.info("Tier 3 (legacy) succeeded: %d URLs", len(collected_urls))

    # ── Final: no URLs from any tier ─────────────────────────────────────
    if not collected_urls:
        if _google_circuit_breaker.is_open:
            logger.warning(
                "⛔ Google API circuit breaker OPEN — quota exhausted. "
                "Returning empty result for this window."
            )
        result = _empty_result(queries_used=verbatim_queries)
    else:
        # ── Scrape + verbatim match ───────────────────────────────────────────
        matches, top_match_pct = _scrape_and_match(window_text, collected_urls)

        # Sort by match % descending
        sorted_urls = sorted(
            collected_urls,
            key=lambda u: matches.get(u, {}).get("match_pct", 0.0),
            reverse=True,
        )

        logger.info(
            "Window search complete | tier=%s | urls=%d | top_match=%.1f%%",
            tier_used, len(sorted_urls), top_match_pct,
        )

        result = {
            "urls":          sorted_urls,
            "matches":       matches,
            "top_match_pct": round(top_match_pct, 2),
            "queries_used":  queries_used,
            "tier_used":     tier_used,
        }
    
    # Cache the result
    _set_cache(window_text, result)
    return result


def google_search_with_matches(text: str, use_sliding_window: bool = True) -> Dict:
    """
    Full verbatim search pipeline with 3-tier fallback.
    
    H5 ENHANCEMENT: Sliding window support
    - If text > 50 words and use_sliding_window=True:
      Split into overlapping windows, search each, aggregate results
    - If text <= 50 words or use_sliding_window=False:
      Use original single-pass pipeline
    
    WITH M4 CIRCUIT BREAKER:
    - Detects Google API quota exhaustion
    - Returns empty result gracefully if quota hit
    - Analysis continues without web search
    - Re-enables after 1 hour timeout

    Returns:
    {
        "urls":          [...],        # All unique URLs found (sorted by match%)
        "matches":       {...},        # Per-URL: match_pct, scraped, etc.
        "top_match_pct": 12.3,        # Highest verbatim match across all windows
        "queries_used":  [...],        # Queries that found results
        "tier_used":     "verbatim",  # Which tier produced results (last window)
        "windows_searched": 1,         # H5: Number of windows searched
    }
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        logger.warning("Google Search skipped — API key or CSE ID not set")
        return _empty_result()

    words = text.split()
    
    # H5: Decide whether to use sliding window
    if use_sliding_window and len(words) > WINDOW_SIZE:
        logger.info(
            "H5 Sliding window enabled: %d words → splitting into windows (size=%d, stride=%d)",
            len(words), WINDOW_SIZE, WINDOW_STRIDE
        )
        
        windows = _create_windows(text, window_size=WINDOW_SIZE, stride=WINDOW_STRIDE)
        logger.info("Created %d windows for document (%d words)", len(windows), len(words))
        
        window_results: List[Tuple[str, Dict]] = []
        
        for i, window in enumerate(windows):
            logger.info("Searching window %d/%d...", i + 1, len(windows))
            result = _search_window(window)
            window_results.append((window, result))
            
            # Throttle between window searches (already has delays inside _search_window)
            if i < len(windows) - 1:
                time.sleep(random.uniform(0.5, 1.5))
        
        # Aggregate all window results
        aggregated = _aggregate_window_results(window_results)
        aggregated["windows_searched"] = len(windows)
        
        logger.info(
            "Sliding window search complete | windows=%d | total_urls=%d | top_match=%.1f%%",
            len(windows), len(aggregated["urls"]), aggregated["top_match_pct"]
        )
        
        return aggregated
    
    else:
        # Original single-pass pipeline (for small documents or disabled sliding window)
        logger.info("Single-pass search (document too small or sliding window disabled)")
        result = _search_window(text)
        result["windows_searched"] = 1
        return result


def _empty_result(queries_used: Optional[List[str]] = None) -> Dict:
    """Return empty result structure."""
    return {
        "urls":          [],
        "matches":       {},
        "top_match_pct": 0.0,
        "queries_used":  queries_used or [],
        "tier_used":     "none",
        "windows_searched": 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# BACKWARD-COMPATIBLE PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def google_search(text: str) -> List[str]:
    """
    Backward-compatible API — returns list of URLs only.
    Internally uses the full 3-tier pipeline with circuit breaker and sliding windows.
    """
    result = google_search_with_matches(text)
    return result.get("urls", [])


def get_circuit_breaker_status() -> Dict[str, any]:
    """
    Return circuit breaker status for monitoring/debugging.
    Called by /health endpoint or admin dashboard.
    """
    return {
        "is_open": _google_circuit_breaker.is_open,
        "failure_count": _google_circuit_breaker.failure_count,
        "threshold": _google_circuit_breaker.threshold,
        "last_failure_time": _google_circuit_breaker.last_failure_time.isoformat() if _google_circuit_breaker.last_failure_time else None,
        "status": "⛔ OPEN" if _google_circuit_breaker.is_open else "✅ CLOSED",
        "cache_size": len(_query_cache),
    }