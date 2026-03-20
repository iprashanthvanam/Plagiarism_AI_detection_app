"""
Common Crawl Index API — Fallback plagiarism detection when Google quota exhausted.

Common Crawl does NOT support direct text search. We use a workaround:
1. Extract broad keyword phrases from document
2. Query CDX API for those phrases (URL-based search)
3. Fetch matched pages from Common Crawl archive
4. Check if our document text appears in those pages
5. Return URLs with match percentages (same format as Google Search)

⚠️ IMPORTANT: This is significantly slower than Google (~2-5 seconds per phrase)
because we must:
- Query CDX index
- Fetch full page content from archive
- Run similarity check on each page

Use ONLY as fallback when Google quota exhausted.
"""

import requests
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import quote_plus
import time

logger = logging.getLogger("commoncrawl")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

CDX_API_URL = "https://index.commoncrawl.org/CC-MAIN-2024-18-index"  # Latest crawl
REQUEST_TIMEOUT = 10
MAX_CDX_RESULTS = 20  # Max URLs per CDX query
MAX_CC_FETCHES = 5    # Max Common Crawl pages to fetch (rate limit)
MATCH_THRESHOLD = 0.15  # 15% similarity = match

# Retry logic
MAX_RETRIES = 2
RETRY_DELAY = 1  # seconds


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_query(text: str) -> List[str]:
    """Extract broad search phrases from text (similar to Google fallback queries)."""
    words = text.lower().split()
    if len(words) < 10:
        return [" ".join(words)]  # Too short — return as-is
    
    phrases = []
    
    # Strategy 1: First 15 words
    phrases.append(" ".join(words[:15]))
    
    # Strategy 2: Middle 15 words
    if len(words) > 30:
        mid = len(words) // 2
        phrases.append(" ".join(words[mid:mid+15]))
    
    # Strategy 3: Last 15 words
    if len(words) > 15:
        phrases.append(" ".join(words[-15:]))
    
    # Deduplicate
    return list(dict.fromkeys(phrases))


def _query_cdx(query: str, retry: int = 0) -> List[str]:
    """
    Query Common Crawl CDX Index for URLs matching a phrase.
    
    ⚠️ NOTE: CDX does NOT do text search. We query URL patterns instead.
    This returns all URLs from CDX containing the keyword pattern.
    
    Returns:
        List of URLs from Common Crawl
    """
    if retry > MAX_RETRIES:
        logger.warning("CDX query exceeded max retries for query: %s", query[:80])
        return []
    
    try:
        # URL-encoded query (CDX searches URL patterns, not page text)
        params = {
            "url": f"*{quote_plus(query.split()[0])}*",  # Search first keyword in URLs
            "output": "json",
            "filter": "statuscode:200",  # Only successful pages
            "collapse": "urlkey",  # Deduplicate
            "limit": MAX_CDX_RESULTS,
        }
        
        logger.debug("CDX query: %s with params %s", CDX_API_URL, params)
        
        response = requests.get(
            CDX_API_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        
        if response.status_code == 429:
            # Rate limited — back off and retry
            logger.warning("CDX rate limited — backing off")
            time.sleep(RETRY_DELAY * (retry + 1))
            return _query_cdx(query, retry + 1)
        
        if response.status_code != 200:
            logger.debug("CDX query failed (%d): %s", response.status_code, query[:80])
            return []
        
        data = response.json()
        
        # CDX response format: [["timestamp", "original", "statuscode", ...], ...]
        # Skip header row (first element)
        if not isinstance(data, list) or len(data) < 2:
            logger.debug("CDX returned empty result for query: %s", query[:80])
            return []
        
        urls = []
        for row in data[1:]:  # Skip header
            if len(row) >= 2:
                original_url = row[1]  # "original" field
                urls.append(original_url)
        
        logger.info("CDX query found %d URLs for: %s", len(urls), query[:80])
        return urls
    
    except requests.exceptions.Timeout:
        logger.warning("CDX timeout — backing off and retrying")
        time.sleep(RETRY_DELAY)
        return _query_cdx(query, retry + 1)
    
    except Exception as e:
        logger.error("CDX query error: %s", e)
        return []


def _fetch_from_commoncrawl(url: str) -> Optional[str]:
    """
    Fetch a page from Common Crawl archive.
    
    Common Crawl provides access to archived pages via:
    https://web.archive.org/web/<timestamp>/<url>
    
    But for programmatic access, we use:
    https://commoncrawl.s3.amazonaws.com/<warc-path>
    
    ⚠️ LIMITATION: We don't have the exact WARC path, so we use web.archive.org
    which is slower but doesn't require Common Crawl S3 access.
    
    Args:
        url: Original URL to fetch from archive
    
    Returns:
        Page text, or None if fetch failed
    """
    try:
        # Use web.archive.org as fallback (simpler, no S3 credentials needed)
        # Format: https://web.archive.org/web/<timestamp>/<url>
        # We'll use latest snapshot (no timestamp = latest)
        archive_url = f"https://web.archive.org/web/{url}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Academic Research Bot)"
        }
        
        response = requests.get(
            archive_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        
        if response.status_code != 200:
            logger.debug("Archive.org fetch failed (%d): %s", response.status_code, url[:80])
            return None
        
        # Parse HTML and extract text (similar to scraper.py)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Remove script/style
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)
        
        if len(text.strip()) > 100:
            logger.debug("Archive.org fetch success: %s (%d chars)", url[:80], len(text))
            return text
        
        logger.debug("Archive.org fetch returned empty text: %s", url[:80])
        return None
    
    except requests.exceptions.Timeout:
        logger.debug("Archive.org timeout: %s", url[:80])
        return None
    
    except Exception as e:
        logger.debug("Archive.org fetch error for %s: %s", url[:80], e)
        return None


def _text_similarity(source: str, target: str) -> float:
    """
    Quick similarity check using n-gram overlap.
    Returns percentage (0-100).
    
    ⚠️ FAST but less accurate than ensemble plagiarism score.
    Used only for filtering Common Crawl results.
    """
    if not source or not target:
        return 0.0
    
    # Simple n-gram overlap (word bigrams)
    src_words = source.lower().split()
    tgt_words = target.lower().split()
    
    if len(src_words) < 5 or len(tgt_words) < 5:
        return 0.0
    
    # Build bigrams
    src_bigrams = set(
        f"{src_words[i]} {src_words[i+1]}"
        for i in range(len(src_words) - 1)
    )
    
    tgt_bigrams = set(
        f"{tgt_words[i]} {tgt_words[i+1]}"
        for i in range(len(tgt_words) - 1)
    )
    
    if not src_bigrams or not tgt_bigrams:
        return 0.0
    
    overlap = len(src_bigrams & tgt_bigrams)
    union = len(src_bigrams | tgt_bigrams)
    
    similarity = (overlap / union) * 100 if union > 0 else 0.0
    return round(min(similarity, 100.0), 2)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — Mimics google_search_with_matches() format
# ─────────────────────────────────────────────────────────────────────────────

def commoncrawl_search_with_matches(text: str) -> Dict:
    """
    Search Common Crawl for pages matching document text.
    
    Returns same format as google_search_with_matches():
    {
        "urls": [...],
        "matches": {url: {match_pct, scraped, ...}, ...},
        "top_match_pct": 15.3,
        "queries_used": [...],
        "tier_used": "commoncrawl",
        "windows_searched": 0,
    }
    
    ⚠️ PERFORMANCE WARNING:
    - Each CDX query: ~0.5s
    - Each page fetch: ~2-3s
    - Total time: ~10-20s for full analysis
    
    Use ONLY as fallback.
    """
    
    if not text or len(text.split()) < 20:
        logger.warning("Text too short for Common Crawl search")
        return {
            "urls": [],
            "matches": {},
            "top_match_pct": 0.0,
            "queries_used": [],
            "tier_used": "commoncrawl",
        }
    
    logger.info("Starting Common Crawl fallback search")
    
    # Step 1: Generate search queries
    queries = _normalize_query(text)
    logger.info("Generated %d Common Crawl queries", len(queries))
    
    all_urls = set()
    all_matches: Dict[str, Dict] = {}
    top_match_pct = 0.0
    fetches_done = 0
    
    # Step 2: Query CDX for each phrase
    for query in queries:
        if fetches_done >= MAX_CC_FETCHES:
            logger.info("Reached max Common Crawl fetches limit (%d)", MAX_CC_FETCHES)
            break
        
        logger.debug("CDX query: %s", query[:80])
        cdx_urls = _query_cdx(query)
        
        if not cdx_urls:
            logger.debug("CDX returned no URLs for: %s", query[:80])
            continue
        
        all_urls.update(cdx_urls)
    
    # Step 3: Fetch and match pages from Common Crawl
    logger.info("Fetching content from %d Common Crawl URLs", len(all_urls))
    
    for url in list(all_urls)[:MAX_CC_FETCHES]:
        try:
            logger.debug("Fetching from Common Crawl: %s", url[:80])
            page_text = _fetch_from_commoncrawl(url)
            
            if not page_text:
                all_matches[url] = {
                    "match_pct": 0.0,
                    "scraped": False,
                    "scraped_text_length": 0,
                    "source": "commoncrawl",
                }
                continue
            
            # Check similarity
            match_pct = _text_similarity(text, page_text)
            
            all_matches[url] = {
                "match_pct": match_pct,
                "scraped": True,
                "scraped_text_length": len(page_text),
                "source": "commoncrawl",
            }
            
            if match_pct > top_match_pct:
                top_match_pct = match_pct
            
            logger.debug("Common Crawl match: %s → %.1f%%", url[:80], match_pct)
            fetches_done += 1
        
        except Exception as e:
            logger.warning("Error fetching from Common Crawl: %s", e)
            all_matches[url] = {
                "match_pct": 0.0,
                "scraped": False,
                "scraped_text_length": 0,
                "source": "commoncrawl",
                "error": str(e),
            }
    
    # Step 4: Sort by match % and return
    sorted_urls = sorted(
        all_urls,
        key=lambda u: all_matches.get(u, {}).get("match_pct", 0.0),
        reverse=True,
    )
    
    logger.info(
        "Common Crawl search complete | urls=%d | top_match=%.1f%%",
        len(sorted_urls), top_match_pct
    )
    
    return {
        "urls": sorted_urls,
        "matches": all_matches,
        "top_match_pct": round(top_match_pct, 2),
        "queries_used": queries,
        "tier_used": "commoncrawl",
        "windows_searched": 0,
    }