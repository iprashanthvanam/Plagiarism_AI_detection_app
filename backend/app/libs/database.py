import asyncpg
import os
import json  # ✅ ADD THIS (needed for json.dumps in create_analysis_result)
from typing import Optional, List, Dict, Any, Tuple
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.env import STORAGE_DIR
from app.libs.models import AnalysisResult  # ✅ ADD THIS

logger = logging.getLogger(__name__)

RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "365"))


class DatabaseService:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.pool_loop: Optional[asyncio.AbstractEventLoop] = None

    async def init_db(self):
        """
        Initialize the asyncpg connection pool.

        CELERY WORKER COMPATIBILITY:
        ─────────────────────────────
        asyncpg pools are bound to the event loop they were created on.

        In FastAPI (uvicorn): one long-lived event loop → pool created once,
        reused for all requests. No issues.

        In Celery workers: tasks.py uses a PERSISTENT event loop via
        _get_worker_loop(). This means the loop is the SAME for every task
        on a given worker process. init_db() creates the pool once on first
        task, then reuses it for all subsequent tasks on the same worker.

        FIX vs old code:
        ─────────────────
        Old code tried: await self.pool.close() when loop changed.
        This was WRONG — closing a pool whose event loop is already
        destroyed causes asyncpg to hang while waiting for orphaned
        file descriptors. Even with try/except, the NEW pool creation
        after that would also hang.

        New code: when loop changes (e.g. between uvicorn and Celery worker
        processes), set self.pool = None WITHOUT trying to close the old pool.
        The OS reclaims those connections when the old process/loop exits.
        The new pool is created cleanly for the current loop.
        """
        current_loop = asyncio.get_running_loop()

        # Pool already valid for this exact loop — reuse it
        if self.pool is not None and self.pool_loop is current_loop:
            return

        # Loop changed (different process or worker startup):
        # Do NOT try to await self.pool.close() — the old loop may be
        # closed/destroyed, which causes asyncpg to hang indefinitely.
        # Just discard the old pool reference; the OS will clean up the
        # underlying connections when the old event loop is gone.
        if self.pool is not None and self.pool_loop is not current_loop:
            logger.info(
                "Event loop changed (old=%s new=%s) — discarding old pool without close",
                id(self.pool_loop), id(current_loop),
            )
            self.pool = None
            self.pool_loop = None

        # Create fresh pool for the current event loop
        logger.info("Creating asyncpg pool for loop %s", id(current_loop))

        self.pool = await asyncpg.create_pool(
            user     = os.getenv("DB_USER"),
            password = os.getenv("DB_PASSWORD"),
            database = os.getenv("DB_NAME"),
            host     = os.getenv("DB_HOST"),
            port     = int(os.getenv("DB_PORT", "5432")),
            min_size = 1,
            max_size = 10,
        )

        self.pool_loop = current_loop
        logger.info("asyncpg pool ready (loop=%s)", id(current_loop))

    # ═══════════════════════════════════════════════
    # USER METHODS
    # ═══════════════════════════════════════════════

    async def create_user(
        self,
        user_id: str,
        username: str,
        role: str,
        password_hash: str,
    ):
        await self.init_db()
        await self.pool.execute(
            """
            INSERT INTO users (user_id, username, role, password_hash)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (username) DO NOTHING
            """,
            user_id,
            username,
            role,
            password_hash,
        )

    async def get_user_by_id(self, user_id: str):
        await self.init_db()
        row = await self.pool.fetchrow(
            "SELECT * FROM users WHERE user_id = $1",
            user_id,
        )
        return dict(row) if row else None

    async def get_user_by_username(self, username: str):
        await self.init_db()
        row = await self.pool.fetchrow(
            "SELECT * FROM users WHERE username = $1",
            username,
        )
        return dict(row) if row else None

    async def get_user(self, identifier: str):
        user = await self.get_user_by_id(identifier)
        if user:
            return user
        return await self.get_user_by_username(identifier)

    # ═══════════════════════════════════════════════
    # DOCUMENT METHODS
    # ═══════════════════════════════════════════════

    async def create_document(
        self, user_id, file_name, content_type, size, file_path
    ):
        await self.init_db()
        row = await self.pool.fetchrow(
            """
            INSERT INTO documents (user_id, file_name, content_type, size, file_path)
            VALUES ($1,$2,$3,$4,$5)
            RETURNING *
            """,
            user_id,
            file_name,
            content_type,
            size,
            file_path,
        )
        return dict(row)

    async def get_document(self, document_id: int):
        await self.init_db()
        row = await self.pool.fetchrow(
            "SELECT * FROM documents WHERE id = $1",
            document_id,
        )
        return dict(row) if row else None

    async def get_documents_by_user(self, user_id: str):
        await self.init_db()
        rows = await self.pool.fetch(
            """
            SELECT id, user_id, file_name, upload_date
            FROM documents
            WHERE user_id = $1
            ORDER BY upload_date DESC
            """,
            user_id,
        )
        return [dict(r) for r in rows]

    async def get_all_documents(self):
        await self.init_db()
        rows = await self.pool.fetch(
            "SELECT * FROM documents ORDER BY id DESC"
        )
        return [dict(r) for r in rows]

    # ═══════════════════════════════════════════════
    # TEXT EXTRACTION
    # ═══════════════════════════════════════════════

    async def store_extracted_text(self, document_id: int, text: str) -> Tuple[bool, int]:
        """
        Store extracted text with validation.
        
        ✅ NEW: Returns (success, stored_length)
        ✅ NEW: Validates that full text was stored
        ✅ NEW: Sets extraction_complete flag
        
        Returns:
            (success, actual_stored_length)
            - success: True if text stored completely
            - actual_stored_length: Characters actually stored in DB
        """
        await self.init_db()
        
        if not text:
            logger.warning("Attempt to store empty text for doc %d", document_id)
            return False, 0
        
        original_length = len(text)
        
        try:
            # Store text + metadata
            await self.pool.execute(
                """
                UPDATE documents
                SET extracted_text = $1,
                    extracted_text_length = $2,
                    extraction_complete = $3
                WHERE id = $4
                """,
                text,
                original_length,
                True,  # ✅ Mark extraction as complete
                document_id,
            )
            
            # ✅ VALIDATION: Read back what was actually stored
            row = await self.pool.fetchrow(
                """
                SELECT extracted_text, extracted_text_length
                FROM documents
                WHERE id = $1
                """,
                document_id,
            )
            
            if not row:
                logger.error("Could not verify stored text for doc %d", document_id)
                return False, 0
            
            stored_text = row["extracted_text"]
            stored_length = len(stored_text) if stored_text else 0
            
            # ✅ CRITICAL CHECK: Did we lose data?
            if stored_length < original_length * 0.99:  # Allow 1% loss for encoding
                logger.error(
                    "❌ TEXT TRUNCATION DETECTED for doc %d: "
                    "Sent %d chars, got back %d chars (%.1f%% loss)",
                    document_id, original_length, stored_length,
                    (1 - stored_length / original_length) * 100
                )
                # Mark as incomplete
                await self.pool.execute(
                    "UPDATE documents SET extraction_complete = FALSE WHERE id = $1",
                    document_id,
                )
                return False, stored_length
            
            logger.info(
                "✅ Text stored successfully for doc %d: %d chars (%.1f%% verified)",
                document_id, stored_length,
                (stored_length / original_length) * 100
            )
            return True, stored_length
        
        except Exception as e:
            logger.error("Failed to store text for doc %d: %s", document_id, e)
            return False, 0

    async def get_document_with_validation(self, document_id: int):
        """
        Fetch document + verify extraction completeness.
        Alerts if text was truncated.
        """
        await self.init_db()
        row = await self.pool.fetchrow(
            """
            SELECT id, user_id, file_name, content_type, size,
                   extracted_text, extracted_text_length,
                   extraction_complete, upload_date
            FROM documents
            WHERE id = $1
            """,
            document_id,
        )
        
        if not row:
            return None
        
        doc = dict(row)
        
        # ✅ Alert if extraction was incomplete
        if not doc.get("extraction_complete"):
            logger.warning(
                "⚠️ Document %d extraction marked INCOMPLETE. "
                "Stored text may be truncated or partial.",
                document_id
            )
        
        return doc

    async def get_all_documents_texts(self, exclude_id: Optional[int] = None):
        await self.init_db()
        if exclude_id is not None:
            rows = await self.pool.fetch(
                """
                SELECT id, extracted_text
                FROM documents
                WHERE extracted_text IS NOT NULL
                AND id != $1
                LIMIT 1000
                """,
                exclude_id,
            )
        else:
            rows = await self.pool.fetch(
                """
                SELECT id, extracted_text
                FROM documents
                WHERE extracted_text IS NOT NULL
                LIMIT 1000
                """
            )
        return [{"id": r["id"], "text": r["extracted_text"]} for r in rows]

    async def get_similar_documents_paginated(
        self,
        exclude_id: int,
        limit: int = 100,
        offset: int = 0,
    ):
        await self.init_db()
        current_doc = await self.pool.fetchrow(
            "SELECT extracted_text FROM documents WHERE id = $1",
            exclude_id,
        )
        if not current_doc or not current_doc["extracted_text"]:
            return []
        rows = await self.pool.fetch(
            """
            SELECT id, extracted_text,
                   similarity($1, extracted_text) AS sim_score
            FROM documents
            WHERE extracted_text IS NOT NULL
            AND id != $2
            AND similarity($1, extracted_text) > 0.1
            ORDER BY sim_score DESC
            LIMIT $3 OFFSET $4
            """,
            current_doc["extracted_text"],
            exclude_id,
            limit,
            offset,
        )
        return [
            {"id": r["id"], "text": r["extracted_text"], "sim": r["sim_score"]}
            for r in rows
        ]

    # ═══════════════════════════════════════════════
    # ANALYSIS RESULTS
    # ═══════════════════════════════════════════════

    async def create_analysis_result(self, result: AnalysisResult) -> int:
        """
        Store analysis result in database.
        ✅ Stores sentence_source_map as JSONB (not text array)
        """
        await self.init_db()
        
        # Convert sentence_source_map dict to JSON
        sentence_map_json = json.dumps(result.sentence_source_map or {})
        
        result_id = await self.pool.fetchval(
            """
            INSERT INTO public.analysis_results (
                document_id,
                analyzed_by,
                ai_detected_percentage,
                web_source_percentage,
                local_similarity_percentage,
                human_written_percentage,
                analysis_summary,
                matched_web_sources,
                sentence_source_map,
                processing_time_seconds,
                analysis_date
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
            """,
            result.document_id,
            result.analyzed_by,
            result.ai_detected_percentage,
            result.web_source_percentage,
            result.local_similarity_percentage,
            result.human_written_percentage,
            result.analysis_summary,
            result.matched_web_sources,
            sentence_map_json,  # ✅ Store as JSONB
            result.processing_time_seconds,
            result.analysis_date,
        )
        
        logger.info(
            "Created analysis result %d with %d sentence mappings",
            result_id, len(result.sentence_source_map or {})
        )
        return result_id

    async def get_analysis_result_for_document(self, document_id: int):
        await self.init_db()
        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM analysis_results
            WHERE document_id = $1
            ORDER BY analysis_date DESC
            LIMIT 1
            """,
            document_id,
        )
        return dict(row) if row else None

    # ═══════════════════════════════════════════════
    # RETENTION CLEANUP
    # ═══════════════════════════════════════════════

    async def cleanup_old_documents(self):
        try:
            import os as os_module

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
            logger.info("Starting retention cleanup cutoff=%s", cutoff_date.isoformat())

            await self.init_db()

            old_docs = await self.pool.fetch(
                """
                SELECT id, file_path
                FROM documents
                WHERE upload_date < $1
                """,
                cutoff_date,
            )

            deleted_files = 0
            for doc in old_docs:
                path = doc["file_path"]
                try:
                    if os_module.path.exists(path):
                        os_module.remove(path)
                        deleted_files += 1
                except Exception as e:
                    logger.warning("Failed deleting %s: %s", path, e)

            deleted_count = await self.pool.execute(
                """
                DELETE FROM documents
                WHERE upload_date < $1
                """,
                cutoff_date,
            )

            logger.info(
                "Cleanup complete docs=%s files=%d", deleted_count, deleted_files
            )

        except Exception as e:
            logger.exception("Retention cleanup failed: %s", e)


# ── Module-level singleton — shared by FastAPI and Celery worker (separate processes)
db_service = DatabaseService()


def start_retention_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        db_service.cleanup_old_documents,
        "cron",
        day_of_week=6,
        hour=2,
        minute=0,
        id="document_retention",
    )
    scheduler.start()
    logger.info("Retention scheduler started")
    return scheduler