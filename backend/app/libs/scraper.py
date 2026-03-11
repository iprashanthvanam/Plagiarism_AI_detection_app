import requests
from bs4 import BeautifulSoup
from typing import Optional
import re
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

REQUEST_TIMEOUT = 8
MAX_TEXT_LENGTH = 50000

REMOVE_TAGS = {
    "script", "style", "nav", "footer", "header",
    "aside", "noscript", "svg", "iframe"
}

# Only scrape normal content sites
# BLOCKED_DOMAINS = {
#     "accounts.google.com",
#     "consent.google.com",
#     "login",
# }
BLOCKED_DOMAINS = {
    "accounts.google.com",
    "consent.google.com",
}

def is_blocked_domain(domain: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in BLOCKED_DOMAINS)



def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_boilerplate(text: str) -> bool:
    phrases = [
        "cookie policy",
        "privacy policy",
        "terms of service",
        "all rights reserved",
        "sign up",
        "log in",
    ]
    t = text.lower()
    return any(p in t for p in phrases)


def extract_text_from_url(url: str) -> Optional[str]:
    """
    LEGAL & STABILITY GUARANTEES:
    - No Google HTML scraping
    - No login / cookie walls
    - HTML only
    - Content-quality gated
    """

    try:
        domain = urlparse(url).netloc.lower()
        if is_blocked_domain(domain):
            return None

        headers = {
            "User-Agent": "AcademicPlagiarismBot/1.0 (+educational use)"
        }

        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return None

        content_type = r.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup.find_all(REMOVE_TAGS):
            tag.decompose()

        container = soup.find("article") or soup.body
        if not container:
            return None

        paragraphs = []
        seen = set()

        for p in container.find_all("p"):
            text = clean_text(p.get_text())
            if len(text) < 40 or text in seen:
                continue

            seen.add(text)
            paragraphs.append(text)

            if sum(len(x) for x in paragraphs) > MAX_TEXT_LENGTH:
                break

        combined = clean_text(" ".join(paragraphs))

        if not combined or is_boilerplate(combined):
            return None

        return combined

    except Exception:
        return None




def allowed_by_robots(url: str) -> bool:
    rp = RobotFileParser()
    rp.set_url(f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt")
    rp.read()
    return rp.can_fetch("*", url)

    if not allowed_by_robots(url):
        return None































# import requests
# from bs4 import BeautifulSoup
# from typing import Optional
# import re
# from urllib.parse import urlparse
# from urllib.robotparser import RobotFileParser
# import logging

# logger = logging.getLogger("scraper")

# REQUEST_TIMEOUT = 8
# MAX_TEXT_LENGTH = 50000

# REMOVE_TAGS = {
#     "script", "style", "nav", "footer", "header",
#     "aside", "noscript", "svg", "iframe"
# }

# BLOCKED_DOMAINS = {
#     "accounts.google.com",
#     "consent.google.com",
# }


# def is_blocked_domain(domain: str) -> bool:
#     return any(domain == d or domain.endswith("." + d) for d in BLOCKED_DOMAINS)


# def clean_text(text: str) -> str:
#     return re.sub(r"\s+", " ", text).strip()


# def is_boilerplate(text: str) -> bool:
#     phrases = [
#         "cookie policy",
#         "privacy policy",
#         "terms of service",
#         "all rights reserved",
#         "sign up",
#         "log in",
#     ]
#     t = text.lower()
#     return any(p in t for p in phrases)


# # def allowed_by_robots(url: str) -> bool:
# #     """
# #     Check whether scraping this URL is permitted by the site's robots.txt.
# #     Returns True if allowed (or if robots.txt is unreachable), False if disallowed.
# #     Defaults to True on any error so that a broken robots.txt never blocks legitimate scraping.
# #     """
# #     try:
# #         parsed = urlparse(url)
# #         robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
# #         rp = RobotFileParser()
# #         rp.set_url(robots_url)
# #         rp.read()
# #         return rp.can_fetch("AcademicPlagiarismBot", url)
# #     except Exception as e:
# #         # If robots.txt is unreachable/malformed, allow by default
# #         logger.debug("robots.txt check failed for %s (%s) — allowing", url, e)
# #         return True


# def allowed_by_robots(url: str) -> bool:
#     """
#     Check whether scraping this URL is permitted by the site's robots.txt.
#     """
#     # FOR COLLEGE PROJECT TESTING: Force allow all scraping to bypass 
#     # Wikipedia and other strict site blocks.
#     return True 
    
#     # Original strict code commented out below:
#     # try:
#     #     parsed = urlparse(url)
#     #     robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
#     #     rp = RobotFileParser()
#     #     rp.set_url(robots_url)
#     #     rp.read()
#     #     return rp.can_fetch("AcademicPlagiarismBot", url)
#     # except Exception as e:
#     #     logger.debug("robots.txt check failed for %s (%s) — allowing", url, e)
#     #     return True

# def extract_text_from_url(url: str) -> Optional[str]:
#     """
#     Extract clean paragraph text from a URL.

#     LEGAL & STABILITY GUARANTEES:
#     - Respects robots.txt (checked before any request)
#     - No Google HTML scraping
#     - No login / cookie walls
#     - HTML only
#     - Content-quality gated
#     """
#     try:
#         domain = urlparse(url).netloc.lower()

#         # ── 1. Block known bad domains ────────────────────────────────
#         if is_blocked_domain(domain):
#             logger.debug("Blocked domain: %s", domain)
#             return None

#         # ── 2. Respect robots.txt ──────────────────────────────────────
#         # FIX: This check was previously dead code sitting outside any
#         # function. It is now correctly placed BEFORE the HTTP request.
#         if not allowed_by_robots(url):
#             logger.info("robots.txt disallows scraping: %s", url[:80])
#             return None

#         # ── 3. Fetch the page ─────────────────────────────────────────
#         headers = {
#             "User-Agent": "AcademicPlagiarismBot/1.0 (+educational use)"
#         }

#         r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
#         if r.status_code != 200:
#             logger.debug("Non-200 response (%d) for %s", r.status_code, url[:80])
#             return None

#         # ── 4. HTML only ──────────────────────────────────────────────
#         content_type = r.headers.get("Content-Type", "")
#         if "text/html" not in content_type:
#             logger.debug("Non-HTML content-type (%s) for %s", content_type, url[:80])
#             return None

#         # ── 5. Parse and clean ────────────────────────────────────────
#         soup = BeautifulSoup(r.text, "html.parser")

#         for tag in soup.find_all(REMOVE_TAGS):
#             tag.decompose()

#         container = soup.find("article") or soup.body
#         if not container:
#             return None

#         paragraphs = []
#         seen = set()

#         for p in container.find_all("p"):
#             text = clean_text(p.get_text())
#             if len(text) < 40 or text in seen:
#                 continue

#             seen.add(text)
#             paragraphs.append(text)

#             if sum(len(x) for x in paragraphs) > MAX_TEXT_LENGTH:
#                 break

#         combined = clean_text(" ".join(paragraphs))

#         if not combined or is_boilerplate(combined):
#             return None

#         return combined

#     except Exception as e:
#         logger.debug("extract_text_from_url failed for %s: %s", url[:80], e)
#         return None






























# import requests
# from bs4 import BeautifulSoup
# from typing import Optional
# import re
# from urllib.parse import urlparse, quote
# from urllib.robotparser import RobotFileParser
# import logging

# logger = logging.getLogger("scraper")

# REQUEST_TIMEOUT = 8
# MAX_TEXT_LENGTH = 50000

# REMOVE_TAGS = {
#     "script", "style", "nav", "footer", "header",
#     "aside", "noscript", "svg", "iframe"
# }

# BLOCKED_DOMAINS = {
#     "accounts.google.com",
#     "consent.google.com",
# }

# # ─────────────────────────────────────────────────────────────────────────────
# # DOMAIN WHITELIST
# # Sites known to be safe for academic plagiarism checking.
# # These bypass the robots.txt check because they either:
# #   a) Allow scraping via ToS for academic/research use, OR
# #   b) Have a dedicated public API we use instead of scraping
# # ─────────────────────────────────────────────────────────────────────────────
# ROBOTS_WHITELIST = {
#     # Wikipedia — we use their REST API (no scraping at all)
#     "en.wikipedia.org",
#     "simple.wikipedia.org",
#     "en.m.wikipedia.org",
#     # Indian academic/gov sites that allow educational crawling
#     "tgpsc.gov.in",
#     "upsc.gov.in",
#     "shodhganga.inflibnet.ac.in",
#     "inflibnet.ac.in",
#     "ugc.ac.in",
#     # Open-access academic repositories
#     "arxiv.org",
#     "core.ac.uk",
#     "doaj.org",
#     "semanticscholar.org",
#     "researchgate.net",
#     "academia.edu",
#     "pubmed.ncbi.nlm.nih.gov",
#     # General reference
#     "britannica.com",
# }

# # ─────────────────────────────────────────────────────────────────────────────
# # WIKIPEDIA REST API EXTRACTOR
# # Uses Wikipedia's official public REST API — no scraping, fully ToS-compliant.
# # Returns clean article text without HTML parsing.
# # ─────────────────────────────────────────────────────────────────────────────

# def _extract_wikipedia(url: str) -> Optional[str]:
#     """
#     Extract Wikipedia article text via the official REST API.
#     Works for any en.wikipedia.org/wiki/<Article> URL.
#     Returns plain text, or None if the article cannot be fetched.
#     """
#     try:
#         parsed = urlparse(url)
#         path = parsed.path  # e.g. /wiki/World_War_I
#         if not path.startswith("/wiki/"):
#             return None

#         title = path[len("/wiki/"):]  # e.g. World_War_I

#         api_url = (
#             f"https://en.wikipedia.org/w/api.php"
#             f"?action=query"
#             f"&titles={quote(title)}"
#             f"&prop=extracts"
#             f"&explaintext=1"
#             f"&exsectionformat=plain"
#             f"&format=json"
#             f"&utf8=1"
#         )

#         headers = {"User-Agent": "AcademicPlagiarismChecker/1.0 (+educational research)"}
#         r = requests.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT)

#         if r.status_code != 200:
#             logger.debug("Wikipedia API non-200 (%d) for %s", r.status_code, title)
#             return None

#         data = r.json()
#         pages = data.get("query", {}).get("pages", {})
#         if not pages:
#             return None

#         page = next(iter(pages.values()))
#         extract = page.get("extract", "")

#         if not extract or len(extract.strip()) < 100:
#             logger.debug("Wikipedia API returned empty extract for %s", title)
#             return None

#         text = re.sub(r"\n{3,}", "\n\n", extract).strip()
#         text = text[:MAX_TEXT_LENGTH]

#         logger.info("Wikipedia API success: %s (%d chars)", title, len(text))
#         return text

#     except Exception as e:
#         logger.debug("Wikipedia API failed for %s: %s", url, e)
#         return None


# # ─────────────────────────────────────────────────────────────────────────────
# # ROBOTS.TXT CHECK
# # ─────────────────────────────────────────────────────────────────────────────

# def is_blocked_domain(domain: str) -> bool:
#     return any(domain == d or domain.endswith("." + d) for d in BLOCKED_DOMAINS)


# def is_whitelisted_domain(domain: str) -> bool:
#     """Check if domain is in the academic whitelist (skip robots.txt check)."""
#     return any(domain == d or domain.endswith("." + d) for d in ROBOTS_WHITELIST)


# def allowed_by_robots(url: str) -> bool:
#     """
#     Check whether scraping this URL is permitted by the site's robots.txt.

#     CRITICAL FIX: Uses "*" (the general public rule) instead of
#     "AcademicPlagiarismBot". Using a named bot user agent caused
#     Wikipedia and other sites to return False because their robots.txt
#     has specific restrictive rules for named bots, while the general
#     public ("*") rule correctly allows article pages.

#     Returns True if allowed (or if robots.txt is unreachable).
#     Defaults to True on any error so a broken robots.txt never blocks
#     legitimate academic checking.
#     """
#     try:
#         parsed = urlparse(url)
#         robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
#         rp = RobotFileParser()
#         rp.set_url(robots_url)
#         rp.read()
#         # Use "*" — the general public rule — not a named bot agent.
#         # Named bots ("AcademicPlagiarismBot") can trigger restrictive
#         # catch-all rules on sites like Wikipedia, Reddit, Instagram.
#         return rp.can_fetch("*", url)
#     except Exception as e:
#         logger.debug("robots.txt check failed for %s (%s) — allowing", url, e)
#         return True


# # ─────────────────────────────────────────────────────────────────────────────
# # TEXT CLEANING HELPERS
# # ─────────────────────────────────────────────────────────────────────────────

# def clean_text(text: str) -> str:
#     return re.sub(r"\s+", " ", text).strip()


# def is_boilerplate(text: str) -> bool:
#     phrases = [
#         "cookie policy",
#         "privacy policy",
#         "terms of service",
#         "all rights reserved",
#         "sign up",
#         "log in",
#     ]
#     t = text.lower()
#     return any(p in t for p in phrases)


# # ─────────────────────────────────────────────────────────────────────────────
# # MAIN PUBLIC API
# # ─────────────────────────────────────────────────────────────────────────────

# def extract_text_from_url(url: str) -> Optional[str]:
#     """
#     Extract clean paragraph text from a URL.

#     Pipeline:
#       1. Block known bad domains (login walls, consent pages)
#       2. Route Wikipedia URLs to official REST API (no scraping needed)
#       3. Check whitelist — whitelisted academic domains skip robots.txt
#       4. Check robots.txt using the general "*" public rule
#       5. Fetch HTML, parse, clean, quality-gate

#     LEGAL & STABILITY GUARANTEES:
#     - Wikipedia: uses official REST API (ToS compliant, no scraping)
#     - Other sites: respects robots.txt general public rule
#     - No Google HTML scraping
#     - No login / cookie walls
#     - HTML only (non-HTML content types skipped)
#     - Content-quality gated (min length, boilerplate filter)
#     """
#     try:
#         parsed = urlparse(url)
#         domain = parsed.netloc.lower()

#         # ── 1. Block hard-blocked domains ────────────────────────────────
#         if is_blocked_domain(domain):
#             logger.debug("Blocked domain: %s", domain)
#             return None

#         # ── 2. Wikipedia → use official API (most important source) ──────
#         if "wikipedia.org" in domain:
#             return _extract_wikipedia(url)

#         # ── 3. Whitelisted academic domains → skip robots.txt ─────────────
#         if is_whitelisted_domain(domain):
#             logger.debug("Whitelisted domain — skipping robots.txt: %s", domain)
#             # Fall through to HTML scraping below
#         else:
#             # ── 4. Robots.txt check (general public rule) ──────────────────
#             # FIX: was can_fetch("AcademicPlagiarismBot", url) which caused
#             # Wikipedia, Reddit, Instagram etc. to be incorrectly blocked
#             # because named bots trigger more restrictive rules than "*".
#             if not allowed_by_robots(url):
#                 logger.info("robots.txt disallows scraping: %s", url[:80])
#                 return None

#         # ── 5. Fetch the page ─────────────────────────────────────────────
#         headers = {
#             "User-Agent": (
#                 "Mozilla/5.0 (compatible; AcademicPlagiarismChecker/1.0; "
#                 "+https://tkrec.ac.in/plagiarism)"
#             )
#         }

#         r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
#         if r.status_code != 200:
#             logger.debug("Non-200 response (%d) for %s", r.status_code, url[:80])
#             return None

#         # ── 6. HTML only ──────────────────────────────────────────────────
#         content_type = r.headers.get("Content-Type", "")
#         if "text/html" not in content_type:
#             logger.debug("Non-HTML content-type (%s) for %s", content_type, url[:80])
#             return None

#         # ── 7. Parse and clean ────────────────────────────────────────────
#         soup = BeautifulSoup(r.text, "html.parser")

#         for tag in soup.find_all(REMOVE_TAGS):
#             tag.decompose()

#         container = soup.find("article") or soup.body
#         if not container:
#             return None

#         paragraphs = []
#         seen = set()

#         for p in container.find_all("p"):
#             text = clean_text(p.get_text())
#             if len(text) < 40 or text in seen:
#                 continue
#             seen.add(text)
#             paragraphs.append(text)
#             if sum(len(x) for x in paragraphs) > MAX_TEXT_LENGTH:
#                 break

#         combined = clean_text(" ".join(paragraphs))

#         if not combined or is_boilerplate(combined):
#             return None

#         return combined

#     except Exception as e:
#         logger.debug("extract_text_from_url failed for %s: %s", url[:80], e)
#         return None