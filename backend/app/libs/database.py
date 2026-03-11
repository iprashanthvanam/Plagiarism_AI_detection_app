

import asyncpg
import os
from typing import Optional, List, Dict, Any


class DatabaseService:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def init_db(self):
        if self.pool:
            return
        self.pool = await asyncpg.create_pool(
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
)


    # ===============================
    # USER METHODS (IDENTITY FIX)
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

    # 🔁 Backward compatibility
    async def get_user(self, identifier: str):
        """
        Compatibility layer:
        - login → username
        - JWT → user_id
        """
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
            VALUES ($1, $2, $3, $4, $5)
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

    # ===============================
    # TEXT EXTRACTION
    # ===============================

    async def store_extracted_text(self, document_id: int, text: str):
        await self.init_db()
        await self.pool.execute(
            """
            UPDATE documents
            SET extracted_text = $1
            WHERE id = $2
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
                """,
                exclude_id,
            )
        else:
            rows = await self.pool.fetch(
                """
                SELECT id, extracted_text
                FROM documents
                WHERE extracted_text IS NOT NULL
                """
            )

        return [{"id": r["id"], "text": r["extracted_text"]} for r in rows]

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
            WHERE document_id = $1
            ORDER BY analysis_date DESC
            LIMIT 1
            """,
            document_id,
        )
        return dict(row) if row else None


db_service = DatabaseService()




