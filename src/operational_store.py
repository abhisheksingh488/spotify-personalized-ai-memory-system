"""
Durable operational storage for the Personalized AI Memory System.

PostgreSQL:
- traces
- feedback
- deletion jobs

Redis:
- short-lived operational cache
- deletion invalidation markers
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row
import redis

from .config import settings
from .models import DeletionStatus, FeedbackResponse, TraceRecord

log = logging.getLogger(__name__)


class OperationalStore:
    def __init__(self) -> None:
        self.postgres_url = settings.POSTGRES_URL
        self.redis_url = settings.REDIS_URL

        self._redis: Optional[redis.Redis] = None

        self._initialize_database()

    # ---------------------------------------------------------
    # Connections
    # ---------------------------------------------------------

    def _connect_postgres(self):
        return psycopg.connect(
            self.postgres_url,
            row_factory=dict_row,
        )

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
            )

        return self._redis

    # ---------------------------------------------------------
    # Database initialization
    # ---------------------------------------------------------

    def _initialize_database(self) -> None:
        with self._connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS operational_traces (
                        trace_id TEXT PRIMARY KEY,
                        subject_id TEXT NOT NULL,
                        event_id TEXT,
                        memory_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                        stages JSONB NOT NULL DEFAULT '[]'::jsonb,
                        fallback BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS operational_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        subject_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS deletion_jobs (
                        job_id TEXT PRIMARY KEY,
                        subject_id TEXT NOT NULL,
                        memory_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        graph_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                        vector_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                        cache_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                        operational_metadata_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL,
                        completed_at TIMESTAMPTZ
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_operational_traces_subject
                    ON operational_traces(subject_id)
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_feedback_subject
                    ON operational_feedback(subject_id)
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_deletion_jobs_subject
                    ON deletion_jobs(subject_id)
                    """
                )

            conn.commit()

    # ---------------------------------------------------------
    # TRACE
    # ---------------------------------------------------------

    def save_trace(self, trace: TraceRecord) -> None:
        with self._connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO operational_traces (
                        trace_id,
                        subject_id,
                        event_id,
                        memory_ids,
                        stages,
                        fallback,
                        created_at,
                        metadata
                    )
                    VALUES (
                        %s, %s, %s, %s::jsonb, %s::jsonb,
                        %s, %s, %s::jsonb
                    )
                    ON CONFLICT (trace_id)
                    DO UPDATE SET
                        subject_id = EXCLUDED.subject_id,
                        event_id = EXCLUDED.event_id,
                        memory_ids = EXCLUDED.memory_ids,
                        stages = EXCLUDED.stages,
                        fallback = EXCLUDED.fallback,
                        created_at = EXCLUDED.created_at,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        trace.trace_id,
                        trace.subject_id,
                        trace.event_id,
                        json.dumps(trace.memory_ids),
                        json.dumps(trace.stages),
                        trace.fallback,
                        trace.created_at,
                        json.dumps(trace.metadata),
                    ),
                )

            conn.commit()

        # Cache a serialized copy for quick trace lookup.
        self._get_redis().setex(
            f"trace:{trace.trace_id}",
            3600,
            json.dumps(trace.model_dump(mode="json")),
        )

    def get_trace(self, trace_id: str) -> Optional[TraceRecord]:
        redis_client = self._get_redis()

        cached = redis_client.get(f"trace:{trace_id}")

        if cached:
            try:
                return TraceRecord.model_validate(json.loads(cached))
            except Exception:
                log.warning(
                    "Invalid cached trace %s; falling back to PostgreSQL",
                    trace_id,
                )

        with self._connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        trace_id,
                        subject_id,
                        event_id,
                        memory_ids,
                        stages,
                        fallback,
                        created_at,
                        metadata
                    FROM operational_traces
                    WHERE trace_id = %s
                    """,
                    (trace_id,),
                )

                row = cur.fetchone()

        if not row:
            return None

        trace = TraceRecord(
            trace_id=row["trace_id"],
            subject_id=row["subject_id"],
            event_id=row["event_id"],
            memory_ids=row["memory_ids"] or [],
            stages=row["stages"] or [],
            fallback=row["fallback"],
            created_at=row["created_at"],
            metadata=row["metadata"] or {},
        )

        redis_client.setex(
            f"trace:{trace_id}",
            3600,
            json.dumps(trace.model_dump(mode="json")),
        )

        return trace

    def delete_trace_cache(self, trace_id: str) -> None:
        self._get_redis().delete(f"trace:{trace_id}")

    # ---------------------------------------------------------
    # FEEDBACK
    # ---------------------------------------------------------

    def save_feedback(self, feedback: FeedbackResponse) -> None:
        with self._connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO operational_feedback (
                        feedback_id,
                        subject_id,
                        status
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (feedback_id)
                    DO UPDATE SET
                        subject_id = EXCLUDED.subject_id,
                        status = EXCLUDED.status
                    """,
                    (
                        feedback.feedback_id,
                        feedback.subject_id,
                        feedback.status,
                    ),
                )

            conn.commit()

    # ---------------------------------------------------------
    # DELETION JOBS
    # ---------------------------------------------------------

    def save_deletion_job(self, deletion: DeletionStatus) -> None:
        with self._connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO deletion_jobs (
                        job_id,
                        subject_id,
                        memory_id,
                        status,
                        graph_deleted,
                        vector_deleted,
                        cache_deleted,
                        operational_metadata_deleted,
                        created_at,
                        completed_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (job_id)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        graph_deleted = EXCLUDED.graph_deleted,
                        vector_deleted = EXCLUDED.vector_deleted,
                        cache_deleted = EXCLUDED.cache_deleted,
                        operational_metadata_deleted =
                            EXCLUDED.operational_metadata_deleted,
                        completed_at = EXCLUDED.completed_at
                    """,
                    (
                        deletion.job_id,
                        deletion.subject_id,
                        deletion.memory_id,
                        deletion.status,
                        deletion.graph_deleted,
                        deletion.vector_deleted,
                        deletion.cache_deleted,
                        deletion.operational_metadata_deleted,
                        deletion.created_at,
                        deletion.completed_at,
                    ),
                )

            conn.commit()

        # Mark the memory as deleted in the operational cache.
        self._get_redis().setex(
            f"memory:deleted:{deletion.memory_id}",
            86400,
            json.dumps(
                {
                    "memory_id": deletion.memory_id,
                    "job_id": deletion.job_id,
                    "subject_id": deletion.subject_id,
                    "status": deletion.status,
                    "timestamp": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }
            ),
        )

    def get_deletion_job(
        self,
        job_id: str,
    ) -> Optional[DeletionStatus]:
        with self._connect_postgres() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        job_id,
                        subject_id,
                        memory_id,
                        status,
                        graph_deleted,
                        vector_deleted,
                        cache_deleted,
                        operational_metadata_deleted,
                        created_at,
                        completed_at
                    FROM deletion_jobs
                    WHERE job_id = %s
                    """,
                    (job_id,),
                )

                row = cur.fetchone()

        if not row:
            return None

        return DeletionStatus(
            job_id=row["job_id"],
            subject_id=row["subject_id"],
            memory_id=row["memory_id"],
            status=row["status"],
            graph_deleted=row["graph_deleted"],
            vector_deleted=row["vector_deleted"],
            cache_deleted=row["cache_deleted"],
            operational_metadata_deleted=row[
                "operational_metadata_deleted"
            ],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    def mark_memory_cache_deleted(self, memory_id: str) -> None:
        self._get_redis().delete(
            f"memory:deleted:{memory_id}"
        )

    # ---------------------------------------------------------
    # HEALTH
    # ---------------------------------------------------------

    def health(self) -> dict[str, Any]:
        postgres_ok = False
        redis_ok = False

        try:
            with self._connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    postgres_ok = cur.fetchone() is not None
        except Exception:
            log.exception("PostgreSQL health check failed")

        try:
            redis_ok = bool(self._get_redis().ping())
        except Exception:
            log.exception("Redis health check failed")

        return {
            "postgres": postgres_ok,
            "redis": redis_ok,
        }


operational_store = OperationalStore()