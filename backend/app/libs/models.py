from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

@dataclass
class User:
    user_id: str
    username: str
    role: str
    password_hash: str


@dataclass
class Document:
    id: int
    user_id: str
    file_name: str
    content_type: str
    size: int
    file_path: str
    upload_date: datetime
    extracted_text: Optional[str] = None


@dataclass
class AnalysisResult:
    document_id: int
    analyzed_by: str
    ai_detected_percentage: float
    web_source_percentage: float
    local_similarity_percentage: float
    human_written_percentage: float
    analysis_summary: str
    analysis_date: datetime
    matched_web_sources: Optional[List[str]] = None
    processing_time_seconds: Optional[float] = None
    sentence_source_map: Optional[Dict[str, int]] = None  # ✅ NEW: Sentence → source index
