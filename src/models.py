"""
Typed contracts for the Spotify Personalized AI Memory System.

These models cover:
- interaction/event contracts
- candidate and stored memories
- retrieval/context contracts
- feedback
- deletion status
- trace records

The contracts are intentionally explicit so API, worker,
retrieval, MCP, and frontend layers can share stable data shapes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# COMMON HELPERS
# ============================================================

def now_iso() -> str:
    """
    Return the current UTC timestamp in ISO-8601 format.
    """
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# ENUMS
# ============================================================

class MemoryType(str, Enum):
    EPISODE = "episode"
    EXPLICIT_PREFERENCE = "explicit_preference"
    CANDIDATE_PREFERENCE = "candidate_preference"
    EXCLUSION = "exclusion"
    CORRECTION = "correction"


class PolicyClass(str, Enum):
    STANDARD = "standard"
    SENSITIVE = "sensitive"
    BLOCKED = "blocked"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    DELETED = "deleted"


class CandidateDecision(str, Enum):
    """
    Decision produced by the memory extraction/governance stage.
    """

    ACCEPT = "accept"
    REJECT = "reject"
    REVIEW = "review"


# ============================================================
# INTERACTION EVENT
# ============================================================

class InteractionEvent(BaseModel):
    """
    Versioned raw interaction entering the memory pipeline.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    schema_version: str = "1.0"

    event_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    subject_id: str

    surface: str

    event_type: str

    text: Optional[str] = None

    locale: str = "en-IN"

    timestamp: str = Field(
        default_factory=now_iso
    )

    # --------------------------------------------------------
    # Provenance / governance
    # --------------------------------------------------------

    source: str = "api"

    consent: bool = True

    geography: Optional[str] = None
    age_group: Optional[str] = None

    # --------------------------------------------------------
    # Idempotency
    # --------------------------------------------------------

    idempotency_key: str = Field(
        default_factory=lambda: str(uuid4())
    )


# ============================================================
# MEMORY FACT
# ============================================================

class MemoryFact(BaseModel):
    """
    Canonical memory stored in graph and vector indexes.

    Every durable memory should carry:
    - subject ownership
    - memory type
    - confidence
    - policy class
    - provenance
    - temporal validity
    - retention information
    - lifecycle status
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    schema_version: str = "1.0"

    memory_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    subject_id: str

    memory_type: MemoryType

    fact_text: str

    entities: list[str] = Field(
        default_factory=list
    )

    # --------------------------------------------------------
    # Confidence / policy
    # --------------------------------------------------------

    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    policy_class: PolicyClass = (
        PolicyClass.STANDARD
    )

    # --------------------------------------------------------
    # Provenance
    # --------------------------------------------------------

    source_event_id: Optional[str] = None

    source: str = "memory_processor"

    # --------------------------------------------------------
    # Temporal validity
    # --------------------------------------------------------

    valid_from: str = Field(
        default_factory=now_iso
    )

    valid_to: Optional[str] = None

    recorded_at: str = Field(
        default_factory=now_iso
    )

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------

    status: MemoryStatus = (
        MemoryStatus.ACTIVE
    )

    superseded_by: Optional[str] = None

    # --------------------------------------------------------
    # Governance metadata
    # --------------------------------------------------------

    retention_class: str = "standard"

    geography: Optional[str] = None

    age_group: Optional[str] = None


# ============================================================
# MEMORY CANDIDATE
# ============================================================

class MemoryCandidate(BaseModel):
    """
    Structured candidate produced by memory extraction.

    This is NOT automatically a durable memory.

    The candidate must pass validation and policy checks
    before it can become a MemoryFact.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    # --------------------------------------------------------
    # Extraction decision
    # --------------------------------------------------------

    decision: CandidateDecision = (
        CandidateDecision.ACCEPT
    )

    # --------------------------------------------------------
    # Memory content
    # --------------------------------------------------------

    memory_type: MemoryType

    fact_text: str

    # Normalized representation of the extracted fact.
    normalized_fact: Optional[str] = None

    entities: list[str] = Field(
        default_factory=list
    )

    # --------------------------------------------------------
    # Ranking / confidence
    # --------------------------------------------------------

    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    # --------------------------------------------------------
    # Temporal scope
    # --------------------------------------------------------

    temporal_scope: Optional[str] = None

    # --------------------------------------------------------
    # Policy
    # --------------------------------------------------------

    policy_class: PolicyClass = (
        PolicyClass.STANDARD
    )

    policy_flags: list[str] = Field(
        default_factory=list
    )

    # --------------------------------------------------------
    # Explanation
    # --------------------------------------------------------

    reason: Optional[str] = None


# ============================================================
# RETRIEVED MEMORY
# ============================================================

class RetrievedMemory(BaseModel):
    """
    A memory returned by the hybrid retrieval layer.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    memory: MemoryFact

    relevance_score: float

    relevance_reason: str

    # --------------------------------------------------------
    # Retrieval provenance
    # --------------------------------------------------------

    retrieval_source: str = "hybrid"


# ============================================================
# CONTEXT PACKAGE
# ============================================================

class ContextPackage(BaseModel):
    """
    Structured memory package handed to the generation layer.

    Only policy-approved memories should appear here.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    schema_version: str = "1.0"

    subject_id: str

    intent: str

    memories: list[RetrievedMemory]

    fallback: bool = False

    # --------------------------------------------------------
    # End-to-end trace
    # --------------------------------------------------------

    trace_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    # --------------------------------------------------------
    # Memories actually allowed into context
    # --------------------------------------------------------

    influencing_memory_ids: list[str] = Field(
        default_factory=list
    )


# ============================================================
# FEEDBACK
# ============================================================

class FeedbackRequest(BaseModel):
    """
    User feedback about a personalized response or memory.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    subject_id: str

    feedback_type: str

    memory_id: Optional[str] = None

    trace_id: Optional[str] = None

    value: Optional[str] = None

    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    """
    Response returned after feedback is recorded.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    schema_version: str = "1.0"

    feedback_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    subject_id: str

    status: str = "recorded"


# ============================================================
# DELETION STATUS
# ============================================================

class DeletionStatus(BaseModel):
    """
    Status of a memory deletion job.

    Deletion must propagate across all relevant stores.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    schema_version: str = "1.0"

    job_id: str

    subject_id: str

    status: str

    memory_id: Optional[str] = None

    # --------------------------------------------------------
    # Deletion propagation
    # --------------------------------------------------------

    graph_deleted: bool = False

    vector_deleted: bool = False

    cache_deleted: bool = False

    operational_metadata_deleted: bool = False

    # --------------------------------------------------------
    # Timing
    # --------------------------------------------------------

    created_at: str = Field(
        default_factory=now_iso
    )

    completed_at: Optional[str] = None


# ============================================================
# TRACE RECORD
# ============================================================

class TraceRecord(BaseModel):
    """
    Minimal trace information for an end-to-end
    memory request.
    """

    model_config = ConfigDict(
        extra="allow"
    )

    trace_id: str

    subject_id: str

    event_id: Optional[str] = None

    memory_ids: list[str] = Field(
        default_factory=list
    )

    stages: list[str] = Field(
        default_factory=list
    )

    fallback: bool = False

    created_at: str = Field(
        default_factory=now_iso
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )