# import requests
# from newspaper import Article

# def extract_text_from_url(url):
#     try:
#         article = Article(url)
#         article.download()
#         article.parse()
#         return article.text
#     except Exception as e:
#         # fallback, simple requests + bs4
#         try:
#             from bs4 import BeautifulSoup
#             resp = requests.get(url, timeout=5)
#             soup = BeautifulSoup(resp.content, 'html.parser')
#             texts = [p.get_text() for p in soup.find_all('p')]
#             return "\n".join(texts)
#         except Exception:
#             return ""































# # backend/app/libs/scraper.py

# import requests
# from bs4 import BeautifulSoup
# from typing import Optional
# import re


# # =========================
# # CONFIG
# # =========================

# REQUEST_TIMEOUT = 8
# MIN_TEXT_LENGTH = 0        # below this → ignore page
# MAX_TEXT_LENGTH = 50000      # avoid massive boilerplate
# REMOVE_TAGS = {
#     "script", "style", "nav", "footer", "header",
#     "aside", "noscript", "svg", "iframe"
# }


# # =========================
# # HELPERS
# # =========================

# def clean_text(text: str) -> str:
#     """Normalize whitespace and remove junk."""
#     text = re.sub(r"\s+", " ", text)
#     return text.strip()


# def is_boilerplate(text: str) -> bool:
#     """Detect common boilerplate-only pages."""
#     boilerplate_phrases = [
#         "cookie policy",
#         "privacy policy",
#         "accept cookies",
#         "all rights reserved",
#         "terms of service",
#         "sign up",
#         "log in",
#     ]
#     lowered = text.lower()
#     return any(p in lowered for p in boilerplate_phrases)


# # =========================
# # MAIN SCRAPER
# # =========================

# def extract_text_from_url(url: str) -> Optional[str]:
#     """
#     Extract meaningful article text from a webpage.

#     ✔ Removes boilerplate
#     ✔ Ignores short / empty pages
#     ✔ Prevents repeated paragraphs
#     ✔ Avoids HTML noise inflating similarity
#     """

#     try:
#         headers = {
#             "User-Agent": (
#                 "Mozilla/5.0 (X11; Linux x86_64) "
#                 "AppleWebKit/537.36 "
#                 "(KHTML, like Gecko) "
#                 "Chrome/120.0 Safari/537.36"
#             )
#         }

#         response = requests.get(
#             url,
#             headers=headers,
#             timeout=REQUEST_TIMEOUT,
#         )

#         if response.status_code != 200:
#             return None

#         soup = BeautifulSoup(response.text, "html.parser")

#         # Remove junk tags
#         for tag in soup.find_all(REMOVE_TAGS):
#             tag.decompose()

#         # Prefer <article> if present
#         article = soup.find("article")
#         container = article if article else soup.body

#         if not container:
#             return None

#         paragraphs = []
#         seen = set()

#         for p in container.find_all("p"):
#             text = clean_text(p.get_text())

#             if len(text) < 40:
#                 continue

#             if text in seen:
#                 continue

#             seen.add(text)
#             paragraphs.append(text)

#             # Hard stop to avoid boilerplate dominance
#             if sum(len(x) for x in paragraphs) > MAX_TEXT_LENGTH:
#                 break

#         combined = clean_text(" ".join(paragraphs))

#         # Quality gates
#         if len(combined) < MIN_TEXT_LENGTH:
#             return None

#         if is_boilerplate(combined):
#             return None

#         return combined

#     except Exception:
#         return None

















# import requests
# from bs4 import BeautifulSoup
# from typing import Optional
# import re
# from urllib.parse import urlparse
# from urllib.robotparser import RobotFileParser

# REQUEST_TIMEOUT = 8
# MAX_TEXT_LENGTH = 50000

# REMOVE_TAGS = {
#     "script", "style", "nav", "footer", "header",
#     "aside", "noscript", "svg", "iframe"
# }

# # Only scrape normal content sites
# # BLOCKED_DOMAINS = {
# #     "accounts.google.com",
# #     "consent.google.com",
# #     "login",
# # }
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


# def extract_text_from_url(url: str) -> Optional[str]:
#     """
#     LEGAL & STABILITY GUARANTEES:
#     - No Google HTML scraping
#     - No login / cookie walls
#     - HTML only
#     - Content-quality gated
#     """

#     try:
#         domain = urlparse(url).netloc.lower()
#         if is_blocked_domain(domain):
#             return None

#         headers = {
#             "User-Agent": "AcademicPlagiarismBot/1.0 (+educational use)"
#         }

#         r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
#         if r.status_code != 200:
#             return None

#         content_type = r.headers.get("Content-Type", "")
#         if "text/html" not in content_type:
#             return None

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

#     except Exception:
#         return None




# def allowed_by_robots(url: str) -> bool:
#     rp = RobotFileParser()
#     rp.set_url(f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt")
#     rp.read()
#     return rp.can_fetch("*", url)

#     if not allowed_by_robots(url):
#         return None




###############################################################################################################above is imp
















# # backend/app/libs/scraper.py
# from typing import Optional
# import re
# import requests
# from bs4 import BeautifulSoup
# from urllib.parse import urlparse




# def extract_text_from_url(url: str) -> Optional[str]:
#     try:
#         domain = urlparse(url).netloc.lower()
#         if is_blocked_domain(domain):
#             return None

#         headers = {
#             "User-Agent": "AcademicPlagiarismBot/1.0 (+educational use)"
#         }

#         r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
#         if r.status_code != 200:
#             return None

#         content_type = r.headers.get("Content-Type", "").lower()
#         if "text/html" not in content_type:
#             return None

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

#     except Exception:
#         return None






























# import requests
# from bs4 import BeautifulSoup
# from typing import Optional
# import re
# from urllib.parse import urlparse

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


# def extract_text_from_url(url: str) -> Optional[str]:
#     """
#     LEGAL & STABILITY GUARANTEES:
#     - No Google HTML scraping
#     - HTML only
#     - Content-quality gated
#     """

#     try:
#         domain = urlparse(url).netloc.lower()
#         if is_blocked_domain(domain):
#             return None

#         headers = {
#             "User-Agent": "AcademicPlagiarismBot/1.0 (+educational use)"
#         }

#         r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
#         if r.status_code != 200:
#             return None

#         content_type = r.headers.get("Content-Type", "").lower()
#         if "text/html" not in content_type:
#             return None

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

#     except Exception:
#         return None

















































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