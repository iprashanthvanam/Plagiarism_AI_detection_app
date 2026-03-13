# import asyncpg
# import os
# from typing import Optional, List, Dict, Any
# import logging
# from datetime import datetime, timedelta, timezone
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from app.env import STORAGE_DIR

# logger = logging.getLogger(__name__)

# RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "365"))


# class DatabaseService:
#     def __init__(self):
#         self.pool: Optional[asyncpg.Pool] = None

#     async def init_db(self):
#         if self.pool:
#             return
#         self.pool = await asyncpg.create_pool(
#             user=os.getenv("DB_USER"),
#             password=os.getenv("DB_PASSWORD"),
#             database=os.getenv("DB_NAME"),
#             host=os.getenv("DB_HOST"),
#             port=int(os.getenv("DB_PORT")),
#         )

#     # ===============================
#     # USER METHODS (IDENTITY FIX)
#     # ===============================

#     async def create_user(
#         self,
#         user_id: str,
#         username: str,
#         role: str,
#         password_hash: str,
#     ):
#         await self.init_db()
#         await self.pool.execute(
#             """
#             INSERT INTO users (user_id, username, role, password_hash)
#             VALUES ($1, $2, $3, $4)
#             ON CONFLICT (username) DO NOTHING
#             """,
#             user_id,
#             username,
#             role,
#             password_hash,
#         )

#     async def get_user_by_id(self, user_id: str):
#         await self.init_db()
#         row = await self.pool.fetchrow(
#             "SELECT * FROM users WHERE user_id = $1",
#             user_id,
#         )
#         return dict(row) if row else None

#     async def get_user_by_username(self, username: str):
#         await self.init_db()
#         row = await self.pool.fetchrow(
#             "SELECT * FROM users WHERE username = $1",
#             username,
#         )
#         return dict(row) if row else None

#     # 🔁 Backward compatibility
#     async def get_user(self, identifier: str):
#         """
#         Compatibility layer:
#         - login → username
#         - JWT → user_id
#         """
#         user = await self.get_user_by_id(identifier)
#         if user:
#             return user
#         return await self.get_user_by_username(identifier)

#     # ===============================
#     # DOCUMENT METHODS
#     # ===============================

#     async def create_document(
#         self, user_id, file_name, content_type, size, file_path
#     ):
#         await self.init_db()
#         row = await self.pool.fetchrow(
#             """
#             INSERT INTO documents (user_id, file_name, content_type, size, file_path)
#             VALUES ($1, $2, $3, $4, $5)
#             RETURNING *
#             """,
#             user_id,
#             file_name,
#             content_type,
#             size,
#             file_path,
#         )
#         return dict(row)

#     async def get_document(self, document_id: int):
#         await self.init_db()
#         row = await self.pool.fetchrow(
#             "SELECT * FROM documents WHERE id = $1",
#             document_id,
#         )
#         return dict(row) if row else None

#     async def get_documents_by_user(self, user_id: str):
#         await self.init_db()
#         rows = await self.pool.fetch(
#             """
#             SELECT id, user_id, file_name, upload_date
#             FROM documents
#             WHERE user_id = $1
#             ORDER BY upload_date DESC
#             """,
#             user_id,
#         )
#         return [dict(r) for r in rows]

#     async def get_all_documents(self):
#         await self.init_db()
#         rows = await self.pool.fetch(
#             "SELECT * FROM documents ORDER BY id DESC"
#         )
#         return [dict(r) for r in rows]

#     # ===============================
#     # TEXT EXTRACTION
#     # ===============================

#     async def store_extracted_text(self, document_id: int, text: str):
#         await self.init_db()
#         await self.pool.execute(
#             """
#             UPDATE documents
#             SET extracted_text = $1
#             WHERE id = $2
#             """,
#             text,
#             document_id,
#         )

#     async def get_all_documents_texts(self, exclude_id: int | None = None):
#         """
#         Get all extracted texts for plagiarism comparison.
#         Simple version without pg_trgm (no similarity ranking).
#         """
#         await self.init_db()
        
#         if exclude_id is not None:
#             rows = await self.pool.fetch(
#                 """
#                 SELECT id, extracted_text
#                 FROM documents
#                 WHERE extracted_text IS NOT NULL AND id != $1
#                 LIMIT 1000
#                 """,
#                 exclude_id,
#             )
#         else:
#             rows = await self.pool.fetch(
#                 """
#                 SELECT id, extracted_text
#                 FROM documents
#                 WHERE extracted_text IS NOT NULL
#                 LIMIT 1000
#                 """
#             )

#         return [{"id": r["id"], "text": r["extracted_text"]} for r in rows]

#     async def get_similar_documents_paginated(
#         self, 
#         exclude_id: int, 
#         limit: int = 100, 
#         offset: int = 0
#     ):
#         """
#         Get similar documents in batches (pagination).
#         Used by plagiarism.py to process large databases in chunks.
#         """
#         await self.init_db()
        
#         current_doc = await self.pool.fetchrow(
#             "SELECT extracted_text FROM documents WHERE id = $1",
#             exclude_id
#         )
        
#         if not current_doc or not current_doc["extracted_text"]:
#             return []
        
#         rows = await self.pool.fetch(
#             """
#             SELECT id, extracted_text,
#                    similarity($1, extracted_text) AS sim_score
#             FROM documents
#             WHERE extracted_text IS NOT NULL
#               AND id != $2
#               AND similarity($1, extracted_text) > 0.1
#             ORDER BY sim_score DESC
#             LIMIT $3 OFFSET $4
#             """,
#             current_doc["extracted_text"],
#             exclude_id,
#             limit,
#             offset,
#         )
        
#         return [{"id": r["id"], "text": r["extracted_text"], "sim": r["sim_score"]} for r in rows]

#     # ===============================
#     # ANALYSIS RESULTS
#     # ===============================

#     async def create_analysis_result(self, result):
#         await self.init_db()
#         await self.pool.execute(
#             """
#             INSERT INTO analysis_results
#             (
#                 document_id,
#                 analyzed_by,
#                 ai_detected_percentage,
#                 web_source_percentage,
#                 local_similarity_percentage,
#                 human_written_percentage,
#                 analysis_summary,
#                 analysis_date,
#                 matched_web_sources,
#                 processing_time_seconds
#             )
#             VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
#             """,
#             result.document_id,
#             result.analyzed_by,
#             result.ai_detected_percentage,
#             result.web_source_percentage,
#             result.local_similarity_percentage,
#             result.human_written_percentage,
#             result.analysis_summary,
#             result.analysis_date,
#             result.matched_web_sources,
#             result.processing_time_seconds,
#         )

#     async def get_analysis_result_for_document(self, document_id: int):
#         await self.init_db()
#         row = await self.pool.fetchrow(
#             """
#             SELECT *
#             FROM analysis_results
#             WHERE document_id = $1
#             ORDER BY analysis_date DESC
#             LIMIT 1
#             """,
#             document_id,
#         )
#         return dict(row) if row else None

#     async def cleanup_old_documents(self):
#         """
#         Delete documents older than RETENTION_DAYS.
#         Removes files from disk and DB records (cascades to analysis_results).
#         """
#         try:
#             import os as os_module
#             cutoff_date = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
#             logger.info("Starting retention cleanup (cutoff: %s, retention: %d days)",
#                         cutoff_date.isoformat(), RETENTION_DAYS)

#             await self.init_db()

#             # Get all documents to be deleted (for file cleanup)
#             old_docs = await self.pool.fetch(
#                 """
#                 SELECT id, file_path
#                 FROM documents
#                 WHERE upload_date < $1
#                 """,
#                 cutoff_date
#             )

#             # Delete files from disk
#             deleted_files = 0
#             for doc in old_docs:
#                 file_path = doc["file_path"]
#                 try:
#                     if os_module.path.exists(file_path):
#                         os_module.remove(file_path)
#                         deleted_files += 1
#                         logger.debug("Deleted file: %s", file_path)
#                 except Exception as e:
#                     logger.warning("Failed to delete file %s: %s", file_path, e)

#             # Delete from DB (cascades to analysis_results via foreign key)
#             deleted_count = await self.pool.execute(
#                 """
#                 DELETE FROM documents
#                 WHERE upload_date < $1
#                 """,
#                 cutoff_date
#             )

#             logger.info(
#                 "Retention cleanup complete: %d documents, %d files deleted",
#                 deleted_count, deleted_files
#             )

#         except Exception as e:
#             logger.exception("Retention cleanup failed: %s", e)


# # ✅ Create singleton AFTER class definition (no circular import)
# db_service = DatabaseService()


# def start_retention_scheduler():
#     """Initialize APScheduler for weekly cleanup."""
#     scheduler = AsyncIOScheduler()

#     # Run every Sunday at 2 AM UTC
#     scheduler.add_job(
#         db_service.cleanup_old_documents,
#         'cron',
#         day_of_week=6,
#         hour=2,
#         minute=0,
#         id='document_retention',
#         name='Weekly document retention cleanup'
#     )

#     scheduler.start()
#     logger.info("Retention scheduler started (weekly, Sunday 2 AM UTC)")
#     return scheduler











import asyncpg
import os
from typing import Optional, List, Dict, Any
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.env import STORAGE_DIR

logger = logging.getLogger(__name__)

RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "365"))


class DatabaseService:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.pool_loop: Optional[asyncio.AbstractEventLoop] = None

    async def init_db(self):
        """
        Initialize database pool safely.

        IMPORTANT:
        Celery workers run in separate processes and event loops.
        asyncpg pools are bound to a specific loop.
        So we must recreate the pool if the loop changes.
        """

        current_loop = asyncio.get_running_loop()

        if self.pool and self.pool_loop == current_loop:
            return

        if self.pool:
            try:
                await self.pool.close()
            except Exception:
                pass

        logger.info("Creating new asyncpg pool for loop %s", id(current_loop))

        self.pool = await asyncpg.create_pool(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            min_size=1,
            max_size=10,
        )

        self.pool_loop = current_loop

    # ===============================
    # USER METHODS
    # ===============================

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

    # ===============================
    # DOCUMENT METHODS
    # ===============================

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
            SELECT id,user_id,file_name,upload_date
            FROM documents
            WHERE user_id=$1
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

    # ===============================
    # TEXT EXTRACTION
    # ===============================

    async def store_extracted_text(self, document_id: int, text: str):
        await self.init_db()

        await self.pool.execute(
            """
            UPDATE documents
            SET extracted_text=$1
            WHERE id=$2
            """,
            text,
            document_id,
        )

    async def get_all_documents_texts(self, exclude_id: int | None = None):
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
            "SELECT extracted_text FROM documents WHERE id=$1",
            exclude_id,
        )

        if not current_doc or not current_doc["extracted_text"]:
            return []

        rows = await self.pool.fetch(
            """
            SELECT id, extracted_text,
                   similarity($1,extracted_text) AS sim_score
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

    # ===============================
    # ANALYSIS RESULTS
    # ===============================

    async def create_analysis_result(self, result):
        await self.init_db()

        await self.pool.execute(
            """
            INSERT INTO analysis_results
            (
                document_id,
                analyzed_by,
                ai_detected_percentage,
                web_source_percentage,
                local_similarity_percentage,
                human_written_percentage,
                analysis_summary,
                analysis_date,
                matched_web_sources,
                processing_time_seconds
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """,
            result.document_id,
            result.analyzed_by,
            result.ai_detected_percentage,
            result.web_source_percentage,
            result.local_similarity_percentage,
            result.human_written_percentage,
            result.analysis_summary,
            result.analysis_date,
            result.matched_web_sources,
            result.processing_time_seconds,
        )

    async def get_analysis_result_for_document(self, document_id: int):
        await self.init_db()

        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM analysis_results
            WHERE document_id=$1
            ORDER BY analysis_date DESC
            LIMIT 1
            """,
            document_id,
        )

        return dict(row) if row else None

    # ===============================
    # RETENTION CLEANUP
    # ===============================

    async def cleanup_old_documents(self):
        try:
            import os as os_module

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

            logger.info(
                "Starting retention cleanup cutoff=%s",
                cutoff_date.isoformat(),
            )

            await self.init_db()

            old_docs = await self.pool.fetch(
                """
                SELECT id,file_path
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
                    logger.warning("Failed deleting %s : %s", path, e)

            deleted_count = await self.pool.execute(
                """
                DELETE FROM documents
                WHERE upload_date < $1
                """,
                cutoff_date,
            )

            logger.info(
                "Cleanup complete docs=%s files=%s",
                deleted_count,
                deleted_files,
            )

        except Exception as e:
            logger.exception("Retention cleanup failed: %s", e)


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