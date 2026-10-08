"""
FastAPI backend for the Spotify Personalized AI Memory System.

REST surface:
- POST /v1/events
- POST /v1/memories/extract
- POST /v1/memories
- POST /v1/memories/search
- POST /v1/context/compose
- PATCH /v1/memories/{memory_id}
- DELETE /v1/memories/{memory_id}
- GET /v1/deletions/{job_id}
- POST /v1/feedback
- GET /v1/traces/{trace_id}

Run:
    uvicorn src.api:app --reload --port 8000
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from pydantic import BaseModel, ConfigDict, Field
from src.tracing import init_tracing
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from src.security import (
    get_authenticated_subject,
    require_same_subject,
)

from src.graph_store import GraphStore
from src.vector_store import VectorStore
from src.agent import build_agent
from src.retrieval import retrieve
from src.context_composer import compose_context
from src.memory_processor import extract_candidates, process_event
from src.operational_store import operational_store as op_store

from src.metrics import (
    API_REQUESTS_TOTAL,
    API_REQUEST_LATENCY_SECONDS,
    API_AUTH_FAILURES_TOTAL,
    MEMORY_PROCESSING_TOTAL,
    MEMORY_PROCESSING_LATENCY_SECONDS,
    MEMORY_RETRIEVAL_TOTAL,
    MEMORY_RETRIEVAL_LATENCY_SECONDS,
    MEMORY_RETRIEVAL_RESULTS,
    MEMORY_RETRIEVAL_FALLBACK_TOTAL,
    MEMORY_CORRECTIONS_TOTAL,
    MEMORY_DELETIONS_TOTAL,
    CONTEXT_COMPOSITIONS_TOTAL,
    CONTEXT_COMPOSITION_LATENCY_SECONDS,
    CONTEXT_MEMORIES_INCLUDED,
    set_storage_health,
)

from src.models import (
    CandidateDecision,
    ContextPackage,
    DeletionStatus,
    FeedbackRequest,
    FeedbackResponse,
    InteractionEvent,
    MemoryCandidate,
    MemoryFact,
    MemoryType,
    PolicyClass,
    TraceRecord,
)


init_tracing()

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Spotify Personalized AI Memory System API",
    version="1.0",
)

FastAPIInstrumentor.instrument_app(app)
# ============================================================
# PROMETHEUS REQUEST METRICS MIDDLEWARE
# ============================================================

@app.middleware("http")
async def prometheus_request_metrics(request: Request, call_next):
    start_time = time.perf_counter()

    try:
        response = await call_next(request)

        status = str(response.status_code)

        # Avoid high-cardinality or sensitive route values.
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)

        API_REQUESTS_TOTAL.labels(
            method=request.method,
            route=route_path,
            status=status,
        ).inc()

        return response

    except Exception:
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unknown")

        API_REQUESTS_TOTAL.labels(
            method=request.method,
            route=route_path,
            status="500",
        ).inc()

        raise


    finally:
        elapsed = time.perf_counter() - start_time

        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)

        API_REQUEST_LATENCY_SECONDS.labels(
            method=request.method,
            route=route_path,
        ).observe(elapsed)

# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# LOGGING
# ============================================================

log = logging.getLogger(__name__)


# ============================================================
# SERVICES
# ============================================================

graph = GraphStore()
vectors = VectorStore()
agent = build_agent(graph, vectors)


# ============================================================
# IN-MEMORY OPERATIONAL STATE
# ============================================================
#
# These stores provide API-level trace/deletion status.
# A production deployment should persist them in PostgreSQL
# or another durable operational store.
# ============================================================

deletion_jobs: dict[str, DeletionStatus] = {}

traces: dict[str, TraceRecord] = {}

feedback_records: dict[str, FeedbackResponse] = {}


# ============================================================
# REQUEST / RESPONSE MODELS
# ============================================================

class ChatRequest(BaseModel):
    """
    Backward-compatible chat/event request.

    Existing clients can send:
        {
            "subject_id": "...",
            "message": "..."
        }

    Optional event fields allow the endpoint to also behave
    as the event ingestion surface.
    """

    model_config = ConfigDict(extra="forbid")

    subject_id: str
    message: str

    surface: str = "chat"
    event_type: str = "message"
    locale: str = "en-IN"

    consent: bool = True

    geography: Optional[str] = None
    age_group: Optional[str] = None

    idempotency_key: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    trace_id: str


class EventResponse(BaseModel):
    event_id: str
    idempotency_key: str
    trace_id: str
    status: str


class ExplicitPreferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    fact_text: str
    entities: list[str] = Field(default_factory=list)


class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    corrected_fact_text: str
    entities: list[str] = Field(default_factory=list)


class CreateMemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str

    memory_type: MemoryType

    fact_text: str

    entities: list[str] = Field(
        default_factory=list
    )

    confidence: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
    )

    policy_class: PolicyClass = (
        PolicyClass.STANDARD
    )

    source_event_id: Optional[str] = None

    valid_from: Optional[str] = None

    valid_to: Optional[str] = None

    retention_class: str = "standard"


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str

    intent: str

    limit: int = Field(
        default=10,
        ge=1,
        le=50,
    )


class ContextComposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str

    intent: str


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str

    text: str

    surface: str = "api"

    event_type: str = "message"

    locale: str = "en-IN"

    consent: bool = True

    geography: Optional[str] = None
    age_group: Optional[str] = None

    source: str = "api"

    idempotency_key: Optional[str] = None


class ExtractResponse(BaseModel):
    event_id: str

    candidates: list[MemoryCandidate]

    count: int


class MemoryCreateResponse(BaseModel):
    memory_id: str

    status: str

    memory_type: str

    policy_class: str


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_trace(
    subject_id: str,
    event_id: Optional[str] = None,
) -> TraceRecord:
    """
    Create and register an operational trace.
    """

    trace = TraceRecord(
        trace_id=str(uuid4()),
        subject_id=subject_id,
        event_id=event_id,
    )

    traces[trace.trace_id] = trace

    return trace


def _update_trace(
    trace_id: str,
    *,
    stage: Optional[str] = None,
    memory_ids: Optional[list[str]] = None,
    fallback: Optional[bool] = None,
) -> None:
    trace = traces.get(trace_id)

    if trace is None:
        return

    if stage and stage not in trace.stages:
        trace.stages.append(stage)

    if memory_ids:
        for memory_id in memory_ids:
            if memory_id not in trace.memory_ids:
                trace.memory_ids.append(memory_id)

    if fallback is not None:
        trace.fallback = fallback


def _validate_memory_text(
    fact_text: str,
) -> str:
    """
    Basic deterministic validation before durable storage.
    """

    text = fact_text.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Memory fact_text cannot be empty",
        )

    if len(text) > 2000:
        raise HTTPException(
            status_code=400,
            detail="Memory fact_text is too long",
        )

    return text


def _validate_policy(
    policy_class: PolicyClass,
) -> None:
    """
    BLOCKED content must never become durable memory.
    """

    if policy_class == PolicyClass.BLOCKED:
        raise HTTPException(
            status_code=400,
            detail="Blocked memories cannot be persisted",
        )


def _persist_memory(
    fact: MemoryFact,
) -> None:
    """
    Persist one canonical memory to graph and vector stores.
    """

    _validate_policy(fact.policy_class)

    graph.upsert_memory(fact)

    vectors.upsert(
        fact.memory_id,
        fact.subject_id,
        fact.fact_text,
    )


# ============================================================
# EVENTS
# ============================================================

@app.post(
    "/v1/events",
    response_model=EventResponse,
)
def send_event(
    req: ChatRequest,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    """
    Capture an interaction event.

    The event is sent through the normal agent capture path.
    The agent publishes to Kafka when available and falls
    back to synchronous processing when Kafka is unavailable.
    """

    require_same_subject(
        authenticated_subject,
        req.subject_id,
    )

    event = InteractionEvent(
        subject_id=authenticated_subject,
        surface=req.surface,
        event_type=req.event_type,
        text=req.message,
        locale=req.locale,
        consent=req.consent,
        geography=req.geography,
        age_group=req.age_group,
        idempotency_key=(
            req.idempotency_key
            or str(uuid4())
        ),
    )

    trace = _new_trace(
        authenticated_subject,
        event.event_id,
    )

    _update_trace(
        trace.trace_id,
        stage="capture",
    )

    try:
        result = agent.invoke(
            {
                "subject_id": authenticated_subject,
                "user_message": req.message,
            }
        )

        response_trace = result.get(
            "context_package"
        )

        if response_trace is not None:
            memory_ids = [
                item.memory.memory_id
                for item in response_trace.memories
            ]

            _update_trace(
                trace.trace_id,
                stage="retrieve",
                memory_ids=memory_ids,
                fallback=response_trace.fallback,
            )

    except Exception as exc:
        log.exception(
            "Event processing failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to process event",
        ) from exc

    _update_trace(
        trace.trace_id,
        stage="complete",
    )

    return EventResponse(
        event_id=event.event_id,
        idempotency_key=event.idempotency_key,
        trace_id=trace.trace_id,
        status="accepted",
    )


# ============================================================
# CHAT COMPATIBILITY ENDPOINT
# ============================================================

@app.post(
    "/v1/chat",
    response_model=ChatResponse,
)
def chat(
    req: ChatRequest,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    """
    Direct chat endpoint.

    Kept separate from /v1/events so event ingestion and
    conversational generation have clear responsibilities.
    """

    require_same_subject(
        authenticated_subject,
        req.subject_id,
    )

    trace = _new_trace(
        authenticated_subject
    )

    _update_trace(
        trace.trace_id,
        stage="capture",
    )

    try:
        result = agent.invoke(
            {
                "subject_id": authenticated_subject,
                "user_message": req.message,
            }
        )

        package = result.get(
            "context_package"
        )

        if package is not None:
            memory_ids = [
                item.memory.memory_id
                for item in package.memories
            ]

            _update_trace(
                trace.trace_id,
                stage="retrieve",
                memory_ids=memory_ids,
                fallback=package.fallback,
            )

        _update_trace(
            trace.trace_id,
            stage="generate",
        )

        response = result.get(
            "response",
            "",
        )

        _update_trace(
            trace.trace_id,
            stage="complete",
        )

        return ChatResponse(
            response=response,
            trace_id=trace.trace_id,
        )

    except Exception as exc:
        log.exception(
            "Chat failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to generate response",
        ) from exc


# ============================================================
# MEMORY EXTRACTION
# ============================================================

@app.post(
    "/v1/memories/extract",
    response_model=ExtractResponse,
)
def extract_memories(
    req: ExtractRequest,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    """
    Extract typed memory candidates from an interaction.

    Important:
    extraction does NOT automatically persist the candidate.
    """

    require_same_subject(
        authenticated_subject,
        req.subject_id,
    )

    event = InteractionEvent(
        subject_id=authenticated_subject,
        surface=req.surface,
        event_type=req.event_type,
        text=req.text,
        locale=req.locale,
        consent=req.consent,
        geography=req.geography,
        age_group=req.age_group,
        source=req.source,
        idempotency_key=(
            req.idempotency_key
            or str(uuid4())
        ),
    )

    if not event.consent:
        return ExtractResponse(
            event_id=event.event_id,
            candidates=[],
            count=0,
        )

    try:
        candidates = extract_candidates(
            event
        )
    except Exception as exc:
        log.exception(
            "Memory extraction failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Memory extraction failed",
        ) from exc

    # Never allow blocked candidates to become
    # durable memories through this endpoint.
    safe_candidates: list[MemoryCandidate] = []

    for candidate in candidates:
        if (
            candidate.policy_class
            == PolicyClass.BLOCKED
        ):
            continue

        safe_candidates.append(
            candidate
        )

    return ExtractResponse(
        event_id=event.event_id,
        candidates=safe_candidates,
        count=len(safe_candidates),
    )


# ============================================================
# LIST MEMORIES
# ============================================================

@app.get("/v1/memories")
def list_memories(
    subject_id: str,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    require_same_subject(
        authenticated_subject,
        subject_id,
    )

    return graph.get_active_memories(
        authenticated_subject
    )

# ============================================================
# SEARCH MEMORIES
# ============================================================

@app.post("/v1/memories/search")
def search_memories(
    req: SearchRequest,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    require_same_subject(
        authenticated_subject,
        req.subject_id,
    )

    trace = _new_trace(
        authenticated_subject
    )

    _update_trace(
        trace.trace_id,
        stage="retrieve",
    )

    retrieval_start = time.perf_counter()

    try:
        results = retrieve(
            authenticated_subject,
            req.intent,
            graph,
            vectors,
        )

        results = results[: req.limit]

        MEMORY_RETRIEVAL_TOTAL.labels(
            status="success"
        ).inc()

        MEMORY_RETRIEVAL_RESULTS.observe(
            len(results)
        )

        if not results:
            MEMORY_RETRIEVAL_FALLBACK_TOTAL.labels(
                reason="no_results"
            ).inc()

    except Exception:
        MEMORY_RETRIEVAL_TOTAL.labels(
            status="error"
        ).inc()

        raise

    finally:
        MEMORY_RETRIEVAL_LATENCY_SECONDS.observe(
            time.perf_counter() - retrieval_start
        )

    memory_ids = [
        item.memory.memory_id
        for item in results
    ]

    _update_trace(
        trace.trace_id,
        memory_ids=memory_ids,
    )

    _update_trace(
        trace.trace_id,
        stage="complete",
    )

    return {
        "trace_id": trace.trace_id,
        "subject_id": authenticated_subject,
        "results": [
            {
                "memory_id": r.memory.memory_id,
                "fact_text": r.memory.fact_text,
                "memory_type": (
                    r.memory.memory_type.value
                ),
                "confidence": r.memory.confidence,
                "policy_class": (
                    r.memory.policy_class.value
                ),
                "valid_from": r.memory.valid_from,
                "valid_to": r.memory.valid_to,
                "relevance_score": (
                    r.relevance_score
                ),
                "relevance_reason": (
                    r.relevance_reason
                ),
                "retrieval_source": (
                    r.retrieval_source
                ),
            }
            for r in results
        ],
    }
# ============================================================
# CONTEXT COMPOSITION
# ============================================================

@app.post(
    "/v1/context/compose",
    response_model=ContextPackage,
)
def compose_context_endpoint(
    req: ContextComposeRequest,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    require_same_subject(
        authenticated_subject,
        req.subject_id,
    )

    trace = _new_trace(
        authenticated_subject
    )

    _update_trace(
        trace.trace_id,
        stage="retrieve",
    )

    results = retrieve(
        authenticated_subject,
        req.intent,
        graph,
        vectors,
    )

    composition_start = time.perf_counter()

    try:
        package = compose_context(
            authenticated_subject,
            req.intent,
            results,
        )

        CONTEXT_COMPOSITIONS_TOTAL.labels(
            status="success"
        ).inc()

        CONTEXT_MEMORIES_INCLUDED.observe(
            len(package.memories)
        )

    except Exception:
        CONTEXT_COMPOSITIONS_TOTAL.labels(
            status="error"
        ).inc()

        raise

    finally:
        CONTEXT_COMPOSITION_LATENCY_SECONDS.observe(
            time.perf_counter() - composition_start
        )

    # Keep a single trace identifier for this request.
    package.trace_id = trace.trace_id

    package.influencing_memory_ids = [
        item.memory.memory_id
        for item in package.memories
    ]

    _update_trace(
        trace.trace_id,
        stage="compose_context",
        memory_ids=(
            package.influencing_memory_ids
        ),
        fallback=package.fallback,
    )

    _update_trace(
        trace.trace_id,
        stage="complete",
    )

    return package
# ============================================================
# CREATE MEMORY
# ============================================================

@app.post(
    "/v1/memories",
    response_model=MemoryCreateResponse,
)
def create_memory(
    req: CreateMemoryRequest,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    require_same_subject(
        authenticated_subject,
        req.subject_id,
    )

    _validate_policy(
        req.policy_class
    )

    fact_text = _validate_memory_text(
        req.fact_text
    )

    fact = MemoryFact(
        subject_id=authenticated_subject,
        memory_type=req.memory_type,
        fact_text=fact_text,
        entities=req.entities,
        confidence=req.confidence,
        policy_class=req.policy_class,
        source_event_id=req.source_event_id,
        valid_from=(
            req.valid_from
            or datetime.now(
                timezone.utc
            ).isoformat()
        ),
        valid_to=req.valid_to,
        retention_class=req.retention_class,
    )

    try:
        _persist_memory(fact)

    except Exception as exc:
        log.exception(
            "Memory persistence failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to persist memory",
        ) from exc

    return MemoryCreateResponse(
        memory_id=fact.memory_id,
        status="created",
        memory_type=fact.memory_type.value,
        policy_class=fact.policy_class.value,
    )


# ============================================================
# EXPLICIT PREFERENCE
# ============================================================

@app.post("/v1/memories/explicit")
def add_explicit_preference(
    req: ExplicitPreferenceRequest,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    require_same_subject(
        authenticated_subject,
        req.subject_id,
    )

    fact_text = _validate_memory_text(
        req.fact_text
    )

    fact = MemoryFact(
        subject_id=authenticated_subject,
        memory_type=(
            MemoryType.EXPLICIT_PREFERENCE
        ),
        fact_text=fact_text,
        entities=req.entities,
        confidence=0.95,
        policy_class=PolicyClass.STANDARD,
        source="explicit_user_input",
    )

    _persist_memory(fact)

    return {
        "memory_id": fact.memory_id,
        "status": "created",
        "confidence": fact.confidence,
    }


# ============================================================
# CORRECTION
# ============================================================

@app.patch(
    "/v1/memories/{memory_id}"
)
def correct_memory(
    memory_id: str,
    req: CorrectionRequest,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    require_same_subject(
        authenticated_subject,
        req.subject_id,
    )

    old_memory = graph.get_memory(
        memory_id
    )

    if not old_memory:
        raise HTTPException(
            status_code=404,
            detail="Memory not found",
        )

    if (
        old_memory.get("subject_id")
        != authenticated_subject
    ):
        raise HTTPException(
            status_code=403,
            detail="Memory access denied",
        )

    corrected_text = _validate_memory_text(
        req.corrected_fact_text
    )

    new_fact = MemoryFact(
        subject_id=authenticated_subject,
        memory_type=MemoryType.CORRECTION,
        fact_text=corrected_text,
        entities=req.entities,
        confidence=0.95,
        policy_class=PolicyClass.STANDARD,
        source="user_correction",
    )

    _persist_memory(new_fact)

    graph.supersede_memory(
        memory_id,
        new_fact.memory_id,
    )

    MEMORY_CORRECTIONS_TOTAL.labels(
        status="success"
    ).inc()

    return {
        "old_memory_id": memory_id,
        "new_memory_id": (
            new_fact.memory_id
        ),
        "status": "superseded_old",
    }


# ============================================================
# DELETE MEMORY
# ============================================================

@app.delete(
    "/v1/memories/{memory_id}"
)
def delete_memory(
    memory_id: str,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    memory = graph.get_memory(
        memory_id
    )

    if not memory:
        raise HTTPException(
            status_code=404,
            detail="Memory not found",
        )

    if (
        memory.get("subject_id")
        != authenticated_subject
    ):
        raise HTTPException(
            status_code=403,
            detail="Memory access denied",
        )

    job_id = str(uuid4())

    deletion = DeletionStatus(
        job_id=job_id,
        subject_id=authenticated_subject,
        memory_id=memory_id,
        status="processing",
    )

    deletion_jobs[job_id] = deletion

    try:
        graph.delete_memory(
            memory_id
        )

        deletion.graph_deleted = True

        vectors.delete(
            memory_id
        )

        deletion.vector_deleted = True

        # No separate cache/operational store exists
        # in the current API layer.
        deletion.cache_deleted = True
        deletion.operational_metadata_deleted = True

        deletion.status = "completed"

        deletion.completed_at = _now()

    except Exception as exc:
        deletion.status = "failed"

        log.exception(
            "Deletion failed for %s: %s",
            memory_id,
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Memory deletion failed. "
                f"job_id={job_id}"
            ),
        ) from exc
    MEMORY_DELETIONS_TOTAL.labels(
        status="success"
    ).inc()
    return {
        "job_id": job_id,
        "memory_id": memory_id,
        "status": deletion.status,
    }


# ============================================================
# DELETION STATUS
# ============================================================

@app.get(
    "/v1/deletions/{job_id}",
    response_model=DeletionStatus,
)
def get_deletion_status(
    job_id: str,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    deletion = deletion_jobs.get(
        job_id
    )

    if deletion is None:
        raise HTTPException(
            status_code=404,
            detail="Deletion job not found",
        )

    require_same_subject(
        authenticated_subject,
        deletion.subject_id,
    )

    return deletion


# ============================================================
# FEEDBACK
# ============================================================

@app.post(
    "/v1/feedback",
    response_model=FeedbackResponse,
)
def record_feedback(
    req: FeedbackRequest,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    require_same_subject(
        authenticated_subject,
        req.subject_id,
    )

    if req.memory_id:
        memory = graph.get_memory(
            req.memory_id
        )

        if not memory:
            raise HTTPException(
                status_code=404,
                detail="Referenced memory not found",
            )

        if (
            memory.get("subject_id")
            != authenticated_subject
        ):
            raise HTTPException(
                status_code=403,
                detail="Memory access denied",
            )

    if req.trace_id:
        trace = traces.get(
            req.trace_id
        )

        if trace is None:
            raise HTTPException(
                status_code=404,
                detail="Trace not found",
            )

        require_same_subject(
            authenticated_subject,
            trace.subject_id,
        )

    response = FeedbackResponse(
        subject_id=authenticated_subject,
        status="recorded",
    )

    feedback_records[
        response.feedback_id
    ] = response

    return response


# ============================================================
# TRACE
# ============================================================

@app.get(
    "/v1/traces/{trace_id}",
    response_model=TraceRecord,
)
def get_trace(
    trace_id: str,
    authenticated_subject: str = Depends(
        get_authenticated_subject
    ),
):
    trace = traces.get(
        trace_id
    )

    if trace is None:
        raise HTTPException(
            status_code=404,
            detail="Trace not found",
        )

    require_same_subject(
        authenticated_subject,
        trace.subject_id,
    )

    return trace

# ============================================================
# PROMETHEUS METRICS
# ============================================================

from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


@app.get("/metrics")
def metrics():
    """
    Prometheus metrics endpoint.

    Privacy:
    Metrics must never contain subject IDs, memory text,
    secrets, tokens, or other sensitive user information.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

# ============================================================
# HEALTH
# ============================================================

@app.get("/v1/health")
def health():
    """
    Report health of the API and all backing stores.

    Prometheus storage gauges are updated on every health check.
    No user memory content or subject identifiers are exposed.
    """

    # PostgreSQL + Redis
    try:
        operational = op_store.health()
    except Exception:
        operational = {
            "postgres": False,
            "redis": False,
        }

    postgres_healthy = bool(
        operational.get("postgres")
    )

    redis_healthy = bool(
        operational.get("redis")
    )

    # Neo4j
    try:
        neo4j_healthy = bool(
            graph.health_check()
        )
    except Exception:
        neo4j_healthy = False

    # Qdrant
    try:
        qdrant_healthy = bool(
            vectors.health_check()
        )
    except Exception:
        qdrant_healthy = False

    # Update Prometheus storage gauges
    set_storage_health(
        "neo4j",
        neo4j_healthy,
    )

    set_storage_health(
        "qdrant",
        qdrant_healthy,
    )

    set_storage_health(
        "postgresql",
        postgres_healthy,
    )

    set_storage_health(
        "redis",
        redis_healthy,
    )

    all_healthy = all(
        [
            neo4j_healthy,
            qdrant_healthy,
            postgres_healthy,
            redis_healthy,
        ]
    )

    return {
        "status": (
            "ok"
            if all_healthy
            else "degraded"
        ),
        "service": "spotify-memory-api",
        "version": "1.0",
        "storage": {
            "neo4j": neo4j_healthy,
            "qdrant": qdrant_healthy,
            "postgres": postgres_healthy,
            "redis": redis_healthy,
        },
        "operational_store": operational,
    }