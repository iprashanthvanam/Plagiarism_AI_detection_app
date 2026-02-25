









# import os
# import mimetypes
# import logging
# from typing import Optional

# import pandas as pd
# import pdfplumber
# from docx import Document
# from pptx import Presentation

# from app.libs.gemini_service import extract_text_with_gemini


# logger = logging.getLogger(__name__)



# async def extract_text(file_path: str, content_type: Optional[str] = None) -> str:
#     """
#     Unified extraction entrypoint.
#     MUST return str (never None).
#     """
#     if not os.path.exists(file_path):
#         logger.error("File does not exist: %s", file_path)
#         return ""

#     ext = os.path.splitext(file_path)[1].lower()
#     mime, _ = mimetypes.guess_type(file_path)

#     try:
#         # ---------- TXT ----------
#         if ext == ".txt":
#             with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
#                 return f.read()

#         # ---------- DOCX ----------
#         if ext == ".docx":
#             doc = Document(file_path)
#             return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

#         # ---------- DOC (fallback to Gemini OCR) ----------
#         if ext == ".doc":
#             logger.info("Routing .doc to Gemini OCR")
#             if extract_text_with_gemini:
#                 return await extract_text_with_gemini(file_path, is_pdf=False)
#             else:
#                 logger.warning("Gemini disabled due to dependency conflict")
#             return ""


#         # ---------- XLSX ----------
#         if ext == ".xlsx":
#             dfs = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
#             return "\n".join(
#                 df.astype(str).to_string(index=False) for df in dfs.values()
#             )

#         # ---------- XLS ----------
#         if ext == ".xls":
#             dfs = pd.read_excel(file_path, sheet_name=None, engine="xlrd")
#             return "\n".join(
#                 df.astype(str).to_string(index=False) for df in dfs.values()
#             )

#         # ---------- PPTX ----------
#         if ext == ".pptx":
#             prs = Presentation(file_path)
#             slides_text = []
#             for slide in prs.slides:
#                 for shape in slide.shapes:
#                     if hasattr(shape, "text"):
#                         slides_text.append(shape.text)
#             return "\n".join(slides_text)

#         # ---------- PPT (unsupported but safe) ----------
#         if ext == ".ppt":
#             logger.warning(".ppt format not supported; skipping")
#             return ""

#         # ---------- PDF ----------
#         if ext == ".pdf":
#             text = ""
#             with pdfplumber.open(file_path) as pdf:
#                 for page in pdf.pages:
#                     page_text = page.extract_text() or ""
#                     text += page_text + "\n"

#             if text.strip():
#                 return text

#             logger.info("PDF appears scanned; routing to Gemini OCR")
#             if extract_text_with_gemini:
#                 return await extract_text_with_gemini(file_path, is_pdf=False)
#             else:
#                 logger.warning("Gemini disabled due to dependency conflict")
#             return ""

#         # ---------- IMAGES ----------
#         if ext in [".png", ".jpg", ".jpeg"]:
#             if extract_text_with_gemini:
#                 return await extract_text_with_gemini(file_path, is_pdf=False)
#             else:
#                 logger.warning("Gemini disabled due to dependency conflict")
#             return ""

#         logger.warning("Unsupported file type: %s", ext)
#         return ""

#     except Exception as e:
#         logger.exception("Text extraction failed: %s", e)
#         return ""



# try:
#     from app.libs.gemini_service import extract_text_with_gemini
# except Exception:
#     extract_text_with_gemini = None
























# # backend/app/libs/extract.py

# import os
# import mimetypes
# import logging
# import re
# from typing import Optional

# import pandas as pd
# import pdfplumber
# from docx import Document
# from pptx import Presentation

# from app.libs.gemini_service import extract_text_with_gemini

# logger = logging.getLogger(__name__)


# def normalize_text(text: str) -> str:
#     """
#     Makes extracted text Google-search friendly.
#     """
#     text = text.replace("\n", " ")
#     text = re.sub(r"\s+", " ", text)
#     return text.strip()


# async def extract_text(file_path: str, content_type: Optional[str] = None) -> str:
#     if not os.path.exists(file_path):
#         logger.error("File does not exist: %s", file_path)
#         return ""

#     ext = os.path.splitext(file_path)[1].lower()

#     try:
#         # TXT
#         if ext == ".txt":
#             with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
#                 return normalize_text(f.read())

#         # DOCX
#         if ext == ".docx":
#             doc = Document(file_path)
#             text = " ".join(p.text for p in doc.paragraphs if p.text.strip())
#             return normalize_text(text)

#         # DOC (OCR)
#         if ext == ".doc":
#             if extract_text_with_gemini:
#                 text = await extract_text_with_gemini(file_path, is_pdf=False)
#                 return normalize_text(text)
#             return ""

#         # XLSX
#         if ext == ".xlsx":
#             dfs = pd.read_excel(file_path, sheet_name=None)
#             text = " ".join(df.astype(str).to_string(index=False) for df in dfs.values())
#             return normalize_text(text)

#         # XLS
#         if ext == ".xls":
#             dfs = pd.read_excel(file_path, sheet_name=None)
#             text = " ".join(df.astype(str).to_string(index=False) for df in dfs.values())
#             return normalize_text(text)

#         # PPTX
#         if ext == ".pptx":
#             prs = Presentation(file_path)
#             slides = []
#             for slide in prs.slides:
#                 for shape in slide.shapes:
#                     if hasattr(shape, "text"):
#                         slides.append(shape.text)
#             return normalize_text(" ".join(slides))

#         # PDF
#         if ext == ".pdf":
#             pages = []
#             with pdfplumber.open(file_path) as pdf:
#                 for page in pdf.pages:
#                     t = page.extract_text()
#                     if t:
#                         pages.append(t)

#             text = normalize_text(" ".join(pages))
#             if text:
#                 return text

#             # OCR fallback
#             if extract_text_with_gemini:
#                 return normalize_text(await extract_text_with_gemini(file_path, is_pdf=True))
#             return ""

#         # IMAGES
#         if ext in [".png", ".jpg", ".jpeg"]:
#             if extract_text_with_gemini:
#                 return normalize_text(await extract_text_with_gemini(file_path, is_pdf=False))
#             return ""

#         return ""

#     except Exception as e:
#         logger.exception("Extraction failed: %s", e)
#         return ""





































# import os
# import re
# import asyncio
# import logging
# from typing import Optional

# import pandas as pd
# import pdfplumber
# from docx import Document
# from pptx import Presentation

# from app.libs.gemini_service import extract_text_with_gemini
# from app.core.gemini_queue import run_gemini_task

# logger = logging.getLogger(__name__)

# GEMINI_RETRIES = 3
# GEMINI_BASE_DELAY = 2


# def normalize_text(text: str) -> str:
#     text = re.sub(r"[^\w\s\.\+\-\=\(\)\{\}<>/]", " ", text)
#     text = re.sub(r"\s+", " ", text)
#     return text.strip()


# async def _gemini_retry(file_path: str, is_pdf: bool) -> str:
#     delay = GEMINI_BASE_DELAY
#     for _ in range(GEMINI_RETRIES):
#         try:
#             text = await run_gemini_task(extract_text_with_gemini(file_path, is_pdf=is_pdf))
            
#             if text and len(text.strip()) > 50:
#                 return normalize_text(text)
#         except Exception:
#             await asyncio.sleep(delay)
#             delay *= 2
#     return ""


# async def extract_text(file_path: str, content_type: Optional[str] = None) -> str:
#     if not os.path.exists(file_path):
#         return ""

#     ext = os.path.splitext(file_path)[1].lower()

#     gemini_text = await _gemini_retry(file_path, is_pdf=(ext == ".pdf"))
#     if gemini_text:
#         return gemini_text

#     try:
#         if ext == ".txt":
#             with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
#                 return normalize_text(f.read())

#         if ext == ".docx":
#             doc = Document(file_path)
#             text = " ".join(p.text for p in doc.paragraphs if p.text.strip())
#             return normalize_text(text)

#         if ext in [".xls", ".xlsx"]:
#             dfs = pd.read_excel(file_path, sheet_name=None)
#             text = " ".join(
#                 df.astype(str).to_string(index=False) for df in dfs.values()
#             )
#             return normalize_text(text)

#         if ext == ".pptx":
#             prs = Presentation(file_path)
#             slides = []
#             for slide in prs.slides:
#                 for shape in slide.shapes:
#                     if hasattr(shape, "text"):
#                         slides.append(shape.text)
#             return normalize_text(" ".join(slides))

#         if ext == ".pdf":
#             pages = []
#             with pdfplumber.open(file_path) as pdf:
#                 for page in pdf.pages:
#                     t = page.extract_text()
#                     if t:
#                         pages.append(t)
#             return normalize_text(" ".join(pages))

#     except Exception:
#         pass

#     return ""




































































# import os
# import mimetypes
# import logging
# from typing import Optional

# import pandas as pd
# import pdfplumber
# from docx import Document
# from pptx import Presentation

# from app.libs.gemini_service import extract_text_with_gemini


# logger = logging.getLogger(__name__)



# async def extract_text(file_path: str, content_type: Optional[str] = None) -> str:
#     """
#     Unified extraction entrypoint.
#     MUST return str (never None).
#     """
#     if not os.path.exists(file_path):
#         logger.error("File does not exist: %s", file_path)
#         return ""

#     ext = os.path.splitext(file_path)[1].lower()
#     mime, _ = mimetypes.guess_type(file_path)

#     try:
#         # ---------- TXT ----------
#         if ext == ".txt":
#             with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
#                 return f.read()

#         # ---------- DOCX ----------
#         if ext == ".docx":
#             doc = Document(file_path)
#             return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

#         # ---------- DOC (fallback to Gemini OCR) ----------
#         if ext == ".doc":
#             logger.info("Routing .doc to Gemini OCR")
#             if extract_text_with_gemini:
#                 return await extract_text_with_gemini(file_path, is_pdf=False)
#             else:
#                 logger.warning("Gemini disabled due to dependency conflict")
#             return ""


#         # ---------- XLSX ----------
#         if ext == ".xlsx":
#             dfs = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
#             return "\n".join(
#                 df.astype(str).to_string(index=False) for df in dfs.values()
#             )

#         # ---------- XLS ----------
#         if ext == ".xls":
#             dfs = pd.read_excel(file_path, sheet_name=None, engine="xlrd")
#             return "\n".join(
#                 df.astype(str).to_string(index=False) for df in dfs.values()
#             )

#         # ---------- PPTX ----------
#         if ext == ".pptx":
#             prs = Presentation(file_path)
#             slides_text = []
#             for slide in prs.slides:
#                 for shape in slide.shapes:
#                     if hasattr(shape, "text"):
#                         slides_text.append(shape.text)
#             return "\n".join(slides_text)

#         # ---------- PPT (unsupported but safe) ----------
#         if ext == ".ppt":
#             logger.warning(".ppt format not supported; skipping")
#             return ""

#         # ---------- PDF ----------
#         if ext == ".pdf":
#             text = ""
#             with pdfplumber.open(file_path) as pdf:
#                 for page in pdf.pages:
#                     page_text = page.extract_text() or ""
#                     text += page_text + "\n"

#             if text.strip():
#                 return text

#             logger.info("PDF appears scanned; routing to Gemini OCR")
#             if extract_text_with_gemini:
#                 return await extract_text_with_gemini(file_path, is_pdf=False)
#             else:
#                 logger.warning("Gemini disabled due to dependency conflict")
#             return ""

#         # ---------- IMAGES ----------
#         if ext in [".png", ".jpg", ".jpeg"]:
#             if extract_text_with_gemini:
#                 return await extract_text_with_gemini(file_path, is_pdf=False)
#             else:
#                 logger.warning("Gemini disabled due to dependency conflict")
#             return ""

#         logger.warning("Unsupported file type: %s", ext)
#         return ""

#     except Exception as e:
#         logger.exception("Text extraction failed: %s", e)
#         return ""



# try:
#     from app.libs.gemini_service import extract_text_with_gemini
# except Exception:
#     extract_text_with_gemini = None































import os
import re
import logging
import tempfile
import shutil as _shutil
from typing import Optional

import pandas as pd
import pdfplumber
from docx import Document
from pptx import Presentation

logger = logging.getLogger(__name__)

# ============================================================
# LOCAL OCR IMPORTS (optional — graceful degradation)
# ============================================================
try:
    import pytesseract
    from PIL import Image
    _tesseract_available = True
except ImportError:
    _tesseract_available = False
    logger.warning("pytesseract/Pillow not installed — image OCR falls back to Gemini")

try:
    from pdf2image import convert_from_path
    _pdf2image_available = True
except ImportError:
    _pdf2image_available = False
    logger.warning("pdf2image not installed — scanned PDF OCR falls back to Gemini")

# ============================================================
# GEMINI FALLBACK IMPORT
# ============================================================
try:
    from app.libs.gemini_service import extract_text_with_gemini
    _gemini_available = True
except Exception as e:
    logger.warning("Gemini service unavailable: %s", e)
    extract_text_with_gemini = None
    _gemini_available = False

# Minimum chars to consider local extraction successful
MIN_LOCAL_TEXT = 50

# Noise tokens found in .doc OLE metadata / font tables — filtered out
_DOC_NOISE = {
    "Times New Roman", "Liberation Serif", "Liberation Sans", "DejaVu Sans",
    "Open Sans", "FreeSans", "OpenSymbol", "Arial Unicode MS", "Droid Sans",
    "Fallback", "Symbol", "Arial", "Heading", "oasis.open", "office.com",
    "Visited Internet Link", "Internet Link", "Root Entry", "WordDocument",
}


# ============================================================
# LOCAL EXTRACTION HELPERS
# ============================================================

def _extract_doc_binary(file_path: str) -> str:
    """
    Extract body text from a legacy .doc (binary OLE / Word 97-2003) file.

    Method: Word stores document body text as UTF-16LE strings inside the
    OLE binary. We scan for runs of printable UTF-16LE characters (≥8 chars),
    decode them, and filter out known OLE metadata / font name noise.

    No external tools or libraries required — pure Python, no API calls.
    Works on any .doc file regardless of filename length.
    """
    try:
        abs_path = os.path.abspath(file_path)
        with open(abs_path, "rb") as f:
            data = f.read()

        # Find all runs of printable UTF-16LE characters (≥8 chars = ≥16 bytes)
        # Pattern: each char is one printable ASCII byte followed by \x00
        chunks = re.findall(b"(?:[\x20-\x7e]\x00){8,}", data)

        text_parts = []
        for chunk in chunks:
            try:
                decoded = chunk.decode("utf-16-le", errors="ignore").strip()
            except Exception:
                continue

            # Skip short segments
            if len(decoded) < 15:
                continue

            # Skip known OLE metadata / font name noise
            if any(noise in decoded for noise in _DOC_NOISE):
                continue

            text_parts.append(decoded)

        result = "\n".join(text_parts)
        logger.info(
            ".doc extracted via binary UTF-16LE scan: %s (%d chars)",
            os.path.basename(file_path), len(result)
        )
        return result

    except Exception as e:
        logger.warning("Binary .doc extraction failed for %s: %s", file_path, e)
        return ""


def _extract_image_local(file_path: str) -> str:
    """OCR an image using Tesseract. Returns text or ''."""
    if not _tesseract_available:
        return ""
    try:
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img, timeout=30)
        return text.strip()
    except Exception as e:
        logger.warning("Tesseract OCR failed for %s: %s", file_path, e)
        return ""


def _extract_scanned_pdf_local(file_path: str) -> str:
    """Convert scanned PDF pages to images and OCR with Tesseract."""
    if not _pdf2image_available or not _tesseract_available:
        return ""
    try:
        pages = convert_from_path(file_path, dpi=200, first_page=1, last_page=15)
        texts = []
        for i, page in enumerate(pages):
            try:
                page_text = pytesseract.image_to_string(page, timeout=30)
                if page_text.strip():
                    texts.append(page_text.strip())
            except Exception as e:
                logger.warning("Tesseract failed on PDF page %d: %s", i + 1, e)
        return "\n".join(texts)
    except Exception as e:
        logger.warning("pdf2image+tesseract failed for %s: %s", file_path, e)
        return ""


async def _gemini_fallback(file_path: str) -> str:
    """Try Gemini OCR as absolute last resort. Returns '' if unavailable."""
    if _gemini_available and extract_text_with_gemini:
        try:
            result = await extract_text_with_gemini(file_path)
            return result or ""
        except Exception as e:
            logger.warning("Gemini fallback failed for %s: %s", file_path, e)
    return ""


# ============================================================
# MAIN EXTRACTION ENTRYPOINT
# ============================================================
async def extract_text(file_path: str, content_type: Optional[str] = None) -> str:
    """
    Unified text extraction — fully local, Gemini only as last resort.

    Format       | Method                           | External tool?
    -------------|----------------------------------|----------------
    .txt         | open() read                      | None
    .docx        | python-docx                      | None
    .doc         | Binary UTF-16LE scan             | None ✅
    .xlsx/.xls   | pandas                           | None
    .pptx        | python-pptx                      | None
    .pdf digital | pdfplumber                       | None
    .pdf scanned | pdf2image + Tesseract            | tesseract-ocr
    .png/.jpg    | Tesseract                        | tesseract-ocr
    Any above    | Gemini OCR (only if local fails) | API key needed

    Always returns str. Never raises. Never stores error message strings.
    """
    # Resolve to absolute path — relative paths cause silent failures
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        logger.error("File not found: %s (resolved: %s)", file_path, abs_path)
        return ""
    file_path = abs_path

    ext = os.path.splitext(file_path)[1].lower()

    try:
        # ----------------------------------------------------------------
        # TXT
        # ----------------------------------------------------------------
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        # ----------------------------------------------------------------
        # DOCX — python-docx
        # ----------------------------------------------------------------
        if ext == ".docx":
            doc = Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

        # ----------------------------------------------------------------
        # DOC — Binary UTF-16LE scan (no external tools, no API)
        # Word stores body text as UTF-16LE inside the OLE binary structure.
        # We scan for those char runs and filter out metadata noise.
        # ----------------------------------------------------------------
        if ext == ".doc":
            text = _extract_doc_binary(file_path)
            if text and len(text) >= MIN_LOCAL_TEXT:
                return text
            logger.info(
                ".doc binary extraction returned %d chars — trying Gemini: %s",
                len(text), os.path.basename(file_path)
            )
            return await _gemini_fallback(file_path)

        # ----------------------------------------------------------------
        # XLSX
        # ----------------------------------------------------------------
        if ext == ".xlsx":
            dfs = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
            return "\n".join(
                df.astype(str).to_string(index=False) for df in dfs.values()
            )

        # ----------------------------------------------------------------
        # XLS
        # ----------------------------------------------------------------
        if ext == ".xls":
            dfs = pd.read_excel(file_path, sheet_name=None, engine="xlrd")
            return "\n".join(
                df.astype(str).to_string(index=False) for df in dfs.values()
            )

        # ----------------------------------------------------------------
        # PPTX
        # ----------------------------------------------------------------
        if ext == ".pptx":
            prs = Presentation(file_path)
            return "\n".join(
                shape.text
                for slide in prs.slides
                for shape in slide.shapes
                if hasattr(shape, "text")
            )

        # ----------------------------------------------------------------
        # PPT (unsupported natively)
        # ----------------------------------------------------------------
        if ext == ".ppt":
            logger.warning(".ppt not supported for local extraction")
            return ""

        # ----------------------------------------------------------------
        # PDF — 3-stage pipeline
        # ----------------------------------------------------------------
        if ext == ".pdf":
            # Stage 1: pdfplumber (digital PDFs — instant, no OCR)
            text = ""
            try:
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text += (page.extract_text() or "") + "\n"
            except Exception as e:
                logger.warning("pdfplumber failed for %s: %s", file_path, e)

            if text.strip() and len(text.strip()) >= MIN_LOCAL_TEXT:
                logger.info("PDF (digital) via pdfplumber: %s (%d chars)",
                            os.path.basename(file_path), len(text.strip()))
                return text

            # Stage 2: Scanned PDF → pdf2image + Tesseract
            logger.info("PDF appears scanned — trying local OCR: %s",
                        os.path.basename(file_path))
            text = _extract_scanned_pdf_local(file_path)
            if text and len(text) >= MIN_LOCAL_TEXT:
                logger.info("Scanned PDF via local OCR: %s (%d chars)",
                            os.path.basename(file_path), len(text))
                return text

            # Stage 3: Gemini (last resort)
            logger.info("Local OCR returned %d chars — trying Gemini: %s",
                        len(text), os.path.basename(file_path))
            return await _gemini_fallback(file_path)

        # ----------------------------------------------------------------
        # IMAGES — Tesseract first, Gemini fallback
        # ----------------------------------------------------------------
        if ext in [".png", ".jpg", ".jpeg"]:
            logger.info("Extracting image via Tesseract: %s",
                        os.path.basename(file_path))
            text = _extract_image_local(file_path)
            if text and len(text) >= MIN_LOCAL_TEXT:
                logger.info("Image via Tesseract: %s (%d chars)",
                            os.path.basename(file_path), len(text))
                return text
            logger.info("Tesseract returned %d chars — trying Gemini: %s",
                        len(text), os.path.basename(file_path))
            return await _gemini_fallback(file_path)

        logger.warning("Unsupported file type: %s", ext)
        return ""

    except Exception as e:
        logger.exception("Text extraction failed for %s: %s", file_path, e)
        return ""