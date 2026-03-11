#  # backend/app/libs/google_search.py

# import time
# import random
# import requests
# from typing import List
# from urllib.parse import quote_plus

# from app.env import GOOGLE_API_KEY, GOOGLE_CSE_ID

# MAX_RESULTS = 8
# MIN_QUERY_WORDS = 6
# REQUEST_TIMEOUT = 8
# REQUEST_DELAY_RANGE = (0.3, 0.8)


# def build_search_queries(text: str) -> List[str]:
#     words = text.split()
#     if len(words) < MIN_QUERY_WORDS:
#         return []

#     queries = [
#         " ".join(words[:12]),
#         " ".join(words[len(words)//2:len(words)//2 + 12]),
#         " ".join(words[-12:]),
#     ]

#     seed = hash(text[:200])
#     rng = random.Random(seed)
#     start = rng.randint(0, max(0, len(words) - 12))
#     queries.append(" ".join(words[start:start + 12]))

#     return list(dict.fromkeys(q.strip() for q in queries if q.strip()))


# def google_search(text: str) -> List[str]:
#     """
#     LEGAL NOTE:
#     - Uses Google Custom Search JSON API
#     - No HTML scraping
#     - Fully ToS compliant
#     """

#     if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
#         return []

#     queries = build_search_queries(text)
#     collected_urls: List[str] = []

#     for query in queries:
#         url = (
#             "https://www.googleapis.com/customsearch/v1"
#             f"?key={GOOGLE_API_KEY}"
#             f"&cx={GOOGLE_CSE_ID}"
#             f"&q={quote_plus(query)}"
#             f"&num=5"
#         )

#         try:
#             r = requests.get(url, timeout=REQUEST_TIMEOUT)
#             if r.status_code != 200:
#                 continue

#             for item in r.json().get("items", []):
#                 link = item.get("link")
#                 if link and link not in collected_urls:
#                     collected_urls.append(link)

#         except Exception:
#             continue

#         time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

#         if len(collected_urls) >= MAX_RESULTS:
#             break

#     return collected_urls[:MAX_RESULTS]























# # backend/app/libs/google_search.py
# """
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║           TKREC GOOGLE SEARCH + VERBATIM MATCHING ENGINE                   ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║                                                                              ║
# ║  Issue 3 Fix: Verbatim Matching — Same Words, Same Order                   ║
# ║  ─────────────────────────────────────────────────────────────────────────  ║
# ║                                                                              ║
# ║  HOW IT WORKS                                                               ║
# ║  1. Text is chunked into overlapping n-grams (default n=8 words)           ║
# ║  2. Each n-gram is wrapped in "double quotes" → forces Google exact match  ║
# ║  3. Google Search API returns URLs for pages containing that exact phrase  ║
# ║  4. The scraped page text is compared verbatim against the source          ║
# ║  5. Per-URL exact match % is returned (how much of the doc appears there)  ║
# ║                                                                              ║
# ║  DESIGN                                                                     ║
# ║  • google_search(text) → List[str]  (URLs, backward-compatible)            ║
# ║  • google_search_with_matches(text) → Dict with URLs + per-URL match%     ║
# ║  • verbatim_match_percentage(source, target) → float (0-100%)             ║
# ║                                                                              ║
# ║  LEGAL NOTE:                                                                ║
# ║  • Uses Google Custom Search JSON API — fully ToS compliant                ║
# ║  • No HTML scraping of Google results pages                                ║
# ║  • Respects robots.txt on scraped target pages (via scraper.py)           ║
# ║                                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
# """

# import time
# import random
# import re
# import requests
# import logging
# from typing import List, Dict, Optional, Tuple
# from urllib.parse import quote_plus

# from app.env import GOOGLE_API_KEY, GOOGLE_CSE_ID
# from app.libs.scraper import extract_text_from_url

# logger = logging.getLogger("google_search")

# # ─────────────────────────────────────────────────────────────────────────────
# # CONFIGURATION
# # ─────────────────────────────────────────────────────────────────────────────

# MAX_RESULTS           = 8     # Max unique URLs to return
# MIN_QUERY_WORDS       = 6     # Don't bother searching tiny snippets
# REQUEST_TIMEOUT       = 8
# REQUEST_DELAY_RANGE   = (0.3, 0.8)  # Rate-limit friendly

# # Verbatim n-gram matching config
# NGRAM_SIZE            = 8     # Number of words per verbatim search phrase
# NGRAM_STEP            = 4     # Step size between n-grams (overlapping by NGRAM_SIZE - NGRAM_STEP)
# MAX_QUERIES_PER_DOC   = 6     # Limit total API calls per document
# MIN_VERBATIM_NGRAM    = 6     # Minimum n-gram size for verbatim comparison (smaller than search)

# # Academic stopwords — don't use these alone as search queries
# # (they appear in many papers and won't narrow results)
# _ACADEMIC_STOP_PHRASES = {
#     "in this paper", "we propose", "results show", "in this work",
#     "the proposed", "as shown in", "can be seen", "it can be",
#     "as a result", "in addition", "on the other hand", "for example",
#     "in order to", "due to the", "based on the", "with respect to",
# }


# # ─────────────────────────────────────────────────────────────────────────────
# # QUERY BUILDING — VERBATIM N-GRAM QUERIES
# # ─────────────────────────────────────────────────────────────────────────────

# def _normalize_for_query(text: str) -> List[str]:
#     """
#     Tokenize text into clean words for n-gram query building.
#     Remove punctuation, lowercase, filter short/stopword tokens.
#     """
#     words = re.sub(r"[^a-zA-Z0-9\s]", " ", text).split()
#     # Keep words that are at least 3 chars and not pure numbers
#     return [w.lower() for w in words if len(w) >= 3 and not w.isdigit()]


# def _is_generic_phrase(phrase: str) -> bool:
#     """Check if a phrase is too generic to be useful as a verbatim search query."""
#     phrase_lower = phrase.lower().strip()
#     for stop in _ACADEMIC_STOP_PHRASES:
#         if stop in phrase_lower:
#             return True
#     # Also skip if more than 40% of the words are very common English words
#     common = {"the", "and", "for", "are", "but", "not", "you", "all",
#               "can", "has", "had", "have", "its", "was", "our", "that",
#               "this", "with", "from", "they", "been", "their"}
#     words = phrase_lower.split()
#     if not words:
#         return True
#     common_ratio = sum(1 for w in words if w in common) / len(words)
#     return common_ratio > 0.5


# def build_verbatim_queries(text: str, max_queries: int = MAX_QUERIES_PER_DOC) -> List[str]:
#     """
#     Build verbatim search queries from the document text.

#     Strategy:
#     1. Slide an n-gram window across the text
#     2. Wrap each n-gram in double quotes → Google exact phrase search
#     3. Filter out generic/stopword-heavy phrases
#     4. Select diverse phrases (beginning, middle, end, random)
#     5. Deduplicate

#     Returns:
#         List of query strings, each wrapped in double quotes for exact matching.
#         Example: ['"incremental subspace learning streaming data"',
#                   '"optimized multi-viewpoint assessment framework"']
#     """
#     words = _normalize_for_query(text)
#     if len(words) < MIN_QUERY_WORDS:
#         return []

#     # Generate all possible n-grams
#     all_ngrams = []
#     for i in range(0, len(words) - NGRAM_SIZE + 1, NGRAM_STEP):
#         phrase = " ".join(words[i:i + NGRAM_SIZE])
#         if not _is_generic_phrase(phrase):
#             all_ngrams.append((i, phrase))

#     if not all_ngrams:
#         return []

#     # Select diverse n-grams from different parts of the document
#     selected = []
#     n = len(all_ngrams)

#     # Strategy 1: Beginning (first substantive n-gram)
#     for _, phrase in all_ngrams[:5]:
#         if not _is_generic_phrase(phrase):
#             selected.append(phrase)
#             break

#     # Strategy 2: Early-middle
#     if n >= 4:
#         idx = n // 4
#         phrase = all_ngrams[idx][1]
#         if not _is_generic_phrase(phrase):
#             selected.append(phrase)

#     # Strategy 3: Middle
#     if n >= 2:
#         idx = n // 2
#         phrase = all_ngrams[idx][1]
#         if not _is_generic_phrase(phrase):
#             selected.append(phrase)

#     # Strategy 4: Late-middle
#     if n >= 4:
#         idx = (3 * n) // 4
#         phrase = all_ngrams[idx][1]
#         if not _is_generic_phrase(phrase):
#             selected.append(phrase)

#     # Strategy 5: End (last substantive n-gram)
#     for _, phrase in reversed(all_ngrams[-5:]):
#         if not _is_generic_phrase(phrase):
#             selected.append(phrase)
#             break

#     # Strategy 6: Seeded random for reproducibility
#     seed = hash(text[:300]) % (2**32)
#     rng = random.Random(seed)
#     random_indices = rng.sample(range(n), min(3, n))
#     for idx in random_indices:
#         phrase = all_ngrams[idx][1]
#         if not _is_generic_phrase(phrase):
#             selected.append(phrase)

#     # Deduplicate while preserving order
#     seen = set()
#     unique = []
#     for phrase in selected:
#         if phrase not in seen:
#             seen.add(phrase)
#             unique.append(phrase)

#     # Wrap in double quotes for Google exact phrase matching
#     quoted = [f'"{phrase}"' for phrase in unique[:max_queries]]

#     logger.debug("Built %d verbatim queries from %d words", len(quoted), len(words))
#     return quoted


# # ─────────────────────────────────────────────────────────────────────────────
# # GOOGLE SEARCH API
# # ─────────────────────────────────────────────────────────────────────────────

# def _do_google_search(query: str, num: int = 5) -> List[str]:
#     """
#     Execute a single Google Custom Search API query.
#     Returns list of result URLs.
#     """
#     if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
#         return []

#     url = (
#         "https://www.googleapis.com/customsearch/v1"
#         f"?key={GOOGLE_API_KEY}"
#         f"&cx={GOOGLE_CSE_ID}"
#         f"&q={quote_plus(query)}"
#         f"&num={num}"
#     )

#     try:
#         r = requests.get(url, timeout=REQUEST_TIMEOUT)
#         if r.status_code != 200:
#             logger.warning("Google Search API error %d for query: %s", r.status_code, query[:80])
#             return []

#         items = r.json().get("items", [])
#         links = [item.get("link") for item in items if item.get("link")]
#         return links

#     except Exception as e:
#         logger.warning("Google Search request failed: %s", e)
#         return []


# # ─────────────────────────────────────────────────────────────────────────────
# # VERBATIM MATCH PERCENTAGE COMPUTATION
# # ─────────────────────────────────────────────────────────────────────────────

# def verbatim_match_percentage(source: str, target: str, ngram_size: int = MIN_VERBATIM_NGRAM) -> float:
#     """
#     Compute what percentage of the source text appears VERBATIM in the target.

#     Method:
#     1. Tokenize both texts
#     2. Build a set of all n-grams from the target text
#     3. Slide n-gram window across the source text
#     4. Count how many source n-grams appear in the target's n-gram set
#     5. Return: (matching n-grams / total source n-grams) * 100

#     This is similar to how Turnitin computes its "similarity index" —
#     it measures what fraction of the document's phrases are found elsewhere.

#     Args:
#         source:     the document being checked
#         target:     the web page text to compare against
#         ngram_size: word n-gram size for matching (default 6 words)

#     Returns:
#         Float 0.0 – 100.0 representing the % of source that verbatim-matches target
#     """
#     if not source or not target:
#         return 0.0

#     def tokenize(text: str) -> List[str]:
#         text = text.lower()
#         text = re.sub(r"[^a-z0-9\s]", " ", text)
#         return text.split()

#     src_tokens = tokenize(source)
#     tgt_tokens = tokenize(target)

#     if len(src_tokens) < ngram_size or len(tgt_tokens) < ngram_size:
#         return 0.0

#     # Build target n-gram lookup (set for O(1) lookup)
#     target_ngrams: set = set()
#     for i in range(len(tgt_tokens) - ngram_size + 1):
#         gram = tuple(tgt_tokens[i:i + ngram_size])
#         target_ngrams.add(gram)

#     # Count source n-grams that appear in target
#     source_total = len(src_tokens) - ngram_size + 1
#     if source_total <= 0:
#         return 0.0

#     source_matched = 0
#     matched_positions = set()  # Track which source tokens are "covered"

#     for i in range(source_total):
#         gram = tuple(src_tokens[i:i + ngram_size])
#         if gram in target_ngrams:
#             source_matched += 1
#             # Mark all tokens in this n-gram as covered
#             for j in range(i, i + ngram_size):
#                 matched_positions.add(j)

#     # Primary metric: percentage of source TOKENS covered by verbatim matches
#     # (not n-grams — avoids double-counting overlapping matches)
#     token_coverage = len(matched_positions) / len(src_tokens) * 100.0

#     # Secondary metric: percentage of source n-grams matched
#     ngram_match_pct = source_matched / source_total * 100.0

#     # Return the average of both metrics (balanced view)
#     match_pct = (token_coverage + ngram_match_pct) / 2.0

#     logger.debug(
#         "Verbatim match: %.1f%% (token_cov=%.1f%% ngram=%.1f%%) | "
#         "src=%d tgt=%d ngram_size=%d",
#         match_pct, token_coverage, ngram_match_pct,
#         len(src_tokens), len(tgt_tokens), ngram_size
#     )

#     return round(min(match_pct, 100.0), 2)


# # ─────────────────────────────────────────────────────────────────────────────
# # MAIN SEARCH FUNCTION — WITH VERBATIM MATCHING
# # ─────────────────────────────────────────────────────────────────────────────

# def google_search_with_matches(text: str) -> Dict:
#     """
#     Full verbatim search pipeline.

#     Steps:
#     1. Build quoted n-gram queries
#     2. Send each to Google Custom Search API
#     3. Collect all unique URLs from results
#     4. Scrape each URL (via scraper.py)
#     5. Compute verbatim match percentage for each URL
#     6. Return URLs sorted by match percentage (highest first)

#     Returns:
#     {
#         "urls": ["https://...", "https://..."],   # All unique URLs found
#         "matches": {
#             "https://...": {
#                 "match_pct": 12.3,               # Verbatim match %
#                 "scraped_text_length": 4521,     # Characters scraped
#                 "scraped": True,                 # Whether scraping succeeded
#             },
#             ...
#         },
#         "top_match_pct": 12.3,                   # Highest match across all URLs
#         "queries_used": ['"phrase one"', ...],   # Queries that were sent
#     }
#     """
#     if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
#         logger.warning("Google Search skipped — API key or CSE ID not set")
#         return _empty_result()

#     queries = build_verbatim_queries(text)
#     if not queries:
#         logger.info("No usable verbatim queries built from text")
#         return _empty_result()

#     # ── Step 1: Collect all URLs from all queries ─────────────────────────
#     collected_urls: List[str] = []

#     for query in queries:
#         urls = _do_google_search(query, num=5)
#         for url in urls:
#             if url and url not in collected_urls:
#                 collected_urls.append(url)

#         time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

#         if len(collected_urls) >= MAX_RESULTS:
#             break

#     collected_urls = collected_urls[:MAX_RESULTS]

#     if not collected_urls:
#         logger.info("Google Search returned no URLs")
#         return _empty_result(queries_used=queries)

#     # ── Step 2: Scrape each URL and compute verbatim match ────────────────
#     matches: Dict[str, Dict] = {}
#     top_match_pct = 0.0

#     for url in collected_urls:
#         try:
#             scraped_text = extract_text_from_url(url)

#             if not scraped_text:
#                 matches[url] = {
#                     "match_pct":            0.0,
#                     "scraped_text_length":  0,
#                     "scraped":              False,
#                     "scrape_failed":        True,
#                 }
#                 continue

#             match_pct = verbatim_match_percentage(text, scraped_text)

#             matches[url] = {
#                 "match_pct":            match_pct,
#                 "scraped_text_length":  len(scraped_text),
#                 "scraped":              True,
#                 "scrape_failed":        False,
#             }

#             if match_pct > top_match_pct:
#                 top_match_pct = match_pct

#             logger.info("URL: %s | verbatim_match=%.1f%%", url[:80], match_pct)

#         except Exception as e:
#             logger.warning("Failed to process URL %s: %s", url[:80], e)
#             matches[url] = {
#                 "match_pct":            0.0,
#                 "scraped_text_length":  0,
#                 "scraped":              False,
#                 "scrape_failed":        True,
#                 "error":                str(e),
#             }

#     # Sort URLs by match percentage (descending)
#     sorted_urls = sorted(
#         collected_urls,
#         key=lambda u: matches.get(u, {}).get("match_pct", 0.0),
#         reverse=True,
#     )

#     return {
#         "urls":          sorted_urls,
#         "matches":       matches,
#         "top_match_pct": round(top_match_pct, 2),
#         "queries_used":  queries,
#     }


# def _empty_result(queries_used: Optional[List[str]] = None) -> Dict:
#     """Return an empty result structure."""
#     return {
#         "urls":          [],
#         "matches":       {},
#         "top_match_pct": 0.0,
#         "queries_used":  queries_used or [],
#     }


# # ─────────────────────────────────────────────────────────────────────────────
# # BACKWARD-COMPATIBLE PUBLIC API
# # ─────────────────────────────────────────────────────────────────────────────

# def google_search(text: str) -> List[str]:
#     """
#     BACKWARD-COMPATIBLE API — called by main.py.

#     Returns list of URLs found, same as before.
#     Use google_search_with_matches() for per-URL verbatim percentages.
#     """
#     if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
#         return []

#     queries = build_verbatim_queries(text)
#     if not queries:
#         # Fallback: use the original query building strategy if verbatim yields nothing
#         return _legacy_google_search(text)

#     collected_urls: List[str] = []

#     for query in queries:
#         urls = _do_google_search(query, num=5)
#         for url in urls:
#             if url and url not in collected_urls:
#                 collected_urls.append(url)

#         time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

#         if len(collected_urls) >= MAX_RESULTS:
#             break

#     return collected_urls[:MAX_RESULTS]


# def _legacy_google_search(text: str) -> List[str]:
#     """
#     Original query building strategy as fallback.
#     Used when verbatim query building produces no results.
#     """
#     words = text.split()
#     if len(words) < MIN_QUERY_WORDS:
#         return []

#     queries = [
#         " ".join(words[:12]),
#         " ".join(words[len(words)//2:len(words)//2 + 12]),
#         " ".join(words[-12:]),
#     ]

#     seed = hash(text[:200])
#     rng = random.Random(seed)
#     start = rng.randint(0, max(0, len(words) - 12))
#     queries.append(" ".join(words[start:start + 12]))

#     queries = list(dict.fromkeys(q.strip() for q in queries if q.strip()))
#     collected_urls: List[str] = []

#     for query in queries:
#         urls = _do_google_search(query, num=5)
#         for url in urls:
#             if url and url not in collected_urls:
#                 collected_urls.append(url)

#         time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

#         if len(collected_urls) >= MAX_RESULTS:
#             break

#     return collected_urls[:MAX_RESULTS]















































# backend/app/libs/google_search.py
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           TKREC GOOGLE SEARCH + VERBATIM MATCHING ENGINE                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  HOW IT WORKS                                                               ║
║  1. Text is chunked into overlapping n-grams (default n=8 words)           ║
║  2. Each n-gram is wrapped in "double quotes" → forces Google exact match  ║
║  3. Google Search API returns URLs for pages containing that exact phrase  ║
║  4. The scraped page text is compared verbatim against the source          ║
║  5. Per-URL exact match % is returned (how much of the doc appears there)  ║
║                                                                              ║
║  FALLBACK STRATEGY (fixes 0-URL problem for govt/regional sites):          ║
║  If verbatim quoted queries return 0 URLs, automatically retries with      ║
║  broader non-quoted queries. This catches content from poorly-indexed      ║
║  sites like tgpsc.gov.in that don't appear in exact-phrase searches.       ║
║                                                                              ║
║  QUERY PIPELINE (3 tiers):                                                  ║
║  Tier 1: Quoted verbatim n-grams  →  "exact phrase here"                  ║
║  Tier 2: Key phrase + site hint   →  Hyderabad PSC 1947 history            ║
║  Tier 3: Legacy broad queries     →  first/middle/last 12 words            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import time
import random
import re
import requests
import logging
from typing import List, Dict, Optional
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

_ACADEMIC_STOP_PHRASES = {
    "in this paper", "we propose", "results show", "in this work",
    "the proposed", "as shown in", "can be seen", "it can be",
    "as a result", "in addition", "on the other hand", "for example",
    "in order to", "due to the", "based on the", "with respect to",
}


# ─────────────────────────────────────────────────────────────────────────────
# QUERY BUILDING
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_for_query(text: str) -> List[str]:
    words = re.sub(r"[^a-zA-Z0-9\s]", " ", text).split()
    return [w.lower() for w in words if len(w) >= 3 and not w.isdigit()]


def _is_generic_phrase(phrase: str) -> bool:
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

    for _, phrase in all_ngrams[:5]:
        if not _is_generic_phrase(phrase):
            selected.append(phrase)
            break

    if n >= 4:
        selected.append(all_ngrams[n // 4][1])
    if n >= 2:
        selected.append(all_ngrams[n // 2][1])
    if n >= 4:
        selected.append(all_ngrams[(3 * n) // 4][1])

    for _, phrase in reversed(all_ngrams[-5:]):
        if not _is_generic_phrase(phrase):
            selected.append(phrase)
            break

    seed = hash(text[:300]) % (2**32)
    rng = random.Random(seed)
    for idx in rng.sample(range(n), min(3, n)):
        selected.append(all_ngrams[idx][1])

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

    Builds longer keyword phrases (no quotes) from different document sections,
    which Google can use to find partially-matching pages.
    """
    words = text.split()
    if len(words) < MIN_QUERY_WORDS:
        return []

    queries = []

    # Strategy: 12-word slices from beginning, 1/4, middle, 3/4, end
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

    # Seeded random slice for reproducibility
    seed = hash(text[:200])
    rng = random.Random(seed)
    start = rng.randint(0, max(0, len(words) - 12))
    q = " ".join(words[start:start + 12]).strip()
    if q and q not in queries:
        queries.append(q)

    return queries[:max_queries]


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE SEARCH API
# ─────────────────────────────────────────────────────────────────────────────

def _do_google_search(query: str, num: int = 5) -> List[str]:
    """Execute a single Google Custom Search API query. Returns list of URLs."""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
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
        if r.status_code != 200:
            logger.warning("Google Search API error %d for query: %s", r.status_code, query[:80])
            return []
        items = r.json().get("items", [])
        return [item.get("link") for item in items if item.get("link")]
    except Exception as e:
        logger.warning("Google Search request failed: %s", e)
        return []


def _collect_urls(queries: List[str], label: str = "") -> List[str]:
    """
    Run a list of queries through Google Search, collect unique URLs.
    Stops once MAX_RESULTS is reached.
    """
    collected: List[str] = []
    for query in queries:
        urls = _do_google_search(query, num=5)
        for url in urls:
            if url and url not in collected:
                collected.append(url)
        time.sleep(random.uniform(*REQUEST_DELAY_RANGE))
        if len(collected) >= MAX_RESULTS:
            break

    if collected:
        logger.info("Google Search [%s]: %d URLs found", label or "query", len(collected))
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
# MAIN — WITH 3-TIER FALLBACK
# ─────────────────────────────────────────────────────────────────────────────

def google_search_with_matches(text: str) -> Dict:
    """
    Full verbatim search pipeline with 3-tier fallback.

    Tier 1 — Quoted verbatim n-grams (most precise):
      "exact phrase here" → Google exact-phrase match
      Best for well-indexed sources (Wikipedia, journals, news)

    Tier 2 — Broad keyword queries (fallback for poorly-indexed sources):
      key phrase without quotes → Google keyword match
      Catches content from government sites, regional portals
      (e.g. tgpsc.gov.in) that rarely appear in phrase searches

    Tier 3 — Legacy slices (last resort):
      Raw 12-word slices from beginning/middle/end
      Very broad, maximises URL discovery

    Once URLs are collected (from whichever tier succeeds), ALL URLs
    go through the same verbatim scrape-and-match pipeline.

    Returns:
    {
        "urls":          [...],        # All unique URLs found (sorted by match%)
        "matches":       {...},        # Per-URL: match_pct, scraped, etc.
        "top_match_pct": 12.3,        # Highest verbatim match across all URLs
        "queries_used":  [...],        # Queries that found results
        "tier_used":     "verbatim",  # Which tier produced results
    }
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        logger.warning("Google Search skipped — API key or CSE ID not set")
        return _empty_result()

    collected_urls: List[str] = []
    queries_used: List[str]   = []
    tier_used = "none"

    # ── TIER 1: Quoted verbatim n-gram queries ────────────────────────────
    verbatim_queries = build_verbatim_queries(text)
    if verbatim_queries:
        collected_urls = _collect_urls(verbatim_queries, label="verbatim")
        if collected_urls:
            queries_used = verbatim_queries
            tier_used    = "verbatim"
            logger.info("Tier 1 (verbatim) succeeded: %d URLs", len(collected_urls))

    # ── TIER 2: Broad keyword queries (no quotes) ─────────────────────────
    # Triggered when verbatim returns 0 — catches govt/regional sites
    if not collected_urls:
        logger.info(
            "Tier 1 (verbatim) returned 0 URLs — trying Tier 2 (broad keyword)"
        )
        broad_queries = build_broad_queries(text)
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
        words = text.split()
        legacy_queries = []

        if len(words) >= MIN_QUERY_WORDS:
            seed = hash(text[:200])
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
        logger.info(
            "All 3 query tiers returned 0 URLs — "
            "source may not be publicly indexed (e.g. intranet, low-SEO govt site)"
        )
        return _empty_result(queries_used=verbatim_queries)

    # ── Scrape + verbatim match ───────────────────────────────────────────
    matches, top_match_pct = _scrape_and_match(text, collected_urls)

    # Sort by match % descending
    sorted_urls = sorted(
        collected_urls,
        key=lambda u: matches.get(u, {}).get("match_pct", 0.0),
        reverse=True,
    )

    logger.info(
        "Search complete | tier=%s | urls=%d | top_match=%.1f%%",
        tier_used, len(sorted_urls), top_match_pct,
    )

    return {
        "urls":          sorted_urls,
        "matches":       matches,
        "top_match_pct": round(top_match_pct, 2),
        "queries_used":  queries_used,
        "tier_used":     tier_used,
    }


def _empty_result(queries_used: Optional[List[str]] = None) -> Dict:
    return {
        "urls":          [],
        "matches":       {},
        "top_match_pct": 0.0,
        "queries_used":  queries_used or [],
        "tier_used":     "none",
    }


# ─────────────────────────────────────────────────────────────────────────────
# BACKWARD-COMPATIBLE PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def google_search(text: str) -> List[str]:
    """
    Backward-compatible API — returns list of URLs only.
    Internally uses the full 3-tier pipeline.
    """
    result = google_search_with_matches(text)
    return result.get("urls", [])