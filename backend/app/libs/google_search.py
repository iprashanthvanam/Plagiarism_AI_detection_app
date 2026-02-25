

# import requests
# from app.env import GOOGLE_API_KEY, GOOGLE_CSE_ID
# import re 

# def google_search(query, num_results=5):
#     # Gracefully skip if keys are missing
#     if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
#         print("[Google Search] Skipped — API key or CSE ID not set")
#         return []

#     # 1. AGGRESSIVE CLEANING: Keep only letters, numbers, and spaces.
#     cleaned_query = re.sub(r'[^a-zA-Z0-9\s]', '', query) # Remove all punctuation/symbols
#     cleaned_query = re.sub(r'\s+', ' ', cleaned_query).strip()
    
#     # Limit to first 15 words
#     words = cleaned_query.split()[:15]
#     final_query = " ".join(words)

#     if not final_query:
#          print("[Google Search] Skipped — Empty query after cleaning.")
#          return []

#     url = "https://www.googleapis.com/customsearch/v1"
#     params = {
#         "key": GOOGLE_API_KEY,
#         "cx": GOOGLE_CSE_ID,
#         "q": final_query, 
#         "num": num_results,
#     }

#     resp = requests.get(url, params=params)

#     if resp.status_code != 200:
#         # The exception now includes the specific query that failed
#         raise Exception(f"Google Search API error for query '{final_query}' ({resp.status_code}): {resp.text}")

#     search_results = resp.json().get("items", [])
#     return [item.get("link") for item in search_results]










# # backend/app/libs/google_search.py

# import os
# import time
# import random
# import requests
# from typing import List
# from urllib.parse import quote_plus

# from app.env import GOOGLE_API_KEY, GOOGLE_CSE_ID


# # =========================
# # CONFIG — SAFE DEFAULTS
# # =========================

# MAX_RESULTS = 8                  # Do NOT over-fetch
# MIN_QUERY_WORDS = 6              # Avoid generic queries
# REQUEST_TIMEOUT = 8
# REQUEST_DELAY_RANGE = (0.3, 0.8) # Rate-limit friendly


# # =========================
# # QUERY BUILDING
# # =========================

# def build_search_queries(text: str) -> List[str]:
#     """
#     Generate diversified queries from the document.
#     This prevents identical URLs for different files.
#     """

#     words = text.split()
#     if len(words) < MIN_QUERY_WORDS:
#         return []

#     queries = []

#     # Strategy 1: Beginning snippet
#     queries.append(" ".join(words[:12]))

#     # Strategy 2: Middle snippet
#     mid = len(words) // 2
#     queries.append(" ".join(words[mid:mid + 12]))

#     # Strategy 3: Ending snippet
#     queries.append(" ".join(words[-12:]))

#     # Strategy 4: Random slice (stabilized)
#     seed = hash(text[:200])
#     rng = random.Random(seed)
#     start = rng.randint(0, max(0, len(words) - 12))
#     queries.append(" ".join(words[start:start + 12]))

#     # Deduplicate
#     return list(dict.fromkeys(q.strip() for q in queries if q.strip()))


# # =========================
# # GOOGLE SEARCH
# # =========================

# def google_search(text: str) -> List[str]:
#     """
#     Perform diversified Google CSE search.

#     ✔ Different documents → different URLs
#     ✔ Prevents boilerplate domination
#     ✔ Avoids same-result syndrome
#     """

#     if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
#         return []

#     queries = build_search_queries(text)
#     if not queries:
#         return []

#     collected_urls: List[str] = []

#     for query in queries:
#         encoded = quote_plus(query)

#         url = (
#             "https://www.googleapis.com/customsearch/v1"
#             f"?key={GOOGLE_API_KEY}"
#             f"&cx={GOOGLE_CSE_ID}"
#             f"&q={encoded}"
#             f"&num=5"
#         )

#         try:
#             response = requests.get(url, timeout=REQUEST_TIMEOUT)
#             if response.status_code != 200:
#                 continue

#             data = response.json()
#             items = data.get("items", [])

#             for item in items:
#                 link = item.get("link")
#                 if link and link not in collected_urls:
#                     collected_urls.append(link)

#         except Exception:
#             continue

#         # Gentle rate limiting
#         time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

#         if len(collected_urls) >= MAX_RESULTS:
#             break

#     return collected_urls[:MAX_RESULTS]
















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


################################################################################## above is main imp










# # backend/app/libs/google_search.py

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




# def normalize_for_search(text: str, max_words: int = 120) -> str:
#     """
#     Normalizes extracted text for reliable Google search queries.
#     Removes numbers, short tokens, and symbols.
#     """
#     words = [
#         w for w in re.split(r"\W+", text.lower())
#         if len(w) > 3 and not w.isdigit()
#     ]
#     return " ".join(words[:max_words])






# def build_search_queries(text: str) -> List[str]:
#     words = text.split()
#     if len(words) < 10:
#         return []

#     queries = [
#         " ".join(words[:15]),
#         " ".join(words[len(words)//2 : len(words)//2 + 15]),
#         " ".join(words[-15:]),
#     ]

#     return list(dict.fromkeys(q for q in queries if len(q.split()) >= 6))





# def google_search(text: str) -> List[str]:
#     """
#     Uses Google Custom Search JSON API (ToS compliant)
#     Forces HTML results (not PDFs)
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
#             f"&fileType=html"
#             f"&excludeTerms=pdf doc ppt xls"
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















































# import time
# import random
# import requests
# import re
# from typing import List
# from urllib.parse import quote_plus

# from app.env import GOOGLE_API_KEY, GOOGLE_CSE_ID

# MAX_RESULTS = 8
# REQUEST_TIMEOUT = 8
# REQUEST_DELAY_RANGE = (0.4, 0.9)


# def normalize_for_search(text: str, max_words: int = 120) -> str:
#     words = [
#         w for w in re.split(r"\W+", text.lower())
#         if len(w) > 3 and not w.isdigit()
#     ]
#     return " ".join(words[:max_words])


# def google_search(text: str) -> List[str]:
#     if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
#         return []

#     query = normalize_for_search(text)
#     if len(query.split()) < 6:
#         return []

#     url = (
#         "https://www.googleapis.com/customsearch/v1"
#         f"?key={GOOGLE_API_KEY}"
#         f"&cx={GOOGLE_CSE_ID}"
#         f"&q={quote_plus(query)}"
#         f"&num=5"
#         f"&fileType=html"
#         f"&excludeTerms=pdf doc ppt xls"
#     )

#     try:
#         r = requests.get(url, timeout=REQUEST_TIMEOUT)
#         if r.status_code != 200:
#             return []

#         links = []
#         for item in r.json().get("items", []):
#             link = item.get("link")
#             if link and link not in links:
#                 links.append(link)

#         time.sleep(random.uniform(*REQUEST_DELAY_RANGE))
#         return links[:MAX_RESULTS]

#     except Exception:
#         return []



































 # backend/app/libs/google_search.py

import time
import random
import requests
from typing import List
from urllib.parse import quote_plus

from app.env import GOOGLE_API_KEY, GOOGLE_CSE_ID

MAX_RESULTS = 8
MIN_QUERY_WORDS = 6
REQUEST_TIMEOUT = 8
REQUEST_DELAY_RANGE = (0.3, 0.8)


def build_search_queries(text: str) -> List[str]:
    words = text.split()
    if len(words) < MIN_QUERY_WORDS:
        return []

    queries = [
        " ".join(words[:12]),
        " ".join(words[len(words)//2:len(words)//2 + 12]),
        " ".join(words[-12:]),
    ]

    seed = hash(text[:200])
    rng = random.Random(seed)
    start = rng.randint(0, max(0, len(words) - 12))
    queries.append(" ".join(words[start:start + 12]))

    return list(dict.fromkeys(q.strip() for q in queries if q.strip()))


def google_search(text: str) -> List[str]:
    """
    LEGAL NOTE:
    - Uses Google Custom Search JSON API
    - No HTML scraping
    - Fully ToS compliant
    """

    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []

    queries = build_search_queries(text)
    collected_urls: List[str] = []

    for query in queries:
        url = (
            "https://www.googleapis.com/customsearch/v1"
            f"?key={GOOGLE_API_KEY}"
            f"&cx={GOOGLE_CSE_ID}"
            f"&q={quote_plus(query)}"
            f"&num=5"
        )

        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                continue

            for item in r.json().get("items", []):
                link = item.get("link")
                if link and link not in collected_urls:
                    collected_urls.append(link)

        except Exception:
            continue

        time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

        if len(collected_urls) >= MAX_RESULTS:
            break

    return collected_urls[:MAX_RESULTS]