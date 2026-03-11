







# ## for scanned pdf only local, gemini not using 




# import os
# import re
# import logging
# import tempfile
# import shutil as _shutil
# from typing import Optional

# import pandas as pd
# import pdfplumber
# from docx import Document
# from pptx import Presentation

# logger = logging.getLogger(__name__)

# # ============================================================
# # LOCAL OCR IMPORTS (optional — graceful degradation)
# # ============================================================
# try:
#     import pytesseract
#     from PIL import Image
#     _tesseract_available = True
# except ImportError:
#     _tesseract_available = False
#     logger.warning("pytesseract/Pillow not installed — image OCR falls back to Gemini")

# try:
#     from pdf2image import convert_from_path
#     _pdf2image_available = True
# except ImportError:
#     _pdf2image_available = False
#     logger.warning("pdf2image not installed — scanned PDF OCR falls back to Gemini")

# # ============================================================
# # GEMINI FALLBACK IMPORT
# # ============================================================
# try:
#     from app.libs.gemini_service import extract_text_with_gemini
#     _gemini_available = True
# except Exception as e:
#     logger.warning("Gemini service unavailable: %s", e)
#     extract_text_with_gemini = None
#     _gemini_available = False

# # Minimum chars to consider local extraction successful
# MIN_LOCAL_TEXT = 10

# # Noise tokens found in .doc OLE metadata / font tables — filtered out
# _DOC_NOISE = {
#     "Times New Roman", "Liberation Serif", "Liberation Sans", "DejaVu Sans",
#     "Open Sans", "FreeSans", "OpenSymbol", "Arial Unicode MS", "Droid Sans",
#     "Fallback", "Symbol", "Arial", "Heading", "oasis.open", "office.com",
#     "Visited Internet Link", "Internet Link", "Root Entry", "WordDocument",
# }


# # ============================================================
# # LOCAL EXTRACTION HELPERS
# # ============================================================

# def _extract_doc_binary(file_path: str) -> str:
#     """
#     Extract body text from a legacy .doc (binary OLE / Word 97-2003) file.
#     No external tools — pure Python UTF-16LE scan of OLE binary.
#     """
#     try:
#         abs_path = os.path.abspath(file_path)
#         with open(abs_path, "rb") as f:
#             data = f.read()

#         chunks = re.findall(b"(?:[\x20-\x7e]\x00){8,}", data)

#         text_parts = []
#         for chunk in chunks:
#             try:
#                 decoded = chunk.decode("utf-16-le", errors="ignore").strip()
#             except Exception:
#                 continue
#             if len(decoded) < 15:
#                 continue
#             if any(noise in decoded for noise in _DOC_NOISE):
#                 continue
#             text_parts.append(decoded)

#         result = "\n".join(text_parts)
#         logger.info(
#             ".doc extracted via binary UTF-16LE scan: %s (%d chars)",
#             os.path.basename(file_path), len(result)
#         )
#         return result

#     except Exception as e:
#         logger.warning("Binary .doc extraction failed for %s: %s", file_path, e)
#         return ""


# def _extract_image_local(file_path: str) -> str:
#     if not _tesseract_available:
#         return ""
#     try:
#         img = Image.open(file_path)
#         text = pytesseract.image_to_string(img, timeout=30)
#         return text.strip()
#     except Exception as e:
#         logger.warning("Tesseract OCR failed for %s: %s", file_path, e)
#         return ""


# def _extract_scanned_pdf_local(file_path: str) -> str:
#     if not _pdf2image_available or not _tesseract_available:
#         return ""
#     try:
#         pages = convert_from_path(file_path, dpi=200, first_page=1, last_page=15)
#         texts = []
#         for i, page in enumerate(pages):
#             try:
#                 page_text = pytesseract.image_to_string(page, timeout=30)
#                 if page_text.strip():
#                     texts.append(page_text.strip())
#             except Exception as e:
#                 logger.warning("Tesseract failed on PDF page %d: %s", i + 1, e)
#         return "\n".join(texts)
#     except Exception as e:
#         logger.warning("pdf2image+tesseract failed for %s: %s", file_path, e)
#         return ""


# def _extract_spreadsheet(file_path: str, ext: str) -> str:
#     """
#     Extract readable text from XLS/XLSX without NaN artifacts.

#     ROOT CAUSE OF BUG: df.astype(str).to_string() converts every empty cell
#     to the literal string "NaN". This contaminated:
#       1. The extracted_text stored in the database
#       2. Google search queries (returning pandas/NaN tech pages)
#       3. TF-IDF similarity (inflating web plagiarism scores to ~100%)

#     FIX: Iterate each cell individually, skip pd.isna() cells and any cell
#     whose string representation is "nan" / "NaN" / empty. Join real values
#     with double-space separators to preserve the row structure readably.
#     """
#     try:
#         engine = "xlrd" if ext == ".xls" else "openpyxl"
#         dfs = pd.read_excel(file_path, sheet_name=None, engine=engine)

#         lines: list = []
#         for sheet_name, df in dfs.items():
#             if len(dfs) > 1:
#                 lines.append(f"[Sheet: {sheet_name}]")

#             for _, row in df.iterrows():
#                 cell_values: list = []
#                 for val in row:
#                     if pd.isna(val):
#                         continue
#                     sval = str(val).strip()
#                     if not sval or sval.lower() == "nan":
#                         continue
#                     # Also skip pure-numeric noise like "0.0" from empty numeric cols
#                     cell_values.append(sval)

#                 if cell_values:
#                     lines.append("  ".join(cell_values))

#         result = "\n".join(lines)
#         logger.info(
#             "Spreadsheet (%s) extracted cleanly (NaN-free): %s (%d chars)",
#             ext, os.path.basename(file_path), len(result)
#         )
#         return result

#     except Exception as e:
#         logger.warning("Spreadsheet extraction failed for %s: %s", file_path, e)
#         return ""


# async def _gemini_fallback(file_path: str) -> str:
#     if _gemini_available and extract_text_with_gemini:
#         try:
#             result = await extract_text_with_gemini(file_path)
#             return result or ""
#         except Exception as e:
#             logger.warning("Gemini fallback failed for %s: %s", file_path, e)
#     return ""


# # ============================================================
# # MAIN EXTRACTION ENTRYPOINT
# # ============================================================
# async def extract_text(file_path: str, content_type: Optional[str] = None) -> str:
#     """
#     Unified text extraction — fully local, Gemini only as last resort.

#     Format       | Method                              | External tool?
#     -------------|-------------------------------------|----------------
#     .txt         | open() read                         | None
#     .docx        | python-docx                         | None
#     .doc         | Binary UTF-16LE scan                | None
#     .xlsx/.xls   | pandas cell iteration (NaN-free)    | None  <- FIXED
#     .pptx        | python-pptx                         | None
#     .pdf digital | pdfplumber                          | None
#     .pdf scanned | pdf2image + Tesseract               | tesseract-ocr
#     .png/.jpg    | Tesseract                           | tesseract-ocr
#     Any above    | Gemini OCR (only if local fails)    | API key

#     Always returns str. Never raises. Never stores error messages.
#     """
#     abs_path = os.path.abspath(file_path)
#     if not os.path.exists(abs_path):
#         logger.error("File not found: %s (resolved: %s)", file_path, abs_path)
#         return ""
#     file_path = abs_path

#     ext = os.path.splitext(file_path)[1].lower()

#     try:
#         if ext == ".txt":
#             with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
#                 return f.read()

#         if ext == ".docx":
#             doc = Document(file_path)
#             return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

#         if ext == ".doc":
#             text = _extract_doc_binary(file_path)
#             if text and len(text) >= MIN_LOCAL_TEXT:
#                 return text
#             logger.info(".doc binary returned %d chars — trying Gemini: %s",
#                         len(text), os.path.basename(file_path))
#             return await _gemini_fallback(file_path)

#         # FIXED: NaN-free cell iteration instead of df.to_string()
#         if ext in (".xlsx", ".xls"):
#             text = _extract_spreadsheet(file_path, ext)
#             if text and len(text) >= MIN_LOCAL_TEXT:
#                 return text
#             logger.warning("Spreadsheet appears empty: %s", os.path.basename(file_path))
#             return ""

#         if ext == ".pptx":
#             prs = Presentation(file_path)
#             return "\n".join(
#                 shape.text
#                 for slide in prs.slides
#                 for shape in slide.shapes
#                 if hasattr(shape, "text") and shape.text.strip()
#             )

#         if ext == ".ppt":
#             logger.warning(".ppt not supported for local extraction")
#             return ""

#         if ext == ".pdf":
#             text = ""
#             try:
#                 with pdfplumber.open(file_path) as pdf:
#                     for page in pdf.pages:
#                         text += (page.extract_text() or "") + "\n"
#             except Exception as e:
#                 logger.warning("pdfplumber failed for %s: %s", file_path, e)

#             if text.strip() and len(text.strip()) >= MIN_LOCAL_TEXT:
#                 logger.info("PDF (digital) via pdfplumber: %s (%d chars)",
#                             os.path.basename(file_path), len(text.strip()))
#                 return text

#             logger.info("PDF appears scanned — trying local OCR: %s",
#                         os.path.basename(file_path))
#             text = _extract_scanned_pdf_local(file_path)
#             if text and len(text) >= MIN_LOCAL_TEXT:
#                 logger.info("Scanned PDF via local OCR: %s (%d chars)",
#                             os.path.basename(file_path), len(text))
#                 return text

#             logger.info("Local OCR returned %d chars — trying Gemini: %s",
#                         len(text), os.path.basename(file_path))
#             return await _gemini_fallback(file_path)

#         if ext in (".png", ".jpg", ".jpeg"):
#             logger.info("Extracting image via Tesseract: %s",
#                         os.path.basename(file_path))
#             text = _extract_image_local(file_path)
#             if text and len(text) >= MIN_LOCAL_TEXT:
#                 logger.info("Image via Tesseract: %s (%d chars)",
#                             os.path.basename(file_path), len(text))
#                 return text
#             logger.info("Tesseract returned %d chars — trying Gemini: %s",
#                         len(text), os.path.basename(file_path))
#             return await _gemini_fallback(file_path)

#         logger.warning("Unsupported file type: %s", ext)
#         return ""

#     except Exception as e:
#         logger.exception("Text extraction failed for %s: %s", file_path, e)
#         return ""



































# """
# Text extraction pipeline — TKREC Plagiarism Analysis System

# SCANNED PDF ROUTING:
#   1. pdfplumber          → digital PDF (selectable text, any language)
#   2. Gemini Vision       → scanned PDF PRIMARY  (multilingual LLM, handles
#                            Telugu, Hindi, handwriting, diagrams natively)
#      quota/unavailable →
#   3. Enhanced Tesseract  → fallback
#        - 300 DPI rendering
#        - contrast + sharpen + binarize preprocessing
#        - PSM 4 + LSTM engine
#        - per-page quality gate (skips garbage pages)
#        - TWO-PASS LANGUAGE DETECTION (new)
#            Pass 1: eng only  → detect Indic script in output
#            Pass 2: eng+<lang> if pack installed (e.g. eng+tel for Telugu)

# LANGUAGE SUPPORT (scanned PDFs):
#   Digital PDFs with embedded Unicode text → pdfplumber returns correct
#   Telugu/Hindi/Tamil/etc text automatically — no special handling needed.

#   Scanned PDFs → Gemini handles all Indian languages natively.
#   Tesseract fallback → requires tesseract-ocr-<lang> system package:
#     sudo apt-get install -y tesseract-ocr-tel   # Telugu
#     sudo apt-get install -y tesseract-ocr-hin   # Hindi
#     sudo apt-get install -y tesseract-ocr-tam   # Tamil
#     sudo apt-get install -y tesseract-ocr-kan   # Kannada
#     sudo apt-get install -y tesseract-ocr-mal   # Malayalam

# BUGS FIXED (vs original):
#   BUG-1  dpi=200 → blurry renders  →  fixed: dpi=300
#   BUG-2  no preprocessing          →  fixed: contrast/sharpen/binarize
#   BUG-3  wrong PSM mode (3→4)      →  fixed: --psm 4 --oem 1
#   BUG-4  no quality gate           →  fixed: skip pages < 40% alpha ratio
#   BUG-5  Gemini called without is_pdf arg → TypeError silently swallowed
#           → Gemini NEVER actually ran  →  fixed: pass is_pdf=True/False
#   BUG-6  Gemini was fallback for scanned PDFs, should be PRIMARY
#   BUG-7  No Telugu / Indic language support in Tesseract fallback
#           →  fixed: two-pass lang detection + eng+tel if pack installed
# """

# import os
# import re
# import logging
# import subprocess
# from typing import Optional, Tuple, List

# import pandas as pd
# import pdfplumber
# from docx import Document
# from pptx import Presentation

# logger = logging.getLogger(__name__)

# # ============================================================
# # LOCAL OCR IMPORTS
# # ============================================================
# try:
#     import pytesseract
#     from PIL import Image, ImageFilter, ImageEnhance
#     import numpy as np
#     _tesseract_available = True
# except ImportError:
#     _tesseract_available = False
#     logger.warning("pytesseract/Pillow not installed — image OCR falls back to Gemini")

# try:
#     from pdf2image import convert_from_path
#     _pdf2image_available = True
# except ImportError:
#     _pdf2image_available = False
#     logger.warning("pdf2image not installed — scanned PDF OCR falls back to Gemini")

# # ============================================================
# # GEMINI IMPORT
# # ============================================================
# try:
#     from app.libs.gemini_service import extract_text_with_gemini
#     _gemini_available = True
# except Exception as e:
#     logger.warning("Gemini service unavailable: %s", e)
#     extract_text_with_gemini = None
#     _gemini_available = False

# # ============================================================
# # CONSTANTS
# # ============================================================
# MIN_LOCAL_TEXT = 10

# # Pages below this alpha-char ratio are skipped (garbage OCR)
# OCR_QUALITY_THRESHOLD = 0.40

# # Max pages to process from a scanned PDF for plagiarism purposes
# SCANNED_PDF_MAX_PAGES = 20

# # Tesseract base config — works for all scripts
# TESSERACT_BASE_CONFIG = "--psm 4 --oem 1"

# # Gemini quota/rate-limit error signals from gemini_service
# _GEMINI_QUOTA_SIGNALS = {
#     "quota", "429", "resource_exhausted", "rate limit",
#     "too many requests", "exceeded",
# }

# # ─── Indic script Unicode ranges ────────────────────────────────────────────
# # Maps Tesseract language code → (range_start, range_end)
# # All Indian language PDFs will be detected and routed correctly.
# _INDIC_SCRIPT_RANGES: dict[str, tuple[str, str]] = {
#     "tel": ("\u0C00", "\u0C7F"),   # Telugu
#     "hin": ("\u0900", "\u097F"),   # Hindi / Devanagari (also Marathi)
#     "tam": ("\u0B80", "\u0BFF"),   # Tamil
#     "kan": ("\u0C80", "\u0CFF"),   # Kannada
#     "mal": ("\u0D00", "\u0D7F"),   # Malayalam
#     "guj": ("\u0A80", "\u0AFF"),   # Gujarati
#     "pan": ("\u0A00", "\u0A7F"),   # Punjabi / Gurmukhi
#     "ori": ("\u0B00", "\u0B7F"),   # Odia
#     "ben": ("\u0980", "\u09FF"),   # Bengali
# }

# _LANGUAGE_NAMES: dict[str, str] = {
#     "tel": "Telugu", "hin": "Hindi/Devanagari", "tam": "Tamil",
#     "kan": "Kannada", "mal": "Malayalam", "guj": "Gujarati",
#     "pan": "Punjabi", "ori": "Odia", "ben": "Bengali",
# }

# # Noise tokens in .doc OLE metadata
# _DOC_NOISE = {
#     "Times New Roman", "Liberation Serif", "Liberation Sans", "DejaVu Sans",
#     "Open Sans", "FreeSans", "OpenSymbol", "Arial Unicode MS", "Droid Sans",
#     "Fallback", "Symbol", "Arial", "Heading", "oasis.open", "office.com",
#     "Visited Internet Link", "Internet Link", "Root Entry", "WordDocument",
# }


# # ============================================================
# # LANGUAGE DETECTION UTILITIES
# # ============================================================

# def _detect_indic_scripts(text: str) -> List[str]:
#     """
#     Return list of detected Tesseract language codes for Indic scripts
#     present in the given text. E.g. ['tel'] for Telugu, ['tel', 'hin']
#     for mixed Telugu+Hindi.
#     """
#     return [
#         lang
#         for lang, (start, end) in _INDIC_SCRIPT_RANGES.items()
#         if any(start <= c <= end for c in text)
#     ]


# def _get_installed_tesseract_langs() -> set:
#     """
#     Return the set of Tesseract language codes installed on this system.
#     Cached after first call to avoid repeated subprocess calls.
#     """
#     if not hasattr(_get_installed_tesseract_langs, "_cache"):
#         try:
#             r = subprocess.run(
#                 ["tesseract", "--list-langs"],
#                 capture_output=True, text=True, timeout=5
#             )
#             lines = r.stdout.strip().split("\n")
#             # First line is "List of available languages..." header — skip it
#             langs = {l.strip() for l in lines[1:] if l.strip()}
#             _get_installed_tesseract_langs._cache = langs
#             logger.info("Installed Tesseract languages: %s", langs)
#         except Exception as e:
#             logger.warning("Could not query Tesseract langs: %s", e)
#             _get_installed_tesseract_langs._cache = {"eng"}
#     return _get_installed_tesseract_langs._cache


# def _build_tesseract_lang_string(detected_scripts: List[str]) -> str:
#     """
#     Build the Tesseract -l argument from detected scripts.

#     Rules:
#     - Always include 'eng' (academic docs are almost always mixed with English)
#     - Only include script packs that are actually installed
#     - Warn if a detected script pack is NOT installed
#     - Returns e.g. 'eng+tel' if tel is installed, 'eng' if not

#     System install guide (logged as WARNING if missing):
#       sudo apt-get install -y tesseract-ocr-tel   # Telugu
#       sudo apt-get install -y tesseract-ocr-hin   # Hindi
#       (see requirements.txt for full list)
#     """
#     if not detected_scripts:
#         return "eng"

#     installed = _get_installed_tesseract_langs()
#     available = []
#     missing = []

#     for script in detected_scripts:
#         if script in installed:
#             available.append(script)
#         else:
#             missing.append(script)

#     if missing:
#         lang_names = [_LANGUAGE_NAMES.get(m, m) for m in missing]
#         logger.warning(
#             "Tesseract language packs NOT installed for detected scripts %s. "
#             "OCR quality for these scripts will be degraded. "
#             "Install with: sudo apt-get install -y %s",
#             lang_names,
#             " ".join(f"tesseract-ocr-{m}" for m in missing),
#         )

#     all_langs = ["eng"] + available
#     return "+".join(all_langs)  # e.g. "eng+tel" or "eng+tel+hin"


# # ============================================================
# # IMAGE QUALITY HELPERS
# # ============================================================

# def _assess_image_quality(img) -> float:
#     """
#     Content-presence score 0.0–1.0 from grayscale pixel stddev.
#     Blank pages ≈ 0.0–0.1  |  text-filled pages ≈ 0.7–1.0
#     """
#     from PIL import ImageStat
#     gray = img.convert("L")
#     stat = ImageStat.Stat(gray)
#     return min(1.0, stat.stddev[0] / 40.0)


# def _preprocess_for_tesseract(img) -> "Image":
#     """
#     Enhance a page image before OCR:
#       1. Grayscale     — remove colour noise
#       2. Contrast ×1.8 — ink stands out from paper
#       3. Sharpen       — sharpen pen/print strokes
#       4. Binarize      — threshold = mean − 0.2×std (Otsu-style)
#                          robust to yellowed/uneven scanned paper
#     Works well for both English and Indic script pages.
#     """
#     img = img.convert("L")
#     img = ImageEnhance.Contrast(img).enhance(1.8)
#     img = img.filter(ImageFilter.SHARPEN)
#     arr = np.array(img)
#     threshold = arr.mean() - arr.std() * 0.2
#     arr = np.where(arr > threshold, 255, 0).astype(np.uint8)
#     return Image.fromarray(arr)


# def _ocr_quality_score(text: str) -> float:
#     """
#     Fraction of alphabetic / Indic chars among non-whitespace chars.

#     Extended to count Indic Unicode chars as 'valid' — without this,
#     a page of pure Telugu text would score 0% (no ASCII alpha) and
#     get skipped by the quality gate.
#     """
#     stripped = text.replace(" ", "").replace("\n", "")
#     if not stripped:
#         return 0.0

#     def is_valid_char(c: str) -> bool:
#         # ASCII letters
#         if c.isalpha():
#             return True
#         # Indic script characters (U+0900 – U+0D7F covers all major scripts)
#         cp = ord(c)
#         return 0x0900 <= cp <= 0x0D7F

#     valid = sum(1 for c in stripped if is_valid_char(c))
#     return valid / len(stripped)


# # ============================================================
# # SCANNED PDF — GEMINI PRIMARY
# # ============================================================

# async def _extract_scanned_pdf_gemini(file_path: str) -> Tuple[str, bool]:
#     """
#     Attempt Gemini Vision extraction for a scanned PDF.

#     Gemini is multilingual by design — it handles Telugu, Hindi, Tamil,
#     and other Indic scripts WITHOUT needing any language configuration.

#     Returns: (text, quota_exceeded)
#     """
#     if not _gemini_available or not extract_text_with_gemini:
#         logger.info("Gemini not configured — skipping Gemini path")
#         return "", False

#     try:
#         # BUG-5 FIX: is_pdf=True (this arg was missing before → TypeError)
#         result = await extract_text_with_gemini(file_path, is_pdf=True)

#         if not result:
#             return "", False

#         result_lower = result.lower()
#         if result.startswith("ERROR:"):
#             quota_hit = any(sig in result_lower for sig in _GEMINI_QUOTA_SIGNALS)
#             level = "quota/rate-limit" if quota_hit else "error"
#             logger.warning("Gemini %s for %s: %s",
#                            level, os.path.basename(file_path), result[:120])
#             return "", quota_hit

#         logger.info("Scanned PDF via Gemini: %s (%d chars)",
#                     os.path.basename(file_path), len(result))
#         return result, False

#     except Exception as e:
#         err = str(e).lower()
#         quota_hit = any(sig in err for sig in _GEMINI_QUOTA_SIGNALS)
#         logger.warning("Gemini %s for %s: %s",
#                        "quota" if quota_hit else "exception",
#                        os.path.basename(file_path), e)
#         return "", quota_hit


# # ============================================================
# # SCANNED PDF — ENHANCED TESSERACT FALLBACK
# # ============================================================

# def _extract_scanned_pdf_local(file_path: str) -> str:
#     """
#     Enhanced local Tesseract OCR for scanned PDFs.
#     Used ONLY when Gemini is unavailable or quota-exceeded.

#     TWO-PASS LANGUAGE DETECTION:
#     ─────────────────────────────
#     Pass 1 (eng only, fast):
#       • Run Tesseract with English only on page 1
#       • Check output for Indic Unicode characters

#     Pass 2 (full run with correct languages):
#       • If Indic scripts detected in Pass 1:
#           - Build lang string: eng+tel / eng+hin / eng+tel+hin etc.
#           - Warn if language pack is not installed
#           - Re-run with correct lang on all pages
#       • If no Indic scripts:
#           - Continue with eng only (no overhead)

#     This ensures Telugu/Hindi/Tamil PDFs get proper Tesseract
#     language support without slowing down English-only documents.
#     """
#     if not _pdf2image_available or not _tesseract_available:
#         logger.warning("pdf2image or pytesseract unavailable")
#         return ""

#     try:
#         pages = convert_from_path(
#             file_path,
#             dpi=300,                         # BUG-1 FIX: was 200
#             first_page=1,
#             last_page=SCANNED_PDF_MAX_PAGES,
#         )
#     except Exception as e:
#         logger.warning("pdf2image failed for %s: %s", os.path.basename(file_path), e)
#         return ""

#     # ── Pass 1: Language Detection ────────────────────────────────────────
#     tesseract_lang = "eng"
#     if pages:
#         try:
#             processed_p1 = _preprocess_for_tesseract(pages[0])
#             p1_text = pytesseract.image_to_string(
#                 processed_p1,
#                 config=f"{TESSERACT_BASE_CONFIG} -l eng",
#                 timeout=30,
#             )
#             detected_scripts = _detect_indic_scripts(p1_text)

#             if not detected_scripts:
#                 # Pass 1 text is English-only OCR — check if the raw image
#                 # might contain Indic characters that eng-only Tesseract missed
#                 # by sampling the raw (unprocessed) first page too
#                 raw_p1_text = pytesseract.image_to_string(
#                     pages[0],
#                     config=f"{TESSERACT_BASE_CONFIG} -l eng",
#                     timeout=30,
#                 )
#                 detected_scripts = _detect_indic_scripts(raw_p1_text)

#             if detected_scripts:
#                 tesseract_lang = _build_tesseract_lang_string(detected_scripts)
#                 script_names = [_LANGUAGE_NAMES.get(s, s) for s in detected_scripts]
#                 logger.info(
#                     "Indic scripts detected in Pass 1: %s → Tesseract lang=%r",
#                     script_names, tesseract_lang
#                 )
#             else:
#                 logger.info("No Indic scripts detected → using Tesseract lang='eng'")

#         except Exception as e:
#             logger.warning("Pass 1 language detection failed: %s — using eng", e)
#             tesseract_lang = "eng"

#     # ── Pass 2: Full Extraction ───────────────────────────────────────────
#     tesseract_config = f"{TESSERACT_BASE_CONFIG} -l {tesseract_lang}"
#     logger.info("Pass 2: OCR with config=%r on %d pages",
#                 tesseract_config, len(pages))

#     texts = []
#     total = len(pages)
#     good = skipped_blank = skipped_garbage = 0

#     for i, page in enumerate(pages):
#         try:
#             # Skip blank / nearly-blank pages
#             if _assess_image_quality(page) < 0.10:
#                 skipped_blank += 1
#                 continue

#             # Preprocess (BUG-2 FIX: was raw image)
#             processed = _preprocess_for_tesseract(page)

#             # OCR with tuned config (BUG-3 FIX: was default config)
#             page_text = pytesseract.image_to_string(
#                 processed,
#                 config=tesseract_config,
#                 timeout=45,
#             )

#             if not page_text.strip():
#                 skipped_blank += 1
#                 continue

#             # Per-page quality gate (BUG-4 FIX: was no gate)
#             # NOTE: quality score now counts Indic chars as valid
#             quality = _ocr_quality_score(page_text)
#             if quality < OCR_QUALITY_THRESHOLD:
#                 logger.warning("Page %d/%d quality low (%.0f%%) — skipped",
#                                i + 1, total, quality * 100)
#                 skipped_garbage += 1
#                 continue

#             texts.append(page_text.strip())
#             good += 1

#         except Exception as e:
#             logger.warning("Tesseract page %d error: %s", i + 1, e)

#     logger.info(
#         "Enhanced Tesseract [lang=%s]: %d/%d good | %d blank | %d garbage | %s",
#         tesseract_lang, good, total, skipped_blank, skipped_garbage,
#         os.path.basename(file_path),
#     )
#     return "\n\n".join(texts)


# # ============================================================
# # OTHER FORMAT HELPERS
# # ============================================================

# def _extract_doc_binary(file_path: str) -> str:
#     """Legacy .doc (Word 97-2003) binary UTF-16LE text extraction."""
#     try:
#         with open(os.path.abspath(file_path), "rb") as f:
#             data = f.read()
#         chunks = re.findall(b"(?:[\x20-\x7e]\x00){8,}", data)
#         text_parts = []
#         for chunk in chunks:
#             try:
#                 decoded = chunk.decode("utf-16-le", errors="ignore").strip()
#             except Exception:
#                 continue
#             if len(decoded) < 15:
#                 continue
#             if any(noise in decoded for noise in _DOC_NOISE):
#                 continue
#             text_parts.append(decoded)
#         result = "\n".join(text_parts)
#         logger.info(".doc binary: %s (%d chars)", os.path.basename(file_path), len(result))
#         return result
#     except Exception as e:
#         logger.warning("Binary .doc failed for %s: %s", file_path, e)
#         return ""


# def _extract_image_local(file_path: str) -> str:
#     """
#     Tesseract OCR for standalone image files with language detection.
#     Same two-pass approach as scanned PDFs.
#     """
#     if not _tesseract_available:
#         return ""
#     try:
#         img = Image.open(file_path)
#         processed = _preprocess_for_tesseract(img)

#         # Quick language detection pass
#         p1_text = pytesseract.image_to_string(
#             processed, config=f"{TESSERACT_BASE_CONFIG} -l eng", timeout=20
#         )
#         detected = _detect_indic_scripts(p1_text)
#         lang = _build_tesseract_lang_string(detected)

#         if lang != "eng":
#             return pytesseract.image_to_string(
#                 processed,
#                 config=f"{TESSERACT_BASE_CONFIG} -l {lang}",
#                 timeout=30,
#             ).strip()
#         return p1_text.strip()

#     except Exception as e:
#         logger.warning("Tesseract image OCR failed for %s: %s", file_path, e)
#         return ""


# def _extract_spreadsheet(file_path: str, ext: str) -> str:
#     """XLS/XLSX extraction — NaN-free cell iteration."""
#     try:
#         engine = "xlrd" if ext == ".xls" else "openpyxl"
#         dfs = pd.read_excel(file_path, sheet_name=None, engine=engine)
#         lines: list = []
#         for sheet_name, df in dfs.items():
#             if len(dfs) > 1:
#                 lines.append(f"[Sheet: {sheet_name}]")
#             for _, row in df.iterrows():
#                 cell_values: list = []
#                 for val in row:
#                     if pd.isna(val):
#                         continue
#                     sval = str(val).strip()
#                     if not sval or sval.lower() == "nan":
#                         continue
#                     cell_values.append(sval)
#                 if cell_values:
#                     lines.append("  ".join(cell_values))
#         result = "\n".join(lines)
#         logger.info("Spreadsheet (%s): %s (%d chars)",
#                     ext, os.path.basename(file_path), len(result))
#         return result
#     except Exception as e:
#         logger.warning("Spreadsheet extraction failed for %s: %s", file_path, e)
#         return ""


# async def _gemini_fallback_image(file_path: str) -> str:
#     """Gemini fallback for standalone image files. BUG-5 FIX: is_pdf=False."""
#     if not _gemini_available or not extract_text_with_gemini:
#         return ""
#     try:
#         result = await extract_text_with_gemini(file_path, is_pdf=False)
#         if result and not result.startswith("ERROR:"):
#             return result
#         logger.warning("Gemini image error: %s", (result or "")[:100])
#         return ""
#     except Exception as e:
#         logger.warning("Gemini image exception: %s", e)
#         return ""


# # ============================================================
# # MAIN EXTRACTION ENTRYPOINT
# # ============================================================

# async def extract_text(file_path: str, content_type: Optional[str] = None) -> str:
#     """
#     Unified text extraction — always returns str, never raises.

#     Format        Primary                        Fallback
#     ──────────────────────────────────────────────────────────────────────
#     .txt          open() read                    —
#     .docx         python-docx                    —
#     .doc          UTF-16LE binary scan           Gemini (is_pdf=False)
#     .xlsx/.xls    pandas NaN-free                —
#     .pptx         python-pptx                    —
#     .pdf digital  pdfplumber (Unicode-aware)     —
#     .pdf scanned  Gemini Vision PRIMARY           Enhanced Tesseract
#                   (multilingual, no config)       (300dpi + preprocess
#                                                    + 2-pass lang detect
#                                                    + quality gate)
#     .png/.jpg     Tesseract (2-pass lang detect)  Gemini (is_pdf=False)

#     TELUGU / INDIC LANGUAGE SUPPORT:
#     • Digital PDF:  pdfplumber returns Telugu Unicode directly ✓
#     • Scanned PDF:  Gemini handles Telugu natively (no config needed) ✓
#     • Tesseract fallback: auto-detects Telugu, uses eng+tel if installed ✓
#       Install: sudo apt-get install -y tesseract-ocr-tel
#     """
#     abs_path = os.path.abspath(file_path)
#     if not os.path.exists(abs_path):
#         logger.error("File not found: %s", abs_path)
#         return ""
#     file_path = abs_path
#     ext = os.path.splitext(file_path)[1].lower()

#     try:
#         # ── Plain text ────────────────────────────────────────────────
#         if ext == ".txt":
#             with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
#                 return f.read()

#         # ── Word .docx ───────────────────────────────────────────────
#         if ext == ".docx":
#             doc = Document(file_path)
#             return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

#         # ── Legacy Word .doc ─────────────────────────────────────────
#         if ext == ".doc":
#             text = _extract_doc_binary(file_path)
#             if text and len(text) >= MIN_LOCAL_TEXT:
#                 return text
#             logger.info(".doc binary %d chars — trying Gemini", len(text))
#             if _gemini_available and extract_text_with_gemini:
#                 try:
#                     result = await extract_text_with_gemini(file_path, is_pdf=False)
#                     if result and not result.startswith("ERROR:"):
#                         return result
#                 except Exception as e:
#                     logger.warning("Gemini .doc fallback failed: %s", e)
#             return ""

#         # ── Spreadsheets ─────────────────────────────────────────────
#         if ext in (".xlsx", ".xls"):
#             text = _extract_spreadsheet(file_path, ext)
#             if text and len(text) >= MIN_LOCAL_TEXT:
#                 return text
#             logger.warning("Spreadsheet empty: %s", os.path.basename(file_path))
#             return ""

#         # ── PowerPoint ───────────────────────────────────────────────
#         if ext == ".pptx":
#             prs = Presentation(file_path)
#             return "\n".join(
#                 shape.text
#                 for slide in prs.slides
#                 for shape in slide.shapes
#                 if hasattr(shape, "text") and shape.text.strip()
#             )

#         if ext == ".ppt":
#             logger.warning(".ppt not supported for local extraction")
#             return ""

#         # ── PDF ──────────────────────────────────────────────────────
#         if ext == ".pdf":

#             # Step 1: Digital PDF — pdfplumber
#             # Works for all languages with proper Unicode embedding.
#             # Telugu, Hindi, Tamil etc. in digital PDFs are extracted
#             # correctly with no special configuration.
#             text = ""
#             try:
#                 with pdfplumber.open(file_path) as pdf:
#                     for page in pdf.pages:
#                         text += (page.extract_text() or "") + "\n"
#             except Exception as e:
#                 logger.warning("pdfplumber failed: %s", e)

#             if text.strip() and len(text.strip()) >= MIN_LOCAL_TEXT:
#                 detected = _detect_indic_scripts(text)
#                 if detected:
#                     lang_names = [_LANGUAGE_NAMES.get(s, s) for s in detected]
#                     logger.info("Digital PDF with Indic script %s: %s (%d chars)",
#                                 lang_names, os.path.basename(file_path), len(text.strip()))
#                 else:
#                     logger.info("PDF digital via pdfplumber: %s (%d chars)",
#                                 os.path.basename(file_path), len(text.strip()))
#                 return text.strip()

#             # Step 2: Scanned PDF — Gemini FIRST (multilingual)
#             # ────────────────────────────────────────────────────────────
#             # Gemini Vision is natively multilingual — it reads Telugu,
#             # Hindi, Tamil etc. without any special configuration.
#             # No language detection needed here — Gemini just works.
#             # ────────────────────────────────────────────────────────────
#             logger.info("Scanned PDF — trying Gemini FIRST: %s",
#                         os.path.basename(file_path))

#             gemini_text, quota_exceeded = await _extract_scanned_pdf_gemini(file_path)

#             if gemini_text and len(gemini_text) >= MIN_LOCAL_TEXT:
#                 detected = _detect_indic_scripts(gemini_text)
#                 if detected:
#                     lang_names = [_LANGUAGE_NAMES.get(s, s) for s in detected]
#                     logger.info("Gemini extracted Indic script %s from scanned PDF",
#                                 lang_names)
#                 return gemini_text

#             # Step 3: Tesseract fallback (two-pass language detection)
#             reason = "quota exceeded" if quota_exceeded else "unavailable/error"
#             logger.warning("Gemini %s — enhanced Tesseract fallback: %s",
#                            reason, os.path.basename(file_path))

#             local_text = _extract_scanned_pdf_local(file_path)
#             if local_text and len(local_text) >= MIN_LOCAL_TEXT:
#                 return local_text

#             logger.error("All extraction methods failed: %s",
#                          os.path.basename(file_path))
#             return ""

#         # ── Images ───────────────────────────────────────────────────
#         if ext in (".png", ".jpg", ".jpeg"):
#             text = _extract_image_local(file_path)
#             if text and len(text) >= MIN_LOCAL_TEXT:
#                 logger.info("Image via Tesseract: %s (%d chars)",
#                             os.path.basename(file_path), len(text))
#                 return text
#             logger.info("Tesseract %d chars — trying Gemini: %s",
#                         len(text), os.path.basename(file_path))
#             return await _gemini_fallback_image(file_path)

#         logger.warning("Unsupported file type: %s", ext)
#         return ""

#     except Exception as e:
#         logger.exception("Text extraction failed for %s: %s", file_path, e)
#         return ""












































# """
# backend/app/libs/extract.py

# TEXT EXTRACTION PIPELINE — PRIORITY ORDER
# ==========================================

# For SCANNED / IMAGE PDFs (handwritten notes, Telugu scans):
#   1. Gemini Vision  (PRIMARY)   — VLM, understands handwriting + Telugu + diagrams
#   2. PaddleOCR      (SECONDARY) — Deep learning OCR, multilingual fallback
#   3. Tesseract      (LAST RESORT)— Traditional OCR, emergency fallback only

# For TEXT PDFs (digital, selectable text):
#   1. pdfplumber     (PRIMARY)   — Fast, accurate, preserves layout

# For DOCX:  python-docx
# For TXT:   direct read
# For Images: Gemini → PaddleOCR → Tesseract

# KEY DESIGN CHANGE vs old code:
#   OLD: pdfplumber → Tesseract → Gemini  (Gemini rarely triggered since Tesseract
#                                          always returns something, even garbage)
#   NEW: pdfplumber → [if scanned] → Gemini → PaddleOCR → Tesseract
# """

# import os
# import logging
# from typing import Optional

# import pdfplumber
# from PIL import Image

# logger = logging.getLogger("extract")

# MIN_SELECTABLE_CHARS = 50   # Below this → treat PDF as scanned
# PDF_RENDER_DPI       = 300  # DPI for rendering PDF pages to images
# MAX_CHARS            = 100_000

# _paddle_ocr = None          # Lazy-loaded PaddleOCR singleton


# # ─────────────────────────────────────────────────────────────────────────────
# # SCANNED PDF DETECTION
# # ─────────────────────────────────────────────────────────────────────────────

# def _is_scanned_pdf(file_path: str) -> bool:
#     try:
#         with pdfplumber.open(file_path) as pdf:
#             total = ""
#             for page in pdf.pages[:3]:
#                 total += page.extract_text() or ""
#                 if len(total) >= MIN_SELECTABLE_CHARS:
#                     return False
#         return len(total.strip()) < MIN_SELECTABLE_CHARS
#     except Exception:
#         return True


# # ─────────────────────────────────────────────────────────────────────────────
# # TIER 1a — pdfplumber (text PDFs)
# # ─────────────────────────────────────────────────────────────────────────────

# def _extract_with_pdfplumber(file_path: str) -> str:
#     try:
#         with pdfplumber.open(file_path) as pdf:
#             parts = []
#             for page in pdf.pages:
#                 t = page.extract_text()
#                 if t:
#                     parts.append(t.strip())
#             return "\n\n".join(parts)[:MAX_CHARS]
#     except Exception as e:
#         logger.debug("pdfplumber failed: %s", e)
#         return ""


# # ─────────────────────────────────────────────────────────────────────────────
# # TIER 1b — Gemini Vision (PRIMARY for scanned/image PDFs)
# # ─────────────────────────────────────────────────────────────────────────────

# async def _extract_with_gemini(file_path: str) -> str:
#     """
#     Gemini Vision — best for handwritten notes, Telugu, equations, diagrams.
#     Sends the entire file as a single API call with full page context.
#     """
#     try:
#         from app.libs.gemini_service import extract_text_with_gemini
#         result = await extract_text_with_gemini(file_path)
#         if result and len(result.strip()) >= 20:
#             logger.info("Gemini Vision OCR: %d chars from %s",
#                         len(result), os.path.basename(file_path))
#             return result[:MAX_CHARS]
#         return ""
#     except Exception as e:
#         logger.warning("Gemini OCR failed: %s", e)
#         return ""


# # ─────────────────────────────────────────────────────────────────────────────
# # TIER 2 — PaddleOCR (multilingual deep-learning fallback)
# # ─────────────────────────────────────────────────────────────────────────────

# def _get_paddle_ocr():
#     global _paddle_ocr
#     if _paddle_ocr is None:
#         try:
#             from paddleocr import PaddleOCR
#             _paddle_ocr = PaddleOCR(
#                 use_angle_cls=True,
#                 lang="en",
#                 use_gpu=False,
#                 show_log=False,
#             )
#             logger.info("PaddleOCR loaded successfully")
#         except ImportError:
#             logger.warning("PaddleOCR not installed. Run: pip install paddlepaddle paddleocr")
#         except Exception as e:
#             logger.warning("PaddleOCR init failed: %s", e)
#     return _paddle_ocr


# def _extract_with_paddleocr(image: Image.Image) -> str:
#     ocr = _get_paddle_ocr()
#     if not ocr:
#         return ""
#     try:
#         import numpy as np
#         result = ocr.ocr(np.array(image.convert("RGB")), cls=True)
#         lines = []
#         if result and result[0]:
#             for line in result[0]:
#                 if line and len(line) >= 2:
#                     text_info = line[1]
#                     if text_info and text_info[0].strip():
#                         confidence = text_info[1] if len(text_info) > 1 else 1.0
#                         if confidence > 0.5:
#                             lines.append(text_info[0].strip())
#         return " ".join(lines)
#     except Exception as e:
#         logger.debug("PaddleOCR page failed: %s", e)
#         return ""


# # ─────────────────────────────────────────────────────────────────────────────
# # TIER 3 — Tesseract (last resort)
# # ─────────────────────────────────────────────────────────────────────────────

# def _extract_with_tesseract(image: Image.Image) -> str:
#     try:
#         import pytesseract
#         # eng+tel = English + Telugu simultaneously
#         return pytesseract.image_to_string(image, lang="eng+tel").strip()
#     except Exception as e:
#         logger.debug("Tesseract failed: %s", e)
#         return ""


# # ─────────────────────────────────────────────────────────────────────────────
# # PDF → IMAGES (for page-level OCR fallback)
# # ─────────────────────────────────────────────────────────────────────────────

# def _pdf_to_images(file_path: str, dpi: int = PDF_RENDER_DPI):
#     try:
#         from pdf2image import convert_from_path
#         images = convert_from_path(file_path, dpi=dpi)
#         logger.info("Rendered %d pages at %d DPI", len(images), dpi)
#         return images
#     except ImportError:
#         logger.warning("pdf2image not installed. Run: pip install pdf2image")
#         return []
#     except Exception as e:
#         logger.warning("PDF rendering failed: %s", e)
#         return []


# # ─────────────────────────────────────────────────────────────────────────────
# # SCANNED PDF PIPELINE
# # ─────────────────────────────────────────────────────────────────────────────

# async def _extract_scanned_pdf(file_path: str) -> str:
#     """
#     OCR pipeline for scanned/handwritten PDFs.

#     1. Gemini Vision on the whole file (best accuracy — context-aware)
#     2. PaddleOCR page by page (multilingual deep learning)
#     3. Tesseract page by page (last resort)
#     """

#     # ── Tier 1: Gemini whole-file OCR ────────────────────────────────────
#     logger.info("Scanned PDF — trying Gemini Vision OCR first")
#     gemini_text = await _extract_with_gemini(file_path)
#     if gemini_text and len(gemini_text.strip()) >= 50:
#         logger.info("Gemini Vision succeeded: %d chars", len(gemini_text))
#         return gemini_text

#     logger.info("Gemini insufficient — falling back to page-level OCR")

#     # ── Render pages for page-level OCR ──────────────────────────────────
#     images = _pdf_to_images(file_path)
#     if not images:
#         return ""

#     all_pages = []
#     paddle_available = _get_paddle_ocr() is not None

#     for i, image in enumerate(images, start=1):
#         page_text = ""

#         # Tier 2: PaddleOCR
#         if paddle_available:
#             page_text = _extract_with_paddleocr(image)

#         # Tier 3: Tesseract (only if PaddleOCR gave nothing)
#         if not page_text or len(page_text.strip()) < 20:
#             page_text = _extract_with_tesseract(image)

#         if page_text.strip():
#             all_pages.append(f"[Page {i}]\n{page_text.strip()}")

#     return "\n\n".join(all_pages)[:MAX_CHARS]


# # ─────────────────────────────────────────────────────────────────────────────
# # DOCX
# # ─────────────────────────────────────────────────────────────────────────────

# def _extract_docx(file_path: str) -> str:
#     try:
#         import docx
#         doc = docx.Document(file_path)
#         parts = [p.text for p in doc.paragraphs if p.text.strip()]
#         return "\n".join(parts)[:MAX_CHARS]
#     except Exception as e:
#         logger.debug("python-docx failed: %s", e)
#         return ""


# # ─────────────────────────────────────────────────────────────────────────────
# # PUBLIC API
# # ─────────────────────────────────────────────────────────────────────────────

# async def extract_text(file_path: str, content_type: str = "") -> str:
#     """
#     Main text extraction entry point — called by main.py upload handler.

#     Routing:
#       .txt              → direct read
#       .docx / .doc      → python-docx → Gemini (if embedded images)
#       .png/.jpg/images  → Gemini → PaddleOCR → Tesseract
#       .pdf (text)       → pdfplumber
#       .pdf (scanned)    → Gemini → PaddleOCR → Tesseract
#       unknown           → Gemini
#     """
#     if not os.path.exists(file_path):
#         logger.error("File not found: %s", file_path)
#         return ""

#     ext = os.path.splitext(file_path)[1].lower()

#     # ── Plain text ────────────────────────────────────────────────────────
#     if ext == ".txt" or "text/plain" in content_type:
#         try:
#             with open(file_path, "r", encoding="utf-8", errors="replace") as f:
#                 return f.read()[:MAX_CHARS]
#         except Exception:
#             return ""

#     # ── Word document ─────────────────────────────────────────────────────
#     if ext in (".docx", ".doc") or "wordprocessingml" in content_type:
#         text = _extract_docx(file_path)
#         if text:
#             return text
#         logger.info("DOCX empty — trying Gemini for embedded images")
#         return await _extract_with_gemini(file_path)

#     # ── Images ────────────────────────────────────────────────────────────
#     if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff") \
#             or (content_type and content_type.startswith("image/")):
#         text = await _extract_with_gemini(file_path)
#         if text:
#             return text
#         try:
#             image = Image.open(file_path)
#             text = _extract_with_paddleocr(image)
#             if text:
#                 return text
#             return _extract_with_tesseract(image)
#         except Exception:
#             return ""

#     # ── PDF ───────────────────────────────────────────────────────────────
#     if ext == ".pdf" or "pdf" in content_type:

#         # Fast path: text-based PDF
#         if not _is_scanned_pdf(file_path):
#             text = _extract_with_pdfplumber(file_path)
#             if text and len(text.strip()) >= MIN_SELECTABLE_CHARS:
#                 logger.info("Text PDF: %d chars via pdfplumber", len(text))
#                 return text
#             logger.info("PDF has partial text — supplementing with OCR")

#         # Scanned PDF path: Gemini first
#         return await _extract_scanned_pdf(file_path)

#     # ── Unknown ───────────────────────────────────────────────────────────
#     logger.warning("Unknown type %s — trying Gemini", ext)
#     return await _extract_with_gemini(file_path)












































"""
backend/app/libs/extract.py

TEXT EXTRACTION PIPELINE — PRIORITY ORDER
==========================================

For SCANNED / IMAGE PDFs (handwritten notes, Telugu scans):
  1. PaddleOCR      (PRIMARY)    — Deep learning OCR, multilingual, runs locally
  2. Tesseract      (SECONDARY)  — Traditional OCR, eng+tel language support
  3. Gemini Vision  (LAST RESORT)— API call, used only when local OCR fails

For TEXT PDFs (digital, selectable text):
  1. pdfplumber     (PRIMARY)    — Fast, accurate, preserves layout

For DOCX:  python-docx -> Gemini (embedded images only)
For TXT:   direct read
For Images: PaddleOCR -> Tesseract -> Gemini
"""

import os
import logging

import pdfplumber
from PIL import Image

logger = logging.getLogger("extract")

MIN_SELECTABLE_CHARS = 50
PDF_RENDER_DPI       = 300
MAX_CHARS            = 100_000

_paddle_ocr = None


# ─────────────────────────────────────────────────────────────────────────────
# SCANNED PDF DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _is_scanned_pdf(file_path: str) -> bool:
    try:
        with pdfplumber.open(file_path) as pdf:
            total = ""
            for page in pdf.pages[:3]:
                total += page.extract_text() or ""
                if len(total) >= MIN_SELECTABLE_CHARS:
                    return False
        return len(total.strip()) < MIN_SELECTABLE_CHARS
    except Exception:
        return True


# ─────────────────────────────────────────────────────────────────────────────
# TIER 0 — pdfplumber (text PDFs only — no OCR needed)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_with_pdfplumber(file_path: str) -> str:
    try:
        with pdfplumber.open(file_path) as pdf:
            parts = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t.strip())
            return "\n\n".join(parts)[:MAX_CHARS]
    except Exception as e:
        logger.debug("pdfplumber failed: %s", e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# TIER 1 — PaddleOCR (PRIMARY for scanned/image content)
# ─────────────────────────────────────────────────────────────────────────────

def _get_paddle_ocr():
    global _paddle_ocr
    if _paddle_ocr is None:
        try:
            from paddleocr import PaddleOCR
            _paddle_ocr = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                use_gpu=False,
                show_log=False,
            )
            logger.info("PaddleOCR loaded successfully")
        except ImportError:
            logger.warning("PaddleOCR not installed. Run: pip install paddlepaddle paddleocr")
        except Exception as e:
            logger.warning("PaddleOCR init failed: %s", e)
    return _paddle_ocr


def _extract_with_paddleocr(image: Image.Image) -> str:
    ocr = _get_paddle_ocr()
    if not ocr:
        return ""
    try:
        import numpy as np
        result = ocr.ocr(np.array(image.convert("RGB")), cls=True)
        lines = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    text_info = line[1]
                    if text_info and text_info[0].strip():
                        confidence = text_info[1] if len(text_info) > 1 else 1.0
                        if confidence > 0.5:
                            lines.append(text_info[0].strip())
        return " ".join(lines)
    except Exception as e:
        logger.debug("PaddleOCR page failed: %s", e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# TIER 2 — Tesseract (secondary fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_with_tesseract(image: Image.Image) -> str:
    try:
        import pytesseract
        return pytesseract.image_to_string(image, lang="eng+tel").strip()
    except Exception as e:
        logger.debug("Tesseract failed: %s", e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# TIER 3 — Gemini Vision (LAST RESORT)
# ─────────────────────────────────────────────────────────────────────────────

async def _extract_with_gemini(file_path: str) -> str:
    try:
        from app.libs.gemini_service import extract_text_with_gemini
        result = await extract_text_with_gemini(file_path)
        if result and len(result.strip()) >= 20:
            logger.info("Gemini Vision OCR (last resort): %d chars from %s",
                        len(result), os.path.basename(file_path))
            return result[:MAX_CHARS]
        return ""
    except Exception as e:
        logger.warning("Gemini OCR failed: %s", e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# PDF -> IMAGES
# ─────────────────────────────────────────────────────────────────────────────

def _pdf_to_images(file_path: str, dpi: int = PDF_RENDER_DPI):
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(file_path, dpi=dpi)
        logger.info("Rendered %d pages at %d DPI", len(images), dpi)
        return images
    except ImportError:
        logger.warning("pdf2image not installed. Run: pip install pdf2image")
        return []
    except Exception as e:
        logger.warning("PDF rendering failed: %s", e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# SCANNED PDF PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

async def _extract_scanned_pdf(file_path: str) -> str:
    images = _pdf_to_images(file_path)

    if not images:
        # pdf2image unavailable - skip straight to Gemini
        logger.info("Cannot render pages (pdf2image missing) - falling back to Gemini")
        return await _extract_with_gemini(file_path)

    all_pages = []
    paddle_available = _get_paddle_ocr() is not None

    for i, image in enumerate(images, start=1):
        page_text = ""

        # Tier 1: PaddleOCR
        if paddle_available:
            page_text = _extract_with_paddleocr(image)
            if page_text and len(page_text.strip()) >= 20:
                logger.debug("Page %d: PaddleOCR (%d chars)", i, len(page_text))

        # Tier 2: Tesseract (only if PaddleOCR gave nothing)
        if not page_text or len(page_text.strip()) < 20:
            page_text = _extract_with_tesseract(image)
            if page_text and len(page_text.strip()) >= 20:
                logger.debug("Page %d: Tesseract (%d chars)", i, len(page_text))

        if page_text.strip():
            all_pages.append(f"[Page {i}]\n{page_text.strip()}")

    combined = "\n\n".join(all_pages)

    # Tier 3: Gemini - only if both local methods failed
    if not combined or len(combined.strip()) < 50:
        logger.info(
            "Local OCR returned insufficient text (%d chars) - "
            "trying Gemini Vision as last resort",
            len(combined.strip())
        )
        return await _extract_with_gemini(file_path)

    return combined[:MAX_CHARS]


# ─────────────────────────────────────────────────────────────────────────────
# DOCX
# ─────────────────────────────────────────────────────────────────────────────

def _extract_docx(file_path: str) -> str:
    try:
        import docx
        doc = docx.Document(file_path)
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(parts)[:MAX_CHARS]
    except Exception as e:
        logger.debug("python-docx failed: %s", e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

async def extract_text(file_path: str, content_type: str = "") -> str:
    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return ""

    ext = os.path.splitext(file_path)[1].lower()

    # Plain text
    if ext == ".txt" or "text/plain" in content_type:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()[:MAX_CHARS]
        except Exception:
            return ""

    # Word document
    if ext in (".docx", ".doc") or "wordprocessingml" in content_type:
        text = _extract_docx(file_path)
        if text:
            return text
        logger.info("DOCX has no text - trying Gemini for embedded images")
        return await _extract_with_gemini(file_path)

    # Image files
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff") \
            or (content_type and content_type.startswith("image/")):
        try:
            image = Image.open(file_path)
            text = _extract_with_paddleocr(image)
            if text and len(text.strip()) >= 20:
                return text
            text = _extract_with_tesseract(image)
            if text and len(text.strip()) >= 20:
                return text
            return await _extract_with_gemini(file_path)
        except Exception as e:
            logger.debug("Image open failed: %s", e)
            return await _extract_with_gemini(file_path)

    # PDF
    if ext == ".pdf" or "pdf" in content_type:
        if not _is_scanned_pdf(file_path):
            text = _extract_with_pdfplumber(file_path)
            if text and len(text.strip()) >= MIN_SELECTABLE_CHARS:
                logger.info("Text PDF: %d chars via pdfplumber", len(text))
                return text
            logger.info("PDF has partial text - running full OCR pipeline")
        return await _extract_scanned_pdf(file_path)

    # Unknown
    logger.warning("Unknown type ext=%s - trying local OCR then Gemini", ext)
    try:
        image = Image.open(file_path)
        text = _extract_with_paddleocr(image)
        if text:
            return text
        text = _extract_with_tesseract(image)
        if text:
            return text
    except Exception:
        pass
    return await _extract_with_gemini(file_path)